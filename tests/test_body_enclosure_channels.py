"""What reaches a body sealed inside another body, and what leaves it.

An enclosed occupant is the sharpest test of the perception layer, because
every channel points a different way at once: the enclosure is the nearest
thing in the world on touch, scent and conducted sound, and an absolute wall on
sight; the room beyond it is gone; and the occupant's own body is unaffected by
any of it. Get one direction wrong and the character behaves as though they are
somewhere else entirely.

All three were wrong, and one measurement showed why. Against a live scene, an
occupant fully enclosed in another body read:

    rel(occupant -> enclosure) = {"same_room": false, "barrier": "separated",
                                  "distance": "far"}
    scent_level                = "muffled"

and the relation to a WINDOW ACROSS THE ROOM was byte-identical. The engine
could not tell the body around her from a draught outside. Reported from play
as "the scent goes faint exactly when it should drown out everything else",
which is precisely what that relation produces.

Three separate defects behind it:

**The ledger form was invisible.** A scene expresses one body inside another
two ways -- an interior room parented to the body, or a `contained` record --
and `_body_interior_holder` read only the first, while `_hiding_holders` read
both. So an occupant got every consequence of being sealed away (concealment)
and none of the compensations (conducted sound, flooding scent), because two
halves of one fact were answered by two functions and only one of them knew the
common case.

**Identity was compared by spelling.** The same character appears as a cast
display name and as a scene entity id at once. `contained` named the entity id,
`positions` was keyed by the display name, and `derive_contained_positions`
resolved neither -- so it skipped, silently, and left the occupant's position
set to the entity id: a room that does not exist.

**One symmetric flag stood for two opposite situations.** `concealed` is true
when either party is enclosed, so "the source is shut inside something"
(muffled, correct) and "the PERCEIVER is shut inside something" got the same
answer. The second is not a muffling at all.

The vocabulary is now directional: `inside_source` (perceiver within this
source), `enclosed_from_source` (perceiver within something else), and
`source_enclosed` (this source within something the perceiver is outside of).

Deliberately scoped to BODIES. A crate is not a mass -- opaque is not
soundproof, and `tests/test_containment_concealment.py` holds that line.
"""

from __future__ import annotations

import pytest

from world.spatial import (
    derive_contained_positions,
    hear_level,
    merge_scene_with_diff,
    repair_entity_positions,
    same_subject,
    scent_level,
    spatial_rel_between,
    visual_level_between,
)

OCCUPANT = "Wren"
HOST = "Vessel"
HOST_ID = "vessel_entity"


def _scene(*, by_id=True, position=None):
    """One room. `Wren` is sealed inside `Vessel`, who is standing in it.

    `by_id` writes the containment record against the entity id while
    `positions` is keyed by the display name -- the live shape, and the one
    that resolved to nothing.
    """
    holder = HOST_ID if by_id else HOST
    return {
        "rooms": {"hall": {"name": "Hall", "desc": "A hall.", "adjacent": []}},
        "positions": {
            OCCUPANT: position if position is not None else "hall",
            HOST: "hall",
            "lamp": "hall",
        },
        "entities": {
            HOST_ID: {"name": HOST, "kind": "person", "aliases": []},
            "lamp": {"name": "Lamp", "kind": "fixture", "aliases": []},
        },
        # `_is_body_entity`: bodies are the things that wear something and the
        # things that have a size relative to their own baseline.
        "attire": {HOST: {}, OCCUPANT: {}},
        "scales": {OCCUPANT: 0.05},
        "contained": {OCCUPANT: {"in": holder, "mode": "inside"}},
    }


# --- the relation itself ---------------------------------------------------

class TestTheEnclosureIsNotDistance:
    def test_the_occupant_is_inside_the_source(self):
        sc = _scene()
        rel = spatial_rel_between(sc, OCCUPANT, HOST)
        assert rel.get("inside_source") is True

    def test_the_ledger_form_is_read_not_only_the_interior_room_form(self):
        """The defect in one assertion: expressed as a `contained` record
        rather than a parented room, the enclosure used to be invisible."""
        sc = _scene()
        assert sc.get("rooms", {}).get("hall", {}).get("parent_entity") is None
        assert spatial_rel_between(sc, OCCUPANT, HOST).get("inside_source")

    def test_the_enclosure_and_a_fixture_across_the_room_differ(self):
        """They were byte-identical, which is the whole report."""
        sc = _scene()
        near = spatial_rel_between(sc, OCCUPANT, HOST)
        far = spatial_rel_between(sc, OCCUPANT, "lamp")
        assert near != far
        assert far.get("enclosed_from_source") is True
        assert near.get("enclosed_from_source") is not True


