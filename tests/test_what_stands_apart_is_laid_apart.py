"""A room the plan or the lore puts outside the building's walls is laid there.

Every shrine the engine laid (2026-10-15) had its latrine inside the house,
where the layout lab's shrine the owner liked has it as a small building
behind it -- though each Writers' Room plan had already said so: the latrine
joined to the washroom across an authored distance, `near`, that no other
join of the house carried. And the Seal Cavern, beyond the basement's far
wall in the lab's shrine, was laid inside the basement's own storey unless
the plan happened to give it a shape other than a rectangle. The names here
are illustrations: the rule reads the plan's typed distance and the first
call's one word, never a room's name.
"""
from __future__ import annotations

import copy

import pytest

from world import layout_bridge as lb

from tests.test_the_grounds_keep_their_doors import _add, _building, _court, _lay, _spec


def _apart_room(distance="near", every_join=False):
    """The court's side room joined, east, to a walled room the plan puts
    across `distance` -- on every join of the structure with `every_join`."""
    def mutate(specs, sort, relate):
        specs["side"][1]["adjacent"].append({"to": "latrine", "dir": "e", "barrier": "closed_door"})
        _add(specs, "latrine", "the Latrine", "a latrine across the yard",
             [dict({"to": "side", "dir": "w"}, **({"distance": distance} if distance else {}))],
             exposure="enclosed")
        if every_join:
            for _uid, (_name, spec) in specs.items():
                for edge in spec.get("adjacent") or ():
                    if not edge.get("vertical"):
                        edge["distance"] = distance
    return mutate


@pytest.mark.parametrize("distance", ["near", "12 m"])
def test_a_room_the_plan_puts_across_ground_is_a_building_apart(distance):
    """The plan joins the latrine to the side room across ground: it is no
    room of the house but a building apart, with a walk to the door it is
    reached from -- and nothing else of the house changes."""
    plan = _court(_apart_room(distance))
    b = _building(plan)
    assert "latrine" not in b["rooms"]
    assert "latrine" in {g["id"] for g in b["grounds"]}
    spec, layout, refused = _lay(plan)
    assert refused == []
    assert not spec.get("places_dropped"), spec.get("places_dropped")
    assert spec["ground_is"]["latrine"] == "outbuilding"
    assert next(x for x in spec["blocks"] if x["id"] == "latrine")["apart"] is True
    assert "latrine__way" in layout.ways


@pytest.mark.parametrize("distance", ["a fair way", "adjacent", None])
def test_a_distance_the_engine_does_not_read_as_ground_says_nothing(distance):
    """A word the engine cannot read, a distance that is a shared wall, or
    none at all: the room stays within the house."""
    b = _building(_court(_apart_room(distance)))
    assert "latrine" in b["rooms"]


def test_a_distance_every_join_carries_says_nothing():
    """A plan that writes `near` on every join says how it writes joins, not
    that one room stands apart: the house stays one house."""
    b = _building(_court(_apart_room("near", every_join=True)))
    assert "latrine" in b["rooms"] and "side" in b["rooms"]


def test_a_walled_place_left_unsaid_is_never_open_ground():
    """The first call says nothing of the latrine now standing apart: read
    as open ground it would be a band of the court; it is a building apart."""
    plan = _court(_apart_room("near"))
    b = _building(plan)
    held = lb.hold_grounds(b, [])
    assert {"id": "latrine", "name": "the Latrine", "is": "outbuilding"} in held


def _vault(distance=None, second_join=False):
    """A cellar under the hall, and a vault off its north wall."""
    def mutate(specs, sort, relate):
        specs["hall"][1]["adjacent"].append({"to": "cellar", "vertical": "down", "way": "stair"})
        specs["cellar"] = ("the Cellar", {
            "purpose": "a cellar", "structure": "court", "exposure": "enclosed",
            "adjacent": [{"to": "hall", "vertical": "up", "way": "stair"},
                         {"to": "vault", "dir": "n", "barrier": "closed_door"}]})
        edge = dict({"to": "cellar", "dir": "s"}, **({"distance": distance} if distance else {}))
        specs["vault"] = ("the Vault", {
            "purpose": "a vault cut into the rock", "structure": "court", "exposure": "enclosed",
            "level": -1,
            "adjacent": [edge] + ([{"to": "side_vault", "dir": "e"}] if second_join else [])})
        if second_join:
            specs["side_vault"] = ("the Side Vault", {
                "purpose": "a side vault", "structure": "court", "exposure": "enclosed", "level": -1,
                "adjacent": [{"to": "vault", "dir": "w"}]})
        sort["rooms"] += [{"id": "cellar", "fixtures": []}, {"id": "vault", "fixtures": []}]
        sort["stairs"].append({"from": "hall", "to": "cellar", "enclosed": False})
        relate["rooms"] += [{"id": "cellar", "purpose": "cellar", "fixtures": []},
                            {"id": "vault", "purpose": "other", "fixtures": []}]
        relate["stairs"].append({"from": "hall", "to": "cellar", "from_at": "w", "to_at": "w"})
    return mutate


def test_a_space_below_ground_the_plan_puts_apart_stands_beyond_its_wall():
    """Below the ground there is no yard to cross: a vault the plan puts
    apart from its cellar is entered through the cellar's wall and lies past
    it, in a block of its own -- as the lab's shrine has its cavern."""
    b = _building(_court(_vault("near")))
    assert "vault" in b["rooms"]
    assert b["own_blocks"]["vault"] == {"beside": "cellar", "side": "n"}


