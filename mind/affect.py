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

from mind.theory_of_mind import claim_similarity

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

# --- Surface habituation (saturation has a cost) ---------------------------
#
# Decay handles FADING; nothing handled SATURATION. A model that sees its own
# ceiling-pinned surface in the payload proposes the ceiling again, the clamp
# at +/-1 accepts it, and per-beat decay (half-life 8) is undone by the next
# proposal -- so a surface that reaches maximum STAYS there. Measured across
# the live corpus (44 characters with >=8 beats): 21 carry a pinned streak of
# six beats or more at >=0.9 on an axis, three stories hold THIRTY-beat
# valence streaks, and chat 71's Elyra sat ~0.55 above her own baseline for
# seventeen straight turns -- so the climax her whole scene built toward
# landed mathematically FLATTER than its own build-up, which is exactly why
# she read unfazed at it.
#
# The precedent is the codebase's own: `psychology_runtime` habituates the
# hedonic level's cognitive claim across `sustained_beats` ("habituation
# covers the plateau, never the spike"), and comfort habituates on a
# sustained source. The same idea applied to the surface: holding an axis
# near the ceiling costs sensitivity, so under CONTINUED identical stimulus
# the surface drifts down -- restoring headroom -- and a genuine peak has
# somewhere to land. Physiologically true, and dramatically it converts a
# flat plateau into an actual plateau followed by an actual peak.
#
# The pierce condition is the hedonic RELEASE, deliberately. Neither shock
# nor novelty can discriminate the peak on the measured story: the plateau
# beats carry dominant impacts of 0.85-0.95 (shock fires chronically) and
# model-reported novelty reads 0.65 mid-plateau and 0.15 on the actual first
# climax. `released` is the character's own declared discharge, already owned
# and zeroed by the hedonic layer -- on that beat sensitivity is mostly
# refunded (the body re-sensitizes through discharge), so the peak lands with
# its headroom restored while the plateau around it stays compressed.
#
# Per axis, symmetric about the baseline (misery pins exactly as delight
# does): `s` in [0,1] approaches the ELEVATION -- the fraction of the axis's
# available headroom the held surface occupies -- at _HABITUATION_RATE per
# psych unit while elevation stays above the floor, recovers on a half-life
# when the surface comes down, and compresses the resolution TARGET's excess
# over baseline by up to _HABITUATION_MAX_COMPRESSION. The model still
# authors what it feels; the engine bounds it honestly -- the same contract
# resolve_affect has always stated.
# THE FLOOR IS A PROTECTED RANGE, NOT A TRIGGER. Everything below elevation
# _HABITUATION_ELEVATION_FLOOR is never compressed at all -- sustained
# ordinary warmth is a character trait, not a defect -- and only the
# ceiling-slice ABOVE it pays, at up to _HABITUATION_MAX_COMPRESSION of
# that slice. Both halves were calibrated on live replays: a uniform
# compression strong enough to give chat 71's climax a +0.1 contrast cost
# the control story (chat 38, 144 beats of recurring warmth around
# elevation 0.7-0.9) a story-wide ~0.1 valence shift, because its stimulus
# also rides high -- medicine landing on health. Top-slice compression
# separates them structurally: the control's mid-range passes through
# untouched by construction, and the pinned plateau -- which lives almost
# entirely inside the slice -- still settles.
_HABITUATION_RATE = 0.18
_HABITUATION_RECOVERY_HALF_LIFE = 2.5
_HABITUATION_ELEVATION_FLOOR = 0.70
_HABITUATION_MAX_COMPRESSION = 0.85
_HABITUATION_RELEASE_RESET = 0.4

_WANT_CAP = 3
_WANT_SIMILARITY = 0.4
_INTENT_CAP = 4
_INTENT_SIMILARITY = 0.4

# --- Attentional capacity -------------------------------------------------
#
# How much this mind holds at once. `_WANT_CAP` and `_INTENT_CAP` were single
# global constants, identical for every character ever written, and measured
# over the live corpus the want cap BINDS: 78% of banks sit at it, mean 2.63 of
# 3. That is not a safety valve catching an outlier, it is the shape of every
# character's attention, authored once by whoever picked the number 3.
#
# The precedent is `theory_of_mind.sheet_capacity`, which scales the hypothesis
# sheet 5 -> 1 with cognitive absorption on exactly this reasoning: not "your
# beliefs are worth less" but "you can only keep so much in mind at once". This
# extends the same idea from a transient state to an authored disposition -- a
# single-minded character and a character who juggles are different people, and
# the difference should be writable.
#
# `ordinary` IS today's pair, and it is the default everywhere, so an unset
# capacity behaves exactly as every existing story already does. That matters
# more here than usual: CLAUDE.md records twice that an unset psychology field
# fails silently and surfaces fifty beats later as a character who behaves
# wrongly for no visible reason. This dial cannot do that -- the worst an
# unset one can be is what shipped -- and `importers.character_import_warnings`
# still names it so an author knows the dial exists.
#
# PROJECTS ARE NOT ON THIS LADDER, deliberately. `PROJECT_CAP` is a DRAMATIC
# limit, not a cognitive one: with two slots, taking on a third costs something
# given up by name, with the reason stated. A "capable" character allowed six
# projects does not become more capable, they lose the displacement rule that
# makes a project mean anything at all.
CAPACITY_LADDER = ("narrow", "focused", "ordinary", "broad", "wide")
CAPACITY_DEFAULT = "ordinary"
_CAPACITY_CAPS = {
    "narrow":   (1, 2),
    "focused":  (2, 3),
    "ordinary": (_WANT_CAP, _INTENT_CAP),
    "broad":    (4, 5),
    "wide":     (5, 6),
}
CAPACITY_DESCRIPTIONS = {
    "narrow": "one thing at a time; whatever is in front of them is the "
              "whole world until it is finished",
    "focused": "a single purpose and one thing pulling against it",
    "ordinary": "the human middle -- a few live wants, a handful of "
                "commitments in flight",
    "broad": "keeps more in the air than most people can, and drops less",
    "wide": "holds a great deal at once; several commitments stay live and "
            "current without being written down",
}


def normalize_capacity(value):
    """A ladder rung, or the default. Never raises and never invents a rung."""
    key = str(value or "").strip().casefold()
    return key if key in _CAPACITY_CAPS else CAPACITY_DEFAULT


def capacity_caps(capacity=None, absorption=0.0):
    """(want cap, intention cap) for this mind, right now.

    Absorption narrows both by one at the top of the range, floored at one --
    the same claim `sheet_capacity` makes about hypotheses, applied to what a
    mind is trying to want and do. A body screaming for attention leaves less
    room to hold anything else, and this is one step rather than the
    hypothesis sheet's five because a want cap that collapses to a single
    entry under pain would erase ambivalence exactly when it matters most.
    """
    wants, intents = _CAPACITY_CAPS[normalize_capacity(capacity)]
    try:
        pressed = 1 if float(absorption or 0.0) >= 0.8 else 0
    except (TypeError, ValueError):
        pressed = 0
    return max(1, wants - pressed), max(1, intents - pressed)
