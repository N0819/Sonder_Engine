"""The world-context compiler: lore routing and retrieval, deterministic.

`compile_world_context` is what the two mapping model stages used to be. It
assembles, with no model role of its own -- one provider round trip, the lore
query's embedding, is the whole of what it spends -- what they assembled: the
beat's relevant lore from the story's own rows, the books that lore came
from, the owed history a place has accrued, the plan's brief for a room the
beat named, and the movement classification the cached-recall stage did
cheaply -- and
it refuses the one thing they also did: inventing. Where `mapping_stage`
staged a room for a door the plan had not drawn, the compiler emits a typed
PLANNING NEED (`world/planning_needs.py`) and the Director renders the
surface the beat perceived, the way it renders an unplanned frontier stub.
The creative fallback belongs to the Writers' Room (v2 § 9.3), and until
the room exists a deterministic fill answers the need at commit.

Every reader of the old stages' output keeps its keys: `relevant_lore`,
`relevant_books`, `staged_lore` (always empty now) and `scene_patch` (always
the empty containers). `PipelineContext.world_context()` is the one read.
"""

from __future__ import annotations

from core.db import wget, wget_for_frame
from mind.memory import search_lore
from story.scene import (
    cast_scene_context,
    get_scene,
    persona_name,
    persona_of,
    recent_events,
)
from world.spatial import (
    normalize_room_id, room_of, room_spellings, scene_room_id)

from .common import (
    _books,
    _book_weights,
    _join_text,
    _lore_fingerprint,
    _normalize_scene_patch,
    figures_in_view,
    rooms_in_view,
)

#: Candidates retrieved for a beat -- the full stage's `k`.
WORLD_CONTEXT_LORE_K = 14
#: Entries carried on the step after the cache merge -- the quick stage's cap.
WORLD_CONTEXT_LORE_CAP = 12
#: Recent beats folded into the retrieval query -- the full stage's window.
WORLD_CONTEXT_RECENT_EVENTS = 5

#: The RULEBOOK slice: engine rows rendered from typed data the Director
#: rules on -- the day cycle, the weather, the authored mechanics of a
#: creature in view, the posts an institution holds here. A mechanic authored
#: as data is never also authored as prose: the compiler renders the prose
#: from the data, so the two cannot disagree. Bounded so a town with forty
#: institutions in view does not hand the Director a treatise.
RULEBOOK_ROWS_CAP = 8
RULEBOOK_ROW_CHARS = 400

#: The fields a relevant-lore row carries onto the step. The engine's own
#: rows, verbatim -- there is no model echo to join any more, which was the
#: transcription that lost sentences in 13.6% of 855 measured entries.
LORE_ROW_FIELDS = (
    "id", "entry_uid", "book_id", "keys", "content", "category", "locked")


def _lore_row(hit):
    return {field: hit.get(field) for field in LORE_ROW_FIELDS if field in hit}


def _query(ctx, interp):
    chat = ctx.chat
    fl = interp.get("flow") or {}
    pieces = [e.get("text") or e.get("attempt") or ""
              for e in (interp.get("sequence") or []) if isinstance(e, dict)]
    pieces += [fl.get("mapping_request") or "",
               interp.get("location_query") or "", ctx.input or ""]
    # Frame-scoped and scrubbed (audit X18): a routing stage is never
    # entitled to the omniscient events row.
    pieces += recent_events(chat["id"], WORLD_CONTEXT_RECENT_EVENTS)
    if not interp:
        # The opening: no interpretation yet, so the scenario and the cast's
        # public surface are the query.
        pieces += [chat.get("scenario") or ""]
        for actor in cast_scene_context(ctx.cast):
            pieces.extend([
                actor["name"],
                actor["public_history"],
                actor["opening_context"],
                " ".join(str(ab.get("name") or "") for ab in actor["abilities"]
                         if isinstance(ab, dict)),
                " ".join(str(ab.get("notes") or "") for ab in actor["abilities"]
                         if isinstance(ab, dict)),
            ])
    return _join_text(pieces)


