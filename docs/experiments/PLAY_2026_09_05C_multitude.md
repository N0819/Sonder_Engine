# Play campaign 3 — "The Hearing at Vaunt's Yard" (agent M, slug `multitude`)

**Stress axis: too many people talking at once.** Six named bodies in one
room, a crowd behind a shut door, and a scene that only works as public
speech. Twenty player turns, 2026-09-05, scratch database from
`export_bench.py prepare --chats 115`, Gemini 3.8-flash on provider 3, capture
on with full bodies.

**What was authored, and what the engine built.** Per the mid-run correction:
only a persona (Ottoline Sarr, harbour clerk), five character cards with every
psychology field filled (`character_card_warnings` empty on all five), and a
scenario in ordinary prose naming no room id, no extent, no anchor and no
barrier word. `director_establish` built the whole world from that paragraph
— four rooms, six anchors, three doorways, the positions and stations of six
bodies. Nothing about the geometry was repaired by hand before play. Three
host interventions through the World Browser routes are marked as such in §3
and all three came after the beat that motivated them.

**Harness conditions.** Turn 5 died mid-pipeline on an HTTP 402
(`in_flight_budget_exhausted`) while five play agents shared one OpenRouter
account; it was resumed from the last recorded step once credit was restored,
and what the engine did with the partial result is PM19 — a finding, not
noise. Two Writers' Room calls (of five) ended F1-class
(`ReasoningBudgetExhausted`) after four attempts, costing 435 s and 160 s.
The 402 affected exactly one beat; every latency in §2 is otherwise a clean
measurement. I did **not** run a Japanese turn: switching the story language
in the middle of a hearing with six English cards tests the pack in a
configuration no player uses, and the axis I was given is speech in a crowd.

---

# 1. The critic

## It is good. That is the first thing to say, and it is not a courtesy.

Read cold, most of these twenty beats are publishable. Not "good for a
machine" — good. The register holds for a nineteenth-century dockside
hearing across four thousand words, the vocabulary is specific in the way
that only comes from somebody who knows what a sling of pig-iron is, and the
dialogue does the thing good courtroom fiction does, which is that everybody
argues past everybody else while advancing their own case.

Turn 3, Devereux Hallam, who has just been asked in public whose hand signed
a manifest twice:

> "Madam Chair. With respect to Mrs Sarr, there is no need for theatrical
> ultimatums over a commercial record. By all means, let the sheet be read
> into the proceedings. If an over-zealous clerk put his pen to paper at the
> river's edge without proper authority, no one in this hall has a greater
> concern to see it brought to light than I do."

