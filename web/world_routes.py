"""Typed HTTP boundary for the World Browser: the room index and the
per-room slice, read through `story/room_slice.py` -- the ONE reader the
Writers' Room's `inspect_rooms`, the frontier and the browser all share, so
a host and the Planner cannot be shown two different worlds -- and, since
2026-09-04, four NARROW writes so a host edits a field rather than a blob.

Reads (under ``/api/chats/{cid}/rooms``; ``frame_id`` absent or null is the
present, else a frame row of this chat, 404 otherwise -- the same contract
`app._era` gives the attire route):

* ``GET  ?frame_id=`` -> ``{frame_id, location, groups, bodies, vocab}``.
  ``groups`` is ``{cast, reachable, unreachable, retired}``, each a list of
  index rows in the index's own order (hops, then id); ``cast`` is every
  room a cast member stands in (hops 0); ``reachable`` every other room the
  walk from the cast reaches, live or planned; ``unreachable`` every
  unretired room it does not; ``retired`` the spent ids. Every row is the
  index row plus ``holder_name`` (the entity's display name when the room
  is the inside of a body), ``holder_room`` (where that body stands, for
  nesting) and ``occupants`` (the names `positions` place here).
  ``bodies`` is every body the scene knows -- cast, player, promoted
  presence, and a body the attire ledger dresses but nothing places -- each
  ``{name, kind, char_id, room, room_name, station, pose, attire}`` with the
  ledger AS STORED (`body_rows`), followed by the TOWNSPEOPLE the charter
  registry stands in a room of the scene (`charter_body_records`, since
  2026-09-05): ``kind`` ``"charter"``, ``name`` the display name or the
  permanent uid when the name is withheld (the view's own rule, never
  invented here), plus ``charter``, ``body``, ``uid``, ``source`` (one of
  `world.charter_place.SOURCES`), ``facing``, ``posts``, ``presented``,
  ``withheld``, ``authored`` (the body record's own station, or None) and a
  ``station`` DERIVED by the placement rule -- no pose, no attire, no
  ``char_id``. ``vocab`` is every closed set the browser offers as a
  select, read from the engine's own constants so a menu cannot drift from
  the code (`vocabulary`); ``body_kinds`` and ``charter_sources`` are the
  map's legend words.
* ``GET  /{room_id}?frame_id=`` -> the slice plus ``holder_name``,
  ``record`` (the room's stored editable fields: name, desc, notes, light,
  size, exposure, region, extent, shape, parts, anchors, adjacent -- the
  slice renders prose capped and exits derived, and an editor needs what
  is STORED -- plus ``geometry``, what the engine's grid makes of them:
  ``{w, d, shape, measured, size_derived, walls: {n, e, s, w: paces}}``,
  the wall counts being `RoomGrid.rim`'s, the number `wall_overfull`
  measures an anchor load against), ``stationable`` (the anchors a station
  may name here, authored and the implicit `door:<to>` ones --
  `world.spatial.effective_anchors`, the same set
  `normalize_scene_stations` keeps -- each with its bearing), ``region_look``
  (the region's `look` from the registry, '' when none) and ``lint`` (the
  layout-lint rows naming this room -- `world.spatial.room_layout_lint`,
  every standing row -- each the row plus ``field`` (`LINT_FIELDS`: the
  card field it concerns) and ``text`` (`layout_warning`)); 404 when no
  room of that id is known to the story. Index rows carry ``lint`` as the
  COUNT of rows naming the room, so the tree can mark it.
* ``GET  /{room_id}/grid?frame_id=`` -> the room's field AS THE ENGINE
  COMPUTES IT, for the map editor (`grid_view`; pure over the same functions
  sight and light run over -- `room_grid`, `anchor_cells`, `body_cell`,
  `room_field` -- so there is no second geometry): ``room`` ``{id, name, w,
  d, shape, measured, cells}``, ``rims`` ``{n, e, s, w: [cells]}`` (the
  cells that ARE each wall, in `RoomGrid.rim`'s order -- the order `offset`
  counts along), ``anchors`` ``{id: {cells, dir, height, footprint,
  opacity, desc, offset, cell, source}}`` (authored anchors; ``source`` is
  what placed it -- ``"cell"`` an authored origin cell, ``"offset"`` a place
  along its wall, ``"seed"`` the formula), ``doorways`` ``[{id, to,
  name, dir, cells, barrier, offset, status}]`` (the implicit door anchors,
  ``cells`` empty when the edge has no bearing to place it by), ``bodies``
  ``{name: {cell, facing, kind, at, near, measured, source}}`` (``cell``
  None and ``measured`` false for a body with no station -- somewhere in the
  room; ``source`` ``"cell"`` for the station's own pin, ``"anchor"`` for a
  cell derived from `at`/`near`, ``"none"``; a townsperson's entry is the
  `charter_body_records` record -- ``kind`` ``"charter"``, ``source`` the
  placement's, ``room`` the room it stands in, which is this one or a
  neighbour the field lays, since the observer's frame is what is placed),
  ``things`` ``[{id, name, kind, cell, anchor, placed}]``, ``walls`` (the
  field's wall lines, each ``{axis, coord, extent, aperture, to, name}``),
  ``neighbours`` ``[{id, name, offset, w, d, shape, cells, anchors}]``
  (every room `room_field` lays beyond a doorway, at the offset it lays it,
  its cells in ITS OWN frame), ``lint`` (the rows naming the room, as the
  slice carries them) and ``overlays`` -- ``{}`` today; the slot a sibling
  fills with ``{name: {"x,y": word}}`` per-cell readings (light, sound),
  which the map paints with a legend and this module never computes.
  404 when the room is not in the frame's scene (a planned room has no
  grid).
* ``GET /api/chats/{cid}/map?frame_id=`` -> the whole scene's rooms placed
  by bearing (`map_view` over `world.spatial.layout_rooms`, the lint's own
  embedding): ``components`` ``[{start, rooms: [{id, name, offset, w, d,
  shape, measured, cells, exits: [{to, name, dir, barrier, placed}],
  occupants, lint, holder, collided, onto, via}], collisions: [{room,
  onto, via}]}]``, one component per connected set of beared, non-wall
  edges, laid out from its smallest id. A room the bearings land on another
  is DRAWN at the offset it would have had (``collided`` true, ``onto`` the
  room it lands on, ``via`` the doorway it was reached through), never
  hidden.

Writes, each host-only and era-scoped exactly like the reads, each refused
with 409 while any pipeline of the chat runs (the same guard `world_put`
and the position route hold), each reading the scene through
`story.scene.get_scene`, applying the change under the SAME normalisers the
commit path runs (`normalize_scene_barriers`, `normalize_scene_bearings`,
`normalize_scene_stations` -- `world/spatial_merge.merge_scene_with_diff`'s
tail), writing it through `wset` as `attire_put` does, and reconciling the
`room_registry` projection through `persist.commit
.sync_room_registry_with_scene` -- the rule every scene writer keeps
(`AGENTS.md`):

* ``PATCH /{room_id}`` with a body of ONLY the changed fields. ``name``,
  ``desc``, ``notes`` are text (an empty ``name`` is refused: the id needs a
  label); ``light`` / ``size`` / ``exposure`` are refused outside their sets
  with a message naming the set, and an empty string CLEARS the field
  (absent means the engine's default, which is what the word means);
  ``region`` is free text folded to a region id, empty clearing it;
  ``extent`` is ``{w, d}`` in paces, clamped by the engine's own
  `normalize_extent` to [`EXTENT_MIN_PACES`, `EXTENT_MAX_PACES`], refused
  when it is not a measurement, null/empty clearing it -- and setting one
  writes the ``size`` tier it implies (`size_from_extent`), since the card
  shows size as DERIVED while an extent stands; ``shape`` is a `SHAPES`
  word (empty clears: the rectangle); ``parts`` is the full list of
  ``{w, d, at}`` for an `l`, ``at`` refused outside `ROOM_CORNERS`, run
  through `normalize_parts`; ``exits`` and ``anchors`` are FULL replacement
  lists for this room. An
  exit is ``{to, barrier, dir?, offset?}``; a doorway is one object, so the
  far room's reciprocal edge is written too -- created when missing, its
  barrier set when it stands (every barrier but `one_way_window`, which is
  asymmetric by design), its ``dir`` the opposite bearing, its ``offset``
  the same fraction (a wall's start is the same end from either room), and
  REMOVED when the exit is (`_mirror_symmetric_barriers` in
  `world/spatial_merge.py` is the merge's statement of the same rule;
  `Design.md`'s "One doorway, one barrier"). Fields an edge carried that the
  browser does not edit (`distance`, `passage_from`, ...) survive on the
  edge that keeps its ``to``. Anchors are ``{anchor_id: {desc, dir?,
  height?, footprint?, opacity?, offset?, cell?}}``; an anchor without an
  id is keyed by its folded desc; the geometry words are refused outside
  `HEIGHTS` / `FOOTPRINTS` / `OPACITIES`. ``offset`` -- on an anchor or an
  exit -- is where along its wall the thing stands, a number in [0, 1] from
  the wall's start (`world.spatial.normalize_offset`; the map editor's
  drag writes it), refused outside the range naming it, null or '' clearing
  it back to the seeded placement. ``cell`` -- on an anchor -- is its ORIGIN
  cell ``[x, y]`` in the room's own grid (the west-most, north-most cell of
  its footprint; the map editor's drop on any cell writes it, the owner's
  ruling of 2026-09-04), refused outside the room's cells naming the
  bounds (`_cell_or_400`), null clearing it. ``cell`` and ``offset`` are
  exclusive: a cell written clears the offset. Returns the fresh slice (as
  the GET shapes it) so the card re-renders without a second fetch.
* ``PATCH /{room_id}/entities/{entity_id}`` for a thing standing in the
  room: ``kind``, ``description`` (text), ``portable`` (bool),
  ``light_source`` (a `LIGHT_LEVELS` word, empty clearing it), ``lit`` (bool
  -> ``state.lit``; null clears), ``room`` (a live room id to move the
  thing's position row to; a thing placed only as an anchor is not moved --
  the anchor editor is where it lives). Returns the fresh slice.
* ``PUT  /bodies/{name}/station`` with ``{at, near, cell}``: ``at`` must be
  an anchor the body's room holds (`effective_anchors`; the refusal names
  them) or null; ``near`` names bodies standing in the same room; ``cell``
  is ``[x, y]`` in the room's own grid, refused outside the room's cells
  naming the bounds (`_cell_or_400`), null or absent for no pin -- the map
  editor's placement on ANY cell (the owner, 2026-09-04), for the player
  and a presence as much as the cast, since it never changes the room. A
  station field the route does not own (`cover`) rides through. Returns
  the body's row.
* ``PATCH /api/chats/{cid}/regions/{region_id}`` with ``{look}``: the
  region's visual register, written through `world.regions.set_region_look`
  into the frame's registry (not the scene, so no registry projection to
  reconcile); an empty look removes it. Shared by every room in the region
  by construction. Returns ``{id, name, brief, look, rooms}``.
* ``PUT /api/chats/{cid}/charters/{charter}/bodies/{body}/station`` with
  ``{room, at?, cell?, facing?}`` and ``DELETE`` of the same: a
  TOWNSPERSON'S place, written on the charter registry and never the scene
  (`charter_body_station_put` / `charter_body_station_delete`, 2026-09-05):
  the room through `world.charter.place_body`, the within-room station
  through `station_body`, both landed by `registry_for_update` +
  `save_registry` for the chat's frame. Refused naming the reason when the
  room is not live, the cell is outside the room (the bounds named, never
  clamped), the anchor is not the room's, the body is bound, reserved or
  departed, the charter or body is unknown (404), or a pipeline runs (409).
  The DELETE clears the authored station, back to the post's anchor, the
  walk's doorway or the dealt cell. Returns the body's row read back
  through the placement.

Since 2026-09-05 (the owner, on the map editor: "This room editor feels very
incomplete") the editor CREATES, REMOVES and MOVES, each a narrow typed
write with the same guards, each refusal naming its reason
(`docs/design/DESIGN_ROOM_FIDELITY.md` §5, §11):

* ``POST /api/chats/{cid}/rooms`` ``{name, from?, dir?, barrier?, extent?,
  shape?, region?}`` -> the new room's slice plus ``id`` (minted from the
  name, never an id the scene or the registry holds; joined to ``from`` by
  ONE doorway -- a passage record and both edges -- its region the joined
  room's unless said otherwise).
* ``DELETE /api/chats/{cid}/rooms/{room_id}`` -> ``{removed, retired}``;
  REFUSED while any body or thing stands in the room, each named; every
  edge into it and every passage naming it go with it; the registry
  retires the id through `sync_room_registry_with_scene`.
* ``POST /rooms/{room_id}/entities`` ``{name, kind?, description?, cell?}``
  mints a thing standing here by a position row (pinned when ``cell``);
  ``DELETE /rooms/{room_id}/entities/{entity_id}`` removes one (an
  anchor-placed thing and a body are refused).
* ``POST /rooms/{room_id}/presences`` ``{name, cell?}`` places a presence
  (a position row, nothing else minted; refused when the name already
  stands somewhere or is the player's or a cast member's).
* ``DELETE /api/chats/{cid}/bodies/{name}`` removes a presence (the player,
  the cast and a thing are refused); ``PUT /bodies/{name}/room`` ``{room}``
  moves ANY body, dropping its station ``cell`` and a pose detail holding
  another body on a change of room; ``PUT /bodies/{name}/pose`` writes the
  six `_POSE_FIELDS` through `_clean_pose`.
* The doorways router, ``/api/chats/{cid}/doorways``: ``POST`` ``{room, to,
  barrier?, dir?, offset?, name?, material?, width?}`` opens ONE doorway (a
  passage record, `scene.passages[id]`, and both edges naming it);
  ``PATCH /{room}/{to}`` edits it as one object from EITHER room (`DOORWAY_FIELDS`;
  a doorway declared from the far side alone gets its record minted from
  the standing edge and this side's edge with it); ``DELETE /{room}/{to}``
  closes it. ``width`` is whole paces in [1, `DOORWAY_MAX_WIDTH`].
* ``POST /api/chats/{cid}/regions`` ``{name}`` enters a region (idempotent);
  the regions ``PATCH`` also takes ``{name}`` to rename one (the id every
  room carries stays).
* The entity PATCH gained the source fields the light and sound fields read:
  ``light_shape`` (`LIGHT_SHAPES`), ``light_height`` (`LIGHT_HEIGHTS`; a
  ceiling light is `full` and casts no shadow), ``steadiness``
  (`STEADINESS`), ``sound_source`` (`SOUND_LEVELS`), ``running`` and
  ``pointed_at`` (a bearing, an anchor of the room or an entity of the
  scene, refused outside those classes). Moving a thing drops its station.
* The room PATCH's ``parts`` take ``at`` as a corner word OR an origin cell
  ``[x, y]``; a cell part outside the box is refused naming the box;
  ``shape`` may be `composite`.
* ``GET /{room_id}/grid?sound_from=`` now carries ``overlays`` (``light``,
  ``noise``, and ``sound`` for the chosen source), ``sound_sources`` and
  ``light_sources`` (`_overlays`, through the composer's own readers);
  doorways carry ``passage``, ``label``, ``material``, ``width``, ``state``
  and ``declared_here``; things carry ``source``. ``GET /map`` exits carry
  ``cells`` (the door's cells in the room's frame) and ``passage``; rooms
  carry ``region`` and ``placed_via`` (the room each was laid out from).

Attire is NOT written here: the browser's attire editor sends the whole
ledger to `app.attire_put`, which re-derives every entry
(`story.attire.rederive_entry`) -- one writer, one derivation.

Host-only by construction: nothing here is in `GUEST_ALLOWED_API_PATHS`.
The slice is author knowledge -- planned stubs, package operations, another
body's whole attire ledger -- and reaches no mind (`story/room_tools.py`).
"""

