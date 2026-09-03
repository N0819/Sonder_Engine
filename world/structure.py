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
import re

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


def _axis_words(text):
    return set(re.findall(r"[^\W\d_]+", str(text or "").casefold()))


def _proper(name):
    """A room name is a proper noun. A grammar name or an axis label a
    planner wrote in lower case ("upland road") takes a capital at the front
    of each word; a name with a capital anywhere keeps its author's spelling
    ("Saint Orrin's Shrine", "McKay's Yard")."""
    text = " ".join(str(name or "").split())
    if not text or any(ch.isupper() for ch in text):
        return text
    return " ".join(part[:1].upper() + part[1:] for part in text.split(" "))


def mint_frontier(structure, from_uid, axis, seed, existing=()):
    """Deterministically turn one structure-side frontier label into a room.

    A FRONTIER STUB IS NAMED FOR THE DIRECTION IT LEAVES IN, never for a room
    the plan already has. The grammar's rule is chosen by its affinity with
    the axis (the words the axis shares with the rule's kind, names and
    purposes), so the "upland road" axis draws on the road rule and not the
    residential one; and a grammar name that is already a room -- the
    planner wrote its planned rooms into the grammar's name pool -- is
    RESERVED and never a stub's name. When every name in the rule is
    reserved, the axis label is the name: it is what the planner said leaves
    here. Measured on the Harrowmere replay (2026-09-03): the axis "upland
    road" off the gate minted "bridge road" (`bridge_road_2`, purpose
    "crossing") beside the real Bridge Road, and the Director, shown a stub
    called "bridge road" north of the gate, minted `upland_road` beside it;
    `slate_lane_2`, `market_square_2` and `_3` were the same class, and
    those were every duplicate room of the run.
    """
    structure = normalize_structure(structure)
    material = "|".join((structure["key"], str(from_uid), str(axis), str(seed)))
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    rng = random.Random(int(digest[:16], 16))
    axis_label = str(axis).replace("_", " ")
    grammar = structure["grammar"] or [{
        "kind": "place", "names": [axis_label], "purposes": [axis_label]}]
    words = _axis_words(axis_label)

    def affinity(rule):
        pool = _axis_words(rule.get("kind"))
        for text in list(rule.get("names") or ()) + list(rule.get("purposes") or ()):
            pool |= _axis_words(text)
        return len(words & pool)

    best = max(affinity(rule) for rule in grammar)
    rules = [rule for rule in grammar if affinity(rule) == best] if best \
        else list(grammar)
    rule = rules[rng.randrange(len(rules))]
    taken = {str(x) for x in existing}
    # A grammar name is the stub's only when the axis asked for it by a
    # word of its own -- "north" draws "North Lane"; "upland road" draws
    # "upland road" -- and never by the rule's kind word alone, or the "far
    # road" axis would draw the road rule's "upland road" and be one more
    # stub named for a place it is not. Otherwise the axis label is the
    # name, and the Director names the room properly when it furnishes it.
    kind_words = _axis_words(rule.get("kind"))
    names = [name for name in (rule["names"] or ())
             if normalize_room_id(name) not in taken
             and (_axis_words(name) & words) - kind_words]
    purposes = rule["purposes"] or [rule["kind"]]
    name = _proper(names[rng.randrange(len(names))] if names else axis_label)
    base = normalize_room_id(name) or "planned_room"
    uid, suffix = base, 2
    while uid in taken:
        uid, suffix = f"{base}_{suffix}", suffix + 1
    if uid != base:
        # A second segment of the same axis is the same name with an
        # ordinal, so the Director never sees two rooms spelled alike.
        name = f"{name} {suffix - 1}"
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


def _planned_specs(cid):
    """{room_uid: (name, planned spec)} for every live planned registry row."""
    from core.db import q

    out = {}
    for row in q(
            "SELECT room_uid,name,payload FROM room_registry "
            "WHERE chat_id=? AND retired_turn_id IS NULL", (cid,)):
        payload = _payload(row)
        spec = payload.get("planned") if isinstance(payload, dict) else None
        if isinstance(spec, dict):
            out[str(row["room_uid"])] = (str(row["name"] or row["room_uid"]),
                                         spec)
    return out


def is_planned_stub(scene, room_id, specs=None):
    """Is this live room still the plan's prose-free stub?

    A stub is a room the scene marks `planned` with no `desc`, or one the
    registry plans that the scene has not yet described. A room with a
    description has been developed, whatever flag it still carries.
    """
    room = ((scene or {}).get("rooms") or {}).get(room_id)
    if not isinstance(room, dict):
        return False
    if str(room.get("desc") or room.get("description") or "").strip():
        return False
    if room.get("planned"):
        return True
    return bool(specs and room_id in specs)


def rooms_to_develop(scene, focus_room, extra=()):
    """The rooms a Director beat is standing in or could be looking into:
    the focus room, any movement target, and every neighbour of the focus
    room joined by something other than a wall -- a closed door is a room
    the beat may open, and a room in view through an open one is a room
    the beat may describe. Deterministic; reads no prose."""
    from world.spatial import effective_adjacent, normalize_barrier

    rooms = (scene or {}).get("rooms") or {}
    out = []
    for rid in (focus_room, *extra):
        if rid and rid in rooms and rid not in out:
            out.append(str(rid))
    if focus_room and focus_room in rooms:
        for edge in effective_adjacent(scene, focus_room):
            if not isinstance(edge, dict) or not edge.get("to"):
                continue
            if normalize_barrier(edge.get("barrier")) == "wall":
                continue
            to = str(edge["to"])
            if to in rooms and to not in out:
                out.append(to)
    return out


