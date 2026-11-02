"""A building lot (`world/lots.py`): one planned place standing for a whole
building nobody has entered, expanded into the building's rooms when the
player or a major character first comes upon it (`agents/director_lots.py`),
then laid out as one building by the layout tier whatever its storeys
(`world/layout_bridge.py`). The owner's idea, 2026-10-28: "mark spaces as a
building generation for when an actor like a player or major character
stumble upon it. These marked spaces can act as homes and work places for
charter npcs.\""""
from __future__ import annotations

import copy
import time

import pytest

from world import layout_bridge as lb
from world.lots import LOT_KEY, LOT_OF_KEY, is_unexpanded_lot, normalize_lot


STREET = ("the Street", {"purpose": "the village street", "exposure": "open",
                         "adjacent": [{"to": "store", "dir": "n", "barrier": "closed_door"}]})
STORE = ("the General Store", {
    "purpose": "the general store, the grocer's family living above it", "exposure": "enclosed",
    "far_look": "a two-storey timber shopfront", "extent": {"w": 10, "d": 8},
    "lot": {"storeys": 2},
    "adjacent": [{"to": "street", "dir": "s", "barrier": "a glazed shop door"}]})

ANSWER = {"rooms": [
    {"id": "shop", "name": "the Shop", "purpose": "where goods are sold over the counter",
     "level": 0, "entry": True,
     "joins": [{"to": "store_room", "side": "n", "barrier": "a plank door"},
               {"to": "living_room", "vertical": "up", "way": "stair"}]},
    {"id": "store_room", "name": "the Store Room", "purpose": "where stock is kept", "level": 0},
    {"id": "living_room", "name": "the Living Room", "purpose": "where the family eats and sits",
     "level": 1, "joins": [{"to": "bedroom", "side": "e", "barrier": "a door"},
                           {"to": "attic", "vertical": "up", "way": "ladder"},
                           {"to": "nowhere", "side": "w"}]},
    {"id": "bedroom", "name": "the Bedroom", "purpose": "where the family sleeps",
     "level": 1, "sleeps": 3},
    {"id": "attic", "name": "the Attic", "purpose": "storage under the roof", "level": 3},
    {"id": "shed", "name": "the Shed", "purpose": "joined to nothing", "level": 0}]}


def _rows(specs):
    return {uid: {"name": name, "planned": copy.deepcopy(spec)} for uid, (name, spec) in specs.items()}


def test_a_lot_record_reads_only_what_the_engine_holds():
    assert normalize_lot(True) == {}
    assert normalize_lot(None) is None and normalize_lot("a lot") is None
    assert normalize_lot({"storeys": 9, "cellar": True, "colour": "red"}) == {"storeys": 4, "cellar": True}
    assert normalize_lot({"storeys": 0}) == {}
    assert is_unexpanded_lot({"lot": {}}) and not is_unexpanded_lot({"lot": {"expanded": 3}})
    assert not is_unexpanded_lot({"purpose": "a room"})


def test_the_rooms_plan_keeps_a_lot_and_never_its_expanded_turn():
    """The Room may mark a lot; only the engine says it was expanded."""
    from story.plot_packages import _shape_plan_rooms
    op = _shape_plan_rooms({"structure": {"key": "village"}, "rooms": {
        "store": {"name": "the General Store", "purpose": "a shop",
                  "lot": {"storeys": 2, "expanded": 7}},
        "lane": {"name": "the Lane", "purpose": "a lane"}}})
    assert op["rooms"]["store"]["lot"] == {"storeys": 2}
    assert "lot" not in op["rooms"]["lane"]


def test_the_architects_answer_is_held_to_the_engines_rules():
    """The entry keeps the lot's uid, name, far look and way onto the street;
    every other room is a new room of the lot, marked `lot_of`; a join to a
    room the answer does not hold, a stair past a neighbouring storey and a
    room reached by nothing are set aside, each said."""
    from agents.director_lots import planned_rooms_of
    rows = _rows({"street": STREET, "store": STORE})
    rooms, notes, sleeps = planned_rooms_of("store", rows, ANSWER, turn_idx=5)
    assert set(rooms) == {"store", "store__store_room", "store__living_room", "store__bedroom"}
    entry = rooms["store"]
    assert entry["name"] == "the General Store"
    assert entry["far_look"] == "a two-storey timber shopfront"
    assert entry[LOT_KEY] == {"storeys": 2, "expanded": 5, "footprint": {"w": 10, "d": 8},
                              "building": "the general store, the grocer's family living above it"}
    assert {e["to"] for e in entry["adjacent"]} == {"street", "store__store_room", "store__living_room"}
    stair = next(e for e in entry["adjacent"] if e["to"] == "store__living_room")
    assert stair["vertical"] == "up" and stair["way"] == "stair"
    assert all(spec[LOT_OF_KEY] == "store" and spec["exposure"] == "enclosed" for spec in rooms.values())
    assert rooms["store__living_room"]["level"] == 1
    assert sleeps == {"store__bedroom": 3}
    said = " ".join(notes)
    assert "nowhere" in said and "attic" in said and "shed" in said


