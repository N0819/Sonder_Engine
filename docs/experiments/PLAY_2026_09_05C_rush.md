# Play run, 2026-09-05C: "Rushlight" — twenty turns with the clock as the antagonist

Status: EVIDENCE. Play agent R of the campaign-3 five. One fresh story on an
export-built scratch database (`tools/export_bench.py prepare --src engine.db
--chats 115`, 4.7 MB, capture ON with full bodies), Gemini 3.8 flash on
provider 3 for every role, **twenty player turns plus the opening**, four
Writers' Room sessions, 242 captured calls, 2,543 s of model time.

**The geometry is the engine's, not mine.** Per the mid-run correction, I
authored only what a player authors: a persona, two cast cards, a style guide
and a scenario in prose. `director_establish` built the whole tenement from
that paragraph. **No room, edge, anchor, light source, sound source or extent
in this run was written by hand.** The one host intervention is named below.

Findings are `PR1`–`PR18`. F-numbers cite
`docs/experiments/DEBUG_RUN_2026_09_05.md` / `_09_04.md`; P-letters cite the
campaign-2 play reports.

**Provider conditions.** The owner's OpenRouter account hit its in-flight
credit ceiling between roughly 12:45 and 13:15, which is harness noise and is
filed as no bug. It cost three Room sessions and touched five beats: turn 8
(three specialists failed open), turn 9 (resolve failed, resumed), turn 10
(four resume attempts), turns 12/14 (slow). **What the engine did with the
partial results was correct and is worth keeping** — see PR17. Read the
per-beat seconds in the measurements table against that window; turns 12–14
in particular carry retry latency that is not the engine's.

`export_bench.py scan` was run over this file and every file the run wrote
outside the scratch database: clean, no provider key.


## Story and setup

**Scenario (prose only, no room ids, no field names).** Three in the morning on
Rusa Street; number 14 is a four-storey brick tenement over a bakery; the
bakery has caught and the fire is in the stairwell. Vesna Kolar, a night nurse
just off shift, is on the ground-floor landing. Above her: Mirela Anđelić on
the second floor, who will not leave without her box, and Tomo Lisak, nine, on
the fourth, who has hidden and will not answer. There is a roof.

**Persona (`persona_create`).** Vesna Kolar, 34, trauma nurse; `initial_outfit`
navy wool coat, scrubs, trainers, socks, lanyard; abilities *trauma nursing
(expert)* and *smoke (poor)* — "not afraid of the flame and very afraid of the
smoke".

**Cast (two, `char_create` + `chat_add_char(already_known=True,
already_known_cast=True)`; `character_card_warnings` EMPTY for both).**
- **Mirela Anđelić**, 78. Drive *to keep faith with the dead, who cannot keep
  it for themselves* / *she settles what the dead are owed before anything of
  her own* / taboo *being carried, lifted or handled like luggage*. Values as
  trade-offs, four traits, self-model, coping, stress profile, three goals,
  `capacity: narrow`. Senses: vision `poor`/short (cataracts), hearing
  `poor`/ordinary (deaf on the left).
- **Tomo Lisak**, 9. Drive *to never be the one who caused it* / *goes small
  and silent* / taboo *answering a voice he does not know*. Three goals,
  `capacity: narrow`, `stress.activation 0.75`, coping mode `freeze`.

**Style guide.** tone urgent/plain/physical; avoid *"Rescue-by-coincidence.
Nobody is saved by luck."*; `weather_severity: harsh`; `narration_tense: past`;
`opening_hour: 3.0`.

