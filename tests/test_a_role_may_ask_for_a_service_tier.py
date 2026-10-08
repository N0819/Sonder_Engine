"""A role may ask OpenRouter for a service tier; none does by default.

OpenRouter serves Google's models at a FLEX tier -- half price, "in exchange
for higher latency and lower availability" -- taken as a top-level
`service_tier` on the request. Confirmed 2026-10-08 with one streamed call on
google/gemini-3.8-flash under the owner's routing block: HTTP 200, first
token at 1.6 s, `service_tier: "flex"` on the stream's chunks, $0.375/$1.875
per M tokens against the standard $0.75/$3.75. The encoder was 41-52% of the
Brackwater run's USD; whether it, or any role, trades latency and
availability for that price is the owner's call, so the setting
(`service_tier`, `{role: tier}`) names nothing until the owner names a role.

Pure request shaping, plus the call ledger: a flex request for a model with
no flex provider is answered at the standard rate without a word, so the
tier a call asked for and the one the provider says served it are recorded.
"""

from __future__ import annotations

import json

from llm import providers

OPENROUTER = {"id": 3, "kind": "openrouter", "name": "openrouter", "api_key": "k",
              "base_url": "https://openrouter.ai/api/v1"}
NANOGPT = {"id": 1, "kind": "nanogpt", "name": "nanogpt", "api_key": "k",
           "base_url": "https://nano-gpt.com/api/v1"}


def _body(prov, role):
    return providers._apply_service_tier({}, prov, role)


def test_no_role_asks_for_a_tier_by_default(temp_db):
    assert providers.service_tiers() == {}
    assert _body(OPENROUTER, "encoder") == {}


def test_a_named_role_asks_openrouter_for_its_tier(temp_db):
    temp_db.set_setting("service_tier", json.dumps({"encoder": "flex"}))
    assert _body(OPENROUTER, "encoder") == {"service_tier": "flex"}
    assert _body(OPENROUTER, "narrator") == {}, "only the role the owner named"


def test_an_unset_role_follows_the_default_row(temp_db):
    temp_db.set_setting("service_tier", json.dumps(
        {"default": "flex", "character_major": "priority"}))
    assert _body(OPENROUTER, "narrator") == {"service_tier": "flex"}
    assert _body(OPENROUTER, "character_major") == {"service_tier": "priority"}


def test_a_tier_rides_only_to_openrouter(temp_db):
    """The one host whose tier vocabulary this was checked against."""
    temp_db.set_setting("service_tier", json.dumps({"encoder": "flex"}))
    assert _body(NANOGPT, "encoder") == {}


def test_a_value_openrouter_does_not_take_is_never_sent(temp_db):
    temp_db.set_setting("service_tier", json.dumps(
        {"encoder": "vibes", "narrator": " FLEX ", "director": "default"}))
    assert providers.service_tiers() == {"narrator": "flex"}
    assert _body(OPENROUTER, "encoder") == {}


def test_a_400_retry_drops_the_tier_with_the_other_optional_fields():
    """A price-for-latency choice is never what an answer depends on."""
    assert "service_tier" not in providers._strip_extended(
        {"service_tier": "flex", "model": "m"})


class _Stream:
    status_code = 200
    text = ""

    def __init__(self, chunks):
        self._chunks = chunks

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def close(self):
        pass

    def iter_lines(self):
        for chunk in self._chunks:
            yield ("data: " + json.dumps(chunk)).encode("utf-8")
        yield b"data: [DONE]"


def _call_through_the_wire(monkeypatch, temp_db, chunks):
    bodies, entries = [], []

    class _Session:
        def post(self, url, headers=None, json=None, stream=None, timeout=None, **kw):
            bodies.append(json)
            return _Stream(chunks)

    monkeypatch.setattr(providers, "_session", lambda: _Session())
    monkeypatch.setattr(providers, "resolve_role_candidates",
                        lambda role: [(OPENROUTER, "google/gemini-3.8-flash", {})])
    token = providers.call_ledger_sink.set(entries.append)
    try:
        providers.chat_complete("encoder", "system", "user")
    finally:
        providers.call_ledger_sink.reset(token)
    return bodies, entries


def test_the_ledger_says_which_tier_served_a_call_that_asked(monkeypatch, temp_db):
    temp_db.set_setting("service_tier", json.dumps({"encoder": "flex"}))
    bodies, entries = _call_through_the_wire(monkeypatch, temp_db, [
        {"model": "google/gemini-3.8-flash", "service_tier": "default",
         "choices": [{"delta": {"content": "ok"}, "finish_reason": "stop"}]},
        {"choices": [], "usage": {"prompt_tokens": 3, "completion_tokens": 1}}])
    assert bodies[0]["service_tier"] == "flex"
    assert entries[-1]["tier_asked"] == "flex"
    assert entries[-1]["tier"] == "default", (
        "asked for flex and served at the standard rate: the ledger says so")


def test_a_call_that_asked_for_no_tier_records_none(monkeypatch, temp_db):
    bodies, entries = _call_through_the_wire(monkeypatch, temp_db, [
        {"model": "google/gemini-3.8-flash", "service_tier": "default",
         "choices": [{"delta": {"content": "ok"}, "finish_reason": "stop"}]}])
    assert "service_tier" not in bodies[0]
    assert "tier" not in entries[-1] and "tier_asked" not in entries[-1]
