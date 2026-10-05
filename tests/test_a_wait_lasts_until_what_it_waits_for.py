"""A step the prose measures by its end lasts until that end.

Live, Larch Hill (scratch chat 165 turn 5, 2026-10-04): "we stay up in the
cabin talking while the light goes. When it is fully dark..." -- the
Director's account let the dusk run out, the encoder priced the wait at an
hour because nothing told it the time, the clock read 16:48 in the afternoon
and the page said full dark. "For the next three hours" on the next beat was
honoured exactly. The owner: "Those sound like they need repair."
"""

from __future__ import annotations

from world.day_cycle import SUN_LIGHT, phase_of_hour, seconds_until
from tests.helpers import model_dict


def test_until_dark_runs_to_the_day_cycles_own_dark():
    # 16:48 -> evening, dark by SUN_LIGHT, begins 19:30
    assert seconds_until(16.8, light="dark") == round(2.7 * 3600, 1)
    assert SUN_LIGHT[phase_of_hour(16.8 + 2.7)] == "dark"
    # already dark is reached now; first light and full day come after
    assert seconds_until(23.0, light="dark") == 0.0
    assert seconds_until(23.0, light="dim") == 7.0 * 3600
    assert seconds_until(23.0, light="lit") == 8.0 * 3600


def test_until_an_hour_is_the_next_time_the_clock_reads_it():
    assert seconds_until(16.8, hour=24) == round(7.2 * 3600, 1)
    assert seconds_until(23.0, hour=6) == 7.0 * 3600
    assert seconds_until(12.0, light="moonrise") is None


def test_a_wait_after_other_steps_starts_when_they_end():
    from agents.director_prose import ledger_from_events
    events = [
        {"event": "They talk.", "seconds": 1800},                 # 16:48 -> 17:18
        {"event": "They stay until it is fully dark.", "until_light": "dark"},
        {"event": "She looks down the valley.", "seconds": 5},
    ]
    rows, _ = ledger_from_events(events, start_hour=16.8)
    assert [r.get("seconds") for r in rows] == [1800, round(2.2 * 3600, 1), 5]


def test_a_step_without_a_clock_keeps_what_it_wrote():
    from agents.director_prose import ledger_from_events
    rows, _ = ledger_from_events([{"event": "x", "seconds": 60, "until_light": "dark"}])
    assert rows[0]["seconds"] == 60


def test_the_encoder_schema_keeps_a_steps_end():
    from llm.schemas import UnifiedEvent
    event = UnifiedEvent(event="They wait.", until_light="dark", until_hour=None)
    dumped = model_dict(event)
    assert dumped["until_light"] == "dark"
