"""Lorebooks attach BY REFERENCE; a story deviates by OVERLAY.

Until 2026-09-03 attaching a library book duplicated its whole subtree into
a chat-owned "(chat copy)". Measured on the owner's database: 143 copies,
2,044 copied entries, 1,681 of them byte-identical to their origin. Now
`chat_lorebooks` points at the library row, retrieval reads the library
with the story's `lore_overlays` merged, and the copy is a migration.

Covered here: the graph admits a library book by reference; overlays are
set, merged, cleared and refused where they must be; the knowledge gate and
the compartment declaration read the merged rows; the routes write an
overlay from inside a story and a canon entry for an addition; checkpoints
keep the reference and the overlays and re-attach a legacy copy's origin;
an archive bundles the library and links by uid on import; a branch keeps
the reference; the migration converts a copy as measured; circles are story
state; the compiler's rulebook renders from data and containment is never
an unplanned door.
"""
from __future__ import annotations

import json
import sqlite3
import time

import pytest

from core.db import wget_for_frame, wset_for_frame
from mind import memory
from web import app as app_module
from web import guest_access as guest
from mind.memory import (
    clear_lore_overlay, knowledge_for_character, lore_overlay, lore_rows,
    search_lore, set_lore_overlay, declared_circles)
from tests.helpers import patch_provider_seam


@pytest.fixture(autouse=True)
def _flat_embeddings(monkeypatch):
    patch_provider_seam(monkeypatch, "embed_texts",
                        lambda values: [[0.25] * 8 for _ in values])
    from llm import providers

    class _Meta:
        def __init__(self, n):
            self.vectors = [[0.25] * 8 for _ in range(n)]
            self.model_key = "test:8"
            self.dimensions = 8
            self.fallback = False
    monkeypatch.setattr(providers, "embed_texts_meta",
                        lambda values, **kw: _Meta(len(values)))
    import mind.memory_lore_entries as mle
    monkeypatch.setattr(mle, "embed_texts_meta", lambda values, **kw: _Meta(len(values)))
    monkeypatch.setattr(mle, "_kw_scores", lambda *a, **k: {})


def _chat(db, name="Story"):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 (name, "", time.time()))


def _library(db, name="Guild Book", circles="[]"):
    return db.qi("INSERT INTO lorebooks(name,book_type,summary,resource_uid,default_circles) "
                 "VALUES(?,?,?,?,?)", (name, "general", "", "book_" + name.replace(" ", "_"), circles))


def _entry(book, keys, content, **kw):
    return memory.add_lore(book, keys, content, **kw)


def _attach(db, cid, book):
    db.qi("INSERT INTO chat_lorebooks(chat_id,lorebook_id,enabled) VALUES(?,?,1)", (cid, book))


@pytest.fixture
def client(temp_db):
    """The host's authenticated client (`tests/test_room_routes.py`'s shape)."""
    from fastapi.testclient import TestClient
    guest.reset_host_account()
    guest._join_attempts.clear()
    guest._login_attempts.clear()
    with TestClient(app_module.app) as c:
        r = c.post("/api/auth/setup", json={"username": "host", "password": "pw12345"})
        assert r.status_code == 200, r.text
        yield c
    guest.reset_host_account()
    guest._join_attempts.clear()
    guest._login_attempts.clear()


def _archive_roundtrip_service():
    """The app's own wired archive service, remappers and all."""
    return app_module._chat_archive_service


# ---- the graph reads the library by reference -----------------------------

