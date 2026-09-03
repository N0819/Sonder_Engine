# Room geometry: a line of sight the Director cannot argue with

Status: PROTOTYPE, on a branch. Built 2026-09-02 in an isolated worktree
from a design conversation about deterministic mapping and navigation; every
number below was measured on that branch. Nothing here is merged. The
companion pieces — the planned-room handoff (§8) and the anchor schema (§2) —
landed in the same commit and are described here because they share the
seam.

The ask was "realistic geometry and object occlusion, rendered as text".
The answer is a derived layer, never stored, that reads what the scene
already persists — a room's size tier, its anchors with their bearings, each
body's station and pose and facing — and computes who can see whom, past
what, from where. It has the same shape as `agents/perception` and for the
same reason: geometry is a deterministic floor. The Director cannot decide
the guard saw her behind the counter, because the line did not reach.

---

## 1. Measured before anything was written

Read-only over the owner's live database (104 scenes, 571 rooms):

    rooms carrying anchors                        271 / 571   (47%)
    occupied rooms carrying anchors               145 / 243   (60%)
    anchors carrying a bearing                    796 / 827   (96%)
    anchors carrying any geometry field             0 / 827
    positioned bodies resolving a facing          212 / 785   (27%)
    bodies holding a measured station              86 / 785   (11%)
    station rows, and rows with `at`              151 / 83

So the cone would subtract on roughly a quarter of views today and body
occlusion on about a tenth, and both grow only as the Director writes
stations. The layer was built to be right at those rates and to cost nothing
at the others — see §4.

## 2. Schema (additive, optional)

On each room anchor, beside `desc` and `dir`:

    footprint   point | small | large | run     how many cells it takes
    height      floor | waist | head | full     what a line of sight is cut at
    opacity     opaque | see_through            whether it blocks sight at all

On each station, beside `at` and `near`:

    cover       true | <anchor_id>              the body is on the FAR side of
                                                its anchor -- between a counter
                                                and the wall, on the blind side
                                                of a screen

Three closed sets the ENGINE owns and reads (`world/spatial_fov.FOOTPRINTS`,
`HEIGHTS`, `OPACITIES`): a schema, not a vocabulary table, which is the
distinction CLAUDE.md draws. Unknown values fall to the default that
subtracts least (`point`, `floor`, `opaque`). `RoomDef.anchors` was already
`dict[str, dict]`, so the fields survive the Director's typed round trip;
`_ROOM_SILENT_WHEN_EMPTY` already keeps `anchors` from being blanked on
re-echo; `effective_station` already passed unknown station keys through and
named `cover` as the example. Nothing in commit, checkpoint, archive or
branch remap had to change: the fields ride the room and station records they
already persist. **One persistence surface not exercised:** no test on this
branch round-trips a geometry-bearing scene through `chat_archive` export and
import; the fields are plain keys on existing records and should survive, but
it is asserted, not measured.

Eye height comes from the body's own pose. `posture_class` reads the pose
record's `posture`, then the entity state's `posture`/`position`, by exact
token — the vocabulary `world/comfort._posture_of` already reads, plus
`crouching`, which is the posture this layer exists for. Unknown → standing:
the tallest eye sees most and the tallest body is most visible, which is the
direction that subtracts least.

## 3. Placement and the cast

    grid          one cell ≈ one pace; side by size tier
                  tiny 3 · small 4 · medium 6 · large 8 · huge 10 · vast 12
    wall anchor   placed on the wall its bearing names, at a seeded offset
                  keyed on (room uid, anchor id) -- so a later anchor never
                  moves an earlier one; two anchors may share a cell and the
                  cell blocks at the taller
    a THING       an anchor with a stated height, or a run/large footprint,
                  stands one pace off its wall, leaving the lane a body takes
                  cover in; a door, a window, a hearth is the wall itself
    interior      an anchor with no bearing sits at a seeded interior cell
    body          derived from its station -- `at`: one step room-side of the
                  anchor (`cover`: one step wall-side); `near`: beside that
                  body; nothing: unmeasured. NEVER stored.
    sight         recursive shadowcasting from the observer's cell; a cell
                  cuts the line when its height is level with the eye or
                  with the target's top; a supercover walk names what cut
                  it, or the tallest thing the line cleared (the "waist up")
    doorway       an open edge with a bearing casts into the neighbour's
                  grid, placed beyond a one-cell wall band with the two door
                  cells aligned; what stands in the neighbour occludes
    cone          relative_bearing's eight sectors over the cell vector:
                  front full, sides an impression, rear nothing -- only when
                  a facing is known; a deliberate look around is a sweep

