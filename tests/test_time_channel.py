"""The `state_diff.time` channel has ONE reader, and it reads every spelling
the engine itself teaches.

`state_diff.time` is declared `Optional[dict]`, so every key validates and
nothing downstream is obliged to look at any of them. Until this commit the
sole normal-turn clock reader knew exactly one absolute spelling,
`end_seconds`, and returned the previous clock UNCHANGED — with no warning
anywhere — for anything else. Meanwhile the resolve payload hands the model
the clock under its own name, `simulation_clock: {"elapsed_seconds": N}`
(agents/director_fanout.py:318), so a model echoing the engine's own key
emitted a time advance the engine read as silence.

Measured against the live corpus (engine.db, active director_* variants,
read-only, 2026-08-25): 2,450 stored time diffs; 2,440 carry the canonical
start/duration/end/mode/explicit/display_advance six, 2,408 carry exactly
those six. The non-canonical spellings actually observed are `display` (38),
`elapsed_seconds` (22, in chats 74/78/86/87/88/89), `time_scale` (10) and
`value` (3). Those totals grow with play and will read higher than this on a
later day; the five-row set the argument rests on does not move. Of the 22
`elapsed_seconds` diffs, 17 sit beside a full canonical shape where the value
always lies inside [start_seconds, end_seconds] — an absolute position, not a
duration — and 5 carry no other numeric key at all and were dropped whole:
chat 74 turns 55 and 60, and chat 88 turns 61, 64 and 66.

Chat 88 is the case that names the class. Turn 58's canonical diff left the
clock at 1106; turns 61 and 64 then claimed 1107 and 1266 against that
standing 1106.0, and neither moved it. Turn 65's canonically spelled diff
(start 1106, duration 30, end 1136) is the only advance in the stretch, and
turn 66 then claimed 7200 against the resulting 1136.0 and was dropped too.
`world.simulation_clock` for chat 88 still reads
`{"elapsed_seconds": 1136.0}`. Not one of the three refusals raised a warning.

The rule these tests pin: the vocabulary of `state_diff.time` belongs to one
reader (`world.mechanics.read_time_diff`); a clock position may arrive under
either name the engine uses for it; a diff that asserts only a duration is an
advance, not silence; and a diff that NAMES a time the reader cannot act on
must SAY so rather than hold the clock quietly — keyed on whether the reader
acted, not on whether the stored number happened to change.

One rule was added on top of these (docs/UNBUILT.md 1.84a, chat 95 second
pass beat 2): THE ENGINE OWNS THE CLOCK'S POSITION, AND A BEAT CONTRIBUTES A
SPAN. An absolute is read in the frame its own `start_seconds` declares; a
block anchored where the clock stands (or declaring no anchor) behaves
exactly as it always did, and a block anchored anywhere else advances the
clock by its span alone and is reported. Nothing in a model's payload
measures where the story clock stands, so an absolute computed from another
anchor is a guess wearing the authority of a measurement.
"""

from __future__ import annotations

import time

from core.pipeline_context import ChatData, PipelineContext, TurnData


# --- the vocabulary's owner ------------------------------------------------


