"""A branch's memories must survive branching AND a round trip through export.

`memories.event_key` is deliberately COPY-STABLE. `mind/memory_snapshot.
dump_memory_summaries` states the contract outright: a summary's per-clause
`support` holds event_keys, "which restore preserves verbatim, so this needs
no id remapping on branch, clone or checkpoint rollback -- the reason it was
built out of event_keys rather than row ids."

So a branch carrying the source's keys is the design, not a defect, and any
future change that remaps or blanks them on copy silently dangles every
summary's support. That failure is invisible: the summaries still load, the
memories still load, and only the link between them is gone. These tests are
the guard, written after a proposed "fix" did exactly that.

The last one leaves the fixtures behind and drives a real reroll through
`commit_memories`, because that is the shape the reported bug had and no test
here reached it. `tools/project_check.check_memory_identity_writers` enforces
the coupling these rely on: only `persist/commit_memory.py` may mint a key
from `turn.id`, and every other memory writer declares how it keeps a row's
identity re-derivable.
"""

from __future__ import annotations

import json
import time

from web import app
from persist.checkpoints import ensure_checkpoint
from agents.common import _stable_event_key
from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist.commit import commit_memories


def _story(db):
    """One chat, one character, two memories, one summary citing them both."""
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Branch source", "", time.time()))
    char_id = db.qi(
        "INSERT INTO characters(name,sheet,created) VALUES(?,?,?)",
        ("Hinami", "{}", time.time()))
    db.qi("INSERT INTO chat_chars(chat_id,char_id) VALUES(?,?)",
          (cid, char_id))
    frame_id = db.qi(
        "INSERT INTO frames(chat_id,label,ordinal,kind,created) "
        "VALUES(?,?,?,?,?)", (cid, "Present", 0, "present", time.time()))
    turn_id = db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
        "VALUES(?,?,?,?,?)", (cid, 0, "wait", time.time(), frame_id))
    keys = []
    for slot, text in (("episode", "I heard her say she was born with them."),
                       ("own_acts", "I said 'People do not grow fox ears.'")):
        key = _stable_event_key(turn_id, char_id, slot)
        keys.append(key)
        db.qi(
            "INSERT INTO memories(chat_id,char_id,turn_id,turn_idx,kind,"
            "provenance,salience,content,event_key) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (cid, char_id, turn_id, 0, "episodic", "witnessed", 0.5, text, key))
    db.qi(
        "INSERT INTO memory_summaries(chat_id,char_id,scope,start_turn_idx,"
        "end_turn_idx,summary,support,updated) VALUES(?,?,?,?,?,?,?,?)",
        (cid, char_id, "recent", 0, 0, "She explained her ears.",
         json.dumps([{"clause": "She explained her ears.", "refs": keys}]),
         time.time()))
    return cid, char_id, turn_id, keys


def _memories(db, cid):
    return {(r["content"], r["event_key"]) for r in db.q(
        "SELECT content, event_key FROM memories WHERE chat_id=?", (cid,))}


def _dangling_refs(db, cid):
    """Summary support refs in `cid` that name no memory in `cid`."""
    keys = {r["event_key"] for r in db.q(
        "SELECT event_key FROM memories WHERE chat_id=?", (cid,))}
    dangling = []
    for row in db.q(
            "SELECT support FROM memory_summaries WHERE chat_id=?", (cid,)):
        for clause in json.loads(row["support"] or "[]"):
            for ref in clause.get("refs") or []:
                if ref not in keys:
                    dangling.append(ref)
    return dangling


def test_branch_carries_memories_and_their_summary_links(temp_db):
    cid, char_id, turn_id, keys = _story(temp_db)

    ncid = app.turn_branch(turn_id)["id"]

    assert _memories(temp_db, ncid) == _memories(temp_db, cid), (
        "the branch's memories differ from the source's")
    assert _dangling_refs(temp_db, ncid) == [], (
        "branching left summary support refs naming no memory")


def test_exporting_a_branch_round_trips_its_memories(temp_db):
    """The case that matters for actually moving a branch somewhere: export
    a BRANCH (not the original) and import it back."""
    cid, char_id, turn_id, keys = _story(temp_db)
    ncid = app.turn_branch(turn_id)["id"]
    branch_memories = _memories(temp_db, ncid)
    assert branch_memories, "the branch carried no memories to export"

    # The app's own wired instance, so this exercises the remappers
    # production uses rather than a hand-built stand-in.
    service = app._chat_archive_service
    imported = service.import_chat({"data": service.export_chat(ncid)})
    icid = imported["id"] if isinstance(imported, dict) else imported

    assert _memories(temp_db, icid) == branch_memories, (
        "exporting a branch and importing it changed its memories")
    assert _dangling_refs(temp_db, icid) == [], (
        "the imported branch's summary support names no memory")


def test_exported_branch_keeps_its_memories_whole_not_merely_present(temp_db):
    """Count and content, so a partial carry cannot pass by leaving one row
    behind -- the shape `_memories` alone would hide if both sides shrank."""
    cid, char_id, turn_id, keys = _story(temp_db)
    ncid = app.turn_branch(turn_id)["id"]
    service = app._chat_archive_service
    imported = service.import_chat({"data": service.export_chat(ncid)})
    icid = imported["id"] if isinstance(imported, dict) else imported

    n = temp_db.q("SELECT COUNT(*) AS n FROM memories WHERE chat_id=?",
                  (icid,), one=True)["n"]
    assert n == 2, f"expected both memories to survive export, found {n}"
    contents = {r["content"] for r in temp_db.q(
        "SELECT content FROM memories WHERE chat_id=?", (icid,))}
    assert contents == {"I heard her say she was born with them.",
                        "I said 'People do not grow fox ears.'"}


def test_checkpoint_rollback_restores_memories_and_their_links(temp_db):
    """Rollback is the third path that moves memory rows in bulk, and the
    one that actually reached the reported chat: `restore_checkpoint`
    delete-and-reinserts every memory for the chat from a blob. A summary
    whose support no longer names a memory would be invisible -- both tables
    load fine, only the link is gone."""
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint

    cid, char_id, turn_id, keys = _story(temp_db)
    before = _memories(temp_db, cid)
    ensure_checkpoint(cid, 0)

    # Whatever a later turn did, rollback must undo.
    temp_db.qi("UPDATE memories SET content=? WHERE chat_id=?",
               ("a later, rejected take", cid))
    temp_db.qi(
        "INSERT INTO memories(chat_id,char_id,turn_id,turn_idx,kind,"
        "provenance,salience,content,event_key) VALUES(?,?,?,?,?,?,?,?,?)",
        (cid, char_id, turn_id, 1, "episodic", "witnessed", 0.5, "extra",
         _stable_event_key(turn_id, char_id, "episode_later")))

    restore_checkpoint(cid, 0)

    assert _memories(temp_db, cid) == before, (
        "rollback did not restore the memories the checkpoint captured")
    assert _dangling_refs(temp_db, cid) == [], (
        "rollback left summary support naming no memory")


def test_rollback_inside_a_branch_restores_the_branch_own_memories(temp_db):
    """The reported shape: roll back inside a BRANCH, whose checkpoints were
    copied from its source. The rows restored must be the branch's own."""
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint

    cid, char_id, turn_id, keys = _story(temp_db)
    ncid = app.turn_branch(turn_id)["id"]
    branch_before = _memories(temp_db, ncid)
    ensure_checkpoint(ncid, 0)

    temp_db.qi("UPDATE memories SET content=? WHERE chat_id=?",
               ("rerolled take", ncid))
    restore_checkpoint(ncid, 0)

    assert _memories(temp_db, ncid) == branch_before, (
        "rollback in a branch did not restore the branch's own memories")
    assert _dangling_refs(temp_db, ncid) == [], (
        "rollback in a branch left summary support naming no memory")
    # And it must not have reached into the chat it was branched from: the
    # source's rows share these event_keys, so a restore scoped by key rather
    # than by chat_id would silently rewrite another story's memories.
    assert _memories(temp_db, cid) == branch_before, (
        "rollback in a branch altered the chat it was branched from")


def test_recommitting_a_turn_keeps_its_memory_identities(temp_db):
    """The invariant that makes `event_key` worth minting from `turn.id`.

    Re-running a turn must land on the SAME identities, so `_upsert_memory`
    updates the rows in place and every summary clause that cited them still
    resolves. A mint keyed to anything that changes between runs -- content,
    ordering, a fresh row id -- would silently turn each re-run into a new set
    of rows and strand the audit trail behind the old ones.

    This is the test that refuses the tempting "fix" of re-deriving
    `event_key` from a copy-stable identity instead: `turn.id` is stable
    across a re-run, which is the property actually being relied on, and the
    two paths that reconcile by key WITHOUT deleting first
    (`story/greetings.py`'s content digest, `world/offscreen.py`'s
    chat-scoped agent key) do not use this mint at all.
    """
    cid, char_id, turn_id, keys = _story(temp_db)
    before = {r["event_key"] for r in temp_db.q(
        "SELECT event_key FROM memories WHERE chat_id=?", (cid,))}

    # What a re-run does: drop the turn's rows, mint them again from the same
    # turn. The identities must come back identical.
    from mind.memory import delete_turn_memories
    delete_turn_memories(turn_id)
    for slot, text in (("episode", "a differently worded take"),
                       ("own_acts", "and a different line said")):
        temp_db.qi(
            "INSERT INTO memories(chat_id,char_id,turn_id,turn_idx,kind,"
            "provenance,salience,content,event_key) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (cid, char_id, turn_id, 0, "episodic", "witnessed", 0.5, text,
             _stable_event_key(turn_id, char_id, slot)))

    after = {r["event_key"] for r in temp_db.q(
        "SELECT event_key FROM memories WHERE chat_id=?", (cid,))}
    assert after == before, "a re-run changed the turn's memory identities"
    assert _dangling_refs(temp_db, cid) == [], (
        "a re-run stranded the summary support that cited these memories")


