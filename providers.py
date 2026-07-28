# providers.py
"""LLM providers, streaming, retries, cancellation, and embeddings."""

import json, zlib, asyncio, threading, time, re, os
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

from db import q, get_setting

token_sink = contextvars.ContextVar("token_sink", default=None)
generation_event_sink = contextvars.ContextVar(
    "generation_event_sink",
    default=None,
)
cancel_event = contextvars.ContextVar("cancel_event", default=None)

REQUEST_TIMEOUT = (30, 300)

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
    read=300.0,
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


def _request_timeout():
    """(connect, read) for `requests`, honoring an active override."""
    override = read_timeout_override.get()
    if override is None:
        return REQUEST_TIMEOUT
    return (REQUEST_TIMEOUT[0], override)


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
        
class DegenerateOutput(LLMError):
    def __init__(self, reason: str):
        super().__init__(
            f"Degenerate model output: {reason}",
            status_code=0,
            retryable=True,
        )
        self.reason = reason

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

def _generation_notice(event: dict):
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

def _anthropic_system(system):
    """The `system` field for an Anthropic request: a cache-marked content
    block when caching is on and there is a prompt to cache, else the plain
    string (Anthropic accepts either form)."""
    if PROMPT_CACHE_ENABLED and system:
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


def _cache_passthrough_allowed(prov):
    """Whether this provider may receive a cache-marked system message.

    `prompt_cache_allow` opts additional providers in by name or kind;
    `prompt_cache_deny` opts any provider back out and wins over both the
    allowlist and the built-in kinds. FICTION_ENGINE_PROMPT_CACHE=0 remains the
    all-providers kill switch.
    """
    kind = str(_prov_field(prov, "kind") or "").strip().casefold()
    name = str(_prov_field(prov, "name") or "").strip().casefold()
    if {kind, name} & _setting_name_set("prompt_cache_deny"):
        return False
    if kind in _CACHE_PASSTHROUGH_KINDS:
        return True
    return bool({kind, name} & _setting_name_set("prompt_cache_allow"))


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
    else the env override, else "" (unset). Mirrors agent-model role fallback."""
    efforts = reasoning_efforts()
    if role in efforts:
        return efforts[role]
    if "default" in efforts:
        return efforts["default"]
    return _coerce_reasoning_effort(
        os.environ.get("FICTION_ENGINE_REASONING_EFFORT"))


def _apply_reasoning_effort(body, prov, role):
    """Attach this role's reasoning effort to an OpenAI-compatible request.
    OpenRouter takes `reasoning: {effort}` (and `{enabled: false}` to disable);
    every other OpenAI-style backend takes the flat `reasoning_effort` ('none'
    to disable). Nothing is added when the role is unset."""
    effort = reasoning_effort_for(role)
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


def _clamp_max_tokens(max_tokens):
    """Cap a requested output budget at the configured ceiling. Only ever
    lowers -- a caller asking for less (a 1000-token utility call) keeps its
    own smaller budget."""
    ceiling = max_output_tokens()
    try:
        requested = int(max_tokens)
    except (TypeError, ValueError):
        return ceiling
    return max(1, min(requested, ceiling))

ROLES = [
    "default",
    "director",
    "perception",
    "character_bg",
    "character_mid",
    "character_major",
    "narrator",
    "mapping",
    "utility",
    "embeddings",
    # Writes an image prompt from spatial data (backdrops.py). OPTIONAL and
    # deliberately out of band: it never runs inside the turn pipeline, so a
    # slow or failed image prompt cannot delay or break a beat. When no model
    # is configured for it, backdrops fall back to a deterministic template.
    "backdrop_prompt",
]

# Image generation is a different API surface from chat completion, so it gets
# its own setting rather than an entry in agent_models: {provider, model}.
# nano-gpt exposes 201 image models at /api/models/image and an
# OpenAI-compatible endpoint at /v1/images/generations; its /v1/models list
# contains no image-output models at all, which is why this cannot simply
# reuse the chat role plumbing.
IMAGE_ENDPOINT = "/images/generations"


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

@dataclass
class RetryConfig:
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    retryable_status: frozenset = frozenset({429, 500, 502, 503, 504})

    def delay_for(self, attempt: int) -> float:
        delay = min(self.base_delay * (2 ** attempt), self.max_delay)
        return delay

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

def resolve_role_candidates(role):
    models = agent_models()
    primary = models.get(role) or models.get("default")

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
    for k in ("top_k", "repetition_penalty", "min_p", "top_a",
              "reasoning_effort", "reasoning"):
        body.pop(k, None)
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
    text = ""
    usage = None
    t0 = time.time()
    _check_cancel()
    with _session().post(url, headers=headers, json=body, stream=True, timeout=_request_timeout()) as r:
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
                raise LLMError(f"provider stream error: {msg}", 0, True)
            if j.get("usage"):
                usage = j["usage"]
            d = (j.get("choices") or [{}])[0].get("delta", {}).get("content")
            if d:
                text += d
                sink(d)
    if role:
        _log_usage(role, model, t0, usage)
    return text

def _sse_anthropic(base, headers, body, sink, role=None, model=None):
    body["stream"] = True
    text = ""
    # Anthropic splits usage across two events: input and cache counts arrive
    # on message_start, the final output count on message_delta. Neither alone
    # is the whole picture, so both are folded together.
    usage = None
    t0 = time.time()
    _check_cancel()
    with _session().post(base + "/v1/messages", headers=headers, json=body, stream=True, timeout=_request_timeout()) as r:
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
                raise LLMError(f"provider stream error: {msg or 'overloaded'}", 0, True)
            if j.get("type") == "message_start":
                usage = _merge_usage(
                    usage, (j.get("message") or {}).get("usage"))
            elif j.get("type") == "message_delta":
                usage = _merge_usage(usage, j.get("usage"))
            if j.get("type") == "content_block_delta":
                d = j.get("delta", {}).get("text")
                if d:
                    text += d
                    sink(d)
    if role:
        _log_usage(role, model, t0, usage)
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
):
    _check_cancel()
    retry_config = retry_config or DEFAULT_RETRY
    max_tokens = _clamp_max_tokens(max_tokens)

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

    for attempt in range(retry_config.max_retries + 1):
        _check_cancel()

        if attempt > 0:
            _generation_notice({
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
            )
        except Aborted:
            raise
        except Exception as exc:
            error = _classify_error(exc)
            last_error = error

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


def _log_usage(role, model, t0, usage):
    """Make caching observable. Without reading `usage` back there is no way to
    confirm that a role's static system prompt -- repeated byte-for-byte on
    every call for that role -- is actually being served from cache instead of
    reprocessed, which is how a silently-uncached setup goes unnoticed."""
    from logging_utils import log_llm_call
    counts = _normalize_usage(usage)
    try:
        log_llm_call(
            role, model,
            system_tokens=counts["input"],
            response_tokens=counts["output"],
            cached_tokens=counts["cache_read"],
            cache_write_tokens=counts["cache_write"],
            duration=time.time() - t0,
        )
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
):
    _check_cancel()

    prov, model, cfg = resolved or resolve_role(role)
    t, merged = _merge_samplers(cfg, sampler, temperature)
    base = prov["base_url"].rstrip("/")
    sink = token_sink.get()

    if sink:
        sink = _guarded_sink(sink)

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
            "system": _anthropic_system(system),
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

        if sink:
            return _sse_anthropic(
                base,
                h,
                dict(body),
                sink,
                role=role,
                model=model,
            )

        _t0 = time.time()
        response = _session().post(
            base + "/v1/messages",
            headers=h,
            json=body,
            timeout=_request_timeout(),
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
        _log_usage(role, model, _t0, parsed.get("usage"))
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
    _apply_reasoning_effort(body, prov, role)

    if json_mode:
        body["response_format"] = {
            "type": "json_object",
        }

    url = base + "/chat/completions"
    headers = _headers(prov)

    if sink:
        try:
            out = _sse_openai(
                url,
                headers,
                dict(body),
                sink,
                role=role,
                model=model,
            )
        except LLMError as exc:
            if exc.status_code != 400:
                raise

            fallback_body = _strip_extended(dict(body))
            if json_mode:
                fallback_body.pop("response_format", None)

            out = _sse_openai(
                url,
                headers,
                fallback_body,
                sink,
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
                sink,
                role=role,
                model=model,
            )
        return out

    _t0 = time.time()
    response = _session().post(
        url,
        headers=headers,
        json=body,
        timeout=_request_timeout(),
    )

    if response.status_code == 400:
        fallback_body = _strip_extended(dict(body))
        if json_mode:
            fallback_body.pop("response_format", None)

        response = _session().post(
            url,
            headers=headers,
            json=fallback_body,
            timeout=_request_timeout(),
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
    content = parsed["choices"][0]["message"]["content"]
    # Some models (nemotron:thinking observed) honour response_format=json_object
    # by returning a syntactically-valid SKELETON with every string value set to
    # the literal "..." -- which parses and validates fine, so "..." reaches the
    # player as prose. When json_mode produced such a skeleton, retry once
    # WITHOUT json_mode (the same model writes real content ungated).
    if json_mode and _is_placeholder_json(content):
        retry_body = dict(body)
        retry_body.pop("response_format", None)
        alt = _session().post(url, headers=headers, json=retry_body,
                              timeout=_request_timeout())
        if alt.status_code < 400:
            parsed = alt.json()
            content = parsed["choices"][0]["message"]["content"]
    _log_usage(role, model, _t0, parsed.get("usage"))
    return content

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
                _generation_notice({
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
):
    _check_cancel()
    prov, model, cfg = resolved or resolve_role(role)
    t, merged = _merge_samplers(cfg, sampler, temperature)
    base = prov["base_url"].rstrip("/")
    sink = token_sink.get()
    if sink:
        sink = _guarded_sink(sink)

    if prov["kind"] == "anthropic":
        h = {"x-api-key": prov["api_key"] or "", "anthropic-version": "2023-06-01", "content-type": "application/json"}
        body = {"model": model, "max_tokens": max_tokens, "temperature": t, "system": _anthropic_system(system), "messages": [{"role": "user", "content": user}]}
        for k in ANTHROPIC_SAMPLERS:
            if k in merged:
                body[k] = merged[k]
        async with httpx.AsyncClient(timeout=_httpx_timeout()) as client:
            if sink:
                return await _sse_anthropic_async(base, h, dict(body), sink, client, role=role, model=model)
            _t0 = time.time()
            r = await client.post(base + "/v1/messages", headers=h, json=body)
            if r.status_code >= 400:
                raise LLMError(f"{prov['name']}: HTTP {r.status_code}: {r.text[:300]}", r.status_code, r.status_code in DEFAULT_RETRY.retryable_status)
            parsed = r.json()
            _log_usage(role, model, _t0, parsed.get("usage"))
            return "".join(b.get("text", "") for b in parsed.get("content", []))

    body = {"model": model, "temperature": t, "max_tokens": max_tokens, "messages": [_openai_system_message(system, prov, model), {"role": "user", "content": user}]}
    body.update(merged)
    _apply_provider_routing(body, prov)
    _apply_reasoning_effort(body, prov, role)
    if json_mode:
        body["response_format"] = {"type": "json_object"}

    async with httpx.AsyncClient(timeout=_httpx_timeout()) as client:
        if sink:
            try:
                out = await _sse_openai_async(base + "/chat/completions", _headers(prov), dict(body), sink, client, role=role, model=model)
            except LLMError as e:
                if e.status_code == 400:
                    b2 = dict(body)
                    if json_mode:
                        b2.pop("response_format", None)
                    b2 = _strip_extended(b2)
                    out = await _sse_openai_async(base + "/chat/completions", _headers(prov), b2, sink, client, role=role, model=model)
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
                out = await _sse_openai_async(base + "/chat/completions", _headers(prov), retry_body, sink, client, role=role, model=model)
            return out
        _t0 = time.time()
        r = await client.post(base + "/chat/completions", headers=_headers(prov), json=body)
        if r.status_code == 400:
            b2 = _strip_extended(dict(body))
            if json_mode:
                b2.pop("response_format", None)
            r = await client.post(base + "/chat/completions", headers=_headers(prov), json=b2)
        if r.status_code >= 400:
            raise LLMError(f"{prov['name']}: HTTP {r.status_code}: {r.text[:300]}", r.status_code, r.status_code in DEFAULT_RETRY.retryable_status)
        parsed = r.json()
        _log_usage(role, model, _t0, parsed.get("usage"))
        return parsed["choices"][0]["message"]["content"]

async def _sse_openai_async(url, headers, body, sink, client, role=None, model=None):
    body["stream"] = True
    # Without this a streamed response reports no token counts at all -- see
    # the matching comment in _sse_openai.
    body["stream_options"] = {"include_usage": True}
    text = ""
    usage = None
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
                raise LLMError(f"provider stream error: {msg}", 0, True)
            if j.get("usage"):
                usage = j["usage"]
            d = (j.get("choices") or [{}])[0].get("delta", {}).get("content")
            if d:
                text += d
                if sink:
                    sink(d)
    if role:
        _log_usage(role, model, t0, usage)
    return text

async def _sse_anthropic_async(base, headers, body, sink, client, role=None, model=None):
    body["stream"] = True
    text = ""
    usage = None
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
                raise LLMError(f"provider stream error: {msg or 'overloaded'}", 0, True)
            if j.get("type") == "message_start":
                usage = _merge_usage(usage, (j.get("message") or {}).get("usage"))
            elif j.get("type") == "message_delta":
                usage = _merge_usage(usage, j.get("usage"))
            if j.get("type") == "content_block_delta":
                d = j.get("delta", {}).get("text")
                if d:
                    text += d
                    if sink:
                        sink(d)
    if role:
        _log_usage(role, model, t0, usage)
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

def embed_texts_meta(texts) -> EmbeddingBatch:
    texts = [str(t or "") for t in texts]
    if not texts:
        return EmbeddingBatch(vectors=[], model_key=embedding_model_key(), dimensions=0)
    try:
        prov, model, _ = resolve_role("embeddings")
        base = prov["base_url"].rstrip("/")
        r = _session().post(base + "/embeddings", headers=_headers(prov), json={"model": model, "input": texts}, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json().get("data") or []
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
    except Exception as exc:
        vectors = [cheap_embed(text) for text in texts]
        return EmbeddingBatch(vectors=vectors, model_key="cheap:crc32:256", dimensions=256, fallback=True, error=str(exc))

def embed_texts(texts):
    return embed_texts_meta(texts).vectors
