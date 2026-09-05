"""Where a charter body stands WITHIN its room -- derived at read time,
laid onto a view of the scene, never stored in it.

``docs/design/DESIGN_CHARTER_PLACEMENT.md``. A charter body's location is
``place``: a scene room id, written only by the movers (`charter_move`).
Within the room it had nothing, and it never entered ``scene.positions``, so
four readers each improvised around the same missing object -- measured
before this module existed:

  * `world.spatial.observer_field` laid no cell for it, so the sight, light
    and sound grids did not know it existed;
  * perception placed it by ROOM alone (`agents.perception._presence_bodies`
    wrote a bare positions row onto the stage's scene copy), so a body with
    no measured station was graded open by `body_visibility` and at the
    room's median light by `light_at`: dim light could not hide one
    townsperson and show another, and a body behind a screen was seen;
  * `charter_observe._observer_scene` faked a positions row for the
    observing body alone, so its eye was graded by room, never by line;
  * `charter_runtime.charter_carriers` vouched for a holder by room because
    the scene had no record to hand the transfer ledger.

THE RULE. A body stands at ONE of four places, tried in order, the first
that answers winning:

  (i)  the body's own authored ``station`` (`charter_model.
       normalize_body_station`): ``{"at": anchor}`` or ``{"cell": [x, y]}``,
       host-written by the map or routed from a Director ``stations`` entry
       at commit (`resolve_scene_placements`), snapped to a cell the room's
       shape keeps (`RoomGrid.nearest`). Cleared by every writer of
       ``place``, so it can never name a fixture of a room the body left.
       FIRST, because it is the more specific and the later fact: the beat
       that stood the clerk at the door said so about HER, where the post's
       anchor says where clerks in general stand -- and a Director station
       that the post overrode next beat would be exactly the snap-back the
       owner's ruling forbids.
  (ii) the post it holds on the watch names an ``anchor`` of the post's
       place (`charter_model.normalize_post`): it stands AT that fixture --
       the clerk at the counter, the smith at the forge. An anchor the room
       does not carry is ignored, fail-open, no lint.
 (iii) a body mid-walk (`charter_move.en_route`) stands at the doorway
       toward its next leg -- the implicit ``door:<next>`` anchor
       `effective_anchors` contributes -- where a courier held at a gate
       stands.
  (iv) otherwise a DEALT cell: one value per (body, room) from the identity
       seed and the room id (the surface's dealing law, `charter_surface`),
       byte-identical on replay and STABLE ACROSS BEATS -- the turn never
       enters the seed, so a body nobody has touched does not wander. Dealt
       among the cells the room's shape keeps that no anchor occupies (a
       body does not stand in the hearth); two bodies may share a cell, as
       two bodies may share an anchor.

FACING follows the same order: an authored ``facing`` where the station
carries one, else toward the anchor's wall for (i)-at and (ii) (the anchor's
own bearing), toward the doorway for (iii), and dealt for (iv) and for an
anchor with no bearing -- dealt, because a body at a table faces SOME way,
and `effective_facing`'s "never guessed" rule protects the Director's
declarations, of which there are none for a townsperson.

THE VIEW. `scene_with_charter_bodies` is a SHALLOW copy of the scene whose
``positions``, ``stations`` and ``orientation`` gain one derived row per
placed body, keyed by the body's display name -- the spelling every other
seam speaks (`background_presence_records`, `charter_carriers`) -- or by the
permanent uid ``charter:<charter>:<body>`` (`identity_seed`) when the display
name is AMBIGUOUS within the registry, because a name two people share is
withheld from every view (`background_presence_records`) and a positions
dict has one slot per key. The stored scene is never touched and the view is
never persisted: it exists for the length of one reader, exactly as the
derived crowd does (DESIGN_BACKGROUND_PRESENTATION Part B). Nothing about
the row is a fact the observer receives -- the row is what lets the
subtracting guards RUN: `visual_level_between` now finds a measured
station on both sides and asks `body_visibility` what stands between,
`light_at` reads the body's own cell, the sound field seats a listener at
its cell. The identity rules are untouched: the stranger label is still
`charter_surface`'s and a withheld name is keyed by a uid no label is ever
cut from.

WHAT IS NOT STORED, deliberately: no positions row, no station row, no
orientation row for an unpromoted body, ever. `place` stays the ONE owner of
the room; `station` on the body record is the one owner of the within-room
position when one has been authored; everything else is recomputed.

Pure: dicts in, dicts out. No database. The I/O that lands a Director's
placement on the registry is `charter_runtime.apply_scene_placements`.
"""

