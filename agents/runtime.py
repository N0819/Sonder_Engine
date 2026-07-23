"""Pipeline planning, execution, streaming, cancellation, resume, and reruns."""

from __future__ import annotations

import contextvars
import json
import logging
import queue
import threading

from character_schema import character_name, normalize_persona_data, persona_appearance
from checkpoints import ensure_checkpoint, restore_checkpoint
from commit import commit_all
from db import active_frame_id, q, qi, wset
from pipeline_context import ChatData, PipelineContext, TurnData
from providers import Aborted, cancel_event, generation_event_sink, token_sink
from scene import (
    NON_AWAKE_GATED,
    active_cast,
    awareness_map,
    awareness_of,
    dialogue_config,
    get_scene,
)

from .background import background_react
from .character import character_step
from .common import _assert_plan_materialized, _dict
from .director import director_establish, director_interpret, director_resolve
from .loops import interaction_loop, reaction_loop
from .mapping import mapping_quick, mapping_stage
from .narration import narrator, narrator_extra
from .perception import perception_act, perception_establish, perception_outcome
from .storage import (
    active_content, clear_steps_stale, mark_steps_stale, save_step,
    step_is_stale, variant_count,
)

def _load_extra_players(chat_id, turn_idx, frame_id=None):
    """Additional human players attached to this chat AND stationed in
    this same frame, paired with whatever they've already declared for
    this specific turn index (via POST
    /api/chats/{cid}/turns/{idx}/player_input) -- submitted ahead of the
    primary player's request, which is what makes same-beat resolution
    possible: whichever request actually creates the turn row picks up
    everything already declared for that index.

    A persona stationed in a DIFFERENT frame is excluded entirely -- they
    are not in this scene; they're eras away, playing their own thread.
    Same-frame co-op (everyone stationed together, including the common
    case of everyone at the implicit present) is the degenerate case that
    reduces to exactly today's behavior.

    Every attached, same-frame, active persona is included even with no
    submission this beat ("input": "") -- an idle connected player still
    needs their own perceiver and their own narrator_extra render of what
    just happened around them (the scene, other players'/NPCs' visible
    actions, time passing), even though they personally declared nothing.
    Silently dropping idle players would mean anyone not acting every
    single beat gets no rendered update at all while someone else keeps
    ticking turns.
    """
    rows = q(
        "SELECT cp.persona_id, p.sheet, tpi.input FROM chat_personas cp "
        "JOIN personas p ON p.id=cp.persona_id "
        "LEFT JOIN turn_player_inputs tpi "
        "  ON tpi.chat_id=cp.chat_id AND tpi.persona_id=cp.persona_id AND tpi.turn_idx=? "
        "WHERE cp.chat_id=? AND cp.status='active' AND cp.frame_id IS ?",
        (turn_idx, chat_id, frame_id),
    )
    extras = []
    for row in rows:
        sheet = normalize_persona_data(json.loads(row["sheet"]))
        extras.append({
            "persona_id": row["persona_id"],
            "name": sheet.get("identity", {}).get("name") or "Player",
            "pronouns": sheet.get("identity", {}).get("pronouns", {}),
            "appearance": persona_appearance(sheet),
            "idle": not bool(row["input"]),
            "input": row["input"] or "",
        })
    return extras

# Keyed by (chat_id, frame_id) -- NOT chat_id alone -- so two frames of
# the same chat can each have their own live pipeline running truly
# concurrently without falsely blocking each other, while a second
# attempt within the SAME frame is still correctly rejected. frame_id
# None means the present frame, exactly like everywhere else in this
# feature; a frameless chat's key is just (chat_id, None), identical in
# effect to the old chat_id-only key it replaces.
ABORTS = {}

# Guards the check-then-register step in begin_pipeline. Without this,
# two near-simultaneous requests for the SAME (chat_id, frame_id) could
# both observe the slot as free (app.py's own _require_frame_idle/
# _require_chat_idle checks happen even earlier, with no lock at all)
# and both call begin_pipeline, with the second's Event silently
# clobbering the first's in ABORTS -- leaving the first pipeline
# unabortable and letting two pipelines run against the same frame at
# once, exactly the thing this whole keying scheme exists to prevent.
_ABORTS_LOCK = threading.Lock()


