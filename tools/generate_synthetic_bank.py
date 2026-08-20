#!/usr/bin/env python3
"""Generate a fiction-domain memory bank whose probes are independent by
construction, and which contains the three things no borrowed benchmark can
test.

LongMemEval answered what it could (`docs/experiments/CRC32_CONTROL.md`,
UNBUILT 1.76): retrieval is scale-robust to 10,960 rows, embeddings buy +61
probes over lexical, and the abstention signal is blind. What it cannot reach
is everything downstream of its own domain -- it is task-oriented
user/assistant chat, so nothing in it was *witnessed*, nothing was *told* by a
third party, and no fact in it is superseded in a way its pass rule can score.

Three gaps this bank exists to fill:

1. **Preference persistence.** The worst class in LongMemEval at 15/30, and
   the one that matters most here: a preference is stated once, casually, in
   generic language, and a character is expected to still act on it two
   hundred beats later. Planted early, probed late, never repeated.

2. **Belief revision.** LongMemEval scores 94.4% on knowledge-update, and the
   number is an artefact: its pass rule accepts ANY evidence row, so
   retrieving the superseded fact passes exactly like retrieving the current
   one. Here a `superseded` probe carries `targets` (the current row) AND
   `antitargets` (the stale row), and retrieving only the stale one is a
   FAILURE. Sonder has no belief versioning (UNBUILT 4.4), so the expected
   result is bad -- which is the point of measuring it.

3. **Provenance.** A mind may know a thing because it saw it, was told it, or
   inferred it, and the whole engine rests on those staying distinct. A
   `channel` probe asks about an event the character only ever HEARD about,
   and its antitargets are rows about the same event from another character's
   direct observation.

**Why generated rather than authored.** Every probe this project has was
written by someone who had read the rows it targets, so the question's
vocabulary was chosen knowing the answer's. Here the PLAN is generated first;
prose is generated from a plan entry, and the probe question is generated from
the same plan entry by a separate call that never sees the prose. The question
and the answer are siblings rather than parent and child, so shared wording is
whatever the plan forced, not what an author noticed.

**Structure the content, randomise the arrangement.** Random prose would be
maximally separable and would flatter any retriever -- real recall is hard
because forty rows describe the same room. So the plan is deliberate and the
DISORDER is deliberate: storylines interleave, the gap between an event and
its probe is drawn from a wide range, and decoy rows describe planted events
from angles that are not the target.

Usage:
    cp engine.db /scratch/bank.db          # a configured database, not a fresh one
    ENGINE_DB=/scratch/bank.db python3 tools/generate_synthetic_bank.py \\
        --plan-size 40 --rows-per-fact 12 \\
        --out-probes tools/memory_probes/synthetic_fiction.json

Then measure with the ordinary instrument:
    ENGINE_DB=/scratch/bank.db python3 tools/memory_probe_harness.py \\
        --probes tools/memory_probes/synthetic_fiction.json --label synthetic
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Same ceiling and the same reason as tools/longmemeval_to_bank.py: the
# provider caps a request by tokens AND by input count, and a refusal is not
# retried into success, it is replaced by hash vectors (UNBUILT 1.75).
EMBED_TOKEN_BUDGET = 60_000
EMBED_COUNT_BUDGET = 64
CHARS_PER_TOKEN = 4

FACT_KINDS = ("preference", "superseded", "channel", "event")

PLAN_SCHEMA = """Return JSON only:
{"cast":[{"name":str,"role":str}],
 "places":[str],
 "facts":[{"id":str,"kind":"preference|superseded|channel|event",
           "subject":str,"summary":str,
           "early":str,"late":str}]}

`summary` states the fact abstractly, for a question-writer who will never see
the story prose. `early` is what happens first; for `superseded` it is the fact
that is later replaced. `late` is what supersedes or reveals it later; for
`preference` leave `late` empty.