def test_an_answer_with_no_ground_storey_plants_nothing():
    from agents.director_lots import planned_rooms_of
    rows = _rows({"street": STREET, "store": STORE})
    rooms, notes, _ = planned_rooms_of("store", rows, {"rooms": [{"id": "loft", "level": 1}]})
    assert rooms == {} and notes


def _expanded_specs():
    from agents.director_lots import planned_rooms_of
    rows = _rows({"street": STREET, "store": STORE})
    rooms, _notes, _ = planned_rooms_of("store", rows, ANSWER, turn_idx=5)
    specs = {"street": STREET}
    for uid, spec in rooms.items():
        specs[uid] = (spec["name"], dict(spec, structure="village"))
    specs["street"] = ("the Street", dict(STREET[1], structure="village"))
    return specs


def test_a_lot_expanded_is_one_building_to_the_layout_tier():
    """The rooms a lot was expanded into are one building, its entry's door
    onto the street its entrance."""
    (b,) = lb.plan_buildings(_expanded_specs(), {"rooms": {}})
    assert b["refusal"] is None
    assert set(b["rooms"]) == {"store", "store__store_room", "store__living_room", "store__bedroom"}
    assert b["lot"] == "store" and b["entrance"]["room"] == "store"


def test_a_one_storey_lot_is_laid_out_and_a_one_storey_house_is_not():
    """One storey is no building to lay out -- the doorway walk places a
    cottage's rooms -- save a lot's, whose rooms the lot says are one."""
    specs = _expanded_specs()
    for uid in ("store__living_room", "store__bedroom"):
        specs.pop(uid)
    entry = specs["store"][1]
    entry["adjacent"] = [e for e in entry["adjacent"] if e["to"] in ("street", "store__store_room")]
    (b,) = lb.plan_buildings(copy.deepcopy(specs), {"rooms": {}})
    assert b["refusal"] is None and b["lot"] == "store"
    for spec in (specs["store"][1], specs["store__store_room"][1]):
        spec.pop(LOT_OF_KEY)
    assert lb.plan_buildings(specs, {"rooms": {}}) == []


def test_two_lots_that_share_a_wall_are_two_buildings():
    specs = _expanded_specs()
    specs["store__store_room"][1]["adjacent"] = [{"to": "store", "dir": "s"},
                                                 {"to": "bakery", "dir": "e", "barrier": "a door"}]
    specs["bakery"] = ("the Bakery", {"purpose": "the bakery", "structure": "village",
                                      "exposure": "enclosed", "level": 0, LOT_OF_KEY: "bakery",
                                      "adjacent": [{"to": "store__store_room", "dir": "w"},
                                                   {"to": "street", "dir": "s"}]})
    buildings = lb.plan_buildings(specs, {"rooms": {}})
    store = next(b for b in buildings if "store" in b["rooms"])
    assert "bakery" not in store["rooms"]


def _chat(db):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Lots", "A village.", time.time()))
    for i in range(3):
        db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
              (cid, i, "", time.time()))
    return cid


def _plant(cid):
    from world.structure import plant_structure
    rooms = {uid: dict(copy.deepcopy(spec), name=name) for uid, (name, spec)
             in {"street": STREET, "store": STORE}.items()}
    plant_structure(cid, {"key": "village", "name": "The Village"}, rooms)


def _architect(calls):
    def call(step, system, payload):
        calls.append((step, payload))
        return copy.deepcopy(ANSWER)
    return call


