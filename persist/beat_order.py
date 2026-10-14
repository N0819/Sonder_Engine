"""The order commits land in, and what a rewind takes back with it (2026-10-13).

A CHECKPOINT IS AN INSTANT, NOT A TURN NUMBER. A turn's index and its
checkpoint are fixed when the beat BEGINS; its commit lands when it ENDS; and
the beats of two frames overlap -- every commit of the player's beat schedules
each live bubble's beat, which runs beside the player's next one. So
restoring "the world before turn T" takes back everything that landed after
that instant, and two things followed from reading it by turn number alone:

* while a bubble lived, the player's newest page could never be rerolled,
  edited or deleted -- the bubble's beat after it had a higher number, and
  "another frame has advanced" refused;
* a bubble beat with a LOWER number that finished after T began was erased by
  rewinding T, its rows left standing: Home 10 (chat 173) turn 2, and chats
  167 and 170 the same way (docs/experiments/OBSERVE_2026_10_13_home10.md,
  item 3).

The owner, 2026-10-13: the unseen beats are TAKEN BACK and lived again. A
rewind of T takes back, inside its own restore transaction, every beat
nobody declared or saw that a bubble split from T's frame ran after T began:
later beats always, earlier ones whose commit landed after T's checkpoint
was taken. The re-committed page schedules each live bubble's beat again
(`agents.offscreen_beat.schedule_offscreen_beats`); a deleted page's
bubbles live again at that frame's next commit. A beat somebody played in
another frame still refuses the rewind, as it always has.

THE RECORD: `turns.commit_seq`, the chat's next number stamped as the last
write of a commit's transaction (`stamp_commit`), and
`checkpoints.commit_seq`, the newest commit a saved state holds, read
together with the snapshot. Both NULL on rows from before schema v45: no
backfill rewrites the owner's checkpoint blobs (2.8 GB), and an unknown
order reads as it did before -- an earlier-numbered beat is not taken back.
And `turns.offscreen`, WHO WROTE THE ROW: the off-screen beat, or anyone
else. Read off the row, never derived from it -- an empty line a human sent
looks like an off-screen beat until its page is written, and a bubble that
rejoined is no longer a bubble (review of 2026-10-13).

DECIDED UNDER THE LOCK. The plan a route shows is advice: rows land, runs
start and slots free while a rewind stops a beat, and every one of those
changes what the rewind may take back. So the restore asks again inside its
own transaction (`decide`), where no row can change, and refuses outright
while any run but the rewinding one still holds a slot -- nothing runs
across a restore, and no row a run still holds is deleted under it.
"""
from __future__ import annotations

from core.db import q, qi


#: What the route says when a rewind would take back a beat somebody played
#: in another frame -- word for word the sentence the pipeline drawer shows
#: (`chat.js`), as it has been since frames could run side by side.
ANOTHER_FRAME_ADVANCED = (
    "Another frame has advanced since this turn. Recompute here "
    "would silently roll back that frame's progress too -- shared "
    "state (memories, cast, world entities) isn't sliced per frame "
    "in this version.")


class RewindRefused(RuntimeError):
    """A rewind refused under the lock, before anything was written."""


def latest_commit_seq(chat_id) -> int:
    """The newest commit this chat has landed, or 0."""
    row = q("SELECT MAX(commit_seq) AS m FROM turns WHERE chat_id=?", (chat_id,), one=True)
    return int(row["m"] or 0) if row else 0


def stamp_commit(chat_id, turn_id):
    """Stamp `turn_id` with the chat's next commit number. Called as the last
    write inside a commit's transaction, under the write lock, so numbers are
    strictly increasing per chat and a commit that rolls back has none."""
    if turn_id is None:
        return None
    seq = latest_commit_seq(chat_id) + 1
    qi("UPDATE turns SET commit_seq=? WHERE id=?", (seq, turn_id))
    return seq


def settled(chat_id, held, blob, snapshot, version):
    """Under the write lock: `(held, blob)` made exact. Both were read outside
    the lock, `held` before the snapshot and `version` (`db.data_version`)
    before either; anything another connection committed since may be in the
    blob whole or in part, or missing from it, so both are read again here,
    where nothing lands. Otherwise they stand: the blob is the world as it is,
    and it holds exactly the commits numbered up to `held`."""
    from core.db import data_version
    if data_version() == version:
        return held, blob
    return latest_commit_seq(chat_id), snapshot(chat_id)


def checkpoint_seq(chat_id, idx):
    """The newest commit the checkpoint at `idx` holds, or None (none, or
    written before the order was recorded)."""
    row = q("SELECT commit_seq FROM checkpoints WHERE chat_id=? AND turn_idx=?",
            (chat_id, idx), one=True)
    return None if not row or row["commit_seq"] is None else int(row["commit_seq"])


