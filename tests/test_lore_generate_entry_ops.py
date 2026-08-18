"""The single-book lore generator read a key its own prompt never offers.

`generator_lorebook` documents exactly one output shape for entries,
`entry_ops`, and its closing rule tells a model that receives no `"stage"`
key -- which is every call `generate_lore_entries` makes -- to "return
complete entry_ops in this one response". The word `entries` appears nowhere
in that prompt as an output key. `generate_lore_entries` nevertheless read
`parsed.get("entries")` and raised "Lore generator returned no entries" when
it was missing, so a fully compliant model response failed the route at
`POST /api/lorebooks/{id}/generate` every time. Reported against alpha 7.2;
the function was byte-identical on the 8.0 line.

The staged tree generator calls the same prompt and has always folded both
shapes through `_normalize_entry_ops`, so two callers of one prompt disagreed
about its contract -- and the one that was wrong was the one an author reaches
from the lorebook entry list.

What is pinned here: the documented shape works, the legacy shape a custom
preset or a loose model may still emit keeps working, the prompt's own richer
fields survive the trip instead of being dropped on the floor, and a genuinely
empty response is still a loud failure rather than a silent success.

Two neighbours of the same drift are pinned at the bottom. `apply_lorebook_plan`
dispatches on an op's `"op"` key, so an entry_ops response that omits it -- the
prompt documents the key, which is not the same as a model always sending it --
was written nowhere while the run still reported success. And `importance`
reaches `float()` inside `add_lore`, so one model answering `"high"` aborted an
entire approved plan inside its transaction and took every other entry with it.
Both are folded on the way in, in `_normalize_entry_ops`, rather than guarded
at each of the three call sites that would have to remember.
"""

from __future__ import annotations

import json

import pytest

from story import importers
from core.db import q


@pytest.fixture
def book(temp_db):
    return temp_db.qi(
        "INSERT INTO lorebooks(name,chat_id,book_type,summary) "
        "VALUES(?,?,?,?)",
        ("Canon", None, "general", "The kingdom."),
    )


def _stub(monkeypatch, response):
    captured = {}

    def fake(role, system, user, **kwargs):
        captured["system"] = system
        captured["user"] = json.loads(user)
        return json.dumps(response) if isinstance(response, dict) else response

    monkeypatch.setattr(importers, "chat_complete", fake)
    return captured


ENTRY_OPS_RESPONSE = {
    "analysis": {"themes": ["salt"], "missing_areas": []},
    "book_ops": [],
    "link_ops": [],
    "entry_ops": [
        {
            "op": "create",
            "book_id": 1,
            "keys": "salt road, caravan",
            "content": "The salt road runs east from the delta.",
            "category": "location",
            "title": "The Salt Road",
            "knowledge_tag": "common",
            "knowledge_range": "local",
            "knowledge_locations": ["delta"],
            "importance": 0.8,
            "aliases": ["saltway"],
            "source_notes": "generated",
        },
        {
            "op": "create",
            "book_id": 1,
            "keys": "delta",
            "content": "The delta is where the salt is cut.",
            "category": "location",
            "title": "The Delta",
        },
    ],
}


def test_compliant_entry_ops_response_creates_entries(temp_db, book, monkeypatch):
    _stub(monkeypatch, ENTRY_OPS_RESPONSE)

    entry_ids = importers.generate_lore_entries(book, "Write the salt lore.")

    assert len(entry_ids) == 2
    rows = q(
        "SELECT keys, content, title, category FROM lore_entries "
        "WHERE lorebook_id=? ORDER BY id",
        (book,),
    )
    assert [r["title"] for r in rows] == ["The Salt Road", "The Delta"]
    assert rows[0]["category"] == "location"


def test_entry_ops_fields_are_not_discarded(temp_db, book, monkeypatch):
    _stub(monkeypatch, ENTRY_OPS_RESPONSE)

    entry_ids = importers.generate_lore_entries(book, "Write the salt lore.")

    row = q(
        "SELECT importance, aliases, knowledge_tag, knowledge_range, "
        "knowledge_locations, source_notes FROM lore_entries WHERE id=?",
        (entry_ids[0],),
        one=True,
    )
    assert row["importance"] == pytest.approx(0.8)
    assert json.loads(row["aliases"]) == ["saltway"]
    assert row["knowledge_tag"] == "common"
    assert row["knowledge_range"] == "local"
    assert json.loads(row["knowledge_locations"]) == ["delta"]
    assert row["source_notes"] == "generated"


