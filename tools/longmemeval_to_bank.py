#!/usr/bin/env python3
"""Convert LongMemEval into a Sonder memory bank plus a frozen probe file.

Every retrieval number this project has is measured against probes written by
someone who had already read the rows they target (AUDIT_MEMORY.md section 3,
MEMORY_IMPROVEMENTS.md section 1).  That is a real thumb on the scale: the
question's vocabulary was chosen knowing the answer's vocabulary, and no amount
of authoring discipline removes the fact that the same head held both.
LongMemEval was built by people who have never seen this engine, so its
questions are independent by construction rather than by intention.

Source: https://github.com/xiaowu0162/LongMemEval (ICLR 2025), redistributed on
HuggingFace as `xiaowu0162/longmemeval-cleaned` under the MIT licence.  Nothing
from it is vendored here -- `tools/fetch_longmemeval.py` downloads it to a
scratch path and this tool reads it from there.

What it is worth, and what it is not:

- It is a strong test of the RANKING machinery.  Paraphrase recall, temporal
  reasoning, knowledge updates and multi-session fusion are all present, in
  quantities this project cannot hand-author.
- It carries **30 abstention questions with ground truth** -- questions whose
  answers are genuinely absent from the history.  `recall_confidence` is
  currently calibrated against fifteen hand-made negatives and catches none of
  them; this is the first independent test that signal has ever had.
- It is a WEAK test of everything the firewall touches.  The corpus is
  task-oriented user/assistant chat, so nothing in it was witnessed in the
  sense this engine means, and the provenance mapping below is an analogy
  rather than a reconstruction.  A good score here does not say characters
  recall well.  A bad one does say something is wrong.

**All records are merged into ONE bank**, rather than the benchmark's own
one-haystack-per-question layout.  Two reasons, and the second matters more:
it turns a 494-rows-per-probe ratio into roughly 22, and it makes every other
record's history into distractor material for this record's question --
topically diverse, identical in register, and far larger than any bank the
live corpus contains (10,960 rows against a real-world maximum of 657).
Sessions stay contiguous within a record so that within-record chronology,
which the temporal-reasoning questions depend on, survives the merge.

Provenance mapping, stated so nobody mistakes it for a claim about the data:
an `assistant` turn becomes `witnessed` (the speaker's own conduct) and a
`user` turn becomes `told` (something said to them).  That exercises the
scoped-summary machinery honestly without pretending the corpus has a
perception layer.

Runs against a COPY of a configured database, never a fresh one -- see
`_refuse_fallback_embeddings` for why that is not merely convenient. The new
bank gets its own `chats` and `characters` rows; nothing existing is touched.

Usage:
    python3 tools/fetch_longmemeval.py --out /tmp/lme
    cp engine.db /tmp/lme/bank.db
    ENGINE_DB=/tmp/lme/bank.db python3 tools/longmemeval_to_bank.py \\
        --source /tmp/lme/longmemeval_oracle.json \\
        --out-probes tools/memory_probes/longmemeval_merged.json

Then measure with the ordinary instrument:
    ENGINE_DB=/tmp/lme/bank.db python3 tools/memory_probe_harness.py \\
        --probes tools/memory_probes/longmemeval_merged.json --label lme
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# A row this long is unlike anything the live corpus holds (mean 1,206 chars
# against a live median far below it).  The full text is stored, because
# truncating it would silently change what retrieval is scored on; the gist
# is what gets shortened, which is what a gist is for.
GIST_CHARS = 240

# The embeddings provider caps a request at 120,000 tokens. A batch is TWO
# texts per row (document and cues), and LongMemEval rows are far longer than
# anything this engine mints -- mean 1,206 characters against a live median
# well below it -- so a row-counted batch overshoots on this corpus while
# looking reasonable on ours. Measured: 256 rows produced a 120,817-token
# request, the provider returned 400, and `embed_texts_meta` fell back to
# crc32 for 491 texts and let the write proceed. Budget tokens, not rows, and
# leave half the cap as headroom for the estimate being wrong.
EMBED_TOKEN_BUDGET = 60_000
CHARS_PER_TOKEN = 4


def _refuse_live_database():
    """The harness's rule, restated here because this tool WRITES.

    `memory_probe_harness.py` only reads and still refuses the live file. This
    one inserts eleven thousand rows, so the check is not a formality.
    """
    target = os.environ.get("ENGINE_DB", "")
    if not target:
        raise SystemExit(
            "set ENGINE_DB to a scratch path -- this tool creates a database")
    resolved = Path(target).expanduser().resolve()
    repo_db = (Path(__file__).resolve().parents[1] / "engine.db").resolve()
    if resolved == repo_db:
        raise SystemExit(
            f"refusing to write the live database at {repo_db}. "
            "Point ENGINE_DB at a scratch path.")


def _refuse_fallback_embeddings():
    """Fail before writing anything if embeddings are not really configured.

    One probe text through the production seam. Cheap, and it turns a corpus
    that is silently worthless into an error at second zero.

    This guard is the reason the tool runs against a COPY of a configured
    database rather than a database it creates itself. A fresh `db.init()`
    has no providers and no `agent_models`, so the embeddings role resolves to
    nothing and `embed_texts_meta` returns crc32 lexical hashes -- and nothing
    on the write path objects, because `prepare_memories_batch` embeds whatever
    it is handed. Measured: the first run of this tool wrote 561 rows of hash
    vectors and reported success. The harness refuses fallback QUERY vectors
    for the same reason; the corpus side had no such guard, which is how this
    was found.
    """
    from llm.providers import embed_texts_meta
    batch = embed_texts_meta(["retrieval configuration probe"])
    if batch.fallback:
        raise SystemExit(
            "embeddings resolved to the crc32 fallback -- every row would be "
            "written with a lexical hash vector and the bank would measure a "
            "retrieval nobody runs. Check --seed-config-from.")
    return batch.model_key, batch.dimensions


def _seed_bank(db, label):
    """A chat and a character row, so the bank has the identities its rows
    reference and the ordinary read paths work unmodified."""
    now = time.time()
    chat_id = db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        (label, "", now))
    char_id = db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("LongMemEval Speaker", json.dumps({}), "{}", now))
    return chat_id, char_id


def _rows_for_record(record, chat_id, char_id, turn_base):
    """One memory row per haystack turn, in order.

    Returns (rows, evidence_positions) where evidence_positions indexes into
    rows -- the row ids do not exist until the batch is written, so targets
    are resolved by position afterwards.
    """
    rows, evidence = [], []
    idx = turn_base
    for session in record["haystack_sessions"]:
        for turn in session:
            role = turn.get("role")
            content = (turn.get("content") or "").strip()
            if not content:
                continue
            if turn.get("has_answer"):
                evidence.append(len(rows))
            rows.append({
                "chat_id": chat_id,
                "char_id": char_id,
                "turn_id": None,
                "kind": "episodic",
                "category": "episode",
                # An analogy, not a reconstruction -- see the module docstring.
                "provenance": "witnessed" if role == "assistant" else "told",
                "salience": 0.5,
                "content": content,
                "gist": content[:GIST_CHARS],
                "turn_idx": idx,
            })
            idx += 1
    return rows, evidence, idx


def _probe_for_record(record, target_ids, turn_span):
    """A record's question becomes one probe.

    A `_abs` question id marks an abstention record: the benchmark asserts the
    answer is absent, which is exactly this harness's `negative` kind. Those
    are the reason this conversion is worth doing at all.
    """
    qid = record["question_id"]
    negative = qid.endswith("_abs")
    return {
        "id": qid,
        "kind": "negative" if negative else "positive",
        "query": record["question"],
        "targets": [] if negative else sorted(target_ids),
        "target_turns": turn_span,
        "note": (f"{record.get('question_type')} | "
                 + ("answer absent by construction (LongMemEval abstention "
                    "record)" if negative
                    else f"expected answer: {str(record.get('answer'))[:120]}")),
    }


def convert(source, out_probes, limit, batch_size, label):
    from core import db
    from mind.memory_write import add_memories_batch, prepare_memories_batch

    records = json.loads(Path(source).read_text(encoding="utf-8"))
    if limit:
        records = records[:limit]

    db.init()
    model_key, dims = _refuse_fallback_embeddings()
    print(f"embeddings: {model_key} ({dims}d)")
    chat_id, char_id = _seed_bank(db, label)

    pending, pending_meta, probes = [], [], []
    written = 0
    turn_cursor = 0

    def flush():
        """Embed and write one batch, then resolve each record's targets.

        Batched deliberately: `prepare_memories_batch` embeds outside any write
        lock, which is the same ordering the turn commit path uses.
        """
        nonlocal pending, pending_meta, written
        if not pending:
            return
        prepared = prepare_memories_batch(pending)
        # The up-front probe proves the provider is CONFIGURED; it cannot
        # prove every later request succeeds. A batch that overshoots the
        # request cap comes back fallback-stamped with only a log line, and
        # the write path is happy to store it -- so refuse here instead. The
        # rows already committed stay; the run stops rather than quietly
        # producing a bank that is half real vectors and half crc32.
        batch = prepared.get("embedded")
        if batch is not None and getattr(batch, "fallback", False):
            raise SystemExit(
                f"embedding fell back to crc32 after {written} rows -- the "
                f"batch of {len(pending)} rows was refused by the provider. "
                f"Lower --batch-size (currently {batch_size} estimated "
                f"tokens) and start a fresh bank; this one is now mixed.")
        ids = add_memories_batch(prepared_batch=prepared)
        written += len(ids)
        for rec, start, count, evidence, span in pending_meta:
            target_ids = [ids[start + e] for e in evidence
                          if start + e < len(ids)]
            probes.append(_probe_for_record(rec, target_ids, span))
        pending, pending_meta = [], []
        print(f"  wrote {written} rows, {len(probes)} probes", flush=True)

    pending_tokens = 0
    for rec in records:
        rows, evidence, turn_cursor = _rows_for_record(
            rec, chat_id, char_id, turn_cursor)
        if not rows:
            continue
        span = [rows[0]["turn_idx"], rows[-1]["turn_idx"]]
        # Two embedded texts per row, so the estimate doubles.
        cost = 2 * sum(len(r["content"]) for r in rows) // CHARS_PER_TOKEN
        # A record is never split across batches: its targets are resolved
        # from one id list, and a split would strand half of them.
        if pending and (pending_tokens + cost > batch_size
                        or len(pending) >= 512):
            flush()
            pending_tokens = 0
        pending_meta.append((rec, len(pending), len(rows), evidence, span))
        pending.extend(rows)
        pending_tokens += cost
    flush()

    positives = [p for p in probes if p["kind"] == "positive"]
    negatives = [p for p in probes if p["kind"] == "negative"]
    empty = [p["id"] for p in positives if not p["targets"]]

    spec = {
        "bank": {"chat_id": chat_id, "char_id": char_id,
                 "label": f"LongMemEval merged ({written} rows)"},
        "authored": time.strftime("%Y-%m-%d"),
        "note": (
            "Derived from LongMemEval (MIT, xiaowu0162/longmemeval-cleaned) by "
            "tools/longmemeval_to_bank.py. Questions are INDEPENDENT of this "
            "engine: nobody who wrote them has seen its retrieval. All records "
            "merged into one bank so every other record's history is a "
            "distractor. Negative probes are the benchmark's own abstention "
            "records, whose answers are absent by construction -- the first "
            "independent test recall_confidence has had."),
        "probes": probes,
    }
    Path(out_probes).write_text(
        json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"\nbank {chat_id}/{char_id}: {written} rows")
    print(f"probes: {len(positives)} positive, {len(negatives)} negative")
    if empty:
        # Not fatal, and worth printing: a positive with no resolvable target
        # can never hit, so it would silently depress the score.
        print(f"WARNING {len(empty)} positive probes have no evidence row "
              f"and can never hit: {', '.join(empty[:5])}"
              + (" ..." if len(empty) > 5 else ""))
    print(f"probe file: {out_probes}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True,
                    help="longmemeval_oracle.json or longmemeval_s_cleaned.json")
    ap.add_argument("--out-probes", required=True)
    ap.add_argument("--limit", type=int, default=0,
                    help="convert only the first N records (0 = all)")
    ap.add_argument("--batch-size", type=int, default=EMBED_TOKEN_BUDGET,
                    help="estimated TOKENS per embedding request group, not "
                         f"rows (default {EMBED_TOKEN_BUDGET})")
    ap.add_argument("--label", default="LongMemEval merged bank")
    args = ap.parse_args()
    _refuse_live_database()
    convert(args.source, args.out_probes, args.limit, args.batch_size,
            args.label)


if __name__ == "__main__":
    main()
