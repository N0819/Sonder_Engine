"""The world over N hours is the same whether the hours passed in one beat or
in many: the sky walks once for every drift window a beat crosses, each step
seeded by its own window, and the ground lies one window at a time under the
sky that stood in it.

Measured (the probe story, 2026-10-21, control chat 2): time skips move the
story clock since 72ba9da3 and 781ea6ea, and the weather did not follow it.

* `advance_weather` took ONE drift per beat: `step = elapsed //
  DRIFT_SECONDS`, and if the stamped window differed, one `_walk` per axis
  seeded by `step`. "Two days later ..." (idx 8), replayed through the commit
  from checkpoint 8 with the beat's time alone, crossed 42 windows (21 -> 63)
  and walked the sky once, where 42 one-hour beats walk it 42 times.
* A declared sky was placed in whatever window FIRST OBSERVED it. "That
  evening" (idx 5) declared a sky in window 3; "The next morning" (idx 6)
  observed it in window 15 and placed it there -- twelve hours, no drift at
  all (checkpoint 7: `drift_step` 15, the sky exactly as declared).
* `_advance_ground` took one `ground_after` step per COMMIT. Three
  conversational beats inside four and a half minutes of story (idx 2-4,
  elapsed 1720 -> 1993 s) took the rock landing from "damp ground" to
  "churned mud" (checkpoints 2-5: levels 2, 4, 7, 10), and the 56-hour beat
  drained it one level (checkpoint 9: 12 -> 11).
"""

from __future__ import annotations

import random
import time

import pytest

from world.weather import (CLOUDS, DECLARED_STEP, DRIFT_SECONDS,
                           DRIFT_STEP_KEY, INTENSITIES, MOONS, WINDS,
                           WIND_FROM_KEY, advance_weather, is_falling,
                           normalize_weather)

HOUR = float(DRIFT_SECONDS)


# ---------------------------------------------------------------------------
# The sky, one beat or many
# ---------------------------------------------------------------------------

#: Sky names: the five this engine mints (which the drift may keep in step
#: with the cloud it walks) and authored ones (which it never rewrites).
_SKY_NAMES = ("clear", "fair", "overcast", "fog", "storm",
              "pewter overcast", "an ash-choked pall", "a sky of two suns")
#: Falls: none, the engine's own words, and authored names with and without
#: a stated kind.
_FALLS = (("none", None), ("rain", None), ("snow", None), ("spray", "liquid"),
          ("ashfall", "particulate"), ("the fall", None))


def _random_sky(rng):
    fall, kind = rng.choice(_FALLS)
    sky = {"sky": rng.choice(_SKY_NAMES), "precipitation": fall,
           "cloud": rng.choice(CLOUDS), "wind": rng.choice(WINDS),
           "intensity": rng.choice(INTENSITIES),
           "temperature": rng.choice(("freezing", "cold", "mild", "hot")),
           "electrical": rng.random() < 0.3,
           "moon": rng.choice(MOONS)}
    if kind:
        sky["precipitation_kind"] = kind
    if rng.random() < 0.5:
        sky[WIND_FROM_KEY] = rng.choice(("n", "sw", "e"))
    return normalize_weather(sky)


def _hour_by_hour(weather, start, end, seed, severity=None):
    """`end - start` beats, each crossing exactly one window and landing
    somewhere inside it, as a story told an hour at a time would."""
    rng = random.Random("%s|%s|%s" % (seed, start, end))
    for window in range(start + 1, end + 1):
        weather = advance_weather(weather, window * HOUR + rng.uniform(0, HOUR - 1),
                                  seed, severity)
    return weather


def test_one_beat_of_n_windows_lands_where_n_beats_of_one_do():
    """The class, as a property: random skies, seeds, severities, starting
    windows and spans. Before the fix the long beat took one walk and the
    hour-by-hour story took N."""
    rng = random.Random(20261021)
    differed = 0
    for _ in range(300):
        sky = _random_sky(rng)
        seed = "chat:%d" % rng.randrange(10 ** 6)
        severity = rng.choice((None, "calm", "seasonal", "harsh"))
        start = rng.randrange(0, 400)
        span = rng.randrange(2, 80)
        placed = dict(sky, **{DRIFT_STEP_KEY: start})
        at_once = advance_weather(placed, (start + span) * HOUR + rng.uniform(0, HOUR - 1),
                                  seed, severity)
        assert at_once == _hour_by_hour(placed, start, start + span, seed, severity), (
            sky, seed, severity, start, span)
        assert at_once[DRIFT_STEP_KEY] == start + span
        differed += at_once != placed
    assert differed > 200          # the sky is alive, not merely consistent


