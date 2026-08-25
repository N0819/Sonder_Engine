"""One overlay is one named thing, however the beat that wrote it spelled it.

`overlays` says what a body currently looks like. The channel accepts two
representations of the same fact -- a bare line of prose, and a `{name,
description}` record -- and until 2026-08-25 they could never meet: named
records deduped only against named records, and bare prose only by exact list
membership. So one overlay could stand up to three times.

Measured, chat 88 turn 67, one body's list:

    ["bright red across her cheeks", "flush",
     "golden shimmer rippling outward across bare skin",
     {"name": "flush", "description": "golden shimmer rippling outward
      across bare skin"}]

-- the last three entries are one overlay written three ways, and every
observer's appearance view rendered all three. The same shape stood in chats
86 and 87, and chat 78 held each of three overlays twice (the record and a
bare copy of its own description): 11 duplicate entries of 91 corpus-wide,
and zero entries anywhere carrying no handle at all.

Identity is the entry's HANDLE SET, which deliberately does NOT include
`subject`: on the chat 78 spelling `subject` names the BODY the overlay is
about (`persist/commit_attire._overlay_texts_by_subject` reads it that way),
so three distinct overlays there share one subject and folding on it would
silently delete two authored appearance facts -- the exact failure this rule
exists to prevent.

These are pure-function tests. They import through `persist.commit`, the
facade, because they only CALL the helpers -- the definer-not-facade rule
applies to MONKEYPATCHING, which nothing here does.
"""

from __future__ import annotations

from persist.commit import (
    _dedupe_overlay_entries,
    _merge_overlays,
    _overlay_handles,
)


def _merged(standing, incoming, body="Ada"):
    sc = {"overlays": {body: list(standing)}}
    _merge_overlays(sc, {body: list(incoming)})
    return sc["overlays"][body]


class TestHandles:
    def test_a_record_is_handled_by_its_name_and_its_description(self):
        assert _overlay_handles({"name": "Flush", "description": "Red Cheeks"}) \
            == {"flush", "red cheeks"}

    def test_the_other_stored_description_spelling_counts_too(self):
        assert "a grey smear" in _overlay_handles(
            {"id": "smear_01", "desc": "A grey smear"})

    def test_the_body_an_overlay_is_about_is_not_a_handle(self):
        """chat 78 keys overlays by overlay name and carries `subject` as the
        BODY. Three overlays there share one subject; folding on it would
        collapse them into one."""
        handles = _overlay_handles(
            {"subject": "Ada", "description": "shivering"})
        assert handles == {"shivering"}

    def test_a_bare_line_is_handled_by_itself(self):
        assert _overlay_handles("  Flush  ") == {"flush"}

    def test_an_entry_with_nothing_to_identify_it_has_no_handle(self):
        assert _overlay_handles({"kind": "smudge", "shade": "grey"}) == set()
        assert _overlay_handles("") == set()


class TestMerge:
    def test_a_record_replaces_a_bare_line_equal_to_its_name(self):
        out = _merged(["flush"],
                      [{"name": "flush", "description": "red across the brow"}])
        assert out == [{"name": "flush", "description": "red across the brow"}]

    def test_a_record_also_absorbs_a_bare_line_equal_to_its_description(self):
        out = _merged(["red across the brow"],
                      [{"name": "flush", "description": "red across the brow"}])
        assert out == [{"name": "flush", "description": "red across the brow"}]

    def test_a_bare_restatement_of_a_standing_record_is_silence(self):
        """The named record is the richer account of the same fact; a bare
        copy of its name or its description adds nothing and must not grow
        the list or displace the record."""
        record = {"name": "flush", "description": "red across the brow"}
        for restatement in ("flush", "red across the brow"):
            assert _merged([record], [restatement]) == [record]

    def test_two_records_under_one_name_keep_newest_wins(self):
        out = _merged([{"name": "flush", "description": "faint"}],
                      [{"name": "flush", "description": "deepening"}])
        assert out == [{"name": "flush", "description": "deepening"}]

    def test_two_distinct_overlays_coexist(self):
        out = _merged([{"name": "flush", "description": "red across the brow"}],
                      [{"name": "soot", "description": "streaked at the jaw"}])
        assert len(out) == 2

    def test_distinct_bare_lines_still_accumulate(self):
        out = _merged(["ears drooping"], ["shoulders squared"])
        assert out == ["ears drooping", "shoulders squared"]

    def test_the_six_entry_cap_holds(self):
        out = _merged([f"mark {i}" for i in range(6)], ["mark 6"])
        assert len(out) == 6
        assert out[-1] == "mark 6"

    def test_a_body_the_diff_never_mentions_is_healed_too(self):
        """The heal pass is what lets an already-dirty ledger recover with
        no migration: every chat carrying the measured duplication is one
        commit away from clean, whether or not that beat touched the body."""
        sc = {"overlays": {"Ada": [
            "flush", {"name": "flush", "description": "red across the brow"}]}}
        _merge_overlays(sc, {"Bex": ["soot at the jaw"]})
        assert sc["overlays"]["Ada"] == [
            {"name": "flush", "description": "red across the brow"}]

    def test_an_overlay_map_that_is_not_a_map_is_left_alone(self):
        sc = {"overlays": []}
        _merge_overlays(sc, {"Ada": ["flush"]})
        assert sc["overlays"] == []


