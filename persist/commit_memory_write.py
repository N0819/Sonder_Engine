"""The durable memory write (commit_memories) and its out-of-band
consolidation twin.

Extracted verbatim from commit.py, which re-exports every name here.
See docs/experiments/AUDIT_COMMIT.md for the split record.
"""

import contextvars
from concurrent.futures import ThreadPoolExecutor
from core.db import qi, transaction, wget, wset
from mind.memory import (add_memories_batch, delete_turn_memories,
                    record_dispute, raise_importance,
                    apply_relationship_updates,
                    update_relationships_from_inference,
                    maybe_consolidate_character_memory,
                    reconcile_inference_confidence)
from story.character_schema import character_name_from_text
from story.scene import set_char_state
from persist.commit_memory import prepare_memory_commit

def _consolidate_committed_memories(ctx):
    """Update derived autobiographical summaries after the atomic commit.

    Summaries are reconstructible caches, not primary turn facts.  Keeping
    their LLM calls outside the transaction avoids deadlocks and ensures a
    consolidation failure can never roll back an otherwise valid turn.

    This is the DIRECT, blocking form -- commit_memories' standalone path
    and tests use it. The live turn pipeline no longer does: consolidation
    is a background summarisation job, and running it on the `utility` role
    inside the player's wait was measured at 29.5s of a 45.8s commit stage
    (chat 71 turn 10, the first beat to reach the consolidation cadence).
    `schedule_memory_consolidation` below is the out-of-band twin the commit
    tail actually calls.
    """
    cid = ctx.chat.id
    turn = ctx.turn
    notes = []

    def _consolidate_one(char_row):
        try:
            result = maybe_consolidate_character_memory(
                cid, char_row["id"], turn.idx, frame_id=turn.frame_id,
            )
            if result:
                return (
                    f"{character_name_from_text(char_row['sheet'])}: "
                    "autobiographical summary updated"
                )
        except Exception as exc:
            ctx.add_warning(
                f"Memory consolidation failed for character {char_row['id']}: {exc}"
            )
        return None

    if ctx.cast:
        # A bare pool worker starts from an EMPTY context, so the story
        # language was lost and `memory_consolidate` resolved to English --
        # writing English autobiography into a Japanese story's memory bank.
        # `agents/narration.py` and `agents/director.py` copy the context for
        # exactly this reason; this pool was missed.
        parent = contextvars.copy_context()

        def _consolidate_in_context(char_row):
            return parent.run(_consolidate_one, char_row)

        with ThreadPoolExecutor(max_workers=len(ctx.cast)) as pool:
            for note in pool.map(_consolidate_in_context, ctx.cast):
                if note:
                    notes.append(note)
    return notes


MEMORY_CONSOLIDATION_JOB_KEY = "memory_consolidation"


def schedule_memory_consolidation(ctx):
    """Queue this turn's autobiographical consolidation out of band.

    Returns the Job, or None when there is no cast or one is already in
    flight for this chat. Called from the commit tail AFTER the turn's
    facts are durable, on the same terms as the offscreen ticks beside it:
    a summary is a reconstructible cache derived from committed rows, so
    nothing about correctness changes -- only who waits for it. Measured
    cost of waiting: the first consolidation of a live chat took 29.5s
    (27.4s of it one `utility`-role LLM call) inside the commit stage's
    wall clock.

    The job snapshots the scalars it needs (ids, names, turn, frame) so it
    never touches ctx after the turn returns. Sequential per character with
    a cancellation check between -- abandonable at every unit boundary --
    and a failure for one character is logged and skipped, never raised:
    background work cannot break a turn, and the cadence check re-offers
    the window on a later beat. Deduped on the chat by jobs.submit: a
    consolidation still running when the next beat commits simply keeps
    running, and that beat schedules nothing (maybe_consolidate re-reads
    the cursor, so nothing is lost -- only deferred). Checkpoint restore
    cancels the in-flight job cooperatively (see checkpoints.py) so a
    rolled-back turn does not land a summary computed from rows that no
    longer exist; the residual window -- a restore arriving mid-LLM-call --
    is recorded in docs/UNBUILT.md.
    """
    from core import jobs

    cid = ctx.chat.id
    turn_idx = ctx.turn.idx
    frame_id = ctx.turn.frame_id
    members = [
        {"id": row["id"],
         "name": character_name_from_text(row["sheet"])}
        for row in (ctx.cast or [])
    ]
    if not members:
        return None

    def _produce(job):
        # Fresh thread, fresh contextvars: pin the scheduling turn's frame
        # for every frame-scoped read/write below (the offscreen tick
        # producers set the precedent, and the reason -- a nested frame's
        # consolidation landing in the present frame -- is the same).
        from core.db import active_frame_id
        from core.logging_utils import logger
        token = active_frame_id.set(frame_id)
        try:
            notes = []
            for member in members:
                if job.cancelled.is_set():
                    break
                try:
                    result = maybe_consolidate_character_memory(
                        cid, member["id"], turn_idx, frame_id=frame_id,
                    )
                    if result:
                        notes.append(f"{member['name']}: autobiographical "
                                     "summary updated")
                except Exception as exc:
                    # Silence toward the turn, a trace toward the operator:
                    # the cadence re-offers this window next beat.
                    logger.info(
                        "memory consolidation failed out of band: chat=%s "
                        "char=%s error=%s", cid, member["id"],
                        str(exc)[:300])
            return notes
        finally:
            active_frame_id.reset(token)

    return jobs.submit(cid, MEMORY_CONSOLIDATION_JOB_KEY, _produce,
                       base_turn=turn_idx)


