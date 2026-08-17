"""
create_sample_input.py — Generates a sample input_queries.xlsx for testing.

Run once after setup:
    venv\\Scripts\\python create_sample_input.py
"""

import sys
from pathlib import Path

try:
    import pandas as pd
    import openpyxl  # noqa: F401  # ensure openpyxl is available
except ImportError:
    print("ERROR: pandas / openpyxl not installed. Run setup.bat first.")
    sys.exit(1)

SAMPLE_QUERIES = [
    # 1. Simple WHERE
    "SELECT customer_id, name FROM customers WHERE age IS NULL",
    # 2. No WHERE
    "SELECT id, name FROM customers",
    # 3. Multiple conditions
    "SELECT id FROM orders WHERE amount <= 0 AND status = 'PENDING'",
    # 4. LEFT JOIN
    (
        "SELECT a.id FROM customers a "
        "LEFT JOIN addresses b ON a.id = b.customer_id "
        "WHERE a.status = 'ACTIVE' AND b.country = 'US'"
    ),
    # 5. IN subquery — inner WHERE must NOT be the outer error condition
    (
        "SELECT a.id FROM customers a "
        "WHERE a.id IN (SELECT customer_id FROM orders WHERE status = 'ACTIVE')"
    ),
    # 6. CTE — inner CTE WHERE must NOT become the outer error condition
    (
        "WITH customer_data AS ("
        "    SELECT * FROM customers WHERE status = 'ACTIVE'"
        ") "
        "SELECT * FROM customer_data WHERE age IS NULL"
    ),
    # 7. EXISTS subquery
    (
        "SELECT c.id FROM customers c "
        "WHERE EXISTS ("
        "    SELECT 1 FROM orders o "
        "    WHERE o.customer_id = c.id AND o.status = 'CANCELLED'"
        ")"
    ),
    # 8. CASE in WHERE
    (
        "SELECT id FROM transactions "
        "WHERE CASE WHEN amount > 0 THEN 'CREDIT' ELSE 'DEBIT' END = 'DEBIT'"
    ),
    # 9. Function in WHERE
    "SELECT id FROM events WHERE DATEDIFF('day', created_at, CURRENT_DATE()) > 30",
    # 10. Multiple nested subqueries
    (
        "SELECT a.id FROM customers a "
        "WHERE a.region_id IN ("
        "    SELECT region_id FROM regions "
        "    WHERE country_id IN ("
        "        SELECT country_id FROM countries WHERE iso_code = 'US'"
        "    )"
        ")"
    ),
]

OUTPUT_PATH = Path("input/input_queries.xlsx")


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame({"query": SAMPLE_QUERIES})
    df.to_excel(str(OUTPUT_PATH), index=False, engine="openpyxl")

    print(f"Sample input file created: {OUTPUT_PATH}")
    print(f"  Rows written: {len(df)}")


if __name__ == "__main__":
    main()
