"""
Application logging configuration.

Logs are written to logs/app.log and also displayed
in the development terminal.
"""

import logging
from pathlib import Path


LOG_DIRECTORY = Path("logs")
LOG_FILE = LOG_DIRECTORY / "app.log"


def get_logger(
    logger_name: str,
) -> logging.Logger:
    """Create or return an application logger."""

    LOG_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    logger = logging.getLogger(logger_name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | "
        "%(name)s | %(message)s"
    )

    file_handler = logging.FileHandler(
        LOG_FILE,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger