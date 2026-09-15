"""A cast member is a body whether or not the opening minted one, and a walk
is the walker's own.

Scratch play 2026-09-14, chat 9: the establish minted no entity for the
companion or the captain, so both stood as positions with no record. On turn
5 "Captain Edmund Hale" resolved to no entity, the movement fallback read his
walk into the card room as the player's, and the companion was stood in the
room she had just refused to enter. The positions table is where the engine
stands a body; a record is minted from it, and a mover the scene cannot place
moves nobody.
"""

import json

from agents.common import ensure_cast_entities
from agents.director import _resolve_movement_mover


CAST = [{"id": 11, "sheet": json.dumps({"identity": {"name": "Captain Edmund Hale"}})}]


def test_a_placed_cast_member_without_a_record_gets_one():
    scene = {"entities": {"mr_pellew": {"name": "Mr Pellew", "kind": "person"}},
             "positions": {"Clara Penrose": "ballroom", "Captain Edmund Hale": "ballroom",
                           "mr_pellew": "ballroom", "negus_glasses": "ballroom"}}
    minted = ensure_cast_entities(scene, CAST, player_name="Clara Penrose")
    assert sorted(minted) == [("char_captain_edmund_hale", "Captain Edmund Hale"),
                              ("char_clara_penrose", "Clara Penrose")]
    assert scene["entities"]["char_captain_edmund_hale"]["kind"] == "person"
    assert "negus_glasses" not in {n for _e, n in minted}
    # Idempotent: a second pass mints nothing.
    assert ensure_cast_entities(scene, CAST, player_name="Clara Penrose") == []


def test_a_cast_member_already_recorded_is_left_alone():
    scene = {"entities": {"char_x": {"name": "Captain Edmund Hale", "kind": "person"}},
             "positions": {"Captain Edmund Hale": "ballroom"}}
    assert ensure_cast_entities(scene, CAST) == []


def test_a_mover_the_positions_table_stands_resolves_without_a_record():
    scene = {"entities": {}, "positions": {"Captain Edmund Hale": "ballroom"}}
    key, room, eid = _resolve_movement_mover(
        scene, {}, {"mover": "captain edmund hale", "to_room": "card_room"}, "Clara Penrose")
    assert (key, room, eid) == ("Captain Edmund Hale", "ballroom", None)


def test_a_mover_nobody_can_place_resolves_to_nobody():
    scene = {"entities": {}, "positions": {"Clara Penrose": "ballroom"}}
    assert _resolve_movement_mover(
        scene, {}, {"mover": "a stranger", "to_room": "card_room"}, "Clara Penrose") == (None, None, None)
