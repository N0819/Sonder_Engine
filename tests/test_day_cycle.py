"""The day moves with the clock: hour, phase, label, light, and the town.

THE DEFECT THIS PINS. The Harrowmere playtest (2026-09-02, forty beats,
64.9 story hours) read "mid-morning" on every beat, because the standing
time-of-day label was free text the Director declared once and nothing
derived a later hour from the exact clock beside it. Every reader -- the
Director's payload, a background voice's block, the ambience bucket, the
clock's display, the outdoor light, the charter's errands -- read the word,
and the word never moved.

`world/day_cycle.py` is the arithmetic; `persist/commit_scene_state.
_advance_day_cycle` is the one writer; `world/spatial_light.room_light`
and `world/charter_move.errands` are the two readers that change behaviour
on it. Everything here fails open: a story that never named a readable time
gets no anchor, no phase, and every reader's old behaviour byte for byte.
"""

from __future__ import annotations

import copy
import json
import time

import pytest

from core.pipeline_context import ChatData, PipelineContext, TurnData
from world.day_cycle import (
    DAY_LENGTH_HOURS_DEFAULT, PHASE_NAMES, RESTING_PHASES, SOCIAL_PHASES,
    charter_phase, clock_anchor, day_length_hours, hour_of_day, label_hour,
    label_phase, phase_of_hour, sun_light)


# --- arithmetic --------------------------------------------------------------


def test_the_hour_is_the_anchor_plus_the_clock_and_wraps():
    assert hour_of_day(0.0, 9.5) == 9.5
    assert hour_of_day(3600.0 * 30, 20.0) == pytest.approx(2.0)
    assert hour_of_day(3600.0 * 5, 28.0, 30.0) == pytest.approx(3.0)


def test_the_phase_table_is_closed_total_and_lands_on_its_boundaries():
    assert set(PHASE_NAMES) == {"night", "pre-dawn", "dawn", "morning",
                                "midday", "afternoon", "dusk", "evening"}
    expected = [(0.0, "night"), (4.49, "night"), (4.5, "pre-dawn"),
                (6.0, "dawn"), (7.0, "morning"), (11.0, "midday"),
                (13.5, "afternoon"), (18.0, "dusk"), (19.5, "evening"),
                (22.0, "night"), (23.99, "night")]
    for hour, phase in expected:
        assert phase_of_hour(hour) == phase, hour
    # Total: every hour of the day is in exactly one phase.
    for tenth in range(0, 240):
        assert phase_of_hour(tenth / 10.0) in PHASE_NAMES


def test_a_thirty_hour_day_scales_every_phase_with_it():
    # Dawn is a quarter of the way through the day, whatever the day is.
    assert phase_of_hour(6.0, 24.0) == "dawn"
    assert phase_of_hour(7.5, 30.0) == "dawn"
    assert phase_of_hour(7.5, 24.0) == "morning"
    assert phase_of_hour(15.0, 30.0) == "midday"
    assert phase_of_hour(27.5, 30.0) == "night"


def test_a_label_names_a_phase_or_it_does_not():
    assert label_phase("before dawn") == "pre-dawn"
    assert label_phase("Dusk") == "dusk"
    assert label_phase("nightfall") == "evening"
    assert label_phase("Late autumn afternoon") == "afternoon"
    assert label_phase("high noon") == "midday"
    assert label_phase("08:42:15 AM") == "morning"
    assert label_phase("Stardate 46357.4, 14:32 hours") == "afternoon"
    assert label_phase("0830") == "morning"
    # The guards the corpus earned: a countdown and a year are not times.
    assert label_phase("Cycle-End -01:45:00") is None
    assert label_phase("Spring 1893") is None
    assert label_phase("now") is None
    assert label_phase("") is None
    # A reading past the end of a short day cannot be a time on that clock.
    assert label_phase("22:00", 20.0) is None


def test_a_label_anchors_on_its_reading_or_its_phases_middle():
    assert label_hour("08:42") == pytest.approx(8.7)
    assert label_hour("dusk") == pytest.approx(18.75)
    assert label_hour("dawn", 30.0) == pytest.approx(8.125)
    assert label_hour("Immediate aftermath of a containment breach") is None


