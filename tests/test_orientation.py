"""Egocentric orientation: came_from derivation + egocentric_frame bucketing.
The deterministic, authored-data-free spatial frame that gives perception and
the narrator a coherent 'behind/ahead/aside' instead of an unordered adjacency
list they must invent geometry from."""

from __future__ import annotations

from spatial import (egocentric_frame, rooms_adjacent, spatial_digest,
                     normalize_bearing, opposite_bearing, relative_bearing,
                     lateral_of, travel_bearing, normalize_scene_bearings,
                     merge_scene_with_diff)
from spatial_frames import infer_came_from, infer_focus, infer_facing


def _scene(positions, orientation, rooms):
    return {"positions": positions, "orientation": orientation, "rooms": rooms}


CORRIDOR = {
    "station": {"adjacent": [{"to": "checkpoint", "barrier": "open_door"}]},
    "checkpoint": {"adjacent": [
        {"to": "station", "barrier": "open_door"},
        {"to": "corridor", "barrier": "open_door"},
    ]},
    "corridor": {"adjacent": [
        {"to": "checkpoint", "barrier": "open_door"},
        {"to": "common_room", "barrier": "open"},
    ]},
    "common_room": {"adjacent": [{"to": "corridor", "barrier": "open"}]},
}


def test_came_from_is_behind_and_onward_is_ahead():
    # The failing turn: in the corridor having come from the checkpoint, the
    # checkpoint MUST be behind and the common room (the single other exit)
    # onward/ahead -- never both "ahead".
    sc = _scene({"Hinami": "corridor"},
                {"Hinami": {"came_from": "checkpoint"}}, CORRIDOR)
    f = egocentric_frame(sc, "Hinami")
    assert [e["to"] for e in f["behind"]] == ["checkpoint"]
    assert [e["to"] for e in f["ahead"]] == ["common_room"]
    assert f["aside"] == []


def test_no_history_is_all_unclassified():
    sc = _scene({"Hinami": "corridor"}, {}, CORRIDOR)
    f = egocentric_frame(sc, "Hinami")
    assert not f["behind"] and not f["ahead"]
    assert {e["to"] for e in f["unclassified"]} == {"checkpoint", "common_room"}


def test_multi_exit_without_focus_stays_aside():
    # Three-way room, came from one exit, no focus -> the other two are ASIDE,
    # never guessed as "ahead" (one-ahead-max; ambiguity stays topological).
    rooms = {"hub": {"adjacent": [
        {"to": "a"}, {"to": "b"}, {"to": "c"}]}}
    sc = _scene({"P": "hub"}, {"P": {"came_from": "a"}}, rooms)
    f = egocentric_frame(sc, "P")
    assert [e["to"] for e in f["behind"]] == ["a"]
    assert f["ahead"] == []
    assert {e["to"] for e in f["aside"]} == {"b", "c"}


def test_focus_edge_is_ahead():
    rooms = {"hub": {"adjacent": [{"to": "a"}, {"to": "b"}, {"to": "c"}]}}
    sc = _scene({"P": "hub"},
                {"P": {"came_from": "a", "focus": {"kind": "edge", "ref": "c"}}}, rooms)
    f = egocentric_frame(sc, "P")
    assert [e["to"] for e in f["ahead"]] == ["c"]
    assert {e["to"] for e in f["aside"]} == {"b"}


def test_vertical_edges_bucket_above_below():
    rooms = {"landing": {"adjacent": [
        {"to": "up_hall", "vertical": "up"},
        {"to": "cellar", "vertical": "down"},
        {"to": "corridor"}]}}
    sc = _scene({"P": "landing"}, {"P": {"came_from": "corridor"}}, rooms)
    f = egocentric_frame(sc, "P")
    assert [e["to"] for e in f["above"]] == ["up_hall"]
    assert [e["to"] for e in f["below"]] == ["cellar"]
    assert [e["to"] for e in f["behind"]] == ["corridor"]


def test_infer_came_from_adjacent_step():
    prev = _scene({"P": "checkpoint"}, {}, CORRIDOR)
    new = _scene({"P": "corridor"}, {}, CORRIDOR)
    infer_came_from(1, None, prev, new, ["P"])
    assert new["orientation"]["P"]["came_from"] == "checkpoint"


