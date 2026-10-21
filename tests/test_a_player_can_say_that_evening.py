"""A beat that passes over time moves the story clock by it.

Measured (the probe story, 2026-10-20, chat 1 turn 5): the player wrote "That
evening, with the lamp lit and the first watch set, Rhona sits at the kitchen
table with a mug of tea ...". The interpretation wrote her sit as a standing
correction and opened its account "Evening at the tower:", but nothing wrote
the beat's `time` -- `time` had been no channel's since 2026-09-20, when it
left the spatial hand because a hand saw a slice of the beat and could not sum
it -- so the beat's time was the sum of its steps: `{duration_seconds: 44}`
against a clock at 15:50. The keeper went on in the afternoon. In the owner's
own play database the same class: "You wake up a few hours later somewhere
incredibly tight." (chats 101, 102, 112, 113, idx 70) moved the clock on 0
of 4 beats.

THE CLASS: a beat whose account passes over time it does not show -- a
stretch nothing in it fills, or a later part of the day -- writes `time`, and
the engine moves its clock by that span, with everything windowed on the
clock following. The steps' own seconds stay the engine's sum
(`beat_time_from_spans`); the stretch passed over is the one claim no sum of
steps can carry, so it is written: by the encoder (`encoder.time`) when the
decision model grants it (`jev_questions.time`), as a length, or as a part of
the day the engine solves against its clock (`director_prose.solve_skip`).
"""

from __future__ import annotations

import json
import time

import pytest

import agents.director as director
from agents import director_prose
from agents.director import SPECIALISTS, channel_serves_stage
from llm import decisions, prompts, schemas
from llm.schemas import validate_llm_output
from story.scene import set_player_authority
from world.causality import compile_transforms
from world.day_cycle import PHASE_NAMES, phase_of_hour, seconds_until
from world.mechanics import (TIME_DIFF_KEYS, beat_end_elapsed,
                             beat_time_block, beat_time_from_spans,
                             skip_seconds)
from tests.director_fakes import _fake_agent, _make_ctx

#: The probe story's clock before turn 5 (checkpoint 5 of control.db chat 1).
PROBE_CLOCK = {"elapsed_seconds": 338.0,
               "display": "afternoon, eighteen minutes past two",
               "anchor_hour": 15.75, "day_length_hours": 24.0,
               "hour_of_day": 15.84, "phase": "afternoon"}
#: 15.84 -> 19:30, where evening begins on a 24-hour day.
TO_EVENING = round((19.5 - 15.84) * 3600.0, 1)


def _to_evening(clock):
    """The same stretch solved from the clock the engine KEEPS -- its anchor
    plus its elapsed seconds -- rather than from the hundredth of an hour it
    is stamped and shown at: what `director_prose.stage_start_hour` reads
    since 2026-10-21 (`day_cycle.clock_hour`). For the probe's clock that is
    15.8439 rather than 15.84, and the 14 seconds between them are the class
    `tests/test_two_days_later_all_morning.py` closes: solved from a stamp,
    the probe story's "until full dark" landed at 21:59:46, in the evening."""
    return round((19.5 - (clock["anchor_hour"]
                          + clock["elapsed_seconds"] / 3600.0)) * 3600.0, 1)


#: The probe beat's evening as the Director stages solve it.
ON_THE_CLOCK = _to_evening(PROBE_CLOCK)


def _skip(until_phase=None, duration=None, *, source_event_id=""):
    """The skip event the encoder's `time` part asks for: no actor, no
    observable, no seconds of its own, its item the account's words."""
    block = {}
    if until_phase is not None:
        block["until_phase"] = until_phase
    if duration is not None:
        block["duration_seconds"] = duration
    return {"source_entity_id": "world", "source_event_id": source_event_id,
            "event": "That evening.", "observable": "",
            "item_names": ["that evening"],
            "transforms": [{"item": "that evening", "patch": {"time": block}}]}


def _step(event, seconds, source="persona:primary", **fields):
    row = {"source_entity_id": source, "event": event, "observable": event,
           "seconds": seconds, "item_names": [], "transforms": []}
    row.update(fields)
    return row


