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

# ---- Hybrid retrieval ----

def _memory_fts_query(text):
    stopwords = _ling("_STOPWORDS")
    tokens = [t.lower() for t in _ling("_WORD_RE").findall(text or "")
              if t.lower() not in stopwords]
    tokens = list(dict.fromkeys(tokens))[:16]
    if not tokens:
        return None
    return " OR ".join(f'"{t.replace(chr(34), chr(34)+chr(34))}"' for t in tokens)

def _lexical_memory_ranking(chat_id, char_id, query_text, limit=60):
    fq = _memory_fts_query(query_text)
    if not fq:
        return []
    try:
        rows = q("""SELECT CAST(memory_id AS INTEGER) AS mid, bm25(memory_retrieval_fts) AS score
            FROM memory_retrieval_fts WHERE memory_retrieval_fts MATCH ? AND chat_id=? AND char_id=?
            ORDER BY score LIMIT ?""", (fq, str(chat_id), str(char_id), limit))
        return [r["mid"] for r in rows]
    except Exception:
        return []

def _temporal_mode(query_text):
    text = (query_text or "").lower()
    if any(re.search(p, text) for p in _ling("_OLD_CUES")):
        return "old"
    if any(re.search(p, text) for p in _ling("_RECENT_CUES")):
        return "recent"
    return "neutral"

def _exact_cue_score(memory, query_text):
    ql = (query_text or "").lower()
    if not ql:
        return 0.0
    score = 0.0
    for phrase in memory.get("key_phrases") or []:
        pl = phrase.lower().strip()
        if pl and pl in ql:
            score = max(score, 1.0)
        elif pl and ql in pl and len(ql) >= 4:
            score = max(score, 0.8)
    for entity in memory.get("entities") or []:
        if entity.lower() in ql:
            score = max(score, 0.7)
    loc = (memory.get("location") or "").lower()
    if loc and loc in ql:
        score = max(score, 0.7)
    return score

def _jaccard_text(a, b):
    # Same content-word rule as `_content_words`, and the same pack key: this
    # is the fallback whenever two memories have no vectors to compare, and an
    # English-only tokenizer scored every Japanese pair at 0.0 similarity --
    # which reads as "unrelated", not as "could not tell".
    word_re = _ling("_SUPPORT_WORD_RE")
    la = set(word_re.findall((a or "").lower()))
    lb = set(word_re.findall((b or "").lower()))
    if not la or not lb:
        return 0.0
    return len(la & lb) / len(la | lb)

def _memory_similarity(a, b):
    av, bv = a.get("_vector"), b.get("_vector")
    if av is not None and bv is not None and len(av) == len(bv):
        return max(0.0, _cos(av, bv))
    return _jaccard_text(f"{a.get('gist','')} {a.get('content','')}",
                         f"{b.get('gist','')} {b.get('content','')}")

# The bridge between two score scales that were being added together as though
# they shared one.
#
# RRF's output is arbitrary in magnitude -- `weight / (60 + rank)` is about
# 0.02 at rank 1, and only its ORDER carries meaning. The bonuses that follow
# (salience, recency, presence) are hand-tuned on a 0..1 utility scale. Summed
# raw, the four relevance rankings could contribute at most 0.074 combined,
# while the recency bonus alone reaches 0.12 -- so a recent, salient memory
# with NO relevance to the query outranked the single best match on every
# relevance signal the engine has.
#
# It was invisible until alpha 6.3. With the crc32 fallback the vector
# rankings were lexical noise, so nobody could tell they were being ignored;
# configuring a real embeddings provider made the signal real and the
# imbalance measurable. Measured on a live 441-memory story: end-to-end
# retrieval of a paraphrased memory ran at 1/16, and 88% of the memories
# handed to a character carried no vector match at all.
#
# Scaled rather than re-tuning the bonuses, because the bonuses' RELATIVE
# values are meaningful and their absolute band is the one that was chosen
# deliberately. 12 puts the four rankings at ~0.9 combined against a ~0.4
# bonus band: relevance leads, and salience/recency/presence still decide
# between comparably relevant memories, which is what they are for. Measured
# across 12 real perception views, the share of retrieved memories with an
# actual vector match goes 12% -> ~50% and plateaus by 16, so this sits at the
# top of the useful range rather than past it.
_RRF_SCALE = 12.0


# How many retrieved memories reach a character each beat.
#
# Was 8, and measured too low once relevance actually worked. Every result set
# is padded with chronological neighbours of what was recalled, so at 8 those
# four padding entries were a third of what the character saw. Raising the
# limit dilutes them with relevance-selected memories instead -- measured on
# real perception views, mean relevance of the whole set RISES from 0.608 to
# 0.640 while the least relevant slot does not move, i.e. the added memories
# are better than the padding they displace, not filler.
#
# 16 rather than 24: end-to-end recall of a paraphrased memory goes 7/16 ->
# 11/16 -> 13/16 across 8/16/24, but relevance flattens (0.640 -> 0.649) while
# the payload keeps growing (~890 -> ~1242 tokens per character per beat). The
# attention budget is real -- see docs/UNBUILT.md 1.12 on nine payload keys --
# so this stops where the curve does.
_RECALL_LIMIT = 16

# How many EARLIER summary windows travel beside the current one. Two, for the
# same attention-budget reason the number above stops at 16 -- and because the
# windows are long-form paragraphs, not one-line gists, so each one costs
# several times what a recalled memory does.
#
# There is deliberately no minimum score. Measured on the live bank (chat 58,
# the Doctor, 176 embedded memories against two windows): every prose vector
# scores its window somewhere in 0.45-0.55, so an absolute floor either drops
# everything or nothing depending on the embedding model, and would silently
# become "nothing" the day the model changes. What the band DOES separate is
# rank -- a memory formed inside a window ranks that window above the other one
# 97% and 82% of the time across the two windows -- so the ordering is
# trustworthy where the magnitude is not, and top-k is the honest way to use it.
_SUMMARY_RECALL_LIMIT = 2


# Mood-congruent recall: what you feel shapes what comes back.
#
# `memories.valence` is written on every row and, until alpha 6.3.1, fed the
# ranking nowhere -- its only consumer was `contrast_memory`, and there as
# `abs(valence)`, which is emotional INTENSITY ("this memory is charged"), not
# congruence ("this matches how you feel now"). The signed half of an affect
# signal the engine already tracked had never been used for anything.
#
# It was also unbuildable until the same release, and that is worth recording
# rather than repeating: memories were taking the character's raw self-report
# instead of their resolved affect, which measured 0% negative against a true
# 22%. Ranking on it then was ranking on a constant -- built once, measured as
# inert, and withdrawn. It works now because the axis does.
#
# Deliberately small, and in the same band as the salience term for the reason
# the belief-credence comment beside it already gives: this should break a tie
# between comparably relevant memories, never outrank an actual match. And
# deliberately bounded, because congruence is a FEEDBACK loop -- a character in
# despair recalling only despair deepens the despair. That may be exactly right
# for fiction (it is what rumination is), but it should be a chosen intensity
# rather than an emergent one.
_MOOD_CONGRUENCE = 0.05

# How much of a memory's emotional charge is the mood it was CARRIED INTO
# versus the mood it was LEFT WITH. Two different real phenomena: the first is
# state-dependent context (what you were feeling when you walked in), the
# second is the memory's emotional tone (what it came to mean once appraised).
#
# Congruence read `valence` alone -- the incoming mood -- which inverts on the
# case that matters most: walk into a celebration happy, discover a betrayal,
# leave devastated, and the memory carries POSITIVE incoming charge. A
# despairing character was then pushed away from recalling the betrayal.
#
# Weighted toward the encoded tone because that is what the memory is ABOUT,
# with the incoming mood kept as real context rather than discarded.
_ENCODED_SHARE = 0.75


def _congruence_valence(mem) -> float:
    """The emotional charge mood-congruence should match against.

    Falls back to incoming valence when there is no encoded value, which is
    not a rare path: `encoding_valence` is younger than most of the corpus and
    is populated in only the two newest banks, so every older memory has 0.0
    there and blending it in blind would silently halve their charge.

    HONEST LIMIT: this is principled, not measured. Across the corpus only 738
    memories carry both values and exactly 2 disagree in sign, and in the banks
    where the column exists NEITHER field has ever gone below -0.05 -- these
    stories are warm, so the "opposite feeling pushes down" half of congruence
    has not once fired. The change cannot be wrong in a way the data would show,
    and it cannot be shown to help either. Revisit with a story that goes dark.
    """
    incoming = float(mem.get("valence") if isinstance(mem, dict) else mem["valence"] or 0.0) \
        if isinstance(mem, dict) else float(mem["valence"] or 0.0)
    encoded = mem.get("encoding_valence") if isinstance(mem, dict) else mem["encoding_valence"]
    try:
        encoded = float(encoded or 0.0)
    except (TypeError, ValueError):
        encoded = 0.0
    try:
        incoming = float(incoming or 0.0)
    except (TypeError, ValueError):
        incoming = 0.0
    if not encoded:
        return incoming
    return (_ENCODED_SHARE * encoded) + ((1.0 - _ENCODED_SHARE) * incoming)

def _mood_axis(text):
    """The signed valence a mood/goal string implies, or None if it implies
    none. Word-matched against a small closed vocabulary rather than embedded:
    this is a tiebreak, and a wrong sign is worse than no sign."""
    words = set(_ling("_MOOD_TOKEN_RE").findall(str(text or "").casefold()))
    if not words:
        return None
    score = 0.0
    for vocab, sign in _ling("_MOOD_VALENCE"):
        score += sign * len(words & set(vocab))
    return None if score == 0 else (1.0 if score > 0 else -1.0)


def _rrf_add(scores, reasons, ranking, weight, reason):
    for rank, mid in enumerate(ranking, 1):
        scores[mid] += (weight * _RRF_SCALE) / (60.0 + rank)
        if rank <= 12 and reason not in reasons[mid]:
            reasons[mid].append(reason)

# (chat_id, char_id, model_key) already reported. Retrieval runs for every
# character on every beat, so the warning has to be once per situation rather
# than once per call, or it becomes the noise it exists to cut through.
_STRANDED_REPORTED = set()


def _warn_stranded_embeddings(chat_id, char_id, stranded, total, model_key):
    """Say so when stored vectors no longer match the live embedding model.

    A row whose `embedding_model`/`embedding_dim` differ from the current
    provider's scores 0.0 on BOTH vector rankings -- forever, because nothing
    re-embeds. That is correct behaviour (a vector from another model is not
    comparable) and it is silent, which is the problem: configure an
    `embeddings` provider on a story with history and every memory written
    before that moment quietly drops to keyword-and-exact-match only, while
    new ones get the full four signals. The bank splits into two eras and
    nothing says a word.

    Retrieval still WORKS -- BM25 and exact-match are unaffected, so this
    degrades rather than breaks, which is exactly why it needs announcing.
    The fix when it fires is a re-embed pass; see docs/UNBUILT.md §1.15.
    """
    if not stranded or not total:
        return
    key = (chat_id, char_id, model_key)
    if key in _STRANDED_REPORTED:
        return
    _STRANDED_REPORTED.add(key)
    logger.warning(
        "memory: %d of %d stored memories for chat %s char %s were embedded by "
        "a different model than the live one (%s); their semantic and "
        "cue-vector rankings score 0 and only keyword/exact matching reaches "
        "them. Re-embed to restore semantic recall (docs/UNBUILT.md 1.15).",
        stranded, total, chat_id, char_id, model_key,
    )


# How hard an aspect ranking pulls, against 1.0/1.15 for the main query's own
# semantic and cue rankings. Deliberately below both: an aspect is a nudge
# from what the character wants or feels, and it must be able to break a tie
# between two comparably relevant memories without outranking what the beat is
# actually about.
_ASPECT_WEIGHT = 0.55


def _rank_normalized_importance(memories):
    """`effective_importance`, respaced across the rows this search can see.

    Ordering is preserved exactly and the influence budget is unchanged; only
    the GAPS move. What that fixes is measured (tools/salience_replay.py, 270
    probes over the live corpus):

    | arm                                   | top-16 membership moved |
    |---------------------------------------|-------------------------|
    | the term deleted entirely             | 35.2%                   |
    | percentile-normalised to [0,1]        | 59.6%                   |
    | stretched 3x about the mean           | 47.0%                   |
    | respaced inside the bank's own range  | **15.2%**               |

    Two things follow, and the second one killed the original plan. First the
    term is NOT decoration -- deleting it moves a third of all top-16s, so the
    compression was never making it silent. Second, both obvious fixes for the
    compression (normalise to [0,1], rescale) move retrieval MORE than deleting
    the term does: values live in a 0.27-wide band, so mapping them onto [0,1]
    multiplies this term's influence by about 3.7 while changing not one
    memory's rank order. That is a weight increase wearing the word
    "normalisation", and it would let salience out-argue semantic match.

    What is left once weight is held fixed is the real defect: how much
    discrimination this term has depends on how the minting model happened to
    spread its numbers that day. A bank minted at 0.70 +/- 0.03 gets a silent
    salience term and a bank spanning 0.4-0.9 gets a loud one, for a reason
    with nothing to do with the fiction. Rank-normalising inside the bank's own
    p10-p90 makes the two behave alike.

    Scoped to `memories` -- the rows already filtered for this character, this
    frame and this turn cutoff -- so the comparison is against what this mind
    can actually reach, never the whole table. Ties share a rank, so a bank
    with no spread stays flat instead of being handed an ordering by row id;
    a degenerate range collapses to the constant it already was. Callers
    asking an ABSOLUTE question -- archiving ("did this ever matter"),
    contrast selection -- keep reading `effective_importance` directly, which
    is why this respacing lives here and not in that function.
    """
    values = [(effective_importance(mem), mid)
              for mid, mem in memories.items()]
    if len(values) < 2:
        return {mid: v for v, mid in values}
    values.sort()
    ordered = [v for v, _mid in values]
    lo = ordered[int(len(ordered) * 0.10)]
    hi = ordered[int(len(ordered) * 0.90)]
    if hi - lo <= 1e-9:
        return {mid: v for v, mid in values}
    out = {}
    n = len(values)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[j + 1][0] == values[i][0]:
            j += 1
        pct = ((i + j) / 2.0) / (n - 1)
        for k in range(i, j + 1):
            out[values[k][1]] = lo + pct * (hi - lo)
        i = j + 1
    return out


def search_memories(chat_id, char_id, query, k=8, *, include_archived=True,
                    current_turn_idx=None, chronological=True, viewer_frame_id=_UNSET,
                    here=None, in_sight=None, aspects=None, embedded=None,
                    record_access=False):
    """Retrieve, fusing the main query with any `aspects` given alongside it.

    `aspects` is [(label, text), ...] -- short, separate facets of what the
    character is bringing to the beat (their mood, their goal, the threads
    they have not resolved). Each gets its OWN ranking fused into the same
    RRF, rather than being concatenated onto the query string.

    That distinction is the whole point, and it is measured. The caller used
    to join everything into one string, where the character's current view
    ran a median 1,015 characters against a mood fragment of 10-60 -- so
    `cosine(query_with_mood, view_alone)` came out at 0.994. The mood moved
    the query vector by essentially nothing and reached recall only as
    whichever stray n-grams the word happened to share. A short facet cannot
    compete for influence inside a long string; given its own rank list it
    does not have to.
    """
    # Audit F1 (a mind deciding turn N must not read how turn N turned out)
    # and frame visibility both live in visible_memory_rows, applied before any
    # ranking so no scoring path can resurrect what they dropped. The turn
    # cutoff used to feed only the recency scoring below, which RANKED those
    # rows highly instead of removing them.
    rows = visible_memory_rows(
        chat_id, char_id,
        before_turn_idx=current_turn_idx,
        viewer_frame_id=viewer_frame_id,
        include_archived=include_archived,
    )
    here_set = {str(here).strip().casefold()} if here else set()
    in_sight_set = {
        str(p).strip().casefold() for p in (in_sight or ()) if str(p or "").strip()
    } - here_set
    if not rows:
        return []
    query_text = str(query or "").strip()
    # One embedding call for the query AND every aspect: the aspects are short
    # and the round trip is what costs, so separating the rankings is free.
    _aspects = [(str(lbl), str(txt).strip()) for lbl, txt in (aspects or [])
                if str(txt or "").strip()]
    # A caller that has already embedded this exact batch passes it in rather
    # than paying a second round trip -- build_character_memory_context embeds
    # once and ranks both raw memories and summary windows from it. The length
    # check is the guard: if the aspect filter above disagrees with what the
    # caller sent, these are not the vectors this function thinks they are, so
    # embed properly instead of silently ranking against the wrong facet.
    if (embedded is None
            or len(getattr(embedded, "vectors", ()) or ()) != 1 + len(_aspects)):
        embedded = embed_texts_meta([query_text or "memory"]
                                    + [txt for _lbl, txt in _aspects])
    qv = embedded.vectors[0]
    aspect_vectors = list(zip((lbl for lbl, _t in _aspects),
                              embedded.vectors[1:]))
    memories = {}
    sem_scores, cue_scores = [], []
    stranded = 0
    comparable = {}
    for row in rows:
        mem = _row_memory(row)
        fv, cv = _vec(row["embedding"]), _vec(row["cue_embedding"])
        compatible = row["embedding_model"] == embedded.model_key and row["embedding_dim"] == embedded.dimensions
        if not compatible:
            stranded += 1
        sem = _cos(qv, fv) if compatible and fv is not None else 0.0
        cue = _cos(qv, cv) if compatible and cv is not None else 0.0
        mem["_vector"] = fv if compatible else None
        memories[mem["id"]] = mem
        sem_scores.append((sem, mem["id"]))
        cue_scores.append((cue, mem["id"]))
        if compatible and aspect_vectors:
            # Kept only while the aspect rankings are built, a few lines down.
            comparable[mem["id"]] = (fv, cv)
    _warn_stranded_embeddings(chat_id, char_id, stranded, len(rows), embedded.model_key)
    sem_rank = [mid for s, mid in sorted(sem_scores, reverse=True) if s > 0][:60]
    cue_rank = [mid for s, mid in sorted(cue_scores, reverse=True) if s > 0][:60]
    lex_rank = _lexical_memory_ranking(chat_id, char_id, query_text)
    exact_rank = [mid for mid in sorted(memories, key=lambda x: _exact_cue_score(memories[x], query_text), reverse=True)
                  if _exact_cue_score(memories[mid], query_text) > 0]
    fused = defaultdict(float)
    reasons = defaultdict(list)
    _rrf_add(fused, reasons, sem_rank, 1.0, "semantic match")
    _rrf_add(fused, reasons, cue_rank, 1.15, "cue-vector match")
    _rrf_add(fused, reasons, lex_rank, 1.1, "keyword match")
    _rrf_add(fused, reasons, exact_rank, 1.25, "exact phrase or entity match")
    # One ranking per aspect, at a weight that can break a tie but not win an
    # argument with what the beat is about.
    for label, av in aspect_vectors:
        scored = []
        for mid, (fv, cv) in comparable.items():
            best = max(_cos(av, fv) if fv is not None else 0.0,
                       _cos(av, cv) if cv is not None else 0.0)
            if best > 0:
                scored.append((best, mid))
        if scored:
            ranked = [mid for _s, mid in sorted(scored, reverse=True)][:60]
            _rrf_add(fused, reasons, ranked, _ASPECT_WEIGHT, label)
    tmode = _temporal_mode(query_text)
    # From the aspects when the caller supplied them (that is where mood
    # actually travels), falling back to the query itself.
    mood_axis = None
    for label, text in _aspects:
        if "feel" in label.casefold():
            mood_axis = _mood_axis(text)
            break
    if mood_axis is None:
        mood_axis = _mood_axis(query_text)
    known_turns = [m["turn_idx"] for m in memories.values() if m["turn_idx"] is not None]
    max_turn = current_turn_idx if current_turn_idx is not None else max(known_turns, default=0)
    ranked_importance = _rank_normalized_importance(memories)
    for mid, mem in memories.items():
        # `importance`, not `salience`: how much it matters NOW, which is the
        # question ranking is asking. They are the same number until some
        # consequence revises one, so a bank that has never been touched ranks
        # exactly as it did.
        fused[mid] += 0.08 * ranked_importance[mid]
        fused[mid] += 0.04 * mem["confidence"]
        if mem["kind"] == "inference":
            # Belief-weighted recall. Confidence on an inference row is no
            # longer a mint-time constant -- reconcile_inference_confidence
            # tracks it to what the character currently believes -- so it is
            # the signal that separates a live belief from one they have since
            # explained away. Signed around 0.5 so a held belief is promoted
            # and an abandoned one demoted; magnitude is deliberately in the
            # same band as the salience term above rather than larger, because
            # this should break a tie between competing inferences, not
            # outrank an actual semantic match.
            fused[mid] += 0.10 * (mem["confidence"] - 0.5)
            if mem["confidence"] >= 0.6:
                reasons[mid].append("belief the character still holds")
            elif mem["confidence"] <= 0.25:
                reasons[mid].append("belief the character has since revised")
        fused[mid] += 0.08 * _exact_cue_score(mem, query_text)
        if mood_axis is not None:
            # Same-signed feeling pulls up, opposite pushes down, scaled by how
            # strongly the memory itself is charged. A neutral memory (valence
            # 0) is untouched either way.
            congruent = mood_axis * _congruence_valence(mem)
            if congruent:
                fused[mid] += _MOOD_CONGRUENCE * congruent
                if congruent > 0 and "matches how you feel" not in reasons[mid]:
                    reasons[mid].append("matches how you feel")
        ti = mem["turn_idx"]
        if ti is not None and max_turn:
            age = _clamp((max_turn - ti) / max(max_turn, 1))
            if tmode == "old":
                fused[mid] += 0.12 * age
                if "older-memory cue" not in reasons[mid]:
                    reasons[mid].append("older-memory cue")
            elif tmode == "recent":
                fused[mid] += 0.12 * (1.0 - age)
                if "recent-memory cue" not in reasons[mid]:
                    reasons[mid].append("recent-memory cue")
        # Where you are is a retrieval cue. Ranking was semantic + lexical +
        # recency only, so "what happened in THIS room" -- and the navigational
        # form of it, "which way did I go from here last time" -- had no index
        # behind it at all: the one memory that answers it competes purely on
        # wording. `location` was already stored on every row and simply never
        # read. Deliberately modest, and additive rather than a filter: being
        # here makes a memory easier to reach, it does not make everything
        # elsewhere unreachable.
        if here_set and str(mem.get("location") or "").strip().casefold() \
                in here_set:
            fused[mid] += 0.09
            if "happened here" not in reasons[mid]:
                reasons[mid].append("happened here")
        elif in_sight_set and str(mem.get("location") or "").strip().casefold() \
                in in_sight_set:
            # A place currently VISIBLE is a retrieval cue too, and it is the
            # more useful one: recalling what happened in the room you are
            # standing in confirms where you are, but recalling it about a room
            # you can SEE lets you decide whether to go there. Weighted below
            # the here-cue, since standing somewhere is stronger evidence of
            # relevance than looking at it.
            fused[mid] += 0.05
            if "visible from here" not in reasons[mid]:
                reasons[mid].append("visible from here")
        if mem["category"] == "promise" and any(
                t in query_text.lower()
                for t in _ling("_PROMISE_QUERY_CUES")):
            fused[mid] += 0.1
            reasons[mid].append("promise category")
    ranked = sorted(memories, key=lambda x: fused[x], reverse=True)
    selected = []
    pool = ranked[:max(k * 8, 40)]
    while pool and len(selected) < k:
        best_id, best = None, float("-inf")
        for mid in pool:
            rel = fused[mid]
            red = max((_memory_similarity(memories[mid], memories[s]) for s in selected), default=0.0)
            mmr = 0.82 * rel - 0.18 * red
            if mmr > best:
                best = mmr
                best_id = mid
        selected.append(best_id)
        pool.remove(best_id)
    expanded = list(selected)
    if len(expanded) < k + 2:
        by_turn = sorted((m for m in memories.values() if m["turn_idx"] is not None), key=lambda m: (m["turn_idx"], m["id"]))
        positions = {m["id"]: i for i, m in enumerate(by_turn)}
        for mid in selected[:3]:
            mem = memories[mid]
            if mem["category"] != "episode":
                continue
            pos = positions.get(mid)
            if pos is None:
                continue
            for np in (pos - 1, pos + 1):
                if 0 <= np < len(by_turn):
                    nid = by_turn[np]["id"]
                    if nid not in expanded and abs(by_turn[np]["turn_idx"] - mem["turn_idx"]) <= 1:
                        expanded.append(nid)
                        reasons[nid].append("chronological neighbor of recalled episode")
                    if len(expanded) >= k + 2:
                        break
    result = []
    for mid in expanded:
        mem = dict(memories[mid])
        mem.pop("_vector", None)
        mem["score"] = round(fused[mid], 6)
        mem["retrieval_reasons"] = reasons[mid]
        result.append(mem)
    if chronological:
        result.sort(key=lambda m: (m["turn_idx"] is None, m["turn_idx"] if m["turn_idx"] is not None else 10**12, m["id"]))
    # `access_count` answers one question -- did this memory ever come BACK to
    # the character -- and the write used to fire for anybody who called this
    # function. The author's Memories tab runs the same search
    # (`web/app.py`'s memory search route, which states in its own comment
    # that the author is not a fictional mind), and every such search
    # incremented the counter that `tools/remember_lines.py` and
    # `tools/salience_replay.py` read as their answer. A replay tool measuring
    # retrieval must not alter the number it is measuring, either.
    #
    # So recording is asserted by the caller that IS a mind recalling, rather
    # than opted out of by everyone who is not -- the same posture
    # `visible_memory_rows` takes with its required arguments, and for the
    # same reason: the caller who forgets is the one who gets it wrong.
    if result and record_access:
        now = time.time()
        ids = [m["id"] for m in result]
        ph = ",".join("?" for _ in ids)
        qi(f"UPDATE memories SET access_count=access_count+1, last_accessed=? WHERE id IN ({ph})", (now, *ids))
    return result

