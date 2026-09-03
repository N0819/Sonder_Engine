"""Lore-grounded Fable Town generation and prehistory.

One model call proposes qualitative structure. Deterministic closure creates
all rooms, bodies, rates, needs and stock. A second optional call may design
physical historical interventions; it cannot write resident memories. After
presimulation, a historian may summarize only cited event ids from the run.
"""

from __future__ import annotations

import copy
import hashlib
import json

from world.charter_identity import materialize_body_names
from world.charter_surface import (deal_surface, default_looks,
                                   looks_material_exists,
                                   normalize_looks_profile, post_dress)
from world.charter_model import (
    integer as _integer, normalize_charter, number as _number)
from world.charter_needs import seed_needs
from world.charter_roster import seed_roster


FAIL_HOURS = {"days": 72.0, "a_week": 168.0, "weeks": 336.0,
              "a_season": 720.0}
RESTORE_HOURS = {"hours": 6.0, "a_shift": 12.0, "days": 72.0}
GENERATION_VERSION = 1
HISTORIAN_RESIDENT_CAP = 240

#: CLOSURE INVARIANTS, each a named number because each is a decision the
#: closer takes on the author's behalf (Harrowmere playtest, 2026-09-02: one
#: brief closed to 14 bodies on one run and 108 on the next, three reeves and
#: three innkeepers held singular offices, and 65 householders were berthed in
#: one house).
#:
#: A closed population may miss its requested total by this fraction before
#: the closer says so. Rounding across a dozen posts and the crew floor make
#: an exact landing impossible; a tenth is the width inside which "about a
#: hundred" is still a hundred.
POPULATION_TOLERANCE = 0.10
#: Sleepers one dwelling may berth before the closer splits it into siblings.
#: Applies only to a room that is ONLY a berth -- no post's place, no
#: upkeep's place, no commons -- because a workplace is not a dwelling and
#: minting a second common room does not house anybody.
BERTH_CEILING = 8
#: Holders of a post nobody reports past. One, because the post's title is an
#: address (docs/UNBUILT.md 1.84b) and an address resolving to three minds is
#: the collision the engine already refuses for display names.
HEAD_SEATS = 1
#: The rotation every other post is topped to: a Charter post is a
#: continuous watch, and three is the smallest crew that lets fatigue rotate.
CREW_SIZE = 3


_PLAN_SYSTEM = """You design one inhabited location from supplied lore.
Return one JSON object and no prose outside it. Do not invent an institution
unless the lore or author brief implies one. Output: {name, structure:{key,
max_planned, grammar:[{kind,names,purposes}]}, rooms:{id:{name,purpose,
adjacent:[{to,barrier:"open_door"}],frontier:[]}}, charters:[{key,name,naming,
priority,commons,upkeeps:{id:{place,floor,level,fails_untended,one_body_restores_in,
requires,depends_on}},posts:{id:{place,serves,requires,reports_to,authority}},
populations:[{post,count,competence,berth,rank}],economy:{goods,stocks,targets,
flows,markets},decisions:{policies}}]}. Use qualitative timescales only; never
write drift_per_hour or service_per_hour. Planned rooms contain no prose.
Match the naming STYLE of the setting; never copy a name the lore gives to an
individual. Keep authority/actions genre neutral. IDs are stable machine keys; names retain canonical spelling.
charter.commons is a list of rooms ids: the places this institution's people go
FOR THEIR OWN SAKE -- rooms nobody is posted to and nobody keeps, whose purpose
is being in them rather than working at them. Name them; posts and upkeeps say
where the work is, and off-duty people cannot go anywhere you do not list here.
Every population.post MUST name an entry in posts, every place and berth MUST
be a rooms id, population competence MUST meet that post's numeric requires,
and every upkeep id MUST occur in at least one post.serves. A post that other
posts report to and that reports to nobody is ONE person, and closure keeps
exactly one holder for it; every other post is a continuous watch, so provide
at least three people for it unless the brief explicitly calls for a
dangerously short-handed institution. When the payload carries population, it
is the total number of residents across every charter; make the population
counts sum to it. Use competence and
requires objects like {"medicine":2}, never vague levels or lists. Naming is
{seed,given_parts:{starts,middles,ends},family_parts:{starts,middles,ends},
name_format,formal_format,titles:{posts:{},ranks:{}}}; supply SYLLABLE
FRAGMENTS the setting's names are built from, never a list of names. A name the
lore already gives to somebody is that person's name and is not material to
build strangers out of; fragments name nobody, which is why fragments are what
you may supply. A fragment must not be the opening or the ending of any
individual's name -- not one the lore names, and not one you know of from this
setting that the lore does not mention. Cutting a person's name into pieces
does not turn it into material. Fragments are sound: draw them from how the
setting's ordinary words and places sound, not from its people. Give enough of
them that the population does not repeat. Every generated body must resolve to
a stable scene-facing personal name before simulation. If the setting does not
use ordinary names, supply lore-compatible callsigns, serial names, epithets or
syllable parts; never expose a post/body machine id as the person's name.
Each charter also carries looks:{stature:[],build:[],gait:[],complexion:[],
hair:[],age:[],marks:[]} -- its LOOK LAW, the counterpart of naming for
bodies: per axis, short phrases in this population's own words for what a
stranger takes in at a glance, enough of them that a hundred people do not
repeat, and none describing an individual the lore names. stature, build,
gait, complexion and age are words that stand before a noun; hair and marks
are the thing itself. Each post may carry worn:[] (what its holders visibly
wear at the work) and marks:[] (what the work leaves on a body); supply them
where the trade shows on the person and omit them where it does not.
Economy is strictly id-keyed:
goods:{good:{label,base_value,unit}}, stocks:{holder:{good:lots}}, targets:
{holder:{good:{minimum,desired,capacity}}}, flows:{id:{holder,good,kind:
"produce|consume",lots_per_hour,requires_upkeep}}, markets:{id:{place,holder,
margin,route_burden,currency}}, supply_points:{id:{place,holder,goods:
{good:lots_per_hour},reliability,route_burden,mode}}. A material economy needs actual stocks,
targets and flows, not only a list of goods. Create 6-20 operational anchor
rooms for a large location and put omitted districts in frontier labels. When
consumption exceeds local production, declare a supply_point at a boundary;
do not pretend an externally supported location is self-sufficient."""

_PLAN_SYSTEM += """
The payload may contain featured_residents. They are authored people who must
already belong to this location when its simulated history begins. Place every
one exactly once by adding featured_residents:[{seed_id,post,competence,berth,
rank,title}] to the appropriate charter. Preserve seed_id exactly. Their name,
public_history, and abilities are placement evidence, not permission to invent
private facts or rewrite the card. Give each a lore-appropriate real post;
their presence counts toward that post's continuous shift crew."""

_PLAN_SYSTEM += """
The payload may include scale, topology, and required_rooms. Treat every
required_rooms entry as author law: preserve its exact id/name/purpose, include
it in rooms, and honor its adjacent ids. Fill out the support infrastructure
needed for that scale even when lore describes only dramatic rooms. Such
support rooms are reasonable infrastructure, not new setting canon."""

