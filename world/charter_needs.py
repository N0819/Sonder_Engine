"""Needs, and why a body can stop being able to stand a post.

``docs/design/DESIGN_INSTITUTIONS_AND_UPKEEP.md``. A NEED IS AN UPKEEP WHOSE
PLACE IS A BODY. Fatigue drifts while you stand watches and is serviced by
rest; hunger drifts and is serviced by whatever the institution's supply chain
ends in; injury drifts only after an incident and is serviced by a medical
post. All of that is ``{level, floor, drift_per_hour, service_per_hour,
depends_on}`` — the five fields upkeeps already have, pointed at a person.

No new primitive, and that is the argument for doing it this way rather than
bolting on a needs system: the same arithmetic, the same events, the same
replay, and a supply chain that already knows how to starve now has somebody
at the end of it to starve.

WHAT THIS BUYS, and it is the largest single change to the model's fidelity:
``available`` stops being an authored boolean and becomes a CONSEQUENCE. A
body whose fatigue or health is under its floor cannot stand a post. That
closes the loop the simulation has been missing —

    a chain fails -> the need it fed goes unserviced -> bodies go unavailable
    -> posts go unfilled -> more chains fail

— which is a famine spiral the engine produces without anybody scripting one,
and a recovery it produces just as freely once the mill turns again.

WHAT THIS IS NOT. It is not an emotion model. Feelings belong to
``mind/psychology_runtime.py``, which already owns bounded hedonic tone,
stress, beliefs and learned associations, and whose ``resolve_hedonic`` takes
``body_state`` and ``interoception`` as INPUTS. This module produces exactly
those inputs. The background tier makes the pressure; the character tier makes
the meaning; a second affect model here would leave a promoted body holding
two incompatible interiors.
"""

from __future__ import annotations

from .charter_model import _clamp

#: Needs every body has unless a role says otherwise. Authored PER ROLE rather
#: than per body: a thousand townsfolk with four needs each is four thousand
#: numbers nobody will ever read, and rates that nobody reads are the authored
#: content this project has measured failing silently.
DEFAULT_NEEDS = {
    "rest": {"floor": 0.15, "drift_per_hour": 0.030,
             "service_per_hour": 0.110},
    "sustenance": {"floor": 0.10, "drift_per_hour": 0.012,
                   "service_per_hour": 0.090},
    "health": {"floor": 0.20, "drift_per_hour": 0.000,
               "service_per_hour": 0.040},
}

#: Standing a post costs rest at this multiple of the idle rate. Work is what
#: makes a short-handed institution eat its own remaining hands: fewer bodies
#: means more watches each, which means they fatigue faster, which means fewer
#: bodies. The spiral is in this one number.
ON_WATCH_STRAIN = 2.5

#: How far above its floor a need must climb before a body counts as able
#: again. WITHOUT HYSTERESIS THE WHOLE MODEL FLAPS: a body exhausted on watch
#: is stood down, recovers past the floor in a single window, is posted again
#: immediately, and exhausts again — two events per cycle, forever. Measured
#: on the twin-town fixture before this existed: 666 events in twenty days
#: that the log described as quiet, which is the same "storage grows with
#: time" failure this package has now made three times in three different
#: places.
#:
#: It is also the physical truth. Nobody stops being exhausted at the instant
#: they cross back over the line, and an institution that put them straight
#: back on watch would be one nobody would work for.
RECOVERY_MARGIN = 0.25


def normalize_need(key, entry):
    entry = entry if isinstance(entry, dict) else {}
    default = DEFAULT_NEEDS.get(str(key), {})
    return {
        "key": str(key),
        "level": _clamp(entry.get("level", 1.0)),
        "floor": _clamp(entry.get("floor", default.get("floor", 0.15))),
        "drift_per_hour": max(0.0, float(
            entry.get("drift_per_hour", default.get("drift_per_hour", 0.0)))),
        "service_per_hour": max(0.0, float(
            entry.get("service_per_hour",
                      default.get("service_per_hour", 0.0)))),
        # The upkeep this need draws on. `sustenance` pointing at the end of a
        # supply chain is what gives the chain a consumer.
        "fed_by": str(entry.get("fed_by") or ""),
    }


