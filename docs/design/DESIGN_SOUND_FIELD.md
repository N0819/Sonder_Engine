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

**WAVE B1, 2026-10-20** (§ 13): the LISTENER'S state, which every path ends
at. A sleeper wakes to a sound loud for the room, or to their own name; a
listener's own machine and their covered ears lower what reaches them; a
blast leaves an ear dulled and ringing, recovering with the clock; a steady
sound fades from every mind's attention and its stopping is told once; and
one's own name comes through a line otherwise lost.

**WAVE B2, 2026-10-20** (§ 14, how sound TRAVELS; § 13 is the listener's
state): a voice is directional, and behind its speaker the words fall
first; outdoors the wind is noise at the ear and bends a sound's reach by
its direction; a sound arrives after the sight of what made it; and loud
sound is felt through what a body stands on. Found on the way: two places
under the sky joined by an opening are one stretch of open air.

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
  particular was spoken to nobody -- and, since § 14.8, is UNKNOWN to every
  reader, None, where an empty field had read as "somebody else") for both perception passes -- the onset
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

## 13. Wave B1: the listener's state (2026-10-20)

The owner, the same day: "the system is failing to meet several real world
principles", and, on this list, "I guess go ahead". §§ 11 and 12 price the
PATH between a speaker and a listener. Nothing priced the one thing every
path ends at: the listener's own ear -- whether its owner is asleep, making
noise, covering it, or ringing from a blast -- nor what an ear does over
time (it stops attending to a steady sound, and notices it stop) or with one
word above all others (its owner's name). Wave B1 builds the five, each from
typed state only, each stated with its real-world basis beside its constant
(`world/spatial_listener.py`, re-exported by the `world/spatial.py` facade),
and each failing-first (`tests/test_a_sleeper_wakes_to_sound.py`,
`tests/test_your_own_noise_and_covered_ears.py`,
`tests/test_a_blast_dulls_hearing.py`,
`tests/test_getting_used_to_a_sound.py`,
`tests/test_your_own_name_catches_your_ear.py`). Lane B2 (how sound
TRAVELS: facing, wind, delay, vibration) ran beside it.

### 13.1 A sleeper wakes to sound

**The world.** A sleeper is woken by a sound loud or sudden for the room --
behavioural awakening climbs steeply across about 50-70 dB(A) at the ear (a
smoke alarm must put 75 dB(A) at the pillow to wake nearly every adult) --
or by a meaningful sound far quieter, their own name above all (the
own-name effect in sleep). A steady murmur does not wake them.

**What existed.** A non-awake mind gets a content-free residue
(`composer.residue_percepts`, `common._compose_residue_view`). Three waking
rules live in `director_floors._awareness_exits` (the player's own
declaration; a rouse aimed at a sleeper; a full night on the clock) -- and
they run only inside `_reconcile_resolution`, which a beat with encoded rows
skips (`UNBUILT_PIPELINE.md` § 1 item 3), so on today's prose path waking is
the encoder's, by one clause ("a noise reaches them") with no model of what
reaches an ear. The residue's "a sound, huge and wordless, reaches down" fired
for any loud or shouted line ANYWHERE in the beat -- another building's
included, and the sleeper's own cry.

**The class.** A sound reaching a sleeper's ear at `WAKING_DB` and standing
`WAKING_EMERGENCE_DB` out of the room's steady noise, or their own name in a
line whose words would reach them awake, wakes them. Nothing quieter does.
Only sleep: a sedated or unconscious body is not woken by a sound (dosage and
medicine, the line `_awareness_exits`' third rule draws). The woken mind is
told what woke them and nothing else; the commit ends the sleep; from the
next beat they perceive as anyone awake does.

**As built.**

* `WAKING_DB` = 60 dB(A) at the ear, the middle of 50-70: a voice RAISED
  anywhere in the room wakes a sleeper, a normal one only at the bedside, a
  conversation across the room never. `WAKING_EMERGENCE_DB` = 10: what wakes
  is loud or sudden FOR THE ROOM (a sleeper on an engine deck sleeps through
  what wakes one in a bedroom). `SOUND_WAKES` = `asleep`.
* `perception._sleep_hears` (the outcome pass, for every perceiver under):
  the beat's lines -- each voice at the sleeper's ear by the hearing rule's own
  path, `spatial_listener.voice_at_ear_db` -- its one-beat sounds on the
  sleeper's field, far sounds the room graph brings (`distant_sounds`), and a
  running thing that STARTED this beat (`started_sources`, measured against
  the room's noise without it); a thing already running when they went under
  is the room's own and is slept through. Through whatever covers the ears
  (§ 13.2). Their own name (`composer.own_name_forms`, § 13.5) wakes them
  where `hear_level` gives the line's words at all. A body with no hearing is
  woken by none of it. Only a sleeper asleep when the beat BEGAN
  (`_asleep_when_the_beat_began`: every active awareness row on them
  `asleep`) -- a sleep the beat itself began is not ended by its own sounds.
* The woken view is the residue's `woke` sentence alone, by what woke them
  (`WAKING_SOUNDS`: `name`, `shout`, `voice`, `noise`; `residue.woke` in both
  packs): "A shout tears through your sleep. You are awake." -- "Someone says
  your name, and it pulls you up out of sleep. You are awake." No word of the
  line, no speaker, no room: the rest of the beat happened while they slept.
* The stage that renders the beat does not write the world: the outcome
  hands on `woken`, and the commit closes every active awareness row on that
  body under its own `condition_id` (`commit_entities._with_sound_wakings`,
  `ended_reason: woken by a sound (...)`), over a re-assertion, never over an
  ending the diff already wrote -- `_awareness_exits`' own merge rule.
* The residue's intrusion now fires only for a LOUD sound (a loud or
  shouted line, a `loud`-and-up event, a far sound) that reached the
  sleeper's ear and stood out of the room, at the outcome and at the onset
  (the player's raised line), never the sleeper's own.

A voice through a body's mass (a sleeper inside another body) has no air
budget (`voice_at_ear_db` answers None for the conducted cases), so it wakes
by name only.

### 13.2 Your own noise, and covered ears

**The world.** You hear others less while you make noise yourself -- a
drill, a hair-dryer, a vacuum cleaner at your own ear -- and hands over the
ears take about 15-25 dB, a finger or a plug in the canal 25-30; a hood or a
helmet muffles some.

**The class.** A listener's own sound, and what covers their ears, lower
what reaches them -- read from typed state only.

**As built** (`spatial_listener.stamp_listener_ear`, called by
`spatial_senses.spatial_rel_between` after the sound field's stamp; the cap
`ear_level` is `hear_level`'s fourth, after the masking and the din, in
`_capped_levels`; `hearing_reason` names `ears_covered`, `own_noise`,
`hearing_dulled`):

* COVERED (`ear_cover_db`): a settled contact over BOTH of the listener's
  ears -- the part kind `ear` by the contact ledger's structural rule
  (`_part_identity`, `_same_appendage`: "ears", "both ears", "ear canal"),
  plural or a left and a right; a covering part that is a pair (hands,
  palms, fingers) or a thing with no part. One ear, a moving or momentary
  contact (read the way the ledger reads a record saved before `motion`), a
  single thumb on "ears": nothing. On the surface `EARS_COVERED_DB` = 20 (the
  middle of 15-25); into the canal (`relation: interior`) `EARS_STOPPED_DB` =
  27 (the middle of 25-30). It takes from everything, the room's floor and
  the listener's own noise included, down to the ear's own threshold.
* OWN NOISE (`own_noise_db`): a running thing whose holder is the listener
  (`sound_sources` places it at the holder's own cell), counted only where it
  is a din at the ear (`DIN_DB`, the noise words' own threshold): a drill,
  never a pocket watch. It caps everyone, the line's addressee included --
  the din's "noise never stops people talking to each other" rests on both
  of them sharing the noise and rising over it, and this noise is at the
  listener's ear and a few decibels down at the speaker's.
* THE EAR'S BUDGET (`ear_margin_db`): the voice at the ear
  (`voice_at_ear_db`: its level, raised over the noise where the speaker
  stands where the relation knows it, less the rule's own path), through the
  covering, plus `AV_BENEFIT_DB` for a watched face, against
  `ear_noise_db` -- the room's quiet floor and the listener's own noise, both
  through the covering, and `EAR_SPEECH_THRESHOLD_DB` = 25 dB(A) (a healthy
  ear follows a sentence in perfect quiet at about 20-30 dB(A): a speech
  reception threshold of 0-10 dB HL, where 0 dB HL for speech in a sound
  field is about 20 dB SPL), summed as powers; graded at the speech margins.
  The voice rung (`voice_carries`) reads the weaker of the path's budget and
  the ear's.
* A SOUND, not only a line: `heard_events` and `distant_sounds` grade
  through the ear (`heard_at_ear`, `ear_adjusted_db`), and a one-beat sound
  in the listener's own room, received whole by an open ear as ever, is
  graded on the field for a covered or dulled one
  (`perception._reaches_this_ear`).

| hands over both ears (20 dB) | open ear | covered |
|---|---|---|
| a normal voice across the room | full | full |
| a whisper at arm's reach | full | none |
| a normal voice through an open doorway | full | fragment |
| a raised one through it | full | full |

| a `loud` drill in the listener's own hands | quiet | drilling |
|---|---|---|
| a normal line said TO them from 9 paces | full | fragment |
| a shout from 9 paces | full | full |
| a normal line from at their elbow (the voice risen over it) | full | full |
| a whisper from at their elbow | full | none |

NOT READ, each for want of a typed fact or by ruling, and registered:
the listener's own SPEECH (a beat's lines take turns and nothing typed says
two overlapped -- read as masking every other line of the beat, a speaker
would never hear an answer); a one-beat sound they make (a hammer blow is a
moment, not a floor -- the owner, 2026-09-25); a running thing they operate
but do not hold (a tap); a hood, a helmet or earmuffs (the attire ledger
knows a garment covers the `head`, never whether it covers the ears, and a
garment's name is prose).

### 13.3 After a blast, hearing is dulled

**The world.** An impulse past about 120-140 dB at the ear -- a gunshot
close, an explosion, a crash in a closed space -- leaves a temporary
threshold shift: muffled hearing and ringing, recovering over minutes to
hours, linearly in the logarithm of the time since (Ward, Glorig & Sklar
1959); a shift under 40 dB is gone within about sixteen hours.

**As built.**

* `BLAST_DB` = 120, the lower end. The shift: `DULLED_SHIFT_AT_BLAST_DB` = 20
  at the threshold, a decibel more for each over it, to
  `DULLED_SHIFT_MAX_DB` = 40 (past which the damage is not temporary, and not
  modelled) -- `blast_shift_db`.
* Recovery (`recovered_shift_db`): whole for `DULLED_HELD_SECONDS` = 120
  (TTS2 is measured at two minutes), then linear in log time to nothing at
  `DULLED_RECOVERY_SECONDS` = 16 h: some 45% left after an hour, a ninth
  after eight.
* THE BODY STATE is the scene key `dulled_hearing` (`HEARING_KEY`): `{name:
  {shift_db, shift0_db, since_seconds, exposure_db}}`, beside the body's
  other live physical state, so it rides checkpoints, archives and branches
  with the scene. The outcome measures the loudest thing at each composed
  mind's ear (`perception._blast_exposure`, `loudest_at_ear`: the field's
  placed sources and the far sounds, through any covering) wherever anything
  this beat could reach the threshold at all (`blast_possible`), and hands on
  `hearing_exposures`; the commit (`commit_scene_state._record_dulled_hearing`)
  ages every shift to the beat's end on the story clock, lays the exposures
  on (a fresh blast restarts the recovery from the larger shift) and drops
  the ears that are back (`DULLED_GONE_DB` = 1) -- `next_hearing_ledger`.
* The hearing rule reads it (`dulled_db`) as the ear's threshold raised by
  the shift; a far sound and a sound in the next room too.
* THE LISTENER KNOWS (`composer.ear_percepts`, interoception, in their own
  view only): "Your ears are ringing, and every sound comes to you
  muffled." while the shift is at least `RINGING_DB` = 10, from the beat of
  the blast (`blast_exposure`) on; "The ringing in your ears has faded."
  once, to an ear whose own ledger held the ringing. Nobody else is told:
  another body knows it only by what it sees.

| a dulled ear in a quiet hall | shift 40 | 30 | 20 | 10 |
|---|---|---|---|---|
| a normal voice a pace off | fragment | full | full | full |
| a normal voice across the hall | fragment | fragment | full | full |
| a raised voice across the hall | fragment | full | full | full |
| a whisper a pace off | none | none | fragment | fragment |

### 13.4 Getting used to a sound, and noticing it stop

**The world.** A steady sound fades from attention (habituation), and its
stopping or changing is salient: "the clock has stopped".

**What existed.** The player's delta view already drops a standing percept
it holds unchanged, and `sound_ceased_percept` ("The noise has stopped.")
reaches a player seat whose own ledger held the room's sound. The character
tier re-rendered every steady sound every beat and was never told one stop:
it computed no verdict to tell it by (`unheard_ceasing` dropped every
`ceased` percept there).

**As built** (`composer.HABITUATING_SOUND_TAGS` = the room's soundscape and a
crowd's hum; `steady_sound`, `view_verdicts`, `habituated`,
`_was_in_its_room`; both renderers):

* a steady sound is told when it starts and when it changes (its key moves:
  `changed`); between, `habituated` takes it out of the view -- on the
  character tier too, which otherwise re-tells everything every beat; an
  explicit look (`full_render`) asks for the room back;
* its stopping is told ONCE to whoever was hearing it, character or player:
  the character tier now has a steady sound's verdict (`view_verdicts`), so a
  `ceased` percept its own ledger earned renders, and the next beat's
  `unchanged` one does not; an ear that never had the sound is told nothing;
* a sound that STARTS where the observer already stood (their ledger holds
  the room's own description, `env`) leads the player's beat
  (`leads_the_beat`); a newcomer hears the room as it is, in the background;
* the character ledger files no verdicts, as before.

NOT BUILT, and the larger half of the class: "THE RAIN HAS STOPPED". Rain,
wind and thunder are no hearing percept at all -- the weather's sound is
folded into the field's floor, and the narrator's manifest re-derives its
words every beat, unkeyed (`narration.py`, `weather_words(scoped, "sound")`)
-- and a steady sound in a room it fills evenly (a clock, a generator in a
small room) has no percept either (`sound_shape` speaks only for an uneven
room). Neither can be told to start, to fade, or to stop until it is one;
registered, with the proposed shape (§ 13.7).

### 13.5 Your own name catches your ear

**The world.** One's own name is detected at lower signal levels than other
words, out of a din or a conversation one is not following -- the
cocktail-party effect (Moray 1959; Wood & Cowan 1995).

**As built.**

* `composer.own_name_forms`: the names others call a body by -- the card's
  name, the name without a leading article ("The Doctor" is called
  "Doctor"), each word of it substantial enough to be called alone
  (`self_name_forms`), and the card's aliases; never a uid, a
  `character:<id>` or an engine-coined descriptor, never a Latin form under
  three letters. `perception._own_name_forms` reads them off the cards, once
  a turn.
* `own_name_said`: the name-learning reader's own match (`commit_common.
  _form_in`): a name boundary in whatever script (so 「ヒナミさん」 holds
  「ヒナミ」), case-sensitive for a name that is also an ordinary word.
* `speech_percept(name_forms=)`: where the listener has the line only in
  pieces (`fragment`) or as a voice alone (the voice rung, § 12.2), and it
  holds their own name, the percept carries `own_name` -- "You catch your
  name in it." / 「その中に、自分の名前が聞こえた。」, and in memory "I caught
  my name in it." It says THAT the name was said, never which form, never
  who said it, never another word: the voice rung still carries no words and
  the fragment keeps exactly the pieces it had. A voice that does not reach
  the listener carries no name either.
* One voice a beat (`_names_kept`): voice-only lines of one speaker share a
  sentence, and a name caught in a later one is kept on it.

### 13.6 Measured

Offline, no model call and no network (every socket refused), through the
engine's own readers, on the owner's `engine.db` read `mode=ro` and copies
of the four 2026-09-26 stories (deleted after). Scripts in the lane
directory: `regrade_b1.py` (wave A's `regrade_a.py` plus each line's
listener's ear stamps and own name), `compare_b1.py`, `measure_sleep.py`,
`measure_blast.py`, `measure_habituation.py`, `scan_listener_state.py`.

* **Every recorded line, re-graded: 2,408 of 2,408 decisions identical** in
  every field (word, word if addressed, voice). No recorded relation carries
  an ear stamp: of the 42 ear contacts in 4,505 checkpoints, one covers both
  ears (chat 44 turn 94, Lilaeve's hands pressed over Hinami's ears while she
  slept), and no recorded listener held a running thing.
* **Your own name: 305 recorded decisions are of a line holding the
  listener's own name; the rescue fires on 4 (2 beats).** 287 were heard
  whole and 16 not at all, voice included. Chat 137 turn 49, from inside
  Mirelle, "M-mirelle it tingles in here." reaches her through her own mass
  in pieces -- now she catches her name; the opera story's turn 9,
  "Then supper it is. Isolde -- your arm." two rooms off reaches Isolde as a
  voice alone -- now she catches her name.
* **Sleep: 128 beats began with a body under** (116 unconscious, 12
  asleep). **Woken by sound: 1** -- chat 40 turn 11, "Good morning,
  Hinami." muttered at the nest's side; the player's own input that beat was
  "You eventually wake when morning comes". **Kept asleep: 11** -- Tamamo's
  muttered "Slept well?" (40 t10); Lilaeve's normal-voice lines in the bath
  (44 t93, t95), spoken within reach -- 60 dB at the ear, the waking level --
  and kept from waking her only by Lilaeve's own hands pressed over her ears
  (20 dB): a soothing voice the encoder wrote `normal` at arm's reach is the
  edge question 1 is about; Mirelle's line to Hinami asleep inside her (101,
  102, 112, 113 t70: a voice through a body's mass wakes by name only); four
  beats with no line (t81). No unconscious body woken.
  **The residue's intrusion: 4 beats lose it, 0 gain it** -- all four were
  the sleeper's OWN cry (chats 23 and 27, the unconscious player's "AaUaa!"
  and "WAAAAAAAA").
* **Blast: 2 beats past `BLAST_DB`**, both the Site-17 elevator crash (chats
  160 and 161 turn 11: "a tremendous crashing impact of metal crumpling and
  concrete fracturing", `catastrophic`; "a bone-jarring crash as the car
  impacts the concrete floor", `thunderous`): Hinami and Sarah Moon in the
  car at 128-138 dB at the ear, shifts of 28-38 dB, 23-33 dB left by the
  last recorded beat. Of the 26 recorded lines to them afterwards, 2 change:
  Hinami's normal line to Sarah Moon the beat after (160 t12, shift 38) now
  arrives in pieces, and Sarah Moon's whisper to Hinami nine beats on (161
  t20, shift 25) is lost. Both minds would be told their ears ring. "A sound
  like a gunshot echoing through the vertical shaft" in the same beat is
  written `loud` (72 dB at its cell on the impact ladder) and dulls nobody.
* **Habituation, on 9,315 stored views (onset and outcome): 37 character
  views re-told an unchanged steady sound** (chat 122's character 58 on
  turns 1-9, among them) -- now faded; 39 player views already dropped
  theirs; **3 sound stops a character's ledger held were never told** -- now
  told once.

What changes for the worse, read as fiction: a character mind that has
habituated holds no record of the steady sound past the beat it began (a
soundscape is not filed into memory) -- its source is still seen; a raised
voice, a slammed door or an argument in a sleeper's room now wakes them,
which the corpus never asked of a story; a whisper beside a body running a
machine in its own hands is lost (`tests/test_sound_field.py`'s
`test_the_listener_hears_their_own_running_machine_first`, overturned in
part, says so).

### 13.7 The owner's questions, and what is left

1. **Waking at 60 dB(A) at the ear, 10 out of the room.** At 55 a normal
   voice two paces off wakes a sleeper; at 65 a raised voice across the room
   does not. At 60 a normal voice at arm's reach does -- a body talking a
   sleeper down in an ordinary voice, as chat 44's bath did, wakes them
   unless the line is written as the hush it is.
2. **A name wakes at any level its words carry** -- a muttered "Good
   morning, Hinami" wakes her (chat 40 t11); a whispered name at arm's reach
   would too.
3. **Only sleep is woken by sound.** A lightly sedated body responds to voice
   in the world (the RASS scale's -1 to -3); `sedated` is one rung here, and
   it is not woken.
4. **A voice through a body's mass wakes by name only** (chats 101-113 t70).
5. **The waking beat tells only what woke them**; the rest of the beat --
   even what followed the waking sound -- is not perceived. An ordered
   reading (the beat's moments, `_sound_moments`) would give them the
   remainder.
6. **The listener's own speech is not self-masking**: no typed overlap. A
   typed `over` on a line (an interruption, two people shouting at once) is
   the shape that would let it be.
7. **Garments over the ears are not read**: an `ears` zone on the attire
   ledger's `head` region (`VISIBLE_ZONES`, `covered_zones`) is the typed
   fact a hood, a helmet or earmuffs would need.
8. **Own noise is a held running thing at a din** (`DIN_DB` 57): a tap a body
   operates, a one-beat hammer blow and chewing are not read.
9. **Covering takes 20 dB on the surface, 27 in the canal, and needs both
   ears**; one covering part covers one ear at most.
10. **The blast**: `BLAST_DB` 120; a shift of 20 at it, a decibel a decibel,
    to 40; held two minutes, gone at sixteen hours; ringing from 10. The
    impact ladder's `deafening` is 80 dB at its cell (§ 11.9's table), so a
    gunshot written `deafening` dulls nobody -- the ladder's recalibration
    (`docs/UNBUILT.md`) is what would let a close gunshot ring an ear.
11. **The ear's own threshold, 25 dB(A).**
12. **Characters habituate to a steady sound** -- the one place this wave
    departs from the character tier's "a stateless mind is re-told
    everything" -- and a soundscape is still filed into no memory, start or
    stop. Whether a sound's starting and stopping should be remembered is the
    owner's (memory is the priority).
13. **"The rain has stopped" is not built**: a hearing percept for the
    weather's sound -- told when it starts and changes, faded between, its
    stopping told once by what the observer's ledger held -- keyed like the
    soundscape, with the narrator's manifest entry carrying its verdict; and
    an even room's steady source (a clock) given a percept of its own.
14. **The own-name rescue says "your name"**, never the form spoken; a name
    the fragment keeps by chance still trips the self-narration tripwire,
    which does not read a fragment's pieces as quoted speech
    (`UNBUILT_PERCEPTION.md` § 1.159, "a composer symptom the fragment
    exposed").
15. **The encoder's waking clause** ("WAKING IS YOURS ... a noise reaches
    them", `conditions__awareness.txt`, en + ja) is unchanged: the model may
    still wake a sleeper on a noise the hearing rule says did not reach them,
    and the engine now wakes one a noise did. Whether the card should leave
    noise to the engine is the owner's; no prompt text was touched.

What is left is registered in `docs/UNBUILT_PERCEPTION.md` § 2.36 (wave B1's
paragraph), and the defect found on the way -- the commit's sleeper set for
stamina is always empty -- in `docs/UNBUILT_WORLD.md` § 1.218.

## 14. Wave B2: how sound travels (2026-10-20)

The owner, on the list of what hearing still lacked against reality: "I
guess go ahead", and before it, "the system is failing to meet several real
world principles". Wave B1 (§ 13) took the LISTENER's state; this wave takes
the way between the source and the ear. Four concepts, each a class in the
engine's own vocabulary with its real-world basis beside its constant, each
verified against what existed first and built failing-first
(`tests/test_which_way_the_speaker_faces.py`,
`tests/test_the_wind_carries_and_swallows_sound.py`,
`tests/test_sound_arrives_after_what_made_it.py`,
`tests/test_loud_sound_is_felt.py`; every one of their twenty tests fails
with its fix taken back).

### 14.1 Which way the speaker faces

**The world.** A voice is directional. The mouth radiates forward and the
head shades what goes behind it: round talkers at a metre the overall level
directly behind is some 6-8 dB under the level in front, 4-6 dB at the rear
diagonals; the 2-4 kHz band the consonants carry the words in falls most,
10-15 dB behind, while the vowels and the tune below 1 kHz lose 2-4 (Chu &
Warnock 2002; Monson, Hunter & Story 2012).

**Verified first.** The engine reads facing for hearing only from the
LISTENER's side: `entity_arc` (an act behind you is heard, not seen) and
`sound_bearing` (which way a sound comes from). Nothing read the SPEAKER's
facing. The record exists: `orientation.facing`, written at commit by
`spatial_frames.infer_facing`, and `effective_facing`, which derives a
facing from the focus between commits -- 11,501 body-facings across the
owner's 4,470 checkpoint scenes (a third of placed bodies).

**The class.** A listener in the speaker's rear arc (behind and the two rear
diagonals, `spatial_geometry._REAR_SECTORS`) gets the voice's DIRECT sound
lower: its words by `FACING_AWAY_WORDS_DB` 8 (the consonant band's loss over
that arc), its low half -- what the tone rung carries -- by
`FACING_AWAY_VOICE_DB` 3. Never within conversational reach: the one at the
speaker's shoulder hears a turned head whole. And only for a BYSTANDER
(§ 14.8): the facing on the record is where the speaker ends the beat, and a
speaker turns to the one they talk to, so a line's addressee -- and a
listener nobody can say it was for -- is graded as faced
(`spatial_senses._facing_its_addressee`).

**Where it bites, and where the physics says it cannot.** § 11's table is
used because its entries sit far from either threshold; facing moves a line
only where its budget is the direct sound and marginal:

| path | budget | facing |
|---|---|---|
| under the open sky (`open_air_loss_db`), and across an opening between two places under it (§ 14.2) | direct sound, 6 dB a doubling | words 8, voice 3 |
| rooms away from a speaker standing under the sky (`far_loss_db`) | the direct sound leaves by the way toward the listener | words 8, voice 3 |
| a bystander in a din (§ 12.1, `_din_voice_db`) | direct sound: the ring is under the din | words 8, voice 3 |
| across an enclosed room, through an opening, to a shut door nobody stands at, rooms away from an enclosed room, a wall | the room's RING carries the voice | none |

The brief named "through a door with nobody at it". It is not built, and
the reason is the physics the table is written against: with nobody at a
shut door the voice reaches it as the room's reverberant field
(`VOICE_ROOM_DROP_DB`, the budget's -6), and the ring is set by the voice's
total power, not its direction -- it faces nowhere. A speaker standing AT
the door facing away still clears it (60 - 8 - 25 = 27 dB at a quiet
room's 27, the 0 dB the table's "full" stands on). The one door case where
facing would matter -- a speaker within a metre or so of a door, facing it,
whose direct sound outruns the ring -- RAISES a line, and the table never
claimed that budget.

**As built.** `spatial_sound_field.stamp_sound_relation` stamps
`speaker_turned_away` (`_speaker_turned_away`) only where a budget reads the
direct sound and the record gives the speaker a facing: the bearing from
speaker to listener is the observer's own composite field for one room or a
neighbour (`bearing_between` of the two cells), else the site plan, else
the far field's first hop out of the speaker's room (`_first_hop`, a flood
from the listener's room). `facing_loss_db(rel, part)` is read by
`_hear_level`'s open-air, opening-under-the-sky and rooms-away rows,
`_voice_path_loss_db`'s two direct paths (the masking budget),
`_din_voice_db` and `voice_margin_db`. `hearing_reason` says
`speaker_turned_away` for a line that would have been whole facing the
listener.

| an ordinary voice, open ground | in front | behind |
|---|---|---|
| 2 paces | full | full (within conversational reach) |
| 40 paces (30 m) | full (+1 dB) | fragment (-7) |
| 90 paces, raised | full (+3.9) | fragment (-4.1) |
| 94 paces, normal | fragment (-6.5); voice -6.5 | none; voice still carries (-9.5) |
| a busy tavern (a few dozen), a raised voice 4 paces off, to a bystander | full (+4.7) | fragment (-3.3) |

### 14.2 The wind

**The world.** Outdoors the wind does two things to sound. Wind at the ear is
itself noise -- the turbulence the moving air makes round the head and the
outer ear, roughly 50-70 dB(A) in a strong wind. And wind bends a sound's
reach: it blows faster a few metres up than at the ground, so a sound going
WITH it is bent back down and carried a few decibels further, and one going
AGAINST it is bent up into a shadow near the ground that swallows it --
10-20 dB at long range once the path passes the shadow's edge, some 100-200
m out for a source and a listener a metre or two up; across the wind little
changes (Piercy, Embleton & Sutherland 1977; Embleton 1996).

**Verified first.** The weather record carries the wind's STRENGTH
(`WINDS`: still, breeze, wind, gale) and no direction anywhere in the
engine. `WIND_NOISE` priced a strong wind at 34.8 dB and a gale at 40.0,
under a quiet room's talk -- "wind you have to raise your voice over is what
wind is" was the comment that kept it there on 2026-09-05, when the run that
moved the rain levels had measured rain. Six checkpoint scenes of the
owner's 4,470 carry a `wind` or a `gale` (chats 46, 166 and 178), none a
quarter.

**The class.** Outdoors, a strong wind is a din at the ear, and the wind
bends a sound's reach by its direction. Never indoors. The owner's rain
ruling is untouched: rain is never a din, and a call across a street is
whole in any weather.

**As built.**

* WIND AT THE EAR: `WIND_NOISE_DB` = `wind` 60, `gale` 70 dB(A) (the
  powers `WIND_NOISE` are derived), added to the floor of a room the wind
  reaches (`weather_for_room`'s `wind_reaches`: under the sky or a roof open
  at its sides). Both are over `DIN_DB`, so § 12.1's rule applies as it does
  to any din: a bystander beyond conversational reach catches pieces of a
  conversation a few paces off; the people talking to each other, and a
  line spoken TO its listener at any range, are untouched. A gale is also
  the noise every sound outdoors is heard over (`level_of`), a distant
  sound's margin, a footfall's, and the room's noise word, `din`.
* THE WIND'S QUARTER: `weather.WIND_FROM_KEY` = `wind_from`, the compass
  point the wind blows FROM on the engine's own eight bearings
  (`normalize_bearing`: `w`, `west`, `NW`; an egocentric word is none).
  Absent unless a story names it, so an old record serializes exactly as it
  did and bends nothing; carried by a later record that does not restate it
  and by the drift, which walks the strength and never the quarter
  (`advance_weather`); accepted by the causal verifier's weather receipts.
  ONE CLAUSE, en + ja, is how a model learns it exists: the encoder's
  `weather` part names `wind_from` among the operational axes ("the compass
  point the wind blows from"), and `director_establish`'s weather spec adds
  it ("the quarter the wind blows FROM; omitted in still air").
* THE BEND: `wind_bend_db(scene, travel, metres)` -- the cosine of the angle
  between the sound's way and the wind's scales `WIND_DOWNWIND_DB` with the
  wind and `WIND_UPWIND_DB` against it, growing with the logarithm of the
  path from `WIND_BEND_ONSET_M` 50 m to its full size at `WIND_BEND_FULL_M`
  400 m. `stamp_sound_relation` folds it into `open_air_loss_db` (one place
  under the sky, or two joined by an opening) and into `far_loss_db` when
  both rooms are under the sky, and stamps `wind_bend_db`;
  `distant_sounds` and the near field's `SoundField.signal_at` apply it to
  sounds. `hearing_reason` says `upwind`.

| the bend, by path length | 50 m | 75 m | 100 m | 150 m | 200 m | 300 m | 400 m+ |
|---|---|---|---|---|---|---|---|
| gale, downwind | 0 | +1.0 | +1.7 | +2.6 | +3.3 | +4.3 | +5.0 |
| gale, upwind | 0 | -2.9 | -5.0 | -7.9 | -10.0 | -12.9 | -15.0 |
| gale, quartering (45 degrees) downwind | 0 | +0.7 | +1.2 | +1.9 | +2.4 | +3.1 | +3.5 |

A strong wind (`wind`) is two thirds of a gale's shadow and three fifths of
its carry; a breeze a third and a fifth.

**Found on the way: two places under the sky are one stretch of air.** The
hearing rule graded a voice between two NEIGHBOURING rooms by the opening
row -- whole at any distance, the budget of a room's ring radiating through
a doorway into the next room's ring -- even where both rooms are under the
sky. Measured: an ordinary voice 140 paces from a meadow into the pasture
through the gap in its hedge was whole, and in pieces across one field of
the same length. Where both rooms are under the sky and an opening joins
them (`_open_between`), the open air's law now runs over the field's own
path through the opening (`open_air_loss_db(..., speaker_room=)`), and the
opening row reads it (`hearing_reason`: `open_air_distance`). A barn's
doorway onto the pasture is still a room's opening.

### 14.3 Sound arrives after what made it

**The world.** Light crosses any distance a story holds at once; sound
crosses air at some 343 m/s (dry air at 20 C). A thing seen far off is seen
first and heard after: a gun's flash and then its bang, an axe across a
valley and then its chock, lightning and then its thunder, three seconds a
kilometre. Within a building the gap is a few hundredths of a second.

**Verified first.** Where do a seen source and its sound share one beat's
composition?

* THE SKY: nowhere. The `electrical` axis reached the screen -- the overlay
  draws the flash and schedules the clap 0.7-6.5 s after it
  (`static/js/weather-fx.js`, "thunder follows lightning, never leads it")
  -- and the ambience's sound bed (`weather_words`), and no mind's view at
  all: `composer.weather_percepts` said nothing of a flash or of thunder.
  No checkpoint in the owner's database holds an electrical sky.
* THE FAR LAYERS: never. `distant_sounds` gives a bearing and a character
  and never a source; `landscape` and `vistas` give places and never events.
* THE NEAR FIELD: one beat's sound events and its seen acts meet in the
  outcome pass's composition for bodies in one room or a neighbour the
  observer's composite places -- at most two rooms' extents, under 150 m.
  The sound events were minted with no place among the beat's events.

**The class.** Where a view holds the sight of a thing and the sound it made,
and the thing stands past the distance at which the gap reads as a beat,
the sight is told first and the sound after it. An order within one beat,
never a new beat.

**As built.**

* `SPEED_OF_SOUND_M_S` 343; `SOUND_AFTER_SIGHT_S` 0.3 -- the eye and the
  ear bind a sight and a sound into one event across roughly a tenth to a
  fifth of a second, and a third of a second is past that with room to
  spare -- so `SOUND_AFTER_SIGHT_M` = 102.9 m; from `SOUND_SECONDS_AFTER_S`
  1.5 s (about half a kilometre) the sound comes "seconds" after rather than
  "a moment" (`sound_after_sight`, `SOUND_AFTER_WORDS`).
* THE SKY: `composer._storm_percepts`. The flash is seen where the sky's
  weather is in view (`weather_visible`); the thunder is heard where
  `weather.thunder_heard` says it reaches -- one definition, which the sound
  bed's `weather_words` now reads too. A body with both is told them in
  order, "Lightning flickers across the storm sky. Its thunder follows each
  flash, seconds later.": lightning comes down from a cloud base a kilometre
  or two up (`LIGHTNING_M` 1500), so the gap is always seconds. Indoors, the
  thunder alone, muffled as the rain is. Standing: said when the storm
  begins and when what this body has of it changes. Both packs.
* THE BEAT: `perception._sounds_after_sight` names the beat's sounds whose
  maker -- a body the scene places, named as the event's `source` -- the
  observer sees past the threshold (`seen_source_metres`: the straight line
  between measured cells on the observer's composite, or on the site plan;
  an unplaced body is never guessed). The outcome pass holds each back and
  tells it right after the last act of its maker the observer saw that
  beat, saying it came after ("A flat crack of musket fire — the sound
  reaches you a moment after the sight of it."); a maker seen doing nothing
  keeps it where it was. `ambient_percepts(after=)` and the packs'
  `sound_after_sight_*` say it.

Found and registered, not built: the outcome pass mints a beat's own sound
events with no order key, so a near sound lands lowercase in the view's
background half ("... You see a person of unremarkable appearance. a flat
crack of musket fire.") although `ambient_percepts`' own note says a beat's
sound is not standing state; the establish pass keys them, the outcome pass
does not (`docs/UNBUILT_PERCEPTION.md` § 2.36).

### 14.4 Loud sound is felt

**The world.** A very loud low-frequency sound and a heavy impact are felt as
well as heard -- through the floor or the ground a body stands, sits or lies
on, and in the chest: an explosion, a falling beam, a big drum, machinery a
voice cannot be raised over. Often before the sound and beyond it: the
structure carries a blow where the air between rooms has lost it, and a
body that cannot hear feels it all the same.

**Verified first.** Nothing in the engine carried it. The touch channel held
the weather on the skin, contacts and a body's own state; a sound event was
hearing alone, so chat 160 turn 11's elevator car striking the concrete at
the foot of its shaft (`catastrophic`) reached its riders and the floors
above it as a noise, or as nothing.

**The class.** An impact or an emission past a felt threshold reaches nearby
bodies as touch through what they stand on, graded by distance and by the
storeys between. Deterministic from typed data -- the beat's sound events on
the impact ladder (`EVENT_DB`, or an authored `db`), a running thing or a
place's own sound at `deafening` and above, the site plan's storeys -- and
naming no source and no direction.

**As built** (`spatial_sound_field.felt_vibrations`, `felt_word`,
`felt_through_ground`; `composer.felt_percepts`;
`perception._felt_percepts_for` in all three passes):

* `FELT_DB` 100 dB(A), the level a source holds a pace from where it is
  made: the floor of the `deafening` class. Airborne low-frequency sound
  begins to be felt in the body about 100-110 dB, and an impact heavy
  enough to shake a floor -- a dropped load, a heavy door slammed, a beam
  coming down -- is 90-110 dB(A) a metre off. A household thing never
  reaches it, nor a voice (a shout is 82).
* `FELT_SPREAD_DB_PER_DOUBLING` 3: the waves that carry a blow through a
  floor slab or along the ground spread over a surface (amplitude as one
  over the square root of the distance), where airborne sound loses 6.
  Material damping is not counted.
* `FELT_STOREY_DB` 3 a storey: a floor is the medium, not a barrier
  (building-vibration practice takes some 1-3 dB a floor; airborne sound
  loses 50 through the same floor).
* `FELT_LEVELS` tremor | shudder | jolt, ten decibels a rung
  (`FELT_SHUDDER_DB` 10, `FELT_JOLT_DB` 20): the steps vibration perception
  is graded by -- barely, distinctly, strongly perceptible.
* the distance is the straight line on one room's cells or the site plan,
  else the structure's chain of rooms (`_structure_paces`: any declared
  way, a wall included, half-spans a hop); a body off the ground (a flier)
  feels nothing through a floor it is not on.
* `composer.felt_percepts`: one blow (the beat's hardest) and one steady
  trembling at most, on the touch channel, through the floor or -- under
  the open sky with no floor of its own -- the ground, in the story's
  language ("The floor jolts hard beneath you." / 「足元の床が激しく揺れる。」).
  A blow's key carries the beat, so it is news each time; a trembling is
  standing. NOT GATED BY ANY SENSE CARD: a deaf body feels it (the act
  pass test: a powder magazine through a wall, a deaf guard).

| reach on one storey | tremor from | shudder from | jolt from |
|---|---|---|---|
| a `deafening` machine (100 a pace) | 1 pace | -- | -- |
| a `thunderous` blow (120) | 100 paces (75 m) | 10 paces | 1 pace |
| a `catastrophic` blow (140) | 10,000 paces (7.7 km) | 1,000 paces | 100 paces |

An ordinary crash -- the impact ladder's own `deafening`, 80 at its cell --
is heard and felt by nobody: the ladder's 43 dB gap to `thunderous` is the
impact recalibration `docs/UNBUILT.md` already registers.

### 14.5 Measured

Offline, no model call and no network (every socket refused), through the
engine's own readers, on the owner's `engine.db` read `mode=ro` and copies of
the four 2026-09-26 stories (opera, harbour, fort, schoolhouse; copies deleted
after). Scripts in the wave's lane directory: `regrade_b2.py` (wave A's
`regrade_a.py`, recording the facing, wind and open-air stamps too),
`compare_b2.py`, `b2_survey.py` (felt, after-sight and the wind per beat),
`seen_far.py`.

* **As merged (§ 14.8): every recorded line arrives exactly as before the
  wave -- 2,408 of 2,408 identical in word, none raised, none lowered.** The
  eight lines below came back whole: none of them names its addressee, and
  a line that names nobody has no bystander. What follows is the lane's own
  measurement, before that correction.
* **Every recorded line, re-graded (2,408 decisions, 2,296 distinct beats):
  2,400 identical in word, reason and voice; 8 lowered, full to fragment;
  none raised.** The owner's 1,782 lines in chats 118-178 are all identical,
  chats 175-178's 153 included. All eight are the harbour story's:
  * SEVEN BY FACING, turns 1-3: Wren at the end of the harbour wall, facing
    the sea with her focus on Jonah beside her, and Aldo at the bollards on
    the quay, 18-19 paces (14 m) apart across the open way between quay and
    wall; their exchange about the skiff and the tide names no addressee.
    The open air's budget, read across that opening now (§ 14.2), gives +6
    to +7 dB with the speaker facing the listener and -1 to -2 with their
    back to them: pieces. Right by the physics -- on a quiet 30 dB floor; a
    working harbour is louder and would cost more -- and borderline as
    fiction: the beat wrote an exchange, and the page could now have one of
    them half-hear the other (§ 14.7, question 2).
  * ONE BY THE WIND, turn 19, in a gale: Wren raises her voice at Jonah
    beside her, and Aldo, sixteen paces up the wall and watching her, now
    catches pieces of it (-11 dB with her face in view; `din_bystander`).
    Right as fiction.
  On the distinct lines the stamps fall `speaker_turned_away` 57 times (7
  changed), the open air across an opening 53 (none changed by it alone),
  and a new din from the wind 11 (1 changed).
* **The wind**: 9 body-beats stand in a wind or a gale -- the harbour's gale
  (turns 18-19: Jonah, Wren, Aldo) and the fort story's yard in a strong
  wind (turns 5, 7, 9) -- and the noise at their ear goes from 36.5-40.4 dB
  to 60 and 70, a din. No body lost a distant sound to it. No record anywhere
  names the wind's quarter, so the bend moves nothing until a model writes
  `wind_from`.
* **After sight**: 233 placed pairs in which an observer saw the maker of one
  of its beat's sounds; the farthest stood 12 m off (the opera story, turn
  2). None is past the 103 m threshold, and no checkpoint holds an
  electrical sky: the rule changes nothing recorded. The end-to-end test is
  its evidence (a musket across two fields, 112 m).
* **Felt**: of 4,345 beats with a checkpoint after them, the felt percept
  reaches a body on 6 body-beats, and they are exactly the elevator crash:
  chat 160 turns 11 and 13, Hinami and Sarah Moon riding the car, "The
  floor jolts hard beneath you." (27.5 and 24.3 dB over the threshold, the
  `catastrophic` impact at the shaft's foot); chat 161 turn 11, the same
  riders, a shudder (that replay wrote the impact `thunderous`, in the car
  itself). Site-17's `deafening` klaxon trembles only the things fixed at
  it -- no body stood within a pace of it. Nothing else in the corpus is
  loud enough to be felt.
* **Nothing else moved**: the voice rung, the reasons and every other
  decision are byte-identical; the wave's own and the touched suites pass.

### 14.6 Guards and clauses

No new guard. Every rule here only subtracts or reorders what a body already
had a channel to -- facing and the wind lower a voice's budget, the delay
reorders two percepts the observer already had, and the felt percept names
no source, no direction and no word -- except the felt percept and the
thunder, which are NEW content: both are public physical facts (the floor
moved; the sky flashed) delivered on their own channel, never the sound's
detail, and the thunder only where `weather.thunder_heard` already let the
ambience play it.

ONE CLAUSE, en + ja: the weather's `wind_from` axis, in the encoder's
`weather` part and in `director_establish`'s weather spec (§ 14.2). Its
effect needs a live run.

### 14.7 The owner's questions, and what is left

Each a constant or a reading this wave had to take, and the owner's:

1. **The facing losses, words 8 / voice 3 dB** over the rear arc: the
   consonant band's loss averaged over 135-225 degrees, and the low half's.
   At 6 (the overall level behind a talker) the harbour story's seven lines
   would stay whole. Moot for the corpus since § 14.8: those seven name no
   addressee and are whole again at 8.
2. **Facing is the record at the end of the beat.** A speaker talking to
   someone mostly turns to them; the record says where their focus was
   left. Should a line spoken TO a listener be graded as faced toward them
   (none in the corpus: the harbour lines name no addressee)? **Built as
   yes** in the merge (§ 14.8), under the owner's standing lean where
   hearing is borderline (toward the voice carrying, 2026-09-26) -- and for
   a line naming nobody as well. The owner's to reverse.
3. **The door with nobody at it is not built** (§ 14.1): the ring that
   carries a voice to a far door faces nowhere.
4. **Wind at the ear: `wind` 60, `gale` 70 dB(A)**; a breeze adds nothing.
5. **A din spares an addressee at any range** (§ 12.1's rule). Under the
   open sky in a gale an addressee a hundred metres off follows a raised
   voice against the quiet floor. Should the wind -- or any din -- reach a
   line spoken to someone beyond conversational reach?
6. **The bend's sizes**: upwind 5 / 10 / 15 dB and downwind 1 / 3 / 5 by
   breeze, wind and gale, from 50 m to full at 400 m.
7. **`wind_from` is written by a model** (one clause, en + ja): the opening
   names it with the weather, the encoder when the prose changes the sky.
   Whether the drift should ever veer it. Its effect needs a live run.
8. **Two places under the sky across an opening are one stretch of air.** A
   voice leaving a BUILDING through an open door into the open air is still
   charged nothing for the open air it spreads into (§ 11.8 question 9).
9. **The after-sight threshold, 0.3 s (103 m)**; lightning's thunder always
   "seconds later" (`LIGHTNING_M` 1500); thunder heard indoors only where
   the rain is, the sound bed's existing rule -- a dry storm is silent
   indoors.
10. **The felt numbers**: `FELT_DB` 100 a pace from the source, 3 dB a
    doubling, 3 a storey, 10 dB a rung. A `deafening` siren on a wall
    trembles the floor at it exactly as a machine standing on it does -- the
    class cannot tell them apart -- and the impact ladder's 43 dB gap
    between `deafening` (80) and `thunderous` (123) means no ordinary crash
    is ever felt.
11. **The storm in every stormy view**: the flash and its thunder are
    standing percepts, said when the storm begins and when what a body has
    of it changes.

What is left is registered in `docs/UNBUILT_PERCEPTION.md` § 2.36 (the
outcome pass's keyless beat sounds, the act pass's order, a maker matched by
its name, the felt coupling and damping, the sky's thunder felt, the heard
thud through a floor, the head turned against the body, the near field's
unbent noise) and `docs/UNBUILT_WORLD.md` (the weather drift drops the moon).

### 14.8 Merged: whom a line is spoken to (main session, 2026-10-20)

Two corrections, made when the wave was merged into the main checkout.

**The head's shadow falls on a bystander only.** The lane graded a turned
head against everyone behind the speaker beyond conversational reach, the
line's own addressee included (its question 2). The facing record is where
a body ENDS the beat (`effective_facing`), not where its head turned while
it spoke, and a speaker turns to the one they talk to; so a line's
addressee is graded as faced, and so is a listener nobody can say the line
was for (`spatial_senses._facing_its_addressee`, read by `hear_level`,
`voice_carries` and `hearing_reason`). The din's own class (§ 12.1): nothing
about a speaker stops people talking TO EACH OTHER.

**A line that names nobody is not a line to somebody else.** That
correction moved none of the eight lines, and the reason was a defect in
every reader of the flag, wave A's din included. The flag is three-valued
-- True, the line names this listener; False, it names somebody else; None,
it names nobody, which § 12.1 says caps nothing -- but no reader produced
None. The addressee field is on nearly every recorded line and EMPTY on
3,678 of the owner's 11,841 (31%); `composer.line_addressed`,
`perception._line_is_to` and six other readers answered "does it name this
listener?" and read the empty field as "no", so a third of all talk made
each of its listeners a bystander. Two people trading lines that named
nobody lost each other's words to a turned head on the quay, and would have
to a din beyond two paces. Wave A's own pin held a line with NO addressee
field, which no recorded line is.

Built: the rule stated once, `spatial_senses.spoken_to(names_this,
names_anyone)`, and read by every site that grades a line for a listener --
the composer (`line_addressed`, so `line_hear_level`, `speech_percept` and
`communication_percept`), perception and the interaction round
(`_line_is_to`), the three background-presence readers, reactor widening
(`common`), a charter's public evidence (`charter_observe`), the follow
(`director_movement`), and the address gate (`commit_background.
address_reaches`, whose body is the one being spoken to: True on a flow ref,
else unknown, never a bystander). The ear rung is unchanged: it refuses an
unknown addressee exactly as it refused "somebody else".
`tests/test_a_line_to_nobody_has_no_bystander.py`: the din, the turned
head and the empty field each fail with the reading taken back.

Measured as merged: 2,408 of 2,408 recorded lines arrive as they did before
the wave.

**What it leaves, and it is the owner's.** Privacy in a din and the head's
shadow can only bite on a line that NAMES somebody else, and 31% of lines
name nobody: the harbour story's gale line (turn 19), which the prose aims
at Jonah, names nobody, so Aldo sixteen paces up the wall follows it whole.
The lever is upstream -- the encoder naming a line's addressee wherever the
prose says whom it is to -- and is a prompt clause that needs a live run
(UNBUILT_PERCEPTION § 2.36).
