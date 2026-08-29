"""A contact that names nothing is not a contact, and a whole-body one is.

The distinction this file pins is easy to get backwards, and getting it
backwards breaks containment. An EMPTY part is a positive claim -- the whole
body is what touches -- and it is how an embrace and every containment record
are written (`spatial_containment._WHOLE_BODY_PARTS`). What carries no
information is the CONJUNCTION: both sides whole-body AND the default manner,
between two bodies.

Measured 2026-08-28 over a six-scenario contact experiment run against five
prompt variants: of 51 contact `add` ops, 5 were exactly that shape, every one
with manner "touch", appearing under three different prompts including the
unmodified sheet. Twice, the same beat also carried the correct specific
release beside it.
"""
from __future__ import annotations

from world.spatial import apply_contact_ops


def _scene():
    return {
        "rooms": {"hall": {"name": "hall"}},
        "positions": {"Ada": "hall", "Bo": "hall"},
        # A body is what WEARS something (`spatial_transit._is_body_entity`),
        # so attire is what makes these two people rather than furniture.
        "entities": {},
        "attire": {"Ada": [{"item": "coat"}], "Bo": [{"item": "coat"}]},
        "contacts": [],
    }


def test_two_whole_bodies_touching_somehow_is_refused_and_reported():
    """The measured shape: a handshake was added as hand/hand `grip`, removed
    as hand/hand `grip`, and a whole-body `touch` emitted in the same beat
    survived both -- leaving two strangers recorded as touching after they had
    shaken hands and let go."""
    scene, report = _scene(), []
    apply_contact_ops(scene, [{"op": "add", "actor": "Ada", "target": "Bo",
                               "manner": "touch"}], report=report)

    assert scene["contacts"] == []
    assert any("names no part on either side" in line for line in report), report


def test_a_whole_body_contact_with_a_named_manner_still_stands():
    """An embrace names no part because there is no part to name. Refusing
    this would take out containment, which is written the same way."""
    scene = _scene()
    apply_contact_ops(scene, [{"op": "add", "actor": "Ada", "target": "Bo",
                               "manner": "embrace"}])

    assert len(scene["contacts"]) == 1
    assert scene["contacts"][0]["manner"] == "embrace"


def test_a_named_part_on_either_side_still_stands():
    """`touch` is only empty when nothing else is said. One named part is
    enough to make it an assertion about surfaces."""
    scene = _scene()
    apply_contact_ops(scene, [{"op": "add", "actor": "Ada", "actor_part": "hand",
                               "target": "Bo", "manner": "touch"}])

    assert len(scene["contacts"]) == 1
    assert scene["contacts"][0]["actor_part"] == "hand"
