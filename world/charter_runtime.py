"""Production seam for the pure institution/upkeep simulator.

The ``charter_*`` package deliberately owns no I/O.  This module owns the
small amount of I/O required to make it diegetic: frame-scoped state, one
out-of-band catch-up job per off-screen epoch, rollback/epoch guards, and
stable consequence rows on the existing scheduled-event rail.

Definitions remain explicit author input.  Merely enabling off-screen life
does not invent an institution; a stored registry with at least one item is
the opt-in.
"""

from __future__ import annotations

import copy
import json

from core import jobs
from core.logging_utils import logger
from world.charter import normalize_charter, run
from world.charter_news import WITNESSABLE
from world.mechanics import stable_event_key


CHARTERS_KEY = "charters"
REGISTRY_VERSION = 1
DEFAULT_WINDOW_HOURS = 4.0
MAX_CATCHUP_HOURS = 720.0
DEFAULT_PRESIM_TAIL_HOURS = 96.0
GENERATION_LORE_LIMIT = 48
CAST_HISTORY_REQUEST_CAP = 16

#: Different institutions sharing one place exchange through a few actual
#: bodies, never by merging registers or broadcasting to both populations.
CROSS_CHARTER_GOSSIP_CAP = 8


def _window_hours(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        value = DEFAULT_WINDOW_HOURS
    return max(0.25, min(24.0, value))


def normalize_registry(stored):
    """Normalize author definitions and runtime markers into one JSON shape."""
    stored = stored if isinstance(stored, dict) else {}
    raw_items = stored.get("items")
    if not isinstance(raw_items, dict):
        # Authoring convenience: a bare ``{key: charter}`` map is accepted.
        raw_items = {
            key: value for key, value in stored.items()
            if key not in {"version", "recent_events"}
            and isinstance(value, dict)
        }
    items = {}
    for key, raw in raw_items.items():
        raw = raw if isinstance(raw, dict) else {}
        state = raw.get("state") if isinstance(raw.get("state"), dict) else raw
        state = normalize_charter(state)
        state["key"] = str(state.get("key") or key)
        last = raw.get("last_elapsed_seconds")
        try:
            last = None if last is None else max(0.0, float(last))
        except (TypeError, ValueError):
            last = None
        items[str(key)] = {
            "state": state,
            "window_hours": _window_hours(raw.get("window_hours")),
            "last_elapsed_seconds": last,
            "last_epoch_id": str(raw.get("last_epoch_id") or ""),
        }
    # Older development snapshots may contain ``recent_events``. Deliberately
    # discard it: incidents have one durable home, scheduled_events ->
    # world_events. The Charter registry stores current simulation state only.
    return {"version": REGISTRY_VERSION, "items": items}


def registry_for(cid, frame_id=None):
    from core.db import wget_for_frame
    return normalize_registry(
        wget_for_frame(cid, CHARTERS_KEY, frame_id, {}) or {})


def save_registry(cid, stored, frame_id=None):
    """Persist an explicitly authored registry in one temporal frame."""
    from core.db import wset_for_frame
    normalized = normalize_registry(stored)
    wset_for_frame(cid, CHARTERS_KEY, normalized, frame_id)
    return normalized


def _prepare_cast_histories(cid, request, *, frame_id=None):
    """Resolve quick-start history routes and add only safe resident seeds.

    Browser keys never identify people here.  Every request is resolved back
    to an actual character attached to this story before any public slice is
    allowed into the location planner.
    """
    from core.db import q, wget_for_frame, wset_for_frame
    from story.character_schema import normalize_character_data
    from story.history_routing import (
        resolve_character_history_route, route_uses_charter)
    from world.charter_history import (
        featured_resident_private_habits, featured_resident_seed)

    raw = request.get("character_histories")
    if not isinstance(raw, list):
        return request, []
    requested = []
    seen = set()
    for value in raw:
        if not isinstance(value, dict):
            continue
        try:
            char_id = int(value.get("char_id"))
        except (TypeError, ValueError):
            continue
        if char_id <= 0 or char_id in seen:
            continue
        seen.add(char_id)
        requested.append((char_id, value))
    if len(requested) > CAST_HISTORY_REQUEST_CAP:
        raise ValueError(
            "a lived-location start can generate history for at most "
            f"{CAST_HISTORY_REQUEST_CAP} full characters at once; Charter "
            "residents themselves are not limited by this cognition budget")
    if not requested:
        clean = dict(request)
        clean.pop("character_histories", None)
        return clean, []

    placeholders = ",".join("?" for _ in requested)
    rows = q(
        "SELECT cc.char_id, COALESCE(NULLIF(cc.sheet,''), ch.sheet) sheet "
        "FROM chat_chars cc JOIN characters ch ON ch.id=cc.char_id "
        f"WHERE cc.chat_id=? AND cc.char_id IN ({placeholders})",
        (cid, *(char_id for char_id, _value in requested)))
    sheets = {
        int(row["char_id"]): normalize_character_data(
            json.loads(row["sheet"] or "{}"))
        for row in rows
    }
    chat = q("SELECT scenario FROM chats WHERE id=?", (cid,), one=True)
    opening = str(chat["scenario"] or "") if chat else ""
    clean = copy.deepcopy(request)
    clean.pop("character_histories", None)
    featured = [copy.deepcopy(row) for row in clean.get(
        "featured_residents", []) if isinstance(row, dict)]
    featured_ids = {str(row.get("seed_id") or "") for row in featured}
    private = copy.deepcopy(clean.get("featured_resident_private") or {})
    if not isinstance(private, dict):
        private = {}
    routes = wget_for_frame(
        cid, "character_history_routes", frame_id, {}) or {}
    prepared = []
    for char_id, value in requested:
        sheet = sheets.get(char_id)
        if not sheet:  # A character outside this story has no authority here.
            continue
        route = resolve_character_history_route(
            sheet, requested=value, opening=opening,
            location_brief=clean.get("brief") or "")
        route["guidance"] = str(value.get("brief") or "")[:2000]
        routes[str(char_id)] = copy.deepcopy(route)
        prepared.append({"char_id": char_id, "sheet": sheet, "route": route})
        if route_uses_charter(route):
            seed = featured_resident_seed(char_id, sheet)
            if seed["seed_id"] not in featured_ids:
                featured.append(seed)
                featured_ids.add(seed["seed_id"])
            private[seed["seed_id"]] = {
                "habits": featured_resident_private_habits(sheet)}
    wset_for_frame(cid, "character_history_routes", routes, frame_id)
    if featured:
        clean["featured_residents"] = featured
    if private:
        clean["featured_resident_private"] = private
    return clean, prepared


def _complete_cast_histories(cid, request, prepared, generated, *,
                             frame_id=None):
    """Compile the selected topology and record the cognition handoff."""
    from core.db import q, wget_for_frame, wset_for_frame
    from story.character_schema import character_name
    from story.history_routing import route_uses_charter

    if not prepared or not isinstance(generated, dict) or not generated.get("ok"):
        return
    routes = wget_for_frame(
        cid, "character_history_routes", frame_id, {}) or {}
    bindings = generated.get("featured_residents") or {}
    opening_row = q(
        "SELECT scenario FROM chats WHERE id=?", (cid,), one=True)
    opening = str(opening_row["scenario"] or "") if opening_row else ""
    for item in prepared:
        char_id, sheet, route = (
            item["char_id"], item["sheet"], item["route"])
        if route_uses_charter(route):
            binding = bindings.get(f"character:{char_id}")
            if not binding:
                raise ValueError(
                    f"lived location did not place featured character {char_id}")
            from world.charter_history import integrate_featured_resident
            result = integrate_featured_resident(
                cid, char_id, binding, sheet, frame_id=frame_id,
                author_guidance=route.get("guidance") or "")
            routes[str(char_id)]["handoff"] = {
                "complete": True,
                "memory_count": len(result.get("memory_event_keys") or ()),
                "binding": copy.deepcopy(binding),
            }
            continue

        is_journey = (
            route.get("mode") in {"visitor", "generated_journey"}
            or (route.get("mode") == "auto"
                and route.get("opening_relationship") == "visiting"))
        if not is_journey:
            routes[str(char_id)]["handoff"] = {
                "complete": True, "memory_count": 0,
                "backend": "authored card" if route.get("backends") else "none",
            }
            continue
        from story.journey_history import compile_journey_history
        lore, _source = generation_lore(
            cid, request.get("lorebook_id"),
            query=f"{character_name(sheet)} journeys visits history")
        try:
            result = compile_journey_history(
                cid, char_id, sheet, route, lore=lore, opening=opening,
                frame_id=frame_id)
            routes[str(char_id)]["handoff"] = {
                "complete": True,
                "memory_count": len(result.get("memory_event_keys") or ()),
                "journey_events": len(result.get("events") or ()),
            }
        except Exception as exc:
            if route.get("mode") == "generated_journey":
                raise
            routes[str(char_id)]["handoff"] = {
                "complete": False,
                "safe_fallback": "authored card only",
                "error": f"{type(exc).__name__}: {str(exc)[:240]}",
            }
    wset_for_frame(cid, "character_history_routes", routes, frame_id)


def registry_revision(registry):
    """Stable identity for the exact author/runtime state a job advanced."""
    encoded = json.dumps(normalize_registry(registry), sort_keys=True,
                         ensure_ascii=False, separators=(",", ":"))
    return stable_event_key("charter_registry", encoded)


def presim_registry(registry, *, horizon_hours=MAX_CATCHUP_HOURS,
                    active_tail_hours=DEFAULT_PRESIM_TAIL_HOURS,
                    tail_places=(), seed=0):
    """Live a generated registry forward before the first story beat.

    The long body establishes durable service, acquaintance, politics and
    stock movement cheaply. The recent tail enables practices at authored
    places so Scene Life has fresh episodes to draw on. Returned events are
    objective history; no memories are fabricated from the history brief.
    """
    registry = normalize_registry(copy.deepcopy(registry))
    horizon = max(0.0, min(MAX_CATCHUP_HOURS, float(horizon_hours or 0.0)))
    tail = max(0.0, min(horizon, float(active_tail_hours or 0.0)))
    coarse = horizon - tail
    produced = []
    for index, (key, item) in enumerate(sorted(registry["items"].items())):
        state = copy.deepcopy(item["state"])
        if coarse:
            state["active_places"] = []
            state, events = run(
                state, coarse, window=max(8.0, item["window_hours"]),
                seed=int(seed) + index * 100_000)
            produced.extend({"charter": key, **copy.deepcopy(event)}
                            for event in events)
        if tail:
            state["active_places"] = sorted({str(x) for x in tail_places
                                               if str(x)})
            state, events = run(
                state, tail, window=min(4.0, item["window_hours"]),
                seed=int(seed) + index * 100_000 + 50_000)
            produced.extend({"charter": key, **copy.deepcopy(event)}
                            for event in events)
        item["state"] = state
        item["last_elapsed_seconds"] = 0.0
        item["last_epoch_id"] = "presim"
    return normalize_registry(registry), produced


def generation_lore(cid, lorebook_id=None, entry_ids=None,
                    *, limit=GENERATION_LORE_LIMIT, query=""):
    """Bounded lore selected explicitly for one lived-location generation.

    The selected book and its descendants are the authoring scope.  This is
    intentionally narrower than ordinary retrieval, which may walk ancestors
    and reference links: choosing a city book must not quietly let an attached
    rules compendium or unrelated nation design the city instead.  A global
    library book is accepted for the create-story seam; story-local books must
    belong to this story.
    """
    from core.db import q
    from mind.memory import lorebook_descendants

    chat = q("SELECT id,lorebook_id FROM chats WHERE id=?", (cid,), one=True)
    if not chat:
        raise ValueError("story not found")
    source = lorebook_id if lorebook_id not in (None, "") \
        else chat["lorebook_id"]
    if source in (None, ""):
        return [], None
    try:
        source = int(source)
    except (TypeError, ValueError) as exc:
        raise ValueError("lorebook_id must be a number") from exc
    book = q("SELECT id,chat_id FROM lorebooks WHERE id=?", (source,), one=True)
    if not book:
        raise ValueError(f"lorebook {source} not found")
    if book["chat_id"] is not None and int(book["chat_id"]) != int(cid):
        raise ValueError("selected lorebook belongs to another story")
    scoped = lorebook_descendants(source)
    if book["chat_id"] is not None:
        scoped = [lid for lid in scoped if q(
            "SELECT 1 FROM lorebooks WHERE id=? AND chat_id=?",
            (lid, cid), one=True)]
    selected_entries = []
    for value in entry_ids or ():
        try:
            selected_entries.append(int(value))
        except (TypeError, ValueError):
            raise ValueError("lore_entry_ids must contain numbers")
    if not scoped:
        return [], source
    placeholders = ",".join("?" for _ in scoped)
    params = list(scoped)
    sql = (
        "SELECT le.id,le.title,le.content,lb.name book_name "
        "FROM lore_entries le JOIN lorebooks lb ON lb.id=le.lorebook_id "
        f"WHERE le.lorebook_id IN ({placeholders})")
    if selected_entries:
        entry_ph = ",".join("?" for _ in selected_entries)
        sql += f" AND le.id IN ({entry_ph})"
        params.extend(selected_entries)
    bounded = max(1, min(GENERATION_LORE_LIMIT, int(limit)))
    if selected_entries or not str(query or "").strip():
        sql += " ORDER BY le.lorebook_id,le.id LIMIT ?"
        params.append(bounded)
        rows = q(sql, tuple(params))
    else:
        # Generation is a retrieval problem, not an insertion-order problem.
        # The ordinary lore ranker already combines semantic and lexical
        # relevance across an arbitrarily large selected subtree. Reusing it
        # keeps a 2,000-entry library from making "the first 48 rows" author
        # the requested city merely because they were imported first.
        from mind.memory import search_lore
        hits = search_lore(scoped, str(query), k=bounded)
        ranked_ids = [int(hit["id"]) for hit in hits if hit.get("id")]
        # Setting-law entries are constraints rather than relevance hits.
        # Keep a small bounded prefix even when the requested location shares
        # none of their vocabulary; otherwise retrieval can faithfully find a
        # place while silently dropping the book's rules for depicting it.
        rule_rows = q(
            "SELECT id FROM lore_entries "
            f"WHERE lorebook_id IN ({placeholders}) AND ("
            "LOWER(COALESCE(category,'')) IN ('rule','rules') OR "
            "LOWER(LTRIM(COALESCE(content,''))) LIKE '<rules>%') "
            "ORDER BY lorebook_id,id LIMIT 4", tuple(scoped))
        ordered_ids = []
        for entry_id in [row["id"] for row in rule_rows] + ranked_ids:
            if entry_id not in ordered_ids:
                ordered_ids.append(entry_id)
        ordered_ids = ordered_ids[:bounded]
        if ordered_ids:
            ranked_ph = ",".join("?" for _ in ordered_ids)
            fetched = q(
                "SELECT le.id,le.title,le.content,lb.name book_name "
                "FROM lore_entries le JOIN lorebooks lb "
                "ON lb.id=le.lorebook_id "
                f"WHERE le.id IN ({ranked_ph})", tuple(ordered_ids))
            by_id = {row["id"]: row for row in fetched}
            rows = [by_id[entry_id] for entry_id in ordered_ids
                    if entry_id in by_id]
        else:
            sql += " ORDER BY le.lorebook_id,le.id LIMIT ?"
            params.append(bounded)
            rows = q(sql, tuple(params))
    if selected_entries and len(rows) != len(set(selected_entries)):
        raise ValueError("one or more lore entries are outside the selected book")
    return [{"id": row["id"], "book": row["book_name"],
             "title": row["title"], "content": row["content"]}
            for row in rows], source


def _generation_lore_query(request, brief):
    """The requested place and its author-required facets, as one query."""
    parts = [request.get("name"), brief, request.get("scale"),
             request.get("topology")]
    for room in request.get("required_rooms") or ():
        if isinstance(room, dict):
            parts.extend((room.get("name"), room.get("purpose")))
        elif isinstance(room, str):
            parts.append(room)
    return "\n".join(str(part).strip() for part in parts
                      if str(part or "").strip())


def _unique_generated_key(base, taken):
    base = str(base or "generated").strip() or "generated"
    if base not in taken:
        return base
    index = 2
    while f"{base}_{index}" in taken:
        index += 1
    return f"{base}_{index}"


def _remap_generated_town(cid, town, existing_registry):
    """Give an added location its own stable namespace when ids collide."""
    from core.db import q, wget_for_frame
    from world.spatial import normalize_room_id

    town = copy.deepcopy(town)
    stored_structures = wget_for_frame(cid, "structures", None, {}) or {}
    structure_items = stored_structures.get("items") \
        if isinstance(stored_structures.get("items"), dict) \
        else stored_structures
    taken_structures = {str(key) for key in (structure_items or {})}
    old_structure = str((town.get("structure") or {}).get("key") or "location")
    structure_key = _unique_generated_key(old_structure, taken_structures)
    existing_rooms = {str(row["room_uid"]) for row in q(
        "SELECT room_uid FROM room_registry WHERE chat_id=? ", (cid,))}
    generated_rooms = {str(uid) for uid in (town.get("rooms") or {})}
    needs_namespace = structure_key != old_structure \
        or bool(existing_rooms.intersection(generated_rooms))
    room_map = {uid: uid for uid in generated_rooms}
    if needs_namespace:
        taken = set(existing_rooms)
        room_map = {}
        for uid in sorted(generated_rooms):
            stem = normalize_room_id(f"{structure_key} {uid}") \
                or f"{structure_key}_{len(room_map) + 1}"
            mapped = _unique_generated_key(stem, taken)
            taken.add(mapped)
            room_map[uid] = mapped

    rooms = {}
    for old_uid, raw in (town.get("rooms") or {}).items():
        room = copy.deepcopy(raw)
        for edge in room.get("adjacent") or ():
            if isinstance(edge, dict):
                edge["to"] = room_map.get(str(edge.get("to")), edge.get("to"))
        rooms[room_map[str(old_uid)]] = room
    town["rooms"] = rooms
    town.setdefault("structure", {})["key"] = structure_key

    taken_charters = set((existing_registry.get("items") or {}).keys())
    charters = {}
    for old_key, raw in (town.get("charters") or {}).items():
        new_key = _unique_generated_key(old_key, taken_charters)
        taken_charters.add(new_key)
        state = copy.deepcopy(raw)
        state["key"] = new_key
        state["structure"] = structure_key
        for collection in ("upkeeps", "posts", "bodies"):
            for value in (state.get(collection) or {}).values():
                if not isinstance(value, dict):
                    continue
                for field in ("place", "berth"):
                    if value.get(field) is not None:
                        value[field] = room_map.get(
                            str(value[field]), value[field])
        for market in ((state.get("economy") or {}).get("markets") or {}).values():
            if isinstance(market, dict) and market.get("place") is not None:
                market["place"] = room_map.get(
                    str(market["place"]), market["place"])
        for intervention in state.get("interventions") or ():
            if not isinstance(intervention, dict):
                continue
            if intervention.get("charter") == old_key:
                intervention["charter"] = new_key
            if intervention.get("place") is not None:
                intervention["place"] = room_map.get(
                    str(intervention["place"]), intervention["place"])
        charters[new_key] = normalize_charter(state)
    town["charters"] = charters
    town["structure"]["charters"] = list(charters)
    return town


def generate_lived_location(cid, request, *, frame_id=None):
    """Generate and add one lore-grounded, presimulated Charter location.

    Existing locations and institutions are preserved.  Only the newly
    generated registry slice is lived through its prehistory, so adding a
    spaceport halfway through a story cannot age the town already in play by
    another month.
    """
    from core.db import q, wget_for_frame
    from world.charter_generate import (
        close_plan, ensure_required_rooms, narrate_actual_history,
        propose_history, propose_town)
    from world.structure import plant_structure, structure_warnings

    request = request if isinstance(request, dict) else {}
    chat = q("SELECT * FROM chats WHERE id=?", (cid,), one=True)
    if not chat:
        raise ValueError("story not found")
    request, cast_histories = _prepare_cast_histories(
        cid, request, frame_id=frame_id)
    lore = request.get("lore")
    source_book = request.get("lorebook_id")
    brief = str(request.get("brief") or chat["scenario"]
                or chat["name"] or "inhabited location")
    lore_query = _generation_lore_query(request, brief)
    if lore is None:
        lore, source_book = generation_lore(
            cid, source_book, request.get("lore_entry_ids"),
            query=lore_query)
    elif source_book not in (None, ""):
        # Explicit lore is allowed for tools, but a claimed provenance book
        # still has to exist in this authoring scope.
        _unused, source_book = generation_lore(cid, source_book, limit=1)
    owning_book = request.get("owning_lorebook_id") or source_book
    if request.get("owning_lorebook_id") not in (None, ""):
        try:
            owning_book = int(request["owning_lorebook_id"])
        except (TypeError, ValueError) as exc:
            raise ValueError("owning_lorebook_id must be a number") from exc
        owner = q("SELECT chat_id FROM lorebooks WHERE id=?",
                  (owning_book,), one=True)
        if not owner or int(owner["chat_id"] or -1) != int(cid):
            raise ValueError("owning lorebook must belong to this story")
    horizon = max(0.0, min(
        MAX_CATCHUP_HOURS,
        float(request.get("horizon_hours", MAX_CATCHUP_HOURS))))
    constraints = {
        key: copy.deepcopy(request.get(key))
        for key in ("scale", "topology", "required_rooms",
                    "featured_residents")
        if request.get(key) not in (None, "", [])}
    plan = (propose_town(lore, brief, constraints=constraints)
            if constraints else propose_town(lore, brief))
    history = {}
    wants_history = bool(request.get("generate_history", True)) and horizon > 0
    if wants_history:
        history = propose_history(plan, lore, horizon)
    town = close_plan(
        plan, history=history,
        featured_residents=request.get("featured_residents"))
    unnamed = [
        f"{charter_key}/{body_key}"
        for charter_key, state in town["charters"].items()
        for body_key, body in (state.get("bodies") or {}).items()
        if not str(body.get("name") or "").strip()
        or str(body.get("name") or "").strip() == str(body_key)
    ]
    if unnamed:
        raise ValueError(
            "generated lived location did not provide a usable naming law "
            "for every resident: " + ", ".join(unnamed[:8]))
    # Private character material crosses only after the public location plan
    # has closed and only onto the exact body selected by resident_seed_id.
    # It cannot shape rooms, posts, lore, or anybody else's state.
    private_by_seed = request.get("featured_resident_private") or {}
    if isinstance(private_by_seed, dict):
        for state in town["charters"].values():
            for body in state.get("bodies", {}).values():
                seed_id = str(body.get("resident_seed_id") or "")
                private = private_by_seed.get(seed_id)
                if isinstance(private, dict) and private.get("habits"):
                    body["private_habits"] = copy.deepcopy(private["habits"])
    lore_manifest = {
        "source_lorebook_id": source_book,
        "entry_ids": [entry.get("id") for entry in lore
                      if isinstance(entry, dict) and entry.get("id") is not None],
        "query": lore_query,
    }
    for state in town["charters"].values():
        state.setdefault("history", {}).setdefault(
            "architecture", {})["generation_lore"] = copy.deepcopy(
                lore_manifest)
    required_rooms_added = ensure_required_rooms(
        town, request.get("required_rooms"))
    requested_name = str(request.get("name") or "").strip()
    if requested_name:
        # Display spelling is author authority. The stable structure key stays
        # machine-normalized and collision-safe; names are allowed to retain
        # punctuation and case exactly as the author supplied them.
        town["name"] = requested_name
        town["structure"]["name"] = requested_name
    existing = registry_for(cid, frame_id)
    town = _remap_generated_town(cid, town, existing)
    structure, rooms = plant_structure(
        cid, town["structure"], town["rooms"],
        owning_book_id=owning_book)
    generated = normalize_registry({"items": {
        key: {"state": state,
              "window_hours": float(request.get("window_hours", 4.0))}
        for key, state in town["charters"].items()}})
    combined = copy.deepcopy(existing)
    combined["items"].update(copy.deepcopy(generated["items"]))
    combined = save_registry(cid, combined, frame_id)
    source_revision = registry_revision(combined)
    tail_places = list(request.get("tail_places") or list(rooms)[:8])
    # Featured residents must receive recent-resolution life where they
    # actually work and live; otherwise the arbitrary first eight rooms can
    # leave the featured person with only an aggregate shift counter.
    for item in generated["items"].values():
        for body in item["state"].get("bodies", {}).values():
            if not body.get("resident_seed_id"):
                continue
            tail_places.extend((body.get("place"), body.get("berth")))
    tail_places = list(dict.fromkeys(str(place) for place in tail_places if place))
    presimmed, events = presim_registry(
        generated, horizon_hours=horizon,
        active_tail_hours=float(request.get(
            "active_tail_hours", min(DEFAULT_PRESIM_TAIL_HOURS, horizon))),
        tail_places=tail_places,
        seed=int(request.get("seed") or 0))
    historian_error = ""
    if wants_history:
        try:
            actual = narrate_actual_history(town, presimmed, events)
            for key, item in presimmed["items"].items():
                local = dict(actual)
                local["residents"] = {
                    resident_id.split("/", 1)[1]: value
                    for resident_id, value in (actual.get("residents") or {}).items()
                    if resident_id.startswith(f"{key}/")}
                item["state"].setdefault("history", {})["actual"] = local
        except Exception as exc:  # history prose may fail; simulation stands
            historian_error = f"{type(exc).__name__}: {str(exc)[:240]}"
    landed_registry = copy.deepcopy(combined)
    landed_registry["items"].update(copy.deepcopy(presimmed["items"]))
    clock = wget_for_frame(
        cid, "simulation_clock", frame_id, {"elapsed_seconds": 0.0}) or {}
    latest = q("SELECT MAX(idx) idx FROM turns WHERE chat_id=?", (cid,), one=True)
    landed = land_presim(
        cid, frame_id, landed_registry, events,
        base_turn=int(latest["idx"] if latest and latest["idx"] is not None
                      else 0),
        expected_revision=source_revision,
        now_seconds=float(clock.get("elapsed_seconds") or 0.0))
    from world.charter_history import featured_resident_bindings
    resident_bindings = featured_resident_bindings(
        presimmed,
        [row.get("seed_id") for row in request.get("featured_residents") or ()
         if isinstance(row, dict)])
    result = {
        "ok": landed.get("reason") is None, "town": town["name"],
        "structure": structure, "rooms": len(rooms),
        "charters": list(presimmed["items"]), "presim": landed,
        "warnings": structure_warnings(structure, rooms),
        "historian_error": historian_error,
        "required_rooms_added": required_rooms_added,
        "source_lorebook_id": source_book,
        "source_lore_entry_ids": lore_manifest["entry_ids"],
        "featured_residents": resident_bindings,
    }
    _complete_cast_histories(
        cid, request, cast_histories, result, frame_id=frame_id)
    return result


def land_presim(cid, frame_id, registry, produced, *, base_turn=0,
                expected_revision=None, now_seconds=0.0):
    """Atomically land explicit presimulation with a revision race guard."""
    from core.db import qtx, transaction, wset_for_frame

    if expected_revision and registry_revision(registry_for(cid, frame_id)) \
            != expected_revision:
        return {"advanced": 0, "events": 0, "reason": "registry_changed"}
    rows = []
    horizon = max((float((item.get("state") or {}).get("clock_hours") or 0.0)
                   for item in (registry.get("items") or {}).values()),
                  default=0.0)
    for event in produced:
        charter_key = str(event.get("charter") or "charter")
        due_at = float(now_seconds) - max(
            0.0, horizon - float(event.get("at_hours") or 0.0)) * 3600.0
        rows.append(_scheduled_row(
            cid, frame_id, base_turn, "presim", charter_key, event, due_at))
    with transaction():
        if expected_revision and registry_revision(registry_for(cid, frame_id)) \
                != expected_revision:
            return {"advanced": 0, "events": 0,
                    "reason": "registry_changed"}
        wset_for_frame(cid, CHARTERS_KEY, normalize_registry(registry), frame_id)
        for row in rows:
            qtx(
                "INSERT OR IGNORE INTO scheduled_events"
                "(event_id,chat_id,due_at,kind,location_id,payload,seed,status) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (row["event_id"], row["chat_id"], row["due_at"], row["kind"],
                 row["location_id"], row["payload"], row["seed"], row["status"]),
            )
    return {"advanced": len(registry["items"]), "events": len(produced),
            "scheduled": len(rows)}