from __future__ import annotations

import copy
import json
from contextlib import contextmanager

from fastapi import APIRouter, Body, HTTPException

from core import db
from core.db import q, transaction, wset
from persist.commit import sync_room_registry_with_scene
from story import room_slice as rooms
from story.attire import (GARMENT_STATES, REGIONS as ATTIRE_REGIONS,
                          entry_for as attire_entry_for)
from story.character_schema import character_name, persona_name
from story.scene import get_scene, persona_of
from world.spatial import (
    _BEARINGS, _DOOR_ANCHOR_PREFIX, _EYE_RANK, _PART_SHAPES, _POSE_FIELDS,
    _VALID_BARRIERS, _clean_pose, _door_cells, EXTENT_MAX_PACES,
    EXTENT_MIN_PACES, FOOTPRINTS, HEIGHTS, LAYOUT_LINT_KINDS, LIGHT_HEIGHTS,
    LIGHT_LEVELS, LIGHT_SHAPES, OPACITIES, ROOM_CORNERS, ROOM_SIZES, SHAPES,
    SOUND_LEVELS, STEADINESS, anchor_cells, body_cell,
    body_cell_source,
    effective_adjacent, effective_anchors, effective_facing,
    effective_station, invalidate_moved_body_pose_details, layout_rooms,
    layout_warning, light_field, noise_word, normalize_barrier,
    normalize_bearing, normalize_cell, normalize_extent, normalize_offset,
    normalize_part_at, normalize_parts,
    normalize_room_id, normalize_scene_anchor_cells, normalize_scene_barriers,
    normalize_scene_bearings, normalize_scene_passages,
    normalize_scene_stations, normalize_shape, normalize_vertical,
    opposite_bearing, opposite_vertical, part_box, passage_id_for, passage_of,
    quantise_hearing,
    room_field, room_grid, room_layout_lint, room_of, scene_passages,
    size_from_extent, sound_field, sync_scene_passages,
)
from world.weather import EXPOSURES
# The townspeople (`world/charter_place.py`, DESIGN_CHARTER_PLACEMENT § the
# map): the placement read through the charter facade, the two authoring
# seams the drag lands on, and the registry chokepoints they go through.
from world.charter import (
    PLACEMENT_SOURCES, body_of_an_authored_mind, charter_placements,
    place_body, placement_uid, rooms_in_frame, scene_with_charter_bodies,
    station_body)
from world.charter_runtime import registry_for, registry_for_update, save_registry

router = APIRouter(prefix="/api/chats/{cid}/rooms", tags=["world-browser"])

#: The display groups, in the order the browser lists them.
GROUPS = ("cast", "reachable", "unreachable", "retired")

#: The room fields the browser edits as text. `name` is required non-empty.
TEXT_FIELDS = ("name", "desc", "notes")

#: The room fields that are a word from a closed set the engine owns, each
#: with its set. An empty string clears the field.
ROOM_ENUMS = {"light": LIGHT_LEVELS, "size": ROOM_SIZES, "exposure": EXPOSURES}

#: The anchor geometry words and their sets (`world/spatial_fov.py` owns them).
ANCHOR_ENUMS = {"height": HEIGHTS, "footprint": FOOTPRINTS, "opacity": OPACITIES}

#: The card field each layout-lint row concerns, so the browser shows a row
#: beside the field it is about and never has to know a kind by name. Keyed
#: by every `LAYOUT_LINT_KINDS` word (`tests/test_world_routes.py` pins the
#: coverage): a bearing or a placement row is about the doorways, a wall
#: row about what stands on the wall, a shape row about the shape, and the
#: two extent rows about the measurement.
LINT_FIELDS = {
    "reciprocal_bearing_disagrees": "exits",
    "rooms_overlap_when_placed": "exits",
    "openings_overlap": "exits",
    "wall_overfull": "anchors",
    "corner_in_round_room": "shape",
    "l_part_redundant": "shape",
    "parts_disconnected": "shape",
    "shape_disconnected": "shape",
    "size_disagrees_with_extent": "extent",
    "extent_unreadable": "extent",
}
assert set(LINT_FIELDS) == set(LAYOUT_LINT_KINDS)

#: The straight walls, in the order the browser lists them; the corners
#: follow (`ROOM_CORNERS`), then the anchors with no bearing.
WALLS = ("n", "e", "s", "w")

#: The barrier that is asymmetric BY DESIGN and is never mirrored onto the far
#: room's edge (`_mirror_symmetric_barriers` holds the same exception).
_ASYMMETRIC_BARRIER = "one_way_window"


@contextmanager
def _era(cid: int, frame_id):
    """Scope the scene read to one era, as `app._era` does for the attire
    route: validate that the frame is this chat's, then set the ambient
    `active_frame_id` so `get_scene` lands on that era's blob."""
    if frame_id is not None:
        row = q("SELECT id FROM frames WHERE id=? AND chat_id=?",
                (int(frame_id), int(cid)), one=True)
        if row is None:
            raise HTTPException(404, f"Frame {frame_id} not found")
    token = db.active_frame_id.set(
        int(frame_id) if frame_id is not None else None)
    try:
        yield
    finally:
        db.active_frame_id.reset(token)


def _chat_or_404(cid: int):
    chat = q("SELECT * FROM chats WHERE id=?", (cid,), one=True)
    if not chat:
        raise HTTPException(404, "Chat not found")
    return dict(chat)


def _require_idle(cid: int):
    """The pipeline reads and rewrites the scene throughout a turn; a field
    edit underneath a running one would be corrupted or silently overwritten
    by the commit. `app._require_chat_idle`'s rule over the same registry
    (`agents.runtime.ABORTS`), stated here because `web.app` imports this
    module and cannot be imported back at module load."""
    from agents.runtime import ABORTS
    if any(key[0] == cid for key in list(ABORTS)):
        raise HTTPException(
            409,
            "This chat still has an active pipeline. Abort it and wait for "
            "the aborted response before editing the world.")


def _holder_name(scene, holder):
    """The display name of the body a room is inside of -- the scene
    entity's `name` when it has one, else the id the room recorded."""
    if not holder:
        return None
    entity = (scene.get("entities") or {}).get(str(holder))
    if isinstance(entity, dict) and str(entity.get("name") or "").strip():
        return str(entity["name"]).strip()
    return str(holder)


def _is_body(scene, who):
    """The ONE body predicate (review 2026-09-07 A56).

    This was a third spelling of it -- a position row keyed by an entity of
    an inanimate kind places a thing, anything else is a body -- and it
    answered the same as the shared ladder for every kind but one: a subject
    the scene DRESSES or gives a size to, whose entity record calls it a
    box, is a body by its wardrobe and was a thing here. `scene_names_body`
    reads the body ledgers first and the entity record second, which is the
    order that settles it.
    """
    from world.spatial import scene_names_body

    return scene_names_body(scene, str(who))


def _lint_rows(scene):
    """Every standing layout row of the scene (`room_layout_lint` with no
    previous scene: the standing state, as the Room's `inspect_contradictions`
    reads it), each carrying the room ids it names under `rooms` so a caller
    can file it, the card field it concerns (`LINT_FIELDS`) and its sentence
    (`layout_warning`)."""
    out = []
    for row in room_layout_lint(scene):
        named = [str(r) for r in (row.get("rooms") or [])]
        if row.get("room") is not None:
            named.append(str(row["room"]))
        out.append({**row, "rooms": named,
                    "field": LINT_FIELDS.get(row.get("kind")),
                    "text": layout_warning(row)})
    return out


def _room_lint(rows, room_id):
    """The rows naming one room, in the lint's own order."""
    return [dict(r) for r in rows if str(room_id) in (r.get("rooms") or [])]


def _occupants(scene):
    """``{room_id: [names]}`` -- the BODIES each room holds, by the rule
    `cast_rooms` counts the cast with: a position row keyed by a scene entity
    of an inanimate kind places a thing (the slice lists it under `things`),
    and a row with no entity record behind it, or an animate one, is a body.
    Read by the tree's rows and the structure map alike."""
    occupants = {}
    for who, room in (scene.get("positions") or {}).items():
        if not str(room or "") or not _is_body(scene, who):
            continue
        occupants.setdefault(str(room), []).append(str(who))
    return occupants


#: The kinds a body on the map can be. The first three are the scene's
#: (`_body_kind`); `charter` is a townsperson the registry stands in the room
#: (`charter_body_records`), whose position is derived and never stored.
#: Offered to the browser as `vocab.body_kinds` so its legend cannot drift.
BODY_KINDS = ("player", "cast", "presence", "charter")
CHARTER_KIND = BODY_KINDS[3]


def _body_kind(name, player, cast):
    """player | cast | presence: the player by the persona's name, the cast
    by the registered sheets (`_cast_ids`), anyone else a presence. A
    townsperson is never asked here: it is not in `positions`, and its kind
    is `CHARTER_KIND` by construction."""
    key = str(name).strip().casefold()
    if key == str(player or "").strip().casefold():
        return "player"
    if key in (cast or {}):
        return "cast"
    return "presence"


def group_rows(index_rows, scene, lint_rows=None):
    """Sort index rows into the four display groups, each keeping the
    index's order, and decorate every row for display. Pure over its inputs
    so the grouping is testable without a request. `lint_rows` (the shape
    `_lint_rows` returns) puts the count of layout rows naming each room on
    its row as `lint`, so the tree can mark it."""
    occupants = _occupants(scene)
    groups = {key: [] for key in GROUPS}
    for row in index_rows:
        row = dict(row)
        holder = row.get("holder")
        row["holder_name"] = _holder_name(scene, holder)
        row["holder_room"] = rooms.holder_room(scene, holder) if holder else None
        row["occupants"] = list(occupants.get(row["id"], []))
        row["lint"] = len(_room_lint(lint_rows or [], row["id"]))
        if row["status"] == rooms.STATUS_RETIRED:
            groups["retired"].append(row)
        elif row["hops"] == 0:
            groups["cast"].append(row)
        elif row["hops"] is None:
            groups["unreachable"].append(row)
        else:
            groups["reachable"].append(row)
    return groups


def vocabulary(cid, frame_id):
    """Every closed set the browser offers, from the engine's own constants.
    `regions` is the map's known regions (`world.regions.region_registry`,
    for a datalist -- a region is free text that folds to an id, not a
    closed set); every other key is a set the engine refuses values outside
    of."""
    from world.regions import region_registry
    registry = region_registry(cid, frame_id)
    return {
        "light": list(LIGHT_LEVELS),
        "size": list(ROOM_SIZES),
        "exposure": list(EXPOSURES),
        "barriers": sorted(_VALID_BARRIERS),
        "dirs": list(_BEARINGS),
        "heights": list(HEIGHTS),
        "footprints": list(FOOTPRINTS),
        "opacities": list(OPACITIES),
        "shapes": list(SHAPES),
        "corners": list(ROOM_CORNERS),
        "part_shapes": list(_PART_SHAPES),
        "walls": list(WALLS),
        "extent": {"min": EXTENT_MIN_PACES, "max": EXTENT_MAX_PACES},
        # A thing's light and sound (`world/spatial_light_field.py`,
        # `world/spatial_sound_field.py`): the four closed sets a source is
        # authored in, and the sound ladder.
        "light_shapes": list(LIGHT_SHAPES),
        "light_heights": list(LIGHT_HEIGHTS),
        "steadiness": list(STEADINESS),
        "sound_levels": list(SOUND_LEVELS),
        # A body's pose: the fields (`spatial_geometry._POSE_FIELDS`, open
        # prose each) and the posture words the geometry reads an eye height
        # from (`spatial_fov._EYE_RANK`), offered as suggestions, never
        # refused outside -- a posture is prose.
        "pose_fields": list(_POSE_FIELDS),
        "postures": list(_EYE_RANK),
        "regions": [{"id": rid, "name": str(entry.get("name") or rid),
                     "look": str(entry.get("look") or "")}
                    for rid, entry in sorted(registry.items())],
        "attire_regions": list(ATTIRE_REGIONS),
        "garment_states": list(GARMENT_STATES),
        # A body's kind on the map (`BODY_KINDS`) and, for a townsperson,
        # what placed it (`world.charter_place.SOURCES`, in the order the
        # rule tries them: authored station, post anchor, walk doorway,
        # dealt cell) -- so the legend's words are the engine's.
        "body_kinds": list(BODY_KINDS),
        "charter_sources": list(PLACEMENT_SOURCES),
    }


def _cast_ids(cid):
    """``{folded name: char_id}`` for the registered cast of the story."""
    out = {}
    for row in q("SELECT cc.char_id AS id, COALESCE(cc.sheet, ch.sheet) AS sheet "
                 "FROM chat_chars cc JOIN characters ch ON ch.id = cc.char_id "
                 "WHERE cc.chat_id=?", (cid,)):
        try:
            name = character_name(json.loads(row["sheet"] or "{}"))
        except (TypeError, ValueError):
            continue
        if name:
            out[name.strip().casefold()] = int(row["id"])
    return out