## 4. The fail-open rule, stated as data

Every answer carries a `basis`:

    open   nothing could subtract -- the caller keeps every verdict it had
    cone   a facing put this feature behind the observer
    line   the observer's measured cell and an opaque anchor between

The layer may only subtract on evidence it has:

  * body occlusion needs BOTH bodies at a measured station (`at` or `near`),
    the same bar `measured_proximity_rel` sets for proximity -- a body with
    no station is somewhere in the room, and "somewhere" is not behind the
    counter;
  * the cone needs a facing, and never subtracts what is within reach;
  * feature occlusion needs the observer at a measured station;
  * a room whose anchors carry no geometry field composes BYTE-IDENTICALLY
    to before: no features sentence, the same percept data, the same dedupe
    keys (`test_a_room_without_geometry_composes_byte_identically` pins the
    key formulas; `test_a_degradation_is_a_failing_test` pins that evidence
    with nothing between subtracts nothing).

## 5. One sight decision

The verdict is folded into `visual_level_between`
(`world/spatial_senses.py`), the one function every sight decision goes
through. A body the line does not reach answers `none` there, so presence,
pose, appearance, the act channel, the micro-loop's `_delivery_ok`, the
observations and the memory episode all refuse it at once, with no second
copy of the rule anywhere (`test_an_occluded_body_is_absent_from_view_
observations_and_episode`, and the stage-level
`test_the_stage_itself_withholds_the_hidden_body`). What survives to the
composer is the PARTIAL case — a body seen over a counter from the waist up
— and a measured side where the anchor-bearing approximation had none.

## 6. Rendered as a person would say it

    BEFORE (no geometry authored):
      You are in the Taproom. Sawdust on the boards. Reya is across the room
      on your left, Keeper is across the room, and Hider is across the room on
      your right.

    AFTER (bar waist-high, screen head-high, Hider behind the screen, Keeper
    behind the bar; observer at the hearth facing north):
      You are in the Taproom. Sawdust on the boards. You can see the hearth
      within arm's reach, a folding screen at the edge of your sight, the long
      bar across the room, and the front door across the room on your left.
      Reya is across the room on your left and Keeper is across the room,
      behind the long bar, from the waist up.

    AFTER, turned to face the hearth:
      You are in the Taproom. Sawdust on the boards. You can see the hearth
      within arm's reach and a folding screen at the edge of your sight. Reya
      is across the room on your right.

Hider is gone from the page, the observations and the memory. Turning round
takes the bar, the door and Keeper out of view and changes the environment
percept's key, so the ledger reads the room as CHANGED for this observer,
not restated. No cell, fraction, degree or sector name reaches the text
(`test_rendered_text_carries_no_grid_vocabulary`). The English templates live
in `language_packs/en/cards/compositor.json` (`features`, `feature_item`,
`feature_glimpse`, `presence_behind`, `presence_shows`), mirrored in ja.

## 7. The Director's interface

The Director READS `payload.sightlines` — `spatial_fov.sight_digest` over the
player and cast: who sees whom, who is hidden behind what, who is seen from
the waist up over what, who is within reach of whom — on `director_establish`,
`director_resolve` and the spatial hand's payload. A pair the layer has no
evidence about reads as open, never hidden, so nothing here can talk the
Director out of a body it can plainly place.

It DECLARES only through channels it already owns: a station `at`/`near` an
anchor, the station's `cover`, a pose, a facing (through focus). A deliberate
look around is the existing explicit-look intent, which now also turns the
observer through the whole room for that beat. Geometry never moves anything
and never overrides a position write; perception is composed from the
geometry regardless of what the prose implies.

Two clauses, one per chunk (`specialists/spatial/chunks/rooms.txt` and
`stations.txt`), each stating a class: AN ANCHOR IS A THING WITH A HEIGHT,
and WHICH SIDE OF THE FIXTURE. Ledgered in `EXPECTED_DIVERGENCE.json`,
mirrored in ja.

## 8. The planned-room handoff (same seam, same commit)