def test_the_day_length_is_the_authors_dial_with_a_terran_default():
    assert day_length_hours(None) == DAY_LENGTH_HOURS_DEFAULT
    assert day_length_hours({"day_length_hours": 30}) == 30.0
    assert day_length_hours({"day_length_hours": "x"}) == DAY_LENGTH_HOURS_DEFAULT
    assert day_length_hours({"day_length_hours": -3}) == DAY_LENGTH_HOURS_DEFAULT


def test_a_clock_anchors_on_its_stored_anchor_then_its_label_then_the_dial():
    assert clock_anchor({"anchor_hour": 5.0, "elapsed_seconds": 99999.0}) == (5.0, 24.0)
    anchor, length = clock_anchor({"elapsed_seconds": 3600.0, "display": "dusk"})
    assert (anchor, length) == (pytest.approx(17.75), 24.0)
    assert clock_anchor({"elapsed_seconds": 0.0, "display": "now"},
                        {"opening_hour": 9.0}) == (9.0, 24.0)
    assert clock_anchor({"elapsed_seconds": 0.0, "display": "now"}) == (None, 24.0)
    assert clock_anchor({}) == (None, 24.0)


def test_the_style_guide_validates_the_two_numbers_rather_than_trimming_them():
    from story.scene import normalize_style_guide
    assert normalize_style_guide({"day_length_hours": "30"})["day_length_hours"] == 30.0
    assert "day_length_hours" not in normalize_style_guide({"day_length_hours": "24"})
    assert "day_length_hours" not in normalize_style_guide({"day_length_hours": "0"})
    assert "day_length_hours" not in normalize_style_guide({"day_length_hours": "soon"})
    assert normalize_style_guide({"opening_hour": "9.5"})["opening_hour"] == 9.5
    assert "opening_hour" not in normalize_style_guide({"opening_hour": "25"})
    assert normalize_style_guide(
        {"day_length_hours": 30, "opening_hour": 25})["opening_hour"] == 25.0
    assert "opening_hour" not in normalize_style_guide({"opening_hour": True})


# --- the commit is the one writer --------------------------------------------


def _make_chat(temp_db):
    return temp_db.qi(
        "INSERT INTO chats(name,persona_id,scenario,created) VALUES(?,?,?,?)",
        ("Day", None, "", time.time()))


def _scene(time_of_day="dusk"):
    return {
        "location": "Harrowmere", "time_of_day": time_of_day,
        "rooms": {"square": {"name": "Market Square", "desc": "A cobbled square.",
                             "exposure": "open", "adjacent": []}},
        "entities": {}, "positions": {"Wren": "square"},
        "attire": {}, "overlays": {},
    }


def _ctx(temp_db, chat_id, *, turn_idx, resolve=None, establish=None):
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, turn_idx, "wait", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Day", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=turn_idx,
                      player_input="wait", created=time.time()),
        cast=[], input="wait",
    )
    if establish is not None:
        ctx.director_establish = establish
    if resolve is not None:
        ctx.director_resolve = {"resolved_event": "Time passes.",
                                "dialogue_log": [], "state_diff": resolve}
    return ctx


def _commit(temp_db, chat_id, ctx):
    from persist.commit import commit_scene, prepare_scene_commit
    commit_scene(ctx, 0, prepared=prepare_scene_commit(ctx))
    return (temp_db.wget(chat_id, "scene", {}),
            temp_db.wget(chat_id, "simulation_clock", {}), ctx.warnings)


def _open(temp_db, chat_id, label, *, style=None):
    if style is not None:
        temp_db.wset(chat_id, "style_guide", style)
    est = {"location": "Harrowmere", "time": label,
           "scene_description": "A town.", "rooms": _scene()["rooms"],
           "entities": {}, "positions": {"Wren": "square"},
           "simulation_clock": {"elapsed_seconds": 0.0, "display": label,
                                "time_scale": "scene"}}
    return _commit(temp_db, chat_id, _ctx(temp_db, chat_id, turn_idx=0,
                                          establish=est))


