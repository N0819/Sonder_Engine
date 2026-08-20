#!/usr/bin/env python3
"""Score the crc32 fallback at several sketch widths, on one probe file.

`providers.cheap_embed` hashes character 3- and 4-grams into **256** signed
buckets. That width is a bare default: it is argued for nowhere in the
codebase, and `_embed_with_retry` hard-codes it twice more (the stamp
`cheap:crc32:256` and `dimensions=256`), so it cannot be varied through the
provider seam at all. This measures what it costs.

Substitutes exactly ONE thing: the embedder. The stored documents, the
production `search_memories` seam and `memory_probe_harness`'s frozen pass
rule are untouched. Rows are rebuilt with the same document construction
`memory_vectors.rebuild_embeddings` uses and stamped `cheap:crc32:<width>`, so
a row and a query are comparable exactly when they were made at the same
width -- the rule already in the schema, which is also why widening is a free
migration: every existing hash row reads as stale the moment the width moves.

Width **0** is the arm below the fallback: the query is stamped with a key no
row carries, so both vector rankings score 0.0 for the whole bank
(`mind/memory_retrieval.py:453` drops non-positive scores from the rank lists)
and only BM25 plus exact-cue reach anything. It is the only way to see whether
the hash vector is contributing or subtracting, and on the LongMemEval bank it
was the arm that answered the question (docs/experiments/CRC32_CONTROL.md).

Runs against a COPY of a populated database, which it REWRITES: every pass
overwrites `memories.embedding`/`cue_embedding` for the probed bank. Never
point ENGINE_DB at a database anybody wants to keep.

Usage:
    ENGINE_DB=/tmp/copy.db python3 tools/cheap_embed_width_sweep.py \\
        --probes tools/memory_probes/longmemeval_merged.json \\
        --widths 0 256 1024 4096 16384 --out-dir /tmp/sweep
"""

import argparse
import json
import os
import sys
import time
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np


def ngram_hashes(text):
    """The exact crc32 sequence `cheap_embed` consumes, in the same order.

    Character slicing (not byte slicing) and the `len(t) - n` bound are
    reproduced literally, off-by-one included: `cheap_embed` drops the final
    n-gram of every text, and a control that kept it would be measuring a
    different function. `--verify` asserts the equality rather than trusting
    this paragraph.
    """
    t = " " + (text or "").lower() + " "
    out = []
    for n in (3, 4):
        for i in range(max(len(t) - n, 0)):
            out.append(zlib.crc32(t[i:i + n].encode("utf-8", "ignore")))
    return np.asarray(out, dtype=np.int64)


def sketch_from_hashes(h, dim):
    if h.size == 0:
        return np.zeros(dim, dtype=np.float32)
    signs = np.where((h >> 16) & 1, 1.0, -1.0)
    v = np.bincount(h % dim, weights=signs, minlength=dim).astype(np.float32)
    norm = float(np.linalg.norm(v))
    return v / norm if norm > 0 else v


def sketch(text, dim):
    return sketch_from_hashes(ngram_hashes(text), dim)


def verify_against_cheap_embed(texts):
    """Largest absolute disagreement with `cheap_embed` at its own width."""
    from llm.providers import cheap_embed
    worst = 0.0
    for text in texts:
        worst = max(worst, float(np.abs(
            np.asarray(cheap_embed(text), dtype=np.float32)
            - sketch(text, 256)).max()))
    return worst


def rebuild(chat_id, char_id, width, batch=500):
    """Re-embed the bank at `width`, stamped `cheap:crc32:<width>`."""
    from core.db import q, qi, transaction
    from mind.memory_common import _blob
    from mind.memory_write import _memory_cues, _memory_document, _row_memory

    started = time.time()
    rows = q("SELECT * FROM memories WHERE chat_id=? AND char_id=? ORDER BY id",
             (chat_id, char_id))
    key, done, pending = f"cheap:crc32:{width}", 0, []

    def flush():
        nonlocal done, pending
        if not pending:
            return
        with transaction():
            for args in pending:
                qi("UPDATE memories SET embedding=?,cue_embedding=?,"
                   "embedding_model=?,embedding_dim=? WHERE id=?", args)
        done += len(pending)
        pending = []

    for row in rows:
        mem = _row_memory(row)
        doc = _memory_document(mem)
        cue = _memory_cues(mem) or doc
        pending.append((_blob(sketch(doc, width)), _blob(sketch(cue, width)),
                        key, width, row["id"]))
        if len(pending) >= batch:
            flush()
    flush()
    return done, time.time() - started


def score(probe_file, width, k, out_dir, label_width):
    """One harness pass with the embedder replaced by the sketch at `width`."""
    import llm.providers as providers
    from llm.providers import EmbeddingBatch
    import tools.memory_probe_harness as harness

    key = f"cheap:crc32:{label_width}"
    providers.embedding_model_key = lambda: key
    providers.embed_texts_meta = lambda texts, retry=None: EmbeddingBatch(
        vectors=[sketch(t, width) for t in texts], model_key=key,
        dimensions=width, fallback=True, error="declared crc32 control arm")

    started = time.time()
    report = harness.run_probe_file(
        probe_file, k, {}, str(Path(out_dir) / f"qcache_{label_width}.json"),
        allow_fallback=True)
    report["elapsed_s"] = round(time.time() - started, 1)
    Path(out_dir, f"width_{label_width}.json").write_text(
        json.dumps(report, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--probes", required=True)
    parser.add_argument("--widths", type=int, nargs="+",
                        default=[0, 256, 1024, 4096, 16384])
    parser.add_argument("--k", type=int, default=16)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--verify", action="store_true",
                        help="assert the sketch equals cheap_embed at 256 "
                             "on this bank's own documents, then continue")
    args = parser.parse_args()
    if not os.environ.get("ENGINE_DB"):
        raise SystemExit("set ENGINE_DB to a COPY of the database first — "
                         "this tool REWRITES the probed bank's vectors")
    Path(args.out_dir).mkdir(parents=True, exist_ok=True)

    from core.db import q
    bank = json.loads(Path(args.probes).read_text(encoding="utf-8"))["bank"]
    chat_id, char_id = bank["chat_id"], bank["char_id"]

    if args.verify:
        rows = q("SELECT content, gist FROM memories WHERE chat_id=? AND "
                 "char_id=? ORDER BY id LIMIT 200", (chat_id, char_id))
        texts = [r["content"] for r in rows] + [r["gist"] for r in rows]
        worst = verify_against_cheap_embed(texts)
        print(f"max |sketch(t,256) - cheap_embed(t)| over {len(texts)} "
              f"documents: {worst:g}")
        assert worst == 0.0, "the control is not the function it controls for"

    for width in args.widths:
        if width == 0:
            # No rebuild: the rows keep whatever stamp they have and the
            # query claims a width nothing carries, so the vector rankings
            # come back empty and BM25 + exact cue run alone.
            report = score(args.probes, 256, args.k, args.out_dir, 0)
            print(f"no vector channel: {report['positives']['hits']}/"
                  f"{report['positives']['total']} in {report['elapsed_s']}s")
            continue
        done, secs = rebuild(chat_id, char_id, width)
        report = score(args.probes, width, args.k, args.out_dir, width)
        print(f"width {width}: {report['positives']['hits']}/"
              f"{report['positives']['total']} "
              f"(rebuilt {done} rows in {secs:.1f}s, "
              f"scored in {report['elapsed_s']}s)")


if __name__ == "__main__":
    main()
