"""A charter body the scene presents as an entity is not also carried by its
charter's crowd.

DESIGN_BACKGROUND_PRESENTATION B2: a charter body is ground exactly when
nothing this beat presents it individually, and `members_of` learns what is
presented from the background-presence ledger, which the COMMIT writes. A
body the Director binds to an entity this beat (`charter_ref`, the identity
floor's binding) is presented by the scene before any ledger knows. Live,
chat 167 turn 4616 (validation story, 2026-10-10): the opening bound the
landlord as an entity and the inn's crowd still counted him -- the view said
"The middle-aged square landlord ... is close by" and "a handful of
landlords and potmen", and the page "a handful of other landlords".
"""

from agents.common import charter_ground_for_room


def _inn():
    return {"key": "inn", "naming": {}, "watch": {}, "presented_bodies": [],
            "bodies": {key: {"key": key, "name": name, "place": "taproom",
                             "home_post": key.split(":")[0]}
                       for key, name in (("landlord:0001", "Llanarfryn Eigalyn"),
                                         ("barman:0001", "Rhiinwyr Llanelias"),
                                         ("barman:0002", "Bryinwyr Rhiadd"),
                                         ("barman:0003", "Aelig Morwr"))}}


def test_a_body_bound_to_a_scene_entity_is_not_ground():
    # The face is the first barman by key, so the landlord is not fronted:
    # only the scene's binding can keep him out of the crowd.
    scene = {"rooms": {"taproom": {"name": "the Taproom"}},
             "entities": {"Llanarfryn Eigalyn": {
                 "name": "Llanarfryn Eigalyn", "kind": "person",
                 "charter_ref": {"charter": "inn", "body": "landlord:0001"}}},
             "positions": {"Llanarfryn Eigalyn": "taproom"}}
    ground = charter_ground_for_room(1, scene, "taproom", {"charters": [_inn()]})
    assert ("inn", "landlord:0001") not in ground["carried"]
    for crowd in ground["crowds"]:
        assert "landlord" not in crowd["composition"], crowd["composition"]


def test_an_unbound_body_is_still_ground():
    scene = {"rooms": {"taproom": {"name": "the Taproom"}}, "entities": {},
             "positions": {}}
    ground = charter_ground_for_room(1, scene, "taproom", {"charters": [_inn()]})
    carried = {body for _key, body in ground["carried"]}
    assert "landlord:0001" in carried and len(carried) == 3, carried  # one fronted as a face
