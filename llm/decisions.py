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
providers row id; default: the first `openrouter`-kind row). A module-level
`OVERRIDE` callable lets a test answer without the network.
"""

from __future__ import annotations

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
MAX_QUESTIONS_PER_REQUEST = 64

#: Installed by a test: `OVERRIDE(state, questions) -> {key: answer}`.
OVERRIDE = None


class DecisionError(Exception):
    """Jev could not answer: unconfigured, refused or unreachable."""


def _provider():
    pid = get_setting("jev_provider")
    if pid:
        row = q("SELECT * FROM providers WHERE id=?", (pid,), one=True)
        if row:
            return row
    return q(
        "SELECT * FROM providers WHERE kind='openrouter' ORDER BY id LIMIT 1",
        one=True,
    )


def configured() -> bool:
    if OVERRIDE is not None:
        return True
    prov = _provider()
    return bool(prov and prov["api_key"])


def _url(prov) -> str:
    base = str(prov["base_url"] or "https://openrouter.ai/api/v1").rstrip("/")
    root = base.split("/api/", 1)[0]
    return root + DECISIONS_PATH


def _post(prov, model, state, questions):
    import requests
    from llm.providers import _headers, record_llm_call

    t0 = time.time()
    resp = requests.post(
        _url(prov),
        headers=_headers(prov),
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
    if not prov or not prov["api_key"]:
        raise DecisionError("no OpenRouter provider configured for jev")
    model = get_setting("jev_model") or DEFAULT_MODEL
    items = list(questions.items())
    batches = [
        dict(items[i:i + MAX_QUESTIONS_PER_REQUEST])
        for i in range(0, len(items), MAX_QUESTIONS_PER_REQUEST)
    ]
    if len(batches) == 1:
        return _post(prov, model, state, batches[0])
    out = {}
    with ThreadPoolExecutor(max_workers=len(batches)) as pool:
        for answers in pool.map(lambda b: _post(prov, model, state, b), batches):
            out.update(answers)
    return out


def probability(answer) -> float:
    """A noul answer's yes-probability, 0.0 for anything unreadable."""
    if not isinstance(answer, dict):
        return 0.0
    try:
        return float(answer.get("noul", 0.0))
    except (TypeError, ValueError):
        return 0.0
