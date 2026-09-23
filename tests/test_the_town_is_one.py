"""Sibling bubbles of one era share one town.

A causality bubble is the same era somewhere else, so the town on the other
side of the hill is the same town. It used to be COPIED into every bubble at
the split, on the argument that two copies of a deterministic simulation over
one clock track each other -- and they did not: each bubble ran its own clock
and seeded its own ticks, and a lease wrote only the holding bubble's copy.
Measured on the playerless Aldermill run (2026-09-23): the same mill hand
leased at the weir beside Emory in one bubble and walked around the forecourt
by the other bubble's copy, four of forty bodies in two places at once.

The era keys (`db.ERA_WORLD_KEYS`) resolve to their era's row; a lease names
the scene that holds a body, and no other live scene may move it.
"""
import time

from core.db import (ERA_WORLD_KEYS, era_of_frame, wget_for_frame,
                     wset_for_frame)
from core.frames import create_frame
from world.charter_model import normalize_charter
from world.charter_place import (held_elsewhere, lease_holder,
                                 lease_scene_bodies, resolve_scene_placements)


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Aldermill", "", time.time()))


def _frames(db):
    cid = _chat(db)
    emory = create_frame(cid, label="Emory", ordinal=0, kind="spatial",
                         split_turn_idx=1)
    sal = create_frame(cid, label="Sal", ordinal=0, kind="spatial",
                       split_turn_idx=1)
    past = create_frame(cid, label="Before the flood", ordinal=-1, kind="past")
    past_bubble = create_frame(cid, label="Upriver, then", ordinal=-1,
                               kind="spatial", parent_frame_id=past,
                               split_turn_idx=2)
    call = create_frame(cid, label="the call", ordinal=0, kind="couple",
                        parent_frame_id=emory, split_turn_idx=3)
    return cid, {"emory": emory, "sal": sal, "past": past,
                 "past_bubble": past_bubble, "call": call}


class TestOneRowPerEra:
    def test_a_bubble_belongs_to_the_era_it_split_from(self, temp_db):
        _, f = _frames(temp_db)
        assert era_of_frame(f["emory"]) is None
        assert era_of_frame(f["call"]) is None          # a couple of a bubble
        assert era_of_frame(f["past"]) == f["past"]
        assert era_of_frame(f["past_bubble"]) == f["past"]
        assert era_of_frame(987654) == 987654           # no such frame: its own

    def test_what_one_bubble_writes_of_the_town_the_other_reads(self, temp_db):
        cid, f = _frames(temp_db)
        town = {"items": {"mill": {"tag": "written in Emory's bubble"}}}
        wset_for_frame(cid, "charters", town, f["emory"])
        assert wget_for_frame(cid, "charters", f["sal"]) == town
        assert wget_for_frame(cid, "charters", None) == town
        assert wget_for_frame(cid, "charters", f["call"]) == town

    def test_another_era_keeps_its_own_town(self, temp_db):
        cid, f = _frames(temp_db)
        wset_for_frame(cid, "charters", {"era": "now"}, None)
        wset_for_frame(cid, "charters", {"era": "then"}, f["past"])
        assert wget_for_frame(cid, "charters", f["past_bubble"]) == {"era": "then"}
        assert wget_for_frame(cid, "charters", f["sal"]) == {"era": "now"}

    def test_what_is_the_partys_stays_the_partys(self, temp_db):
        cid, f = _frames(temp_db)
        wset_for_frame(cid, "scene", {"who": "Emory"}, f["emory"])
        wset_for_frame(cid, "known", {"Emory Vane": ["Sal"]}, f["emory"])
        assert wget_for_frame(cid, "scene", f["sal"]) is None
        assert wget_for_frame(cid, "known", f["sal"]) is None

    def test_every_era_key_is_frame_scoped(self):
        from core.db import FRAME_SCOPED_WORLD_KEYS
        assert ERA_WORLD_KEYS <= FRAME_SCOPED_WORLD_KEYS


def _registry(leased=None):
    body = {"name": "Robkinet Flourbrooks", "place": "mill_forecourt"}
    if leased is not None:
        body["leased"] = leased
    charter = normalize_charter({"key": "mill", "posts": {}, "watch": {},
                                 "bodies": {"hand": body}})
    return {"items": {"mill": {"state": charter}}}


def _scene(room="mill_race_weir"):
    return {"rooms": {"mill_race_weir": {"name": "Weir"},
                      "mill_forecourt": {"name": "Forecourt"}},
            "positions": {"Robkinet Flourbrooks": room},
            "entities": {"Robkinet Flourbrooks": {
                "name": "Robkinet Flourbrooks", "kind": "person",
                "charter_ref": {"charter": "mill", "body": "hand"}}}}


class TestOneBodyOneScene:
    def test_a_lease_names_its_holder_and_survives_the_normalizer(self):
        reg = _registry(leased="frame:7")
        assert reg["items"]["mill"]["state"]["bodies"]["hand"]["leased"] == "frame:7"

    def test_a_body_another_live_scene_holds_is_yielded_not_moved(self):
        reg = _registry(leased=lease_holder(1))
        out = lease_scene_bodies(reg, _scene(), ["mill_race_weir"],
                                 holder=lease_holder(2),
                                 live={lease_holder(None), lease_holder(1),
                                       lease_holder(2)})
        assert out["moves"] == []
        assert out["yielded"] == out["released"] == ["Robkinet Flourbrooks"]

    def test_a_merged_or_foreign_holder_is_no_claim(self):
        reg = _registry(leased="frame:99")
        out = lease_scene_bodies(reg, _scene(), ["mill_race_weir"],
                                 holder=lease_holder(2),
                                 live={lease_holder(None), lease_holder(2)})
        assert out["moves"] == [{"charter": "mill", "body": "hand",
                                 "name": "Robkinet Flourbrooks",
                                 "room": "mill_race_weir",
                                 "leased": lease_holder(2)}]
        assert not held_elsewhere({"leased": True}, lease_holder(2), None)

    def test_a_move_of_a_body_held_elsewhere_is_refused(self):
        reg = _registry(leased=lease_holder(1))
        diff = {"positions": {"Robkinet Flourbrooks": "mill_forecourt"}}
        scene = _scene()
        scene["positions"] = {}
        scene["entities"] = {}
        out = resolve_scene_placements(
            reg, diff, scene, holder=lease_holder(2),
            live={lease_holder(None), lease_holder(1), lease_holder(2)})
        assert out["moves"] == []
        assert out["refused"] == ["Robkinet Flourbrooks"]
        assert out["names"] == ["Robkinet Flourbrooks"]


def test_the_bubble_furthest_behind_acts_first(temp_db, monkeypatch):
    from agents import offscreen_beat
    import world.spatial_frames as frames_mod
    cid, f = _frames(temp_db)
    monkeypatch.setattr(frames_mod, "is_bubble_frame", lambda chat, frame: True)
    wset_for_frame(cid, "simulation_clock", {"elapsed_seconds": 189.0}, f["emory"])
    wset_for_frame(cid, "simulation_clock", {"elapsed_seconds": 116.0}, f["sal"])
    assert offscreen_beat.live_bubbles(cid, None) == [f["sal"], f["emory"]]
