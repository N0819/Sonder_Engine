"""An occupant of a room parented to another entity is concealed, and is felt.

A scene can express one entity being inside another two ways: the `contained`
ledger, or a room carrying `parent_entity` which the occupant simply has as
their position. Every concealment mechanism keyed off the ledger alone, so the
room form concealed nothing -- found live, where an occupant of a parented
interior read as an ordinary occupant of an ordinary adjacent room: visible to
the very entity enclosing them, and delivering no touch to it.

Both halves were wrong, in opposite directions: seen when they should not have
been, and not felt when they should have been.
"""

from __future__ import annotations

from world import spatial
from agents.perception import _touch_only_sources


def _scene():
    """The live shape: an interior room parented to an entity that itself holds
    a position, reached through an opaque barrier, with the occupant's position
    simply set to that room. No `contained` record and no `contacts` entry --
    which is exactly the case that slipped through."""
    return {
        "rooms": {
            "hold": {"name": "Hold", "light": "dim",
                     "adjacent": [{"to": "yard", "barrier": "open"}]},
            "yard": {"name": "Yard",
                     "adjacent": [{"to": "hold", "barrier": "open"}]},
            "interior": {
                "name": "Interior", "light": "dark", "parent_entity": "Carrier",
                "adjacent": [{"to": "hold", "barrier": "membrane",
                              "distance": "near"}],
            },
        },
        "positions": {"Carrier": "hold", "Occupant": "interior",
                      "Bystander": "hold"},
        "entities": {"Carrier": {}, "Occupant": {}, "Bystander": {}},
        "contained": {}, "contacts": [], "attire": {}, "overlays": {},
    }


class TestConcealed:
    def test_the_enclosing_entity_cannot_see_the_occupant(self):
        assert spatial.containment_conceals(_scene(), "Carrier", "Occupant")
        assert spatial.visual_level_between(
            _scene(), "Carrier", "Occupant") == "none"

    def test_the_occupant_cannot_see_out(self):
        """Being shut inside blocks the view out exactly as it blocks the view
        in -- the direction that is easier to forget."""
        assert spatial.visual_level_between(
            _scene(), "Occupant", "Carrier") == "none"

    def test_a_bystander_in_the_room_cannot_see_the_occupant(self):
        assert spatial.visual_level_between(
            _scene(), "Bystander", "Occupant") == "none"
        assert spatial.containment_conceals(_scene(), "Bystander", "Occupant")

    def test_the_carrier_is_not_concealed_by_its_own_interior(self):
        assert not spatial.containment_conceals(_scene(), "Bystander", "Carrier")
        assert spatial.hiding_holders_of(_scene(), "Carrier") == []

    def test_the_holder_is_resolved(self):
        assert spatial.hiding_holders_of(_scene(), "Occupant") == ["Carrier"]


class TestButFelt:
    def test_touch_reaches_both_ways(self):
        """Losing this half is the wrong trade: concealment that also deletes
        the contact channel leaves the enclosing entity perceiving nothing at
        all of what it contains."""
        scene = _scene()
        rel = {"Occupant": spatial.spatial_rel_between(
            scene, "Carrier", "Occupant")}
        assert _touch_only_sources(
            scene, "Carrier", rel, {"Occupant": False}) == {"Occupant"}
        rel = {"Carrier": spatial.spatial_rel_between(
            scene, "Occupant", "Carrier")}
        assert _touch_only_sources(
            scene, "Occupant", rel, {"Carrier": False}) == {"Carrier"}

    def test_an_uninvolved_bystander_gets_no_touch(self):
        scene = _scene()
        rel = {"Occupant": spatial.spatial_rel_between(
            scene, "Bystander", "Occupant")}
        assert _touch_only_sources(
            scene, "Bystander", rel, {"Occupant": False}) == set()


