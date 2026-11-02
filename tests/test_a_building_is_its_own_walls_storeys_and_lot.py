"""Which planned rooms are one building, which storey each stands on, and
which door is its front -- read off the plan's own structure.

Four defects of `layout_bridge.plan_buildings`, each reproduced by the audit
of 2026-11-01 (world_layout_bridge_structure F2, F4, F5, F6, F11):

* an UNEXPANDED lot -- one room standing for a building nobody has entered --
  joined by a door to a planned building was laid out as one of its rooms,
  because the grouping read only `lot_of`, which a lot carries once expanded;
* a sheltered genkan between the house and its path was walled only where
  the path said `open` in so many words and the genkan was filed in the
  house's own part of the map -- 338 of 586 planned rooms in the owner's
  registry state no exposure, and chat 179's Room filed the grounds apart;
* a cellar reached by a stair down, its storey left to the stair (the plan
  specification: "a stair changes it, a door does not"), was refused as a
  storey of the house and its stair laid as a door in an outside wall;
* with no storey stated anywhere, the ground floor was seeded from the first
  outside way by id -- an outside ladder from the loft included -- and the
  house was laid upside down;
* the front door was ranked by English substrings of room names: "Marshall's
  Study" read as a hall, and a Japanese room name as nothing at all.

Hand-made plans; the names are illustrations, not the rule.
"""
from __future__ import annotations

import copy

from world.layout_bridge import plan_buildings


def _spec(name, **kw):
    kw.setdefault("structure", "town")
    return (name, kw)


def _buildings(specs):
    return [b for b in plan_buildings(specs, {"rooms": {}})]


def test_an_unexpanded_lot_is_never_a_room_of_the_building_next_door():
    specs = {
        "taproom": _spec("Taproom", exposure="enclosed", level=0,
                         adjacent=[{"to": "street", "barrier": "closed_door", "dir": "s"},
                                   {"to": "stable", "barrier": "closed_door", "dir": "e"},
                                   {"to": "guest_rooms", "vertical": "up"}]),
        "guest_rooms": _spec("Guest Rooms", exposure="enclosed", level=1),
        "stable": _spec("Stable", exposure="enclosed", level=0, lot={"storeys": 2},
                        extent={"w": 8, "d": 10},
                        adjacent=[{"to": "street", "barrier": "closed_door", "dir": "s"}]),
        "street": _spec("Street", exposure="open"),
    }
    [inn] = _buildings(specs)
    assert inn["rooms"] == ["guest_rooms", "taproom"]
    assert {o["to"] for o in inn["outside"]} == {"stable", "street"}


def _shrine(genkan_structure="shrine_house", path_exposure="open"):
    specs = {
        "genkan": _spec("Genkan", structure=genkan_structure, exposure="sheltered", level=0,
                        adjacent=[{"to": "lantern_path", "barrier": "closed_door", "dir": "s"},
                                  {"to": "main_hall", "barrier": "open_door", "dir": "n"}]),
        "lantern_path": _spec("Lantern Path", structure="shrine_grounds", exposure=path_exposure),
        "main_hall": _spec("Main Hall", structure="shrine_house", exposure="enclosed", level=0,
                           adjacent=[{"to": "kitchen", "barrier": "open_door", "dir": "e"},
                                     {"to": "upper", "vertical": "up"}]),
        "kitchen": _spec("Kitchen", structure="shrine_house", exposure="enclosed", level=0,
                         adjacent=[{"to": "well", "barrier": "closed_door", "dir": "e"}]),
        "well": _spec("Well", structure="shrine_grounds", exposure="open"),
        "upper": _spec("Upper Room", structure="shrine_house", exposure="enclosed", level=1),
    }
    if path_exposure is None:
        specs["lantern_path"][1].pop("exposure")
    return specs


def test_a_genkan_behind_the_front_door_is_within_the_walls_as_stated():
    [house] = _buildings(_shrine())
    assert "genkan" in house["rooms"]
    assert (house["entrance"]["room"], house["entrance"]["to"]) == ("genkan", "lantern_path")


def test_a_path_that_states_no_exposure_is_still_the_ground_outside_the_door():
    [house] = _buildings(_shrine(path_exposure=None))
    assert "genkan" in house["rooms"]
    assert (house["entrance"]["room"], house["entrance"]["to"]) == ("genkan", "lantern_path")


def test_a_genkan_filed_with_the_grounds_is_still_the_house_s():
    [house] = _buildings(_shrine(genkan_structure="shrine_grounds"))
    assert "genkan" in house["rooms"]
    assert (house["entrance"]["room"], house["entrance"]["to"]) == ("genkan", "lantern_path")
    assert house["structure"] == "shrine_house"


def test_a_porch_with_no_door_stays_the_ground_the_house_opens_onto():
    specs = _shrine()
    for edge in specs["genkan"][1]["adjacent"]:
        if edge["to"] == "lantern_path":
            edge["barrier"] = "open"
    [house] = _buildings(specs)
    assert "genkan" not in house["rooms"]


def _cellar(level):
    cellar = {"structure": "under_shrine", "exposure": "enclosed"}
    if level is not None:
        cellar["level"] = level
    return {
        "hall": _spec("Main Hall", structure="house", exposure="enclosed", level=0,
                      adjacent=[{"to": "path", "barrier": "closed_door", "dir": "s"},
                                {"to": "upper", "vertical": "up"},
                                {"to": "cellar", "vertical": "down"}]),
        "upper": _spec("Upper Room", structure="house", exposure="enclosed", level=1),
        "cellar": _spec("Cellar", **cellar),
        "path": _spec("Path", structure="grounds", exposure="open"),
    }


