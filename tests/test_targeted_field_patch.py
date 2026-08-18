"""The cheap rung of the repair ladder.

One malformed field used to cost the whole beat re-authored on the stage's
own model. Measured live: `state_assertions.overlays` arrived as a list
instead of a name-keyed map and bought a 4.2s full round-trip on the
Director -- for a channel a specialist replaced immediately afterwards; a
character's decision-review retry cost 36.3s the same way.

The validator already names the path and the reason, so the fix is a small
call about those fields alone, spliced back deterministically. What makes a
cheap model safe here is not trust: it is that nothing outside the failed
paths can move.
"""
from __future__ import annotations

import json

from llm import llm_quality


def _fake_patch(monkeypatch, reply, seen=None):
    def fake(role, system, user, **kwargs):
        if seen is not None:
            seen.append({"role": role, "user": json.loads(user),
                         "max_tokens": kwargs.get("max_tokens")})
        return reply
    monkeypatch.setattr(llm_quality, "chat_complete", fake)


def test_it_asks_only_about_the_fields_that_failed(monkeypatch):
    seen = []
    _fake_patch(monkeypatch, json.dumps(
        {"state_assertions.overlays": {"Hinami": ["flushed to the ears"]}}),
        seen)
    parsed = {
        "summary": "A long beat that must not be re-authored.",
        "state_assertions": {"overlays": ["flushed to the ears"],
                             "poses": {"Hinami": {"posture": "lying back"}}},
    }
    out = llm_quality._targeted_field_patch(
        "director_interpret", parsed,
        ["state_assertions.overlays: value is not a valid dict"], {})

    assert out["state_assertions"]["overlays"] == {
        "Hinami": ["flushed to the ears"]}
    # Everything else is byte-identical -- the beat was never re-authored.
    assert out["summary"] == parsed["summary"]
    assert out["state_assertions"]["poses"] == parsed["state_assertions"]["poses"]
    # Asked on the dedicated cheap lane, and handed only the broken fragment.
    assert seen[0]["role"] == "repair"
    assert list(seen[0]["user"]["invalid_fragments"]) == [
        "state_assertions.overlays"]
    assert "summary" not in json.dumps(seen[0]["user"])


def test_a_patch_naming_an_uncomplained_field_cannot_move_it(monkeypatch):
    """The floor. A small model is safe here only because the splice
    refuses any path the validator did not name."""
    _fake_patch(monkeypatch, json.dumps({
        "state_assertions.overlays": {"Hinami": ["flushed"]},
        "summary": "a summary it was never asked about",
    }))
    parsed = {"summary": "the original",
              "state_assertions": {"overlays": ["flushed"]}}
    out = llm_quality._targeted_field_patch(
        "director_interpret", parsed,
        ["state_assertions.overlays: value is not a valid dict"], {})
    assert out["summary"] == "the original"


def test_it_falls_through_rather_than_guessing(monkeypatch):
    """Any doubt hands the beat to the full rebuild unchanged."""
    parsed = {"state_assertions": {"overlays": ["x"]}}
    errors = ["state_assertions.overlays: value is not a valid dict"]

    _fake_patch(monkeypatch, "not json at all")
    assert llm_quality._targeted_field_patch("s", parsed, errors, {}) is None

    _fake_patch(monkeypatch, json.dumps({"something.else": 1}))
    assert llm_quality._targeted_field_patch("s", parsed, errors, {}) is None

    _fake_patch(monkeypatch, json.dumps({"a": 1}))
    # A path the validator named but the output does not carry.
    assert llm_quality._targeted_field_patch(
        "s", parsed, ["nowhere.at.all: bad"], {}) is None


def test_paths_reach_into_lists():
    parsed = {"dialogue_log": [{"speaker": "A"}, {"speaker": 7}]}
    value, found = llm_quality._dig(parsed, "dialogue_log.1.speaker")
    assert found and value == 7
    llm_quality._place(parsed, "dialogue_log.1.speaker", "B")
    assert parsed["dialogue_log"][1]["speaker"] == "B"
    assert parsed["dialogue_log"][0]["speaker"] == "A"


def test_repair_is_its_own_configurable_role():
    """Separable from `utility`, which also carries autobiographical
    consolidation: a host may want a 3000 tok/s open model fixing shapes
    and something else writing summaries.

    Unset it follows `default` like every other row -- it used to ride
    `utility` and through it `mapping`, which put the cheap patcher one
    hidden hop from a row the host never looked at. A host who wants a fast
    patcher sets this row; the panel says so on its face. See
    `tests/test_provider_fallbacks.py`."""
    from llm import providers

    assert "repair" in providers.ROLES
    assert providers.ROLE_FALLBACKS == {}
