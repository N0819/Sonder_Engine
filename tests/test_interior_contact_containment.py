"""A body inside another body's mouth was seen by the body around it.

`containment_conceals` already states the rule exactly, and has for a long
time: "being shut inside something blocks the view out exactly as it blocks
the view in... something carried inside a body is not seen BY that body
either... what it has instead of sight is touch." It reads `scene.contained`,
and nothing ever derived that from the contact ledger.

Measured, chat 86 t49-t50. The contact specialist wrote
`containment: {"Hinami": null}` -- explicitly RELEASING the record -- and
expressed the same enclosure as an interior `contact_op` instead. From that
beat the scene held a body at rest inside a mouth in one ledger and nobody
inside anything in the other, and the enclosing body's own view carried the
enclosed body's appearance region by region:

    You see a young woman appearing in golden fox ears and six golden tails
    ... Hinami's exposed groin is visible ...
    Barely visible copper-gold hair on her shins.

Touch was correct and vivid the whole time ("Your body registers Hinami's body
within your mouth: pressure, fullness and movement"). The enclosure was
modelled; it just was not modelled for sight.

The direction of the fix matters. Containment stays authoritative -- contact
normalisation defers to it on exactly that ground -- so this only fills a gap
the contact ledger already asserts, and never overrides a record that exists.
"""

from __future__ import annotations

import pytest

from world.spatial import (containment_conceals,
                           derive_containment_from_contacts,
                           merge_scene_with_diff)


def _scene(**over):
    scene = {
        "rooms": {"reception_room": {"name": "Reception Room"}},
        "positions": {"Hinami": "reception_room",
                      "Mirelle": "reception_room"},
        "entities": {}, "contacts": [], "contained": {}, "scales": {},
        "poses": {}, "stations": {},
    }
    scene.update(over)
    return scene


def _inside(actor="Hinami", holder="Mirelle", part="body",
            interior="mouth", relation="interior"):
    """The exact shape chat 86 t50 committed."""
    return {"actor": actor, "actor_part": part, "target": holder,
            "target_part": "", "target_interior": interior,
            "manner": "rest", "relation": relation, "motion": "settled"}


class TestTheEnclosureIsRecorded:
    def test_a_whole_body_in_an_interior_becomes_containment(self):
        scene = _scene(contacts=[_inside()])
        assert derive_containment_from_contacts(scene) == ["Hinami"]
        assert scene["contained"]["Hinami"] == {"in": "Mirelle",
                                                "mode": "interior"}

    def test_and_that_is_what_blocks_the_sight(self):
        """Both directions. The body around it cannot see in either -- it is
        not inside its own enclosure, so the two do not match."""
        scene = _scene(contacts=[_inside()])
        assert not containment_conceals(scene, "Mirelle", "Hinami")

        derive_containment_from_contacts(scene)
        assert containment_conceals(scene, "Mirelle", "Hinami")
        assert containment_conceals(scene, "Hinami", "Mirelle")

    @pytest.mark.parametrize("part", ["body", "", "whole body", "self"])
    def test_every_spelling_of_the_whole_body(self, part):
        scene = _scene(contacts=[_inside(part=part)])
        assert derive_containment_from_contacts(scene) == ["Hinami"]

    @pytest.mark.parametrize("interior", ["mouth", "coils", "pouch", "hull"])
    def test_the_rule_is_not_about_mouths(self, interior):
        """Stated in the engine's vocabulary, so it holds for a mouth, a
        coil, a pouch and a ship's hull alike."""
        scene = _scene(contacts=[_inside(interior=interior)])
        assert derive_containment_from_contacts(scene) == ["Hinami"]


