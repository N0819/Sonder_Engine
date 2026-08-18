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

def cap_mind_model_updates(updates, absorption=0.0):
    """Clamp each update's confidence to its kind's epistemic ceiling, lowered
    for the effortful kinds by how much of the mind the body currently has
    (see absorbed_cap)."""
    result = []
    for raw in updates or []:
        update = dict(raw)
        # Route an off-enum kind ("suspicion", ...) through the same mapping
        # apply_mind_model_updates uses, so a hypothesis is capped under the
        # SAME kind it will later be merged/blended under -- previously it was
        # capped at the 0.5 default on emission but treated as _DEFAULT_KIND
        # thereafter, an inconsistent ceiling.
        kind = effective_kind(update.get("kind"), update.get("claim"))
        update["kind"] = kind
        cap = absorbed_cap(kind, absorption)
        confidence = _clamp01(update.get("confidence", 0.5))
        update["confidence"] = max(0.0, min(cap, confidence))
        result.append(update)
    return result


# ---- F8: the declared `kind` is not taken on trust ----
#
# Every ceiling in this module keys off a `kind` the MODEL declares, and nothing
# checked it. The failure is not hypothetical or adversarial -- it is just the
# path of least resistance: a model that wants to be confident about "Vorne is
# the sort who sells people out" declares it `observation` (cap 1.0) instead of
# `trait` (cap 0.45), and the whole epistemic gradient, including the absorption
# erosion built on top of it, quietly stops applying.
#
# So the claim's own language votes too, and the STRICTER of the two wins. This
# is text matching, and text matching is not something to build an information
# boundary on -- but this is not an information boundary. It is confidence
# calibration, and it is deliberately arranged so a misfire can only ever make a
# character less sure than they might be, never more. Under-confidence is a
# degradation; over-confidence is the belief layer laundering a guess into a
# fact, and those are not equally bad.
#
# Ordered: the first pattern to match wins, so more specific readings are tested
# before the general ones ("thinks I want the letter" is second-order, not goal).
_KIND_CUES = (
    ("second_order", (
        r"\bthinks (?:that )?(?:i|we|he|she|they)\b",
        r"\bbelieves (?:that )?(?:i|we|he|she|they)\b",
        r"\b(?:knows|suspects|assumes|reckons) (?:that )?(?:i|we)\b",
        r"\bthinks .{0,24}\bbelieves\b",
    )),
    ("stated_fact", (
        r"\b(?:said|told|claimed|admitted|swore|promised|announced)\b",
    )),
    ("identity", (
        r"\bis really\b", r"\bis actually\b", r"\bmust be the\b",
        r"\bis the one who\b", r"\bgoes by\b",
    )),
    ("trait", (
        r"\bis (?:a|an) \w+", r"\balways\b", r"\bnever\b",
        r"\b(?:kind|sort|type) of person\b", r"\bby nature\b",
    )),
    ("goal", (
        r"\bwants?\b", r"\bintends?\b", r"\bplans? to\b",
        r"\btrying to\b", r"\bmeans to\b", r"\bhopes? to\b",
        r"\baims? to\b", r"\bis going to\b", r"\bafter the\b",
    )),
    ("emotion", (
        r"\bfeels?\b", r"\bis (?:afraid|angry|frightened|upset|nervous|"
        r"happy|sad|ashamed|jealous|calm)\b",
    )),
)


def _inferred_kind(claim):
    """The kind the claim's own language suggests, or None if it says nothing."""
    low = str(claim or "").casefold()
    if not low.strip():
        return None
    for kind, cues in _KIND_CUES:
        if any(re.search(cue, low) for cue in cues):
            return kind
    return None


def effective_kind(declared, claim):
    """The kind to actually cap and group this claim under.

    Whichever of the declared and the inferred kind carries the LOWER ceiling.
    A model cannot buy confidence by mislabelling, and a wrong inference can
    only cost confidence, never grant it.
    """
    declared_kind = _kind_or_default(declared)
    inferred = _inferred_kind(claim)
    if inferred is None:
        return declared_kind
    if _TOM_CONFIDENCE_CAPS[inferred] < _TOM_CONFIDENCE_CAPS[declared_kind]:
        return inferred
    return declared_kind