def _played_chat(db, name):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                (name, "", time.time()))
    char_id = db.qi("INSERT INTO characters(name,sheet,created) VALUES(?,?,?)",
                    ("Alice", '{"name":"Alice"}', time.time()))
    db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
          "VALUES(?,?,?,?)", (cid, char_id, "active", "{}"))
    db.wset(cid, "scene", {"rooms": {"kitchen": {"name": "Kitchen"}},
                           "positions": {"Alice": "kitchen"},
                           "entities": {}, "attire": {}, "overlays": {}})
    tid = db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                "VALUES(?,?,?,?)", (cid, 0, "hello", time.time()))
    return cid, char_id, tid


def _commit_ctx(db, cid, char_id, tid, view):
    cast = db.q("SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
                "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
                (cid,))
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="T", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=tid, chat_id=cid, idx=0, player_input="hello",
                      created=time.time()),
        cast=cast, input="hello")
    ctx.director_resolve = {"summary": "s", "resolved_event": view,
                            "dialogue_log": []}
    ctx.perception_outcome = {"views": {str(char_id): view}}
    ctx.character_results = {char_id: {
        "sequence": [], "appraisal": {"goal_impacts": []},
        "active_state": {"affect": {"surface": {"label": "calm",
                                                "valence": 0.1,
                                                "arousal": 0.1}},
                         "hedonic": {"released": True}, "wants": []}}}
    return ctx


