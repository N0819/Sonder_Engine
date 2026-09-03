# providers.py
"""LLM providers, streaming, retries, cancellation, and embeddings."""

import json, zlib, asyncio, threading, time, re, os, random
import numpy as np
import httpx
import requests.exceptions as _req_exc

# Network-level exceptions that mean "transient, retry" regardless of which
# HTTP client raised them. The sync pipeline path runs on `requests`, so its
# ConnectionError/Timeout/ChunkedEncodingError (a mid-stream drop) must be
# treated the same as httpx.NetworkError -- otherwise a single Wi-Fi hiccup
# kills the whole turn instead of retrying (observed live: a ChunkedEncoding
# drop and a RemoteDisconnected each aborted a turn).
_RETRYABLE_NETWORK = (
    httpx.TimeoutException, httpx.NetworkError,
    _req_exc.ConnectionError, _req_exc.Timeout, _req_exc.ChunkedEncodingError,
)

# Public alias for callers OUTSIDE the retry loop that must tell "the network
# dropped" apart from "the model answered badly" -- resumable lorebook-tree
# generation uses it to decide whether a stopped run is a mere interruption
# (stop and offer resume) or unusable output (record it and carry on).
TRANSIENT_NETWORK_ERRORS = _RETRYABLE_NETWORK
import contextvars
from contextlib import contextmanager
from typing import Optional, Callable, Any
from dataclasses import dataclass

from core.db import q, get_setting, set_setting
from core.logging_utils import logger as _logger
from language_runtime import apply_common_prompt_policy

token_sink = contextvars.ContextVar("token_sink", default=None)
generation_event_sink = contextvars.ContextVar(
    "generation_event_sink",
    default=None,
)
cancel_event = contextvars.ContextVar("cancel_event", default=None)

# Where one finished provider call's ledger entry should land: a callable
# taking one dict ({role, requested, served, in, out, cached, duration,
# kind}), or None outside a pipeline step. `agents.runtime.compute_step`
# points it at the running PipelineContext (the same funnel that sets
# `current_step_key`), which stamps the step and keeps the entries for
# `_with_engine_notes` to persist on the step's saved variant.
#
# This exists because per-call timing used to live only in stderr
# (`_log_usage` -> log_llm_call) and died with the process: three separate
# slow-stage investigations on 2026-08-11/12 each started from a wrong guess
# ("it was embeddings", "it was corpus size", "the server is stale") because
# the only durable record of a turn was stage-total timestamps. A ContextVar
# for the same reason `last_reasoning` is one: the pipeline fans out across
# thread pools with contextvars.copy_context(), and a plain global would
# file one stage's calls under another.
call_ledger_sink = contextvars.ContextVar("call_ledger_sink", default=None)

# The last reasoning block a thinking model returned, per context. For such a
# model this is the actual decision trace -- the structured output is only its
# conclusion -- and it was being dropped at the response boundary, so the one
# artifact that explains WHY a beat came out as it did never left this module.
# It is diagnostic only: nothing downstream may treat it as content, because a
# reasoning trace is a model talking to itself and has not been through any of
# the checks the answer has.
#
# A ContextVar rather than a global: perception fans out across a thread pool
# with contextvars.copy_context(), so a plain global would hand one observer's
# reasoning to another.
last_reasoning = contextvars.ContextVar("last_reasoning", default=None)

# WHY the model stopped, per context. Every provider says so on the response --
# OpenAI-compatible `finish_reason`, Anthropic `stop_reason` -- and this module
# used to drop all of it at the response boundary, which made a recoverable
# failure indistinguishable from an unrecoverable one.
#
# It matters because "the model ran out of output budget" and "the model wrote
# nonsense" arrive downstream as the same thing: a JSON parse error. The first
# is a LENGTH problem and one more call with more room fixes it; the second is
# a content problem and more room changes nothing. Two beats of a 14-beat
# real-model playthrough died on a cut-off object (`Expecting ',' delimiter at
# position 5042`), and the repair ladder that was supposed to save them re-asked
# the same model for the same object on the same budget.
#
# A ContextVar for the same reason `last_reasoning` is one: the pipeline fans
# out across a thread pool with contextvars.copy_context(), and a plain global
# would report one stage's truncation against another's response.
last_finish_reason = contextvars.ContextVar(
    "last_finish_reason",
    default=None,
)

# Every spelling of "I hit the output ceiling" seen across the dialects:
# OpenAI/aggregators `length`, Anthropic `max_tokens`, and the variants some
# OpenRouter upstreams pass through in `native_finish_reason`.
_LENGTH_STOPS = frozenset({
    "length",
    "max_tokens",
    "max_output_tokens",
    "model_length",
    "max_length",
})


def _capture_finish_reason(value):
    """Stash why the last completion stopped, under whichever key it arrived by.

    Called with None at the start of every completion: a stale `length` left
    standing from an earlier call on this thread would report the NEXT
    response as truncated, and a false truncation spends a whole escalated
    retry on an output that was merely wrong.
    """
    try:
        text = str(value or "").strip().lower()
        last_finish_reason.set(text or None)
    except Exception:
        pass


def response_truncated():
    """Did the last completion on this context stop because it ran out of room?

    Authoritative where it answers True -- the provider is stating it. False
    covers both "stopped normally" and "the provider said nothing", so a
    caller must not read False as proof the response is whole; the JSON's own
    shape is the second witness (llm_quality.output_ran_out_of_room).
    """
    return (last_finish_reason.get() or "") in _LENGTH_STOPS


def _capture_choice_finish(parsed):
    """The finish reason off an OpenAI-compatible response body."""
    choice = (parsed.get("choices") or [{}])[0] if isinstance(parsed, dict) else {}
    if not isinstance(choice, dict):
        return
    # OpenRouter reports its own normalized `finish_reason` and the upstream's
    # verbatim `native_finish_reason`; either one saying length is length.
    for key in ("finish_reason", "native_finish_reason"):
        value = choice.get(key)
        if value:
            _capture_finish_reason(value)
            if response_truncated():
                return


def _capture_reasoning(message):
    """Stash a thinking model's trace, under whichever key it arrived by."""
    if not isinstance(message, dict):
        return
    text = ""
    for key in ("reasoning", "reasoning_content", "thinking"):
        value = message.get(key)
        if isinstance(value, str) and value.strip():
            text = value
            break
        # OpenRouter can return reasoning as a list of blocks.
        if isinstance(value, list):
            parts = [
                str(b.get("text") or b.get("thinking") or "")
                for b in value if isinstance(b, dict)
            ]
            if any(parts):
                text = "\n".join(p for p in parts if p)
                break
    try:
        last_reasoning.set(text or None)
    except Exception:
        pass

# (connect, read). THE READ HALF IS INTER-CHUNK, NOT TOTAL: every request the
# pipeline makes is streamed, so this clock resets on each chunk and does not
# limit how long a legitimate generation may run. What it limits is how long a
# provider may say NOTHING -- before the first byte, or between two of them.
#
# It was 300s, which is not a timeout so much as an afternoon. With
# `RetryConfig.max_retries` at 3 (four attempts), a provider that accepted the
# connection and then went silent cost 20 minutes per `chat_complete`, and
# `complete_validated_json` makes several in a row -- its primary call, a
# repair, a token-ceiling retry -- so a single dead connection could hold a
# turn for the better part of an hour. Measured against a real rate limit for
# contrast: a 429 answers at once, so that path is four attempts and about 4
# seconds of jittered backoff, and was never the hang.
#
# 90s is chosen against time-to-first-byte, which is the only legitimate long
# silence: the largest system prompt this engine ships is ~38k characters and
# first tokens arrive in seconds. A stream silent for a minute and a half is
# not slow, it is gone. Owner's number (2026-08-29); raise it per-call with
# `request_timeout(...)` where a role genuinely needs longer.
REQUEST_TIMEOUT = (30, 90)

# Independent pipeline stages (mapping+perception_act, narrator+
# narrator_extra, narrator_extra's own per-persona loop) now run
# concurrently on separate threads, each making several sequential HTTPS
# calls to the same remote host. Without connection reuse, every single
# call pays a fresh DNS+TCP+TLS handshake. requests.Session is not safe to
# share across threads under concurrent use, so this hands each thread its
# own session (created lazily, kept for the thread's lifetime) rather than
# one global session -- reuse within a thread's own sequential calls,
# no cross-thread contention.
_thread_local = threading.local()

def _session():
    s = getattr(_thread_local, "session", None)
    if s is None:
        import requests
        s = requests.Session()
        _thread_local.session = s
    return s
HTTPX_TIMEOUT = httpx.Timeout(
    connect=30.0,
    # The async path's twin of REQUEST_TIMEOUT's read half; see the note there.
    read=90.0,
    write=60.0,
    pool=30.0,
)

# Read timeout for model requests made inside a `request_timeout(...)` block;
# None means "use the 300s default above". The default is sized for pipeline
# turns, which must not hang a player mid-scene -- but a long authoring call
# (a lorebook-tree structure pass, or a batch of entries on a slow local
# model) can legitimately still be producing tokens at 300s, and severing it
# there fails a response that was on its way. Callers that know they are doing
# long work raise it for themselves rather than everyone paying for it.
read_timeout_override = contextvars.ContextVar(
    "read_timeout_override",
    default=None,
)

# 30s floor stops a typo (or a 0) from making every request fail instantly;
# the hour ceiling stops one from wedging a worker thread indefinitely.
READ_TIMEOUT_MIN = 30.0
READ_TIMEOUT_MAX = 3600.0


def clamp_read_timeout(seconds):
    """The usable read timeout for `seconds`, or None if it means 'default'."""
    try:
        value = float(seconds or 0)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return max(READ_TIMEOUT_MIN, min(value, READ_TIMEOUT_MAX))


@contextmanager
def request_timeout(seconds):
    """Raise the read timeout for model requests made inside this block.

    Falsy/unparseable values are a no-op, so callers can pass an unvalidated
    setting straight through. Reset in `finally` for the same reason
    token_sink/cancel_event are: a contextvar left set would leak the override
    into whatever ran next on this thread.
    """
    value = clamp_read_timeout(seconds)
    if value is None:
        yield
        return

    token = read_timeout_override.set(value)
    try:
        yield
    finally:
        read_timeout_override.reset(token)


# What a blocking read is allowed to wait. REQUEST_TIMEOUT's 90s is reasoned
# entirely about time-to-first-byte -- "a stream silent for a minute and a
# half is not slow, it is gone" -- which is true of a STREAM and false of a
# blocking POST, where silence until the response completes is normal. Applied
# there it cut healthy generations at 90s, and RetryConfig's three attempts
# turned one cut into 3*90s plus jittered backoff: the ~245-253s failures this
# engine kept attributing to nanogpt, then to openrouter, on grok, qwen,
# deepseek, gemma and gemini alike. Same number every time, because it was
# never a provider.
#
# Reasoning models are what made it visible: on a stream their thinking
# arrives on its own delta key (see _sse_openai) and keeps the socket busy, so
# the 90s never fires. Without a stream nothing arrives until the whole answer
# is done, and a model that thinks for two minutes looks exactly like a dead
# connection.
BLOCKING_READ_TIMEOUT = 300.0


def _request_timeout(streaming=True):
    """(connect, read) for `requests`, honoring an active override.

    `streaming=False` asks for the deadline a whole generation may take rather
    than the one a silent stream may take. An explicit override still wins on
    either transport -- a caller that knows it is doing long work has said so.
    """
    override = read_timeout_override.get()
    if override is not None:
        return (REQUEST_TIMEOUT[0], override)
    if not streaming:
        return (REQUEST_TIMEOUT[0], BLOCKING_READ_TIMEOUT)
    return REQUEST_TIMEOUT


def _httpx_timeout():
    """The httpx equivalent, so the async path honors the same override."""
    override = read_timeout_override.get()
    if override is None:
        return HTTPX_TIMEOUT
    return httpx.Timeout(connect=30.0, read=override, write=60.0, pool=30.0)

class Aborted(RuntimeError):
    pass