def commit_memories(ctx, nonce, *, prepared=None, consolidate=True):
    prepared = prepared or prepare_memory_commit(ctx)
    turn = ctx.turn
    cid = ctx.chat.id

    with transaction():
        # A name heard this beat, of somebody standing in the room. Applied
        # here rather than in prepare, which runs outside the write lock;
        # merged rather than assigned, because `validated_introductions` may
        # have written the same map earlier in this turn and an explicit
        # introduction must not be lost to an overwrite.
        _learned = prepared.get("names_learned") or {}
        if _learned:
            _known = wget(cid, "known", {}) or {}
            for _hearer, _names in _learned.items():
                _known.setdefault(_hearer, [])
                for _name in _names:
                    if _name not in _known[_hearer]:
                        _known[_hearer].append(_name)
            wset(cid, "known", _known)
        delete_turn_memories(turn.id)
        memory_ids = add_memories_batch(
            prepared_batch=prepared["memory_batch"],
        )
        for kind, char_id, updates in prepared["relationship_ops"]:
            if kind == "explicit":
                # The frame goes with it: a branch that never had the argument
                # must not inherit the reason it happened.
                apply_relationship_updates(cid, char_id, turn.idx, updates,
                                           frame_id=ctx.turn.frame_id)
            else:
                update_relationships_from_inference(
                    cid, char_id, turn.idx, updates,
                )
        for chat_id, char_id, state_json in prepared["state_updates"]:
            set_char_state(
                chat_id, char_id, state_json, frame_id=turn.frame_id,
            )
        # After the batch insert AND after the state write, so this turn's own
        # freshly-minted inference rows are re-weighted by the same reconciled
        # mind_models everything else now reads -- a claim minted at the
        # model's declared confidence and then blended/suppressed by
        # apply_mind_model_updates would otherwise sit in the bank at the
        # pre-blend number forever.
        for chat_id, char_id, char_state, clock_seconds in prepared.get(
                "belief_reconciles") or []:
            reconcile_inference_confidence(
                chat_id, char_id, char_state, turn.idx,
                elapsed_seconds=clock_seconds,
            )
        # A mind re-reading one of its own memories. Scoped to that character's
        # own rows inside record_dispute, so this can never reach across the
        # firewall however the model phrased the gist.
        for chat_id, char_id, _gist, _reading, _tidx, _ref in prepared.get(
                "memory_disputes") or []:
            try:
                record_dispute(chat_id, char_id, _gist, _reading, _tidx,
                               memory_ref=_ref)
            except Exception as exc:
                ctx.add_warning(f"memory dispute not recorded: {exc}")
        # Memories that turned out to be load-bearing for a belief. Once each,
        # ever (`only_unrevised`), which is what keeps this a consequence
        # rather than a popularity loop -- see _cited_memory_ids.
        for char_id, ids in prepared.get("importance_bumps") or []:
            try:
                raise_importance(cid, char_id, event_keys=ids,
                                 only_unrevised=True)
            except Exception as exc:
                ctx.add_warning(f"memory importance not updated: {exc}")
        qi(
            """INSERT INTO events(chat_id,turn_id,content) VALUES(?,?,?)
            ON CONFLICT(chat_id,turn_id) WHERE turn_id IS NOT NULL
            DO UPDATE SET content=excluded.content""",
            (cid, turn.id, prepared["event_content"]),
        )

    committed = [f"memory:{mid}" for mid in memory_ids]
    if consolidate:
        committed.extend(_consolidate_committed_memories(ctx))
    return {"committed": committed}