def _memory_contents(db, cid):
    return [r["content"] for r in db.q(
        "SELECT content FROM memories WHERE chat_id=? ORDER BY id", (cid,))]


def test_rerolling_a_branched_turn_lands_the_new_take(temp_db):
    """The end-to-end shape the reported bug had, driven through the real
    commit path rather than through SQL fixtures: commit a turn, branch it,
    then re-commit the branch's copy from different stage output. The
    branch must end holding the new take and not the rejected one, and the
    chat it came from must be untouched.

    This passes today, which is the useful part: it rules `commit_memories`
    OUT as the cause of a branch that kept its pre-reroll memories, and
    pins that path so a later change cannot quietly become the cause."""
    TAKE_ONE = "Alice sees the lamp is GREEN and says so."
    TAKE_TWO = "Alice sees the lamp is CRIMSON and says so."

    cid, char_id, tid = _played_chat(temp_db, "source")
    commit_memories(_commit_ctx(temp_db, cid, char_id, tid, TAKE_ONE), "n1",
                    consolidate=False)
    assert any("GREEN" in c for c in _memory_contents(temp_db, cid)), \
        f"take one never landed: {_memory_contents(temp_db, cid)}"

    ncid = app.turn_branch(tid)["id"]
    btid = temp_db.q("SELECT id FROM turns WHERE chat_id=? AND idx=0",
                     (ncid,), one=True)["id"]
    bchar = temp_db.q("SELECT char_id FROM chat_chars WHERE chat_id=?",
                      (ncid,), one=True)["char_id"]
    assert any("GREEN" in c for c in _memory_contents(temp_db, ncid)), \
        "the branch did not carry take one"

    # The reroll: same turn, different stage output.
    commit_memories(_commit_ctx(temp_db, ncid, bchar, btid, TAKE_TWO), "n2",
                    consolidate=False)

    after = _memory_contents(temp_db, ncid)
    assert any("CRIMSON" in c for c in after), \
        f"the reroll's memories never landed in the branch: {after}"
    assert not any("GREEN" in c for c in after), \
        f"the branch still holds the rejected take: {after}"
    # And the source is untouched.
    assert any("GREEN" in c for c in _memory_contents(temp_db, cid))


