"""S1: the read-time spatial derivation layer.

Implicit door anchors from beared edges (S1a), effective stations derived
from contacts and threshold crossings (S1b), read-time facing fallback and
the un-starved focus->facing arm (S1c), the edge-distance normalizer (S1d),
and the room-size keyword hint (S1e). Everything here is derive-or-default:
a scene with no new data must behave exactly as before, which the inert-
default tests pin.
"""
from __future__ import annotations

from world.spatial import (
    anchor_bearing_of,
    door_anchor_id,
    effective_anchors,
    effective_facing,
    effective_room_size,
    effective_station,
    entity_side,
    hear_level,
    measured_proximity_rel,
    normalize_edge_distance,
    normalize_scene_stations,
    proximity_rel,
    room_layout,
    spatial_rel,
)
from world.spatial_frames import infer_facing


def _scene(**over):
    base = {
        "rooms": {
            "hall": {
                "name": "the Hall", "size": "large",
                "anchors": {"bar": {"desc": "the long bar", "dir": "n"}},
                "adjacent": [
                    {"to": "kitchen", "barrier": "open_door", "dir": "e"},
                ],
            },
            "kitchen": {
                "name": "the Kitchen",
                "anchors": {"stove": {"desc": "the stove", "dir": "n"}},
                "adjacent": [],
            },
        },
        "positions": {},
        "entities": {},
    }
    base.update(over)
    return base


# ---- S1a: implicit door anchors -------------------------------------------

def test_beared_edge_becomes_an_implicit_door_anchor():
    sc = _scene()
    anchors = effective_anchors(sc, "hall")
    assert anchors["bar"]["dir"] == "n"          # authored survives untouched
    door = anchors[door_anchor_id("kitchen")]
    assert door["implicit"] is True
    assert door["dir"] == "e"
    assert door["desc"] == "the open doorway"


def test_reverse_declared_edge_bears_reciprocally():
    sc = _scene()
    # kitchen declares no edge of its own; hall's east edge still gives the
    # kitchen a west doorway.
    door = effective_anchors(sc, "kitchen")[door_anchor_id("hall")]
    assert door["dir"] == "w"


def test_authored_anchor_wins_an_id_collision():
    sc = _scene()
    sc["rooms"]["hall"]["anchors"][door_anchor_id("kitchen")] = {
        "desc": "the service hatch", "dir": "s"}
    door = effective_anchors(sc, "hall")[door_anchor_id("kitchen")]
    assert door["desc"] == "the service hatch"
    assert door["dir"] == "s"
    assert not door.get("implicit")


def test_implicit_anchors_are_never_written_to_the_scene():
    sc = _scene()
    effective_anchors(sc, "hall")
    assert door_anchor_id("kitchen") not in sc["rooms"]["hall"]["anchors"]


def test_vertical_edge_becomes_a_vertical_pseudo_anchor():
    sc = _scene()
    sc["rooms"]["hall"]["adjacent"].append(
        {"to": "cellar", "barrier": "open", "vertical": "down"})
    sc["rooms"]["cellar"] = {"name": "the Cellar", "adjacent": []}
    assert effective_anchors(sc, "hall")[door_anchor_id("cellar")][
        "vertical"] == "down"
    assert effective_anchors(sc, "cellar")[door_anchor_id("hall")][
        "vertical"] == "up"


# ---- S1b: effective stations -----------------------------------------------

def test_no_data_no_station_inert_default():
    sc = _scene(positions={"P": "hall", "Q": "hall"})
    st = effective_station(sc, "P")
    assert st.get("at") is None and st.get("near") == []
    assert proximity_rel(sc, "P", "Q") == "near"
    assert measured_proximity_rel(sc, "P", "Q") is None


def test_a_standing_contact_derives_a_mutual_near_link():
    sc = _scene(positions={"P": "hall", "Q": "hall"},
                contacts=[{"actor": "P", "target": "Q",
                           "manner": "holds", "actor_part": "hand"}])
    assert proximity_rel(sc, "P", "Q") == "within_reach"
    assert proximity_rel(sc, "Q", "P") == "within_reach"
    # ...which is what lets a whisper between them arrive whole.
    rel = spatial_rel(sc, "hall", "hall")
    assert hear_level(rel, "whisper",
                      proximity=proximity_rel(sc, "P", "Q")) == "full"


