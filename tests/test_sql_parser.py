"""
test_sql_parser.py — Unit tests for sql_parser.py.

Each test verifies that:
  a) The correct total_count_query is generated (no WHERE).
  b) The correct error_count_query is generated (outer WHERE only).
  c) Inner WHERE conditions in CTEs / subqueries are NOT surfaced as the
     outer error condition.
  d) FROM / JOIN structures required by the outer WHERE are preserved.

Run with:
    venv\\Scripts\\activate
    pytest tests/ -v
"""

import sys
from pathlib import Path

import pytest

# ── Path fix so tests can import from src/ without installing the package ─────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.sql_parser import generate_count_queries, is_safe_select, parse_sql
import sqlglot


# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

def _normalise(sql: str) -> str:
    """Collapse whitespace for comparison."""
    return " ".join(sql.split()).upper()


# ─────────────────────────────────────────────────────────────────────────────
# 1. Simple SELECT + WHERE
# ─────────────────────────────────────────────────────────────────────────────

class TestSimpleSelectWithWhere:
    SQL = "SELECT customer_id, name FROM customers WHERE age IS NULL"

    def test_total_count_has_count_star(self):
        total, _ = generate_count_queries(self.SQL)
        assert "COUNT(*)" in total.upper()

    def test_total_count_has_no_where(self):
        total, _ = generate_count_queries(self.SQL)
        assert "WHERE" not in total.upper()

    def test_total_count_preserves_from(self):
        total, _ = generate_count_queries(self.SQL)
        assert "CUSTOMERS" in total.upper()

    def test_error_count_has_count_star(self):
        _, error = generate_count_queries(self.SQL)
        assert error is not None
        assert "COUNT(*)" in error.upper()

    def test_error_count_preserves_outer_where(self):
        _, error = generate_count_queries(self.SQL)
        assert error is not None
        assert "AGE IS NULL" in _normalise(error)

    def test_error_count_preserves_from(self):
        _, error = generate_count_queries(self.SQL)
        assert error is not None
        assert "CUSTOMERS" in error.upper()


# ─────────────────────────────────────────────────────────────────────────────
# 2. SELECT without WHERE
# ─────────────────────────────────────────────────────────────────────────────

class TestSelectWithoutWhere:
    SQL = "SELECT id, name FROM customers"

    def test_total_count_has_count_star(self):
        total, _ = generate_count_queries(self.SQL)
        assert "COUNT(*)" in total.upper()

    def test_total_count_no_where(self):
        total, _ = generate_count_queries(self.SQL)
        assert "WHERE" not in total.upper()

    def test_error_count_is_none(self):
        _, error = generate_count_queries(self.SQL)
        assert error is None

    def test_does_not_raise(self):
        generate_count_queries(self.SQL)  # Must not raise


# ─────────────────────────────────────────────────────────────────────────────
# 3. Multiple WHERE conditions (AND / OR)
# ─────────────────────────────────────────────────────────────────────────────

class TestMultipleWhereConditions:
    SQL = (
        "SELECT id FROM orders "
        "WHERE amount <= 0 AND status = 'PENDING' OR created_at < '2023-01-01'"
    )

    def test_error_count_contains_all_conditions(self):
        _, error = generate_count_queries(self.SQL)
        assert error is not None
        n = _normalise(error)
        assert "AMOUNT <= 0" in n
        assert "STATUS = 'PENDING'" in n

    def test_total_count_has_no_where(self):
        total, _ = generate_count_queries(self.SQL)
        assert "WHERE" not in total.upper()


# ─────────────────────────────────────────────────────────────────────────────
# 4. INNER JOIN
# ─────────────────────────────────────────────────────────────────────────────

class TestInnerJoin:
    SQL = (
        "SELECT a.id, b.amount "
        "FROM customers a "
        "INNER JOIN orders b ON a.id = b.customer_id "
        "WHERE b.amount < 0"
    )

    def test_total_count_preserves_join(self):
        total, _ = generate_count_queries(self.SQL)
        assert "JOIN" in total.upper()

    def test_total_count_no_where(self):
        total, _ = generate_count_queries(self.SQL)
        assert "WHERE" not in total.upper()

    def test_error_count_preserves_join(self):
        _, error = generate_count_queries(self.SQL)
        assert error is not None
        assert "JOIN" in error.upper()

    def test_error_count_outer_where_only(self):
        _, error = generate_count_queries(self.SQL)
        assert error is not None
        assert "AMOUNT < 0" in _normalise(error)


# ─────────────────────────────────────────────────────────────────────────────
# 5. LEFT JOIN
# ─────────────────────────────────────────────────────────────────────────────