def _beat(temp_db, chat_id, diff, *, turn_idx=1):
    return _commit(temp_db, chat_id,
                   _ctx(temp_db, chat_id, turn_idx=turn_idx, resolve=diff))


def test_the_opening_anchors_the_day_and_keeps_its_own_words(temp_db):
    cid = _make_chat(temp_db)
    scene, clock, _ = _open(temp_db, cid, "before dawn")
    assert scene["time_of_day"] == "before dawn"
    assert scene["day_phase"] == "pre-dawn"
    assert clock["display"] == "before dawn"
    assert clock["phase"] == "pre-dawn"
    assert clock["day_length_hours"] == 24.0
    assert clock["anchor_hour"] == pytest.approx(5.25, abs=0.01)
    assert clock["hour_of_day"] == pytest.approx(5.25, abs=0.01)


def test_the_label_follows_the_clock_once_the_clock_leaves_its_phase(temp_db):
    cid = _make_chat(temp_db)
    _open(temp_db, cid, "08:42")
    scene, clock, _ = _beat(temp_db, cid, {"time": {"duration_seconds": 3600}})
    assert scene["time_of_day"] == "08:42"          # still morning
    assert clock["hour_of_day"] == pytest.approx(9.7, abs=0.01)
    scene, clock, _ = _beat(temp_db, cid, {"time": {"duration_seconds": 3 * 3600}},
                            turn_idx=2)
    assert scene["time_of_day"] == "midday"
    assert scene["day_phase"] == "midday"
    assert clock["display"] == "midday"
    assert clock["hour_of_day"] == pytest.approx(12.7, abs=0.01)


def test_the_display_moves_across_sixty_five_story_hours(temp_db):
    """The Harrowmere case, in its own shape: 40 beats, hours passing,
    the display must not read one word throughout."""
    cid = _make_chat(temp_db)
    _open(temp_db, cid, "mid-morning")
    seen = set()
    for idx in range(1, 41):
        scene, clock, _ = _beat(
            temp_db, cid, {"time": {"duration_seconds": 65 * 3600 / 40}},
            turn_idx=idx)
        seen.add(clock["display"])
    assert len(seen) >= 6, seen
    assert clock["hour_of_day"] == pytest.approx((9.0 + 65.0) % 24.0, abs=0.05)


def test_a_declared_time_the_clock_is_not_in_re_anchors_and_says_so(temp_db):
    cid = _make_chat(temp_db)
    _open(temp_db, cid, "dusk")
    scene, clock, warnings = _beat(temp_db, cid, {"time": "the next morning"})
    assert scene["time_of_day"] == "the next morning"      # the Director's words
    assert scene["day_phase"] == "morning"
    assert clock["phase"] == "morning"
    assert clock["hour_of_day"] == pytest.approx(9.0, abs=0.05)
    assert any("re-anchored" in w for w in warnings), warnings


def test_a_declared_time_the_clock_is_already_in_changes_nothing(temp_db):
    cid = _make_chat(temp_db)
    _, opened, _ = _open(temp_db, cid, "dusk")
    scene, clock, warnings = _beat(temp_db, cid, {"time": "dusk deepens"})
    assert scene["time_of_day"] == "dusk deepens"
    assert clock["anchor_hour"] == pytest.approx(opened["anchor_hour"])
    assert not any("re-anchored" in w for w in warnings)


def test_a_skip_that_names_where_it_lands_lands_there(temp_db):
    """Harrowmere replay (2026-09-03, t19): "by dusk" with an eleven-hour
    duration from 06:19 landed at 17:19, in the afternoon, and the phase
    the Director named was silently wrong. The phrase is the intent and the
    duration the estimate: the clock lands at the START of the named phase
    and says which hour the duration had reached."""
    cid = _make_chat(temp_db)
    _open(temp_db, cid, "dawn")                              # 06:30
    scene, clock, warnings = _beat(temp_db, cid, {"time": {
        "duration_seconds": 11 * 3600, "mode": "time_skip",
        "display_advance": "by dusk"}})
    assert clock["phase"] == "dusk"
    assert clock["hour_of_day"] == pytest.approx(18.0, abs=0.05)
    assert scene["time_of_day"] == "dusk"
    assert any("landed" in w and "afternoon" in w for w in warnings), warnings


