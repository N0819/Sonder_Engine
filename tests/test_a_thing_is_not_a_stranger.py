"""A thing that acts is called what it is, and has no acquaintance to earn.

Scratch story 166, turn 4597: the tide rocked the Grebe, and the player's
view read "The unfamiliar person rocks once as the tide reaches the mooring
line", "You feel the unfamiliar person's thwart against your seat" and "You
are in the deck of the unfamiliar person" -- filed to her memory that way.
The boat was a beat's SOURCE, every source went into the identity roster,
and the identity scrub rewrote "Grebe" to the person fallback wherever it
stood, room names included. Recognition is a fact about bodies; the engine
already says which entities are things (`_mover_is_a_body`).
"""

from __future__ import annotations

from agents.perception import (_source_is_a_body, _thing_label,
                               identity_bearing_sources)

SCENE = {
    "rooms": {"rope_bridge": {"name": "the rope bridge"},
              "grebe_board": {"name": "the deck of the Grebe",
                              "parent_entity": "the_grebe"},
              "landing_stage": {"name": "the landing stage"}},
    "entities": {
        "the_grebe": {"name": "the Grebe", "kind": "vehicle",
                      "aliases": ["Grebe", "the pilot boat"], "portable": False,
                      "interior_rooms": ["grebe_board"]},
        "char_hester_gale": {"name": "Hester Gale", "kind": "person"}},
    "positions": {"the_grebe": "landing_stage", "Hester Gale": "rope_bridge"},
}

SOURCES = [{"name": "the Grebe"}, {"name": "Hester Gale"},
           {"name": "rope_bridge"}, {"name": "the rope bridge"},
           {"name": "Murren"}, {"name": "cousins and mistress", "chorus": True}]


def test_a_boat_and_a_bridge_bear_no_identity():
    names = [s["name"] for s in identity_bearing_sources(SOURCES, SCENE)]
    assert names == ["Hester Gale", "Murren"], (
        "a body keeps its identity, and so does a name the scene has no "
        "record of -- a miss keeps a name withheld rather than spoken")


def test_without_the_scene_only_a_chorus_is_left_out():
    names = [s["name"] for s in identity_bearing_sources(SOURCES)]
    assert names == ["the Grebe", "Hester Gale", "rope_bridge",
                     "the rope bridge", "Murren"]


def test_a_thing_that_acts_is_called_by_its_name():
    assert not _source_is_a_body(SCENE, "the Grebe")
    assert not _source_is_a_body(SCENE, "Grebe")
    assert _source_is_a_body(SCENE, "Hester Gale")
    assert _thing_label(SCENE, "Grebe") == "the Grebe"