_HISTORY_SYSTEM = """You are a prehistory architect for a simulated town.
Return JSON {eras:[{name,summary}], interventions:[...]}. Interventions may be
only physical circumstances: upkeep_shock, need_shock, drift_dial. Every entry
has id, op, at_hours within the supplied horizon, cause, and the fields needed
by that op. upkeep_shock may include an observable surface. Never write minds,
memories, relationships, judgments, politics, decisions, promises, or outcomes.
The simulator will decide consequences. Prefer 2-8 consequential interventions."""

#: What one resident may cost the historian, stated to the model as a budget
#: per entry and to the engine as tokens per resident. Measured 2026-09-03
#: (Harrowmere replay, 100 residents): at 90 tokens a resident the call was
#: cut off 22,181 characters in with the JSON unterminated -- cited event ids
#: are token-dense, under two characters a token -- so the town opened with
#: no history brief for the second run running. A summary of 40 words, three
#: citations and two turning points is about 200 tokens; the allowance is
#: that with a margin, and the prompt states the same numbers so the model
#: writes to the budget the engine reserved.
HISTORIAN_SUMMARY_WORDS = 40
HISTORIAN_CITATIONS_PER_ENTRY = 3
HISTORIAN_TURNING_POINTS = 2

#: When the historian outruns its budget anyway, the call is retried with
#: half the residents, this many times, before the town is allowed to open
#: without its brief. A ceiling that does not hold is a number, not a
#: ceiling.
HISTORIAN_OVERRUN_RETRIES = 2

_HISTORIAN_SYSTEM = """Summarize the actual simulated prehistory of these
residents. Return JSON {overview:{summary,event_ids}, eras:[{summary,event_ids}],
residents:{body_id:{summary,event_ids,turning_points:
[{event_id,meaning}]}}, institutions:[{name,summary,event_ids}]}. Every factual turning point must cite an
event_id supplied in the chronicle. Every overview, era, and institution entry
must include event_ids too. A service_record is evidence only of the named
resident's actual aggregate work and route edges travelled; use posts and
watches_stood for a concise career summary, and mention route travel only when
it is materially notable. It is not evidence for an invented incident or
feeling. Every non-empty resident
summary must cite event_ids too. Do not invent an event, private memory,
relationship, quote, or outcome. Omit anything the chronicle cannot support.
Budget, per entry: a resident summary is at most %d words and cites at most
%d event_ids; a resident has at most %d turning_points; an overview, era or
institution entry cites at most %d event_ids.""" % (
    HISTORIAN_SUMMARY_WORDS, HISTORIAN_CITATIONS_PER_ENTRY,
    HISTORIAN_TURNING_POINTS, HISTORIAN_CITATIONS_PER_ENTRY)


#: Token budget for one generation call. A location plan grows with the rooms
#: and posts it has to describe, and a Galaxy-class starship with six required
#: rooms and five placed officers overran the old fixed 6000 -- which arrived
#: as a `JSONDecodeError` from `json.loads` on a half-written object, roughly
#: 24,000 characters in, naming a line and column in output nobody had asked
#: to see. The budget is generous because the failure is expensive: the call
#: has already been paid for by the time the truncation is discovered.
PLAN_MAX_TOKENS = 16000


#: The historian's output budget: a floor for the overview, eras and
#: institutions, plus a per-resident allowance for one summary with its cited
#: event ids and turning points, capped at the plan budget. Measured
#: 2026-09-02: a fixed 7,000 overran at 108 residents (`historian_error`).
#: Residents are trimmed to what the ceiling affords rather than the call
#: being allowed to outrun it, and the trim is reported in the record.
HISTORIAN_TOKENS_BASE = 3000
HISTORIAN_TOKENS_PER_RESIDENT = 220


