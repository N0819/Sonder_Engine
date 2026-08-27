"""Advancing an institution through time, and the only things it writes down.

``docs/design/DESIGN_INSTITUTIONS_AND_UPKEEP.md`` §6 and §7. This is the
path-dependent half: what can be recomputed from the clock stays in
``charter_drift``, and what BRANCHES is emitted here as an event.

TWO PROPERTIES THIS MODULE EXISTS TO HOLD, both of them testable and both of
them cheap to lose:

  * **EVENTS grow with incident, not with time.** A window in which nothing
    crossed a floor, nothing went unfilled and nothing was restored emits
    ZERO events. A well-run year is a handful of rows; a bad week is a
    hundred. A tick that writes "nothing happened" every window is the thing
    that makes a long story expensive, and it is the easy mistake here.

    THE EVENT LOG, THOUGH, IS NOT THE PEOPLE. This rule was written for the
    institution's incident ledger and then applied to everything, and the
    result was measurable: a healthy 40-body charter emitted zero events
    across a simulated YEAR, and every social source in the module was gated
    on something going wrong -- `tending` opens only when a body is under its
    floor, `greeting` only between people who have not met, `converse` was
    switched off offscreen for cost. So the only thing an institution could
    ever be found to have done was fail, and a year of it promoted a
    character with 17.6 memories against a month's 16.7. "All systems
    nominal" is a REPORT; it is not what happened to these people.

    So autobiographical rows are held to a WEAKER bound than events, and
    deliberately: `ENCOUNTER_ODDS` draws a specific occasion out of the
    ordinary ones a pair share, at a rate slow enough that a body keeps about
    seventy rows per simulated year and `EXPERIENCE_CAP` still holds decades.
    The same year now promotes at 93.8. The institution's ledger stays
    incident-only; the lives inside it do not.
  * **Nothing learns anything.** An event is layer-1 fact in the sense
    ``world/living_world.py`` already uses: it happened, at a place, at an
    hour, before anyone asks. Who comes to know it is a separate, channelled
    question this module does not touch.

Returns events rather than committing them. Wiring these into the existing
consequence-fuse mint is deliberately NOT done here -- the prototype proves the
mechanism first, and a pure function is testable in ways a commit path is not.
"""

from __future__ import annotations

import hashlib

from .charter_drift import advance_level, starving_input, supply_factor
from .charter_model import (EXPERIENCE_CAP, normalize_charter,
                            out_of_band)
from .charter_plan import plan_watch, tended_upkeeps
from .charter_politics import (
    attribute_blame, normalize_politics, regard_map, regard_pair,
    spend_reluctance)
from .charter_roster import decay_roster, observe
from .charter_space import charter_places, reach_map, refresh_reach
from .charter_feel import STRAIN_REST_TOLL, advance_feel, strain_of
from .charter_log import window_note
from .charter_figure import sight_figures
from .charter_mind import cap_minds, decay_minds
from .charter_move import ERRAND_RATE, errands, homecomings, relocate, walk
from .charter_news import (check_reports, decay_news, news_keys_in,
                          witness)
from .charter_practice import (
    COARSE_PRACTICES, close_stale, enact, normalize_practices, opportunities)
from .charter_needs import advance_needs, mood, pressure, unmet
from .charter_talk import converse, report_to_superiors, report_up
from .charter_commitment import advance_commitments
from .charter_decide import advance_decisions, deliver_orders, execute_orders
from .charter_economy import advance_economy
from .charter_social import update_judgments_from_minds, update_ties
from .charter_intervene import apply_due


def _event(kind, at_hours, place, **payload):
    return {"kind": kind, "at_hours": round(float(at_hours), 6),
            "place": str(place or ""), **payload}


#: WHICH ACTS CHANGE WHAT TWO PEOPLE ARE TO EACH OTHER, and the event each
#: one is. `aid_given` was declared witnessable ("aid visibly given"), given
#: judgment weights and given narration phrasing, and NOTHING in the
#: repository emitted it -- three quarters of a social event with no producer.
#: `accusation` and `apology` were in exactly the same state, with weights at
#: `charter_social.DEFAULT_SIGNALS` and no producer, while `accuse` and
#: `reconcile` were already changing regard and closing quarrels in silence:
#: nobody else in the room ever learned either had happened.
#:
#: Both are self-limiting without a new constant, which is why this is a map
#: and not a rate. `accuse` dies when regard falls under the 0.45 gate in
#: `charter_practice._afford_accuse` -- roughly two accusations per pair, each
#: costing 0.1 -- and `reconcile` closes its own practice.
_ACT_EVENTS = {
    "tend": "aid_given",
    "accuse": "accusation",
    "reconcile": "apology",
}


def _social_events(acts, bodies, at_hours):
    """The acts of this beat, as things a body standing there would notice.

    ONLY WHAT A BYSTANDER PERCEIVES: who acted, whom they acted on, and
    where. No blame count, no attribution, no claim content -- these payloads
    reach the character tier through `charter_runtime._scheduled_row`, so a
    field naming the institution's own register would be a leak into it.
    """
    out = []
    for act in acts or ():
        kind = _ACT_EVENTS.get(str(act.get("act") or ""))
        if kind is None:
            continue
        actor = str(act.get("actor") or "")
        if not actor or actor not in (bodies or {}):
            continue
        out.append(_event(
            kind, at_hours, str((bodies.get(actor) or {}).get("place") or ""),
            # `about` and `actor` both name the ACTING body: the signal reader
            # takes whichever it finds, and what an onlooker learns is who
            # did it. `subject` is whom to -- carried into the claim by
            # `charter_news.news_claim`'s `toward` since 2026-08-27.
            about=actor, actor=actor, body=actor,
            subject=str(act.get("other") or "")))
    return out


#: How many bodies may share a place before co-presence stops depositing
#: familiarity. A room of this many is people you served beside; a hall of
#: five hundred is a crowd, and pairing it is quadratic for no depth.
CO_PRESENCE_WIDTH = 64

#: One window in this many, per pair sharing a place, becomes a specific
#: occasion rather than another tick of the tally. Tuned so a pair together
#: through a simulated year keeps a handful of them: often enough that the
#: system is always in motion, rare enough that storage stays sub-linear in
#: time, which is the bound this module has always been held to.
ENCOUNTER_ODDS = 96


