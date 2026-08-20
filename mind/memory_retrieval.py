"""Hybrid retrieval: what a mind recalls when asked, and what surfaces unbidden.

Lexical ranking and vector similarity fused by reciprocal rank, tilted by mood
congruence and rank-normalised importance."""

import re
import time
from collections import defaultdict
from core.db import q, qi
from llm.providers import embed_texts_meta
from core.logging_utils import logger

from mind.memory_common import (
    _SUMMARY_SCOPES, _UNSET, _cos, _ling, _vec, summary_scope_for,
)
from mind.memory_write import _clamp, _row_memory, effective_importance
from mind.memory_read import visible_memory_rows

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

# The exact signal's full tier is reserved for DISTINCTIVE stored phrases --
# a quoted utterance, a proper multi-word cue -- because that is the signal
# MEMORY.md 5 documents as strongest and rarest. "Distinctive" is three or
# more tokens by the pack word regex (stopwords included -- "in the kitchen"
# qualifies); a stricter content-bearing count is untried and would need its
# own probe measurement. Key phrases also carry the
# frequency counter's unigrams and bigrams ("the woman", "told us"), and a
# bigram literally present in the query is usually a coincidence of common
# words: measured on the repaired tuning bank, those fires alone put 3-20
# arbitrary rows into the highest-weighted RRF list and pushed
# semantically-best targets out of the payload (tuned probes 24/26 -> 21/26).
# Word overlap is the LEXICAL leg's job (BM25 weighs it properly); a generic
# phrase fire is demoted below the entity tier so it can nudge the scalar
# bonus but never claim the exact list's full rank weight.
_EXACT_DISTINCTIVE_TOKENS = 3
_EXACT_GENERIC_TIER = 0.6


def _distinctive_phrase(phrase):
    return len(_ling("_WORD_RE").findall(phrase)) >= _EXACT_DISTINCTIVE_TOKENS


_BOUNDARY_RE_CACHE: dict[str, "re.Pattern"] = {}


def _boundary_re(literal):
    """The word-boundary matcher for one cue, compiled once per literal.

    `re.escape` plus an f-string plus a pattern-cache lookup ran per row per
    cue per query. Measured over 8 queries on a 10,960-row bank: 87,680 calls
    to `_exact_cue_score`, 79.9 of the run's 89.9 seconds -- 89% of ALL
    retrieval time, against roughly 10% for the vector scan. The cues repeat
    constantly across a bank, so the distinct literals are few and this cache
    is small.
    """
    got = _BOUNDARY_RE_CACHE.get(literal)
    if got is None:
        got = re.compile(
            r"(?<![A-Za-z0-9])%s(?![A-Za-z0-9])" % re.escape(literal))
        # Bounded so a pathological bank cannot grow this without limit; the
        # cues in one bank are far below it.
        if len(_BOUNDARY_RE_CACHE) < 20000:
            _BOUNDARY_RE_CACHE[literal] = got
    return got


