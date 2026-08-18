"""Extension-declared model lanes: a role of the extension's own.

Before this seam an extension's `llm_json`/`llm_text` calls had to borrow a
host role, which failed twice over: the call ran on whatever model the host
chose FOR THAT ROLE'S WORK (the extension had no row of its own to be
configured on), and it was logged as that role's spend, so "which model is
looping" stopped being answerable per lane. `docs/design/
DIRECTIVE_HOST_SURFACE.md` §6 is the measurement: Directive configures two
inference lanes of its own, and Sonder had nowhere to put them.

Each test pins the property that makes the seam safe rather than its happy
path:

* a lane is a ROLE to everything downstream -- resolution, inheritance, the
  per-call ledger -- so those come from the existing role plumbing, keyed on
  the namespaced role string, not from a parallel mechanism that could drift;
* a blank lane row means INHERIT `default`, because that is what a blank row
  has always meant to a host and an extension must not be the exception;
* `providers.ROLES` is the host's fixed vocabulary and never mutates -- an
  extension can neither shadow a host role nor wear one's name;
* disable takes the settings row (no phantom lane in the panel), never the
  host's stored configuration, which is the same removal rule that leaves
  `world["ext:<id>"]` alone.
"""

from __future__ import annotations

import json
import time

import pytest

from llm import providers
import extension_runtime
from extension_runtime import ExtensionError

from tests.test_extensions import (  # noqa: F401 - fixtures are used by name
    _enable, _write_extension, ext_root,
)


def _api(ext_id):
    return extension_runtime._apis[ext_id]


@pytest.fixture
def bare(ext_root):
    """One installed, enabled extension whose entry registers nothing, so each
    test states the one lane it is about."""
    _write_extension(ext_root, "lanes", {
        "id": "lanes", "version": "1.0.0", "ext_api": 1, "name": "Lanes",
        "capabilities": {"python": "extension.py"},
    }, {"extension.py": "def register(api):\n    pass\n"})
    _enable("lanes")
    return _api("lanes")


def _stub_provider(monkeypatch):
    monkeypatch.setattr(
        providers, "provider",
        lambda name: {"name": name, "kind": "openai",
                      "base_url": "http://x", "api_key": ""})


# ------------------------------------------------------------- declaration


class TestDeclaringALane:
    def test_the_returned_role_is_namespaced_under_the_extension(
            self, temp_db, bare):
        role = bare.add_model_lane("planner", label="Directive · planner",
                                   description="Plans the next beat.")
        assert role == "ext:lanes:planner"
        lanes = extension_runtime.registered_model_lanes()
        assert lanes == [{"ext_id": "lanes", "name": "planner",
                          "role": "ext:lanes:planner",
                          "label": "Directive · planner",
                          "description": "Plans the next beat."}]

    def test_redeclaring_replaces_rather_than_duplicates(self, temp_db, bare):
        """Re-enabling an extension in a live process re-runs `register()`;
        the same lane declared twice must stay one settings row, not two."""
        bare.add_model_lane("planner", label="v1")
        bare.add_model_lane("planner", label="v2")
        lanes = extension_runtime.registered_model_lanes()
        assert [lane["label"] for lane in lanes] == ["v2"]

    def test_a_host_role_name_is_refused_not_namespaced(self, temp_db, bare):
        """`ext:lanes:director` would shadow nothing -- the namespace already
        guarantees that -- but a settings row wearing a host role's name reads
        as that role's configuration, and the misread costs real money. Every
        host role is refused, not just the famous ones."""
        for host_role in providers.ROLES:
            with pytest.raises(ExtensionError):
                bare.add_model_lane(host_role)
        assert extension_runtime.registered_model_lanes() == []

    def test_an_invalid_name_is_refused(self, temp_db, bare):
        for bad in ("", "Has Spaces", "UPPER", "9starts-with-digit",
                    "ext:sneaky", None):
            with pytest.raises(ExtensionError):
                bare.add_model_lane(bad)

    def test_declaring_a_lane_never_mutates_the_host_role_list(
            self, temp_db, bare):
        """`ROLES` is read all over the engine; a list an install could grow
        is one it could also shadow or shrink."""
        before = list(providers.ROLES)
        bare.add_model_lane("planner")
        assert providers.ROLES == before
        assert "ext:lanes:planner" not in providers.ROLES


# -------------------------------------------------------------- resolution


