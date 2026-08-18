"""Document storage for extensions: JSON documents at logical paths.

The fifth persistence home, built for the storage adapter a ported extension
brings with it -- documents at paths, with `list`, `delete` and `verify` --
and pinned here by the properties that make it a HOME rather than a dict:

* documents are namespaced, so one extension can never read or clobber
  another's, and scoped, so a story's documents and the install's never mix;
* paths are validated like the attacker-adjacent input they are, even though
  no filesystem is ever touched;
* the ceilings REFUSE rather than truncate, because a truncated JSON document
  is a parse error and the writer must learn at write time;
* `verify` reports damage without throwing, because an integrity check that
  dies on the first broken row cannot tell you about the second;
* and -- the reason it is KV rows and not a table -- documents ride
  checkpoint restore, portable archive and branch EXACTLY as the four
  existing homes do, with no line of carriage code of their own.
"""

from __future__ import annotations

import json
import time

import pytest

import extension_runtime
from extension_runtime import DocumentStore, ExtensionError
from extension_runtime.api import document_path

from tests.test_extensions import (  # noqa: F401 - fixtures are used by name
    _StubCtx, _chat, _enable, _turn, _write_extension, ext_root,
)


@pytest.fixture
def pair(ext_root):
    """Two installed, enabled extensions, so namespacing is testable at all."""
    for ext_id in ("alpha", "beta"):
        _write_extension(ext_root, ext_id, {
            "id": ext_id, "version": "1.0.0", "ext_api": 1, "name": ext_id,
            "capabilities": {"python": "extension.py", "chat_state": True},
        }, {"extension.py": "def register(api):\n    pass\n"})
    _enable("alpha", "beta")
    return (extension_runtime._apis["alpha"], extension_runtime._apis["beta"])


# ----------------------------------------------------------- put / get / stat


class TestRoundTrip:
    def test_a_document_round_trips_with_metadata(self, temp_db, pair):
        alpha, _ = pair
        chat_id = _chat(temp_db)
        docs = alpha.documents(chat_id)

        meta = docs.put_now("missions/epsilon", {"stage": 2, "open": True})

        assert docs.get("missions/epsilon") == {"stage": 2, "open": True}
        assert meta["path"] == "missions/epsilon"
        assert meta["revision"] == 1
        assert meta["size"] > 0
        assert len(meta["sha256"]) == 64
        assert meta["created_at"] <= meta["updated_at"]
        assert docs.stat("missions/epsilon") == meta

    def test_non_dict_documents_are_documents_too(self, temp_db, pair):
        """A JSON document is any JSON value. An adapter porting files will
        bring lists and scalars, and a store that silently dict-ified them
        would corrupt every one."""
        alpha, _ = pair
        docs = alpha.documents(_chat(temp_db))
        docs.put_now("a-list", [1, 2, {"x": None}])
        docs.put_now("a-string", "just text")
        assert docs.get("a-list") == [1, 2, {"x": None}]
        assert docs.get("a-string") == "just text"

    def test_absent_is_default_and_stat_is_none(self, temp_db, pair):
        alpha, _ = pair
        docs = alpha.documents(_chat(temp_db))
        assert docs.get("never/written", default="fallback") == "fallback"
        assert docs.stat("never/written") is None

    def test_identical_content_does_not_bump_the_revision(self, temp_db,
                                                          pair):
        """The NarrationBlock rule, for the same reason: a caller that re-puts
        on every beat must not make the revision number meaningless. Key
        order does not count as new content -- the hash is over the CANONICAL
        serialization, so reordering a dict is not a write."""
        alpha, _ = pair
        docs = alpha.documents(_chat(temp_db))
        first = docs.put_now("ledger", {"a": 1, "b": 2})
        again = docs.put_now("ledger", {"b": 2, "a": 1})
        assert again["revision"] == first["revision"] == 1
        changed = docs.put_now("ledger", {"a": 1, "b": 3})
        assert changed["revision"] == 2

    def test_unserializable_content_is_refused(self, temp_db, pair):
        alpha, _ = pair
        docs = alpha.documents(_chat(temp_db))
        with pytest.raises(ExtensionError, match="JSON-serializable"):
            docs.put_now("bad", {"when": object()})
        assert docs.stat("bad") is None


# --------------------------------------------------------------- namespacing


