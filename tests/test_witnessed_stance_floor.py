"""A registered mind's stances move on the evidence it was delivered.

Review 2026-09-07 D21. A charter body moved five axes deterministically from
the speech-act kinds it witnessed; a registered character moved only when the
model chose to emit `relationship_updates`, so promoting a body stopped it
obeying the rules that formed it. The floor built for that item applies
`charter_social.DEFAULT_SIGNALS` -- the same table, the same diminishing
returns -- to the graph a registered mind keeps, once per beat, citing the
observation id it read.

The firewall rule the owner approved it under is the adversarial test in this
file: the source set is the mind's OWN delivered observations, never another
observer's reception answer, so a stance may not move on an observation this
mind was never handed.

Measured on the town bench (chat 114, sanitized copy) while this was written:
across its thirteen resolved beats the grounded `public_evidence` carries
three `praise`, two `apology` and one `thanks` -- six acts the floor now
reads, and on the one that ran both ways (turn 3, the persona thanking the
Doctor) the quote is present in char 58's composed view and absent from the
persona's own, which is exactly the delivery split this floor is keyed on.
"""

from __future__ import annotations

import time

import pytest

from mind.memory import (apply_relationship_updates, apply_witnessed_signals,
                         get_relationships, relationship_history)
from persist.commit import _witnessed_signals
from world.charter import DEFAULT_SIGNALS, signal_landing


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Floor", "", time.time()))


def _apply(cid, char_id, turn_idx, witnessed):
    return apply_witnessed_signals(cid, char_id, turn_idx, witnessed,
                                   frame_id=None)


SPEECH = {
    "source_id": "speech:Mora:0",
    "kind": "speech",
    "actor": "Mora",
    "exact_quote": '"You did that well. Better than I would have."',
    "speech_acts": [{"kind": "praise", "content": "You did that well."}],
}


class TestDeliveryDecidesTheSourceSet:
    def test_a_stance_moves_on_a_line_this_mind_was_delivered(self):
        view = ("Mora says, “You did that well. Better than I would "
                "have.”")
        assert _witnessed_signals([SPEECH], view, "Ilsa", {"Mora"}) == [
            {"subject": "Mora", "signal": "praise",
             "source_id": "speech:Mora:0"}]

    def test_a_stance_does_not_move_on_an_observation_never_delivered(self):
        """The adversarial half of the ruling: one observer's gate must never
        decide another's. The same beat, the same evidence, a mind whose own
        view does not carry the line."""
        elsewhere = "You are alone in the stairwell. A door closes below."
        assert _witnessed_signals([SPEECH], elsewhere, "Ilsa",
                                  {"Mora"}) == []

    def test_a_mind_forms_no_stance_about_itself(self):
        view = "You say, “You did that well. Better than I would have.”"
        assert _witnessed_signals([SPEECH], view, "Mora", {"Mora"}) == []

    def test_a_body_this_mind_cannot_name_moves_nothing(self):
        """The stance store is keyed by canonical name and
        `relationships_for_payload` hands those keys to the mind, so a floor
        that opened a row for an unrecognised speaker would tell the
        character a name they only heard in the dark."""
        view = ("Mora says, “You did that well. Better than I would "
                "have.”")
        assert _witnessed_signals([SPEECH], view, "Ilsa", set()) == []

    def test_an_act_carrying_no_signal_is_not_evidence(self):
        row = {**SPEECH, "speech_acts": [{"kind": "question",
                                          "content": "You did that well."}]}
        view = ("Mora says, “You did that well. Better than I would "
                "have.”")
        assert _witnessed_signals([row], view, "Ilsa", {"Mora"}) == []

    def test_a_communication_row_is_proved_by_its_own_surface(self):
        row = {"source_id": "communication:Mora:0", "kind": "communication",
               "actor": "Mora", "surface": "warns about the flooded shaft",
               "speech_acts": [{"kind": "warning",
                                "content": "the flooded shaft"}]}
        view = "Mora warns about the flooded shaft."
        assert _witnessed_signals([row], view, "Ilsa", {"Mora"}) == [
            {"subject": "Mora", "signal": "warning",
             "source_id": "communication:Mora:0"}]

    def test_a_communication_content_string_is_not_a_delivery_proof(self):
        """Review 2026-09-07 D21 rework. `communication_surface` renders
        `f"{verb} {content}"` and the verb is never empty, so a row's
        `speech_acts` content is always a strict substring of its surface: as
        a span it proves no delivery the surface does not, and only loosens
        the match into hitting a view for an unrelated reason.

        This is exactly `agents.composer.communication_percept`'s partial-
        hearing branch, which replaces the surface with "speaks indistinctly"
        because partial hearing cannot deliver a proposition whose words were
        never specified. The content span re-admitted the proposition and
        landed the largest row in DEFAULT_SIGNALS on a mind that was told only
        that somebody spoke."""
        row = {"source_id": "communication:Vek:0", "kind": "communication",
               "actor": "Vek", "surface": "threatens the courier",
               "speech_acts": [{"kind": "threat",
                                "content": "the courier"}]}
        partial = ("Vek speaks indistinctly. Across the yard the courier "
                   "waits by the gate.")
        assert _witnessed_signals([row], partial, "Ilsa", {"Vek"}) == []


