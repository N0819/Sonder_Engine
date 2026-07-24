# affect.py
"""Deterministic floors for character interior state (goals + blended mood).

Character agents emit a proposed interior state each turn: a mood label,
wants, and intention updates. Left unchecked, weak models drift — a
character "cheerfully" watches their plan collapse, sprouts six urgent
wants at once, or abandons a three-turn-old goal with no on-screen cause.
This module owns the deterministic floors that keep the LLM's proposals
honest, independent of the orchestration in agents/ and the persistence
boundary in commit.py.

The model draws on standard appraisal-theory findings rather than trusting
the label the LLM happened to sample:

- OCC-style appraisal (Ortony, Clore & Collins 1988): emotions arise from
  goal-relevant events graded by desirability, certainty, and agency —
  an uncertain threat reads as fear, a certain other-caused loss as anger,
  a certain uncaused loss as sadness.
- Core affect as a valence/arousal plane (Russell 1980): mood is a point
  (V, A), and any label is only a name for a quadrant of that plane, so a
  label can be mechanically checked against the numbers.
- Mood inertia and decay: affect blends toward an appraisal target rather
  than jumping (arousal raises plasticity), and unreinforced affect decays
  exponentially back to the character's baseline — the same convex-blend /
  half-life idioms as theory_of_mind.py.
- Suppression is not deletion: a proposed label that contradicts the
  computed appraisal is kept as the character's self-report, and the
  disagreement is stored as an explicit *undercurrent* the narrator can
  leak through tells instead of through dialogue.

Every function here is pure (no DB/network access) so it can be unit
tested in isolation and imported by both commit.py and agents/common.py
without creating an import cycle. The only local import is
theory_of_mind.claim_similarity, itself pure.
"""

from __future__ import annotations

from theory_of_mind import claim_similarity

# ---- Tunables ----
#
# kv/ka: how strongly a unit of appraisal weight moves valence/arousal.
# certainty threshold: OCC's prospect/confirmed split — below it an
#   outcome is still "in prospect" (fear/hope), above it it is confirmed
#   (anger/sadness/satisfaction).
# inertia step: max per-turn movement of V or A absent a shock, so one
#   beat can't teleport a mood across the plane.
# proposal jump: a model-proposed surface this far (per axis) from the
#   decayed previous mood counts as a shock — the model is deliberately
#   authoring a turn, not drifting, so the inertia clamp lifts.
# half-lives: surface mood fades to baseline slowly; an undercurrent is
#   appraisal-linked and goes stale twice as fast (mirrors the
#   emotion-vs-trait half-life split in theory_of_mind).

_KV = 0.5
_KA = 0.4
_CERTAINTY_THRESHOLD = 0.8
_MAX_STEP = 0.4
_SHOCK_IMPACT = 0.8
_PROPOSAL_SHOCK_JUMP = 0.6
_SURFACE_HALF_LIFE = 8.0
_UNDERCURRENT_HALF_LIFE = 4.0
_UNDERCURRENT_FLOOR = 0.1
_SIGN_EPS = 0.05

_WANT_CAP = 3
_WANT_SIMILARITY = 0.4
_INTENT_CAP = 4
_INTENT_SIMILARITY = 0.4
_INTENT_EVIDENCE_WINDOW = 3
_INTENT_DORMANT_AFTER = 30
_INTENT_PROGRESS_STEP = 0.2
_LEAK_SIMILARITY = 0.5

# ---- Drive-rupture tunables ----
#
# A character's core drive is normally immovable: no single beat may
# rewrite it. Rupture is the earned exception — slow *strain* accrual
# plus one confirmed drive-scale event, inside a rare window.
#
# strain half-life: grievances against the drive fade over arcs, not
#   beats — far slower than surface mood (60 turns vs 8).
# contradiction/relief gains: a fully confirmed catastrophic
#   contradiction (|impact|=1, certainty=1) adds only 0.25 (0.375 when
#   self-caused), so rupture takes several distinct wounds, never one;
#   relief pays strain down slightly faster than contradiction builds
#   it, so a drive that keeps winning stays stable.
# self-agency multipliers: harm your own drive *caused* cuts deeper
#   than harm done to it (strain x1.5) and tips a rupture more easily
#   (event score x1.15).
# suppression drift: enacting against your own drive while the
#   drive-serving want sits suppressed erodes it a little each beat
#   (0.06 -> ~11 beats of pure self-betrayal to reach the strain gate).
# pump damper: a contradiction whose `why` restates a recent strain-log
#   grievance (claim_similarity >= 0.6, window 6) accrues nothing —
#   brooding over one wound cannot pump strain to the threshold.
# rupture gates: BOTH keys must turn — accumulated strain >= 0.65 AND a
#   confirmed drive-scale event >= 0.55 on this beat — and a 40-turn
#   cooldown keeps identity shifts rare even in a stormy story.
# shift-coherence band: a proposed new essence >0.6 similar to the old
#   one is a rephrase (at most a bend), while one <0.2 similar to
#   *everything* (rupture cause, old essence/taboo, former drives) is
#   an unrelated personality transplant; both are refused as breaks.

_STRAIN_HALF_LIFE = 60.0
# Certainty floor for DRIVE-STRAIN accrual and rupture ignition -- lower than
# the mood-appraisal _CERTAINTY_THRESHOLD (0.8) on purpose. A drive rupture is
# the ONE domain where a character is inherently uncertain ("was it a fool's
# errand? ask me when I know"); gating strain behind 0.8 demanded certainty
# ABOUT the self-doubt before letting the self-doubt accumulate, so the more
# authentic (uncertain) the pre-rupture signal, the more the ledger discarded
# it -- observed live: a capable model registered a -0.35 drive contradiction
# at certainty 0.7 and it accrued nothing. The magnitude gates
# (_RUPTURE_STRAIN_MIN, _RUPTURE_EVENT_MIN) still keep ignition earned; only the
# certainty bar moves. The accrual delta already scales by certainty, so a
# less-confident hit contributes proportionally less rather than nothing.
_STRAIN_CERTAINTY_MIN = 0.5
_STRAIN_CONTRADICTION_GAIN = 0.25
_STRAIN_RELIEF_GAIN = 0.30
_STRAIN_SELF_MULT = 1.5
_STRAIN_SUPPRESSION_DRIFT = 0.06
_STRAIN_PUMP_SIMILARITY = 0.6
_STRAIN_PUMP_WINDOW = 6
_RUPTURE_STRAIN_MIN = 0.65
_RUPTURE_EVENT_MIN = 0.55
_RUPTURE_SELF_MULT = 1.15
_RUPTURE_COOLDOWN = 40
_SHIFT_EVIDENCE_SIM = 0.2
_SHIFT_REPHRASE_SIM = 0.6
_SHIFT_RELATED_SIM = 0.2