_INTENT_EVIDENCE_WINDOW = 3
_INTENT_DORMANT_AFTER = 30
# Public: agents/character.py surfaces an active intention as `fading` once
# it has gone two-thirds of the dormancy fuse without progress, so the
# giving-up can happen BY the character instead of TO them (see
# docs/design/DESIGN_LONG_TERM_GOALS.md, "Decay should be reasoned, not silent").
INTENT_DORMANT_AFTER = _INTENT_DORMANT_AFTER
_INTENT_PROGRESS_STEP = 0.2
# Consecutive attempts at FULL progress -- the beat spent on a goal that has
# nothing left to give -- before it stops steering. Two, not more: one barren
# attempt is a straggler, two in a row is a loop, and every further beat is a
# character visibly stuck.
_INTENT_STALL_AFTER = 2
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

def normalize_serves(serves, intentions, projects=None):
    """Resolve a model-emitted `serves` key to "drive", an intention id, or
    a project id.

    Models routinely emit serves as "intention:i2" — or "intention:<the
    goal's own text>" — instead of the bare id the commit priority lookup
    expects, which silently scores a goal-serving impact at situational
    priority (0.4 instead of 0.8). Strips an "intention:" or "project:"
    prefix and resolves the remainder against the matching ledger: an exact
    id match wins, else the entry whose text is most similar
    (claim_similarity >= _SERVES_INTENT_SIMILARITY). Unprefixed keys
    ("drive", bare ids, "situational") pass through untouched, and an
    unresolvable remainder is returned stripped so the caller's situational
    fallback still applies. Pure and total on junk inputs.
    """
    key = str(serves or "").strip()
    folded = key.casefold()
    if folded.startswith("project:"):
        rows = [(str(p.get("id") or ""), str(p.get("project") or ""))
                for p in (projects or []) if isinstance(p, dict)]
        rest = key[len("project:"):].strip()
    elif folded.startswith("intention:"):
        rows = [(str(i.get("id") or ""), str(i.get("intent") or ""))
                for i in (intentions or []) if isinstance(i, dict)]
        rest = key[len("intention:"):].strip()
    else:
        return key
    if not rest:
        return rest
    if rest in {rid for rid, _ in rows}:
        return rest
    best_id, best_sim = "", 0.0
    for rid, text in rows:
        sim = claim_similarity(rest, text)
        if sim > best_sim:  # strict > keeps first-wins ties deterministic
            best_id, best_sim = rid, sim
    if best_id and best_sim >= _SERVES_INTENT_SIMILARITY:
        return best_id
    return rest

def _normalize_impact(raw, priority_of):
    """Coerce one goal-impact dict and compute its evidence weight."""
    serves = str(raw.get("serves") or "situational").strip() or "situational"
    impact = _clamp(raw.get("impact"))
    certainty = _clamp01(raw.get("certainty"), fallback=0.5)
    agency = str(raw.get("agency") or "none").strip().casefold()
    if agency not in ("self", "other", "world", "none"):
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

