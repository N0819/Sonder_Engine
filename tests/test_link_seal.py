"""A link that chooses who crosses and yields only to sustained force.

The owner's shrine (2026-10-03) keeps a Seal between a cavern and a divine
realm: freestanding, seen through, crossed by one goddess and nobody else,
and breakable -- "not a fragile thing", but "some enemy shouldn't be able to
break it instantly"; mending is "more prose determined than time based".
Hand-made scenes; the names are illustrations, not the rule.
"""

from __future__ import annotations

import copy

from agents.director import _unreachable_position_writes
from world.spatial import (LINK_STEP_SECONDS, apply_transit_dock_edges,
                           merge_scene_with_diff, passable_route_exists,
                           spatial_rel)


def _scene(**link):
    base = {"rooms": ["cavern", "realm"], "phase": "closed"}
    base.update(link)
    return {
        "rooms": {
            "cavern": {"name": "Cavern", "desc": "Steam.", "adjacent": [], "zone": "shrine"},
            "realm": {"name": "Realm", "desc": "Light.", "adjacent": [], "zone": "realm"},
        },
        "entities": {"seal": {"name": "The Seal", "kind": "portal",
                              "enclosure": "transparent",
                              "state": {"link": base}}},
        "positions": {"Goddess": "realm", "Raider": "cavern"},
    }


def test_a_closed_see_through_link_is_a_window_crossed_only_by_whom_it_admits():
    sc = _scene(admits=["goddess"])
    apply_transit_dock_edges(sc)
    assert spatial_rel(sc, "cavern", "realm")["barrier"] == "window"
    assert not passable_route_exists(sc, "cavern", "realm")
    assert not passable_route_exists(sc, "cavern", "realm", body="Raider")
    assert passable_route_exists(sc, "realm", "cavern", body="Goddess")
    assert passable_route_exists(sc, "cavern", "realm", body="Goddess")


def test_an_opaque_closed_link_that_admits_someone_is_a_wall_to_everyone_else():
    sc = _scene(admits=["goddess"])
    sc["entities"]["seal"].pop("enclosure")
    apply_transit_dock_edges(sc)
    assert spatial_rel(sc, "cavern", "realm")["barrier"] == "wall"
    assert passable_route_exists(sc, "realm", "cavern", body="goddess")
    assert not passable_route_exists(sc, "realm", "cavern", body="Raider")


def test_a_closed_opaque_link_with_no_one_admitted_joins_nothing_as_before():
    sc = _scene()
    sc["entities"]["seal"].pop("enclosure")
    apply_transit_dock_edges(sc)
    assert spatial_rel(sc, "cavern", "realm")["barrier"] != "wall"
    assert not sc["rooms"]["cavern"]["adjacent"]


def test_cracked_lets_sound_through_and_broken_is_open_to_everyone():
    sc = _scene(admits=["goddess"], condition="cracked")
    apply_transit_dock_edges(sc)
    assert spatial_rel(sc, "cavern", "realm")["barrier"] == "bars"
    assert not passable_route_exists(sc, "cavern", "realm", body="Raider")
    sc["entities"]["seal"]["state"]["link"]["condition"] = "broken"
    apply_transit_dock_edges(sc)
    assert spatial_rel(sc, "cavern", "realm")["barrier"] == "open_door"
    assert passable_route_exists(sc, "cavern", "realm", body="Raider")
    assert passable_route_exists(sc, "realm", "cavern")


def _beat(scene, condition, clock):
    diff = {"entities": {"seal": {"name": "The Seal",
                                  "state": {"link": {"condition": condition}}}}}
    return merge_scene_with_diff(scene, diff, clock_seconds=clock)


def _condition(scene):
    return scene["entities"]["seal"]["state"]["link"].get("condition")


