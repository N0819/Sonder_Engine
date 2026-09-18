"""The causality bubble, end to end: opened, coupled, uncoupled, rejoined.

`test_causality_bubble_detectors.py` proves the three decisions are right
against constructed scenes, and `test_couple_invariants.py` proves a couple
moves a voice and nothing else. Neither of them fires anything. This file is
the wiring: `detect_and_reconcile` is the one commit-time entry point, and
every structural change a beat can produce has to come out of it in the right
order, on real rows.

THE LIFECYCLE THIS FILE WALKS, once, in order:

    a character walks into a zone the player is not in
        -> a bubble frame opens, with no persona anywhere near it
    somebody keys a handset
        -> a couple frame opens and the beat is played there
    the handset goes off
        -> the couple closes and the bubble is a bubble again
    the character walks back into the player's zone
        -> the bubble merges away and the separation is over

There is no uncouple DRIVER in that list, and its absence is the design: the
bubble's sixth refusal is "a live channel already reaches them", so a call
ending lifts the refusal and the bubble re-opens by itself on the next commit.
Nothing latches, which is why nothing can be left latched.
"""

from __future__ import annotations

import json
import time

import pytest

from core.db import active_frame_id, wget_for_frame, wset, wset_for_frame
from core.frames import get_frame
from core.pipeline_context import ChatData, PipelineContext, TurnData
from mind.memory import prepare_memory, visible_memory_rows
from story.character_schema import default_character_data
from story.scene import active_cast
from web import app
from world import spatial as sp
from world import spatial_bubbles, spatial_frames


# ------------------------------------------------------------- construction

def _make_chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Test", "", time.time()))


def _make_char(db, chat_id, name):
    char_id = db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        (name, json.dumps(default_character_data(name)), "{}", time.time()))
    db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
          "VALUES(?,?,'active','{}')", (chat_id, char_id))
    return char_id


def _ctx(chat_id, frame_id, turn_idx):
    turn_id = None
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=turn_idx,
                      player_input="test", created=time.time(),
                      frame_id=frame_id),
        cast=[], input="test",
    )
    return ctx


def _reconcile(chat_id, frame_id, turn_idx):
    """`detect_and_reconcile` the way commit calls it: inside the frame."""
    ctx = _ctx(chat_id, frame_id, turn_idx)
    token = active_frame_id.set(frame_id)
    try:
        return spatial_frames.detect_and_reconcile(ctx, 0), ctx
    finally:
        active_frame_id.reset(token)


#: FOUR ROOMS IN A LINE, AND NOT ONE ZONE. The trigger is RANGE (owner ruling
#: 2026-09-17), so a fixture that declared a locale could pass on the label
#: rather than on the rule. The rooms are joined by real edges for the same
#: reason: a room with no `adjacent` at all is an island, and an island is
#: out of range of everything, which would make every assertion here true by
#: accident. `attic` is the one island, deliberately, and it is where the
#: shared-room cases live.
BASE_SCENE = {
    "location": "The Kestrel",
    "rooms": {
        "bridge": {"name": "Bridge",
                   "adjacent": [{"to": "lane", "barrier": "closed_door"}]},
        "lane": {"name": "The lane",
                 "adjacent": [{"to": "bridge", "barrier": "closed_door"},
                              {"to": "market", "barrier": "open"}]},
        "market": {"name": "Market",
                   "adjacent": [{"to": "lane", "barrier": "open"}]},
        "attic": {"name": "Attic", "adjacent": []},
    },
    "positions": {"The Stranger": "bridge", "Hinami": "market"},
    "entities": {}, "attire": {}, "overlays": {}, "comms": {}, "contacts": [],
}


def _story(db, *, comms=None):
    """The player on the ship, one cast character in the city. No persona
    anywhere -- that absence is the whole point of a bubble."""
    chat_id = _make_chat(db)
    hinami = _make_char(db, chat_id, "Hinami")
    scene = json.loads(json.dumps(BASE_SCENE))
    if comms:
        sp.apply_comms_ops(scene, comms)
    wset(chat_id, "scene", scene)
    return chat_id, hinami


def _handset(chat_id, frame_ids, carriers=("The Stranger", "Hinami"), op=None):
    for frame_id in frame_ids:
        scene = wget_for_frame(chat_id, "scene", frame_id, {}) or {}
        sp.apply_comms_ops(scene, [dict(
            {"id": "handset", "name": "the handset", "carriers": list(carriers)},
            **({"op": op} if op else {}))])
        wset_for_frame(chat_id, "scene", scene, frame_id)


# ================================================================ 1. it opens


class TestTheBubbleOpens:
    def test_a_character_out_of_the_beats_reach_gets_a_frame(self, temp_db):
        chat_id, hinami = _story(temp_db)

        result, ctx = _reconcile(chat_id, None, turn_idx=3)

        assert result["bubble"] is True
        assert result["characters"] == ["Hinami"]
        assert "market" in result["rooms"]
        bubble = get_frame(result["child_frame_id"])
        assert bubble["kind"] == "spatial"
        assert bubble["label"].startswith("Bubble")
        assert bubble["split_turn_idx"] == 3
        assert bubble["merged_turn_idx"] is None

    def test_it_fires_exactly_where_a_party_split_refuses(self, temp_db):
        chat_id, _ = _story(temp_db)
        # No personas attached at all, which is `detect_split`'s second
        # refusal and the entire gap the bubble exists to fill.
        assert spatial_frames.detect_split(chat_id, None, 3) is None
        assert _reconcile(chat_id, None, 3)[0].get("bubble") is True

    def test_the_cast_is_partitioned_and_the_player_keeps_their_own_scene(
            self, temp_db):
        chat_id, hinami = _story(temp_db)
        bubble = _reconcile(chat_id, None, 3)[0]["child_frame_id"]

        assert {r["id"] for r in active_cast(chat_id, None)} == set()
        assert {r["id"] for r in active_cast(chat_id, bubble)} == {hinami}

        parent_scene = wget_for_frame(chat_id, "scene", None, {})
        bubble_scene = wget_for_frame(chat_id, "scene", bubble, {})
        assert "Hinami" not in parent_scene["positions"]
        assert "The Stranger" not in bubble_scene["positions"]
        assert spatial_frames.is_bubble_frame(chat_id, bubble) is True

    def test_it_does_not_fire_while_a_voice_still_reaches_them(self, temp_db):
        chat_id, _ = _story(temp_db, comms=[{
            "id": "handset", "carriers": ["The Stranger", "Hinami"]}])
        assert _reconcile(chat_id, None, 3)[0] == {"active": False}

    def test_it_fires_on_the_beat_the_voice_stops(self, temp_db):
        """The uncouple driver, and there is no other one. Nothing latches:
        the refusal lifts because the world changed."""
        chat_id, _ = _story(temp_db, comms=[{
            "id": "handset", "carriers": ["The Stranger", "Hinami"]}])
        assert _reconcile(chat_id, None, 3)[0] == {"active": False}

        _handset(chat_id, [None], op="close")
        assert _reconcile(chat_id, None, 4)[0].get("bubble") is True


