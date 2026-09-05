# Design: decibels, and how far a very loud sound goes

**Status: BUILT 2026-09-05** on `writers-room`, in the same worktree as the
note, against the sound field built and repaired the day before
(`world/spatial_sound_field.py`, `docs/design/DESIGN_SOUND_FIELD.md`).
Written after the owner asked for "a db system so that incredibly loud noises
can travel very far". §§ 2-4 are built as written except where § 5a says
otherwise; every constant is marked built or still proposed in § 5, and what
was registered rather than taken is in `docs/UNBUILT.md` § 1.122.

## 1. What was true before, measured in the source

  * **The field was one hop wide.** `spatial_fov.room_field` lays the room
    and the neighbours placed beyond its own doorways, and nothing further
    (`_placed_neighbours`). So a sound two rooms away was not quiet: it was
    ABSENT. No constant could change that, which is why this note is mostly
    about reach and only a little about scale.
  * **A wall passed nothing.** `APERTURE_PASS["wall"] = 0.0`. Right for
    sight, which is what the table was borrowed from. It meant no explosion,
    ever, was heard through a wall by anyone.
  * **Decay is inverse-square in path length**, `pass / (1 + L^2)`, and the
    ladders were linear powers: speech `mutter 0.6 | whisper 1 | normal 12 |
    loud 40 | shout 120`, sources `faint 1 | audible 12 | loud 40 |
    deafening 150`. The top of the source ladder was 12.5x a normal voice.
    A cannon, a collapsing roof, a dragon and a ship's horn had no rung.
  * **A sound that HAPPENED had no channel at all** (`docs/UNBUILT.md`
    § 1.117): `running` is a state, and a bell rung once either became a
    permanent source or reached nobody.

## 2. What was built

### 2A. Decibels are the same curve written in logs

Every level is a sound pressure level and every loss a subtraction, with
`L_dB = 10*log10(P) + DB_REF`. Today's `P * pass / (1 + L^2)` is exactly
`L0 - 10*log10(1 + L^2) - pass_dB`, and the two thresholds are exactly
`FULL +10*log10(2.0) = +3.01 dB` and `FRAGMENT +10*log10(0.8) = -0.97 dB`
over the noise. The conversion is arithmetic, not a behaviour change.

Three things the build learned that the note did not know:

  * **Powers still add in power.** Two sources at one cell make a level of
    `db(p1 + p2)`; logarithms do not sum. So `noise_at` sums intensities and
    the WORD is decided in dB against a dB margin, which is what real
    acoustics does. That is the only place the conversion has to be careful,
    and it is careful in the direction that is also correct.
  * **The linear tables are written down and the dB tables derived from
    them**, not the other way round. A dB literal round-trips to a power
    that differs in the last bits (12.0 becomes 12.000000000000007), and the
    near field's flood multiplies those factors together and breaks ties on
    the product. Deriving in this direction makes the dB tables EXACT
    conversions of the arithmetic that shipped.
  * **An inclusive `>=` needs a slack once it is a logarithm.** Measured
    over 800,000 exactly-at-threshold pairs across ten decades: the largest
    disagreement the logarithm introduces is 1.4e-14 dB. `_DB_EPS` is 1e-12
    dB, seventy times that and 2.3e-13 in power, and the guarantee it buys
    is exact: **the dB path and the linear path give the same word for every
    pair not within 1e-12 dB of a threshold**, and an exact tie resolves the
    inclusive way the linear comparison resolved it.

**The conversion was exactly identity.** `quantise_hearing` (linear) is kept
as the reference path and `quantise_hearing_db` is the production one;
`tests/test_sound_field.py` asserts they agree over randomised levels and
over every fixture the module builds, and the whole suite (12,685 tests)
passed unchanged on the conversion commit. **No case was found where the
conversion could not be made identical.**

The ONE place the decibels are a view rather than the arithmetic is the
near field's flood, which still accumulates a multiplicative factor:
`spread` breaks ties between two equally short paths on the larger FACTOR,
and a sum of dB losses and a product of factors do not order identically in
the last bits -- which is exactly the class of defect the 2026-09-05
reciprocity repair was. `loss_db_at` is the dB view of it. A product of
factors IS a sum of losses, so nothing behavioural rides on which side of
the logarithm the accumulation happens; only the tie-break does, and it
stays where it was measured.

### 2B. A wall attenuates; it does not abolish

A wall gets a finite transmission loss, so a sound loud enough gets through
one and a voice never does. Everything else in the aperture table converts
exactly (`open 0 | open_door 0.46 | bars 0.46 | membrane 3.01 |
closed_door 6.02 | window 10.0` dB of loss).