def appraise(goal_impacts, priority_of, dimensions=None, unresolved_drive=0.0):
    """OCC-style appraisal of this beat's goal impacts into a mood delta.

    `goal_impacts` is a list of {serves, impact[-1,1], certainty[0,1],
    agency: self|other|none, why}; `priority_of` maps a `serves` key to a
    weight (a drive 1.0, an intention id 0.8, "situational" 0.4). Each
    impact contributes weight = |impact| * certainty * priority to a
    valence/arousal delta and votes for one emotion tag. Deterministic and
    total: an empty/None list appraises to zeros with no emotions.

    `unresolved_drive` is the character's carried hedonic `charge` (0..1) --
    `psychology_runtime.resolve_hedonic`'s slow integral of appetite that has
    built up and not yet gone anywhere -- and 0 when they declared release this
    beat. It exists to answer one question this function otherwise cannot ask:
    is this goal DONE, or is it being fed?

    `_emotion_for` tags every confirmed positive impact `satisfaction`, and
    satisfaction stands the body down. That is correct for a goal, which
    completes. It is never correct for a drive, which by construction cannot be
    satisfied -- so a character succeeding continuously at what they most want
    had arousal driven DOWN on every beat of it. Measured live: -0.39 per beat
    against a +0.17 somatic lift, with nothing anywhere providing an
    equilibrium, so surface arousal fell from 0.72 to 0.17 across five beats of
    a character's own strongest appetite, passing their baseline of 0.70 on the
    way to the deactivated quadrant the lexicon calls subdued and numb. It was
    not one character or one kind of scene: five of the author's thirty-six
    live characters sat more than 0.3 below their own baseline, in four
    unrelated stories.

    So while the charge stands unreleased, the satisfaction stand-down is
    withdrawn in proportion to it -- fully at saturation, not at all at zero.
    Only that term is touched: fear and anger still mobilize, sadness still
    deactivates, and the correction can only REMOVE a false stand-down, never
    manufacture arousal that no appraisal produced. When the character declares
    release, `unresolved_drive` is 0 and satisfaction resumes at full strength,
    which is the settling the arc actually wants.
    """
    extended = isinstance(dimensions, dict)
    dimensions = dimensions if extended else {}
    d_v, d_a = 0.0, 0.0
    # The satisfaction-tagged share of d_a, kept separately so it alone can be
    # withdrawn below without disturbing any other emotion's contribution.
    d_a_satisfaction = 0.0
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
        arousal_term = _KA * weight * _AROUSAL_DIRECTION[tag]
        d_a += arousal_term
        if tag == "satisfaction":
            d_a_satisfaction += arousal_term
        tag_weights[tag] = tag_weights.get(tag, 0.0) + weight
        if weight > dominant_weight:  # strict > keeps first-wins ties deterministic
            dominant, dominant_weight = norm, weight
        if norm["serves"] == "drive" and weight > drive_weight:
            drive_impact, drive_weight = norm, weight

    # Intrinsic bodily pleasantness and appraisal-process dimensions are
    # orthogonal to goal success. A current touch can hurt or feel good even
    # when no standing goal moved; novelty can mobilize without being bad.
    intrinsic = _clamp(dimensions.get("intrinsic_pleasantness"))
    norm = _clamp(dimensions.get("norm_compatibility"))
    congruence = _clamp(dimensions.get("self_congruence"))
    novelty = _clamp01(dimensions.get("novelty"))
    somatic = dimensions.get("somatic_impact")
    somatic = somatic if isinstance(somatic, dict) else {}
    pain = _clamp01(somatic.get("pain"), fallback=0.0)
    pleasure = _clamp01(somatic.get("pleasure"), fallback=0.0)
    memory_echo = dimensions.get("memory_echo")
    memory_echo = memory_echo if isinstance(memory_echo, dict) else {}
    remembered_somatic = _clamp(
        memory_echo.get("somatic"), -0.2, 0.2, 0.0)
    d_v += intrinsic * 0.25 + norm * 0.08 + congruence * 0.08
    d_v += pleasure * 0.2 - pain * 0.25
    d_a += novelty * 0.12 + max(pain, pleasure) * 0.12
    # A remembered danger can tighten the chest; a remembered pleasure can
    # bring warmth. It nudges mood/arousal but never enters somatic_impact, so
    # the runtime cannot reinterpret it as current injury or stimulation.
    d_v += remembered_somatic * 0.2
    d_a += abs(remembered_somatic) * 0.1

    # An appetite still carrying its charge has not been satisfied, whatever
    # the goal ledger says it just achieved. Withdraw that share of the
    # stand-down (d_a_satisfaction is <= 0, so this only ever adds back).
    unresolved = _clamp01(unresolved_drive)
    if unresolved > 0.0 and d_a_satisfaction < 0.0:
        d_a -= d_a_satisfaction * unresolved

    # sorted() is stable, so equal-weight tags keep first-seen order.
    emotions = [t for t, _ in sorted(tag_weights.items(), key=lambda kv: -kv[1])]
    result = {
        "dV": _clamp(d_v),
        "dA": _clamp(d_a),
        "emotions": emotions,
        "dominant": dominant,
        "drive_impact": drive_impact,
    }
    if extended:
        result.update({
            "unresolved_drive": unresolved,
            "novelty": novelty,
            "controllability": _clamp01(
                dimensions.get("controllability"), fallback=0.5),
            "coping_potential": _clamp01(
                dimensions.get("coping_potential"), fallback=0.5),
            "norm_compatibility": norm,
            "self_congruence": congruence,
            "intrinsic_pleasantness": intrinsic,
            "somatic_impact": {
                "pain": pain, "pleasure": pleasure,
                "why": str(somatic.get("why") or ""),
            },
            "memory_echo": {
                "somatic": remembered_somatic,
                "threat_bias": _clamp01(
                    memory_echo.get("threat_bias"), fallback=0.0),
                "why": str(memory_echo.get("why") or ""),
                "temporal_source": "remembered_past",
            } if memory_echo else {},
        })
    return result

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

    Same 0.5**(t/half_life) form as theory_of_mind.decayed_confidence, but
    NOT the same t: unreinforced mood halves its distance from the
    character's baseline every `half_life` TURNS -- the caller counts beats
    -- while a belief's half-life is measured in minutes of simulation time
    whenever the story has a clock. The shared shape is the arithmetic, not
    the unit.
    """
    v, a = _va_pair(va)
    base_v, base_a = _va_pair(baseline_va)
    elapsed = max(0.0, _float_or(turns))
    if elapsed == 0:
        return (v, a)
    factor = 0.5 ** (elapsed / max(0.001, _float_or(half_life, _SURFACE_HALF_LIFE)))
    return (_clamp(base_v + (v - base_v) * factor),
            _clamp(base_a + (a - base_a) * factor))

def _habituation_elevation(value, base):
    """The fraction of this axis's available headroom a surface occupies.

    Relative to the character's OWN baseline, so a placid 0.1-baseline body
    and an excitable 0.7-baseline body saturate at the same felt distance
    from home, not at the same absolute number. The span floor keeps a
    baseline sitting near a rail from making every twitch read as
    saturation."""
    span = max(0.25, 1.0 - abs(_clamp(base)))
    return _clamp01(abs(_clamp(value) - _clamp(base)) / span)


def resolve_surface_habituation(prev_s, elevation, turns, released=False):
    """One axis's sensitivity state, advanced one resolution.

    Pure and total, the resolve_hedonic idiom: `prev_s` in [0,1] (junk reads
    as 0), `elevation` from _habituation_elevation, `turns` in psych units.
    A release refunds most of the accumulated cost FIRST (discharge
    re-sensitizes the body), then the beat accumulates or recovers as
    usual: elevation held above the floor drags `s` toward it at
    _HABITUATION_RATE per unit; anything lower lets `s` decay home on the
    recovery half-life."""
    s = _clamp01(prev_s)
    elevation = _clamp01(elevation)
    units = max(0.0, _float_or(turns))
    if released:
        s *= _HABITUATION_RELEASE_RESET
    if units == 0.0:
        return round(s, 4)
    # The destination is the elevation's EXCESS above the floor, rescaled --
    # not the elevation itself. A merely-warm hold just over the floor
    # habituates toward almost nothing, a pinned ceiling toward almost
    # everything; measured on the control story (chat 38), destination =
    # elevation compressed its recurring 0.9-ish warmth nearly as hard as
    # chat 71's flat 1.0 plateau, which is medicine landing on health.
    span = max(0.001, 1.0 - _HABITUATION_ELEVATION_FLOOR)
    destination = _clamp01((elevation - _HABITUATION_ELEVATION_FLOOR) / span)
    if destination > s:
        rate = 1.0 - (1.0 - _HABITUATION_RATE) ** units
        s = s + (destination - s) * rate
    else:
        factor = 0.5 ** (units / _HABITUATION_RECOVERY_HALF_LIFE)
        s = destination + (s - destination) * factor
    return round(_clamp01(s), 4)


def _compress_top_slice(value, base, s):
    """Habituation's cost, paid only by the ceiling-slice of an axis.

    The excess of `value` over the baseline is split at the protected
    range's edge (_HABITUATION_ELEVATION_FLOOR of the axis's span): the
    part below passes through untouched, the slice above is scaled by
    (1 - _HABITUATION_MAX_COMPRESSION * s). Symmetric about the baseline,
    total on junk."""
    base = _clamp(base)
    value = _clamp(value)
    span = max(0.25, 1.0 - abs(base))
    protected = _HABITUATION_ELEVATION_FLOOR * span
    excess = value - base
    magnitude = abs(excess)
    if magnitude <= protected:
        return value
    slice_ = magnitude - protected
    compressed = protected + slice_ * (
        1.0 - _HABITUATION_MAX_COMPRESSION * _clamp01(s))
    return _clamp(base + (1.0 if excess >= 0 else -1.0) * compressed)


def _habituation_state(prev_affect):
    """The stored per-axis sensitivity state, tolerantly read."""
    prev = prev_affect if isinstance(prev_affect, dict) else {}
    state = prev.get("habituation")
    state = state if isinstance(state, dict) else {}
    return (_clamp01(state.get("valence")), _clamp01(state.get("arousal")))


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

def resolve_affect(prev_affect, appraisal_out, baseline, turns_since, proposed,
                   *, habituate=False, released=False):
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

    `habituate` (default False -- the shipped behaviour, byte-identical,
    and the state key is then neither read nor written) switches on
    surface habituation: sustained near-ceiling elevation accumulates a
    per-axis sensitivity cost (see the _HABITUATION_* block) that
    compresses the target's excess over baseline, so a pinned plateau
    settles and a genuine peak has headroom to land in. `released` is the
    hedonic discharge flag for THIS beat (the same one resolve_hedonic
    receives): it refunds most of the accumulated cost before this beat
    resolves, which is what lets the climax pierce the compression the
    plateau earned.
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
    habituation = None
    if habituate:
        # Sensitivity accumulates from the STIMULUS -- this beat's
        # uncompressed target elevation -- not from the body's own already-
        # dampened surface, which would cap `s` at a feedback fixed point
        # and let a pinned stimulus keep most of its ceiling (measured on
        # the chat-71 replay: surface-driven accumulation stalled at
        # s=0.40 exactly where compressed elevation met its own
        # destination). The target then pays the cost: its excess over
        # baseline is compressed by up to _HABITUATION_MAX_COMPRESSION.
        # A released beat refunds most of the cost first (inside
        # resolve_surface_habituation), so the discharge lands with its
        # headroom restored. Compression bounds the DESTINATION only --
        # the label, the undercurrent and every other channel of the
        # resolution are untouched, and the model's self-report survives
        # exactly as before.
        prev_s_v, prev_s_a = _habituation_state(prev)
        s_v = resolve_surface_habituation(
            prev_s_v, _habituation_elevation(target_v, base_v),
            turns_since, released=released)
        s_a = resolve_surface_habituation(
            prev_s_a, _habituation_elevation(target_a, base_a),
            turns_since, released=released)
        # Habituation covers the plateau, never the spike (the
        # cognitive_absorption rule, applied here): on the RELEASE beat
        # compression is waived outright -- the discharge is the one moment
        # the body is fully present -- and the reset `s` above covers the
        # beats that follow it.
        if not released:
            target_v = _compress_top_slice(target_v, base_v, s_v)
            target_a = _compress_top_slice(target_a, base_a, s_a)
        habituation = {"valence": s_v, "arousal": s_a}
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

    resolved = {
        "surface": {"label": label, "valence": round(v, 4), "arousal": round(a, 4)},
        "undercurrent": undercurrent,
        "baseline": {"valence": base_v, "arousal": base_a},
    }
    if habituation is not None:
        # Present only when the feature is on: the default path stays
        # byte-identical, and a story switched back off simply stops
        # carrying (and reading) the state.
        resolved["habituation"] = habituation
    return resolved

# ---- Wants ----

def _want_text(want):
    return str(want.get("want") or want.get("desire") or want.get("text") or "").strip()

def normalize_wants(wants, valid_intention_ids, *, want_cap=None):
    """Deterministic floor for a character's declared wants.

    `want_cap` is this character's attentional capacity (see `capacity_caps`);
    omitted it is the `ordinary` rung, which is the constant this has always
    used, so every existing caller and story is unchanged.

    Caps to `want_cap` -- 1 at the `narrow` rung through 5 at `wide`, and 3
    at `ordinary`, which is the default and the number this used to hardcode
    -- merges near-duplicates (claim_similarity >= 0.4, higher
    urgency wins), rewrites unknown `serves` (neither "drive" nor a known
    intention/project id -- the caller passes the union) to "situational",
    and lets at most one situational want
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
            # Models emit "intention:i2" / "project:pa1" here exactly as they
            # do in goal_impacts, and until now that silently demoted the
            # want to situational -- the same demotion normalize_serves
            # exists to prevent one field over.
            stripped = serves
            for prefix in ("intention:", "project:"):
                if stripped.casefold().startswith(prefix):
                    stripped = stripped[len(prefix):].strip()
                    break
            serves = stripped if stripped in valid_ids else "situational"
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

    # cap by urgency, preserving original relative order of survivors
    cap = _WANT_CAP if want_cap is None else max(1, int(want_cap))
    if len(kept) > cap:
        ranked = sorted(range(len(kept)), key=lambda i: (-kept[i]["urgency"], i))
        keep_idx = set(ranked[:cap])
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

