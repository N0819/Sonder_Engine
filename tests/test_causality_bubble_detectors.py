"""The causality-bubble detectors, against constructed scenes.

`world/spatial_bubbles.py` holds three pure decisions and nothing else. The
tests that matter here are the ones where the detector must NOT fire: a
detector that says yes too often does not produce a slightly-wrong scene, it
produces a frame split that `perform_merge` cannot losslessly undo
(spatial_frames.py:1036-1041 lifts two keys off the child and drops the rest)
and that `core/frames.py:145-176` uses to gate memory visibility. So the
refusals are tested one at a time, each with a sibling case proving the
detector still fires when only that refusal's condition is lifted -- otherwise
a detector wired shut would pass every negative test in the file.
"""

from __future__ import annotations

import copy
import json
import time

import pytest

from world import spatial_bubbles as bubbles
from world import spatial_frames


# --------------------------------------------------------------- scene fixtures
# --------------------------------------------------------------- scene fixtures

def _radio(**over):
    channel = {"name": "squad radio", "rooms": [], "carriers": [],
               "mode": "duplex", "source": "", "private": False, "live": True}
    channel.update(over)
    return channel


def _one_frame_scene(**over):
    """One unsplit frame, and NOT ONE ZONE IN IT.

    Deliberate: the trigger is range, so the fixture must not be able to pass
    by accident on a declared locale. Four rooms in a line -- the player in
    the tap room, the courier wherever the test puts her. A closed door
    between the tap room and the lane, because a barrier is not what range
    means: `attended_rooms` has no barrier allowlist, and a room behind a shut
    door is still a room the beat may be about.
    """
    scene = {
        "rooms": {
            "tap": {"name": "Tap room",
                    "adjacent": [{"to": "lane", "barrier": "closed_door"}]},
            "lane": {"name": "Mill Lane",
                     "adjacent": [{"to": "tap", "barrier": "closed_door"},
                                  {"to": "road", "barrier": "open"}]},
            "road": {"name": "The north road",
                     "adjacent": [{"to": "lane", "barrier": "open"},
                                  {"to": "landing", "barrier": "open"}]},
            "landing": {"name": "Ferry landing",
                        "adjacent": [{"to": "road", "barrier": "open"}]},
        },
        "positions": {"The Stranger": "tap", "Hinami": "landing"},
        "comms": {},
    }
    scene.update(over)
    return scene


def _side(positions, comms=None, rooms=None):
    return {"rooms": rooms if rooms is not None else {},
            "positions": dict(positions),
            "comms": dict(comms or {})}


def _decide(scene, **over):
    kw = {"party_names": ["The Stranger"], "cast_names": ["Hinami"]}
    kw.update(over)
    return bubbles.bubble_split_decision(scene, **kw)


# ============================================================ 1. bubble split


