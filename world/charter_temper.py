"""Temperament: the stable dispositions a body brings to what happens to it.

``docs/design/DESIGN_INSTITUTIONS_AND_UPKEEP.md`` §4. Personality at the
background tier is NOT a new vocabulary. It is exactly the five numbers the
character tier already reads and nothing else:

  * ``pain_sensitivity`` / ``pleasure_sensitivity`` — what
    ``mind/psychology_runtime.resolve_hedonic`` takes as ``interoception``,
    and what a card stores under ``embodiment.interoception``.
  * ``baseline_reactivity`` / ``recovery_rate`` / ``overload_threshold`` —
    what ``resolve_stress`` takes as ``profile``, and what a card stores
    under ``psychology.stress_profile``.

That identity is the whole design. A promoted body's temperament is COPIED
onto its card, not translated into it, so there is no second personality
model to keep in step with the first — the failure the mood experiment
(`charter_needs.mood`, measured r = 0.994 against `pressure`) exists to warn
against. Two bodies with the same week behind them and different numbers here
feel that week differently, and the one the institution eventually meets as a
character is the one its background life actually produced.

DERIVED, NOT AUTHORED, BY DEFAULT. Five hundred crew times five traits is
2,500 numbers nobody will read, and rates nobody reads are the authored
content this repo has measured failing silently. So a body's temperament is a
pure function of its key — recomputed on demand, stored nowhere — and an
author writes one only when a particular body should differ. The derivation
uses ``zlib.crc32`` rather than ``hash()`` because Python salts string hashes
per process: a checkpoint restore is a different process, and a temperament
that changed across restarts would not be a disposition at all.
"""

from __future__ import annotations

import zlib

#: The five traits, their card defaults, and the band each is held inside.
#: The bands are deliberately narrower than [0, 1]: a zero sensitivity is a
#: body that cannot be hurt and a zero recovery is one that cannot calm down,
#: and neither is a temperament — both are authoring mistakes this module
#: refuses to represent silently.
TRAITS = {
    "pain_sensitivity": (0.5, 0.15, 0.85),
    "pleasure_sensitivity": (0.5, 0.15, 0.85),
    "baseline_reactivity": (0.5, 0.15, 0.85),
    "recovery_rate": (0.5, 0.15, 0.85),
    "overload_threshold": (0.8, 0.55, 0.95),
}

#: How far from the default a derived trait may sit. Wide enough that the
#: reactive hand and the steady one respond visibly differently to the same
#: failure; narrow enough that nobody derived is outside what a card author
#: could plausibly have written.
SPREAD = 0.18


def _lane(body_key, trait):
    """A stable value in [-1.0, 1.0] for one body's one trait.

    Keyed on the body alone, deliberately: identity is not per-institution,
    so the same name shows the same disposition wherever it turns up, and a
    replay in a fresh process shows it too.
    """
    digest = zlib.crc32(f"{body_key}|{trait}".encode("utf-8"))
    return (digest % 20001) / 10000.0 - 1.0


def _held(value, trait):
    default, low, high = TRAITS[trait]
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    if value != value:  # NaN
        return default
    return max(low, min(high, value))


def derived_temperament(body_key):
    """The temperament a body has when nobody authored one."""
    out = {}
    for trait, (default, low, high) in TRAITS.items():
        out[trait] = round(
            max(low, min(high, default + SPREAD * _lane(str(body_key),
                                                        trait))), 4)
    return out


def normalize_temperament(stored):
    """An authored temperament, clamped into band, unknown keys dropped.

    Partial on purpose: an author who writes one trait gets the derived
    values for the rest, so a sheet saying only "flinches easily" does not
    silently zero four dispositions it never mentioned.
    """
    stored = stored if isinstance(stored, dict) else {}
    return {trait: round(_held(stored[trait], trait), 4)
            for trait in TRAITS if trait in stored}


def temperament_of(body):
    """The five numbers this body responds to the world with.

    Authored traits override derived ones per key; everything is recomputed
    rather than stored, so an unauthored population costs nothing to hold.
    """
    body = body if isinstance(body, dict) else {}
    out = derived_temperament(str(body.get("key") or ""))
    out.update(normalize_temperament(body.get("temperament")))
    return out


def interoception_of(temperament):
    """The slice ``resolve_hedonic`` reads, in its own vocabulary."""
    return {
        "pain_sensitivity": temperament["pain_sensitivity"],
        "pleasure_sensitivity": temperament["pleasure_sensitivity"],
    }


def stress_profile_of(temperament):
    """The slice ``resolve_stress`` reads, in its own vocabulary."""
    return {
        "baseline_reactivity": temperament["baseline_reactivity"],
        "recovery_rate": temperament["recovery_rate"],
        "overload_threshold": temperament["overload_threshold"],
    }


def temperament_warnings(body_key, stored):
    """What an authored temperament silently loses. Validation from day one.

    Every rate an author writes is content nobody will read back, so the
    misspelled key and the out-of-band value must be said at write time —
    the psychology lesson (`character_card_warnings`, nine surfaces) applied
    before the failure instead of after it.
    """
    warnings = []
    if stored is None:
        return warnings
    if not isinstance(stored, dict):
        return [f"{body_key}: temperament must be a mapping of trait to "
                f"number; got {type(stored).__name__} and derived values "
                "will be used instead"]
    for key, value in stored.items():
        if key not in TRAITS:
            known = ", ".join(sorted(TRAITS))
            warnings.append(
                f"{body_key}: unknown temperament trait {key!r} is dropped "
                f"(known: {known})")
            continue
        default, low, high = TRAITS[key]
        try:
            number = float(value)
        except (TypeError, ValueError):
            warnings.append(
                f"{body_key}: temperament {key!r} is not a number "
                f"({value!r}) and falls back to {default}")
            continue
        if number != number:
            warnings.append(
                f"{body_key}: temperament {key!r} is not a number "
                f"({value!r}) and falls back to {default}")
        elif not low <= number <= high:
            warnings.append(
                f"{body_key}: temperament {key!r}={number} is outside "
                f"[{low}, {high}] and is clamped")
    return warnings