def _frames(chat_id):
    return {r["id"]: dict(r) for r in q(
        "SELECT id, kind, label, parent_frame_id, merged_turn_idx FROM frames WHERE chat_id=?",
        (chat_id,))}


def _has_step(turn_id, key):
    return bool(q("SELECT 1 FROM steps WHERE turn_id=? AND key=? LIMIT 1",
                  (turn_id, key), one=True))


def _committed(turn_id):
    return bool(q(
        "SELECT 1 FROM steps s JOIN variants v ON v.step_id=s.id AND v.active=1 "
        "WHERE s.turn_id=? AND s.key='commit' LIMIT 1", (turn_id,), one=True))


def _split_from(frame, frame_id):
    """A spatial child of `frame_id`: a bubble of it, or a human's away party."""
    return bool(frame and frame.get("kind") == "spatial"
                and frame.get("parent_frame_id") == frame_id)


def _unseen_beat_of(chat_id, turn, frame_id, frames):
    """A beat the engine scheduled for a bubble split from `frame_id`.

    THE ROW SAYS WHO WROTE IT (`turns.offscreen`, since v45): 1 when the
    off-screen beat wrote it, 0 for every other writer -- a line a human
    typed, or an empty Send, wherever it was sent. A row from before v45
    carries NULL and is judged as the runtime judges a turn
    (`agents.offscreen_beat.is_offscreen_beat`): no input and no page, in a
    live bubble -- and, once the bubble has rejoined, by its lineage, since
    the merge that ended it turned `is_bubble_frame` false."""
    frame = frames.get(turn["frame_id"])
    if not _split_from(frame, frame_id):
        return False
    marked = turn.get("offscreen")
    if marked is not None:
        return bool(marked)
    if str(turn["player_input"] or "").strip():
        return False
    if frame.get("merged_turn_idx") is None:
        from world.spatial_frames import is_bubble_frame
        if not is_bubble_frame(chat_id, turn["frame_id"]):
            return False
    return not (_has_step(turn["id"], "narrator") or _has_step(turn["id"], "narrator_extra"))


def _running(running_frames, frame_id):
    """{frame: held by an off-screen beat} for the slots held now, the
    rewound turn's own frame left out. `agents.runtime.running_frames` gives
    the mapping; a plain collection reads as slots of no known kind."""
    if isinstance(running_frames, dict):
        items = running_frames.items()
    else:
        items = ((f, False) for f in (running_frames or ()))
    return {f: bool(kind) for f, kind in items if f != frame_id}


def rewind_plan(chat_id, turn, running_frames=None):
    """What rewinding `turn` to its checkpoint takes back.

    `{carried, blocking, stop, held, reason}`: `carried` the turn rows taken
    back with it (unseen beats of bubbles split from the turn's frame, later
    in play order or landed after its checkpoint, or the one a bubble's
    off-screen beat is writing now), `stop` the frames whose off-screen beat
    the rewind stops, `blocking` the turns that refuse it, `held` the newest
    commit the checkpoint holds and `reason` the sentence that refuses.
    `running_frames` as `agents.runtime.running_frames` gives them. Pure
    reads -- asked again under the lock before anything is taken (`decide`)."""
    frame_id = turn["frame_id"]
    idx = int(turn["idx"])
    held = checkpoint_seq(chat_id, idx)
    frames = _frames(chat_id)
    running = _running(running_frames, frame_id)
    # IN FLIGHT IS THE ROW A RUN IS WRITING: its frame's newest, while it has
    # no commit. An older uncommitted row is a beat that died part-way, read
    # like any other row -- counting it made one failed beat refuse every
    # rewind for as long as its bubble lived (review of 2026-10-13).
    newest = {}
    for f in running:
        row = q("SELECT id FROM turns WHERE chat_id=? AND frame_id IS ? "
                "ORDER BY idx DESC LIMIT 1", (chat_id, f), one=True)
        if row:
            newest[f] = row["id"]
    # Only the rows that can matter are read: later in play order, landed
    # after the checkpoint, or a running frame's newest. `commit_seq > NULL`
    # is never true, so an unknown order selects nothing by it.
    where, args = ["idx>?", "commit_seq>?"], [idx, held]
    if newest:
        where.append("id IN (%s)" % ",".join("?" * len(newest)))
        args += list(newest.values())
    carried, blocking = [], []
    for row in q("SELECT * FROM turns WHERE chat_id=? AND frame_id IS NOT ? AND (%s) "
                 "ORDER BY idx" % " OR ".join(where), (chat_id, frame_id, *args)):
        row = dict(row)
        later = int(row["idx"]) > idx
        landed_after = (held is not None and row["commit_seq"] is not None
                        and int(row["commit_seq"]) > held)
        in_flight = newest.get(row["frame_id"]) == row["id"] and not _committed(row["id"])
        if not (later or landed_after or in_flight):
            continue
        (carried if _unseen_beat_of(chat_id, row, frame_id, frames) else blocking).append(row)
    # A frame's beats go back from the first one carried to its end: a turn
    # after them in that frame that is not itself an unseen beat holds them.
    for fid in {r["frame_id"] for r in carried}:
        first = min(int(r["idx"]) for r in carried if r["frame_id"] == fid)
        tail = q("SELECT id FROM turns WHERE chat_id=? AND frame_id=? AND idx>=?",
                 (chat_id, fid, first))
        ids = {r["id"] for r in carried}
        if any(t["id"] not in ids for t in tail):
            blocking.extend(r for r in carried if r["frame_id"] == fid)
            carried = [r for r in carried if r["frame_id"] != fid]
    # Stopped: the slots an OFF-SCREEN BEAT holds in a bubble of ours, its row
    # written or not yet -- never a slot a human's run holds, whose row may
    # not exist yet either (a typed line still taking its snapshot).
    stop = sorted(f for f, offscreen in running.items()
                  if offscreen and _split_from(frames.get(f), frame_id)
                  and not any(b["frame_id"] == f for b in blocking))
    return {"carried": carried, "blocking": blocking, "stop": stop, "held": held,
            "reason": ANOTHER_FRAME_ADVANCED if blocking else None}


