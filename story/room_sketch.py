"""The planting sketch: the light tier of the Writers' Room's fill.

THE OWNER'S RULING (2026-10-08): "Can we do lighter weight planning
potentially? And save heavy plans for when the actors near them?" Planting
ahead -- the fill's standing work since the same day's ruling restored it --
is ONE compact call that files light plans, not the Planner's full agent
loop: a fill job on the Brackwater run averaged about 17 model calls, and
77% of its steps re-read a world the payload could have handed it once. The
loop is kept, whole, for everything a sketch cannot say.

WHAT IT IS. One model call on the Story Planner's role and routing
(`agents/story_planner.PLANNER_ROLE`), at a lighter reasoning effort than
the Planner's own loop (`SKETCH_REASONING_EFFORT`, a ceiling: a role the
host set lower keeps its own). It is handed everything it may use, once:
the ground within reach of the player (each room's id, name, purpose, ways
out and open exits), the frontier's counts, the story's voice (its bible
and the names its people carry), the names the world already holds, what
the plan already holds ahead, the last few beats as the player saw them,
and the grants. It answers with LIGHT PLANS -- rooms (a name, what it is
for, the room and the way it joins, how much sky it stands under and how it
reads from far off -- `_seen_from_afar`), people (a name, a role, where they
belong), far looks for places that already stand and read from far off by
their ground alone (`looks_offered`, through `plot_packages.set_far_looks`)
and, only when a grant allows one and the pacing has run
(`room_frontier.LOCAL_EVENT_BEATS`), at most one local event near the
actors through the engine's own local-drama kinds. Code validates every
name, join, room and grant (`_plan`) and files ONE package through the
Room's own write seam (`room_tools.run_tool` over `story/plot_packages.py`:
draft, validate, publish under the standing mandates) -- so nothing lands
that the full Planner could not have landed, and a person, a room or an
event is met by the story exactly as the loop's would be.

ESCALATION KEEPS EVERY CAPABILITY. The owner, the same day: "We aren't
trying to remove functionality, just make it more efficient." The sketch
hands the question to the full fill loop, with its reason, when it says the
story needs more than a sketch can say, when its answer cannot be read,
when code refuses anything it planned, and when its package does not
validate or publish; a question goes to the loop without the call when the
frontier is short of something the standing grants do not let a sketch
plan (`sketch_payload`'s `unsketchable`: the loop may plant what it can and
ask the player for the rest); and `agents/story_planner.run_fill` sends a
question straight to the loop when a need is open or a player's line is
waiting in the thread. A sketch that plans nothing is an ANSWER -- the
question's back-off holds it -- and never an escalation.

THE AUTHOR LAYER, UNCHANGED. The sketch reads objective truth, as the
Planner does, and writes nothing but a package: rooms through `plan_rooms`,
people through `plan_entity`, an event through its own kind. No operation
addresses a mind; a local event is a circumstance that ARRIVES and the
Director rules what happens when it does. Harm is the one thing the code
can check in an event's fields, and it needs its own grant
(`schedule_harm`); that an event's summary must not end a thing for good
without one is the card's to say, because no guard can read it out of prose.
"""

from __future__ import annotations

import hashlib

from core.logging_utils import logger

#: The effort the sketch asks for, as a CEILING over the Planner role's own
#: (`llm.providers.reasoning_effort_for`): a role the host set at `off`,
#: `minimal` or `low` keeps its setting, and anything heavier or unset is
#: asked for `low`. The sketch reads a payload it was handed whole and
#: writes a few short plans; the Planner's loop thinks its way through tool
#: results, which is what its heavier effort is for (the encoder's
#: measured precedent: 12-20k tokens of trace on a 1.5k answer at the
#: host's `high`, chat 153, 2026-09-22). A provider that refuses the field
#: has it stripped and the call retried (`providers._strip_extended`).
SKETCH_REASONING_EFFORT = "low"
#: The efforts at or below the ceiling, lightest first.
_LIGHTER_EFFORTS = ("off", "minimal", "low")

#: SAFETY CEILINGS ON ONE SKETCH, not quotas: more than this many rooms or
#: people in one answer is a fill that wants the full Planner, and the
#: sketch hands it on (an escalation, never a truncation). The frontier
#: wants two of each ahead (`room_frontier.FRONTIER_ROOMS_MIN`,
#: `FRONTIER_IDENTITIES_MIN`), so four rooms and three people leave room
#: for an exit into nothing and a chain of two without asking the loop.
SKETCH_ROOMS_CAP = 4
SKETCH_PEOPLE_CAP = 3
#: FAR LOOKS ONE PASS WRITES, AT MOST (the owner's go-ahead, 2026-10-09: "at
#: most a named number per pass, under the same back-off as planting"): the
#: nearest this many standing places and parts of the map that far eyes read
#: by their ground (`room_frontier.looks_wanted`), parts of the map first --
#: one of their looks stands for every place of them a far eye reaches at
#: the outline. A PER-PASS cap guarding one call's payload and answer, never
#: the work: the rest are offered at the next pass, which a pass that landed
#: looks reaches after `room_frontier.FILL_RETRY_BEATS`. Eight is three
#: passes for chat 166's twenty standing places and its one part of the map,
#: and one for Kirinoura's seven and its one (measured 2026-10-09); chat
#: 166's live pass was shown 2.9k characters for its eight and answered in
#: 0.9k, about the size of the rooms the sketch already plans.
SKETCH_LOOKS_CAP = 8

#: What the sketch is shown, each a size the payload is held to. The
#: payload is the sketch's whole world -- it has no tools -- so these are
#: the cuts that keep one call compact. None of them limits what code
#: checks: every reserved name, every room the world holds and every grant
#: is checked in full (`_plan`).
#: Beats of the player-visible stream (`agents.dramaturge.
#: player_visible_stream`, its own per-beat cut).
SKETCH_BEATS = 3
#: The player's own recent lines to the room the sketch is shown, newest
#: last, each whole -- the Planner's loop carries the player's lines whole
#: because they are the brief (`story_planner._conversation`). Six: a
#: standing direction ("keep it to the harbour") is rarely more than a few
#: lines back, and the sketch stays one compact call.
SKETCH_PLAYER_LINES = 6
#: Characters of the story bible (`room_bible.render_block`).
SKETCH_BIBLE_CHARS = 1500
#: Characters of the scenario the story opened on.
SKETCH_SCENARIO_CHARS = 1200
#: Characters of one room's purpose in the area view.
SKETCH_PURPOSE_CHARS = 200
#: Reserved names shown; the rest are counted (`reserved_more`) and still
#: refused by code.
SKETCH_NAMES_SHOWN = 120
#: Planned people and things shown ahead, and packages by title.
SKETCH_PLANS_SHOWN = 24
SKETCH_PACKAGES_SHOWN = 12
#: Names shown from each list of the story's naming law.
SKETCH_NAME_SAMPLES = 12
#: Rooms an event may be placed in, listed by id.
SKETCH_EVENT_ROOMS_SHOWN = 40
#: Characters of what the story has said of a place a far look is asked
#: for (its description, else its plan's purpose): enough to see the place
#: whole, never the whole room's text.
SKETCH_LOOK_SOURCE_CHARS = 300
#: Rooms of a part of the map named beside it, so its look is of the whole.
SKETCH_REGION_ROOMS_SHOWN = 12
#: Characters of the reason an escalation carries into the loop's task.
SKETCH_ESCALATE_CHARS = 600