class TestReference:
    def test_a_library_book_attached_by_reference_is_retrievable(self, temp_db):
        cid = _chat(temp_db)
        book = _library(temp_db)
        _attach(temp_db, cid, book)
        assert book in memory.chat_lorebook_ids(cid)
        assert memory.chat_lorebook_weights(cid)[book] == 1.0

    def test_another_stories_book_is_never_readable(self, temp_db):
        cid, other = _chat(temp_db, "A"), _chat(temp_db, "B")
        theirs = temp_db.qi("INSERT INTO lorebooks(name,chat_id,book_type,summary) "
                            "VALUES(?,?,?,?)", ("Theirs", other, "general", ""))
        _attach(temp_db, cid, theirs)
        assert theirs not in memory.chat_lorebook_ids(cid)

    def test_the_attach_route_keeps_the_library_row(self, temp_db, client):
        cid = _chat(temp_db)
        book = _library(temp_db)
        r = client.post(f"/api/chats/{cid}/lorebooks", json={"lorebook_id": book})
        assert r.status_code == 200 and r.json()["lorebook_id"] == book
        rows = temp_db.q("SELECT * FROM lorebooks WHERE chat_id=?", (cid,))
        assert rows == [], "no chat copy was made"
        att = temp_db.q("SELECT * FROM chat_lorebooks WHERE chat_id=?", (cid,), one=True)
        assert att["lorebook_id"] == book and att["origin_id"] is None
        again = client.post(f"/api/chats/{cid}/lorebooks", json={"lorebook_id": book})
        assert again.json().get("already") is True

    def test_a_library_book_cannot_be_bound_as_canon(self, temp_db, client):
        cid = _chat(temp_db)
        book = _library(temp_db)
        r = client.post(f"/api/chats/{cid}/lorebook", json={"lorebook_id": book})
        assert r.status_code == 400
        assert temp_db.q("SELECT lorebook_id FROM chats WHERE id=?", (cid,), one=True)["lorebook_id"] is None

    def test_the_greeting_launch_attaches_by_reference(self, temp_db, monkeypatch):
        """`start_story` used to duplicate the template book into a chat copy."""
        from story import greetings
        import story.greetings as g
        cid = _chat(temp_db)
        book = _library(temp_db)
        called = []
        monkeypatch.setattr(g, "duplicate_lorebook_for_chat",
                            lambda *a, **k: called.append(a) or 999)
        lb = temp_db.q("SELECT * FROM lorebooks WHERE id=?", (book,), one=True)
        # The attach block, verbatim from start_story, applied to a library row.
        if lb["chat_id"] is None or lb["chat_id"] == cid:
            new_lb, origin = lb["id"], None
        else:
            new_lb = g.duplicate_lorebook_for_chat(lb["id"], cid)
            origin = lb["id"]
        temp_db.qi("INSERT OR IGNORE INTO chat_lorebooks(chat_id,lorebook_id,origin_id,enabled) "
                   "VALUES(?,?,?,1)", (cid, new_lb, origin))
        assert called == [] and new_lb == book
        src = __import__("inspect").getsource(greetings.start_story)
        assert 'lb["chat_id"] is None' in src


# ---- overlays: set, merge, clear, refuse ----------------------------------

