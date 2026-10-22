"""A skip of whole days lands on a part of the day, the resolve is shown
where it landed, and the writer sets the beat's time.

Measured (the probe story, 2026-10-21, control chat 2 turn 15 = idx 8): the
player wrote "Two days later the wind gets up from the west and the sea comes
white over the rock all morning. Rhona keeps to the kitchen with the stove
going and the log open on the table, writing up the trial of the new
mechanism." Against a clock standing at 13:32:46 (an afternoon):

* the interpretation's encoder wrote one skip, `{duration_seconds: 172800}`
  -- the `time` part could carry "two days" or "morning", never both -- and
  the beat landed in the afternoon two days on, not the morning its account
  is set in;
* the resolve's account, shown that afternoon, ran the weather on "by early
  afternoon", "into the evening" and "until full dark", and its encoder filed
  two more skips (to the evening, 4.4 h; to the night, 2.5 h) -- while the page
  the player read, built from what Rhona perceived, was a morning;
* the night skip was solved from the clock's display-rounded stamp (13.55)
  rather than the clock (13.5461), landed 14 seconds short, at 21:59:46, and
  the beat committed in the evening beside a stamp of 22.0 -- so the next
  beat's decision model, told the time of day from the stamp, was told night,
  and the player's "That night, when Elias comes down from the first watch
  ..." passed nothing.

THREE CLASSES. (1) A count of the story's days and a part of the day are one
skip, `{days, until_phase}`, solved by the engine to where that part of the
day begins on the day counted (`day_cycle.seconds_until(days=)`). (2) Every
reader of where a stage begins -- the decision model, the encoder's solve, the
clock the resolve's encoder is shown, the label beside it, and the commit --
reads one clock: the anchor plus the elapsed seconds, never a stamp rounded
for showing (`day_cycle.clock_hour`, `display_hour`). (3) The writer sets the
time: at a resolve whose input passed over time, the world's account passes
over none of its own (`director_prose.time_is_the_inputs`).
"""

from __future__ import annotations

import json
import random
import time

import pytest

import agents.director as director
from agents import director_prose
from llm import decisions, prompts
from world import day_cycle, mechanics
from world.day_cycle import PHASE_NAMES, hour_of_day, phase_of_hour, seconds_until
from world.mechanics import TIME_DIFF_KEYS, TIME_METADATA_KEYS, beat_time_block
from tests.director_fakes import _fake_agent, _make_ctx

#: The probe story's clock before idx 8 (checkpoint 8 of control.db chat 2):
#: stamped 13.55, standing at 15.75 + 78466 s = 13.546111 -- 13:32:46.
PROBE_CLOCK = {"elapsed_seconds": 78466.0, "display": "afternoon",
               "anchor_hour": 15.75, "day_length_hours": 24.0,
               "hour_of_day": 13.55, "phase": "afternoon"}
#: Where it stands, to the second.
PROBE_HOUR = (15.75 + 78466.0 / 3600.0) % 24.0
#: "Two days later ... all morning": 07:00 on the second day on.
TO_THE_SECOND_MORNING = round((48.0 + 7.0 - PROBE_HOUR) * 3600.0, 1)

#: The input as the player wrote it.
PROBE_INPUT = ("Two days later the wind gets up from the west and the sea comes "
               "white over the rock all morning. Rhona keeps to the kitchen with "
               "the stove going and the log open on the table, writing up the "
               "trial of the new mechanism.")


def _skip(block, *, words="two days later", source="world"):
    """The skip event the encoder's `time` part asks for."""
    return {"source_entity_id": source, "source_event_id": "",
            "event": words.capitalize() + ".", "observable": "",
            "item_names": [words],
            "transforms": [{"item": words, "patch": {"time": dict(block)}}]}


def _step(event, seconds, source="persona:primary", **fields):
    row = {"source_entity_id": source, "event": event, "observable": event,
           "seconds": seconds, "item_names": [], "transforms": []}
    row.update(fields)
    return row