class TestTheBubbleFires:
    def test_a_character_out_of_the_beats_reach_gets_a_bubble(self):
        assert _decide(_one_frame_scene()) == {
            "kind": "bubble", "characters": ["Hinami"],
            "rooms": ["landing", "road"]}

    def test_no_zone_is_needed_anywhere_which_is_the_whole_point(self):
        # The zone-era trigger required somebody to have LABELLED the away
        # place, and the live Millbrook run (2026-09-17, gemini-3.8-flash)
        # is what that cost: a courier walked out on an errand and the engine
        # could not tell she had gone, because the road carried no zone.
        scene = _one_frame_scene()
        assert not any("zone" in r for r in scene["rooms"].values())
        assert _decide(scene) is not None
        assert "zone" not in bubbles.bubble_split_decision.__code__.co_varnames

    def test_no_persona_is_needed_either(self):
        # `detect_split`'s second refusal is "a chat with no attached extra
        # personas (nobody to split FROM)". The bubble detector takes no
        # persona argument at all, so the case that refusal excludes is
        # exactly the case this one is for.
        assert "persona" not in bubbles.bubble_split_decision.__code__.co_varnames

    def test_the_frame_she_gets_is_walkable(self):
        # A frame holding only the room she stands in is a sealed box, and
        # the movement she is in the middle of is what the bubble exists to
        # keep going.
        decision = _decide(_one_frame_scene())
        assert "landing" in decision["rooms"]
        assert "road" in decision["rooms"], "somewhere to walk to"

    def test_two_people_who_walked_off_separately_are_two_threads(self):
        # One frame for both would put them in a room together without
        # either of them moving.
        scene = _one_frame_scene(
            rooms={**_one_frame_scene()["rooms"],
                   "cellar": {"name": "Cellar", "adjacent": []}},
            positions={"The Stranger": "tap", "Hinami": "landing",
                       "Vela": "cellar"},
        )
        decision = bubbles.bubble_split_decision(
            scene, party_names=["The Stranger"],
            cast_names=["Hinami", "Vela"])
        assert decision["characters"] == ["Hinami"]
        assert "cellar" not in decision["rooms"]

    def test_two_who_left_together_are_one_thread(self):
        scene = _one_frame_scene(
            positions={"The Stranger": "tap", "Hinami": "landing",
                       "Vela": "road"})
        decision = bubbles.bubble_split_decision(
            scene, party_names=["The Stranger"],
            cast_names=["Hinami", "Vela"])
        assert decision["characters"] == ["Hinami", "Vela"]

    def test_the_answer_does_not_depend_on_the_callers_list_order(self):
        scene = _one_frame_scene(
            positions={"The Stranger": "tap", "Hinami": "landing",
                       "Vela": "road"})
        one = bubbles.bubble_split_decision(
            scene, party_names=["The Stranger"], cast_names=["Hinami", "Vela"])
        two = bubbles.bubble_split_decision(
            scene, party_names=["The Stranger"], cast_names=["Vela", "Hinami"])
        assert one == two


class TestTheBubbleRefuses:
    """Five refusals, each isolated. Every test here pairs with a fires-case
    above or a lift below, so a permanently-shut detector cannot pass."""

    def test_refuses_a_nested_split(self):
        assert _decide(_one_frame_scene(), frame_is_live_spatial=True) is None

    def test_refuses_during_an_active_paradox(self):
        assert _decide(_one_frame_scene(), paradox_active=True) is None

    def test_refuses_when_the_party_is_nowhere(self):
        # No reference frame: there is no range to be outside of.
        scene = _one_frame_scene(positions={"Hinami": "landing"})
        assert _decide(scene) is None

    def test_refuses_when_there_is_no_party_at_all(self):
        assert _decide(_one_frame_scene(), party_names=[]) is None

    def test_refuses_a_body_the_scene_cannot_place(self):
        # Nowhere is not away: there would be nothing to partition.
        scene = _one_frame_scene(positions={"The Stranger": "tap"})
        assert _decide(scene) is None

    def test_refuses_a_character_in_the_players_own_room(self):
        scene = _one_frame_scene(
            positions={"The Stranger": "tap", "Hinami": "tap"})
        assert _decide(scene) is None

    def test_refuses_a_character_one_room_away(self):
        # THE RULE THAT KEEPS ORDINARY PLAY WHOLE. Someone who stepped into
        # the next room is in the beat -- they are in the Director's payload,
        # which is the same set -- and splitting on mere separation is what
        # `spatial_frames.py`'s docstring refuses.
        scene = _one_frame_scene(
            positions={"The Stranger": "tap", "Hinami": "lane"})
        assert _decide(scene) is None

    def test_a_shut_door_is_not_distance(self):
        # The tap/lane edge is a closed door in every fixture here, and the
        # test above passes through it. Stated separately because a barrier
        # allowlist is the obvious wrong fix for churn.
        scene = _one_frame_scene(
            positions={"The Stranger": "tap", "Hinami": "lane"})
        assert scene["rooms"]["tap"]["adjacent"][0]["barrier"] == "closed_door"
        assert _decide(scene) is None

    def test_refuses_when_a_human_is_out_there_too(self):
        # That is `detect_split`'s case. Firing both would nest a bubble
        # inside a party split, which refusal 1 exists to forbid.
        scene = _one_frame_scene(
            positions={"The Stranger": "tap", "Bob": "landing",
                       "Hinami": "landing"})
        assert _decide(scene, party_names=["The Stranger", "Bob"]) is None

    def test_a_live_channel_holds_it_shut_without_a_clause_for_it(self):
        # THE REFUSAL THAT BECAME STRUCTURAL. A mind answering over a comm
        # channel from another room is already a participant of the unsplit
        # frame, and `attended_rooms` folds a live two-way channel's far end
        # into the range -- so this is reached by construction rather than by
        # a sixth clause remembering to check it.
        scene = _one_frame_scene(comms={"net": _radio(
            carriers=["The Stranger", "Hinami"])})
        assert _decide(scene) is None

    def test_the_channel_refusal_lifts_the_moment_it_is_closed(self):
        # The paired lift: the same scene with `live: False` fires. This is
        # what proves the range keys off LIVENESS and not merely off the
        # channel record existing.
        scene = _one_frame_scene(comms={"net": _radio(
            carriers=["The Stranger", "Hinami"], live=False)})
        assert _decide(scene)["characters"] == ["Hinami"]

    def test_a_one_way_broadcast_does_not_hold_it_shut(self):
        # `comms_reachable_rooms` is TWO-WAY only, and says why: a broadcast
        # reaches its receivers and hears nothing back, so a public address
        # promotes nobody -- there is nobody at the other end who can reply.
        # She is being talked AT, not kept in the beat.
        scene = _one_frame_scene(comms={"pa": _radio(
            rooms=["tap", "landing"], mode="broadcast", source="tap")})
        assert _decide(scene) is not None

    def test_a_channel_to_one_body_does_not_protect_another(self):
        scene = _one_frame_scene(
            rooms={**_one_frame_scene()["rooms"],
                   "cellar": {"name": "Cellar", "adjacent": []}},
            positions={"The Stranger": "tap", "Hinami": "landing",
                       "Vela": "cellar"},
            comms={"net": _radio(carriers=["The Stranger", "Hinami"])},
        )
        decision = bubbles.bubble_split_decision(
            scene, party_names=["The Stranger"],
            cast_names=["Hinami", "Vela"])
        assert decision["characters"] == ["Vela"]