# ---------------------------------------------------------------------------
# 1. A later part of the day is a span from the clock
# ---------------------------------------------------------------------------

class TestAPartOfTheDayIsASpan:

    def test_afternoon_to_evening_is_the_probe_story_beat(self):
        assert seconds_until(15.84, phase="evening") == TO_EVENING

    def test_morning_to_evening(self):
        assert seconds_until(9.0, phase="evening") == 10.5 * 3600

    def test_evening_to_the_next_morning_crosses_midnight(self):
        assert seconds_until(20.0, phase="morning") == 11.0 * 3600
        assert seconds_until(23.0, phase="dawn") == 7.0 * 3600

    def test_a_part_of_the_day_already_reached_passes_nothing(self):
        """"That evening" said in the evening is now."""
        assert seconds_until(20.0, phase="evening") == 0.0

    def test_it_lands_where_the_part_of_the_day_begins(self):
        """Every phase from every hour: the clock lands inside the phase it
        was sent to, and at its first minute, never past it."""
        for target in PHASE_NAMES:
            for start in [h + 0.25 for h in range(24)]:
                span = seconds_until(start, phase=target)
                assert span is not None, (target, start)
                landed = (start + span / 3600.0) % 24.0
                assert phase_of_hour(landed) == target, (target, start)
                if span:
                    assert phase_of_hour((landed - 0.05) % 24.0) != target

    def test_a_label_is_read_by_the_engines_own_reader(self):
        """`label_phase` and `clock_reading_hour`, the readers every written
        time of day goes through: a reading lands on its hour, another word
        for a part of the day lands on that part, and a word for none is
        nothing to solve."""
        assert seconds_until(15.0, phase="19:00") == 4.0 * 3600
        assert seconds_until(15.0, phase="sunset") == seconds_until(15.0, phase="dusk")
        assert seconds_until(15.0, phase="moonrise") is None


# ---------------------------------------------------------------------------
# 2. The encoder's part is on the schema
# ---------------------------------------------------------------------------

class TestTheEncoderWritesIt:

    def test_time_is_an_owned_channel_at_both_stages(self):
        assert "time" in SPECIALISTS["spatial"]["channels"]
        assert "time" in schemas.SPECIALIST_CHANNELS["director_spatial"]
        for stage in ("interpret", "resolve"):
            assert channel_serves_stage("time", stage)
            assert "time" in director_prose.candidate_channels(stage)

    def test_the_skip_event_reaches_its_owner(self):
        """It validates as the encoder writes it, and the owner split hands
        it to the spatial owner: a channel no owner holds is dropped out loud
        (`director_prose.run`), which is where the probe beat's evening
        would have gone."""
        parsed, warnings = validate_llm_output(
            "director_specialist", {"events": [_skip("evening")]})
        assert not warnings
        patch = parsed["events"][0]["transforms"][0]["patch"]
        clean, dropped = schemas.validated_specialist_patch_channels(
            "director_spatial", patch)
        assert not dropped and clean["time"] == {"until_phase": "evening"}
        held = {director_prose.CTX_KEY: {
            "transforms": {1: [{"item": "that evening", "patch": patch}]},
            "channels": ["time"]}}
        plan, answer_for = director_prose.dispatch(held, "resolve")
        assert "time" in plan["spatial"]["scope"]
        answer = answer_for("spatial", {"ledger_items": [{"chrono_id": 1}]})
        assert answer["results"][0]["transforms"] == [
            {"item": "that evening", "patch": {"time": {"until_phase": "evening"}}}]

    def test_every_key_the_part_asks_for_is_one_the_reader_knows(self):
        for language in ("en", "ja"):
            chunk = prompts._prompt_card(language)["encoder"]["time"]
            for key in ("duration_seconds", "until_phase"):
                assert key in chunk, language
                assert key in TIME_DIFF_KEYS
            for phase in PHASE_NAMES:
                assert phase in chunk, (language, phase)

    @pytest.mark.parametrize("language", ["en", "ja"])
    def test_the_part_ships_only_when_granted(self, language):
        chunk = prompts._prompt_card(language)["encoder"]["time"].strip()
        first = chunk.splitlines()[0][:40]
        assert first in prompts.unified_specialist_prompt(["time"], language, [])
        assert first not in prompts.unified_specialist_prompt(["poses"], language, [])

    def test_the_part_states_the_class_and_what_it_is_not(self):
        chunk = prompts._prompt_card("en")["encoder"]["time"]
        assert "passes over time it does not show" in chunk
        assert "never for how long its own steps take" in chunk
        assert "A time someone only speaks of -- to come, or gone by -- passes nothing." in chunk
        assert "never a position on the clock" in chunk


