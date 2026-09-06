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
from world.regions import normalize_region_id
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


#: The MEASURABLE half of a planned room, in the scene's own vocabulary.
#: `story.plot_packages._plan_geometry` normalizes and clamps these three
#: against the same closed sets a LIVED room is read through
#: (`spatial.normalize_extent` / `spatial.SHAPES` / `weather.EXPOSURES`), so
#: what the registry holds is already a scene value and is carried through as
#: is. Absent stays absent: a room that measured nothing must read exactly as
#: it did before a plan could measure anything, and a `None` written into the
#: field is not the same as no field.
GEOMETRY_FIELDS = ("extent", "shape", "exposure")


def planned_geometry(planned):
    """The geometry a planned room carries, omitting what it does not."""
    planned = planned if isinstance(planned, dict) else {}
    return {key: copy.deepcopy(planned[key]) for key in GEOMETRY_FIELDS
            if planned.get(key)}


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
            # A structure IS a region (world/regions.py): a planned room
            # enters the scene already knowing which part of the map it is.
            "region": normalize_region_id(structure_key),
            # And what the plan MEASURED, beside what the room is FOR.
            **planned_geometry(planned),
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


#: The widest a place's NAME runs before it stops being a name and starts
#: being a description of what is that way. Measured 2026-09-05 over every
#: frontier two live plans wrote: the nine phrases that minted junk rooms ran
#: 5 to 9 words ("the river flowing west upstream", "bare grassy slopes
#: falling away to the east and west"), and every label that named a place ran
#: 1 to 4 ("north", "far road", "west ridge path", "the fish wharves lane").
#: Four is where the two populations part.
FRONTIER_NAME_WORDS = 4


def frontier_refusal(axis, *, allow_bearing=False):
    """Why this frontier label cannot be minted as a room, or ``None``.

    A FRONTIER NAMES A PLACE. It is the answer to "what lies that way", and
    the way out is drawn to it by name -- so what cannot be a place's name
    cannot be minted as one, and is reported instead of becoming a room whose
    id is the sentence somebody wrote.

    Two things are not a name, and both were measured:

    * a bare BEARING (F3, chat 116): `frontier: ["west"]` minted a room called
      West. A direction is where the way out points, not what is at the end of
      it, and it belongs on `adjacent.bearing`.
    * a DESCRIPTION (F63 / PD4, the market and the road runs, six junk rooms
      of fifteen in one story): `frontier: ["the village street of Ambry
      beyond the gate"]` minted
      `the_village_street_of_ambry_beyond_the_gate` -- no extent, no light, no
      exposure, rendered to the player as "Through the open doorway is The
      Village Street Of Ambry Beyond The Gate", and reported by
      `inspect_contradictions.structure` as an edge to an unknown room ever
      after.

    The distinction is stated as the class rather than as a vocabulary of
    English: a name is short because it is a name (`FRONTIER_NAME_WORDS`), and
    a bearing is a closed set the engine owns.

    `allow_bearing` is for the MINT, and only there: the fringe has a grammar
    to draw on, so a bearing off a square becomes "North Lane" -- a real name
    for a real place -- and plans published before the authoring gate existed
    still carry bearings that mint correctly. A description has no such
    remedy: there is no name in it to draw.
    """
    from world.spatial import normalize_bearing

    text = " ".join(str(axis or "").split())
    if not text:
        return None
    word = text.casefold()
    if not allow_bearing and (normalize_bearing(word) or word in ("up", "down")):
        return ("frontier %r is a direction; a frontier names WHAT lies that "
                "way (a lane, a yard, the town beyond), and a direction "
                "belongs on adjacent.bearing" % text)
    if len(text.split()) > FRONTIER_NAME_WORDS:
        return ("frontier %r describes what lies that way instead of naming "
                "it; a frontier is the NAME the place is reached by, because "
                "the way out is drawn to it by that name -- say the name and "
                "put the description in the room's purpose" % text)
    return None


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
    those were every duplicate room of the run. THAT CLASS IS CLOSED, in two
    halves: the naming half here (2026-09-03), and the half a name could
    never reach -- a later plan had no way to say "that space is mine", so
    it built a rival beside the stub whatever the stub was called. A plan
    now CLAIMS the space by identity (`claim_frontier_spaces`,
    `docs/design/DESIGN_FRONTIER_SPACES.md`, 2026-09-05).

    A STUB REMEMBERS WHAT IT STANDS FOR, which is what makes a later plan
    able to claim it instead of building a rival beside it: the spec keeps
    the axis it was minted from (`frontier_of`) and a `provisional` mark
    saying this room is a space held open, not a space spent.

    AND IT INHERITS THE AXIS IT WAS MINTED FROM, so the road runs on. A
    frontier is the answer to "what lies that way", and one ring out the
    answer is still the same road -- so the stub carries the axis onward and
    the world does not stop one ring past whatever a plan drew.  The onward
    axis is refused exactly where the plan-side gate refuses it (ONE RULE,
    ONE OWNER, `frontier_refusal`): a bearing is not the name of a place, so
    it cannot be the name of what lies beyond the place it named.
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
    # A PURPOSE THAT IS THE NAME SAYS NOTHING, AND READS AS AUTHORED. A
    # structure with no grammar falls back to a rule built out of the axis
    # label itself, so the purpose comes back as the room's own name: the
    # Room's `frontier: ["Lake Sarrat Dry Bed"]` minted a planned room whose
    # entire description was "Lake Sarrat Dry Bed" (PS8, solitude run,
    # 2026-09-05). An ABSENT purpose is honest -- the Director furnishes the
    # room on entry, and `is_planned_stub` already reads a stub with no prose
    # as a stub -- where a purpose equal to the name is a description nobody
    # wrote standing in the way of the one somebody would.
    purpose = str(purposes[rng.randrange(len(purposes))] or "")
    if normalize_room_id(purpose) in (normalize_room_id(name),
                                      normalize_room_id(axis_label)):
        purpose = ""
    return uid, {
        "name": name, "purpose": purpose,
        "structure": structure["key"], "access": "",
        # AN OPENING, NOT A DOOR. A frontier label answers "what lies that
        # way" and says nothing about what stands between, so minting
        # `open_door` invented a door -- outdoors, a door between a wharf
        # terrace and a dry lake bed (PS8). `open` asserts strictly less and
        # is passable, visible, audible and scent-carrying everywhere
        # `open_door` is; the Director may still declare a door when it
        # furnishes the room.
        "adjacent": [{"to": str(from_uid), "barrier": "open"}],
        "frontier": [] if frontier_refusal(axis) else [str(axis)],
        "provisional": True,
        "frontier_of": {"room": str(from_uid), "axis": str(axis)},
    }


