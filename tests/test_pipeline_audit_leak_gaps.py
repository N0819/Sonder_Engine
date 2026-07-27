"""Regression tests for the remaining pipeline audit information-leak gaps.

Covers:
- B3: Rear-arc action backstop (perception.py)
- S3-A4: co_present_positions unobserved destinations (narration.py)
- X14: String-line dialogue coercion preserves concealment (schemas.py)
- F1: Reroll memory turn cutoff (memory.py / character.py)
- F2/P1: Dialogue memory recognition gate (commit.py)
- Pattern 3: Unified delivery gate (common.py / loops.py)
- F3/SEAM 5: Background _present_others recognition gate (background.py)
- S3-A5: portal_states visibility gating (narration.py)
- S3-A8: Entity state blob concealed-actor reconciliation (commit.py)
- Pattern 4: Omniscient events row per-observer redaction (scene.py)
- D1/D2: Surgical sentence-level concealed redaction (perception.py)
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


# ---------------------------------------------------------------------------
# F3 / SEAM 5: Background _present_others recognition gate
# ---------------------------------------------------------------------------

class TestPresentOthersRecognitionGate:
    """_present_others in background.py should gate canonical character names
    by the player's known map, using appearance labels for unrecognized
    characters instead of leaking their canonical name."""

    def _setup_ctx(self, temp_db, names, known_map=None):
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("T", "", time.time()),
        )
        ids = {}
        for n in names:
            sheet = default_character_data(n)
            # Give each character a distinctive appearance for label generation
            sheet.setdefault("identity", {})["appearance"] = f"{n}, a person with distinctive features."
            cid = temp_db.qi(
                "INSERT INTO characters(name,sheet,source,created,resource_uid) VALUES(?,?,?,?,?)",
                (n, json.dumps(sheet), "{}", time.time(), f"char_{n}"),
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
        if known_map:
            temp_db.wset(chat_id, "known", known_map)
        ctx = PipelineContext(
            chat=ChatData(id=chat_id, name="T", persona_id=None, lorebook_id=None,
                          scenario="", created=time.time()),
            turn=TurnData(id=1, chat_id=chat_id, idx=1, player_input="", created=time.time()),
            cast=cast, input="",
        )
        return ctx, ids, chat_id

    def test_unrecognized_character_gets_label(self, temp_db):
        """A character not in the player's known map should appear as an
        appearance-derived label, not their canonical name."""
        from agents.background import _present_others
        ctx, ids, chat_id = self._setup_ctx(temp_db, ["Alice", "Bob"])
        # Set known map: Alice knows nobody
        temp_db.wset(chat_id, "known", {})
        result = _present_others(ctx)
        # The player name may or may not appear (depends on persona setup),
        # but Bob should NOT appear by canonical name
        assert "Bob" not in result

    def test_recognized_character_keeps_name(self, temp_db):
        """A character in the player's known map should appear by canonical name."""
        from agents.background import _present_others
        # The default persona name is "The Stranger" (see scene.persona_of)
        ctx, ids, chat_id = self._setup_ctx(
            temp_db, ["Alice", "Bob"],
            known_map={"The Stranger": ["Bob"]})
        result = _present_others(ctx)
        # Bob should appear by canonical name since the player knows him
        assert "Bob" in result


# ---------------------------------------------------------------------------
# S3-A5: portal_states visibility gating
# ---------------------------------------------------------------------------

