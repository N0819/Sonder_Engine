"""A payload hook that fails leaves the payload exactly as the engine
assembled it, and every change a hook makes lands attributed or not at all.

Audit 2026-11-01 (web_routes_extensions F9, CONFIRMED by snippet): the three
payload seams handed a hook the payload they were about to send, so a hook
that edited in place and THEN raised -- or, at the Director seam, edited in
place and returned `None`, the documented "leave it alone" -- kept its edit
while the skip path dropped the routing note: a character hook that set
`payload["forbidden_fact"]` and raised sent `{'perception': 'a hallway',
'forbidden_fact': 'the vault code is 4471'}` to the model with no note at
all. The existing throwing-hook tests raised WITHOUT mutating and compared
the returned object to itself, so they could not see it.
"""

from __future__ import annotations

import copy

import pytest

import extension_runtime

from tests.test_extensions import (  # noqa: F401 - fixtures are used by name
    _StubCtx, _chat, _enable, _write_extension, ext_root,
)


@pytest.fixture
def hooks(ext_root):
    _write_extension(ext_root, "router", {
        "id": "router", "version": "1.0.0", "ext_api": 1, "name": "Router",
        "capabilities": {"python": "extension.py"},
    }, {"extension.py": "def register(api):\n    pass\n"})
    _enable("router")
    return extension_runtime._apis["router"]


def _payload():
    return {"perception": {"view": "a hallway"}, "self": {"name": "Ash"}}


def test_a_character_hook_that_edits_then_raises_changes_nothing(temp_db, hooks):
    def leaky(payload, info):
        payload["forbidden_fact"] = "the vault code is 4471"
        payload["perception"]["view"] = "a hallway with the vault open"
        raise RuntimeError("half way through")

    hooks.on_character_payload(leaky)
    ctx = _StubCtx(chat_id=_chat(temp_db))
    payload = _payload()

    out = extension_runtime.dispatch_character_payload(ctx, 7, payload)

    assert out == _payload()
    assert payload == _payload()
    assert extension_runtime.routing_notes(ctx) == []
    assert extension_runtime.observer_failures()["router"] == 1


def test_a_narration_hook_that_edits_then_raises_changes_nothing(temp_db, hooks):
    def leaky(payload, info):
        payload["perception"]["view"] = "the thief's face, clearly"
        raise RuntimeError("half way through")

    hooks.on_narration_payload(leaky)
    ctx = _StubCtx(chat_id=_chat(temp_db))

    out = extension_runtime.dispatch_narration_payload(ctx, _payload())

    assert out == _payload()
    assert extension_runtime.routing_notes(ctx) == []
    assert extension_runtime.observer_failures()["router"] == 1


def test_a_director_hook_that_edits_then_raises_changes_nothing_and_is_counted(
        temp_db, hooks):
    def leaky(payload, info):
        payload["campaign_rule"] = "the vault is already open"
        raise RuntimeError("half way through")

    hooks.on_director_payload(leaky)
    ctx = _StubCtx(chat_id=_chat(temp_db))

    out = extension_runtime.dispatch_director_payload(ctx, _payload(),
                                                      phase="resolve")

    assert out == _payload()
    assert extension_runtime.routing_notes(ctx) == []
    assert extension_runtime.observer_failures()["router"] == 1


def test_a_director_hook_that_edits_in_place_and_returns_none_is_attributed(
        temp_db, hooks):
    def quiet(payload, info):
        payload["campaign_rule"] = "the vault is sealed"
        return None

    hooks.on_director_payload(quiet)
    ctx = _StubCtx(chat_id=_chat(temp_db))

    out = extension_runtime.dispatch_director_payload(ctx, _payload(),
                                                      phase="resolve")

    assert out["campaign_rule"] == "the vault is sealed"
    assert extension_runtime.routing_notes(ctx) == [
        {"ext": "router", "char_id": None, "scope": "director_resolve",
         "changed": ["campaign_rule"]}]


def test_a_hook_returning_a_non_dict_after_editing_changes_nothing(
        temp_db, hooks):
    def odd(payload, info):
        payload["perception"]["view"] = "somewhere else"
        return "not a payload"

    hooks.on_character_payload(odd)
    ctx = _StubCtx(chat_id=_chat(temp_db))
    payload = _payload()

    out = extension_runtime.dispatch_character_payload(ctx, 7, payload)

    assert out == _payload() and payload == _payload()
    assert extension_runtime.routing_notes(ctx) == []


def test_a_good_hook_after_a_failed_one_sees_the_assembled_payload(
        temp_db, ext_root):
    for name in ("a-fails", "b-reads"):
        _write_extension(ext_root, name, {
            "id": name, "version": "1.0.0", "ext_api": 1, "name": name,
            "capabilities": {"python": "extension.py"},
        }, {"extension.py": "def register(api):\n    pass\n"})
    _enable("a-fails", "b-reads")
    seen = []

    def fails(payload, info):
        payload["perception"]["view"] = "poisoned"
        raise RuntimeError("boom")

    extension_runtime._apis["a-fails"].on_character_payload(fails)
    extension_runtime._apis["b-reads"].on_character_payload(
        lambda payload, info: seen.append(copy.deepcopy(payload)))
    ctx = _StubCtx(chat_id=_chat(temp_db))

    extension_runtime.dispatch_character_payload(ctx, 7, _payload())

    assert seen == [_payload()]
