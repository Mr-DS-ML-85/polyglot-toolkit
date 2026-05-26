"""
Logging system with file rotation, console output, and in-GUI log handler.
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional, Callable


class GUILogHandler(logging.Handler):
    """Logging handler that forwards records to a callback (for GUI live feed)."""

    def __init__(self, callback: Callable[[str, str], None]):
        super().__init__()
        self.callback = callback

    def emit(self, record):
        try:
            msg = self.format(record)
            self.callback(record.levelname, msg)
        except Exception:
            pass


def setup_logging(
    log_file: str = "logs/polyglot_shield.log",
    level: str = "INFO",
    max_bytes: int = 10_000_000,
    backup_count: int = 5,
    gui_callback: Optional[Callable] = None,
) -> logging.Logger:
    """
    Configure root logger with:
      - RotatingFileHandler (persistent log)
      - StreamHandler (console)
      - Optional GUILogHandler (live feed to GUI)
    """
    root = logging.getLogger("polyglot_shield")
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers.clear()

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)-18s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # File handler with rotation
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    fh = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    fh.setFormatter(fmt)
    root.addHandler(fh)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    # GUI handler (optional)
    if gui_callback:
        gh = GUILogHandler(gui_callback)
        gh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s",
                                          datefmt="%H:%M:%S"))
        root.addHandler(gh)

    root.info("PolyglotShield logging initialized")
    return root
