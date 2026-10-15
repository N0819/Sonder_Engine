"""The layout tier's calls answer from the building, never from the card.

Its answer templates held example values, and the model copied them
(2026-10-15, the engine's three live shrines against the layout lab's): the
relate card's `"storeys": [{"level": 1, "smaller": true}]` became two of
three answers' full second floor 'under the roof', which moved the stairs
and the corridor; `"count": 1` left no fixture or window of 249 with more
than one; `"order": 1` stood on 30 of 33 joins. A template says when to give
a field and what may go in it. And what the answers do say reaches the
spec: an order from the room whose wall it counts, a window's count from
the call that quoted the words for it, the lore of the ground the building
stands in, and doorways laid in the order asked.
"""
from __future__ import annotations

import copy
import re

import pytest

from world import layout_bridge as lb
from world.layout_solver import SEED, solve

from tests.test_the_grounds_keep_their_doors import _add, _court, _spec

CARDS = ("layout_sort", "layout_relate")


@pytest.mark.parametrize("lang", ["en", "ja"])
@pytest.mark.parametrize("card", CARDS)
def test_no_template_carries_a_value_to_copy(lang, card):
    from pathlib import Path
    text = Path(f"language_packs/{lang}/cards/system_prompts/prose_contract/{card}.txt").read_text()
    for field in ("level", "count", "order"):
        assert not re.search(rf'"{field}": \d', text), (card, lang, field)
    for field in ("enclosed", "implied", "smaller"):
        assert not re.search(rf'"{field}": false', text), (card, lang, field)
    assert not re.search(r'"smaller": true\}\]', text) or '"level": <' in text


@pytest.mark.parametrize("lang", ["en", "ja"])
def test_the_sort_asks_where_a_room_stands_in_both_languages(lang):
    from llm.prompts import layout_prompt
    card = layout_prompt("sort", lang)
    assert '"stands": "beyond' in card and "`stands`" in card


def _two_rooms_east(specs, sort, relate):
    """The hall's east wall opens to an annex and a bath, the relate ordering
    them from the north; both ids sort before the hall's."""
    specs.pop("side")
    specs["hall"][1]["adjacent"] = [e for e in specs["hall"][1]["adjacent"] if e["to"] != "side"]
    specs["hall"][1]["adjacent"] += [{"to": "annex", "dir": "e", "barrier": "closed_door"},
                                     {"to": "bath", "dir": "e", "barrier": "closed_door"}]
    _add(specs, "annex", "the Annex", "a sleeping room", [{"to": "hall", "dir": "w"}], exposure="enclosed")
    _add(specs, "bath", "the Bath", "a bath room", [{"to": "hall", "dir": "w"}], exposure="enclosed")
    sort["rooms"] = [r for r in sort["rooms"] if r["id"] != "side"] + \
        [{"id": "annex", "fixtures": [{"id": "bed", "name": "a bed", "mount": "floor"}]},
         {"id": "bath", "fixtures": [{"id": "tub", "name": "a tub", "mount": "floor"}]}]
    relate["rooms"] = [r for r in relate["rooms"] if r["id"] != "side"] + \
        [{"id": "annex", "purpose": "bedroom", "fixtures": [{"id": "bed", "kind": "bed"}]},
         {"id": "bath", "purpose": "washroom", "fixtures": [{"id": "tub", "kind": "tub"}]}]
    hall = next(r for r in relate["rooms"] if r["id"] == "hall")
    # the bath first from the north: against the order the solver lays them
    # in by itself, so only the asked order can put it there
    hall["joins"] = [{"to": "bath", "side": "e", "order": 1}, {"to": "annex", "side": "e", "order": 2}]


def test_a_join_order_is_written_from_the_room_whose_wall_it_counts():
    """The hall orders its two east doorways; written from the annex and the
    bath, whose ids sort first, the order was dropped."""
    _b, spec = _spec(_court(_two_rooms_east))
    hall = next(r for r in spec["rooms"] if r["id"] == "hall")
    got = {j["to"]: (j.get("side"), j.get("order")) for j in hall["joins"]}
    assert got["bath"] == ("e", 1) and got["annex"] == ("e", 2)
    for rid in ("annex", "bath"):
        room = next(r for r in spec["rooms"] if r["id"] == rid)
        assert all(j["to"] != "hall" for j in room["joins"]), rid


