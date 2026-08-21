#!/usr/bin/env python3
"""Measure the reading pass that replaced two statistics.

`mind/memory_judge.review_recall` answers two questions a scorer cannot:
whether anything in a payload bears on the moment, and whether any two rows in
it fail to sit together. Both had a deterministic predecessor and both
predecessors are measured not to work -- `recall_confidence` fires 0 of 30
times on probes whose answers are absent by construction (UNBUILT 1.76), and
similarity-plus-entity-overlap contradiction detection scores a real
supersession BELOW the 95th percentile of unrelated pairs (UNBUILT 2.24). This
is the instrument that says whether reading the rows does better.

Two modes, because the two questions have different instruments:

  --mode abstention   LongMemEval: positives whose answer is in the bank, and
                      negatives whose answer is absent by construction. The
                      number that matters is FALSE abstention -- a positive
                      probe the review calls empty is a mind told it does not
                      remember something it does. The predecessor scored 0
                      false and 0 true, which is only reassuring until you
                      notice nothing fires at all.

  --mode tension      The synthetic worlds' `superseded` probes, where a
                      belief and the observation that overturns it are both
                      planted and both known by row id. Scored only on the
                      cases where retrieval actually delivered BOTH rows,
                      because a tension between a row and something absent
                      from the payload is not a tension this pass could have
                      found.

Retrieval runs through the production `search_memories` seam at the production
`_RECALL_LIMIT`, and the rows are projected exactly as `memory_context` would
project them, so what the review reads here is what it reads in a beat.

    ENGINE_DB=/scratch/bank.db python3 tools/benchmark_recall_review.py \
        --probes tools/memory_probes/longmemeval_merged.json \
        --mode abstention --limit 60 --out /scratch/abstain.json
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _rows_for(mem):
    """The shape `_attach_recall_review` hands over, from a raw search row."""
    return {
        "memory_ref": str(mem.get("event_key") or ""),
        "when": "about %s beats ago" % mem.get("turn_idx"),
        "epistemic_origin": str(mem.get("provenance") or ""),
        "gist": mem.get("gist") or "",
        "details": mem.get("content") or "",
        "_id": mem.get("id"),
    }


def _probe_bank(probe, default_bank):
    bank = probe.get("bank") or default_bank or {}
    return int(bank["chat_id"]), int(bank["char_id"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--probes", required=True)
    parser.add_argument("--mode", choices=("abstention", "tension", "dispute"),
                        required=True)
    parser.add_argument("--plan", help="dispute mode: the world's plan file")
    parser.add_argument("--character-role", default="character_major")
    parser.add_argument("--neutral-beat", action="store_true",
                        help="dispute mode: keep the payload but ask a "
                             "question that does NOT point at the "
                             "contradiction -- what ordinary play looks like")
    parser.add_argument("--with-occasion", action="store_true",
                        help="dispute mode: put the planted pair in front of "
                             "the mind as `memories_that_do_not_sit_together`")
    parser.add_argument("--k", type=int, default=None,
                        help="payload size; defaults to the production "
                             "_RECALL_LIMIT")
    parser.add_argument("--limit", type=int, default=0,
                        help="score at most this many probes of each class")
    parser.add_argument("--label", default="")
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    if not os.environ.get("ENGINE_DB"):
        raise SystemExit("set ENGINE_DB explicitly, so which bank is being "
                         "measured is a stated choice")

    from mind.memory import (_RECALL_LIMIT, backfill_missing_memory_event_keys,
                             search_memories)
    from mind.memory_judge import review_recall

    if args.mode == "dispute":
        return _dispute_mode(args)

    k = int(args.k or _RECALL_LIMIT)
    doc = json.loads(Path(args.probes).read_text(encoding="utf-8"))
    probes = doc["probes"] if isinstance(doc, dict) else doc
    default_bank = doc.get("bank") if isinstance(doc, dict) else None

    if args.mode == "abstention":
        wanted = [p for p in probes if p.get("kind") == "negative"]
        others = [p for p in probes if p.get("kind") != "negative"]
        if args.limit:
            others = others[:args.limit]
        selected = [("negative", p) for p in wanted] + \
                   [("positive", p) for p in others]
    else:
        selected = [("superseded", p) for p in probes
                    if p.get("targets") and p.get("antitargets")]
        if args.limit:
            selected = selected[:args.limit]

    # What `build_character_memory_context` does before it projects a single
    # row, and skipping it silently invalidated a whole run: every row in the
    # LongMemEval bank carries an empty `event_key`, `review_recall` drops a
    # row it could not be asked to cite, and 90 of 90 probes returned "no
    # call made" while reporting 26 rows retrieved. A benchmark that does not
    # reproduce the caller's preparation is measuring a different function.
    for chat_id, char_id in sorted({_probe_bank(p, default_bank)
                                    for _k, p in selected}):
        backfill_missing_memory_event_keys(chat_id, char_id)

    report = {"label": args.label, "mode": args.mode, "k": k,
              "probes": args.probes, "cases": []}
    t0 = time.time()
    for i, (klass, probe) in enumerate(selected, 1):
        chat_id, char_id = _probe_bank(probe, default_bank)
        raw = search_memories(chat_id, char_id, probe.get("query") or "", k=k,
                              include_archived=True, chronological=True)
        rows = [_rows_for(m) for m in raw]
        by_id = {r["_id"]: r["memory_ref"] for r in rows}
        verdict = review_recall("the character", probe.get("query") or "",
                                [{kk: vv for kk, vv in r.items()
                                  if kk != "_id"} for r in rows])
        case = {"id": probe.get("id"), "class": klass,
                "available": bool(verdict.get("available")),
                "bears_n": len(verdict.get("bears") or []),
                "abstained": verdict.get("available")
                             and verdict.get("bears") == [],
                "n_rows": len(rows)}
        if args.mode == "tension":
            target = next((by_id[t] for t in (probe.get("targets") or [])
                           if t in by_id), None)
            anti = next((by_id[a] for a in (probe.get("antitargets") or [])
                         if a in by_id), None)
            case["both_delivered"] = bool(target and anti)
            pairs = [set(t.get("memories") or [])
                     for t in (verdict.get("tensions") or [])]
            case["n_tensions"] = len(pairs)
            case["found_the_pair"] = bool(
                target and anti and {target, anti} in pairs)
            case["subjects"] = [t.get("they_disagree_about")
                                for t in (verdict.get("tensions") or [])]
        report["cases"].append(case)
        print("  %d/%d %s %s" % (i, len(selected), probe.get("id"),
                                 "abstain" if case["abstained"] else ""),
              flush=True)

    cases = report["cases"]
    report["seconds"] = round(time.time() - t0, 1)
    report["unavailable"] = sum(1 for c in cases if not c["available"])
    if report["unavailable"]:
        print("!! %d of %d cases were never reviewed -- read this before the "
              "summary below, which counts them as 'did not abstain' and "
              "'found no tension'" % (report["unavailable"], len(cases)))
    if args.mode == "abstention":
        pos = [c for c in cases if c["class"] == "positive"]
        neg = [c for c in cases if c["class"] == "negative"]
        report["summary"] = {
            "false_abstention": "%d/%d" % (
                sum(1 for c in pos if c["abstained"]), len(pos)),
            "true_abstention": "%d/%d" % (
                sum(1 for c in neg if c["abstained"]), len(neg)),
        }
    else:
        both = [c for c in cases if c["both_delivered"]]
        report["summary"] = {
            "both_rows_delivered": "%d/%d" % (len(both), len(cases)),
            "named_the_planted_pair": "%d/%d" % (
                sum(1 for c in both if c["found_the_pair"]), len(both)),
            "any_tension_at_all": "%d/%d" % (
                sum(1 for c in both if c["n_tensions"]), len(both)),
            "tensions_on_cases_missing_a_row": sum(
                c["n_tensions"] for c in cases if not c["both_delivered"]),
        }
    print(json.dumps(report["summary"], indent=2))
    print("unavailable: %d, %.0fs" % (report["unavailable"],
                                      report["seconds"]))
    if args.out:
        Path(args.out).write_text(json.dumps(report, ensure_ascii=False,
                                             indent=1), encoding="utf-8")
        print("full report:", args.out)


def _dispute_mode(args):
    """Does a mind handed the occasion actually record the dispute?

    THE LAST LINK, and the only one never run. `record_dispute` is wired end
    to end, the grounding now admits a later memory as evidence, and the
    occasion is found at mint and offered when both rows are in hand -- each
    tested in isolation, none of it ever fired as a chain.

    Two arms over the same cases: the payload as production builds it, and
    the same payload carrying `memories_that_do_not_sit_together` naming the
    planted pair. The system prompt is the REAL "READING A MEMORY
    DIFFERENTLY" contract lifted verbatim from the character sheet, because
    an invented one would measure a prompt nobody ships.
    """
    import json as _json
    from pathlib import Path as _P
    from mind import memory
    # Imported HERE, not inherited from `main`: those names are local to that
    # function, and the first run of this mode died on the third line with a
    # NameError while the shell wrapper printed "DONE" six times. A crash that
    # announces success is the same failure shape as a lane that fails open --
    # both look exactly like working.
    from mind.memory import backfill_missing_memory_event_keys
    from llm.providers import chat_complete
    from llm.prompts import get_prompt

    sheet = get_prompt("character")
    marker = "READING A MEMORY DIFFERENTLY:"
    start = sheet.index(marker)
    contract = sheet[start:start + 1100]
    system = (
        "You are the viewpoint character of a saved Sonder Engine story. "
        "Answer the one question from your supplied memory payload only. "
        "Every row is REMEMBERED PAST and carries `when`. Do not invent.\n\n"
        + contract +
        '\n\nOutput STRICT JSON: {"answer": your reply in the first person, '
        '"memory_disputes": [{"memory_ref": ..., "now_reads": ..., '
        '"evidence": [{"event_id": ...}]}]}. memory_disputes is [] unless '
        "this beat genuinely made an earlier moment read differently.")

    spec = _json.loads(_P(args.probes).read_text(encoding="utf-8"))
    plan = {f["id"]: f for f in
            _json.loads(_P(args.plan).read_text(encoding="utf-8"))["facts"]}
    chat_id, char_id = spec["bank"]["chat_id"], spec["bank"]["char_id"]
    backfill_missing_memory_event_keys(chat_id, char_id)
    cutoff = memory.q("SELECT MAX(turn_idx) mt FROM memories WHERE chat_id=? "
                      "AND char_id=?", (chat_id, char_id), one=True)["mt"] + 1

    cases, fired = [], 0
    for probe in spec["probes"]:
        if not probe.get("antitargets"):
            continue
        ctx = memory.build_character_memory_context(
            chat_id, char_id, current_turn_idx=cutoff,
            current_view="a quiet moment alone, thinking back",
            active_state={}, ponder_query=probe["query"])
        refs = {}
        for m in (ctx.get("recalled_old_memories") or []):
            refs[m.get("memory_ref")] = True
        for m in ((ctx.get("deliberate_recall") or {})
                  .get("additional_episodes") or []):
            refs[m.get("memory_ref")] = True
        rowref = {r["id"]: r["event_key"] for r in memory.q(
            "SELECT id, event_key FROM memories WHERE chat_id=? AND char_id=?",
            (chat_id, char_id))}
        target = rowref.get((probe.get("targets") or [None])[0])
        anti = rowref.get((probe.get("antitargets") or [None])[0])
        both = bool(target in refs and anti in refs)
        if args.with_occasion and both:
            ctx["memories_that_do_not_sit_together"] = [{
                "memories": [anti, target],
                "they_disagree_about": probe.get("note", "").split("|")[0]
                                       .strip() or "this"}]
        # THE ARM THAT MATTERS, and the one the first run could not see.
        #
        # Asking the probe question aims a mind straight at the contradicted
        # fact, which is a far stronger occasion than the payload key being
        # tested -- so the key was drowned by the question and both arms
        # scored the same. UNBUILT 2.24 says this in its own words ("every
        # case aims a question squarely at the contradicted fact; a beat that
        # merely happens near one does not") and I built an instrument that
        # did it anyway.
        #
        # The neutral beat keeps the precondition (ponder has put both rows in
        # the payload) and removes the pointer. That is the situation the
        # occasion exists for: a mind holding both halves on a beat about
        # something else.
        asked = ("What is on your mind just now?" if args.neutral_beat
                 else probe["query"])
        raw = chat_complete(args.character_role, system, _json.dumps(
            {"question": asked, "memory": ctx},
            ensure_ascii=False, default=str))
        try:
            got = _json.loads(raw)
        except Exception:
            got = {}
        disputes = [d for d in (got.get("memory_disputes") or [])
                    if isinstance(d, dict) and str(d.get("memory_ref") or "")]
        cited = [d for d in disputes if d.get("memory_ref") in (anti, target)]
        # Only cases where retrieval actually delivered both rows are
        # scorable, so only those may be counted -- the first run printed
        # "6/5" because a case that fired without both present was counted in
        # the numerator and excluded from the denominator.
        fired += bool(cited and both)
        cases.append({"probe": probe["id"], "both_in_payload": both,
                      "disputes": len(disputes), "cited_the_pair": bool(cited),
                      "now_reads": [d.get("now_reads") for d in cited][:1]})
        print("  %-24s both=%-5s disputes=%d pair=%s"
              % (probe["id"], both, len(disputes), bool(cited)), flush=True)
    n = len(cases)
    scorable = [c for c in cases if c["both_in_payload"]]
    print("\n  arm: %s beat, %s"
          % ("NEUTRAL" if args.neutral_beat else "aimed",
             "WITH the occasion" if args.with_occasion else "no occasion"))
    print("  emitted a dispute citing the planted pair: %d/%d"
          % (fired, len(scorable)))
    print("  emitted any dispute at all              : %d/%d"
          % (sum(1 for c in cases if c["disputes"]), n))
    if args.out:
        _P(args.out).write_text(_json.dumps(
            {"with_occasion": bool(args.with_occasion), "cases": cases},
            ensure_ascii=False, indent=1), encoding="utf-8")
        print("  full report:", args.out)


if __name__ == "__main__":
    main()