def test_legacy_entries_response_still_accepted(temp_db, book, monkeypatch):
    _stub(monkeypatch, {
        "entries": [
            {
                "keys": "salt road",
                "content": "The salt road runs east.",
                "category": "location",
                "title": "The Salt Road",
            },
        ],
    })

    entry_ids = importers.generate_lore_entries(book, "Write the salt lore.")

    assert len(entry_ids) == 1
    row = q(
        "SELECT title, category FROM lore_entries WHERE id=?",
        (entry_ids[0],), one=True,
    )
    assert row["title"] == "The Salt Road"
    assert row["category"] == "location"


def test_update_op_without_a_usable_id_is_kept_not_dropped(
    temp_db, book, monkeypatch
):
    """This path never shows the model an entry id, so it cannot address one.

    Misfiling one entry is fixable by hand; silently discarding a generated
    entry is not -- the same trade `_normalize_book_id` and
    `apply_lorebook_plan` already make.
    """
    _stub(monkeypatch, {
        "entry_ops": [
            {
                "op": "update",
                "keys": "salt road",
                "content": "The salt road runs east.",
                "category": "location",
                "title": "The Salt Road",
            },
        ],
    })

    entry_ids = importers.generate_lore_entries(book, "Expand the salt lore.")

    assert len(entry_ids) == 1


def test_bad_category_is_still_guessed(temp_db, book, monkeypatch):
    _stub(monkeypatch, {
        "entry_ops": [
            {
                "op": "create",
                "keys": "the west stair",
                "content": "A stair climbs the west wing to the upper hall.",
                "category": "not-a-category",
            },
        ],
    })

    entry_ids = importers.generate_lore_entries(book, "Map the keep.")

    row = q(
        "SELECT category FROM lore_entries WHERE id=?",
        (entry_ids[0],), one=True,
    )
    assert row["category"] in importers.LORE_CATEGORIES
    assert row["category"] != "not-a-category"


@pytest.mark.parametrize("response", [
    {"entry_ops": [], "entries": []},
    {"analysis": {"themes": []}},
    {"entry_ops": [{"op": "create", "content": "   "}]},
    "not json at all",
])
def test_an_empty_generation_is_still_a_loud_failure(
    temp_db, book, monkeypatch, response
):
    """Tolerating two input shapes must not become tolerating nothing at all.

    A run that proposes no usable entry has to reach the author as an error;
    reporting "added 0" would present a failed generation as a finished one.
    """
    _stub(monkeypatch, response)

    with pytest.raises(RuntimeError):
        importers.generate_lore_entries(book, "Write the salt lore.")

    assert q(
        "SELECT COUNT(*) AS n FROM lore_entries WHERE lorebook_id=?",
        (book,), one=True,
    )["n"] == 0


# ---- the same drift, one call site over ----------------------------------

def test_a_non_numeric_importance_does_not_abort_the_write(
    temp_db, book, monkeypatch
):
    """`float("high")` inside add_lore used to cost the whole generation.

    In the plan path that write is one transaction, so a single malformed
    number would have rolled back every other entry in an approved plan.
    """
    _stub(monkeypatch, {
        "entry_ops": [
            {"op": "create", "keys": "salt", "content": "Salt is cut here.",
             "category": "other", "importance": "high"},
        ],
    })

    entry_ids = importers.generate_lore_entries(book, "Write the salt lore.")

    row = q(
        "SELECT importance FROM lore_entries WHERE id=?",
        (entry_ids[0],), one=True,
    )
    assert row["importance"] == pytest.approx(0.5)


def test_an_op_less_entry_still_reaches_the_book(temp_db, book):
    """An applied plan reported success and wrote nothing.

    `apply_lorebook_plan` selects on `entry_op["op"]`, so an entry_ops item
    that never carried one fell through both branches and was discarded in
    silence -- the failure a generator can least afford, because the author
    has already approved the plan and has no way to tell it was lost.
    """
    plan = {
        "book_ops": [],
        "link_ops": [],
        "entry_ops": importers._normalize_entry_ops(
            {"entry_ops": [
                {"keys": "salt", "content": "Salt is cut here.",
                 "category": "other"},
                {"op": "update", "keys": "delta",
                 "content": "The delta feeds the pans.", "category": "other"},
            ]},
            book,
        ),
    }

    result = importers.apply_lorebook_plan(plan, root_id=book)

    assert result["entries_created"] == 2
    assert q(
        "SELECT COUNT(*) AS n FROM lore_entries WHERE lorebook_id=?",
        (book,), one=True,
    )["n"] == 2
