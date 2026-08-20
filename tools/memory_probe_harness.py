#!/usr/bin/env python3
"""Deterministic retrieval probe harness for character memory.

Runs labeled probes through the PRODUCTION `search_memories` seam against a
COPY of a populated database and reports, per probe, whether any target row
reaches the k=16 payload a character would actually receive. This is the
instrument that makes ranking/extraction changes falsifiable
(docs/experiments/AUDIT_MEMORY.md section 4.1): the probe sets under
`tools/memory_probes/` are FROZEN — authored from bank contents before any
change, never adjusted once a fix is in.

Discipline the instrument enforces:

- No model calls for SCORING. The only provider traffic is embedding each
  probe query once, through the same `embed_texts_meta` seam production uses;
  pass/fail is a deterministic membership check on the returned payload.
- Query vectors are cached on disk (keyed by model + text), so two runs of
  the harness compare code, never embedding jitter, and re-running is free.
- A fallback (crc32) query embedding ABORTS the run rather than scoring: a
  lexical hash vector would silently measure a different retrieval than the
  one players get (measured 0% paraphrase recall, docs/guides/MEMORY.md §4).
  `--allow-fallback-queries` turns that refusal into a DECLARED arm rather
  than removing it. The refusal exists because the substitution is silent,
  not because the hash is unmeasurable — a null control needs a retriever
  with no semantic capability, and crc32 is exactly that. So the flag scores,
  and in exchange every result it produces is stamped: the report carries
  `allow_fallback_queries` and a per-bank `fallback_queries` count, and the
  run prints a banner. The distinction UNBUILT §1.75 is about is undeclared
  substitution versus a chosen mode; this is the second one. The pass rule
  does not move, and without the flag nothing changes.
- Probes run with no aspects and no location cues — the standalone-query
  slice of production retrieval. That is deliberately the harder, purer test
  of the four fused rankings; the aspect/bonus machinery is measured
  elsewhere (tools/salience_replay.py).

Negative probes (kind: "negative", empty targets) name events genuinely
absent from the bank. Plain retrieval always returns k rows, so they score
nothing by themselves; they exist to calibrate an abstention ("I don't
remember") floor, and the harness reports the per-probe score distribution
plus, when the production seam exposes `recall_confidence`, that signal —
additively, without touching the frozen pass rule.

Usage:
    ENGINE_DB=/tmp/copy.db python3 tools/memory_probe_harness.py \
        --probes tools/memory_probes/tuned_chat63_char35.json \
        [--probes ...] [--out results.json] [--label baseline]

Never point this at the live engine.db: it opens the database read-write
(SQLite), even though it only reads memory rows.
"""

import argparse
import base64
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_QCACHE_DEFAULT = "/tmp/memory_probe_qcache.json"


