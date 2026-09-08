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
    # COMPANY (D18, review 2026-09-07). The town that met itself and had
    # nothing further to do: nothing in the model ever pulled a body toward
    # another body, so an institution's whole social life was whatever its
    # watch bill happened to put in one room. This is the same five fields
    # pointed at that, and no new primitive -- it drifts while nobody speaks
    # to you and is serviced by the window's acts you were part of.
    #
    # NOT DUTY-BEARING, and that is the owner's constraint rather than a
    # tuning choice: a body starved of company is in pain and is pulled
    # toward people, but it is never stood down from its post and never
    # weighs on the watch bill. Loneliness does not excuse you from work,
    # and a fourth term silently entering the planner's reluctance axis is
    # exactly the double count `mood` is held out of the bill to avoid.
    # THE THREE NUMBERS, NAMED because the house names every cap, ceiling
    # and rate rather than burying it (D18 rework, 2026-09-08). `floor` 0.12
    # is the highest of the four needs': a body no act names falls under it
    # after about 88 hours and is then pulled by errands, which is what a
    # week of being spoken to by nobody should cost. `drift_per_hour` 0.010
    # is that slope. `service_per_hour` 0.180 restores a floored body fully
    # inside one four-hour window, so ONE conversation answers loneliness
    # where a meal does not answer hunger -- company is cheap to give and
    # slow to lose, which is the shape being modelled.
    "company": {"floor": 0.12, "drift_per_hour": 0.010,
                "service_per_hour": 0.180, "duty_bearing": False},
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
        # WHETHER A BREACH OF THIS FLOOR BEARS ON STANDING A POST. True for
        # every need the institution can be short-handed by; False for one
        # that pulls without disqualifying (D18's `company`). Every reader of
        # it goes through `bears_on_duty`, which states the decision/report
        # line that settles which side any new reader falls on.
        "duty_bearing": bool(entry.get(
            "duty_bearing", default.get("duty_bearing", True))),
    }


def seed_needs(bodies, template=None):
    """Every body at full, from a per-role template or the defaults."""
    template = template or DEFAULT_NEEDS
    return {
        key: {name: normalize_need(name, dict(spec))
              for name, spec in template.items()}
        for key in (bodies or {})
    }


def ensure_needs(needs, bodies, template=None):
    """Give every body the needs the model has, at full, and keep the rest.

    A NEED ADDED TO THE MODEL MUST REACH THE TOWNS ALREADY RUNNING. `company`
    landed after bench.db chat 114's 66 bodies were seeded, and a body with
    no `company` entry feels no pull toward anybody -- the exact silence D18
    was written against, preserved forever in every story that already
    exists. Called once a window from `charter_run.step`, so a stored charter
    picks up a new need on its next window rather than on a migration nobody
    will run.

    It only ADDS, at full level: an authored rate already on a body is the
    author's, and a level already lived is the story's.

    A BODY HOLDING NO NEEDS AT ALL IS LEFT HOLDING NONE, and the distinction
    is the whole safety of doing this at all. "Missing one key" is a charter
    that predates a need; "no needs row" is a caller that chose not to model
    needs for this body -- the `charter_fixtures` charters, and every body a
    promotion has taken out of the institution's hands
    (`tests/test_charter_run.py`: "one window, and it is gone"). Filling the
    second put a full needs model on a crew that had never had one: measured,
    the SHIP fixture's silent simulated week became 69 `body_unable` and 53
    `post_unfilled` events, none of them anything to do with the new need.
    """
    template = template or DEFAULT_NEEDS
    out = dict(needs or {})
    for key in (bodies or {}):
        held = (needs or {}).get(key)
        if not held:
            continue
        held = dict(held)
        for name, spec in template.items():
            if name not in held:
                held[name] = normalize_need(name, dict(spec))
        out[key] = held
    return out


def wants_company(held):
    """Is this body short of people. THE VOCABULARY LIVES HERE, with the
    module that owns the need, so `charter_move.errands` reads a question
    rather than a need name it would have to know about."""
    need = (held or {}).get("company")
    if not isinstance(need, dict):
        return False
    return float(need.get("level", 1.0)) < float(need.get("floor", 0.0))


def _flow_rows(economy):
    for flow in ((economy or {}).get("flows") or {}).values() \
            if isinstance(economy, dict) else ():
        if not isinstance(flow, dict):
            continue
        yield (str(flow.get("good") or ""),
               str(flow.get("kind") or ""),
               str(flow.get("requires_upkeep") or ""),
               max(0.0, float(flow.get("lots_per_hour") or 0.0)))