#: THE LOCAL-DRAMA KINDS A SKETCH MAY FILE, the closed set the engine owns
#: (`plot_packages.OPERATIONS`; docs/design/DESIGN_WRITERS_ROOM_PLAN.md,
#: "Local drama is a first-class op set"): each its own grant, and harm
#: inside one its own grant again (`plot_packages.operation_harms`).
SKETCH_EVENT_KINDS = ("arrival", "errand", "incident", "summons",
                      "scheduled_consequence", "schedule_event")
#: The package clock an event the sketch defers rides on.
SKETCH_CLOCK_ID = "sketch_due"

#: The keys an answer may carry; an answer carrying none is not one.
ANSWER_KEYS = ("rooms", "people", "looks", "event", "escalate", "reply", "title")

#: What a deferred event's `due_in_turns` means, as the sketch is told it
#: in place of the package clock it cannot name (`_event_fields`).
_DUE_FIELD_TEXT = ("how many beats from now it arrives (1..DRAMA_DUE_TURNS_CAP); "
                   "the next beat when left out")


class Refused(Exception):
    """What the sketch planned that code would not file, or the package
    that did not validate: the reason the question goes to the full loop."""


def _text(value, limit):
    return " ".join(str(value or "").split())[:limit]


def _given(value, limit):
    """An optional field's text, or "" where the answer left it empty --
    JSON's null written out as a word included, which is how a model that
    quotes every value says it (the card's own shape reads "..., or null")."""
    text = _text(value, limit)
    return "" if text.casefold() in ("null", "none") else text


def _head(value, limit):
    """``value`` within ``limit`` characters, cut at a word and marked."""
    text = _text(value, 100_000)
    if len(text) <= limit:
        return text
    return text[:limit - 1].rsplit(" ", 1)[0] + "…"


def _cancelled(job):
    flag = getattr(job, "cancelled", None)
    return bool(flag is not None and getattr(flag, "is_set", lambda: False)())


# ---------------------------------------------------------------------------
# What the sketch is shown, and what code checks its answer against
# ---------------------------------------------------------------------------

def sketch_effort(role):
    """The effort the sketch asks its role for: the role's own when it is
    at or below `SKETCH_REASONING_EFFORT`, else the ceiling."""
    try:
        from llm.providers import reasoning_effort_for
        own = reasoning_effort_for(role)
    except Exception:
        own = ""
    if own in _LIGHTER_EFFORTS and (_LIGHTER_EFFORTS.index(own)
                                    <= _LIGHTER_EFFORTS.index(SKETCH_REASONING_EFFORT)):
        return own
    return SKETCH_REASONING_EFFORT


def _player_name(cid):
    from core.db import q
    from story.character_schema import persona_name
    from story.scene import persona_of
    chat = q("SELECT * FROM chats WHERE id=?", (cid,), one=True)
    try:
        return str(persona_name(persona_of(dict(chat)))) if chat else ""
    except Exception:
        return ""


def _actor_rooms(scene, names, contained):
    """The rooms the story's people stand in: the player and every attached
    cast member, by their `positions` rows (exactly, then case-folded). An
    actor inside a body stands in their holder's room for this purpose: an
    event happens to a place, and the inside of a body is not one."""
    positions = (scene or {}).get("positions") or {}
    folded = {str(k).strip().casefold(): str(v) for k, v in positions.items() if v}
    rooms = (scene or {}).get("rooms") or {}
    out = []
    for name in names:
        room = positions.get(name) or folded.get(str(name).strip().casefold())
        if not room:
            continue
        room = str(room)
        if room in contained:
            from story.room_slice import holder_room
            room = str(holder_room(scene, contained[room]) or "")
        if room and room in rooms and room not in out:
            out.append(room)
    return out


def _held_spellings(cid, scene):
    """Every spelling a room of this story answers to -- live, planned or
    retired -- folded, and every name case-folded: a room the sketch plans
    must be a NEW place, never a second copy of one the story holds."""
    from world.spatial import normalize_room_id
    from world.structure import registry_rows, retired_room_spellings
    folded, names = set(), set()
    for rid, room in ((scene or {}).get("rooms") or {}).items():
        folded.add(normalize_room_id(str(rid)))
        name = str((room or {}).get("name") or "") if isinstance(room, dict) else ""
        if name:
            folded.add(normalize_room_id(name))
            names.add(name.casefold())
    for uid, entry in registry_rows(cid).items():
        for spelling in (uid, entry.get("name"), *(entry.get("aliases") or ())):
            spelling = str(spelling or "")
            if spelling:
                folded.add(normalize_room_id(spelling))
                names.add(spelling.casefold())
    folded |= retired_room_spellings(cid)
    folded.discard("")
    return folded, names


def _event_fields(kind, harm):
    """One local-drama kind's fields as the sketch is told them: the kind's
    own (`plot_packages.OPERATION_FIELDS`), with the package clock -- which
    the sketch cannot name -- replaced by `due_in_turns`, the room it
    happens in made required (an event is placed near the actors, so it
    must say where), and the harm field offered only under its grant."""
    from story.plot_packages import OPERATION_FIELDS, ROOM_FIELDS
    fields = {k: v for k, v in OPERATION_FIELDS[kind].items()
              if k not in ("clock", "clock?")}
    if kind == "incident" and not harm:
        fields.pop("harms?", None)
    room_field = (ROOM_FIELDS.get(kind) or ("room",))[0]
    if room_field + "?" in fields:
        fields[room_field] = fields.pop(room_field + "?")
    if kind == "schedule_event":
        fields["room"] = "<room_id> where it happens"
    else:
        fields["due_in_turns?"] = _DUE_FIELD_TEXT
    return fields


def _event_room_field(kind):
    from story.plot_packages import ROOM_FIELDS
    return (ROOM_FIELDS.get(kind) or ("room",))[0]


def looks_offered(wanted):
    """The nearest `SKETCH_LOOKS_CAP` of what the frontier says wants a far
    look (`room_frontier.looks_wanted`): ``{"regions": [...], "places":
    [...]}``, parts of the map first. The one cut the sketch and the fill's
    full loop share, so both are asked about the same places."""
    wanted = wanted if isinstance(wanted, dict) else {}
    regions = [r for r in wanted.get("regions") or () if isinstance(r, dict)]
    places = [p for p in wanted.get("places") or () if isinstance(p, dict)]
    regions = regions[:SKETCH_LOOKS_CAP]
    places = places[:max(0, SKETCH_LOOKS_CAP - len(regions))]
    return {"regions": regions, "places": places}


