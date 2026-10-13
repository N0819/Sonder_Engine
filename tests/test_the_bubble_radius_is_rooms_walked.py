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


class TestAStepIsAnEdgeTwoPeopleAreTogetherAcross:
    """Home 9 (chat 172): the garden was one edge from Hinami's second-storey
    room, through the window the layout tier made, and six rooms walked. A
    window between two rooms, or a wall, is not a step: seen through, or heard
    muffled, is not together. A way a body takes is, and so is a way an
    ordinary voice carries at full -- bars, an overlook -- a thing's own way
    out of its inside whatever it is made of, and a link that admits a body
    (review of 2026-10-13: each of those split a body off at every radius
    while the walk was routes alone)."""

    def _house(self):
        rooms = _line(7)
        rooms["r0"]["adjacent"].append(_edge("garden", "window"))
        rooms["r6"]["adjacent"].append(_edge("garden", "open_door"))
        rooms["garden"] = {"name": "garden", "adjacent": [_edge("r6", "open_door")]}
        rooms["r1"]["adjacent"].append(_edge("yard", "wall"))
        rooms["yard"] = {"name": "yard", "adjacent": []}
        return rooms

    def test_a_window_and_a_wall_are_no_step(self):
        from world.spatial import nearby_rooms, rooms_walked_within
        scene = {"rooms": self._house()}
        walked = rooms_walked_within(scene, {"r0"}, 3)
        assert not {"garden", "yard"} & set(walked)
        assert "garden" in rooms_walked_within(scene, {"r0"}, 7), "the way round, on foot"
        # the payload's walk is unchanged: relevance crosses every edge
        assert "garden" in nearby_rooms(scene, {"r0"}, hops=1)

    def test_a_body_seen_through_the_window_but_far_on_foot_gets_a_thread(self):
        scene = {"rooms": self._house(), "positions": {"Hinami": "r0", "Tamamo": "garden"}}
        assert _decide(scene)["characters"] == ["Tamamo"]

    def test_bars_are_a_step_a_voice_carries_at_full(self):
        rooms = {"guardroom": {"adjacent": [_edge("cell", "bars")]},
                 "cell": {"adjacent": [_edge("guardroom", "bars")]}}
        scene = {"rooms": rooms, "positions": {"Hinami": "guardroom", "Tamamo": "cell"}}
        assert _decide(scene, radius=1) is None, "a prisoner talks face to face"

    def test_an_overlook_is_a_step_a_voice_carries_down(self):
        rooms = {"gallery": {"adjacent": [_edge("court", vertical="down", way="overlook")]},
                 "court": {"adjacent": []}}
        scene = {"rooms": rooms, "positions": {"Hinami": "gallery", "Tamamo": "court"}}
        assert _decide(scene, radius=1) is None

    def test_a_things_own_way_out_is_a_step_whatever_it_is_made_of(self):
        """A shut glass jar on the study table: `spatial_transit` writes its
        hatch `window`, and the body in it is in the study all the same."""
        rooms = {"study": {"adjacent": []},
                 "jar_inside": {"parent_entity": "glass_jar",
                                "adjacent": [_edge("study", "window")]}}
        scene = {"rooms": rooms, "entities": {"glass_jar": {"kind": "object"}},
                 "positions": {"Hinami": "jar_inside", "Tamamo": "study"}}
        assert _decide(scene, radius=1) is None

    def test_a_link_that_admits_a_body_is_a_step(self):
        rooms = {"cavern": {"adjacent": [_edge("divine_realm", "window", admits=["tamamo"])]},
                 "divine_realm": {"adjacent": []}}
        scene = {"rooms": rooms, "positions": {"Hinami": "cavern", "Tamamo": "divine_realm"}}
        assert _decide(scene, radius=1) is None


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


# ------------------------------------------------- the review of 2026-10-13


def _reconcile_as(chat_id, frame_id, turn_idx, typed=""):
    """`detect_and_reconcile` as commit calls it, for a beat that was typed
    (`typed`) or one the engine scheduled (no input)."""
    from core.db import active_frame_id
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    from world import spatial_frames
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=None, chat_id=chat_id, idx=turn_idx, player_input=typed,
                      created=time.time(), frame_id=frame_id),
        cast=[], input=typed)
    token = active_frame_id.set(frame_id)
    try:
        return spatial_frames.detect_and_reconcile(ctx, 0)
    finally:
        active_frame_id.reset(token)