**Where the wall's loss lives is the far field, not the near one**, and that
is a build decision the note did not anticipate. On the NEAR field a wall is
not an aperture: `sound_passes` refuses to place a neighbour beyond one, so
there is no cell path through a wall to charge a loss to, and teaching the
near field to place wall-neighbours would relay every existing composite --
different offsets, different aperture spans, different path lengths -- and
change answers that have nothing to do with walls. A sound through a wall
does not need a cell path anyway: what survives that is a direction and a
character, which is the far field's business exactly.

### 2C. Beyond the near field, sound travels on the ROOM graph

The cell grid stays exactly as it is for the room and its neighbours -- that
is where the placement, the occluders and the sentences live. Past it, a
loud sound floods the room graph by Dijkstra, minimising ACCUMULATED LOSS:

  * each **room** crossed costs `spreading_loss_db(length)` on the running
    total of the spans of every room on the path, source's own included,
    each span from `extent` where it is written and the size tier where it
    is not (`room_span` -> `spatial_fov.grid_side`, the engine's own
    conversion, not a second one);
  * each **edge** costs its barrier's transmission loss, after the same
    material shift the edge rules already make -- an aperture's own number,
    `WALL_LOSS_DB` for a partition, `FLOOR_CEILING_LOSS_DB` for an edge that
    goes up or down and is a wall rather than a passage (a stairwell is an
    opening and keeps its own);
  * the graph is **undirected**, because a doorway is one object and may be
    declared from either side, and where both sides declare it the smaller
    loss wins. A path has no direction: the loss from A to B is the loss
    from B to A, pinned.

**It terminates on AUDIBILITY and has no hop cap.** Loss only accumulates,
so once a room is under the quietest floor the model has
(`AMBIENT["enclosed"]` at the `fragment` margin, or the absolute floor --
whichever is higher; weather and sources only ever ADD to a floor, so this
is an exact bound and costs nothing to compute), no room beyond it can be
over it. How far a sound goes is then a property of how loud it is, which is
the owner's whole sentence. Measured on a line of medium rooms with open
doorways: `catastrophic` crosses 50 rooms and stops, `thunderous` 28,
`deafening` 5. Through walls: `catastrophic` crosses one and stops.

**The near field and the far field never answer the same room.** Between a
cell model and a room model there is no arithmetic that makes two
derivations agree to the decibel, so the boundary is a HANDOVER rather than
an argument: every room on the listener's own composite (`grid.offsets`) is
the near field's, `distant_sounds` is told what those are and skips them,
and a listener is never answered twice about one sound. That is what
"they agree at the boundary" can mean here, and it is pinned.

**It costs nothing on an ordinary beat.** Nothing under
`FAR_FIELD_ENTRY_DB` (70) enters it, and the loudest thing an ordinary beat
holds is a shout at 60.8 dB. `distant_sounds` returns before it builds
anything, and no graph is walked. Measured (§ 7).

## 3. What a distant sound delivers

**A bearing and a character, never a sentence, and never a place.** The far
field carries EVENTS: a bang, a bell, a roar, an engine. It never carries
content, because distance takes the words first and a body two streets away
who "hears" a line is the same defect as one who sees through a wall.

Concretely, `distant_sounds` returns `{kind, level, db, character, bearing}`
and the record is built field by field from a closed set, so no
configuration, constant or caller can widen it:

  * **no speech, at any volume.** `far_field_sources` has no `speakers`
    parameter and drops the kind. The threshold alone would do it -- a shout
    is 60.8 dB against an entry of 70 -- but a threshold is a constant and a
    constant can be moved, so the refusal is by construction as well.
  * **no speaker and no source name.** The character is an EVENT's `detail`,
    which is prose the objects hand wrote for exactly this: what the noise
    sounded like. A running entity contributes NO character, deliberately:
    the engine has a public description of the THING and none of its sound,
    and handing a body three rooms away "a rusted iron bell on an iron
    bracket" would put a sight fact on a hearing channel.
  * **no room.** The flood knows which neighbour the sound arrived from and
    that room id never leaves the function: it is turned into a bearing
    there, against the listener's own facing and their own room's edge
    (`spatial_senses.sound_bearing_via`, split out of `sound_bearing`, which
    already returns no room id and no room name). A bearing is a direction;
    a direction is not a location.

A one-beat sound is the only thing the far field ever carries content
ABOUT, and `level` is one of `DISTANT_LEVELS` (`faint | plain |
overwhelming`) -- a margin over the LISTENING room's own noise floor, so the
same event is overwhelming in a sealed room and faint in a gale. It is
deliberately NOT the hearing ladder: `full` on that ladder means the words
came through, and no distant sound ever carries words.

## 4. The event channel (narrows `docs/UNBUILT.md` § 1.117)