def charter_body_records(cid, frame_id, scene, frame_rooms=None):
    """``{key: record}`` for every townsperson the registry stands in a room
    of ``scene`` -- restricted to ``frame_rooms`` when given -- READ THROUGH
    THE PLACEMENT MODULE: `charter_placements` says where each stands and
    why, `scene_with_charter_bodies` lays the rows on a view, and the cell,
    facing and station are then read off that view with the same functions
    `grid_view` reads a cast body with (`body_cell`, `effective_facing`,
    `effective_station`), so there is no second derivation of a position.

    The key is the placement's own: the display name where it is unique
    across the registry, else the permanent uid ``charter:<charter>:<body>``
    -- a name two people share is WITHHELD from every view
    (`background_presence_records`), and this module invents none. A record
    is ``{cell, facing, kind: "charter", at, near, measured, source, room,
    charter, body, uid, withheld, posts, presented, station, authored}``:
    ``source`` one of `PLACEMENT_SOURCES`, ``posts`` the watch posts the body
    holds, ``station`` the placement's ``{at}`` | ``{cell}`` (plus ``near``
    where authored), ``authored`` the body record's own station or None (what
    a clear returns from, so Undo can put it back exactly). A body the scene
    already stands under the same spelling (`room_of` answers: the Director
    minted an entity for it) is the scene's, and is left to `positions`.
    Empty -- and no registry parse beyond the cached one -- for a story with
    no charters, so every other story's views are byte-identical."""
    registry = registry_for(cid, frame_id)
    placements = charter_placements(registry, scene, frame_rooms=frame_rooms)
    if not placements:
        return {}
    view = scene_with_charter_bodies(scene, placements)
    items = registry.get("items") or {}
    out = {}
    for uid, placement in sorted(placements.items()):
        key = str(placement.get("key") or "")
        if not key or room_of(scene, key):
            continue
        state = ((items.get(placement["charter"]) or {}).get("state") or {})
        posts = sorted(str(post) for post, holder
                       in (state.get("watch") or {}).items()
                       if str(holder) == str(placement["body"]))
        body = (state.get("bodies") or {}).get(placement["body"]) or {}
        authored = body.get("station") if isinstance(body.get("station"), dict) else None
        cell = body_cell(view, key)
        station = effective_station(view, key)
        out[key] = {
            "cell": [int(cell[0]), int(cell[1])] if cell else None,
            "facing": effective_facing(view, key),
            "kind": CHARTER_KIND,
            "at": station.get("at") or None,
            "near": [str(n) for n in (station.get("near") or [])],
            "measured": cell is not None,
            "source": str(placement.get("source") or ""),
            "room": str(placement["room"]),
            "charter": str(placement["charter"]), "body": str(placement["body"]),
            "uid": str(uid), "withheld": bool(placement.get("ambiguous")),
            "posts": posts, "presented": str(placement.get("presented") or ""),
            "station": dict(placement.get("station") or {}),
            "authored": dict(authored) if authored else None,
        }
    return out


def body_rows(cid, chat, scene, charter=None):
    """Every body the scene knows, for the Bodies tab: the bodies `positions`
    place (by `cast_rooms`'s rule), the player whether placed or not, and any
    body the attire ledger dresses that nothing places (offscreen, but
    dressed). Ordered player first, then by name. ``charter``
    (`charter_body_records`) appends the townspeople after them, under their
    own kind, each with its room, its posts and its derived station -- no
    pose, no attire: those ledgers are the scene's, and a townsperson has no
    row in either."""
    rooms_ = scene.get("rooms") or {}
    positions = scene.get("positions") or {}
    stations = scene.get("stations") if isinstance(scene.get("stations"), dict) else {}
    poses = scene.get("poses") if isinstance(scene.get("poses"), dict) else {}
    attire = scene.get("attire") if isinstance(scene.get("attire"), dict) else {}
    player = str(persona_name(persona_of(chat)) or "").strip()
    cast = _cast_ids(cid)

    names = []
    seen = set()

    def add(name):
        key = str(name).strip().casefold()
        if key and key not in seen:
            seen.add(key)
            names.append(str(name))

    if player:
        add(player)
    for who, room in positions.items():
        if str(room or "") and _is_body(scene, who):
            add(who)
    for who in attire:
        add(who)

    out = []
    for name in names:
        key = name.strip().casefold()
        room = room_of(scene, name)
        room_def = rooms_.get(room) if room else None
        out.append({
            "name": name,
            "kind": _body_kind(name, player, cast),
            "char_id": cast.get(key),
            "room": room or None,
            "room_name": (str(room_def.get("name") or room)
                          if isinstance(room_def, dict) else room),
            "station": stations.get(name),
            "pose": poses.get(name),
            # `entry_for`: `names` is built from positions as well as from
            # the wardrobe, so the spelling in hand need not be the ledger's
            # (review 2026-09-07 B5).
            "attire": attire_entry_for(attire, name) or None,
        })
    out.sort(key=lambda b: (b["kind"] != "player", b["name"].casefold()))
    for key, rec in sorted((charter or {}).items(), key=lambda kv: kv[0].casefold()):
        room_def = rooms_.get(rec["room"])
        out.append({
            "name": key, "kind": CHARTER_KIND, "char_id": None,
            "room": rec["room"],
            "room_name": (str(room_def.get("name") or rec["room"])
                          if isinstance(room_def, dict) else rec["room"]),
            "station": dict(rec.get("station") or {}),
            "pose": None, "attire": None,
            "charter": rec["charter"], "body": rec["body"], "uid": rec["uid"],
            "source": rec["source"], "facing": rec.get("facing"),
            "posts": list(rec.get("posts") or []), "presented": rec.get("presented"),
            "withheld": bool(rec.get("withheld")),
            "authored": dict(rec["authored"]) if rec.get("authored") else None,
        })
    return out


@router.get("")
def rooms_index(cid: int, frame_id: int | None = None):
    chat = _chat_or_404(cid)
    with _era(cid, frame_id):
        scene = rooms.read_scene(cid)
        index = rooms.room_index(cid, frame_id, scene)
        bodies = body_rows(cid, chat, scene,
                           charter=charter_body_records(cid, frame_id, scene))
        vocab = vocabulary(cid, frame_id)
        lint = _lint_rows(scene)
    return {
        "frame_id": frame_id,
        "location": str(scene.get("location") or ""),
        "groups": group_rows(index, scene, lint),
        "bodies": bodies,
        "vocab": vocab,
    }


def _geometry(scene, room_id, room):
    """What the room's stored measurement comes to, by the engine's own
    grid (`room_grid`): the box in paces, whether it is MEASURED (an extent
    stands) or the size tier's square, the tier the extent implies
    (`size_from_extent`, None without one), and how many paces each straight
    wall has -- `RoomGrid.rim`, the same count `wall_overfull` compares an
    anchor load against, so the card shows a wall's room before the lint
    says it ran out."""
    grid = room_grid(scene, room_id)
    return {
        "w": grid.w, "d": grid.d, "shape": grid.shape,
        "measured": bool(grid.measured),
        "size_derived": size_from_extent(room.get("extent")),
        "walls": {wall: len(grid.rim(wall)) for wall in WALLS},
    }


def _record(scene, room_id, room):
    """The room's stored editable fields, for the card's inputs, plus the
    `geometry` the engine derives from them."""
    room = room if isinstance(room, dict) else {}
    anchors = room.get("anchors") or {}
    if isinstance(anchors, (list, tuple)):
        anchors = {str(a): {"desc": str(a)} for a in anchors if str(a)}
    return {
        "name": str(room.get("name") or ""),
        "desc": str(room.get("desc") or room.get("description") or ""),
        "notes": str(room.get("notes") or ""),
        "light": str(room.get("light") or ""),
        "size": str(room.get("size") or ""),
        "exposure": str(room.get("exposure") or ""),
        "region": str(room.get("region") or ""),
        # The measurement as the engine reads it: an unreadable stored extent
        # is None here (the lint row `extent_unreadable` says what it was),
        # an unknown shape word is the rectangle it is read as.
        "extent": normalize_extent(room.get("extent")),
        "shape": normalize_shape(room.get("shape")) if room.get("shape") else "",
        "parts": normalize_parts(room.get("parts")),
        "geometry": _geometry(scene, room_id, room),
        "anchors": {str(aid): dict(a) for aid, a in anchors.items()
                    if isinstance(a, dict)},
        "adjacent": [dict(e) for e in (room.get("adjacent") or [])
                     if isinstance(e, dict) and e.get("to")],
    }


def _region_look(cid, frame_id, region_id):
    """The region's `look` from the registry, '' when it has none."""
    if not region_id:
        return ""
    from world.regions import region_registry
    entry = region_registry(cid, frame_id).get(str(region_id)) or {}
    return str(entry.get("look") or "")


def _decorated_slice(cid, frame_id, room_id, scene, lint_rows=None):
    row = rooms.room_slice(cid, frame_id, room_id, scene)
    if row is None:
        return None
    row["holder_name"] = _holder_name(scene, row.get("holder"))
    # The region's look rides the card because the card is where a host
    # meets the region; it is the REGION's field, shared by every room there,
    # and is written through the regions route, never the room PATCH.
    row["region_look"] = _region_look(cid, frame_id, row.get("region"))
    room = (scene.get("rooms") or {}).get(room_id)
    if isinstance(room, dict):
        row["record"] = _record(scene, room_id, room)
        row["stationable"] = [
            {"id": str(aid), "desc": str((a or {}).get("desc") or aid),
             "implicit": bool((a or {}).get("implicit")),
             "dir": normalize_bearing((a or {}).get("dir"))}
            for aid, a in effective_anchors(scene, room_id).items()]
        # The layout rows naming this room, each with the card field it
        # concerns and its sentence, so the card puts a row beside the field
        # it is about rather than in a list at the bottom.
        row["lint"] = _room_lint(
            lint_rows if lint_rows is not None else _lint_rows(scene), room_id)
    else:
        row["record"] = None
        row["stationable"] = []
        row["lint"] = []
    # Each thing's stored editable fields, and HOW it is placed here: by a
    # position row (movable) or as one of the room's anchors (the anchor
    # editor's business).
    entities = scene.get("entities") or {}
    for thing in row.get("things") or []:
        ent = entities.get(thing["id"])
        ent = ent if isinstance(ent, dict) else {}
        thing["record"] = {
            "kind": str(ent.get("kind") or ""),
            "description": str(ent.get("description") or ""),
            "portable": bool(ent.get("portable")),
            "light_source": str(ent.get("light_source") or ""),
            # The source fields the light and sound fields read
            # (`world/spatial_light_field.py`, `world/spatial_sound_field.py`):
            # as stored, '' for absent; `state` carries `lit`, `pointed_at`,
            # `running`.
            "light_shape": str(ent.get("light_shape") or ""),
            "light_height": str(ent.get("light_height") or ""),
            "steadiness": str(ent.get("steadiness") or ""),
            "sound_source": str(ent.get("sound_source") or ""),
            "state": ent.get("state") if isinstance(ent.get("state"), dict) else {},
        }
        thing["placed"] = "position" if room_of(scene, thing["id"]) else "anchor"
    return row


@router.get("/{room_id}")
def rooms_slice(cid: int, room_id: str, frame_id: int | None = None):
    _chat_or_404(cid)
    with _era(cid, frame_id):
        scene = rooms.read_scene(cid)
        row = _decorated_slice(cid, frame_id, room_id, scene)
    if row is None:
        raise HTTPException(404, f"No room '{room_id}' in this story")
    return row


# ---------------------------------------------------------------------------
# The map editor's two reads: one room's grid, and the scene placed by bearing
# ---------------------------------------------------------------------------

def _cells(cells):
    """Cells as JSON lists, in one order, so two reads of one room agree."""
    return [[int(x), int(y)] for x, y in sorted(cells)]


def _room_name(scene, room_id):
    room = (scene.get("rooms") or {}).get(room_id)
    if isinstance(room, dict) and str(room.get("name") or "").strip():
        return str(room["name"]).strip()
    return str(room_id)


