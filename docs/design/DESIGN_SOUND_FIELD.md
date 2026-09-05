# The sound field: loudness as a quantity on the sight grid

Status: DESIGN, not built. Agreed with the owner 2026-09-04 ("do you think we
should raycast speech and sounds as well?" -- yes, and not with rays), queued
directly after the light field (`DESIGN_LIGHT_FIELD.md`), whose grid, source
class, quantise-last rule and fail-open it reuses. Every number in § 6 is a
proposed constant; § 9 lists what to measure and none of it has been.

---

## 1. What exists, and where it stops

Hearing is decided by `spatial_senses.hear_level(rel, volume, vouched,
proximity)`: the speaker's VOLUME word (`mutter | whisper | normal | loud |
shout`, the social hand's field on a spoken line), the barrier between the two
rooms shifted by its `material` (`_material_shifted_barrier`), a distance tier
on the edge, and the containment cases (`inside_source`, `enclosed_from_source`
-- a voice conducted through the mass one body is inside). It answers on the
ladder `none | fragment | full`, the composer renders a fragment as broken
words ("A muffled voice: ...Evening... relief... Which..."), sound WALKS more
than one room over `_SOUND_WALK_BARRIERS`, comms carry a voice over any wall,
and `sensory_events` carry ambient sound with an `intensity` and a `distance`.

That model is right about barriers and containment and silent about the
three things geometry decides:

  * DISTANCE inside a room -- a whisper at the far end of a large hall and a
    whisper beside you are the same answer;
  * the PATH -- sound reaches a listener round a corner through an open door
    at reduced level, whatever stands in the way; a straight-line model would
    make a voice behind a counter inaudible and a voice round a corner silent,
    both wrong, which is why this is a flood and not a raycast;
  * NOISE -- nothing masks anything. A generator in the shed does not make
    speech in the shed hard to follow; a body operating a loud machine hears
    the room as well as a body standing still.

## 2. The rule in one sentence

Sound is a scalar on every cell of the observer's field, spread from each
source along the SHORTEST ACOUSTIC PATH -- cell to cell, through apertures in
the wall lines with a drop per barrier, never through the wall itself --
decayed by path length, summed into a signal for the source being listened to
and a NOISE for everything else plus the room's ambient, and quantised to the
existing ladder LAST by signal against noise, so every reader keeps its three
words and gets them from geometry instead of from the edge.

## 3. Schema: a source is a class, not a device

Speech already has its class: the VOLUME word on the line. Nothing new is
asked of the social hand. For things that make sound, on the entity beside
`light_source`:

    sound_source   faint | audible | loud | deafening     what it emits when
                                                          running; absent = none
    steadiness     steady | flickering | failing          SHARED with the light
                                                          field: a generator
                                                          that cuts out is the
                                                          same class as a lamp
                                                          that goes out
    state.running  true | false                           the switch; absent =
                                                          running (the light
                                                          field's state.lit)

Two closed sets the engine owns (`SOUND_LEVELS`, and `STEADINESS` from the
light field). Nothing names a generator, a waterfall, a radio or a crowd; the
objects hand's clause states the class: "a thing that makes a continuous
sound carries `sound_source` at the level it makes; what the thing IS lives in
its name and description". Crowds (`crowd_ops`) are a source at `audible`
when open, `loud` when their `mood` is a raised one -- read from the crowd
record, not declared twice. Weather is ambient (§ 4.6), never a source.

## 4. The field

Computed per (scene, observer) on the same composite field as sight
(`observer_field`), cached with it for the turn:

1. **Power.** A speaking body is a source at `SPEECH_POWER[volume]` on its
   cell; a running entity at `SOUND_POWER[sound_source]` on its cell; a crowd
   at its level on its room's centre cells.

2. **Spread.** From the source cell, Dijkstra over the field's cells: a step
   to a side neighbour costs 1, to a diagonal `DIAGONAL_COST`; a step that
   crosses a wall line is allowed only inside an aperture (`_wall_verdict`
   answers where the wall is) and multiplies the carried intensity by
   `APERTURE_PASS[barrier]` -- an open doorway passes nearly all, a curtain
   half, a closed door a quarter, a window a tenth, a wall nothing. The
   barrier's `material` shifts the class exactly as `_material_shifted_barrier`
   does today, so a thin door and a bank-vault door differ as they already
   do. Occluders inside a room do NOT block sound: a counter is walked
   round by the flood at the cost of the extra path.

3. **Decay.** Intensity at a cell reached by path length L is
   `P / (1 + L^2)`, with the aperture factors applied where crossed. Path
   length, not straight distance: that is the whole difference from light.

4. **Sum.** A listener's SIGNAL for one source is that source's intensity at
   the listener's cell. The listener's NOISE is the sum of every OTHER
   source's intensity there, plus the room's ambient (§ 4.6), plus the
   listener's OWN noise (§ 4.7). Two people talking at once mask each other,
   which is the reason group scenes get fragments.

5. **Quantise, last.** `full` if `signal >= FULL_SNR * noise`, `fragment` if
   `signal >= FRAGMENT_SNR * noise` and `signal >= HEAR_FLOOR`, else `none`.
   Two ratios and one absolute floor, named. Every reader below this line
   sees three words.

6. **Ambient floor.** Every cell of a room carries `AMBIENT[exposure]` plus
   the weather's audible words as a level (wind, rain, a storm -- the
   `weather_words(..., "hearing")` ladder already exists); outdoors is
   noisier than a sealed room. The floor is NOISE, never a source: it masks,
   it does not spread.

7. **The listener's own noise.** A body holding or operating a running
   `sound_source` hears it at its own cell as noise before anything else;
   the same body's `pose.detail` is not consulted (it is free prose).

### 4a. What stays exactly as it is

The containment rules (`inside_source`, `enclosed_from_source`, a voice out
through a body's mass) keep their present answers -- the medium there is a
body, not air, and the field has no cell for it. `vouched` and comms keep
theirs: a live channel is a channel. The composer keeps rendering a fragment
as broken words; WHICH words survive is its business, and § 9 asks whether
the fragment should thin with the ratio.

### 4b. Readers

  * `hear_level(rel, volume, ...)` -- when the observer's scene carries
    geometry, `rel` arrives with `signal` and `noise` for the pair and the
    function quantises them; when it does not, every present rule stands and
    the answer is byte-identical. The words do not change.
  * `sensory_events` -- an event with a `source_room` and an `intensity` is a
    one-beat source at that level on that room's centre, spread the same
    way, so a crash two rooms away is heard through the door it came by.
  * The composer gets, per room in view, the field's SHAPE in words --
    "the generator drowns everything at the east end; by the door you could
    hear yourself speak" -- from the per-anchor cell mapping sight already
    uses. Prose from geometry, never a number.

## 5. Steadiness

Shared with the light field: a `flickering` source drops a level on beats
chosen by the hash of (turn, source id); a `failing` one goes quiet by the
same hash and files the same engine notice ("the generator in the shed has
stopped"), which is a sound event in its own right -- silence where there
was noise is heard. One hash, two senses, so a lamp and the generator it
runs on fail on the same beat when they are one entity.

## 6. Constants the owner sets

    SPEECH_POWER    mutter 1 | whisper 1.5 | normal 6 | loud 14 | shout 30
    SOUND_POWER     faint 2 | audible 6 | loud 14 | deafening 40
    APERTURE_PASS   open 1.0 | open_door 0.9 | bars 0.9 | membrane 0.5 |
                    closed_door 0.25 | window 0.1 | one_way_window 0.1 | wall 0
    DIAGONAL_COST   1.4
    AMBIENT         enclosed 0.3 | sheltered 0.6 | open 1.0   (+ weather)
    HEAR_FLOOR      0.3        FULL_SNR 2.0        FRAGMENT_SNR 0.8

Chosen so that in a `medium` (6-cell) quiet enclosed room a `normal` voice is
`full` everywhere, a `whisper` is `full` within two cells and a `fragment` to
four, a `shout` through a `closed_door` reaches the next room as a
`fragment`, and a `loud` generator in the same room makes a `normal` voice a
`fragment` beyond three cells and `full` beside the speaker. § 9.3 is the
table that checks those sentences.

## 7. Cost, and fail-open

One Dijkstra per source over at most ~600 cells, a handful of sources: well
under a millisecond against seconds of model time, computed once per
(scene, observer) and cached with the field. No model call anywhere. Where the
scene carries no geometry the field does not exist and every reader falls
back to today's functions unchanged, pinned byte-identically as the light
field and `observer_field` are.

## 8. Ownership

  * The **social** hand owns a line's volume, as it does.
  * The **objects** hand mints and changes `sound_source`, `steadiness`,
    `state.running`. One clause stating the class (§ 3).
  * **Perception** computes the field and reads it; `hear_level` is the seam.
  * The **Narrator** renders fragments and the room's sound shape; it cannot
    make anything louder or quieter.
  * The **Writers' Room** plants a source through the existing entity
    operations; sound is not an operation.

## 9. To measure before and while building

  1. Corpus (a copy, read-only): the distribution of volume words on spoken
     lines; entities whose description names a continuous sound and would
     take `sound_source`; rooms carrying sources and geometry both.
  2. Pin: every scene without geometry composes byte-identically.
  3. Synthetic: the § 6 sentences as a table -- a whisper across a large
     room; a shout through a closed door; a normal voice round a corner via
     an open door versus through the wall; a loud generator masking a normal
     voice at one, three and five cells; a listener operating the generator;
     two normal voices at once from opposite ends.
  4. Corpus before/after: `hear_level` over every (speaker, listener) pair in
     scenes carrying geometry, the first twenty changed pairs read one by one.
  5. Live: two beats in a fresh non-explicit scenario with a running machine
     in the room (the Lantern Station's shed is one), every stage read.

Open questions for the owner: whether a fragment should THIN with the ratio
(fewer words at 0.9 than at 1.9) or stay one kind of fragment; whether a
crowd's level should follow its `band` as well as its mood; and the
constants, which the owner may want to set after the § 9.3 table exists.
