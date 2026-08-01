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


# ---- the field reaching the scene at all ---------------------------------
#
# Every test above ran against a hand-built scene. In production the field was
# undeclared on both StateDiff and ScenePatch, so Pydantic's default
# extra="ignore" deleted it before merge_scene_with_diff ever saw one: 0 of 45
# live scenes carried a station, while 17 model outputs across the same
# database contained one the schema had thrown away.

def test_state_diff_carries_stations_through_validation():
    from schemas import StateDiff, _dump
    out = _dump(StateDiff(**{"stations": {"Hinami": {"at": "bed", "near": []}}}))
    assert out["stations"] == {"Hinami": {"at": "bed", "near": []}}


def test_scene_patch_carries_stations_through_validation():
    from schemas import ScenePatch, _dump
    out = _dump(ScenePatch(**{"stations": {"Barkeep": {"at": "bar"}}}))
    assert out["stations"] == {"Barkeep": {"at": "bar"}}


def test_a_diff_touching_only_at_keeps_the_standing_near_list():
    """Why `stations` is a plain dict and not a typed sub-model: a typed one
    would default-fill `near` and clobber the standing roster every beat."""
    sc = _scene({"P": "taproom", "Mara": "taproom"},
                {"P": {"at": "bar", "near": ["Mara"]}, "Mara": {"at": "bar"}})
    sc = merge_scene_with_diff(sc, {"stations": {"P": {"at": "hearth"}}})

    assert sc["stations"]["P"]["at"] == "hearth"
    assert "Mara" in sc["stations"]["P"]["near"]


def test_an_explicit_null_at_survives_validation():
    """The only way to say "stepped away from the fixture". `_dump` uses
    exclude_none, which would have deleted a typed Optional field."""
    from schemas import StateDiff, _dump
    assert _dump(StateDiff(**{"stations": {"P": {"at": None}}}))["stations"] \
        == {"P": {"at": None}}


def test_a_bare_string_station_reads_as_its_anchor():
    from schemas import StateDiff, _dump
    assert _dump(StateDiff(**{"stations": {"P": "bar"}}))["stations"] \
        == {"P": {"at": "bar"}}


# ---- derivation: the ledger models maintain seeds the one they do not ----

BEDROOM = {
    "bedroom": {
        "name": "Bedroom", "size": "small", "adjacent": [],
        "anchors": {"bed": {"desc": "a wide bed", "dir": "s"},
                    "hearth": {"desc": "a low hearth", "dir": "w"}},
    },
    "hall": {"name": "Hall", "adjacent": []},
}


def _bedroom(**over):
    scene = {
        "rooms": BEDROOM,
        "positions": {"Hinami": "bedroom", "Elyndra": "bedroom",
                      "bed": "bedroom"},
        "entities": {"bed": {"name": "Wide Bed", "kind": "furniture",
                             "aliases": ["mattress"]}},
        "attire": {"Hinami": {"wearing": []}, "Elyndra": {"wearing": []}},
        "contacts": [], "stations": {},
    }
    scene.update(over)
    return scene


def _touch(actor, actor_part, target, target_part, manner="touch"):
    return {"op": "add", "actor": actor, "actor_part": actor_part,
            "target": target, "target_part": target_part, "manner": manner}


def test_a_contact_with_an_anchor_backed_entity_stations_the_body_there():
    """A hand on the quilt is a body at the bed. The Director fills contact
    reliably and stations essentially never, so contact seeds the station."""
    sc = merge_scene_with_diff(_bedroom(), {"contact_ops": [
        _touch("Elyndra", "palm", "bed", "quilt", "rest")]})

    assert sc["stations"]["Elyndra"]["at"] == "bed"


def test_two_bodies_in_contact_become_mutual_near_links():
    sc = merge_scene_with_diff(_bedroom(), {"contact_ops": [
        _touch("Elyndra", "lips", "Hinami", "lips", "kiss")]})

    assert proximity_rel(sc, "Hinami", "Elyndra") == "within_reach"


def test_furniture_never_gets_a_station_of_its_own():
    sc = merge_scene_with_diff(_bedroom(), {"contact_ops": [
        _touch("Elyndra", "palm", "bed", "quilt", "rest")]})

    assert "bed" not in sc["stations"]