class PipelineBusyError(RuntimeError):
    """Raised by begin_pipeline when (chat_id, frame_id) already has a
    live pipeline registered. Callers (app.py's turn/step endpoints)
    must catch this and translate it to a 409 -- it means a concurrent
    request won the race, not that this request did anything wrong."""

_step_logger = logging.getLogger("fiction_engine.pipeline")

class StaleStepError(RuntimeError):
    """Raised when a rerun/resume would build on top of a step whose
    stale flag is still set -- i.e. content left over from an earlier,
    now-superseded run rather than something actually consistent with
    what's about to be (re)computed. Refusing here, instead of silently
    consuming the stale content and then clearing the flag at the end
    (which erased the evidence anything was ever inconsistent), is the
    fix: surface it as an error the caller must resolve, not paper over.
    """

def request_abort(chat_id, frame_id=None):
    ev = ABORTS.get((chat_id, frame_id))
    if ev:
        ev.set()
        return True
    return False

def begin_pipeline(chat_id, frame_id=None):
    """Register this (chat, frame) as having an active pipeline
    SYNCHRONOUSLY, before any streaming response is constructed or
    returned.

    run_pipeline is a generator function -- calling it executes none of
    its body (including the old `ABORTS[key] = abort` line) until the
    caller first iterates it, which for a StreamingResponse can be
    arbitrarily delayed past the point the HTTP handler already returned
    200. That left a real window where a second request's idle check
    would see the key missing from ABORTS and proceed, even though a
    pipeline for that (chat, frame) was already committed to starting.
    Callers (app.py's turn/step endpoints) must call this themselves, in
    the handler body, before constructing the streaming response, and
    pass the returned event into run_pipeline(..., abort=).

    The check-then-register is done under _ABORTS_LOCK, atomically --
    raises PipelineBusyError instead of overwriting an existing entry if
    a concurrent request already claimed this exact (chat_id, frame_id)
    since the caller's own idle check ran.
    """
    with _ABORTS_LOCK:
        if (chat_id, frame_id) in ABORTS:
            raise PipelineBusyError(
                f"a pipeline is already running for chat {chat_id} frame {frame_id}"
            )
        abort = threading.Event()
        ABORTS[(chat_id, frame_id)] = abort
        return abort

STEP_HANDLERS = {
    "interaction_loop": interaction_loop,
    "reaction_loop": reaction_loop,
    "director_establish": director_establish,
    "director_interpret": director_interpret,
    "mapping_stage": mapping_stage,
    "mapping_quick": mapping_quick,
    "perception_establish": perception_establish,
    "perception_act": perception_act,
    "director_resolve": director_resolve,
    "background_react": background_react,
    "perception_outcome": perception_outcome,
    "narrator": narrator,
    "narrator_extra": narrator_extra,
    "commit": commit_all,
}


def register_step(key, handler, *, replace=False):
    """Register a fixed pipeline step without editing dispatch logic.

    Dynamic ``character:<id>`` steps remain owned by ``character_step``.
    Plan construction is deliberately separate: callers must still add a new
    key to ``build_plan`` or ``establishment_plan`` at the intended position.
    """
    if not isinstance(key, str) or not key.strip():
        raise ValueError("step key must be a non-empty string")
    if key.startswith("character:"):
        raise ValueError("character:<id> is a reserved dynamic step namespace")
    if not callable(handler):
        raise TypeError("step handler must be callable")
    if key in STEP_HANDLERS and not replace:
        raise ValueError(f"step {key!r} is already registered")
    STEP_HANDLERS[key] = handler


def compute_step(key, ctx, nonce):
    if key.startswith("character:"):
        return character_step(ctx, int(key.split(":", 1)[1]), nonce)

    handler = STEP_HANDLERS.get(key)
    if handler is None:
        raise RuntimeError("unknown step " + key)
    return handler(ctx, nonce)

class Bus:
    def __init__(self):
        self.q = queue.Queue()

