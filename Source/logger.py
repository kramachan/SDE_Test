
"""
**************************************************************************************************
@File : logger.py
@Date
: 19/07/2026
@Version: 1.0
@Author: Ram
@Change History

Description: Central Logging Configuration
**************************************************************************************************
"""
import logging
import sys
from pathlib import Path
from datetime import datetime

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
# Project Root
PROJECT_ROOT = Path(__file__).resolve().parent.parent

LOG_FOLDER = PROJECT_ROOT / "logs"
LOG_FOLDER.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_FOLDER / f"etl_pipeline_{timestamp}.log"


def get_logger(name: str):

    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # File
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    logger.propagate = False

    return logger