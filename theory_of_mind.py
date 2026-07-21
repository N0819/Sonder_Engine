# theory_of_mind.py
"""Character theory-of-mind belief revision.

Character agents emit hypotheses about other entities ("mind model
updates"): what they observed, what someone said, what they think someone
feels, wants, or is. This module owns how those hypotheses persist and
change over time, independent of the LLM orchestration in agents/.

The model draws on a handful of well-established findings about how real
minds revise beliefs about other people, rather than treating every claim
as either permanent truth or an isolated data point:

- Belief perseverance / primacy in person perception (Ross, Lepper &
  Hubbard 1975; Asch 1946): first impressions of stable character (trait,
  identity) are disproportionately sticky and resist single-instance
  revision.
- Affect as a transient, appraisal-linked state: emotional reads are
  volatile and go stale quickly once the eliciting moment passes.
- Source-monitoring for direct testimony: something a character was
  directly told is strong, fast-updating evidence.
- Ebbinghaus-style forgetting: unreinforced beliefs fade over time rather
  than sitting at peak confidence forever.
- "Explaining away": a strong competing claim weakens a prior belief
  without erasing it outright — real belief revision usually needs
  repeated disconfirmation, not one data point.

Every function here is pure (no DB/network access) so it can be unit
tested in isolation and imported by both commit.py (the persistence
boundary) and agents/common.py (the LLM-facing payload builder) without
creating an import cycle.
"""

from __future__ import annotations

import re

# ---- Per-kind parameters ----
#
# confidence cap: the ceiling a single claim of this kind may ever reach
#   (already existed as _TOM_CONFIDENCE_CAPS before this module).
# plasticity: how much one new consistent data point moves the belief on
#   reinforcement, and how strongly a competing claim can suppress it.
# half_life: turns until an unreinforced belief's confidence decays by
#   half. Deliberately not just the inverse of plasticity — "how fast a
#   belief updates" and "how fast it fades from disuse" are dissociable.

_DEFAULT_KIND = "goal"

_TOM_CONFIDENCE_CAPS = {
    "observation": 1.0, "stated_fact": 0.9, "emotion": 0.8,
    "goal": 0.65, "trait": 0.45, "identity": 0.35, "second_order": 0.5,
}

_TOM_PLASTICITY = {
    "observation": 0.75,
    "stated_fact": 0.85,
    "emotion": 0.7,
    "goal": 0.5,
    "second_order": 0.35,
    "trait": 0.25,
    "identity": 0.2,
}

_TOM_HALF_LIFE = {
    "observation": 5,
    "stated_fact": 18,
    "emotion": 6,
    "goal": 45,
    "second_order": 75,
    "trait": 400,
    "identity": 400,
}

_SIMILARITY_THRESHOLD = 0.4
_MAX_SUPPRESSION = 0.6

_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "seems", "seem", "appears", "appear", "of", "to", "about", "that",
    "this", "these", "those", "they", "them", "their", "he", "she", "him",
    "her", "his", "hers", "it", "its", "and", "or", "but", "with", "for",
    "on", "in", "at", "as", "has", "have", "had", "will", "would", "may",
    "might", "can", "could", "from", "by", "so", "not", "than", "then",
    "into", "up", "out", "if", "no", "there", "around", "near", "toward",
    "when", "while", "very", "just", "still",
}

def _clamp01(value, fallback=0.5):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return fallback
    return max(0.0, min(1.0, v))

def _kind_or_default(kind):
    kind = str(kind or _DEFAULT_KIND)
    return kind if kind in _TOM_CONFIDENCE_CAPS else _DEFAULT_KIND

def cap_mind_model_updates(updates):
    """Clamp each update's confidence to its kind's epistemic ceiling."""
    result = []
    for raw in updates or []:
        update = dict(raw)
        # Route an off-enum kind ("suspicion", ...) through the same mapping
        # apply_mind_model_updates uses, so a hypothesis is capped under the
        # SAME kind it will later be merged/blended under -- previously it was
        # capped at the 0.5 default on emission but treated as _DEFAULT_KIND
        # thereafter, an inconsistent ceiling.
        kind = _kind_or_default(update.get("kind"))
        cap = _TOM_CONFIDENCE_CAPS[kind]
        confidence = _clamp01(update.get("confidence", 0.5))
        update["confidence"] = max(0.0, min(cap, confidence))
        result.append(update)
    return result

def decayed_confidence(confidence, kind, turns_elapsed):
    """Exponential (Ebbinghaus-style) decay of an unreinforced belief."""
    conf = _clamp01(confidence, fallback=0.0)
    elapsed = max(0, int(turns_elapsed or 0))
    if elapsed == 0 or conf <= 0.0:
        return conf
    half_life = _TOM_HALF_LIFE.get(_kind_or_default(kind), _TOM_HALF_LIFE[_DEFAULT_KIND])
    return conf * (0.5 ** (elapsed / half_life))

def _tokens(text):
    words = re.findall(r"[a-z0-9']+", str(text or "").casefold())
    filtered = [w for w in words if w not in _STOPWORDS]
    return set(filtered) if filtered else set(words)

def claim_similarity(a, b):
    """How likely two claims describe the same underlying belief.

    Uses stopword-stripped token overlap coefficient rather than raw
    Jaccard, plus a subset short-circuit, so a terse restatement of a
    longer claim ("is hiding something" vs. "seems to be hiding something
    about the letter") is recognized as the same belief rather than a
    competing one. No embeddings/LLM calls -- this runs once per incoming
    update against a small in-memory list, deterministically and for
    free. It will occasionally misclassify very short, same-vocabulary
    claims; that's an accepted tradeoff (see module docstring/plan) since
    reinforcement blends rather than overwrites and suppression is
    partial, so an occasional misread self-corrects over a few turns
    rather than permanently distorting a belief.
    """
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 1.0 if ta == tb else 0.0
    if ta <= tb or tb <= ta:
        return 1.0
    overlap = len(ta & tb)
    return overlap / min(len(ta), len(tb))