def feeding_upkeep(upkeeps=None, economy=None, town=None):
    """The upkeep of whoever in town PRODUCES what this institution eats.

    ``None`` when nothing in town produces a good this institution consumes
    -- which is the case the caller must SAY rather than paper over, because
    a town where the bread comes from nowhere is a lore fact to author (A25,
    owner's ruling 2026-09-08). Otherwise ``{upkeep, charter, good, hand}``,
    where ``charter`` is empty for a producer this institution holds itself
    and names another institution when the only producer in town belongs to
    one -- a dependency the per-charter window cannot read, since
    `advance_needs` and `charter_drift.supply_factor` both resolve an upkeep
    key against the charter's OWN upkeeps.

    THE SEARCH IS THE TOWN'S, THE ANSWER IS THE INSTITUTION'S. The first
    derivation looked only at the charter's own flows and asked for a good
    it both produced and consumed; the ruling widened the SEARCH to every
    institution of the town -- the guesthouse's groceries from the farm --
    and widened the CLAUSE not at all. One clause, over the goods this
    institution consumes, most consumed first: whoever in town produces that
    good, preferring a producer this institution holds itself.

    A SECOND CLAUSE WAS TRIED AND IS REFUSED (2026-09-08). Reading the
    upkeep the consuming flow itself requires -- "the last hand the good
    passes through before a person" -- derives a hand for nearly everything,
    and that is the objection rather than the recommendation: measured on
    bench.db chat 114 it fired 66 of 66 times where this clause fires 0 of
    4, so a town whose food demonstrably comes from nowhere would have been
    fed in silence by its own cold room. The ranking is blind to what a good
    IS -- the fishery consumes twice as much block ice as diesel and lands
    fish nobody in town consumes -- and telling ice from bread has no
    structural signal, only a goods word list, which is the thing this repo
    does not build (`CLAUDE.md`: an enumeration is a promise the list can be
    finished, and it never can). So the chain stops where a produced-and-
    consumed link proves it, and `unfed_notice` says so everywhere else.

    ``town`` is ``[(charter_key, upkeeps, economy)]`` for the OTHER
    institutions of the same location; omit it and the search is this one's
    alone.
    """
    upkeeps = upkeeps if isinstance(upkeeps, dict) else {}
    consumed, producers = {}, {}
    for good, kind, upkeep, rate in _flow_rows(economy):
        if not good:
            continue
        if kind == "consume":
            consumed[good] = consumed.get(good, 0.0) + rate
        elif kind == "produce" and upkeep and upkeep in upkeeps:
            producers.setdefault(good, set()).add(("", upkeep))
    for entry in town or ():
        try:
            other_key, other_upkeeps, other_economy = entry
        except (TypeError, ValueError):
            continue
        other_upkeeps = other_upkeeps if isinstance(other_upkeeps, dict) else {}
        for good, kind, upkeep, _rate in _flow_rows(other_economy):
            if kind == "produce" and good and upkeep and upkeep in other_upkeeps:
                producers.setdefault(good, set()).add((str(other_key), upkeep))
    ranked = sorted(consumed, key=lambda good: (-consumed[good], good))
    # A PRODUCER THIS INSTITUTION HOLDS BEFORE ONE IT DOES NOT: the window
    # resolves an upkeep key against its own upkeeps, so a foreign key would
    # read as level 0.0 and starve the town it was meant to feed. The
    # foreign producer is still reported, for the warning.
    for good in ranked:
        own = sorted(upkeep for charter, upkeep in producers.get(good, ())
                     if not charter)
        if own:
            return {"upkeep": own[0], "charter": "", "good": good,
                    "hand": "producer"}
    for good in ranked:
        rows = sorted(producers.get(good, ()))
        if rows:
            return {"upkeep": rows[0][1], "charter": rows[0][0],
                    "good": good, "hand": "producer"}
    return None