def grid_view(scene, room_id, lint_rows, *, player="", cast=None, things=(),
              sound_from=None, charter=None):
    """One room's field exactly as the engine computes it -- the module
    docstring gives the shape. Pure over the scene and the same functions
    sight and light read (`room_grid`, `anchor_cells`, `body_cell`,
    `room_field`), so the map cannot show a wall the cast is not judged by.
    `things` is the slice's list for the room (`story.room_slice`), so a
    thing is filed the one way it is filed everywhere. `charter`
    (`charter_body_records` over the frame `rooms_in_frame` lays) adds the
    townspeople to ``bodies`` as `kind: "charter"` -- those standing in this
    room, and those in a neighbour the grid lays, each carrying ``room`` so
    the map draws the latter faintly where the neighbour is. None when the
    room is not in the scene."""
    rooms_ = scene.get("rooms") or {}
    if not isinstance(rooms_.get(room_id), dict):
        return None
    grid = room_grid(scene, room_id)
    placed = anchor_cells(scene, room_id)
    field = room_field(scene, room_id)
    edges = {str(e.get("to")): e for e in effective_adjacent(scene, room_id)
             if isinstance(e, dict) and e.get("to")}

    anchors, doorways = {}, []
    for aid, rec in placed.items():
        if rec["implicit"] and str(aid).startswith(_DOOR_ANCHOR_PREFIX):
            to = str(aid)[len(_DOOR_ANCHOR_PREFIX):]
            edge = edges.get(to) or {}
            record = passage_of(scene, edge) or {}
            doorways.append({
                "id": str(aid), "to": to, "name": _room_name(scene, to),
                "dir": rec["dir"],
                # A doorway with no bearing has no wall to stand in; the
                # seeded interior cell `_place_anchors` gave it means
                # nothing here, so it is listed and not drawn.
                "cells": _cells(rec["cells"]) if rec["dir"] else [],
                "barrier": normalize_barrier(edge.get("barrier")),
                "offset": rec.get("offset"),
                "status": "live" if to in rooms_ else None,
                # THE PASSAGE (DESIGN_ROOM_FIDELITY §5): the one record both
                # edges read through, when the doorway has one; the fields a
                # host edits as ONE object from either room. `declared_here`
                # says whether this room's own list holds the edge -- the
                # doorway routes mint the missing side, so it no longer
                # decides what may be edited.
                "passage": str(edge.get("passage")) if record else None,
                "label": str(record.get("name") or edge.get("name") or ""),
                "material": str(record.get("material") or edge.get("material") or ""),
                "width": record.get("width"),
                "state": record.get("state") if isinstance(record.get("state"), dict) else {},
                "declared_here": not bool(edge.get("implicit")),
            })
            continue
        anchors[str(aid)] = {
            "cells": _cells(rec["cells"]), "dir": rec["dir"],
            "height": rec["height"], "footprint": rec["footprint"],
            "opacity": rec["opacity"], "desc": rec["desc"],
            "implicit": bool(rec["implicit"]), "offset": rec.get("offset"),
            # What placed it: "cell" (an authored origin cell), "offset" (a
            # place along its wall), or "seed" (the formula).
            "cell": rec.get("cell"), "source": rec.get("source") or "seed",
        }
    doorways.sort(key=lambda d: d["to"])

    bodies = {}
    for who, where in (scene.get("positions") or {}).items():
        if str(where or "") != str(room_id) or not _is_body(scene, who):
            continue
        cell = body_cell(scene, who)
        station = effective_station(scene, who)
        bodies[str(who)] = {
            "cell": [int(cell[0]), int(cell[1])] if cell else None,
            "facing": effective_facing(scene, who),
            "kind": _body_kind(who, player, cast),
            "at": station.get("at") or None,
            "near": [str(n) for n in (station.get("near") or [])],
            "measured": cell is not None,
            # Where the cell came from: "cell" (the station's own pin),
            # "anchor" (derived from `at`/`near`), or "none".
            "source": body_cell_source(scene, who),
        }
    # The townspeople, after the scene's bodies: this room's, then the ones
    # standing in a neighbour the field lays (`room` says which). Their
    # ``source`` is the placement's (`PLACEMENT_SOURCES`), not the pin word.
    laid = {str(room_id)} | {str(o) for o in (field.offsets if field else {})}
    for key, rec in sorted((charter or {}).items(),
                           key=lambda kv: (kv[1]["room"] != str(room_id), kv[0].casefold())):
        if rec["room"] in laid and key not in bodies:
            bodies[key] = dict(rec)

    things_out = []
    for thing in things or ():
        tid = str(thing.get("id") or "")
        if not tid:
            continue
        if tid in placed:
            cell, anchor, how, source = None, tid, "anchor", "anchor"
        else:
            placed_cell = body_cell(scene, tid)
            cell = [int(placed_cell[0]), int(placed_cell[1])] if placed_cell else None
            anchor, how = None, "position"
            # A thing is placed by its station's `cell` exactly as a body
            # is (the same route, the same rule), so the map can drag it.
            source = body_cell_source(scene, tid)
        ent = (scene.get("entities") or {}).get(tid)
        ent = ent if isinstance(ent, dict) else {}
        things_out.append({"id": tid, "name": str(thing.get("name") or tid),
                           "kind": str(thing.get("kind") or ""),
                           "cell": cell, "anchor": anchor, "placed": how,
                           "source": source,
                           "light_source": str(ent.get("light_source") or ""),
                           "sound_source": str(ent.get("sound_source") or "")})

    neighbours = []
    for other, offset in (field.offsets if field else {}).items():
        if str(other) == str(room_id):
            continue
        far = room_grid(scene, other)
        neighbours.append({
            "id": str(other), "name": _room_name(scene, other),
            "offset": [int(offset[0]), int(offset[1])],
            "w": far.w, "d": far.d, "shape": far.shape,
            "cells": _cells(far.cells),
            "anchors": {str(aid): {"cells": _cells(rec["cells"]),
                                   "desc": rec["desc"],
                                   "implicit": bool(rec["implicit"])}
                        for aid, rec in (field.anchors.get(other) or {}).items()},
        })
    walls = [{"axis": int(w["axis"]), "coord": int(w["coord"]),
              "extent": [float(w["extent"][0]), float(w["extent"][1])],
              "aperture": [float(w["aperture"][0]), float(w["aperture"][1])],
              "to": str(w["to"]), "name": _room_name(scene, w["to"])}
             for w in (field.walls if field else [])]
    return {
        "room": {"id": str(room_id), "name": _room_name(scene, room_id),
                 "w": grid.w, "d": grid.d, "shape": grid.shape,
                 "measured": bool(grid.measured), "cells": _cells(grid.cells)},
        # In the rim's OWN order (along the wall from its start), not sorted:
        # it is the order `offset` counts in, and on a round room's arc the
        # two differ.
        "rims": {wall: [[int(x), int(y)] for x, y in grid.rim(wall)]
                 for wall in WALLS},
        "anchors": anchors,
        "doorways": doorways,
        "bodies": bodies,
        "things": things_out,
        "walls": walls,
        "neighbours": neighbours,
        "lint": _room_lint(lint_rows, room_id),
        # THE OVERLAYS SLOT. `{name: {"x,y": word}}` per-cell readings the
        # map paints with a legend. Filled by the readers the composer uses
        # -- `light_field` and `sound_field`, over the same composite
        # `room_field` returns -- and quantised with their own ladders;
        # nothing is computed here or twice (`_overlays`). Absent when the
        # room has no geometry for the field to exist over.
        **_overlays(scene, room_id, sound_from),
    }


def _overlays(scene, room_id, sound_from=None):
    """``{overlays: {light, noise, sound?}, sound_sources: [...],
    light_sources: [...]}`` for one room, or empty maps when the room carries
    no geometry. `light` is the light field's word per cell
    (`LightField.level`, the room's own frame); `noise` is the sound field's
    floor per cell as `noise_word` says it -- every placed source's
    intensity plus the room's ambient, the composer's `noise_at` for a
    listener standing on that cell; `sound` is the hearing word for ONE
    chosen source or speaker (`sound_from`, an id `sound_sources` lists):
    `quantise_hearing` of its signal against the noise without it, per cell.
    `light_sources` are the field's own placed sources with their height
    RANK and shape, so the map can draw a full-height source as a ring (it
    casts no shadow, `DESIGN_LIGHT_FIELD.md`) without re-deriving the rule."""
    overlays, sound_sources, light_sources = {}, [], []
    lf = light_field(scene, room_id)
    if lf is not None:
        overlays["light"] = {f"{x},{y}": lf.level((x, y))
                             for x, y in lf.room_cells(room_id)}
        heights = list(HEIGHTS)
        for source in lf.sources:
            if source.get("room") != room_id:
                continue
            rank = source.get("height")
            light_sources.append({
                "id": str(source.get("id")), "label": str(source.get("label") or source.get("id")),
                "cell": [int(source["cell"][0]), int(source["cell"][1])],
                "height": heights[min(len(heights) - 1, max(0, int(round(float(rank or 0)))))],
                "shape": str(source.get("shape") or ""),
            })
    sf = sound_field(scene, "", room=room_id)
    if sf is not None:
        cells = [c for c, r in sf.grid.inside.items() if r == room_id]
        noise = {}
        for cell in cells:
            total = sf.ambient.get(room_id, 0.0)
            for source in sf.sources:
                total += sf.intensity_at(source, cell)
            noise[f"{cell[0]},{cell[1]}"] = noise_word(total)
        overlays["noise"] = noise
        sound_sources = [{"id": str(s["id"]), "label": str(s.get("label") or s["id"]),
                          "kind": str(s.get("kind") or "")} for s in sf.sources]
        chosen = next((s for s in sf.sources if str(s["id"]) == str(sound_from or "")), None)
        if chosen is not None:
            heard = {}
            for cell in cells:
                signal = sf.intensity_at(chosen, cell)
                rest = sf.ambient.get(room_id, 0.0) + sum(
                    sf.intensity_at(s, cell) for s in sf.sources if s is not chosen)
                heard[f"{cell[0]},{cell[1]}"] = quantise_hearing(signal, rest)
            overlays["sound"] = heard
    return {"overlays": overlays, "sound_sources": sound_sources,
            "light_sources": light_sources}


def map_view(scene, lint_rows, charter=None):
    """Every live room placed by bearing, as the lint's embedding places
    them (`layout_rooms`, one component per connected set of beared,
    non-wall edges, from its smallest id), each with its box and shape, its
    exits by wall, who stands in it and how many lint rows name it. A room
    the bearings land on another is DRAWN at the offset the rule gave it,
    flagged `collided` with the room it lands on and the doorway it was
    reached through -- the contradiction is the thing to look at, so it is
    never hidden. ``charter`` (`charter_body_records`, the whole scene)
    counts the townspeople among each room's ``occupants``, after the
    scene's bodies. The module docstring gives the shape."""
    rooms_ = {str(rid): room for rid, room in (scene.get("rooms") or {}).items()
              if isinstance(room, dict)}
    occupants = _occupants(scene)
    for key, rec in sorted((charter or {}).items(), key=lambda kv: kv[0].casefold()):
        occupants.setdefault(rec["room"], []).append(key)
    components = []
    placed = set()
    for start in sorted(rooms_):
        if start in placed:
            continue
        layout = layout_rooms(scene, start)
        offsets = dict(layout.get("offsets") or {})
        collided = dict(layout.get("collided") or {})
        placed.update(offsets)
        placed.update(collided)
        landed = {other: (onto, via) for other, onto, via in layout["collisions"]}
        parents = dict(layout.get("parents") or {})
        rows = []
        for rid in list(offsets) + [r for r in collided if r not in offsets]:
            grid = room_grid(scene, rid)
            offset = offsets.get(rid, collided.get(rid))
            exits = []
            for edge in effective_adjacent(scene, rid):
                if not isinstance(edge, dict) or not edge.get("to"):
                    continue
                to = str(edge["to"])
                # The doorway's cells in THIS room's frame (`_door_cells`,
                # the placement the layout itself used), so the structure
                # map draws the door where it stands rather than at the
                # middle of its wall; empty when the edge has no bearing.
                door_cells, _b = _door_cells(scene, rid, to)
                exits.append({"to": to, "name": _room_name(scene, to),
                              "dir": normalize_bearing(edge.get("dir")),
                              "barrier": normalize_barrier(edge.get("barrier")),
                              "cells": _cells(door_cells or []),
                              "passage": str(edge["passage"])
                              if passage_of(scene, edge) else None,
                              "placed": to in offsets or to in collided})
            exits.sort(key=lambda e: e["to"])
            onto, via = landed.get(rid, (None, None))
            rows.append({
                "id": rid, "name": _room_name(scene, rid),
                "offset": [int(offset[0]), int(offset[1])],
                "w": grid.w, "d": grid.d, "shape": grid.shape,
                "measured": bool(grid.measured), "cells": _cells(grid.cells),
                "exits": exits,
                "occupants": list(occupants.get(rid, [])),
                "lint": len(_room_lint(lint_rows, rid)),
                "holder": rooms_[rid].get("parent_entity") or None,
                "region": str(rooms_[rid].get("region") or "") or None,
                "collided": rid in collided and rid not in offsets,
                "onto": onto, "via": via,
                # The room this one was placed FROM (`layout_rooms`'s
                # `parents`): the edge a drag on the structure map re-bears.
                "placed_via": parents.get(rid) or via,
            })
        components.append({
            "start": start, "rooms": rows,
            "collisions": [{"room": a, "onto": b, "via": c}
                           for a, b, c in layout["collisions"]],
        })
    return {"components": components}


@router.get("/{room_id}/grid")
def rooms_grid(cid: int, room_id: str, frame_id: int | None = None,
               sound_from: str | None = None):
    chat = _chat_or_404(cid)
    with _era(cid, frame_id):
        scene = rooms.read_scene(cid)
        if not isinstance((scene.get("rooms") or {}).get(room_id), dict):
            raise HTTPException(
                404, f"No room '{room_id}' in this scene -- a planned room "
                     "has no grid until a beat furnishes it")
        slice_ = rooms.room_slice(cid, frame_id, room_id, scene) or {}
        view = grid_view(
            scene, room_id, _lint_rows(scene),
            player=str(persona_name(persona_of(chat)) or "").strip(),
            cast=_cast_ids(cid), things=slice_.get("things") or (),
            sound_from=sound_from,
            # The townspeople of this room and of every room the field lays
            # beyond its doorways -- the observer's frame, and no more.
            charter=charter_body_records(
                cid, frame_id, scene,
                frame_rooms=rooms_in_frame(scene, [room_id])))
    view["frame_id"] = frame_id
    return view


map_router = APIRouter(prefix="/api/chats/{cid}/map", tags=["world-browser"])


@map_router.get("")
def map_index(cid: int, frame_id: int | None = None):
    _chat_or_404(cid)
    with _era(cid, frame_id):
        scene = rooms.read_scene(cid)
        view = map_view(scene, _lint_rows(scene),
                        charter=charter_body_records(cid, frame_id, scene))
    view["frame_id"] = frame_id
    view["location"] = str(scene.get("location") or "")
    return view


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------

def _refuse_outside(field, value, allowed):
    """400 naming the set, when a value is not one of its words."""
    if value not in allowed:
        raise HTTPException(
            400, f"{field} must be one of: {', '.join(allowed)} (got '{value}')")


def _enum_value(field, raw, allowed):
    """A closed-set field's value from the body: '' or None clears (returns
    None), anything else must be one of the set's words."""
    value = str(raw or "").strip().casefold()
    if not value:
        return None
    _refuse_outside(field, value, allowed)
    return value


def _live_room_or_400(scene, room_id):
    room = (scene.get("rooms") or {}).get(str(room_id))
    if not isinstance(room, dict):
        known = ", ".join(sorted(scene.get("rooms") or {})) or "(none)"
        raise HTTPException(
            400, f"No room '{room_id}' in this scene. Known rooms: {known}")
    return room


def _edge_to(room, to_id):
    for edge in room.get("adjacent") or []:
        if isinstance(edge, dict) and str(edge.get("to")) == str(to_id):
            return edge
    return None


def _apply_exits(scene, room_id, room, exits):
    """Replace the room's exits and keep every doorway one object: the far
    room's reciprocal edge is created, re-barriered, re-beared or removed to
    agree. Fields the browser does not edit survive on an edge that keeps
    its `to`."""
    if not isinstance(exits, list):
        raise HTTPException(400, "exits must be a list of {to, barrier, dir}")
    scene_rooms = scene.get("rooms") or {}
    known = set(scene_rooms)
    prior = {str(e.get("to")): e for e in (room.get("adjacent") or [])
             if isinstance(e, dict) and e.get("to")}
    fresh, seen = [], set()
    for raw in exits:
        if not isinstance(raw, dict):
            raise HTTPException(400, "exits must be a list of {to, barrier, dir}")
        to = str(raw.get("to") or "").strip()
        if not to:
            raise HTTPException(400, "an exit needs a room to lead to")
        if to == str(room_id):
            raise HTTPException(400, "a room cannot exit into itself")
        if to in seen:
            raise HTTPException(400, f"exit to '{to}' is listed twice")
        seen.add(to)
        barrier = str(raw.get("barrier") or "").strip().casefold() or "open"
        _refuse_outside("barrier", barrier, sorted(_VALID_BARRIERS))
        direction = None
        if str(raw.get("dir") or "").strip():
            direction = normalize_bearing(raw.get("dir"))
            if direction is None:
                _refuse_outside("dir", str(raw.get("dir")), list(_BEARINGS))
        edge = dict(prior.get(to) or {})
        edge["to"] = to
        edge["barrier"] = barrier
        if direction:
            edge["dir"] = direction
        else:
            edge.pop("dir", None)
        if "offset" in raw:
            placed_at = _offset_or_400("an exit's offset", raw.get("offset"))
            if placed_at is None:
                edge.pop("offset", None)
            else:
                edge["offset"] = placed_at
        fresh.append(edge)
    room["adjacent"] = fresh

    # The far side. A planned room the scene does not hold has no edge list
    # to mirror onto; the plan's own topology already names the doorway.
    # A removed exit takes its passage record with it: the doorway is gone
    # from both rooms, and a record naming it would be re-minted onto them
    # by the sync.
    for to in set(prior) - seen:
        far = scene_rooms.get(to)
        if isinstance(far, dict):
            far["adjacent"] = [e for e in (far.get("adjacent") or [])
                               if not (isinstance(e, dict)
                                       and str(e.get("to")) == str(room_id))]
        gone = prior.get(to) or {}
        if passage_of(scene, gone):
            scene_passages(scene).pop(gone.get("passage"), None)
    for edge in fresh:
        to = edge["to"]
        if to not in known:
            continue
        far = scene_rooms[to]
        if not isinstance(far, dict):
            continue
        back = _edge_to(far, room_id)
        if back is None:
            back = {"to": str(room_id)}
            far.setdefault("adjacent", []).append(back)
        if edge["barrier"] != _ASYMMETRIC_BARRIER \
                and str(back.get("barrier") or "") != _ASYMMETRIC_BARRIER:
            back["barrier"] = edge["barrier"]
            # The host spoke on this edge: the passage the doorway resolves
            # through says the same, so `sync_scene_passages` writes it back
            # rather than the standing record overruling the edit.
            record = passage_of(scene, edge)
            if record is not None and edge["barrier"] != _ASYMMETRIC_BARRIER:
                record["barrier"] = edge["barrier"]
        if edge.get("dir"):
            back["dir"] = opposite_bearing(edge["dir"])
        else:
            back.pop("dir", None)
        # The doorway stands at one place along the wall from either side:
        # a wall's start is the same end seen from both rooms (west for a
        # north or south wall, north for an east or west one), so the
        # fraction is copied, not mirrored.
        if edge.get("offset") is not None:
            back["offset"] = edge["offset"]
        else:
            back.pop("offset", None)