def test_infer_came_from_teleport_clears_orientation():
    # Non-adjacent jump: disoriented -> came_from None, focus cleared.
    prev = _scene({"P": "station"},
                  {"P": {"came_from": "x", "focus": {"kind": "edge", "ref": "y"}}}, CORRIDOR)
    new = _scene({"P": "common_room"},
                 {"P": {"came_from": "x", "focus": {"kind": "edge", "ref": "y"}}}, CORRIDOR)
    infer_came_from(1, None, prev, new, ["P"])
    assert new["orientation"]["P"]["came_from"] is None
    assert new["orientation"]["P"]["focus"] is None


def test_infer_came_from_staying_put_keeps_orientation():
    prev = _scene({"P": "corridor"}, {"P": {"came_from": "checkpoint"}}, CORRIDOR)
    new = _scene({"P": "corridor"}, {"P": {"came_from": "checkpoint"}}, CORRIDOR)
    infer_came_from(1, None, prev, new, ["P"])
    assert new["orientation"]["P"]["came_from"] == "checkpoint"


def test_infer_came_from_prunes_absent_names():
    prev = _scene({"P": "corridor"}, {}, CORRIDOR)
    new = _scene({}, {"Ghost": {"came_from": "x"}}, CORRIDOR)
    infer_came_from(1, None, prev, new, ["P"])
    assert "Ghost" not in new["orientation"]


def test_spatial_digest_renders_room_names_by_bucket():
    rooms = {
        "corridor": {"name": "The Corridor", "adjacent": [
            {"to": "checkpoint", "barrier": "open_door"},
            {"to": "common_room", "barrier": "open"},
        ]},
        "checkpoint": {"name": "Checkpoint"},
        "common_room": {"name": "Common Room"},
    }
    sc = _scene({"P": "corridor"}, {"P": {"came_from": "checkpoint"}}, rooms)
    d = spatial_digest(sc, "P")
    assert d["behind"] == [{"room": "Checkpoint", "barrier": "open_door"}]
    assert d["ahead"] == [{"room": "Common Room", "barrier": "open"}]
    assert "aside" not in d


def test_spatial_digest_unclassified_when_no_history():
    rooms = {"corridor": {"name": "The Corridor", "adjacent": [
        {"to": "checkpoint"}, {"to": "common_room"}]},
        "checkpoint": {"name": "Checkpoint"}, "common_room": {"name": "Common Room"}}
    sc = _scene({"P": "corridor"}, {}, rooms)
    d = spatial_digest(sc, "P")
    assert "behind" not in d and "ahead" not in d
    assert len(d["unclassified"]) == 2  # narrator asserts no direction


# ---- focus derivation (FOV spec A/D) -------------------------------------

def _dlog(*pairs):
    return {"dialogue_log": [{"speaker": s, "intended_target": t} for s, t in pairs]}


def test_conversation_auto_holds_mutual_focus():
    # A speaks to B (co-located): each focuses the other, no "I look at them".
    prev = _scene({"A": "room", "B": "room"}, {}, {"room": {}})
    new = _scene({"A": "room", "B": "room"},
                 {"A": {}, "B": {}}, {"room": {}})
    infer_focus(1, None, prev, new, _dlog(("A", "B")), ["A", "B"])
    assert new["orientation"]["A"]["focus"] == {"kind": "target", "ref": "B"}
    assert new["orientation"]["B"]["focus"] == {"kind": "target", "ref": "A"}  # addressed


def test_cross_room_address_focuses_the_doorway():
    prev = _scene({"A": "hall", "B": "kitchen"}, {}, {})
    new = _scene({"A": "hall", "B": "kitchen"}, {"A": {}, "B": {}}, {})
    infer_focus(1, None, prev, new, _dlog(("A", "B")), ["A", "B"])
    assert new["orientation"]["A"]["focus"] == {"kind": "edge", "ref": "kitchen"}


def test_locomotion_resets_focus():
    # Moved this beat, addressed no one -> gaze resets (pass-through supplies ahead).
    prev = _scene({"A": "station"}, {}, CORRIDOR)
    new = _scene({"A": "checkpoint"},
                 {"A": {"came_from": "station", "focus": {"kind": "target", "ref": "old"}}}, CORRIDOR)
    infer_focus(1, None, prev, new, {}, ["A"])
    assert new["orientation"]["A"]["focus"] is None