# ---- Contrast retrieval (unbidden recall) ----
#
# Ordinary recall asks "what is most like this beat". A character measurably
# stuck -- reissuing a sentence shape, holding the same ungoverned goal for a
# dozen beats, plateaued on a sustained stimulus -- needs the opposite
# question answered once: "what that mattered is LEAST like this beat".
# The selection is a second scoring pass over the same character-scoped,
# turn-cutoff, frame-filtered rows ordinary recall reads; it crosses no
# information boundary ordinary recall doesn't already cross, and it is a
# pure read -- it must never touch access_count even though it runs on the
# character's behalf, because it runs mid-pipeline at character-stage time.

# How hard semantic distance pushes an unbidden memory away from the beat.
# Comparable to the token penalty (0.8) rather than larger: the structural
# axis is exact and has been carrying this since the beginning, so the vector
# joins it instead of replacing it.
_CONTRAST_SEMANTIC = 0.7

# What share of the bank must be comparable with the live model before the
# semantic axis is used at all. See the inversion note in contrast_memory.
_CONTRAST_SEMANTIC_COVERAGE = 0.9

# Below this many rows, "far from the recent window" barely means anything.
_CONTRAST_MIN_BANK = 20
# Obligation-tier categories never intrude as texture: surfacing a promise
# "unbidden" reads as the engine nagging, and those tiers have their own
# governance (fading/adrift clocks).
_CONTRAST_EXCLUDED_CATEGORIES = ("promise", "intention", "relationship")
# The salience backbone: what returns unbidden is what MATTERED. This floor
# also happens to exclude the unplaced-perception boilerplate rows (minted at
# salience 0.469 by the deterministic salience rule), which are noise here.
_CONTRAST_MIN_SALIENCE = 0.5


def contrast_memory(chat_id, char_id, query_text, current_turn_idx, *,
                    here=None, exclude_ids=(), k=1, viewer_frame_id=_UNSET):
    """Up to `k` high-salience memories DISSIMILAR to the current beat.

    Deliberately ignores `confidence`: a belief the character has since set
    aside is exactly the sort of thing that returns unprompted.

    Dissimilarity is carried by the structural fields (tokens, location,
    entities, turn distance), which are exact, PLUS semantic distance where
    the bank can supply it. The semantic half was deliberately absent until
    alpha 6.3.1: on a corpus embedded with the local-hash fallback, cosine was
    a fuzzy-lexical signal and would only have restated the token penalty.
    With real vectors it says something the token axis structurally cannot --
    that "the alley smelled of wet brick and chip fat" and "the backstreet
    stank of damp masonry and frying grease" are the SAME memory, not a
    perfect contrast. It is gated on near-total model coverage; see the
    inversion note in the body for why that gate is not optional.

    Same epistemic envelope as search_memories: this character's own rows
    only, hard turn cutoff, frame visibility. No writes.
    """
    rows = visible_memory_rows(
        chat_id, char_id,
        before_turn_idx=current_turn_idx,
        viewer_frame_id=viewer_frame_id,
        include_archived=True,
    )
    if len(rows) < _CONTRAST_MIN_BANK:
        return []
    excluded = set()
    for i in exclude_ids or ():
        try:
            excluded.add(int(i))
        except (TypeError, ValueError):
            continue
    here_cf = str(here or "").strip().casefold()
    query_cf = str(query_text or "").casefold()

    # THE INVERSION TRAP, and why this is gated so carefully.
    #
    # A row embedded by a different model scores 0.0 against any query. In
    # `search_memories` that makes it invisible, which is a silent omission.
    # Here the axis is INVERTED -- distance is the thing being rewarded -- so
    # the same 0.0 would read as maximally contrasting, and unbidden recall
    # would preferentially surface precisely the memories that have not been
    # rebuilt yet. The identical number flips from an omission into a
    # systematic bias, so only rows that are actually comparable get the
    # semantic term; the rest keep the structural axis alone, exactly as
    # before. A story mid-rebuild degrades to the old behaviour rather than to
    # a wrong one.
    qv = None
    comparable = {}
    try:
        embedded = embed_texts_meta([query_text or "memory"])
        for r in rows:
            if (r["embedding"] and r["embedding_model"] == embedded.model_key
                    and r["embedding_dim"] == embedded.dimensions):
                comparable[r["id"]] = _vec(r["embedding"])
        # Only worth the axis if MOST of the bank can be compared; a bank that
        # is half rebuilt would otherwise rank on which half a row is in.
        if len(comparable) >= _CONTRAST_SEMANTIC_COVERAGE * len(rows):
            qv = embedded.vectors[0]
        else:
            comparable = {}
    except Exception:
        qv, comparable = None, {}

    scored = []
    for r in rows:
        if r["id"] in excluded:
            continue
        mem = _row_memory(r)
        if mem["category"] in _CONTRAST_EXCLUDED_CATEGORIES:
            continue
        if not (mem["gist"] or "").strip():
            continue
        sal = effective_importance(mem)
        if sal < _CONTRAST_MIN_SALIENCE:
            continue
        score = sal
        score += 0.5 * abs(float(mem["valence"] or 0.0))
        score += 0.3 * float(mem["arousal"] or 0.0)
        ti = mem["turn_idx"]
        if ti is not None and current_turn_idx:
            score += 0.4 * _clamp((current_turn_idx - ti)
                                  / max(current_turn_idx, 1))
        else:
            # No place in play order (imported/authored past): as far from
            # the present as a memory gets.
            score += 0.4
        score -= 0.8 * _jaccard_text(
            query_text,
            f"{mem['gist']} {' '.join(mem['key_phrases'] or [])}")
        if qv is not None:
            # Semantic distance, once the vectors can carry it. The token
            # penalty above can only see DIFFERENT WORDS, and different words
            # routinely mean the same thing -- "the alley smelled of wet brick
            # and chip fat" against "the backstreet stank of damp masonry and
            # frying grease" shares nothing lexically and is the same memory.
            # A lexical axis calls that a perfect contrast; this one does not.
            fv = comparable.get(mem["id"])
            if fv is not None:
                score -= _CONTRAST_SEMANTIC * _cos(qv, fv)
        if here_cf and str(mem["location"] or "").strip().casefold() == here_cf:
            score -= 0.3
        ents = [str(e) for e in (mem["entities"] or []) if str(e).strip()]
        if ents and query_cf:
            present = sum(1 for e in ents if e.casefold() in query_cf)
            score -= 0.4 * (present / len(ents))
        scored.append((score, mem["id"], mem))
    scored.sort(key=lambda item: (-item[0], item[1]))
    out = []
    for score, _mid, mem in scored[:max(1, int(k))]:
        entry = dict(mem)
        entry["contrast_score"] = round(score, 4)
        out.append(entry)
    return out


def provenance_context_label(provenance):
    """The label a character's own context uses for this provenance class --
    'what_i_experienced' / 'what_i_was_told' / 'what_i_concluded' -- shared
    with the summary scopes so an unbidden memory speaks the same epistemic
    vocabulary the summaries already taught."""
    scope = summary_scope_for(provenance)
    for s, _field, label in _SUMMARY_SCOPES:
        if s == scope:
            return label
    return "what_i_experienced"


def recent_memory_buffer(chat_id, char_id, current_turn_idx, turns=4, limit=12, viewer_frame_id=_UNSET):
    # Fetch newest-first so a memory-dense window (many self/episodic/
    # inference rows in a short span) truncates its OLDEST rows against
    # `limit`, not its newest -- ORDER BY turn_idx, id ASC with LIMIT would
    # silently drop exactly the most recent memories (e.g. "I just escaped
    # aboard the ship") while keeping stale ones from a turn or two back,
    # which is precisely the wrong direction for a "recent memory" buffer
    # meant to keep a character's own decisions grounded in what most
    # recently happened. Reversed back to chronological order below since
    # every caller presents/reads this as an ordered narrative, not a
    # ranked list.
    # Exclude turn_idx >= current_turn_idx. A character's onset-time context
    # (perception/character decision for THIS turn) must never contain its own
    # committed memory of how this very turn resolved -- otherwise a single-step
    # reroll of a pre-commit stage on an already-committed turn would feed the
    # outcome back into the onset declaration (audit #10). The current turn has
    # not legitimately "happened" yet from the deciding mind's point of view.
    #
    # Recent-by-play-order is not the same as recent-by-diegetic-order: the
    # turn immediately before a frame jump can be an entirely different era,
    # so the frame filter in the seam is what stops a flash-forward's opening
    # turns pulling in the pre-jump present as "recent memory."
    rows = visible_memory_rows(
        chat_id, char_id,
        before_turn_idx=current_turn_idx,
        viewer_frame_id=viewer_frame_id,
        include_archived=False,
        since_turn_idx=max(0, current_turn_idx - turns),
        require_turn_idx=True,
    )
    # Truncate against `limit` from the NEWEST end, then hand back in
    # chronological order. Sorting ascending and slicing would drop exactly
    # the most recent memories ("I just escaped aboard the ship") and keep
    # stale ones from a turn or two back, which is the wrong direction for a
    # buffer meant to keep a character's own decisions grounded in what most
    # recently happened. Ordering after the seam rather than in SQL also means
    # the cap counts VISIBLE rows: it used to be applied before the frame
    # pass, so another era's memories consumed slots and shortened the buffer.
    rows.sort(key=lambda r: (r["turn_idx"], r["id"]), reverse=True)
    rows = list(reversed(rows[:limit]))
    return [_row_memory(r) for r in rows]

# ---- Memory Summaries ----

def get_memory_summary(chat_id, char_id, scope="autobiographical", *,
                       before_turn_idx=None):
    """The character's CURRENT summary for this scope: the latest window.

    Since v23 a scope holds one row per window rather than one row overall, so
    this orders. Behaviour is unchanged for every bank that existed at the
    migration -- each had exactly one row, which is trivially the latest.

    What this does NOT return is the character's life. The consolidator is told
    to merge the previous summary forward, but it is told just as firmly to shed
    low-salience detail, and measurement says shedding wins: successive live
    windows share 3-16% of their text. So the latest window is the latest
    CHAPTER, and under the pre-v23 singleton the chapters before it were
    overwritten -- 53 of the 67 live banks have no summary covering their
    opening turns, and never will. The windows behind the latest are what
    `search_memory_summaries` reaches and what
    `build_character_memory_context` now sends alongside this one.

    `end_turn_idx` first, `id` as the tiebreak: two windows can legitimately
    close on the same turn (different scopes are separate rows, but a rerun
    that lands on the same boundary updates in place, and a restore renumbers
    ids), so the later row wins.
    """
    cutoff_sql = ""
    args = [chat_id, char_id, scope]
    if before_turn_idx is not None:
        cutoff_sql = " AND end_turn_idx < ?"
        args.append(int(before_turn_idx))
    row = q("SELECT * FROM memory_summaries WHERE chat_id=? AND char_id=? "
            "AND scope=?" + cutoff_sql +
            " ORDER BY end_turn_idx DESC, id DESC LIMIT 1",
            tuple(args), one=True)
    if not row:
        return {"scope": scope, "start_turn_idx": 0, "end_turn_idx": 0, "summary": "",
                "key_phrases": [], "unresolved_threads": [], "updated": None}
    return {"scope": row["scope"], "start_turn_idx": row["start_turn_idx"], "end_turn_idx": row["end_turn_idx"],
            "summary": row["summary"], "key_phrases": _json_list(row["key_phrases"]),
            "unresolved_threads": _json_list(row["unresolved_threads"]), "updated": row["updated"]}

def search_memory_summaries(chat_id, char_id, query, k=3, *,
                            scope="autobiographical", before_turn_idx=None,
                            exclude_latest=True, embedded=None):
    """Rank a character's summary WINDOWS by semantic similarity to `query`.

    The layer above raw recall: which ERA of my life is this beat about. Every
    summary has carried a maintained embedding since summaries existed -- built
    from `_summary_retrieval_text`, re-embedded on a model change, carried
    verbatim through every archive and checkpoint -- and until v23 no retrieval
    path read a single one of them, because the table held exactly one row per
    character per scope and there was nothing to rank.

    Scoped exactly like `search_memories`:

    - **char_id** is the bank. A summary is one character's autobiography and
      is never comparable across characters.
    - **before_turn_idx** is the same exclusive cutoff the read seam applies.
      A window that closed at or after the deciding turn describes how this
      beat turned out, and a mind deciding turn N must not read it. Windows
      are ranked on `end_turn_idx` because that is when the window's knowledge
      became complete.
    - **exclude_latest** drops the window `get_memory_summary` already returns,
      so a caller that sends both does not send it twice. Turn it off to rank
      the whole history.

    A window whose vector was built by a different embedding model scores 0.0
    and is skipped rather than compared -- the same rule the memory rankings
    follow, for the same reason: a cross-model cosine is noise wearing the
    shape of a score.

    Returns [{...window..., "score": float}], best first, `k` at most.
    """
    rows = q("SELECT * FROM memory_summaries WHERE chat_id=? AND char_id=? "
             "AND scope=? ORDER BY end_turn_idx DESC, id DESC",
             (chat_id, char_id, scope))
    if not rows:
        return []
    if before_turn_idx is not None:
        cutoff = int(before_turn_idx)
        rows = [r for r in rows if (r["end_turn_idx"] or 0) < cutoff]
    # "Latest" means latest VISIBLE window. Applying this before the temporal
    # cutoff drops the wrong row on a rerun: the future global latest vanishes
    # at the cutoff and the visible latest is then returned twice.
    if exclude_latest:
        rows = rows[1:]
    rows = [r for r in rows if (r["summary"] or "").strip()]
    if not rows:
        return []
    # `embedded` lets a caller that already vectorised this same query hand the
    # batch over; vectors[0] is the query in both this function's own call and
    # in search_memories', which is what makes them shareable.
    if embedded is None or not (getattr(embedded, "vectors", None) or ()):
        embedded = embed_texts_meta([str(query or "")])
    qv = np.asarray(embedded.vectors[0], dtype=np.float32)
    live_model = embedded.model_key
    scored = []
    for r in rows:
        if (r["embedding_model"] or "") != live_model:
            continue
        v = _vec(r["embedding"])
        if v is None or v.shape != qv.shape:
            continue
        scored.append((_cos(qv, v), r))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    out = []
    for score, r in scored[:k]:
        out.append({
            "scope": r["scope"],
            "start_turn_idx": r["start_turn_idx"],
            "end_turn_idx": r["end_turn_idx"],
            "summary": r["summary"],
            "key_phrases": _json_list(r["key_phrases"]),
            "unresolved_threads": _json_list(r["unresolved_threads"]),
            "updated": r["updated"],
            "score": float(score),
        })
    return out


# Clause boundary, content-word regex and stopwords all come from the pack
# (`mind.memory.*`): "a sentence ends at a full stop followed by a capital"
# is an English typographic rule, and against Japanese punctuation it found
# one clause per summary and therefore one undifferentiated support set.
# Two shared content words is coincidence in prose this dense; three is a
# claim about the same thing. Calibrated against the live corpus rather than
# guessed -- at two, every clause matched every memory in its own window.
_SUPPORT_MIN_OVERLAP = 3
_SUPPORT_MAX_REFS = 3


def _content_words(text):
    return {w for w in _ling("_SUPPORT_WORD_RE").findall(
                str(text or "").casefold())
            if w not in _ling("_SUPPORT_STOPWORDS")}


def derive_summary_support(summary, memories):
    """Which of this window's memories stand behind each clause of a summary.

    Summaries move appraisal and speech. They are deliberately barred from
    reinforcing durable belief -- which contains most of the danger -- but a
    consolidator sentence that no memory supports still reaches the character
    and currently leaves no trace when it does. This is the trace.

    Derived HOST-SIDE, from the same window the consolidator was given, by
    content-word overlap. Deliberately not a model call and deliberately not
    embeddings: the question is "which stored rows does this sentence actually
    talk about", a lexical question with a checkable answer, and an
    audit trail produced by the same kind of process it audits is not one.

    An empty `support_refs` is a RESULT, not a failure -- it says this clause
    generalises, compresses across several rows, or was invented. The three
    are not distinguished here, because distinguishing them is a judgement and
    this is a measurement. What matters is that the clause is now countable.

    Refs are `event_key`s rather than row ids, so they survive checkpoint
    restore (delete-and-reinsert changes every id) and chat branching without
    remapping -- the same reasoning that keeps disputes off id-keyed edges.
    """
    text = " ".join(str(summary or "").split())
    if not text:
        return []
    rows = []
    for mem in memories or []:
        if not isinstance(mem, dict):
            continue
        ref = str(mem.get("event_key") or "").strip()
        if not ref:
            continue
        words = _content_words(mem.get("gist")) | _content_words(mem.get("content"))
        for phrase in (mem.get("key_phrases") or []):
            words |= _content_words(phrase)
        for entity in (mem.get("entities") or []):
            words |= _content_words(entity)
        rows.append((ref, words, mem.get("provenance")))
    out = []
    for clause in [c.strip() for c in _ling("_CLAUSE_SPLIT").split(text)
                   if c.strip()]:
        cw = _content_words(clause)
        scored = sorted(
            ((len(cw & words), ref, prov) for ref, words, prov in rows
             if len(cw & words) >= _SUPPORT_MIN_OVERLAP),
            key=lambda item: (-item[0], item[1]))[:_SUPPORT_MAX_REFS]
        out.append({
            "claim": clause,
            "support_refs": [ref for _n, ref, _p in scored],
            # The epistemic class of the STRONGEST supporter. A clause built
            # on what the character was told must not read as something they
            # saw, and with no supporter at all it is left blank rather than
            # defaulted to first-hand -- the safest wrong answer here is the
            # one that claims the least.
            "epistemic_origin": (provenance_context_label(scored[0][2])
                                 if scored else ""),
        })
    return out


