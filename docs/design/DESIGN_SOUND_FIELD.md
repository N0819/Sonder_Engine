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

**SPEECH LEFT THE FIELD 2026-10-20** (§ 11, the owner's "voices carry unless
something in the story stops them"). Whether the words of a line arrive is
no longer signal against noise on this grid: it is the hearing rule in
`spatial_senses.hear_level`, a table over what stands between two bodies
whose every entry is a real-world decibel budget, with noise entering only
from what the story makes deafening. What this note describes still holds
for SOUNDS -- a thing running, a crowd, a one-beat event, the room's own
voice: where they reach, how loud they are at a cell, what the composer says
of a room's noise, and the far field. §§ 1, 2, 4.4-4.5, 4b's first reader,
§ 6a's speech sentences and § 10.3 describe the speech grade that § 11
replaces; they are kept as the record.

**WAVE A, 2026-10-20** (§ 12, the owner's "I guess go ahead"): four things
the world does that § 11 left out. A din keeps a far table's talk from a
BYSTANDER -- never from the people talking to each other (§ 11.4's
"noise never masks speech" was the over-simplification); a voice's tone
travels farther than its words; a voice is known by its sound, and a
stranger's is described by what it carries; footsteps come through floors.

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
* **A beat's one-off sounds are moments, not a floor** (the owner,
  2026-09-25: "sounds should be allowed to be transient mid beat. there are
  types of sound after all."). The noise a line -- or any sound -- is heard
  over is what sounds throughout it: standing sources, crowds, the room's own
  sound and its ambient floor. A sound event (`sensory_events`: a creak, a
  gasp, a shot) happens at some moment in the beat and is heard as itself;
  it masks nothing. Counted as a floor, an instant sat on every line of its
  beat at full power: on the owner's chat 155 turn 34 a listener's own
  `audible` moan, placed at her own cell, read 58 dB in her ears and took a
  line murmured by a face inches from hers to nothing, and a faint creak of
  the table she lay on still held it to a fragment. A noise meant to drown
  speech for as long as it lasts is a standing source (`sound_source` with
  `state.running`), and it still does.
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

### 6c. The ladders re-authored from real decibels (2026-09-14)

The § 6a tables (`SPEECH_POWER 0.6 | 1 | 12 | 40 | 120`, `SOUND_POWER 1 |
12 | 40 | 150`, and `audible` 12 → 4 on 2026-09-14 morning) are the record of
what shipped and no longer the values. They had the ORDER a real voice has
and not its span — whisper to shout was 20.8 dB against 55 in the world — so
a fire and a voice, an engine and a raised voice, held one power each and
every masking verdict between them was a coin toss the play lost
(`DESIGN_SOUND_DECIBELS.md` § 5c has the three scenes and their numbers).
The constants keep their § 6 names and are now authored in dB at one pace,
the powers derived:

    SPEECH_ONE_PACE_DB   mutter 38 | whisper 35 | normal 60 | loud 70 | shout 82
    SOUND_ONE_PACE_DB    faint 40 | audible 50 | loud 80 | deafening 100 |
                         thunderous 120 | catastrophic 140
    FRAGMENT_SNR         1/16 (-12 dB)      FULL_SNR 2.0 (as § 6)
    HEAR_FLOOR, AMBIENT, WEATHER_NOISE, WIND_NOISE, APERTURE_PASS, DIAGONAL_COST,
    OCCLUDER_PASS, CROWD_SOUND   unmoved

With these, in a still enclosed room (27.0 dB): a `normal` voice is `full`
across any room the engine lays out; a `whisper` is `full` to two paces, a
fragment at three, gone at four; a `mutter` is `full` to three, a fragment
at four, gone at five (and dies across a large room's width, which the aside
tests hold). A hearth fire (`audible`) leaves its own hearth `quiet` and a
normal line from it is `full` five paces off. A `loud` engine on a 4x3 deck
is `drowned` at every cell; a raised line one pace off is a fragment from
every cell, a normal line at arm's reach a fragment three paces from the
machine and `none` at two, and a whisper is gone everywhere. The noise words
derive as before: `quiet` to 57 dB, `din` to 72, `drowned` above.
`tests/test_sound_calibration.py` pins the three scenes.

The aperture, partition, ambient and weather tables are still on the
compressed scale of § 6a and 2026-09-05, so the model is mixed and known to
pass a real voice through an opening more readily than a real opening
would; registered as `docs/UNBUILT.md` § 1.159 rather than taken here.

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

## 11. The hearing rule, restated (2026-10-20)

**VOICES CARRY UNLESS SOMETHING IN THE STORY STOPS THEM.** The owner,
2026-10-20: "the sound system repeatedly wars with both reality and fiction,
it's not very good in it's current state", after "Kettles are not that loud
... I think the design principles behind it might be incredibly flawed" --
and, mid-build, "I just think the system is failing to meet several real
world principles". Earlier, 2026-09-26: "Sound gatings is entirely
overzealous. Rain is not even that loud you could still call to someone
across a street in rain and not really strain your voice."

### 11.1 What the rule replaced, and why it failed

Every line was graded by signal against noise on the cell grid (§§ 2, 4):
the speaker's level at their cell, faded per cell along the flood as in
open air, against every noise at the listener's cell -- the room's floor,
the weather, every running thing, the crowd -- with +3 dB asked for a line
to be followed. Measured in play:

* chat 176 turn 2: the opening wrote a kettle `sound_source: loud`, read as
  80 dB at a pace; a SHOUT three paces off arrived as "Thank..." (on HEAD
  the same scene grades a normal line `none`, a raised one and a shout
  `fragment`);
* rain broke dialogue into "...word... word..." until 2026-09-26 (§ 1.167);
* chat 177 turn 21: a shut door turned a question at arm's reach into a
  fragment ("What was that?") -- and the cells the verdict hung on drew the
  listener at the far wall while her pose said she was by the door.

Every error ran one way: it took away speech everyone in the story would
have heard, which produces the most visible kind of broken scene.

### 11.2 The model chosen: a table whose entries are real-world budgets

Two shapes were possible -- a corrected acoustic model on the cell grid, or
a table over the path between two bodies with every entry justified by real
hearing. **The table**, because the budget's inputs are the engine's least
reliable facts: cell positions that are often wrong (177 t21), and emission
words that are a model's judgement (`loud` is a whistling kettle, a PA horn
and an engine at idle alike, 65-85 dB(A) in the world). For voiced speech
the entries sit 8-33 dB from either threshold, so no plausible error in
those inputs moves them; at the three edges where the budget is marginal
the physics itself names the answer -- a far shut door muffles (transmission
loss rises about 6 dB an octave, so what crosses is a voice's low half), a
whisper beyond reach is a hiss in the room's own ring, a wall passes only a
shout's low half. Where a level genuinely varies -- rooms away, under the
open sky, inside a deafening noise -- a small dB budget runs with the same
real numbers. ONE speech model: `spatial_senses.hear_level` is the table and
calls the budgets; nothing else grades a line.

The real-world numbers every entry is checked against, dB(A):

| quantity | value | basis |
|---|---|---|
| a voice at a pace | whisper 30-35, under the breath 35-45, conversation 60, raised 70, shouting 80-88 | `SPEECH_ONE_PACE_DB` 35 / 38 / 60 / 70 / 82, unchanged since 2026-09-14 |
| a quiet lived-in room | 25-35 | `AMBIENT_DB` 27 enclosed, 30 open, unchanged |
| across a room | beyond the critical distance (1-3 m) the reverberant field holds a voice 0-10 dB under its level at a pace, by the room's size | Sabine's room constant; `VOICE_ROOM_DROP_DB` 6 where a level is needed |
| into the next room | what an opening or a door radiates spreads over the receiving room's absorption, 10 log10(S/A), about -10 dB | `ROOM_COUPLING_DB` 10 |
| barriers | open doorway ~2, curtain ~5, closed interior door 15-25, closed glass or a heavy door 28-40, interior wall 35-45 | `APERTURE_DB` 2 / 5 / 25 / 28, `WALL_LOSS_DB` 45, unchanged |
| intelligibility | a sentence is followed at 0 dB SNR, half of it near -5, words caught to about -12; whispered speech has no voicing to follow | `SPEECH_FULL_SNR` 0 dB (new), `FRAGMENT_SNR` -12 (unchanged) |

### 11.3 The rule

`spatial_senses.hear_level(rel, volume, proximity=None, level_db=None, *,
seen=False)` -> `none | fragment | full`; `_hear_level` is the table:

| path (after the material shift) | normal | raised | shout | whisper | mutter | budget, a normal voice into a quiet room |
|---|---|---|---|---|---|---|
| a body's mass (conducted) | unchanged | | | | | the medium is a body, not air |
| one enclosed room | full | full | full | by reach | by reach | 60 - (0..10) vs 27: +23..+33 |
| one room under the sky | by distance | by distance | by distance | by reach | by reach | free field, 6 dB a doubling |
| an opening (open, open door, grille) | full | full | full | by reach | by reach | 60 - 6 - 2 - 10 = 42: +15 |
| a shut door or curtain, a body at it | full | full | full | none | none | 60 - 25 = 35: +8 |
| ... nobody at it | fragment | full | full | none | none | 60 - 41 = 19: -8 (muffled) |
| a heavy door or glass, a body at it | fragment | full | full | none | none | 60 - 35 = 25: -2 |
| ... nobody at it | none | fragment | fragment | none | none | 60 - 51: -18; 82 - 51: +4, its low half |
| a wall | none | none | fragment | none | none | 82 - 61 = 21: -6, a murmur |
| rooms away | by the far field | | | | | the room graph's loss vs the quiet floor |
| no air (another locale, a body unplaced) | none | none | none | none | none | |

Then, only where the relation carries `masking_db`, the masking cap (§ 11.5).

**One room.** Distance inside an enclosed room takes nothing from a voiced
line: the reverberant field carries it across any room the engine lays out.
Under the sky there is no ring: a voice falls 6 dB a doubling over the
field's own path (`spatial_sound_field.open_air_loss_db`), against the open
place's quiet floor -- a normal voice is followed to 45 paces (about 34 m,
nearly three times a 12 m street) and caught in pieces to 180; a raised one
to 140; on a still night every reach doubles. Applied only where the scene
places both bodies (a body with no station stands at the room's centre on
the field, a guess, and a guess must not take a voice away).

**Breath** (`UNVOICED_VOLUMES`: whisper, mutter) is private beyond reach.
Where the field places both bodies, by the paces of its own path between
them (`rel["paces"]`): a whisper is whole to `WHISPER_REACH_PACES` 2 and
lost beyond; a mutter whole to `MUTTER_REACH_PACES` 3, in pieces to
`MUTTER_PIECES_PACES` 4, lost beyond -- the distances the field gave a still
room before, kept as the privacy they were, less the whisper's band of
pieces at three (the owner: lost beyond reach). Elsewhere by the reach tier
(`rel["reach"]`, `spatial_rel_between`: a standing contact is within reach,
then the measured tier -- `measured_proximity_rel`, never the default --
and across an opening the doorway: both at it within reach, one near).
Unmeasured -- nothing places the two apart -- breath is whole, as it always
was. Noise no longer shortens any of it.

**A shut door** is spoken through when ONE body stands at it, either side
(`door_reach`): a path has no direction, and the man at a cottage door and
the woman stepped back two paces into the tiny room beyond it (177 t21)
are the same path both ways. With nobody at it a normal voice is muffled.
A heavy door or a pane keeps its stronger loss, a rung past a light door
everywhere.

**Rooms away** (`far_loss_db`, stamped for rooms the room graph joins
beyond the next one): the speaker's level at their cell less the far field's
loss, against the listening room's QUIET floor (`quiet_floor`: the
place's own level, never its weather or what runs in it), at the speech
margins; a way that crossed anything heavier than a shut ordinary door
(`FAR_CLEAR_EDGE_DB` 25) leaves the voice its low half -- in pieces at best.
A normal voice down a run of open doorways is whole three rooms on, in
pieces from four, gone at eight.

### 11.4 Noise never masks speech -- but for what the story makes deafening

`MASKING_LEVELS` = `deafening`, `thunderous`, `catastrophic`, and a one-beat
event the story says DROWNS everything out (`sensory_events[].drowns`,
literally `true`; priced no quieter than `deafening`). Nothing else -- a
kettle, a fire, rain, a gale, a crowd's murmur, a clock, an engine written
`loud`, another voice -- ever reaches a line.

The decision the brief asked for: **masking is simply gone below
`deafening`; `loud` is not capped.** The class word is a model's judgement
of an everyday thing, and across what it names (65-85 dB at a pace) a voice
that shares the noise rises with it (Lombard, +3 to +10 dB and up to a
shout) while a sentence is still followed at 0 dB and caught to -12 -- in
the world people talk in kitchens, workshops and on launches, raising their
voices. `deafening` (a klaxon, a siren, a jackhammer: 95-110) is the first
class whose every member stands above the ceiling a voice can be raised to,
which is what masking noise is. `loud` kept its 80 dB for what it still
decides -- how far a sound reaches and what the room's noise words say --
until the owner ruled § 11.8's question 1 the same day: it is a household
level now, 65 dB at a pace (§ 11.9).

**Corrected by wave A (§ 12.1), for one listener:** "nothing else ever
reaches a line" let a bystander anywhere in a busy tavern follow every word
at another table. It stays true for the people talking to each other -- the
line's addressee and anyone within conversational reach -- and for rain and
a quiet house, which are never a din; for a bystander beyond conversational
reach a din at their own ear limits what they follow (`din_level`).

### 11.5 Within the source's reach: the masking budget

`spatial_sound_field.masked_level`, read only where `stamp_sound_relation`
found masking noise at the listener's ear (`SoundField.masking_db_at`): the
field's own intensity from each masking source -- held, in the source's own
enclosed room, to the room's diffuse level (`VOICE_ROOM_DROP_DB` under its
level at a pace), because a klaxon fills the room it sounds in -- plus the
quiet floor. The voice: its level at a pace, raised over the masking noise
where the SPEAKER stands (`lombard_level_db`, to a shout at most), less the
rule's own path (`_voice_path_loss_db`: nothing within reach, the room's
drop across it, the opening or door and `ROOM_COUPLING_DB` into the next
room, the far field's loss rooms away), plus `AV_BENEFIT_DB` 6 where the
listener sees the speaker's face (`seen`, which the composer passes from
the view's own sight grade). Graded at the speech margins. In a klaxon
hall: a voice at arm's length is caught in pieces, one across the hall
lost, a watched one across it in pieces; breath lost everywhere; two people
talking in the yard outside the hall's shut door untouched.