def _stream_one(bus, key, fn, holder):
    def work():
        token_sink.set(
            lambda delta: bus.q.put({
                "type": "token",
                "key": key,
                "delta": delta,
            })
        )

        generation_event_sink.set(
            lambda event: bus.q.put({
                **event,
                "key": key,
            })
        )

        try:
            holder["v"] = fn()
        except Exception as exc:
            _step_logger.exception(
                "Pipeline step '%s' failed",
                key,
            )
            holder["e"] = exc
        finally:
            bus.q.put({
                "type": "__done__",
                "key": key,
            })

    context = contextvars.copy_context()
    thread = threading.Thread(
        target=lambda: context.run(work)
    )
    thread.start()

    while True:
        event = bus.q.get()

        if (
            event.get("type") == "__done__"
            and event["key"] == key
        ):
            thread.join()
            return

        yield event

def _stream_parallel(bus, jobs, holders):
    remaining = set(k for k, _ in jobs)
    def work(k, fn):
        token_sink.set(
            lambda delta, key=k: bus.q.put({
                "type": "token",
                "key": key,
                "delta": delta,
            })
        )

        generation_event_sink.set(
            lambda event, key=k: bus.q.put({
                **event,
                "key": key,
            })
        )

        try:
            holders[k] = {"v": fn()}
        except Exception as exc:
            _step_logger.exception(
                "Pipeline step '%s' failed",
                k,
            )
            holders[k] = {"e": exc}
        finally:
            bus.q.put({
                "type": "__done__",
                "key": k,
            })
    ths = []
    for k, f in jobs:
        cv = contextvars.copy_context()
        ths.append(threading.Thread(target=lambda cv=cv, k=k, f=f: cv.run(lambda: work(k, f))))
    for t in ths:
        t.start()
    while remaining:
        ev = bus.q.get()
        if ev.get("type") == "__done__":
            remaining.discard(ev["key"])
            continue
        yield ev
    for t in ths:
        t.join()

def _evt(key, label, sid, vid, n, content):
    return {"type": "step", "key": key, "label": label,
            "step_id": sid, "variant_id": vid, "variants": n, "content": content}

def _step_stream(bus, turn_id, key, label, ordn, ctx, nonce):
    yield {"type": "step_start", "key": key, "label": label}
    holder = {}
    yield from _stream_one(bus, key, lambda: compute_step(key, ctx, nonce), holder)
    if "e" in holder:
        raise holder["e"]
    ctx[key] = holder["v"]
    sid, vid, n = save_step(turn_id, key, label, ordn, holder["v"])
    yield _evt(key, label, sid, vid, n, holder["v"])

def resume_key_for_turn(turn_id, chat_id):
    """Find the first missing or stale step in a turn's plan."""
    turn = q(
        "SELECT * FROM turns WHERE id=? AND chat_id=?",
        (turn_id, chat_id),
        one=True,
    )
    if not turn:
        return "director_interpret"

    if turn["idx"] == 0:
        plan = establishment_plan()
    else:
        interpretation = active_content(turn_id, "director_interpret")
        if not isinstance(interpretation, dict):
            return "director_interpret"
        plan = build_plan(
            interpretation,
            active_cast(chat_id, turn["frame_id"]),
            chat_id=chat_id,
            frame_id=turn["frame_id"],
        )

    rows = q(
        """
        SELECT s.key, s.stale,
               SUM(CASE WHEN v.active=1 THEN 1 ELSE 0 END)
                   AS active_count
        FROM steps s
        LEFT JOIN variants v ON v.step_id=s.id
        WHERE s.turn_id=?
        GROUP BY s.id, s.key, s.stale
        """,
        (turn_id,),
    )

    status = {
        row["key"]: {
            "stale": bool(row["stale"]),
            "active_count": int(row["active_count"] or 0),
        }
        for row in rows
    }

    for key, _label in plan:
        current = status.get(key)
        if current is None:
            return key
        if current["stale"]:
            return key
        if current["active_count"] != 1:
            return key

    return None

