"""A room's name being a placeholder is a FACT the mint records, not a guess.

D8 -- a room is called what a mind learned to call it -- was built, reworked
and then held at the gate on this (review 2026-09-07 § K, 2026-09-08):

    `is_derived_room_name` cannot tell an AUTHORED name from the placeholder
    a nameless room wears, whenever the authored name is the id spelled out
    -- which is how rooms are ordinarily named. `market_square`/"Market
    Square", `crossroads`/"Crossroads" and `spine`/"Spine" all read as
    placeholders, so the name would have been withheld from every mind
    forever, and a room whose only content was its name composed an EMPTY
    view. A hyphen or an article saved a name by accident and nothing else
    did.

There is no string rule that separates the two, so the placeholder says so
where it is written. `merge_scene_with_diff` mints it and marks it; a later
name clears the mark; `room_name_is_placeholder` asks the room, and falls
back to the old spelling test only for a scene written before the mark
existed, where the guess is all there is.
"""
from __future__ import annotations

import pytest

from world.spatial import (ROOM_NAME_DERIVED, derived_room_name,
                           is_derived_room_name, merge_scene_with_diff,
                           room_name_is_placeholder)


def _scene():
    return {"rooms": {}, "positions": {}, "entities": {}}


ID_SHAPED = ["market_square", "crossroads", "spine", "the_gate"]


@pytest.mark.parametrize("room_id", ID_SHAPED)
def test_an_authored_name_that_looks_like_the_id_is_not_a_placeholder(room_id):
    """The case that held D8: every one of these is a name a planner really
    writes, and every one of them the spelling test calls a placeholder."""
    authored = derived_room_name(room_id)
    assert is_derived_room_name(room_id, authored), "the old guess, for contrast"

    scene = merge_scene_with_diff(
        _scene(), {"rooms": {room_id: {"name": authored, "desc": "Cobbles."}}})
    room = scene["rooms"][room_id]
    assert room["name"] == authored
    assert room_name_is_placeholder(room, room_id) is False


@pytest.mark.parametrize("room_id", ID_SHAPED)
def test_a_room_minted_nameless_wears_a_placeholder_and_says_so(room_id):
    scene = merge_scene_with_diff(
        _scene(), {"rooms": {room_id: {"desc": "Bare walls."}}})
    room = scene["rooms"][room_id]
    assert room["name"] == derived_room_name(room_id)
    assert room[ROOM_NAME_DERIVED] is True
    assert room_name_is_placeholder(room, room_id) is True


def test_naming_a_placeholder_room_clears_the_mark():
    scene = merge_scene_with_diff(
        _scene(), {"rooms": {"market_square": {"desc": "Cobbles."}}})
    assert room_name_is_placeholder(scene["rooms"]["market_square"],
                                    "market_square") is True

    scene = merge_scene_with_diff(
        scene, {"rooms": {"market_square": {"name": "The Shambles"}}})
    room = scene["rooms"]["market_square"]
    assert room["name"] == "The Shambles"
    assert room_name_is_placeholder(room, "market_square") is False


def test_echoing_the_placeholder_back_is_not_naming_it():
    """A specialist handed "Market Square" and returning it unchanged has not
    named anything -- the establishing sheet says outright that a planned
    room's name is a placeholder and naming it is the model's job. The engine
    cannot tell an echo from a choice, and this is the direction that costs
    less: a room described rather than labelled, instead of a mind told a
    name the engine invented.
    """
    scene = merge_scene_with_diff(
        _scene(), {"rooms": {"market_square": {"desc": "Cobbles."}}})
    echoed = merge_scene_with_diff(
        scene, {"rooms": {"market_square": {"name": "Market Square",
                                            "desc": "Cobbles and stalls."}}})
    room = echoed["rooms"]["market_square"]
    assert room["desc"] == "Cobbles and stalls."      # the rest still lands
    assert room_name_is_placeholder(room, "market_square") is True


def test_a_scene_written_before_the_mark_still_gets_an_answer():
    """The fallback, and its known cost: with no mark there is only the
    spelling, so an old scene's "Market Square" still reads as a placeholder.
    That is the state D8 was blocked on, and it now applies to stored scenes
    alone rather than to every room the engine mints."""
    old = {"name": "Market Square", "desc": "Cobbles."}
    assert room_name_is_placeholder(old, "market_square") is True
    assert room_name_is_placeholder({"name": "The Shambles"},
                                    "market_square") is False


def test_the_mint_marks_what_it_mints_and_nothing_else():
    """The mark is written at the one point a room ENTERS the scene. A room
    that predates it -- a stored scene from before 2026-09-08 -- keeps its
    answer from the spelling fallback, and a redeclaration does not invent a
    mark for it: the merge has no way to know what that name once was."""
    old = {"rooms": {"hall": {"name": "The Long Hall", "adjacent": []}},
           "positions": {}, "entities": {}}
    scene = merge_scene_with_diff(old, {"rooms": {"hall": {"desc": "Cold."}}})
    room = scene["rooms"]["hall"]
    assert ROOM_NAME_DERIVED not in room, "no mark invented for an old room"
    assert room["desc"] == "Cold."
    # The fallback still answers, correctly here: this name is not the id.
    assert room_name_is_placeholder(room, "hall") is False

    # And a room the mint DOES see is marked, either way.
    minted = merge_scene_with_diff(
        _scene(), {"rooms": {"hall": {"name": "The Long Hall"}}})
    assert minted["rooms"]["hall"][ROOM_NAME_DERIVED] is False
