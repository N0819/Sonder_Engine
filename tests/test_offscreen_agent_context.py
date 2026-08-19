"""What an absent mind is allowed to know.

The `character_agent` rung is the highest-fidelity purchase in the off-screen
design and the most dangerous: it lets a character who is nowhere near the
player act on their own initiative. The failure it must not have is named in
the design as the fatal one — "how did he know that" — and its shape is a
villain who reacts before evidence reaches them, in prose that sounds entirely
plausible while doing it.

So the context is built as a STRUCTURE rather than as an instruction, and
these tests are about what is absent.
"""

from __future__ import annotations

import json
import time

import pytest

from world import offscreen


def _subject(state=None, sheet=None):
    return {
        "id": "kestrel_uid",
        "char_id": None,
        "sheet": sheet or {"identity": {"name": "Kestrel", "uid": "kestrel_uid"},
                           "psychology": {"drive": {"essence": "hold the gate"},
                                          "traits": {"wary": 0.8}}},
        "state": state or {},
    }


class TestTheFirewallIsAStructure:
    def test_it_is_an_allowlist_not_a_denylist(self, temp_db):
        """A denylist grows a hole every time the payload gains a key, and the
        hole is silent. The roadmap lists what must be excluded; the way to
        honour a list of exclusions is to never build the thing they would
        have to be removed from."""
        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) "
                         "VALUES(?,?,?)", ("A", "", time.time()))
        ctx = offscreen.agent_context(cid, _subject())
        assert set(ctx) <= set(offscreen.AGENT_CONTEXT_KEYS)

    def test_there_is_no_scene_to_forget_to_leave_out(self):
        """`agent_context` takes no scene parameter at all. A signature that
        cannot receive the objective world cannot leak it."""
        import inspect

        params = inspect.signature(offscreen.agent_context).parameters
        assert "scene" not in params
        assert "player_room" not in params
        # `turn_idx` carries no world content: it is the decay clock for the
        # mind's own hypothesis ledger, nothing more.
        assert set(params) == {"cid", "entry", "frame_id", "clock",
                               "turn_idx"}

    def test_nothing_about_the_player_reaches_it(self, temp_db):
        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) "
                         "VALUES(?,?,?)", ("A", "", time.time()))
        ctx = offscreen.agent_context(cid, _subject())
        blob = json.dumps(ctx).casefold()
        for forbidden in ("player", "position", "scene", "narrat"):
            assert forbidden not in blob

    def test_importance_never_becomes_content(self, temp_db):
        """Distance and importance may select model spend. A character who
        could tell how important they were would be reading the engine rather
        than the world."""
        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) "
                         "VALUES(?,?,?)", ("A", "", time.time()))
        sheet = {"identity": {"name": "Kestrel"},
                 "psychology": {"drive": {}, "traits": {}},
                 "simulation": {"tier": "major", "importance_override": 0.9}}
        ctx = offscreen.agent_context(cid, _subject(sheet=sheet))
        blob = json.dumps(ctx).casefold()
        assert "importance" not in blob and "tier" not in blob