class LLMError(RuntimeError):
    def __init__(self, message: str, status_code: int = 0, retryable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


class ReasoningBudgetExhausted(LLMError):
    """The model returned private reasoning but never emitted an answer.

    This is distinct from malformed content: there is no candidate answer to
    validate or repair.  Keeping the failure typed lets the retry boundary
    change only the setting that caused it, without scraping a reasoning trace
    into user-visible content or weakening successful thinking-model calls.
    """

    def __init__(self, message: str):
        super().__init__(message, status_code=0, retryable=True)
        
class DegenerateOutput(LLMError):
    def __init__(self, reason: str):
        super().__init__(
            f"Degenerate model output: {reason}",
            status_code=0,
            retryable=True,
        )
        self.reason = reason

#: Shortest phrase worth calling a phrase. Below this the 2-16 rule above has
#: it covered, at a much higher repeat count, which is the right trade at that
#: length -- "ha ha ha" is prose and "ha" x 80 is not.
_LOOP_MIN_PERIOD = 24
#: A short phrase must repeat three times; a long one twice. Two consecutive
#: identical sentences is something a writer does -- a stammer, a refrain, a
#: character insisting -- so a short cycle has to prove itself. Two identical
#: blocks of a few hundred characters is not a stylistic choice.
_LOOP_LONG_PERIOD = 240
#: The window the loop check reads. Larger than the 4KB the other rules use,
#: because detecting a cycle of length p needs at least two full copies of it,
#: and the cycles that actually occur are long: the three seen in play were
#: 100, 142 and 1,237 characters.
_LOOP_WINDOW = 16000
#: How much of the tail is used to FIND the cycle. Long enough that an
#: accidental match is unlikely, short enough to sit inside any real cycle.
_LOOP_NEEDLE = 96


def _repeating_period(tail: str) -> int:
    """The length of a phrase repeating back-to-back at the END of `tail`, or 0.

    Found by SEARCH rather than by scanning candidate lengths. The first
    version swept periods from 24 to 700 and compared slices, which meant the
    longest cycle it could see was a number chosen in advance -- and the very
    next loop reported from play had a period of 1,237, so it sailed straight
    through. Raising the bound would only move where the next one hides.

    Instead: take the last `_LOOP_NEEDLE` characters, ask where they last
    occurred before that, and the distance between the two IS the period. One
    `str.rfind` over the window, and it finds a cycle of any length up to half
    of it. Periodic text always matches at exactly one cycle back, so a short
    needle spanning several cycles still lands on the true period rather than a
    multiple of it.

    Anchored at the end on purpose. A loop is a thing that has STARTED and is
    still going, so the evidence is always the most recent output -- and
    reading only the tail means legitimate repetition earlier in a long passage
    can never accumulate into a false positive.
    """
    if len(tail) < _LOOP_NEEDLE * 2:
        return 0
    needle = tail[-_LOOP_NEEDLE:]
    # `end` bounds where a match must FINISH, not where it may start. Passing
    # `len(tail) - _LOOP_NEEDLE` therefore demanded the whole needle fit before
    # the final copy, which for a cycle shorter than the needle skips the
    # nearest recurrence and lands on a MULTIPLE of the period -- 100 instead
    # of 50 on a five-times-repeated sentence, which then failed its own
    # three-repeat check and reported no loop at all. `len(tail) - 1` excludes
    # only the final occurrence, which is the one thing that must be excluded.
    previous = tail.rfind(needle, 0, len(tail) - 1)
    if previous < 0:
        return 0
    period = len(tail) - _LOOP_NEEDLE - previous
    if period < _LOOP_MIN_PERIOD:
        return 0
    repeats = 2 if period >= _LOOP_LONG_PERIOD else 3
    if len(tail) < period * repeats:
        return 0
    block = tail[-period:]
    # The needle only proposes a period; these confirm it. Each comparison is
    # one memcmp, and the first that fails rejects the candidate outright.
    if all(tail[-period * (n + 1):-period * n or None] == block
           for n in range(1, repeats)):
        return period
    return 0


_GUARD_CHECK_STRIDE = 200

class OutputGuard:
    """High-confidence detector for runaway or corrupted model output."""

    def __init__(self):
        self.text = ""
        self._checked_len = 0

    def feed(self, delta: str):
        self.text += str(delta or "")

        if len(self.text) < 160:
            return

        # Streaming feeds this a few characters at a time, but the checks
        # below always re-scan a 4KB tail window regardless of how much
        # actually changed -- running the full battery (3 regexes plus a
        # per-character control-count loop) on every single delta rescans
        # nearly the same window hundreds of times over one response for
        # no detection benefit, since degenerate output doesn't appear
        # between one 3-character delta and the next. Only re-check once
        # at least _GUARD_CHECK_STRIDE new characters have accumulated;
        # a single large feed() (e.g. a non-streamed call, or a test
        # feeding a whole string at once) always exceeds the stride
        # immediately, so this only throttles genuine incremental
        # streaming, not detection on any individual check.
        if len(self.text) - self._checked_len < _GUARD_CHECK_STRIDE:
            return
        self._checked_len = len(self.text)

        tail = self.text[-4000:]

        if re.search(r"[ \t]{800,}", tail):
            raise DegenerateOutput(
                "excessive uninterrupted whitespace"
            )

        if re.search(r"(.)\1{350,}", tail, re.S):
            raise DegenerateOutput(
                "single-character repetition"
            )

        if re.search(r"(.{2,16})\1{80,}", tail, re.S):
            raise DegenerateOutput(
                "repeating output fragment"
            )

        # The SAME failure at sentence scale, which the rule above cannot see:
        # its longest unit is 16 characters. Measured live, a character step
        # locked onto a 100-character cycle -- "I apologize for the shock. Are
        # you able to understand me? The restraints are a standard precaution."
        # -- and rode it for three and a half minutes toward the 40,000-token
        # ceiling, because every rule here was looking for something shorter.
        #
        # Checked by periodicity rather than by regex: `(.{17,600})\1{2,}`
        # against a 4KB tail is a backtracking hazard on exactly the input
        # this runs on. Slice comparison is a C-level memcmp per candidate
        # period, so the whole sweep is a few hundred of those.
        # Its own window: the other rules look at 4KB, and two copies of a
        # 1,237-character cycle do not fit in that.
        period = _repeating_period(self.text[-_LOOP_WINDOW:])
        if period:
            raise DegenerateOutput(
                f"repeating {period}-character phrase"
            )

        controls = sum(
            1
            for char in tail
            if ord(char) < 32
            and char not in "\n\r\t"
        )

        if controls > max(16, int(len(tail) * 0.03)):
            raise DegenerateOutput(
                "excessive control characters"
            )

def _guarded_sink(sink):
    guard = OutputGuard()

    def guarded(delta):
        guard.feed(delta)
        sink(delta)

    return guarded

def generation_notice(event: dict):
    """Tell the live turn view that this step is being generated again.

    Public rather than private because the reasons a step gets regenerated are
    not all inside this module: `llm_quality` re-asks for a response that came
    back truncated, and a retry nobody can see is the failure mode this repo
    keeps rediscovering. `agents/runtime` tags the event with the step key on
    its way to the browser, so no caller has to know which step it is in.
    """
    sink = generation_event_sink.get()

    if sink:
        sink(event)

@dataclass
class EmbeddingBatch:
    vectors: list[np.ndarray]
    model_key: str
    dimensions: int
    fallback: bool = False
    error: str = ""

def _check_cancel():
    ev = cancel_event.get()
    if ev is not None and ev.is_set():
        raise Aborted("generation aborted by user")


# LIVE RESPONSES, SO AN ABORT CAN REACH A BLOCKED READ.
#
# `_check_cancel` is polled between streamed chunks, which is the right place
# and is enough for every case where chunks keep arriving. It is no help at
# all for the one the user actually hits: a connection that has stopped
# sending. `iter_lines` is then blocked inside a socket read, no chunk
# arrives, the poll never runs, and the flag the abort sets is invisible until
# `REQUEST_TIMEOUT`'s read deadline expires -- 300 seconds. A turn cancelled
# in the first second still holds the pipeline for five minutes, which is why
# killing the server is faster than waiting.
#
# So the abort closes the socket. A response registered here is closed by
# `abort_live_requests` from whichever thread called it, and the blocked read
# raises immediately, surfacing as the `Aborted` the poll would have raised.
# Keyed by the cancel Event itself -- identity, one per pipeline run -- so a
# concurrent chat's requests are untouched.
_LIVE_REQUESTS = {}
_LIVE_LOCK = threading.Lock()


@contextmanager
def _abortable(response):
    """Register a streaming response for the life of the read."""
    ev = cancel_event.get()
    if ev is None:
        yield response
        return
    with _LIVE_LOCK:
        _LIVE_REQUESTS.setdefault(ev, set()).add(response)
    # Set between registration and the first read: closing it now is what an
    # abort that landed a moment ago would have done.
    if ev.is_set():
        with _LIVE_LOCK:
            _LIVE_REQUESTS.get(ev, set()).discard(response)
        _close_quietly(response)
        raise Aborted("generation aborted by user")
    try:
        yield response
    finally:
        with _LIVE_LOCK:
            live = _LIVE_REQUESTS.get(ev)
            if live is not None:
                live.discard(response)
                if not live:
                    _LIVE_REQUESTS.pop(ev, None)


def _close_quietly(response):
    for method in ("close", "aclose"):
        closer = getattr(response, method, None)
        if closer is None:
            continue
        try:
            result = closer()
        except Exception:
            return
        # An async close returns a coroutine this thread must not await; the
        # httpx paths carry their own cancellation through the event loop.
        if hasattr(result, "close"):
            try:
                result.close()
            except Exception:
                pass
        return



def _post_abortable(url, **kw):
    """A blocking POST an abort can actually interrupt.

    `_abortable` reached only the two streaming readers, so every plain post
    below was invisible to `abort_live_requests`: the thread parks in a socket
    read, no chunk arrives, `_check_cancel` never runs, and the flag stays
    unseen until the read deadline. That is the identical failure the comment
    above describes and the streaming path fixed -- the non-streaming leg kept
    it, which is why an abort lands instantly on some stages and hangs for
    minutes on others.

    `stream=True` only defers the BODY: headers and status arrive as before,
    and the read that blocks now happens inside the guard, where closing the
    socket raises where it stands. The body is materialised here so every
    existing caller keeps using `.json()`, `.text` and `.content` unchanged.
    """
    kw.setdefault("timeout", _request_timeout(streaming=False))
    # No pipeline to abort -- background jobs, tooling, tests. Behave exactly
    # as the plain post did, including the response object the caller gets, so
    # this helper adds a capability and changes no existing contract.
    if cancel_event.get() is None:
        return _session().post(url, **kw)
    response = _session().post(url, stream=True, **kw)
    with _abortable(response):
        # Materialise inside the guard: this is the read that blocks, and
        # closing the socket from the aborting thread raises it where it
        # stands. `getattr` because a caller's stand-in response need not
        # implement the streaming half of requests' surface.
        getattr(response, "content", None)
    return response

def abort_live_requests(ev) -> int:
    """Close every in-flight response belonging to this cancel event.

    Returns how many were closed, so a caller can report whether the abort had
    anything to interrupt. Total: a close that raises must not stop the rest,
    because the point of calling this is that something is already wrong.
    """
    if ev is None:
        return 0
    with _LIVE_LOCK:
        live = list(_LIVE_REQUESTS.get(ev) or ())
    for response in live:
        _close_quietly(response)
    return len(live)

DEFAULT_BASES = {
    "openai": "https://api.openai.com/v1",
    "nanogpt": "https://nano-gpt.com/api/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "together": "https://api.together.xyz/v1",
    "groq": "https://api.groq.com/openai/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "mistral": "https://api.mistral.ai/v1",
    "xai": "https://api.x.ai/v1",
    "anthropic": "https://api.anthropic.com",
    "ollama": "http://localhost:11434/v1",
    "koboldcpp": "http://localhost:5001/v1",
    "lmstudio": "http://localhost:1234/v1",
    "llamacpp": "http://localhost:8080/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    "generic": "",
}

DEFAULT_SAMPLERS = {
    "temperature": 0.8,
    "top_p": 1.0,
    "top_k": 0,
    "frequency_penalty": 0.0,
    "presence_penalty": 0.0,
    "repetition_penalty": 1.0,
    "min_p": 0.0,
    "top_a": 0.0,
}

_NOOP = {
    "top_k": 0,
    "min_p": 0.0,
    "top_a": 0.0,
    "repetition_penalty": 1.0,
    "frequency_penalty": 0.0,
    "presence_penalty": 0.0,
    "top_p": 1.0,
}

SAMPLER_KEYS = (
    "temperature",
    "top_p",
    "top_k",
    "frequency_penalty",
    "presence_penalty",
    "repetition_penalty",
    "min_p",
    "top_a",
)

ANTHROPIC_SAMPLERS = ("temperature", "top_p", "top_k")

# The per-role `system` prompt is the large, stable prefix repeated
# byte-for-byte on every call for that role (it comes from get_prompt(role),
# which is deterministic per preset; only the `user` payload varies). Marking
# it with Anthropic's ephemeral cache_control lets repeated calls read that
# prefix from cache (~90% cheaper, ~5-minute TTL) instead of reprocessing it.
# GA feature under anthropic-version 2023-06-01 -- no beta header needed. The
# env kill-switch is a safety valve for anyone pointing kind="anthropic" at a
# stricter proxy that rejects the structured system-block form.
PROMPT_CACHE_ENABLED = os.environ.get("FICTION_ENGINE_PROMPT_CACHE", "1") != "0"

def _anthropic_system(system, prov=None):
    """The `system` field for an Anthropic request: a cache-marked content
    block when caching is on and there is a prompt to cache, else the plain
    string (Anthropic accepts either form).

    `prov` is consulted so that `prompt_cache_deny` means the same thing on the
    native path as on the aggregator one. Without it the host-facing switch
    lied for exactly the provider whose caching is least in doubt: a direct
    kind="anthropic" connection ignored the deny list entirely, so turning
    caching off in the UI changed nothing and the only real off switch was an
    env var needing a restart."""
    if PROMPT_CACHE_ENABLED and system and not _cache_denied(prov):
        return [{"type": "text", "text": system,
                 "cache_control": {"type": "ephemeral"}}]
    return system

# An Anthropic model reached through an OpenAI-compatible aggregator still
# needs an explicit cache breakpoint -- the caching is Anthropic's, not the
# aggregator's, so the plain-string system message every other provider takes
# produces no breakpoint and nothing ever caches. An aggregator passes a
# content-part array's cache_control through to Anthropic verbatim, so the
# marked form is how a Claude-via-aggregator caller gets the same ~90%
# cached-prefix discount as a direct kind="anthropic" caller.
#
# This stays an ALLOWLIST rather than becoming allow-by-default. Reshaping the
# system message into a content-part array is only safe where the aggregator is
# known to forward an unrecognized `cache_control` key rather than reject it,
# and a rejected request fails the turn -- a worse outcome than an uncached one.
#
# What WAS wrong is that the list was hardcoded to ("openrouter",), so the same
# Claude model reached through nanogpt -- the provider this engine is actually
# configured with -- silently reprocessed its whole system prompt on every call,
# with no way to fix it short of editing this file. The list is now extensible
# from settings, so a provider that supports caching can be opted in without a
# code change, and one that turns out to be strict can be opted back out.
_CACHE_PASSTHROUGH_KINDS = ("openrouter", "nanogpt")


def _setting_name_set(key):
    """A comma-separated setting as a set of casefolded provider names/kinds."""
    try:
        raw = get_setting(key) or ""
    except Exception:
        return frozenset()
    return frozenset(part.strip().casefold()
                     for part in str(raw).split(",") if part.strip())


def cache_tokens(prov):
    """The two strings that name a provider in `prompt_cache_allow`/`_deny`:
    its own name and its kind, casefolded. A name is per-connection; a kind
    covers every connection of that kind, including ones not created yet."""
    return (str(_prov_field(prov, "name") or "").strip().casefold(),
            str(_prov_field(prov, "kind") or "").strip().casefold())


def _cache_denied(prov):
    """`prompt_cache_deny` names this provider, by name or by kind.

    Checked by BOTH caching paths -- native Anthropic and aggregator
    passthrough -- so the host has one switch rather than one per code path."""
    if prov is None:
        return False
    name, kind = cache_tokens(prov)
    return bool({kind, name} & _setting_name_set("prompt_cache_deny"))


def _cache_passthrough_allowed(prov):
    """Whether this provider may receive a cache-marked system message.

    `prompt_cache_allow` opts additional providers in by name or kind;
    `prompt_cache_deny` opts any provider back out and wins over both the
    allowlist and the built-in kinds. FICTION_ENGINE_PROMPT_CACHE=0 remains the
    all-providers kill switch.
    """
    if _cache_denied(prov):
        return False
    name, kind = cache_tokens(prov)
    if kind in _CACHE_PASSTHROUGH_KINDS:
        return True
    return bool({kind, name} & _setting_name_set("prompt_cache_allow"))


def prompt_cache_enabled_for(prov):
    """Whether prompt caching is actually in effect for this provider -- the
    single question the settings UI asks, answered by the same code the request
    path uses rather than by the UI re-deriving the rule and drifting from it.

    kind="anthropic" caches natively (no message reshaping involved), so it is
    on by default and only the deny list can turn it off. Everything else goes
    through the passthrough allowlist."""
    if not PROMPT_CACHE_ENABLED:
        return False
    if str(_prov_field(prov, "kind") or "").strip().casefold() == "anthropic":
        return not _cache_denied(prov)
    return _cache_passthrough_allowed(prov)


def prompt_cache_supported_for(prov):
    """Whether caching is on by default for this provider's kind. A provider
    outside this set can still be opted in, but the UI says so rather than
    presenting an unticked box that looks like a plain off."""
    kind = str(_prov_field(prov, "kind") or "").strip().casefold()
    return kind == "anthropic" or kind in _CACHE_PASSTHROUGH_KINDS


# ---- Cache routing affinity (the hint that makes implicit caching land) ----
#
# Fireworks-class hosts cache prompt prefixes automatically -- but ONLY within
# one replica ("prompt caching only works within 1 replica", their prompt-
# caching guide), and serverless routes requests across replicas unless the
# client hints where to send them, via the standard OpenAI `user` field or an
# `x-session-affinity` header. Without a hint, whether this engine's ~15,000-
# token static role prompt is served from cache on any given call is routing
# luck. The `user` body field is used because it is part of the OpenAI request
# schema (so compatible hosts and aggregators tolerate it) and it survives
# aggregation, where a bespoke header may be stripped.
#
# THE VALUE MUST CARRY NO CONTENT AND NO IDENTITY. It is sent to a third
# party on every call, so it is exactly the kind of field that quietly
# becomes a leak: never a character name, persona name, chat title, player
# input, or anything derived from them. `sonder:<role>` is built from engine
# constants only ("character_major", "narrator"...) -- do not "improve" it
# into something descriptive.
#
# Role-only, deliberately, rather than chat+role:
# - the sharing unit that matters here is the per-character prefix (the
#   character system prompt is name-substituted 32 characters in, so
#   cross-character sharing is nil either way), and one replica caches MANY
#   prefixes -- pinning a role's whole traffic to one replica keeps every
#   character's and every chat's prefix warm in one place;
# - a single-host engine's per-role traffic is far below one replica's
#   capacity (measured 1.01-1.11 character calls/turn; simultaneous same-role
#   calls are the rare wave), so the coarse key costs no real parallelism;
# - the role is already in scope at this layer, while a chat id would need
#   plumbing through every caller -- including generator/importer callers
#   that have no chat at all;
# - the retry paths inherit it for free: the decision-review retry and the
#   repair ladder call with the same role, so a second call lands on the
#   replica that already holds the first call's prefix.
#
# FAIL CLOSED PER PROVIDER, same idiom as `prompt_cache_allow`: some
# OpenAI-compatible hosts reject bodies with fields they do not expect, and a
# host that 400s because we added a performance hint is a regression, not a
# trade. `cache_affinity_allow` opts providers in by name or kind; unset
# means no field is added anywhere and every request is byte-identical to
# before.
def cache_affinity_allowed(prov):
    """`cache_affinity_allow` names this provider, by name or by kind."""
    if prov is None:
        return False
    name, kind = cache_tokens(prov)
    return bool({kind, name} & _setting_name_set("cache_affinity_allow"))


def _apply_cache_affinity(body, prov, role):
    """Attach the stable routing hint for providers opted into it."""
    if role and cache_affinity_allowed(prov):
        body["user"] = f"sonder:{role}"
    return body


def _prov_field(prov, key, default=None):
    """Read a provider field from either a sqlite3.Row (what provider() returns)
    or a plain dict (tests, synthetic callers). Row supports subscripting but
    NOT .get(), and raises IndexError rather than KeyError on a missing key --
    calling .get() on one is an AttributeError at request time, which surfaces
    as an opaque "all providers failed" turn error."""
    try:
        value = prov[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if value is None else value


def _model_is_anthropic(model):
    m = str(model or "").lower()
    return m.startswith("anthropic/") or "claude" in m


def _openai_system_message(system, prov, model):
    """The system message for an OpenAI-compatible request. Anthropic models on
    a cache-passthrough aggregator get the cache-marked content-part form;
    everyone else gets the plain string they expect."""
    if (PROMPT_CACHE_ENABLED and system
            and _model_is_anthropic(model)
            and _cache_passthrough_allowed(prov)):
        return {"role": "system",
                "content": [{"type": "text", "text": system,
                             "cache_control": {"type": "ephemeral"}}]}
    return {"role": "system", "content": system}

# OpenRouter provider routing. One OpenRouter model id is served by several
# upstream providers (Anthropic direct, Amazon Bedrock, Azure, Google Vertex,
# and third-party hosts), and they are not interchangeable: output quality
# varies between them, and -- the part that isn't a preference -- so does the
# prompt-retention policy. Without this, routing is OpenRouter's choice on
# every call, so a privacy-sensitive caller has no way to keep a prompt away
# from a provider that retains it.
#
# Sent as the `provider` field on the request body (OpenRouter reads it and
# every other backend ignores an unknown field, but it is only attached for
# kind="openrouter" so nothing else has to tolerate it).
_ROUTING_LIST_KEYS = ("order", "only", "ignore")
_ROUTING_SORTS = ("price", "throughput", "latency")


def _clean_slugs(value):
    """A provider-slug list from arbitrary stored input: strings only, trimmed,
    de-duplicated, order preserved (order is meaningful for `order`)."""
    if isinstance(value, str):
        value = re.split(r"[,\s]+", value)
    if not isinstance(value, (list, tuple)):
        return []
    out = []
    for item in value:
        slug = str(item or "").strip()
        if slug and slug not in out:
            out.append(slug)
    return out


def normalize_openrouter_routing(raw):
    """A valid OpenRouter `provider` block from stored settings, or {} when
    nothing is configured. Unknown keys are dropped rather than forwarded --
    this rides on every request, so it must never be able to make one invalid.
    """
    if isinstance(raw, str):
        try:
            raw = json.loads(raw or "{}")
        except Exception:
            return {}
    if not isinstance(raw, dict):
        return {}
    out = {}
    for key in _ROUTING_LIST_KEYS:
        slugs = _clean_slugs(raw.get(key))
        if slugs:
            out[key] = slugs
    # "deny" restricts routing to providers that do not train on / retain
    # prompts. Only ever sent when explicitly chosen -- "allow" is OpenRouter's
    # own default, so sending it would just be noise.
    if str(raw.get("data_collection") or "").lower() == "deny":
        out["data_collection"] = "deny"
    sort = str(raw.get("sort") or "").lower()
    if sort in _ROUTING_SORTS:
        out["sort"] = sort
    if raw.get("allow_fallbacks") is False:
        # Pinning without this still silently falls back to another provider,
        # which defeats the point of pinning one.
        out["allow_fallbacks"] = False
    return out


def openrouter_routing():
    """The configured routing block. Read per call so a settings change applies
    on the next turn without a restart."""
    try:
        stored = get_setting("openrouter_routing")
    except Exception:
        return {}
    return normalize_openrouter_routing(stored)


def _apply_provider_routing(body, prov, routing=None):
    """Attach the routing block for OpenRouter requests only."""
    if _prov_field(prov, "kind") != "openrouter":
        return body
    routing = openrouter_routing() if routing is None else routing
    if routing:
        body["provider"] = routing
    return body

# Output-token ceiling. Four stages used to request 200000 output tokens, which
# no model can produce -- but which providers still act on: OpenRouter reserves
# credit against the requested maximum and rejects a model outright when
# input + max_tokens exceeds its context window, so an unreachable ceiling
# silently locked callers out of models and required a balance to match. Every
# request is clamped here rather than at the call sites, so no single stage can
# reintroduce the problem.
#
# 20000 suits every stage in the pipeline: the longest single output the engine
# produces is a narrator turn (prose plus a small JSON envelope), which runs
# well under this. Raise it only for a model with a genuinely larger usable
# output window AND a reason to fill it -- the ceiling costs nothing when
# unused, but a value above the model's own output cap is what re-creates the
# lockout. Lower it to hard-cap spend per call.
MAX_OUTPUT_TOKENS_DEFAULT = 20000
MAX_OUTPUT_TOKENS_MIN = 1024
MAX_OUTPUT_TOKENS_MAX = 128000


def _coerce_max_output_tokens(value, fallback=MAX_OUTPUT_TOKENS_DEFAULT):
    """A usable ceiling from arbitrary input (a settings row, an env var, a
    request body). Out-of-range values are pulled into range rather than
    rejected -- this gates every LLM call, so it must always yield a number."""
    try:
        n = int(float(value))
    except (TypeError, ValueError):
        return fallback
    return max(MAX_OUTPUT_TOKENS_MIN, min(n, MAX_OUTPUT_TOKENS_MAX))


def max_output_tokens():
    """The configured ceiling. Read per call rather than cached at import so a
    change in the settings UI takes effect on the next turn without a restart
    -- the DB read is trivial next to the HTTP request it precedes.

    Precedence: the saved setting, then the env override (which is what a
    headless/CI run has), then the default."""
    env = os.environ.get("FICTION_ENGINE_MAX_OUTPUT_TOKENS")
    fallback = (_coerce_max_output_tokens(env) if env
                else MAX_OUTPUT_TOKENS_DEFAULT)
    try:
        stored = get_setting("max_output_tokens")
    except Exception:
        # No configured DB yet (import-time callers, some tests) -- the env
        # value or the default still has to work.
        return fallback
    if stored in (None, ""):
        return fallback
    return _coerce_max_output_tokens(stored, fallback)


# Reasoning effort for models that expose it (OpenAI o-series `reasoning_effort`;
# OpenRouter's `reasoning: {effort}`; GLM / DeepSeek thinking variants via the
# same OpenAI-compatible field on aggregators that pass it through). A single
# global setting applied to every role -- "" / "default" means send nothing and
# let the model decide, exactly as before this existed. A provider that does not
# understand the field ignores an unknown key, so it is safe to send.
# "off" explicitly disables reasoning; minimal/low/medium/high set the level;
# "" (unset) sends nothing and lets the model decide.
REASONING_EFFORTS = ("off", "minimal", "low", "medium", "high")


def _coerce_reasoning_effort(value):
    """A valid effort level, or "" for 'unset / model default'. Anything
    unrecognized degrades to "" rather than erroring -- this rides on requests."""
    v = str(value or "").strip().lower()
    if v in ("", "default", "auto", "unset", "inherit"):
        return ""
    return v if v in REASONING_EFFORTS else ""


def reasoning_efforts():
    """The per-role reasoning-effort map, {role: level}. Read per call so a
    settings change applies on the next turn without a restart."""
    try:
        raw = get_setting("reasoning_effort")
    except Exception:
        return {}
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        # Legacy single-string value from the first (global) version: treat it
        # as the default-role level so an old setting keeps working.
        lvl = _coerce_reasoning_effort(raw)
        return {"default": lvl} if lvl else {}
    if not isinstance(data, dict):
        return {}
    out = {}
    for role, level in data.items():
        lvl = _coerce_reasoning_effort(level)
        if lvl:
            out[str(role)] = lvl
    return out


def reasoning_effort_for(role):
    """The effort level for one role: its own entry, else the 'default' role's,
    else the env override, else "" (unset).

    This does NOT consult ROLE_FALLBACKS -- it goes straight to `default`,
    which matches agent-model resolution only while that map is empty. It is
    empty now, so a blank row's model, samplers and effort all come from the
    same place. Add an entry there and they stop agreeing: the model would
    follow the parent while the effort still followed `default`, which is a
    thinking model running at a non-thinking role's level. Whoever adds one
    resolves that here too."""
    efforts = reasoning_efforts()
    if role in efforts:
        return efforts[role]
    if "default" in efforts:
        return efforts["default"]
    return _coerce_reasoning_effort(
        os.environ.get("FICTION_ENGINE_REASONING_EFFORT"))


def _apply_reasoning_effort(body, prov, role, effort_override=None):
    """Attach this role's reasoning effort to an OpenAI-compatible request.
    OpenRouter takes `reasoning: {effort}` (and `{enabled: false}` to disable);
    every other OpenAI-style backend takes the flat `reasoning_effort` ('none'
    to disable). Nothing is added when the role is unset."""
    effort = (effort_override if effort_override is not None
              else reasoning_effort_for(role))
    if not effort:
        return body
    is_openrouter = _prov_field(prov, "kind") == "openrouter"
    if effort == "off":
        if is_openrouter:
            body["reasoning"] = {"enabled": False}
        else:
            body["reasoning_effort"] = "none"
        return body
    if is_openrouter:
        body["reasoning"] = {"effort": effort}
    else:
        body["reasoning_effort"] = effort
    return body


def _scale_for_language(max_tokens):
    """Widen an output budget by the story language's own cost factor.

    Every `max_tokens` in this codebase was chosen against English. Japanese
    spends roughly twice as many tokens to say the same thing, so an
    English-tuned cap truncates it -- and a truncated response is not a
    shorter answer, it is invalid JSON and a generation reported as failed.
    Measured: character generation returned exactly 5000 tokens against a
    5000 cap and 502'd.

    Applied HERE rather than at 42 call sites, so a new language gets the
    right budget everywhere by declaring one number in its manifest. The
    host's configured ceiling still clamps the result.
    """
    if not max_tokens:
        return max_tokens
    try:
        from language_runtime import output_token_scale
        scale = float(output_token_scale())
    except Exception:
        return max_tokens
    if scale <= 1.0:
        return max_tokens
    return int(max_tokens * scale)


def _clamp_max_tokens(max_tokens, ceiling=None):
    """Cap a requested output budget at the configured ceiling. Only ever
    lowers -- a caller asking for less (a 1000-token utility call) keeps its
    own smaller budget.

    `ceiling` is the one documented way past that, and it only ever RAISES: it
    is what a caller recovering from a length-truncated response passes so the
    retry can ask for the room the first call did not have. Without it the
    clamp made the recovery impossible to express -- the configured ceiling is
    exactly the wall the response hit, so re-requesting it re-hits it. Still
    hard-capped at MAX_OUTPUT_TOKENS_MAX, because the reason the clamp exists
    (an unreachable ceiling locks callers out of models entirely) does not stop
    applying during a retry.
    """
    ceiling_value = max_output_tokens()
    try:
        raised = int(ceiling)
    except (TypeError, ValueError):
        raised = 0
    if raised > ceiling_value:
        ceiling_value = min(raised, MAX_OUTPUT_TOKENS_MAX)
    try:
        requested = int(max_tokens)
    except (TypeError, ValueError):
        return ceiling_value
    return max(1, min(requested, ceiling_value))


# A FIXED addition, not a multiplier, because the shortfall is fixed. A
# reasoning model bills its thinking as output (maze arm A11: 11-13k tokens of
# deliberation, then nothing left for the answer), and what got squeezed out is
# the answer -- which by the note above is never more than one stage's worth.
# So one stage's worth is exactly what a retry needs, whatever the ceiling was.
#
# Doubling would be the obvious rule and is the wrong one: it scales the retry
# with the setting rather than with the miss, so a host who has already raised
# the ceiling to 40000 gets an 80000-token request, and an unreachable
# max_tokens is precisely what the ceiling above exists to prevent -- providers
# reject a model outright when input + max_tokens exceeds its context window.
_ESCALATION_HEADROOM = MAX_OUTPUT_TOKENS_DEFAULT


def escalated_max_tokens(requested):
    """The budget for ONE retry after a length-truncated response, or 0.

    0 means "no headroom left" -- the failed call was already at the absolute
    cap -- and the caller must then stop rather than retry at the same size,
    which is the loop this function exists to avoid.

    The configured ceiling is only overshot by a call that was already sitting
    on it. A 1000-token utility call that truncates escalates up to the host's
    ceiling and stops there: it asked for less deliberately, and "lower it to
    hard-cap spend per call" has to keep meaning that.
    """
    current = _clamp_max_tokens(requested)
    configured = max_output_tokens()
    cap = MAX_OUTPUT_TOKENS_MAX if current >= configured else configured
    raised = min(current + _ESCALATION_HEADROOM, cap)
    return raised if raised > current else 0

ROLES = [
    "default",
    "director",
    # NO "perception". Perception is deterministic -- every view is composed
    # from the typed IR in `agents/composer.py` and `agents/perception.py`
    # imports no model seam at all -- so a model chosen for that role would
    # never be called. Neither the prompt nor the schema survives: replay
    # reads STORED VARIANTS, not prompt text, and it resolves the real step
    # keys (`perception_act`, `perception_outcome`, `perception_establish`),
    # none of which were ever in `SCHEMA_MAP`. A `perception` step has never
    # existed in the corpus. Keeping either cost 28,467 characters of prompt
    # in every language pack, an uneditable entry in the host's prompt editor,
    # and two validation branches that read as firewall protection and could
    # not fire.
    # A settings row is a different thing again, and offering one sells a host
    # a choice that does nothing and a cost they will not pay.
    "character_bg",
    "character_mid",
    "character_major",
    # The orchestrated Director's specialists (design note 19). Scoped
    # structural tasks that may not need a frontier model; when no model is
    # configured for one it follows `default` like every other role, and
    # either way its calls stay separable in _log_usage under its own role
    # name.
    "director_body",
    "director_social",
    "director_contact",
    "director_objects",
    "director_spatial",
    "director_offscreen",
    "narrator",
    # NO "mapping". Lore routing and retrieval is `agents/mapping.
    # compile_world_context`, deterministic since 2026-09-04: the two model
    # stages it replaced staged rooms and lore a plan had not drawn, and
    # the filing of what a beat established is a structured write from the
    # Director's committed diff (persist/commit_mapping). A model chosen for
    # this role would never be called, so no row is offered for it.
    # SHAPE, never content. When a stage's output fails validation, this
    # model is asked about the failed FIELDS ALONE and its answer is spliced
    # back at exactly the paths the validator named -- everything else is
    # byte-identical by construction, so it cannot touch the beat. That
    # constraint is what makes the job small: fix the shape, keep every
    # fact. A fast cheap model is the right choice here, and it saves the
    # rung below, which re-authors the whole response on the stage's own
    # model (measured: 4.2s on the Director for one malformed field, 36.3s
    # on a character decision review). Unset, it follows `default` -- so a
    # host who wants the cheap patcher has to say so, on this row.
    "repair",
    "utility",
    "embeddings",
    # Writes an image prompt from spatial data (backdrops.py). OPTIONAL and
    # deliberately out of band: it never runs inside the turn pipeline, so a
    # slow or failed image prompt cannot delay or break a beat. When no model
    # is configured for it, backdrops fall back to a deterministic template.
    "backdrop_prompt",
    # Writes a sound-library search query from spatial data (ambience.py).
    # OPTIONAL and out of band on the same terms as backdrop_prompt: with no
    # model configured, ambience falls back to a deterministic keyword query.
    "ambience_prompt",
    # NO extension lanes, though they exist: an enabled extension may declare
    # its own lane (`api.add_model_lane`), and the role it gets is namespaced
    # `ext:<extension-id>:<name>` -- never appended here, because this list is
    # the HOST's fixed vocabulary, read all over the engine, and a ROLES an
    # install could grow would also be one it could shadow or shrink. A lane
    # needs no entry to work: `resolve_role_candidates` looks its role string
    # up in `agent_models`, so a configured lane resolves its own row, a blank
    # one inherits `default` exactly as a blank host row does, and `_log_usage`
    # attributes the spend to the lane's own role string. The settings panel
    # learns the live lanes from the bootstrap's `extension_lanes`
    # (`extension_runtime.registered_model_lanes`), which empties with the
    # extension's registration -- so a disabled or removed extension leaves no
    # phantom row here or there, while the host's stored configuration for it
    # survives (`extension_runtime.keep_orphan_lane_rows`).
]

# Image generation is a different API surface from chat completion, so it gets
# its own setting rather than an entry in agent_models: {provider, model}.
# nano-gpt exposes 201 image models at /api/models/image and an
# OpenAI-compatible endpoint at /v1/images/generations; its /v1/models list
# contains no image-output models at all, which is why this cannot simply
# reuse the chat role plumbing.
IMAGE_ENDPOINT = "/images/generations"
# The image-to-image half of the same OpenAI-compatible surface: a multipart
# POST carrying an existing image for the model to work FROM. Not every
# provider implements it, so every caller must be able to fall back to plain
# generation -- see backdrops.generate_backdrop.
IMAGE_EDIT_ENDPOINT = "/images/edits"


def image_model():
    """The configured image model as {provider, model}, or None."""
    try:
        raw = get_setting("image_model")
    except Exception:
        return None
    if not raw:
        return None
    try:
        cfg = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if not isinstance(cfg, dict) or not cfg.get("provider") or not cfg.get("model"):
        return None
    return cfg


# A chat backdrop fills a browser viewport behind a centred text column, so the
# default is LANDSCAPE. A square would be cropped hard top and bottom on any
# normal window, throwing away most of what was paid for and usually the
# horizon with it. Overridable per install via the image_model setting's
# `size`, since supported sizes vary by model.
DEFAULT_IMAGE_SIZE = "1536x1024"   # 3:2


# The listing lives one path segment ABOVE the OpenAI-compatible base: the
# stored base_url is https://nano-gpt.com/api/v1 (where generation happens) but
# the catalogue is at https://nano-gpt.com/api/models/image. Appending to the
# base, the way list_models() does, would 404.
IMAGE_MODELS_PATH = "/models/image"


def image_models_url(base):
    base = (base or "").rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3].rstrip("/")
    return base + IMAGE_MODELS_PATH


# The catalogue arrives NESTED, and one level of unwrapping is not enough:
# nano-gpt answers {"models": {"image": {"<model id>": {...}}}, "meta": {...}}.
# Stopping at "models" yields a single entry called "image" -- a picker with
# one nonsense row in it, which is exactly what shipped first.
_IMAGE_LIST_WRAPPERS = ("data", "models", "image_models", "image")


def _image_entries(payload):
    """Normalise a provider's image catalogue into an iterable of (id, meta).

    Tolerant on purpose: this is one vendor-specific endpoint with no shared
    spec behind it, so it may come back as a list of strings, a list of
    objects, {"data": [...]}, or an id-keyed map nested a couple of levels
    down. Unwrapping is bounded and stops as soon as the dict stops looking
    like an envelope -- real model ids ("fal-ai/boogu-image") never collide
    with the wrapper names.
    """
    for _ in range(len(_IMAGE_LIST_WRAPPERS)):
        if not isinstance(payload, dict):
            break
        for key in _IMAGE_LIST_WRAPPERS:
            inner = payload.get(key)
            if isinstance(inner, (list, dict)):
                payload = inner
                break
        else:
            break
    if isinstance(payload, dict):
        return [(str(k), v if isinstance(v, dict) else {})
                for k, v in payload.items()]
    out = []
    for entry in (payload or []):
        if isinstance(entry, dict):
            mid = entry.get("id") or entry.get("model") or entry.get("name")
            if mid:
                out.append((str(mid), entry))
        elif entry:
            out.append((str(entry), {}))
    return out


def _image_model_entry(mid, meta):
    """One catalogue row: {id, badge, included, ctx, sizes}.

    `sizes` matters more than it looks. Half these models do not take a
    WxH string at all -- they take named resolutions ("square_hd",
    "landscape_16_9") -- so a picker that offers no sizes is a picker that
    lets you save a model which then fails at generation time.
    """
    subscription = meta.get("subscription")
    if isinstance(subscription, dict):
        included = bool(subscription.get("included"))
    else:
        included = bool(subscription)
    prices = [v for v in (meta.get("cost") or {}).values()
              if isinstance(v, (int, float))] if isinstance(meta.get("cost"), dict) else []
    if included:
        badge = "included in subscription"
    elif prices:
        # %g, not a fixed 3 decimals: these prices run from $0.003 to $0.25,
        # and %.3f rounds $0.0075 down to "$0.007" -- quoting a price lower
        # than the one charged.
        badge = "from $%.4g" % min(prices)
    else:
        badge = "image"
    sizes = [str(r.get("value")) for r in (meta.get("resolutions") or [])
             if isinstance(r, dict) and r.get("value")]
    return {"id": mid, "badge": badge, "included": included, "ctx": None,
            "sizes": sizes}


def list_image_models(prov):
    """Image-generation models offered by `prov`, as catalogue rows.

    Only nano-gpt publishes a separate image catalogue; for every other
    provider the ordinary model list is the honest answer (OpenAI's, for
    instance, contains gpt-image-1 and dall-e-3 alongside the chat models),
    and the picker is a search box, so an unfiltered list costs nothing.
    """
    if prov["kind"] != "nanogpt":
        return list_models(prov)
    url = image_models_url(_prov_field(prov, "base_url"))
    r = _session().get(url, headers=_headers(prov), timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    out = []
    for mid, meta in _image_entries(r.json()):
        # A backdrop is generated from text alone. Roughly a fifth of this
        # catalogue is image-to-image (edit) models, which require an input
        # image and can only fail here -- listing them is a trap, not a
        # choice. "both" and an absent label are kept.
        if str(meta.get("iconLabel") or "") == "image-to-image":
            continue
        out.append(_image_model_entry(mid, meta))
    out.sort(key=lambda x: x["id"])
    return out


def generate_image(prompt, size=None, timeout=180):
    """Generate one image, returning raw bytes. Raises on failure.

    Never called from the turn pipeline -- see backdrops.py.
    """
    cfg = image_model()
    if not cfg:
        raise RuntimeError("No image model configured — set the `image_model` setting")
    size = size or cfg.get("size") or DEFAULT_IMAGE_SIZE
    prov = provider(cfg["provider"])
    if not prov:
        raise RuntimeError("Image provider %r not found" % cfg["provider"])
    base = (_prov_field(prov, "base_url") or "").rstrip("/")
    url = base + IMAGE_ENDPOINT
    body = {"model": cfg["model"], "prompt": prompt, "n": 1, "size": size,
            "response_format": "b64_json"}
    headers = {"Authorization": "Bearer %s" % (_prov_field(prov, "api_key") or ""),
               "Content-Type": "application/json"}
    resp = _session().post(url, json=body, headers=headers, timeout=timeout)
    if resp.status_code >= 400:
        raise LLMError("image generation failed (%s): %s"
                       % (resp.status_code, resp.text[:300]),
                       status_code=resp.status_code)
    payload = resp.json()
    entries = payload.get("data") or []
    if not entries:
        raise LLMError("image generation returned no data: %s"
                       % json.dumps(payload)[:300])
    entry = entries[0]
    if entry.get("b64_json"):
        import base64
        return base64.b64decode(entry["b64_json"])
    if entry.get("url"):
        got = _session().get(entry["url"], timeout=timeout)
        got.raise_for_status()
        return got.content
    raise LLMError("image entry had neither b64_json nor url: %s"
                   % json.dumps(entry)[:200])

def edit_image(prompt, image_bytes, size=None, timeout=180):
    """Generate one image FROM another, returning raw bytes. Raises on failure.

    The point is CONTINUITY: handed the room's existing picture, a model
    changes what the prompt asks for and leaves the rest of the place alone,
    where a fresh generation reinvents the architecture every time the light
    changes. Same configured model and provider as `generate_image`; only the
    endpoint and the encoding differ (multipart, because it carries a file).

    Never called from the turn pipeline -- see backdrops.py.
    """
    cfg = image_model()
    if not cfg:
        raise RuntimeError("No image model configured — set the `image_model` setting")
    prov = provider(cfg["provider"])
    if not prov:
        raise RuntimeError("Image provider %r not found" % cfg["provider"])
    base = (_prov_field(prov, "base_url") or "").rstrip("/")
    fields = {"model": (None, cfg["model"]), "prompt": (None, prompt),
              "n": (None, "1"), "response_format": (None, "b64_json"),
              "image": ("scene.png", image_bytes, "image/png")}
    # `auto` is a generations-only size on several providers, and an edit
    # inherits its dimensions from the image it is given anyway.
    if size or (cfg.get("size") and cfg["size"] != "auto"):
        fields["size"] = (None, size or cfg["size"])
    headers = {"Authorization": "Bearer %s" % (_prov_field(prov, "api_key") or "")}
    resp = _session().post(base + IMAGE_EDIT_ENDPOINT, files=fields,
                           headers=headers, timeout=timeout)
    if resp.status_code >= 400:
        raise LLMError("image edit failed (%s): %s"
                       % (resp.status_code, resp.text[:300]),
                       status_code=resp.status_code)
    payload = resp.json()
    entries = payload.get("data") or []
    if not entries:
        raise LLMError("image edit returned no data: %s"
                       % json.dumps(payload)[:300])
    entry = entries[0]
    if entry.get("b64_json"):
        import base64
        return base64.b64decode(entry["b64_json"])
    if entry.get("url"):
        got = _session().get(entry["url"], timeout=timeout)
        got.raise_for_status()
        return got.content
    raise LLMError("image edit entry had neither b64_json nor url: %s"
                   % json.dumps(entry)[:200])


@dataclass
class RetryConfig:
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    retryable_status: frozenset = frozenset({429, 500, 502, 503, 504})

    def delay_for(self, attempt: int) -> float:
        """Exponential backoff, JITTERED.

        The engine fans out: a turn runs character steps in parallel, and one
        upstream rate limit answers the whole wave at once. Without jitter
        every member of that wave sleeps exactly 1s, then exactly 2s, and
        collides with itself at each rung -- a synchronized retry storm made
        out of the very requests the backoff exists to separate. Measured on
        the live embeddings provider (2026-08-11): a burst of 12 took 4
        rate limits, and 8 SEQUENTIAL requests at ~2.5/s took 3, so the
        collisions are real at this engine's ordinary fan-out.

        EQUAL jitter, not full: half the delay is fixed and half is random.
        Full jitter can draw a delay near zero, which against a rate ceiling
        is a retry that was never really a backoff at all.
        """
        delay = min(self.base_delay * (2 ** attempt), self.max_delay)
        return delay / 2 + random.uniform(0, delay / 2)

DEFAULT_RETRY = RetryConfig()

def _should_retry(error: Exception, attempt: int, config: RetryConfig) -> bool:
    if attempt >= config.max_retries:
        return False
    if isinstance(error, Aborted):
        return False
    if isinstance(error, LLMError):
        if error.retryable:
            return True
        if error.status_code in config.retryable_status:
            return True
    if isinstance(error, _RETRYABLE_NETWORK):
        return True
    return False

def provider(pid):
    return q("SELECT * FROM providers WHERE id=?", (pid,), one=True)

def agent_models():
    return json.loads(get_setting("agent_models") or "{}")

# Intermediate inheritance, keyed role -> parent role, consulted before
# "default". IT IS DELIBERATELY EMPTY: every unset row follows `default`,
# which is what the settings panel has always said and what a host who
# leaves a row blank means.
#
# Eight rows used to live here -- the six Director specialists inheriting
# `director`, `utility` inheriting `mapping`, `repair` inheriting `utility`.
# Each had a real argument (a specialist is a hand of the Director; the
# helper lane is mechanical work that should ride the cheap model). Both
# arguments describe what a host would probably WANT, and neither survives
# the thing a host actually DOES: leaving six rows blank to park them all on
# one cheap model, and getting the frontier writing model instead the moment
# `director` was set. An inheritance nobody can see is not a good default,
# it is a trap -- and `f706da7` proved the label alone could not dig out of
# it, because the panel then had to teach eight exceptions to a rule that
# reads as universal.
#
# What the removal costs, stated so it is not rediscovered as a surprise:
# an unset `utility` lands back on `default`, which is how a 27.4s
# autobiographical consolidation once ate a live commit. That is survivable
# now only because consolidation moved OUT OF BAND
# (`commit.schedule_memory_consolidation` -> `jobs.py`), so it costs money
# on a slow default rather than the player's wall clock. If a background
# lane ever returns to the turn's critical path, it needs its own cheap
# role SET, not a hidden inheritance.
#
# The map and its lookup stay because the bootstrap publishes it and the
# panel renders "follow <parent>" from it (`app.py` bootstrap,
# `static/js/settings.js`): a future role that genuinely needs a non-default
# parent adds one row here and the label follows automatically, instead of
# the client learning a second copy of the rule. The ROLE string handed to
# _log_usage is the role's own regardless, which is what keeps per-role
# spend and served-model attribution separable (design note 19, "How it
# gets judged").
ROLE_FALLBACKS = {}


def resolve_role_candidates(role):
    models = agent_models()
    primary = (models.get(role)
               or models.get(ROLE_FALLBACKS.get(role, ""))
               or models.get("default"))

    if (
        not primary
        or not primary.get("provider")
        or not primary.get("model")
    ):
        raise RuntimeError(
            f"No model configured for role '{role}' "
            "— open API Connections"
        )

    configurations = [primary]

    for fallback in primary.get("fallbacks") or []:
        if not isinstance(fallback, dict):
            continue

        if (
            not fallback.get("provider")
            or not fallback.get("model")
        ):
            continue

        configurations.append({
            **primary,
            **fallback,
            "fallbacks": [],
        })

    resolved = []

    for config in configurations:
        prov = provider(config["provider"])

        if not prov:
            continue

        resolved.append((
            prov,
            config["model"],
            config,
        ))

    if not resolved:
        raise RuntimeError(
            f"No usable model configured for role '{role}'"
        )

    return resolved

def role_candidate_count(role):
    return len(resolve_role_candidates(role))

def resolve_role(role):
    return resolve_role_candidates(role)[0]

def _sampler_from(d):
    out = {}
    for k in SAMPLER_KEYS:
        v = (d or {}).get(k)
        if v is None or v == "":
            continue
        try:
            out[k] = float(v)
        except Exception:
            pass
    return out

def _headers(prov):
    h = {"Content-Type": "application/json"}
    if prov["api_key"]:
        h["Authorization"] = "Bearer " + prov["api_key"]
    if prov["kind"] == "openrouter":
        h["HTTP-Referer"] = "http://localhost:8008"
        h["X-Title"] = "Sonder Engine"
    return h

def _is_placeholder_json(text):
    """A JSON object whose string leaves are all the placeholder '...' (or
    empty) -- the skeleton some models emit under response_format=json_object
    instead of real content. True only when there is at least one string leaf
    and EVERY string leaf is a placeholder, so genuine prose is never mistaken
    for one."""
    try:
        data = json.loads(str(text or "").strip())
    except (TypeError, ValueError):
        return False
    strings = []

    def walk(v):
        if isinstance(v, str):
            strings.append(v)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    walk(data)
    if not strings:
        return False
    return all(s.strip().strip(".") == "" for s in strings)


def _strip_extended(body):
    # The 400-retry path: drop OPTIONAL params a provider may reject with a hard
    # 400 rather than ignore. Besides the extended samplers, this includes the
    # reasoning controls -- a provider/model that doesn't support the requested
    # reasoning_effort 400s ("Supported values are: high, max" on nanogpt's GLM
    # for 'none'/'low'), so the value must be stripped and the call retried, not
    # allowed to kill the turn. The assumption that an unknown key is ignored
    # held for most providers but not all.
    # `user` is the cache-affinity routing hint (_apply_cache_affinity) --
    # standard OpenAI schema, but it is added by an opt-in and it is purely a
    # performance hint, so on the 400-retry it goes the way of the extended
    # samplers rather than costing the turn on a host that rejects it.
    for k in ("top_k", "repetition_penalty", "min_p", "top_a",
              "reasoning_effort", "reasoning", "user"):
        body.pop(k, None)
    return body


# `response_format: {"type": "json_object"}` is NOT universally accepted. LM
# Studio 0.4.x hard-400s it -- "'response_format.type' must be 'json_schema' or
# 'text'" -- where most backends either honour or ignore it.
#
# That rejection used to cost far more than JSON mode. The 400 retry dropped
# EVERY optional field at once, so a 400 caused by response_format also took
# `reasoning_effort` with it, and a role deliberately configured "off" silently
# went back to thinking. Measured against a local Qwen3.6-35B-A3B, both still
# passing validate_llm_output_strict 2/2: director_interpret 48.70s -> 6.03s
# (8.1x) and character 52.38s -> 14.64s (3.6x). Nothing reported the cause --
# the turn simply ran slow.
#
# So the retry is STAGED: response_format first, because it is the least
# portable thing we send, and the blanket strip only if the provider is still
# unhappy. A rejection is then REMEMBERED per provider and model so the next
# call omits the field instead of paying the same 400 forever.
#
# READ THAT ERROR AGAIN: it names its own remedy. "must be 'json_schema' or
# 'text'" is not a refusal of structured output, it is a request for the
# ENFORCED kind, and the first fix here answered it by sending less rather than
# by sending what was asked for. `_apply_json_mode` now offers the schema
# first. A llama.cpp server fails differently and worse -- it accepts
# json_object with no 400 at all and then ignores it, so nothing above ever
# learns anything is wrong -- which is why the preference is unconditional
# rather than keyed to a host that complained.
#
# Process-local and reset on restart, for the same reason the embedding pacer
# is: the limit belongs to the provider, not the engine, and a restart is the
# cheapest moment to re-ask after a runtime upgrade or a model swap.
_NO_JSON_OBJECT: set = set()
_NO_JSON_OBJECT_LOCK = threading.Lock()


def _json_object_key(prov, model):
    return (str(_prov_field(prov, "id") or _prov_field(prov, "name") or ""),
            str(model or ""))


def _json_object_supported(prov, model) -> bool:
    """False once this provider+model has 400'd on response_format."""
    with _NO_JSON_OBJECT_LOCK:
        return _json_object_key(prov, model) not in _NO_JSON_OBJECT


def _note_json_object_rejected(prov, model):
    """Record that response_format=json_object is unusable here. Said once."""
    key = _json_object_key(prov, model)
    with _NO_JSON_OBJECT_LOCK:
        if key in _NO_JSON_OBJECT:
            return
        _NO_JSON_OBJECT.add(key)
    _logger.info(
        "providers: %s rejects response_format=json_object for %s; sending "
        "JSON-mode calls without it for the rest of this process",
        _prov_field(prov, "name") or "provider", model)


#: (role, provider) pairs already told that a request feature they have
#: configured cannot be sent on this connection. Said once per process: it is
#: a settings problem, not a per-call event.
_UNSENT_ON_ANTHROPIC: set = set()
_UNSENT_LOCK = threading.Lock()


def _warn_unsent_on_anthropic(prov, role, json_schema):
    """Say so when a configured request feature cannot reach this provider.

    The native Anthropic branch builds its body and RETURNS before
    `_apply_reasoning_effort` and `_apply_json_mode` are reached, so both are
    OpenAI-path only. Neither is a small setting: reasoning effort is a
    first-class per-role control in the settings panel, and the JSON grammar
    is worth a measured narrator 2/5 -> 5/5 valid and character 53.4s/2029
    tokens -> 15.3s/587. Configured against a native Anthropic connection
    they change nothing, and nothing said so -- the host reads the panel,
    sees the value they set, and attributes the difference to the model.

    Sending them is a request-shape decision and is the owner's to make.
    Saying that a set dial is inert is not.

    What that shape IS, though, is not a matter of taste, and the answer this
    docstring gave was out of date: Anthropic no longer spells reasoning as a
    token budget. `thinking: {type: "enabled", budget_tokens: N}` is
    deprecated on the 4.6 generation and rejected outright, with a 400, on the
    models after it. The live pair is `thinking: {type: "adaptive"}` alongside
    `output_config: {effort: low|medium|high|xhigh|max}` -- which is this
    module's own per-role dial under another name, so the mapping is nearly
    the identity rather than a budget anyone has to invent. "off" maps to
    `thinking: {type: "disabled"}`, which is itself refused above the middle
    effort levels on some models and refused entirely on others. Output is
    likewise no longer constrained only through a tool: `output_config:
    {format: ...}` is the native structured-output field, so the JSON grammar
    has a direct spelling here too.

    Both are versioned request shapes that have to be checked against the
    model actually configured before anything is sent, which is why this
    remains a decision rather than a repair -- but it should be decided
    against the current API, not the one this comment described.
    """
    name = _prov_field(prov, "name") or "provider"
    unsent = []
    if reasoning_effort_for(role):
        unsent.append("reasoning effort")
    if json_schema:
        unsent.append("the JSON grammar")
    if not unsent:
        return
    key = (str(role), name, tuple(unsent))
    with _UNSENT_LOCK:
        if key in _UNSENT_ON_ANTHROPIC:
            return
        _UNSENT_ON_ANTHROPIC.add(key)
    _logger.warning(
        "providers: %s is a native Anthropic connection, which this engine "
        "does not yet send %s on; the setting is configured for role %r and "
        "is having no effect",
        name, " or ".join(unsent), role)


_NO_JSON_SCHEMA: set = set()
_NO_JSON_SCHEMA_LOCK = threading.Lock()

# A STALL IS EVIDENCE, NOT PROOF -- so it is counted rather than acted on.
#
# A 400 naming the grammar is a provider saying "I cannot compile this", and
# one is enough. A dropped connection says only that the wire broke, which can
# be an ordinary blip; acting on one would cost a capable model its grammar
# for a bad minute. Acting on none costs a whole turn every time, because the
# request is re-sent until the retry budget runs out.
#
# Two independent stalls on the same provider+model is the line. Measured
# 2026-09-01: gemini-3.6-flash via openrouter stalled on the director_resolve
# schema at 60.2s on every one of six attempts, while the identical body
# without `response_format` answered in 12.5s -- a fault that reproduces six
# times out of six is not a blip, and a fault that never reproduces never
# reaches two.
_SCHEMA_STALLS: dict = {}
_SCHEMA_STALL_LIMIT = 2

# The learned set, persisted so a restart does not re-pay the tuition. Kept as
# a plain settings row rather than a table: it is a cache of provider
# behaviour, it is always safe to lose, and anything that cannot be re-learned
# in one call does not belong in it.
_NO_JSON_SCHEMA_SETTING = "providers_no_json_schema"


def _schema_blacklist_key(prov, model):
    return "%s\u0000%s" % _json_object_key(prov, model)


def _load_schema_blacklist():
    """Rehydrate what earlier runs learned. Failure here is not an error."""
    try:
        import json as _json
        stored = _json.loads(get_setting(_NO_JSON_SCHEMA_SETTING) or "[]")
    except Exception:
        return
    if not isinstance(stored, list):
        return
    with _NO_JSON_SCHEMA_LOCK:
        for entry in stored:
            if isinstance(entry, str) and "\u0000" in entry:
                _NO_JSON_SCHEMA.add(tuple(entry.split("\u0000", 1)))


def _persist_schema_blacklist():
    try:
        import json as _json
        with _NO_JSON_SCHEMA_LOCK:
            rows = ["%s\u0000%s" % k for k in sorted(_NO_JSON_SCHEMA)]
        set_setting(_NO_JSON_SCHEMA_SETTING, _json.dumps(rows))
    except Exception:
        # A cache that cannot be written is still a cache that works for this
        # process. Never let bookkeeping fail a call.
        pass


def _json_schema_supported(prov, model) -> bool:
    """False once this provider+model is known not to answer a json_schema."""
    if not _NO_JSON_SCHEMA and not getattr(_json_schema_supported, "_loaded", False):
        _json_schema_supported._loaded = True
        _load_schema_blacklist()
    with _NO_JSON_SCHEMA_LOCK:
        return _json_object_key(prov, model) not in _NO_JSON_SCHEMA


def _note_json_schema_rejected(prov, model):
    """Record that response_format=json_schema is unusable here. Said once."""
    key = _json_object_key(prov, model)
    with _NO_JSON_SCHEMA_LOCK:
        if key in _NO_JSON_SCHEMA:
            return
        _NO_JSON_SCHEMA.add(key)
    _logger.info(
        "providers: %s rejects response_format=json_schema for %s; falling "
        "back to json_object from now on",
        _prov_field(prov, "name") or "provider", model)
    _persist_schema_blacklist()


def _stream_error_status(err) -> int:
    """The HTTP status an in-stream error frame is reporting, or 0.

    A provider that REJECTS a request does not always get to say so with an
    HTTP status: once the response has begun, the rejection arrives as an
    `{"error": {...}}` frame and the status lives inside it. Every raise site
    below used to hardcode 0, which threw that away -- and 0 is not 400, so
    `_chat_complete_once`'s json-mode recovery could never fire on the
    streaming path. Measured 2026-09-01 on google/gemini-3.7-flash, which
    rejects `response_format` and answers fine without it: the blocking path
    recovered and the streaming path raised
    `provider stream error: Request contains an invalid argument.` and killed
    the turn.

    The rule is about the transport, not the model: a rejection is the same
    event whether it arrives as a status line or a frame, so recovery must not
    depend on which one carried it. Reading the code the frame already states
    is the whole fix -- no message matching, which would only work until a
    provider rewords it.
    """
    if not isinstance(err, dict):
        return 0
    for key in ("code", "status", "status_code", "http_status"):
        value = err.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, int) and 100 <= value <= 599:
            return value
        if isinstance(value, str) and value.strip().isdigit():
            number = int(value.strip())
            if 100 <= number <= 599:
                return number
    return 0


def _note_json_schema_stalled(prov, model):
    """Count a schema request that was accepted and then never answered."""
    key = _json_object_key(prov, model)
    with _NO_JSON_SCHEMA_LOCK:
        if key in _NO_JSON_SCHEMA:
            return
        n = _SCHEMA_STALLS.get(key, 0) + 1
        _SCHEMA_STALLS[key] = n
        crossed = n >= _SCHEMA_STALL_LIMIT
    if not crossed:
        _logger.info(
            "providers: %s stalled on a json_schema request for %s (%d of %d "
            "before it is treated as unsupported)",
            _prov_field(prov, "name") or "provider", model, n,
            _SCHEMA_STALL_LIMIT)
        return
    _note_json_schema_rejected(prov, model)


def _apply_json_mode(body, prov, model, json_mode, json_schema=None):
    """Attach JSON mode, preferring an ENFORCED schema over an advisory flag.

    `json_object` is not a guarantee. It is honoured by the big hosted APIs and
    is merely a suggestion on a llama.cpp-family server, which accepts it with
    no 400 and then samples freely -- so the staged retry below, which only
    fires on a 400, never learns anything is wrong. Measured on llama.cpp
    2.28.2 against a local 27B, five trials per mode:

        narrator    none 2/5 valid   json_object 0/5   json_schema 5/5
        character   none 4/5 valid   json_object 4/5   json_schema 5/5

    `json_object` was WORSE THAN SENDING NOTHING on the narrator, whose prompt
    leads with prose formatting: the flag nudges toward JSON, the prompt asks
    for prose, and the model splits the difference into neither.

    A schema is compiled to a sampling grammar instead, so the shape is not
    requested but enforced -- and it is faster, because a constrained model
    cannot pad: `character` went 53.4s/2029 tokens to 15.3s/587, a 3.5x cut on
    the heaviest role in the pipeline.

    Schema first, `json_object` second, nothing last. A provider that refuses
    either is memoised so the tax is paid once per process, not per call.
    """
    if not json_mode:
        return body
    if json_schema and _json_schema_supported(prov, model):
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": "output", "schema": json_schema},
        }
    elif _json_object_supported(prov, model):
        body["response_format"] = {"type": "json_object"}
    return body