def _revive_intent(target):
    """Engagement revives a set-aside goal. A blocked goal progressed again is
    being routed around, so the block and its bookkeeping clear with it --
    otherwise `blocked_turn` outlives the block and an active goal carries the
    turn index of a state it is no longer in."""
    target["status"] = "active"
    for key in ("blocked_why", "blocked_turn", "stalled_turn"):
        target.pop(key, None)

def _advance_intent(target, turn_idx, warnings, *, barren_beat=False):
    """Apply one step of forward progress, returning True if it actually moved.

    A goal already at the ceiling cannot advance: the beat was spent on it and
    gained nothing. Recording that as progress is what let a character grind
    one goal turn after turn -- `last_progress_turn` was refreshed by the very
    act of grinding, so the dormancy sweep below could only ever fire on a
    FORGOTTEN goal, never on a stuck one, and the guard meant to stop a goal
    steering forever was defeated by exactly the behaviour it existed to catch.

    `barren_beat` is that same rule one rung lower, and it was found in play.
    The ceiling test catches a character grinding once there is nothing left to
    gain; it says nothing about one grinding UP THE RAMP, where every repeat
    still buys a real +0.2 and refreshes the clock. Live (chat 80, turns 1-3):
    a psychologist delivered the same three propositions -- you were sedated,
    it was not to harm you, the restraints are for safety -- on three
    consecutive beats, and `ia1` went 0.0 -> 0.2 -> 0.4 with `barren_attempts`
    never set. Nothing had happened; the ledger recorded steady progress
    because progress is a SELF-REPORT and this was the only place it was
    audited.

    The caller supplies the flag rather than this module deriving it, because
    the engine has already measured it: `agents/character.py` detects that this
    beat repeated an earlier move.

    That detection used to be filtered by a model screen that judged whether
    the beat had INVITED the repetition, and only an unscreened one reached
    here. The screen existed to decide whether to pay for a full re-ask; the
    re-ask is gone (repetition is weak, not unusable, and a redo on anything
    short of broken output is a nuisance), so the screen went with it. The
    honest consequence, stated rather than hidden: a repetition the beat
    genuinely invited -- an insistence, one continuous riff, a deliberate
    return -- now counts barren too. It costs that goal its +0.2 and surfaces
    `barren_attempts` to the character, which for an insistence that is not
    working is the right thing to say and for one that is working is a beat of
    over-caution. Nothing is asked of the model either way: it emits whatever
    ops it likes, and the engine declines to call a repeat an advance.

    Barren attempts leave the clock alone and never revive a set-aside goal.
    After _INTENT_STALL_AFTER of them AT THE CEILING the goal stops steering:
    with nothing left to gain it must be satisfied, abandoned, or replaced by a
    goal that asks something genuinely different. A barren beat below the
    ceiling counts and warns but does NOT stall, deliberately -- a slow
    intention is not a stuck one, and taking a goal away from a character over
    two repeated beats would be the guard doing more harm than the grind.
    Closing a goal still needs evidence.
    """
    before = _clamp01(_float_or(target.get("progress")))
    after = _clamp01(before + _INTENT_PROGRESS_STEP)
    at_ceiling = after <= before
    if not at_ceiling and not barren_beat:
        target["progress"] = after
        target["last_progress_turn"] = turn_idx
        target.pop("barren_attempts", None)
        return True

    barren = int(_float_or(target.get("barren_attempts"))) + 1
    target["barren_attempts"] = barren
    if at_ceiling and barren >= _INTENT_STALL_AFTER and target.get("status") == "active":
        target["status"] = "dormant"
        target["stalled_turn"] = turn_idx
        warnings.append(
            f"intent {target.get('id')!r} stalled: {barren} attempts at full "
            "progress with nothing gained -- satisfy, abandon or re-route it")
    elif at_ceiling:
        warnings.append(
            f"intent {target.get('id')!r}: already at full progress, "
            "nothing gained this beat")
    else:
        warnings.append(
            f"intent {target.get('id')!r}: progress claimed on a beat that "
            f"repeated an earlier move -- {barren} barren attempt(s), progress "
            f"held at {before:.1f}")
    return False

