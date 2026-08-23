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
"""

from __future__ import annotations

from .charter_politics import regard_value


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
    "order_obeyed": {"trust": 0.025, "respect": 0.025},
    "order_refused": {"trust": -0.025, "suspicion": 0.025},
}


def _clamp(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0.0
    return round(max(-1.0, min(1.0, value)), 6)


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
                    delta = float(raw) * weight
                    if not delta:
                        continue
                    before = float(stance.get(axis) or 0.0)
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


__all__ = [
    "DEFAULT_SIGNALS", "JUDGMENT_AXES", "judgment_of", "judgment_view",
    "normalize_judgments", "normalize_social_norms",
    "update_judgments_from_minds",
]
