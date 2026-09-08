"""A/B harness for the beat's scene composition (review 2026-09-07 A26/B1/C6).

WHAT IT MEASURES. For every stored turn of one chat that carries a resolve
(or an establish) step, it rebuilds that turn's `PipelineContext` out of the
persisted step variants, runs the commit-side composition
(`persist.commit_scene_state.prepare_scene_commit`) against the chat's
CURRENT stored scene, and writes down two things: the wall clock of the
composition, and a canonical-JSON digest of everything the composition
answers with (the composed scene, the post-dedup diff, the clock, the
destruction bundle, the region entries, the charter routing, the frontier
mutations, the prepared room registry, plus the warnings and the
Director-facing notes the run raised).

WHY IT EXISTS. A26 was closed by making `persist.commit_scene_state.
compose_beat_scene` the one composition perception_outcome and commit both
call. "Same answer, faster" is only a claim until the answer is diffed on real
stored beats, so: run this on a WRITABLE copy of a bench database before the
change and after it, and diff the two JSON files byte for byte.

WHAT THE BEFORE ARM DOES NOT RUN. This harness times and diffs the commit
composition alone; it never runs perception_outcome first. That is the
comparison that proved the split answer-preserving, and it is also why the
first A26 patch's proof missed the stage writing on the shared object: the
production sequence is perception THEN commit, and the A26 skeptic's harness
(perception_outcome, then prepare_scene_commit, per stored beat) is the one
that caught it. Run both arms when the seam between the two stages moves.

    cp bench.db /tmp/b114.db && chmod u+w /tmp/b114.db
    python tools/bench/scene_composition.py /tmp/b114.db 114 --out before.json
    # ...change the code, take a fresh copy of the db...
    python tools/bench/scene_composition.py /tmp/b114.db 114 --out after.json
    diff before.json after.json

THE COPY IS NOT OPTIONAL. The composition files engine notices and two
once-per-chat flags outside the turn's transaction, so it needs a database it
may write, and a second run has to start from a fresh copy to see the same
"already told" state the first one did.

`prev_scene` is the chat's current committed scene rather than the scene each
beat actually started from (no per-turn scene snapshot is stored). That is
deliberate: what this harness proves is that the SAME inputs produce the same
answer through the old and new code, and a real stored diff applied to a real
stored scene is the size of input the finding is about.
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("db")
    ap.add_argument("chat_id", type=int)
    ap.add_argument("--out", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument(
        "--via-perception", action="store_true",
        help="compose the beat first (what perception_outcome does) and stash "
             "it on the context, so the commit reads that composition back "
             "instead of composing its own -- the A26 reuse path")
    args = ap.parse_args()

    os.environ["ENGINE_DB"] = args.db
    from core import db as core_db
    core_db.configure(args.db)
    from core.db import active_frame_id, q
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    from agents.runtime import _hydrate_steps_before, _load_extra_players
    from story.scene import active_cast
    from language_runtime import story_language
    from persist.commit import compose_beat_scene, prepare_scene_commit

    chat_row = q("SELECT * FROM chats WHERE id=?", (args.chat_id,), one=True)
    turns = q("SELECT * FROM turns WHERE chat_id=? ORDER BY idx",
              (args.chat_id,))
    out = []
    total = 0.0
    for turn_row in turns:
        keys = {r["key"] for r in q("SELECT key FROM steps WHERE turn_id=?",
                                    (turn_row["id"],))}
        if not ({"director_resolve", "director_establish"} & keys):
            continue
        token = active_frame_id.set(turn_row["frame_id"])
        try:
            ctx = PipelineContext(
                chat=ChatData.from_row(chat_row),
                turn=TurnData.from_row(turn_row),
                cast=active_cast(args.chat_id, turn_row["frame_id"]),
                input=turn_row["player_input"] or "",
                language=story_language(args.chat_id),
                extra_players=_load_extra_players(
                    args.chat_id, turn_row["idx"], turn_row["frame_id"]),
            )
            _hydrate_steps_before(ctx, turn_row["id"], 10 ** 9)
            t0 = time.perf_counter()
            compose_ms = 0.0
            if args.via_perception:
                ctx["_composed_beat"] = compose_beat_scene(ctx)
                compose_ms = (time.perf_counter() - t0) * 1000.0
            t1 = time.perf_counter()
            prepared = prepare_scene_commit(ctx)
            commit_ms = (time.perf_counter() - t1) * 1000.0
            dt = time.perf_counter() - t0
        finally:
            active_frame_id.reset(token)
        total += dt
        out.append({
            "turn_idx": turn_row["idx"],
            "answer": {
                k: prepared.get(k) for k in (
                    "scene", "clock", "diff", "destruction", "regions",
                    "charter_placements", "charter_orders",
                    "frontier_mutations", "room_registry", "prev_clock")
            },
            "warnings": list(ctx.warnings),
            "engine_feedback": list(ctx.engine_feedback),
        })
        print("turn %4d  %7.1f ms (compose %6.1f, commit %6.1f)"
              % (turn_row["idx"], dt * 1000.0, compose_ms, commit_ms),
              file=sys.stderr)
        if args.limit and len(out) >= args.limit:
            break
    print("%d beats composed, %.2fs total, %.1f ms/beat"
          % (len(out), total, 1000.0 * total / max(1, len(out))),
          file=sys.stderr)
    text = "\n".join(_canonical(row) for row in out)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    else:
        print(text)


if __name__ == "__main__":
    main()
