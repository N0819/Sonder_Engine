"""Evidence-backed local social judgment for Charter people.

This is deliberately not a reputation score.  A judgment belongs to one
holder, points at one subject, keeps several independent axes, and cites the
claims that moved it.  Objective events do not enter here directly: callers
pass the holder's own sparse ``minds`` map, so a closed door or an untold
report produces no social change simply because the event was true.

``regard`` in :mod:`world.charter_politics` remains the narrow credibility
weight used when somebody tells a claim.  Trust is broader, fear is not
negative warmth, respect is not obedience, and suspicion is not forced to be
the inverse of trust.  Keeping those distinctions is the whole feature.

THE TIE LAYER LIVES HERE, beside the axes it reads, and not in a module of
its own.  ``RESEARCH.md`` §1.7.6 item 3 takes Comme il Faut's decision to keep
BOTH representations: numbers drive scoring, a discrete label drives
legibility, and a narrator can state "they are close" where it cannot state a
five-tuple.  Co-location is the anti-contradiction guarantee -- a tie is a
READING of ``JUDGMENT_AXES`` plus the holder's own directed regard and its own
co-presence count, so a change to the axes that orphaned the derivation is
visible in the same file rather than three modules away.

A TIE IS ONE HEAD'S VIEW AND IS DIRECTIONAL.  CiF's discrete relationships are
symmetric by definition; here they cannot be, because two people do not share
a head.  ``ties[holder][other]`` reads only ``judgments[holder][other]``,
``regard["holder->other"]`` and ``served_beside[holder][other]`` -- never the
other party's stance, never the institution's blame register.  A may hold B
``close`` while B holds A merely ``familiar``, and the unrequited tie is worth
more than the symmetric one: a mind acting on a bond the other party does not
hold is the distance deception and dramatic irony are made of.
"""

from __future__ import annotations

from .charter_politics import (NEUTRAL_REGARD, REGARD_CEILING,
                               REGARD_FLOOR, regard_value)


JUDGMENT_AXES = ("trust", "warmth", "fear", "respect", "suspicion")
JUDGMENT_CAP = 24
REASON_CAP = 6
SEEN_CAP = 128

# Conservative substrate defaults.  Worlds may replace or extend these with
# ``social_norms.signals``.  These signals describe what an observable event
# ordinarily does to reliance/avoidance, not whether the act was moral.
DEFAULT_SIGNALS = {
    "threat": {"fear": 0.16, "suspicion": 0.06, "trust": -0.05},
    "warning": {"respect": 0.02},
    "accusation": {"suspicion": 0.04},
    "apology": {"warmth": 0.03},
    "thanks": {"warmth": 0.025},
    "praise": {"warmth": 0.025, "respect": 0.015},
    "insult": {"warmth": -0.06, "respect": -0.025},
    "commitment_fulfilled": {
        "trust": 0.14, "respect": 0.06, "suspicion": -0.08},
    "commitment_defaulted": {
        "trust": -0.18, "respect": -0.06, "suspicion": 0.14},
    "commitment_repudiated": {
        "trust": -0.11, "respect": -0.04, "suspicion": 0.08},
    "report_confirmed": {"trust": 0.09, "suspicion": -0.04},
    "report_refuted": {"trust": -0.12, "suspicion": 0.10},
    "aid_given": {"trust": 0.08, "warmth": 0.06, "respect": 0.03},
    "harm_done": {"trust": -0.13, "fear": 0.10, "suspicion": 0.08},
    # SPELLED THE WAY THE EVENT IS SPELLED. This was `order_obeyed`, and
    # `institution_order_executed` has been emitted by `charter_decide` and
    # witnessed into every co-present head since the day orders landed -- it
    # moved nothing because two dictionaries in the same package named the
    # same happening differently. Renaming the SIGNAL rather than the event is
    # deliberate: the event kind is already persisted in `scheduled_events`
    # payloads and already in `charter_news.WITNESSABLE`.
    #
    # `order_refused` is deleted rather than remapped. The only candidate was
    # `institution_order_failed`, which fires on absent stock
    # (`charter_decide` line 187), carries no body at all, and records nobody
    # refusing anything -- attributing it to `received_by` would blame a
    # person for empty shelves.
    "institution_order_executed": {"trust": 0.025, "respect": 0.025},
}

