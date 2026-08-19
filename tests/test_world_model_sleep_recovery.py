"""MASTER-021 / docs/UNBUILT.md 1.3: sleep is an awareness fact, and it must
reach the survival tick.

`tick_vitals(..., asleep=)` was derived exclusively from
`scene.contained[x]["mode"] == "asleep"` -- a CONTAINMENT vocabulary
(carried/held/pocket/enclosed), never an awareness level -- so the set was
always effectively empty and nobody has ever recovered stamina by sleeping:
a character sleeping eight hours on a stone floor DRAINED instead. Awareness
lives in the conditions ledger (`story.scene.AWARENESS_LEVELS`, read via
`awareness_map`), a layer above `world/`, which this package must not reach
up into -- so the seam is an explicit `sleeping=` argument on
`merge_scene_with_diff`, computed by the caller at the commit boundary.

The caller-side half (persist/commit_scene_state.py computing sleepers from
`awareness_map` and passing them) is outside this change's file ownership;
these tests pin the seam itself so the wiring has a contract to land on.
"""

from __future__ import annotations

from world.spatial import merge_scene_with_diff
from world.survival import _SLEEP_STAMINA_PER_HOUR


def _scene(**vitals_overrides):
    vitals = {"stamina": 0.5, "air": 1.0}
    vitals.update(vitals_overrides)
    return {
        "rooms": {"cell": {"name": "Cell", "adjacent": []}},
        "positions": {"Mora": "cell"},
        "entities": {}, "attire": {}, "overlays": {},
        "vitals": {"Mora": dict(vitals)},
    }


EIGHT_HOURS = {"time": {"duration_seconds": 8 * 3600}}


def _stamina(merged):
    return merged["vitals"]["Mora"]["stamina"]


def test_a_named_sleeper_recovers_at_the_sleep_rate():
    merged = merge_scene_with_diff(_scene(), dict(EIGHT_HOURS),
                                   sleeping={"Mora"})
    expected = min(1.0, 0.5 + 8 * _SLEEP_STAMINA_PER_HOUR)
    assert abs(_stamina(merged) - expected) < 1e-6


def test_without_the_argument_the_floor_still_drains():
    """The pre-fix behaviour, pinned as the contrast: not asleep, not on a
    rest surface -- eight hours pass and stamina does not rise."""
    merged = merge_scene_with_diff(_scene(), dict(EIGHT_HOURS))
    assert _stamina(merged) <= 0.5


def test_containment_modes_do_not_imply_sleep():
    """Being carried, pocketed or enclosed is a containment relation, never
    an awareness level."""
    scene = _scene()
    scene["entities"]["Satchel"] = {"kind": "container", "name": "Satchel"}
    scene["contained"] = {"Mora": {"in": "Satchel", "mode": "carried"}}
    merged = merge_scene_with_diff(scene, dict(EIGHT_HOURS))
    assert _stamina(merged) <= 0.5


def test_the_accidental_containment_spelling_keeps_what_it_had():
    """The legacy reading is kept as a UNION, not replaced: it cannot
    subtract from the caller's set, and a stored `mode: "asleep"` -- the
    only spelling the old code ever honoured -- still counts."""
    scene = _scene()
    scene["entities"]["Bedroll"] = {"kind": "container", "name": "Bedroll"}
    scene["contained"] = {"Mora": {"in": "Bedroll", "mode": "asleep"}}
    merged = merge_scene_with_diff(scene, dict(EIGHT_HOURS))
    expected = min(1.0, 0.5 + 8 * _SLEEP_STAMINA_PER_HOUR)
    assert abs(_stamina(merged) - expected) < 1e-6