def _elapsed(hypothesis, turn_idx):
    last = hypothesis.get("last_updated_turn", turn_idx)
    try:
        last = int(last)
    except (TypeError, ValueError):
        last = turn_idx
    return max(0, int(turn_idx) - last)

def _live_confidence(hypothesis, turn_idx):
    kind = _kind_or_default(hypothesis.get("kind"))
    return decayed_confidence(
        hypothesis.get("confidence", 0.0), kind, _elapsed(hypothesis, turn_idx))

def apply_mind_model_updates(state, updates, turn_idx, floor=0.05, max_per_entity=30):
    """Merge this turn's mind-model updates into persistent character state.

    Replaces the old exact-text-keyed max()-only accumulation. A claim
    that matches an existing hypothesis for the same (about_entity, kind)
    reinforces it via a convex blend toward the new evidence (scaled by
    the kind's plasticity) rather than jumping straight to the higher
    value. A claim that doesn't match is treated as a competing
    hypothesis: it's kept alongside the others, and it partially
    suppresses ("explains away") its same-group siblings rather than
    erasing them. Every hypothesis's confidence is decay-adjusted for
    elapsed turns before being used or displayed, and hypotheses (or
    whole entities) that decay below `floor` are pruned, which is what
    keeps long campaigns from accumulating an unbounded number of tracked
    entities.
    """
    models = state.setdefault("mind_models", {})

    for update in updates or []:
        if not isinstance(update, dict):
            continue
        about = str(update.get("about_entity") or "unknown").strip() or "unknown"
        claim = str(update.get("claim") or "").strip()
        if not claim:
            continue
        kind = _kind_or_default(update.get("kind"))
        evidence_confidence = _clamp01(update.get("confidence", 0.5))
        cap = _TOM_CONFIDENCE_CAPS.get(kind, 1.0)
        plasticity = _TOM_PLASTICITY.get(kind, _TOM_PLASTICITY[_DEFAULT_KIND])

        model = models.setdefault(about, {"hypotheses": []})
        hyps = model.setdefault("hypotheses", [])
        group = [i for i, h in enumerate(hyps)
                 if isinstance(h, dict) and _kind_or_default(h.get("kind")) == kind]

        best_idx, best_sim = None, 0.0
        for i in group:
            sim = claim_similarity(claim, str(hyps[i].get("claim") or ""))
            if sim > best_sim:
                best_sim, best_idx = sim, i

        if best_idx is not None and best_sim >= _SIMILARITY_THRESHOLD:
            existing = hyps[best_idx]
            decayed_old = _live_confidence(existing, turn_idx)
            new_conf = decayed_old + (evidence_confidence - decayed_old) * plasticity
            merged = dict(update)
            merged["about_entity"] = about
            merged["kind"] = kind
            merged["claim"] = claim
            merged["confidence"] = max(0.0, min(cap, new_conf))
            merged["last_updated_turn"] = turn_idx
            hyps[best_idx] = merged
        else:
            new_hyp = dict(update)
            new_hyp["about_entity"] = about
            new_hyp["kind"] = kind
            new_hyp["claim"] = claim
            new_hyp["confidence"] = max(0.0, min(cap, evidence_confidence))
            new_hyp["last_updated_turn"] = turn_idx
            hyps.append(new_hyp)

            suppression = min(_MAX_SUPPRESSION, plasticity * evidence_confidence)
            for i in group:
                sib = hyps[i]
                sib["confidence"] = max(0.0, _live_confidence(sib, turn_idx) * (1 - suppression))
                sib["last_updated_turn"] = turn_idx

        model["last_updated_turn"] = turn_idx

    # Sweep every tracked entity (not just ones mentioned this turn) so
    # beliefs about people who've dropped out of the story actually fade
    # from storage instead of accumulating forever.
    for about in list(models.keys()):
        model = models.get(about) or {}
        hyps = model.get("hypotheses") or []
        scored = []
        for h in hyps:
            if not isinstance(h, dict):
                continue
            live_conf = _live_confidence(h, turn_idx)
            if live_conf >= floor:
                scored.append((live_conf, h))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        survivors = [h for _, h in scored[:max_per_entity]]
        if survivors:
            model["hypotheses"] = survivors
            models[about] = model
        else:
            models.pop(about, None)

    return state

def mind_models_for_payload(mind_models, turn_idx, max_competitors=2):
    """Build the character-turn view: leading belief + live competitors.

    Applies decay for display without mutating storage, and groups by
    (about_entity, kind) so the character can see it's still weighing,
    say, two theories about someone's goal -- real metacognitive
    awareness of open questions, rather than a flat, unfiltered dump of
    every hypothesis ever formed.
    """
    out = {}
    for about, model in (mind_models or {}).items():
        hyps = (model or {}).get("hypotheses") or []
        by_kind = {}
        for h in hyps:
            if not isinstance(h, dict):
                continue
            kind = _kind_or_default(h.get("kind"))
            by_kind.setdefault(kind, []).append({
                "claim": h.get("claim", ""),
                "confidence": round(_live_confidence(h, turn_idx), 3),
            })
        kinds_out = {}
        for kind, entries in by_kind.items():
            entries.sort(key=lambda e: e["confidence"], reverse=True)
            kinds_out[kind] = {
                "leading": entries[0],
                "competitors": entries[1:1 + max_competitors],
            }
        if kinds_out:
            out[about] = kinds_out
    return out