class TestWhoRejoinsHer:
    def test_a_beat_typed_into_her_frame_still_rejoins_her(self, temp_db):
        from world import spatial_frames
        cid, child = _bubble(temp_db)
        _move(cid, child, "Tamamo", "r1")
        assert spatial_frames.detect_merge(cid, child, played=True) == (None, child)
        assert _reconcile_as(cid, child, 5, typed="Tamamo goes back down.")["merged"]

    def test_her_scheduled_beat_leaves_it_to_the_parent(self, temp_db):
        from core.frames import get_frame
        cid, child = _bubble(temp_db)
        _move(cid, child, "Tamamo", "r1")
        assert not (_reconcile_as(cid, child, 5) or {}).get("merged")
        assert get_frame(child)["merged_turn_idx"] is None

    def test_the_parent_asks_every_child_not_only_its_first(self, temp_db):
        from world import spatial_frames
        cid = _chat(temp_db)
        _persona(temp_db, cid, "Hinami")
        _cast(temp_db, cid, "Tamamo")
        _cast(temp_db, cid, "Ren")
        temp_db.wset(cid, "scene", {"rooms": _line(14), "entities": {}, "comms": {},
                                    "positions": {"Hinami": "r7", "Tamamo": "r0", "Ren": "r13"}})
        first = spatial_frames.perform_split(cid, None, 0, bubble=True, away_names=["Tamamo"])
        second = spatial_frames.perform_split(cid, None, 1, bubble=True, away_names=["Ren"])
        _move(cid, second, "Ren", "r8")
        assert spatial_frames.detect_merge(cid, None) == (None, second)
        assert first != second


class TestACallHoldsHerApart:
    """A bubble a live call holds stays apart until the call ends:
    `close_couple` partitions back by the map recorded at open, and a merge
    landing mid-call left her active in the parent with no position."""

    def _called(self, db):
        from tests.test_causality_bubbles_wired import _handset, _reconcile, _story
        chat_id, _ = _story(db)
        bubble = _reconcile(chat_id, None, 3)[0]["child_frame_id"]
        _handset(chat_id, [None, bubble])
        couple = _reconcile(chat_id, None, 4)[0]["couple_frame_id"]
        return chat_id, bubble, couple

    def test_neither_the_parents_commit_nor_its_next_beat_merges_her_mid_call(self, temp_db):
        from world import spatial_frames
        chat_id, bubble, _couple = self._called(temp_db)
        _move(chat_id, bubble, "Hinami", "lane")          # back within reach
        assert spatial_frames.detect_merge(chat_id, None) is None
        assert spatial_frames.bubbles_the_beat_reaches(chat_id, None, {"bridge"}) == []

    def test_a_bubble_already_back_within_reach_is_met_not_called(self, temp_db):
        from tests.test_causality_bubbles_wired import _handset, _reconcile, _story
        from world import spatial_frames
        chat_id, _ = _story(temp_db)
        bubble = _reconcile(chat_id, None, 3)[0]["child_frame_id"]
        _move(chat_id, bubble, "Hinami", "lane")
        _handset(chat_id, [None, bubble])
        assert spatial_frames.detect_couple(chat_id, bubble) is None
        assert not (_reconcile_as(chat_id, bubble, 5) or {}).get("coupled")
        assert spatial_frames.detect_merge(chat_id, None) == (None, bubble)


