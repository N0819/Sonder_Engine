"""The COUPLE relation: what must be true before one ships.

A couple is the proposed answer to "two bubbles are separated, and then a
comm channel opens between them". The design's choice is that the frames
STAY SPLIT -- `merged_turn_idx` is never touched -- and a temporary third
frame materialises the fused view as storage, so `get_scene` and the
eighteen ambient readers in `agents/` work unchanged and
`spatial_rel`/`comms_link`/`composer` do the separation work for free. On
close, that frame is partitioned back to its two members by a map recorded
at open.

This file is the SPECIFICATION for that, written before the driver, and it
is deliberately in two halves.

The first half asserts what is true TODAY and must survive a couple. Those
tests pass now. They are here because a couple is a change to the physical
and epistemic layers, and the cheapest way to notice it broke one is to
have written down what those layers said beforehand.

The second half asserts what a couple must do, against an API that does
not exist. Those are xfail(strict) on the API's absence -- the moment
`world/spatial_frames.py` grows `detect_couple`/`open_couple`/
`close_couple`, the markers go inert on their own and these become
ordinary failing tests until the behaviour is right.

THE PROPERTY, stated once: a couple carries a VOICE between two bubbles
and moves nothing else. Not a body, not a room, not a cast list, not one
line of anybody's memory ledger. The three ways this feature could destroy
the firewall are all one mistake wearing different clothes -- treating
"they can talk" as "they are together" -- and each assertion below is one
place that mistake would land.

Naming note: `detect_couple` / `open_couple` / `close_couple` are this
file's proposal. If the implementation lands other names, `_COUPLE_API`
and the three thin wrappers below are the only lines that change.
"""

from __future__ import annotations

import json
import time

import pytest

from web import app
from world import spatial as sp
from world import spatial_frames
from core.db import (FRAME_SCOPED_WORLD_KEYS, wget_for_frame, wset,
                     wset_for_frame)
from core.frames import create_frame, get_frame, is_memory_visible
from mind.memory import visible_memory_rows
from story.character_schema import default_character_data
from story.scene import active_cast


# --------------------------------------------------------------- the API

_COUPLE_API = ("detect_couple", "open_couple", "close_couple")
_MISSING = [name for name in _COUPLE_API if not hasattr(spatial_frames, name)]

needs_couple = pytest.mark.xfail(
    bool(_MISSING),
    reason=(
        "no couple driver yet -- world/spatial_frames.py defines none of "
        + ", ".join(_MISSING)
        + ". What must exist: (1) core/frames.create_frame must accept "
        "kind='couple' (it raises ValueError on anything outside "
        "past/future/other/spatial at core/frames.py:99-103); (2) "
        "detect_couple(chat_id, frame_id) -> (a_id, b_id) | None, deciding "
        "on comms_link over a candidate fused view; (3) open_couple(chat_id, "
        "a_id, b_id, turn_idx) -> couple_frame_id, recording the room->frame "
        "and body->frame map; (4) close_couple(chat_id, couple_frame_id, "
        "turn_idx) -> [warning, ...], partitioning every frame-scoped key "
        "back by that recorded map."
    ),
    strict=True,
)


def _detect_couple(chat_id, frame_id):
    return spatial_frames.detect_couple(chat_id, frame_id)


def _open_couple(chat_id, a_id, b_id, turn_idx):
    return spatial_frames.open_couple(chat_id, a_id, b_id, turn_idx=turn_idx)


def _close_couple(chat_id, couple_id, turn_idx):
    return spatial_frames.close_couple(chat_id, couple_id, turn_idx=turn_idx)


# ---------------------------------------------------------- construction

def _make_chat(db):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )


def _make_persona(db, name):
    return db.qi(
        "INSERT INTO personas(name,sheet) VALUES(?,?)",
        (name, json.dumps({"identity": {"name": name}})),
    )


def _make_char(db, name):
    return db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        (name, json.dumps(default_character_data(name)), "{}", time.time()),
    )


def _add_memory_row(db, chat_id, char_id, *, turn_idx, frame_id, content):
    """Straight SQL on purpose.

    `mind.memory_write.add_memory` embeds, and embedding is a provider
    call. Nothing in this file may make one, and nothing here needs a
    vector: every assertion is about which rows `visible_memory_rows`
    hands back, which is decided by `frames.is_memory_visible` on
    (char_id, frame_id, turn_idx) alone.
    """
    return db.qi(
        "INSERT INTO memories(chat_id,char_id,turn_idx,frame_id,content,kind,"
        "provenance) VALUES(?,?,?,?,?,'episodic','witnessed')",
        (chat_id, char_id, turn_idx, frame_id, content),
    )


SPLIT_TURN = 7


