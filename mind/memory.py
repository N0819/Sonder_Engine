"""Memory system with hierarchical lorebook support and expanded categories.

A FACADE. Every name below is defined in one of the `mind/memory_*` modules and
re-exported here so that `from mind.memory import X` keeps meaning what it meant
before the split — 105 names across the engine import it that way, and not one
of them changed. Plan and range table: `docs/design/SPLIT_MEMORY.md`.

The import block below is RETAINED rather than pruned. Two things depend on it
and neither is visible from this file: `payload_legacy` is imported from
`llm.prompts` here and re-imported *out* of `mind.memory` elsewhere, and fifteen
test files monkeypatch `memory.<imported-name>` — `chat_complete`,
`embed_texts`, `embed_texts_meta`, `embedding_model_key`. A patch on this
module is inert for any reader that moved, so those tests name the sibling that
defines the reader; the names must still resolve here regardless.
"""

import base64
import hashlib
import json, re, threading, time
import numpy as np
from collections import defaultdict
from core.db import q, qi, wget, wset, transaction
from llm.providers import (embed_texts, embed_texts_meta, chat_complete,
                       embedding_model_key)
from llm.prompts import get_prompt, payload_legacy
from dataclasses import dataclass, field, asdict
from typing import Optional
from core import frames as _frames
from core.logging_utils import logger
from mind.theory_of_mind import belief_credence
from core.db import active_frame_id as _active_frame_id
from language_runtime import linguistic

from mind.memory_common import (  # noqa: F401
    KNOWLEDGE_RANGES, KNOWLEDGE_TAGS, LOREBOOK_LINK_TYPES, LOREBOOK_TYPES,
    LORE_CATEGORIES, LORE_INHERITANCE_MODES, MEMORY_CATEGORIES,
    MEMORY_PROVENANCE, SUMMARY_SCOPE_FIRSTHAND, SUMMARY_SCOPE_HEARSAY,
    SUMMARY_SCOPE_SURMISE, _PROVENANCE_SCOPE, _SUMMARY_SCOPES, _UNSET,
    _b64_to_blob, _blob, _blob_to_b64, _cos, _fts_query, _ids, _kw_scores,
    _ling, _storage_json, _summary_retrieval_text, _vec,
    summary_context_label, summary_scope_for,
)
from mind.memory_lorebooks import (  # noqa: F401
    _chat_lorebook_root_ids, _inheriting_ancestors, add_lorebook_link,
    chat_lorebook_ids, chat_lorebook_weights, delete_lorebook_link,
    dump_lorebook_links, get_lorebook_links, lorebook_descendants,
    lorebook_manifest, monitoring_subtree, move_lorebook, reorder_lorebook,
    resolve_lorebook_graph, restore_lorebook_links, update_lorebook_link,
    would_create_book_cycle,
)
from mind.memory_write import (  # noqa: F401
    _IMPORTANCE_CEILING, _IMPORTANCE_DISPUTE_STEP, _IMPORTANCE_STEP,
    _MAX_DISPUTE_READING, _REPAIR_DELAY, _REPAIR_LOCK, _REPAIR_MAX_DELAY,
    _REPAIR_MAX_PENDING, _REPAIR_MAX_ROUNDS, _REPAIR_PENDING, _REPAIR_THREAD,
    _clamp, _clamp_signed, _default_category, _delete_memory_fts, _dispute_of,
    _embed_memory, _ensure_repair_thread, _extract_entities,
    _extract_key_phrases, _gist, _json_list, _memory_cues, _memory_document,
    _repair_loop, _replace_memory_fts, _row_memory, _turn_idx_for,
    _upsert_memory, add_memories_batch, add_memory, delete_turn_memories,
    effective_importance, note_failed_embedding_write, prepare_memories_batch,
    prepare_memory, queue_fallback_rows_for_repair, repair_pending_embeddings,
)
from mind.memory_read import (  # noqa: F401
    HOST_SCOPE_READERS, delete_memory, dramatic_irony_feed, list_memories,
    promise_ledger, raise_importance, record_dispute, update_memory,
    visible_memory_rows,
)
from mind.memory_retrieval import (  # noqa: F401
    _ASPECT_WEIGHT, _CONTRAST_EXCLUDED_CATEGORIES, _CONTRAST_MIN_BANK,
    _CONTRAST_MIN_SALIENCE, _CONTRAST_SEMANTIC, _CONTRAST_SEMANTIC_COVERAGE,
    _ENCODED_SHARE, _MOOD_CONGRUENCE, _RECALL_LIMIT, _RRF_SCALE,
    _STRANDED_REPORTED, _SUMMARY_RECALL_LIMIT, _congruence_valence,
    _exact_cue_score, _jaccard_text, _lexical_memory_ranking,
    _memory_fts_query, _memory_similarity, _mood_axis,
    _rank_normalized_importance, _rrf_add, _temporal_mode,
    _warn_stranded_embeddings, contrast_memory, provenance_context_label,
    recent_memory_buffer, search_memories,
)
from mind.memory_summaries import (  # noqa: F401
    _EMPTY_VIEW_MARKERS, _SUPPORT_MAX_REFS, _SUPPORT_MIN_OVERLAP,
    _content_words, _empty_view_markers, _is_empty_view,
    _portable_memory_event_key, _substantive, _write_consolidated_window,
    backfill_memory_summary_windows, backfill_missing_memory_event_keys,
    consolidate_character_memory, derive_summary_support, get_memory_summary,
    maybe_consolidate_character_memory, memory_summary_coverage,
    save_memory_summary, search_memory_summaries, summary_support,
)
from mind.memory_context import (  # noqa: F401
    _beats_ago_span, _origin_on_drift, _summary_id, _with_reading,
    build_character_memory_context,
)
from mind.memory_lore_entries import (  # noqa: F401
    _carried_stamp, _embed_lore_document, _stamped_live_dimensions, add_lore,
    backfill_lore_embedding_stamps, delete_lore, duplicate_lorebook_for_chat,
    duplicate_lorebook_tree_for_chat, ensure_chat_canon_book,
    knowledge_for_character, lore_embedding_health, search_lore, update_lore,
)
from mind.memory_snapshot import (  # noqa: F401
    _StoredEmbeddingMeta, apply_chat_memory_restore,
    apply_memory_summary_restore, dump_character_memories, dump_chat_memories,
    dump_lorebook, dump_memory_summaries, dump_memory_vectors,
    get_memory_vectors, import_character_memories,
    prepare_chat_memory_restore, prepare_memory_summary_restore,
    put_memory_vector, restore_chat_memories, restore_lorebook,
    restore_memory_summaries, restore_memory_vectors, vector_address,
)
from mind.memory_relationships import (  # noqa: F401
    RELATIONSHIP_AXES, Relationship, RelationshipGraph, _TRUST_INFERENCE_STEP,
    apply_relationship_updates, get_relationships, record_relationship_event,
    relationship_history, relationships_for_payload, save_relationships,
    update_relationships_from_inference,
)
from mind.memory_vectors import (  # noqa: F401
    _REBUILD_BATCH, _REBUILD_LOCK, _REBUILD_STATE, _memory_vector_key,
    _rebuild_book_ids, _run_rebuild, _summary_vector_key, _vector_key,
    embedding_bank_status, rebuild_checkpoint_embeddings, rebuild_embeddings,
    rebuild_progress, start_rebuild_if_needed,
)

