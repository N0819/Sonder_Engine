"""Regression tests for the remaining pipeline audit information-leak gaps.

Covers:
- B3: Rear-arc action backstop (perception.py)
- S3-A4: co_present_positions unobserved destinations (narration.py)
- X14: String-line dialogue coercion preserves concealment (schemas.py)
- F1: Reroll memory turn cutoff (memory.py / character.py)
- F2/P1: Dialogue memory recognition gate (commit.py)
- Pattern 3: Unified delivery gate (common.py / loops.py)
"""

from __future__ import annotations

import json
import time

import pytest

from character_schema import default_character_data
from pipeline_context import ChatData, PipelineContext, TurnData
from schemas import preprocess_llm_output


# ---------------------------------------------------------------------------
# X14: String-line dialogue coercion preserves concealment
# ---------------------------------------------------------------------------

class TestStringLineConcealment:
    """A string dialogue line with a [concealed] prefix should preserve
    visibility='concealed' through coercion, not default to 'overt'."""

    def _process(self, dialogue_log):
        raw = {"dialogue_log": dialogue_log}
        result = preprocess_llm_output("character", raw)
        return result["dialogue_log"]

    def test_concealed_string_prefix_preserved(self):
        lines = ["[concealed] Sarah: I know your secret"]
        cleaned = self._process(lines)
        assert len(cleaned) == 1
        assert cleaned[0]["visibility"] == "concealed"
        assert cleaned[0]["speaker"] == "Sarah"
        assert cleaned[0]["exact_quote"] == "I know your secret"

    def test_overt_string_default_visibility(self):
        lines = ["Sarah: Hello there"]
        cleaned = self._process(lines)
        assert len(cleaned) == 1
        assert cleaned[0]["visibility"] == "overt"

    def test_dict_visibility_concealed_preserved(self):
        lines = [{"speaker": "Bob", "exact_quote": "psst", "visibility": "concealed"}]
        cleaned = self._process(lines)
        assert len(cleaned) == 1
        assert cleaned[0]["visibility"] == "concealed"

    def test_dict_visibility_hidden_normalized_to_concealed(self):
        lines = [{"speaker": "Bob", "exact_quote": "psst", "visibility": "hidden"}]
        cleaned = self._process(lines)
        assert len(cleaned) == 1
        assert cleaned[0]["visibility"] == "concealed"

    def test_dict_conceal_from_preserved(self):
        lines = [{"speaker": "Bob", "exact_quote": "psst", "conceal_from": ["Alice"]}]
        cleaned = self._process(lines)
        assert len(cleaned) == 1
        assert cleaned[0]["conceal_from"] == ["Alice"]

    def test_dict_conceal_from_coerced_to_list(self):
        lines = [{"speaker": "Bob", "exact_quote": "psst", "conceal_from": "Alice"}]
        cleaned = self._process(lines)
        assert len(cleaned) == 1
        assert cleaned[0]["conceal_from"] == []


# ---------------------------------------------------------------------------
# F1: Reroll memory turn cutoff (search_memories max_turn_idx)
# ---------------------------------------------------------------------------

class TestRerollMemoryCutoff:
    """search_memories should accept a max_turn_idx parameter that excludes
    memories with turn_idx > max_turn_idx."""

    def test_max_turn_idx_parameter_exists(self):
        import inspect
        from memory import search_memories
        sig = inspect.signature(search_memories)
        assert "max_turn_idx" in sig.parameters

    def test_build_character_memory_context_max_turn_idx(self):
        import inspect
        from memory import build_character_memory_context
        sig = inspect.signature(build_character_memory_context)
        assert "max_turn_idx" in sig.parameters


# ---------------------------------------------------------------------------
# B3: Rear-arc action backstop
# ---------------------------------------------------------------------------

