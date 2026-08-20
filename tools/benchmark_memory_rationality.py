#!/usr/bin/env python3
"""Does a mind handed contradictory memories reason, or take the first one?

Every memory measurement this project has answers "what reached the character".
None answers "what did the character do with it", and the gap matters most in
the one case the architecture is built for: a mind holding a belief and the
later observation that overturns it.

Retrieval already delivers both. Measured across three independently generated
fiction worlds (`docs/experiments/SYNTHETIC_BANK.md`): the correction reaches
the payload 16 times in 18, and outranks the stale belief only 8 times in 18 --
so the character is usually shown the outdated row FIRST. Both rows carry a
`when` stamp, so the material to prefer the newer one is present.

This asks what happens next, and sorts it into four outcomes that mean
different things:

    current    stated the corrected fact -- reasoned from conflicting evidence
    stale      stated the superseded one -- took what it read first
    conflict   named the contradiction    -- the best outcome, and the one
               `record_dispute` exists for (fired once in 9,608 live memories)
    neither    answered from something else, or did not answer

`stale` is the failure this exists to count. `conflict` is not a lesser form
of `current`: a mind that notices its own belief was overturned is doing the
thing the dispute lane was built to receive, and the engine currently has no
way to find out how often that happens.

The judge is a separate model call that never sees the memory payload -- only
the answer and the two competing facts from the PLAN. It cannot be swayed by
what retrieval happened to deliver.

Usage:
    ENGINE_DB=/scratch/world1.db python3 tools/benchmark_memory_rationality.py \\
        --probes tools/memory_probes/synthetic_world1.json \\
        --plan /scratch/w1.json.plan.json --repeats 2
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# The leading clause below ("if your memories disagree, say so") is the whole
# reason for --unled. Asking for a behaviour and then measuring it establishes
# CAPABILITY and says nothing about RATE, and production carries no such
# instruction. Both arms are needed: one says what a mind can do, the other
# what it does unprompted.
CHARACTER_SYSTEM = (
    "You are the viewpoint character of this saved Sonder Engine story. "
    "Answer the one question from your supplied memory payload only. "
    "Every row is REMEMBERED PAST and carries `when` -- how long ago it was. "
    "`epistemic_origin` says how you came to know it: what_i_was_told is "
    "received, what_i_concluded is fallible. Do not invent. If your memories "
    "disagree with each other, say so plainly rather than picking one "
    "silently. Answer in two or three sentences, first person."
)

JUDGE_SYSTEM = (
    "You classify one answer against two competing facts. EARLIER is what was "
    "believed first; LATER is what overturned it. Decide what the answer "
    "asserts:\n"
    "  current  -- it states LATER, or is consistent with LATER and not EARLIER\n"
    "  stale    -- it states EARLIER as though still true\n"
    "  conflict -- it names the contradiction, or says the earlier belief was "
    "wrong or has changed\n"
    "  neither  -- it addresses something else, hedges without content, or "
    "does not answer\n"
    "Prefer `conflict` over `current` when the answer explicitly acknowledges "
    "the earlier belief was superseded. Return JSON only: "
    '{"verdict":"current|stale|conflict|neither","why":str}'
)


def _json_call(role, system, user, *, retries=4):
    from llm.providers import chat_complete
    import time as _t
    last = ""
    for attempt in range(retries):
        try:
            raw = chat_complete(role, system, user)
        except Exception as exc:
            last = f"{type(exc).__name__}: {exc}"
            _t.sleep(min(20, 2 ** attempt))
            continue
        text = str(raw or "").strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            text = text.split("\n", 1)[1] if text.startswith("json") else text
        last = text
        try:
            return json.loads(text)
        except Exception:
            _t.sleep(1)
    raise SystemExit("model call failed after %d attempts: %s" % (retries, last[:200]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--probes", required=True)
    ap.add_argument("--plan", required=True)
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--character-role", default="character_major")
    ap.add_argument("--judge-role", default="utility")
    ap.add_argument("--output")
    ap.add_argument("--unled", action="store_true",
                    help="drop the clause inviting the character to name a "
                         "conflict, which is what production actually does")
    args = ap.parse_args()

    if not os.environ.get("ENGINE_DB"):
        raise SystemExit("set ENGINE_DB to the database holding this bank")

    from mind import memory
    from llm.providers import chat_complete

    system = CHARACTER_SYSTEM
    if args.unled:
        system = system.replace(
            "If your memories disagree with each other, say so plainly rather "
            "than picking one silently. ", "")
        assert "disagree" not in system, "the leading clause must actually go"

    spec = json.loads(Path(args.probes).read_text(encoding="utf-8"))
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    facts = {f["id"]: f for f in plan["facts"]}
    chat_id, char_id = spec["bank"]["chat_id"], spec["bank"]["char_id"]

    cases = []
    for p in spec["probes"]:
        if not p.get("antitargets"):
            continue
        fid = p["id"].rsplit("_", 1)[0]
        fact = facts.get(fid)
        if fact and fact.get("early") and fact.get("late"):
            cases.append((p, fact))
    if not cases:
        raise SystemExit("no superseded probes with antitargets in this bank")

    cutoff = memory.q("SELECT MAX(turn_idx) mt FROM memories "
                      "WHERE chat_id=? AND char_id=?",
                      (chat_id, char_id), one=True)["mt"] + 1
    print(f"{len(cases)} superseded facts, {args.repeats} repeat(s), "
          f"bank {chat_id}/{char_id}\n")

    tally = collections.Counter()
    rows = []
    for i, (probe, fact) in enumerate(cases, 1):
        for rep in range(args.repeats):
            ctx = memory.build_character_memory_context(
                chat_id, char_id, current_turn_idx=cutoff,
                current_view="a quiet moment alone, thinking back",
                active_state={}, ponder_query=probe["query"])
            answer = str(chat_complete(
                args.character_role, system,
                json.dumps({"question": probe["query"], "memory": ctx},
                           ensure_ascii=False, default=str)) or "").strip()
            verdict = _json_call(
                args.judge_role, JUDGE_SYSTEM,
                json.dumps({"question": probe["query"],
                            "EARLIER": fact["early"], "LATER": fact["late"],
                            "answer": answer}, ensure_ascii=False))
            v = str(verdict.get("verdict") or "neither")
            tally[v] += 1
            rows.append({"probe": probe["id"], "repeat": rep, "verdict": v,
                         "why": verdict.get("why", ""), "answer": answer})
            print(f"  [{i}/{len(cases)}] {probe['id']:<32} {v}", flush=True)

    n = sum(tally.values())
    print(f"\n{n} answers")
    for key in ("current", "conflict", "stale", "neither"):
        print(f"   {key:<9} {tally[key]:>3}  ({tally[key]/max(1,n):>5.0%})")
    rational = tally["current"] + tally["conflict"]
    print(f"\n   reasoned from the newer evidence: {rational}/{n} "
          f"({rational/max(1,n):.0%})")
    print(f"   took the superseded belief      : {tally['stale']}/{n} "
          f"({tally['stale']/max(1,n):.0%})")
    if args.output:
        Path(args.output).write_text(
            json.dumps({"bank": spec["bank"], "tally": dict(tally),
                        "rows": rows}, ensure_ascii=False, indent=2),
            encoding="utf-8")
        print(f"\nfull transcript: {args.output}")


if __name__ == "__main__":
    main()