def test_focus_persists_when_nothing_changes():
    prev = _scene({"A": "room", "B": "room"}, {}, {"room": {}})
    new = _scene({"A": "room", "B": "room"},
                 {"A": {"focus": {"kind": "target", "ref": "B"}}, "B": {}}, {"room": {}})
    infer_focus(1, None, prev, new, {}, ["A", "B"])
    assert new["orientation"]["A"]["focus"] == {"kind": "target", "ref": "B"}  # no decay


def test_focus_gc_when_target_leaves():
    # B is no longer co-located -> stale target focus is garbage-collected.
    prev = _scene({"A": "room", "B": "room"}, {}, {"room": {}})
    new = _scene({"A": "room", "B": "elsewhere"},
                 {"A": {"focus": {"kind": "target", "ref": "B"}}, "B": {}}, {"room": {}})
    infer_focus(1, None, prev, new, {}, ["A", "B"])
    assert new["orientation"]["A"]["focus"] is None


def test_focus_makes_target_the_ahead_entity():
    rooms = {"room": {"adjacent": [{"to": "hall"}]}}
    sc = _scene({"P": "room"},
                {"P": {"came_from": "hall", "focus": {"kind": "target", "ref": "Mara"}}}, rooms)
    assert egocentric_frame(sc, "P")["ahead_entity"] == "Mara"
    assert spatial_digest(sc, "P")["ahead_entity"] == "Mara"


def test_rooms_adjacent_undirected():
    sc = _scene({}, {}, CORRIDOR)
    assert rooms_adjacent(sc, "corridor", "common_room")
    assert rooms_adjacent(sc, "common_room", "corridor")  # reverse
    assert not rooms_adjacent(sc, "station", "common_room")


# ---- compass bearings (allocentric truth) --------------------------------

def test_normalize_bearing_cardinals_and_aliases():
    assert normalize_bearing("n") == "n"
    assert normalize_bearing("North") == "n"
    assert normalize_bearing("north-east") == "ne"
    assert normalize_bearing(" SouthWest ") == "sw"
    assert normalize_bearing("W") == "w"


def test_normalize_bearing_rejects_egocentric_and_junk():
    # 'left' is a fact about an observer, never allocentric edge truth.
    for word in ("left", "right", "ahead", "behind", "forward", "port",
                 "starboard", "up", "down"):
        assert normalize_bearing(word) is None
    assert normalize_bearing("") is None
    assert normalize_bearing("banana") is None
    assert normalize_bearing(None) is None


def test_opposite_bearing():
    assert opposite_bearing("n") == "s"
    assert opposite_bearing("ne") == "sw"
    assert opposite_bearing("w") == "e"
    assert opposite_bearing(None) is None


def test_relative_bearing_sectors():
    assert relative_bearing("n", "n") == "ahead"
    assert relative_bearing("n", "s") == "behind"
    assert relative_bearing("n", "e") == "right"
    assert relative_bearing("n", "w") == "left"
    # facing east: north is now on the LEFT, south on the right.
    assert relative_bearing("e", "n") == "left"
    assert relative_bearing("e", "s") == "right"
    assert relative_bearing("n", None) is None


def test_lateral_of_only_sides():
    assert lateral_of("n", "e") == "right"
    assert lateral_of("n", "w") == "left"
    assert lateral_of("n", "n") is None   # pure fore/aft -> no side
    assert lateral_of("n", "s") is None
    assert lateral_of(None, "e") is None  # no facing -> no side


# ---- egocentric left/right refinement ------------------------------------

# Facing north in a hub: the checkpoint is behind (came from), and the two
# other exits carry bearings placing one east (right) and one west (left).
HUB_BEARINGS = {"hub": {"name": "Hub", "adjacent": [
    {"to": "back", "barrier": "open", "dir": "s"},
    {"to": "east_wing", "barrier": "open_door", "dir": "e"},
    {"to": "west_wing", "barrier": "open_door", "dir": "w"},
]}}


def test_facing_and_bearings_yield_left_and_right():
    sc = _scene({"P": "hub"},
                {"P": {"came_from": "back", "facing": "n"}}, HUB_BEARINGS)
    f = egocentric_frame(sc, "P")
    assert [e["to"] for e in f["behind"]] == ["back"]
    assert [e["to"] for e in f["right"]] == ["east_wing"]
    assert [e["to"] for e in f["left"]] == ["west_wing"]
    assert f["aside"] == []