def _merge_samplers(cfg, sampler, temperature):
    scfg = _sampler_from(cfg)
    scall = _sampler_from(sampler)
    merged = dict(DEFAULT_SAMPLERS)
    merged.update(scfg)
    merged.update(scall)
    if "temperature" in scall:
        t = scall["temperature"]
    elif temperature is not None:
        t = temperature
    elif "temperature" in scfg:
        t = scfg["temperature"]
    else:
        t = DEFAULT_SAMPLERS["temperature"]
    merged.pop("temperature", None)
    if "top_k" in merged:
        merged["top_k"] = int(merged["top_k"])
    for k, nv in _NOOP.items():
        if k in merged and merged[k] == nv:
            merged.pop(k)
    return t, merged

def _classify_error(e: Exception) -> LLMError:
    if isinstance(e, LLMError):
        return e
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        msg = f"HTTP {status}: {e.response.text[:300]}"
        retryable = status in DEFAULT_RETRY.retryable_status
        return LLMError(msg, status, retryable)
    if isinstance(e, _RETRYABLE_NETWORK):
        return LLMError(str(e), 0, True)
    return LLMError(str(e), 0, False)

def _sse_openai(url, headers, body, sink, role=None, model=None):
    body["stream"] = True
    # Ask for a final usage-bearing chunk -- without this, streamed
    # responses never report token counts at all, so there'd be no way to
    # confirm implicit prompt caching (see _log_usage) is doing anything on
    # the streaming path, which is the one actually used during normal
    # pipeline runs (token_sink is set for the live "stream agents" UI).
    body["stream_options"] = {"include_usage": True}
    text, reasoning = "", ""
    usage = None
    served = ""
    t0 = time.time()
    _check_cancel()
    with _session().post(url, headers=headers, json=body, stream=True,
                         timeout=_request_timeout()) as r, _abortable(r):
        if r.status_code >= 400:
            raise LLMError(f"HTTP {r.status_code}: {r.text[:300]}", r.status_code, r.status_code in DEFAULT_RETRY.retryable_status)
        for raw in r.iter_lines():
            _check_cancel()
            if not raw:
                continue
            line = raw.decode("utf-8", "ignore")
            if line.startswith("data: "):
                line = line[6:]
            if line.strip() == "[DONE]":
                break
            try:
                j = json.loads(line)
            except Exception:
                continue
            # Some OpenAI-compatible backends emit an {"error": {...}} chunk
            # mid-stream (e.g. an overload 30s in). Ignoring it silently
            # returned the truncated prefix as a completed response, which for
            # a JSON step could pass validation and commit truncated. Surface
            # it as a retryable failure instead.
            if isinstance(j, dict) and j.get("error"):
                err = j["error"]
                msg = err.get("message") if isinstance(err, dict) else str(err)
                raise LLMError(f"provider stream error: {msg}",
                               _stream_error_status(err), True)
            if j.get("usage"):
                usage = j["usage"]
            # The finish reason rides the LAST chunk of a stream, usually one
            # carrying an empty delta. This is the branch the pipeline
            # actually runs (the sink is set for the live UI), so capturing
            # only in the non-streaming branch would leave the signal dead
            # exactly where it is needed -- the same way reasoning capture was
            # dead here for a release.
            _capture_choice_finish(j)
            # The model of record rides every chunk of an OpenAI-compatible
            # stream, and a router alias is not a model -- see
            # `_note_served_model`. The streaming branch is the one the
            # pipeline actually runs, so reading it only in the non-streaming
            # path would leave substitution invisible exactly where it counts.
            if not served:
                served = str(j.get("model") or "").strip()
            _delta = (j.get("choices") or [{}])[0].get("delta", {})
            # Reasoning arrives on its OWN delta key, never in `content`, and
            # it is the pipeline's real path -- the sink is set for the live
            # UI, so this function serves every engine turn while the
            # non-streaming branch below serves almost nothing. Capturing
            # reasoning only there meant the feature was dead in the engine
            # and looked, from the outside, exactly like a model that does not
            # expose a trace. It is NOT passed to `sink`: the sink is player-
            # facing prose, and a model's private thinking is not that.
            _r = _delta.get("reasoning") or _delta.get("reasoning_content")
            if isinstance(_r, str) and _r:
                reasoning += _r
            d = _delta.get("content")
            if d:
                text += d
                sink(d)
    if role:
        _log_usage(role, model, t0, usage, served=served,
                   kind="stream")
    try:
        last_reasoning.set(reasoning or None)
    except Exception:
        pass
    return text