def steering_intent_ids(intentions, turn_idx):
    """The ids that still weigh as GOALS when scoring this beat's appraisal.

    A goal that has stopped steering must stop moving the character's mood at
    full goal priority. Membership of the intentions list only answers "is this
    a real id"; scoring every real id at intention priority meant a goal the
    world had closed, or one gone dormant, kept hitting as hard as a live one
    for the rest of the story.

    An intent still steers when it is active, OR when it was touched THIS beat
    whatever its new status. The second clause matters more than it looks: the
    closing ops all stamp `last_progress_turn` with the current turn, and the
    beat a goal is satisfied, abandoned, or sealed off by the world is the beat
    it matters MOST. Dropping those to situational weight would mute every
    payoff and every collapse at the exact moment it lands -- a worse fault
    than the one this fixes. A stall is the deliberate exception: it does not
    stamp the clock, because arriving at "nothing gained, again" is not a
    dramatic beat and should not be scored like one.
    """
    out = set()
    for intent in intentions or []:
        if not isinstance(intent, dict):
            continue
        try:
            touched = int(_float_or(intent.get("last_progress_turn"), -1)) >= int(
                _float_or(turn_idx))
        except (TypeError, ValueError):
            touched = False
        if intent.get("status") == "active" or touched:
            out.add(str(intent.get("id")))
    return out

def apply_intent_ops(intentions, ops, turn_idx, evidence_ok, *,
                     intent_cap=None, barren_beat=False):
    """Apply a turn's intention operations under deterministic guards.

    `intent_cap` is this character's attentional capacity (see
    `capacity_caps`); omitted it is the `ordinary` rung, which is the constant
    this has always used, so every existing caller and story is unchanged.

    Enforced floors: at most `intent_cap` active intentions -- 2 at the
    `narrow` rung through 6 at `wide`, and 4 at `ordinary`, which is the
    default and the number this used to hardcode; an `add` that is
    near-duplicate (claim_similarity >= 0.4) of an existing intent becomes
    a `progress` on it; `satisfy`/`abandon` within 3 turns of formation
    require `evidence_ok(op)` (goals should not evaporate the beat after
    they form without on-screen cause); `progress`/`block` move progress
    up/down within [0, 1] and bump last_progress_turn -- except that a
    `progress` on a goal already at the ceiling gains nothing, so it does not
    touch the clock and counts toward a stall instead (see _advance_intent);
    anything active but untouched for more than 30 turns goes dormant. New ids
    are assigned i<max+1> deterministically. Returns (intentions, warnings).
    """
    result = [dict(i) for i in (intentions or []) if isinstance(i, dict)]
    warnings: list[str] = []
    turn_idx = int(_float_or(turn_idx))
    _cap = _INTENT_CAP if intent_cap is None else max(1, int(intent_cap))

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
                # Rephrasing is not a way around a spent goal: the restatement
                # revives it only if it had somewhere left to go -- and not
                # around a BARREN one either. A character repeating itself
                # usually restates the goal rather than emitting `progress`
                # on it, so leaving the flag off here left the rung it exists
                # to close open to exactly the traffic that most needs it:
                # same beat, same repetition, opposite outcome decided by
                # which op the model happened to choose.
                if _advance_intent(match, turn_idx, warnings,
                                   barren_beat=barren_beat):
                    _revive_intent(match)
                continue
            active = sum(1 for i in result if i.get("status") == "active")
            if active >= _cap:
                warnings.append(
                    f"intent add rejected (cap {_cap} active): {text!r}")
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
            if kind == "block":
                # The world pushing back IS engagement: it moves the goal (down)
                # and re-opens room above it, so the barren count starts over.
                target["progress"] = _clamp01(
                    _float_or(target.get("progress")) - _INTENT_PROGRESS_STEP)
                target["last_progress_turn"] = turn_idx
                target.pop("barren_attempts", None)
                moved = True
            else:
                moved = _advance_intent(target, turn_idx, warnings,
                                        barren_beat=barren_beat)
            if moved and target.get("status") in ("dormant", "blocked"):
                _revive_intent(target)
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

# ---- Projects (Tier 1.5) ----
#
# The tier between the eternal drive and the completable intention: durable
# but not eternal, able to name a room, and structurally immune to every
# mechanism above that correctly spends intentions. Four measured failures
# motivate it (docs/design/DESIGN_LONG_TERM_GOALS.md): a life's-work aim marked
# satisfied the beat after its first success; a commission decayed dormant by
# 150 barren beats the world had not withdrawn; aims abandoned along with the
# tactic that served them; and a standing purpose out-competed every beat by
# whatever the current room offered, because it scored 0.8 against
# drive-serving wants at 1.0.
#
# The cap IS the mechanism. Two slots, never more: with seven live
# intentions there is no answer to "what is this person about right now",
# with two there always is. Adoption over a full ledger is refused, so
# taking on a third has a price -- something must be given up, by name, with
# the reason stated. That displacement is deliberately the ONLY way a
# project ends other than meeting its own criterion: no dormancy sweep, no
# stall counter, no progress field. A hundred barren beats is a normal week
# inside a project.

PROJECT_CAP = 2
_PROJECT_SIMILARITY = 0.4
# A satisfied_when at or above this similarity to its own project text is
# circular ("done when I have done it"). Measured gap on real strings:
# circular/task criteria 0.5-0.75, genuine external conditions 0.125-0.25.
_CRITERION_RESTATES_SIM = 0.4
_FORMER_PROJECTS_CAP = 6


def _next_project_id(projects, former):
    """Deterministic p<n>, never reusing an id a former project carried --
    a displaced project's id coming back on an unrelated adoption would make
    the former ledger read as the history of the new one."""
    highest = 0
    for rec in list(projects or []) + list(former or []):
        raw = str((rec or {}).get("id") or "") if isinstance(rec, dict) else ""
        if raw.startswith("p"):
            try:
                highest = max(highest, int(raw.lstrip("pa")))
            except ValueError:
                pass
    return f"p{highest + 1}"