A `channel` fact MUST name an observer who is NOT the bank's owner, and its
`early` must be that observer's DIRECT observation while the owner is
elsewhere. `late` is the moment the owner is TOLD about it. The whole point is
that the owner's only route to this fact is hearsay: if the owner witnessed
it too, the fact tests nothing, because both channels then carry it and the
distinction the engine is built on cannot be scored."""


def _refuse_live_database():
    target = os.environ.get("ENGINE_DB", "")
    if not target:
        raise SystemExit("set ENGINE_DB to a scratch copy of a CONFIGURED "
                         "database (a fresh one has no embeddings provider)")
    if Path(target).expanduser().resolve() == (
            Path(__file__).resolve().parents[1] / "engine.db").resolve():
        raise SystemExit("refusing to write the live engine.db")


def _refuse_fallback_embeddings():
    from llm.providers import embed_texts_meta
    batch = embed_texts_meta(["retrieval configuration probe"])
    if batch.fallback:
        raise SystemExit(
            "embeddings resolved to the crc32 fallback, which measures 49 "
            "probes WORSE than no vectors at all (UNBUILT 2.21). Configure "
            "the embeddings role before generating a bank.")
    return batch.model_key, batch.dimensions


def _json_call(role, system, user, *, retries=3):
    """One model call that must return JSON, with the fences stripped."""
    from llm.providers import chat_complete
    for attempt in range(retries):
        raw = chat_complete(role, system, user)
        text = str(raw or "").strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            text = text.split("\n", 1)[1] if text.startswith("json") else text
        try:
            return json.loads(text)
        except Exception:
            if attempt == retries - 1:
                raise SystemExit("model did not return JSON after "
                                 f"{retries} attempts: {text[:200]}")
    return None


def build_plan(size, role, seed_prompt):
    """The answer key, written before any prose exists."""
    plan = _json_call(
        role,
        "You are planning the skeleton of a long interactive story so that a "
        "retrieval benchmark can be built from it. Be concrete and varied. "
        "Never write scene prose here.",
        f"{seed_prompt}\n\nPlan {size} facts, roughly evenly split across the "
        f"four kinds. {PLAN_SCHEMA}")
    facts = [f for f in plan.get("facts", []) if f.get("kind") in FACT_KINDS]
    if not facts:
        raise SystemExit("plan contained no usable facts")
    plan["facts"] = facts
    return plan


def rows_for_fact(fact, plan, role, n_decoys):
    """Prose for one planted fact, plus decoys that are near-misses.

    The decoys are the reason this is not a toy: they describe the SAME
    people and places from angles that do not answer the question, which is
    what a real bank is full of and what a synthetic one usually lacks.
    """
    cast = ", ".join(c.get("name", "") for c in plan.get("cast", [])[:6])
    out = _json_call(
        role,
        "You write single memories as a character would have stored them: one "
        "concrete moment, past tense, first person, 1-3 sentences. Return JSON "
        "only.",
        json.dumps({
            "cast": cast, "places": plan.get("places", [])[:6],
            "fact": fact, "decoys_wanted": n_decoys,
            "want": {"early": "one memory of `early`",
                     "late": "one memory of `late`, or null when empty",
                     "decoys": "memories about the same people and places "
                               "that do NOT contain the fact"},
            "schema": {"early": str, "late": "str|null", "decoys": [str]},
        }, default=str))
    return out


def probe_for_fact(fact, role):
    """A question written from the PLAN, never from the prose.

    This is the whole methodological point. The question-writer is given the
    abstract `summary` and nothing else, so it cannot echo a phrase the prose
    happened to use.
    """
    out = _json_call(
        role,
        "You write one recall question a character might ask their own "
        "memory. Use ordinary language. Do NOT reuse distinctive nouns from "
        "the material you are given if a plainer word exists. Return JSON only.",
        json.dumps({"fact_summary": fact.get("summary", ""),
                    "subject": fact.get("subject", ""),
                    "kind": fact.get("kind", ""),
                    "schema": {"question": str}}))
    return str(out.get("question") or "").strip()


def _embed_chunks(texts):
    """Token- AND count-budgeted grouping; see UNBUILT 1.75."""
    groups, cur, tok = [], [], 0
    for t in texts:
        cost = len(t) // CHARS_PER_TOKEN
        if cur and (tok + cost > EMBED_TOKEN_BUDGET
                    or len(cur) >= EMBED_COUNT_BUDGET):
            groups.append(cur); cur, tok = [], 0
        cur.append(t); tok += cost
    if cur:
        groups.append(cur)
    return groups


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan-size", type=int, default=40)
    ap.add_argument("--rows-per-fact", type=int, default=12)
    ap.add_argument("--out-probes", required=True)
    ap.add_argument("--role", default="utility",
                    help="model role to generate with (default: utility)")
    ap.add_argument("--seed", type=int, default=20260820)
    ap.add_argument("--seed-prompt", default=(
        "A long-running story set in one town over several seasons, with a "
        "recurring cast who work, argue, travel and keep secrets."))
    ap.add_argument("--owner", default="Mara Chen",
                    help="whose bank this is; a `channel` fact only tests "
                         "anything when the owner did NOT witness it")
    ap.add_argument("--label", default="Synthetic fiction bank")
    args = ap.parse_args()

    _refuse_live_database()
    from core import db
    db.init()
    model_key, dims = _refuse_fallback_embeddings()
    print(f"embeddings: {model_key} ({dims}d)")

    rng = random.Random(args.seed)
    print(f"planning {args.plan_size} facts...")
    plan = build_plan(args.plan_size, args.role,
                      args.seed_prompt + "\nThe bank belongs to "
                      + args.owner + ", who is the viewpoint character.")
    print(f"  plan: {len(plan['facts'])} facts, "
          f"{len(plan.get('cast', []))} cast, {len(plan.get('places', []))} places")

    Path(args.out_probes).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_probes + ".plan.json").write_text(
        json.dumps(plan, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"  plan written beside the probes (the answer key, kept for audit)")
    print("\nNext: prose generation and turn placement -- see --help. This "
          "pilot stops after the plan so the plan can be inspected before "
          "spending a generation budget on it.")


if __name__ == "__main__":
    main()
