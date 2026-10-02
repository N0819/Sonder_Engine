"""Inside a thing with rooms is in those rooms, wherever its outside is.

Chat 160 (2026-10-01): Sarah Moon was positioned in the room `elevator_car`
and contained `inside` `freight_elevator`, whose interior room it is. The car
was called down and the Director stood its outside in the route room
`elevator_shaft`, as a vehicle under way stands; `derive_contained_positions`
read only that outside and put her in the shaft, while Hinami -- positioned
in the car, contained in nothing -- stayed in it.
"""

from world.spatial import derive_contained_positions


def _scene(mode="inside"):
    return {
        "rooms": {
            "elevator_car": {"name": "Freight Elevator Car", "parent_entity": "freight_elevator", "adjacent": []},
            "elevator_shaft": {"name": "Elevator Shaft", "adjacent": []},
            "hallway_upper": {"name": "Upper Hallway", "adjacent": []},
        },
        "entities": {"freight_elevator": {"name": "Freight Elevator", "kind": "vehicle",
                                          "interior_rooms": ["elevator_car"], "container": True}},
        "positions": {"freight_elevator": "elevator_shaft", "Sarah Moon": "elevator_car",
                      "Hinami": "elevator_car"},
        "contained": {"Sarah Moon": {"in": "freight_elevator", "mode": mode}},
    }


def test_a_body_inside_a_moving_vehicle_stays_in_its_car():
    sc = derive_contained_positions(_scene())
    assert sc["positions"]["Sarah Moon"] == "elevator_car" == sc["positions"]["Hinami"]


def test_one_who_had_not_yet_been_placed_inside_arrives_at_the_entry_room():
    sc = _scene()
    sc["positions"]["Sarah Moon"] = "hallway_upper"
    assert derive_contained_positions(sc)["positions"]["Sarah Moon"] == "elevator_car"


def test_a_thing_carried_by_a_body_inside_follows_her_into_the_car():
    sc = _scene()
    sc["positions"]["satchel"] = "hallway_upper"
    sc["contained"]["satchel"] = {"in": "Sarah Moon", "mode": "carried"}
    assert derive_contained_positions(sc)["positions"]["satchel"] == "elevator_car"


def test_held_by_a_thing_with_rooms_is_not_inside_it():
    """Only an inside link reaches the rooms: a body held in a giant's hand is
    where the giant stands, not in the giant's stomach."""
    sc = _scene(mode="held")
    assert derive_contained_positions(sc)["positions"]["Sarah Moon"] == "elevator_shaft"


def test_docked_in_its_route_room_a_vehicle_has_arrived():
    """One beat took the freight elevator sealed -> in_transit (into its
    route room, the shaft) -> docked at the shelter landing with ETA 0; it
    stayed in the shaft and its door opened onto it (chat 160 turn 4541)."""
    from world.spatial import settle_departures
    before = {"entities": {"freight_elevator": {"name": "Freight Elevator", "state": {"transit": {
        "phase": "docked", "route_room": "elevator_shaft"}}}},
        "positions": {"freight_elevator": "hallway_upper"}, "rooms": {}}
    merged = _scene()
    merged["rooms"]["shelter_level_landing"] = {"name": "Shelter Level Landing", "adjacent": []}
    merged["entities"]["freight_elevator"]["state"] = {"transit": {
        "phase": "docked", "destination_room": "shelter_level_landing", "eta_seconds": 0,
        "route_room": "elevator_shaft"}}
    settle_departures(before, merged)
    assert merged["positions"]["freight_elevator"] == "shelter_level_landing"
    assert "destination_room" not in merged["entities"]["freight_elevator"]["state"]["transit"]


def test_a_docked_vehicle_standing_somewhere_else_is_not_moved():
    from world.spatial import settle_departures
    merged = _scene()
    merged["positions"]["freight_elevator"] = "hallway_upper"
    merged["rooms"]["shelter_level_landing"] = {"name": "Shelter Level Landing", "adjacent": []}
    merged["entities"]["freight_elevator"]["state"] = {"transit": {
        "phase": "docked", "destination_room": "shelter_level_landing", "route_room": "elevator_shaft"}}
    settle_departures({}, merged)
    assert merged["positions"]["freight_elevator"] == "hallway_upper"


def test_the_plan_never_restores_a_door_across_an_interiors_boundary(monkeypatch):
    """The car's planned door to the upper hallway was restored after it
    docked four floors down; an interior's way out is where its entity
    stands (`apply_transit_dock_edges`). Between two rooms of one interior
    the plan still holds."""
    from world import structure
    sc = _scene()
    sc["rooms"]["cargo_bay"] = {"name": "Cargo bay", "parent_entity": "freight_elevator", "adjacent": []}
    monkeypatch.setattr(structure, "_planned_specs", lambda cid: {
        "elevator_car": ("Freight Elevator Car", {"adjacent": [
            {"to": "hallway_upper", "barrier": "open_door"}, {"to": "cargo_bay", "barrier": "open"}]}),
        "hallway_upper": ("Upper Hallway", {"adjacent": [{"to": "elevator_car", "barrier": "open_door"}]})})
    restored = structure.protect_planned_edges(1, sc)
    assert restored == [("elevator_car", "cargo_bay")]


def test_the_fringe_never_hands_an_occupied_car_its_planned_door(monkeypatch):
    """The second writer of the same door: the planned fringe supplies an
    occupied room every planned exit it lacks, and two bodies stood in the
    car (chat 160 turn 4541)."""
    from world import structure
    sc = _scene()
    sc["positions"]["freight_elevator"] = "shelter_level_landing"
    sc["rooms"]["shelter_level_landing"] = {"name": "Shelter Level Landing", "adjacent": []}
    sc["rooms"]["elevator_car"]["adjacent"] = [{"to": "shelter_level_landing", "barrier": "closed_door"}]
    monkeypatch.setattr(structure, "_planned_specs", lambda cid: {
        "elevator_car": ("Freight Elevator Car", {"adjacent": [
            {"to": "hallway_upper", "barrier": "open_door"}, {"to": "elevator_shaft", "barrier": "open"}]})})
    structure.materialize_planned_fringe(1, sc)
    assert [e["to"] for e in sc["rooms"]["elevator_car"]["adjacent"]] == ["shelter_level_landing"]
    assert structure.crosses_an_interior(sc["rooms"], "elevator_car", "hallway_upper")
    assert not structure.crosses_an_interior(sc["rooms"], "hallway_upper", "elevator_shaft")