def apply_project_ops(projects, former, ops, turn_idx):
    """Apply a turn's project operations under the cap and the legibility
    floor. Returns (projects, former, warnings).

    Ops: `adopt` {project, about?, satisfied_when?} takes one on while a
    slot is free; `displace` {id, why} gives one up -- why is REQUIRED,
    because the giving-up is the act: it is the one revision of a belief
    about the self the engine supports, and it must happen out loud, never
    as silent eviction; `satisfy` {id, why} closes one whose OWN
    satisfied_when criterion has been met -- a project with no criterion is
    not completable at all (it re-arms at every occasion by construction)
    and satisfy on it is refused.

    Closures are applied before adoptions whatever order the model emitted,
    so displace-and-adopt lands in one beat without the model having to know
    the processing order. Ends land in `former` with the stated reason and
    the turn -- continuity, like former_drives, not obligation.

    What is deliberately ABSENT here is most of the point: no dormancy
    sweep, no barren counter, no progress ceiling. Nothing in this function
    or any other touches a project the model did not explicitly close.
    """
    live = [dict(p) for p in (projects or []) if isinstance(p, dict)]
    ended = [dict(p) for p in (former or []) if isinstance(p, dict)]
    warnings: list[str] = []
    turn_idx = int(_float_or(turn_idx))
    ops = [op for op in (ops or []) if isinstance(op, dict)]

    def _find(pid):
        pid = str(pid or "")
        for p in live:
            if str(p.get("id") or "") == pid:
                return p
        return None

    for op in ops:
        kind = str(op.get("op") or "").strip().casefold()
        if kind not in ("displace", "satisfy"):
            continue
        target = _find(op.get("id"))
        if target is None:
            warnings.append(f"project {kind} rejected: unknown id "
                            f"{str(op.get('id') or '')!r}")
            continue
        why = str(op.get("why") or "").strip()
        if not why:
            warnings.append(
                f"project {kind} rejected for {target.get('id')!r}: a "
                "project ends by a stated reason or not at all")
            continue
        if kind == "satisfy" and not str(
                target.get("satisfied_when") or "").strip():
            warnings.append(
                f"project satisfy rejected for {target.get('id')!r}: it has "
                "no satisfied_when criterion, so it is not completable -- "
                "it re-arms at every occasion; displace it with a reason if "
                "it no longer speaks for the character")
            continue
        live.remove(target)
        ended.append({
            "id": str(target.get("id") or ""),
            "project": str(target.get("project") or ""),
            "why": why, "turn": turn_idx,
            "end": "satisfied" if kind == "satisfy" else "displaced",
        })

    for op in ops:
        kind = str(op.get("op") or "").strip().casefold()
        if kind in ("displace", "satisfy"):
            continue
        if kind != "adopt":
            warnings.append(f"unknown project op {kind!r}")
            continue
        text = str(op.get("project") or "").strip()
        if not text:
            warnings.append("project adopt rejected: empty project text")
            continue
        dup = next((p for p in live if claim_similarity(
            text, str(p.get("project") or "")) >= _PROJECT_SIMILARITY), None)
        if dup is not None:
            warnings.append(
                f"project adopt rejected: restates {dup.get('id')!r} -- a "
                "project is held, not re-adopted")
            continue
        # THE DELIBERATION GATE. "Can a mind reliably deliberate that this
        # is worthy as a project?" is answered by making the deliberation
        # mechanical: state what would END this other than doing it once.
        # A criterion that RESTATES the project is not a criterion --
        # measured cleanly separable on real strings: circular criteria
        # ("understand the symbols" -> "when I understand the symbols")
        # score 0.5-0.75 against their project text, genuine external
        # conditions ("the keepers withdraw the commission", "spring comes
        # and the village still stands") score 0.125-0.25. The same gate
        # catches a TASK wearing the word, because a task's completion
        # restates the task ("fetch the physician" -> "the physician is
        # here", 0.5). What it cannot catch is an insincere-but-external
        # criterion; that residue is what probation below is for.
        crit = str(op.get("satisfied_when") or "").strip()
        if not crit:
            warnings.append(
                "project adopt rejected: adoption is a deliberation -- "
                "state satisfied_when, what would end this project OTHER "
                "than doing it once. No statable end beyond the doing "
                "means it is a task or a fascination, not a project")
            continue
        if claim_similarity(text, crit) >= _CRITERION_RESTATES_SIM:
            warnings.append(
                "project adopt rejected: satisfied_when restates the "
                "project, which is circular -- 'done when I have done it' "
                "is what a TASK says. Name the condition OUTSIDE the doing "
                "that would end it, or serve it as an intention instead")
            continue
        if len(live) >= PROJECT_CAP:
            warnings.append(
                "project adopt rejected: both slots full -- adopting a "
                "third requires displacing one by name, with the reason "
                "stated (a displace op in the same beat frees the slot)")
            continue
        about = str(op.get("about") or "").strip().casefold()
        live.append({
            "id": _next_project_id(live, ended),
            "project": text,
            "about": about if about in ("world", "self") else "",
            "satisfied_when": crit,
            "adopted_turn": turn_idx,
            # Fresh adoption counts as service: the drift clock starts now,
            # not at some notional zero that would read as instantly adrift.
            "last_served_turn": turn_idx,
            # PROBATION: a runtime adoption weighs at intention level and
            # may lapse quietly until it is lived into -- see
            # settle_probation. Nobody knows on day one that something is
            # their life's work; time filters instead of judgement.
            "probation": True,
            "served_beats": 0,
        })

    return (live, ended[-_FORMER_PROJECTS_CAP:], warnings)


# Establishment is EARNED BY SERVICE, never by survival. The obvious rule
# ("survives N boundary reviews") was considered and rejected: the measured
# failure mode of this tier is precisely that the model stops referring to
# what it holds, so passive survival would establish a project by
# inattention -- the exact pathology, made permanent. Both floors are
# needed: service alone lets a three-beat enthusiasm establish same-day;
# age alone is establishment by neglect. Served on three distinct beats
# across at least a dozen turns is a commitment that lasted AND was acted
# on.
_PROBATION_SERVED_MIN = 3
_PROBATION_AGE_MIN = 12
# A probationary project unserved this long lapses -- quietly, because you
# can drop something you took up last week without ceremony; the stated-
# reason floor stays where it matters, on projects a character has actually
# lived by. Three times the drift-marker threshold: the character has been
# SHOWN the drift for two-thirds of the fuse before the lapse lands, so a
# lapse is never the first notice. Deliberately wider than the intention
# stall (2 barren attempts) -- probationary barren-tolerance is most of
# what adoption buys before establishment.
_LAPSE_AFTER = 24