def _resolve_events():
    """The probe's resolve account as its encoder wrote it (llm_capture seq
    6 of turn 15): five steps and, between them, two stretches the account
    passed over -- to the evening, then to full dark."""
    trial = _step("The new clockwork runs on trial through the evening until "
                  "full dark as the pinion skips on each turn.", 0.0, source="world")
    trial["transforms"] = [{"item": "darkness_stretch",
                            "patch": {"time": {"until_phase": "night"}}}]
    trial["item_names"] = ["darkness_stretch"]
    return [
        _step("The swell heaves under the rock, breaking against the west face.",
              1800.0, source="world"),
        _step("Rhona Carrick looks up from the log.", 3.0),
        _step("The wind backs a point and strengthens into the evening.",
              3600.0, source="world"),
        _skip({"until_phase": "evening"}, words="evening stretch"),
        _step("Elias Thorne lights the tower lamp at the hour.", 30.0,
              source="character:1"),
        _step("The pinion cocked against the gear wheel begins to skip.",
              60.0, source="world"),
        trial,
    ]


#: The resolve's own steps, which stand whatever is ruled on its stretches.
RESOLVE_STEPS = 1800.0 + 3.0 + 3600.0 + 30.0 + 60.0
#: Rhona keeping to the kitchen: the interpretation's one priced step.
INPUT_STEP = 120.0


def _stage(monkeypatch, ctx, events, prose, stage):
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": {"prose": prose},
        "director_specialist": {"events": events},
    }))
    run = director.director_interpret if stage == "interpret" else director.director_resolve
    return run(ctx, nonce=0), calls


def _encoder_payload(calls):
    return next(c["payload"] for c in calls if c["step_key"] == "director_specialist")


# ---------------------------------------------------------------------------
# Committing a resolved beat's time, as `tests/test_a_player_can_say_that_
# evening.py` does: a chat of its own holding the clock the beat began on.
# ---------------------------------------------------------------------------

def _scene(**extra):
    scene = {"location": "Tower", "time": "", "time_of_day": "afternoon",
             "rooms": {"kitchen": {"name": "Kitchen", "desc": "A kitchen.",
                                   "adjacent": []}},
             "entities": {}, "positions": {"Mara": "kitchen"},
             "attire": {}, "overlays": {}}
    scene.update(extra)
    return scene


def _commit(temp_db, diff, clock, scene=None):
    """`(stored clock, stored scene, warnings)` after committing `diff`."""
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    from persist.commit import (commit_scene, commit_transit_sweep,
                                prepare_scene_commit)
    cid = temp_db.qi("INSERT INTO chats(name,persona_id,scenario,created) "
                     "VALUES(?,?,?,?)", ("Skip", None, "", time.time()))
    temp_db.wset(cid, "scene", scene or _scene())
    temp_db.wset(cid, "simulation_clock", dict(clock))
    turn_id = temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                         "VALUES(?,?,?,?)", (cid, 8, PROBE_INPUT, time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Skip", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=cid, idx=8,
                      player_input=PROBE_INPUT, created=time.time()),
        cast=[], input=PROBE_INPUT)
    ctx.director_resolve = {"resolved_event": "The weather on the rock.",
                            "dialogue_log": [], "state_diff": diff}
    prepared = prepare_scene_commit(ctx)
    commit_transit_sweep(ctx, 0, prepared=prepared)
    commit_scene(ctx, 0, prepared=prepared)
    return (temp_db.wget(cid, "simulation_clock", {}),
            temp_db.wget(cid, "scene", {}), list(ctx.warnings))


# ---------------------------------------------------------------------------
# 1. A count of days lands on a part of the day
# ---------------------------------------------------------------------------