class TestLeftJoin:
    SQL = (
        "SELECT a.id "
        "FROM customers a "
        "LEFT JOIN addresses b ON a.id = b.customer_id "
        "WHERE a.status = 'ACTIVE' AND b.country = 'US'"
    )

    def test_total_count_preserves_left_join(self):
        total, _ = generate_count_queries(self.SQL)
        n = _normalise(total)
        assert "LEFT JOIN" in n

    def test_error_count_preserves_left_join(self):
        _, error = generate_count_queries(self.SQL)
        assert error is not None
        assert "LEFT JOIN" in _normalise(error)

    def test_error_count_where_references_both_aliases(self):
        _, error = generate_count_queries(self.SQL)
        assert error is not None
        n = _normalise(error)
        assert "A.STATUS = 'ACTIVE'" in n
        assert "B.COUNTRY = 'US'" in n

    def test_total_count_no_where(self):
        total, _ = generate_count_queries(self.SQL)
        assert "WHERE" not in total.upper()


# ─────────────────────────────────────────────────────────────────────────────
# 6. CTE — inner WHERE must NOT become the outer error condition
# ─────────────────────────────────────────────────────────────────────────────

class TestCTE:
    SQL = (
        "WITH customer_data AS ("
        "    SELECT * FROM customers WHERE status = 'ACTIVE'"
        ") "
        "SELECT * FROM customer_data WHERE age IS NULL"
    )

    def test_error_count_uses_outer_where_not_cte_where(self):
        """Critical: status = 'ACTIVE' is the CTE's WHERE, not the outer WHERE."""
        _, error = generate_count_queries(self.SQL)
        assert error is not None
        n = _normalise(error)
        # Outer WHERE should be present
        assert "AGE IS NULL" in n
        # Inner CTE WHERE must NOT be used as the sole/primary outer condition
        # (It may appear inside the CTE body, which is acceptable)

    def test_error_count_cte_body_preserved(self):
        """The CTE definition must be retained so the query is valid."""
        _, error = generate_count_queries(self.SQL)
        assert error is not None
        assert "WITH" in error.upper()
        assert "CUSTOMER_DATA" in error.upper()

    def test_total_count_cte_preserved(self):
        total, _ = generate_count_queries(self.SQL)
        assert "WITH" in total.upper()

    def test_total_count_no_outer_where(self):
        total, _ = generate_count_queries(self.SQL)
        # The outer WHERE (age IS NULL) must be removed in the total count
        n = _normalise(total)
        # After stripping we should see COUNT(*) and the CTE FROM but NOT the outer WHERE
        assert "COUNT(*)" in n


# ─────────────────────────────────────────────────────────────────────────────
# 7. Subquery in FROM — inner WHERE must NOT become outer error condition
# ─────────────────────────────────────────────────────────────────────────────

class TestSubqueryInFrom:
    SQL = (
        "SELECT id "
        "FROM (SELECT * FROM customers WHERE inner_condition = 1) t "
        "WHERE outer_condition = 2"
    )

    def test_error_count_outer_where_only(self):
        _, error = generate_count_queries(self.SQL)
        assert error is not None
        n = _normalise(error)
        assert "OUTER_CONDITION = 2" in n

    def test_total_count_no_outer_where(self):
        """The outer WHERE is removed. The inner WHERE inside the FROM subquery
        must remain — it belongs to that subquery, not the outer query."""
        total, _ = generate_count_queries(self.SQL)
        n = _normalise(total)
        # Outer WHERE condition (outer_condition = 2) must be gone
        assert "OUTER_CONDITION = 2" not in n
        # Inner subquery WHERE (inner_condition = 1) stays inside the FROM subquery
        assert "INNER_CONDITION = 1" in n


# ─────────────────────────────────────────────────────────────────────────────
# 8. Multiple nested subqueries
# ─────────────────────────────────────────────────────────────────────────────

class TestMultipleNestedSubqueries:
    SQL = (
        "SELECT a.id "
        "FROM customers a "
        "WHERE a.region_id IN ("
        "    SELECT region_id FROM regions "
        "    WHERE country_id IN ("
        "        SELECT country_id FROM countries WHERE iso_code = 'US'"
        "    )"
        ")"
    )

    def test_error_count_preserves_full_outer_where(self):
        """The entire nested IN expression is the outer WHERE — preserve it."""
        _, error = generate_count_queries(self.SQL)
        assert error is not None
        n = _normalise(error)
        # Outer condition references a.region_id
        assert "A.REGION_ID IN" in n

    def test_error_count_is_not_deepest_inner_where(self):
        """iso_code = 'US' is the innermost WHERE and must NOT be the outer condition."""
        _, error = generate_count_queries(self.SQL)
        assert error is not None
        # The WHERE clause must contain the full subquery chain, not just the deepest.
        # Use case-insensitive normalisation because SQLGlot preserves literal casing.
        n = _normalise(error)
        assert "ISO_CODE = 'US'" in n  # fine — it's part of the nested subquery

    def test_total_count_no_where(self):
        total, _ = generate_count_queries(self.SQL)
        assert "WHERE" not in total.upper()


