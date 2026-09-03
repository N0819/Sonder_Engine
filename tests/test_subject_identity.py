"""One spelling per being, so `==` can be right again.

A character can be registered cast AND present as a scene entity with its own
id, and nothing joins the two records. The Director then writes whichever it
reaches for, and both are correct. Five separate defects in one investigation
were the same consequence: some function compared `"Elyndra"` against
`"elyndra_succubus"` with `==`, got False, and did nothing — silently, because
every spatial query answers an unresolved subject with its safe-closed default,
which is indistinguishable from distance.

`same_subject` closed those five. It is a FLOOR, not a fix: it only helps at
comparison sites somebody remembered to route through it, and every new site is
a fresh chance to write `==` again. A guard that must be remembered is a guard
that will be forgotten.

`normalize_scene_subjects` is the fix. Run at merge, before anything resolves
one ledger against another, it leaves exactly one key per being — after which
`==` is correct because there is nothing left for it to be wrong about.

THE SCOPE IS THE HARD PART, and getting it wrong is worse than the defect. The
first version folded on identity alone and broke eleven tests: `positions`
legitimately keys objects, fixtures and unregistered presences by entity id,
and readers resolve them that way, so renaming those to display names stranded
carried lights, derived stations and destruction cascades. Two rules keep it
narrow:

  * fold only when the canonical name is ALREADY live as a subject spelling
    somewhere in this scene — the defect is two records for one being, not
    "ids ought to be names"; and
  * an id differing from its name only by case ("tardis" for "TARDIS") is its
    own evidence, and must not count.
"""

from __future__ import annotations

import pytest

from world.spatial import (
    canonical_subject,
    canonical_subject_map,
    merge_scene_with_diff,
    normalize_scene_subjects,
    same_subject,
    spatial_rel_between,
)

HOST = "Elyn"
HOST_ID = "elyn_entity"
ALIAS = "The Keeper"


def _scene():
    """The live shape: one being under two spellings, plus an object that is
    legitimately keyed by id alone."""
    return {
        "rooms": {"hall": {"name": "Hall", "adjacent": []}},
        "entities": {
            HOST_ID: {"name": HOST, "kind": "person", "aliases": [ALIAS]},
            "lamp_7f3": {"name": "Lamp", "kind": "fixture"},
        },
        "positions": {HOST: "hall", "lamp_7f3": "hall", "Wren": "hall"},
        "attire": {HOST: {}, "Wren": {}},
        "scales": {"Wren": 0.05},
        "contained": {"Wren": {"in": HOST_ID, "mode": "inside"}},
        "contacts": [{"actor": ALIAS, "target": "Wren"}],
    }


class TestTheFold:
    def test_a_containment_record_naming_the_entity_id_is_folded(self):
        sc = _scene()
        normalize_scene_subjects(sc)
        assert sc["contained"]["Wren"]["in"] == HOST

    def test_a_contact_naming_an_alias_is_folded(self):
        sc = _scene()
        normalize_scene_subjects(sc)
        assert sc["contacts"][0]["actor"] == HOST

    def test_a_ledger_key_under_the_entity_id_is_folded(self):
        sc = _scene()
        sc["scales"][HOST_ID] = 1.0
        normalize_scene_subjects(sc)
        assert HOST in sc["scales"] and HOST_ID not in sc["scales"]

    def test_value_folds_are_reported_too(self):
        """`contained.in` naming one spelling while `positions` uses another
        is the shape that started this, and it leaves no key to report."""
        sc = _scene()
        report = normalize_scene_subjects(sc)
        assert ("contained.in", HOST_ID, HOST) in report

    def test_a_following_target_is_folded(self):
        sc = _scene()
        sc["following"] = {"Wren": {"target": ALIAS}}
        normalize_scene_subjects(sc)
        assert sc["following"]["Wren"]["target"] == HOST