The charter/structure planner lays out rooms with a purpose and adjacency
(`room_registry.payload.planned`); the live scene received them as prose-free
stubs (`structure.materialize_planned_fringe`) and the seed reached a model
in exactly one place — the mapping stage, only when `interp.location_query`
named one planned room — while the spatial sheet said nothing about stubs
and the mapping card said keep a minted room minimal. A persona walking a
planned town saw rooms that kept their planned names and exits and stayed
bare.

Now: `structure.rooms_to_develop` (the focus room, the movement target, every
non-wall neighbour — deterministic, no prose) selects; `planned_room_brief`
hands purpose, access, exits and the structure grammar as
`payload.planned_rooms` to `director_establish`, `director_resolve` and the
spatial hand; the rooms chunk's clause A ROOM YOU ARE HANDED AS PLANNED
EXISTS AND IS YOURS TO FURNISH licenses the write on entry or in view whether
or not the prose described it — the one stated exception to "encode only
what the beat asserts". At commit `protect_planned_edges` restores a planned
exit a development dropped and `settle_developed_stubs` drops the flag and
the seed from a stub that now carries a desc. The seed reaches no mind
(`test_the_seed_reaches_no_view_and_no_observation`); the mapping
`planned_context` path is unchanged and pinned.

## 9. Cost

    one observer view, huge room, 20 anchors, 8 bodies    6.3 ms median
    all 8 observers                                       49.5 ms
    one body_visibility                                    0.8 ms
    sight_digest over 9 bodies (72 pairs)                 54 ms
    perception_act, 4 bodies, taproom:
        geometry room, hook live                         107 ms
        hook stubbed open (the pre-layer path)           102 ms
        room without geometry                            111 ms

The anchor placement is memoised on the room's own inputs (`_ANCHOR_CACHE`),
which halved the first numbers. Per turn the digest is computed three times
(establish or resolve payload, interpret extras) and perception runs twice,
so a huge room with nine stationed bodies adds on the order of a quarter of a
second of pure Python; an ordinary two-body scene adds milliseconds.

## 10. What argues against it

  * **It bites on a quarter of views today.** Facing resolves for 27% of
    bodies and stations for 11%. Until the Director writes stations more
    often — and `cover` at all — most of this is machinery waiting for its
    input. The clauses ask for the input; whether the model supplies it is a
    play-test question, not a schema one.
  * **A 2D grid at one pace.** No elevation, no partial transparency, no
    light per cell beyond the room's own light, no occlusion of sound (right)
    or scent (right). A balcony, a pit and a stairwell are not modelled.
  * **Placement is seeded, not authored.** The bar is somewhere along the
    north wall, not at the end the prose put it. When a scene's prose is
    specific about where two features stand relative to each other, the grid
    may disagree, and the grid wins for sight. Nothing surfaces that
    disagreement.
  * **`cover` on an interior anchor is relative to the room's centre.** A
    body behind a free-standing screen is hidden from the centre side and
    exposed from the other, which is right for a screen and meaningless for
    a pillar.
  * **Two doorways on one wall cannot both cast.** The second neighbour whose
    grid would overlap the first is skipped, and reads as open.
  * **The `_visible_features` opt-in is per room.** A room with one geometry
    field on one anchor gets the features sentence for ALL its anchors, so a
    Director that annotates one counter changes what the room's whole view
    says. That is arguably the point, and it is a behaviour change for that
    room.
  * **Archive round-trip unmeasured** (§2).

## 11. Files

    world/spatial_fov.py                 the module (exported via world/spatial.py)
    world/spatial_senses.py              visual_level_between asks the line
    agents/composer.py                   environment features; presence behind/shows
    agents/perception.py                 _visible_features; the sweep flag
    agents/director_movement.py          _sightlines_view, _planned_rooms_view
    agents/director.py, director_fanout.py   payload.sightlines, payload.planned_rooms
    world/structure.py                   rooms_to_develop, planned_room_brief,
                                         protect_planned_edges, settle_developed_stubs
    persist/commit_scene_state.py        the two seams before the fringe
    language_packs/*/cards/compositor.json          templates
    language_packs/*/cards/system_prompts/specialists/spatial/chunks/{rooms,stations}.txt
    tests/test_room_geometry.py          30 tests
    tests/test_planned_room_handoff.py   11 tests
