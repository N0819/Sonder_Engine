# Design: where a charter body stands in its room

**Status: BUILT 2026-09-05** (`world/charter_place.py`,
`tests/test_charter_placement.py`). The map half -- drawing the placed bodies
on the World Browser's grid and dragging them -- is the follow-up registered
in [`docs/UNBUILT.md`](../UNBUILT.md) §1.10b.

## The gap, measured in the code

A charter body's location was `place`, a scene room id written only by the
movers (`world/charter_move.py`). Within the room it had nothing, and it never
entered `scene.positions`. Four readers each improvised around the one
missing object:

| reader | what it did |
|---|---|
| `world.spatial.observer_field` | laid no cell for it, so the sight, light and sound grids did not know it existed |
| `agents.perception._presence_bodies` | wrote a bare positions row onto the stage's scene copy, so the body was graded by ROOM: `body_visibility` answered open (no measured station on its side), `light_at` answered the room's median light -- dim light could not hide one townsperson and show another, and a body behind a screen was seen |
| `charter_observe._observer_scene` | faked a positions row for the observing body alone, so a townsperson's own eye was graded by room, never by line |
| `charter_runtime.charter_carriers` | vouched for a holder by room, because the scene had no record to hand the transfer ledger |

And a fifth, found while building: the merge does not DROP a Director
`positions` entry naming a townsperson -- `merge_scene_with_diff` updates the
position map blind -- so such a move committed as a SECOND positions row in
the stored scene, disagreeing with the registry's `place` from the next beat
on. `_unreachable_position_writes` never route-checked it either, because the
floor reads a mover's origin off the scene and the scene stood the body
nowhere: the Director could walk a townsperson through a wall unobjected.

## The owner's ruling

> "its fine if charter npcs don't have a position when not being observed by
> a player or major character. It's just a massive problem if they don't when
> present in a scene, or cannot navigate a room while being handled by the
> pipeline."

So: the unobserved body has a DEALT position that is stable per (body, room)
across beats; a body present in a scene has a STATEFUL position -- whatever
the pipeline wrote to it lands and is read back next beat; and the movement
floor judges a townsperson's move exactly as it judges a cast member's.

## The rule

A body stands at ONE of four places, tried in order (`charter_place.
_station_and_facing`):

1. **The body's own authored `station`** -- one new optional field on a body
   record (`charter_model.normalize_body_station`): `{"at": anchor}` or
   `{"cell": [x, y]}` (a cell of its room's own grid, `normalize_cell`),
   optionally with `near` and `facing`. Host-written: the map's drag, or a
   Director `stations` entry routed at commit. Snapped to a cell the room's
   shape keeps (`RoomGrid.nearest`) at read. FIRST, because it is the more
   specific and the later fact: the beat that stood the clerk at the door said
   so about HER, where the post's anchor says where clerks in general stand,
   and a Director station the post overrode next beat would be exactly the
   snap-back the ruling forbids. **Cleared by every writer of `place`** --
   `charter_move._advance` (a walk leg), `charter_move.place_body` (a scene
   move), the bound-body sync in `charter_runtime.advance_snapshot`,
   `charter_intervene`'s lair move, and the normalizer for a body whose place
   is empty -- the same rule `invalidate_moved_body_cells` applies to a scene
   body's pinned cell: a cell or an anchor names nothing in another room.
2. **The post on watch names an `anchor`** -- one new optional field on a post
   record (`charter_model.normalize_post`): "where in its place the duty is
   stood, as one of the room's fixtures", the id of an anchor of the post's
   `place`. The clerk stands at the counter. Fail-open: an anchor the room
   does not carry is ignored, no lint, no warning -- the normalizer cannot see
   the scene, and a planner naming a fixture the room lacks has made a small
   mistake, not a movement. The generator prompt states the class only
   (`world/charter_generate.py`, `_PLAN_SYSTEM`).
3. **A body mid-walk** (`charter_move.en_route`) stands at the doorway toward
   its next leg -- the implicit `door:<next>` anchor `effective_anchors`
   contributes -- where a courier held at a gate stands.
4. **Otherwise a DEALT cell**, from the identity seed `charter:<charter>:<body>`
   and the ROOM ID and nothing else (`_lane`, blake2b under the salt `place:`,
   the surface's dealing law). Byte-identical on replay and stable across
   beats: the turn never enters the seed, so a body nobody has touched does
   not wander. Dealt among the cells the room's shape keeps that no anchor
   occupies (a body does not stand in the hearth); two bodies may share a
   cell, as two may share an anchor.

**Facing** follows the same order: an authored `facing` where the station
carries one, else the anchor's own bearing for (1)-at and (2) (toward the
anchor's wall), the doorway's bearing for (3), and dealt for (4) and for an anchor
with no bearing -- dealt, because a body at a table faces SOME way, and
`effective_facing`'s "never guessed" rule protects Director declarations, of
which there are none for a townsperson.

**Poses** for an unpromoted body are out of scope: a pose rides the scene's
`poses` ledger for scene bodies, the registry body has no pose store, and a
townsperson's posture is `charter_feel`'s and the voice's to describe. A
Director `poses` or `orientation` entry naming a charter body is neither
routed nor stored; its `facing` is derived as above.

## The view

`charter_place.scene_with_charter_bodies(scene, placements)` is a SHALLOW
copy of the scene whose `positions`, `stations` and `orientation` gain one
derived row per placed body. The stored scene is never touched and the view
is never persisted -- the crowd's rule (DESIGN_BACKGROUND_PRESENTATION Part
B). It is keyed by the body's **display name** (the spelling every other seam
speaks) when that name is unique across the registry, and by the permanent
uid `charter:<charter>:<body>` when it is AMBIGUOUS -- a name two people
share is withheld from every view (`background_presence_records`), and a
positions dict has one slot per key. A body the scene already stands
(`room_of` answers: the Director minted an entity for it, or it is a
registered character) is left alone entirely; the scene owns it.

