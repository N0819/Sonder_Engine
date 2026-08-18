"""The cache-affinity routing hint: stable, content-free, and opt-in.

Fireworks-class hosts cache prompt prefixes automatically but only within one
replica, and serverless routing scatters requests across replicas unless the
client hints where to send them (their prompt-caching guide names the OpenAI
`user` field and the `x-session-affinity` header). Without a hint, whether
this engine's ~15,000-token static role prompt is served from cache is
routing luck. `_apply_cache_affinity` adds `user: "sonder:<role>"` to the
OpenAI-compatible request body for providers opted in via the
`cache_affinity_allow` setting (by name or kind -- the `prompt_cache_allow`
idiom).

Pure request-shaping -- no network. What these pin, in the order it matters:
the value carries no content and no identity (an engine role constant,
nothing derived from a chat, character, or player input); it is stable across
repeated builds so calls that share a prefix share a replica; it is absent by
default and absent for any provider not opted in, so a working provider's
requests stay byte-identical; and the 400-retry path strips it rather than
letting a host that rejects it cost the turn.
"""

from __future__ import annotations

from llm import providers

FIREWORKS = {"kind": "generic", "name": "Fireworks",
             "api_key": "k", "base_url": "https://api.fireworks.ai/inference/v1"}
NANOGPT = {"kind": "nanogpt", "name": "nanogpt",
           "api_key": "k", "base_url": "https://nano-gpt.com/api/v1"}


def _allow(monkeypatch, value):
    monkeypatch.setattr(
        providers, "get_setting",
        lambda key, default=None: value if key == "cache_affinity_allow"
        else default)


def test_absent_by_default(monkeypatch):
    """Unset setting: no field is added anywhere -- every request stays
    byte-identical to before the feature existed."""
    _allow(monkeypatch, "")
    body = providers._apply_cache_affinity({}, FIREWORKS, "character_major")
    assert "user" not in body


def test_opt_in_by_name(monkeypatch):
    _allow(monkeypatch, "fireworks")
    body = providers._apply_cache_affinity({}, FIREWORKS, "character_major")
    assert body["user"] == "sonder:character_major"


def test_opt_in_by_kind(monkeypatch):
    _allow(monkeypatch, "nanogpt")
    body = providers._apply_cache_affinity({}, NANOGPT, "narrator")
    assert body["user"] == "sonder:narrator"


def test_a_provider_not_named_gets_nothing(monkeypatch):
    """Fail closed per provider: opting Fireworks in must not add the field
    to anyone else's requests."""
    _allow(monkeypatch, "fireworks")
    assert "user" not in providers._apply_cache_affinity(
        {}, NANOGPT, "character_major")
    assert "user" not in providers._apply_cache_affinity(
        {}, None, "character_major")


def test_stable_across_repeated_builds(monkeypatch):
    """Stability is the whole point: the same role maps to the same string on
    every build, so the calls that share a prefix -- turn after turn, and the
    retry path's byte-identical resend -- share a replica."""
    _allow(monkeypatch, "fireworks")
    values = {providers._apply_cache_affinity(
        {}, FIREWORKS, "character_major")["user"] for _ in range(20)}
    assert values == {"sonder:character_major"}


def test_value_is_an_engine_constant_never_content(monkeypatch):
    """The hint goes to a third party on every call. It is built from the
    role name alone -- an engine constant -- and must never grow a chat,
    character, persona, or input-derived component."""
    _allow(monkeypatch, "fireworks")
    for role in ("narrator", "director", "character_bg", "character_mid",
                 "character_major", "default"):
        body = providers._apply_cache_affinity({}, FIREWORKS, role)
        assert body["user"] == f"sonder:{role}"
    # No role, no field: an anonymous call gets no hint rather than an
    # invented one.
    assert "user" not in providers._apply_cache_affinity({}, FIREWORKS, "")
    assert "user" not in providers._apply_cache_affinity({}, FIREWORKS, None)


def test_the_400_retry_strips_the_hint(monkeypatch):
    """A host that rejects the field costs a retry, never the turn."""
    _allow(monkeypatch, "fireworks")
    body = providers._apply_cache_affinity(
        {"model": "m"}, FIREWORKS, "narrator")
    stripped = providers._strip_extended(dict(body))
    assert "user" not in stripped
    assert stripped["model"] == "m"


def test_both_openai_body_builders_apply_it():
    """Source-level wiring guard (the test_strict_stage_validation idiom): a
    hint on some transport paths and not others makes the cache measurement
    lie. Both OpenAI-compatible body builders -- sync and async, whose built
    bodies the SSE paths consume -- must call _apply_cache_affinity."""
    import inspect
    source = inspect.getsource(providers)
    assert source.count("_apply_cache_affinity(body, prov, role)") >= 2
