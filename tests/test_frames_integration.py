"""Integration tests for temporal frames across app.py endpoints,
character.py's existence-masking backstop, and turn_branch's safe
(present-only) handling of frame references -- as opposed to
tests/test_frames.py, which covers frames.py's own mechanics in
isolation.

Concurrency model (see frames.py's module docstring and db.py's
active_frame_id contextvar): there is no chat-wide "current frame"
anymore -- each pipeline run sets its own active frame from the turn
row it's processing, and extra players are "stationed" to a frame via
chat_personas.frame_id so two players can be genuinely eras apart.
"""

from __future__ import annotations

import json
import time

import pytest
from fastapi import HTTPException

import app
import memory
from character_schema import default_character_data


def _make_chat(db):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )


def _make_char(db, name):
    return db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        (name, json.dumps(default_character_data(name)), "{}", time.time()),
    )


def _make_persona(db, name):
    return db.qi(
        "INSERT INTO personas(name,sheet) VALUES(?,?)",
        (name, json.dumps({"identity": {"name": name}})),
    )


class TestFrameEndpoints:
    def test_frames_list_starts_with_only_present(self, temp_db):
        chat_id = _make_chat(temp_db)
        result = app.frames_list(chat_id)
        assert len(result["frames"]) == 1
        assert result["frames"][0]["id"] is None

    def test_frames_create_requires_a_label(self, temp_db):
        chat_id = _make_chat(temp_db)
        with pytest.raises(HTTPException) as exc_info:
            app.frames_create(chat_id, {"ordinal": 5})
        assert exc_info.value.status_code == 400

    def test_frames_create_rejects_present_kind(self, temp_db):
        chat_id = _make_chat(temp_db)
        with pytest.raises(HTTPException) as exc_info:
            app.frames_create(chat_id, {"label": "x", "ordinal": 1, "kind": "present"})
        assert exc_info.value.status_code == 400

    def test_frames_create_and_list(self, temp_db):
        chat_id = _make_chat(temp_db)
        created = app.frames_create(chat_id, {"label": "Far future", "ordinal": 10, "kind": "future"})
        assert created["label"] == "Far future"
        listed = app.frames_list(chat_id)
        assert len(listed["frames"]) == 2


class TestPersonaStationing:
    def test_stationing_an_unattached_persona_404s(self, temp_db):
        chat_id = _make_chat(temp_db)
        pid = _make_persona(temp_db, "Bob")
        with pytest.raises(HTTPException) as exc_info:
            app.chat_persona_station(chat_id, pid, {"frame_id": None})
        assert exc_info.value.status_code == 404

    def test_stationing_to_an_unknown_frame_404s(self, temp_db):
        chat_id = _make_chat(temp_db)
        pid = _make_persona(temp_db, "Bob")
        app.chat_add_persona(chat_id, {"persona_id": pid})
        with pytest.raises(HTTPException) as exc_info:
            app.chat_persona_station(chat_id, pid, {"frame_id": 999999})
        assert exc_info.value.status_code == 404

    def test_stationing_moves_the_persona(self, temp_db):
        chat_id = _make_chat(temp_db)
        pid = _make_persona(temp_db, "Bob")
        app.chat_add_persona(chat_id, {"persona_id": pid})
        future = app.frames_create(chat_id, {"label": "Future", "ordinal": 10, "kind": "future"})

        result = app.chat_persona_station(chat_id, pid, {"frame_id": future["id"]})
        assert result["frame_id"] == future["id"]

        listed = app.chat_list_extra_personas(chat_id)
        assert listed["personas"][0]["frame_id"] == future["id"]

    def test_stationing_blocked_while_chat_has_active_pipeline(self, temp_db):
        from agents.runtime import ABORTS

        chat_id = _make_chat(temp_db)
        pid = _make_persona(temp_db, "Bob")
        app.chat_add_persona(chat_id, {"persona_id": pid})
        ABORTS[(chat_id, None)] = object()
        try:
            with pytest.raises(HTTPException) as exc_info:
                app.chat_persona_station(chat_id, pid, {"frame_id": None})
            assert exc_info.value.status_code == 409
        finally:
            ABORTS.pop((chat_id, None), None)


