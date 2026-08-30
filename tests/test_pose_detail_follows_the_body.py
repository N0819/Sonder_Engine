"""A pose `detail` that holds a body says where that body is.

`invalidate_transferred_pose_details` reconciles a possession claim in pose
prose against the transfer ledger. This is the same claim against the other
ledger: where a body is belongs to `positions`, and prose saying somebody is
HELD is a statement about where they are.

A `detail` is the one scene field nothing re-derives -- written once,
rendered verbatim into every view that can see the body including its own
interoception, and standing until some later beat happens to overwrite it.

Measured live (chat 99). A detail written while a shrunken body lay in a
mouth read "tongue curled around the little fox, holding her at the back of
the mouth". She was swallowed on the next beat and again on the one after --
mouth, throat, stomach -- and the detail followed its owner unchanged, so the
holder's own interoception went on reporting a body at the back of her mouth
that was by then two rooms further down.
"""
from world.spatial import merge_scene_with_diff


def _scene(detail, **poses):
    pose = {"posture": "sitting", "support": "wide_bed", "detail": detail}
    pose.update(poses)
    return {
        "rooms": {"room": {}, "mouth": {}, "throat": {}},
        "positions": {"Mirelle": "room", "Hinami": "mouth"},
        "attire": {"Mirelle": {"wearing": []}, "Hinami": {"wearing": []}},
        "entities": {"Mirelle": {"name": "Mirelle", "kind": "person"},
                     "Hinami": {"name": "Hinami", "kind": "person"}},
        "poses": {"Mirelle": pose},
    }


def _after(detail, diff):
    return merge_scene_with_diff(_scene(detail), diff)["poses"]["Mirelle"]


class TestAHeldBodyThatMovesLeavesTheProse:
    def test_the_carriage_clause_is_retired(self):
        pose = _after("tongue curled around Hinami, holding her at the back "
                      "of the mouth", {"positions": {"Hinami": "throat"}})
        assert pose["detail"] == ""

    def test_the_holders_own_arrangement_survives(self):
        """She is still sitting on the bed; she is simply not holding them.
        Posture, support and the relation fields are hers and no move of
        somebody else's touches them."""
        pose = _after("holding Hinami against her chest",
                      {"positions": {"Hinami": "throat"}})
        assert pose["posture"] == "sitting"
        assert pose["support"] == "wide_bed"

    def test_an_alias_counts_as_naming_them(self):
        scene = _scene("cradling the little fox against her chest")
        scene["entities"]["Hinami"]["aliases"] = ["the little fox"]
        out = merge_scene_with_diff(scene, {"positions": {"Hinami": "throat"}})
        assert out["poses"]["Mirelle"]["detail"] == ""


class TestWhatItLeavesAlone:
    def test_watching_is_not_holding(self):
        """`_CONTACT_BOUND_POSE_WORDS` is the engine's one list for a clause
        that depends on something being held -- shared with the transfer twin
        rather than duplicated, because a second competing list is how two
        ledgers start disagreeing."""
        pose = _after("watching Hinami across the room",
                      {"positions": {"Hinami": "throat"}})
        assert pose["detail"] == "watching Hinami across the room"

    def test_a_body_that_did_not_move_keeps_its_clause(self):
        pose = _after("holding Hinami close", {})
        assert pose["detail"] == "holding Hinami close"

    def test_a_detail_naming_nobody_is_untouched(self):
        pose = _after("one hand flat on the silk, shoulders loose",
                      {"positions": {"Hinami": "throat"}})
        assert pose["detail"] == "one hand flat on the silk, shoulders loose"

    def test_the_movers_own_pose_is_their_own_business(self):
        scene = _scene("still")
        scene["poses"]["Hinami"] = {"posture": "prone",
                                    "detail": "held at the back of the mouth"}
        out = merge_scene_with_diff(scene, {"positions": {"Hinami": "throat"}})
        assert out["poses"]["Hinami"]["detail"] == \
            "held at the back of the mouth"

    def test_a_newly_placed_body_has_not_moved(self):
        """Absent from the previous map means newly placed, not relocated."""
        scene = _scene("holding Corin close")
        scene["entities"]["Corin"] = {"name": "Corin", "kind": "person"}
        out = merge_scene_with_diff(scene, {"positions": {"Corin": "room"}})
        assert out["poses"]["Mirelle"]["detail"] == "holding Corin close"


class TestAnObjectIsTheOtherTwinsBusiness:
    def test_a_portable_thing_moving_does_not_fire_this_one(self):
        scene = _scene("holding the padd against her chest")
        scene["entities"]["padd"] = {"name": "padd", "kind": "object",
                                     "portable": True}
        scene["positions"]["padd"] = "room"
        out = merge_scene_with_diff(scene, {"positions": {"padd": "throat"}})
        assert out["poses"]["Mirelle"]["detail"] == \
            "holding the padd against her chest"