# =============================================================== 2. it couples


class TestTheCoupleOpensAndCloses:
    def _bubbled(self, db):
        chat_id, hinami = _story(db)
        bubble = _reconcile(chat_id, None, 3)[0]["child_frame_id"]
        return chat_id, hinami, bubble

    def test_a_handset_on_both_sides_opens_a_couple(self, temp_db):
        chat_id, _, bubble = self._bubbled(temp_db)
        _handset(chat_id, [None, bubble])

        result, _ = _reconcile(chat_id, None, turn_idx=4)

        assert result["coupled"] is True
        couple = get_frame(result["couple_frame_id"])
        assert couple["kind"] == "couple"
        assert couple["parent_frame_id"] is None
        assert get_frame(bubble)["merged_turn_idx"] is None, (
            "a channel is not a reunion")

    def test_both_parties_stand_in_the_couples_scene_and_still_cannot_shout(
            self, temp_db):
        chat_id, _, bubble = self._bubbled(temp_db)
        _handset(chat_id, [None, bubble])
        couple = _reconcile(chat_id, None, 4)[0]["couple_frame_id"]

        fused = wget_for_frame(chat_id, "scene", couple, {})
        here = sp.room_of(fused, "The Stranger")
        there = sp.room_of(fused, "Hinami")
        assert here and there and here != there

        rel = sp.spatial_rel(fused, here, there)
        assert sp.sight_level(rel) == "none"
        assert sp.scent_level(rel) == "none"
        assert sp.hear_level(rel, "shout") == "none"
        # ...and the channel is what does carry.
        assert sp.comms_link(fused, here, there, speaker_name="The Stranger",
                             observer_name="Hinami")

    def test_the_beat_is_played_in_the_couple(self, temp_db):
        """The redirect, asked of the route rather than of the driver: the
        client goes on naming the frame it has always named."""
        chat_id, _, bubble = self._bubbled(temp_db)
        _handset(chat_id, [None, bubble])
        couple = _reconcile(chat_id, None, 4)[0]["couple_frame_id"]

        assert spatial_frames.live_couple_for(chat_id, None) == couple
        assert spatial_frames.live_couple_for(chat_id, bubble) == couple

    def test_closing_the_handset_closes_the_couple(self, temp_db):
        chat_id, _, bubble = self._bubbled(temp_db)
        _handset(chat_id, [None, bubble])
        couple = _reconcile(chat_id, None, 4)[0]["couple_frame_id"]

        _handset(chat_id, [couple], op="close")
        result, ctx = _reconcile(chat_id, couple, turn_idx=5)

        assert result["uncoupled"] is True
        assert get_frame(couple)["merged_turn_idx"] == 5
        assert get_frame(bubble)["merged_turn_idx"] is None
        assert spatial_frames.live_couple_for(chat_id, None) is None
        assert any("apart" in w for w in ctx.warnings)

    def test_a_live_handset_keeps_the_couple_open(self, temp_db):
        chat_id, _, bubble = self._bubbled(temp_db)
        _handset(chat_id, [None, bubble])
        couple = _reconcile(chat_id, None, 4)[0]["couple_frame_id"]

        result, _ = _reconcile(chat_id, couple, turn_idx=5)
        assert result == {"coupled": True, "couple_frame_id": couple}
        assert get_frame(couple)["merged_turn_idx"] is None

    def test_nothing_else_happens_inside_a_couple(self, temp_db):
        """A split or a merge decided against a fused view would partition a
        world that is about to be partitioned by the map, and the two answers
        would disagree. The couple frame answers one question only."""
        chat_id, _, bubble = self._bubbled(temp_db)
        _handset(chat_id, [None, bubble])
        couple = _reconcile(chat_id, None, 4)[0]["couple_frame_id"]

        before = {row["id"] for row in temp_db.q(
            "SELECT id FROM frames WHERE chat_id=?", (chat_id,))}
        _reconcile(chat_id, couple, turn_idx=5)
        after = {row["id"] for row in temp_db.q(
            "SELECT id FROM frames WHERE chat_id=?", (chat_id,))}
        assert after == before

    def test_the_bubble_survives_the_call_rather_than_being_rebuilt(
            self, temp_db):
        """The whole cycle, and the reason it is cheap.

        A call does not destroy and re-make a bubble: `merged_turn_idx` is
        never touched, so when the handset goes off the SAME frame is simply
        un-fused, holding the same cast and the same ledger it held before
        anybody picked the radio up. A couple that ended by merging and
        re-splitting would pay `perform_split` per call and hand the two sides
        each other's whole separation on the way through.
        """
        chat_id, hinami, bubble = self._bubbled(temp_db)
        _handset(chat_id, [None, bubble])
        couple = _reconcile(chat_id, None, 4)[0]["couple_frame_id"]
        _handset(chat_id, [couple], op="close")
        _reconcile(chat_id, couple, turn_idx=5)

        assert get_frame(bubble)["merged_turn_idx"] is None
        assert {r["id"] for r in active_cast(chat_id, bubble)} == {hinami}
        assert "Hinami" in (wget_for_frame(chat_id, "scene", bubble, {})
                            .get("positions") or {})
        # And nothing structural is left to do: no second bubble, no couple.
        frames_before = {row["id"] for row in temp_db.q(
            "SELECT id FROM frames WHERE chat_id=?", (chat_id,))}
        assert _reconcile(chat_id, None, turn_idx=6)[0] == {"active": False}
        assert {row["id"] for row in temp_db.q(
            "SELECT id FROM frames WHERE chat_id=?", (chat_id,))} == frames_before

    def test_a_second_call_couples_the_same_two_frames_again(self, temp_db):
        chat_id, _, bubble = self._bubbled(temp_db)
        for turn in (4, 8):
            _handset(chat_id, [None, bubble])
            couple = _reconcile(chat_id, None, turn)[0]["couple_frame_id"]
            assert get_frame(couple)["kind"] == "couple"
            _handset(chat_id, [couple], op="close")
            assert _reconcile(chat_id, couple, turn + 1)[0]["uncoupled"] is True
        assert get_frame(bubble)["merged_turn_idx"] is None


