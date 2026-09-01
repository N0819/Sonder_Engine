# logging_utils.py
"""Structured logging for pipeline observability."""
import logging
import logging.handlers
import os

logger = logging.getLogger("fiction_engine")

#: Where the level comes from, in order: SONDER_LOG_LEVEL, then the `log_level`
#: setting, then INFO. The env wins because the level is fixed at import --
#: before a database is necessarily configured -- and because raising it to
#: debug a startup problem must not require a working database to do it.
DEFAULT_LOG_LEVEL = "INFO"

#: Rotation, named rather than buried because together they are the ceiling on
#: how much history a log can hold: 10MB x 5 files is ~50MB, which at the
#: observed rate of one INFO line per provider call is many thousands of turns
#: -- and at DEBUG is far fewer, which is the point of it being a knob.
LOG_FILE_MAX_BYTES = 10 * 1024 * 1024
LOG_FILE_BACKUPS = 5

_FORMAT = ('{"ts": "%(asctime)s", "level": "%(levelname)s", '
           '"msg": "%(message)s"}')


def _configured_level() -> int:
    name = str(os.environ.get("SONDER_LOG_LEVEL") or "").strip().upper()
    if not name:
        try:
            from core.db import get_setting
            name = str(get_setting("log_level", "") or "").strip().upper()
        except Exception:
            # Called at import, when a database may not be configured yet.
            name = ""
    return getattr(logging, name or DEFAULT_LOG_LEVEL,
                   getattr(logging, DEFAULT_LOG_LEVEL))


def _log_file_path() -> str:
    path = str(os.environ.get("SONDER_LOG_FILE") or "").strip()
    if path:
        return path
    try:
        from core.db import get_setting
        return str(get_setting("log_file", "") or "").strip()
    except Exception:
        return ""


def configure_logging(level=None, log_file=None) -> None:
    """(Re)apply the level and the optional rotating file handler.

    Callable at runtime so changing the setting takes effect without a
    restart, which is the whole complaint the stderr-only default produced: an
    engine you must restart to make talkative has already lost the turn you
    wanted to look at.
    """
    logger.setLevel(level if level is not None else _configured_level())
    if not any(isinstance(h, logging.StreamHandler)
               and not isinstance(h, logging.FileHandler)
               for h in logger.handlers):
        stream = logging.StreamHandler()
        stream.setFormatter(logging.Formatter(_FORMAT))
        logger.addHandler(stream)

    path = log_file if log_file is not None else _log_file_path()
    existing = [h for h in logger.handlers
                if isinstance(h, logging.handlers.RotatingFileHandler)]
    if not path:
        for handler in existing:
            logger.removeHandler(handler)
            handler.close()
        return
    if any(getattr(h, "baseFilename", None) == os.path.abspath(path)
           for h in existing):
        return
    for handler in existing:
        logger.removeHandler(handler)
        handler.close()
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".",
                    exist_ok=True)
        rotating = logging.handlers.RotatingFileHandler(
            path, maxBytes=LOG_FILE_MAX_BYTES,
            backupCount=LOG_FILE_BACKUPS, encoding="utf-8")
        rotating.setFormatter(logging.Formatter(_FORMAT))
        logger.addHandler(rotating)
    except Exception:
        # A log that cannot open its file must not stop the engine starting.
        pass


configure_logging()

def log_llm_call(
    role: str,
    model: str,
    system_tokens: int = 0,
    user_tokens: int = 0,
    response_tokens: int = 0,
    cached_tokens: int = 0,
    cache_write_tokens: int = 0,
    duration: float = 0,
    success: bool = True,
    error: str = "",
):
    """Log an LLM API call with metrics.

    cached_tokens (prefix served from cache) and cache_write_tokens (prefix
    written to cache) are logged separately: writes with no later reads is the
    signature of a prefix that isn't stable across calls, which reads as
    "caching is on" but costs more than not caching at all.
    """
    logger.info(
        f"llm_call role={role} model={model} "
        f"system_tokens={system_tokens} user_tokens={user_tokens} "
        f"response_tokens={response_tokens} cached_tokens={cached_tokens} "
        f"cache_write_tokens={cache_write_tokens} "
        f"duration={duration:.2f}s "
        f"success={success}"
        + (f" error={error}" if error else "")
    )