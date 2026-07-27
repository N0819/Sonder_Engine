"""Deterministic live psychology beyond mood.

The character model proposes appraisals, beliefs, and learned associations.
This module owns their bounded persistence. It never chooses an action and
never receives another character's private state.
"""

from __future__ import annotations


def _float(value, default=0.0):
    try:
        result = float(value)
    except (TypeError, ValueError):
        result = default
    return default if result != result else result


# Sustained-drive integration. The gain is per psych unit of stimulus, the
# half-life is six times the pain/pleasure level's so charge outlives the beat
# that caused it, and saturation is the point at which the state says the drive
# is demanding resolution rather than merely present.
_CHARGE_GAIN = 0.18
_CHARGE_HALF_LIFE = 12.0
_CHARGE_SATURATION = 0.85


def _clamp(value, low=0.0, high=1.0, default=0.0):
    return max(low, min(high, _float(value, default)))


def elapsed_psych_units(previous_seconds, current_seconds, fallback_turns=1):
    """Use simulation time when it advanced, otherwise preserve turn behavior.

    One unit is one minute. Explicit multi-hour jumps therefore relax transient
    state much further than a three-second beat, while stories that do not use
    the simulation clock retain the established one-unit-per-turn cadence.
    """
    try:
        previous = float(previous_seconds)
        current = float(current_seconds)
    except (TypeError, ValueError):
        return max(0.0, _float(fallback_turns, 1.0))
    if current > previous:
        return max(0.001, (current - previous) / 60.0)
    return max(0.0, _float(fallback_turns, 1.0))


def resolve_hedonic(previous, appraisal, interoception, body_state,
                    elapsed_units, released=False):
    """Resolve transient pain/pleasure from this beat's grounded appraisal,
    plus the sustained charge those levels leave behind.

    The proposal must carry a concrete `why`; otherwise non-zero values are
    ignored. Survival vitals may add a pain floor, but are never required.
    Pain and pleasure are independent because real mixed states can contain
    both.

    `pain`/`pleasure` are LEVELS: peak-held and fast-decaying, they say what
    the body registers right now. A level alone cannot represent a stimulus
    that has been building for many beats -- once it clamps at the ceiling,
    beat twelve is indistinguishable from beat one, so nothing in the state
    ever says "this has gone on and has to go somewhere". `charge` is the
    slow integral of that unresolved drive. It only ever discharges when the
    character declares the resolution (`released`), because that resolution is
    theirs to have; the runtime owns how it accumulates, not whether it ends.
    """
    previous = previous if isinstance(previous, dict) else {}
    appraisal = appraisal if isinstance(appraisal, dict) else {}
    interoception = interoception if isinstance(interoception, dict) else {}
    body_state = body_state if isinstance(body_state, dict) else {}
    somatic = appraisal.get("somatic_impact")
    somatic = somatic if isinstance(somatic, dict) else {}
    why = str(somatic.get("why") or "").strip()

    proposed_pain = _clamp(somatic.get("pain")) if why else 0.0
    proposed_pleasure = _clamp(somatic.get("pleasure")) if why else 0.0
    pain_sensitivity = _clamp(interoception.get("pain_sensitivity"), default=0.5)
    pleasure_sensitivity = _clamp(
        interoception.get("pleasure_sensitivity"), default=0.5)
    proposed_pain = _clamp(proposed_pain * (0.5 + pain_sensitivity))
    proposed_pleasure = _clamp(
        proposed_pleasure * (0.5 + pleasure_sensitivity))

    injury = _clamp(body_state.get("injury"))
    air = _clamp(body_state.get("air"), default=1.0)
    proposed_pain = max(proposed_pain, injury * 0.8, (1.0 - air) * 0.75)

    elapsed = max(0.0, _float(elapsed_units))
    decay = 0.5 ** (elapsed / 2.0) if elapsed else 1.0
    old_pain = _clamp(previous.get("pain"))
    old_pleasure = _clamp(previous.get("pleasure"))
    pain = max(old_pain * decay, proposed_pain)
    pleasure = max(old_pleasure * decay, proposed_pleasure)
    source = why if (proposed_pain or proposed_pleasure) else str(
        previous.get("source") or "")
    if pain < 0.02 and pleasure < 0.02:
        source = ""

    old_charge = _clamp(previous.get("charge"))
    if released:
        charge = 0.0
    else:
        charge_decay = 0.5 ** (elapsed / _CHARGE_HALF_LIFE) if elapsed else 1.0
        # Pain drives less accumulation than pleasure at equal level: a body
        # under sustained pain escalates through stress, which resolve_stress
        # already models, not through a drive waiting on release.
        drive = max(proposed_pleasure, proposed_pain * 0.5)
        charge = _clamp(old_charge * charge_decay
                        + drive * _CHARGE_GAIN * min(max(elapsed, 1.0), 3.0))
    return {
        "pain": round(_clamp(pain), 4),
        "pleasure": round(_clamp(pleasure), 4),
        "source": source[:300],
        "charge": round(charge, 4),
        "saturated": charge >= _CHARGE_SATURATION,
    }