# ================================================================ 3. it rejoins


class TestTheBubbleRejoins:
    def test_walking_into_the_players_zone_ends_the_separation(self, temp_db):
        chat_id, hinami = _story(temp_db)
        bubble = _reconcile(chat_id, None, 3)[0]["child_frame_id"]

        # She comes back. The ship's own rooms are not in her frame -- the
        # split gave her the away-zoned and unzoned ones -- so her Director
        # plants the room she walks into, as it would for any arrival.
        scene = wget_for_frame(chat_id, "scene", bubble, {})
        scene["rooms"]["bridge"] = {"name": "Bridge", "adjacent": [],
                                    "zone": "ship"}
        scene["positions"]["Hinami"] = "bridge"
        wset_for_frame(chat_id, "scene", scene, bubble)

        result, _ = _reconcile(chat_id, None, turn_idx=7)

        assert result["merged"] is True
        assert get_frame(bubble)["merged_turn_idx"] == 7
        assert {r["id"] for r in active_cast(chat_id, None)} == {hinami}
        assert "Hinami" in (wget_for_frame(chat_id, "scene", None, {})
                            .get("positions") or {})

    def test_a_bubble_still_away_does_not_merge(self, temp_db):
        chat_id, _ = _story(temp_db)
        bubble = _reconcile(chat_id, None, 3)[0]["child_frame_id"]
        assert spatial_frames.detect_merge(chat_id, None) is None
        assert get_frame(bubble)["merged_turn_idx"] is None


class TestWalkingIntoTheRoomMidCall:
    """`uncouple_decision`'s whole reason for reporting a REASON.

    `comms_link` declines a pair a voice already reaches, so the naive
    negation of the couple predicate -- "no link, therefore uncouple" -- fires
    hardest exactly when the two parties have walked into the same room, and
    would tear a pair standing face to face into two frames. Here they do
    walk into one room, and what must happen is the opposite: the couple ends
    AND the separation ends, in that order, one structural change per commit.
    """

    def test_a_reunion_in_a_call_ends_the_call_and_then_the_split(self, temp_db):
        chat_id, hinami = _story(temp_db)
        bubble = _reconcile(chat_id, None, 3)[0]["child_frame_id"]
        _handset(chat_id, [None, bubble])
        couple = _reconcile(chat_id, None, 4)[0]["couple_frame_id"]

        # She walks onto the bridge, still holding the handset.
        fused = wget_for_frame(chat_id, "scene", couple, {})
        fused["positions"]["Hinami"] = "bridge"
        wset_for_frame(chat_id, "scene", fused, couple)

        closed, _ = _reconcile(chat_id, couple, turn_idx=5)
        assert closed["uncoupled"] is True

        merged, _ = _reconcile(chat_id, None, turn_idx=6)
        assert merged["merged"] is True
        assert get_frame(bubble)["merged_turn_idx"] == 6
        assert {r["id"] for r in active_cast(chat_id, None)} == {hinami}
        positions = (wget_for_frame(chat_id, "scene", None, {})
                     .get("positions") or {})
        assert positions.get("Hinami") == "bridge"
        assert positions.get("The Stranger") == "bridge"


# =============================================================== 4. the firewall


class TestWhatTheCallDoesNotCarry:
    def _in_a_call(self, db):
        chat_id, hinami = _story(db)
        bubble = _reconcile(chat_id, None, 3)[0]["child_frame_id"]
        _handset(chat_id, [None, bubble])
        couple = _reconcile(chat_id, None, 4)[0]["couple_frame_id"]
        return chat_id, hinami, bubble, couple

    def test_a_memory_formed_in_a_call_is_stamped_with_its_own_member_frame(
            self, temp_db):
        """Through the real mint door, not raw SQL. `prepare_memory` is the one
        place every path walks through, so a couple frame id reaching the
        column would mean the two ledgers had a shared era."""
        chat_id, hinami, bubble, couple = self._in_a_call(temp_db)

        token = active_frame_id.set(couple)
        try:
            row = prepare_memory(chat_id, hinami, None, "episodic",
                                 "witnessed", 0.5, "a voice on the handset",
                                 turn_idx=4)
        finally:
            active_frame_id.reset(token)

        assert row["frame_id"] == bubble
        assert row["frame_id"] != couple

    def test_a_mind_on_the_radio_still_reads_its_own_ledger(self, temp_db):
        """The other half, and it is the one a naive fix breaks: stamp
        correctly and read wrong, and the away party forgets everything since
        the split for exactly as long as they are on the radio."""
        chat_id, hinami, bubble, couple = self._in_a_call(temp_db)
        temp_db.qi(
            "INSERT INTO memories(chat_id,char_id,turn_idx,frame_id,content,"
            "kind,provenance) VALUES(?,?,?,?,?,'episodic','witnessed')",
            (chat_id, hinami, 4, bubble, "what the city actually held"))

        rows = visible_memory_rows(chat_id, hinami, before_turn_idx=None,
                                   viewer_frame_id=couple,
                                   include_archived=False)
        assert [r["content"] for r in rows] == ["what the city actually held"]

    def test_the_call_does_not_make_the_away_ledger_readable_at_home(
            self, temp_db):
        chat_id, hinami, bubble, couple = self._in_a_call(temp_db)
        temp_db.qi(
            "INSERT INTO memories(chat_id,char_id,turn_idx,frame_id,content,"
            "kind,provenance) VALUES(?,?,?,?,?,'episodic','witnessed')",
            (chat_id, hinami, 4, bubble, "what the city actually held"))

        assert visible_memory_rows(chat_id, hinami, before_turn_idx=None,
                                   viewer_frame_id=None,
                                   include_archived=False) == []