class TestCrossingGrace:
    """The threshold-crossing grace floors sight at `shapes` for two beats so a
    body does not blink out mid-step through a doorway. Entry into a parented
    interior is not a threshold anyone stands part-way through -- left as one,
    it kept an occupant rendering as `shapes` to the very entity enclosing
    them, for two beats after the entry was complete."""

    def _crossing_scene(self):
        scene = _scene()
        scene["crossings"] = {"Occupant": {"from": "hold", "to": "interior",
                                           "beats": 2}}
        return scene

    def test_a_live_crossing_does_not_defeat_parented_room_concealment(self):
        scene = self._crossing_scene()
        assert not spatial.crossing_visible_from(scene, "hold", "Occupant")
        assert spatial.visual_level_between(
            scene, "Carrier", "Occupant") == "none"
        assert spatial.visual_level_between(
            scene, "Bystander", "Occupant") == "none"

    def test_an_ordinary_doorway_crossing_still_gets_its_grace(self):
        """The grace is load-bearing for real thresholds and must survive."""
        scene = _scene()
        scene["rooms"]["hold"]["adjacent"] = [{"to": "yard", "barrier": "curtain"}]
        scene["rooms"]["yard"]["adjacent"] = [{"to": "hold", "barrier": "curtain"}]
        scene["positions"]["Occupant"] = "yard"
        scene["crossings"] = {"Occupant": {"from": "hold", "to": "yard",
                                           "beats": 2}}
        assert spatial.crossing_visible_from(scene, "hold", "Occupant")


def test_the_contained_ledger_form_still_works():
    """The room form is an addition, not a replacement."""
    scene = _scene()
    scene["rooms"]["interior"].pop("parent_entity")
    scene["positions"]["Occupant"] = "hold"
    scene["contained"] = {"Occupant": {"in": "Carrier", "mode": "enclosed"}}
    assert spatial.hiding_holders_of(scene, "Occupant") == ["Carrier"]
    assert spatial.containment_conceals(scene, "Bystander", "Occupant")


class TestConductedHearing:
    """Sound from inside a parented interior is CONDUCTED, not transmitted.
    The enclosing entity is the medium, so its voice arrives close and low
    rather than faint -- an occupant was otherwise unable to make out the one
    voice they are physically closest to in the world.

    Strictly one-way: the reverse direction is a voice trying to get OUT
    through that same mass, which the barrier already models correctly.
    """

    def test_the_occupant_hears_the_enclosing_entity(self):
        scene = _scene()
        rel = spatial.spatial_rel_between(scene, "Occupant", "Carrier")
        assert rel.get("inside_source") is True
        assert spatial.hear_level(rel, "normal") == "full"

    def test_the_enclosing_entity_does_not_hear_the_occupant_the_same_way(self):
        scene = _scene()
        rel = spatial.spatial_rel_between(scene, "Carrier", "Occupant")
        assert not rel.get("inside_source")
        assert spatial.hear_level(rel, "normal") != "full"

    def test_a_bystander_is_unaffected(self):
        scene = _scene()
        rel = spatial.spatial_rel_between(scene, "Bystander", "Occupant")
        assert not rel.get("inside_source")
        assert spatial.hear_level(rel, "normal") != "full"

    def test_a_murmur_still_only_fragments(self):
        """Conduction is not a bypass -- it changes the medium, not the
        volume."""
        scene = _scene()
        rel = spatial.spatial_rel_between(scene, "Occupant", "Carrier")
        assert spatial.hear_level(rel, "mutter") == "fragment"

    def test_conduction_grants_no_sight(self):
        scene = _scene()
        assert spatial.visual_level_between(
            scene, "Occupant", "Carrier") == "none"


class TestMuffledFragmentRendering:
    """A fragment is a partial transcript of what carried, not a description of
    the act of half-hearing. The old form rendered '...something about <three
    middle words>...', which told the perceiver they heard something about a
    thing instead of letting them hear the pieces -- and handed the narrator a
    stock phrase to echo."""

    def test_it_delivers_words_not_a_summary(self):
        from agents.common import _muffled_fragment
        got = _muffled_fragment("the ledger is going to sink you")
        assert "something about" not in got
        assert "ledger" in got and "sink" in got

    def test_every_chunk_is_verbatim(self):
        """_scrub_invented_dialogue validates a muffled line chunk by chunk
        against what was actually said, so a chunk stitched across punctuation
        would get the whole line dropped as invented."""
        from agents.common import _muffled_fragment
        import re
        body = "hold still, breathe slowly, and do not struggle"
        got = _muffled_fragment(body)
        chunks = [c.strip() for c in re.split(r"\.{2,}|…", got) if c.strip()]
        assert chunks
        for c in chunks:
            assert c in body, c

    def test_function_words_are_what_gets_lost(self):
        from agents.common import _muffled_fragment
        got = _muffled_fragment("I will not let you go and I will not stop")
        assert " you" not in got and " and" not in got

    def test_too_little_to_carry_stays_indistinct(self):
        from agents.common import _muffled_fragment
        assert _muffled_fragment("no") == "...something indistinct..."
        assert _muffled_fragment("") == "...something indistinct..."
