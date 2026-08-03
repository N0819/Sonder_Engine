"""Somebody asked you something. You are allowed to refuse; you are not allowed
to not notice.

Live, chat 38 t144–t147. The player stayed silent for four turns so the Doctor
and Tamamo could talk to each other. Tamamo put a direct request to the Doctor
on three consecutive beats — "tell me yourself, what purpose brings...",
"Doctor, describe its dimensional nature in your own terms", "Name one way its
dimensions interface with established boundaries" — and on the last two he said
nothing at all.

His own reasoning is on the record and nothing about it is broken. He KNEW
about the question: it is in his `observations_used`, recalled from memory. He
weighed answering — "offer one terse clarifying remark on the TARDIS if the
silence stretches" — and rejected it at inhibition 0.4 with the norm conflict
"shrine etiquette favors waiting rather than filling silence". He selected
"remain silent and observant to honor etiquette and give Tamamo room to
respond", expecting that it "allows Tamamo to speak next".

Both characters were waiting for the other. Tamamo filled the gap with more
questions and by turning back to the player who had deliberately stepped out.

Two things were missing, and the engine had both:

1. Nothing told a character that a question was outstanding and it was theirs.
   `interaction.expects_response` is written by every character result and was
   consumed in exactly one place — `_recent_self_moves`, as `expected_answer`,
   which tells a character *I* asked something.
2. Order. Once the player was silent, the queue fell back to cast-registration
   order, so the Doctor opened every beat — speaking before Tamamo asked, every
   time, so his line could never be the answer.
"""

from __future__ import annotations

import json
import time

from agents.character import _player_quiet_beats, _unanswered_question_note


def _seed(temp_db, turns):
    """turns: [(idx, player_speech, {char_id: result})]"""
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)", ("T", "", 0.0))
    for idx, speech, results in turns:
        tid = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
            (chat_id, idx, "", time.time()))
        for key, content in (
            ("director_interpret", {"speech": speech}),
            ("interaction_loop", {"character_results": results}),
        ):
            sid = temp_db.qi(
                "INSERT INTO steps(turn_id,key,label,ord,stale) VALUES(?,?,?,?,0)",
                (tid, key, key, 0))
            temp_db.qi(
                "INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
                (sid, json.dumps(content), time.time()))
    return chat_id


def _asked(name, line, addresses):
    return {"name": name,
            "sequence": [{"type": "speech", "text": line}],
            "interaction": {"expects_response": True, "addresses": addresses}}


def _said(name, line):
    return {"name": name,
            "sequence": [{"type": "speech", "text": line}],
            "interaction": {"expects_response": False, "addresses": []}}


class TestTheLiveFailure:
    def test_the_ignored_request_is_surfaced(self, temp_db):
        chat_id = _seed(temp_db, [
            (145, "", {"41": _asked(
                "Tamamo", "Doctor, describe its dimensional nature in your own terms.",
                ["The Doctor"])}),
        ])
        note = _unanswered_question_note(chat_id, "The Doctor", 146, None)
        owed = note["awaiting_your_answer"]
        assert owed["from"] == "Tamamo"
        assert "dimensional nature" in owed["asked"]
        assert owed["turns_ago"] == 1

    def test_an_imperative_counts_and_a_question_mark_is_not_required(self, temp_db):
        """Every ask in the live case was an imperative — "describe...", "Name
        one way..." — so punctuation would have missed all of them. The engine's
        own `expects_response` is the test."""
        chat_id = _seed(temp_db, [
            (146, "", {"41": _asked(
                "Tamamo", "Name one way its dimensions interface with boundaries.",
                ["The Doctor"])}),
        ])
        assert "?" not in _unanswered_question_note(
            chat_id, "The Doctor", 147, None)["awaiting_your_answer"]["asked"]

    def test_speaking_clears_the_debt(self, temp_db):
        """Whether the reply was responsive is the asker's business, not a
        field's — having spoken is enough."""
        chat_id = _seed(temp_db, [
            (145, "", {"41": _asked("Tamamo", "Describe it.", ["The Doctor"])}),
            (146, "", {"35": _said("The Doctor", "It is only a machine.")}),
        ])
        assert _unanswered_question_note(chat_id, "The Doctor", 147, None) == {}

    def test_the_asker_owes_nothing(self, temp_db):
        chat_id = _seed(temp_db, [
            (145, "", {"41": _asked("Tamamo", "Describe it.", ["The Doctor"])}),
        ])
        assert _unanswered_question_note(chat_id, "Tamamo", 146, None) == {}

    def test_a_question_to_somebody_else_is_not_yours(self, temp_db):
        chat_id = _seed(temp_db, [
            (145, "", {"41": _asked("Tamamo", "Hinami, will you stay?", ["Hinami"])}),
        ])
        assert _unanswered_question_note(chat_id, "The Doctor", 146, None) == {}

    def test_a_statement_is_not_a_debt(self, temp_db):
        chat_id = _seed(temp_db, [
            (145, "", {"41": _said("Tamamo", "Your words are noted, Doctor.")}),
        ])
        assert _unanswered_question_note(chat_id, "The Doctor", 146, None) == {}

    def test_it_does_not_reach_back_forever(self, temp_db):
        """Three beats. A question nobody has picked up in that long has been
        dropped by the scene, and re-raising it is its own kind of stall."""
        chat_id = _seed(temp_db, [
            (140, "", {"41": _asked("Tamamo", "Describe it.", ["The Doctor"])}),
        ])
        assert _unanswered_question_note(chat_id, "The Doctor", 147, None) == {}


