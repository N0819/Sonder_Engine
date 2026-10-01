"""The decision-model seam: typed answers from TypeSafe's Jev, no prose.

Jev is not a chat model. It takes a STATE (text or JSON) and a map of typed
QUESTIONS and returns one typed answer per question -- a probability for a
`noul` (yes/no), a key plus a distribution for a `choice`, a position for a
`score` -- in well under a second. It writes nothing, so it can invent
nothing; that is the property the prose-contract Director leans on: the
decision "which engine channels does this passage touch" is made by a model
that cannot also start authoring the beat.

Questions in one request are evaluated INDEPENDENTLY against the state. One
answer never informs another, so a caller that needs a chain asks twice.
TypeSafe's guidance is to ask everything plausibly relevant at once and let
code discard what it does not need; adding questions costs little latency.

Measured 2026-09-22 on the owner's OpenRouter key: three questions, 379 input
tokens, 0.29s, $0.000016, all three right. The bare id `typesafe/jev` is
refused by OpenRouter ("does not exist"); the versioned id is what answers.

Settings: `jev_model` (default `DEFAULT_MODEL`) and `jev_provider` (a
providers row id; default: the first `openrouter`-kind row), chosen on the
models panel's "decision model" row (`PUT /api/decision_model`, `setting`),
and `jev_url` (a full decisions URL on another host of the same API, e.g. a
self-hosted Jev's `/v1/systemone`). A self-hosted URL needs no key, and
without an explicit `jev_provider` the seam sends it none: the OpenRouter key
never leaves for a host that is not OpenRouter. A module-level `OVERRIDE`
callable lets a test answer without the network.
"""

from __future__ import annotations

import contextvars
import time
from concurrent.futures import ThreadPoolExecutor

from core.db import get_setting, q

DEFAULT_MODEL = "typesafe/jev-1.13"
#: OpenRouter's decisions surface, relative to the provider's base url root.
DECISIONS_PATH = "/api/alpha/decisions"
#: Connect / read. A decision that takes longer than this has failed; the
#: caller falls back to asking for everything.
TIMEOUT = (10, 30)
#: Questions per request. TypeSafe publishes no ceiling; this is ours, so a
#: very large battery is split and asked concurrently rather than risking one
#: refused request. Named here per the owner's ask-before-limiting rule.
#: Raised 64 -> 128 (owner, 2026-09-30): every request repeats its state, and
#: Jev bills input only, so a split costs a whole state copy. Jev took 200 in
#: one request at the same latency (~0.25-0.5 s).
MAX_QUESTIONS_PER_REQUEST = 128
#: Answer options per request, the other ceiling: a request's OUTPUT grows
#: with its options, and 60 questions of 55 long options each (3,300) hit
#: Jev's output limit on 2026-09-30, where 2,560 short ones answered. A batch
#: closes at whichever limit it reaches first.
MAX_OPTIONS_PER_REQUEST = 2400

#: Installed by a test: `OVERRIDE(state, questions) -> {key: answer}`.
OVERRIDE = None


class DecisionError(Exception):
    """Jev could not answer: unconfigured, refused or unreachable."""


def _explicit_url() -> str:
    return str(get_setting("jev_url") or "").strip()


def _provider():
    pid = get_setting("jev_provider")
    if pid:
        row = q("SELECT * FROM providers WHERE id=?", (pid,), one=True)
        if row:
            return row
    if _explicit_url():
        # A self-hosted Jev: falling back to the OpenRouter row would hand its
        # key to whatever host `jev_url` names.
        return None
    return q(
        "SELECT * FROM providers WHERE kind='openrouter' ORDER BY id LIMIT 1",
        one=True,
    )


def setting() -> dict:
    """The decision model as the models panel shows it: what the host chose
    (`provider` None and `model` "" when unchosen) beside what the seam will
    actually use -- `effective_provider`, the row `_provider` resolves to,
    and `default_model` -- and whether it can be asked at all."""
    raw = str(get_setting("jev_provider") or "").strip()
    try:
        pid = int(raw) if raw else None
    except ValueError:
        pid = None
    prov = _provider()
    return {
        "provider": pid,
        "model": str(get_setting("jev_model") or "").strip(),
        "effective_provider": prov["id"] if prov else None,
        "default_model": DEFAULT_MODEL,
        "url": _explicit_url(),
        "configured": configured(),
    }


def configured() -> bool:
    if OVERRIDE is not None:
        return True
    if _explicit_url():
        return True
    prov = _provider()
    return bool(prov and prov["api_key"])


def _url(prov) -> str:
    # A full decisions URL (`jev_url`) points the seam at another host of the
    # same API -- a self-hosted open-source Jev -- without code changes.
    explicit = _explicit_url()
    if explicit:
        return explicit
    base = str(prov["base_url"] or "https://openrouter.ai/api/v1").rstrip("/")
    root = base.split("/api/", 1)[0]
    return root + DECISIONS_PATH


