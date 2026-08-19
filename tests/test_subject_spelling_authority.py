"""A cast body is spelled the way its sheet spells it.

`DESIGN_SUBJECT_SPELLING_AUTHORITY.md`. `canonical_subject_map` folds every
spelling of a being onto the scene ENTITY's own `name`, on the stated ground
that "for a mirrored cast member [it] IS the display name every reader already
expects". Live in chat 82 ("Sarah Moon — Hinami attempt 2") it was not: the
sheet said "Sarah Moon" and the Director minted the entity "Dr. Sarah Moon",
one of her aliases. Two cast-aware folds then disagreed about whether aliases
count — `_heal_attire_identity_keys` said yes, `canonicalize_positions` said no
— so one woman was `attire["Sarah Moon"]` and `positions["Dr. Sarah Moon"]` at
once, and every spatial read from her own name found nothing.

The repair is not a different fold direction. It makes the fold's assumption
TRUE: an entity that unambiguously answers to exactly one registered character
is renamed to that character's sheet name, at the seams that already hold the
cast, and the spelling it loses is demoted to an alias. The entity KEY is never
touched — renaming id-keyed rows is what cost eleven tests the first time
identity folding was tried.
"""

from __future__ import annotations

import copy
import json

from agents.common import cast_spelling_policy, reconcile_cast_entity_names
from world.spatial import (canonical_subject_map, normalize_scene_subjects,
                           room_of)


def _sheet(name, uid, aliases=()):
    return {"identity": {"name": name, "uid": uid, "aliases": list(aliases)}}


def _cast(*sheets):
    return [{"id": i + 1, "sheet": json.dumps(s), "status": "active"}
            for i, s in enumerate(sheets)]


MOON = _sheet("Sarah Moon", "char_moon", ["Dr. Moon", "Dr. Sarah Moon"])


def _chat82_scene():
    """The live shape: entity keyed AND named by the honorific, ledgers split
    between the two spellings."""
    return {
        "entities": {"Dr. Sarah Moon": {
            "name": "Dr. Sarah Moon", "kind": "character",
            "aliases": ["Sarah Moon", "Dr. Moon"]}},
        "positions": {"Dr. Sarah Moon": "annex"},
        "poses": {"Dr. Sarah Moon": {"posture": "seated upright"}},
        "stations": {"Dr. Sarah Moon": {"at": "desk", "near": []}},
        "orientation": {"Dr. Sarah Moon": {"came_from": None, "focus": None}},
        "attire": {"Sarah Moon": {"wearing": ["white lab coat"], "state": []}},
    }


def test_the_chat_82_shape_folds_onto_the_sheet():
    sc = _chat82_scene()

    reconcile_cast_entity_names(sc, _cast(MOON))
    normalize_scene_subjects(sc)

    for ledger in ("positions", "poses", "stations", "orientation", "attire"):
        assert list(sc[ledger]) == ["Sarah Moon"], (ledger, sc[ledger])
    assert sc["entities"]["Dr. Sarah Moon"]["name"] == "Sarah Moon"
    assert "Dr. Sarah Moon" in sc["entities"]["Dr. Sarah Moon"]["aliases"]
    assert "Dr. Sarah Moon" in sc["entities"], "the entity KEY must not move"
    assert room_of(sc, "Sarah Moon") == "annex"
    assert room_of(sc, "Dr. Sarah Moon") == "annex", \
        "prose already written with the honorific must still resolve"


def test_it_is_a_fixpoint():
    """It runs on the standing scene at every commit and a checkpoint restore
    replays it, so a second pass must fold nothing and change nothing."""
    sc = _chat82_scene()
    reconcile_cast_entity_names(sc, _cast(MOON))
    normalize_scene_subjects(sc)
    once = copy.deepcopy(sc)

    assert reconcile_cast_entity_names(sc, _cast(MOON)) == []
    assert normalize_scene_subjects(sc) == []
    assert sc == once


def test_the_tardis_guard_holds():
    """The eleven-test tripwire. A non-cast object keyed by an id that differs
    from its name only by case keeps its id-keyed position: no fold fires on
    identity alone."""
    sc = {"entities": {"tardis": {"name": "TARDIS", "kind": "object"}},
          "positions": {"tardis": "grounds"}}

    reconcile_cast_entity_names(sc, _cast(MOON))
    normalize_scene_subjects(sc)

    assert sc["positions"] == {"tardis": "grounds"}
    assert canonical_subject_map(sc) == {}