class TestLaneResolution:
    def test_a_configured_lane_resolves_its_own_row(
            self, temp_db, bare, monkeypatch):
        """The point of the feature: the lane's calls run on the model the
        host configured for THE LANE, samplers and all, not on whatever the
        borrowed host role happened to hold."""
        role = bare.add_model_lane("planner")
        _stub_provider(monkeypatch)
        monkeypatch.setattr(providers, "agent_models", lambda: {
            "default": {"provider": "frontier", "model": "big"},
            role: {"provider": "cheap", "model": "small", "temperature": 0.1},
        })
        prov, model, cfg = providers.resolve_role(role)
        assert (prov["name"], model) == ("cheap", "small")
        assert cfg["temperature"] == 0.1

    def test_a_blank_lane_inherits_default_like_every_blank_row(
            self, temp_db, bare, monkeypatch):
        """A blank `agent_models` row means INHERIT, deliberately -- the rule
        stated on `ROLE_FALLBACKS` and pinned for host roles in
        `tests/test_provider_fallbacks.py`. An extension lane must not be the
        one row where blank means broken."""
        role = bare.add_model_lane("planner")
        _stub_provider(monkeypatch)
        monkeypatch.setattr(providers, "agent_models", lambda: {
            "default": {"provider": "frontier", "model": "big"},
        })
        prov, model, _cfg = providers.resolve_role(role)
        assert (prov["name"], model) == ("frontier", "big")

    def test_lane_backup_models_ride_the_same_fallback_plumbing(
            self, temp_db, bare, monkeypatch):
        """A lane is a role to `resolve_role_candidates`, so the host's
        backup-model list works on it unchanged -- no parallel mechanism."""
        role = bare.add_model_lane("planner")
        _stub_provider(monkeypatch)
        monkeypatch.setattr(providers, "agent_models", lambda: {
            "default": {"provider": "frontier", "model": "big"},
            role: {"provider": "cheap", "model": "small",
                   "fallbacks": [{"provider": "spare", "model": "backup"}]},
        })
        resolved = providers.resolve_role_candidates(role)
        assert [(prov["name"], model) for prov, model, _ in resolved] == [
            ("cheap", "small"), ("spare", "backup")]


# -------------------------------------------------------------- attribution


class TestUsageAttribution:
    def test_llm_calls_carry_the_lane_role_to_the_provider_seam(
            self, temp_db, bare, monkeypatch):
        """`api.llm_json`/`llm_text` must hand `chat_complete` the lane's own
        role string -- that string is what `_log_usage` keys the ledger on,
        so losing it here is losing per-lane spend everywhere."""
        role = bare.add_model_lane("planner")
        seen = []

        def fake_chat_complete(r, system, user, **kw):
            seen.append(r)
            return "{}"

        monkeypatch.setattr(providers, "chat_complete", fake_chat_complete)
        bare.llm_json("You plan.", {"beat": 1}, role=role)
        bare.llm_text("You write.", "A door closed.", role=role)
        assert seen == [role, role]

    def test_the_ledger_records_the_lane_not_the_served_models_owner(
            self, temp_db, bare):
        """The separability guarantee itself: even when an unconfigured lane
        is SERVED by default's model, the ledger entry names the lane, so the
        lane's spend never disappears into `default`'s ledger. Same property
        the Director specialists rely on (design note 19)."""
        role = bare.add_model_lane("planner")
        entries = []
        token = providers.call_ledger_sink.set(entries.append)
        try:
            providers._log_usage(
                role, "big", time.time() - 0.2,
                {"prompt_tokens": 100, "completion_tokens": 20})
        finally:
            providers.call_ledger_sink.reset(token)
        assert entries[0]["role"] == role
        assert entries[0]["served"] == "big"


# ----------------------------------------------------------- deregistration