def registry_warnings(registry, scene=None, *, cid=None, frame_id=None):
    """Author-facing validation; warnings never silently rewrite a Charter."""
    registry = normalize_registry(registry)
    rooms = set((scene or {}).get("rooms") or {})
    warnings = []
    for key, item in registry["items"].items():
        state = item["state"]
        known_rooms = set(rooms)
        if cid is not None and state.get("structure"):
            try:
                from world.structure import skeleton_rooms
                known_rooms.update(skeleton_rooms(
                    cid, state["structure"], frame_id).get("rooms") or {})
            except Exception:
                pass
        from story.dialogue_colors import normalize_color
        from world.charter_identity import display_name
        if not state["upkeeps"]:
            warnings.append(f"{key}: no upkeeps; this institution has no goal")
        if not state["posts"]:
            warnings.append(f"{key}: no posts; no upkeep can be serviced")
        if not state["bodies"]:
            warnings.append(f"{key}: no bodies; every post will be unfilled")
        roles = {}
        for post, assigned in (state.get("watch") or {}).items():
            roles.setdefault(str(assigned), []).append(str(post))
        display_groups = {}
        for body_key, body in state["bodies"].items():
            display = display_name(
                body, roles.get(body_key) or (), state.get("naming"))
            display_groups.setdefault(display.casefold(), []).append(body_key)
            raw_color = str(body.get("dialogue_color") or "").strip()
            if raw_color and not normalize_color(raw_color):
                warnings.append(
                    f"{key}: body {body_key!r} has unreadable dialogue_color "
                    f"{raw_color!r}; expected #rgb or #rrggbb")
        for display, bodies in sorted(display_groups.items()):
            if display and len(bodies) > 1:
                warnings.append(
                    f"{key}: display name {display!r} belongs to multiple "
                    f"bodies {bodies}; scene presence is withheld until "
                    "the author distinguishes them")
        served = {upkeep for post in state["posts"].values()
                  for upkeep in post.get("serves") or ()}
        for upkeep in sorted(set(state["upkeeps"]) - served):
            warnings.append(f"{key}: upkeep {upkeep!r} is served by no post")
        for post_key, post in state["posts"].items():
            for upkeep in post.get("serves") or ():
                if upkeep not in state["upkeeps"]:
                    warnings.append(
                        f"{key}: post {post_key!r} serves unknown upkeep "
                        f"{upkeep!r}")
            superior = str(post.get("reports_to") or "")
            if superior and superior not in state["posts"]:
                warnings.append(
                    f"{key}: post {post_key!r} reports to unknown post "
                    f"{superior!r}")
            if superior == post_key:
                warnings.append(
                    f"{key}: post {post_key!r} cannot report to itself")
        if known_rooms:
            places = {
                str(entry.get("place") or "")
                for entry in list(state["upkeeps"].values())
                + list(state["posts"].values())
                + list(state["bodies"].values())
                if str(entry.get("place") or "")
            }
            for place in sorted(places - known_rooms):
                warnings.append(
                    f"{key}: place {place!r} is not a room in this frame")
    return warnings