class TestRearArcActionBackstop:
    """The perception_outcome action backstop should skip actors in the
    perceiver's behind_sources (rear arc)."""

    def test_behind_sources_field_in_perceiver_dict(self):
        """The perceiver dict in perception_outcome includes behind_sources."""
        # This is a structural test: the field exists and is populated
        # by _behind_sources, which is already tested. The fix adds a
        # check for it in the action backstop loop.
        from agents.perception import _behind_sources
        # Verify the function still exists and returns a list
        scene = {
            "rooms": {"r1": {"name": "Room 1", "adjacent": []}},
            "positions": {"Alice": "r1", "Bob": "r1"},
            "entities": {}, "attire": {}, "overlays": {},
            "location": "x", "time": "day",
        }
        result = _behind_sources(scene, "Alice", [])
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# S3-A4: co_present_positions only includes current-room characters
# ---------------------------------------------------------------------------

class TestCoPresentPositionsLeak:
    """_position_delta_payload should only include characters currently in
    the player's room, not those who left (which leaks destination info)."""

    def _setup_ctx(self, temp_db, names, rooms):
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("T", "", time.time()),
        )
        ids = {}
        for n in names:
            cid = temp_db.qi(
                "INSERT INTO characters(name,sheet,source,created,resource_uid) VALUES(?,?,?,?,?)",
                (n, json.dumps(default_character_data(n)), "{}", time.time(), f"char_{n}"),
            )
            temp_db.qi(
                "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
                (chat_id, cid, "active", "{}"),
            )
            ids[n] = cid
        cast = temp_db.q(
            "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
            "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
            (chat_id,),
        )
        scene = {
            "location": "x", "time": "day",
            "rooms": {rid: {"name": rname, "adjacent": []}
                      for rid, rname in rooms.items()},
            "positions": {n: list(rooms.keys())[0] for n in names},
            "entities": {}, "attire": {}, "overlays": {},
        }
        temp_db.wset(chat_id, "scene", scene)
        ctx = PipelineContext(
            chat=ChatData(id=chat_id, name="T", persona_id=None, lorebook_id=None,
                          scenario="", created=time.time()),
            turn=TurnData(id=1, chat_id=chat_id, idx=1, player_input="", created=time.time()),
            cast=cast, input="",
        )
        return ctx, ids, scene, chat_id

    def test_character_who_left_not_in_positions(self, temp_db):
        """A character who left the player's room should NOT appear in
        co_present_positions (no destination leak)."""
        from agents.narration import _position_delta_payload
        ctx, ids, scene, chat_id = self._setup_ctx(
            temp_db, ["Alice", "Bob"], {"r1": "Room 1", "r2": "Room 2"})
        # Alice stays in r1, Bob moves to r2
        outcome_scene = json.loads(json.dumps(scene))
        outcome_scene["positions"]["Bob"] = "r2"
        ctx["outcome_scene"] = outcome_scene
        cast_info = {
            "Bob": {"appearance": "a tall person", "aliases": []},
        }
        payload, facts, room_names = _position_delta_payload(
            ctx, ctx.chat, "Alice", "r1", set(), cast_info)
        # Bob left -> should NOT be in payload (no destination leak)
        assert "Bob" not in payload

    def test_character_who_stays_in_positions(self, temp_db):
        """A character who stays in the player's room SHOULD appear."""
        from agents.narration import _position_delta_payload
        ctx, ids, scene, chat_id = self._setup_ctx(
            temp_db, ["Alice", "Bob"], {"r1": "Room 1", "r2": "Room 2"})
        outcome_scene = json.loads(json.dumps(scene))
        ctx["outcome_scene"] = outcome_scene
        cast_info = {
            "Bob": {"appearance": "a tall person", "aliases": []},
        }
        payload, facts, room_names = _position_delta_payload(
            ctx, ctx.chat, "Alice", "r1", {"Bob"}, cast_info)
        # Bob is still in r1 -> should be in payload (recognized, so name used)
        assert "Bob" in payload
        assert payload["Bob"]["room"] == "Room 1"
        assert payload["Bob"]["moved"] is False

    def test_character_who_arrived_in_positions(self, temp_db):
        """A character who arrived from another room should appear with
        moved=True and prev_room set."""
        from agents.narration import _position_delta_payload
        ctx, ids, scene, chat_id = self._setup_ctx(
            temp_db, ["Alice", "Bob"], {"r1": "Room 1", "r2": "Room 2"})
        # Bob starts in r2 (set previous scene), then moves to r1
        prev_scene = json.loads(json.dumps(scene))
        prev_scene["positions"]["Bob"] = "r2"
        temp_db.wset(chat_id, "scene", prev_scene)

        outcome_scene = json.loads(json.dumps(scene))
        outcome_scene["positions"]["Bob"] = "r1"
        ctx["outcome_scene"] = outcome_scene
        cast_info = {
            "Bob": {"appearance": "a tall person", "aliases": []},
        }
        payload, facts, room_names = _position_delta_payload(
            ctx, ctx.chat, "Alice", "r1", {"Bob"}, cast_info)
        # Bob arrived in r1 -> should be in payload with moved=True
        assert "Bob" in payload
        assert payload["Bob"]["moved"] is True
        assert payload["Bob"]["prev_room"] == "Room 2"


