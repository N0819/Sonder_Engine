# Play run, 2026-09-05: "The Lamp at Sorrow Point" (story A, vertical stack)

Status: EVIDENCE. One fresh non-explicit scenario authored through the app's
own routes on an export-built scratch database and played for TWENTY player
turns plus the opening, Gemini 3.8 flash on provider 3 for every role, under
the owner's standing grant to find gaps by play. The story is a storm night
at a lighthouse: a seven-room VERTICAL stack (cliff path, yard, kitchen,
store, stair, watch room, gallery), one carried cone light, one failing
fixture at `full` height, one loud bell, a half-deaf keeper hiding a fault,
and a player frightened of heights. It was chosen to exercise the light
field, the sound field, passages with `vertical`, room shapes, and the
firewall across a stack where almost every pair of bodies is two or three
hops apart.

Every stage's active variant of every beat was read against the others -- the
merged `state_diff`, the scene before and after, the registry, the regions
and the warnings -- before any finding was written, and where a stage's
answer was in doubt the deterministic readers were REPLAYED against the
committed scene (`light_field`, `sound_field`, `spatial_rel_between`,
`hear_level`, `sound_walk_level`, `feature_visibility`,
`composer.speech_percept`, `composer.line_hear_level`) so a finding names the
stage where the data first went wrong rather than the stage that rendered it.
Findings are `PA<n>`. F-numbers cited are from
`docs/experiments/DEBUG_RUN_2026_09_04.md` (F1-F35) and
`DEBUG_RUN_2026_09_05.md` (F36-F68).

Beats: 21 turns (opening + 20), 62-138 s each, none F1-class -- no
reasoning-only reply on any of the 211 captured calls. Turns 1-15 ran against
`writers-room` at 527ffcc3; the session was interrupted by a model usage
limit and turns 16-20 ran at 3e56c6d8, whose only engine changes are the
World Browser routes and `world/charter.py` (no pipeline stage moved).


## 1. Story and setup

Authoring, all through the app's own functions with `ENGINE_DB` on the
scratch database (`web.app.chat_new`, `persona_create`, `chat_edit`,
`char_create`, `chat_add_char(already_known=True, already_known_cast=True)`),
the recipe `DEBUG_RUN_2026_09_05.md` § Method records:

* **Persona** Wren Calloway, the relief keeper: practical, exact about oil and
  wicks, frightened of heights and hiding it from the Board.
* **Cast** Ivo Marrick, keeper of thirty-one years, every psychology field
  filled -- drive (`essence` "that the light must burn every night of the
  world, whatever it costs him", `expression`, `taboo` "asking anyone for help
  with the light"), four `values` phrased as trade-offs ("a bluff held over a
  fault admitted"), four weighted traits, self-model, protected beliefs, pride
  and shame triggers, coping, stress profile, three goals, three active
  concerns, and a `senses` card giving hearing `acuity: poor`, `range: short`
  with the deafness written out. `char_create` returned
  `character_card_warnings: []`.
* **Geometry, through the World Browser routes** (`PATCH /rooms/{id}`): every
  room got `extent`, `shape` (`round` for the store, watch room and gallery;
  `rectangle` elsewhere), `exposure`, `light`, anchors with `height` /
  `footprint` / `opacity` (`great_lamp` at `full` height on cell (3,3);
  `stair_foot` and `stair_riser` at `full`; the yard wall at `head`), and
  exits with `offset`. F44 recurred immediately -- the establish wrote
  `dir: "c"` on three anchors and the route refuses it, so the centre anchors
  were re-authored as `cell` pins, which the route accepts and which survived
  every merge.
* **Passages, through `PATCH /doorways/{room}/{to}`**: five doorways as ONE
  object each, with `material`, `width`, `name`, and `vertical: up` on
  store->stair and stair->watch_room.
* **Sources, through `PATCH /rooms/{id}/entities/{id}`**: the lantern
  (`light_source: lit`, `light_shape: cone`, `light_height: head`,
  `steadiness: steady`, `lit: true`), the kitchen table lamp (`all_round`,
  `waist`, `flickering`), the stove (`dim`, `waist`), the great lamp
  (`bright`, `light_height: full`, `steadiness: failing`) and the fog bell
  (`sound_source: loud`, `running: false`).
* **By hand, into the scene blob** (no route writes them, recorded as such):
  `scene.contained["wren_lantern"] = {in: "Wren Calloway", mode: "held"}` --
  the containment ledger has no World Browser route, and this is what F46 was
  about; and `scene.weather` (storm / rain / heavy / gale / freezing), which
  also has no route.
* No charter: the station has two people on it and the scenario has no town.

The opening ran clean in 26 s and produced all seven rooms with the ids the
scenario named, both bodies stationed, five entities, and three
`setting_fact` planning needs (F4's legibility class again -- they read as
"the beat reached for setting fact '...'").


## 2. Turn table

| # | player prose (<=15 words) | outcome (<=15 words) | findings |
|---|---|---|---|
| 0 | (opening) | seven rooms, both bodies, five entities, three planning needs | F4 |
| 1 | back to the rock on the dark path, whisper to self, aim the cone north | cone rendered, "You stand in the light", no warnings | works |
| 2 | into the sheltered yard, shout up at the tower | Ivo hears the shout in full, four rooms away | PA4 |
| 3 | open the cottage door, enter the dim kitchen, shut it, normal voice | door opened and closed on both edges; Ivo answers in full | PA4, PA11 |
| 4 | open the store door, cone through it, look up the dark stair | door opened; "approach is not arrival" refused the step | PA6, PA12 |
| 5 | shut the store door, listen at the wood, whisper | reply arrives as a muffled fragment -- correct | PA9, works |
| 6 | unlatch, into the dark round store, loud call up the shaft | position committed; objects/spatial channel scolded | PA13 |
| 7 | climb the narrow vertical stair, whisper to self | arrives on the stair; Ivo blocks the hatch above | works |
| 8 | up through the hatch, plain voice at his face | both stationed at `stair_hatch`, `near` each other | PA6 |
| 9 | hand him the lantern, ask about the stutter | transfer refused silently; composer tripwire fires twice | PA10, PA15 |
| 10 | open the gallery door, step into the storm, shout back in | gallery reached; declared `bright` room reads dark | PA3 |
| 11 | shut the door, ring the fog bell, speak in the ringing | bell set `running: true` -- and never stops again | PA2, PA3 |
| 12 | kneel at the hatch, look down the dark stair, whisper | in-room loud line correctly drowned to a fragment | works, PA10 |
| 13 | round the pedestal out of his sight, hand on the housing | he crosses to block; no sight gate on the full-height column | works |
| 14 | a lie, loud, to his good ear | Room's scheduled pane-crack lands as an unplaced entity | PA13 |
| 15 | offer tea, start down the iron | "approach is not arrival" refuses again | PA12 |
| 16 | descend three rooms to the kitchen, drop the kitbag | Ivo "sees" the whole descent from the watch room | **PA1** |
| 17 | blow out the lamp, shut the stove grate, stand in the dark | room goes `dark`, field goes to zero sources -- correct | works, PA8 |
| 18 | shout up four rooms from the black kitchen | shout delivered in full; replay says `fragment` | PA4, PA5 |
| 19 | (ja) relight the lamp, whisper to self | pose sentence "youはbracedleaning。", doubled 「「」」 | PA14, PA10 |
| 20 | carry the lit lamp three rooms up, quiet line at his ear | the transit leak reaches memory; the whisper is drowned | **PA1**, PA2 |

Writers' Room sessions after turns 4, 8 and 11; World Browser writes after
turns 4, 7, 8 and (creation) 7.


## 3. Findings

### PA1. An act that crosses rooms is delivered whole to an observer who had a channel only to the room it began in -- and becomes their memory
*Stage of origin: `agents/perception.py`'s act delivery (the per-beat
relation), not the composer's `act_percept`, which behaved correctly given
what it was handed. Severity: **firewall**.*

