"""
main.py — Entry point for the Monte Carlo SQL Validator.

Run from the project root:
    python src/main.py

Or via:
    run.bat
"""

import logging
import sys
from pathlib import Path

# ── Ensure project root is on sys.path so ``src.*`` imports resolve ───────────
# This is needed when running ``python src/main.py`` from the project root.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.logger import setup_logging
from src.config import load_snowflake_config
from src.excel_handler import read_queries, write_results
from src.snowflake_connector import SnowflakeConnection
from src.query_processor import process_all_queries

# ── File paths (relative to project root) ────────────────────────────────────
INPUT_FILE: str = "input/input_queries.xlsx"
OUTPUT_FILE: str = "output/output_results.xlsx"


def main() -> None:
    """Application entry point."""
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("Monte Carlo SQL Validator — Application Start")
    logger.info("=" * 60)
    logger.info("Input  : %s", INPUT_FILE)
    logger.info("Output : %s", OUTPUT_FILE)

    # ── 1. Load Snowflake configuration ───────────────────────────────
    try:
        config = load_snowflake_config()
    except EnvironmentError as exc:
        logger.error("Configuration error: %s", exc)
        logger.error(
            "Please copy .env.example to .env and populate all required variables."
        )
        sys.exit(1)

    # ── 2. Read queries from input Excel ──────────────────────────────
    try:
        queries = read_queries(INPUT_FILE)
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        sys.exit(1)
    except ValueError as exc:
        logger.error("Input Excel error: %s", exc)
        sys.exit(1)

    if not queries:
        logger.warning(
            "No queries found in '%s'. Nothing to process. Exiting.", INPUT_FILE
        )
        sys.exit(0)

    logger.info("%d queries loaded for processing.", len(queries))

    # ── 3. Connect to Snowflake, run all queries, disconnect ──────────
    try:
        with SnowflakeConnection(config) as conn:
            results = process_all_queries(queries, conn)
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Fatal error during Snowflake processing: %s", exc)
        sys.exit(1)

    # ── 4. Write results to output Excel ──────────────────────────────
    try:
        write_results(OUTPUT_FILE, results)
    except ValueError as exc:
        logger.error("Output Excel error: %s", exc)
        sys.exit(1)

    # ── 5. Summary ────────────────────────────────────────────────────
    successful = sum(1 for r in results if r["status"] == "SUCCESS")
    failed = len(results) - successful

    logger.info("=" * 60)
    logger.info("Application completed successfully.")
    logger.info("  Queries processed : %d", len(results))
    logger.info("  SUCCESS           : %d", successful)
    logger.info("  FAILED            : %d", failed)
    logger.info("  Output file       : %s", OUTPUT_FILE)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