# ================================================================ 2. the couple


class TestFuseComms:
    def test_identical_copies_survive(self):
        a = _side({}, {"net": _radio(carriers=["A", "B"])})
        b = _side({}, {"net": _radio(carriers=["A", "B"])})
        assert set(bubbles.fuse_comms(a, b)) == {"net"}

    def test_silence_on_one_side_is_not_refusal(self):
        # A radio picked up AFTER the split is written into one frame only.
        a = _side({}, {"net": _radio(carriers=["A", "B"])})
        b = _side({}, {})
        assert set(bubbles.fuse_comms(a, b)) == {"net"}

    def test_hanging_up_on_either_side_vetoes(self):
        a = _side({}, {"net": _radio(carriers=["A", "B"])})
        b = _side({}, {"net": _radio(carriers=["A", "B"], live=False)})
        assert bubbles.fuse_comms(a, b) == {}
        assert bubbles.fuse_comms(b, a) == {}

    def test_a_contested_channel_is_no_channel(self):
        a = _side({}, {"net": _radio(carriers=["A", "B"])})
        b = _side({}, {"net": _radio(carriers=["A", "C"])})
        assert bubbles.fuse_comms(a, b) == {}

    def test_does_not_mutate_either_side(self):
        a = _side({}, {"net": _radio(carriers=["A", "B"])})
        b = _side({}, {"net": _radio(carriers=["A", "B"])})
        before = (copy.deepcopy(a), copy.deepcopy(b))
        bubbles.fuse_comms(a, b)
        assert (a, b) == before


class TestTheCoupleOpens:
    def test_a_radio_carried_on_both_sides_couples_the_frames(self):
        chan = _radio(carriers=["The Stranger", "Hinami"])
        a = _side({"The Stranger": "bridge"}, {"net": chan})
        b = _side({"Hinami": "market"}, {"net": chan})
        decision = bubbles.couple_decision(a, ["The Stranger"], b, ["Hinami"])
        assert decision["kind"] == "couple"
        assert decision["channel_id"] == "net"
        assert {decision["speaker"], decision["observer"]} == {
            "The Stranger", "Hinami"}

    def test_a_channel_opened_on_only_one_side_still_couples(self):
        chan = _radio(carriers=["The Stranger", "Hinami"])
        a = _side({"The Stranger": "bridge"}, {"net": chan})
        b = _side({"Hinami": "market"}, {})
        assert bubbles.couple_decision(
            a, ["The Stranger"], b, ["Hinami"])["channel_id"] == "net"

    def test_a_broadcast_couples_in_the_direction_it_transmits(self):
        chan = _radio(rooms=["observation", "cell"], mode="broadcast",
                      source="observation")
        a = _side({"The Stranger": "observation"}, {"pa": chan})
        b = _side({"Hinami": "cell"}, {"pa": chan})
        decision = bubbles.couple_decision(a, ["The Stranger"], b, ["Hinami"])
        assert decision["speaker"] == "The Stranger"
        assert decision["observer"] == "Hinami"