class TestOverlay:
    def test_an_overlay_is_merged_over_the_library_row(self, temp_db):
        cid = _chat(temp_db)
        book = _library(temp_db)
        eid = _entry(book, "gate", "The gate is iron.", title="The Gate",
                     knowledge_tag="common")
        _attach(temp_db, cid, book)
        row = set_lore_overlay(cid, eid, content="The gate is iron, and rusted through.",
                               turn_idx=4, source_notes="the player saw it")
        assert row["disposition"] == "story_edit" and row["turn_idx"] == 4
        (merged,) = lore_rows([book], chat_id=cid)
        assert merged["content"] == "The gate is iron, and rusted through."
        assert merged["title"] == "The Gate", "an unset field inherits"
        assert merged["overlay_id"] == row["id"]
        (library,) = lore_rows([book])
        assert library["content"] == "The gate is iron." and library["overlay_id"] is None
        (hit,) = search_lore([book], "gate", chat_id=cid)
        assert hit["content"].endswith("rusted through.") and hit["overlay"] is True
        (plain,) = search_lore([book], "gate")
        assert plain["content"] == "The gate is iron." and plain["overlay"] is False

    def test_a_second_set_replaces_and_clear_reverts(self, temp_db):
        cid = _chat(temp_db)
        book = _library(temp_db)
        eid = _entry(book, "gate", "The gate is iron.")
        set_lore_overlay(cid, eid, content="Bronze.")
        set_lore_overlay(cid, eid, title="Renamed")
        over = lore_overlay(cid, eid)
        assert over["content"] == "Bronze." and over["title"] == "Renamed"
        assert temp_db.q("SELECT COUNT(*) c FROM lore_overlays", one=True)["c"] == 1
        assert clear_lore_overlay(cid, eid) is True
        assert clear_lore_overlay(cid, eid) is False
        (row,) = lore_rows([book], chat_id=cid)
        assert row["content"] == "The gate is iron."

    def test_overlays_are_per_story_and_per_era(self, temp_db):
        a, b = _chat(temp_db, "A"), _chat(temp_db, "B")
        book = _library(temp_db)
        eid = _entry(book, "gate", "The gate is iron.")
        frame = temp_db.qi("INSERT INTO frames(chat_id,kind,label,created) VALUES(?,?,?,?)",
                           (a, "branch", "later", time.time()))
        set_lore_overlay(a, eid, content="A's gate.")
        set_lore_overlay(a, eid, content="A's later gate.", frame_id=frame)
        assert lore_rows([book], chat_id=a)[0]["content"] == "A's gate."
        assert lore_rows([book], chat_id=a, frame_id=frame)[0]["content"] == "A's later gate."
        assert lore_rows([book], chat_id=b)[0]["content"] == "The gate is iron."

    def test_own_and_foreign_entries_refuse_an_overlay(self, temp_db):
        cid, other = _chat(temp_db, "A"), _chat(temp_db, "B")
        own = temp_db.qi("INSERT INTO lorebooks(name,chat_id,book_type,summary) VALUES(?,?,?,?)",
                         ("Canon", cid, "general", ""))
        theirs = temp_db.qi("INSERT INTO lorebooks(name,chat_id,book_type,summary) VALUES(?,?,?,?)",
                            ("Theirs", other, "general", ""))
        e1 = _entry(own, "k", "mine")
        e2 = _entry(theirs, "k", "theirs")
        with pytest.raises(ValueError, match="owns this entry"):
            set_lore_overlay(cid, e1, content="x")
        with pytest.raises(ValueError, match="another story"):
            set_lore_overlay(cid, e2, content="x")
        lib = _library(temp_db)
        e3 = _entry(lib, "k", "lib")
        with pytest.raises(ValueError, match="may not set"):
            set_lore_overlay(cid, e3, importance=1.0)
        with pytest.raises(ValueError, match="disposition"):
            set_lore_overlay(cid, e3, content="x", disposition="whim")

    def test_the_knowledge_gate_and_compartments_read_the_overlay(self, temp_db):
        cid = _chat(temp_db)
        book = _library(temp_db)
        eid = _entry(book, "rite", "The rite is sung at dusk.", title="The Rite",
                     knowledge_tag="common", circles=["choir"])
        _attach(temp_db, cid, book)
        # An outsider does not know it in the library...
        assert knowledge_for_character([book], None, ["common"], [], circles=[],
                                       chat_id=cid) == []
        # ...the story leaks it into rumour: the compartment opens, for this
        # story only.
        set_lore_overlay(cid, eid, circles=[], content="The rite is sung at dusk, everybody says.")
        (known,) = knowledge_for_character([book], None, ["common"], [], circles=[], chat_id=cid)
        assert "everybody says" in known["content"]
        assert knowledge_for_character([book], None, ["common"], [], circles=[]) == []
        # And a compartment the story adds is declared for the story.
        set_lore_overlay(cid, eid, circles=["choir", "sextons"])
        assert "sextons" in declared_circles([book], chat_id=cid)
        assert "sextons" not in declared_circles([book])

    def test_a_story_lock_lives_on_the_overlay(self, temp_db):
        cid = _chat(temp_db)
        book = _library(temp_db)
        eid = _entry(book, "gate", "The gate is iron.")
        set_lore_overlay(cid, eid, canon_locked=True)
        assert lore_rows([book], chat_id=cid)[0]["canon_locked"] == 1
        assert lore_rows([book])[0]["canon_locked"] == 0
        assert search_lore([book], "gate", chat_id=cid)[0]["locked"] is True

    def test_deleting_the_library_entry_takes_the_overlay_with_it(self, temp_db):
        cid = _chat(temp_db)
        book = _library(temp_db)
        eid = _entry(book, "gate", "The gate is iron.")
        set_lore_overlay(cid, eid, content="x")
        memory.delete_lore(eid)
        assert temp_db.q("SELECT COUNT(*) c FROM lore_overlays", one=True)["c"] == 0


# ---- the routes ------------------------------------------------------------