def _played_turns(db, turns=4):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Src", "", time.time()))
    char_id = db.qi("INSERT INTO characters(name,sheet,created) VALUES(?,?,?)",
                    ("Alice", "{}", time.time()))
    db.qi("INSERT INTO chat_chars(chat_id,char_id) VALUES(?,?)", (cid, char_id))
    fid = db.qi("INSERT INTO frames(chat_id,label,ordinal,kind,created) "
                "VALUES(?,?,?,?,?)", (cid, "Present", 0, "present", time.time()))
    tids = []
    for i in range(turns):
        ensure_checkpoint(cid, i)          # state BEFORE turn i
        tid = db.qi("INSERT INTO turns(chat_id,idx,player_input,created,"
                    "frame_id) VALUES(?,?,?,?,?)",
                    (cid, i, f"turn{i}", time.time(), fid))
        tids.append(tid)
        db.qi("INSERT INTO memories(chat_id,char_id,turn_id,turn_idx,kind,"
              "provenance,salience,content,event_key) "
              "VALUES(?,?,?,?,?,?,?,?,?)",
              (cid, char_id, tid, i, "episodic", "witnessed", 0.5,
               f"memory from turn {i}", _stable_event_key(tid, char_id, "ep")))
    return cid, char_id, tids


def _memory_turn_idxs(db, cid):
    return sorted(r["turn_idx"] for r in db.q(
        "SELECT turn_idx FROM memories WHERE chat_id=?", (cid,)))


def test_branch_with_a_checkpoint_stops_at_the_branch_point(temp_db):
    cid, char_id, tids = _played_turns(temp_db)
    ensure_checkpoint(cid, 2)              # state before turn 2 == after turn 1
    ncid = app.turn_branch(tids[1])["id"]
    assert _memory_turn_idxs(temp_db, ncid) == [0, 1], (
        f"branch at turn 1 carried {_memory_turn_idxs(temp_db, ncid)}")


def test_branch_without_a_next_checkpoint_stops_at_the_branch_point(temp_db):
    """The fallback path: with no checkpoint at idx+1, turn_branch snapshots
    the chat's CURRENT state -- which is the state after every turn played,
    not the state at the branch point."""
    cid, char_id, tids = _played_turns(temp_db)
    temp_db.qi("DELETE FROM checkpoints WHERE chat_id=? AND turn_idx>?",
               (cid, 1))
    ncid = app.turn_branch(tids[1])["id"]
    assert _memory_turn_idxs(temp_db, ncid) == [0, 1], (
        f"branch at turn 1 carried {_memory_turn_idxs(temp_db, ncid)} -- memories from "
        "after the branch point came across")


def test_a_memory_with_no_turn_still_crosses_the_branch(temp_db):
    """The exception the horizon rule must not swallow. A greeting seed is
    written with `turn_id=None` (`story/greetings.py`), so it is not after
    anything and belongs to the branch as much as to the source. Dropping
    every unmapped row indiscriminately would silently delete the opening
    memories of every branched story."""
    cid, char_id, tids = _played_turns(temp_db)
    temp_db.qi(
        "INSERT INTO memories(chat_id,char_id,turn_id,turn_idx,kind,"
        "provenance,salience,content,event_key) "
        "VALUES(?,?,?,?,?,?,?,?,?)",
        (cid, char_id, None, 0, "episodic", "remembered", 0.5,
         "the story opened here", "greeting_seed:abc123"))
    temp_db.qi("DELETE FROM checkpoints WHERE chat_id=? AND turn_idx>?",
               (cid, 1))

    ncid = app.turn_branch(tids[1])["id"]

    carried = {r["content"] for r in temp_db.q(
        "SELECT content FROM memories WHERE chat_id=?", (ncid,))}
    assert "the story opened here" in carried, (
        "the horizon rule dropped a turnless memory")