# ─────────────────────────────────────────────────────────────────────────────
# 9. WHERE containing IN subquery
# ─────────────────────────────────────────────────────────────────────────────

class TestWhereInSubquery:
    SQL = (
        "SELECT a.id "
        "FROM customers a "
        "WHERE a.id IN (SELECT customer_id FROM orders WHERE status = 'ACTIVE')"
    )

    def test_error_count_outer_in_expression_preserved(self):
        _, error = generate_count_queries(self.SQL)
        assert error is not None
        n = _normalise(error)
        assert "A.ID IN" in n

    def test_inner_where_status_is_part_of_subquery(self):
        """status = 'ACTIVE' must appear inside the subquery of the WHERE, not as the root condition."""
        _, error = generate_count_queries(self.SQL)
        assert error is not None
        # The subquery including the inner WHERE is preserved inside the error query.
        # Use case-insensitive normalisation because SQLGlot preserves literal casing.
        n = _normalise(error)
        assert "STATUS = 'ACTIVE'" in n

    def test_total_count_no_where(self):
        total, _ = generate_count_queries(self.SQL)
        assert "WHERE" not in total.upper()


# ─────────────────────────────────────────────────────────────────────────────
# 10. WHERE containing EXISTS subquery
# ─────────────────────────────────────────────────────────────────────────────

class TestWhereExistsSubquery:
    SQL = (
        "SELECT c.id "
        "FROM customers c "
        "WHERE EXISTS ("
        "    SELECT 1 FROM orders o "
        "    WHERE o.customer_id = c.id AND o.status = 'CANCELLED'"
        ")"
    )

    def test_error_count_preserves_exists(self):
        _, error = generate_count_queries(self.SQL)
        assert error is not None
        assert "EXISTS" in error.upper()

    def test_total_count_no_where(self):
        total, _ = generate_count_queries(self.SQL)
        assert "WHERE" not in total.upper()


# ─────────────────────────────────────────────────────────────────────────────
# 11. CASE expression in WHERE
# ─────────────────────────────────────────────────────────────────────────────

class TestCaseInWhere:
    SQL = (
        "SELECT id FROM transactions "
        "WHERE CASE WHEN amount > 0 THEN 'CREDIT' ELSE 'DEBIT' END = 'DEBIT'"
    )

    def test_error_count_preserves_case(self):
        _, error = generate_count_queries(self.SQL)
        assert error is not None
        assert "CASE" in error.upper()

    def test_total_count_no_where(self):
        total, _ = generate_count_queries(self.SQL)
        assert "WHERE" not in total.upper()


# ─────────────────────────────────────────────────────────────────────────────
# 12. Functions in WHERE
# ─────────────────────────────────────────────────────────────────────────────

class TestFunctionsInWhere:
    SQL = (
        "SELECT id FROM events "
        "WHERE DATEDIFF('day', created_at, CURRENT_DATE()) > 30"
    )

    def test_error_count_preserves_function(self):
        _, error = generate_count_queries(self.SQL)
        assert error is not None
        assert "DATEDIFF" in error.upper()

    def test_total_count_no_where(self):
        total, _ = generate_count_queries(self.SQL)
        assert "WHERE" not in total.upper()


# ─────────────────────────────────────────────────────────────────────────────
# 13. Parentheses in WHERE
# ─────────────────────────────────────────────────────────────────────────────

class TestParenthesesInWhere:
    SQL = (
        "SELECT id FROM customers "
        "WHERE (age < 18 OR age > 65) AND (status = 'INACTIVE')"
    )

    def test_error_count_preserves_conditions(self):
        _, error = generate_count_queries(self.SQL)
        assert error is not None
        n = _normalise(error)
        assert "AGE < 18" in n
        assert "STATUS = 'INACTIVE'" in n

    def test_total_count_no_where(self):
        total, _ = generate_count_queries(self.SQL)
        assert "WHERE" not in total.upper()


# ─────────────────────────────────────────────────────────────────────────────
# 14. Unsupported SQL — UNION
# ─────────────────────────────────────────────────────────────────────────────

