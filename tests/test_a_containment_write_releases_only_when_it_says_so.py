"""A containment write releases a standing record only when it SAYS release.

Audit world_spatial_truth F5 (2026-11-01, CONFIRMED CORRUPTION): the schema is
`containment: dict[str, Optional[dict]]`, so `{Pip: {mode: "container"}}`
(restating only the mode), `{Pip: {holder: "jar"}}` and `{Pip: ["jar"]}` all
validate -- and each returned None from `_clean_containment`, which the merge
read as a release: the jarred body walked free with no report. Silence and
defaults are never erasure anywhere else in the merge; only an explicit empty
value is the documented release (`encoder/containment.txt`).
"""

import pytest

from world.spatial import merge_scene_with_diff


def _scene():
    return {
        "rooms": {"study": {"name": "Study", "adjacent": []}},
        "positions": {"Pip": "study", "jar": "study", "Ada": "study"},
        "entities": {"jar": {"name": "jar", "kind": "object", "container": True}},
        "attire": {"Pip": {}, "Ada": {}},
        "scales": {"Pip": 0.05},
        "contained": {"Pip": {"in": "jar", "mode": "container"}},
        "contacts": [],
    }


@pytest.mark.parametrize("raw", [
    {"mode": "container"}, {"holder": "jar"}, ["jar"], {"in": "Pip"},
])
def test_a_write_that_does_not_clean_keeps_the_standing_record(raw):
    report = []
    merged = merge_scene_with_diff(_scene(), {"containment": {"Pip": raw}},
                                   inventory_report=report)
    assert merged["contained"].get("Pip", {}).get("in") == "jar"
    assert report, "a refused containment write is told to the Director"


@pytest.mark.parametrize("raw", [None, {}, ""])
def test_an_explicit_empty_value_releases(raw):
    merged = merge_scene_with_diff(_scene(), {"containment": {"Pip": raw}})
    assert "Pip" not in merged["contained"]


def test_a_well_formed_write_still_moves_the_body():
    merged = merge_scene_with_diff(
        _scene(), {"containment": {"Pip": {"in": "Ada", "mode": "held"}}})
    assert merged["contained"]["Pip"]["in"] == "Ada"