# ============================================================ 5. across a branch


class TestACallSurvivesABranch:
    """`couple:<frame_id>` is chat-global, so the generic frame-scoped KEY
    remap never sees it, and every id it holds is an integer the string-id
    remap never touches. A branch taken mid-call must rescope both, or
    `close_couple` would partition a fused scene back into the SOURCE chat's
    frames -- the one way this feature could put a body somewhere it never was.
    """

    def _world(self):
        from world.spatial_frames import COUPLE_MAP_PREFIX
        return {
            f"{COUPLE_MAP_PREFIX}7": {
                "members": [None, 5], "home": None, "opened_turn": 9,
                "rooms": {"bridge": "a"}, "bodies": {"Hinami": "b"},
                "cast": {"a": [], "b": [31]}, "names": {"a": [], "b": []},
                "personas": {"12": 5}, "clocks": {}, "sides": {},
            },
        }

    def test_every_id_in_the_map_is_rescoped(self):
        from web.app import _remap_couple_frames
        from world.spatial_frames import COUPLE_MAP_PREFIX

        world = self._world()
        _remap_couple_frames(world, {7: 70, 5: 50, None: None},
                             char_idmap={31: 310}, persona_idmap={12: 120})

        assert f"{COUPLE_MAP_PREFIX}7" not in world
        mapped = world[f"{COUPLE_MAP_PREFIX}70"]
        assert mapped["members"] == [None, 50]
        assert mapped["home"] is None
        assert mapped["personas"] == {"120": 50}
        assert mapped["cast"] == {"a": [], "b": [310]}

    def test_a_same_install_branch_keeps_shared_ids(self):
        """Characters and personas are shared rows on a branch and keep their
        ids; only an import into another install supplies the two maps."""
        from web.app import _remap_couple_frames
        from world.spatial_frames import COUPLE_MAP_PREFIX

        world = self._world()
        _remap_couple_frames(world, {7: 70, 5: 50, None: None})
        mapped = world[f"{COUPLE_MAP_PREFIX}70"]
        assert mapped["cast"] == {"a": [], "b": [31]}
        assert mapped["personas"] == {"12": 50}

    def test_an_uncloned_member_drops_the_map_rather_than_dangling(self):
        """An unpartitionable couple is worse than no couple: the two parties
        would stay fused with nothing able to separate them again."""
        from web.app import _remap_couple_frames
        from world.spatial_frames import COUPLE_MAP_PREFIX

        world = self._world()
        _remap_couple_frames(world, {7: 70, None: None})
        assert not [k for k in world if k.startswith(COUPLE_MAP_PREFIX)]


# ================================================== 6. what the fuse must not keep


class TestTheFuseChoiceIsUndone:
    """A split hands the child every UNZONED room while the parent keeps all of
    them, so the two id spaces overlap by construction and then diverge for as
    long as the parties are apart. The fused view has to pick one copy of each
    shared id to play in -- one scene cannot hold two versions of one room --
    and the close must not let that choice propagate, or every call would
    overwrite the home frame's attic with the away frame's, and again per call.
    """

    def _diverged(self, db):
        chat_id, hinami = _story(db)
        bubble = _reconcile(chat_id, None, 3)[0]["child_frame_id"]
        # `attic` is unzoned, so both frames hold it. Each side's Director
        # writes its own copy while they are apart.
        for frame_id, desc in ((None, "swept and lamplit"), (bubble, "still dark")):
            scene = wget_for_frame(chat_id, "scene", frame_id, {}) or {}
            scene["rooms"]["attic"] = {"name": "Attic", "adjacent": [],
                                       "desc": desc}
            wset_for_frame(chat_id, "scene", scene, frame_id)
        _handset(chat_id, [None, bubble])
        couple = _reconcile(chat_id, None, 4)[0]["couple_frame_id"]
        return chat_id, bubble, couple

    def _attic(self, chat_id, frame_id):
        return ((wget_for_frame(chat_id, "scene", frame_id, {}) or {})
                .get("rooms") or {}).get("attic", {}).get("desc")

    def test_each_side_keeps_its_own_copy_of_a_shared_room(self, temp_db):
        chat_id, bubble, couple = self._diverged(temp_db)
        _handset(chat_id, [couple], op="close")
        _reconcile(chat_id, couple, turn_idx=5)

        assert self._attic(chat_id, None) == "swept and lamplit"
        assert self._attic(chat_id, bubble) == "still dark"

    def test_ten_calls_lose_nothing(self, temp_db):
        """Per-cycle loss is invisible on the first call and total by the
        tenth, which is the shape a conversation actually has."""
        chat_id, hinami = _story(temp_db)
        bubble = _reconcile(chat_id, None, 3)[0]["child_frame_id"]
        for frame_id, desc in ((None, "swept and lamplit"), (bubble, "still dark")):
            scene = wget_for_frame(chat_id, "scene", frame_id, {}) or {}
            scene["rooms"]["attic"] = {"name": "Attic", "adjacent": [],
                                       "desc": desc}
            wset_for_frame(chat_id, "scene", scene, frame_id)

        for turn in range(4, 24, 2):
            _handset(chat_id, [None, bubble])
            couple = _reconcile(chat_id, None, turn)[0]["couple_frame_id"]
            _handset(chat_id, [couple], op="close")
            _reconcile(chat_id, couple, turn + 1)

        assert self._attic(chat_id, None) == "swept and lamplit"
        assert self._attic(chat_id, bubble) == "still dark"

    def test_a_room_changed_DURING_the_call_goes_to_both(self, temp_db):
        """The other half, and it must be both halves: a guard that simply
        restored each side's own copy would throw away what the beat did to
        the one room both frames answer for."""
        chat_id, bubble, couple = self._diverged(temp_db)

        fused = wget_for_frame(chat_id, "scene", couple, {})
        fused["rooms"]["attic"] = {"name": "Attic", "adjacent": [],
                                   "desc": "burning"}
        wset_for_frame(chat_id, "scene", fused, couple)
        _handset(chat_id, [couple], op="close")
        _reconcile(chat_id, couple, turn_idx=5)

        assert self._attic(chat_id, None) == "burning"
        assert self._attic(chat_id, bubble) == "burning"


# ========================================================= 7. what a quiet beat pays