def _fold_name(text):
    return " ".join(str(text or "").split()).casefold()


def _looks_payload(cid, frame_id, scene, offered):
    """What the sketch is shown of each place and part of the map it is
    asked to give a far look: its name, what kind of ground it is, what the
    story has said of it, what the far layer already says standing on it,
    and the part of the map it is in -- a building from outside only, with
    the look made for another side of it where this side reads that one now
    -- and, for a part of the map, what it holds. ``(payload section,
    {offered id: "room" | "region"}, {folded name: offered id})`` -- the
    last for an answer that names a place by the name it was shown rather
    than its id, a name two offered places share naming neither."""
    from world.landscape import big_things, building_height, building_of, far_look_of
    from world.regions import region_name, region_registry
    rooms = (scene or {}).get("rooms") or {}
    try:
        registry = region_registry(cid, frame_id)
    except Exception:
        registry = {}
    places, kinds = [], {}
    for item in offered["places"]:
        rid = str(item.get("room") or "")
        room = rooms.get(rid)
        if not isinstance(room, dict):
            continue
        said = str(room.get("desc") or room.get("description") or "").strip() \
            or str(room.get("purpose") or "").strip()
        entry = {"id": rid, "name": str(room.get("name") or rid),
                 "ground": str(item.get("ground") or "")}
        if item.get("ground") == "building":
            # A BUILDING IS SEEN FROM OUTSIDE ONLY (review 2026-10-09, F5).
            # What the story has said of its front room, and the names of
            # its rooms, are what a body INSIDE it meets -- "crates to the
            # rafters" -- and a far look is told to every far eye, which no
            # far layer floor stops at what is inside. So they ride as its
            # inside, by name, and the card says nothing of an inside shows
            # from far off; what does show is said beside them -- how high
            # its mass stands, the words its look is said in place of.
            if said:
                entry["said_within"] = _head(said, SKETCH_LOOK_SOURCE_CHARS)
            members = [m for m in item.get("members") or () if m != rid and m in rooms]
            if members:
                entry["rooms_within"] = [str((rooms.get(m) or {}).get("name") or m)
                                         for m in members]
            entry["height"] = building_height(building_of(scene, rid)[1])
            # A SIDE THAT READS ANOTHER SIDE'S LOOK (review 2026-10-09, N1):
            # far eyes on this side are told, for want of its own, the look
            # made for another side of it -- shown, so this side's look is
            # its own and the two agree in what the building is.
            other = far_look_of(scene, str(item.get("reads_look_of") or ""))
            if other:
                entry["another_sides_look"] = other
        else:
            if said:
                entry["the_story_says"] = _head(said, SKETCH_LOOK_SOURCE_CHARS)
            beside = big_things(scene, rid)
            if beside:
                entry["said_beside_it"] = beside
        region = str(room.get("region") or "")
        if region:
            entry["part_of_the_map"] = region_name(registry, region)
        places.append(entry)
        kinds[rid] = "room"
    regions = []
    for item in offered["regions"]:
        region = str(item.get("region") or "")
        entry = registry.get(region)
        if not isinstance(entry, dict):
            continue
        out = {"id": region, "name": str(entry.get("name") or region)}
        if str(entry.get("brief") or "").strip():
            out["brief"] = _head(entry["brief"], SKETCH_LOOK_SOURCE_CHARS)
        held = [str((rooms.get(r) or {}).get("name") or r)
                for r in item.get("rooms") or () if r in rooms]
        if held:
            out["places_in_it"] = held[:SKETCH_REGION_ROOMS_SHOWN]
        regions.append(out)
        kinds[region] = "region"
    section = {"most": SKETCH_LOOKS_CAP, "places": places, "regions": regions}
    named = {}
    for entry in places + regions:
        named.setdefault(_fold_name(entry["name"]), set()).add(entry["id"])
    return section, kinds, {name: next(iter(ids)) for name, ids in named.items()
                            if name and len(ids) == 1}