# ---------------------------------------------------------------------------
# 3. The decision model is asked, and told the time of day it was
# ---------------------------------------------------------------------------

def _answers(scores, states=None):
    def answer(state, questions):
        if states is not None:
            states.append(state)
        return {key: {"type": "noul", "noul": scores.get(key, 0.0)}
                for key in questions}
    return answer


class TestTheQuestion:

    @pytest.mark.parametrize("language", ["en", "ja"])
    def test_the_question_is_in_both_packs(self, language):
        assert prompts.jev_channel_questions(["time"], language)["time"].strip()

    def test_the_question_states_the_class_and_its_exclusion(self):
        text = prompts.jev_channel_questions(["time"], "en")["time"]
        assert "a stretch nothing in it fills" in text
        assert "a later part of the day" in text
        assert "Answer no for how long what it shows takes, however long that is" in text
        assert "only speaks of a time to come or gone by" in text

    @pytest.mark.parametrize("stage", ["interpret", "resolve"])
    def test_a_yes_grants_the_part_and_a_no_does_not(self, temp_db, monkeypatch, stage):
        monkeypatch.setattr(decisions, "OVERRIDE", _answers({"time": 0.9}))
        ctx = _make_ctx(temp_db)
        selected, _record = director_prose.select_channels(
            ctx, stage, "Hours later she wakes.", {})
        assert "time" in selected
        monkeypatch.setattr(decisions, "OVERRIDE", _answers({"time": 0.1}))
        selected, _record = director_prose.select_channels(
            ctx, stage, "She talks for an hour.", {})
        assert "time" not in selected

    def test_the_state_says_what_part_of_the_day_it_was(self, temp_db, monkeypatch):
        """"Evening at the tower:" is a skip only against an afternoon, and
        nothing in the passage says which."""
        states = []
        monkeypatch.setattr(decisions, "OVERRIDE", _answers({}, states))
        ctx = _make_ctx(temp_db)
        director_prose.select_channels(ctx, "interpret", "Evening at the tower.", {})
        assert "TIME OF DAY BEFORE" not in states[-1]   # no anchor, no line
        temp_db.wset(ctx.chat["id"], "simulation_clock", dict(PROBE_CLOCK))
        _sel, record = director_prose.select_channels(
            ctx, "interpret", "Evening at the tower.", {})
        assert "TIME OF DAY BEFORE THE PASSAGE: afternoon" in states[-1]
        assert record["before"] == "afternoon"

    def test_at_resolve_it_is_the_time_the_input_left(self, temp_db, monkeypatch):
        states = []
        monkeypatch.setattr(decisions, "OVERRIDE", _answers({}, states))
        ctx = _make_ctx(temp_db)
        temp_db.wset(ctx.chat["id"], "simulation_clock", dict(PROBE_CLOCK))
        ctx.director_interpret = dict(ctx.director_interpret, state_assertions={
            "time": {"until_phase": "evening", "duration_seconds": TO_EVENING}})
        director_prose.select_channels(ctx, "resolve", "He climbs to the lamp.", {})
        assert "TIME OF DAY BEFORE THE PASSAGE: evening" in states[-1]


# ---------------------------------------------------------------------------
# 4. The beat's time: the stretch passed over, then the steps
# ---------------------------------------------------------------------------