def _event_subject(event):
    return str(event.get("upkeep") or event.get("post")
               or event.get("body") or event.get("actor")
               or event.get("by") or event.get("holder")
               or event.get("commitment_id") or event.get("order_id")
               or event.get("good") or "institution")


def _event_surface(event):
    subject = _event_subject(event)
    kind = str(event.get("kind") or "institution_event")
    phrases = {
        "upkeep_out_of_band": f"{subject} fell below its operating floor",
        "upkeep_restored": f"{subject} returned to its operating band",
        "body_unable": f"{subject} became unable to continue",
        "body_recovered": f"{subject} recovered enough to continue",
        "post_filled_again": f"{subject} was staffed again",
        "post_unfilled": f"{subject} could not be staffed",
        "post_believed_filled": f"{subject} was believed staffed but was not",
        "incident": str(event.get("surface") or
                        f"an incident changed {subject}"),
        "stock_low": f"{subject} ran low",
        "stock_empty": f"{subject} ran out",
        "stock_restored": f"{subject} was restocked",
        "stock_surplus": f"{subject} became abundant",
        "goods_exchanged": f"{subject} changed hands",
        "institution_order_issued": f"{subject} issued an order",
        "institution_order_executed": f"{subject} carried out an order",
        "institution_order_failed": f"an order concerning {subject} failed",
        "commitment_fulfilled": f"{subject} fulfilled an undertaking",
        "commitment_disputed": f"{subject} disputed an undertaking",
        "commitment_released": f"{subject} released an undertaking",
        "commitment_repudiated": f"{subject} repudiated an undertaking",
        "commitment_defaulted": f"{subject} defaulted on an undertaking",
        "commitment_transferred": f"{subject} transferred an undertaking",
        "report_confirmed": f"{subject} confirmed a report",
        "report_refuted": f"{subject} refuted a report",
        "aid_given": f"{subject} gave aid",
        "harm_done": f"{subject} caused harm",
    }
    return phrases.get(kind, f"{subject} changed state")