def plant_structure(cid, structure, rooms, *, owning_book_id=None,
                    created_turn_id=None, claims=None):
    """Persist a prose-free planned skeleton and its structure grammar.

    `claims` is `claim_frontier_spaces`' second return value, and it is the
    only thing that may write a room's NAME to something other than the
    plan's own: a claimed room keeps the name a story has been using for it
    and accumulates the other spelling as an alias, so every reference
    already written still resolves (`_planned_spellings`). Absent, this
    writes exactly what it always wrote.
    """
    from core.db import q, qi, transaction, wget_for_frame, wset_for_frame

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
            # What a claimed stub was minted for, carried through the claim:
            # the axis a room was minted from names the way ON, and
            # `prepare_frontier_expansion` reads it to tell a chain from a
            # reference. Absent on every room no frontier made.
            **({"frontier_of": dict(raw["frontier_of"])}
               if isinstance(raw.get("frontier_of"), dict) else {}),
            # A plan could say what a room is FOR and not how big it is: this
            # rebuild listed the prose fields and dropped the measurement, so
            # a stall range asked for "four paces wide and twenty long"
            # reached the registry sizeless and survived only as prose in
            # `purpose` (F47, measured 2026-09-05 in all five play runs).
            **planned_geometry(raw),
        }
    if len(normalized) > structure["max_planned"]:
        raise ValueError("planned rooms exceed structure.max_planned")
    claimed = (claims or {}).get("rows") or {}
    holders = (claims or {}).get("holders") or {}
    with transaction():
        for uid, planned in normalized.items():
            payload = json.dumps({"planned": planned}, ensure_ascii=False)
            row = claimed.get(uid)
            if row:
                # A CLAIM RENAMES IN PLACE. The uid never moves, so the name
                # and the alias list are the only columns that change, and
                # the old name goes into the aliases the same commit the new
                # one goes into the column.
                qi(
                    "INSERT INTO room_registry"
                    "(chat_id,room_uid,owning_book_id,parent_entity,name,"
                    "aliases,payload,created_turn_id,retired_turn_id) "
                    "VALUES(?,?,?,?,?,?,?,?,NULL) "
                    "ON CONFLICT(chat_id,room_uid) DO UPDATE SET "
                    "name=excluded.name,aliases=excluded.aliases,"
                    "payload=excluded.payload,retired_turn_id=NULL",
                    (cid, uid, owning_book_id, None, row["name"],
                     json.dumps(row.get("aliases") or [], ensure_ascii=False),
                     payload, created_turn_id),
                )
                continue
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
        # A claim on a space nothing has minted into yet spends the holder's
        # axis and records what now stands in it; only the holder's planned
        # payload moves, never its identity.
        for uid, spec in holders.items():
            row = q("SELECT payload FROM room_registry WHERE chat_id=? AND "
                    "room_uid=?", (cid, uid), one=True)
            if not row:
                continue
            payload = _payload(row)
            payload["planned"] = spec
            qi("UPDATE room_registry SET payload=? WHERE chat_id=? AND "
               "room_uid=?",
               (json.dumps(payload, ensure_ascii=False), cid, uid))
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
    #: room uid -> the planned edges this pass offers it, applied below once
    #: every stub of the pass exists.
    supply = {}
    for uid in occupied:
        spec = (planned.get(uid) or (None, {}))[1]
        planned_edges = [dict(e) for e in spec.get("adjacent") or ()
                         if isinstance(e, dict) and e.get("to")]
        # A plan may attach to a room the scene ALREADY HOLDS from the
        # planned side only: the Room plans a lighthouse "adjacent: [{to:
        # beach}]" and the live beach, which is in no plan, carries no spec
        # naming the lighthouse back. Read from the occupied room alone, the
        # fringe never saw such a neighbour, so the player walked toward a
        # published plan and the Director minted a stub of its own beside
        # it and filed a need the plan already answered (chat 114 on a copy,
        # 2026-09-05, turns 4-6: `beach_far_end` minted, the planned
        # `lighthouse_keeper_room` never). An edge is one doorway however
        # many sides declare it, so a planned room whose spec names the
        # occupied room is that room's planned neighbour too, and the
        # occupied room receives the reciprocal exit it did not declare.
        for other_uid, (_name, other_spec) in planned.items():
            if other_uid == uid or other_uid in rooms:
                continue
            for e in other_spec.get("adjacent") or ():
                if isinstance(e, dict) and str(e.get("to") or "") == uid \
                        and not any(str(pe.get("to")) == other_uid
                                    for pe in planned_edges):
                    planned_edges.append({
                        "to": other_uid,
                        **{k: v for k, v in (("barrier", e.get("barrier")),)
                           if v}})
        targets.update(str(e.get("to")) for e in planned_edges)
        if uid in rooms and planned_edges:
            supply.setdefault(uid, []).extend(planned_edges)
    for uid in sorted(targets):
        if uid in rooms or uid not in planned:
            continue
        name, spec = planned[uid]
        rooms[uid] = {
            "name": name, "adjacent": [],
            "planned": True, "purpose": str(spec.get("purpose") or ""),
            # A stub is measured the beat it is minted, not once some hand
            # describes it: a planned room reaching the live scene by the
            # fringe is the same room `skeleton_rooms` lays out at the
            # opening, and a measurement the plan stated is not the
            # Director's to invent a second time.
            **planned_geometry(spec),
        }
        if spec.get("structure"):
            rooms[uid]["region"] = normalize_region_id(spec["structure"])
        supply[uid] = [dict(e) for e in spec.get("adjacent") or ()
                       if isinstance(e, dict) and e.get("to")]
        added += 1
    # WHILE A ROOM IS STILL THE PLAN'S PROSE-FREE STUB, THE PLAN OWNS ITS
    # NAME, ITS PURPOSE AND ITS MEASUREMENTS. A claim renames the registry
    # row in place, and the live scene has to follow: `_prepare_room_registry`
    # projects the registry's name FROM the scene every commit, so a
    # registry-only rename of a stub the fringe has already materialized is
    # written back to its old name on the next beat and the claim silently
    # un-happens. Once the room carries prose it is its own
    # (`settle_developed_stubs` takes the seed off) and nothing here touches
    # it -- which is the same line the claim draws when it refuses to rename.
    for uid, (name, spec) in planned.items():
        room = rooms.get(uid)
        if not isinstance(room, dict) or not room.get("planned"):
            continue
        if str(room.get("desc") or room.get("description") or "").strip():
            continue
        room["name"] = name
        if str(spec.get("purpose") or ""):
            room["purpose"] = str(spec["purpose"])
        room.update(planned_geometry(spec))
    # THE SCENE ONLY EVER HOLDS AN EDGE INTO A ROOM THE SCENE HOLDS, and the
    # membership test runs after every stub of this pass exists, so two
    # planned rooms minted together keep the doorway between them.
    #
    # The plan keeps the rest. A fringe that materialises only the room next
    # to the occupied one hands the new stub the plan's whole adjacency,
    # including the way on to a room nobody has walked toward yet; the
    # dangling-exit guard then drops that edge and warns, in the same commit,
    # every beat, for ever ("scene: dropped exit(s) from `desert_road_east`
    # to undefined room(s) `milestone_shrine`", nine consecutive beats of one
    # caravanserai run, 2026-09-05). `protect_planned_edges` states the other
    # half of the same rule and puts the edge back the beat the target is
    # minted, so nothing is lost -- what stops is a warning about a room the
    # world does not have yet.
    for uid, edges_in in supply.items():
        room = rooms.get(uid)
        if not isinstance(room, dict):
            continue
        # The live definition owns prose/physics it declared; structure
        # supplies only exits that live mapping has not named.
        edges = {str(e.get("to")): dict(e)
                 for e in (room.get("adjacent") or ())
                 if isinstance(e, dict) and e.get("to")}
        for edge in edges_in:
            to = str(edge.get("to") or "")
            if to and to in rooms:
                edges.setdefault(to, dict(edge))
        room["adjacent"] = list(edges.values())
    _settle_stub_barriers(rooms)
    return scene, added