# Public thresholds, read outside this module so the gates stay defined in
# one place: commit.py keeps an expired rupture window OPEN while strain
# stays >= RUPTURE_STRAIN_MIN (denial is a phase, not an exit), and
# agents/character.py feeds a `crisis` flag into the character payload at
# CRISIS_STRAIN_MIN so the manifest/tells escalate to visible breaking
# even before any drive_shift.
RUPTURE_STRAIN_MIN = _RUPTURE_STRAIN_MIN
CRISIS_STRAIN_MIN = 0.8

# A rupture window that keeps re-extending with no drive_shift used to sit open
# indefinitely (observed live: 23 turns at strain ~1.0, the character neither
# transforming nor recovering -- a permanent crisis limbo). Two floors close it:
#   * RUPTURE_FORCE_AFTER: once the window has been open this many turns,
#     agents/character.py escalates the prompt from an optional "you MAY shift"
#     to a FORCED resolution -- shift now, or reaffirm the old drive in a
#     concrete, page-visible act; passive untouched calm is no longer offered.
#   * RUPTURE_MAX_OPEN: the hard cap -- once the window has been open this long,
#     commit.py force-closes it and pays strain down below the floor, so denial
#     resolves (as reaffirmation) instead of persisting forever.
RUPTURE_FORCE_AFTER = 3
RUPTURE_MAX_OPEN = 6

# ---- Affect lexicon ----
#
# Label -> V/A quadrant *signs* only ({-1, 0, +1}); 0 means the lexicon is
# unopinionated about that axis. Signs are all the reconciliation needs:
# the question is never "how happy is 'cheerful'", only "can 'cheerful'
# coexist with negative valence".

AFFECT_LEXICON = {
    # fear / anxiety
    "fear": {"v": -1, "a": 1}, "afraid": {"v": -1, "a": 1},
    "terrified": {"v": -1, "a": 1}, "panicked": {"v": -1, "a": 1},
    "anxious": {"v": -1, "a": 1}, "nervous": {"v": -1, "a": 1},
    "dread": {"v": -1, "a": 1}, "alarmed": {"v": -1, "a": 1},
    "wary": {"v": -1, "a": 0}, "suspicious": {"v": -1, "a": 0},
    # anger
    "anger": {"v": -1, "a": 1}, "angry": {"v": -1, "a": 1},
    "furious": {"v": -1, "a": 1}, "irritated": {"v": -1, "a": 1},
    "frustrated": {"v": -1, "a": 1}, "resentful": {"v": -1, "a": 0},
    # sadness / grief
    "sadness": {"v": -1, "a": -1}, "sad": {"v": -1, "a": -1},
    "grief": {"v": -1, "a": -1}, "sorrowful": {"v": -1, "a": -1},
    "despairing": {"v": -1, "a": -1}, "melancholy": {"v": -1, "a": -1},
    "lonely": {"v": -1, "a": -1}, "downcast": {"v": -1, "a": -1},
    # disgust / contempt
    "disgusted": {"v": -1, "a": 0}, "contemptuous": {"v": -1, "a": 0},
    # shame / guilt
    "ashamed": {"v": -1, "a": -1}, "guilty": {"v": -1, "a": -1},
    "embarrassed": {"v": -1, "a": 1},
    # joy
    "joyful": {"v": 1, "a": 1}, "happy": {"v": 1, "a": 1},
    "cheerful": {"v": 1, "a": 1}, "excited": {"v": 1, "a": 1},
    "elated": {"v": 1, "a": 1}, "delighted": {"v": 1, "a": 1},
    "amused": {"v": 1, "a": 1},
    # hope
    "hope": {"v": 1, "a": 1}, "hopeful": {"v": 1, "a": 1},
    "eager": {"v": 1, "a": 1}, "curious": {"v": 1, "a": 1},
    # calm / contentment / relief
    "satisfaction": {"v": 1, "a": -1}, "satisfied": {"v": 1, "a": -1},
    "content": {"v": 1, "a": -1}, "calm": {"v": 1, "a": -1},
    "relaxed": {"v": 1, "a": -1}, "serene": {"v": 1, "a": -1},
    "peaceful": {"v": 1, "a": -1}, "relieved": {"v": 1, "a": -1},
    "grateful": {"v": 1, "a": -1},
    # pride / tenderness
    "proud": {"v": 1, "a": 1}, "confident": {"v": 1, "a": 0},
    "tender": {"v": 1, "a": -1}, "affectionate": {"v": 1, "a": 0},
    "warm": {"v": 1, "a": -1}, "fond": {"v": 1, "a": -1},
    "pleased": {"v": 1, "a": 0},
    # boredom / fatigue
    "bored": {"v": -1, "a": -1}, "weary": {"v": -1, "a": -1},
    "tired": {"v": 0, "a": -1}, "numb": {"v": 0, "a": -1},
    "subdued": {"v": 0, "a": -1},
    # neutral / arousal-only
    "neutral": {"v": 0, "a": 0}, "alert": {"v": 0, "a": 1},
    "surprised": {"v": 0, "a": 1}, "startled": {"v": 0, "a": 1},
    "unhappy": {"v": -1, "a": 0}, "uneasy": {"v": -1, "a": 0},
}

# One canonical label per (v-sign, a-sign) cell, used when no proposed
# label survives reconciliation. Every value must exist in AFFECT_LEXICON
# with matching signs so quadrant_label output always passes label_matches.
_QUADRANT_DEFAULTS = {
    (0, 0): "neutral", (0, 1): "alert", (0, -1): "subdued",
    (1, 0): "pleased", (1, 1): "excited", (1, -1): "content",
    (-1, 0): "unhappy", (-1, 1): "anxious", (-1, -1): "downcast",
}

def _float_or(value, fallback=0.0):
    try:
        f = float(value)
    except (TypeError, ValueError):
        return fallback
    return fallback if f != f else f  # NaN -> fallback

def _clamp(value, lo=-1.0, hi=1.0, fallback=0.0):
    return max(lo, min(hi, _float_or(value, fallback)))

def _clamp01(value, fallback=0.0):
    return _clamp(value, 0.0, 1.0, fallback)