def _scheduled_row(cid, frame_id, base_turn, epoch_id, charter_key, event,
                   due_at):
    kind = str(event.get("kind") or "institution_event")
    subject = _event_subject(event)
    location = str(event.get("place") or "")
    event_id = stable_event_key(
        "charter", cid, frame_id, charter_key, kind, subject,
        event.get("at_hours"))
    public = _event_surface(event) if kind in WITNESSABLE else ""
    payload = {
        "frame_id": frame_id,
        "what": _event_surface(event),
        "where": location,
        "where_kind": "room",
        "witnessed": public,
        "origin": {"charter": charter_key, "epoch_id": epoch_id},
        "originator": "",
        "base_turn": int(base_turn),
        "disposition": "resolved_fact",
        "charter_event": copy.deepcopy(event),
    }
    return {
        "event_id": event_id, "chat_id": cid, "due_at": float(due_at),
        "kind": "consequence", "location_id": location,
        "payload": json.dumps(payload, ensure_ascii=False),
        "seed": f"charter:{charter_key}:{epoch_id}", "status": "pending",
    }


def advance_snapshot(registry, *, elapsed_seconds, epoch_id, base_turn,
                     cid, frame_id, scene=None, cancelled=None):
    """Advance a copied registry and compose stable scheduled-event rows."""
    registry = normalize_registry(copy.deepcopy(registry))
    rows, produced = [], []
    elapsed_seconds = max(0.0, float(elapsed_seconds or 0.0))
    advanced_any = False
    for index, (key, item) in enumerate(sorted(registry["items"].items())):
        if cancelled is not None and cancelled.is_set():
            break
        previous_elapsed = item.get("last_elapsed_seconds")
        if previous_elapsed is None:
            item["last_elapsed_seconds"] = elapsed_seconds
            item["last_epoch_id"] = str(epoch_id)
            continue
        delta_hours = max(0.0, (elapsed_seconds - previous_elapsed) / 3600.0)
        if delta_hours <= 0.0 or item.get("last_epoch_id") == str(epoch_id):
            continue
        advanced_hours = min(delta_hours, MAX_CATCHUP_HOURS)
        state = copy.deepcopy(item["state"])
        if isinstance(scene, dict) and scene.get("rooms"):
            # The live scene owns the room graph. Charter retains background
            # body positions but never carries a competing adjacency map.
            if state.get("structure"):
                from world.structure import composed_scene, skeleton_rooms
                state["scene"] = composed_scene(
                    skeleton_rooms(cid, state["structure"], frame_id), scene)
            else:
                state["scene"] = copy.deepcopy(scene)
            # Registered-character movement is authoritative.  A bound body
            # remains in Charter only as an institutional projection, and its
            # place follows the scene instead of being advanced here.
            try:
                from world.spatial import room_of
                for body_key, binding in (state.get("bindings") or {}).items():
                    room = (room_of(scene, binding.get("name"))
                            or room_of(scene, binding.get("entity_id")))
                    if room and body_key in state["bodies"]:
                        state["bodies"][body_key]["place"] = str(room)
            except Exception:
                pass
        before_hours = float(state.get("clock_hours") or 0.0)
        state, events = run(
            state, hours=advanced_hours,
            window=item["window_hours"],
            seed=int(stable_event_key(epoch_id, key)[-8:], 16),
        )
        item["state"] = state
        advanced_any = True
        item["last_elapsed_seconds"] = (
            previous_elapsed + advanced_hours * 3600.0)
        item["last_epoch_id"] = str(epoch_id)
        start_elapsed = previous_elapsed
        for event in events:
            offset_hours = max(
                0.0, float(event.get("at_hours") or before_hours)
                - before_hours)
            due_at = min(elapsed_seconds,
                         start_elapsed + offset_hours * 3600.0)
            stamped = {"charter": key, **copy.deepcopy(event)}
            produced.append(stamped)
            rows.append(_scheduled_row(
                cid, frame_id, base_turn, epoch_id, key, event, due_at))
    if advanced_any:
        cross_charter_gossip(registry)
    return registry, rows, produced


