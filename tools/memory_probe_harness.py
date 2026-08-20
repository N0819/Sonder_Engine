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


def _embedded_batch(query, cache, cache_path):
    """One EmbeddingBatch for one query, disk-cached by (model, text)."""
    import numpy as np
    from llm.providers import EmbeddingBatch, embed_texts_meta, embedding_model_key

    model_key = embedding_model_key()
    key = _qkey(model_key, query)
    hit = cache.get(key)
    if hit and hit.get("model_key") == model_key:
        vec = np.frombuffer(base64.b64decode(hit["vec"]), dtype=np.float32)
        return EmbeddingBatch(vectors=[vec], model_key=model_key,
                              dimensions=int(hit["dims"]), fallback=False)
    batch = embed_texts_meta([query])
    if batch.fallback:
        raise SystemExit(
            "refusing to score with a fallback (lexical hash) query "
            "embedding — the instrument would measure a different retrieval "
            "than production. Configure the embeddings provider.")
    vec = np.asarray(batch.vectors[0], dtype=np.float32)
    cache[key] = {"model_key": batch.model_key,
                  "dims": batch.dimensions,
                  "vec": base64.b64encode(vec.tobytes()).decode("ascii")}
    _save_qcache(cache_path, cache)
    return batch


def run_probe_file(path, k, cache, cache_path):
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
    for probe in spec["probes"]:
        query = probe["query"]
        batch = _embedded_batch(query, cache, cache_path)
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
        entry = {
            "id": probe["id"],
            "kind": probe.get("kind", "positive"),
            "hit": bool(found),
            "targets_found": found,
            "target_ranks": {str(t): ranks[t] for t in found},
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
        "positives": {"hits": sum(r["hit"] for r in positives),
                      "total": len(positives),
                      "misses": [r["id"] for r in positives if not r["hit"]]},
        "negatives": {"total": len(negatives)},
        "probes": results,
    }
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--probes", action="append", required=True)
    parser.add_argument("--k", type=int, default=16)
    parser.add_argument("--label", default="")
    parser.add_argument("--out")
    parser.add_argument("--qcache", default=_QCACHE_DEFAULT)
    args = parser.parse_args()
    if not os.environ.get("ENGINE_DB"):
        raise SystemExit("set ENGINE_DB to a COPY of the database first")
    cache = _load_qcache(args.qcache)
    report = {"label": args.label,
              "db": os.environ["ENGINE_DB"],
              "banks": [run_probe_file(p, args.k, cache, args.qcache)
                        for p in args.probes]}
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    for bank in report["banks"]:
        pos = bank["positives"]
        print(f"{bank['bank']['label']}: {pos['hits']}/{pos['total']} "
              f"positive probes hit at k={bank['k']}"
              + (f"; misses: {', '.join(pos['misses'])}" if pos["misses"]
                 else ""))
    if args.out:
        print(f"full report: {args.out}")


if __name__ == "__main__":
    main()
