"""What the charter closure invents, it measures, marks and says.

Three things the closure did not do until 2026-10-08, each measured on the
Brackwater runs (`docs/design/DESIGN_CHARTER_PLACES.md`):

* it kept a drafted room's name and purpose and dropped its measurements --
  chat 166's closure-planted pile houses reached the registry with no
  exposure, though the Room's review refuses a draft without one;
* it gave a sibling its parent's doorway down to where on the wall it
  stands, and recorded nowhere which room a sibling or an annex came from;
* it hung 29 purpose-less annexes off chat 164's public walk and told the
  host and never the Room whose plan made it.

Hand-made plans; the names are illustrations, not the rule.
"""

from __future__ import annotations

import time

import pytest

from core import db
from world.charter_generate import BERTH_CEILING, berth_split_warning, close_plan
from world.frontage import ANNEX_OF, SPLIT_OF


NAMING = {"given_parts": {"starts": ["Ba", "Do", "Ke", "Mo"],
                          "ends": ["n", "rk", "lt", "ss"]},
          "family_parts": {"starts": ["Sal", "Fen", "Hol", "Wic"],
                           "ends": ["more", "den", "croft", "stead"]}}


def _plan(*, house_edge=None, workplace=False, house_name="the House",
          grammar=None):
    """A lane, a house off it, a yard; twenty people berthed in the house."""
    edge = {"to": "lane", "barrier": "open_door"}
    edge.update(house_edge or {})
    upkeep_place = "house" if workplace else "yard"
    return {
        "name": "Row",
        "structure": {"key": "row", "max_planned": 20,
                      **({"grammar": grammar} if grammar else {})},
        "rooms": {
            "lane": {"name": "the Lane", "purpose": "a lane",
                     "exposure": "open", "extent": {"w": 24, "d": 3},
                     "adjacent": [{"to": "house", "barrier": "open_door"},
                                  {"to": "yard", "barrier": "open_door"}]},
            "house": {"name": house_name, "purpose": "family dwelling",
                      "exposure": "enclosed", "extent": {"w": 6, "d": 5},
                      "level": 0, "adjacent": [edge]},
            "yard": {"name": "the Yard", "purpose": "labour",
                     "exposure": "open",
                     "adjacent": [{"to": "lane", "barrier": "open_door"}]},
        },
        "charters": [{
            "key": "yard", "naming": NAMING,
            "upkeeps": {"stack": {"place": upkeep_place, "floor": 0.3,
                                  "fails_untended": "days",
                                  "one_body_restores_in": "hours"}},
            "posts": {"hand": {"place": upkeep_place, "serves": ["stack"],
                               "requires": {"labour": 1}}},
            "populations": [{"post": "hand", "count": 20,
                             "competence": {"labour": 1}, "berth": "house"}],
        }],
    }


def test_a_drafted_rooms_measurements_survive_the_closure():
    town = close_plan(_plan())
    lane, house = town["rooms"]["lane"], town["rooms"]["house"]
    assert lane["extent"] == {"w": 24, "d": 3} and lane["exposure"] == "open"
    assert house["exposure"] == "enclosed" and house["level"] == 0
    # The same fail-open reading the package path uses: a value the world
    # cannot read is no value, never a guess.
    plan = _plan()
    plan["rooms"]["lane"].update({"extent": "very long", "exposure": "breezy"})
    lane = close_plan(plan)["rooms"]["lane"]
    assert "extent" not in lane and "exposure" not in lane


def test_a_sibling_is_marked_and_measured_like_its_parent_but_not_on_its_door():
    town = close_plan(_plan(house_edge={
        "dir": "s", "offset": 0.25, "cell": [1, 4], "passage": "front_door"}))
    split = town["closure"]["berths_split"]["house"]
    assert split["mode"] == "siblings" and len(split["rooms"]) == 2
    for uid in split["rooms"]:
        room = town["rooms"][uid]
        assert room[SPLIT_OF] == "house"
        assert room["extent"] == {"w": 6, "d": 5}
        assert room["exposure"] == "enclosed"
        (edge,) = room["adjacent"]
        assert edge["to"] == "lane" and edge["dir"] == "s"
        assert not {"offset", "cell", "passage"} & set(edge)
    # The parent keeps its own doorway exactly as drawn.
    assert town["rooms"]["house"]["adjacent"][0]["offset"] == 0.25


def test_an_annex_is_marked_and_claims_no_measurement():
    town = close_plan(_plan(workplace=True))
    split = town["closure"]["berths_split"]["house"]
    assert split["mode"] == "annexes"
    for uid in split["rooms"]:
        room = town["rooms"][uid]
        assert room[ANNEX_OF] == "house" and room["purpose"] == ""
        assert "extent" not in room and "exposure" not in room


def test_the_split_warning_tells_the_planner_how_its_plan_made_annexes():
    record = {"mode": "annexes", "rooms": ["walk_2", "walk_3"]}
    line = berth_split_warning("walk", record)
    assert "2 annexes minted (walk_2, walk_3)" in line
    assert "`berth`" in line
    sibling = berth_split_warning("house", {"mode": "siblings", "rooms": ["house_2"]})
    assert "`berth`" not in sibling and str(BERTH_CEILING) in sibling