def summary_support(chat_id, char_id, scope="autobiographical", *,
                    end_turn_idx=None):
    """The stored per-clause support for a summary, or []. Never raises on a
    malformed blob -- an unreadable audit trail must not make the summary it
    describes unreadable."""
    sql = ("SELECT support FROM memory_summaries WHERE chat_id=? AND char_id=? "
           "AND scope=?")
    params = [chat_id, char_id, scope]
    if end_turn_idx is not None:
        sql += " AND end_turn_idx=?"
        params.append(int(end_turn_idx))
    row = q(sql + " ORDER BY end_turn_idx DESC, id DESC", tuple(params), one=True)
    if not row:
        return []
    try:
        parsed = json.loads(row["support"] or "[]")
    except (TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def save_memory_summary(chat_id, char_id, summary, *, scope="autobiographical", start_turn_idx=0,
                        end_turn_idx=0, key_phrases=None, unresolved_threads=None,
                        embedding=None, embedding_model=None, embedding_dim=None,
                        support=None):
    key_phrases = key_phrases or []
    unresolved_threads = unresolved_threads or []
    support = support or []
    # Checkpoint/export restore passes the previously stored vector back
    # in verbatim (raw bytes) so a restore never re-embeds -- every
    # normal caller omits it and embeds exactly as before.
    if embedding is None or not embedding_model:
        retrieval_text = _summary_retrieval_text(summary, key_phrases, unresolved_threads)
        embedded = embed_texts_meta([retrieval_text])
        embedding = _blob(embedded.vectors[0])
        embedding_model = embedded.model_key
        embedding_dim = embedded.dimensions
    qi("""INSERT INTO memory_summaries(chat_id,char_id,scope,start_turn_idx,end_turn_idx,summary,
        key_phrases,unresolved_threads,support,embedding,embedding_model,embedding_dim,updated)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(chat_id,char_id,scope,end_turn_idx) DO UPDATE SET
        start_turn_idx=excluded.start_turn_idx, end_turn_idx=excluded.end_turn_idx,
        summary=excluded.summary, key_phrases=excluded.key_phrases,
        unresolved_threads=excluded.unresolved_threads, support=excluded.support,
        embedding=excluded.embedding,
        embedding_model=excluded.embedding_model, embedding_dim=excluded.embedding_dim,
        updated=excluded.updated""",
       (chat_id, char_id, scope, start_turn_idx, end_turn_idx, summary or "",
        json.dumps(key_phrases, ensure_ascii=False), json.dumps(unresolved_threads, ensure_ascii=False),
        json.dumps(support, ensure_ascii=False),
        embedding, embedding_model, embedding_dim, time.time()))
    if embedding_model == "cheap:crc32:256":
        # Queued by identity rather than rowid: this statement UPSERTs on
        # (chat, char, scope, end_turn_idx), so `qi`'s lastrowid is not
        # reliably this row's id on the conflict path.
        row = q("SELECT id FROM memory_summaries WHERE chat_id=? AND char_id=? "
                "AND scope=? AND end_turn_idx=?",
                (chat_id, char_id, scope, end_turn_idx), one=True)
        if row:
            note_failed_embedding_write("memory_summaries", [row["id"]])


def _portable_memory_event_key(mem):
    """A deterministic event handle for a legacy row that has none.

    Row ids are database-local and change on archive/checkpoint restore.  The
    fields below are the portable identity of the remembered event; once
    written, the resulting key travels in every existing dump format.
    """
    document = {
        "turn_idx": mem.get("turn_idx"),
        "kind": mem.get("kind") or "episodic",
        "category": mem.get("category") or "episode",
        "provenance": mem.get("provenance") or "witnessed",
        "content": " ".join(str(mem.get("content") or "").split()),
        "gist": " ".join(str(mem.get("gist") or "").split()),
        "key_phrases": list(mem.get("key_phrases") or []),
        "entities": list(mem.get("entities") or []),
        "location": str(mem.get("location") or ""),
        "emotional_context": str(mem.get("emotional_context") or ""),
    }
    raw = json.dumps(document, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":"))
    return "event:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def backfill_missing_memory_event_keys(chat_id, char_id=None):
    """Give legacy memories stable, portable citation handles.

    Exact duplicate legacy rows receive deterministic occurrence suffixes in
    row order.  Once assigned, dumps/restores carry the key verbatim, so the
    suffix is never recomputed from a new database's row ids.
    """
    args = [chat_id]
    scope = "chat_id=? AND event_key=''"
    if char_id is not None:
        scope += " AND char_id=?"
        args.append(char_id)
    rows = q("SELECT * FROM memories WHERE " + scope +
             " ORDER BY char_id, id", tuple(args))
    if not rows:
        return 0
    used = defaultdict(int)
    repaired = 0
    with transaction():
        for row in rows:
            mem = _row_memory(row)
            base = _portable_memory_event_key(mem)
            used[(row["char_id"], base)] += 1
            ordinal = used[(row["char_id"], base)]
            key = base if ordinal == 1 else f"{base}:{ordinal}"
            # A generated key can collide with an already-keyed identical
            # import. Keep the handle stable and advance only the suffix.
            while q("SELECT 1 FROM memories WHERE chat_id=? AND char_id=? "
                    "AND event_key=?", (chat_id, row["char_id"], key), one=True):
                ordinal += 1
                key = f"{base}:{ordinal}"
            qi("UPDATE memories SET event_key=? WHERE id=? AND event_key=''",
               (key, row["id"]))
            repaired += 1
    return repaired

def _with_reading(mem, current_turn_idx=None):
    """Project one stored row as an explicitly PAST character memory.

    Present observations use ``current:<perceiver>:<n>`` ids. Memories cite
    their durable ``event_key`` and say ``remembered_past`` in the data itself,
    so a model does not have to infer temporal status from which parent list
    happened to contain the row. The numeric ``id`` stays host-only.

    The memory itself remains unchanged -- content, gist, provenance and
    salience all stay as recorded -- and a later re-reading travels beside it
    under its own key. A mind that was deceived holds both the experience and
    the correction.

    The key is phrased as the character's own voice, matching the
    `it_comes_back_to_me` / `i_suspect` precedent -- epistemic status carried
    by the key rather than by prose a model can drop.

    WHAT THIS DELIBERATELY DOES NOT PROJECT. Three fields were carried here for
    no reader on the deciding side, measured across the live banks:

      * ``key_phrases`` -- 12 short cues per row, 80% of them already verbatim
        in the gist/details beside them, and never once named in the 61 KB
        character prompt. Its consumers are ``memory_retrieval_fts`` and
        ``_retrieval_text`` -- retrieval machinery, not the mind deciding.
      * ``category`` -- one host-side reader (``promise_memories``' SQL), and
        across 900 corpus rows only four (category, epistemic_origin) pairs
        occur, so it restates a label the row already carries.
      * ``memory_form`` -- the constant ``"episode"`` on every row this
        function projects. Summaries set their own, so ABSENCE now means
        episode and the distinction survives.

    The columns stay written and stay indexed; only the projection narrows, so
    recall quality cannot move by construction. Together with the gist rule
    below this is 5.8 KB of a 26.8 KB delivered block (chat 72, 24 rows).
    """
    # Model projection only.  ``dict(mem)`` used to leak database ids,
    # access counters, archive state, embedding metadata and retrieval scores
    # into the character's mind.  Those are host diagnostics, not memories.
    out = {
        "memory_ref": str(mem.get("event_key") or ""),
        # RESTORED after measurement. Removing this per-row constant was the one
        # compaction that cost something: `appraisal.goal_impacts[].evidence` is
        # grounded namespace="present", so a memory_ref cited there is dropped as
        # ungrounded and the impact zeroed -- past evidence mis-laned as present,
        # 0 occurrences before and 2 after across three live turns, alongside the
        # same lane failure in tools/benchmark_memory_temporal.py's anomaly_now.
        # The label never varies, so it cannot ORDER anything (`when` does that);
        # what it does is mark the lane, per row, at the point of use. 0.9 KB of
        # a 26 KB block is a cheap price for a discrimination the engine cannot
        # re-impose downstream -- a dropped citation is evidence already lost.
        "temporal_status": "remembered_past",
        "epistemic_origin": provenance_context_label(mem.get("provenance")),
        "gist": mem.get("gist") or "",
        "details": mem.get("content") or "",
        "entities": list(mem.get("entities") or []),
        "location": mem.get("location") or "",
        "confidence": float(mem.get("confidence") or 0.0),
        "felt_importance": float(mem.get("importance") or
                                 mem.get("salience") or 0.0),
        "affect_before": {
            "label": mem.get("emotional_context") or "",
            "valence": float(mem.get("valence") or 0.0),
            "arousal": float(mem.get("arousal") or 0.0),
        },
        "affect_after_encoding": {
            "valence": float(mem.get("encoding_valence") or 0.0),
            "arousal": float(mem.get("encoding_arousal") or 0.0),
        },
    }
    if payload_legacy("fields"):
        out["memory_form"] = "episode"
        out["category"] = mem.get("category") or "episode"
        out["key_phrases"] = list(mem.get("key_phrases") or [])
    if not payload_legacy("gist"):
        # A gist that is a PREFIX of its own details is not a low-resolution
        # recall, it is the first sentence twice. Measured on chat 72's live
        # bank: 4% byte-identical, 77% a substring, median length ratio 0.52 --
        # so the consolidator does compress, and the rows where it did not are
        # the ones that carry nothing the details below do not already say.
        # Dropped only in that case; a genuinely condensed gist survives.
        gist = str(out.get("gist") or "").strip()
        details = str(out.get("details") or "").strip()
        if gist and details and gist.casefold() in details.casefold():
            out.pop("gist", None)
    out = {k: v for k, v in out.items()
           if v not in ("", [], {}) or k in {
               "memory_ref", "temporal_status", "memory_form",
               "epistemic_origin", "confidence", "felt_importance"}}
    ti = mem.get("turn_idx")
    if ti is None:
        out["when"] = "before this story's recorded turns"
    elif current_turn_idx is not None:
        age = max(1, int(current_turn_idx) - int(ti))
        out["when"] = "about 1 beat ago" if age == 1 else f"about {age} beats ago"
    dispute = mem.get("disputed")
    if not dispute:
        return out
    out["i_now_read_this_differently"] = dispute.get("reading") or ""
    if dispute.get("count", 0) > 1:
        out["times_i_have_reconsidered_it"] = int(dispute["count"])
    return out


def _beats_ago_span(current_turn_idx, start_turn_idx, end_turn_idx):
    """When an earlier window happened, in the character's own units.

    RELATIVE, never the absolute turn index, and that is a firewall rule rather
    than a style choice: `turn_idx` is GLOBAL play order shared by every frame,
    so an absolute number tells a character where a flash-forward or flashback
    sits in the story's construction -- something no mind in the fiction has any
    way to know. Every other dated thing in the payload says "about N beats ago"
    for the same reason (see `_unbidden_entry`).
    """
    if current_turn_idx is None:
        return ""
    oldest = int(current_turn_idx) - int(start_turn_idx or 0)
    newest = int(current_turn_idx) - int(end_turn_idx or 0)
    if newest <= 0:
        # Defensive only: every read seam must withhold a window that closed at
        # or after the deciding turn. Never relabel future knowledge "just now".
        return ""
    if oldest == newest:
        return f"about {oldest} beats ago"
    return f"between about {newest} and {oldest} beats ago"


def _summary_id(scope, end_turn_idx):
    """A citable, explicitly-past id for one delivered summary window."""
    return f"summary:{scope}:{int(end_turn_idx or 0)}"


def _origin_on_drift(chat_id, char_id, current_turn_idx, active_state, *,
                     earlier_ids=()):
    """Surface the character's ORIGIN summary window when a drift signal fires.

    An origin is not a similarity match: a character's foundational era is
    frequently dissimilar to whatever is happening now, which is exactly when
    it should still be present. Top-k similarity ranking drops it in the beats
    where it matters most (UNBUILT §1.21).

    Three drift signals, all already tracked in the active state:

    - **goal_held**: the same ungoverned goal for 12+ beats (the character is
      stuck in a rut, not pursuing something).
    - **project adrift**: a held project has gone 8+ beats without anything
      serving it (the character has lost the thread of what they set out to do).
    - **mood sign-flip**: the current mood's valence has flipped sign from the
      character's baseline (a despairing character who was once hopeful, or
      vice versa) -- the moment a person reaches for who they were before the
      current stretch swallowed them.

    When any signal fires, the earliest first-hand summary window is fetched
    and included under ``where_i_came_from``. It is NOT added to
    ``earlier_in_my_life`` because those are similarity-ranked; the origin is
    surfaced for a different reason and should not compete for a similarity
    slot. Absent (not empty) when no signal fires or when there is no origin
    window to reach.

    ``earlier_ids`` is the set of ``end_turn_idx`` values already in the
    ``earlier_in_my_life`` payload, so the origin is not sent twice when
    similarity ranking happened to reach it.
    """
    if not isinstance(active_state, dict):
        return {}
    drift = False
    # Signal 1: same goal held too long.
    if active_state.get("goal_held"):
        drift = True
    # Signal 2: a project has gone adrift.
    for p in (active_state.get("projects") or []):
        if isinstance(p, dict) and p.get("adrift"):
            drift = True
            break
    # Signal 3: mood sign-flip from baseline.
    mood = str(active_state.get("mood") or "").strip().casefold()
    if mood and not drift:
        # The baseline is "neutral" unless the character's stored affect
        # says otherwise. A sign-flip is when a clearly positive mood gives
        # way to a clearly negative one or vice versa, compared to what the
        # character's affect surface has been tracking. We use the mood label
        # vocabulary the engine already maintains.
        _negative = any(w in mood for w in (
            "afraid", "anxious", "angry", "ashamed", "despair", "disgust",
            "fear", "grief", "guilt", "horror", "rage", "sad", "shame",
            "terror", "worried", "dread", "misery", "anguish", "desolate",
        ))
        _positive = any(w in mood for w in (
            "calm", "content", "delighted", "ecstatic", "elated", "excited",
            "glad", "happy", "joy", "love", "peaceful", "pleased", "proud",
            "relieved", "satisfied", "serene", "triumphant", "warm",
        ))
        # Only a clear signal counts: a mood that is clearly one or the other,
        # and the character's active_state also carries valence from resolved
        # affect. We check the valence sign flip against the stored baseline.
        if _negative or _positive:
            surface = (active_state.get("affect") or {}).get("surface") or {}
            valence = float(surface.get("valence") or 0.0)
            baseline = (active_state.get("affect") or {}).get("baseline") or {}
            base_v = float(baseline.get("valence") or 0.0)
            # A sign flip: current and baseline are on opposite sides of zero,
            # and the current is not near zero (which is neutral, not a flip).
            if abs(valence) > 0.15 and (valence * base_v) < 0:
                drift = True
    if not drift:
        return {}
    # Fetch the earliest first-hand summary window.
    rows = q("SELECT * FROM memory_summaries WHERE chat_id=? AND char_id=? "
             "AND scope=? AND end_turn_idx < ? "
             "ORDER BY end_turn_idx ASC, id ASC LIMIT 1",
             (chat_id, char_id, SUMMARY_SCOPE_FIRSTHAND,
              int(current_turn_idx)))
    if not rows:
        return {}
    r = rows[0]
    if not (r["summary"] or "").strip():
        return {}
    # Do not duplicate what earlier_in_my_life already carries.
    if (r["end_turn_idx"] or 0) in earlier_ids:
        return {}
    return {"where_i_came_from": {
        "what_i_lived_through_then": r["summary"] or "",
        "summary_id": _summary_id(r["scope"], r["end_turn_idx"]),
        "temporal_status": "remembered_past",
        "memory_form": "summary",
        "epistemic_origin": summary_context_label(r["scope"]),
        "when": _beats_ago_span(current_turn_idx, r["start_turn_idx"],
                                r["end_turn_idx"]),
    }}