class TestADayCountLandsOnAPartOfTheDay:

    def test_two_days_later_all_morning_is_the_second_morning_on(self):
        """Not the afternoon two days on (a length of two days), and not the
        third morning (two whole days, then the next morning)."""
        span = seconds_until(PROBE_HOUR, phase="morning", days=2)
        assert span == TO_THE_SECOND_MORNING
        landed = (PROBE_HOUR + span / 3600.0) % 24.0
        assert phase_of_hour(landed) == "morning"
        assert span < 2 * 86400.0 < span + 86400.0

    @pytest.mark.parametrize("hour, days, phase, hours", [
        (23.0, 1, "morning", 8.0),    # the next morning, said late at night
        (1.0, 1, "morning", 6.0),     # ...said after midnight: the night is
                                      # the day before's, so a few hours off
        (5.0, 1, "morning", 26.0),    # ...said once the night has ended
        (2.0, 1, "night", 20.0),      # the next night, said at two: tonight
        (23.0, 1, "night", 23.0),     # ...said in the night: tomorrow's
        (15.0, 7, "dawn", 159.0),     # a week on, at dawn
        (20.0, 1, "evening", 23.5),   # the next evening, said in the evening
        (15.0, 2, "19:00", 52.0),     # a reading lands on the reading
    ])
    def test_the_day_turns_where_its_night_ends(self, hour, days, phase, hours):
        assert day_cycle.DAY_TURNS_AT * 24.0 == 4.5
        assert seconds_until(hour, phase=phase, days=days) == hours * 3600.0

    def test_every_part_of_the_day_lands_inside_it_days_on(self):
        for target in PHASE_NAMES:
            for start in [h + 0.37 for h in range(24)]:
                for days in (1, 2, 7):
                    span = seconds_until(start, phase=target, days=days)
                    landed = start + span / 3600.0
                    assert phase_of_hour(landed % 24.0) == target, (target, start, days)
                    # On the day counted: more than days-1 whole days on, and
                    # never a whole day past it.
                    assert (days - 1) * 24.0 < span / 3600.0 < (days + 1) * 24.0

    def test_a_count_on_a_thirty_hour_world_counts_its_days(self):
        """Morning there runs 8.75-13.75; "the next morning" said at 10.0 is
        the start of tomorrow's, 28.75 hours on."""
        span = seconds_until(10.0, phase="morning", days=1, day_length=30.0)
        assert phase_of_hour((10.0 + span / 3600.0) % 30.0, 30.0) == "morning"
        assert span == 28.75 * 3600.0

    def test_a_count_that_is_not_a_whole_number_of_days_solves_nothing(self):
        for bad in (1.5, -1, True, "two"):
            assert seconds_until(15.0, phase="morning", days=bad) is None

    def test_the_solve_writes_one_span_and_keeps_the_record(self):
        events = [_skip({"days": 2, "until_phase": "morning"}),
                  _step("Rhona keeps to the kitchen.", INPUT_STEP)]
        rows, transforms = director_prose.ledger_from_events(
            events, start_hour=PROBE_HOUR)
        assert transforms[1][0]["patch"]["time"] == {
            "days": 2, "until_phase": "morning",
            "duration_seconds": TO_THE_SECOND_MORNING}
        assert [row.get("seconds") for row in rows] == [None, INPUT_STEP]

    def test_a_count_alone_is_whole_days_of_this_worlds_day(self):
        block = {"days": 2}
        assert director_prose.solve_skip(block, 13.5, 30.0) == 2 * 30 * 3600.0
        assert block["duration_seconds"] == 216000.0
        # ...and is the engine's sum, not a length the account stated.
        assert not mechanics._states_a_length(block)

    def test_a_count_that_is_not_whole_days_is_said_and_the_part_still_lands(self):
        block = {"days": "a few", "until_phase": "morning"}
        events = [_skip(block)]
        _rows, transforms = director_prose.ledger_from_events(
            events, start_hour=20.0)
        assert transforms[1][0]["patch"]["time"]["duration_seconds"] == 11 * 3600.0
        assert director_prose.unsolved_skips(events) == ["a few days"]

    def test_an_unanchored_day_still_passes_the_days(self):
        """No time of day to solve the part of the day from: the days pass,
        and the part of the day is said where the solve was tried (the
        commit then makes it the time of day, `_unanchored_phase`)."""
        block = {"days": 2, "until_phase": "evening"}
        assert director_prose.solve_skip(block, None, 24.0) == 172800.0
        assert director_prose.unsolved_skips([_skip(block)], anchored=False) == [
            "evening"]
        assert director_prose.unsolved_skips([_skip(dict(block))]) == []

    def test_a_length_written_beside_where_the_skip_lands_is_set_aside(self):
        """Live, 2026-10-21 (the lighthouse replayed, chat 3 turn 25): the
        interpret encoder wrote the days twice, once as a length, and the
        length won -- the cast lived to the afternoon two days on and the
        beat ran on to 22:15. Where the block names where it lands, that
        decides it."""
        block = {"days": 2, "until_phase": "morning", "duration_seconds": 172800.0}
        assert director_prose.solve_skip(block, PROBE_HOUR, 24.0) == \
            TO_THE_SECOND_MORNING
        assert block["duration_seconds"] == TO_THE_SECOND_MORNING
        later = {"until_phase": "evening", "duration_seconds": 600.0}
        assert director_prose.solve_skip(later, PROBE_HOUR, 24.0) == \
            seconds_until(PROBE_HOUR, phase="evening")

    def test_a_length_still_stands_alone_and_beside_a_part_already_reached(self):
        assert director_prose.solve_skip({"duration_seconds": 3600.0},
                                         PROBE_HOUR, 24.0) == 3600.0
        # Already evening, no days: the length is the only word on how much
        # time passes, so it stands.
        block = {"until_phase": "evening", "duration_seconds": 7200.0}
        assert director_prose.solve_skip(block, 20.0, 24.0) == 7200.0

    def test_resolving_a_solved_block_from_the_same_hour_changes_nothing(self):
        block = {"days": 2, "until_phase": "morning"}
        first = director_prose.solve_skip(block, PROBE_HOUR, 24.0)
        assert director_prose.solve_skip(block, PROBE_HOUR, 24.0) == first

    def test_days_is_a_key_every_reader_knows(self):
        assert "days" in TIME_METADATA_KEYS and "days" in TIME_DIFF_KEYS
        assert mechanics.skip_days({"days": 2}) == (True, 2)
        assert mechanics.skip_days({"days": 2.0}) == (True, 2)
        assert mechanics.skip_days({"days": 1.5}) == (True, None)
        assert mechanics.skip_days({"days": None}) == (False, None)
        assert mechanics.skip_days({}) == (False, None)

    def test_where_the_input_landed_is_one_record(self):
        onset = {"days": 2, "until_phase": "morning",
                 "duration_seconds": TO_THE_SECOND_MORNING}
        block = beat_time_block({"duration_seconds": 10.0}, onset, None)
        assert block == {"days": 2, "until_phase": "morning",
                         "duration_seconds": TO_THE_SECOND_MORNING + 10.0,
                         "skipped_seconds": TO_THE_SECOND_MORNING,
                         "mode": "time_skip"}
        # A resolve's own part of the day is never stood beside the input's
        # days: the landing is taken whole or not at all.
        mixed = beat_time_block(None, onset, {"until_phase": "night",
                                              "duration_seconds": 3600.0})
        assert mixed["until_phase"] == "night" and "days" not in mixed

    @pytest.mark.parametrize("language", ["en", "ja"])
    def test_the_part_teaches_the_count(self, language):
        chunk = prompts._prompt_card(language)["encoder"]["time"]
        assert "time:{days}" in chunk
        assert "time:{days, until_phase}" in chunk
        for phase in PHASE_NAMES:
            assert phase in chunk

    def test_the_part_states_what_a_count_is(self):
        chunk = prompts._prompt_card("en")["encoder"]["time"]
        assert ("time:{days, until_phase} for a part of the day a number of "
                "whole days on") in chunk
        assert "the same part of a later day takes its days" in chunk
        assert ("Never a length beside days or a part of the day, and never "
                "a position on the clock") in chunk