class TestTheBeatsTime:

    def test_the_stretch_is_solved_where_it_falls_in_the_account(self):
        rows, transforms = director_prose.ledger_from_events(
            [_skip("evening"), _step("Rhona sits.", 0), _step("She speaks.", 8)],
            start_hour=PROBE_CLOCK["hour_of_day"])
        assert transforms[1][0]["patch"]["time"] == {
            "until_phase": "evening", "duration_seconds": TO_EVENING}
        assert [row.get("seconds") for row in rows] == [None, 0, 8]

    def test_a_step_named_by_its_end_is_priced_after_the_stretch(self):
        """A wait until dark after "that evening" is no wait at all: the
        evening is dark (`SUN_LIGHT`)."""
        rows, _ = director_prose.ledger_from_events(
            [_skip("evening"), _step("They wait for dark.", None, until_light="dark")],
            start_hour=15.84)
        assert rows[1]["seconds"] == 0.0

    def test_two_stretches_in_one_account_are_one_cumulative_reading(self):
        events = [_skip(duration=3600.0), _step("She works.", 60), _skip("evening")]
        rows, transforms = director_prose.ledger_from_events(events, start_hour=12.0)
        second = transforms[3][0]["patch"]["time"]
        own = round((19.5 - (12.0 + 1.0 + 60 / 3600.0)) * 3600.0, 1)
        assert second["skipped_seconds"] == own
        assert second["duration_seconds"] == 3600.0 + own
        compiled, _history, _rejected = compile_transforms(
            [{"chrono_id": chrono, "item_id": 1, "patch": transform["patch"]}
             for chrono, kept in transforms.items() for transform in kept],
            allowed_channels={"time"})
        assert skip_seconds(compiled["time"]) == 3600.0 + own

    def test_solving_the_same_account_twice_counts_each_stretch_once(self):
        """A repair re-reads the encoder's events; a cumulative reading must
        not be taken for the second stretch's own length."""
        events = [_skip(duration=3600.0), _step("She works.", 60), _skip("evening")]
        _rows, first = director_prose.ledger_from_events(events, start_hour=12.0)
        before = dict(first[3][0]["patch"]["time"])
        _rows, again = director_prose.ledger_from_events(events, start_hour=12.0)
        assert again[3][0]["patch"]["time"] == before

    def test_a_length_that_is_not_a_number_states_nothing_and_is_said(self):
        block = {"duration_seconds": "a few hours"}
        assert beat_time_block({"duration_seconds": 44.0}, None, dict(block)) == {
            "duration_seconds": 44.0}
        assert beat_time_block(None, None, dict(block)) is None
        assert director_prose.unsolved_skips([_skip(duration="a few hours")]) == [
            "a few hours"]
        assert director_prose.unsolved_skips([_skip("moonrise")]) == ["moonrise"]

    def test_the_stretch_and_the_steps_add(self):
        steps = {"duration_seconds": 44.0}
        onset = {"until_phase": "evening", "duration_seconds": TO_EVENING}
        block = beat_time_block(steps, onset, None)
        assert block == {"until_phase": "evening",
                         "duration_seconds": TO_EVENING + 44.0,
                         "skipped_seconds": TO_EVENING, "mode": "time_skip"}
        assert beat_end_elapsed(338.0, block, floor=True)[0] == 338.0 + TO_EVENING + 44.0

    def test_a_length_told_twice_counts_once_and_two_lengths_both_count(self):
        steps = {"duration_seconds": 10.0}
        hours = {"duration_seconds": 10800.0}
        assert beat_time_block(steps, hours, dict(hours))["duration_seconds"] == 10810.0
        assert beat_time_block(steps, hours, {"duration_seconds": 3600.0}
                               )["duration_seconds"] == 14410.0

    def test_a_part_of_the_day_already_reached_leaves_the_floor_to_charge(self):
        """Solved to 0 with nothing priced is a beat that said nothing about
        time; a stated zero is a beat saying none passed."""
        reached = beat_time_block(None, None,
                                  {"until_phase": "evening", "duration_seconds": 0.0})
        assert reached == {"until_phase": "evening"}
        _elapsed, _displaced, refused, floored = beat_end_elapsed(
            338.0, reached, floor=True)
        assert floored and refused == []    # a label, never a refused claim
        stated = beat_time_block(None, None, {"duration_seconds": 0})
        assert beat_end_elapsed(338.0, stated, floor=True)[:2] == (338.0, None)

    def test_a_beat_with_no_stretch_is_its_steps_exactly_as_before(self):
        assert beat_time_block({"duration_seconds": 44.0}, None, None) == {
            "duration_seconds": 44.0}
        assert beat_time_block(None, None, None) is None
        assert beat_time_block(None, None, {}) is None
        legacy = {"start_seconds": 0, "end_seconds": 30}
        assert beat_time_block({"duration_seconds": 5.0}, None, legacy) == legacy


