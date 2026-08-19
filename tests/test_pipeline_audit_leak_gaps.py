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

from mind import memory
from story.character_schema import default_character_data
from core.pipeline_context import ChatData, PipelineContext, TurnData
from llm.schemas import preprocess_llm_output


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
# F1: Reroll memory turn cutoff (search_memories current_turn_idx)
# ---------------------------------------------------------------------------

class TestRerollMemoryCutoff:
    """A mind deciding turn N must not retrieve turn N's own committed
    outcome. `current_turn_idx` is the single hard filter that guarantees it;
    it was once only a recency-scoring hint, which is what let a reroll read
    the discarded future of the beat it was re-deciding (audit F1).

    Asserted behaviourally against a populated bank -- the earlier version of
    this test only checked that a parameter name appeared in a signature,
    which a broken filter would have passed just as happily.
    """

    def _bank(self, db):
        chat_id = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                        ("Test", "", time.time()))
        char_id = db.qi(
            "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
            ("Alice", json.dumps(default_character_data("Alice")), "{}", time.time()))
        memory.add_memory(chat_id, char_id, None, "episode", "witnessed", 0.9,
                          "Alice watched the lantern go out.", turn_idx=3,
                          gist="the lantern went out")
        memory.add_memory(chat_id, char_id, None, "episode", "witnessed", 0.9,
                          "Alice watched the lantern shatter on the floor.", turn_idx=7,
                          gist="the lantern shattered")
        memory.add_memory(chat_id, char_id, None, "episode", "witnessed", 0.9,
                          "Alice watched the lantern be swept up afterwards.", turn_idx=8,
                          gist="the lantern was swept up")
        return chat_id, char_id

    def test_current_and_later_turns_are_dropped(self, temp_db):
        chat_id, char_id = self._bank(temp_db)
        found = memory.search_memories(chat_id, char_id, "lantern", k=10,
                                       current_turn_idx=7)
        assert {m["turn_idx"] for m in found} == {3}

    def test_no_cutoff_when_current_turn_idx_is_omitted(self, temp_db):
        """The filter is opt-in: an author-facing search with no turn context
        must still see the whole bank."""
        chat_id, char_id = self._bank(temp_db)
        found = memory.search_memories(chat_id, char_id, "lantern", k=10)
        assert {m["turn_idx"] for m in found} == {3, 7, 8}

    def test_unplaced_memories_survive_the_cutoff(self, temp_db):
        """turn_idx IS NULL rows (imported/authored) belong to no turn, so
        they cannot be this turn's leaked outcome and must not be dropped."""
        chat_id, char_id = self._bank(temp_db)
        memory.add_memory(chat_id, char_id, None, "semantic", "authored", 0.9,
                          "Alice has always hated lantern light.", turn_idx=None,
                          gist="hates lantern light")
        found = memory.search_memories(chat_id, char_id, "lantern", k=10,
                                       current_turn_idx=7)
        assert None in {m["turn_idx"] for m in found}

    def test_character_context_cannot_see_this_turns_outcome(self, temp_db):
        """The end-to-end path a rerolled character step actually takes."""
        chat_id, char_id = self._bank(temp_db)
        ctx = memory.build_character_memory_context(
            chat_id=chat_id, char_id=char_id, current_turn_idx=7,
            current_view="The lantern is guttering.", active_state={})
        episodes = ctx["recent_episodes"] + ctx["recalled_old_memories"]
        assert episodes, "bank must be non-empty or this test is vacuous"
        assert all(e.get("turn_idx") is None or e["turn_idx"] < 7 for e in episodes)
        assert "shatter" not in " ".join(str(e.get("content") or "") for e in episodes)


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
        """A character who arrived in the player's room appears with
        moved=True -- the player watched them walk in -- but their ORIGIN is
        only named when the player can see into it.

        Rewritten for the second half of S3-A4: this test previously asserted
        prev_room == "Room 2" for an entrant out of a room r1 has no sight
        line to at all, which is the leak the audit named (the player is told
        the display name of a room they may never have heard of). The arrival
        itself stays -- withholding a body the player plainly sees would break
        ordinary narration -- and the origin is asserted BOTH ways below."""
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
        # r1 has no adjacency to r2 at all: the player saw him arrive, not
        # where he came from.
        assert payload["Bob"]["prev_room"] is None

        # Give r1 a sight line into r2 and the origin becomes the player's to
        # know, so it ships.
        outcome_scene["rooms"]["r1"]["adjacent"] = [
            {"to": "r2", "barrier": "open", "distance": "near"}]
        payload, facts, room_names = _position_delta_payload(
            ctx, ctx.chat, "Alice", "r1", {"Bob"}, cast_info)
        assert payload["Bob"]["prev_room"] == "Room 2"