#: THE SIX LABELS. Each one is a single axis's dominance, so the label set is
#: a READING of the network above and never a second opinion about it: `close`
#: and `at_odds` are the two signs of the same warmth-led quantity, `wary` is
#: suspicion, `afraid_of` is fear, `looks_up_to` is respect, and `familiar` is
#: co-presence with nothing said about it either way. Five axes, five
#: quantities, six words -- there is deliberately no label the numbers cannot
#: produce, because a label the numbers cannot produce is a second store that
#: will disagree with the first one.
#:
#: `familiar` is DERIVED at read time and never stored (`tie_of`). It is the
#: floor of the ladder rather than a rung on it: it needs no evidence beyond
#: the tally `served_beside` already keeps, and storing it would put a row on
#: nearly every pair in a stable institution for no information at all.
TIE_LABELS = ("close", "at_odds", "wary", "afraid_of", "looks_up_to",
              "familiar")

#: Shared windows at which familiarity reads 1.0. HOISTED from
#: `charter_promote.acquainted`, which had it inline as `shared / 200.0`: the
#: same saturation now has two readers, and two copies of a tuned constant is
#: how they drift. The claim is unchanged -- the difference between never and
#: often is most of the signal, and the difference between often and
#: constantly is nearly none.
TIE_SATURATION = 200

#: Shared windows before a pair reads `familiar` at all. Measured on
#: `twin_towns(40)`, window 8h, seed 5: at 24 windows nobody qualifies after a
#: simulated week (168h) and the people who actually share a place do after a
#: simulated month. Below this the label fires for one accidental crossing,
#: which is not what the word means.
FAMILIAR_FLOOR = 24

#: What it takes to ADOPT a signed label, in the quantities below. Read against
#: `DEFAULT_SIGNALS`' per-event magnitudes (0.02-0.18) this says "about five
#: ordinary acts in one direction, or two grave ones".
#:
#: IT IS A PREDICTION AND NOT YET A MEASUREMENT, and should be re-set the day
#: the distribution is worth reading: before `RESEARCH.md` §1.7.6 item 2 landed
#: there was no distribution at all -- a stressed simulated year of
#: `twin_towns(40)` produced 8 events, 4 judgment holders and a largest axis
#: anywhere in the institution of 0.142. With item 2's producers in, the same
#: fixture driven into famine for a quarter reaches 40 holders and 149 stances
#: with 18 axes pinned at 1.000, so the threshold now has something to bite on.
TIE_FORM = 0.30

#: How much of the forming quantity a label needs to KEEP existing, as a
#: fraction of `TIE_FORM`. Hysteresis, and the reason a tie is not a number
#: with a name: a bond that formed at 0.30 and drifted to 0.22 is still a bond,
#: and relabelling it every time the arithmetic crosses a line would make the
#: legible half of this design less legible than the numbers it summarizes.
TIE_HOLD = 0.6

#: Familiarity a pair must already have before `close` may form. FORMATION
#: ONLY -- `normalize_ties` never applies it, for the same reason forming is
#: harder than holding everywhere else here. You cannot be close to somebody
#: you have barely been near, however well the axes read; a stranger who does
#: you one enormous favour is somebody you trust, which is what the axes will
#: say on their own.
CLOSE_FAMILIARITY = 0.25

#: How long a freshly adopted label is left alone before another may replace
#: it. FORMING TAKES A SEASON, LOSING TAKES AN INSTANT: a move to `at_odds` or
#: `afraid_of` ignores the dwell entirely, because a rupture that had to wait
#: a day to be recorded would be a rupture the state cannot represent.
TIE_DWELL_HOURS = 24.0

