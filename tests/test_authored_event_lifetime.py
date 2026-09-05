"""An assertion is one row, and a future whose subject has ended cannot happen.

"Never dropped" was the whole point of authored events, and it had become
"never ends" by two separate routes.

IDENTITY. `_event_id` hashed the chat, the MINTING BEAT and the index, so
identity was the beat that minted a row rather than the assertion it carried.
A due event is handed back to the Director as `due_authored_events`, and the
interpret prompt asks it to fold that into THIS beat -- so a still-standing
assertion is routinely re-emitted in `flow.scheduled_assertions` on later
turns, and every echo became a NEW row with a fresh re-queue budget. Measured:
three identical pending copies of one assertion at one beat, two at another,
the earliest minted nine beats before. `MAX_REQUEUES` bounds ONE row to three
deliveries, so nine beats were only reachable by re-minting.

FORECLOSURE. `resolve_authored_events` judged a due event against the resolved
prose alone. Nothing asked whether the referent still stood, so an assertion
the beat's own committed diff RETIRED spent its whole budget re-delivering a
finished thing to the Director. The engine already states this rule for the
other half of the same table -- a fuse whose cause un-happened is "cancelled
loudly, never fired" -- and the authored side never got the sibling rule.

SPENT BY THE WORLD. Coverage was measured against the resolved PROSE alone, so
in a story where the characters spend every beat talking about the coming
thing, every scheduled event fires on its due beat whether or not it occurs
(PX9). A scheduled event is spent when the WORLD changes, not when the
conversation reaches it, so the committed diff has to carry it too -- and an
event the prose carries and no channel encodes is said out loud rather than
swallowed (PR2).

All three are subtractive: none can create an event, extend one, or need a
model to cooperate.
"""

from __future__ import annotations

import json
import time

import pytest

from core.db import q
from story.authored_events import (MAX_REQUEUES, _changed_text, _retired_text,
                                   due_authored_events, mint_authored_events,
                                   resolve_authored_events)


def _chat(temp_db):
    return temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                      ("t", "", time.time()))


def _rows(temp_db, cid):
    return q("SELECT event_id, status, payload FROM scheduled_events "
             "WHERE chat_id=? AND kind='authored_event'", (cid,))


class TestOneAssertionIsOneRow:
    def test_a_later_beat_re_emitting_it_absorbs_into_the_live_row(
            self, temp_db):
        """The shape that actually happened: the Director is HANDED the due
        event and asked to fold it in, and emits it again as a fresh
        assertion."""
        cid = _chat(temp_db)
        mint_authored_events(cid, 36, [{"summary": "the rain keeps falling",
                                        "due_in_turns": 1}])
        for beat in (37, 38, 39):
            mint_authored_events(cid, beat, [
                {"summary": "the rain keeps falling", "due_in_turns": 1}])
        assert len(_rows(temp_db, cid)) == 1
        assert len(due_authored_events(cid, 40)) == 1

    def test_an_echo_mints_nothing(self, temp_db):
        cid = _chat(temp_db)
        assert mint_authored_events(
            cid, 3, [{"summary": "the bridge collapses"}]) == 1
        assert mint_authored_events(
            cid, 4, [{"summary": "the bridge collapses"}]) == 0

    def test_reflowed_whitespace_and_case_are_the_same_assertion(
            self, temp_db):
        cid = _chat(temp_db)
        mint_authored_events(cid, 3, [{"summary": "The bridge  collapses"}])
        mint_authored_events(cid, 4, [{"summary": "the bridge collapses"}])
        assert len(_rows(temp_db, cid)) == 1

    def test_the_echo_does_not_reset_the_budget(self, temp_db):
        """An assertion ages out on the budget it was minted with, rather than
        being reset by the fold-in it caused."""
        cid = _chat(temp_db)
        mint_authored_events(cid, 1, [{"summary": "the tower falls"}])
        resolve_authored_events(cid, 2, "Nothing of the sort happened.")
        mint_authored_events(cid, 2, [{"summary": "the tower falls"}])
        payload = json.loads(_rows(temp_db, cid)[0]["payload"])
        assert payload["requeues"] == 1

    def test_the_echo_does_not_push_the_due_date_out(self, temp_db):
        cid = _chat(temp_db)
        mint_authored_events(cid, 1, [{"summary": "the tower falls",
                                       "due_in_turns": 1}])
        mint_authored_events(cid, 5, [{"summary": "the tower falls",
                                       "due_in_turns": 1}])
        assert len(due_authored_events(cid, 2)) == 1

    def test_a_finished_row_can_be_re_armed(self, temp_db):
        """A row that has already fired or gone stale is NOT live, so
        scheduling the same thing again later is a new schedule, not an
        echo."""
        cid = _chat(temp_db)
        mint_authored_events(cid, 1, [{"summary": "the bell rings"}])
        resolve_authored_events(
            cid, 2, "The bell rings out over the yard.",
            state_diff={"sensory_events": [{"text": "the bell rings"}]})
        assert mint_authored_events(cid, 9, [{"summary": "the bell rings"}]) == 1
        assert len(due_authored_events(cid, 10)) == 1

    def test_a_rerun_of_the_same_turn_still_never_doubles(self, temp_db):
        cid = _chat(temp_db)
        mint_authored_events(cid, 3, [{"summary": "the bridge collapses",
                                       "due_in_turns": 2}])
        mint_authored_events(cid, 3, [{"summary": "the bridge collapses",
                                       "due_in_turns": 2}])
        assert len(due_authored_events(cid, 5)) == 1