class TestTheCoupleRefuses:
    def _linked(self):
        chan = _radio(carriers=["The Stranger", "Hinami"])
        return (_side({"The Stranger": "bridge"}, {"net": chan}),
                _side({"Hinami": "market"}, {"net": chan}))

    def test_the_linked_pair_is_a_real_couple(self):
        # The control for every refusal below.
        a, b = self._linked()
        assert bubbles.couple_decision(a, ["The Stranger"], b, ["Hinami"])

    def test_refuses_with_no_channel_at_all(self):
        a = _side({"The Stranger": "bridge"})
        b = _side({"Hinami": "market"})
        assert bubbles.couple_decision(
            a, ["The Stranger"], b, ["Hinami"]) is None

    def test_refuses_when_one_side_hung_up(self):
        a, b = self._linked()
        b["comms"]["net"] = _radio(carriers=["The Stranger", "Hinami"],
                                   live=False)
        assert bubbles.couple_decision(
            a, ["The Stranger"], b, ["Hinami"]) is None

    def test_refuses_a_contested_channel(self):
        a, b = self._linked()
        b["comms"]["net"] = _radio(carriers=["The Stranger", "Vela"])
        assert bubbles.couple_decision(
            a, ["The Stranger"], b, ["Hinami"]) is None

    def test_refuses_on_a_colliding_occupied_room_id(self):
        # perform_split hands the child every unzoned room while the parent
        # keeps all of them (spatial_frames.py:860-869), so the two id spaces
        # overlap by construction. A fused `{**a, **b}` would silently pick
        # one side's "cabin" for two people standing in different ones.
        #
        # The COLLIDING room is deliberately neither speaker's. Put the two
        # radio holders in the shared id instead and the test passes with the
        # guard deleted, because `comms_link` declines a same-room pair on its
        # own (spatial_senses.py:317-322) -- which is passing for the wrong
        # reason. The collision here is a third body on each side.
        chan = _radio(carriers=["The Stranger", "Hinami"])
        a = _side({"The Stranger": "bridge", "Vela": "cabin"}, {"net": chan})
        b = _side({"Hinami": "market", "Ito": "cabin"}, {"net": chan})
        assert bubbles.couple_decision(
            a, ["The Stranger"], b, ["Hinami"]) is None
        # The paired lift: move that third body to a room of its own and the
        # very same channel couples the frames.
        b["positions"]["Ito"] = "loft"
        assert bubbles.couple_decision(a, ["The Stranger"], b, ["Hinami"])

    def test_refuses_on_a_colliding_body_name(self):
        chan = _radio(carriers=["The Stranger", "Hinami"])
        a = _side({"The Stranger": "bridge", "guard_1": "bridge"},
                  {"net": chan})
        b = _side({"Hinami": "market", "Guard_1": "market"}, {"net": chan})
        assert bubbles.couple_decision(
            a, ["The Stranger"], b, ["Hinami"]) is None

    def test_refuses_during_an_active_paradox(self):
        a, b = self._linked()
        assert bubbles.couple_decision(
            a, ["The Stranger"], b, ["Hinami"], paradox_active=True) is None

    def test_refuses_a_channel_that_joins_two_bodies_on_the_same_side(self):
        # A radio between two people who are both at home is not a bridge to
        # anywhere; nothing about it crosses the split.
        chan = _radio(carriers=["The Stranger", "Vela"])
        a = _side({"The Stranger": "bridge", "Vela": "galley"}, {"net": chan})
        b = _side({"Hinami": "market"}, {})
        assert bubbles.couple_decision(
            a, ["The Stranger", "Vela"], b, ["Hinami"]) is None

    def test_refuses_when_an_endpoint_body_is_not_placed(self):
        # A carrier the scene cannot position has no room to partition back to.
        chan = _radio(carriers=["The Stranger", "Hinami"])
        a = _side({"The Stranger": "bridge"}, {"net": chan})
        b = _side({}, {"net": chan})
        assert bubbles.couple_decision(
            a, ["The Stranger"], b, ["Hinami"]) is None

    def test_refuses_a_name_that_is_not_a_party_of_either_side(self):
        # The channel is live and crosses, but neither endpoint is one of the
        # frames' own bodies -- so it joins nothing these two frames answer for.
        chan = _radio(carriers=["Courier", "Runner"])
        a = _side({"The Stranger": "bridge", "Courier": "galley"},
                  {"net": chan})
        b = _side({"Hinami": "market", "Runner": "attic"}, {"net": chan})
        assert bubbles.couple_decision(
            a, ["The Stranger"], b, ["Hinami"]) is None
        # ...and naming them makes it a couple, which is what proves the
        # refusal above is about the NAME LISTS and not about the channel.
        assert bubbles.couple_decision(
            a, ["The Stranger", "Courier"], b, ["Hinami", "Runner"])


