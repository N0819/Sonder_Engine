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
from world.charter_model import (
    integer as _integer, normalize_charter, number as _number)
from world.charter_needs import seed_needs
from world.charter_roster import seed_roster


FAIL_HOURS = {"days": 72.0, "a_week": 168.0, "weeks": 336.0,
              "a_season": 720.0}
RESTORE_HOURS = {"hours": 6.0, "a_shift": 12.0, "days": 72.0}
GENERATION_VERSION = 1
HISTORIAN_RESIDENT_CAP = 240


_PLAN_SYSTEM = """You design one inhabited location from supplied lore.
Return one JSON object and no prose outside it. Do not invent an institution
unless the lore or author brief implies one. Output: {name, structure:{key,
max_planned, grammar:[{kind,names,purposes}]}, rooms:{id:{name,purpose,
adjacent:[{to,barrier:"open_door"}],frontier:[]}}, charters:[{key,name,naming,
priority,upkeeps:{id:{place,floor,level,fails_untended,one_body_restores_in,
requires,depends_on}},posts:{id:{place,serves,requires,reports_to,authority}},
populations:[{post,count,competence,berth,rank}],economy:{goods,stocks,targets,
flows,markets},decisions:{policies}}]}. Use qualitative timescales only; never
write drift_per_hour or service_per_hour. Planned rooms contain no prose.
Preserve exact canonical lore names and naming style. Keep authority/actions
genre neutral. IDs are stable machine keys; names retain canonical spelling.
Every population.post MUST name an entry in posts, every place and berth MUST
be a rooms id, population competence MUST meet that post's numeric requires,
and every upkeep id MUST occur in at least one post.serves. Charter posts are
continuous watches, so provide at least three people for each post unless the
brief explicitly calls for a dangerously short-handed institution. Use competence and
requires objects like {"medicine":2}, never vague levels or lists. Naming is
{seed,given:[...],family:[...],name_format,formal_format,titles:{posts:{},
ranks:{}}}; supply lore-compatible pools large enough for the population when
the lore permits ordinary personal names. Every generated body must resolve to
a stable scene-facing personal name before simulation. If the setting does not
use ordinary names, supply lore-compatible callsigns, serial names, epithets or
syllable parts; never expose a post/body machine id as the person's name.
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
relationship, quote, or outcome. Omit anything the chronicle cannot support."""


#: Token budget for one generation call. A location plan grows with the rooms
#: and posts it has to describe, and a Galaxy-class starship with six required
#: rooms and five placed officers overran the old fixed 6000 -- which arrived
#: as a `JSONDecodeError` from `json.loads` on a half-written object, roughly
#: 24,000 characters in, naming a line and column in output nobody had asked
#: to see. The budget is generous because the failure is expensive: the call
#: has already been paid for by the time the truncation is discovered.
PLAN_MAX_TOKENS = 16000


def _json_call(system, payload, *, max_tokens=PLAN_MAX_TOKENS,
               temperature=0.5):
    from llm.providers import chat_complete
    raw = chat_complete(
        "utility", system, json.dumps(payload, ensure_ascii=False),
        temperature=temperature, max_tokens=max_tokens, json_mode=True)
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
                        "featured_residents")
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


def _ensure_shift_crews(bodies, posts, *, crew_size=3):
    """Give every generated continuous post a real rotation.

    Charter's post primitive is a watch, not a nine-to-five job: if a post is
    present it is planned every window. Model-authored populations commonly
    put one leader behind one office, which makes that person work twenty-four
    hours a day until needs correctly stand them down. Deterministic closure
    supplies three post-specific bodies so routine fatigue rotates quietly.

    Post-specific ids make the coverage guarantee structural. Counting all
    broadly competent bodies would let the same three administrators appear
    to cover four simultaneous offices.
    """
    bodies = bodies if isinstance(bodies, dict) else {}
    added = []
    crew_size = max(1, int(crew_size))
    for post_key, post in sorted((posts or {}).items()):
        prefix = f"{post_key}:"
        own = sorted(key for key in bodies if str(key).startswith(prefix))
        template = dict(bodies[own[0]]) if own else {}
        competence = _competence(template.get("competence"))
        for tag, level in _competence(post.get("requires")).items():
            competence[tag] = max(competence.get(tag, 0), level)
        place = str(post.get("place") or template.get("place") or "")
        while len(own) < crew_size:
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
    return added


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
               reservation=None, naming_law=None):
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
    """
    from world.charter_identity import normalize_naming_profile

    plan = plan if isinstance(plan, dict) else {}
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
    charters = {}
    resident_sources, resident_assignments = _featured_assignments(
        plan, featured_residents)
    interventions = list((history or {}).get("interventions") or ())
    for ci, raw in enumerate((plan.get("charters") or ())[:8]):
        if not isinstance(raw, dict):
            continue
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
            berth = (requested_place if requested_place in room_ids
                      else str(posts[post].get("place") or default_place))
            existing = sum(1 for body_id in bodies
                           if body_id.startswith(f"{post}:"))
            for index in range(count):
                body_id = f"{post}:{existing + index + 1:04d}"
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
        staffing_reserve_added = _ensure_shift_crews(bodies, posts)
        naming = normalize_naming_profile(
            naming_law if naming_law else raw.get("naming"))
        bodies = materialize_body_names(ckey, bodies, naming, reservation)
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
        }
        charter = normalize_charter({
            "key": ckey, "structure": structure["key"],
            "upkeeps": upkeeps, "posts": posts, "bodies": bodies,
            "naming": naming,
            "priority": _strings(raw.get("priority")),
            "needs": seed_needs(bodies), "economy": economy,
            "decisions": raw.get("decisions") or {},
            "interventions": local_interventions,
            "history": {"architecture": history_record},
        }, reservation)
        charter["roster"] = seed_roster(charter["bodies"])
        charters[ckey] = charter
    return {"version": GENERATION_VERSION,
            "name": str(plan.get("name") or structure["key"]),
            "structure": structure, "rooms": rooms, "charters": charters,
            "featured_residents": {
                seed_id: {"name": source.get("name"),
                          "placed": seed_id in resident_assignments}
                for seed_id, source in resident_sources.items()},
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
    selected = candidates[:HISTORIAN_RESIDENT_CAP]
    chronicle = event_chronicle(events)
    chronicle.extend(resident_service_chronicle(
        registry, [row[2] for row in selected]))
    payload = {
        "town": {"name": town.get("name"),
                 "structure": town.get("structure")},
        "population_context": population_context,
        # One call remains bounded even for a thousand-person location. The
        # overview speaks for the whole population; individual sketches go to
        # the residents with the richest actual service/travel evidence.
        "residents": {row[2]: row[3] for row in selected},
        "chronicle": chronicle,
    }
    value = (model_call or (lambda p: _json_call(
        _HISTORIAN_SYSTEM, p, max_tokens=7000, temperature=0.45)))(payload)
    return ground_history_output(value, chronicle)


__all__ = [
    "HISTORIAN_RESIDENT_CAP", "close_plan", "ensure_required_rooms",
    "event_chronicle", "ground_history_output",
    "narrate_actual_history", "propose_history", "propose_town",
    "resident_service_chronicle",
]