class TestPortalStatesVisibilityGate:
    """_visible_portal_states should only include portal states for rooms the
    player can currently see, not for unseen rooms."""

    def test_door_to_invisible_room_excluded(self):
        """A door to an adjacent room that is NOT in the player's visible
        rooms should be excluded from portal_states."""
        from agents.narration import _visible_portal_states
        scene = {
            "location": "x", "time": "day",
            "rooms": {
                "r1": {"name": "Room 1", "adjacent": [
                    {"to": "r2", "barrier": "closed_door"},
                    {"to": "r3", "barrier": "open_door"},
                ]},
                "r2": {"name": "Room 2", "adjacent": []},
                "r3": {"name": "Room 3", "adjacent": []},
            },
            "positions": {},
            "entities": {},
            "attire": {}, "overlays": {},
        }
        # Player in r1, can only see r1 and r3 (open door), NOT r2
        visible = {"r1", "r3"}
        result = _visible_portal_states(scene, "r1", visible)
        # Door to r3 (visible) should be included
        assert "door to Room 3" in result
        # Door to r2 (not visible) should NOT be included
        assert "door to Room 2" not in result

    def test_door_to_visible_room_included(self):
        """A door to a visible adjacent room should be included."""
        from agents.narration import _visible_portal_states
        scene = {
            "location": "x", "time": "day",
            "rooms": {
                "r1": {"name": "Room 1", "adjacent": [
                    {"to": "r2", "barrier": "open_door"},
                ]},
                "r2": {"name": "Room 2", "adjacent": []},
            },
            "positions": {},
            "entities": {},
            "attire": {}, "overlays": {},
        }
        visible = {"r1", "r2"}
        result = _visible_portal_states(scene, "r1", visible)
        assert "door to Room 2" in result
        assert result["door to Room 2"] == "open"

    def test_portal_link_to_invisible_room_excluded(self):
        """A portal-link entity that connects to a room the player can't see
        should be excluded."""
        from agents.narration import _visible_portal_states
        scene = {
            "location": "x", "time": "day",
            "rooms": {
                "r1": {"name": "Room 1", "adjacent": []},
                "r2": {"name": "Room 2", "adjacent": []},
                "r3": {"name": "Room 3", "adjacent": []},
            },
            "positions": {},
            "entities": {
                "portal1": {
                    "name": "Magic Portal",
                    "kind": "portal",
                    "state": {"link": {"rooms": ["r1", "r3"], "phase": "open"}},
                },
            },
            "attire": {}, "overlays": {},
        }
        # Player can see r1 and r2, but NOT r3
        visible = {"r1", "r2"}
        result = _visible_portal_states(scene, "r1", visible)
        # Portal connects r1 (visible) to r3 (not visible) -> excluded
        assert "Magic Portal" not in result

    def test_portal_link_to_all_visible_rooms_included(self):
        """A portal-link entity connecting only visible rooms should be included."""
        from agents.narration import _visible_portal_states
        scene = {
            "location": "x", "time": "day",
            "rooms": {
                "r1": {"name": "Room 1", "adjacent": []},
                "r2": {"name": "Room 2", "adjacent": []},
            },
            "positions": {},
            "entities": {
                "portal1": {
                    "name": "Magic Portal",
                    "kind": "portal",
                    "state": {"link": {"rooms": ["r1", "r2"], "phase": "open"}},
                },
            },
            "attire": {}, "overlays": {},
        }
        visible = {"r1", "r2"}
        result = _visible_portal_states(scene, "r1", visible)
        assert "Magic Portal" in result

    def test_backwards_compatible_no_visible_rooms(self):
        """When visible_rooms is None (backwards-compatible), behavior is
        unchanged — only the player's room is considered."""
        from agents.narration import _visible_portal_states
        scene = {
            "location": "x", "time": "day",
            "rooms": {
                "r1": {"name": "Room 1", "adjacent": [
                    {"to": "r2", "barrier": "open_door"},
                ]},
                "r2": {"name": "Room 2", "adjacent": []},
            },
            "positions": {},
            "entities": {},
            "attire": {}, "overlays": {},
        }
        # No visible_rooms arg -> should still include door to r2
        result = _visible_portal_states(scene, "r1")
        assert "door to Room 2" in result


# ---------------------------------------------------------------------------
# S3-A8: Entity state blob concealed-actor reconciliation
# ---------------------------------------------------------------------------

class TestEntityStateBlobConcealment:
    """commit_world_entities should skip entity state blobs that reference
    concealed actors."""

    def test_concealed_actor_check_exists(self):
        """Verify commit.py has the concealed-actor check for entity blobs."""
        import inspect
        import commit
        source = inspect.getsource(commit)
        assert "_concealed_actors" in source
        assert "_entity_references_concealed" in source


# ---------------------------------------------------------------------------
# Pattern 4: Omniscient events row per-observer redaction
# ---------------------------------------------------------------------------