def cross_charter_gossip(registry, cap=CROSS_CHARTER_GOSSIP_CAP):
    """Let co-present bodies from different Charters trade one claim each.

    A Charter is an ownership boundary, not a soundproof wall.  This function
    chooses at most one representative per institution per occupied place,
    pairs actual co-present bodies, and uses the same ``hear_claim`` uptake
    door as internal Charter conversation.  Registers, needs, politics and
    non-news beliefs never cross.  Repeated windows rotate the representative,
    so a market spreads a story over time instead of teaching every head at
    once.
    """
    from world.charter_identity import display_name
    from world.charter_mind import cap_minds, hear_claim
    from world.charter_news import known_news, news_keys_in
    from world.charter_talk import RETOLD_RETENTION

    normalized = normalize_registry(registry)
    # The caller owns the snapshot that will be landed. Keep the helper's
    # mutation explicit rather than returning a second registry beside a
    # count and inviting one caller to forget which copy is authoritative.
    registry.clear()
    registry.update(normalized)
    try:
        cap = max(0, int(cap))
    except (TypeError, ValueError):
        cap = CROSS_CHARTER_GOSSIP_CAP
    by_place = {}
    for charter_key, item in sorted(registry["items"].items()):
        state = item["state"]
        roles = {}
        for post, body_key in (state.get("watch") or {}).items():
            roles.setdefault(str(body_key), []).append(str(post))
        placed = {}
        for body_key, body in sorted(state["bodies"].items()):
            if body_key in (state.get("bindings") or {}) \
                    or not body.get("available", True):
                continue
            place = str(body.get("place") or "")
            if place:
                placed.setdefault(place, []).append(body_key)
        for place, body_keys in placed.items():
            # Rotate on the institution's own clock. Sparse and deterministic:
            # a thousand people at one fair still create one mouth per Charter.
            turn = int(float(state.get("clock_hours") or 0.0))
            body_key = body_keys[turn % len(body_keys)]
            body = state["bodies"][body_key]
            by_place.setdefault(place, []).append({
                "charter": charter_key, "body": body_key,
                "name": display_name(
                    body, roles.get(body_key) or (), state.get("naming")),
            })

    told = 0
    for place in sorted(by_place):
        people = sorted(by_place[place], key=lambda row: (
            row["charter"], row["body"]))
        if len(people) < 2:
            continue
        pairs = []
        seen = set()
        for index, left in enumerate(people):
            right = people[(index + 1) % len(people)]
            if left["charter"] == right["charter"]:
                continue
            pair_key = tuple(sorted(((left["charter"], left["body"]),
                                     (right["charter"], right["body"]))))
            if pair_key in seen:
                continue
            seen.add(pair_key)
            pairs.append((left, right))
        for left, right in pairs:
            for speaker, listener in ((left, right), (right, left)):
                if told >= cap:
                    break
                source = registry["items"][speaker["charter"]]["state"]
                target = registry["items"][listener["charter"]]["state"]
                for claim in known_news(
                        source.get("minds") or {}, speaker["body"]):
                    if hear_claim(
                            target.setdefault("minds", {}), listener["body"],
                            claim, RETOLD_RETENTION, 1.0,
                            heard_from=speaker["name"]):
                        target["minds"] = cap_minds(target["minds"])
                        target["news_keys"] = sorted(
                            news_keys_in(target["minds"]))
                        told += 1
                        break
            if told >= cap:
                break
        if told >= cap:
            break
    return told


def land_snapshot(cid, frame_id, base_turn, epoch_id, registry, rows,
                  produced, *, expected_revision=None):
    """Atomically land state and consequences if the scheduling edge remains."""
    from core.db import (q, qtx, transaction, wget_for_frame,
                         wset_for_frame)

    with transaction():
        # All three checks run under the same write lock as landing. Reading
        # them before BEGIN leaves a gap where a turn commit, restore, or
        # author edit can invalidate the snapshot and then be overwritten.
        current_epoch = wget_for_frame(
            cid, "offscreen_epoch", frame_id, {}) or {}
        if str(current_epoch.get("epoch_id") or "") != str(epoch_id):
            logger.info("charter tick discarded: chat=%s epoch=%s changed",
                        cid, epoch_id)
            return {"advanced": 0, "events": 0,
                    "discarded": len(produced), "reason": "epoch_changed"}
        latest = q("SELECT MAX(idx) AS idx FROM turns WHERE chat_id=?", (cid,),
                   one=True)
        current_turn = (latest["idx"] if latest
                        and latest["idx"] is not None else None)
        if jobs.story_rewound_past(base_turn, current_turn):
            logger.info("charter tick discarded: chat=%s base_turn=%s rewound",
                        cid, base_turn)
            return {"advanced": 0, "events": 0,
                    "discarded": len(produced), "reason": "rolled_back"}
        if expected_revision:
            current_registry = registry_for(cid, frame_id)
            if registry_revision(current_registry) != expected_revision:
                logger.info(
                    "charter tick discarded: chat=%s registry changed", cid)
                return {"advanced": 0, "events": 0,
                        "discarded": len(produced),
                        "reason": "registry_changed"}
        wset_for_frame(cid, CHARTERS_KEY, registry, frame_id)
        for row in rows:
            qtx(
                "INSERT OR IGNORE INTO scheduled_events"
                "(event_id,chat_id,due_at,kind,location_id,payload,seed,status) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (row["event_id"], row["chat_id"], row["due_at"], row["kind"],
                 row["location_id"], row["payload"], row["seed"],
                 row["status"]),
            )
    return {"advanced": len(registry["items"]), "events": len(produced),
            "scheduled": len(rows)}