def _load_qcache(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _save_qcache(path, cache):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(cache, fh)
    os.replace(tmp, path)


def _qkey(model_key, text):
    return hashlib.sha1(
        (model_key + "\x00" + text).encode("utf-8")).hexdigest()


_FALLBACK_REFUSAL = (
    "refusing to score with a fallback (lexical hash) query embedding — the "
    "instrument would measure a different retrieval than production. "
    "Configure the embeddings provider, or pass --allow-fallback-queries to "
    "run a DECLARED null-control arm.")


def _embedded_batch(query, cache, cache_path, allow_fallback=False):
    """One EmbeddingBatch for one query, disk-cached by (model, text)."""
    import numpy as np
    from llm.providers import EmbeddingBatch, embed_texts_meta, embedding_model_key

    model_key = embedding_model_key()
    key = _qkey(model_key, query)
    hit = cache.get(key)
    if hit and hit.get("model_key") == model_key:
        vec = np.frombuffer(base64.b64decode(hit["vec"]), dtype=np.float32)
        # THE CACHE MUST NOT LAUNDER THE FLAG. A cached entry used to be
        # rebuilt as `fallback=False` unconditionally, which was true of every
        # entry the old code could write (a fallback aborted before caching)
        # and stops being true the moment a declared arm caches one. Anything
        # downstream that branches on `fallback` -- `recall_confidence` does,
        # mind/memory_retrieval.py:743 -- would then read a hash vector as a
        # real one on the second run only. Legacy entries have no key and are
        # correctly False.
        return EmbeddingBatch(vectors=[vec], model_key=model_key,
                              dimensions=int(hit["dims"]),
                              fallback=bool(hit.get("fallback")))
    batch = embed_texts_meta([query])
    if batch.fallback and not allow_fallback:
        raise SystemExit(_FALLBACK_REFUSAL)
    vec = np.asarray(batch.vectors[0], dtype=np.float32)
    cache[key] = {"model_key": batch.model_key,
                  "dims": batch.dimensions,
                  "fallback": bool(batch.fallback),
                  "vec": base64.b64encode(vec.tobytes()).decode("ascii")}
    _save_qcache(cache_path, cache)
    return batch


def _prewarm_queries(paths, cache, cache_path, allow_fallback=False):
    """Embed every uncached probe query up front, in request-sized batches.

    `_embedded_batch` asks for one query at a time, which is right for a
    hand-authored bank of thirty probes and wrong for a borrowed benchmark of
    five hundred: each request pays a full round trip plus whatever the
    adaptive pacer has learned, so the instrument spends an hour doing a
    minute of work. Measured on the LongMemEval bank: 71 queries in the time
    the batched form needs for all 500.

    Scoring is untouched. This only fills the same disk cache
    `_embedded_batch` already reads, keyed identically, so a warmed run and a
    cold run produce byte-identical verdicts -- which is the property the
    frozen probe sets depend on.

    Batched by estimated tokens rather than count, for the reason UNBUILT 1.75
    records: a request refused for being too large is not retried into
    success, it is silently replaced by hash vectors.
    """
    from llm.providers import embed_texts_meta, embedding_model_key

    model_key = embedding_model_key()
    wanted, seen = [], set()
    for path in paths:
        for probe in json.loads(Path(path).read_text(encoding="utf-8"))["probes"]:
            text = probe["query"]
            key = _qkey(model_key, text)
            hit = cache.get(key)
            if (hit and hit.get("model_key") == model_key) or text in seen:
                continue
            seen.add(text)
            wanted.append(text)
    if not wanted:
        return 0

    import numpy as np

    done = 0
    batch, budget = [], 0
    def flush(group):
        nonlocal done
        if not group:
            return
        got = embed_texts_meta(group)
        if got.fallback and not allow_fallback:
            raise SystemExit(_FALLBACK_REFUSAL)
        for text, vec in zip(group, got.vectors):
            arr = np.asarray(vec, dtype=np.float32)
            cache[_qkey(got.model_key, text)] = {
                "model_key": got.model_key, "dims": got.dimensions,
                "fallback": bool(got.fallback),
                "vec": base64.b64encode(arr.tobytes()).decode("ascii")}
            done += 1
        _save_qcache(cache_path, cache)

    for text in wanted:
        cost = len(text) // 4
        if batch and budget + cost > 60_000:
            flush(batch)
            batch, budget = [], 0
        batch.append(text)
        budget += cost
    flush(batch)
    print(f"pre-embedded {done} probe queries")
    return done


def run_probe_file(path, k, cache, cache_path, allow_fallback=False):
    from core.db import q
    from mind import memory

    spec = json.loads(Path(path).read_text(encoding="utf-8"))
    bank = spec["bank"]
    chat_id, char_id = bank["chat_id"], bank["char_id"]
    row = q("SELECT MAX(turn_idx) mt, COUNT(*) n FROM memories "
            "WHERE chat_id=? AND char_id=?", (chat_id, char_id), one=True)
    if not row or not row["n"]:
        raise SystemExit(f"bank {chat_id}/{char_id} is empty in this database")
    cutoff = int(row["mt"]) + 1
    results = []
    fallback_queries = 0
    for probe in spec["probes"]:
        query = probe["query"]
        batch = _embedded_batch(query, cache, cache_path, allow_fallback)
        fallback_queries += bool(batch.fallback)
        returned = memory.search_memories(
            chat_id, char_id, query, k=k,
            current_turn_idx=cutoff, viewer_frame_id=None,
            chronological=False, embedded=batch, record_access=False)
        by_score = sorted(returned, key=lambda m: m["score"], reverse=True)
        ranks = {m["id"]: i + 1 for i, m in enumerate(by_score)}
        targets = set(probe.get("targets") or [])
        found = sorted(t for t in targets if t in ranks)
        neighbor_only = bool(found) and all(
            "chronological neighbor of recalled episode"
            in (by_score[ranks[t] - 1].get("retrieval_reasons") or [])
            for t in found)
        # ---- additive, and deliberately outside the pass rule ----------
        # `hit` above is the frozen verdict the committed probe sets were
        # measured on and must not move. These two answer questions membership
        # cannot: whether the CURRENT version of a revised fact outranks the
        # stale one, and whether what came back still knows how it was learned.
        anti = set(probe.get("antitargets") or [])
        anti_found = sorted(a for a in anti if a in ranks)
        best_target = min((ranks[t] for t in found), default=None)
        best_anti = min((ranks[a] for a in anti_found), default=None)
        # No antitarget in the payload is the cleanest pass: the stale row was
        # not offered at all. A target above every stale row is the next best.
        revision_correct = (None if not anti else
                            best_target is not None
                            and (best_anti is None or best_target < best_anti))
        want_prov = probe.get("expect_provenance")
        top_prov = None
        if best_target is not None:
            top_prov = (by_score[best_target - 1] or {}).get("provenance")
        entry = {
            "id": probe["id"],
            "kind": probe.get("kind", "positive"),
            "hit": bool(found),
            "targets_found": found,
            "target_ranks": {str(t): ranks[t] for t in found},
            "antitargets_found": anti_found,
            "antitarget_ranks": {str(a): ranks[a] for a in anti_found},
            "revision_correct": revision_correct,
            "expect_provenance": want_prov,
            "top_target_provenance": top_prov,
            "provenance_ok": (None if not want_prov else top_prov == want_prov),
            "neighbor_only": neighbor_only,
            "returned_ids": [m["id"] for m in by_score],
            "returned_scores": [round(m["score"], 6) for m in by_score],
        }
        # Additive display of a production abstention signal if one exists;
        # the frozen pass rule above does not depend on it.
        conf_fn = getattr(memory, "recall_confidence", None)
        if callable(conf_fn):
            try:
                entry["recall_confidence"] = conf_fn(
                    chat_id, char_id, query, current_turn_idx=cutoff,
                    viewer_frame_id=None, embedded=batch)
            except Exception as exc:  # pragma: no cover - display only
                entry["recall_confidence_error"] = str(exc)
        results.append(entry)
    positives = [r for r in results if r["kind"] == "positive"]
    negatives = [r for r in results if r["kind"] == "negative"]
    summary = {
        "bank": bank,
        "probe_file": str(path),
        "k": k,
        # Provenance, not decoration: a stored report must say on its face
        # which retriever produced it, or a null-control arm reads later as a
        # production number.
        "query_model": _query_model_key(),
        "fallback_queries": fallback_queries,
        "positives": {"hits": sum(r["hit"] for r in positives),
                      "total": len(positives),
                      "misses": [r["id"] for r in positives if not r["hit"]]},
        "negatives": {"total": len(negatives)},
        # Two sub-scores the frozen pass rule cannot express. `revision` is
        # only defined for probes carrying antitargets, `provenance` only for
        # probes carrying `expect_provenance`; both are absent, not zero, on a
        # probe set that has neither.
        "revision": {
            "checked": sum(1 for r in results if r.get("revision_correct") is not None),
            "correct": sum(1 for r in results if r.get("revision_correct") is True),
            "stale_outranked_current": [
                r["id"] for r in results if r.get("revision_correct") is False],
        },
        "provenance": {
            "checked": sum(1 for r in results if r.get("provenance_ok") is not None),
            "correct": sum(1 for r in results if r.get("provenance_ok") is True),
            "wrong": [r["id"] for r in results if r.get("provenance_ok") is False],
        },
        "probes": results,
    }
    return summary


def _query_model_key():
    from llm.providers import embedding_model_key
    return embedding_model_key()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--probes", action="append", required=True)
    parser.add_argument("--k", type=int, default=16)
    parser.add_argument("--label", default="")
    parser.add_argument("--out")
    parser.add_argument("--qcache", default=_QCACHE_DEFAULT)
    parser.add_argument(
        "--allow-fallback-queries", action="store_true",
        help="score with crc32 hash query vectors instead of refusing. For a "
             "DECLARED null-control arm only: the result is a lexical floor, "
             "not a production retrieval number, and is stamped as such.")
    args = parser.parse_args()
    if not os.environ.get("ENGINE_DB"):
        raise SystemExit("set ENGINE_DB to a COPY of the database first")
    if args.allow_fallback_queries:
        print("*** --allow-fallback-queries: crc32 hash query vectors are "
              "permitted. This arm measures a LEXICAL FLOOR, not production "
              "retrieval. ***")
    cache = _load_qcache(args.qcache)
    _prewarm_queries(args.probes, cache, args.qcache,
                     args.allow_fallback_queries)
    report = {"label": args.label,
              "db": os.environ["ENGINE_DB"],
              "allow_fallback_queries": bool(args.allow_fallback_queries),
              "banks": [run_probe_file(p, args.k, cache, args.qcache,
                                       args.allow_fallback_queries)
                        for p in args.probes]}
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    for bank in report["banks"]:
        pos = bank["positives"]
        print(f"{bank['bank']['label']}: {pos['hits']}/{pos['total']} "
              f"positive probes hit at k={bank['k']} "
              f"[{bank['query_model']}"
              + (f", {bank['fallback_queries']} fallback queries]"
                 if bank["fallback_queries"] else "]")
              + (f"; misses: {', '.join(pos['misses'])}" if pos["misses"]
                 else ""))
    if args.out:
        print(f"full report: {args.out}")


if __name__ == "__main__":
    main()