def is_contained_destination(target, scene):
    """True when ``target`` names a scene ENTITY or an entity's inside.

    WHERE A BODY WALKS IS ITS OWN; WHERE THE WORLD PUTS IT IS THE DIRECTOR'S.
    A body put inside another body is a place the moment it happens -- the
    spatial hand mints the room with `parent_entity` -- and no plan can hold
    it in advance, so a destination that is an entity (by id or name), a room
    an entity already lists as its interior, or a spelling of that entity's
    inside (the engine's containment rooms are `<entity>_<part>`) is
    `contained`, never `unplanned`, and raises no need. Measured live
    (chats 74-76): every containment room the Director minted would have
    been filed as a door the plan forgot.
    """
    folded = _folds(target)
    if not folded:
        return False
    if contained_interior_holder(target, scene):
        return True
    # ...or the entity itself. `contained_interior_holder` answers "" here on
    # purpose -- a body is not a room and has no parentage to stamp -- but the
    # ROUTING answer is unchanged: a destination that is an entity is the
    # Director's to mint, never a door the plan forgot.
    for eid, entity in ((scene or {}).get("entities") or {}).items():
        entity = entity if isinstance(entity, dict) else {}
        if folded & (_folds(eid) | _folds(entity.get("name"))):
            return True
    return False


def _folds(text):
    """The spellings one name folds to: `normalize_room_id`'s ASCII slug and
    the same slug in every script (`language_runtime.fold_key`), so a name
    written in a script the slug empties -- 宿屋, ホール -- still compares
    with itself. For ASCII the two are one string."""
    from language_runtime import fold_key
    return {normalize_room_id(str(text or "")), fold_key(text, "_")} - {""}


def contained_interior_holder(target, scene):
    """The scene entity whose INSIDE ``target`` names, as an entity id, or "".

    The same predicate `is_contained_destination` is the boolean of, kept as
    one function so the routing decision and the room's parentage can never
    disagree about which entity a destination belongs to. Returns "" when the
    target names an entity itself rather than its inside: standing at a body
    is not standing in one, and a room is what this answers about.
    """
    folded = _folds(target)
    if not folded:
        return ""
    rooms = (scene or {}).get("rooms") or {}
    room = rooms.get(str(target))
    if isinstance(room, dict) and str(room.get("parent_entity") or "").strip():
        return str(room["parent_entity"]).strip()
    holder = ""
    for eid, entity in ((scene or {}).get("entities") or {}).items():
        entity = entity if isinstance(entity, dict) else {}
        spellings = _folds(eid) | _folds(entity.get("name"))
        if folded & spellings:
            # The entity itself, not a place inside it.
            return ""
        if any(fold.startswith(sp + "_") for fold in folded for sp in spellings):
            holder = holder or str(eid)
        for rid in entity.get("interior_rooms") or ():
            if _folds(rid) & folded:
                return str(eid)
    return holder