def build_character_memory_context(chat_id, char_id, current_turn_idx, current_view, active_state, *,
                                   recent_turns=4, recall_limit=_RECALL_LIMIT, here=None,
                                   in_sight=None, absorption=0.0,
                                   ponder_query=""):
    active_state = active_state or {}
    # Legacy banks predate event_key. Repair only the active mind's missing
    # handles before any row is projected, so every delivered citation is
    # stable across checkpoint restore and portable archive import.
    backfill_missing_memory_event_keys(chat_id, char_id)
    # Sensory absorption narrows deliberative recall while preserving a small
    # automatic-recognition lane.  A body monopolising attention should reduce
    # how many old chapters can be worked through, not erase a salient face,
    # warning, or promise already associated with the present cue.
    absorption = _clamp(absorption)
    if absorption >= 0.7:
        recent_limit, recall_limit, summary_limit = 4, min(recall_limit, 4), 0
    elif absorption >= 0.35:
        recent_limit, recall_limit, summary_limit = 8, min(recall_limit, 8), 1
    else:
        recent_limit, summary_limit = 12, _SUMMARY_RECALL_LIMIT
    recent = recent_memory_buffer(
        chat_id, char_id, current_turn_idx, turns=recent_turns,
        limit=recent_limit)
    recent_ids = {m["id"] for m in recent}
    summary = get_memory_summary(
        chat_id, char_id, before_turn_idx=current_turn_idx)
    # P8: the other two epistemic classes travel as their own labelled fields
    # rather than being melted into the first-hand paragraph. A character must
    # be able to tell what they saw from what they were told from what they
    # worked out -- collapsing them is the same layer-collapse the engine
    # polices between minds, happening inside one.
    provenance_summaries = {}
    summary_citations = {}
    for scope, _field, label in _SUMMARY_SCOPES:
        if scope == SUMMARY_SCOPE_FIRSTHAND:
            continue
        scoped_summary = get_memory_summary(
            chat_id, char_id, scope, before_turn_idx=current_turn_idx)
        text = str(scoped_summary.get("summary") or "").strip()
        if text:
            provenance_summaries[label] = text
            summary_citations[label] = {
                "summary_id": _summary_id(
                    scope, scoped_summary.get("end_turn_idx")),
                "temporal_status": "remembered_past",
                "when": _beats_ago_span(
                    current_turn_idx, scoped_summary.get("start_turn_idx"),
                    scoped_summary.get("end_turn_idx")),
                "epistemic_origin": label,
                "memory_form": "summary",
            }
    # The beat is the query; what the character BRINGS to it travels beside it
    # as aspects, each with its own ranking. Concatenated, they did nothing:
    # the view runs a median ~1,015 characters and a mood fragment 10-60, so
    # the combined vector sat at cosine 0.994 to the view alone and the mood
    # reached recall only through stray shared n-grams. See search_memories.
    query_text = str(current_view or "").strip()
    aspects = [
        ("what you are trying to do", str(active_state.get("goal") or "")),
        ("how you are feeling", str(active_state.get("mood") or "")),
        ("what is still unsettled",
         " ".join(summary.get("unresolved_threads") or [])),
    ]
    if not query_text:
        # No perception this beat (a character gated out of the scene): fall
        # back to the aspects as the query rather than retrieving on "".
        query_text = " ".join(t for _l, t in aspects if t)
    # current_turn_idx is required here (recent_memory_buffer arithmetic above
    # would already fail on None), so search_memories' F1 turn cutoff always
    # fires on this path -- the character context can never see turn N's own
    # committed memories while deciding turn N, reroll or not.
    # One embedding for everything ranked from this beat. search_memories has
    # always batched the query with its aspects; the summary windows rank
    # against the same query vector, so sharing the batch is what keeps the
    # window layer free rather than a second round trip per character per beat.
    _aspects = [(str(lbl), str(txt).strip()) for lbl, txt in aspects
                if str(txt or "").strip()]
    embedded = embed_texts_meta([query_text or "memory"]
                                + [txt for _lbl, txt in _aspects])
    recalled = search_memories(chat_id, char_id, query_text, k=recall_limit,
                               include_archived=True, current_turn_idx=current_turn_idx,
                               chronological=True, here=here, in_sight=in_sight,
                               aspects=aspects, embedded=embedded,
                               record_access=True)
    recalled = [m for m in recalled if m["id"] not in recent_ids]
    if len(recalled) > recall_limit:
        recalled = sorted(
            sorted(recalled, key=lambda m: float(m.get("score") or 0.0),
                   reverse=True)[:recall_limit],
            key=lambda m: (m.get("turn_idx") is None,
                           m.get("turn_idx") if m.get("turn_idx") is not None
                           else 10**12, m.get("id") or 0))
    # A character may deliberately set ONE query on the previous character
    # turn. This is an additive, explicitly-labelled retrieval lane: normal
    # cue/mood/goal recall above remains untouched. It costs an embedding call
    # only when a ponder is actually pending, which should be exceptional.
    ponder_query = " ".join(str(ponder_query or "").split())[:240]
    pondered = []
    if ponder_query:
        pondered = search_memories(
            chat_id, char_id, ponder_query, k=4, include_archived=True,
            current_turn_idx=current_turn_idx, chronological=True,
            here=here, in_sight=in_sight, record_access=True)
        # Chronological-neighbour expansion may return k+2. Deliberate recall
        # is a small supplement, not a second full memory payload.
        if len(pondered) > 4:
            pondered = sorted(
                sorted(pondered, key=lambda m: float(m.get("score") or 0.0),
                       reverse=True)[:4],
                key=lambda m: (m.get("turn_idx") is None,
                               m.get("turn_idx")
                               if m.get("turn_idx") is not None else 10**12,
                               m.get("id") or 0))
    # The layer between the summary and the raw rows: which EARLIER stretch of
    # this life the present beat is about.
    #
    # `summary` above is only the latest window, and a window is in practice
    # about its own turns -- the consolidator is told to merge the previous
    # summary in, but it is told just as firmly to shed low-salience detail, and
    # shedding wins. Measured across the six live window pairs, successive
    # windows share 3-16% of their text and sit at cosine 0.57-0.88; the
    # Doctor's second window recaps the first in a single clause and is
    # otherwise entirely about its own ten turns.
    #
    # So the singleton design was not holding a life story, it was holding the
    # most recent chapter of one, and overwriting the rest. 53 of the 67 live
    # banks have no summary at all over their opening turns. Windows stopped the
    # loss; this is what reads what they kept.
    #
    # First-hand scope only. Hearsay and surmise have windows too, and folding
    # them in here would put three provenances in one field -- the same collapse
    # `provenance_summaries` exists to prevent.
    earlier = (search_memory_summaries(
        chat_id, char_id, query_text, k=summary_limit,
        scope=SUMMARY_SCOPE_FIRSTHAND, before_turn_idx=current_turn_idx,
        exclude_latest=True, embedded=embedded) if summary_limit else [])
    # Chronological, oldest first: these are stretches of a life, and rank order
    # would present it out of sequence. Ranking has already done its work by
    # choosing WHICH ones. Absent rather than empty when there are none, like
    # the provenance summaries below -- an empty key still spends attention.
    earlier_payload = {"earlier_in_my_life": [
        {"what_i_lived_through_then": w.get("summary") or "",
         "summary_id": _summary_id(
             w.get("scope") or SUMMARY_SCOPE_FIRSTHAND,
             w.get("end_turn_idx")),
         "temporal_status": "remembered_past",
         "memory_form": "summary",
         "epistemic_origin": summary_context_label(
             w.get("scope") or SUMMARY_SCOPE_FIRSTHAND),
         "when": _beats_ago_span(current_turn_idx, w.get("start_turn_idx"),
                                 w.get("end_turn_idx"))}
        for w in sorted(earlier, key=lambda w: (w.get("end_turn_idx") or 0))
    ]} if earlier else {}
    # Origin-era retrieval on drift (UNBUILT §1.21).
    #
    # A character's foundational era is frequently DISSIMILAR to whatever is
    # happening now, which is exactly when it should still be present -- a
    # character who has lost the thread of why they set out needs to remember
    # the beginning, and similarity-based top-k drops it in the beats where it
    # matters most. An origin is not a similarity match.
    #
    # Rather than always including the origin (which costs a slot every beat
    # for something usually irrelevant) or waiting for an absolute floor the
    # compressed cosine band cannot provide, surface the origin window when a
    # drift signal fires: the same goal held for 12+ beats, a project gone
    # adrift for 8+ beats, or a mood sign-flip from the character's baseline.
    # These are exactly the moments a person reaches for who they were before
    # the current stretch swallowed them.
    origin_payload = _origin_on_drift(
        chat_id, char_id, current_turn_idx, active_state,
        earlier_ids={w.get("end_turn_idx") for w in earlier})
    if str(summary.get("summary") or "").strip():
        summary_citations["autobiographical_summary"] = {
            "summary_id": _summary_id(
                SUMMARY_SCOPE_FIRSTHAND, summary.get("end_turn_idx")),
            "temporal_status": "remembered_past",
            "when": _beats_ago_span(
                current_turn_idx, summary.get("start_turn_idx"),
                summary.get("end_turn_idx")),
            "epistemic_origin": summary_context_label(
                SUMMARY_SCOPE_FIRSTHAND),
            "memory_form": "summary",
        }
    row_ids = {
        str(m.get("id")): str(m.get("event_key") or "")
        for m in (*recent, *recalled, *pondered)
        if m.get("id") is not None and str(m.get("event_key") or "")
    }
    normal_refs = {str(m.get("event_key") or "")
                   for m in (*recent, *recalled)}
    ponder_refs = [str(m.get("event_key") or "") for m in pondered
                   if str(m.get("event_key") or "")]
    recent_projected = [_with_reading(m, current_turn_idx) for m in recent]
    # A recent-life stream must be one chronological row per experienced beat,
    # not a turn-sized blob of episode + durable quote + self duplicate +
    # conclusion.  Keep the epistemic side records available, but in their own
    # lanes so neither chronology nor provenance has to be reconstructed by the
    # character model.
    recent_experienced = [
        m for m in recent_projected
        if m.get("epistemic_origin") == "what_i_experienced"]
    recent_received = [
        m for m in recent_projected
        if m.get("epistemic_origin") == "what_i_was_told"]
    recent_conclusions = [
        m for m in recent_projected
        if m.get("epistemic_origin") == "what_i_concluded"]
    recalled_projected = [
        _with_reading(m, current_turn_idx) for m in recalled]
    for item in (*recent_projected, *recalled_projected):
        if str(item.get("memory_ref") or "") in ponder_refs:
            item["retrieval_origin"] = [
                "normal_recall", "deliberate_ponder"]
    ponder_additional = []
    for mem in pondered:
        ref = str(mem.get("event_key") or "")
        if ref in normal_refs:
            continue
        item = _with_reading(mem, current_turn_idx)
        item["retrieval_origin"] = ["deliberate_ponder"]
        ponder_additional.append(item)
    ponder_payload = ({"deliberate_recall": {
        "query_i_chose_last_turn": ponder_query,
        "temporal_status": "remembered_past",
        "retrieval_origin": "deliberate_ponder",
        "result_refs": ponder_refs,
        "additional_episodes": ponder_additional,
        # Results do not force another query, but a genuinely new uncertainty
        # may be pondered immediately; optionality lives in the explicit act.
        "may_set_another_ponder_this_turn": True,
    }} if ponder_query else {})
    score_rows = {}
    for mem in (*recalled, *pondered):
        ref = str(mem.get("event_key") or "")
        if ref:
            score_rows[ref] = max(
                score_rows.get(ref, float("-inf")),
                float(mem.get("score") or 0.0))
    return {
        # Host-only registry. character.py removes it before serialization.
        "_internal": {
            "row_ids": row_ids,
            "retrieved_ids": [
                m.get("id") for m in (*recent, *recalled, *pondered)
                              if m.get("id") is not None],
            "scores": score_rows,
        },
        "unresolved_from_past": {
            "temporal_status": "remembered_past",
            "items": list(dict.fromkeys([
                *[str(item) for item in (active_state.get("active_concerns") or [])
                  if str(item).strip()],
                *[str(item) for item in (summary.get("unresolved_threads") or [])
                  if str(item).strip()],
            ]))[:6],
        },
        "recent_episodes": recent_experienced,
        **({"recent_received_information": recent_received}
           if recent_received else {}),
        **({"recent_conclusions": recent_conclusions}
           if recent_conclusions else {}),
        "recalled_old_memories": recalled_projected,
        # First-hand only. What reached this character through someone else's
        # account, and what they worked out for themselves, are carried
        # separately below and must not be folded in here.
        "autobiographical_summary": summary.get("summary") or "",
        "summary_key_phrases": summary.get("key_phrases") or [],
        "unresolved_threads": summary.get("unresolved_threads") or [],
        **({"summary_citations": summary_citations}
           if summary_citations else {}),
        **earlier_payload,
        **origin_payload,
        **ponder_payload,
        **provenance_summaries,
    }

# Views that record no perceptible event. Matched on the engine's OWN
# placeholders rather than on prose: `agents/perception.py` writes "an
# unspecified area" when it cannot name a room, and `agents/character.py`
# falls back to "You register nothing new this beat." Both mean the same
# thing -- this mind perceived nothing this beat -- and neither is an episode.
#
# Lives here rather than in `commit.py` (which owns the write-side rule and
# imports it back) because consolidation needs the same answer. Banks written
# before the write-side guard still carry these rows -- 369 across the live
# corpus -- and a consolidator handed ten of them summarises an absence into
# prose, which is then handed to a character as something they lived through.
_EMPTY_VIEW_MARKERS = (
    "you are in an unspecified area",
    "you register nothing new",
)


def _empty_view_markers():
    """The phrases that mean "nothing happened", in every installed language.

    The literals above are English, so a Japanese empty view matched none of
    them and was consolidated into autobiography -- an absence written up as
    something the character lived through, which is the exact failure this
    guard exists to prevent. The English strings are KEPT rather than
    replaced: rows written before packs existed still carry them.
    """
    from language_runtime import compositor_value, installed_language_packs

    markers = list(_EMPTY_VIEW_MARKERS)
    for language_id in installed_language_packs():
        try:
            templates = compositor_value("templates", language_id)
        except Exception:
            continue
        phrase = str(templates.get("narrator_nothing") or "").strip()
        if phrase:
            markers.append(phrase.casefold().rstrip("。."))
    return tuple(dict.fromkeys(markers))


def _is_empty_view(text):
    """True when a perception view records no event worth remembering."""
    body = " ".join(str(text or "").split()).strip().casefold().rstrip("。.")
    if not body:
        return True
    return any(body == m or body.startswith(m) and len(body) < len(m) + 25
               for m in _empty_view_markers())


def _substantive(memories):
    """The memories in this window that record something that happened."""
    return [m for m in memories
            if not _is_empty_view(m.get("content") or m.get("gist") or "")]


def _write_consolidated_window(chat_id, char_id, char_name, memories, previous_summary):
    """The consolidator call and the rows it produces, for ONE window.

    Shared by the forward path (`consolidate_character_memory`, which then
    archives) and the backward one (`backfill_memory_summary_windows`, which
    must not). Factored out when the second caller arrived rather than
    duplicated: the epistemic-scope rule below is the kind of thing that gets
    fixed in one copy.

    Returns the parsed consolidator result.
    """
    payload = {
        "character": char_name,
        "previous_summary": previous_summary,
        "memories_chronological": [
            {"id": m["id"], "turn_idx": m["turn_idx"], "category": m["category"],
             "provenance": m["provenance"], "salience": m["salience"], "confidence": m["confidence"],
             "gist": m["gist"], "details": m["content"], "key_phrases": m["key_phrases"],
             "entities": m["entities"], "location": m["location"], "emotional_context": m["emotional_context"]}
            for m in memories
        ],
    }
    raw = chat_complete("utility", get_prompt("memory_consolidate"),
                        json.dumps(payload, ensure_ascii=False), temperature=0.1, max_tokens=5000)
    try:
        result = json.loads(raw)
    except Exception:
        match = re.search(r"\{.*\}", raw or "", re.S)
        if not match:
            raise RuntimeError("Memory consolidator returned invalid JSON")
        result = json.loads(re.sub(r",\s*([}\]])", r"\1", match.group(0)))
    start_turn = min(m["turn_idx"] for m in memories)
    end_turn = max(m["turn_idx"] for m in memories)
    # One row per epistemic class. The first-hand row is written
    # unconditionally, even when this window produced nothing first-hand,
    # because maybe_consolidate_character_memory reads ITS end_turn_idx as the
    # cursor -- skip it on a hearsay-only window and the same memories
    # re-consolidate forever.
    present = {summary_scope_for(m.get("provenance")) for m in memories}
    for scope, field, _label in _SUMMARY_SCOPES:
        text = str(result.get(field) or "").strip()
        if scope != SUMMARY_SCOPE_FIRSTHAND and not text and scope not in present:
            continue
        save_memory_summary(
            chat_id, char_id, text, scope=scope,
            start_turn_idx=start_turn, end_turn_idx=end_turn,
            key_phrases=(result.get("key_phrases") or []
                         if scope == SUMMARY_SCOPE_FIRSTHAND else []),
            unresolved_threads=(result.get("unresolved_threads") or []
                                if scope == SUMMARY_SCOPE_FIRSTHAND else []),
            # Scoped to the memories of THIS epistemic class: a first-hand
            # clause supported by something the character was only told would
            # be an audit trail that launders hearsay into experience.
            support=derive_summary_support(
                text, [m for m in memories
                       if summary_scope_for(m.get("provenance")) == scope]))
    return result