def _apply_anchors(scene, room_id, room, anchors):
    """Replace the room's anchors: `{id: {desc, dir?, height?, footprint?,
    opacity?, offset?, cell?}}`, an empty id keyed by the folded desc,
    geometry words refused outside their sets, a `cell` refused outside the
    room's cells. `cell` and `offset` are exclusive -- a cell is a place and
    an offset is a place along a wall -- so a cell written here clears the
    offset, and an offset written with no cell is the whole of the placement
    (the map sends `cell: null` when it drags an anchor onto a wall)."""
    if isinstance(anchors, list):
        anchors = {str(a.get("id") or ""): a for a in anchors if isinstance(a, dict)}
    if not isinstance(anchors, dict):
        raise HTTPException(400, "anchors must be a mapping of id -> {desc, dir, ...}")
    grid = room_grid(scene, room_id)
    out = {}
    for aid, raw in anchors.items():
        if not isinstance(raw, dict):
            raise HTTPException(400, f"anchor '{aid}' must be an object")
        desc = " ".join(str(raw.get("desc") or "").split())
        key = normalize_room_id(str(aid or "")) or normalize_room_id(desc)
        if not key:
            raise HTTPException(400, "an anchor needs a description or an id")
        if key in out:
            raise HTTPException(400, f"anchor '{key}' is listed twice")
        anchor = {"desc": desc or key}
        if str(raw.get("dir") or "").strip():
            direction = normalize_bearing(raw.get("dir"))
            if direction is None:
                _refuse_outside("dir", str(raw.get("dir")), list(_BEARINGS))
            anchor["dir"] = direction
        for field, allowed in ANCHOR_ENUMS.items():
            value = _enum_value(field, raw.get(field), allowed)
            if value:
                anchor[field] = value
        cell = _cell_or_400(f"anchor '{key}' cell", raw.get("cell"), grid)
        placed_at = _offset_or_400(f"anchor '{key}' offset", raw.get("offset"))
        if cell is not None:
            anchor["cell"] = cell
        elif placed_at is not None:
            anchor["offset"] = placed_at
        # Whatever else the engine wrote on the anchor rides through.
        for field, value in raw.items():
            if field not in ("id", "desc", "dir", "offset", "cell", *ANCHOR_ENUMS) \
                    and value is not None:
                anchor.setdefault(field, value)
        out[key] = anchor
    room["anchors"] = out


def _paces_or_400(field, raw):
    """`{w, d}` in whole paces within the engine's clamp, or a 400 naming
    the range. `normalize_extent` CLAMPS a readable number and refuses only
    an unreadable one -- prose, a missing side, a zero -- so the refusal here
    is for a value that is not a measurement at all."""
    extent = normalize_extent(raw)
    if extent is None:
        raise HTTPException(
            400, f"{field} must be {{w, d}} in whole paces, each between "
                 f"{EXTENT_MIN_PACES} and {EXTENT_MAX_PACES} (got {raw!r})")
    return extent


def _offset_or_400(field, raw):
    """Where along its wall a thing stands, as `normalize_offset` reads it,
    or None to clear (null, ''), or a 400 naming the range. A numeric
    string is read as its number -- a form field is text -- and everything
    else that is not a number in [0, 1] is refused, never clamped: a host
    who typed 1.5 meant something the wall does not have."""
    if raw is None or raw == "":
        return None
    value = raw
    if isinstance(raw, str):
        try:
            value = float(raw.strip())
        except ValueError:
            value = raw
    placed_at = normalize_offset(value)
    if placed_at is None:
        raise HTTPException(
            400, f"{field} must be a number between 0 and 1 -- how far along "
                 f"the wall from its start (got {raw!r})")
    return placed_at


def _cell_or_400(field, raw, grid):
    """A cell of the room's own grid as `[x, y]`, or None to clear (null,
    '', []), or a 400 naming the bounds. Read by `normalize_cell` -- two
    whole numbers, nothing else -- and then required to lie on one of the
    room's cells: a host who dropped a body on (9, 2) of an 8-by-4 room
    dropped it outside, and the engine's own reader would silently snap it
    to the nearest cell (the fail-open for a room that has since shrunk),
    which is not what an authoring surface should do with a fresh mistake.
    The owner dragging bodies and anchors on the map, 2026-09-04."""
    if raw is None or raw == "" or raw == []:
        return None
    cell = normalize_cell(raw)
    if cell is None:
        raise HTTPException(
            400, f"{field} must be [x, y], two whole numbers in the room's own "
                 f"grid (got {raw!r})")
    if not grid.contains(cell):
        raise HTTPException(
            400, f"{field} [{cell[0]}, {cell[1]}] is outside the room: a "
                 f"{grid.shape} of {grid.w} by {grid.d} paces, x in 0..{grid.w - 1} "
                 f"and y in 0..{grid.d - 1}, and on a cell the shape keeps")
    return [cell[0], cell[1]]


def _apply_extent(room, raw):
    """Set or clear the room's extent. Setting one also writes the size
    tier it implies (`size_from_extent`): `size` is the WORD for the floor
    and `extent` its measurement, the card shows the word as derived while
    an extent stands, and the record should say what the card shows rather
    than carry a `size_disagrees_with_extent` row the host did not author.
    Clearing leaves `size` as it stands -- the room does not shrink to an
    unsized default because its measurement was withdrawn."""
    if raw in (None, "", {}, []):
        room.pop("extent", None)
        return
    extent = _paces_or_400("extent", raw)
    room["extent"] = extent
    room["size"] = size_from_extent(extent)


def _apply_parts(room, raw):
    """Replace the room's parts: each `{w, d, at}`, `at` a corner word of
    `ROOM_CORNERS` or an origin cell `[x, y]` in the room's own grid (the
    `cell` convention), the sides within the extent clamp, then the engine's
    own `normalize_parts` over the result. A cell part that lies outside the
    room's bounding box -- a negative origin, or a far edge past the extent
    when one stands -- is REFUSED naming the box: the reader would clip it to
    nothing, and an authoring surface should not quietly lose a fresh part.
    An empty list clears. Parts on a shape that is not `l` or `composite`
    are accepted -- the lint reports them (`corner_in_round_room`), and a
    host who changes the shape back keeps what was authored."""
    if raw in (None, ""):
        raw = []
    if not isinstance(raw, list):
        raise HTTPException(400, "parts must be a list of {w, d, at}")
    box = normalize_extent(room.get("extent"))
    parts = []
    for part in raw:
        if not isinstance(part, dict):
            raise HTTPException(400, "parts must be a list of {w, d, at}")
        at = normalize_part_at(part.get("at"))
        if at is None:
            raise HTTPException(
                400, f"a part's at must be a corner of the box "
                     f"({', '.join(ROOM_CORNERS)}) or its origin cell [x, y] "
                     f"(got {part.get('at')!r})")
        extent = _paces_or_400("a part's extent", part)
        if isinstance(at, list):
            if at[0] < 0 or at[1] < 0:
                raise HTTPException(
                    400, f"a part at [{at[0]}, {at[1]}] starts outside the "
                         f"room: x and y count from 0 at the north-west corner")
            if box and (at[0] + extent["w"] > box["w"] or at[1] + extent["d"] > box["d"]):
                raise HTTPException(
                    400, f"a part of {extent['w']} by {extent['d']} paces at "
                         f"[{at[0]}, {at[1]}] runs outside the room's box of "
                         f"{box['w']} by {box['d']} paces (x in 0..{box['w'] - 1}, "
                         f"y in 0..{box['d'] - 1}); widen the extent or move "
                         f"the part")
        parts.append({"w": extent["w"], "d": extent["d"], "at": at})
    parts = normalize_parts(parts)
    if parts:
        room["parts"] = parts
    else:
        room.pop("parts", None)


def _write_scene(cid, chat, before, scene):
    """The one way a route here lands a scene: normalised as the commit
    path normalises, written through `wset` under the ambient era, the
    registry projection reconciled against what the blob held before."""
    normalize_scene_barriers(scene)
    normalize_scene_bearings(scene)
    normalize_scene_anchor_cells(scene)
    # A doorway with a passage record is one object: an edge this write
    # changed (against `before`) speaks for it, and the record is written
    # back onto both edges (`sync_scene_passages`, the merge's own call).
    normalize_scene_passages(scene)
    sync_scene_passages(scene, before)
    scene.setdefault("stations", {})
    normalize_scene_stations(scene)
    with transaction():
        wset(cid, "scene", scene)
        sync_room_registry_with_scene(cid, chat.get("lorebook_id"), before, scene)


@router.patch("/{room_id}")
def room_patch(cid: int, room_id: str, body: dict = Body(...),
               frame_id: int | None = None):
    chat = _chat_or_404(cid)
    _require_idle(cid)
    if not isinstance(body, dict):
        raise HTTPException(400, "Send an object of the changed fields")
    with _era(cid, frame_id):
        scene = get_scene(cid, chat)
        before = copy.deepcopy(scene)
        room = _live_room_or_400(scene, room_id)
        for field in TEXT_FIELDS:
            if field in body:
                text = str(body.get(field) or "").strip()
                if field == "name" and not text:
                    raise HTTPException(400, "A room needs a name")
                room[field] = text
                if field == "desc":
                    room.pop("description", None)
        for field, allowed in ROOM_ENUMS.items():
            if field in body:
                value = _enum_value(field, body.get(field), allowed)
                if value:
                    room[field] = value
                else:
                    room.pop(field, None)
        if "region" in body:
            from world.regions import normalize_region_id
            region = normalize_region_id(str(body.get("region") or ""))
            if region:
                room["region"] = region
            else:
                room.pop("region", None)
        if "extent" in body:
            _apply_extent(room, body.get("extent"))
        if "shape" in body:
            shape = _enum_value("shape", body.get("shape"), SHAPES)
            if shape:
                room["shape"] = shape
            else:
                room.pop("shape", None)
        if "parts" in body:
            _apply_parts(room, body.get("parts"))
        if "exits" in body:
            _apply_exits(scene, room_id, room, body.get("exits"))
        if "anchors" in body:
            _apply_anchors(scene, room_id, room, body.get("anchors"))
        _write_scene(cid, chat, before, scene)
        row = _decorated_slice(cid, frame_id, room_id, scene)
    return row


@router.patch("/{room_id}/entities/{entity_id}")
def room_entity_patch(cid: int, room_id: str, entity_id: str,
                      body: dict = Body(...), frame_id: int | None = None):
    from world.regions import scene_anchors
    chat = _chat_or_404(cid)
    _require_idle(cid)
    if not isinstance(body, dict):
        raise HTTPException(400, "Send an object of the changed fields")
    with _era(cid, frame_id):
        scene = get_scene(cid, chat)
        before = copy.deepcopy(scene)
        _live_room_or_400(scene, room_id)
        entities = scene.setdefault("entities", {})
        entity = entities.get(str(entity_id))
        if not isinstance(entity, dict):
            raise HTTPException(404, f"No entity '{entity_id}' in this scene")
        placed_by_position = room_of(scene, str(entity_id))
        where = placed_by_position or scene_anchors(scene).get(str(entity_id))
        if str(where or "") != str(room_id):
            raise HTTPException(
                400, f"'{entity_id}' does not stand in '{room_id}'"
                     + (f" (it is in '{where}')" if where else ""))
        for field in ("kind", "description"):
            if field in body:
                entity[field] = " ".join(str(body.get(field) or "").split())
        if "portable" in body:
            entity["portable"] = bool(body.get("portable"))
        # THE SOURCE FIELDS. A thing that gives light or sound is a CLASS,
        # not a device (`world/spatial_light_field.py`'s rule): the level it
        # emits, how the emission is shaped, where it sits, whether it can
        # be relied on, what a cone points at, and whether it is lit or
        # running. This is how a ceiling light is authored -- `light_source`
        # with `light_height: full`, which casts no shadow -- and a lantern
        # on the floor, and a generator that cuts out, without naming any.
        for field, allowed in (("light_source", LIGHT_LEVELS),
                               ("light_shape", LIGHT_SHAPES),
                               ("light_height", LIGHT_HEIGHTS),
                               ("steadiness", STEADINESS),
                               ("sound_source", SOUND_LEVELS)):
            if field in body:
                value = _enum_value(field, body.get(field), allowed)
                if value:
                    entity[field] = value
                else:
                    entity.pop(field, None)
        for flag in ("lit", "running"):
            if flag in body:
                state = entity.get("state")
                if not isinstance(state, dict):
                    state = entity["state"] = {}
                if body.get(flag) is None:
                    state.pop(flag, None)
                else:
                    state[flag] = bool(body.get(flag))
        if "pointed_at" in body:
            state = entity.get("state")
            if not isinstance(state, dict):
                state = entity["state"] = {}
            target = str(body.get("pointed_at") or "").strip()
            if not target:
                state.pop("pointed_at", None)
            else:
                # What a cone may point at (`_resolve_pointed_at`): a
                # bearing word, an anchor of the room -- a doorway's implicit
                # anchor included -- or an entity the scene holds.
                anchors = effective_anchors(scene, room_id)
                if normalize_bearing(target) is None and target not in anchors \
                        and target not in entities:
                    raise HTTPException(
                        400, f"pointed_at must be a bearing ({', '.join(_BEARINGS)}), "
                             f"an anchor of '{room_id}' ({', '.join(sorted(anchors)) or 'none'}) "
                             f"or an entity of the scene (got {target!r})")
                state["pointed_at"] = normalize_bearing(target) or target
        if "room" in body:
            target = str(body.get("room") or "").strip()
            if not placed_by_position:
                raise HTTPException(
                    400, f"'{entity_id}' is placed as an anchor of '{room_id}', "
                         "not by a position; edit the room's anchors to move it")
            if not target:
                raise HTTPException(400, "A thing needs a room to move to")
            _live_room_or_400(scene, target)
            positions = scene.setdefault("positions", {})
            for key in [k for k in positions
                        if str(k).strip().casefold() == str(entity_id).strip().casefold()]:
                positions.pop(key)
            positions[str(entity_id)] = target
            # A thing's station -- its `cell`, in the OLD room's grid -- is
            # dropped on a change of room, the rule bodies follow
            # (`invalidate_moved_body_cells`); the map writes a fresh one in
            # the new room's grid when it moved the thing there.
            if target != placed_by_position:
                _drop_station(scene, str(entity_id))
        _write_scene(cid, chat, before, scene)
        row = _decorated_slice(cid, frame_id, room_id, scene)
    return row