Only the observer's room and the rooms `room_field` lays beyond its open
doorways are ever laid (`rooms_in_frame`). Measured at Harrowmere scale (100
bodies, 30 rooms with geometry, 3 rooms in frame): **10 bodies laid in
1.7 ms per beat**; the evidence pass, which asks about every body, lays all
100 in 12.6 ms.

### Who reads it

| reader | before | now |
|---|---|---|
| `agents.perception._presence_bodies` | a bare positions row | `presence_figures_for_room` carries each row's `placement`; the stage lays position, station and facing on its own scene copy (`lay_charter_bodies`), so `visual_level_between` finds a measured station on both sides and asks `body_visibility` what stands between, `light_at` reads the body's own cell, the sound field seats it at its cell. The rooms beyond the observer's doorways are laid too, so a townsperson seen through a door is graded by the doorway cone like a cast member there |
| `charter_observe.plan_public_evidence` | `_observer_scene`, the observer alone by room | `observer_view`: every unbound body of the charter at its cell on one view per plan; the observing body's eye is graded by line and light and it listens at its cell. The sensory cache is keyed by (source, place, station, facing), not by place alone. `_observer_scene` survives only as the fallback for a body whose place is no room the scene holds |
| `agents.director` movement floor | never route-checked a townsperson (no origin on the scene) | `common.charter_view_for_rooms` builds the view before `_unreachable_position_writes` runs and adds the bodies' keys to the floor's roster: a townsperson walking through an open door lands, one written through a wall is refused with the cast's own warning |
| `agents.common.present_charter_figures` (the Director's payload) | name, role, room, look | plus `station` and `facing`, so the objects and social hands can reason about who is beside what |
| `charter_runtime.charter_carriers` | vouches by room | unchanged: the transfer ledger needs a room, and the room is still `place`'s |

## The routing: a Director move of a townsperson is the registry's to land

`charter_place.resolve_scene_placements(registry, diff, scene)` (pure) says
which of a diff's `positions` and `stations` entries name a charter body the
scene does not stand -- by the spelling table `charter_carriers` builds (body
key, uid, name, display name, authored aliases), a spelling two bodies share
being nobody's. `charter_runtime.route_scene_placements` STRIPS those entries
from the commit's copy of the diff in `prepare_scene_commit`, before the
merge, so the scene stores no row; `charter_runtime.apply_scene_placements`
lands them in `commit_scene`, inside the turn's transaction: the room through
`charter_move.place_body` (place set, `walk` and `errand` dropped so no
charter route competes with what the scene just did, `station` cleared), the
within-room entry through `charter_move.station_body`, and one
`save_registry`. `place` stays the ONE owner of the room and `station` the one
owner of the within-room position.

Not `relocate`, deliberately: `relocate`/`walk` dispatch a body along a route
the charter planned and pay for it window by window. A Director `positions`
entry is a fact the beat already resolved -- she is in the next room NOW.

The next charter catch-up (`advance_snapshot`) starts from the landed
`place`, as it already did for a bound body whose place the scene sync
copies. A body the pipeline moved out of the observed rooms goes back to
simulation from its new `place` with no station -- the "unobserved is fine"
half of the ruling.

## What is deliberately not stored

No positions row, no station row, no orientation row for an unpromoted body,
ever, in the scene. Two optional fields on the registry blob -- `posts.*.
anchor` and `bodies.*.station` -- and nothing else; a registry from before
either existed is byte-identical on read and write.

## Firewall

A placed body is a PRESENCE fact for observers who can see its cell, graded
by light and line exactly as cast are; the post and its anchor are not a
label the observer receives (the stranger label stays `charter_surface`'s).
The rows exist so the SUBTRACTING guards can run at all -- which is the
firewall's own direction. The Director, which owns what exists, is shown the
placement whole. A withheld ambiguous name is keyed by a uid no label is ever
cut from, so `presence_has_an_identity` and the stranger label hold.

## Bodies are not occluders

In this engine's sight model only ANCHORS occlude (`_Field.add_room` lays
anchor heights; bodies are targets, never blockers) -- for cast as for
townspeople. A charter body therefore does not shadow a cast member's line
either. Making bodies occlude is a spatial-model change in
`world/spatial_fov.py`, not a charter one, and is not made here.

## The map follow-up (UNBUILT §1.10b)

`web/world_routes.py`'s `grid_view` lays bodies from `scene.positions`; the
placed townspeople are on the view, not the store, so the map does not draw
them yet. The seams the map's drag will call already exist:

* `charter_move.place_body(registry, charter, body, room)` -- the room half;
* `charter_move.station_body(registry, charter, body, station)` -- the
  within-room half, `station` as `{"at": anchor}` or `{"cell": [x, y]}`,
  optionally `near`/`facing`; `None` clears it;

both through `registry_for_update` + `save_registry`. The route to add:
`PUT /api/chats/{cid}/charters/{charter}/bodies/{body}/station` with body
`{"room": <room id>, "at": <anchor id>}` or `{"room": <room id>, "cell":
[x, y]}`, plus `grid_view` gaining a `charter_bodies` block from
`charter_placements(registry_for(cid, frame), scene, frame_rooms={room})`
keyed by uid, carrying `name`, `cell`, `facing`, `source` and `presented`.
