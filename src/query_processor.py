"""
query_processor.py — Orchestrates SQL parsing, query generation, and Snowflake execution.

One failed query row never stops the batch; the error is captured and the
next row is processed immediately.
"""

import logging
from typing import Any, Optional

from src.sql_parser import generate_count_queries, is_safe_select
from src.snowflake_connector import SnowflakeConnection

logger = logging.getLogger(__name__)

# Sentinel displayed in output when no error-count query exists
NO_WHERE_SENTINEL: str = "N/A — no outer WHERE clause"


def process_query(
    original_sql: str,
    snowflake_conn: SnowflakeConnection,
) -> dict[str, Any]:
    """
    Process a single Monte Carlo SQL query end-to-end.

    Steps
    ─────
    1. Parse SQL with SQLGlot and generate count queries.
    2. Safety-validate the generated SQL (must be SELECT).
    3. Execute the total-count query in Snowflake.
    4. Execute the error-count query in Snowflake (when it exists).
    5. Return a result dict compatible with excel_handler.OUTPUT_COLUMNS.

    Args:
        original_sql:   The raw query read from the input Excel.
        snowflake_conn: An active SnowflakeConnection instance.

    Returns:
        Result dict with keys: query, total_count_query, error_count_query,
        total_count, error_count, status, error_message.
    """
    result: dict[str, Any] = {
        "query": original_sql,
        "total_count_query": None,
        "error_count_query": None,
        "total_count": None,
        "error_count": None,
        "status": "FAILED",
        "error_message": None,
    }

    # ── Step 1: SQL parsing ───────────────────────────────────────────
    logger.info("Parsing SQL: %.120s%s", original_sql, " …" if len(original_sql) > 120 else "")

    try:
        total_count_sql, error_count_sql = generate_count_queries(original_sql)
    except ValueError as exc:
        logger.warning("SQL parsing failed: %s", exc)
        result["error_message"] = f"SQL parsing failed: {exc}"
        return result

    result["total_count_query"] = total_count_sql
    result["error_count_query"] = error_count_sql or NO_WHERE_SENTINEL
    logger.info("Count queries generated successfully.")
    logger.debug("  total_count_query:\n%s", total_count_sql)
    logger.debug("  error_count_query:\n%s", error_count_sql)

    # ── Step 2: Safety validation ─────────────────────────────────────
    if not is_safe_select(total_count_sql):
        msg = "Generated total_count_query failed safety check (not a SELECT)."
        logger.error(msg)
        result["error_message"] = msg
        return result

    if error_count_sql and not is_safe_select(error_count_sql):
        msg = "Generated error_count_query failed safety check (not a SELECT)."
        logger.error(msg)
        result["error_message"] = msg
        return result

    # ── Step 3: Execute total count ───────────────────────────────────
    try:
        total_count: Optional[Any] = snowflake_conn.execute_scalar(total_count_sql)
        result["total_count"] = total_count
        logger.info("total_count = %s", total_count)
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("total_count_query execution failed: %s", exc)
        result["error_message"] = f"total_count_query execution failed: {exc}"
        return result

    # ── Step 4: Execute error count (when WHERE clause exists) ────────
    if error_count_sql:
        try:
            error_count: Optional[Any] = snowflake_conn.execute_scalar(error_count_sql)
            result["error_count"] = error_count
            logger.info("error_count = %s", error_count)
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("error_count_query execution failed: %s", exc)
            result["error_message"] = f"error_count_query execution failed: {exc}"
            return result
    else:
        # No outer WHERE — error count is intentionally undefined
        result["error_count"] = None
        logger.info("No outer WHERE clause — error_count set to None.")

    result["status"] = "SUCCESS"
    return result


def process_all_queries(
    queries: list[str],
    snowflake_conn: SnowflakeConnection,
) -> list[dict[str, Any]]:
    """
    Iterate over every query, process it, and collect results.

    A single failure does NOT abort the batch.

    Args:
        queries:        List of raw SQL strings from the input Excel.
        snowflake_conn: An active SnowflakeConnection instance.

    Returns:
        List of result dicts (one per query, in the original order).
    """
    total = len(queries)
    logger.info("Starting batch processing of %d queries.", total)

    results: list[dict[str, Any]] = []

    for idx, sql in enumerate(queries, start=1):
        logger.info("─" * 60)
        logger.info("Query %d / %d", idx, total)
        result = process_query(sql, snowflake_conn)
        results.append(result)
        logger.info("Status: %s", result["status"])
        if result["error_message"]:
            logger.warning("Error detail: %s", result["error_message"])

    successful = sum(1 for r in results if r["status"] == "SUCCESS")
    failed = total - successful
    logger.info("=" * 60)
    logger.info(
        "Batch complete. Total: %d | Success: %d | Failed: %d",
        total,
        successful,
        failed,
    )
    return results
