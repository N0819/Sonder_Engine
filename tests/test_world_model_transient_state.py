"""MASTER-036 / docs/UNBUILT.md 1.10: momentary entity state must not outlive
its beat.

`_merge_entity` merges `state` key-wise and the doctrine is silence-is-never-
an-erasure -- right for a held wrench, wrong for a breath: an omitted key
survived forever, and `composer.body_state_percept` reads `activity` back to
the subject's OWN mind (interoception, source "you"), so a body told once it
was running kept perceiving itself running and each later model call received
that as current evidence. Measured stuck verbatim for dozens of beats:
`"breath": "caught"`, `"voice_quality": "held_breath_steadying"`.

The fix is a narrow transient allowlist that expires on the next merge unless
re-asserted -- NOT a rejection of undeclared keys (`state` is deliberately
open free text; an earlier skip-the-update attempt was reverted as durable
corruption) and NOT an expiry of durable configuration (posture, held items,
transit all keep today's merge). `activity` is deliberately NOT in the
allowlist yet: tests/test_body_position.py pins it never-touched as
load-bearing standing state, so expiring it means first deciding that
contract -- the remaining half of docs/UNBUILT.md 1.10.
"""

from __future__ import annotations

from world.spatial import merge_scene_with_diff


def _scene():
    return {
        "rooms": {"cell": {"name": "Cell", "adjacent": []}},
        "positions": {"mora_uid": "cell"},
        "entities": {"mora_uid": {
            "kind": "person", "name": "Mora",
            "state": {
                "activity": "running for the stair",
                "breath": "caught",
                "voice_quality": "held_breath_steadying",
                "posture": "crouched low",
                "held_items": ["wrench"],
                "transit": {"phase": "boarding"},
            },
        }},
        "attire": {}, "overlays": {},
    }


def _state(merged):
    return merged["entities"]["mora_uid"]["state"]


class TestExpiry:
    def test_momentary_keys_expire_when_the_diff_is_silent(self):
        merged = merge_scene_with_diff(_scene(), {})
        for key in ("breath", "voice_quality"):
            assert key not in _state(merged), key

    def test_they_expire_even_when_the_entity_itself_is_untouched(self):
        """The entity the diff is silent about is exactly the one whose
        caught breath has gone stale -- expiry cannot be scoped to entities
        the diff happens to mention."""
        merged = merge_scene_with_diff(_scene(), {
            "entities": {"someone_else": {"kind": "person", "name": "Tavi"}}})
        assert "breath" not in _state(merged)

    def test_durable_state_keeps_the_silence_doctrine(self):
        merged = merge_scene_with_diff(_scene(), {})
        state = _state(merged)
        assert state["posture"] == "crouched low"
        assert state["held_items"] == ["wrench"]
        assert state["transit"] == {"phase": "boarding"}
        # `activity` deliberately durable for now: pinned load-bearing by
        # tests/test_body_position.py; the remaining half of UNBUILT 1.10.
        assert state["activity"] == "running for the stair"

    def test_reassertion_carries_it_forward(self):
        merged = merge_scene_with_diff(_scene(), {
            "entities": {"mora_uid": {
                "state": {"breath": "steadying now"}}}})
        assert _state(merged)["breath"] == "steadying now"

    def test_assertion_by_display_name_reaches_the_id_keyed_entity(self):
        """A diff may key one body by id, name or alias; expiry must honour
        whichever spelling the assertion used."""
        merged = merge_scene_with_diff(_scene(), {
            "entities": {"Mora": {"state": {"breath": "ragged"}}}})
        entities = merged["entities"]
        held = [e.get("state", {}).get("breath")
                for e in entities.values() if isinstance(e, dict)]
        assert "ragged" in held


class TestWhatTheOwnMindStillReads:
    def test_the_interoception_percept_survives_the_sweep(self):
        """Entity state feeds `composer.body_state_percept` (the subject's
        own interoception, source "you"); the sweep must take only the
        momentary keys, never the durable body facts the percept renders."""
        from agents.composer import body_state_percept

        merged = merge_scene_with_diff(_scene(), {})
        percept = body_state_percept(_state(merged))
        assert percept is not None
        assert percept.data["posture"] == "crouched low"
        assert percept.data["held_items"] == ["wrench"]