def test_a_room_the_first_call_says_stands_beyond_gets_a_block_of_its_own():
    """The plan gives no distance; the first call reads the lore and says the
    vault stands beyond the walls. Before the second call reads the building
    it has a block of its own past the cellar's wall, and the spec lays it
    there."""
    plan = _court(_vault())
    b = _building(plan)
    assert not (b.get("own_blocks") or {}).get("vault")
    inv = lb.hold_inventory(b, {"rooms": [{"id": "vault", "stands": "beyond", "fixtures": []}]})
    assert next(r for r in inv["rooms"] if r["id"] == "vault")["stands"] == "beyond"
    b2 = lb.stand_beyond(b, inv)
    assert b2["own_blocks"]["vault"] == {"beside": "cellar", "side": "n"}
    assert not (b.get("own_blocks") or {}).get("vault"), "the plan's building is not changed"
    spec = lb.spec_from_answers(b2, inv, copy.deepcopy(plan[4]))
    assert next(r for r in spec["rooms"] if r["id"] == "vault")["block"] == "vault"
    assert {"id": "vault", "apart": False, "beside": {"block": "main", "side": "n"}} in spec["blocks"]


def test_the_tier_stands_a_room_beyond_before_the_second_call_reads_it():
    """Through the tier's own path: the sort answer says the vault stands
    beyond, and the spec the solve lays has its block."""
    def mutate(specs, sort, relate):
        _vault()(specs, sort, relate)
        next(r for r in sort["rooms"] if r["id"] == "vault")["stands"] = "beyond"
    spec, layout, refused = _lay(_court(mutate))
    assert refused == []
    assert next(r for r in spec["rooms"] if r["id"] == "vault")["block"] == "vault"
    assert "vault" in layout.outlines


def test_a_room_joined_twice_keeps_its_place_within_the_walls():
    """A room joined to two rooms cannot stand past one wall: it keeps its
    place, and the building names it."""
    b = _building(_court(_vault(second_join=True)))
    inv = lb.hold_inventory(b, {"rooms": [{"id": "vault", "stands": "beyond", "fixtures": []}]})
    b2 = lb.stand_beyond(b, inv)
    assert not (b2.get("own_blocks") or {}).get("vault")
    assert b2["stands_within"] == ["vault"]


@pytest.mark.parametrize("word", ["within", "apart", "", "BEYOND "])
def test_only_the_engines_word_stands_a_room_beyond(word):
    """`beyond` is the engine's one word; anything else stands within (a
    stray case or spacing reads as the word)."""
    b = _building(_court(_vault()))
    inv = lb.hold_inventory(b, {"rooms": [{"id": "vault", "stands": word, "fixtures": []}]})
    held = next(r for r in inv["rooms"] if r["id"] == "vault")
    assert (held.get("stands") == "beyond") == (word.strip().casefold() == "beyond")


def _near_between_rooms(specs, sort, relate):
    """Every join of the court's walled rooms written `near` -- as one live
    plan of 2026-10-15 wrote every join between its rooms -- and the lane's
    way on down the hill `far`."""
    for _uid, (_name, spec) in specs.items():
        if str(spec.get("exposure") or "") == "enclosed":
            for edge in spec.get("adjacent") or ():
                if not edge.get("vertical"):
                    edge["distance"] = "near"
    specs["lane"][1]["adjacent"].append({"to": "road", "dir": "s", "distance": "far"})
    specs["road"] = ("the Road", {"purpose": "the road down", "structure": "court", "exposure": "open",
                                  "adjacent": [{"to": "lane", "dir": "n", "distance": "far"}]})


def test_a_distance_written_on_most_joins_between_rooms_is_the_plans_habit():
    """That plan, read as fact, took the kitchen, the store, two halls and
    both bedrooms out of its house, for the one `far` out of doors kept
    `near` from being its only word. How a plan writes the joins between
    its rooms is read over those joins, the outdoors aside, and a word on
    most of them says nothing of one room."""
    b = _building(_court(_near_between_rooms))
    assert {"hall", "side", "loft"} <= set(b["rooms"])
    assert not (b.get("own_blocks") or {})


def test_the_habit_counts_the_rooms_the_room_planned_and_not_a_solves_stairs():
    """A stair room an earlier solve made carries no distance of the Room's;
    counted, it would make `near` a minority of the joins."""
    planned = {
        "a": {"structure": "s", "exposure": "enclosed", "adjacent": [{"to": "b", "distance": "near"}]},
        "b": {"structure": "s", "exposure": "enclosed", "adjacent": [{"to": "c", "distance": "near"}]},
        "c": {"structure": "s", "exposure": "enclosed", "adjacent": []},
        "a__b_stair_0": {"structure": "s", "exposure": "enclosed", lb.LAYOUT_MADE_KEY: True,
                         "adjacent": [{"to": "a"}, {"to": "b"}, {"to": "c"}]},
        "yard": {"structure": "s", "exposure": "open", "adjacent": [{"to": "a"}, {"to": "b"}]},
    }
    assert lb._apart_habit(planned, "s") is True
    planned["c"]["adjacent"].append({"to": "a"})
    planned["a"]["adjacent"].append({"to": "c"})
    assert lb._apart_habit(planned, "s") is True, "two of three is still most"
    planned["c"]["adjacent"].append({"to": "d"})
    planned["d"] = {"structure": "s", "exposure": "enclosed", "adjacent": [{"to": "c"}]}
    assert lb._apart_habit(planned, "s") is False, "two of four is no habit"
