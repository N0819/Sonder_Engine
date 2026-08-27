"""A room's exits include the doorways only its neighbour declared.

The room graph is undirected by this package's stated doctrine
(`neighbor_map`) and by the spatial specialist's own prompt, but five readers
were never told: `egocentric_frame` (and everything built on it --
`spatial_digest`, `room_layout`'s exits, the Director's exits, a character's
spatial frame, perception's rear arc), `corridor_sightlines`, `sprint_reach`
and `survival.is_sealed_in` all read `room["adjacent"]` alone.

Measured cause, live run 3: `merge_scene_with_diff` upserts only the edges a
diff names, the spatial prompt put the connecting edge on the NEW room, and
`connect_orphan_new_rooms` deliberately skips a room something already points
AT -- so the room a story starts in ends `adjacent: []` while both later rooms
point back at it with named doorways. 20 such sink rooms in the live corpus,
9 of them occupied; 117 of 374 room pairs (31.3%) declared from one side only,
and ZERO of the 16 `one_way_window` declarations among them.

Nothing is blanket-symmetrised on the WRITE side. The reciprocal is derived at
READ time by `effective_adjacent`, and a passage that really is one-way says
so with a FIELD (`passage_from`), the way `sight_from` already carries the
direction of a one-way window -- because one-sidedness is how edges get
written and can never be what one-way looks like.
"""
from __future__ import annotations

import pytest

from world.spatial import (
    corridor_sightlines,
    edge_passable,
    effective_adjacent,
    merge_scene_with_diff,
    normalize_scene_barriers,
    passable_path,
    passable_route_exists,
    room_layout,
    spatial_digest,
    sprint_reach,
)
from world.survival import is_sealed_in

ORIGIN, BACK, FAR = "r_origin", "r_back", "r_far"


def _sink_scene(observer_facing="n"):
    """The run-3 shape: the origin declares nothing, two rooms point at it."""
    return {
        "rooms": {
            ORIGIN: {"name": "First Place", "desc": "where it began",
                     "light": "lit", "adjacent": []},
            BACK: {"name": "Second Place", "desc": "later", "light": "lit",
                   "adjacent": [{"to": ORIGIN, "barrier": "open_door",
                                 "dir": "s", "name": "the near door"}]},
            FAR: {"name": "Third Place", "desc": "later still", "light": "lit",
                  "adjacent": [{"to": ORIGIN, "barrier": "open", "dir": "w"}]},
        },
        "positions": {"OBS": ORIGIN},
        "orientation": {"OBS": {"came_from": None, "facing": observer_facing}},
    }


# --------------------------------------------------------------------------
# The derivation itself


def test_a_room_that_declared_nothing_still_has_its_doorways():
    edges = effective_adjacent(_sink_scene(), ORIGIN)
    assert {e["to"] for e in edges} == {BACK, FAR}
    assert all(e.get("implicit") for e in edges)


def test_the_derived_edge_reverses_the_bearing():
    by_to = {e["to"]: e for e in effective_adjacent(_sink_scene(), ORIGIN)}
    assert by_to[BACK]["dir"] == "n"      # declared 's' from the far side
    assert by_to[FAR]["dir"] == "e"       # declared 'w' from the far side
    assert by_to[BACK]["barrier"] == "open_door"
    assert by_to[BACK]["name"] == "the near door"


def test_the_rooms_own_declaration_wins_its_target():
    scene = _sink_scene()
    scene["rooms"][ORIGIN]["adjacent"] = [
        {"to": BACK, "barrier": "closed_door", "dir": "n"}]
    by_to = {e["to"]: e for e in effective_adjacent(scene, ORIGIN)}
    assert by_to[BACK]["barrier"] == "closed_door"
    assert not by_to[BACK].get("implicit")
    assert by_to[FAR].get("implicit") is True


def test_a_far_side_wall_is_not_derived_into_a_doorway():
    scene = _sink_scene()
    scene["rooms"][FAR]["adjacent"] = [{"to": ORIGIN, "barrier": "wall"}]
    assert {e["to"] for e in effective_adjacent(scene, ORIGIN)} == {BACK}


def test_an_unreadable_barrier_word_is_not_derived_either():
    """`normalize_barrier` folds anything it cannot read to `wall`, and a word
    nothing could read is not evidence of a way through."""
    scene = _sink_scene()
    scene["rooms"][FAR]["adjacent"] = [
        {"to": ORIGIN, "barrier": "a thing nobody named"}]
    assert {e["to"] for e in effective_adjacent(scene, ORIGIN)} == {BACK}


def test_the_derivation_writes_nothing_back():
    scene = _sink_scene()
    effective_adjacent(scene, ORIGIN)
    assert scene["rooms"][ORIGIN]["adjacent"] == []