def test_the_opening_sky_stands_at_the_start_of_the_clock():
    """A sky no commit has placed is the opening's, written at the start of
    the story's clock: a first beat two days on walks every window from
    there, exactly as forty-eight hourly beats would."""
    rng = random.Random(7)
    for _ in range(40):
        sky = _random_sky(rng)
        seed = "chat:%d" % rng.randrange(10 ** 6)
        assert DRIFT_STEP_KEY not in sky
        assert advance_weather(sky, 48 * HOUR + 600, seed) == \
            _hour_by_hour(sky, 0, 48, seed)


def test_every_rule_holds_at_every_window():
    """The declared sky, the never-fell sky, the severity cap and the sky's
    name are rules of ONE window's step, and a long beat is those steps."""
    from world.weather import weather_course

    rng = random.Random(11)
    for _ in range(60):
        sky = _random_sky(rng)
        seed = "chat:%d" % rng.randrange(10 ** 6)
        severity = rng.choice((None, "calm"))
        closed, now = weather_course(dict(sky, **{DRIFT_STEP_KEY: 5}),
                                     (5 + 50) * HOUR + 30, seed, severity)
        assert len(closed) == 50
        for window, stood in enumerate(closed[1:] + [now], start=6):
            assert stood[DRIFT_STEP_KEY] == window
            # What falls, and what it is called, are the story's.
            assert stood["precipitation"] == sky["precipitation"]
            assert stood["precipitation_kind"] == sky["precipitation_kind"]
            if sky["precipitation_kind"] == "none":
                assert not is_falling(stood)          # never-fell stays dry
            if severity == "calm":
                assert stood["intensity"] in ("none", "light")
            # Carried, never walked.
            for axis in ("air", "electrical", "temperature", "moon"):
                assert stood[axis] == sky[axis]
            assert stood.get(WIND_FROM_KEY) == sky.get(WIND_FROM_KEY)
            if sky["sky"] not in ("clear", "fair", "overcast", "fog", "storm"):
                assert stood["sky"] == sky["sky"]     # an authored name stands


def test_a_skip_past_the_limit_lands_where_every_window_does():
    """`DRIFT_WINDOW_LIMIT`: a beat crossing more windows than that walks
    only the last of them. The walk is monotone on every ladder, so once a
    copy started on the lowest rungs and one started on the highest have
    met, every start has met them -- the windows before the limit change
    nothing. Measured on the exact pair chain: P(not met after 168 windows)
    < 1e-14."""
    from world.weather import DRIFT_WINDOW_LIMIT

    rng = random.Random(3)
    span = 2 * DRIFT_WINDOW_LIMIT + 7
    for _ in range(12):
        sky = dict(_random_sky(rng), **{DRIFT_STEP_KEY: 40})
        seed = "chat:%d" % rng.randrange(10 ** 6)
        assert advance_weather(sky, (40 + span) * HOUR, seed) == \
            _hour_by_hour(sky, 40, 40 + span, seed)


# ---------------------------------------------------------------------------
# Through the commit: the probe story's own beats
# ---------------------------------------------------------------------------

#: The probe story's clock before idx 8 (checkpoint 8 of control.db chat 2).
PROBE_CLOCK = {"elapsed_seconds": 78466.0, "display": "afternoon",
               "anchor_hour": 15.75, "day_length_hours": 24.0,
               "hour_of_day": 13.55, "phase": "afternoon"}

#: Its sky, stamped in window 21 by idx 7's drift.
PROBE_SKY = {"sky": "pewter overcast", "air": "clear", "cloud": "covered",
             "electrical": False, "precipitation": "spray",
             "precipitation_kind": "liquid", "intensity": "heavy",
             "wind": "gale", "temperature": "cold", "moon": "none",
             "wind_from": "w", DRIFT_STEP_KEY: 21}

#: Its ground: the landing and the steps churned to mud by idx 1-7.
PROBE_GROUND = {"rock_landing": {"kind": "wet", "level": 12, "state": "churned mud"},
                "the_stair": {"kind": "wet", "level": 12, "state": "churned mud"}}


