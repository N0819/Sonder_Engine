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

Four gaps this bank exists to fill:

1. **Preference persistence.** The worst class in LongMemEval at 15/30, and
   the one that matters most here: a preference is stated once, casually, in
   generic language, and a character is expected to still act on it two
   hundred beats later. Planted early, probed late, never repeated.

2. **Belief revision.** LongMemEval scores 94.4% on knowledge-update, and the
   number is an artefact: its pass rule accepts ANY evidence row, so
   retrieving the superseded fact passes exactly like retrieving the current
   one. Here a `superseded` probe carries `targets` (the current row) AND
   `antitargets` (the stale row), and surfacing only the stale one is a
   FAILURE. Sonder has no belief versioning (UNBUILT 4.4), so a poor result is
   expected -- measuring it is the point.

3. **Provenance.** A mind may know a thing because it saw it, was told it, or
   inferred it, and the whole engine rests on those staying distinct. A
   `channel` fact happens while the owner is ELSEWHERE, so the only row that
   enters their bank is the telling, stamped `told`. The probe carries
   `expect_provenance`, and the question is whether what comes back still
   knows how it was learned.

4. **Fiction-domain negatives.** Genre-plausible events that never happened,
   written from the same plan so they name the same people and places. The
   class every abstention signal has failed on.

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
DISORDER is deliberate: storylines interleave, the gap between a fact and its
revision is drawn from a wide range, and decoy rows describe the planted
people and places from angles that do not answer the question.

Usage:
    cp engine.db /scratch/bank.db          # a configured database, not a fresh one
    ENGINE_DB=/scratch/bank.db python3 tools/generate_synthetic_bank.py \\
        --plan-size 40 --decoys 10 --negatives 12 \\
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
`preference` and `event` leave `late` empty.

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


def _json_call(role, system, user, *, retries=5):
    """One model call that must return JSON, with the fences stripped.

    Retries the TRANSPORT as well as the parse. The first version retried only
    a malformed response, so a single `RemoteDisconnected` from the provider
    killed a fifteen-minute run and lost every call before it -- which is the
    same shape as the defects this whole afternoon has been about: a transient
    failure writing a permanent loss. A dropped connection is a thing you wait
    out, exactly like the rate limit `_repair_loop` was built for.
    """
    from llm.providers import chat_complete

    last = ""
    for attempt in range(retries):
        try:
            raw = chat_complete(role, system, user)
        except Exception as exc:                # transport, not content
            last = "%s: %s" % (type(exc).__name__, exc)
            if attempt == retries - 1:
                break
            time.sleep(min(30, 2 ** attempt))
            continue
        text = str(raw or "").strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            text = text.split("\n", 1)[1] if text.startswith("json") else text
        last = text
        try:
            return json.loads(text)
        except Exception:
            time.sleep(1)
            continue
    raise SystemExit("model call failed after %d attempts: %s"
                     % (retries, last[:200]))


def build_plan(size, role, seed_prompt):
    """The answer key, written before any prose exists."""
    plan = _json_call(
        role,
        "You are planning the skeleton of a long interactive story so that a "
        "retrieval benchmark can be built from it. Be concrete and varied. "
        "Never write scene prose here.",
        "%s\n\nPlan %d facts, roughly evenly split across the four kinds. %s"
        % (seed_prompt, size, PLAN_SCHEMA))
    facts = [f for f in plan.get("facts", []) if f.get("kind") in FACT_KINDS]
    if not facts:
        raise SystemExit("plan contained no usable facts")
    plan["facts"] = facts
    return plan


def prose_for_fact(fact, plan, role, n_decoys, owner):
    """Prose for one planted fact, plus decoys that are near-misses.

    The decoys are why this is not a toy: they describe the SAME people and
    places from angles that do not answer the question, which is what a real
    bank is full of and what a synthetic one usually lacks.
    """
    cast = ", ".join(c.get("name", "") for c in plan.get("cast", [])[:8])
    return _json_call(
        role,
        "You write single memories exactly as %s would have stored them: one "
        "concrete moment, past tense, first person, 1-3 sentences. No "
        "headings, no commentary. Return JSON only." % owner,
        json.dumps({
            "cast": cast, "places": plan.get("places", [])[:8],
            "fact": fact, "decoys_wanted": n_decoys,
            "want": {
                "early": "one memory of `early`. For a `channel` fact this is "
                         "what the OTHER person saw -- write it anyway; it "
                         "will not be stored in this bank.",
                "late": "one memory of `late`, or null when `late` is empty",
                "decoys": "memories about the same people and places that do "
                          "NOT contain the fact and do not answer a question "
                          "about it",
            },
            "schema": {"early": "str", "late": "str|null", "decoys": ["str"]},
        }, default=str))


