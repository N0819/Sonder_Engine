"""Three ledgers already hold what a thing IS; none of them held what it smells of.

Scent has been a permission system with nothing to permit: `scent_level`
grades reach as none|muffled|full, cards can author a nose, perception
computes a graded map per perceiver -- and no card, entity, substance or
diff anywhere says what anything smells LIKE, so no builder could ever emit
one.

The fact goes where the thing already is, rather than into a fourth ledger:

  * a body's standing smell beside its standing appearance, on the card
    (`embodiment.scent`, sibling of `embodiment.visible`);
  * an object's smell on the scene entity (`SceneEntityDef.scent`, sibling of
    `light_source` -- what this thing emits);
  * deposited matter's smell on the substance record, which is the commonest
    case in play and already carries the material, its placement and how much
    of it there is.

Each of the three has a trap this file pins, and each trap is one the
codebase has already sprung once on a neighbouring field.
"""

import copy

from llm.schemas import SceneEntityDef, validate_llm_output_strict
from story.character_schema import (
    character_scent, default_character_data, default_persona_data,
    normalize_character_data, normalize_persona_data, persona_scent,
)
from story.scene import scent_of
from world.spatial import apply_substance_ops, merge_scene_with_diff


# ---------------------------------------------------------------- entities

def _scene():
    return {
        "rooms": {"bakehouse": {"name": "Bakehouse", "adjacent": []}},
        "entities": {
            "oven_01": {
                "name": "Bread Oven", "kind": "fixture",
                "description": "A domed brick oven.",
                "scent": "hot flour and woodsmoke",
                "state": {"lit": True},
            },
        },
        "positions": {"oven_01": "bakehouse"},
    }


def test_a_declared_entity_scent_survives_the_validation_round_trip():
    """The reason `enclosure` and `light_source` are declared fields rather
    than passengers: `model_dump()` drops what the model does not declare, so
    an authored scent would come back absent before anything could read it."""
    report = validate_llm_output_strict("director_objects", {
        "entities": {"censer_01": {"name": "Censer", "kind": "object",
                                   "scent": "cold frankincense"}},
    })
    assert report.valid, report.errors
    assert report.output["entities"]["censer_01"]["scent"] \
        == "cold frankincense"


def test_the_field_is_optional_and_absent_means_absent():
    assert SceneEntityDef(name="Rock").scent is None


def test_a_partial_redeclaration_does_not_erase_a_standing_scent():
    """`_merge_entity` copies the fields it knows and passes everything else
    through verbatim -- and validation fills an undeclared field with its
    default first, so a `scent` outside `_ENTITY_DEFAULT_FIELDS` would be
    written back as None on every later beat that touched the oven. That is
    exactly what made `enclosure` and `light_source` settable only at
    creation for as long as they were missing from that map."""
    scene = _scene()
    merged = merge_scene_with_diff(scene, {
        "entities": {"oven_01": {"name": "Bread Oven", "kind": "fixture",
                                 "scent": None, "state": {"lit": False}}},
    })
    assert merged["entities"]["oven_01"]["scent"] == "hot flour and woodsmoke"
    assert merged["entities"]["oven_01"]["state"]["lit"] is False


def test_a_deliberate_change_of_scent_still_lands():
    merged = merge_scene_with_diff(_scene(), {
        "entities": {"oven_01": {"name": "Bread Oven",
                                 "scent": "scorched crust"}},
    })
    assert merged["entities"]["oven_01"]["scent"] == "scorched crust"


# -------------------------------------------------------------- substances

def _substance_scene():
    return {
        "rooms": {"cellar": {"name": "Cellar", "adjacent": []}},
        "positions": {"Mara": "cellar", "flagstones": "cellar"},
        "entities": {"flagstones": {"name": "Flagstones", "kind": "fixture"}},
        "contacts": [],
        "substances": [],
    }


def test_a_deposit_carries_its_smell_into_the_ledger():
    scene = apply_substance_ops(_substance_scene(), [
        {"op": "add", "source": "Mara", "source_part": "forearm",
         "substance": "blood", "target": "flagstones", "placement": "surface",
         "target_part": "flagstones", "amount": "a spreading pool",
         "scent": "wet iron"},
    ])
    [record] = scene["substances"]
    assert record["scent"] == "wet iron"


def test_a_re_description_updates_the_smell_of_the_pool_it_joins():
    """`scent` follows `amount` and `detail`, not the identity fields: the
    same matter from the same source on the same region is ONE pool that a
    later release re-describes, and how it smells NOW is part of that
    re-description. Putting it in `_substance_id` instead would file drying
    blood as a second puddle beside fresh."""
    scene = _substance_scene()
    scene = apply_substance_ops(scene, [
        {"op": "add", "source": "Mara", "source_part": "forearm",
         "substance": "blood", "target": "flagstones", "placement": "surface",
         "target_part": "flagstones", "scent": "wet iron"},
    ])
    scene = apply_substance_ops(scene, [
        {"op": "add", "source": "Mara", "source_part": "forearm",
         "substance": "blood", "target": "flagstones", "placement": "surface",
         "target_part": "flagstones", "scent": "drying iron, going sweet"},
    ])
    assert len(scene["substances"]) == 1
    assert scene["substances"][0]["scent"] == "drying iron, going sweet"