def test_left_right_mirror_when_facing_flips():
    # Same world, observer facing SOUTH: east becomes left, west becomes right.
    sc = _scene({"P": "hub"},
                {"P": {"came_from": "back", "facing": "s"}}, HUB_BEARINGS)
    f = egocentric_frame(sc, "P")
    # came_from 'back' (s) is claimed as behind; the bearinged exits flip sides.
    assert [e["to"] for e in f["right"]] == ["west_wing"]
    assert [e["to"] for e in f["left"]] == ["east_wing"]


def test_no_facing_means_no_side():
    # Bearings present but no facing -> side is never guessed; stays aside.
    sc = _scene({"P": "hub"}, {"P": {"came_from": "back"}}, HUB_BEARINGS)
    f = egocentric_frame(sc, "P")
    assert f["left"] == [] and f["right"] == []
    assert {e["to"] for e in f["aside"]} == {"east_wing", "west_wing"}


def test_spatial_digest_renders_left_right():
    sc = _scene({"P": "hub"},
                {"P": {"came_from": "back", "facing": "n"}}, HUB_BEARINGS)
    d = spatial_digest(sc, "P")
    assert d["left"] == [{"room": "west_wing", "barrier": "open_door"}]
    assert d["right"] == [{"room": "east_wing", "barrier": "open_door"}]


# ---- reciprocity reconciliation ------------------------------------------

def test_normalize_scene_bearings_fills_reciprocal():
    scene = {"rooms": {
        "a": {"adjacent": [{"to": "b", "dir": "e"}]},
        "b": {"adjacent": [{"to": "a"}]},  # missing dir
    }}
    normalize_scene_bearings(scene)
    back = scene["rooms"]["b"]["adjacent"][0]
    assert back["dir"] == "w"  # reciprocal of east


def test_normalize_scene_bearings_drops_contradiction():
    scene = {"rooms": {
        "a": {"adjacent": [{"to": "b", "dir": "e"}]},
        "b": {"adjacent": [{"to": "a", "dir": "n"}]},  # not the opposite of e
    }}
    normalize_scene_bearings(scene)
    assert "dir" not in scene["rooms"]["a"]["adjacent"][0]
    assert "dir" not in scene["rooms"]["b"]["adjacent"][0]


def test_normalize_scene_bearings_drops_egocentric_dir():
    scene = {"rooms": {"a": {"adjacent": [{"to": "b", "dir": "left"}]},
                       "b": {"adjacent": [{"to": "a"}]}}}
    normalize_scene_bearings(scene)
    assert "dir" not in scene["rooms"]["a"]["adjacent"][0]


def test_merge_reconciles_bearings():
    scene = {"rooms": {}, "entities": {}, "positions": {}}
    diff = {"rooms": {
        "a": {"name": "A", "adjacent": [{"to": "b", "barrier": "open", "dir": "north"}]},
        "b": {"name": "B", "adjacent": [{"to": "a", "barrier": "open"}]},
    }}
    merged = merge_scene_with_diff(scene, diff)
    fwd = merged["rooms"]["a"]["adjacent"][0]
    back = merged["rooms"]["b"]["adjacent"][0]
    assert fwd["dir"] == "n"   # normalized from 'north'
    assert back["dir"] == "s"  # reciprocal filled


# ---- infer_facing --------------------------------------------------------

BEARINGED = {
    "lobby": {"adjacent": [{"to": "corridor", "barrier": "open", "dir": "n"}]},
    "corridor": {"adjacent": [
        {"to": "lobby", "barrier": "open", "dir": "s"},
        {"to": "office", "barrier": "open_door", "dir": "e"},
    ]},
    "office": {"adjacent": [{"to": "corridor", "barrier": "open_door", "dir": "w"}]},
}


def test_infer_facing_faces_travel_direction():
    # Walk lobby -> corridor (an edge bearing north): you now face north.
    prev = _scene({"P": "lobby"}, {}, BEARINGED)
    new = _scene({"P": "corridor"}, {"P": {"came_from": "lobby"}}, BEARINGED)
    infer_facing(1, None, prev, new, ["P"])
    assert new["orientation"]["P"]["facing"] == "n"


def test_infer_facing_none_when_edge_has_no_bearing():
    prev = _scene({"P": "station"}, {}, CORRIDOR)   # CORRIDOR edges carry no dir
    new = _scene({"P": "checkpoint"}, {"P": {"came_from": "station"}}, CORRIDOR)
    infer_facing(1, None, prev, new, ["P"])
    # No prior facing and no bearing to derive one: heading stays unknown
    # (absent == None to egocentric_frame; never guessed).
    assert new["orientation"]["P"].get("facing") is None


