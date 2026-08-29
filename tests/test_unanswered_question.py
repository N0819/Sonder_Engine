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


CAST = ("The Doctor", "Tamamo", "Hinami")


def _seed(temp_db, turns):
    """turns: [(idx, player_speech, {char_id: result})]

    Everybody is in one room and hears everything: each beat's composed view
    carries every line spoken on it, for every mind. That is the case these
    tests are about — what a mind does with a question it RECEIVED. The
    undelivered case has a class of its own, below.
    """
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)", ("T", "", 0.0))
    ids = {}
    for name in CAST:
        ids[name] = temp_db.qi(
            "INSERT INTO characters(name,sheet,created) VALUES(?,?,?)",
            (name, json.dumps({"identity": {"name": name}}), 0.0))
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
            (chat_id, ids[name], "active", "{}"))
    for idx, speech, results in turns:
        tid = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
            (chat_id, idx, "", time.time()))
        heard = [speech] + [element.get("text")
                            for result in results.values()
                            for element in (result.get("sequence") or [])
                            if element.get("type") == "speech"]
        view = "\n".join(line for line in heard if line)
        for key, content in (
            ("director_interpret", {"speech": speech}),
            ("interaction_loop", {"character_results": results}),
            ("perception_outcome",
             {"views": {str(cid): view for cid in ids.values()}}),
        ):
            sid = temp_db.qi(
                "INSERT INTO steps(turn_id,key,label,ord,stale) VALUES(?,?,?,?,0)",
                (tid, key, key, 0))
            temp_db.qi(
                "INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
                (sid, json.dumps(content), time.time()))
    return chat_id, ids


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
        chat_id, ids = _seed(temp_db, [
            (145, "", {"41": _asked(
                "Tamamo", "Doctor, describe its dimensional nature in your own terms.",
                ["The Doctor"])}),
        ])
        note = _unanswered_question_note(
            chat_id, "The Doctor", ids["The Doctor"], 146, None)
        owed = note["awaiting_your_answer"]
        assert owed["from"] == "Tamamo"
        assert "dimensional nature" in owed["asked"]
        assert owed["turns_ago"] == 1

    def test_an_imperative_counts_and_a_question_mark_is_not_required(self, temp_db):
        """Every ask in the live case was an imperative — "describe...", "Name
        one way..." — so punctuation would have missed all of them. The engine's
        own `expects_response` is the test."""
        chat_id, ids = _seed(temp_db, [
            (146, "", {"41": _asked(
                "Tamamo", "Name one way its dimensions interface with boundaries.",
                ["The Doctor"])}),
        ])
        assert "?" not in _unanswered_question_note(
            chat_id, "The Doctor", ids["The Doctor"], 147,
            None)["awaiting_your_answer"]["asked"]

    def test_speaking_clears_the_debt(self, temp_db):
        """Whether the reply was responsive is the asker's business, not a
        field's — having spoken is enough."""
        chat_id, ids = _seed(temp_db, [
            (145, "", {"41": _asked("Tamamo", "Describe it.", ["The Doctor"])}),
            (146, "", {"35": _said("The Doctor", "It is only a machine.")}),
        ])
        assert _unanswered_question_note(
            chat_id, "The Doctor", ids["The Doctor"], 147, None) == {}

    def test_the_asker_owes_nothing(self, temp_db):
        chat_id, ids = _seed(temp_db, [
            (145, "", {"41": _asked("Tamamo", "Describe it.", ["The Doctor"])}),
        ])
        assert _unanswered_question_note(
            chat_id, "Tamamo", ids["Tamamo"], 146, None) == {}

    def test_a_question_to_somebody_else_is_not_yours(self, temp_db):
        chat_id, ids = _seed(temp_db, [
            (145, "", {"41": _asked("Tamamo", "Hinami, will you stay?", ["Hinami"])}),
        ])
        assert _unanswered_question_note(
            chat_id, "The Doctor", ids["The Doctor"], 146, None) == {}

    def test_a_statement_is_not_a_debt(self, temp_db):
        chat_id, ids = _seed(temp_db, [
            (145, "", {"41": _said("Tamamo", "Your words are noted, Doctor.")}),
        ])
        assert _unanswered_question_note(
            chat_id, "The Doctor", ids["The Doctor"], 146, None) == {}

    def test_it_does_not_reach_back_forever(self, temp_db):
        """Three beats. A question nobody has picked up in that long has been
        dropped by the scene, and re-raising it is its own kind of stall."""
        chat_id, ids = _seed(temp_db, [
            (140, "", {"41": _asked("Tamamo", "Describe it.", ["The Doctor"])}),
        ])
        assert _unanswered_question_note(
            chat_id, "The Doctor", ids["The Doctor"], 147, None) == {}


