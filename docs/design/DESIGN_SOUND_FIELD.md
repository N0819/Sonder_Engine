# The sound field: loudness as a quantity on the sight grid

Status: PROTOTYPE, merged on `writers-room` 2026-09-04; not yet on `main`.
The register holds what is still open as `docs/UNBUILT.md` § 2.36 (this
note's § 10 and the open questions at its end: the constants, crowd mood,
simultaneous lines, fragment thinning, `sensory_events` after establish, the
two gates, the live run). Designed 2026-09-04 with the owner ("do you
think we should raycast speech and sounds as well?" -- yes, and not with
rays) and built the same day in an isolated worktree as
`world/spatial_sound_field.py` behind the `world/spatial.py` facade, beside
the light field (`DESIGN_LIGHT_FIELD.md`), whose grid, source class,
quantise-last rule and fail-open it reuses. §§ 3-8 are built as written with
the exceptions § 6a and § 10 name; § 9's measurements were taken read-only
over the owner's corpus and are in § 9a, with the synthetic table.

**Merged with the light field 2026-09-04**, under the owner's ruling of the
same day, each item pinned: the composite is ONE derivation
(`spatial_fov.room_field` under `sound_passes`; `_acoustic_grid` is gone --
§ 4.2, § 10.7); the composer says WHERE the sound is (`sound_shape`, the
noise ladder `quiet | din | drowned` derived from the SNR thresholds --
§ 4b, § 10.6); a `failing` source is switched off at commit and reported
once, in one block with the light field's (§ 5, § 10.5); the steadiness
words, hash and rates are the light field's (§ 10.8); and a listener whose
station lands on an occluder's cell hears (§ 4.2). The rest of § 10 stands.

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
   do. Occluders inside a room do NOT block sound. SOUND IS STOPPED ONLY BY
   WHAT REACHES THE CEILING (2026-09-05, § 6b): a `full`-height partition is
   walked round by the flood at the cost of the extra path -- its own cells
   are REACHED and never passed through (2026-09-04: a listener whose station
   resolved onto another anchor's seeded cell was never entered and heard
   nothing at any volume; now the flood steps onto the cell and goes round)
   -- and anything lower is CROSSED for `OCCLUDER_PASS` and no extra path at
   all, because a voice goes over a counter rather than round it. The
   round-it rule ran from the waist up until 2026-09-05 and silenced ordinary
   conversation in any furnished room (§ PE1).
   The composite the flood runs over is `spatial_fov.room_field` under the
   `sound_passes` predicate -- every barrier that is not a wall, at its pass
   -- the SAME derivation sight and light use, so an L or a round room is
   its shape for sound as it is for sight.

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
  * **Where the sound is** (built 2026-09-04: `sound_shape`, rendered by
    `composer.render_sound_shape` and the Japanese adapter as a standing
    HEARING percept, `soundscape_percept`; `tests/test_field_sentences.py`).
    The noise at a cell is graded on a closed ladder DERIVED from the two SNR
    thresholds -- `quiet` (a normal voice one pace off is `full`, noise <=
    6.0 / FULL_SNR), `din` (a fragment, <= 6.0 / FRAGMENT_SNR), `drowned`
    (nothing) -- so the words move with the constants (`NOISE_WORDS`,
    `noise_word`). Then the light field's five rules, word for word: speak
    only when the room is UNEVEN; grade by ANCHOR (the visible anchors at
    the noise word of their nearest cell, loud to quiet); name a source in
    this room only when it is HEARD, one beyond a doorway by the opening
    ("the noise from beyond the open doorway") when that opening is in
    view, and never one the listener has no channel to; say where the
    listener stands (with a cell); subtract, never add -- the sentence is
    re-derived by `observations_from_render` and each listener receives only
    their own. Lines and one-beat events are the beat's, not the room's, and
    are not named. The same sentence reaches the Director's digest
    (`payload.sightlines.sound[name]`). "The noise from the generator drowns
    everything at the shelf and the hearth and dies away at the table.
    Where you stand, the noise drowns everything."