def schedule_charter_ticks(ctx, epoch=None):
    """Queue deterministic institution catch-up for one committed epoch."""
    from core.db import wget_for_frame
    from story.scene import dialogue_config, offscreen_life_allows

    epoch = epoch if isinstance(epoch, dict) else {}
    if not epoch.get("opportunity") or not epoch.get("epoch_id"):
        return None
    cfg = dialogue_config(ctx.chat.id) or {}
    if not offscreen_life_allows(cfg.get("offscreen_life"), "deterministic"):
        epoch["charter_skip"] = "ceiling"
        return None
    cid, frame_id, base_turn = ctx.chat.id, ctx.turn.frame_id, ctx.turn.idx
    registry = registry_for(cid, frame_id)
    if not registry["items"]:
        epoch["charter_skip"] = "no_charters"
        return None
    scene = wget_for_frame(cid, "scene", frame_id, {}) or {}
    epoch_id = str(epoch["epoch_id"])
    elapsed = float(epoch.get("elapsed_seconds") or 0.0)
    source_revision = registry_revision(registry)

    def _produce(job):
        advanced, rows, produced = advance_snapshot(
            registry, elapsed_seconds=elapsed, epoch_id=epoch_id,
            base_turn=base_turn, cid=cid, frame_id=frame_id, scene=scene,
            cancelled=job.cancelled)
        if job.cancelled.is_set():
            return {"advanced": 0, "events": 0, "cancelled": True}
        return land_snapshot(cid, frame_id, base_turn, epoch_id, advanced,
                             rows, produced,
                             expected_revision=source_revision)

    job = jobs.submit(cid, f"charter:{epoch_id}", _produce,
                      base_turn=base_turn)
    epoch["charter_scheduled"] = True
    epoch["charters"] = len(registry["items"])
    return job


def _place_views(registry, place):
    """Build room views from one immutable registry snapshot."""
    from world.charter import scene_ledger

    place = str(place or "")
    ledgers = []
    for key, item in sorted(registry["items"].items()):
        state = item["state"]
        occupied_places = {
            str(entry.get("place") or "")
            for collection in (state["upkeeps"], state["posts"],
                               state["bodies"])
            for entry in collection.values()
        }
        if place not in occupied_places:
            continue
        ledgers.append({"charter": key,
                        **scene_ledger(state, place, events=())})
    return ledgers[:3]


def place_view(cid, place, frame_id=None):
    """Capped objective/presence aperture for one currently encountered room."""
    return _place_views(registry_for(cid, frame_id), place)


def residue_facts(cid, place, frame_id=None, cap=3):
    """Present-state Charter facts suitable for the existing residue aperture."""
    facts = []
    registry = registry_for(cid, frame_id)
    for ledger in _place_views(registry, place):
        key = ledger["charter"]
        for upkeep, state in (ledger.get("place_state") or {}).items():
            if state.get("failing"):
                facts.append(
                    f"{upkeep} is currently below its operating floor "
                    f"within {key}.")
        charter_state = registry["items"][key]["state"]
        unfilled = ((charter_state.get("reported") or {})
                    .get("post_unfilled") or {})
        for post in ledger.get("posts_here") or ():
            if post in unfilled:
                facts.append(
                    f"The {post} duty remains unfilled ({unfilled[post]}).")
        for name, presence in (ledger.get("presences") or {}).items():
            if not presence.get("able"):
                facts.append(f"{name} is here but unable to continue working.")
        if len(facts) >= max(0, int(cap)):
            break
    return facts[:max(0, int(cap))]


def charter_diagnostics(cid, frame_id=None, *, charter_key="", body_key=""):
    """Author-only explanation surface; no result is delivered to a mind."""
    from core.db import q, wget_for_frame
    from world.charter_log import life_of, summarize

    registry = registry_for(cid, frame_id)
    events = []
    for row in q(
            "SELECT payload FROM scheduled_events WHERE chat_id=? "
            "AND seed LIKE 'charter:%' ORDER BY due_at DESC LIMIT 500", (cid,)):
        try:
            payload = json.loads(row["payload"] or "{}")
            event = payload.get("charter_event")
            if isinstance(event, dict):
                event = {"charter": str(
                    (payload.get("origin") or {}).get("charter") or ""),
                    **event}
        except (TypeError, ValueError, json.JSONDecodeError):
            event = None
        if isinstance(event, dict):
            events.append(event)
    resident_histories = wget_for_frame(
        cid, "charter_resident_histories", frame_id, {}) or {}
    items = {}
    for key, item in sorted(registry["items"].items()):
        if charter_key and key != str(charter_key):
            continue
        state = item["state"]
        local_events = [e for e in events
                        if not e.get("charter") or e.get("charter") == key]
        entry = {
            "summary": summarize(state, local_events),
            "warnings": registry_warnings(
                {"items": {key: item}}, scene=state.get("scene"),
                cid=cid, frame_id=frame_id),
            "judgment_holders": len(state.get("judgments") or {}),
            "commitments": list((state.get("commitments") or {}).values()),
            "economy": copy.deepcopy(state.get("economy") or {}),
            "decisions": copy.deepcopy(state.get("decisions") or {}),
            "history": copy.deepcopy(state.get("history") or {}),
            "refused_interventions": copy.deepcopy(
                state.get("refused_interventions") or []),
            "featured_resident_histories": {
                char_id: copy.deepcopy(history)
                for char_id, history in resident_histories.items()
                if isinstance(history, dict)
                and str((history.get("binding") or {}).get("charter") or "")
                == key
                and (not body_key or str(
                    (history.get("binding") or {}).get("body") or "")
                    == str(body_key))
            },
        }
        if body_key:
            entry["life"] = life_of(body_key, state, local_events)
            entry["believes"] = copy.deepcopy(
                (state.get("minds") or {}).get(str(body_key)) or {})
            entry["believed_by"] = {
                holder: copy.deepcopy(claims[str(body_key)])
                for holder, claims in (state.get("minds") or {}).items()
                if str(body_key) in claims}
            entry["judgments_by"] = copy.deepcopy(
                (state.get("judgments") or {}).get(str(body_key)) or {})
            entry["judgments_about"] = {
                holder: copy.deepcopy(subjects[str(body_key)])
                for holder, subjects in (state.get("judgments") or {}).items()
                if str(body_key) in subjects}
        items[key] = entry
    return {"items": items, "event_count": len(events)}


def carrier_entries(cid, frame_id=None):
    """Unpromoted Charter people shaped for ``story.carriers``.

    This is a projection, never a second knowledge store. Carrier modules may
    enumerate and copy these rows exactly as they do for full characters;
    ``save_carrier_state`` translates only newly acquired rows back into the
    owning body's sparse Charter mind.
    """
    from world.charter_identity import display_name, identity_aliases
    from world.charter_news import report_from_claim

    registry = registry_for(cid, frame_id)
    out = []
    for charter_key, item in sorted(registry["items"].items()):
        state = item["state"]
        roles = {}
        for post, body_key in (state.get("watch") or {}).items():
            roles.setdefault(str(body_key), []).append(str(post))
        for body_key, body in sorted(state["bodies"].items()):
            if body_key in (state.get("bindings") or {}):
                continue
            place = str(body.get("place") or "")
            reports = []
            for claim in (state.get("minds") or {}).get(body_key, {}).values():
                row = report_from_claim(claim, current_location=place)
                if row is not None:
                    reports.append(row)
            aliases = identity_aliases(
                body, roles.get(body_key) or (), state.get("naming"))
            shown = display_name(
                body, roles.get(body_key) or (), state.get("naming"))
            out.append({
                "row": None,
                "charter": True,
                "charter_ref": {"charter": charter_key, "body": body_key},
                "name": shown,
                "uid": body_key,
                "aliases": list(dict.fromkeys(
                    [str(body.get("name") or ""), body_key, *aliases])),
                "room": place,
                "state": {"carried_reports": reports},
            })
    return out