def question_for_fact(fact, role):
    """A question written from the PLAN, never from the prose.

    This is the whole methodological point. The question-writer sees the
    abstract `summary` and nothing else, so it cannot echo a phrase the prose
    happened to use.
    """
    out = _json_call(
        role,
        "You write one recall question a character asks their own memory. "
        "Ordinary language, first person. Prefer plain words over distinctive "
        "ones. Never quote the material you were given. Return JSON only.",
        json.dumps({"fact_summary": fact.get("summary", ""),
                    "subject": fact.get("subject", ""),
                    "kind": fact.get("kind", ""),
                    "schema": {"question": "str"}}))
    return str(out.get("question") or "").strip()


def negatives_for_plan(plan, role, n):
    """Genre-plausible events that never happened, in the plan's own world.

    Deliberately ADJACENT rather than absurd: they name the planted cast and
    places, so a retriever cannot reject them on topic alone. That is the
    class every abstention signal measured here has failed on.
    """
    out = _json_call(
        role,
        "You write recall questions about things that did NOT happen. They "
        "must sound like ordinary questions about this story and must name "
        "its people and places. Return JSON only.",
        json.dumps({
            "cast": [c.get("name") for c in plan.get("cast", [])[:8]],
            "places": plan.get("places", [])[:8],
            "known_facts": [f.get("summary") for f in plan["facts"]][:20],
            "wanted": n,
            "rule": "Each question must be answerable ONLY if an event that "
                    "is not in known_facts had happened. Topically adjacent, "
                    "never absurd.",
            "schema": {"questions": ["str"]},
        }, default=str))
    return [str(q).strip() for q in (out.get("questions") or []) if str(q).strip()]


def _embed_chunks(texts):
    """Token- AND count-budgeted grouping; see UNBUILT 1.75."""
    groups, cur, tok = [], [], 0
    for t in texts:
        cost = len(t) // CHARS_PER_TOKEN
        if cur and (tok + cost > EMBED_TOKEN_BUDGET
                    or len(cur) >= EMBED_COUNT_BUDGET):
            groups.append(cur)
            cur, tok = [], 0
        cur.append(t)
        tok += cost
    if cur:
        groups.append(cur)
    return groups


def _seed_bank(db, label, owner):
    now = time.time()
    chat_id = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                    (label, "", now))
    char_id = db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        (owner, json.dumps({}), "{}", now))
    return chat_id, char_id