def test_the_solver_lays_doorways_in_the_order_asked():
    """On every seed the tier tries where both doorways stand in the hall's
    east wall, the bath's -- asked first -- is nearer its north end."""
    _b, spec = _spec(_court(_two_rooms_east))
    seen = 0
    for k in range(4):
        layout = solve(copy.deepcopy(spec), seed=SEED + k)
        doors = {d["b"] if d["a"] == "hall" else d["a"]: d for d in layout.doors
                 if "hall" in (d["a"], d["b"]) and {d["a"], d["b"]} & {"annex", "bath"}}
        if len(doors) < 2:
            continue
        hall_rect = layout.floors[0]["hall"][0]
        east = hall_rect.x + hall_rect.w - 1

        def row(d):
            return d["cell"][1] if d["a"] == "hall" else d["cell"][1]
        sides = {rid: (d["side"] if d["a"] == "hall" else {"w": "e", "e": "w", "n": "s", "s": "n"}[d["side"]])
                 for rid, d in doors.items()}
        if sides["annex"] == sides["bath"] == "e":
            seen += 1
            assert row(doors["bath"]) < row(doors["annex"]), (k, doors, east)
    assert seen, "no seed laid both doorways in the east wall"


def test_a_windows_count_is_the_first_calls():
    """The first call quoted three windows; the relate's template said one
    for every window of every shrine, and that was the one laid."""
    def mutate(specs, sort, relate):
        hall = next(r for r in sort["rooms"] if r["id"] == "hall")
        hall["windows"] = [{"id": "hall_windows", "name": "a window", "faces": "the court", "count": 3,
                            "why": "three tall windows look onto the court"}]
        rhall = next(r for r in relate["rooms"] if r["id"] == "hall")
        rhall["windows"] = [{"id": "hall_windows", "side": "s", "count": 1}]
    _b, spec = _spec(_court(mutate))
    hall = next(r for r in spec["rooms"] if r["id"] == "hall")
    assert next(w for w in hall["windows"] if w["id"] == "hall_windows")["count"] == 3


def test_the_lore_of_the_ground_reaches_the_layout_calls(temp_db):
    """The tier lays out the court and the lane with the hall; an entry the
    lore keys to the lane reached none of its calls."""
    from agents.director_layout import building_description
    from tests.test_a_planned_building_is_laid_out_by_relations import _book, _chat
    from tests.test_the_grounds_hold_together import COURT_SPECS, SCENE
    cid = _chat(temp_db)
    _book(temp_db, cid, [
        ("the lane", "Two stone lanterns stand where the lane leaves the court."),
        ("the far realm", "Past the gate lies another world."),
    ])
    found = lb.plan_buildings(copy.deepcopy(COURT_SPECS), copy.deepcopy(SCENE), grounds=True)
    building = max(found, key=lambda x: len(x["rooms"]))
    text = building_description(cid, building)
    assert "stone lanterns" in text
    assert "another world" not in text


#: What six live answers dropped though the lore said it (2026-10-15), and
#: the words each card now says it with: the sort counted "windows line the
#: west wall" as one in every run; the relate left a wall's doors unordered
#: where the lore ordered them, tied a desk "beneath the window" to its wall
#: alone, and read "behind the west end" as the west side.
CLAUSES = {
    ("sort", "en"): "A plural the words give with no number is still several",
    ("sort", "ja"): "言葉が数を言わずに複数で述べているものも複数です",
    ("relate", "en"): ("in the order the description or the brief gives",
                       "names it there as well as giving its wall",
                       "what stands behind the building is off its back"),
    ("relate", "ja"): ("description か brief が順を述べていれば、その順で",
                       "そこでもそれを名指します",
                       "建物の裏に立つものは"),
}


@pytest.mark.parametrize("card,lang", sorted(CLAUSES))
def test_the_cards_say_what_the_live_answers_dropped(card, lang):
    from llm.prompts import layout_prompt
    text = layout_prompt(card, lang)
    wanted = CLAUSES[(card, lang)]
    for words in (wanted if isinstance(wanted, tuple) else (wanted,)):
        assert words in text, (card, lang, words)