regions_router = APIRouter(prefix="/api/chats/{cid}/regions", tags=["world-browser"])


@regions_router.patch("/{region_id}")
def region_patch(cid: int, region_id: str, body: dict = Body(...),
                 frame_id: int | None = None):
    """Write a region's `look` -- the visual register every room in the
    region shares (`world.regions.set_region_look`, the seam the room
    fidelity note left for a Room tool that is not built). Host-only,
    era-scoped and idle-guarded like the room writes; the region is entered
    by its id when the registry lacks it, as the seam does; an empty look
    removes the field. Returns ``{id, name, brief, look, rooms}``, `rooms`
    the live rooms of this frame in the region, so the card can say how
    many rooms the one sentence reaches."""
    from world.regions import (ensure_regions, normalize_region_id,
                               region_registry, set_region_look,
                               set_region_name)
    chat = _chat_or_404(cid)
    _require_idle(cid)
    if not isinstance(body, dict) or not ({"look", "name"} & set(body)):
        raise HTTPException(400, "Send {look} or {name}")
    rid = normalize_region_id(region_id)
    if not rid:
        raise HTTPException(400, "A region needs an id")
    look = body.get("look")
    if look is not None and not isinstance(look, str):
        raise HTTPException(400, "look must be text")
    # `name` (2026-09-05, the map's rename): the display name alone; the
    # id every room carries stays, so no room changes region.
    name = body.get("name")
    if "name" in body and (not isinstance(name, str) or not name.strip()):
        raise HTTPException(400, "A region needs a name")
    with _era(cid, frame_id):
        # A REGION IS ENTERED UNDER THE SPELLING IT WAS ASKED FOR. `rid` is
        # the id derived from that spelling, and the seam seeds a new entry's
        # display name from whatever it is handed -- so entering "the working
        # wing" wrote back `{"id": "the_working_wing", "name":
        # "the_working_wing"}`: the human phrase became the id and then the id
        # became the name (PX19, masque run, 2026-09-05). `ensure_regions`
        # never overwrites a standing entry, so this only ever supplies the
        # name a region did not have.
        ensure_regions(cid, frame_id,
                       {rid: " ".join(str(region_id).split()) or rid})
        entry = None
        if "look" in body:
            entry = set_region_look(cid, frame_id, rid, look or "")
        if "name" in body:
            entry = set_region_name(cid, frame_id, rid, name)
        if entry is None:
            entry = region_registry(cid, frame_id).get(rid)
        scene = get_scene(cid, chat) or {}
    if entry is None:
        raise HTTPException(400, "A region needs an id")
    in_region = sorted(
        str(room_id) for room_id, room in (scene.get("rooms") or {}).items()
        if isinstance(room, dict) and str(room.get("region") or "") == rid)
    return {"id": rid, "name": str(entry.get("name") or rid),
            "brief": str(entry.get("brief") or ""),
            "look": str(entry.get("look") or ""), "rooms": in_region}


bodies_router = APIRouter(prefix="/api/chats/{cid}/bodies", tags=["world-browser"])


@bodies_router.put("/{name}/station")
def body_station_put(cid: int, name: str, body: dict = Body(...),
                     frame_id: int | None = None):
    chat = _chat_or_404(cid)
    _require_idle(cid)
    if not isinstance(body, dict):
        raise HTTPException(400, "Send {at, near, cell}")
    with _era(cid, frame_id):
        scene = get_scene(cid, chat)
        before = copy.deepcopy(scene)
        positions = scene.get("positions") or {}
        folded = str(name).strip().casefold()
        key = next((k for k in positions if str(k).strip().casefold() == folded), None)
        room = str(positions.get(key) or "") if key is not None else ""
        if not room:
            raise HTTPException(400, f"'{name}' stands in no room, so has no station")
        # `cell`: a place in the room's own grid, the map editor's pin (the
        # owner, 2026-09-04: "why are characters and personas locked to
        # stations?"). Validated inside the room's cells; null or absent
        # is no pin. The player and a promoted presence are placed this
        # way like the cast -- the route asks only that the body stand in
        # a room; moving one BETWEEN rooms is `chat_char_position_put`,
        # which the registered cast alone has.
        cell = _cell_or_400(f"'{key}' cell", body.get("cell"), room_grid(scene, room))
        anchors = effective_anchors(scene, room)
        at = str(body.get("at") or "").strip() or None
        if at is not None and at not in anchors:
            held = ", ".join(sorted(anchors)) or "(none)"
            raise HTTPException(
                400, f"'{room}' has no anchor '{at}'. Anchors here: {held}")
        near_raw = body.get("near")
        if near_raw is None:
            near_raw = []
        if not isinstance(near_raw, list):
            raise HTTPException(400, "near must be a list of names")
        near = []
        for other in near_raw:
            other = str(other or "").strip()
            if not other or other.casefold() == folded:
                continue
            other_key = next((k for k in positions
                              if str(k).strip().casefold() == other.casefold()), None)
            if other_key is None or str(positions.get(other_key) or "") != room:
                raise HTTPException(
                    400, f"'{other}' does not stand in '{room}' with '{key}'")
            if other_key not in near:
                near.append(other_key)
        stations = scene.setdefault("stations", {})
        if not isinstance(stations, dict):
            stations = scene["stations"] = {}
        # The route writes what it owns -- `at`, `near`, `cell` -- and a
        # field it does not (`cover`, the geometry note's) rides through.
        prior = stations.get(key) if isinstance(stations.get(key), dict) else {}
        station = {k: v for k, v in prior.items() if k not in ("at", "near", "cell")}
        station.update({"at": at, "near": near})
        # NEAR IS ONE FACT STORED TWICE, so unchecking it has to be written
        # twice. `normalize_scene_stations` SYMMETRIZES on every merge -- if A
        # names B, B is given A -- and nothing ever removed the mirror, so
        # clearing the box on A's row wrote `near: []` and the next merge put
        # B back from B's own list. The link could not be broken from either
        # side (owner, 2026-09-08: "I can't uncheck the near checkbox"). The
        # route owns the intent, so it drops this body from the list of every
        # co-located body it no longer names; the merge then re-symmetrizes
        # what survives.
        dropped = [n for n in (prior.get("near") or []) if n not in near]
        for other in dropped:
            mirror = stations.get(other)
            if isinstance(mirror, dict) and isinstance(mirror.get("near"), list):
                mirror["near"] = [n for n in mirror["near"]
                                  if str(n).strip().casefold() != folded]
        if cell is not None:
            station["cell"] = cell
        stations[key] = station
        _write_scene(cid, chat, before, scene)
        rows = body_rows(cid, chat, scene,
                         charter=charter_body_records(cid, frame_id, scene))
    row = next((b for b in rows if b["name"].strip().casefold() == folded), None)
    return row or {"name": key, "room": room, "station": stations[key]}


# ---------------------------------------------------------------------------
# Create and remove, from the map (2026-09-05; the owner: "this room editor
# feels very incomplete"). Each write is narrow, typed, era-scoped and
# idle-guarded like the ones above, lands through `_write_scene`, and refuses
# naming the reason.
# ---------------------------------------------------------------------------

def _drop_station(scene, name):
    """Remove a body's or a thing's station row, case-insensitively."""
    stations = scene.get("stations")
    if not isinstance(stations, dict):
        return
    folded = str(name).strip().casefold()
    for key in [k for k in stations if str(k).strip().casefold() == folded]:
        stations.pop(key, None)


def _mint_id(name, taken, fallback):
    """An id from a name, the room-id fold (`normalize_room_id`), suffixed
    `_2`, `_3`, ... while `taken` holds it -- so a retired room's spent id
    is never reused."""
    base = normalize_room_id(str(name or "")) or fallback
    candidate, n = base, 1
    while candidate in taken:
        n += 1
        candidate = f"{base}_{n}"
    return candidate


def _position_key(scene, name):
    folded = str(name or "").strip().casefold()
    for key in (scene.get("positions") or {}):
        if str(key).strip().casefold() == folded:
            return key
    return None


def _ensure_passage(scene, a, b):
    """The passage record a doorway between `a` and `b` resolves through,
    minted from the standing edges when neither names one: the id
    `passage_id_for` gives, the barrier the room's own edge carries (else
    the far edge's, else `open`), the edge fields the passage owns copied
    up. Both edges are made to exist and to name it. Returns `(id, record)`;
    `sync_scene_passages` in `_write_scene` then writes the record back onto
    both edges."""
    rooms_ = scene.get("rooms") or {}
    ra, rb = rooms_[a], rooms_[b]
    ea, eb = _edge_to(ra, b), _edge_to(rb, a)
    for edge in (ea, eb):
        record = passage_of(scene, edge) if edge else None
        if record is not None:
            pid = edge["passage"]
            break
    else:
        pid = passage_id_for(a, b)
        passages = scene.setdefault("passages", {})
        if not isinstance(passages, dict):
            passages = scene["passages"] = {}
        spoken = ea if ea is not None and "barrier" in ea else eb
        record = {"rooms": [str(a), str(b)],
                  "barrier": normalize_barrier((spoken or {}).get("barrier") or "open")}
        for field in ("name", "material"):
            value = (ea or {}).get(field) or (eb or {}).get(field)
            if value:
                record[field] = value
        passages[pid] = record
    if ea is None:
        ea = {"to": str(b)}
        if eb is not None and normalize_bearing(eb.get("dir")):
            ea["dir"] = opposite_bearing(normalize_bearing(eb["dir"]))
        if eb is not None and eb.get("offset") is not None:
            ea["offset"] = eb["offset"]
        ra.setdefault("adjacent", []).append(ea)
    if eb is None:
        eb = {"to": str(a)}
        if normalize_bearing(ea.get("dir")):
            eb["dir"] = opposite_bearing(normalize_bearing(ea["dir"]))
        if ea.get("offset") is not None:
            eb["offset"] = ea["offset"]
        rb.setdefault("adjacent", []).append(eb)
    ea["passage"] = pid
    eb["passage"] = pid
    return pid, record


def _occupants_of(scene, room_id):
    """(bodies, things) standing in the room by a position row."""
    bodies, things = [], []
    for who, where in (scene.get("positions") or {}).items():
        if str(where or "") != str(room_id):
            continue
        (bodies if _is_body(scene, who) else things).append(str(who))
    return sorted(bodies), sorted(things)


@router.post("")
def room_create(cid: int, body: dict = Body(...), frame_id: int | None = None):
    """Mint a live room from the map: ``{name, from?, dir?, barrier?,
    extent?, shape?, region?}``. With ``from`` (a live room) the new room is
    joined to it by ONE doorway -- a passage record with both edges, the
    given ``barrier`` (default `open`) and ``dir`` as the bearing FROM the
    existing room, its opposite on the new room's edge -- so the layout
    places it off that wall; without ``from`` the room stands unjoined.
    The region is the joined room's unless ``region`` says otherwise (the
    commit's own rule for a room reached from another). The id is minted
    from the name and never reuses one the scene or the registry holds.
    Returns the new room's slice plus ``id``."""
    chat = _chat_or_404(cid)
    _require_idle(cid)
    if not isinstance(body, dict):
        raise HTTPException(400, "Send {name, from, dir, barrier}")
    name = " ".join(str(body.get("name") or "").split())
    if not name:
        raise HTTPException(400, "A room needs a name")
    with _era(cid, frame_id):
        scene = get_scene(cid, chat)
        before = copy.deepcopy(scene)
        rooms_ = scene.setdefault("rooms", {})
        taken = set(rooms_) | {str(r["room_uid"]) for r in q(
            "SELECT room_uid FROM room_registry WHERE chat_id=?", (cid,))}
        rid = _mint_id(name, taken, "room")
        room = {"name": name, "desc": "", "adjacent": []}
        source = str(body.get("from") or "").strip()
        if source:
            origin = _live_room_or_400(scene, source)
            direction = None
            if str(body.get("dir") or "").strip():
                direction = normalize_bearing(body.get("dir"))
                if direction is None:
                    _refuse_outside("dir", str(body.get("dir")), list(_BEARINGS))
            barrier = str(body.get("barrier") or "").strip().casefold() or "open"
            _refuse_outside("barrier", barrier, sorted(_VALID_BARRIERS))
            edge = {"to": rid, "barrier": barrier}
            if direction:
                edge["dir"] = direction
            origin.setdefault("adjacent", []).append(edge)
            if origin.get("region") and not origin.get("parent_entity"):
                room["region"] = origin["region"]
        if "region" in body:
            from world.regions import normalize_region_id
            region = normalize_region_id(str(body.get("region") or ""))
            if region:
                room["region"] = region
            else:
                room.pop("region", None)
        rooms_[rid] = room
        if source:
            _ensure_passage(scene, source, rid)
        if body.get("extent") not in (None, "", {}, []):
            _apply_extent(room, body.get("extent"))
        if str(body.get("shape") or "").strip():
            shape = _enum_value("shape", body.get("shape"), SHAPES)
            if shape:
                room["shape"] = shape
        _write_scene(cid, chat, before, scene)
        row = _decorated_slice(cid, frame_id, rid, scene)
    row = row or {}
    row["id"] = rid
    return row