# ---------------------------------------------------------------------------
# 5. End to end through both Director stages
# ---------------------------------------------------------------------------

def _stage(temp_db, monkeypatch, ctx, events, prose, stage):
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": {"prose": prose},
        "director_specialist": {"events": events},
    }))
    run = director.director_interpret if stage == "interpret" else director.director_resolve
    return run(ctx, nonce=0), calls


@pytest.mark.usefixtures("prose_director")
class TestThroughTheDirector:

    def _probe_ctx(self, temp_db):
        ctx = _make_ctx(temp_db, player_input=(
            "That evening, with the lamp lit and the first watch set, I sit at "
            'the kitchen table. "Eleven years out here?"'))
        temp_db.wset(ctx.chat["id"], "simulation_clock", dict(PROBE_CLOCK))
        return ctx

    def test_the_inputs_stretch_is_the_beats(self, temp_db, monkeypatch):
        ctx = self._probe_ctx(temp_db)
        interp, _ = _stage(temp_db, monkeypatch, ctx, [
            _skip("evening"),
            _step("Eleven years out here?", 8, speech=True, observable=""),
        ], 'Evening at the tower. She asks, "Eleven years out here?"', "interpret")
        assert interp["state_assertions"]["time"] == {
            "until_phase": "evening", "duration_seconds": ON_THE_CLOCK}
        ctx.director_interpret = interp
        out, calls = _stage(temp_db, monkeypatch, ctx, [
            _step("Mara climbs to the lamp room.", 36, source="character:1"),
        ], "Mara climbs to the lamp room.", "resolve")
        block = out["state_diff"]["time"]
        assert block["skipped_seconds"] == ON_THE_CLOCK
        assert block["mode"] == "time_skip"
        assert block["duration_seconds"] == ON_THE_CLOCK + 8 + 36
        # The resolve's encoder is shown the evening, not the afternoon the
        # input left: a part of the day its clock already stands in is now.
        payload = next(c["payload"] for c in calls if c["step_key"] == "director_specialist")
        assert payload["simulation_clock"]["phase"] == "evening"
        assert payload["simulation_clock"]["elapsed_seconds"] == 338.0 + ON_THE_CLOCK + 8
        stored = temp_db.wget(ctx.chat["id"], "simulation_clock", {})
        assert stored["elapsed_seconds"] == 338.0   # nothing moved before commit

    def test_the_worlds_own_stretch_at_resolve(self, temp_db, monkeypatch):
        ctx = self._probe_ctx(temp_db)
        out, _ = _stage(temp_db, monkeypatch, ctx, [
            _skip(duration=10800.0), _step("Mara wakes.", 5, source="character:1"),
        ], "Hours later, Mara wakes.", "resolve")
        assert out["state_diff"]["time"]["duration_seconds"] == 10805.0
        assert out["state_diff"]["time"]["skipped_seconds"] == 10800.0

    def test_an_ordinary_beat_is_its_steps(self, temp_db, monkeypatch):
        ctx = self._probe_ctx(temp_db)
        out, calls = _stage(temp_db, monkeypatch, ctx, [
            _step("Mara nods.", 2, source="character:1")], "Mara nods.", "resolve")
        assert out["state_diff"]["time"] == {"duration_seconds": 2.0}
        payload = next(c["payload"] for c in calls if c["step_key"] == "director_specialist")
        assert payload["simulation_clock"] == PROBE_CLOCK


