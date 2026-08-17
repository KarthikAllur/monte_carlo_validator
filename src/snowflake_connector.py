"""
snowflake_connector.py — Reusable Snowflake connection wrapper.

Design choices
──────────────
* Uses the official ``snowflake-connector-python`` library (no SQLAlchemy,
  no Snowpark).
* Wraps the connection in a context manager so callers can use ``with``
  blocks and the connection is always closed cleanly.
* Passwords are NEVER logged.
* A single connection is opened once and reused across all queries in the
  batch (see query_processor.py).
"""

import logging
from typing import Any, Optional

import snowflake.connector
import snowflake.connector.errors as sf_errors

from src.config import SnowflakeConfig

logger = logging.getLogger(__name__)


class SnowflakeConnection:
    """
    Manages a single Snowflake connection for the lifetime of the batch run.

    Usage
    ─────
    ::

        with SnowflakeConnection(config) as conn:
            result = conn.execute_scalar("SELECT COUNT(*) FROM my_table")
    """

    def __init__(self, config: SnowflakeConfig) -> None:
        self._config = config
        self._conn: Optional[snowflake.connector.SnowflakeConnection] = None

    # ── Context manager ───────────────────────────────────────────────

    def __enter__(self) -> "SnowflakeConnection":
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        self.disconnect()
        return False  # Never suppress exceptions

    # ── Connection lifecycle ──────────────────────────────────────────

    def connect(self) -> None:
        """
        Open a Snowflake connection.

        Raises:
            sf_errors.DatabaseError: On authentication or network failure.
        """
        logger.info(
            "Opening Snowflake connection | account=%s | user=%s | warehouse=%s "
            "| database=%s | schema=%s",
            self._config.account,
            self._config.user,
            self._config.warehouse,
            self._config.database,
            self._config.schema,
        )
        try:
            connect_kwargs: dict = {
                "account": self._config.account,
                "user": self._config.user,
                "password": self._config.password,
                "warehouse": self._config.warehouse,
                "database": self._config.database,
                "schema": self._config.schema,
                # Limit client-side metadata network traffic
                "client_session_keep_alive": False,
            }
            if self._config.role:
                connect_kwargs["role"] = self._config.role

            self._conn = snowflake.connector.connect(**connect_kwargs)
            logger.info("Snowflake connection established successfully.")
        except sf_errors.DatabaseError as exc:
            # Log the error message but NOT the password
            logger.error(
                "Failed to connect to Snowflake (account=%s, user=%s): %s",
                self._config.account,
                self._config.user,
                exc,
            )
            raise

    def disconnect(self) -> None:
        """Close the Snowflake connection if it is open."""
        if self._conn:
            try:
                self._conn.close()
                logger.info("Snowflake connection closed.")
            except Exception as exc:  # pylint: disable=broad-except
                logger.warning("Error while closing Snowflake connection: %s", exc)
            finally:
                self._conn = None

    # ── Query execution ───────────────────────────────────────────────

    def execute_scalar(self, sql: str) -> Optional[Any]:
        """
        Execute *sql* and return the first column of the first result row.

        Designed for ``SELECT COUNT(*)`` queries which return a single value.

        Args:
            sql: A SELECT SQL string to execute.

        Returns:
            The scalar value from the first column of the first row, or
            ``None`` if the result set is empty.

        Raises:
            RuntimeError: If no connection is open.
            sf_errors.ProgrammingError: On query execution failure.
            sf_errors.DatabaseError: On general Snowflake errors.
        """
        if self._conn is None:
            raise RuntimeError(
                "SnowflakeConnection.execute_scalar() called with no active connection. "
                "Use the 'with' context manager or call connect() first."
            )

        cursor = None
        try:
            cursor = self._conn.cursor()
            logger.debug("Executing SQL:\n%s", sql)
            cursor.execute(sql)
            row = cursor.fetchone()
            value = row[0] if row else None
            logger.debug("Query returned scalar value: %s", value)
            return value
        except sf_errors.ProgrammingError as exc:
            logger.error(
                "Snowflake query execution error: %s\nSQL:\n%s", exc, sql
            )
            raise
        except sf_errors.DatabaseError as exc:
            logger.error(
                "Snowflake database error during query: %s\nSQL:\n%s", exc, sql
            )
            raise
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:  # pylint: disable=broad-except
                    pass
