"""A causality bubble opens at a RADIUS OF ROOMS WALKED, a whole stair one.

The owner's ruling of 2026-10-13: "same building should probably be the same
bubble", then "maybe it should be a radius of rooms?" -- three rooms walked by
default, a whole stair counting as ONE room (the layout tier's halls, one per
storey, joined by flights), held in ONE named setting (`dialogue_config
["bubble_radius"]`, the Absent threads card) replacing the one doorway the
split, the rejoin, the merge before a beat, the sibling meeting and the
town's claims each asked.

Measured on Home 10 (chat 173, docs/experiments/OBSERVE_2026_10_13_home10.md
item 1): the opening split Tamamo off four rooms from Hinami -- three with the
ladder as one -- while her voice reached Hinami at full strength; turn 4624
ended her in the court, two rooms off, and the rejoin, asking one doorway,
kept her away.

The new API is imported inside the tests that use it, so this file collects
on code that predates it and only the behaviour fails there.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _edge(to, barrier="open", **more):
    return dict({"to": to, "barrier": barrier}, **more)


def _shrine(**positions):
    """Home 10's shrine as chat 173's scene holds it, cut to what distance
    reads: the paper door, the hall, the court, the ladder the layout tier
    made as two halls (one per storey) joined by its flight, and the roost."""
    stair0, stair1 = "shrine_hall__tamamo_roost_stair_0", "shrine_hall__tamamo_roost_stair_1"
    rooms = {
        "hinami_room": {"name": "Hinami's Room", "level": 0,
                        "adjacent": [_edge("shrine_hall", "closed_door")]},
        "shrine_hall": {"name": "The Hall", "level": 0, "adjacent": [
            _edge("shrine_courtyard", "closed_door"), _edge("hinami_room", "closed_door"),
            _edge(stair0)]},
        "shrine_courtyard": {"name": "The Shrine Court", "level": 0, "adjacent": [
            _edge("shrine_hall", "closed_door"), _edge("storehouse", "closed_door"),
            _edge("mountain_path")]},
        "storehouse": {"name": "The Storehouse", "level": 0,
                       "adjacent": [_edge("shrine_courtyard", "closed_door")]},
        "mountain_path": {"name": "The Mountain Path", "level": 0,
                          "adjacent": [_edge("shrine_courtyard")]},
        stair0: {"name": "ladder", "level": 0, "made_by_layout": True, "adjacent": [
            _edge("shrine_hall"), _edge(stair1, vertical="up", way="ladder")]},
        stair1: {"name": "ladder", "level": 1, "made_by_layout": True, "adjacent": [
            _edge(stair0, vertical="down", way="ladder"), _edge("tamamo_roost")]},
        "tamamo_roost": {"name": "The Roost", "level": 1, "adjacent": [_edge(stair1)]},
    }
    return {"rooms": rooms, "comms": {}, "entities": {},
            "positions": dict({"Hinami": "hinami_room"}, **positions)}


def _line(n=8):
    ids = [f"r{i}" for i in range(n)]
    rooms = {rid: {"name": rid, "adjacent": []} for rid in ids}
    for a, b in zip(ids, ids[1:]):
        rooms[a]["adjacent"].append(_edge(b))
        rooms[b]["adjacent"].append(_edge(a))
    return rooms


def _decide(scene, radius=3):
    from world.spatial_bubbles import bubble_split_decision
    return bubble_split_decision(scene, party_names=["Hinami"], cast_names=["Tamamo"],
                                 radius=radius)


# ------------------------------------------------------------------ the walk


class TestTheRadius:
    def test_three_rooms_walked_is_inside_the_beat(self):
        scene = {"rooms": _line(), "positions": {"Hinami": "r0", "Tamamo": "r3"}}
        assert _decide(scene) is None
        assert _decide(scene, radius=1)["characters"] == ["Tamamo"], "the old doorway"

    def test_four_rooms_walked_is_a_thread_of_its_own(self):
        scene = {"rooms": _line(), "positions": {"Hinami": "r0", "Tamamo": "r4"}}
        assert _decide(scene)["characters"] == ["Tamamo"]

    def test_a_shut_door_is_one_room_and_not_a_wall(self):
        from world.spatial import rooms_walked_within
        scene = _shrine()
        assert "shrine_courtyard" in rooms_walked_within(scene, {"hinami_room"}, 2)

    def test_the_radius_has_no_default(self):
        from world.spatial_bubbles import bubble_reach, bubble_split_decision, in_range_rooms
        scene = {"rooms": _line(), "positions": {"Hinami": "r0", "Tamamo": "r4"}}
        for call in (lambda: in_range_rooms(scene, ["Hinami"]),
                     lambda: bubble_reach(scene, {"r0"}),
                     lambda: bubble_split_decision(scene, party_names=["Hinami"],
                                                   cast_names=["Tamamo"])):
            with pytest.raises(TypeError):
                call()


class TestAWholeStairIsOneRoom:
    def test_home_10s_roost_is_three_rooms_from_hinami(self):
        from world.spatial import rooms_walked_within
        assert _decide(_shrine(Tamamo="tamamo_roost")) is None
        assert "tamamo_roost" not in rooms_walked_within(_shrine(), {"hinami_room"}, 2)

    def test_without_a_made_stair_the_same_rooms_are_four(self):
        scene = _shrine(Tamamo="tamamo_roost")
        for room in scene["rooms"].values():
            room.pop("made_by_layout", None)
        assert _decide(scene)["characters"] == ["Tamamo"]

    def test_a_stair_is_one_room_however_many_storeys_it_climbs(self):
        from world.spatial import rooms_walked_within
        flight = {"vertical": "up", "way": "stair"}
        rooms = {"ground": {"adjacent": [_edge("s0")]},
                 "s0": {"made_by_layout": True, "adjacent": [_edge("ground"), _edge("s1", **flight)]},
                 "s1": {"made_by_layout": True, "adjacent": [_edge("s2", **flight)]},
                 "s2": {"made_by_layout": True, "adjacent": [_edge("top")]},
                 "top": {"adjacent": []}}
        scene = {"rooms": rooms}
        assert set(rooms_walked_within(scene, {"ground"}, 1)) == {"ground", "s0", "s1", "s2"}
        assert "top" in rooms_walked_within(scene, {"ground"}, 2)

    def test_two_made_halls_joined_by_no_flight_are_two_rooms(self):
        from world.spatial import rooms_walked_within
        rooms = {"a": {"adjacent": [_edge("h0")]},
                 "h0": {"made_by_layout": True, "adjacent": [_edge("h1")]},
                 "h1": {"made_by_layout": True, "adjacent": [_edge("b")]},
                 "b": {"adjacent": []}}
        assert "b" not in rooms_walked_within({"rooms": rooms}, {"a"}, 2)
        assert "b" in rooms_walked_within({"rooms": rooms}, {"a"}, 3)

    def test_both_marks_reach_the_scene_through_the_tiers_own_write(self, temp_db):
        """The rule reads two facts the layout tier writes -- a made hall's
        mark and its flight's `vertical` -- and both have to survive the plan's
        write, the fringe and the stub laid on its plan, or the stair quietly
        counts as two rooms again."""
        from tests.test_a_stair_is_a_room import _chat, _expected, _plant, _solve
        from world.spatial import rooms_walked_within
        from world.structure import (LAYOUT_MADE_KEY, _planned_specs, apply_planned_layout,
                                     materialize_planned_fringe, write_planned_layout)
        cid = _chat(temp_db)
        _plant(cid)
        assert write_planned_layout(cid, _solve(), expected=_expected(cid))
        street = {"name": "the Street", "adjacent": [_edge("hall", "open_door", dir="n")]}
        scene, _ = materialize_planned_fringe(cid, {
            "rooms": {"street": street}, "entities": {},
            "positions": {"Walker": "street", "Mara": "hall", "Oda": "hall__loft_stair_1"}})
        apply_planned_layout(scene, _planned_specs(cid))
        low, high = scene["rooms"]["hall__loft_stair_0"], scene["rooms"]["hall__loft_stair_1"]
        assert low.get(LAYOUT_MADE_KEY) and high.get(LAYOUT_MADE_KEY)
        assert {e["to"]: e.get("vertical") for e in low["adjacent"]}.get(
            "hall__loft_stair_1") == "up"
        # the hall, its stair (one room), the loft: two rooms walked
        assert "loft" in rooms_walked_within(scene, {"hall"}, 2)
        assert "loft" not in rooms_walked_within(scene, {"hall"}, 1)


class TestOnlyAWayABodyTakesIsAStep:
    """Home 9 (chat 172): the garden was one edge from Hinami's second-storey
    room, through the window the layout tier made, and six rooms walked."""

    def _house(self):
        rooms = _line(7)
        rooms["r0"]["adjacent"].append(_edge("garden", "window"))
        rooms["r6"]["adjacent"].append(_edge("garden", "open_door"))
        rooms["garden"] = {"name": "garden", "adjacent": [_edge("r6", "open_door")]}
        rooms["r1"]["adjacent"].append(_edge("yard", "wall"))
        rooms["yard"] = {"name": "yard", "adjacent": []}
        # an overlook is a vertical edge: a gallery over a court, seen down into
        rooms["r2"]["adjacent"].append(_edge("pit", "open", vertical="down", way="overlook"))
        rooms["pit"] = {"name": "pit", "adjacent": []}
        return rooms

    def test_a_window_a_wall_and_an_overlook_are_no_way_through(self):
        from world.spatial import nearby_rooms, rooms_walked_within
        scene = {"rooms": self._house()}
        walked = rooms_walked_within(scene, {"r0"}, 3)
        assert not {"garden", "yard", "pit"} & set(walked)
        assert "garden" in rooms_walked_within(scene, {"r0"}, 7), "the way round, on foot"
        # the payload's walk is unchanged: relevance crosses every edge
        assert "garden" in nearby_rooms(scene, {"r0"}, hops=1)

    def test_a_body_seen_through_the_window_but_far_on_foot_gets_a_thread(self):
        scene = {"rooms": self._house(), "positions": {"Hinami": "r0", "Tamamo": "garden"}}
        assert _decide(scene)["characters"] == ["Tamamo"]


class TestThePayloadDidNotMove:
    def test_the_payload_window_is_still_one_plain_doorway(self):
        from world.spatial import attended_rooms
        assert set(attended_rooms(_shrine(), {"hinami_room"})) == {"hinami_room", "shrine_hall"}

    def test_the_bubbles_range_is_the_story_radius(self):
        from world.spatial_bubbles import bubble_reach
        assert bubble_reach(_shrine(), {"hinami_room"}, radius=3) == set(_shrine()["rooms"])

    def test_every_body_the_range_keeps_is_in_the_payload(self):
        from agents.common import _contextual_rooms
        from story.character_schema import default_character_data
        scene = {"rooms": _line(), "positions": {"Hinami": "r0", "Tamamo": "r3"}}
        cast = [{"sheet": json.dumps(default_character_data("Tamamo"))}]
        assert "r3" in _contextual_rooms(scene, cast, "r0")


# ------------------------------------------------------------- the story's dial


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Home", "", time.time()))


def _cast(db, chat_id, name):
    from story.character_schema import default_character_data
    char_id = db.qi("INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
                    (name, json.dumps(default_character_data(name)), "{}", time.time()))
    db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,'active','{}')",
          (chat_id, char_id))
    return char_id


def _persona(db, chat_id, name):
    from story.character_schema import default_persona_data
    pid = db.qi("INSERT INTO personas(name,sheet) VALUES(?,?)",
                (name, json.dumps(default_persona_data(name))))
    db.qi("UPDATE chats SET persona_id=? WHERE id=?", (pid, chat_id))


def _story(db, *, tamamo_at, rooms=None):
    cid = _chat(db)
    _persona(db, cid, "Hinami")
    _cast(db, cid, "Tamamo")
    db.wset(cid, "scene", {"rooms": rooms or _line(), "entities": {}, "comms": {},
                           "positions": {"Hinami": "r0", "Tamamo": tamamo_at}})
    return cid


def _bubble(db, *, tamamo_at="r7"):
    from world import spatial_frames
    cid = _story(db, tamamo_at=tamamo_at)
    child = spatial_frames.perform_split(cid, None, 0, bubble=True, away_names=["Tamamo"])
    return cid, child


def _move(cid, frame_id, name, room):
    from core.db import wget_for_frame, wset_for_frame
    scene = wget_for_frame(cid, "scene", frame_id, {})
    scene["positions"][name] = room
    wset_for_frame(cid, "scene", scene, frame_id)


class TestTheStorysDial:
    @pytest.mark.parametrize("stored,expected", [(None, 3), (1, 1), (0, 1), (99, 12), ("x", 3)])
    def test_it_defaults_to_three_and_is_clamped(self, temp_db, stored, expected):
        from story.scene import dialogue_config
        cid = _chat(temp_db)
        if stored is not None:
            temp_db.wset(cid, "dialogue_config", {"bubble_radius": stored})
        assert dialogue_config(cid)["bubble_radius"] == expected

    def test_a_panel_save_keeps_both_thread_dials(self, temp_db):
        """`max_bubbles` was sent by the panel since 2026-09-20 and never
        stored: a save of 1 read back 3."""
        from fastapi import HTTPException
        from story.scene import dialogue_config
        from web import app
        cid = _chat(temp_db)
        app.dlg_put(cid, {"autonomy": 50, "max_bubbles": 1, "bubble_radius": 5})
        assert (dialogue_config(cid)["max_bubbles"], dialogue_config(cid)["bubble_radius"]) == (1, 5)
        app.dlg_put(cid, {"autonomy": 50})
        assert (dialogue_config(cid)["max_bubbles"], dialogue_config(cid)["bubble_radius"]) == (1, 5)
        app.dlg_put(cid, {"bubble_radius": 0})
        assert dialogue_config(cid)["bubble_radius"] == 1, "clamped to one room, never zero"
        with pytest.raises(HTTPException):
            app.dlg_put(cid, {"bubble_radius": "far"})

    def test_every_key_the_panel_sends_is_kept(self, temp_db):
        from web import app
        source = (ROOT / "static" / "js" / "settings.js").read_text(encoding="utf-8")
        body = re.search(r"/dialogue_config`, \{(.*?)\}\);", source, re.S).group(1)
        keys = set(re.findall(r"(\w+):", body))
        assert {"max_bubbles", "bubble_radius"} <= keys
        saved = app.dlg_put(_chat(temp_db), {"autonomy": 50, **{k: 2 for k in keys if "bubble" in k}})
        assert keys <= set(saved), keys - set(saved)

    def test_the_room_reads_it(self, temp_db):
        from story.room_tools import run_tool
        cid = _chat(temp_db)
        temp_db.wset(cid, "dialogue_config", {"bubble_radius": 4})
        assert run_tool(cid, "inspect_config", {})["offscreen"]["bubble_radius"] == 4


class TestEverySiteReadsTheStorysRadius:
    """Each site asked of a story whose radius is FIVE, with bodies four or
    five rooms walked apart: under the default they are apart, under the
    story's setting together. A site that read the default -- or forgot the
    setting -- fails here."""

    def test_the_split(self, temp_db):
        from world.spatial_bubbles import detect_bubble
        cid = _story(temp_db, tamamo_at="r5")
        assert detect_bubble(cid, None, 1)["characters"] == ["Tamamo"]
        temp_db.wset(cid, "dialogue_config", {"bubble_radius": 5})
        assert detect_bubble(cid, None, 1) is None

    def test_the_rejoin_at_the_parents_commit(self, temp_db):
        from world import spatial_frames
        cid, child = _bubble(temp_db)
        _move(cid, child, "Tamamo", "r5")
        assert spatial_frames.detect_merge(cid, None) is None
        temp_db.wset(cid, "dialogue_config", {"bubble_radius": 5})
        assert spatial_frames.detect_merge(cid, None) == (None, child)

    def test_the_merge_before_a_beat(self, temp_db):
        from world import spatial_frames
        cid, child = _bubble(temp_db)
        _move(cid, child, "Tamamo", "r6")
        assert spatial_frames.bubbles_the_beat_reaches(cid, None, {"r1"}) == []
        temp_db.wset(cid, "dialogue_config", {"bubble_radius": 5})
        assert spatial_frames.bubbles_the_beat_reaches(cid, None, {"r1"}) == [child]

    def test_the_sibling_meeting(self, temp_db):
        from tests.test_sibling_bubbles_meet import _two_lives
        from world.spatial_bubbles import detect_sibling_meeting
        chat_id, _ids, frames = _two_lives(temp_db)        # four rooms walked apart
        emory = frames["Emory Vane"]
        assert detect_sibling_meeting(chat_id, emory) is None
        temp_db.wset(chat_id, "dialogue_config", {"bubble_radius": 5})
        assert detect_sibling_meeting(chat_id, emory) == (emory, frames["Sal Weatherby"])

    def test_the_towns_claims(self, temp_db, monkeypatch):
        from core.db import wset_for_frame
        from persist.commit import town_for_sweep
        from tests.test_town_events_fire_where_they_happen import ROOMS, _bubbles
        from world import spatial_bubbles
        cid, emory, sal = _bubbles(temp_db)
        people = {emory: ["Emory Vane"], sal: ["Sal Weatherby"], None: []}
        monkeypatch.setattr(spatial_bubbles, "frame_body_names",
                            lambda chat_id, frame_id: people[frame_id])
        emory_scene = {"rooms": ROOMS, "positions": {"Emory Vane": "mill_race"}}
        wset_for_frame(cid, "scene", {"rooms": ROOMS, "positions": {
            "Sal Weatherby": "market"}}, sal)
        assert town_for_sweep(cid, emory, emory_scene)["claims"]["market"] == sal
        temp_db.wset(cid, "dialogue_config", {"bubble_radius": 5})
        assert town_for_sweep(cid, emory, emory_scene)["claims"]["market"] == emory


class TestTheRejoin:
    def test_turn_4624s_court_brings_her_back(self, temp_db):
        from world import spatial_frames
        cid = _chat(temp_db)
        _persona(temp_db, cid, "Hinami")
        _cast(temp_db, cid, "Tamamo")
        temp_db.wset(cid, "scene", _shrine(Tamamo="tamamo_roost"))
        child = spatial_frames.perform_split(cid, None, 0, bubble=True, away_names=["Tamamo"])
        _move(cid, child, "Tamamo", "shrine_courtyard")
        assert spatial_frames.detect_merge(cid, None) == (None, child)

    def test_a_bubble_never_merges_itself_from_its_own_commit(self, temp_db):
        """Her own commit sees the rejoin and leaves it to the parent: every
        domain after the spatial one writes to the frame being committed, and
        the player's beat beside hers would overwrite a merge that landed
        while it ran."""
        from world import spatial_frames
        cid, child = _bubble(temp_db)
        _move(cid, child, "Tamamo", "r1")
        assert spatial_frames.detect_merge(cid, child) is None
        assert spatial_frames.detect_merge(cid, None) == (None, child)
        assert spatial_frames.bubbles_the_beat_reaches(cid, None, {"r0"}) == [child]

    def test_the_beat_asks_from_every_member_of_the_party(self, temp_db):
        """The merge before a beat is where a body that walked back comes
        home, so it asks what the commit's rejoin asks: every party member's
        room, not only the rooms the beat walks the primary player through."""
        from world import spatial_frames
        cid, child = _bubble(temp_db)
        _move(cid, child, "Tamamo", "r6")
        assert spatial_frames.bubbles_the_beat_reaches(cid, None, {"r0"}) == []
        assert spatial_frames.bubbles_the_beat_reaches(
            cid, None, {"r0"}, party_names=["Hinami"]) == []
        from core.db import wget_for_frame, wset_for_frame
        scene = wget_for_frame(cid, "scene", None, {})
        scene["positions"]["Ren"] = "r4"
        wset_for_frame(cid, "scene", scene, None)
        assert spatial_frames.bubbles_the_beat_reaches(
            cid, None, {"r0"}, party_names=["Hinami", "Ren"]) == [child]