def _remember_experience(store, holder, row, fold=True):
    """Append one participant-owned experience, updating repeated habits.

    ``fold`` off is the fast path for rows whose id is already unique -- a
    social act or a witnessed happening is a distinct occasion, so scanning
    the holder's whole life for a match finds nothing and costs the length of
    that life on every write. Only genuinely recurring rows (a habit, a post
    stood again, an acquaintance met again) need the scan.

    Rows are mutated by copy rather than in place: the caller's charter is
    shared into this store by reference, and `step` promises not to mutate
    what it was handed.
    """
    holder = str(holder or "")
    if not holder:
        return
    rows = list(store.get(holder) or ())
    if fold:
        event_id = str(row.get("id") or "")
        for position, existing in enumerate(rows):
            if not isinstance(existing, dict):
                continue
            if event_id and str(existing.get("id") or "") == event_id:
                rows[position] = dict(
                    existing, last_at_hours=row.get("at_hours"),
                    repetitions=int(existing.get("repetitions") or 1) + 1)
                store[holder] = rows[-EXPERIENCE_CAP:]
                return
    rows.append(dict(row))
    rows.sort(key=lambda value: (
        float(value.get("at_hours") or 0.0), str(value.get("id") or "")))
    store[holder] = rows[-EXPERIENCE_CAP:]


def _record_social_experiences(experiences, acts, bodies, at_hours):
    for index, act in enumerate(acts or ()):
        actor, other = str(act.get("actor") or ""), str(act.get("other") or "")
        if actor not in bodies:
            continue
        place = str((bodies.get(actor) or {}).get("place") or "")
        base = {
            "id": "social:%s:%s:%s:%0.4f:%d" % (
                actor, act.get("act") or "act", other,
                float(at_hours), index),
            "kind": "social", "at_hours": round(float(at_hours), 6),
            "place": place, "actor": actor, "other": other,
            "act": str(act.get("act") or "interacted"),
            "line": str(act.get("line") or "")[:500],
        }
        # Unique id per act: nothing to fold, so do not pay the scan.
        _remember_experience(experiences, actor, dict(base, role="actor"),
                             fold=False)
        if other in bodies:
            _remember_experience(
                experiences, other, dict(base, role="recipient"), fold=False)


def _run_private_habits(experiences, habit_runs, bodies, watch, at_hours):
    """Run due off-duty habits without creating a public event surface."""
    on_watch = {str(body) for body in (watch or {}).values()}
    for body_key, body in sorted((bodies or {}).items()):
        if body_key in on_watch or not body.get("available", True):
            continue
        for habit in body.get("private_habits") or ():
            habit_id = str(habit.get("id") or "")
            if not habit_id:
                continue
            previous = float((habit_runs.get(body_key) or {}).get(
                habit_id, -1e9))
            cadence = max(4.0, float(habit.get("cadence_hours") or 48.0))
            if float(at_hours) - previous < cadence:
                continue
            habit_runs.setdefault(body_key, {})[habit_id] = float(at_hours)
            _remember_experience(experiences, body_key, {
                # One durable autobiographical row per habit. Repetition
                # updates its count/last time rather than minting a diary row
                # for every evening.
                "id": f"private_habit:{body_key}:{habit_id}",
                "kind": "private_habit", "role": "self",
                "at_hours": round(float(at_hours), 6),
                "place": str(body.get("berth") or body.get("place") or ""),
                "habit_id": habit_id,
                "label": str(habit.get("label") or "private routine")[:160],
                "activity": str(habit.get("activity") or "")[:500],
                "privacy": "private",
            })


