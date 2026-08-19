"""What a time traveller remembers, and where.

Frames give this engine a diegetic-time axis separate from play order, and
`is_memory_visible` is the single rule deciding which of a character's own
memories they may reach from where they are standing. It has never been
stress-tested against the case the feature exists for: a mind that goes
somewhere in time and comes BACK.

These are the five shapes flagged as most likely to entangle play order,
diegetic era and subjective sequence -- a traveller alternating between two
frames, two versions of one character in different eras, memories formed in
the future and recalled after returning, consolidation after a long excursion,
and rollback into the middle of one.

One of them was broken.

    THE TRAVELLER WHO CAME BACK. `is_memory_visible` grants a traveller
    continuity by checking the travellers list of the frame they are STANDING
    IN. The present is the implicit frame -- `frame_id is None`, no row, and
    `get_frame(None)` synthesises it with `travelers: []`. So that clause can
    never fire in the present, and a character who visited the year 5000 and
    walked home could not remember one moment of it. Standing in the future
    they saw everything; standing where they live, nothing.

The fix is one clause, and the reason it is safe is worth stating: every
caller reaches this through `visible_memory_rows`, which has already filtered
`char_id=?`. The only question this function ever answers is whether a mind
may reach its OWN experience. "You were registered as having travelled there"
is not a widening of anyone's information -- it is the definition of having
been there.
"""

from __future__ import annotations

import time

import pytest

from core import frames
from mind import memory
from core.frames import create_frame, is_memory_visible
from mind.memory import add_memory, search_memories, visible_memory_rows
from tests.helpers import patch_provider_seam

PRESENT = None


@pytest.fixture
def story(temp_db):
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Time", "", time.time()))
    traveller = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("The Doctor", "{}", "{}", time.time()))
    native = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("Hinami", "{}", "{}", time.time()))
    return {"chat_id": chat_id, "traveller": traveller, "native": native}


def _frame(story, label, ordinal, kind, travelers=()):
    return create_frame(story["chat_id"], label=label, ordinal=ordinal,
                        kind=kind, travelers=list(travelers))


def _remember(story, char_id, text, turn_idx, frame_id, key=None):
    return add_memory(story["chat_id"], char_id, None, "episodic", "witnessed",
                      0.7, text, gist=text, turn_idx=turn_idx,
                      frame_id=frame_id, event_key=key or f"event:{turn_idx}")


def _visible(story, char_id, viewer_frame_id, before=1000):
    return {r["gist"] for r in visible_memory_rows(
        story["chat_id"], char_id, before_turn_idx=before,
        viewer_frame_id=viewer_frame_id, include_archived=True)}


class TestTheTravellerWhoCameBack:
    """The live defect. A mind that visited the future and returned held no
    memory of it while standing at home."""

    def test_the_future_is_remembered_after_returning(self, story):
        future = _frame(story, "Year 5000", 5, "future",
                        travelers=[story["traveller"]])
        _remember(story, story["traveller"], "the sun over New Earth", 5, future)
        _remember(story, story["traveller"], "tea at the shrine", 9, PRESENT)
        assert _visible(story, story["traveller"], PRESENT) == {
            "the sun over New Earth", "tea at the shrine"}

    def test_a_native_of_the_present_still_cannot_see_the_future(self, story):
        """The firewall the whole feature exists for. Being alive later is not
        a way to know what happens later."""
        future = _frame(story, "Year 5000", 5, "future",
                        travelers=[story["traveller"]])
        _remember(story, story["native"], "the sun over New Earth", 5, future)
        _remember(story, story["native"], "tea at the shrine", 9, PRESENT)
        assert _visible(story, story["native"], PRESENT) == {"tea at the shrine"}

    def test_travelling_to_the_past_still_carries_the_present_along(self, story):
        """The clause that DID work, and must keep working: a traveller
        standing in an earlier era still remembers their own later life."""
        past = _frame(story, "Edo", -3, "past", travelers=[story["traveller"]])
        _remember(story, story["traveller"], "tea at the shrine", 9, PRESENT)
        assert "tea at the shrine" in _visible(story, story["traveller"], past)

    def test_a_native_of_the_past_does_not_know_the_future(self, story):
        past = _frame(story, "Edo", -3, "past", travelers=[story["traveller"]])
        _remember(story, story["native"], "tea at the shrine", 9, PRESENT)
        assert _visible(story, story["native"], past) == set()

    def test_the_rule_is_about_having_been_there(self, story):
        """Stated directly against the function, without the row machinery."""
        future = _frame(story, "Year 5000", 5, "future",
                        travelers=[story["traveller"]])
        assert is_memory_visible(story["traveller"], future, PRESENT, 5)
        assert not is_memory_visible(story["native"], future, PRESENT, 5)


