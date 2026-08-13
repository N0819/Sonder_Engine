#!/usr/bin/env python3
"""A/B the character's deliberation surface on a REAL story, with real calls.

The question this answers is not "is it faster" -- that is arithmetic. It is
"did quality drop", which is the one outcome that makes the saving worthless.

Method: duplicate the live database, pick a turn, and rerun ONLY the
character loop against identical upstream state, N times per arm. Same beat,
same payload, same model, same seed sequence; the single variable is the
sheet's deliberation surface (prompts.deliberation_mode).

WHY only_key: rerunning the whole turn would let the Director's own variance
move the ground under the character. The character stage reads a fixed
upstream, so reruns of it are a controlled comparison and nothing else in the
turn is touched.

NEVER writes to engine.db. The copy is made with sqlite3's backup API, which
carries the WAL -- `cp` alone silently drops it and reads a stale story.

    python tools/deliberation_ab.py --chat 71 --runs 3
    python tools/deliberation_ab.py --chat 71 --runs 3 --keep   # keep the copy
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import statistics
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _duplicate(live):
    tmp = tempfile.mkdtemp(prefix="delib_ab_")
    copy = os.path.join(tmp, "engine.db")
    src = sqlite3.connect(f"file:{live}?mode=ro", uri=True)
    dst = sqlite3.connect(copy)
    src.backup(dst)
    dst.close()
    src.close()
    return tmp, copy


# --- quality signals --------------------------------------------------------
#
# Every one is derived from the decision the character actually produced, and
# every one is a property a WEAKER deliberation would plausibly degrade. None
# of them is a proxy for prose taste, which no counter can measure -- the
# transcript is printed at the end so a human reads the words themselves.

def _signals(result):
    out = {}
    cands = [c for c in (result.get("response_candidates") or [])
             if isinstance(c, dict)]
    out["candidates"] = len(cands)
    out["selected"] = sum(1 for c in cands if c.get("selected"))
    # What the chosen action serves. A mind that stops weighing tends to
    # collapse toward "situational" -- acting because the moment is there
    # rather than because something in it wants.
    #
    # CLASSIFIED BY VOCABULARY, NOT SUBSTRING. The first version counted
    # `"drive" in s` and `"intent" in s`, and the engine's serves values are
    # intention IDS -- `ia1`, `ia2` -- which contain neither word. Measured
    # consequence: every A/B row reported 0 drive-serving and 0
    # intention-serving while the same rows' candidates and wants cited
    # three live intention ids each, which read as "a mind that has stopped
    # wanting things" and was in fact a broken ruler. The vocabulary is
    # affect.py's: "drive" is the drive, "situational" (or nothing) is the
    # moment, and anything else is a named target -- an intention or
    # project id, possibly "intention:"-prefixed.
    serves = []
    for c in cands:
        if c.get("selected"):
            serves = [str(v) for v in (c.get("serves") or [])]
    active = result.get("active_state") or {}
    for want in (active.get("wants") or []):
        if isinstance(want, dict) and want.get("serves"):
            serves.append(str(want["serves"]))

    def _serves_class(value):
        v = str(value or "").strip().casefold()
        if not v or v == "situational":
            return "situational"
        if v == "drive":
            return "drive"
        return "targeted"

    classes = [_serves_class(s) for s in serves]
    out["serves_drive"] = classes.count("drive")
    out["serves_targeted"] = classes.count("targeted")
    out["serves_situational"] = classes.count("situational")
    # Grounding: the firewall's floor. If these thin out, the mind is
    # asserting more than it can point at.
    for key in ("observations_used", "present_evidence_used",
                "memory_evidence_used", "belief_updates",
                "mind_model_updates", "relationship_updates",
                "memory_effects", "remember_lines"):
        out[key] = len(result.get(key) or [])
    app = result.get("appraisal") or {}
    out["goal_impacts"] = len(app.get("goal_impacts") or [])
    out["appraisal_whys"] = sum(
        1 for k, v in app.items()
        if isinstance(v, dict) and str(v.get("why") or "").strip())
    speech = str(result.get("speech") or "")
    out["speech_chars"] = len(speech)
    out["_speech"] = speech
    seq = result.get("sequence") or []
    out["sequence_beats"] = len(seq)
    return out


def _character_results(content):
    """The per-character decisions in a loop variant, from EITHER loop.

    The two loops spell it differently -- the interaction loop stores
    `character_results`, the reaction loop `reaction_results` -- and reading
    only the first silently sampled half the story (every beat where the
    player acts ON someone runs the reaction loop). Same trap the Director
    hit reading `speaker` on rounds that record `reactor`.
    """
    for key in ("character_results", "reaction_results"):
        results = content.get(key) or {}
        if isinstance(results, dict) and results:
            return [(k, v) for k, v in results.items() if isinstance(v, dict)]
        if isinstance(results, list) and results:
            return [(str(i), v) for i, v in enumerate(results)
                    if isinstance(v, dict)]
    return []


def _reflection_signals(content):
    """Quality signals from a reflection_loop result (design note 23)."""
    out = {"reflect_out_chars": 0, "reflect_minds": 0, "reflect_updates": 0,
           "reflect_disputes": 0, "reflect_held": 0, "reflect_reviews": 0,
           "reflect_ponders": 0, "gap_mean": None}
    gaps = []
    for res in (content.get("reflections") or {}).values():
        if not isinstance(res, dict):
            continue
        out["reflect_minds"] += 1
        out["reflect_out_chars"] += len(json.dumps(res, ensure_ascii=False))
        for field in ("belief_updates", "association_updates",
                      "mind_model_updates", "relationship_updates",
                      "remember_lines", "memory_effects"):
            out["reflect_updates"] += len(res.get(field) or [])
        out["reflect_disputes"] += len(res.get("memory_disputes") or [])
        out["reflect_held"] += len(res.get("held_beliefs") or [])
        out["reflect_reviews"] += 1 if res.get("choice_review") else 0
        out["reflect_ponders"] += 1 if res.get("ponder") else 0
        gap = (res.get("expectation_gap") or {}).get("score")
        if isinstance(gap, (int, float)):
            gaps.append(float(gap))
    if gaps:
        out["gap_mean"] = sum(gaps) / len(gaps)
    return out


def _run_reflection(chat_id, turn_id, report, mode, run_idx):
    """Drive reflection_loop directly against the fresh conduct results.

    The harness reruns only the loop step, so the plan's own reflection
    step never materializes on the copied turn; reflection is exercised by
    hydrating a context exactly the way runtime's rehydration does and
    calling the loop function itself. The conduct-time stash does not
    survive into this context, so the self-slice arrives degraded -- the
    payload sizes measured here are a floor, and the cognition signals are
    the real cargo.
    """
    import sqlite3 as _sqlite3

    import db
    from agents.character import reflection_loop
    from agents.runtime import _rehydrate_loop_results
    from pipeline_context import ChatData, PipelineContext, TurnData

    chat_row = dict(db.q("SELECT * FROM chats WHERE id=?", (chat_id,),
                         one=True))
    turn_row = dict(db.q("SELECT * FROM turns WHERE id=?", (turn_id,),
                         one=True))
    from scene import active_cast
    ctx = PipelineContext(
        chat=ChatData.from_row(chat_row), turn=TurnData.from_row(turn_row),
        cast=active_cast(chat_id, turn_row["frame_id"]),
        input=turn_row["player_input"])
    from agents.storage import active_content
    for key in ("interaction_loop", "reaction_loop", "perception_outcome"):
        content = active_content(turn_id, key)
        if content is not None:
            ctx[key] = content
            _rehydrate_loop_results(ctx, key, content)
    if not ctx.perception_outcome:
        report.append({"mode": mode, "run": run_idx,
                       "error": "no perception_outcome stored"})
        return
    t0 = time.monotonic()
    result = reflection_loop(ctx, nonce=run_idx)
    elapsed = time.monotonic() - t0
    row = {"mode": mode, "run": run_idx, "turn": turn_id,
           "stage": "reflection_loop", "reflect_seconds": elapsed}
    row.update(_reflection_signals(result))
    report.append(row)


def _run_arm(copy_db, chat_id, turn_id, mode, runs, report,
             step_key="interaction_loop", experiment="deliberation"):
    os.environ["ENGINE_DB"] = copy_db
    for name in [m for m in list(sys.modules) if m.split(".")[0] in (
            "db", "prompts", "agents", "providers", "commit", "pipeline_context",
            "llm_quality", "scene", "memory")]:
        sys.modules.pop(name, None)

    import db
    db.configure(copy_db)
    if experiment == "reflection":
        # Arms: full = the shipped monolithic character call; lean = the
        # conduct/reflection split (design note 23).
        db.set_setting("character_deliberation", "full")
        db.set_setting("character_reflection",
                       "on" if mode == "lean" else "")
    else:
        db.set_setting("character_deliberation",
                       "lean" if mode == "lean" else "full")

    from agents.runtime import run_pipeline

    for i in range(runs):
        t0 = time.monotonic()
        try:
            for _ in run_pipeline(chat_id, turn_id, only_key=step_key):
                pass
        except Exception as exc:
            report.append({"mode": mode, "run": i, "error": str(exc)[:200]})
            continue
        elapsed = time.monotonic() - t0
        con = sqlite3.connect(copy_db)
        con.row_factory = sqlite3.Row
        row = con.execute(
            """SELECT v.content FROM variants v JOIN steps s ON s.id=v.step_id
               WHERE s.turn_id=? AND s.key=?
               ORDER BY v.created DESC LIMIT 1""", (turn_id, step_key)).fetchone()
        con.close()
        if not row:
            report.append({"mode": mode, "run": i, "error": "no variant"})
            continue
        content = json.loads(row["content"])
        calls = ((content.get("_engine_notes") or {}).get("llm_calls")) or []
        billed = sum(c.get("out", 0) for c in calls
                     if str(c.get("role", "")).startswith("character"))
        for who, result in _character_results(content):
            entry = {"mode": mode, "run": i, "who": who, "turn": turn_id,
                     "stage": step_key, "seconds": elapsed,
                     "out_tokens": billed,
                     "json_chars": len(json.dumps(result, ensure_ascii=False))}
            entry.update(_signals(result))
            report.append(entry)
        if experiment == "reflection" and mode == "lean":
            try:
                _run_reflection(chat_id, turn_id, report, mode, i)
            except Exception as exc:
                report.append({"mode": mode, "run": i,
                               "error": f"reflection: {exc}"[:200]})


def _summarise(report):
    arms = {}
    for row in report:
        if row.get("error"):
            continue
        arms.setdefault(row["mode"], []).append(row)
    keys = ["out_tokens", "json_chars", "seconds", "candidates",
            "serves_drive", "serves_targeted", "serves_situational",
            "observations_used", "present_evidence_used", "memory_evidence_used",
            "belief_updates", "mind_model_updates", "relationship_updates",
            "memory_effects", "remember_lines", "goal_impacts",
            "appraisal_whys", "speech_chars", "sequence_beats",
            "reflect_out_chars", "reflect_minds", "reflect_updates",
            "reflect_disputes", "reflect_held", "reflect_reviews",
            "reflect_ponders", "gap_mean", "reflect_seconds"]
    print("\n" + "=" * 76)
    print("A/B — deliberation surface")
    print("=" * 76)
    print(f"{'signal':24}{'full':>12}{'lean':>12}{'delta':>12}")
    print("-" * 76)
    for k in keys:
        vals = {}
        for mode in ("full", "lean"):
            xs = [r[k] for r in arms.get(mode, []) if isinstance(r.get(k), (int, float))]
            vals[mode] = statistics.mean(xs) if xs else None
        if vals["full"] is None or vals["lean"] is None:
            continue
        d = vals["lean"] - vals["full"]
        pct = (100 * d / vals["full"]) if vals["full"] else 0
        flag = ""
        # A quality signal moving DOWN is the thing we are watching for.
        if k not in ("out_tokens", "json_chars", "seconds") and pct < -20:
            flag = "  <== DROP"
        print(f"{k:24}{vals['full']:>12.1f}{vals['lean']:>12.1f}"
              f"{d:>+9.1f}{pct:>+6.0f}%{flag}")
    print("\nWhat each arm actually said (no counter measures prose):")
    for mode in ("full", "lean"):
        for row in arms.get(mode, [])[:2]:
            print(f"  [{mode}] {row['_speech'][:150]!r}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="engine.db")
    ap.add_argument("--chat", type=int, required=True)
    ap.add_argument("--turn", type=int, default=None)
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--experiment", default="deliberation",
                    choices=("deliberation", "reflection"),
                    help="which A/B: the deliberation surface, or "
                         "the conduct/reflection split (design "
                         "note 23; arms are split off vs on)")
    ap.add_argument("--turns", type=int, default=1,
                    help="how many recent beats to sample (N=1 on one beat "
                         "is a direction, not a result)")
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()

    tmp, copy = _duplicate(args.db)
    print(f"duplicated -> {copy}  (engine.db is never written)")
    con = sqlite3.connect(copy)
    con.row_factory = sqlite3.Row
    # The NEWEST turn that actually has a character loop. Picking the newest
    # turn outright reruns a stage that turn never had, which is four real
    # model calls spent on "step not found".
    # BOTH loop stages: a beat where the player acts on someone runs the
    # reaction loop, and excluding it would sample only the conversational
    # half of the story.
    rows = con.execute(
        """SELECT DISTINCT t.id, t.idx, s.key FROM turns t
           JOIN steps s ON s.turn_id=t.id
           WHERE t.chat_id=? AND s.key IN ('interaction_loop','reaction_loop')
           ORDER BY t.idx DESC LIMIT ?""",
        (args.chat, args.turns)).fetchall()
    if args.turn:
        beats = [(args.turn, "interaction_loop")]
    elif rows:
        beats = [(r["id"], r["key"]) for r in rows]
    else:
        print(f"chat {args.chat} has no turn with a character loop")
        return
    con.close()
    print(f"chat {args.chat}, {len(beats)} beat(s), {args.runs} run(s) per arm: "
          + ", ".join(f"{t}/{k.split('_')[0]}" for t, k in beats) + "\n")

    report = []
    try:
        for mode in ("full", "lean"):
            print(f"--- {mode} ---")
            for turn_id, key in beats:
                _run_arm(copy, args.chat, turn_id, mode, args.runs, report,
                         step_key=key, experiment=args.experiment)
        _summarise(report)
        for row in report:
            if row.get("error"):
                print(f"  ERROR [{row['mode']} run {row['run']}]: {row['error']}")
    finally:
        out = os.path.join(tempfile.gettempdir(), "deliberation_ab.json")
        with open(out, "w") as fh:
            json.dump(report, fh, indent=2)
        print(f"\nraw rows -> {out}")
        if not args.keep:
            shutil.rmtree(tmp, ignore_errors=True)
        else:
            print(f"copy kept at {copy}")


if __name__ == "__main__":
    main()