### 11.6 What was retired, and what stays for whom

Retired with the speech grade: `sound_field_hear_level`, `open_edge_floor`
and `one_opening_away` (a raised voice through an opening is simply whole
now), the `door_gain` ceiling and `SoundField.door_gain` (masking is the
deafening source's own), `SoundField.gain_between` / `gain_parts` /
`speech_level` / `speaker_noise`, `WITHIN_REACH_SIGNAL_GAIN`, the `signal` /
`noise` / `source_noise` / `open_edge` / `reverberant` / `echo` relation
stamps, the `speakers` parameter of `sound_field` and `sound_sources` and
its `speech` source kind (no reader in the engine ever passed it; one voice
never masks another), and the ring's smear of speech (`REVERB_SMEAR_DB`,
`EARLY_WINDOW_S`, `C50_SMEAR_DB`, `clarity_db`: it put the cell path back
into a voice in one room, and fired on none of the 2,408 lines replayed).

Kept, each for a reader that is not speech: the flood and its constants
(every sound's reach on the near field, `heard_events`, `level_of`,
`sound_shape`, the map editor's hearing overlay), `FULL_SNR` +3 dB (a SOUND
heard plainly; `distant_level_word`'s `plain` rung needs it -- moved to 0 dB
it emptied the `faint` rung), `noise_at` (what a sound is heard over), the
Lombard function (now the masking budget's), the ring (`ring_boost_db`, the
echo of an event, the bearing that "comes from everywhere"), the noise words
`quiet | din | drowned` byte for byte -- DESCRIPTION of how far a voice must
rise, never a verdict -- and the far field entire.