#: Ties one holder may carry, ranked by the strength of what produced them.
#: The same cap and the same argument as `JUDGMENT_CAP` above it: a head that
#: holds a view about everyone holds a useful view about no one.
TIE_CAP = 24

#: What a bond is made of. Warmth leads, trust follows, and directed regard is
#: a thumb on the scale rather than a term that can decide anything: 0.15 is
#: below `TIE_FORM` by construction, so regard alone -- which every pair in a
#: charter has, at `NEUTRAL_REGARD` or moved by a blame the holder may never
#: have heard about -- can neither form nor sustain a tie. That bound is what
#: makes `update_ties`' holder prefilter sound, and `test_regard_alone_cannot
#: _form_a_tie` fails loudly if this weight is ever raised past `TIE_FORM`.
TIE_WEIGHTS = {"warmth": 0.50, "trust": 0.35, "regard": 0.15}

#: Evidence ids a stored tie carries, COPIED from the holder's own judgment
#: reasons. Two, because the tie is a summary and a summary that cites six
#: things is the thing it was summarizing.
TIE_REASON_CAP = 2

#: Order a tie between equally strong quantities is decided in. Dominance
#: picks the label first; this only breaks a tie between magnitudes, and it
#: breaks it toward the reading that changes conduct most -- being afraid of
#: somebody is a stronger fact about how you behave near them than admiring
#: them is.
_TIE_PRIORITY = ("afraid_of", "at_odds", "wary", "close", "looks_up_to")