class TestNamespacing:
    def test_one_extension_cannot_see_anothers_documents(self, temp_db, pair):
        """The property the `ext:<id>` namespace exists for, extended to the
        fifth home: alpha's documents are invisible to beta's list, get and
        verify, even at the same path in the same chat."""
        alpha, beta = pair
        chat_id = _chat(temp_db)
        alpha.documents(chat_id).put_now("shared/name", {"owner": "alpha"})

        assert beta.documents(chat_id).get("shared/name") is None
        assert beta.documents(chat_id).list() == []
        assert beta.documents(chat_id).verify() == {
            "ok": True, "checked": 0, "damaged": []}
        assert alpha.documents(chat_id).get("shared/name") == {
            "owner": "alpha"}

    def test_delete_prefix_is_bounded_by_the_namespace(self, temp_db, pair):
        """However wide the prefix -- here, everything -- only the deleting
        extension's own rows can go."""
        alpha, beta = pair
        chat_id = _chat(temp_db)
        alpha.documents(chat_id).put_now("a/1", 1)
        alpha.documents(chat_id).put_now("a/2", 2)
        beta.documents(chat_id).put_now("a/1", "beta keeps this")

        assert alpha.documents(chat_id).delete_prefix_now("") == 2
        assert alpha.documents(chat_id).list() == []
        assert beta.documents(chat_id).get("a/1") == "beta keeps this"

    def test_stories_do_not_share_documents(self, temp_db, pair):
        alpha, _ = pair
        one, two = _chat(temp_db, "One"), _chat(temp_db, "Two")
        alpha.documents(one).put_now("campaign", {"chat": "one"})
        assert alpha.documents(two).get("campaign") is None

    def test_story_and_install_scope_are_different_stores(self, temp_db,
                                                          pair):
        """`chat_id=None` is the install: the campaign library that exists
        before any story does. The same path in a story is a different
        document, and a story's rewind must never reach the install's rows."""
        alpha, _ = pair
        chat_id = _chat(temp_db)
        alpha.documents().put_now("library/pack", {"scope": "install"})
        alpha.documents(chat_id).put_now("library/pack", {"scope": "story"})

        assert alpha.documents().get("library/pack") == {"scope": "install"}
        assert alpha.documents(chat_id).get("library/pack") == {
            "scope": "story"}
        assert [m["path"] for m in alpha.documents().list()] == [
            "library/pack"]

    def test_documents_do_not_collide_with_the_other_homes(self, temp_db,
                                                           pair):
        """`ext:<id>:doc:narration` and `ext:<id>:narration` are different
        rows: a document may be named after any sibling surface without
        shadowing it."""
        from core.db import wget

        alpha, _ = pair
        chat_id = _chat(temp_db)
        alpha.narration_context(chat_id).set("standing context")
        alpha.documents(chat_id).put_now("narration", {"a": "document"})

        assert alpha.narration_context(chat_id).text == "standing context"
        assert alpha.documents(chat_id).get("narration") == {"a": "document"}
        assert wget(chat_id, "ext:alpha:narration")["text"] == (
            "standing context")


# ---------------------------------------------------------------- path rules


class TestPathRules:
    @pytest.mark.parametrize("path", [
        "",                       # empty
        "/absolute",              # absolute
        "..",                     # traversal
        "../up",                  # traversal
        "a/../b",                 # traversal mid-path
        "a//b",                   # empty segment
        "a/",                     # trailing empty segment
        ".hidden",                # dot-leading segment
        "a/.hidden/b",            # dot-leading segment mid-path
        "a b",                    # whitespace
        "a\\b",                   # backslash
        "a%b",                    # outside the portable alphabet
        "s" * 65,                 # one segment over the segment ceiling
        "x/" * 200 + "x",         # whole path over the path ceiling
    ])
    def test_a_hostile_or_malformed_path_is_refused(self, path):
        """Logical paths are attacker-adjacent input. Nothing here touches a
        filesystem -- the path is an exact KV row key -- but the alphabet is
        held to the portable one anyway, and every traversal spelling is
        unspellable by construction (a segment must start alphanumeric)."""
        with pytest.raises(ExtensionError):
            document_path(path)

    @pytest.mark.parametrize("path", [
        "a", "missions/epsilon-2.json", "A/B/C", "0/1/2", "state",
        "a..b",   # dots INSIDE a segment are a name, not traversal
    ])
    def test_an_ordinary_path_is_accepted_verbatim(self, path):
        assert document_path(path) == path

    def test_refusal_applies_to_every_operation(self, temp_db, pair):
        """One validator, called by every entrance -- a delete that accepted
        what put refused would let a bad path exist in half the API."""
        alpha, _ = pair
        docs = alpha.documents(_chat(temp_db))
        for op in (lambda: docs.put_now("../x", 1),
                   lambda: docs.get("../x"),
                   lambda: docs.stat("../x"),
                   lambda: docs.delete_now("../x"),
                   lambda: docs.list("../x"),
                   lambda: docs.verify("../x"),
                   lambda: docs.delete_prefix_now("../x")):
            with pytest.raises(ExtensionError):
                op()