def _record_coarse_experiences(experiences, bodies, watch, stood_before,
                               posts, events, known_before, minds, at_hours,
                               feel=None, encounters=()):
    """The past a body keeps at COARSE resolution, where nobody is watching.

    THE GAP THIS CLOSES. `active_places` is documented three hundred lines
    below as "uniform existence, variable resolution -- everybody keeps needs,
    feeling, belief and A PAST; only the places a scene is actually in get
    social simulation." The past was the one item on that list that was not
    true. Measured before this existed: the coarse phase produced ZERO
    experience rows over 240 simulated hours, so a 720-hour presim was 624
    hours of silence and a 96-hour tail, and two of four charters in a real
    story ended a simulated month with no memory of it whatsoever.

    APPEND-ONLY, AND ONLY ON CHANGE. The module's cost rule is that storage
    grows with incident rather than with time, and it holds here: standing the
    same post for a year writes one row, not one per window; an acquaintance
    is written when it is FORMED, because the belief store already tracks
    whether it exists; a happening is written by the bodies who were standing
    where it happened. A quiet year is a handful of rows and a hard one is
    hundreds, which is the shape a life actually has.

    Nothing here reaches past a body's own position. Who was in the room, what
    post they took, and what occurred where they stood is what that body
    perceived; the institution's register is not consulted and no row is
    copied to anybody who was elsewhere.
    """
    at_hours = round(float(at_hours), 6)
    place_of = {key: str((body or {}).get("place") or "")
                for key, body in (bodies or {}).items()}
    feel = feel or {}

    def felt(body_key):
        """How the moment landed, in the affect model's own two numbers.

        Not a second opinion about the event -- `charter_feel` has already
        appraised this window from the body's own needs, its own place and
        the events that reached it, and this only carries that reading onto
        the row so the memory keeps it. A body with nothing to feel about
        contributes nothing, which is what keeps a quiet institution's feel
        dict empty and this stamp absent rather than neutral-valued.
        """
        held = (feel or {}).get(body_key)
        if not isinstance(held, dict):
            return {}
        hedonic = held.get("hedonic") or {}
        stress = held.get("stress") or {}
        # `psychology_runtime`'s own persisted shape, in its own vocabulary:
        # hedonic carries pain/pleasure/charge and stress carries
        # activation/strain. Valence is what the two hedonic poles come to;
        # arousal is the activation already computed beside them. One affect
        # model across both tiers, so a promoted character's inherited rows
        # speak the same language as the ones it goes on to lay down itself.
        valence = (float(hedonic.get("pleasure") or 0.0)
                   - float(hedonic.get("pain") or 0.0))
        arousal = float(stress.get("activation") or 0.0)
        if not valence and not arousal:
            return {}
        return {"valence": round(valence, 4), "arousal": round(arousal, 4)}

    # A POST STOOD FOR THE FIRST TIME. Not every change of the bill: the bill
    # is re-planned every window, and on a short-handed institution it churns
    # constantly as hands tire and recover -- measured on the six-body ship,
    # writing every change grew service rows 35x for 36x the hours, which is
    # exactly the storage-grows-with-time failure this module's docstring
    # forbids. Taking the engine watch the first time is an event in a life;
    # taking it the three hundredth is a shift. The volume is already counted
    # by `stood`, and who it was stood beside by `served_beside`.
    for post_key, body_key in sorted((watch or {}).items()):
        if body_key not in (bodies or {}):
            continue
        if (stood_before.get(body_key) or {}).get(post_key):
            continue
        post = (posts or {}).get(post_key) or {}
        _remember_experience(experiences, body_key, {
            "id": f"service:{body_key}:{post_key}:{at_hours:0.4f}",
            "kind": "service", "role": "self", "at_hours": at_hours,
            "place": str(post.get("place") or place_of.get(body_key) or ""),
            "post": str(post_key),
            "serves": [str(x) for x in (post.get("serves") or ())][:4],
            **felt(body_key),
        }, fold=False)

    # AN ACQUAINTANCE FORMED, and FOLDED, which is the whole of the care here.
    # The belief store is the record of who a body has come to know, but it
    # DECAYS: a claim ages out, the two meet again, and the absence-from-
    # `known_before` test reads that as a first meeting all over again. Left
    # appending, a quiet 40-body town wrote 8 acquaintance rows in 48 hours,
    # 94 in two months and 1134 in two years -- twenty-eight rows per person
    # known, growing with time and not with incident, which is the exact
    # failure this module's docstring names. The id is stable per pair, so
    # folding turns every re-meeting into a repetition count on the one row
    # that says they know each other. An existing test caught this.
    for body_key, held in sorted((minds or {}).items()):
        if body_key not in (bodies or {}):
            continue
        seen = known_before.get(body_key) or frozenset()
        for other in sorted(set(held or ()) - set(seen)):
            if other == body_key:
                continue
            # A NEWS CLAIM IS NOT A PERSON. `minds` is ONE store with kinds
            # in it -- a claim about somebody, a sighting of a figure, a
            # thing that happened -- and this loop read every key in it as
            # somebody newly met. Measured on the 40-body `twin_towns`
            # charter driven into famine for a simulated quarter: 9,902
            # acquaintance rows, 9,284 of which named a news key rather than
            # a body. Forty-four per cent of the entire experience store was
            # people who do not exist, evicting real rows under
            # `EXPERIENCE_CAP` -- a silent quality loss rather than a visible
            # cost one. Found by measuring the row budget while landing the
            # rumour-check producer, which added 145 of them.
            if (held.get(other) or {}).get("kind") == "news":
                continue
            _remember_experience(experiences, body_key, {
                "id": f"met:{body_key}:{other}",
                "kind": "acquaintance", "role": "self", "at_hours": at_hours,
                "place": place_of.get(body_key, ""),
                "other": str(other),
                "firsthand": (held.get(other) or {}).get("heard_from") is None,
                **felt(body_key),
            })

    # AN OCCASION WITH SOMEBODY, drawn in `step` from the pairs actually
    # sharing a place. Both parties keep it, because both were there -- and
    # only the two of them, because nobody else was. Not folded: this is the
    # one row per pair that is NOT the tally, and collapsing two occasions
    # into a repetition count is precisely what the tally already does better.
    for one, other, where in encounters or ():
        if one not in (bodies or {}) or other not in (bodies or {}):
            continue
        post_of = {body: post for post, body in (watch or {}).items()}
        for holder, companion in ((one, other), (other, one)):
            _remember_experience(experiences, holder, {
                "id": f"encounter:{holder}:{companion}:{at_hours:0.4f}",
                "kind": "encounter", "role": "self", "at_hours": at_hours,
                "place": where, "other": str(companion),
                "during": str(post_of.get(holder) or ""),
                **felt(holder),
            }, fold=False)

    # A HAPPENING STOOD THROUGH. Presence is the whole test, exactly as it is
    # for `charter_news.witness` -- a body standing where something crossed a
    # floor lived through it, and a body elsewhere did not.
    for index, event in enumerate(events or ()):
        where = str((event or {}).get("place") or "")
        if not where:
            continue
        kind = str(event.get("kind") or "")
        for body_key in sorted(bodies or {}):
            if place_of.get(body_key) != where:
                continue
            _remember_experience(experiences, body_key, {
                "id": f"stood_through:{body_key}:{kind}:{at_hours:0.4f}:{index}",
                "kind": "stood_through", "role": "witness",
                "at_hours": at_hours, "place": where,
                "event_kind": kind,
                "about": str(event.get("upkeep") or event.get("post")
                             or event.get("body") or ""),
                **felt(body_key),
            }, fold=False)


