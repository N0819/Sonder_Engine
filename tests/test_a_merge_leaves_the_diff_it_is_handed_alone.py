"""A scene merge never writes into the diff it is handed, and the opening reads
the ground the launch laid.

`merge_scene_with_diff` deep-copies the scene it starts from -- "scene merges
are correctness boundaries" -- but stood a room or a thing that was NEW to the
merge into the result by reference. Every repair the merge then made to that
record (the orphan pass's exit, a name, a normalized barrier) was made to the
caller's diff as well, so a merge run only to LOOK at a beat wrote its answer
into the beat.

Live, chat 167 turn 4616 (the validation story, 2026-10-10): the opening's
placement floor previewed its diff on an EMPTY scene ("the opening has no scene
before it", written before a launch laid the plan's rooms ahead of the first
beat). Every planned room the Director listed as a stub was new to that
preview and, judged on the diff alone, an island; the orphan pass gave each an
exit to the first room in the diff -- the inn -- and the exits landed in the
diff through the shared lists. The commit merged that diff onto the launched
town, and the inn's common room opened onto sixteen places, three of them
galleries four hundred feet underground.
"""

from __future__ import annotations

import copy
import json
import time

from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import default_persona_data
from world.spatial import merge_scene_with_diff


def _edges_to(rooms, target):
    return sorted(rid for rid, room in rooms.items()
                  if any(isinstance(edge, dict) and edge.get("to") == target
                         for edge in (room.get("adjacent") or [])))


def test_a_merge_never_writes_into_the_diff_it_is_handed():
    """The merge's own result may repair an island; the diff stays what the
    beat wrote."""
    base = {"rooms": {"street": {"name": "Street", "adjacent": []}},
            "positions": {"Nia": "street"}, "entities": {}}
    diff = {"rooms": {"plaza": {"name": "Plaza", "adjacent": []}},
            "entities": {"lamp": {"name": "a lamp", "state": {"lit": True}}},
            "positions": {"lamp": "plaza"}}
    written = copy.deepcopy(diff)
    merged = merge_scene_with_diff(base, diff)
    assert _edges_to(merged["rooms"], "street") == ["plaza"], (
        "the merge still connects the island it was given")
    assert diff == written, "the merge wrote into the diff it was handed"


def test_the_opening_adds_no_exit_the_launched_ground_did_not_need(temp_db, monkeypatch):
    """The plan's rooms the opening only lists stay as the launch connected
    them: a stub is not an island when the ground it stands on reaches it."""
    import agents.director as director
    from core.db import wset

    persona = default_persona_data("Nia")
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source,resource_uid) VALUES(?,?,?,?)",
        ("Nia", json.dumps(persona), "{}", persona["identity"]["uid"]))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,persona_id,scenario,created) VALUES(?,?,?,?)",
        ("Valley", persona_id, "", time.time()))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 0, "", time.time()))
    edge = lambda to: {"to": to, "barrier": "open", "distance": "near"}  # noqa: E731
    # THE GROUND THE LAUNCH LAID: an inn on a street, a chapel and a pit
    # head off it, the pit bottom below the pit head.
    wset(chat_id, "scene", {
        "rooms": {"inn": {"name": "the Inn", "adjacent": [edge("street")]},
                  "street": {"name": "the Street",
                             "adjacent": [edge("inn"), edge("chapel"), edge("pithead")]},
                  "chapel": {"name": "the Chapel", "adjacent": [edge("street")]},
                  "pithead": {"name": "the Pit Head",
                              "adjacent": [edge("street"), edge("pit_bottom")]},
                  "pit_bottom": {"name": "the Pit Bottom", "adjacent": [edge("pithead")]}},
        "entities": {}, "positions": {}})
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Valley", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=0, player_input="",
                      created=time.time()),
        cast=[], input="")

    def fake_agent_json(role, step_key, system, payload, **kwargs):
        # The opening furnishes the room it stands in and lists the rest as
        # stubs, their exits left to the plan -- as its card allows.
        return {"location": "the valley",
                "rooms": {"inn": {"name": "the Inn", "adjacent": [edge("street")]},
                          "street": {"name": "the Street", "adjacent": []},
                          "chapel": {"name": "the Chapel", "adjacent": []},
                          "pithead": {"name": "the Pit Head", "adjacent": []},
                          "pit_bottom": {"name": "the Pit Bottom", "adjacent": []}},
                "entities": {"bag": {"name": "a satchel"}},
                "positions": {"Nia": "inn", "bag": "inn"},
                "attire": {}}

    monkeypatch.setattr(director, "_agent_json", fake_agent_json)
    monkeypatch.setattr(director, "validate_llm_output", lambda step, value: (value, []))
    result = director.director_establish(ctx, nonce=0)
    assert _edges_to(result["rooms"], "inn") == [], (
        "the opening gave a planned room an exit to the inn it never had")
    assert _edges_to(result["state_diff"]["rooms"], "inn") == []
    # What the commit will merge: the launched street still reaches the chapel
    # and the pit head, and the pit bottom is still below the pit head only.
    merged = merge_scene_with_diff(director.get_scene(chat_id), result["state_diff"])
    assert _edges_to(merged["rooms"], "inn") == ["street"]
    assert [e["to"] for e in merged["rooms"]["pit_bottom"]["adjacent"]] == ["pithead"]


def test_the_opening_never_moves_what_the_launch_placed(temp_db, monkeypatch):
    """A thing the launch stood in a room is not a mint with no room because
    the opening writes its state without its place."""
    import agents.director as director
    from core.db import wset

    persona = default_persona_data("Nia")
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source,resource_uid) VALUES(?,?,?,?)",
        ("Nia", json.dumps(persona), "{}", persona["identity"]["uid"]))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,persona_id,scenario,created) VALUES(?,?,?,?)",
        ("Valley", persona_id, "", time.time()))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 0, "", time.time()))
    edge = lambda to: {"to": to, "barrier": "open", "distance": "near"}  # noqa: E731
    wset(chat_id, "scene", {
        "rooms": {"inn": {"name": "the Inn", "adjacent": [edge("chapel")]},
                  "chapel": {"name": "the Chapel", "adjacent": [edge("inn")]}},
        "entities": {"bell": {"name": "the tide bell"}},
        "positions": {"bell": "chapel"}})
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Valley", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=0, player_input="",
                      created=time.time()),
        cast=[], input="")

    def fake_agent_json(role, step_key, system, payload, **kwargs):
        return {"location": "the valley",
                "rooms": {"inn": {"name": "the Inn", "adjacent": [edge("chapel")]}},
                "entities": {"bell": {"name": "the tide bell", "state": {"ringing": True}}},
                "positions": {"Nia": "inn"},
                "attire": {}}

    monkeypatch.setattr(director, "_agent_json", fake_agent_json)
    monkeypatch.setattr(director, "validate_llm_output", lambda step, value: (value, []))
    result = director.director_establish(ctx, nonce=0)
    assert "bell" not in result["state_diff"]["positions"], (
        "the opening stood the launch's bell in its own room")