# ============================================================== 3. the uncouple


def _couple_scene(**over):
    scene = {
        "rooms": {"bridge": {"name": "Bridge"}, "galley": {"name": "Galley"},
                  "market": {"name": "Market"}},
        "positions": {"The Stranger": "bridge", "Hinami": "market"},
        "comms": {"net": _radio(carriers=["The Stranger", "Hinami"])},
    }
    scene.update(over)
    return scene


class TestTheCoupleHolds:
    def test_a_live_channel_keeps_the_couple(self):
        assert bubbles.uncouple_decision(
            _couple_scene(), ["The Stranger"], ["Hinami"]) is None

    def test_a_one_way_broadcast_keeps_the_couple(self):
        scene = _couple_scene(comms={"pa": _radio(
            rooms=["bridge", "market"], mode="broadcast", source="bridge")})
        assert bubbles.uncouple_decision(
            scene, ["The Stranger"], ["Hinami"]) is None

    def test_one_surviving_link_keeps_the_couple_even_as_a_pair_reunites(self):
        # Vela has walked back into the player's room while Ito is still on
        # the radio to Hinami. The couple is not over.
        scene = _couple_scene(
            positions={"The Stranger": "bridge", "Vela": "bridge",
                       "Ito": "galley", "Hinami": "market"},
            comms={"net": _radio(carriers=["Ito", "Hinami"])},
        )
        assert bubbles.uncouple_decision(
            scene, ["The Stranger", "Ito"], ["Vela", "Hinami"]) is None


class TestTheCoupleEnds:
    def test_a_closed_channel_ends_it(self):
        scene = _couple_scene(comms={"net": _radio(
            carriers=["The Stranger", "Hinami"], live=False)})
        assert bubbles.uncouple_decision(
            scene, ["The Stranger"], ["Hinami"]) == {
                "kind": "uncouple", "reason": "channel_closed",
                "shared_room": None, "who": []}

    def test_a_removed_channel_ends_it(self):
        assert bubbles.uncouple_decision(
            _couple_scene(comms={}), ["The Stranger"], ["Hinami"]
        )["reason"] == "channel_closed"

    def test_walking_into_the_same_room_is_a_REUNION_not_a_dropped_call(self):
        # THE test this function exists for. comms_link deliberately answers
        # None for two people in one room (spatial_senses.py:317-322), so the
        # naive negation of couple_decision fires hardest exactly here -- and
        # would partition back into two frames a pair standing face to face.
        scene = _couple_scene(
            positions={"The Stranger": "bridge", "Hinami": "bridge"},
            comms={},
        )
        decision = bubbles.uncouple_decision(
            scene, ["The Stranger"], ["Hinami"])
        assert decision["reason"] == "reunited"
        assert decision["shared_room"] == "bridge"

    def test_reunion_is_reported_even_with_the_radio_still_live(self):
        # Same room, radio never switched off: comms_link still declines, so
        # the reason must not be "channel_closed".
        scene = _couple_scene(
            positions={"The Stranger": "bridge", "Hinami": "bridge"})
        assert bubbles.uncouple_decision(
            scene, ["The Stranger"], ["Hinami"])["reason"] == "reunited"


# ================================================================ purity


