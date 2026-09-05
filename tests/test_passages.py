"""The passage record: one doorway, one object (`DESIGN_ROOM_FIDELITY.md` §5,
built 2026-09-05; `docs/UNBUILT.md` § 2.37's first residual).

F16 and F22 were one class: a doorway stored as two edges that can disagree,
so sight followed the side you stood on. `scene.passages[id] = {rooms,
barrier, name, material, width, vertical, state}` is the one record, edges
carry `passage: id`, and the five readers the note named -- `spatial_rel`,
`effective_adjacent`, `neighbor_map`, `_sight_neighbours` (through
`_placed_neighbours`) and `effective_anchors`' door derivation -- resolve
through it when an edge names one and per edge when it does not. The merge's
`sync_scene_passages` writes both edges from the record and lets the edge a
beat changed speak for it; `_mirror_symmetric_barriers` stays the answer for
edges with no passage. Additive: a scene with no `passages` reads byte for
byte as before, pinned here on every reader.
"""

from __future__ import annotations

import copy

from world.spatial import (
    _sight_neighbours, anchor_cells, effective_adjacent, effective_anchors,
    merge_scene_with_diff, neighbor_map, normalize_scene_passages, passage_of,
    resolve_edge, spatial_rel, sync_scene_passages,
)


def two_rooms(*, passage=True, a_barrier="closed_door", b_barrier=None,
              record=None):
    """A and B, A's edge east onto B; B's edge back only when `b_barrier`
    is given. With `passage`, both edges name the record."""
    a_edge = {"to": "b", "barrier": a_barrier, "dir": "e"}
    edges_b = []
    if b_barrier is not None:
        edges_b.append({"to": "a", "barrier": b_barrier, "dir": "w"})
    if passage:
        a_edge["passage"] = "a|b"
        for e in edges_b:
            e["passage"] = "a|b"
    sc = {"rooms": {"a": {"name": "A", "size": "small", "adjacent": [a_edge]},
                    "b": {"name": "B", "size": "small", "adjacent": edges_b}},
          "positions": {"P": "a", "Q": "b"}, "stations": {}, "entities": {},
          "orientation": {}, "poses": {}}
    if passage:
        sc["passages"] = {"a|b": dict(record or {"rooms": ["a", "b"], "barrier": "open_door"})}
    return sc


# ---------------------------------------------------------------------------
# The readers resolve through the passage
# ---------------------------------------------------------------------------

def test_every_reader_answers_the_passage_from_either_side():
    """A's edge says closed, B's says open, the passage says open_door: every
    reader says open_door from both rooms."""
    sc = two_rooms(a_barrier="closed_door", b_barrier="open")
    assert spatial_rel(sc, "a", "b")["barrier"] == "open_door"
    assert spatial_rel(sc, "b", "a")["barrier"] == "open_door"
    assert [e["barrier"] for e in effective_adjacent(sc, "a")] == ["open_door"]
    assert [e["barrier"] for e in effective_adjacent(sc, "b")] == ["open_door"]
    assert neighbor_map(sc, {"open_door"}) == {"a": {"b"}, "b": {"a"}}
    assert neighbor_map(sc, {"closed_door"}) == {}
    assert effective_anchors(sc, "a")["door:b"]["desc"] == "the open doorway"
    assert effective_anchors(sc, "b")["door:a"]["desc"] == "the open doorway"
    assert _sight_neighbours(sc, "a") == [("b", "e")]
    assert _sight_neighbours(sc, "b") == [("a", "w")]


def test_a_far_declared_doorway_resolves_too_and_the_passage_carries_its_name():
    sc = two_rooms(a_barrier="closed_door",
                   record={"rooms": ["a", "b"], "barrier": "open", "name": "the hatch",
                           "material": "iron", "width": 2})
    far = effective_adjacent(sc, "b")
    assert far[0]["implicit"] is True and far[0]["barrier"] == "open"
    assert far[0]["name"] == "the hatch" and far[0]["material"] == "iron"
    assert spatial_rel(sc, "b", "a")["material"] == "iron"
    # `width` is the doorway's aperture: two cells on the wall, from either
    # side (`_place_anchors` reads it on the implicit door anchor).
    assert len(anchor_cells(sc, "a")["door:b"]["cells"]) == 2
    assert len(anchor_cells(sc, "b")["door:a"]["cells"]) == 2


def test_resolve_edge_returns_the_same_object_when_nothing_is_named():
    sc = two_rooms(passage=False, b_barrier="open")
    edge = sc["rooms"]["a"]["adjacent"][0]
    assert resolve_edge(sc, edge) is edge
    assert passage_of(sc, edge) is None
    # A passage the scene does not hold, or one naming three rooms, is none.
    sc2 = two_rooms()
    sc2["rooms"]["a"]["adjacent"][0]["passage"] = "ghost"
    assert passage_of(sc2, sc2["rooms"]["a"]["adjacent"][0]) is None
    sc2["passages"]["a|b"]["rooms"] = ["a", "b", "c"]
    assert passage_of(sc2, {"to": "b", "passage": "a|b"}) is None