def save_carrier_state(cid, entry, carrier_state, frame_id=None):
    """Land rows newly earned through the shared physical carrier rail."""
    ref = (entry or {}).get("charter_ref") or {}
    charter_key = str(ref.get("charter") or "")
    body_key = str(ref.get("body") or "")
    if not charter_key or not body_key:
        return False
    registry = registry_for(cid, frame_id)
    item = registry["items"].get(charter_key)
    if item is None or body_key not in item["state"]["bodies"] \
            or body_key in (item["state"].get("bindings") or {}):
        return False
    from world.charter_mind import cap_minds
    from world.charter_news import FIRSTHAND_PROVENANCE, claim_from_report

    state = item["state"]
    held = state.setdefault("minds", {}).setdefault(body_key, {})
    changed = False
    at_hours = float(state.get("clock_hours") or 0.0)
    for report in (carrier_state or {}).get("carried_reports") or ():
        claim = claim_from_report(report, at_hours)
        if claim is None:
            continue
        current = held.get(claim["body"])
        if current is not None:
            current_firsthand = str(
                current.get("provenance") or "") in FIRSTHAND_PROVENANCE
            arriving_firsthand = str(
                claim.get("provenance") or "") in FIRSTHAND_PROVENANCE
            if current_firsthand or not arriving_firsthand \
                    and float(current.get("strength") or 0.0) >= float(
                        claim.get("strength") or 0.0):
                continue
        held[claim["body"]] = claim
        changed = True
    if not changed:
        return False
    state["minds"] = cap_minds(state.get("minds") or {})
    state["news_keys"] = sorted({
        subject for claims in state["minds"].values()
        for subject, claim in claims.items() if claim.get("kind") == "news"
    })
    item["state"] = state
    save_registry(cid, registry, frame_id)
    return True


def load_caravan_freight(cid, request, origin, *, frame_id=None):
    """Take requested lots from a real market holder into a caravan.

    The Director may ask for freight but cannot mint it. ``from_holder`` must
    own stock at a market in the origin room; the actual loaded amount is
    bounded by that stock. One registry read/write for the whole request.
    """
    request = request if isinstance(request, dict) else {}
    wanted = request.get("stock") if isinstance(request.get("stock"), dict) \
        else {}
    source = str(request.get("from_holder") or "")
    if not source or not wanted:
        return {"stock": {}, "wants": dict(request.get("wants") or {}),
                "from_holder": source}, []
    from world.charter_economy import normalize_economy, trade

    registry = registry_for(cid, frame_id)
    def amount(value):
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            return 0.0

    loaded, events = {}, []
    changed = False
    for item in registry["items"].values():
        state = item["state"]
        economy = normalize_economy(state.get("economy"))
        if not any(m["holder"] == source and m["place"] == str(origin)
                   for m in economy["markets"].values()):
            continue
        wagon = "__loading_caravan__"
        for good, quantity in wanted.items():
            economy, event, moved = trade(
                economy, seller=source, buyer=wagon, good=str(good),
                quantity=amount(quantity),
                at_hours=float(state.get("clock_hours") or 0.0),
                place=str(origin), reason="caravan_loading")
            if moved:
                loaded[str(good)] = loaded.get(str(good), 0.0) + moved
                events.append(event)
                changed = True
        economy["stocks"].pop(wagon, None)
        state["economy"] = economy
        item["state"] = state
        if loaded:
            break
    if changed:
        save_registry(cid, registry, frame_id)
    return {"stock": loaded,
            "wants": {str(k): amount(v) for k, v in
                      (request.get("wants") or {}).items()
                      if amount(v) > 0.0},
            "from_holder": source}, events


def exchange_caravan_freight(cid, freight, room, *, frame_id=None):
    """Exchange one wagon with authored markets at its physical stop."""
    from world.charter_economy import caravan_exchange

    registry = registry_for(cid, frame_id)
    changed = False
    events = []
    carried = copy.deepcopy(freight) if isinstance(freight, dict) else {}
    for item in registry["items"].values():
        state = item["state"]
        economy, carried_after, traded = caravan_exchange(
            state.get("economy"), carried, str(room),
            at_hours=float(state.get("clock_hours") or 0.0))
        if traded:
            from world.charter_news import news_keys_in, witness
            state["minds"], _witnessed = witness(
                state.get("minds") or {}, state.get("bodies") or {}, traded,
                float(state.get("clock_hours") or 0.0))
            state["news_keys"] = sorted(news_keys_in(state["minds"]))
            state["economy"] = economy
            item["state"] = state
            carried = carried_after
            events.extend(traded)
            changed = True
    if changed:
        save_registry(cid, registry, frame_id)
    return carried, events


def ingest_public_evidence(cid, evidence_rows, scene, *, turn_id,
                           frame_id=None):
    """Deliver one resolved beat to the Charter bodies that sensed it.

    One registry read and one conditional write regardless of population or
    witness count.  The expensive/semantic work was already shared at resolve;
    this side is deterministic perception plus sparse claim insertion.
    """
    from world.charter_observe import apply_public_evidence

    rows = [row for row in (evidence_rows or ()) if isinstance(row, dict)]
    if not rows:
        return {"sources": 0, "opportunities": 0, "acquired": 0}
    registry = registry_for(cid, frame_id)
    opportunities = acquired = 0
    for item in registry["items"].values():
        state, metrics = apply_public_evidence(
            item["state"], rows, scene or {}, turn_id)
        item["state"] = state
        opportunities += int(metrics.get("opportunities") or 0)
        acquired += int(metrics.get("acquired") or 0)
    if acquired:
        save_registry(cid, registry, frame_id)
    return {"sources": len(rows), "opportunities": opportunities,
            "acquired": acquired}


def presence_view(cid, place, name, frame_id=None, figures=None):
    """Only what one Charter body earned, never its institution's register."""
    out = []
    registry = registry_for(cid, frame_id)
    for charter_key, body_key in _body_refs(registry, name=name):
        item = registry["items"][charter_key]
        state = copy.deepcopy(item["state"])
        body = state["bodies"].get(body_key) or {}
        if str(body.get("place") or "") != str(place or ""):
            continue
        # Scene-owned people are figures here: visible subjects with no mind
        # for Charter to read or simulate.  They exist only in this aperture;
        # a landed act may leave a claim about the encounter, but no copied
        # character mind survives the call.
        for figure in figures or ():
            figure = str(figure or "").strip()
            if figure and figure not in state["bodies"]:
                state.setdefault("figures", {})[figure] = {
                    "key": figure, "place": str(place or ""),
                    "surface": {"label": figure},
                }
        from world.charter import (action_instances, opportunities,
                                   scene_ledger)
        focused = {body_key: body}
        opened = opportunities(
            focused, state.get("minds") or {}, state.get("needs") or {},
            events=(), practices=state.get("practices") or {},
            at_hours=float(state.get("clock_hours") or 0.0),
            figures={key: value for key, value in state["figures"].items()
                     if str(value.get("place") or "") == str(place or "")})
        state.setdefault("practices", {}).update(opened)
        presence = (scene_ledger(state, place, events=())
                    .get("presences", {}).get(body_key))
        if presence is None:
            continue
        out.append({
            "charter": charter_key,
            "body": body_key,
            "presence": copy.deepcopy(presence),
            # Exact typed options.  The model may echo one; prose can never
            # smuggle a Charter mutation through this seam.
            "action_instances": copy.deepcopy(
                (action_instances(state, actor=body_key).get(body_key) or [])[:6]),
        })
    return out[:2]


def _body_refs(registry, *, name=None, refs=None, include_bound=False):
    """Resolve an external presence to Charter body ids, without guessing."""
    wanted = str(name or "").strip().casefold()
    exact = set()
    for ref in refs or ():
        if isinstance(ref, dict) and ref.get("charter") and ref.get("body"):
            exact.add((str(ref["charter"]), str(ref["body"])))
    found = []
    for charter_key, item in sorted(registry["items"].items()):
        state = item["state"]
        from world.charter_identity import display_name
        roles = {}
        for post, assigned in (state.get("watch") or {}).items():
            roles.setdefault(str(assigned), []).append(str(post))
        for body_key, body in sorted(state["bodies"].items()):
            if body_key in (state.get("bindings") or {}) and not include_bound:
                continue
            if exact:
                matches = (charter_key, body_key) in exact
            else:
                matches = bool(wanted) and wanted in {
                    str(body_key).casefold(),
                    str(body.get("name") or "").strip().casefold(),
                    display_name(body, roles.get(body_key) or (),
                                 state.get("naming")).casefold(),
                }
            if matches:
                found.append((charter_key, body_key))
    return found


