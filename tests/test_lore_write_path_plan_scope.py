"""apply_lorebook_plan must not write outside the tree the plan was made for.

The generator's apply path took the model's integer ids at face value:
`_plan_parent_id` checked only that a parent EXISTED anywhere in the database,
and an `{"op":"update","id":N}` entry op reached `update_lore` with no
ownership check at all -- `UPDATE lore_entries SET ... WHERE id=?`, no
lorebook_id, no chat_id, no canon_locked. That matters because the model is
INSTRUCTED to emit update ops when `allow_updates` is true (the default) while
`_lore_gen_context` sends it NO entry ids -- so every update op the model
emits carries an invented integer, aimed at a live table holding thousands of
entries across every chat (measured on the owner's database: 2,322 entries,
ids 9-3880, ~20 chats). Reproduced before the fix: a plan generated for chat
A overwrote a canon_locked entry belonging to chat B, and parented a chat-A
book under chat B's book, and reported success.

The rule pinned here is scope, not identity: every integer the plan names --
update targets, create-op book ids, parent ids, link endpoints -- must
resolve inside the subtree of the book the plan was generated for (plus books
this same plan just created), or be refused. Refusals are RECORDED in the
result's `skipped` list rather than silently swallowed, which also pins the
MASTER-030 half: `add_lorebook_link`'s cross-scope ValueError used to vanish
into a bare `except: pass` while the route returned ok.
"""

from __future__ import annotations

import time

import pytest

from core.db import q
from story.importers import apply_lorebook_plan, _plan_parent_id


def _chat(db, name="Chat"):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        (name, "", time.time()),
    )


def _book(db, name, chat_id=None, parent_id=None):
    return db.qi(
        "INSERT INTO lorebooks(name,chat_id,book_type,summary,parent_id) "
        "VALUES(?,?,?,?,?)",
        (name, chat_id, "general", "", parent_id),
    )


def _entry(db, book_id, keys, content, locked=0, title=None, importance=0.5):
    return db.qi(
        "INSERT INTO lore_entries(lorebook_id,keys,content,canon_locked,"
        "title,importance) VALUES(?,?,?,?,?,?)",
        (book_id, keys, content, locked, title, importance),
    )


@pytest.fixture
def two_chats(temp_db):
    chat_a = _chat(temp_db, "A")
    chat_b = _chat(temp_db, "B")
    root_a = _book(temp_db, "A root", chat_id=chat_a)
    child_a = _book(temp_db, "A child", chat_id=chat_a, parent_id=root_a)
    book_b = _book(temp_db, "B book", chat_id=chat_b)
    return {
        "db": temp_db, "chat_a": chat_a, "chat_b": chat_b,
        "root_a": root_a, "child_a": child_a, "book_b": book_b,
    }


class TestUpdateOpScope:
    def test_update_cannot_reach_an_entry_in_another_chats_book(self, two_chats):
        eid = _entry(two_chats["db"], two_chats["book_b"],
                     "harbor", "The harbor belongs to chat B.")

        result = apply_lorebook_plan(
            {"entry_ops": [{"op": "update", "id": eid,
                            "keys": "harbor", "content": "OVERWRITTEN"}]},
            chat_id=two_chats["chat_a"], root_id=two_chats["root_a"],
        )

        row = q("SELECT content FROM lore_entries WHERE id=?", (eid,), one=True)
        assert row["content"] == "The harbor belongs to chat B."
        assert result["entries_created"] == 0
        assert any(s.get("id") == eid for s in result["skipped"])

    def test_update_cannot_reach_a_canon_locked_entry_even_in_scope(self, two_chats):
        eid = _entry(two_chats["db"], two_chats["child_a"],
                     "founding", "The city was founded by exiles.", locked=1)

        result = apply_lorebook_plan(
            {"entry_ops": [{"op": "update", "id": eid,
                            "keys": "founding", "content": "REWRITTEN"}]},
            chat_id=two_chats["chat_a"], root_id=two_chats["root_a"],
        )

        row = q("SELECT content, canon_locked FROM lore_entries WHERE id=?",
                (eid,), one=True)
        assert row["content"] == "The city was founded by exiles."
        assert row["canon_locked"] == 1
        assert any(s.get("id") == eid for s in result["skipped"])

    def test_update_inside_the_subtree_still_applies(self, two_chats):
        eid = _entry(two_chats["db"], two_chats["child_a"],
                     "market", "Old text.")

        result = apply_lorebook_plan(
            {"entry_ops": [{"op": "update", "id": eid,
                            "keys": "market", "content": "New text."}]},
            chat_id=two_chats["chat_a"], root_id=two_chats["root_a"],
        )

        row = q("SELECT content FROM lore_entries WHERE id=?", (eid,), one=True)
        assert row["content"] == "New text."
        assert result["entries_created"] == 1
        assert result["skipped"] == []

    def test_a_hallucinated_id_is_a_recorded_skip_not_a_success(self, two_chats):
        result = apply_lorebook_plan(
            {"entry_ops": [{"op": "update", "id": 99999,
                            "keys": "ghost", "content": "invented"}]},
            chat_id=two_chats["chat_a"], root_id=two_chats["root_a"],
        )
        assert result["entries_created"] == 0
        assert any(s.get("id") == 99999 for s in result["skipped"])