def _settle_stub_barriers(rooms):
    """A STUB'S DOORWAY IS THE PLAN'S GUESS UNTIL SOMEONE STANDS AT IT.

    An edge is one doorway however many sides declare it, and a barrier is a
    property of the doorway rather than of the side you stand on --
    `spatial_merge._mirror_symmetric_barriers` states that for a diff, which
    is where both sides are written by the same hand in the same breath. The
    plan-supply path above never met that rule: a stub takes its exits from
    the plan, where the barrier is whatever the Room wrote (or the schema's
    open way through) before anybody had been there, and it keeps that
    barrier for ever while the story goes on describing the same doorway
    from the room it can actually see.

    Every sense then reads whichever side it happens to stand on. Measured
    in the descent run (chat 117, turn 13): six of the seven doorways off
    one service spine disagreed with themselves, and the containment annex
    -- which the spine records behind a shut `closed_door` named "the
    containment door" -- heard through an `open_door`, because that is what
    its own side still said.

    The plan yields and the story stands: a stub's barrier is replaced by
    the one the room on the other side declares, and only ever by a barrier
    that room actually carries. A stub with prose is not a stub any more
    (`settle_developed_stubs` takes the flag off) and is not touched, and a
    declaration made from the stub's OWN side has already been mirrored onto
    the live room by the merge, so what is left here is exactly the
    plan-against-story disagreement."""
    for uid, room in (rooms or {}).items():
        if not isinstance(room, dict) or not room.get("planned"):
            continue
        for edge in room.get("adjacent") or ():
            if not isinstance(edge, dict) or not edge.get("to"):
                continue
            other = rooms.get(str(edge["to"]))
            if not isinstance(other, dict):
                continue
            for back in other.get("adjacent") or ():
                if not isinstance(back, dict) \
                        or str(back.get("to") or "") != str(uid):
                    continue
                if "barrier" in back and back["barrier"] != edge.get("barrier"):
                    edge["barrier"] = back["barrier"]
                break


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