def background_presence_records(cid, *, places=None, names=None,
                                frame_id=None):
    """Unpromoted Charter bodies as ordinary background-presence records.

    Records are derived apertures, not a second identity store.  Ambiguous
    display names are withheld until the fiction distinguishes them.
    """
    registry = registry_for(cid, frame_id)
    place_set = {str(p) for p in (places or ()) if str(p or "")}
    name_set = {str(n).strip().casefold() for n in (names or ())
                if str(n or "").strip()}
    candidates = []
    counts = {}
    for charter_key, item in sorted(registry["items"].items()):
        state = item["state"]
        from world.charter_identity import display_name
        roles = {}
        for post, body_key in (state.get("watch") or {}).items():
            roles.setdefault(str(body_key), []).append(str(post))
        for body_key, body in sorted(state["bodies"].items()):
            if body_key in (state.get("bindings") or {}):
                continue
            display = display_name(
                body, roles.get(body_key) or (), state.get("naming"))
            place = str(body.get("place") or "")
            if place_set and place not in place_set:
                continue
            if name_set and display.casefold() not in name_set \
                    and body_key.casefold() not in name_set:
                continue
            counts[display.casefold()] = counts.get(display.casefold(), 0) + 1
            candidates.append((charter_key, body_key, display, place,
                               roles.get(body_key) or []))
    out = {}
    for charter_key, body_key, display, place, roles in candidates:
        if counts.get(display.casefold(), 0) != 1:
            continue
        role = (", ".join(roles) if roles else f"member of {charter_key}")
        out[display] = {
            "dialogue_turns": [], "mention_turns": [],
            "addressed_turns": [], "nature": "person",
            "charter_refs": [{"charter": charter_key, "body": body_key}],
            "sketch": {"role_hint": role, "station_room": place},
        }
    return out


def charter_speaker_records(cid, frame_id=None, *, include_bound=False):
    """All stable Charter speaker identities for render-time colour lookup.

    This is deliberately a flat O(bodies) projection.  It performs no model
    calls and stores no duplicate palette.  A thousand bodies are cheap; the
    transcript still colours only exact quotes that were actually spoken.
    """
    from world.charter_identity import (
        display_name, identity_aliases, identity_seed)

    registry = registry_for(cid, frame_id)
    out = []
    for charter_key, item in sorted(registry["items"].items()):
        state = item["state"]
        roles = {}
        for post, assigned in (state.get("watch") or {}).items():
            roles.setdefault(str(assigned), []).append(str(post))
        for body_key, body in sorted(state["bodies"].items()):
            if body_key in (state.get("bindings") or {}) and not include_bound:
                continue
            name = display_name(
                body, roles.get(body_key) or (), state.get("naming"))
            if not name:
                continue
            out.append({
                "name": name,
                "aliases": identity_aliases(
                    body, roles.get(body_key) or (), state.get("naming")),
                "charter": charter_key,
                "body": body_key,
                "seed": identity_seed(charter_key, body_key),
                "color": str(body.get("dialogue_color") or ""),
                "place": str(body.get("place") or ""),
            })
    return out


def apply_presence_conduct(cid, name, conduct, *, record=None, frame_id=None,
                           allowed=None, place=""):
    """Land one exact background-authored Charter act, or refuse it."""
    conduct = conduct if isinstance(conduct, dict) else {}
    act, other = str(conduct.get("act") or ""), str(conduct.get("other") or "")
    if not act or not other:
        return None
    permitted = {(str(row.get("act") or ""), str(row.get("other") or ""))
                 for row in (allowed or ()) if isinstance(row, dict)}
    if (act, other) not in permitted:
        return {"actor": str(name), "act": act, "other": other,
                "refused": "not_offered_to_scene_life"}
    registry = registry_for(cid, frame_id)
    refs = (record or {}).get("charter_refs") or ()
    matches = _body_refs(registry, name=name, refs=refs)
    if len(matches) != 1:
        return {"actor": str(name), "act": act, "other": other,
                "refused": "ambiguous_charter_identity"}
    charter_key, body_key = matches[0]
    from world.charter import authored
    original = registry["items"][charter_key]["state"]
    state = copy.deepcopy(original)
    temporary_figure = other not in state["bodies"]
    if temporary_figure:
        state.setdefault("figures", {})[other] = {
            "key": other, "place": str(place or ""),
            "surface": {"label": other},
        }
    state, result = authored(state, body_key, act, other)
    if temporary_figure:
        state.setdefault("figures", {}).pop(other, None)
    registry["items"][charter_key]["state"] = state
    save_registry(cid, registry, frame_id)
    return {"charter": charter_key, "body": body_key, **result}


def _charter_events(cid, charter_key, frame_id=None):
    """Fired objective Charter events only; never a private runtime cache."""
    from core.db import q
    if frame_id is None:
        rows = q("SELECT payload FROM world_events WHERE chat_id=? "
                 "AND frame_id IS NULL ORDER BY occurred_at", (cid,))
    else:
        rows = q("SELECT payload FROM world_events WHERE chat_id=? "
                 "AND frame_id=? ORDER BY occurred_at", (cid, frame_id))
    out = []
    for row in rows:
        try:
            payload = json.loads(row["payload"] or "{}")
        except (TypeError, json.JSONDecodeError):
            continue
        origin = payload.get("origin") or {}
        event = payload.get("charter_event")
        if str(origin.get("charter") or "") == str(charter_key) \
                and isinstance(event, dict):
            out.append(event)
    return out


def promotion_bundle(cid, name, *, record=None, frame_id=None):
    """The one Charter life this tracked presence can legitimately carry."""
    registry = registry_for(cid, frame_id)
    refs = (record or {}).get("charter_refs") or ()
    matches = _body_refs(registry, name=name, refs=refs)
    if len(matches) != 1:
        return None
    charter_key, body_key = matches[0]
    from world.charter import promotion_handoff
    handoff = promotion_handoff(
        body_key, registry["items"][charter_key]["state"],
        events=_charter_events(cid, charter_key, frame_id))
    body = registry["items"][charter_key]["state"]["bodies"][body_key]
    state = registry["items"][charter_key]["state"]
    from world.charter_identity import display_name
    roles = {}
    for post, assigned in (state.get("watch") or {}).items():
        roles.setdefault(str(assigned), []).append(str(post))
    social_names = {
        key: display_name(value, roles.get(key) or (), state.get("naming"))
        for key, value in state["bodies"].items()}
    for key, figure in (state.get("figures") or {}).items():
        surface = figure.get("surface") or {}
        social_names[key] = str(surface.get("name") or surface.get("label")
                                or key)
    from world.charter_identity import identity_seed
    return {"charter": charter_key, "body": body_key,
            "place": str(body.get("place") or ""), "handoff": handoff,
            "social_names": social_names,
            "dialogue_color": str(body.get("dialogue_color") or ""),
            "dialogue_color_seed": identity_seed(charter_key, body_key)}


def bind_promoted_character(cid, bundle, *, char_id, name, entity_id="",
                            promoted_turn=None, place="", frame_id=None):
    """Retire Charter cognition while retaining the institutional projection."""
    if not isinstance(bundle, dict):
        return False
    charter_key, body_key = bundle.get("charter"), bundle.get("body")
    registry = registry_for(cid, frame_id)
    item = registry["items"].get(str(charter_key))
    if item is None or str(body_key) not in item["state"]["bodies"]:
        return False
    state = item["state"]
    body_key = str(body_key)
    state.setdefault("bindings", {})[body_key] = {
        "char_id": int(char_id), "entity_id": str(entity_id or ""),
        "name": str(name), "promoted_turn": promoted_turn,
    }
    state["bodies"][body_key]["name"] = str(name)
    if place:
        state["bodies"][body_key]["place"] = str(place)
    for store in ("minds", "needs", "feel", "heard_blame"):
        (state.get(store) or {}).pop(body_key, None)
    for store in ("experiences", "habit_runs"):
        (state.get(store) or {}).pop(body_key, None)
    state["bodies"][body_key].pop("private_habits", None)
    (state.get("judgments") or {}).pop(body_key, None)
    state["practices"] = {
        key: practice for key, practice in (state.get("practices") or {}).items()
        if body_key not in set((practice.get("roles") or {}).values())
    }
    item["state"] = normalize_charter(state)
    save_registry(cid, registry, frame_id)
    return True
