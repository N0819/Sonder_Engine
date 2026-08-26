"""A resolved beat that asserts no time still costs the clock a floor.

THE MEASUREMENT. Read-only against the author's corpus at 49ea899,
2026-08-25: of 2,614 active non-stale `director_resolve` outputs, 130 (5.0%)
carry a `state_diff.time` block this engine can read no claim out of, and 109
of those sit in six chats of one story line (88:24, 89:24, 90:20, 86:15,
87:15, 85:11). Chat 89 turns 58-62 are five consecutively: five resolved
beats, empty player input, and a simulation clock that stood at 1098.0
through all of them while the Director's own note described a transit in
progress. Everything the engine windows on seconds -- condition ticks,
scheduled events, weather drift, the off-screen epoch, affect decay, strain
and belief provenance -- compares against that clock, so they all went quiet
together.

TWO HALVES, AND THE SECOND IS WHY THIS FILE EXISTS RATHER THAN A LINE IN
`test_time_channel.py`. The floor is worthless if only one of the beat's
clock readers applies it: the scene commit writes `simulation_clock` and the
memory commit stamps psychology windows, and they must land on the same
number for the same beat. That is the class `_monotonic_elapsed` was made a
shared helper to close, once already, for backwards beats.

ASSERTION IS THE OFF SWITCH. A beat keeps the authority to say no time passed
-- by SAYING it. `duration_seconds: 0`, a re-asserted current position, any
claim the reader can act on: all of them turn the floor off completely.
"""
import time

import pytest

from world.mechanics import (UNCLAIMED_BEAT_SECONDS, beat_end_elapsed,
                             read_time_diff, time_diff_claims)


class TestTheFloorChargesSilenceAndNothingElse:

    def test_an_absent_block_is_charged(self):
        assert beat_end_elapsed(1098.0, None, floor=True) == (
            1098.0 + UNCLAIMED_BEAT_SECONDS, None, [], True)

    def test_an_empty_block_is_charged(self):
        elapsed, backwards, refused, floored = beat_end_elapsed(
            1098.0, {}, floor=True)
        assert (elapsed, backwards, refused, floored) == (1108.0, None, [], True)

    def test_an_explicit_zero_is_not_charged(self):
        """The Director's own way of saying a beat took no story time."""
        assert beat_end_elapsed(
            1098.0, {"duration_seconds": 0}, floor=True) == (
                1098.0, None, [], False)

    def test_a_position_equal_to_the_clock_is_not_charged(self):
        """Re-asserting where the clock already stands is a claim, not
        silence -- the same distinction `read_time_diff.refused` draws."""
        assert beat_end_elapsed(
            1098.0, {"end_seconds": 1098.0}, floor=True) == (
                1098.0, None, [], False)

    def test_a_labelled_but_numberless_beat_is_charged_and_not_accused(self):
        """5 corpus rows carry a phrase and no number. Labelling time is not
        claiming it, so it is charged -- and it is not a refusal, so nothing
        is reported."""
        assert beat_end_elapsed(
            1098.0, {"display": "later"}, floor=True) == (
                1108.0, None, [], True)

    def test_an_unreadable_claim_is_charged_AND_still_reported(self):
        """The double defect: a refusal that also froze the world. Chat 88's
        turns 61/64/66 shape -- a taught key, no readable position."""
        elapsed, backwards, refused, floored = beat_end_elapsed(
            1136.0, {"start_seconds": 1200, "mode": "action"}, floor=True)
        assert elapsed == 1146.0
        assert floored is True
        assert refused == ["start_seconds"]

    def test_floor_off_never_charges_anything(self):
        """An establish turn has no beat to charge for."""
        assert beat_end_elapsed(1098.0, {}, floor=False) == (
            1098.0, None, [], False)
        assert beat_end_elapsed(1098.0, None, floor=False) == (
            1098.0, None, [], False)

    def test_a_backwards_beat_still_reports_backwards(self):
        """The floor is additive to `read_time_diff`, never a replacement:
        a beat that claims a position earlier than the clock holds is a
        CLAIM, so it is not charged, and it still reports."""
        elapsed, backwards, refused, floored = beat_end_elapsed(
            1136.0, {"start_seconds": 0, "duration_seconds": 30,
                     "end_seconds": 30}, floor=True)
        assert backwards == (30.0, 1136.0)
        assert elapsed == 1166.0
        assert floored is False


class TestTheClaimTestCannotDriftFromTheReader:
    """`time_diff_claims` IS `read_time_diff`'s own acted-ness test. Two
    copies of one judgement is how the clock and the warning disagreed in
    the first place, so this walks the corpus shapes case by case."""

    SHAPES = [
        None,
        {},
        {"display": "a moment later"},
        {"display_advance": ""},
        {"mode": "action", "explicit": False},
        {"time_scale": "scene"},
        {"seconds": 300},
        {"value": "midnight"},
        {"start_seconds": 1200},
        {"start_seconds": 1200, "mode": "action", "explicit": False},
        {"end_seconds": "soon"},
        {"duration_seconds": "a while"},
        {"duration_seconds": 0},
        {"duration_seconds": 25},
        {"end_seconds": 1136},
        {"end_seconds": 1136, "value": "midnight"},
        {"elapsed_seconds": 7200},
        {"start_seconds": 430, "duration_seconds": 25, "end_seconds": 455},
        "a string, which is not a block at all",
    ]

    @pytest.mark.parametrize("shape", SHAPES)
    def test_the_claim_test_agrees_with_the_reader(self, shape):
        elapsed, _backwards, refused = read_time_diff(1000.0, shape)
        acted = not refused and (elapsed != 1000.0 or _reader_acted(shape))
        assert time_diff_claims(shape) is _reader_acted(shape), shape
        # And the two agree on the one thing the floor keys off: a shape the
        # reader acted on never gets charged.
        assert beat_end_elapsed(1000.0, shape, floor=True)[3] is not acted