def _sign(value):
    v = _float_or(value)
    if v > _SIGN_EPS:
        return 1
    if v < -_SIGN_EPS:
        return -1
    return 0

def _va_pair(value, fallback=(0.0, 0.0)):
    """Coerce an affect point into a clamped (valence, arousal) float pair.

    Reads tolerantly: the canonical {"valence", "arousal"} keys, the
    legacy {"v", "a"} keys (canonical wins when both appear), or a
    (v, a) tuple/list. Anything unusable degrades to `fallback`.
    """
    if isinstance(value, dict):
        v = value.get("valence")
        if v is None:
            v = value.get("v")
        a = value.get("arousal")
        if a is None:
            a = value.get("a")
        return (_clamp(v), _clamp(a))
    try:
        v, a = value  # tuple/list of two
    except (TypeError, ValueError):
        return fallback
    return (_clamp(v), _clamp(a))

def _has_va(value):
    """True when a dict carries an explicit affect point on either key set."""
    return isinstance(value, dict) and any(
        k in value for k in ("valence", "arousal", "v", "a"))

def quadrant_label(v, a):
    """A sensible default label for the V/A quadrant of (v, a)."""
    return _QUADRANT_DEFAULTS[(_sign(v), _sign(a))]

def label_matches(label, v, a):
    """True unless the label's lexicon quadrant *contradicts* sign(v), sign(a).

    A lexicon sign of 0 is unopinionated and matches anything, and an
    observed near-zero axis contradicts nothing — the check only fires on
    an outright opposition like "cheerful" over negative valence. Unknown
    labels return True: don't reject what we can't judge.
    """
    entry = AFFECT_LEXICON.get(str(label or "").strip().casefold())
    if entry is None:
        return True
    for lex_sign, observed in ((entry["v"], v), (entry["a"], a)):
        if lex_sign * _sign(observed) == -1:
            return False
    return True

# ---- Appraisal ----

_SERVES_INTENT_SIMILARITY = 0.4

def normalize_serves(serves, intentions):
    """Resolve a model-emitted `serves` key to "drive" or an intention id.

    Models routinely emit serves as "intention:i2" — or "intention:<the
    goal's own text>" — instead of the bare id the commit priority lookup
    expects, which silently scores a goal-serving impact at situational
    priority (0.4 instead of 0.8). Strips an "intention:" prefix and
    resolves the remainder: an exact id match wins, else the intention
    whose text is most similar (claim_similarity >=
    _SERVES_INTENT_SIMILARITY). Unprefixed keys ("drive", bare ids,
    "situational") pass through untouched, and an unresolvable remainder
    is returned stripped so the caller's situational fallback still
    applies. Pure and total on junk inputs.
    """
    key = str(serves or "").strip()
    if not key.casefold().startswith("intention:"):
        return key
    rest = key[len("intention:"):].strip()
    if not rest:
        return rest
    intents = [i for i in (intentions or []) if isinstance(i, dict)]
    ids = {str(i.get("id") or "") for i in intents}
    if rest in ids:
        return rest
    best_id, best_sim = "", 0.0
    for intent in intents:
        sim = claim_similarity(rest, str(intent.get("intent") or ""))
        if sim > best_sim:  # strict > keeps first-wins ties deterministic
            best_id, best_sim = str(intent.get("id") or ""), sim
    if best_id and best_sim >= _SERVES_INTENT_SIMILARITY:
        return best_id
    return rest

def _normalize_impact(raw, priority_of):
    """Coerce one goal-impact dict and compute its evidence weight."""
    serves = str(raw.get("serves") or "situational").strip() or "situational"
    impact = _clamp(raw.get("impact"))
    certainty = _clamp01(raw.get("certainty"), fallback=0.5)
    agency = str(raw.get("agency") or "none").strip().casefold()
    if agency not in ("self", "other", "none"):
        agency = "none"
    try:
        priority = max(0.0, _float_or(priority_of(serves), 0.4))
    except Exception:
        priority = 0.4  # a broken priority callable degrades to situational weight
    return {
        "serves": serves,
        "impact": impact,
        "certainty": certainty,
        "agency": agency,
        "why": str(raw.get("why") or ""),
        "weight": abs(impact) * certainty * priority,
        "priority": priority,
    }

def _emotion_for(impact, certainty, agency):
    """OCC prospect/agency mapping from one appraised impact to an emotion tag."""
    if impact < 0:
        if certainty < _CERTAINTY_THRESHOLD:
            return "fear"           # loss still in prospect
        if agency == "other":
            return "anger"          # confirmed, someone did this
        return "sadness"            # confirmed, no one to blame
    if certainty < _CERTAINTY_THRESHOLD:
        return "hope"               # gain still in prospect
    return "satisfaction"           # confirmed gain

# Arousal direction per emotion, as a multiplier on ka*weight. Fear and
# anger mobilize; sadness and satisfaction stand down; hope lifts only
# slightly (it is anticipatory, not activating).
_AROUSAL_DIRECTION = {
    "fear": 1.0, "anger": 1.0, "sadness": -1.0,
    "satisfaction": -1.0, "hope": 0.5,
}

def appraise(goal_impacts, priority_of):
    """OCC-style appraisal of this beat's goal impacts into a mood delta.

    `goal_impacts` is a list of {serves, impact[-1,1], certainty[0,1],
    agency: self|other|none, why}; `priority_of` maps a `serves` key to a
    weight (a drive 1.0, an intention id 0.8, "situational" 0.4). Each
    impact contributes weight = |impact| * certainty * priority to a
    valence/arousal delta and votes for one emotion tag. Deterministic and
    total: an empty/None list appraises to zeros with no emotions.
    """
    d_v, d_a = 0.0, 0.0
    tag_weights: dict[str, float] = {}
    dominant, dominant_weight = None, -1.0
    # The DRIVE-serving impact is tracked separately from the overall dominant:
    # drive strain must accrue from a wound to the drive whenever one is present
    # this beat, NOT only when it happens to be the single highest-weight impact.
    # Observed live: a -0.5 drive contradiction (weight 0.40) was discarded
    # because an intention wound (weight 0.43) narrowly out-ranked it, so the
    # drive never registered the hit -- the exact reason ruptures never built.
    drive_impact, drive_weight = None, -1.0

    for raw in goal_impacts or []:
        if not isinstance(raw, dict):
            continue
        norm = _normalize_impact(raw, priority_of)
        if norm["impact"] == 0.0:
            continue  # a no-op impact carries no emotion
        tag = _emotion_for(norm["impact"], norm["certainty"], norm["agency"])
        weight = norm["weight"]
        d_v += _KV * norm["impact"] * norm["certainty"] * norm["priority"]
        d_a += _KA * weight * _AROUSAL_DIRECTION[tag]
        tag_weights[tag] = tag_weights.get(tag, 0.0) + weight
        if weight > dominant_weight:  # strict > keeps first-wins ties deterministic
            dominant, dominant_weight = norm, weight
        if norm["serves"] == "drive" and weight > drive_weight:
            drive_impact, drive_weight = norm, weight

    # sorted() is stable, so equal-weight tags keep first-seen order.
    emotions = [t for t, _ in sorted(tag_weights.items(), key=lambda kv: -kv[1])]
    return {
        "dV": _clamp(d_v),
        "dA": _clamp(d_a),
        "emotions": emotions,
        "dominant": dominant,
        "drive_impact": drive_impact,
    }

