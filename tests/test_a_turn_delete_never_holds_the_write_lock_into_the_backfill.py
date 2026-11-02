"""A turn delete restores as its own outermost transaction, so nothing the
restore does after its commit runs under the global write lock.

`turn_del` ran `restore_checkpoint` inside its own `transaction()`, and the
restore's tail -- the embedding-bank probe, `about_backfill.backfill_chat`,
the world-epoch bump -- is written to run AFTER the restore commits. Nested,
it ran with `_write_lock` still held, and `backfill_chat` takes the chat's
backfill lock. The startup pass (`web.app._reconcile_embedding_bank` ->
`backfill_all`) holds that same lock while it computes and then waits for the
write lock to file its tags: the two orders cross, and every writer in the
process waited forever (audit 2026-11-01, persistence_paths_schema F1,
reproduced: both threads still alive after 3 s).

The delete's own rows ride inside the restore's transaction instead (asked
under its lock, before anything is restored), so a failed delete still
leaves the chat exactly as it was -- `test_app_audit_transactionality`'s
`TestTurnDelAtomicity` holds that half.
"""
from __future__ import annotations

import json
import threading
import time


def _story(db):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Lock", "", time.time()))
    db.wset(cid, "flag", "before")
    from persist.checkpoints import ensure_checkpoint
    ensure_checkpoint(cid, 0)
    tid = db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                (cid, 0, "I wait.", time.time()))
    sid = db.qi("INSERT INTO steps(turn_id,key,ord,label) VALUES(?,?,?,?)",
                (tid, "narrator", 0, "Narrator · render"))
    db.qi("INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
          (sid, json.dumps({"prose": "x"}), time.time()))
    db.wset(cid, "flag", "after")
    return cid, tid


def test_a_delete_finishes_beside_a_backfill_that_holds_its_chat(temp_db, monkeypatch):
    from persist import about_backfill
    from web import app

    db = temp_db
    cid, tid = _story(db)
    startup = {}
    holding = threading.Event()
    outcome = {}

    def startup_pass(chat_id, counts):
        """The startup pass's shape: the chat's backfill lock held while it
        computes, then the write lock wanted to file the tags."""
        if threading.current_thread() is not startup.get("thread"):
            return  # the restore's own tail: nothing to tag in this story
        holding.set()
        time.sleep(0.4)
        # Bounded, so a regression fails this test instead of wedging the
        # session: a deadlocked acquire would never return.
        got = db._write_lock.acquire(timeout=5)
        outcome["got_write_lock"] = got
        if got:
            db._write_lock.release()

    monkeypatch.setattr(about_backfill, "_backfill_chat", startup_pass)
    backfill = threading.Thread(target=about_backfill.backfill_chat, args=(cid,),
                                name="startup-backfill", daemon=True)
    startup["thread"] = backfill
    backfill.start()
    assert holding.wait(5), "the startup pass never took the chat's lock"

    result = {}

    def delete():
        try:
            result["out"] = app.turn_del(tid)
        except BaseException as exc:  # noqa: BLE001 -- reported below
            result["err"] = exc

    began = time.monotonic()
    deleting = threading.Thread(target=delete, name="turn-del", daemon=True)
    deleting.start()
    deleting.join(15)
    backfill.join(15)
    assert not deleting.is_alive() and not backfill.is_alive()
    assert outcome.get("got_write_lock") is True, (
        "the startup pass waited out its timeout for the write lock: the delete "
        "held it into the restore's backfill")
    assert "err" not in result, result.get("err")
    assert result["out"] == {"ok": True, "carried": 0}
    assert time.monotonic() - began < 4
    assert db.q("SELECT 1 FROM turns WHERE id=?", (tid,), one=True) is None
    assert db.wget(cid, "flag") == "before"


def test_the_restore_is_not_opened_inside_a_transaction_of_the_routes_own():
    """The shape the deadlock needs, read off the route: no `transaction()`
    of `turn_del`'s own may enclose its `restore_checkpoint` call."""
    import inspect
    from web import app

    source = inspect.getsource(app.turn_del)
    call = source.index("restore_checkpoint(cid")
    opened = source.rfind("with transaction()", 0, call)
    assert opened == -1, "turn_del opens a transaction around its restore"


def test_a_turn_with_no_checkpoint_is_still_deleted(temp_db):
    """No snapshot to restore: the rows still go, as they always did."""
    from web import app

    db = temp_db
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Bare", "", time.time()))
    tid = db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                (cid, 0, "", time.time()))
    sid = db.qi("INSERT INTO steps(turn_id,key,ord,label) VALUES(?,?,?,?)",
                (tid, "narrator", 0, "Narrator · render"))
    db.qi("INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
          (sid, "{}", time.time()))
    assert app.turn_del(tid) == {"ok": True, "carried": 0}
    assert db.q("SELECT 1 FROM turns WHERE id=?", (tid,), one=True) is None
    assert db.q("SELECT COUNT(*) AS n FROM steps", one=True)["n"] == 0
    assert db.q("SELECT COUNT(*) AS n FROM variants", one=True)["n"] == 0