def test_contact_derived_links_ignore_a_partner_in_another_room():
    sc = _scene(positions={"P": "hall", "Q": "kitchen"},
                contacts=[{"actor": "P", "target": "Q"}])
    assert effective_station(sc, "P")["near"] == []


def test_a_live_crossing_stations_the_body_at_the_door():
    sc = _scene(positions={"Runner": "kitchen"},
                crossings={"Runner": {"from": "hall", "to": "kitchen",
                                      "beats": 2}})
    assert effective_station(sc, "Runner")["at"] == door_anchor_id("hall")
    # ...which bears, so the facing derivation has fuel (S1c).
    assert anchor_bearing_of(sc, "Runner") == "w"


def test_two_fresh_entrants_through_one_door_are_within_reach():
    sc = _scene(positions={"A": "kitchen", "B": "kitchen"},
                crossings={"A": {"from": "hall", "to": "kitchen", "beats": 2},
                           "B": {"from": "hall", "to": "kitchen", "beats": 1}})
    assert proximity_rel(sc, "A", "B") == "within_reach"
    # The crossing-derived anchor is a MEASUREMENT, so it forwards.
    assert measured_proximity_rel(sc, "A", "B") == "within_reach"


def test_an_expired_crossing_stations_nothing():
    sc = _scene(positions={"Runner": "kitchen"},
                crossings={"Runner": {"from": "hall", "to": "kitchen",
                                      "beats": 0}})
    assert effective_station(sc, "Runner")["at"] is None


def test_an_authored_station_always_wins():
    sc = _scene(positions={"Runner": "kitchen"},
                stations={"Runner": {"at": "stove", "near": []}},
                crossings={"Runner": {"from": "hall", "to": "kitchen",
                                      "beats": 2}})
    assert effective_station(sc, "Runner")["at"] == "stove"


def test_unknown_station_keys_pass_through():
    sc = _scene(positions={"P": "hall"},
                stations={"P": {"at": "bar", "near": [], "cover": True}})
    assert effective_station(sc, "P").get("cover") is True


# ---- S1c: facing ------------------------------------------------------------

def test_effective_facing_prefers_the_persisted_bearing():
    sc = _scene(positions={"P": "hall"},
                orientation={"P": {"facing": "s",
                                   "focus": {"kind": "edge",
                                             "ref": "kitchen"}}})
    assert effective_facing(sc, "P") == "s"


def test_effective_facing_derives_from_an_edge_focus():
    sc = _scene(positions={"P": "hall"},
                orientation={"P": {"focus": {"kind": "edge",
                                             "ref": "kitchen"}}})
    assert effective_facing(sc, "P") == "e"


def test_effective_facing_derives_from_an_anchored_target_focus():
    sc = _scene(positions={"P": "hall", "Barkeep": "hall"},
                stations={"Barkeep": {"at": "bar", "near": []}},
                orientation={"P": {"focus": {"kind": "target",
                                             "ref": "Barkeep"}}})
    assert effective_facing(sc, "P") == "n"


def test_effective_facing_is_never_guessed():
    sc = _scene(positions={"P": "hall"})
    assert effective_facing(sc, "P") is None


def test_entity_side_fires_for_a_body_in_a_doorway():
    # No authored stations at all: the target's crossing seats them at the
    # east door pseudo-anchor; the observer faces north; east is right.
    sc = _scene(positions={"P": "hall", "Runner": "hall"},
                orientation={"P": {"facing": "n"}},
                crossings={"Runner": {"from": "kitchen", "to": "hall",
                                      "beats": 2}})
    assert entity_side(sc, "P", "Runner") == "right"


def test_infer_facing_focus_arm_is_unstarved_by_derived_stations():
    # The commit-time deriver (spatial_frames.infer_facing) turns a focused
    # observer toward the target's anchor bearing -- which used to starve on
    # authored stations (11% coverage). A crossing-derived door station now
    # feeds it with zero authoring.
    prev = _scene(positions={"Watcher": "kitchen", "Runner": "kitchen"})
    new = _scene(positions={"Watcher": "kitchen", "Runner": "kitchen"},
                 crossings={"Runner": {"from": "hall", "to": "kitchen",
                                       "beats": 2}},
                 orientation={"Watcher": {"focus": {"kind": "target",
                                                    "ref": "Runner"}}})
    changed = infer_facing(None, None, prev, new, ["Watcher"])
    assert changed
    assert new["orientation"]["Watcher"]["facing"] == "w"


# ---- S1d: the edge-distance normalizer --------------------------------------