## 5. Steadiness

Shared with the light field: a `flickering` source drops a level on beats
chosen by the hash of (turn, source id); a `failing` one goes quiet by the
same hash and files the same engine notice ("the generator in the shed has
stopped"), which is a sound event in its own right -- silence where there
was noise is heard. One hash, two senses, so a lamp and the generator it
runs on fail on the same beat when they are one entity.

At commit (2026-09-04, `persist/commit_scene_state._record_failed_sources`)
the two fields are one block: it reads `failing_sources_out` (light) and
`failing_sound_sources_out` (sound), writes `state.running: false` for a
sound that stopped as it writes `state.lit: false` for a light that went
out, and files ONE notice per thing -- "has stopped", "has gone out", or
"has failed" for a thing that does both. Perception no longer files the
sound notice; `SoundField.notices` still carries it for the field's own
readers.

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

### 6a. What the build set, and why (2026-09-04)

The table above was checked against its own sentences before a line of the
reader was changed, and it fails them: with `P / (1 + L^2)` a 4:1
normal-to-whisper ratio cannot both carry a normal voice across a medium room
as `full` (corner to corner is a path of 7, so 6/50 = 0.12) and fade a
whisper to a fragment at three cells (1.5/10 = 0.15 sits above it); and with
`FULL_SNR 2` over an enclosed floor of 0.3, `full` needs 0.6 where a normal
voice five cells off is 0.23 -- below even `HEAR_FLOOR`, so two people at
opposite walls of a medium room would not have heard each other at all. The
sentences need the ratio a real voice has (a whisper is tens of decibels
under conversation, not a quarter of it) and a quieter floor. Every constant
keeps its § 6 name; these are the values on the branch, each beside its
table in the module and every one the owner's to move:

    SPEECH_POWER    mutter 0.6 | whisper 1 | normal 12 | loud 40 | shout 120
    SOUND_POWER     faint 1 | audible 12 | loud 40 | deafening 150
                    (tied rung for rung to speech: `audible` IS a normal
                    voice, `loud` IS a loud one)
    APERTURE_PASS   as § 6                DIAGONAL_COST   1.4 (as § 6)
    AMBIENT         enclosed 0.05 | sheltered 0.1 | open 0.2
    WEATHER_NOISE   light 0.3 | moderate 0.6 | heavy 1.0  (x the room's
                    weather `gain`)           WIND_NOISE  wind 0.3 | gale 1.0
                    -- the two numbers "(+ weather)" needed; not in § 6
    HEAR_FLOOR      0.05      FULL_SNR 2.0 (as § 6)      FRAGMENT_SNR 0.8
    CROWD_SOUND     a handful faint | a dozen or so audible |
                    a few dozen audible | a throng loud   (§ 10, item 2)
    FLICKER_RATE    1 in 4    FAIL_RATE 1 in 12   (the light field's; must
                    be equal at merge)

With these, in a quiet enclosed room a `normal` voice is `full` to a path of
ten paces (a vast hall's far end reads as a fragment), a `whisper` is `full`
to two, a `fragment` at three and four and `none` at five, and a `mutter` is
`full` at one, a fragment to three and gone at four. `mutter` was 0.5 until
the corpus pass (§ 9a.4): the one live pair on a field stands 2.4 paces
apart, and 0.5 turned a mutter today's live path delivers as a fragment
into `none`; 0.6 keeps it a fragment there and gone at four paces.

### 6b. What the play runs moved (2026-09-05)

One constant added and one owner decision registered, both from the five
play runs of 2026-09-05.

    OCCLUDER_PASS   0.9 per non-partition occluder cell the path crosses

**Added** by the PE1 repair (`docs/experiments/PLAY_2026_09_05_flat.md`).
Sound is stopped only by what reaches the ceiling: the flood rounds a
`full`-height partition and CROSSES anything lower for this factor and no
extra path. Before it, the round-it rule ran from the waist up and an
ordinary kitchen counter parted a room as a wall does -- an 8x6 kitchen with
a counter run and a table in it graded a normal voice between two bodies four
paces apart at 0.0067 against a noise of 0.32, `none`, because the flood
walked twelve cells for a four-cell line. 0.9 is chosen so that a counter and
a table between two bodies four paces apart in a quiet room leave a normal
voice `full` (0.9² × 12/17 = 0.57 against the 0.10 `full` asks there) and a
line of three such things costs about a quarter of the signal. It is near 1
for a second reason: the flood minimises PATH LENGTH, so a factor much below
1 would make the shortest path the wrong answer and the Dijkstra would have
to optimise the gain itself. The LIGHT field is deliberately unchanged --
a ray is cast, not flooded, so a head-high shelf must shadow a waist-high
candle and must not shadow a ceiling fixture, which is what `_cast` already
does by comparing the occluder against the SOURCE's height.

**Registered, not taken: outdoors an ordinary voice is `full` only inside
about five paces**, and in light rain 3.3 (`PLAY_2026_09_05_road.md` § PD2).
Measured again while landing PE1: it is not a bug -- the ambient floor is
applied once, to the listener's cell's room, and the weather term is a
separate quantity from the exposure term -- so it is the values that are in
question and the values are the owner's. The full radius table per exposure
and weather, the rule the constants should satisfy, and a recommendation
(move `AMBIENT["open"]` 0.2 → 0.1 and `WEATHER_NOISE` light/moderate/heavy
0.3/0.6/1.0 → 0.1/0.25/0.5, and nothing else) are in `docs/UNBUILT.md`
§ 1.120.

### 6c. Two rules the play runs restated (2026-09-05)

Neither is a constant; both are the same sentence in two places.

* **A path between two cells has no direction.** The gain for a PAIR is
  computed on one field chosen by the pair -- the two rooms sorted, first
  that can place both bodies -- not on whichever listener's field is asking.
  Every composite is laid from one room outward, so two composites of the
  same two rooms are two layouts with different offsets, aperture spans and
  path lengths; read per listener that made hearing one-way, and a shout
  across an open arch was answered by one body and not heard by the other in
  the same beat (`PLAY_2026_09_05_caravanserai.md` § PB2). The NOISE stays
  the listener's own: a noise floor is a property of where a body stands,
  which is the one thing about a pair that is not shared.
* **Noise masks a voice by what reaches the listener, wherever the voice came
  from.** One masking rule, on every path. Where the field places both bodies
  it quantises `signal` against `noise` as § 4.5 says. Where it cannot place
  the speaker, the relation carries `door_gain` instead -- what the same
  voice would deliver from this room's own best opening -- and `hear_level`
  takes the weaker of the edge model's answer and that ceiling, since
  whatever came from beyond entered through one of those openings and crossed
  the rest of the room like any other sound. Before it, a fog bell drowned an
  ordinary voice in its own room and did nothing at all to a shout from three
  rooms away (`PLAY_2026_09_05_lighthouse.md` § PA5). A `vouched` channel is
  exempt: a voice on a live comm channel is not crossing this room's air.
* **A raised voice carries through an opening.** One passable edge away
  (`one_opening_away`: an edge sound walks through, after the material shift,
  declared from either side) a `loud` voice or a `shout` is at worst a
  `fragment`, whatever the walk costs it. The edge model always said so and
  the field can refuse it, so a shout across the most open archway in a house
  arrived as less than one through a shut door, and once both perception
  passes read the field it reached nobody at all
  (`PLAY_2026_09_05_manor.md` § PC3). The floor answers to the masking rule
  above like everything else: where the noise at the listener's own cell
  would refuse the same voice one pace off, nothing from the next room
  survives either.

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

### 9a. Measured (2026-09-04, read-only, chat 111 excluded)

The owner's database could not be copied (4.0 GB free against a 3.4 GB
file), so the rows were streamed from a `sqlite3 -readonly` open straight
into aggregating scripts and nothing content-bearing was written to disk.

1. **Corpus.** 10,093 spoken lines with a `dialogue_log` across 3,650
   resolve turns in 91 chats: `normal` 8,560 (84.8%), `mutter` 1,113
   (11.0%), `loud` 206 (2.0%), `whisper` 178 (1.8%), `shout` 36 (0.4%). 104
   scene rows, 589 rooms, 321 with a size tier; **2 rooms carry a geometry
   field on an anchor, both in one scene (chat 114); 1 is occupied, by 2
   bodies, one of whom has spoken.** No stored entity carries `sound_source`
   (the field did not exist). The field bites on almost nothing in the
   existing corpus and on everything the spatial hand writes geometry for
   from here -- the same rate the sight layer found on 2026-09-02.
2. **Pin.** `tests/test_sound_field.py::test_a_scene_without_geometry_
   stamps_nothing_and_composes_byte_identically`: the relation carries
   exactly the keys it carried before, and `hear_level` answers by the edge
   rules; the cross-room case pins today's closed-door answers verbatim.
3. **Synthetic** (the § 6a constants; L is the acoustic path in cells,
   gain the fraction of the speaker's power at the listener's cell, noise
   the listener's floor). A large room (8 cells) and pairs of medium rooms
   (6), all enclosed and quiet:

       case                                       L    gain   noise  mutter whisper normal loud shout
       whisper across a large room, wall to wall  5.8  0.029  0.05   none   none    full   full full
       ...beside the speaker (`near`)             1.0  0.500  0.05   full   full    full   full full
       shout through a closed_door, far walls     6.8  0.005  0.05   none   none    frag   full full
       ...door to door                            3.0  0.025  0.05   none   none    full   full full
       ...the same door in paper                  6.8  0.019  0.05   none   none    full   full full
       ...the same door in steel                  6.8  0.002  0.05   none   none    none   frag full
       ...a window, far walls                     6.8  0.002  0.05   none   none    none   frag full
       ...a membrane, far walls                   6.8  0.011  0.05   none   none    full   full full
       round a corner via an open door            6.8  0.019  0.05   none   none    full   full full
       through the wall (room never placed)        --  edge rule: normal none, shout fragment
       behind the counter (`cover`), from the hearth   6.4  0.021  0.05  none none full full full
       before the counter, from the hearth        4.4  0.049  0.05   none   none    full   full full
       (both re-measured 2026-09-05: the counter is CROSSED for
        OCCLUDER_PASS, not gone round, so the `cover` path is 6.4 and not
        10.0 -- the body is still on the far side of the run, so it is a
        longer walk, and the flood no longer detours to the end of it)
       loud generator 3 off; speaker beside you   1.0  0.500  4.58    --     --     frag   full full
       loud generator 0 off; speaker beside you   1.0  0.500  40.05   --     --     none   none frag
       loud generator 3 off; speaker 5.2 away     5.2  0.036  4.58    --     --     none   none frag
       no generator; speaker 5.2 away             5.2  0.036  0.05    --     --     full   full full
       the listener HOLDS the running generator   1.0  0.500  40.05   --     --     none   none frag
       ...switched off (`state.running` false)    1.0  0.500  0.05    --     --     full   full full
       two normal voices, listener at the far wall           A fragment, B none (A alone: full)
       two normal voices, listener beside A                  A full, B none

   Against the § 6 sentences: the whisper and the corner hold; a shout
   through a shut door is `full`, not a fragment (today's edge rule also
   says `full`, and the door in steel gives the fragment); the counter
   costs path and blocks nothing; a loud generator masks a normal voice
   beside you to a fragment at three paces and to nothing at zero -- `full`
   beside the speaker needs the machine five or more paces off. `FULL_SNR
   2` is strict on masking; 1.0 would make the beside-speaker case `full`
   at three paces. The owner's call.
4. **Corpus before/after.** 2 listener fields built, 2 speaker-listener
   pairs on a field, both changed, both chat 114's console room (Hinami and
   the Doctor at cells (9,6) and (11,5), path 2.4, gain 0.148, noise 0.1):
   `normal`/`loud`/`shout` unchanged at `full`; `whisper` `full` ->
   `fragment`; `mutter` `full` -> `none` at 0.5, `fragment` at 0.6 (the live
   path, which passes measured proximity `near`, already answered
   `fragment` for both). There is no third pair to read.
5. **Live.** Not run on this branch (the standing grant asks for Gemini on
   a copy, and there is no room for a copy); the Lantern Station shed is the
   scenario to play first.

## 10. What was built differently, and what is left

  1. **Where the stamp lives.** `spatial_rel` (room to room) never sees a
     body, so `signal`/`noise` are stamped by `spatial_rel_between`, the
     body-to-body builder, and `hear_level` quantises them; `spatial_rel`
     is untouched. `signal` is the path GAIN per unit of the speaker's
     power, because the relation is built before the line's volume is read.
  2. **Crowds read their BAND, not their mood.** `mood` is 24 characters of
     free prose; reading it for "a raised one" is a word list. The band is a
     closed set the engine already grades density by (`CROWD_SOUND`). Mood
     stays an open question.
  3. **One line at a time.** The reader path grades each spoken line with
     the beat's OTHER speakers absent: the lines of a beat are sequential,
     not simultaneous, and treating them as one chorus would turn every
     two-person conversation heard by a third into fragments. Simultaneous
     voices mask through `sound_field(..., speakers={name: volume})`, pinned
     in the two-voices test; nothing yet says which lines of a beat overlap.
  4. **Sound events** reach other rooms at the OPENING (`heard_events` in
     `perception_establish`); `sensory_events` exist on no later stage's
     schema, so there is nothing to spread on a normal beat.
  5. ~~Failing sources file the notice and stay running.~~ Decided
     2026-09-04, once for both fields: the commit switches the thing off in
     every sense it has and files one notice (§ 5).
  6. ~~The composer's sound-shape sentence is not built.~~ Built 2026-09-04
     (§ 4b): perception hands the composer the shape, the templates say it.
  7. ~~The composite is placed twice.~~ One derivation since 2026-09-04
     (§ 4.2): `room_field(through=sound_passes)`; the copy had already
     drifted to squares after the room-shapes work.
  8. ~~`STEADINESS`, `FLICKER_RATE` and `FAIL_RATE` are defined twice.~~
     The light field's, imported (the 2026-09-04 merge).
  9. **`sensory_events` exist on no schema after establish** (item 4): a
     crash two rooms away on a normal beat has no channel to arrive by. A
     Director schema addition with an owner question attached -- which hand
     owns a one-beat sound -- so registered, not built (`docs/UNBUILT.md`
     § 2.36).
 10. **Two gates.** The sound field exists where `room_has_geometry` (an
     authored footprint, height or opacity: 2 of 589 live rooms); the light
     field where `light_geometry_exists` (a size tier or anchors: 321).
     Both are argued in their notes; whether hearing should take the wider
     gate is the owner's, and is registered.
 11. **`hear_level`'s `vouched` branch** is unreachable for a pair on a
     field, as the comment there says: a vouched channel is one with NO
     spatial relation (barrier unknown, distance remote), and two bodies on
     one placed field always have one. Not a defect; comms decide before
     `hear_level` is asked.

Open questions for the owner: whether a fragment should THIN with the ratio
(fewer words at 0.9 than at 1.9) or stay one kind of fragment; whether a
crowd's level should follow its `mood` as well as its band (§ 10.2); which
lines of a beat count as simultaneous (§ 10.3); whether a one-beat sound
should have a channel on a normal beat (§ 10.9); which gate hearing should
take (§ 10.10); and the constants (§ 6a).