@router.delete("/{room_id}")
def room_delete(cid: int, room_id: str, frame_id: int | None = None):
    """Remove a live room from the scene. REFUSED while anything stands in
    it -- bodies and things alike, each named -- because a position row
    naming no room is a body nowhere. Every edge into it and every passage
    record naming it go with it; the registry projection retires the id
    through `sync_room_registry_with_scene`, the path every scene writer
    keeps (and the path restore reads), so the id is spent, never reused.
    Returns ``{removed, retired}``."""
    chat = _chat_or_404(cid)
    _require_idle(cid)
    with _era(cid, frame_id):
        scene = get_scene(cid, chat)
        before = copy.deepcopy(scene)
        _live_room_or_400(scene, room_id)
        bodies, things = _occupants_of(scene, room_id)
        if bodies or things:
            parts = []
            if bodies:
                parts.append("bodies: " + ", ".join(bodies))
            if things:
                parts.append("things: " + ", ".join(things))
            raise HTTPException(
                400, f"'{room_id}' is not empty ({'; '.join(parts)}); move "
                     "them out before removing the room")
        rooms_ = scene.get("rooms") or {}
        rooms_.pop(room_id, None)
        for room in rooms_.values():
            if isinstance(room, dict) and room.get("adjacent"):
                room["adjacent"] = [e for e in room["adjacent"]
                                    if not (isinstance(e, dict)
                                            and str(e.get("to")) == str(room_id))]
        for pid, record in list(scene_passages(scene).items()):
            if str(room_id) in [str(r) for r in (record.get("rooms") or [])]:
                scene["passages"].pop(pid, None)
        _write_scene(cid, chat, before, scene)
    return {"removed": str(room_id), "retired": True}


@router.post("/{room_id}/entities")
def room_entity_create(cid: int, room_id: str, body: dict = Body(...),
                       frame_id: int | None = None):
    """Mint a THING standing in the room by a position row: ``{name, kind?,
    description?, cell?}``. Its id is minted from the name against the
    scene's entities; ``cell`` pins it in the room's grid through the
    station the map writes (`_cell_or_400`). Returns the fresh slice plus
    ``id``."""
    chat = _chat_or_404(cid)
    _require_idle(cid)
    if not isinstance(body, dict):
        raise HTTPException(400, "Send {name, kind, description, cell}")
    name = " ".join(str(body.get("name") or "").split())
    if not name:
        raise HTTPException(400, "A thing needs a name")
    with _era(cid, frame_id):
        scene = get_scene(cid, chat)
        before = copy.deepcopy(scene)
        _live_room_or_400(scene, room_id)
        entities = scene.setdefault("entities", {})
        taken = set(entities) | {str(k) for k in (scene.get("positions") or {})}
        eid = _mint_id(name, taken, "thing")
        entity = {"name": name, "kind": " ".join(str(body.get("kind") or "object").split()),
                  "description": " ".join(str(body.get("description") or "").split())}
        entities[eid] = entity
        scene.setdefault("positions", {})[eid] = str(room_id)
        cell = _cell_or_400("cell", body.get("cell"), room_grid(scene, room_id))
        if cell is not None:
            scene.setdefault("stations", {})[eid] = {"at": None, "near": [], "cell": cell}
        _write_scene(cid, chat, before, scene)
        row = _decorated_slice(cid, frame_id, room_id, scene)
    row = row or {}
    row["id"] = eid
    return row


@router.delete("/{room_id}/entities/{entity_id}")
def room_entity_delete(cid: int, room_id: str, entity_id: str,
                       frame_id: int | None = None):
    """Remove a thing standing in the room by a position row: its entity
    record, position, station and pose. A thing placed as one of the
    room's anchors is refused -- the anchor editor is where it lives -- as
    is a body (a person is not a thing; the bodies routes own them)."""
    from world.regions import scene_anchors
    chat = _chat_or_404(cid)
    _require_idle(cid)
    with _era(cid, frame_id):
        scene = get_scene(cid, chat)
        before = copy.deepcopy(scene)
        _live_room_or_400(scene, room_id)
        entities = scene.get("entities") or {}
        if not isinstance(entities.get(str(entity_id)), dict):
            raise HTTPException(404, f"No entity '{entity_id}' in this scene")
        if _is_body(scene, entity_id):
            raise HTTPException(
                400, f"'{entity_id}' is a body, not a thing; remove a presence "
                     "through the bodies route")
        placed_by_position = room_of(scene, str(entity_id))
        if not placed_by_position:
            where = scene_anchors(scene).get(str(entity_id))
            raise HTTPException(
                400, f"'{entity_id}' is placed as an anchor"
                     + (f" of '{where}'" if where else "")
                     + ", not by a position; edit the room's anchors to remove it")
        if str(placed_by_position) != str(room_id):
            raise HTTPException(
                400, f"'{entity_id}' does not stand in '{room_id}' "
                     f"(it is in '{placed_by_position}')")
        entities.pop(str(entity_id), None)
        key = _position_key(scene, entity_id)
        if key is not None:
            scene["positions"].pop(key, None)
        _drop_station(scene, entity_id)
        poses = scene.get("poses")
        if isinstance(poses, dict):
            poses.pop(str(entity_id), None)
        _write_scene(cid, chat, before, scene)
        row = _decorated_slice(cid, frame_id, room_id, scene)
    return row


@router.post("/{room_id}/presences")
def room_presence_create(cid: int, room_id: str, body: dict = Body(...),
                         frame_id: int | None = None):
    """Place a PRESENCE in the room: ``{name, cell?}``. A presence is a body
    the scene places by a position row with no registered sheet behind it
    (`_body_kind`); nothing else is minted -- no entity, no memory, no
    psychology (that is promotion). Refused when the name already stands
    somewhere, or is the player's or a cast member's -- those are moved,
    not created. Returns the fresh slice."""
    chat = _chat_or_404(cid)
    _require_idle(cid)
    if not isinstance(body, dict):
        raise HTTPException(400, "Send {name, cell}")
    name = " ".join(str(body.get("name") or "").split())
    if not name:
        raise HTTPException(400, "A presence needs a name")
    with _era(cid, frame_id):
        scene = get_scene(cid, chat)
        before = copy.deepcopy(scene)
        _live_room_or_400(scene, room_id)
        key = _position_key(scene, name)
        if key is not None:
            raise HTTPException(
                400, f"'{key}' already stands in '{scene['positions'][key]}'; "
                     "move them rather than placing them twice")
        player = str(persona_name(persona_of(chat)) or "").strip()
        kind = _body_kind(name, player, _cast_ids(cid))
        if kind != "presence":
            raise HTTPException(
                400, f"'{name}' is the {kind}; move them into the room rather "
                     "than placing a presence of the same name")
        scene.setdefault("positions", {})[name] = str(room_id)
        cell = _cell_or_400("cell", body.get("cell"), room_grid(scene, room_id))
        if cell is not None:
            scene.setdefault("stations", {})[name] = {"at": None, "near": [], "cell": cell}
        _write_scene(cid, chat, before, scene)
        row = _decorated_slice(cid, frame_id, room_id, scene)
    return row


@bodies_router.delete("/{name}")
def body_presence_delete(cid: int, name: str, frame_id: int | None = None):
    """Remove a presence from the scene: its position, station and pose.
    The player and the registered cast are refused -- their place is the
    story's and the cast editor's -- and so is a thing. The attire ledger is
    left: a body the ledger dresses that nothing places is a legitimate
    state (`body_rows`). Returns ``{removed}``."""
    chat = _chat_or_404(cid)
    _require_idle(cid)
    with _era(cid, frame_id):
        scene = get_scene(cid, chat)
        before = copy.deepcopy(scene)
        key = _position_key(scene, name)
        if key is None:
            raise HTTPException(400, f"'{name}' stands in no room")
        if not _is_body(scene, key):
            raise HTTPException(400, f"'{key}' is a thing; remove it through its room")
        player = str(persona_name(persona_of(chat)) or "").strip()
        kind = _body_kind(key, player, _cast_ids(cid))
        if kind != "presence":
            raise HTTPException(
                400, f"'{key}' is the {kind} and cannot be removed here; "
                     "only a presence can")
        scene["positions"].pop(key, None)
        _drop_station(scene, key)
        for ledger in ("poses", "orientation"):
            table = scene.get(ledger)
            if isinstance(table, dict):
                for k in [k for k in table if str(k).strip().casefold() == key.strip().casefold()]:
                    table.pop(k, None)
        _write_scene(cid, chat, before, scene)
    return {"removed": key}


@bodies_router.put("/{name}/room")
def body_room_put(cid: int, name: str, body: dict = Body(...),
                  frame_id: int | None = None):
    """Move ANY body the scene knows -- the player, a presence, a cast
    member -- to a live room: ``{room}``. The route the cast editor lacked
    for the player and a presence (`chat_char_position_put` is by character
    id); the same invalidation follows a change of room: the station's
    `cell` (a place in the OLD room's grid) is dropped, and a pose detail
    holding another body is dropped by `invalidate_moved_body_pose_details`.
    Refused for an unknown room naming the known ones, and for a name the
    scene does not place (a presence is created through its room). Returns
    the body's row."""
    chat = _chat_or_404(cid)
    _require_idle(cid)
    if not isinstance(body, dict):
        raise HTTPException(400, "Send {room}")
    target = str(body.get("room") or "").strip()
    if not target:
        raise HTTPException(400, "A body needs a room to move to")
    with _era(cid, frame_id):
        scene = get_scene(cid, chat)
        before = copy.deepcopy(scene)
        _live_room_or_400(scene, target)
        positions = scene.setdefault("positions", {})
        key = _position_key(scene, name)
        player = str(persona_name(persona_of(chat)) or "").strip()
        if key is None:
            if player and str(name).strip().casefold() == player.casefold():
                key = player
            else:
                raise HTTPException(
                    400, f"'{name}' stands in no room; place a presence "
                         "through the room it should stand in")
        elif not _is_body(scene, key):
            raise HTTPException(400, f"'{key}' is a thing; move it through its room")
        was = str(positions.get(key) or "")
        positions[key] = target
        if was != target:
            stations = scene.get("stations")
            station = stations.get(key) if isinstance(stations, dict) else None
            if isinstance(station, dict):
                station.pop("cell", None)
            invalidate_moved_body_pose_details(scene, before.get("positions") or {})
        _write_scene(cid, chat, before, scene)
        rows = body_rows(cid, chat, scene,
                         charter=charter_body_records(cid, frame_id, scene))
    folded = key.strip().casefold()
    return next((b for b in rows if b["name"].strip().casefold() == folded),
                {"name": key, "room": target})


@bodies_router.put("/{name}/pose")
def body_pose_put(cid: int, name: str, body: dict = Body(...),
                  frame_id: int | None = None):
    """Write a body's pose: the six fields of `_POSE_FIELDS`, each open
    prose, cleaned by the engine's own `_clean_pose` (a null idiom is empty;
    a pose with nothing in it is no pose and the record is removed). A body
    must be one the scene places or the player. Returns the body's row."""
    chat = _chat_or_404(cid)
    _require_idle(cid)
    if not isinstance(body, dict):
        raise HTTPException(400, "Send {" + ", ".join(_POSE_FIELDS) + "}")
    unknown = sorted(k for k in body if k not in _POSE_FIELDS)
    if unknown:
        raise HTTPException(
            400, f"a pose has the fields {', '.join(_POSE_FIELDS)} (got "
                 f"{', '.join(unknown)})")
    with _era(cid, frame_id):
        scene = get_scene(cid, chat)
        before = copy.deepcopy(scene)
        key = _position_key(scene, name)
        player = str(persona_name(persona_of(chat)) or "").strip()
        if key is None and player and str(name).strip().casefold() == player.casefold():
            key = player
        if key is None:
            raise HTTPException(400, f"'{name}' stands in no room, so has no pose")
        poses = scene.setdefault("poses", {})
        if not isinstance(poses, dict):
            poses = scene["poses"] = {}
        for k in [k for k in poses if str(k).strip().casefold() == key.strip().casefold()]:
            poses.pop(k, None)
        pose = _clean_pose(body)
        if pose is not None:
            poses[key] = pose
        _write_scene(cid, chat, before, scene)
        rows = body_rows(cid, chat, scene,
                         charter=charter_body_records(cid, frame_id, scene))
    folded = key.strip().casefold()
    return next((b for b in rows if b["name"].strip().casefold() == folded),
                {"name": key, "pose": pose})


# ---------------------------------------------------------------------------
# The doorway as ONE object (the passage record, DESIGN_ROOM_FIDELITY §5)
# ---------------------------------------------------------------------------

doorways_router = APIRouter(prefix="/api/chats/{cid}/doorways", tags=["world-browser"])

#: What a doorway PATCH may carry.
DOORWAY_FIELDS = ("barrier", "dir", "offset", "name", "material", "width",
                  "vertical", "state")

#: The widest doorway in paces: the extent ceiling, since a doorway cannot be
#: wider than any wall it stands in. Owner-visible.
DOORWAY_MAX_WIDTH = EXTENT_MAX_PACES


def _apply_doorway_fields(scene, room_id, to, record, ea, eb, body):
    """Write the fields of one doorway onto its passage record and, for the
    per-edge ones (`dir`, `offset`), onto both edges directly -- `dir` as
    given from `room_id` and its opposite from `to`, `offset` the same
    fraction on both (a wall's start is the same end from either room)."""
    if "barrier" in body:
        barrier = str(body.get("barrier") or "").strip().casefold() or "open"
        _refuse_outside("barrier", barrier, sorted(_VALID_BARRIERS))
        record["barrier"] = barrier
        # The edges are written here too, so a one_way_window -- which the
        # sync leaves per edge -- still lands on both.
        ea["barrier"] = barrier
        eb["barrier"] = barrier
    if "dir" in body:
        if str(body.get("dir") or "").strip():
            direction = normalize_bearing(body.get("dir"))
            if direction is None:
                _refuse_outside("dir", str(body.get("dir")), list(_BEARINGS))
            ea["dir"] = direction
            eb["dir"] = opposite_bearing(direction)
        else:
            ea.pop("dir", None)
            eb.pop("dir", None)
    if "offset" in body:
        placed_at = _offset_or_400("a doorway's offset", body.get("offset"))
        for edge in (ea, eb):
            if placed_at is None:
                edge.pop("offset", None)
            else:
                edge["offset"] = placed_at
    for field in ("name", "material"):
        if field in body:
            text = " ".join(str(body.get(field) or "").split())
            if text:
                record[field] = text
            else:
                record.pop(field, None)
                ea.pop(field, None)
                eb.pop(field, None)
    if "width" in body:
        raw = body.get("width")
        if raw in (None, ""):
            record.pop("width", None)
            ea.pop("width", None)
            eb.pop("width", None)
        else:
            try:
                width = int(raw) if not isinstance(raw, bool) else None
            except (TypeError, ValueError):
                width = None
            if width is None or width < 1 or width > DOORWAY_MAX_WIDTH:
                raise HTTPException(
                    400, f"a doorway's width is whole paces between 1 and "
                         f"{DOORWAY_MAX_WIDTH} (got {raw!r})")
            record["width"] = width
    if "vertical" in body:
        if str(body.get("vertical") or "").strip():
            vertical = normalize_vertical(body.get("vertical"))
            if vertical is None:
                raise HTTPException(
                    400, f"vertical must be up or down as seen from '{room_id}' "
                         f"(got {body.get('vertical')!r})")
            # Stored as seen from `rooms[0]`; the sync writes the edges.
            record["vertical"] = vertical if str(record["rooms"][0]) == str(room_id) \
                else (opposite_vertical(vertical) or vertical)
        else:
            record.pop("vertical", None)
            ea.pop("vertical", None)
            eb.pop("vertical", None)
    if "state" in body:
        state = body.get("state")
        if state in (None, "", {}):
            record.pop("state", None)
        elif isinstance(state, dict):
            record["state"] = {str(k): v for k, v in state.items() if str(k)}
        else:
            raise HTTPException(400, "a doorway's state is an object of facts about it")