def test_a_story_with_no_zones_pays_almost_nothing_per_beat(temp_db):
    """`detect_and_reconcile` runs on every committed beat of every story, so
    the bubble's cost on a beat that has no bubble in it is the cost the
    feature imposes on the whole engine.

    The number is a guard, not a target: it is here so that a later change
    that moves the gathering back in front of the cheapest refusal -- a
    persona query and a cast read per beat, to be told no -- fails a test
    instead of quietly costing every story.
    """
    chat_id = _make_chat(temp_db)
    _make_char(temp_db, chat_id, "Hinami")
    wset(chat_id, "scene", {
        "rooms": {"kitchen": {"name": "Kitchen", "adjacent": [
                      {"to": "hall", "barrier": "open"}]},
                  "hall": {"name": "Hall", "adjacent": [
                      {"to": "kitchen", "barrier": "open"}]}},
        "positions": {"The Stranger": "kitchen", "Hinami": "hall"},
        "entities": {}, "attire": {}, "overlays": {}, "comms": {},
    })

    counted = []
    real_q = temp_db.q
    temp_db.q = lambda sql, *a, **k: (counted.append(sql), real_q(sql, *a, **k))[1]
    try:
        assert spatial_bubbles.detect_bubble(chat_id, None, 3) is None
    finally:
        temp_db.q = real_q

    # Measured: 2 (the chat row, and the scene's own world row). The same
    # detector on a ZONED scene costs 5, because that is when the persona and
    # cast reads are worth making.
    assert len(counted) <= 2, counted


def test_a_call_invents_no_world_rows_that_were_never_there(temp_db):
    """ABSENT IS NOT NULL, and it is not `{}` either.

    `wget` returns a stored value verbatim and its default only when the ROW is
    missing, so a couple that copied a key its home frame does not have into
    the fused frame and back would leave an explicit null where there had been
    nothing -- and every reader passing a real default would get None from that
    key forever after. Asserted over the whole key set rather than over the
    handful a fixture happens to seed, because the loss is per key and silent.
    """
    from core.db import FRAME_SCOPED_WORLD_KEYS

    chat_id, hinami = _story(temp_db)
    bubble = _reconcile(chat_id, None, 3)[0]["child_frame_id"]
    _handset(chat_id, [None, bubble])

    missing = object()

    def present(frame_id):
        return {k for k in sorted(FRAME_SCOPED_WORLD_KEYS)
                if wget_for_frame(chat_id, k, frame_id, missing) is not missing}

    before = {fid: present(fid) for fid in (None, bubble)}

    couple = _reconcile(chat_id, None, 4)[0]["couple_frame_id"]
    _handset(chat_id, [couple], op="close")
    _reconcile(chat_id, couple, turn_idx=5)

    for fid in (None, bubble):
        assert present(fid) == before[fid], fid


def test_an_unrelated_dead_channel_survives_a_call(temp_db):
    """`fuse_comms` answers which channels the two frames can be HELD to, and
    refuses one that either side hung up. That is the right answer for the
    decision and the wrong one for the scene: dropping a refused channel would
    delete a dead intercom in the away frame the first time anybody made an
    unrelated call, and again per call.
    """
    chat_id, _ = _story(temp_db)
    bubble = _reconcile(chat_id, None, 3)[0]["child_frame_id"]

    # A wall intercom in the city, switched off, belonging to the away frame
    # alone -- nothing to do with the handset the call runs on.
    scene = wget_for_frame(chat_id, "scene", bubble, {}) or {}
    # Both rooms must be ones HER frame holds, or `normalize_scene_comms`
    # prunes the channel for naming a room nobody in it can stand in -- which
    # is correct, and is a different rule from the one under test.
    scene["rooms"]["attic"] = {"name": "Attic", "adjacent": [
        {"to": "market", "barrier": "open"}]}
    scene["rooms"]["market"]["adjacent"] = list(
        scene["rooms"]["market"].get("adjacent") or []) + [
            {"to": "attic", "barrier": "open"}]
    sp.apply_comms_ops(scene, [{"id": "intercom", "name": "the wall intercom",
                                "rooms": ["market", "attic"]}])
    sp.apply_comms_ops(scene, [{"id": "intercom", "op": "close"}])
    wset_for_frame(chat_id, "scene", scene, bubble)

    _handset(chat_id, [None, bubble])
    couple = _reconcile(chat_id, None, 4)[0]["couple_frame_id"]
    _handset(chat_id, [couple], op="close")
    _reconcile(chat_id, couple, turn_idx=5)

    after = (wget_for_frame(chat_id, "scene", bubble, {}) or {}).get("comms") or {}
    assert "intercom" in after, "the device is still on the wall"
    assert after["intercom"]["live"] is False
    assert after["intercom"]["rooms"] == ["market", "attic"]


def test_a_body_dormant_in_both_frames_does_not_walk_into_the_call(temp_db):
    """`active_cast` falls back to the BASE `chat_chars` row in a frame with no
    override -- right for a fresh spatial child walking away mid-continuity,
    and wrong for a couple, which is not where anybody's baseline lives.

    THE HAZARD NEEDS A REAL PARENT FRAME, and saying why is the point. Off the
    PRESENT (`frame_id` None) the parent's override IS the base row, so
    "dormant in the parent" and "dormant in the base" are one fact and the
    fallback cannot disagree with anyone. Split off a declared frame and they
    come apart: the base row still says active, neither member's cast holds
    them, and without an explicit statement per character a body nobody's
    story has on stage would have been in the room for the call.
    """
    from core.frames import create_frame
    from story.scene import set_char_status

    chat_id = _make_chat(temp_db)
    hinami = _make_char(temp_db, chat_id, "Hinami")
    gone = _make_char(temp_db, chat_id, "Vela")
    era = create_frame(chat_id, label="Later", ordinal=5, kind="future")
    wset_for_frame(chat_id, "scene", json.loads(json.dumps(BASE_SCENE)), era)

    bubble = _reconcile(chat_id, era, 3)[0]["child_frame_id"]
    for frame_id in (era, bubble):
        set_char_status(chat_id, gone, "dormant", frame_id=frame_id)
    assert temp_db.q("SELECT status FROM chat_chars WHERE chat_id=? AND char_id=?",
                     (chat_id, gone), one=True)["status"] == "active"
    assert gone not in {r["id"] for r in active_cast(chat_id, era)}
    assert gone not in {r["id"] for r in active_cast(chat_id, bubble)}

    _handset(chat_id, [era, bubble])
    couple = _reconcile(chat_id, era, 4)[0]["couple_frame_id"]

    in_call = {r["id"] for r in active_cast(chat_id, couple)}
    assert in_call == {hinami}

    _handset(chat_id, [couple], op="close")
    _reconcile(chat_id, couple, turn_idx=5)
    assert not temp_db.q(
        "SELECT 1 FROM chat_char_frames WHERE chat_id=? AND frame_id=?",
        (chat_id, couple))