def test_a_skip_whose_duration_agrees_with_its_phrase_keeps_its_hour(temp_db):
    cid = _make_chat(temp_db)
    _, opened, _ = _open(temp_db, cid, "midday")             # 12:15
    scene, clock, warnings = _beat(temp_db, cid, {"time": {
        "duration_seconds": 6 * 3600, "mode": "time_skip",
        "display_advance": "by dusk"}})
    assert clock["phase"] == "dusk"
    assert clock["hour_of_day"] == pytest.approx(18.25, abs=0.05)
    assert clock["anchor_hour"] == pytest.approx(opened["anchor_hour"])
    assert not any("landed" in w for w in warnings)


def test_a_skip_phrase_carrying_a_reading_lands_on_the_reading(temp_db):
    cid = _make_chat(temp_db)
    _open(temp_db, cid, "dawn")
    scene, clock, warnings = _beat(temp_db, cid, {"time": {
        "duration_seconds": 3 * 3600, "mode": "time_skip",
        "display_advance": "by 20:00"}})
    assert clock["hour_of_day"] == pytest.approx(20.0, abs=0.05)
    assert clock["phase"] == "evening"
    assert any("landed" in w for w in warnings)
    # The passage phrase is still written nowhere: the label is the phase.
    assert scene["time_of_day"] == "evening"


def test_a_skip_phrase_the_cycle_cannot_read_changes_nothing(temp_db):
    cid = _make_chat(temp_db)
    _open(temp_db, cid, "dawn")
    scene, clock, warnings = _beat(temp_db, cid, {"time": {
        "duration_seconds": 5 * 3600, "mode": "time_skip",
        "display_advance": "some hours later"}})
    assert clock["hour_of_day"] == pytest.approx(11.5, abs=0.05)
    assert not any("landed" in w for w in warnings)


def test_a_label_the_cycle_cannot_read_stands_untouched(temp_db):
    cid = _make_chat(temp_db)
    _open(temp_db, cid, "08:42")
    scene, clock, warnings = _beat(
        temp_db, cid, {"time": {"duration_seconds": 5 * 3600}})
    assert scene["time_of_day"] == "afternoon"
    scene, clock, warnings = _beat(temp_db, cid, {"time": "Stardate 46357.4"},
                                   turn_idx=2)
    assert scene["time_of_day"] == "Stardate 46357.4"
    assert clock["phase"] == "afternoon"                   # still derived
    assert not any("re-anchored" in w for w in warnings)
    scene, clock, _ = _beat(temp_db, cid, {"time": {"duration_seconds": 6 * 3600}},
                            turn_idx=3)
    assert scene["time_of_day"] == "Stardate 46357.4"      # never overwritten
    assert clock["phase"] == "evening"


def test_a_story_that_never_named_a_readable_time_gets_no_cycle(temp_db):
    cid = _make_chat(temp_db)
    scene, clock, _ = _open(temp_db, cid, "Immediate aftermath of a breach")
    assert "day_phase" not in scene
    assert "anchor_hour" not in clock
    scene, clock, _ = _beat(temp_db, cid, {"time": {"duration_seconds": 3600}})
    assert "day_phase" not in scene
    assert "anchor_hour" not in clock
    assert scene["time_of_day"] == "Immediate aftermath of a breach"
    assert clock["display"] == "Immediate aftermath of a breach"


def test_the_authors_opening_hour_stands_in_when_the_opening_names_none(temp_db):
    cid = _make_chat(temp_db)
    scene, clock, _ = _open(temp_db, cid, "Immediate aftermath of a breach",
                            style={"opening_hour": 21.0})
    assert scene["day_phase"] == "evening"
    assert clock["anchor_hour"] == pytest.approx(21.0)
    assert scene["time_of_day"] == "Immediate aftermath of a breach"