class TestAlternatingBetweenTwoFrames:
    def test_each_leg_accumulates_and_none_of_it_is_lost(self, story):
        """Turn order is play order; the traveller's subjective sequence is
        the order they lived it, which is the same thing. Four legs, and at
        the end they hold all four."""
        future = _frame(story, "Year 5000", 5, "future",
                        travelers=[story["traveller"]])
        for idx, (text, frame) in enumerate([
                ("the shrine steps", PRESENT), ("the glass towers", future),
                ("the shrine bell", PRESENT), ("the towers burning", future)]):
            _remember(story, story["traveller"], text, idx + 1, frame)
        assert len(_visible(story, story["traveller"], PRESENT)) == 4
        assert len(_visible(story, story["traveller"], future)) == 4

    def test_a_native_sees_only_their_own_era_however_often_it_alternates(
            self, story):
        future = _frame(story, "Year 5000", 5, "future",
                        travelers=[story["traveller"]])
        for idx, (text, frame) in enumerate([
                ("the shrine steps", PRESENT), ("the glass towers", future),
                ("the shrine bell", PRESENT), ("the towers burning", future)]):
            _remember(story, story["native"], text, idx + 1, frame)
        assert _visible(story, story["native"], PRESENT) == {
            "the shrine steps", "the shrine bell"}


class TestTwoVersionsOfOneCharacter:
    """A character genuinely alive in two eras at once. The banks are the same
    row set -- there is one `char_id` -- so the separation has to come from
    the visibility rule, not from duplicated state."""

    def test_the_earlier_self_does_not_know_what_the_later_self_learned(
            self, story):
        past = _frame(story, "Edo", -3, "past")
        _remember(story, story["native"], "I learned his real name", 9, PRESENT)
        _remember(story, story["native"], "I was given the seal", 2, past)
        assert _visible(story, story["native"], past) == {"I was given the seal"}

    def test_the_later_self_remembers_the_earlier_one(self, story):
        past = _frame(story, "Edo", -3, "past")
        _remember(story, story["native"], "I was given the seal", 2, past)
        _remember(story, story["native"], "I learned his real name", 9, PRESENT)
        assert len(_visible(story, story["native"], PRESENT)) == 2

    def test_two_future_frames_are_not_visible_to_each_other(self, story):
        """Different eras at different ordinals: the nearer one cannot see the
        further one, even for a traveller registered in the further one only.
        Ordinals order eras; travelling is not a wildcard."""
        near = _frame(story, "Year 3000", 3, "future")
        far = _frame(story, "Year 5000", 5, "future")
        _remember(story, story["native"], "the towers burning", 5, far)
        assert _visible(story, story["native"], near) == set()


class TestConsolidationAfterAnExcursion:
    def test_consolidation_never_runs_outside_the_present(self, story):
        """A singleton autobiography has nowhere to put "as of the future".
        Consolidating in another era would permanently blend two of them with
        no way to un-blend."""
        future = _frame(story, "Year 5000", 5, "future",
                        travelers=[story["traveller"]])
        for idx in range(60):
            _remember(story, story["traveller"], f"a thing happened {idx}",
                      idx + 1, future, key=f"event:f{idx}")
        assert memory.maybe_consolidate_character_memory(
            story["chat_id"], story["traveller"], 60, frame_id=future) is None

    def test_the_present_still_consolidates_after_a_long_excursion(
            self, story, monkeypatch):
        """And the excursion's own memories are inside it, because the
        traveller lived them -- which only became true once the returning
        traveller could see them at all."""
        future = _frame(story, "Year 5000", 5, "future",
                        travelers=[story["traveller"]])
        for idx in range(30):
            _remember(story, story["traveller"], f"in the towers {idx}",
                      idx + 1, future, key=f"event:f{idx}")
        for idx in range(30):
            _remember(story, story["traveller"], f"at the shrine {idx}",
                      idx + 31, PRESENT, key=f"event:p{idx}")

        seen = {}

        def _fake(role, system, user, **kw):
            import json as _json
            seen["payload"] = _json.loads(user)
            return _json.dumps({"summary": "A long journey and a return home.",
                                "key_phrases": [], "unresolved_threads": []})

        patch_provider_seam(monkeypatch, "chat_complete", _fake)
        memory.maybe_consolidate_character_memory(
            story["chat_id"], story["traveller"], 61, frame_id=PRESENT)
        gists = {m["gist"] for m in seen["payload"]["memories_chronological"]}
        assert any(g.startswith("in the towers") for g in gists)
        assert any(g.startswith("at the shrine") for g in gists)

    def test_a_native_s_consolidation_never_sees_the_excursion(
            self, story, monkeypatch):
        future = _frame(story, "Year 5000", 5, "future",
                        travelers=[story["traveller"]])
        for idx in range(30):
            _remember(story, story["native"], f"in the towers {idx}",
                      idx + 1, future, key=f"event:f{idx}")
        for idx in range(30):
            _remember(story, story["native"], f"at the shrine {idx}",
                      idx + 31, PRESENT, key=f"event:p{idx}")

        seen = {}

        def _fake(role, system, user, **kw):
            import json as _json
            seen["payload"] = _json.loads(user)
            return _json.dumps({"summary": "An ordinary season.",
                                "key_phrases": [], "unresolved_threads": []})

        patch_provider_seam(monkeypatch, "chat_complete", _fake)
        memory.maybe_consolidate_character_memory(
            story["chat_id"], story["native"], 61, frame_id=PRESENT)
        gists = {m["gist"] for m in seen["payload"]["memories_chronological"]}
        assert not any(g.startswith("in the towers") for g in gists)


