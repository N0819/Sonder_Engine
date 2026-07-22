"""Within-room position (Phase 2): anchors + entity stations -> derived
proximity tiers, co-located left/right, whisper gating, and station hygiene
through the scene merge."""
from __future__ import annotations

from spatial import (proximity_rel, entity_side, entity_arc, room_layout,
                     normalize_scene_stations, merge_scene_with_diff, hear_level)


TAVERN = {
    "taproom": {
        "name": "the Taproom", "size": "large",
        "anchors": {
            "bar": {"desc": "the long oak bar", "dir": "n"},
            "hearth": {"desc": "the great stone hearth", "dir": "s"},
            "door": {"desc": "the front door", "dir": "e"},
        },
    },
}


def _scene(positions, stations, orientation=None):
    return {"rooms": TAVERN, "positions": dict(positions),
            "stations": dict(stations), "orientation": dict(orientation or {})}


# ---- proximity tiers -----------------------------------------------------

def test_same_anchor_is_within_reach():
    sc = _scene({"P": "taproom", "Barkeep": "taproom"},
                {"P": {"at": "bar"}, "Barkeep": {"at": "bar"}})
    assert proximity_rel(sc, "P", "Barkeep") == "within_reach"


def test_near_link_is_within_reach():
    sc = _scene({"P": "taproom", "Mara": "taproom"},
                {"P": {"at": "hearth", "near": ["Mara"]}, "Mara": {"at": "hearth"}})
    assert proximity_rel(sc, "P", "Mara") == "within_reach"
    assert proximity_rel(sc, "Mara", "P") == "within_reach"  # symmetric read


def test_distinct_anchors_in_large_room_is_across():
    sc = _scene({"P": "taproom", "Drunk": "taproom"},
                {"P": {"at": "bar"}, "Drunk": {"at": "hearth"}})
    assert proximity_rel(sc, "P", "Drunk") == "across"


def test_distinct_anchors_in_small_room_is_near():
    small = {"rooms": {"nook": {"name": "Nook", "size": "small", "anchors": {
        "table": {"dir": "n"}, "window": {"dir": "s"}}}},
        "positions": {"P": "nook", "Q": "nook"},
        "stations": {"P": {"at": "table"}, "Q": {"at": "window"}}}
    assert proximity_rel(small, "P", "Q") == "near"


def test_no_stations_defaults_to_near():
    sc = _scene({"P": "taproom", "Q": "taproom"}, {})
    assert proximity_rel(sc, "P", "Q") == "near"


def test_different_rooms_is_none():
    sc = {"rooms": TAVERN, "positions": {"P": "taproom", "Q": "cellar"},
          "stations": {}}
    assert proximity_rel(sc, "P", "Q") is None


# ---- co-located left/right -----------------------------------------------

def test_entity_side_from_anchor_and_facing():
    # Facing east (toward the door): the bar (north) is on the LEFT, the hearth
    # (south) on the RIGHT.
    sc = _scene({"P": "taproom", "Barkeep": "taproom", "Cook": "taproom"},
                {"Barkeep": {"at": "bar"}, "Cook": {"at": "hearth"}},
                {"P": {"facing": "e"}})
    assert entity_side(sc, "P", "Barkeep") == "left"
    assert entity_side(sc, "P", "Cook") == "right"


def test_entity_side_mirrors_when_observer_turns():
    sc = _scene({"P": "taproom", "Barkeep": "taproom"},
                {"Barkeep": {"at": "bar"}}, {"P": {"facing": "w"}})
    # facing west now: north (bar) is on the RIGHT.
    assert entity_side(sc, "P", "Barkeep") == "right"


def test_entity_side_none_without_facing_or_anchor():
    sc = _scene({"P": "taproom", "Barkeep": "taproom"},
                {"Barkeep": {"at": "bar"}}, {})            # no facing
    assert entity_side(sc, "P", "Barkeep") is None
    sc2 = _scene({"P": "taproom", "Ghost": "taproom"},
                 {"Ghost": {}}, {"P": {"facing": "e"}})     # no anchor
    assert entity_side(sc2, "P", "Ghost") is None


# ---- whisper gating by proximity -----------------------------------------

def test_whisper_reaches_within_reach_but_not_across():
    same = {"same_room": True}
    assert hear_level(same, "mutter", proximity="within_reach") == "full"
    assert hear_level(same, "mutter", proximity="near") == "fragment"
    assert hear_level(same, "mutter", proximity="across") == "none"
    # Back-compat: unknown proximity keeps the old same-room -> full behavior.
    assert hear_level(same, "mutter") == "full"
    # A normal-volume line is unaffected by proximity.
    assert hear_level(same, "normal", proximity="across") == "full"


