"""The Writers' Room may cite a row by the handle the tool handed it.

`search_lore`, `read_lore` and `scan_lore` return `{"citation": "lore:42",
"id": 42, ...}` and their tool description says "Cite an entry by its
citation when you rely on it". The harvest of what was read knew neither:
`citation` was not one of `ID_KEYS`, and `_add` kept only strings, so an
integer id was never recorded either. A claim citing exactly what it was told
to cite read as unsupported and was demoted to a proposal -- the expensive
direction of the error, as `ID_KEYS`' own comment says (story_attire_import
audit F17).
"""

from __future__ import annotations

from story import room_citations as rc


RESULT = {"hits": [{"citation": "lore:42", "id": 42, "uid": "e_abc",
                    "book_id": 7, "title": "The Salt Road"}]}


def _verdicts(*cites):
    with rc.reading():
        rc.note_reads("search_lore", RESULT)
        checked = rc.check_claims([{"text": "claim %d" % n, "cites": [c]}
                                   for n, c in enumerate(cites)])
    return [c["verdict"] for c in checked["claims"]]


def test_the_citation_the_tool_handed_out_is_supported():
    assert _verdicts("lore:42") == ["supported"]


def test_an_integer_id_is_citable_as_written_or_as_text():
    assert _verdicts(42, "42", 7) == ["supported"] * 3


def test_a_string_uid_still_is():
    assert _verdicts("e_abc") == ["supported"]


def test_a_flag_is_not_an_id():
    with rc.reading():
        rc.note_reads("read_scene", {"rooms": [{"id": True, "uid": "r1"}]})
        rows = rc.rows_read()
    assert "True" not in rows and "r1" in rows
