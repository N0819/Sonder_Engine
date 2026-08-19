"""`{{fragment:<name>}}` references in a system-prompt card resolve at load.

Four authored fragments (`category_note`, `book_type_note`, `transit_note`,
`extra_parts_note`) are embedded in seventeen prompt bodies. When each copy
was a hand-maintained paste, editing the fragment and not its copies left two
prompts teaching different rules for the same field -- and in the Japanese
pack ZERO of seventeen copies matched their own fragment, because the
translation pass rendered each one independently. A reference resolved at
card load makes that drift structurally impossible: the card holds the text
once, and every embedding is the same bytes by construction.

The failure mode a reference introduces is a reference that does not resolve
-- an unknown name, a typo, a cycle -- and each of those must fail the PACK
LOAD, not ship a prompt with `{{fragment:foo}}` in it for every story to
read.
"""

import pytest

from language_runtime import (
    LanguagePackError,
    _resolve_prompt_fragments,
    installed_language_packs,
)


def test_a_reference_resolves_wherever_a_string_leaf_sits():
    card = {
        "greeting_note": "SAY HELLO FIRST.",
        "prompts": {"opening": "You are the opener. {{fragment:greeting_note}} Then stop."},
        "specialists": {"social": {"chunks": ["{{fragment:greeting_note}}"]}},
    }
    resolved = _resolve_prompt_fragments(card, "en")
    assert resolved["prompts"]["opening"] == (
        "You are the opener. SAY HELLO FIRST. Then stop.")
    assert resolved["specialists"]["social"]["chunks"][0] == "SAY HELLO FIRST."
    # The fragment itself is still published under its own key.
    assert resolved["greeting_note"] == "SAY HELLO FIRST."


def test_a_fragment_may_reference_another_fragment():
    card = {
        "inner": "the core rule",
        "outer": "Remember {{fragment:inner}} always.",
        "prompts": {"opening": "{{fragment:outer}}"},
    }
    resolved = _resolve_prompt_fragments(card, "en")
    assert resolved["prompts"]["opening"] == "Remember the core rule always."
    assert resolved["outer"] == "Remember the core rule always."


def test_an_unknown_fragment_name_fails_the_load():
    card = {"prompts": {"opening": "{{fragment:no_such_note}}"}}
    with pytest.raises(LanguagePackError) as excinfo:
        _resolve_prompt_fragments(card, "ja")
    message = str(excinfo.value)
    assert "no_such_note" in message
    assert "prompts.opening" in message
    assert "'ja'" in message


def test_a_reference_to_a_non_string_value_is_unknown():
    # `prompts` exists, but a dict cannot be spliced into prompt text.
    card = {"prompts": {"opening": "{{fragment:prompts}}"}}
    with pytest.raises(LanguagePackError, match="prompts"):
        _resolve_prompt_fragments(card, "en")


def test_a_reference_cycle_fails_the_load():
    card = {
        "a": "see {{fragment:b}}",
        "b": "see {{fragment:a}}",
        "prompts": {"opening": "{{fragment:a}}"},
    }
    with pytest.raises(LanguagePackError, match="cycle"):
        _resolve_prompt_fragments(card, "en")


def test_a_misspelled_reference_cannot_ship_as_literal_prompt_text():
    # None of these match the reference grammar, so substitution alone would
    # leave them in the sheet verbatim -- for every story to read. The load
    # must refuse instead.
    for spelling in (
        "{{fragment:Category_Note}}",   # case is not part of the grammar
        "{{fragment category_note}}",   # missing the colon
        "{{fragment:}}",                # missing the name
    ):
        card = {"category_note": "x", "prompts": {"opening": spelling}}
        with pytest.raises(LanguagePackError, match="prompts.opening"):
            _resolve_prompt_fragments(card, "en")


def _string_leaves(value):
    if isinstance(value, str):
        yield value
    elif hasattr(value, "items"):
        for child in value.values():
            yield from _string_leaves(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _string_leaves(child)


def test_no_installed_pack_publishes_an_unresolved_reference():
    """Black-box restatement of the loader guarantee: whatever the raw JSON
    holds, the card a consumer sees -- prompt assembly, the editor,
    project_check -- never contains `{{fragment` in any string leaf."""
    packs = installed_language_packs(refresh=True)
    assert packs
    for pack in packs.values():
        if not pack.story:
            continue
        for leaf in _string_leaves(pack.card("system_prompts")):
            assert "{{fragment" not in leaf, pack.id


def test_a_preset_body_carrying_a_placeholder_is_refused():
    """Presets are applied AFTER card load, so a `{{fragment:...}}` in a
    preset body has no resolver left to meet -- it would reach the model as
    literal text. The import path must say so instead of storing it."""
    from llm.prompts import PRESET_FILE_KIND, PRESET_FILE_VERSION, preset_import_document

    document = {
        "kind": PRESET_FILE_KIND,
        "version": PRESET_FILE_VERSION,
        "name": "leaky",
        "language": "en",
        "prompts": {"narrator": "Narrate. {{fragment:transit_note}}"},
    }
    with pytest.raises(ValueError, match="narrator"):
        preset_import_document(document)