class TestTheFloorIsTheSameArithmeticAsACharterBodys:
    def test_the_movement_is_the_shared_signal_table(self, temp_db):
        cid = _chat(temp_db)
        moved = _apply(cid, 7, 3, [{"subject": "Mora", "signal": "praise",
                                    "source_id": "speech:Mora:0"}])
        expected = signal_landing("praise", {axis: 0.0 for axis in
                                             DEFAULT_SIGNALS["praise"]})
        assert {m["axis"]: m["delta"] for m in moved} == expected
        rel = get_relationships(cid, 7).get("Mora")
        assert rel.emotional_valence == pytest.approx(expected["warmth"])
        assert rel.respect == pytest.approx(expected["respect"])

    def test_repeated_evidence_lands_less_each_time(self, temp_db):
        """`_room`: the fiftieth time somebody helps you is not worth what the
        first was, and the floor inherits that rather than re-deriving it."""
        cid = _chat(temp_db)
        first = _apply(cid, 7, 1, [{"subject": "Mora", "signal": "praise",
                                    "source_id": "speech:Mora:0"}])
        second = _apply(cid, 7, 2, [{"subject": "Mora", "signal": "praise",
                                     "source_id": "speech:Mora:1"}])
        warmth = {m["axis"]: m["delta"] for m in first}["warmth"]
        warmth_again = {m["axis"]: m["delta"] for m in second}["warmth"]
        assert 0 < warmth_again < warmth

    def test_every_movement_cites_the_observation_it_read(self, temp_db):
        cid = _chat(temp_db)
        _apply(cid, 7, 3, [{"subject": "Mora", "signal": "threat",
                            "source_id": "speech:Mora:2"}])
        rows = relationship_history(cid, 7, "Mora")
        assert rows, "the floor recorded nothing"
        assert {r["provenance"] for r in rows} == {"witnessed"}
        assert {r["triggers"] for r in rows} == {"speech:Mora:2"}
        assert {r["note"] for r in rows} == {"threat"}
        assert {r["axis"] for r in rows} == set(DEFAULT_SIGNALS["threat"])

    def test_the_same_beat_committed_twice_moves_a_stance_once(self, temp_db):
        cid = _chat(temp_db)
        item = [{"subject": "Mora", "signal": "insult",
                 "source_id": "speech:Mora:0"}]
        _apply(cid, 7, 5, item)
        before = get_relationships(cid, 7).get("Mora").emotional_valence
        assert _apply(cid, 7, 5, item) == []
        assert get_relationships(cid, 7).get("Mora").emotional_valence == before

    def test_the_floor_moves_from_where_the_model_left_the_stance(
            self, temp_db):
        """Ordering, which is the whole of why this runs after the ops: the
        declared movement is applied first and the floor's diminishing
        returns are measured against it, never the other way round."""
        cid = _chat(temp_db)
        apply_relationship_updates(cid, 7, 4, [{
            "target_entity": "Mora", "warmth_delta": 0.2,
            "trigger_event_ids": ["ev:she-came-back"]}])
        moved = _apply(cid, 7, 4, [{"subject": "Mora", "signal": "praise",
                                    "source_id": "speech:Mora:0"}])
        warmth = {m["axis"]: m["delta"] for m in moved}["warmth"]
        fresh = signal_landing("praise", {"warmth": 0.0})["warmth"]
        assert 0 < warmth < fresh
        rel = get_relationships(cid, 7).get("Mora")
        assert rel.emotional_valence == pytest.approx(0.2 + warmth)

    def test_a_declared_reason_survives_the_floor(self, temp_db):
        """`salient_event` is the model's own sentence about why a stance
        moved; a deterministic floor overwriting it would erase the history
        `apply_relationship_updates` takes care not to erase."""
        cid = _chat(temp_db)
        apply_relationship_updates(cid, 7, 4, [{
            "target_entity": "Mora", "trust_delta": -0.2,
            "trigger_event_ids": ["ev:she-lied"]}])
        _apply(cid, 7, 4, [{"subject": "Mora", "signal": "thanks",
                            "source_id": "speech:Mora:0"}])
        assert get_relationships(cid, 7).get("Mora").salient_event \
            == "ev:she-lied"


