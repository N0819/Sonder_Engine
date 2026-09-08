"""B33: one reader rule for `state_diff.cast_changes[].status`.

The status is a free string, and `story.scene.cast_change_status` reads it
through a vocabulary the engine owns: a word it does not hold answers None.
Two readers then disagreed about what None meant. `commit_cast_changes` left
the roster untouched and warned -- the character stayed `active`, in the scene,
addressable. `spatial_frames._cast_changes_leaving`, the single set behind the
stranded-occupant guard, destruction's vacate and companion carry, tested
`!= CAST_STATUS_PRESENT` and so counted the same entry as a departure.

The cost of the disagreement is at the vacate, whose comment promises "the
guard has already proven every doomed-room occupant repositioned or departed,
so this pop can never lose a person": a status like `"fled"` disarmed the
guard AND popped the position, leaving a character active in the roster and
standing in no room at all, with nothing said about it.

The rule now: an unreadable word MOVES NOBODY. Only `CAST_STATUS_ABSENT` sends
a body out, at the roster and at the scene alike.
"""

from __future__ import annotations

import json
import time

import pytest

from persist.commit import _guard_occupied_mover_removal, commit_cast_changes
from story.scene import (CAST_STATUS_ABSENT, CAST_STATUS_PRESENT,
                         cast_change_status)
from world import spatial_frames

# Words a model reaches for that the vocabulary does not hold. Illustrations
# of the class "unreadable", not a list the engine matches against.
UNREADABLE = ("fled", "bewildered", "asleep", "", None)


class TestTheLeavingSet:
    def test_an_unreadable_status_sends_nobody_out(self):
        for word in UNREADABLE:
            assert spatial_frames._cast_changes_leaving(
                [{"who": "Mira", "status": word}]) == set(), word

    def test_a_readable_departure_still_sends_them_out(self):
        assert spatial_frames._cast_changes_leaving(
            [{"who": "Mira", "status": "departed"}]) == {"mira"}
        assert spatial_frames._cast_changes_leaving(
            [{"who": "Mira", "status": "dormant"}]) == {"mira"}

    def test_an_arrival_is_still_not_a_departure(self):
        """The defect this set was built to fix, kept fixed."""
        assert spatial_frames._cast_changes_leaving(
            [{"who": "Mira", "status": "arrived"}]) == set()

    def test_the_two_readers_now_answer_one_question_the_same_way(self):
        """No word may be a departure to the scene and not to the roster."""
        for word in UNREADABLE + ("departed", "active", "dormant", "arrived"):
            leaves_the_scene = bool(spatial_frames._cast_changes_leaving(
                [{"who": "Mira", "status": word}]))
            leaves_the_roster = (
                cast_change_status(word) == CAST_STATUS_ABSENT)
            assert leaves_the_scene is leaves_the_roster, word


def _doomed_scene():
    return {
        "rooms": {
            "quay": {"name": "The Quay", "adjacent": []},
            "hold": {"name": "Hold", "adjacent": [], "parent_entity": "ship"},
        },
        "entities": {"ship": {"kind": "vehicle", "name": "Ship",
                              "interior_rooms": ["hold"]}},
        "positions": {"Mira": "hold", "ship": "quay"},
    }


class TestTheStrandingGuard:
    def test_an_unreadable_exit_is_no_exit(self):
        """Previously the guard let this through and destruction's vacate
        popped Mira's position, while the roster kept her active."""
        diff = {"remove_entities": ["ship"],
                "cast_changes": [{"who": "Mira", "status": "fled"}]}
        with pytest.raises(RuntimeError, match="strand.*Mira"):
            _guard_occupied_mover_removal(_doomed_scene(), diff)

    def test_a_recorded_departure_is_still_a_legal_exit(self):
        diff = {"remove_entities": ["ship"],
                "cast_changes": [{"who": "Mira", "status": "departed",
                                  "reason": "over the side"}]}
        _guard_occupied_mover_removal(_doomed_scene(), diff)


class TestTheRoster:
    def test_the_roster_is_the_answer_the_scene_now_agrees_with(self, temp_db):
        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) "
                         "VALUES(?,?,?)", ("Story", "", time.time()))
        char = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
            ("Mira", json.dumps({"identity": {"name": "Mira"}}), "{}",
             time.time()))
        temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status) "
                   "VALUES(?,?,?)", (cid, char, CAST_STATUS_PRESENT))
        turn_id = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) "
            "VALUES(?,?,?,?)", (cid, 1, "", time.time()))

        from core.pipeline_context import ChatData, PipelineContext, TurnData
        ctx = PipelineContext(
            chat=ChatData(id=cid, name="Story", persona_id=None,
                          lorebook_id=None, scenario="", created=time.time()),
            turn=TurnData(id=turn_id, chat_id=cid, idx=1, player_input="",
                          created=time.time(), frame_id=None),
            cast=[], input="")
        ctx.director_resolve = {"state_diff": {"cast_changes": [
            {"who": "Mira", "status": "fled"}]}}
        commit_cast_changes(ctx, nonce=0)

        row = temp_db.q("SELECT status FROM chat_chars WHERE chat_id=? AND "
                        "char_id=?", (cid, char), one=True)
        assert row["status"] == CAST_STATUS_PRESENT
        assert any("fled" in w for w in ctx.warnings), ctx.warnings
        assert spatial_frames._cast_changes_leaving(
            [{"who": "Mira", "status": "fled"}]) == set()


class TestCompanionCarry:
    def test_a_companion_whose_status_could_not_be_read_is_still_carried(
        self, temp_db,
    ):
        """She is still active in the roster and still standing beside the
        player; the exemption is for someone the beat sent AWAY."""
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Test", "", time.time()))
        prev_scene = {
            "rooms": {
                "room_a": {"name": "Room A", "adjacent": []},
                "ship_cockpit": {"name": "Cockpit", "adjacent": [],
                                 "parent_entity": "ship"},
            },
            "entities": {"ship": {"kind": "vehicle", "name": "Ship",
                                  "interior_rooms": ["ship_cockpit"]}},
            "positions": {"The Stranger": "room_a", "Reya": "room_a",
                          "ship": "room_a"},
            "attire": {}, "overlays": {},
        }
        new_scene = json.loads(json.dumps(prev_scene))
        new_scene["positions"]["The Stranger"] = "ship_cockpit"

        changed = spatial_frames.infer_companion_carry(
            chat_id, None, prev_scene, new_scene, ["Reya"],
            [{"who": "Reya", "status": "bewildered"}])

        assert changed is True
        assert new_scene["positions"]["Reya"] == "ship_cockpit"
