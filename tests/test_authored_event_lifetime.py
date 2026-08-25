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

Both are subtractive: neither can create an event, extend one, or need a model
to cooperate.
"""

from __future__ import annotations

import json
import time

import pytest

from core.db import q
from story.authored_events import (MAX_REQUEUES, _retired_text,
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
        resolve_authored_events(cid, 2, "The bell rings out over the yard.")
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
        """`state_diff` defaults to None so every existing caller keeps what
        it had -- establish has no diff at all."""
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