class TestWhatItMustNotDo:
    def test_a_part_inside_an_interior_is_not_containment(self):
        """The other contact live on that same beat: a tongue against a torso
        inside a mouth. That is contact WITHIN an enclosure and says nothing
        about who is enclosed -- and if it did, it would make the enclosing
        body the contents of its own mouth."""
        scene = _scene(contacts=[
            {"actor": "Mirelle", "actor_part": "tongue", "target": "Hinami",
             "target_part": "torso", "target_interior": "mouth",
             "manner": "press", "relation": "interior", "motion": "settled"}])
        assert derive_containment_from_contacts(scene) == []
        assert scene["contained"] == {}

    def test_a_hand_in_a_pocket_does_not_pocket_its_owner(self):
        scene = _scene(contacts=[_inside(part="hand", interior="pocket")])
        assert derive_containment_from_contacts(scene) == []

    def test_a_surface_contact_is_not_an_enclosure(self):
        scene = _scene(contacts=[_inside(relation="surface", interior="")])
        assert derive_containment_from_contacts(scene) == []

    def test_an_existing_record_is_never_overridden(self):
        """Containment is authoritative; contact normalisation already defers
        to it. A body the scene says is carried IN VIEW stays visible."""
        scene = _scene(contacts=[_inside()],
                       contained={"Hinami": {"in": "Mirelle",
                                             "mode": "held"}})
        assert derive_containment_from_contacts(scene) == []
        assert scene["contained"]["Hinami"]["mode"] == "held"
        # `held` is an OPEN mode -- a body in an open palm is seen.
        assert not containment_conceals(scene, "Mirelle", "Hinami")

    def test_a_body_cannot_contain_itself(self):
        scene = _scene(contacts=[_inside(actor="Hinami", holder="Hinami")])
        assert derive_containment_from_contacts(scene) == []

    def test_no_contacts_is_a_no_op(self):
        scene = _scene()
        assert derive_containment_from_contacts(scene) == []
        assert scene["contained"] == {}


class TestThroughTheMerge:
    def test_the_beat_that_swallowed_her(self):
        """End to end in the shape t50 actually committed: the contact op
        arrives and the containment channel is empty."""
        scene = _scene()
        merged = merge_scene_with_diff(scene, {
            "contact_ops": [{"op": "add", "actor": "Hinami",
                             "actor_part": "body", "target": "Mirelle",
                             "target_interior": "mouth", "manner": "rest",
                             "relation": "interior"}],
        })
        record = (merged.get("contained") or {}).get("Hinami")
        assert record, "the merge left the enclosure out of `contained`"
        assert record["in"] == "Mirelle"
        assert containment_conceals(merged, "Mirelle", "Hinami")

    def test_an_explicit_release_still_releases(self):
        """t49 wrote `containment: {"Hinami": null}`. An author clearing a
        record must not have it silently reinstated by a contact that is only
        a part touching an interior."""
        scene = _scene(contained={"Hinami": {"in": "Mirelle",
                                             "mode": "held"}})
        merged = merge_scene_with_diff(scene, {
            "containment": {"Hinami": None},
            "contact_ops": [{"op": "add", "actor": "Mirelle",
                             "actor_part": "tongue", "target": "Hinami",
                             "target_part": "torso",
                             "target_interior": "mouth", "manner": "press",
                             "relation": "interior"}],
        })
        assert not (merged.get("contained") or {}).get("Hinami")

    def test_the_enclosed_body_then_travels_with_its_container(self):
        """The record has to be a real one, not a flag the sight gate happens
        to read: a body inside another goes where that body goes.

        Two merges, because a contact cannot be made between bodies in
        different rooms in the first place -- the enclosure forms where they
        both are, and the journey comes after.
        """
        scene = _scene(rooms={"reception_room": {"name": "Reception Room",
                                                 "adjacent": ["corridor"]},
                              "corridor": {"name": "Corridor",
                                           "adjacent": ["reception_room"]}})
        merged = merge_scene_with_diff(scene, {
            "contact_ops": [{"op": "add", "actor": "Hinami",
                             "actor_part": "body", "target": "Mirelle",
                             "target_interior": "mouth", "manner": "rest",
                             "relation": "interior"}],
        })
        assert (merged["contained"] or {}).get("Hinami")

        moved = merge_scene_with_diff(merged,
                                      {"positions": {"Mirelle": "corridor"}})
        assert moved["positions"]["Mirelle"] == "corridor"
        assert moved["positions"]["Hinami"] == "corridor"
        assert containment_conceals(moved, "Mirelle", "Hinami")

    def test_a_contact_across_rooms_never_forms_an_enclosure(self):
        """Nothing here can invent an enclosure out of a refused contact."""
        scene = _scene(positions={"Hinami": "corridor",
                                  "Mirelle": "reception_room"},
                       rooms={"reception_room": {"name": "Reception Room"},
                              "corridor": {"name": "Corridor"}})
        merged = merge_scene_with_diff(scene, {
            "contact_ops": [{"op": "add", "actor": "Hinami",
                             "actor_part": "body", "target": "Mirelle",
                             "target_interior": "mouth", "manner": "rest",
                             "relation": "interior"}],
        })
        assert merged["contacts"] == []
        assert merged["contained"] == {}
        assert merged["positions"]["Hinami"] == "corridor"