def _two_bubbles(db):
    """A real split, performed by the real machinery.

    Parent (the present frame, id None): the primary player and Nova on
    the bridge, zone `ship_alpha`. Child (a spatial frame): the extra
    persona Bob and Astra in the shuttle, zone `ship_beta`.

    Both sides carry a handset. A CARRIED channel rather than a fixed
    installation, because a room-endpoint channel is not representable
    across a split at all -- see
    `test_a_room_endpoint_channel_does_not_survive_into_the_away_frame`.
    """
    chat_id = _make_chat(db)
    bob = _make_persona(db, "Bob")
    app.chat_add_persona(chat_id, {"persona_id": bob})

    nova = _make_char(db, "Nova")
    astra = _make_char(db, "Astra")
    for char_id in (nova, astra):
        db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) "
            "VALUES(?,?,'active','{}')",
            (chat_id, char_id),
        )

    scene = {
        "location": "The Kestrel",
        "rooms": {
            "bridge": {"name": "Bridge", "adjacent": [], "zone": "ship_alpha"},
            "shuttle": {"name": "Shuttle", "adjacent": [], "zone": "ship_beta"},
        },
        "positions": {"The Stranger": "bridge", "Nova": "bridge",
                      "Bob": "shuttle", "Astra": "shuttle"},
        "entities": {}, "attire": {}, "overlays": {}, "comms": {},
        "contacts": [],
    }
    wset(chat_id, "scene", scene)
    wset(chat_id, "known", {"The Stranger": ["Nova", "Astra", "Bob"]})

    child = spatial_frames.perform_split(chat_id, None, turn_idx=SPLIT_TURN,
                                         away_zone="ship_beta")

    # One handset, held by one body on each side, recorded in each side's
    # own scene. Each side also has a contact strictly inside itself; the
    # couple must leave both alone.
    parent_scene = wget_for_frame(chat_id, "scene", None, {})
    sp.apply_comms_ops(parent_scene, [{
        "id": "handset", "name": "the handset",
        "carriers": ["The Stranger", "Bob"]}])
    parent_scene["contacts"] = [{
        "actor": "The Stranger", "actor_part": "hand",
        "target": "Nova", "target_part": "shoulder", "manner": "touch"}]
    wset_for_frame(chat_id, "scene", parent_scene, None)

    child_scene = wget_for_frame(chat_id, "scene", child, {})
    sp.apply_comms_ops(child_scene, [{
        "id": "handset", "name": "the handset",
        "carriers": ["The Stranger", "Bob"]}])
    child_scene["contacts"] = [{
        "actor": "Bob", "actor_part": "hand",
        "target": "Astra", "target_part": "wrist", "manner": "grip"}]
    wset_for_frame(chat_id, "scene", child_scene, child)

    return {"chat_id": chat_id, "child": child, "nova": nova, "astra": astra,
            "bob_persona": bob}


def _seed_the_keys_perform_split_does_not(chat_id, frame_id, tag):
    """Distinctive values in the frame-scoped keys the split leaves blank.

    `perform_split` seeds a closed list of seven (world/spatial_frames.py:
    847-858) and `perform_merge` lifts exactly two off the child scene
    (:1036-1041). Everything else -- charters, crowds, couriers,
    artifacts, offscreen_plans, subject_last_seen, persona_carrier_state
    -- is precisely where a fuse-and-refuse design loses state, so the
    totality assertion has to be seeded with something it would notice.
    """
    wset_for_frame(chat_id, "charters", {"guild": {"tag": tag}}, frame_id)
    wset_for_frame(chat_id, "crowds", {"market": {"tag": tag}}, frame_id)
    wset_for_frame(chat_id, "couriers", [{"tag": tag}], frame_id)
    wset_for_frame(chat_id, "artifacts", [{"tag": tag}], frame_id)
    wset_for_frame(chat_id, "offscreen_plans", {"tag": tag}, frame_id)
    wset_for_frame(chat_id, "subject_last_seen", {"1": {"tag": tag}}, frame_id)
    wset_for_frame(chat_id, "persona_carrier_state", {"tag": tag}, frame_id)
    wset_for_frame(chat_id, "standing_intentions", [{"tag": tag}], frame_id)


#: ABSENT IS NOT NULL, and reading the snapshot with a `None` default cannot
#: tell them apart. `wget` returns a stored JSON null verbatim and its default
#: only when the ROW is missing, so a couple that copied a key its home frame
#: does not have into the fused frame and back would leave an explicit null
#: where there had been nothing -- and every reader passing a real default
#: (`{}`, `[]`) would get None from that key forever after, per call. The
#: round trip is only total if it round-trips absence too.
_MISSING = "__no_row__"


def _frame_scoped_snapshot(chat_id, frame_id, char_ids):
    keys = sorted(FRAME_SCOPED_WORLD_KEYS) + [f"relationships:{c}"
                                              for c in sorted(char_ids)]
    return {k: wget_for_frame(chat_id, k, frame_id, _MISSING) for k in keys}


#: `offscreen_log` is APPEND-ONLY and the couple writes its own open and close
#: into it, exactly as `perform_split` and `perform_merge` write theirs. The
#: property these two tests assert is that nothing is DROPPED, and an audit
#: notice is not a loss -- a couple that logged nothing would be the one piece
#: of frame surgery with no record. So the pre-couple log must still be a
#: PREFIX of what came back, and every other key must be identical.
def _assert_nothing_lost(after, before, label=""):
    for key in before:
        if key == "offscreen_log" and before[key] is not _MISSING:
            head = (after[key] or [])[:len(before[key] or [])]
            assert head == (before[key] or []), f"{label}{key}"
            continue
        assert after[key] == before[key], f"{label}{key}"