class TestTheNextMorningWithNoCount:
    """KEPT AS IT WAS (a pin, not a fix): a part of the day with no count is
    where that part of the day NEXT begins -- "the next morning" said in the
    evening is the coming morning, and said in the morning it is reached
    now, which is why the part tells the encoder the same part of a later
    day takes its days."""

    def test_the_next_morning_said_in_the_evening(self):
        assert seconds_until(20.0, phase="morning") == 11.0 * 3600.0

    def test_the_next_morning_said_in_the_morning_is_now(self):
        assert seconds_until(9.0, phase="morning") == 0.0


def test_a_count_of_one_and_no_count_agree_from_the_evening():
    """The two shapes of "the next morning" land on the same morning where
    both are read the same way; only said in the morning do they part."""
    assert seconds_until(20.0, phase="morning", days=1) == seconds_until(
        20.0, phase="morning")
    assert seconds_until(9.0, phase="morning", days=1) == 22.0 * 3600.0


# ---------------------------------------------------------------------------
# 2. The resolve is shown where the input's skip left it, on one clock
# ---------------------------------------------------------------------------

class TestOneClock:

    def test_the_stage_begins_on_the_clock_not_its_stamp(self, temp_db):
        ctx = _make_ctx(temp_db, player_input=PROBE_INPUT)
        temp_db.wset(ctx.chat["id"], "simulation_clock", dict(PROBE_CLOCK))
        hour, length = director_prose.stage_start_hour(ctx, "interpret")
        assert hour == pytest.approx(PROBE_HOUR, abs=1e-9) and length == 24.0
        assert day_cycle.clock_hour(PROBE_CLOCK) == (pytest.approx(PROBE_HOUR, abs=1e-9), 24.0)

    def test_a_stamp_with_no_anchor_is_read_as_stamped(self):
        assert day_cycle.clock_hour({"hour_of_day": 19.0, "day_length_hours": 24.0}) == (19.0, 24.0)
        assert day_cycle.clock_hour({"elapsed_seconds": 0.0, "display": ""}) == (None, 24.0)

    def test_the_stamp_reads_the_part_of_the_day_beside_it(self):
        """The probe's clock after idx 8: 21:59:46 is evening, and its stamp
        read 22.0 -- night."""
        assert day_cycle.display_hour(21.9961) == 21.99
        assert phase_of_hour(day_cycle.display_hour(21.9961)) == phase_of_hour(21.9961) == "evening"
        assert day_cycle.display_hour(6.99611) == 6.99
        assert day_cycle.display_hour(13.546111) == 13.55

    def test_the_commit_stamps_an_hour_that_reads_its_own_phase(self, temp_db):
        """A beat whose steps end ten seconds short of 22:00: the clock and
        the scene say evening, and so must the stamp beside them (rounded to
        the nearest hundredth it read 22.0 -- night)."""
        end = (22.0 - 15.75) * 3600.0 - 10.0 - PROBE_CLOCK["elapsed_seconds"] \
            + 24 * 3600.0
        clock, scene, _ = _commit(temp_db, {"time": {"duration_seconds": end}},
                                  PROBE_CLOCK)
        assert clock["phase"] == "evening" and scene["time_of_day"] == "evening"
        assert phase_of_hour(clock["hour_of_day"]) == "evening"
        assert clock["hour_of_day"] == 21.99

    def test_a_span_priced_to_a_tenth_of_a_second_lands_inside(self):
        """Solved from the clock to the second and rounded to the tenth of a
        second spans are priced to, a skip to where a part of the day begins
        lands within that tenth either side of it, and the clock reads the
        part of the day it was sent to (measured on HEAD: 41% read the part
        before)."""
        rng = random.Random(20261021)
        short = 0
        for _ in range(4000):
            anchor = round(rng.uniform(0.0, 24.0), 4)
            elapsed = float(rng.randint(0, 10 ** 6))
            target = rng.choice(PHASE_NAMES)
            span = seconds_until(hour_of_day(elapsed, anchor), phase=target)
            if span and phase_of_hour(hour_of_day(elapsed + span, anchor)) != target:
                short += 1
        assert short == 0

    @pytest.mark.usefixtures("prose_director")
    def test_full_dark_lands_in_the_night(self, temp_db, monkeypatch):
        """The resolve's own "until full dark", in a beat whose input passed
        no time, solved from the probe's clock: the night, and every field
        of the record says so."""
        ctx = _make_ctx(temp_db, player_input="Rhona writes up the trial.")
        temp_db.wset(ctx.chat["id"], "simulation_clock", dict(PROBE_CLOCK))
        out, _ = _stage(monkeypatch, ctx, _resolve_events(),
                        "The swell builds into the evening and full dark.", "resolve")
        clock, scene, _ = _commit(temp_db, {"time": out["state_diff"]["time"]},
                                  PROBE_CLOCK)
        assert clock["phase"] == "night"
        assert scene["time_of_day"] == "night"
        assert phase_of_hour(clock["hour_of_day"]) == "night"
        assert phase_of_hour(day_cycle.clock_hour(clock)[0]) == "night"

    def test_a_clock_re_anchored_onto_a_boundary_reads_it_back(self, temp_db):
        """A passage phrase naming where a skip lands re-anchors the clock to
        the START of that part of the day (`_advance_day_cycle`'s "a skip
        that names where it lands lands there"). Stored to four decimals, the
        anchor carried the clock 0.16 seconds back across that boundary, so
        every later reader of the stored clock -- which now reads the anchor
        and the elapsed seconds, `day_cycle.clock_hour` -- read the
        afternoon beside a phase of dusk."""
        clock = {"elapsed_seconds": 0.0, "display": "afternoon",
                 "anchor_hour": 15.0, "day_length_hours": 24.0,
                 "hour_of_day": 15.0, "phase": "afternoon"}
        stored, _scene_after, warnings = _commit(
            temp_db, {"time": {"duration_seconds": 2.0,
                               "display_advance": "by dusk"}}, clock)
        assert stored["elapsed_seconds"] == 2.0
        assert [w for w in warnings if "time of day landed" in w]
        assert stored["phase"] == "dusk"
        assert phase_of_hour(day_cycle.clock_hour(stored)[0]) == "dusk"
        assert phase_of_hour(hour_of_day(stored["elapsed_seconds"],
                                         stored["anchor_hour"])) == "dusk"