class TestTurnFrameTagging:
    def test_new_turn_is_tagged_with_the_requested_frame(self, temp_db, monkeypatch):
        from agents.runtime import ABORTS

        chat_id = _make_chat(temp_db)
        future = app.frames_create(chat_id, {"label": "Future", "ordinal": 10, "kind": "future"})

        monkeypatch.setattr(app, "run_pipeline", lambda *a, **k: iter(()))
        try:
            app.turn_new(chat_id, {"input": "hello", "frame_id": future["id"]})
        finally:
            ABORTS.pop((chat_id, future["id"]), None)

        row = temp_db.q("SELECT frame_id FROM turns WHERE chat_id=?", (chat_id,), one=True)
        assert row["frame_id"] == future["id"]

    def test_new_turn_defaults_to_present(self, temp_db, monkeypatch):
        from agents.runtime import ABORTS

        chat_id = _make_chat(temp_db)
        monkeypatch.setattr(app, "run_pipeline", lambda *a, **k: iter(()))
        try:
            app.turn_new(chat_id, {"input": "hello"})
        finally:
            ABORTS.pop((chat_id, None), None)
        row = temp_db.q("SELECT frame_id FROM turns WHERE chat_id=?", (chat_id,), one=True)
        assert row["frame_id"] is None

    def test_two_frames_can_each_have_a_pipeline_running_at_once(self, temp_db, monkeypatch):
        """The actual point of Stage A: creating a turn in frame B while
        frame A's pipeline is still marked active must NOT be blocked --
        only a second overlapping attempt within the SAME frame is."""
        from agents.runtime import ABORTS

        chat_id = _make_chat(temp_db)
        future = app.frames_create(chat_id, {"label": "Future", "ordinal": 10, "kind": "future"})
        monkeypatch.setattr(app, "run_pipeline", lambda *a, **k: iter(()))

        ABORTS[(chat_id, None)] = object()  # present frame "busy"
        try:
            # Creating a turn in the FUTURE frame must succeed even though
            # the present frame has an active pipeline.
            app.turn_new(chat_id, {"input": "hello", "frame_id": future["id"]})
        finally:
            ABORTS.pop((chat_id, None), None)
            ABORTS.pop((chat_id, future["id"]), None)

        row = temp_db.q("SELECT frame_id FROM turns WHERE chat_id=? AND frame_id=?",
                        (chat_id, future["id"]), one=True)
        assert row is not None

    def test_same_frame_overlap_is_still_rejected(self, temp_db):
        from agents.runtime import ABORTS

        chat_id = _make_chat(temp_db)
        ABORTS[(chat_id, None)] = object()
        try:
            with pytest.raises(HTTPException) as exc_info:
                app.turn_new(chat_id, {"input": "hello"})
            assert exc_info.value.status_code == 409
        finally:
            ABORTS.pop((chat_id, None), None)


class TestExtraPlayersFoldOnlyIntoTheirOwnFrame:
    def test_load_extra_players_excludes_a_different_stationed_persona(self, temp_db):
        from agents.runtime import _load_extra_players

        chat_id = _make_chat(temp_db)
        here = _make_persona(temp_db, "Alice")
        there = _make_persona(temp_db, "Bob")
        app.chat_add_persona(chat_id, {"persona_id": here})
        app.chat_add_persona(chat_id, {"persona_id": there})
        future = app.frames_create(chat_id, {"label": "Future", "ordinal": 10, "kind": "future"})
        app.chat_persona_station(chat_id, there, {"frame_id": future["id"]})

        extras = _load_extra_players(chat_id, turn_idx=1, frame_id=None)
        assert [e["name"] for e in extras] == ["Alice"]

        extras_future = _load_extra_players(chat_id, turn_idx=1, frame_id=future["id"])
        assert [e["name"] for e in extras_future] == ["Bob"]


