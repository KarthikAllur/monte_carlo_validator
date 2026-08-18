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
    # Q01 - Customers with NULL name
    """SELECT
    customer_id,
    account_type,
    region,
    join_date
FROM CUSTOMERS
WHERE customer_name IS NULL""",

    # Q02 - Transactions with NULL amount
    """SELECT
    transaction_id,
    customer_id,
    tx_date,
    tx_type,
    status
FROM TRANSACTIONS
WHERE amount IS NULL""",

    # Q03 - Transactions with negative amount
    """SELECT
    transaction_id,
    customer_id,
    tx_date,
    tx_type,
    amount,
    status
FROM TRANSACTIONS
WHERE amount < 0""",

    # Q04 - Transactions with invalid status
    """SELECT
    transaction_id,
    customer_id,
    tx_date,
    amount,
    status
FROM TRANSACTIONS
WHERE status NOT IN ('COMPLETED', 'PENDING', 'FAILED', 'REVERSED')""",

    # Q05 - Customers with unrecognised risk rating
    """SELECT
    customer_id,
    customer_name,
    account_type,
    risk_rating
FROM CUSTOMERS
WHERE risk_rating NOT IN ('LOW', 'MEDIUM', 'HIGH')""",

    # Q06 - Orphaned transactions (no matching customer)
    """SELECT
    t.transaction_id,
    t.customer_id,
    t.tx_date,
    t.amount,
    t.status
FROM TRANSACTIONS t
LEFT JOIN CUSTOMERS c
    ON t.customer_id = c.customer_id
WHERE c.customer_id IS NULL""",

    # Q07 - Transactions referencing unknown product
    """SELECT
    t.transaction_id,
    t.customer_id,
    t.product_id,
    t.amount,
    t.tx_date
FROM TRANSACTIONS t
LEFT JOIN PRODUCTS p
    ON t.product_id = p.product_id
WHERE p.product_id IS NULL""",

    # Q08 - Account summary records with no matching customer
    """SELECT
    a.account_id,
    a.customer_id,
    a.current_balance,
    a.currency,
    a.last_updated
FROM ACCOUNT_SUMMARY a
LEFT JOIN CUSTOMERS c
    ON a.customer_id = c.customer_id
WHERE c.customer_id IS NULL""",

    # Q09 - Customers with no transaction history
    """SELECT
    customer_id,
    customer_name,
    account_type,
    risk_rating,
    join_date
FROM CUSTOMERS
WHERE customer_id NOT IN (
    SELECT DISTINCT customer_id
    FROM TRANSACTIONS
    WHERE customer_id IS NOT NULL
)""",

    # Q10 - Accounts with at least one FAILED transaction
    """SELECT
    a.account_id,
    a.customer_id,
    a.current_balance,
    a.currency
FROM ACCOUNT_SUMMARY a
WHERE EXISTS (
    SELECT 1
    FROM TRANSACTIONS t
    WHERE t.customer_id = a.customer_id
      AND t.status = 'FAILED'
)""",

    # Q11 - Transactions with future TX_DATE
    """SELECT
    transaction_id,
    customer_id,
    tx_date,
    amount,
    status
FROM TRANSACTIONS
WHERE tx_date > CURRENT_DATE()""",

    # Q12 - Accounts with negative current balance
    """SELECT
    account_id,
    customer_id,
    current_balance,
    currency,
    last_updated
FROM ACCOUNT_SUMMARY
WHERE current_balance < 0""",

    # Q13 - Products with NULL or zero minimum balance
    """SELECT
    product_id,
    product_name,
    category,
    interest_rate_pct,
    min_balance
FROM PRODUCTS
WHERE min_balance IS NULL
   OR min_balance <= 0""",

    # Q14 - High-risk customers with negative account balances (CTE)
    """WITH high_risk_customers AS (
    SELECT
        customer_id,
        customer_name,
        risk_rating
    FROM CUSTOMERS
    WHERE risk_rating = 'HIGH'
)
SELECT
    a.account_id,
    h.customer_name,
    h.risk_rating,
    a.current_balance,
    a.currency
FROM ACCOUNT_SUMMARY a
INNER JOIN high_risk_customers h
    ON a.customer_id = h.customer_id
WHERE a.current_balance < 0""",

    # Q15 - Transactions missing critical fields
    """SELECT
    transaction_id,
    customer_id,
    product_id,
    tx_date,
    tx_type,
    status,
    branch_code
FROM TRANSACTIONS
WHERE tx_type IS NULL
   OR status IS NULL
   OR branch_code IS NULL""",
]

OUTPUT_PATH = Path("input/input_queries.xlsx")


SAMPLE_LABELS = [
    "Q01 - Customers with NULL name",
    "Q02 - Transactions with NULL amount",
    "Q03 - Transactions with negative amount",
    "Q04 - Transactions with invalid status",
    "Q05 - Customers with unrecognised risk rating",
    "Q06 - Orphaned transactions (no matching customer)",
    "Q07 - Transactions referencing unknown product",
    "Q08 - Account summary records with no matching customer",
    "Q09 - Customers with no transaction history",
    "Q10 - Accounts with at least one FAILED transaction",
    "Q11 - Transactions with future TX_DATE",
    "Q12 - Accounts with negative current balance",
    "Q13 - Products with NULL or zero minimum balance",
    "Q14 - High-risk customers with negative account balances (CTE)",
    "Q15 - Transactions missing critical fields (tx_type, status, or branch_code)",
]


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame({
        "label":                         SAMPLE_LABELS,
        "Snowflake Compatible SQL Query": SAMPLE_QUERIES,
    })
    df.to_excel(str(OUTPUT_PATH), index=False, engine="openpyxl")

    print(f"Sample input file created: {OUTPUT_PATH}")
    print(f"  Rows written: {len(df)}")



if __name__ == "__main__":
    main()