def _sse_anthropic(base, headers, body, sink, role=None, model=None):
    body["stream"] = True
    text = ""
    # Anthropic splits usage across two events: input and cache counts arrive
    # on message_start, the final output count on message_delta. Neither alone
    # is the whole picture, so both are folded together.
    usage = None
    served = ""
    t0 = time.time()
    _check_cancel()
    with _session().post(base + "/v1/messages", headers=headers, json=body,
                         stream=True, timeout=_request_timeout()) as r, \
            _abortable(r):
        if r.status_code >= 400:
            raise LLMError(f"HTTP {r.status_code}: {r.text[:300]}", r.status_code, r.status_code in DEFAULT_RETRY.retryable_status)
        for raw in r.iter_lines():
            _check_cancel()
            if not raw:
                continue
            line = raw.decode("utf-8", "ignore")
            if line.startswith("data: "):
                line = line[6:]
            try:
                j = json.loads(line)
            except Exception:
                continue
            # Anthropic's documented mid-stream error event (overloaded_error,
            # etc.) -- surface as retryable rather than silently truncating.
            if j.get("type") == "error":
                err = j.get("error") or {}
                msg = err.get("message") if isinstance(err, dict) else str(err)
                raise LLMError(f"provider stream error: {msg or 'overloaded'}",
                               _stream_error_status(err), True)
            if j.get("type") == "message_start":
                message = j.get("message") or {}
                usage = _merge_usage(usage, message.get("usage"))
                # The model of record. Anthropic states it once, on this
                # event -- the same object this line already opens for
                # `usage` -- and `served` was assigned `""` at the top of
                # the function and never again, so `_note_served_model`
                # returned on its own `if not served` and the ledger
                # recorded served == requested by fallback. Both
                # OpenAI-compatible stream readers do this; neither
                # Anthropic one did, and the streaming path is the one the
                # pipeline runs.
                if not served:
                    served = str(message.get("model") or "").strip()
            elif j.get("type") == "message_delta":
                usage = _merge_usage(usage, j.get("usage"))
                # Anthropic reports `max_tokens` here rather than on a choice.
                stop = (j.get("delta") or {}).get("stop_reason")
                if stop:
                    _capture_finish_reason(stop)
            if j.get("type") == "content_block_delta":
                d = j.get("delta", {}).get("text")
                if d:
                    text += d
                    sink(d)
    if role:
        _log_usage(role, model, t0, usage, served=served,
                   kind="stream")
    return text

