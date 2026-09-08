"""One store per question: retirement and a standing hazard of a place.

Review 2026-09-07 finding B8. `world.region_events.apply_wave` wrote a
`ruined` flag and a `hazard` block into the scene beside the two stores that
already owned those questions -- `room_registry.retired_turn_id` and
`world_conditions` -- and the copies were free to disagree. They did: a ruin
stays in the scene on purpose (a ruin is still a place), so the registry
projection in `persist/commit_room_registry.py` saw a live room and cleared
the retirement again on the very next commit.

The rules under test:

* the REGISTRY answers whether a room is retired, and a projection of the
  scene revives a retired row only when the room's live existence BEGINS
  this beat -- the mirror of the retire rule, which fires when it ENDS;
* `world_conditions` answers what stands over a place, and it is the only
  source `world.mechanics` reads for it.
"""
from __future__ import annotations

import json
import time

import pytest

from persist.commit import sync_room_registry_with_scene
from world.mechanics import unanswered_hazard_subjects
from world.region_events import apply_wave


def _room(name, *exits):
    return {"name": name, "desc": name + ".",
            "adjacent": [{"to": e, "barrier": "open_door"} for e in exits]}


def _scene():
    return {"location": "Port", "rooms": {"quay": _room("Quay", "warehouse"),
                                          "warehouse": _room("Warehouse", "quay")},
            "positions": {"Wren Ashby": "warehouse"}}


def _chat(db, *, turns=2):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Ruin", "A port at dusk.", time.time()))
    db.wset(cid, "scene", _scene())
    db.wset(cid, "simulation_clock", {"elapsed_seconds": 0.0})
    book = db.qi("INSERT INTO lorebooks(chat_id,name) VALUES(?,?)", (cid, "Canon"))
    ids = [db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                 "VALUES(?,?,?,?)", (cid, i, "", time.time()))
           for i in range(turns)]
    return cid, book, ids


def _retired(db, cid, rid="warehouse"):
    row = db.q("SELECT retired_turn_id FROM room_registry WHERE chat_id=? "
               "AND room_uid=?", (cid, rid), one=True)
    return row["retired_turn_id"]


def _event(label="the quake", *, destroy=True, damage="burning"):
    return {"label": label, "profile": {"mode": "at_once", "intensity": 1.0},
            "effects": {"damage": damage, "destroy": destroy, "shock": 0.0,
                        "harm": None, "displace": False, "artifacts": [],
                        "news": ""}}


class TestRetirementIsTheRegistrys:
    def test_a_retired_room_that_merely_stands_in_the_scene_stays_retired(
            self, temp_db):
        """The bug B8 names: the ruin came back live one commit later."""
        cid, book, turns = _chat(temp_db)
        scene = temp_db.wget(cid, "scene")
        sync_room_registry_with_scene(cid, book, {}, scene)
        temp_db.qi("UPDATE room_registry SET retired_turn_id=? WHERE chat_id=? "
                   "AND room_uid=?", (turns[-1], cid, "warehouse"))
        # The next commit projects the same scene -- the room never stopped
        # standing there, so nothing about it BEGAN this beat.
        sync_room_registry_with_scene(cid, book, scene, scene)
        assert _retired(temp_db, cid) == turns[-1]

    def test_a_room_that_returns_to_the_scene_is_revived(self, temp_db):
        """The complement: a genuine re-mint still clears the retirement, so
        the rule subtracts a revival it should never have made and no more."""
        cid, book, turns = _chat(temp_db)
        scene = temp_db.wget(cid, "scene")
        sync_room_registry_with_scene(cid, book, {}, scene)
        gone = {**scene, "rooms": {"quay": scene["rooms"]["quay"]}}
        sync_room_registry_with_scene(cid, book, scene, gone)
        assert _retired(temp_db, cid) is not None
        sync_room_registry_with_scene(cid, book, gone, scene)
        assert _retired(temp_db, cid) is None

    def test_a_room_leaving_the_scene_still_retires(self, temp_db):
        cid, book, turns = _chat(temp_db)
        scene = temp_db.wget(cid, "scene")
        sync_room_registry_with_scene(cid, book, {}, scene)
        assert _retired(temp_db, cid) is None
        gone = {**scene, "rooms": {"quay": scene["rooms"]["quay"]}}
        sync_room_registry_with_scene(cid, book, scene, gone)
        assert _retired(temp_db, cid) == turns[-1]