def resolve_stress(previous, appraisal, profile, hedonic, elapsed_units,
                   proposed_mode=""):
    """Resolve acute activation and slower cumulative load.

    Stress biases the next deliberation but does not select behavior. Inputs are
    appraisal dimensions the character authored from its permitted current
    observations plus its own hedonic state.

    Activation has two independent sources, and collapsing them was wrong:
    STRAIN (threat, novelty, low control, pain) is aversive and accrues
    cumulative load, while DRIVE (sustained pleasure and its unresolved charge)
    is activating without being distressing. Subtracting pleasure from a single
    combined figure -- as this did -- made a body at the ceiling of a powerful
    stimulus read as perfectly composed, activation and load both arithmetically
    zero. Pleasure still damps the accumulation of chronic load; it no longer
    damps the acute arousal of the moment. `overloaded` and `load` remain
    strain-only, because a demanding drive is not a coping failure.
    """
    previous = previous if isinstance(previous, dict) else {}
    appraisal = appraisal if isinstance(appraisal, dict) else {}
    profile = profile if isinstance(profile, dict) else {}
    hedonic = hedonic if isinstance(hedonic, dict) else {}

    reactivity = _clamp(profile.get("baseline_reactivity"), default=0.5)
    recovery = _clamp(profile.get("recovery_rate"), default=0.5)
    threshold = _clamp(profile.get("overload_threshold"), default=0.8)
    novelty = _clamp(appraisal.get("novelty"))
    controllability = _clamp(appraisal.get("controllability"), default=0.5)
    coping = _clamp(appraisal.get("coping_potential"), default=0.5)
    norm = max(
        0.0,
        -_clamp(appraisal.get("norm_compatibility"), -1.0, 1.0, 0.0),
    )
    pain = _clamp(hedonic.get("pain"))
    pleasure = _clamp(hedonic.get("pleasure"))

    impacts = appraisal.get("goal_impacts") or []
    threat = 0.0
    for impact in impacts:
        if not isinstance(impact, dict):
            continue
        signed = _clamp(impact.get("impact"), -1.0, 1.0, 0.0)
        certainty = _clamp(impact.get("certainty"), default=0.5)
        if signed < 0:
            threat = max(threat, abs(signed) * certainty)

    charge = _clamp(hedonic.get("charge"))

    strain_target = _clamp(
        reactivity * (
            threat * 0.55 + novelty * 0.15
            + (1.0 - controllability) * 0.15
            + (1.0 - coping) * 0.15
            + norm * 0.1
        )
        + pain * 0.45
    )
    drive = _clamp(pleasure * 0.3 + charge * 0.35)
    elapsed = max(0.0, _float(elapsed_units))
    half_life = 2.0 + (1.0 - recovery) * 6.0
    decay = 0.5 ** (elapsed / half_life) if elapsed else 1.0
    # `strain` is peak-held separately from `activation` so last beat's drive
    # is never re-read as this beat's distress. Legacy states carry no strain
    # key; their activation is the closest thing to it.
    old_strain = _clamp(previous.get(
        "strain", previous.get("activation")))
    old_load = _clamp(previous.get("load"))
    strain = max(old_strain * decay, strain_target)
    activation = _clamp(strain + drive)
    load_decay = 0.5 ** (elapsed / 60.0) if elapsed else 1.0
    load = _clamp(old_load * load_decay
                  + max(0.0, strain - pleasure * 0.15) * 0.08)
    mode = str(proposed_mode or previous.get("coping_mode") or "")
    return {
        "activation": round(activation, 4),
        "strain": round(strain, 4),
        "load": round(load, 4),
        "coping_mode": mode[:120],
        "overloaded": max(strain, load) >= threshold,
    }


