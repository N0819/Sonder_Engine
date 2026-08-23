"""Planned location structure composed with the small live scene.

Planned rooms live in ``room_registry.payload`` and remain prose-free.  The
live scene receives only adjacent stubs; entering one lets the ordinary mapping
stage write description and contents without hauling a whole town through
every story prompt.
"""

from __future__ import annotations

import copy
import hashlib
import json
import random

from world.charter_model import integer as _integer
from world.spatial import normalize_room_id


STRUCTURES_KEY = "structures"
STRUCTURE_VERSION = 1


def normalize_structure(stored):
    stored = stored if isinstance(stored, dict) else {}
    grammar = []
    for raw in stored.get("grammar") or ():
        if not isinstance(raw, dict):
            continue
        grammar.append({
            "kind": str(raw.get("kind") or "place"),
            "names": [str(x) for x in raw.get("names") or () if str(x)],
            "purposes": [str(x) for x in raw.get("purposes") or () if str(x)],
        })
    return {
        "version": STRUCTURE_VERSION,
        "key": str(stored.get("key") or "structure"),
        "name": str(stored.get("name") or stored.get("key") or "Location"),
        "charters": sorted({str(x) for x in stored.get("charters") or ()
                            if str(x)}),
        "max_planned": max(1, min(
            1000, _integer(stored.get("max_planned"), 200))),
        "grammar": grammar,
        "revision": max(0, _integer(stored.get("revision"))),
    }


def normalize_structures(stored):
    stored = stored if isinstance(stored, dict) else {}
    items = stored.get("items") if isinstance(stored.get("items"), dict) \
        else stored
    return {"version": STRUCTURE_VERSION, "items": {
        str(key): normalize_structure(dict(value or {}, key=key))
        for key, value in items.items() if isinstance(value, dict)
        and key != "version"}}