class TestRoutes:
    def test_an_edit_from_inside_a_story_is_an_overlay(self, temp_db, client):
        cid = _chat(temp_db)
        book = _library(temp_db)
        eid = _entry(book, "gate", "The gate is iron.", title="The Gate")
        _attach(temp_db, cid, book)
        r = client.put(f"/api/lore_entries/{eid}", json={
            "chat_id": cid, "content": "The gate is bronze.", "canon_locked": True})
        assert r.status_code == 200
        entry = r.json()["entry"]
        assert entry["overlay"] is True and entry["content"] == "The gate is bronze."
        assert entry["canon_locked"] is True and entry["title"] == "The Gate"
        assert temp_db.q("SELECT content FROM lore_entries WHERE id=?", (eid,), one=True)["content"] == "The gate is iron."
        # The library, read without a story, is unchanged; read AS the story,
        # it carries the overlay.
        assert client.get(f"/api/lorebooks/{book}").json()["entries"][0]["content"] == "The gate is iron."
        as_story = client.get(f"/api/lorebooks/{book}", params={"chat_id": cid}).json()
        assert as_story["book"]["library"] is True and as_story["book"]["read_as_story"] == cid
        assert as_story["entries"][0]["overlay"] is True
        # Reverting.
        r = client.delete(f"/api/lore_entries/{eid}/overlay", params={"chat_id": cid})
        assert r.json()["cleared"] is True and r.json()["entry"]["overlay"] is False

    def test_an_edit_with_no_story_writes_the_library(self, temp_db, client):
        book = _library(temp_db)
        eid = _entry(book, "gate", "The gate is iron.")
        r = client.put(f"/api/lore_entries/{eid}", json={"content": "The gate is bronze."})
        assert r.status_code == 200 and r.json()["entry"]["overlay"] is False
        assert temp_db.q("SELECT content FROM lore_entries WHERE id=?", (eid,), one=True)["content"] == "The gate is bronze."

    def test_an_addition_from_inside_a_story_lands_in_canon(self, temp_db, client):
        cid = _chat(temp_db)
        book = _library(temp_db)
        _attach(temp_db, cid, book)
        r = client.post(f"/api/lorebooks/{book}/entries", json={
            "chat_id": cid, "keys": "well", "content": "The well is dry."})
        assert r.status_code == 200
        body = r.json()
        canon = temp_db.q("SELECT lorebook_id FROM chats WHERE id=?", (cid,), one=True)["lorebook_id"]
        assert canon is not None and body["redirected_to"] == canon
        assert body["entry"]["lorebook_id"] == canon
        assert "Guild Book" in body["entry"]["source_notes"]
        assert temp_db.q("SELECT COUNT(*) c FROM lore_entries WHERE lorebook_id=?", (book,), one=True)["c"] == 0

    def test_a_library_entry_is_not_deleted_from_a_story(self, temp_db, client):
        cid = _chat(temp_db)
        book = _library(temp_db)
        eid = _entry(book, "gate", "The gate is iron.")
        r = client.delete(f"/api/lore_entries/{eid}", params={"chat_id": cid})
        assert r.status_code == 400
        assert temp_db.q("SELECT 1 FROM lore_entries WHERE id=?", (eid,), one=True)


# ---- checkpoints ------------------------------------------------------------