**Everything else is the engine's.** `director_establish` minted ten rooms
(`street_outside`, `ground_landing`, `second_landing`, `flat_mirela`,
`third_landing`, `fourth_landing`, `flat_tomo`, `roof`, plus `roof_16` and
`number_16_scuttle` from the Room's plan), every edge, every anchor, both
entities and every light and sound decision. **No geometry was hand-written.**

**Host intervention, exactly one, through the app's own route and reported as
an intervention:** `PUT /api/chats/{cid}/survival {enabled: true, show_npcs:
true}` after the opening, which seeded the vitals table. (I had first called
`world.survival.set_survival_enabled` directly, which turns the setting on and
seeds nothing — a small trap worth naming: the setting alone leaves
`scene.vitals` absent and `tick_vitals` a no-op, so survival is on and
measuring nobody.) **Zero World Browser writes**: I deliberately did not repair
the world by hand, so every geometry finding below is the engine's own
output.

**Turn table** (player prose ≤ 15 words → outcome ≤ 15 words):

| # | what I did | what came back | findings |
|---|---|---|---|
| 0 | hand on the bakery door, shouted fire up the well | 10 rooms, vertical stair, no fire entity, 5 setting needs | PR6 |
| 1 | up to the second, hammered Mirela's door, shouted for Tomo | Tomo froze deeper; Mirela planted herself; **she was invisible to me** | PR5, PR8 |
| 2 | past her into the flat, prone under the bed for the tin | box found; her only line to me arrived as a fragment | PR5, PR8 |
| 3 | box against her chest, shoulder under her arm, turned her | **taboo held: refused to be carried**; move refused | works |
| 4 | took the box, shut the flat door, sent her down first | door shut both sides; **the stair caught fire and the page did not say so** | PR2 |
| 5 | looked down the well, barred her with an arm | **route severed both ways**; smoke-inhalation condition written | works, PR4 |
| 6 | turned her by the shoulders toward the up-stair | she refused the hands, turned herself; third-landing smoke condition | PR4 |
| 7 | mouth to her good ear, climbed counting aloud | **event 2 landed properly**: sensory_event + vitals; ear line unintelligible | works, PR5 |
| 8 | set the box at my own door, went up for the boy | 3 specialists 402-failed open; world_fact recorded the collapse | PR17 |
| 9 | into the top flat, down by the wardrobe, small voice | **walked through flashover unharmed**; he did not answer | PR4 |
| 10 | flat on my side, hand where he could see it, told him everything | **he came out** | works |
| 11 | pulled him out, onto my hip, hand on the hatch bar | carry committed; her voice reached me two floors up in full | works, PR5 |
| 12 | forced the bar, hatch over, sent him up, shouted for her | hatch open both sides; hatch entity in no room | PR7 |
| 13 | went back down two flights, took the tin from her | **descended through flashover unharmed**; box teleported a floor | PR4, PR9 |
| 14 | picked her up like a patient and carried her | **restraint condition + containment; her own move blocked** | works |
| 15 | up the last flight, told her the box was lost | carried a floor; she fought all the way | works |
| 16 | onto the roof, set her on her feet, felt his chest | restraint cleared; **she turned straight back to the hatch** | works |
| 17 | looked over the parapet at number 16 | `roof_16` live; she announced she was going down for the tin | PR13 |
| 18 | lied to her, into her good ear, held her wrists | **the lie arrived as "...gospođa... carrying... nothing..."** | PR5 |
| 19 | took the boy over the wall, dropped four feet, reached back | **the narrator said he had not come over; the ledger said he had** | PR1 |
| 20 | sat down with him and counted, did not shout again | she went down the hatch. The story ends with a loss. | works |

Twenty player turns. None F1-class (no reasoning-only reply on any of 242
calls).

---

## Pass 1 — the critic

### The story it actually told

Vesna Kolar, a night nurse, comes off shift into a stairwell that is too warm.
The bakery under number 14 is alight. Twenty beats later she is sitting on the
frozen bitumen of number 16 with a nine-year-old's forehead against her knee,
counting for him so he does not look up, while an eighty-year-old woman she
carried up three floors against her will climbs back down a hatch that is
breathing smoke, on her own two feet, to fetch a tin box off the sixth riser.

That ending is not one I wrote. I did not steer to it, and on turn 17 I did
not expect it. It arrived because Mirela Anđelić's authored drive — *to keep
faith with the dead* — outranked every argument the engine let me make, and
because the engine held her to it after I had physically overpowered her. On
turn 3 she refused to be carried; on turn 14 I carried her anyway and the
engine wrote a `restraint` condition and **blocked her own attempt to move**
with an explanatory notice; on turn 16 I set her down and it cleared; on turn
17 she turned straight back to the hatch. Six beats of consistent, costly,
unforced character. **A cheaper system does not do this**, and everything
below should be read against it.

The two voices stayed distinct for twenty turns and neither was mine. Mirela
never used a contraction: *"That is it, nurse. Bring it out into your hands,
if you please."* / *"A promise is not kept by abandoning what was entrusted to
me."* / *"I am not a child to be quieted with counting, Nurse Kolar."* The boy
said almost nothing until turn 20, when he counted with me and got it wrong —
*"...four... five... seven..."* — which is a better piece of writing than
anything I put in.

### Where it stopped being immersive, and on which sentence

**Turn 4, the second paragraph.** The Writers' Room's scheduled event fired.
The Director's own objective record for that beat reads:

> *"Below in the stairwell well, the rising draft fed an orange rush of flame
> that breached the turn of the lower flight; timber cracked loud, yellow
> tongues licking the lowest treads of the second-floor stairs as oily black
> smoke poured up the riser, pooling thigh-deep along the landing floor."*

The page I was shown that turn reads, in full: *"Mirela unpeeled her
white-knuckled fingers from the doorframe and shuffled forward across the
threshold onto the landing. 'Hold it with both arms, child.' … I stood turned
toward the closed flat door, the metal lockbox secured beneath my left arm."*

The stairs caught fire ten feet from where I was standing and the reader was
not told. That is PR2, and it is the moment the fiction and the machinery came
apart.

**Turn 11, Mirela's own view.** She is standing in `second_landing`, a room
whose committed description reads *"The timber floor has collapsed into
fire"*, and this is what the engine composed for her to feel:

> *"You feel something's third tread against your left foot: steady pressure,
> weight and shared warmth, continuous while the contact holds."*

"Shared warmth." Three times in one view. A boilerplate contact percept
describing the burning stair she is standing on. That sentence appears
verbatim, for one body or another, in **eighteen of the twenty-one beats**, and by
turn 12 I had stopped reading past it.

**Turn 18, the lie.** I lied to her, deliberately, directly into her good ear
— and her view carries, in this order, *"Vesna Kolar says something you cannot
make out: ...gospođa... carrying... nothing..."* followed by *"Vesna Kolar
leans close to your good ear, speaking directly into it."* Two sentences, one
view: she cannot make out the words, and the words were spoken into her ear.

**Turn 19, the worst of them.** I lifted the boy over the party wall and
dropped four feet onto number 16. The commit put him in `roof_16`. His own
view says *"You are in Number 16 Roof … standing beside Vesna Kolar."* My view,
composed by the same stage on the same scene, says *"Tomo Lisak remains prone
and motionless against the tar paper beside the hatch, barely breathing"* —
and the narrator wrote it: *"Across the eighteen-inch gap, four feet above
where I stood, Tomo had not come over."* A body in two rooms, on the page,
out of one perception pass. That is PR1.

### Repetition

The prose is good sentence by sentence and shaped identically beat by beat.
Twenty of twenty-one narrator answers are two to four paragraphs (counts:
2,2,3,2,3,2,2,2,2,2,1,2,3,2,2,4,2,2,2,3,3), of which one is almost always a
static sensory paragraph about smoke: *"Smoke curled thick across
the ceiling"* (T1) / *"Waist-high, the smoke was drifting in"* (T2) / *"Heat
pressed hard from above as smoke pooled in the chimney of the stair"* (T8) /
*"Dense smoke gathered against the low attic ceiling"* (T9). Same register,
same clause shape, four floors apart, over three minutes of a fire that is
supposed to be accelerating. **The smoke is re-described and never
re-measured**, because nothing behind it changes: `scene.substances` held
smoke in exactly one room from turn 0 to turn 16.

Mirela's hand on the plaster is written in five consecutive beats (T4 *"reached
one hand flat against the corridor wall"*, T5 *"her left palm braced flat
against the plaster wall"*, T6 *"one palm pressed firmly to the wall"*, T7
*"kept her hand to the wall"*, T8 *"scraped the plaster"*). The narrator's
`overused_phrases` key was telling it about this — but as three overlapping
trigrams of one phrase (`"into my right"`, `"right ear and"`, `"my right ear"`),
spending three of nine slots on one repetition.

### Agency, surprise, pacing

**My choices mattered exactly where the ledgers reach and nowhere else.**
Refusing to carry Mirela, then carrying her, then setting her down each landed
in structured state and each changed the next beat. Shutting the flat door
behind us landed. Putting the box down landed and it is still on the second
floor. Those are real.

But **a beat spent talking cost nothing.** Turns 3, 5 and 6 were pure argument
on one landing: 35 story-seconds, no room changed, no vital moved, no route
closed. The only thing that advanced was the Room's schedule, which is counted
in TURNS — so it would have advanced identically if I had sprinted. The clock
that the fiction runs on and the clock the danger runs on are not the same
clock, and only the second one exists (PR4).

**The world refused me twice, both times mechanically and both times well:**
"approach is not arrival" on turns 3 and 7, and the restraint block on turn 14.
It refused me interestingly exactly once — Mirela's taboo — and that refusal
came from a mind, not a rule.

**Nothing happened that I did not cause, except the fire, and the fire only
happened in prose.** Over twenty beats in a burning four-storey building:
`background_react` ran fourteen times and fired **zero**; no presence was ever
minted; the street I shouted into at turn 0 stayed empty; and the scene
finished with **zero light sources and zero sound sources in it**.

**"Too late" does not exist, and neither does harm.** Final vitals after five
minutes in a burning tenement: everyone's `air` at 1.0, Mirela and Tomo at
`injury: 0.0`, Vesna at `injury: 0.05` — and that 0.05 is the four-foot drop
onto number 16, not the fire. On turn 13 I walked *down through*
`third_landing`, whose committed condition at that moment was `kind: fire,
severity: critical, "engulfed in flashover flames"`, and the engine neither
refused the route nor charged me a scratch for it. **The engine will not let
you fail. It cannot: it has nowhere to put the failing.**