def _scene(weather=None, ground=None):
    scene = {"location": "The Tower", "time": "", "time_of_day": "afternoon",
             "rooms": {
                 "rock_landing": {"name": "The Landing", "exposure": "open",
                                  "desc": "An iron landing on the rock.",
                                  "adjacent": [{"to": "the_stair", "barrier": "open"}]},
                 "the_stair": {"name": "The Steps", "exposure": "open",
                               "desc": "Steps cut up the rock.",
                               "adjacent": [{"to": "rock_landing", "barrier": "open"},
                                            {"to": "kitchen", "barrier": "door"}]},
                 "kitchen": {"name": "The Kitchen", "exposure": "enclosed",
                             "desc": "A stove and a table.",
                             "adjacent": [{"to": "the_stair", "barrier": "door"}]}},
             "entities": {}, "positions": {"Rhona": "kitchen"},
             "attire": {}, "overlays": {}}
    if weather is not None:
        scene["weather"] = dict(weather)
    if ground is not None:
        scene["ground"] = {k: dict(v) for k, v in ground.items()}
    return scene


def _chat(temp_db, scene, clock, cid=None):
    """A chat holding `scene` on `clock` -- or `cid` put back to them, so a
    story told two ways is told under one seed (the drift's is the chat's)."""
    if cid is None:
        cid = temp_db.qi("INSERT INTO chats(name,persona_id,scenario,created) "
                         "VALUES(?,?,?,?)", ("Lamp Room", None, "", time.time()))
    temp_db.wset(cid, "scene", scene)
    temp_db.wset(cid, "simulation_clock", dict(clock))
    return cid


def _beat(temp_db, cid, diff):
    """One resolved beat committed through the real scene commit."""
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    from persist.commit import (commit_scene, commit_transit_sweep,
                                prepare_scene_commit)
    idx = int(temp_db.q("SELECT COALESCE(MAX(idx), 0) + 1 AS n FROM turns "
                        "WHERE chat_id=?", (cid,), one=True)["n"])
    turn_id = temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                         "VALUES(?,?,?,?)", (cid, idx, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Lamp Room", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=cid, idx=idx, player_input="",
                      created=time.time()),
        cast=[], input="")
    ctx.director_resolve = {"resolved_event": "The weather on the rock.",
                            "dialogue_log": [], "state_diff": diff}
    prepared = prepare_scene_commit(ctx)
    commit_transit_sweep(ctx, 0, prepared=prepared)
    commit_scene(ctx, 0, prepared=prepared)
    scene = temp_db.wget(cid, "scene", {})
    return scene.get("weather"), scene.get("ground") or {}


def _lasting(seconds):
    return {"time": {"duration_seconds": float(seconds)}}


def test_a_conversational_beat_moves_neither_the_sky_nor_the_ground(temp_db):
    """Idx 2-4 of the probe, in the commit: a downpour standing over an open
    landing, and a beat of talk inside one window. Before the fix every
    such beat laid another one to three levels of mud."""
    cid = _chat(temp_db, _scene(PROBE_SKY, {"rock_landing": {
        "kind": "wet", "level": 4, "state": "wet ground"}}),
        dict(PROBE_CLOCK, elapsed_seconds=21 * HOUR + 100.0))
    for _ in range(3):
        weather, ground = _beat(temp_db, cid, _lasting(70))
        assert weather == PROBE_SKY
        assert ground == {"rock_landing": {"kind": "wet", "level": 4,
                                           "state": "wet ground"}}


def test_the_ground_over_hours_is_the_same_in_one_beat_or_many(temp_db):
    """Six one-hour beats and one six-hour beat leave the same sky AND the
    same floor. Before the fix the six-hour beat took one ground step and
    one drift, the hourly story six of each."""
    start = dict(PROBE_CLOCK, elapsed_seconds=21 * HOUR + 100.0)
    for seed_room in ({}, PROBE_GROUND):
        cid = _chat(temp_db, _scene(PROBE_SKY, seed_room), start)
        weather_once, ground_once = _beat(temp_db, cid, _lasting(6 * HOUR))
        _chat(temp_db, _scene(PROBE_SKY, seed_room), start, cid=cid)
        for _ in range(6):
            weather_hourly, ground_hourly = _beat(temp_db, cid, _lasting(HOUR))
        assert weather_once == weather_hourly
        assert ground_once == ground_hourly
        assert weather_once[DRIFT_STEP_KEY] == 27


