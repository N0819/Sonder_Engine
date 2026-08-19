"""A pronoun paradigm is a mapping, whatever the card offered.

Found by the A/B harness rather than by the audit: a persona authored with
`"pronouns": "they/them"` -- the most natural thing anyone writes -- was
accepted by `normalize_persona_data` and then raised
`AttributeError: 'str' object has no attribute 'values'` on the NARRATOR step
of the first turn, and of every turn after it.

The normalizer checked PRESENCE and not TYPE: `value.get("pronouns") or
{default}` treats a non-empty string as a valid paradigm, because a non-empty
string is truthy. Every downstream reader assumes a mapping --
`_narration_person_counts` iterates `.values()`, the fidelity guards index by
role -- so the card was valid at the door and fatal three stages later.
"""

from __future__ import annotations

import pytest

from story.character_schema import (normalize_character_data,
                                    normalize_persona_data)

NORMALIZERS = (normalize_character_data, normalize_persona_data)


@pytest.mark.parametrize("normalize", NORMALIZERS)
class TestAParadigmIsAlwaysAMapping:
    def test_a_string_is_read_rather_than_discarded(self, normalize):
        """It is what people write. Falling back to a default would lose an
        authored fact to a formatting choice."""
        out = normalize({"identity": {"name": "Wren",
                                      "pronouns": "they/them/their"}})
        assert out["identity"]["pronouns"] == {
            "subject": "they", "object": "them", "possessive": "their"}

    def test_two_parts_repeat_the_last_rather_than_leaving_a_gap(self, normalize):
        out = normalize({"identity": {"name": "Sable", "pronouns": "she/her"}})
        assert out["identity"]["pronouns"] == {
            "subject": "she", "object": "her", "possessive": "her"}

    def test_commas_work_too(self, normalize):
        out = normalize({"identity": {"name": "Halden",
                                      "pronouns": "he, him, his"}})
        assert out["identity"]["pronouns"]["possessive"] == "his"

    @pytest.mark.parametrize("bad", [42, [], ["they", "them"], True, "   "])
    def test_anything_unreadable_falls_back_to_a_full_paradigm(
            self, normalize, bad):
        out = normalize({"identity": {"name": "X", "pronouns": bad}})
        assert set(out["identity"]["pronouns"]) == {
            "subject", "object", "possessive"}
        assert all(out["identity"]["pronouns"].values())

    def test_a_partial_mapping_is_completed_not_left_ragged(self, normalize):
        out = normalize({"identity": {"name": "X",
                                      "pronouns": {"subject": "ze"}}})
        assert out["identity"]["pronouns"]["subject"] == "ze"
        assert all(out["identity"]["pronouns"].values())

    def test_the_result_is_always_iterable_the_way_readers_iterate_it(
            self, normalize):
        """The exact call that died: `_narration_person_counts` does
        `(player_pronouns or {}).values()`."""
        out = normalize({"identity": {"name": "X", "pronouns": "they/them"}})
        assert list(out["identity"]["pronouns"].values())