def _transit_destination_needs(scene, planned_for, *, turn_idx, frame_id,
                               aliases=None):
    """A room need for every vehicle moving toward no room, and one for
    every vehicle moving THROUGH no room.

    A transit that names no `destination_room` can never dock (`mechanics`
    times an arrival only for a named destination), and one that names a
    place the scene does not hold and no plan reserves comes in at a name
    and no room when its way is done (below). The need makes the journey's
    end a place somebody has to plan; the vehicle keeps moving meanwhile.

    AND THE SPACE IT MOVES THROUGH (`transit_route_unplanned`, 2026-10-20).
    Under way a vehicle stands in its route room or, when the world holds no
    room for that space, in no room (`spatial_transit.settle_departures`),
    and no room is only the floor (the owner, 2026-09-25). A vehicle with an
    inside -- the one whose doorway and occupants that answer strands --
    that the scene places in no room files a need for that space: its route
    when one is named (`new:<words>` or an id nothing holds), else the
    stretch between the place it left and the place it is bound for, both
    on the surface, so the space is planned as reached from where the
    vehicle left and never as the place it is going. The control story
    (chat 1 idx 4): the Mary Ann cast off from the landing with the
    mainland street as route AND destination; refused as no between, the
    route left her in no room, and nothing asked for the water. A vehicle
    with no inside (a coach, a boat the story never boarded) is a thing in
    no room, and asks for nothing.

    AND THE PLACE A VESSEL CAME IN AT, while the world does not hold it
    (2026-10-21). A journey whose way is done docks at its end even when
    nobody built it -- off the map, in no room, its `destination_room` the
    place's name (`spatial.docked_off_the_map`, `mechanics._fire_due_events`)
    -- and stands there the beat the place is a room, so that place is one
    somebody has to plan, as it was while the vessel was under way.

    A DESTINATION THE SCENE HOLDS UNDER ANY SPELLING IS HELD: its id, its
    name, its name's words, an alias the registry keeps (`scene_room_id`,
    the reading the mechanics give the same field). This compared the
    spelling to the scene's keys exactly, so a ferry bound for "Cope's
    Boatyard" asked the Room to plan a duplicate of `copes_boatyard` (audit of
    2026-11-01, world_misc_causal F8). And A VESSEL BOUND NOWHERE is the
    vessel's need, one per vessel: filed under its own name, it asked for a
    ROOM called the vessel -- chats 154, 157 and 158 each hold an open
    `room:the tardis` need, chat 154's scene holding `tardis_console_room`
    inside that very vessel."""
    from world.planning_needs import need_identity, planning_need
    from world.spatial import docked_off_the_map, room_of_record
    needs = []
    rooms = (scene or {}).get("rooms") or {}
    for eid, ent in ((scene or {}).get("entities") or {}).items():
        state = ent.get("state") if isinstance(ent, dict) else None
        transit = state.get("transit") if isinstance(state, dict) else None
        if not isinstance(transit, dict):
            continue
        phase = str(transit.get("phase") or "").strip().casefold()
        off_map = phase == "docked" and docked_off_the_map(scene, eid, ent)
        if phase not in ("in_transit", "arriving") and not off_map:
            continue
        destination = str(transit.get("destination_room") or "").strip()
        label = str(ent.get("name") or eid)
        route = str(transit.get("route_room") or "").strip()
        origin = str(transit.get("departed_from") or "").strip()
        held = scene_room_id(scene, destination, aliases) if destination else ""
        if not (held or (destination and planned_for(destination))):
            needs.append(planning_need(
                "room", "transit_destination_unplanned",
                subject=destination or "%s -> ?" % label,
                identity=None if destination else need_identity(
                    "room", "vehicle:%s:destination" % eid),
                surface={"vehicle": str(eid),
                         "route_room": route,
                         "eta_seconds": str(transit.get("eta_seconds") or "")},
                turn_idx=turn_idx, frame_id=frame_id))
        if off_map:
            continue                        # docked: no space it moves through
        here = room_of_record(scene, eid, ent)
        if here and here in rooms:
            continue                        # in its route, or (D2) where it set off
        if not any(isinstance(room, dict)
                   and str(room.get("parent_entity") or "").strip() == str(eid)
                   for room in rooms.values()):
            continue                        # no inside: nothing is stranded
        if route and planned_for(route):
            continue                        # the plan holds that space already
        words = route[len("new:"):].strip() if route.casefold().startswith("new:") \
            else route
        needs.append(planning_need(
            "room", "transit_route_unplanned",
            subject=words or "%s -> %s" % (origin or label, destination or label),
            surface={"vehicle": str(eid), "route_room": route,
                     "departed_from": origin, "destination_room": destination},
            turn_idx=turn_idx, frame_id=frame_id))
    return needs


def _held_room_aliases(cid, scene):
    """`{room id: [spelling, ...]}`: the further names the world keeps for
    the rooms the scene holds -- the reader the prose Director resolves a
    destination through (`director_prose.room_aliases`), so the compiler and
    the Director answer "is this room held?" alike. Fail-open: no aliases,
    and every room answers to its own spellings as before."""
    try:
        from .director_prose import room_aliases
        return room_aliases(cid, (scene or {}).get("rooms") or {})
    except Exception:  # noqa: BLE001 -- the rooms' own spellings stand
        return {}