def sketch_payload(cid, frame_id, report, *, turn_idx=None):
    """``(context, payload)``: what the sketch is shown, and what code holds
    its answer to. ``report`` is the fill's own `frontier_report`.

    ``context["unsketchable"]`` names what the frontier is short of that
    the standing grants do not let a sketch plan -- rooms with no
    `plan_rooms`, people with no `plan_entity` and `create_people` -- and a
    question that names any goes to the full loop, which may plant what it
    can and ask the player for the rest, exactly as before. A local event
    is never the reason a sketch runs: it rides a sketch that plants."""
    from story.mandates import coverage
    from story.plot_packages import (list_packages, operation_shape_line,
                                     reserved_identities)
    from story.room_bible import render_block
    from story.room_frontier import (FRONTIER_DEPTH_HOPS, frame_turn_idx,
                                     sketched_event_wait)
    from story.room_slice import (containment, read_scene, room_graph,
                                  room_hops, room_slices)
    from world.planned_entities import planned_entities
    from world.structure import frontier_spaces, registry_rows

    scene = read_scene(cid, frame_id) or {}
    contained = containment(scene)
    here = report.get("player_room")
    reach = ([str(here)] if here and str(here) not in contained else []) + [
        str(r) for r in report.get("reachable") or () if str(r) not in contained]
    stubs = {str(r) for r in report.get("rooms_ahead") or ()}
    registry = registry_rows(cid)

    # THE GROUND WITHIN REACH, as the sketch plans from it.
    axes, unheld, names, area = {}, {}, {}, []
    for row in frontier_spaces(cid):
        if row["room"] in reach:
            axes.setdefault(row["room"], []).append(str(row["axis"]))
    for slc in room_slices(cid, frame_id, reach, scene=scene):
        rid = slc["id"]
        names[rid] = slc["name"]
        plan = (registry.get(rid) or {}).get("planned") or {}
        purpose = (plan.get("purpose") or (slc.get("planned_stub") or {}).get("purpose")
                   or slc.get("description") or "")
        exits, open_exits = [], []
        for edge in slc.get("exits") or ():
            to = str(edge.get("to") or "")
            if not to or to in contained:
                continue
            if edge.get("status") is None:
                open_exits.append(to)            # a way out into nothing
                unheld.setdefault(rid, []).append(to)
            else:
                exits.append({"to": to, "name": edge.get("name") or to})
        open_exits.extend(axes.get(rid) or ())
        area.append({"id": rid, "name": slc["name"],
                     "state": ("here" if rid == here else
                               "planned" if rid in stubs else "developed"),
                     "purpose": _text(purpose, SKETCH_PURPOSE_CHARS),
                     "exits": exits,
                     **({"open_exits": open_exits} if open_exits else {})})

    # WHO THE WORLD HOLDS: every name, for code; the first of them, shown.
    identities = reserved_identities(cid, frame_id)
    player = _player_name(cid)
    reserved = set(identities["names"])
    if player:
        reserved.add(player.casefold())
    shown = [str(c["name"]) for c in identities["cast"] if c.get("name")]
    if player and player not in shown:
        shown.insert(0, player)
    plans = planned_entities(cid, frame_id)
    for plan in plans.values():
        shown.append(plan["name"])
    for _key, bodies in sorted((identities.get("charter_bodies") or {}).items()):
        shown.extend(str(b) for b in bodies)
    shown = list(dict.fromkeys(n for n in shown if n))

    # WHAT THE PLAN ALREADY HOLDS AHEAD.
    people_ahead = [{"name": p["name"], "role": p.get("role") or "",
                     "where": (p.get("brief") or {}).get("where") or ""}
                    for p in plans.values()
                    if p["kind"] == "person" and not p.get("rendered")]
    packages = [{"title": p["title"], "status": p["status"]}
                for p in list_packages(cid, frame_id=frame_id)
                if p["status"] != "retired"]

    # WHAT THE GRANTS ALLOW. Each through `coverage`, the one reader of the
    # standing mandates, so a total grant resolves here as it does at publish.
    def granted(*caps):
        try:
            return bool(coverage(cid, frame_id, list(caps), turn_idx=turn_idx)["ok"])
        except Exception:
            return False
    grants = {"rooms": granted("plan_rooms"),
              "people": granted("plan_entity", "create_people"),
              "looks": granted("set_far_looks"),
              "harm": granted("schedule_harm")}

    # WHO IS IN THE STORY, and where an event may arrive: within the
    # frontier's own depth of a room one of them stands in.
    actors = _actor_rooms(scene, [player] + [str(c["name"]) for c in identities["cast"]
                                             if c.get("name")], contained)
    kinds = [k for k in SKETCH_EVENT_KINDS if granted(k)]
    # Paced in THIS frame's beats, as the fill's back-off is: a live
    # bubble's rows in the chat-wide numbering are not this frame's.
    wait = sketched_event_wait(cid, frame_id, frame_turn_idx(cid, frame_id))
    event_may = bool(kinds) and not wait and bool(actors)
    event_rooms = []
    if actors:
        hops = room_hops(cid, scene, actors,
                         graph=room_graph(cid, scene, contained=contained))
        event_rooms = sorted((r for r, n in hops.items()
                              if n <= FRONTIER_DEPTH_HOPS and r not in contained),
                             key=lambda r: (hops[r], r))
    if event_may:
        event = {"may": True,
                 "kinds": {k: operation_shape_line(k, _event_fields(k, grants["harm"]))
                           for k in kinds},
                 "where": event_rooms[:SKETCH_EVENT_ROOMS_SHOWN]}
    else:
        event = {"may": False, "why": (
            "no grant allows one" if not kinds else
            "nobody in the story stands in a room" if not actors else
            "a sketched event arrived recently; the next may come in %d beats"
            % wait)}

    voice = {}
    try:
        bible = render_block(cid, frame_id, limit=SKETCH_BIBLE_CHARS).strip()
        if bible:
            voice["bible"] = bible
    except Exception as exc:
        logger.info("sketch: the story bible is unavailable: %s", exc)
    try:
        from story.naming import story_naming_lanes
        lanes, _source = story_naming_lanes(cid)
        for lane in lanes[:1]:
            # A law's names when it lists them, else the parts it builds
            # them from: either is how this story's people are called.
            sample = {}
            for key in ("given", "family"):
                if lane.get(key):
                    sample[key] = list(lane[key])[:SKETCH_NAME_SAMPLES]
                    continue
                parts = {part: list(values)[:SKETCH_NAME_SAMPLES]
                         for part, values in (lane.get(key + "_parts") or {}).items()
                         if values}
                if parts:
                    sample[key + "_parts"] = parts
            if sample:
                sample["format"] = lane.get("name_format") or ""
                voice["names"] = sample
    except Exception as exc:
        logger.info("sketch: the naming law is unavailable: %s", exc)
    try:
        from agents.dramaturge import player_visible_stream
        recent = player_visible_stream(cid, frame_id, beats=SKETCH_BEATS)
    except Exception as exc:
        logger.info("sketch: the recent beats are unavailable: %s", exc)
        recent = []

    # WHAT THE PLAYER SAID BOUNDS WHAT A SKETCH PLANS, as it bounds what the
    # full loop plans: the standing grants' own words and scope, and the
    # player's recent lines to the room. Code checks only which
    # capabilities are granted; a grant's scope ("keep it to the harbour --
    # leave the town above the cliff alone") is the planner's to honour, and
    # a sketch shown none of it planted the cliff-top chapel the loop would
    # have left alone (review of the 2026-10-08 landing).
    said = {}
    try:
        from story.mandates import active_mandates
        said["grants"] = [{"text": row["text"], "scope": row["scope"]}
                          for row in active_mandates(cid, frame_id, turn_idx)]
    except Exception as exc:
        logger.info("sketch: the standing grants are unavailable: %s", exc)
    try:
        from story import room_conversation as room
        said["lines"] = [str(m["text"]).strip()
                         for m in room.messages(cid, frame_id)
                         if m["role"] == "player" and str(m["text"] or "").strip()
                         ][-SKETCH_PLAYER_LINES:]
    except Exception as exc:
        logger.info("sketch: the room's thread is unavailable: %s", exc)

    from core.db import q
    chat = q("SELECT name, scenario FROM chats WHERE id=?", (cid,), one=True)
    frontier = {"rooms_short": int(report.get("rooms_short") or 0),
                "identities_short": int(report.get("identities_short") or 0),
                "rooms_developed": list(report.get("rooms_developed") or ()),
                "bodies_ahead": dict(report.get("bodies_ahead") or {})}
    if report.get("rooms_unmeasured"):
        frontier["rooms_unmeasured"] = report["rooms_unmeasured"]
    payload = {
        "kind": "sketch",
        "story": {"name": str((chat or {})["name"] if chat else ""),
                  "scenario": _text((chat or {})["scenario"] if chat else "",
                                    SKETCH_SCENARIO_CHARS)},
        "voice": voice,
        "recent": recent,
        "area": {"player_room": here, "rooms": area},
        "frontier": frontier,
        "planned_ahead": {"people": people_ahead[:SKETCH_PLANS_SHOWN],
                          "things": list(report.get("things_ahead") or ())[:SKETCH_PLANS_SHOWN],
                          "packages": packages[-SKETCH_PACKAGES_SHOWN:]},
        "reserved_names": shown[:SKETCH_NAMES_SHOWN],
        **({"reserved_more": len(shown) - SKETCH_NAMES_SHOWN}
           if len(shown) > SKETCH_NAMES_SHOWN else {}),
        "granted": grants,
        "player_said": said,
        "event": event,
    }
    # WORDS SAID ALOUD NEAR THE STORY WITH NO REPORT BEHIND THEM (the
    # owner's ruling on D6, 2026-10-09): a person a character invents stays
    # their claim, and the Room MAY make them real when it plans. Not this
    # tier: who knows a claimed person, and what the plans already say that
    # bears on them, are the full planner's to read and to write, so a
    # sketch is shown the claims to hand such a person on, and code refuses
    # one it plants anyway (`_plan`, `_claimed`). The same reader and reach
    # as the full Planner's payload (`story_planner._claims_near`). Absent
    # when there is none.
    try:
        from story.carriers import unbacked_claims
        # The player's own room even when it is the inside of a body, which
        # `reach` leaves out because a plan cannot be filed there; a claim
        # held by somebody beside them is near all the same.
        claim_rows, claims_total = unbacked_claims(
            cid, frame_id, [here, *reach] if here else reach, scene=scene)
    except Exception as exc:
        logger.info("sketch: the claims near the story are unavailable: %s", exc)
        claim_rows, claims_total = [], 0
    if claim_rows:
        payload["unbacked_claims"] = claim_rows
        if claims_total > len(claim_rows):
            payload["unbacked_claims_more"] = claims_total - len(claim_rows)
    # FAR LOOKS FOR WHAT ALREADY STANDS: the nearest places and parts of the
    # map far eyes read by their ground alone, under their grant
    # (`room_frontier.looks_wanted`, `looks_offered`). Absent when none is
    # wanted or the grants do not let the Room write one.
    look_kinds, look_names = {}, {}
    if grants["looks"] and report.get("looks_wanted"):
        section, look_kinds, look_names = _looks_payload(
            cid, frame_id, scene, looks_offered(report["looks_wanted"]))
        if section["places"] or section["regions"]:
            payload["looks"] = section
    held_folded, held_names = _held_spellings(cid, scene)
    context = {
        "scene": scene, "here": here, "reach": reach, "names": names,
        "contained": contained, "axes": axes, "unheld": unheld,
        "held_folded": held_folded, "held_names": held_names,
        "reserved": reserved, "grants": grants,
        # The words of every claim this payload shows, and only those: what
        # the sketch was shown is what it can be held to.
        "claim_words": [row["said"] for row in claim_rows],
        "event_kinds": kinds if event_may else [], "actors": actors,
        "looks": look_kinds, "look_names": look_names,
        "room_structure": {uid: str((entry.get("planned") or {}).get("structure") or "")
                           for uid, entry in registry.items()},
        "unsketchable": [what for what, short, allowed in (
            ("rooms", frontier["rooms_short"], grants["rooms"]),
            ("people", frontier["identities_short"], grants["people"]))
            if short and not allowed],
    }
    return context, payload