def build_plan(interp, cast_rows, chat_id=None, frame_id=None):
    if not isinstance(interp, dict):
        interp = {}
        
    plan = [("director_interpret", "Director · interpret & flow plan")]
    fl = interp.get("flow")
    if not isinstance(fl, dict):
        fl = {}
        
    if fl.get("needs_mapping"):
        plan.append(("mapping_stage", "Mapping · route books & lore"))
    else:
        plan.append(("mapping_quick", "Mapping · cached recall"))
    plan.append(("perception_act", "Perception · pass 1 — the act"))

    valid_ids = {int(row["id"]) for row in cast_rows}
    reactors = [int(char_id) for char_id in (fl.get("reactors") or [])
                if int(char_id) in valid_ids]

    # Consciousness gate: an unconscious/asleep/sedated mind neither perceives
    # nor deliberates, so drop it from the reactor set before any character
    # step is planned (perception excludes it too -- defense-in-depth). Awake by
    # absence (fail-open); waking is a Director state transition, so a roused
    # character acts on the NEXT beat, matching the onset/outcome separation.
    if chat_id is not None and reactors:
        amap = awareness_map(chat_id)
        _names_by_id = {int(row["id"]): character_name(json.loads(row["sheet"]))
                        for row in cast_rows}
        reactors = [cid for cid in reactors
                    if awareness_of(amap, _names_by_id.get(cid, "")) not in NON_AWAKE_GATED]

    autonomy = 0
    if chat_id is not None:
        autonomy = int(dialogue_config(chat_id).get("autonomy", 50))

    # Add reaction loop if contested
    flags = _dict(fl.get("resolution_flags"))
    contested = bool(flags.get("contested") and reactors)
    if contested:
        plan.append(("reaction_loop", "Characters · physical reactions"))

    if reactors:
        if autonomy > 0:
            plan.append(("interaction_loop", "Characters · interaction loop"))
        elif not contested:
            names = {row["id"]: character_name(json.loads(row["sheet"])) for row in cast_rows}
            for char_id in reactors:
                plan.append((f"character:{char_id}", f"Character · {names[char_id]}"))
        # Contested at autonomy == 0: reaction_loop above already gives every
        # reactor its single character_step declaration for this beat, and
        # director_resolve consumes those via ctx.reaction_loop. Appending the
        # parallel character:<id> steps as well ran every reactor's
        # character_step TWICE (the interaction_loop path dedups via
        # already_reacted; the parallel path had no equivalent), and the
        # second, full-turn declaration was then silently dropped from
        # dialogue_log while perception_outcome still injected its actions.

    plan += [
        ("director_resolve", "Director · resolve"),
        # Unconditional but self-gating: pick_background_reactor (commit.py)
        # is a cheap, LLM-free check that returns None for the large
        # majority of turns (no salient, un-voiced background presence this
        # beat) -- only then does background_react spend an LLM call.
        ("background_react", "Background · presence reaction"),
        ("perception_outcome", "Perception · pass 2 — the outcome"),
        ("narrator", "Narrator · render"),
    ]
    if chat_id is not None and _chat_has_extra_players(chat_id, frame_id):
        plan.append(("narrator_extra", "Narrator · render (other players)"))
    plan.append(("commit", "Mapping & memory · commit-up"))
    return plan

def _mapping_must_precede_perception(ctx):
    """Return True when perception needs freshly staged spatial lore.

    Full mapping is usually independent and worth overlapping with the
    perception LLM.  A newly entered or explicitly queried location is the
    exception: perception's room-notes fallback reads mapping_stage output,
    so running both concurrently would make the first view of that room lose
    its freshly generated sensory description.
    """
    interp = ctx.get("director_interpret") or {}
    if interp.get("location_query"):
        return True
    movement = interp.get("movement")
    target = movement.get("to_room") if isinstance(movement, dict) else None
    if target:
        scene = get_scene(ctx.chat.id, ctx.chat)
        if target not in (scene.get("rooms") or {}):
            return True
    request = str((interp.get("flow") or {}).get("mapping_request") or "").casefold()
    return any(
        phrase in request
        for phrase in ("new room", "generate room", "scene graph", "new location")
    )