That is a man conceding a clerk in order to keep a wharf, offered in the
grammar of helpfulness, and it is exactly what his card says he does
("volunteering an alternative subject", "the appearance of candour over
candour"). It is also — and I will come back to this — a sentence he could
only have written because the engine leaked him a whisper.

And turn 6, Tobin Slake, the rope-maker nobody summoned, who has been
authored to speak out of turn and refuse a summary:

> "That were written down proper, madam chair. That were where the white line
> sat, sure as water finds its level. And she took the river with her
> rubbing-strake under, any road."

Two sentences of agreement and then, uninvited, the thing nobody asked for.
That is a character, not a voice.

The pressure test I set was whether six interiors survive one room. Mostly
they do. Ilsabet Roon repeats herself verbatim under pressure because her
card says she does ("repeats a question verbatim rather than rephrasing
it"), and across nine beats she asks for a name in four different sentences
that are all the same sentence. Corin Ashe volunteers soundings nobody wants
— "three fathoms two off the cut wall", "twenty-seven inches", "four bells
past midnight" — which is precisely the tell of a man filling silence, and
his card says so. Maren Vaunt hits the table with the flat of her hand and
never raises her voice, as authored. The engine is not producing five voices
and colouring them; it is producing five people and letting them collide.

## Where it stopped being immersive, and on which sentence

**Turn 12.** Ottoline stands in the open doorway and shouts the guilty
clerk's name into the yard. The engine answers:

> "The call carried over the cobbles, meeting only the steady drumming of the
> rain and the dull wash of the river beyond the sheds."

The yard is empty. It has been empty the whole time. Since turn 0 the
scenario, the Director's own `world_pressure` row (`dockhands_outside`), a
`sensory_events` entry about "fists and shoulders slamming against the tall
yard doors", and Tobin Slake's own line ("There's fifty men standing in the
wet who ought to hear whose ink it were") have all asserted a crowd. There
has never been a body in that yard. The whole second half of my story — open
the doors, take it to the men, make it public — was played against a set
with nothing behind the flat. That is the single worst thing in the run, and
§3 traces exactly how the engine arrived at it (PM10, PM21): it *did* build
fourteen dockhands, and it built them in a duplicate copy of the yard that
nothing in the story can reach.

**Turn 8.** I haul the yard door open. Maren Vaunt, sitting eight feet away,
says:

> "Unbolt the doors, clear the benches, and let the rivermen take up their
> tools. This hearing is adjourned."

She is ordering somebody to open a door that is standing open with the rain
coming in over the sill, because her view of the beat said "The tall yard
doors is shut" and did not carry a single one of my three declared actions
(PM5). Two beats later she orders it again — "Master Slake, see those yard
doors thrown wide" — after Hallam has walked out through it. A reader stops
at that. It is the one failure that cannot be read as anything but the
machine showing.

**Turn 10-11, the climax.** Ottoline goes up to the gallery and names the
clerk over everybody's heads. What she sees below:

> "Maren Vaunt moves, too little of it to make out."
> "Tobin Slake moves, too little of it to make out."
> "Corin Ashe moves, too little of it to make out."
> "Down on the planks, Slake, Ashe, and Vaunt stirred beneath the tie-beam
> lamps, their outlines obscured in the gloom."

Beneath the tie-beam lamps, in a hall the same view describes in the next
sentence as lit by them. The most dramatic beat in the story is staged in a
fog, and the reason (PM1 → PM2) is a bearing that was dropped on turn 0
because a stair and a door both claimed the south wall. The gallery's own
authored description says it offers "a clear view down over the witness
floor". It never once did.

## Repetition

The prose does not repeat itself much; the *characters* do, and it is worse
because it reads as a model looping rather than a person insisting. Maren
Vaunt delivered her finding three times in four beats — turn 6 "The yard's
thirty-two stand cleared on Sarr's notch, Mr. Hallam", turn 7 the same clause
verbatim, turn 8 "The entry stands in ink: the yard's thirty-two are
cleared". The `repeat_correction` and the narrator's own recycled-content
guard both fired on turn 7 and the beat stood anyway. She also ordered the
room cleared on turns 8, 10, 13, 16, 18 and 20 without it ever happening,
which turns an authoritative character into a nagging one.

Physically, everyone is stuck to their furniture. Ilsabet's hands are on the
bench rail in nine of twenty beats. Corin's cap is in his hands in eleven.
Tobin's palm is flat on something in seven. These are authored gestures and
the first three uses are excellent; by the ninth the room reads like a
tableau with three animated hands.

## Voice

Five distinguishable voices, which is more than I expected, and one measured
bleed. Corin Ashe's card gives him the markers `sir`, `ma'am`, `on my word`;
Tobin Slake's give him `I were` and `any road`. On turn 14 Corin says:

> "The flood won't make till four bells past midnight **any road**, with this
> south-easter checking her off the spit."

That is Tobin's authored marker in the pilot's mouth, two beats after Tobin
had used it twice. The narrator does not sound like the characters — its
register is markedly more controlled than any of them, which is right — but
under load the *characters* drift toward whoever spoke most recently and
most distinctively.

The narrator's own tic is the adverbial appositive: "deliberate and
measured", "unhurried, procedural", "cold and measured", "measured and
benevolent", "curt and level", "steady and unyielding". The craft guard
caught four of these and the beat stood each time.

## Agency

My choices mattered more than I expected and the world refused me
interestingly at least twice. Turn 5, I asked the chair to swear an
unsummoned old man; she did it, and the whole case turned on it. Turn 16, I
asked two people to sign in a named order and both did — the engine handled
a two-addressee demand cleanly. Turn 18, I put my hand out for the wharf
slip and Corin gave it up in a whisper with his hand shaking on mine, which
is the best beat in the run.

But the refusals I *should* have been given were absorbed instead. I declared
pushing the clerks'-room door shut behind me; the interpret recorded the
intent in its own `movement.why` ("closing off the hall") and the barrier
never changed and nothing told me (PM13). Four times my declared physical
conduct simply did not appear in the prose (PM4) — on turn 7 I walked the
length of a hall and shouted through a door and the page contains none of it,
only Maren saying "Stand down from the doors, Mrs. Sarr" to a woman the
reader never saw go there. Being absorbed is worse than being refused,
because a refusal is a fact and an absorption is a hole.

## Surprise

Two things happened that I did not cause and both were earned. On turn 2
Tobin Slake pushed off the wall and walked two paces onto the floor
uninvited, which is the whole of his authored drive discharging itself, and
it broke the hearing open. On turn 13 the Director tried to give Corin Ashe a
line he had not declared, the character-speech-authority floor caught it, and
the line landed in Tobin's mouth instead — where it was better. The engine
was defending an invariant and improved the scene doing it.

Nothing arbitrary happened. Nothing happened at all from the yard, the tide,
the river, or the fourteen dockhands, and the absence of arbitrary events is
partly the absence of any event the player did not start.

## Pacing

Twenty beats cost 3,460 s of wall clock — an average of 173 s, with a worst
of 262 s (turn 6). At three minutes a beat this is not playable in the sense
of a session; it is playable in the sense of correspondence chess. And the
cost is not where the value is: turn 6's 262 s bought four spoken lines, of
which 216 s was model time and 61 s of that was three Director specialists
producing 1,300 characters between them (§2).

The beat that gave back least for its cost was turn 7 (145 s): I walked a
hall and shouted through a door, and the page shows neither.

## The uncanny — what a cheaper system could not do

Three things, and they are the reason this is worth fixing rather than
replacing.

**A lie was tracked as a lie by the people who knew better.** Corin Ashe
swore he was aboard until six. By turn 5 Tobin Slake's beat goal, read
straight out of `inspect_minds`, was *"Correct the pilot's lie about staying
aboard the Cormorant"*, and his model of Corin was *"Trying to place himself
entirely at the helm and ignorant of the extra slings to escape liability."*
Nobody told him that. He watched, he remembered, and he formed it. Over the
next four beats Corin's story eroded under him from "aboard until six" to
"three paces to the office hatch at twenty past five" to a whispered
confession — not because a plot said so, but because two minds with
incompatible memories were in one room.

**Two registers in one beat, correctly separated, in a room of five.** Turn
17 I said one thing to the hall and another thing to one man's ear. The
public line reached everybody; the private line reached Corin and *only*
Corin — Maren, Ilsabet, Tobin and Hallam received nothing, verified in every
view. That is the firewall doing the thing the firewall is for, under the
hardest social load I could build.

**A private room stayed private.** Turn 15, in the clerks' room with the
chair, a low line reached Maren and no one else, through a doorway the
ledger had (wrongly, PM13) left open — the sound field graded it correctly on
the merits.

---

# 2. The technical pass

## 2.1 Cost, per role, over 20 beats

Totals from the capture (`export_turn_debug`), 258 model calls:

| step | role | n | secs | system (chars) | payload (chars) | output (chars) |
|---|---|---|---|---|---|---|
| interaction_loop | character_mid | 62 | 793.6 | 3,253,198 | 3,433,271 | 395,442 |
| director_resolve | director_contact | 20 | 379.6 | 681,380 | 137,940 | 14,170 |
| director_resolve | director_objects | 17 | 273.7 | 444,498 | 143,727 | 10,673 |
| director_resolve | director_spatial | 20 | 256.0 | 660,180 | 246,627 | 21,942 |
| director_resolve | director | 24 | 243.0 | 972,805 | 907,650 | 190,774 |
| director_interpret | director | 33 | 201.7 | 540,924 | 339,844 | 90,290 |
| narrator | narrator | 21 | 183.7 | 807,114 | 530,892 | 17,319 |
| director_interpret | director_spatial | 14 | 182.9 | 462,126 | 135,782 | 3,763 |
| director_interpret | director_contact | 17 | 129.4 | 579,173 | 97,206 | 3,361 |
| director_resolve | director_body | 10 | 88.4 | 284,408 | 72,215 | 2,117 |
| reaction_loop | character_mid | 4 | 51.2 | 208,868 | 257,971 | 22,772 |
| director_interpret | director_social | 15 | 42.4 | 229,591 | 68,261 | 3,960 |
| director_interpret | director_objects | 7 | 32.2 | 177,452 | 45,588 | 1,113 |
| director_interpret | director_body | 8 | 24.8 | 252,736 | 43,091 | 952 |
| background_react | character_bg | 1 | 3.5 | 2,778 | 657 | 31 |

The five specialists together: **1,509 s across 128 calls for 62 KB of
output** — 44 % of all model time for 3.7 % of all output. `director_body` in
the interpret is the extreme: 31.6 KB of system prompt, 5.1 KB of payload,
**119 characters back on average**, across eight calls.

## 2.2 The biggest single waste

**`director_resolve`'s `interaction_rounds` and `character_declarations` are
the same content twice.** Measured on turn 3's resolve payload (36,533
chars):

```
interaction_rounds       13,537   [{"result": {"action": {"attempt": "Smoothly unlace my fingers and turn an unhurried, open gaze from Sarr towa…
character_declarations   11,046   [{"action": {"asserted_effects": [], "attempt": "Smoothly unlace my fingers and turn an unhurried, open gaze f…
```

24.6 KB of a 36.5 KB payload, and the two keys begin with the identical
string. This scales linearly with the number of characters who spoke, which
is exactly the axis this run was given: at four speakers it is 11 KB of pure
duplication per resolve, twenty times over. **Cut `character_declarations`
and let the resolve read the declaration out of `interaction_rounds`:
≈ 220 KB of payload across this run, ~30 % of every resolve call.**

## 2.3 Per role — what was sent, what came back, what I would cut

**`director` (interpret), 24.9 KB system / 13.2 KB payload / 6 s.** Payload
is 43 % `scene` (5.7 KB) and 15 % `present_characters` (2.0 KB, full
appearance prose for all five). Nine keys arrive empty every call
(`paradox`, `world_books`, `standing_intentions`, `pending`, `other_players`,
`engine_notices`, `due_authored_events`, `addressable_presences`,
`variant_seed`). **Misread:** on turns 1, 4, 6, 7, 8 and 14 it set
`needs_mapping: true` with `mapping_request: "Player action implies
entering/approaching a contained space"` for beats with `movement: null` —
laying boards on a table, walking two paces across one room. The field name
invites a yes; the class it wants is "the beat named a room the plan does not
hold". **Cut:** the empty keys (presence should mean something); send
`present_characters` as names and rooms, not appearance prose the composer
will render anyway.

**`director` (resolve), 39.6 KB system / 36.5 KB payload / 10 s.** Twenty
keys empty on every call — `unratified_claims`, `travel_in_flight`,
`standing_intentions`, `reaction_rounds`, `other_players_declarations`,
`notices`, `engine_notices`, `due_authored_events`, `dice_results_final`,
`crowds`, `couriers`, `character_material_effects`,
`character_contact_endings`, `carried_reports`,
`background_presence_knowledge`, `active_restraints`, `active_conditions`,
`active_awareness`, `paradox`, `variant_seed`. That is a majority of the key
count teaching the model that keys are furniture. **Cut:** omit an empty key.
Plus §2.2.

**`director_contact`, 34.1 KB system against 5–8 KB payload, 15–41 s per
call, ~870 chars out.** The worst instruction-to-work ratio in the engine and
the second-largest time sink. Its payload carries `worn_garments` (1.6 KB:
every garment on all six bodies) on every beat of a hearing in which nobody
touched a garment, plus eight always-empty keys. It also refused work four
times with a correct routing note that goes nowhere: *"placing tally boards
on table belongs to objects ledger"*, *"'manifest sheet' is not an indexed
entity; unindexed held item belongs to objects"* — a refusal with a
destination and no route (the registered refusal-without-routing class,
PB §6). **Cut:** send `worn_garments` only when the beat's own declarations
name a garment; make a specialist's refusal write to the named hand's channel
rather than to a warning.

**`director_spatial`, 33.0 KB system, 8.7–12.7 KB payload, up to 28.7 s for
176 characters of output.** Its payload is a whole rooms map for a beat whose
only spatial fact is one body moving one anchor within one room. The
registered scope class, measured again.

**`character_mid`, 52–53 KB system / 26–56 KB payload / 12 s, ×62.** By far
the largest consumer. Payload composition on turn 3: `memory` 9.8 KB,
`perception` 7.6 KB, `self` 6.2 KB — and inside `perception`, `observations`
(4.0 KB) and `view` (3.0 KB) are the same beat rendered twice, the view being
composed *from* the observations. **Cut one of them: ≈ 190 KB across this
run.** Payloads grew from 26 KB at turn 3 to 56 KB at turn 6 as memory
accumulated; extrapolated to a hundred beats this role alone is the story's
cost.

`perception.corridor_sight` is nonsense in this room and is sent every beat
to every character: `[{"along": [], "dir": "e", "distance": 1, "terminus":
"darkness", "vagueness": "just ahead"}]` — the clerks' room, a tiny lit
alcove through an open door, described as a corridor east terminating in
darkness. (PM17.)

**`narrator`, 38.4 KB system / 19–36 KB payload / 7–13 s.** The composed view
arrives three times: `present_scene` (2.7 KB, the player's outcome view),
`sensory_channels.hearing.this_beat` (3.4 KB, the same lines), and
`current_events` (3.0 KB, the same lines again with numbering), plus
`dialogue_lines` (1.1 KB) as tokens — a fourth copy of the quoted bodies.
**Misread, and the important one:** `current_events` numbers the player's
declared actions with *"NOT yet on the page — the player described attempting
it; you must render it happening"*, and on turn 7 the narrator rendered none
of the three (PM4). `player_declared.sequence` also carries the player's
speech element with a `volume` and **no text at all** — correct policy (the
narrator must not echo player dialogue) expressed as an empty object, which
reads to a model as a dropped field rather than a rule.

`overused_phrases` on turn 3 was `["bench ilsabet roon", "corin ashe froze",
"out on the"]` — word n-grams spanning sentence boundaries, containing proper
names. In a scene with six named bodies this channel increasingly asks the
narrator to stop naming the people in the room. (PM18.)

**`director_social`, 12.4 KB system / 2.0–2.6 KB payload / 2 s, 264 chars
out.** The cheapest hand and the one that owns crowds. It produced the run's
only crowd op and it was rejected (`unknown crowd op 'open'`, F62 recurring
on turn 0).

**`background_react`.** One call in twenty beats under `scene_life: off` with
`max_reactors` raised to its ceiling of 3 by a host dial — and it fired on
turn 11 only, twice, and both outputs were discarded (PM21). PE13's
measurement holds: the background layer is effectively silent.

**Writers' Room / Planner.** Now captured. Five asks: 107 s (14 calls, 8
steps, published), 77 s (refused with a question), 435 s F1, 160 s F1,
plus tool-only calls. Tool events still arrive with `tool` set and `args:
null`, `result_head: "None"` — the registered capture gap.

## 2.4 Warning volume, by class, over 20 beats

| n | stage | class |
|---|---|---|
| 15 | narrator | Quote attributed to wrong speaker (**all 15 false**, PM8) |
| 16 | director_resolve | Possible untracked physical restraint/duress (**all false**, PM9) |
| 36 | interaction_loop | `fused N spoken lines` / `move_correction` / `repeat_correction` |
| 10 | director_resolve | `player state: resolve restated …; the assertion yields` |
| 9 | director_resolve | Resolve reconciliation: prose asserts X, diff does not encode it |
| 6 | narrator | craft tell (4 adverb, 2 `registers` on the guild **register**) |
| 5 | narrator | Physical act from event_order may be missing in prose |

Two of these are pure noise at scale. The quote-attribution guard fired on
75 % of beats and was wrong every time; the restraint guard fired on six of
six bodies in a single beat. Both are literal matchers over free prose, both
scale with the number of names in a sentence, and CLAUDE.md forbids exactly
this shape. A warning at 100 % carries no information — the register's own
phrase for F14, now true of two more guards.

---

# 3. The bugs

Registered ids cited where a class recurs
(`docs/experiments/DEBUG_RUN_2026_09_05.md`, and the campaign-1 PLAY reports).

---

## PM1. A vertical edge is collided against the compass wall it names, so a stair and a doorway on the same bearing both lose their bearing

* **Stage of origin:** `world/spatial_orientation.normalize_scene_bearings`,
  final collision pass.
* **Live case, turn 0.** `director_establish` authored, correctly:
  `guild_hall → gallery {barrier: open, dir: "s", vertical: "up", name: "a
  narrow wooden stair"}` and `guild_hall → yard {barrier: closed_door, dir:
  "s", name: "the tall yard doors"}`. The collision pass groups a room's
  edges by `dir` alone, finds two on `s`, and drops `dir` from both — and
  from both reciprocals. The committed scene:
  `{"to": "gallery", "barrier": "open", "vertical": "up"}` and
  `{"to": "yard", "barrier": "closed_door"}`, neither with a bearing, while
  the anchors `hall_doors` and `gallery_stair` both still read `dir: "s"`.
* **Severity:** story-breaking (it is the cause of PM2).
* **Recurs:** adjacent to F67 (the layout lint embedding a vertical neighbour
  on the plane); this is the same confusion in the *normalizer*, and it
  subtracts data rather than mis-reporting it.
* **Fix.** The rule in engine vocabulary: *a way that goes up or down does
  not stand on a wall, so it cannot occupy one.* In the `by_bearing` loop,
  skip any edge carrying a normalized `vertical`. Test:
  `tests/test_spatial_bearings.py` — a room with one `dir: s` doorway and one
  `dir: s, vertical: up` stair keeps the doorway's bearing on both sides.

## PM2. A doorway view-cone is applied to a gallery over a hall, and no bearing exists under which the floor below can be seen

* **Stage of origin:** `world/spatial_senses._opening_view_cap`, spent by
  `visual_level_between`.
* **Live case, turns 10–11.** Player in `gallery`, cast in `guild_hall`
  (`light: lit`, `size: large`). Every act below rendered
  `act_shapes`: *"Maren Vaunt moves, too little of it to make out."* ×4 in
  one view, beside the sentence *"Lamps burning along the tie-beam provide
  yellow light across the room."* The gallery's own authored description is
  *"offering a clear view down over the witness floor."*
* Probed offline on the committed scene (no model calls):

  | scene | `visual_level_between(gallery→hall)` |
  |---|---|
  | as committed (no bearing on the stair edge) | `shapes` |
  | stair edge given a proper n/s bearing | **`none`** |
  | hall `size` forced to `medium` | `shapes` |

  The observer-side cap answers `full`; the target-side cap answers `shapes`.
  With no bearing it falls to the *"large+ caps at `shapes`"* branch; with a
  bearing, a body at `factors_table` (`dir: n`) is more than one sector off
  `opposite_bearing(n)` and caps to `none`. **There is no configuration in
  which a gallery shows the room it overlooks.**
* **Severity:** story-breaking. It fogged the climactic beat of the run.
* **Fix.** The cone models *a hole in a wall seen from the side*; a gallery,
  balcony, mezzanine or stairhead is an opening in the *ceiling* and the
  whole room is in its cone. The rule: *an opening you look down through
  shows the floor, not a slice of it* — return `full` from
  `_opening_view_cap` when the edge between the two rooms carries a
  `vertical`, before any bearing or size test. Test:
  `tests/test_spatial_senses.py` — a `small` gallery over a `large` room, an
  `open` edge with `vertical: up`, a body at any anchor below reads `full`.

## PM3. A room with no measurement collapses a long fixture to a point, so a whisper "no further than the head of the table" is delivered verbatim to the man at its far end

* **Stage of origin:** `director_establish` (no `extent`, no `shape`, no
  `parts` on any of four rooms); consequence in `director_interpret`'s
  concealment list and `perception_act`'s delivery.
* **Live case, turn 2.** Player declaration: *"she leaned in over the oak and
  dropped her voice so that it would go no further than the head of the
  table."* `dialogue_log`:
  `{volume: "whisper", intended_target: "Maren Vaunt", conceal_from: [3, 4, 6]}`
  — Ilsabet, Corin, Tobin. Not `[5]`. Devereux Hallam's `perception_act`
  view carried it whole:

  > *Ottoline Sarr says under their breath in a low, pointed voice: "Ask him
  > whose clerk was down on the wharf at five."*

  He acted on it the next beat, pre-emptively conceding "an over-zealous
  clerk" nobody had yet named. The delivery is *correct on the ledger*:
  Maren, Hallam and Ottoline all stand `at: factors_table`, so all three are
  "within arm's reach" of each other. The ledger is wrong because the hall
  has no extent and the long table the prose keeps describing — "at the head
  of the table", "at the table's far end", "looked down the length of the
  table" — is one anchor at one point.
* **Severity:** firewall-shaped. Nothing crossed a boundary the engine
  believed in; the boundary was never built.
* **Recurs:** F45 (the hands write the level word and never the measurement),
  third campaign running, and this is the first measured case where the
  missing measurement produces an information outcome rather than a spatial
  one. Note the contrast in §5: the Writers' Room *did* author
  `extent`/`shape`/`exposure` for all four rooms it planted.
* **Fix (owner decision on where).** Either the establish must measure a
  room it describes as long, or a fixture whose description names an extent
  (`"a long scarred trestle table set crosswise"`) must be able to carry
  `footprint: "run"` and seat bodies at different offsets along it. The
  cheapest correct floor: **a station at a `run`-footprint anchor is not
  automatically within reach of another station at the same anchor.** Test:
  two bodies at one `run` anchor, `offset` 0.1 and 0.9, in a room with an
  extent — `spatial_rel_between` must not answer "within arm's reach".

## PM4. The narrator is told in numbered items to render the player's declared conduct and no check verifies it did

* **Stage of origin:** `agents/common._check_narrator_fidelity`.
* **Live case, turn 7.** `narrator.payload.current_events` items 1–3:
  *"Ottoline Sarr did this (NOT yet on the page — the player described
  attempting it; you must render it happening): walks the length of the hall
  to the shut double doors"* / *"places both palms flat against the heavy oak
  doors"* / *"keeps her palms pressed flat against the wood, holding still."*
  The committed prose contains none of the three. The only warnings that
  fired were about repetition and an unplaced entity.
* Four occurrences in twenty beats (turns 7, 12, 19, 20). On turns 12, 19 and
  20 a *different* guard — *"Physical act from event_order may be missing in
  narrator prose"* — fired for the movement component only, which proves the
  check exists and is not applied to the player's own declaration.
* **Severity:** story-breaking. In a beat with five other speakers the
  player's own action is what gets crowded out.
* **Fix.** `_check_narrator_fidelity` already receives `event_order`; extend
  the same lexical-footprint test to the player's un-rendered declarations
  (the `current_events` items the payload marks). The rule: *what the page
  was told is not yet on it must end up on it.* Test:
  `tests/test_narrator_world_fidelity.py` — a beat with four character lines
  and one player action whose head verb and object appear nowhere in the
  prose must warn.

## PM5. A declared act reached two of five co-present observers, and the three who were not told acted as if it had not happened

* **Stage of origin:** `agents/perception.perception_act`, act-channel
  delivery. **I could not isolate the branch** and say so plainly; everything
  I read is below.
* **Live case, turn 8.** Player hauls the yard door open. Tobin Slake's act
  view:

  > *"Ottoline Sarr takes hold of the iron ring with both hands, levers her
  > shoulder beneath the bar, and heaves the right-hand leaf of the heavy
  > doors open."*

  Devereux Hallam's carries it too. **Maren Vaunt's, Ilsabet Roon's and Corin
  Ashe's carry only her speech** — no act sentence, and Maren's view also
  omits Ottoline from its presence list entirely while ending with her line.
  Maren's view additionally reads *"The tall yard doors is shut."* She then
  declared *"Unbolt the doors."*
* What I read: all five in one lit room; `sightlines.sees` lists everyone
  seeing everyone; `composer_ledger.standing` holds **no `act:` keys** for
  any observer on either turn, so this is not the standing dedupe; the same
  three observers were short on turn 7 and turn 8. The split does not follow
  station (Maren, Hallam and Tobin were all `at: factors_table`).
* **Severity:** story-breaking. It produced the run's most visible nonsense.
* **Fix.** Unknown until the branch is found; the test that would pin it is
  cheap and should exist regardless: five bodies in one lit room, one
  declares an overt unconcealed act, assert the act surface appears in all
  four other `perception_act` views.

## PM6. A delta suppression is rendered in the grammar of an exhaustive roll-call, so a body that merely stands still leaves the room

* **Stage of origin:** `agents/composer`, the presence-slot sentence, spent
  against `_composer_prev_ledger`'s `standing` keys.
* **Live case, turn 1.** Six bodies in the hall. Every observer's
  `perception_act` view names all five others. In `perception_outcome` of the
  same beat, Tobin Slake appears in **one** of six views. The player's:

  > *"Maren Vaunt is within arm's reach on your left, Ilsabet Roon is across
  > the room on your left, Corin Ashe is across the room on your left, **and**
  > Devereux Hallam is within arm's reach."*

  Four names, an `and` before the last, no Tobin — who is standing at the
  doors and is the only person who did nothing that beat. The narrator's
  prose then named exactly those four. Recurs turn 4 (Ilsabet dropped), turn
  7 (Tobin), turn 8 (four of six views short), turn 9 (the player's view
  names one body).
* **Severity:** story-breaking. The mechanism is defensible; the *grammar* is
  the defect — a closed conjunctive list cannot be read as a delta by either
  a reader or the narrator model.
* **Recurs:** the class PB4 addressed from the crowd side ("seven bodies
  present and delivered in neither form"), now measured for registered cast.
* **Fix.** Either render a suppressed body's presence at reduced cost (`"…
  and Tobin Slake, still by the doors"`) or drop the conjunction and render
  the delta as a delta (`"Maren Vaunt has moved within arm's reach."`). The
  rule: *a sentence that enumerates who is present must enumerate everyone
  present.* Test: two bodies present, one unchanged since the last view; the
  outcome view either names both or contains no enumerating presence
  sentence.

## PM7. The beat's budget counts rounds, not participants, so one reactor is silently dropped every beat and silence costs a round

* **Stage of origin:** `agents/loops.interaction_loop` against
  `story/scene.interaction_limits` (`max_micro_rounds: 4` at autonomy 50).
* **Live case.** Five reactors listed in `flow.reactors` on turns 1, 2, 3, 4,
  7, 8. Four rounds ran each time. Turn 1: Maren, Corin, Ilsabet, **Devereux
  Hallam with an empty sequence** — a round consumed by a character who
  declared nothing — and Tobin Slake never ran. Turn 2: Hallam dropped. Turn
  3: Tobin dropped. Nothing records who was dropped or why.
* **Severity:** wrong-but-recoverable, and it is the structural cap on how
  many people can be in a room.
* **Recurs:** not registered; the register's own note says the round
  structure under many participants is unmeasured.
* **Fix (owner decision).** Two separable parts. (a) An empty declaration
  should not consume a round — a character who declares nothing has not taken
  a turn of talk. (b) When `len(reactors) > max_micro_rounds`, say so: a
  warning naming who did not get a round, so a defect two beats later is
  attributable. Test: five reactors, one returning an empty sequence, at
  `max_micro_rounds: 4` — every reactor with something to say gets a round.

## PM8. A speaker-attribution guard resolves a quote's owner by nearest preceding *name* rather than grammatical subject

* **Stage of origin:** `agents/common._check_narrator_fidelity`.
* **Live case, turn 4.** Prose: *"Devereux Hallam kept his gloved hands
  resting open upon the oak and inclined his head deferentially toward Maren
  Vaunt. 'Mrs Sarr is entirely right to put the question, Madam Chair.'"*
  Warning: *"…spoken by Devereux Hallam, but the nearest preceding actor
  reference in the prose is Maren Vaunt."* The subject of the sentence is
  Devereux Hallam; Maren Vaunt is the object of *toward*.
* **15 false fires in 20 beats, 0 true.** Every one is the same shape: a
  speaker looks at, turns toward, or holds something belonging to another
  named body before speaking — which is what people do in a room of six. It
  fires more the more names a sentence carries, so it is a crowd amplifier.
* **Severity:** cosmetic, corrosive. A guard that is wrong every time trains
  its reader to ignore it, and this one shares a channel with real findings.
* **Fix.** The rule in engine vocabulary: *the owner of a quote is the
  subject of the sentence that introduces it, not the last name before it.*
  Cheapest correct version: exempt a name that appears as a possessive
  (`Vaunt's hand`) or after a preposition (`toward Maren Vaunt`) from being
  "the nearest actor reference". Better: stop guessing — the narrator is
  already handed `dialogue_lines` with `{{L1}}` tokens, so attribution is
  available structurally and the textual matcher is a fallback that should
  not warn. Test: the turn-4 sentence above must not warn.

## PM9. The restraint/duress guard is a keyword-near-a-name matcher and fired on six of six bodies in one beat

* **Stage of origin:** `director_resolve` guard over `resolved_event` and
  `dialogue_log`.
* **Live case, turn 20.** Six warnings, one per body including the player:
  *"Possible untracked physical restraint/duress detected for 'Ottoline Sarr'
  … but no matching state_diff.conditions entry was recorded this beat."*
  Nobody was restrained; the beat is three people signing a piece of paper.
  16 fires across three beats, all false. Trigger words in evidence:
  *"Stand aside"*, *"take it in the lane"*, *"under that iron"*, *"held
  fast"*.
* **Severity:** cosmetic (noise), and a direct CLAUDE.md violation — a word
  list read against free prose, whose failure rate rises with how well the
  model writes.
* **Fix.** State the class the engine owns instead: a restraint is a
  `conditions` entry or a `contact_op` with a restraining `relation`; if the
  Director did not write one, there is nothing to reconcile. If the guard is
  kept, scope it to the *actor* of a declared act, not to any name within N
  characters of a keyword. Test: the turn-20 resolve must produce zero
  restraint warnings.

## PM10. `generate_lived_location` ignores `required_rooms` and mints a parallel duplicate of every room named, in a second structure nothing can reach

* **Stage of origin:** `world/charter_runtime.generate_lived_location` →
  `charter_generate.close_plan`.
* **Live case, turn 8.** The Writers' Room drafted `request_location` with
  `required_rooms: [{name: "yard", connect_to: "wharf_apron"}, {name:
  "rope_walk", …}, {name: "wharf_apron", …}, {name: "north_basin_slip", …}]`
  — the live yard and the three rooms it had itself planted twenty minutes
  earlier. What landed:

  ```
  yard                                       live     (no region)
  rope_walk / wharf_apron / north_basin_slip planned  vaunts_yard_waterfront
  vaunts_yard_waterfront_2_yard              planned  vaunts_yard_waterfront_2
  vaunts_yard_waterfront_2_rope_walk         planned  vaunts_yard_waterfront_2
  vaunts_yard_waterfront_2_wharf_apron       planned  vaunts_yard_waterfront_2
  vaunts_yard_waterfront_2_north_basin_slip  planned  vaunts_yard_waterfront_2
  + bothy, bothy_2, gear_loft, mess_hall, tally_office, timber_shed, yard_gatehouse
  ```

  All 14 charter bodies were placed in the `_2` rooms. `publish_package`
  reported success with `{"summary": "Vaunt's Yard Waterfront", "rooms": [],
  "charters": []}` and no warning.
* The engine then diagnoses itself, in `background_react._engine_notes.
  decisions` on turn 11:

  > `{"kind": "charter_bridge", "verdict": "no_shared_ground", "reason": "9
  > charter places, 6 rooms in scope, no id in common -- no body can ever
  > surface here"}`

  That verdict is recorded as a decision and surfaced to no one.
* **Severity:** story-breaking. It is why the yard was empty for the second
  half of the story and why the run's whole crowd axis had nothing to test
  against.
* **Recurs:** not registered. Adjacent to F3/F63 (a frontier minting a room
  from a sentence) — the same failure to bind an authored name to an
  existing id, one layer up.
* **Fix.** `required_rooms` is a promise that these rooms exist; the closure
  must bind a required room by id rather than mint a slugged copy, and must
  refuse (not silently duplicate) when it cannot. And `no_shared_ground` is
  a fatal condition for an institution, not a decision note — raise it where
  the host can see it, at publish. Tests: (a) a `request_location` naming an
  existing live room id produces no new room with that name; (b) a published
  `request_location` whose charter places share no id with any live room
  warns.

## PM11. `inspect_contradictions` reports nothing when two structures hold same-named duplicate rooms

* **Stage of origin:** `structure_warnings` / the dangling-reference checks
  behind `inspect_contradictions`.
* **Live case, turn 9.** With the eleven `vaunts_yard_waterfront_2_*` rooms
  standing beside their originals, the tool answered `structure: []`,
  `dangling: []`, `layout: []` — while its own description advertises "a
  region whose live rooms are in pieces no path joins — a possible duplicate
  room". The only two rows it returned were about the charter's rank
  structure, and both were good.
* **Severity:** wrong-but-recoverable. It is the tool a host would use to
  find PM10 and it does not.
* **Recurs:** the F31/F32/PE8 family (the structure check handed the wrong
  room set), from the opposite direction — this one is handed everything and
  finds nothing.
* **Fix.** Add the check the description already promises: two rooms whose
  names normalize to the same slug in different structures, or a structure
  whose rooms are unreachable from every live room. Test: plant two
  structures with a room named "yard" each; `inspect_contradictions` must
  name it.

## PM12. The generated institution's names come from a name generator with no relation to the story, and the two residents the Room named were discarded

* **Stage of origin:** the naming law inside `close_plan` /
  `generate_lived_location`.
* **Live case.** The Room's own `request.featured_residents` were
  `Bram Hardesty` (Yard Gatekeeper) and `Kester Prowse` (Crane Master).
  Neither exists. The 14 bodies are named: *Wulvenan Pintlewason, Wultent
  Balebering, Branlean Dunner, Tadvenis Silting, Branferey Griplinging, Orlet
  Gallowdenridge, Hobbis Ropeterford, Wulsian Gallowterman, Gawleey Casking,
  Tadferard Balemaning, Malteney Brinewaman, Malvenkin Pintlemanson, Ortenan
  Gallowberridge, Wulley Silter.*
* The cast they were generated to stand beside is Ottoline Sarr, Maren Vaunt,
  Ilsabet Roon, Corin Ashe, Devereux Hallam, Tobin Slake. Nobody in this
  story can speak to a Wulvenan Pintlewason without the register breaking.
* **Severity:** story-breaking for immersion, and the harder half is the
  discarded `featured_residents` — a field whose whole purpose is "these
  people, by name" was ignored, which is PM10's failure in the person
  namespace.
* **Fix.** `featured_residents` must survive the closure verbatim. For the
  rest: seed the naming law from the story's *existing* names rather than a
  standalone morphology, or let the request carry a naming register. Test: a
  `request_location` with two `featured_residents` produces a charter
  containing both names.

## PM13. A player-declared door-close is recorded in the interpret's own movement record and never written to the barrier

* **Stage of origin:** `director_interpret` → the spatial hand.
* **Live case, turn 14.** Declaration: *"pushed the door to behind her with
  her heel until there was nothing but a band of lamplight from the hall
  lying on the boards between them."* `director_interpret.flow.movement`:
  `{"to_room": "clerks_room", "arrives": true, "why": "following the register
  into the side office **and closing off the hall**"}`. The committed scene,
  both sides: `{"to": "clerks_room", "barrier": "open_door"}` /
  `{"to": "guild_hall", "barrier": "open_door"}`. No `movement_refused`, no
  warning, no notice.
* Consequence two beats later: Maren Vaunt, in the clerks' room, is heard
  clearly by the hall and answers it, and the private room the player built
  is not private.
* **Severity:** story-breaking. The player changed the world's state and the
  world did not change, silently.
* **Recurs:** adjacent to F16/F23 (the passage as one object) but the
  opposite failure — not a one-sided write, no write at all.
* **Fix.** The rule: *a movement whose own reason names a barrier change is a
  barrier change.* Either the spatial hand must encode it or the movement
  backstop must refuse and say so; an unencoded declared change must never be
  silent. Test: a declared move carrying "closing the door behind her" writes
  `barrier: closed_door` on both sides, or files a warning.

## PM14. A contact's sensation phrase asserts a property of the thing touched without consulting what it is

* **Stage of origin:** `world/spatial_contacts._SENSATION_FORMS`.
* **Live case, turn 10.** Player grips a wooden gallery rail. Composed view:
  *"You feel something's surface against your hands: steady pressure, weight
  and **shared warmth**, continuous while the contact holds."* Turn 13, a
  hand on a leather book: *"Under Ottoline's palm, the thick leather cover
  held its heavy warmth."* Turn 18, hand to hand: *"his hand meeting her palm
  with sudden, trembling weight and shared warmth"* — where it is correct.
* The table is `{("settled", "either"): ("against it", "steady pressure,
  weight and shared warmth")}`, one phrase for every settled contact.
  *Shared* asserts the other party has warmth to share.
* **Severity:** cosmetic, and it breaks immersion every time a body touches
  furniture, which in a hearing is every beat.
* **Fix.** The engine already knows whether the target is a body: split the
  `settled` form on that, `"steady pressure and weight"` for anything else.
  This is a schema question, not a vocabulary one — no word list needed.
  Test: a settled contact whose target is a `fixture` renders without
  "warmth".

## PM15. The contact hand is shown the anchors of the room the body started in, so a contact made on arrival has no nameable target

* **Stage of origin:** `director_contact` payload assembly.
* **Live case, turn 10.** Player moves `guild_hall → gallery` and grips the
  rail. Warning: *"contact specialist: gallery rail not in entity_names or
  anchors"* — while `gallery.anchors.gallery_rail` exists and reads *"a
  waist-high oak railing overlooking the floor below."* The contact landed
  against an unnamed referent and the view rendered *"something's surface"*.
* **Severity:** wrong-but-recoverable.
* **Recurs:** PB10/PE12's class (a hand cannot name a target the scene
  already holds), which was resolved for the room a body is in — this is the
  room a body arrives in.
* **Fix.** Scope the `anchors` map by the same rule the register proposes for
  every hand: *the rooms a body could stand in by the end of this beat*, not
  the room it stood in at the start. Test: a beat with a declared move and a
  contact in the destination room includes the destination's anchors in the
  contact hand's payload.

## PM16. A container and its contents were folded into one entity on an alias overlap

* **Stage of origin:** `persist/commit` `_fold_duplicate_mints`, plus the
  station merge.
* **Live case, turn 1.** The Director minted `tally_boards` ("two notched
  wooden tally boards") and wrote `inventory_ops: [{op: "transfer",
  object_id: "tally_boards", from_id: "tally_satchel", to_id:
  "factors_table_entity"}]` — taking the boards out of the satchel and
  putting them on the table. The commit notice:

  > *"'tally_boards' is 'tally_satchel', which the scene already holds; the
  > mint was folded onto the record that exists rather than making a second
  > one."*

  `tally_satchel` acquired the aliases `["tally boards", "boards",
  "satchel"]`, the transfer had nowhere to land, and `scene.contained` is
  `{}` after twenty beats.
* The station consequence persisted to the end of the run:
  `tally_satchel: {at: "clerks_room_door", near: ["Ilsabet Roon"]}` — pinned
  to a doorway across the hall while `near` a body at the benches, and
  narrated on the factors' table for four beats.
* **Severity:** wrong-but-recoverable, and it silently disabled containment
  for the object the plot turns on. The notice is correct and lands in
  `commit.results.transit.notices`, which `read_stages` does not surface as a
  warning.
* **Fix.** The rule: *a thing named in an `inventory_ops` transfer whose
  `from_id` is the candidate it would fold into is its contents, not itself.*
  Refuse the fold when the same diff moves the mint out of the record it
  matched. Test: a diff minting X with a transfer `from_id: Y` does not fold
  X into Y.

## PM17. A tiny lit alcove off a lit hall is described to every mind as a corridor terminating in darkness

* **Stage of origin:** the `corridor_sight` builder feeding
  `character_mid.payload.perception`.
* **Live case, every beat.** `corridor_sight: [{"along": [], "dir": "e",
  "distance": 1, "terminus": "darkness", "vagueness": "just ahead"}]`. East
  of the hall is `clerks_room`: `size: tiny`, `light: dim`, `open_door`,
  described in the same payload's `view` as *"Dimly lit from the hall
  doorway."*
* **Severity:** cosmetic, but it is a nonsense fact sent to five minds
  sixty-two times, and "terminus: darkness, just ahead" invites a model to
  narrate a dark passage that does not exist.
* **Fix.** A one-hop sight to an adjacent named room is not a corridor and
  has no terminus; `dim` is not `darkness`. Emit `corridor_sight` only where
  the line of rooms is longer than the neighbour, and take the terminus word
  from the terminal room's own light. Test: a two-room scene with an
  `open_door` between them produces no `corridor_sight`.

## PM18. The anti-repetition channel feeds the narrator n-grams that span sentence boundaries and contain proper names

* **Stage of origin:** narrator payload assembly (`overused_phrases`).
* **Live case, turn 3.** `overused_phrases: ["bench ilsabet roon", "corin
  ashe froze", "out on the"]`. The first spans a sentence boundary
  (*"Behind the bench, Ilsabet Roon…"*); the third is a stopword trigram.
* **Severity:** cosmetic, and it worsens with cast size — with six named
  bodies the frequent n-grams are increasingly name-adjacent, so the channel
  asks the narrator to stop naming the people in the room. Two
  `Proper noun from view missing in narrator prose` warnings fired in this
  run, which is the other end of the same rope.
* **Fix.** Compute n-grams within a sentence and drop any containing a cast
  name or an alias. Test: prose containing "Behind the bench, Ilsabet Roon
  stood" twice produces no phrase containing "ilsabet".

## PM19. A resumed pipeline re-runs a deterministic stage and mints a fresh variant each time; a first-stage failure leaves a turn row with no steps

* **Stage of origin:** `agents/runtime.run_pipeline(from_key=…)`.
* **Live case, turn 5.** The beat failed at `director_interpret` on an HTTP
  402; the `turns` row existed with `player_input` set and **zero steps** —
  a turn in the history with an input and no output, which the next
  `run_beat` would have stepped past silently. Resuming from the last
  recorded step, once per 402, left:

  ```
  director_interpret     variants: [(57, active)]
  compile_world_context  variants: [(58, active)]
  perception_act         variants: 16 rows, 15 inactive
  ```

  `perception_act` is deterministic and its inputs never changed; fifteen
  byte-equivalent dead variants accumulated. Nothing else duplicated:
  the Writers' Room's four F1 retries produced **one** package, not four,
  which is a good result worth recording.
* **Severity:** cosmetic. Filed because the coordinator asked what the engine
  does with a partial result, and because the same `from_key` path is the
  UI's "rerun from here".
* **Fix.** A deterministic step re-entered with unchanged inputs should reuse
  its active variant. Test: `run_pipeline(from_key="perception_act")` twice
  on an unchanged turn produces one `perception_act` variant.
* **Also filed here:** an F1'd Writers' Room reply left a titled draft package
  (`plot:the_river_bailiff_s_salvage_docket:46830967ea`) with zero
  operations. Harmless, but it is state a failed call left behind.

## PM20. A JSON-parse refusal diagnoses a budget overrun for a failure whose text is the model's own reasoning

* **Stage of origin:** `charter_runtime.generate_lived_location`.
* **Live case, turn 8.**

  > *"the location generator returned 2270 characters of unparseable JSON
  > (Expecting value). If it ends mid-object the plan outran its 16000-token
  > budget -- ask for fewer required_rooms or featured_residents. Tail:
  > …shift crew 4 each. But they DO count, so you put 2 in populations. And
  > 1 + 2 + 2 + 3 + 4 = 12 in populations, plus 2 featured = 14 total
  > residents!"*

  The tail is a chain of thought, not truncated JSON. The remedy offered
  (shrink the request) cannot address it. On the retry the same call refused
  with a budget of **4000** tokens rather than 16000; the third attempt
  succeeded.
* **Severity:** wrong-but-recoverable. A host following the advice would
  shrink a request that was never too big.
* **Recurs:** the F1 family with content instead of an empty answer.
* **Fix.** Distinguish the two: a tail that does not parse *and* does not end
  mid-structure is a reasoning leak, and the remedy is a retry (which the
  call has no automatic path for), not a smaller request. Test: a stubbed
  generator returning prose produces a refusal that does not mention the
  token budget.

## PM21. The run's only crowd voice was produced by two model calls and discarded

* **Stage of origin:** `background_react`, downstream of PM10.
* **Live case, turn 11.** `director_resolve` gave a line to `Hobbis
  Ropeterford` — a charter body standing in `vaunts_yard_waterfront_2_yard`.
  Warnings: *"Routed 'Hobbis Ropeterford''s line to the background stage"*
  then *"Dropped 'Hobbis Ropeterford' from dialogue_order: no surviving
  dialogue_log line for this speaker."* The stage record:
  `{"fired": false, "selected": ["Hobbis Ropeterford"], "selected_why":
  {"Hobbis Ropeterford": ["routed", "channel:exempt"]}, "reactions": [],
  "mode": "background_react+background_react"}` with **two `character_bg`
  calls** (225 and 198 chars of output) and the `no_shared_ground` decision
  quoted in PM10.
* **Severity:** story-breaking as an outcome (the crowd's single line in
  twenty beats), though the proximate cause is PM10.
* **Fix.** Belongs with PM10; separately, the Director should not be offered
  as an addressable presence a body whose place shares no id with any room in
  scope — `no_shared_ground` is knowable before the line is written, not
  after it is deleted.

## PM22. A character-act-authority warning named the wrong character

* **Stage of origin:** the `director_resolve` undeclared-movement guard.
* **Live case, turn 16.** *"Character undeclared movement this beat
  (character-act authority): **Tobin Slake**: 'She turns the key twice with a
  harsh screech of tumblers, slides the iron key deep into her coat pocket,
  and turns squar…'"* The sentence is about Maren Vaunt; Tobin is at the
  doors with his palms on the frame.
* **Severity:** wrong-but-recoverable. A warning that names the wrong body
  sends its reader to the wrong sheet, which is the most expensive kind of
  wrong.
* **Fix.** Attribute by the subject the guard extracted, not by position in
  the resolved event. Test: a resolved event whose sentences name two bodies
  attributes each undeclared movement to the body that performed it.

## PM23. The objects the story turns on are never encoded, and four end the run at no anchor

* **Stage of origin:** `director_resolve` and the objects/contact hands.
* **Live case.** Nine `Resolve reconciliation: prose asserts X … but
  state_diff still does not encode it after self-repair` warnings, five of
  them in turn 20 alone: *"laid flat on bench surface and signed by Ottoline
  Sarr" (wharf_slip)*, *"takes quill from Ottoline Sarr's hand" (Ilsabet
  Roon)*, *"signed by Ilsabet Roon"*, *"takes quill from Ilsabet Roon's
  hand"*, *"marked with a thick cross by Tobin Slake"*. The document the
  entire story exists to produce is signed by three people in the prose and
  by nobody in the state. Two entities were minted unplaced (`guild_register`,
  `iron_wall_safe`, both warned — PA13's guard working). Final stations:
  `wharf_slip`, `guild_register`, `manifest_sheet`, `relief_draught` all
  `at: null`; `Devereux Hallam` `at: null` since turn 9; `Tobin Slake`
  `at: null` from turn 2 until turn 16.
* A related mint: `a_wool_cap_corin_ashe` became a scene entity, duplicating
  a garment that is authored on Corin's card and already lives in
  `scene.attire`.
* **Severity:** wrong-but-recoverable individually; story-breaking in
  aggregate, because the story's own artefact has no existence.
* **Fix.** The contact and objects hands each refused this work with a
  correct destination (*"unindexed held item belongs to objects"*, *"target
  wharf_slip is not an indexed entity"*) and no route. Give a specialist's
  refusal a channel to the named hand — the registered
  refusal-without-routing class, now measured nine times in one story.

## PM24. The narrator moved a body through a door the ledger kept her behind

* **Stage of origin:** narrator, on a character declaration the merge did not
  complete.
* **Live case, turn 13.** Prose: *"With a turn of her shoulder, Vaunt stepped
  through the low doorway into the clerks' room, the book clamped tight
  beneath her arm."* Warning: *"Character placed in wrong room: 'Maren Vaunt'
  is narrated in 'The Clerks' Room' but this beat's committed position is
  'The Guild Hall' and no movement occurred for them this beat."* The guard
  fired and nothing repaired; the reader now believes she left, and she
  leaves for real on the next beat.
* **Severity:** wrong-but-recoverable (a self-correcting instance, but the
  class is a body in two places).
* **Fix:** owner decision — either the guard should be able to withhold the
  sentence, or a character declaration that reaches a doorway should be
  resolved as a move rather than dropped.

## PM25. Small ones, stated once

* **Number agreement in an engine-owned view slot.** *"The tall yard doors is
  shut."* — in every observer's view of every beat while the doors were shut.
  `language_packs/en/cards/compositor.json`, the portal sentence: the label
  is authored plural and the copula is fixed singular.
* **`size` recomputed against its own measurement.** The hall read
  `size: "large"` with no extent. After a host World Browser PATCH of
  `extent: {w: 6, d: 14}` it reads `size: "huge"` — the same word the yard
  carries. 84 square paces is not huge. PD10's class, from the other
  direction: the derivation ran and disagreed with the measurement.
* **`conceal_from` is written in two spellings in one `dialogue_log`.** Turn
  17: the player's line carries `[2, 3, 5, 6]` (character ids), the character
  reply beside it carries `["Tobin Slake", "Ilsabet Roon", "Maren Vaunt"]`
  (display names). Every consumer must handle both.
* **The craft-tell list fired twice on the word "register"** — the guild
  *register*, a physical leather book carried under an arm through six beats.
  Exactly the case CLAUDE.md already records; still live.
* **Voice bleed.** Corin Ashe used `any road`, Tobin Slake's authored marker,
  on turn 14, two beats after Tobin used it twice.

---

# 4. Works — what behaved, with evidence

* **Two registers in one beat, in a room of five (turn 17).** A public line
  and a concealed line in one declaration: the public line reached all four
  others; the concealed line reached Corin Ashe and **only** Corin Ashe.
  Verified in all ten views of both perception passes. This is the axis's
  central question answered correctly.
* **A private conversation stayed private (turn 15).** A low line in the
  clerks' room reached Maren Vaunt and no one else, across an `open_door`.
* **A lie was tracked as a lie by the minds that knew better.** Tobin Slake's
  beat goal on turn 5, from `inspect_minds`: *"Correct the pilot's lie about
  staying aboard the Cormorant"*, with a ToM claim about Corin at 0.627
  confidence, formed from what he saw and never told to him.
* **The character-speech-authority floor caught a mis-attributed line (turn
  13)** — the Director tried to speak as Corin Ashe; the floor refused and
  the line landed with Tobin, where it was better.
* **The passage as one object.** A host `doorway_patch` on `guild_hall→yard`
  with `dir`, `offset`, `width` and `material` mirrored onto the yard side
  automatically (`dir: n`, same offset), and the player's door-opening on
  turn 8 changed `closed_door → open_door` on both sides.
* **Planned-fringe materialisation.** After the Room planted four rooms, the
  live `yard` acquired reciprocal edges to `rope_walk` and `wharf_apron`
  without a hand writing them.
* **Two-addressee demand (turn 16).** "Ilsabet. Tobin. Out loud, one after
  the other" — both answered, both in the same beat, neither dropped.
* **`sensory_events` as a one-beat emission.** The Director wrote
  `{kind: "sound", room: "guild_hall", level: "loud", detail: "a dry, sharp
  clap of a palm striking the oak table"}` — PA2's channel, working.
* **F1 retries did not duplicate work.** Four planner attempts, one package.
* **Card authoring.** Five sheets, `character_card_warnings` empty on all
  five, and every authored trade-off value, taboo and coping style is visible
  in conduct across twenty beats.
* **Unplaced-entity and orphan-mint warnings fired correctly** three times
  (PA13's guard).

---

# 5. The Writers' Room as co-author

**Five asks. Two published, one refused with a good question, two F1.**

**What it did well, and it is worth saying first: it authors better geometry
than the Director does.** Asked for the wharf beyond the doors, it returned
four rooms with `extent`, `shape`, `exposure`, bearings and frontiers —
`{"name": "The Rope-Walk", "extent": {"w": 6, "d": 24}, "shape":
"rectangle", "exposure": "sheltered", "adjacent": [{"bearing": "e", "to":
"yard"}, {"bearing": "n", "to": "north_basin_slip"}], "frontier": ["Rigging
Sheds"]}` — and it honoured both my constraints (somewhere out of sight of
the yard; the water reachable on foot) with reasons. `director_establish`,
given the same style of prose, produced four rooms with `extent: null` and
`shape: null`. That is a direct comparison on one story and it is not close.

**It took a pushback properly.** It offered two paths for placing the crowd;
I rejected both with an argument (moving the hands one room out would make
opening the door worthless) and gave my own. Its next draft was exactly my
version: gatekeeper on the yard cobbles, crane crew left at the North Basin,
and a `director_note` reading *"The gathering of dockhands and lightermen is
stationed directly on the wet cobbles of Vaunt's Yard facing the open guild
hall double doors, held back by gatekeeper Bram Hardesty."* It did not
re-litigate and it did not quietly keep its own plan.

**It refused something, correctly, and asked instead of guessing.** Told to
generate the yard's institution, it came back: the Charter Planner *"refused
to place the gatekeeper and the crowd of hands in the unzoned Yard without
clarification"*, because the live rooms `director_establish` minted belong to
no structure. That is a real seam between the engine's two world-builders and
it named it rather than working around it.

**It granted itself mandates from my words, legibly.** Two mandates, each
quoting the sentence that authorised it, with capability lists
(`plan_rooms`, `director_note`; then `create_people`, `plan_entity`,
`request_location`, `charter_ops`, `move_body`, `assign_post`). I could read
what I had agreed to.

**It cited.** Every reply carried `claims` with `cites` and a `proposal`
flag — *"Vaunt's Yard is an existing live ground of open cobbles connecting
to the Guild Hall through closed double doors" cites: [yard, guild_hall],
proposal: false*.

**What it could not do.**

1. **It could not put a person in the world.** Its one attempt produced
   PM10/PM12: a duplicate waterfront and fourteen bodies nobody can meet.
   The failure is downstream of the Room, but from the co-author's chair the
   Room told me it had populated the yard and the yard is empty.
2. **It could not cross the structure seam it correctly identified.** It
   offered to bind the yard into a structure "in a brief package draft" and
   the F1 killed the attempt; there is no host route for it either.
3. **Its reply is F1-prone under load.** Two of five asks ended
   `ReasoningBudgetExhausted` after four attempts — 435 s and 160 s of wall
   clock for nothing. Each retry re-runs the *whole* planner from the first
   tool call; the 435 s run re-entered `prepare_package` (a model call) on a
   retry.
4. **Its tool events are still blind.** Every `tool_call` came back with
   `args: null` and `result_head: "None"`, so I can see that it called
   `inspect_charters` and not what it asked or got.
5. **`hops` is null for every room in `inspect_rooms`, live rooms included** —
   PC10's class (a tool answering WHAT without WHY).

**Where it overstepped: it did not.** Nothing in five asks authored a mind, a
motive, or an attention. Its `director_note` describes positions and a
gatekeeper's function, never what anyone concludes. When I asked it to make
people it asked for leave first, and when I gave leave in words it recorded
the words. On this run the overstepping class the earlier campaigns
registered did not recur once.

**What I would improve.** (a) Let `prepare_package` retry a reasoning-leak
itself rather than refusing and handing back a wrong diagnosis (PM20).
(b) Make the planner's retry resumable from the last completed tool call —
435 s to produce nothing, twice, is the difference between a collaborator and
a lottery. (c) When a generated institution's places share no id with any
live room, that is a publish-time refusal, not a note in a decision log
(PM10). (d) `featured_residents` should be a promise, not a hint (PM12).

---

# 6. Host interventions (World Browser), and whether they survived

All three came after the beat that motivated them, and all three were things
I would actually reach for as a host.

1. **Turn 8.** `room_entity_create` + `room_entity_patch` on `guild_hall`:
   `hanging lamps`, `light_source: lit`, `light_height: full`, `steadiness:
   steady`. Motivation: the hall read `light: "lit"` with its own `notes`
   saying "Lamps burning along the tie-beam" and **no source entity existed**
   — nothing could be doused, carried or fail (F40/PA3's shape). Survived
   twelve subsequent commits unchanged; Ilsabet picked up a brass lamp on
   turn 19 as a separate object.
2. **Turn 12.** `doorway_patch` `guild_hall→yard` with `offset: 0.5`,
   `dir: "s"`, `width: 2`, `material: "oak"`, and `guild_hall→gallery` with
   `offset: 0.85`. Motivation: PM1 had left the hall's main doors with no
   bearing at all. Mirrored correctly onto the yard side; survived.
3. **Turn 12.** `room_patch` `guild_hall` `extent: {w: 6, d: 14}`,
   `shape: "rectangle"`, and `body_station_put` for Corin Ashe. Motivation:
   PM3. Survived; `size` recomputed to `huge` (PM25).

Also, twice, a host dial the run needed and I record as an intervention:
`background_config` set to `max_reactors: 3` (from the default 1) before the
opening turn, and `scene_life: "off" → "ambient"` after the doors opened on
turn 8. Neither changed the outcome: `background_react` fired once in twenty
beats, on the turn its subject was a body in an unreachable room.

---

# 7. What I would change first — three

1. **Bind a generated institution to the rooms it was asked for, and refuse
   loudly when it cannot** (PM10, PM12, PM21). This is the difference between
   a world with people in it and a world with a note saying people. The
   engine already computes the fatal condition — `"no charter place shares an
   id with any room in scope — no body can ever surface here"` — and files it
   where nobody looks. Make it a publish-time refusal, bind `required_rooms`
   by id, and keep `featured_residents` verbatim.

2. **Make an opening you look *down* through show the room below** (PM1 +
   PM2). Two small edits, one dependent: skip `vertical` edges in the bearing
   collision pass, and return `full` from `_opening_view_cap` for an edge that
   carries a `vertical` before any bearing or size test. Today there is no
   configuration of a gallery over a hall in which anyone can see anything,
   which quietly rules out every balcony, mezzanine, loft, stairhead and
   upper window in every story.

3. **Stop the two guards that are wrong every time, and add the one that is
   missing** (PM8, PM9, PM4). Fifteen false quote-attributions and sixteen
   false restraint alarms in twenty beats — both literal matchers over free
   prose, both amplified by cast size — while the check that would have
   caught the player's own action vanishing from the page four times does not
   exist. The narrator already receives structural attribution
   (`dialogue_lines` tokens) and the player's declared conduct already
   arrives numbered and flagged; both replacements are cheaper than what they
   replace.

---

**Turn table**

| idx | what I did (≤15 words) | outcome (≤15 words) | findings |
|---|---|---|---|
| 0 | opening (no input) | engine builds 4 rooms, 6 anchors, 3 doorways; no extent anywhere | PM1, PM3, F62 |
| 1 | lay two tallies before the chair, ask them entered | Vaunt takes them; Roon demands the notch read aloud | PM6, PM7, PM16 |
| 2 | name the discrepancy; whisper "ask him whose clerk" to the chair | whisper delivered verbatim to Hallam; Slake speaks unbidden | **PM3** |
| 3 | ask Hallam publicly whose hand signed twice | Hallam concedes "an over-zealous clerk"; four speakers | PM8 |
| 4 | put the hour to Corin Ashe on the floor | Corin lies; Slake contradicts him from the back | PM8 |
| 5 | speak over Hallam; demand Slake be sworn | Corin puts himself at Hallam's hatch; Slake takes the book | PM19 (402) |
| 6 | whisper to the widow; pass her the second board | she takes it; Vaunt enters the finding | PM8 |
| 7 | walk the hall, shout through the shut doors | none of it reaches the page | **PM4** |
| 8 | haul the yard door open | 3 of 5 never told; the chair orders it unbolted | **PM5** |
| 9 | call into the yard for whoever stood longest | nobody; Hallam leaves | PM21 |
| 10 | up the stair, call down over the rail | everyone below is "too little to make out" | **PM2**, PM14, PM15 |
| 11 | name Jenner Voake from the gallery | Roon and Slake take it up; a crowd voice is deleted | PM10, **PM21** |
| 12 | shout the name into the open yard | "meeting only the steady drumming of the rain" | **PM10** |
| 13 | hand on the register at the clerks' door | reaction loop; narrator moves Vaunt, ledger does not | PM24 |
| 14 | follow the book in, push the door to | door never closes; nothing says so | **PM13** |
| 15 | low words to the chair in the dark | reaches her alone; the safe swallows the book | PM23 |
| 16 | ask Roon and Slake to sign, in order | both agree, both in the same beat | PM22 |
| 17 | public defence of Ashe + private line to his ear | two registers, correctly separated | *works* |
| 18 | hand out for the wharf slip | Corin gives it up in a whisper | PM14, PM23 |
| 19 | hold the slip up to the lamplight | Roon brings the lamp; Vaunt bars the doors | PM4, PM9 |
| 20 | sign it, pass the quill | three names on the slip; nothing encoded | PM23, PM8, PM9 |

**Measurements.** 21 beats, 3,460 s wall clock (opening 51 s; mean 173 s;
worst 262 s on turn 6). 258 captured model calls. One beat lost to a shared
provider account. Warning classes and counts in §2.4. `export_bench.py scan`
run over every file written outside the scratch database: clean.