def decide(chat_id, turn, running_frames, own_frame=False):
    """INSIDE the restore's transaction: the plan, asked where no row can
    change, and the refusal of a rewind any live run is in the way of.

    `running_frames` is read here, under the lock; every run claims its slot
    BEFORE it writes its row, so a run missing from it writes nothing until
    the restore has landed, and then on the restored world. A run in it --
    a beat the stop did not reach in time, a line sent in another frame
    while the rewind waited -- refuses the rewind, with nothing written:
    restoring under it would run it across the restore. `own_frame` is true
    for a recompute, whose own run holds the turn's frame; a delete holds no
    slot, so a run in the page's own frame refuses it too. Blocking rows are
    returned for the caller to judge: the routes refuse them at the gate."""
    plan = rewind_plan(chat_id, turn, running_frames)
    live = [f for f in (running_frames or {})
            if not (own_frame and f == turn["frame_id"])]
    if live:
        frames = _frames(chat_id)
        named = ", ".join(sorted({(frames.get(f) or {}).get("label") or ""
                                  for f in live} - {""})) or "another thread"
        raise RewindRefused(
            f"A run is still live in this story ({named}); nothing was rewound -- try again in a moment.")
    return plan


def take_back(chat_id, carried, restored_idx, held=None):
    """Delete the carried turns -- variants, steps, memories, events, rows --
    and clear the numbers of every commit the restored checkpoint does not
    hold. Called INSIDE the restore's own transaction, with rows read in that
    same transaction (`decide`), so a restore that fails keeps them, rows and
    world roll back together, and a row is never taken back by an id another
    turn has been given since (SQLite hands the highest id out again). A row
    of another chat is never touched."""
    from mind.memory import delete_turn_memories
    for row in carried or ():
        turn_id = row["id"] if isinstance(row, dict) else row
        if not q("SELECT 1 FROM turns WHERE id=? AND chat_id=?", (turn_id, chat_id), one=True):
            continue
        for step in q("SELECT id FROM steps WHERE turn_id=?", (turn_id,)):
            qi("DELETE FROM variants WHERE step_id=?", (step["id"],))
        qi("DELETE FROM steps WHERE turn_id=?", (turn_id,))
        # as `turn_del` does for its own turn: a snapshot that carries no
        # memory bank (one written before it did) puts none back
        delete_turn_memories(turn_id)
        qi("DELETE FROM events WHERE turn_id=?", (turn_id,))
        qi("DELETE FROM turns WHERE id=? AND chat_id=?", (turn_id, chat_id))
    # EVERY COMMIT THE CHECKPOINT DOES NOT HOLD: the turns from the restored
    # one on, and a lower-numbered one that landed after it -- a direct
    # caller restores over a played beat with a warning, and the number of a
    # commit no longer in the world must not refuse the next rewind
    # (`commit_seq > NULL` is never true, so an unknown order clears by idx).
    qi("UPDATE turns SET commit_seq=NULL WHERE chat_id=? AND (idx>=? OR commit_seq>?)",
       (chat_id, restored_idx, held))


def carried_notice(plan, frames=None):
    """The stream event that says what a rewind took back, or None."""
    carried = (plan or {}).get("carried") or []
    if not carried:
        return None
    frames = frames if frames is not None else _frames(carried[0]["chat_id"])
    labels = sorted({(frames.get(r["frame_id"]) or {}).get("label") or "" for r in carried} - {""})
    return {"type": "notice", "kind": "carried", "count": len(carried), "labels": labels}