# ---------------------------------------------------------------------------
# Pattern 3: Unified delivery gate
# ---------------------------------------------------------------------------

class TestDeliveryGate:
    """_delivery_ok is the single predicate every deterministic delivery site
    calls: containment, awareness, hearing (with proximity) and sight (with
    the rear-arc blind spot) in one place.

    These used to pass a scene as the first argument and assert only that the
    function returned True. That was vacuous -- the implementation returned
    True for every channel after the containment check, so 'sight is OK' and
    'hearing is not blocked by behind' were the same assertion about a
    function that gated neither. The relation is now the caller's own
    spatial_rel result, and each channel is checked for what it claims.
    """

    SCENE = {
        "rooms": {"r1": {"name": "Room 1", "adjacent": []},
                  "r2": {"name": "Room 2", "adjacent": []}},
        "positions": {"Alice": "r1", "Bob": "r1", "Carol": "r2"},
        "entities": {}, "attire": {}, "overlays": {},
        "location": "x", "time": "day",
    }

    def _rel(self, a="r1", b="r1"):
        from world.spatial import spatial_rel
        return spatial_rel(self.SCENE, a, b)

    def test_delivery_ok_exists(self):
        from agents.common import _delivery_ok
        assert callable(_delivery_ok)

    def test_non_aware_blocks_every_channel(self):
        from agents.common import _delivery_ok
        rel = self._rel()
        for channel, level in (("sight", "unconscious"), ("hearing", "asleep"),
                               ("action", "sedated")):
            assert not _delivery_ok(rel, self.SCENE, "Alice", "Bob", channel,
                                    awareness=level)

    def test_awake_observer_receives_a_co_located_source(self):
        from agents.common import _delivery_ok
        rel = self._rel()
        assert _delivery_ok(rel, self.SCENE, "Alice", "Bob", "sight",
                            awareness="awake")
        assert _delivery_ok(rel, self.SCENE, "Alice", "Bob", "hearing",
                            awareness="awake")

    def test_behind_blocks_sight_and_action_but_not_hearing(self):
        from agents.common import _delivery_ok
        rel = self._rel()
        assert not _delivery_ok(rel, self.SCENE, "Alice", "Bob", "sight",
                                behind_sources=["Bob"])
        assert not _delivery_ok(rel, self.SCENE, "Alice", "Bob", "action",
                                behind_sources=["Bob"])
        # Sound carries into the blind spot -- the rear arc is a visual fact.
        assert _delivery_ok(rel, self.SCENE, "Alice", "Bob", "hearing",
                            behind_sources=["Bob"])

    def test_sight_actually_consults_the_relation(self):
        """The old gate returned True for sight regardless of the relation, so
        a source in another room passed. has_visual is now applied."""
        from agents.common import _delivery_ok
        far = self._rel("r1", "r2")
        assert not _delivery_ok(far, self.SCENE, "Alice", "Carol", "action")

    def test_hearing_applies_the_proximity_downgrade(self):
        """F4: hear_level was called without proximity everywhere, so a mutter
        carried to an arbitrarily large room at full volume."""
        from agents.common import _delivery_ok
        from world.spatial import hear_level
        rel = self._rel()
        assert hear_level(rel, "mutter", proximity="within_reach") != "none"
        assert _delivery_ok(rel, self.SCENE, "Alice", "Bob", "hearing",
                            volume="mutter", proximity="within_reach")
        # Same room, but not within reach: the gate must agree with hear_level
        # rather than deliver regardless.
        assert (_delivery_ok(rel, self.SCENE, "Alice", "Bob", "hearing",
                             volume="mutter", proximity="far")
                == (hear_level(rel, "mutter", proximity="far") != "none"))

    def test_a_source_is_always_delivered_to_itself(self):
        from agents.common import _delivery_ok
        rel = self._rel()
        assert _delivery_ok(rel, self.SCENE, "Alice", "Alice", "sight",
                            behind_sources=["Alice"])


# ---------------------------------------------------------------------------
# F2/P1: Dialogue memory recognition gate
# ---------------------------------------------------------------------------

