"""A clock reading in the twelve o'clock hour with an a.m. marker is the hour
after midnight.

world_offscreen_time F4 (audit 2026-11-01): `clock_reading_hour` had a p.m.
rule and no a.m. rule, so "Late night, 12:40 AM" read as 12:40 -- midday --
and every reader of a written label (the opening anchor, a declared
re-anchor, a skip "until 12:30 am", the itinerary windows) landed twelve
hours off: outdoor rooms lit at midnight, the sun up, the charter's errands
run at night. "Midnight, 12:00" (a phase word beside a reading it
contradicts) is a separate question and is not decided here.
"""

import pytest

from world import day_cycle


@pytest.mark.parametrize("label, hour", [
    ("Late night, 12:40 AM", 40 / 60),
    ("12:30 a.m.", 0.5),
    ("12:05am", 5 / 60),
    ("00:30", 0.5),
    ("11:15 am", 11.25),
    ("12:30 p.m.", 12.5),
    ("12:00 PM", 12.0),
    ("3:10 pm", 15 + 10 / 60),
])
def test_the_marker_places_the_hour(label, hour):
    assert day_cycle.clock_reading_hour(label) == pytest.approx(hour)


def test_the_phase_follows_the_hour():
    assert day_cycle.label_phase("Late night, 12:40 AM") == "night"
    assert day_cycle.label_phase("12:30 a.m.") == "night"
    assert day_cycle.label_phase("12:30 p.m.") == "midday"
