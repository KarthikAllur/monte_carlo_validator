# Monte Carlo SQL Validator

A production-quality local Python application that reads SQL queries from an
Excel file (exported from Monte Carlo), generates validation COUNT queries for
each SQL, executes them in Snowflake, and writes the results back to an output
Excel file.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [Prerequisites](#3-prerequisites)
4. [Python Installation](#4-python-installation)
5. [Virtual Environment Setup](#5-virtual-environment-setup)
6. [Installing Dependencies](#6-installing-dependencies)
7. [.env Configuration](#7-env-configuration)
8. [Snowflake Configuration Details](#8-snowflake-configuration-details)
9. [Input Excel Format](#9-input-excel-format)
10. [Output Excel Format](#10-output-excel-format)
11. [How SQL Parsing Works](#11-how-sql-parsing-works)
12. [Outer WHERE Rule](#12-outer-where-rule)
13. [Running the Application](#13-running-the-application)
14. [Running Tests](#14-running-tests)
15. [Troubleshooting](#15-troubleshooting)
16. [Future SharePoint Integration](#16-future-sharepoint-integration)

---

## 1. Project Overview

Monte Carlo sends data quality alerts as SQL queries.  This tool:

1. Reads every SQL query from `input/input_queries.xlsx`.
2. Parses each query using **SQLGlot** (AST-based, never regex).
3. Generates two validation queries per input query:
   - **total_count_query** — `SELECT COUNT(*) FROM <outer table/joins>` (no WHERE).
   - **error_count_query** — `SELECT COUNT(*) FROM <outer table/joins> WHERE <outer condition>`.
4. Executes both queries against **Snowflake** using the official connector.
5. Writes all results to `output/output_results.xlsx`.

One failed row never stops the batch — it is marked `FAILED` and processing continues.

---

## 2. Architecture

```
monte_carlo_validator/
│
├── src/
│   ├── main.py               # Entry point
│   ├── config.py             # Loads .env credentials
│   ├── logger.py             # Centralised logging setup
│   ├── sql_parser.py         # SQLGlot-based SQL parsing + query generation
│   ├── snowflake_connector.py# Snowflake connection / execution
│   ├── excel_handler.py      # Read input Excel / write output Excel
│   └── query_processor.py   # Orchestrates parse → validate → execute → record
│
├── tests/
│   └── test_sql_parser.py    # 19 test classes covering all SQL patterns
│
├── input/
│   └── input_queries.xlsx    # ← Place your queries here
│
├── output/
│   └── output_results.xlsx   # ← Generated automatically
│
├── logs/
│   └── application.log       # ← Generated automatically
│
├── create_sample_input.py    # Helper to generate a sample input Excel
├── .env                      # Your credentials (never commit)
├── .env.example              # Template for .env
├── requirements.txt
├── setup.bat
├── run.bat
└── README.md
```

**Data flow:**

```
input_queries.xlsx
       │
       ▼
 excel_handler.read_queries()
       │
       ▼ (list of SQL strings)
 query_processor.process_all_queries()
       │
       ├──► sql_parser.generate_count_queries()  [SQLGlot AST]
       │
       ├──► sql_parser.is_safe_select()          [safety check]
       │
       └──► snowflake_connector.execute_scalar() [Snowflake]
                      │
                      ▼
            excel_handler.write_results()
                      │
                      ▼
            output_results.xlsx
```

---

## 3. Prerequisites

| Requirement | Details |
|---|---|
| Windows 10/11 | All scripts are `.bat` files |
| Python 3.9+ | Download from https://python.org |
| Snowflake account | With warehouse, database, and schema access |
| Input Excel file | Must contain a column named `query` |

---

## 4. Python Installation

1. Go to https://www.python.org/downloads/
2. Download Python 3.11 or later.
3. Run the installer. **Check "Add Python to PATH"** before clicking Install.
4. Verify:

```cmd
python --version
```

Expected output: `Python 3.11.x` (or similar).

---

## 5. Virtual Environment Setup

Open a Command Prompt in the project root folder, then run:

```cmd
setup.bat
```

`setup.bat` will:
1. Verify Python is installed.
2. Create `venv/` virtual environment.
3. Activate it.
4. Upgrade pip.
5. Install all dependencies from `requirements.txt`.

You only need to run `setup.bat` **once**, or after modifying `requirements.txt`.

---

## 6. Installing Dependencies

Dependencies are installed automatically by `setup.bat`. To install manually:

```cmd
venv\Scripts\activate
pip install -r requirements.txt
```

Key libraries:

| Library | Purpose |
|---|---|
| `sqlglot` | AST-based SQL parsing |
| `snowflake-connector-python` | Official Snowflake connector |
| `pandas` | Excel read/write |
| `openpyxl` | Excel engine for pandas |
| `python-dotenv` | Load `.env` credentials |
| `pytest` | Unit testing |

---

## 7. .env Configuration

**Step 1** — Copy the template:

```cmd
copy .env.example .env
```

**Step 2** — Open `.env` in Notepad or any text editor:

```
SNOWFLAKE_ACCOUNT=myorg-myaccount
SNOWFLAKE_USER=my_username
SNOWFLAKE_PASSWORD=my_password
SNOWFLAKE_WAREHOUSE=MY_WAREHOUSE
SNOWFLAKE_DATABASE=MY_DATABASE
SNOWFLAKE_SCHEMA=MY_SCHEMA
SNOWFLAKE_ROLE=MY_ROLE
```

- `SNOWFLAKE_ROLE` is optional. Leave it blank to use your user's default role.
- The `.env` file is excluded from git via `.gitignore`.  **Never commit it.**

---

## 8. Snowflake Configuration Details

| Variable | Description | Example |
|---|---|---|
| `SNOWFLAKE_ACCOUNT` | Account identifier (without `.snowflakecomputing.com`) | `xy12345.us-east-1` |
| `SNOWFLAKE_USER` | Snowflake username | `john.doe` |
| `SNOWFLAKE_PASSWORD` | Snowflake password | `S3cur3P@ss!` |
| `SNOWFLAKE_WAREHOUSE` | Compute warehouse | `COMPUTE_WH` |
| `SNOWFLAKE_DATABASE` | Default database | `PROD_DB` |
| `SNOWFLAKE_SCHEMA` | Default schema | `PUBLIC` |
| `SNOWFLAKE_ROLE` | Optional role override | `ANALYST` |

> **Finding your account identifier:** In Snowsight go to Admin → Accounts and copy the Account Locator or Account URL segment.

---

## 9. Input Excel Format

Place your file at: `input/input_queries.xlsx`

The file must contain a column named **`query`** (exactly, case-sensitive):

| query |
|---|
| `SELECT customer_id, name FROM customers WHERE age IS NULL` |
| `SELECT id FROM orders WHERE amount <= 0` |
| `SELECT * FROM customers` |

- Blank rows are automatically skipped.
- Each query may be complex (JOINs, CTEs, subqueries, etc.).
- Trailing semicolons are stripped automatically.

To generate a sample input file:

```cmd
venv\Scripts\activate
python create_sample_input.py
```

---

## 10. Output Excel Format

The file is written to: `output/output_results.xlsx`

| Column | Description |
|---|---|
| `query` | Original Monte Carlo query |
| `total_count_query` | Generated `SELECT COUNT(*) FROM …` (no WHERE) |
| `error_count_query` | Generated `SELECT COUNT(*) FROM … WHERE <outer_condition>` |
| `total_count` | Result from Snowflake (integer) |
| `error_count` | Result from Snowflake (integer), or blank if no outer WHERE |
| `status` | `SUCCESS` or `FAILED` |
| `error_message` | Error details if status is `FAILED`, otherwise blank |

---

## 11. How SQL Parsing Works

The application uses **SQLGlot** to parse each SQL string into an Abstract
Syntax Tree (AST).  It does NOT use `str.split()`, `split("WHERE")`, or
regular expressions for parsing.

**Why SQLGlot?**
- Handles arbitrarily complex SQL: JOINs, CTEs, nested subqueries, functions,
  CASE expressions, HAVING, etc.
- Snowflake dialect support is built in.
- Provides clean, structured access to every clause via `.args`.

**How the outer SELECT is identified:**

```python
parsed = sqlglot.parse_one(sql, dialect="snowflake")
# For both plain SELECT and CTE (WITH … SELECT), parsed is exp.Select
outer_where = parsed.args.get("where")
```

`parsed.args["where"]` contains **only** the WHERE clause of the outermost
SELECT.  Inner WHERE clauses inside subqueries or CTEs are stored as children
of those inner Select nodes, not at the top level.

**How count queries are built:**

```python
# Clone the outermost Select node
total_stmt = outer_select.copy()
# Replace column list with COUNT(*)
total_stmt.set("expressions", [exp.Count(this=exp.Star())])
# Remove clauses irrelevant to counting
total_stmt.set("where", None)      # For total count only
total_stmt.set("group", None)
total_stmt.set("having", None)
total_stmt.set("order", None)
total_stmt.set("limit", None)
# Serialise back to SQL
total_count_sql = total_stmt.sql(dialect="snowflake", pretty=True)
```

The `from` and `joins` args are untouched, preserving all JOIN structures.

---

## 12. Outer WHERE Rule

**Rule:** Only the WHERE clause of the OUTERMOST SELECT is used for the
error-count query.  Inner WHERE clauses (inside CTEs, subqueries, EXISTS, IN
expressions) are ignored as standalone conditions — they remain as part of the
nested expression when that expression itself is the outer WHERE condition.

### Example 1 — Subquery in WHERE

```sql
SELECT a.id
FROM customers a
WHERE a.id IN (
    SELECT customer_id
    FROM orders
    WHERE status = 'ACTIVE'   -- INNER WHERE (not extracted)
)
```

Generated error query:

```sql
SELECT COUNT(*)
FROM customers AS a
WHERE
  a.id IN (SELECT customer_id FROM orders WHERE status = 'ACTIVE')
```

The outer WHERE condition is the entire `a.id IN (...)` expression.
`status = 'ACTIVE'` is **inside** the subquery and is preserved as part of it.

### Example 2 — CTE

```sql
WITH customer_data AS (
    SELECT * FROM customers WHERE status = 'ACTIVE'  -- INNER WHERE (not extracted)
)
SELECT * FROM customer_data WHERE age IS NULL        -- OUTER WHERE ✓
```

Generated error query:

```sql
WITH customer_data AS (SELECT * FROM customers WHERE status = 'ACTIVE')
SELECT COUNT(*)
FROM customer_data
WHERE age IS NULL
```

### Example 3 — No outer WHERE

```sql
SELECT id, name FROM customers
```

- `total_count_query`: `SELECT COUNT(*) FROM customers`
- `error_count_query`: `N/A — no outer WHERE clause` *(no Snowflake execution)*
- `error_count`: blank

---

## 13. Running the Application

From the project root directory:

```cmd
run.bat
```

`run.bat` will:
1. Check that `venv/` exists (if not, prompt to run `setup.bat`).
2. Activate the virtual environment.
3. Check that `.env` exists.
4. Warn if `input/input_queries.xlsx` is missing.
5. Execute `python src/main.py`.
6. Print a success or failure summary.

**Results** appear in `output/output_results.xlsx`.  
**Detailed logs** appear in `logs/application.log`.

### Manual execution

```cmd
venv\Scripts\activate
python src\main.py
```

---

## 14. Running Tests

```cmd
venv\Scripts\activate
pytest tests/ -v
```

Expected output: 60+ passing tests.

To run a specific test class:

```cmd
pytest tests/test_sql_parser.py::TestCTE -v
```

To see which SQL is generated by each test:

```cmd
pytest tests/ -v -s
```

### What the tests cover

| # | Scenario |
|---|---|
| 1 | Simple SELECT + WHERE |
| 2 | SELECT without WHERE |
| 3 | Multiple WHERE conditions (AND / OR) |
| 4 | INNER JOIN |
| 5 | LEFT JOIN |
| 6 | CTE — inner CTE WHERE must NOT become outer error condition |
| 7 | Subquery in FROM — inner WHERE must NOT become outer error condition |
| 8 | Multiple nested subqueries |
| 9 | WHERE containing IN subquery |
| 10 | WHERE containing EXISTS subquery |
| 11 | CASE expression in WHERE |
| 12 | Functions in WHERE |
| 13 | Parentheses in WHERE |
| 14 | UNION — unsupported, must raise ValueError |
| 15 | Completely invalid SQL — must raise ValueError |
| 16 | `is_safe_select` — INSERT / UPDATE / DELETE / DROP rejected |
| 17 | GROUP BY / HAVING / ORDER BY / LIMIT are stripped from count queries |
| 18 | RIGHT JOIN |
| 19 | CTE with no outer WHERE — error count must be None |

---

## 15. Troubleshooting

### "Python is not installed or not on PATH"
Install Python from https://python.org with "Add Python to PATH" checked.

### "Missing required environment variables"
Open `.env` and ensure all variables are populated:
```
SNOWFLAKE_ACCOUNT=xy12345.us-east-1
SNOWFLAKE_USER=myuser
...
```

### "Input Excel file not found"
Place the file at `input/input_queries.xlsx` or run:
```cmd
venv\Scripts\python create_sample_input.py
```

### "Required column 'query' not found"
The input Excel sheet must have a column header exactly named `query` (lowercase).

### Snowflake authentication failure
- Double-check `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD` in `.env`.
- Ensure the user has SELECT access on the target tables.
- Verify `SNOWFLAKE_WAREHOUSE` is not suspended.

### "SQL parsing failed"
The input SQL may use unsupported syntax.  Check `logs/application.log` for
the exact SQLGlot error.  That row will be marked `FAILED`; other rows will
still process.

### "UNION queries are not supported"
UNION queries cannot be automatically decomposed into a single outer WHERE.
Split the UNION branches into separate queries in the input Excel.

### Logs location
All detailed logs are written to: `logs/application.log`

---

## 16. Future SharePoint Integration

The application is deliberately layered so the Excel I/O can be replaced with
SharePoint without touching the SQL or Snowflake modules.

**Current architecture:**

```
excel_handler.read_queries()   →   Local Excel
excel_handler.write_results()  →   Local Excel
```

**Future architecture:**

```
sharepoint_handler.read_queries()   →   SharePoint List / Drive file
sharepoint_handler.write_results()  →   SharePoint Drive file
```

To add SharePoint support:

1. Create `src/sharepoint_handler.py`.
2. Implement the same two functions:
   ```python
   def read_queries(filepath: str) -> list[str]: ...
   def write_results(filepath: str, results: list[dict]) -> None: ...
   ```
3. In `src/main.py`, swap the import:
   ```python
   # from src.excel_handler import read_queries, write_results
   from src.sharepoint_handler import read_queries, write_results
   ```

No changes are needed in `sql_parser.py`, `snowflake_connector.py`, or
`query_processor.py`.
