"""The room designer is offered `offset` -- a place along a wall -- for the
fixture or doorway the prose fixes there, in both packs, and is told that the
engine stands every other new fixture along the wall it was given and says
when a wall cannot hold them (`world/spatial_pack.py`). The engine read
`offset` already; the designer wrote it unprompted in 4 steps of the 2026-10-08
play database and was never told what it meant."""

from __future__ import annotations

import pytest

from llm.prompts import room_author_prompt


@pytest.mark.parametrize("language", ["en", "ja"])
def test_the_room_author_is_offered_a_place_along_the_wall(language):
    sheet = room_author_prompt(language)
    assert "`offset`" in sheet
    head = sheet.split("`offset`", 1)[0]
    assert head.count("anchors") >= 1, "offered beside the fixtures it places"