def _chat_has_extra_players(chat_id, frame_id=None):
    # Same-frame filter as _load_extra_players: a co-player stationed in a
    # DIFFERENT frame is not in this scene, so their presence must not add
    # a spurious narrator_extra step to this frame's plan (the step would
    # then render for zero perceivers).
    return bool(q(
        "SELECT 1 FROM chat_personas WHERE chat_id=? AND status='active' "
        "AND frame_id IS ? LIMIT 1",
        (chat_id, frame_id), one=True,
    ))

def establishment_plan():
    return [
        ("mapping_stage", "Mapping · route books & lore"),
        ("director_establish", "Director · establish scene"),
        ("perception_establish", "Perception · opening player view"),
        ("narrator", "Narrator · opening"),
        ("commit", "Mapping & memory · commit-up"),
    ]

def _rehydrate_loop_results(ctx, key, content):
    """Rebuild the per-character result maps a loop step populated in the
    uninterrupted run but that plain `ctx[key] = content` hydration does NOT
    reconstruct on resume/reroll (audit #11).

    `commit.py` and `agents/perception.py` read `ctx.character_results` /
    `ctx.reaction_results` directly. When a resumed or reroll-commit turn only
    loads the persisted interaction_loop/reaction_loop CONTENT into
    `ctx.interaction_loop` / `ctx.reaction_loop`, those maps stay empty, so the
    turn silently commits no character self-memories, mind_model_updates,
    stance_updates, or active_state. Rebuild each loop's native map from its
    persisted `character_results`/`reaction_results` dict, falling back to the
    per-round `result` payloads, so resume reproduces the uninterrupted run.
    """
    if not isinstance(content, dict):
        return
    if key == "interaction_loop":
        target, results_field, id_field = ctx.character_results, "character_results", "speaker_id"
    elif key == "reaction_loop":
        target, results_field, id_field = ctx.reaction_results, "reaction_results", "reactor_id"
    else:
        return
    results = content.get(results_field)
    if isinstance(results, dict):
        for cid_str, result in results.items():
            try:
                cid = int(cid_str)
            except (TypeError, ValueError):
                continue
            if isinstance(result, dict):
                target.setdefault(cid, result)
    for round_data in content.get("rounds") or []:
        if not isinstance(round_data, dict):
            continue
        result = round_data.get("result")
        try:
            cid = int(round_data.get(id_field))
        except (TypeError, ValueError):
            continue
        if isinstance(result, dict):
            target.setdefault(cid, result)

