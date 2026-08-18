"""Prompt caching became a switch a host can reach, per connection.

The controls existed -- `prompt_cache_allow`, `prompt_cache_deny`, and the
`FICTION_ENGINE_PROMPT_CACHE=0` env kill switch -- but nothing in the UI wrote
them, so the only way to turn caching off was to edit a settings row by hand or
restart the process with an env var. That matters because caching is not
unambiguously a win: a host who suspects it is costing latency had no way to
test the suspicion.

Two things were actually broken underneath the missing UI:

* the NATIVE Anthropic path (`kind="anthropic"`) never consulted the deny list
  at all, so the switch would have lied for the provider whose caching is least
  in doubt, and
* a KIND-level deny covers every connection of that kind, so enabling one of
  them by dropping the token would silently enable the others too. The route
  expands it into per-connection denies instead.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from web import app as app_module
from web import guest_access as guest
from llm import providers
from core.db import get_setting, set_setting


@pytest.fixture
def client(temp_db):
    guest.reset_host_account()
    with TestClient(app_module.app) as c:
        r = c.post("/api/auth/setup",
                   json={"username": "host", "password": "pw12345"})
        assert r.status_code == 200, r.text
        yield c
    guest.reset_host_account()


def _add(client, kind, name=None):
    r = client.post("/api/providers", json={"kind": kind, "name": name or kind})
    assert r.status_code == 200, r.text
    return r.json()


def _set(client, pid, enabled):
    r = client.put(f"/api/providers/{pid}/prompt_cache", json={"enabled": enabled})
    assert r.status_code == 200, r.text
    return r.json()


# ---- the native Anthropic path now honours the same switch ----

def test_native_anthropic_caches_by_default(temp_db):
    """Unchanged behaviour, pinned: a direct Anthropic connection has always
    marked its system prompt, and the switch must not quietly cost that."""
    prov = {"kind": "anthropic", "name": "claude"}
    block = providers._anthropic_system("A long stable system prompt.", prov)
    assert isinstance(block, list)
    assert block[0]["cache_control"] == {"type": "ephemeral"}


def test_deny_reaches_the_native_path(temp_db):
    """The bug the toggle exposed: `_anthropic_system` read only the env var,
    so `prompt_cache_deny` was ignored for kind="anthropic" and the UI switch
    would have reported off while every call still cached."""
    set_setting("prompt_cache_deny", "claude")
    plain = providers._anthropic_system("A long stable system prompt.",
                                        {"kind": "anthropic", "name": "claude"})
    assert plain == "A long stable system prompt."


def test_no_provider_still_caches(temp_db):
    """`prov` is optional so a synthetic caller does not lose caching by
    omitting it -- the pre-change signature took `system` alone."""
    assert isinstance(providers._anthropic_system("prompt"), list)


# ---- the route ----

def test_toggling_off_stops_the_breakpoint(client):
    """End to end: the box in ⚙ API and the request path are the same rule."""
    p = _add(client, "nanogpt")
    assert p["prompt_cache"] is True

    off = _set(client, p["id"], False)
    assert off["prompt_cache"] is False
    row = {"kind": "nanogpt", "name": "nanogpt"}
    assert not providers._cache_passthrough_allowed(row)

    on = _set(client, p["id"], True)
    assert on["prompt_cache"] is True
    assert providers._cache_passthrough_allowed(row)


def test_opting_in_an_unknown_provider(client):
    """A provider outside the built-in kinds needs the allowlist, not just an
    absent deny -- the two are not the same and the route has to pick."""
    p = _add(client, "openai", name="my-gateway")
    assert p["prompt_cache"] is False
    assert p["prompt_cache_default"] is False

    on = _set(client, p["id"], True)
    assert on["prompt_cache"] is True
    assert "my-gateway" in get_setting("prompt_cache_allow")


def test_enabling_one_connection_does_not_enable_its_siblings(client):
    """The reason the route rewrites lists instead of dropping a token: a
    kind-level deny covers every nanogpt connection, so enabling one by
    removing "nanogpt" would turn caching back on for the other as well."""
    a = _add(client, "nanogpt", name="nano-a")
    b = _add(client, "nanogpt", name="nano-b")
    set_setting("prompt_cache_deny", "nanogpt")

    on = _set(client, a["id"], True)
    assert on["prompt_cache"] is True

    still_off = client.get("/api/bootstrap").json()["providers"]
    by_id = {r["id"]: r for r in still_off}
    assert by_id[b["id"]]["prompt_cache"] is False


def test_disabling_outranks_a_hand_typed_allow(client):
    """Deny wins over allow -- documented in `_cache_passthrough_allowed`, and
    the route must not paper over it by reporting what was asked for."""
    p = _add(client, "openai", name="my-gateway")
    set_setting("prompt_cache_allow", "my-gateway")
    off = _set(client, p["id"], False)
    assert off["prompt_cache"] is False
    # The opt-in the host typed survives, so re-enabling restores it rather
    # than needing it typed again.
    assert "my-gateway" in get_setting("prompt_cache_allow")


def test_the_env_kill_switch_is_reported_as_locked(client, monkeypatch):
    """A disabled box needs a reason. Without this the host unticks nothing,
    reticks nothing, and concludes the setting is broken."""
    p = _add(client, "nanogpt")
    monkeypatch.setattr(providers, "PROMPT_CACHE_ENABLED", False)
    row = client.get("/api/bootstrap").json()["providers"][0]
    assert row["id"] == p["id"]
    assert row["prompt_cache"] is False
    assert row["prompt_cache_locked"] is True


def test_unknown_provider_id_is_a_404(client):
    """Paired with a real id so this asserts the route EXISTS and 404s on a
    missing row -- on its own, "404" is also what a missing route returns."""
    p = _add(client, "nanogpt")
    assert client.put(f"/api/providers/{p['id']}/prompt_cache",
                      json={"enabled": False}).status_code == 200
    r = client.put("/api/providers/9999/prompt_cache", json={"enabled": False})
    assert r.status_code == 404