# ---- Mood dynamics ----

def blend_affect(old_va, target_va, arousal, shock=False):
    """Convex blend of mood toward an appraisal target, with inertia.

    Plasticity mirrors theory_of_mind's reinforcement blend: high arousal
    makes mood more labile (clamp(0.35 + 0.3*arousal) into [0, 0.9]).
    Absent `shock=True`, each axis moves at most _MAX_STEP per turn so a
    single beat can't teleport a mood across the plane.
    """
    old_v, old_a = _va_pair(old_va)
    target_v, target_a = _va_pair(target_va)
    plasticity = max(0.0, min(0.9, 0.35 + 0.3 * _float_or(arousal)))
    v = old_v + (target_v - old_v) * plasticity
    a = old_a + (target_a - old_a) * plasticity
    if not shock:
        v = old_v + max(-_MAX_STEP, min(_MAX_STEP, v - old_v))
        a = old_a + max(-_MAX_STEP, min(_MAX_STEP, a - old_a))
    return (_clamp(v), _clamp(a))

def decay_affect(va, baseline_va, turns, half_life=_SURFACE_HALF_LIFE):
    """Exponential decay of (va - baseline) back toward baseline.

    Same 2**(-turns/half_life) form as theory_of_mind.decayed_confidence:
    unreinforced mood halves its distance from the character's baseline
    every `half_life` turns instead of persisting at peak forever.
    """
    v, a = _va_pair(va)
    base_v, base_a = _va_pair(baseline_va)
    elapsed = max(0, int(_float_or(turns)))
    if elapsed == 0:
        return (v, a)
    factor = 0.5 ** (elapsed / max(0.001, _float_or(half_life, _SURFACE_HALF_LIFE)))
    return (_clamp(base_v + (v - base_v) * factor),
            _clamp(base_a + (a - base_a) * factor))

# ---- Resolution (the commit-side orchestrator entry point) ----

def _proposed_surface(proposed):
    """The proposal's surface dict, or None for a bare string/junk proposal.

    A full affect dict nests it under "surface"; a flat dict (legacy
    {"label": ...} or {"label", "valence", "arousal"}) *is* the surface.
    """
    if not isinstance(proposed, dict):
        return None
    surface = proposed.get("surface")
    return surface if isinstance(surface, dict) else proposed

def _proposed_label(proposed):
    surface = _proposed_surface(proposed)
    if surface is not None:
        proposed = surface.get("label")
    label = str(proposed or "").strip()
    return label or None

def _undercurrent_label(emotions, proposed, d_v, d_a):
    """Name the suppressed feeling: the dominant emotion *opposite* the
    proposed label, falling back to the top emotion, then the quadrant."""
    for tag in emotions:
        entry = AFFECT_LEXICON.get(tag, {"v": 0, "a": 0})
        if not label_matches(proposed, entry["v"], entry["a"]):
            return tag
    if emotions:
        return emotions[0]
    return quadrant_label(d_v, d_a)

def _relief_impacts(appraisal):
    """Positive, confirmed impacts — candidates for clearing an undercurrent."""
    impacts = []
    dominant = (appraisal or {}).get("dominant")
    if isinstance(dominant, dict):
        impacts.append(dominant)
    for extra in (appraisal or {}).get("impacts") or []:
        if isinstance(extra, dict):
            impacts.append(extra)
    return [i for i in impacts
            if _float_or(i.get("impact")) > 0
            and _float_or(i.get("certainty")) >= _CERTAINTY_THRESHOLD]