# =====================================================================
# Half one: what is true today, and must still be true afterwards.
# =====================================================================


class TestTheSeparationTheCoupleInherits:
    """Two rooms with no edge between them.

    This is the whole reason the design fuses rooms without adding edges:
    `spatial_rel` is a one-step edge lookup, never a path search, so a
    disconnected cluster costs nothing and reports `separated` -- which
    is opaque on sight and scent already.
    """

    def test_no_edge_reads_as_separated(self):
        rel = sp.spatial_rel({"rooms": {"a": {}, "b": {}}}, "a", "b")
        assert rel["same_room"] is False
        assert rel["barrier"] == "separated"
        assert rel["distance"] == "far"

    def test_separated_is_opaque_to_sight_and_scent_and_an_ordinary_voice(self):
        rel = sp.spatial_rel({"rooms": {"a": {}, "b": {}}}, "a", "b")
        assert sp.sight_level(rel) == "none"
        assert sp.scent_level(rel) == "none"
        assert sp.hear_level(rel, "normal") == "none"

    def test_a_shout_still_crosses_separated_and_that_is_the_leak(self):
        """`world/spatial_senses.py:866-867`:

            if barrier in ("wall", "separated"):
                return "fragment" if volume == "shout" else "none"

        Correct for two rooms in one building with no mapped hallway
        between them, which is what `separated` means today. Fused across
        two bubbles it says a shout on the bridge reaches a shuttle a
        light-year off. This test records the fact; the obligation it
        creates is `test_a_shout_does_not_cross_a_couple` below.
        """
        rel = sp.spatial_rel({"rooms": {"a": {}, "b": {}}}, "a", "b")
        assert sp.hear_level(rel, "shout") == "fragment"


class TestWhatASplitDoesToAChannel:
    def test_a_room_endpoint_channel_now_survives_into_the_away_frame(
            self, temp_db):
        """REVERSED 2026-09-17, and the reversal is the point.

        This asserted the opposite, on the ground that `perform_split` gave
        the child only the away-zoned and unzoned rooms -- so the parent's
        room was absent from the child's `rooms`, and `normalize_scene_comms`
        pruned any channel naming it, "a channel to a room nobody can stand in
        is not a channel".

        A split now partitions BODIES AND NOT THE MAP: the child gets the same
        rooms the parent has, exactly as the parent has always kept the rooms
        the child took. The asymmetry had no argument behind it and one large
        consequence -- an away frame could never gain a room, so a companion
        split off with two of them walked toward a watermill that did not
        exist in her world for four beats running (Aldermill, 2026-09-17).

        Keeping the installation is right on its own terms too: an intercom
        between two rooms is a real thing in the world, and deleting it from
        the away party's copy was the engine forgetting a wall fitting because
        somebody walked out of the room. A map is not a perception -- what a
        channel DELIVERS is still decided by where the bodies stand, and the
        split does partition those.
        """
        b = _two_bubbles(temp_db)
        chat_id, child = b["chat_id"], b["child"]

        child_scene = wget_for_frame(chat_id, "scene", child, {})
        assert "bridge" in child_scene["rooms"], "the map is the world's"

        sp.apply_comms_ops(child_scene, [{
            "id": "intercom", "rooms": ["bridge", "shuttle"]}])
        sp.normalize_scene_comms(child_scene)
        assert "intercom" in child_scene["comms"]
        # ...and it carries nothing by itself: nobody on the far end is in
        # this frame to speak into it.
        assert sp.room_of(child_scene, "The Stranger") is None

    def test_a_carried_channel_survives_the_split_in_both_frames(self, temp_db):
        """A handset names bodies, not rooms, so `normalize_scene_comms`
        keeps it on both sides -- it is the one channel shape that is
        even expressible across a split."""
        b = _two_bubbles(temp_db)
        chat_id, child = b["chat_id"], b["child"]
        for frame_id in (None, child):
            scene = wget_for_frame(chat_id, "scene", frame_id, {})
            sp.normalize_scene_comms(scene)
            assert "handset" in scene["comms"]
            assert scene["comms"]["handset"]["carriers"] == [
                "The Stranger", "Bob"]