def _write_rows(rows, chat_id, char_id):
    """Insert with the production mint path, in request-sized groups.

    Returns row ids in the order given. Refuses a fallback batch rather than
    storing hash vectors -- a bank built on crc32 measures a retrieval nobody
    runs, and would do so silently (UNBUILT 1.75, 2.21).
    """
    from mind.memory_write import add_memories_batch, prepare_memories_batch

    ids = []
    groups, cur, tok = [], [], 0
    for r in rows:
        cost = 2 * len(r["content"]) // CHARS_PER_TOKEN
        if cur and (tok + cost > EMBED_TOKEN_BUDGET
                    or len(cur) >= EMBED_COUNT_BUDGET // 2):
            groups.append(cur)
            cur, tok = [], 0
        cur.append(r)
        tok += cost
    if cur:
        groups.append(cur)

    for group in groups:
        prepared = prepare_memories_batch([
            {"chat_id": chat_id, "char_id": char_id, "turn_id": None,
             "kind": "episodic", "category": "episode",
             "provenance": r["provenance"], "salience": r["salience"],
             "content": r["content"], "gist": r["content"][:240],
             "turn_idx": r["turn_idx"]}
            for r in group])
        batch = prepared.get("embedded")
        if batch is not None and getattr(batch, "fallback", False):
            raise SystemExit(
                "embedding fell back to crc32 after %d rows; the bank would "
                "be measuring a retrieval nobody runs. Stopping." % len(ids))
        ids.extend(add_memories_batch(prepared_batch=prepared))
        print("    %d rows written" % len(ids), flush=True)
    return ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan-size", type=int, default=40)
    ap.add_argument("--decoys", type=int, default=10,
                    help="near-miss rows generated per fact")
    ap.add_argument("--negatives", type=int, default=12)
    ap.add_argument("--out-probes", required=True)
    ap.add_argument("--role", default="utility")
    ap.add_argument("--seed", type=int, default=20260820)
    ap.add_argument("--seed-prompt", default=(
        "A long-running story set in one town over several seasons, with a "
        "recurring cast who work, argue, travel and keep secrets."))
    ap.add_argument("--owner", default="Mara Chen",
                    help="whose bank this is; a `channel` fact only tests "
                         "anything when the owner did NOT witness it")
    ap.add_argument("--label", default="Synthetic fiction bank")
    ap.add_argument("--plan-file", help="reuse a plan instead of generating one")
    args = ap.parse_args()

    _refuse_live_database()
    from core import db
    db.init()
    model_key, dims = _refuse_fallback_embeddings()
    print("embeddings: %s (%dd)" % (model_key, dims))

    rng = random.Random(args.seed)
    if args.plan_file:
        plan = json.loads(Path(args.plan_file).read_text(encoding="utf-8"))
        print("reusing plan: %d facts" % len(plan["facts"]))
    else:
        print("planning %d facts..." % args.plan_size)
        plan = build_plan(args.plan_size, args.role,
                          args.seed_prompt + "\nThe bank belongs to "
                          + args.owner + ", who is the viewpoint character.")
    print("  %d facts, %d cast, %d places" % (
        len(plan["facts"]), len(plan.get("cast", [])),
        len(plan.get("places", []))))
    Path(args.out_probes).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_probes + ".plan.json").write_text(
        json.dumps(plan, indent=1, ensure_ascii=False), encoding="utf-8")

    # ---- prose, one call per fact, checkpointed ------------------------
    # Written to disk as each fact completes, and read back on a rerun. A
    # provider blip fifteen minutes into a run used to lose every call before
    # it; now it loses one. The cache is keyed by fact id, so editing the plan
    # invalidates only the facts that changed.
    cache_path = Path(args.out_probes + ".prose.jsonl")
    prose_cache = {}
    if cache_path.exists():
        for line in cache_path.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
                prose_cache[rec["id"]] = rec["prose"]
            except Exception:
                continue
        print("  resuming: %d facts already have prose" % len(prose_cache))

    pending = []          # (fact, role_in_fact, text)
    for i, fact in enumerate(plan["facts"], 1):
        fid = fact.get("id")
        prose = prose_cache.get(fid)
        if prose is None:
            try:
                prose = prose_for_fact(fact, plan, args.role, args.decoys,
                                       args.owner)
            except SystemExit as exc:
                print("  fact %s skipped: %s" % (fid, exc))
                continue
            with cache_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"id": fid, "prose": prose},
                                    ensure_ascii=False) + "\n")
        early = str(prose.get("early") or "").strip()
        late = str(prose.get("late") or "").strip()
        # A `channel` fact's `early` is the OTHER person's direct observation.
        # It must not enter this bank: the owner was elsewhere, and a bank
        # holding both channels cannot score the distinction it exists for.
        if early and fact["kind"] != "channel":
            pending.append((fact, "early", early))
        if late:
            pending.append((fact, "late", late))
        for d in (prose.get("decoys") or [])[:args.decoys]:
            d = str(d or "").strip()
            if d:
                pending.append((fact, "decoy", d))
        print("  [%d/%d] %s %s -> %d rows" % (
            i, len(plan["facts"]), fact.get("id"), fact.get("kind"),
            sum(1 for p in pending if p[0] is fact)), flush=True)

    if not pending:
        raise SystemExit("no prose generated")

    # ---- placement: structured content, randomised arrangement ---------
    span = max(600, len(pending) * 3)
    slots = {}
    for fact in plan["facts"]:
        base = rng.randrange(0, max(1, span // 2))
        slots[fact["id"]] = (base, base + rng.randrange(60, 400))
    rows = []
    for fact, role_in_fact, text in pending:
        early_t, late_t = slots[fact["id"]]
        if role_in_fact == "early":
            turn = early_t
        elif role_in_fact == "late":
            turn = late_t
        else:
            turn = rng.randrange(0, span)          # decoys interleave freely
        # `told` only for the telling of a channel fact -- the one route the
        # owner legitimately had. Everything else this bank plants, the owner
        # was present for.
        prov = "told" if (fact["kind"] == "channel"
                          and role_in_fact == "late") else "witnessed"
        rows.append({"content": text, "turn_idx": turn, "provenance": prov,
                     "salience": 0.6 if role_in_fact != "decoy" else 0.45,
                     "_fact": fact["id"], "_role": role_in_fact})
    rows.sort(key=lambda r: r["turn_idx"])

    chat_id, char_id = _seed_bank(db, args.label, args.owner)
    print("\nwriting %d rows into bank %d/%d..." % (len(rows), chat_id, char_id))
    ids = _write_rows(rows, chat_id, char_id)
    for r, rid in zip(rows, ids):
        r["_id"] = rid
    by_fact = {}
    for r in rows:
        by_fact.setdefault(r["_fact"], {}).setdefault(r["_role"], []).append(r)

    # ---- probes: questions written from the plan alone -----------------
    print("\nwriting questions from the plan (never from the prose)...")
    probes = []
    for i, fact in enumerate(plan["facts"], 1):
        got = by_fact.get(fact["id"])
        if not got:
            continue
        try:
            question = question_for_fact(fact, args.role)
        except SystemExit:
            continue
        if not question:
            continue
        kind = fact["kind"]
        targets, antitargets, expect = [], [], None
        if kind == "superseded":
            # The current truth is the answer; the stale belief is the trap.
            targets = [r["_id"] for r in got.get("late", [])]
            antitargets = [r["_id"] for r in got.get("early", [])]
        elif kind == "channel":
            targets = [r["_id"] for r in got.get("late", [])]
            expect = "told"
        else:
            targets = [r["_id"] for r in got.get("early", [])]
        if not targets:
            continue
        probes.append({
            "id": "%s_%s" % (fact["id"], kind),
            "kind": "positive",
            "query": question,
            "targets": sorted(targets),
            "antitargets": sorted(antitargets),
            "expect_provenance": expect,
            "note": "%s | %s" % (kind, str(fact.get("summary", ""))[:160]),
        })
        print("  [%d/%d] %s" % (i, len(plan["facts"]), fact["id"]), flush=True)

    if args.negatives:
        print("\nwriting %d negatives..." % args.negatives)
        try:
            for j, q in enumerate(negatives_for_plan(plan, args.role,
                                                     args.negatives)):
                probes.append({
                    "id": "neg%02d" % (j + 1), "kind": "negative",
                    "query": q, "targets": [], "antitargets": [],
                    "expect_provenance": None,
                    "note": "absent by construction: written from the plan as "
                            "an event that never happened",
                })
        except SystemExit as exc:
            print("  negatives skipped: %s" % exc)

    spec = {
        "bank": {"chat_id": chat_id, "char_id": char_id,
                 "label": "%s (%d rows)" % (args.label, len(ids))},
        "authored": time.strftime("%Y-%m-%d"),
        "note": ("Generated by tools/generate_synthetic_bank.py. The PLAN was "
                 "written first; prose was written from a plan entry; each "
                 "question was written from the SAME entry by a call that "
                 "never saw the prose. `antitargets` are superseded rows -- "
                 "retrieving only those is a failure, which no borrowed "
                 "benchmark can express. `expect_provenance` asks whether "
                 "what comes back still knows how it was learned."),
        "probes": probes,
    }
    Path(args.out_probes).write_text(
        json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    pos = [p for p in probes if p["kind"] == "positive"]
    print("\nbank %d/%d: %d rows" % (chat_id, char_id, len(ids)))
    print("probes: %d positive (%d with antitargets, %d provenance-checked), "
          "%d negative" % (
              len(pos), sum(1 for p in pos if p["antitargets"]),
              sum(1 for p in pos if p["expect_provenance"]),
              sum(1 for p in probes if p["kind"] == "negative")))
    print("probe file: %s" % args.out_probes)


if __name__ == "__main__":
    main()
