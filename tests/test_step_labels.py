"""The phase names the reader sees live in one harvestable table.

`tools/extract_ui_catalog.py`'s `READER_FACING_TABLES` names a `STEP_LABELS` in
`agents/runtime.py`; there was none, and the labels were inline literals inside
`build_plan`, `establishment_plan`, `_background_stage_label` and one
`_step_stream` call. So every pipeline phase name shipped untranslated in every
language pack while the extractor's promise looked kept.
"""

from __future__ import annotations

from agents.runtime import (STEP_LABELS, build_plan, establishment_plan,
                            step_label)


def test_every_planned_label_comes_from_the_table():
    published = set(STEP_LABELS.values())
    plan = build_plan({"flow": {"needs_mapping": True}}, [])
    plan += establishment_plan()
    for key, label in plan:
        assert label in published, (key, label)


def test_the_character_label_is_a_template_not_a_format_string_at_the_site():
    assert "{name}" in STEP_LABELS["character"]
    assert step_label("character", name="Mara") == "Character · Mara"


def test_an_unnamed_step_falls_back_to_its_key():
    # Extension steps (`ext:<id>:<key>`) carry labels from their own manifest,
    # so the table is not the authority on them and must not invent one.
    assert step_label("ext:demo:pulse") == "ext:demo:pulse"


def test_the_opening_narrator_keeps_its_own_name():
    labels = dict(establishment_plan())
    assert labels["narrator"] == STEP_LABELS["narrator.establish"]
    assert labels["narrator"] != STEP_LABELS["narrator"]