def test_a_cellar_whose_storey_is_left_to_its_stair_is_the_house_s():
    for level in (-1, None):
        [house] = _buildings(_cellar(level))
        assert house["rooms"] == ["cellar", "hall", "upper"], level
        assert [(o["room"], o["to"]) for o in house["outside"]] == [("hall", "path")], level
        assert house["levels"]["cellar"] == -1


def test_a_cellar_other_cellars_open_into_is_no_storey_of_the_house():
    """The registered limit holds: a stair down into a place that also joins a
    walled room of somebody else's -- a catacomb a dozen cellars open into --
    is not this house's cellar, its storey stated or left to the stair."""
    for level in (-1, None):
        specs = _cellar(level)
        specs["cellar"][1]["adjacent"] = [{"to": "next_cellar", "barrier": "closed_door"}]
        specs["next_cellar"] = _spec("Next Cellar", structure="next_house", exposure="enclosed",
                                     level=-1, adjacent=[{"to": "next_hall", "vertical": "up"}])
        specs["next_hall"] = _spec("Next Hall", structure="next_house", exposure="enclosed",
                                   level=0, adjacent=[{"to": "path", "barrier": "closed_door"}])
        house = next(b for b in _buildings(specs) if "hall" in b["rooms"])
        assert "cellar" not in house["rooms"], level


def test_with_no_storey_stated_the_ground_is_where_the_front_door_is():
    specs = {
        "a_loft": _spec("Hay Loft", structure="house", exposure="enclosed",
                        adjacent=[{"to": "yard", "vertical": "down", "way": "ladder"},
                                  {"to": "hall", "vertical": "down"}]),
        "hall": _spec("Hall", structure="house", exposure="enclosed",
                      adjacent=[{"to": "yard", "barrier": "closed_door", "dir": "s"},
                                {"to": "kitchen", "barrier": "open_door"}]),
        "kitchen": _spec("Kitchen", structure="house", exposure="enclosed"),
        "yard": _spec("Yard", structure="house", exposure="open"),
    }
    [house] = _buildings(specs)
    assert house["levels"] == {"a_loft": 1, "hall": 0, "kitchen": 0}
    assert house["refusal"] is None


def test_only_an_outside_ladder_puts_the_room_it_leaves_above_the_ground():
    specs = {
        "loft": _spec("Loft", structure="house", exposure="enclosed",
                      adjacent=[{"to": "yard", "vertical": "down", "way": "ladder"},
                                {"to": "store", "vertical": "down"}]),
        "store": _spec("Store", structure="house", exposure="enclosed"),
        "yard": _spec("Yard", structure="house", exposure="open"),
    }
    [barn] = _buildings(specs)
    assert barn["levels"] == {"loft": 1, "store": 0}


# ---------------------------------------------------------------- the front door

def _house(**names):
    """A parlour with the front door onto the street, a study off it with a
    door onto the garden, and a stair up from the parlour."""
    return {
        "parlour": _spec(names.get("parlour", "Front Parlour"), structure="house",
                         exposure="enclosed", level=0,
                         adjacent=[{"to": "street", "barrier": "closed_door", "dir": "s"},
                                   {"to": "study", "barrier": "open_door", "dir": "n"},
                                   {"to": "kitchen", "barrier": "open_door", "dir": "e"},
                                   {"to": "bedroom", "vertical": "up"}]),
        "study": _spec(names.get("study", "Marshall's Study"), structure="house",
                       exposure="enclosed", level=0,
                       adjacent=[{"to": "garden", "barrier": "closed_door", "dir": "n"}]),
        "kitchen": _spec("Kitchen", structure="house", exposure="enclosed", level=0),
        "bedroom": _spec("Bedroom", structure="house", exposure="enclosed", level=1),
        "street": _spec("Street", structure="house", exposure="open"),
        "garden": _spec("Garden", structure="house", exposure="open"),
    }


def test_a_name_that_only_contains_a_purpose_word_is_not_that_room():
    """"Marshall's Study" and "Whitehall Office" are no halls: the engine's
    words are read whole, never inside another word."""
    for study in ("Marshall's Study", "Whitehall Office"):
        [house] = _buildings(_house(study=study))
        assert house["entrance"]["room"] == "parlour", study
        assert house["plan"] == "layout:parlour"


def test_a_lot_s_own_entry_is_its_front_door():
    specs = _house(study="Back Hall")
    for uid, (_name, spec) in specs.items():
        if uid not in ("street", "garden"):
            spec["lot_of"] = "parlour"
    specs["parlour"][1]["lot"] = {"expanded": 3}
    [house] = _buildings(specs)
    assert house["entrance"]["room"] == "parlour"


def test_the_pack_s_words_name_an_entry_in_any_script(monkeypatch):
    """No English word in a Japanese house's names, so the rank fell to the
    first room by id: the pack says which of its words name an entry or a
    hall (`_entry_words`, read whole), and without a table nothing is read."""
    from world import layout_bridge
    specs = _house(parlour="玄関", study="大広間")
    specs = {("a_" + uid if uid == "study" else uid): entry for uid, entry in specs.items()}
    specs["parlour"][1]["adjacent"][1]["to"] = "a_study"
    monkeypatch.setattr(layout_bridge, "_entry_words",
                        lambda: {"entryway": ("玄関", "entrance"), "hall": ("広間",)})
    [house] = _buildings(copy.deepcopy(specs))
    assert house["entrance"]["room"] == "parlour"
    english = _house(parlour="Entrance", study="Great Hall")
    [house] = _buildings(english)
    assert house["entrance"]["room"] == "parlour"