def unfed_notice(charter_key, feeder=None):
    """What the author is told when nothing in town feeds this institution.

    ONE STRING, TWO SURFACES: generation says it in `closure.warnings` on the
    day the town is written, and `charter_runtime.registry_warnings` says it
    again every time the registry is read, because an economy edited after
    generation can take the hand away.
    """
    if feeder and feeder.get("charter"):
        return (f"{charter_key}: what its people live on ("
                f"{feeder['good']}) is made in town only by "
                f"{feeder['charter']}'s upkeep {feeder['upkeep']!r}, and a "
                "window resolves an upkeep against its own institution's; "
                "sustenance draws on nothing here. Give this institution a "
                "flow that makes what it eats, or name its "
                "`needs.sustenance.fed_by`")
    return (f"{charter_key}: nothing in town makes what its people live on, "
            "so sustenance is serviced at full supply whatever the stocks "
            "say. Give some institution a flow producing a good this one "
            "consumes, or name its `needs.sustenance.fed_by`")


def needs_template(authored=None, upkeeps=None, economy=None, town=None):
    """The per-charter need template: the defaults, an authored `needs`
    block laid over them, and `fed_by` derived from the town's own
    structure where the author named none.

    NOTHING GENERATED EVER SET `fed_by`. `DEFAULT_NEEDS` has none, the
    generator called `seed_needs(bodies)` with no template, and four
    readers depend on it: the supply factor (`advance_needs`), the
    own-stake appraisal (`charter_feel`), the where-the-bread-is errand
    (`charter_move.errands`) and the post-heals-the-need rule. So every
    town serviced sustenance at supply 1.0 whatever its stocks, and the
    economy had no body at the end of it. Only tests set the field.

    The derivation is structural, not lexical, and the SEARCH IS THE
    TOWN'S (`feeding_upkeep`): `sustenance` draws on the upkeep of whoever
    in town PRODUCES a good this institution consumes, the most-consumed
    such good first. Nothing else counts, and the towns that derive nothing
    are the point rather than a shortfall -- where no produced-and-consumed
    link exists the field stays empty as before, and both `close_plan` and
    `charter_runtime.registry_warnings` say so to the author rather than
    letting the need be serviced at supply 1.0 in silence. An authored
    template (`charters[].needs`) overrides any of it, which is how a need
    with no structural signal -- `health` -- names its infirmary, and how a
    town whose food genuinely arrives from off the map names the hand that
    lands it.
    """
    template = {name: dict(spec) for name, spec in DEFAULT_NEEDS.items()}
    feeder = feeding_upkeep(upkeeps, economy, town)
    if feeder and not feeder["charter"]:
        template.setdefault("sustenance", {})["fed_by"] = feeder["upkeep"]
    for name, spec in (authored.items() if isinstance(authored, dict) else ()):
        if not isinstance(spec, dict):
            continue
        template.setdefault(str(name), {}).update(
            {k: v for k, v in spec.items()
             if k in ("fed_by", "floor", "drift_per_hour",
                      "service_per_hour", "level")})
    return template


def advance_needs(needs, bodies, watch, upkeeps, hours, strain=None,
                  toll=0.0, company=None):
    """One window of living. Returns ``(needs, newly_unable, recovered)``.

    A body on watch spends rest faster and eats no better for it. A need whose
    ``fed_by`` upkeep has failed is serviced at whatever that upkeep's level
    permits — the same weakest-link rule the supply chain uses, because it is
    the same question one layer down.

    ``company`` is ``{body: 0..1}``, how much of the window a body spent in
    somebody's company. It scales the `company` need's service exactly as
    `fed_by`'s upkeep level scales sustenance's, because it is the same
    sentence: a need is serviced by whatever it draws on, at whatever that
    thing actually delivered. A body nobody spoke to draws nothing.

    ITS ONLY PRODUCER WRITES 1.0 OR NOTHING, and the docstring says so
    rather than describing a fraction nothing computes (skeptic's finding,
    2026-09-08). `charter_run` builds it from the deposited `window_acts`,
    and an act row records who did what to whom, not for how long -- so one
    greeting buys a full window's service, and the record contains nothing
    that would honestly say otherwise. The parameter stays a share because
    the arithmetic is the same either way and because the day acts carry a
    duration this becomes true without a caller changing; today read it as
    "was anybody with you at all".

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
            if name == "company":
                supply *= max(0.0, min(1.0, float(
                    (company or {}).get(key, 0.0))))
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

    ONLY A DUTY-BEARING NEED ANSWERS THIS QUESTION. `company` breaches its
    floor and hurts and pulls, and it never stands anybody down: the owner's
    constraint on D18, and the only thing standing between a fourth need and
    a town that empties its posts because nobody spoke to anybody.
    """
    margin = 0.0 if was_able else RECOVERY_MARGIN
    for need in (held or {}).values():
        if not bears_on_duty(need):
            continue
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
        # SPENTNESS IS WHAT A WATCH COSTS, and the bill spends the least
        # reluctant body first (`charter_run`). A need that cannot stand a
        # body down must not quietly re-enter through the same door and
        # decide who gets posted -- which for `company` would mean the
        # lonely are worked less, a rule nobody wrote.
        if not bears_on_duty(need):
            continue
        spent = 1.0 - float(need["level"])
        if spent > worst:
            worst = spent
    return round(worst, 6)