class TestThePlayerAskingCountsToo:
    """The larger half, and the one the character-result path could never see:
    the player has no character result, so `expects_response` does not exist
    for them. 809 beats in the stored corpus carry player speech aimed at a
    named character; 363 of those contain a question."""

    def _seed_player_ask(self, temp_db, speech, addressed):
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)", ("T", "", 0.0))
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,created) VALUES(?,?,?)",
            ("The Doctor", json.dumps({"identity": {"name": "The Doctor"}}), 0.0))
        temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
                   (chat_id, char_id, "active", "{}"))
        tid = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
            (chat_id, 145, "", time.time()))
        sid = temp_db.qi(
            "INSERT INTO steps(turn_id,key,label,ord,stale) VALUES(?,?,?,?,0)",
            (tid, "director_interpret", "d", 0))
        temp_db.qi(
            "INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
            (sid, json.dumps({"speech": speech,
                              "flow": {"addressed_to": [addressed(char_id)]}}),
             time.time()))
        return chat_id

    def test_a_question_from_the_player_is_surfaced(self, temp_db):
        chat_id = self._seed_player_ask(
            temp_db, "So what is that box of yours, really?", lambda cid: cid)
        owed = _unanswered_question_note(
            chat_id, "The Doctor", 146, None)["awaiting_your_answer"]
        assert owed["from"] == "the player"
        assert "box of yours" in owed["asked"]

    def test_addressed_to_resolves_by_name_as_well_as_id(self, temp_db):
        chat_id = self._seed_player_ask(
            temp_db, "What is it?", lambda cid: "The Doctor")
        assert _unanswered_question_note(
            chat_id, "The Doctor", 146, None)["awaiting_your_answer"]

    def test_a_statement_from_the_player_is_not_a_debt(self, temp_db):
        chat_id = self._seed_player_ask(
            temp_db, "That box of yours is strange.", lambda cid: cid)
        assert _unanswered_question_note(chat_id, "The Doctor", 146, None) == {}

    def test_a_question_aimed_at_somebody_else_is_not_yours(self, temp_db):
        chat_id = self._seed_player_ask(
            temp_db, "What is it?", lambda cid: "Tamamo")
        assert _unanswered_question_note(chat_id, "The Doctor", 146, None) == {}


class TestSustainedSilenceIsADifferentEvent:
    """One quiet beat is something the player just did. Four in a row is
    somebody who has stepped back — and reading it afresh each beat is what
    produced "Hinami, you have gone quiet after such proud words" followed by
    "Hinami, your presence here is a quiet joy"."""

    def test_one_quiet_beat_counts_as_one(self, temp_db):
        chat_id = _seed(temp_db, [(144, "I was being polite.", {})])
        assert _player_quiet_beats(chat_id, 145, None, None) == 1

    def test_consecutive_silence_accumulates(self, temp_db):
        chat_id = _seed(temp_db, [(144, "", {}), (145, "", {}), (146, "", {})])
        assert _player_quiet_beats(chat_id, 147, None, None) == 4

    def test_speech_resets_the_run(self, temp_db):
        chat_id = _seed(temp_db, [(144, "", {}), (145, "Still here.", {}),
                                  (146, "", {})])
        assert _player_quiet_beats(chat_id, 147, None, None) == 2

    def test_the_note_only_carries_the_count_once_it_means_something(self):
        """A run of one is the ordinary case the existing field already
        covers, so it adds nothing."""
        import inspect

        from agents import character

        src = inspect.getsource(character._player_silence_note)
        assert "if quiet_beats > 1:" in src


class TestWhoeverOwesAnAnswerHasTheFloor:
    def test_the_loop_orders_on_it(self):
        import inspect

        from agents import loops

        src = inspect.getsource(loops.interaction_loop)
        assert "_unanswered_question_note(" in src
        order = src.index("_owes = []")
        assert src.index("addressed = normalize_character_refs") < order, (
            "the debt sort must run after the address sort, so it wins")

    def test_it_is_derived_not_declared(self):
        """The Director cannot see this better than the record can:
        `expects_response` and `addresses` are already written by the character
        who asked. A second spelling of one fact drifts and then disagrees."""
        import inspect

        from agents import loops

        src = inspect.getsource(loops.interaction_loop)
        assert "second spelling of one fact" in src


def test_the_prompt_says_what_both_fields_mean():
    from prompts import get_prompt

    text = get_prompt("character")
    assert "awaiting_your_answer" in text
    assert "player_quiet_for_beats" in text
    # Noticing is required; answering is not.
    assert "not obliged to answer" in text
