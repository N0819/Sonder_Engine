"""Leaf helpers shared by every memory domain.

The vocabularies, the codecs, and the two scorers. Nothing here reads another
`memory_*` module -- this is the module that makes the family acyclic."""

import base64
import json
import re
import numpy as np
from core.db import q
from language_runtime import linguistic

def _ling(name):
    """One deterministic recognizer, from the story's own language pack.

    Read at use time, never at import: two stories in different languages run
    concurrently and each must see its own vocabulary. A pack that lacks the
    key raises rather than returning empty -- a recognizer that quietly
    matches nothing is the failure this file is least able to notice, because
    every one of them degrades to "no signal" rather than to an error.
    """
    return linguistic("mind.memory", name)

_UNSET = object()

LORE_CATEGORIES = [
    "location", "layout", "event", "mechanic", "myth",
    "character", "faction", "species", "culture", "technology",
    "knowledge", "other",
    # THE ONLY CATEGORY THE NAME MINT MAY READ. A phonology entry holds the
    # MATERIAL a name is built from -- fragments, onsets, endings -- and
    # never a person. Every other category may name individuals, and an
    # individual's name is not pool material: harvested from a `character`
    # entry and cross-producted, a lorebook's cast issued "Jean-Luc Crusher"
    # to twenty strangers and reconstituted one canon character verbatim
    # (measured 2026-08-28). Partitioning at the READ is what makes that
    # impossible rather than merely filtered afterwards.
    "phonology",
]

LOREBOOK_TYPES = [
    "general", "world", "knowledge", "location", "system",
    "characters", "events", "vehicle",
]

LOREBOOK_LINK_TYPES = [
    "related",
    "references",
    "depends_on",
    "supplements",
    "overlaps",
    "supersedes",
    "contradicts",
    "alternate_version",
    "same_setting",
    "portal",
    # "is at right now": a mobile (anchored) book's live presence link to
    # the book of wherever its anchor entity currently is, rewritten from
    # scene positions at every commit (commit.sync_anchored_books).
    # Distinct from parent_id, which is canonical "belongs to" and is
    # never mutated by commit. Retrieval follows it so docked-location
    # lore stays reachable; it is NEVER perception authorization.
    "currently_within",
]

KNOWLEDGE_TAGS = ["common", "scholarly", "esoteric"]
KNOWLEDGE_RANGES = ["local", "global"]

LORE_INHERITANCE_MODES = ["inherit", "isolated", "reference_only"]

# The kind vocabulary (docs/guides/MEMORY.md 1). Enforced at prepare_memory:
# rows HAD escaped it -- 253 `episode` rows and one `belief` row live -- and
# two consumers test kind by exact string (belief weighting fires on
# kind == "inference" only, and reconcile_inference_confidence selects
# kind='inference'), so the stray `belief` row was a belief that could never
# be revised or demoted (docs/experiments/AUDIT_MEMORY.md 1.5).
MEMORY_KINDS = [
    "episodic", "dialogue", "inference", "semantic",
    "relationship", "promise", "intention",
]

# Spellings live mint sites actually used, mapped to the vocabulary. These
# coerce quietly; an unknown kind coerces with a warning.
MEMORY_KIND_ALIASES = {"episode": "episodic", "belief": "inference"}

MEMORY_CATEGORIES = [
    "episode", "dialogue", "promise", "relationship",
    "person", "place", "semantic", "intention",
    "emotion", "self", "inference",
]

MEMORY_PROVENANCE = [
    "witnessed", "heard", "told", "read",
    "inferred", "remembered",
]

# P8: which rolling summary a memory folds into.
#
# Consolidation used to melt every provenance into ONE autobiographical string
# that was then fed back wholesale each turn -- so the distinction this engine's
# thesis rests on, between what a character SAW, what they were TOLD, and what
# they GUESSED, did not survive the summary layer. A belief they inferred came
# back a few turns later indistinguishable from something they had witnessed,
# which is belief laundering into knowledge inside a single mind.
#
# Three scopes rather than a provenance tag per sentence, because the summary is
# prose written by a model and a tag inside prose is a convention it can drop.
# A separate row cannot be dropped. `memory_summaries` is already keyed
# (chat_id, char_id, scope) and every dump/restore/archive path iterates rows
# generically, so this needs no migration and rides existing round-trips.
SUMMARY_SCOPE_FIRSTHAND = "autobiographical"
SUMMARY_SCOPE_HEARSAY = "hearsay"
SUMMARY_SCOPE_SURMISE = "surmise"

_PROVENANCE_SCOPE = {
    "witnessed": SUMMARY_SCOPE_FIRSTHAND,
    "remembered": SUMMARY_SCOPE_FIRSTHAND,
    "heard": SUMMARY_SCOPE_HEARSAY,
    "told": SUMMARY_SCOPE_HEARSAY,
    "read": SUMMARY_SCOPE_HEARSAY,
    "inferred": SUMMARY_SCOPE_SURMISE,
}

