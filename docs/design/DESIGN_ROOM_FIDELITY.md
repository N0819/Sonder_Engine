# Room fidelity: one record, rendered three ways

Status: PROTOTYPE, on a branch. Built 2026-09-04 in an isolated worktree
from the owner's ruling of the same day: a room is minted ONCE and rendered
three ways -- prose by the composer, sight and light by the geometry, a
picture by the backdrop agent -- so every fidelity field on the room record
is chosen because all three read it. Every number below was measured on a
copy of the owner's database (104 scene rows, 589 rooms; chat 111 excluded).
The companion notes are `DESIGN_ROOM_GEOMETRY.md` (the grid this widens) and
`DESIGN_ROOM_REGIONS.md` (the registry the picture's `look` lives in).

The live cases this answers, from `docs/experiments/DEBUG_RUN_2026_09_04.md`:

  * **F3** -- a bare compass word minted a room called "West": a bearing is
    not a place, and nothing checked the plan's geometry before it became
    rooms. The lint (§3) is the deterministic layer that reads a scene's
    bearings and extents and says where they cannot all be true.
  * **F16 / F22** -- one door, two answers, and sight following the side you
    stand on. The merge now mirrors a barrier (landed the same day); the
    passage record (§5) is the design that makes the door ONE object so
    the question cannot arise, and it is designed here and not built.
  * **F18** -- a pose detail asserted a percept through a closed door whose
    room the description called glass. The backdrop brief (§4) is built from
    the same edges perception reads, so a picture cannot show a window the
    geometry says is a door; the vocabulary gap (`window` exists, the
    Director chose `closed_door`) is a prompt matter and is not touched.
  * **F27** -- a station anchor owned by two rooms because one door has an
    anchor on each side. The lint's overlap and embedding checks read anchors
    ROOM-scoped, as every writer does, and never search scene-wide.

---

## 1. Measured before anything was written

Read-only over the copy (`/tmp` scratch; the original was never opened):

    scene rows / rooms                                104 / 589
    rooms carrying authored anchors                   273 / 589   (46%)
    authored anchors / effective (with implicit doors) 831 / 1765
    authored anchors by wall class
        north-south walls                             314
        east-west walls                               360
        corners (diagonal bearing)                     23
        no bearing (interior)                         134
    exits by wall class
        north-south                                    95
        east-west                                     248
        corners                                         2
        no bearing                                    578
    rooms by size tier (derived, `effective_room_size`)
        small 161 · medium 250 · large 177 · vast 1 · tiny 0 · huge 0
    anchors per room (authored)  0:316 1:44 2:76 3:49 4:46 5:48 6:9 10:1
    rooms with two exits on one wall                    7
    rooms whose one wall carries more anchor cells
      than the tier side can hold                       0
    rooms carrying `extent` or `shape` today            0 / 0

Two things fall out. Every room in the corpus is a SQUARE today, so every
wall is the same length and the question "long wall or short wall" has no
answer yet: the 314 north-south and 360 east-west wall anchors are the
population that MOVES the first time a Director writes `extent` on a room
whose proportion matters -- on a wide room the north-south anchors sit on
the long wall and the east-west ones on the short; on a deep room the
reverse. And 578 of 923 exits (63%) carry no bearing at all, which bounds
what any geometry can do: a doorway with no wall cannot be placed, cast
through, or drawn.

## 2. Shape and extent (`world/spatial_fov.py`, `world/spatial_geometry.py`)

Three optional fields on the room record, beside `size`:

    extent   {w, d}        paces east-west and north-south; each clamped to
                           [EXTENT_MIN_PACES, EXTENT_MAX_PACES] = [2, 24]
    shape    rectangle | round | l        SHAPES, a closed set the engine owns
    parts    [{w, d, at}]  for `l` only: rectangles placed at a corner word
                           (ne | se | sw | nw) of the room's bounding box

Absent, the grid is exactly the square the size tier gave it before this
note (`GRID_SIDE`): `test_room_shapes.py::test_a_room_without_extent_composes_byte_identically`
pins that every existing test scene's anchor cells, body cells, walls and
rendered view are unchanged byte for byte. The cache key that memoises anchor
placement carries the grid's signature, so the memo cannot serve one shape's
cells to another.

**Why paces and not a size word.** `size` is FLOOR -- "how much floor there
is to cross", the spatial hand's own definition -- and one word cannot say
that a corridor is long. So `extent` is the measurement and `size` is derived
from it when both are present: the tier of the equal-area square,
`size_from_extent` (`sqrt(w*d)` against the tier sides' midpoints), so a
3x12 corridor is `medium` floor with a long proportion, and the prose word
and the grid never disagree. A Director that writes both and disagrees is
reported by the lint (`size_disagrees_with_extent`), never silently
overruled -- but the grid follows the measurement.

**Where an anchor sits.** A wall anchor is placed on the wall its bearing
names, at a seeded offset along THAT wall's length, so the north anchor of a
wide room sits somewhere on the long north wall and the east anchor of the
same room on the short east wall. The corner cell for a diagonal bearing is
the shape's extreme cell in that direction. An anchor with no bearing sits
at a seeded interior cell of the bounding box, snapped to the nearest cell
the shape contains (a round room's corner is not the room).

**Round.** The cells whose centres lie within the inscribed ellipse of the
bounding box. A "wall" of a round room is its rim facing that bearing -- the
cells inside whose neighbour in that direction is outside -- so the north
anchor of a round room sits on the northern arc, and a doorway on the arc is
a gap in the wall line exactly as on a straight wall.

**L.** The union of two rectangles, each placed at a corner of the bounding
box. The bounding box is `extent` when given, else the widest part by the
deepest part. By construction one part spans the full width and one the full
depth, so the union is connected whenever they are different parts; a part
contained in another is a rectangle wearing the word and the lint says so
(`l_part_redundant`). The notch is not the room: its cells are outside
`inside`, so a line through it is a line through a wall, and the field
contract needed nothing new to say so.

**The field contract is unchanged.** `_Field.inside`, `.height`,
`.occluder`, `.offsets`, `.anchors`, `.walls` (`{axis, coord, extent,
aperture, to}`), `cell_of`, and every public signature are what they were;
the light-field sibling reading `observer_field` sees the same shapes with
more cells in them. What changed underneath: `_Field.add_room` iterates the
shape's cells rather than a square; a wall's `extent` runs over the two
rooms' bounding boxes along that axis rather than two equal sides; the
neighbour-overlap test in `observer_field` tests the neighbour's actual
cells, so a wide room with two small neighbours off one long wall can now
cast through both doorways (the GEOMETRY note's §10 residual, half
answered: the neighbours must still fit).

**Fail-open, stated as data.** An unreadable `extent` (prose, a negative, a
missing side) is None at the schema (`RoomDef._coerce_extent`, the
`_positive_float_or_none` shape) and None at the reader
(`normalize_extent`), so the room is the tier's square; an unknown `shape`
is `rectangle`; `parts` on a non-`l` shape are ignored by the grid and
reported by the lint. Nothing here can make a room SMALLER than a Director
meant without a readable number saying so.

## 3. The layout lint (`world/spatial_lint.py`, behind `world/spatial.py`)

Deterministic, pure over the scene dict, and it READS NO PROSE: not `desc`,
not `name`, not `notes`. Rows, never fixes -- the `contradictory_sight_edges`
precedent: surfaced once on appearance as a commit warning (the
`layout_lint_told` flag plays the part `sight_contradictions_told` plays),
and always in the Room's `inspect_contradictions` under `layout`.

    kind                          what it read
    reciprocal_bearing_disagrees  A->B is `dir` x and B->A is `dir` y with
                                  y != opposite(x): the pair `_shield_standing_bearings`
                                  refuses to re-bear one-sidedly, reported when
                                  a scene already holds it
    openings_overlap              two doorways on one wall whose placed door
                                  cells share a cell
    wall_overfull                 one wall's anchors need more cells than the
                                  wall has (point 1, small/large 2, run the
                                  wall less two)
    corner_in_round_room          `parts` (corner-placed) on a `round` room
    l_part_redundant              an `l` whose one part contains the other
    shape_disconnected            a shape whose cells are not one component
    rooms_overlap_when_placed     placing rooms by bearing with the composite-
                                  field rule (door cells aligned beyond a one-
                                  cell band) lands two rooms on the same cells:
                                  the bearing set cannot be embedded on a plane
    size_disagrees_with_extent    authored `size` is not the tier `extent` gives
    extent_unreadable             `extent` present and not `{w, d}` in paces

Measured over the copy (§7): 9 rows in 4 of 104 scenes, 0.20 s for the
whole corpus. The embedding check is the expensive one -- it lays out every
connected component of beared, non-wall edges once -- and it is the one that
answers F3's class from the geometry side: a plan whose bearings cannot be
drawn is a plan with a room in the wrong place, and the lint names the pair.
Where a doorway's two bearings already disagree, the collision that follows
is that row's consequence and is not reported twice.

## 4. The backdrop brief (`dressing/backdrops.py`)

`room_projection` is still a whitelist and still has no concept of an
occupant; it gains five keys, each derived from the room record alone:

    walls       {n|e|s|w|ne|se|sw|nw|free: [{desc, height?, footprint?}]}
                the authored anchors grouped by the wall their bearing names,
                `free` for a bearingless one; implicit door anchors are not
                walls, they are openings
    openings    {<wall>|unplaced: [{barrier, name?, vertical?}]}
                the exits by wall with their barrier state; never `to`
    proportion  one sentence from extent/shape/size -- "a long room, three
                paces wide and twelve deep" -- English, like every string an
                image model is handed
    camera      {from, looking, framing} -- the room's main entrance, the
                first passable exit in compass order (n, e, s, w, then by
                target id), looking in, "level, wide"; a room with no placed
                passable exit has no camera and the prompt says nothing
    look        the region registry's `look` string, when the region carries
                one (`world/regions.py`; see below)
    lighting    RESERVED. Not computed here. When the light-field sibling
                lands a lighting sentence it goes in this slot and
                `compose_prompt` reads it in place of the light word.

`visual_signature` keys on `walls`, `openings`, `camera`, `proportion` and
`look` too -- so a fixture moved to another wall, a door opened, a region
given a look, is a different picture, and a bystander is not
(`test_backdrop_brief.py::test_a_bystander_is_still_not_a_new_picture`).
Two costs, named. **Every existing backdrop is redrawn once:** any room with
an exit or an anchor now hashes differently, and the owner's install holds
299 images across 74 chat directories, so the next visit to each room pays
one generation. **One standing defect closes with it:** `exits` reached the
prompt and not the key, against this module's own rule that the key is a
function of what reaches the image, so a door opening never redrew the
room; it does now.

**The camera behind `backdrop_continuity`.** With the setting on, the
picture may be taken from where the VIEWER stands: their measured cell
(`body_cell`, never stored) as a part-of-the-room word and their facing.
The reason it is gated: continuity makes every later picture of a room an
EDIT of its first, so a re-angled view is the same room turned rather than a
fresh invention; without continuity a viewer-camera would mint a new room
per angle. The cost, named: more images per room -- one per (part of the
room, facing) the viewer stands in, up to eight facings by nine parts, where
today a room costs one picture per visible state. Off, the camera is the
entrance and a room is one picture. `room_projection(..., viewer_camera=True)`
is the switch; `build_backdrop_request` reads the setting.

**`look` on the region.** `world/regions.py`'s registry record gains an
optional `look` string -- the visual register of a part of the map ("brick
and iron under sodium lamps"), the thing a picture of any room there should
share. Present only when set, so `normalize_regions` keeps the shape the
regions tests pin. It is WRITTEN by `regions.set_region_look(cid, frame_id,
region_id, look)`, which exists and which nothing in the Room calls yet:
there is no Room tool that writes the registry (only `ensure_regions` at
commit, which enters names), so the writer is the seam and the tool is
registered in `docs/UNBUILT.md`. Until then a host sets it the way any
frame-scoped world key is set.

**The draft.** `compose_prompt` builds the draft from the brief outward: the
proportion, then each wall with what stands on it and what opens in it, then
the camera, the look, the light. The agent card (`backdrop_prompt.txt`)
changed ONE clause -- the paragraph naming what it receives -- to state the
class: compose from the walls outward, light as stated, the centre empty. The
HARD RULES paragraph is byte-identical in both packs.

## 5. The passage as one object (designed; NOT built)

F16 and F22 are one class: a doorway is stored as two edges and the two can
disagree. `_mirror_symmetric_barriers` closes the common case at merge, and
`_shield_minted_edges` the seal; the design that removes the class is one
record per doorway:

    scene.passages[id] = {rooms: [a, b], barrier, name, material, width,
                          vertical, state}
    rooms[a].adjacent[i].passage = id        (and the same id on b's edge)

Readers resolve the barrier THROUGH the passage when the edge names one
and per-edge as today when it does not (fail-open: an old scene reads
exactly as before). The merge keeps both in sync -- a barrier written on
either edge writes the passage, and a passage write writes both edges --
with `_mirror_symmetric_barriers` staying as the fallback for edges with no
passage. Archive, checkpoint and branch ride free because the scene is one
blob; the registry projection is untouched because a passage is not a room.
`width` in paces gives the doorway's aperture (`_door_cells` reads it in
place of the door anchor's footprint), and `state` is where a latch, a bar,
a wedge lives -- F22's "latched" against `open_door` becomes a state on one
object rather than prose against an edge.

Why it is not built here: the readers are `spatial_rel`, `effective_adjacent`,
`neighbor_map`, `_sight_neighbours` and the door-anchor derivation in
`effective_anchors` -- five, across `spatial_routing.py`, `spatial_barriers.py`,
`spatial_fov.py` and `spatial_geometry.py` -- and the merge seam is the
block `_mirror_symmetric_barriers` sits in. The light-field sibling is
editing `spatial_routing.py`'s light key and `spatial_merge.py`'s durable
entity fields in the same window, and a fail-open reader change in five
places is not the "additive and small" this worktree was held to. Registered
in `docs/UNBUILT.md` with this design.

## 6. Constants the owner sets

    EXTENT_MIN_PACES = 2      a room narrower than two paces is a passage,
                              not a room; `transit_seconds` is for those
    EXTENT_MAX_PACES = 24     twice the `vast` side; the shadowcast is
                              O(cells) per observer and 576 cells is the
                              ceiling this note accepts without measuring
    SHAPES = (rectangle, round, l)
    ROOM_CORNERS = (ne, se, sw, nw)   where an `l` part may sit
    CAMERA_WALL_ORDER = (n, e, s, w)  which entrance is "main" when several
                                      are passable: compass order, then id

## 7. Measured after

Run over the same copy with the built lint (no scene was changed; the corpus
carries no `extent`, so the shape checks cannot fire on it and the numbers
say what the corpus already holds):

    rows in total                                       9, in 4 of 104 scenes
        openings_overlap                                3
        rooms_overlap_when_placed                       6
        reciprocal_bearing_disagrees                    0   (`normalize_scene_bearings`
                                                             already drops such a pair)
        every shape and extent check                    0   (nothing to read)
    lint time, whole corpus                             0.20 s

The nine, because they are evidence: chat 22's bridge has the ready room
and the observation lounge on one north wall, placed on the same cells; chat
27's shelter has three rooms that land on the west lower descent when the
bearings are followed; chat 74's hotel lobby -- the chat the CLAUDE.md
investigation rule was written on -- puts the back office on the lift; chat
84's elevator hall opens the interview cell and the first-floor hallway
through one west wall. None of these is a room the corpus knew was wrong.

**The fail-open claim, measured:** the pre-change `spatial_fov` (from the
branch's base commit, loaded beside the built one) and the built one agree on
every room and every body in the corpus -- anchor placement identical for
589 of 589 rooms, body cell identical for 783 of 783 positioned bodies, the
observer field (cells, heights, occluders, offsets, walls) identical for 783
of 783 -- because no room carries `extent` or `shape` and the rectangle path
with `w == d == GRID_SIDE[tier]` executes the same arithmetic.
`test_room_shapes.py::test_a_room_without_extent_composes_byte_identically`
pins the reduction against the pre-change formulas copied into the test, for
every anchor kind on every size tier.

## 8. What argues against it

  * **The Director has to write it.** 0 of 589 rooms carry an extent today.
    The clause asks for one where proportion matters; whether the hand
    supplies it is a play-test question.
  * **A rim is not a curve.** A round room's wall anchors sit on rim cells,
    and a doorway on the arc is judged as a gap in an axis-aligned wall line
    between the two rooms' bounding boxes. Right for sight through the
    doorway; the arc itself is a staircase of cells.
  * **`size` derived from area loses one distinction.** A 2x18 gallery and a
    6x6 room are both `medium` floor. That is the definition of `size`, and
    the proportion sentence carries the difference to the picture; the
    proximity ladder (`near`/`across`) still reads the tier, so two bodies at
    the far ends of the gallery grade as they did before.
  * **The lint's embedding check reads only beared edges.** 578 of 923 exits
    have no bearing and cannot be placed, so a contradiction that runs
    through one of them is not seen.
  * **The viewer camera multiplies pictures** (§4), and it is off by default
    for that reason.
  * **The passage record is a design** (§5).

## 9. Files

    world/spatial_geometry.py        EXTENT_*, normalize_extent, size_from_extent,
                                     effective_room_size reads extent first
    world/spatial_fov.py             SHAPES, ROOM_CORNERS, room_grid/RoomGrid,
                                     the shape-aware placement, walls, field
    world/spatial_lint.py               the lint (exported via world/spatial.py)
    world/regions.py                 `look` on the registry record; set_region_look
    llm/schemas.py                   RoomDef.extent/shape/parts
    world/spatial_merge.py           _ROOM_SILENT_WHEN_EMPTY += extent, shape, parts
    persist/commit_scene_state.py    the lint's once-on-appearance warnings
    story/room_tools.py              inspect_contradictions["layout"]
    dressing/backdrops.py            the brief, the camera, the signature, the draft
    language_packs/*/cards/system_prompts/specialists/spatial/chunks/rooms.txt
    language_packs/*/cards/system_prompts/prompts/backdrop_prompt.txt
    tests/test_room_shapes.py, tests/test_room_lint.py, tests/test_backdrop_brief.py