# ---------------------------------------------------------------------------
# The answer, checked: what code would file
# ---------------------------------------------------------------------------

def _room_ref(context, text, new):
    """A room the answer names, as an id: an id within reach, the name of
    a room within reach, or the name of a room this answer plans."""
    text = _text(text, 120)
    if not text:
        return None
    if text in context["reach"]:
        return text
    folded = text.casefold()
    for rid, name in context["names"].items():
        if str(name).casefold() == folded:
            return rid
    return new.get(folded)


def _edge(joins, raw):
    """The planned room's way to the room it joins: the way's own words as
    the edge's label, its barrier where the engine reads one in them (a
    word it cannot read leaves the way open rather than sealing it, as
    `normalize_barrier` would), and its vertical sense when given."""
    from world.spatial import normalize_barrier, normalize_vertical
    edge = {"to": joins}
    way = _given(raw.get("way"), 120)
    if way:
        edge["name"] = way
        unread = set()
        barrier = normalize_barrier(way, unresolved=unread)
        if not unread and barrier != "wall":
            edge["barrier"] = barrier
    vertical = normalize_vertical(raw.get("vertical"))
    if vertical:
        edge["vertical"] = vertical
    return edge


def _seen_from_afar(raw):
    """What a sketched room says about being SEEN FROM FAR OFF: its
    `exposure` in the engine's closed vocabulary (`weather.EXPOSURES`) and
    its `far_look` (`landscape.normalize_far_look`), each fail-open -- a
    word the engine cannot read is no value, as `plan_rooms` reads them.

    Planting ahead is when a place is planned, and a sketched room arrived
    with neither: every room the sketch filed was in no far view at all (an
    undeclared room is no ground to the far layer), and one it had been
    asked to look at from afar could only read as its ground."""
    from world.landscape import FAR_LOOK_CHARS, normalize_far_look
    from world.weather import EXPOSURES
    out = {}
    exposure = _given(raw.get("exposure"), 20).casefold()
    if exposure in EXPOSURES:
        out["exposure"] = exposure
    look = normalize_far_look(_given(raw.get("far_look"), FAR_LOOK_CHARS * 2))
    if look:
        out["far_look"] = look
    return out


def _structure_for(cid, context, joins):
    """The structure a sketched room is planted under: its joined room's
    (as stored; publishing keeps whatever the stored record holds either
    way, `plot_packages._structure_as_held`), else the one most rooms within
    reach belong to, else the one the story holds, else one named after the
    scene's place."""
    from core.db import wget_for_frame
    from world.spatial import normalize_room_id
    from world.structure import STRUCTURES_KEY, normalize_structures
    stored = normalize_structures(
        wget_for_frame(cid, STRUCTURES_KEY, None, {}) or {})["items"]
    key = context["room_structure"].get(joins) or ""
    if not key:
        counts = {}
        for rid in context["reach"]:
            k = context["room_structure"].get(rid)
            if k:
                counts[k] = counts.get(k, 0) + 1
        if counts:
            key = sorted(counts, key=lambda k: (-counts[k], k))[0]
        elif len(stored) == 1:
            key = next(iter(stored))
    if key and key in stored:
        return dict(stored[key])
    place = str((context["scene"] or {}).get("location") or "")
    return {"key": key or normalize_room_id(place)[:40] or "story",
            "name": place.split(",")[0].strip() or key or "story"}


def _looks_read(raw):
    """The answer's far looks as ``[(place, look)]`` in its order, and
    whether any of it could not be read. The card's shape is a list of
    ``{place, far_look}``; a map ``{place: look}``, and the operation's own
    ``{rooms: {...}, regions: {...}}`` that the Planner's sheet shows, say the
    same thing and are read as it."""
    if raw in (None, "", [], {}):
        return [], False
    if isinstance(raw, dict):
        split = set(raw) <= {"rooms", "regions"} and all(
            isinstance(v, dict) or v in (None, "", []) for v in raw.values())
        maps = [raw.get("rooms"), raw.get("regions")] if split else [raw]
        return [(place, look) for m in maps if isinstance(m, dict)
                for place, look in m.items()], False
    if not isinstance(raw, list):
        return [], True
    pairs, unread = [], False
    for item in raw:
        if isinstance(item, dict):
            pairs.append((item.get("place") or item.get("id"),
                          item["far_look"] if "far_look" in item else item.get("look")))
        else:
            unread = True
    return pairs, unread