def _authored_beliefs(psychology):
    self_model = (psychology or {}).get("self_model") or {}
    return [
        dict(item) for item in (self_model.get("beliefs") or [])
        if isinstance(item, dict) and str(item.get("belief") or "").strip()
    ]


def apply_belief_updates(existing, psychology, updates, turn_idx, clock_seconds):
    """Merge bounded self/world belief revisions with protected-belief inertia."""
    result = [
        dict(item) for item in (existing or [])
        if isinstance(item, dict) and str(item.get("belief") or "").strip()
    ]
    by_text = {str(item["belief"]).strip().casefold(): item for item in result}
    for authored in _authored_beliefs(psychology):
        key = str(authored.get("belief") or "").strip().casefold()
        if key and key not in by_text:
            item = {
                **authored,
                "authored": True,
                "last_updated_turn": 0,
                "last_updated_seconds": 0.0,
            }
            result.append(item)
            by_text[key] = item

    for update in updates or []:
        if not isinstance(update, dict):
            continue
        text = str(update.get("belief") or "").strip()
        evidence = update.get("evidence") or []
        if not text or not evidence:
            continue
        key = text.casefold()
        item = by_text.get(key)
        operation = str(update.get("operation") or "reinforce").casefold()
        confidence = _clamp(update.get("confidence"), default=0.5)
        if item is None:
            item = {
                "belief": text,
                "confidence": confidence,
                "protected": False,
                "emotional_charge": _clamp(
                    update.get("emotional_charge"), -1.0, 1.0),
            }
            result.append(item)
            by_text[key] = item
        else:
            old = _clamp(item.get("confidence"), default=0.5)
            if operation in ("weaken", "contradict", "revise"):
                step = 0.05 if item.get("protected") else 0.15
                item["confidence"] = max(0.0, old - step * confidence)
            else:
                item["confidence"] = old + (confidence - old) * 0.2
            item["emotional_charge"] = _clamp(
                update.get("emotional_charge", item.get("emotional_charge")),
                -1.0, 1.0,
            )
        item["last_updated_turn"] = int(turn_idx)
        item["last_updated_seconds"] = _float(clock_seconds)
        item["last_evidence"] = [
            dict(ev) for ev in evidence if isinstance(ev, dict)
        ][-3:]
    return result[-20:]


def apply_association_updates(existing, psychology, updates, turn_idx,
                              clock_seconds):
    """Reinforce or extinguish bounded cue-response associations."""
    authored = (((psychology or {}).get("learning") or {}).get("associations")
                or [])
    result = [
        dict(item) for item in [*(authored or []), *(existing or [])]
        if isinstance(item, dict) and str(item.get("cue") or "").strip()
    ]
    deduped = {}
    for item in result:
        deduped[str(item.get("cue")).strip().casefold()] = item
    result = list(deduped.values())

    for update in updates or []:
        if not isinstance(update, dict) or not (update.get("evidence") or []):
            continue
        cue = str(update.get("cue") or "").strip()
        if not cue:
            continue
        key = cue.casefold()
        item = deduped.get(key)
        if item is None:
            item = {
                "cue": cue,
                "appraisal_bias": str(update.get("appraisal_bias") or ""),
                "response_tendency": str(update.get("response_tendency") or ""),
                "strength": 0.0,
                "generalization_tags": [],
            }
            result.append(item)
            deduped[key] = item
        amount = _clamp(update.get("amount"), 0.0, 0.25, 0.1)
        operation = str(update.get("operation") or "reinforce").casefold()
        old = _clamp(item.get("strength"), default=0.5)
        item["strength"] = _clamp(
            old - amount if operation in ("extinguish", "weaken") else old + amount)
        if update.get("appraisal_bias"):
            item["appraisal_bias"] = str(update["appraisal_bias"])
        if update.get("response_tendency"):
            item["response_tendency"] = str(update["response_tendency"])
        item["last_updated_turn"] = int(turn_idx)
        item["last_updated_seconds"] = _float(clock_seconds)
    return result[-20:]