class TestMemoryIsFrameGatedToday:
    """The baseline the couple must not move.

    Worth stating explicitly because it is easy to get backwards:
    `memories` DOES carry a `frame_id` column (core/db.py:621, added by
    the v10->v11 migration at :1225), and `visible_memory_rows`
    (mind/memory_read.py:96-98) filters every row through
    `frames.is_memory_visible`. Memory is frame-gated, and the gate is
    live on the ordinary read path. So a couple's memory obligation is
    not "do not add gating" -- it is "do not move the gate", which is
    what the assertions here pin down.
    """

    def test_a_post_split_parent_memory_is_invisible_from_the_child(
            self, temp_db):
        b = _two_bubbles(temp_db)
        chat_id, child, nova = b["chat_id"], b["child"], b["nova"]
        _add_memory_row(temp_db, chat_id, nova, turn_idx=SPLIT_TURN + 1,
                        frame_id=None, content="the bridge went dark")

        rows = visible_memory_rows(chat_id, nova, before_turn_idx=None,
                                   viewer_frame_id=child,
                                   include_archived=False)
        assert rows == []

    def test_a_child_memory_is_invisible_from_the_parent(self, temp_db):
        b = _two_bubbles(temp_db)
        chat_id, child, astra = b["chat_id"], b["child"], b["astra"]
        _add_memory_row(temp_db, chat_id, astra, turn_idx=SPLIT_TURN + 1,
                        frame_id=child, content="the shuttle undocked")

        rows = visible_memory_rows(chat_id, astra, before_turn_idx=None,
                                   viewer_frame_id=None,
                                   include_archived=False)
        assert rows == []

    def test_shared_history_from_before_the_split_stays_visible(self, temp_db):
        b = _two_bubbles(temp_db)
        chat_id, child, nova = b["chat_id"], b["child"], b["nova"]
        _add_memory_row(temp_db, chat_id, nova, turn_idx=SPLIT_TURN - 1,
                        frame_id=None, content="we boarded together")

        rows = visible_memory_rows(chat_id, nova, before_turn_idx=None,
                                   viewer_frame_id=child,
                                   include_archived=False)
        assert len(rows) == 1


class TestTheChannelPredicateItself:
    """`detect_couple` rests entirely on `comms_link` answering. These
    are the answers it will be resting on."""

    def _radio_scene(self):
        scene = {
            "rooms": {"bridge": {"name": "Bridge", "adjacent": []},
                      "shuttle": {"name": "Shuttle", "adjacent": []}},
            "positions": {"The Stranger": "bridge", "Bob": "shuttle"},
            "comms": {},
        }
        sp.apply_comms_ops(scene, [{
            "id": "handset", "name": "the handset",
            "carriers": ["The Stranger", "Bob"]}])
        return scene

    def test_an_open_channel_answers_in_both_directions(self):
        scene = self._radio_scene()
        assert sp.comms_link(scene, "bridge", "shuttle",
                             speaker_name="The Stranger", observer_name="Bob")
        assert sp.comms_link(scene, "shuttle", "bridge",
                             speaker_name="Bob", observer_name="The Stranger")

    def test_a_closed_channel_stops_delivering(self):
        scene = self._radio_scene()
        sp.apply_comms_ops(scene, [{"id": "handset", "op": "close"}])
        assert sp.comms_link(scene, "bridge", "shuttle",
                             speaker_name="The Stranger",
                             observer_name="Bob") is None

    def test_a_room_channel_to_a_vanished_room_delivers_until_renormalised(
            self):
        """Measured, not assumed.

        `comms_link` never checks that a channel's rooms still exist --
        the prune lives in `normalize_scene_comms`, which runs once rooms
        have settled. So any code that mutates `rooms` and then asks the
        channel a question before renormalising gets a voice delivered
        into a room that is gone. A couple mutates `rooms` twice, on open
        and on close; this is the obligation that creates.
        """
        scene = {
            "rooms": {"bridge": {"adjacent": []}, "shuttle": {"adjacent": []}},
            "positions": {"The Stranger": "bridge", "Bob": "shuttle"},
            "comms": {},
        }
        sp.apply_comms_ops(scene, [{
            "id": "intercom", "rooms": ["bridge", "shuttle"]}])
        del scene["rooms"]["shuttle"]

        assert sp.comms_link(scene, "bridge", "shuttle") is not None, (
            "today the dead room still carries a voice")
        sp.normalize_scene_comms(scene)
        assert sp.comms_link(scene, "bridge", "shuttle") is None

    def test_a_carried_channel_does_not_answer_for_a_body_that_is_not_here(
            self):
        scene = {
            "rooms": {"bridge": {"adjacent": []}},
            "positions": {"The Stranger": "bridge"},
            "comms": {},
        }
        sp.apply_comms_ops(scene, [{
            "id": "handset", "carriers": ["The Stranger", "Bob"]}])
        assert sp.comms_link(scene, "bridge", sp.room_of(scene, "Bob"),
                             speaker_name="The Stranger",
                             observer_name="Bob") is None


# =====================================================================
# Half two: what a couple must do. The specification.
# =====================================================================


class TestTheCoupleFrameItself:
    def test_a_couple_frame_is_a_kind_of_its_own(self, temp_db):
        chat_id = _make_chat(temp_db)
        couple = create_frame(chat_id, label="Couple", ordinal=0,
                              kind="couple", parent_frame_id=None,
                              split_turn_idx=9)
        assert get_frame(couple)["kind"] == "couple"

    @needs_couple
    def test_a_couple_never_sets_merged_turn_idx(self, temp_db):
        """The single most load-bearing assertion in this file.

        `qi("UPDATE frames SET merged_turn_idx=?...")` at
        world/spatial_frames.py:1050 is the only writer of that column in
        the engine, there is no un-merge, and `merged_turn_idx IS NULL`
        is the entire condition in core/frames.py:145-176 that keeps the
        two sides incomparable. Setting it hands each side the other's
        whole post-split ledger, permanently. A radio must not be able to
        do that.
        """
        b = _two_bubbles(temp_db)
        chat_id, child = b["chat_id"], b["child"]
        assert get_frame(child)["merged_turn_idx"] is None

        couple = _open_couple(chat_id, None, child, turn_idx=9)
        assert get_frame(child)["merged_turn_idx"] is None, (
            "opening a channel is not a reunion")
        _close_couple(chat_id, couple, turn_idx=10)
        assert get_frame(child)["merged_turn_idx"] is None