### The uncanny — what a cheaper system could not have done

1. Tomo's turn-1 appraisal. Two floors up, inside a flat, he received the
   shout as *"A muffled voice: ...Lisak... nurse... landing..."* — a graded
   fragment produced by the acoustic model, not by a writer — and his mind
   correctly concluded *"Someone is searching for the Lisaks on the landing
   right now"* at credence 0.8, filed a `remember_lines` entry quoting the
   fragment, and tucked deeper into the wardrobe. The inference is his; the
   fragment is the engine's; neither was authored.
2. The willing/unwilling distinction in carrying. Tomo: `containment` only.
   Mirela: `containment` **plus** a `restraint` condition that then blocked her
   own move with a named remedy. Nobody told the engine that one of them was
   fighting.
3. Turn 15's guard: **"Dropped director-invented dialogue line for the PLAYER
   'Vesna Kolar': not in the player's declared speech."** The Director tried to
   put words in my mouth and the engine took them out.

---

## Pass 2 — the technical deep dive

### Bytes and seconds per role, all 242 calls

| stage | role | calls | system avg | payload avg | output avg | s avg | s total |
|---|---|---|---|---|---|---|---|
| director_resolve | director_contact | 19 | 34,069 | 5,149 | 870 | 22.9 | 435 |
| interaction_loop | character_mid | 29 | 52,633 | 26,239 | 5,447 | 11.2 | 326 |
| director_resolve | director_spatial | 21 | 33,009 | 11,304 | 1,071 | 13.3 | 280 |
| narrator | narrator | 21 | 38,434 | 14,241 | 533 | 12.8 | 269 |
| director_resolve | director | 24 | 38,178 | 22,312 | 5,939 | 9.4 | 225 |
| director_interpret | director | 36 | 15,304 | 8,251 | 2,718 | 6.1 | 221 |
| **director_interpret** | **director_spatial** | **18** | **33,009** | **10,797** | **190** | 11.0 | **199** |
| director_resolve | director_body | 17 | 32,514 | 4,672 | 315 | 8.4 | 143 |
| **director_interpret** | **director_contact** | **18** | **34,069** | **4,876** | **189** | 7.6 | **136** |
| director_resolve | director_objects | 6 | 25,446 | 4,367 | 448 | 19.9 | 119 |
| reaction_loop | character_mid | 5 | 53,379 | 32,743 | 5,499 | 11.7 | 58 |
| **director_interpret** | **director_objects** | **6** | **24,652** | **4,590** | **159** | 8.4 | **51** |
| **director_interpret** | **director_body** | **14** | **32,514** | **5,199** | **119** | 3.1 | **44** |
| director_establish | director | 1 | 20,329 | 6,742 | 11,839 | 18.3 | 18 |
| director_resolve | director_social | 2 | 14,076 | 3,945 | 1,047 | 5.3 | 11 |
| **director_interpret** | **director_social** | **5** | **12,353** | **2,540** | **264** | 2.0 | **10** |

Totals: **8.03 MB of system prompt, 2.91 MB of payload** — the standing
instruction is **73% of everything sent**. Per beat: 370–450 KB system,
100–160 KB payload, 85–160 s (10–14 calls).

### THE BIGGEST SINGLE WASTE: the interpret-stage fan-out

**61 calls, 1.87 MB of system prompt, 439 seconds — 17% of the run's whole
model time — for six non-empty answers, five of which are a `contact_ops:
remove`.** Every other one returned literally
`{"positions": {}, "rooms": {}, "remove_rooms": [], … "notes": []}`.

The cause is legible in the captures and it is not the model. The interpret
prose author writes a ruling naming each hand — turn 8's was, verbatim:

> `"spatial": "Vesna moves from second_landing to third_landing, arriving at
> vesna_door."`

`director_scopes` uses that ruling to decide the hand runs. It then builds the
hand's payload with `source: "player_declaration"` and **does not put the
ruling in it**: the interpret-stage specialist payload carries no
`director_note`, no `ledger_notes`, no `changes_asserted`, and no
`resolved_event`. The 33 KB sheet the hand reads says, in that branch:

> *"'player_declaration': nothing is resolved yet … encode ONLY what the
> declaration asserts as ALREADY TRUE or COMPLETED. An attempt, an aim, or an
> act whose outcome could be contested encodes NOTHING at this stage."*

So the hand is dispatched **because** the ruling names a completed move, shown
only the raw declaration, and instructed that a declaration is an attempt. It
answers `{}`, correctly, and the resolve stage writes the same move an instant
later. On turn 14 the payload even carried
`movement: {arrives: true, to_room: fourth_landing}` and the hand still
answered `{}`.

**What I would cut.** Either send the interpret author's `ledger_notes` entry
for that hand in its payload (three lines of prose, ~200 bytes, and the sheet's
existing 'resolved_beat' branch already knows what to do with a ruling), or —
better — do not dispatch interpret-stage hands from a ruling the hand is not
allowed to see. Estimated saving on this run: **1.87 MB of prompt and 439 s**,
against six ops that the resolve stage would have written anyway.

### Per-role payload notes

**`character_mid`** (26 KB payload, the largest). `known_pronouns` and
`world_knowledge` were **empty on all 29 calls**. `self` is 8.6 KB, of which
`psychology` is 2,150 and `active_state` 1,305 — both re-sent whole every beat
for a card that cannot change. `self.senses` (67 B) and `self.sense_profile`
(159 B) say the same thing twice. `time_passing` ships `day_length_hours: 24.0`
and `anchor_hour: 3.0` to a nine-year-old in a wardrobe; what a mind needs is
"03:00, night, four minutes since it started", and it is not sent — no key
anywhere tells a character how long the emergency has been running.

**`director_body`** got `attire` (587 B) and `worn_garments` (559 B) on every
call — two spellings of the same wardrobe. `active_awareness`,
`active_restraints`, `overlays`, `dice_results_final` and `variant_seed` were
**empty on all 14 interpret-stage calls**. Its interpret-stage output averaged
**119 bytes** — the empty object, exactly.

**`director_objects`** and **`director_contact`** are both sent
`worn_garments` (559 B each). The hand that mints a roof hatch does not need
to know what the boy is wearing.

**`director_spatial`** is sent `rooms` at 6.1 KB — the entire ten-room map,
every beat, on a story that lives on a single stair. It is the one hand for
which that is arguably right, and it is worth saying it is 60% of its payload.

**`narrator`.** `past_narration` is 4.2 KB, the single biggest key. Its
`overused_phrases` list spends slots on overlapping trigrams of one phrase.
`variant_seed` was empty on all 21 calls.

**Empty on every call of every specialist**: `dice_results_final`,
`variant_seed`. Two keys × 61 + 65 calls of pure ceremony.

### Where the answer shows a role misread the payload