from __future__ import annotations

import hashlib

from .charter_identity import display_name, identity_aliases, identity_seed
from .charter_model import body_of_an_authored_mind
from .charter_move import en_route
from .spatial import (_BEARINGS, anchor_cells, door_anchor_id,
                      effective_anchors, normalize_bearing, normalize_cell,
                      room_field, room_grid, room_of)

#: The seed salt the dealing lanes fold in, so a placement lane can never
#: collide with a surface lane (`charter_surface._lane`) or a name lane
#: (`charter_identity._number`) drawn from the same identity seed.
_SALT = "place"

#: The four sources a placement can have, in the order they are tried.
SOURCES = ("authored", "post", "walk", "dealt")


def _lane(uid, room, lane):
    raw = hashlib.blake2b(
        f"{_SALT}:{uid}|{room}|{lane}".encode("utf-8"),
        digest_size=8).digest()
    return int.from_bytes(raw, "big")


def placement_uid(charter_key, body_key):
    """The permanent key a placement is filed under: `identity_seed`'s
    ``charter:<charter>:<body>``, the same spelling `persist.commit_background.
    _charter_uid_seed` keys a presence record on."""
    return identity_seed(str(charter_key), str(body_key))


def _roles_of(charter):
    roles = {}
    for post, holder in ((charter or {}).get("watch") or {}).items():
        roles.setdefault(str(holder), []).append(str(post))
    return roles


def _anchor_bearing(anchors, anchor_id):
    rec = (anchors or {}).get(anchor_id)
    return normalize_bearing(rec.get("dir")) if isinstance(rec, dict) else None


def _dealt_cell(scene, room, uid):
    """Rule (iv): a cell of the room's shape that no anchor occupies, dealt
    from (uid, room) and nothing else."""
    grid = room_grid(scene, room)
    taken = set()
    for rec in anchor_cells(scene, room).values():
        taken.update(tuple(c) for c in rec.get("cells") or ())
    free = sorted(c for c in grid.cells if c not in taken) or sorted(grid.cells)
    if not free:
        return grid.centre()
    cell = free[_lane(uid, room, 0) % len(free)]
    return grid.nearest(cell)


def _dealt_facing(uid, room):
    return _BEARINGS[_lane(uid, room, 1) % len(_BEARINGS)]