# --------------------------------------------------------------------------
# What the asymmetry cost, reader by reader


def test_the_exits_and_the_anchors_of_one_payload_now_agree():
    """`room_layout` reported two doorways as anchors and no exits at all in
    the same payload -- `effective_anchors` reads both sides, `spatial_digest`
    did not."""
    layout = room_layout(_sink_scene(), "OBS")
    assert layout["exits"], "the look-around offered no way out of the room"
    assert len(layout["anchors"]) == len(
        [ref for refs in layout["exits"].values() for ref in refs])


def test_the_narrator_digest_names_both_doorways():
    digest = spatial_digest(_sink_scene(), "OBS")
    named = {ref["room"] for refs in digest.values() for ref in refs}
    assert named == {"Second Place", "Third Place"}


def test_a_run_can_leave_the_room_a_story_started_in():
    assert {tuple(o["path"]) for o in sprint_reach(_sink_scene(), ORIGIN)} == \
        {(BACK,), (FAR,)}


def test_sight_runs_down_a_passage_declared_from_the_far_end():
    assert {line["dir"] for line in corridor_sightlines(_sink_scene(), ORIGIN)} \
        == {"n", "e"}


def test_a_room_with_two_doorways_is_not_reported_a_dead_end():
    """The exact "invent a dead end" error `_onward_exits` was repaired for,
    still live in the onward walks of both sight and running."""
    scene = _sink_scene()
    scene["rooms"][BACK]["adjacent"].append(
        {"to": "r_side", "barrier": "open", "dir": "n"})
    scene["rooms"]["r_side"] = {"name": "Fourth Place", "light": "lit",
                                "adjacent": []}
    stops = {tuple(o["path"]): o["stops"] for o in sprint_reach(scene, BACK)}
    # Running from BACK through the origin: the origin has a second doorway.
    assert stops[(ORIGIN, FAR)] == "dead_end"       # FAR really is one
    assert (ORIGIN,) not in stops


def test_a_body_is_not_sealed_in_by_a_doorway_the_outside_declared():
    scene = {
        "rooms": {
            "hold": {"name": "inside", "parent_entity": "e1",
                     "adjacent": []},
            "yard": {"name": "outside",
                     "adjacent": [{"to": "hold", "barrier": "membrane"}]},
        },
        "positions": {"OBS": "hold"},
        "entities": {"e1": {"name": "the holder"}},
    }
    assert is_sealed_in(scene, "OBS") is False


# --------------------------------------------------------------------------
# The firewall direction: gaining edges must SUBTRACT


def _facing_scene(facing):
    scene = _sink_scene(observer_facing=facing)
    del scene["rooms"][FAR]
    scene["rooms"][BACK]["adjacent"][0]["barrier"] = "open"
    return scene


def test_a_room_at_the_observers_back_is_withheld_even_when_far_declared():
    from agents.perception import _behind_rooms, _visible_rooms_for

    scene = _facing_scene("s")          # doorway lies to the north
    assert _behind_rooms(scene, "OBS") == [BACK]
    assert [r["room_id"] for r in _visible_rooms_for(scene, "OBS", ORIGIN)] == []


def test_the_rear_ARC_is_gated_on_a_far_declared_doorway_too():
    """`egocentric_frame` collapses behind_left/behind_right into the LATERAL
    buckets -- correctly, since an exit behind your left shoulder is the one
    on your left when prose places it -- so `_behind_rooms` has a second pass
    of its own for the rear arc, and that pass read `room["adjacent"]` alone.
    A doorway 135 degrees behind an observer, declared only from the far side,
    was therefore ungated twice over."""
    from agents.perception import _behind_rooms, _visible_rooms_for

    scene = _facing_scene("n")
    scene["rooms"][BACK]["adjacent"][0]["dir"] = "ne"    # reads 'sw' from here
    assert _behind_rooms(scene, "OBS") == [BACK]
    assert [r["room_id"] for r in _visible_rooms_for(scene, "OBS", ORIGIN)] == []


def test_the_same_room_is_delivered_when_the_observer_faces_it():
    from agents.perception import _visible_rooms_for

    scene = _facing_scene("n")
    assert [r["room_id"] for r in _visible_rooms_for(scene, "OBS", ORIGIN)] \
        == [BACK]


# --------------------------------------------------------------------------
# A deliberately one-way passage stays one-way


def _chute_scene():
    """Declared from BOTH ends, the universal habit -- and both agree."""
    edge = {"barrier": "open", "passage_from": ORIGIN}
    return {
        "rooms": {
            ORIGIN: {"name": "Above", "light": "lit",
                     "adjacent": [{"to": BACK, "dir": "s", **edge}]},
            BACK: {"name": "Below", "light": "lit",
                   "adjacent": [{"to": ORIGIN, "dir": "n", **edge}]},
        },
        "positions": {"OBS": ORIGIN},
        "orientation": {},
    }