class TestNoSideEffects:
    def test_no_detector_mutates_the_scene_it_was_given(self):
        one = _one_frame_scene(comms={"net": _radio(
            carriers=["The Stranger", "Hinami"])})
        a = _side({"The Stranger": "bridge"},
                 {"net": _radio(carriers=["The Stranger", "Hinami"])})
        b = _side({"Hinami": "market"},
                 {"net": _radio(carriers=["The Stranger", "Hinami"])})
        couple = _couple_scene()
        before = copy.deepcopy((one, a, b, couple))

        bubbles.bubble_split_decision(one, party_names=["The Stranger"],
                                      cast_names=["Hinami"])
        bubbles.couple_decision(a, ["The Stranger"], b, ["Hinami"])
        bubbles.uncouple_decision(couple, ["The Stranger"], ["Hinami"])

        assert (one, a, b, couple) == before


# ================================== the read-only gatherer, against a real chat


def _make_chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Test", "", time.time()))


def _attach_char(db, chat_id, name):
    char_id = db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        (name, json.dumps({"identity": {"name": name}}), "{}", time.time()))
    db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
          "VALUES(?,?,'active','{}')", (chat_id, char_id))
    return char_id


class TestDetectBubbleAgainstAChat:
    def test_it_fires_exactly_where_detect_split_refuses(self, temp_db):
        # No personas are attached at all, which is detect_split's second
        # refusal and the entire gap this detector exists to fill -- and no
        # zone is declared anywhere, which is the gap the RANGE trigger
        # closed on 2026-09-17.
        from core.db import wset

        chat_id = _make_chat(temp_db)
        _attach_char(temp_db, chat_id, "Hinami")
        wset(chat_id, "scene", {
            "rooms": {
                "tap": {"name": "Tap", "adjacent": [{"to": "lane", "barrier": "open"}]},
                "lane": {"name": "Lane", "adjacent": [
                    {"to": "tap", "barrier": "open"},
                    {"to": "landing", "barrier": "open"}]},
                "landing": {"name": "Landing", "adjacent": [
                    {"to": "lane", "barrier": "open"}]},
            },
            "positions": {"The Stranger": "tap", "Hinami": "landing"},
            "entities": {}, "attire": {}, "overlays": {}, "comms": {},
        })

        assert spatial_frames.detect_split(chat_id, None, 1) is None
        decision = bubbles.detect_bubble(chat_id, None, 1)
        assert decision["kind"] == "bubble"
        assert decision["characters"] == ["Hinami"]
        assert "landing" in decision["rooms"]

    def test_a_character_in_the_next_room_is_still_in_the_beat(self, temp_db):
        from core.db import wset

        chat_id = _make_chat(temp_db)
        _attach_char(temp_db, chat_id, "Hinami")
        wset(chat_id, "scene", {
            "rooms": {
                "tap": {"name": "Tap", "adjacent": [{"to": "lane", "barrier": "closed_door"}]},
                "lane": {"name": "Lane", "adjacent": [{"to": "tap", "barrier": "closed_door"}]},
            },
            "positions": {"The Stranger": "tap", "Hinami": "lane"},
            "entities": {}, "attire": {}, "overlays": {}, "comms": {},
        })
        assert bubbles.detect_bubble(chat_id, None, 1) is None

    def test_a_live_channel_in_the_stored_scene_holds_it_shut(self, temp_db):
        from core.db import wset

        chat_id = _make_chat(temp_db)
        _attach_char(temp_db, chat_id, "Hinami")
        wset(chat_id, "scene", {
            "rooms": {
                "tap": {"name": "Tap", "adjacent": [{"to": "lane", "barrier": "open"}]},
                "lane": {"name": "Lane", "adjacent": [
                    {"to": "tap", "barrier": "open"},
                    {"to": "landing", "barrier": "open"}]},
                "landing": {"name": "Landing", "adjacent": [
                    {"to": "lane", "barrier": "open"}]},
            },
            "positions": {"The Stranger": "tap", "Hinami": "landing"},
            "entities": {}, "attire": {}, "overlays": {},
            "comms": {"net": _radio(carriers=["The Stranger", "Hinami"])},
        })
        assert bubbles.detect_bubble(chat_id, None, 1) is None

    def test_an_unknown_chat_is_none_not_a_crash(self, temp_db):
        assert bubbles.detect_bubble(999999, None, 1) is None