def settle_probation(projects, former, turn_idx):
    """Establish or lapse probationary projects. Returns (projects, former,
    warnings). Deterministic, runs every commit AFTER the service ledger so
    this beat's service counts.

    Establishment removes the probation flag: the project now weighs at
    drive level and can no longer lapse -- from here only its own
    satisfied_when or a displacement with a stated reason ends it. A lapse
    moves it to former_projects with end 'lapsed' and an auto-stated why:
    recorded continuity, no ceremony. Authored and harness-written projects
    never pass through here at all (no probation flag -- the author's
    deliberation already happened), which is what keeps the live pa1
    untouched by this change."""
    live, ended, warnings = [], list(former or []), []
    turn_idx = int(_float_or(turn_idx))
    for p in projects or []:
        if not (isinstance(p, dict) and p.get("probation")):
            live.append(p)
            continue
        p = dict(p)
        served = int(_float_or(p.get("served_beats")))
        age = turn_idx - int(_float_or(p.get("adopted_turn"), turn_idx))
        idle = turn_idx - int(_float_or(p.get("last_served_turn"), turn_idx))
        if served >= _PROBATION_SERVED_MIN and age >= _PROBATION_AGE_MIN:
            p.pop("probation", None)
            warnings.append(
                f"project {p.get('id')!r} established -- served "
                f"{served} beats over {age} turns; it now weighs with the "
                "drive and ends only by its criterion or out loud")
        elif idle >= _LAPSE_AFTER:
            ended.append({
                "id": str(p.get("id") or ""),
                "project": str(p.get("project") or ""),
                "why": f"lapsed on probation: unserved for {idle} beats",
                "turn": turn_idx,
                "end": "lapsed",
            })
            warnings.append(
                f"project {p.get('id')!r} lapsed -- adopted turn "
                f"{p.get('adopted_turn')}, unserved for {idle} beats; a "
                "fascination that passed, recorded without ceremony")
            continue
        live.append(p)
    return (live, ended[-_FORMER_PROJECTS_CAP:], warnings)


def _last_named_room(text, named_rooms):
    """The last room a text names, resolved against {casefolded node name:
    rid}. Last-named wins for the same reason as _destination_from_goals:
    'from the gate to the shrine' is going TO the shrine. None when the text
    names no known room -- both vocabularies closed, identifier recognition,
    never prose reading."""
    folded = str(text or "").casefold()
    best = None
    for key, rid in (named_rooms or {}).items():
        if not key:
            continue
        pos = folded.rfind(str(key))
        if pos >= 0 and (best is None or pos > best[0]):
            best = (pos, str(rid))
    return best[1] if best else None


def projects_served_this_beat(projects, wants, goal_text, impact_serves=(),
                              named_rooms=None):
    """The project ids this beat's declared interior actually served.

    The measured failure this feeds (A15, run 5): `pa1` held at weight 1.0
    while, twenty beats in, nothing the character emitted served it -- top
    want serves 'drive', goal 'Reorient and test connectivity', and no
    marker anywhere for the gap between HOLDING a project and SERVING it.
    The tier stopped failing by being outranked and started failing by
    being forgotten. This is the ledger the drift marker reads.

    Three channels, most explicit first:
      * a want whose `serves` resolves to the project id;
      * a goal-impact `serves` resolving to it (caller pre-normalizes);
      * the beat goal naming the SAME room the project text names, over the
        character's own place-graph names -- the substance channel, because
        a character routinely serves a project without citing it ('Move
        west along proven route toward Chamber 0603' never says pa1).
        Text similarity was measured and rejected for this: it scored the
        chalk-circle detour (0.2) ABOVE 'walk the proved line to the
        shrine' (0.167). Naming the same destination is the honest test,
        and for projects about people rather than places the two explicit
        channels still carry.
    """
    rows = [(str(p.get("id") or ""), str(p.get("project") or ""))
            for p in (projects or []) if isinstance(p, dict)]
    ids = {rid for rid, _ in rows if rid}
    served = set()
    for w in wants or []:
        if isinstance(w, dict) and str(w.get("serves") or "") in ids:
            served.add(str(w["serves"]))
    for s in impact_serves or ():
        if str(s) in ids:
            served.add(str(s))
    goal_room = _last_named_room(goal_text, named_rooms)
    if goal_room:
        for rid, text in rows:
            if rid not in served \
                    and _last_named_room(text, named_rooms) == goal_room:
                served.add(rid)
    return served


def goal_slot_currency(prev_active, goal_text, named_rooms, here_rid,
                       turn_idx):
    """Tenure and spend stamps for the beat-goal slot, computed at commit.

    `active_state.goal` is rewritten every commit from the enacted want, so
    the SLOT is per-beat -- but the CLAIM inside it is whatever the model
    re-emits, and re-emission is free: the en_route continuation-default
    deliberately made goals sticky, and stickiness serves whatever holds the
    slot. Measured (maze, turns 370-385): "Compare chalk circle patterns
    across chambers" survived a run boundary and a process restart with no
    cap, criterion, or visibility; "Run east to Chamber 0206 along the
    proved line" kept steering for beats after he had stood in Chamber 0206
    and moved on -- a claim the engine could SEE was spent, tethering him
    back to the room it named (visited tail ... 0306 0206 0205 0206 0306
    0206). The goal was functioning as an ungoverned project.

    Two deterministic facts, stamped here at the single active_state write
    point and read back by agents/character._annotate_goal_currency:

      * `goal_since` -- the turn the slot last CHANGED words. Same words
        carried forward keep the stamp; any re-wording is a re-authoring
        and restarts the clock. Tenure is what a run boundary the engine
        cannot see (no engine row) still shows up as.
      * `goal_room` / `goal_room_reached` -- the room the goal's own text
        names over the character's OWN place-graph names (identifier
        recognition, never prose reading), and the turn the character's
        committed position first became that room while these exact words
        held. A reached claim stays reached only while the words stand:
        "return to the kitchen", said fresh, is a new claim and routes.

    Facts only -- nothing here rewrites the goal, and the payload marker
    plus the routing exclusion (_destination_from_goals) are the read side.
    Pure and total on junk inputs. Returns the stamps to merge into the
    freshly rebuilt active_state; an empty slot holds nothing and gets
    nothing.
    """
    text = str(goal_text or "").strip()
    if not text or not isinstance(turn_idx, int):
        return {}
    prev = prev_active if isinstance(prev_active, dict) else {}
    same_claim = (text.casefold()
                  == str(prev.get("goal") or "").strip().casefold())
    since = None
    if same_claim:
        try:
            since = int(prev.get("goal_since"))
        except (TypeError, ValueError):
            since = None
    out = {"goal_since": since if since is not None else turn_idx}
    room = _last_named_room(text, named_rooms)
    if not room:
        return out
    out["goal_room"] = room
    reached = None
    if same_claim:
        try:
            reached = int(prev.get("goal_room_reached"))
        except (TypeError, ValueError):
            reached = None
    if reached is None and here_rid is not None \
            and str(here_rid) == room:
        reached = turn_idx
    if reached is not None:
        out["goal_room_reached"] = reached
    return out