`pitched_level_db` is restated: the quietest WORD the rule carries to the
addressee whole (a whisper within reach, a mutter at three paces, an
ordinary voice across a room, a raised one through a shut door from farther
off), returned as that word's level so every caller keeps reading a level.
A pitched line can be private only within breath's reach; beyond it, the
room hears an ordinary voice.

`hearing_reason(rel, volume, ...)` names the clause that decided a line
short of whole (`breath_beyond_reach`, `open_air_distance`,
`breath_through_a_door`, `shut_door_from_farther_off`, `heavy_door_or_glass`,
`wall`, `rooms_away`, `rooms_away_muffled`, `deafening`, `no_air`,
`conducted`); perception's speech decision note carries it, and
`tools/speech_replay.py` reports by it. The replay tool also read the wrong
checkpoints (idx-1 and idx, one beat early); checkpoint N is the world
BEFORE turn N, so the onset pass reads idx and the outcome pass idx+1.

### 11.7 Per principle: before, and now

| principle | before (HEAD 56b5d633) | now |
|---|---|---|
| 1. Indoors the reverberant field holds a voice across a room | a voice faded 10 log10(1 + L^2) per cell as in open air, then met every noise in the room | in an enclosed room distance takes nothing from a voiced line; the masking budget holds voice and noise to one diffuse drop; under the sky the free field is the law (45 paces for a normal voice) |
| 2. Intelligibility tolerates noise | full at +3 dB, pieces to -12 | full at 0 dB for speech (`SPEECH_FULL_SNR`), pieces to -12; in-building entries sit 8-33 dB from either line |
| 3. Lombard | a normal or raised line rose over the speaker's whole noise inside the SNR grade -- rescuing some lines, and on the rival story turning a stale "soprano" room sound into a voice carried through a shut door | the rise is why everyday noise takes nothing; computed only in a deafening source's reach, raising the voice to its ceiling before masking is judged |
| 4. Noise is not all alike | every running thing, the weather, the crowd and any second voice counted as broadband masking at its class level; one-beat events already excluded (2026-09-25) | only `deafening` and above, or an event the story says drowns everything, masks; narrowband, fluctuating and everyday noise never does. Spatial release is not modelled: it would move the edge of a deafening source's reach by 3-6 dB in the open and little in a ringing room |
| 5. Everyday levels are modest | `loud` = 80 dB at a pace for whatever the model called loud; a kettle masked a shout | `loud` decides no line, and since the owner's ruling it is a household level, 65 dB at a pace: a `din` at most, heard in its room and the next (§ 11.9) |
| 6. Barriers | real losses on the field, but the verdict also charged per-cell spreading on both sides and every noise | the table's barrier rows, each a budget with margin; one body at a shut door carries a normal voice; a heavy door a rung more; a wall a shout's murmur; rooms away the far field's loss, muffled past a light door |
| 7. A seen face | nothing (a line lost in noise could still be seen spoken: "seen speaking, unheard") | +6 dB (`AV_BENEFIT_DB`) in a deafening source's reach where the listener sees the speaker |

### 11.8 Measured, and the owner's questions