class TestTheOwnerOfTheVocabulary:
    """`world.mechanics.read_time_diff` is the single place that knows what a
    time diff can say. Everything else asks it."""

    def test_a_position_may_arrive_under_either_name(self):
        from world.mechanics import read_time_diff

        assert read_time_diff(1136.0, {"elapsed_seconds": 7200}) == (
            7200.0, None, [])
        assert read_time_diff(1136.0, {"end_seconds": 7200}) == (
            7200.0, None, [])

    def test_the_canonical_name_outranks_the_synonym(self):
        """Chat 86 turn 22 verbatim: `elapsed_seconds` 435.0 sits inside the
        canonical span 430..455. All 2,402 canonical corpus rows must behave
        exactly as they did before."""
        from world.mechanics import read_time_diff

        assert read_time_diff(430.0, {
            "start_seconds": 430, "duration_seconds": 25, "end_seconds": 455,
            "mode": "action", "explicit": False,
            "display_advance": "moments later", "elapsed_seconds": 435.0,
            "display": "moments later"}) == (455.0, None, [])

    def test_a_forward_absolute_anchored_off_the_clock_is_a_span(self):
        """Chat 95 second pass beat 2, verbatim: four people talking on a
        bridge declared start 20520 / duration 45 / end 20565 against a
        clock standing at 20.0 -- the model was doing its arithmetic in a
        time of day the engine never held. The old contract adopted the
        forward absolute and the conversation moved the clock five and a
        half hours; the declared start is the block's own anchor, the
        anchor is not where the clock stood, so only the span crosses."""
        from world.mechanics import read_time_diff

        assert read_time_diff(20.0, {
            "start_seconds": 20520, "duration_seconds": 45,
            "end_seconds": 20565, "mode": "action", "explicit": False,
            "display_advance": ""}) == (65.0, (20565.0, 20.0), [])

    def test_a_skip_lands_whole_from_a_displaced_frame(self):
        """A time skip is a duration, and a span survives the frame
        translation that a position does not: a night's sleep declared
        from a wrong anchor still costs the story its 28800 seconds."""
        from world.mechanics import read_time_diff

        assert read_time_diff(20.0, {
            "start_seconds": 20520, "duration_seconds": 28800,
            "end_seconds": 49320}) == (28820.0, (49320.0, 20.0), [])

    def test_a_displaced_pair_without_a_duration_uses_its_own_span(self):
        from world.mechanics import read_time_diff

        assert read_time_diff(20.0, {
            "start_seconds": 20520, "end_seconds": 20565}) == (
            65.0, (20565.0, 20.0), [])

    def test_a_block_backwards_in_its_own_frame_claims_nothing_forward(self):
        """end < start is incoherent whatever the frame; with no duration
        there is no span to cross, so the clock holds and the caller is
        told a position was asserted and not adopted."""
        from world.mechanics import read_time_diff

        assert read_time_diff(20.0, {
            "start_seconds": 500, "end_seconds": 100}) == (
            20.0, (100.0, 20.0), [])

    def test_an_anchor_that_is_the_clock_changes_nothing(self):
        """The definitional case: a beat begins where the clock stands, so
        a block anchored there has its end adopted verbatim -- every
        canonical corpus row, byte-identical to every release since the
        reader existed."""
        from world.mechanics import read_time_diff

        assert read_time_diff(20520.0, {
            "start_seconds": 20520, "duration_seconds": 45,
            "end_seconds": 20565}) == (20565.0, None, [])

    def test_a_bare_duration_is_an_advance_not_silence(self):
        from world.mechanics import read_time_diff

        assert read_time_diff(100.0, {"duration_seconds": 60}) == (
            160.0, None, [])

    def test_a_backwards_position_still_gets_its_duration_and_reports(self):
        from world.mechanics import read_time_diff

        assert read_time_diff(5400.0, {
            "elapsed_seconds": 30, "duration_seconds": 30}) == (
            5430.0, (30.0, 5400.0), [])

    def test_a_key_it_cannot_read_is_named(self):
        from world.mechanics import read_time_diff

        assert read_time_diff(100.0, {"seconds": 300}) == (
            100.0, None, ["seconds"])

    def test_a_taught_key_it_cannot_act_on_is_named_too(self):
        """The refusal is keyed on whether the reader ACTED, not on whether
        it met an unknown key. `{start_seconds}` with no end and no duration
        is spelled entirely in the vocabulary the prompts teach and still
        moves nothing — a start is where the beat began, never where it
        ended — so it is exactly as dropped as `{"seconds": 300}` and must
        report the same way. Same for a position that will not parse."""
        from world.mechanics import read_time_diff

        assert read_time_diff(1136.0, {
            "start_seconds": 1200, "mode": "action"}) == (
            1136.0, None, ["start_seconds"])
        assert read_time_diff(1136.0, {
            "end_seconds": "soon", "display_advance": "later"}) == (
            1136.0, None, ["end_seconds"])
        assert read_time_diff(100.0, {"duration_seconds": "a while"}) == (
            100.0, None, ["duration_seconds"])

    def test_a_position_that_merely_equals_the_clock_is_not_a_refusal(self):
        """The converse, and the reason the key is `acted` rather than
        `the number moved`. `value` is a real corpus spelling (3 rows, chats
        72/73/74) and is unreadable — but when the beat ALSO names a
        position the reader takes, the clock was read, and a warning saying
        it carried none would be false. A beat may legitimately re-assert
        where the clock already stands."""
        from world.mechanics import read_time_diff

        assert read_time_diff(1136.0, {
            "end_seconds": 1136, "value": "midnight"}) == (1136.0, None, [])
        assert read_time_diff(100.0, {"duration_seconds": 0, "zzz": 1}) == (
            100.0, None, [])

    def test_known_metadata_alone_is_not_a_refusal(self):
        """`display` and `time_scale` are the clock's own vocabulary echoed
        back (38 and 10 times in the corpus). They ASSERT no time — they
        label one — so the clock holds and nothing is reported. Refusing to
        act on a claim and being handed no claim are different states."""
        from world.mechanics import read_time_diff

        assert read_time_diff(100.0, {
            "display": "later", "time_scale": "scene"}) == (100.0, None, [])

    def test_a_non_dict_reads_as_no_claim(self):
        from world.mechanics import read_time_diff

        assert read_time_diff(100.0, None) == (100.0, None, [])
        assert read_time_diff(100.0, "later") == (100.0, None, [])

    def test_the_passage_phrase_is_still_vocabulary_and_still_no_claim(self):
        """The phrase reaches no reader now (see `tests/test_time_of_day.py`)
        but must stay in the vocabulary: a key the reader does not KNOW is
        reported as an unreadable claim, and a beat labelling how long it
        took has made no claim to refuse."""
        from world.mechanics import (TIME_DIFF_KEYS, read_time_diff,
                                     time_diff_claims)

        assert {"display_advance", "display"} <= TIME_DIFF_KEYS
        assert not time_diff_claims({"display_advance": "moments later"})
        assert read_time_diff(100.0, {"display_advance": "an hour later"}) == (
            100.0, None, [])

    def test_the_stored_clock_has_one_reader_too(self):
        """`clock_elapsed` owns the other half of the shape, so no commit
        site spells the stored dict for itself."""
        from world.mechanics import clock_elapsed

        assert clock_elapsed({"elapsed_seconds": 1136.0}) == 1136.0
        assert clock_elapsed({"elapsed_seconds": "1136"}) == 1136.0
        assert clock_elapsed({}) == 0.0
        assert clock_elapsed(None) == 0.0
        assert clock_elapsed({"elapsed_seconds": "soon"}) == 0.0

    def test_the_span_of_a_beat(self):
        """The vitals seam has no previous clock to subtract from, so an
        absolute-only diff reads as zero span. Deliberately conservative."""
        from world.mechanics import time_diff_duration

        assert time_diff_duration({
            "start_seconds": 430, "duration_seconds": 45,
            "end_seconds": 475}) == 45.0
        assert time_diff_duration({"start_seconds": 200,
                                   "end_seconds": 500}) == 300.0
        assert time_diff_duration({"elapsed_seconds": 7200}) == 0.0
        assert time_diff_duration(None) == 0.0