def _exact_cue_score(memory, query_text):
    ql = (query_text or "").lower()
    if not ql:
        return 0.0
    score = 0.0
    for phrase in memory.get("key_phrases") or []:
        pl = phrase.lower().strip()
        if pl and pl in ql:
            score = max(score, 1.0 if _distinctive_phrase(pl)
                        else _EXACT_GENERIC_TIER)
        elif pl and ql in pl and len(ql) >= 4:
            score = max(score, 0.8)
    for entity in memory.get("entities") or []:
        el = entity.lower().strip()
        # Word-boundary, not bare substring: a stored "Mara" must not fire
        # inside "marathon". Insufficient alone (audit 1.3 measured it), but
        # correct, and cheap now that the stock is junk-free. The boundary
        # class is ASCII alphanumerics, NOT \w: substring-inside-a-word is an
        # alphabetic-script hazard, while \w counts every CJK character as a
        # word character -- so it silenced this cue for Japanese banks, where
        # a name is followed directly by its particle (a stored entity
        # stopped firing inside a query naming it before the particle).
        # Found by adversarial review of this branch.
        # `el in ql` is a NECESSARY condition for the boundary regex to
        # match, and it is a C-speed substring test against a regex search
        # that dominated the whole retrieval path. Semantics are unchanged:
        # every match the regex would find still reaches it.
        if el and el in ql and _boundary_re(el).search(ql):
            score = max(score, 0.7)
    loc = (memory.get("location") or "").lower().strip()
    if loc and loc in ql and _boundary_re(loc).search(ql):
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
# 24 since 2026-08-20, and the 16 it replaces was a considered choice rather
# than a default, so the reasoning that moved it is recorded here rather than
# overwritten.
#
# The case for 16 was: paraphrase recall 7/16 -> 11/16 -> 13/16 across 8/16/24,
# relevance flattening (0.640 -> 0.649), payload growing ~890 -> ~1242 tokens
# per character per beat, and a real attention budget (UNBUILT 1.12). Nothing
# in that is wrong. What changed is the evidence available on both sides.
#
# BENEFIT, on 470 questions written by people who have never seen this engine
# (LongMemEval, run at each k rather than derived):
#
#     k     4    8   12   16   24
#     hit 304  359  382  399  413
#
# 16 was not where the curve stops -- +14 probes sit between 16 and 24. The
# earlier reading rested on 16 paraphrase probes; this rests on 470.
#
# COST, the part the old note was protecting and the part that had never been
# measured behaviourally: the worry is dilution, since rows ranked 17-24 are
# mostly noise by construction. Measured with the behavioural benchmark
# (9 cases, 2 repeats, both retrieval modes, real character calls):
#
#                    passed      accuracy  grounded  historical hits
#     k=16 lexical    8/18         0.444     0.778        12/16
#     k=16 semantic  10/18         0.556     0.944        12/16
#     k=24 lexical   12/18         0.667     0.889        14/16
#     k=24 semantic  12/18         0.667     0.889        14/16
#
# Better in both modes on four measures including the deterministic one. The
# dilution did not happen. Read with the instrument's own caution: 18 cases
# cannot separate an arm from its noise, and noise is exactly what a single
# improving metric would be -- four moving together in two independent modes
# is what makes this worth acting on.
#
# The payload growth is also smaller than the arithmetic suggests, because
# `build_character_memory_context` drops rows already in the recent buffer:
# measured on chat 63, k=24 returned 25 rows from the seam and delivered 16 to
# the payload, the rest being things the character already had in front of it.
# The cost self-limits.
#
# And the owner accepted the token cost explicitly when shown it, which is the
# half of this decision that was never mine to make.
_RECALL_LIMIT = 24

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
    # Once per row, not three times (sort key, filter, bonus loop) -- linear
    # waste flagged by the audit (docs/experiments/AUDIT_MEMORY.md 1.6).
    exact_scores = {mid: _exact_cue_score(mem, query_text)
                    for mid, mem in memories.items()}
    # Capped at 60 like its sibling rankings: this list is the
    # highest-weighted of the four, and it was the only uncapped one, so on a
    # bank where the exact signal fires wide (measured 71% of one live bank,
    # audit 1.3) it alone handed an RRF contribution to every firing row.
    # Measured on the frozen probe sets: the cap alone flipped two held-out
    # probes to HIT and regressed nothing (10/14 -> 12/14, tuned 24/26
    # unchanged).
    #
    # Ties are the COMMON case here (the score has three flat tiers), and
    # they fall to dict insertion order -- the seam's oldest-first SQL. Two
    # deliberate tie-breaks were tried against the frozen probe sets and BOTH
    # rejected: importance-first regressed both banks (tuned 24 -> 23,
    # held-out 10 -> 9; importance concentrates on the same early-era seed
    # rows whose junk cues fire this signal), and newest-first swung the two
    # banks in OPPOSITE directions by three probes each (tuned 24 -> 21,
    # held-out 10 -> 13) -- a lottery, not a rule. While the score has three
    # flat tiers and junk cue material makes ties bank-wide, every tie order
    # is arbitrary; the disease is the tie mass, and the cue-material fixes
    # are what shrink it. Revisit only if a tie-break can be measured as a
    # win on BOTH banks.
    # Only phrase-tier fires enter the exact LIST: a distinctive stored
    # phrase literally present in the query (1.0), or the whole query inside
    # a stored phrase (0.8 -- a short deliberate query contained in a stored
    # quote, which only a directed query can produce and only a distinctive
    # phrase can absorb). Entity and location fires keep the small scalar
    # bonus below but not the 1.25-weight rank list: a production query is
    # the beat's whole view, which contains the cast's names by construction,
    # so an entity fire is near-bank-wide (the audit's measured 71%) and rank
    # inside the list falls to tie order. Generic-tier fires (a frequency
    # bigram coinciding with query words) stay out for the same reason from
    # the other side: word overlap is the lexical leg's job, weighed by BM25
    # instead of flat. Admitting the 0.8 tier was a stated decision after
    # adversarial review (an earlier filter silently dropped it); measured as
    # a no-op on the frozen probe sets, whose queries are too long to fit
    # inside a stored phrase.
    exact_rank = [mid for mid in sorted(
        memories, key=lambda x: exact_scores[x], reverse=True)
        if exact_scores[mid] >= 0.8][:60]
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
        fused[mid] += 0.08 * exact_scores[mid]
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