def test_a_story_that_predates_the_cycle_anchors_on_its_standing_label(temp_db):
    cid = _make_chat(temp_db)
    temp_db.wset(cid, "scene", _scene("dusk"))
    temp_db.wset(cid, "simulation_clock", {"elapsed_seconds": 7200.0,
                                           "display": "dusk"})
    scene, clock, _ = _beat(temp_db, cid, {"time": {"duration_seconds": 60}})
    assert clock["phase"] == "dusk"
    assert clock["anchor_hour"] == pytest.approx(18.75 - 7200.0 / 3600.0 - 1 / 60,
                                                  abs=0.02)
    assert scene["time_of_day"] == "dusk"


def test_a_thirty_hour_world_runs_its_own_day(temp_db):
    cid = _make_chat(temp_db)
    scene, clock, _ = _open(temp_db, cid, "dawn", style={"day_length_hours": 30})
    assert clock["day_length_hours"] == 30.0
    assert clock["hour_of_day"] == pytest.approx(8.125, abs=0.01)
    scene, clock, _ = _beat(temp_db, cid, {"time": {"duration_seconds": 15 * 3600}})
    assert clock["hour_of_day"] == pytest.approx(23.125, abs=0.01)
    assert scene["day_phase"] == "dusk"
    assert scene["time_of_day"] == "dusk"


def test_every_reader_sees_the_derived_label(temp_db):
    """The Director payload, a background presence and the ambience bucket
    all read `scene.time_of_day` and `simulation_clock`; after the clock has
    moved, what they read has moved."""
    from dressing.backdrops import time_bucket
    from story.scene import simulation_clock
    cid = _make_chat(temp_db)
    _open(temp_db, cid, "08:42")
    scene, clock, _ = _beat(temp_db, cid, {"time": {"duration_seconds": 12 * 3600}})
    assert scene["time_of_day"] == "evening"
    assert time_bucket(scene["time_of_day"]) == "evening"
    live = simulation_clock(cid)
    assert live["phase"] == "evening"
    assert live["display"] == "evening"
    assert live["hour_of_day"] == pytest.approx(20.7, abs=0.01)
    # Every phase name the table can write is a label the scenery bucket reads.
    for phase in PHASE_NAMES:
        assert time_bucket(phase), phase


def test_the_clock_fields_survive_archive_and_checkpoint(temp_db):
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint
    from web import app
    cid = _make_chat(temp_db)
    _open(temp_db, cid, "dusk")
    ensure_checkpoint(cid, 1)
    _beat(temp_db, cid, {"time": "the next morning"})
    exported = app.chat_export(cid)
    imported = app.chat_import({"data": exported})
    clock = temp_db.wget(imported["id"], "simulation_clock", {})
    assert clock["phase"] == "morning"
    assert clock["anchor_hour"] is not None
    assert clock["day_length_hours"] == 24.0
    restore_checkpoint(cid, 1)
    restored = temp_db.wget(cid, "simulation_clock", {})
    assert restored["phase"] == "dusk"
    assert restored["display"] == "dusk"


# --- outdoors, the sky is the ceiling ----------------------------------------


def _lit_scene(phase=None, **room):
    scene = {
        "rooms": {
            "square": {"name": "Square", "desc": "An open square.",
                       "exposure": "open", "adjacent": [], **room},
            "porch": {"name": "Porch", "desc": "A covered porch.",
                      "exposure": "sheltered", "adjacent": []},
            "cellar": {"name": "Cellar", "desc": "A stone cellar.",
                       "exposure": "enclosed", "light": "dark", "adjacent": []},
        },
        "entities": {}, "positions": {},
    }
    if phase:
        scene["day_phase"] = phase
    return scene


def test_the_sun_lights_an_outdoor_room_by_phase():
    from world.spatial import room_light
    table = {"night": "dark", "pre-dawn": "dark", "dawn": "dim", "morning": "lit",
             "midday": "lit", "afternoon": "lit", "dusk": "dim", "evening": "dark"}
    for phase, level in table.items():
        assert sun_light(phase) == level
        assert room_light(_lit_scene(phase), "square") == level, phase
        assert room_light(_lit_scene(phase), "porch") == level, phase
        assert room_light(_lit_scene(phase), "cellar") == "dark", phase