def memory_summary_coverage(chat_id, char_id, *, window=10):
    """How much of this character's life has a summary above it.

    The question the backfill button asks before offering itself. Counts only
    memories that record something -- a bank of empty-view placeholders has
    nothing to summarise and offering to rebuild it would burn a call per
    window to describe an absence.

    Returns {total, covered, uncovered, first_turn, floor, windows,
    missing_windows}.
    """
    rows = q("SELECT turn_idx, content, gist FROM memories WHERE chat_id=? AND "
             "char_id=? AND turn_idx IS NOT NULL", (chat_id, char_id))
    mems = [dict(r) for r in rows]
    real = _substantive(mems)
    spans = q("SELECT start_turn_idx s, end_turn_idx e FROM memory_summaries "
              "WHERE chat_id=? AND char_id=? AND scope=?",
              (chat_id, char_id, SUMMARY_SCOPE_FIRSTHAND))
    spans = [(r["s"], r["e"]) for r in spans]
    covered = sum(1 for m in real
                  if any(s <= m["turn_idx"] <= e for s, e in spans))
    first = min((m["turn_idx"] for m in real), default=None)
    floor = min((s for s, _e in spans), default=None)
    missing = 0
    if first is not None and floor is not None and floor > first:
        below = sorted({m["turn_idx"] for m in real if m["turn_idx"] < floor})
        edges = set()
        for t in below:
            edges.add(floor - ((floor - t + int(window) - 1) // int(window)) * int(window))
        missing = len(edges)
    return {
        "total": len(real), "covered": covered,
        "uncovered": len(real) - covered,
        "placeholders": len(mems) - len(real),
        "first_turn": first, "floor": floor,
        "windows": len(spans), "missing_windows": missing,
    }


def backfill_memory_summary_windows(chat_id, char_id, *, window=10,
                                    viewer_frame_id=_UNSET, on_window=None):
    """Rebuild the summary windows the pre-v23 singleton destroyed.

    Until schema v23 a scope held one row and each consolidation overwrote it,
    so a long story ends up with a summary of its most recent ten turns and
    nothing behind it. Measured on the live bank: 53 of 67 banks have no
    summary over their opening turns, and in the longest story (chat 38, 118
    turns) 82-87% of every character's memories sit under no summary at all.

    The raw memories survive -- nothing was ever deleted -- so the era is
    recoverable by consolidating it again. This walks FORWARD from the
    character's first memory to the earliest surviving window, in `window`-turn
    steps aligned to that window's boundary so the reconstructed cadence
    matches the live one, chaining each result into the next as
    `previous_summary` exactly as the forward path would have.

    Two things it deliberately does not do:

    - **It does not archive.** The forward path archives low-salience memories
      it has just folded in; doing that here would retire hundreds of rows at
      once on the strength of a summary written years after the fact.
    - **It does not move the consolidation cursor.**
      `maybe_consolidate_character_memory` reads the first-hand row's
      `end_turn_idx` as its cursor, and `get_memory_summary` orders by
      `end_turn_idx DESC` -- so writing OLDER windows leaves the cursor on the
      newest row, untouched. That is load-bearing, and tested.

    `on_window(start, end, count)` is called before each consolidator request,
    for progress on a long run.

    Returns {"windows": n_written, "turns": (lo, hi), "skipped": n_empty}.
    """
    char = q("SELECT name FROM characters WHERE id=?", (char_id,), one=True)
    if not char:
        raise ValueError("Character not found")
    row = q("SELECT MIN(start_turn_idx) AS s FROM memory_summaries "
            "WHERE chat_id=? AND char_id=?", (chat_id, char_id), one=True)
    floor = row["s"] if row else None
    if floor is None:
        # Nothing has ever been consolidated; the forward path is the right
        # tool and will produce the same windows without this one guessing.
        return {"windows": 0, "turns": None, "skipped": 0}
    rows = visible_memory_rows(
        chat_id, char_id, before_turn_idx=int(floor),
        viewer_frame_id=viewer_frame_id, include_archived=False,
        require_turn_idx=True)
    if not rows:
        return {"windows": 0, "turns": None, "skipped": 0}
    rows.sort(key=lambda r: (r["turn_idx"], r["id"]))
    memories = [_row_memory(r) for r in rows]
    lo, hi = memories[0]["turn_idx"], memories[-1]["turn_idx"]
    # Aligned to the SURVIVING window's boundary and counted backwards, so the
    # reconstructed windows abut it instead of overlapping it by a few turns.
    edges = []
    edge = int(floor)
    while edge > lo:
        edges.append(edge)
        edge -= int(window)
    edges.append(min(edge, lo))
    edges.reverse()
    previous = {"scope": SUMMARY_SCOPE_FIRSTHAND, "start_turn_idx": 0,
                "end_turn_idx": 0, "summary": "", "key_phrases": [],
                "unresolved_threads": []}
    written = skipped = 0
    for start, stop in zip(edges, edges[1:]):
        chunk = _substantive([m for m in memories
                              if start <= m["turn_idx"] < stop])
        if not chunk:
            # Either nobody was there, or every row is the engine's own
            # "unspecified area" placeholder from an off-screen beat. Neither
            # is an era, and summarising one writes a character fifty turns of
            # authored amnesia they never lived.
            skipped += 1
            continue
        if on_window:
            on_window(start, stop - 1, len(chunk))
        result = _write_consolidated_window(chat_id, char_id, char["name"],
                                            chunk, previous)
        written += 1
        previous = {
            "scope": SUMMARY_SCOPE_FIRSTHAND,
            "start_turn_idx": chunk[0]["turn_idx"],
            "end_turn_idx": chunk[-1]["turn_idx"],
            "summary": str(result.get("summary") or ""),
            "key_phrases": result.get("key_phrases") or [],
            "unresolved_threads": result.get("unresolved_threads") or [],
        }
    return {"windows": written, "turns": (lo, hi), "skipped": skipped}


def consolidate_character_memory(chat_id, char_id, *, through_turn_idx=None, archive_old=True,
                                 viewer_frame_id=_UNSET):
    char = q("SELECT name FROM characters WHERE id=?", (char_id,), one=True)
    if not char:
        raise ValueError("Character not found")
    old_summary = get_memory_summary(chat_id, char_id)
    # Everything up to old_summary["end_turn_idx"] is already folded into
    # old_summary (sent below as previous_summary) and archived rows were
    # already folded into some still-earlier summary -- resending either
    # gets the consolidator no new information but made the payload (and
    # its cost) grow without bound across a long chat's repeated
    # consolidation passes, since every call previously re-sent the
    # complete history since turn 0 regardless of what had already been
    # summarized.
    # turn_idx is GLOBAL play order shared by every frame, not per-era -- so
    # without the seam's frame filter, memories formed during a
    # flash-forward/-back would be folded into the singleton autobiographical
    # summary the moment play returns to the present and turn_idx catches up,
    # handing a character knowledge of events they have not diegetically
    # reached. `before_turn_idx` is exclusive and this window is inclusive of
    # `through_turn_idx`, hence the +1.
    rows = visible_memory_rows(
        chat_id, char_id,
        before_turn_idx=(None if through_turn_idx is None
                         else int(through_turn_idx) + 1),
        viewer_frame_id=viewer_frame_id,
        include_archived=False,
        since_turn_idx=(old_summary.get("end_turn_idx") or 0) + 1,
        require_turn_idx=True,
    )
    rows.sort(key=lambda r: (r["turn_idx"], r["id"]))
    memories = [_row_memory(r) for r in rows]
    if not memories:
        return old_summary
    start_turn = min(m["turn_idx"] for m in memories)
    end_turn = max(m["turn_idx"] for m in memories)
    substantive = _substantive(memories)
    if not substantive:
        # Every row in this window is the engine's own empty-view placeholder
        # (an off-screen character), so there is nothing to consolidate. The
        # cursor still has to advance -- maybe_consolidate reads THIS row's
        # end_turn_idx, and stalling it re-consolidates the same rows every
        # ten turns forever -- so carry the previous account forward unchanged
        # rather than asking a model to summarise an absence. No LLM call.
        save_memory_summary(
            chat_id, char_id, old_summary.get("summary") or "",
            scope=SUMMARY_SCOPE_FIRSTHAND,
            start_turn_idx=start_turn, end_turn_idx=end_turn,
            key_phrases=old_summary.get("key_phrases") or [],
            unresolved_threads=old_summary.get("unresolved_threads") or [])
        return get_memory_summary(chat_id, char_id)
    result = _write_consolidated_window(chat_id, char_id, char["name"],
                                        substantive, old_summary)
    if archive_old:
        cutoff = max(start_turn, end_turn - 12)
        # Archive ONLY memories that were part of THIS (frame-visible)
        # consolidation set. turn_idx is global play order, so the old
        # blanket UPDATE also archived another era's memories that were
        # correctly excluded from this summary (is_memory_visible filtered
        # them out of `memories`) and never folded into any summary.
        archivable = [
            m["id"] for m in memories
            if m.get("id") is not None
            and (m.get("turn_idx") or 0) < cutoff
            # The HIGHER of the two. A memory that turned out to matter is
            # not archived on the strength of how ordinary it looked at the
            # time -- which is the entire reason the two numbers are separate.
            and max(float(m.get("salience") or 0),
                    effective_importance(m)) < 0.72
            and m.get("category") not in ("promise", "relationship", "intention")
        ]
        if archivable:
            marks = ",".join("?" for _ in archivable)
            qi(f"UPDATE memories SET archived=1 WHERE id IN ({marks})", tuple(archivable))
    return {**get_memory_summary(chat_id, char_id), "stable_facts": result.get("stable_facts") or [], "memory_count": len(memories)}

def maybe_consolidate_character_memory(chat_id, char_id, current_turn_idx, *, frame_id=_UNSET):
    # A singleton per-character summary has nowhere to put "as of the
    # present era" vs. "as of the future flash-forward" -- consolidating
    # outside the present would permanently blend eras into one
    # autobiography with no way to un-blend it. Frozen to present only;
    # a frame visited away from the present just accumulates raw memories
    # (still correctly filtered by is_memory_visible) until play returns.
    #
    # frame_id is accepted explicitly (falling back to the ambient
    # contextvar only when the caller doesn't have it on hand) rather
    # than always trusting the contextvar, because the one real caller
    # that matters -- commit.py's per-character consolidation loop --
    # runs each character's check on a concurrent.futures.ThreadPoolExecutor
    # worker thread, and THAT does not propagate contextvars the way
    # agents/runtime.py's own bespoke thread-spawning helpers do (they
    # explicitly contextvars.copy_context() first). Reading the
    # contextvar from inside the worker thread would silently see the
    # default None on every call regardless of which frame's turn is
    # actually being committed, defeating this guard exactly the way
    # app.py's old streaming path defeated active_frame_id.
    fid = _active_frame_id.get() if frame_id is _UNSET else frame_id
    if fid is not None:
        return None
    summary = get_memory_summary(chat_id, char_id)
    last_turn = summary.get("end_turn_idx") or 0
    count = q("SELECT COUNT(*) AS c FROM memories WHERE chat_id=? AND char_id=? AND archived=0 AND turn_idx>?",
              (chat_id, char_id, last_turn), one=True)["c"]
    if current_turn_idx - last_turn < 10 and count < 40:
        return None
    return consolidate_character_memory(chat_id, char_id, through_turn_idx=current_turn_idx,
                                        viewer_frame_id=fid)

# ---- Snapshot dump/restore ----

def vector_address(embedding, cue_embedding) -> str:
    """Address a vector pair by ITS OWN BYTES.

    The first version of this addressed on `(char_id, content)` -- reusing
    `_memory_vector_key` on the reasoning that a vector is a pure function of
    the memory. It is, but not of its CONTENT: `_memory_document` also folds in
    `turn`, `location`, `category`, `key_phrases`, `entities`, `gist`,
    `provenance` and `emotional_context`. Two memories can therefore share
    content and hold different vectors, and that address collapses them.

    Found in production, by the compaction verifier refusing four stories:
    checkpoint 855 of chat 36 held "You are in Ten Forward." at turn 42 and
    again at turn 44 -- same character, same content, two different embedding
    payloads. Addressing on bytes makes a collision impossible by construction
    rather than by assumption, and costs almost nothing: across chat 38's
    40,224 stored entries, content-addressing found 529 distinct and
    byte-addressing finds 583, still 69x deduplication.

    The `v1:` prefix distinguishes these from addresses written by the earlier
    scheme. Those rows stay in `memory_vectors` and keep resolving, so already
    converted checkpoints are unaffected -- and they are known-good, because a
    story whose entries collided could not have passed verification.

    `_memory_vector_key` carried the same old assumption for a while longer
    and `rebuild_checkpoint_embeddings` joined on it, which is the same bug
    one layer over: it could substitute one memory's vector onto another. That
    key now hashes the whole `_memory_document` (and a summary's whole
    `_summary_retrieval_text`), so both addresses are computed from the text
    the vector was actually built from.
    """
    digest = hashlib.sha1()
    digest.update(embedding or b"")
    digest.update(b"|")
    digest.update(cue_embedding or b"")
    return "v1:" + digest.hexdigest()


def put_memory_vector(vkey, embedding, cue_embedding, model, dim):
    """File a vector pair under its content address. Idempotent, append-only.

    `INSERT OR IGNORE`, not upsert: the address IS the content, so a second
    write for the same key is the same vector. If it somehow is not -- a model
    change without a rekey -- the FIRST one wins, because that is the one the
    existing checkpoints were written against and a rollback has to reproduce
    what it saved, not what is current.
    """
    if not vkey or embedding is None or cue_embedding is None:
        return False
    qi("INSERT OR IGNORE INTO memory_vectors"
       "(vkey,embedding,cue_embedding,embedding_model,embedding_dim,created) "
       "VALUES(?,?,?,?,?,?)",
       (vkey, embedding, cue_embedding, model or "", dim, time.time()))
    return True


def get_memory_vectors(vkeys):
    """{vkey: (embedding_blob, cue_blob, model, dim)} for the keys that exist."""
    keys = [str(k) for k in (vkeys or []) if str(k or "").strip()]
    if not keys:
        return {}
    out = {}
    # Chunked: a long story's restore can ask for hundreds of keys at once and
    # SQLite caps host parameters.
    for i in range(0, len(keys), 400):
        part = keys[i:i + 400]
        marks = ",".join("?" for _ in part)
        for r in q("SELECT * FROM memory_vectors WHERE vkey IN (%s)" % marks,
                   tuple(part)):
            out[r["vkey"]] = (r["embedding"], r["cue_embedding"],
                              r["embedding_model"], r["embedding_dim"])
    return out


def dump_memory_vectors(vkeys):
    """Content-addressed vectors, base64'd, for a portable archive."""
    out = []
    for vkey, (full, cue, model, dim) in sorted(get_memory_vectors(vkeys).items()):
        out.append({"vkey": vkey, "embedding": _blob_to_b64(full),
                    "cue_embedding": _blob_to_b64(cue),
                    "embedding_model": model, "embedding_dim": dim})
    return out


def restore_memory_vectors(entries):
    """File an archive's vectors into this database's store.

    Additive and idempotent -- the address is the content, so an entry that is
    already here is the same vector. Never deletes: another chat's checkpoints
    may reference the same address.

    VERIFIED, not trusted: this used to file the archive's `vkey` straight
    through with no recomputation and no length check, while
    `persist/checkpoints.py`'s restore recomputed. That broke the store's
    premise -- `put_memory_vector` is INSERT OR IGNORE with first-writer-wins
    because the address IS the content, so one mislabeled archive entry could
    park wrong bytes under a true address and shadow the real vector for
    every checkpoint that later referenced it. A violation RAISES rather than
    skipping, so the enclosing import transaction rolls the whole restore
    back: a partially-restored vector bank is a silent retrieval downgrade,
    which is the failure mode the model stamps were added to end. Pre-`v1:`
    keys were addressed on the memory document, not the bytes, so they cannot
    be recomputed here and restore on the well-formedness checks alone.
    """
    n = 0
    with transaction():
        for e in entries or []:
            if not isinstance(e, dict):
                continue
            vkey = str(e.get("vkey") or "").strip()
            if not vkey:
                continue
            full = _b64_to_blob(e.get("embedding"))
            cue = _b64_to_blob(e.get("cue_embedding"))
            if full is None or cue is None:
                raise ValueError(
                    f"memory vector {vkey!r}: payload is not a well-formed "
                    "float32 blob"
                )
            try:
                dim = int(e.get("embedding_dim"))
            except (TypeError, ValueError):
                dim = None
            if dim and len(full) != dim * 4:
                raise ValueError(
                    f"memory vector {vkey!r}: blob holds {len(full) // 4} "
                    f"floats but claims dimension {dim}"
                )
            if vkey.startswith("v1:") and vector_address(full, cue) != vkey:
                raise ValueError(
                    f"memory vector {vkey!r}: bytes do not hash to their own "
                    "address"
                )
            if put_memory_vector(vkey, full, cue,
                                 e.get("embedding_model"),
                                 dim if dim else e.get("embedding_dim")):
                n += 1
    return n


def dump_chat_memories(chat_id, *, inline_vectors=True):
    """The chat's memory bank, for a checkpoint or a portable archive.

    `inline_vectors` is the difference between the two callers, and it matters:

    * a CHECKPOINT lives in the same database as the vector store, so it can
      reference vectors by content address and carry none of the payload.
      That is the whole compaction -- the two vector fields are 96.9% of a
      checkpoint, re-stored on every turn for the life of the story.
    * a portable ARCHIVE is imported into a DIFFERENT database, where no such
      store exists, so it must carry the vectors with it or the import
      re-embeds the whole bank (expensive, and a provider hiccup during it
      silently downgrades every vector to the crc32 fallback).

    The restore path accepts either shape, so an old checkpoint written before
    this existed still restores from its inline vectors unchanged.
    """
    rows = q("SELECT * FROM memories WHERE chat_id=? ORDER BY CASE WHEN turn_idx IS NULL THEN 1 ELSE 0 END, turn_idx, id", (chat_id,))
    if not inline_vectors:
        with transaction():
            for r in rows:
                if r["embedding"] is None or r["cue_embedding"] is None:
                    continue
                put_memory_vector(
                    vector_address(r["embedding"], r["cue_embedding"]),
                    r["embedding"], r["cue_embedding"],
                    r["embedding_model"], r["embedding_dim"])
    return [
        {"char_id": r["char_id"], "turn_id": r["turn_id"], "turn_idx": r["turn_idx"],
         "frame_id": r["frame_id"],
         "kind": r["kind"], "category": r["category"], "provenance": r["provenance"],
         "salience": r["salience"], "content": r["content"], "gist": r["gist"],
         "key_phrases": _json_list(r["key_phrases"]), "entities": _json_list(r["entities"]),
         "location": r["location"], "emotional_context": r["emotional_context"],
         "valence": r["valence"], "arousal": r["arousal"], "confidence": r["confidence"],
         "encoding_valence": r["encoding_valence"],
         "encoding_arousal": r["encoding_arousal"],
         "archived": bool(r["archived"]), "event_key": r["event_key"],
         "importance": r["importance"], "disputed": r["disputed"] or "",
         # How often this memory came back to the character, and when it last
         # did. The engine never reads either column; `tools/remember_lines.py`
         # and `tools/salience_replay.py` read them as their whole answer, so a
         # bank that forgets them on every reroll, branch or import has a
         # denominator that silently resets to zero. Neither is re-derivable
         # from anything -- the same argument `importance` and `disputed` are
         # carried on, one line up.
         "access_count": r["access_count"] or 0,
         "last_accessed": r["last_accessed"],
         # Stored vectors travel with the dump so restore can put them
         # back byte-identically instead of re-embedding the entire
         # memory bank on every checkpoint restore (expensive, and a
         # provider hiccup during it silently downgrades every vector
         # to the crc32 fallback, which then scores 0.0 forever).
         **({"embedding": _blob_to_b64(r["embedding"]),
             "cue_embedding": _blob_to_b64(r["cue_embedding"])}
            if inline_vectors else
            {"vkey": vector_address(r["embedding"], r["cue_embedding"])}),
         "embedding_model": r["embedding_model"],
         "embedding_dim": r["embedding_dim"]}
        for r in rows
    ]

@dataclass
class _StoredEmbeddingMeta:
    """Stands in for providers.EmbeddingBatch when the vectors came out
    of a dump instead of a live embedding call -- _upsert_memory only
    reads model_key/dimensions off it."""
    model_key: str
    dimensions: int

def prepare_chat_memory_restore(chat_id, mems):
    """Build a write-free restore plan for restore_chat_memories.

    All normalization and any embedding calls happen here, BEFORE any
    row is touched, so apply_chat_memory_restore is pure writes and can
    run inside an outer transaction (checkpoint restore) without a
    remote provider call ever holding SQLite's write lock. Dumps that
    carry their stored vectors (see dump_chat_memories) are restored
    verbatim; only legacy dumps without them are re-embedded."""
    entries = []
    legacy_items = []
    # One lookup for every address in the dump, before the loop: a restore
    # should not issue a query per memory.
    vector_store = get_memory_vectors(
        [m.get("vkey") for m in (mems or []) if isinstance(m, dict) and m.get("vkey")])
    for m in mems or []:
        if not m.get("content"):
            continue
        item = {
            "chat_id": chat_id, "char_id": m.get("char_id"), "turn_id": m.get("turn_id"),
            "turn_idx": m.get("turn_idx"), "kind": m.get("kind", "episodic"),
            # Preserved verbatim, never re-stamped with whatever frame
            # happens to be active during the restore -- a checkpoint
            # restore means "put it back exactly as it was," and a
            # branch clone is expected to have already remapped this to
            # the new chat's own frame ids before calling this function.
            "frame_id": m.get("frame_id"),
            "category": m.get("category"), "provenance": m.get("provenance", "witnessed"),
            "salience": m.get("salience", 0.5), "content": m["content"],
            "gist": m.get("gist"), "key_phrases": m.get("key_phrases"),
            "entities": m.get("entities"), "location": m.get("location", ""),
            "emotional_context": m.get("emotional_context", ""),
            "valence": m.get("valence", 0.0), "arousal": m.get("arousal", 0.0),
            "encoding_valence": m.get("encoding_valence", 0.0),
            "encoding_arousal": m.get("encoding_arousal", 0.0),
            "confidence": m.get("confidence", 1.0), "event_key": m.get("event_key", ""),
            # Carried verbatim. A revised importance and a recorded re-reading
            # are things the character earned; a rollback restores the bank as
            # it was, and neither is re-derivable from the row's own text.
            "importance": m.get("importance"),
            "disputed": m.get("disputed") or "",
        }
        # Restored after the insert, beside `archived`: `prepare_memory`
        # describes a memory as it was FORMED, and neither of these is part of
        # that -- they are the record of it being read since.
        history = (int(m.get("access_count") or 0), m.get("last_accessed"))
        full_blob = _b64_to_blob(m.get("embedding"))
        cue_blob = _b64_to_blob(m.get("cue_embedding"))
        model = m.get("embedding_model") or ""
        # A compacted checkpoint carries a content address instead of the
        # payload. Resolve it here, in the same read-only phase the inline
        # shape is handled in, so the write phase stays identical for both.
        if (full_blob is None or cue_blob is None) and m.get("vkey"):
            hit = vector_store.get(m["vkey"])
            if hit:
                full_blob, cue_blob = hit[0], hit[1]
                model = model or hit[2]
                if not m.get("embedding_dim"):
                    m = {**m, "embedding_dim": hit[3]}
        if full_blob is not None and cue_blob is not None and model:
            full_vec = _vec(full_blob)
            cue_vec = _vec(cue_blob)
            dim = m.get("embedding_dim") or len(full_vec)
            entries.append({
                "mode": "direct", "source": m, "data": prepare_memory(**item),
                "full_vec": full_vec, "cue_vec": cue_vec,
                "meta": _StoredEmbeddingMeta(model, int(dim)),
                "retrieval_history": history,
            })
        else:
            entries.append({"mode": "legacy", "source": m,
                            "retrieval_history": history})
            legacy_items.append(item)
    legacy_batch = prepare_memories_batch(legacy_items) if legacy_items else None
    return {"entries": entries, "legacy_batch": legacy_batch}

def apply_chat_memory_restore(chat_id, plan):
    """Write phase of restore_chat_memories: delete-and-reinsert the
    chat's memory bank from a plan built by prepare_chat_memory_restore.
    One transaction, no provider calls; FTS rows are maintained through
    the exact same _upsert_memory path the normal add path uses."""
    entries = plan.get("entries") or []
    legacy_batch = plan.get("legacy_batch")
    legacy_prepared = (legacy_batch or {}).get("prepared") or []
    legacy_embedded = (legacy_batch or {}).get("embedded")
    legacy_count = sum(1 for e in entries if e["mode"] == "legacy")
    if legacy_count and (legacy_embedded is None
                         or len(legacy_embedded.vectors) != legacy_count * 2
                         or len(legacy_prepared) != legacy_count):
        raise ValueError("Invalid prepared memory embedding batch")
    with transaction():
        for r in q("SELECT id FROM memories WHERE chat_id=?", (chat_id,)):
            _delete_memory_fts(r["id"])
        qi("DELETE FROM memories WHERE chat_id=?", (chat_id,))
        li = 0
        for entry in entries:
            if entry["mode"] == "direct":
                mid = _upsert_memory(entry["data"], entry["full_vec"],
                                     entry["cue_vec"], entry["meta"])
            else:
                mid = _upsert_memory(legacy_prepared[li],
                                     legacy_embedded.vectors[li * 2],
                                     legacy_embedded.vectors[li * 2 + 1],
                                     legacy_embedded)
                li += 1
            if entry["source"].get("archived"):
                qi("UPDATE memories SET archived=1 WHERE id=?", (mid,))
            count, last = entry.get("retrieval_history") or (0, None)
            if count or last is not None:
                qi("UPDATE memories SET access_count=?, last_accessed=? "
                   "WHERE id=?", (int(count), last, mid))

def restore_chat_memories(chat_id, mems):
    apply_chat_memory_restore(chat_id, prepare_chat_memory_restore(chat_id, mems))

def dump_character_memories(chat_id, char_id):
    """Same shape as dump_chat_memories, but scoped to one character --
    the unit a user actually wants to carry around (export a character's
    accumulated memory bank, import it into a different story with the
    same character, or back it up separately from the whole chat)."""
    rows = q(
        "SELECT * FROM memories WHERE chat_id=? AND char_id=? "
        "ORDER BY CASE WHEN turn_idx IS NULL THEN 1 ELSE 0 END, turn_idx, id",
        (chat_id, char_id),
    )
    return [
        {"turn_idx": r["turn_idx"],
         "kind": r["kind"], "category": r["category"], "provenance": r["provenance"],
         "salience": r["salience"], "content": r["content"], "gist": r["gist"],
         "key_phrases": _json_list(r["key_phrases"]), "entities": _json_list(r["entities"]),
         "location": r["location"], "emotional_context": r["emotional_context"],
         "valence": r["valence"], "arousal": r["arousal"], "confidence": r["confidence"],
         "encoding_valence": r["encoding_valence"],
         "encoding_arousal": r["encoding_arousal"],
         "archived": bool(r["archived"]), "event_key": r["event_key"],
         "importance": r["importance"], "disputed": r["disputed"] or ""}
        for r in rows
    ]

def import_character_memories(chat_id, char_id, memories):
    """Additive import for one character's memories -- unlike
    restore_chat_memories (which wipes and replaces, only ever used for
    checkpoint restore), this never deletes anything: it's for a user
    bringing a character's memory bank INTO a chat, possibly a different
    one than it was exported from. turn_id/turn_idx are always dropped
    even on a same-chat re-import, since an old export's turn numbering
    can't be trusted to still line up with this chat's actual turns --
    the same treatment already used for background-promotion memory
    seeds, which also arrive with no real turn to anchor to."""
    prepared = []
    for m in memories or []:
        content = str(m.get("content") or "").strip()
        if not content:
            continue
        prepared.append({
            "chat_id": chat_id, "char_id": char_id, "turn_id": None, "turn_idx": None,
            "kind": m.get("kind", "episodic"), "category": m.get("category"),
            "provenance": m.get("provenance", "told"),
            "salience": m.get("salience", 0.5), "content": content,
            "gist": m.get("gist"), "key_phrases": m.get("key_phrases"),
            "entities": m.get("entities"), "location": m.get("location", ""),
            "emotional_context": m.get("emotional_context", ""),
            "valence": m.get("valence", 0.0), "arousal": m.get("arousal", 0.0),
            "encoding_valence": m.get("encoding_valence", 0.0),
            "encoding_arousal": m.get("encoding_arousal", 0.0),
            "confidence": m.get("confidence", 1.0), "event_key": "",
            # Both travel with a portable character bank: they are the
            # character's own history with these memories, not facts about the
            # chat they were formed in.
            "importance": m.get("importance"),
            "disputed": m.get("disputed") or "",
        })
    return len(add_memories_batch(prepared))

def dump_memory_summaries(chat_id):
    return [
        {"char_id": r["char_id"], "scope": r["scope"], "start_turn_idx": r["start_turn_idx"],
         "end_turn_idx": r["end_turn_idx"], "summary": r["summary"],
         "key_phrases": _json_list(r["key_phrases"]), "unresolved_threads": _json_list(r["unresolved_threads"]),
         # Per-clause support travels with the summary. Refs are event_keys,
         # which restore preserves verbatim, so this needs no id remapping on
         # branch, clone or checkpoint rollback -- the reason it was built out
         # of event_keys rather than row ids.
         "support": _json_list(r["support"]),
         "updated": r["updated"],
         # Same rationale as dump_chat_memories: carry the stored vector
         # so restore is verbatim instead of a provider round trip.
         "embedding": _blob_to_b64(r["embedding"]),
         "embedding_model": r["embedding_model"],
         "embedding_dim": r["embedding_dim"]}
        # end_turn_idx joins the ordering since v23: a scope holds one row per
        # WINDOW, so (char_id, scope) alone no longer identifies a row and an
        # export's order would depend on rowid.
        for r in q("SELECT * FROM memory_summaries WHERE chat_id=? "
                   "ORDER BY char_id, scope, end_turn_idx, id", (chat_id,))
    ]

def prepare_memory_summary_restore(summaries):
    """Embedding phase of restore_memory_summaries: resolves each
    summary's vector (verbatim from the dump when present, one embed
    call per legacy item otherwise) with zero writes, so the apply
    phase never makes a provider call while holding the write lock."""
    prepared = []
    for item in summaries or []:
        emb = _b64_to_blob(item.get("embedding"))
        model = item.get("embedding_model") or ""
        dim = item.get("embedding_dim")
        if emb is None or not model:
            embedded = embed_texts_meta([_summary_retrieval_text(
                item.get("summary"), item.get("key_phrases") or [],
                item.get("unresolved_threads") or [])])
            emb = _blob(embedded.vectors[0])
            model = embedded.model_key
            dim = embedded.dimensions
        prepared.append((item, emb, model, dim))
    return prepared

def apply_memory_summary_restore(chat_id, prepared):
    with transaction():
        qi("DELETE FROM memory_summaries WHERE chat_id=?", (chat_id,))
        for item, emb, model, dim in prepared:
            save_memory_summary(chat_id, item["char_id"], item.get("summary", ""),
                                scope=item.get("scope", "autobiographical"),
                                start_turn_idx=item.get("start_turn_idx", 0),
                                end_turn_idx=item.get("end_turn_idx", 0),
                                key_phrases=item.get("key_phrases") or [],
                                unresolved_threads=item.get("unresolved_threads") or [],
                                support=item.get("support") or [],
                                embedding=emb, embedding_model=model, embedding_dim=dim)

def restore_memory_summaries(chat_id, summaries):
    apply_memory_summary_restore(chat_id, prepare_memory_summary_restore(summaries))

def dump_lorebook(lb_id):
    return [
        {
            "entry_uid": r["entry_uid"], "keys": r["keys"], "content": r["content"],
            "category": r["category"] or "other", "locked": r["canon_locked"],
            "turn_added": r["turn_added"], "title": r["title"],
            "knowledge_tag": r["knowledge_tag"], "knowledge_range": r["knowledge_range"],
            "knowledge_locations": r["knowledge_locations"],
            "importance": r["importance"], "aliases": r["aliases"],
            "scope": r["scope"], "relations": r["relations"],
            "source_notes": r["source_notes"],
            # Stored vector travels with the dump so restore/import can
            # reuse it verbatim instead of re-embedding every entry -- and
            # with the stamp that says what produced it, because a vector
            # whose provenance was dropped in transit is one every later
            # reader has to judge on width alone.
            "embedding": _blob_to_b64(r["embedding"]),
            "embedding_model": r["embedding_model"],
            "embedding_dim": r["embedding_dim"],
        }
        for r in q("SELECT * FROM lore_entries WHERE lorebook_id=? ORDER BY id", (lb_id,))
    ]

def restore_lorebook(lb_id, entries):
    import hashlib, uuid

    def legacy_entry_uid(entry):
        raw = "\x1f".join([
            str(entry.get("keys") or "").strip().casefold(),
            re.sub(r"\s+", " ", str(entry.get("content") or "").strip().casefold()),
            str(entry.get("category") or "other"),
        ])
        return f"legacy_entry_{hashlib.sha256(raw.encode('utf-8')).hexdigest()}"

    incoming = [entry for entry in (entries or []) if isinstance(entry, dict) and entry.get("content")]
    incoming_uids = set()

    # Resolve every entry's embedding up front, before any row is
    # touched: entries dumped by dump_lorebook carry their stored vector
    # (reused verbatim -- the snapshot's vector matches the snapshot's
    # keys/content by construction), and only legacy dumps without one
    # are re-embedded, in a single batch so no per-entry provider call
    # ever runs between writes.
    entry_vecs = {}
    entry_stamps = {}
    legacy_entries = []
    for entry in incoming:
        raw = entry.get("embedding")
        if isinstance(raw, str):
            raw = _b64_to_blob(raw)
        elif not isinstance(raw, (bytes, bytearray, memoryview)):
            raw = None
        vec = _vec(bytes(raw)) if raw and len(raw) % 4 == 0 else None
        if vec is None:
            legacy_entries.append(entry)
        entry_vecs[id(entry)] = vec
        # The stamp belongs to the vector that arrived, so a snapshot old
        # enough to carry bytes without one stays unstamped, and an entry
        # re-embedded below is stamped by the embedder rather than by the
        # snapshot it came from.
        entry_stamps[id(entry)] = (
            entry.get("embedding_model") if vec is not None else None)
    if legacy_entries:
        texts = [(e.get("keys") or "") + " " + (e.get("content") or "") for e in legacy_entries]
        for e, vec in zip(legacy_entries, embed_texts(texts)):
            entry_vecs[id(e)] = vec
            # NOT stamped with the live model key: `embed_texts` returns bare
            # vectors and degrades to the crc32 fallback on any provider
            # error, so the name would be a guess. Unstamped is the true
            # answer, and what the backfill exists to settle.
            entry_stamps[id(e)] = None

    for entry in incoming:
        uid = entry.get("entry_uid") or legacy_entry_uid(entry)
        existing = q("SELECT id FROM lore_entries WHERE lorebook_id=? AND entry_uid=?", (lb_id, uid), one=True)
        if existing:
            incoming_uids.add(uid)
            update_lore(existing["id"], entry.get("keys", ""), entry["content"],
                        entry.get("category", "other"), title=entry.get("title"),
                        knowledge_tag=entry.get("knowledge_tag"),
                        knowledge_range=entry.get("knowledge_range"),
                        knowledge_locations=_storage_json(entry.get("knowledge_locations")),
                        importance=entry.get("importance", 0.5),
                        aliases=entry.get("aliases", []),
                        scope=entry.get("scope", {}),
                        relations=entry.get("relations", {}),
                        source_notes=entry.get("source_notes", ""),
                        embedding=entry_vecs.get(id(entry)),
                        embedding_model=entry_stamps.get(id(entry)),
                        embedding_dim=entry.get("embedding_dim"))
            qi("UPDATE lore_entries SET canon_locked=?, turn_added=? WHERE id=?",
               (int(bool(entry.get("locked", 0))), entry.get("turn_added"), existing["id"]))
            continue

        # UID might exist in a different lorebook (global UNIQUE constraint)
        global_existing = q("SELECT id FROM lore_entries WHERE entry_uid=?", (uid,), one=True)
        if global_existing:
            uid = f"entry_{uuid.uuid4().hex}"

        incoming_uids.add(uid)
        add_lore(lb_id, entry.get("keys", ""), entry["content"],
                 turn_added=entry.get("turn_added"), locked=int(bool(entry.get("locked", 0))),
                 category=entry.get("category", "other"), title=entry.get("title"),
                 knowledge_tag=entry.get("knowledge_tag"), knowledge_range=entry.get("knowledge_range"),
                 knowledge_locations=_storage_json(entry.get("knowledge_locations")),
                 entry_uid=uid,
                 importance=entry.get("importance", 0.5),
                 aliases=entry.get("aliases", []),
                 scope=entry.get("scope", {}),
                 relations=entry.get("relations", {}),
                 source_notes=entry.get("source_notes", ""),
                 embedding=entry_vecs.get(id(entry)),
                 embedding_model=entry_stamps.get(id(entry)),
                 embedding_dim=entry.get("embedding_dim"))

    for row in q("SELECT id,entry_uid FROM lore_entries WHERE lorebook_id=?", (lb_id,)):
        if row["entry_uid"] not in incoming_uids:
            delete_lore(row["id"])

# ---- Lorebook Entries ----

def ensure_chat_canon_book(chat_id):
    """The chat's own canon lorebook, minted on demand.

    Canon written DURING play -- facts the Director established this run --
    lives in one book per chat, hung off `chats.lorebook_id`. It used to be
    minted inline by `commit.commit_mapping` and nowhere else, so a second
    writer could only spell the same book into existence again; a ratified
    background claim (`background_claims.settle_claims`) is exactly that second
    writer, and it lands on beats where mapping is skipped entirely. One
    spelling, folded here, rather than a rule each new writer must remember.

    Returns the lorebook id, or None if the chat does not exist.
    """
    row = q("SELECT name, lorebook_id FROM chats WHERE id=?", (chat_id,), one=True)
    if not row:
        return None
    if row["lorebook_id"]:
        return row["lorebook_id"]
    lb = qi(
        "INSERT INTO lorebooks(name,chat_id,book_type,summary) VALUES(?,?,?,?)",
        (
            f"{row['name']} — canon", chat_id, "general",
            "Chat canon: facts, events and specifics established during this chat.",
        ),
    )
    qi("UPDATE chats SET lorebook_id=? WHERE id=?", (lb, chat_id))
    return lb


def _embed_lore_document(keys, content):
    """The vector for one lore entry, WITH the model that made it.

    THE WRITE PATH USED TO THROW THAT AWAY. `add_lore` and `update_lore` both
    called `embed_texts`, which returns bare vectors, so neither could tell a
    real embedding from `cheap_embed`'s crc32 hash -- and `embed_texts_meta`
    degrades to that hash on ANY provider error. 1,061 of 1,418 entries on a
    live corpus were written that way, byte-identical to the fallback,
    semantically meaningless, and nothing recorded it because there was
    nowhere to record it and nothing asking.

    Returns `(vector, model_key, dimensions)`. The caller stores all three, so
    the question "what embedded this row" is answered at the moment of writing
    rather than reconstructed by hashing every entry in the table afterwards.
    """
    got = embed_texts_meta([(keys or "") + " " + (content or "")])
    return got.vectors[0], got.model_key, got.dimensions


def _carried_stamp(vec, embedding_model, embedding_dim):
    """What a caller-supplied lore vector may claim about its own provenance.

    A vector arriving from a restore, an import or a branch is reused verbatim
    rather than recomputed, so the stamp has to travel with it or be lost. It
    used to be lost: the dump carried only the bytes, and this returned a NULL
    model for every restored entry -- which was the RIGHT answer to the
    question it was being asked, since inventing a model name from bytes would
    be a guess written down as a measurement. The fix is upstream, in what the
    dump carries; here the rule is only that a claim is honoured when one was
    made and never manufactured when it was not.

    The WIDTH still comes from the bytes when they disagree with a claimed
    dimension: the vector is the artefact, the number is a description of it.
    """
    try:
        dims = len(vec)
    except TypeError:
        dims = None
    if dims is None:
        try:
            dims = int(embedding_dim)
        except (TypeError, ValueError):
            dims = None
    model_key = str(embedding_model).strip() if embedding_model else None
    return (model_key or None), dims


def add_lore(lorebook_id, keys, content, turn_added=None, locked=0, category="other",
             title=None, knowledge_tag=None, knowledge_range=None,
             knowledge_locations=None, entry_uid=None,
             importance=0.5, aliases=None, scope=None, relations=None,
             source_notes="", embedding=None, embedding_model=None,
             embedding_dim=None):
    import uuid
    entry_uid = entry_uid or f"entry_{uuid.uuid4().hex}"
    vec = embedding
    model_key, dims = None, None
    if vec is None:
        vec, model_key, dims = _embed_lore_document(keys, content)
    else:
        model_key, dims = _carried_stamp(vec, embedding_model, embedding_dim)
    return qi("""INSERT INTO lore_entries(
            lorebook_id, keys, content, category, canon_locked, turn_added,
            embedding, title, knowledge_tag, knowledge_range,
            knowledge_locations, entry_uid, importance, aliases, scope,
            relations, source_notes, embedding_model, embedding_dim
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (lorebook_id, keys or "", content or "",
         category if category in LORE_CATEGORIES else "other",
         locked, turn_added, _blob(vec), title, knowledge_tag,
         knowledge_range, _storage_json(knowledge_locations), entry_uid,
         float(importance),
         _storage_json(aliases or []),
         _storage_json(scope or {}),
         _storage_json(relations or {}),
         source_notes, model_key, dims))

def update_lore(entry_id, keys, content, category=None, title=None,
                knowledge_tag=None, knowledge_range=None, knowledge_locations=None,
                importance=None, aliases=None, scope=None, relations=None,
                source_notes=None, embedding=None, embedding_model=None,
                embedding_dim=None):
    vec = embedding
    model_key, dims = None, None
    if vec is None:
        vec, model_key, dims = _embed_lore_document(keys, content)
    else:
        model_key, dims = _carried_stamp(vec, embedding_model, embedding_dim)
    fields = ["keys=?", "content=?", "embedding=?", "title=?",
              "knowledge_tag=?", "knowledge_range=?", "knowledge_locations=?",
              "embedding_model=?", "embedding_dim=?"]
    values = [keys or "", content or "", _blob(vec), title,
              knowledge_tag, knowledge_range, knowledge_locations,
              model_key, dims]
    
    if category and category in LORE_CATEGORIES:
        fields.append("category=?")
        values.append(category)
    if importance is not None:
        fields.append("importance=?")
        values.append(float(importance))
    if aliases is not None:
        fields.append("aliases=?")
        values.append(_storage_json(aliases))
    if scope is not None:
        fields.append("scope=?")
        values.append(_storage_json(scope))
    if relations is not None:
        fields.append("relations=?")
        values.append(_storage_json(relations))
    if source_notes is not None:
        fields.append("source_notes=?")
        values.append(source_notes)
    
    values.append(entry_id)
    qi(f"UPDATE lore_entries SET {','.join(fields)} WHERE id=?", tuple(values))

def duplicate_lorebook_tree_for_chat(root_id, chat_id, include_links=True):
    """Duplicate a lorebook subtree for a chat, preserving hierarchy and links."""
    book_ids = lorebook_descendants(root_id)
    if not book_ids:
        return {}
    
    old_to_new = {}
    
    # Pass 1: Create all books
    for old_id in book_ids:
        src = q("SELECT * FROM lorebooks WHERE id=?", (old_id,), one=True)
        if not src:
            continue
        new_id = qi("""INSERT INTO lorebooks(name,chat_id,origin_id,book_type,summary,
                      parent_id,scope_world_id,scope_location_id,inheritance_mode,sort_order,
                      resource_uid)
                      VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                    ((src["name"] or "book") + " (chat copy)", chat_id, old_id,
                     src["book_type"] or "general", src["summary"] or "",
                     src["parent_id"], src["scope_world_id"],
                     src["scope_location_id"], src["inheritance_mode"] or "inherit",
                     src["sort_order"] or 0,
                     None))
        old_to_new[old_id] = new_id
        for e in q("SELECT * FROM lore_entries WHERE lorebook_id=?", (old_id,)):
            add_lore(new_id, e["keys"], e["content"], e["turn_added"], e["canon_locked"],
                     e["category"] or "other", title=e["title"],
                     knowledge_tag=e["knowledge_tag"],
                     knowledge_range=e["knowledge_range"],
                     knowledge_locations=e["knowledge_locations"],
                     importance=e["importance"],
                     aliases=_json_list(e["aliases"]),
                     scope=json.loads(e["scope"] or "{}"),
                     relations=json.loads(e["relations"] or "{}"),
                     source_notes=e["source_notes"],
                     # The clone's keys/content are identical to the
                     # source row's, so its stored vector is reused
                     # verbatim instead of re-embedding every entry
                     # (falls back to embedding only if the source row
                     # never had a vector). Same row, same bytes, so the
                     # same stamp -- dropping it here turned every cloned
                     # book into one judged on width alone.
                     embedding=_vec(e["embedding"]),
                     embedding_model=e["embedding_model"],
                     embedding_dim=e["embedding_dim"])
    
    # Pass 2: Remap parent IDs
    for old_id, new_id in old_to_new.items():
        src = q("SELECT parent_id FROM lorebooks WHERE id=?", (old_id,), one=True)
        if src and src["parent_id"] and src["parent_id"] in old_to_new:
            qi("UPDATE lorebooks SET parent_id=? WHERE id=?",
               (old_to_new[src["parent_id"]], new_id))
        elif src and src["parent_id"]:
            # Parent was outside the subtree, null it out
            qi("UPDATE lorebooks SET parent_id=NULL WHERE id=?", (new_id,))
    
    # Pass 3: Copy links
    if include_links:
        links = dump_lorebook_links(book_ids)
        restore_lorebook_links(chat_id, old_to_new, links)
    
    return old_to_new

def duplicate_lorebook_for_chat(src_id, chat_id):
    """Legacy single-book duplication for backward compatibility."""
    return list(duplicate_lorebook_tree_for_chat(src_id, chat_id, include_links=False).values())[0]

def delete_lore(entry_id):
    qi("DELETE FROM lore_entries WHERE id=?", (entry_id,))

def search_lore(lorebook_ids, query, k=6, exclude_categories=None):
    # lorebook_ids may be a plain list/int (existing callers, unweighted --
    # every book competes as an equal) or a {book_id: weight} dict as
    # returned by chat_lorebook_weights -- _ids() already extracts the id
    # list correctly from either (iterating a dict yields its keys), so
    # this only changes behavior for callers that opt in by passing the
    # richer shape. Previously an ancestor several hops up the lorebook
    # tree, or a reference_only-linked book, scored identically to a
    # book the chat is actually attached to -- resolve_lorebook_graph
    # computed a meaningful per-book weight for exactly this and it was
    # discarded the moment chat_lorebook_ids flattened it to bare ids.
    weights = lorebook_ids if isinstance(lorebook_ids, dict) else None
    ids = _ids(lorebook_ids)
    if not ids:
        return []
    ph = ",".join("?" * len(ids))
    rows = q(f"SELECT * FROM lore_entries WHERE lorebook_id IN ({ph})", tuple(ids))
    if exclude_categories:
        rows = [r for r in rows if (r["category"] or "other") not in exclude_categories]
    if not rows:
        return []
    qv = embed_texts([query or ""])[0]
    kw = _kw_scores("lore_fts", query)
    scored = []
    # HOW MANY ROWS AM I SCORING BLIND? `_cos` returns 0.0 when the dimensions
    # disagree -- it cannot raise, because it is called in a ranking loop over
    # rows embedded at different times -- and 0.0 is also the honest score for
    # a genuinely unrelated entry. So an entry left behind by a retired
    # embedding model is INDISTINGUISHABLE from one that simply does not match,
    # and it silently forfeits the 0.65 it can never win back.
    #
    # Measured on a corpus that had run this way for months: 1,061 of 1,418
    # lore entries carried 256-dimension vectors while the configured model
    # emits 2,560, so three quarters of the corpus was competing on the 0.35
    # keyword term alone. One lorebook was 10 of 15 stale, and the entry a
    # reader kept asking after -- a room nobody could get the agents to
    # describe -- was among them. Nothing anywhere said so.
    #
    # Counted, not repaired: re-embedding is a migration and this is a ranking
    # loop. What this owes its caller is the number.
    blind = 0
    for r in rows:
        vec = _vec(r["embedding"])
        if qv is not None and vec is not None and len(qv) != len(vec):
            blind += 1
        s = (0.65 * _cos(qv, vec)
             + 0.35 * kw.get(r["id"], 0.0)
             + (0.1 if r["canon_locked"] else 0.0)
             + (0.05 * (r["importance"] or 0.5)))
        if weights is not None:
            s *= (0.7 + 0.3 * weights.get(r["lorebook_id"], 1.0))
        scored.append((s, r))
    if blind:
        logger.warning(
            "lore search scored %d of %d entries blind: their embedding "
            "dimension does not match the configured model, so only the "
            "keyword term ranked them. Re-embed to restore them.",
            blind, len(rows))
    scored.sort(key=lambda x: -x[0])
    return [
        {"id": row["id"], "entry_uid": row["entry_uid"],
         "book_id": row["lorebook_id"], "keys": row["keys"],
         "content": row["content"], "category": row["category"] or "other",
         "locked": bool(row["canon_locked"])}
        for _, row in scored[:k]
    ]

def backfill_lore_embedding_stamps(batch=500):
    """Decide what embedded each unstamped lore entry, once, and record it.

    `lore_entries` gained `embedding_model`/`embedding_dim` long after it
    gained vectors, so every row written before that carries bytes and no
    provenance. This is the one-time retrofit that puts lore into the same
    reconciliation system `memories` has always been in -- after it, the
    column carries the answer and nothing ever hashes a corpus again.

    THE TEST IS PROVIDER-INDEPENDENT, which is the whole reason it can be
    trusted. `cheap_embed` is a pure function of the text, so "is this row the
    crc32 fallback" is answerable with the provider face-down: recompute it
    and compare bytes. Width alone cannot answer that -- width is relative to
    whatever the provider happens to be emitting right now, which is exactly
    how a degraded provider inverts the question.

    A row that is not the fallback is stamped with its WIDTH and a model of
    `unknown:<dims>`. That is deliberately not a model name: the bytes cannot
    say which real model made them, and inventing one would record a guess as
    a fact. It is enough for the rebuild, which only needs to know whether a
    row matches what the live provider emits.

    ONE CAVEAT, WORTH KEEPING BESIDE IT. This proves "produced by the CURRENT
    `cheap_embed`". Change its bucket count or its hash and old fallback rows
    silently stop matching and read as real -- the same class of defect as the
    one this repairs, a comparison whose premise moved. That is an argument
    for stamping once and never asking again, which is what this does.
    """
    from llm.providers import cheap_embed
    report = {"scanned": 0, "fallback": 0, "real": 0, "unembedded": 0}
    while True:
        rows = q("SELECT id, keys, content, embedding FROM lore_entries "
                 "WHERE embedding_model IS NULL LIMIT ?", (batch,))
        if not rows:
            break
        with transaction():
            for row in rows:
                report["scanned"] += 1
                vec = _vec(row["embedding"])
                if vec is None:
                    # Never embedded is not the same as embedded badly, and
                    # they need different repairs. Stamped so the scan does
                    # not revisit it forever.
                    qi("UPDATE lore_entries SET embedding_model=?, "
                       "embedding_dim=? WHERE id=?",
                       ("none:unembedded", None, row["id"]))
                    report["unembedded"] += 1
                    continue
                text = (row["keys"] or "") + " " + (row["content"] or "")
                is_fallback = False
                if len(vec) == 256:
                    try:
                        want = np.asarray(cheap_embed(text), dtype=np.float32)
                        is_fallback = (len(want) == len(vec)
                                       and np.allclose(want, vec))
                    except Exception:  # noqa: BLE001 - cannot hash, cannot claim
                        is_fallback = False
                if is_fallback:
                    qi("UPDATE lore_entries SET embedding_model=?, "
                       "embedding_dim=? WHERE id=?",
                       ("cheap:crc32:256", 256, row["id"]))
                    report["fallback"] += 1
                else:
                    qi("UPDATE lore_entries SET embedding_model=?, "
                       "embedding_dim=? WHERE id=?",
                       ("unknown:%d" % len(vec), len(vec), row["id"]))
                    report["real"] += 1
    logger.info("memory: stamped %d lore entries (%d fallback, %d real, "
                "%d unembedded)", report["scanned"], report["fallback"],
                report["real"], report["unembedded"])
    return report


def lore_embedding_health(lorebook_ids=None):
    """How much of the lore corpus can still be ranked by meaning.

    THE QUESTION HAD NO ANSWER BEFORE THIS. The warning in `search_lore` only
    speaks when a search runs, which makes "is my lore reachable" a thing you
    discover by accident mid-story. This answers it on demand, per book when
    asked, so a corpus can be checked before it is trusted.

    `stale` counts entries whose vector cannot be compared against the current
    model's output at all. They are not gone -- the keyword term still ranks
    them -- but they compete for 0.35 against rivals playing for 1.0, which in
    practice means they never surface.
    """
    # MEASUREMENT MUST NOT DECLINE WHEN THE PROVIDER IS DOWN -- that is
    # precisely when somebody is looking. `embed_texts` degrades silently to a
    # 256-wide hash, so asking IT what the live width is turns every real
    # 2,560-wide entry into a "stale" one and reports the corpus backwards.
    # The stamp on the rows is provider-independent, so it is read first and
    # the probe is only a fallback for a corpus the backfill has not reached.
    live = _stamped_live_dimensions()
    probed = False
    if live is None:
        try:
            live = len(embed_texts([""])[0])
            probed = True
        except Exception:  # noqa: BLE001 - no provider is not a corpus finding
            live = None
    ids = _ids(lorebook_ids) if lorebook_ids is not None else None
    if ids:
        ph = ",".join("?" * len(ids))
        rows = q(f"SELECT lorebook_id, embedding, embedding_model, "
                 f"embedding_dim FROM lore_entries "
                 f"WHERE lorebook_id IN ({ph})", tuple(ids))
    else:
        rows = q("SELECT lorebook_id, embedding, embedding_model, "
                 "embedding_dim FROM lore_entries")
    total = stale = unembedded = unstamped = 0
    fallback = 0
    by_book = {}
    for r in rows or []:
        total += 1
        vec = _vec(r["embedding"])
        book = by_book.setdefault(r["lorebook_id"], {"total": 0, "stale": 0})
        book["total"] += 1
        if vec is None:
            unembedded += 1
            continue
        if r["embedding_model"] == "cheap:crc32:256":
            # Proven, not inferred: the backfill matched these against
            # `cheap_embed` of their own text. They were never embedded
            # semantically at all.
            fallback += 1
        if r["embedding_model"] is None:
            unstamped += 1
        width = r["embedding_dim"] or len(vec)
        if live is not None and width != live:
            stale += 1
            book["stale"] += 1
    return {"total": total, "stale": stale, "unembedded": unembedded,
            "fallback": fallback, "unstamped": unstamped,
            "current_dimensions": live, "probed_provider": probed,
            "books": {k: v for k, v in by_book.items() if v["stale"]}}


def _stamped_live_dimensions():
    """The width the engine's writes use: asked of the provider when it is
    answering, and of what it recorded when it is not.

    THE PROBE IS AUTHORITATIVE WHEN IT IS HEALTHY, and `embed_texts_meta` says
    which it is -- `fallback` is exactly that flag. Asking `embed_texts`
    instead cannot tell the two apart, which is how an earlier version of this
    reported a corpus backwards during an outage.

    STAMPS ARE THE FALLBACK, NOT THE FIRST ANSWER, because reading them alone
    inverts the moment a genuinely current model is NARROWER than a retired
    one: "widest real stamp" would then pick the stranded space as the
    reference and report every correct row as needing repair. That has not
    happened here -- the live space is the wider one -- and it is one model
    change away.

    Within the stamps, widest-real rather than most-common: `cheap:crc32:256`
    is easily the majority on a corpus that needs repairing, and a majority
    vote would call a wholly broken corpus healthy.
    """
    try:
        # No retry: this is a MEASUREMENT, and it runs while a host is
        # waiting. A degraded provider is an answer here, not a failure to
        # work around -- the stamps below are the fallback that matters.
        probe = embed_texts_meta([""], retry=None)
        if probe.dimensions and not probe.fallback:
            return int(probe.dimensions)
    except Exception:  # noqa: BLE001 - an unreachable provider is not an answer
        pass
    rows = q("SELECT embedding_dim AS dim FROM memories "
             "WHERE embedding_dim IS NOT NULL "
             "AND embedding_model IS NOT NULL "
             "AND embedding_model != 'cheap:crc32:256' "
             "ORDER BY embedding_dim DESC LIMIT 1")
    if rows and rows[0]["dim"]:
        return int(rows[0]["dim"])
    rows = q("SELECT MAX(embedding_dim) AS dim FROM lore_entries "
             "WHERE embedding_model IS NOT NULL "
             "AND embedding_model != 'cheap:crc32:256'")
    if rows and rows[0]["dim"]:
        return int(rows[0]["dim"])
    return None


def knowledge_for_character(lorebook_ids, char_room, known_tags, excluded_titles, limit=30):
    ids = _ids(lorebook_ids)
    if not ids or not known_tags:
        return []
    ph = ",".join("?" * len(ids))
    rows = q(f"""SELECT * FROM lore_entries WHERE lorebook_id IN ({ph})
             AND category='knowledge' ORDER BY lorebook_id, id""", tuple(ids))
    excl = set(excluded_titles or [])
    seen_titles = set()
    results = []
    for r in rows:
        tag = r["knowledge_tag"] or "common"
        if tag not in known_tags:
            continue
        title = r["title"] or ""
        if title and (title in excl or title in seen_titles):
            continue
        range_type = r["knowledge_range"] or "global"
        if range_type == "local":
            try:
                locations = json.loads(r["knowledge_locations"] or "[]")
            except Exception:
                locations = []
            if not locations:
                continue
            if char_room and char_room not in locations:
                continue
        results.append({"title": title, "content": r["content"],
                        "tag": tag, "range": range_type})
        if title:
            seen_titles.add(title)
        if len(results) >= limit:
            break
    return results

# ---- Relationship Graph ----

@dataclass
class Relationship:
    target_name: str
    trust: float = 0.0
    familiarity: float = 0.0
    emotional_valence: float = 0.0
    fear: float = 0.0
    last_interaction_turn: int = 0
    salient_event: str = ""
    notes: str = ""

@dataclass
class RelationshipGraph:
    relationships: dict[str, Relationship] = field(default_factory=dict)

    def get(self, target_name: str) -> Optional[Relationship]:
        return self.relationships.get(target_name)

    def update(self, target_name: str, **kwargs):
        r = self.relationships.setdefault(target_name, Relationship(target_name=target_name))
        for k, v in kwargs.items():
            if hasattr(r, k):
                setattr(r, k, v)

    def adjust_trust(self, target_name: str, delta: float, trigger: str = ""):
        r = self.relationships.setdefault(target_name, Relationship(target_name=target_name))
        r.trust = max(-1.0, min(1.0, r.trust + delta))
        if trigger:
            r.salient_event = trigger

    def to_dict(self) -> dict:
        return {name: asdict(rel) for name, rel in self.relationships.items()}

    @classmethod
    def from_dict(cls, data: dict) -> "RelationshipGraph":
        graph = cls()
        for name, rd in (data or {}).items():
            graph.relationships[name] = Relationship(**rd)
        return graph

def get_relationships(chat_id: int, char_id: int) -> RelationshipGraph:
    state = wget(chat_id, f"relationships:{char_id}", None)
    if state:
        return RelationshipGraph.from_dict(state)
    return RelationshipGraph()

def save_relationships(chat_id: int, char_id: int, graph: RelationshipGraph):
    wset(chat_id, f"relationships:{char_id}", graph.to_dict())

#: The three axes a stance moves along. Named here so the ledger and the
#: scalar graph cannot disagree about what they are called.
RELATIONSHIP_AXES = (("trust_delta", "trust"),
                     ("warmth_delta", "warmth"),
                     ("fear_delta", "fear"))


def record_relationship_event(chat_id, char_id, target, axis, delta, *,
                              triggers=(), note="", provenance="character",
                              turn_idx=0, frame_id=None):
    """Append one reason a stance moved. Never updated, never deleted.

    The scalar graph answers WHERE a relationship stands and cannot answer why
    it got there: it keeps a single `salient_event` string and overwrites it
    whenever the character's feelings move at all, so the reason somebody
    stopped trusting you survives until the next time they feel anything.

    Measured before this was built, because the interesting question was
    whether the reasons existed at all: 98.8% of the 5,704 stance movements in
    the live corpus already carried `trigger_event_ids`. The model had been
    saying why the entire time. This keeps what it said.
    """
    if not target or not axis or not float(delta or 0.0):
        return None
    return qi(
        "INSERT INTO relationship_events(chat_id,frame_id,char_id,target,axis,"
        "delta,triggers,note,provenance,turn_idx,created) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (int(chat_id), frame_id, int(char_id), str(target), str(axis),
         float(delta), ",".join(str(t) for t in (triggers or []) if t),
         str(note or "")[:300], str(provenance or ""), int(turn_idx or 0),
         time.time()))


def relationship_history(chat_id, char_id, target, limit=20):
    """Why this stance is where it is, oldest first.

    The question the scalar graph could never answer, and the reason item 4 of
    the off-screen roadmap exists.
    """
    rows = q("SELECT axis,delta,triggers,note,provenance,turn_idx "
             "FROM relationship_events WHERE chat_id=? AND char_id=? "
             "AND target=? ORDER BY id DESC LIMIT ?",
             (int(chat_id), int(char_id), str(target), int(limit))) or []
    return [dict(r) for r in reversed(rows)]


def apply_relationship_updates(chat_id, char_id, turn_idx, updates,
                               frame_id=None):
    graph = get_relationships(chat_id, char_id)
    for update in updates or []:
        target = str(update.get("target_entity") or "").strip()
        if not target:
            continue
        current = graph.get(target)
        if current is None:
            graph.update(target)
            current = graph.get(target)
        trust_delta = _clamp_signed(update.get("trust_delta", 0.0), -0.2, 0.2)
        warmth_delta = _clamp_signed(update.get("warmth_delta", 0.0), -0.2, 0.2)
        fear_delta = _clamp_signed(update.get("fear_delta", 0.0), -0.2, 0.2)
        trigger_ids = [t for t in (update.get("trigger_event_ids") or []) if t]
        triggers = ", ".join(trigger_ids)
        # The ledger takes one row per axis that actually moved. Axes are kept
        # apart because "trust fell and fear rose" and "trust fell" are
        # different events with different causes, and a single blended row
        # could never be read back into either.
        for field, axis in RELATIONSHIP_AXES:
            moved = {"trust_delta": trust_delta, "warmth_delta": warmth_delta,
                     "fear_delta": fear_delta}[field]
            if moved:
                record_relationship_event(
                    chat_id, char_id, target, axis, moved,
                    triggers=trigger_ids, note=update.get("reason") or "",
                    provenance="character" if trigger_ids else "unevidenced",
                    turn_idx=turn_idx, frame_id=frame_id)
        graph.update(target,
            trust=_clamp_signed(current.trust + trust_delta, -1.0, 1.0),
            emotional_valence=_clamp_signed(current.emotional_valence + warmth_delta, -1.0, 1.0),
            fear=_clamp_signed(current.fear + fear_delta, -1.0, 1.0),
            familiarity=min(1.0, current.familiarity + 0.03),
            last_interaction_turn=turn_idx,
            # Only overwrite the recorded salient event when this update
            # actually carries triggers -- a routine trigger-less delta
            # must not erase previously recorded history.
            **({"salient_event": triggers[-300:]} if triggers else {}))
    save_relationships(chat_id, char_id, graph)
    return graph

# How far one inference moves trust, by direction. Deliberately asymmetric:
# concluding somebody cannot be trusted is worth more than concluding they
# can, because the cost of the two mistakes is not the same. This is
# psychology, not language, so it does NOT live in the pack -- only the
# vocabularies that decide which direction a conclusion points do.
_TRUST_INFERENCE_STEP = {"trusting": 0.1, "wary": -0.15}


def update_relationships_from_inference(chat_id, char_id, turn_idx,
                                        inference_updates, existing=None,
                                        frame_id=_UNSET):
    """Move a stance from what the character CONCLUDED about someone.

    The second of the two paths that move the scalar graph, and the one that
    left no trace. `apply_relationship_updates` writes a `relationship_events`
    row per axis that moved -- a ledger that is never updated and never deleted,
    because the graph holds one `salient_event` string and overwrites it
    whenever the character feels anything at all. This path moved the same
    scalar, on the same graph, saved by the same call, and recorded nothing. A
    whole class of trust movement was missing from the record of why trust is
    where it is, and the gap does not surface as a wrong row: it surfaces as a
    stance whose history cannot explain it.

    The reason is stamped `inference` rather than `character`, because
    concluding somebody is dangerous and being told so are different
    provenances and the ledger already exists to keep that difference.

    Which conclusions move trust is a question about WORDS, so the two
    vocabularies live in the pack (`mind.memory._TRUST_INFERENCE_CUES`); how
    far each moves it does not, so the step stays here. Before this, a
    Japanese story drew every inference it liked and none of them ever moved
    a relationship, silently.
    """
    graph = existing or get_relationships(chat_id, char_id)
    resolved_frame_id = (
        _active_frame_id.get() if frame_id is _UNSET else frame_id)
    for u in inference_updates:
        about = u.get("about", "")
        if not about:
            continue
        confidence = float(u.get("confidence", 0.5))
        conclusion = u.get("conclusion", "")
        cl = conclusion.lower()
        trust_delta = 0.0
        for direction, cues in _ling("_TRUST_INFERENCE_CUES"):
            if any(w in cl for w in cues):
                trust_delta = _TRUST_INFERENCE_STEP[direction] * confidence
                break
        if trust_delta != 0:
            graph.adjust_trust(about, trust_delta, conclusion[:200])
            # The conclusion IS the reason, so it is the note. No trigger ids:
            # an inference cites the events it was drawn from upstream, and
            # inventing one here would put a fabricated citation in a ledger
            # that is never corrected.
            record_relationship_event(
                chat_id, char_id, about, "trust", trust_delta,
                note=conclusion, provenance="inference",
                turn_idx=turn_idx, frame_id=resolved_frame_id)
        graph.update(about,
            familiarity=min(1.0, (graph.get(about).familiarity + 0.05) if graph.get(about) else 0.05),
            last_interaction_turn=turn_idx)
    save_relationships(chat_id, char_id, graph)
    return graph

def relationships_for_payload(chat_id: int, char_id: int) -> dict:
    graph = get_relationships(chat_id, char_id)
    return graph.to_dict()

# ---- Rebuilding vectors after the embedding model changes ----

# Rows per embedding call. Each memory costs TWO documents (its full document
# and its cue text), so a batch of 32 is 64 texts -- comfortably inside every
# provider's per-request limit while still amortising the round trip.
_REBUILD_BATCH = 32


def embedding_bank_status(chat_id=None, char_id=None):
    """How many stored rows were embedded by a model other than the live one.

    Read-only, and cheap: it is the question `_warn_stranded_embeddings`
    answers per retrieval, asked deliberately and for the whole bank so a host
    can see the split before deciding to spend on rebuilding it.

    ASKED WITHOUT RETRIES. This runs on the chat-open path, where the host is
    watching a story fail to appear, and `is_fallback` is a REPORTED state
    rather than an error to survive -- the panel says "no embeddings provider
    is answering" and says why. Spending the write path's retry budget here
    would only make a degraded provider slow to admit to.

    A COMPARISON NEEDS BOTH SIDES. The probe answers "what does the engine
    embed with right now", and when it falls back that answer is a
    PLACEHOLDER, not the live model's identity. Read as an identity it
    strands the whole bank: measured live 2026-08-11, chat 70 held 34
    memories every one of them correctly stamped
    `openrouter:3:perplexity/pplx-embed-v1-4b`, the open-chat probe hit that
    provider's rate limit, and the host was told all 34 were written by a
    different model and should go configure the provider they already had.

    So the configured role -- read from settings, no network -- separates the
    two cases the probe cannot:

      no provider configured  the hash IS this engine's embedding. Real
                              stamps genuinely are keyword-only, and a
                              rebuild onto the hash is a downgrade. Compare.
      configured, not answering
                              the live model is known and simply silent. No
                              row is classifiable, so none is reported, and
                              `live_unknown` says why rather than inventing a
                              migration out of a 429.
    """
    live = embed_texts_meta(["status"], retry=None)
    configured = embedding_model_key()
    no_provider = configured == "cheap:crc32:256"
    live_unknown = bool(live.fallback) and not no_provider
    where, args = ["1=1"], []
    if chat_id is not None:
        where.append("chat_id=?"); args.append(chat_id)
    if char_id is not None:
        where.append("char_id=?"); args.append(char_id)
    clause = " AND ".join(where)
    stale = ("(embedding_model IS NULL OR embedding_model!=? "
             "OR embedding_dim IS NULL OR embedding_dim!=?)")
    counts = {}
    for table in ("memories", "memory_summaries"):
        total = q(f"SELECT COUNT(*) AS n FROM {table} WHERE {clause}",
                  tuple(args), one=True)["n"]
        stranded = 0 if live_unknown else q(
            f"SELECT COUNT(*) AS n FROM {table} WHERE {clause} AND {stale}",
            tuple(args) + (live.model_key, live.dimensions), one=True)["n"]
        # Of those, the ones THIS ENGINE failed to write rather than the ones
        # a model change stranded. The hash stamp separates them exactly: a
        # crc32 row under a real provider is a call that fell back, which the
        # repair queue finishes on its own, while another model's key is a
        # migration a host chooses. Only the second is worth a question.
        fallback_written = 0 if live.fallback else q(
            f"SELECT COUNT(*) AS n FROM {table} WHERE {clause} "
            "AND embedding_model='cheap:crc32:256'",
            tuple(args), one=True)["n"]
        counts[table] = {"total": total, "stranded": stranded,
                         "fallback_written": fallback_written}
    # LORE, counted with the SAME predicate that repairs it. Without this the
    # bank could not see the one table it has a repair lane for, and
    # `start_rebuild_if_needed` summed a total lore never entered -- so a
    # database whose ONLY stale vectors were lore reported "nothing to
    # rebuild" forever while the lane sat behind it, working, unreachable.
    #
    # It must be the REPAIR's predicate and not the `stale` clause above.
    # Lore rows carry a NULL stamp far more often than memories do, and the
    # repair treats a NULL stamp as stale only when the vector's WIDTH is
    # wrong. Counting every unstamped row as stranded would report rows the
    # repair will never select -- live, four entries already at the correct
    # width with no stamp -- and the count could then never reach zero, which
    # turns a reconciler into something that starts a rebuild on every call
    # forever. A wrong counter here is worse than no counter.
    book_ids = _rebuild_book_ids(chat_id)
    lore_total = lore_stranded = 0
    if book_ids:
        holes = ",".join("?" * len(book_ids))
        lore_total = q(f"SELECT COUNT(*) AS n FROM lore_entries "
                       f"WHERE lorebook_id IN ({holes})",
                       tuple(book_ids), one=True)["n"]
        # Totals are a fact about the bank; staleness is a comparison, and
        # with the live model silent there is nothing to compare against.
        lore_stranded = 0 if live_unknown else q(
            f"SELECT COUNT(*) AS n FROM lore_entries "
            f"WHERE lorebook_id IN ({holes}) AND embedding IS NOT NULL "
            "AND ((embedding_model IS NOT NULL "
            "      AND (embedding_model != ? OR embedding_dim != ?)) "
            "  OR (embedding_model IS NULL AND length(embedding) != ?))",
            tuple(book_ids) + (live.model_key, live.dimensions,
                               (live.dimensions or 0) * 4), one=True)["n"]
    counts["lore_entries"] = {"total": lore_total, "stranded": lore_stranded}
    return {
        # The model the engine embeds with. When the provider is silent that
        # is still the CONFIGURED one -- reporting the hash placeholder here
        # is what told a host their Perplexity corpus was written by a
        # different model than Perplexity.
        "model": configured if live_unknown else live.model_key,
        "dimensions": live.dimensions,
        # NO EMBEDDINGS PROVIDER IS CONFIGURED -- which is the only thing
        # every consumer of this flag uses it for: the panel offers to set
        # one, the chat-open toast says to set one, and `start_rebuild_if_-
        # needed` refuses to rebuild onto the hash. It used to be
        # `live.fallback`, i.e. "the last probe failed", so one rate-limited
        # request presented as an unconfigured engine.
        "is_fallback": no_provider,
        # A provider IS configured and did not answer this probe. Nothing is
        # comparable, so every `stranded` above is 0 by construction and a
        # caller must say "cannot tell" rather than "nothing to do".
        "live_unknown": live_unknown,
        # WHY it fell back, verbatim from the provider. Without this the
        # panel can only say "no embeddings provider", which is wrong and
        # unhelpful when one IS configured and is simply not an embeddings
        # model: `embed_texts_meta` catches every failure and degrades to the
        # hash, so choosing a chat model for this role looks like success and
        # silently changes nothing. Measured live -- `inception/mercury-2`
        # selected here returned "Model inception/mercury-2 does not exist",
        # which is exactly the sentence a host needs to see.
        "fallback_reason": str(live.error or "") if live.fallback else "",
        **counts,
    }


def _rebuild_book_ids(chat_id):
    """Which lorebooks a rebuild covers.

    Scoped to the chat when one is named, because that is how the reconciler
    is called after a restore and re-embedding an unrelated 300-entry book on
    somebody's reroll would be a surprise bill. Every book when it is not.
    """
    if chat_id is None:
        return [r["id"] for r in q("SELECT id FROM lorebooks") or []]
    ids = []
    row = q("SELECT lorebook_id FROM chats WHERE id=?", (chat_id,), one=True)
    if row and row["lorebook_id"]:
        ids.append(row["lorebook_id"])
    for r in q("SELECT lorebook_id FROM chat_lorebooks WHERE chat_id=?",
               (chat_id,)) or []:
        if r["lorebook_id"] not in ids:
            ids.append(r["lorebook_id"])
    for r in q("SELECT id FROM lorebooks WHERE chat_id=?", (chat_id,)) or []:
        if r["id"] not in ids:
            ids.append(r["id"])
    return ids


def rebuild_embeddings(chat_id=None, char_id=None, *, batch=_REBUILD_BATCH,
                       limit=None, progress=None):
    """Re-embed every row whose vectors were made by a different model.

    Configuring an `embeddings` provider on a story with history does not
    re-embed anything, and `search_memories` scores a row 0.0 on BOTH vector
    rankings when its `embedding_model`/`embedding_dim` do not match the live
    ones. Without this pass, the upgrade silently splits a memory bank into
    two eras -- everything written before it reachable only by keyword and
    exact match, forever. See docs/UNBUILT.md §1.15.

    Rebuilt with the SAME document construction `_embed_memory` uses, because
    a vector built from different text is not comparable with one built from
    the same text, and a rebuild that quietly changed the recipe would be a
    subtler version of the bug it fixes.

    **Resumable by construction**: the selection is "rows that do not match
    the live model", so a run that dies halfway simply has less to do next
    time. Each batch commits on its own for that reason.

    **Refuses to write a fallback over a real vector.** `embed_texts_meta`
    degrades to the crc32 hash on any provider error, and stamps the batch as
    `cheap:crc32:256`. Writing that would mark the rows migrated while
    downgrading them -- the one outcome worse than not running. A batch that
    comes back `fallback` when the caller is not deliberately rebuilding TO
    the fallback aborts the run and reports what it managed.

    Never call this on the turn path: it is O(bank) and it talks to a provider.
    """
    live = embed_texts_meta(["status"])
    target_key, target_dim = live.model_key, live.dimensions
    # A fallback batch may be WRITTEN only when the hash is what this run is
    # migrating onto -- the run's own target, not a fact about one request.
    # It must also be the target, not merely a failed probe: writing crc32
    # while `target_key` is a real model marks rows migrated that the `stale`
    # predicate will select again forever, which is a rebuild that never
    # terminates.
    want_fallback = target_key == "cheap:crc32:256"
    report = {"model": target_key, "dimensions": target_dim,
              "memories": 0, "summaries": 0, "lore": 0, "batches": 0,
              "stopped_early": False, "error": ""}
    if live.fallback and embedding_model_key() != "cheap:crc32:256":
        # A provider IS configured and did not answer this probe, so there is
        # nothing to rebuild ONTO: `target_key` is the hash placeholder, it
        # matches no stored row, and proceeding would either select the whole
        # bank to overwrite with hashes or stop on the first batch. Whether
        # the host has an embeddings provider is a settings fact; read as
        # `live.fallback` instead, one rate-limited request would have turned
        # the guard above off and licensed a real corpus to be overwritten.
        report["stopped_early"] = True
        report["error"] = ("embedding provider unavailable (%s); nothing "
                           "rebuilt" % (live.error or "unknown"))
        return report

    where, args = ["1=1"], []
    if chat_id is not None:
        where.append("chat_id=?"); args.append(chat_id)
    if char_id is not None:
        where.append("char_id=?"); args.append(char_id)
    clause = " AND ".join(where)
    stale = ("(embedding_model IS NULL OR embedding_model!=? "
             "OR embedding_dim IS NULL OR embedding_dim!=?)")
    stale_args = tuple(args) + (target_key, target_dim)

    def _embed(texts):
        """Embed, or raise so the run stops with the bank still coherent."""
        got = embed_texts_meta(texts)
        if got.fallback and not want_fallback:
            raise RuntimeError(
                "embedding provider unavailable (%s); refusing to write "
                "fallback vectors over real ones" % (got.error or "unknown"))
        return got

    done = 0
    try:
        while limit is None or done < limit:
            take = batch if limit is None else min(batch, limit - done)
            rows = q(f"SELECT * FROM memories WHERE {clause} AND {stale} "
                     "ORDER BY id LIMIT ?", stale_args + (take,))
            if not rows:
                break
            mems = [_row_memory(r) for r in rows]
            docs = []
            for mem in mems:
                docs.append(_memory_document(mem))
                docs.append(_memory_cues(mem) or _memory_document(mem))
            got = _embed(docs)
            with transaction():
                for index, mem in enumerate(mems):
                    qi("UPDATE memories SET embedding=?,cue_embedding=?,"
                       "embedding_model=?,embedding_dim=? WHERE id=?",
                       (_blob(got.vectors[index * 2]),
                        _blob(got.vectors[index * 2 + 1]),
                        got.model_key, got.dimensions, mem["id"]))
            done += len(rows)
            report["memories"] += len(rows)
            report["batches"] += 1
            if progress:
                progress(report["memories"], "memories")

        while True:
            rows = q(f"SELECT * FROM memory_summaries WHERE {clause} AND {stale} "
                     "ORDER BY id LIMIT ?", stale_args + (batch,))
            if not rows:
                break
            texts = [_summary_retrieval_text(
                r["summary"], _json_list(r["key_phrases"]),
                _json_list(r["unresolved_threads"])) for r in rows]
            got = _embed(texts)
            with transaction():
                for index, row in enumerate(rows):
                    qi("UPDATE memory_summaries SET embedding=?,"
                       "embedding_model=?,embedding_dim=? WHERE id=?",
                       (_blob(got.vectors[index]), got.model_key,
                        got.dimensions, row["id"]))
            report["summaries"] += len(rows)
            report["batches"] += 1
            if progress:
                progress(report["summaries"], "summaries")

        # LORE WAS LEFT OUT OF THIS, and it has the same disease with none of
        # the cure. `search_lore` scores an entry 0.0 on its 0.65 vector term
        # when the dimensions disagree, so a lorebook embedded before the
        # provider changed goes on ranking by keyword alone and simply looks
        # like a lorebook the agents ignore. Measured live: 1,061 of 1,418
        # entries stranded, one book 10 of 15, and the one room a reader kept
        # asking after was among them.
        #
        # It also has to be here rather than in a tool of its own, because
        # `checkpoints.restore_state` calls `start_rebuild_if_needed` to undo
        # exactly this damage after a restore -- a checkpoint carries lore
        # vectors verbatim, so rewinding past a migration silently reverts it.
        # A repair that lives outside this function is a repair a reroll
        # quietly discards.
        #
        # `lore_entries` has no `embedding_model`/`embedding_dim` columns, so
        # staleness is the vector's WIDTH rather than a recorded model key.
        # That is weaker -- two models sharing a width are indistinguishable --
        # and it is what the schema supports.
        # NOT WHEN THE TARGET IS THE FALLBACK. Lore staleness is measured by
        # the vector's WIDTH, so a degraded provider inverts the test: the
        # crc32 fallback is 256 wide, every real 2,560-wide entry then reads as
        # stale, and a background reconciler firing on a reroll during a
        # provider hiccup would quietly downgrade the entire corpus it was
        # called to protect. The memory pass survives this because it compares
        # model KEYS and a caller can legitimately rebuild onto the fallback;
        # lore has no key to compare, so the only safe answer is to wait.
        book_ids = _rebuild_book_ids(chat_id)
        if want_fallback and book_ids:
            # NO REPAIR IS AVAILABLE IN THIS STATE, which is a stronger reason
            # than the one this guard was first written for. Every write the
            # pass could make while the provider is degraded is a fallback
            # write -- overwriting a crc32 vector with a freshly computed
            # crc32 vector -- so "refuse to write a fallback" and "decline the
            # pass" are the same instruction. It is the decision the memories
            # path already makes; see the stopped_early test.
            logger.info("memory: skipping the lore pass, the embedding "
                        "provider is degraded -- every write it could make "
                        "would be another fallback")
            book_ids = []
        if book_ids and target_dim:
            book_ph = ",".join("?" * len(book_ids))
            while True:
                # STAMP FIRST, WIDTH ONLY WHERE THERE IS NO STAMP. A recorded
                # model key answers "is this row current" exactly; width is a
                # proxy that cannot tell two models sharing a width apart, and
                # it is only still here for rows the backfill has not reached.
                rows = q(
                    f"SELECT id, keys, content FROM lore_entries "
                    f"WHERE lorebook_id IN ({book_ph}) AND embedding IS NOT NULL "
                    f"AND ((embedding_model IS NOT NULL "
                    f"      AND (embedding_model != ? OR embedding_dim != ?)) "
                    f"  OR (embedding_model IS NULL "
                    f"      AND length(embedding) != ?)) "
                    f"ORDER BY id LIMIT ?",
                    tuple(book_ids) + (target_key, target_dim,
                                       target_dim * 4, batch))
                if not rows:
                    break
                # EXACTLY the document `update_lore` builds. A vector made from
                # different text is not comparable with one made from the same
                # text, and a rebuild that quietly changed the recipe would be a
                # subtler version of the bug it fixes.
                texts = [(r["keys"] or "") + " " + (r["content"] or "")
                         for r in rows]
                got = _embed(texts)
                with transaction():
                    for index, row in enumerate(rows):
                        qi("UPDATE lore_entries SET embedding=?,"
                           "embedding_model=?,embedding_dim=? WHERE id=?",
                           (_blob(got.vectors[index]), got.model_key,
                            got.dimensions, row["id"]))
                report["lore"] += len(rows)
                report["batches"] += 1
                if progress:
                    progress(report["lore"], "lore")
    except Exception as exc:
        # Everything committed so far stands, and re-running resumes.
        report["stopped_early"] = True
        report["error"] = str(exc)
        logger.warning("memory: embedding rebuild stopped early after "
                       "%d memories, %d summaries and %d lore entries: %s",
                       report["memories"], report["summaries"],
                       report["lore"], exc)
        return report

    # A rebuilt row is no longer stranded, so let the per-retrieval warning
    # speak again if it ever becomes true a second time.
    _STRANDED_REPORTED.clear()
    logger.info("memory: rebuilt %d memories, %d summaries and %d lore "
                "entries onto %s", report["memories"], report["summaries"],
                report["lore"], target_key)
    return report


def _vector_key(char_id, text):
    """Address a saved row by whose it is and the exact text that was embedded.

    Checkpoint dumps carry no row id, so the join has to be on content. What
    counts as "the content" is the whole point: it must be the string the
    vector was actually computed FROM, or the join can hand a row someone
    else's vector.

    The first version keyed a memory on its `content` field alone, reasoning
    that a vector is a pure function of the memory. It is -- but not of its
    content: `_memory_document` also folds in turn, location, category,
    key_phrases, entities, gist, provenance and emotional_context, and a
    summary's vector comes from `_summary_retrieval_text`, not its `summary`
    field. Two rows can therefore agree on the keyed field and hold genuinely
    different vectors. `vector_address` hit exactly this in production --
    checkpoint 855 of chat 36 held "You are in Ten Forward." at turn 42 and
    again at turn 44, same character, two different embedding payloads -- and
    was moved to byte-addressing; the note it left said this join still
    carried the old assumption. It no longer does.
    """
    body = " ".join(str(text or "").split())
    return (char_id, hashlib.sha1(body.encode("utf-8", "ignore")).hexdigest())


def _memory_vector_key(data):
    """Address a memory by the document its vector is computed from."""
    return _vector_key(data.get("char_id"), _memory_document(data))


def _summary_vector_key(data):
    """Address a summary by the retrieval text its vector is computed from."""
    return _vector_key(data.get("char_id"),
                       _summary_retrieval_text(data.get("summary"),
                                               data.get("key_phrases"),
                                               data.get("unresolved_threads")))


def rebuild_checkpoint_embeddings(chat_id=None, *, dry_run=True, progress=None):
    """Carry a completed rebuild back through a story's saved states.

    A checkpoint stores each memory's vector verbatim so that restoring one
    never re-embeds a bank (see `_blob_to_b64`). That is right, and it means a
    checkpoint written BEFORE a rebuild holds the old vectors and the old model
    key -- so rolling back to it silently undoes the rebuild. Measured live:
    one reroll put 637 of 642 rows back on the crc32 fallback.

    **This re-embeds nothing.** A vector is a pure function of the memory's
    content, and the same memory appears in dozens of checkpoints unchanged --
    chat 38 held 40,224 memory copies across its checkpoints and only 526
    distinct by content, 90.7% of which already had a rebuilt vector in the
    live table. So the fix is substitution, not computation: look each saved
    memory up by (character, content) and write in the vector already earned.

    Deliberately conservative, because this rewrites rollback history:

    * a saved row with no live match is left EXACTLY as it was, never blanked
      and never guessed at (those are memories since deleted; if one is ever
      restored, `start_rebuild_if_needed` picks it up);
    * a blob is rewritten only if something actually changed, and only after
      re-parsing to prove it is still valid JSON with the same row count;
    * `dry_run` is the default -- it reports what it would do and writes
      nothing.

    Resumable by construction: a checkpoint already carrying the live model
    key has nothing to substitute and is skipped on the next pass.
    """
    live = embed_texts_meta(["status"])
    key, dim = live.model_key, live.dimensions
    where, args = ["1=1"], []
    if chat_id is not None:
        where.append("chat_id=?"); args.append(chat_id)
    clause = " AND ".join(where)

    # Every column `_memory_document` reads, because the key is that document
    # and not the `content` slice of it.
    vectors = {}
    for row in q(f"SELECT char_id, category, turn_idx, location, entities, "
                 f"key_phrases, gist, content, provenance, emotional_context, "
                 f"embedding, cue_embedding "
                 f"FROM memories WHERE {clause} AND embedding_model=? "
                 f"AND embedding_dim=?", tuple(args) + (key, dim)):
        vectors[_memory_vector_key({
            "char_id": row["char_id"], "category": row["category"],
            "turn_idx": row["turn_idx"], "location": row["location"],
            "entities": _json_list(row["entities"]),
            "key_phrases": _json_list(row["key_phrases"]),
            "gist": row["gist"], "content": row["content"],
            "provenance": row["provenance"],
            "emotional_context": row["emotional_context"],
        })] = (_blob_to_b64(row["embedding"]),
               _blob_to_b64(row["cue_embedding"]))
    summaries = {}
    for row in q(f"SELECT char_id, summary, key_phrases, unresolved_threads, "
                 f"embedding FROM memory_summaries "
                 f"WHERE {clause} AND embedding_model=? AND embedding_dim=?",
                 tuple(args) + (key, dim)):
        summaries[_summary_vector_key({
            "char_id": row["char_id"], "summary": row["summary"],
            "key_phrases": _json_list(row["key_phrases"]),
            "unresolved_threads": _json_list(row["unresolved_threads"]),
        })] = _blob_to_b64(row["embedding"])

    report = {"model": key, "checkpoints": 0, "rewritten": 0,
              "memories_repaired": 0, "summaries_repaired": 0,
              "memories_unmatched": 0, "dry_run": bool(dry_run)}
    if not vectors and not summaries:
        return report

    rows = q(f"SELECT id, chat_id, turn_idx, blob FROM checkpoints "
             f"WHERE {clause} ORDER BY id", tuple(args))
    for row in rows:
        report["checkpoints"] += 1
        try:
            blob = json.loads(row["blob"])
        except (TypeError, ValueError):
            continue          # an unreadable checkpoint is left untouched
        changed = 0
        for mem in (blob.get("memories") or []):
            if not isinstance(mem, dict):
                continue
            if mem.get("embedding_model") == key and mem.get("embedding_dim") == dim:
                continue
            hit = vectors.get(_memory_vector_key(mem))
            if hit is None:
                report["memories_unmatched"] += 1
                continue
            mem["embedding"], mem["cue_embedding"] = hit
            mem["embedding_model"], mem["embedding_dim"] = key, dim
            changed += 1
            report["memories_repaired"] += 1
        for summ in (blob.get("memory_summaries") or []):
            if not isinstance(summ, dict):
                continue
            if summ.get("embedding_model") == key and summ.get("embedding_dim") == dim:
                continue
            hit = summaries.get(_summary_vector_key(summ))
            if hit is None:
                continue
            summ["embedding"] = hit
            summ["embedding_model"], summ["embedding_dim"] = key, dim
            changed += 1
            report["summaries_repaired"] += 1
        if not changed or dry_run:
            continue
        text = json.dumps(blob, ensure_ascii=False)
        # Prove it before it replaces rollback history: parseable, and the
        # same number of rows it went in with.
        check = json.loads(text)
        if (len(check.get("memories") or []) != len(blob.get("memories") or [])
                or sorted(check) != sorted(blob)):
            continue
        qi("UPDATE checkpoints SET blob=? WHERE id=?", (text, row["id"]))
        report["rewritten"] += 1
        if progress:
            progress(report["rewritten"], report["checkpoints"])
    if not dry_run and report["rewritten"]:
        logger.info("memory: carried the rebuild into %d checkpoint(s); "
                    "%d saved memories repaired, %d left unmatched",
                    report["rewritten"], report["memories_repaired"],
                    report["memories_unmatched"])
    return report


# ---- The rebuild, run for the host instead of by the host ----------------
#
# Nobody should have to know that changing an embeddings provider silently
# halves their retrieval, notice that it happened, find a maintenance command
# and run it. The engine knows the model it is embedding with and the model
# every stored row was embedded with; where those disagree it can simply fix
# it. This is the standing reconciler that does.
#
# NOT a one-time upgrade migration, and that distinction is the whole design:
# a mismatch appears whenever the embedding model changes -- configuring a
# provider, switching providers, a provider changing its default model or its
# dimensions, or falling back to the crc32 hash because a key expired. So this
# is a condition to be reconciled whenever it holds, checked at startup and
# again whenever provider settings are written, rather than a migration that
# runs once and is never thought about again.

_REBUILD_LOCK = threading.Lock()
_REBUILD_STATE = {
    "running": False, "done": 0, "total": 0, "model": "",
    "finished_at": 0.0, "error": "", "stopped_early": False,
}


def rebuild_progress():
    """A snapshot of the reconciler, for the status endpoint."""
    with _REBUILD_LOCK:
        return dict(_REBUILD_STATE)


def _run_rebuild(chat_id=None, char_id=None):
    status = embedding_bank_status(chat_id, char_id)
    total = (status["memories"]["stranded"]
             + status["memory_summaries"]["stranded"])
    with _REBUILD_LOCK:
        _REBUILD_STATE.update(running=True, done=0, total=total,
                              model=status["model"], error="",
                              stopped_early=False, finished_at=0.0)
    try:
        def _tick(count, _kind):
            with _REBUILD_LOCK:
                # Memories are rebuilt before summaries, so the summary pass
                # continues the same count rather than restarting it.
                _REBUILD_STATE["done"] = max(_REBUILD_STATE["done"], count)
        report = rebuild_embeddings(chat_id, char_id, progress=_tick)
        with _REBUILD_LOCK:
            _REBUILD_STATE.update(
                done=report["memories"] + report["summaries"],
                error=report["error"], stopped_early=report["stopped_early"])
    except Exception as exc:           # never take the server down for this
        logger.warning("memory: embedding rebuild failed: %s", exc)
        with _REBUILD_LOCK:
            _REBUILD_STATE.update(error=str(exc), stopped_early=True)
    finally:
        with _REBUILD_LOCK:
            _REBUILD_STATE.update(running=False, finished_at=time.time())


def start_rebuild_if_needed(chat_id=None, char_id=None, *, force=False):
    """Reconcile stored vectors with the live embedding model, in the
    background. Returns what it decided, having already started if it started.

    Safe to call on every startup and every settings write: it costs one
    COUNT per table when there is nothing to do, and it will not start a
    second run while one is going.
    """
    with _REBUILD_LOCK:
        if _REBUILD_STATE["running"]:
            return {"started": False, "reason": "already running"}
    try:
        status = embedding_bank_status(chat_id, char_id)
    except Exception as exc:
        logger.warning("memory: could not check embedding bank: %s", exc)
        return {"started": False, "reason": "status check failed: %s" % exc}
    if status.get("live_unknown"):
        # The configured provider did not answer, so every count below is 0
        # by construction and "nothing to rebuild" would be a guess wearing a
        # fact's clothes. Say what happened; the next call re-checks.
        return {"started": False,
                "reason": "embedding provider not answering", **status}
    # Lore counts. It did not, and `rebuild_embeddings` has had a working lore
    # lane behind this gate the whole time -- so a database whose only stale
    # vectors were lore was told "nothing to rebuild" on every startup and
    # every settings write, forever, while the repair sat one call away.
    # Measured live: 1,087 lore rows selected by the repair's own predicate,
    # and this function returning `nothing to rebuild`.
    stranded = (status["memories"]["stranded"]
                + status["memory_summaries"]["stranded"]
                + status.get("lore_entries", {}).get("stranded", 0))
    if not stranded:
        return {"started": False, "reason": "nothing to rebuild", **status}
    if status["is_fallback"] and not force:
        # The live "model" is the crc32 hash, which means no embeddings
        # provider is configured. Rebuilding onto it would overwrite real
        # vectors with the fallback -- a downgrade, and one the host never
        # asked for. Wait for a provider, or for an explicit force.
        logger.info("memory: %d rows do not match the live embedding model, "
                    "but no embeddings provider is configured -- not "
                    "rebuilding onto the fallback.", stranded)
        return {"started": False, "reason": "no embeddings provider", **status}
    logger.info("memory: rebuilding %d rows onto %s in the background",
                stranded, status["model"])
    thread = threading.Thread(target=_run_rebuild, args=(chat_id, char_id),
                              name="embedding-rebuild", daemon=True)
    thread.start()
    return {"started": True, "stranded": stranded, **status}


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
