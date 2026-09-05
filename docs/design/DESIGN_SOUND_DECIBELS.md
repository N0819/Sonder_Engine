# Design: decibels, and how far a very loud sound goes

**Status: DESIGN, not built (2026-09-05).** Written after the owner asked
for "a db system so that incredibly loud noises can travel very far", against
the sound field built and repaired the same day
(`world/spatial_sound_field.py`, `docs/design/DESIGN_SOUND_FIELD.md`).

## 1. What is true today, measured in the source

  * **The field is one hop wide.** `spatial_fov.room_field` lays the room and
    the neighbours placed beyond its own doorways, and nothing further
    (`_placed_neighbours`). So a sound two rooms away is not quiet: it is
    ABSENT. No constant can change that, which is why this note is mostly
    about reach and only a little about scale.
  * **A wall passes nothing.** `APERTURE_PASS["wall"] = 0.0`. Right for
    sight, which is what the table was borrowed from. It means no explosion,
    ever, is heard through a wall by anyone.
  * **Decay is inverse-square in path length**, `pass / (1 + L^2)`, and the
    ladders are linear powers: speech `mutter 0.6 | whisper 1 | normal 12 |
    loud 40 | shout 120`, sources `faint 1 | audible 12 | loud 40 |
    deafening 150`. The top of the source ladder is 12.5x a normal voice.
    A cannon, a collapsing roof, a dragon and a ship's horn have no rung.
  * **A sound that HAPPENS has no channel at all** (`docs/UNBUILT.md` s1.117):
    `running` is a state, and a bell rung once either becomes a permanent
    source or reaches nobody.

## 2. The claim

Three changes, and only the second is about decibels for its own sake.

**A. Decibels are the same curve written in logs.** Define every level as a
sound pressure level at one pace and every loss as a subtraction, with
`L_dB = 10 * log10(P_linear)`. Then today's `P * pass / (1 + L^2)` is exactly
`L0 - 10*log10(1 + L^2) + pass_dB`, and today's thresholds are exactly
`FULL 10*log10(2.0) = +3.01 dB` and `FRAGMENT 10*log10(0.8) = -0.97 dB` over
the noise. The conversion is arithmetic, not a behaviour change, and a
byte-identity test over every existing scene must prove it. What it buys is
that the dynamic range stops being unwieldy: a whisper and an artillery piece
are 100 dB apart, which is one small number, where linearly they are a factor
of ten million.

**B. A wall attenuates; it does not abolish.** This is the change that makes
the owner's sentence true. A wall gets a finite transmission loss, so a sound
loud enough gets through one and a voice never does. Everything else in the
aperture table converts exactly (`open 0 | open_door 0.46 | bars 0.46 |
membrane 3.0 | closed_door 6.0 | window 10.0` dB of loss); `wall` is the only
new number, and it is the owner's.

**C. Beyond the near field, sound travels on the ROOM graph.** The cell grid
stays exactly as it is for the room and its neighbours -- that is where the
placement, the occluders and the sentences live. Past it, a loud sound floods
the room graph by Dijkstra, minimising ACCUMULATED LOSS rather than path
length: each room crossed costs its own span (from `extent` where it is
written, else the size tier), each edge costs its barrier's loss. The flood
terminates on AUDIBILITY -- when the level falls under the quietest room's
noise floor, no further room can hear it, so there is no hop cap to choose
and none is added. A scene of ninety rooms costs one bounded Dijkstra on the
beat something loud happens, and nothing on every other beat.

## 3. What a distant sound delivers

**A bearing and a character, never a sentence.** The far field carries
EVENTS: a bang, a bell, a roar, an engine. It never carries content, because
distance takes the words first and a body two streets away who "hears" a
line is the same defect as one who sees through a wall. Concretely: the far
field can deliver `kind: sound` with a level word, a direction (the first
edge of the path, which is where a listener would turn), and whatever public
description the source carries; it may not deliver speech content at any
volume. A shout dies of the arithmetic anyway -- 88 dB against an explosion's
140 is a factor of four hundred in distance -- so this rule costs nothing a
story wants and closes the leak it would otherwise open.

## 4. The event channel (closes `docs/UNBUILT.md` s1.117)

A loud sound is usually a THING THAT HAPPENED, and the engine has no word for
one. `state_diff.sensory_events: [{kind, room, level | db, source, detail}]`,
written by the objects hand, heard where it happened by whoever was there,
and over when the beat is. It is the natural home of the same repair: the
existing clause tells a hand that an emission is a state and a noise is an
event, and then offers it nowhere to put the event. Build the two together or
the ladder has nothing to stand on.

## 5. Constants, all the owner's

| | proposed | note |
|---|---|---|
| speech, dB at one pace | mutter 28, whisper 30, normal 51, loud 56, shout 61 | exact conversion of today's ladder; nothing moves |
| sources, dB at one pace | faint 30, audible 51, loud 56, deafening 62 | the same |
| new rungs above the ladder | `thunderous` 85, `catastrophic` 100 | for a cannon, a collapse, a dragon; the vocabulary stays closed and the engine owns it |
| authored number | `db` on an entity or event | for anything the words do not reach; absent means the word decides |
| wall transmission loss | 45 dB | the one genuinely new number: a shout is inaudible through it, a `catastrophic` event is a fragment two rooms away |
| floor and ceiling loss | 50 dB | a vertical passage's barrier already has its own |
| ambient, dB | enclosed 14, sheltered 17, open 20 | exact conversion of `AMBIENT` |
| far-field entry | any source over 70 dB | below it the near field is the whole answer |

## 6. What argues against it

  * **A finite wall makes everything slightly audible everywhere.** The
    threshold and the wall loss are what keep that from being true, and they
    are the two numbers most worth a play test.
  * **Room distances are crude until extents are written.** The far field
    measures a room by its `extent` and falls back to the size tier, and 0 of
    589 rooms carried an extent when this was measured. That is the same
    dependency the geometry work has, and the Room cannot author one (F47).
  * **Free-field spreading indoors is wrong in the flattering direction.** A
    real corridor carries further than the inverse square says; the model
    will under-report reach in exactly the place stories care about. Kept
    because the alternative is a reverberation model nobody asked for.
  * **A distant event is a strong narrative hook**, and the composer will
    have to be disciplined about not making every beat about a noise three
    streets away.
