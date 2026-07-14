"""
Project configuration for the Real-Time Market Intelligence Scanner.

This module:
1. Finds the project root directory.
2. Loads environment variables from the .env file.
3. Defines commonly used file paths.
4. Provides a helper for validating required secrets.
"""

import os
from pathlib import Path

from dotenv import load_dotenv


# __file__ is the location of this config.py file.
# resolve() converts it into an absolute path.
#
# Example:
# /Users/amber/projects/real-time-market-intelligence-scanner/src/config.py
CONFIG_FILE_PATH = Path(__file__).resolve()


# config.py is inside src/, so:
# .parent gives us src/
# .parent.parent gives us the project root
#
# Project root example:
# /Users/amber/projects/real-time-market-intelligence-scanner
PROJECT_ROOT = CONFIG_FILE_PATH.parent.parent


# Build paths relative to the project root.
#
# Using pathlib is safer and more portable than manually writing
# strings such as "/Users/amber/project/data".
ENV_FILE = PROJECT_ROOT / ".env"
DATA_DIR = PROJECT_ROOT / "src" / "data"
DATABASE_PATH = DATA_DIR / "paper_trades.db"
MARKET_MAP_PATH = DATA_DIR / "market_map.csv"


# Read key-value pairs from the local .env file.
#
# Example .env contents:
# ODDS_API_KEY=abc123
#
# load_dotenv() places those values into the process environment
# so os.getenv() can retrieve them.
load_dotenv(ENV_FILE)


# Read API credentials from environment variables.
ODDS_API_KEY = os.getenv("ODDS_API_KEY")
KALSHI_API_KEY = os.getenv("KALSHI_API_KEY")
KALSHI_API_SECRET = os.getenv("KALSHI_API_SECRET")


def require_environment_variable(
    variable_name: str,
    variable_value: str | None,
) -> str:
    """
    Validate that a required environment variable exists.

    Args:
        variable_name:
            The name of the environment variable, such as
            "ODDS_API_KEY".

        variable_value:
            The value returned by os.getenv().

    Returns:
        The validated string value.

    Raises:
        RuntimeError:
            If the variable is missing or empty.

    Why this is useful:
        Without validation, the program might make an API request
        using a missing key and fail with a confusing error.

        This helper gives us a clear error immediately.
    """
    if not variable_value:
        raise RuntimeError(
            f"Missing required environment variable: {variable_name}. "
            f"Add it to the local file: {ENV_FILE}"
        )

    return variable_value