def test_a_lot_is_planted_with_its_mark_and_kept_from_single_room_design(temp_db):
    """Planted, the lot keeps its record; the job between turns never designs
    it as one room (`rooms_to_build`), as it never designs a frontier space."""
    from agents.director_rooms import rooms_to_build
    from world.structure import registry_rows
    cid = _chat(temp_db)
    _plant(cid)
    assert registry_rows(cid)["store"]["planned"]["lot"] == {"storeys": 2}
    scene = {"rooms": {"street": {"name": "the Street", "desc": "A street.",
                                  "adjacent": [{"to": "store", "barrier": "open_door"}]},
                       "store": {"name": "the General Store", "planned": True, "adjacent": []}},
             "positions": {"Hinami": "street"}}
    assert "store" not in rooms_to_build(cid, scene, ["Hinami"])


def test_a_lot_an_actor_stands_beside_is_expanded_into_its_building(temp_db):
    """Standing on the street at its door, whatever the door: the architect
    is asked once, with the lot, its door and its people; the building's rooms
    are planted under the lot's part of the map, the entry keeping the lot's
    uid, and the lot is expanded once."""
    from agents.director_lots import LOT_STEP, expand_lots_near
    from world.structure import registry_rows
    cid = _chat(temp_db)
    _plant(cid)
    scene = {"rooms": {"street": {"name": "the Street", "desc": "A street.",
                                  "adjacent": [{"to": "store", "barrier": "closed_door"}]},
                       "store": {"name": "the General Store", "planned": True, "adjacent": []}},
             "positions": {"Hinami": "street"}}
    calls = []
    done = expand_lots_near(None, cid, scene, ["Hinami"], "en", call=_architect(calls))
    assert done == ["store"]
    assert [step for step, _p in calls] == [LOT_STEP]
    lot = calls[0][1]["lot"]
    assert lot["name"] == "the General Store" and lot["storeys"] == 2
    assert lot["door"] == {"opens_onto": "the Street", "side": "s", "barrier": "a glazed shop door"}
    rows = registry_rows(cid)
    assert rows["store"]["planned"]["lot"]["expanded"] == 0
    assert rows["store__living_room"]["planned"]["structure"] == "village"
    assert rows["store__living_room"]["planned"][LOT_OF_KEY] == "store"
    assert expand_lots_near(None, cid, scene, ["Hinami"], "en", call=_architect(calls)) == []
    assert len(calls) == 1


def test_a_lot_the_story_has_described_is_never_expanded(temp_db):
    from agents.director_lots import expand_lot
    cid = _chat(temp_db)
    _plant(cid)
    scene = {"rooms": {"store": {"name": "the General Store", "desc": "A dim shop."}}}
    calls = []
    assert expand_lot(cid, "store", scene, call=_architect(calls), language_id="en") == []
    assert calls == []


def test_a_failed_answer_waits_before_it_is_asked_again(temp_db):
    from agents.director_lots import LOT_RUNS_KEY, expand_lot
    cid = _chat(temp_db)
    _plant(cid)
    asked = []

    def broken(step, system, payload):
        asked.append(step)
        return {"rooms": "none"}
    assert expand_lot(cid, "store", {}, call=broken, language_id="en", turn_idx=2) == []
    assert temp_db.wget(cid, LOT_RUNS_KEY)["store"]["failed"] == 1
    assert expand_lot(cid, "store", {}, call=broken, language_id="en", turn_idx=2) == []
    assert len(asked) == 1


def test_a_beat_that_walks_into_a_lot_designs_its_entry_with_the_building_beyond(temp_db):
    """The beat that enters a lot the job has not reached expands it first:
    the room it designs is the building's entry, its exits the building's
    rooms, never the whole building in one room."""
    from agents.director_lots import expand_entered_lots
    cid = _chat(temp_db)
    _plant(cid)
    scene = {"rooms": {"street": {"name": "the Street", "desc": "A street.",
                                  "adjacent": [{"to": "store"}]},
                       "store": {"name": "the General Store", "planned": True, "adjacent": []}},
             "positions": {"Hinami": "store"}}
    old = {"store": {"name": "the General Store", "purpose": "the general store",
                     "exits": [{"to": "street", "name": "the Street"}]}}
    calls = []
    develop = expand_entered_lots(cid, old, scene, "en", call=_architect(calls), turn_idx=2)
    exits = {e["to"] for e in develop["store"]["exits"]}
    assert {"store__store_room", "store__living_room"} <= exits
    assert develop["store"]["purpose"] == "where goods are sold over the counter"