def historian_budget(resident_count):
    """``(max_tokens, residents_afforded)`` for one historian call."""
    afforded = max(0, (PLAN_MAX_TOKENS - HISTORIAN_TOKENS_BASE)
                   // HISTORIAN_TOKENS_PER_RESIDENT)
    residents = min(int(resident_count), afforded)
    return (min(PLAN_MAX_TOKENS,
                HISTORIAN_TOKENS_BASE
                + HISTORIAN_TOKENS_PER_RESIDENT * residents),
            residents)


def _json_call(system, payload, *, max_tokens=PLAN_MAX_TOKENS,
               temperature=0.5):
    from llm.providers import chat_complete
    # REASONING OFF, EXPLICITLY. Every OpenAI-style seam counts private
    # reasoning against `max_tokens`, so a thinking model spends the plan's
    # whole budget on a trace and returns 8,484 characters of half-written
    # JSON (measured 2026-09-02 with the utility role's effort left to the
    # settings map). These calls are JSON-shaped and the output IS the
    # budget; the provider layer already turns reasoning off on the retry
    # after that failure, and here it is off on the first attempt.
    raw = chat_complete(
        "utility", system, json.dumps(payload, ensure_ascii=False),
        temperature=temperature, max_tokens=max_tokens, json_mode=True,
        reasoning_effort="off")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        # SAY WHICH FAILURE THIS IS. A plan cut off mid-object and a model
        # that returned prose are both `JSONDecodeError`, and only one of them
        # is fixed by asking for less. The tail is what tells them apart.
        raise ValueError(
            "the location generator returned %d characters of unparseable "
            "JSON (%s). If it ends mid-object the plan outran its %d-token "
            "budget -- ask for fewer required_rooms or featured_residents. "
            "Tail: ...%s"
            % (len(raw or ""), exc.msg, max_tokens,
               (raw or "")[-160:].replace("\n", " "))) from exc
    if not isinstance(value, dict):
        raise ValueError("town generator returned a non-object")
    return value


def propose_town(lore, brief="", *, constraints=None, model_call=None):
    payload = {"lore": lore, "author_brief": str(brief or "")}
    if isinstance(constraints, dict):
        payload.update({
            key: copy.deepcopy(constraints[key])
            for key in ("scale", "topology", "required_rooms",
                        "featured_residents", "population")
            if constraints.get(key) not in (None, "", [])})
    return (model_call or (lambda p: _json_call(_PLAN_SYSTEM, p)))(payload)


def propose_history(plan, lore, horizon_hours, *, model_call=None):
    payload = {"town_plan": plan, "lore": lore,
               "horizon_hours": float(horizon_hours)}
    return (model_call or (lambda p: _json_call(
        _HISTORY_SYSTEM, p, max_tokens=4000, temperature=0.55)))(payload)


def _rate(span, floor, restoring=False):
    table = RESTORE_HOURS if restoring else FAIL_HOURS
    hours = table.get(str(span), table["a_shift" if restoring else "a_week"])
    return round((1.0 - float(floor)) / max(1.0, hours), 8)


def _key(value, fallback):
    text = str(value or fallback).strip()
    return text or fallback


def _mapping(value):
    """A model-authored object, or an empty object without coercion traps."""
    return dict(value) if isinstance(value, dict) else {}


def _strings(value):
    """Normalize one label or a JSON list without splitting strings to chars."""
    if value in (None, ""):
        return []
    values = value if isinstance(value, (list, tuple, set)) else [value]
    return [str(item) for item in values if str(item or "").strip()]


def _competence(value):
    """Accept both ranked maps and the common model shorthand list of tags."""
    if isinstance(value, dict):
        return {
            str(tag): max(0, _integer(level, 1))
            for tag, level in value.items() if str(tag or "").strip()
        }
    return {tag: 1 for tag in _strings(value)}


def _head_posts(posts):
    """The posts nobody reports past and somebody reports to.

    Read from `reports_to` alone, the signal docs/UNBUILT.md 1.84b found
    already in the data. A post with no superior AND no subordinate is not a
    head, it is a lone watch -- the smith of a one-post smithy rotates like
    any other duty. A chain has to have been authored for a top to exist.
    """
    superiors = {}
    for key, post in (posts or {}).items():
        if not isinstance(post, dict):
            continue
        superior = str(post.get("reports_to") or "")
        # A post reporting to ITSELF has no superior: planners write the top
        # of a chain that way ("reeve reports to reeve"), and
        # `charter_runtime` refuses the self-edge on validation anyway.
        superiors[str(key)] = "" if superior == str(key) else superior
    reported_to = {sup for sup in superiors.values() if sup in superiors}
    return {key for key, sup in superiors.items()
            if not sup and key in reported_to}


def _post_seats(posts):
    """{post: exact holder count} for every post whose headcount is fixed.

    Three ways a post fixes its headcount, in the order they are honoured:
    an authored `seats` (docs/UNBUILT.md 1.84e's shape (a) -- posts gain a
    headcount), an authored `singular` flag, or being a head of the chain
    (`_head_posts`). A post in this map is neither topped to a crew nor
    scaled with the population; it holds exactly what it says.
    """
    seats = {}
    heads = _head_posts(posts)
    for key, post in (posts or {}).items():
        post = post if isinstance(post, dict) else {}
        explicit = post.get("seats")
        if explicit not in (None, ""):
            seats[str(key)] = max(1, _integer(explicit, 1))
        elif post.get("singular") or str(key) in heads:
            seats[str(key)] = HEAD_SEATS
    return seats


def _ensure_shift_crews(bodies, posts, *, crew_size=CREW_SIZE, seats=None):
    """Give every generated continuous post a real rotation -- and every
    fixed-seat post exactly its seats.

    Charter's post primitive is a watch, not a nine-to-five job: if a post is
    present it is planned every window. Model-authored populations commonly
    put one leader behind one office, which makes that person work twenty-four
    hours a day until needs correctly stand them down. Deterministic closure
    supplies three post-specific bodies so routine fatigue rotates quietly.

    Post-specific ids make the coverage guarantee structural. Counting all
    broadly competent bodies would let the same three administrators appear
    to cover four simultaneous offices.

    ``seats`` (`_post_seats`) is the complement: a post whose headcount is
    fixed is TRIMMED to it as well as topped to it. Measured on a generated
    starship the rotation floor produced three captains (docs/UNBUILT.md
    1.84b), and on a generated town three reeves and three innkeepers -- an
    address resolving to three minds. Trimming drops generated bodies from
    the highest index down and never a featured resident, who was placed at
    that post under a registered name on purpose.

    Returns ``(added, trimmed)``, both lists of body keys.
    """
    bodies = bodies if isinstance(bodies, dict) else {}
    seats = seats if isinstance(seats, dict) else {}
    added, trimmed = [], []
    crew_size = max(1, int(crew_size))
    for post_key, post in sorted((posts or {}).items()):
        prefix = f"{post_key}:"
        own = sorted(key for key in bodies if str(key).startswith(prefix))
        target = int(seats.get(post_key, crew_size))
        if post_key in seats:
            surplus = [key for key in reversed(own)
                       if ":featured:" not in str(key)]
            while len(own) > target and surplus:
                victim = surplus.pop(0)
                bodies.pop(victim, None)
                own.remove(victim)
                trimmed.append(victim)
        template = dict(bodies[own[0]]) if own else {}
        competence = _competence(template.get("competence"))
        for tag, level in _competence(post.get("requires")).items():
            competence[tag] = max(competence.get(tag, 0), level)
        place = str(post.get("place") or template.get("place") or "")
        while len(own) < target:
            index = len(own) + 1
            body_id = f"{post_key}:{index:04d}"
            while body_id in bodies:
                index += 1
                body_id = f"{post_key}:{index:04d}"
            bodies[body_id] = {
                "competence": dict(competence),
                "place": place,
                "berth": str(template.get("berth") or place),
                "available": True,
                "home_post": str(post_key),
                "rank": str(template.get("rank") or ""),
            }
            own.append(body_id)
            added.append(body_id)
    return added, trimmed


def _population_counts(raw):
    """{post: authored count} for one raw charter's populations."""
    counts = {}
    for pi, population in enumerate(raw.get("populations") or ()):
        if not isinstance(population, dict):
            continue
        post = str(population.get("post") or f"role_{pi + 1}")
        counts[post] = counts.get(post, 0) + max(
            0, min(5000, _integer(population.get("count"))))
    return counts


def _projected_bodies(raw, factor, seats, crew_size=CREW_SIZE):
    """How many bodies one raw charter closes to at a population factor.

    Mirrors closure without running it: a fixed-seat post holds its seats,
    every other post holds max(round(factor x authored), crew), and an
    upkeep no post serves mints one crewed duty post unless a post already
    stands at its place. Exact enough for a bisection; the tolerance covers
    the rest.
    """
    posts = {str(k): (v if isinstance(v, dict) else {})
             for k, v in _mapping(raw.get("posts")).items()}
    scaled = {}
    for pi, population in enumerate(raw.get("populations") or ()):
        if not isinstance(population, dict):
            continue
        post = str(population.get("post") or f"role_{pi + 1}")
        count = max(0, min(5000, _integer(population.get("count"))))
        # Per ENTRY, as closure rounds: two populations of four at one post
        # scale to 3 + 3, not round(8 x factor).
        scaled[post] = scaled.get(post, 0) + (
            max(1, int(round(count * factor))) if count else 0)
    total = 0
    for post in sorted(set(posts) | set(scaled)):
        if post in seats:
            total += int(seats[post])
            continue
        total += max(scaled.get(post, 0), crew_size)
    served = set()
    places = {str(post.get("place") or "") for post in posts.values()}
    for post in posts.values():
        served.update(_strings(post.get("serves")))
    for upkeep_key, upkeep in _mapping(raw.get("upkeeps")).items():
        upkeep = upkeep if isinstance(upkeep, dict) else {}
        if str(upkeep_key) in served:
            continue
        if str(upkeep.get("place") or "") not in places:
            total += crew_size
    return total


def _scale_populations(plan, target, seats_by_charter):
    """Scale a plan's population counts so closure lands near ``target``.

    The planner is told the number and does not reliably hit it -- the same
    brief closed to 14 bodies on one run and 108 on the next -- so the
    requested population is a CLOSURE INPUT. Fixed-seat posts are never
    scaled (a head is one person whatever the town's size), the crew floor
    is respected (a post cannot be scaled below its rotation), and the factor
    is found by bisection over the projected closed total, which is monotone
    in it. Rewrites `populations[].count` on the plan in place and returns the
    record; a plan with no target is returned untouched.
    """
    charters = [raw for raw in (plan.get("charters") or ())[:8]
                if isinstance(raw, dict)]
    record = {"target": None, "authored": None, "projected": None,
              "factor": 1.0}
    if target is None or not charters:
        return record
    target = max(1, int(target))

    def projected(factor):
        return sum(_projected_bodies(raw, factor, seats_by_charter[ci])
                   for ci, raw in enumerate(charters))

    authored = projected(1.0)
    record.update({"target": target, "authored": authored})
    low, high = 0.0, 1.0
    while projected(high) < target and high < 4096:
        high *= 2
    for _ in range(64):
        mid = (low + high) / 2
        if projected(mid) < target:
            low = mid
        else:
            high = mid
    # Two candidates straddle the target; take the nearer, the lower on a tie
    # -- fewer invented people is the conservative miss.
    factor = min((low, high), key=lambda f: (abs(projected(f) - target), f))
    for ci, raw in enumerate(charters):
        seats = seats_by_charter[ci]
        for pi, population in enumerate(raw.get("populations") or ()):
            if not isinstance(population, dict):
                continue
            post = str(population.get("post") or f"role_{pi + 1}")
            if post in seats:
                continue
            count = max(0, min(5000, _integer(population.get("count"))))
            if count:
                population["count"] = max(1, int(round(count * factor)))
    record.update({"projected": projected(factor), "factor": factor})
    return record


def _post_berths(post, upkeeps, room_ids, requested_place, default_place):
    """Where a population's bodies sleep, in the order they are dealt.

    A BODY SLEEPS WHERE THE WORK IT SERVES IS. The plan's own place for the
    population wins when it named one; otherwise a post that serves upkeeps
    in several places is dealt round those places, one body to each in
    turn, and only a post whose work is in one place berths everyone at
    that place. A post's single `place` is the watch bill's, not the
    sleeper's: the planner writes one generic post for every household of
    a town ("household_member", serving `keep_house_*` for ten houses) and
    gives it one address, and read as a berth that address held 48
    sleepers behind one door while nine houses held three each
    (Harrowmere replay, 2026-09-03) -- the berth split then hung five
    annexes off the one house rather than fill the nine.
    """
    if requested_place in room_ids:
        return [requested_place]
    served = sorted({
        str((upkeeps.get(key) or {}).get("place") or "")
        for key in _strings(post.get("serves"))} & set(room_ids))
    if len(served) > 1:
        return served
    return [str(post.get("place") or default_place)]


def _spread_berths(rooms, charter_bodies, ceiling=BERTH_CEILING):
    """Split a berth over its ceiling into rooms beside it.

    A berth room holding more than ``ceiling`` sleepers is split one of two
    ways, and the engine's own vocabulary decides which -- WORK is serving
    an upkeep, so a room where one is served (placed there, or served by a
    post placed there) is a workplace and every other berth is a dwelling:

      * a DWELLING gets siblings: same purpose, same neighbours, reciprocal
        edges on those neighbours, an ordinal on the name -- more houses on
        the same lane -- and its sleepers are dealt across the set;
      * a WORKPLACE keeps its first ``ceiling`` sleepers and the overflow
        moves into annexes hung off it, which claim no purpose: the plan
        does not know what an inn's staff sleep in, and the Director
        furnishes a planned room on entry (`structure.planned_room_brief`),
        so an empty seed is a room it will write rather than a room the
        closer guessed at.

    `place` follows `berth` for a body that was standing at home.
    ``charter_bodies`` is ``[(charter_key, bodies_dict, work_places)]``.
    Mutates ``rooms`` and the bodies in place. Returns
    ``{berth: {"mode": "siblings"|"annexes", "rooms": [ids]}}``.
    """
    occupancy = {}
    workplaces = set()
    for ckey, bodies, places in charter_bodies:
        workplaces.update(str(place) for place in places or () if str(place))
        for bkey, body in (bodies or {}).items():
            berth = str(body.get("berth") or "")
            if berth in rooms:
                occupancy.setdefault(berth, []).append((str(ckey), str(bkey)))
    by_charter = {str(ckey): bodies for ckey, bodies, _p in charter_bodies}
    minted = {}
    for berth in sorted(occupancy):
        sleepers = sorted(occupancy[berth])
        if len(sleepers) <= ceiling:
            continue
        base = rooms[berth] if isinstance(rooms.get(berth), dict) else {}
        annexes = berth in workplaces
        needed = -(-len(sleepers) // ceiling)
        new_rooms = []
        index = 2
        while len(new_rooms) + 1 < needed:
            uid = f"{berth}_{index}"
            while uid in rooms:
                index += 1
                uid = f"{berth}_{index}"
            if annexes:
                edges = [{"to": berth, "barrier": "open_door"}]
                purpose = ""
            else:
                edges = [dict(edge) for edge in base.get("adjacent") or ()
                         if isinstance(edge, dict) and edge.get("to")]
                purpose = str(base.get("purpose") or "")
            rooms[uid] = {
                "name": f"{base.get('name') or berth} {index}",
                "purpose": purpose,
                "adjacent": edges,
                "frontier": [],
            }
            for edge in edges:
                neighbour = rooms.get(str(edge["to"]))
                if isinstance(neighbour, dict):
                    neighbour.setdefault("adjacent", []).append(
                        {"to": uid,
                         "barrier": str(edge.get("barrier") or "open_door")})
            new_rooms.append(uid)
            index += 1
        if annexes:
            assignment = [berth] * ceiling
            for uid in new_rooms:
                assignment.extend([uid] * ceiling)
        else:
            cycle = [berth] + new_rooms
            assignment = [cycle[n % len(cycle)] for n in range(len(sleepers))]
        for n, (ckey, bkey) in enumerate(sleepers):
            new_berth = assignment[n]
            body = by_charter[ckey][bkey]
            if str(body.get("place") or "") == berth:
                body["place"] = new_berth
            body["berth"] = new_berth
        minted[berth] = {"mode": "annexes" if annexes else "siblings",
                         "rooms": new_rooms}
    return minted


def _words(value):
    import re
    return set(re.findall(r"[a-z0-9]+", str(value or "").casefold()))


def _featured_assignments(plan, residents):
    """Assign authored residents once, with a deterministic omission repair.

    The planner gets first refusal because lore vocabulary is semantic. If it
    omits somebody, lexical overlap with the actual post requirements chooses
    a conservative existing post; closure never drops an authored resident or
    asks a second model call merely to repair a list omission.
    """
    residents = {
        str(row.get("seed_id")): copy.deepcopy(row)
        for row in residents or () if isinstance(row, dict)
        and str(row.get("seed_id") or "").strip()
    }
    assigned = {}
    charters = [row for row in (plan.get("charters") or ())[:8]
                if isinstance(row, dict)]
    for ci, charter in enumerate(charters):
        for row in charter.get("featured_residents") or ():
            if not isinstance(row, dict):
                continue
            seed_id = str(row.get("seed_id") or "")
            if seed_id in residents and seed_id not in assigned:
                assigned[seed_id] = (ci, copy.deepcopy(row))
    for seed_id, resident in residents.items():
        if seed_id in assigned or not charters:
            continue
        resident_words = _words(resident.get("public_history"))
        for ability in resident.get("abilities") or ():
            if isinstance(ability, dict):
                resident_words |= _words(" ".join(str(v) for v in ability.values()))
            else:
                resident_words |= _words(ability)
        options = []
        for ci, charter in enumerate(charters):
            for post_key, post in _mapping(charter.get("posts")).items():
                post = post if isinstance(post, dict) else {}
                surface = " ".join([
                    str(post_key), str(post.get("serves") or ""),
                    str(post.get("requires") or "")])
                score = len(resident_words.intersection(_words(surface)))
                options.append((-score, ci, str(post_key)))
        if options:
            _neg, ci, post_key = min(options)
            assigned[seed_id] = (ci, {"seed_id": seed_id, "post": post_key})
    return residents, assigned


def close_plan(plan, *, history=None, featured_residents=None,
               reservation=None, naming_law=None, population=None):
    """Convert qualitative model output to bounded executable structures.

    ``reservation`` is the story's registered identity forms
    (`charter_identity.identity_reservation`). The model proposes the naming
    law from the same lore that supplied the cast, so its pools arrive
    carrying the cast's own name elements: measured 2026-08-27 on chat 95,
    where 42 generated bodies drew from a family pool holding the registered
    crew's surnames under ``{rank} {family}``, and two of them landed on
    them. Both subtractions land before anything persists: the mint refuses
    a reserved candidate, and `normalize_charter` -- which closes every
    charter this returns -- removes the reserved elements from the law it
    STORES, so no later reader is offered them again.

    ``naming_law``, when the story has an authored one, replaces the derived
    law for every charter in this plan. `story/naming.py` already ranks an
    authored profile above a Charter's own; a mint that ignored that ranking
    would be a second naming authority beside the story's.

    ``population``, when the author gave a number, is a CLOSURE INPUT rather
    than a hope in the brief: `_scale_populations` scales the plan's
    population counts so the closed total lands within
    `POPULATION_TOLERANCE` of it, and the returned ``closure`` record says
    what was asked, what the planner wrote, and what closed. The same record
    carries the head posts held to `HEAD_SEATS`, the dwellings split at
    `BERTH_CEILING`, and the warnings each invariant raised.
    """
    from world.charter_identity import (normalize_naming_profile,
                                    refuse_harvested_material)

    plan = copy.deepcopy(plan) if isinstance(plan, dict) else {}
    closure_warnings = []
    raw_charters = [raw for raw in (plan.get("charters") or ())[:8]
                    if isinstance(raw, dict)]
    seats_by_charter = [_post_seats(_mapping(raw.get("posts")))
                        for raw in raw_charters]
    population_record = _scale_populations(
        plan, population, seats_by_charter)
    structure = _mapping(plan.get("structure"))
    structure["key"] = _key(structure.get("key"), "town")
    rooms = {}
    for uid, raw in _mapping(plan.get("rooms")).items():
        if not isinstance(raw, dict):
            continue
        rooms[str(uid)] = {
            "name": str(raw.get("name") or uid),
            "purpose": str(raw.get("purpose") or ""),
            "adjacent": [dict(e) for e in raw.get("adjacent") or ()
                         if isinstance(e, dict) and e.get("to")],
            "frontier": [str(x) for x in raw.get("frontier") or () if str(x)],
        }
    room_ids = set(rooms)
    default_place = next(iter(rooms), "")
    # THE SETTING'S NAMES FOR PLACES, kept for the naming step. A place is
    # not a person, so this vocabulary is material where a name list is not
    # -- see `refuse_harvested_material`. Read only where refusing the pieces
    # of people out of a law's fragments left a field with nothing.
    #
    # NAMES ONLY, never a room's `purpose`: a purpose is a sentence about
    # what happens somewhere, and its ordinary connecting words would supply
    # ordinary connecting syllables. A place NAME is a proper noun the
    # setting chose, which is the closest thing to its phonology that names
    # nobody.
    place_words = [str(plan.get("name") or ""), str(structure.get("key") or "")]
    place_words.extend(str(room.get("name") or "") for room in rooms.values())
    charters = {}
    pending = []
    resident_sources, resident_assignments = _featured_assignments(
        plan, featured_residents)
    interventions = list((history or {}).get("interventions") or ())
    for ci, raw in enumerate(raw_charters):
        ckey = _key(raw.get("key"), f"institution_{ci + 1}")
        upkeeps = {}
        for uid, upkeep in (raw.get("upkeeps") or {}).items():
            upkeep = upkeep if isinstance(upkeep, dict) else {}
            floor = max(0.05, min(
                0.9, _number(upkeep.get("floor"), 0.25)))
            upkeeps[str(uid)] = {
                "place": str(upkeep.get("place") or ""),
                "floor": floor,
                "level": max(0.0, min(
                    1.0, _number(upkeep.get("level"), 1.0))),
                "drift_per_hour": _rate(
                    upkeep.get("fails_untended"), floor),
                "service_per_hour": _rate(
                    upkeep.get("one_body_restores_in"), floor, True),
                "requires": _competence(upkeep.get("requires")),
                "depends_on": _strings(upkeep.get("depends_on")),
            }
        posts = {str(k): dict(v) for k, v in _mapping(raw.get("posts")).items()
                 if isinstance(v, dict)}
        for post in posts.values():
            post["serves"] = _strings(post.get("serves"))
            post["requires"] = _competence(post.get("requires"))
            if str(post.get("place") or "") not in room_ids:
                post["place"] = default_place
            dress = post_dress(post)
            post.pop("worn", None)
            post.pop("marks", None)
            if dress["worn"]:
                post["worn"] = dress["worn"]
            if dress["marks"]:
                post["marks"] = dress["marks"]
        bodies = {}
        for pi, population in enumerate(raw.get("populations") or ()):
            if not isinstance(population, dict):
                continue
            count = max(0, min(5000, _integer(population.get("count"))))
            post = str(population.get("post") or f"role_{pi + 1}")
            competence = _competence(population.get("competence"))
            requested_place = str(population.get("place") or
                                  population.get("berth") or "")
            if post not in posts:
                posts[post] = {
                    "place": (requested_place if requested_place in room_ids
                              else default_place),
                    "serves": [], "requires": dict(competence),
                }
            required = _competence(posts[post].get("requires"))
            # A population authored FOR a post is capable of that post. Loose
            # model vocabulary ("high", "standard") may add texture but may
            # not make the generated institution incapable of staffing itself.
            for tag, level in required.items():
                competence[tag] = max(competence.get(tag, 0), level)
            berths = _post_berths(posts[post], upkeeps, room_ids,
                                  requested_place, default_place)
            existing = sum(1 for body_id in bodies
                           if body_id.startswith(f"{post}:"))
            for index in range(count):
                body_id = f"{post}:{existing + index + 1:04d}"
                berth = berths[(existing + index) % len(berths)]
                bodies[body_id] = {
                    "competence": competence,
                    "place": berth, "berth": berth, "available": True,
                    "home_post": post,
                    "rank": str(population.get("rank") or ""),
                }
        for seed_id, (assigned_ci, assignment) in resident_assignments.items():
            if assigned_ci != ci:
                continue
            source = resident_sources[seed_id]
            post = str(assignment.get("post") or "")
            competence = _competence(assignment.get("competence"))
            requested_place = str(assignment.get("berth") or "")
            if post not in posts:
                post = post or "resident"
                posts[post] = {
                    "place": (requested_place if requested_place in room_ids
                              else default_place),
                    "serves": [], "requires": dict(competence),
                }
            for tag, level in _competence(posts[post].get("requires")).items():
                competence[tag] = max(competence.get(tag, 0), level)
            berth = (requested_place if requested_place in room_ids
                      else str(posts[post].get("place") or default_place))
            suffix = hashlib.sha1(seed_id.encode("utf-8")).hexdigest()[:10]
            body_id = f"{post}:featured:{suffix}"
            bodies[body_id] = {
                "name": str(source.get("name") or body_id),
                "resident_seed_id": seed_id,
                "competence": competence,
                "place": berth, "berth": berth, "available": True,
                "home_post": post,
                "rank": str(assignment.get("rank") or ""),
                "title": str(assignment.get("title") or ""),
            }
        # An upkeep nobody can even attempt to serve is malformed generation,
        # not an interesting institutional failure. Attach it to a co-located
        # post when possible; otherwise mint one mechanically neutral duty.
        for upkeep_key, upkeep in upkeeps.items():
            if any(upkeep_key in _strings(post.get("serves"))
                   for post in posts.values()):
                continue
            candidates = [key for key, post in posts.items()
                          if post.get("place") == upkeep.get("place")]
            if candidates:
                chosen = sorted(candidates)[0]
            else:
                chosen = _key(f"{upkeep_key}_duty", "upkeep_duty")
                suffix = 2
                base = chosen
                while chosen in posts:
                    chosen = f"{base}_{suffix}"
                    suffix += 1
                posts[chosen] = {
                    "place": upkeep.get("place") or default_place,
                    "serves": [],
                    "requires": dict(upkeep.get("requires") or {}),
                }
            posts[chosen]["serves"] = sorted(set(
                _strings(posts[chosen].get("serves")) + [upkeep_key]))
        seats = _post_seats(posts)
        staffing_reserve_added, staffing_trimmed = _ensure_shift_crews(
            bodies, posts, seats=seats)
        if naming_law:
            # The story's own authored law, ranked above a generated one by
            # `story/naming.py`. An author's list is theirs.
            naming = normalize_naming_profile(naming_law)
        else:
            # The planner's law, written by a model reading this story's lore
            # -- and reading its own knowledge of the setting, which no
            # reservation reaches. Its name lists are the people the lore
            # names and its fragments are those people cut up; neither is
            # material. See `refuse_harvested_material`, which also answers
            # "and then what does the mint read".
            naming = refuse_harvested_material(
                raw.get("naming"), reservation,
                place_words + [str(raw.get("name") or ""), ckey])
        bodies = materialize_body_names(ckey, bodies, naming, reservation)
        # THE LOOK LAW, dealt now so the stored registry carries every
        # surface and a replay is byte-identical. A plan without one gets
        # the engine's default pools and says so: a hundred bodies dealt
        # from six words an axis will repeat, and the author should know
        # the town is wearing the engine's face rather than its own.
        looks = normalize_looks_profile(raw.get("looks"))
        if looks_material_exists(looks):
            look_source = "authored"
        else:
            looks, look_source = default_looks(), "default"
            closure_warnings.append(
                f"{ckey!r} authored no look law; bodies dealt from the "
                f"engine's default pools")
        for body_id, body in bodies.items():
            body["surface"] = deal_surface(
                ckey, body_id, looks,
                post=posts.get(str(body.get("home_post") or "")),
                source=look_source)
        from world.charter_economy import ensure_supply_points
        economy = ensure_supply_points(
            copy.deepcopy(raw.get("economy") or {}), rooms)
        local_interventions = []
        for entry in interventions:
            if not isinstance(entry, dict):
                continue
            if entry.get("charter") and str(entry["charter"]) != ckey:
                continue
            if entry.get("upkeep") and str(entry["upkeep"]) not in upkeeps:
                continue
            if entry.get("body") and str(entry["body"]) not in bodies:
                continue
            local_interventions.append(entry)
        history_record = copy.deepcopy(history or {})
        history_record["closure"] = {
            "staffing_model": "three_person_continuous_watch",
            "staffing_reserve_added": list(staffing_reserve_added),
            "staffing_trimmed": list(staffing_trimmed),
            "seats": dict(seats),
        }
        commons = [place for place in _strings(raw.get("commons"))
                   if place in room_ids]
        # WORK IS SERVING AN UPKEEP: the places upkeeps live, and the places
        # of the posts that serve one. Read by `_spread_berths` to tell a
        # workplace from a dwelling without reading a word of purpose.
        work_places = {str(upkeep.get("place") or "")
                       for upkeep in upkeeps.values()}
        work_places.update(
            str(post.get("place") or "") for post in posts.values()
            if _strings(post.get("serves")))
        pending.append((ckey, {
            "key": ckey, "structure": structure["key"],
            "upkeeps": upkeeps, "posts": posts, "bodies": bodies,
            "naming": naming,
            "looks": looks,
            "priority": _strings(raw.get("priority")),
            # Where its people go for their own sake, as distinct from where
            # its work is. Filtered to real rooms here for the same reason
            # `post.place` is: a place id the plan never minted is not a place.
            "commons": commons,
            "economy": economy,
            "decisions": raw.get("decisions") or {},
            "interventions": local_interventions,
            "history": {"architecture": history_record},
        }, work_places))
    # BERTHS ARE SPREAD ACROSS EVERY CHARTER BEFORE ANY IS NORMALIZED. A
    # dwelling is a room, and rooms are the town's; a house that the
    # households charter and the inn's staff both berth in overflows as one
    # room, so the split has to see every charter's sleepers at once.
    minted_dwellings = _spread_berths(
        rooms, [(ckey, state["bodies"], places)
                for ckey, state, places in pending])
    if minted_dwellings:
        structure["max_planned"] = max(
            len(rooms), _integer(structure.get("max_planned"), len(rooms)))
        for berth, record in sorted(minted_dwellings.items()):
            closure_warnings.append(
                f"{berth!r} berthed more than {BERTH_CEILING} sleepers; "
                f"{len(record['rooms'])} {record['mode']} minted "
                f"({', '.join(record['rooms'])})")
    heads = {}
    for ckey, state, _places in pending:
        state["needs"] = seed_needs(state["bodies"])
        charter = normalize_charter(state, reservation)
        charter["roster"] = seed_roster(charter["bodies"])
        charters[ckey] = charter
        for post_key, count in sorted(
                (state["history"]["architecture"]["closure"]["seats"]
                 or {}).items()):
            heads[f"{ckey}/{post_key}"] = count
    closed_total = sum(len(state["bodies"]) for state in charters.values())
    population_record["closed"] = closed_total
    target = population_record.get("target")
    if target is not None:
        miss = abs(closed_total - target)
        if miss > POPULATION_TOLERANCE * target:
            closure_warnings.append(
                f"population closed to {closed_total} against a requested "
                f"{target} (planner wrote {population_record['authored']}; "
                f"tolerance {POPULATION_TOLERANCE:.0%})")
    return {"version": GENERATION_VERSION,
            "name": str(plan.get("name") or structure["key"]),
            "structure": structure, "rooms": rooms, "charters": charters,
            "featured_residents": {
                seed_id: {"name": source.get("name"),
                          "placed": seed_id in resident_assignments}
                for seed_id, source in resident_sources.items()},
            "closure": {
                "population": population_record,
                "heads": heads,
                "berths_split": minted_dwellings,
                "warnings": closure_warnings,
            },
            }


def ensure_required_rooms(town, required):
    """Close explicit author-required anchors into the planned skeleton.

    The model gets first refusal so it can integrate them naturally. Any it
    omitted become prose-free planned rooms, connected only by the topology
    the author supplied (or to the first standing anchor as a safe fallback).
    """
    from world.spatial import normalize_room_id

    town = town if isinstance(town, dict) else {}
    rooms = town.setdefault("rooms", {})
    specs = []
    for index, raw in enumerate(required or ()):
        raw = {"name": raw} if isinstance(raw, str) else raw
        if not isinstance(raw, dict):
            continue
        uid = normalize_room_id(raw.get("id") or raw.get("name") or
                                f"required_{index + 1}")
        if not uid:
            continue
        specs.append((uid, raw))
    added = []
    fallback = next(iter(rooms), "")
    required_ids = {uid for uid, _raw in specs}
    for uid, raw in specs:
        existed = uid in rooms
        room = dict(rooms.get(uid) or {})
        room["name"] = str(raw.get("name") or room.get("name") or uid)
        room["purpose"] = str(
            raw.get("purpose") or room.get("purpose") or "support")
        room["frontier"] = _strings(
            raw.get("frontier") if "frontier" in raw
            else room.get("frontier"))
        authored_edges = _strings(raw.get("adjacent"))
        edges = [dict(edge) for edge in room.get("adjacent") or ()
                 if isinstance(edge, dict) and edge.get("to")]
        if authored_edges:
            edges = [{"to": target, "barrier": str(
                raw.get("barrier") or "open_door")}
                     for target in authored_edges
                     if target in rooms or target in required_ids]
        elif not edges and fallback and fallback != uid:
            edges = [{"to": fallback, "barrier": "open_door"}]
        room["adjacent"] = edges
        rooms[uid] = room
        if not existed:
            added.append(uid)
        if not fallback:
            fallback = uid
    structure = town.setdefault("structure", {})
    structure["max_planned"] = max(
        len(rooms), _integer(structure.get("max_planned"), len(rooms)))
    return added


def event_chronicle(events):
    rows = []
    for index, event in enumerate(events or ()):
        material = json.dumps(event, sort_keys=True, ensure_ascii=False)
        event_id = "presim:" + hashlib.sha256(
            f"{index}|{material}".encode("utf-8")).hexdigest()[:16]
        rows.append({"event_id": event_id, **copy.deepcopy(event)})
    return rows


def resident_service_chronicle(registry, resident_ids):
    """Bounded historical evidence derived from aggregate simulation state.

    A quiet institution deliberately emits no per-window events, so its people
    otherwise appear to have no past precisely because they did their jobs.
    ``stood`` and ``travelled`` are bounded service records already maintained
    for promotion. Turning each selected resident's aggregate into one cited
    row gives the historian evidence of a career without inventing episodes or
    growing storage with time.
    """
    rows = []
    for resident_id in resident_ids or ():
        charter_key, divider, body_id = str(resident_id).partition("/")
        if not divider:
            continue
        item = (registry.get("items") or {}).get(charter_key) or {}
        state = item.get("state") or {}
        body = (state.get("bodies") or {}).get(body_id)
        if not isinstance(body, dict):
            continue
        stood = {
            str(post): max(0, _integer(windows))
            for post, windows in ((state.get("stood") or {}).get(body_id)
                                  or {}).items()
            if _integer(windows) > 0}
        travelled = max(0, _integer(
            (state.get("travelled") or {}).get(body_id)))
        if not stood and not travelled:
            continue
        evidence = {
            "kind": "service_record",
            "charter": charter_key,
            "body": str(resident_id),
            "name": str(body.get("name") or body_id),
            "posts": stood,
            "watches_stood": sum(stood.values()),
            "at_hours": round(float(state.get("clock_hours") or 0.0), 6),
        }
        if travelled > 1:
            evidence["route_edges_travelled"] = travelled
        material = json.dumps(evidence, sort_keys=True, ensure_ascii=False)
        rows.append({
            "event_id": "presim:service:" + hashlib.sha256(
                material.encode("utf-8")).hexdigest()[:16],
            **evidence,
        })
    return rows


def ground_history_output(value, chronicle):
    """Remove unsupported historian turning points, retaining diagnostics."""
    value = value if isinstance(value, dict) else {}
    valid = {str(row.get("event_id")) for row in chronicle}
    out = copy.deepcopy(value)
    dropped = []
    for field in ("overview", "eras", "institutions"):
        raw = out.get(field)
        rows = raw if isinstance(raw, list) else [raw]
        kept = []
        for row in rows:
            if not isinstance(row, dict):
                if row not in (None, ""):
                    dropped.append({"section": field, "claim": row})
                continue
            citations = [str(x) for x in row.get("event_ids") or ()]
            if citations and all(event_id in valid for event_id in citations):
                kept.append(row)
            else:
                dropped.append({"section": field, "claim": row})
        out[field] = kept if isinstance(raw, list) else (kept[0] if kept else {})
    for body, resident in list((out.get("residents") or {}).items()):
        if not isinstance(resident, dict):
            out["residents"].pop(body, None)
            continue
        citations = [str(x) for x in resident.get("event_ids") or ()]
        if str(resident.get("summary") or "").strip() and not (
                citations and all(event_id in valid for event_id in citations)):
            dropped.append({"body": body, "summary": resident.get("summary")})
            resident["summary"] = ""
            citations = []
        resident["event_ids"] = citations
        kept = []
        for point in resident.get("turning_points") or ():
            if isinstance(point, dict) and str(point.get("event_id")) in valid:
                kept.append(point)
            else:
                dropped.append({"body": body, "point": point})
        resident["turning_points"] = kept[:12]
    out["grounding"] = {"cited": sorted({
        str(point.get("event_id"))
        for resident in (out.get("residents") or {}).values()
        if isinstance(resident, dict)
        for point in resident.get("turning_points") or ()
        if isinstance(point, dict)}), "dropped": dropped[:24]}
    return out


def narrate_actual_history(town, registry, events, *, model_call=None):
    candidates = []
    population_context = {}
    for key, item in (registry.get("items") or {}).items():
        state = item.get("state") or {}
        population_context[key] = {
            "residents": len(state.get("bodies") or {}),
            "posts": list((state.get("posts") or {}).keys()),
            "upkeeps": list((state.get("upkeeps") or {}).keys()),
        }
        for body_id, body in (state.get("bodies") or {}).items():
            stood = (state.get("stood") or {}).get(body_id, {})
            candidates.append((
                sum(int(v) for v in stood.values()),
                int((state.get("travelled") or {}).get(body_id, 0)),
                f"{key}/{body_id}", {
                    "name": body.get("name"), "charter": key,
                    "stood": stood,
                    "travelled": (state.get("travelled") or {}).get(body_id, 0),
                }))
    candidates.sort(key=lambda row: (-row[0], -row[1], row[2]))
    budget, afforded = historian_budget(HISTORIAN_RESIDENT_CAP)
    selected = candidates[:afforded]
    call = model_call or (lambda p, budget: _json_call(
        _HISTORIAN_SYSTEM, p, max_tokens=budget, temperature=0.45))
    retries = 0
    while True:
        budget, _n = historian_budget(len(selected))
        chronicle = event_chronicle(events)
        chronicle.extend(resident_service_chronicle(
            registry, [row[2] for row in selected]))
        payload = {
            "town": {"name": town.get("name"),
                     "structure": town.get("structure")},
            "population_context": population_context,
            # One call remains bounded even for a thousand-person location.
            # The overview speaks for the whole population; individual
            # sketches go to the residents with the richest actual
            # service/travel evidence.
            "residents": {row[2]: row[3] for row in selected},
            "chronicle": chronicle,
        }
        try:
            value = _call_historian(call, payload, budget)
            break
        except ValueError as exc:
            # A plan cut off mid-object is the one failure asking for less
            # fixes (`_json_call` names it); prose where JSON should be is
            # not, and is raised as it was.
            if ("unparseable" not in str(exc) or len(selected) <= 1
                    or retries >= HISTORIAN_OVERRUN_RETRIES):
                raise
            retries += 1
            selected = selected[:max(1, len(selected) // 2)]
    out = ground_history_output(value, chronicle)
    out["budget"] = {"max_tokens": budget, "residents": len(selected),
                     "afforded": afforded, "overrun_retries": retries}
    return out


def _call_historian(call, payload, budget):
    """Hand the budget to a caller that takes it; a test double that takes
    only the payload is called the way it always was."""
    try:
        return call(payload, budget)
    except TypeError as exc:
        if "positional" not in str(exc):
            raise
        return call(payload)


__all__ = [
    "BERTH_CEILING", "CREW_SIZE", "HEAD_SEATS", "POPULATION_TOLERANCE",
    "HISTORIAN_RESIDENT_CAP", "HISTORIAN_OVERRUN_RETRIES",
    "HISTORIAN_SUMMARY_WORDS", "HISTORIAN_CITATIONS_PER_ENTRY",
    "HISTORIAN_TURNING_POINTS", "historian_budget",
    "close_plan", "ensure_required_rooms",
    "event_chronicle", "ground_history_output",
    "narrate_actual_history", "propose_history", "propose_town",
    "resident_service_chronicle",
]


#: WHY A MODEL AND NOT A PARSER. Deciding whether a lore entry names an
#: INDIVIDUAL, whether that individual is already one of the story's registered
#: minds, and what post they hold is reading, not matching. Measured
#: 2026-08-28: a real lorebook filed a watch rotation and a set of standing
#: orders under the `character` category, and titled a person's entry "<name>,
#: <role>" so that a parser splitting on the comma got the name and a parser
#: not splitting got neither. Both mistakes are obvious to a reader and
#: invisible to a rule.
#:
#: The output is PLACEMENT EVIDENCE ONLY, exactly as a card-derived seed is:
#: who exists, where they work, what they are called. Nothing here writes a
#: mind, a memory, or a private fact.
_CAST_SYSTEM = """You read a story's lore and pick out the PEOPLE in it.

Return {"residents":[{"entry_id":int,"name":str,"post":str,"rank":str}]}.

Include an entry when it names ONE INDIVIDUAL PERSON who belongs to this
location. Give their name exactly as the lore spells it, without any role or
description attached to it: an entry titled "<name>, <role>" contributes the
name, and the role belongs in `post`.

EXCLUDE, and these are the common cases rather than an exhaustive list:
  * anything that is not a person -- a group, a watch, a rotation, a body of
    standing orders, a ship, a place, an event, a species, a culture;
  * a person already in `registered`, under any spelling of their name. Those
    are the story's own cast and are already present;
  * a person the lore places somewhere else, or who is dead, or who the lore
    says has left.

`post` is the working position they hold, in the vocabulary the lore itself
uses, and `rank` is their standing where the lore gives one; leave `rank`
empty rather than inventing a hierarchy the setting does not have.

Return an empty list rather than reaching. A lorebook about a place with no
named inhabitants is an ordinary thing."""


def lore_cast_residents(entries, registered, *, model_call=None):
    """The lore's named people who are not already the story's cast.

    `entries` are lore rows ({id,title,content}); `registered` are the names
    the story already answers to. Returns placement seeds shaped like
    `charter_history.featured_resident_seed`'s output, keyed `lore:<entry_id>`
    so a second generation places the same person once.

    Never fatal, and never a guess: a failed or unparseable call yields no
    residents, and a location generates with the population it would have had.
    """
    entries = [e for e in (entries or []) if isinstance(e, dict)]
    if not entries:
        return []
    payload = {
        "registered": sorted({str(n).strip() for n in (registered or ())
                              if str(n or "").strip()}),
        "entries": [{"entry_id": e.get("id"),
                     "title": str(e.get("title") or "")[:200],
                     "content": str(e.get("content") or "")[:1200]}
                    for e in entries],
    }
    call = model_call or (lambda system, body: _json_call(
        system, body, max_tokens=4000, temperature=0.2))
    try:
        out = call(_CAST_SYSTEM, payload)
    except Exception:
        return []
    known = {str(e.get("id")): e for e in entries}
    seeds, seen = [], set()
    for row in (out or {}).get("residents") or []:
        if not isinstance(row, dict):
            continue
        entry = known.get(str(row.get("entry_id")))
        name = " ".join(str(row.get("name") or "").split())
        if not entry or not name or name.casefold() in seen:
            continue
        seen.add(name.casefold())
        seeds.append({
            "seed_id": "lore:%s" % entry.get("id"),
            "name": name,
            "post": str(row.get("post") or "").strip(),
            "rank": str(row.get("rank") or "").strip(),
            "public_history": str(entry.get("content") or "")[:4000],
        })
    return seeds