class TestParentAndBookScope:
    def test_parent_outside_the_subtree_falls_back_to_the_plan_root(self, two_chats):
        apply_lorebook_plan(
            {"book_ops": [{"op": "create", "temp_id": "b1", "name": "Stowaway",
                           "parent_id": two_chats["book_b"]}]},
            chat_id=two_chats["chat_a"], root_id=two_chats["root_a"],
        )
        row = q("SELECT parent_id FROM lorebooks WHERE name='Stowaway'",
                one=True)
        assert row["parent_id"] == two_chats["root_a"]

    def test_plan_parent_id_refuses_a_book_that_merely_exists(self, two_chats):
        resolved = _plan_parent_id(
            two_chats["book_b"], {}, two_chats["root_a"], two_chats["chat_a"],
            allowed_books={two_chats["root_a"], two_chats["child_a"]},
        )
        assert resolved == two_chats["root_a"]

    def test_create_op_aimed_at_a_foreign_book_files_into_the_root(self, two_chats):
        apply_lorebook_plan(
            {"entry_ops": [{"op": "create", "book_id": two_chats["book_b"],
                            "keys": "smuggled", "content": "An entry."}]},
            chat_id=two_chats["chat_a"], root_id=two_chats["root_a"],
        )
        row = q("SELECT lorebook_id FROM lore_entries WHERE keys='smuggled'",
                one=True)
        assert row["lorebook_id"] == two_chats["root_a"]


class TestLinkOpScope:
    def test_a_refused_link_is_reported_not_swallowed(self, temp_db):
        # A canon root (chat_id NULL) with a plan applied for chat A: the
        # plan's own created book carries chat A's id, so linking it to the
        # canon root crosses ownership scopes and add_lorebook_link refuses.
        # Before the fix the refusal vanished into a bare except and the
        # route reported ok with links_created: 0 and no explanation.
        chat_a = _chat(temp_db, "A")
        canon_root = _book(temp_db, "Canon", chat_id=None)

        result = apply_lorebook_plan(
            {
                "book_ops": [{"op": "create", "temp_id": "b1", "name": "New"}],
                "link_ops": [{"source_id": "b1", "target_id": canon_root,
                              "relation_type": "related"}],
            },
            chat_id=chat_a, root_id=canon_root,
        )

        assert result["links_created"] == 0
        assert len(result["skipped"]) == 1
        assert "scope" in result["skipped"][0]["reason"].lower() \
            or "ownership" in result["skipped"][0]["reason"].lower()

    def test_the_generator_context_shows_the_model_real_entry_ids(self, two_chats):
        """The other half of refusing invented update ids: `allow_updates`
        defaults true and the prompt invites `{"op":"update","id":N}`, but
        `_lore_gen_context` sent the model no entry ids -- so every update op
        was invented by construction, and with the scope guard alone the
        feature would simply be dead. An id the model was actually shown is
        the only kind that can pass the guard."""
        from story.importers import _lore_gen_context

        eid = _entry(two_chats["db"], two_chats["child_a"], "market",
                     "The market opens at dawn.")
        ctx = _lore_gen_context(two_chats["root_a"])
        assert [e["id"] for e in ctx["existing_entries"]] == [eid]

    def test_a_link_naming_a_book_outside_the_subtree_is_skipped(self, two_chats):
        result = apply_lorebook_plan(
            {"link_ops": [{"source_id": two_chats["root_a"],
                           "target_id": two_chats["book_b"],
                           "relation_type": "related"}]},
            chat_id=two_chats["chat_a"], root_id=two_chats["root_a"],
        )
        assert result["links_created"] == 0
        assert q("SELECT COUNT(*) AS c FROM lorebook_links", one=True)["c"] == 0
        assert len(result["skipped"]) == 1