class TestBranchResetsFramesToPresent:
    def test_branching_a_chat_with_frame_tagged_memories_resets_to_present(self, temp_db):
        chat_id = _make_chat(temp_db)
        alice = _make_char(temp_db, "Alice")
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
            (chat_id, alice, "active", "{}"),
        )
        turn_id = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
            (chat_id, 0, "start", time.time()),
        )

        future = app.frames_create(chat_id, {"label": "Future", "ordinal": 10, "kind": "future"})
        memory.add_memory(chat_id, alice, None, "episode", "witnessed", 0.5,
                           "From the future frame.", turn_idx=0, frame_id=future["id"])

        branched = app.turn_branch(turn_id)
        ncid = branched["id"]

        # Frames are now cloned with a fresh id (not dropped/reset to
        # present) -- the memory must point at the BRANCH's own
        # corresponding frame row, which carries the same label/ordinal.
        mem_row = temp_db.q("SELECT frame_id FROM memories WHERE chat_id=?", (ncid,), one=True)
        assert mem_row is not None
        assert mem_row["frame_id"] is not None
        assert mem_row["frame_id"] != future["id"]  # a NEW row, not the source chat's

        cloned_frames = app.frames_list(ncid)["frames"]
        cloned_future = next(f for f in cloned_frames if f["id"] == mem_row["frame_id"])
        assert cloned_future["label"] == "Future"
        assert cloned_future["ordinal"] == 10

    def test_branching_clones_frame_scoped_world_state(self, temp_db):
        chat_id = _make_chat(temp_db)
        turn_id = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
            (chat_id, 0, "start", time.time()),
        )
        future = app.frames_create(chat_id, {"label": "Future", "ordinal": 10, "kind": "future"})

        from db import active_frame_id
        token = active_frame_id.set(future["id"])
        try:
            temp_db.wset(chat_id, "scene", {"location": "Alien planet"})
        finally:
            active_frame_id.reset(token)
        temp_db.wset(chat_id, "scene", {"location": "Earth"})  # present, unaffected

        branched = app.turn_branch(turn_id)
        ncid = branched["id"]
        cloned_future_id = app.frames_list(ncid)["frames"][1]["id"]

        assert temp_db.wget(ncid, "scene") == {"location": "Earth"}
        token = active_frame_id.set(cloned_future_id)
        try:
            assert temp_db.wget(ncid, "scene") == {"location": "Alien planet"}
        finally:
            active_frame_id.reset(token)


class TestExistenceMaskingBackstop:
    def test_character_step_strips_relationship_with_a_not_yet_existing_castmate(self, temp_db, monkeypatch):
        import agents.character as character_module
        from pipeline_context import ChatData, PipelineContext, TurnData

        chat_id = _make_chat(temp_db)
        tamamo = _make_char(temp_db, "Tamamo")
        hinami = _make_char(temp_db, "Hinami")
        for cid_ in (tamamo, hinami):
            temp_db.qi(
                "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
                (chat_id, cid_, "active", "{}"),
            )
        temp_db.wset(chat_id, "scene", {
            "location": "Shrine", "time": "day",
            "rooms": {"hall": {"name": "Hall", "adjacent": []}},
            "positions": {"Tamamo": "hall", "Hinami": "hall"},
            "entities": {}, "attire": {}, "overlays": {},
        })

        past = app.frames_create(chat_id, {
            "label": "Before Hinami existed", "ordinal": -10, "kind": "past",
            "travelers": [hinami], "nonexistent_cast": [hinami],
        })

        memory.save_relationships(
            chat_id, tamamo,
            memory.RelationshipGraph.from_dict({"Hinami": {"target_name": "Hinami", "trust": 0.9}}),
        )
        assert "Hinami" in memory.relationships_for_payload(chat_id, tamamo)

        cast = temp_db.q(
            "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
            "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
            (chat_id,),
        )
        turn_id = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) VALUES(?,?,?,?,?)",
            (chat_id, 1, "who are you?", time.time(), past["id"]),
        )
        ctx = PipelineContext(
            chat=ChatData(id=chat_id, name="Test", persona_id=None, lorebook_id=None,
                          scenario="", created=time.time()),
            turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                          player_input="who are you?", created=time.time(), frame_id=past["id"]),
            cast=cast, input="who are you?",
        )
        ctx.director_interpret = {"flow": {"reactors": [tamamo], "tom_triggers": []}}

        captured = {}

        def fake_agent_json(role, step_key, system, payload, **kwargs):
            captured["payload"] = payload
            return {"sequence": []}

        monkeypatch.setattr(character_module, "_agent_json", fake_agent_json)

        character_module.character_step(ctx, tamamo, nonce=0)

        assert "Hinami" not in captured["payload"]["relationships"]