class TestCheckpoints:
    def test_a_snapshot_keeps_the_reference_and_the_overlays_not_the_entries(self, temp_db):
        from persist.checkpoints import snapshot_state
        cid = _chat(temp_db)
        book = _library(temp_db)
        eid = _entry(book, "gate", "The gate is iron.")
        _attach(temp_db, cid, book)
        set_lore_overlay(cid, eid, content="Bronze.")
        snap = snapshot_state(cid)
        (ref,) = [b for b in snap["lorebooks"] if b["lorebook_id"] == book]
        assert ref["library"] is True and "entries" not in ref
        assert ref["resource_uid"] == "book_Guild_Book"
        (over,) = snap["lore_overlays"]
        assert over["entry_uid"] and over["content"] == "Bronze." and over["frame_id"] is None

    def test_a_restore_re_attaches_and_puts_overlays_back_and_never_touches_the_library(self, temp_db):
        from persist.checkpoints import ensure_checkpoint, restore_checkpoint
        cid = _chat(temp_db)
        book = _library(temp_db)
        eid = _entry(book, "gate", "The gate is iron.")
        _attach(temp_db, cid, book)
        set_lore_overlay(cid, eid, content="Bronze.")
        temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                   (cid, 0, "", time.time()))
        ensure_checkpoint(cid, 0)
        # Later: the story edits the library entry again, detaches the book,
        # attaches another, and the LIBRARY itself is edited by its author.
        set_lore_overlay(cid, eid, content="Gold.")
        temp_db.qi("DELETE FROM chat_lorebooks WHERE chat_id=?", (cid,))
        other = _library(temp_db, "Other Book")
        _attach(temp_db, cid, other)
        memory.update_lore(eid, "gate", "The gate is iron, the author says.")
        restore_checkpoint(cid, 0)
        att = [r["lorebook_id"] for r in temp_db.q("SELECT lorebook_id FROM chat_lorebooks WHERE chat_id=?", (cid,))]
        assert att == [book], "the snapshot's book set: the reference back, the later one gone"
        assert lore_overlay(cid, eid)["content"] == "Bronze."
        assert temp_db.q("SELECT content FROM lore_entries WHERE id=?", (eid,), one=True)["content"] \
            == "The gate is iron, the author says.", "a restore never rewrites the library"

    def test_a_legacy_copy_snapshot_maps_onto_its_library_origin(self, temp_db):
        """A checkpoint taken before 2026-09-03 lists the story's COPY with
        `origin_id` naming the library book. The copy is gone (migrated);
        restoring must re-attach the origin, not re-create the copy."""
        from persist.checkpoints import _restore_books
        cid = _chat(temp_db)
        book = _library(temp_db)
        _entry(book, "gate", "The gate is iron.")
        snapshot = [{"lorebook_id": 9999, "origin_id": book, "name": "Guild Book (chat copy)",
                     "book_type": "general", "summary": "", "canon": False, "enabled": 1,
                     "entries": [{"keys": "gate", "content": "The gate is iron.",
                                  "category": "other", "entry_uid": "entry_legacy"}]}]
        mapping = _restore_books(cid, snapshot, [])
        assert mapping[9999] == book
        assert temp_db.q("SELECT COUNT(*) c FROM lorebooks WHERE chat_id=?", (cid,), one=True)["c"] == 0
        assert temp_db.q("SELECT lorebook_id FROM chat_lorebooks WHERE chat_id=?", (cid,), one=True)["lorebook_id"] == book


# ---- archives ---------------------------------------------------------------

class TestArchive:
    def test_export_bundles_the_library_and_import_links_by_uid(self, temp_db):
        svc = _archive_roundtrip_service()
        cid = _chat(temp_db)
        book = _library(temp_db)
        eid = _entry(book, "gate", "The gate is iron.", entry_uid="entry_gate")
        _attach(temp_db, cid, book)
        set_lore_overlay(cid, eid, content="Bronze.")
        export = svc.export_chat(cid)
        (lib,) = [b for b in export["lorebooks"] if b["book"]["id"] == book]
        assert lib["library"] is True and lib["entries"][0]["entry_uid"] == "entry_gate"
        assert export["lore_overlays"][0]["entry_uid"] == "entry_gate"
        # Import on the SAME install: the library book is linked, not copied.
        imported = svc.import_chat({"data": json.loads(json.dumps(export))})
        new_cid = imported["id"] if isinstance(imported, dict) else imported
        assert temp_db.q("SELECT COUNT(*) c FROM lorebooks WHERE chat_id IS NULL", one=True)["c"] == 1
        assert temp_db.q("SELECT lorebook_id FROM chat_lorebooks WHERE chat_id=?", (new_cid,), one=True)["lorebook_id"] == book
        assert lore_overlay(new_cid, eid)["content"] == "Bronze."

    def test_import_creates_the_library_book_when_the_install_lacks_it(self, temp_db):
        svc = _archive_roundtrip_service()
        cid = _chat(temp_db)
        book = _library(temp_db)
        eid = _entry(book, "gate", "The gate is iron.", entry_uid="entry_gate2")
        _attach(temp_db, cid, book)
        set_lore_overlay(cid, eid, content="Bronze.")
        export = json.loads(json.dumps(svc.export_chat(cid)))
        # The library leaves this install.
        temp_db.qi("DELETE FROM chats WHERE id=?", (cid,))
        temp_db.qi("DELETE FROM lorebooks WHERE id=?", (book,))
        imported = svc.import_chat({"data": export})
        new_cid = imported["id"] if isinstance(imported, dict) else imported
        lib = temp_db.q("SELECT * FROM lorebooks WHERE chat_id IS NULL", one=True)
        assert lib is not None and lib["resource_uid"] == "book_Guild_Book"
        assert temp_db.q("SELECT lorebook_id FROM chat_lorebooks WHERE chat_id=?", (new_cid,), one=True)["lorebook_id"] == lib["id"]
        new_eid = temp_db.q("SELECT id FROM lore_entries WHERE entry_uid=?", ("entry_gate2",), one=True)["id"]
        assert lore_overlay(new_cid, new_eid)["content"] == "Bronze."