@pytest.fixture()
def chat(temp_db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("A story", "", time.time()))


def test_the_rooms_review_says_what_the_closure_will_split(chat):
    """Chat 164: the closure hung 29 annexes off one public walk and the
    review the Room believes said nothing about it."""
    from story import location_design

    plan = _plan(workplace=True)
    location_design.open_draft(chat, {"wants_history": False})
    location_design.set_skeleton(chat, name=plan["name"],
                                 structure=plan["structure"], rooms=plan["rooms"])
    location_design.set_charter(chat, plan["charters"][0])
    result = location_design.check(chat)
    assert any("annexes minted" in note and "`berth`" in note
               for note in result["notes"]), result


def test_the_plan_keeps_a_split_rooms_mark_through_planting(chat):
    from world.structure import plant_structure, registry_rows

    town = close_plan(_plan())
    plant_structure(chat, town["structure"], town["rooms"])
    planned = {uid: entry["planned"] for uid, entry in registry_rows(chat).items()}
    assert planned["house_2"][SPLIT_OF] == "house"
    assert SPLIT_OF not in planned["house"]


def test_a_namespaced_town_keeps_its_marks_pointing_home(chat):
    """A second town planted beside rooms the story already has is re-keyed,
    and a mark naming the room a sibling came from is re-keyed with it."""
    from world.charter_runtime import _remap_generated_town, registry_for
    from world.structure import plant_structure

    plant_structure(chat, {"key": "row", "name": "Old Row"}, {
        "house": {"name": "the Old House", "purpose": "a ruin",
                  "adjacent": []}})
    plan = _plan()
    plan["rooms"]["lane"]["over"] = ["yard"]       # a room reference too
    town = close_plan(plan)
    remapped = _remap_generated_town(chat, town, registry_for(chat, None))
    marks = {uid: room[SPLIT_OF] for uid, room in remapped["rooms"].items()
             if SPLIT_OF in room}
    assert len(marks) == 2
    parent = set(marks.values()).pop()
    assert parent != "house" and parent in remapped["rooms"]
    assert remapped["rooms"][parent]["name"] == "the House"
    lane = next(room for room in remapped["rooms"].values()
                if room["name"] == "the Lane")
    (under,) = lane["over"]
    assert under != "yard" and remapped["rooms"][under]["name"] == "the Yard"


def test_a_measurement_the_world_cannot_read_is_no_measurement_and_no_failure():
    """Review L3: the closure reads every drafted room through the package
    path's normalizer since 2026-10-08, and that normalizer iterated `over`
    -- "chapel" became six one-letter rooms and `over: true` raised, which
    failed the Room's review and a one-shot launch."""
    from story.plot_packages import _plan_geometry
    from world.structure import GEOMETRY_FIELDS

    for field in GEOMETRY_FIELDS:
        for value in (True, 3, 2.5, "chapel", {}, {"w": "x"}, [None], [True]):
            plan = _plan()
            plan["rooms"]["lane"][field] = value
            close_plan(plan)                      # never raises
            _plan_geometry({field: value})
    plan = _plan()
    plan["rooms"]["lane"]["over"] = "yard"
    assert close_plan(plan)["rooms"]["lane"]["over"] == ["yard"]
    plan["rooms"]["lane"]["over"] = True
    assert "over" not in close_plan(plan)["rooms"]["lane"]
    plan["rooms"]["lane"]["floor"] = {"made": "planks"}
    assert "floor" not in close_plan(plan)["rooms"]["lane"]


def test_a_spent_identity_re_keys_every_room_reference_on_the_plan(chat):
    """Review L4: planting re-keys a room whose uid folds onto a ruin, and
    every reference to it -- edges, the frontier it was minted from, a split
    room's mark and the rooms that lie `over` it -- moves with it. `over`
    stayed on the ruin's spelling, so the storey inference dropped the pair
    as unknown."""
    from world.structure import plant_structure, registry_rows

    turn = db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                 "VALUES(?,?,?,?)", (chat, 0, "", time.time()))
    plant_structure(chat, {"key": "old", "name": "Old Row"}, {
        "house": {"name": "the Old House", "purpose": "a ruin",
                  "adjacent": []}})
    db.qi("UPDATE room_registry SET retired_turn_id=? WHERE chat_id=? "
          "AND room_uid=?", (turn, chat, "house"))
    plan = _plan()
    plan["rooms"]["loft"] = {"name": "the Loft", "purpose": "a store",
                             "exposure": "enclosed", "level": 1,
                             "over": ["house"],
                             "adjacent": [{"to": "house", "vertical": "down"}]}
    town = close_plan(plan)
    plant_structure(chat, town["structure"], town["rooms"])
    planned = {uid: entry["planned"] for uid, entry in registry_rows(chat).items()}
    home = next(uid for uid, spec in planned.items()
                if spec["name"] == "the House")
    assert home != "house"
    assert planned["loft"]["over"] == [home]
    marks = [spec[SPLIT_OF] for spec in planned.values() if SPLIT_OF in spec]
    assert marks and set(marks) == {home}
