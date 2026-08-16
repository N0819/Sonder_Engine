"""An object the beat sets down is not a person.

`track_background_presences` has a `positions` path -- anything the beat placed
in a room is in the scene by construction -- guarded by an inert-entity rule
shared with the entity harvest. It has failed twice, in two different ways.

First, the lookup was keyed by the entity's DISPLAY NAME while being queried
with a `positions` key, which is an entity ID.
`utility_sash_with_pouches_hinami` never matched "utility sash with pouches
hinami", the lookup returned None, and None is not an inert kind -- so the rule
never fired for any entity whose id differs from its name. Live, chat 75 turns
57-60: a shed utility sash was admitted as a background presence, handed a
housekeeper persona, and given three turns of dialogue.

Second, and only visible once the lookup worked: `kind` is a FREEFORM model
string, and the model writes compound nouns. Of the four objects tracked as
presences across chats 74-76, three were tagged `device`, `key card` and
`currency pouch` -- none of which any deny-list would hold, and which cannot be
added to it because the generic words are omitted on purpose so a sentient
robot stays trackable. `_is_inert_presence_candidate` answers that structurally
instead, and these tests pin the two ways a PERSON can be portable.
"""

from __future__ import annotations

import commit
from schemas import _ANIMATE_ENTITY_KINDS


def _inert(ent, scene=None, eid="e1"):
    """Ask the real predicate, so this file cannot drift from the code."""
    return commit._is_inert_presence_candidate(scene or {}, eid, ent)


SASH_ID = "utility_sash_with_pouches_hinami"
SASH = {
    "name": "Utility Sash With Pouches Hinami",
    "kind": "object",
    "portable": True,
    "state": {"clothing": True, "worn_by": None, "shed": True},
}
CLERK = {"name": "night clerk", "kind": "character"}


# -- the original regression: an id-keyed position must resolve ---------------

def test_a_shed_garment_is_inert():
    assert _inert(SASH, eid=SASH_ID) is True


def test_a_person_is_not_inert():
    """The whole reason the positions path exists is the hotel clerk who
    arrived in `positions` and nothing else (chat 72 turn 47)."""
    assert _inert(CLERK) is False


def test_an_unenumerated_agent_kind_still_defaults_to_inclusion():
    """`kind` is freeform. An agent kind nobody listed -- 'spirit', 'drone' --
    must still be tracked; that is the trade the deny-list exists to make."""
    assert _inert({"name": "Wandering Spirit", "kind": "spirit"}) is False


def test_a_bare_name_with_no_entity_def_is_not_inert():
    """Nothing to judge it on, and a name the beat PLACED IN A ROOM is in the
    scene by construction. Recorded so a change to that trade is deliberate."""
    assert _inert({}) is False


# -- the freeform-kind hole, measured in chats 74-76 -------------------------

def test_the_objects_a_deny_list_could_never_hold():
    """All three were live tracked presences. None is an inert KIND."""
    for kind, name in (("device", "The sonic screwdriver"),
                       ("key card", "hotel key card"),
                       ("currency pouch", "small worn leather pouch")):
        assert kind not in commit._INERT_ENTITY_KINDS, kind
        assert _inert({"name": name, "kind": kind, "portable": True}) is True, name


def test_an_ambiguous_kind_is_kept_when_it_is_not_portable():
    """'machine' and 'device' are left off the deny-list ON PURPOSE so a
    sentient robot tagged that way stays trackable. Portability, not the word,
    is what separates it from a screwdriver."""
    assert _inert({"name": "Sentry Drone", "kind": "device"}) is False
    assert _inert({"name": "War Machine", "kind": "machine"}) is False


# -- the two ways a PERSON is pocketable ------------------------------------

def test_a_shrunken_character_is_not_an_object():
    """She is portable AND she is the resized one, so she carries a `scales`
    entry -- and that entry is precisely what makes her small. Live, chat 41."""
    scene = {"scales": {"Hinami": {"factor": 0.05}}}
    ent = {"name": "Hinami", "kind": "kitsune", "portable": True}
    assert _inert(ent, scene, eid="Hinami") is False


def test_a_baseline_character_pocketed_by_a_giant_is_not_an_object():
    """The other direction, and it fails differently: SHE is not the resized
    one, so there is no `scales` entry to find. Only `attire` catches her."""
    scene = {"attire": {"Korin": {"torso": "linen shirt"}}}
    ent = {"name": "Korin", "kind": "person", "portable": True}
    assert _inert(ent, scene, eid="Korin") is False


def test_an_undressed_pocketed_person_survives_on_kind_alone():
    """Neither half of the body predicate can help -- no attire, no scales --
    so the animate allow-list is the only thing left holding her. This is why
    that third term exists: `_is_body_entity` scores 23 of 88 animate entities
    as things, `night clerk` among them."""
    ent = {"name": "Korin", "kind": "person", "portable": True}
    assert "person" in _ANIMATE_ENTITY_KINDS
    assert _inert(ent, {}, eid="Korin") is False


def test_the_stated_residual_is_still_the_behaviour():
    """Documented in the predicate rather than papered over: a carried,
    undressed, baseline-sized body whose kind is on no animate list reads as a
    thing. Pinned so it is a known cost, not a surprise -- it is survivable
    only because a presence that SPEAKS is harvested from dialogue_log before
    ever reaching this gate."""
    ent = {"name": "Pocket Familiar", "kind": "homunculus", "portable": True}
    assert "homunculus" not in _ANIMATE_ENTITY_KINDS
    assert _inert(ent, {}) is True


def test_a_portable_object_is_inert_even_with_an_unknown_kind():
    """The general case the three live objects are instances of."""
    assert _inert({"name": "Tea Set", "kind": "porcelain service",
                   "portable": True}) is True