def decayed_confidence(confidence, kind, turns_elapsed):
    """Exponential (Ebbinghaus-style) decay of an unreinforced belief."""
    conf = _clamp01(confidence, fallback=0.0)
    try:
        elapsed = max(0.0, float(turns_elapsed or 0))
    except (TypeError, ValueError):
        elapsed = 0.0
    if elapsed == 0 or conf <= 0.0:
        return conf
    half_life = _TOM_HALF_LIFE.get(_kind_or_default(kind), _TOM_HALF_LIFE[_DEFAULT_KIND])
    return conf * (0.5 ** (elapsed / half_life))

def _tokens(text):
    words = re.findall(r"[a-z0-9']+", str(text or "").casefold())
    filtered = [w for w in words if w not in _STOPWORDS]
    return set(filtered) if filtered else set(words)

def claim_similarity(a, b, ignore=None):
    """How likely two claims describe the same underlying belief.

    `ignore` is the SUBJECT both claims are about, and its tokens are removed
    from both sides before comparing. Naming the subject inside the claim is
    ordinary phrasing, but it inflated every same-subject pair toward a match:
    "Chamber 0505 has a toppled bench" and "Chamber 0505 is empty and swept"
    scored as the same belief on the strength of "chamber" and "0505" alone, so
    two distinct facts about one room merged into one and the second silently
    overwrote the first. The same held for people -- "Vorne is afraid" and
    "Vorne wants to leave" shared "vorne". What a claim is ABOUT is already
    carried by about_entity; only what it SAYS should decide sameness.

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
    if ignore:
        drop = _tokens(ignore)
        ta, tb = (ta - drop) or ta, (tb - drop) or tb
    if not ta or not tb:
        return 1.0 if ta == tb else 0.0
    if ta <= tb or tb <= ta:
        return 1.0
    overlap = len(ta & tb)
    return overlap / min(len(ta), len(tb))

def _same_belief(hyps, indices, claim, about):
    """Which of `indices` names the hypothesis that IS `claim`, or None.

    The only place that answers "are these two the same belief". It used to be
    answered twice -- once by the merge and once by `belief_credence` -- and
    the two copies drifted: the merge learned to drop the subject's own tokens
    before comparing (see `claim_similarity`) and the credence read did not, so
    a claim the merge had deliberately kept as a SEPARATE hypothesis could
    still take its confidence from the hypothesis it had been kept apart from.
    Two rules for one question is the defect; one function is the fix.

    `indices` is the caller's scope -- the merge passes the same-kind group,
    because a new claim only competes with (and only reinforces) its own kind;
    a reader with no declared kind passes them all.
    """
    best_idx, best_sim = None, 0.0
    for i in indices:
        hyp = hyps[i]
        if not isinstance(hyp, dict):
            continue
        sim = claim_similarity(claim, str(hyp.get("claim") or ""), ignore=about)
        if sim > best_sim:
            best_sim, best_idx = sim, i
    if best_idx is None or best_sim < _SIMILARITY_THRESHOLD:
        return None
    return best_idx


def _elapsed(hypothesis, turn_idx, elapsed_seconds=None):
    if elapsed_seconds is not None and hypothesis.get("last_updated_seconds") is not None:
        try:
            delta = float(elapsed_seconds) - float(hypothesis["last_updated_seconds"])
        except (TypeError, ValueError):
            delta = 0.0
        if delta > 0.0:
            return delta / 60.0
    last = hypothesis.get("last_updated_turn", turn_idx)
    try:
        last = int(last)
    except (TypeError, ValueError):
        last = turn_idx
    return max(0, int(turn_idx) - last)

def _live_confidence(hypothesis, turn_idx, elapsed_seconds=None):
    kind = _kind_or_default(hypothesis.get("kind"))
    return decayed_confidence(
        hypothesis.get("confidence", 0.0), kind,
        _elapsed(hypothesis, turn_idx, elapsed_seconds))

def rekey_place_claims(updates, place_names, protected=()):
    """Re-key a claim ABOUT A PLACE onto that place, so places stop competing.

    Hypotheses are grouped by (about_entity, kind), and within a group a new
    claim partially explains away its siblings -- which is right for a mind,
    where rival theories about one person genuinely should suppress each other,
    and exactly backwards for space. Observed live: a character mapping a maze
    filed every room under one umbrella entity ("maze layout in this sector"),
    so learning Chamber 0805 actively suppressed what it knew about Chamber
    0505 -- two independent facts treated as rival explanations of one subject.
    Confidences sat at 0.68 and 0.28 for rooms that had nothing to do with
    each other, and the map dismantled itself as fast as it was built.

    Re-keying to the specific place preserves BOTH behaviours: competing claims
    about the SAME room still revise each other normally (a place can turn out
    to be different from what you thought), while claims about DIFFERENT rooms
    stop colliding.

    `protected` names are never re-keyed -- a claim about a PERSON stays about
    that person even when it mentions where they were standing. Only a claim
    naming exactly one place is moved; naming two is ambiguous, and guessing
    would scatter a belief onto the wrong room.
    """
    protected_cf = {str(p).strip().casefold() for p in (protected or ()) if str(p).strip()}
    # Longest first: "Chamber 05" must not shadow "Chamber 0505".
    names = sorted(
        {str(n).strip() for n in (place_names or ()) if str(n).strip()},
        key=len, reverse=True)
    if not names:
        return updates
    out = []
    for raw in updates or []:
        if not isinstance(raw, dict):
            continue
        update = dict(raw)
        about = str(update.get("about_entity") or "").strip()
        if about.casefold() in protected_cf:
            out.append(update)
            continue
        haystack = f"{about} {update.get('claim') or ''}"
        hits = [n for n in names
                if re.search(rf"\b{re.escape(n)}\b", haystack, re.I)]
        # Substring shadowing already handled by longest-first; collapse names
        # that are prefixes of an earlier hit.
        distinct = [n for n in hits
                    if not any(n != o and n.casefold() in o.casefold() for o in hits)]
        if len(distinct) == 1:
            update["about_entity"] = distinct[0]
        out.append(update)
    return out


def apply_mind_model_updates(state, updates, turn_idx, floor=0.05,
                             max_per_entity=30, elapsed_seconds=None,
                             absorption=0.0):
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
        kind = effective_kind(update.get("kind"), claim)
        evidence_confidence = _clamp01(update.get("confidence", 0.5))
        # Two ceilings, because two different operations. Recognising more of
        # what you already think is AUTOMATIC and survives absorption; building
        # a theory about someone is CONTROLLED and does not. Applying the
        # eroded cap to both made a beat that CONFIRMED a settled belief cut it
        # from 0.6 to 0.37 -- absorption eating convictions it should only have
        # stopped you adding to.
        formation_cap = absorbed_cap(kind, absorption)
        reinforce_cap = _TOM_CONFIDENCE_CAPS.get(kind, 1.0)
        plasticity = _TOM_PLASTICITY.get(kind, _TOM_PLASTICITY[_DEFAULT_KIND])

        model = models.setdefault(about, {"hypotheses": []})
        hyps = model.setdefault("hypotheses", [])
        group = [i for i, h in enumerate(hyps)
                 if isinstance(h, dict) and _kind_or_default(h.get("kind")) == kind]

        best_idx = _same_belief(hyps, group, claim, about)

        if best_idx is not None:
            existing = hyps[best_idx]
            decayed_old = _live_confidence(existing, turn_idx, elapsed_seconds)
            # A belief reached while the body had the mind, revisited now that
            # it does not, moves further on the same evidence than a belief
            # formed clear-headed would. Without this, `formed_under` was a
            # label the payload mentioned and nothing acted on -- the whole
            # re-evaluation rested on the model choosing to comply, which is
            # the kind of guarantee this engine does not accept anywhere else.
            effective_plasticity = plasticity
            if due_for_reappraisal(existing, absorption):
                effective_plasticity = min(
                    _REAPPRAISAL_PLASTICITY_CEILING,
                    plasticity * _REAPPRAISAL_PLASTICITY_BOOST)
            new_conf = (
                decayed_old
                + (evidence_confidence - decayed_old) * effective_plasticity)
            merged = dict(update)
            merged["about_entity"] = about
            merged["kind"] = kind
            merged["claim"] = claim
            # Provenance belongs to the BELIEF, not to the update that last
            # touched it. `merged` is built from the incoming update, so
            # without this every reinforcement silently dropped these -- a
            # belief reached in agony and merely restated became one that had
            # always been held calmly, and could never come up for review.
            for carried in ("first_seen_turn", "formed_under",
                            "reappraised_turn"):
                if carried in existing and carried not in update:
                    merged[carried] = existing[carried]
            merged["confidence"] = max(
                0.0, min(max(reinforce_cap, decayed_old), new_conf))
            merged["last_updated_turn"] = turn_idx
            if effective_plasticity != plasticity:
                # Reviewed with a clear head: it is now a belief they hold,
                # not one they arrived at in extremity, so it stops being
                # re-flagged every calm beat thereafter.
                merged.pop("formed_under", None)
                merged["reappraised_turn"] = turn_idx
            if elapsed_seconds is not None:
                merged["last_updated_seconds"] = float(elapsed_seconds)
            hyps[best_idx] = merged
        else:
            # Forming a belief about someone for the FIRST time is the
            # expensive operation -- reinforcing one you already hold is
            # nearly free -- so absorption gates formation, not reinforcement.
            # A body that has most of the mind does not stop the character
            # noticing; it stops them starting a new theory about anyone.
            if evidence_confidence < formation_floor(absorption):
                continue
            new_hyp = dict(update)
            new_hyp["about_entity"] = about
            new_hyp["kind"] = kind
            new_hyp["claim"] = claim
            new_hyp["confidence"] = max(
                0.0, min(formation_cap, evidence_confidence))
            new_hyp["last_updated_turn"] = turn_idx
            new_hyp["first_seen_turn"] = turn_idx
            if absorption > 0.0:
                # Stamped rather than merely capped, so the belief can come
                # back up for review once there is room to review it, instead
                # of standing as though it were reached calmly OR being
                # discounted forever. See due_for_reappraisal.
                new_hyp["formed_under"] = {
                    "absorption": round(_clamp01(absorption, 0.0), 3),
                    "turn": turn_idx,
                }
            if elapsed_seconds is not None:
                new_hyp["last_updated_seconds"] = float(elapsed_seconds)
            hyps.append(new_hyp)

            suppression = min(_MAX_SUPPRESSION, plasticity * evidence_confidence)
            for i in group:
                sib = hyps[i]
                sib["confidence"] = max(
                    0.0,
                    _live_confidence(sib, turn_idx, elapsed_seconds)
                    * (1 - suppression),
                )
                sib["last_updated_turn"] = turn_idx
                if elapsed_seconds is not None:
                    sib["last_updated_seconds"] = float(elapsed_seconds)

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
            live_conf = _live_confidence(h, turn_idx, elapsed_seconds)
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

def mind_models_for_payload(mind_models, turn_idx, max_competitors=2,
                            elapsed_seconds=None):
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
                "confidence": round(
                    _live_confidence(h, turn_idx, elapsed_seconds), 3),
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


def belief_credence(state, about_entity, claim, turn_idx, elapsed_seconds=None):
    """This character's CURRENT live credence in `claim` about `about_entity`,
    or None when no surviving hypothesis expresses it.

    apply_mind_model_updates already does the hard part -- it similarity-matches
    a new claim against its same-kind siblings, blends toward it by the kind's
    plasticity, explains away the competitors it displaces, decays the
    unreinforced, and prunes below the floor. That reconciliation lives entirely
    in mind_models, though, so nothing downstream could ask what the character
    believes NOW about a claim they made earlier. This is that question.

    Returns the decay-adjusted confidence of the best-matching hypothesis above
    _SIMILARITY_THRESHOLD -- literally the same matcher the merge itself calls
    (`_same_belief`), so a memory and a hypothesis are judged "the same belief"
    by one rule rather than by two that can drift apart. They did drift: this
    read once compared claims without dropping the subject's own tokens, and
    answered from hypotheses the merge had refused to fold.
    """
    models = (state or {}).get("mind_models")
    if not isinstance(models, dict):
        return None
    about = str(about_entity or "").strip()
    model = models.get(about)
    if not isinstance(model, dict):
        return None
    hyps = model.get("hypotheses") or []
    # Every kind, deliberately: the question arrives as a bare claim -- an
    # inference memory's gist, a mirrored affordance -- with no declared kind
    # to scope by, and a character who credits "Vorne is frightened" as an
    # emotion credits it however the claim was filed. Guessing a kind here to
    # narrow the scan would make a mind credit less than its own evidence
    # supports; the SUBJECT drop is what keeps the match honest.
    best_idx = _same_belief(hyps, range(len(hyps)), claim, about)
    if best_idx is None:
        return None
    return _clamp01(_live_confidence(hyps[best_idx], turn_idx, elapsed_seconds),
                    fallback=0.0)


# ---- Absorption: what the body's claim on attention does to cognition ----
#
# psychology_runtime.cognitive_absorption supplies the 0..1 figure (deliberately
# valence-blind -- see its docstring). Everything below takes it as a plain
# float so this module keeps its no-dependency property.

# Kinds whose ceiling absorption lowers, and how far. The existing cap table is
# already an EFFORT gradient -- observation 1.0 down to identity 0.35 is
# essentially "how much slow, deliberate mentalising does this take" -- so
# absorption scales the effortful end and leaves the immediate end alone. A
# character in agony does not get worse at noticing what is in front of them;
# they get worse at modelling why somebody else is doing what they are doing.
# (Easterbrook's cue-utilisation narrowing.)
_ABSORPTION_CAP_EROSION = {
    "observation": 0.0, "stated_fact": 0.05, "emotion": 0.25,
    "goal": 0.45, "second_order": 0.75, "trait": 0.6, "identity": 0.6,
}

# A NEW hypothesis has to clear this before it can be formed at all. Reinforcing
# a belief you already hold is cheap; noticing something about someone for the
# first time is not, and under absorption it is the first one that stops
# happening.
_FORMATION_FLOOR_AT_FULL_ABSORPTION = 0.55

_SHEET_CAPACITY_MAX = 5
_SHEET_CAPACITY_MIN = 1
# An incumbent keeps its slot unless a challenger beats it by this much. Without
# hysteresis the sheet churns every turn as confidences wobble and it stops
# being "what I am actively wondering about" -- which is the whole point of it
# being stable.
_SHEET_INCUMBENT_MARGIN = 0.08


def absorbed_cap(kind, absorption):
    """The confidence ceiling for `kind` at this absorption."""
    base = _TOM_CONFIDENCE_CAPS.get(_kind_or_default(kind), 1.0)
    erosion = _ABSORPTION_CAP_EROSION.get(_kind_or_default(kind), 0.5)
    return max(0.05, base * (1.0 - erosion * _clamp01(absorption, 0.0)))


def formation_floor(absorption):
    """Minimum confidence a NEW hypothesis needs before it can form."""
    return _FORMATION_FLOOR_AT_FULL_ABSORPTION * _clamp01(absorption, 0.0)


def sheet_capacity(absorption):
    """How many hypotheses this mind can actively hold right now.

    The direct, legible form of the narrowing: not "your beliefs are worth
    less" but "you can only keep so much in mind at once." Full absorption
    leaves room for exactly one open question.
    """
    span = _SHEET_CAPACITY_MAX - _SHEET_CAPACITY_MIN
    return int(round(_SHEET_CAPACITY_MAX - span * _clamp01(absorption, 0.0)))


def hypothesis_key(about, kind, claim):
    return f"{str(about).strip()}|{_kind_or_default(kind)}|{str(claim).strip()}"


def select_active_hypotheses(mind_models, previous_keys, capacity, turn_idx,
                             elapsed_seconds=None, absorption=0.0):
    """The stable hypothesis sheet: the few open questions this mind is
    actively holding, each explicitly marked AS a hypothesis.

    Two problems this solves. The payload used to carry every entity's leading
    belief plus competitors with no overall bound, so a character with five
    tracked people saw dozens of claims -- undifferentiated, and nothing in the
    structure said "these are your guesses." A mind reading its own conjecture
    back as settled fact is the same information-layer collapse this engine
    polices between minds, happening inside one.

    Selection is by live confidence, with hysteresis: an incumbent from
    `previous_keys` holds its slot unless a challenger beats it by
    _SHEET_INCUMBENT_MARGIN. Returns (entries, keys).

    `absorption` is the character's CURRENT state, and is what decides whether a
    belief reached under absorption is flagged for reappraisal. Passing 0.0 --
    as this did while hardcoded -- flags every such belief unconditionally,
    including for a character still in the grip of the thing that produced it,
    telling them to reconsider "now that the body does not have your attention"
    while it plainly does.
    """
    previous = set(previous_keys or ())
    scored = []
    for about, model in (mind_models or {}).items():
        for hyp in ((model or {}).get("hypotheses") or []):
            if not isinstance(hyp, dict):
                continue
            claim = str(hyp.get("claim") or "").strip()
            if not claim:
                continue
            kind = _kind_or_default(hyp.get("kind"))
            live = _live_confidence(hyp, turn_idx, elapsed_seconds)
            key = hypothesis_key(about, kind, claim)
            rank = live + (_SHEET_INCUMBENT_MARGIN if key in previous else 0.0)
            scored.append((rank, live, key, about, kind, claim, hyp))
    scored.sort(key=lambda row: (-row[0], row[2]))

    entries, keys = [], []
    for _rank, live, key, about, kind, claim, hyp in scored[:max(0, capacity)]:
        entry = {
            "about": about,
            "kind": kind,
            # Named so the field itself carries the epistemic status: this is
            # something the character GUESSES, and the payload should never let
            # it read as something they know.
            "i_suspect": claim,
            "confidence": round(live, 3),
            "held_since_turn": hyp.get("first_seen_turn", hyp.get("last_updated_turn")),
        }
        formed = hyp.get("formed_under")
        if isinstance(formed, dict):
            entry["formed_under"] = formed
            if due_for_reappraisal(hyp, absorption):
                entry["reappraisal"] = (
                    "formed while the body had most of your attention; "
                    "worth reconsidering now that it does not"
                )
        entries.append(entry)
        keys.append(key)
    return entries, keys


# How much calmer than formation the present has to be before a belief reached
# under absorption becomes eligible for reconsideration.
_REAPPRAISAL_DROP = 0.35

# What reappraisal actually DOES. A belief up for review is more open to being
# moved by the next thing the character learns -- which is what looking at
# something again with a clear head amounts to. Bounded well under 1.0 so
# reappraisal opens a belief up rather than letting one beat overwrite it;
# belief revision still needs repeated evidence, not a single data point.
_REAPPRAISAL_PLASTICITY_BOOST = 1.8
_REAPPRAISAL_PLASTICITY_CEILING = 0.9


def due_for_reappraisal(hypothesis, current_absorption):
    """Was this belief reached while the body had the mind, and is the mind
    free enough now to look at it again?

    The point of stamping `formed_under` rather than just capping: a conclusion
    reached mid-agony should not silently stand as though it were reached
    calmly, and should not be permanently discounted either. It should come
    back up for review once there is room to review it -- which is what real
    minds do in the cold light of day.
    """
    formed = (hypothesis or {}).get("formed_under")
    if not isinstance(formed, dict):
        return False
    then = _clamp01(formed.get("absorption"), 0.0)
    now = _clamp01(current_absorption, 0.0)
    return then >= 0.5 and (then - now) >= _REAPPRAISAL_DROP