def _clamp(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0.0
    return round(max(-1.0, min(1.0, value)), 6)


def _room(before, raw):
    """How much of a signal is left to land, given where the axis already is.

    DIMINISHING RETURNS ARE REQUIRED HERE, not a refinement. Judgments decay
    NOWHERE in this package, so every signal is permanent and `_clamp`
    saturates hard at 1.0. Measured on the 40-body `twin_towns` charter driven
    into famine for a simulated quarter: 674 `aid_given` events, 29 stances,
    and 63 of their 145 axes sitting at exactly 1.000 -- a network that has
    stopped carrying information and now measures the same thing familiarity
    already measures in `served_beside`. It is also the right claim about
    people: the fiftieth time somebody helps you is not worth what the first
    was.

    TOWARD THE BOUND THE EVIDENCE PUSHES AT, which is the one deviation from
    "scale by ``1 - abs(before)``". That form damps CONTRARY evidence just as
    hard as confirming evidence, so an axis at +0.9 barely moves for a
    betrayal and an axis pinned at 1.0 could never come back at all -- in a
    package with no decay that is a stance frozen for the life of the story.
    Room is measured in the direction of travel and never exceeds full weight,
    so the first piece of evidence against a settled view lands whole.
    """
    room = 1.0 - before * (1.0 if float(raw) > 0.0 else -1.0)
    return max(0.0, min(1.0, room))


def _unit(value, default=0.0):
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = float(default)
    return max(0.0, min(1.0, value))


def normalize_social_norms(stored):
    """Author-owned signal weights, closed onto safe numeric bounds."""
    stored = stored if isinstance(stored, dict) else {}
    signals = {kind: dict(weights) for kind, weights in DEFAULT_SIGNALS.items()}
    for kind, raw in (stored.get("signals") or {}).items():
        if not isinstance(raw, dict):
            continue
        weights = {}
        for axis in JUDGMENT_AXES:
            if axis in raw:
                weights[axis] = _clamp(raw[axis])
        if weights:
            signals[str(kind)] = weights
    return {
        "signals": signals,
        # How much weaker ordinary hearsay is than firsthand evidence.  The
        # teller's directed regard is applied separately at uptake.
        "hearsay_weight": _unit(stored.get("hearsay_weight", 0.55), 0.55),
    }


def normalize_judgments(stored):
    """``holder -> subject -> stance`` from any tolerant JSON shape."""
    out = {}
    for holder, subjects in (stored or {}).items():
        if not isinstance(subjects, dict):
            continue
        held = {}
        for subject, raw in subjects.items():
            if not isinstance(raw, dict):
                continue
            reasons = []
            for reason in raw.get("reasons") or ():
                if not isinstance(reason, dict) or not reason.get("evidence_id"):
                    continue
                reasons.append({
                    "evidence_id": str(reason["evidence_id"]),
                    "signal": str(reason.get("signal") or ""),
                    "source": str(reason.get("source") or ""),
                    "weight": round(_unit(reason.get("weight", 1.0), 1.0), 6),
                })
            entry = {axis: _clamp(raw.get(axis, 0.0))
                     for axis in JUDGMENT_AXES}
            entry["reasons"] = reasons[-REASON_CAP:]
            entry["seen"] = [str(x) for x in raw.get("seen") or ()
                             if str(x)][-SEEN_CAP:]
            if not entry["seen"]:
                entry["seen"] = [r["evidence_id"] for r in reasons][-SEEN_CAP:]
            held[str(subject)] = entry
        if held:
            # Strongest/most-reasoned stances survive an overfull import.
            ranked = sorted(held.items(), key=lambda pair: (
                max(abs(pair[1][a]) for a in JUDGMENT_AXES),
                len(pair[1]["reasons"]), pair[0]), reverse=True)
            out[str(holder)] = dict(ranked[:JUDGMENT_CAP])
    return out


def _signals_in_claim(claim, signal_kinds):
    public = claim.get("public_evidence")
    if isinstance(public, dict):
        for act in public.get("speech_acts") or ():
            if not isinstance(act, dict):
                continue
            kind = str(act.get("kind") or "")
            # A promise changes no trust merely by being uttered.  Its later
            # fulfilment/default is the evidence that moves judgment.
            if kind in signal_kinds:
                yield kind, str(public.get("actor") or claim.get("about") or "")
    event_kind = str(claim.get("event_kind") or "")
    if event_kind in signal_kinds:
        actor = str(claim.get("actor") or claim.get("about") or "")
        yield event_kind, actor


def update_judgments_from_minds(judgments, minds, *, politics=None,
                                norms=None):
    """Fold newly held evidence into local stances, exactly once per holder.

    A claim may be copied or strengthened later; its stable ``body`` key is
    the evidence identity.  Reasons are therefore both explanation and
    idempotence guard.  Returns ``(judgments, movements)``.
    """
    out = normalize_judgments(judgments)
    cfg = normalize_social_norms(norms)
    regard = ((politics or {}).get("regard") or {})
    movements = []
    for holder, claims in (minds or {}).items():
        if not isinstance(claims, dict):
            continue
        for evidence_id, claim in claims.items():
            if not isinstance(claim, dict):
                continue
            strength = _unit(claim.get("strength", 0.0))
            source = str(claim.get("heard_from") or "")
            weight = strength
            if source:
                weight *= cfg["hearsay_weight"]
                weight *= min(1.0, regard_value(regard, holder, source))
            for signal, subject in _signals_in_claim(
                    claim, set(cfg["signals"])):
                subject = str(subject or "").strip()
                if not subject or subject == str(holder):
                    continue
                stance = out.setdefault(str(holder), {}).setdefault(
                    subject, {**{axis: 0.0 for axis in JUDGMENT_AXES},
                              "reasons": [], "seen": []})
                seen_key = f"{evidence_id}|{signal}"
                if seen_key in stance.get("seen", ()) \
                        or str(evidence_id) in stance.get("seen", ()):
                    continue
                deltas = cfg["signals"].get(signal) or {}
                moved = {}
                for axis, raw in deltas.items():
                    before = float(stance.get(axis) or 0.0)
                    delta = float(raw) * weight * _room(before, raw)
                    if not delta:
                        continue
                    stance[axis] = _clamp(before + delta)
                    moved[axis] = round(stance[axis] - before, 6)
                if not moved:
                    continue
                reason = {"evidence_id": str(evidence_id), "signal": signal,
                          "source": source, "weight": round(weight, 6)}
                stance["reasons"] = (stance["reasons"] + [reason])[-REASON_CAP:]
                stance["seen"] = (list(stance.get("seen") or ())
                                  + [seen_key])[-SEEN_CAP:]
                movements.append({"holder": str(holder), "subject": subject,
                                  "signal": signal, "deltas": moved,
                                  **reason})
    return normalize_judgments(out), movements


def judgment_of(judgments, holder, subject):
    return (normalize_judgments(judgments).get(str(holder), {})
            .get(str(subject)))


def judgment_view(judgments, holder, *, subjects=(), cap=4):
    """Bounded, explanation-bearing Scene Life/promotion projection."""
    held = normalize_judgments(judgments).get(str(holder), {})
    wanted = {str(s) for s in subjects if str(s)}
    rows = []
    for subject, stance in held.items():
        if wanted and subject not in wanted:
            continue
        salience = max(abs(float(stance[a])) for a in JUDGMENT_AXES)
        rows.append({"subject": subject,
                     **{a: stance[a] for a in JUDGMENT_AXES},
                     "reasons": list(stance.get("reasons") or ()),
                     "salience": round(salience, 6)})
    rows.sort(key=lambda row: (-row["salience"], row["subject"]))
    return rows[:max(0, int(cap))]


# --------------------------------------------------------------------------
# The discrete tie. `RESEARCH.md` §1.7.6 item 3, and the module docstring
# above carries the argument for why it lives in this file.
# --------------------------------------------------------------------------


def familiarity(served_beside, holder, other):
    """How much of a life two people have spent in the same room, 0.0-1.0.

    The holder's OWN co-presence tally and nothing else -- the same number
    `charter_promote.acquainted` hands a promotion, saturating at the same
    `TIE_SATURATION`, so the promotion payload and the tie cannot disagree
    about how well two people know each other.
    """
    shared = int(((served_beside or {}).get(str(holder)) or {})
                 .get(str(other)) or 0)
    return round(min(1.0, max(0, shared) / float(TIE_SATURATION)), 4)


def _regard_offset(regard, holder, other):
    """Directed regard as a signed unit, neutral at zero.

    Regard lives in `[REGARD_FLOOR, REGARD_CEILING]` around `NEUTRAL_REGARD`,
    which is an asymmetric band; scaling by the WIDER half keeps a full-scale
    swing under 1.0 in both directions rather than letting the short side
    reach further per point than the long one.
    """
    span = max(REGARD_CEILING - NEUTRAL_REGARD, NEUTRAL_REGARD - REGARD_FLOOR)
    raw = (regard_value(regard, holder, other) - NEUTRAL_REGARD) / (span or 1.0)
    return max(-1.0, min(1.0, raw))


def _quantities(judgment, regard_offset=0.0):
    """The four quantities the six labels read, from one stance.

    ONE AXIS EACH, except `bond`, which is warmth-led and mixes trust and
    directed regard under `TIE_WEIGHTS`: liking somebody, relying on them and
    believing them are the three things "close" is ordinarily made of, and
    separating them into three labels would be the five-tuple again with
    worse words. Suspicion, fear and respect each keep their own label
    because none of them is the negative of another -- that distinction is
    the whole reason `JUDGMENT_AXES` has five entries.

    Only the POSITIVE side of guard/dread/esteem names anything. There is no
    word for the absence of fear, and inventing one would put a row on every
    pair in the institution.
    """
    stance = judgment if isinstance(judgment, dict) else {}

    def axis(name):
        try:
            return float(stance.get(name) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    bond = (TIE_WEIGHTS["warmth"] * axis("warmth")
            + TIE_WEIGHTS["trust"] * axis("trust")
            + TIE_WEIGHTS["regard"] * float(regard_offset))
    return {"bond": round(max(-1.0, min(1.0, bond)), 6),
            "guard": axis("suspicion"), "dread": axis("fear"),
            "esteem": axis("respect")}


#: Which quantity each signed label reads, and in which direction.
_TIE_SOURCE = {
    "close": ("bond", 1.0),
    "at_odds": ("bond", -1.0),
    "wary": ("guard", 1.0),
    "afraid_of": ("dread", 1.0),
    "looks_up_to": ("esteem", 1.0),
}


def tie_strength(quantities, label):
    """How strongly the numbers say this label, or 0.0 if they do not."""
    source = _TIE_SOURCE.get(str(label))
    if source is None:
        return 0.0
    key, sign = source
    return max(0.0, sign * float((quantities or {}).get(key) or 0.0))


def derive_tie(quantities, familiar, held=None, at_hours=0.0):
    """The label this head holds, given the numbers and the label it had.

    THREE RULES, and each is a different claim about people:

      * FORMING IS HARDER THAN HOLDING. A label adopts at `TIE_FORM` and
        survives down to `TIE_FORM * TIE_HOLD`. Without the hysteresis a tie
        is a number with a name on it, flickering every time the arithmetic
        crosses a line, and the legible half of this design would be less
        legible than the numbers it summarizes.
      * A BOND NEEDS TIME IN THE SAME ROOM. `close` additionally requires
        `CLOSE_FAMILIARITY`; the other four do not, because you can be afraid
        of a stranger and you cannot be close to one.
      * FORMING TAKES A SEASON, LOSING TAKES AN INSTANT. A label younger than
        `TIE_DWELL_HOURS` is not replaced by another -- except by `at_odds`
        or `afraid_of`, which land the window they land. A rupture that had
        to wait out a dwell is a rupture the state cannot represent, and the
        asymmetry is the point rather than an exemption.
    """
    hold_floor = TIE_FORM * TIE_HOLD
    candidates = []
    for label in _TIE_PRIORITY:
        strength = tie_strength(quantities, label)
        if strength < TIE_FORM:
            continue
        if label == "close" and float(familiar or 0.0) < CLOSE_FAMILIARITY:
            continue
        candidates.append((strength, -_TIE_PRIORITY.index(label), label))
    best = max(candidates)[2] if candidates else ""

    was = str((held or {}).get("tie") or "")
    if was in _TIE_SOURCE and tie_strength(quantities, was) >= hold_floor:
        if not best or best == was:
            return was
        rupture = best in ("at_odds", "afraid_of")
        age = float(at_hours) - float((held or {}).get("since_hours") or 0.0)
        if rupture or age >= TIE_DWELL_HOURS:
            return best
        return was
    return best


def _because(judgment):
    """The evidence ids the holder's OWN stance already cites.

    Copied, never scanned for: these ids are on the same surface the
    quantities came from, so the tie adds no read and cites nothing the head
    did not already have a reason to hold.
    """
    reasons = (judgment or {}).get("reasons") or ()
    return [str(r.get("evidence_id")) for r in reasons
            if isinstance(r, dict) and r.get("evidence_id")][-TIE_REASON_CAP:]


def _tie_row(label, since_hours, judgment):
    return {"tie": str(label), "since_hours": round(float(since_hours), 6),
            "because": _because(judgment)}


def _cap_holder(held, judgments, regard, holder):
    """`TIE_CAP` strongest ties, ranked by what produced them."""
    if len(held) <= TIE_CAP:
        return held
    ranked = sorted(held.items(), key=lambda pair: (
        -tie_strength(
            _quantities((judgments.get(holder) or {}).get(pair[0]),
                        _regard_offset(regard, holder, pair[0])),
            pair[1].get("tie")),
        pair[0]))
    return dict(ranked[:TIE_CAP])


def normalize_ties(stored, *, bodies=None, judgments=None, politics=None,
                   served_beside=None):
    """``holder -> other -> row``, with every row the numbers no longer support
    DELETED rather than merely discouraged.

    THIS IS A VALIDATOR AND NOT A COERCION, and it is the reason a tie cannot
    contradict the axes on ANY path. `normalize_charter` runs on both load and
    save (`charter_runtime.registry_for`/`save_registry`), so this also covers
    an archive import, a checkpoint restore of an older charter shape, a
    hand-edited registry, and a judgment moved by some future writer that
    never calls `update_ties` at all. A rule applied only where rows are
    WRITTEN is inert here -- the same argument `charter_model`'s
    `EXPERIENCE_CAP` comment already makes for its own bound.

    Both FORMATION gates are enforced, not just the survival band. Neither
    input can fall -- `served_beside` only rises and a stored label was
    checked against `CLOSE_FAMILIARITY` when it formed -- so a row this
    deletes is a row that could never have formed legitimately.

    Deletion is instant and has no dwell, deliberately: the dwell is a rule
    about which label REPLACES another, and there is no honest way to hold a
    label whose evidence is gone for another day because it is young.
    """
    bodies = bodies if isinstance(bodies, dict) else None
    judgments = judgments if isinstance(judgments, dict) else {}
    regard = ((politics or {}).get("regard") or {})
    hold_floor = TIE_FORM * TIE_HOLD
    out = {}
    for holder, held in (stored or {}).items():
        if not isinstance(held, dict):
            continue
        holder = str(holder)
        if bodies is not None and holder not in bodies:
            continue
        rows = {}
        for other, raw in held.items():
            other = str(other)
            if other == holder or not isinstance(raw, dict):
                continue
            if bodies is not None and other not in bodies:
                continue
            label = str(raw.get("tie") or "")
            if label not in _TIE_SOURCE:
                continue
            stance = (judgments.get(holder) or {}).get(other)
            quantities = _quantities(
                stance, _regard_offset(regard, holder, other))
            if tie_strength(quantities, label) < hold_floor:
                continue
            if label == "close" and familiarity(
                    served_beside, holder, other) < CLOSE_FAMILIARITY:
                continue
            rows[other] = {
                "tie": label,
                "since_hours": round(float(raw.get("since_hours") or 0.0), 6),
                "because": [str(x) for x in (raw.get("because") or ())
                            if str(x)][-TIE_REASON_CAP:],
            }
        if rows:
            out[holder] = _cap_holder(rows, judgments, regard, holder)
    return out


def update_ties(ties, *, company=None, movements=(), judgments=None,
                politics=None, served_beside=None, at_hours=0.0):
    """Re-derive the ties of the pairs that could have changed. ``(ties, changes)``.

    VISITING ONLY THE DIRTY SET IS COMPLETE HERE, not an approximation, and
    the completeness rests on three properties of code that exists today:

      * `served_beside` only ever RISES (`charter_run` increments it and
        nothing decrements it), so familiarity cannot fall out from under a
        `close`;
      * judgments never DECAY (`update_judgments_from_minds` only adds), so a
        stance that moved appears in `movements` and a stance that did not is
        exactly where it was;
      * regard's weight is `TIE_WEIGHTS["regard"] = 0.15`, below `TIE_FORM`,
        so a pair whose regard moved but who shared no place and moved no
        judgment cannot have crossed a threshold on regard alone.

    NONE OF THE THREE IS ENFORCED ANYWHERE. If a judgment-decay feature lands
    later, unvisited pairs go genuinely stale and this walk has to become a
    full sweep or gain a decay-driven dirty set of its own.

    The holder gate -- a body with neither a judgment nor an existing tie is
    skipped BEFORE its co-presence is walked -- is what keeps this O(bodies)
    per window while the judgment network is empty, which is what a healthy
    institution is. Measured on `twin_towns(40)`: 131 directed co-presence
    pair-visits per window, 143,360 over a simulated year, and a healthy year
    visits none of them because nobody holds a stance.
    """
    judgments = judgments if isinstance(judgments, dict) else {}
    regard = ((politics or {}).get("regard") or {})
    out = {str(h): {str(o): dict(r) for o, r in held.items()
                    if isinstance(r, dict)}
           for h, held in (ties or {}).items() if isinstance(held, dict)}

    dirty = set()
    for _place, folk in sorted((company or {}).items()):
        folk = sorted(str(one) for one in folk)
        for one in folk:
            if one not in judgments and one not in out:
                continue
            for other in folk:
                if other != one:
                    dirty.add((one, other))
    for row in movements or ():
        if not isinstance(row, dict):
            continue
        holder, subject = str(row.get("holder") or ""), str(
            row.get("subject") or "")
        if holder and subject and holder != subject:
            dirty.add((holder, subject))

    changes = []
    touched = set()
    for holder, other in sorted(dirty):
        stance = (judgments.get(holder) or {}).get(other)
        held = (out.get(holder) or {}).get(other)
        if stance is None and held is None:
            continue
        label = derive_tie(
            _quantities(stance, _regard_offset(regard, holder, other)),
            familiarity(served_beside, holder, other), held, at_hours)
        was = str((held or {}).get("tie") or "")
        if label == was:
            continue
        if label:
            out.setdefault(holder, {})[other] = _tie_row(
                label, at_hours, stance)
        else:
            out.get(holder, {}).pop(other, None)
            if not out.get(holder, True):
                out.pop(holder, None)
        touched.add(holder)
        changes.append({"holder": holder, "other": other, "tie": label,
                        "was": was})
    for holder in sorted(touched):
        if holder in out:
            out[holder] = _cap_holder(out[holder], judgments, regard, holder)
    return out, changes


def tie_of(ties, holder, other, *, served_beside=None):
    """The one label this head holds about that one, or ``""``.

    THE ONLY READER. `familiar` is derived here and the signed labels are
    stored, which is two code paths for one concept -- so every surface goes
    through this function and none of them looks in `charter["ties"]`, or one
    of them shows `close` where another shows `familiar` for the same pair.
    """
    holder, other = str(holder), str(other)
    row = ((ties or {}).get(holder) or {}).get(other)
    label = str((row or {}).get("tie") or "")
    if label in _TIE_SOURCE:
        return label
    shared = int(((served_beside or {}).get(holder) or {}).get(other) or 0)
    return "familiar" if shared >= FAMILIAR_FLOOR else ""


def tie_view(ties, holder, *, subjects=(), served_beside=None, cap=4):
    """Bounded ``{other, tie, since_hours}`` rows for one head's own ties.

    One head's OWN view outward and nothing about how it is held: there is no
    reciprocity field here and there must not be one, because "they hold me
    close" is the other head's interior.
    """
    holder = str(holder)
    wanted = {str(s) for s in subjects if str(s)}
    stored = (ties or {}).get(holder) or {}
    pool = set(stored) | {
        str(other) for other, shared in (
            (served_beside or {}).get(holder) or {}).items()
        if int(shared or 0) >= FAMILIAR_FLOOR}
    rows = []
    for other in sorted(pool):
        if other == holder or (wanted and other not in wanted):
            continue
        label = tie_of(ties, holder, other, served_beside=served_beside)
        if not label:
            continue
        rows.append({"other": other, "tie": label,
                     "since_hours": round(float(
                         (stored.get(other) or {}).get("since_hours") or 0.0),
                         6)})
    # Signed before derived: a label somebody's conduct earned outranks the
    # floor label a tally produced.
    rows.sort(key=lambda row: (row["tie"] == "familiar", row["other"]))
    return rows[:max(0, int(cap))]


__all__ = [
    "CLOSE_FAMILIARITY", "DEFAULT_SIGNALS", "FAMILIAR_FLOOR", "JUDGMENT_AXES",
    "TIE_CAP", "TIE_DWELL_HOURS", "TIE_FORM", "TIE_HOLD", "TIE_LABELS",
    "TIE_SATURATION", "TIE_WEIGHTS", "derive_tie", "familiarity",
    "judgment_of", "judgment_view", "normalize_judgments", "normalize_ties",
    "normalize_social_norms", "tie_of", "tie_strength", "tie_view",
    "update_judgments_from_minds", "update_ties",
]