@doorways_router.post("")
def doorway_create(cid: int, body: dict = Body(...), frame_id: int | None = None):
    """Open a doorway between two live rooms: ``{room, to, barrier?, dir?,
    offset?, name?, material?, width?}`` -- ``dir`` the bearing from
    ``room``, ``offset`` where along that wall (the map's click on a blank
    wall segment supplies both). ONE object: a passage record and both
    edges. Refused when a doorway already stands between the two (edit it),
    when either room is not live, or when the two are one. Returns
    ``{passage, room, to}`` plus the fresh slice of ``room`` as ``slice``."""
    chat = _chat_or_404(cid)
    _require_idle(cid)
    if not isinstance(body, dict):
        raise HTTPException(400, "Send {room, to, barrier, dir, offset}")
    room_id = str(body.get("room") or "").strip()
    to = str(body.get("to") or "").strip()
    if not room_id or not to:
        raise HTTPException(400, "A doorway joins two rooms: send room and to")
    if room_id == to:
        raise HTTPException(400, "a room cannot exit into itself")
    with _era(cid, frame_id):
        scene = get_scene(cid, chat)
        before = copy.deepcopy(scene)
        here = _live_room_or_400(scene, room_id)
        there = _live_room_or_400(scene, to)
        if _edge_to(here, to) is not None or _edge_to(there, room_id) is not None:
            raise HTTPException(
                400, f"a doorway already stands between '{room_id}' and '{to}'; "
                     "edit it rather than opening a second")
        here.setdefault("adjacent", []).append({"to": to, "barrier": "open"})
        pid, record = _ensure_passage(scene, room_id, to)
        fields = {k: v for k, v in body.items() if k in DOORWAY_FIELDS}
        fields.setdefault("barrier", "open")
        _apply_doorway_fields(scene, room_id, to, record,
                              _edge_to(here, to), _edge_to(there, room_id), fields)
        _write_scene(cid, chat, before, scene)
        row = _decorated_slice(cid, frame_id, room_id, scene)
    return {"passage": pid, "room": room_id, "to": to, "slice": row}


@doorways_router.patch("/{room_id}/{to}")
def doorway_patch(cid: int, room_id: str, to: str, body: dict = Body(...),
                  frame_id: int | None = None):
    """Edit the doorway between two rooms as ONE object, from EITHER room --
    a doorway declared from the far side alone included, since the passage
    record is minted from the standing edge and the missing edge with it
    (`_ensure_passage`). Fields: `DOORWAY_FIELDS`; ``dir`` and ``vertical``
    are as seen from ``room_id``. Refused when no doorway stands between
    the two. Returns ``{passage}`` plus the fresh slice of ``room_id`` as
    ``slice``."""
    chat = _chat_or_404(cid)
    _require_idle(cid)
    if not isinstance(body, dict):
        raise HTTPException(400, "Send the changed fields: " + ", ".join(DOORWAY_FIELDS))
    unknown = sorted(k for k in body if k not in DOORWAY_FIELDS)
    if unknown:
        raise HTTPException(
            400, f"a doorway has the fields {', '.join(DOORWAY_FIELDS)} "
                 f"(got {', '.join(unknown)})")
    with _era(cid, frame_id):
        scene = get_scene(cid, chat)
        before = copy.deepcopy(scene)
        here = _live_room_or_400(scene, room_id)
        there = _live_room_or_400(scene, to)
        if _edge_to(here, to) is None and _edge_to(there, room_id) is None:
            raise HTTPException(
                400, f"no doorway stands between '{room_id}' and '{to}'; open "
                     "one first")
        pid, record = _ensure_passage(scene, room_id, to)
        _apply_doorway_fields(scene, room_id, to, record,
                              _edge_to(here, to), _edge_to(there, room_id), body)
        _write_scene(cid, chat, before, scene)
        row = _decorated_slice(cid, frame_id, room_id, scene)
    return {"passage": pid, "room": room_id, "to": to, "slice": row}


@doorways_router.delete("/{room_id}/{to}")
def doorway_delete(cid: int, room_id: str, to: str, frame_id: int | None = None):
    """Close up a doorway: both edges and the passage record. Refused when
    none stands between the two rooms. Returns ``{removed: [room, to]}``
    plus the fresh slice of ``room_id`` as ``slice``."""
    chat = _chat_or_404(cid)
    _require_idle(cid)
    with _era(cid, frame_id):
        scene = get_scene(cid, chat)
        before = copy.deepcopy(scene)
        here = _live_room_or_400(scene, room_id)
        there = _live_room_or_400(scene, to)
        ea, eb = _edge_to(here, to), _edge_to(there, room_id)
        if ea is None and eb is None:
            raise HTTPException(
                400, f"no doorway stands between '{room_id}' and '{to}'")
        for edge in (ea, eb):
            record = passage_of(scene, edge) if edge else None
            if record is not None:
                scene_passages(scene).pop(edge.get("passage"), None)
        here["adjacent"] = [e for e in (here.get("adjacent") or [])
                            if not (isinstance(e, dict) and str(e.get("to")) == str(to))]
        there["adjacent"] = [e for e in (there.get("adjacent") or [])
                             if not (isinstance(e, dict) and str(e.get("to")) == str(room_id))]
        _write_scene(cid, chat, before, scene)
        row = _decorated_slice(cid, frame_id, room_id, scene)
    return {"removed": [room_id, to], "slice": row}


# ---------------------------------------------------------------------------
# Regions: create and rename (the `look` PATCH stands above)
# ---------------------------------------------------------------------------

@regions_router.post("")
def region_create(cid: int, body: dict = Body(...), frame_id: int | None = None):
    """Enter a region in the frame's registry by name: ``{name}``. The id is
    the name's room-id fold (`normalize_region_id`); a region of that id
    already standing is returned as it is (the write is idempotent) so the
    map can offer it to a room at once. Returns ``{id, name, brief, look,
    rooms}``."""
    from world.regions import ensure_regions, normalize_region_id, region_registry
    chat = _chat_or_404(cid)
    _require_idle(cid)
    if not isinstance(body, dict):
        raise HTTPException(400, "Send {name}")
    name = " ".join(str(body.get("name") or "").split())
    rid = normalize_region_id(name)
    if not name or not rid:
        raise HTTPException(400, "A region needs a name")
    with _era(cid, frame_id):
        ensure_regions(cid, frame_id, {rid: name})
        entry = region_registry(cid, frame_id).get(rid) or {"name": name, "brief": ""}
        scene = get_scene(cid, chat) or {}
    in_region = sorted(
        str(room_id) for room_id, room in (scene.get("rooms") or {}).items()
        if isinstance(room, dict) and str(room.get("region") or "") == rid)
    return {"id": rid, "name": str(entry.get("name") or rid),
            "brief": str(entry.get("brief") or ""),
            "look": str(entry.get("look") or ""), "rooms": in_region}


# ---------------------------------------------------------------------------
# A townsperson's place (2026-09-05, DESIGN_CHARTER_PLACEMENT § the map). The
# REGISTRY is written, never the scene: a charter body's room is `place` and
# its within-room position its authored `station`, both on the body record
# (`world/charter_move.place_body` / `station_body`), read back next beat by
# the placement rule (`world/charter_place.py` rule i) and by the next
# `grid_view`. No positions row is ever stored for it.
# ---------------------------------------------------------------------------

charters_router = APIRouter(prefix="/api/chats/{cid}/charters", tags=["world-browser"])

#: What a townsperson's station PUT may carry.
CHARTER_STATION_FIELDS = ("room", "at", "cell", "facing")


def _charter_body_or_refused(registry, charter_key, body_key):
    """The charter state and the body record the route may author, or the
    refusal naming why not: an unknown charter or body (404, the known ones
    named), an authored person's body -- bound or reserved for a registered
    character (`body_of_an_authored_mind`), whose place is the cast editor's
    -- or a departed one, which stands nowhere (400)."""
    items = (registry or {}).get("items") or {}
    item = items.get(str(charter_key))
    if not isinstance(item, dict):
        known = ", ".join(sorted(items)) or "(none)"
        raise HTTPException(
            404, f"No charter '{charter_key}' in this story. Charters: {known}")
    state = item.get("state") or {}
    bodies = state.get("bodies") or {}
    body = bodies.get(str(body_key))
    if not isinstance(body, dict):
        known = ", ".join(sorted(bodies)) or "(none)"
        raise HTTPException(
            404, f"No body '{body_key}' in charter '{charter_key}'. Bodies: {known}")
    if body_of_an_authored_mind(state, str(body_key), body):
        raise HTTPException(
            400, f"'{body_key}' is an authored person's body -- bound or reserved "
                 "for a registered character -- and stands where the cast editor "
                 "puts them, not where the charter does")
    if body.get("departed"):
        raise HTTPException(400, f"'{body_key}' has departed and stands nowhere")
    return state, body


def _charter_row(cid, chat, scene, frame_id, charter_key, body_key):
    """The body's row as the Bodies tab lists it, after a write -- read back
    through `charter_body_records`, so the answer is what the next grid
    shows and not what the route thinks it wrote."""
    uid = placement_uid(charter_key, body_key)
    rows = body_rows(cid, chat, scene,
                     charter=charter_body_records(cid, frame_id, scene))
    return next((b for b in rows if b.get("uid") == uid),
                {"uid": uid, "charter": str(charter_key), "body": str(body_key),
                 "kind": CHARTER_KIND, "room": None})


@charters_router.put("/{charter_key}/bodies/{body_key}/station")
def charter_body_station_put(cid: int, charter_key: str, body_key: str,
                             body: dict = Body(...), frame_id: int | None = None):
    """Stand a townsperson somewhere: ``{room, at?, cell?, facing?}``.
    ``room`` is a live room of the scene (refused naming the known ones);
    ``at`` an anchor that room holds (`effective_anchors`, the implicit
    `door:<to>` ones included; refused naming them); ``cell`` ``[x, y]`` in
    the room's own grid, refused outside it naming the bounds, never
    clamped (`_cell_or_400`); ``facing`` a bearing (`_BEARINGS`), which
    needs an ``at`` or a ``cell`` to face from. A room other than the body's
    ``place`` moves it there first (`place_body`: the walk and errand it was
    on are dropped, its old station with them), then the station is authored
    (`station_body`, rule i of the placement); a move with no ``at``/``cell``
    leaves the body to the dealt rule in the new room. The same room with
    neither is refused: there is nothing to write. Refused for a body the
    charter does not own the place of (`_charter_body_or_refused`) and while
    a pipeline runs (409). The registry is read for update and saved for the
    chat's frame (`registry_for_update` + `save_registry`). Returns the
    body's row, read back through the placement."""
    chat = _chat_or_404(cid)
    _require_idle(cid)
    if not isinstance(body, dict):
        raise HTTPException(400, "Send {" + ", ".join(CHARTER_STATION_FIELDS) + "}")
    unknown = sorted(k for k in body if k not in CHARTER_STATION_FIELDS)
    if unknown:
        raise HTTPException(
            400, f"a townsperson's station has the fields "
                 f"{', '.join(CHARTER_STATION_FIELDS)} (got {', '.join(unknown)})")
    room = str(body.get("room") or "").strip()
    if not room:
        raise HTTPException(400, "A body needs a room to stand in")
    with _era(cid, frame_id):
        scene = get_scene(cid, chat)
        _live_room_or_400(scene, room)
        registry = registry_for_update(cid, frame_id)
        _state, rec = _charter_body_or_refused(registry, charter_key, body_key)
        cell = _cell_or_400(f"'{body_key}' cell", body.get("cell"), room_grid(scene, room))
        anchors = effective_anchors(scene, room)
        at = str(body.get("at") or "").strip() or None
        if at is not None and at not in anchors:
            held = ", ".join(sorted(anchors)) or "(none)"
            raise HTTPException(
                400, f"'{room}' has no anchor '{at}'. Anchors here: {held}")
        facing = _enum_value("facing", body.get("facing"), _BEARINGS)
        station = {}
        if at is not None:
            station["at"] = at
        if cell is not None:
            station["cell"] = cell
        if facing and not station:
            raise HTTPException(
                400, "facing needs an at or a cell: a body faces from where it stands")
        if facing:
            station["facing"] = facing
        moved = room != str(rec.get("place") or "")
        if not station and not moved:
            raise HTTPException(
                400, f"'{body_key}' already stands in '{room}'; send at or cell "
                     "to say where in it")
        if moved:
            place_body(registry, charter_key, body_key, room)
        if station:
            station_body(registry, charter_key, body_key, station)
        save_registry(cid, registry, frame_id)
        return _charter_row(cid, chat, scene, frame_id, charter_key, body_key)


@charters_router.delete("/{charter_key}/bodies/{body_key}/station")
def charter_body_station_delete(cid: int, charter_key: str, body_key: str,
                                frame_id: int | None = None):
    """Clear a townsperson's authored station (`station_body(..., None)`):
    the body falls back to its post's anchor, its walk's doorway or its
    dealt cell -- rules ii-iv of the placement. Idempotent; the same
    refusals as the PUT for the body and the pipeline. Returns the row."""
    chat = _chat_or_404(cid)
    _require_idle(cid)
    with _era(cid, frame_id):
        scene = get_scene(cid, chat)
        registry = registry_for_update(cid, frame_id)
        _charter_body_or_refused(registry, charter_key, body_key)
        station_body(registry, charter_key, body_key, None)
        save_registry(cid, registry, frame_id)
        return _charter_row(cid, chat, scene, frame_id, charter_key, body_key)