def classify_movement(interp, scene, *, planned_for, aliases=None):
    """Where the beat is going, and whether the world has it.

    ``planned_for(query)`` answers with the plan's record for a room the
    plan holds under that spelling, or None. ``aliases`` is `{room id:
    [spelling, ...]}`, the further names the world keeps for the rooms the
    scene holds (`_held_room_aliases`). Returns
    ``{"to_room", "status"}`` with status one of ``known`` (a scene room),
    ``planned`` (the plan holds it; the Director furnishes it on entry),
    ``contained`` (an entity or its inside -- the Director's to mint, see
    `is_contained_destination`), ``unplanned`` (none of these -- a planning
    need), or ``None`` when the beat declares no destination. This is the
    classification `mapping_quick` made to decide whether to escalate; it is
    now a fact on the step.
    """
    mv = interp.get("movement") if isinstance(interp, dict) else None
    target = mv.get("to_room") if isinstance(mv, dict) else None
    if not target:
        return {"to_room": None, "status": None}
    target = str(target)
    # THE WORLD'S ROOM ENTERS UNDER THE WORLD'S ID, the same rule the plan's
    # room gets below. A room answers to its id and to its name, folded
    # (`spatial.scene_room_id`); a Director that spells a room the scene
    # already holds its own way is naming that room, not a new one. Review
    # 2026-09-07 B2: this compared the model's spelling to the scene keys
    # EXACTLY while commit's mint dedup folded, so one beat could raise a
    # planning need here and a redirect there for the same room.
    #
    # AND TO EVERY NAME THE REGISTRY KEEPS FOR IT, as the prose Director reads
    # the same destination (`director_prose.destination_place`): a room minted
    # "Scullery" and renamed "Kitchen" was held for the Director and
    # unplanned here, so the compiler filed a need and `canonical_movement`
    # left the old spelling standing for the commit's destination ledgers
    # (audit of 2026-11-01, agents_runtime_loops_mapping F7).
    held = scene_room_id(scene, target, aliases)
    if held:
        out = {"to_room": held, "status": "known"}
        if held != target:
            out["declared_as"] = target
        return out
    # The compiler runs beside first-pass perception, after the Director has
    # already let the spatial hand mint the destination on THIS step.  That
    # room is not in the committed scene yet, but it is no longer missing and
    # must not become a Writers' Room debt.  In particular, entity interiors
    # are spatially authored at reveal/entry rather than preplanned.
    asserted = ((interp.get("state_assertions") or {}).get("rooms") or {})
    asserted_scene = {"rooms": asserted}
    held = scene_room_id(asserted_scene, target)
    if held:
        out = {"to_room": held, "status": "known"}
        if held != target:
            out["declared_as"] = target
        return out
    plan = planned_for(target)
    if plan:
        # THE PLAN'S ROOM ENTERS UNDER THE PLAN'S IDENTITY. The Director
        # spells a destination as it heard it ("lantern_path" for a room the
        # plan keys "coastal_lane"); the plan resolved that spelling, so the
        # step carries the plan's id and keeps the spelling as `declared_as`.
        # Measured (bench, chat 114, 2026-09-03): the slug went downstream
        # unchanged, the spatial hand found no brief under it, minted a
        # second "Lantern Path" beside the planned one, and commit filed a
        # need for a room the plan held.
        uid = str(plan.get("room_uid") or target) if isinstance(plan, dict) else target
        out = {"to_room": uid, "status": "planned"}
        if uid != target:
            out["declared_as"] = target
        return out
    if is_contained_destination(target, scene):
        return {"to_room": target, "status": "contained"}
    return {"to_room": target, "status": "unplanned"}


def _location_query_status(query, scene, *, planned_for, destination=None,
                           aliases=None):
    """A location query is answered by the scene, by the plan, or by nobody.

    The Director writes the query as a DESCRIPTION, not an id -- "Reeve's
    Hall interior and occupants", "Ford Inn kitchen Harrowmere" (21 of 21
    on the Harrowmere replay named a room this way and none was an id) --
    so a room answers it when the room's own spelling, uid, name or an alias
    the world keeps, stands in the query as a WHOLE name
    (`structure.rooms_named_whole`, the reading `structure.planned_context`
    applies to the plan). And a query that rides a beat whose destination
    the world already holds is a request for lore ABOUT that room, not for
    the room: the destination answers it.
    """
    if not query:
        return None

    if destination in ("known", "planned", "contained"):
        return destination
    from language_runtime import fold_key
    from world.structure import rooms_named_whole
    if not fold_key(query):
        return None
    rooms = (scene or {}).get("rooms") or {}
    aliases = aliases if isinstance(aliases, dict) else {}
    # Same spellings as every other reader (`spatial.room_spellings`, the
    # registry's aliases); only the PREDICATE differs, because a query is a
    # description and a description holds the room's spelling rather than
    # being it. Held as a WHOLE name: the bare substring test this was let a
    # held `inn` answer "the inner keep" and "the old spinning mill", so no
    # `location_query_unmatched` need was ever raised for either (audit of
    # 2026-11-01, agents_runtime_loops_mapping F5).
    forms = {}
    for rid, room in rooms.items():
        spellings = set(room_spellings(rid, room)) | {str(rid)}
        if isinstance(room, dict) and str(room.get("name") or "").strip():
            spellings.add(str(room["name"]))
        spellings.update(str(alias) for alias in aliases.get(str(rid)) or ())
        forms[str(rid)] = spellings
    if rooms_named_whole(query, forms):
        return "known"
    if planned_for(query):
        return "planned"
    if is_contained_destination(query, scene):
        return "contained"
    return "unmatched"