def chat_complete(
    role,
    system,
    user,
    temperature=None,
    json_mode=True,
    max_tokens=16000,
    sampler=None,
    retry_config=None,
    candidate_offset=0,
    token_ceiling=None,
    json_schema=None,
    reasoning_effort=None,
):
    """``reasoning_effort`` is a per-CALL override of the role's configured
    effort (`reasoning_effort_for`): "off" for a JSON-shaped utility call
    whose output is the whole budget, because every OpenAI-style seam counts
    a thinking model's private trace against `max_tokens` and the seam
    offers no way to budget the two apart. None leaves the role's setting
    in charge, exactly as before the parameter existed."""
    _check_cancel()
    # Final, universal boundary: even repair prompts and utility calls that do
    # not originate in prompts.py must know that free text is localized while
    # JSON/schema protocol remains canonical English.
    system = apply_common_prompt_policy(system)
    retry_config = retry_config or DEFAULT_RETRY
    max_tokens = _clamp_max_tokens(
        _scale_for_language(max_tokens), ceiling=token_ceiling)

    candidates = resolve_role_candidates(role)

    try:
        candidate_offset = max(0, int(candidate_offset))
    except (TypeError, ValueError):
        candidate_offset = 0

    if candidate_offset >= len(candidates):
        raise RuntimeError(
            f"No backup model exists for role '{role}' "
            f"at offset {candidate_offset}"
        )

    resolved = candidates[candidate_offset]
    last_error = None
    # A reasoning-only response has no answer to salvage.  On its retry only,
    # ask for a direct answer instead of spending the same budget the same way
    # again.  This is deliberately adaptive rather than a role/model default:
    # successful reasoning-enabled calls retain every configured feature.
    # A caller that asked for an effort outright starts there instead.
    reasoning_effort_override = _coerce_reasoning_effort(reasoning_effort) \
        or None

    for attempt in range(retry_config.max_retries + 1):
        _check_cancel()

        if attempt > 0:
            generation_notice({
                "type": "generation_reset",
                "attempt": attempt + 1,
                "candidate": candidate_offset,
                "reason": (
                    type(last_error).__name__
                    if last_error
                    else "retry"
                ),
            })

        try:
            return _chat_complete_once(
                role,
                system,
                user,
                temperature,
                json_mode,
                max_tokens,
                sampler,
                resolved=resolved,
                json_schema=json_schema,
                reasoning_effort_override=reasoning_effort_override,
            )
        except Aborted:
            raise
        except Exception as exc:
            # AN ABORT IS NOT A TRANSPORT FAULT. Cancelling closes the socket
            # under a blocked read, which surfaces here as an ordinary
            # connection error -- retryable, by every rule this loop has. On
            # any attempt but the last that costs nothing (the backoff's own
            # `_check_cancel` fires before it sleeps), but on the LAST attempt
            # `_should_retry` is False and the connection error is raised as
            # the call's outcome, so the caller sees a network failure where
            # the user pressed stop and may go on to spend a repair call on
            # it. Asked first, the answer is always the true one.
            _check_cancel()
            error = _classify_error(exc)
            last_error = error

            if isinstance(error, ReasoningBudgetExhausted):
                reasoning_effort_override = "off"

            if not _should_retry(error, attempt, retry_config):
                raise error

            # Sleep in short slices so an abort during backoff is observed
            # promptly instead of stalling for the full (up to ~30s) delay.
            deadline = retry_config.delay_for(attempt)
            slept = 0.0
            while slept < deadline:
                _check_cancel()
                step = min(0.5, deadline - slept)
                time.sleep(step)
                slept += step

    if last_error:
        raise last_error

    raise LLMError(
        f"Model generation failed for role '{role}'",
        retryable=False,
    )

def _int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _normalize_usage(usage):
    """One shape from either provider dialect.

    The two report caching in entirely different fields, and reading only one
    dialect makes the other look like caching never happened -- which is
    exactly how a real cache miss and an unread field become indistinguishable.

    - OpenAI-compatible: prompt_tokens / completion_tokens, with implicit-cache
      reads under prompt_tokens_details.cached_tokens.
    - Anthropic: input_tokens / output_tokens, with explicit cache_read_ and
      cache_creation_input_tokens. An aggregator fronting Anthropic may pass
      either or both through, so both are always checked.

    `cache_write` matters as much as `cache_read`: a first call writes the
    prefix and later ones read it, so writes with no subsequent reads is the
    signature of a prefix that is changing between calls (or sitting under the
    model's minimum cacheable length) rather than caching working.
    """
    usage = usage if isinstance(usage, dict) else {}
    details = usage.get("prompt_tokens_details")
    details = details if isinstance(details, dict) else {}
    return {
        "input": _int(usage.get("prompt_tokens") or usage.get("input_tokens")),
        "output": _int(usage.get("completion_tokens")
                       or usage.get("output_tokens")),
        "cache_read": _int(usage.get("cache_read_input_tokens")
                           or details.get("cached_tokens")),
        "cache_write": _int(usage.get("cache_creation_input_tokens")),
    }


def _merge_usage(base, extra):
    """Fold a later usage report into an earlier one. Anthropic streams usage
    in two pieces -- input and cache counts on message_start, the final output
    count on message_delta -- so neither event alone is the whole picture."""
    base = base if isinstance(base, dict) else {}
    extra = extra if isinstance(extra, dict) else {}
    merged = dict(base)
    for key, value in extra.items():
        if _int(value) or key not in merged:
            merged[key] = value
    return merged


