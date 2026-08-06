"""
Application logging configuration.

Responsibilities:
- Create a consistent logger for the project.
- Write logs to both the terminal and a file.
- Keep timestamps and log levels.
- Avoid duplicate handlers when modules import the logger repeatedly.
"""

import logging
from pathlib import Path

from config import PROJECT_ROOT


LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "scanner.log"


def get_logger(
    name: str,
    level: int = logging.INFO,
) -> logging.Logger:
    """
    Return a configured project logger.

    Args:
        name:
            Usually __name__ from the calling module.

        level:
            Minimum logging level to record.

    Returns:
        Configured logging.Logger instance.
    """
    LOG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Prevent messages from being passed upward and printed twice.
    logger.propagate = False

    # If handlers already exist, this logger was configured earlier.
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        (
            "%(asctime)s | "
            "%(levelname)s | "
            "%(name)s | "
            "%(message)s"
        )
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(
        LOG_FILE,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