Turn 16. Wren left the watch room and walked down three rooms. Ivo, who
stayed in the watch room, received on the SIGHT channel:

> "Wren Calloway grips the cold rail and descends the spiral stair, passing
> through the store below and stepping into the kitchen. Wren Calloway
> unslings her wet canvas kitbag and drops it onto the floor beside the
> stove."

He cited it as present evidence ("Wren Calloway ... stepping into the
kitchen, dropping her canvas kitbag by the stove"). The store is two hops
away and the kitchen three, the last hop through a door, and the intervening
stair is `dark`. Turn 20 repeated it in the other direction ("lift the
burning oil lamp off the table by its wire handle ... climbs the dark spiral
stair ... emerging through the hatch").

**It reaches memory**, which is the part that lasts. Rows 69 and 77 of
`memories` on the scratch database:

> "I saw Wren Calloway grip the cold rail and descends the spiral stair,
> passing through the store below and stepping into the kitchen. I saw Wren
> Calloway unsling her wet canvas kitbag and drops it onto the floor beside
> the stove."

That is F36's class through a different door: F36 was an unearned NAME
reaching the episode; this is an unearned ROOM, and `_scrub_episode_identities`
has nothing to say about it because no identity is unearned -- only the
places are.

Mechanism: an action element carries ONE `observable` surface for the whole
beat, and the beat is graded against ONE relation. The rescue in
`_spatial_to_sources` (documented as "the SOURCE is the one whose act severed
the channel") correctly keeps Ivo's beat-start channel to Wren; what it
cannot do is stop the surface it admits from describing three rooms.

**Fix.** The class, in engine vocabulary: *a body that crosses rooms performs
one act per room it is in, and an observer is entitled to the legs that
happened where their channel stood.* Two places it can land, and the first is
better: (a) `agents/director.py`'s movement contract already knows the route
(`movement.to_room`, the travel legs the commit walks) -- emit one action
element per leg, each with its own `observable` and its own room, so
`act_percept` gates each against the observer's channel to THAT room; (b)
failing that, `composer.act_percept` truncates a surface at the first clause
that names a room the observer has no channel to -- which is prose matching,
and CLAUDE.md's objection to guards that read free prose applies. Test:
`tests/test_played_scene_classes.py`, a three-room stack, a mover who crosses
two of them, and an observer in the first -- the observer's percepts and
episode must name the room left and no other.

### PA2. A sound that happens ONCE is stored as a source that runs for ever
*Stage of origin: `director_resolve.state_diff.entities` (objects
specialist), turn 11. Severity: **story-breaking**.*

The player pulled the fog bell's cord once. The objects hand wrote
`brass_fog_bell.state = {"status": "ringing", "running": true}` beside the
authored `sound_source: loud`. Nothing ever cleared it. From turn 11 to turn
20 -- nine beats, several minutes of story time -- every view in the watch
room carried "Where you stand, the noise drowns everything", and the sound
field's noise at Ivo's cell measured 20.5 against a whisper's signal of 0.34.
The player's closing line on turn 20, spoken deliberately at the good ear of
a half-deaf man at arm's reach, was refused by the field and appears in no
view and no prose. The engine was right and the ledger was wrong.

`sound_source` is a STANDING emission, and there is no spelling for a sound
that happened. `DEBUG_RUN_2026_09_05.md`'s market turn 3 measured the
complementary half (a whistle reached nobody, "there is no `sensory_events`
channel after establish", § 2.36); this is the same gap seen from the other
side, and it is the more damaging one, because a standing source silently
rewrites every later beat.

**Fix.** Owner decision on the channel, but the rule is statable now: *a
thing that emits while it runs carries `sound_source` and `state.running`; a
thing that made a noise this beat is an EVENT of the beat and is not written
onto the thing.* Until the `sensory_events` channel exists, the cheapest
correct floor is the same one the light field already has for
`state.pointed_at`: the commit clears `state.running` on an entity whose
`running` was turned on by this beat's diff and whose kind has no continuous
draw -- no; that is a device list. Better: the objects hand's clause states
the distinction (a switch that STAYS is `running`; a stroke, a shot, a crash
is the beat's own event), and `persist/commit_scene_state` files a notice
when an entity has carried `running: true` for more than N beats with no
diff touching it. Test: a bell rung on one beat is not a noise floor on the
next.

### PA3. The declared room word is a floor in BOTH directions: a `bright` room with every source extinguished still reads bright
*Stage of origin: `world/spatial_light.room_light`. Severity:
**story-breaking**. Mirror of F40, and F41 seen from the other side.*

The great lamp is the watch room's only source. `steadiness: failing` fired
twice (turns 5 and 11) and the commit correctly wrote `state.lit: false`.
Probed on the committed scene after turn 18:

    watch_room  declared: bright   room_level: bright   sources: []

The room is lit by its declared word alone. Every view Ivo received for nine
beats opened "Hot and intensely bright from the lamp", he told the player
"she's blazing white across the whole chamber", and the Writers' Room's own
director note ("the great lamp is unlit ... he has not yet turned to see")
sat in the resolve payload against a world that would not go dark. The story
had one secret -- a failing light -- and the engine's light model could not
express it, because a room's declared word cannot be lowered by its source
going out.

F40 registered the opposite instance (a declared-`lit` room with no source
reading DARK because the sky rule may only darken). Both are the same class:
**the declared word and the sources are two accounts of one fact, and neither
is allowed to correct the other.** The consequence differs only in which
direction the lie runs.

**Fix (owner decision, with a recommendation).** An `enclosed` room whose
declared word is above `dark` and which holds no lit source is a
contradiction the engine can see: either the word yields (the room takes the
sources' answer, so putting out the only lamp darkens the room), or the
engine files a notice naming both halves the way `contradictory_sight_edges`
does. The first is what a reader expects and what makes `steadiness:
failing` mean anything at all; it is also the smaller change, because
`room_light` already computes the sources' answer. Test: a room declared
`bright` with one `bright` fixture composes `bright`; the same room with
`state.lit: false` on that fixture composes `dark`.

### PA4. The delivered clarity of a cross-room line is not reproducible from the committed scene
*Stage of origin: `agents/perception.py`'s per-beat relation for speech (the
grade is not recorded anywhere). Severity: **wrong-but-recoverable**, and it
is the reason the whole vertical-stack sound test cannot be trusted.*

On turn 18 the player shouted from the pitch-dark kitchen; Ivo, three hops
up, received it verbatim: `You hear Wren Calloway shout: "MISTER MARRICK!
YOUR LAMP IS OUT! LOOK AT YOUR OWN LAMP!"`. His reply came back in full. The
same happened on turns 2 (yard -> watch room, two hops and a closed door),
3 and 19.

Replayed on the committed scene, every deterministic reader disagrees:

    spatial_rel(Ivo, Wren)                       -> {separated, far}
    hear_level(rel, "shout")                     -> "fragment"
    sound_walk_level(kitchen, watch_room, ...)   -> "none" (any volume)
    composer.speech_percept(shout, rel, Ivo)     -> fidelity 'fragment',
                                                    "...something indistinct..."
    scene.comms                                  -> {}   (no channel to rescue it)

So the live grade is more generous than the same admission function replayed
on the same scene, and nothing persists which relation was used or why:
`act_percept` records its refusals through `note_step_decision`, and
`speech_percept` records nothing. Candidate sites, in order of likelihood:
the relation built in the perceiver loop (`spatial_rel_between` with the
beat's sound field) differing from the one a reader can rebuild; the
`open_group_continuity` compatibility floor at `composer.py:2116`, which
turns `none` into `full` for any normal/loud/shout line; and
`line_hear_level`'s addressed rescue, whose premise ("a by-name exchange
across a barrier implies a device carrying it") is false in a stone tower.

**Fix.** First make it visible, then decide: give `speech_percept` the same
`note_step_decision` record `act_percept` has (level, volume, barrier,
distance, which rescue fired), which costs one call on a path that already
has one. Then the two rescues want the owner's eye -- an addressed rescue
that promotes an unheard line to a full verbatim quotation is a comm channel
invented from a name. Test: two rooms with a closed door between and no
comms record; a normal voice naming the far body is not delivered in full.

### PA5. Noise masks a co-present voice and does not mask a voice from the next room
*Stage of origin: `world/spatial_senses.hear_level`'s edge branch. Severity:
wrong-but-recoverable. F61's class, one level up.*

Turn 18, one beat, one room: the fog bell drowns everything in the watch
room, so an ordinary voice IN the room grades to `none` (measured: signal
0.34, noise 20.5) -- and a shout from three rooms away arrives in full. The
edge model, which decides every cross-room line, has no idea there is a bell
in the listener's room; the field, which decides same-room lines, does. F61
recorded the act floor and the outcome floor disagreeing about one whisper;
this is the same defect on the axis of WHERE the speaker is.

**Fix.** `hear_level(rel, volume, ...)` already receives a relation the caller
can stamp with the listener's field. State the rule once: *a listener's noise
floor is a property of where the listener stands, not of how far the speaker
is* -- so the cross-room branch quantises against the same
`quantise_hearing(signal, noise)` the same-room branch uses, with the edge
model supplying the signal's attenuation and the field supplying the noise.
Test: a `deafening` source beside the listener drops a shout from the next
room by at least one grade.

### PA6. F60 recurs three times, and the World Browser cannot outrun it
**RESOLVED 2026-09-05.** Incoming anchors ADD; removal is the room's own
`remove_anchors` channel. The host's `PATCH /rooms/{id}` still replaces the
map whole — it writes the room record directly and its editor was shown the
whole map — so the restore this finding measured now survives the next beat.

*Stage of origin: `world/spatial_merge._merge_anchor_fields`. Severity:
wrong-but-recoverable. Registered as F60.*

A diff that writes one anchor replaces the room's whole anchor map. Turn 4
reduced the kitchen from three anchors to `store_door`; turn 7 reduced the
watch room from four to `stair_hatch`; turn 16 reduced the kitchen again to
`kitchen_stove`. I restored them through `PATCH /rooms/{id}` twice, and the
next diff that touched the room removed them again. The cost here is not
cosmetic: the anchors carry the `height` values the light and sound fields
gate on, so a room loses its shape sentences the first time a hand mentions a
door.

Nothing to add to F60's fix (incoming anchors ADD; removal is an explicit
channel) except the measurement that a host cannot work around it -- the
authored map survives exactly until the next beat that names any anchor.

### PA7. The Room can plan a room above you but cannot say how you get up to it
*Stage of origin: `story/plot_packages.OPERATION_FIELDS["plan_rooms"]`.
Severity: wrong-but-recoverable. Extends F47.*

Asked to plan the service loft above the watch room and the oil store off the
stair's midway landing, the Room published both. The loft materialised with

    service_loft.adjacent = [{"to": "watch_room", "barrier": "wall", "bearing": "up"}]

-- a room reached by "an iron rung ladder and overhead trapdoor" (its own
`access` prose) whose only edge is a WALL, so it is sealed, and the watch
room's reciprocal edge is `wall` too. The Room diagnosed this itself in
session 2 ("the opening ... was recorded with a solid wall barrier rather
than a ceiling hatch and rung ladder ... that connection will need to be
revised from a wall to an iron ladder and trapdoor") and had no tool with
which to fix it. `plan_rooms.adjacent` is `[{to, barrier?, bearing?}]`:
`bearing` has no `up`/`down` reading and `barrier` has no vertical member, so
a vertical plan edge can only be spelled as a bearing the mint discards and a
barrier the mint takes literally. F47's "the Room cannot author geometry"
(extent/shape/parts) recurred verbatim in the same session -- I asked for
extents in paces and got prose in `purpose`.

**Fix.** `plan_rooms.adjacent` takes the same `vertical: up|down` the scene
edge and the doorway route already own, and a `bearing` that normalises to a
vertical becomes `vertical` rather than a wall. Test: a planned room joined
`vertical: up` materialises with a passable edge and its reciprocal.

### PA8. Feature visibility ignores light: you can see the stove in a room that is pitch dark
*Stage of origin: `world/spatial_fov.feature_visibility`. Severity: cosmetic
to wrong-but-recoverable.*

Turn 17, after the player blew out the lamp and shut the stove grate, her own
view read:

> "You can see The cast-iron stove radiating dull warmth against the
> whitewashed stone wall. within arm's reach. The cottage door is shut. There
> is the store door. **It is dark here.**"

Probed on that scene: `effective_light(kitchen) = dark`, the light field has
zero sources and every cell `dark`, and `feature_visibility` returns
`visible: true` for all three anchors with `basis: "open"`. The list is gated
by geometry -- occlusion, arc, distance -- and not by light, so the composer
names what a body could see if there were light and then says there is none.
(The light-shape sentence does the right thing and is the reason the
contradiction is visible in one paragraph.)

**Fix.** `feature_visibility` consults the field it already has:
an anchor whose cell is `dark` is not visible, exactly as an occluded one is
not. The one case worth carving out is the anchor a body is TOUCHING, which
is knowledge from a channel that does not need light. Test: a room with no
lit source names no features and still names its doorways as doorways.

### PA9. The failing-source notice is written and then discarded inside the same commit
*Stage of origin: `persist/commit.py`'s domain order. Severity:
**story-breaking**, and it is the reason PA3 could never self-correct.*

`commit_scene_state._record_failed_sources` appends its notice to
`engine_notices` -- but it runs inside `prepare_scene_commit`, which
`persist/commit.py:434` calls BEFORE the write lock. Inside the lock the
first domain is `commit_transit_sweep` (`commit.py:467`), which at
`commit_mechanics.py:200-201` builds its own list and writes the key whole:

    notices = list(notices) + list(getattr(ctx, "engine_feedback", []) or [])
    wset(cid, "engine_notices", notices)

The failed-source notice is gone before the beat ends. Measured twice: the
great lamp failed at the commits of turns 5 and 11 (the warning is in both
step records), and the next beat's Director payload carried
`engine_notices: []` both times (traces of turns 6 and 12). The Director was
never told its light had gone out, so it never relit it, never had a
character notice, and never wrote the scene the `steadiness` design exists to
produce. `ctx.engine_feedback` items survive because the sweep concatenates
its own; anything written to the key earlier does not.

**Fix.** `commit_transit_sweep` appends rather than replaces -- read the key,
extend, write -- or, better, every notice writer goes through one
`add_engine_notice(ctx, msg)` helper that owns the read-extend-write, since
there are now four writers (`commit_scene_state` twice,
`commit_mechanics`, `commit_destruction`) and the ordering between them is
accidental. Test: a `failing` source that goes out on a beat appears in the
NEXT beat's `director_interpret` payload `engine_notices`.

### PA10. The quotation-mark class (F29/F54) recurs, and now trips the invention guard
*Stage of origin: the narrator's rendering plus the literal quote guards.
Severity: cosmetic, but it is the loudest false-positive source in the run.*

Doubled quotation marks (`""line""`) on six beats; in Japanese the narrator
wrapped 「"line"」 and then doubled the corner brackets (「「...」」). Five
"Delivered line rendered without quotation marks" and seven "Narrator
invented quoted dialogue absent from the player view" warnings fired, all
false. Two of them are new and worse than F54's: the guard fired on the
narrator's correct rendering of a MUFFLED FRAGMENT (`"...deafen... glass...
midnight..."`) and on a bare stage direction ("He tilts his chin slightly to
bring his left ear forward while holding my eyes."), because the guard sees a
quoted span it cannot match to a delivered line. The narrator is doing the
right thing and being told off for it. F54's proposal (normalise repeated
quote runs before matching) stands; add that a fragment percept's rendered
ellipsis is a delivered line and should be matched as one.

### PA11. Every character step is told it cited no delivered observation
*Stage of origin: the claims floor in the interaction loop. Severity:
wrong-but-recoverable (a warning that fires always carries no information).*

18 of the 19 beats with a character step warned "character Ivo Marrick: no
delivered present observation was cited". Reading the payloads, Ivo DID cite
them -- `appraisal.present_evidence` carries `event_id: "current:2:3"` and
`"current:2:0"` on almost every beat, matching the `observation_id`s in his
`perception.observations`. The floor is looking for citations in a field the
model does not fill (`observations_used`, `present_evidence_used`,
`memory_evidence_used` were `[]` on every single call) while the same
information sits, correctly keyed, in `appraisal.present_evidence`. Either
the floor reads the wrong field or the contract asks for the same thing
twice. A warning at 18/19 is noise that will hide the real one.

**LANDED 2026-09-05** with PE20 (flat run), which measured the same line at 45
of 116 warnings; the manor run counted it 44 times and the road run on 17 of
20 beats. Both halves were wrong at once: the guard read a lane that is no
longer requested, and it fired regardless of whether any present lane had been
asked for. It now reads the lanes the advertised schema offers and accepts a
citation from whichever lane the answer used. See the flat run's PE20 for the
before/after measurement.

### PA12. F28 recurs: "approach is not arrival" refuses a declared step into the next room
*Turns 4 and 15. Severity: wrong-but-recoverable; registered as F28.* Both
times the interpret wrote `movement {arrives: false}` for a step the player
declared as taken ("cross to the inner door and draw it open onto the store",
"I go to the hatch and start down the iron"), and the guard committed no
position. On turn 4 the story recovered because the player never needed the
store; on turn 15 the descent had to be re-declared on turn 16. F28's fix
(accept a room on a passable path toward `to_room` as the leg walked) would
have taken both.

### PA13. The objects hand mints entities with no room, twice, including the Room's scheduled event
*Turns 14 and 18. Severity: wrong-but-recoverable.* `watch_room_storm_pane`
and `box_of_matches` were both minted with no `positions` entry, and the
resolve warned correctly ("exist after this beat but are in no room, so
nothing can perceive or act on them"). The first is the Writers' Room's
scheduled pane-crack landing as an object nobody can see -- an authored event
arriving as an orphan. The warning is right and nothing acts on it; a mint
with no placement could take the acting body's room the way
`derive_minted_entity_placements` already does for a mint with contact
evidence.

### PA14. F59 recurs and widens: the Japanese pose sentence fuses English posture words
*Turn 19. Severity: wrong-but-recoverable; registered as F59.* Ivo's view in
Japanese: `youはbracedleaning。` -- the subject is `you`, and two posture
words are concatenated with no separator, where F59 recorded them merely
unspaced (`youはatthe kitchen tablethe chairの上にseated`). The light, sound,
scent and speech sentences were correctly Japanese, and the narrator's prose
was good Japanese. The room names and descriptions stay English, which is
correct (they are authored English), but that makes the mixed pose sentence
read as a bug rather than a translation gap.

### PA15. A tripwire fired: the composed view narrated its own perceiver
*Turn 9, both perception stages. Severity: firewall (caught).*
`perception_act: COMPOSER TRIPWIRE -- composed view of Ivo Marrick narrated
its own perceiver (engine defect): 'Marrick...'`. The tripwire did its job
and repaired the view; recorded here as evidence that the guard fires on live
data, with the note that the excerpt it prints ('Marrick...') is too short to
locate the sentence that caused it -- 40 characters of context would make it
actionable.

Also on turn 9, and NOT a defect: the player held the lantern out to Ivo and
the transfer did not happen. The Director realised the offer as an offer
(`claim_dispositions`: "Lantern held out toward Marrick") and Ivo refused it
in prose; `contained.wren_lantern` correctly still names Wren twenty turns
later. The player's declared conduct was the OFFER, and the engine resolved
it as one.


## 4. Works -- what behaved by the rules

* **Dousing a room's only sources goes dark, end to end** (turn 17). Both
  entities took `state.lit: false`, `rooms.kitchen.light` became `dark`, the
  light field dropped to zero sources and every cell `dark`, the view said
  "It is dark here.", and the narrator wrote "In the sudden pitch". This is
  the single cleanest chain in the run and it is the thing PA3 shows is
  impossible in the other direction.
* **Masking works where it is asked.** The bell drowned Ivo's own loud line
  in the same room to a muffled fragment on turn 12 and refused the player's
  whisper on turn 20. The physics was right; the ledger behind it (PA2) was
  not.
* **The passage as one object held for twenty beats.** Five doorways written
  through `PATCH /doorways`, with `material`, `width` and `vertical`; the
  store door went `closed_door -> open -> closed_door -> open_door` and the
  gallery door `closed_door -> open_door -> closed_door` across five beats,
  and BOTH edges plus the passage record agreed every single time. F16 and
  F22's class did not recur once.
* **Every World Browser write survived every commit.** Extents, shapes
  (`round` on three rooms), exposures, anchor heights and opacities, exit
  offsets, the `light_shape`/`light_height`/`steadiness`/`sound_source`
  fields, a thing created from the map with a `cell` (`spare_wick_tin` kept
  its cell (5,3) for thirteen beats), a doorway offset moved to 0.8, and a
  doorway `state: {latched: true}` -- all still present at turn 20. The one
  thing that did not survive is anchors, and that is PA6.
* **The carried cone.** `contained.wren_lantern = {in: Wren, mode: held}`
  survived twenty beats and every room change; the light field placed the
  source at the HOLDER's cell with `shape: 'cone'`, `height: 2.0`, `axis`
  from the holder's facing, and `holder: 'Wren Calloway'` -- F46's "a carried
  light recorded by position lights from the room's default cell" did not
  recur once the containment ledger was authored. The cone's aim followed her
  facing through six rooms.
* **The `full`-height fixture cast no shadow.** The watch room holds a
  `full`-height opaque `great_lamp` at the centre and `head`/`waist` anchors
  around it; the field is `bright` in all 32 cells with no shadowed cell,
  which is what § 4.2 of the light-field design says a `full` source must do.
* **The light-shape sentence spoke where the room was uneven and stayed
  quiet where it was even** (F52's class holding): "The light from hooded
  brass lantern leaves A bank of heavy metal drums ... and The open foot of
  the cast-iron spiral staircase. in the dark" in the round store; a flat
  sentence in the uniform kitchen. The missing article F52 noted is still
  missing ("from hooded brass lantern").
* **The sound-shape sentence named the source and the places** ("The noise
  from brass fog bell drowns everything at ... and is a din at ... Where you
  stand, the noise drowns everything.").
* **The half-deaf card reached the deterministic floor.** `sense_adjusted`
  graded a shout down one rung for Ivo's `acuity: poor` in replay
  (`fragment` -> `trace`), so the authored sense card is live -- it simply
  never mattered, because PA4's delivery was more generous than the floor.
* **Weather is ambient and scoped by exposure**: gain 1.0 on the cliff path
  and gallery, 0.8 in the sheltered yard, 0.45 in every enclosed room, with
  "muffled rain / indoors through wall / distant thunder" inside and "rain
  heavy / thunder / gale" outside, and the watch room correctly adding
  "echoing cave reverb".
* **Psychology moved for stated reasons.** Ivo's `suspicion` rose to 0.35 and
  `trust` sat at -0.2 with `last_interaction_turn` tracked; his beliefs grew
  from "Calloway has arrived at the light during the storm" (0.95) to
  "Calloway noticed the uneven revolution of the light before reaching the
  tower top" (0.8) -- an inference from the player's own question, which is
  the product, not a leak. His authored protected beliefs stayed protected.
  The interior-leak guard fired once, correctly ("spoken line voices
  unenacted intention 'ia1'").
* **`character_card_warnings` was empty** for a fully authored sheet, and the
  drive did the work it is supposed to: Ivo blocked the pedestal on eight
  separate beats without being told to.

## 5. The Writers' Room as co-author

**What it did.** Three sessions, 13-35 s each, 2-6 steps and 4-10 tool calls.
It planned two rooms beyond the frontier with `purpose`, `access`, structure
and region, published them, and they materialised as planned stubs that
reached the Director's own spatial frame by the next beat (F2's class
holding). It left two director notes that arrived VERBATIM in the resolve
payload's `author_notes` two beats later. It scheduled an event and the event
arrived as `due_authored_events` on exactly the beat requested. It recapped
the story accurately. `inspect_minds` showed the authored tier beside the
ledger (F8's fix holding) -- values, traits, protected beliefs, drive
essence, strain, stress, intentions with `idle_beats`, and a theory-of-mind
model of the player. It recorded a new mandate mid-story when I granted one.
Pushed on its own oil-store placement, it defended it with one concrete
sentence about five-gallon service founts rather than caving -- the right
behaviour for a co-author.

**What it could not do.** Author geometry: I asked, in the same sentence, for
extents in paces and shapes, and got prose in `purpose` (F47, verbatim). Say
how a body gets to a room it plans above you (PA7) -- and it could see the
resulting sealed edge and had no tool to mend it. Its tool events carry no
results (`result_head: None` on all 20 calls), so a host watching the panel
sees tool NAMES and no answers. Its calls are not captured at all
(`llm_capture` records only `agents/runtime.py`), so the one agent whose
payload design I most wanted to read is the one I could not.

**Where it overstepped -- and it is subtle.** Asked outright to write a
belief into Ivo, it refused, in exactly the right words: *"I cannot write a
belief into Ivo Marrick's head. In this world, authors place only
circumstances and what characters see, hear, or read; characters form their
own conclusions."* Two turns later, asked to note that the lamp had gone out,
it published a `director_note` reading: *"The great lamp is unlit: its wick
failed in the last minute while Ivo was facing the door to the gallery, **and
he has not yet turned to see that the light has gone out**."* The second
clause is a fact about a mind's attention, and `OPERATION_FIELDS`'
`director_note` says in its own field text: "what a placed thing is and is
for, **never how a character will take it -- a mind's conclusion is its
own**". It refused the front door and used the side one, and nothing in
`validate_package` looks at note PROSE for claims about minds. Reported, not
changed. (It also volunteered a confident reading of Ivo's inner life in
prose -- "he is desperately concealing that mechanical failure" -- which is
fine as an answer to the host and would not be fine in a note.)

**What I would improve, in order.** (1) Give `plan_rooms` `extent`, `shape`,
`parts` and `vertical` -- the Room is the only author who thinks about a
place before anyone stands in it, and it currently cannot say how big it is
or how you get up to it. (2) Return tool results in the event stream. (3)
Capture Room calls like any other role. (4) Let a session REVISE a published
plan edge it can already diagnose. (5) State the note contract's mind rule in
the note tool's own refusal path, since the model clearly knows the rule
(it quoted it) and still crossed it when the sentence was phrased as world
state.

## 6. Prompt and payload proposals, per stage

Measured over 211 captured calls; sizes are the JSON payload, excluding the
system sheet.

* **`director_interpret` (director, avg 14.5 KB payload / 26 KB system).**
  `scene` is 6.1 KB and `director_recent_messages` 3.1 KB -- 78 % of the
  payload. The interpret classifies a declaration and names a destination; it
  needs the room graph and the bodies, not every entity's `description`,
  `aliases` and `state`. *Proposal: the interpret's scene slice is rooms
  (id, name, exits, light word) and bodies; a thing appears only when the
  declaration's own words could name it.*
* **`director_spatial` (avg 12.7 KB, 10.0 s -- the slowest hand, 38 calls).**
  `rooms` alone is 8.6 KB: every room's full `desc` and `notes`, including
  the four rooms no body could reach this beat. *Proposal: the mover's room,
  its neighbours, the declared destination and the rooms holding a body --
  stated as the rule "the rooms a body could stand in by the end of this
  beat", which needs no list.*
* **`director_contact` (avg 3.3 KB payload against a 32.4 KB system sheet).**
  The worst instruction-to-work ratio in the engine: 26 calls, 172 s, and on
  most beats the correct answer was one op or none. *Proposal: this is the
  hand `reads_dialogue` already excludes from the transcript; consider the
  same treatment for its sheet -- the contact vocabulary a beat can use is
  decided by whether any body is touching anything, and the gate already
  knows (`contacts_standing`).*
* **`character:<id>` (avg 37 KB, 13.9 s).** `memory` is 19.5 KB and `self`
  16.4 KB -- 90 % -- while `perception`, the thing the beat is ABOUT, is
  3.6 KB. Every beat carried the full authored psychology, all eight beliefs,
  three intentions, the theory-of-mind model and the recent-episode list
  unchanged. *Proposal: the authored tier is stable per story and per
  character -- send it once behind the prompt cache and send the DELTA of the
  ledgers, or cap `recent_episodes` by beat distance rather than count. This
  is also where PA11 lives: the payload asks for citations in three fields
  the model never fills.*
* **`narrator` (avg 14.4 KB, 13.5 s, largest single call 21.9 KB).** The
  composed view appears THREE times in one payload: as `present_scene`, again
  verbatim inside `sensory_channels.sight.this_beat`, and a third time inside
  `current_events` as numbered items. *Proposal: `present_scene` is the
  view; `sensory_channels` carries the per-channel STANDING words and the
  `why`; `current_events` carries what changed. Say each thing once.*
* **`director_resolve` (avg 14.5 KB).** `scene` 7.5 KB + `player_declaration`
  4.5 KB + `interaction_rounds` 3.5 KB. The `player_declaration` block
  carries the full `sequence` AND the derived `action` AND
  `authority_claims`, all restating one paragraph the model already has as
  `resolved_event`.
* **Prompt text.** The resolve's barrier clause is an enumeration
  (`open|open_door|window|bars|one_way_window|membrane|closed_door|wall` with
  a gloss each) and is the RIGHT kind -- a closed set the engine owns and can
  enumerate, exactly the carve-out CLAUDE.md names. What is missing is not a
  list but a distinction: **nothing anywhere tells the objects hand that a
  sound which HAPPENS is not a source that RUNS** (PA2), and nothing tells
  the spatial hand that a plan edge going up is `vertical` rather than a wall
  (PA7). Both are one sentence stating a class.
* **Where the model misread a field.** `state` on an entity is free text and
  the hands use it as prose: `{"status": "ringing", "running": true}`,
  `{"shutter": "angled upward toward the lantern room"}`,
  `{"grate": "closed"}`. The engine reads exactly two of those keys. A field
  that accepts anything gets everything, and the useful half is
  indistinguishable from the decorative half.

## 7. Measurements

Per turn (captured calls; payload and system in characters):

| turn | calls | seconds | payload | system |
|---|---|---|---|---|
| 0 (opening) | 2 | 23.7 | 6.8 K | 58.6 K |
| 1 | 10 | 78.6 | 69 K | 279 K |
| 2 | 10 | 83.3 | 91 K | 286 K |
| 3 | 11 | 84.3 | 135 K | 329 K |
| 4 | 10 | 77.1 | 106 K | 308 K |
| 5 | 8 | 62.9 | 99 K | 286 K |
| 6 | 13 | 132.4 | 149 K | 405 K |
| 7 | 11 | 90.9 | 113 K | 341 K |
| 8 | 8 | 65.1 | 115 K | 263 K |
| 9 | 10 | 73.7 | 146 K | 327 K |
| 10 | 13 | 108.1 | 169 K | 383 K |
| 11 | 12 | 148.4 | 166 K | 373 K |
| 12 | 11 | 88.7 | 154 K | 311 K |
| 13 | 11 | 84.3 | 146 K | 352 K |
| 14 | 11 | 83.1 | 154 K | 335 K |
| 15 | 10 | 73.1 | 141 K | 301 K |
| 16 | 12 | 112.9 | 152 K | 363 K |
| 17 | 9 | 104.6 | 102 K | 276 K |
| 18 | 10 | 98.5 | 147 K | 340 K |
| 19 (ja) | 8 | 85.7 | 156 K | 135 K |
| 20 | 11 | 90.4 | 167 K | 341 K |

Per role, all 211 calls:

| role | calls | total s | avg s | avg payload | avg system |
|---|---|---|---|---|---|
| director | 65 | 470.0 | 7.2 | 14.5 K | 26.0 K |
| director_spatial | 38 | 378.8 | 10.0 | 12.7 K | 31.2 K |
| narrator | 21 | 284.5 | 13.5 | 14.4 K | 37.3 K |
| character_mid | 18 | 249.8 | 13.9 | 37.0 K | 50.4 K |
| director_objects | 25 | 220.0 | 8.8 | 5.8 K | 20.5 K |
| director_contact | 26 | 172.2 | 6.6 | 3.3 K | 32.4 K |
| director_body | 13 | 57.1 | 4.4 | 3.1 K | 31.6 K |
| director_social | 5 | 17.3 | 3.5 | 3.3 K | 11.5 K |

The Director's own two-pass shape costs more than any hand: 65 director calls
against 20 beats, because the interpret runs a coverage-correction call on
almost every beat (its answer was `sequence: []` -- "already_covered" -- on
most of them) and the resolve runs an omission-correction call on nine.
`director_social` ran on 5 of 21 beats and `director_body` on 13, so the
gating works; `director_contact` ran on 26 and produced one op or none on
most.

Capture: 211 `llm_capture` rows, one `trace_<turn>.json` per beat in the job
scratch directory, no F1-class retries, no failed beat. 79 memory rows
written. `tools/export_bench.py scan` was run over every file written outside
the scratch database before this document was committed: no provider key in
any file.
