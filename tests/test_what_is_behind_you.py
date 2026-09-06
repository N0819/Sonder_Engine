"""What is behind you is not seen, and it is still heard.

`spatial.entity_arc` has always promised exactly this -- "the observer gets
NO NEW VISUAL detail from them (a silent approach or gesture is unseen)
though sound still carries" -- and neither half held. An act reached an
observer on the SIGHT channel alone, so nothing carried the sound: five
bodies at one anchor split into the two facing the actor, who got the beat,
and three facing away, who acted as if it had not happened (multitude,
2026-09-05, PM5).

Three rules, and they are the owner's, given 2026-09-05:

  * You receive only the SOUNDS someone behind you makes -- that something
    moved, and where, never who and never what they were doing. A footstep
    does not carry an identity.
  * A VOICE you already know DOES identify its owner, seen or not. That is
    what ears are for, and gating it on sight was the defect.
  * ...unless somebody is deliberately concealing who they are, which the
    disguise ledger already says and `observer_display_map` already applies.

The blind spot itself is untouched: a body behind you is still absent from
presence, still gives no appearance and no conduct. What it gains is a sound.
"""

from __future__ import annotations

import agents.composer as composer


def _facing_pair(facing="n"):
    """P faces north; Q stands at the south anchor, behind them."""
    return {
        "rooms": {"hall": {"name": "The Hall", "size": "medium",
                           "anchors": {"door": {"desc": "the door", "dir": "n"},
                                       "hearth": {"desc": "the hearth",
                                                  "dir": "s"}},
                           "adjacent": []}},
        "positions": {"P": "hall", "Q": "hall"},
        "stations": {"P": {"at": "door"}, "Q": {"at": "hearth"}},
        "orientation": {"P": {"facing": facing}},
        "poses": {}, "entities": {}, "attire": {},
    }


def _act(scene, *, display="Q"):
    from world.spatial import entity_arc
    assert entity_arc(scene, "P", "Q") == "rear", "fixture is not a blind spot"
    return composer.act_percept(
        scene, {"event_id": "e1", "actor": "Q", "targets": []},
        "P", "Q", {"same_room": True, "barrier": "open"},
        surface="lifts the latch and eases it back",
        display=display, can_see=False, sight="none", order_key=0)


def test_a_body_behind_you_is_heard_moving_and_never_named():
    percept = _act(_facing_pair())
    assert percept is not None, "the beat reached nobody at all"
    assert percept.channel == "hearing"
    assert percept.data.get("unseen") is True
    # Neither who, nor what they were doing.
    assert percept.source_label == ""
    assert "surface" not in percept.data
    line = composer.render_view([percept]).text
    assert "Q" not in line and "latch" not in line
    assert "moves" in line


def test_the_sound_carries_where_it_came_from_when_the_geometry_says():
    """`sound_bearing` answers with the observer's own egocentric sector and
    never guesses; its record carries no room id and no room name, so a
    bearing discloses nothing a body's ears did not.

    The complement is the arc's own fail-open, and it is why this test does
    not try to build a bearing-less blind spot: with no facing and no
    stations `entity_arc` answers None -- nothing is behind you when the
    geometry cannot say where anything is -- so the act is delivered by
    sight as it always was.
    """
    from world.spatial import entity_arc

    placed = _act(_facing_pair())
    line = composer.render_view([placed]).text.strip()
    assert line.endswith(".")
    if placed.data.get("bearing"):
        assert placed.data["bearing"] in line

    bare = {**_facing_pair(), "stations": {}, "orientation": {}}
    assert entity_arc(bare, "P", "Q") != "rear"


def test_a_voice_you_know_identifies_its_owner_unseen():
    """A line from a body behind you, or across a dark room, arrived
    anonymous however well you knew them. Recognition is the question, and
    `observer_display_map` already answers it: a recognised body gets its own
    NAME, a stranger a descriptor."""
    entry = {"speaker": "Q", "text": "It is only me.", "volume": "normal"}
    rel = {"barrier": "closed_door", "same_room": False}
    assert composer.hear_level(rel, "normal") == "fragment"

    known = composer.speech_percept(entry, rel, "P", display="Q",
                                    can_see=False)
    assert known.data["attributed"] is True

    # A stranger's label is not a name, so the voice stays anonymous.
    stranger = composer.speech_percept(
        entry, rel, "P", display="the unfamiliar person", can_see=False)
    assert stranger.data["attributed"] is False


def test_a_disguise_that_conceals_identity_takes_the_voice_with_it():
    """`observer_display_map` applies `disguise_breaks_recognition` on the
    way, so a disguise that MEANS to hide who somebody is hands this function
    a stranger's label and the voice is unattributed. One that only hides
    features hands back the name, and the voice is still theirs."""
    from story.scene import disguise_breaks_recognition

    assert disguise_breaks_recognition([], "P", True) is True
    assert disguise_breaks_recognition([], "P", False) is False
    entry = {"speaker": "Q", "text": "Steady.", "volume": "normal"}
    rel = {"barrier": "closed_door", "same_room": False}
    hidden = composer.speech_percept(
        entry, rel, "P", display="a figure in a long coat", can_see=False)
    assert hidden.data["attributed"] is False
