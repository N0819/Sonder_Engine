"""A discarded run must leave no trace: reroll/restore coherence.

Three live failure modes of the same shape -- restore_checkpoint rewrites
durable state, but something either escapes the rewrite or was cached before
it ran, so a rerolled turn re-executes against fragments of the timeline it
was supposed to discard:

1. `_run_pipeline` builds `ctx.cast` (including each character's `cstate`)
   BEFORE restore_checkpoint runs.  The restore rewrites `chat_chars.state`,
   but the pipeline keeps deliberating with the discarded run's POST-turn
   interior -- so a rerolled onset decision already "feels" the outcome it is
   supposed to be deciding blind, and commit then evolves psychology from the
   discarded post-state (stance/stress/charge ratchet a second time).

2. `background_presences` sat in PRESERVED_SETTING_KEYS, so an erased
   timeline's spoken line stayed in the conduct tail voiced back to the
   presence, its write-once blurb anchored identity from a discarded run, and
   `pending_reply` debts survived into a timeline where the address never
   happened.  It is diegetic bookkeeping written by every commit, not a
   reader dial.

3. A character promoted to the cast DURING the discarded run kept its
   `chat_chars` membership after restore: its state, recognition, and seed
   memories rolled back, leaving a hollow active cast member that could
   neither be re-tracked as a presence nor cleanly re-promoted.
"""

from __future__ import annotations

import json
import time

from db import q, qi, wget, wset


def _make_chat(db, name="Restore Chat"):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        (name, "", time.time()),
    )


def _attach_character(db, chat_id, name, state=None):
    from character_schema import default_character_data

    char_id = db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (name, json.dumps(default_character_data(name)), "{}",
         time.time(), f"char_{name.lower()}"),
    )
    db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", json.dumps(state or {})),
    )
    return char_id


def test_background_presences_roll_back_with_the_timeline(temp_db):
    """A presence's conduct tail/blurb/pending_reply written by a discarded
    run must not survive into the rerun -- they are story bookkeeping, not a
    reader preference (audit P3/X22)."""
    from checkpoints import ensure_checkpoint, restore_checkpoint

    chat_id = _make_chat(temp_db)
    pre = {"Barkeep": {"mentions": 1, "conduct": ["polishes a glass"]}}
    wset(chat_id, "background_presences", pre)
    # A genuine reader dial, to prove the fix does not overshoot.
    wset(chat_id, "dialogue_config", {"max_micro_rounds": 3})
    ensure_checkpoint(chat_id, 4)

    # The run being discarded: the presence spoke, and a dial was turned.
    wset(chat_id, "background_presences", {
        "Barkeep": {"mentions": 2,
                    "conduct": ["polishes a glass", "mutters a warning"],
                    "pending_reply": {"speaker": "someone"}},
    })
    wset(chat_id, "dialogue_config", {"max_micro_rounds": 5})

    restore_checkpoint(chat_id, 4)

    assert wget(chat_id, "background_presences", None) == pre
    # Reader settings still survive the rollback.
    assert wget(chat_id, "dialogue_config", {}) == {"max_micro_rounds": 5}


def test_membership_added_after_the_checkpoint_is_removed(temp_db):
    """A character auto-promoted during the discarded run must not survive
    restore as a hollow active cast member (audit P4).  The reusable library
    row survives -- only this chat's membership is rolled back."""
    from checkpoints import ensure_checkpoint, restore_checkpoint

    chat_id = _make_chat(temp_db)
    kept = _attach_character(temp_db, chat_id, "Alice")
    ensure_checkpoint(chat_id, 7)

    promoted = _attach_character(temp_db, chat_id, "Barkeep")

    restore_checkpoint(chat_id, 7)

    members = {r["char_id"] for r in q(
        "SELECT char_id FROM chat_chars WHERE chat_id=?", (chat_id,))}
    assert members == {kept}
    # The library resource is untouched; only membership rolled back.
    assert q("SELECT id FROM characters WHERE id=?", (promoted,), one=True)