class TestDisableAndRemoval:
    def test_disable_takes_the_lane_out_of_the_registry(self, temp_db,
                                                        ext_root):
        """No phantom row: the settings panel renders lanes from this
        registry, so an empty registry IS the row's removal."""
        _write_extension(ext_root, "laned", {
            "id": "laned", "version": "1.0.0", "ext_api": 1, "name": "Laned",
            "capabilities": {"python": "extension.py"},
        }, {"extension.py": (
            "def register(api):\n"
            "    api.add_model_lane('planner', label='Planner')\n")})
        _enable("laned")
        assert [lane["role"] for lane in
                extension_runtime.registered_model_lanes()] == [
            "ext:laned:planner"]

        extension_runtime.disable_extension("laned")
        assert extension_runtime.registered_model_lanes() == []

        # Re-enabling re-registers exactly one lane -- the replace-not-append
        # rule holding across a real disable/enable cycle.
        _enable("laned")
        assert [lane["role"] for lane in
                extension_runtime.registered_model_lanes()] == [
            "ext:laned:planner"]

    def test_a_vanished_extensions_configuration_survives_a_full_map_save(
            self, temp_db, bare):
        """The models panel PUTs the whole map, built from the rows it
        rendered. A disabled extension's lane is not rendered, so without the
        carry-through its configuration -- the HOST's work -- would be
        silently deleted by the next unrelated save. Removal takes the code,
        never the host's choices: the same rule that leaves
        `world["ext:<id>"]` alone on remove."""
        stored = {
            "default": {"provider": "frontier", "model": "big"},
            "ext:gone:planner": {"provider": "cheap", "model": "small"},
        }
        incoming = {"default": {"provider": "frontier", "model": "big"}}
        merged = extension_runtime.keep_orphan_lane_rows(stored, incoming)
        assert merged["ext:gone:planner"] == {"provider": "cheap",
                                              "model": "small"}
        assert merged["default"] == incoming["default"]

    def test_a_live_lane_omitted_from_the_save_was_cleared_and_stays_cleared(
            self, temp_db, bare):
        """The other half of the split, without which a host could never
        unset a lane: a LIVE lane's row was rendered, so its omission from
        the body is the host clearing it, not the panel not knowing it."""
        role = bare.add_model_lane("planner")
        stored = {
            "default": {"provider": "frontier", "model": "big"},
            role: {"provider": "cheap", "model": "small"},
        }
        incoming = {"default": {"provider": "frontier", "model": "big"}}
        merged = extension_runtime.keep_orphan_lane_rows(stored, incoming)
        assert role not in merged

    def test_an_orphan_row_breaks_no_read(self, temp_db, monkeypatch):
        """A stored configuration for a lane whose extension is gone must be
        inert, not explosive: `agent_models` parses, host roles resolve, and
        the orphan key resolves too (its extension could be re-enabled
        mid-process and its calls must not 500 in the meantime)."""
        from core.db import set_setting
        set_setting("agent_models", json.dumps({
            "default": {"provider": "frontier", "model": "big"},
            "ext:gone:planner": {"provider": "dead", "model": "small"},
        }))
        _stub_provider(monkeypatch)
        prov, model, _cfg = providers.resolve_role("director")
        assert (prov["name"], model) == ("frontier", "big")
        prov, model, _cfg = providers.resolve_role("ext:gone:planner")
        assert (prov["name"], model) == ("dead", "small")


    def test_the_settings_route_actually_carries_the_orphan_through(
            self, temp_db, ext_root):
        """The policy above is only real if the PUT route calls it -- this is
        the wiring test, over the same route the panel's Save button hits."""
        from fastapi.testclient import TestClient
        from web import app as app_module
        from web import guest_access as guest
        from core.db import get_setting, set_setting

        set_setting("agent_models", json.dumps({
            "default": {"provider": "frontier", "model": "big"},
            "ext:gone:planner": {"provider": "cheap", "model": "small"},
        }))
        guest.reset_host_account()
        try:
            with TestClient(app_module.app) as client:
                r = client.post("/api/auth/setup",
                                json={"username": "host",
                                      "password": "pw12345"})
                assert r.status_code == 200, r.text
                r = client.put("/api/agent_models", json={
                    "default": {"provider": "frontier", "model": "bigger"}})
                assert r.status_code == 200, r.text
        finally:
            guest.reset_host_account()

        stored = json.loads(get_setting("agent_models"))
        assert stored["default"]["model"] == "bigger"
        assert stored["ext:gone:planner"] == {"provider": "cheap",
                                              "model": "small"}


# ------------------------------------------------- nothing installed at all


class TestNothingInstalled:
    def test_no_extensions_means_no_lanes_and_untouched_settings(
            self, temp_db, ext_root):
        """The engine must behave identically with nothing installed: an
        empty registry, and a full-map save that passes through unchanged --
        zero new rows, byte-identical stored settings."""
        assert extension_runtime.registered_model_lanes() == []
        incoming = {"default": {"provider": "frontier", "model": "big"}}
        assert extension_runtime.keep_orphan_lane_rows({}, incoming) == incoming
        assert extension_runtime.keep_orphan_lane_rows(
            {"narrator": {"provider": "a", "model": "b"}}, incoming) == incoming