# ---- Recall confidence (the "nothing convincing" floor) ----
#
# Retrieval always returns k rows, however weak the best of them is -- so a
# character asked about something that never happened receives sixteen
# nearest misses and nothing that says "your memory holds no answer here".
# For a mind, confabulated recall is a character break; the missing signal is
# an ABSTENTION floor (docs/experiments/AUDIT_MEMORY.md 4.3 item 3).
#
# Not a cosine threshold. Every prose vector scores every bank somewhere in a
# compressed band whose position depends on the embedding model, so an
# absolute floor drops everything or nothing the day the model changes
# (measured for summary windows, MEMORY.md 8, and the reasoning holds here).
# The standard IR answer is query-performance prediction (NQC/WIG, Zhou &
# Croft): read the score DISTRIBUTION -- how far the top-k mean sits above
# the bank-wide mean, in units of the bank's own standard deviation. That is
# per-query self-calibrating, and cheap for the same reason the engine has no
# ANN index: a bank is scanned exhaustively anyway. HONESTY NOTE: the current
# implementation is a SECOND row fetch and 2-cosines-per-row pass per beat,
# not literally the same scan -- folding it into search_memories' own loop is
# the free form and remains unbuilt; at measured bank sizes the second pass
# is milliseconds beside the model call.

# Below this many comparable rows the distribution is not a baseline, and a
# bank mid-rebuild (low model coverage) must never read as empty -- the same
# fail-open posture as the contrast gate's coverage rule.
_RECALL_CONFIDENCE_MIN_BANK = 40
_RECALL_CONFIDENCE_COVERAGE = 0.5