def test_a_room_with_no_phase_composes_exactly_as_before():
    from world.spatial import effective_light, light_at, room_light
    for light in ("dark", "dim", "lit", "bright", None):
        with_phase = _lit_scene(None, **({"light": light} if light else {}))
        assert room_light(with_phase, "square") == (light or "lit")
        assert effective_light(with_phase, "square") == (light or "lit")
    scene = _lit_scene(None)
    scene["positions"]["Wren"] = "square"
    assert light_at(scene, "Wren") == "lit"


def test_a_declared_light_may_darken_the_sun_and_never_brighten_it():
    from world.spatial import room_light
    assert room_light(_lit_scene("midday", light="dim"), "square") == "dim"
    assert room_light(_lit_scene("night", light="lit"), "square") == "dark"
    assert room_light(_lit_scene("night", light="bright"), "square") == "dark"


def test_a_lamp_in_the_square_lights_it_again():
    from world.spatial import effective_light, light_blocks_sight
    scene = _lit_scene("night")
    assert light_blocks_sight(effective_light(scene, "square"))
    scene["entities"]["lamp"] = {"name": "brazier", "light_source": "lit",
                                 "light_radius": "room"}
    scene["positions"]["lamp"] = "square"
    assert effective_light(scene, "square") == "lit"


def test_fog_takes_one_step_off_the_daylight_and_no_more():
    from world.spatial import room_light
    scene = _lit_scene("midday")
    scene["weather"] = {"sky": "fog"}
    assert room_light(scene, "square") == "dim"
    scene = _lit_scene("dusk")
    scene["weather"] = {"sky": "overcast"}
    assert room_light(scene, "square") == "dim"
    assert sun_light("night", "storm") == "dark"


# --- the town responds to the day --------------------------------------------


def _town():
    import sys
    sys.path.insert(0, "tests")
    from charter_worlds import small_town
    from world.charter import normalize_charter, seed_needs, seed_roster
    charter = normalize_charter(copy.deepcopy(small_town()))
    charter["roster"] = seed_roster(charter["bodies"])
    charter["needs"] = seed_needs(charter["bodies"])
    return charter


def test_a_charter_reads_its_phase_from_the_story_or_has_none():
    charter = {"day_anchor_hours": 20.0, "day_length_hours": 24.0}
    assert charter_phase(charter, 0.0) == "evening"
    assert charter_phase(charter, 7.0) == "night"
    assert charter_phase(charter, 10.0) == "dawn"
    assert charter_phase({"day_anchor_hours": None}, 10.0) is None
    assert charter_phase({}, 10.0) is None
    assert charter_phase({"day_anchor_hours": 0.0, "day_length_hours": 30.0},
                         15.0) == "midday"


def test_nobody_runs_an_errand_in_the_night_and_evenings_are_for_the_commons():
    from world.charter_move import errands
    charter = _town()
    from world.charter_space import reach_map, frequented_places
    reach = reach_map(charter["scene"], frequented_places(charter),
                      charter["bodies"])
    args = (charter["bodies"], charter["needs"], charter["upkeeps"], {},
            frequented_places(charter), reach)
    daytime = errands(*args, seed=3, rate=1.0, hours=4.0,
                      commons=charter["commons"], phase="morning")
    assert daytime
    assert errands(*args, seed=3, rate=1.0, hours=4.0,
                   commons=charter["commons"], phase="night") == {}
    assert errands(*args, seed=3, rate=1.0, hours=4.0,
                   commons=charter["commons"], phase="pre-dawn") == {}
    evening = errands(*args, seed=3, rate=1.0, hours=4.0,
                      commons=charter["commons"], phase="evening")
    assert evening and set(evening.values()) <= set(charter["commons"])
    assert errands(*args, seed=3, rate=1.0, hours=4.0, commons=(),
                   phase="evening") == {}
    # No phase is the day as it was: errands at any hour.
    assert errands(*args, seed=3, rate=1.0, hours=4.0,
                   commons=charter["commons"], phase=None) == daytime
    assert RESTING_PHASES == {"night", "pre-dawn"}
    assert SOCIAL_PHASES == {"dusk", "evening"}


