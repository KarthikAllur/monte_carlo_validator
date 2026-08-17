"""
sql_parser.py — SQL parsing and count-query generation using SQLGlot.

Key design decisions
────────────────────
1.  We use SQLGlot's AST (not string operations / regex) for all parsing.
2.  The OUTER WHERE is obtained by reading ``outer_select.args["where"]``.
    SQLGlot keeps each SELECT node's WHERE separate from any nested SELECT's
    WHERE, so we can never accidentally pick up an inner condition.
3.  The complete FROM / JOIN tree is preserved in both generated queries.
4.  CTE definitions (``WITH`` clause) are automatically preserved because
    SQLGlot stores them inside the outermost ``Select`` node's ``with`` arg.
5.  UNION queries are rejected — the "outer WHERE" concept is ambiguous for
    a UNION and we prefer an explicit FAILED status over a silent wrong result.
"""

import logging
from typing import Optional, Tuple

import sqlglot
from sqlglot import exp

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

_UNSAFE_STATEMENT_TYPES: tuple = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.AlterTable,    # SQLGlot 23.x: ALTER TABLE
    exp.Create,
    exp.Merge,
    exp.TruncateTable, # SQLGlot 23.x: TRUNCATE TABLE
    exp.Command,       # catches remaining raw DDL
)


def parse_sql(sql: str) -> exp.Expression:
    """
    Parse a SQL string into a SQLGlot AST using the Snowflake dialect.

    Args:
        sql: Raw SQL string (may include trailing semicolon).

    Returns:
        Root SQLGlot expression.

    Raises:
        ValueError: If the SQL cannot be parsed.
    """
    cleaned = sql.strip().rstrip(";").strip()
    if not cleaned:
        raise ValueError("SQL string is empty after stripping.")

    try:
        parsed = sqlglot.parse_one(
            cleaned,
            dialect="snowflake",
            error_level=sqlglot.ErrorLevel.RAISE,
        )
    except sqlglot.errors.ParseError as exc:
        raise ValueError(f"SQLGlot could not parse the SQL: {exc}") from exc

    return parsed


def is_safe_select(sql: str) -> bool:
    """
    Return True only when *sql* is a syntactically valid SELECT statement.

    Rejects INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, MERGE, TRUNCATE and
    any other DDL / DML so we never accidentally mutate data.

    Args:
        sql: SQL string to validate.

    Returns:
        True if safe SELECT, False otherwise.
    """
    if not sql or not sql.strip():
        return False
    try:
        parsed = parse_sql(sql)
    except ValueError:
        return False

    if isinstance(parsed, _UNSAFE_STATEMENT_TYPES):
        return False

    # Must be a plain Select (or a Select carrying a WITH clause)
    return isinstance(parsed, exp.Select)