def _station_and_facing(scene, room, charter, body_key, body, uid, anchors):
    """``(station, facing, source)`` by the rule in the module note."""
    # (i) the body's own authored station.
    authored = body.get("station") if isinstance(body.get("station"), dict) \
        else None
    if authored:
        station = {}
        at = str(authored.get("at") or "")
        if at and at in anchors:
            station["at"] = at
        cell = normalize_cell(authored.get("cell"))
        if cell is not None:
            snapped = room_grid(scene, room).nearest(cell)
            station["cell"] = [snapped[0], snapped[1]]
        if authored.get("near"):
            station["near"] = [str(n) for n in authored["near"]]
        if station:
            facing = normalize_bearing(authored.get("facing"))
            if not facing and station.get("at"):
                facing = _anchor_bearing(anchors, station["at"])
            return station, facing or _dealt_facing(uid, room), "authored"
    # (ii) the post on watch, where it names a fixture of the room.
    posts = (charter or {}).get("posts") or {}
    for post_key in sorted(_roles_of(charter).get(str(body_key)) or ()):
        post = posts.get(post_key)
        if not isinstance(post, dict) or str(post.get("place") or "") != room:
            continue
        anchor = str(post.get("anchor") or "")
        if anchor and anchor in anchors:
            return ({"at": anchor},
                    _anchor_bearing(anchors, anchor) or _dealt_facing(uid, room),
                    "post")
    # (iii) mid-walk: at the doorway toward the next leg.
    if en_route(body):
        rec = body.get("walk") or {}
        route = [str(r) for r in rec.get("route") or ()]
        leg = int(rec.get("leg") or 0)
        nxt = route[leg + 1] if leg + 1 < len(route) else ""
        door = door_anchor_id(nxt) if nxt else ""
        if door and door in anchors:
            return ({"at": door},
                    _anchor_bearing(anchors, door) or _dealt_facing(uid, room),
                    "walk")
    # (iv) dealt.
    cell = _dealt_cell(scene, room, uid)
    return {"cell": [cell[0], cell[1]]}, _dealt_facing(uid, room), "dealt"


def charter_placements(registry, scene, *, frame_rooms=None):
    """``{uid: placement}`` for every unpromoted, undeparted, UNBOUND body
    of every charter whose ``place`` is a room the scene holds -- restricted
    to ``frame_rooms`` when given (the observer's room and the rooms
    `room_field` lays beyond its doorways; see `rooms_in_frame`).

    A placement row: ``uid`` (`placement_uid`), ``name`` (the display name),
    ``key`` (the spelling the view's positions row is filed under: the name
    when it is unique across the registry, else the uid), ``room``,
    ``station`` (``{"at": anchor}`` | ``{"cell": [x, y]}``, plus ``near``
    where authored), ``facing``, ``source`` (one of `SOURCES`), ``charter``,
    ``body``, ``presented`` (``"crowd"`` when a derived crowd of the body's
    institution carries it in this room, else ``"figure"``) and
    ``ambiguous`` (True when the name is shared).

    ``registry`` is the normalized registry shape (``{"items": {key:
    {"state": charter}}}``); `placements_from_slices` wraps
    `agents.common.chatter_inputs`' per-charter slices into it.
    """
    from .charter_crowd import CHARTER_CROWD_FLOOR, members_of

    rooms = (scene or {}).get("rooms") or {}
    wanted = None if frame_rooms is None else {
        str(r) for r in frame_rooms if str(r or "")}
    if not rooms or (wanted is not None and not wanted):
        return {}
    items = ((registry or {}).get("items") or {})
    candidates = []
    counts = {}
    for charter_key, item in sorted(items.items()):
        state = (item or {}).get("state") or {}
        roles = _roles_of(state)
        naming = state.get("naming")
        for body_key, body in sorted((state.get("bodies") or {}).items()):
            body = body if isinstance(body, dict) else {}
            if body_of_an_authored_mind(state, body_key, body):
                continue
            if body.get("departed"):
                continue
            room = str(body.get("place") or "")
            if room not in rooms or (wanted is not None and room not in wanted):
                continue
            name = display_name(body, roles.get(str(body_key)) or (), naming)
            counts[name.casefold()] = counts.get(name.casefold(), 0) + 1
            candidates.append((str(charter_key), str(body_key), body, room,
                               name, state))
    out = {}
    crowd_memo = {}
    for charter_key, body_key, body, room, name, state in candidates:
        uid = placement_uid(charter_key, body_key)
        anchors = effective_anchors(scene, room)
        station, facing, source = _station_and_facing(
            scene, room, state, body_key, body, uid, anchors)
        ambiguous = counts.get(name.casefold(), 0) != 1
        memo_key = (charter_key, room)
        if memo_key not in crowd_memo:
            members = members_of(state, room)
            crowd_memo[memo_key] = (
                set(members) if len(members) >= CHARTER_CROWD_FLOOR else set())
        out[uid] = {
            "uid": uid, "name": name,
            "key": uid if ambiguous else name,
            "room": room, "station": station, "facing": facing,
            "source": source, "charter": charter_key, "body": body_key,
            "presented": "crowd" if body_key in crowd_memo[memo_key]
            else "figure",
            "ambiguous": ambiguous,
        }
    return out