def resolve_affect(prev_affect, appraisal_out, baseline, turns_since, proposed):
    """Fold decay, appraisal, and the model's proposed affect into fresh state.

    The affect object is {surface: {label, valence, arousal},
    undercurrent: {label, valence, arousal, source, serves}|None,
    baseline: {valence, arousal}} — canonical keys are "valence" and
    "arousal" on every point this function writes; inputs are read
    tolerantly (legacy "v"/"a" and tuples also accepted). `proposed` may
    be a bare mood string, None, or a full affect dict of that shape.
    The model authors the affect; this function bounds it with
    deterministic floors:

    (a) decay the previous surface toward baseline over `turns_since`;
    (b) pick the surface target: the model's proposed surface point when
        the proposal carries one, nudged by the appraisal's dV/dA;
        otherwise the decayed surface plus dV/dA. Blend from the decayed
        surface toward the target under the inertia clamp, lifted
        (shock) when the dominant impact's |impact| >= 0.8 or the
        proposed surface is a large jump from the previous mood;
    (c) surface label = the model's proposed label (the character's
        *self-report*), kept even when it contradicts the computed signs
        — denial/masking is real behavior. label_matches only
        *substitutes* a label when the model gave none;
    (d) undercurrent: a model-proposed undercurrent is adopted
        (normalized, clamped) and supersedes stale prior residue; relief
        — a positive confirmed impact serving the same goal — still
        clears it. When the model proposes none, the prior undercurrent
        decays on the faster half-life (relief clears it, the floor
        retires it) and a new one is synthesized only when the proposed
        label contradicts a strong appraisal signal.

    Total and graceful: empty appraisal with a bare/absent proposal is
    pure decay toward baseline, and no undercurrent is invented.
    """
    prev = prev_affect if isinstance(prev_affect, dict) else {}
    appraisal = appraisal_out if isinstance(appraisal_out, dict) else {}
    base_v, base_a = _va_pair(baseline if baseline is not None else prev.get("baseline"))

    surface = prev.get("surface") if isinstance(prev.get("surface"), dict) else {}
    prev_label = str(surface.get("label") or "neutral")

    # (a) unreinforced mood drifts home
    decayed_v, decayed_a = decay_affect(surface, (base_v, base_a), turns_since)

    # (b) target = the model's proposed surface point (nudged by the
    # appraisal delta) when it authored one, else the appraisal delta
    # applied to the decayed mood; empty appraisal blends to itself
    d_v, d_a = _clamp(appraisal.get("dV")), _clamp(appraisal.get("dA"))
    dominant = appraisal.get("dominant") if isinstance(appraisal.get("dominant"), dict) else None
    shock = dominant is not None and abs(_float_or(dominant.get("impact"))) >= _SHOCK_IMPACT
    prop_surface = _proposed_surface(proposed)
    if _has_va(prop_surface):
        prop_v, prop_a = _va_pair(prop_surface)
        target_v, target_a = _clamp(prop_v + d_v), _clamp(prop_a + d_a)
        # a deliberate large authored jump is a shock, not drift
        jump = max(abs(prop_v - decayed_v), abs(prop_a - decayed_a))
        shock = shock or jump >= _PROPOSAL_SHOCK_JUMP
    else:
        target_v, target_a = _clamp(decayed_v + d_v), _clamp(decayed_a + d_a)
    v, a = blend_affect(
        (decayed_v, decayed_a), (target_v, target_a), decayed_a, shock=shock)

    # (c) the model's label is the self-report; only substitute when absent
    emotions = [str(e) for e in appraisal.get("emotions") or []]
    proposed_label = _proposed_label(proposed)
    has_signal = bool(emotions) or d_v != 0.0 or d_a != 0.0
    prop_under = (proposed.get("undercurrent")
                  if isinstance(proposed, dict)
                  and isinstance(proposed.get("undercurrent"), dict) else None)
    new_undercurrent = None
    if proposed_label is None:
        # no proposal: keep the old label if it still fits, else rename
        label = prev_label if label_matches(prev_label, v, a) else quadrant_label(v, a)
    else:
        # kept even when the computed signs disagree — masking is real
        label = proposed_label
        if (prop_under is None and has_signal
                and not label_matches(proposed_label, v, a)):
            # The character insists on a label the appraisal contradicts
            # and authored no undercurrent of their own: record what is
            # actually running underneath, so tells (not dialogue) can
            # leak it.
            new_undercurrent = {
                "label": _undercurrent_label(emotions, proposed_label, d_v, d_a),
                "valence": round(d_v, 4),
                "arousal": round(d_a, 4),
                "source": str((dominant or {}).get("why") or ""),
                "serves": str((dominant or {}).get("serves") or ""),
            }

    # (d) undercurrent: the model's authored one wins; relief clears it
    relief = _relief_impacts(appraisal)

    def _relieved(serves):
        return bool(serves) and any(
            str(i.get("serves") or "") == serves for i in relief)

    if prop_under is not None:
        u_v, u_a = _va_pair(prop_under)
        undercurrent = {
            "label": (str(prop_under.get("label") or "").strip()
                      or quadrant_label(u_v, u_a)),
            "valence": round(u_v, 4),
            "arousal": round(u_a, 4),
            "source": str(prop_under.get("source") or ""),
            "serves": str(prop_under.get("serves") or ""),
        }
        if _relieved(undercurrent["serves"]):
            undercurrent = None  # the confirmed win dissolves the dread
    else:
        undercurrent = (prev.get("undercurrent")
                        if isinstance(prev.get("undercurrent"), dict) else None)
        if undercurrent is not None:
            if _relieved(str(undercurrent.get("serves") or "")):
                undercurrent = None
            else:
                u_v, u_a = decay_affect(
                    undercurrent, (0.0, 0.0),
                    turns_since, half_life=_UNDERCURRENT_HALF_LIFE)
                if max(abs(u_v), abs(u_a)) < _UNDERCURRENT_FLOOR:
                    undercurrent = None
                else:
                    undercurrent = {k: val for k, val in undercurrent.items()
                                    if k not in ("v", "a")}
                    undercurrent["valence"] = round(u_v, 4)
                    undercurrent["arousal"] = round(u_a, 4)
        if new_undercurrent is not None:
            undercurrent = new_undercurrent  # suppression supersedes stale residue

    return {
        "surface": {"label": label, "valence": round(v, 4), "arousal": round(a, 4)},
        "undercurrent": undercurrent,
        "baseline": {"valence": base_v, "arousal": base_a},
    }

# ---- Wants ----

def _want_text(want):
    return str(want.get("want") or want.get("desire") or want.get("text") or "").strip()

def normalize_wants(wants, valid_intention_ids):
    """Deterministic floor for a character's declared wants.

    Caps to 3, merges near-duplicates (claim_similarity >= 0.4, higher
    urgency wins), rewrites unknown `serves` (neither "drive" nor a known
    intention id) to "situational", and lets at most one situational want
    survive — weak models otherwise multiply free-floating urges that
    serve nothing. Picks enacted = highest-urgency want and suppressed =
    highest-urgency remaining want with `conflicts_with` set (the desire
    the character is sitting on), annotating both for leak_scan. Returns
    (wants, enacted_idx, suppressed_idx); indices are None when empty.
    """
    valid_ids = {str(i) for i in (valid_intention_ids or [])}
    kept: list[dict] = []
    for raw in wants or []:
        if not isinstance(raw, dict):
            continue
        text = _want_text(raw)
        if not text:
            continue
        want = dict(raw)
        want["want"] = text
        want["urgency"] = _clamp01(raw.get("urgency"), fallback=0.5)
        serves = str(raw.get("serves") or "situational").strip()
        if serves != "drive" and serves not in valid_ids:
            serves = "situational"
        want["serves"] = serves
        want.pop("enacted", None)
        want.pop("suppressed", None)

        # merge near-duplicates: same underlying desire, keep the max urgency
        merged = False
        for i, other in enumerate(kept):
            if claim_similarity(text, other["want"]) >= _WANT_SIMILARITY:
                if want["urgency"] > other["urgency"]:
                    kept[i] = want
                merged = True
                break
        if not merged:
            kept.append(want)

    # at most one free-floating situational want survives (highest urgency)
    best_situational = None
    for want in kept:
        if want["serves"] == "situational":
            if best_situational is None or want["urgency"] > best_situational["urgency"]:
                best_situational = want
    kept = [w for w in kept
            if w["serves"] != "situational" or w is best_situational]

    # cap to 3 by urgency, preserving original relative order of survivors
    if len(kept) > _WANT_CAP:
        ranked = sorted(range(len(kept)), key=lambda i: (-kept[i]["urgency"], i))
        keep_idx = set(ranked[:_WANT_CAP])
        kept = [w for i, w in enumerate(kept) if i in keep_idx]

    if not kept:
        return ([], None, None)

    enacted_idx = max(range(len(kept)), key=lambda i: (kept[i]["urgency"], -i))
    kept[enacted_idx]["enacted"] = True

    suppressed_idx = None
    for i, want in enumerate(kept):
        if i == enacted_idx or not want.get("conflicts_with"):
            continue
        if suppressed_idx is None or want["urgency"] > kept[suppressed_idx]["urgency"]:
            suppressed_idx = i
    if suppressed_idx is not None:
        kept[suppressed_idx]["suppressed"] = True

    return (kept, enacted_idx, suppressed_idx)