def test_the_town_is_home_in_its_berths_at_night_and_out_by_day():
    from world.charter import step
    charter = _town()
    charter["errand_rate"] = 1.0
    charter["day_anchor_hours"] = 0.0      # charter hour 0 is midnight
    charter["day_length_hours"] = 24.0
    posts = {p["place"] for p in charter["posts"].values()}

    def away_from_home():
        return {key for key, body in charter["bodies"].items()
                if body["place"] != body["berth"]
                and key not in set(charter["watch"].values())}

    # Step to the middle of the afternoon: unposted bodies are out.
    for _ in range(14):
        charter, _events = step(charter, hours=1.0, seed=3)
    assert away_from_home(), "nobody left home by afternoon"
    # Step through the night: every unposted body is in its berth.
    for _ in range(13):
        charter, _events = step(charter, hours=1.0, seed=3)
    assert charter_phase(charter, charter["clock_hours"]) == "night"
    assert away_from_home() == set()
    for key, body in charter["bodies"].items():
        if key in set(charter["watch"].values()):
            assert body["place"] in posts


def test_the_catch_up_tells_the_town_when_it_is(temp_db, monkeypatch):
    """`advance_snapshot` re-derives each charter's anchor from the story
    clock every window, so the town's night is the story's night."""
    from world import charter_runtime
    cid = _make_chat(temp_db)
    _open(temp_db, cid, "dusk")                       # anchor 18.75 at elapsed 0
    charter = _town()
    charter["clock_hours"] = 100.0
    registry = {"items": {"town": {"state": charter, "window_hours": 4.0,
                                   "last_elapsed_seconds": 0.0,
                                   "last_epoch_id": "old"}}}
    advanced, _rows, _produced = charter_runtime.advance_snapshot(
        registry, elapsed_seconds=4 * 3600.0, epoch_id="e1", base_turn=1,
        cid=cid, frame_id=None, scene=None)
    state = advanced["items"]["town"]["state"]
    assert state["day_length_hours"] == 24.0
    # Story hour at elapsed 0 was 18.75, charter hour then was 100.0.
    assert state["day_anchor_hours"] == pytest.approx((18.75 - 100.0) % 24.0, abs=0.01)
    assert charter_phase(state, 100.0) == "dusk"
    assert charter_phase(state, 104.0) == "night"


def test_a_story_with_no_anchor_leaves_the_town_unanchored(temp_db):
    from world import charter_runtime
    cid = _make_chat(temp_db)
    charter = _town()
    registry = {"items": {"town": {"state": charter, "window_hours": 4.0,
                                   "last_elapsed_seconds": 0.0,
                                   "last_epoch_id": "old"}}}
    advanced, _rows, _produced = charter_runtime.advance_snapshot(
        registry, elapsed_seconds=4 * 3600.0, epoch_id="e1", base_turn=1,
        cid=cid, frame_id=None, scene=None)
    state = advanced["items"]["town"]["state"]
    assert state["day_anchor_hours"] is None
    assert charter_phase(state, 4.0) is None


def test_the_prehistory_ends_on_the_storys_hour():
    from world.charter_runtime import presim_registry
    charter = _town()
    registry = {"items": {"town": {"state": charter, "window_hours": 4.0}}}
    presimmed, _events = presim_registry(
        registry, horizon_hours=48.0, active_tail_hours=8.0,
        story_day=(18.75, 24.0))
    state = presimmed["items"]["town"]["state"]
    assert state["clock_hours"] == pytest.approx(48.0)
    assert charter_phase(state, state["clock_hours"]) == "dusk"
    unanchored, _ = presim_registry(
        {"items": {"town": {"state": _town(), "window_hours": 4.0}}},
        horizon_hours=8.0, active_tail_hours=4.0)
    assert unanchored["items"]["town"]["state"]["day_anchor_hours"] is None