def _payload(row):
    try:
        return json.loads(row["payload"] or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def skeleton_rooms(cid, structure_key, frame_id=None):
    """Read one planned skeleton in ordinary spatial scene shape."""
    from core.db import q

    rooms = {}
    for row in q(
            "SELECT room_uid,name,payload FROM room_registry "
            "WHERE chat_id=? AND retired_turn_id IS NULL", (cid,)):
        payload = _payload(row)
        planned = payload.get("planned") if isinstance(payload, dict) else None
        if not isinstance(planned, dict) \
                or str(planned.get("structure") or "") != str(structure_key):
            continue
        rooms[str(row["room_uid"])] = {
            "name": str(row["name"] or row["room_uid"]),
            "adjacent": [dict(edge) for edge in planned.get("adjacent") or ()
                         if isinstance(edge, dict) and edge.get("to")],
            "planned": True,
            "purpose": str(planned.get("purpose") or ""),
            "access": str(planned.get("access") or ""),
        }
    return {"rooms": rooms}


def composed_scene(skeleton, live_scene):
    """Merge planned travel topology under live authored room definitions."""
    live = copy.deepcopy(live_scene or {})
    planned_rooms = copy.deepcopy((skeleton or {}).get("rooms") or {})
    live_rooms = live.get("rooms") or {}
    merged = planned_rooms
    for uid, room in live_rooms.items():
        if not isinstance(room, dict):
            merged[str(uid)] = room
            continue
        base = dict(merged.get(str(uid)) or {})
        base.update(copy.deepcopy(room))
        # Live edges win per endpoint; planned edges retain destinations the
        # currently materialized scene has not had reason to spell yet.
        edges = {}
        for edge in (planned_rooms.get(str(uid)) or {}).get("adjacent") or ():
            if isinstance(edge, dict) and edge.get("to"):
                edges[str(edge["to"])] = dict(edge)
        for edge in room.get("adjacent") or ():
            if isinstance(edge, dict) and edge.get("to"):
                edges[str(edge["to"])] = dict(edge)
        if edges:
            base["adjacent"] = list(edges.values())
        merged[str(uid)] = base
    live["rooms"] = merged
    return live


def mint_frontier(structure, from_uid, axis, seed, existing=()):
    """Deterministically turn one structure-side frontier label into a room."""
    structure = normalize_structure(structure)
    material = "|".join((structure["key"], str(from_uid), str(axis), str(seed)))
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    rng = random.Random(int(digest[:16], 16))
    grammar = structure["grammar"] or [{
        "kind": "place", "names": [str(axis).replace("_", " ").title()],
        "purposes": [str(axis).replace("_", " ")]}]
    rule = grammar[rng.randrange(len(grammar))]
    names = rule["names"] or [str(axis).replace("_", " ").title()]
    purposes = rule["purposes"] or [rule["kind"]]
    name = names[rng.randrange(len(names))]
    base = normalize_room_id(name) or "planned_room"
    uid, suffix = base, 2
    taken = {str(x) for x in existing}
    while uid in taken:
        uid, suffix = f"{base}_{suffix}", suffix + 1
    return uid, {
        "name": name, "purpose": purposes[rng.randrange(len(purposes))],
        "structure": structure["key"], "access": "",
        "adjacent": [{"to": str(from_uid), "barrier": "open_door"}],
        "frontier": [],
    }


def plant_structure(cid, structure, rooms, *, owning_book_id=None,
                    created_turn_id=None):
    """Persist a prose-free planned skeleton and its structure grammar."""
    from core.db import qi, transaction, wget_for_frame, wset_for_frame

    structure = normalize_structure(structure)
    normalized = {}
    for uid, raw in (rooms or {}).items():
        if not isinstance(raw, dict):
            continue
        normalized[str(uid)] = {
            "name": str(raw.get("name") or uid),
            "purpose": str(raw.get("purpose") or ""),
            "structure": structure["key"],
            "access": str(raw.get("access") or ""),
            "adjacent": [dict(edge) for edge in raw.get("adjacent") or ()
                         if isinstance(edge, dict) and edge.get("to")],
            "frontier": [str(x) for x in raw.get("frontier") or () if str(x)],
        }
    if len(normalized) > structure["max_planned"]:
        raise ValueError("planned rooms exceed structure.max_planned")
    with transaction():
        for uid, planned in normalized.items():
            payload = json.dumps({"planned": planned}, ensure_ascii=False)
            qi(
                "INSERT INTO room_registry"
                "(chat_id,room_uid,owning_book_id,parent_entity,name,aliases,"
                "payload,created_turn_id,retired_turn_id) VALUES(?,?,?,?,?,?,?,?,NULL) "
                "ON CONFLICT(chat_id,room_uid) DO UPDATE SET "
                "name=excluded.name,payload=excluded.payload,retired_turn_id=NULL",
                (cid, uid, owning_book_id, None, planned["name"],
                 json.dumps([planned["name"], uid.replace("_", " ")]),
                 payload, created_turn_id),
            )
        stored = normalize_structures(
            wget_for_frame(cid, STRUCTURES_KEY, None, {}) or {})
        stored["items"][structure["key"]] = structure
        wset_for_frame(cid, STRUCTURES_KEY, stored, None)
    return structure, normalized


def materialize_planned_fringe(cid, scene):
    """Add planned neighbours of occupied rooms as small live-scene stubs."""
    from core.db import q

    scene = scene if isinstance(scene, dict) else {}
    rooms = scene.setdefault("rooms", {})
    occupied = {str(room) for room in (scene.get("positions") or {}).values()
                if str(room)}
    if not occupied:
        return scene, 0
    planned = {}
    for row in q(
            "SELECT room_uid,name,payload FROM room_registry "
            "WHERE chat_id=? AND retired_turn_id IS NULL", (cid,)):
        payload = _payload(row)
        spec = payload.get("planned") if isinstance(payload, dict) else None
        if isinstance(spec, dict):
            planned[str(row["room_uid"])] = (str(row["name"] or
                                                    row["room_uid"]), spec)
    added = 0
    targets = set()
    for uid in occupied:
        spec = (planned.get(uid) or (None, {}))[1]
        planned_edges = [dict(e) for e in spec.get("adjacent") or ()
                         if isinstance(e, dict) and e.get("to")]
        targets.update(str(e.get("to")) for e in planned_edges)
        if uid in rooms and planned_edges:
            # The occupied live definition owns prose/physics it declared;
            # structure supplies only exits that live mapping has not named.
            edges = {str(e.get("to")): dict(e)
                     for e in (rooms[uid].get("adjacent") or ())
                     if isinstance(e, dict) and e.get("to")}
            for edge in planned_edges:
                edges.setdefault(str(edge["to"]), edge)
            rooms[uid]["adjacent"] = list(edges.values())
    for uid in sorted(targets):
        if uid in rooms or uid not in planned:
            continue
        name, spec = planned[uid]
        rooms[uid] = {
            "name": name, "adjacent": [dict(e) for e in spec.get("adjacent") or ()],
            "planned": True, "purpose": str(spec.get("purpose") or ""),
        }
        added += 1
    return scene, added


def planned_context(cid, query):
    """Short structural context for mapping a specifically requested room."""
    from core.db import q

    folded = normalize_room_id(str(query or ""))
    if not folded:
        return None
    rows = []
    all_rows = q(
        "SELECT room_uid,name,payload FROM room_registry "
        "WHERE chat_id=? AND retired_turn_id IS NULL", (cid,))
    names = {str(row["room_uid"]): str(row["name"] or row["room_uid"])
             for row in all_rows}
    for row in all_rows:
        payload = _payload(row)
        spec = payload.get("planned") if isinstance(payload, dict) else None
        if not isinstance(spec, dict):
            continue
        uid, name = str(row["room_uid"]), str(row["name"] or row["room_uid"])
        uid_key, name_key = normalize_room_id(uid), normalize_room_id(name)
        if folded not in {uid_key, name_key} \
                and name_key not in folded and uid_key not in folded:
            continue
        rows.append({
            "room_uid": uid, "name": name,
            "purpose": str(spec.get("purpose") or ""),
            "structure": str(spec.get("structure") or ""),
            "access": str(spec.get("access") or ""),
            "adjacent": [names.get(str(edge.get("to")), str(edge.get("to")))
                         for edge in spec.get("adjacent") or ()
                         if isinstance(edge, dict) and edge.get("to")],
        })
    return rows[0] if len(rows) == 1 else None


def prepare_frontier_expansion(cid, scene):
    """Mint approached frontier nodes without writing during commit prepare.

    Returns ``(scene, mutations)``. The caller writes mutations inside the
    same transaction as the scene, so a frontier can never point at a room
    whose planned identity failed to land.
    """
    from core.db import q, wget_for_frame

    scene = scene if isinstance(scene, dict) else {}
    occupied = {str(room) for room in (scene.get("positions") or {}).values()
                if str(room)}
    if not occupied:
        return scene, []
    rows = q(
        "SELECT room_uid,owning_book_id,parent_entity,name,aliases,payload "
        "FROM room_registry WHERE chat_id=? AND retired_turn_id IS NULL", (cid,))
    by_uid = {str(row["room_uid"]): row for row in rows}
    specs = {}
    counts = {}
    for uid, row in by_uid.items():
        payload = _payload(row)
        spec = payload.get("planned") if isinstance(payload, dict) else None
        if isinstance(spec, dict):
            specs[uid] = (payload, dict(spec))
            skey = str(spec.get("structure") or "")
            counts[skey] = counts.get(skey, 0) + 1
    structures = normalize_structures(
        wget_for_frame(cid, STRUCTURES_KEY, None, {}) or {})["items"]
    mutations = []
    existing = set(by_uid)
    rooms = scene.setdefault("rooms", {})
    for uid in sorted(occupied):
        if uid not in specs:
            continue
        payload, spec = specs[uid]
        structure_key = str(spec.get("structure") or "")
        structure = structures.get(structure_key) or {
            "key": structure_key, "max_planned": 200, "grammar": []}
        frontiers = [str(x) for x in spec.get("frontier") or () if str(x)]
        retained = []
        for axis in frontiers:
            if counts.get(structure_key, 0) >= normalize_structure(
                    structure)["max_planned"]:
                retained.append(axis)
                continue
            new_uid, new_spec = mint_frontier(
                structure, uid, axis, f"{cid}:{structure_key}", existing)
            existing.add(new_uid)
            counts[structure_key] = counts.get(structure_key, 0) + 1
            edge = {"to": new_uid, "barrier": "open_door",
                    "axis": axis}
            spec.setdefault("adjacent", []).append(edge)
            rooms.setdefault(uid, {"name": str(by_uid[uid]["name"] or uid),
                                   "adjacent": []})
            rooms[uid].setdefault("adjacent", []).append(dict(edge))
            rooms[new_uid] = {
                "name": new_spec["name"], "planned": True,
                "purpose": new_spec["purpose"],
                "adjacent": [dict(e) for e in new_spec["adjacent"]],
            }
            new_payload = {"planned": new_spec}
            mutations.append({
                "room_uid": new_uid,
                "owning_book_id": by_uid[uid]["owning_book_id"],
                "parent_entity": by_uid[uid]["parent_entity"],
                "name": new_spec["name"],
                "aliases": [new_spec["name"], new_uid.replace("_", " ")],
                "payload": new_payload,
            })
        if frontiers:
            spec["frontier"] = retained
            payload = dict(payload, planned=spec)
            mutations.append({
                "room_uid": uid,
                "owning_book_id": by_uid[uid]["owning_book_id"],
                "parent_entity": by_uid[uid]["parent_entity"],
                "name": str(by_uid[uid]["name"] or uid),
                "aliases": json.loads(by_uid[uid]["aliases"] or "[]"),
                "payload": payload,
            })
    return scene, mutations


def apply_frontier_mutations(cid, turn_id, mutations):
    """Write prepared frontier rows; call only inside the scene transaction."""
    from core.db import qtx

    for row in mutations or ():
        qtx(
            "INSERT INTO room_registry"
            "(chat_id,room_uid,owning_book_id,parent_entity,name,aliases,payload,"
            "created_turn_id,retired_turn_id) VALUES(?,?,?,?,?,?,?,?,NULL) "
            "ON CONFLICT(chat_id,room_uid) DO UPDATE SET "
            "owning_book_id=excluded.owning_book_id,"
            "parent_entity=excluded.parent_entity,name=excluded.name,"
            "aliases=excluded.aliases,payload=excluded.payload,retired_turn_id=NULL",
            (cid, row["room_uid"], row.get("owning_book_id"),
             row.get("parent_entity"), row["name"],
             json.dumps(row.get("aliases") or []),
             json.dumps(row.get("payload") or {}, ensure_ascii=False), turn_id),
        )


def structure_warnings(structure, rooms):
    structure = normalize_structure(structure)
    rooms = rooms if isinstance(rooms, dict) else {}
    warnings = []
    if not rooms:
        return [f"{structure['key']}: structure has no planned rooms"]
    for uid, room in rooms.items():
        if str(room.get("desc") or room.get("description") or "").strip():
            warnings.append(f"{uid}: planned room contains prose")
        destinations = [str(e.get("to")) for e in room.get("adjacent") or ()
                        if isinstance(e, dict) and e.get("to")]
        for target in destinations:
            if target not in rooms:
                warnings.append(f"{uid}: planned edge targets unknown room {target}")
        if set(destinations) & set(str(x) for x in room.get("frontier") or ()):
            warnings.append(f"{uid}: frontier label collides with a real edge")
    # Undirected reach is sufficient for author diagnostics; runtime pathing
    # will still enforce each authored barrier direction.
    start, seen = next(iter(rooms)), set()
    stack = [start]
    reverse = {}
    for uid, room in rooms.items():
        for edge in room.get("adjacent") or ():
            if isinstance(edge, dict) and edge.get("to") in rooms:
                reverse.setdefault(str(edge["to"]), set()).add(str(uid))
    while stack:
        uid = stack.pop()
        if uid in seen:
            continue
        seen.add(uid)
        room = rooms.get(uid) or {}
        stack.extend(str(e.get("to")) for e in room.get("adjacent") or ()
                     if isinstance(e, dict) and e.get("to") in rooms)
        stack.extend(reverse.get(uid, ()))
    if len(seen) != len(rooms):
        warnings.append(f"{structure['key']}: planned skeleton is disconnected")
    return warnings


__all__ = [
    "STRUCTURES_KEY", "apply_frontier_mutations", "composed_scene",
    "materialize_planned_fringe", "prepare_frontier_expansion",
    "mint_frontier", "normalize_structure", "normalize_structures",
    "planned_context",
    "plant_structure", "skeleton_rooms", "structure_warnings",
]
