"""
config.py — Loads and validates Snowflake connection settings from environment variables.

Credentials are never logged or exposed.
"""

import os
import logging
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load .env from the project root (one level above src/)
_ENV_PATH = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH, override=False)

_REQUIRED_VARS: list[str] = [
    "SNOWFLAKE_ACCOUNT",
    "SNOWFLAKE_USER",
    "SNOWFLAKE_PASSWORD",
    "SNOWFLAKE_WAREHOUSE",
    "SNOWFLAKE_DATABASE",
    "SNOWFLAKE_SCHEMA",
]


@dataclass(frozen=True)
class SnowflakeConfig:
    """Immutable Snowflake connection configuration."""

    account: str
    user: str
    password: str
    warehouse: str
    database: str
    schema: str
    role: str = ""


def load_snowflake_config() -> SnowflakeConfig:
    """
    Read Snowflake credentials from environment variables.

    Raises:
        EnvironmentError: If any required variable is missing or empty.

    Returns:
        Populated SnowflakeConfig dataclass.
    """
    missing: list[str] = [v for v in _REQUIRED_VARS if not os.getenv(v)]
    if missing:
        raise EnvironmentError(
            f"The following required environment variables are not set: "
            f"{', '.join(missing)}. "
            f"Please populate the .env file (see .env.example)."
        )

    config = SnowflakeConfig(
        account=os.environ["SNOWFLAKE_ACCOUNT"].strip(),
        user=os.environ["SNOWFLAKE_USER"].strip(),
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"].strip(),
        database=os.environ["SNOWFLAKE_DATABASE"].strip(),
        schema=os.environ["SNOWFLAKE_SCHEMA"].strip(),
        role=os.getenv("SNOWFLAKE_ROLE", "").strip(),
    )

    # Log non-sensitive fields only
    logger.debug(
        "Snowflake config loaded | account=%s | user=%s | warehouse=%s | "
        "database=%s | schema=%s | role=%s",
        config.account,
        config.user,
        config.warehouse,
        config.database,
        config.schema,
        config.role or "(default)",
    )
    return config
