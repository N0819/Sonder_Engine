"""ONE fold decides whether the world already holds a room.

Review 2026-09-07 finding B2: four sites answered "does the scene have this
room?" three different ways for the same beat. `classify_movement` and the
Director's `needs_mapping` trigger compared the model's spelling to the scene
KEYS exactly; `_location_query_status` folded id and name; commit's
`dedup_minted_rooms` folded through its own private `_room_display_slug`,
which read an incoming id against a held room's id but never against its
NAME. So a Director spelling a room the scene already held its own way drew a
planning need and a room-description request at one end and a redirect at the
other.

A room answers to its id and to its name, folded -- `spatial.room_spellings`
is the only producer of that set and `spatial.scene_room_id` the only reader
of the scene by it. A spelling two rooms answer to names neither.

Database-independent apart from the commit-side dedup case, which needs a
chat row.
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.director import _beat_rooms
from agents.mapping import _location_query_status, classify_movement
from agents.perception import _declared_arrival_room
from core.pipeline_context import canonical_movement
from world.spatial import room_spellings, scene_room_id


def _scene():
    return {"rooms": {"r_dock_7": {"name": "Lantern Path", "adjacent": []},
                      "beach": {"name": "Moonlit Shore", "adjacent": []}},
            "positions": {"Hinami": "beach"}}


def _never(_spelling):
    return None


class TestTheSpellingsARoomAnswersTo:
    def test_a_room_answers_to_its_name_and_to_its_id(self):
        assert room_spellings("r_dock_7", {"name": "Lantern Path"}) == (
            "lantern_path", "r_dock_7")
        # No name: the id is the display slug and the only spelling.
        assert room_spellings("beach", {}) == ("beach",)
        assert room_spellings("", None) == ()

    def test_the_scene_is_read_by_that_set(self):
        sc = _scene()
        assert scene_room_id(sc, "r_dock_7") == "r_dock_7"
        assert scene_room_id(sc, "Lantern Path") == "r_dock_7"
        assert scene_room_id(sc, "lantern_path") == "r_dock_7"
        assert scene_room_id(sc, "drowned_chapel") == ""
        assert scene_room_id(None, "beach") == ""

    def test_a_spelling_two_rooms_answer_to_names_neither(self):
        sc = {"rooms": {"hall": {"name": "Great Hall"},
                        "great_hall": {"name": ""}}}
        assert scene_room_id(sc, "great hall") == ""
        # An exact key still wins outright -- it is not a guess.
        assert scene_room_id(sc, "great_hall") == "great_hall"


class TestTheCompilerAndTheQueryAgree:
    def test_a_held_room_spelled_by_its_name_is_known(self):
        """Before B2 this returned `unplanned`, and the beat filed a
        planning need for a room already on the map."""
        out = classify_movement({"movement": {"to_room": "Lantern Path"}},
                                _scene(), planned_for=_never)
        assert out == {"to_room": "r_dock_7", "status": "known",
                       "declared_as": "Lantern Path"}

    def test_an_exactly_spelled_room_carries_no_second_spelling(self):
        out = classify_movement({"movement": {"to_room": "beach"}},
                                _scene(), planned_for=_never)
        assert out == {"to_room": "beach", "status": "known"}

    def test_a_room_the_world_does_not_have_is_still_unplanned(self):
        out = classify_movement({"movement": {"to_room": "drowned_chapel"}},
                                _scene(), planned_for=_never)
        assert out == {"to_room": "drowned_chapel", "status": "unplanned"}

    def test_the_location_query_reads_the_same_spellings(self):
        # A query is a DESCRIPTION, so the predicate stays containment; the
        # spellings it contains are the shared ones.
        assert _location_query_status("Lantern Path lanterns and occupants",
                                      _scene(), planned_for=_never) == "known"
        assert _location_query_status("the drowned chapel", _scene(),
                                      planned_for=_never) == "unmatched"


class TestTheResolvedIdIsCarried:
    def test_the_canonical_destination_takes_a_known_resolution(self):
        """`canonical_movement` propagated the compiler's id only for
        `planned`; a room the scene itself holds resolves the same way."""
        declared = {"to_room": "Lantern Path", "why": "steps in"}
        compiled = {"to_room": "r_dock_7", "status": "known"}
        assert canonical_movement(declared, compiled) == {
            "to_room": "r_dock_7", "why": "steps in",
            "declared_as": "Lantern Path"}
        # Nothing resolved, nothing rewritten.
        assert canonical_movement(
            declared, {"to_room": "Lantern Path", "status": "unplanned"}
        ) is declared

    def test_perception_grades_arrival_by_the_worlds_id(self):
        sc = _scene()
        assert _declared_arrival_room(
            sc, {"movement": {"to_room": "Lantern Path"}}, "beach") == "r_dock_7"
        # Already there under the world's spelling: nothing was declared.
        assert _declared_arrival_room(
            sc, {"movement": {"to_room": "Lantern Path"}}, "r_dock_7") == ""

    def test_a_hands_beat_rooms_include_the_declared_destination(self):
        sc = _scene()
        view = {"declaration": {"movement": {"to_room": "Lantern Path"}}}
        assert _beat_rooms(sc, None, ["Hinami"], view=view) == [
            "beach", "r_dock_7"]


def test_a_mint_whose_id_is_a_held_rooms_name_is_redirected(temp_db):
    """The held room is keyed `r_dock_7` and NAMED "Lantern Path"; the hand
    mints `lantern_path` under a fresh name. The old comparison read the
    incoming id against the held id only, so it minted a duplicate."""
    from persist.commit import dedup_minted_rooms
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Folded", "", time.time()))
    prev = {"rooms": {"r_dock_7": {"name": "Lantern Path", "adjacent": []}},
            "positions": {"Hinami": "r_dock_7"}}
    diff = {"rooms": {"lantern_path": {"name": "Lit Path", "desc": "Lanterns.",
                                       "adjacent": []}},
            "positions": {"Hinami": "lantern_path"}}
    assert dedup_minted_rooms(cid, prev, diff) == {"lantern_path": "r_dock_7"}
    assert set(diff["rooms"]) == {"r_dock_7"}
    assert diff["positions"] == {"Hinami": "r_dock_7"}


def test_a_genuinely_new_room_is_still_minted(temp_db):
    """Ledger, not cage: the fold must not swallow an invention."""
    from persist.commit import dedup_minted_rooms
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Folded", "", time.time()))
    prev = {"rooms": {"r_dock_7": {"name": "Lantern Path", "adjacent": []}}}
    diff = {"rooms": {"drowned_chapel": {"name": "Drowned Chapel",
                                         "adjacent": []}}}
    assert dedup_minted_rooms(cid, prev, diff) == {}
    assert set(diff["rooms"]) == {"drowned_chapel"}