class TestOneStorePerQuestion:
    def test_ruin_writes_the_registry_and_no_scene_flag(self, temp_db):
        cid, book, turns = _chat(temp_db)
        sync_room_registry_with_scene(cid, book, {}, temp_db.wget(cid, "scene"))
        apply_wave(cid, None, _event(), {"rooms": ["warehouse"], "intensity": 1.0},
                   turn_idx=1, turn_id=turns[-1], elapsed=0.0)
        scene = temp_db.wget(cid, "scene")
        room = scene["rooms"]["warehouse"]
        assert "ruined" not in room and "hazard" not in room  # kept as a place
        assert _retired(temp_db, cid) == turns[-1]

    def test_the_ruin_survives_the_next_registry_projection(self, temp_db):
        cid, book, turns = _chat(temp_db)
        scene = temp_db.wget(cid, "scene")
        sync_room_registry_with_scene(cid, book, {}, scene)
        apply_wave(cid, None, _event(), {"rooms": ["warehouse"], "intensity": 1.0},
                   turn_idx=1, turn_id=turns[-1], elapsed=0.0)
        after = temp_db.wget(cid, "scene")
        sync_room_registry_with_scene(cid, book, scene, after)
        assert _retired(temp_db, cid) == turns[-1]

    def test_a_hazard_stands_in_world_conditions(self, temp_db):
        cid, book, turns = _chat(temp_db)
        apply_wave(cid, None, _event(destroy=False),
                   {"rooms": ["warehouse"], "intensity": 0.5},
                   turn_idx=1, turn_id=turns[-1], elapsed=120.0)
        rows = temp_db.q("SELECT condition_id, subject_id, kind, started_at, "
                         "payload FROM world_conditions WHERE chat_id=? AND "
                         "active=1", (cid,))
        assert len(rows) == 1
        payload = json.loads(rows[0]["payload"])
        assert rows[0]["subject_id"] == "warehouse"
        assert payload["state"] == "burning" and payload["severity"] == 0.5
        assert rows[0]["started_at"] == 120.0

    def test_a_later_wave_restates_the_hazard_rather_than_stacking_one(
            self, temp_db):
        cid, book, turns = _chat(temp_db)
        for intensity, at in ((0.5, 120.0), (0.25, 600.0)):
            apply_wave(cid, None, _event(destroy=False),
                       {"rooms": ["warehouse"], "intensity": intensity},
                       turn_idx=1, turn_id=turns[-1], elapsed=at)
        rows = temp_db.q("SELECT started_at, payload FROM world_conditions "
                         "WHERE chat_id=? AND active=1", (cid,))
        assert len(rows) == 1
        assert json.loads(rows[0]["payload"])["severity"] == 0.25
        assert rows[0]["started_at"] == 120.0   # a restatement is not a start


class TestMechanicsReadsOneSource:
    def _bits(self, hazard_block=None, condition=None):
        scene = _scene()
        if hazard_block is not None:
            scene["rooms"]["warehouse"]["hazard"] = hazard_block
        return scene, ([condition] if condition else [])

    def test_a_scene_hazard_block_is_not_a_second_source(self):
        scene, conditions = self._bits(
            hazard_block={"state": "burning", "cause": "a fire",
                          "intensity": 0.9})
        assert unanswered_hazard_subjects(
            scene, conditions, ["Wren Ashby"], {}) == []

    def test_a_condition_over_the_room_is_the_source(self):
        scene, conditions = self._bits(condition={
            "subject_id": "warehouse", "kind": "a fire",
            "payload": {"severity": 0.9}})
        assert unanswered_hazard_subjects(
            scene, conditions, ["Wren Ashby"], {}) == ["Wren Ashby"]

    def test_an_answered_beat_stays_silent(self):
        scene, conditions = self._bits(condition={
            "subject_id": "warehouse", "kind": "a fire",
            "payload": {"severity": 0.9}})
        assert unanswered_hazard_subjects(
            scene, conditions, ["Wren Ashby"], {"dice": [{"roll": 1}]}) == []