# --- scent: the reported symptom -------------------------------------------

class TestScent:
    def test_the_enclosure_is_maximal(self):
        """There is no barrier between you and a thing you are within."""
        sc = _scene()
        assert scent_level(spatial_rel_between(sc, OCCUPANT, HOST)) == "full"

    def test_the_room_beyond_is_gone(self):
        """Not muffled -- gone. The occupant is breathing nothing else."""
        sc = _scene()
        assert scent_level(spatial_rel_between(sc, OCCUPANT, "lamp")) == "none"

    def test_the_occupant_still_smells_of_themselves(self):
        """A body is the one thing no enclosure can put a wall in front of."""
        sc = _scene()
        assert scent_level(
            spatial_rel_between(sc, OCCUPANT, OCCUPANT)) == "full"

    def test_the_host_smells_the_occupant_only_faintly(self):
        """The direction that was already right, and must stay right: a
        concealed source is muffled to whoever is outside it."""
        sc = _scene()
        assert scent_level(spatial_rel_between(sc, HOST, OCCUPANT)) == "muffled"

    def test_two_occupants_of_one_enclosure_are_not_walled_from_each_other(self):
        sc = _scene()
        sc["contained"]["Mote"] = {"in": HOST_ID, "mode": "inside"}
        sc["positions"]["Mote"] = "hall"
        rel = spatial_rel_between(sc, OCCUPANT, "Mote")
        assert rel.get("enclosed_from_source") is not True
        assert scent_level(rel) == "full"


# --- sound: three directions -----------------------------------------------

class TestHearing:
    def test_the_host_s_voice_is_conducted_not_transmitted(self):
        """The one voice the occupant is physically closest to in the world."""
        sc = _scene()
        assert hear_level(spatial_rel_between(sc, OCCUPANT, HOST),
                          "normal") == "full"

    def test_the_room_beyond_barely_carries(self):
        """A latch rattling across the room reached the occupant at full
        clarity, because a contained body's position derives to its carrier's
        and so read `same_room` with everything it could no longer hear."""
        sc = _scene()
        rel = spatial_rel_between(sc, OCCUPANT, "lamp")
        assert hear_level(rel, "normal") == "none"
        assert hear_level(rel, "shout") == "fragment"

    def test_the_occupant_hears_their_own_voice(self):
        sc = _scene()
        rel = spatial_rel_between(sc, OCCUPANT, OCCUPANT)
        assert hear_level(rel, "normal") == "full"
        assert hear_level(rel, "whisper") == "full"

    def test_the_occupant_is_muffled_to_the_host(self):
        """Muffled outward, unattenuated inward -- the asymmetry is the point.
        The barrier rules used to be trusted with this direction, which held
        only while the two sides sat in different rooms; a containment ledger
        derives them into one, leaving nothing to muffle anything."""
        sc = _scene()
        rel = spatial_rel_between(sc, HOST, OCCUPANT)
        assert hear_level(rel, "normal") == "fragment"
        assert hear_level(rel, "shout") == "fragment"
        assert hear_level(rel, "whisper") == "none"


class TestSight:
    def test_the_occupant_sees_nothing_out(self):
        sc = _scene()
        assert visual_level_between(sc, OCCUPANT, HOST) == "none"
        assert visual_level_between(sc, OCCUPANT, "lamp") == "none"

    def test_the_room_sees_nothing_in(self):
        sc = _scene()
        assert visual_level_between(sc, HOST, OCCUPANT) == "none"


# --- a crate is not a body -------------------------------------------------