def _reader_acted(shape):
    """What `read_time_diff` did, derived from its OWN two observable
    outputs rather than from a second copy of its logic: it acted when it
    refused nothing and either moved the clock or was handed a position it
    could parse."""
    td = shape if isinstance(shape, dict) else {}
    _elapsed, _backwards, refused = read_time_diff(1000.0, td)
    if refused:
        return False
    # No refusal and no keys at all is silence; no refusal with a readable
    # key is a claim. `read_time_diff` reports a refusal for every claim key
    # it could not act on, so what is left is exactly the readable ones.
    return any(k in ("duration_seconds", "end_seconds", "elapsed_seconds")
               for k in td)


# --- both stored readers, one number ---------------------------------------


def _make_chat(temp_db):
    return temp_db.qi(
        "INSERT INTO chats(name,persona_id,scenario,created) VALUES(?,?,?,?)",
        ("Test", None, "", time.time()))


def _hall_scene():
    return {
        "location": "Kessler Tower", "time": "night",
        "rooms": {"hall": {"name": "Hall", "desc": "A hall.", "adjacent": []}},
        "entities": {},
        "positions": {"The Stranger": "hall"},
        "attire": {}, "overlays": {},
    }


def _make_ctx(temp_db, chat_id, *, diff, resolved=True):
    from core.pipeline_context import ChatData, PipelineContext, TurnData

    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input="", created=time.time()),
        cast=[], input="",
    )
    if resolved:
        ctx.director_resolve = {"resolved_event": "The beat passes.",
                                "dialogue_log": [], "state_diff": diff}
    return ctx


def _run_scene_commit(temp_db, chat_id, diff, *, clock, resolved=True):
    from persist.commit import commit_scene, prepare_scene_commit

    temp_db.wset(chat_id, "scene", _hall_scene())
    temp_db.wset(chat_id, "simulation_clock", clock)
    ctx = _make_ctx(temp_db, chat_id, diff=diff, resolved=resolved)
    prepared = prepare_scene_commit(ctx)
    commit_scene(ctx, 0, prepared=prepared)
    return ctx, temp_db.wget(chat_id, "simulation_clock", {})


class TestTheStoredClockIsCharged:

    def test_a_timeless_resolved_beat_advances_by_the_floor(self, temp_db):
        """Chat 89 turn 58 replayed: no time block at all, clock at 1098.0."""
        chat_id = _make_chat(temp_db)
        ctx, clock = _run_scene_commit(
            temp_db, chat_id, {},
            clock={"elapsed_seconds": 1098.0, "display": "moments later"})
        assert clock["elapsed_seconds"] == 1098.0 + UNCLAIMED_BEAT_SECONDS
        # Silence is not a refusal, so nothing is accused.
        assert not [w for w in ctx.warnings if "state_diff.time" in w]

    def test_an_explicit_zero_leaves_the_clock_exactly_where_it_was(
            self, temp_db):
        chat_id = _make_chat(temp_db)
        _ctx, clock = _run_scene_commit(
            temp_db, chat_id, {"time": {"duration_seconds": 0}},
            clock={"elapsed_seconds": 1098.0, "display": "moments later"})
        assert clock["elapsed_seconds"] == 1098.0

    def test_a_re_asserted_position_leaves_the_clock_where_it_was(
            self, temp_db):
        chat_id = _make_chat(temp_db)
        _ctx, clock = _run_scene_commit(
            temp_db, chat_id, {"time": {"end_seconds": 1098}},
            clock={"elapsed_seconds": 1098.0, "display": "moments later"})
        assert clock["elapsed_seconds"] == 1098.0

    def test_an_establish_turn_is_never_charged(self, temp_db):
        """No resolved beat, nothing to charge for."""
        chat_id = _make_chat(temp_db)
        _ctx, clock = _run_scene_commit(
            temp_db, chat_id, {},
            clock={"elapsed_seconds": 1098.0, "display": "moments later"},
            resolved=False)
        assert clock["elapsed_seconds"] == 1098.0


class TestBothStoredReadersLandOnOneNumber:

    def test_the_memory_seam_stamps_the_same_clock_as_the_scene(self):
        """The class `_monotonic_elapsed` was made a shared helper to close,
        applied to the silent beat. Driven at the helper rather than through
        a full turn: `prepare_memory_commit` offers no seam that returns the
        stamp, which `tests/test_carriers.py` records as the reason its own
        pin on this reads source."""
        from persist.commit import _monotonic_elapsed

        prev = {"elapsed_seconds": 1098.0, "display": "moments later"}
        scene_end, _b, _r, floored = beat_end_elapsed(
            1098.0, None, floor=True)
        memory_end, _backwards = _monotonic_elapsed(prev, None, floor=True)
        assert floored is True
        assert memory_end == scene_end == 1108.0

    def test_neither_reader_floors_a_beat_that_claimed(self):
        from persist.commit import _monotonic_elapsed

        prev = {"elapsed_seconds": 1098.0}
        td = {"duration_seconds": 0}
        assert _monotonic_elapsed(prev, td, floor=True)[0] == 1098.0
        assert beat_end_elapsed(1098.0, td, floor=True)[0] == 1098.0