@pytest.mark.usefixtures("prose_director")
class TestTheResolveIsShownTheMorning:

    def _interpret(self, temp_db, monkeypatch, block):
        ctx = _make_ctx(temp_db, player_input=PROBE_INPUT)
        temp_db.wset(ctx.chat["id"], "simulation_clock", dict(PROBE_CLOCK))
        # The label the commit stamped beside that clock, as on the probe.
        scene = temp_db.wget(ctx.chat["id"], "scene", {})
        temp_db.wset(ctx.chat["id"], "scene", dict(scene, time_of_day="afternoon"))
        interp, _ = _stage(monkeypatch, ctx, [
            _skip(block),
            _step("Rhona keeps to the kitchen, writing up the trial.", INPUT_STEP),
        ], "Two days later the sea comes white over the rock all morning. "
           "Rhona keeps to the kitchen.", "interpret")
        ctx.director_interpret = interp
        return ctx, interp

    def test_the_inputs_two_days_and_morning_are_one_stretch(self, temp_db, monkeypatch):
        _ctx, interp = self._interpret(
            temp_db, monkeypatch, {"days": 2, "until_phase": "morning"})
        assert interp["state_assertions"]["time"] == {
            "days": 2, "until_phase": "morning",
            "duration_seconds": TO_THE_SECOND_MORNING}

    def test_the_resolves_encoder_and_decision_model_are_shown_the_morning(
            self, temp_db, monkeypatch, prose_director):
        ctx, _interp = self._interpret(
            temp_db, monkeypatch, {"days": 2, "until_phase": "morning"})
        _out, calls = _stage(monkeypatch, ctx, _resolve_events(),
                             "The swell builds all morning.", "resolve")
        payload = _encoder_payload(calls)
        assert payload["simulation_clock"]["phase"] == "morning"
        assert phase_of_hour(payload["simulation_clock"]["hour_of_day"]) == "morning"
        # The label beside the clock is that clock's, not the afternoon the
        # input left.
        assert payload["time_of_day"] == "morning"
        told = [a["state"] for a in prose_director
                if "TIME OF DAY BEFORE THE PASSAGE" in a["state"]]
        assert "TIME OF DAY BEFORE THE PASSAGE: afternoon" in told[0]   # interpret
        assert "TIME OF DAY BEFORE THE PASSAGE: morning" in told[-1]    # resolve

    def test_that_evening_shows_the_evening_beside_the_evening(
            self, temp_db, monkeypatch):
        """The same two answers in one payload, on the shape built first."""
        ctx, _interp = self._interpret(temp_db, monkeypatch,
                                       {"until_phase": "evening"})
        _out, calls = _stage(monkeypatch, ctx, [
            _step("Mara climbs to the lamp room.", 36, source="character:1")],
            "Mara climbs to the lamp room.", "resolve")
        payload = _encoder_payload(calls)
        assert payload["simulation_clock"]["phase"] == "evening"
        assert payload["time_of_day"] == "evening"