def project_boundary(projects, intentions, before_status, new_room,
                     prev_room, scene_marker, location, frame_id,
                     named_rooms=None):
    """The engine-detectable moments that re-ask a held project. Returns a
    why-string, or None when no boundary passed this beat.

    v1 left boundary review prompt-normative and it did not hold (A15 run
    5: nine perfect beats, then drift, with no moment that ever re-asked
    what the project meant for the next move). These are the boundaries the
    engine can actually SEE, each one honest:

      * arrival -- the character's committed position just became the room
        a project's own text names, over their own place-graph names;
      * a task ending -- an intention entered satisfied/abandoned/blocked
        this commit (the closing ops are the one lifecycle edge commit can
        observe without trusting a self-report);
      * the scene or frame changing -- against the scene_marker persisted
        last beat; no marker (first beat) is silence, never a boundary.

    NOT detectable, deliberately absent rather than faked: 'run end' (a
    harness concept the engine has no row for) and 'major Director event'
    (events carry no uniform salience field; memory salience is a different
    ledger). Detection is a fact; what the review MEANS stays the
    character's -- the flag invites project_ops, it never applies any.

    A CHARACTER WITH NO PROJECTS STILL GETS BOUNDARIES. This used to open with
    `if not projects: return None`, and combined with the payload's matching
    guard it closed the tier permanently: the prompt names the review beat as
    the occasion to emit project_ops, the review beat required a project, and
    so no first project could ever be adopted. Measured over the live corpus,
    0 of 14 banks that carry the field have ever held a project or a former one
    -- an entire tier of psychology, with the longest single block in the
    character prompt behind it, that has never once run.

    Only the ARRIVAL reason genuinely needs projects, because it compares the
    new room against what a held project names. A task closing and the scene
    or frame changing are boundaries in their own right, and for a character
    with nothing standing they are the moments the question is worth asking at
    all: you have just finished something, or you are somewhere new. Nothing
    here adopts anything -- it invites, exactly as it did before.
    """
    reasons = []
    if new_room and str(new_room) != str(prev_room or ""):
        for p in projects or ():
            if not isinstance(p, dict):
                continue
            proom = _last_named_room(str(p.get("project") or ""), named_rooms)
            if proom and proom == str(new_room):
                reasons.append("you have arrived where your project "
                               f"{str(p.get('id') or '')} points")
                break
    closed = ("satisfied", "abandoned", "blocked")
    for intent in intentions or []:
        if not isinstance(intent, dict):
            continue
        sid = str(intent.get("id") or "")
        if intent.get("status") in closed \
                and (before_status or {}).get(sid) not in closed:
            reasons.append(f"your task {sid} closed this beat")
            break
    if isinstance(scene_marker, dict):
        if str(location or "") != str(scene_marker.get("location") or ""):
            reasons.append("the scene has changed")
        elif str(frame_id or "") != str(scene_marker.get("frame") or ""):
            reasons.append("the frame has changed")
    return "; ".join(reasons) if reasons else None


def serves_priority(serves, steering_ids, project_ids=(), probation_ids=()):
    """The appraisal weight of a `serves` key: drive 1.0, an ESTABLISHED
    project 1.0, a probationary project or steering intention 0.8, anything
    else situational 0.4.

    Established projects score AT DRIVE WEIGHT deliberately -- this is the
    whole answer to the measured loss: the shrine commission, expressed as
    an intention, lost the beat auction to drive-serving wants at
    1.0-vs-0.8 every time, in three arms. A project is what a character is
    ABOUT right now; a want serving it must not weigh less than a want
    serving what they eternally are. The scarcity cap (two slots) is what
    makes that weight safe to grant -- seven intentions at 1.0 would just
    move the soup up a tier.

    A PROBATIONARY project weighs exactly as an intention does, on purpose:
    adoption alone must buy no appraisal power, or a nine-beat fascination
    adopted into the free slot becomes privileged the moment it is named.
    Drive weight is earned by service (settle_probation), never by the act
    of adopting.
    """
    key = str(serves or "")
    if key == "drive":
        return 1.0
    if key in {str(p) for p in (project_ids or ())}:
        return 1.0
    if key in {str(p) for p in (probation_ids or ())}:
        return 0.8
    return 0.8 if key in (steering_ids or ()) else 0.4


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
    moves by at most one delta from the impact that serves the DRIVE this
    beat (`_drive_serving_impact`: `appraise`'s dedicated `drive_impact`,
    falling back to `dominant` only when the dominant one serves the drive
    — a drive wound out-ranked by an intention wound still registers), and
    only when that impact is confirmed at certainty >=
    _STRAIN_CERTAINTY_MIN (0.5, NOT the mood-appraisal
    _CERTAINTY_THRESHOLD of 0.8 — see the constant's own note: a
    pre-rupture signal is inherently uncertain, and demanding certainty
    about the self-doubt discarded the most authentic version of it):

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
    elapsed = max(0.0, _float_or(turns_since))
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
    _RUPTURE_STRAIN_MIN AND this beat's drive-serving impact
    (`_drive_serving_impact`, the same one strain accrues from) is a
    confirmed drive-scale event — event_score = |impact| * certainty
    (x_RUPTURE_SELF_MULT when self-caused), valid only at certainty >=
    _STRAIN_CERTAINTY_MIN (0.5), else 0. High strain
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


def ground_tells(manifest, active_state):
    """F6: every manifest tell must carry a non-empty `because` -- the
    CONCRETE private ground the cue is evidence of -- so a planted tell can
    be paid off in a later beat instead of dangling as fake significance
    (impostor t2: a hand lingering 'a half-second longer than a servant's
    glance should' whose ground -- handedness? habit? -- never existed
    anywhere).

    Deterministic floor, applied at the character stage (the earliest point
    the data exists): a tell the model left ungrounded derives its `because`
    from its own `betrays` pointer -- the suppressed want's text or the
    undercurrent's label from active_state -- falling back to whichever of
    the two exists. Only a tell with NO derivable ground at all is left
    empty, and that is reported as a warning. The ground is PRIVATE: the
    perception layer delivers only the cue text (_delivered_manifest), never
    `because`.

    Mutates and returns (manifest, warnings)."""
    if not isinstance(manifest, dict):
        return manifest, []
    tells = manifest.get("tells")
    if not isinstance(tells, list):
        return manifest, []
    state = active_state if isinstance(active_state, dict) else {}
    affect_state = state.get("affect") if isinstance(state.get("affect"), dict) else {}
    undercurrent = affect_state.get("undercurrent")
    if isinstance(undercurrent, dict):
        under_text = str(undercurrent.get("label") or "").strip()
    else:
        under_text = str(undercurrent or "").strip()
    wants = state.get("wants") if isinstance(state.get("wants"), list) else []
    suppressed_text = ""
    sup_idx = state.get("suppressed_want")
    if sup_idx is not None:
        try:
            want = wants[int(sup_idx)]
            if isinstance(want, dict):
                suppressed_text = _want_text(want)
        except (TypeError, ValueError, IndexError):
            pass

    warnings = []
    for tell in tells:
        if not isinstance(tell, dict) or not str(tell.get("cue") or "").strip():
            continue
        because = str(tell.get("because") or "").strip()
        if because:
            tell["because"] = because
            continue
        betrays = str(tell.get("betrays") or "").strip().lower()
        if betrays == "suppressed_want":
            ground = suppressed_text or under_text
        elif betrays == "undercurrent":
            ground = under_text or suppressed_text
        else:
            ground = under_text or suppressed_text
        if ground:
            tell["because"] = ground
        else:
            warnings.append(
                f"ungrounded tell: {str(tell.get('cue'))[:60]!r} has no "
                "`because` and no undercurrent/suppressed want to derive "
                "one from -- a planted tell needs a stored ground."
            )
    return manifest, warnings
