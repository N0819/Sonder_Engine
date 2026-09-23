"""Two causality bubbles whose people meet become one thread.

Two bubbles of one era are two threads of one town. Measured on the playerless
Aldermill runs (2026-09-23): Emory and Sal could stand in one room of the one
town and not see each other, because only a bubble and its parent could ever
merge -- the siblings had no path to each other at all.

The meeting is judged on the range a bubble opens on (the same room, or one
step of adjacency), from each side's own scene. The committing frame survives;
the other's clock, knowledge, people, their lived state, the map it drew, its
pending fuses and the town bodies it stood all come across.
"""

from __future__ import annotations

import json
import time

from core.db import active_frame_id, q, wget_for_frame, wset, wset_for_frame
from core.frames import get_frame, is_memory_visible
from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import default_character_data
from story.scene import active_cast, char_state, set_char_state
from world import spatial as sp
from world import spatial_bubbles, spatial_frames
from world.charter_place import rehold_leases


ROOMS = {
    "mill_race": {"name": "Mill Race", "adjacent": [{"to": "mill_floor", "barrier": "open"}]},
    "mill_floor": {"name": "Mill Floor", "adjacent": [
        {"to": "mill_race", "barrier": "open"}, {"to": "market", "barrier": "open"}]},
    "market": {"name": "Market Square", "adjacent": [{"to": "mill_floor", "barrier": "open"}]},
    "attic": {"name": "Attic", "adjacent": []},
}


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Aldermill", "", time.time()))


def _char(db, chat_id, name):
    char_id = db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        (name, json.dumps(default_character_data(name)), "{}", time.time()))
    db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
          "VALUES(?,?,'active','{}')", (chat_id, char_id))
    return char_id


def _two_lives(db, *, sal_at="market"):
    """Emory at the race, Sal elsewhere; one bubble each, as the harness
    opens them, and nobody playing."""
    chat_id = _chat(db)
    ids = {"Emory Vane": _char(db, chat_id, "Emory Vane"),
           "Sal Weatherby": _char(db, chat_id, "Sal Weatherby")}
    wset(chat_id, "scene", {"rooms": json.loads(json.dumps(ROOMS)),
                            "positions": {"Emory Vane": "mill_race",
                                          "Sal Weatherby": sal_at},
                            "entities": {}})
    wset(chat_id, "simulation_clock", {"elapsed_seconds": 0.0})
    frames = {name: spatial_frames.perform_split(
        chat_id, None, turn, bubble=True, away_names=[name])
        for turn, name in enumerate(sorted(ids), start=1)}
    return chat_id, ids, frames


def _move(chat_id, frame_id, name, room):
    scene = wget_for_frame(chat_id, "scene", frame_id, {}) or {}
    scene["positions"][name] = room
    wset_for_frame(chat_id, "scene", scene, frame_id)


def _reconcile(chat_id, frame_id, turn_idx):
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Aldermill", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=None, chat_id=chat_id, idx=turn_idx, player_input="",
                      created=time.time(), frame_id=frame_id),
        cast=[], input="")
    token = active_frame_id.set(frame_id)
    try:
        return spatial_frames.detect_and_reconcile(ctx, 0)
    finally:
        active_frame_id.reset(token)


class TestTheRange:
    def _decide(self, room_a, room_b, comms=None):
        a = {"rooms": ROOMS, "positions": {"Emory Vane": room_a}}
        b = {"rooms": ROOMS, "positions": {"Sal Weatherby": room_b}}
        if comms:
            for scene in (a, b):
                sp.apply_comms_ops(scene, comms)
        return spatial_bubbles.sibling_meet_decision(
            a, ["Emory Vane"], b, ["Sal Weatherby"])

    def test_one_room_or_one_step_is_together(self):
        assert self._decide("mill_floor", "mill_floor")
        assert self._decide("mill_race", "mill_floor")

    def test_two_steps_is_apart(self):
        assert not self._decide("mill_race", "market")

    def test_a_voice_over_a_wire_is_not_standing_together(self):
        handset = [{"id": "handset", "name": "the handset",
                    "carriers": ["Emory Vane", "Sal Weatherby"]}]
        assert not self._decide("mill_race", "market", comms=handset)