# ---- Why there is no vector index ----
#
# There was a `sqlite-vec` ANN index here (`init_vec_index`,
# `search_memories_vec`). It never ran -- no caller, and the extension was
# never loaded -- and it was deleted rather than wired, because wiring it
# would have been a REGRESSION.
#
# `search_memories` filters its rows before ranking: the F1 turn cutoff (a
# mind deciding turn N must never retrieve how turn N turned out, live on
# every reroll) and frame visibility. The ANN query filtered on chat_id and
# char_id only, and those predicates are exactly the kind an ANN index cannot
# carry cheaply -- so a vec-first branch would have handed a character the
# committed outcome of its own undecided beat.
#
# And the scan it would have optimised does not need optimising. Memories
# accrue at ~3.5 rows per turn per character; measured with `_cos` verbatim,
# the full scan costs 16ms at a real story's worst case (442 rows), 126ms at
# ~1,000 turns, 709ms at ~10,000 -- beside an LLM call measured in seconds.
# Two cheap optimisations sit in front of an index anyway if it ever mattered:
# `_cos` recomputes both norms although every stored vector is already
# normalised (~4x), and the loop could be one matmul (~20x). See
# docs/UNBUILT.md §1.4.


# How far an inference the character no longer holds is pushed down, and the
# floor it stops at. Not zero: a belief that was explained away is still a
# belief they once had, and "I was sure of this and I was wrong" is a thing a
# character should be able to recall. It just must not outrank what replaced it.
#
# The demotion is a ONE-SHOT re-anchoring to a fraction of the confidence the
# character declared at mint time -- never a compounding per-turn decay on the
# current value. The predicate "no surviving hypothesis expresses it" is met by
# per-entity pruning and half-life expiry as well as by genuine explaining-away,
# and mind_models is a small working set while the memory bank is an archive:
# under the compounding rule, 76-80% of a long chat's entire inference bank
# reached the floor within 7-18 played turns of the rule landing (measured
# 2026-07-29 across the live corpus), at which point the belief-weighted
# ranking term removed inferences from recall almost completely (0-1 of top-8
# vs 13-15 at mint confidence in replayed late-turn retrievals). A belief that
# merely aged out of the working set was never concluded WRONG, and must not
# rank as though it was.
_ABANDONED_BELIEF_DECAY = 0.55
_ABANDONED_BELIEF_FLOOR = 0.08