# ---- Intentions ----

def _next_intent_id(intentions):
    highest = 0
    for intent in intentions:
        raw = str(intent.get("id") or "")
        if raw.startswith("i"):
            try:
                highest = max(highest, int(raw[1:]))
            except ValueError:
                pass
    return f"i{highest + 1}"

def _find_intent(intentions, intent_id):
    intent_id = str(intent_id or "")
    for intent in intentions:
        if str(intent.get("id") or "") == intent_id:
            return intent
    return None

def apply_intent_ops(intentions, ops, turn_idx, evidence_ok):
    """Apply a turn's intention operations under deterministic guards.

    Enforced floors: at most 4 active intentions; an `add` that is
    near-duplicate (claim_similarity >= 0.4) of an existing intent becomes
    a `progress` on it; `satisfy`/`abandon` within 3 turns of formation
    require `evidence_ok(op)` (goals should not evaporate the beat after
    they form without on-screen cause); `progress`/`block` bump
    last_progress_turn and move progress up/down within [0, 1]; anything
    active but untouched for more than 30 turns goes dormant. New ids are
    assigned i<max+1> deterministically. Returns (intentions, warnings).
    """
    result = [dict(i) for i in (intentions or []) if isinstance(i, dict)]
    warnings: list[str] = []
    turn_idx = int(_float_or(turn_idx))

    for op in ops or []:
        if not isinstance(op, dict):
            continue
        kind = str(op.get("op") or "").strip().casefold()

        if kind == "add":
            text = str(op.get("intent") or "").strip()
            if not text:
                warnings.append("intent add rejected: empty intent text")
                continue
            # a rephrased existing goal is progress on it, not a new goal
            match, best_sim = None, 0.0
            for intent in result:
                if intent.get("status") in ("satisfied", "abandoned"):
                    continue
                sim = claim_similarity(text, str(intent.get("intent") or ""))
                if sim > best_sim:
                    match, best_sim = intent, sim
            if match is not None and best_sim >= _INTENT_SIMILARITY:
                match["progress"] = _clamp01(
                    _float_or(match.get("progress")) + _INTENT_PROGRESS_STEP)
                match["last_progress_turn"] = turn_idx
                match["status"] = "active"
                continue
            active = sum(1 for i in result if i.get("status") == "active")
            if active >= _INTENT_CAP:
                warnings.append(
                    f"intent add rejected (cap {_INTENT_CAP} active): {text!r}")
                continue
            result.append({
                "id": _next_intent_id(result),
                "intent": text,
                "serves_drive": str(op.get("serves_drive") or op.get("serves") or ""),
                "status": "active",
                "formed_turn": turn_idx,
                "last_progress_turn": turn_idx,
                "progress": 0.0,
            })
            continue

        target = _find_intent(result, op.get("id"))
        if target is None:
            warnings.append(f"intent op {kind!r} on unknown id {op.get('id')!r}")
            continue

        if kind in ("progress", "block"):
            step = _INTENT_PROGRESS_STEP if kind == "progress" else -_INTENT_PROGRESS_STEP
            target["progress"] = _clamp01(_float_or(target.get("progress")) + step)
            target["last_progress_turn"] = turn_idx
            if target.get("status") in ("dormant", "blocked"):
                # engagement revives a set-aside goal; a blocked goal that is
                # progressed again is being routed around, so clear the block.
                target["status"] = "active"
                target.pop("blocked_why", None)
        elif kind == "nonviable":
            # The world has CLOSED this goal this beat (route sealed, target
            # destroyed, tool lost). Guarded like satisfy/abandon: the op must
            # cite on-screen evidence (or carry a `why`), so a goal is never
            # quietly dropped. A blocked goal stops steering and stops being a
            # valid `serves` target until engagement (progress/add) revives it.
            try:
                ok = bool(evidence_ok(op))
            except Exception:
                ok = False
            if not ok:
                warnings.append(
                    f"intent nonviable rejected for {target.get('id')!r}: no "
                    "on-screen evidence the goal became impossible")
                continue
            target["status"] = "blocked"
            target["blocked_why"] = str(op.get("why") or "").strip()
            target["blocked_turn"] = turn_idx
            target["last_progress_turn"] = turn_idx
        elif kind in ("satisfy", "abandon"):
            formed = int(_float_or(target.get("formed_turn"), turn_idx))
            if turn_idx - formed <= _INTENT_EVIDENCE_WINDOW:
                try:
                    ok = bool(evidence_ok(op))
                except Exception:
                    ok = False
                if not ok:
                    warnings.append(
                        f"intent {kind} rejected for {target.get('id')!r}: "
                        f"formed {turn_idx - formed} turn(s) ago and no evidence")
                    continue
            target["status"] = "satisfied" if kind == "satisfy" else "abandoned"
            if kind == "satisfy":
                target["progress"] = 1.0
            target["last_progress_turn"] = turn_idx
        else:
            warnings.append(f"unknown intent op {kind!r}")

    # long-untouched goals fade to dormant instead of steering forever
    for intent in result:
        if intent.get("status") != "active":
            continue
        last = int(_float_or(intent.get("last_progress_turn"), turn_idx))
        if turn_idx - last > _INTENT_DORMANT_AFTER:
            intent["status"] = "dormant"
            warnings.append(
                f"intent {intent.get('id')!r} went dormant "
                f"({turn_idx - last} turns without progress)")

    return (result, warnings)

# ---- Drive rupture ----