# Keyed by scope: the model field carrying it, and how the character's own
# context labels it back to them.
_SUMMARY_SCOPES = (
    (SUMMARY_SCOPE_FIRSTHAND, "summary", "what_i_experienced"),
    (SUMMARY_SCOPE_HEARSAY, "hearsay_summary", "what_i_was_told"),
    (SUMMARY_SCOPE_SURMISE, "surmise_summary", "what_i_concluded"),
)


def summary_scope_for(provenance):
    return _PROVENANCE_SCOPE.get(
        str(provenance or "").strip().casefold(), SUMMARY_SCOPE_FIRSTHAND)

def summary_context_label(scope):
    return next((label for value, _field, label in _SUMMARY_SCOPES
                 if value == scope), "what_i_experienced")

def _blob(v): return np.asarray(v, dtype=np.float32).tobytes()
def _vec(b):  return np.frombuffer(b, dtype=np.float32) if b else None

def _blob_to_b64(b):
    """Raw embedding BLOB -> JSON-safe base64 string (None if absent).

    Snapshot/export dumps are stored as JSON, so raw bytes must be
    encoded. The round trip through base64 is byte-identical, which is
    what lets checkpoint restore put embeddings back verbatim instead
    of re-embedding (and risking a silent crc32-fallback downgrade)."""
    if not b:
        return None
    return base64.b64encode(bytes(b)).decode("ascii")

def _b64_to_blob(s):
    """Inverse of _blob_to_b64; returns None on anything malformed so
    callers fall back to re-embedding rather than storing garbage."""
    if not s or not isinstance(s, str):
        return None
    try:
        raw = base64.b64decode(s, validate=True)
    except Exception:
        return None
    # Stored vectors are float32 arrays; anything that can't be one is
    # not a usable embedding.
    if not raw or len(raw) % 4 != 0:
        return None
    return raw
def _storage_json(value):
    if value is None or isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)

def _ids(lorebook_ids):
    if lorebook_ids is None: return []
    if isinstance(lorebook_ids, int): return [lorebook_ids]
    out = []
    for i in lorebook_ids:
        if i and i not in out: out.append(i)
    return out

def _fts_query(text):
    toks = re.findall(r"[A-Za-z0-9]{3,}", text or "")[:12]
    return " OR ".join(f'"{t}"' for t in toks) if toks else None

def _kw_scores(fts_table, query, limit=50):
    """Keyword MAGNITUDES: normalized BM25, not a positional decay.

    The old body ordered by rank -- which IS bm25() -- and then threw the
    score away for `1.0 - i / len(rows)`, so a single weak match scored 1.0,
    the best match in a field of fifty also scored 1.0, and the slope
    depended on how MANY rows matched, never on how well. Harmless to an
    order-only consumer; the one production consumer is `search_lore`'s
    0.65*cosine + 0.35*keyword blend, which consumes the magnitude, and the
    counterfactual measured on live books put 59% of queries on large books
    handing the mapping stage a different top-10 lore set than true keyword
    relevance would (docs/experiments/AUDIT_MEMORY.md 1.1).

    SQLite's bm25() returns more-negative-is-better, so the magnitude is
    -bm25, normalized by the best match so the blend's 0.35 weight keeps the
    scale it was tuned on.
    """
    fq = _fts_query(query)
    if not fq: return {}
    try:
        rows = q(f"SELECT rowid, bm25({fts_table}) AS s FROM {fts_table} "
                 f"WHERE {fts_table} MATCH ? ORDER BY rank LIMIT ?",
                 (fq, limit))
        if not rows:
            return {}
        best = max(-r["s"] for r in rows)
        if best <= 0:
            return {r["rowid"]: 1.0 for r in rows}
        return {r["rowid"]: max(0.0, -r["s"]) / best for r in rows}
    except Exception:
        return {}

def _cos(a, b):
    """Cosine between two STORED vectors, which are already unit length.

    Both producers normalise before returning -- `providers.cheap_embed`
    divides by its norm, and `embed_texts_meta` does the same to every vector
    a provider hands back -- so the divisor here was two `np.linalg.norm`
    calls per comparison that both computed 1.0. Dropping them makes this a
    plain dot product and about 4x faster, which is the whole cost of the
    retrieval scan: `search_memories` calls this twice per candidate row.

    A zero vector is the one input that is not unit length, and it is still
    correct: its dot product is 0.0, which is what the old expression returned
    for it too.
    """
    if a is None or b is None or len(a) != len(b): return 0.0
    return float(np.dot(a, b))

def _summary_retrieval_text(summary, key_phrases, unresolved_threads):
    return "\n".join([summary or "", ", ".join(key_phrases or []),
                      "\n".join(unresolved_threads or [])])