def test_infer_facing_clears_stale_when_moving_unbearinged():
    # HAD a facing, then walked through an edge with no bearing -> cleared,
    # because the old heading is now stale and a side must never be guessed.
    prev = _scene({"P": "station"}, {"P": {"facing": "e"}}, CORRIDOR)
    new = _scene({"P": "checkpoint"},
                 {"P": {"came_from": "station", "facing": "e"}}, CORRIDOR)
    infer_facing(1, None, prev, new, ["P"])
    assert new["orientation"]["P"]["facing"] is None


def test_infer_facing_cleared_on_disorienting_jump():
    prev = _scene({"P": "lobby"}, {}, BEARINGED)
    new = _scene({"P": "office"},
                 {"P": {"came_from": None, "facing": "n"}}, BEARINGED)
    infer_facing(1, None, prev, new, ["P"])
    assert new["orientation"]["P"]["facing"] is None


def test_infer_facing_persists_when_stationary():
    prev = _scene({"P": "corridor"}, {"P": {"facing": "e"}}, BEARINGED)
    new = _scene({"P": "corridor"}, {"P": {"facing": "e"}}, BEARINGED)
    infer_facing(1, None, prev, new, ["P"])
    assert new["orientation"]["P"]["facing"] == "e"


def test_infer_facing_turns_to_focused_doorway():
    # Standing in the corridor, focus becomes the doorway toward the office
    # (dir e) -> the character turns to face east.
    prev = _scene({"P": "corridor"}, {"P": {"facing": "n"}}, BEARINGED)
    new = _scene({"P": "corridor"},
                 {"P": {"facing": "n", "focus": {"kind": "edge", "ref": "office"}}},
                 BEARINGED)
    infer_facing(1, None, prev, new, ["P"])
    assert new["orientation"]["P"]["facing"] == "e"


def test_infer_facing_turns_to_face_colocated_target():
    # Phase 3: addressing/attending a co-located person at a known anchor turns
    # you to face them -- so someone in your rear arc you turn toward
    # deterministically enters your front arc (the blind-spot lift).
    rooms = {"room": {"anchors": {"door": {"dir": "s"}}}}
    prev = {"positions": {"P": "room", "Q": "room"}, "rooms": rooms,
            "stations": {"Q": {"at": "door"}},
            "orientation": {"P": {"facing": "n"}}}
    new = {"positions": {"P": "room", "Q": "room"}, "rooms": rooms,
           "stations": {"Q": {"at": "door"}},
           "orientation": {"P": {"facing": "n",
                                 "focus": {"kind": "target", "ref": "Q"}}}}
    infer_facing(1, None, prev, new, ["P", "Q"])
    assert new["orientation"]["P"]["facing"] == "s"   # faced Q at the south door


def test_full_pipeline_walk_produces_left_right():
    # End-to-end deterministic chain: merge a bearinged diff, walk the player
    # one adjacent room, run the orientation inferers in commit order, and the
    # digest should place the side exit on the correct hand.
    scene = merge_scene_with_diff(
        {"rooms": {}, "entities": {}, "positions": {"P": "lobby"}},
        {"rooms": {
            "lobby": {"name": "Lobby", "adjacent": [
                {"to": "corridor", "barrier": "open", "dir": "n"}]},
            "corridor": {"name": "Corridor", "adjacent": [
                {"to": "lobby", "barrier": "open", "dir": "s"},
                {"to": "office", "barrier": "open_door", "dir": "e"}]},
            "office": {"name": "Office", "adjacent": [
                {"to": "corridor", "barrier": "open_door", "dir": "w"}]},
        }},
    )
    prev = {**scene, "positions": {"P": "lobby"}}
    new = {**scene, "positions": {"P": "corridor"}, "orientation": {}}
    infer_came_from(1, None, prev, new, ["P"])
    infer_focus(1, None, prev, new, {}, ["P"])
    infer_facing(1, None, prev, new, ["P"])
    assert new["orientation"]["P"]["came_from"] == "lobby"
    assert new["orientation"]["P"]["facing"] == "n"
    d = spatial_digest(new, "P")
    assert d["behind"] == [{"room": "Lobby", "barrier": "open"}]
    assert d["right"] == [{"room": "Office", "barrier": "open_door"}]