def _planned_spellings(cid):
    """``{room_uid: {spelling, ...}}`` -- every spelling a live planned room
    answers to, folded by `normalize_room_id`: its id, its current name and
    every alias the registry keeps for it.

    THE ALIAS IS THE WHOLE POINT OF A RENAME. A room the plan renames keeps
    its uid and its old name as an alias (`claim_frontier_spaces`), and a
    lookup that reads only the `name` column stops answering to the old
    spelling the moment the new one lands -- so a Director still saying
    "Coastal Lane" mints `coastal_lane_2` beside the plan's room, which is
    exactly the duplicate class the claim exists to close (the second bridge
    road, Harrowmere 2026-09-03). `_registry_alias_index` and
    `subjects.resolve_subject` already read aliases; the plan's own tables
    did not.
    """
    from core.db import q

    out = {}
    for row in q(
            "SELECT room_uid,name,aliases,payload FROM room_registry "
            "WHERE chat_id=? AND retired_turn_id IS NULL", (cid,)):
        payload = _payload(row)
        spec = payload.get("planned") if isinstance(payload, dict) else None
        if not isinstance(spec, dict):
            continue
        try:
            aliases = json.loads(row["aliases"] or "[]")
        except (TypeError, ValueError, json.JSONDecodeError):
            aliases = []
        keys = {normalize_room_id(str(row["room_uid"])),
                normalize_room_id(str(row["name"] or ""))}
        keys.update(normalize_room_id(str(a or "")) for a in aliases or ())
        keys.discard("")
        out[str(row["room_uid"])] = keys
    return out


def planned_room_spellings(cid):
    """{spelling: room_uid} for every live planned registry room, under its
    id, its name and every alias as `normalize_room_id` spells them. A
    spelling two plans share maps to ``""``: two rooms answer to it, so it
    names neither (the room rule `dedup_minted_rooms` applies to bodies
    too)."""
    out = {}
    for uid, keys in _planned_spellings(cid).items():
        for key in keys:
            out[key] = "" if key in out and out[key] != uid else uid
    return out


def is_planned_stub(scene, room_id, specs=None):
    """Is this live room still the plan's prose-free stub?

    A stub is a room the scene marks `planned` with no `desc`, or one the
    registry plans that the scene has not yet described. A room with a
    description has been developed, whatever flag it still carries.
    """
    room = ((scene or {}).get("rooms") or {}).get(room_id)
    if not isinstance(room, dict):
        # Planned by the registry and not yet a scene row: a stub the
        # scene has not reached, which is exactly what a brief is for.
        return bool(specs and room_id in specs)
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
    if focus_room and focus_room in rooms:
        out.append(str(focus_room))
    # A declared target is in reach whether or not the scene holds it yet:
    # a planned room the beat walks into is briefed before it is a scene
    # row (`planned_room_brief` keeps only what the plan knows).
    for rid in extra:
        if rid and str(rid) not in out:
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
            # The part of the map the room is in, by the structure that
            # planned it (world/regions.py) -- so the hand furnishing a stub
            # knows what the room is part of, and its neighbours it mints
            # inherit the same answer.
            brief["region"] = {
                "id": normalize_region_id(skey),
                "name": str((structure or {}).get("name") or skey),
            }
        out[rid] = brief
    return out


def planned_room_ids(cid):
    """Every live registry room that carries a plan -- the town's own
    topology, which a beat may furnish and may not delete."""
    return set(_planned_specs(cid))


def planned_room_index(cid, scene=None):
    """`{room_uid: name}` for every live planned room the SCENE does not yet
    hold -- one line each, the whole plan, uncapped.

    THE BRIEF IS SCOPED; KNOWING THE PLACE EXISTS MUST NOT BE.
    `planned_room_brief` deliberately covers only the stubs a beat stands in
    or looks into, because a purpose, an access note and an exit list are
    expensive and a Director furnishing a room only needs the one it is
    entering. But a player names a place from anywhere -- across a town, from
    memory, from something a character said three beats ago -- and a Director
    that has never been shown the name cannot spell it. It invents one, and
    `classify_movement` cannot rescue an invention that shares no word with
    the plan's spelling.

    Measured (the Salt Terraces, 2026-09-05, PS5): the Writers' Room
    published "Town Habitations Shelf" (`town_shelf_lane`) and a roofless
    common hall; from three rooms away the interpret payload carried no
    `planned_rooms` key at all, the Director wrote
    `upper_terrace_settlement`, and the beat after minted
    `settlement_common_hall` beside the planned one. The town ended with two
    shelves of workers' houses, two common halls, and the one thing the Room
    had planted to be found unreachable in either.

    So the index is a NAME and nothing else, which is what a spelling costs:
    seven rooms was 591 bytes in that run, and the largest plan in the
    owner's database (chat 114, 49 rooms) is a few kilobytes. Uncapped, per
    the owner's standing ruling that a cap is named rather than buried --
    there is nothing here to cap.
    """
    rooms = (scene or {}).get("rooms") or {}
    return {rid: name for rid, (name, _spec) in _planned_specs(cid).items()
            if rid not in rooms}