class TestRollbackIntoTheMiddleOfAnExcursion:
    def test_the_turn_cutoff_applies_inside_a_frame_too(self, story):
        """Rerunning turn 4 of an excursion must not let the mind read what it
        did on turn 6 of that same excursion. Audit F1 and the frame rule are
        independent filters and both have to hold."""
        future = _frame(story, "Year 5000", 5, "future",
                        travelers=[story["traveller"]])
        _remember(story, story["traveller"], "stepped off the ship", 3, future)
        _remember(story, story["traveller"], "the towers burning", 6, future)
        rows = visible_memory_rows(
            story["chat_id"], story["traveller"], before_turn_idx=4,
            viewer_frame_id=future, include_archived=True)
        assert {r["gist"] for r in rows} == {"stepped off the ship"}

    def test_rolling_back_to_before_the_excursion_hides_all_of_it(self, story):
        future = _frame(story, "Year 5000", 5, "future",
                        travelers=[story["traveller"]])
        _remember(story, story["traveller"], "tea at the shrine", 1, PRESENT)
        _remember(story, story["traveller"], "the glass towers", 5, future)
        rows = visible_memory_rows(
            story["chat_id"], story["traveller"], before_turn_idx=2,
            viewer_frame_id=PRESENT, include_archived=True)
        assert {r["gist"] for r in rows} == {"tea at the shrine"}

    def test_an_undated_memory_survives_every_rollback(self, story):
        """Imported or authored history belongs to no turn, so it cannot be
        any turn's leaked outcome -- and must not vanish when one is rerun."""
        _remember(story, story["traveller"], "my childhood", None, PRESENT,
                  key="event:child")
        rows = visible_memory_rows(
            story["chat_id"], story["traveller"], before_turn_idx=1,
            viewer_frame_id=PRESENT, include_archived=True)
        assert {r["gist"] for r in rows} == {"my childhood"}


class TestSpatialFramesAreADifferentAxis:
    def test_a_split_still_hides_the_other_side(self, story):
        """Spatial frames share their parent's ordinal, so the traveller
        clause must not accidentally reopen them. Two parties far apart RIGHT
        NOW is not time travel."""
        away = create_frame(story["chat_id"], label="The far shore", ordinal=0,
                            kind="spatial", parent_frame_id=None,
                            split_turn_idx=4)
        _remember(story, story["native"], "before we parted", 2, PRESENT)
        _remember(story, story["native"], "after we parted", 7, PRESENT)
        assert _visible(story, story["native"], away) == {"before we parted"}

    def test_someone_who_actually_went_there_keeps_their_own_side(self, story):
        away = create_frame(story["chat_id"], label="The far shore", ordinal=0,
                            kind="spatial", parent_frame_id=None,
                            split_turn_idx=4,
                            travelers=[story["traveller"]])
        _remember(story, story["traveller"], "on the far shore", 6, away)
        assert "on the far shore" in _visible(story, story["traveller"], PRESENT)

    def test_a_native_who_stayed_behind_does_not(self, story):
        away = create_frame(story["chat_id"], label="The far shore", ordinal=0,
                            kind="spatial", parent_frame_id=None,
                            split_turn_idx=4,
                            travelers=[story["traveller"]])
        _remember(story, story["native"], "on the far shore", 6, away)
        assert _visible(story, story["native"], PRESENT) == set()