class TestOnlyABodyConducts:
    """`tests/test_containment_concealment.py` holds the other half of this:
    opaque is not soundproof. A box you can be heard through must not become
    one because the enclosure rules got better at bodies."""

    def _crate(self):
        return {
            "rooms": {"hall": {"name": "Hall", "adjacent": []}},
            "positions": {"Ada": "hall", "Bo": "hall", "Crate": "hall"},
            "contained": {"Ada": {"in": "Crate", "mode": "container"}},
        }

    def test_a_crate_does_not_conduct(self):
        sc = self._crate()
        assert spatial_rel_between(sc, "Ada", "Crate").get(
            "inside_source") is not True

    def test_a_crate_does_not_wall_off_the_room(self):
        sc = self._crate()
        assert spatial_rel_between(sc, "Ada", "Bo").get(
            "enclosed_from_source") is not True

    def test_someone_in_a_crate_is_still_heard(self):
        sc = self._crate()
        assert hear_level(spatial_rel_between(sc, "Bo", "Ada"),
                          "normal") == "full"

    def test_an_undeclared_holder_stays_a_container(self):
        """Positive evidence required. An enclosure nobody described must not
        be promoted to a mass on the strength of silence."""
        sc = self._crate()
        sc["entities"] = {}
        assert spatial_rel_between(sc, "Ada", "Crate").get(
            "inside_source") is not True


# --- identity, and the position that was not a room ------------------------

class TestIdentityAcrossSpellings:
    def test_an_entity_id_and_its_display_name_are_one_being(self):
        sc = _scene()
        assert same_subject(sc, HOST_ID, HOST)
        assert same_subject(sc, HOST, HOST_ID)

    def test_two_different_beings_are_not(self):
        sc = _scene()
        assert not same_subject(sc, HOST, OCCUPANT)
        assert not same_subject(sc, HOST_ID, "lamp")

    def test_nothing_matches_nothing(self):
        sc = _scene()
        assert not same_subject(sc, "", HOST)
        assert not same_subject(sc, None, None)

    def test_containment_resolves_a_carrier_named_by_id(self):
        """`derive_contained_positions` skipped when the carrier was not a key
        in `positions`, which is silent -- and left the occupant at whatever
        position had been written, valid or not."""
        sc = _scene(position="somewhere_else")
        derive_contained_positions(sc)
        assert sc["positions"][OCCUPANT] == "hall"

    def test_a_carrier_named_by_display_name_still_works(self):
        sc = _scene(by_id=False, position="somewhere_else")
        derive_contained_positions(sc)
        assert sc["positions"][OCCUPANT] == "hall"


class TestAPositionMustNameARoom:
    def test_an_entity_written_as_a_position_is_repaired(self):
        """The root defect. Every spatial query resolves an unknown room to
        the safe-closed default rather than raising, so a body written into a
        room that does not exist is not broken loudly -- it is nowhere, and
        every channel reads as distance."""
        sc = _scene(position=HOST_ID)
        sc["contained"] = {}
        assert repair_entity_positions(sc) == [(OCCUPANT, HOST_ID, "hall")]
        assert sc["positions"][OCCUPANT] == "hall"

    def test_the_repair_records_being_at_the_entity(self):
        """"At a thing" is what `stations` already expresses. Containment is
        NOT inferred -- turning a mistyped position into an enclosure would
        make a typo change the information firewall."""
        sc = _scene(position=HOST_ID)
        sc["contained"] = {}
        repair_entity_positions(sc)
        assert sc["stations"][OCCUPANT]["at"] == HOST_ID
        assert sc.get("contained") == {}

    def test_a_real_containment_record_wins(self):
        """Both run at merge, containment first, so an actual enclosure is
        never downgraded to standing beside the thing."""
        sc = _scene(position=HOST_ID)
        merged = merge_scene_with_diff(sc, {})
        assert merged["positions"][OCCUPANT] == "hall"
        assert spatial_rel_between(merged, OCCUPANT, HOST).get("inside_source")

    def test_a_valid_position_is_left_alone(self):
        sc = _scene()
        assert repair_entity_positions(sc) == []
        assert sc["positions"][OCCUPANT] == "hall"

    def test_an_unknown_string_that_names_nothing_is_left_alone(self):
        """A room the scene has not defined yet is a different problem, and
        guessing at it would be worse than leaving it visible."""
        sc = _scene(position="a_room_not_yet_written")
        sc["contained"] = {}
        assert repair_entity_positions(sc) == []
        assert sc["positions"][OCCUPANT] == "a_room_not_yet_written"

    def test_the_merge_runs_it(self):
        sc = _scene(position=HOST_ID)
        sc["contained"] = {}
        merged = merge_scene_with_diff(sc, {})
        assert merged["positions"][OCCUPANT] == "hall"