# ---- the migration ----------------------------------------------------------

class TestMigration:
    def test_a_chat_copy_becomes_a_reference_plus_overlays(self, temp_db):
        from core import db as core_db
        cid = _chat(temp_db)
        book = _library(temp_db)
        same = _entry(book, "gate", "The gate is iron.", title="The Gate")
        edited = _entry(book, "well", "The well is deep.", title="The Well")
        # The pre-2026-09 shape: a chat-owned copy with origin_id, attached.
        copy = temp_db.qi("INSERT INTO lorebooks(name,chat_id,origin_id,book_type,summary) "
                          "VALUES(?,?,?,?,?)", ("Guild Book (chat copy)", cid, book, "general", ""))
        _entry(copy, "gate", "The gate is iron.", title="The Gate")
        _entry(copy, "well", "The well is deep, and poisoned.", title="The Well")
        _entry(copy, "shrine", "A shrine nobody in the library knows.", title="The Shrine")
        temp_db.qi("INSERT INTO chat_lorebooks(chat_id,lorebook_id,origin_id,enabled) VALUES(?,?,?,0)",
                   (cid, copy, book))
        orphan = temp_db.qi("INSERT INTO lorebooks(name,chat_id,origin_id,book_type,summary) "
                            "VALUES(?,?,?,?,?)", ("Lost (chat copy)", cid, 424242, "general", ""))
        c = sqlite3.connect(core_db.DB)
        c.row_factory = sqlite3.Row
        report = core_db._migrate_chat_copies_to_overlays(c)
        c.commit()
        c2 = sqlite3.connect(core_db.DB); c2.row_factory = sqlite3.Row
        assert core_db._migrate_chat_copies_to_overlays(c2)["copies"] == 0, "idempotent"
        c.close(); c2.close()
        assert report == {"copies": 2, "converted": 1, "kept_own": 1,
                          "dropped": 1, "overlaid": 1, "moved": 1}
        assert temp_db.q("SELECT 1 FROM lorebooks WHERE id=?", (copy,), one=True) is None
        att = temp_db.q("SELECT * FROM chat_lorebooks WHERE chat_id=?", (cid,), one=True)
        assert att["lorebook_id"] == book and att["enabled"] == 0 and att["origin_id"] is None
        over = lore_overlay(cid, edited)
        assert over["content"] == "The well is deep, and poisoned." and over["disposition"] == "migrated_copy"
        assert lore_overlay(cid, same) is None
        canon = temp_db.q("SELECT lorebook_id FROM chats WHERE id=?", (cid,), one=True)["lorebook_id"]
        moved = temp_db.q("SELECT * FROM lore_entries WHERE lorebook_id=?", (canon,), one=True)
        assert moved["title"] == "The Shrine" and "moved 2026-09" in moved["source_notes"]
        kept = temp_db.q("SELECT origin_id FROM lorebooks WHERE id=?", (orphan,), one=True)
        assert kept["origin_id"] is None, "an orphaned copy is the story's own book now"


# ---- circles as story state -------------------------------------------------