# ------------------------------------------------------------------ ceilings


class TestCeilings:
    def test_an_oversized_document_is_refused_not_truncated(self, temp_db,
                                                            pair,
                                                            monkeypatch):
        """Refusal is the point: a truncated JSON document is not a smaller
        document, it is a parse error `verify` would report fifty beats
        after the write that caused it. And refusal must leave the PREVIOUS
        revision standing -- an overwrite that half-fails by deleting is
        worse than one that refuses."""
        monkeypatch.setattr("extension_runtime.api.DOCUMENT_MAX_BYTES", 64)
        alpha, _ = pair
        docs = alpha.documents(_chat(temp_db))
        docs.put_now("log", {"v": 1})

        with pytest.raises(ExtensionError, match="ceiling"):
            docs.put_now("log", {"v": "x" * 200})
        assert docs.get("log") == {"v": 1}

    def test_the_count_ceiling_refuses_new_paths_not_overwrites(self,
                                                                temp_db,
                                                                pair,
                                                                monkeypatch):
        """A full store still accepts an update to a document it already
        holds -- the ceiling bounds the checkpoint tax, and an overwrite adds
        no row to tax."""
        monkeypatch.setattr("extension_runtime.api.DOCUMENT_COUNT_MAX", 2)
        alpha, _ = pair
        docs = alpha.documents(_chat(temp_db))
        docs.put_now("a", 1)
        docs.put_now("b", 2)

        with pytest.raises(ExtensionError, match="ceiling"):
            docs.put_now("c", 3)
        assert docs.put_now("a", 10)["revision"] == 2
        docs.delete_now("b")
        docs.put_now("c", 3)  # room again after a delete
        assert [m["path"] for m in docs.list()] == ["a", "c"]

    def test_ceilings_are_per_extension(self, temp_db, pair, monkeypatch):
        """One extension filling its store must not consume a sibling's
        headroom -- the count is per namespace, like everything else."""
        monkeypatch.setattr("extension_runtime.api.DOCUMENT_COUNT_MAX", 1)
        alpha, beta = pair
        chat_id = _chat(temp_db)
        alpha.documents(chat_id).put_now("only", 1)
        beta.documents(chat_id).put_now("only", 1)  # beta's own headroom


# ---------------------------------------------------------------- write gate


