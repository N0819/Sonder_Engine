"""What changes is written in its record, never only as an observable or a
sound.

Two measured failures of one class (the owner's review of chats 175-178,
2026-10-19), reduced to one core clause:

- WHERE A BODY GOES IS ITS MOVEMENT AND POSITIONS. Chat 178 turn 23: the
  interpret encoder, `positions` granted, wrote Hinami's walk down to the
  kitchen with a position and her walk back up to the second room with none
  -- the return lived only in its observable, and the world kept her
  downstairs.
- THE SOUND OF A CHANGE IS NOT THE CHANGE. Chat 177 turn 20: "turns the
  latch until it catches" was encoded as a station, a pose and a click, and
  the casement was "unlatched" again the next beat; chat 175 turn 1's door
  "swings inward with a single complaining creak" was a creak and no door.
"""

from __future__ import annotations

from llm.prompts import unified_specialist_prompt


def test_the_core_says_a_change_is_written_in_its_record():
    en = unified_specialist_prompt([], "en", [])
    ja = unified_specialist_prompt([], "ja", [])
    assert "what changes is written in its record, never only as an observable or a sound" in en
    assert "where a body goes is its movement and positions" in en
    assert "observable や音だけで済ませてはいけません" in ja
    # A rule needs its field: both records the clause names are on the
    # event's own shape or a channel the encoder holds.
    from llm.schemas import UnifiedEvent, _fields
    from agents.director import SPECIALISTS
    assert "movement" in _fields(UnifiedEvent)
    assert any("positions" in spec["channels"] for spec in SPECIALISTS.values())