Offline, no model call and no network (every socket refused), every
recorded `speech_percept` decision re-graded through the engine's own
`composer.line_hear_level` on its beat's checkpoint -- onset on checkpoint
idx, outcome on idx+1 -- at HEAD 56b5d633 and with the rule: the owner's
`engine.db` read `mode=ro` (every chat that recorded decisions, 118-178) and
copies of the four 2026-09-26 test stories (opera/rival, harbour/homecoming,
fort/betrayal, schoolhouse/lie). 2,408 decisions; 2,296 on distinct beats
(177 and 178 repeat 176's opening turns). HEAD's replay reproduces the grade
the live play recorded on 2,204 (91.5%; the replay had read idx-1 and idx,
and reproduced 69-79% on 2026-09-26).

| distinct beats | before (HEAD) | after | raised | lowered |
|---|---|---|---|---|
| all | full 1,932, fragment 198, none 166 | full 2,088, fragment 36, none 172 | 176 (172 to full) | 19 |
| chats 175-178 (52 turns, 153 lines) | full 144, fragment 6, none 3 | full 150, none 3 | 6 | 0 |
| owner's chats 118-178 (1,782 lines) | full 1,619, fragment 148, none 15 | full 1,737, fragment 31, none 14 | 118 | 0 |
| opera (rival) | full 100, fragment 20, none 24 | full 106, fragment 3, none 35 | 24 | 18 |
| harbour (homecoming) | full 59, fragment 7, none 62 | full 69, none 59 | 10 | 0 |
| fort (betrayal) | full 74, fragment 17, none 38 | full 91, fragment 2, none 36 | 19 | 0 |
| schoolhouse (lie) | full 80, fragment 6, none 27 | full 85, none 28 | 5 | 1 |

In 175-178 the six raised are the kettle kitchen (176 t1-2, four normal
lines HEAD broke) and the shut door (177 t20-21, both directions). The
three still `none` are 177 t19, an artifact of the replay: Mellisande went
upstairs during that beat and the replay grades the outcome on the world
after it, while perception graded each line where it was spoken and
delivered it.

**Every line lowered (19), read as fiction.** Sixteen are one story's
player lines the 2026-09-26 interpret filed as `whisper` or `mutter` while
the prose speaks aloud ("Tell me honestly, Miss Varga -- are you entering
the commission yourself?", called from mid-stage down to the pit); HEAD
carried them across 11.8 paces of bare stage on the stage's ring, and the
rule keeps a whisper private beyond reach. The fault is the volume word
upstream -- filed `normal`, the rule hears every one whole through the
opening -- and it does not reproduce on today's engine: chats 170-178
recorded 79 of 79 player lines `normal`. Two are a normal voice from the
rehearsal room to the pit two rooms off, a fragment on HEAD only because
the speaker's voice was raised (Lombard) over the stale "soprano" room
sound § 1.167 registered; now `none`, which is what two rooms of stone do.
One is a whisper across the schoolhouse, `fragment` -> `none`: a whisper
beyond reach has no band of pieces any more.

**Every line still short of whole, by reason (distinct beats, 208):**

| reason | lines | right as fiction? |
|---|---|---|
| replay: a body the checkpoint does not place (no air) | 79 none, 3 fragment | an artifact of grading on the wrong moment's world, not a verdict |
| breath beyond reach | 62 none, 11 fragment | a whisper or mutter across a quay, a room, a stage: private, as the owner ruled. All 62 are the 2026-09-26 stories' (none in the owner's chats), and 54 are the player's own lines the 2026-09-26 interpret filed `whisper` or `mutter` -- the upstream label above |
| breath through a shut door | 23 none | yes: a door keeps a whisper and a mutter |
| conducted (a body inside another) | 21 fragment | yes, unchanged: chat 135's voice through Mirelle's mass |
| rooms away | 6 none | yes for the opera's two rooms of stone; 177 t19's three are the replay artifact above |
| deafening | 2 none | yes: chat 160/161's Site-17 klaxon, 102.6 dB at the listener |
| a shut door from farther off | 1 fragment | yes: the opera's stage to the rehearsal room, nobody at the door |
| another building, a wall, a heavy door | 0 | none in the corpus |

The owner's questions, each a constant or a reading this build had to take
(the owner answered 1, 2 and part of 4 the same day; § 11.9 is what that
built):

1. **`loud` = 80 dB at a pace.** It no longer decides a line, but it still
   decides reach: a kettle written `loud` (83 at its cell) clears
   `FAR_FIELD_ENTRY_DB` 70 and is heard rooms away, and its room reads `din`
   or `drowned` near it. Re-anchoring `loud` at 70 ("a loud household or
   street sound") would keep it a near-field thing; a real engine would then
   be written `deafening` or under-reach by 10 dB.
   **RULED 2026-10-20, CLOSED:** "Ordinary household objects should probably
   be scaled back." `loud` is the loudest everyday life gets -- 65 dB(A) at a
   pace, the household band's floor -- and what stops conversation is
   `deafening` (§ 11.9).
2. **One body at a shut door suffices** (the reciprocal reading of "a normal
   voice from someone AT the door is full"). It overturns the 2026-10-20
   door_reach lane's far-wall pin and makes an ear pressed to a door follow a
   normal conversation inside, as an eavesdropper does.
   **RULED 2026-10-20, AS BUILT, CLOSED:** "Ear to the door to eavesdrop makes
   sense as it's a more direct transfer of sounds." Nothing changed.
3. **A heavy door or glass from across the room** passes a raised voice and
   a shout in pieces (was: a shout only, on the edge rule; a raised voice
   whole on the field in tiny rooms).
4. **Breath radii** 2 / 3 / 4 paces, kept from the field's still room; the
   whisper's band of pieces at three removed.
   **RULED IN PART 2026-10-20:** "Whisper should probably have levels,
   whispering into someone's ears is clearly a lot quieter than a normal
   whisper." The breath ladder gains a rung under the whisper, a breath
   INTO AN EAR, which reaches its addressee and nobody else (§ 11.9). The
   radii themselves stand, still the owner's numbers.
5. **The open-air reach**: 45 paces for a normal voice (well past 12 m), from
   the free-field law and the open floor; a still night doubles it.
6. **The ring no longer smears speech**; a cavernous bare hall carries a
   line whole at any range.
7. **Unmeasured breath is whole**, as before: two unstationed bodies and a
   third in a room -- the third hears the whisper. Unchanged; registered.
   A line breathed INTO AN EAR is not distance's to decide (§ 11.9): with
   nothing measured, its addressee hears it whole and the third body
   nothing.
8. **`drowns`** is a new encoder field (one clause, en + ja); what it does on
   the page needs a live run.
9. **A voice leaving a building** is charged nothing for the open air it
   spreads into (the far field's room lengths): with both front doors open a
   normal voice reaches the parlour across a 16-pace street in pieces (42.6
   dB of loss), today and before. A doorway radiating into the sky loses
   some 20 dB more than a room would hold; an envelope term is proposed.

### 11.9 The rulings of 2026-10-20, built

**A HOUSEHOLD `loud`** (§ 11.8 question 1). `SOUND_ONE_PACE_DB["loud"]` 80
-> 65 dB(A) at a pace, 68 at its cell. A vacuum cleaner or a television
turned up is 65-75 dB(A) at a metre, and a kettle's whistle, a radio turned
up and a busy street sit in the same band. The band's floor is taken for the
two readers a standing source still has: the noise words read a source at
its OWN cell, three decibels over a pace, which is where a body standing at
the thing is placed, and a household thing reads `din` there at most (68,
and 71 with a second such thing beside it, under the 72 at which a room is
`drowned`); and the far field's entry (70 at the cell) keeps it a thing heard
in its own room and the next. At 70 a pace, the band's middle, it would read
`drowned` at its own cell (73) and enter the far field again.

The class is stated once, by what a sound does to talk beside it: anything
ordinary life goes on beside, in a home, a shop or a street, is `loud` at
most; `deafening` and above are only for what stops conversation outright.
It is in the encoder's `entities__emits` part and the room vocabulary
(which the opening and the encoder's `rooms` part carry), en + ja, and in
the Writers' Room's planned-thing and planned-room levels
(`plot_packages`). The planned-room text also lost a stale claim that a
room's own sound "drowns the voices in the room". A beat that writes rooms
and an emission together carries the clause twice, once in each part.

What reads a `loud` emission, and what changed:

| reader | after |
|---|---|
| speech (`hear_level`) | nothing: only `deafening` and above mask (§ 11.4); re-graded, 2,408 of 2,408 recorded decisions identical in every field |
| the noise words (`sound_shape`, `room_noise_word`, the `ceased` percept) | a household `loud` reads `din` at most at every cell, its own included (was `drowned` at its cell and round it) |
| the far field (`far_field_sources`, `distant_sounds`) | does not enter (68 < 70) unless a bare room's ring lifts it (`ring_boost_db`); a `deafening` one still does |
| sounds heard over it (`level_of`: events, other sources, `heard_events`, a source `sound_shape` names) | 15 dB less noise beside a household thing |
| a crowd's band (`CROWD_SOUND`: a throng is `loud`) | moves with it, 65 at a pace from the room's centre; no crowd in any checkpoint of the corpus |
| a flickering `deafening` source's dropped beat (`_power_of_level`) | drops to 65 rather than 80 |
| unchanged | the impact ladder (`EVENT_POWER`: a `loud` event is 72 at its cell and still enters the far field), a room's own `sound` (the impact ladder), `sound_walk_level` and `is_alarming` (they read the SPEECH word `loud`, a raised voice), `MASKING_LEVELS` |

Measured on every checkpoint of the owner's database that holds a running
`loud` source (77; nine sources: the kettle of chats 176-178, the TARDIS
console of 153/157/158 and the TARDIS itself in the vortex of 154, the Site-17
PA of 160/161), read-only, no network:

| source | cells of its room, before | after |
|---|---|---|
| the kettle, 176-178 (33 checkpoints) | `drowned` 25 | `din` 25 |
| the console, 153/157/158 (7) | `drowned` 26, `din` 6 | `din` 26, `quiet` 6 |
| the TARDIS in the vortex, 154 (2) | `din` 115, `drowned` 29 | `quiet` 107, `din` 37 |
| the PA, 160/161 (35) | `drowned` 144 | `drowned` 144 (the `deafening` klaxon in the same bare hallway) |

Fourteen body-checkpoints in the console room read "the noise drowns
everything" where they stood and now read the din. Far-field entries fell
from 199 source-checkpoints to 157: the kettle's 33 and the console's nine
gone, the PA still entering on its bare stone hallway's ring. Distant sounds
delivered fell from 241 to 226, all fifteen in chat 154, where the console
room had heard the ship in the vortex as `plain`.

**THE EAR RUNG** (§ 11.8 question 4, in part). `SpeechVolume.ear`: a whisper
INTO an ear, the lips at it, 20-30 dB(A) at a metre-equivalent
(`SPEECH_ONE_PACE_DB["ear"]` 25). Lips at an ear put that ear some 26 dB
nearer than a metre -- about 50 dB there, plainly -- while a body a pace off
meets the breath at a quiet room's own floor, and one half a metre off a few
decibels over it, where breath, with no voicing to follow, carries no words.
So the rung is an IDENTITY, not a distance: to its addressee it is graded as
a whisper is (`_graded_word`: whole within reach, lost beyond it and through
a door), and to anybody else it is `none` by every path -- an opening, a
body's mass, a live channel (`composer.line_hear_level` refuses it before
the channel), a name called across a barrier, a contact with the speaker
elsewhere. `hear_level(addressed=)` is the switch, and its default is the
refusal: a reader that cannot say whether its listener is the addressee
gives the line to nobody (a missed delivery costs a line; a leak costs the
firewall). `hearing_reason` names it `into_another_ear`.

The readers that grade a line for a listener ask whose ear:
`composer.speech_percept` / `communication_percept` / `line_hear_level`
(`line_addressed` reads the line's targets by name or cast handle; perception
passes its own scene-aware answer, `_line_is_to`, at onset and at outcome);
the interaction round
(`common._delivery_ok(addressed=)`); the unanswered address (the body is the
line's target); background presences (the whole-name match,
`_background_name_named_exactly`); a charter's public evidence (the one body
`resolve_target_body` gives, uncached, as a comm's endpoint is);
`address_reaches` (a flow ref); the follow rule (`_voice_reaches`, the row's
targets through `_source_bodies`); `widen_reactors_to_hearers` (the flow's
addressees). Every other caller (`can_perceive`, the frame split, the
unaddressed-line debt, the World Browser) reads the default and so gives an
`ear` line to nobody.

A pitched line never solves to it (`pitched_level_db` starts at a whisper:
lips put to an ear are an act the prose states, never a level a voice is
pitched at from where it stands) and no level rounds to it
(`word_for_level`). The views say it: the addressee is told it was said
into their ear (`dialogue_verbs.ear`, en + ja); a bystander who sees it sees
speech and no words (the "seen speaking, unheard" percept). The schema owns
the word and its plainest spellings (`normalize_speech_volume`); the
encoder's volume clause states the ladder by who each rung reaches and that
`ear` names its listener in targets; the read-back's "how loudly" offers it
(`options.volume.ear`), its whisper option now "for whoever is within arm's
reach" (en + ja).

NOT DERIVED FROM THE SCENE. A `whisper` whose speaker stands in contact with
the addressee's head stays a whisper: the scene holds no typed fact that a
mouth is at an ear -- a contact's parts are the Director's own words, and
reading one as a mouth or an ear needs the body-part vocabulary
`spatial_contacts.canonical_region` refuses -- so the clause in the encoder's
card states the class instead.

Measured: no recorded line is `ear`, so the re-grade moves nothing (2,408 of
2,408). Of the 357 breath-level decisions on distinct beats (whisper and
mutter), read against the beat's own lines: 85 reached the body they were
spoken to (8 did not); 149 reached a listener from a line whose record names
no target, or whose line the record does not give (91 did not); and 12
reached a body the line was not spoken to -- a mutter "to" a massage table
(chats 135/137/155 turn 15) and a whisper across a group at arm's reach (the
betrayal story's turns 6 and 15, the lie story's turn 13). The prose put
none of those twelve at an ear, so no recorded whisper is one the new rung
would treat differently. One of them is the case the rung is for: in the lie
story's turn 13 the boy whispers to the schoolmistress with the magistrate
within a whisper's reach, the rule hands it to him, and the page kept it
from him ("the only sound is the nib on the page") -- written `ear`, it
would have been kept from him by the engine too. The prose put lips at an ear in 4 of the 512 beats
with speech (chats 135/137 turns 35-36: Mirelle to Hinami, nobody else
present), and all four lines name no addressee.

Owner questions left:

1. **`loud` at 65, the band's floor.** Chosen for the two readers above; at
   70 a household thing reads `drowned` at its own cell and enters the far
   field.
2. **An `ear` line that names no addressee reaches nobody.** Measured, 4 of
   27 whisper decisions in chats 161-178 came from lines naming no target,
   and the four ear-prose lines of chats 135/137 named none. Demoting such a
   line to a whisper would hand it to every body within reach; the encoder's
   clause asks for the listener instead.
3. **The read-back's two options** (`ear` "Into one person's ear, your lips
   at it."; `whisper` "In a whisper, for whoever is within arm's reach.")
   need a Jev probe in each pack; an unresolved addressee there (the
   speaker's own description of a stranger, UNBUILT_CHARACTERS § 6.19) loses
   an `ear` line the same way.
4. **Derivation from contacts**, declined above, is the owner's to reopen.
## 12. Wave A: four real-world concepts (2026-10-20)

The owner's go, the same day as § 11: "I guess go ahead". § 11 restated the
hearing rule on real-world budgets and, to keep every error from running one
way again, let no noise below `deafening` touch a line. Four things the world
does were still missing, and the first of them § 11 had over-simplified away.
Each is stated as a class in the engine's own vocabulary, with its real-world
basis beside its constant, and each was built failing-first
(`tests/test_a_din_keeps_a_far_tables_talk.py`,
`tests/test_tone_travels_farther_than_words.py`,
`tests/test_a_voice_is_known_by_its_sound.py`,
`tests/test_footsteps_come_through_floors.py`).

### 12.1 Privacy in a din

**The over-simplification.** "Noise never masks speech except deafening" let a
bystander anywhere in a busy tavern follow every word at another table.

**The world.** In babble or music around 65-75 dB(A) the people TALKING TO
EACH OTHER raise their voices (Lombard) and, a pace or two apart, understand
each other; a bystander a few paces off has the same raised voice's DIRECT
sound 10-15 dB down against the same din, and gets pieces of it or only the
fact that people are talking -- energetic masking, plus the informational
masking of competing talk: the cocktail-party effect cuts both ways. The room's
ring, which carries a voice across a QUIET room (§ 11.3's one-room row), is
under the din, and reverberant speech is the smeared part a listener cannot
use.

**The class.** Noise never stops people talking to each other -- the line's
addressee, and anyone within conversational reach of its speaker. A din at the
ear of a bystander beyond conversational reach limits what the bystander
follows. Rain and an ordinary quiet house are not a din.

**As built.**

* `spatial_sound_field.stamp_sound_relation` stamps `din_db` -- the noise at
  the listener's ear (`SoundField.noise_at`: standing sources, crowds, the
  room's own sound, the ambient floor and the weather; never a one-beat event)
  -- where it is at least `DIN_DB`, and `speaker_din_db` at the speaker's ear.
  Only where the field places both bodies (`paces` is the budget's distance).
* `DIN_DB` = 57 dB(A): the `din` rung's floor in the noise words
  (`VOICE_ONE_PACE_DB - FULL_SNR_DB`), where a normal voice one pace off is no
  longer followed as it is. Babble and music at 65-75 are a din; rain (37 at
  its heaviest) and a quiet house (25-35) never are -- the owner's rain ruling
  holds by construction -- and the view that says "you are in the din" and the
  rule are one number.
* `CONVERSATION_REACH_PACES` = 2.0: the people around one table or standing
  together, the distance groups close to in a din.
* `spatial_senses.hear_level(..., addressed=)`: `_bystander_in_a_din` caps a
  voiced line for a listener it was not addressed to (`addressed is False`),
  beyond conversational reach (a standing contact is always within it), by
  `spatial_sound_field.din_level`: the speaker's level raised over the din at
  THEIR ear (`lombard_level_db`, up to a shout), less the free-field spreading
  over the field's path (`spreading_loss_db`, 6 dB a doubling) and an
  opening's own loss, plus `AV_BENEFIT_DB` for a watched face, graded against
  the din at the speech margins (`quantise_speech_db`: 0 / -12 dB). `addressed`
  None -- a caller that does not know -- caps nothing. `hearing_reason` names
  it `din_bystander`.
* WHO IT WAS SPOKEN TO is read by `composer.line_addressed` (a line's
  `intended_target`, or a span's `targets`; a line said to nobody in
  particular was spoken to nobody) for both perception passes -- the onset
  entry now carries its `intended_target`, which it had dropped, so every
  onset line read as addressed to nobody -- by the interaction loop's round
  (`_delivery_ok`, `loops.deterministic_micro_perception`) and by the three
  background-presence readers (`background._addressed_to`).
* WHERE THE DIN EXISTS. A crowd's talk is priced by its band at a real babble
  level (`CROWD_BABBLE_DB`: a handful 55, a dozen or so 62, a few dozen 68, a
  throng 75 dB(A); restaurants and canteens measure 60-80, a busy one around
  70) and FILLS the room it stands in (`SoundField.intensity_at`); it was a
  point at the room's centre on the emission ladder, so a few dozen people
  talking were a 50 dB hearth fire and no crowd short of a throng was ever a
  din. Music is a room's `sound` or a running thing's `sound_source`, at its
  level. Whatever level a household or an industrial source is re-anchored to
  (§ 11.8 question 1, the l7 lane), the rule reads the field's own decibels,
  never a word. A crowd's `mood` is not read (free prose).

In a taproom ten paces by eight, the speaker A, the one spoken to B beside A,
E at A's elbow (1.4 paces), D 2.4 paces off and C at the far table (9 paces),
a normal line not addressed to the listener:

| crowd | din at C | B (addressed) | E (1.4) | D (2.4) | C (9) | C's voice rung |
|---|---|---|---|---|---|---|
| none | 27 | full | full | full | full | -- |
| a handful | 55 | full | full | full | full | -- |
| a dozen or so | 62 | full | full | full | fragment (a raised one whole) | -- |
| a few dozen | 68 | full | full | full | fragment (raised and shouted too) | -- |
| a throng | 75 | full | full | fragment | none | the voice carries |

A watched speaker across a throng is caught in pieces rather than lost; a line
spoken TO the far table is whole in all of them.

### 12.2 Tone travels farther than words

**The world.** Through a wall, a door or distance a listener detects a voice
-- that someone spoke, how loudly, its pitch and its emotional colour --
some 10-15 dB below the level at which its words come through (the speech
detection threshold sits about 8-12 dB under recognition), and a partition
takes a voice's consonants and leaves its low half, the vowels and the tune.

**The class.** Where a line's words do not come through, the fact of the
voice, how it sounds and its tone can still come through, down to a lower
threshold. Tone is a channel; words and names are not, unless they come
through.

**As built.**

* `TONE_BELOW_WORDS_DB` = 10, `VOICE_TONE_SNR_DB` = -22 dB: ten decibels
  under the last caught word (`FRAGMENT_SNR_DB`), the near end of the range.
* `spatial_sound_field.voice_margin_db` is the voice's budget, from the same
  numbers the table is written against: rooms away the far field's loss,
  under the sky the open air's, otherwise `_voice_path_loss_db`'s path classes
  (the room's drop, the opening or door, the spread into the next room, a
  wall), against the listening room's quiet floor; with `masking_db` or a din
  the weaker of that budget and the path's.
* `spatial_senses.voice_carries(rel, volume, ...)`: True where any word
  arrives; where none does, where the margin is at least `VOICE_TONE_SNR_DB`.
  Never for breath, never through a body's mass, never with no air.
* `composer.speech_percept` mints, where the words are lost and the voice
  carries, a hearing percept with fidelity `voice`: no body, no fragment, the
  speaker's label only where the listener knows the voice or sees the speaker
  (`attributed`), the line's loudness, the bearing it came from, and the tone
  it carried (`tone_heard`). One per speaker per beat (`speech-voice:` dedupe).
  "Mara's voice, raised, beyond the wall -- the words do not carry. It sounds
  furious." Both packs and the memory renderers say it (`speech_voice*`,
  `episode_speech_voice*`). A fragment carries its tone too. The "seen
  speaking, unheard" sight percept stays for a noise that took the voice as
  well.
* THE TONE FLOOR (`composer._carried_tone`, a deterministic guard): a line's
  `tone` is free prose its speaker's model wrote, and what crosses a wall with
  a voice is its colour, never what it was about. Only the tone's first part
  is carried, and only shaped like a voice quality: it fits the manner slot,
  holds no digit or quotation, no capital after its first letter (a name), is
  not conduct the pack's tone reader already calls conduct, and shares no
  word with the line itself. Anything else is withheld whole. Measured on the
  owner's tones: the heads that pass are "furious", "dry", "panicked",
  "warm"; withheld are "flustered and bright", "Warm and lightly teasing,
  glancing over her shoulder", "settling into the chair across from her",
  "mocking Ivo" and a tone holding a word of its line. In a spaced script
  the carried head is ONE word: a phrase is where what the voice did ends
  and what the body did ("murmured against skin") or what the line was
  ("whispered command") begins.
* THE `trace` LEAK, found here and closed: a sense card's `trace` -- detected,
  no words, no identity (`sense_adjusted`) -- fell through `speech_percept`'s
  full branch, so an extraordinary ear behind a wall was handed the line
  verbatim under "the unfamiliar person". It is now the contentless
  `_trace_percept` ("A faint voice beyond the wall -- nothing you can make
  out."), in `communication_percept` too.

| path, a voice into a quiet room | words | the voice |
|---|---|---|
| a wall, normal voice | none (-28 dB) | no |
| a wall, raised | none (-18) | yes |
| a wall, shout | fragment (-6) | yes |
| a heavy door or glass, nobody at it, normal | none (-11 to -18) | yes |
| rooms away down open doorways, normal | pieces from four rooms, gone at eight | beyond the words |
| a whisper or a mutter through a door | none | no -- breath has no voicing |

### 12.3 A voice is recognised by its sound

**Verified first** (`composer.observer_display_map`, perception's
`_attributed_label`): a speaker the listener recognises -- the `known` ledger,
with `disguise_breaks_recognition` on the way -- is named whether seen or not,
for a whole line and a fragment ("A VOICE YOU KNOW IDENTIFIES ITS OWNER, SEEN
OR NOT", built 2026-09-05 on the owner's § 1.136 ruling). A stranger who cannot
be seen is "a voice" -- the English literal, in a Japanese view too -- and
nothing of how the voice sounds reached the listener: the speaker's register
was said only in the manner slot of a line SEEN in full.

**What the cards hold.** A character card has `social.voice` -- `register`
(how the voice sounds and is used: "low contralto, warm and unhurried",
"Clinical, deadpan, and strictly monotone"), `cadence`, `verbosity`, `markers`
(verbal tics: content) and `notes` (often what the character says). 61 of the
owner's 70 characters fill `register`. A persona card has none -- its
`narration.voice_setting` is the narration's -- and nothing on either card
carries a voice's sex, rough age or accent as a fact about sound (pronouns are
a gender, not a voice).

**As built.**

* An unseen stranger's voice is described once, after whatever of the line
  arrived (`voice_apart`), by the speaker's own register: "You hear a voice
  say: '...' The voice is low contralto, warm and unhurried." It files the
  voice as heard (`voice_key`), so it is not said again, and never names
  the speaker.
* THE REGISTER FLOOR (`composer._register_heard_unseen`, a deterministic
  guard) keeps review round 4's refusal (2026-10-05) where its reasons hold:
  sheet text can NAME the body it belongs to, and a register that is a
  clause is prose about anything. Only a register every part of which fits
  the manner slot, and which holds no word of the speaker's name, is said to
  a listener in the dark.
* A speaker the listener sees keeps the manner slot, as before; a known voice
  through a wall is named on the voice rung (12.2).
* The unseen speaker's label is the story language's own word
  (`unseen_voice_label`: "a voice", 「誰か」).

**Proposed, not invented:** `embodiment.voice` on character AND persona cards
-- what a listener who cannot see the body hears of it: sex, rough age,
timbre, accent -- the hearing sibling of `visible.summary` and `scent`. The
register would stay the voice's use; this would be its sound.

### 12.4 Footsteps and thuds come through floors

**The world.** Impact sound -- a footfall, a dropped weight, a slammed door, a
body falling -- is made in the structure and travels through it far better
than airborne speech: on a timber floor a footfall above is plainly heard
below; stone or earth carries less; a sneaking step, soft footwear or a carpet
carry less again.

**What existed.** `tread_events` (2026-09-15): a tread in the walker's room
and one in every room it declares itself `over`, at the floor's impact level
(`FLOOR_IMPACT_DB` timber 55, masonry 40; a run `TREAD_RUN_DB` +8), for the
bodies the resolve's travel record walked. 4 of the 238 sited rooms in the
owner's scenes declare `over`, so a body pacing a laid-out cottage's bedroom
reached nobody in the kitchen under it; and a walk the encoder wrote as a
`positions` patch made no footfall anywhere (chat 177 turn 19).

**The class.** A body that moves on a storey makes footfall impacts heard on
the storey below and in the rooms beside it, graded by the floor's material
and the gait. The listener learns that someone moves overhead, not who.

**As built** (`spatial_sound_field.tread_events`, `footfall_db`, `tread_gait`;
`site_plan.plan_rooms_below`, `plan_rooms_beside`):

* the rooms under the walker are the plan's (a storey down on one plan, a
  cell under a cell) as well as the declared `over`, never a room a way joins
  it to (a stair carries a tread through the air);
* the rooms beside it are those the plan sets wall to wall with it and those a
  declared way that is not an opening joins it to on its storey, at
  `FOOTFALL_FLANKING_DB` = 15 under what falls straight down (flanking
  transmission, 10-20 dB);
* the gaits are a closed set on the walk's `pace` (`TREAD_GAITS`): `sneak`,
  `walk`, `run`; a sneak is `TREAD_SNEAK_DB` = 15 under a walk (measured impact
  peaks fall 10-20 dB from a firm walk to a slow soft one) and makes no tread
  in its own room. The encoder is told the value in one clause (en + ja):
  "pace is run when the step runs, and sneak when the body moves so as not to
  be heard";
* a footfall is filed in a room only where it is heard over that room's own
  floor (`_footfall_heard`: the place and its weather, a sound's margins);
* the movers are the travel record's walkers and every body of the cast or the
  player the beat took to another room on its own feet (`perception.
  _beat_movers`), never a carried one.

| footfall, into a quiet room (27) | below, timber | below, masonry | beside, timber | beside, masonry |
|---|---|---|---|---|
| sneak | 40, heard | 25, not | 25, not | 10, not |
| walk | 55 | 40 | 40 | 25, not |
| run | 63 | 48 | 48 | 33 |

Thuds are not built: a one-beat impact event above reaches the room below only
by the far field (70 dB and up at its cell) and only through a declared `over`
(`spatial_levels.floor_edges`) -- § 12.6.

### 12.5 Measured

Offline, no model call and no network (every socket refused), through the
engine's own readers, on the owner's `engine.db` read `mode=ro` and copies of
the four 2026-09-26 stories (opera, harbour, fort, schoolhouse; copies deleted
after). Scripts in the wave's lane directory: `regrade_a.py` (l6's regrade,
plus each line's addressee from its beat's `dialogue_log` -- 1,172 of the
2,296 distinct lines addressed to their listener, 809 to someone else, 264
unmatched and graded with no addressee, 51 mixed -- and the listener's sight
of the speaker), `compare_a.py`, `footfalls.py`, `tone_floor.py`.

* **Privacy in a din: 0 of 2,408 recorded lines change.** A din reaches the
  listener's ear on 162 distinct lines -- the TARDIS console written `loud`
  (chats 153-159), Site-17's PA and klaxon (160-161), the kettle (176-178),
  the opera's soprano and piano (the rival story) -- and every one was
  addressed to its listener, within conversational reach, or spoken a few
  paces off by a speaker who rises over the din and is watched: the kettle
  kitchen's line said to nobody in particular, three paces from Hinami with
  75 dB at her ear, arrives at 73.5 dB of raised voice and 6 more for
  Mellisande's face, +4.4 dB, whole. No live scene holds a crowd record. The
  rule bites where no recorded story has yet gone -- a full room of talk --
  and the table in § 12.1 is that room.
* **The tone rung: 7 of the 163 distinct lines whose words are lost still
  carry their voice.** Three rooms away (chat 177 turn 19 between the
  kitchen and the room above it, graded on the world after the beat -- the
  replay artifact § 11.8 names -- and the opera's rehearsal room to the pit,
  two rooms of stone), and the two lines in Site-17's klaxon (chats 160 and
  161, the deafening rows), where Hinami's line to Sarah Moon -- who
  sees her and does not yet know her -- is now her voice under Sarah's
  descriptor for her, "the words do not carry". None of the 62 lines of breath
  beyond reach or the 23 through a shut door carries (breath, as ruled), nor
  the 70 the replay cannot place.
* **A stranger's voice: 37 distinct lines reach a listener who neither sees
  nor recognises the speaker.** 33 come from a body with no register (a
  persona, a background presence); 2 now say "The voice is clinical,
  deadpan, and strictly monotone." (Sarah Moon to Hinami at Site-17's
  opening, chats 160 and 161); the floor withholds the Doctor's clause
  register on 2 (chat 153 turn 25).
* **The tone floor**, on the 272 distinct toned lines of the owner's chats
  118 on: 201 would carry a one-word head -- "warm" 50, "low" 27, "flat" 14,
  "soft" 8, "bright" and "dry" 7 each, "flustered", "husky", "panicked",
  "exasperated" -- and 71 are withheld whole: every phrase head ("murmured
  against skin", "whispered command", "sharp and commanding"), every head
  of four words or a clause, and those sharing a word with their line.
* **Footsteps: at HEAD no beat of the 4,347 with a checkpoint pair (every
  chat in the owner's database and the four stories) delivered a footfall
  to a body on another storey or in the room beside; now 7 beats do (5
  distinct, chat 178 repeating 177's).** One below -- chat 177 turn 19,
  Mellisande up the stair, "footsteps overhead" to Hinami in the kitchen
  under the timber -- and four beside, "footsteps through the door": chat
  177 turn 20 (Hinami up to the landing, heard by Mellisande in the room
  off it), the opera's stage heard in the rehearsal room (turn 9), the
  schoolhouse heard on its front step (turn 2) and in its back hall (turn
  6). Only chat 177 turn 20 is reachable through the resolve's travel
  record: 469 beats moved a body to another room with no travel row, and 37
  had one. A walker's own-room tread reaches a body that cannot see them on
  14 beats with room-change walkers counted, 3 without.

### 12.6 The owner's questions, and what is left

Each a constant or a reading this wave had to take, and the owner's:

1. **Conversational reach, 2 paces.** A pace or two; a table of four is
   inside it. At 3 a bystander at the next table follows more of a din.
2. **The din is the noise words' `din` rung, 57 dB(A)** -- tied to the
   words so the view and the rule agree. A fixed 65 (the low edge of
   babble and music) would leave a dozen people talking a quiet room.
3. **The crowd's babble by band**, 55 / 62 / 68 / 75 dB(A), filling its
   room; and whether a raised `mood` (a brawl, a wedding) should add to it --
   still unread, free prose.
4. **Babble's informational masking is not apart from its level**: a
   bystander in talk loses some few decibels more than in a machine's noise
   of the same level; the margins are the speech margins.
5. **A watched face across a din is worth 6 dB** to a bystander, as to a
   listener in a klaxon's reach.
6. **The tone rung, 10 dB under the last caught word** -- the near end of
   10-15. At 15 a normal voice through a masonry wall would be heard as a
   voice too.
7. **Breath has no voice rung** -- the owner's privacy ruling read strictly.
   The fact that someone is whispering, a few paces off, is real; whether it
   should reach a mind is the owner's.
8. **The tone crosses a wall only as one word** of the speaker's own `tone`,
   under the floor. A typed vocal affect on a spoken event (a closed set the
   engine would own) is the clean channel; it would be an encoder field and
   a clause, so it is proposed, not built.
9. **A stranger is described by their register**; `embodiment.voice` (sex,
   rough age, timbre, accent) on character and persona cards is proposed.
10. **The footfall numbers**: a sneak 15 under a walk, a flanking path 15
    under the room below; and a sneak walks at a walk's pace.
11. **A room change is a walk**: a body the beat took to another room is
    heard walking there -- a cut or a carried body excepted, a teleport not.
12. **The encoder clause**: "pace is run when the step runs, and sneak when
    the body moves so as not to be heard" (en + ja). Its effect needs a live
    run.

What is left is registered in `docs/UNBUILT_PERCEPTION.md` § 2.36 (breath's
voice, thuds through a sited building's floors, a sneak's pace, footwear and
coverings, the round's voice rung, the callers that pass no addressee,
`known` as recognition, the persona's voice, babble's informational
masking) and § 1.209 of `docs/UNBUILT_WORLD.md` (floor coverings).
