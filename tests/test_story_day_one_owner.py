"""The story day has ONE owner, and every reader asks it.

Review 2026-09-07 finding B9 ("two representations free to disagree"): four
sites answered "how long is a day, and which part of it is this" for
themselves instead of asking `world/day_cycle` --

  * `world/routines.py` kept a literal ``86400.0``, so a tavern's watches
    stayed Terran on a world whose author had set ``day_length_hours``;
  * `dressing/backdrops.py._hour_bucket` cut the day at 5/11/17/21 against
    the cycle's 4.5/7/11/13.5/18/19.5/22, so one moment written "09:42 PM"
    got a night backdrop while the same moment written "evening" got an
    evening one;
  * `world/day_cycle.clock_reading_hour` refused any hour past 23 while
    both of its callers already carried the world's own day length;
  * `agents/mapping.rulebook_rows` carried a second copy of the sun-light
    table and its dimming rule.

Each test below is one of those sites reading the owner.
"""

from __future__ import annotations

import time

import pytest

from world.day_cycle import (
    DAY_LENGTH_HOURS_DEFAULT, PHASE_NAMES, clock_reading_hour, label_hour,
    label_phase, phase_bounds_hours, phase_of_hour, sun_light,
)


def _make_chat(db):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )


def test_the_scenery_bucket_cuts_the_day_where_the_cycle_does():
    """The four scenery buckets are this file's own coarseness; WHERE the
    day is cut is not. Every hour buckets as the phase it falls in does."""
    from dressing.backdrops import _PHASE_BUCKETS, _hour_bucket, time_bucket

    assert set(_PHASE_BUCKETS) == set(PHASE_NAMES)
    for tenth in range(int(DAY_LENGTH_HOURS_DEFAULT) * 10):
        hour = tenth / 10.0
        assert _hour_bucket(hour) == time_bucket(phase_of_hour(hour)), hour

    # The three readings the old boundaries answered differently from the
    # phase word for the same moment.
    assert time_bucket("09:42 PM") == time_bucket("evening") == "evening"
    assert time_bucket("05:10") == time_bucket("pre-dawn") == "night"
    assert time_bucket("17:30") == time_bucket("afternoon") == "day"


def test_a_clock_reading_is_bounded_by_this_worlds_day():
    """A reading is a time on the clock the story keeps: 27:30 is a time on
    a thirty-hour world and on no Terran one, and the bound is
    `day_length_hours` rather than a restatement of 24."""
    assert clock_reading_hour("27:30") is None
    assert clock_reading_hour("27:30", 30.0) == pytest.approx(27.5)
    assert label_phase("27:30", 30.0) == "night"
    assert label_hour("27:30", 30.0) == pytest.approx(27.5)

    # What the corpus earned stays earned: an ordinary reading, a countdown
    # that is not a time, and a reading past the end of a SHORT day refused
    # rather than wrapped around it.
    assert clock_reading_hour("23:47") == pytest.approx(23.783, abs=0.01)
    assert clock_reading_hour("Cycle-End -01:45:00") is None
    assert label_phase("22:00", 20.0) is None


def test_a_routine_turns_on_this_worlds_day():
    """The watches divide the story's day, so a rhythm and the sun it is
    kept by turn over together: the same FRACTION of a thirty-hour day and
    of a Terran one stand at the same band."""
    from world import routines

    assert routines.DAY_SECONDS == DAY_LENGTH_HOURS_DEFAULT * 3600.0

    key = "room:1:tavern"
    long_day = 30 * 3600.0
    for tenth in range(10):
        fraction = tenth / 10.0
        assert routines.routine_band(key, fraction * long_day, long_day) == \
            routines.routine_band(key, fraction * routines.DAY_SECONDS)
    # Handed nothing usable, a day is still a day.
    assert routines.routine_band(key, 100.0, 0) == \
        routines.routine_band(key, 100.0)

    # Food keeps for a day, and a day is thirty hours where the author said
    # so -- twenty-five hours is stale on Earth and fresh there.
    tavern = "The Brass Tankard tavern"
    assert routines.entropy_facts(tavern, 25 * 3600.0)
    assert routines.entropy_facts(tavern, 25 * 3600.0, long_day) == []
    assert routines.entropy_facts(tavern, 31 * 3600.0, long_day)


def test_the_residue_reads_the_authors_day(temp_db):
    """`residue_for` is where the routine meets a story, so it is where the
    day's length is resolved -- from `day_cycle.day_length_hours` over the
    author's style guide, the one owner of the dial."""
    from core.db import wset
    from world.routines import residue_for

    cid = _make_chat(temp_db)
    wset(cid, "subject_last_seen",
         {"tap": {"turn": 1, "room": "tap", "elapsed_seconds": 0.0}})
    scene = {"rooms": {"tap": {"name": "The Brass Tankard tavern"}}}

    out = residue_for(cid, scene, "tap", now_seconds=25 * 3600.0)
    assert any("food or drink" in fact for fact in out["facts"])

    wset(cid, "style_guide", {"day_length_hours": 30})
    out = residue_for(cid, scene, "tap", now_seconds=25 * 3600.0)
    assert out is None or not any(
        "food or drink" in fact for fact in out["facts"])


def test_the_rulebook_states_the_light_the_cycle_gives(temp_db):
    """The Director's rulebook row says what an outdoor room has to see by,
    and that sentence is `day_cycle.sun_light`'s answer rather than a
    second copy of its table and its dimming rule."""
    from agents.mapping import rulebook_rows
    from core.db import wset_for_frame

    cid = _make_chat(temp_db)
    for phase in PHASE_NAMES:
        start, end = phase_bounds_hours(phase)
        hour = ((start + end) / 2.0) % DAY_LENGTH_HOURS_DEFAULT
        for sky in ("clear", "fog", "storm", "overcast"):
            wset_for_frame(cid, "simulation_clock",
                           {"hour_of_day": hour, "phase": phase,
                            "day_length_hours": DAY_LENGTH_HOURS_DEFAULT},
                           None)
            rows = {row["source"]: row for row in
                    rulebook_rows(cid, {"weather": {"sky": sky}}, None)}
            assert "%s light" % sun_light(phase, sky) in \
                rows["day_cycle"]["text"], (phase, sky)
