"""Regression tests for B14 from Fable's audit: the nonexistent_cast
existence-masking backstop (frames.is_recognized_in_frame) was only
consulted inside agents/character.py's own payload-filtering step, and
even there it silently defeated itself for DORMANT cast members (a
masked character can be simultaneously active/present-as-a-stranger AND
declared not-yet-existing -- these are independent axes). Two real gaps:

1. character_step's own name_to_id lookup was built from ctx.cast
   (active-only), so a DORMANT masked character fell through to a -1
   fallback that reads as "recognized" (-1 is never in a frame's
   nonexistent_cast list) -- the exact case the mask exists to catch.
   Fixed by looking names up against EVERY attached character
   (scene.all_cast_name_to_id), active or dormant.

2. commit_mapping's introduction-commit path (world.known writes) never
   consulted is_recognized_in_frame at all -- the mapping model could
   freely propose "X learns Y's identity" for a Y who is deterministically
   masked in this frame, permanently marking them recognized in
   world.known with no way to un-recognize them afterward. Fixed with an
   is_recognized_in_frame check before the known[who].append(learns) write.
"""

from __future__ import annotations

import json
import time

import pytest

import commit
from character_schema import default_character_data
from frames import create_frame
from pipeline_context import ChatData, PipelineContext, TurnData
from scene import all_cast_name_to_id


def _make_chat(db):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )


def _make_char(db, name, status="active"):
    char_id = db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        (name, json.dumps(default_character_data(name)), "{}", time.time()),
    )
    return char_id


def _attach(db, chat_id, char_id, status="active"):
    db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, status, "{}"),
    )


class TestAllCastNameToIdIncludesDormant:
    def test_dormant_characters_are_included(self, temp_db):
        chat_id = _make_chat(temp_db)
        alice = _make_char(temp_db, "Alice")
        bob = _make_char(temp_db, "Bob")
        _attach(temp_db, chat_id, alice, status="active")
        _attach(temp_db, chat_id, bob, status="dormant")

        mapping = all_cast_name_to_id(chat_id)
        assert mapping == {"Alice": alice, "Bob": bob}


class TestCharacterStepMasksDormantCastmatesToo:
    def test_a_dormant_masked_castmates_relationship_is_still_stripped(self, temp_db, monkeypatch):
        """Mirrors test_frames_integration.py's existing masking test,
        but with the masked character DORMANT rather than active -- the
        real pipeline's ctx.cast is active_cast(), which excludes
        dormant rows entirely, so a name_to_id lookup built from ctx.cast
        alone (the pre-fix code) could never resolve a dormant
        castmate's real id and fell through to a fallback that reads as
        "recognized". Existence masking and active/dormant status are
        independent axes -- a not-yet-existing character being dormant
        must not accidentally bypass the mask."""
        import agents.character as character_module
        import memory
        from scene import active_cast

        chat_id = _make_chat(temp_db)
        tamamo = _make_char(temp_db, "Tamamo")
        hinami = _make_char(temp_db, "Hinami")
        _attach(temp_db, chat_id, tamamo, status="active")
        _attach(temp_db, chat_id, hinami, status="dormant")
        temp_db.wset(chat_id, "scene", {
            "location": "Shrine", "time": "day",
            "rooms": {"hall": {"name": "Hall", "adjacent": []}},
            "positions": {"Tamamo": "hall"},
            "entities": {}, "attire": {}, "overlays": {},
        })

        from frames import create_frame
        past = create_frame(chat_id, label="Before Hinami existed", ordinal=-10,
                            kind="past", travelers=[hinami], nonexistent_cast=[hinami])

        memory.save_relationships(
            chat_id, tamamo,
            memory.RelationshipGraph.from_dict({"Hinami": {"target_name": "Hinami", "trust": 0.9}}),
        )

        # The real pipeline's ctx.cast for this frame -- active_cast
        # excludes Hinami since she's dormant.
        cast = active_cast(chat_id, past)
        assert [c["id"] for c in cast] == [tamamo]

        turn_id = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) VALUES(?,?,?,?,?)",
            (chat_id, 1, "who are you?", time.time(), past),
        )
        ctx = PipelineContext(
            chat=ChatData(id=chat_id, name="Test", persona_id=None, lorebook_id=None,
                          scenario="", created=time.time()),
            turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                          player_input="who are you?", created=time.time(), frame_id=past),
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


class TestCommitMappingHonorsExistenceMasking:
    def _base_ctx(self, temp_db, chat_id, frame_id, cast):
        turn_id = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) VALUES(?,?,?,?,?)",
            (chat_id, 1, "test", time.time(), frame_id),
        )
        ctx = PipelineContext(
            chat=ChatData(id=chat_id, name="Test", persona_id=None, lorebook_id=None,
                          scenario="", created=time.time()),
            turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="test",
                          created=time.time(), frame_id=frame_id),
            cast=cast, input="test",
        )
        ctx.director_resolve = {
            "summary": "", "resolved_event": "", "dialogue_log": [],
            "state_diff": {"introductions": ["Alice meets Bob"]},
        }
        ctx.narrator = {}
        ctx.mapping_stage = {}
        return ctx

    def test_a_masked_characters_identity_is_not_recognized_via_introduction(
        self, temp_db, monkeypatch,
    ):
        chat_id = _make_chat(temp_db)
        alice = _make_char(temp_db, "Alice")
        bob = _make_char(temp_db, "Bob")  # not yet existing to natives here
        _attach(temp_db, chat_id, alice, status="active")
        _attach(temp_db, chat_id, bob, status="active")

        past = create_frame(chat_id, label="Before Bob existed", ordinal=-10,
                            kind="past", nonexistent_cast=[bob])

        cast = temp_db.q(
            "SELECT ch.*, cc.state AS cstate, cc.status FROM chat_chars cc "
            "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
            (chat_id,),
        )
        ctx = self._base_ctx(temp_db, chat_id, past, cast)

        import llm_quality
        monkeypatch.setattr(llm_quality, "complete_validated_json", lambda **k: {
            "validated": [], "lore_ops": [],
            "validated_introductions": [{"ok": True, "who": "Alice", "learns": "Bob"}],
        })

        from db import active_frame_id, wget
        token = active_frame_id.set(past)
        try:
            commit.commit_mapping(ctx, nonce=0)
            known = wget(chat_id, "known", {})
        finally:
            active_frame_id.reset(token)

        assert "Bob" not in (known.get("Alice") or [])

    def test_a_recognized_characters_identity_is_still_learned(self, temp_db, monkeypatch):
        chat_id = _make_chat(temp_db)
        alice = _make_char(temp_db, "Alice")
        bob = _make_char(temp_db, "Bob")
        _attach(temp_db, chat_id, alice, status="active")
        _attach(temp_db, chat_id, bob, status="active")

        past = create_frame(chat_id, label="After Bob existed", ordinal=-10, kind="past")

        cast = temp_db.q(
            "SELECT ch.*, cc.state AS cstate, cc.status FROM chat_chars cc "
            "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
            (chat_id,),
        )
        ctx = self._base_ctx(temp_db, chat_id, past, cast)

        import llm_quality
        monkeypatch.setattr(llm_quality, "complete_validated_json", lambda **k: {
            "validated": [], "lore_ops": [],
            "validated_introductions": [{"ok": True, "who": "Alice", "learns": "Bob"}],
        })

        from db import active_frame_id, wget
        token = active_frame_id.set(past)
        try:
            commit.commit_mapping(ctx, nonce=0)
            known = wget(chat_id, "known", {})
        finally:
            active_frame_id.reset(token)

        assert "Bob" in (known.get("Alice") or [])