def _looks_op(context, raw, notes):
    """``[set_far_looks op]`` for the answer's "looks", or [] when it gives
    none.

    NEVER A REFUSAL (review 2026-10-09, F2). A far look plans nothing and
    nothing else in the package leans on it, so each one stands alone: a
    look for a place the payload did not offer -- under an id or a name --
    or one that cannot be read is left out and said in ``notes``, and the
    offered looks beside it land. Refused, one look for the warehouse's own
    loft threw away the two offered looks with it and handed a one-call
    question to the full loop, which averaged about seventeen calls a fill
    on the Brackwater run. A place a look named that wants one is offered
    at a later pass, with what it is. A place the answer left out, or gave
    null, gets no look now and is offered again too. An offered place may
    be named by the name it was shown (`_looks_payload`). More looks than
    were offered cannot land, so the cap needs no check of its own."""
    from world.landscape import FAR_LOOK_CHARS, normalize_far_look
    pairs, unread = _looks_read(raw)
    if not pairs:
        if unread:
            notes.append("the answer's looks could not be read and were left out")
        return []
    offered = context.get("looks") or {}
    if not offered:
        # Not offered now -- no grant, or nothing wants one -- so nothing
        # the sketch wrote here is filed, and nothing else is refused for it.
        notes.append("far looks were not asked for now and were left out")
        return []
    names = context.get("look_names") or {}
    rooms, regions, left = {}, {}, []
    for place, value in pairs:
        place = _text(place, 120)
        if value is not None and not isinstance(value, str):
            unread = True
            continue
        look = normalize_far_look(_given(value, FAR_LOOK_CHARS * 2))
        if not place or not look:
            continue
        ident = place if place in offered else names.get(_fold_name(place))
        if ident is None:
            left.append(place)
            continue
        target = rooms if offered[ident] == "room" else regions
        target.setdefault(ident, look)
    if unread:
        notes.append("some of the answer's looks could not be read and were left out")
    if left:
        shown = ", ".join(repr(p) for p in left[:SKETCH_LOOKS_CAP])
        more = len(left) - SKETCH_LOOKS_CAP
        notes.append("far looks for %s%s were left out: not offered now"
                     % (shown, " and %d more" % more if more > 0 else ""))
    if not rooms and not regions:
        return []
    op = {"op": "set_far_looks"}
    if rooms:
        op["rooms"] = rooms
    if regions:
        op["regions"] = regions
    return [op]