class TestItReceivesWhatItLegitimatelyHas:
    def test_its_own_carried_reports_arrive_already_degraded(self, temp_db):
        """The reports were subtracted at the moment each was heard, so this
        hands over what the character BELIEVES rather than what is true."""
        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) "
                         "VALUES(?,?,?)", ("A", "", time.time()))
        heard = {"world_event_id": "e1", "retellings": 2, "told_by": "Rem",
                 "claim": "a stranger barred the gate in some place"}
        ctx = offscreen.agent_context(cid, _subject(state={
            "carried_reports": [heard]}))
        assert ctx["carried_reports"] == [heard]

    def test_it_gets_its_own_drive_and_beliefs(self, temp_db):
        """Beliefs live where `commit_memory` writes them --
        `state["interior"]["beliefs"]`, a list of belief records. This test
        used to assert a top-level `state["beliefs"]` no writer has ever
        produced, so the allowlist field documented as "what they think is
        true, including wrongly" was `{}` on every paid tick. Measured live:
        0 of 100 `chat_chars` rows carry the top-level key, 31 carry the
        interior one."""
        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) "
                         "VALUES(?,?,?)", ("A", "", time.time()))
        held = [{"belief": "the gate still holds", "confidence": 0.8}]
        ctx = offscreen.agent_context(cid, _subject(state={
            "interior": {"beliefs": held}}))
        assert ctx["drive"]["essence"] == "hold the gate"
        assert ctx["beliefs"] == held

    def test_a_mind_with_nothing_gets_an_empty_context_not_an_error(self,
                                                                   temp_db):
        """An absent character with no memories, no plans and no reports is
        the ordinary case, not an exception. Failing here would make the rung
        unreachable for exactly the characters it is cheapest to run."""
        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) "
                         "VALUES(?,?,?)", ("A", "", time.time()))
        ctx = offscreen.agent_context(cid, _subject())
        assert ctx["memories"] == [] and ctx["plans"] == []
        assert ctx["carried_reports"] == []

    def test_a_real_char_id_reaches_real_memory_rows(self, temp_db):
        """The memory read shipped selecting a `summary` column the memories
        table has never had, and every test exercised it with char_id=None —
        so the query that crashed on any real candidate looked covered and
        was not. The paid producer's first live run would have been the
        crash's first exercise."""
        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) "
                         "VALUES(?,?,?)", ("A", "", time.time()))
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created) "
            "VALUES(?,?,?,?)", ("Kestrel", "{}", "{}", time.time()))
        temp_db.qi(
            "INSERT INTO memories(chat_id,char_id,turn_idx,content) "
            "VALUES(?,?,?,?)", (cid, char_id, 3, "the gate held"))
        temp_db.qi(
            "INSERT INTO memories(chat_id,char_id,turn_idx,content,archived) "
            "VALUES(?,?,?,?,1)", (cid, char_id, 4, "an archived aside"))
        entry = _subject()
        entry["char_id"] = char_id
        ctx = offscreen.agent_context(cid, entry)
        assert ctx["memories"] == [{"summary": "the gate held",
                                    "turn_idx": 3}]


class TestSelectionStaysSeparateFromContent:
    def test_candidates_are_chosen_without_reading_the_world(self):
        """`full_agent_candidates` already documents this; it is asserted here
        because the producer is the step that would be tempted to pass the
        scene along for convenience."""
        import inspect

        params = inspect.signature(offscreen.full_agent_candidates).parameters
        assert "scene" not in params and "player_room" not in params
        # And the body reads only the character's own rows, never the turn.
        body = inspect.getsource(offscreen.full_agent_candidates)
        body = body[body.index('"""', body.index('"""') + 3) + 3:]
        assert "scene" not in body and "director" not in body