def placements_from_slices(slices, scene, *, frame_rooms=None):
    """`charter_placements` over `agents.common.chatter_inputs`' per-charter
    slices (each carrying ``key``, ``bodies``, ``watch``, ``posts``,
    ``naming``, ``bindings`` and the presentation sets `members_of` reads),
    so perception derives placements from the same once-per-stage fetch the
    derived crowd reads and the two cannot disagree about who is ground."""
    registry = {"items": {
        str(s.get("key") or ""): {"state": s}
        for s in (slices or ()) if isinstance(s, dict) and s.get("key")}}
    return charter_placements(registry, scene, frame_rooms=frame_rooms)


def rooms_in_frame(scene, rooms):
    """``rooms`` plus every room `room_field` lays beyond one of their
    doorways -- the whole of what an observer standing in any of them can
    have a line to, and therefore the only rooms whose bodies are ever laid
    (a 100-body town costs its observed rooms, never its back offices)."""
    out = []
    for room in rooms or ():
        room = str(room or "")
        if not room or room in out:
            continue
        out.append(room)
        field = room_field(scene, room)
        for other in (field.offsets if field else {}):
            other = str(other)
            if other not in out:
                out.append(other)
    return out


def lay_charter_bodies(scene, placements, *, keys=None):
    """Write the derived rows of ``placements`` onto ``scene`` IN PLACE --
    the stage's own fresh copy, never the store -- and return it.

    A body the scene already stands (`room_of` answers for its key: the
    Director minted an entity for it, or a registered character) is left
    alone entirely: the scene owns it, and re-keying it would put one being
    in the room twice. ``keys`` overrides the positions key per uid (a
    presence record's own spelling, which perception speaks).
    """
    positions = scene.setdefault("positions", {})
    stations = scene.setdefault("stations", {})
    orientation = scene.setdefault("orientation", {})
    for uid, placement in sorted((placements or {}).items()):
        key = str((keys or {}).get(uid) or placement.get("key") or "")
        if not key or room_of(scene, key):
            continue
        positions[key] = placement["room"]
        station = dict(placement.get("station") or {})
        if "cell" in station:
            station["cell"] = list(station["cell"])
        if station:
            stations[key] = station
        if placement.get("facing"):
            held = orientation.get(key)
            held = dict(held) if isinstance(held, dict) else {}
            held["facing"] = placement["facing"]
            orientation[key] = held
    return scene


def scene_with_charter_bodies(scene, placements, *, keys=None):
    """THE VIEW: a shallow copy of ``scene`` whose ``positions``,
    ``stations`` and ``orientation`` gain the derived rows of
    ``placements`` (`lay_charter_bodies`). The input is not touched -- the
    three ledgers are copied before they are written -- and nothing here is
    ever persisted."""
    viewed = dict(scene or {})
    for field in ("positions", "stations", "orientation"):
        held = viewed.get(field)
        viewed[field] = dict(held) if isinstance(held, dict) else {}
    return lay_charter_bodies(viewed, placements, keys=keys)


# ------------------------------------------------ the Director's placements