class TestWriteGate:
    def test_story_documents_are_gated_like_state(self, temp_db, pair):
        """The same ghost-state hazard as `ExtState.set`: a document written
        mid-pipeline lands outside the turn's transaction and survives the
        rollback that undid everything it was computed from. The message
        names the escape hatch, so the refusal teaches the fix."""
        alpha, _ = pair
        docs = alpha.documents(_chat(temp_db))
        with pytest.raises(ExtensionError, match="put_now"):
            docs.put("a", 1)
        docs.put_now("a", 1)
        with pytest.raises(ExtensionError, match="delete_now"):
            docs.delete("a")
        with pytest.raises(ExtensionError, match="delete_prefix_now"):
            docs.delete_prefix("")
        assert docs.get("a") == 1

    def test_the_gate_opens_inside_a_committed_turn_hook(self, temp_db,
                                                         pair):
        alpha, _ = pair
        chat_id = _chat(temp_db)
        alpha.on_turn_committed(
            lambda turn: alpha.documents(chat_id).put("beat/log",
                                                      {"turn": turn.turn_idx}))
        report = extension_runtime.dispatch_turn_committed(
            _StubCtx(chat_id=chat_id, turn_id=_turn(temp_db, chat_id), idx=7))

        assert report["errors"] == {}
        assert alpha.documents(chat_id).get("beat/log") == {"turn": 7}

    def test_install_documents_are_ungated_like_settings(self, temp_db,
                                                         pair):
        """The install store is host configuration: no turn transaction is
        ever implicated, so gating it would be superstition -- the same
        ruling as `api.settings`."""
        alpha, _ = pair
        alpha.documents().put("library/pack", {"v": 1})
        assert alpha.documents().get("library/pack") == {"v": 1}
        assert alpha.documents().delete("library/pack") is True

    def test_a_commit_domain_gets_an_ungated_store(self, temp_db, pair):
        """Inside `run_commit_domains` the transaction is the guarantee, so
        `CommitView.documents()` is ungated -- the same reasoning as
        `CommitView.state`."""
        alpha, _ = pair
        chat_id = _chat(temp_db)
        alpha.add_commit_domain(
            "docs", lambda view: view.documents().put("domain/wrote", True))
        results = {}
        extension_runtime.run_commit_domains(
            _StubCtx(chat_id=chat_id, turn_id=_turn(temp_db, chat_id)),
            results)

        meta = results["ext:alpha:docs"]
        assert meta["path"] == "domain/wrote"
        assert meta["revision"] == 1
        assert alpha.documents(chat_id).get("domain/wrote") is True


# ------------------------------------------------------------- list / delete


class TestListAndDelete:
    def test_list_prefixes_are_segment_aware(self, temp_db, pair):
        """`missions` matches `missions` and `missions/1`, never
        `missions2/1`: a character-prefix match would bleed one directory's
        namespace into its lexical neighbour's."""
        alpha, _ = pair
        docs = alpha.documents(_chat(temp_db))
        for path in ("missions", "missions/1", "missions/2/deep",
                     "missions2/1", "other"):
            docs.put_now(path, path)

        assert [m["path"] for m in docs.list("missions")] == [
            "missions", "missions/1", "missions/2/deep"]
        assert len(docs.list()) == 5

    def test_delete_is_idempotent_and_answers_honestly(self, temp_db, pair):
        alpha, _ = pair
        docs = alpha.documents(_chat(temp_db))
        docs.put_now("once", 1)
        assert docs.delete_now("once") is True
        assert docs.delete_now("once") is False
        assert docs.get("once") is None

    def test_delete_prefix_reports_the_count_and_is_segment_aware(
            self, temp_db, pair):
        alpha, _ = pair
        docs = alpha.documents(_chat(temp_db))
        for path in ("m/1", "m/2", "m2/1"):
            docs.put_now(path, 1)
        assert docs.delete_prefix_now("m") == 2
        assert [x["path"] for x in docs.list()] == ["m2/1"]


# -------------------------------------------------------------------- verify