class TestDialogueMemoryRecognitionGate:
    """Dialogue memories should use appearance-based labels for unrecognized
    speakers instead of canonical names."""

    def test_recognition_gate_in_commit(self):
        """Verify commit.py has the recognition gate code."""
        import inspect
        from persist import commit
        # The gate lives in prepare_memory_commit (commit_memory since the
        # split); the function source survives the move.
        source = inspect.getsource(commit.prepare_memory_commit)
        # The gate should check the hearer's known map
        assert "_hearer_known" in source
        assert "spk_label" in source
        assert "a voice" in source


# ---------------------------------------------------------------------------
# F3 / SEAM 5: Background _present_others recognition gate
# ---------------------------------------------------------------------------

class TestPresentOthersRecognitionGate:
    """_present_others in background.py names the cast for a BACKGROUND
    PRESENCE's payload, so the recognition basis is that presence's own
    entry in the `known` ledger -- not the player's. A presence with no
    entry (the normal case for an unregistered one) recognizes nobody, and
    every cast member renders as an appearance label."""

    def _setup_ctx(self, temp_db, names, known_map=None, positions=None):
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("T", "", time.time()),
        )
        ids = {}
        for n in names:
            sheet = default_character_data(n)
            # A distinctive appearance so the label is checkably that
            # character's. It has to go in embodiment.visible.summary --
            # identity.appearance is not read by character_appearance.
            sheet.setdefault("embodiment", {}).setdefault("visible", {})[
                "summary"] = f"{n}, a wiry person in {n.lower()}-grey."
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
        # Everybody in the taproom unless a case says otherwise: `here` is a
        # room and a body not standing in it is not present.
        rooms = dict(positions or {})
        for n in list(names) + ["The Stranger", "The Barkeep", "The Fiddler"]:
            rooms.setdefault(n, "taproom")
        self.scene = {"rooms": {r: {} for r in set(rooms.values())},
                      "positions": rooms}
        temp_db.wset(chat_id, "scene", self.scene)
        ctx = PipelineContext(
            chat=ChatData(id=chat_id, name="T", persona_id=None, lorebook_id=None,
                          scenario="", created=time.time()),
            turn=TurnData(id=1, chat_id=chat_id, idx=1, player_input="", created=time.time()),
            cast=cast, input="",
        )
        return ctx, ids, chat_id

    def test_presence_with_no_ledger_entry_recognizes_nobody(self, temp_db):
        """The normal case: an unregistered presence has no `known` entry, so
        every cast member -- and the player -- renders as a label."""
        from agents.background import _present_others, _presence_recognizes
        ctx, ids, chat_id = self._setup_ctx(temp_db, ["Alice", "Bob"])

        result = _present_others(
            ctx, self.scene, "taproom",
            _presence_recognizes(ctx, "The Barkeep"))

        assert "Alice" not in result
        assert "Bob" not in result
        assert "The Stranger" not in result
        # Labels, and distinct ones -- two strangers must not collapse into
        # the same phrase (the reason _unknown_actor_label derives from
        # appearance at all).
        assert any("alice-grey" in r for r in result)
        assert any("bob-grey" in r for r in result)
        assert len(set(result)) == len(result)

    def test_presence_uses_its_own_ledger_entry(self, temp_db):
        """A presence that has been introduced to someone may name them."""
        from agents.background import _present_others, _presence_recognizes
        ctx, ids, chat_id = self._setup_ctx(
            temp_db, ["Alice", "Bob"],
            known_map={"The Barkeep": ["Bob"]})

        result = _present_others(
            ctx, self.scene, "taproom",
            _presence_recognizes(ctx, "The Barkeep"))

        assert "Bob" in result
        assert "Alice" not in result

    def test_players_recognition_is_not_the_basis(self, temp_db):
        """The regression this gate was rebuilt for: the player knowing Bob
        says nothing about whether the barkeep does."""
        from agents.background import _present_others, _presence_recognizes
        ctx, ids, chat_id = self._setup_ctx(
            temp_db, ["Alice", "Bob"],
            known_map={"The Stranger": ["Alice", "Bob"]})

        result = _present_others(
            ctx, self.scene, "taproom",
            _presence_recognizes(ctx, "The Barkeep"))

        assert "Alice" not in result
        assert "Bob" not in result

    def test_shared_manager_payload_uses_the_intersection(self, temp_db):
        """scene_life voices several presences from one payload, so a name
        only one of them knows must not be handed to all of them."""
        from agents.background import _present_others, _presence_recognizes
        ctx, ids, chat_id = self._setup_ctx(
            temp_db, ["Alice", "Bob"],
            known_map={"The Barkeep": ["Alice", "Bob"],
                       "The Fiddler": ["Bob"]})

        both = _present_others(
            ctx, self.scene, ["taproom", "taproom"],
            _presence_recognizes(ctx, "The Barkeep", "The Fiddler"))

        assert "Bob" in both
        assert "Alice" not in both

    def test_a_body_in_another_room_is_not_present(self, temp_db):
        """The gate this field never had. A label asserts a body is HERE as
        much as a name does, so "the wiry person in alice-grey" about someone
        in the cellar is the same false claim about presence, made about a
        stranger."""
        from agents.background import _present_others, _presence_recognizes
        ctx, ids, chat_id = self._setup_ctx(
            temp_db, ["Alice", "Bob"], positions={"Alice": "cellar"})

        result = _present_others(
            ctx, self.scene, "taproom",
            _presence_recognizes(ctx, "The Barkeep"))

        assert not any("alice-grey" in r for r in result)
        assert any("bob-grey" in r for r in result)

    def test_a_shared_payload_names_nobody_the_voices_do_not_share(self, temp_db):
        """One context read by every voice in it: annotation cannot stand in
        for non-admission, so a body present to only one of them is present to
        none of them here."""
        from agents.background import _present_others, _presence_recognizes
        ctx, ids, chat_id = self._setup_ctx(temp_db, ["Alice", "Bob"])

        split = _present_others(
            ctx, self.scene, ["taproom", "cellar"],
            _presence_recognizes(ctx, "The Barkeep", "The Fiddler"))

        assert split == []

    def test_an_unplaced_presence_is_told_of_nobody(self, temp_db):
        """Not knowing where a presence stands is a reason to deliver
        nothing, exactly as it is for `_beat_for_presence` and
        `_audience_map`."""
        from agents.background import _present_others, _presence_recognizes
        ctx, ids, chat_id = self._setup_ctx(temp_db, ["Alice", "Bob"])

        assert _present_others(
            ctx, self.scene, None,
            _presence_recognizes(ctx, "The Barkeep")) == []

    def test_player_name_is_gated_too(self, temp_db):
        """The protagonist is not exempt: a presence that has never been
        introduced has no claim on the player's name either."""
        from agents.background import _present_others, _presence_recognizes
        ctx, ids, chat_id = self._setup_ctx(
            temp_db, ["Alice"],
            known_map={"The Barkeep": ["The Stranger"]})

        gated = _present_others(
            ctx, self.scene, "taproom", _presence_recognizes(ctx, "The Fiddler"))
        known = _present_others(
            ctx, self.scene, "taproom", _presence_recognizes(ctx, "The Barkeep"))

        assert "The Stranger" not in gated
        assert "The Stranger" in known

    def test_no_bare_except_swallows_the_gate(self, temp_db):
        """A failing lookup used to degrade the whole cast to "someone" with
        no signal, which reads exactly like a working gate."""
        import inspect
        from agents import background
        source = inspect.getsource(background._present_others)
        assert "except" not in source
        assert "someone" not in source


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

    def test_a_door_to_an_unseen_room_is_withheld(self):
        """This test used to assert the opposite, under the name
        `test_backwards_compatible_no_visible_rooms`: it called
        `_visible_portal_states` without `visible_rooms` and required the door
        to r2 to be INCLUDED. There was never a backwards-compatible caller --
        the one production call site has always passed the set
        (`narration.py:919`) -- so the arm it pinned could only ever be reached
        from this test, and what it pinned was the pre-S3-A5 leak: the state of
        a door into a room the player cannot see."""
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
        assert "door to Room 2" not in _visible_portal_states(
            scene, "r1", {"r1"})
        assert "door to Room 2" in _visible_portal_states(
            scene, "r1", {"r1", "r2"})


