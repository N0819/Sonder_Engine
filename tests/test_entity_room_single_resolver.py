"""Where an entity IS has one resolver (review 2026-09-07 finding B18).

`room_of` is the engine's "where is X". Every site that holds an entity
record and wants its room asks the same label walk -- entity id, name, then
aliases, each looked up with the same case/script tolerance -- instead of
re-implementing a narrower one against `positions` with exact strings.

The class: `positions` is keyed by whatever the writer used, so an entity
whose row is filed under its display name or an alias (or under its id in a
different case) is placed; a site walking labels with `in positions` reads it
as nowhere, and everything downstream fails closed -- a severed dock edge, an
unlit room, a silent machine, a zone the vehicle never arrived in.
"""

from world.spatial import (apply_transit_dock_edges, containment_chain,
                           room_of)


def _lift_scene(position_key):
    """A lift car whose interior room hangs off it, with the car's own
    position filed under `position_key` -- the spelling variation the live
    scenes actually produce."""
    return {
        "rooms": {
            "lobby": {"name": "Lobby", "adjacent": []},
            "lift_interior": {"name": "Lift car",
                              "parent_entity": "Lift_Car",
                              "adjacent": []},
        },
        "entities": {
            "Lift_Car": {
                "kind": "vehicle",
                "name": "the lift car",
                "aliases": ["service lift"],
                "interior_rooms": ["lift_interior"],
                "state": {"transit": {"phase": "docked", "hatch": "open"}},
            },
        },
        "positions": {position_key: "lobby"},
    }


def _dock_targets(scene):
    return {e.get("to") for e in
            (scene["rooms"]["lift_interior"].get("adjacent") or [])
            if isinstance(e, dict)}


def test_dock_edge_derived_from_position_filed_under_the_id():
    scene = _lift_scene("Lift_Car")
    apply_transit_dock_edges(scene)
    assert _dock_targets(scene) == {"lobby"}


def test_dock_edge_derived_from_position_filed_under_the_name():
    scene = _lift_scene("The Lift Car")
    assert room_of(scene, "Lift_Car") == "lobby"
    apply_transit_dock_edges(scene)
    assert _dock_targets(scene) == {"lobby"}


def test_dock_edge_derived_from_position_filed_under_an_alias():
    scene = _lift_scene(" Service Lift ")
    assert room_of(scene, "Lift_Car") == "lobby"
    apply_transit_dock_edges(scene)
    assert _dock_targets(scene) == {"lobby"}


def test_dock_edge_derived_from_a_differently_cased_id():
    scene = _lift_scene("lift_car")
    assert room_of(scene, "Lift_Car") == "lobby"
    apply_transit_dock_edges(scene)
    assert _dock_targets(scene) == {"lobby"}


def test_containment_chain_walks_out_through_a_tolerant_position():
    scene = _lift_scene("Service Lift")
    chain = containment_chain(scene, "lift_interior")
    assert [step["room"] for step in chain] == ["lift_interior", "lobby"]


def _emitter_scene(position_key, extra):
    """One emitter in a cellar, its position filed under `position_key`."""
    entity = {"kind": "object", "name": "storm lantern",
              "aliases": ["the hooked lamp"], "state": {"lit": True}}
    entity.update(extra)
    return {
        "rooms": {"cellar": {"name": "Cellar"}},
        "entities": {"lantern_1": entity},
        "positions": {position_key: "cellar"},
    }


def test_light_source_filed_under_an_alias_still_lights_its_room():
    from world.spatial import source_light
    scene = _emitter_scene("The Hooked Lamp", {"light_source": "bright"})
    assert source_light(scene, "cellar") == "bright"


def test_a_doused_fixture_filed_under_an_alias_still_darkens_its_room():
    """`ambient_floor_word` yields the declared word to a room whose only
    fixture is out -- which needs the fixture to be found at all."""
    from world.spatial import ambient_floor_word
    scene = _emitter_scene("The Hooked Lamp", {"light_source": "bright"})
    scene["rooms"]["cellar"]["light"] = "bright"
    scene["entities"]["lantern_1"]["state"] = {"lit": False}
    assert ambient_floor_word(scene, "cellar") == "dark"


def test_sound_source_filed_under_an_alias_still_sounds_in_its_room():
    from world.spatial import sound_sources
    scene = _emitter_scene("The Hooked Lamp",
                           {"sound_source": "loud", "state": {"running": True}})
    sources, _notices = sound_sources(scene)
    assert [s["room"] for s in sources] == ["cellar"]


def test_zone_follows_a_vehicle_whose_position_is_filed_under_its_name():
    """A party member riding an interior room is attributed to the zone of
    the room the vehicle itself stands in -- resolved by identity, so the
    vehicle's own position row need not be filed under its id."""
    from world.spatial_frames import _effective_zone
    scene = {
        "rooms": {
            "dock": {"name": "Dock", "zone": "harbour"},
            "cabin": {"name": "Cabin", "parent_entity": "Ferry_01"},
        },
        "entities": {"Ferry_01": {"kind": "vehicle", "name": "the ferry",
                                  "interior_rooms": ["cabin"]}},
        "positions": {"Hinami": "cabin", "The Ferry": "dock"},
    }
    assert _effective_zone(scene, "Hinami") == "harbour"


# ---------------------------------------------------------------------------
# The same rule at the sites outside `world/spatial_*` that iterate
# `scene["entities"]` and then read `positions` by id alone.
# ---------------------------------------------------------------------------