def _post(prov, model, state, questions):
    import requests
    from llm.providers import _headers, record_llm_call

    t0 = time.time()
    resp = requests.post(
        _url(prov),
        headers=_headers(prov) if prov else {"Content-Type": "application/json"},
        json={"model": model, "state": state, "questions": questions},
        timeout=TIMEOUT,
    )
    try:
        body = resp.json()
    except Exception:
        body = {}
    if resp.status_code != 200 or not isinstance(body.get("answers"), dict):
        err = (body.get("error") or {}).get("message") if isinstance(body, dict) else ""
        raise DecisionError(f"jev {resp.status_code}: {err or resp.text[:200]}")
    usage = body.get("usage") or {}
    record_llm_call({
        "role": "jev",
        "requested": model,
        "served": body.get("model") or model,
        "in": int(usage.get("input_tokens") or 0),
        "out": int(usage.get("output_tokens") or 0),
        "cached": 0,
        "duration": round(time.time() - t0, 3),
        "kind": "decision",
    })
    return body["answers"]


def _foregone(questions: dict) -> dict:
    """The answers no model is needed for: a `choice` with ONE alternative.

    Jev 1.13 answers one with certainty (`{"choice": "a0", "probabilities":
    {"a0": 1}, "confidence": 1}`, measured 2026-09-28), but a self-hosted
    Jev-compatible server may refuse it -- Winnow-12B answers "Questions
    require 2–64 alternatives" with a 400 -- and the refusal sinks every other
    question in the same request (a character's whole read-back was lost on
    chat 27 turn 89; which question tripped it was not recorded). A
    `want_serves` for a mind with no aims is one such choice: `situational`
    alone. Answered here, the same way, and never sent. Past 64 is the
    server's to accept, as Jev does."""
    out = {}
    for key, question in questions.items():
        if not isinstance(question, dict) or question.get("type") != "choice":
            continue
        criteria = question.get("criteria")
        if isinstance(criteria, dict) and len(criteria) == 1:
            only = next(iter(criteria))
            out[key] = {"type": "choice", "choice": only, "probabilities": {only: 1.0},
                        "confidence": 1.0}
    return out


def _options_in(question) -> int:
    criteria = (question or {}).get("criteria") if isinstance(question, dict) else None
    return len(criteria) if isinstance(criteria, dict) else 2


def _batches(items):
    """Split `[(key, question)]` into requests, each closed at whichever of
    `MAX_QUESTIONS_PER_REQUEST` and `MAX_OPTIONS_PER_REQUEST` it reaches
    first; a single question over the options limit still goes, alone."""
    out, cur, options = [], {}, 0
    for key, question in items:
        n = _options_in(question)
        if cur and (len(cur) >= MAX_QUESTIONS_PER_REQUEST or options + n > MAX_OPTIONS_PER_REQUEST):
            out.append(cur)
            cur, options = {}, 0
        cur[key] = question
        options += n
    if cur:
        out.append(cur)
    return out


def decide(state, questions: dict) -> dict:
    """Ask every question in `questions` of `state`; return `{key: answer}`.

    `state` is a string or a JSON-able value. Each question is Jev's own
    shape: `{"type": "noul"|"choice"|"score", "instructions": str,
    "criteria": ...}`. Answers come back in Jev's shape too
    (`{"type": "noul", "noul": 0.97}` and so on); `probability` below reads a
    noul. Raises `DecisionError` when nothing could be asked.
    """
    if not questions:
        return {}
    if OVERRIDE is not None:
        return dict(OVERRIDE(state, questions) or {})
    prov = _provider()
    if not _explicit_url() and (not prov or not prov["api_key"]):
        raise DecisionError("no OpenRouter provider configured for jev")
    model = get_setting("jev_model") or DEFAULT_MODEL
    answered = _foregone(questions)
    items = [(k, v) for k, v in questions.items() if k not in answered]
    if not items:
        return answered
    batches = _batches(items)
    if len(batches) == 1:
        return {**answered, **_post(prov, model, state, batches[0])}
    out = dict(answered)
    with ThreadPoolExecutor(max_workers=len(batches)) as pool:
        # Each shard runs in a copy of THIS thread's context, taken here: the
        # call ledger is a ContextVar a worker does not inherit, and every
        # shard of a large battery recorded into nothing (the bare-card
        # replay, 2026-09-27: the after-call pass never reached the ledger).
        futures = [pool.submit(contextvars.copy_context().run, _post, prov, model, state, b)
                   for b in batches]
        for future in futures:
            out.update(future.result())
    return out


def probability(answer) -> float:
    """A noul answer's yes-probability, 0.0 for anything unreadable."""
    if not isinstance(answer, dict):
        return 0.0
    try:
        return float(answer.get("noul", 0.0))
    except (TypeError, ValueError):
        return 0.0
