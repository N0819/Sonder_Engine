"""Lookups recall cannot replace (`agents/character_tools.py`, step 3, the
owner 2026-10-06): where a need can be met and the way there, over the
mind's own walked map; and what a note in its notebook rests on.
"""

from __future__ import annotations

import json
import time

import numpy as np
import pytest

from llm.providers import EmbeddingBatch
from story.character_schema import default_character_data
from tests.helpers import patch_provider_seam


def _graph():
    """Hall -- Corridor -- Kitchen walked; Corridor -> Garden only SEEN; a Cellar
    known by name with no way there; the Inn told of."""
    return {
        "nodes": {
            "hall": {"name": "Hall", "basis": "walked"},
            "corridor": {"name": "Corridor", "basis": "walked"},
            "kitchen": {"name": "Kitchen", "basis": "walked",
                        "affords": {"food": {"basis": "witnessed", "last": 4}}},
            "garden": {"name": "Garden", "basis": "seen",
                       "affords": {"food": {"basis": "witnessed", "last": 2}}},
            "cellar": {"name": "Cellar", "basis": "told",
                       "affords": {"drink": {"basis": "told", "sureness": 0.7}}},
            "inn_lane": {"name": "Old Inn", "basis": "walked"},
        },
        "edges": {
            "hall": {"corridor": {"taken": True, "basis": "walked"}},
            "corridor": {"kitchen": {"taken": True, "basis": "walked"},
                         "garden": {"basis": "seen"},
                         "inn_lane": {"taken": True, "basis": "walked"}},
        },
    }


def _lookups(**kw):
    from agents.character_tools import Lookups
    base = dict(chat_id=1, char_id=2, turn_idx=10, bank=None, handles={}, memory_context={},
                memory_internal={}, holding=None, notebook_inputs={}, ponder_inputs={},
                place_inputs={"graph": _graph(), "room": "hall"})
    base.update(kw)
    return Lookups(**base)


def test_where_can_i_names_only_places_with_a_walked_way(temp_db):
    look = _lookups()
    got = look.run("where_can_i", {"need": "food"})
    names = [p["place"] for p in got["places"]]
    assert "Kitchen" in names, "lived, two doorways over walked ground"
    assert "Garden" not in names, "seen, never walked to: a memory, not an option"
    kitchen = next(p for p in got["places"] if p["place"] == "Kitchen")
    assert kitchen["basis"] == "witnessed" and kitchen["doorways_away"] == 2
    inn = [p for p in got["places"] if p["place"] == "Old Inn"]
    assert inn and inn[0]["basis"] == "assumed", "a name it walked to says what it is for"
    assert look.run("where_can_i", {"need": "a pony"})["refused"]


def test_where_can_i_says_so_when_the_room_it_stands_in_answers(temp_db):
    look = _lookups(place_inputs={"graph": _graph(), "room": "kitchen"})
    assert look.run("where_can_i", {"need": "food"}).get("right_here") is True


def test_route_to_walks_only_its_own_walked_doorways(temp_db):
    look = _lookups()
    assert look.run("route_to", {"place": "kitchen"}) == {"route": ["Hall", "Corridor", "Kitchen"],
                                                          "doorways": 2}
    assert look.run("route_to", {"place": "Garden"}) == {"no_way_you_have_walked": True}
    assert look.run("route_to", {"place": "Cellar"}) == {"no_way_you_have_walked": True}
    assert look.run("route_to", {"place": "Hall"}) == {"you_are_there": True}
    assert look.run("route_to", {"place": "the moon"})["refused"]


def test_route_to_asks_which_when_a_name_is_ambiguous(temp_db):
    graph = _graph()
    graph["nodes"]["kitchen2"] = {"name": "Back Kitchen", "basis": "walked"}
    look = _lookups(place_inputs={"graph": graph, "room": "hall"})
    assert look.run("route_to", {"place": "kitchen"}) == {"route": ["Hall", "Corridor", "Kitchen"],
                                                          "doorways": 2}, "an exact name wins"
    assert sorted(look.run("route_to", {"place": "itch"})["which_one"]) == ["Back Kitchen", "Kitchen"]


DIM = 8


@pytest.fixture
def bank(temp_db, monkeypatch):
    patch_provider_seam(monkeypatch, "embed_texts_meta", lambda texts, **_kw: EmbeddingBatch(
        vectors=[np.ones(DIM, dtype=np.float32) / np.sqrt(DIM) for _ in texts],
        model_key="t", dimensions=DIM))
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)", ("T", "", time.time()))
    char_id = temp_db.qi("INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
                         ("Mara", json.dumps(default_character_data("Mara")), "{}", time.time()))
    from mind.memory import add_memories_batch
    add_memories_batch([{"chat_id": chat_id, "char_id": char_id, "turn_id": None, "turn_idx": 3,
                         "kind": "episodic", "category": "episode", "provenance": "witnessed",
                         "salience": 0.6, "content": "Oren slipped the key under the floorboard.",
                         "event_key": "event:key", "encoded_at_seconds": 180.0}])
    return chat_id, char_id


def test_why_do_i_think_hands_back_what_a_note_rests_on(temp_db, bank):
    from mind import theory_of_mind as tom
    chat_id, char_id = bank
    hyp = {"claim": "Oren is hiding the key", "confidence": 0.7, "kind": "goal",
           "evidence": [{"event_id": "event:key", "fact": "Oren slipped the key under the floorboard."},
                        {"event_id": "current:2:4", "fact": "Oren would not meet my eyes."}]}
    state = {"mind_models": {"Oren": {"hypotheses": [hyp]}},
             "notebook": [{"id": "r1", "note": "ask about the box"}]}
    look = _lookups(chat_id=chat_id, char_id=char_id, notebook_inputs={"state": state})
    got = look.run("why_do_i_think", {"note_id": tom.note_id("Oren", hyp)})
    assert got["note"] == "Oren is hiding the key" and got["about"] == "Oren"
    assert isinstance(got["sure"], str)
    by_fact = {b["fact"]: b for b in got["because"]}
    ref = by_fact["Oren slipped the key under the floorboard."]["memory_ref"]
    assert look.handles[ref] == "event:key", "a memory of its own, named so expand can open it"
    assert "memory_ref" not in by_fact["Oren would not meet my eyes."], "a moment it saw, not a memory row"
    assert look.run("why_do_i_think", {"note_id": "r1"}) == {"note": "ask about the box",
                                                             "nothing_written_beneath_it": True}
    assert look.run("why_do_i_think", {"note_id": "nope"})["refused"]


def test_another_minds_memory_is_never_handed_back_as_evidence(temp_db, bank):
    """An evidence id that is not this mind's own row is a fact, never a ref."""
    chat_id, char_id = bank
    hyp = {"claim": "x", "confidence": 0.5, "evidence": [{"event_id": "event:someone-elses", "fact": "f"}]}
    from mind import theory_of_mind as tom
    look = _lookups(chat_id=chat_id, char_id=char_id,
                    notebook_inputs={"state": {"mind_models": {"Oren": {"hypotheses": [hyp]}}}})
    got = look.run("why_do_i_think", {"note_id": tom.note_id("Oren", hyp)})
    assert got["because"] == [{"fact": "f"}]