class TestHeal:
    def test_the_live_shape_collapses_to_two_entries(self):
        """chat 88 t67, story-neutral: a stale earlier description, a bare
        name, a bare description, and the record carrying both. Only the
        record's two restatements are duplicates; the stale line is a
        different fact and ageing is not this rule's job (UNBUILT 1.10)."""
        healed = _dedupe_overlay_entries([
            "red across the brow",
            "blush",
            "gold shimmer across the skin",
            {"name": "blush", "description": "gold shimmer across the skin"},
        ])
        assert healed == [
            "red across the brow",
            {"name": "blush", "description": "gold shimmer across the skin"},
        ]

    def test_the_record_and_a_bare_copy_of_its_description_collapse(self):
        """chat 78's spelling: the record keyed by overlay name, with a bare
        copy of its own description beside it."""
        record = {"subject": "Ada", "description": "shivering from the cold"}
        healed = _dedupe_overlay_entries([record, "shivering from the cold"])
        assert healed == [record]

    def test_records_sharing_one_subject_are_never_collapsed(self):
        rows = [{"subject": "Ada", "description": "head lolling"},
                {"subject": "Ada", "description": "shivering"},
                {"subject": "Ada", "description": "looks unwell"}]
        assert _dedupe_overlay_entries(rows) == rows

    def test_an_entry_with_no_handle_passes_through_untouched(self):
        rows = [{"kind": "smudge"}, "flush", {"kind": "smudge"}]
        assert _dedupe_overlay_entries(rows) == rows

    def test_a_clean_ledger_is_returned_unchanged(self):
        rows = ["ears drooping", "shoulders squared",
                {"name": "soot", "description": "streaked at the jaw"}]
        assert _dedupe_overlay_entries(rows) == rows


class TestMalformedLedgers:
    """The heal now runs on EVERY commit, so the shapes it can meet are no
    longer only the ones a diff brought with it.

    `overlays` present with a JSON null is the one that bites: `get` and
    `setdefault` both hand back the stored None, so a guard that only turns
    away a non-dict lets it through -- and the heal then raises inside
    `persist/commit.py`, the sole persistence boundary, where any domain
    failure rolls the whole turn back. The EMPTY diff is the crashing case,
    which is the common one. No in-tree writer produces that shape and none
    of the 77 stored blobs carries it (scanned 2026-08-25); an archive or
    checkpoint written elsewhere is the exposure.
    """

    def test_a_null_overlay_map_is_reset_rather_than_read(self):
        sc = {"overlays": None}
        _merge_overlays(sc, {})
        assert sc["overlays"] == {}

    def test_a_null_overlay_map_still_takes_this_beat_s_overlays(self):
        sc = {"overlays": None}
        _merge_overlays(sc, {"Ada": ["flush"]})
        assert sc["overlays"] == {"Ada": ["flush"]}

    def test_a_scene_with_no_overlay_key_at_all_gains_one(self):
        sc = {}
        _merge_overlays(sc, {"Ada": ["flush"]})
        assert sc["overlays"] == {"Ada": ["flush"]}