# Router aliases that have already answered, and with what. Process-local and
# reset on restart, like the embedding pacer: what a router served last week is
# not evidence about this week.
_SERVED_SEEN = {}
_SERVED_LOCK = threading.Lock()


def _note_served_model(role, requested, served):
    """Say so when the model that answered is not the one that was asked for.

    A ROUTER ALIAS IS NOT A MODEL. The live configuration points director,
    character and narrator at `accounts/fireworks/routers/glm-5p2-fast`, and a
    router dispatches to whatever backing model it picks per request -- so the
    engine can be served a materially different model, of different speed and
    different reliability, with nothing in any log, metric or stored turn
    saying which.

    That is not a theoretical gap. Every wall-clock number in the corpus is a
    mixture over this unrecorded variable, which made a latency investigation
    of the pipeline's own stages produce medians that were an artefact of
    which backing model happened to answer. `usage` was already read back for
    exactly this reason -- to make caching observable rather than assumed --
    and the model's own identity was sitting unread in the same response.

    Logged once per (role, alias, served) so a substitution is visible without
    a line per call.
    """
    served = str(served or "").strip()
    requested = str(requested or "").strip()
    if not served or not requested or served == requested:
        return
    key = (role, requested, served)
    with _SERVED_LOCK:
        if key in _SERVED_SEEN:
            return
        _SERVED_SEEN[key] = True
    _logger.warning(
        "provider served a different model than requested: role=%s "
        "requested=%s served=%s -- timings and quality for this role are "
        "about %s, not %s", role, requested, served, served, requested)


def _log_usage(role, model, t0, usage, served=None, kind="chat"):
    """Make caching observable. Without reading `usage` back there is no way to
    confirm that a role's static system prompt -- repeated byte-for-byte on
    every call for that role -- is actually being served from cache instead of
    reprocessed, which is how a silently-uncached setup goes unnoticed.

    `served` is the model the PROVIDER says answered, which is not always the
    one that was asked for -- see `_note_served_model`. It is logged as the
    model of record so a metrics line describes the call that happened.

    Besides the stderr line, every call is offered to `call_ledger_sink` so a
    pipeline step can persist its own per-call ledger (see the ContextVar's
    comment). `kind` says which transport carried it ('chat' | 'stream');
    embeddings report through their own batch path with kind 'embedding'.
    """
    from core.logging_utils import log_llm_call
    counts = _normalize_usage(usage)
    _note_served_model(role, model, served)
    record_llm_call({
        "role": role,
        "requested": model,
        "served": str(served or "").strip() or model,
        "in": counts["input"],
        "out": counts["output"],
        "cached": counts["cache_read"],
        "duration": round(time.time() - t0, 3),
        "kind": kind,
    })
    try:
        log_llm_call(
            role, str(served or "").strip() or model,
            system_tokens=counts["input"],
            response_tokens=counts["output"],
            cached_tokens=counts["cache_read"],
            cache_write_tokens=counts["cache_write"],
            duration=time.time() - t0,
        )
    except Exception:
        pass


def record_llm_call(entry):
    """Hand one finished provider call to the context's ledger sink, if any.

    A diagnostic must never fail the call it is describing, so every failure
    -- a sink that raises, a sink that is not callable -- is swallowed."""
    sink = call_ledger_sink.get()
    if sink is None:
        return
    try:
        sink(dict(entry))
    except Exception:
        pass

def _chat_complete_once(
    role,
    system,
    user,
    temperature,
    json_mode,
    max_tokens,
    sampler,
    resolved=None,
    json_schema=None,
    reasoning_effort_override=None,
):
    _check_cancel()
    # Clear before the request, not after: every path below either records a
    # reason or records nothing, and "nothing" must read as unknown rather
    # than as the previous call's answer.
    _capture_finish_reason(None)

    prov, model, cfg = resolved or resolve_role(role)
    t, merged = _merge_samplers(cfg, sampler, temperature)
    base = prov["base_url"].rstrip("/")
    raw_sink = token_sink.get()
    streaming = bool(raw_sink)

    # A FRESH GUARD PER ATTEMPT. `OutputGuard` accumulates every delta it is
    # fed and judges a 4KB tail plus a 16KB loop window, so one guard shared
    # across this function's several stream attempts -- the two json_schema
    # rejection stages and the placeholder-skeleton re-stream -- judges the
    # concatenation of two different responses. Two attempts at the same
    # object look exactly like the failure it exists to catch, so the guard
    # could abort a healthy second attempt precisely because the first one
    # was retried; and `_checked_len` carried over, so the first stride of
    # the second response went unexamined. A guard is about ONE response.
    def guarded():
        return _guarded_sink(raw_sink)

    if prov["kind"] == "anthropic":
        h = {
            "x-api-key": prov["api_key"] or "",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        body = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": t,
            "system": _anthropic_system(system, prov),
            "messages": [
                {
                    "role": "user",
                    "content": user,
                }
            ],
        }

        for key in ANTHROPIC_SAMPLERS:
            if key in merged:
                body[key] = merged[key]

        _warn_unsent_on_anthropic(prov, role, json_schema)

        if streaming:
            return _sse_anthropic(
                base,
                h,
                dict(body),
                guarded(),
                role=role,
                model=model,
            )

        _t0 = time.time()
        response = _post_abortable(
            base + "/v1/messages",
            headers=h,
            json=body,
        )

        if response.status_code >= 400:
            raise LLMError(
                f"{prov['name']}: HTTP {response.status_code}: "
                f"{response.text[:300]}",
                response.status_code,
                response.status_code
                in DEFAULT_RETRY.retryable_status,
            )

        parsed = response.json()
        _log_usage(role, model, _t0, parsed.get("usage"),
                   served=parsed.get("model"))
        _capture_finish_reason(parsed.get("stop_reason"))
        return "".join(
            block.get("text", "")
            for block in parsed.get("content", [])
        )

    body = {
        "model": model,
        "temperature": t,
        "max_tokens": max_tokens,
        "messages": [
            _openai_system_message(system, prov, model),
            {
                "role": "user",
                "content": user,
            },
        ],
    }
    body.update(merged)
    _apply_provider_routing(body, prov)
    _apply_cache_affinity(body, prov, role)
    _apply_reasoning_effort(
        body, prov, role, effort_override=reasoning_effort_override)

    _apply_json_mode(body, prov, model, json_mode, json_schema)

    url = base + "/chat/completions"
    headers = _headers(prov)

    if streaming:
        try:
            out = _sse_openai(
                url,
                headers,
                dict(body),
                guarded(),
                role=role,
                model=model,
            )
        except (LLMError,) + _RETRYABLE_NETWORK as exc:
            # A SCHEMA THAT IS NEVER ANSWERED IS A SCHEMA THAT WAS REJECTED.
            #
            # This ladder existed for a provider that says 400. Some do not:
            # handed a `response_format` they cannot compile, they accept the
            # request and then never answer it, and an intermediary drops the
            # connection. That arrives as requests.ConnectionError, sails past
            # an `except LLMError` gated on 400, and reaches the outer retry
            # loop -- which re-sends the identical unusable body three more
            # times. RetryConfig.max_retries is 3 (four attempts), so a 60s
            # cut becomes 4*60s plus jittered backoff: the ~245-253s failures
            # this engine spent a day attributing to nanogpt and then to
            # openrouter.
            #
            # Measured 2026-09-01, gemini-3.6-flash via openrouter on the real
            # director_resolve body: verbatim, it dies at 60.2s every time;
            # with `response_format` removed and nothing else changed, first
            # byte at 2.3s and done in 12.5s. Removing reasoning effort,
            # provider routing, stream_options or lowering max_tokens each
            # changed nothing -- the schema was the only variable that mattered.
            #
            # So a connection death on a schema-bearing request takes the same
            # remedy as a 400. It is NOT recorded via
            # `_note_json_schema_rejected`: a dropped connection can also be an
            # ordinary blip, and one bad minute should not permanently cost a
            # capable model its grammar. Recover this call; judge the model on
            # what it says, not on what the wire did.
            # Narrowed to a full json_schema, which is what was measured to
            # stall. `json_object` is a one-word constraint no provider has to
            # compile, so a connection death alongside it is far likelier to be
            # an ordinary blip -- and that belongs to the outer retry loop,
            # not to a capability downgrade here.
            _rf = body.get("response_format")
            schema_bearing = (isinstance(_rf, dict)
                              and _rf.get("type") == "json_schema")
            if isinstance(exc, LLMError):
                if exc.status_code != 400:
                    raise
            elif not schema_bearing:
                raise
            else:
                _note_json_schema_stalled(prov, model)

            # Stage 1: response_format alone. Dropping only the least portable
            # field keeps reasoning_effort and the extended samplers, which a
            # blanket strip discards for a rejection they did not cause.
            recovered = False
            if "response_format" in body:
                stage_one = dict(body)
                stage_one.pop("response_format", None)
                try:
                    out = _sse_openai(
                        url,
                        headers,
                        stage_one,
                        guarded(),
                        role=role,
                        model=model,
                    )
                    _note_json_object_rejected(prov, model)
                    recovered = True
                except LLMError as exc_one:
                    if exc_one.status_code != 400:
                        raise

            # Stage 2: every optional field, as before.
            if not recovered:
                fallback_body = _strip_extended(dict(body))
                fallback_body.pop("response_format", None)

                out = _sse_openai(
                    url,
                    headers,
                    fallback_body,
                    guarded(),
                    role=role,
                    model=model,
                )
        # Same placeholder-skeleton guard as the non-streaming path below: a
        # model that "honours" response_format=json_object by streaming an
        # all-"..." skeleton would send that skeleton to the player as prose.
        # The pipeline runs on THIS streaming path (sink set for the live UI),
        # so the guard has to live here too. Retry once without json_mode --
        # still streaming, so the live UI keeps receiving tokens.
        if json_mode and _is_placeholder_json(out):
            retry_body = dict(body)
            retry_body.pop("response_format", None)
            out = _sse_openai(
                url,
                headers,
                retry_body,
                guarded(),
                role=role,
                model=model,
            )
        return out

    _t0 = time.time()
    response = _post_abortable(
        url,
        headers=headers,
        json=body,
    )

    if response.status_code == 400:
        # Stage 0: a json_schema this provider cannot compile. Drop to the
        # advisory flag rather than to nothing -- a host that rejects grammars
        # usually still honours json_object, and giving up both at once would
        # cost every later call on this provider its only shape constraint.
        _rf = (body.get("response_format") or {})
        if _rf.get("type") == "json_schema":
            stage_zero = dict(body)
            if _json_object_supported(prov, model):
                stage_zero["response_format"] = {"type": "json_object"}
            else:
                stage_zero.pop("response_format", None)
            response = _post_abortable(
                url,
                headers=headers,
                json=stage_zero,
            )
            if response.status_code < 400:
                _note_json_schema_rejected(prov, model)
                body = stage_zero

        # Stage 1: response_format alone -- see _apply_json_mode. Keeping the
        # reasoning controls here is the whole point: a 400 they did not cause
        # must not turn a role configured "off" back into a thinking model.
        if response.status_code == 400 and "response_format" in body:
            stage_one = dict(body)
            stage_one.pop("response_format", None)
            response = _post_abortable(
                url,
                headers=headers,
                json=stage_one,
            )
            if response.status_code < 400:
                _note_json_object_rejected(prov, model)

        # Stage 2: every optional field, as before.
        if response.status_code == 400:
            fallback_body = _strip_extended(dict(body))
            fallback_body.pop("response_format", None)

            response = _post_abortable(
                url,
                headers=headers,
                json=fallback_body,
            )

    if response.status_code >= 400:
        raise LLMError(
            f"{prov['name']}: HTTP {response.status_code}: "
            f"{response.text[:300]}",
            response.status_code,
            response.status_code
            in DEFAULT_RETRY.retryable_status,
        )

    parsed = response.json()
    # A 200 with no `choices` is not a model answering badly, it is the provider
    # not answering at all -- observed live at ~2.6% of beats on one endpoint,
    # surfacing as "'choices'" inside a JSON-validation error that blamed the
    # model. Retried as a transport failure, which is what it is; a KeyError
    # here would abort the beat and read as the character having nothing to say.
    if not (parsed.get("choices") or []):
        raise LLMError(
            f"{prov['name']}: response carried no choices "
            f"({str(parsed)[:200]})",
            response.status_code,
            True,
        )
    _capture_reasoning(parsed["choices"][0].get("message"))
    _capture_choice_finish(parsed)
    content = _message_content(parsed, prov["name"], model)
    # Some models (nemotron:thinking observed) honour response_format=json_object
    # by returning a syntactically-valid SKELETON with every string value set to
    # the literal "..." -- which parses and validates fine, so "..." reaches the
    # player as prose. When json_mode produced such a skeleton, retry once
    # WITHOUT json_mode (the same model writes real content ungated).
    if json_mode and _is_placeholder_json(content):
        retry_body = dict(body)
        retry_body.pop("response_format", None)
        alt = _post_abortable(url, headers=headers, json=retry_body)
        if alt.status_code < 400:
            parsed = alt.json()
            _capture_reasoning(parsed["choices"][0].get("message"))
            _capture_choice_finish(parsed)
            content = _message_content(parsed, prov["name"], model)
    _log_usage(role, model, _t0, parsed.get("usage"),
                   served=parsed.get("model"))
    return content

def _message_content(parsed, prov_name, model):
    """The answer, or a retryable failure that says what actually happened.

    A reasoning model can return a message carrying `reasoning` and NO
    `content` key at all -- it spent its whole budget thinking and never
    wrote the answer. Read as parsed["..."]["content"], that raised
    KeyError('content'), whose str() is the bare word 'content', and it
    surfaced live as "all providers failed (last provider error:
    'content')" on a specialist call. A missing answer is an ordinary,
    retryable outcome; it should never look like a parser bug.
    """
    message = ((parsed.get("choices") or [{}])[0] or {}).get("message") or {}
    content = message.get("content")
    if content:
        return content
    reasoning = str(message.get("reasoning") or "").strip()
    if reasoning:
        raise ReasoningBudgetExhausted(
            f"{prov_name}: {model} returned reasoning but no answer "
            f"({len(reasoning)} chars of trace, content empty) -- the "
            f"thinking budget consumed the reply")
    if content == "":
        raise LLMError(f"{prov_name}: {model} returned empty content",
                       None, True)
    raise LLMError(
        f"{prov_name}: response message carried no content "
        f"({str(message)[:200]})", None, True)


async def chat_complete_async(
    role,
    system,
    user,
    temperature=None,
    json_mode=True,
    max_tokens=16000,
    sampler=None,
    retry_config=None,
    candidate_offset=0,
    json_schema=None,
):
    _check_cancel()
    retry_config = retry_config or DEFAULT_RETRY
    max_tokens = _clamp_max_tokens(max_tokens)

    candidates = resolve_role_candidates(role)
    candidates = candidates[max(0, int(candidate_offset)):]

    if not candidates:
        raise RuntimeError(
            f"No backup model exists for role '{role}' "
            f"at offset {candidate_offset}"
        )

    last_error = None
    first_attempt = True

    for candidate_index, candidate in enumerate(candidates):
        for attempt in range(
            retry_config.max_retries + 1
        ):
            _check_cancel()

            if not first_attempt:
                generation_notice({
                    "type": "generation_reset",
                    "attempt": attempt + 1,
                    "candidate": (
                        candidate_offset + candidate_index
                    ),
                    "reason": (
                        type(last_error).__name__
                        if last_error
                        else "retry"
                    ),
                })

            first_attempt = False

            try:
                return await _chat_complete_async_once(
                    role,
                    system,
                    user,
                    temperature,
                    json_mode,
                    max_tokens,
                    sampler,
                    resolved=candidate,
                    json_schema=json_schema,
                )
            except Aborted:
                raise
            except Exception as exc:
                error = _classify_error(exc)
                last_error = error

                if _should_retry(
                    error,
                    attempt,
                    retry_config,
                ):
                    await asyncio.sleep(
                        retry_config.delay_for(attempt)
                    )
                    continue

                if not error.retryable:
                    raise error

                break

    if last_error:
        raise last_error

    raise LLMError(
        f"All configured models failed for role '{role}'",
        retryable=False,
    )

