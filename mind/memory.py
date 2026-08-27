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
    MEMORY_KIND_ALIASES, MEMORY_KINDS,
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
    _MAX_DISPUTE_HISTORY, _MAX_DISPUTE_READING, _REPAIR_DELAY, _REPAIR_LOCK, _REPAIR_MAX_DELAY,
    _REPAIR_MAX_PENDING, _REPAIR_MAX_ROUNDS, _REPAIR_PENDING, _REPAIR_THREAD,
    _clamp, _clamp_signed, _default_category, _delete_memory_fts, _dispute_of,
    _CHARS_PER_TOKEN, _EMBED_REQUEST_TOKENS, _embed_in_request_sized_chunks,
    _embed_memory, _ensure_repair_thread, _extract_entities,
    _extract_key_phrases, _gist, _json_list, _memory_cues, _memory_document,
    _repair_loop, _replace_memory_fts, _row_memory, _turn_idx_for,
    _upsert_memory, add_memories_batch, add_memory, delete_turn_memories,
    effective_importance, note_failed_embedding_write, prepare_memories_batch,
    _SEED_SALIENCE_CEILING, prepare_memory, queue_fallback_rows_for_repair,
    repair_memory_kinds, repair_pending_embeddings, repair_seed_salience,
)
from mind.memory_read import (  # noqa: F401
    HOST_SCOPE_READERS, delete_memory, dramatic_irony_feed, list_memories,
    promise_ledger, raise_importance, record_dispute, update_memory,
    visible_memory_rows,
)
from mind.memory_retrieval import (  # noqa: F401
    _ASPECT_WEIGHT, _CONTRAST_EXCLUDED_CATEGORIES, _CONTRAST_MIN_BANK,
    _CONTRAST_MIN_SALIENCE, _CONTRAST_SEMANTIC, _CONTRAST_SEMANTIC_COVERAGE,
    _ENCODED_SHARE, _MOOD_CONGRUENCE, _RECALL_ABSTAIN_LIFT, _RECALL_CONFIDENCE_TOPK, _RECALL_LIMIT,
    _RRF_SCALE,
    _STRANDED_REPORTED, _SUMMARY_RECALL_LIMIT, _congruence_valence,
    _exact_cue_score, _jaccard_text, _lexical_memory_ranking,
    _memory_fts_query, _memory_similarity, _mood_axis,
    _rank_normalized_importance, _rrf_add, _temporal_mode,
    _warn_stranded_embeddings, contrast_memory, provenance_context_label,
    recall_confidence, recent_memory_buffer, search_memories,
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
    _origin_on_drift, _summary_id, _with_reading,
    build_character_memory_context,
)
from mind.memory_time import (  # noqa: F401
    JUST_NOW, MemoryClock, UNIT_LADDER, WHEN_BEFORE_RECORD, WHEN_UNPLACEABLE,
    current_clock_reading, elapsed_phrase, time_ago_phrase, time_ago_span,
    window_clock_readings,
)
from mind.memory_lore_entries import (  # noqa: F401
    _carried_stamp, _embed_lore_document, _stamped_live_dimensions, add_lore,
    backfill_lore_embedding_stamps, delete_lore, duplicate_lorebook_for_chat,
    duplicate_lorebook_tree_for_chat, ensure_chat_canon_book,
    declared_circles, knowledge_circles, knowledge_for_character,
    lore_embedding_health,
    search_lore, update_lore,
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
    rebuild_progress, repair_memory_cues, start_rebuild_if_needed,
)
from mind.memory_inference import (  # noqa: F401
    _ABANDONED_BELIEF_DECAY, _ABANDONED_BELIEF_FLOOR, _abandoned_confidence,
    _mint_confidence_of, reconcile_inference_confidence,
)