class TestTheyMeet:
    def test_apart_they_stay_two_threads(self, temp_db):
        chat_id, _ids, frames = _two_lives(temp_db)
        out = _reconcile(chat_id, frames["Emory Vane"], 5)
        assert not out.get("sibling_merged")
        assert len(spatial_bubbles_live(chat_id)) == 2

    def test_within_reach_the_committing_frame_takes_the_other(self, temp_db):
        chat_id, ids, frames = _two_lives(temp_db)
        emory, sal = frames["Emory Vane"], frames["Sal Weatherby"]
        _move(chat_id, sal, "Sal Weatherby", "mill_floor")
        wset_for_frame(chat_id, "simulation_clock", {"elapsed_seconds": 900.0}, sal)
        wset_for_frame(chat_id, "simulation_clock", {"elapsed_seconds": 600.0}, emory)
        set_char_state(chat_id, ids["Sal Weatherby"],
                       json.dumps({"active_state": {"mood": "wary"}}), frame_id=sal)

        out = _reconcile(chat_id, emory, 5)

        assert out == {"sibling_merged": True, "survivor_frame_id": emory,
                       "absorbed_frame_id": sal, "warnings": out["warnings"]}
        assert get_frame(sal)["merged_turn_idx"] == 5
        assert spatial_bubbles_live(chat_id) == [emory]
        assert {row["id"] for row in active_cast(chat_id, emory)} == set(ids.values())
        positions = wget_for_frame(chat_id, "scene", emory, {})["positions"]
        assert positions["Emory Vane"] == "mill_race"
        assert positions["Sal Weatherby"] == "mill_floor"
        # The later clock; her own lived state, not the base row.
        assert wget_for_frame(chat_id, "simulation_clock", emory)["elapsed_seconds"] == 900.0
        assert char_state(chat_id, ids["Sal Weatherby"], emory) == {
            "active_state": {"mood": "wary"}}

    def test_every_doorway_either_side_opened_survives(self, temp_db):
        chat_id, _ids, frames = _two_lives(temp_db)
        emory, sal = frames["Emory Vane"], frames["Sal Weatherby"]
        mine = wget_for_frame(chat_id, "scene", emory, {})
        mine["rooms"]["mill_race"]["adjacent"].append({"to": "weir", "barrier": "open"})
        mine["rooms"]["weir"] = {"name": "Weir", "adjacent": [{"to": "mill_race"}]}
        wset_for_frame(chat_id, "scene", mine, emory)
        theirs = wget_for_frame(chat_id, "scene", sal, {})
        theirs["rooms"]["market"]["adjacent"].append({"to": "wharf", "barrier": "open"})
        theirs["rooms"]["wharf"] = {"name": "Wharf", "adjacent": [{"to": "market"}]}
        theirs["positions"]["Sal Weatherby"] = "mill_floor"
        wset_for_frame(chat_id, "scene", theirs, sal)

        assert _reconcile(chat_id, emory, 5).get("sibling_merged")

        rooms = wget_for_frame(chat_id, "scene", emory, {})["rooms"]
        assert {"weir", "wharf"} <= set(rooms)
        assert "weir" in {e["to"] for e in rooms["mill_race"]["adjacent"]}
        assert "wharf" in {e["to"] for e in rooms["market"]["adjacent"]}

    def test_her_memory_is_hers_from_the_frame_she_joined(self, temp_db):
        chat_id, ids, frames = _two_lives(temp_db)
        emory, sal = frames["Emory Vane"], frames["Sal Weatherby"]
        who = ids["Sal Weatherby"]
        # Formed in her own bubble; and in the parent between the two splits
        # (Emory's opened at turn 1, hers at turn 2).
        assert not is_memory_visible(who, sal, emory, memory_turn_idx=4)
        assert not is_memory_visible(who, None, emory, memory_turn_idx=2)
        _move(chat_id, sal, "Sal Weatherby", "mill_floor")
        assert _reconcile(chat_id, emory, 5).get("sibling_merged")
        assert is_memory_visible(who, sal, emory, memory_turn_idx=4)
        assert is_memory_visible(who, None, emory, memory_turn_idx=2)

    def test_her_pending_fuse_still_comes_due_and_her_town_bodies_stay_held(self, temp_db):
        chat_id, _ids, frames = _two_lives(temp_db)
        emory, sal = frames["Emory Vane"], frames["Sal Weatherby"]
        temp_db.qi(
            "INSERT INTO scheduled_events(event_id,chat_id,due_at,kind,location_id,"
            "payload,seed,status) VALUES(?,?,?,?,?,?,?,?)",
            ("fuse", chat_id, 999.0, "consequence", "market",
             json.dumps({"frame_id": sal, "where": "market"}), "living_world:t3",
             "pending"))
        _move(chat_id, sal, "Sal Weatherby", "mill_floor")
        assert _reconcile(chat_id, emory, 5).get("sibling_merged")
        row = q("SELECT payload FROM scheduled_events WHERE chat_id=? AND event_id='fuse'",
                (chat_id,), one=True)
        assert json.loads(row["payload"])["frame_id"] == emory

    def test_a_frame_that_ended_plays_no_beat(self, temp_db):
        from agents.offscreen_beat import run_offscreen_beat
        chat_id, _ids, frames = _two_lives(temp_db)
        emory, sal = frames["Emory Vane"], frames["Sal Weatherby"]
        _move(chat_id, sal, "Sal Weatherby", "mill_floor")
        assert _reconcile(chat_id, emory, 5).get("sibling_merged")
        before = q("SELECT COUNT(*) AS n FROM turns WHERE chat_id=?", (chat_id,), one=True)["n"]
        assert run_offscreen_beat(chat_id, sal)["skipped"]
        after = q("SELECT COUNT(*) AS n FROM turns WHERE chat_id=?", (chat_id,), one=True)["n"]
        assert after == before


def test_leases_move_to_the_frame_that_holds_the_scene_now():
    registry = {"items": {"town": {"state": {"bodies": {
        "a": {"leased": "frame:2"}, "b": {"leased": "frame:1"}, "c": {}}}}}}
    assert rehold_leases(registry, "frame:2", "frame:1") == 1
    bodies = registry["items"]["town"]["state"]["bodies"]
    assert [bodies[k].get("leased") for k in "abc"] == ["frame:1", "frame:1", None]


def spatial_bubbles_live(chat_id):
    from agents.offscreen_beat import live_bubbles
    return live_bubbles(chat_id, None)