def planned_topology(cid):
    """``{room_uid: [adjacent room uids]}`` for every live planned registry
    row -- the plan's edges by ID. `planned_context` renders the same edges
    by NAME for a reader; a walk over the graph wants the ids."""
    out = {}
    for rid, (_name, spec) in _planned_specs(cid).items():
        out[rid] = [str(edge.get("to")) for edge in spec.get("adjacent") or ()
                    if isinstance(edge, dict) and edge.get("to")]
    return out


def planned_rooms_named_in(cid, text):
    """The planned rooms whose uid or name spelling sits inside ``text``,
    folded the way `planned_context` folds a query -- the rooms a scenario
    names without ids. Sorted, for a stable payload."""
    folded = normalize_room_id(str(text or ""))
    if not folded:
        return []
    out = []
    for rid, keys in _planned_spellings(cid).items():
        if any(k == folded or k in folded for k in keys):
            out.append(str(rid))
    return sorted(out)


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
            # Only into a room the SCENE holds. An edge to a planned room the
            # fringe has not minted yet is the plan's, not the scene's: put
            # back here, the dangling-exit guard drops it as undefined in the
            # same commit, and the pair fired four warnings a beat on chat
            # 114's terrace (lounge, dining, garden, 2026-09-04) while
            # changing nothing. The edge returns the beat the stub is minted.
            if to in present or to not in rooms:
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
    # AND EVERY SPELLING THE ROOM ANSWERS TO, the old name a claim retired
    # included (`_planned_spellings`): a brief asked for under the name the
    # story has been using is the same room, not an unplanned destination.
    spellings = _planned_spellings(cid)
    for row in all_rows:
        payload = _payload(row)
        spec = payload.get("planned") if isinstance(payload, dict) else None
        if not isinstance(spec, dict):
            continue
        uid, name = str(row["room_uid"]), str(row["name"] or row["room_uid"])
        keys = set(spellings.get(uid) or ())
        keys.update({normalize_room_id(uid), normalize_room_id(name)})
        keys.discard("")
        exact = folded in keys
        if not exact and not any(key in folded for key in keys):
            continue
        rows.append({
            "_exact": exact,
            "room_uid": uid, "name": name,
            "purpose": str(spec.get("purpose") or ""),
            "structure": str(spec.get("structure") or ""),
            # The structure's key as a region id (world/regions.py): the
            # part of the map a reader files the room under.
            "region": normalize_region_id(spec.get("structure") or "") or None,
            "access": str(spec.get("access") or ""),
            "adjacent": [names.get(str(edge.get("to")), str(edge.get("to")))
                         for edge in spec.get("adjacent") or ()
                         if isinstance(edge, dict) and edge.get("to")],
        })
    # AN EXACT MATCH IS NOT AMBIGUOUS, and the substring tier is what made it
    # look like one. The match above is deliberately loose -- the Director
    # writes a destination as a description ("Reeve's Hall interior and
    # occupants"), so a room answers when its spelling SITS INSIDE the query
    # -- but a room id also sits inside another room id. Measured on the live
    # chat 114 register: a room called `parking` is a substring of
    # `guest_parking_lot`, so both matched, `len(rows) != 1`, and the query
    # resolved to None; 30-odd rooms of that story's district answered nothing
    # at all, which is the brief the Director is handed walking into one.
    #
    # So the tiers are ranked rather than pooled. A query that names a room
    # exactly is answered by that room however many others it also brushes;
    # only when nothing matches exactly does the loose tier decide, and there
    # an ambiguity is still refused, because two descriptions matching one
    # query really is two candidates. Two EXACT hits stay refused too: one
    # room's uid equalling another's name is a genuine collision this cannot
    # break by guessing.
    exact = [r for r in rows if r.pop("_exact")]
    for row in rows:
        row.pop("_exact", None)
    if len(exact) == 1:
        return exact[0]
    if exact:
        return None
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
        # WHAT THE PLAN RESERVED AND WHAT NOW STANDS IN IT. An axis used to
        # be simply deleted the moment it minted, so nothing anywhere
        # recorded that a room was a placeholder and a later plan had no
        # slot to claim -- it built a rival beside it instead (the second
        # bridge road). ``{axis: room_uid}`` on the holder is that record.
        standing = dict(spec.get("frontier_standing") or {}) \
            if isinstance(spec.get("frontier_standing"), dict) else {}
        origin = spec.get("frontier_of")
        own_axis = str((origin or {}).get("axis") or "") \
            if isinstance(origin, dict) else ""
        for axis in frontiers:
            # WHAT CANNOT BE A PLACE'S NAME IS NOT MINTED AS ONE. A phrase
            # describing what lies that way is kept on the spec, where
            # `structure_warnings` reports it, instead of becoming a registry
            # room whose uid is the sentence (F63/PD4).
            if frontier_refusal(axis, allow_bearing=True):
                retained.append(axis)
                continue
            # An axis that names a room the plan already has is not a stub
            # to mint but an edge to draw: "the lane continues to Market
            # Square" reaches the square, never a second one.
            #
            # AN AXIS A ROOM WAS MINTED FROM NAMES THE WAY ON, NOT THE ROOM
            # IT MADE. A stub inherits its axis so the frontier keeps
            # moving; read as a reference, the inherited label would resolve
            # to the very room it named -- one ring out, the room BEFORE it
            # -- and the road would stop at its second segment with an edge
            # doubling back. A room's own origin axis is the one spelling
            # that cannot mean a room that already exists.
            target = None if axis == own_axis else by_name.get(
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
                standing[axis] = target
                continue
            if counts.get(structure_key, 0) >= normalize_structure(
                    structure)["max_planned"]:
                retained.append(axis)
                continue
            new_uid, new_spec = mint_frontier(
                structure, uid, axis, f"{cid}:{structure_key}", existing)
            existing.add(new_uid)
            standing[axis] = new_uid
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
            if structure_key:
                rooms[new_uid]["region"] = normalize_region_id(structure_key)
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
            if standing:
                spec["frontier_standing"] = standing
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


def frontier_spaces(cid):
    """Every frontier space the plan is still holding OPEN, for a planner.

    A SPACE IS THE AXIS, THE ROOM IT HANGS OFF, AND WHAT STANDS THERE. Two
    states, and both are unfilled:

    * ``open`` -- the axis is on the holder's plan and nothing has minted
      from it, because nobody has stood in the holder room yet. An axis the
      mint refuses (`frontier_refusal`) is open too and says why.
    * ``provisional`` -- a stub stands in the space, named from the
      structure's grammar, standing in until a plan claims it.

    A space a real plan fills is not a space and is not listed. A planner
    that cannot see the slot plans BESIDE it, which is exactly what the
    Harrowmere corpus measured: the axis "upland road" minted a stub called
    "bridge road" beside the real Bridge Road and the Director, shown the
    stub, minted `upland_road` beside THAT. Those, with `slate_lane_2` and
    `market_square_2`/`_3`, were every duplicate room of the run.

    `claim_frontier_spaces` takes the ``room`` and ``axis`` of a row here.
    """
    specs = _planned_specs(cid)
    out = []
    for uid, (name, spec) in specs.items():
        skey = str(spec.get("structure") or "")
        for axis in spec.get("frontier") or ():
            axis = str(axis or "")
            if not axis:
                continue
            row = {"room": uid, "room_name": name, "structure": skey,
                   "axis": axis, "state": "open"}
            refusal = frontier_refusal(axis, allow_bearing=True)
            if refusal:
                row["unmintable"] = refusal
            out.append(row)
        standing = spec.get("frontier_standing")
        if not isinstance(standing, dict):
            continue
        for axis, target in standing.items():
            stub_name, stub_spec = specs.get(str(target), ("", {}))
            if not isinstance(stub_spec, dict) or not stub_spec.get("provisional"):
                continue
            out.append({"room": uid, "room_name": name, "structure": skey,
                        "axis": str(axis), "state": "provisional",
                        "stub": str(target), "stub_name": stub_name})
    return sorted(out, key=lambda row: (row["room"], row["axis"]))


def _registry_aliases(cid):
    """``{room_uid: [alias, ...]}`` as the registry stores them."""
    from core.db import q

    out = {}
    for row in q("SELECT room_uid,aliases FROM room_registry WHERE chat_id=? "
                 "AND retired_turn_id IS NULL", (cid,)):
        try:
            aliases = json.loads(row["aliases"] or "[]")
        except (TypeError, ValueError, json.JSONDecodeError):
            aliases = []
        out[str(row["room_uid"])] = [str(a) for a in aliases or () if str(a)]
    return out


def claim_frontier_spaces(cid, rooms, *, scene=None):
    """Rekey planned rooms that CLAIM a frontier space onto the room already
    holding it.

    THE RULE: a minted stub is the space the plan reserved, standing in
    until a plan claims it; claiming renames the room and never mints a
    second one.

    A plan says which space it fills BY IDENTITY -- ``claims: {room, axis}``
    on a planned room, the holder's uid and the axis, both ids
    `frontier_spaces` already hands the planner. Never a name and never a
    resemblance between two nouns: a guard reading free prose fails in
    whichever direction its missing word points, and this one would decide
    whether two places are one place.

    Returns ``(rooms, plan, errors)``:

    * `rooms` -- the map rekeyed onto the claimed uids, every
      ``adjacent.to`` inside the same operation remapped with it, so THE
      ROOM'S UID NEVER CHANGES: edges, the registry projection, anything
      standing in it and every reference already written stay intact. The
      stub's own edges survive a claim that does not name them, the same
      rule `protect_planned_edges` keeps for a developed room.
    * `plan` -- ``{"rows", "holders", "claims"}`` for `plant_structure` to
      write and for a preview to report.
    * `errors` -- one per refusal, naming the holder and what fills the
      space. First claim wins; a second is refused, because a place cannot
      be two things. `plan["refused"]` names the rooms those refusals came
      from: a claim that cannot be honoured must not fall back to planting
      the room ANYWAY, because a room planted beside the space it meant to
      fill is the whole defect.

    A ROOM SOMEBODY HAS BEEN IN KEEPS ITS NAME. A name is what the player
    knows the place by, and renaming it is a lie about their own memory --
    so a claim on such a room takes the purpose, the geometry and the onward
    axes and LEAVES the name, and says which it did. What "has been in"
    means is the record the engine can answer honestly rather than the one
    that would be nicest to have: the room CARRIES PROSE (the live `desc`,
    or `planned.resolved`, which `_prepare_room_registry` maintains from it
    every commit) or a body stands in it NOW. This engine keeps no durable
    "was ever occupied" mark to ask, and prose is the closest honest
    proxy -- a stub is furnished the beat a beat reaches it, and a memory
    is only ever written under the name of a room its owner was standing
    in, so the rooms whose names memory retrieval depends on
    (`memory_retrieval`, which matches `memories.location` by NAME) are
    exactly the rooms this refuses to rename.
    """
    from core.db import wget

    specs = _planned_specs(cid)
    aliases_by_uid = _registry_aliases(cid)
    if scene is None:
        scene = wget(cid, "scene", {}) or {}
    scene = scene if isinstance(scene, dict) else {}
    live = scene.get("rooms") or {}
    occupied = {str(r) for r in (scene.get("positions") or {}).values()
                if str(r)}
    rooms = {str(k): dict(v) for k, v in (rooms or {}).items()
             if isinstance(v, dict)}
    errors, records, rows, work = [], [], {}, {}
    rename, filled, refused = {}, set(), []

    def _live_prose(uid):
        room = live.get(uid)
        if not isinstance(room, dict):
            return False
        return bool(str(room.get("desc") or room.get("description")
                        or "").strip())

    for key in sorted(rooms):
        raw = rooms[key].pop("claims", None)
        if raw is None:
            continue
        if not isinstance(raw, dict):
            errors.append("room %r claims a frontier space that is not a "
                          "{room, axis}" % key)
            refused.append(key)
            continue
        holder = str(raw.get("room") or "")
        axis = str(raw.get("axis") or "")
        if not holder or not axis:
            errors.append("room %r claims a frontier space without naming "
                          "both the room it hangs off and the axis it fills"
                          % key)
            refused.append(key)
            continue
        if holder not in specs:
            errors.append("room %r claims the space %r off %r, which holds no "
                          "plan; a frontier space hangs off a planned room"
                          % (key, axis, holder))
            refused.append(key)
            continue
        hspec = work.get(holder) or specs[holder][1]
        standing = hspec.get("frontier_standing")
        standing = dict(standing) if isinstance(standing, dict) else {}
        open_axes = [str(a) for a in hspec.get("frontier") or () if str(a)]
        if (holder, axis) in filled:
            errors.append("room %r claims the space %r off %r, which an "
                          "earlier room of this plan already fills; a place "
                          "cannot be two things" % (key, axis, holder))
            refused.append(key)
            continue
        if axis in standing:
            target = str(standing[axis])
            stub_name, stub_spec = specs.get(target, ("", None))
            if not isinstance(stub_spec, dict):
                errors.append("room %r claims the space %r off %r, whose room "
                              "%r the plan no longer holds"
                              % (key, axis, holder, target))
                refused.append(key)
                continue
            if not stub_spec.get("provisional"):
                errors.append("room %r claims the space %r off %r, which %r "
                              "already fills; a place cannot be two things"
                              % (key, axis, holder, target))
                refused.append(key)
                continue
            if target in rooms and target != key:
                errors.append("room %r claims the space %r off %r, whose room "
                              "%r this same plan also plants"
                              % (key, axis, holder, target))
                refused.append(key)
                continue
            filled.add((holder, axis))
            rename[key] = target
            was = str(stub_name or target)
            wants = str(rooms[key].get("name") or key)
            visited = target in occupied or bool(stub_spec.get("resolved")) \
                or _live_prose(target)
            keep = bool(visited and was and wants != was)
            # The stub's ways out survive a claim that does not name them.
            edges = {str(e.get("to")): dict(e)
                     for e in stub_spec.get("adjacent") or ()
                     if isinstance(e, dict) and e.get("to")}
            for edge in rooms[key].get("adjacent") or ():
                if isinstance(edge, dict) and edge.get("to"):
                    edges[str(edge["to"])] = dict(edge)
            rooms[key]["adjacent"] = list(edges.values())
            if isinstance(stub_spec.get("frontier_of"), dict):
                rooms[key]["frontier_of"] = dict(stub_spec["frontier_of"])
            rows[target] = {
                "name": was if keep else wants,
                "aliases": list(dict.fromkeys(
                    [*aliases_by_uid.get(target, ()), was, wants,
                     target.replace("_", " ")])),
            }
            records.append({
                "room": target, "holder": holder, "axis": axis,
                "stub": target, "was": was, "name": was if keep else wants,
                "renamed": bool(not keep and wants != was),
                "kept_name": keep, "visited": bool(visited)})
            continue
        if axis in open_axes:
            # NOTHING STANDS THERE YET, and the plan's own room fills the
            # space directly: no stub, no rename, and the axis is spent the
            # way a mint spends it.
            filled.add((holder, axis))
            wspec = work.setdefault(holder, copy.deepcopy(specs[holder][1]))
            wspec["frontier"] = [str(a) for a in wspec.get("frontier") or ()
                                 if str(a) and str(a) != axis]
            wstanding = wspec.get("frontier_standing")
            wstanding = dict(wstanding) if isinstance(wstanding, dict) else {}
            wstanding[axis] = key
            wspec["frontier_standing"] = wstanding
            hedges = {str(e.get("to")): dict(e)
                      for e in wspec.get("adjacent") or ()
                      if isinstance(e, dict) and e.get("to")}
            hedges.setdefault(key, {"to": key, "barrier": "open_door",
                                    "axis": axis})
            wspec["adjacent"] = list(hedges.values())
            redges = {str(e.get("to")): dict(e)
                      for e in rooms[key].get("adjacent") or ()
                      if isinstance(e, dict) and e.get("to")}
            redges.setdefault(holder, {"to": holder, "barrier": "open_door"})
            rooms[key]["adjacent"] = list(redges.values())
            records.append({
                "room": key, "holder": holder, "axis": axis, "stub": "",
                "was": "", "name": str(rooms[key].get("name") or key),
                "renamed": False, "kept_name": False, "visited": False})
            continue
        held = sorted(set(open_axes) | set(standing))
        errors.append("room %r claims the space %r off %r, which holds no "
                      "such frontier; %r holds %s"
                      % (key, axis, holder, holder,
                         ", ".join(repr(a) for a in held) or "no frontier"))
        refused.append(key)

    for old, new in rename.items():
        rooms[new] = rooms.pop(old)
    if rename:
        for room in rooms.values():
            for edge in room.get("adjacent") or ():
                if isinstance(edge, dict) and str(edge.get("to")) in rename:
                    edge["to"] = rename[str(edge["to"])]
    return (rooms,
            {"rows": rows, "holders": work, "claims": records,
             "refused": refused},
            errors)


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


def structure_warnings(structure, rooms, known=()):
    """What is wrong with this planned skeleton, in author-facing words.

    `known` is every room that exists OUTSIDE the plan -- in practice the live
    scene's ids. A PLAN MAY NAME A ROOM THAT ALREADY EXISTS: what this warning
    is for is a plan that names a room nothing can be, and a live room is the
    least unknown thing in the scene. It joins the plan too, so a skeleton
    hanging off an existing room is connected rather than "disconnected".

    Measured 2026-09-05 (PE8, Flat 4B): the Writers' Room planned
    `stairwell_fourth_to_third` and `flat_4a_hallway`, each declaring
    `adjacent: [{to: landing}]`; both landed, the landing carried both
    reciprocals, the plan WORKED -- and `inspect_contradictions.structure`
    reported three contradictions for it, so the tool that exists to show the
    Room its errors showed it errors it had not made.
    """
    structure = normalize_structure(structure)
    rooms = rooms if isinstance(rooms, dict) else {}
    known = {str(x) for x in known or ()} - set(rooms)
    warnings = []
    if not rooms:
        return [f"{structure['key']}: structure has no planned rooms"]
    for uid, room in rooms.items():
        if str(room.get("desc") or room.get("description") or "").strip():
            warnings.append(f"{uid}: planned room contains prose")
        destinations = [str(e.get("to")) for e in room.get("adjacent") or ()
                        if isinstance(e, dict) and e.get("to")]
        for target in destinations:
            if target not in rooms and target not in known:
                warnings.append(f"{uid}: planned edge targets unknown room {target}")
        if set(destinations) & set(str(x) for x in room.get("frontier") or ()):
            warnings.append(f"{uid}: frontier label collides with a real edge")
        for axis in room.get("frontier") or ():
            refusal = frontier_refusal(axis, allow_bearing=True)
            if refusal:
                warnings.append(f"{uid}: {refusal}")
    # Undirected reach is sufficient for author diagnostics; runtime pathing
    # will still enforce each authored barrier direction.
    # A live room the plan hangs off is a NODE of the graph, not a hole in
    # it: two planned rooms that both open onto the landing are joined
    # through it.
    nodes = set(rooms) | known
    start, seen = next(iter(rooms)), set()
    stack = [start]
    reverse = {}
    for uid, room in rooms.items():
        for edge in room.get("adjacent") or ():
            if isinstance(edge, dict) and str(edge.get("to")) in nodes:
                reverse.setdefault(str(edge["to"]), set()).add(str(uid))
    while stack:
        uid = stack.pop()
        if uid in seen:
            continue
        seen.add(uid)
        room = rooms.get(uid) or {}
        stack.extend(str(e.get("to")) for e in room.get("adjacent") or ()
                     if isinstance(e, dict) and str(e.get("to")) in nodes)
        stack.extend(reverse.get(uid, ()))
    if len(seen & set(rooms)) != len(rooms):
        warnings.append(f"{structure['key']}: planned skeleton is disconnected")
    return warnings


__all__ = [
    "FRONTIER_NAME_WORDS", "GEOMETRY_FIELDS", "STRUCTURES_KEY",
    "apply_frontier_mutations", "claim_frontier_spaces",
    "composed_scene", "frontier_refusal", "frontier_spaces",
    "planned_geometry",
    "materialize_planned_fringe", "prepare_frontier_expansion",
    "mint_frontier", "normalize_structure", "normalize_structures",
    "planned_context",
    "plant_structure", "skeleton_rooms", "structure_warnings",
]