async def _chat_complete_async_once(
    role,
    system,
    user,
    temperature,
    json_mode,
    max_tokens,
    sampler,
    resolved=None,
    json_schema=None,
):
    _check_cancel()
    _capture_finish_reason(None)
    prov, model, cfg = resolved or resolve_role(role)
    t, merged = _merge_samplers(cfg, sampler, temperature)
    base = prov["base_url"].rstrip("/")
    raw_sink = token_sink.get()
    streaming = bool(raw_sink)

    # A FRESH GUARD PER ATTEMPT. `OutputGuard` accumulates every delta it is
    # fed and judges a 4KB tail plus a 16KB loop window, so one guard shared
    # across this function's several stream attempts -- the two json_schema
    # rejection stages and the placeholder-skeleton re-stream -- judges the
    # concatenation of two different responses. Two attempts at the same
    # object look exactly like the failure it exists to catch, so the guard
    # could abort a healthy second attempt precisely because the first one
    # was retried; and `_checked_len` carried over, so the first stride of
    # the second response went unexamined. A guard is about ONE response.
    def guarded():
        return _guarded_sink(raw_sink)

    if prov["kind"] == "anthropic":
        h = {"x-api-key": prov["api_key"] or "", "anthropic-version": "2023-06-01", "content-type": "application/json"}
        body = {"model": model, "max_tokens": max_tokens, "temperature": t, "system": _anthropic_system(system, prov), "messages": [{"role": "user", "content": user}]}
        for k in ANTHROPIC_SAMPLERS:
            if k in merged:
                body[k] = merged[k]
        _warn_unsent_on_anthropic(prov, role, json_schema)
        async with httpx.AsyncClient(timeout=_httpx_timeout()) as client:
            if streaming:
                return await _sse_anthropic_async(base, h, dict(body), guarded(), client, role=role, model=model)
            _t0 = time.time()
            r = await client.post(base + "/v1/messages", headers=h, json=body)
            if r.status_code >= 400:
                raise LLMError(f"{prov['name']}: HTTP {r.status_code}: {r.text[:300]}", r.status_code, r.status_code in DEFAULT_RETRY.retryable_status)
            parsed = r.json()
            _log_usage(role, model, _t0, parsed.get("usage"),
                   served=parsed.get("model"))
            _capture_finish_reason(parsed.get("stop_reason"))
            return "".join(b.get("text", "") for b in parsed.get("content", []))

    body = {"model": model, "temperature": t, "max_tokens": max_tokens, "messages": [_openai_system_message(system, prov, model), {"role": "user", "content": user}]}
    body.update(merged)
    _apply_provider_routing(body, prov)
    _apply_cache_affinity(body, prov, role)
    _apply_reasoning_effort(body, prov, role)
    _apply_json_mode(body, prov, model, json_mode, json_schema)

    async with httpx.AsyncClient(timeout=_httpx_timeout()) as client:
        if streaming:
            try:
                out = await _sse_openai_async(base + "/chat/completions", _headers(prov), dict(body), guarded(), client, role=role, model=model)
            except LLMError as e:
                if e.status_code == 400:
                    # Staged, as on the sync paths: response_format first so a
                    # rejection it caused cannot strip the reasoning controls.
                    recovered = False
                    if "response_format" in body:
                        b1 = dict(body)
                        b1.pop("response_format", None)
                        try:
                            out = await _sse_openai_async(base + "/chat/completions", _headers(prov), b1, guarded(), client, role=role, model=model)
                            _note_json_object_rejected(prov, model)
                            recovered = True
                        except LLMError as e1:
                            if e1.status_code != 400:
                                raise
                    if not recovered:
                        b2 = dict(body)
                        b2.pop("response_format", None)
                        b2 = _strip_extended(b2)
                        out = await _sse_openai_async(base + "/chat/completions", _headers(prov), b2, guarded(), client, role=role, model=model)
                else:
                    raise
            # Same placeholder-skeleton guard as the sync streaming path:
            # a model that "honours" response_format=json_object by
            # streaming an all-"..." skeleton would send that skeleton to
            # the player as prose. Retry once without json_mode -- still
            # streaming, so the live UI keeps receiving tokens.
            if json_mode and _is_placeholder_json(out):
                retry_body = dict(body)
                retry_body.pop("response_format", None)
                out = await _sse_openai_async(base + "/chat/completions", _headers(prov), retry_body, guarded(), client, role=role, model=model)
            return out
        _t0 = time.time()
        r = await client.post(base + "/chat/completions", headers=_headers(prov), json=body)
        if r.status_code == 400:
            if "response_format" in body:
                b1 = dict(body)
                b1.pop("response_format", None)
                r = await client.post(base + "/chat/completions", headers=_headers(prov), json=b1)
                if r.status_code < 400:
                    _note_json_object_rejected(prov, model)
            if r.status_code == 400:
                b2 = _strip_extended(dict(body))
                b2.pop("response_format", None)
                r = await client.post(base + "/chat/completions", headers=_headers(prov), json=b2)
        if r.status_code >= 400:
            raise LLMError(f"{prov['name']}: HTTP {r.status_code}: {r.text[:300]}", r.status_code, r.status_code in DEFAULT_RETRY.retryable_status)
        parsed = r.json()
        _log_usage(role, model, _t0, parsed.get("usage"),
                   served=parsed.get("model"))
        _capture_reasoning((parsed.get("choices") or [{}])[0].get("message"))
        _capture_choice_finish(parsed)
        return _message_content(parsed, prov["name"], model)

async def _sse_openai_async(url, headers, body, sink, client, role=None, model=None):
    body["stream"] = True
    # Without this a streamed response reports no token counts at all -- see
    # the matching comment in _sse_openai.
    body["stream_options"] = {"include_usage": True}
    text, reasoning = "", ""
    usage = None
    served = ""
    t0 = time.time()
    _check_cancel()
    async with client.stream("POST", url, headers=headers, json=body) as r:
        if r.status_code >= 400:
            body_text = await r.aread()
            raise LLMError(f"HTTP {r.status_code}: {body_text.decode()[:300]}", r.status_code, r.status_code in DEFAULT_RETRY.retryable_status)
        async for raw in r.aiter_lines():
            _check_cancel()
            if not raw:
                continue
            line = raw
            if line.startswith("data: "):
                line = line[6:]
            if line.strip() == "[DONE]":
                break
            try:
                j = json.loads(line)
            except Exception:
                continue
            # Some OpenAI-compatible backends emit an {"error": {...}} chunk
            # mid-stream (e.g. an overload 30s in). Ignoring it silently
            # returned the truncated prefix as a completed response, which for
            # a JSON step could pass validation and commit truncated. Surface
            # it as a retryable failure instead -- matches _sse_openai.
            if isinstance(j, dict) and j.get("error"):
                err = j["error"]
                msg = err.get("message") if isinstance(err, dict) else str(err)
                raise LLMError(f"provider stream error: {msg}",
                               _stream_error_status(err), True)
            if j.get("usage"):
                usage = j["usage"]
            _capture_choice_finish(j)
            # The model of record rides every chunk of an OpenAI-compatible
            # stream, and a router alias is not a model -- see
            # `_note_served_model`. The streaming branch is the one the
            # pipeline actually runs, so reading it only in the non-streaming
            # path would leave substitution invisible exactly where it counts.
            if not served:
                served = str(j.get("model") or "").strip()
            _delta = (j.get("choices") or [{}])[0].get("delta", {})
            _r = _delta.get("reasoning") or _delta.get("reasoning_content")
            if isinstance(_r, str) and _r:
                reasoning += _r
            d = _delta.get("content")
            if d:
                text += d
                if sink:
                    sink(d)
    if role:
        _log_usage(role, model, t0, usage, served=served,
                   kind="stream")
    try:
        last_reasoning.set(reasoning or None)
    except Exception:
        pass
    return text

async def _sse_anthropic_async(base, headers, body, sink, client, role=None, model=None):
    body["stream"] = True
    text = ""
    usage = None
    served = ""
    t0 = time.time()
    _check_cancel()
    async with client.stream("POST", base + "/v1/messages", headers=headers, json=body) as r:
        if r.status_code >= 400:
            body_text = await r.aread()
            raise LLMError(f"HTTP {r.status_code}: {body_text.decode()[:300]}", r.status_code, r.status_code in DEFAULT_RETRY.retryable_status)
        async for raw in r.aiter_lines():
            _check_cancel()
            if not raw:
                continue
            line = raw
            if line.startswith("data: "):
                line = line[6:]
            try:
                j = json.loads(line)
            except Exception:
                continue
            # Anthropic's documented mid-stream error event (overloaded_error,
            # etc.) -- surface as retryable rather than silently truncating.
            # Matches _sse_anthropic.
            if j.get("type") == "error":
                err = j.get("error") or {}
                msg = err.get("message") if isinstance(err, dict) else str(err)
                raise LLMError(f"provider stream error: {msg or 'overloaded'}",
                               _stream_error_status(err), True)
            if j.get("type") == "message_start":
                message = j.get("message") or {}
                usage = _merge_usage(usage, message.get("usage"))
                if not served:
                    served = str(message.get("model") or "").strip()
            elif j.get("type") == "message_delta":
                usage = _merge_usage(usage, j.get("usage"))
                stop = (j.get("delta") or {}).get("stop_reason")
                if stop:
                    _capture_finish_reason(stop)
            if j.get("type") == "content_block_delta":
                d = j.get("delta", {}).get("text")
                if d:
                    text += d
                    if sink:
                        sink(d)
    if role:
        _log_usage(role, model, t0, usage, served=served,
                   kind="stream")
    return text