def _drive_serving_impact(appraisal):
    """The impact wounding (or relieving) the DRIVE this beat, for the strain
    ledger. Prefers appraise()'s dedicated `drive_impact` (the highest-weight
    drive-serving impact, tracked separately so a drive wound registers even
    when an intention wound out-ranks it); falls back to `dominant` when IT
    serves the drive, so a bare/legacy/single-impact appraisal still works."""
    if not isinstance(appraisal, dict):
        return None
    di = appraisal.get("drive_impact")
    if isinstance(di, dict) and str(di.get("serves") or "") == "drive":
        return di
    dom = appraisal.get("dominant")
    if isinstance(dom, dict) and str(dom.get("serves") or "") == "drive":
        return dom
    return None


def update_drive_strain(strain, strain_log, appraisal_out, enacted_serves,
                        suppressed_serves, turns_since):
    """Accrue or pay down the slow strain a character's core drive carries.

    Strain is the deterministic ledger behind drive rupture. The previous
    value first decays toward 0 (half-life _STRAIN_HALF_LIFE over
    `turns_since` — the same 0.5**(t/hl) idiom as decay_affect), then
    moves by at most one delta from the appraisal's *dominant* impact,
    and only when that impact serves the drive and is confirmed
    (certainty >= _CERTAINTY_THRESHOLD):

    - contradiction (impact < 0): +_STRAIN_CONTRADICTION_GAIN * |impact|
      * certainty, x_STRAIN_SELF_MULT when self-caused — UNLESS its
      `why` restates a recent strain-log grievance (claim_similarity >=
      _STRAIN_PUMP_SIMILARITY within the last _STRAIN_PUMP_WINDOW
      entries), in which case it accrues nothing: brooding cannot pump
      strain.
    - relief (impact > 0): -_STRAIN_RELIEF_GAIN * |impact| * certainty.
      Relief is exempt from the damper, as is suppression drift.

    Independently of the dominant accrual, enacting a want that does not
    serve the drive while a drive-serving want sits suppressed drifts
    strain up by _STRAIN_SUPPRESSION_DRIFT: choosing against your own
    drive erodes it.

    Returns (new strain clamped to [0, 1], log entry or None). The entry
    is {"source": contradiction|relief|suppression, "why", "delta"} for
    the largest-magnitude accrual this beat (every accrual still applies
    to the strain value); the caller stamps `turn` before appending it
    to the log. Pure, total, and deterministic on junk inputs.
    """
    new = _clamp01(strain)
    elapsed = max(0, int(_float_or(turns_since)))
    if elapsed:
        new *= 0.5 ** (elapsed / _STRAIN_HALF_LIFE)

    recent = [e for e in (strain_log or []) if isinstance(e, dict)]
    recent = recent[-_STRAIN_PUMP_WINDOW:]
    appraisal = appraisal_out if isinstance(appraisal_out, dict) else {}
    drive_hit = _drive_serving_impact(appraisal)

    accruals = []  # (delta, source, why)
    if drive_hit:
        impact = _clamp(drive_hit.get("impact"))
        certainty = _clamp01(drive_hit.get("certainty"))
        why = str(drive_hit.get("why") or "")
        if certainty >= _STRAIN_CERTAINTY_MIN and impact != 0.0:
            if impact < 0:
                pumped = any(
                    claim_similarity(why, str(e.get("why") or ""))
                    >= _STRAIN_PUMP_SIMILARITY
                    for e in recent)
                if not pumped:
                    delta = _STRAIN_CONTRADICTION_GAIN * abs(impact) * certainty
                    if str(drive_hit.get("agency") or "") == "self":
                        delta *= _STRAIN_SELF_MULT
                    accruals.append((delta, "contradiction", why))
            else:
                accruals.append(
                    (-_STRAIN_RELIEF_GAIN * abs(impact) * certainty,
                     "relief", why))

    if (str(enacted_serves or "") != "drive"
            and str(suppressed_serves or "") == "drive"):
        accruals.append((
            _STRAIN_SUPPRESSION_DRIFT, "suppression",
            "enacted a want that does not serve the drive while a "
            "drive-serving want sat suppressed"))

    for delta, _, _ in accruals:
        new += delta
    new = _clamp01(new)
    if not accruals:
        return (new, None)
    # max() keeps the first maximal accrual, so ties stay deterministic
    delta, source, why = max(accruals, key=lambda acc: abs(acc[0]))
    return (new, {"source": source, "why": why, "delta": round(delta, 4)})

def detect_drive_rupture(strain, appraisal_out, turn_idx, last_shift_turn):
    """Decide whether this beat opens a drive-rupture window.

    Fires only when BOTH keys turn: accumulated strain >=
    _RUPTURE_STRAIN_MIN AND this beat's dominant impact is a confirmed
    drive-scale event — event_score = |impact| * certainty
    (x_RUPTURE_SELF_MULT when self-caused), valid only when it serves
    the drive at certainty >= _CERTAINTY_THRESHOLD, else 0. High strain
    alone smolders without igniting; one catastrophic beat from a cold
    start bounces off. A shift within the last _RUPTURE_COOLDOWN turns
    closes the window entirely.

    Returns None, or {"why", "direction", "score"} where direction is
    "contradiction" for a confirmed loss and "transformation" for a
    strained drive tipped by a transformative gain.
    """
    turn_idx = int(_float_or(turn_idx))
    if (last_shift_turn is not None
            and turn_idx - int(_float_or(last_shift_turn)) < _RUPTURE_COOLDOWN):
        return None
    appraisal = appraisal_out if isinstance(appraisal_out, dict) else {}
    drive_hit = _drive_serving_impact(appraisal) or {}
    impact = _clamp(drive_hit.get("impact"))
    certainty = _clamp01(drive_hit.get("certainty"))
    event_score = 0.0
    if drive_hit and certainty >= _STRAIN_CERTAINTY_MIN:
        event_score = abs(impact) * certainty
        if str(drive_hit.get("agency") or "") == "self":
            event_score *= _RUPTURE_SELF_MULT
    if _clamp01(strain) < _RUPTURE_STRAIN_MIN or event_score < _RUPTURE_EVENT_MIN:
        return None
    return {
        "why": str(drive_hit.get("why") or ""),
        "direction": "contradiction" if impact < 0 else "transformation",
        "score": round(event_score, 4),
    }

def _substring_either(a, b):
    a, b = str(a or "").casefold(), str(b or "").casefold()
    return bool(a) and bool(b) and (a in b or b in a)