# ---------------------------------------------------------------------------
# 3. The writer sets the time
# ---------------------------------------------------------------------------

def _interp_with(block):
    return {"state_assertions": {"time": dict(block)}} if block else {}


class TestTheWriterSetsTheTime:

    def test_a_resolve_files_no_stretch_after_the_inputs(self):
        notes = []
        kept, held = director_prose.time_is_the_inputs(
            _resolve_events(), _interp_with({"duration_seconds": 172800}),
            warn=notes.append)
        assert held == [{"until_phase": "evening"}, {"until_phase": "night"}]
        # The stretch-only event goes; the step that also carried one keeps
        # everything but its stretch; every step keeps its seconds.
        assert [e["event"] for e in kept] == [
            e["event"] for e in _resolve_events() if e["event"] != "Evening stretch."]
        assert sum(e["seconds"] for e in kept) == RESOLVE_STEPS
        assert not [t for e in kept for t in e["transforms"]
                    if "time" in (t.get("patch") or {})]
        assert notes and "the input set this beat's time" in notes[0]

    @pytest.mark.parametrize("interp", [
        {},                                                   # passed no time
        {"state_assertions": {}},                             # the ladder refused it
        {"state_assertions": {"time": {"start_seconds": 0,    # the retired contract
                                       "end_seconds": 30}}},
    ])
    def test_a_resolve_whose_input_passed_no_time_keeps_its_stretch(self, interp):
        """Where the ladder refused the input's skip (`actor_only`,
        `explicit_outcomes`) the resolve's account decides whether the time
        passes, and a beat whose input passed none is not this rule's."""
        kept, held = director_prose.time_is_the_inputs(_resolve_events(), interp)
        assert held == [] and kept == _resolve_events()

    def test_the_resolve_is_not_asked_the_time_when_the_input_set_it(
            self, temp_db, monkeypatch):
        asked = []

        def answer(state, questions):
            asked.append(dict(questions))
            return {key: {"type": "noul", "noul": 0.99} for key in questions}

        monkeypatch.setattr(decisions, "OVERRIDE", answer)
        ctx = _make_ctx(temp_db, player_input=PROBE_INPUT)
        ctx.director_interpret = dict(ctx.director_interpret, state_assertions={
            "time": {"days": 2, "until_phase": "morning",
                     "duration_seconds": TO_THE_SECOND_MORNING}})
        selected, record = director_prose.select_channels(
            ctx, "resolve", "The swell builds all morning.", {})
        assert "time" not in selected and "time" not in asked[-1]
        assert record["time_set_by_input"]["days"] == 2
        # The interpretation is asked as before, and so is a resolve whose
        # input passed no time.
        selected, _ = director_prose.select_channels(
            ctx, "interpret", "Two days later.", {})
        assert "time" in selected
        ctx.director_interpret = dict(ctx.director_interpret, state_assertions={})
        selected, _ = director_prose.select_channels(
            ctx, "resolve", "Hours later.", {})
        assert "time" in selected