def list_openrouter_endpoints(prov, model):
    """The upstream providers currently serving one OpenRouter model.

    A model id like `anthropic/claude-opus-4-6` is fronted by several
    upstreams whose quality and prompt-retention policy differ, and their
    slugs are not guessable -- this is what lets a picker offer the real set
    instead of asking someone to type one from memory.
    """
    if _prov_field(prov, "kind") != "openrouter":
        return []
    slug = str(model or "").strip()
    if not slug:
        return []
    base = prov["base_url"].rstrip("/")
    r = _session().get(f"{base}/models/{slug}/endpoints",
                       headers=_headers(prov), timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    data = (r.json() or {}).get("data") or {}
    out = []
    for ep in data.get("endpoints") or []:
        if not isinstance(ep, dict):
            continue
        # `tag` is the slug the routing block expects; `name` is for humans.
        slug_name = ep.get("tag") or ep.get("provider_name") or ep.get("name")
        if not slug_name:
            continue
        policy = ep.get("data_policy") or {}
        out.append({
            "slug": slug_name,
            "name": ep.get("provider_name") or ep.get("name") or slug_name,
            "context": ep.get("context_length"),
            "quantization": ep.get("quantization"),
            # Surfaced so the privacy decision can be made in the picker
            # rather than by cross-referencing OpenRouter's own docs.
            "trains_on_data": bool(policy.get("training")),
            "retains_prompts": bool(policy.get("retains_prompts")),
        })
    return out

def list_models(prov):
    base = prov["base_url"].rstrip("/")
    if prov["kind"] == "anthropic":
        r = _session().get(base + "/v1/models", timeout=REQUEST_TIMEOUT, headers={"x-api-key": prov["api_key"] or "", "anthropic-version": "2023-06-01"})
        r.raise_for_status()
        return [{"id": m["id"], "badge": "pay-per-use", "included": False} for m in r.json().get("data", [])]
    url = base + "/models" + ("?detailed=true" if prov["kind"] == "nanogpt" else "")
    r = _session().get(url, headers=_headers(prov), timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    j = r.json()
    data = (
        j if isinstance(j, list)
        else j.get("data", []) if isinstance(j, dict)
        else []
    )
    out = []
    def zero(x):
        try:
            return float(x) == 0.0
        except Exception:
            return False
    for m in data:
        if not isinstance(m, dict):
            m = {"id": str(m)}
        mid = m.get("id") or m.get("name") or ""
        pricing = m.get("pricing") or {}
        included, badge = False, "pay-per-use"
        if prov["kind"] == "openrouter" and (mid.endswith(":free") or (zero(pricing.get("prompt")) and zero(pricing.get("completion")))):
            included, badge = True, "free"
        # nanogpt reports subscription eligibility as a nested object,
        # e.g. {"included": false, "note": "Not included in subscription"}.
        # A dict is truthy regardless of its "included" value, so checking
        # `m.get("subscription")` alone (as this used to) marked every
        # model "included in subscription" as long as the key existed at
        # all — including models that 403 with model_not_included.
        subscription = m.get("subscription")
        if isinstance(subscription, dict):
            if subscription.get("included"):
                included, badge = True, "included in subscription"
        elif subscription:
            included, badge = True, "included in subscription"
        for k in ("included_in_subscription", "in_subscription", "subscriptionIncluded"):
            if m.get(k, pricing.get(k)):
                included, badge = True, "included in subscription"
        if m.get("free") is True:
            included, badge = True, "free"
        if prov["kind"] in ("ollama", "koboldcpp"):
            included, badge = True, "local"
        out.append({"id": mid, "badge": badge, "included": included, "ctx": m.get("context_length") or m.get("context_window")})
    out.sort(key=lambda x: x["id"])
    return out

# ---- Embeddings ----

def cheap_embed(text, dim=256):
    v = np.zeros(dim, dtype=np.float32)
    t = " " + (text or "").lower() + " "
    for n in (3, 4):
        for i in range(max(len(t) - n, 0)):
            h = zlib.crc32(t[i : i + n].encode("utf-8", "ignore"))
            v[h % dim] += 1.0 if (h >> 16) & 1 else -1.0
    nrm = np.linalg.norm(v)
    return v / nrm if nrm > 0 else v

def embedding_model_key() -> str:
    try:
        prov, model, _ = resolve_role("embeddings")
        return f"{prov['kind']}:{prov['id']}:{model}"
    except Exception:
        return "cheap:crc32:256"

# ---- Embedding request pacing ----
#
# ADAPTIVE, and deliberately not a configured number. The ceiling belongs to
# the provider and model, not to the engine: the live OpenRouter/Perplexity
# embeddings route was measured on 2026-08-11 to refuse a burst of 4 and to
# refuse 3 of 8 SEQUENTIAL requests sent at ~2.5/s, while a local embedder
# does tens per second and must not be slowed by a number chosen for someone
# else's provider. So the engine starts unpaced, learns the ceiling from the
# provider's own 429s, and forgets it again once the pressure lifts.
#
# Why pacing rather than only retrying: the retry above already survives a
# rate limit, but each 429 still costs a round trip and, past the retry
# budget, strands whatever was being written on the crc32 fallback under its
# own stamp -- permanent until somebody pays for a rebuild. Waiting 400ms is
# cheaper than that on every axis, and nothing is watching this path.
#
# The whole state is process-local and resets on restart, which is correct: a
# ceiling learned last week is not evidence about this week's provider.
_EMBED_PACE_LOCK = threading.Lock()
_EMBED_PACE = {"interval": 0.0, "next_at": 0.0}
# First penalty. ~2 requests/second, just under the measured ceiling.
_EMBED_PACE_FIRST = 0.5
# Ceiling on the ceiling: past this the provider is not rate limiting, it is
# broken, and the fallback is the right answer rather than a longer queue.
_EMBED_PACE_MAX = 2.0
# Below this, pacing is indistinguishable from not pacing -- drop it entirely
# so a provider that had one bad minute does not pay for it all session.
_EMBED_PACE_FLOOR = 0.05
# Slow decay: a sawtooth that re-probes the ceiling every few calls would
# spend a 429 to learn what it already knew.
_EMBED_PACE_DECAY = 0.98
# HOW FAR THE QUEUE MAY REACH, and the reason it needs a bound at all: each
# waiter books the next free slot, so N callers book N intervals and the
# horizon grows without limit. A rebuild pass or a wide fan-out could
# therefore queue itself minutes into the future while every one of those
# waiters sits in `time.sleep` -- which is not a slow engine, it is a hung
# one, and it is exactly what the first version of this did to the test
# suite (65s to over 10 minutes). Past this horizon the arrival rate is
# simply higher than the ceiling can serve, and no amount of further waiting
# fixes that: let the request go, and let the 429/retry/fallback ladder
# below be the release valve it already is.
_EMBED_PACE_MAX_WAIT = 3.0


def _embed_pace_wait():
    """Take a slot in the queue, then wait for it.

    The slot is computed under the lock and slept OUTSIDE it, so N concurrent
    callers get N spaced departure times and then wait in parallel. Holding
    the lock across the sleep would serialize them into the same queue by
    accident and make the wait quadratic.
    """
    with _EMBED_PACE_LOCK:
        interval = _EMBED_PACE["interval"]
        if interval <= 0:
            return
        now = time.monotonic()
        slot = max(now, _EMBED_PACE["next_at"])
        if slot - now > _EMBED_PACE_MAX_WAIT:
            # The queue already reaches past the horizon. Go now and do not
            # extend it further -- see _EMBED_PACE_MAX_WAIT.
            return
        _EMBED_PACE["next_at"] = slot + interval
    delay = slot - time.monotonic()
    if delay > 0:
        time.sleep(delay)


def _embed_pace_penalize():
    """A rate limit is the provider telling us its ceiling. Believe it."""
    with _EMBED_PACE_LOCK:
        before = _EMBED_PACE["interval"]
        _EMBED_PACE["interval"] = min(
            max(before * 2, _EMBED_PACE_FIRST), _EMBED_PACE_MAX)
        after = _EMBED_PACE["interval"]
    if not before:
        _logger.warning(
            "embeddings: rate limited by the provider; pacing requests at "
            "%.2fs apart from now on, easing off again once they stop. This "
            "is a ceiling on the configured model, not on this engine.",
            after)


def _embed_pace_relax():
    """Ease back toward unpaced after a clean call."""
    with _EMBED_PACE_LOCK:
        if _EMBED_PACE["interval"] <= 0:
            return
        eased = _EMBED_PACE["interval"] * _EMBED_PACE_DECAY
        _EMBED_PACE["interval"] = 0.0 if eased < _EMBED_PACE_FLOOR else eased


def _is_rate_limit(exc) -> bool:
    return isinstance(exc, LLMError) and exc.status_code == 429


def _embed_request(texts) -> EmbeddingBatch:
    """One embeddings round trip. Raises; the retry loop above decides."""
    prov, model, _ = resolve_role("embeddings")
    base = prov["base_url"].rstrip("/")
    _t0 = time.time()
    r = _post_abortable(base + "/embeddings", headers=_headers(prov),
                        json={"model": model, "input": texts})
    if r.status_code >= 400:
        # The BODY carries the reason; `raise_for_status` discards it and
        # leaves only "400 Client Error", which cannot tell a wrong key
        # from a wrong model. Measured live: selecting a chat model for
        # the embeddings role returns "Model inception/mercury-2 does not
        # exist" -- the one sentence that explains why recall silently
        # stopped improving. It reaches the settings panel from here.
        #
        # LLMError rather than RuntimeError so `_should_retry` can read the
        # STATUS: a 429 or a 502 is worth asking again, and "that model does
        # not exist" is worth asking again never. Its str() is the same
        # sentence it always was, which is what the settings panel renders.
        raise LLMError("%s %s: %s" % (r.status_code, base + "/embeddings",
                                      (r.text or "").strip()[:300]),
                       r.status_code,
                       r.status_code in DEFAULT_RETRY.retryable_status)
    r.raise_for_status()
    parsed = r.json()
    # The batch ledger entry: one round trip, however many texts it carried.
    # An embedding call on the turn path is precisely the spend the per-call
    # ledger exists to make attributable -- "the slow commit was embeddings"
    # has already been guessed wrongly once against a stage that never made
    # an embedding call at all.
    record_llm_call({
        "role": "embeddings",
        "requested": model,
        "served": str(parsed.get("model") or "").strip() or model,
        "in": _int((parsed.get("usage") or {}).get("prompt_tokens")
                   if isinstance(parsed.get("usage"), dict) else 0),
        "out": 0,
        "cached": 0,
        "duration": round(time.time() - _t0, 3),
        "kind": "embedding",
        "texts": len(texts),
    })
    data = parsed.get("data") or []
    data = sorted(data, key=lambda item: item.get("index", 0))
    if len(data) != len(texts):
        raise RuntimeError("Embedding provider returned an unexpected vector count")
    vectors = []
    dimensions = None
    for item in data:
        vector = np.asarray(item["embedding"], dtype=np.float32)
        if dimensions is None:
            dimensions = len(vector)
        elif len(vector) != dimensions:
            raise RuntimeError("Embedding provider returned mixed dimensions")
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        vectors.append(vector)
    return EmbeddingBatch(vectors=vectors, model_key=f"{prov['kind']}:{prov['id']}:{model}", dimensions=dimensions or 0, fallback=False)


# Rate limit on the line below, per distinct provider error. An outage lasting
# a whole session must say so, and must not say so ten thousand times.
_EMBED_FALLBACK_SAID: dict[str, float] = {}
_EMBED_FALLBACK_QUIET = 60.0


def _note_embedding_fallback(exc, texts):
    """Say out loud that a vector was computed by the crc32 hash.

    THE SILENCE WAS THE BUG. `embed_texts_meta` degrades on any error, and a
    degraded WRITE is not transient -- the row keeps the fallback stamp until
    somebody pays for a rebuild, and the first anyone hears of it is a story
    offering to rebuild memories it wrote ninety seconds ago. Reported live,
    2026-08-11: a quick start whose greeting seeds were stranded on the turn
    that minted them, with nothing in any log to say which call had failed or
    why. Degrading is the right behaviour; doing it quietly is not.

    Not raised, because a memory is worth more than its vector and the bank
    already records which model wrote each row -- the rebuild lane finds these
    rows on its own. This is the trace that says where they came from.
    """
    if embedding_model_key() == "cheap:crc32:256":
        return  # No provider configured: the hash IS the engine's embedding.
    reason = str(exc or "")[:300]
    now = time.time()
    last = _EMBED_FALLBACK_SAID.get(reason, 0.0)
    if now - last < _EMBED_FALLBACK_QUIET:
        return
    _EMBED_FALLBACK_SAID[reason] = now
    _logger.warning(
        "embeddings: fell back to the crc32 hash for %d text(s) -- the "
        "configured provider (%s) failed: %s. Anything WRITTEN with these "
        "vectors is stamped cheap:crc32:256 and reachable by keyword only "
        "until it is rebuilt.",
        len(texts), embedding_model_key(), reason,
    )


# ---- Remembering an unreachable endpoint ----
#
# The retry ladder below is sized for a provider that ANSWERS -- a 429, a 502,
# a dropped stream. Against an endpoint that never completes a TCP connect it
# degenerates into four 30s connect timeouts plus jittered backoff, ~126s, and
# it was being paid IN FULL twice per turn: measured live 2026-08-28 (chat 95,
# turn idx 905, wall 313.1s), one ladder inside interaction_loop's
# memory-context build and one inside commit's prepare_memories_batch --
# 252.4s, 81% of the turn, all spent re-proving a fact the same process had
# finished proving seventy seconds earlier. `_EMBED_FALLBACK_SAID` rate-limits
# the log line, not the proof.
#
# So the proof is kept. When a FULL ladder ends in a connect-level failure --
# the request never reached a server, as opposed to a status a server chose to
# send -- the configured (provider, model) key is remembered unreachable, and
# later pipeline calls degrade immediately: byte-for-byte the batch the ladder
# would have returned two minutes later, because `cheap_embed` depends only on
# the text. Recovery is watched for OFF the turn path -- one background probe
# attempt per `_EMBED_DEAD_RETRY_EVERY`, nobody waiting on it. The
# `retry=None` measurement callers bypass the memory (a probe that answers
# from memory cannot tell the host their endpoint came back), and a
# successful request from ANY caller clears it.
#
# Process-local and reset on restart, like the pacer above and for the same
# reason: deadness observed last session is not evidence about this one.
_EMBED_DEAD_LOCK = threading.Lock()
_EMBED_DEAD = {"key": None, "reason": "", "probe_at": 0.0, "probing": False}
# How long remembered deadness stands before the next background probe. The
# inline ladder this replaces measured ~126s per call; the probe is one
# connect attempt (<=30s against a dead host) that nobody waits on. It also
# bounds how long a RECOVERED endpoint keeps being answered by the hash:
# rows written in that window carry the crc32 stamp the rebuild lane already
# hunts for, exactly like rows written during the outage itself.
_EMBED_DEAD_RETRY_EVERY = 300.0


def _is_connect_dead(exc) -> bool:
    """True when the request never reached a server at all.

    `requests` puts refused connections, DNS failures and connect timeouts
    under ConnectionError (ConnectTimeout subclasses it). ReadTimeout does
    NOT -- a host that accepted the connection and then stalled is alive,
    and an HTTP status of any kind is a server answering.
    """
    return isinstance(exc, _req_exc.ConnectionError)


def _embed_dead_remember(exc):
    """Keep what an exhausted ladder just proved about the endpoint."""
    if not _is_connect_dead(exc):
        return
    key = embedding_model_key()
    if key == "cheap:crc32:256":
        return  # No provider configured; there is no endpoint to be dead.
    with _EMBED_DEAD_LOCK:
        _EMBED_DEAD.update(
            key=key, reason=str(exc)[:300], probing=False,
            probe_at=time.monotonic() + _EMBED_DEAD_RETRY_EVERY)


def _embed_dead_forget():
    with _EMBED_DEAD_LOCK:
        _EMBED_DEAD.update(key=None, reason="", probe_at=0.0, probing=False)


def _embed_dead_probe(key):
    """One attempt, off anyone's wall clock, to see whether it came back."""
    ok = False
    try:
        _embed_request(["embeddings recovery probe"])
        ok = True
    except Exception:
        pass
    with _EMBED_DEAD_LOCK:
        _EMBED_DEAD["probing"] = False
        # Cleared only for the key that was probed: a host who reconfigured
        # the role mid-cooldown already cleared it by changing the key.
        if ok and _EMBED_DEAD["key"] == key:
            _EMBED_DEAD.update(key=None, reason="", probe_at=0.0)


def _embed_dead_reason():
    """The remembered failure if the CURRENT key is known unreachable.

    Returns None when nothing is remembered or the host has since pointed
    the role somewhere else. When the memory is due for a re-check, starts
    the background probe -- and keeps answering from memory meanwhile, so
    the probe's connect timeout lands on no caller's wall clock.
    """
    with _EMBED_DEAD_LOCK:
        remembered = _EMBED_DEAD["key"]
    if remembered is None:
        return None
    # Outside the lock: resolving the role reads settings.
    key = embedding_model_key()
    with _EMBED_DEAD_LOCK:
        if _EMBED_DEAD["key"] != key:
            return None
        reason = _EMBED_DEAD["reason"]
        now = time.monotonic()
        if now >= _EMBED_DEAD["probe_at"] and not _EMBED_DEAD["probing"]:
            _EMBED_DEAD["probing"] = True
            _EMBED_DEAD["probe_at"] = now + _EMBED_DEAD_RETRY_EVERY
            threading.Thread(target=_embed_dead_probe, args=(key,),
                             name="embed-dead-probe", daemon=True).start()
    return reason


# ---- Coalescing concurrent embedding requests ----
#
# The ceiling that keeps refusing us counts REQUESTS, not tokens: the measured
# OpenRouter/Perplexity route serves a bucket of ~3 refilling at 1-2/s and does
# not care whether a request carries one text or forty. Meanwhile the engine
# fans out -- parallel character steps each embed their own retrieval query --
# so the one thing that reliably lowers the pressure is asking fewer times.
#
# SAFE BY CONSTRUCTION, and verified rather than assumed (2026-08-11): the same
# document embedded alone and embedded inside a batch of three came back
# BITWISE identical, at both first and last position. A text's vector does not
# depend on its companions, so nothing here can move a ranking. The engine was
# already betting on this in one direction -- writes go out batched while
# queries go out one at a time, and recall would already be broken otherwise.
#
# NO ARTIFICIAL WINDOW. A timed "wait a few ms for companions" would tax every
# solo call to help the crowded ones. Instead callers that arrive while a
# request is in flight queue behind it, and the next request takes whoever
# accumulated. Under no contention this is exactly the old behaviour with one
# lock acquisition added; under contention it coalesces for free, and the
# busier the fan-out the better it batches.
_COALESCE_LOCK = threading.Lock()
_COALESCE_QUEUE: list = []
_COALESCE_INFLIGHT = False
# Caps on one grouped request. A group larger than this splits rather than
# growing a body the provider may reject outright.
_COALESCE_MAX_TEXTS = 64
_COALESCE_MAX_CHARS = 120_000
# A follower whose leader never returns serves itself rather than hanging. The
# leader always returns in practice -- `_embed_with_retry` degrades instead of
# raising -- so this is a deadlock backstop, not a code path with a plan.
_COALESCE_WAIT_CEILING = 600.0
# Visible arithmetic for "did this help": callers vs the requests they cost.
_EMBED_STATS = {"callers": 0, "groups": 0, "texts_in": 0, "texts_sent": 0}


class _EmbedWaiter:
    __slots__ = ("texts", "done", "result")

    def __init__(self, texts):
        self.texts = texts
        self.done = threading.Event()
        self.result = None


def _take_embed_group_locked():
    """The queued callers one request may serve. Caller holds the lock."""
    group, n_texts, n_chars = [], 0, 0
    while _COALESCE_QUEUE:
        waiter = _COALESCE_QUEUE[0]
        texts = len(waiter.texts)
        chars = sum(len(t) for t in waiter.texts)
        # `group and` -- a single caller bigger than the cap still goes, alone,
        # because refusing it would strand it forever.
        if group and (n_texts + texts > _COALESCE_MAX_TEXTS
                      or n_chars + chars > _COALESCE_MAX_CHARS):
            break
        _COALESCE_QUEUE.pop(0)
        group.append(waiter)
        n_texts += texts
        n_chars += chars
    return group


def _report_embed_coalescing(callers, texts_sent):
    """Say what the coalescing saved, on the groups where it saved anything.

    `_EMBED_STATS` is described in its own comment as "visible arithmetic for
    did this help" and was visible to nothing: four counters incremented on
    every call with no reader anywhere but a test. A number nobody can read is
    not a measurement -- and this one answers a question that decides whether
    the queue, the leader election and the deadlock backstop above are earning
    their complexity.

    Reported only when a group actually merged callers, because a group of one
    is the ordinary case and would be a log line per embedding. The cumulative
    totals ride along so the ratio is readable without adding up the lines.
    """
    if callers < 2:
        return
    stats = dict(_EMBED_STATS)
    _logger.info(
        "embed_coalesced callers=%d texts_sent=%d "
        "total_callers=%d total_groups=%d total_texts_in=%d "
        "total_texts_sent=%d",
        callers, texts_sent, stats["callers"], stats["groups"],
        stats["texts_in"], stats["texts_sent"])


def _serve_embed_group(group, config):
    """One request for the whole group, each caller handed back its own."""
    order, position = [], {}
    for waiter in group:
        for text in waiter.texts:
            if text not in position:
                position[text] = len(order)
                order.append(text)
    got = _embed_with_retry(order, config)
    _EMBED_STATS["groups"] += 1
    _EMBED_STATS["texts_sent"] += len(order)
    _report_embed_coalescing(len(group), len(order))
    for waiter in group:
        # Routed by position in BOTH outcomes, including the fallback, so a
        # caller can never receive another caller's vector. The dedupe above
        # means two callers asking for the same text share one vector, which
        # is what "the vector does not depend on its companions" licenses.
        waiter.result = EmbeddingBatch(
            vectors=[got.vectors[position[t]] for t in waiter.texts],
            model_key=got.model_key, dimensions=got.dimensions,
            fallback=got.fallback, error=got.error)
        waiter.done.set()


def _coalesced_embed(texts, config) -> EmbeddingBatch:
    global _COALESCE_INFLIGHT
    waiter = _EmbedWaiter(texts)
    with _COALESCE_LOCK:
        _EMBED_STATS["callers"] += 1
        _EMBED_STATS["texts_in"] += len(texts)
        _COALESCE_QUEUE.append(waiter)
        leader = not _COALESCE_INFLIGHT
        if leader:
            _COALESCE_INFLIGHT = True
    if not leader:
        waiter.done.wait(_COALESCE_WAIT_CEILING)
        with _COALESCE_LOCK:
            if waiter in _COALESCE_QUEUE:
                _COALESCE_QUEUE.remove(waiter)
        # WOKEN IS NOT THE SAME AS SERVED. The drain below wakes whoever is
        # still queued without a result to give them, and the ceiling expires
        # with no wake at all -- so the only thing that settles this caller is
        # whether it is holding vectors, never whether its event fired.
        return waiter.result if waiter.result is not None \
            else _embed_with_retry(texts, config)
    try:
        while True:
            with _COALESCE_LOCK:
                group = _take_embed_group_locked()
                if not group:
                    break
            _serve_embed_group(group, config)
    finally:
        # LEADERSHIP IS HELD UNTIL THE DRAIN, not dropped when the queue first
        # reads empty: releasing it earlier leaves a window in which a caller
        # arriving before this block runs elects itself leader, and is then
        # drained by the outgoing one -- so its own request is woken, empty,
        # by a leader that never served it.
        with _COALESCE_LOCK:
            _COALESCE_INFLIGHT = False
            # Never leave a queued caller without a leader: whoever is still
            # waiting is woken to serve itself rather than sleep to the
            # ceiling. Only reachable if `_serve_embed_group` raised, which it
            # is not supposed to be able to do.
            stranded, _COALESCE_QUEUE[:] = list(_COALESCE_QUEUE), []
        for other in stranded:
            other.done.set()
    # A leader can be drained by nothing but itself, yet its own group is
    # served by the same code every other caller depends on: hold the same
    # floor rather than trust that.
    return waiter.result if waiter.result is not None \
        else _embed_with_retry(texts, config)


def _embed_with_retry(texts, config, *, consult_memory=True) -> EmbeddingBatch:
    """Pace, ask, retry, and degrade. Never raises.

    `consult_memory=False` for the `retry=None` measurement callers: they
    exist to observe the endpoint as it is NOW, and their single attempt is
    cheap. Everyone else accepts the remembered verdict -- the batch is
    identical to the one the exhausted ladder would return, minus the wait.
    """
    if consult_memory:
        dead = _embed_dead_reason()
        if dead is not None:
            reason = "endpoint remembered unreachable: " + dead
            _note_embedding_fallback(reason, texts)
            return EmbeddingBatch(
                vectors=[cheap_embed(text) for text in texts],
                model_key="cheap:crc32:256", dimensions=256,
                fallback=True, error=reason)
    attempt = 0
    while True:
        try:
            _embed_pace_wait()
            got = _embed_request(texts)
            _embed_pace_relax()
            if _EMBED_DEAD["key"] is not None:
                _embed_dead_forget()
            return got
        except Exception as exc:
            if _is_rate_limit(exc):
                _embed_pace_penalize()
            if _should_retry(exc, attempt, config):
                time.sleep(config.delay_for(attempt))
                attempt += 1
                continue
            # Only a ladder that had retries to spend has PROVED anything
            # worth remembering; a single declined attempt has not.
            if config.max_retries > 0:
                _embed_dead_remember(exc)
            _note_embedding_fallback(exc, texts)
            vectors = [cheap_embed(text) for text in texts]
            return EmbeddingBatch(vectors=vectors, model_key="cheap:crc32:256",
                                  dimensions=256, fallback=True, error=str(exc))


def embed_texts_meta(texts, *, retry: Optional[RetryConfig] = DEFAULT_RETRY) -> EmbeddingBatch:
    """Vectors for `texts`, with the model that made them.

    RETRIED on the same terms as a chat call, because the consequence of a
    lost embedding is worse than a lost completion: a completion that fails
    is retried by the stage that wanted it, while an embedding that fails is
    silently replaced by a hash and PERSISTED under its own stamp.

    `retry=None` for a caller that is asking rather than writing -- the bank
    status probe runs while somebody is waiting for a chat to open, and it
    must report a degraded provider promptly instead of spending seven
    seconds proving it.
    """
    texts = [str(t or "") for t in texts]
    if not texts:
        return EmbeddingBatch(vectors=[], model_key=embedding_model_key(), dimensions=0)
    config = retry or RetryConfig(max_retries=0)
    if retry is None:
        # A MEASUREMENT, not traffic. The bank probe runs while a chat is
        # opening; queueing it behind somebody else's turn would make it
        # report on a moment that has passed -- and answering it from the
        # dead-endpoint memory would make it report on one that may have
        # passed too, so it alone asks the wire every time.
        return _embed_with_retry(texts, config, consult_memory=False)
    return _coalesced_embed(texts, config)

def embed_texts(texts):
    return embed_texts_meta(texts).vectors