def test_derivation_never_overrides_what_the_beat_stated():
    sc = merge_scene_with_diff(_bedroom(), {
        "stations": {"Elyndra": {"at": "hearth"}},
        "contact_ops": [_touch("Elyndra", "palm", "bed", "quilt", "rest")]})

    assert sc["stations"]["Elyndra"]["at"] == "hearth"


def test_a_station_outlives_the_contact_that_derived_it():
    """You do not leave the bed by taking your hand off the quilt."""
    sc = merge_scene_with_diff(_bedroom(), {"contact_ops": [
        _touch("Elyndra", "palm", "bed", "quilt", "rest")]})
    sc = merge_scene_with_diff(sc, {"contact_ops": [{"op": "clear"}]})

    assert sc["stations"]["Elyndra"]["at"] == "bed"


def test_leaving_the_room_still_clears_a_derived_station():
    sc = merge_scene_with_diff(_bedroom(), {"contact_ops": [
        _touch("Elyndra", "palm", "bed", "quilt", "rest")]})
    sc = merge_scene_with_diff(sc, {"positions": {"Elyndra": "hall"}})

    assert sc["stations"]["Elyndra"]["at"] is None


def test_a_scene_that_says_nothing_still_gets_a_stations_table():
    """The key always exists after a merge, so no reader has to guess whether
    absence means "nowhere" or "not tracked"."""
    assert merge_scene_with_diff(_bedroom(), {}).get("stations") == {}


def test_the_bodys_own_position_string_can_seat_it_at_an_anchor():
    """`state.position: "seated_on_bed_edge"` was the live record, and it was
    the only thing in the engine that knew she was on the bed -- read by
    nothing. Identifier recognition against that room's OWN anchor ids, never
    prose parsing, and only where nothing better has spoken."""
    sc = _bedroom(entities={
        "bed": {"name": "Wide Bed", "kind": "furniture"},
        "hinami": {"name": "Hinami", "kind": "person",
                   "state": {"position": "seated_on_bed_edge"}}})
    sc = merge_scene_with_diff(sc, {})

    assert sc["stations"]["Hinami"]["at"] == "bed"


def test_a_position_string_never_overrides_a_stated_station():
    sc = _bedroom(entities={
        "bed": {"name": "Wide Bed", "kind": "furniture"},
        "hinami": {"name": "Hinami", "kind": "person",
                   "state": {"position": "seated_on_bed_edge"}}})
    sc = merge_scene_with_diff(sc, {"stations": {"Hinami": {"at": "hearth"}}})

    assert sc["stations"]["Hinami"]["at"] == "hearth"


def test_a_position_naming_no_anchor_stations_nobody():
    sc = _bedroom(entities={
        "hinami": {"name": "Hinami", "kind": "person",
                   "state": {"position": "standing_uncertainly"}}})
    sc = merge_scene_with_diff(sc, {})

    assert not (sc["stations"].get("Hinami") or {}).get("at")


def test_an_echoed_room_that_mentions_no_anchors_does_not_erase_them():
    """The validation round-trip emits every declared field, so an empty
    `anchors` rides out on any room the Director merely re-describes -- and
    the catch-all merge would read it as an erasure, taking every station
    hanging off those anchors with it."""
    sc = merge_scene_with_diff(_bedroom(), {"rooms": {"bedroom": {
        "name": "Bedroom", "desc": "warmer now", "anchors": {}, "size": None}}})

    assert set(sc["rooms"]["bedroom"]["anchors"]) == {"bed", "hearth"}


def test_a_room_def_carries_anchors_and_size_through_validation():
    """Undeclared until now, so the round-trip stripped them from every
    Director-authored room -- the only anchors any story had came in through
    the mapping stage's untyped patch dicts."""
    from schemas import RoomDef, _dump
    out = _dump(RoomDef(**{"name": "Bedroom", "size": "small",
                           "anchors": {"bed": {"desc": "a wide bed", "dir": "s"}}}))

    assert out["anchors"]["bed"]["dir"] == "s"
    assert out["size"] == "small"


def test_an_unmentioned_anchors_table_is_absent_rather_than_empty():
    """Why `anchors` is Optional and not default_factory=dict: silence has to
    stay silence through the dump, or every room echo carries an eraser."""
    from schemas import RoomDef, _dump
    assert "anchors" not in _dump(RoomDef(**{"name": "Bedroom"}))