def validate_drive_shift(proposal, old_drive, former_drives, rupture):
    """Deterministic gate on a model-proposed drive shift.

    `proposal` is the model's emitted {essence, expression, taboo,
    because} (may be junk), `old_drive` the current {essence, expression,
    taboo}, `former_drives` the scar list, `rupture` the open window from
    detect_drive_rupture. Floors enforced:

    - no proposal dict, no open rupture window, or an empty essence:
      rejected outright;
    - evidence: `because` must relate to rupture["why"]
      (claim_similarity >= _SHIFT_EVIDENCE_SIM or substring either way)
      — a shift cannot cite a cause the rupture never established;
    - coherence band on the essence: >_SHIFT_REPHRASE_SIM similar to the
      old essence is the same drive in new words — at most a *bend*
      (old essence kept, new expression/taboo adopted), rejected when
      nothing else changed; and the new essence must be >=
      _SHIFT_RELATED_SIM similar to at least one of rupture why, old
      essence, old taboo, or a former drive's essence — a drive cannot
      shift to something unrelated to everything the character was.

    Returns (normalized {essence, expression, taboo} or None, kind in
    {"break", "bend", "none"}, warnings). A break fills expression/taboo
    from the old drive when the model omitted them. Pure and total.
    """
    if not isinstance(proposal, dict):
        return (None, "none", ["drive shift rejected: proposal is not a dict"])
    if not isinstance(rupture, dict):
        return (None, "none", ["drive shift rejected: no open rupture window"])
    essence = str(proposal.get("essence") or "").strip()
    if not essence:
        return (None, "none", ["drive shift rejected: empty essence"])

    old = old_drive if isinstance(old_drive, dict) else {}
    old_essence = str(old.get("essence") or "").strip()
    old_expression = str(old.get("expression") or "").strip()
    old_taboo = str(old.get("taboo") or "").strip()
    because = str(proposal.get("because") or "").strip()
    rupture_why = str(rupture.get("why") or "").strip()

    if not (claim_similarity(because, rupture_why) >= _SHIFT_EVIDENCE_SIM
            or _substring_either(because, rupture_why)):
        return (None, "none",
                [f"drive shift rejected: because {because!r} does not "
                 f"relate to the rupture {rupture_why!r}"])

    new_expression = str(proposal.get("expression") or "").strip()
    new_taboo = str(proposal.get("taboo") or "").strip()

    if claim_similarity(essence, old_essence) > _SHIFT_REPHRASE_SIM:
        # same essence in new words: never a break
        changed = ((new_expression and new_expression != old_expression)
                   or (new_taboo and new_taboo != old_taboo))
        if not changed:
            return (None, "none",
                    ["drive shift rejected: essence rephrases the current "
                     "drive and nothing else changed"])
        return ({"essence": old_essence,
                 "expression": new_expression or old_expression,
                 "taboo": new_taboo or old_taboo},
                "bend",
                ["drive shift downgraded to bend: essence rephrases the "
                 "current drive; expression/taboo updated"])

    anchors = [rupture_why, old_essence, old_taboo]
    for former in former_drives or []:
        if isinstance(former, dict):
            anchors.append(str(former.get("essence") or ""))
    if not any(anchor and claim_similarity(essence, anchor) >= _SHIFT_RELATED_SIM
               for anchor in anchors):
        return (None, "none",
                [f"drive shift rejected: new essence {essence!r} is "
                 "unrelated to the rupture, the old drive, and every "
                 "former drive"])

    return ({"essence": essence,
             "expression": new_expression or old_expression,
             "taboo": new_taboo or old_taboo},
            "break", [])

def former_drive_entry(old_drive, ended_turn, by_event):
    """Scar record for a drive a rupture just ended (former_drives entry)."""
    old = old_drive if isinstance(old_drive, dict) else {}
    return {
        "essence": str(old.get("essence") or ""),
        "expression": str(old.get("expression") or ""),
        "taboo": str(old.get("taboo") or ""),
        "ended_turn": int(_float_or(ended_turn)),
        "by_event": str(by_event or ""),
    }

# ---- Leak scan ----

def leak_scan(spoken_texts, wants, undercurrent, intentions):
    """Flag a character's own speech that voices what they are holding back.

    Compares each spoken line (claim_similarity >= 0.5) against suppressed
    wants, the undercurrent (label + source), and active intentions that
    the enacted want does not serve. Speaking the *enacted* want aloud is
    deliberate action, not a leak. Returns human-readable warning strings
    for the narrator/commit layer; deterministic, no side effects.
    """
    warnings: list[str] = []
    wants = [w for w in (wants or []) if isinstance(w, dict)]
    enacted_serves = {str(w.get("serves") or "")
                      for w in wants if w.get("enacted")}
    undercurrent = undercurrent if isinstance(undercurrent, dict) else None
    probe = ""
    if undercurrent is not None:
        probe = f"{undercurrent.get('label') or ''} {undercurrent.get('source') or ''}".strip()

    for raw in spoken_texts or []:
        text = str(raw or "").strip()
        if not text:
            continue
        for want in wants:
            if not want.get("suppressed") or want.get("enacted"):
                continue
            want_text = _want_text(want)
            if want_text and claim_similarity(text, want_text) >= _LEAK_SIMILARITY:
                warnings.append(
                    f"leak: spoken line voices suppressed want {want_text!r}: {text!r}")
        if probe and claim_similarity(text, probe) >= _LEAK_SIMILARITY:
            warnings.append(
                f"leak: spoken line voices undercurrent "
                f"({undercurrent.get('label')!r}): {text!r}")
        for intent in intentions or []:
            if not isinstance(intent, dict) or intent.get("status") != "active":
                continue
            if str(intent.get("id") or "") in enacted_serves:
                continue  # the enacted want serves this goal: speaking it is deliberate
            intent_text = str(intent.get("intent") or "").strip()
            if intent_text and claim_similarity(text, intent_text) >= _LEAK_SIMILARITY:
                warnings.append(
                    f"leak: spoken line voices unenacted intention "
                    f"{intent.get('id')!r} ({intent_text!r}): {text!r}")
    return warnings

# ---- Tells ----

def tell_gate(tell, acuity, familiarity, attention):
    """Deliver a nonverbal tell iff the observer can plausibly catch it.

    A tell carries a subtlety (~0..1); it lands when subtlety <=
    acuity + familiarity + attention. Total and safe on junk: a missing
    subtlety defaults to 0.5, missing observer terms to 0.
    """
    tell = tell if isinstance(tell, dict) else {}
    subtlety = _float_or(tell.get("subtlety"), 0.5)
    threshold = (_float_or(acuity) + _float_or(familiarity) + _float_or(attention))
    return subtlety <= threshold