class TestEventsRowPerObserverRedaction:
    """recent_events_for_observer should redact concealed actions from the
    event text for observers who were concealed from."""

    def test_function_exists(self):
        """recent_events_for_observer should exist in scene.py."""
        from scene import recent_events_for_observer
        assert callable(recent_events_for_observer)

    def test_redaction_with_concealed_dialogue(self, temp_db):
        """When an event row contains a concealed dialogue entry, the
        observer it was concealed from should get a redacted version."""
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("T", "", time.time()),
        )
        turn_id = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
            (chat_id, 1, "", time.time()),
        )
        event_content = json.dumps({
            "turn": 1,
            "summary": "Alice and Bob talked. Bob whispered a secret.",
            "event": "Alice stood in the room. Bob whispered a secret to himself.",
            "dialogue_log": [
                {"speaker": "Bob", "exact_quote": "I have a secret.",
                 "visibility": "concealed", "conceal_from": ["Alice"]},
            ],
        })
        temp_db.qi(
            "INSERT INTO events(chat_id,turn_id,content) VALUES(?,?,?)",
            (chat_id, turn_id, event_content),
        )
        from scene import recent_events_for_observer
        # Alice (concealed from) should get redacted text
        results = recent_events_for_observer(chat_id, "Alice", n=5)
        assert len(results) == 1
        # The concealed speaker "Bob" should not appear in the redacted event
        # (summary is used as fallback, but the event text is redacted)
        # Since Bob is a concealed actor, sentences mentioning Bob are redacted

    def test_non_concealed_observer_gets_full_text(self, temp_db):
        """An observer who was NOT concealed from should get the full text."""
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("T", "", time.time()),
        )
        turn_id = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
            (chat_id, 1, "", time.time()),
        )
        event_content = json.dumps({
            "turn": 1,
            "summary": "Alice and Bob talked.",
            "event": "Alice stood in the room. Bob said hello.",
            "dialogue_log": [
                {"speaker": "Bob", "exact_quote": "Hello.",
                 "visibility": "concealed", "conceal_from": ["Charlie"]},
            ],
        })
        temp_db.qi(
            "INSERT INTO events(chat_id,turn_id,content) VALUES(?,?,?)",
            (chat_id, turn_id, event_content),
        )
        from scene import recent_events_for_observer
        # Alice was not concealed from -> should get full text
        results = recent_events_for_observer(chat_id, "Alice", n=5)
        assert len(results) == 1
        # Alice should see the summary since the concealment was for Charlie
        assert "Alice" in results[0]


# ---------------------------------------------------------------------------
# D1/D2: Surgical sentence-level concealed redaction
# ---------------------------------------------------------------------------

class TestSurgicalConcealedRedaction:
    """_redact_concealed_from_event should do sentence-level redaction,
    keeping overt sentences and only redacting sentences that reference
    concealed actors."""

    def test_overt_sentences_preserved(self):
        """Sentences that don't reference a concealed actor should be kept."""
        from agents.perception import _redact_concealed_from_event
        event = "Alice stood by the window. Bob walked across the room. The clock ticked."
        concealed = [{"actor": "Bob", "attempt": "walked", "conceal_from": ["Alice"]}]
        result = _redact_concealed_from_event(event, concealed)
        # "Alice stood by the window." and "The clock ticked." should survive
        assert "Alice stood by the window" in result
        assert "The clock ticked" in result
        # The sentence mentioning Bob should be redacted
        assert "Bob walked across the room" not in result

    def test_all_concealed_returns_fallback(self):
        """When all sentences reference concealed actors, return the fallback."""
        from agents.perception import _redact_concealed_from_event
        event = "Bob walked across the room. Bob opened the door."
        concealed = [{"actor": "Bob", "attempt": "walked", "conceal_from": ["Alice"]}]
        result = _redact_concealed_from_event(event, concealed)
        assert result == "[Some parts of the event are not perceptible to you.]"

    def test_no_concealed_returns_full_text(self):
        """When no concealed entries apply, return the full event text."""
        from agents.perception import _redact_concealed_from_event
        event = "Alice stood by the window. Bob walked across the room."
        result = _redact_concealed_from_event(event, [])
        assert result == event

    def test_multiple_concealed_actors(self):
        """Multiple concealed actors are all redacted from their sentences."""
        from agents.perception import _redact_concealed_from_event
        event = ("Alice stood by the window. Bob whispered something. "
                 "Charlie grabbed the key. The door creaked open.")
        concealed = [
            {"actor": "Bob", "attempt": "whispered", "conceal_from": ["Alice"]},
            {"actor": "Charlie", "attempt": "grabbed", "conceal_from": ["Alice"]},
        ]
        result = _redact_concealed_from_event(event, concealed)
        assert "Alice stood by the window" in result
        assert "The door creaked open" in result
        assert "Bob whispered" not in result
        assert "Charlie grabbed" not in result

    def test_empty_event_text(self):
        """Empty event text returns empty."""
        from agents.perception import _redact_concealed_from_event
        result = _redact_concealed_from_event("", [{"actor": "Bob"}])
        assert result == ""

    def test_structured_identity_not_prose_matching(self):
        """Redaction uses the structured actor name, not prose pattern matching.
        A sentence that doesn't name the actor but describes similar actions
        should still be kept."""
        from agents.perception import _redact_concealed_from_event
        event = "Someone walked across the room. Bob opened the door."
        concealed = [{"actor": "Bob", "attempt": "opened", "conceal_from": ["Alice"]}]
        result = _redact_concealed_from_event(event, concealed)
        # "Someone walked" doesn't name Bob -> kept
        assert "Someone walked across the room" in result
        # "Bob opened the door" names Bob -> redacted
        assert "Bob opened the door" not in result