class TestVerify:
    def test_a_clean_store_verifies_clean(self, temp_db, pair):
        alpha, _ = pair
        docs = alpha.documents(_chat(temp_db))
        docs.put_now("a", {"fine": True})
        docs.put_now("b/c", [1, 2])
        assert docs.verify() == {"ok": True, "checked": 2, "damaged": []}

    def test_verify_reports_damage_without_throwing(self, temp_db, pair):
        """The whole reason the surface exists: the integrity screen asks
        `verify` and gets ROWS, never an exception -- a check that dies on
        the first broken row cannot tell you about the second. Three kinds
        of damage, all reported by path: unparseable row text, a row with no
        envelope (written around the store), and a content-hash mismatch
        (altered or corrupted at rest)."""
        alpha, _ = pair
        chat_id = _chat(temp_db)
        docs = alpha.documents(chat_id)
        docs.put_now("fine", 1)
        docs.put_now("rotten", {"v": 1})
        docs.put_now("tampered", {"v": 1})

        # Corrupt one row's raw text, bypassing the store entirely.
        temp_db.qi("UPDATE world SET value=? WHERE chat_id=? AND key=?",
                   ("{not json", chat_id, "ext:alpha:doc:rotten"))
        # Alter a document without updating its recorded hash.
        row = temp_db.q("SELECT value FROM world WHERE chat_id=? AND key=?",
                        (chat_id, "ext:alpha:doc:tampered"), one=True)
        envelope = json.loads(row["value"])
        envelope["doc"] = {"v": "altered"}
        temp_db.qi("UPDATE world SET value=? WHERE chat_id=? AND key=?",
                   (json.dumps(envelope), chat_id,
                    "ext:alpha:doc:tampered"))
        # A bare value written around the store has no envelope.
        from core.db import wset
        wset(chat_id, "ext:alpha:doc:bare", {"no": "envelope"})

        report = docs.verify()
        assert report["ok"] is False
        assert report["checked"] == 4
        by_path = {d["path"]: d["error"] for d in report["damaged"]}
        assert set(by_path) == {"rotten", "tampered", "bare"}
        assert "not JSON" in by_path["rotten"]
        assert "hash mismatch" in by_path["tampered"]
        assert "envelope" in by_path["bare"]

    def test_get_refuses_a_damaged_document(self, temp_db, pair):
        """Absence and damage are different answers. `get` returning
        `default` for a row `verify` reports as broken would be a lie the
        caller cannot detect."""
        alpha, _ = pair
        chat_id = _chat(temp_db)
        docs = alpha.documents(chat_id)
        docs.put_now("hurt", 1)
        temp_db.qi("UPDATE world SET value=? WHERE chat_id=? AND key=?",
                   ("{not json", chat_id, "ext:alpha:doc:hurt"))
        with pytest.raises(ExtensionError, match="not JSON"):
            docs.get("hurt", default="hides the damage")

    def test_list_flags_damaged_rows_instead_of_dying(self, temp_db, pair):
        alpha, _ = pair
        chat_id = _chat(temp_db)
        docs = alpha.documents(chat_id)
        docs.put_now("ok", 1)
        docs.put_now("bad", 1)
        temp_db.qi("UPDATE world SET value=? WHERE chat_id=? AND key=?",
                   ("{not json", chat_id, "ext:alpha:doc:bad"))
        listed = {m["path"]: m for m in docs.list()}
        assert listed["bad"]["damaged"] is True
        assert "damaged" not in listed["ok"]

    def test_overwriting_damage_is_repair(self, temp_db, pair):
        """A put over a broken row succeeds and restarts the revision count:
        the alternative -- refusing until the row is hand-deleted -- would
        make the one legitimate fix need a database console."""
        alpha, _ = pair
        chat_id = _chat(temp_db)
        docs = alpha.documents(chat_id)
        docs.put_now("heal", 1)
        temp_db.qi("UPDATE world SET value=? WHERE chat_id=? AND key=?",
                   ("{not json", chat_id, "ext:alpha:doc:heal"))
        meta = docs.put_now("heal", 2)
        assert meta["revision"] == 1
        assert docs.verify()["ok"] is True


# ------------------------------------------- checkpoint / archive / branch


