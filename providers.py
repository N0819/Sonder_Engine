# providers.py
"""LLM providers, streaming, retries, cancellation, and embeddings."""

import json, zlib, asyncio, threading, time, re, os
import numpy as np
import httpx
import contextvars
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
]

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
    if isinstance(error, (httpx.TimeoutException, httpx.NetworkError)):
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

def _strip_extended(body):
    for k in ("top_k", "repetition_penalty", "min_p", "top_a"):
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
    if isinstance(e, (httpx.TimeoutException, httpx.NetworkError)):
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
    with _session().post(url, headers=headers, json=body, stream=True, timeout=REQUEST_TIMEOUT) as r:
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
            if j.get("usage"):
                usage = j["usage"]
            d = (j.get("choices") or [{}])[0].get("delta", {}).get("content")
            if d:
                text += d
                sink(d)
    if role:
        _log_usage(role, model, t0, usage)
    return text

def _sse_anthropic(base, headers, body, sink):
    body["stream"] = True
    text = ""
    _check_cancel()
    with _session().post(base + "/v1/messages", headers=headers, json=body, stream=True, timeout=REQUEST_TIMEOUT) as r:
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
            if j.get("type") == "content_block_delta":
                d = j.get("delta", {}).get("text")
                if d:
                    text += d
                    sink(d)
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

def _log_usage(role, model, t0, usage):
    """nanogpt (and most OpenAI-compatible backends) apply implicit prompt
    caching automatically -- there's no client-side field to opt into, so
    there's nothing to configure here. This just makes the effect visible:
    without reading `usage` back, there's no way to confirm caching is
    actually reducing the tokens billed/processed for a role's static
    system prompt, which is repeated byte-for-byte on every call.
    """
    from logging_utils import log_llm_call
    usage = usage or {}
    details = usage.get("prompt_tokens_details") or {}
    try:
        log_llm_call(
            role, model,
            system_tokens=usage.get("prompt_tokens", 0),
            response_tokens=usage.get("completion_tokens", 0),
            cached_tokens=details.get("cached_tokens", 0),
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
            )

        response = _session().post(
            base + "/v1/messages",
            headers=h,
            json=body,
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code >= 400:
            raise LLMError(
                f"{prov['name']}: HTTP {response.status_code}: "
                f"{response.text[:300]}",
                response.status_code,
                response.status_code
                in DEFAULT_RETRY.retryable_status,
            )

        return "".join(
            block.get("text", "")
            for block in response.json().get("content", [])
        )

    body = {
        "model": model,
        "temperature": t,
        "max_tokens": max_tokens,
        "messages": [
            {
                "role": "system",
                "content": system,
            },
            {
                "role": "user",
                "content": user,
            },
        ],
    }
    body.update(merged)

    if json_mode:
        body["response_format"] = {
            "type": "json_object",
        }

    url = base + "/chat/completions"
    headers = _headers(prov)

    if sink:
        try:
            return _sse_openai(
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

            return _sse_openai(
                url,
                headers,
                fallback_body,
                sink,
                role=role,
                model=model,
            )

    _t0 = time.time()
    response = _session().post(
        url,
        headers=headers,
        json=body,
        timeout=REQUEST_TIMEOUT,
    )

    if response.status_code == 400:
        fallback_body = _strip_extended(dict(body))
        if json_mode:
            fallback_body.pop("response_format", None)

        response = _session().post(
            url,
            headers=headers,
            json=fallback_body,
            timeout=REQUEST_TIMEOUT,
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
    return parsed["choices"][0]["message"]["content"]

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
        async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
            if sink:
                return await _sse_anthropic_async(base, h, dict(body), sink, client)
            r = await client.post(base + "/v1/messages", headers=h, json=body)
            if r.status_code >= 400:
                raise LLMError(f"{prov['name']}: HTTP {r.status_code}: {r.text[:300]}", r.status_code, r.status_code in DEFAULT_RETRY.retryable_status)
            return "".join(b.get("text", "") for b in r.json().get("content", []))

    body = {"model": model, "temperature": t, "max_tokens": max_tokens, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    body.update(merged)
    if json_mode:
        body["response_format"] = {"type": "json_object"}

    async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
        if sink:
            try:
                return await _sse_openai_async(base + "/chat/completions", _headers(prov), dict(body), sink, client)
            except LLMError as e:
                if e.status_code == 400:
                    b2 = dict(body)
                    if json_mode:
                        b2.pop("response_format", None)
                    b2 = _strip_extended(b2)
                    return await _sse_openai_async(base + "/chat/completions", _headers(prov), b2, sink, client)
                raise
        r = await client.post(base + "/chat/completions", headers=_headers(prov), json=body)
        if r.status_code == 400:
            b2 = _strip_extended(dict(body))
            if json_mode:
                b2.pop("response_format", None)
            r = await client.post(base + "/chat/completions", headers=_headers(prov), json=b2)
        if r.status_code >= 400:
            raise LLMError(f"{prov['name']}: HTTP {r.status_code}: {r.text[:300]}", r.status_code, r.status_code in DEFAULT_RETRY.retryable_status)
        return r.json()["choices"][0]["message"]["content"]

async def _sse_openai_async(url, headers, body, sink, client):
    body["stream"] = True
    text = ""
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
            d = (j.get("choices") or [{}])[0].get("delta", {}).get("content")
            if d:
                text += d
                if sink:
                    sink(d)
    return text

async def _sse_anthropic_async(base, headers, body, sink, client):
    body["stream"] = True
    text = ""
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
            if j.get("type") == "content_block_delta":
                d = j.get("delta", {}).get("text")
                if d:
                    text += d
                    if sink:
                        sink(d)
    return text

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
    data = j.get("data", j if isinstance(j, list) else [])
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