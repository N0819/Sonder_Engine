"""A live channel's far end is a room the beat attends to.

`comms_link` answers whether a voice ARRIVES, which is enough for the person
hearing it and not enough for the person ANSWERING. Every gate that decides
who may answer reads where bodies STAND -- `_contextual_rooms` builds the
payload from occupied rooms, `demand_reaches` and `address_reaches` ask the
ordinary hearing model -- and a room across a radio is not a room across a
doorway. So a call went out and nothing came back: the Director never saw the
far room, could not address anybody in it, and a CHARTER presence, which has
no cast row to be named a reactor by, could not be reached at all.

Three rules, and the third is the firewall one:

  * TWO-WAY ONLY. A broadcast reaches its receivers and hears nothing back
    (`comms_link` is directional and says so), so a public address promotes
    nobody -- there is nobody on the other end who can reply.
  * CAPPED, and the cap is named: `COMMS_ATTENDED_ROOMS`. An attended room is
    a room the payload carries and whose bodies may answer, and a registered
    character answering is a full character call on every beat the channel
    stays live.
  * ATTENDING IS NOT DISCLOSING. The channel carries the voice and nothing
    else, exactly as `line_hear_level`'s comm path does. What the far end
    perceives is theirs; only what they say comes back.
"""

from __future__ import annotations

from agents.common import _contextual_rooms
from persist.commit import address_reaches, demand_reaches
from world.spatial import COMMS_ATTENDED_ROOMS, comms_reachable_rooms


def _scene(*, live=True, mode="duplex", carriers=("Reya",), rooms=None):
    return {
        "rooms": {
            "bunker": {"name": "The Bunker", "adjacent": []},
            "surface": {"name": "The Surface", "adjacent": []},
            "vault": {"name": "The Vault", "adjacent": []},
        },
        "positions": {"Kestrel": "bunker", "Reya": "surface"},
        "entities": {}, "attire": {}, "overlays": {},
        "comms": {"radio": {"live": live, "mode": mode,
                            "carriers": list(carriers),
                            "rooms": list(rooms or ["bunker", "surface"])}},
    }


def test_a_live_two_way_channel_names_the_room_at_its_far_end():
    assert comms_reachable_rooms(_scene(), "bunker") == ["surface"]
    assert comms_reachable_rooms(_scene(), "surface") == ["bunker"]
    # A room the channel does not reach is not reached.
    assert "vault" not in comms_reachable_rooms(_scene(), "bunker")


def test_a_dead_channel_and_a_broadcast_promote_nobody():
    """A broadcast reaches its receivers and hears nothing back, so there is
    nobody on the other end who can answer -- which is the whole of what
    being attended to is for."""
    assert comms_reachable_rooms(_scene(live=False), "bunker") == []
    assert comms_reachable_rooms(
        _scene(mode="broadcast", rooms=["surface"]), "bunker") == []


def test_the_cap_is_named_and_holds():
    scene = _scene(rooms=["bunker", "surface", "vault", "annex"])
    scene["rooms"]["annex"] = {"name": "The Annex", "adjacent": []}
    reached = comms_reachable_rooms(scene, "bunker")
    assert len(reached) <= COMMS_ATTENDED_ROOMS
    assert comms_reachable_rooms(scene, "bunker", cap=1) == reached[:1]
    assert comms_reachable_rooms(scene, "bunker", cap=0) == []


def test_the_payload_attends_to_the_room_at_the_far_end():
    """The Director could not see the room, so it could not address anybody
    standing in it."""
    scene = _scene()
    rooms = _contextual_rooms(scene, [], "bunker")
    assert "surface" in rooms and "bunker" in rooms
    # ...and with no channel it does not, so an ordinary scene is unchanged.
    quiet = _scene(live=False)
    assert "surface" not in _contextual_rooms(quiet, [], "bunker")


def test_a_body_on_the_far_end_can_be_addressed_and_owed_a_reply():
    """`demand_reaches` and `address_reaches` both read the ordinary hearing
    model, and a room across a radio is not a room across a doorway. A
    charter presence has no other way to be reached: it has no cast row, so
    it can never be named a reactor."""
    scene = _scene()
    assert demand_reaches(scene, "surface", ["bunker"], aimed=True)
    assert address_reaches(scene, "Reya", "surface", "Kestrel", ["bunker"])
    # The complement: no channel, no reach.
    quiet = _scene(live=False)
    assert not demand_reaches(quiet, "surface", ["bunker"], aimed=True)
    assert not address_reaches(quiet, "Reya", "surface", "Kestrel", ["bunker"])


def test_attending_to_a_room_discloses_nothing_of_what_is_in_it():
    """The channel carries the voice and nothing else. A body standing in the
    far room is not made visible by the call -- `visual_level_between` is not
    consulted here and does not change."""
    from world.spatial import visual_level_between

    scene = _scene()
    scene["positions"]["Halla"] = "surface"
    assert visual_level_between(scene, "Kestrel", "Halla") == "none"
    assert visual_level_between(scene, "Kestrel", "Reya") == "none"