def _rulebook_text(text):
    return " ".join(str(text or "").split())[:RULEBOOK_ROW_CHARS]


def rulebook_rows(cid, scene, frame_id=None, rooms=None, figures=None):
    """The RULEBOOK slice: what the Director rules on, rendered verbatim
    from the engine's own typed data -- no model, no lore entry, no second
    authored copy. Rows: ``{source, subject, text}``. Fail-open: a story with
    no clock, no weather and no charter has no rulebook.

    ``rooms`` is the beat's aperture -- the rooms whose figures and creatures
    this rulebook describes (`common.rooms_in_view`). Omitted, every room the
    scene holds is walked, UNCAPPED: until review 2026-09-07 finding C18 this
    took the first 24 keys of `scene["rooms"]` in dict order, so a plan with
    more rooms than that could hand the Director the charter of a town four
    rooms away and omit the room the player was standing in. A dict's
    insertion order is not a measure of what a beat is about; the aperture is.

    ``figures`` is that walk's answer where the caller already has it
    (`common.figures_in_view`), so the compiler and `director_resolve` share
    one walk of the charter instead of paying two.
    """
    rows = []
    # The day. `simulation_clock` is the day cycle's ledger
    # (`persist/commit_scene_state._advance_day_cycle`).
    try:
        from world.day_cycle import (DAY_LENGTH_HOURS_DEFAULT, SUN_LIGHT,
                                     phase_of_hour, sun_light)
        clock = wget_for_frame(cid, "simulation_clock", frame_id, {}) or {}
        hour = clock.get("hour_of_day")
        length = float(clock.get("day_length_hours") or DAY_LENGTH_HOURS_DEFAULT)
        phase = clock.get("phase") or (
            phase_of_hour(float(hour), length) if hour is not None else None)
        if phase:
            from world.weather import normalize_weather as _nw
            _sky_record = _nw((scene or {}).get("weather"))
            sky = str(_sky_record.get("sky") or "")
            # What the sun gives a room is `day_cycle.sun_light`'s answer, not
            # a second copy of its table plus its dimming rule (review
            # 2026-09-07 B9). A phase this cycle does not name still says
            # nothing about the light, which is why the membership test
            # stays here rather than becoming a default of "lit" inside it.
            light = sun_light(phase, _sky_record or None) \
                if phase in SUN_LIGHT else ""
            text = "The day here runs %g hours; it is %s%s." % (
                length, phase,
                (" (about hour %g)" % round(float(hour), 1)) if hour is not None else "")
            if light:
                text += " The sun gives an outdoor room %s light%s." % (
                    light, (" under a %s sky" % sky) if sky else "")
            rows.append({"source": "day_cycle", "subject": "the day",
                         "text": _rulebook_text(text)})
    except Exception:
        pass
    # The weather, as declared (`world/weather.normalize_weather`).
    try:
        from world.weather import is_falling, normalize_weather
        weather = normalize_weather((scene or {}).get("weather"))
        if weather:
            parts = ["sky %s" % weather.get("sky")]
            # `is_falling` rather than the name: since A88 a sky keeps the
            # name of what it drops through a dry spell, and `intensity` is
            # the one field that says whether anything is coming down.
            if is_falling(weather):
                parts.append("%s %s" % (weather.get("intensity") or "",
                                        weather["precipitation"]))
            if weather.get("wind"):
                parts.append("wind %s" % weather["wind"])
            if weather.get("temperature"):
                parts.append("%s" % weather["temperature"])
            rows.append({"source": "weather", "subject": "the weather",
                         "text": _rulebook_text("Weather: " + ", ".join(
                             " ".join(p.split()) for p in parts) + ".")})
    except Exception:
        pass
    # Institutions and creatures in view (`world/charter_runtime`).
    try:
        from agents.common import present_charter_figures
        from world.charter_creature import normalize_creature
        from world.charter_runtime import registry_for
        if figures is None:
            walk = ({str(r) for r in rooms if str(r or "")}
                    if rooms is not None
                    else {str(r) for r in ((scene or {}).get("rooms") or {})})
            figures = present_charter_figures(
                cid, scene, walk, frame_id=frame_id) if walk else []
        by_charter = {}
        for row in figures:
            key = str(row.get("charter") or "")
            if key:
                by_charter.setdefault(key, []).append(row)
        if by_charter:
            registry = registry_for(cid, frame_id) or {}
            items = registry.get("items") or {}
            for key, present in by_charter.items():
                item = items.get(key) or {}
                state = item.get("state") if isinstance(item.get("state"), dict) else item
                name = str(state.get("name") or state.get("title") or key)
                creature = normalize_creature(state.get("creature"))
                if creature:
                    text = ("%s is a creature: it hunts %s within %d room(s) of "
                            "itself, %s open doors, and is abroad %s. It is %s "
                            "bold; %d of its kind stand here." % (
                                name, ", ".join(creature["prey"]) or "nothing",
                                creature["senses"]["range_rooms"],
                                "can" if creature["can_open_doors"] else "cannot",
                                ("in the %s" % ", ".join(creature["active_phases"]))
                                if creature["active_phases"] else "at any hour",
                                "%.0f%%" % (100 * creature["boldness"]), len(present)))
                    if creature["bargains"]:
                        text += " It holds a bargain with %s." % ", ".join(
                            b["with"] for b in creature["bargains"])
                    rows.append({"source": "creature:%s" % key, "subject": name,
                                 "text": _rulebook_text(text)})
                    continue
                posts = {}
                for row in present:
                    for post in row.get("posts") or ():
                        posts[post] = posts.get(post, 0) + 1
                if posts:
                    text = "%s holds these posts here: %s." % (name, ", ".join(
                        "%s (%d)" % (post, n) if n > 1 else post
                        for post, n in sorted(posts.items())))
                    rows.append({"source": "charter:%s" % key, "subject": name,
                                 "text": _rulebook_text(text)})
    except Exception:
        pass
    return rows[:RULEBOOK_ROWS_CAP]