# ---------------------------------------------------------------------------
# 6. Passing time is authorship: the ladder rules on it
# ---------------------------------------------------------------------------

class TestTheLadder:

    def _inputs(self, mode):
        return [{"entity_id": "persona:primary", "authority_mode": mode,
                 "events": [{"type": "raw_input", "event_id": "turn:6:player:0:raw"}]}]

    def _events(self):
        sits = _step("Rhona sits at the kitchen table.", 3,
                     source_event_id="turn:6:player:0:raw")
        return [_skip("evening", source_event_id="turn:6:player:0:raw"), sits]

    def test_world_author_keeps_it(self):
        kept, refused = director_prose.skip_is_authorship(
            self._events(), self._inputs("world_author"))
        assert kept == self._events() and refused == []

    @pytest.mark.parametrize("mode", ["actor_only", "explicit_outcomes"])
    def test_a_rung_without_authorship_refuses_it_whole(self, mode):
        notes = []
        kept, refused = director_prose.skip_is_authorship(
            self._events(), self._inputs(mode), warn=notes.append)
        assert [event["event"] for event in kept] == ["Rhona sits at the kitchen table."]
        assert refused == [{"claim_id": "time", "kind": "world", "mode": mode,
                            "channel": "time", "time": {"until_phase": "evening"}}]
        assert notes

    def test_only_the_skip_leaves_an_event_that_carries_more(self):
        both = dict(_step("Evening; she sits.", 3, source_event_id="turn:6:player:0:raw"),
                    transforms=[{"item": "Rhona", "patch": {
                        "time": {"until_phase": "evening"},
                        "poses": {"Rhona": {"posture": "seated"}}}}])
        kept, refused = director_prose.skip_is_authorship(
            [both], self._inputs("actor_only"))
        assert kept[0]["transforms"] == [{"item": "Rhona", "patch": {
            "poses": {"Rhona": {"posture": "seated"}}}}]
        assert len(refused) == 1

    @pytest.mark.usefixtures("prose_director")
    def test_the_refusal_is_put_in_front_of_the_resolving_director(
            self, temp_db, monkeypatch):
        ctx = _make_ctx(temp_db, player_input="Hours later, I wake.")
        temp_db.wset(ctx.chat["id"], "simulation_clock", dict(PROBE_CLOCK))
        set_player_authority(ctx.chat["id"], "actor_only")
        interp, _ = _stage(temp_db, monkeypatch, ctx, [_skip(duration=10800.0)],
                           "Hours later, the Stranger wakes.", "interpret")
        for key in ("state_assertions", "onset_state_assertions"):
            assertions = interp.get(key) or {}
            assert "time" not in assertions, key
            for step in assertions.get("causal_steps") or []:
                assert "time" not in (step.get("patch") or {}), key
                assert not [t for t in step.get("transforms") or []
                            if "time" in (t.get("patch") or {})], key
        assert {"claim_id": "time", "kind": "world", "mode": "actor_only",
                "channel": "time", "time": {"duration_seconds": 10800.0}} \
            in interp["authority_downgrades"]
        assert interp["orchestration"]["prose_contract"]["time_refused"]


# ---------------------------------------------------------------------------
# 7. The commit: the clock moves, and what is windowed on it follows
# ---------------------------------------------------------------------------

def _chat(temp_db):
    return temp_db.qi("INSERT INTO chats(name,persona_id,scenario,created) "
                      "VALUES(?,?,?,?)", ("Skip", None, "", time.time()))


def _commit_ctx(temp_db, cid, diff):
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    turn_id = temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                         "VALUES(?,?,?,?)", (cid, 5, "That evening.", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Skip", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=cid, idx=5,
                      player_input="That evening.", created=time.time()),
        cast=[], input="That evening.")
    ctx.director_resolve = {"resolved_event": "Evening.", "dialogue_log": [],
                            "state_diff": diff}
    return ctx