def planned_room_brief(cid, scene, room_ids):
    """The Director's development brief for the planned stubs among
    `room_ids`: {room_id: {name, purpose, access, exits, structure}}.

    THE SEED, HANDED TO THE HAND THAT FURNISHES. The plan says what a room
    is FOR and what it joins; the Director says what is in it. Purpose and
    exits are given and protected (`protect_planned_edges`); contents are
    the Director's, and this brief is the one place the plan's purpose
    reaches a model during play. It is author knowledge: it goes to the
    Director stages and the spatial hand, never to a mind or the narrator,
    which learn the room by perceiving what the Director wrote.
    """
    specs = _planned_specs(cid)
    rooms = (scene or {}).get("rooms") or {}
    names = {rid: str((r or {}).get("name") or rid) for rid, r in rooms.items()}
    names.update({rid: name for rid, (name, _s) in specs.items()})
    structures = None
    out = {}
    for rid in room_ids or ():
        if not is_planned_stub(scene, rid, specs):
            continue
        room = rooms.get(rid) or {}
        name, spec = specs.get(rid, (names.get(rid, rid), {}))
        exits = {}
        for edge in list(spec.get("adjacent") or ()) + list(
                room.get("adjacent") or ()):
            if not isinstance(edge, dict) or not edge.get("to"):
                continue
            to = str(edge["to"])
            entry = exits.setdefault(to, {"to": to, "name": names.get(to, to)})
            for key in ("barrier", "dir", "name"):
                if edge.get(key) and key not in entry or key == "name" \
                        and edge.get(key):
                    entry[key if key != "name" else "way"] = edge[key]
        brief = {
            "name": name,
            "purpose": str(spec.get("purpose") or room.get("purpose") or ""),
            "access": str(spec.get("access") or room.get("access") or ""),
            "exits": list(exits.values()),
        }
        skey = str(spec.get("structure") or "")
        if skey:
            if structures is None:
                from core.db import wget_for_frame
                structures = normalize_structures(
                    wget_for_frame(cid, STRUCTURES_KEY, None, {}) or {})["items"]
            structure = structures.get(skey)
            if structure:
                brief["structure"] = {
                    "key": skey,
                    "grammar": structure.get("grammar") or [],
                }
        out[rid] = brief
    return out


def planned_room_ids(cid):
    """Every live registry room that carries a plan -- the town's own
    topology, which a beat may furnish and may not delete."""
    return set(_planned_specs(cid))


def protect_planned_edges(cid, scene):
    """Put back every planned exit a development dropped.

    A developed room may ADD exits; it may not lose one the plan gave it,
    because the plan is the town's topology and every other planned room
    counts on the way through. Restores the edge from the plan's own record
    (barrier, bearing, name) on the room that lost it. Returns
    [(room_id, to)] restored, for the caller's warning.
    """
    specs = _planned_specs(cid)
    rooms = (scene or {}).get("rooms") or {}
    restored = []
    for rid, (_name, spec) in specs.items():
        room = rooms.get(rid)
        if not isinstance(room, dict):
            continue
        present = {
            str(e.get("to")) for e in (room.get("adjacent") or [])
            if isinstance(e, dict) and e.get("to")}
        for other_id, other in rooms.items():
            if isinstance(other, dict):
                for e in other.get("adjacent") or []:
                    if isinstance(e, dict) and e.get("to") == rid:
                        present.add(str(other_id))
        for edge in spec.get("adjacent") or ():
            if not isinstance(edge, dict) or not edge.get("to"):
                continue
            to = str(edge["to"])
            if to in present or (to not in rooms and to not in specs):
                continue
            room.setdefault("adjacent", []).append(dict(edge))
            restored.append((rid, to))
    return restored


def settle_developed_stubs(scene):
    """A planned stub that now carries a description is a room.

    Drops the `planned` flag and the plan's `purpose`/`access` seed from the
    live record: the registry keeps the plan, and the seed was author
    knowledge that has done its work. Returns the room ids settled.
    """
    settled = []
    for rid, room in ((scene or {}).get("rooms") or {}).items():
        if not isinstance(room, dict) or not room.get("planned"):
            continue
        if not str(room.get("desc") or room.get("description") or "").strip():
            continue
        room.pop("planned", None)
        room.pop("purpose", None)
        room.pop("access", None)
        settled.append(str(rid))
    return settled


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
    # A planned room reserves its uid, its name and every alias: a stub may
    # not be minted under any spelling the plan already answers to, and an
    # axis written in one of those spellings is an edge to that room.
    by_name = {}
    for row_uid, row in by_uid.items():
        by_name.setdefault(row_uid, row_uid)
        by_name.setdefault(normalize_room_id(str(row["name"] or "")), row_uid)
        try:
            aliases = json.loads(row["aliases"] or "[]")
        except (TypeError, ValueError):
            aliases = []
        for alias in aliases or ():
            by_name.setdefault(normalize_room_id(str(alias or "")), row_uid)
    by_name.pop("", None)
    existing = set(by_uid) | set(by_name)
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
            # An axis that names a room the plan already has is not a stub
            # to mint but an edge to draw: "the lane continues to Market
            # Square" reaches the square, never a second one.
            target = by_name.get(
                normalize_room_id(str(axis).replace("_", " ")))
            if target and target != uid:
                edge = {"to": target, "barrier": "open_door", "axis": axis}
                spec.setdefault("adjacent", []).append(edge)
                rooms.setdefault(uid, {"name": str(by_uid[uid]["name"] or uid),
                                       "adjacent": []})
                rooms[uid].setdefault("adjacent", []).append(dict(edge))
                if isinstance(rooms.get(target), dict):
                    rooms[target].setdefault("adjacent", []).append(
                        {"to": uid, "barrier": "open_door"})
                continue
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
