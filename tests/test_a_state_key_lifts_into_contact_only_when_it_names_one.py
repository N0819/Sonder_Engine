"""Contact written into an entity's `state` lifts into the ledger only when
the key really names a touch, and a key that cannot lift stays where it was.

Audit world_spatial_structure_light F3 (2026-11-01, CONFIRMED mechanism): the
lift (run at every merge) matched its verb fragments as SUBSTRINGS of the key
and popped the key before anything validated the record. So `eyes_on: Hinami`
became Elyra's eyes TOUCHING Hinami, `expression_toward` a press (part 'ex'),
`interest` a rest, `threshold` a hold, `spine_toward` a pin, a value
`pink_ribbon_around_...` a pin ('pink' starts with 'pin'); a passive
`held_by: Hinami` on a lantern became "the lantern holds Hinami"; and
`gaze: resting_on_Hinami's_face` produced a record `apply_contact_ops` refused
-- with the state key deleted anyway. The module's own rule: "inventing a hold
is worse than missing one". Design.md:496 says `gaze` is never touched.
"""

import pytest

from world.spatial import contacts_from_entity_state


def _scene(state, *, who="elyra"):
    sc = {"rooms": {"hall": {"name": "Hall", "adjacent": []}},
          "positions": {"Elyra": "hall", "Hinami": "hall", "lantern": "hall"},
          "entities": {"elyra": {"name": "Elyra", "kind": "person", "state": {}},
                       "lantern": {"name": "lantern", "kind": "object", "state": {}}},
          "attire": {"Elyra": {}, "Hinami": {}},
          "contacts": []}
    sc["entities"][who]["state"] = dict(state)
    return sc


@pytest.mark.parametrize("state", [
    {"eyes_on": "Hinami"}, {"focus_on": "Hinami"},
    {"expression_toward": "Hinami"}, {"interest": "Hinami"},
    {"threshold": "Hinami"}, {"spine_toward": "Hinami"},
    {"gaze": "resting_on_Hinami's_face"},
    {"hand": "pink_ribbon_around_Hinami's_wrist"},
])
def test_an_idiom_or_a_part_of_a_word_invents_no_touch_and_keeps_its_key(state):
    sc = contacts_from_entity_state(_scene(state))
    assert sc["contacts"] == [], sc["contacts"]
    assert sc["entities"]["elyra"]["state"] == state


@pytest.mark.parametrize("key", ["held_by", "carried_by"])
def test_a_passive_key_is_not_lifted_backwards(key):
    sc = contacts_from_entity_state(_scene({key: "Hinami"}, who="lantern"))
    assert sc["contacts"] == []
    assert sc["entities"]["lantern"]["state"] == {key: "Hinami"}


@pytest.mark.parametrize("state, manner", [
    ({"leaning_against": "Hinami"}, "lean"),
    ({"tails_wrapped_around": "Hinami"}, "wrap"),
    ({"hand_position": "beneath_Hinami's_shift_caressing_bare_side"}, "caress"),
    ({"arms": "pinned_around_Hinami"}, "pin"),
])
def test_a_real_contact_key_still_lifts(state, manner):
    sc = contacts_from_entity_state(_scene(state))
    assert [c["manner"] for c in sc["contacts"]] == [manner]
    assert sc["entities"]["elyra"]["state"] == {}
