"""Replay every stored beat of a chat and digest what a reader would SEE.

WHY IT EXISTS. A wave of changes to perception, the composer, the narrator
payload and the world derivations is only safe if every beat it does not
mean to touch is byte-identical. The per-item harnesses each prove one
mechanism; this proves the PAGE, across the whole corpus, in one file you can
diff. Run it at the old revision and at the new one, on a fresh copy of the
same database each time, and diff:

    cp bench.db /tmp/b.db && chmod u+w /tmp/b.db
    python tools/bench/beat_replay_digest.py /tmp/b.db 114 --out before.json
    # ...move the tree, take a FRESH copy...
    python tools/bench/beat_replay_digest.py /tmp/b.db 114 --out after.json
    diff before.json after.json

WHAT IT CAPTURES, per beat, canonicalised (sorted keys, stable order):
  * every observer's composed view TEXT and their structured observations --
    the two representations the firewall keeps from disagreeing;
  * the standing ledger each observer ends the beat with;
  * the objective scene the beat composed;
  * the narrator's world fields.
That is what a defect in this layer surfaces as. A diff line here is either
a change the wave declared or a defect, and there is no third case.

NO MODEL CALL IS MADE. The stored `director_interpret` and `director_resolve`
variants are replayed as the beat's own answers, so a run costs no provider
and needs no key. A COPY IS NOT OPTIONAL: composing a beat files engine
notices and once-per-chat flags outside the turn transaction.

Read the scene each beat starts from is the chat's CURRENT committed scene,
not a per-turn snapshot (none is stored). What this proves is that the same
inputs give the same answer through both revisions, over real stored data.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))


def _canonical(value):
    return json.loads(json.dumps(value, sort_keys=True, default=str))


def _digest_step(content):
    """The reader-facing half of a perception step, order-stable."""
    if not isinstance(content, dict):
        return {"shape": type(content).__name__}
    out = {}
    views = content.get("views")
    if isinstance(views, dict):
        out["views"] = {pid: (v or {}).get("text", "") if isinstance(v, dict)
                        else str(v) for pid, v in sorted(views.items())}
    obs = content.get("observations")
    if isinstance(obs, dict):
        out["observations"] = {pid: _canonical(v) for pid, v in sorted(obs.items())}
    company = content.get("company")
    if isinstance(company, dict):
        out["company"] = {pid: _canonical(v) for pid, v in sorted(company.items())}
    ledger = content.get("composer_ledger")
    if isinstance(ledger, dict):
        out["ledger"] = {pid: {k: sorted(v) if isinstance(v, list) else _canonical(v)
                               for k, v in sorted((entry or {}).items())}
                         for pid, entry in sorted(ledger.items())}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("db")
    ap.add_argument("chat_id", type=int)
    ap.add_argument("--out", default="")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    os.environ["ENGINE_DB"] = args.db
    from core import db
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    from persist.steps import active_content

    chat_row = db.q("SELECT * FROM chats WHERE id=?", (args.chat_id,), one=True)
    if not chat_row:
        raise SystemExit("no such chat")
    turns = db.q("SELECT * FROM turns WHERE chat_id=? ORDER BY idx",
                 (args.chat_id,))
    if args.limit:
        turns = turns[:args.limit]

    cast = db.q(
        "SELECT ch.*, cc.state AS cstate, cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (args.chat_id,))

    from agents import perception

    beats, skipped = [], 0
    for turn in turns:
        resolve = active_content(turn["id"], "director_resolve")
        interp = active_content(turn["id"], "director_interpret")
        if not isinstance(resolve, dict):
            skipped += 1
            continue
        ctx = PipelineContext(
            chat=ChatData(id=chat_row["id"], name=chat_row["name"],
                          persona_id=chat_row["persona_id"],
                          lorebook_id=chat_row["lorebook_id"],
                          scenario=chat_row["scenario"] or "",
                          created=chat_row["created"]),
            turn=TurnData(id=turn["id"], chat_id=args.chat_id, idx=turn["idx"],
                          player_input=turn["player_input"] or "",
                          created=turn["created"],
                          frame_id=turn["frame_id"]
                          if "frame_id" in turn.keys() else None),
            cast=cast, input=turn["player_input"] or "")
        ctx.director_resolve = resolve
        if isinstance(interp, dict):
            ctx.director_interpret = interp
        entry = {"idx": turn["idx"]}
        try:
            perception.perception_outcome(ctx, 0)
            entry["page"] = _digest_step(ctx.get("perception_outcome"))
            entry["scene"] = _canonical(ctx._extra.get("outcome_scene") or {})
            entry["warnings"] = sorted(str(w) for w in (ctx.warnings or []))
        except Exception as exc:                       # noqa: BLE001
            entry["error"] = "%s: %s" % (type(exc).__name__, exc)
            entry["trace"] = traceback.format_exc().splitlines()[-3:]
        beats.append(entry)

    doc = {"chat_id": args.chat_id, "beats": beats,
           "replayed": len(beats), "skipped_no_resolve": skipped}
    text = json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False,
                      default=str)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        errors = sum(1 for b in beats if "error" in b)
        print("%s: %d beats (%d errored, %d skipped) -> %s"
              % (args.db, len(beats), errors, skipped, args.out))
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