def _mint_confidence_of(salience):
    """The confidence an inference row was minted with, recovered from its
    salience. commit.py mints inference memories with
    salience = 0.45 + 0.3 * confidence, and reconciliation deliberately never
    touches salience (it records how much the inference mattered when formed),
    so the mint-time confidence stays reconstructible without a second column.
    Rows whose salience was authored/imported outside that rule get a
    conservative low anchor rather than a crash."""
    try:
        return max(0.0, min(1.0, (float(salience) - 0.45) / 0.3))
    except (TypeError, ValueError):
        return 0.5


def _abandoned_confidence(salience):
    """The resting confidence for an inference no live hypothesis carries.

    A pure function of the row's (untouched) salience, which is what makes
    reconciliation idempotent: reconciling the same abandoned row on every
    subsequent turn lands on the same number instead of compounding it into
    unretrievability -- and a corpus previously crushed by the compounding
    rule self-heals to this value on its next reconcile pass, no migration.
    Clamped to never exceed the mint confidence, so a belief the character
    barely credited when they formed it is not lifted to the floor."""
    mint = _mint_confidence_of(salience)
    return min(mint, max(_ABANDONED_BELIEF_FLOOR,
                         mint * _ABANDONED_BELIEF_DECAY))


def reconcile_inference_confidence(chat_id, char_id, state, turn_idx,
                                   elapsed_seconds=None):
    """Re-weight this character's inference memories to what they believe NOW.

    An inference memory is minted with the confidence the character declared
    the moment they formed it, and nothing ever revisited it. Meanwhile their
    mind_models kept moving -- theory_of_mind.apply_mind_model_updates blends a
    restated belief upward, partially explains away the competitor it displaces,
    decays the unreinforced, and prunes what falls through the floor. So a
    character could hold one belief and preferentially RECALL the one they had
    already abandoned, because recall ranked on a number frozen at mint time.

    This projects the reconciled credence back onto the memories that expressed
    it: a claim still carried by a live hypothesis takes that hypothesis's
    decay-adjusted confidence; a claim no hypothesis carries any more is pushed
    toward _ABANDONED_BELIEF_FLOOR.

    Information-firewall note, because this is the part that matters: the only
    inputs are this character's OWN memory rows and their OWN mind_models, both
    already built from what they legitimately perceived. Nothing here consults
    the objective record, another mind's state, or whether the belief was
    actually TRUE -- a character revises because of what they later perceived,
    never because they were graded against reality. Reconciling against truth
    would collapse the belief layer into the truth layer, which is the one
    distinction this engine exists to keep.

    `salience` is deliberately untouched: it records how much the inference
    mattered when it was formed (and drives consolidation/archiving), which is
    a different question from how much the character credits it now.

    Returns the number of rows whose confidence changed.
    """
    rows = q(
        "SELECT id, entities, gist, salience, confidence FROM memories "
        "WHERE chat_id=? AND char_id=? AND kind='inference'",
        (chat_id, char_id),
    )
    if not rows:
        return 0

    updates = []
    for row in rows:
        subjects = _json_list(row["entities"])
        subject = str(subjects[0]).strip() if subjects else ""
        claim = str(row["gist"] or "").strip()
        if not subject or not claim:
            continue
        credence = belief_credence(
            state, subject, claim, turn_idx, elapsed_seconds)
        abandoned = _abandoned_confidence(row["salience"])
        if credence is None:
            # No live hypothesis carries this claim. That is NOT proof the
            # character concluded they were wrong -- mind_models prunes on
            # capacity and half-life as well as on displacement -- so the row
            # rests at a fixed fraction of its mint confidence (idempotent;
            # see _abandoned_confidence) rather than compounding downward on
            # every reconciled turn.
            revised = abandoned
        else:
            # A claim STILL STORED must never rank below one that was pruned:
            # half-life decay on a surviving hypothesis measures staleness,
            # not disbelief, so the live credence is floored at the abandoned
            # resting place. Held >= abandoned, always.
            revised = max(credence, abandoned)
        if abs(revised - float(row["confidence"] or 0.0)) > 1e-6:
            updates.append((round(revised, 4), row["id"]))

    for confidence, mid in updates:
        qi("UPDATE memories SET confidence=? WHERE id=?", (confidence, mid))
    return len(updates)
