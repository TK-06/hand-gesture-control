"""Logging for the command-line programs: console, plus an optional rotating log file
(the Pi runs headless in the car, so the log file is how you see what happened)."""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def setup_logging(level: str = "INFO", log_file: str | None = None, max_bytes: int = 1_000_000, backups: int = 5) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.handlers.RotatingFileHandler(path, maxBytes=max_bytes, backupCount=backups, encoding="utf-8"))
    logging.basicConfig(level=level.upper(), format=FORMAT, handlers=handlers, force=True)