# ============================================ 8. what the range trigger costs


class TestWhatRangeCostsThatZonesDidNot:
    """The zone trigger fired on a LABEL and the range trigger fires on the
    map, so the map's gaps are now visible in a way they were not. Both
    behaviours below are consequences of the owner's rule rather than bugs
    under it, and they are pinned here so a later reading of either is a
    decision rather than a surprise.
    """

    def test_a_room_with_no_edges_is_out_of_range_immediately(self, temp_db):
        """AN UNDRAWN ADJACENCY NOW READS AS DISTANCE.

        A freshly minted room with no `adjacent` yet is an island to
        `nearby_rooms`, so a body standing in it is outside the beat and gets
        a bubble on the spot -- even if the fiction has them through a doorway.
        This is consistent with the rule (the Director's payload does not
        carry that room either, so the beat genuinely cannot reach them), and
        it is the one case where the map being unfinished has a structural
        consequence rather than a cosmetic one.
        """
        chat_id, hinami = _story(temp_db)
        scene = wget_for_frame(chat_id, "scene", None, {}) or {}
        scene["positions"]["Hinami"] = "attic"          # the island room
        wset_for_frame(chat_id, "scene", scene, None)

        result, _ = _reconcile(chat_id, None, turn_idx=3)
        assert result["bubble"] is True
        assert result["rooms"] == ["attic"]

    def test_the_bubble_ends_the_moment_an_edge_puts_her_back_in_reach(
            self, temp_db):
        """...and the release is the same predicate, which is what makes the
        case above survivable: the mapping that draws the doorway ends the
        bubble on the next commit, with no label and no reunion beat."""
        chat_id, hinami = _story(temp_db)
        scene = wget_for_frame(chat_id, "scene", None, {}) or {}
        scene["positions"]["Hinami"] = "attic"
        wset_for_frame(chat_id, "scene", scene, None)
        bubble = _reconcile(chat_id, None, 3)[0]["child_frame_id"]

        for frame_id in (None, bubble):
            sc = wget_for_frame(chat_id, "scene", frame_id, {}) or {}
            if "attic" in (sc.get("rooms") or {}):
                sc["rooms"]["attic"] = {"name": "Attic", "adjacent": [
                    {"to": "bridge", "barrier": "open"}]}
            if "bridge" in (sc.get("rooms") or {}):
                sc["rooms"]["bridge"]["adjacent"] = [
                    {"to": "lane", "barrier": "closed_door"},
                    {"to": "attic", "barrier": "open"}]
            wset_for_frame(chat_id, "scene", sc, frame_id)

        result, _ = _reconcile(chat_id, None, turn_idx=4)
        assert result["merged"] is True
        assert get_frame(bubble)["merged_turn_idx"] == 4

    def test_a_handset_holds_a_body_in_the_beat_across_any_distance(
            self, temp_db):
        """The repair that made the range rule usable at all.

        `comms_reachable_rooms` claims in its own docstring that "a handset,
        an intercom and a field radio all pass" its two-way test. A CARRIED
        channel did not: it names bodies and no rooms, so the reverse
        direction was asked with no speaker and answered no, every time. With
        range as the trigger that stopped being a missing payload row and
        became a body who is on the radio to the player and in a frame of her
        own regardless.
        """
        chat_id, _ = _story(temp_db, comms=[{
            "id": "handset", "carriers": ["The Stranger", "Hinami"]}])
        scene = wget_for_frame(chat_id, "scene", None, {}) or {}
        scene["positions"]["Hinami"] = "attic"          # as far as the map goes
        wset_for_frame(chat_id, "scene", scene, None)

        assert _reconcile(chat_id, None, turn_idx=3)[0] == {"active": False}


# =========================================== 9. the bubble's own beat


