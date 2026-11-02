"""An extra player's seat with no view this beat is told so in the story's
language, as the primary seat is.

`narrator` falls back to the pack's `narrator_nothing` (`narrator_immediate`
at the opening); `narrator_extra` fell back to the English literal "Nothing
in particular reaches you this beat." in every story (review 2026-11-01,
agents_narration_planner F15).
"""

from __future__ import annotations

import inspect

from agents import narration
from language_runtime import compositor_text


def test_the_extra_seat_reads_the_packs_words():
    src = inspect.getsource(narration.narrator_extra)
    assert "Nothing in particular reaches you this beat." not in src
    assert 'compositor_text("narrator_immediate" if est else "narrator_nothing"' in src
    assert compositor_text("narrator_nothing", "ja") != compositor_text("narrator_nothing", "en")