def _scene(**extra):
    scene = {"location": "Tower", "time": "", "time_of_day": PROBE_CLOCK["display"],
             "rooms": {"kitchen": {"name": "Kitchen", "desc": "A kitchen.",
                                   "adjacent": []}},
             "entities": {}, "positions": {"Mara": "kitchen"},
             "attire": {}, "overlays": {}}
    scene.update(extra)
    return scene


#: An ordinary beat's time: its steps and nothing passed over.
STEPS = {"duration_seconds": 44.0}


def _resolved_time(temp_db, monkeypatch, clock, *, skip=True):
    """The probe beat's `state_diff.time` as `director_resolve` writes it --
    the encoder's skip to the evening, then 44 seconds of steps -- on a
    story whose clock stands at `clock`. The commit tests below consume what
    the engine produced, never a block written by hand."""
    ctx = _make_ctx(temp_db, player_input="That evening, I sit at the table.")
    temp_db.wset(ctx.chat["id"], "simulation_clock", dict(clock))
    events = ([_skip("evening")] if skip else []) + [
        _step("Mara climbs to the lamp room.", 36, source="character:1"),
        _step("Eleven years.", 8, source="character:1", speech=True, observable="")]
    out, _ = _stage(temp_db, monkeypatch, ctx, events,
                    "Evening at the tower. Mara climbs to the lamp room.", "resolve")
    return out["state_diff"]["time"], ctx


def _commit(temp_db, diff, *, clock=None, scene=None, conditions=()):
    from persist.commit import (commit_scene, commit_transit_sweep,
                                prepare_scene_commit)
    cid = _chat(temp_db)
    temp_db.wset(cid, "scene", scene or _scene())
    temp_db.wset(cid, "simulation_clock", dict(clock or PROBE_CLOCK))
    for row in conditions:
        temp_db.qi(
            "INSERT INTO world_conditions(condition_id,chat_id,subject_id,kind,"
            "started_at,expires_at,next_tick,payload,active) "
            "VALUES(?,?,?,?,?,?,?,?,?)", (row[0], cid, *row[1:]))
    ctx = _commit_ctx(temp_db, cid, diff)
    prepared = prepare_scene_commit(ctx)
    commit_transit_sweep(ctx, 0, prepared=prepared)
    commit_scene(ctx, 0, prepared=prepared)
    return cid, ctx