class TestPhysicalSeparationSurvives:
    @needs_couple
    def test_positions_rooms_and_contacts_are_unchanged_by_a_couple(
            self, temp_db):
        b = _two_bubbles(temp_db)
        chat_id, child = b["chat_id"], b["child"]

        before = {fid: wget_for_frame(chat_id, "scene", fid, {})
                  for fid in (None, child)}

        couple = _open_couple(chat_id, None, child, turn_idx=9)
        _close_couple(chat_id, couple, turn_idx=10)

        after = {fid: wget_for_frame(chat_id, "scene", fid, {})
                 for fid in (None, child)}

        for fid in (None, child):
            assert after[fid]["positions"] == before[fid]["positions"]
            assert set(after[fid]["rooms"]) == set(before[fid]["rooms"])
            assert after[fid].get("contacts") == before[fid].get("contacts")

    @needs_couple
    @needs_couple
    def test_no_body_crosses_and_the_couple_mints_no_room(self, temp_db):
        """Stated separately from the round-trip because a couple that added
        the same thing to both sides on open and removed it from both on close
        would pass the round-trip and still have put a body somewhere it never
        went.

        The ROOM half was "the child does not have the bridge" until
        2026-09-17, which is no longer a fact about anything: a split
        partitions bodies and not the map, so both sides hold the whole map
        before the couple opens. What this test is for is unchanged -- the
        couple moves no BODY, and adds no room to either side that was not
        already there.
        """
        b = _two_bubbles(temp_db)
        chat_id, child = b["chat_id"], b["child"]
        before_rooms = {fid: set((wget_for_frame(chat_id, "scene", fid, {})
                                  .get("rooms") or {}))
                        for fid in (None, child)}

        couple = _open_couple(chat_id, None, child, turn_idx=9)

        parent_scene = wget_for_frame(chat_id, "scene", None, {})
        child_scene = wget_for_frame(chat_id, "scene", child, {})
        assert "Bob" not in parent_scene["positions"]
        assert "Astra" not in parent_scene["positions"]
        assert "The Stranger" not in child_scene["positions"]
        assert "Nova" not in child_scene["positions"]
        assert set(child_scene["rooms"]) == before_rooms[child]
        assert set(parent_scene["rooms"]) == before_rooms[None]

        _close_couple(chat_id, couple, turn_idx=10)

    def test_a_contact_never_names_a_body_from_the_other_side(self, temp_db):
        b = _two_bubbles(temp_db)
        chat_id, child = b["chat_id"], b["child"]

        couple = _open_couple(chat_id, None, child, turn_idx=9)
        _close_couple(chat_id, couple, turn_idx=10)

        parent_bodies = {"The Stranger", "Nova"}
        child_bodies = {"Bob", "Astra"}
        for fid, own, other in ((None, parent_bodies, child_bodies),
                                (child, child_bodies, parent_bodies)):
            contacts = (wget_for_frame(chat_id, "scene", fid, {})
                        .get("contacts") or [])
            # Both halves, or this passes for a couple that simply deleted
            # every contact on the way through -- which is a mind concluding
            # LESS, the one direction a firewall guard is never allowed to
            # fail in.
            assert len(contacts) == 1, fid
            for contact in contacts:
                assert contact["actor"] in own
                assert contact["target"] in own
                assert contact["actor"] not in other
                assert contact["target"] not in other

    @needs_couple
    def test_a_shout_does_not_cross_a_couple(self, temp_db):
        """The one leak naive fusion introduces, and it must be closed
        explicitly rather than inherited.

        Two rooms fused into one scene with no edge between them report
        `separated`, and `hear_level` gives `separated` a shout as a
        `fragment` (world/spatial_senses.py:866-867). Correct for two
        rooms in one building; wrong for two bubbles. A couple carries a
        voice over the CHANNEL and nothing off it: if this fragment
        arrives, the design's "physical separation for free" claim is
        false and every other sense is only accidentally safe.
        """
        b = _two_bubbles(temp_db)
        chat_id, child = b["chat_id"], b["child"]

        couple = _open_couple(chat_id, None, child, turn_idx=9)
        fused = wget_for_frame(chat_id, "scene", couple, {})

        # Both bodies must actually BE in the fused view first, or every
        # assertion below is answered by two Nones and means nothing. This
        # is also the positive half of the design's claim: the couple frame
        # is where a coupled beat runs, so both parties are in its scene.
        bob_room = sp.room_of(fused, "Bob")
        stranger_room = sp.room_of(fused, "The Stranger")
        assert bob_room and stranger_room and bob_room != stranger_room

        rel = sp.spatial_rel(fused, bob_room, stranger_room)
        assert sp.sight_level(rel) == "none"
        assert sp.scent_level(rel) == "none"
        assert sp.hear_level(rel, "normal") == "none"
        assert sp.hear_level(rel, "shout") == "none", (
            "a shout on the bridge must not reach the shuttle")

        _close_couple(chat_id, couple, turn_idx=10)