def compile_world_context(ctx, nonce):
    """Assemble the beat's world context from the story's own rows.

    Deterministic: same inputs, same output. ONE provider round trip, for the
    lore query's embedding (`search_lore` -> `embed_texts_meta`), which is
    why the runtime runs this beside action-onset perception rather than
    ahead of it. ``nonce`` is accepted for the step-handler signature and
    unused -- a reroll of this step is the same compilation.
    """
    from world.planning_needs import NEED_KINDS, planning_need
    from world.structure import planned_context

    chat = ctx.chat
    cid = chat["id"]
    interp = ctx.get("director_interpret") or {}
    fl = interp.get("flow") if isinstance(interp.get("flow"), dict) else {}

    query = _query(ctx, interp)
    books = _books(ctx, refresh=True)
    weights = _book_weights(ctx, refresh=True)
    frame_id = getattr(ctx.turn, "frame_id", None)
    hits = search_lore(weights, query, k=WORLD_CONTEXT_LORE_K,
                       exclude_categories=["knowledge"],
                       chat_id=cid, frame_id=frame_id)
    # Living world, approach D: a location entry the beat is about to work
    # from may carry the history the unvisited place has accrued. This seam
    # is the obligation ledger's ONLY consumer -- the place's debt surfaces
    # where the place itself is compiled, never in any mind's payload;
    # arrival is the earning event.
    owed = 0
    try:
        from world.living_world import attach_owed_history
        before = [dict(h) for h in hits]
        hits = attach_owed_history(cid, hits)
        owed = sum(1 for b, a in zip(before, hits)
                   if isinstance(a, dict) and a.get("content") != b.get("content"))
    except Exception as exc:
        ctx.add_warning(f"owed history not attached: {exc}")

    fresh = [_lore_row(h) for h in hits if isinstance(h, dict)]
    # Owed history is attached to the hit's `content`, which `_lore_row`
    # carries -- so the debt rides the step exactly as it rode the model
    # payload, and `lore_for` serves it to the Director.
    cache = wget(cid, "lore_cache", []) or []
    merged = merge_lore(fresh, cache)[:WORLD_CONTEXT_LORE_CAP]

    valid = set(books)
    relevant_books = []
    for entry in merged:
        try:
            bid = int(entry.get("book_id"))
        except (TypeError, ValueError):
            continue
        if bid in valid and bid not in relevant_books:
            relevant_books.append(bid)

    scene = get_scene(cid, chat)
    aliases = _held_room_aliases(cid, scene)

    def planned_for(spelling):
        try:
            return planned_context(cid, spelling)
        except Exception as exc:
            ctx.add_warning(f"planned room context not attached: {exc}")
            return None

    movement = classify_movement(interp, scene, planned_for=planned_for,
                                 aliases=aliases)
    location_query = interp.get("location_query") or None
    query_status = _location_query_status(
        location_query, scene, planned_for=planned_for,
        destination=movement["status"], aliases=aliases)

    planned = None
    if movement["status"] == "planned":
        planned = planned_for(movement["to_room"])
    elif query_status == "planned":
        planned = planned_for(location_query)

    needs = []
    turn_idx = getattr(ctx.turn, "idx", 0) or 0
    mv = interp.get("movement") if isinstance(interp.get("movement"), dict) else {}
    if movement["status"] == "unplanned":
        needs.append(planning_need(
            "room", "declared_destination_unplanned",
            subject=movement["to_room"],
            surface={"why": str(mv.get("why") or ""),
                     "request": str(fl.get("mapping_request") or "")},
            turn_idx=turn_idx, frame_id=frame_id))
    if query_status == "unmatched":
        needs.append(planning_need(
            "room", "location_query_unmatched",
            subject=location_query,
            surface={"request": str(fl.get("mapping_request") or "")},
            turn_idx=turn_idx, frame_id=frame_id))
    for request in (fl.get("generation_requests") or []):
        if not isinstance(request, dict):
            continue
        subject = request.get("subject") or request.get("location_id")
        if not subject:
            continue
        # A request for a room the plan holds is not a need: the plan is
        # the answer, and the Director is handed it (`planned_rooms`). The
        # plan holds only rooms, so a plan room under the request's name
        # answers any request but one that SAYS it is a person or a thing --
        # whatever word it uses for a place, or none. This asked the plan
        # only of `room` and of no kind, and the ledger then filed the
        # kindless one as a PERSON (audit of 2026-11-01, world_misc_causal
        # F9): one request, two kinds. An unstated kind is now `thing` in
        # both readers (`planning_needs.need_kind`).
        stated = str(request.get("kind") or "").strip().casefold()
        if not (stated in NEED_KINDS and stated != "room") and (
                planned_for(subject) or planned_for(request.get("location_id"))):
            continue
        try:
            needs.append(planning_need(
                request.get("kind"), "generation_request",
                subject=subject,
                surface={k: request[k] for k in (
                    "location_id", "constraints", "urgency") if request.get(k)},
                turn_idx=turn_idx, frame_id=frame_id))
        except ValueError as exc:
            ctx.add_warning(f"generation request not recorded: {exc}")
    for need in _transit_destination_needs(scene, planned_for,
                                           turn_idx=turn_idx,
                                           frame_id=frame_id,
                                           aliases=aliases):
        needs.append(need)
    # One need per identity: the same door reached twice in one beat, under
    # whatever reasons, is one need (the first reason is kept).
    unique, seen = [], set()
    for need in needs:
        if need["identity"] in seen:
            continue
        seen.add(need["identity"])
        unique.append(need)

    summary = (f"{len(merged)} lore entries compiled from "
               f"{len(relevant_books)} book(s)")
    if unique:
        summary += f"; {len(unique)} planning need(s) raised"
    # THE BEAT'S APERTURE, derived once (`common.rooms_in_view`, C18) and
    # recorded on the step: the rulebook's charter walk reads it here and
    # `director_resolve` reads the same answer off the context rather than
    # deriving a second one. The player's room comes from THIS stage's own
    # scene read -- the compiler runs beside `perception_act`, which may
    # refresh `ctx["_player_room"]`, and a stage documented deterministic
    # must not depend on which of the two lands first.
    try:
        _pers = persona_of(chat) or {}
        _p_name = _pers.get("name") or persona_name(_pers)
        _view = rooms_in_view(
            ctx, scene,
            (room_of(scene, _p_name) if _p_name else None)
            or ctx.get("_player_room"),
            movement.get("to_room") if isinstance(movement, dict) else None)
    except Exception as exc:
        # Fail-open WIDE, not narrow: an aperture that could not be derived
        # walks every room rather than none, so a charter the beat is
        # standing in front of is never silently dropped.
        ctx.add_warning(f"rooms in view not derived: {exc}")
        _view = None
    _moved = {"lines": [], "snapshot": {"places": {}, "acts": []}}
    try:
        from world.charter_runtime import charter_moves_since
        _moved = charter_moves_since(
            cid, _view or (),
            wget_for_frame(cid, "charter_last_places", frame_id, {}) or {},
            frame_id=frame_id)
    except Exception as exc:
        ctx.add_warning(f"charter moves not derived: {exc}")
    # The one walk of the charter for that aperture, shared with resolve
    # (`common.figures_in_view`). Guarded on its own so a charter that cannot
    # be read costs the charter rows and not the day and the weather beside
    # them -- which is what the inner guard inside `rulebook_rows` did while
    # the walk lived there.
    _figures = None
    if _view is not None:
        try:
            _figures = figures_in_view(ctx, scene, _view, frame_id)
        except Exception as exc:
            ctx.add_warning(f"figures in view not derived: {exc}")
            _figures = []
    try:
        rulebook = rulebook_rows(cid, scene, frame_id, rooms=_view,
                                 figures=_figures)
    except Exception as exc:
        ctx.add_warning(f"rulebook not compiled: {exc}")
        rulebook = []

    return {
        "relevant_lore": merged,
        "relevant_books": relevant_books,
        # Engine rows the Director rules on, rendered from typed data.
        "rulebook": rulebook,
        # The rooms this beat is about (C18): the player's room, its ambient
        # scope, and a declared destination. One derivation, read by the
        # rulebook above and by `director_resolve`'s figures in view.
        "rooms_in_view": sorted(_view or ()),
        # What the charter moved since the last beat, in the rooms the beat
        # is about (`charter_runtime.charter_moves_since`): lines the
        # Director is handed as author notes, and the snapshot the commit
        # persists for the next beat to compare against. The world moves
        # every beat; this is how the page hears of it.
        "charter_moves": _moved["lines"],
        "charter_places_seen": _moved["snapshot"],
        # The compiler never stages and never patches: a room the beat
        # reached with no plan is a NEED, not a proposal.
        "staged_lore": [],
        "scene_patch": _normalize_scene_patch({}),
        "movement": movement,
        "location_query": {"query": location_query, "status": query_status}
                          if location_query else None,
        **({"planned": planned} if planned else {}),
        "planning_needs": unique,
        "owed_history_attached": owed,
        "compiled": True,
        "summary": summary,
    }