def test_a_write_of_one_link_field_keeps_the_rooms_it_joins():
    """`{"link": {"phase": "closed"}}` replaced the whole link, dropping
    `rooms`, and the portal ceased to exist."""
    sc = _scene(admits=["goddess"])
    merged = merge_scene_with_diff(sc, {"entities": {"seal": {
        "name": "The Seal", "state": {"link": {"phase": "open"}}}}})
    link = merged["entities"]["seal"]["state"]["link"]
    assert link["rooms"] == ["cavern", "realm"] and link["admits"] == ["goddess"]
    assert spatial_rel(merged, "cavern", "realm")["barrier"] == "open_door"


def test_no_beat_breaks_a_link_outright_and_each_further_rung_waits():
    sc = _scene(admits=["goddess"])
    t0 = 1_000_000.0
    after = _beat(sc, "broken", t0)
    assert _condition(after) == "strained"              # one rung, the first free
    again = _beat(after, "broken", t0 + 60)
    assert _condition(again) == "strained"              # too soon for the next
    later = _beat(again, "broken", t0 + LINK_STEP_SECONDS)
    assert _condition(later) == "cracked"
    last = _beat(later, "broken", t0 + 2 * LINK_STEP_SECONDS)
    assert _condition(last) == "broken"
    assert spatial_rel(last, "cavern", "realm")["barrier"] == "open_door"


def test_the_refusal_is_reported_to_the_director():
    report = []
    diff = {"entities": {"seal": {"name": "The Seal",
                                  "state": {"link": {"condition": "broken"}}}}}
    merge_scene_with_diff(_scene(), diff, clock_seconds=5.0, crossing_report=report)
    assert any("The Seal" in note and "strained" in note for note in report)


def test_mending_is_never_held_back():
    sc = _scene(condition="cracked", condition_since=10.0)
    mended = _beat(sc, "intact", 11.0)
    assert _condition(mended) == "intact"


def test_an_edit_outside_a_beat_sets_the_condition_freely():
    merged = merge_scene_with_diff(_scene(), {"entities": {"seal": {
        "name": "The Seal", "state": {"link": {"condition": "broken"}}}}})
    assert _condition(merged) == "broken"


def test_the_condition_stamp_is_the_engines_not_the_models():
    sc = _scene(condition="strained", condition_since=100.0)
    diff = {"entities": {"seal": {"name": "The Seal", "state": {"link": {
        "condition": "cracked", "condition_since": -1e9}}}}}
    merged = merge_scene_with_diff(sc, diff, clock_seconds=200.0)
    assert _condition(merged) == "strained"


def test_only_the_admitted_body_is_moved_through_by_the_position_floor():
    sc = _scene(admits=["goddess"])
    apply_transit_dock_edges(sc)
    after = copy.deepcopy(sc)
    refused = _unreachable_position_writes(
        sc, after, {"Goddess": "cavern", "Raider": "realm"}, ["Goddess", "Raider"])
    assert [r[0] for r in refused] == ["Raider"]


def test_the_narrator_is_told_how_worn_a_seal_it_can_see_is():
    from agents.narration import _visible_portal_states
    sc = _scene(admits=["goddess"], condition="cracked")
    apply_transit_dock_edges(sc)
    assert _visible_portal_states(sc, "cavern", {"cavern", "realm"})["The Seal"] == "shut, cracked"
    sc["entities"]["seal"]["state"]["link"]["condition"] = "broken"
    assert _visible_portal_states(sc, "cavern", {"cavern", "realm"})["The Seal"] == "open, broken"


def test_the_far_side_is_seen_through_a_closed_see_through_link_and_not_an_opaque_one():
    from world.spatial import visible_adjacent_rooms
    sc = _scene(admits=["goddess"])
    apply_transit_dock_edges(sc)
    seen = lambda: {r["room_id"] for r in visible_adjacent_rooms(sc, "cavern")}
    assert "realm" in seen()
    sc["entities"]["seal"].pop("enclosure")
    apply_transit_dock_edges(sc)
    assert "realm" not in seen()
