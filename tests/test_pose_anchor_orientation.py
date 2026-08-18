"""A pose may be relative to a room FIXTURE, and that is what turns a body.

`support` has always accepted a room anchor; `relative_to` accepted only
co-located bodies and silently cleared everything else. So the one structured
record of which way a body had turned was thrown away at normalisation, `focus`
kept whatever it had from an earlier beat, and `infer_facing` pinned the heading
there.

Live (chat 74 turn 57): a character in the bathroom turned to the towel rack,
back to the open doorway. `towel_rack` is a real anchor of that room bearing
'ne'; the doorway bears 'w'. The pose was cleared, focus stayed on the doorway
edge, facing stayed 'w' -- and the composed view read "back to the room" and
"You see Hinami" one sentence apart.

Turning away is recorded as turning TOWARD something else, because a heading is
a direction and "not that way" is not one.
"""

from __future__ import annotations

from world.spatial import normalize_scene_poses
from world.spatial_frames import infer_facing, infer_focus

ROOMS = {
    "room_312": {
        "adjacent": [{"to": "room_312_bathroom", "barrier": "open_door",
                      "dir": "e"}],
        "anchors": {"bed": {"desc": "A double bed", "dir": "e"}},
    },
    "room_312_bathroom": {
        "adjacent": [{"to": "room_312", "barrier": "open_door", "dir": "w"}],
        "anchors": {"towel_rack": {"desc": "A wall rack of towels", "dir": "ne"},
                    "sink": {"desc": "Pedestal sink", "dir": "n"}},
    },
}


def _pose(**kw):
    base = {"posture": "standing", "support": "ground", "relative_to": "",
            "relation": "", "constraint": "", "detail": ""}
    base.update(kw)
    return base


def _scene(poses=None, orientation=None, positions=None):
    return {
        "positions": positions or {"Doc": "room_312_bathroom",
                                   "Hinami": "room_312"},
        "orientation": orientation or {},
        "rooms": ROOMS,
        "poses": poses or {},
        "stations": {},
    }


# ---- normalisation: what survives the pose clean ----

def test_a_pose_relative_to_a_room_anchor_survives():
    sc = _scene({"Doc": _pose(relative_to="towel_rack", relation="beside")})
    normalize_scene_poses(sc)
    assert sc["poses"]["Doc"]["relative_to"] == "towel_rack"
    assert sc["poses"]["Doc"]["relation"] == "beside"


def test_a_pose_relative_to_nothing_the_room_knows_is_still_cleared():
    """The guard still guards -- an unresolvable referent buys no orientation."""
    sc = _scene({"Doc": _pose(relative_to="hat_stand", relation="beside")})
    normalize_scene_poses(sc)
    assert sc["poses"]["Doc"]["relative_to"] == ""
    assert sc["poses"]["Doc"]["relation"] == ""


def test_a_pose_relative_to_a_colocated_body_still_survives():
    sc = _scene({"Doc": _pose(relative_to="Nurse", relation="beside")},
                positions={"Doc": "room_312_bathroom",
                           "Nurse": "room_312_bathroom"})
    normalize_scene_poses(sc)
    assert sc["poses"]["Doc"]["relative_to"] == "Nurse"


def test_a_body_in_another_room_is_still_cleared():
    sc = _scene({"Doc": _pose(relative_to="Hinami", relation="beside")})
    normalize_scene_poses(sc)
    assert sc["poses"]["Doc"]["relative_to"] == ""


# ---- focus: the pose claims attention over a stale one ----

def test_the_pose_anchor_becomes_focus():
    sc = _scene({"Doc": _pose(relative_to="towel_rack")})
    prev = _scene()
    infer_focus(1, 1, prev, sc, {}, ["Doc"])
    assert sc["orientation"]["Doc"]["focus"] == {"kind": "anchor",
                                                 "ref": "towel_rack"}