def merge_lore(hits, cache):
    """Fresh retrieval first, cached entries after, one copy of each entry.

    `id` FIRST, because it is the one field two revisions of the same entry
    must share. Lore entries ACCRETE -- the engine appends narrative events to
    them -- and the cache stores SNAPSHOTS rather than references, so the same
    entry can sit here twice at two lengths.

    `entry_uid or fingerprint` could not collide those. A cached dict written
    before the uid was carried through has none, so it falls to the
    fingerprint, and a uid and a fingerprint live in different namespaces. The
    fingerprint cannot rescue it either: it hashes keys+content, which is
    exactly what differs between two revisions.

    Measured live, chat 59: ten cached entries, nine distinct ids, entry 2213
    present twice at 1,572 and 1,442 characters. The shorter copy predates a
    sentence the longer one carries, so the model was handed the same room
    twice at two revisions, one of which did not know a character had gone
    upstairs. A contradiction served as retrieved lore, not a wasted slot.

    `hits` precede `cache`, so keeping the first occurrence keeps the freshly
    retrieved revision and drops the fossil.
    """
    seen, merged = set(), []
    for e in list(hits or []) + list(cache or []):
        if not isinstance(e, dict):
            continue
        key = e.get("id") or e.get("entry_uid") or _lore_fingerprint(e)
        if key in seen:
            continue
        seen.add(key)
        merged.append(e)
    return merged