# --- the commit's clock reader ---------------------------------------------


class TestTheClockReaderAcceptsWhatTheEngineTeaches:
    """`_monotonic_elapsed` keeps its name, its arity and its two-tuple —
    tests/test_carriers.py drives it five times and inspects its caller's
    source — and delegates the shape to the owner above."""

    def test_the_synonym_is_an_absolute_position(self):
        """Chat 88 turn 66's diff verbatim, against the clock it was refused
        by."""
        from persist.commit import _monotonic_elapsed

        assert _monotonic_elapsed({"elapsed_seconds": 1136.0},
                                  {"elapsed_seconds": 7200}) == (7200.0, None)

    def test_chat_88_turn_61_verbatim(self):
        from persist.commit import _monotonic_elapsed

        assert _monotonic_elapsed(
            {"elapsed_seconds": 1106.0},
            {"elapsed_seconds": 1107.0, "display": "moments later"}) == (
            1107.0, None)

    def test_the_canonical_shape_is_untouched(self):
        """Chat 86 turn 22: `end_seconds` outranks the synonym, so every
        canonical corpus row commits the same number it always did."""
        from persist.commit import _monotonic_elapsed

        assert _monotonic_elapsed(
            {"elapsed_seconds": 430.0},
            {"start_seconds": 430, "duration_seconds": 25, "end_seconds": 455,
             "elapsed_seconds": 435.0}) == (455.0, None)

    def test_a_backwards_synonym_still_gets_its_duration(self):
        from persist.commit import _monotonic_elapsed

        assert _monotonic_elapsed(
            {"elapsed_seconds": 5400.0},
            {"elapsed_seconds": 30, "duration_seconds": 30}) == (
            5430.0, (30.0, 5400.0))

    def test_a_bare_duration_advances(self):
        from persist.commit import _monotonic_elapsed

        assert _monotonic_elapsed({"elapsed_seconds": 100.0},
                                  {"duration_seconds": 60}) == (160.0, None)


