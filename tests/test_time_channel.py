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
read-only): 2,411 stored time diffs; 2,402 carry the canonical
start/duration/end/mode/explicit/display_advance six, 2,375 carry exactly
those six. The non-canonical spellings actually observed are `display` (32),
`elapsed_seconds` (18, in chats 74/78/86/87/88), `time_scale` (8) and `value`
(3). Of the 18 `elapsed_seconds` diffs, 13 sit beside a full canonical shape
where the value always lies inside [start_seconds, end_seconds] — an absolute
position, not a duration — and 5 carry no other numeric key at all and were
dropped whole: chat 74 turns 55 and 60, and chat 88 turns 61, 64 and 66.

Chat 88 is the case that names the class: turns 61, 64 and 66 claimed 1107,
1266 and 7200, and `world.simulation_clock` still reads
`{"elapsed_seconds": 1136.0}`. The clock never left 1136.0 against those
three claims, and not one warning was raised.

The rule these tests pin: the vocabulary of `state_diff.time` belongs to one
reader (`world.mechanics.read_time_diff`); a clock position may arrive under
either name the engine uses for it; a diff that asserts only a duration is an
advance, not silence; and a diff whose keys the reader cannot read must SAY
so rather than hold the clock quietly.
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

    def test_known_metadata_alone_is_not_a_refusal(self):
        """`display` and `time_scale` are the clock's own vocabulary echoed
        back (32 and 8 times in the corpus). They carry no position, so the
        clock holds — but nothing is unreadable, so nothing is reported."""
        from world.mechanics import read_time_diff

        assert read_time_diff(100.0, {
            "display": "later", "time_scale": "scene"}) == (100.0, None, [])

    def test_a_non_dict_reads_as_no_claim(self):
        from world.mechanics import read_time_diff

        assert read_time_diff(100.0, None) == (100.0, None, [])
        assert read_time_diff(100.0, "later") == (100.0, None, [])

    def test_the_display_phrase_prefers_the_canonical_name(self):
        from world.mechanics import time_diff_display

        assert time_diff_display({"display": "moments later"}) == (
            "moments later")
        assert time_diff_display({"display_advance": "an hour later",
                                  "display": "moments later"}) == (
            "an hour later")
        assert time_diff_display({}) == ""
        assert time_diff_display(None) == ""

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
        from agents.director import _sleep_elapsed

        assert _sleep_elapsed({"started_at_seconds": 100.0},
                              {"elapsed_seconds": 0.0},
                              {"start_seconds": 1000, "duration_seconds": 60,
                               "end_seconds": 1060}) == 960.0

    def test_no_time_diff_falls_to_the_engine_clock(self):
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
        "location": "Kessler Tower", "time": "night",
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
        chat_id = _make_chat(temp_db)
        ctx, clock = _run_turn(
            temp_db, chat_id, {"time": {"seconds": 300}},
            clock={"elapsed_seconds": 1136.0, "display": "moments later"})
        assert clock["elapsed_seconds"] == 1136.0
        assert any("no clock position" in w for w in ctx.warnings)

    def test_the_display_synonym_reaches_the_clock_and_the_scene(self, temp_db):
        chat_id = _make_chat(temp_db)
        ctx, clock = _run_turn(
            temp_db, chat_id,
            {"time": {"elapsed_seconds": 1200.0, "display": "moments later"}},
            clock={"elapsed_seconds": 1000.0, "display": "now"})
        assert clock["elapsed_seconds"] == 1200.0
        assert clock["display"] == "moments later"
        assert temp_db.wget(chat_id, "scene", {})["time"] == "moments later"

    def test_the_canonical_shape_commits_exactly_as_before(self, temp_db):
        chat_id = _make_chat(temp_db)
        ctx, clock = _run_turn(
            temp_db, chat_id,
            {"time": {"start_seconds": 430, "duration_seconds": 25,
                      "end_seconds": 455, "mode": "action", "explicit": False,
                      "display_advance": "moments later"}},
            clock={"elapsed_seconds": 430.0, "display": "now"})
        assert clock["elapsed_seconds"] == 455.0
        assert clock["display"] == "moments later"
        assert not [w for w in ctx.warnings if "state_diff.time" in w]

    def test_a_backwards_claim_still_reports_backwards(self, temp_db):
        chat_id = _make_chat(temp_db)
        ctx, clock = _run_turn(
            temp_db, chat_id,
            {"time": {"end_seconds": 30, "duration_seconds": 30}},
            clock={"elapsed_seconds": 5400.0, "display": "now"})
        assert clock["elapsed_seconds"] == 5430.0
        assert any("backwards" in w for w in ctx.warnings)
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