class TestTheCastPartitionSurvives:
    @needs_couple
    def test_the_cast_partition_is_identical_before_and_after(self, temp_db):
        b = _two_bubbles(temp_db)
        chat_id, child = b["chat_id"], b["child"]

        before = {fid: {r["id"] for r in active_cast(chat_id, fid)}
                  for fid in (None, child)}
        assert before[None] == {b["nova"]}
        assert before[child] == {b["astra"]}

        couple = _open_couple(chat_id, None, child, turn_idx=9)
        _close_couple(chat_id, couple, turn_idx=10)

        after = {fid: {r["id"] for r in active_cast(chat_id, fid)}
                 for fid in (None, child)}
        assert after == before

    @needs_couple
    def test_a_persona_is_returned_to_the_frame_it_was_stationed_in(
            self, temp_db):
        """`perform_merge` moves every persona to the parent
        (world/spatial_frames.py:1046-1049). A couple must not: Bob is
        playing in the away bubble and is still playing there when the
        call ends."""
        b = _two_bubbles(temp_db)
        chat_id, child, bob = b["chat_id"], b["child"], b["bob_persona"]

        def station():
            return temp_db.q(
                "SELECT frame_id FROM chat_personas WHERE chat_id=? AND "
                "persona_id=?", (chat_id, bob), one=True)["frame_id"]

        assert station() == child
        couple = _open_couple(chat_id, None, child, turn_idx=9)
        _close_couple(chat_id, couple, turn_idx=10)
        assert station() == child


class TestMemoryVisibilityIsUnchanged:
    """Written against the LIVE gate, not against "no gating happens".

    Memory is frame-scoped today (see TestMemoryIsFrameGatedToday), so
    these assertions read `visible_memory_rows` and `is_memory_visible`
    directly. That is deliberate: if someone later changes how memory is
    frame-scoped and gets the couple wrong -- stamping a coupled beat's
    memories with the couple frame, or letting the couple's own frame row
    satisfy the ordinal rule -- these fail, because they compare the
    gate's actual answers across the couple rather than asserting the
    absence of a filter.
    """

    def _matrix(self, chat_id, char_ids, frame_ids):
        answers = {}
        for char_id in char_ids:
            for memory_frame in frame_ids:
                for viewer_frame in frame_ids:
                    for turn_idx in (SPLIT_TURN - 1, SPLIT_TURN + 1, None):
                        answers[(char_id, memory_frame, viewer_frame,
                                 turn_idx)] = is_memory_visible(
                            char_id, memory_frame, viewer_frame, turn_idx)
        return answers

    @needs_couple
    def test_every_visibility_answer_is_identical_before_and_after(
            self, temp_db):
        b = _two_bubbles(temp_db)
        chat_id, child = b["chat_id"], b["child"]
        chars = (b["nova"], b["astra"])

        before = self._matrix(chat_id, chars, (None, child))
        couple = _open_couple(chat_id, None, child, turn_idx=9)
        during = self._matrix(chat_id, chars, (None, child))
        _close_couple(chat_id, couple, turn_idx=10)
        after = self._matrix(chat_id, chars, (None, child))

        assert during == before, "opening a channel is not a reunion"
        assert after == before

    @needs_couple
    def test_the_rows_a_mind_may_read_do_not_change(self, temp_db):
        """The seam, not the predicate. `visible_memory_rows` is the only
        way a mind gets rows (mind/memory_read.py:51), so this is the
        assertion that would actually catch a leak reaching a prompt."""
        b = _two_bubbles(temp_db)
        chat_id, child = b["chat_id"], b["child"]
        nova, astra = b["nova"], b["astra"]

        _add_memory_row(temp_db, chat_id, nova, turn_idx=SPLIT_TURN - 1,
                        frame_id=None, content="we boarded together")
        _add_memory_row(temp_db, chat_id, nova, turn_idx=SPLIT_TURN + 1,
                        frame_id=None, content="the bridge went dark")
        _add_memory_row(temp_db, chat_id, astra, turn_idx=SPLIT_TURN + 1,
                        frame_id=child, content="the shuttle undocked")

        def ids(char_id, viewer_frame):
            return sorted(r["id"] for r in visible_memory_rows(
                chat_id, char_id, before_turn_idx=None,
                viewer_frame_id=viewer_frame, include_archived=False))

        before = {(c, f): ids(c, f)
                  for c in (nova, astra) for f in (None, child)}
        couple = _open_couple(chat_id, None, child, turn_idx=9)
        during = {(c, f): ids(c, f)
                  for c in (nova, astra) for f in (None, child)}
        _close_couple(chat_id, couple, turn_idx=10)
        after = {(c, f): ids(c, f)
                 for c in (nova, astra) for f in (None, child)}

        assert during == before
        assert after == before

    @needs_couple
    def test_a_coupled_beat_stamps_each_memory_with_its_own_member_frame(
            self, temp_db):
        """The seam that makes the whole design work, asserted rather than
        assumed: `commit_memory_write` already takes `frame_id`
        explicitly (persist/commit_memory_write.py:44, 108, 135, 144), so
        a beat that RUNS in the couple frame can still stamp each
        character's memory with the member frame it belongs to. If a
        couple frame id ever lands in this column, the two ledgers have a
        shared era and the incomparability rule has nothing to bite on.
        """
        b = _two_bubbles(temp_db)
        chat_id, child = b["chat_id"], b["child"]

        couple = _open_couple(chat_id, None, child, turn_idx=9)
        _add_memory_row(temp_db, chat_id, b["nova"], turn_idx=9,
                        frame_id=None, content="a voice on the handset")
        _add_memory_row(temp_db, chat_id, b["astra"], turn_idx=9,
                        frame_id=child, content="Bob answered it")
        _close_couple(chat_id, couple, turn_idx=10)

        stamped = {r["frame_id"] for r in temp_db.q(
            "SELECT frame_id FROM memories WHERE chat_id=?", (chat_id,))}
        assert couple not in stamped
        assert stamped <= {None, child}

    @needs_couple
    def test_a_voice_on_the_channel_does_not_make_the_other_side_visible(
            self, temp_db):
        """Restated from the other end, because this is the failure the
        whole design exists to refuse: after a call, a native of the
        parent still cannot read one line the away party formed while
        they were apart."""
        b = _two_bubbles(temp_db)
        chat_id, child, astra = b["chat_id"], b["child"], b["astra"]

        couple = _open_couple(chat_id, None, child, turn_idx=9)
        _add_memory_row(temp_db, chat_id, astra, turn_idx=9, frame_id=child,
                        content="what the shuttle actually found")
        _close_couple(chat_id, couple, turn_idx=10)

        assert visible_memory_rows(chat_id, astra, before_turn_idx=None,
                                   viewer_frame_id=None,
                                   include_archived=False) == []