# --- the sleep floor -------------------------------------------------------


class TestASleepEndsOnTheClockItWasMeasuredBy:
    """`_sleep_elapsed` feeds the awareness view, the clock exit and the
    restraint view. It had its own three-key ladder, so a beat spelled the
    other way left every sleeper under forever."""

    def test_a_full_sleep_ends_on_a_synonym_spelled_beat(self):
        from agents.director import _sleep_elapsed

        assert _sleep_elapsed({"started_at_seconds": 0.0},
                              {"elapsed_seconds": 1000.0},
                              {"elapsed_seconds": 30000}) == 30000.0

    def test_the_canonical_shape_is_unchanged(self):
        """REWRITTEN with the clock-authority decision (docs/UNBUILT.md
        1.84a). This test used to pin the same triple against a clock at
        0.0 and demand 1060 -- a model-declared absolute outranking the
        engine clock by a thousand seconds, which is exactly the contract
        that let chat 95's bridge conversation move the clock five and a
        half hours. The routing property it meant to pin -- a sleep ends on
        the clock the commit will keep -- is pinned here with a WORLD WHOSE
        CLOCK AND TRIPLE AGREE, which is what every canonical corpus row
        looks like."""
        from agents.director import _sleep_elapsed

        assert _sleep_elapsed({"started_at_seconds": 100.0},
                              {"elapsed_seconds": 1000.0},
                              {"start_seconds": 1000, "duration_seconds": 60,
                               "end_seconds": 1060}) == 960.0

    def test_an_absolute_anchored_off_the_clock_cannot_end_a_sleep(self):
        """The other half of the rewrite above: the SAME triple against a
        clock at 0.0 now contributes only its 60-second span, so the sleep
        measures 0 + 60 - 100 -- negative, which the floor reads as
        unknown rather than as a 960-second sleep vouched for by a number
        the engine never held."""
        from agents.director import _sleep_elapsed

        assert _sleep_elapsed({"started_at_seconds": 100.0},
                              {"elapsed_seconds": 0.0},
                              {"start_seconds": 1000, "duration_seconds": 60,
                               "end_seconds": 1060}) is None

    def test_no_time_diff_falls_to_the_engine_clock(self):
        """Passes before AND after: a compat pin, not new behaviour."""
        from agents.director import _sleep_elapsed

        assert _sleep_elapsed({"started_at_seconds": 100.0},
                              {"elapsed_seconds": 900.0}, None) == 800.0


# --- the commit, end to end ------------------------------------------------


def _make_chat(temp_db):
    return temp_db.qi(
        "INSERT INTO chats(name,persona_id,scenario,created) VALUES(?,?,?,?)",
        ("Test", None, "", time.time()))


def _hall_scene():
    return {
        "location": "Kessler Tower", "time_of_day": "night",
        "rooms": {"hall": {"name": "Hall", "desc": "A hall.", "adjacent": []}},
        "entities": {},
        "positions": {"The Stranger": "hall"},
        "attire": {}, "overlays": {},
    }


def _make_ctx(temp_db, chat_id, *, turn_idx, diff):
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, turn_idx, "wait", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=turn_idx,
                      player_input="wait", created=time.time()),
        cast=[], input="wait",
    )
    ctx.director_resolve = {"resolved_event": "Time passes.",
                            "dialogue_log": [], "state_diff": diff}
    return ctx


def _run_turn(temp_db, chat_id, diff, *, clock, turn_idx=1):
    from persist.commit import commit_scene, prepare_scene_commit

    temp_db.wset(chat_id, "scene", _hall_scene())
    temp_db.wset(chat_id, "simulation_clock", clock)
    ctx = _make_ctx(temp_db, chat_id, turn_idx=turn_idx, diff=diff)
    prepared = prepare_scene_commit(ctx)
    commit_scene(ctx, 0, prepared=prepared)
    return ctx, temp_db.wget(chat_id, "simulation_clock", {})