def test_a_silent_re_description_does_not_blank_a_standing_smell():
    """The other direction of the same rule: an op that says nothing about
    the smell is silence, not an erasure."""
    scene = _substance_scene()
    scene = apply_substance_ops(scene, [
        {"op": "add", "source": "Mara", "source_part": "forearm",
         "substance": "blood", "target": "flagstones", "placement": "surface",
         "target_part": "flagstones", "scent": "wet iron"},
    ])
    scene = apply_substance_ops(scene, [
        {"op": "add", "source": "Mara", "source_part": "forearm",
         "substance": "blood", "target": "flagstones", "placement": "surface",
         "target_part": "flagstones", "amount": "a wider pool"},
    ])
    assert scene["substances"][0]["scent"] == "wet iron"
    assert scene["substances"][0]["amount"] == "a wider pool"


def test_a_substance_scent_survives_the_state_diff_round_trip():
    report = validate_llm_output_strict("director_contact", {
        "substance_ops": [
            {"op": "add", "source": "Mara", "source_part": "forearm",
             "substance": "blood", "target": "flagstones",
             "placement": "surface", "scent": "wet iron"},
        ],
    })
    assert report.valid, report.errors
    assert report.output["substance_ops"][0]["scent"] == "wet iron"


# -------------------------------------------------------------------- cards

def test_a_card_can_author_a_standing_body_smell():
    data = default_character_data("Kesa")
    assert data["embodiment"]["scent"] == ""
    data["embodiment"]["scent"] = "woodsmoke and cold iron"
    assert character_scent(normalize_character_data(data)) \
        == "woodsmoke and cold iron"


def test_a_persona_can_author_one_too():
    data = default_persona_data("You")
    data["embodiment"]["scent"] = "rain on wool"
    assert persona_scent(normalize_persona_data(data)) == "rain on wool"


def test_normalizing_a_sheet_that_never_heard_of_scent_reads_as_no_smell():
    """Every card in every existing story. An authoring gap is silence, and
    silence must never become a smell."""
    data = default_character_data("Kesa")
    data["embodiment"].pop("scent", None)
    assert character_scent(normalize_character_data(data)) == ""


def test_scent_of_dispatches_on_sheet_kind_like_its_siblings():
    character = default_character_data("Kesa")
    character["embodiment"]["scent"] = "woodsmoke"
    persona = default_persona_data("You")
    persona["embodiment"]["scent"] = "rain on wool"
    assert scent_of(character) == "woodsmoke"
    assert scent_of(persona) == "rain on wool"


def test_a_card_edit_does_not_disturb_a_scent_it_did_not_touch():
    data = normalize_character_data(default_character_data("Kesa"))
    data["embodiment"]["scent"] = "woodsmoke and cold iron"
    again = normalize_character_data(copy.deepcopy(data))
    assert character_scent(again) == "woodsmoke and cold iron"


# ------------------------------------------------------------------ authoring

def _js_function_body(source, header):
    """One top-level JS function's text, by brace depth.

    Copied in spirit from `tests/test_attire_authoring.py`, which learned the
    hard way that slicing a function by a blank-line convention makes a test
    about clothing fail on a reformat.
    """
    start = source.index(header)
    i, depth = source.index("(", start), 0
    while True:
        if source[i] == "(":
            depth += 1
        elif source[i] == ")":
            depth -= 1
            if depth == 0:
                break
        i += 1
    i, depth = source.index("{", i), 0
    for j in range(i, len(source)):
        if source[j] == "{":
            depth += 1
        elif source[j] == "}":
            depth -= 1
            if depth == 0:
                return source[start:j + 1]
    raise AssertionError("unbalanced braces after %r" % header)


def test_both_card_editors_present_and_save_a_body_scent():
    """There are two card editors and it is easy to build a field into one of
    them. Three halves are asked per editor: a widget, its place in the
    rendered modal, and the read back into the saved sheet -- a field
    presented and never read is authored text that vanishes on save, and a
    widget never appended is a field nobody can find.

    `carryUnpresentedFields` would have kept an unpresented `scent` alive
    through a card edit, which is why this is about the AUTHORING surface and
    not about data loss.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    editor = (root / "static/js/ui-next/library-editors/character-persona.js").read_text(encoding="utf-8")
    sections = (root / "static/js/ui-next/library-editors/person-sections.js").read_text(encoding="utf-8")
    assert "createPersonSectionEditor" in editor
    assert "createSchemaNode" in sections
    assert "JSON.stringify(state.draft, null, 2)" in editor
    assert "services.authoring.stage(parsed, { render: true })" in editor