class TestWhatMustNotBeFolded:
    def test_a_lone_object_id_key_survives(self):
        """`positions` legitimately keys objects and fixtures by id and
        readers resolve them that way. Renaming those stranded carried lights,
        derived stations and destruction cascades -- eleven tests' worth."""
        sc = _scene()
        normalize_scene_subjects(sc)
        assert sc["positions"]["lamp_7f3"] == "hall"
        assert "Lamp" not in sc["positions"]

    def test_an_id_that_differs_only_by_case_is_not_its_own_evidence(self):
        """"tardis" for "TARDIS". The id counts as a live spelling, so without
        this the entity folds itself away and its position disappears."""
        sc = {"entities": {"tardis": {"name": "TARDIS"}},
              "positions": {"tardis": "road", "Ellie": "road"}}
        normalize_scene_subjects(sc)
        assert sc["positions"]["tardis"] == "road"

    def test_two_entities_with_one_name_fold_nothing(self):
        """Two of the same machine in two rooms is exactly the case that must
        not be guessed, and folding both onto one key merges two beings."""
        sc = {
            "entities": {"d1": {"name": "A Dalek"}, "d2": {"name": "A Dalek"}},
            "positions": {"d1": "hall", "d2": "yard", "A Dalek": "hall"},
        }
        normalize_scene_subjects(sc)
        assert sc["positions"]["d1"] == "hall"
        assert sc["positions"]["d2"] == "yard"

    def test_an_ambiguous_alias_folds_nothing(self):
        sc = _scene()
        sc["entities"]["other"] = {"name": "Other", "aliases": [ALIAS]}
        sc["positions"]["Other"] = "hall"
        normalize_scene_subjects(sc)
        assert sc["contacts"][0]["actor"] == ALIAS

    def test_a_room_is_not_a_subject(self):
        """`positions` VALUES are rooms. Naming a place is not naming
        somebody, and a room sharing an entity's name must not be rewritten."""
        sc = _scene()
        before = dict(sc["positions"])
        normalize_scene_subjects(sc)
        assert sc["positions"]["Wren"] == before["Wren"]

    def test_a_station_anchor_is_not_a_subject(self):
        """`stations[x]["at"]` names an anchor -- a place inside a room."""
        sc = _scene()
        sc["stations"] = {"Wren": {"at": "lamp_7f3", "near": []}}
        normalize_scene_subjects(sc)
        assert sc["stations"]["Wren"]["at"] == "lamp_7f3"

    def test_an_unregistered_presence_keeps_its_own_name(self):
        sc = _scene()
        sc["positions"]["A Voice"] = "hall"
        normalize_scene_subjects(sc)
        assert "A Voice" in sc["positions"]


class TestTheCanonicalName:
    def test_it_resolves_every_spelling(self):
        sc = _scene()
        for spelling in (HOST_ID, ALIAS, HOST):
            assert canonical_subject(sc, spelling) == HOST

    def test_an_unknown_string_is_returned_unchanged(self):
        assert canonical_subject(_scene(), "Nobody") == "Nobody"
        assert canonical_subject(_scene(), "") == ""

    def test_the_map_never_rewrites_one_being_into_another(self):
        sc = _scene()
        mapping = canonical_subject_map(sc)
        assert mapping.get("wren") in (None, "Wren")


class TestAfterTheFoldPlainEqualityWorks:
    def test_the_comparison_that_started_all_of_this(self):
        """The point of the whole exercise: not that `same_subject` exists,
        but that a reader who forgets it is no longer wrong."""
        merged = merge_scene_with_diff(_scene(), {})
        assert merged["contained"]["Wren"]["in"] == HOST
        assert merged["contacts"][0]["actor"] == HOST

    def test_the_enclosure_is_recognised_through_the_merge(self):
        merged = merge_scene_with_diff(_scene(), {})
        rel = spatial_rel_between(merged, "Wren", HOST)
        assert rel.get("inside_source") is True

    def test_same_subject_still_holds_the_floor(self):
        """Kept for everything that never went through a merge -- raw model
        output arrives spelled however the model felt like spelling it."""
        sc = _scene()
        assert same_subject(sc, HOST_ID, HOST)
        assert same_subject(sc, ALIAS, HOST)
        assert not same_subject(sc, HOST, "Wren")


def test_the_merge_folds_before_it_derives():
    """Order is load-bearing. `derive_contained_positions` resolves its
    carrier against `positions`; if the fold ran after, it would resolve the
    unfolded spelling, find nothing, and skip -- silently, which is how the
    original defect survived a whole story."""
    import inspect

    from world import spatial
    src = inspect.getsource(spatial.merge_scene_with_diff)
    assert src.index("normalize_scene_subjects(merged)") < \
        src.index("derive_contained_positions(merged")