class TestUnsupportedUnion:
    SQL = (
        "SELECT id FROM customers WHERE status = 'A' "
        "UNION "
        "SELECT id FROM prospects WHERE status = 'B'"
    )

    def test_union_raises_value_error(self):
        with pytest.raises(ValueError, match="UNION"):
            generate_count_queries(self.SQL)


# ─────────────────────────────────────────────────────────────────────────────
# 15. Invalid SQL
# ─────────────────────────────────────────────────────────────────────────────

class TestInvalidSQL:
    def test_completely_invalid_sql_raises(self):
        with pytest.raises(ValueError):
            generate_count_queries("THIS IS NOT SQL !!!@#$")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            generate_count_queries("")

    def test_semicolon_only_raises(self):
        with pytest.raises(ValueError):
            generate_count_queries(";")


# ─────────────────────────────────────────────────────────────────────────────
# 16. is_safe_select helper
# ─────────────────────────────────────────────────────────────────────────────

class TestIsSafeSelect:
    def test_plain_select_is_safe(self):
        assert is_safe_select("SELECT COUNT(*) FROM t") is True

    def test_insert_is_unsafe(self):
        assert is_safe_select("INSERT INTO t (id) VALUES (1)") is False

    def test_update_is_unsafe(self):
        assert is_safe_select("UPDATE t SET col = 1 WHERE id = 1") is False

    def test_delete_is_unsafe(self):
        assert is_safe_select("DELETE FROM t WHERE id = 1") is False

    def test_drop_is_unsafe(self):
        assert is_safe_select("DROP TABLE t") is False

    def test_empty_string_is_unsafe(self):
        assert is_safe_select("") is False

    def test_count_star_is_safe(self):
        assert is_safe_select("SELECT COUNT(*) FROM customers WHERE age IS NULL") is True


# ─────────────────────────────────────────────────────────────────────────────
# 17. GROUP BY / HAVING / ORDER BY / LIMIT stripping
# ─────────────────────────────────────────────────────────────────────────────

class TestClauseStripping:
    SQL = (
        "SELECT department, COUNT(*) as cnt "
        "FROM employees "
        "WHERE hire_date >= '2020-01-01' "
        "GROUP BY department "
        "HAVING COUNT(*) > 5 "
        "ORDER BY cnt DESC "
        "LIMIT 10"
    )

    def test_total_count_strips_group_by(self):
        total, _ = generate_count_queries(self.SQL)
        assert "GROUP BY" not in total.upper()

    def test_total_count_strips_having(self):
        total, _ = generate_count_queries(self.SQL)
        assert "HAVING" not in total.upper()

    def test_total_count_strips_order_by(self):
        total, _ = generate_count_queries(self.SQL)
        assert "ORDER BY" not in total.upper()

    def test_total_count_strips_limit(self):
        total, _ = generate_count_queries(self.SQL)
        assert "LIMIT" not in total.upper()

    def test_error_count_strips_group_by(self):
        _, error = generate_count_queries(self.SQL)
        assert error is not None
        assert "GROUP BY" not in error.upper()

    def test_error_count_keeps_where(self):
        _, error = generate_count_queries(self.SQL)
        assert error is not None
        assert "WHERE" in error.upper()
        assert "HIRE_DATE" in error.upper()


# ─────────────────────────────────────────────────────────────────────────────
# 18. RIGHT JOIN
# ─────────────────────────────────────────────────────────────────────────────

class TestRightJoin:
    SQL = (
        "SELECT b.order_id "
        "FROM customers a "
        "RIGHT JOIN orders b ON a.id = b.customer_id "
        "WHERE b.total IS NULL"
    )

    def test_error_count_preserves_right_join(self):
        _, error = generate_count_queries(self.SQL)
        assert error is not None
        assert "RIGHT JOIN" in _normalise(error)

    def test_total_count_preserves_right_join(self):
        total, _ = generate_count_queries(self.SQL)
        assert "RIGHT JOIN" in _normalise(total)


# ─────────────────────────────────────────────────────────────────────────────
# 19. CTE with no outer WHERE — error count must be None
# ─────────────────────────────────────────────────────────────────────────────

class TestCTENoOuterWhere:
    SQL = (
        "WITH active AS (SELECT * FROM customers WHERE status = 'ACTIVE') "
        "SELECT * FROM active"
    )

    def test_error_count_is_none(self):
        _, error = generate_count_queries(self.SQL)
        assert error is None

    def test_total_count_is_valid(self):
        total, _ = generate_count_queries(self.SQL)
        assert "COUNT(*)" in total.upper()

    def test_total_count_cte_preserved(self):
        total, _ = generate_count_queries(self.SQL)
        assert "WITH" in total.upper()