class TestTheCloseIsTotal:
    @needs_couple
    def test_every_frame_scoped_key_round_trips(self, temp_db):
        """The assertion `perform_merge` could never pass.

        Merge lifts two keys off the child scene (world/spatial_frames.py:
        1036-1041) and drops the rest -- attire, entities, overlays,
        poses, orientation, crossings, comms, and every key outside the
        seven `perform_split` seeds. A couple opens and closes repeatedly
        over one conversation, so anything it drops is dropped again per
        cycle. Iterating `FRAME_SCOPED_WORLD_KEYS` rather than a literal
        list is the point: a key added later is covered without anyone
        remembering to come back here.
        """
        b = _two_bubbles(temp_db)
        chat_id, child = b["chat_id"], b["child"]
        chars = (b["nova"], b["astra"])

        _seed_the_keys_perform_split_does_not(chat_id, None, "parent")
        _seed_the_keys_perform_split_does_not(chat_id, child, "child")

        before = {fid: _frame_scoped_snapshot(chat_id, fid, chars)
                  for fid in (None, child)}

        couple = _open_couple(chat_id, None, child, turn_idx=9)
        _close_couple(chat_id, couple, turn_idx=10)

        after = {fid: _frame_scoped_snapshot(chat_id, fid, chars)
                 for fid in (None, child)}

        for fid in (None, child):
            _assert_nothing_lost(after[fid], before[fid], label=f"{fid}: ")

    @needs_couple
    def test_the_couple_frame_is_retired_and_holds_nothing(self, temp_db):
        """A live couple frame left behind is a third scene that
        `detect_split`/`detect_merge` will iterate and that a later
        checkpoint will snapshot."""
        b = _two_bubbles(temp_db)
        chat_id, child = b["chat_id"], b["child"]

        couple = _open_couple(chat_id, None, child, turn_idx=9)
        _close_couple(chat_id, couple, turn_idx=10)

        assert wget_for_frame(chat_id, "scene", couple, None) in (None, {})
        assert not temp_db.q(
            "SELECT 1 FROM chat_personas WHERE chat_id=? AND frame_id=?",
            (chat_id, couple))

    @needs_couple
    def test_repeated_couples_lose_nothing(self, temp_db):
        """A conversation is many opens and closes. Per-cycle loss is
        invisible on the first cycle and total by the tenth."""
        b = _two_bubbles(temp_db)
        chat_id, child = b["chat_id"], b["child"]
        chars = (b["nova"], b["astra"])

        _seed_the_keys_perform_split_does_not(chat_id, None, "parent")
        _seed_the_keys_perform_split_does_not(chat_id, child, "child")
        before = {fid: _frame_scoped_snapshot(chat_id, fid, chars)
                  for fid in (None, child)}

        for turn_idx in range(9, 19, 2):
            couple = _open_couple(chat_id, None, child, turn_idx=turn_idx)
            _close_couple(chat_id, couple, turn_idx=turn_idx + 1)

        after = {fid: _frame_scoped_snapshot(chat_id, fid, chars)
                 for fid in (None, child)}
        for fid in (None, child):
            _assert_nothing_lost(after[fid], before[fid], label=f"{fid}: ")


