"""A part taken from a whole is its own thing, and a standing thing is never
rewritten into a different one.

Measured on the owner's chat 175 turn 9 (2026-10-19). The encoder did it
right: under its item "pastry_board" it minted `broken_pastry` ("half a warm
pastry") and transferred THAT to Mellisande. `bind_items` admitted the
transfer's object_id as a candidate for the item; nothing standing answered
to `broken_pastry`, so the binder fell back to the record the item names --
the board -- and aliased the new pastry onto it. The board was renamed "half a
warm pastry", re-kinded food, put into her hand, and stopped existing as a
board (checkpoint 10).

The entities channel already refused a named mint the item's name does not
vouch for; an op's object_id now obeys the same rule.
"""

from __future__ import annotations

import copy

import agents.director as director
from llm import decisions
from world.causal_program import bind_items
from world.spatial import merge_scene_with_diff

from tests.director_fakes import BASE_SCENE, _action_interp, _fake_agent, _make_ctx


BOARD = {"name": "board of pastries", "kind": "object",
         "description": "A wooden board holding small round buns and two jam tarts.",
         "aliases": ["board", "pastries", "board of pastries"],
         "portable": True, "container": True}
HALF = {"name": "half a warm pastry", "kind": "food",
        "description": "Half of a freshly baked pastry, still faintly warm.",
        "portable": True, "state": {"broken": True}}


def _rows():
    """Chat 175 turn 9's two object transforms, as bound."""
    return [
        {"item_id": 3, "chrono_id": 3, "object_name": "pastry_board",
         "patch": {"entities": {"broken_pastry": dict(HALF)}}},
        {"item_id": 3, "chrono_id": 3, "object_name": "pastry_board",
         "patch": {"inventory_ops": [{"op": "transfer", "object_id": "broken_pastry",
                                      "from_id": "pastry_board", "to_id": "Mellisande",
                                      "relation": "held"}]}},
    ]


def _world():
    return {"entities": {"pastry_board": dict(BOARD)},
            "positions": {"pastry_board": "lane_end", "Mellisande": "lane_end"}}


def test_the_half_pastry_is_not_aliased_onto_the_board():
    bound, bindings, _notes = bind_items(_rows(), _world())
    assert (bindings.get("3") or {}).get("entity") != "pastry_board"
    minted = bound[0]["patch"]["entities"]
    assert set(minted) == {"broken_pastry"}
    assert bound[1]["patch"]["inventory_ops"][0]["object_id"] == "broken_pastry"
    # The binder's actual job is untouched: an op naming the item's thing by
    # a key nothing mints and nothing holds is that thing.
    slipped = [{"item_id": 3, "chrono_id": 1, "object_name": "pastry_board",
                "patch": {"inventory_ops": [{"op": "transfer", "object_id": "pastry_bord",
                                             "from_id": "Mellisande", "to_id": "lane_end",
                                             "relation": "surface"}]}}]
    bound, bindings, _notes = bind_items(slipped, _world())
    assert bindings["3"]["entity"] == "pastry_board"
    assert bound[0]["patch"]["inventory_ops"][0]["object_id"] == "pastry_board"


def test_the_board_stands_and_the_half_is_in_her_hand(temp_db, monkeypatch):
    """End to end: the turn-9 encoder events through the resolve and merge."""
    temp_db.set_setting("prose_contract_repair", "0")
    monkeypatch.setattr(decisions, "OVERRIDE", lambda state, questions: {
        key: {"type": "noul", "noul": 0.95 if key in ("entities", "inventory_ops",
                                                      "entities__new") else 0.02}
        for key in questions})
    scene = copy.deepcopy(BASE_SCENE)
    scene["entities"] = {"pastry_board": dict(BOARD)}
    scene["positions"]["pastry_board"] = "keeper_room"
    encoder = {"events": [{
        "source_entity_id": "character:1", "source_event_id": "x",
        "event": "Mara breaks a pastry in half over the table and holds one piece out.",
        "observable": "breaks a pastry in half and holds one piece out",
        "speech": False, "targets": ["pastry_board"], "seconds": 3, "movement": None,
        "commitment": "asserted", "item_names": ["Mara", "pastry_board"],
        "transforms": [
            {"item": "pastry_board", "patch": {"entities": {"broken_pastry": dict(HALF)}}},
            {"item": "pastry_board", "patch": {"inventory_ops": [{
                "op": "transfer", "object_id": "broken_pastry",
                "from_id": "pastry_board", "to_id": "Mara", "relation": "held"}]}}]}],
        "missing_tools": [], "missing_referents": [], "notes": []}
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": {"prose": "Mara breaks a pastry in half over the table."},
        "director_specialist": encoder,
    }))
    ctx = _make_ctx(temp_db, scene=scene, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)
    entities = out["state_diff"]["entities"]
    assert "broken_pastry" in entities
    assert (entities.get("pastry_board") or {}).get("name") in (None, BOARD["name"])
    after = merge_scene_with_diff(copy.deepcopy(scene), out["state_diff"])
    assert after["entities"]["pastry_board"]["name"] == "board of pastries"
    assert after["entities"]["broken_pastry"]["name"] == "half a warm pastry"


def test_the_card_mints_one_record_per_thing():
    """Chat 176/177's plate-and-scone, one entity aliased both ways, so a
    reach for the scone moved the plate; chat 175's "two earthenware cups",
    one entity. Shipped with the part a mint is written under -- granted at
    every measured minting beat (175 t2, 175 t9, 176 t1)."""
    from llm.prompts import unified_specialist_prompt
    en = unified_specialist_prompt(["entities"], "en", ["entities__new"])
    ja = unified_specialist_prompt(["entities"], "ja", ["entities__new"])
    assert "ONE THING, ONE RECORD" in en
    assert "a thing resting on or in another is a record of its own" in en
    assert "a part taken from a whole is a new record" in en
    assert "never rewritten into a different thing" in en
    assert "一つの物に一つの記録" in ja and "新しい key" in ja