# ---------------------------------------------------------------------------
# S3-A8: Entity state blob concealed-actor reconciliation
# ---------------------------------------------------------------------------

class TestEntityStateStalenessSignal:
    """S3-A8 is the stale-posture symptom: a free-text posture/description
    clause copied forward verbatim from the pre-beat blob wins over this
    beat's own prose, because the deterministic layers prefer structured
    truth and _PROTECTED_STATE_KEYS shields those keys from normalization.

    An earlier attempt read this finding as a concealment leak and SKIPPED
    any entity whose JSON contained a concealed actor's name as a substring
    -- so an actor named 'Al' matched 'small' -- dropping the update with
    nothing to re-apply it, which diverged world_entities from the scene
    blob it is a projection of. These tests pin the two properties that
    matter: the row always commits, and the copy-forward is reported.
    """

    def _ctx_and_chat(self, temp_db, prior_entities, diff_entities, prose):
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("T", "", time.time()))
        turn_id = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
            (chat_id, 1, "", time.time()))
        temp_db.wset(chat_id, "scene", {
            "rooms": {}, "positions": {}, "entities": prior_entities,
            "attire": {}, "overlays": {},
        })
        from core.pipeline_context import PipelineContext, ChatData, TurnData
        ctx = PipelineContext(
            chat=ChatData(id=chat_id, name="T", persona_id=None,
                          lorebook_id=None, scenario="", created=time.time()),
            turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                          player_input="", created=time.time()),
            cast=[], input="")
        ctx.director_resolve = {
            "resolved_event": prose,
            "state_diff": {"entities": diff_entities},
        }
        return ctx, chat_id

    def test_entity_still_commits_when_a_concealed_actor_is_named(self, temp_db):
        """The projection must never silently lose a row: world_entities is a
        derived view of the scene commit, and a missing row is durable
        corruption, not a closed leak."""
        from persist import commit
        ctx, chat_id = self._ctx_and_chat(
            temp_db,
            prior_entities={},
            diff_entities={"vial": {"kind": "object", "name": "vial",
                                    "state": {"description": "half empty"}}},
            prose="Mara palms the vial.")
        commit.commit_world_entities(ctx, nonce=0)
        rows = temp_db.q(
            "SELECT entity_id FROM world_entities WHERE chat_id=?", (chat_id,))
        assert [r["entity_id"] for r in rows] == ["vial"]

    def test_copy_forward_of_a_named_entity_is_reported(self, temp_db):
        from persist import commit
        ctx, chat_id = self._ctx_and_chat(
            temp_db,
            prior_entities={"cot": {"kind": "object", "name": "cot",
                                    "state": {"posture": "sprawled across it"}}},
            diff_entities={"cot": {"kind": "object", "name": "cot",
                                   "state": {"posture": "sprawled across it"}}},
            prose="She rises from the cot and crosses the room.")
        commit.commit_world_entities(ctx, nonce=0)
        assert any("S3-A8" in w for w in ctx.warnings), ctx.warnings
        # ...and it still committed.
        rows = temp_db.q(
            "SELECT entity_id FROM world_entities WHERE chat_id=?", (chat_id,))
        assert [r["entity_id"] for r in rows] == ["cot"]

    def test_an_updated_clause_is_not_reported(self, temp_db):
        from persist import commit
        ctx, _ = self._ctx_and_chat(
            temp_db,
            prior_entities={"cot": {"kind": "object", "name": "cot",
                                    "state": {"posture": "sprawled across it"}}},
            diff_entities={"cot": {"kind": "object", "name": "cot",
                                   "state": {"posture": "empty, blanket thrown back"}}},
            prose="She rises from the cot and crosses the room.")
        commit.commit_world_entities(ctx, nonce=0)
        assert not any("S3-A8" in w for w in ctx.warnings), ctx.warnings

    def test_an_entity_this_beat_never_mentions_is_not_reported(self, temp_db):
        """An untouched entity legitimately carries its state forward."""
        from persist import commit
        ctx, _ = self._ctx_and_chat(
            temp_db,
            prior_entities={"lamp": {"kind": "object", "name": "lamp",
                                     "state": {"description": "unlit"}}},
            diff_entities={"lamp": {"kind": "object", "name": "lamp",
                                    "state": {"description": "unlit"}}},
            prose="She rises from the cot and crosses the room.")
        commit.commit_world_entities(ctx, nonce=0)
        assert not any("S3-A8" in w for w in ctx.warnings), ctx.warnings