class TestWhenACoupleMayNotOpen:
    @needs_couple
    def test_a_live_channel_is_the_whole_predicate(self, temp_db):
        b = _two_bubbles(temp_db)
        chat_id, child = b["chat_id"], b["child"]
        assert _detect_couple(chat_id, child) == (None, child)

    @needs_couple
    def test_a_closed_channel_does_not_couple(self, temp_db):
        b = _two_bubbles(temp_db)
        chat_id, child = b["chat_id"], b["child"]
        for fid in (None, child):
            scene = wget_for_frame(chat_id, "scene", fid, {})
            sp.apply_comms_ops(scene, [{"id": "handset", "op": "close"}])
            wset_for_frame(chat_id, "scene", scene, fid)
        assert _detect_couple(chat_id, child) is None

    @needs_couple
    def test_no_channel_at_all_does_not_couple(self, temp_db):
        b = _two_bubbles(temp_db)
        chat_id, child = b["chat_id"], b["child"]
        for fid in (None, child):
            scene = wget_for_frame(chat_id, "scene", fid, {})
            sp.apply_comms_ops(scene, [{"id": "handset", "op": "remove"}])
            wset_for_frame(chat_id, "scene", scene, fid)
        assert _detect_couple(chat_id, child) is None

    @needs_couple
    def test_closing_the_channel_closes_an_open_couple(self, temp_db):
        """Liveness is a fact about the world, not a mode the couple
        latches. `live` is a switch (world/spatial_senses.py:246-250) and
        somebody keying it off must end the fusion on that beat, or the
        two scenes stay one for as long as nobody notices."""
        b = _two_bubbles(temp_db)
        chat_id, child = b["chat_id"], b["child"]

        couple = _open_couple(chat_id, None, child, turn_idx=9)
        fused = wget_for_frame(chat_id, "scene", couple, {})
        sp.apply_comms_ops(fused, [{"id": "handset", "op": "close"}])
        wset_for_frame(chat_id, "scene", fused, couple)

        assert _detect_couple(chat_id, couple) is None
        _close_couple(chat_id, couple, turn_idx=10)
        assert get_frame(child)["merged_turn_idx"] is None

    @needs_couple
    def test_a_couple_does_not_open_on_a_room_id_collision(self, temp_db):
        """Fail closed, because `{**parent, **child}` cannot be right
        here. The two id spaces diverge independently after a split --
        each side may mint a room called `bridge` -- and a dict merge
        silently prefers one side's version, so a body would find itself
        standing in the other party's room without moving.
        """
        b = _two_bubbles(temp_db)
        chat_id, child = b["chat_id"], b["child"]

        child_scene = wget_for_frame(chat_id, "scene", child, {})
        child_scene["rooms"]["bridge"] = {"name": "The shuttle's own bridge",
                                          "adjacent": []}
        child_scene["positions"]["Astra"] = "bridge"
        wset_for_frame(chat_id, "scene", child_scene, child)

        assert _detect_couple(chat_id, child) is None

    @needs_couple
    def test_a_couple_does_not_open_to_a_body_with_no_recorded_position(
            self, temp_db):
        """The ghost, from the detector's end.

        `test_a_carried_channel_does_not_answer_for_a_body_that_is_not_here`
        shows `comms_link` answering for a carrier who is in no scene at
        all. `detect_couple` is "couple iff comms_link answers", so
        without that fix it couples a bubble to a body that does not
        exist -- and materialises a fused frame around nobody.
        """
        b = _two_bubbles(temp_db)
        chat_id, child = b["chat_id"], b["child"]

        for fid in (None, child):
            scene = wget_for_frame(chat_id, "scene", fid, {})
            sp.apply_comms_ops(scene, [{
                "id": "handset", "carriers": ["The Stranger", "Nobody"]}])
            wset_for_frame(chat_id, "scene", scene, fid)

        assert _detect_couple(chat_id, child) is None

    @needs_couple
    def test_a_couple_is_refused_while_a_paradox_is_active(self, temp_db):
        """Same rule `detect_split` already carries at
        world/spatial_frames.py:781-782: these two mechanics must not
        cross."""
        from world import paradox

        b = _two_bubbles(temp_db)
        chat_id, child = b["chat_id"], b["child"]
        paradox.add_fixed_point(chat_id, entity_id="pete", frame_id=None,
                                required_exists=True, label="x")
        wset(chat_id, "paradoxes", {"present": {
            "anchor_id": 1, "label": "x", "frame_id": None,
            "epicenter_room": "bridge", "started_clock_seconds": 0,
            "severity": 0.0, "stage": 0, "mode": "hazard",
            "consumed": {"rooms": [], "entities": []}}})

        assert _detect_couple(chat_id, None) is None