def _run_pipeline(chat_id, turn_id, from_key=None, only_key=None):
    bus = Bus()
    chat_row = dict(q("SELECT * FROM chats WHERE id=?", (chat_id,), one=True))
    turn_row = dict(q("SELECT * FROM turns WHERE id=?", (turn_id,), one=True))
    ensure_checkpoint(chat_id, turn_row["idx"])
    cast_rows = active_cast(chat_id, turn_row["frame_id"])

    # Every pipeline run executes IN one frame -- from the turn row's own
    # frame_id, never from ambient world-KV state, since two frames can
    # now have pipelines running truly concurrently. Reset happens in
    # run_pipeline's finally block, matching providers.py's cancel_event/
    # token_sink contextvar discipline exactly (see db.py's comment on
    # active_frame_id for why that reset is load-bearing, not optional).
    active_frame_id.set(turn_row["frame_id"])

    ctx = PipelineContext(
        chat=ChatData.from_row(chat_row),
        turn=TurnData.from_row(turn_row),
        cast=cast_rows,
        input=turn_row["player_input"],
        extra_players=_load_extra_players(chat_id, turn_row["idx"], turn_row["frame_id"]),
    )

    establishment = (turn_row["idx"] == 0)

    # A checkpoint is a snapshot of the WHOLE chat's world table (every
    # frame's rows) at one moment in play order. Restoring it wipes and
    # replaces ALL of them -- correct and necessary for recompute (this
    # turn's downstream state may have genuinely drifted), but for a
    # turn that has never run before there is nothing to restore, and
    # under concurrency the old "run it unconditionally, it's a harmless
    # no-op" reasoning no longer holds: a DIFFERENT frame's pipeline may
    # have committed newer state since this checkpoint was taken, and an
    # unconditional restore would silently roll that back. Skipping it
    # for genuinely fresh turns is a correctness fix, not an optimization.
    has_existing_steps = bool(q("SELECT 1 FROM steps WHERE turn_id=? LIMIT 1", (turn_id,), one=True))

    if only_key:
        for s in q("SELECT * FROM steps WHERE turn_id=? ORDER BY ord", (turn_id,)):
            c = active_content(turn_id, s["key"])
            if c is not None:
                ctx[s["key"]] = c
                _rehydrate_loop_results(ctx, s["key"], c)
        s = q("SELECT * FROM steps WHERE turn_id=? AND key=?", (turn_id, only_key), one=True)
        if not s:
            raise RuntimeError(f"step '{only_key}' not found on this turn")
        # Same stale-upstream refusal the from_key paths make: a reroll of
        # this single step would otherwise silently consume hydrated content
        # from an earlier step that is still flagged stale (left over from an
        # interrupted/superseded run), then save a fresh-looking variant on
        # top of it. Checked before the commit-checkpoint restore below so a
        # refused reroll has no side effects at all.
        stale_upstream = q(
            "SELECT key FROM steps WHERE turn_id=? AND ord<? AND stale=1 "
            "ORDER BY ord LIMIT 1",
            (turn_id, s["ord"]), one=True,
        )
        if stale_upstream:
            raise StaleStepError(
                f"step '{stale_upstream['key']}' is stale and must be resumed "
                f"or rerun before rerolling '{only_key}'"
            )
        if only_key == "commit" and has_existing_steps:
            restore_checkpoint(chat_id, turn_row["idx"])
        elif (
            only_key != "commit"
            and has_existing_steps
            and active_content(turn_id, "commit") is not None
        ):
            # Single-step reroll of a PRE-commit stage on a turn that already
            # committed. The live world tables + this turn's own committed
            # memories now reflect the OUTCOME, so re-running onset perception
            # or a character decision against that state leaks outcome
            # knowledge into the onset declaration (audit #10). Restore the
            # pre-turn checkpoint first -- mirroring the from_key rerun path
            # below -- so the rerolled onset stage sees only pre-turn state.
            # Downstream steps (commit included) are marked stale just below,
            # leaving the turn in an explicit needs-resume state rather than a
            # half-committed one.
            restore_checkpoint(chat_id, turn_row["idx"])
        # Marked stale BEFORE computing (not after) so a crash/abort mid-step
        # leaves accurate breadcrumbs instead of the pre-existing downstream
        # content silently continuing to look fresh.
        qi("UPDATE steps SET stale=1 WHERE turn_id=? AND ord>?", (turn_id, s["ord"]))
        yield from _step_stream(bus, turn_id, only_key, s["label"], s["ord"],
                                ctx, variant_count(turn_id, only_key))
        yield {"type": "done", "turn_id": turn_id}
        return

    if has_existing_steps:
        restore_checkpoint(chat_id, turn_row["idx"])

    if establishment:
        plan = establishment_plan()
        keys = [key for key, _ in plan]

        if from_key is None:
            start_i = 0
        elif from_key in keys:
            start_i = keys.index(from_key)
        else:
            raise RuntimeError(
                f"step '{from_key}' is not in the "
                "establishment plan"
            )

        for step in q(
            "SELECT * FROM steps WHERE turn_id=?",
            (turn_id,),
        ):
            if step["key"] in keys:
                continue

            if variant_count(turn_id, step["key"]) > 1:
                # More than one variant means this step was rerolled or
                # manually edited at least once -- a fresh plan no longer
                # wanting this key (e.g. a cast/flow change) is not a
                # reason to destroy that history. Leave it orphaned: it
                # simply won't be referenced by this turn's plan going
                # forward, but it's still visible via the pipeline drawer.
                continue

            qi(
                "DELETE FROM variants WHERE step_id=?",
                (step["id"],),
            )
            qi(
                "DELETE FROM steps WHERE id=?",
                (step["id"],),
            )

        mark_steps_stale(turn_id, keys[start_i:])

        for index, (key, label) in enumerate(plan):
            if index < start_i:
                content = active_content(turn_id, key)

                if content is None:
                    start_i = index
                elif step_is_stale(turn_id, key):
                    raise StaleStepError(
                        f"step '{key}' is stale and must be resumed or "
                        "rerun before continuing from a later stage"
                    )
                else:
                    ctx[key] = content
                    continue

            yield from _step_stream(
                bus,
                turn_id,
                key,
                label,
                index,
                ctx,
                variant_count(turn_id, key),
            )

        _assert_plan_materialized(
            turn_id,
            plan,
            ctx,
        )

        clear_steps_stale(turn_id, keys)

        yield {
            "type": "done",
            "turn_id": turn_id,
        }
        return

    start_key = None
    if from_key not in (None, "director_interpret"):
        if step_is_stale(turn_id, "director_interpret"):
            raise StaleStepError(
                "step 'director_interpret' is stale and must be resumed "
                "or rerun before continuing from a later stage"
            )
        interp = active_content(turn_id, "director_interpret")
        if isinstance(interp, dict):
            ctx["director_interpret"] = interp
            start_key = from_key
        # A MISSING (absent, or no active variant) director_interpret means
        # there is nothing valid to build the plan or any later stage on --
        # restart from director_interpret (mirroring resume_key_for_turn)
        # instead of substituting {} and failing the materialization assert
        # only after everything, commit included, has already run.

    if start_key is None:
        yield from _step_stream(bus, turn_id, "director_interpret",
            "Director · interpret & flow plan", 0, ctx,
            variant_count(turn_id, "director_interpret"))

    plan = build_plan(ctx["director_interpret"], cast_rows, chat_id=chat_id,
                      frame_id=turn_row["frame_id"])
    keys = [k for k, _ in plan]
    if start_key is not None and start_key not in keys:
        # Refuse before deleting orphans or marking anything stale -- an
        # unknown from_key must surface as an error the caller resolves,
        # exactly like the establishment branch, not silently degrade into
        # a full recompute of the whole turn.
        raise RuntimeError(
            f"step '{from_key}' is not in this turn's plan"
        )
    for s in q("SELECT * FROM steps WHERE turn_id=?", (turn_id,)):
        if s["key"] in keys:
            continue
        if variant_count(turn_id, s["key"]) > 1:
            # Rerolled or manually edited at least once -- see the matching
            # comment in the establishment branch above. Preserve, don't delete.
            continue
        qi("DELETE FROM variants WHERE step_id=?", (s["id"],))
        qi("DELETE FROM steps WHERE id=?", (s["id"],))

    start_i = keys.index(start_key) if (start_key in keys) else 1
    mark_steps_stale(turn_id, keys[start_i:])
    i = 1
    while i < len(plan):
        key, label = plan[i]
        if i < start_i:
            c = active_content(turn_id, key)
            if c is None:
                start_i = i
                continue
            if step_is_stale(turn_id, key):
                raise StaleStepError(
                    f"step '{key}' is stale and must be resumed or "
                    "rerun before continuing from a later stage"
                )
            ctx[key] = c
            _rehydrate_loop_results(ctx, key, c)
            i += 1
            continue
        if key.startswith("character:"):
            group = []
            j = i
            while j < len(plan) and plan[j][0].startswith("character:"):
                group.append(plan[j])
                j += 1
            for k, lbl in group:
                yield {"type": "step_start", "key": k, "label": lbl}
            holders = {}
            jobs = [(k, (lambda kk=k: compute_step(kk, ctx, variant_count(turn_id, kk))))
                    for k, _ in group]
            yield from _stream_parallel(bus, jobs, holders)
            for k, lbl in group:
                h = holders[k]
                if "e" in h:
                    raise h["e"]
                ctx[k] = h["v"]
                sid, vid, n = save_step(turn_id, k, lbl, keys.index(k), h["v"])
                yield _evt(k, lbl, sid, vid, n, h["v"])
            i = j
            continue
        if (
            key == "mapping_stage"
            and i + 1 < len(plan)
            and plan[i + 1][0] == "perception_act"
            and not _mapping_must_precede_perception(ctx)
        ):
            # Existing-world lore routing and action-onset perception are
            # independent, so overlap their provider latency.  Spatially novel
            # turns are excluded by _mapping_must_precede_perception: on those
            # turns perception genuinely consumes the freshly staged room lore
            # and must run second for first-turn sensory fidelity.
            pair = [(key, label), plan[i + 1]]
            for k, lbl in pair:
                yield {"type": "step_start", "key": k, "label": lbl}
            holders = {}
            jobs = [(k, (lambda kk=k: compute_step(kk, ctx, variant_count(turn_id, kk))))
                    for k, _ in pair]
            yield from _stream_parallel(bus, jobs, holders)
            for k, lbl in pair:
                h = holders[k]
                if "e" in h:
                    raise h["e"]
                ctx[k] = h["v"]
                sid, vid, n = save_step(turn_id, k, lbl, keys.index(k), h["v"])
                yield _evt(k, lbl, sid, vid, n, h["v"])
            i += 2
            continue
        if (
            key == "narrator"
            and i + 1 < len(plan)
            and plan[i + 1][0] == "narrator_extra"
        ):
            # narrator (the primary player's render) and narrator_extra
            # (one render per additional simultaneous player) both depend
            # only on already-completed director_interpret/perception_*
            # output, plus each other's PRIOR-turn rows for rhythm context
            # -- never the current turn's sibling. Confirmed via direct
            # grep: narration.py never reads ctx.narrator from within
            # narrator_extra, or vice versa. Same independent-work pattern
            # as the mapping/perception_act pairing above.
            pair = [(key, label), plan[i + 1]]
            for k, lbl in pair:
                yield {"type": "step_start", "key": k, "label": lbl}
            holders = {}
            jobs = [(k, (lambda kk=k: compute_step(kk, ctx, variant_count(turn_id, kk))))
                    for k, _ in pair]
            yield from _stream_parallel(bus, jobs, holders)
            for k, lbl in pair:
                h = holders[k]
                if "e" in h:
                    raise h["e"]
                ctx[k] = h["v"]
                sid, vid, n = save_step(turn_id, k, lbl, keys.index(k), h["v"])
                yield _evt(k, lbl, sid, vid, n, h["v"])
            i += 2
            continue
        yield from _step_stream(bus, turn_id, key, label, i, ctx,
                                variant_count(turn_id, key))
        i += 1

    _assert_plan_materialized(turn_id, plan, ctx)
    clear_steps_stale(turn_id, keys)
    yield {"type": "done", "turn_id": turn_id}