def test_the_pose_anchor_replaces_a_stale_doorway_focus():
    """The actual bug: a focus persisted from an earlier beat outliving the
    turn that ended it."""
    sc = _scene({"Doc": _pose(relative_to="towel_rack")},
                orientation={"Doc": {"focus": {"kind": "edge",
                                               "ref": "room_312"},
                                     "facing": "w", "came_from": "room_312"}})
    prev = _scene()
    infer_focus(1, 1, prev, sc, {}, ["Doc"])
    assert sc["orientation"]["Doc"]["focus"]["kind"] == "anchor"


def test_a_conversation_still_outranks_the_pose():
    """Addressing someone ranks above the pose: a body leaning on a rack while
    answering a question is attending the person, not the rack."""
    sc = _scene({"Doc": _pose(relative_to="towel_rack")},
                positions={"Doc": "room_312_bathroom",
                           "Nurse": "room_312_bathroom"})
    prev = _scene(positions={"Doc": "room_312_bathroom",
                             "Nurse": "room_312_bathroom"})
    dr = {"dialogue_log": [{"speaker": "Doc", "intended_target": "Nurse"}]}
    infer_focus(1, 1, prev, sc, dr, ["Doc", "Nurse"])
    assert sc["orientation"]["Doc"]["focus"] == {"kind": "target",
                                                 "ref": "Nurse"}


# ---- facing: the anchor's bearing becomes the heading ----

def test_facing_follows_the_anchor_and_leaves_the_doorway():
    """End to end. Before: facing 'w', straight at the open doorway to the
    other room. After: 'ne', the rack -- so the doorway is no longer ahead."""
    sc = _scene({"Doc": _pose(relative_to="towel_rack")},
                orientation={"Doc": {"focus": {"kind": "edge",
                                               "ref": "room_312"},
                                     "facing": "w", "came_from": "room_312"}})
    prev = _scene(positions={"Doc": "room_312_bathroom", "Hinami": "room_312"})
    infer_focus(1, 1, prev, sc, {}, ["Doc"])
    infer_facing(1, 1, prev, sc, ["Doc"])
    assert sc["orientation"]["Doc"]["facing"] == "ne"


def test_a_doorway_behind_the_shoulder_is_out_of_sight():
    """The second half. `relative_bearing('ne','w')` is `behind_left`, which
    egocentric_frame collapses into `left` -- correct for prose, wrong for
    sight. The rear ARC gates it, matching what entity_arc already does for
    sources inside the room."""
    from agents.perception import _behind_rooms
    sc = _scene(orientation={"Doc": {"facing": "ne", "came_from": "room_312"}})
    assert _behind_rooms(sc, "Doc") == ["room_312"]


def test_a_doorway_you_are_facing_stays_in_sight():
    from agents.perception import _behind_rooms
    sc = _scene(orientation={"Doc": {"facing": "w", "came_from": "room_312"}})
    assert _behind_rooms(sc, "Doc") == []


def test_without_facing_the_movement_fallback_is_unchanged():
    """No facing -> no bearing arithmetic, and came_from still decides. The
    rule stays 'nothing is gated by default'."""
    from agents.perception import _behind_rooms
    sc = _scene(orientation={"Doc": {"came_from": "room_312"}})
    assert _behind_rooms(sc, "Doc") == ["room_312"]
    bare = _scene(orientation={"Doc": {}})
    assert _behind_rooms(bare, "Doc") == []


def test_an_anchor_without_a_bearing_leaves_facing_alone():
    """Fail-soft, matching every other rule here: no basis, no guess."""
    rooms = {"cell": {"adjacent": [],
                      "anchors": {"cot": {"desc": "A cot"}}}}   # no dir
    sc = {"positions": {"Doc": "cell"}, "rooms": rooms,
          "poses": {"Doc": _pose(relative_to="cot")},
          "orientation": {"Doc": {"facing": "n"}}, "stations": {}}
    prev = {"positions": {"Doc": "cell"}, "rooms": rooms, "orientation": {},
            "poses": {}, "stations": {}}
    infer_focus(1, 1, prev, sc, {}, ["Doc"])
    infer_facing(1, 1, prev, sc, ["Doc"])
    assert sc["orientation"]["Doc"]["facing"] == "n"