def seed_needs(bodies, template=None):
    """Every body at full, from a per-role template or the defaults."""
    template = template or DEFAULT_NEEDS
    return {
        key: {name: normalize_need(name, dict(spec))
              for name, spec in template.items()}
        for key in (bodies or {})
    }


def advance_needs(needs, bodies, watch, upkeeps, hours, strain=None,
                  toll=0.0):
    """One window of living. Returns ``(needs, newly_unable, recovered)``.

    A body on watch spends rest faster and eats no better for it. A need whose
    ``fed_by`` upkeep has failed is serviced at whatever that upkeep's level
    permits — the same weakest-link rule the supply chain uses, because it is
    the same question one layer down.

    ``strain`` is ``{body: 0..1}`` from last window's felt state
    (`charter_feel.strain_of`), and ``toll`` is what full strain multiplies
    the rest drift by, on watch and off. This is the ONLY door feeling has
    back into the institution: a shaken body rests badly, worn rest crosses
    its floor, and the existing `body_unable` path does the rest — no second
    stand-down channel and no term on the planner's reluctance axis, which is
    where the mood experiment measured a duplicate. At ``toll=0.0`` this
    function is bit-for-bit what it was before the parameters existed.
    """
    hours = max(0.0, float(hours))
    on_watch = set((watch or {}).values())
    strain = strain or {}
    toll = max(0.0, float(toll))
    out, newly_unable, recovered = {}, [], []

    for key, held in (needs or {}).items():
        body = (bodies or {}).get(key)
        if body is None:
            continue
        was_able = bool(body.get("available", True))
        worn = 1.0 + toll * max(0.0, min(1.0, float(strain.get(key, 0.0)))) \
            if toll else 1.0
        after = {}
        for name, need in held.items():
            cost = ON_WATCH_STRAIN if (key in on_watch and name == "rest") \
                else 1.0
            if name == "rest":
                cost *= worn
            level = float(need["level"])
            level -= float(need["drift_per_hour"]) * cost * hours
            supply = 1.0
            if need["fed_by"]:
                supply = float(
                    (upkeeps or {}).get(need["fed_by"], {}).get("level", 0.0))
            # Resting is what an off-watch body does; a body on watch is not
            # recovering the thing the watch is spending.
            if key not in on_watch or name != "rest":
                level += float(need["service_per_hour"]) * hours * supply
            record = dict(need)
            record["level"] = _clamp(level)
            after[name] = record
        out[key] = after
        is_able = able(after, was_able=was_able)
        if was_able and not is_able:
            newly_unable.append(key)
        elif is_able and not was_able and body.get("stood_down"):
            # ONLY A BODY NEEDS PUT DOWN MAY BE PICKED UP BY NEEDS. Somebody
            # absent for a reason this module knows nothing about -- injured
            # in an incident, transferred, authored away -- must not be
            # returned to duty because they happen to be rested. Recovering
            # them here would let one subsystem quietly overturn another's
            # decision, which is the failure this whole package is arranged
            # to avoid.
            recovered.append(key)
    return out, sorted(newly_unable), sorted(recovered)


def able(held, was_able=True):
    """Can a body with these needs stand a post at all.

    Hysteresis, not a threshold: falling below the floor makes a body unable,
    and it takes climbing back to ``floor + RECOVERY_MARGIN`` to make it able
    again. Pass ``was_able=False`` for a body currently stood down.
    """
    margin = 0.0 if was_able else RECOVERY_MARGIN
    for need in (held or {}).values():
        if float(need["level"]) < float(need["floor"]) + margin:
            return False
    return True


def pressure(held):
    """How hard this body is being pressed, from 0.0 rested to ~1.0 spent.

    CONTINUOUS, AND THAT IS THE WHOLE POINT. `unmet` measures a breach, so it
    is zero right up until a body collapses — which meant the planner had no
    way to prefer the fresher of two hands and no watch ever rotated. Bodies
    were posted until they fell over, stood down, and posted again.

    Measured on the twin towns before this existed: every patrol burned
    through its rest inside twelve hours, the road went unheld, and both
    towns starved — 240 of 240 bodies down, from a fixture where nothing had
    gone wrong. A watch bill that cannot rotate is not short-handed, it is
    broken.

    Reluctance built on this rotates for free: the planner already spends the
    least reluctant body first, so the freshest hand takes the watch and the
    tired one rests without anybody scheduling it.
    """
    worst = 0.0
    for need in (held or {}).values():
        spent = 1.0 - float(need["level"])
        if spent > worst:
            worst = spent
    return round(worst, 6)


