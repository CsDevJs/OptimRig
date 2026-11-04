"""Activity log: one line per account action, with the user's email.

Lines go to `activity.log` in AUDIT_LOG_DIR (default backend/logs). A
RotatingFileHandler keeps the file small: when it reaches AUDIT_LOG_MAX_BYTES it
is renamed to activity.log.1 (older ones shift to .2, .3, ...) and a new file is
started; past AUDIT_LOG_BACKUP_COUNT the oldest is deleted.

Line format:
    2026-11-04 14:03:12 | LOGIN_FAILED | email=ana@exemplu.com | reason=wrong password
Passwords and tokens are never written.
"""

import logging
import threading
from logging.handlers import RotatingFileHandler

_LOGGER_NAME = "pc_configurator.audit"
_setup_lock = threading.Lock()


def _logger() -> logging.Logger:
    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:
        return logger
    with _setup_lock:
        if not logger.handlers:
            from app.config import settings
            settings.audit_log_dir.mkdir(parents=True, exist_ok=True)
            handler = RotatingFileHandler(
                settings.audit_log_dir / "activity.log", maxBytes=settings.audit_log_max_bytes,
                backupCount=settings.audit_log_backup_count, encoding="utf-8",
            )
            handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s", "%Y-%m-%d %H:%M:%S"))
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            logger.propagate = False  # only in the activity log, not the server console
    return logger


def _clean(value: object) -> str:
    # One action per line: a newline typed into a field can't fake a second entry.
    return str(value).replace("\r", " ").replace("\n", " ").replace("|", "/")


def log_action(action: str, email: str | None, **details: object) -> None:
    """Write one line, e.g. log_action("BUILD_SAVED", "ana@x.com", build_id=3, name="Gaming")."""
    parts = [action, f"email={_clean(email) if email else '-'}"]
    parts += [f"{key}={_clean(value)}" for key, value in details.items()]
    _logger().info(" | ".join(parts))
