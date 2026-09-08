"""The body ledgers are subject-keyed too: review 2026-09-07, Section H
residual on B4 (`R-vitals-subject-keyed`).

`normalize_scene_subjects` exists so `==` is correct again -- it folds every
subject-keyed ledger onto one spelling per being, which is the floor under
`same_subject` and under `survival.vitals_entry_key`. `_SUBJECT_KEYED` listed
eight ledgers; `spatial_frames` partitioned a frame split on "those plus the
body ledgers keyed the same way", naming `vitals` and `overlays`. Two lists of
one thing, and the fold read the shorter: chat 82's woman, held as
`positions["Dr. Sarah Moon"]` beside `attire["Sarah Moon"]`, folded in seven
ledgers and kept both spellings in the one that records her air and her
injuries.
"""

from __future__ import annotations

from world.spatial import (_SUBJECT_KEYED, normalize_scene_subjects)
from world.spatial_frames import _FRAME_SUBJECT_LEDGERS
from world.survival import vitals_of


def _two_spellings():
    return {
        "entities": {"Dr. Sarah Moon": {"name": "Dr. Sarah Moon",
                                        "aliases": ["Sarah Moon"]}},
        "positions": {"Dr. Sarah Moon": "annex"},
        "vitals": {"Sarah Moon": {"air": 0.4, "stamina": 1.0,
                                  "nourishment": 1.0, "injury": 0.6}},
        "overlays": {"Sarah Moon": ["soot on both hands"]},
    }


def test_the_body_ledgers_are_in_the_tuple():
    assert "vitals" in _SUBJECT_KEYED
    assert "overlays" in _SUBJECT_KEYED


def test_the_frame_split_reads_the_same_list():
    """Two lists of one thing is how the fold and the split disagreed."""
    assert tuple(_FRAME_SUBJECT_LEDGERS) == tuple(_SUBJECT_KEYED)


def test_the_vitals_row_folds_onto_the_spelling_every_other_ledger_uses():
    scene = _two_spellings()

    folded = normalize_scene_subjects(scene)

    assert list(scene["vitals"]) == ["Dr. Sarah Moon"]
    assert list(scene["overlays"]) == ["Dr. Sarah Moon"]
    assert ("vitals", "Sarah Moon", "Dr. Sarah Moon") in folded
    # And her air is still hers: the fold moves the key, never the record.
    assert vitals_of(scene, "Dr. Sarah Moon")["air"] == 0.4


def test_the_row_already_under_the_canonical_spelling_wins():
    """Two rows for one body is a conflict, and the one every reader has been
    running on keeps the key -- the same rule the other ledgers fold by."""
    scene = _two_spellings()
    scene["vitals"]["Dr. Sarah Moon"] = {"air": 1.0, "stamina": 1.0,
                                         "nourishment": 1.0, "injury": 0.0}

    normalize_scene_subjects(scene)

    assert list(scene["vitals"]) == ["Dr. Sarah Moon"]
    assert vitals_of(scene, "Dr. Sarah Moon")["air"] == 1.0
