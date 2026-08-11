"""Perception quality baseline — Metric B: retrieval discrimination.

The composer's main risk is that episodic memory (minted verbatim from view
prose at commit time) loses embedding discrimination if views become
templates. This module establishes the BASELINE the composer must beat, from
the stored corpus:

  * view template statistics — first-sentence uniqueness, verbatim-duplicate
    sentence rate, most common openings;
  * memory-bank statistics over the episodic banks the engine actually
    minted — verbatim-twin rate, and (from the STORED embeddings, which are
    real play-time vectors) pairwise cosine spread and the near-duplicate
    collision rate at a stated threshold;
  * lexical-proxy self-retrieval MRR: querying with a turn's stored view,
    does the memory minted from that view outrank the rest of the bank?
    Ties are ranked pessimistically, because a bank of verbatim twins IS the
    discrimination failure being measured.

Embedding availability, stated plainly: the corpus embeddings were produced
by an online provider model (see `embedding_models` in the output). That
model is NOT available offline, so this module (a) uses the stored vectors
as-is for spread/collision — no new embeddings needed — and (b) provides a
lexical proxy for query-side metrics, plus `embed_texts_hook`, the clearly
marked seam where a real embedding call plugs in when a provider is
configured. Composer-vs-baseline comparisons must use the same leg on both
sides (stored-vector metrics against stored-vector metrics, lexical against
lexical).

The database is opened read-only; `search_memories` is never called (it
writes access_count), so no copy is required.

Run:
    python tools/perception_retrieval.py --db /path/to/engine.db
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

PERCEPTION_KEYS = ("perception_establish", "perception_act",
                   "perception_outcome")
EPISODIC_KINDS = ("episodic", "episode")
COLLISION_THRESHOLD = 0.95   # stated: cosine >= this to a neighbor collides
MAX_BANK_FOR_PAIRWISE = 1500  # sample cap per bank for O(n^2) cosine work
MRR_QUERY_CAP = 800           # seeded sample cap for lexical MRR queries

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])[\"”']?\s+")


def sentences(text):
    return [s.strip() for s in _SENTENCE_SPLIT.split(str(text or "").strip())
            if s.strip()]


# --------------------------------------------------------------------------
# Lexical proxy — deterministic, offline
# --------------------------------------------------------------------------

def _trigrams(text):
    text = re.sub(r"\s+", " ", str(text or "").casefold()).strip()
    if len(text) < 3:
        return Counter([text] if text else [])
    return Counter(text[i:i + 3] for i in range(len(text) - 2))


def trigram_cosine(a, b):
    """Character-trigram cosine similarity: the lexical stand-in for
    embedding cosine when no embedding model is reachable. 1.0 for verbatim
    twins, ~0 for unrelated prose."""
    ca, cb = _trigrams(a), _trigrams(b)
    if not ca or not cb:
        return 0.0
    dot = sum(v * cb[k] for k, v in ca.items() if k in cb)
    na = math.sqrt(sum(v * v for v in ca.values()))
    nb = math.sqrt(sum(v * v for v in cb.values()))
    return dot / (na * nb) if na and nb else 0.0


def pessimistic_rank(scores, target_index):
    """Rank of `target_index` in `scores` (higher = better) with every tie
    counted AGAINST the target. A verbatim twin therefore outranks its
    original — which is the retrieval failure this metric exists to expose."""
    target = scores[target_index]
    better_or_equal = sum(1 for i, s in enumerate(scores)
                          if i != target_index and s >= target)
    return 1 + better_or_equal


def embed_texts_hook(texts, model_id=None):
    """HOOK — the seam for real embeddings when a provider is configured.

    The corpus vectors were minted by an online provider model; there is no
    offline equivalent here, so this deliberately refuses rather than
    silently substituting a different space. To activate: implement this via
    `providers.py` with the SAME model id recorded in the corpus rows
    (memories.embedding_model), and re-run the query-side metrics on both
    the baseline and the composer bank with it.
    """
    raise RuntimeError(
        "No offline embedding model is available. Corpus embeddings were "
        "minted by an online provider "
        f"({model_id or 'see the embedding_model column'}); wire this hook "
        "through providers.py with that exact model before trusting "
        "embedding-space query metrics.")


# --------------------------------------------------------------------------
# View template statistics
# --------------------------------------------------------------------------

def view_template_stats(con):
    rows = con.execute(
        "SELECT s.key, s.turn_id, v.content FROM steps s "
        "JOIN variants v ON v.step_id = s.id AND v.active = 1 "
        "WHERE s.stale = 0 AND s.key IN (?,?,?)", PERCEPTION_KEYS).fetchall()
    views = []
    for key, turn_id, content in rows:
        try:
            data = json.loads(content)
        except Exception:
            continue
        for view in (data.get("views") or {}).values():
            if view and str(view).strip():
                views.append(str(view))
    first_sentences = Counter()
    all_sentences = Counter()
    openings = Counter()
    for view in views:
        parts = sentences(view)
        if parts:
            first_sentences[parts[0]] += 1
            openings[parts[0]] += 1
        for part in parts:
            all_sentences[part] += 1
    total_views = len(views)
    dup_first = sum(n for n in first_sentences.values() if n > 1)
    total_sentences = sum(all_sentences.values())
    dup_sentences = sum(n for n in all_sentences.values() if n > 1)
    top = openings.most_common(1)
    return {
        "views_total": total_views,
        "first_sentence_not_unique": dup_first,
        "first_sentence_not_unique_pct":
            round(100 * dup_first / total_views, 1) if total_views else None,
        "sentences_total": total_sentences,
        "sentences_duplicated_verbatim": dup_sentences,
        "sentences_duplicated_verbatim_pct":
            round(100 * dup_sentences / total_sentences, 1)
            if total_sentences else None,
        "top_opening_count": top[0][1] if top else 0,
        # content-restraint: only this one known-boilerplate opening is quoted
        "top_opening_is_unspecified_area":
            bool(top and top[0][0].startswith("You are in an unspecified")),
        "distinct_openings": len(openings),
    }


# --------------------------------------------------------------------------
# Memory-bank statistics
# --------------------------------------------------------------------------

def _decode_embedding(blob, dim):
    try:
        import numpy as np
    except Exception:
        return None
    if not blob:
        return None
    vec = np.frombuffer(blob, dtype=np.float32)
    if dim and len(vec) != dim:
        return None
    return vec


def memory_bank_stats(con, threshold=COLLISION_THRESHOLD, seed=42):
    try:
        import numpy as np
    except Exception:
        np = None
    marks = ",".join("?" for _ in EPISODIC_KINDS)
    rows = con.execute(
        f"SELECT chat_id, char_id, turn_idx, content, embedding, "
        f"embedding_dim, embedding_model FROM memories "
        f"WHERE kind IN ({marks}) AND archived IS NOT 1",
        EPISODIC_KINDS).fetchall()
    banks = defaultdict(list)
    models = Counter()
    global_contents = Counter()
    unspecified = 0
    for chat_id, char_id, turn_idx, content, emb, dim, model in rows:
        banks[(chat_id, char_id)].append((turn_idx, content or "", emb, dim))
        models[model] += 1
        global_contents[str(content or "").strip()] += 1
        if str(content or "").strip() == "You are in an unspecified area.":
            unspecified += 1
    rng = random.Random(seed)
    total_rows = len(rows)
    twin_rows = 0
    collision_rows = 0
    collision_deno = 0
    spread_terms = []  # (bank_mean_pairwise_cosine, n_pairs)
    for (chat_id, char_id), items in banks.items():
        contents = Counter(str(c or "").strip() for _, c, _, _ in items)
        twin_rows += sum(n for n in contents.values() if n > 1)
        if np is None:
            continue
        vecs = []
        sample = items if len(items) <= MAX_BANK_FOR_PAIRWISE else \
            rng.sample(items, MAX_BANK_FOR_PAIRWISE)
        for _, _, emb, dim in sample:
            vec = _decode_embedding(emb, dim)
            if vec is not None:
                vecs.append(vec)
        if len(vecs) < 2:
            continue
        matrix = np.stack(vecs)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        matrix = matrix / norms
        sims = matrix @ matrix.T
        n = len(vecs)
        upper = sims[np.triu_indices(n, k=1)]
        spread_terms.append((float(upper.mean()), len(upper)))
        np.fill_diagonal(sims, -1.0)
        collision_rows += int((sims.max(axis=1) >= threshold).sum())
        collision_deno += n
    weighted_spread = None
    if spread_terms:
        total_pairs = sum(n for _, n in spread_terms)
        weighted_spread = round(
            sum(m * n for m, n in spread_terms) / total_pairs, 4)
    return {
        "episodic_rows": total_rows,
        "banks": len(banks),
        "embedding_models": dict(models),
        "verbatim_twin_rows_within_bank": twin_rows,
        "verbatim_twin_rate_within_bank_pct":
            round(100 * twin_rows / total_rows, 1) if total_rows else None,
        "verbatim_twin_rows_global": sum(
            n for n in global_contents.values() if n > 1),
        "verbatim_twin_rate_global_pct": round(
            100 * sum(n for n in global_contents.values() if n > 1)
            / total_rows, 1) if total_rows else None,
        "unspecified_area_exact_rows": unspecified,
        "collision_threshold": threshold,
        "collision_rows": collision_rows,
        "collision_rate_pct":
            round(100 * collision_rows / collision_deno, 1)
            if collision_deno else None,
        "collision_rows_measured": collision_deno,
        "mean_pairwise_cosine": weighted_spread,
        "numpy_available": np is not None,
    }


# --------------------------------------------------------------------------
# Lexical self-retrieval MRR over the real minted banks
# --------------------------------------------------------------------------

def lexical_self_retrieval_mrr(con, cap=MRR_QUERY_CAP, seed=42):
    """For memories whose source view is identifiable (same chat, char and
    turn_idx as a stored perception view for that character), query the bank
    with the VIEW text and rank memory contents by trigram cosine. Reports
    tie-pessimistic MRR and the share of queries where a twin displaced the
    target — the discrimination number a composer bank must beat."""
    marks = ",".join("?" for _ in EPISODIC_KINDS)
    mem_rows = con.execute(
        f"SELECT id, chat_id, char_id, turn_idx, content FROM memories "
        f"WHERE kind IN ({marks}) AND archived IS NOT 1 "
        f"AND char_id IS NOT NULL AND turn_idx IS NOT NULL",
        EPISODIC_KINDS).fetchall()
    banks = defaultdict(list)
    for mid, chat_id, char_id, turn_idx, content in mem_rows:
        banks[(chat_id, char_id)].append((mid, turn_idx, str(content or "")))

    view_rows = con.execute(
        "SELECT t.chat_id, t.idx, v.content FROM steps s "
        "JOIN variants v ON v.step_id = s.id AND v.active = 1 "
        "JOIN turns t ON t.id = s.turn_id "
        "WHERE s.stale = 0 AND s.key IN ('perception_outcome',"
        "'perception_act','perception_establish')").fetchall()
    views = {}  # (chat_id, char_key, turn_idx) -> view text (outcome wins)
    for chat_id, turn_idx, content in view_rows:
        try:
            data = json.loads(content)
        except Exception:
            continue
        for key, view in (data.get("views") or {}).items():
            if not view or not str(key).isdigit():
                continue
            views.setdefault((chat_id, int(key), turn_idx), str(view))

    candidates = []
    for (chat_id, char_id), items in banks.items():
        if len(items) < 3:
            continue
        for mid, turn_idx, content in items:
            view = views.get((chat_id, char_id, turn_idx))
            if view and content.strip():
                candidates.append((chat_id, char_id, mid, turn_idx, view))
    rng = random.Random(seed)
    if len(candidates) > cap:
        candidates = rng.sample(candidates, cap)
    reciprocal_ranks = []
    displaced_by_tie = 0
    for chat_id, char_id, mid, turn_idx, view in candidates:
        bank = banks[(chat_id, char_id)]
        scores, target_index = [], None
        for i, (bid, _, content) in enumerate(bank):
            scores.append(trigram_cosine(view, content))
            if bid == mid:
                target_index = i
        if target_index is None:
            continue
        rank = pessimistic_rank(scores, target_index)
        reciprocal_ranks.append(1.0 / rank)
        if rank > 1:
            target = scores[target_index]
            if any(i != target_index and abs(s - target) < 1e-9
                   for i, s in enumerate(scores) if s >= target):
                displaced_by_tie += 1
    n = len(reciprocal_ranks)
    return {
        "queries": n,
        "queries_available": len(candidates),
        "mrr_pessimistic": round(sum(reciprocal_ranks) / n, 4) if n else None,
        "rank1_pct": round(
            100 * sum(1 for r in reciprocal_ranks if r == 1.0) / n, 1)
            if n else None,
        "displaced_by_exact_tie": displaced_by_tie,
        "displaced_by_exact_tie_pct":
            round(100 * displaced_by_tie / n, 1) if n else None,
        "method": "char-trigram cosine, tie-pessimistic rank "
                  "(lexical proxy; see embed_texts_hook)",
    }


def run_retrieval_baseline(db_path, seed=42):
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    return {
        "db": str(db_path),
        "view_templates": view_template_stats(con),
        "memory_bank": memory_bank_stats(con, seed=seed),
        "lexical_self_retrieval": lexical_self_retrieval_mrr(con, seed=seed),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", default="engine.db")
    parser.add_argument("--out", default=None)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    result = run_retrieval_baseline(args.db, seed=args.seed)
    text = json.dumps(result, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
