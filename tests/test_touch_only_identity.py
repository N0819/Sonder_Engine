"""The touch-only firewall, and the string comparison that opened it.

An enclosing character can FEEL the body inside them and cannot SEE it. The
`resolved_event` handed to perception is omniscient -- it names what every
actor is doing, including the occupant's own interoceptive state -- so a
perceiver with a touch channel and no sight would otherwise read the hidden
body's exact condition out of prose that was meant to be filtered by channel.
`_surface_translate_event` exists to stop that, and it fails closed: the whole
omniscient event becomes "You register motion and pressure at the contact
surface."

It never ran. `_touch_only_sources` decided who the touch candidates were by
casefolded string equality, and the same character routinely exists under two
spellings at once -- a cast display name and a scene entity id. The containment
ledger recorded the holder as `elyndra_succubus`; the perceiver arrived as
`Elyndra`; `"elyndra_succubus" == "elyndra"` is False. So the occupant was not
a touch candidate, no translation fired, and the omniscient event went into the
enclosing character's payload intact.

Measured in play: the enclosing character's view came back stating the
occupant's skin was hypersensitive -- a fact the player had declared about the
occupant's body that beat, which no amount of contact could transmit. That is
the own-body isolation rule in AGENTS.md breaking on a string comparison: a
mind may receive its own body state and its own scrubbed observations, never
another mind's vitals.

Every identity comparison in that function now goes through
`spatial.same_subject`. The lesson generalises past this one function: an
engine that lets the same being carry two names cannot use `==` to decide who
anybody is, and a firewall that fails this way fails OPEN and silently.
"""

from __future__ import annotations

import pytest

from agents.perception import _surface_translate_event, _touch_only_sources
from world.spatial import spatial_rel_between

HOST = "Vessel"
HOST_ID = "vessel_entity"
OCCUPANT = "Wren"


def _scene(holder=HOST_ID):
    return {
        "rooms": {"hall": {"name": "Hall", "adjacent": []}},
        "positions": {OCCUPANT: "hall", HOST: "hall", "Onlooker": "hall"},
        "entities": {HOST_ID: {"name": HOST, "kind": "person",
                               "aliases": ["The Vessel"]}},
        "attire": {HOST: {}, OCCUPANT: {}},
        "scales": {OCCUPANT: 0.05},
        "contacts": [],
        "contained": {OCCUPANT: {"in": holder, "mode": "inside"}},
    }


def _channels(sc, perceiver, other):
    return ({other: spatial_rel_between(sc, perceiver, other)}, {other: False})


class TestTheOccupantIsATouchCandidate:
    def test_a_holder_recorded_by_entity_id_still_matches(self):
        """The live failure, in one assertion."""
        sc = _scene(holder=HOST_ID)
        sts, vis = _channels(sc, HOST, OCCUPANT)
        assert _touch_only_sources(sc, HOST, sts, vis) == {OCCUPANT}

    def test_a_holder_recorded_by_display_name_still_matches(self):
        sc = _scene(holder=HOST)
        sts, vis = _channels(sc, HOST, OCCUPANT)
        assert _touch_only_sources(sc, HOST, sts, vis) == {OCCUPANT}

    def test_a_holder_recorded_by_alias_still_matches(self):
        sc = _scene(holder="The Vessel")
        sts, vis = _channels(sc, HOST, OCCUPANT)
        assert _touch_only_sources(sc, HOST, sts, vis) == {OCCUPANT}

    def test_the_occupant_feels_the_body_around_them_too(self):
        """The other direction of the same channel: concealed but felt, and
        losing this half leaves an occupant unable to feel the enclosure."""
        sc = _scene()
        sts, vis = _channels(sc, OCCUPANT, HOST)
        assert _touch_only_sources(sc, OCCUPANT, sts, vis) == {HOST}

    def test_the_returned_name_is_the_source_tables_spelling(self):
        """Callers match this set against the source tables, so returning the
        ledger's spelling would be a set nothing can look anything up in."""
        sc = _scene()
        sts, vis = _channels(sc, OCCUPANT, HOST)
        assert _touch_only_sources(sc, OCCUPANT, sts, vis) <= set(sts)


class TestTheTranslationThenFires:
    def test_the_omniscient_event_is_replaced_wholesale(self):
        """Fails closed on purpose. Free prose cannot be security-matched --
        a later sentence may use a pronoun or paraphrase the act -- so the
        whole event goes and the deterministic contact facts supply the
        surface."""
        sc = _scene()
        sts, vis = _channels(sc, HOST, OCCUPANT)
        touch = _touch_only_sources(sc, HOST, sts, vis)
        translated = _surface_translate_event(
            "The occupant's skin turns hypersensitive; she squirms.", touch)
        assert "hypersensitive" not in translated
        assert translated == "You register motion and pressure at the contact surface."

    def test_nothing_is_translated_when_there_is_no_touch_channel(self):
        original = "Someone crosses the hall."
        assert _surface_translate_event(original, set()) == original


class TestItDoesNotOverfire:
    def test_a_perceiver_is_never_a_touch_source_to_themselves(self):
        sc = _scene()
        sts = {HOST: spatial_rel_between(sc, HOST, HOST)}
        assert _touch_only_sources(sc, HOST, sts, {HOST: False}) == set()

    def test_an_entity_id_form_of_the_perceiver_is_not_either(self):
        """The exclusion has to resolve identity too, or the perceiver
        reappears as their own touch-only source under the other spelling."""
        sc = _scene()
        sts = {HOST_ID: spatial_rel_between(sc, HOST, HOST)}
        assert _touch_only_sources(sc, HOST, sts, {HOST_ID: False}) == set()

    def test_someone_merely_in_the_room_is_not_a_touch_source(self):
        sc = _scene()
        sts, vis = _channels(sc, HOST, "Onlooker")
        assert _touch_only_sources(sc, HOST, sts, vis) == set()

    def test_a_source_that_can_be_seen_is_not_touch_only(self):
        """The whole premise is felt-but-not-seen. Something visible needs no
        surface translation and would lose real information."""
        sc = _scene()
        sts, _vis = _channels(sc, HOST, OCCUPANT)
        assert _touch_only_sources(sc, HOST, sts, {OCCUPANT: True}) == set()

    def test_no_scene_or_no_perceiver_is_survivable(self):
        assert _touch_only_sources(None, HOST, {}, {}) == set()
        assert _touch_only_sources(_scene(), "", {}, {}) == set()


def test_contact_alone_still_opens_the_channel():
    """Containment is not the only way to feel something you cannot see --
    contact is the other, and widening the identity resolution must not have
    narrowed it."""
    sc = _scene()
    sc["contained"] = {}
    sc["contacts"] = [{"actor": HOST, "target": OCCUPANT,
                       "actor_part": "hand", "target_part": "shoulder"}]
    sts, vis = _channels(sc, HOST, OCCUPANT)
    assert _touch_only_sources(sc, HOST, sts, vis) == {OCCUPANT}