class TestTheAskersRegisterStillNamesYou:
    """Chat 98 t32->t33 (2026-08-29): an order's `interaction.addresses`
    carried the addressee's RANK followed by his name, the sheet's canonical
    name is the bare name, and exact equality read the pair as nobody. So
    the order never became a debt, its addressee was never promoted to
    answer, and the asker re-issued the same order verbatim one turn later.
    An address resolves through every key the body answers to, tail-matched
    at a word boundary -- a title or honorific prefixes while the name
    survives as the tail."""

    def test_a_rank_prefixed_address_is_still_a_debt(self, temp_db):
        chat_id, ids = _seed(temp_db, [
            (145, "", {"41": _asked(
                "Tamamo", "Hinami, will you carry the lantern ahead of us?",
                ["Lady Hinami"])}),
        ])
        owed = _unanswered_question_note(
            chat_id, "Hinami", ids["Hinami"], 146, None)["awaiting_your_answer"]
        assert owed["from"] == "Tamamo"
        assert "lantern" in owed["asked"]

    def test_a_bare_title_names_nobody(self, temp_db):
        """A title with no name is ambiguous, and ambiguity resolves to
        nobody rather than to whoever happens to match first."""
        chat_id, ids = _seed(temp_db, [
            (145, "", {"41": _asked(
                "Tamamo", "Will you carry the lantern?", ["Lady"])}),
        ])
        assert _unanswered_question_note(
            chat_id, "Hinami", ids["Hinami"], 146, None) == {}

    def test_the_players_address_resolves_the_same_way(self, temp_db):
        """`flow.addressed_to` occasionally holds names rather than ids, in
        the same register the asker speaks -- the one resolver serves both."""
        chat_id, ids = _seed(temp_db, [
            (145, "Hinami, what did you see?", {}),
        ])
        # Rewrite the stored director_interpret to address by styled name.
        row = temp_db.q(
            "SELECT v.id AS vid, v.content AS content FROM turns t "
            "JOIN steps s ON s.turn_id=t.id AND s.key='director_interpret' "
            "JOIN variants v ON v.step_id=s.id WHERE t.chat_id=? AND t.idx=145",
            (chat_id,), one=True)
        content = json.loads(row["content"])
        content["flow"] = {"addressed_to": ["Lady Hinami"]}
        temp_db.qi("UPDATE variants SET content=? WHERE id=?",
                   (json.dumps(content), row["vid"]))
        owed = _unanswered_question_note(
            chat_id, "Hinami", ids["Hinami"], 146, None)["awaiting_your_answer"]
        assert owed["from"] == "the player"


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
        for key, content in (
            ("director_interpret",
             {"speech": speech,
              "flow": {"addressed_to": [addressed(char_id)]}}),
            # Standing in the same room: the line is in his view.
            ("perception_act", {"views": {str(char_id): speech}}),
        ):
            sid = temp_db.qi(
                "INSERT INTO steps(turn_id,key,label,ord,stale) VALUES(?,?,?,?,0)",
                (tid, key, key, 0))
            temp_db.qi(
                "INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
                (sid, json.dumps(content), time.time()))
        return chat_id, char_id

    def test_a_question_from_the_player_is_surfaced(self, temp_db):
        chat_id, char_id = self._seed_player_ask(
            temp_db, "So what is that box of yours, really?", lambda cid: cid)
        owed = _unanswered_question_note(
            chat_id, "The Doctor", char_id, 146, None)["awaiting_your_answer"]
        assert owed["from"] == "the player"
        assert "box of yours" in owed["asked"]

    def test_addressed_to_resolves_by_name_as_well_as_id(self, temp_db):
        chat_id, char_id = self._seed_player_ask(
            temp_db, "What is it?", lambda cid: "The Doctor")
        assert _unanswered_question_note(
            chat_id, "The Doctor", char_id, 146, None)["awaiting_your_answer"]

    def test_a_statement_from_the_player_is_not_a_debt(self, temp_db):
        chat_id, char_id = self._seed_player_ask(
            temp_db, "That box of yours is strange.", lambda cid: cid)
        assert _unanswered_question_note(
            chat_id, "The Doctor", char_id, 146, None) == {}

    def test_a_question_aimed_at_somebody_else_is_not_yours(self, temp_db):
        chat_id, char_id = self._seed_player_ask(
            temp_db, "What is it?", lambda cid: "Tamamo")
        assert _unanswered_question_note(
            chat_id, "The Doctor", char_id, 146, None) == {}


