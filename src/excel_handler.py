"""
excel_handler.py — Read input queries and write output results using pandas/openpyxl.

Designed so this module can be replaced with a SharePoint handler in the
future without changing sql_parser.py or snowflake_connector.py.

Interface contract
──────────────────
    read_queries(filepath: str) -> list[str]
    write_results(filepath: str, results: list[dict]) -> None

A future SharePointHandler module only needs to satisfy the same contract.
"""

import logging
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# ── Column names (single source of truth) ────────────────────────────────────

INPUT_QUERY_COLUMN: str = "query"

OUTPUT_COLUMNS: list[str] = [
    "query",
    "total_count_query",
    "error_count_query",
    "total_count",
    "error_count",
    "status",
    "error_message",
]

_SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".xlsx", ".xls"})


# ── Public API ────────────────────────────────────────────────────────────────

def read_queries(filepath: str) -> list[str]:
    """
    Read SQL queries from the input Excel file.

    Expects a column named ``query`` (case-sensitive).
    Blank rows and whitespace-only cells are silently skipped.

    Args:
        filepath: Path to the input ``.xlsx`` / ``.xls`` file.

    Returns:
        List of non-empty SQL strings.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file format is unsupported or the required
                    column is missing.
    """
    path = Path(filepath)

    if not path.exists():
        raise FileNotFoundError(
            f"Input Excel file not found: '{filepath}'. "
            "Please place your queries file at this location."
        )

    if path.suffix.lower() not in _SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file extension '{path.suffix}'. "
            f"Supported formats: {sorted(_SUPPORTED_EXTENSIONS)}"
        )

    logger.info("Reading input Excel file: %s", filepath)

    try:
        df = pd.read_excel(filepath, engine="openpyxl", dtype=str)
    except Exception as exc:
        raise ValueError(
            f"Failed to read Excel file '{filepath}': {exc}"
        ) from exc

    if INPUT_QUERY_COLUMN not in df.columns:
        raise ValueError(
            f"Required column '{INPUT_QUERY_COLUMN}' not found in '{filepath}'. "
            f"Columns present: {list(df.columns)}"
        )

    # Filter: drop NaN and whitespace-only entries
    raw_series = df[INPUT_QUERY_COLUMN].dropna().astype(str).str.strip()
    queries = [q for q in raw_series if q]

    logger.info("Loaded %d non-empty queries from '%s'.", len(queries), filepath)
    return queries


def write_results(filepath: str, results: list[dict[str, Any]]) -> None:
    """
    Write processing results to an output Excel file.

    Creates parent directories automatically.
    Does NOT overwrite the input file.

    Args:
        filepath: Destination ``.xlsx`` path.
        results:  List of result dicts (keys must include OUTPUT_COLUMNS).

    Raises:
        ValueError: If the file cannot be written.
    """
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(results, columns=OUTPUT_COLUMNS)

    logger.info("Writing %d result rows to '%s'.", len(df), filepath)

    try:
        with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Results")

            # Auto-fit column widths for readability
            worksheet = writer.sheets["Results"]
            for col_idx, col_name in enumerate(df.columns, start=1):
                max_len = max(
                    len(str(col_name)),
                    df[col_name].astype(str).str.len().max()
                    if not df[col_name].isna().all()
                    else 0,
                )
                # Cap column width at 80 characters so Excel stays readable
                worksheet.column_dimensions[
                    worksheet.cell(row=1, column=col_idx).column_letter
                ].width = min(max_len + 4, 80)

    except Exception as exc:
        raise ValueError(
            f"Failed to write output Excel file '{filepath}': {exc}"
        ) from exc

    logger.info("Results successfully written to '%s'.", filepath)