def _ferry_scene(exterior_room):
    return {
        "rooms": {
            "dock": {"name": "Dock", "adjacent": []},
            "island": {"name": "Island", "adjacent": []},
            "cabin": {"name": "Cabin", "parent_entity": "Ferry_01",
                      "adjacent": []},
        },
        "entities": {"Ferry_01": {"kind": "vehicle", "name": "the ferry",
                                  "aliases": ["The Ferry"],
                                  "interior_rooms": ["cabin"]}},
        "positions": {"Hinami": "cabin", "The Ferry": exterior_room},
    }


def test_gap_crossing_stamps_a_zone_for_a_ferry_filed_under_its_name(
        monkeypatch):
    """A vehicle carrying a party member across a gap is recognised by
    identity, not by whether `positions` happens to be keyed by its id
    (review 2026-09-07, B18)."""
    from world import spatial_frames
    monkeypatch.setattr(spatial_frames, "_all_party_names",
                        lambda chat_id, frame_id: ["Hinami"])
    prev_scene = _ferry_scene("dock")
    new_scene = _ferry_scene("island")

    assert spatial_frames.infer_vehicle_zones(1, None, prev_scene, new_scene)
    rooms = new_scene["rooms"]
    assert rooms["island"].get("zone")
    assert rooms["dock"].get("zone") != rooms["island"].get("zone")
    # And the party member riding the interior arrives with it.
    assert spatial_frames._effective_zone(new_scene, "Hinami") == \
        rooms["island"]["zone"]


def test_narrator_reports_the_hatch_of_a_lift_filed_under_an_alias():
    """A transit hatch the player can see is reported whatever spelling the
    vehicle's position row is filed under (review 2026-09-07, B18)."""
    from agents.narration import _visible_portal_states
    scene = _lift_scene(" Service Lift ")
    states = _visible_portal_states(scene, "lobby", {"lobby"})
    assert states.get("the lift car hatch") == "open"


def test_transit_arrival_event_is_filed_at_the_room_the_mover_is_in():
    """The scheduled arrival carries where the mover IS, not what its id is
    keyed to (review 2026-09-07, B18)."""
    from world.mechanics import _schedule_new_arrivals
    scene = _ferry_scene("dock")
    scene["entities"]["Ferry_01"]["state"] = {
        "transit": {"phase": "in_transit", "eta_seconds": 30,
                    "destination_room": "island"}}
    event_ops, scheduled = _schedule_new_arrivals(
        scene, 0.0, None, set(), 1, 7, 3)
    assert scheduled == 1
    assert event_ops[0][1]["location_id"] == "dock"


def test_a_shed_garment_in_another_room_is_out_of_reach_when_filed_by_name():
    """Reach is measured from where the garment IS. Filed under its display
    name it read as lying nowhere, which passes the reach test by accident
    and merged a coat left a room away (review 2026-09-07, B18)."""
    from persist.commit import _reclaim_worn_shed_garments
    sc = {
        "entities": {"coat_1": {"name": "Wool Coat",
                                "state": {"clothing": True, "shed": True,
                                          "worn_by": "Hinami",
                                          "garment": "wool coat"}}},
        "positions": {"Hinami": "hall", "Wool Coat": "cellar"},
        "attire": {"Hinami": []},
    }
    reclaimed = _reclaim_worn_shed_garments(sc, {}, None,
                                            {"Hinami": ["wool coat"]})
    assert reclaimed == []
    assert "coat_1" in sc["entities"]

    # The other direction of the same read: lying where the body is, it is
    # still within reach and still reclaimed. Resolving the room is not a
    # licence to refuse.
    sc["positions"]["Wool Coat"] = "hall"
    reclaimed = _reclaim_worn_shed_garments(sc, {}, None,
                                            {"Hinami": ["wool coat"]})
    assert [row[0] for row in reclaimed] == ["coat_1"]
    assert "coat_1" not in sc["entities"]


def test_the_folded_index_answers_exactly_what_the_scans_answer():
    """`PositionsIndex` is a performance shape, not a behaviour one (review
    2026-09-07, B18): one folded read of `positions` in place of two linear
    scans per label, for a sweep that asks once per label per entity."""
    from world.spatial import PositionsIndex, _positions_lookup
    positions = {"Lift_Car": "lobby", " Service Lift ": "yard",
                 "ひなみ": "garden", "Ferry_01": "dock"}
    index = PositionsIndex(positions)
    for spelling in ("Lift_Car", "lift_car", " LIFT_CAR ", "service lift",
                     "Service Lift", "ひなみ", "Ferry_01",
                     "nobody", "", "the ferry"):
        assert _positions_lookup(positions, spelling, index=index) == \
            _positions_lookup(positions, spelling), spelling


def test_the_picture_and_the_light_field_agree_about_a_fixture_filed_under_an_alias():
    """The backdrop prompt's light-source sweep is a fourth copy of the light
    emitter sweep, in `dressing/backdrops`, and it walked `positions` by
    exact id then exact name (B18, second rework). A room-filling fixture
    filed under an alias read as lit to `source_light` and as lit by nothing
    to its own picture -- one fact stored twice and free to disagree."""
    from dressing.backdrops import _light_sources_in
    from world.spatial import source_light

    scene = _emitter_scene("The Hooked Lamp",
                           {"light_source": "bright", "light_radius": "room"})
    assert source_light(scene, "cellar") == "bright"
    pictured = _light_sources_in(scene, "cellar")
    assert [p["name"] for p in pictured] == ["storm lantern"], pictured
    assert pictured[0]["emits"] == "bright"
    assert pictured[0]["fills_room"] is True