class TestPersistenceRides:
    def test_story_documents_ride_a_checkpoint_restore(self, temp_db, pair):
        """The entire argument for KV rows over a new table: a checkpoint
        snapshots the world table wholesale, so a rewound beat takes its
        documents with it -- writes after the checkpoint are undone, and a
        document created after it is GONE, not orphaned."""
        from persist.checkpoints import ensure_checkpoint, restore_checkpoint

        alpha, _ = pair
        chat_id = _chat(temp_db, "Rewind")
        docs = alpha.documents(chat_id)
        docs.put_now("campaign/stage", {"stage": 1})
        ensure_checkpoint(chat_id, 3)
        docs.put_now("campaign/stage", {"stage": 2})
        docs.put_now("campaign/late", {"born": "after the checkpoint"})

        restore_checkpoint(chat_id, 3)

        assert docs.get("campaign/stage") == {"stage": 1}
        assert docs.get("campaign/late") is None
        assert [m["path"] for m in docs.list()] == ["campaign/stage"]

    def test_install_documents_survive_a_story_restore(self, temp_db, pair):
        """The other half of the scope decision: the install's library is
        host configuration, and rewinding one story must not touch it."""
        from persist.checkpoints import ensure_checkpoint, restore_checkpoint

        alpha, _ = pair
        chat_id = _chat(temp_db)
        ensure_checkpoint(chat_id, 1)
        alpha.documents().put_now("library/pack", {"v": 3})

        restore_checkpoint(chat_id, 1)

        assert alpha.documents().get("library/pack") == {"v": 3}

    def test_story_documents_ride_export_and_import(self, temp_db, pair):
        from web import app
        from persist.checkpoints import ensure_checkpoint

        alpha, _ = pair
        chat_id = _chat(temp_db, "Rides")
        alpha.documents(chat_id).put_now("missions/epsilon", {"stage": 2})
        ensure_checkpoint(chat_id, 0)

        imported = app.chat_import({"data": app.chat_export(chat_id)})

        moved = alpha.documents(imported["id"])
        assert moved.get("missions/epsilon") == {"stage": 2}
        assert moved.verify() == {"ok": True, "checked": 1, "damaged": []}

    def test_story_documents_ride_a_branch(self, temp_db, pair):
        """Branching copies the checkpoint blob's world dict wholesale, so
        the branch holds the documents AS OF the branch point -- and a write
        on the branch afterwards must not reach back into the source."""
        from web import app
        from persist.checkpoints import ensure_checkpoint

        alpha, _ = pair
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Trunk", "", time.time()))
        docs = alpha.documents(chat_id)
        docs.put_now("campaign/stage", {"stage": 1})
        tid = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) "
            "VALUES(?,?,?,?)", (chat_id, 0, "do", time.time()))
        ensure_checkpoint(chat_id, 0)
        ensure_checkpoint(chat_id, 1)
        docs.put_now("campaign/late", {"after": "the branch point"})

        branched = app.turn_branch(tid)
        branch_docs = alpha.documents(branched["id"])

        assert branch_docs.get("campaign/stage") == {"stage": 1}
        assert branch_docs.get("campaign/late") is None
        branch_docs.put_now("campaign/stage", {"stage": 99})
        assert docs.get("campaign/stage") == {"stage": 1}


# --------------------------------------------------------------- HTTP routes


class TestRoutes:
    """The host routes, called as the functions they are -- the same way
    `chat_export`/`chat_import` are exercised. They exist so a browser half
    (a Settings screen's storage check) can use the store without writing a
    Python route of its own."""

    def test_put_get_list_verify_delete_over_http(self, temp_db, pair):
        from web import app

        chat_id = _chat(temp_db)
        meta = app.extension_document_put(
            "alpha", "missions/epsilon", {"doc": {"stage": 2}},
            chat_id=chat_id)
        assert meta["revision"] == 1

        got = app.extension_document_get("alpha", "missions/epsilon",
                                         chat_id=chat_id)
        assert got["doc"] == {"stage": 2}
        assert got["meta"]["sha256"] == meta["sha256"]

        listed = app.extension_documents_list("alpha", chat_id=chat_id)
        assert [m["path"] for m in listed["documents"]] == [
            "missions/epsilon"]

        report = app.extension_documents_verify("alpha", chat_id=chat_id)
        assert report == {"ok": True, "checked": 1, "damaged": []}

        assert app.extension_document_delete(
            "alpha", "missions/epsilon", chat_id=chat_id) == {
                "deleted": True}

    def test_the_routes_speak_400_for_a_refused_path(self, temp_db, pair):
        from web import app
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as err:
            app.extension_document_put("alpha", "../up", {"doc": 1},
                                       chat_id=_chat(temp_db))
        assert err.value.status_code == 400

    def test_a_body_without_the_doc_envelope_is_refused(self, temp_db, pair):
        from web import app
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as err:
            app.extension_document_put("alpha", "a", {"value": 1},
                                       chat_id=_chat(temp_db))
        assert err.value.status_code == 400

    def test_prefix_delete_over_http_reports_the_count(self, temp_db, pair):
        from web import app

        alpha, _ = pair
        chat_id = _chat(temp_db)
        alpha.documents(chat_id).put_now("m/1", 1)
        alpha.documents(chat_id).put_now("m/2", 1)
        assert app.extension_documents_delete(
            "alpha", prefix="m", chat_id=chat_id) == {"deleted": 2}

    def test_install_scope_is_the_absent_chat_id(self, temp_db, pair):
        from web import app

        app.extension_document_put("alpha", "library/pack", {"doc": {"v": 1}})
        assert app.extension_document_get(
            "alpha", "library/pack")["doc"] == {"v": 1}
        assert app.extension_documents_list(
            "alpha", chat_id=_chat(temp_db))["documents"] == []