# Calibrated on the frozen probe sets (tools/memory_probes/) against BOTH
# measured corpus states -- the 2026-08-19 stock as-is and the same stock
# after repair_memory_cues -- because a threshold true of only one of them
# would flag real recall the day the other is live: at 1.8, one genuine hit
# on the unrepaired stock abstained (lift 1.724). Below every positive-probe
# hit ever measured (minimum 1.724, and the thinness of that margin is a
# property of the signal, stated rather than hidden), so measured
# false-abstention is 0/37 in both states -- a floor that suppresses real
# recall is worse than no floor. What the margin buys is deliberately
# modest: 0-1 of 15 negative probes abstain (none at all on the unrepaired
# stock). The rest are negatives whose
# TOPIC genuinely resonates in the bank (an event that was discussed but
# never happened); a score distribution cannot tell topical resonance from
# answer presence, and no estimator tried (top-1/top-4/top-16 lift, NQC,
# top-gap) separated them at zero false abstention on both banks. Full
# table in docs/experiments/MEMORY_IMPROVEMENTS.md; sharper teeth would
# need row-level evidence (the audit's cross-encoder note), not a better
# threshold.
# How many of the best scores define the PEAK the lift is measured against.
#
# This used to read `_RECALL_LIMIT`, which was never a decision -- it inherited
# a number chosen for a different question. "How many rows does a character
# receive" and "how many top scores describe the shape of this bank's response"
# are unrelated, and coupling them meant the abstention threshold silently
# recalibrated whenever the payload size moved. Raising the payload to 24
# lowered every lift (a wider top pulls in more mediocre scores), and a
# genuinely strong match measured 1.2428 against a threshold of 1.7 -- so the
# floor would have begun refusing real recall, which is strictly worse than
# the inert-but-harmless state UNBUILT 1.76 records it in.
#
# Pinned at 16 to hold the calibration the threshold was measured on. It is
# not a claim that 16 is right for this statistic; it is a refusal to change
# two things at once.
_RECALL_CONFIDENCE_TOPK = 16

_RECALL_ABSTAIN_LIFT = 1.7


def recall_confidence(chat_id, char_id, query, *, current_turn_idx,
                      viewer_frame_id=_UNSET, k=None, embedded=None,
                      include_archived=True):
    """How convinced retrieval is that this bank speaks to this query.

    Deterministic, no model call beyond the query embedding the caller
    usually already paid for (pass `embedded` to reuse it). Reads the same
    seam-filtered rows `search_memories` ranks -- same turn cutoff, same
    frame rule -- and never widens them.

    Returns a dict:
      available    -- False when the bank is too small, model coverage is
                      too low, or the distribution is degenerate; callers
                      must treat that as "no signal", never as emptiness.
      lift_sigma   -- (mean of top-k best-vector scores - bank mean) / bank
                      standard deviation.
      abstain      -- lift_sigma below _RECALL_ABSTAIN_LIFT.
    """
    rows = visible_memory_rows(
        chat_id, char_id,
        before_turn_idx=current_turn_idx,
        viewer_frame_id=viewer_frame_id,
        include_archived=include_archived,
    )
    out = {"available": False, "lift_sigma": None, "abstain": False,
           "bank": len(rows), "comparable": 0}
    if len(rows) < _RECALL_CONFIDENCE_MIN_BANK:
        return out
    query_text = str(query or "").strip()
    if embedded is None or not getattr(embedded, "vectors", None):
        embedded = embed_texts_meta([query_text or "memory"])
    if embedded.fallback:
        # A hash vector's geometry says nothing about the bank; no signal.
        return out
    qv = embedded.vectors[0]
    best = []
    for row in rows:
        if row["embedding_model"] != embedded.model_key \
                or row["embedding_dim"] != embedded.dimensions:
            continue
        sem = _cos(qv, _vec(row["embedding"]))
        cue = _cos(qv, _vec(row["cue_embedding"]))
        best.append(max(sem, cue))
    out["comparable"] = len(best)
    if len(best) < _RECALL_CONFIDENCE_MIN_BANK \
            or len(best) < _RECALL_CONFIDENCE_COVERAGE * len(rows):
        return out
    import numpy as _np
    arr = _np.asarray(best, dtype=_np.float64)
    sigma = float(arr.std())
    if sigma <= 1e-9:
        return out
    top = _np.sort(arr)[-int(k or _RECALL_CONFIDENCE_TOPK):]
    lift = (float(top.mean()) - float(arr.mean())) / sigma
    out["available"] = True
    out["lift_sigma"] = round(lift, 4)
    out["abstain"] = lift < _RECALL_ABSTAIN_LIFT
    return out


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