def bears_on_duty(need):
    """Whether a breach of this need's floor is the institution's business.

    THE PREDICATE LIVES IN ONE PLACE because the rule has to be applied in
    several, and a rule spelled out at each door is a rule that will be
    missed at the next one -- it was missed at four of them when `company`
    landed (D18, skeptic 2026-09-08): `charter_practice._afford_tend` and
    `charter_author`'s tend act both chose which need to service by the
    widest gap, and `company`'s floor of 0.12 is the highest of the four, so
    a body stood down by starvation (floor 0.10, level 0.0) was tended for
    its loneliness and stayed down. `charter_run`'s `body_unable` event and
    `charter_feel.window_appraisals`' wake-up were the other two.

    THE LINE IS DECISION VERSUS REPORT. Anything that decides what the
    institution DOES about a body -- post it, stand it down, rank it,
    service it, wake an appraisal for it -- reads only duty-bearing needs.
    Anything that reports what a body is SHORT of -- `unmet`, `body_state`,
    `charter_log.own_state_of` -- counts every need it holds, because
    loneliness is a true thing about a body even where it is none of the
    watch bill's business.
    """
    return bool((need or {}).get("duty_bearing", True))


def worst_need(held):
    """The duty-bearing need furthest under its floor, or ``None``.

    What a carer services (`charter_practice._afford_tend`,
    `charter_author`): the need that put this body down, not the widest gap
    it happens to carry. Ties keep the ledger's own order. The caller checks
    the gap, because "is anybody under a floor at all" and "how much utility
    is it worth" are its questions, not this one's.
    """
    duty = [need for need in (held or {}).values() if bears_on_duty(need)]
    if not duty:
        return None
    return min(duty, key=lambda n: float(n["level"]) - float(n["floor"]))


def unmet(held, duty_only=False):
    """How far below its floor the worst need is. 0.0 when all are met.

    The pressure scalar, and deliberately a single number: it is handed to
    politics as reluctance and, on promotion, to `psychology_runtime` as body
    state. A vector here would invite somebody to interpret its components,
    which is the job of the layer that owns meaning.

    COUNTS EVERY NEED BY DEFAULT, `company` included, because it reports
    what a body is short of and loneliness is something a body is short of.
    ``duty_only`` is for the one reader that is describing an institutional
    decision rather than a body -- `charter_run`'s `body_unable` event,
    which must name the size of the breach that actually stood the body
    down; see `bears_on_duty`.
    """
    worst = 0.0
    for need in (held or {}).values():
        if duty_only and not bears_on_duty(need):
            continue
        gap = float(need["floor"]) - float(need["level"])
        if gap > worst:
            worst = gap
    return round(worst, 6)


def mood(held, blamed=0, regard_of_others=(), weights=None):
    """A single scalar for how a background body is doing. WIRED, AND OFF.

    An experiment, kept out of the planner by a DIAL rather than by an
    absent call, because the case against it is real:
    `mind/psychology_runtime.py` already owns hedonic tone and stress for
    characters, and a second affect model would leave a promoted body
    holding two incompatible interiors. The case FOR measuring it anyway is
    equally real — "do not build it" and "do not find out whether it
    matters" are different claims, and this repo settles that kind of
    question with a number.

    So: computed on request, reported by `charter_log`, and folded into the
    watch bill's reluctance by `charter_run` as `mood_weight * mood(...)` —
    where `mood_weight` ships at **0.0** (`charter_model.normalize_charter`),
    so a shipped run never calls this and is byte-identical to one that
    could not. An arm that raises the dial buys the double-count with the
    disgrace term that `charter_run` states inline and `docs/UNBUILT.md`
    § 1.99a records. (E31, 2026-09-07: this said "NOT WIRED IN … read by
    nothing", which was true until the reluctance fold landed.)

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
