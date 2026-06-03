"""Logging konsisten untuk pipeline PET (Cloud Run Job atau eksekusi kontainer)."""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone


class _UtcFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc).astimezone()
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%d %H:%M:%S")


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    root = logging.getLogger()
    if root.handlers:
        root.setLevel(level)
        return logging.getLogger("pet_pipeline")

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        _UtcFormatter(fmt="[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    )
    root.handlers = [handler]
    root.setLevel(level)
    return logging.getLogger("pet_pipeline")


def get_logger(name: str = "pet_pipeline") -> logging.Logger:
    return logging.getLogger(name)