def step(charter, hours=4.0, seed=0, reach=None, conduct=None, paths=None,
         simulate_bound=False):
    """Advance one planning window. Returns ``(charter, events)``.

    The charter is returned rather than mutated, so a caller may explore a
    window without committing to it -- which is what a rerun-from-stage or a
    checkpoint restore needs, and what a tick that mutated in place could not
    offer.

    ``simulate_bound`` suspends the promotion exclusion below. It is for the
    PRE-STORY catch-up only, and it exists because the exclusion was being
    applied at a time when the thing it defers to does not yet exist. See the
    note on `external`.
    """
    charter = normalize_charter(charter)
    hours = max(0.0, float(hours))
    at = float(charter["clock_hours"])
    events = []
    charter, intervention_events = apply_due(charter, at + hours)
    events.extend(intervention_events)

    # A scene is optional. Without one the institution is a single place and
    # everyone can stand any post, which is the right simplification for six
    # people in one hull and the wrong one for five hundred across ninety
    # compartments.
    scene = charter.get("scene")
    # Promotion delegates cognition and motion to the registered character.
    # Charter keeps only an institutional projection: it may put their name
    # on a watch bill, but may not walk, tire, feel, or speak for them.
    #
    # DURING PLAY. Before the story opens there IS no registered character to
    # delegate to, and manufacturing that character's past is the entire point
    # of the pre-story run -- so applying the exclusion there subtracts
    # cognition and hands it to nobody. Measured on the site_17 presim: after
    # 720 simulated hours the one featured resident had stood 25 watches and
    # was the SINGLE body absent from both `minds` and `needs`, holding zero
    # experiences, while the 39 unbound bodies around it averaged 4.4
    # experiences and knew 5.8 people each. The major character was the
    # emptiest body in its own institution.
    external = set() if simulate_bound \
        else set((charter.get("bindings") or {}).keys())
    if reach is None and scene:
        # Recomputed here when a caller steps directly, and hoisted out by
        # `run` when it does not. Measured on the 500-hand fixture: 500 bodies
        # against 8 places is up to 4,000 graph walks, and doing it per window
        # made a simulated week 8.9s where the work itself is a fraction of
        # that. Bodies that do not move have the same reach every window.
        reach = reach_map(scene, charter_places(charter), charter["bodies"])

    politics = normalize_politics(charter.get("politics"))
    # PRESSURE RIDES THE SAME AXIS AS STANDING. A body whose needs are unmet
    # is one the institution should be reluctant to spend, and the planner
    # already knows how to weigh reluctance — so an exhausted hand is treated
    # as scarce rather than as a special case. It never becomes unpostable
    # that way; it becomes expensive, and a short-handed charter still posts
    # it because it must.
    needs = charter.get("needs") or {}
    mood_weight = float(charter.get("mood_weight") or 0.0)
    blame = (politics.get("blame") or {})
    regard_of = {}
    if mood_weight:
        for pair_key, weight in (politics.get("regard") or {}).items():
            pair = regard_pair(pair_key)
            if pair is not None:
                regard_of.setdefault(pair[1], []).append(weight)
    reluctance = {}
    for key in charter["bodies"]:
        held = needs.get(key) or {}
        weight = spend_reluctance(politics, key) + pressure(held)
        if mood_weight:
            # Felt state joins the SAME axis as standing and exhaustion: a
            # body the institution is reluctant to spend, for whatever reason,
            # is spent later. It can never become unpostable that way, which
            # is what keeps an unhappy crew from becoming an unusable one.
            weight += mood_weight * mood(
                held, blamed=int(blame.get(key, 0)),
                regard_of_others=regard_of.get(key, ()))
        reluctance[key] = weight

    plan = plan_watch(charter, horizon_hours=hours, seed=seed, reach=reach,
                      reluctance=reluctance)
    served = tended_upkeeps(charter, plan["watch"], fixed_bodies=external)

    # ONLY THE CHANGE IS AN EVENT, for posts exactly as for upkeeps. The rule
    # was written for upkeeps and not applied here, and the cost model went
    # immediately: a two-week run over one broken ship wrote 169 rows for five
    # things happening, because an unfilled post re-reported every window. A
    # post that stays unfilled for a fortnight is one fact, not eighty-four.
    #
    # `reported` carries the standing condition forward so a repair, and then
    # a second failure, produce two events rather than one or none.
    reported = {k: dict(v) for k, v in (charter.get("reported") or {}).items()}
    standing_unfilled = reported.get("post_unfilled") or {}
    standing_absent = reported.get("post_believed_filled") or {}

    now_unfilled = {e["post"]: e["reason"] for e in plan["unfilled"]}
    for entry in plan["unfilled"]:
        if standing_unfilled.get(entry["post"]) == entry["reason"]:
            continue
        events.append(_event(
            "post_unfilled", at, entry["place"],
            post=entry["post"], reason=entry["reason"],
            serves=list(entry["serves"])))
    for post_key in sorted(set(standing_unfilled) - set(now_unfilled)):
        post = charter["posts"].get(post_key) or {}
        events.append(_event(
            "post_filled_again", at, post.get("place", ""), post=post_key))

    # A post staffed from a stale roster with a body that is not in fact there
    # tends nothing and says nothing -- the charter believes it is covered.
    # Emitted because it BRANCHES (the upkeep will now drift), not because
    # anybody noticed.
    now_absent = {}
    for post_key, body_key in plan["watch"].items():
        body = charter["bodies"].get(body_key)
        post = charter["posts"][post_key]
        externally_absent = (
            body_key in external and body is not None
            and str(body.get("place") or "") != str(post.get("place") or "")
        )
        if body is None or not body["available"] or externally_absent:
            # Keyed on the POST, not on who was sent. The standing fact is
            # that this post is believed covered and is not; which name the
            # charter tried this window is detail. Keying on the body wrote a
            # row every window as the planner worked through the absent, 308
            # of them for one cut road.
            now_absent[post_key] = body_key
            if post_key in standing_absent:
                continue
            events.append(_event(
                "post_believed_filled", at, post["place"],
                post=post_key, body=body_key,
                reason="absent" if body else "no_such_body"))

    # Supply is read from the levels as they stand at the START of the window,
    # for every upkeep at once. Reading them as they update would make the
    # result depend on dict iteration order -- a chain would behave one way
    # upstream-first and another downstream-first, and neither replay nor
    # checkpoint restore would be honest.
    before_levels = dict(charter["upkeeps"])

    # The posted bodies actually go. Before the needs advance, because the
    # ground they covered is part of what this window cost them, and before
    # the talking, because who is in a room with whom is the result of the
    # watch rather than of last window's berthing.
    movable_watch = (plan["watch"] if not external else
                     {post: body for post, body in plan["watch"].items()
                      if body not in external})
    bodies, travelled = relocate(
        charter["bodies"], movable_watch, charter["posts"], scene,
        charter.get("travelled"))

    # THEN EVERYBODY ELSE'S DAY. Errands are the circulation without which
    # a town has no rumour: a famine month minted 244 witnessable events
    # and not one ever spread second-hand, because apart from the posted
    # half-dozen nobody ever left the room they were authored into. A body
    # off the watch visits the place its needs are fed from — or its
    # nearest charter place — and everyone with nowhere to be walks home to
    # its berth. Same mover, same distance bookkeeping, no new state.
    rate = charter.get("errand_rate")
    rate = ERRAND_RATE if rate is None else float(rate)
    if scene and rate > 0.0:
        visits = errands(bodies, needs, charter["upkeeps"], plan["watch"],
                         charter_places(charter), reach, seed=seed,
                         rate=rate, hours=hours)
        moves = dict(homecomings(bodies, plan["watch"], visits), **visits)
        if external:
            moves = {body: place for body, place in moves.items()
                     if body not in external}
        if moves:
            bodies, travelled = walk(bodies, moves, scene, travelled,
                                     cache=paths)

    upkeeps = {}
    for key, upkeep in charter["upkeeps"].items():
        was_down = out_of_band(upkeep)
        tended = hours if key in served else 0.0
        supply = supply_factor(upkeep, before_levels)
        after = dict(upkeep)
        after["level"] = advance_level(
            upkeep, hours, tended_hours=tended, supply=supply)
        now_down = out_of_band(after)

        # Only the CROSSING is an event. A condition that was already below
        # its floor and stays there writes nothing further -- otherwise a
        # broken thing costs a row every window forever, which is exactly the
        # storage-grows-with-time failure this module is built to avoid.
        if now_down and not was_down:
            # Name the input that starved it, when one did. A chain that
            # collapses must say WHERE, or the log records a symptom and hides
            # its cause -- the town ran out of bread is not the story, the
            # town ran out of flour is.
            starved = starving_input(upkeep, before_levels) if supply < 1.0 \
                else None
            events.append(_event(
                "upkeep_out_of_band", at + hours, after["place"],
                upkeep=key, level=round(after["level"], 6),
                floor=after["floor"], starved_by=starved))
        elif was_down and not now_down:
            events.append(_event(
                "upkeep_restored", at + hours, after["place"],
                upkeep=key, level=round(after["level"], 6)))
        upkeeps[key] = after

    # MATERIAL FLOWS ride the same window and branch-only event discipline as
    # upkeep. Empty economies are byte-stable no-ops; authored flows advance
    # aggregate lots and report only a threshold crossing.
    economy, economy_events = advance_economy(
        charter.get("economy"), hours, upkeeps=upkeeps, at_hours=at)
    events.extend(economy_events)

    # STANDING A POST IS AN OBSERVATION, and without this rule the whole
    # institution starves: roster claims decay, every one of them falls under
    # TRUST_FLOOR at the same hour, the charter stops staking posts on anybody
    # and a fully healthy crew watches its ship fail. Measured on the first
    # run of this module: reactor_thermal crossed its floor at hour 240 with
    # six able bodies aboard and nothing wrong.
    #
    # The rule is also the right one in the fiction, which is why it is a fix
    # rather than a fudge: rosters are kept current by people turning up. A
    # body that stands its watch is seen standing it, so the charter's claim
    # about it is refreshed from what was actually there. A body that never
    # appears decays quietly out of the roster, which IS the "he transferred
    # out two months ago" case arriving on its own.
    #
    # Scope limit, stated rather than hidden: only being ON a post counts as
    # being seen. A crew that passes each other in a corridor all day would
    # also keep a roster current, and this prototype has no co-presence to
    # read. So it forgets an idle body faster than a real institution would.
    roster = decay_roster(charter["roster"], hours)
    for post_key, body_key in plan["watch"].items():
        body = charter["bodies"].get(body_key)
        actually_there = (body_key not in external or (
            body is not None and str(body.get("place") or "")
            == str((charter["posts"].get(post_key) or {}).get("place") or "")))
        if body is not None and body["available"] and actually_there:
            roster = observe(roster, body, at + hours)

    # THEN THEY TALK, and knowing now happens in three distinct places rather
    # than one. Bodies in a room see each other first-hand and pass on what
    # they hold about third parties; then the watch reports what IT believes
    # up to the register. The order matters: this window's seeings circulate
    # in this window, and the roster hears the result rather than last
    # window's.
    # NEEDS, AND AVAILABILITY AS A CONSEQUENCE RATHER THAN A FLAG. A body on
    # watch spends rest faster than it can recover it, and a need whose
    # `fed_by` upkeep has failed is serviced at whatever that upkeep permits.
    # So a failing chain reaches the bodies at the end of it, and the bodies
    # going under take the posts with them — the spiral is not scripted
    # anywhere, it is these two facts meeting.
    # FEELING COSTS REST, AND NOTHING ELSE. Last window's strain — computed
    # by the engine's own stress model over what each body witnessed and
    # carried — wears tonight's rest, and any consequence arrives through
    # the same body_unable path the famine uses. The toll is a dial for the
    # same reason mood_weight is: an experiment must be able to hold its
    # control arm still.
    toll = charter.get("strain_toll")
    toll = STRAIN_REST_TOLL if toll is None else float(toll)
    owned_needs = (needs if not external else
                   {key: held for key, held in needs.items()
                    if key not in external})
    owned_bodies = (bodies if not external else
                    {key: body for key, body in bodies.items()
                     if key not in external})
    needs_after, unable, recovered = advance_needs(
        owned_needs, owned_bodies, movable_watch, upkeeps, hours,
        strain=strain_of(charter.get("feel")), toll=toll)
    for key in unable:
        bodies[key] = dict(bodies[key], available=False, stood_down=True)
        # A needs-driven stand-down is not a private change in ground truth:
        # the body just failed while serving (or reported that it could not
        # serve), which is exactly the kind of observation the institutional
        # register is allowed to learn.  Without this write the roster keeps
        # assigning a body it believes able until the claim decays.
        roster = observe(roster, bodies[key], at + hours)
        events.append(_event("body_unable", at + hours,
                             bodies[key].get("place", ""), body=key,
                             worst=unmet(needs_after.get(key) or {})))
    for key in recovered:
        bodies[key] = dict(bodies[key], available=True, stood_down=False)
        # Recovery has the reciprocal channel: returning fit for duty is a
        # report to the register, not omniscient reconciliation.  A recovered
        # worker would otherwise remain unassignable forever because only an
        # assigned worker is observed standing a watch.
        roster = observe(roster, bodies[key], at + hours)
        events.append(_event("body_recovered", at + hours,
                             bodies[key].get("place", ""), body=key))

    # A promoted body's mind has one owner: character_step.  Drop any stale
    # Charter-held copy before decay/talk, and expose the institutional
    # projection to the remaining bodies as a FIGURE instead.  They may see
    # and talk about the person; Charter may never recreate a mind for them.
    # Who each body knew before this window, so an acquaintance can be
    # written when it is FORMED rather than re-written every window it holds.
    known_before = {str(key): frozenset(held or ())
                    for key, held in (charter.get("minds") or {}).items()
                    if isinstance(held, dict)}
    minds = decay_minds(charter.get("minds") or {}, hours)
    if external:
        minds = {holder: claims for holder, claims in minds.items()
                 if holder not in external}
    news_keys = set(charter.get("news_keys") or ())
    minds = decay_news(minds, hours, news_keys)
    # WITNESSED BEFORE ANYBODY TALKS, so this beat's news can travel in this
    # beat. Presence is the whole test -- a body standing where something
    # happened knows it, nobody else does, and it spreads only by being told.
    minds, witnessed = witness(minds, owned_bodies, events, at + hours)
    # Figures are seen wherever they stand, active place or not: laying eyes
    # on the traveller is perception, not beat-scale social detail, and it is
    # the same rule witnessing an event follows -- presence is the whole
    # test. What a body DOES about the sighting still waits for a scene.
    figures = dict(charter.get("figures") or {})
    for body_key in external:
        body = bodies.get(body_key) or {}
        figures[body_key] = {
            "key": body_key,
            "place": str(body.get("place") or ""),
            "surface": {"name": str(body.get("name") or body_key),
                        "institutional_role": True},
        }
    if figures:
        minds = sight_figures(minds, owned_bodies, figures, at + hours)
    if witnessed or news_keys:
        news_keys = news_keys_in(minds)
    minds, told = converse(minds, owned_bodies, seed=seed,
                           regard=regard_map(politics), at_hours=at + hours,
                           figures=figures)
    minds, formally_reported = report_to_superiors(
        minds, plan["watch"], charter["posts"], owned_bodies,
        naming=charter.get("naming"), at_hours=at + hours)
    told += formally_reported
    roster = report_up(roster, minds, plan["watch"], owned_bodies,
                       standing=politics.get("standing"), at_hours=at + hours)

    # DECISIONS consume only reports that reached the authorised officeholder.
    # Orders then descend one co-present reporting edge and execute through a
    # closed action vocabulary. No objective event list is handed to a mind.
    late_event_start = len(events)
    decisions, issued = advance_decisions(
        charter.get("decisions"), minds, plan["watch"], charter["posts"],
        owned_bodies, charter_key=charter["key"], at_hours=at + hours)
    decisions, delivered_orders = deliver_orders(
        decisions, plan["watch"], charter["posts"], owned_bodies)
    decisions, economy, decision_events = execute_orders(
        decisions, economy, at_hours=at + hours, posts=charter["posts"])
    for order in issued:
        source_body = str(plan["watch"].get(order["from_post"]) or "")
        events.append(_event(
            "institution_order_issued", at + hours,
            (owned_bodies.get(source_body) or {}).get("place", ""),
            order_id=order["id"], action=order["action"],
            body=source_body, to_post=order["to_post"]))
    events.extend(decision_events)

    # Decisions happen after conversation because reports are their input.
    # Their public consequences still belong to this window: people standing
    # at the issuing/executing post witness them now, then may retell them in a
    # later conversation. Without this second aperture orders existed only in
    # the institution's private register and the external world-event rail.
    minds, late_witnessed = witness(
        minds, owned_bodies, events[late_event_start:], at + hours)
    witnessed += late_witnessed
    if late_witnessed:
        news_keys = news_keys_in(minds)

    # AND SOME OF WHAT THEY HOLD, THEY CAN SIMPLY LOOK AT. A body standing
    # where a second-hand rumour named settles it against the place itself
    # and comes to a view about whoever told it. After `converse`, so a claim
    # heard this window in a room that contradicts it is refuted at once;
    # before the judgment fold, because unlike witnessing an act there is
    # nothing to lag here -- the perception IS the revision, the body is
    # standing in front of the evidence.
    checked = 0
    if news_keys:
        minds, checked = check_reports(
            minds, owned_bodies, upkeeps, at + hours, news_keys)
        if checked:
            news_keys = news_keys_in(minds)

    # What a holder thinks changes only from evidence already in that holder's
    # own head. The reason list doubles as an idempotence guard.
    judgments, judgment_movements = update_judgments_from_minds(
        charter.get("judgments"), minds, politics=politics,
        norms=charter.get("social_norms"))

    # Explicit commitment lifecycle events are state; whether a particular
    # person learns one still goes through witnessing/telling next window.
    commitments, commitment_changes = advance_commitments(
        charter.get("commitments"), events)

    # SITUATIONS, AND WHAT THEY MAKE AVAILABLE. Gossip alone saturates: a
    # claim passes only when it beats what the listener holds, so a population
    # that has met itself goes silent and stays silent until decay reopens the
    # door. Measured: 103 interactions in a hundred beats, every one of them
    # in the first nine. Practices supply reasons to act that do not depend on
    # claim strength -- meeting a stranger, attending somebody who has gone
    # down, saying aloud that you blame somebody -- and acting spawns further
    # situations, so the loop feeds itself.
    #
    # AND ONLY WHERE SOMEBODY MIGHT SEE IT. Practices are beat-scale social
    # detail; running them for five hundred bodies nobody is near, once per
    # four-hour planning window, took a simulated month from 3.6s to 32.7s and
    # tripped this package's own cost guard. That is not a tuning problem, it
    # is the wrong cadence: an off-screen body does not need beat-resolution
    # gossip, it needs its state to be RIGHT when somebody arrives, which is
    # the `O(re-contact)` rule the whole architecture rests on.
    #
    # So `active_places` is the resolution dial: uniform existence, variable
    # resolution. Everybody keeps needs, feeling, belief and a past; only the
    # places a scene is actually in get social simulation. Empty means none,
    # because the cheap thing must be the default.
    active = charter.get("active_places")
    practices = close_stale(
        normalize_practices(charter.get("practices")), at + hours)
    if active:
        in_focus = {k: b for k, b in bodies.items()
                    if k not in external
                    and str(b.get("place") or "") in active}
        figs_in_focus = {k: f for k, f in figures.items()
                         if str(f.get("place") or "") in active}
        practices.update(opportunities(
            in_focus, minds, needs_after, events, practices, at + hours,
            seed=seed, figures=figs_in_focus,
            blame=politics.get("blame") or {}))
    else:
        # OFF THE SCENE, THE SOCIAL WORLD STILL TURNS -- just not at beat
        # resolution. This branch used to be empty, and an empty branch is a
        # claim: that a place nobody is looking at contains no relationships
        # forming, nobody helped off the floor, and nobody meeting anybody.
        # Measured on the 40-body site_17 charter, a healthy simulated YEAR
        # emitted zero events of any kind, so the only thing an institution
        # could ever be found to have done was fail. "All systems nominal" is
        # a report; it is not what happened to these people.
        #
        # `COARSE_PRACTICES` is the subset that does not saturate: somebody
        # under their floor and somebody standing over them, and two people
        # who have not met. Both are bounded by the shape of the institution
        # rather than by how long it runs, which is the same rule the event
        # log has always been held to. Gossip stays where it belongs, on
        # screen.
        in_focus = {k: b for k, b in bodies.items() if k not in external}
        figs_in_focus = {}
        practices.update(opportunities(
            in_focus, minds, needs_after, events, practices, at + hours,
            seed=seed, kinds=COARSE_PRACTICES))
    regard = dict(politics.get("regard") or {})
    # AND THEY DECIDE FROM WHAT HAS PASSED BETWEEN THEM. The INCOMING
    # `charter["experiences"]`, not the copy-on-write local built further
    # down: that local does not exist yet here, and semantically a body
    # decides from the record it had when the window opened rather than from
    # one this window is still writing. `judgments` and `commitments` are
    # this window's, both already advanced above from evidence their own
    # holders hold.
    acts, spawned, closed, heard, refused = enact(
        in_focus, minds, needs_after, practices, regard,
        politics.get("blame") or {}, at + hours, seed=seed,
        figures=figs_in_focus, conduct=conduct,
        experiences=charter.get("experiences"),
        served_beside=charter.get("served_beside"),
        judgments=judgments, commitments=commitments)
    for key in closed:
        practices.pop(key, None)
    for key, entry in spawned:
        practices.setdefault(key, entry)
    politics = dict(politics, regard=regard)
    told += len(acts)

    # AN ACT THAT CHANGES WHAT PEOPLE ARE TO EACH OTHER IS AN EVENT. Which
    # acts those are is `_ACT_EVENTS`, above, with the argument for each.
    #
    # Witnessed immediately, judged next window. `update_judgments_from_minds`
    # runs before `enact`, so an act cannot move an opinion in the window it
    # happens; `minds` carries the claim across and the opinion forms on the
    # next one. That is the right lag anyway -- nobody revises their view of a
    # person in the same instant they watch them act. The rumour-check above
    # is the deliberate exception and says why.
    social_events = _social_events(acts, bodies, at + hours)
    if social_events:
        events.extend(social_events)
        minds, act_witnessed = witness(
            minds, owned_bodies, social_events, at + hours)
        witnessed += act_witnessed
        if act_witnessed:
            news_keys = news_keys_in(minds)

    # COPY-ON-WRITE, per holder. The lists are shared in by reference and
    # `_remember_experience` replaces the one it touches, so a window costs the
    # holders it actually writes to rather than every row in the institution.
    # Deep-copying the whole store each window was O(all rows) unconditionally
    # -- at the depth this store is now allowed to reach that alone would have
    # cost a simulated year more than the simulation of it.
    experiences = {
        str(holder): rows
        for holder, rows in (charter.get("experiences") or {}).items()
        if isinstance(rows, list)}
    _record_social_experiences(experiences, acts, bodies, at + hours)
    habit_runs = {
        str(holder): dict(runs)
        for holder, runs in (charter.get("habit_runs") or {}).items()
        if isinstance(runs, dict)}
    _run_private_habits(
        experiences, habit_runs, bodies, plan["watch"], at + hours)

    heard_blame = {k: set(v) for k, v in
                   (charter.get("heard_blame") or {}).items()}
    for subject, tellers in heard.items():
        heard_blame.setdefault(subject, set()).update(tellers)

    # The carry limit runs where the window's additions END, not only where
    # decay does: witnessing, sighting and talk all put claims into heads
    # after `decay_minds` capped them, and a circulating population can meet
    # more in a window than decay had capped for.
    minds = cap_minds(minds)

    # THEN THEY FEEL IT. After the window's events exist, because what a body
    # appraises is what happened where it stood; after needs, because
    # deprivation is this window's pain rather than last window's. The felt
    # state is produced by `mind/psychology_runtime`'s own resolvers — one
    # affect model across both tiers — and it reads only channelled inputs:
    # own needs, the state of the body's own place, and the transient
    # events there.
    owned_feel = (charter.get("feel") or {})
    if external:
        owned_feel = {key: value for key, value in owned_feel.items()
                      if key not in external}
    feel = advance_feel(owned_feel, owned_bodies, needs_after,
                        movable_watch, charter["posts"], upkeeps, events,
                        hours)

    # WHO THEY STOOD IT WITH, counted the same way and for the same reason.
    # A stable institution is QUIET -- measured on the 40-body site_17 charter,
    # a healthy simulated year emitted zero events and the watch bill stopped
    # changing after about three months, so anything written only on change
    # goes silent while the crew is still living. What a year of that actually
    # deposits is not incident, it is FAMILIARITY: the hand you were beside
    # three hundred times is the one you know, and a count says that in one row
    # where three hundred rows would say it worse. Keyed bodies x bodies, so it
    # grows with the shape of the institution rather than with time.
    served_beside = {k: dict(v) for k, v
                     in (charter.get("served_beside") or {}).items()
                     if isinstance(v, dict)}
    _company = {}
    for body_key, body in bodies.items():
        if not body.get("available"):
            continue
        where = str(body.get("place") or "")
        if where:
            _company.setdefault(where, []).append(body_key)
    # AND SOMETIMES SOMETHING HAPPENS BETWEEN THEM. A counter says a pair
    # stood three hundred watches together and says nothing about any of them;
    # the tally is the right way to carry the VOLUME and the wrong way to
    # carry a life. Every social source in this module used to be gated on
    # something going wrong -- `tending` opens only when a body is under its
    # floor, `greeting` only between people who have not met -- so a healthy
    # institution produced no social life at all, and the only thing anyone
    # could be found to have done was fail.
    #
    # A shared watch is the ordinary source. Deterministically drawn from the
    # run's own seed so it replays byte-identically, and rare enough that the
    # rows stay sub-linear in time while never stopping: a pair standing
    # together for a year gets a handful of specific occasions out of hundreds
    # of ordinary ones. The row carries only the fact -- who, where, which
    # watch, and how it landed. What it MEANT is the historian pass's job over
    # cited surfaces, which is where prose belongs and this is not.
    encounters = []
    for where, company in sorted(_company.items()):
        if len(company) > CO_PRESENCE_WIDTH:
            continue
        roster_here = sorted(company)
        for index, one in enumerate(roster_here):
            for other in roster_here[index + 1:]:
                draw = int(hashlib.sha256(
                    ("%s|%0.4f|%s|%s|%s" % (seed, at + hours, where, one,
                                            other)).encode("utf-8")
                ).hexdigest()[:8], 16)
                if draw % ENCOUNTER_ODDS:
                    continue
                encounters.append((one, other, where))


        # WHERE THE BODIES ACTUALLY ARE, on watch or off it. Keying this to
        # post places instead reached 9 of 40 bodies on the site_17 charter,
        # because most posts stand alone in a room and everybody off the bill
        # -- which is most of an institution, most of the time -- was never
        # counted as being anywhere with anyone.
        #
        # A crowd is not acquaintance, and it is quadratic. Past this width a
        # place is a concourse rather than a room shared, so it deposits
        # nothing rather than deposits everything.
        if len(company) > CO_PRESENCE_WIDTH:
            continue
        for one in company:
            held = served_beside.setdefault(one, {})
            for other in company:
                if one != other:
                    held[other] = held.get(other, 0) + 1

    # The service record: a window actually stood is a window remembered.
    # Keyed bodies x posts, so it grows with the shape of the institution
    # rather than with time.
    stood = {k: dict(v) for k, v in (charter.get("stood") or {}).items()}
    for post_key, body_key in plan["watch"].items():
        body = bodies.get(body_key)
        actually_there = (body_key not in external or (
            body is not None and str(body.get("place") or "")
            == str((charter["posts"].get(post_key) or {}).get("place") or "")))
        if body is not None and body.get("available") and actually_there:
            held = stood.setdefault(body_key, {})
            held[post_key] = held.get(post_key, 0) + 1

    # AFTER THE APPRAISAL, deliberately. A memory that records only what
    # happened is a log line; what makes it a memory is how it landed on the
    # body it happened to. `feel` is this window's appraisal of this window's
    # events, computed by the engine's own affect model over channelled inputs
    # only, so stamping it here costs nothing and no second opinion is invented.
    _record_coarse_experiences(
        experiences, bodies, plan["watch"], charter.get("stood") or {},
        charter["posts"], events, known_before, minds, at + hours, feel,
        encounters)

    after_charter = dict(charter)
    after_charter["upkeeps"] = upkeeps
    after_charter["roster"] = roster
    after_charter["clock_hours"] = at + hours
    after_charter["watch"] = dict(plan["watch"])
    after_charter["bodies"] = bodies
    after_charter["needs"] = needs_after
    after_charter["travelled"] = travelled
    after_charter["minds"] = minds
    after_charter["judgments"] = judgments
    after_charter["commitments"] = commitments
    after_charter["economy"] = economy
    after_charter["decisions"] = decisions
    after_charter["practices"] = practices
    after_charter["acts"] = list(acts)
    after_charter["experiences"] = experiences
    after_charter["habit_runs"] = habit_runs
    # Authored conduct the state refused, with reasons. Diagnostics for the
    # author -- nothing reads it, and a refusal changes no state.
    after_charter["refused"] = list(refused)
    after_charter["heard_blame"] = {k: sorted(v)
                                    for k, v in heard_blame.items()}
    after_charter["feel"] = feel
    after_charter["stood"] = stood
    after_charter["served_beside"] = served_beside
    after_charter["told"] = told
    after_charter["witnessed"] = witnessed
    # Rumours settled by looking at the place this window. Diagnostic only,
    # exactly as `refused` is: nothing reads it, and `normalize_charter` drops
    # it at the next persistence boundary along with `told` and `witnessed`.
    after_charter["checked"] = checked
    after_charter["news_keys"] = sorted(news_keys)
    after_charter["reported"] = {
        "post_unfilled": now_unfilled,
        "post_believed_filled": now_absent,
    }
    # Blame attaches to the watch the charter BELIEVED it had arranged, so a
    # body can be held responsible for a post it was never at. That is the
    # intended failure, not a bug in the attribution: the roster said they
    # were on it, the thing failed, and the institution now knows who to be
    # angry with. Correcting that is somebody else's job and may never happen.
    after_charter["politics"] = attribute_blame(
        politics, events, plan["watch"], charter["posts"])

    # THE DISCRETE TIE, LAST, so it reads post-blame regard -- `attribute_blame`
    # is the one writer in this window that can move a directed opinion after
    # the acts are in, and a tie derived before it would be a window behind the
    # numbers it claims to summarize.
    #
    # OFF THE DIRTY SETS THIS WINDOW ALREADY PAID FOR. `judgment_movements`
    # has been computed at the fold above since judgments landed and read by
    # nothing; `_company` is the same per-place roll `served_beside` counts
    # from. `update_ties`' docstring carries the argument for why visiting only
    # those pairs is COMPLETE rather than approximate, and the three properties
    # of today's code it rests on.
    #
    # `CO_PRESENCE_WIDTH` for the same reason the tally uses it: past that
    # width a place is a concourse, `served_beside` deposits nothing there, so
    # familiarity never rises there and the only remaining input is regard --
    # which cannot form a tie on its own (`TIE_WEIGHTS["regard"]` is below
    # `TIE_FORM`). Skipping a crowd is sound here, not a budget cut, and it is
    # what stops a second quadratic landing in the same loop.
    after_charter["ties"], tie_changes = update_ties(
        charter.get("ties"),
        company={where: folk for where, folk in _company.items()
                 if len(folk) <= CO_PRESENCE_WIDTH},
        movements=judgment_movements, judgments=judgments,
        politics=after_charter["politics"], served_beside=served_beside,
        at_hours=at + hours)
    # Diagnostic, dropped by `normalize_charter` exactly as `told`/`witnessed`/
    # `checked` are.
    after_charter["ties_changed"] = len(tie_changes)
    return after_charter, events