def _spelling_table(registry, rooms):
    """``{spelling: (charter, body)}`` for every unbound, undeparted body
    standing in ``rooms``, by every spelling it answers to -- the table
    `charter_runtime.charter_carriers` builds, with the uid and body key
    beside the names. A spelling two bodies share is nobody's."""
    table, clashes = {}, set()
    for charter_key, item in sorted(((registry or {}).get("items") or {}).items()):
        state = (item or {}).get("state") or {}
        roles = _roles_of(state)
        bindings = state.get("bindings") or {}
        for body_key, body in sorted((state.get("bodies") or {}).items()):
            body = body if isinstance(body, dict) else {}
            if body_key in bindings or body.get("departed"):
                continue
            if str(body.get("place") or "") not in rooms:
                continue
            ref = (str(charter_key), str(body_key))
            spellings = [str(body_key), placement_uid(charter_key, body_key),
                         str(body.get("name") or ""),
                         display_name(body, roles.get(body_key) or (),
                                      state.get("naming"))]
            spellings.extend(identity_aliases(
                body, roles.get(body_key) or (), state.get("naming")))
            for spelling in spellings:
                folded = " ".join(str(spelling or "").split()).casefold()
                if not folded:
                    continue
                if folded in table and table[folded] != ref:
                    clashes.add(folded)
                table.setdefault(folded, ref)
    for folded in clashes:
        table.pop(folded, None)
    return table


def resolve_scene_placements(registry, diff, scene):
    """Which of a Director diff's ``positions`` and ``stations`` entries name
    a charter body the scene does not stand, and what each one means for the
    registry. Pure; returns ``{"moves": [{charter, body, name, room}],
    "stations": [{charter, body, name, station}], "names": [spelling]}``
    where ``names`` are the diff keys the commit strips before the merge.

    THE ROUTING. The merge does not drop a positions entry whose key is in
    no ledger -- `merge_scene_with_diff` updates the position map blind --
    so before this a Director move of a townsperson landed as a SECOND
    positions row in the stored scene, disagreeing with the registry's
    ``place`` from the next beat on (the presence readers derive from the
    registry; `room_of` read the row). Routed instead: the room goes to the
    body's ``place`` through `charter_move.place_body`, the within-room
    entry to its ``station`` through `charter_move.station_body`, inside the
    commit's own transaction (`charter_runtime.apply_scene_placements`), and
    the scene keeps no row. A name the scene already stands (`room_of`
    answers) is the scene's and is left alone; a name no single body answers
    to is left for the merge to treat as it always has.

    A destination that is no room of the scene or of this beat's diff is not
    routed either: the merge and the movement floor own that refusal.
    """
    positions = (diff or {}).get("positions")
    stations = (diff or {}).get("stations")
    positions = positions if isinstance(positions, dict) else {}
    stations = stations if isinstance(stations, dict) else {}
    if not positions and not stations:
        return {"moves": [], "stations": [], "names": []}
    rooms = set((scene or {}).get("rooms") or {}) | set(
        (diff or {}).get("rooms") or {})
    table = _spelling_table(registry, rooms)
    if not table:
        return {"moves": [], "stations": [], "names": []}
    moves, routed_stations, names = [], [], []

    def _ref(name):
        if room_of(scene or {}, str(name)):
            return None
        return table.get(" ".join(str(name or "").split()).casefold())

    for name, dest in sorted(positions.items()):
        ref = _ref(name)
        if ref is None:
            continue
        dest = str(dest or "").strip()
        if not dest or dest not in rooms:
            continue
        moves.append({"charter": ref[0], "body": ref[1], "name": str(name),
                      "room": dest})
        names.append(str(name))
    for name, station in sorted(stations.items()):
        ref = _ref(name)
        if ref is None:
            continue
        if isinstance(station, str):
            station = {"at": station}
        elif isinstance(station, (list, tuple)):
            station = {"near": list(station)}
        if not isinstance(station, dict):
            continue
        routed_stations.append({"charter": ref[0], "body": ref[1],
                                "name": str(name), "station": dict(station)})
        if str(name) not in names:
            names.append(str(name))
    return {"moves": moves, "stations": routed_stations, "names": names}


__all__ = [
    "SOURCES", "charter_placements", "lay_charter_bodies", "placement_uid",
    "placements_from_slices", "resolve_scene_placements", "rooms_in_frame",
    "scene_with_charter_bodies",
]