A loud sound is usually a THING THAT HAPPENED, and the engine had no word
for one. `state_diff.sensory_events: [{kind, room, level | db, source,
detail}]`, written by the objects hand, heard where it happened by whoever
was there, and over when the beat is.

Built: `spatial_sound_field.normalize_sensory_event` (the shape, a closed
set of keys, capped at `MAX_SENSORY_EVENTS` 8 a beat),
`commit_scene_state._record_sensory_events` (the write, under the beat that
made it), `spatial_sound_field.beat_sensory_events` (the read, which refuses
any other beat). **The beat number IS the lifetime** -- nothing decays and
nothing expires on a counter, which is the one rule that cannot get the
class wrong. A beat that says nothing about a noise does not inherit the
last one, which is the whole difference from `state.running` and the reason
the fog bell was a defect.

**Not built, and it is what keeps § 1.117 open**: three lines in files this
work did not own. Stated exactly, in § 8.

## 5. Constants, all the owner's

| | proposed | built | note |
|---|---|---|---|
| reference | (none stated) | `DB_REF` **40** | arbitrary and cancels out of every comparison but the absolute floor and the far-field entry; 40 puts an ordinary voice at 51 dB at one pace |
| speech, dB at one pace | mutter 28, whisper 30, normal 51, loud 56, shout 61 | **37.8 / 40.0 / 50.8 / 56.0 / 60.8** | see § 5a: the note's top three are exact and its bottom two are not |
| sources, dB at one pace | faint 30, audible 51, loud 56, deafening 62 | **40.0 / 50.8 / 56.0 / 61.8** | the same |
| new rungs above the ladder | `thunderous` 85, `catastrophic` 100 | **as proposed** | declared in dB, not converted from anything; the only two rungs over the far-field entry |
| authored number | `db` on an entity or event | **built** | `event_db` reads it first, ahead of `level` and the older `intensity`; absent means the word decides |
| wall transmission loss | 45 dB | **as proposed** | the physical number, and its measured consequence is not the note's sentence -- see § 5a |
| floor and ceiling loss | 50 dB | **as proposed** | charged only where a vertical edge is a WALL; a stairwell is an aperture and keeps its own |
| ambient, dB | enclosed 14, sheltered 17, open 20 | **27.0 / 30.0 / 30.0** | the note's steps are right and its reference is not (§ 5a); `open` then moved 33.0 → 30.0 in the same session, the owner accepting `docs/UNBUILT.md` § 1.120 |
| weather, dB | (not in the note) | light **30.0**, moderate **34.0**, heavy **37.0** | was 34.8 / 37.8 / 40.0; moved with `open` under the same accepted recommendation. `WIND_NOISE` deliberately unmoved |
| far-field entry | any source over 70 dB | **as proposed** | above `deafening` 61.8 and below `thunderous` 85, so exactly the two new rungs and an authored number reach it |
| distant level margins | (not in the note) | `FULL_SNR_DB` for `plain`, **`OVERWHELMING_MARGIN_DB` 20** | 20 dB is a hundredfold over the room; new, and the owner's |
| events a beat may hold | (not in the note) | `MAX_SENSORY_EVENTS` **8** | a beat is a moment; a moment with nine distinct noises in it is a model filling a list |

### 5a. Where the note's own table was wrong, and what was done about it

**The § 5 table as first written is not internally consistent, and the
inconsistency is a reference offset applied to some rows and not others.**
Its ratios are what the model behaves by, so the ratios are what survived
and the table above was corrected rather than the code:

  * `normal 51` against `whisper 30` is 21 dB. A normal voice is twelve
    times a whisper in POWER, which is 10.79 dB. The note's loud rungs are
    an exact conversion at `DB_REF` 40 (normal 50.79 -> 51, loud 56.02 ->
    56, shout 60.79 -> 61, deafening 61.76 -> 62); its two quiet rungs, and
    `faint`, were converted against a reference ten decibels lower.
  * the ambient row has exactly the right 3 dB steps (0.05, 0.1, 0.2 are
    doublings) against a reference thirteen decibels lower again.

Nothing behavioural turns on this -- one reference is used throughout and it
cancels -- but it is the reason the built column reads differently from the
proposed one on five rows, and it is worth saying plainly that those five
are the SAME numbers and not a decision anybody took.

**The wall at 45 dB does not do what the note says it does.** Measured on
the model as built, medium rooms, enclosed, floor 27.0 dB:

| | one wall | two walls |
|---|---|---|
| shout (60.8) | 60.8 - 21.6 - 45 = **inaudible** | inaudible |
| deafening (61.8) | **inaudible** | inaudible |
| thunderous (85) | 85 - 21.6 - 45 = 18.4, **inaudible** | inaudible |
| catastrophic (100) | 100 - 21.6 - 45 = 33.4, **heard** | -15, inaudible |