def unmet(held):
    """How far below its floor the worst need is. 0.0 when all are met.

    The pressure scalar, and deliberately a single number: it is handed to
    politics as reluctance and, on promotion, to `psychology_runtime` as body
    state. A vector here would invite somebody to interpret its components,
    which is the job of the layer that owns meaning.
    """
    worst = 0.0
    for need in (held or {}).values():
        gap = float(need["floor"]) - float(need["level"])
        if gap > worst:
            worst = gap
    return round(worst, 6)


def mood(held, blamed=0, regard_of_others=(), weights=None):
    """A single scalar for how a background body is doing. NOT WIRED IN.

    An experiment, deliberately kept out of the planner and off by default,
    because the case against it is real: `mind/psychology_runtime.py` already
    owns hedonic tone and stress for characters, and a second affect model
    would leave a promoted body holding two incompatible interiors. The case
    FOR measuring it anyway is equally real — "do not build it" and "do not
    find out whether it matters" are different claims, and this repo settles
    that kind of question with a number.

    So: computed on request, reported by `charter_log`, read by nothing.
    Three inputs the background tier already has, and no new authored rates:

      * how spent the body is (`pressure`)
      * how often the institution has blamed it
      * what the people who have an opinion of it think

    If a later measurement shows mood-weighted planning produces materially
    different institutions, it earns its way in. If it does not, this function
    is the evidence for leaving it out, and that is worth more than the
    feature would have been.
    """
    weights = weights or {"spent": 0.6, "blame": 0.25, "regard": 0.15}
    spent = pressure(held)
    blame_term = min(1.0, float(blamed) / 3.0)
    opinions = [float(w) for w in regard_of_others]
    regard_term = 0.0
    if opinions:
        # NEUTRAL_REGARD is 1.0; below it is disapproval.
        regard_term = max(0.0, 1.0 - (sum(opinions) / len(opinions)))
    return round(min(1.0, (
        weights["spent"] * spent
        + weights["blame"] * blame_term
        + weights["regard"] * regard_term)), 6)


#: Which vital each default need speaks as, in `world/survival.py`'s
#: vocabulary. `health` is the inversion: survival counts injury UP from
#: zero, needs count health DOWN from one.
_VITAL_OF_NEED = {"rest": "stamina", "sustenance": "nourishment"}


def body_state(held):
    """The shape `mind/psychology_runtime.resolve_hedonic` takes as input.

    THE HANDOFF, and the reason this module computes no feelings. A promoted
    body arrives at the character tier with the pressures its background life
    actually produced, and the tier that owns appraisal turns them into tone.

    THE KEYS ARE `world/survival.py`'S VITALS — `stamina`, `nourishment`,
    `injury` — because those are the keys `resolve_hedonic` actually reads.
    The first version of this function returned `{needs, unmet, able}` and
    claimed the same handoff: every key was ignored, the defaults filled in,
    and a starving, exhausted background body would have arrived at the
    character tier reading as perfectly fresh. The same defect class
    `resolve_stress`'s own docstring records for `goal_impacts` — a caller
    and a callee agreeing about a payload's shape and being wrong about it —
    caught here before a promotion path existed to be silently wrong through.
    `needs`/`unmet`/`able` stay for readers that want the detail; the vitals
    are the contract.
    """
    out = {
        "needs": {name: round(float(need["level"]), 4)
                  for name, need in (held or {}).items()},
        "unmet": unmet(held),
        "able": able(held),
    }
    for name, need in (held or {}).items():
        vital = _VITAL_OF_NEED.get(str(name))
        if vital:
            out[vital] = round(float(need["level"]), 4)
        elif str(name) == "health":
            out["injury"] = round(1.0 - float(need["level"]), 4)
    return out