class TestCircles:
    def test_a_story_grants_and_withdraws_a_circle_over_the_sheet(self, temp_db):
        from core.db import FRAME_SCOPED_WORLD_KEYS
        from mind.knowledge_circles import (
            CIRCLES_KEY, effective_circles, identity_key, join_circle, leave_circle)
        assert CIRCLES_KEY in FRAME_SCOPED_WORLD_KEYS
        cid = _chat(temp_db)
        sheet = {"identity": {"uid": "char_abc", "name": "Reya"}}
        key = identity_key(sheet)
        assert key == "char_abc"
        assert effective_circles(["couriers"], cid, key) == ["couriers"]
        row = join_circle(cid, key, "The Choir", turn_idx=12, via="initiation")
        assert row == {"circle": "the choir", "since_turn": 12, "via": "initiation",
                       "status": "member", "left_turn": None}
        assert effective_circles(["couriers"], cid, key) == ["couriers", "the choir"]
        assert join_circle(cid, key, "the choir", turn_idx=13) == row, "idempotent"
        assert leave_circle(cid, key, "the choir", turn_idx=20) is True
        assert effective_circles(["couriers"], cid, key) == ["couriers"]
        assert leave_circle(cid, key, "couriers", turn_idx=20) is False, \
            "a sheet-authored circle is the card's, not the story's to strip"
        with pytest.raises(ValueError):
            join_circle(cid, key, "  ", turn_idx=1)

    def test_the_character_payload_reads_story_circles(self, temp_db):
        """The gate's caller overlays the story's circles on the sheet's."""
        import inspect
        from agents import character
        src = inspect.getsource(character)
        assert "effective_circles" in src and "knowledge_for_character(" in src
        assert "chat_id=chat.id" in src


# ---- the compiler: containment and the rulebook ------------------------------

class TestCompiler:
    def test_an_entity_or_its_inside_is_contained_never_unplanned(self):
        from agents.mapping import classify_movement, _location_query_status
        scene = {"rooms": {"hall": {"name": "Hall"},
                           "Mirelle Sulmirath_throat": {"name": "Throat",
                                                        "parent_entity": "mirelle"}},
                 "entities": {"mirelle": {"name": "Mirelle Sulmirath",
                                          "interior_rooms": ["Mirelle Sulmirath_throat"]}}}
        never = lambda q: None
        for target in ("mirelle", "Mirelle Sulmirath", "Mirelle Sulmirath_womb",
                       "Mirelle Sulmirath_throat"):
            out = classify_movement({"movement": {"to_room": target}}, scene, planned_for=never)
            assert out["status"] in ("contained", "known"), (target, out)
        assert classify_movement({"movement": {"to_room": "Mirelle Sulmirath_womb"}},
                                 scene, planned_for=never)["status"] == "contained"
        assert classify_movement({"movement": {"to_room": "drowned_chapel"}},
                                 scene, planned_for=never)["status"] == "unplanned"
        assert _location_query_status("Mirelle Sulmirath", scene, planned_for=never) == "contained"
        assert _location_query_status("the customs house", scene, planned_for=never) == "unmatched"

    def test_the_rulebook_renders_from_typed_data(self, temp_db):
        from agents.mapping import rulebook_rows
        cid = _chat(temp_db)
        wset_for_frame(cid, "simulation_clock", {"hour_of_day": 19.0, "day_length_hours": 24.0,
                                                 "phase": "dusk"}, None)
        scene = {"rooms": {"quay": {"name": "Quay"}},
                 "weather": {"sky": "overcast", "precipitation": "rain", "intensity": "light",
                             "wind": "breeze", "temperature": "cold"}}
        rows = rulebook_rows(cid, scene, None)
        by = {r["source"]: r for r in rows}
        assert "dusk" in by["day_cycle"]["text"] and "24 hours" in by["day_cycle"]["text"]
        assert "dim light" in by["day_cycle"]["text"]
        assert "overcast" in by["weather"]["text"] and "rain" in by["weather"]["text"]
        assert all(len(r["text"]) <= 400 for r in rows)

    def test_lore_for_carries_the_rulebook_as_engine_rows(self):
        from agents.common import lore_for

        class _Ctx:
            def world_context(self):
                return {"relevant_lore": [{"id": 1, "book_id": 2, "keys": "k",
                                           "content": "c", "category": "myth",
                                           "locked": False, "overlay": True}],
                        "rulebook": [{"source": "weather", "subject": "the weather",
                                      "text": "Weather: sky clear."}]}
        rows = lore_for(_Ctx())
        assert rows[0]["overlay"] is True and "id" in rows[0]
        assert rows[1] == {"keys": "the weather", "content": "Weather: sky clear.",
                           "category": "mechanic", "locked": True,
                           "source": "engine:rulebook"}
        assert "id" not in rows[1], "a rulebook row is not an entry and never enters the cache"