def generate_count_queries(sql: str) -> Tuple[str, Optional[str]]:
    """
    Parse *sql* and derive two validation queries for Snowflake execution.

    Algorithm
    ─────────
    1. Parse SQL with SQLGlot (Snowflake dialect).
    2. Identify the **outermost** SELECT node.
       - For plain SELECTs this is the root node.
       - For CTEs (WITH … SELECT) this is still the root ``exp.Select``
         node; the CTE body is stored in ``args["with"]`` and is left intact.
    3. Read ``outer_select.args["where"]`` — this is **exclusively** the
       WHERE of the outer query.  Inner WHERE clauses buried inside
       sub-selects are child nodes of those sub-selects and are NOT visible
       at this level.
    4. Build total_count_query:
       - Replace SELECT column list with ``COUNT(*)``.
       - Remove WHERE, GROUP BY, HAVING, ORDER BY, LIMIT, DISTINCT.
       - Keep FROM, all JOINs, and the WITH clause (if present).
    5. Build error_count_query (when outer WHERE exists):
       - Same as above but **keep** the WHERE clause.
    6. If no outer WHERE exists, return ``None`` for the error query.

    Args:
        sql: Raw Monte Carlo SQL query.

    Returns:
        Tuple ``(total_count_sql, error_count_sql)``.
        ``error_count_sql`` is ``None`` when the outer query has no WHERE.

    Raises:
        ValueError: On parse failure, unsupported SQL type, or unsafe SQL.
    """
    parsed = parse_sql(sql)
    outer_select = _get_outer_select(parsed)

    # ── Sanity-check: must be a SELECT, not DDL/DML ──────────────────
    if isinstance(parsed, _UNSAFE_STATEMENT_TYPES):
        raise ValueError(
            "Input SQL contains a non-SELECT statement (INSERT/UPDATE/DELETE/DDL). "
            "Only SELECT queries are supported."
        )

    # ── Read the outer WHERE ─────────────────────────────────────────
    # Because ``outer_select`` is the OUTERMOST Select node, its ``where``
    # arg only contains the top-level WHERE condition.  Any WHERE inside a
    # sub-select (e.g. ``WHERE id IN (SELECT … WHERE status = 'X')``) is
    # stored inside the child Select node, NOT here.
    outer_where: Optional[exp.Where] = outer_select.args.get("where")

    # ── Total count query ────────────────────────────────────────────
    total_stmt = _build_count_stmt(outer_select, keep_where=False)
    total_count_sql = total_stmt.sql(dialect="snowflake", pretty=True)
    logger.debug("total_count_query:\n%s", total_count_sql)

    # ── Error count query ────────────────────────────────────────────
    if outer_where is None:
        logger.debug("No outer WHERE clause found — error_count_query is None.")
        return total_count_sql, None

    error_stmt = _build_count_stmt(outer_select, keep_where=True)
    error_count_sql = error_stmt.sql(dialect="snowflake", pretty=True)
    logger.debug("error_count_query:\n%s", error_count_sql)

    return total_count_sql, error_count_sql


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_outer_select(parsed: exp.Expression) -> exp.Select:
    """
    Return the outermost ``exp.Select`` from a parsed expression.

    For a plain SELECT statement ``parsed`` is already an ``exp.Select``.
    For a CTE (``WITH … SELECT …``) SQLGlot also returns an ``exp.Select``
    where the CTE definitions live in ``args["with"]`` — so no special
    handling is required.

    UNION queries are rejected because the "outer WHERE" concept is
    ambiguous when multiple SELECT branches are combined.

    Args:
        parsed: Root expression returned by ``parse_sql``.

    Returns:
        The outermost ``exp.Select`` node.

    Raises:
        ValueError: For unsupported statement shapes.
    """
    if isinstance(parsed, exp.Select):
        return parsed

    if isinstance(parsed, exp.Union):
        raise ValueError(
            "UNION / UNION ALL / INTERSECT / EXCEPT queries are not supported for "
            "automatic count-query generation because the outer WHERE clause is "
            "ambiguous across multiple SELECT branches."
        )

    raise ValueError(
        f"Unsupported SQL statement type: '{type(parsed).__name__}'. "
        "Only SELECT (including CTEs) is supported."
    )


def _build_count_stmt(outer_select: exp.Select, keep_where: bool) -> exp.Select:
    """
    Clone *outer_select* and rewrite it as a ``SELECT COUNT(*)`` statement.

    Args:
        outer_select: The outermost SELECT node (may include WITH clause).
        keep_where:   If True the outer WHERE clause is preserved;
                      if False it is removed.

    Returns:
        A new ``exp.Select`` node ready for ``.sql()`` serialisation.
    """
    stmt: exp.Select = outer_select.copy()

    # Replace projected columns with COUNT(*)
    stmt.set("expressions", [exp.Count(this=exp.Star())])

    # Remove clauses that are irrelevant for a plain count
    stmt.set("distinct", None)
    stmt.set("group", None)
    stmt.set("having", None)
    stmt.set("order", None)
    stmt.set("limit", None)
    stmt.set("offset", None)
    stmt.set("qualify", None)    # Snowflake QUALIFY extension

    if not keep_where:
        stmt.set("where", None)

    return stmt