def test_the_yuki_guard_holds():
    """One character's alias is another's name often enough in fiction. A real
    name outranks somebody else's nickname for it, in the record as well as in
    the lookup."""
    yuki = _sheet("Yuki", "char_yuki")
    other = _sheet("Amane", "char_amane", ["Yuki"])
    sc = {"entities": {"e_other": {"name": "Amane", "aliases": ["Yuki"]}},
          "attire": {"Yuki": {"wearing": ["yukata"], "state": []}},
          "positions": {"Yuki": "hall", "Amane": "yard"}}

    reconcile_cast_entity_names(sc, _cast(yuki, other))
    normalize_scene_subjects(sc)

    assert sc["attire"]["Yuki"]["wearing"] == ["yukata"], \
        "Yuki's wardrobe was folded onto the other woman"
    assert sc["positions"]["Yuki"] == "hall"
    assert "Yuki" not in sc["entities"]["e_other"].get("aliases", [])


def test_the_promotion_shape_folds_onto_the_sheet():
    """A promoted background presence: the entity still carries the epithet it
    was minted under, and `positions` holds both spellings in different rooms.
    The one already under the canonical spelling wins -- the first-writer rule
    of `normalize_scene_subjects`, unchanged."""
    garret = _sheet("Garret", "char_garret", ["Onlooker"])
    sc = {"entities": {"onlooker_1": {"name": "Onlooker",
                                      "aliases": ["Garret"]}},
          "positions": {"Garret": "tavern", "Onlooker": "street"}}

    reconcile_cast_entity_names(sc, _cast(garret))
    normalize_scene_subjects(sc)

    assert sc["positions"] == {"Garret": "tavern"}
    assert sc["entities"]["onlooker_1"]["name"] == "Garret"


def test_ambiguity_resolves_to_nothing():
    """Two cast rows answering to one spelling are two beings. Folding them
    into one is strictly worse than leaving two spellings of one."""
    a = _sheet("Ash", "char_a", ["The Twin"])
    b = _sheet("Bram", "char_b", ["The Twin"])
    sc = {"entities": {"twin": {"name": "The Twin"}},
          "positions": {"The Twin": "road"}}
    before = copy.deepcopy(sc)

    assert reconcile_cast_entity_names(sc, _cast(a, b)) == []
    assert sc == before

    canonical, forms = cast_spelling_policy(_cast(a, b))
    assert canonical("The Twin") == "The Twin"
    assert "the twin" not in forms


def test_two_entities_for_one_character_are_left_to_the_merge():
    """Renaming both would mint the duplicate key `_dedup_duplicate_entity_keys`
    exists to collapse. That is a merge defect, not this pass's business."""
    sc = {"entities": {"e1": {"name": "Dr. Sarah Moon"},
                       "e2": {"name": "Dr. Moon"}}}
    before = copy.deepcopy(sc)

    assert reconcile_cast_entity_names(sc, _cast(MOON)) == []
    assert sc == before


def test_it_reports_what_it_renamed():
    sc = _chat82_scene()

    assert reconcile_cast_entity_names(sc, _cast(MOON)) == [
        ("Dr. Sarah Moon", "Dr. Sarah Moon", "Sarah Moon")]


def test_orientation_is_a_subject_keyed_ledger():
    """It is keyed by WHO like its six siblings, and was missed by the fold --
    so `entity_arc`/`entity_side` answered None for an observer asking under
    their own sheet name."""
    from world.spatial import _SUBJECT_KEYED

    assert "orientation" in _SUBJECT_KEYED


def test_the_alias_fold_is_reachable_for_a_name_keyed_entity():
    """The alias loop used to sit inside the id-guard, which an entity keyed by
    its own name trips -- so its aliases never folded, which is the commonest
    shape there is."""
    sc = {"entities": {"Dr. Sarah Moon": {"name": "Dr. Sarah Moon",
                                          "aliases": ["Sarah Moon"]}},
          "positions": {"Dr. Sarah Moon": "annex"},
          "attire": {"Sarah Moon": {"wearing": [], "state": []}}}

    assert canonical_subject_map(sc).get("sarah moon") == "Dr. Sarah Moon"
