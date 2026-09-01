"""`attire` regions are a closed engine set, and both packs must spell them.

Sibling of `tests/test_published_vocabularies.py`, for the case that pack
already had in EN and lost in JA. `story.attire.REGIONS` is eight members and
every reader is exact-match after casefold -- `if region not in REGIONS:
continue` at story/attire.py:532, 882 and 2294 -- so a region written in any
other spelling is not rejected, it is DROPPED, and the garment silently keeps
whatever the engine defaulted it to.

The EN body/attire chunk published all eight; the JA one had translated them
(`領域：頭、胴、腕、手、腰、股間、脚、足。`), which is the one thing a value
vocabulary must never be. Measured 2026-09-01: `head`, `arms`, `hands` and
`feet` then appeared NOWHERE in the whole JA body specialist sheet -- core plus
all four chunks -- so the Japanese body hand had no spelling for those regions
at all.

`tools/project_check.py`'s en/ja parity guard structurally cannot catch this:
`CANONICAL_LANGUAGE_TOKEN` only spans names containing `_` or `.` or wrapped in
quotes, and a closed set written as bare comma-separated words matches none of
those. This test is that missing half, bound to the engine constant rather than
restating it, so widening REGIONS without publishing it fails here.
"""

from __future__ import annotations

import pytest

from language_runtime import installed_language_packs
from story.attire import REGIONS

ATTIRE_REGION_LANGUAGES = ("en", "ja")


def _body_attire_sheet(language: str) -> str:
    """Everything the body specialist receives when `attire` is granted."""
    card = installed_language_packs()[language].card("system_prompts")
    spec = card["specialists"]["body"]
    return str(spec["core"]) + str(spec["chunks"]["attire"])


@pytest.mark.parametrize("language", ATTIRE_REGION_LANGUAGES)
def test_every_region_the_engine_accepts_is_spelled_in_the_attire_sheet(
        language):
    sheet = _body_attire_sheet(language)
    missing = sorted(region for region in REGIONS if region not in sheet)
    assert not missing, (
        f"{language}: the hand that writes `covers`/`placement` is never "
        f"shown these region names, and anything else it writes is dropped "
        f"in silence: {missing}")


@pytest.mark.parametrize("language", ATTIRE_REGION_LANGUAGES)
def test_the_region_list_is_published_as_one_run(language):
    """Publication means the SET is visible, not that the words happen to
    occur. Before the fix four of the eight survived in JA only incidentally,
    inside coverage examples and the waist/groin clause -- which teaches four
    spellings and hides the other four."""
    sheet = _body_attire_sheet(language)
    joined = ", ".join(REGIONS)
    assert joined in sheet, (
        f"{language}: the eight regions are not published together as "
        f"{joined!r}; scattered mentions are not an enumeration")


def test_an_unpublished_spelling_is_dropped_rather_than_refused():
    """The cost the publication removes, in the reader the sheet writes to.

    `coerce_diff_shape` is what turns the body specialist's
    `add:[{name,covers:[...]}]` into a placement, and its region filter is
    membership in REGIONS (story/attire.py:1553). A word outside the eight
    does not fail the add -- the garment still goes on, at whatever regions
    its NAME implies, which is the exact case the sheet's own paragraph
    exists to override.
    """
    from story.attire import coerce_diff_shape
    published = coerce_diff_shape({"add": [{"name": "wool cap",
                                            "covers": ["head"]}]})
    assert published == {"add": ["wool cap"],
                         "placement": {"wool cap": ["head"]}}
    translated = coerce_diff_shape({"add": [{"name": "wool cap",
                                             "covers": ["頭"]}]})
    assert translated == {"add": ["wool cap"]}