class TestThePlayerlessBeat:
    """A bubble that only ever holds still is a place, not a life.

    Measured before this landed (`google/gemini-3.8-flash`, the Millbrook run,
    2026-09-17): a courier crossed to the far shore and stood on the landing
    for three player beats, her frame's scene byte-identical each time, and
    formed not one memory. These tests are about the beat that fixes that --
    what it plans, what it refuses to plan, and that it costs no model call to
    decide nobody spoke.
    """

    def _bubbled(self, db):
        chat_id, hinami = _story(db)
        bubble = _reconcile(chat_id, None, 3)[0]["child_frame_id"]
        return chat_id, hinami, bubble

    def test_a_turn_in_a_bubble_with_no_input_is_the_engines_own_beat(
            self, temp_db):
        from agents.offscreen_beat import is_offscreen_beat

        chat_id, _, bubble = self._bubbled(temp_db)
        tid = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
            "VALUES(?,?,?,?,?)", (chat_id, 4, "", time.time(), bubble))
        row = temp_db.q("SELECT * FROM turns WHERE id=?", (tid,), one=True)
        assert is_offscreen_beat(chat_id, row) is True

    def test_a_host_who_types_into_her_frame_is_playing_it(self, temp_db):
        """The same frame, the same character, and an ordinary beat -- because
        somebody is reading it. This is what keeps the derivation honest: the
        marker is the absence of input, not the frame."""
        from agents.offscreen_beat import is_offscreen_beat

        chat_id, _, bubble = self._bubbled(temp_db)
        tid = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
            "VALUES(?,?,?,?,?)", (chat_id, 4, "She keeps walking.",
                                  time.time(), bubble))
        row = temp_db.q("SELECT * FROM turns WHERE id=?", (tid,), one=True)
        assert is_offscreen_beat(chat_id, row) is False

    def test_the_players_own_frame_is_never_an_offscreen_beat(self, temp_db):
        from agents.offscreen_beat import is_offscreen_beat

        chat_id, _, _bubble = self._bubbled(temp_db)
        tid = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
            "VALUES(?,?,?,?,?)", (chat_id, 4, "", time.time(), None))
        row = temp_db.q("SELECT * FROM turns WHERE id=?", (tid,), one=True)
        assert is_offscreen_beat(chat_id, row) is False

    def test_the_plan_stops_at_the_commit(self, temp_db):
        """No narrator, because nobody is reading it -- and a page describing
        her beat is a page that could be shown. No background reactors either:
        the voice tier answers the demand of a beat somebody is in."""
        from agents.runtime import build_plan
        from agents.offscreen_beat import offscreen_interpretation

        chat_id, hinami, bubble = self._bubbled(temp_db)
        cast = active_cast(chat_id, bubble)
        scene = wget_for_frame(chat_id, "scene", bubble, {}) or {}
        interp = offscreen_interpretation(cast, scene)

        keys = [k for k, _ in build_plan(interp, cast, chat_id=chat_id,
                                         frame_id=bubble, offscreen=True)]
        assert "narrator" not in keys
        assert not any(k.startswith("background") for k in keys)
        assert keys[-1] == "commit", (
            "a beat nobody commits is a beat that did not happen")
        assert "perception_outcome" in keys
        assert "perception_act" in keys
        assert "director_resolve" in keys
        # ...and she is asked to act, which is the whole point.
        assert any(k == f"character:{hinami}" or k == "interaction_loop"
                   for k in keys), keys

    def test_the_player_frames_plan_still_has_its_narrator(self, temp_db):
        from agents.runtime import build_plan
        from agents.offscreen_beat import offscreen_interpretation

        chat_id, _, bubble = self._bubbled(temp_db)
        cast = active_cast(chat_id, bubble)
        interp = offscreen_interpretation(cast, wget_for_frame(
            chat_id, "scene", bubble, {}) or {})
        keys = [k for k, _ in build_plan(interp, cast, chat_id=chat_id,
                                         frame_id=bubble, offscreen=False)]
        assert "narrator" in keys

    def test_the_interpretation_declares_no_conduct_and_costs_nothing(
            self, temp_db):
        """An interpret stage asked to read an absent player's input is asked
        to invent one, and nobody may author the player's conduct. The safe
        way to say that is a payload that declares nothing."""
        from agents.offscreen_beat import offscreen_interpretation

        chat_id, hinami, bubble = self._bubbled(temp_db)
        cast = active_cast(chat_id, bubble)
        scene = wget_for_frame(chat_id, "scene", bubble, {}) or {}
        interp = offscreen_interpretation(cast, scene)

        assert interp["speech"] == ""
        assert interp["action"] == ""
        assert interp["actions"] == []
        assert interp["movement"] is None
        assert interp["ledgers"] == []
        assert interp["state_assertions"] == []
        # What it DOES say: whose beat this is.
        assert interp["flow"]["reactors"] == [hinami]

    def test_it_schedules_a_beat_for_a_live_bubble_and_none_otherwise(
            self, temp_db):
        from agents.offscreen_beat import live_bubbles

        chat_id, _, bubble = self._bubbled(temp_db)
        assert live_bubbles(chat_id, None) == [bubble]

        # Once she is back in the beat there is nothing to advance.
        scene = wget_for_frame(chat_id, "scene", bubble, {}) or {}
        scene["positions"]["Hinami"] = "bridge"
        wset_for_frame(chat_id, "scene", scene, bubble)
        _reconcile(chat_id, None, turn_idx=4)
        assert live_bubbles(chat_id, None) == []

    def test_a_story_with_no_bubbles_schedules_nothing(self, temp_db):
        from agents.offscreen_beat import schedule_offscreen_beats

        chat_id, _ = _story(temp_db)
        ctx = _ctx(chat_id, None, 3)
        assert schedule_offscreen_beats(ctx) is None


# ================================== 10. she walks away into the same world


class TestTheAwayPartyKeepsTheWorld:
    """A spatial split is the same era SOMEWHERE ELSE -- the child takes the
    parent's own `ordinal` -- so the town over the hill is the same town.

    A split seeded eight keys and all eight were about the PARTY: what they
    know, their clock, their intentions, their obligations, their log. The
    WORLD half was missing entirely, and a bubble is what made it visible: an
    away character walked into a market town with no institutions, no crowd,
    no rider on the road and no notice on any wall. The one thing a bubble
    exists to show -- what somebody does out there, among people -- had nobody
    in it to do it among.
    """

    WORLD = {"charters": {"guild": {"name": "The Millers' Hall"}},
             "crowds": {"market": {"size": "thick"}},
             "couriers": [{"name": "a rider on the north road"}],
             "artifacts": [{"name": "a notice nailed to the post"}]}

    def _town(self, db):
        chat_id, hinami = _story(db)
        for key, value in self.WORLD.items():
            wset_for_frame(chat_id, key, value, None)
        return chat_id, hinami

    def test_the_town_comes_with_her(self, temp_db):
        chat_id, _ = self._town(temp_db)
        bubble = _reconcile(chat_id, None, 3)[0]["child_frame_id"]

        for key, value in self.WORLD.items():
            assert wget_for_frame(chat_id, key, bubble, None) == value, key

    def test_nothing_the_world_holds_is_dropped_by_a_split(self, temp_db):
        """Over the whole key set rather than the four a fixture happens to
        seed, because the loss is per key and silent: a key added later is
        covered without anyone remembering to come back here."""
        from core.db import FRAME_SCOPED_WORLD_KEYS

        chat_id, _ = self._town(temp_db)
        # Everything the parent holds, in the shape its readers expect -- the
        # split appends to `offscreen_log`, so a dict there is a TypeError
        # rather than a measurement.
        lists = {"standing_intentions", "pending_obligations", "offscreen_log",
                 "couriers", "artifacts"}
        for key in sorted(FRAME_SCOPED_WORLD_KEYS):
            if wget_for_frame(chat_id, key, None, None) in (None, {}, [], ""):
                wset_for_frame(chat_id, key,
                               [{"seeded": key}] if key in lists
                               else "seeded" if key == "shadow_profile"
                               else {"seeded": key}, None)
        bubble = _reconcile(chat_id, None, 3)[0]["child_frame_id"]

        author_owned = {
            # The Room's, not the world's: a party that walks over the hill
            # has not left the story, and its mandates, bible, packages and
            # frontier are the story's rather than the place's.
            "room_mandates", "room_status", "room_bible", "room_frontier",
            "room_proposals", "plot_packages",
            # The PLAYER's own carrier envelope, and the ledger of who was
            # co-present with them: both are about the party that stayed.
            "persona_carrier_state", "subject_last_seen",
            # Per-beat scratch, rebuilt by the beat that needs it.
            "pending", "lore_cache", "active_books", "offscreen_epoch",
            "offscreen_plans", "planning_needs", "knowledge_circles",
            "scene", "known",
        }
        lost = [k for k in sorted(FRAME_SCOPED_WORLD_KEYS)
                if k not in author_owned
                and wget_for_frame(chat_id, k, bubble, None) in (None, {}, [], "")]
        assert lost == [], lost