class TestTheCommitKeepsTheTimeItWasGiven:

    def test_a_synonym_spelled_advance_reaches_the_stored_clock(self, temp_db):
        """Chat 88 turn 66 replayed: 7200 against a clock held at 1136.0."""
        chat_id = _make_chat(temp_db)
        ctx, clock = _run_turn(
            temp_db, chat_id, {"time": {"elapsed_seconds": 7200}},
            clock={"elapsed_seconds": 1136.0, "display": "moments later"})
        assert clock["elapsed_seconds"] == 7200.0
        assert not [w for w in ctx.warnings if "state_diff.time" in w]

    def test_a_refused_advance_says_so(self, temp_db):
        """RE-EARNED. This pin used to assert the clock HELD at 1136.0, and
        holding was the second half of the same defect: the beat was dropped
        AND the world froze. A refusal is still reported -- that is what this
        test is for -- but the beat is charged the unclaimed-beat floor now
        instead of stopping time, and the warning names the number that
        moved rather than reporting a stop."""
        from world.mechanics import UNCLAIMED_BEAT_SECONDS

        chat_id = _make_chat(temp_db)
        ctx, clock = _run_turn(
            temp_db, chat_id, {"time": {"seconds": 300}},
            clock={"elapsed_seconds": 1136.0, "display": "moments later"})
        assert clock["elapsed_seconds"] == 1136.0 + UNCLAIMED_BEAT_SECONDS
        assert any("no clock position" in w and "seconds" in w
                   and "unclaimed-beat floor" in w
                   for w in ctx.warnings)

    def test_a_refusal_spelled_in_taught_keys_says_so_too(self, temp_db):
        """The shape the warning exists for. Every key here is one the
        prompts teach, so a guard keyed on unknown keys would be blind to
        it. Chat 88's three beats were held exactly here; they are charged
        the floor now, and still reported."""
        from world.mechanics import UNCLAIMED_BEAT_SECONDS

        chat_id = _make_chat(temp_db)
        ctx, clock = _run_turn(
            temp_db, chat_id,
            {"time": {"start_seconds": 1200, "mode": "action",
                      "explicit": False}},
            clock={"elapsed_seconds": 1136.0, "display": "moments later"})
        assert clock["elapsed_seconds"] == 1136.0 + UNCLAIMED_BEAT_SECONDS
        assert any("no clock position" in w and "start_seconds" in w
                   for w in ctx.warnings)

    def test_a_position_equal_to_the_clock_is_not_accused_of_silence(
            self, temp_db):
        """The false-positive half. `value` is unreadable and the number did
        not move, but a position WAS read — so the commit must not report
        that the beat carried none."""
        chat_id = _make_chat(temp_db)
        ctx, clock = _run_turn(
            temp_db, chat_id,
            {"time": {"end_seconds": 1136, "value": "midnight"}},
            clock={"elapsed_seconds": 1136.0, "display": "moments later"})
        assert clock["elapsed_seconds"] == 1136.0
        assert not any("no clock position" in w for w in ctx.warnings)

    def test_a_display_only_beat_asserts_no_time_and_is_charged_in_silence(
            self, temp_db):
        """5 corpus rows carry a phrase and no number. LABELLING TIME IS
        STILL NOT CLAIMING IT -- so nothing is warned, because there was no
        refusal to report -- but silence is charged now: the beat happened,
        and a clock that stops whenever the number is missing is exactly the
        class `UNCLAIMED_BEAT_SECONDS` closes."""
        from world.mechanics import UNCLAIMED_BEAT_SECONDS

        chat_id = _make_chat(temp_db)
        ctx, clock = _run_turn(
            temp_db, chat_id, {"time": {"display": "a moment later"}},
            clock={"elapsed_seconds": 1136.0, "display": "moments later"})
        assert clock["elapsed_seconds"] == 1136.0 + UNCLAIMED_BEAT_SECONDS
        assert not [w for w in ctx.warnings if "state_diff.time" in w]

    def test_an_explicit_clear_erases_nothing(self, temp_db):
        """RE-EARNED, and inverted. This pin used to assert that
        `display_advance: ""` CLEARED the scene's time label, which was the
        defect written down as intent: a beat saying "I carry no phrase for
        how long I took" deleted a standing fact about the world that it
        never owned. The clock's number still moves; the time of day stands.
        """
        chat_id = _make_chat(temp_db)
        ctx, clock = _run_turn(
            temp_db, chat_id,
            {"time": {"start_seconds": 430, "duration_seconds": 25,
                      "end_seconds": 455, "display_advance": "",
                      "display": "moments later"}},
            clock={"elapsed_seconds": 430.0, "display": "dusk"})
        assert clock["elapsed_seconds"] == 455.0
        assert temp_db.wget(chat_id, "scene", {})["time_of_day"] == "night"
        # The clock's label restates the scene's own answer -- one statement,
        # two homes, and no way for them to drift apart.
        assert clock["display"] == "night"

    def test_the_passage_phrase_reaches_neither_field(self, temp_db):
        """RE-EARNED, and inverted for the same reason as the test above:
        this used to assert the phrase reached both. "moments later" is not a
        time of day and not a clock reading, and there is nowhere for it to
        land -- it stays the beat's own words on this resolve's variant."""
        chat_id = _make_chat(temp_db)
        ctx, clock = _run_turn(
            temp_db, chat_id,
            {"time": {"elapsed_seconds": 1200.0, "display": "moments later"}},
            clock={"elapsed_seconds": 1000.0, "display": "dusk"})
        assert clock["elapsed_seconds"] == 1200.0
        assert temp_db.wget(chat_id, "scene", {})["time_of_day"] == "night"
        assert clock["display"] == "night"

    def test_the_canonical_shape_commits_exactly_as_before(self, temp_db):
        chat_id = _make_chat(temp_db)
        ctx, clock = _run_turn(
            temp_db, chat_id,
            {"time": {"start_seconds": 430, "duration_seconds": 25,
                      "end_seconds": 455, "mode": "action", "explicit": False,
                      "display_advance": "moments later"}},
            clock={"elapsed_seconds": 430.0, "display": "dusk"})
        assert clock["elapsed_seconds"] == 455.0
        assert clock["display"] == "night"
        assert not [w for w in ctx.warnings if "state_diff.time" in w]

    def test_a_backwards_claim_still_reports_backwards(self, temp_db):
        """Passes before AND after: a compat pin, not new behaviour."""
        chat_id = _make_chat(temp_db)
        ctx, clock = _run_turn(
            temp_db, chat_id,
            {"time": {"end_seconds": 30, "duration_seconds": 30}},
            clock={"elapsed_seconds": 5400.0, "display": "now"})
        assert clock["elapsed_seconds"] == 5430.0
        assert any("backwards" in w for w in ctx.warnings)
        assert not any("no clock position" in w for w in ctx.warnings)

    def test_a_displaced_forward_claim_commits_its_span_and_says_so(
            self, temp_db):
        """Chat 95 second pass beat 2 through the whole commit: the stored
        clock ends 45 seconds on from 20.0, not five and a half hours, and
        the warning names the position that was not adopted without calling
        it backwards -- it ran forward, from an anchor the engine never
        held."""
        chat_id = _make_chat(temp_db)
        ctx, clock = _run_turn(
            temp_db, chat_id,
            {"time": {"start_seconds": 20520, "duration_seconds": 45,
                      "end_seconds": 20565, "mode": "action",
                      "explicit": False, "display_advance": ""}},
            clock={"elapsed_seconds": 20.0, "display": "now"})
        assert clock["elapsed_seconds"] == 65.0
        assert any("anchored away" in w for w in ctx.warnings)
        assert not any("backwards" in w for w in ctx.warnings)
        assert not any("no clock position" in w for w in ctx.warnings)


# --- the fold that keeps the two spellings level ---------------------------


def test_every_taught_spelling_is_one_the_reader_knows():
    """What `check_time_channel_vocabulary` folds, driven rather than
    trusted: the prompts and examples may only teach keys the owner reads."""
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "tools"))
    import project_check

    errors: list[str] = []
    project_check.check_time_channel_vocabulary(errors)
    assert errors == []


def test_the_fold_fires_when_the_reader_stops_reading_a_taught_key(
        monkeypatch):
    """The negative half. `check_time_channel_vocabulary` must read
    `TIME_DIFF_KEYS` at CALL time, or this cannot fire."""
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "tools"))
    import project_check
    from world import mechanics

    monkeypatch.setattr(
        mechanics, "TIME_DIFF_KEYS",
        frozenset(mechanics.TIME_DIFF_KEYS - {"end_seconds"}))
    errors: list[str] = []
    project_check.check_time_channel_vocabulary(errors)
    assert any("end_seconds" in e for e in errors)