def run(charter, hours, window=4.0, seed=0, trace=False, simulate_bound=False):
    """Advance many windows. Returns ``(charter, events)``, or
    ``(charter, events, trace)`` when ``trace`` is set.

    THE TRACE IS NOT STATE. It is handed back beside the events rather than
    folded into them, and nothing reads it — a run behaves identically whether
    it is collected or not. That separation is deliberate: an event is
    something the world recorded and a mind may one day learn, a trace line is
    something an author looked at, and letting the second become the first is
    how a diagnostic turns into canon.

    The shape a test drives ten thousand simulated hours through, and the
    shape an out-of-band job would use to catch a world up to the wall clock
    at re-contact.
    """
    charter = normalize_charter(charter)
    remaining = max(0.0, float(hours))
    window = max(1e-6, float(window))
    events = []
    notes = []
    index = 0
    # Walked once for the whole run, and re-walked only when a body's place
    # changes. Nothing in this package moves anybody yet, so in practice that
    # is once; the guard is here so it stays correct on the day something
    # does.
    scene = charter.get("scene")
    places = charter_places(charter) if scene else ()
    # One path cache for the whole run: a fixed scene's walk between two
    # rooms never changes, so once a population circulates (`errands`) the
    # per-window cost of movement is dict lookups, not graph walks.
    paths = {}
    reach = reach_map(scene, places, charter["bodies"], cache=paths) \
        if scene else None
    where = {k: b["place"] for k, b in charter["bodies"].items()}
    while remaining > 0.0:
        span = min(window, remaining)
        now = {k: b["place"] for k, b in charter["bodies"].items()}
        if scene and now != where:
            moved = {k for k, place in now.items() if where.get(k) != place}
            reach = refresh_reach(reach, scene, places, charter["bodies"],
                                  moved, cache=paths)
            where = now
        # The seed advances with the window so successive windows are not
        # identical draws, while the whole run stays a pure function of the
        # caller's seed.
        charter, produced = step(charter, hours=span, seed=int(seed) + index,
                                 reach=reach, paths=paths,
                                 simulate_bound=simulate_bound)
        events.extend(produced)
        if trace:
            notes.append(window_note(charter, produced,
                                     charter.get("told", 0)))
        remaining -= span
        index += 1
    if trace:
        return charter, events, notes
    return charter, events
