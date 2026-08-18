# logging_utils.py
"""Structured logging for pipeline observability."""
import json, time, logging
from typing import Optional, Any
from dataclasses import dataclass, field, asdict
from contextlib import contextmanager

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

@dataclass
class StepMetrics:
    """Metrics for a single pipeline step execution."""
    step_key: str
    label: str = ""
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration: Optional[float] = None
    success: bool = True
    error: Optional[str] = None
    token_count: Optional[int] = None
    variant_count: int = 0
    warnings: list[str] = field(default_factory=list)

    def finish(self, success: bool = True, error: str = None):
        self.end_time = time.time()
        self.duration = round(self.end_time - self.start_time, 3)
        self.success = success
        self.error = error

    def to_dict(self) -> dict:
        return asdict(self)

@dataclass
class TurnMetrics:
    """Metrics for a complete turn pipeline execution."""
    chat_id: int
    turn_id: int
    turn_idx: int
    start_time: float = field(default_factory=time.time)
    steps: list[StepMetrics] = field(default_factory=list)
    total_duration: Optional[float] = None
    total_llm_calls: int = 0
    total_tokens: int = 0

    def add_step(self, step: StepMetrics):
        self.steps.append(step)

    def finish(self):
        self.total_duration = round(time.time() - self.start_time, 3)

    def summary(self) -> dict:
        return {
            "chat_id": self.chat_id,
            "turn_idx": self.turn_idx,
            "total_duration_s": self.total_duration,
            "total_llm_calls": self.total_llm_calls,
            "steps": [s.to_dict() for s in self.steps],
        }

@contextmanager
def measure_step(key: str, label: str, turn_metrics: Optional[TurnMetrics] = None):
    """Context manager that measures a step's duration and logs it."""
    metrics = StepMetrics(step_key=key, label=label)
    logger.info(f"step_start key={key} label={label}")
    try:
        yield metrics
        metrics.finish(success=True)
    except Exception as e:
        metrics.finish(success=False, error=str(e))
        logger.error(f"step_error key={key} error={e}")
        raise
    finally:
        if turn_metrics:
            turn_metrics.add_step(metrics)
        logger.info(
            f"step_done key={key} duration={metrics.duration}s "
            f"success={metrics.success}"
        )

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