class TestItsOwnTheoryOfOtherMindsTravels:
    """`state["mind_models"]` is this mind's own model of other minds — every
    hypothesis in it was formed on this mind's own firewalled turns
    (`apply_mind_model_updates` is the only writer), so handing it back to the
    same mind opens no channel between minds. Withholding it made the absent
    mind conclude LESS than its own evidence supports, which is the one repair
    the firewall's doctrine forbids. What travels is the DERIVED view the
    on-screen step already hands the same mind — decay-applied, claim and
    current confidence only — never the raw ledger with its engine
    bookkeeping. Argument: docs/design/DESIGN_OFFSCREEN_MIND_MODELS.md."""

    def _cid(self, db):
        return db.qi("INSERT INTO chats(name,scenario,created) "
                     "VALUES(?,?,?)", ("A", "", time.time()))

    def test_the_derived_view_travels_not_the_raw_ledger(self, temp_db):
        cid = self._cid(temp_db)
        raw = {"Rem": {"last_updated_turn": 10, "hypotheses": [
            {"about_entity": "Rem", "kind": "goal",
             "claim": "Rem means to force the gate", "confidence": 0.6,
             "last_updated_turn": 10, "first_seen_turn": 3,
             "formed_under": {"absorption": 0.5, "turn": 3}},
            {"about_entity": "Rem", "kind": "goal",
             "claim": "Rem is only passing through", "confidence": 0.3,
             "last_updated_turn": 10},
        ]}}
        ctx = offscreen.agent_context(
            cid, _subject(state={"mind_models": raw}), turn_idx=10)
        goal = ctx["mind_models"]["Rem"]["goal"]
        assert goal["leading"]["claim"] == "Rem means to force the gate"
        assert [c["claim"] for c in goal["competitors"]] == \
            ["Rem is only passing through"]
        # The ledger's bookkeeping is the ENGINE's, not theirs: a mind that
        # could read when it formed a belief, or under what absorption, would
        # be reading the engine rather than the world.
        blob = json.dumps(ctx)
        for bookkeeping in ("last_updated_turn", "first_seen_turn",
                            "formed_under", "hypotheses"):
            assert bookkeeping not in blob

    def test_conviction_arrives_as_it_stands_now_not_at_peak(self, temp_db):
        """An off-screen tick is exactly the moment the most time has passed,
        so an undecayed confidence would hand the mind its conviction as it
        stood when formed rather than as it stands now."""
        cid = self._cid(temp_db)
        raw = {"Rem": {"hypotheses": [
            {"kind": "emotion", "claim": "Rem is frightened",
             "confidence": 0.8, "last_updated_turn": 0}]}}
        ctx = offscreen.agent_context(
            cid, _subject(state={"mind_models": raw}), turn_idx=60)
        leading = ctx["mind_models"]["Rem"]["emotion"]["leading"]
        assert leading["confidence"] < 0.05
        # Display never mutates storage.
        assert raw["Rem"]["hypotheses"][0]["confidence"] == 0.8

    def test_a_masked_native_of_the_frame_does_not_travel(self, temp_db):
        """The nonexistent_cast recognition backstop, applied at the same
        boundary the on-screen step applies it: in a frame where a cast
        member does not yet exist, a native must not be handed back a model
        keyed to that identity — while a stranger-shaped key (no cast member
        anywhere) rides as itself."""
        from core.frames import create_frame

        cid = self._cid(temp_db)
        hid = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created) "
            "VALUES(?,?,?,?)",
            ("Hinami", json.dumps({"identity": {"name": "Hinami"}}), "{}",
             time.time()))
        temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
                   "VALUES(?,?,?,?)", (cid, hid, "dormant", "{}"))
        fid = create_frame(cid, label="Before her", ordinal=-1, kind="past",
                           nonexistent_cast=[hid])
        hyp = [{"kind": "trait", "claim": "sharp-eyed", "confidence": 0.4,
                "last_updated_turn": 1}]
        raw = {"Hinami": {"hypotheses": list(hyp)},
               "the fox woman": {"hypotheses": list(hyp)}}
        ctx = offscreen.agent_context(
            cid, _subject(state={"mind_models": raw}), frame_id=fid,
            turn_idx=1)
        assert "Hinami" not in ctx["mind_models"]
        assert "the fox woman" in ctx["mind_models"]

    def test_its_model_of_the_player_is_its_own_state(self, temp_db):
        """test_nothing_about_the_player_reaches_it above bars the PLAYER'S
        side — position, recent action, the turn feed — and still holds: the
        signature cannot receive any of it. The mind's own model OF the
        player was formed from what it perceived and is its own state; the
        distance between the two stays real precisely because this model can
        be wrong."""
        cid = self._cid(temp_db)
        raw = {"player": {"hypotheses": [
            {"kind": "goal", "claim": "means to leave without paying",
             "confidence": 0.5, "last_updated_turn": 2}]}}
        ctx = offscreen.agent_context(
            cid, _subject(state={"mind_models": raw}), turn_idx=2)
        assert ctx["mind_models"]["player"]["goal"]["leading"]["claim"] == \
            "means to leave without paying"