def test_a_one_way_passage_is_crossable_only_from_the_room_it_names():
    scene = _chute_scene()
    down = scene["rooms"][ORIGIN]["adjacent"][0]
    up = scene["rooms"][BACK]["adjacent"][0]
    assert edge_passable(down, ORIGIN) is True
    assert edge_passable(up, BACK) is False


def test_the_derived_reciprocal_carries_the_direction_rather_than_losing_it():
    scene = _chute_scene()
    scene["rooms"][BACK]["adjacent"] = []       # written once, from above
    derived = effective_adjacent(scene, BACK)
    assert [e["to"] for e in derived] == [ORIGIN]
    assert edge_passable(derived[0], BACK) is False
    assert edge_passable(derived[0], ORIGIN) is True


def test_a_route_runs_one_way_and_not_the_other():
    scene = _chute_scene()
    assert passable_route_exists(scene, ORIGIN, BACK) is True
    assert passable_route_exists(scene, BACK, ORIGIN) is False
    assert passable_path(scene, ORIGIN, BACK) == [BACK]
    assert passable_path(scene, BACK, ORIGIN) == []


def test_a_run_does_not_go_up_the_chute():
    scene = _chute_scene()
    assert [o["path"] for o in sprint_reach(scene, ORIGIN)] == [[BACK]]
    assert sprint_reach(scene, BACK) == []


def test_a_one_way_passage_inward_seals_its_occupant():
    scene = {
        "rooms": {
            "hold": {"name": "inside", "parent_entity": "e1",
                     "adjacent": []},
            "yard": {"name": "outside",
                     "adjacent": [{"to": "hold", "barrier": "membrane",
                                   "passage_from": "yard"}]},
        },
        "positions": {"OBS": "hold"},
        "entities": {"e1": {"name": "the holder"}},
    }
    assert is_sealed_in(scene, "OBS") is True


def test_sight_and_sound_still_cross_a_one_way_passage_both_ways():
    """Direction is a fact about PASSAGE. A chute you cannot climb is still a
    chute you can see and shout up."""
    from world.spatial import hear_level, sight_level, spatial_rel

    scene = _chute_scene()
    rel = spatial_rel(scene, BACK, ORIGIN)
    assert sight_level(rel) == "full"
    assert hear_level(rel, "normal") == "full"


def test_a_direction_naming_neither_end_is_dropped_at_normalisation():
    """A value that names the mechanism instead of a room would otherwise
    seal the passage from BOTH sides, silently -- the one failure a directed
    edge must never have. Same refusal `sight_direction` makes."""
    scene = _chute_scene()
    scene["rooms"][ORIGIN]["adjacent"][0]["passage_from"] = "the chute itself"
    normalize_scene_barriers(scene)
    assert "passage_from" not in scene["rooms"][ORIGIN]["adjacent"][0]
    assert scene["rooms"][BACK]["adjacent"][0]["passage_from"] == ORIGIN


# --------------------------------------------------------------------------
# End to end, through the real merge


def test_the_merge_still_writes_no_reciprocal_and_the_read_supplies_it():
    """Deliberately NOT fixed on the write side: symmetrising the stored graph
    would not repair the 20 rooms already on disk, would have to be sequenced
    against `stamp_sight_direction`, and would add a writer to a subsystem
    whose doctrine is that silence is never an assertion."""
    prev = {"rooms": {ORIGIN: {"name": "First Place", "desc": "where it began",
                               "adjacent": []}},
            "positions": {"PC": ORIGIN}}
    diff = {"rooms": {BACK: {"name": "Second Place", "desc": "later",
                             "adjacent": [{"to": ORIGIN, "barrier": "open",
                                           "dir": "s"}]}},
            "positions": {"PC": BACK}}
    merged = merge_scene_with_diff(prev, diff)
    assert merged["rooms"][ORIGIN]["adjacent"] == []
    assert {e["to"] for e in effective_adjacent(merged, ORIGIN)} == {BACK}


@pytest.mark.parametrize("field", ["passage_from"])
def test_the_direction_field_survives_a_redeclaration_that_omits_it(field):
    prev = {"rooms": {
        ORIGIN: {"name": "Above",
                 "adjacent": [{"to": BACK, "barrier": "open",
                               field: ORIGIN}]},
        BACK: {"name": "Below", "adjacent": []}}}
    diff = {"rooms": {ORIGIN: {"adjacent": [{"to": BACK, "barrier": "open",
                                             "dir": "s"}]}}}
    merged = merge_scene_with_diff(prev, diff)
    assert merged["rooms"][ORIGIN]["adjacent"][0][field] == ORIGIN