So "a shout is inaudible through it" holds, and "a `catastrophic` event is a
fragment two rooms away" holds through DOORWAYS and not through walls: only
the top rung crosses a wall at all, and only one. Whether that is right is
the owner's; 18 dB would make both of the note's sentences true and 45 dB is
the physical number for masonry. **Registered, not chosen**
(`docs/UNBUILT.md` § 1.122).

### 5b. The outdoor floor, moved in the same session (`docs/UNBUILT.md` § 1.120)

A separate decision, landed as a separate commit and deliberately NOT hidden
inside the conversion: the owner accepted the outdoor-constants
recommendation the field's repair had registered. `AMBIENT["open"]` 0.2 →
0.1 (level with `sheltered` — open air is not itself a noise; what is noisy
outdoors is the weather, counted separately) and `WEATHER_NOISE`
light/moderate/heavy 0.3/0.6/1.0 → 0.1/0.25/0.5. `WIND_NOISE` unmoved.

A normal voice's `full` radius, in paces: fair 5.4 → 7.7, light rain 3.3 →
5.4, moderate 2.5 → 4.0, heavy 2.0 → 3.0, heavy + gale 1.3 → 1.7.

**It touches the far field in one direction only, and less than expected.**
The flood's termination is bounded by the QUIETEST floor the model has,
which is `AMBIENT["enclosed"]` and did not move — so a `catastrophic` event
still reaches exactly 51 medium rooms of open doorways and no further. What
changed is what an open room can HEAR of it: audible in 43 → 48 of those
rooms in fair weather, 37 → 43 in light rain.

## 6. What argues against it

  * **A finite wall makes everything slightly audible everywhere.** The
    entry threshold and the wall loss are what keep that from being true,
    and they are the two numbers most worth a play test. As built the
    threshold does most of the work: nothing an ordinary beat contains
    reaches the far field at all.
  * **Room distances are crude until extents are written.** The far field
    measures a room by its `extent` and falls back to the size tier, and 0
    of 589 rooms carried an extent when this was measured. That is the same
    dependency the geometry work has, and the Room cannot author one (F47).
  * **Free-field spreading indoors is wrong in the flattering direction.** A
    real corridor carries further than the inverse square says; the model
    will under-report reach in exactly the place stories care about. Kept
    because the alternative is a reverberation model nobody asked for.
  * **A distant event is a strong narrative hook**, and the composer will
    have to be disciplined about not making every beat about a noise three
    streets away. The delivery is a percept, not a demand.

## 7. Cost, measured

`distant_sounds` on one listener, on this machine, `.venv` Python 3.12:

| scene | ordinary beat | loud beat, first | loud beat, after |
|---|---|---|---|
| 100 rooms, all open doorways | **0.07 ms** | 17.5 ms | 3.4 ms |
| 600 rooms, all open doorways | **0.08 ms** | 408 ms | 15.6 ms |

The ordinary-beat number is the whole point and it is the gate, not the
graph: nothing qualifies, so nothing is built.

The first loud beat's cost is almost entirely `spatial_barriers.
effective_adjacent`, which resolves passages scene-wide and costs about 8 ms
a room -- 543 of the 600-room scene's 594 ms, against 41 ms for the flood it
feeds. `far_field_graph` therefore caches by identity of the scene and its
rooms dict, the way the sound field caches its composites, so one beat's
readers share one build. **That `effective_adjacent` is O(scene) per room is
not this work's to fix and is worth someone's attention**: it is paid by
every scene-wide walk, not only this one.

## 8. What was registered rather than built

Three lines, in three files this work did not own, and until they land the
event channel exists and nothing writes to it from a live turn:

1. **`llm/schemas.py`, `StateDiff`**: `sensory_events: list[dict] =
   Field(default_factory=list)` -- the same declaration `EstablishOut`
   already carries. Without it the field does not survive the validation
   round trip and a Director that writes one has it dropped.
2. **`agents/director_scopes.py`, `SPECIALISTS["objects"]["channels"]`**:
   add `"sensory_events"`. The objects hand's card already asks for it.
3. **`agents/perception.py` and `agents/composer.py`**: the delivery. The
   normal-turn perception pass calls
   `spatial.distant_sounds(sc, name, room=p["room"], turn_idx=...,
   near_rooms=<the listener's field's `grid.offsets`, or ()>,
   events=spatial.beat_sensory_events(sc, turn_idx))` and hands each record
   to a composer percept rendering
   `sound_distant_<level>` with `where=record["bearing"]["phrase"]` and
   `character=record["character"] or _en("sound_distant_character_none")`.
   The four templates are in both packs already. `heard_events` is the
   establish turn's equivalent and is unchanged.

The engine-side halves of all three are built and tested; what is missing is
the wiring, and it is one line each.
