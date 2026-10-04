"""The planner reads its limits as numbers, never as constant names."""

from __future__ import annotations


def test_the_planner_is_shown_every_limit_as_its_number():
    """Live, the Larch Hill opening (2026-10-04) was told a director_note is
    "at most DIRECTOR_NOTE_CHARS characters" -- the constant's NAME -- wrote
    1249, was refused three times and ran out of time unpublished."""
    import re
    from story.plot_packages import DIRECTOR_NOTE_CHARS, operation_shape_text
    text = operation_shape_text()
    assert not re.findall(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b", text)
    assert f"at most {DIRECTOR_NOTE_CHARS} characters" in text