# ---------------------------------------------------------------------------
# Pattern 4: Omniscient events row per-observer redaction
# ---------------------------------------------------------------------------

SECRET = "the vault code is 4471"


class TestEventsRowPerObserverRedaction:
    """The stored events row is omniscient. Every replay of it into a model
    context must re-apply concealment first, and must do so to the string it
    actually returns -- the first version of this redacted `event` and then
    returned `summary`, so the redaction was thrown away on every real row."""

    def _row(self, temp_db, conceal_from):
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("T", "", time.time()),
        )
        turn_id = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
            (chat_id, 1, "", time.time()),
        )
        temp_db.qi(
            "INSERT INTO events(chat_id,turn_id,content) VALUES(?,?,?)",
            (chat_id, turn_id, json.dumps({
                "turn": 1,
                # Both fields are Director prose written from the omniscient
                # frame; the summary is what every caller actually reads.
                "summary": ("Alice lit the lamp. "
                            "Bob murmured that %s." % SECRET),
                "event": ("Alice lit the lamp. "
                          "Bob murmured that %s to Cara." % SECRET),
                "dialogue_log": [
                    {"speaker": "Bob", "exact_quote": '"%s."' % SECRET,
                     "visibility": "concealed", "conceal_from": conceal_from},
                ],
            })),
        )
        return chat_id

    def test_concealed_from_observer_loses_name_and_quote(self, temp_db):
        """The observer the line was concealed from must get neither the
        concealed speaker's name nor the content of what he said."""
        from story.scene import recent_events_for_observer
        chat_id = self._row(temp_db, ["Alice"])

        results = recent_events_for_observer(chat_id, "Alice", n=5)

        assert len(results) == 1
        text = results[0]
        assert "Bob" not in text
        assert "4471" not in text
        assert SECRET not in text

    def test_entitled_observer_keeps_the_beat(self, temp_db):
        """An observer the line was NOT concealed from is entitled to it --
        redaction must be per-observer, not blanket."""
        from story.scene import recent_events_for_observer
        chat_id = self._row(temp_db, ["Alice"])

        results = recent_events_for_observer(chat_id, "Cara", n=5)

        assert len(results) == 1
        text = results[0]
        assert "Bob" in text
        assert SECRET in text
        assert "Alice lit the lamp" in text

    def test_overt_sentences_survive_for_concealed_observer(self, temp_db):
        """Redaction is sentence-level (D1/D2): what Alice did in the open is
        still hers to remember."""
        from story.scene import recent_events_for_observer
        chat_id = self._row(temp_db, ["Alice"])

        text = recent_events_for_observer(chat_id, "Alice", n=5)[0]

        assert "Alice lit the lamp" in text

    def test_globally_concealed_line_hidden_from_everyone(self, temp_db):
        """An empty conceal_from means concealed from all, so even an
        unnamed observer must not receive it."""
        from story.scene import recent_events_for_observer
        chat_id = self._row(temp_db, [])

        text = recent_events_for_observer(chat_id, "Cara", n=5)[0]

        assert "Bob" not in text
        assert SECRET not in text

    def test_no_observer_is_entitled_to_nothing(self, temp_db):
        """A stage with no vantage (lore routing) gets every concealed entry
        redacted, including ones targeted at a named third party."""
        from story.scene import recent_events_for_observer
        chat_id = self._row(temp_db, ["Alice"])

        text = recent_events_for_observer(chat_id, None, n=5)[0]

        assert "Bob" not in text
        assert SECRET not in text
        assert "Alice lit the lamp" in text

    def test_mapping_recent_events_is_scrubbed(self, temp_db):
        """X18's middle hop: recent_events feeds mapping's search_lore query,
        and mapping is not entitled to the omniscient row."""
        from story.scene import recent_events
        chat_id = self._row(temp_db, ["Alice"])

        results = recent_events(chat_id, n=5)

        assert len(results) == 1
        assert "Bob" not in results[0]
        assert SECRET not in results[0]

    def test_unconcealed_row_is_returned_verbatim(self, temp_db):
        """No concealment, no change: the scrub must not cost ordinary beats
        their text (recent_events' long-standing contract)."""
        from story.scene import recent_events, recent_events_for_observer
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("T", "", time.time()),
        )
        turn_id = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
            (chat_id, 1, "", time.time()),
        )
        temp_db.qi(
            "INSERT INTO events(chat_id,turn_id,content) VALUES(?,?,?)",
            (chat_id, turn_id, json.dumps({
                "summary": "Alice lit the lamp.",
                "event": "Alice lit the lamp in the hall.",
                "dialogue_log": [
                    {"speaker": "Bob", "exact_quote": '"Evening."',
                     "visibility": "overt", "conceal_from": []},
                ],
            })),
        )

        assert recent_events(chat_id, n=5) == ["Alice lit the lamp."]
        assert recent_events_for_observer(
            chat_id, "Alice", n=5) == ["Alice lit the lamp."]


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