def test_rerun_cast_state_is_the_restored_state(temp_db):
    """`ctx.cast` must reflect the pre-turn `chat_chars.state` the restore
    just wrote, not the discarded run's post-turn interior cached before the
    restore ran (audit P2 -- the cstate side of the audit-#10 reroll leak)."""
    import agents.runtime as runtime

    chat_id = _make_chat(temp_db)
    char_id = _attach_character(
        temp_db, chat_id, "Alice",
        state={"active_state": {"mood": "calm", "goal": "rest"}})

    turn_id = qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "I wave.", time.time()),
    )
    # The pre-turn checkpoint captures mood "calm".
    from checkpoints import ensure_checkpoint
    ensure_checkpoint(chat_id, 1)

    # The turn "ran" and committed: one materialized step, and the commit
    # mutated the character's live interior.
    step_id = qi(
        "INSERT INTO steps(turn_id,key,label,ord,stale) VALUES(?,?,?,?,0)",
        (turn_id, "commit", "Commit", 9),
    )
    qi("INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
       (step_id, json.dumps({"ok": True}), time.time()))
    qi("UPDATE chat_chars SET state=? WHERE chat_id=? AND char_id=?",
       (json.dumps({"active_state": {"mood": "shattered", "goal": "flee"}}),
        chat_id, char_id))

    seen_cast = []

    def _capture_step(bus, turn_id_, key, label, ord_, ctx, count):
        seen_cast.append([dict(c) for c in ctx.cast])
        return iter(())

    original = runtime._step_stream
    runtime._step_stream = _capture_step
    try:
        list(runtime._run_pipeline(chat_id, turn_id, only_key="commit"))
    finally:
        runtime._step_stream = original

    assert seen_cast, "the stubbed step was never reached"
    cstate = json.loads(seen_cast[0][0]["cstate"] or "{}")
    assert cstate.get("active_state", {}).get("mood") == "calm", (
        "rerun deliberated with the discarded run's post-turn interior"
    )


class TestRestoreMembershipGuards:
    """P4 removes cast membership added since the checkpoint, but the sweep
    that does it can destroy more than the promotion it was written for."""

    def _chat_with_snapshot(self, temp_db, blob):
        import json as _json
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("T", "", time.time()))
        temp_db.qi(
            "INSERT INTO checkpoints(chat_id,turn_idx,blob,created) "
            "VALUES(?,?,?,?)",
            (chat_id, 1, _json.dumps(blob), time.time()))
        return chat_id

    def _attach(self, temp_db, chat_id, name, sheet=None):
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
            (name, "{}", "{}", time.time()))
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state,sheet) "
            "VALUES(?,?,'active','{}',?)",
            (chat_id, char_id, sheet))
        return char_id

    def test_auto_promoted_member_is_removed(self, temp_db):
        import checkpoints
        chat_id = self._chat_with_snapshot(temp_db, {"world": {}, "chars": {}})
        promoted = self._attach(temp_db, chat_id, "Promoted")
        checkpoints.restore_checkpoint(chat_id, 1)
        rows = temp_db.q(
            "SELECT char_id FROM chat_chars WHERE chat_id=?", (chat_id,))
        assert [r["char_id"] for r in rows] == []
        assert promoted

    def test_a_legacy_blob_without_a_chars_key_does_not_wipe_the_cast(
            self, temp_db):
        """`b.get("chars") or {}` reads identically for 'no cast' and 'no such
        key', so an unguarded sweep deleted every cast member of any chat whose
        checkpoint predates the chars field."""
        import checkpoints
        chat_id = self._chat_with_snapshot(temp_db, {"world": {}})
        kept = self._attach(temp_db, chat_id, "Established")
        checkpoints.restore_checkpoint(chat_id, 1)
        rows = temp_db.q(
            "SELECT char_id FROM chat_chars WHERE chat_id=?", (chat_id,))
        assert [r["char_id"] for r in rows] == [kept]

    def test_an_authored_per_story_card_is_not_destroyed(self, temp_db):
        """chat_chars.sheet is Cast-tab authoring, is not in the snapshot, and
        DELETE has nothing to restore it from."""
        import checkpoints
        chat_id = self._chat_with_snapshot(temp_db, {"world": {}, "chars": {}})
        carded = self._attach(
            temp_db, chat_id, "Carded", sheet='{"identity": {"name": "Carded"}}')
        checkpoints.restore_checkpoint(chat_id, 1)
        row = temp_db.q(
            "SELECT sheet FROM chat_chars WHERE chat_id=? AND char_id=?",
            (chat_id, carded), one=True)
        assert row is not None
        assert "Carded" in row["sheet"]