class TestAFutureWhoseSubjectEnded:
    ASSERTION = {"summary": "the lantern keeps burning on the sill"}

    def test_a_retired_referent_ends_the_event_at_once(self, temp_db):
        cid = _chat(temp_db)
        mint_authored_events(cid, 1, [self.ASSERTION])
        fired, requeued, dropped = resolve_authored_events(
            cid, 2, "She crossed to the window.",
            state_diff={"remove_entities": ["the lantern burning on the sill"]})
        assert (fired, requeued, dropped) == (0, 0, 1)
        assert _rows(temp_db, cid)[0]["status"] == "stale"

    def test_without_the_retirement_it_would_have_re_queued(self, temp_db):
        """The same beat, minus the diff: this is what the budget was being
        spent on."""
        cid = _chat(temp_db)
        mint_authored_events(cid, 1, [self.ASSERTION])
        assert resolve_authored_events(
            cid, 2, "She crossed to the window.") == (0, 1, 0)

    def test_coverage_is_tested_first(self, temp_db):
        """A beat that retires a thing BY enacting the assertion still
        FIRES -- the assertion happened."""
        cid = _chat(temp_db)
        mint_authored_events(cid, 1, [{"summary": "the lantern gutters out"}])
        fired, _requeued, dropped = resolve_authored_events(
            cid, 2, "The lantern gutters out and the sill goes dark.",
            state_diff={"remove_entities": ["the lantern gutters"]})
        assert (fired, dropped) == (1, 0)

    def test_an_unrelated_retirement_leaves_it_alone(self, temp_db):
        cid = _chat(temp_db)
        mint_authored_events(cid, 1, [self.ASSERTION])
        assert resolve_authored_events(
            cid, 2, "She crossed to the window.",
            state_diff={"remove_entities": ["a stack of ledgers"]}) == (0, 1, 0)

    def test_no_diff_is_todays_behaviour_exactly(self, temp_db):
        """`state_diff` defaults to None so a caller that has no diff -- the
        establish has none at all -- re-queues rather than raising. With no
        world record there is nothing to say the beat enacted anything."""
        cid = _chat(temp_db)
        mint_authored_events(cid, 1, [self.ASSERTION])
        assert resolve_authored_events(
            cid, 2, "She crossed to the window.", state_diff=None) == (0, 1, 0)

    def test_it_can_only_end_an_event_sooner(self, temp_db):
        """Subtractive: the foreclosure runs after the budget would have been
        spent anyway, so the terminal count never grows."""
        cid = _chat(temp_db)
        mint_authored_events(cid, 1, [self.ASSERTION])
        for beat in range(2, 2 + MAX_REQUEUES + 1):
            resolve_authored_events(cid, beat, "Nothing happened.")
        assert _rows(temp_db, cid)[0]["status"] == "stale"


class TestWhatCountsAsRetiring:
    def test_any_remove_channel_contributes(self):
        """Channel-agnostic on purpose: naming the channels would tie the
        rule to today's diff shape and to whichever ledger the live case
        happened to be about."""
        text = _retired_text({"remove_entities": ["the lantern"],
                              "remove_contacts": [{"actor": "Mara"}]})
        assert "lantern" in text and "Mara" in text

    def test_a_retiring_op_contributes(self):
        text = _retired_text({"attire": [
            {"op": "remove", "garment": "wool cloak"}]})
        assert "wool cloak" in text

    def test_a_non_retiring_op_does_not(self):
        assert "wool cloak" not in _retired_text(
            {"attire": [{"op": "add", "garment": "wool cloak"}]})

    def test_the_op_verb_itself_is_not_evidence(self):
        """`op` is the engine's own word for what is happening, not a word
        the assertion could be about."""
        assert "remove" not in _retired_text(
            {"attire": [{"op": "remove", "garment": "cloak"}]})

    def test_a_diff_that_retires_nothing_yields_nothing(self):
        assert _retired_text({"positions": {"Mara": "hall"}}) == ""

    def test_a_missing_diff_is_not_an_error(self):
        assert _retired_text(None) == ""
        assert _retired_text("not a diff") == ""


class TestTheWarningSaysWhichEnding:
    def test_it_names_both_terminal_causes(self):
        """`dropped` now covers two, and a warning that names one of them
        misreports the other."""
        import inspect

        from persist import commit

        source = inspect.getsource(commit)
        assert "retired what they name" in source
        assert "re-queue limit" in source