def _plan(cid, context, answer):
    """What code would file for this answer: ``{"ops", "clocks",
    "authority", "event", "notes", "names"}``. Raises `Refused` naming
    every reason it would not -- one bad item refuses the whole sketch,
    because a package lands all of it or none, and the full loop it is
    handed to can fix what a sketch could not. A far look is the exception
    (`_looks_op`): it plans nothing and nothing leans on it, so one that
    cannot land is left out and said in the notes."""
    from story.plot_packages import (DRAMA_DUE_TURNS_CAP, OPERATIONS,
                                     operation_harms)
    from story.room_frontier import FRONTIER_DEPTH_HOPS
    from story.room_slice import room_graph, room_hops
    from world.spatial import normalize_room_id

    refusals, notes, ops, clocks = [], [], [], []
    # AN ANSWER IS READ OR REFUSED, NEVER HALF-READ: a field the card
    # shapes as a list of objects, or one object, that arrives as anything
    # else is refused rather than read as nothing planned.
    for key, shape in (("rooms", list), ("people", list), ("event", dict)):
        value = answer.get(key)
        if value not in (None, "", [], {}) and (
                not isinstance(value, shape)
                or (shape is list and not all(isinstance(v, dict) for v in value))):
            refusals.append("the answer's %r could not be read" % key)
    rooms_in = answer.get("rooms") if isinstance(answer.get("rooms"), list) else []
    people_in = answer.get("people") if isinstance(answer.get("people"), list) else []
    rooms_in = [r for r in rooms_in if isinstance(r, dict)]
    people_in = [p for p in people_in if isinstance(p, dict)]
    if len(rooms_in) > SKETCH_ROOMS_CAP:
        refusals.append("%d rooms is more than a sketch plants (%d)"
                        % (len(rooms_in), SKETCH_ROOMS_CAP))
    if len(people_in) > SKETCH_PEOPLE_CAP:
        refusals.append("%d people is more than a sketch plans (%d)"
                        % (len(people_in), SKETCH_PEOPLE_CAP))
    if rooms_in and not context["grants"]["rooms"]:
        refusals.append("no standing grant lets the room plan rooms")
    if people_in and not context["grants"]["people"]:
        refusals.append("no standing grant lets the room plan people")

    # ROOMS, in two passes: every new room's id first, so one room may join
    # another this answer plans; then what each joins.
    taken = set(context["held_folded"]) | set(context["names"])
    new, entries = {}, []
    for raw in rooms_in[:SKETCH_ROOMS_CAP]:
        name = _text(raw.get("name"), 120)
        if not name:
            refusals.append("a room is planned with no name")
            continue
        folded, slug = name.casefold(), normalize_room_id(name)
        if folded in context["held_names"] or (slug and slug in context["held_folded"]) \
                or folded in new:
            refusals.append("%r is already a room of this story" % name)
            continue
        entry = {"name": name, "raw": raw, "uid": None, "claim": None}
        fills = _given(raw.get("fills"), 120)
        if fills:
            # AN OPEN EXIT IS FILLED BY IDENTITY, never beside it: an axis
            # the plan holds open is claimed (`claim_frontier_spaces`), and
            # an exit into nothing is planted under its own id, so the way
            # that led nowhere now leads here.
            held = _room_ref(context, raw.get("joins"), {})
            axis = next((a for a in context["axes"].get(held) or ()
                         if a.casefold() == fills.casefold()), None) if held else None
            hole = next((h for h in context["unheld"].get(held) or ()
                         if h == fills), None) if held else None
            if axis:
                entry["claim"] = {"room": held, "axis": axis}
            elif hole and hole not in taken:
                entry["uid"] = hole
            else:
                refusals.append("%r fills %r, which is not an open exit of the "
                                "room it joins" % (name, fills))
                continue
        if entry["uid"] is None:
            base = slug or ("room_" + hashlib.sha1(
                name.encode("utf-8")).hexdigest()[:8])
            uid, n = base, 2
            while uid in taken:
                uid, n = "%s_%d" % (base, n), n + 1
            entry["uid"] = uid
        taken.add(entry["uid"])
        new[folded] = entry["uid"]
        entries.append(entry)
    planted, edges = {}, []
    for entry in entries:
        name, raw, uid = entry["name"], entry["raw"], entry["uid"]
        joins = _room_ref(context, raw.get("joins"), new)
        if not joins or joins == uid:
            refusals.append("%r joins %r, which is not a room within reach"
                            % (name, _text(raw.get("joins"), 120)))
            continue
        spec = {"name": name, "purpose": _text(raw.get("purpose"), 400),
                "adjacent": [_edge(joins, raw)], **_seen_from_afar(raw)}
        if entry["claim"]:
            spec["claims"] = entry["claim"]
        planted[uid] = (joins, spec)
        edges.append((uid, joins))
    # Each room under the structure of the held room it is reached from (a
    # chain takes its first link's), one `plan_rooms` per structure.
    by_structure = {}
    for uid, (joins, spec) in planted.items():
        root, seen = joins, set()
        while root in planted and root not in seen:
            seen.add(root)
            root = planted[root][0]
        structure = _structure_for(cid, context, root)
        bucket = by_structure.setdefault(structure["key"], (structure, {}))
        bucket[1][uid] = spec
    for structure, rooms in by_structure.values():
        ops.append({"op": "plan_rooms", "structure": structure, "rooms": rooms})

    # FAR LOOKS for places that already stand, each one the payload offered
    # (`looks_offered`), as ONE `set_far_looks`. A place left out, or given
    # null, is a place the sketch could not see whole: no look, and it is
    # offered again at the next pass; a look for a place not offered is left
    # out and noted, never a refusal (`_looks_op`). What a look may say is
    # the card's, and what a mind is told of it the far layer's floor
    # (`landscape._admit_look`); what the operation may write over is its
    # own rule.
    ops.extend(_looks_op(context, answer.get("looks"), notes))

    # PEOPLE.
    seen_people = set()
    for raw in people_in[:SKETCH_PEOPLE_CAP]:
        name = _text(raw.get("name"), 120)
        if not name:
            refusals.append("a person is planned with no name")
            continue
        if name.casefold() in context["reserved"] or name.casefold() in seen_people:
            refusals.append("%r is a name the world already holds" % name)
            continue
        # A PERSON A CLAIM NAMES IS THE FULL PLANNER'S (review RP-3,
        # 2026-10-10). A sketch's person is a name, a role, a room and a
        # look, so it can neither tie them to the people who already know
        # them nor read what the plans already say that bears on them: the
        # one measured ratification (story 166, checkpoint 24) planted "Tam
        # Elver" as "the Corvina's missing hand", a stranger to both Gales
        # who know him and against the Room's own published truth that Abel
        # was the only hand aboard. So it lands nothing, and the question
        # goes to the loop, which can read the plans and write `known_by` --
        # the card asks for that hand-off, and this holds when a model does
        # not.
        if _claimed(name, context.get("claim_words")):
            refusals.append(
                "%r is a person named in what people near the story claim; "
                "who knows them, and what the plans already say that bears on "
                "them, is the full planner's to read and say" % name)
            continue
        seen_people.add(name.casefold())
        where = _room_ref(context, raw.get("where"), new)
        if not where:
            refusals.append("%r belongs in %r, which is not a room within reach"
                            % (name, _text(raw.get("where"), 120)))
            continue
        role = _text(raw.get("role"), 120)
        op = {"op": "plan_entity", "kind": "person", "name": name,
              "role": role, "brief": {"purpose": role, "where": where}}
        look = _given(raw.get("look"), 600)
        if look:
            op["look"] = look
        ops.append(op)

    # THE EVENT: one, of a kind offered, near the actors.
    event_kind = None
    raw_event = answer.get("event")
    if isinstance(raw_event, dict) and raw_event:
        kind = _text(raw_event.get("op") or raw_event.get("kind"), 40)
        if not context["event_kinds"]:
            # Not offered now -- no grant, or the pacing has not run: the
            # payload said so, and what the sketch planted stands without it.
            notes.append("an event (%s) was not asked for now and was left out"
                         % (kind or "unnamed"))
        elif kind not in context["event_kinds"]:
            refusals.append("the event is a %r, which is not one the grants "
                            "allow (%s)" % (kind, ", ".join(context["event_kinds"])))
        else:
            fields = {k: v for k, v in raw_event.items()
                      if k not in ("op", "kind", "due_in_turns", "clock")}
            room_field = "room" if kind == "schedule_event" else _event_room_field(kind)
            where = _room_ref(context, fields.get(room_field), new)
            scene_rooms = (context["scene"] or {}).get("rooms") or {}
            if not where and _text(fields.get(room_field), 120) in scene_rooms:
                where = _text(fields.get(room_field), 120)
            if not where and _text(fields.get(room_field), 120) in context["room_structure"]:
                where = _text(fields.get(room_field), 120)
            hops = {}
            if where and context["actors"]:
                hops = room_hops(cid, context["scene"], context["actors"],
                                 graph=room_graph(cid, context["scene"],
                                                  extra_edges=edges))
            if not where:
                refusals.append("the event happens at %r, which the world does "
                                "not hold" % _text(fields.get(room_field), 120))
            elif where in context["contained"] or hops.get(where, FRONTIER_DEPTH_HOPS + 1) \
                    > FRONTIER_DEPTH_HOPS:
                refusals.append("the event happens at %r, which is not within "
                                "%d rooms of anyone in the story"
                                % (where, FRONTIER_DEPTH_HOPS))
            else:
                due = _given(raw_event.get("due_in_turns"), 20)
                try:
                    due = int(due) if due else None
                except (TypeError, ValueError):
                    due = None
                    refusals.append("the event's due_in_turns is not a number")
                if due is not None and not 1 <= due <= DRAMA_DUE_TURNS_CAP:
                    refusals.append("the event is due in %d beats; 1..%d"
                                    % (due, DRAMA_DUE_TURNS_CAP))
                    due = None
                if kind == "schedule_event":
                    name = context["names"].get(where) or where
                    op = {"op": kind, "due_in_turns": due or 1,
                          "summary": "%s (at %s)" % (_text(fields.get("summary"), 360),
                                                     name)}
                else:
                    op = dict(fields, op=kind)
                    op[room_field] = where
                    if due or kind == "scheduled_consequence":
                        clocks.append({"id": SKETCH_CLOCK_ID,
                                       "text": _head(op.get("summary") or kind, 200),
                                       "due_turns": due or 1})
                        op["clock"] = SKETCH_CLOCK_ID
                if kind == "incident" and op.get("harms") and not context["grants"]["harm"]:
                    refusals.append("the event harms a body and no standing grant "
                                    "allows harm")
                try:
                    OPERATIONS[kind]["shape"](dict(op))
                except ValueError as exc:
                    refusals.append("the event: %s" % exc)
                else:
                    ops.append(op)
                    event_kind = kind
    if refusals:
        raise Refused("; ".join(refusals))
    harms = any(operation_harms(op) for op in ops)
    return {"ops": ops, "clocks": clocks, "event": event_kind, "notes": notes,
            "authority": {"may_schedule_harm": bool(harms)},
            "names": [spec["name"] for _j, spec in planted.values()]
            + [op["name"] for op in ops if op["op"] == "plan_entity"]}