@pytest.mark.usefixtures("prose_director")
class TestTheCommit:

    def test_the_clock_lands_in_the_evening(self, temp_db, monkeypatch):
        block, _ = _resolved_time(temp_db, monkeypatch, PROBE_CLOCK)
        cid, ctx = _commit(temp_db, {"time": block})
        clock = temp_db.wget(cid, "simulation_clock", {})
        assert clock["elapsed_seconds"] == 338.0 + ON_THE_CLOCK + 44.0
        assert clock["phase"] == "evening"
        assert temp_db.wget(cid, "scene", {})["time_of_day"] == "evening"
        assert not [w for w in ctx.warnings if "state_diff.time" in w]

    def test_the_weather_drifts_across_the_stretch(self, temp_db, monkeypatch):
        clock = dict(PROBE_CLOCK, elapsed_seconds=3700.0)
        weather = {"sky": "grey", "air": "clear", "cloud": "broken", "wind": "breeze",
                   "precipitation": "none", "precipitation_kind": "none",
                   "intensity": "none", "temperature": "cool", "drift_step": 1}
        quiet, _ = _commit(temp_db, {"time": dict(STEPS)}, clock=clock,
                           scene=_scene(weather=dict(weather)))
        assert temp_db.wget(quiet, "scene", {})["weather"]["drift_step"] == 1
        block, _ = _resolved_time(temp_db, monkeypatch, clock)
        moved, _ = _commit(temp_db, {"time": block}, clock=clock,
                           scene=_scene(weather=dict(weather)))
        assert temp_db.wget(moved, "scene", {})["weather"]["drift_step"] == int(
            (3700.0 + _to_evening(clock) + 44.0) // 3600)

    def test_a_condition_tick_comes_due_inside_the_stretch(self, temp_db, monkeypatch):
        hunger = ("pangs", "Mara", "hunger", 0.0, None, 338.0 + 600.0,
                  json.dumps({"tick_interval_seconds": 3600,
                              "tick": {"percept": "her stomach turns over"}}), 1)
        quiet, _ = _commit(temp_db, {"time": dict(STEPS)}, conditions=[hunger])
        row = temp_db.q("SELECT next_tick FROM world_conditions WHERE chat_id=?",
                        (quiet,), one=True)
        assert row["next_tick"] == 938.0                 # not due in 44 seconds
        block, _ = _resolved_time(temp_db, monkeypatch, PROBE_CLOCK)
        moved, _ = _commit(temp_db, {"time": block}, conditions=[hunger])
        row = temp_db.q("SELECT next_tick FROM world_conditions WHERE chat_id=?",
                        (moved,), one=True)
        end = 338.0 + ON_THE_CLOCK + 44.0
        assert row["next_tick"] > end >= row["next_tick"] - 3600.0

    def test_a_body_is_as_hungry_as_the_stretch_made_it(self, temp_db, monkeypatch):
        block, _ = _resolved_time(temp_db, monkeypatch, PROBE_CLOCK)
        cid, _ = _commit(temp_db, {"time": block},
                         scene=_scene(vitals={"Mara": {"nourishment": 1.0}}))
        hours = (ON_THE_CLOCK + 44.0) / 3600.0
        vitals = temp_db.wget(cid, "scene", {})["vitals"]["Mara"]
        assert vitals["nourishment"] == round(1.0 - 0.02 * hours, 4)

    def test_a_sleeper_recovers_through_the_night_the_beat_passed_over(
            self, temp_db, monkeypatch):
        """Sleep recovery reads the beat's elapsed seconds like hunger does
        (`survival.tick_vitals`, a sleeper from `sleepers_of`)."""
        block, _ = _resolved_time(temp_db, monkeypatch, PROBE_CLOCK)
        asleep = ("cond_aware_mara", "Mara", "awareness", 0.0, None, None,
                  json.dumps({"condition_id": "cond_aware_mara", "subject_id": "Mara",
                              "kind": "awareness",
                              "state": {"level": "asleep", "cause": "the night"}}), 1)
        cid, _ = _commit(temp_db, {"time": block}, conditions=[asleep],
                         scene=_scene(vitals={"Mara": {"stamina": 0.2}}))
        hours = (ON_THE_CLOCK + 44.0) / 3600.0
        stamina = temp_db.wget(cid, "scene", {})["vitals"]["Mara"]["stamina"]
        assert stamina == round(min(1.0, 0.2 + 0.14 * hours), 4)

    def test_the_off_screen_world_runs_it_as_a_skip(self, temp_db, monkeypatch):
        from world.offscreen import _beat_context
        block, _ = _resolved_time(temp_db, monkeypatch, PROBE_CLOCK)
        assert _beat_context({"diff": {"time": block}}) == "time_skip"
        plain, _ = _resolved_time(temp_db, monkeypatch, PROBE_CLOCK, skip=False)
        assert plain == STEPS
        assert _beat_context({"diff": {"time": plain}}) == "beat"

    def test_a_story_with_no_time_of_day_takes_the_part_of_the_day(
            self, temp_db, monkeypatch):
        """No anchor, so nothing could solve "that evening" into a span; the
        beat has said what part of the day it is, and the day takes it. The
        stage says the stretch went uncharged."""
        unanchored = {"elapsed_seconds": 1062.0, "display": "", "time_scale": "scene"}
        block, resolve_ctx = _resolved_time(temp_db, monkeypatch, unanchored)
        assert block == {"until_phase": "evening", "duration_seconds": 44.0}
        assert [w for w in resolve_ctx.warnings if "cannot be measured" in w]
        cid, _ = _commit(temp_db, {"time": block}, clock=unanchored,
                         scene=_scene(time_of_day=""))
        clock = temp_db.wget(cid, "simulation_clock", {})
        assert clock["phase"] == "evening"
        assert temp_db.wget(cid, "scene", {})["time_of_day"] == "evening"
        assert clock["elapsed_seconds"] == 1062.0 + 44.0