# ---- station hygiene through merge ---------------------------------------

def test_merge_carries_and_symmetrizes_stations():
    scene = {"rooms": TAVERN, "entities": {}, "positions": {"P": "taproom", "Mara": "taproom"},
             "stations": {}}
    merged = merge_scene_with_diff(scene, {"stations": {
        "P": {"at": "bar", "near": ["Mara"]}}})
    assert merged["stations"]["P"]["at"] == "bar"
    # symmetrized: Mara now lists P as near.
    assert "P" in merged["stations"]["Mara"]["near"]


def test_merge_blanks_phantom_anchor():
    scene = {"rooms": TAVERN, "entities": {}, "positions": {"P": "taproom"},
             "stations": {}}
    merged = merge_scene_with_diff(scene, {"stations": {"P": {"at": "no_such_anchor"}}})
    assert merged["stations"]["P"]["at"] is None


def test_room_move_auto_clears_stale_station():
    # P at the bar in the taproom, then moves to the cellar (no such anchor
    # there): the stale 'at' and 'near' are cleared by hygiene at merge.
    scene = {"rooms": {**TAVERN, "cellar": {"name": "Cellar"}},
             "entities": {}, "positions": {"P": "taproom", "Mara": "taproom"},
             "stations": {"P": {"at": "bar", "near": ["Mara"]},
                          "Mara": {"at": "bar", "near": ["P"]}}}
    merged = merge_scene_with_diff(scene, {"positions": {"P": "cellar"}})
    assert merged["stations"]["P"]["at"] is None      # bar not in the cellar
    assert merged["stations"]["P"]["near"] == []      # Mara no longer co-located


def test_normalize_drops_station_for_unpositioned_entity():
    scene = {"rooms": TAVERN, "positions": {"P": "taproom"},
             "stations": {"P": {"at": "bar"}, "Ghost": {"at": "hearth"}}}
    normalize_scene_stations(scene)
    assert "Ghost" not in scene["stations"]


# ---- Phase 3: rear-arc FOV (blind spots within a room) -------------------

def test_entity_arc_front_and_rear():
    # TAVERN anchors: bar=n, hearth=s, door=e. Facing WEST: the bar (north) is
    # to the side (front arc); a person at the door (east) is directly BEHIND
    # -> rear arc / blind spot.
    sc = _scene({"P": "taproom", "Barkeep": "taproom", "Creeper": "taproom"},
                {"Barkeep": {"at": "bar"}, "Creeper": {"at": "door"}},
                {"P": {"facing": "w"}})
    assert entity_arc(sc, "P", "Barkeep") == "front"
    assert entity_arc(sc, "P", "Creeper") == "rear"


def test_entity_arc_flips_when_observer_turns():
    sc = _scene({"P": "taproom", "Creeper": "taproom"},
                {"Creeper": {"at": "door"}}, {"P": {"facing": "e"}})
    # facing east, toward the door (east) -> the creeper is now in FRONT.
    assert entity_arc(sc, "P", "Creeper") == "front"


def test_entity_arc_none_without_facing():
    sc = _scene({"P": "taproom", "Creeper": "taproom"},
                {"Creeper": {"at": "door"}}, {})   # no facing -> fail open
    assert entity_arc(sc, "P", "Creeper") is None


def test_same_anchor_pair_is_front_not_rear():
    # Two people AT the same anchor are side by side (within reach) -- never a
    # rear blind spot, even facing 'away' from that anchor's room bearing.
    sc = _scene({"P": "taproom", "Q": "taproom"},
                {"P": {"at": "door"}, "Q": {"at": "door"}}, {"P": {"facing": "w"}})
    assert entity_arc(sc, "P", "Q") == "front"   # door dir e, facing w would be 'rear' by bearing
    assert entity_side(sc, "P", "Q") is None     # no meaningful side at the same spot


# ---- Phase 3: room_layout (the look-around map) --------------------------

def test_room_layout_sides_from_facing():
    sc = _scene({"P": "taproom"}, {}, {"P": {"facing": "e"}})
    layout = room_layout(sc, "P")
    assert layout["facing_known"] is True
    sides = {a["desc"]: a["side"] for a in layout["anchors"]}
    # facing east (TAVERN: bar=n, hearth=s, door=e): bar=left, hearth=right,
    # door=ahead.
    assert sides["the long oak bar"] == "left"
    assert sides["the great stone hearth"] == "right"
    assert sides["the front door"] == "ahead"


def test_room_layout_no_facing_gives_topological_anchors():
    sc = _scene({"P": "taproom"}, {}, {})   # no facing
    layout = room_layout(sc, "P")
    assert layout["facing_known"] is False
    assert all(a["side"] is None for a in layout["anchors"])  # topological only