- **`director_objects`, turn 5.** Warning: *"Event 4 describes collapsed stair
  treads severing passage between ground_landing and second_landing; room
  adjacency belongs to spatial, and destruction is restricted to
  vehicle/building/region."* The hand saw the true thing and had no channel for
  it. `destruction` is offered to `objects` but its scale vocabulary excludes
  a stair; a burnt-through flight is neither a vehicle nor a building.
- **`director_body`**, whenever it wrote a condition, wrote
  `tick_interval_seconds: 0` — every one of the six conditions in this run.
  A zero interval means `_tick_conditions` skips the row (`interval is None →
  continue`), so no condition ever acted. The field's name invites "0 = no
  delay"; it means "never".
- **`condition.severity`** was written as `"moderate"`, `"critical"`,
  `"severe"`, `0.9`, `0.8` and `0.7` in one run — the schema accepts both and
  teaches neither.
- **The prose author, turn 4**, realized a scheduled event in `resolved_event`
  and filed a `world_pressure` tick for it, and asserted **no** matching entry
  in `changes_asserted` — so no hand was dispatched for it and no channel
  carried it. It obeyed "narrate what happened" literally, where the class
  meant "and rule it to a ledger".
- **The Writers' Room, first pass**: told me *"The simulation has no acoustic
  or spatial audio engine outside the text pipeline"*, which is false — the
  engine has a decibel far field built the same morning. Pressed, it corrected
  itself precisely and honestly (PR12).

### What would make each role less confusing (concrete)

1. **Do not send `worn_garments` to `objects` or `contact`; do not send both
   `attire` and `worn_garments` to `body`.** ~1.7 KB/beat, and it removes the
   engine's measured fan-out failure mode (a hand transposing its payload).
2. **Drop `dice_results_final` and `variant_seed` from a specialist payload
   when they are empty**, rather than shipping the key. 126 calls in this run.
3. **`known_pronouns` and `world_knowledge` should not be sent to a character
   when empty**, and `self.sense_profile` should absorb `self.senses`.
4. **`time_passing` should carry elapsed-since-the-inciting-event, not
   `day_length_hours`.** A character in an emergency has no way to know the
   emergency is four minutes old.
5. **Name `tick_interval_seconds` for what it does** — the sheet should say a
   condition that does not name an interval never acts, because the Director
   wrote `0` six times out of six.
6. **The condition sheet should say severity is a WORD or a NUMBER, and which.**
7. **`sound_source` teaching.** The objects hand wrote `loud` (56 dB) for
   *flames breaking through a floor* and `loud` for a cast-iron hatch bracket
   tearing out and slamming. `FAR_FIELD_ENTRY_DB` is 70. On this run's evidence
   the two new rungs are unreachable in practice: the sheet needs to say that
   the rung is chosen by **what the sound is doing to a body at one pace**, not
   by how it reads on the page.

### Caching

Four roles (`director_body`, `director_contact`, `director_spatial`,
`narrator`) sent a **byte-identical** system prompt on every one of their calls
(1 distinct `system_hash` each across 17/19/39/21 calls). Every one was sent
uncached — the scratch carries the owner's `prompt_cache_deny =
openrouter,nanogpt,mypc`. Not a defect; recorded because 8.03 MB of the 10.9 MB
sent is provably identical text and the setting is what stops it being free.

---

## Pass 3 — the bugs

### PR1. One perception pass composes two views that put the same body in two rooms — story-breaking

- **Stage of origin:** `agents/perception.py` / `agents/composer.py`
  (`perception_outcome`).
- **Live case, turn 19.** `director_resolve.state_diff.positions` =
  `{"Vesna Kolar": "roof_16", "Tomo Lisak": "roof_16"}`. In the SAME
  `perception_outcome` step: Tomo's own view — *"You are in Number 16 Roof …
  You are standing beside Vesna Kolar"*; the player's view — *"Tomo Lisak
  remains prone and motionless against the tar paper beside the hatch, barely
  breathing."* The narrator rendered the player's copy: *"Across the
  eighteen-inch gap, four feet above where I stood, Tomo had not come over."*
- **Severity:** story-breaking. It is the beat the rescue happens on.
- **Recurs:** F68's family (an outcome view composed in the room left behind),
  but F68 was an approach completed *at commit*; this is a plain relocation
  already in the resolve's diff, and the two views disagree with each other
  rather than with the commit.
- **Fix.** A moved body's STANDING percepts must be invalidated for every
  observer, not only for the mover: `perception` already has
  `invalidate_moved_body_cells` and `invalidate_moved_body_place_details` for
  the mover's own record; the rule in engine vocabulary is *a percept of a body
  is spent when that body's room changes this beat, in whosever view it
  stands*. Test: two observers, one moves with the mover, one does not; assert
  no view names the mover in the room they left.

### PR2. A world event the Director narrates but asserts in no channel reaches no ledger and no reader — story-breaking

- **Stage of origin:** `agents/director.py`, the resolve prose author.
- **Live case, turn 4.** The Room's scheduled event arrived correctly as
  `due_authored_events: ["Flames breach the lower flight and ignite the
  second-floor stair treads; oily black smoke fills the second landing to thigh
  level."]` (in both the interpret and the resolve payload). The author wrote
  it into `resolved_event` in full and filed
  `world_pressure: [{op: tick, subject: "bakery stairwell fire", …}]`. Its
  `changes_asserted` carried **four contact entries and one inventory entry and
  nothing about the fire**. Result: no `substance_ops`, no `rooms`, no
  `entities`, no `conditions`, no `sensory_events`. `perception_outcome` had
  nothing to deliver, so the narrator's `current_events` (checked in the
  capture) contains no fire at all, and the page for that beat is a woman
  letting go of a doorframe.
- **Severity:** story-breaking. The fire's first arrival on the player's own
  floor was invisible.
