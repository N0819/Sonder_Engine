"""Contact hygiene when the two bodies touching are not in the same room.

Contact pruning has one rule and it has always been the right one: you cannot
hold someone you are not standing next to, so a contact whose parties hold
different room ids is stale and goes. That rule is what makes walking away
clear a hold with nothing for the Director to remember.

It reads one case exactly backwards. When a body has taken another body
INSIDE, the occupant stands in a room of their own -- an interior parented to
the holder -- and the holder stands outside it. Two different room ids, for
the two bodies in the world that are closest of all. So the moment the
enclosure becomes a place, room equality severs the single contact that must
never be severed: touch is the ONE channel the firewall permits across an
enclosure (sight is gone in both directions, ambient scope stops at the
boundary), and cutting it leaves the holder with no legitimate account of
what it is holding. The firewall SUBTRACTS; it must never make a mind
conclude less than it has a channel for.

The second half is the station. `target_interior` names the region of the
enclosing body a contact is inside, and once that inside is rooms the region
and the room are one fact under two names. Measured in chat 88: the same
`target_interior` value stood unchanged from t59 through t67 while the prose
moved the occupant steadily deeper, because the value was written once by the
op that established the relation and only an explicit `cross` op ever
rewrote it.
"""

from __future__ import annotations

from world.spatial import enclosure_joins_rooms, normalize_scene_contacts

OCCUPANT = "Wren"
HOLDER = "Vessel"
HOLDER_ID = "vessel_entity"
BYSTANDER = "Corin"


def _scene(*, occupant_room="vessel_antechamber", contacts=()):
    return {
        "rooms": {
            "hall": {"name": "Hall", "desc": "A hall.", "adjacent": []},
            "yard": {"name": "Yard", "desc": "Outside.", "adjacent": []},
            "vessel_antechamber": {
                "name": "Antechamber", "desc": "A close passage.",
                "parent_entity": HOLDER_ID,
                "adjacent": [{"to": "vessel_core", "barrier": "membrane"}],
            },
            "vessel_core": {
                "name": "Core", "desc": "Deeper still.",
                "parent_entity": HOLDER_ID,
                "adjacent": [{"to": "vessel_antechamber", "barrier": "membrane"}],
            },
        },
        "positions": {
            OCCUPANT: occupant_room,
            HOLDER: "hall",
            BYSTANDER: "hall",
        },
        "entities": {
            HOLDER_ID: {"name": HOLDER, "kind": "person", "aliases": [],
                        "interior_rooms": ["vessel_antechamber", "vessel_core"]},
        },
        "attire": {HOLDER: {}, OCCUPANT: {}, BYSTANDER: {}},
        "scales": {OCCUPANT: 0.05},
        "contained": {},
        "contacts": [dict(row) for row in contacts],
    }


def _interior_row(actor, target, station="Deep chamber"):
    return {
        "actor": actor, "actor_part": "body",
        "target": target, "target_part": "torso",
        "relation": "interior", "target_interior": station,
        "manner": "enveloped",
    }


class TestTheHolderKeepsItsChannel:
    def test_an_enclosure_joined_pair_survives(self):
        scene = _scene(contacts=[_interior_row(OCCUPANT, HOLDER)])
        normalize_scene_contacts(scene)
        assert len(scene["contacts"]) == 1
        # The pair, not the direction: `_clean_contact`'s envelopment fold
        # already puts the enclosing side in the actor slot, and which way a
        # symmetric fact is written down is a spelling.
        row = scene["contacts"][0]
        assert {row["actor"], row["target"]} == {OCCUPANT, HOLDER}

    def test_it_survives_stated_from_the_holders_side(self):
        """Contact is symmetric; which body the ledger happens to name as
        actor is a spelling, not a physical fact."""
        scene = _scene(contacts=[_interior_row(HOLDER, OCCUPANT)])
        normalize_scene_contacts(scene)
        assert len(scene["contacts"]) == 1

    def test_the_join_resolves_the_entity_id_against_the_display_name(self):
        """The room's `parent_entity` is an entity ID; the contact names the
        display name. Five separate defects here were a single `==`."""
        scene = _scene()
        assert enclosure_joins_rooms(
            scene, "vessel_antechamber", "hall", OCCUPANT, HOLDER) is True

    def test_the_join_is_directionless(self):
        scene = _scene()
        assert enclosure_joins_rooms(
            scene, "hall", "vessel_antechamber", HOLDER, OCCUPANT) is True


class TestWhatStillGoes:
    def test_walking_away_still_ends_a_hold(self):
        """The rule this widens is untouched for everyone it was written for."""
        scene = _scene()
        scene["positions"][BYSTANDER] = "yard"
        scene["contacts"] = [{
            "actor": HOLDER, "actor_part": "hand",
            "target": BYSTANDER, "target_part": "wrist",
            "relation": "surface", "manner": "grip",
        }]
        normalize_scene_contacts(scene)
        assert scene["contacts"] == []

    def test_a_bystander_cannot_reach_into_the_enclosure(self):
        """THE FIRWALL SUBTRACTS. A third party standing in the room the
        holder is in is outside an enclosure the occupant is inside; being
        near the holder is not being near what the holder contains."""
        scene = _scene(contacts=[{
            "actor": BYSTANDER, "actor_part": "hand",
            "target": OCCUPANT, "target_part": "shoulder",
            "relation": "surface", "manner": "grip",
        }])
        normalize_scene_contacts(scene)
        assert scene["contacts"] == []

    def test_the_join_is_the_pair_and_not_the_neighbourhood(self):
        scene = _scene()
        assert enclosure_joins_rooms(
            scene, "vessel_antechamber", "hall", OCCUPANT, BYSTANDER) is False

    def test_an_unparented_room_joins_nothing(self):
        scene = _scene()
        assert enclosure_joins_rooms(
            scene, "hall", "yard", HOLDER, BYSTANDER) is False


class TestTheStationTracksTheBody:
    def test_target_interior_follows_the_occupant(self):
        """The frozen-ledger class, chat 88 t59-t67: the station stood still
        for eight turns while the body it described moved."""
        scene = _scene(occupant_room="vessel_core",
                       contacts=[_interior_row(OCCUPANT, HOLDER,
                                               station="Antechamber")])
        normalize_scene_contacts(scene)
        assert scene["contacts"][0]["target_interior"] == "Core"

    def test_it_is_the_display_name_not_the_room_key(self):
        """A synthetic room id is not a place anybody can name, and this
        value is read lexically downstream."""
        scene = _scene(occupant_room="vessel_core",
                       contacts=[_interior_row(OCCUPANT, HOLDER)])
        normalize_scene_contacts(scene)
        assert scene["contacts"][0]["target_interior"] == "Core"
        assert "vessel_core" not in scene["contacts"][0]["target_interior"]

    def test_a_surface_relation_is_never_restationed(self):
        scene = _scene(contacts=[{
            "actor": OCCUPANT, "actor_part": "hand",
            "target": HOLDER, "target_part": "shoulder",
            "relation": "surface", "manner": "press",
        }])
        normalize_scene_contacts(scene)
        assert scene["contacts"][0].get("target_interior", "") == ""

    def test_a_same_room_interior_contact_keeps_its_authored_station(self):
        """Nothing about an ordinary in-room interior relation changes: there
        is no interior ROOM to read a station off, so the ledger's own word
        stands."""
        scene = _scene(occupant_room="hall",
                       contacts=[_interior_row(OCCUPANT, HOLDER,
                                               station="Deep chamber")])
        normalize_scene_contacts(scene)
        assert scene["contacts"][0]["target_interior"] == "Deep chamber"