class TestSpentByTheWorldNotTheConversation:
    """PX9 / PR2, masque run turn 10 and rush run turn 4, 2026-09-05.

    The Writers' Room published "The Governor's Descent" for turn 10. Turn 10
    was a beat of pure dialogue ABOUT the coming bell, and its prose happened
    to contain "bell", "governor" and "Torre" -- so the row read
    `{'status': 'fired', 'due_at': 10.0}` and nothing of the kind had
    happened. `inspect_events` pending went empty and the Room's only lever on
    future beats was silently disarmed.

    The rule: a scheduled event is spent when the WORLD changes, not when the
    conversation reaches it. The inverse case is PR2's: the Director narrated
    a stair catching fire ten feet away, asserted it in no channel, and the
    page for that beat was a woman letting go of a doorframe -- the beat is
    re-queued and the engine says so out loud.
    """

    ARRIVAL = {"summary": "Governor Corvay descends into the Long Reception "
                          "Room with his personal retinue"}

    def test_a_beat_that_only_talks_about_it_does_not_fire_it(self, temp_db):
        cid = _chat(temp_db)
        mint_authored_events(cid, 7, [self.ARRIVAL])
        fired, requeued, dropped = resolve_authored_events(
            cid, 10,
            "The Governor Corvay will descend into the Long Reception Room "
            "with his personal retinue when the bell tolls, says Torre.",
            state_diff={"contacts": [{"actor": "Torre", "relation": "rest"}]})
        assert (fired, requeued, dropped) == (0, 1, 0)
        assert _rows(temp_db, cid)[0]["status"] == "pending"

    def test_the_beat_that_enacts_it_fires_it(self, temp_db):
        cid = _chat(temp_db)
        mint_authored_events(cid, 7, [self.ARRIVAL])
        fired, requeued, dropped = resolve_authored_events(
            cid, 10,
            "Governor Corvay descends into the Long Reception Room with his "
            "personal retinue.",
            state_diff={"positions": {
                "Governor Corvay": "long_reception_room",
                "personal retinue": "long_reception_room"}})
        assert (fired, requeued, dropped) == (1, 0, 0)

    def test_the_world_record_alone_is_not_enough_either(self, temp_db):
        """Both channels, not one: a diff that happens to name the same
        subjects for an unrelated reason has not enacted the assertion, and
        the prose is what says the beat carried it."""
        cid = _chat(temp_db)
        mint_authored_events(cid, 7, [self.ARRIVAL])
        assert resolve_authored_events(
            cid, 10, "Nothing stirred in the hall.",
            state_diff={"positions": {
                "Governor Corvay": "long_reception_room",
                "personal retinue": "long_reception_room"}}) == (0, 1, 0)

    def test_a_narrated_but_unencoded_event_is_reported(self, temp_db):
        """PR2: the engine says the fire reached no ledger, rather than
        counting it as enacted or dropping it in silence."""
        import core.pipeline_context as pc

        cid = _chat(temp_db)
        mint_authored_events(cid, 3, [{
            "summary": "Flames breach the lower flight and ignite the "
                       "second-floor stair treads"}])
        said = []
        token = pc.current_warning_sink.set(said.append)
        try:
            resolve_authored_events(
                cid, 4,
                "Flames breach the lower flight and ignite the second-floor "
                "stair treads.",
                state_diff={"contacts": [{"actor": "Mirela"}]})
        finally:
            pc.current_warning_sink.reset(token)
        assert any("no channel" in line for line in said), said

    def test_a_foreclosed_event_still_goes_stale(self, temp_db):
        """The retirement rule survives: the prose does not carry it, so it
        is not enacted, and the diff retires what it names."""
        cid = _chat(temp_db)
        mint_authored_events(
            cid, 1, [{"summary": "the lantern keeps burning on the sill"}])
        assert resolve_authored_events(
            cid, 2, "She crossed to the window.",
            state_diff={"remove_entities": [
                "the lantern burning on the sill"]}) == (0, 0, 1)


class TestWhatCountsAsTheWorldRecord:
    def test_a_nested_key_is_the_subject_it_names(self):
        """A diff keys its channels by who changed, so the key is the world
        saying who -- `positions: {Mara: hall}` is evidence about Mara."""
        text = _changed_text({"positions": {"Mara": "hall"}})
        assert "Mara" in text and "hall" in text

    def test_the_channel_name_is_not_evidence(self):
        """`positions` is the engine's word for a KIND of change, never a
        word an assertion could be about -- the rule `_retired_text` states
        about `op`."""
        assert "positions" not in _changed_text({"positions": {"Mara": "hall"}})

    def test_the_op_verb_is_not_evidence_here_either(self):
        assert "remove" not in _changed_text(
            {"attire": [{"op": "remove", "garment": "cloak"}]})

    def test_a_missing_diff_is_not_an_error(self):
        assert _changed_text(None) == ""
        assert _changed_text("not a diff") == ""