def test_a_one_way_window_is_never_forced_onto_an_edge():
    sc = two_rooms(a_barrier="one_way_window", b_barrier="wall",
                   record={"rooms": ["a", "b"], "barrier": "one_way_window"})
    sc["rooms"]["a"]["adjacent"][0]["sight_from"] = "a"
    assert effective_adjacent(sc, "a")[0]["barrier"] == "one_way_window"
    assert spatial_rel(sc, "a", "b")["barrier"] == "one_way_window"
    assert spatial_rel(sc, "b", "a")["barrier"] == "wall"


# ---------------------------------------------------------------------------
# The sync: both edges from either
# ---------------------------------------------------------------------------

def test_a_passage_write_writes_both_edges_and_mints_the_missing_one():
    sc = two_rooms(a_barrier="closed_door",
                   record={"rooms": ["a", "b"], "barrier": "open_door",
                           "name": "the hatch", "width": 2, "vertical": "up"})
    touched = sync_scene_passages(sc)
    assert touched == ["a|b"]
    a_edge = sc["rooms"]["a"]["adjacent"][0]
    b_edges = sc["rooms"]["b"]["adjacent"]
    assert len(b_edges) == 1 and b_edges[0]["to"] == "a"
    assert a_edge["barrier"] == "open_door" == b_edges[0]["barrier"]
    assert a_edge["name"] == "the hatch" == b_edges[0]["name"]
    assert a_edge["width"] == 2 == b_edges[0]["width"]
    assert a_edge["passage"] == "a|b" == b_edges[0]["passage"]
    # `vertical` is as seen from rooms[0]; the far edge gets its opposite.
    assert a_edge["vertical"] == "up" and b_edges[0]["vertical"] == "down"


def test_the_edge_a_beat_changed_speaks_for_the_passage_in_the_merge():
    prior = two_rooms(a_barrier="open_door", b_barrier="open_door")
    # The Director writes `closed_door` on B's edge alone.
    merged = merge_scene_with_diff(
        prior, {"rooms": {"b": {"adjacent": [{"to": "a", "barrier": "closed_door"}]}}})
    assert merged["passages"]["a|b"]["barrier"] == "closed_door"
    assert merged["rooms"]["a"]["adjacent"][0]["barrier"] == "closed_door"
    assert merged["rooms"]["b"]["adjacent"][0]["barrier"] == "closed_door"
    assert spatial_rel(merged, "a", "b")["barrier"] == "closed_door"
    # An edge the beat did NOT change yields to the passage: a stale edge
    # that disagrees with the record is healed, not believed.
    stale = two_rooms(a_barrier="wall", b_barrier="open_door")
    healed = merge_scene_with_diff(stale, {})
    assert healed["rooms"]["a"]["adjacent"][0]["barrier"] == "open_door"
    assert healed["passages"]["a|b"]["barrier"] == "open_door"


def test_a_passage_naming_a_room_the_scene_lost_is_dropped_and_the_edges_read_per_edge():
    sc = two_rooms(a_barrier="closed_door", b_barrier="open")
    sc["passages"]["a|b"]["rooms"] = ["a", "gone"]
    dropped = normalize_scene_passages(sc)
    assert dropped == ["a|b"] and "passages" not in sc
    assert "passage" not in sc["rooms"]["a"]["adjacent"][0]
    assert spatial_rel(sc, "a", "b")["barrier"] == "closed_door"
    assert spatial_rel(sc, "b", "a")["barrier"] == "open"
    # Junk width and empty prose fields are dropped from a kept record.
    sc = two_rooms(record={"rooms": ["a", "b"], "barrier": "OPEN DOOR", "width": "wide",
                           "name": "  ", "material": ""})
    normalize_scene_passages(sc)
    assert sc["passages"]["a|b"] == {"rooms": ["a", "b"], "barrier": "open_door"}


# ---------------------------------------------------------------------------
# The fail-open pin: no passages, byte for byte
# ---------------------------------------------------------------------------

def test_a_scene_with_no_passages_is_byte_identical_through_every_reader_and_the_merge():
    sc = two_rooms(passage=False, a_barrier="closed_door", b_barrier="open")
    before = copy.deepcopy(sc)
    answers = {
        "rel_ab": spatial_rel(sc, "a", "b"), "rel_ba": spatial_rel(sc, "b", "a"),
        "adj_a": effective_adjacent(sc, "a"), "adj_b": effective_adjacent(sc, "b"),
        "nm": neighbor_map(sc), "anch_a": effective_anchors(sc, "a"),
        "anch_b": effective_anchors(sc, "b"), "sight_a": _sight_neighbours(sc, "a"),
        "cells_a": anchor_cells(sc, "a"),
    }
    # The readers wrote nothing.
    assert sc == before
    # The per-edge answers, as they always were: A's own edge says closed,
    # B's own says open (the disagreement the passage record exists to end).
    assert answers["rel_ab"]["barrier"] == "closed_door"
    assert answers["rel_ba"]["barrier"] == "open"
    assert answers["adj_a"][0] is sc["rooms"]["a"]["adjacent"][0]
    assert "passage" not in answers["adj_b"][0]
    assert sync_scene_passages(sc) == [] and "passages" not in sc
    merged = merge_scene_with_diff(sc, {})
    assert "passages" not in merged
    assert merged["rooms"] == sc["rooms"]
