"""Being carried in the open and being carried inside something.

A carried body has no position of its own -- the engine derives it from its
carrier's. So a body shut inside a container standing in a room reads as
`same_room` with everyone else in that room, and `same_room` answers sight
before barrier or light is consulted at all. The result: a body in a closed bag
was exactly as visible as a body held in an open palm, and perception pasted
its appearance into every observer's view.

Interior rooms have had `enclosure` to settle this. The carry path had nothing:
`mode` recorded HOW something was carried and touched visibility not at all.

Two rules here, and the second is the one that is easy to forget:
  - what is inside a closed thing is not seen from outside it, and
  - what is inside a closed thing cannot see out of it either.
"""

import pytest

from spatial import (
    containment_conceals,
    containment_hides,
    hear_level,
    infer_body_enclosures,
    spatial_rel_between,
    visual_level_between,
)


def _scene(mode="container", holder="Crate"):
    """One room; Ada is inside something Bo is standing next to."""
    return {
        "rooms": {"hall": {"name": "Hall", "desc": "A hall.", "adjacent": []}},
        "positions": {"Ada": "hall", "Bo": "hall", holder: "hall"},
        "contained": {"Ada": {"in": holder, "mode": mode}},
    }


# --- which ways of being carried hide you ----------------------------------

@pytest.mark.parametrize("mode", ["held", "carried", "riding", "mounted",
                                  "worn"])
def test_carried_in_the_open_is_still_visible(mode):
    """The documented in-view modes. These must not change -- an ordinary
    carry is the common case and was never the bug."""
    assert containment_hides(mode) is False
    sc = _scene(mode=mode)
    assert visual_level_between(sc, "Bo", "Ada") == "full"


@pytest.mark.parametrize("mode", ["pocket", "container", "inside"])
def test_carried_inside_something_is_not(mode):
    assert containment_hides(mode) is True
    sc = _scene(mode=mode)
    assert visual_level_between(sc, "Bo", "Ada") == "none"


def test_an_unrecognised_mode_is_read_as_enclosed():
    """The five open modes are exactly the documented ways a body is carried
    in view, so a mode the engine cannot vouch for must not be the one that
    grants sight. Under-sharing is the safe failure here."""
    assert containment_hides("stowed in the lining") is True
    assert visual_level_between(_scene(mode="stowed"), "Bo", "Ada") == "none"


def test_an_absent_mode_still_defaults_to_an_ordinary_carry():
    """_clean_containment fills a missing mode with "carried", and that path
    must keep behaving exactly as it always did."""
    assert containment_hides("carried") is False
    sc = _scene()
    sc["contained"]["Ada"] = {"in": "Crate"}       # no mode at all
    sc["contained"]["Ada"]["mode"] = "carried"
    assert visual_level_between(sc, "Bo", "Ada") == "full"


# --- the rule is symmetric --------------------------------------------------

def test_an_enclosed_body_cannot_see_out_either():
    """The direction that is easy to forget. A closed thing blocks the view
    out as completely as the view in."""
    sc = _scene()
    assert visual_level_between(sc, "Ada", "Bo") == "none"
    assert containment_conceals(sc, "Ada", "Bo") is True


def test_the_holder_does_not_see_its_own_contents():
    """A holder is not inside its own enclosure, so it does not match -- what
    it has instead of sight is touch."""
    sc = _scene()
    assert visual_level_between(sc, "Crate", "Ada") == "none"
    assert visual_level_between(sc, "Ada", "Crate") == "none"


def test_two_bodies_in_the_same_enclosure_see_each_other():
    sc = _scene()
    sc["positions"]["Cass"] = "hall"
    sc["contained"]["Cass"] = {"in": "Crate", "mode": "container"}
    assert containment_conceals(sc, "Ada", "Cass") is False
    assert visual_level_between(sc, "Ada", "Cass") == "full"


def test_nesting_only_matches_at_the_nearest_enclosure():
    """Ada is in a box that is itself in the crate; Bo is loose in the crate.
    Same outer enclosure, different inner one -- they do not see each other."""
    sc = _scene()
    sc["positions"]["Box"] = "hall"
    sc["contained"]["Box"] = {"in": "Crate", "mode": "container"}
    sc["contained"]["Ada"] = {"in": "Box", "mode": "container"}
    sc["contained"]["Bo"] = {"in": "Crate", "mode": "container"}
    assert containment_conceals(sc, "Bo", "Ada") is True


def test_two_bodies_both_in_the_open_are_unaffected():
    sc = {"rooms": {"hall": {"adjacent": []}},
          "positions": {"Ada": "hall", "Bo": "hall"}}
    assert containment_conceals(sc, "Ada", "Bo") is False
    assert visual_level_between(sc, "Bo", "Ada") == "full"


def test_release_restores_sight_both_ways():
    sc = _scene()
    assert visual_level_between(sc, "Bo", "Ada") == "none"
    sc["contained"] = {}
    assert visual_level_between(sc, "Bo", "Ada") == "full"
    assert visual_level_between(sc, "Ada", "Bo") == "full"


def test_concealment_does_not_touch_hearing():
    """Opaque is not soundproof. Being shut in something you can be heard from
    is the whole tension of being shut in it."""
    sc = _scene()
    rel = spatial_rel_between(sc, "Bo", "Ada")
    assert rel["concealed"] is True
    assert hear_level(rel, "normal") == "full"


# --- a body's interior is opaque whether or not anyone said so --------------

def test_a_bodys_interior_defaults_to_an_opaque_way_in():
    """The Director does not reliably declare `enclosure`, and a safety
    property cannot depend on a model remembering it. Bodies are identified by
    the things only bodies have: what they are wearing, and a size relative to
    their own baseline."""
    sc = {
        "rooms": {"hall": {"adjacent": []},
                  "inside_ada": {"adjacent": [], "parent_entity": "Ada"}},
        "entities": {"Ada": {"name": "Ada", "kind": "person",
                             "interior_rooms": ["inside_ada"]}},
        "positions": {"Ada": "hall"},
        "attire": {"Ada": {"wearing": ["a coat"], "state": []}},
    }
    assert infer_body_enclosures(sc) is True
    assert sc["entities"]["Ada"]["enclosure"] == "membrane"
    assert infer_body_enclosures(sc) is False      # idempotent


def test_a_vehicle_interior_is_left_alone():
    """The half that must NOT change: a lift car with its doors open really is
    see-through, and `container: true` is not the test -- plenty of real
    vehicles do not set it."""
    sc = {
        "rooms": {"hall": {"adjacent": []},
                  "car": {"adjacent": [], "parent_entity": "lift"}},
        "entities": {"lift": {"name": "Service Lift", "kind": "vehicle",
                              "interior_rooms": ["car"]}},
        "positions": {"lift": "hall"},
    }
    assert infer_body_enclosures(sc) is False
    assert sc["entities"]["lift"].get("enclosure") is None


def test_an_authored_enclosure_is_never_overridden():
    """Including a deliberately see-through one, which must stay authorable."""
    sc = {
        "rooms": {"hall": {"adjacent": []},
                  "inside_ada": {"adjacent": [], "parent_entity": "Ada"}},
        "entities": {"Ada": {"name": "Ada", "interior_rooms": ["inside_ada"],
                             "enclosure": "transparent"}},
        "positions": {"Ada": "hall"},
        "attire": {"Ada": {"wearing": [], "state": []}},
    }
    assert infer_body_enclosures(sc) is False
    assert sc["entities"]["Ada"]["enclosure"] == "transparent"