def test_the_lots_sleepers_are_dealt_into_the_rooms_they_sleep_in(monkeypatch):
    """Every body berthed at the lot goes to a room the architect says people
    sleep in, filled to its count and the rest to the last; where nobody is
    said to sleep, nothing moves."""
    from agents import director_lots
    import world.charter_runtime as runtime
    registry = {"items": {"household": {"state": {"bodies": {
        f"b{k}": {"berth": "store", "place": "store"} for k in range(4)} | {
        "other": {"berth": "elsewhere", "place": "elsewhere"}}}}}}
    saved = []
    monkeypatch.setattr(runtime, "registry_for_update", lambda cid, frame_id=None: registry)
    monkeypatch.setattr(runtime, "save_registry", lambda cid, reg, frame_id=None: saved.append(reg))
    moved = director_lots.deal_berths(1, "store", {"store__bedroom": 2, "store__loft": 1})
    bodies = registry["items"]["household"]["state"]["bodies"]
    assert moved == 4 and saved
    assert [bodies[f"b{k}"]["berth"] for k in range(4)] == \
        ["store__bedroom", "store__bedroom", "store__loft", "store__loft"]
    assert all(bodies[f"b{k}"]["place"] == "store" for k in range(4))
    assert bodies["other"]["berth"] == "elsewhere"
    assert director_lots.deal_berths(1, "store", {}) == 0


def test_a_lot_is_never_split_into_copies_of_itself():
    """A lot is a whole building: the closure deals an overfull berth into
    siblings, and a lot's sleepers wait for its rooms instead."""
    from world.charter_generate import _spread_berths
    rooms = {"store": {"name": "the General Store", "purpose": "a shop",
                       "lot": {}, "adjacent": [{"to": "street"}]},
             "street": {"name": "the Street", "purpose": "a street", "adjacent": [{"to": "store"}]}}
    bodies = {f"b{k}": {"berth": "store", "place": "store"} for k in range(12)}
    _spread_berths(rooms, [("household", bodies, [])], ceiling=8)
    assert set(rooms) == {"store", "street"}
    assert all(b["berth"] == "store" for b in bodies.values())


def test_the_lot_a_body_walks_to_is_expanded_before_the_ones_it_sees(temp_db):
    """A street of open doors puts every house on it in view; the house a
    body is walking to is the one expanded first."""
    from agents.director_lots import lots_near
    from world.structure import plant_structure
    cid = _chat(temp_db)
    rooms = {"street": dict(copy.deepcopy(STREET[1]), name="the Street",
                            adjacent=[{"to": "a_house", "barrier": "open_door"},
                                      {"to": "store", "barrier": "open_door"}]),
             "a_house": {"name": "A House", "purpose": "a household", "exposure": "enclosed",
                         "lot": {}, "adjacent": [{"to": "street", "barrier": "open_door"}]},
             "store": dict(copy.deepcopy(STORE[1]), name="the General Store")}
    plant_structure(cid, {"key": "village", "name": "The Village"}, rooms)
    scene = {"rooms": {"street": {"name": "the Street", "desc": "A street.",
                                  "adjacent": [{"to": "a_house", "barrier": "open_door"},
                                               {"to": "store", "barrier": "open_door"}]},
                       "a_house": {"name": "A House", "planned": True, "adjacent": []},
                       "store": {"name": "the General Store", "planned": True, "adjacent": []}},
             "positions": {"Hinami": "street"},
             "approach": {"Hinami": {"to_room": "store"}}}
    assert lots_near(cid, scene, ["Hinami"])[0] == "store"


def test_a_lot_is_never_the_ground_of_the_house_next_door():
    """The street is a building's ground; the next lot along it, expanded or
    not, is a building of its own and never laid as an outbuilding beside
    it -- a walked village's headman's house swept the store, the tea house,
    the shrine and three houses into its ground."""
    specs = _expanded_specs()
    specs["street"][1]["adjacent"] = [{"to": "store", "dir": "n"}, {"to": "bakery", "dir": "n"}]
    specs["bakery"] = ("the Bakery", {"purpose": "the bakery", "structure": "village",
                                      "exposure": "enclosed", "lot": {},
                                      "adjacent": [{"to": "street", "dir": "s"}]})
    (b,) = lb.plan_buildings(specs, {"rooms": {}}, grounds=True)
    assert [g["id"] for g in b["grounds"]] == ["street"]