def run_pipeline(
    chat_id,
    turn_id,
    from_key=None,
    only_key=None,
    abort=None,
    frame_id=None,
):
    # Callers that already registered via begin_pipeline() pass that same
    # event through here so there's exactly one abort Event for this run,
    # visible in ABORTS from before the streaming response was returned.
    # Falling back to registering it here keeps direct/test callers working.
    # frame_id here is only for the ABORTS key -- the authoritative source
    # for active_frame_id itself is the turn row, set inside _run_pipeline.
    if abort is None:
        abort = begin_pipeline(chat_id, frame_id)
    else:
        ABORTS[(chat_id, frame_id)] = abort
    cancel_event.set(abort)

    try:
        # Do not stop consuming _run_pipeline merely because the flag has
        # been set. The worker must observe cancellation, publish its done
        # marker, and be joined by the streaming wrapper.
        for event in _run_pipeline(
            chat_id,
            turn_id,
            from_key,
            only_key,
        ):
            yield event

    except Aborted:
        yield {
            "type": "aborted",
            "turn_id": turn_id,
        }

    except Exception:
        try:
            wset(chat_id, "pending", [])
        except Exception:
            pass
        raise

    finally:
        cancel_event.set(None)
        active_frame_id.set(None)

        if ABORTS.get((chat_id, frame_id)) is abort:
            ABORTS.pop((chat_id, frame_id), None)
