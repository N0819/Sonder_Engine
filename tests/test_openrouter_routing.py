"""Regression tests for OpenRouter upstream-provider routing.

One OpenRouter model id (`anthropic/claude-opus-4-6`) is served by several
upstream providers -- Anthropic direct, Amazon Bedrock, Azure, Google Vertex,
third-party hosts. They are not interchangeable: output quality varies between
them, and so does the prompt-retention policy, which makes this a privacy
control and not only a quality preference. Without a routing block, OpenRouter
picks on every call and a prompt can land on a provider that retains it.

Pure request-shaping — no network.
"""

from __future__ import annotations

import json

import providers

OPENROUTER = {"kind": "openrouter", "name": "openrouter",
              "api_key": "k", "base_url": "https://openrouter.ai/api/v1"}
DIRECT = {"kind": "openai", "name": "openai",
          "api_key": "k", "base_url": "https://api.openai.com/v1"}


# ---- Normalization ----

def test_pin_a_single_upstream():
    routing = providers.normalize_openrouter_routing(
        {"only": ["anthropic"], "allow_fallbacks": False})
    assert routing == {"only": ["anthropic"], "allow_fallbacks": False}


def test_order_is_preserved_and_deduped():
    """Order is meaningful — it's the preference sequence."""
    routing = providers.normalize_openrouter_routing(
        {"order": ["anthropic", "amazon-bedrock", "anthropic", "google-vertex"]})
    assert routing["order"] == ["anthropic", "amazon-bedrock", "google-vertex"]


def test_blacklist_and_privacy_policy():
    routing = providers.normalize_openrouter_routing(
        {"ignore": ["some-host"], "data_collection": "deny"})
    assert routing["ignore"] == ["some-host"]
    assert routing["data_collection"] == "deny"


def test_allow_is_not_sent():
    """'allow' is OpenRouter's own default, so sending it is pure noise."""
    routing = providers.normalize_openrouter_routing(
        {"data_collection": "allow", "only": ["anthropic"]})
    assert "data_collection" not in routing


def test_allow_fallbacks_only_sent_when_disabled():
    assert "allow_fallbacks" not in providers.normalize_openrouter_routing(
        {"only": ["anthropic"], "allow_fallbacks": True})


def test_sort_is_whitelisted():
    assert providers.normalize_openrouter_routing({"sort": "throughput"})["sort"] \
        == "throughput"
    assert "sort" not in providers.normalize_openrouter_routing({"sort": "vibes"})


def test_comma_or_space_separated_input_is_accepted():
    """What a text field yields, rather than requiring the user to type JSON."""
    routing = providers.normalize_openrouter_routing(
        {"ignore": "deepinfra, novita  together"})
    assert routing["ignore"] == ["deepinfra", "novita", "together"]


def test_garbage_can_never_produce_an_invalid_request():
    """This rides on every request — it must degrade to 'no routing'."""
    for junk in (None, "", "nonsense", 5, [], {"unknown_key": "x"},
                 {"only": [None, "  "]}, '{"bad json'):
        assert providers.normalize_openrouter_routing(junk) == {}


def test_json_string_from_settings_round_trips():
    stored = json.dumps({"only": ["anthropic"], "data_collection": "deny"})
    assert providers.normalize_openrouter_routing(stored) == {
        "only": ["anthropic"], "data_collection": "deny"}


# ---- Attachment to the request ----

def test_routing_attaches_only_for_openrouter():
    routing = {"only": ["anthropic"]}
    body = providers._apply_provider_routing({}, OPENROUTER, routing)
    assert body["provider"] == routing

    # A direct provider has no upstream choice to make and must not be sent a
    # field it never asked for.
    assert providers._apply_provider_routing({}, DIRECT, routing) == {}


def test_no_configuration_means_no_field():
    assert providers._apply_provider_routing({}, OPENROUTER, {}) == {}


def test_routing_reaches_the_wire(monkeypatch, temp_db):
    """Drives chat_complete and inspects the outgoing body — the only thing
    that proves a real call carries the routing block."""
    import db
    from tests.test_prompt_cache_block import _FakeSession, OPENAI_REPLY

    db.set_setting("openrouter_routing", json.dumps(
        {"only": ["anthropic"], "data_collection": "deny",
         "allow_fallbacks": False}))

    session = _FakeSession(OPENAI_REPLY)
    monkeypatch.setattr(providers, "_session", lambda: session)
    monkeypatch.setattr(providers, "resolve_role_candidates",
                        lambda role: [(OPENROUTER, "anthropic/claude-opus-4-6", {})])
    monkeypatch.setattr(providers, "_log_usage", lambda *a, **kw: None)

    providers.chat_complete("narrator", "system", "user")
    assert session.bodies[0]["provider"] == {
        "only": ["anthropic"], "data_collection": "deny",
        "allow_fallbacks": False}


def test_settings_change_applies_without_restart(temp_db):
    import db

    assert providers.openrouter_routing() == {}
    db.set_setting("openrouter_routing", json.dumps({"only": ["amazon-bedrock"]}))
    assert providers.openrouter_routing() == {"only": ["amazon-bedrock"]}


# ---- Endpoint discovery ----

def test_endpoint_listing_shapes_the_picker(monkeypatch):
    """Slugs aren't guessable, and the retention policy is what the privacy
    decision hinges on — both have to reach the picker."""
    class _R:
        status_code = 200

        @staticmethod
        def raise_for_status():
            pass

        @staticmethod
        def json():
            return {"data": {"endpoints": [
                {"tag": "anthropic", "provider_name": "Anthropic",
                 "context_length": 200000,
                 "data_policy": {"training": False, "retains_prompts": False}},
                {"tag": "amazon-bedrock", "provider_name": "Amazon Bedrock",
                 "context_length": 200000,
                 "data_policy": {"training": False, "retains_prompts": True}},
                {"no_tag_or_name": True},
            ]}}

    monkeypatch.setattr(providers, "_session",
                        lambda: type("S", (), {"get": staticmethod(lambda *a, **k: _R())})())
    eps = providers.list_openrouter_endpoints(OPENROUTER, "anthropic/claude-opus-4-6")
    assert [e["slug"] for e in eps] == ["anthropic", "amazon-bedrock"]
    assert eps[0]["retains_prompts"] is False
    assert eps[1]["retains_prompts"] is True


def test_endpoint_listing_is_openrouter_only():
    assert providers.list_openrouter_endpoints(DIRECT, "gpt-5") == []
    assert providers.list_openrouter_endpoints(OPENROUTER, "") == []