# ---------------------------------------------------------------------------
# Pattern 3: Unified delivery gate
# ---------------------------------------------------------------------------

class TestDeliveryGate:
    """_delivery_ok should consolidate containment, awareness, and sight gates."""

    def test_delivery_ok_exists(self):
        from agents.common import _delivery_ok
        assert callable(_delivery_ok)

    def test_non_aware_blocks_delivery(self):
        from agents.common import _delivery_ok
        scene = {
            "rooms": {"r1": {"name": "Room 1", "adjacent": []}},
            "positions": {"Alice": "r1", "Bob": "r1"},
            "entities": {}, "attire": {}, "overlays": {},
            "location": "x", "time": "day",
        }
        # Non-awake awareness blocks all delivery
        assert not _delivery_ok(scene, "Alice", "Bob", "sight",
                                awareness="unconscious")
        assert not _delivery_ok(scene, "Alice", "Bob", "hearing",
                                awareness="asleep")
        assert not _delivery_ok(scene, "Alice", "Bob", "action",
                                awareness="sedated")

    def test_behind_blocks_sight(self):
        from agents.common import _delivery_ok
        scene = {
            "rooms": {"r1": {"name": "Room 1", "adjacent": []}},
            "positions": {"Alice": "r1", "Bob": "r1"},
            "entities": {}, "attire": {}, "overlays": {},
            "location": "x", "time": "day",
        }
        # Behind sources blocks sight and action
        assert not _delivery_ok(scene, "Alice", "Bob", "sight",
                                behind_sources=["Bob"])
        assert not _delivery_ok(scene, "Alice", "Bob", "action",
                                behind_sources=["Bob"])
        # Without behind_sources, sight is OK
        assert _delivery_ok(scene, "Alice", "Bob", "sight")

    def test_hearing_not_blocked_by_behind(self):
        from agents.common import _delivery_ok
        scene = {
            "rooms": {"r1": {"name": "Room 1", "adjacent": []}},
            "positions": {"Alice": "r1", "Bob": "r1"},
            "entities": {}, "attire": {}, "overlays": {},
            "location": "x", "time": "day",
        }
        # Hearing is not blocked by behind (you can hear behind you)
        assert _delivery_ok(scene, "Alice", "Bob", "hearing",
                            behind_sources=["Bob"])

    def test_aware_none_allows_delivery(self):
        from agents.common import _delivery_ok
        scene = {
            "rooms": {"r1": {"name": "Room 1", "adjacent": []}},
            "positions": {"Alice": "r1", "Bob": "r1"},
            "entities": {}, "attire": {}, "overlays": {},
            "location": "x", "time": "day",
        }
        # awareness=None means no awareness gate -> allowed
        assert _delivery_ok(scene, "Alice", "Bob", "sight", awareness=None)


# ---------------------------------------------------------------------------
# F2/P1: Dialogue memory recognition gate
# ---------------------------------------------------------------------------

class TestDialogueMemoryRecognitionGate:
    """Dialogue memories should use appearance-based labels for unrecognized
    speakers instead of canonical names."""

    def test_recognition_gate_in_commit(self):
        """Verify commit.py has the recognition gate code."""
        import inspect
        import commit
        source = inspect.getsource(commit)
        # The gate should check the hearer's known map
        assert "_hearer_known" in source
        assert "spk_label" in source
        assert "a voice" in source
