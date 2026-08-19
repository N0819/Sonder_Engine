# logging_utils.py
"""Structured logging for pipeline observability."""
import logging

logger = logging.getLogger("fiction_engine")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            '{"ts": "%(asctime)s", "level": "%(levelname)s", '
            '"msg": "%(message)s"}'
        )
    )
    logger.addHandler(handler)

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