def _claimed(name, claim_words):
    """Is this planned person named in the words of a claim the sketch was
    shown? Read as the engine reads a name said aloud
    (`commit_common._address_forms` and `_form_in`): the whole name, its last
    word and its last two, each at a name boundary in either pack -- so
    "Elver" planted is the "Tam Elver" a claim named."""
    if not name or not claim_words:
        return False
    from persist.commit import _address_forms, _form_in
    forms = _address_forms([name]).get(name) or {name}
    return any(_form_in(form, str(words or ""))
               for words in claim_words for form in forms)


# ---------------------------------------------------------------------------
# Filing: one package, through the Room's own write seam
# ---------------------------------------------------------------------------

def _file(cid, frame_id, plan, answer, *, actor, base_turn, job):
    """Draft, validate and publish ONE package under the standing mandates,
    through `room_tools.run_tool` -- the seam every Room write passes. A
    draft that does not validate or publish is retired with the reason (it
    is the sketch's own, and a draft nobody will finish is clutter on the
    panel) and the reason is raised as `Refused`. Returns ``(uid, None)``
    for the published package, or ``(None, stop)`` when the story rewound
    or the job was cancelled before the write."""
    from core.jobs import story_rewound_past
    from story import room_conversation as room
    from story.plot_packages import TEXT_CHARS, retire_package
    from story.room_tools import run_tool

    def tool(name, args):
        out = run_tool(cid, name, args, frame_id=frame_id, actor=actor)
        if isinstance(out, dict) and out.get("refused"):
            raise Refused("%s was refused: %s" % (name, out["refused"]))
        return out

    title = (_given(answer.get("title"), 200)
             or _text("; ".join(plan["names"]), 200) or "Planted ahead")
    pkg = tool("new_package", {"title": title,
                               "premise": _text(answer.get("reply"), TEXT_CHARS),
                               "authority": plan["authority"]})
    uid = pkg["uid"]
    try:
        if plan["clocks"]:
            tool("edit_package", {"uid": uid, "fields": {"clocks": plan["clocks"]}})
        for op in plan["ops"]:
            tool("draft_operation", {"uid": uid, "operation": op})
        verdict = tool("validate_package", {"uid": uid})
        if not verdict.get("ok"):
            raise Refused("the package does not validate: %s"
                          % "; ".join(str(e) for e in (verdict.get("errors") or [])[:4]))
        # THE LAST MOMENT BEFORE THE WRITE, the same guard the loop keeps on
        # `publish_package` (`story_planner._is_write`).
        if _cancelled(job):
            retire_package(cid, uid, note="the room's job was cancelled before "
                           "the sketch was filed", frame_id=frame_id)
            return None, "cancelled"
        if base_turn is not None and story_rewound_past(base_turn,
                                                        room.current_turn_idx(cid)):
            retire_package(cid, uid, note="the story rewound under the sketch",
                           frame_id=frame_id)
            return None, "rewound"
        tool("publish_package", {"uid": uid,
                                 "expected_revision": int(verdict["at_revision"])})
    except Refused as exc:
        try:
            retire_package(cid, uid, note=_text("sketch handed to the full "
                                                "planner: %s" % exc, 400),
                           frame_id=frame_id)
        except Exception as inner:
            logger.info("sketch draft %s not retired: %s", uid, inner)
        raise
    return uid, None


def _ask(role, payload):
    from agents.common import jparse
    from llm.prompts import get_prompt
    from story.room_calls import room_call, room_max_tokens
    raw = room_call(role, get_prompt("room_sketch"), payload,
                    max_tokens=room_max_tokens(), phase="sketch",
                    reasoning_effort=sketch_effort(role))
    out = jparse(raw)
    return out if isinstance(out, dict) else {}


def run_sketch(cid, frame_id, report, *, role, actor, base_turn=None, job=None,
               turn_idx=None):
    """Ask one planting question as a sketch. Returns ``{"published": [uid],
    "escalate": reason or "", "reply", "calls", "stopped", "notes",
    "event"}``: a non-empty ``escalate`` hands the question to the full fill
    loop (`agents/story_planner.run_fill`); otherwise it is answered, with
    a package or with nothing. A provider failure is raised, as the loop's
    first call raises: the fill counts it as an empty answer for the
    back-off."""
    from core.jobs import story_rewound_past
    from story import room_conversation as room
    out = {"published": [], "escalate": "", "reply": "", "calls": 0,
           "stopped": None, "notes": [], "event": None}
    context, payload = sketch_payload(cid, frame_id, report, turn_idx=turn_idx)
    if context["unsketchable"]:
        out["escalate"] = ("the frontier is short of %s, and the standing "
                           "grants do not let a sketch plan them"
                           % " and ".join(context["unsketchable"]))
        return out
    if _cancelled(job):
        out["stopped"] = "cancelled"
        return out
    answer = _ask(role, payload)
    out["calls"] = 1
    if not any(key in answer for key in ANSWER_KEYS):
        out["escalate"] = "the sketch's answer could not be read"
        return out
    out["reply"] = _text(answer.get("reply"), 2000)
    asked_for = _given(answer.get("escalate"), SKETCH_ESCALATE_CHARS)
    if asked_for:
        out["escalate"] = asked_for
        return out
    try:
        plan = _plan(cid, context, answer)
    except Refused as exc:
        out["escalate"] = _text("the sketch planned what could not be filed: %s"
                                % exc, SKETCH_ESCALATE_CHARS)
        return out
    out["notes"].extend(plan["notes"])
    for note in plan["notes"]:
        logger.info("sketch for chat %s: %s", cid, note)
    if not plan["ops"]:
        return out
    if _cancelled(job):
        out["stopped"] = "cancelled"
        return out
    if base_turn is not None and story_rewound_past(base_turn,
                                                    room.current_turn_idx(cid)):
        out["stopped"] = "rewound"
        return out
    try:
        uid, stop = _file(cid, frame_id, plan, answer, actor=actor,
                          base_turn=base_turn, job=job)
    except Refused as exc:
        out["escalate"] = _text(str(exc), SKETCH_ESCALATE_CHARS)
        return out
    if uid is None:
        out["stopped"] = stop
        return out
    out["published"] = [uid]
    turn = room.current_turn_idx(cid) if turn_idx is None else int(turn_idx)
    if plan["event"]:
        from story.room_frontier import frame_turn_idx, record_sketched_event
        record_sketched_event(cid, frame_id, turn_idx=frame_turn_idx(cid, frame_id),
                              package_uid=uid, op=plan["event"])
        out["event"] = plan["event"]
    try:
        from story.room_bible import note_publish
        from story.plot_packages import get_package
        pkg = get_package(cid, uid, frame_id=frame_id) or {}
        note_publish(cid, frame_id, package_uid=uid,
                     title=str(pkg.get("title") or uid), turn_idx=turn)
    except Exception as exc:
        logger.info("sketch: bible note skipped: %s", exc)
    return out