@pytest.mark.usefixtures("prose_director")
class TestTheProbeBeatReplayed:
    """The probe's idx 8 through both Director stages and the commit, with
    the resolve's encoder events as recorded and the interpretation's skip
    in each shape: as the encoder wrote it, and as the part now asks."""

    def _beat(self, temp_db, monkeypatch, block):
        ctx = _make_ctx(temp_db, player_input=PROBE_INPUT)
        temp_db.wset(ctx.chat["id"], "simulation_clock", dict(PROBE_CLOCK))
        interp, _ = _stage(monkeypatch, ctx, [
            _skip(block),
            _step("Rhona keeps to the kitchen, writing up the trial.", INPUT_STEP),
        ], "Two days later the sea comes white over the rock all morning.",
            "interpret")
        ctx.director_interpret = interp
        out, _ = _stage(monkeypatch, ctx, _resolve_events(),
                        "The swell builds into the evening and full dark.", "resolve")
        record = out["orchestration"]["prose_contract"]
        clock, scene, _ = _commit(temp_db, {"time": out["state_diff"]["time"]},
                                  PROBE_CLOCK)
        return out["state_diff"]["time"], record, clock, scene, ctx

    def test_two_days_later_all_morning_commits_in_the_morning(
            self, temp_db, monkeypatch):
        block, record, clock, scene, _ = self._beat(
            temp_db, monkeypatch, {"days": 2, "until_phase": "morning"})
        assert block["skipped_seconds"] == TO_THE_SECOND_MORNING
        assert block["duration_seconds"] == TO_THE_SECOND_MORNING + INPUT_STEP + RESOLVE_STEPS
        assert [b.get("until_phase") for b in record["time_held"]] == ["evening", "night"]
        assert clock["elapsed_seconds"] == (
            78466.0 + TO_THE_SECOND_MORNING + INPUT_STEP + RESOLVE_STEPS)
        assert clock["phase"] == "morning" and scene["time_of_day"] == "morning"

    def test_the_skip_as_the_encoder_wrote_it_ends_where_its_account_does(
            self, temp_db, monkeypatch):
        """`{duration_seconds: 172800}`: the afternoon two days on, where the
        stretch the input set lands -- not the 22:00 the resolve's own two
        stretches carried it to."""
        block, record, clock, scene, _ = self._beat(
            temp_db, monkeypatch, {"duration_seconds": 172800})
        assert block["skipped_seconds"] == 172800.0
        assert clock["elapsed_seconds"] == 78466.0 + 172800.0 + INPUT_STEP + RESOLVE_STEPS
        assert clock["phase"] == "afternoon"

    def test_that_night_then_passes_the_day(self, temp_db, monkeypatch):
        """The player's next beat, "That night, when Elias comes down from
        the first watch ...": from the morning the beat committed in, the
        night is thirteen hours off -- not reached already."""
        _block, _record, clock, _scene, _ = self._beat(
            temp_db, monkeypatch, {"days": 2, "until_phase": "morning"})
        ctx = _make_ctx(temp_db, player_input="That night, when Elias comes down ...")
        temp_db.wset(ctx.chat["id"], "simulation_clock", dict(clock))
        hour, length = director_prose.stage_start_hour(ctx, "interpret")
        assert seconds_until(hour, phase="night", day_length=length) > 13 * 3600.0