class TestSustainedSilenceIsADifferentEvent:
    """One quiet beat is something the player just did. Four in a row is
    somebody who has stepped back — and reading it afresh each beat is what
    produced "Hinami, you have gone quiet after such proud words" followed by
    "Hinami, your presence here is a quiet joy"."""

    def test_one_quiet_beat_counts_as_one(self, temp_db):
        chat_id, ids = _seed(temp_db, [(144, "I was being polite.", {})])
        assert _player_quiet_beats(chat_id, 145, None) == 1

    def test_consecutive_silence_accumulates(self, temp_db):
        chat_id, ids = _seed(temp_db, [(144, "", {}), (145, "", {}), (146, "", {})])
        assert _player_quiet_beats(chat_id, 147, None) == 4

    def test_speech_resets_the_run(self, temp_db):
        chat_id, ids = _seed(temp_db, [(144, "", {}), (145, "Still here.", {}),
                                  (146, "", {})])
        assert _player_quiet_beats(chat_id, 147, None) == 2

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
    from llm.prompts import get_prompt

    text = get_prompt("character")
    assert "awaiting_your_answer" in text
    assert "player_quiet_for_beats" in text
    # Noticing is required; answering is not.
    assert "not obliged to answer" in text


class TestADebtNeedsAChannel:
    """A question becomes a debt through a line that REACHED this mind. The
    asker's `expects_response`/`addresses` states the asker's own intent, and
    intending to address somebody is not the same as their having heard it.

    The engine already writes down what each mind was delivered — the composed
    per-observer view (`perception_act`/`perception_outcome`) and the
    micro-round's `delivered_views` — and this note read none of it, so a line
    spoken through a shut door arrived verbatim in the payload of the mind it
    never reached.
    """

    def _seed_turn(self, temp_db, *, speech=None, results=None, heard=None,
                   bare=None):
        """One turn, with an explicit record of what this mind received.

        `bare` seeds `character:<id>` steps -- one result per step, which is
        what `build_plan` writes instead of an `interaction_loop` on an
        uncontested beat at `autonomy == 0`.
        """
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)", ("T", "", 0.0))
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,created) VALUES(?,?,?)",
            ("The Doctor", json.dumps({"identity": {"name": "The Doctor"}}), 0.0))
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
            (chat_id, char_id, "active", "{}"))
        tid = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
            (chat_id, 145, "", time.time()))
        steps = [("perception_outcome", {"views": {str(char_id): heard}})]
        if speech is not None:
            steps.append(("director_interpret",
                          {"speech": speech,
                           "flow": {"addressed_to": [char_id]}}))
        if results is not None:
            steps.append(("interaction_loop", {"character_results": results}))
        for other_id, result in (bare or {}).items():
            steps.append(("character:%s" % other_id, result))
        for key, content in steps:
            sid = temp_db.qi(
                "INSERT INTO steps(turn_id,key,label,ord,stale) VALUES(?,?,?,?,0)",
                (tid, key, key, 0))
            temp_db.qi(
                "INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
                (sid, json.dumps(content), time.time()))
        return chat_id, char_id

    def test_a_question_that_reached_nobody_is_not_owed(self, temp_db):
        chat_id, char_id = self._seed_turn(
            temp_db, heard=None, results={"41": _asked(
                "Tamamo", "Doctor, describe its dimensional nature.",
                ["The Doctor"])})
        assert _unanswered_question_note(
            chat_id, "The Doctor", char_id, 146, None) == {}

    def test_the_players_question_needs_a_channel_too(self, temp_db):
        chat_id, char_id = self._seed_turn(
            temp_db, heard=None, speech="So what is that box of yours, really?")
        assert _unanswered_question_note(
            chat_id, "The Doctor", char_id, 146, None) == {}

    def test_a_line_that_arrived_muffled_is_not_quoted_back_in_full(self, temp_db):
        """Partial hearing delivers a fragment, never the words. The note may
        repeat only what the recorded view already carried."""
        chat_id, char_id = self._seed_turn(
            temp_db,
            heard='Tamamo says something — "…dimensional…" — little of it.',
            results={"41": _asked(
                "Tamamo", "Doctor, describe its dimensional nature.",
                ["The Doctor"])})
        assert _unanswered_question_note(
            chat_id, "The Doctor", char_id, 146, None) == {}

    def test_the_quoted_line_is_the_one_this_mind_actually_received(self, temp_db):
        """An overt question followed by a concealed aside: `said[-1]` is the
        aside, and the aside is not this mind's. The debt is the question."""
        aside = "And I would not trust him with it."
        result = {
            "name": "Tamamo",
            "sequence": [
                {"type": "speech", "text": "Doctor, describe its nature."},
                {"type": "speech", "text": aside, "visibility": "concealed",
                 "conceal_from": ["The Doctor"]},
            ],
            "interaction": {"expects_response": True,
                            "addresses": ["The Doctor"]},
        }
        chat_id, char_id = self._seed_turn(
            temp_db, heard='Tamamo says, "Doctor, describe its nature."',
            results={"41": result})
        owed = _unanswered_question_note(
            chat_id, "The Doctor", char_id, 146, None)["awaiting_your_answer"]
        assert owed["asked"] == "Doctor, describe its nature."
        assert aside not in owed["asked"]

    def test_a_delivered_question_still_becomes_a_debt(self, temp_db):
        chat_id, char_id = self._seed_turn(
            temp_db, heard='Tamamo says, "Doctor, describe its nature."',
            results={"41": _asked("Tamamo", "Doctor, describe its nature.",
                                  ["The Doctor"])})
        assert _unanswered_question_note(
            chat_id, "The Doctor", char_id, 146, None)["awaiting_your_answer"]

    def test_a_question_asked_in_a_bare_character_step_is_owed_too(
            self, temp_db):
        """At `autonomy == 0` on an uncontested beat there is no
        `interaction_loop` at all -- every declaration is stored under
        `character:<id>` -- so on those chats no character-asked question ever
        became a debt, and the absence looked exactly like a beat with nothing
        owed."""
        chat_id, char_id = self._seed_turn(
            temp_db, heard='Tamamo says, "Doctor, describe its nature."',
            bare={41: _asked("Tamamo", "Doctor, describe its nature.",
                             ["The Doctor"])})
        owed = _unanswered_question_note(
            chat_id, "The Doctor", char_id, 146, None)["awaiting_your_answer"]
        assert owed["from"] == "Tamamo"

    def test_answering_in_a_bare_character_step_clears_it(self, temp_db):
        chat_id, char_id = self._seed_turn(
            temp_db, heard='Tamamo says, "Doctor, describe its nature."',
            bare={41: _asked("Tamamo", "Doctor, describe its nature.",
                             ["The Doctor"]),
                  99: _said("The Doctor", "It is only a machine.")})
        assert _unanswered_question_note(
            chat_id, "The Doctor", char_id, 146, None) == {}