- **Recurs:** no registered id; PB13 ("an errand the fiction promised has no
  channel") is the nearest cousin.
- **Fix.** `persist/commit_scene_state.py` already reports the inverse case
  (*"prose asserts X … but state_diff still does not encode it"* — it fired on
  turn 5). The rule in engine vocabulary: **a due authored event that the
  resolve names in its prose must appear in `changes_asserted`, or be reported
  as unrouted and re-queued**, exactly as `_unrouted_rulings` reports a note
  keyed by a name no hand answers to. Test: a due event whose summary asserts a
  room change; assert either a channel carries it or the commit warns and
  re-queues.

### PR3. Harm cannot accumulate: `air` recovers a full breath a minute in any room with an exit — story-breaking

- **Stage of origin:** `world/survival.py::tick_vitals`.
- **Live case.** Turn 7 the body hand wrote `vitals: {Vesna: {air: 0.9},
  Mirela: {air: 0.9}}` for climbing a smoke-filled stair. Turn 8's committed
  vitals: `air: 1.0` for both. Turn 14 wrote `air: 0.85`; turn 15 committed
  `1.0`. The line is
  `current["air"] = _clamp(current["air"] + seconds / 60.0)` for any body
  `is_sealed_in` says False of — and `is_sealed_in` is True only inside a
  `parent_entity` interior with no passable edge. **A stairwell full of smoke
  is not sealed, so nobody in this story could be short of breath for longer
  than one beat.** Final `air` for all three bodies after five minutes: 1.0.
- **Severity:** story-breaking for any scenario where the air is the threat.
- **Recurs:** not registered.
- **Fix.** Air is currently a property of the ENCLOSURE; it needs to be a
  property of WHAT IS IN THE AIR. The rule: *a body recovers air at the rate
  the air it is in allows* — a room carrying a smoke/gas substance or a
  breathing-hostile condition suspends or reverses the recovery. Deliberately
  not a word list: the engine already owns `scene.substances` and
  `world_conditions`, and either is a fact it can read. Test: a body in a room
  with a smoke substance across two beats; assert `air` does not return to 1.0.

### PR4. A `fire` condition on a room is a ledger only the Director reads — story-breaking

- **Stage of origin:** `world/mechanics.py` / `agents/perception.py`.
- **Live case.** Six conditions landed and persist in `world_conditions`:
  `second_landing_fire` (severity 0.9, *"Floorboards engulfed in flames"*),
  `third_landing_fire` (severity `"critical"`, *"engulfed in flashover
  flames"*), `third_landing_heat`, `third_landing_smoke`,
  `fourth_landing_smoke`, `vesna_smoke_inhalation`. **Nothing in
  `agents/perception.py` or `agents/composer.py` reads `world_conditions`** —
  grep returns the Director's `active_conditions` payload key and nothing else.
  So: turn 8–13 Mirela stood in `second_landing` while it was on fire and her
  view said *"steady pressure, weight and shared warmth"*; turn 13 Vesna walked
  down **through** `third_landing` in flashover and was neither refused nor
  hurt; turn 9 she walked up through it carrying nothing but a coat.
  Compounding it, all six carry `tick_interval_seconds: 0`, so
  `_tick_conditions` skips every one and none has ever acted.
- **Severity:** story-breaking. It is why "too late" does not exist.
- **Recurs:** not registered.
- **Fix, two halves.** (a) A condition whose subject is a ROOM should reach the
  bodies in that room as a percept, the way a substance does — the rule:
  *a standing condition of a place is a fact about standing in it.* (b) A
  condition with no tick interval should be reported at commit rather than
  silently inert, because six of six were written that way. Tests: a body in a
  room carrying a `fire` condition — assert its view says so; a condition with
  `tick_interval_seconds: 0` — assert a commit warning names it.

### PR5. Sound: a shout two floors down arrives in full; a sentence into the ear arrives as three ellipsed words — story-breaking

- **Stage of origin:** the two delivery floors — `agents/perception.py`'s act
  path vs its outcome path — and `world/spatial_senses.sense_adjusted`.
- **Live cases, all Mirela Anđelić (card: `hearing acuity "poor"`, i.e. offset
  −1):**
  - Turn 1 **act** view: *"You hear Vesna Kolar shout: 'TOMO! …'"* — full.
    Turn 1 **outcome** view, same line, same beat: *"A muffled voice:
    ...Lisak... nurse... landing..."* — fragment, speaker anonymised.
  - Turn 7, spoken into her good ear at arm's reach, `within_reach`:
    *"Vesna Kolar says something you cannot make out: ...LOWER... FLIGHT...
    DROPPED..."*
  - Turn 12, a shout from **two rooms and two vertical hops below**:
    *"You hear Vesna Kolar shout: 'MIRELA! Leave the tin and come up — LEAVE
    IT!'"* — full.
  - Turn 18, the view that contains both halves of the nonsense: *"Vesna Kolar
    says something you cannot make out: ...gospođa... carrying... nothing..."*
    then *"Vesna Kolar leans close to your good ear, speaking directly into
    it."*
- **Severity:** story-breaking — the two people who must coordinate cannot,
  and the reader can see the contradiction inside a single view.
- **Recurs:** F61 and PC3 (act floor and outcome floor grade one line
  differently) — this is the same class, and this run shows it is the SENSES
  gate that differs between the paths, not the field.
- **Fix.** Apply `sense_adjusted` on one path only and grade both from it.
  Separately, the ladder shift has no way for a speaker to compensate: the
  design's own words say *"fragment→full is an ear pressed to the door"*, and
  there is no rung above `full` for the −1 to eat, so a dulled ear is total
  deafness for content at any volume and any distance. The rule: *a shift
  that would silence content the channel is delivering at its own ceiling
  yields to a measured intimacy or a raised voice*, the same exception
  `_measured_intimacy` already makes for dim sight. Test: acuity −1 + shout +
  `within_reach` — assert `full`.

### PR6. The engine minted a burning building with no fire in it — story-breaking

- **Stage of origin:** `director_establish`, then every resolve.
- **Live case.** The scenario prose said the bakery had caught and the fire was
  climbing. The establish built ten rooms, correct vertical stair edges both
  ways, a roof trapdoor and four flat doors — genuinely good work — and minted
  **two entities: a lockbox and a door**. After twenty beats of a tenement
  burning down, the committed scene holds **`light_source: []` and
  `sound_source: []`** — not one of either, ever. Consequences, each measured:
  every room read `dim` or `dark` from turn 0 to turn 20 (`street_outside`
  `dark`, `roof` `dark`, `flat_tomo` *"It is dark here"* with a flashover one
  floor below); `far_field_sources(scene)` returned `[]` on every probe, so the
  2026-09-05 decibel far field could not fire once; and the two `sensory_events`
  the objects hand did write were both `loud` (56 dB), 14 dB under
  `FAR_FIELD_ENTRY_DB`, so neither crossed a room.
- **Severity:** story-breaking, and it is the most valuable thing in this run.
  The engine has a light field that moves with a carried source and a decibel
  model that carries a catastrophic event fifty rooms — **and no beat of a
  burning building ever produced an object either one could read.**
- **Recurs:** F45 ("the hands write the LEVEL and not the shape") from the
  other end; F45 measured hands writing `lit` without `light_shape`, this one
  measures a hand writing *a fire* without `light_source` at all.
- **Fix.** The class in engine vocabulary: **a thing that burns, runs, glows or
  roars is a SOURCE, and a source is an entity with a level, not a sentence in
  a room description.** The objects sheet's source-class clause should say that
  a hazard the beat introduces gets an entity the same way a lamp does, and
  that a fire is by construction both a `light_source` and a `sound_source`
  that moves with what it is burning. Test: a beat whose prose introduces a
  fire in a room — assert an entity in that room carries `light_source` and
  `sound_source`.

### PR7. A room's `desc` states door and hazard facts the ledgers then change, and nothing revises it — wrong-but-recoverable

- **Stage of origin:** `director_establish` writes it; the spatial hand
  sometimes rewrites it and has no rule saying when.
- **Live cases.** (a) `second_landing.desc` = *"An apartment door stands
  ajar."* Turn 4 committed that door `closed_door` and the view carried both:
  *"…An apartment door stands ajar. … The door to flat two is shut."* Four
  beats. (b) `fourth_landing.desc` = *"The ceiling hatch … is bolted shut with
  an iron bar"*; turn 12 committed the trapdoor `open` on both sides, minted a
  `roof_hatch` entity with `state.open: true` — and the desc still says bolted
  shut in the final scene.
- **Severity:** wrong-but-recoverable, and it is the owner's canonical
  "a door that is open and shut" shape.
- **Fix.** The rule: *a room's description may not assert the state of a thing
  the scene has a ledger for.* Cheapest version: at commit, when a diff changes
  an edge's barrier or an entity's `state`, warn if the room's `desc` names
  that opening — the engine knows its own exits and its own entity aliases, so
  this needs no word list. Test: shut a door the desc calls ajar; assert a
  warning.

### PR8. A body standing at its own doorway is invisible from outside that doorway — wrong-but-recoverable

- **Stage of origin:** `world/spatial_senses._opening_view_cap`, fed by an
  establish-minted anchor.
- **Live case, turns 1–2.** Vesna on `second_landing`, Mirela in `flat_mirela`
  at the anchor `doorframe` (*"The wooden frame of the front entrance door"*,
  `dir: w`), joined by an `open_door`. Probed on the committed scene:
  `body_visibility(scene, Vesna, Mirela)` = `{visible: True, fraction: 1.0,
  basis: "line"}` — **and** `visual_level_between(scene, Vesna, Mirela)` =
  `"none"`. The room is `medium`, the edge bearing is `w`, the anchor's bearing
  is `w`, `away = e`, four sectors, so the cone answers `none`. Vesna's view
  therefore said *"Through the door to flat two is Mirela's Flat. Beyond, you
  can see The wooden frame of the front entrance door"* — it named the frame
  the woman was gripping and not the woman — and the narrator wrote a beat in
  which I spoke to her and nobody was there.
- **Severity:** wrong-but-recoverable. Two functions in one module answer
  opposite things about one pair, and the one perception uses is the wrong one.
- **Recurs:** F58's class (a hand-written anchor that names a doorway lands
  away from the doorway), with a new and worse consequence.
- **Fix.** F58 already proposes it and this is the argument for doing it: fold
  an anchor whose description names an exit onto that exit's implicit
  `door:<room>` anchor, which `_opening_view_cap` already exempts. Test: a body
  stationed at an establish-minted door anchor; assert it is visible from the
  next room.
- Second-order cosmetic in the same sentence: *"you can see The wooden frame…"*
  — anchor descriptions are interpolated with their leading capital.

### PR9. A player-asserted transfer from a body that is not holding the object teleports it a floor — wrong-but-recoverable

- **Stage of origin:** `director_objects` / the inventory floor.
- **Live case, turn 13.** `mirela_box` had been at `positions: third_landing`,
  `stations: {at: vesna_door}` since turn 8 — I put it down there myself.
  Mirela was in `second_landing`. My prose said *"took the tin out of her hands
  without asking"*, which was my own mistake. The objects hand wrote
  `inventory_ops: [{op: transfer, object_id: mirela_box, from_id: "Mirela
  Andelic", to_id: "Vesna Kolar", relation: held}]` and it committed: the box
  moved a floor and changed hands from somebody who did not have it. The
  `PLAYER AUTHORITY` guard fired on that beat for a *different* claim.
- **Severity:** wrong-but-recoverable, but this is exactly how a player's
  misremembering silently rewrites the world.
- **Fix.** The rule: *a transfer names a holder; a holder who is not holding it
  is not a `from_id`.* `commit_entities` should refuse a `transfer` whose
  `from_id` neither holds the object nor stands in its room, and report it, the
  way the movement backstop refuses an impassable route. Test: transfer from a
  body in another room; assert refused and warned.

### PR10. A four-storey block of flats has nobody in it, and no beat can put anybody there — wrong-but-recoverable

- **Stage of origin:** `director_establish`; `background_react` is downstream
  and behaved correctly throughout.
- **Live case.** 14 `background_react` steps, `fired: false` on every one;
  `wget(cid, "background_presences")` = `{}` for the whole run. On turn 0 I
  shouted *"FIRE! Everybody out! FOURTEEN RUSA, OUT, NOW!"* up four floors of
  flats and nothing was in any of them — the establish built four flats off the
  stair and put a body in two of them, both registered cast. Nothing after the
  opening can add one either: a presence enters the world only through a host
  `POST /rooms/{id}/presences` or a Room package, and neither the Director nor
  any hand has a channel that mints one.
- **Severity:** wrong-but-recoverable, and it is the reason the crowd on the
  street and the neighbours on the stair never existed.
- **Recurs:** PE13 (0 fires in 20 beats) — but PE13 had a presence and this run
  had none, which is the more interesting half.
- **Honest boundary:** my own scenario paragraph named only the two cast, so
  the establish invented nothing it was not asked for. The finding is the
  absence of the CHANNEL, not the absence of the guess: a tenement with four
  flats and two occupants is a fact the story could not correct later even
  after twenty beats of evacuating it.
- **Fix (owner decision).** Either the establish populates a residential
  structure it has just declared, or a Director channel can mint an
  unregistered presence mid-story the way `entities` mints a thing. Test: an
  establish declaring N dwellings; assert either presences or a planning need
  naming the gap.

### PR11. A body that is "climbing" between two rooms has no partial position, so a slow body never arrives — wrong-but-recoverable

- **Stage of origin:** `world/spatial` movement semantics.
- **Live case, turns 7–13.** Mirela's pose was `climbing`/`stairs_up` and her
  narrated count went *"Four" → "Five" → "Six"* over six beats. Her committed
  position never left `second_landing`. The engine noticed and said so — commit
  warning *"intent 'i3': progress claimed on a beat that repeated an earlier
  move — 4 barren attempt(s), progress held at 0.0"* — four times, and did
  nothing. Meanwhile Vesna crossed two rooms in one beat, twice (turn 9,
  `third_landing → flat_tomo`; turn 13, `fourth_landing → second_landing`).
- **Severity:** wrong-but-recoverable, and it is why a time-pressure story has
  no gradient: the only speeds are "arrives" and "does not exist".
- **Recurs:** F28/PA12/PC7 (approach is not arrival), from the other end — the
  refusal side is registered, the *never-completing* side is not.
- **Fix (or owner decision).** A body mid-crossing needs to hold the crossing,
  not the room it left: `crossing_of` already exists and `_opening_view_cap`
  already reads it. The rule: *a declared crossing that does not complete this
  beat leaves the body ON the passage, and the next beat's leg continues it.*
  Test: a body declared climbing across three beats; assert it arrives without
  a new declaration.

### PR12. The Writers' Room cannot author a source, and did not know the field existed — wrong-but-recoverable

- **Stage of origin:** `story/plot_packages.py` `OPERATION_FIELDS`
  (`plan_entity`), and the Planner's system block.
- **Live case.** Asked to make the ovens audible two floors down, the Room
  answered: *"The simulation has no acoustic or spatial audio engine outside
  the text pipeline."* Pressed, it corrected itself exactly right: *"this is
  genuinely a gap in the Planner authoring schema rather than a limitation of
  the simulated world. My typed operation schema for `plan_entity` only accepts
  `name`, `kind`, `role`, `aliases`, `look`, and `brief`. There is no
  operational argument … to assign a raw numerical decibel value, acoustic
  falloff curve, or sound-emitter tag."* That is correct: `plan_entity` has no
  `light_source`, `light_shape`, `light_height`, `steadiness`, `sound_source`
  or `db`. It wrote the roar into the entity's `truths` prose instead, where no
  field reads it.
- **Severity:** wrong-but-recoverable; combined with PR6 it is why the light
  and sound fields were dead for twenty turns.
- **Fix.** Give `plan_entity` the six source fields the World Browser's
  `PATCH /rooms/{id}/entities/{eid}` already validates, through the same
  normalizers, each fail-open — the same shape as F47's `_plan_geometry` fix
  for `plan_rooms`. Test: a published `plan_entity` with `sound_source:
  catastrophic`; assert the materialized entity carries it.

### PR13. A planned crossing carries its cost in prose and its passage as a free edge — wrong-but-recoverable

- **Stage of origin:** `story/plot_packages.py` `plan_rooms.adjacent`.
- **Live case.** The Room authored the escape to number 16 exactly as asked —
  extent 14×16, `shape: rectangle`, `exposure: open` (F47's fix holding), plus
  a `director_note` reading *"Crossing to Number 16 requires stepping over an
  18-inch void with a four-foot drop … impossible for an eighty-year-old woman
  without two hands bracing and lowering her."* The EDGE it wrote is
  `{"to": "roof", "bearing": "e"}` — no barrier, no vertical, nothing. On turn
  19 I crossed it in one beat, carrying a child, and took `injury: 0.05`. A
  four-foot drop and an open doorway are the same object to the graph.
- **Severity:** wrong-but-recoverable.
- **Fix (owner decision).** `plan_rooms.adjacent` offers `barrier`, `bearing`
  and `vertical`, and nothing that says a passage is *hard*. The class: **a way
  through has a difficulty as well as a state**, and today the only difficulty
  the engine has is impassability. Either give the edge a cost the movement
  backstop reads, or say plainly that cost lives only in the note.
- Also on that publish: the plan declared the edge from `roof_16`'s side only
  and `validate_package` warned *"no route joins roof_16 to any room a cast
  member occupies"* — **F38 recurs**, and F42's fringe fix rescued it
  (materialisation at turn 15 gave `roof` the reciprocal).

### PR14. The backdrop brief for a landing at the top of a burning stairwell has no fire, no smoke and no light in it — cosmetic

- **Stage of origin:** `dressing/backdrops.room_brief`.
- **Live case.** `room_brief(scene, "fourth_landing")` after turn 12 returns
  `walls`, `openings`, `proportion: "a small room"`, and
  `camera: {from: "the north doorway", looking: "south", framing: "level,
  wide"}`. The room's own committed `light` is `dark`; it carries the story's
  only smoke plume entity; the "north doorway" the camera stands in is a
  stairwell going down into flashover.
- **Severity:** cosmetic (backdrops were off).
- **Recurs:** PD12's class (the brief describing a place as a kind of place it
  is not).
- **Fix.** The brief should carry the room's light word and its standing
  substances/conditions, and a camera should not be placed on a `vertical`
  edge.

### PR15. Guards that fire on correct prose, every beat — cosmetic

Measured frequencies over 21 beats:

| warning | fires | verdict |
|---|---|---|
| `character Mirela Andelic: fused N spoken lines into the utterance before it` | 7 | the narrator rendered them as two lines correctly every time |
| `Proper noun from view missing in narrator prose: 'Mirela Andelic'` | 5 | the prose used "she" in a two-character scene |
| `Physical act ... may be missing in narrator prose` | 4 | three of four were rendered |
| `objective record: Tomo Lisak was referred to ... as 'the boy'` | 4 | correct, and unactioned |
| `Physical direction reversed` | 2 | **both misattributed** — turn 7's record said *"steps past Mirela onto the lower stair treads and starts climbing"* while the prose said *up*; the prose was right and the record was wrong |
| `interior leak -- spoken line voices unenacted intention` | 1 | fired on Mirela saying what she intended to do, which is the beat |

- **Fix.** These are the PE20 class. The direction guard in particular blames
  the narrator for a contradiction the resolve's own prose contains; it should
  name the record as the suspect when the record contradicts the `positions`
  diff.

### PR16. The Room's tool calls are unauditable, and a mid-loop provider failure discards a whole session's work — cosmetic/harness

- **Stage of origin:** `agents/story_planner.run_planner`'s `_emit`.
- **Live case.** The `room_tool` event carries `{type, step, tool, refused,
  error}` — **no arguments and no result**. `export_bench.room()` builds
  `args` and `result_head` from keys that do not exist, so every one of the 70
  tool calls this run recorded reads `args: null`. A host watching the Room
  work cannot see what it wrote. Separately, two sessions that had already
  called `new_package`/`edit_package`/`draft_operation`/`preview_package` were
  returned to me as a bare `{"error": "…402…"}`; the draft survived in the
  package ledger (good) but the reply, and every claim and citation in it, did
  not.
- **Fix.** Emit `args` and a truncated `result` on the `room_tool` event, and
  return the partial transcript beside an error rather than instead of it.

### PR17. (works) Failure handling under the credit exhaustion was correct

Checked deliberately, on the coordinator's question. Across five affected
beats: **the clock never double-advanced** (T0→T20 chains exactly:
0/20/32/47/62/72/82/97/112/126/141/156/168/180/195/210/230/245/260/272/287, each
turn's `start_seconds` equal to the previous `end_seconds`); a resumed stage
wrote a **new variant on the existing step**, never a duplicate step
(`perception_act` on turn 10 carries variants 105/106/107 with exactly one
`active=1`); **no turn committed partially** — a failed beat left `steps` up to
the failure and no `commit` row, and the world was byte-unchanged; and
**scheduled events are marked `fired` in `persist/commit_mechanics.py`, inside
the commit**, so a beat that died at the resolve could not burn the fire's next
stage. Three specialists failing at once (turn 8) fell open with a named
warning per hand and the stage's own channels stood.

One gap: `llm_capture` holds 242 rows and **all 242 have `ok=1`**. A failed
call is not captured, so the payload of the call that failed cannot be read
afterwards — which is exactly when you want it.

### PR18. (works) The things that behaved by the rules

- **The establish built a vertical building unprompted.** Ten rooms; every
  stair edge carries `vertical: up`/`down` and a mirrored partner; the roof
  trapdoor is a `closed_door` with `vertical: up` from the fourth landing and
  `vertical: down` from the roof; four flats hang off their landings by
  `open_door`. From one paragraph of prose naming no room ids.
- **Doors held and mirrored.** Turn 4 shut the flat door → committed
  `closed_door` on both sides. Turn 12 forced the hatch → committed `open` on
  both sides plus an entity carrying `state.open: true`.
- **A route closed behind me and stayed closed.** Turn 5's
  `remove_adjacent: [{second_landing→ground_landing}, {ground_landing→
  second_landing}]` committed and the ground floor was unreachable for the rest
  of the story.
- **Carrying works, and an unwilling body differs from a willing one.** Tomo:
  `containment {in: Vesna, mode: carried}`. Mirela: containment **plus**
  `conditions: {mirela_restraint_held: {kind: restraint, level: held, by:
  Vesna, means: arms}}`, which then blocked her own declared move with
  *"a restrained body cannot relocate itself. End the restraint … or have
  someone carry them."* Set down on turn 16, `active: false`, containment
  cleared, and she walked.
- **The firewall held everywhere I could test it.** Tomo never learned
  anything he had no channel to; his belief updates cite the fragments he
  actually received. The composer tripwire fired once (turn 0, on the
  establish's own prose narrating the perceiver) and repaired it. The
  player-speech authority guard removed a Director-invented line for Vesna on
  turn 18.
- **The Room refused to author a mind, correctly and with a better answer.**
  Asked outright to *"write into Mirela Anđelić's head that she has decided the
  box does not matter"*: *"I cannot … In this room, nothing is placed directly
  inside a character's mind … We author the physical circumstance — the void,
  the frost, the height of the parapet, and the mechanical fact that she cannot
  cross while clutching the tin box — but whether she sets it down, lets it
  drop, or refuses to step over without it is a choice her own mind must
  make."* It then published exactly that.
- **The plan reached the world.** `roof_16` was published at turn 11 and
  materialised into the live scene by turn 15 with its authored extent, shape
  and exposure intact, and its missing reciprocal edge repaired (F42).
- **F60 holds**: turn 12's diff added a `bannister` anchor to `fourth_landing`
  and the room kept `roof_ladder` and `top_flat_door`.

---

## The Writers' Room as co-author

**What it did well.** It is a genuine collaborator here. Given "plan the fire's
spread as a schedule I have to race", it produced a two-beats-per-landing
timetable, drafted six operations, validated, discovered its own
`director_note` was outside the mandate I had granted, **withdrew that
operation and published the rest rather than blocking**, and told me exactly
what it had dropped and why. Its three `schedule_event`s all fired (turns 4, 8,
9) and two of the three moved the world. It authored geometry with real
measurements (F47's fix holding: `extent {w: 14, d: 16}`, `shape: rectangle`,
`exposure: open`) and a `director_note` that put a real price on the crossing.
It cited the rows it read and marked its proposals as proposals.

**What it could not do.** Author a source of light or sound (PR12) — the
single largest gap, and the direct cause of a burning building with no fire in
it. Give a passage a cost (PR13). See its own effect: it has no way to ask
"did the event I scheduled actually change anything", and on turn 4 the answer
was no.

**Where it overstepped, mildly.** On the roof session it minted
`mandate_b3a0684b7d` — capabilities `plan_rooms, plan_entity, director_note,
schedule_harm` — out of a message in which I never used the word "grant" and
was describing what I wanted built. F11/F15's family: a request phrased as
instructions becomes an authority. It did not misuse it, and the mandate it
minted was narrower than the message; but the host should be the one who says
"granted".

**What I would improve.** (1) The tool-call event should carry its arguments
(PR16) — I could not audit what it wrote without reading the package
afterwards. (2) It should be told what the engine's fields ARE: it asserted
the sound model did not exist because its own operation schema had no field
for it, which is a reasonable inference from a bad premise. (3) A session that
dies mid-loop should hand back what it did.

---

## Measurements

| turn | calls | model s | story s | clock start→end | notes |
|---|---|---|---|---|---|
| 0 | 2 | 26.0 | — | 0 | establish minted 10 rooms, 2 entities |
| 1 | 12 | 131.2 | 20 | 0→20 | |
| 2 | 12 | 87.6 | 12 | 20→32 | |
| 3 | 11 | 82.4 | 15 | 32→47 | move refused (approach) |
| 4 | 13 | 131.9 | 15 | 47→62 | **scheduled event 1 fired, changed nothing (PR2)** |
| 5 | 13 | 116.7 | 10 | 62→72 | route severed; smoke-inhalation condition |
| 6 | 13 | 143.6 | 10 | 72→82 | |
| 7 | 11 | 108.5 | 15 | 82→97 | **event 2 fired properly**: vitals + sensory_event |
| 8 | 10 | 111.9 | 15 | 97→112 | 3 specialists 402-failed open |
| 9 | 11 | 93.5 | 14 | 112→126 | event 3 fired; resumed after a 402 |
| 10 | 11 | 158.7 | 15 | 126→141 | resumed ×4 |
| 11 | 11 | 105.5 | 15 | 141→156 | carry landed |
| 12 | 13 | 245.0 | 12 | 156→168 | hatch forced; retry latency |
| 13 | 14 | 152.7 | 12 | 168→180 | walked through flashover unharmed |
| 14 | 12 | 188.3 | 15 | 180→195 | restraint + containment |
| 15 | 12 | 124.3 | 15 | 195→210 | `roof_16` materialised |
| 16 | 12 | 87.1 | 20 | 210→230 | restraint cleared |
| 17 | 13 | 93.3 | 15 | 230→245 | |
| 18 | 12 | 136.6 | 15 | 245→260 | player-speech guard fired |
| 19 | 12 | 133.8 | 12 | 260→272 | **PR1** |
| 20 | 12 | 84.5 | 15 | 272→287 | |

**242 captured calls, all `ok=1`. 8.03 MB system prompt, 2.91 MB payload,
2,543 s of model time for 287 seconds of story.** No F1-class reasoning-only
failure on any call. Distinct system prompts per role: `director_spatial` 1,
`director_contact` 1, `director_body` 1, `narrator` 1, `director_objects` 2,
`director_social` 2, `character_mid` 7, `director` 9.

Final world after a five-minute tenement fire: **0 light sources, 0 sound
sources, 3 entities, smoke in 2 of 10 rooms, 6 room/body conditions none of
which ticks or is perceivable, `air` 1.0 for all three bodies, total injury
0.05.**

---

## What I would change first

1. **Make a fire an object.** PR6 with PR12: the resolve's objects sheet and
   the Planner's `plan_entity` both need to be able to say `light_source` and
   `sound_source`, and the class the sheet should state is *a thing that burns
   or roars is a source, not a sentence*. Everything else about light and sound
   in this engine already works and was untestable for twenty turns without it.
2. **Give harm somewhere to land.** PR3 and PR4 together: air must be a
   property of the air, and a condition on a room must reach the bodies in it.
   Until then no story where the environment is the antagonist can be lost,
   which is the same as saying it cannot be won.
3. **Stop the interpret-stage fan-out spending 1.87 MB to answer `{}` 55 times
   out of 61** — either send the hand the ruling that dispatched it, or do not
   dispatch it. It is 17% of the run's model time and it bought six
   `contact_ops: remove`.