# ================================ 11. she can reach where she is going


class TestTheBubbleIsNotACulDeSac:
    """A split used to give the away party a SUBSET of the rooms while the
    parent kept every one, including the ones the child took.

    That asymmetry had no argument behind it and one large consequence: the
    away frame could never gain a room. The player's frame grows as the
    Director plants places; the child's map was frozen at the instant of the
    split, so anywhere the party was GOING did not exist for them.

    Measured live (Aldermill, `google/gemini-3.8-flash`, 2026-09-17): a
    companion split off holding two rooms, and on all four of her own beats
    she walked east toward a watermill that was not in her world --
    *"trudges steadily eastward along the packed cart ruts"*, four times,
    `state_diff.positions` null every time, and her memory of the afternoon
    was "I was in River Road." The Director was right to refuse: there was
    nowhere to put her. His frame held sixteen rooms by then; hers held two.
    """

    def _wide_town(self, db):
        """A road out of town, three rooms long, and she is on the first of
        them -- so the place she is walking to is two hops past her reach."""
        chat_id, hinami = _story(db)
        scene = wget_for_frame(chat_id, "scene", None, {}) or {}
        scene["rooms"]["road"] = {"name": "The road", "adjacent": [
            {"to": "market", "barrier": "open"},
            {"to": "mill_yard", "barrier": "open"}]}
        scene["rooms"]["mill_yard"] = {"name": "The mill yard", "adjacent": [
            {"to": "road", "barrier": "open"},
            {"to": "mill_floor", "barrier": "open"}]}
        scene["rooms"]["mill_floor"] = {"name": "The mill floor", "adjacent": [
            {"to": "mill_yard", "barrier": "open"}]}
        scene["rooms"]["market"]["adjacent"] = list(
            scene["rooms"]["market"].get("adjacent") or []) + [
                {"to": "road", "barrier": "open"}]
        wset_for_frame(chat_id, "scene", scene, None)
        return chat_id, hinami

    def test_the_whole_map_goes_with_her(self, temp_db):
        chat_id, _ = self._wide_town(temp_db)
        bubble = _reconcile(chat_id, None, 3)[0]["child_frame_id"]

        parent_rooms = set((wget_for_frame(chat_id, "scene", None, {})
                            .get("rooms") or {}))
        her_rooms = set((wget_for_frame(chat_id, "scene", bubble, {})
                         .get("rooms") or {}))
        assert her_rooms == parent_rooms
        assert "mill_floor" in her_rooms, "somewhere to be going"

    def test_she_can_walk_to_a_room_beyond_her_reach(self, temp_db):
        """The defect itself: the destination has to be somewhere the Director
        can actually put her. Walked one room per beat, as a body walks."""
        from world.spatial import passable_route_exists

        chat_id, _ = self._wide_town(temp_db)
        bubble = _reconcile(chat_id, None, 3)[0]["child_frame_id"]
        her_scene = wget_for_frame(chat_id, "scene", bubble, {}) or {}

        assert passable_route_exists(her_scene, "market", "mill_floor")
        for room in ("road", "mill_yard", "mill_floor"):
            her_scene["positions"]["Hinami"] = room
            wset_for_frame(chat_id, "scene", her_scene, bubble)
            assert (wget_for_frame(chat_id, "scene", bubble, {})
                    .get("positions", {}).get("Hinami")) == room

    def test_holding_the_map_is_not_being_in_it(self, temp_db):
        """The reason this costs nothing. A map is not a perception: which
        rooms a scene DESCRIBES says nothing about what a body in it can see
        or hear, which is `spatial_rel` off positions -- and the parent has
        always held the whole map without that being a leak."""
        from world.spatial import hear_level, sight_level, spatial_rel

        chat_id, _ = self._wide_town(temp_db)
        bubble = _reconcile(chat_id, None, 3)[0]["child_frame_id"]
        her = wget_for_frame(chat_id, "scene", bubble, {}) or {}

        assert "bridge" in her["rooms"], "she holds the room he is in"
        assert "The Stranger" not in (her.get("positions") or {}), (
            "and not the body standing in it")
        # There is nobody in it to perceive, which is the whole of it: a room
        # in her scene with no body in it delivers nothing to anybody, and the
        # split partitions exactly the thing that would.
        assert [n for n, r in (her.get("positions") or {}).items()
                if r == "bridge"] == []
        rel = spatial_rel(her, "mill_floor", "bridge")
        assert sight_level(rel) == "none"
        # `separated` still hands a SHOUT a fragment between two rooms of one
        # scene that no edge joins -- unchanged by this, true of the parent's
        # map since before bubbles existed, and reaching nobody here because
        # no body is at either end. Where the engine does know two places are
        # genuinely elsewhere it says so: `room_locale` reports `remote`
        # between two declared locales, which is opaque to a shout
        # (`TestTheFuseChoiceIsUndone`'s sibling in the couple spec).
        assert hear_level(rel, "shout") == "fragment"

    def test_the_player_still_keeps_everything_he_had(self, temp_db):
        chat_id, _ = self._wide_town(temp_db)
        before = set((wget_for_frame(chat_id, "scene", None, {})
                      .get("rooms") or {}))
        _reconcile(chat_id, None, 3)
        after = set((wget_for_frame(chat_id, "scene", None, {})
                     .get("rooms") or {}))
        assert after == before