def test_a_declared_sky_walks_from_the_window_it_was_declared_in(temp_db):
    """Idx 5-6 of the probe: "That evening" declared a sky in window 3 and
    "The next morning" observed it in window 15. The twelve hours between
    are the sky's, as they would be told an hour at a time."""
    evening = dict(PROBE_CLOCK, elapsed_seconds=13581.0)        # window 3
    declared_sky = normalize_weather(
        {"sky": "pewter overcast", "precipitation": "spray",
         "precipitation_kind": "liquid", "intensity": "moderate",
         "wind": "gale", "temperature": "cold"}, dict(PROBE_SKY))
    assert declared_sky[DRIFT_STEP_KEY] == DECLARED_STEP
    cid = _chat(temp_db, _scene(declared_sky), evening)
    weather, _ = _beat(temp_db, cid, _lasting(54960.0 - 13581.0))  # window 15
    assert weather[DRIFT_STEP_KEY] == 15
    assert weather == _hour_by_hour(dict(declared_sky, **{DRIFT_STEP_KEY: 3}),
                                    3, 15, "chat:%s" % cid)


def test_the_probe_skip_moves_the_sky_and_the_ground_by_its_hours(temp_db):
    """Idx 8 of the probe: "Two days later ..." from the afternoon of window
    21 to the second morning on (+41.5 hours, window 63, the landing
    781ea6ea gives it), committed through the real commit, against the same
    hours told an hour at a time."""
    to_morning = (48.0 + 7.0 - ((15.75 + 78466.0 / 3600.0) % 24.0)) * HOUR
    skip = dict(_lasting(to_morning + 120.0)["time"],
                skipped_seconds=to_morning, mode="time_skip")
    cid = _chat(temp_db, _scene(PROBE_SKY, PROBE_GROUND), PROBE_CLOCK)
    weather_once, ground_once = _beat(temp_db, cid, {"time": skip})
    end = PROBE_CLOCK["elapsed_seconds"] + to_morning + 120.0
    assert weather_once[DRIFT_STEP_KEY] == int(end // HOUR) == 63

    _chat(temp_db, _scene(PROBE_SKY, PROBE_GROUND), PROBE_CLOCK, cid=cid)
    clock = PROBE_CLOCK["elapsed_seconds"]
    while clock < end:
        step = min(HOUR, end - clock)
        weather_hourly, ground_hourly = _beat(temp_db, cid, _lasting(step))
        clock += step
    assert weather_once == weather_hourly
    assert ground_once == ground_hourly


def _open(temp_db, cid, establish):
    """The opening beat, committed through the real scene commit."""
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    from persist.commit import (commit_scene, commit_transit_sweep,
                                prepare_scene_commit)
    turn_id = temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                         "VALUES(?,?,?,?)", (cid, 0, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Lamp Room", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=cid, idx=0, player_input="",
                      created=time.time()),
        cast=[], input="")
    ctx.director_establish = dict({"resolved_event": "The story opens.",
                                   "dialogue_log": [], "state_diff": {}},
                                  **establish)
    prepared = prepare_scene_commit(ctx)
    commit_transit_sweep(ctx, 0, prepared=prepared)
    commit_scene(ctx, 0, prepared=prepared)
    scene = temp_db.wget(cid, "scene", {})
    return scene.get("weather"), scene.get("ground") or {}


def test_the_opening_lays_the_floor_its_sky_implies(temp_db):
    """The opening passes no time, so no window closes in it -- and a story
    that opens in a blizzard must not open on bare ground. Every opening laid
    one step of its sky while the floor stepped per commit (the owner's chat
    46 opened its snowy clearing on "a dusting of snow", level 3); that is
    kept, as `OPENING_GROUND_WINDOWS`, and the beat of talk after it, inside
    the same window, leaves it there."""
    from world.weather import OPENING_GROUND_WINDOWS

    assert OPENING_GROUND_WINDOWS == 1
    cid = _chat(temp_db, _scene(), {"elapsed_seconds": 0.0})
    weather, ground = _open(temp_db, cid, {"weather": {
        "sky": "blizzard", "precipitation": "snow", "intensity": "heavy",
        "wind": "gale", "temperature": "freezing"}})
    assert weather["sky"] == "blizzard"
    dusting = {"kind": "piled", "level": 3, "state": "a dusting of snow",
               "name": "snow"}
    assert ground == {"rock_landing": dusting, "the_stair": dusting}
    assert _beat(temp_db, cid, _lasting(90))[1] == ground