def test_distance_surface_forms_collapse_to_tiers():
    for raw, tier in (
        # word aliases, straight from the corpus's 29 surface forms
        ("close", "adjacent"), ("immediate", "adjacent"),
        ("short", "adjacent"), ("near", "near"), ("mid", "near"),
        ("moderate", "near"), ("medium", "near"), ("far", "far"),
        ("remote", "remote"),
        # numeric and metric forms
        ("0", "adjacent"), ("1", "adjacent"), ("3.0", "adjacent"),
        ("2m", "adjacent"), ("1 step", "adjacent"), ("10", "near"),
        ("20m", "near"), ("50m", "far"), ("15 m", "near"),
        ("200 m", "remote"), ("2 km", "remote"),
        # absent / unparseable -> today's default, never a measurement
        (None, "near"), ("", "near"), ("a fair way off", "near"),
        ("3 leagues", "near"),
    ):
        assert normalize_edge_distance(raw) == tier, (raw, tier)


def test_spatial_rel_normalizes_the_authored_distance():
    sc = _scene()
    sc["rooms"]["hall"]["adjacent"][0]["distance"] = "2m"
    assert spatial_rel(sc, "hall", "kitchen")["distance"] == "adjacent"
    sc["rooms"]["hall"]["adjacent"][0]["distance"] = "200 m"
    assert spatial_rel(sc, "hall", "kitchen")["distance"] == "remote"


def test_a_genuinely_remote_edge_now_reaches_hear_levels_dead_branch():
    # `remote` was consumed by hear_level and authored zero times; the
    # normalizer makes the 200m gallery actually remote.
    sc = _scene()
    sc["rooms"]["hall"]["adjacent"][0]["distance"] = "200 m"
    rel = spatial_rel(sc, "hall", "kitchen")
    assert hear_level(rel, "normal") == "none"
    sc["rooms"]["hall"]["adjacent"][0]["distance"] = "close"
    rel = spatial_rel(sc, "hall", "kitchen")
    assert hear_level(rel, "normal") == "full"   # unchanged for the rest


# ---- S1e: room-size keyword hint ---------------------------------------------

def test_authored_size_always_wins():
    sc = _scene()
    sc["rooms"]["hall"]["size"] = "small"
    sc["rooms"]["hall"]["name"] = "the Grand Ballroom"
    assert effective_room_size(sc, "hall") == "small"


def test_big_sounding_name_hints_large():
    sc = _scene()
    del sc["rooms"]["hall"]["size"]
    sc["rooms"]["hall"]["name"] = "the Feasting Hall"
    assert effective_room_size(sc, "hall") == "large"
    sc["positions"] = {"P": "hall", "Q": "hall"}
    sc["stations"] = {"P": {"at": "bar"},
                      "Q": {"at": door_anchor_id("kitchen")}}
    assert proximity_rel(sc, "P", "Q") == "across"


def test_hallway_is_not_a_hall():
    sc = _scene()
    del sc["rooms"]["hall"]["size"]
    sc["rooms"]["hall"]["name"] = "a narrow hallway"
    assert effective_room_size(sc, "hall") == "medium"


def test_unnamed_room_defaults_medium():
    sc = _scene()
    del sc["rooms"]["hall"]["size"]
    sc["rooms"]["hall"]["name"] = ""
    assert effective_room_size(sc, "hall") == "medium"


# ---- hygiene: door stations survive the merge --------------------------------

def test_normalize_keeps_a_station_at_an_implicit_door_anchor():
    sc = _scene(positions={"Runner": "kitchen"},
                stations={"Runner": {"at": door_anchor_id("hall"),
                                     "near": []}})
    normalize_scene_stations(sc)
    assert sc["stations"]["Runner"]["at"] == door_anchor_id("hall")


def test_a_room_move_still_clears_a_door_station():
    sc = _scene(positions={"Runner": "hall"},
                stations={"Runner": {"at": door_anchor_id("hall"),
                                     "near": []}})
    # A door TO the hall is not an anchor OF the hall.
    normalize_scene_stations(sc)
    assert sc["stations"]["Runner"]["at"] is None


def test_room_layout_lists_the_doorway_as_a_positioned_feature():
    sc = _scene(positions={"P": "hall"}, orientation={"P": {"facing": "n"}})
    layout = room_layout(sc, "P")
    descs = {a["desc"]: a["side"] for a in layout["anchors"]}
    assert descs["the long bar"] == "ahead"
    assert descs["the open doorway"] == "right"