class TestTheFloorReachesTheCommit:
    """End to end through `commit_memories`, because the whole point of the
    item is that this happens without a model emitting anything: the beat
    below carries no `relationship_updates` at all."""

    _QUOTE = '"You are a liar and a poor one."'

    def _story(self, temp_db):
        import json
        from story.character_schema import default_character_data
        from core.pipeline_context import ChatData, PipelineContext, TurnData
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Floor", "", time.time()))
        ids = {}
        for name in ("Lisenne Corvay", "Verrin Sault", "Ivo Sarn"):
            sheet = default_character_data(name)
            char_id = temp_db.qi(
                "INSERT INTO characters(name,sheet,source,created,"
                "resource_uid) VALUES(?,?,?,?,?)",
                (name, json.dumps(sheet), "{}", time.time(), "uid_" + name))
            temp_db.qi(
                "INSERT INTO chat_chars(chat_id,char_id,status,state) "
                "VALUES(?,?,?,?)", (chat_id, char_id, "active", "{}"))
            ids[name] = char_id
        temp_db.wset(chat_id, "scene", {
            "rooms": {"gallery": {"name": "The Gallery"}},
            "positions": {name: "gallery" for name in ids},
            "entities": {}, "attire": {}, "overlays": {}})
        temp_db.wset(chat_id, "known", {
            name: [other for other in ids if other != name] for name in ids})
        turn_id = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) "
            "VALUES(?,?,?,?)", (chat_id, 2, "", time.time()))
        cast = temp_db.q(
            "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
            "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
            (chat_id,))
        ctx = PipelineContext(
            chat=ChatData(id=chat_id, name="Floor", persona_id=None,
                          lorebook_id=None, scenario="", created=time.time()),
            turn=TurnData(id=turn_id, chat_id=chat_id, idx=2,
                          player_input="", created=time.time()),
            cast=cast, input="")
        ctx.director_resolve = {
            "summary": "An insult, in front of one witness.",
            "resolved_event": "Verrin speaks.",
            "dialogue_log": [{"speaker": "Verrin Sault",
                              "exact_quote": self._QUOTE, "volume": "normal",
                              "intended_target": "Ivo Sarn", "tone": ""}],
            "public_evidence": [{
                "source_id": "speech:Verrin Sault:0", "kind": "speech",
                "actor": "Verrin Sault", "exact_quote": self._QUOTE,
                "target": "Ivo Sarn",
                "speech_acts": [{"kind": "insult",
                                 "content": "You are a liar"}]}],
        }
        # Ivo is the man it was aimed at and hears it; Lisenne is across the
        # room and this beat's view does not carry the line.
        ctx.perception_outcome = {"views": {
            str(ids["Verrin Sault"]): "You say your piece.",
            str(ids["Ivo Sarn"]): f"Verrin Sault says: {self._QUOTE}",
            str(ids["Lisenne Corvay"]):
                "Across the gallery someone is speaking, too far to hear.",
        }}
        return ctx, ids

    def _commit(self, monkeypatch, ctx):
        def fake_add_memories_batch(memories=None, *, prepared_batch=None):
            batch = (memories if memories is not None
                     else prepared_batch["prepared"])
            return list(range(1, len(batch) + 1))

        # The DEFINING module: `commit_memories` resolves both names in
        # `commit_memory_write`'s own globals since the split, so a patch on
        # the re-exporting module would be silently inert.
        from persist import commit_memory_write
        monkeypatch.setattr(commit_memory_write, "add_memories_batch",
                            fake_add_memories_batch)
        monkeypatch.setattr(commit_memory_write,
                            "maybe_consolidate_character_memory",
                            lambda *a, **k: None)
        from persist.commit import commit_memories
        commit_memories(ctx, nonce=0)

    def test_the_addressee_moves_and_the_body_who_never_heard_does_not(
            self, temp_db, monkeypatch):
        ctx, ids = self._story(temp_db)
        self._commit(monkeypatch, ctx)
        cid = ctx.chat.id

        heard = relationship_history(cid, ids["Ivo Sarn"], "Verrin Sault")
        assert [(r["axis"], r["provenance"], r["triggers"]) for r in heard] \
            == [("warmth", "witnessed", "speech:Verrin Sault:0"),
                ("respect", "witnessed", "speech:Verrin Sault:0")]
        rel = get_relationships(cid, ids["Ivo Sarn"]).get("Verrin Sault")
        assert rel.emotional_valence < 0 and rel.respect < 0

        assert relationship_history(
            cid, ids["Lisenne Corvay"], "Verrin Sault") == []
        assert get_relationships(
            cid, ids["Lisenne Corvay"]).get("Verrin Sault") is None
        # And the speaker forms no stance about himself.
        assert get_relationships(
            cid, ids["Verrin Sault"]).get("Verrin Sault") is None