class TestTheBeatBeforeItsInterpret:
    def test_her_return_is_merged_before_the_director_reads_the_line(self, temp_db):
        """No interpret yet: the rooms are where the party stands."""
        from agents import runtime
        from core.frames import get_frame
        from core.pipeline_context import ChatData, PipelineContext, TurnData
        cid, child = _bubble(temp_db)
        _move(cid, child, "Tamamo", "r2")
        chat = dict(temp_db.q("SELECT * FROM chats WHERE id=?", (cid,), one=True))
        ctx = PipelineContext(chat=ChatData.from_row(chat),
                              turn=TurnData(id=None, chat_id=cid, idx=6, player_input="I wait.",
                                            created=time.time(), frame_id=None),
                              cast=[], input="I wait.")
        cast = runtime._merge_bubbles_the_beat_reaches(
            ctx, cid, {"frame_id": None, "idx": 6}, filed_under="director_interpret")
        assert cast and get_frame(child)["merged_turn_idx"] == 6

    def test_the_run_asks_before_the_interpret_and_again_after_it(self):
        import inspect
        from agents import runtime
        source = inspect.getsource(runtime._run_pipeline)
        before = source.index('filed_under="director_interpret"')
        interpret = source.index('yield from _step_stream(bus, turn_id, "director_interpret"')
        after = source.index("cast_rows = _merge_bubbles_the_beat_reaches(ctx, chat_id, turn_row) or cast_rows")
        assert before < interpret < after


class TestTwoThreadsMeetAsTheSplitSees:
    def test_a_body_in_another_bodys_inside_meets_the_one_in_its_room(self):
        from tests.test_a_body_inside_another_is_in_reach import _stomach
        from world.spatial_bubbles import sibling_meet_decision
        scene_b = _stomach()                               # Sal deep inside
        scene_b["positions"] = {"Sal": "mirelle_stomach", "Mirelle": "treatment_room"}
        scene_a = dict(_stomach(), positions={"Emory": "hall", "Mirelle": "treatment_room"})
        assert sibling_meet_decision(scene_a, ["Emory"], scene_b, ["Sal"], radius=1)

    def test_a_voice_over_a_wire_still_is_not_standing_together(self):
        from world.spatial_bubbles import sibling_meet_decision
        rooms = {"a": {"adjacent": []}, "b": {"adjacent": []}}
        intercom = {"intercom": {"rooms": ["a", "b"], "live": True}}
        scene_a = {"rooms": rooms, "comms": intercom, "positions": {"Emory": "a"}}
        scene_b = {"rooms": rooms, "comms": intercom, "positions": {"Sal": "b"}}
        from world.spatial_bubbles import bubble_reach
        assert "b" in bubble_reach(scene_a, {"a"}, radius=3), "the channel is live"
        assert not sibling_meet_decision(scene_a, ["Emory"], scene_b, ["Sal"], radius=3)


class TestAnEndedFrameTakesNoCommit:
    def test_a_beat_whose_frame_rejoined_while_it_ran_is_refused(self, temp_db):
        import types
        from persist import commit
        cid, child = _bubble(temp_db)
        ctx = types.SimpleNamespace(turn=types.SimpleNamespace(frame_id=child))
        commit._refuse_an_ended_frame(ctx)                # live: nothing to say
        temp_db.qi("UPDATE frames SET merged_turn_idx=? WHERE id=?", (4, child))
        with pytest.raises(RuntimeError, match="rejoined"):
            commit._refuse_an_ended_frame(ctx)
        commit._refuse_an_ended_frame(types.SimpleNamespace(
            turn=types.SimpleNamespace(frame_id=None)))   # the present never ends

    def test_it_is_asked_first_inside_the_commits_transaction(self):
        import inspect
        from persist import commit
        source = inspect.getsource(commit._commit_all_locked)
        opened = source.index("with transaction(), registry_session():")
        asked = source.index("_refuse_an_ended_frame(ctx)")
        first_domain = source.index("_commit_domain(")
        assert opened < asked < first_domain


class TestNoNumberBreaksTheDial:
    def test_an_infinity_an_archive_carried_reads_as_the_default(self, temp_db):
        from story.scene import dialogue_config
        cid = _chat(temp_db)
        temp_db.wset(cid, "dialogue_config", {"bubble_radius": float("inf"),
                                              "max_bubbles": float("inf")})
        config = dialogue_config(cid)
        assert (config["bubble_radius"], config["max_bubbles"]) == (3, 3)

    def test_the_panel_answers_an_infinity_with_a_400(self, temp_db):
        from fastapi import HTTPException
        from web import app
        with pytest.raises(HTTPException) as refused:
            app.dlg_put(_chat(temp_db), {"bubble_radius": float("inf")})
        assert refused.value.status_code == 400
