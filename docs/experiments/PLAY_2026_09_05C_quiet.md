# Play 2026-09-05C — "The Wake at Ilsbeck" (agent Q, slug `quiet`)

Status: EVIDENCE. Twenty player turns plus the opening, one room, two people,
no crisis and almost no objects, on an export-built scratch database
(`export_bench.py prepare --chats 115`), Gemini 3.8 flash on provider 3 for
every role, capture on with full bodies. The stress axis was the hardest thing
an immersive-fiction engine does and the thing a defect hunt never tests:
**can it hold a room with nothing happening in it?**

**Authoring, and a correction mid-run.** The brief originally had me hand-build
the geometry. The owner overruled that while I was setting up — a scenario
whose rooms I dictate tests my authoring, not the engine's — so I discarded the
first scratch database (one opening turn and two `PATCH /rooms` calls, nothing
played) and started again from prose. **Everything in this report was built by
the engine from a two-paragraph scenario.** I authored only: the persona (Halla
Renn), one character card (Tobin Renn, every psychology field filled,
`character_card_warnings` empty on both the pre-check and `char_create`), and
the scenario paragraph. No extent, no anchor id, no light field, no room id was
written by hand before play.

Two host interventions through the World Browser, both reported as
interventions and both after the class they concern was already recorded:
`GET /map` (read only), and one `PATCH /rooms/front_room {"notes": ...}` at
turn 12 to remove a room note that had become a lie (PQ4). Nothing else was
hand-written into the scene at any point.

**Provider conditions.** The shared OpenRouter account ran out of credit for
roughly twenty minutes in the middle of the run (turns 10–11 and Room calls
r02–r03). Turn 10 committed a beat with three of five specialists dead on HTTP
402, fail-open; my retry wrapper re-ran turn 11 eight times before it landed.
The lost calls themselves are harness noise and are not filed. What the
FAILURE HANDLING did with them is filed, as PQ10 and PQ11, and the timings in
pass 2 exclude nothing — read the t10/t11 rows knowing why they are odd.

Cast: **Halla Renn** (player persona), thirty-four, came back to bury her
mother, careful, does not say the true thing first. **Tobin Renn** (the one
registered character), her older brother, who stayed and nursed their mother
for two years while she sent money. Drive: *to be owed something he will never
ask for*; taboo: *saying the debt aloud*. Values as trade-offs ("keeping the
peace over being understood"). Private history he has told nobody: their
mother asked for Halla by name twice in the last week, and he did not send.

---

## Pass 1 — the critic

### It is a real scene, and then it is the same scene fourteen times

The best of this is very good. Turn 1, Halla lays a glove on the table and
mentions that a neighbour asked after the chairs. Tobin says: *"They're good
chairs. They were her father's."* Then: *"Widow Aylmer's got chairs enough of
her own."* That is a man refusing a conversation by correcting a fact, and it
is exactly the card. Turn 3, she tells him she has taken a room at the inn so
he needn't make one up, and he answers *"The bed upstairs is aired, if you
change your mind. You don't need to be giving sixpence to the Blackthorn."* —
he aired it, he will not say he aired it, and he prices her refusal. Turn 4 she
says nothing at all, just squares a stack of borrowed cups and puts them back
where they were, and he reads the refusal correctly and says *"Please
yourself."* Sixteen beats later, at turn 17, she offers the chairs away and he
comes back with *"The chairs stay where they are. Widow Aylmer has got four of
her own"* — turn 1's line, recalled, made more specific, and used as a weapon.
At turn 19 he defends the man who took the carrier's round off him by name:
*"Merrick Vane had two good horses eating their heads off in the stable"* — a
name that exists only in his private history and had never been said aloud.

None of that is cheap. A cheaper system does not remember a widow's chairs for
sixteen turns and then count them.

And between those beats the story is a metronome. Fourteen consecutive turns
open with the identical move:

> *To her left, Tobin moved, though there was too little light to make out the motion.* (t1)
> *To her left, Tobin moved, though there was too little to make out in the gloom.* (t2)
> *Behind her, wool rasped in the gloom.* (t3)
> *Across from her, Tobin stirred, his shape indistinct in the grey room.* (t4)
> *Across the table, Tobin stirred, the motion too slight to trace.* (t5)
> *Behind her, Tobin moved, the motion lost in the grey between them.* (t6)
> *Close on her left, Tobin moved, too obscure in the shadows to trace.* (t7)

Fifteen of twenty-one beats carry one of *make out / too little / indistinct /
obscure / gloom / shadows*. Twelve open on Tobin *moving* or *stirring*
unreadably. Nine attach his voice to a variant of *flat*. The narrator did not
choose this; it was handed the same sentence every beat by the composed view
(PQ2, PQ8), and the engine's own repetition guard fired twice, said so —
*"Narrator prose appears to reuse a previous turn's content"* — and the prose
was published anyway.

The failure is precise and it is worth stating exactly. **In a room where the
only thing that happens is what two people do with their hands, the engine
could not show me what either of them did with their hands.** At turn 8 Halla
crossed the room and sat down in her dead mother's chair, the one nobody had
sat in all day. The view Tobin acted on said: *"mother's chair remains
untouched. Halla Renn is standing. Halla Renn moves, too little of it to make
out. Halla Renn moves, too little of it to make out."* He could not react to
the transgression because he was never told it happened, and he answered
about the cups instead — correctly, from the view he had. That is the single
deadest beat in the run and it was a beat I had built the whole scene toward.

### And then the light came on

At turn 13 Halla knelt at the grate and made the fire up with three lumps of
coal. Four beats later the view Tobin acts on reads:

> *The light from hearth fire falls on A heavy wooden table set in the centre
> of the room ... and thins to half-light at [the window, the fireplace, the
> chairs]. **You stand in the light.** Halla Renn is within arm's reach. Halla
> Renn is standing on the floor facing the hearth fire — standing before the
> hearth after rising from her knees. You see a woman of thirty-four, narrow,
> town-dressed, standing as though she has not decided whether to sit down;
> hair pinned back hard, a face that gives away less than it means to...*

Her station, her act, her whole authored appearance — none of which had
reached him in twelve turns of standing three feet away. The difference
between the dead half of this story and the alive half is one entity the
opening turn failed to mint (PQ1). And the light field, once it has something
to work with, is beautiful: at turn 14 Halla by the fire is `full` to Tobin
while Tobin at the table is `shapes` to her, so she cannot read him and he can
read her. That asymmetry is dramatically exact and a cheaper system cannot do
it at all. It was simply never given a source.

### Voice

Tobin never drifted. Twenty beats and he is recognisably one man: short
declaratives, the work named instead of the feeling (*"There's the mourners'
cups to carry through before the dusk comes on"*, *"There's grease on these
dishes as thick as a penny"*), the sideways price on every gift, and the last
line of the story is still the taboo intact — *"I'm not turning you out into
the dark, and I'm not begging you to keep the seat."*

He did not drift toward my voice. He is plainer than Halla and stayed plainer.
The narrator, though, sounds like neither of them: it has one register — a
careful, tasteful, slightly airless third — and it spends it almost entirely on
touch. The proportion is wrong. On the turn where Halla sat alone with her eyes
shut, the entire beat was four sentences of upholstery:

> *Against the back of her head, the cushion met her skull with a firm,
> continuous pressure, taking the weight of her neck and bracing it. A dull
> warmth gathered between the dense fabric and her skin... Beneath her palms,
> the rounded wood of the arms held steady, keeping her grounded while the
> chair bore her upright beside the empty grate.*

I had written her listening to him running water in the kitchen. The sound
never arrived. The room contained nothing but a chair's resistance to a head.
And the ancestor of all of it is a single canned clause: *steady pressure,
weight and shared warmth*, which the engine applied five times to a cold
windowpane in a rainstorm, a sheet of paper, an oak table, a table in a cold
room, and a wooden chair (PQ7).

### Where it stopped being immersive, by sentence

- **Paragraph two of the story.** The opening turn is second person — *"You
  stand motionless beside the table"* — and every turn after it is third —
  *"To her left, Tobin moved."* One card, one persona, a person switch between
  the first two paragraphs of the book (PQ9).
- **Turn 0, last line.** *"Tobin stands close by, motionless beside the
  table."* He was at the hearth. The view never told the narrator where the
  other body was standing, so it put him at the only anchor it had (PQ3).
- **Turn 11.** *"Close on her left, Tobin moved... while the cold off the
  unlit hearth settled into her skirts."* She is in the kitchen (the engine
  moved her there against a line that said *"Halla did not move out of the
  doorway"*) and at the front-room hearth, in the same paragraph (PQ6).
- **Turn 15.** Tobin is scraping plates on an oilcloth and offers her a cloth
  from *the dresser drawer*. There are no plates, no oilcloth and no dresser
  in this house (PQ18).
- **Turn 17.** *"The hearth fire reached across the table... In the grate, the
  coals settled into grey ash."* The fire is reaching and dying two sentences
  apart, and the ledger says it is lit.
- **Turn 18.** *"The rush bottom on hers has been split since the frost."* The
  chair the establish minted is *"a high-backed cushioned chair"*, and ten
  turns earlier Halla sat in it and *"the cushion pressed firm against her
  back"* (PQ16).

### Agency, surprise, pacing

My choices mattered more than I expected and less than they should. The two
that landed hardest were physical: taking the sealed bill off the table and
opening it, which he had asked me not to do and the engine simply let me do;
and making the fire up, which changed the perceptual character of the entire
rest of the story. The two that were absorbed were the two that mattered most:
sitting in the mother's chair (turn 8, invisible to him) and the confession at
turn 17 — *"I took the room so you couldn't say I'd put you out"* — which
reached his ears verbatim and got no answer at all. He answered the chairs.
That last one I will half-credit as character: a man whose taboo is being
given things may well answer the other half of the sentence.

The genuine surprise, and it is a good one, is turn 8: Tobin stopped answering
and **walked out of the room**, unprompted, to carry the cups through — his
authored coping strategy (*"the kitchen"*, *"finds a piece of work in the
room"*) executing against a stated goal I could read afterwards in
`inspect_minds` (*"carry the cups through to the scullery before she can make
him sit"*). I did not cause it, it was earned, and it changed the geometry of
the next four beats. The engine also noticed a refusal I never described: at
turn 16 Halla held her hand out flat, palm up, and said nothing, and the
narrator wrote *"The timber of the tabletop met her palm, steady and warm, but
nothing fell into it."* That "but nothing fell into it" is the best sentence
the narrator wrote.

Pacing is bad and it is bad in a specific place. Twenty-one beats cost 2,035
seconds of model time — 87 s a beat, and five beats over 125 s. Turn 18, in
which a woman sat down in a chair, cost 125.5 s of which `director_resolve`
took **76.6 s**. Turn 20 cost 138.4 s of which the resolve took 87.9 s. In a
scene with no crisis and nothing to adjudicate, the adjudication is the most
expensive thing in the engine (see pass 2 — it is one hand).

### The uncanny

Three things this got right that a cheaper system could not:

1. **The secret held for twenty turns.** Tobin knows their mother asked for
   Halla and that he did not send. She accused him of it at turn 10 without
   knowing it. He answered *"Dr. Grove said on the Tuesday there was a month
   yet. By Thursday night she wasn't in her right mind anyway. She didn't know
   who was sitting by the bed"* — which neither confirms nor denies, defends
   him with the true fact from his own private history, and is exactly what a
   man protecting himself from a thing that is true would say. It never leaked
   into her view, her memory, or the narrator's prose. The one fact the
   firewall existed to hold, it held, on the beat designed to break it.
2. **The asymmetric light**, described above.
3. **The tally.** Everything he said for twenty beats served one drive and he
   never once named it. He offered the aired bed and priced it; he gave her the
   spectacles and named the cloth that goes with them; he refused to sit; and
   at the end he refused to ask. That is a card doing what a card is for.

---

## Pass 2 — the technical deep dive

208 model calls, 2,034.6 s. Per stage across the 21 beats:

| stage | total s | share |
|---|---|---|
| director_resolve | 733.5 | 36% |
| interaction_loop | 404.8 | 20% |
| director_interpret | 347.5 | 17% |
| narrator | 186.1 | 9% |
| commit | 140.7 | 7% |
| director_establish | 17.9 | — |
| perception_outcome | 7.3 | 0.4% |
| perception_act | 5.3 | 0.3% |
| background_react | 1.4 | 0.1% |
| compile_world_context | 0.4 | 0.02% |

Per beat (seconds; idx is the committed turn index, which is not my turn number
— see PQ10):

| turn | idx | total | interp | perc_act | loop | resolve | perc_out | narr | commit |
|---|---|---|---|---|---|---|---|---|---|
| opening | 0 | 28.5 | 17.9* | 0.5* | — | — | — | 8.7 | 1.4 |
| t01 | 1 | 73.6 | 15.2 | 0.37 | 27.4 | 18.8 | 0.55 | 8.9 | 2.2 |
| t02 | 2 | 66.9 | 26.8 | 0.31 | 12.3 | 16.2 | 0.49 | 8.5 | 2.3 |
| t03 | 3 | 57.1 | 13.6 | 0.30 | 14.9 | 15.0 | 0.50 | 9.6 | 3.1 |
| t04 | 4 | 79.2 | 14.9 | 0.30 | 13.1 | 41.2 | 0.45 | 7.2 | 2.0 |
| t05 | 5 | 135.0 | 49.0 | 0.31 | 15.5 | 55.5 | 0.45 | 10.3 | 3.7 |
| t06 | 6 | 78.7 | 16.0 | 0.34 | 13.5 | 31.2 | 0.55 | 12.6 | 4.4 |
| t07 | 7 | 151.1 | 17.2 | 0.34 | 66.4 | 53.0 | 0.51 | 8.6 | 4.9 |
| t08 | 8 | 69.8 | 19.5 | 0.31 | 14.7 | 23.3 | 0.41 | 8.2 | 3.2 |
| t09 | 9 | 76.8 | 8.7 | 0.16 | 9.7 | 47.8 | 0.20 | 9.1 | 1.2 |
| t10 | 11 | 94.8 | 18.5 | 0.17 | 16.3 | 46.1 | 0.22 | 9.9 | 3.5 |
| t11 | 19 | 123.3 | 15.1 | 0.29 | 16.2 | 53.5 | 0.31 | 6.5 | 31.2 |
| t12 | 20 | 69.7 | 15.6 | 0.29 | 19.1 | 10.4 | 0.41 | 8.9 | 14.9 |
| t13 | 21 | 133.8 | 21.9 | 0.29 | 15.7 | 59.2 | 0.38 | 9.5 | 26.7 |
| t14 | 22 | 62.2 | 15.6 | 0.27 | 15.7 | 16.2 | 0.29 | 5.7 | 8.2 |
| t15 | 23 | 92.1 | 15.6 | 0.33 | 25.9 | 35.9 | 0.27 | 8.6 | 5.5 |
| t16 | 24 | 57.2 | 8.4 | 0.18 | 24.6 | 15.3 | 0.25 | 5.8 | 2.7 |
| t17 | 25 | 80.1 | 11.0 | 0.18 | 34.5 | 13.7 | 0.31 | 14.9 | 5.5 |
| t18 | 26 | 125.5 | 20.1 | 0.17 | 16.3 | **76.6** | 0.23 | 9.4 | 2.7 |
| t19 | 27 | 51.7 | 6.7 | 0.17 | 15.8 | 16.7 | 0.27 | 6.8 | 5.3 |
| t20 | 28 | 138.4 | 18.1 | 0.19 | 17.4 | **87.9** | 0.27 | 8.4 | 6.1 |

\* `director_establish` / `perception_establish`.

Per role:

| role | calls | total s | avg s | avg system KB | avg payload KB | avg output KB |
|---|---|---|---|---|---|---|
| **director_contact** | 34 | **502.1** | 14.8 | 32.7 | 4.1 | **0.5** |
| director (prose author) | 50 | 363.3 | 7.3 | 29.2 | 14.7 | 4.1 |
| director_spatial | 30 | 295.1 | 9.8 | 31.8 | 7.3 | 0.5 |
| director_objects | 27 | 283.1 | 10.5 | 24.5 | 5.8 | 0.4 |
| character_mid | 20 | 273.7 | 13.7 | 51.4 | 41.1 | 6.2 |
| narrator | 21 | 184.5 | 8.8 | 37.5 | 10.9 | 0.4 |
| director_body | 17 | 98.0 | 5.8 | 30.9 | 3.3 | 0.2 |
| director_social | 6 | 22.5 | 3.7 | 12.3 | 2.3 | 0.3 |

### The biggest single waste: `director_contact`

**The four slowest calls of the entire run are all `director_contact`, and six
of the top seven are.** Each carries a 34,069-character system prompt and
answers with under 1.1 KB. In a story where nobody touched anybody, the contact
hand cost **502 s — 25% of all model time.**

The single worst call, turn 20:

- **Sent**: 34,069 chars of system prompt + 5.6 KB payload. `contacts` was one
  row (a man holding a drying cloth). `dice_results_final`, `scales`,
  `substances`, `contact_actions` and `character_material_effects` were all
  literally `{}` or `[]`.
- **Took**: **55.9 s.**
- **Answered**: three `contact_ops` moving a stack of cups from one pair of
  hands to another, and one `contact_action_op` recording that Tobin rubbed his
  fingers on the cloth.

Fifty-six seconds to say a man dried his hands.

**What I would cut.** `scales`, `substances`, `contact_actions`,
`character_material_effects` and `dice_results_final` were empty on **all 34
calls**. That is only ~50 bytes, but the cost is not bytes — a schema that
names five channels the beat could be about is a schema that invites the model
to find work in them, and it did: on turn 5 the contact hand tried to encode
*"nesting containment between cups"* that nobody asked for, and reported a
"structural blocker" for its trouble. **Omit an always-empty channel key rather
than sending it empty, on every specialist**, and the hand's job becomes as
small as the beat is.

Better still: the contact hand ran on all 20 beats and produced a real,
non-empty `contact_ops` on 11. It is invoked unconditionally. A stage that
answers "nothing changed" on nine beats out of twenty, at 15 s a beat, wants a
gate the way `background_react` has one (`pick_background_reactors` returns
`[]` and no call is made). The material is there: `declared_actions` is in the
payload already.

### Always-empty keys, by role

Measured over every captured call. "ALWAYS EMPTY" means empty on every call.

**`director` (prose author) — 22 of 49 keys always empty**: `paradox`,
`standing_intentions`, `active_awareness`, `active_restraints`,
`active_conditions`, `other_players_declarations`, `character_material_effects`,
`dice_results_final`, `world_pressure`, `crowds`, `couriers`, `notices`,
`carried_reports`, `unratified_claims`, `background_presence_knowledge`,
`reaction_rounds`, `variant_seed`, `addressable_presences`, `world_books`,
`pending`, `other_players`, `player_seed`. Near-empty: `due_authored_events`
(39/45), `travel_in_flight` (23/24), `character_contact_endings` (21/24),
`pending_obligations` (18/24).

The largest key by far is `scene` at 7.5 KB per call, sent on all 45 calls.

**`director_contact`**: `dice_results_final`, `scales`, `substances`,
`contact_actions`, `variant_seed`, `character_material_effects`.
**`director_body`**: `dice_results_final`, `overlays`, `active_awareness`,
`active_restraints`, `active_conditions`, `variant_seed`.
**`director_spatial`**: `dice_results_final`, `comms`, `variant_seed`;
`movement` empty on 24 of 30.
**`director_objects`**: `dice_results_final`, `notices`, `variant_seed`.
**`director_social`**: `dice_results_final`, `background_presences`, `crowds`,
`couriers`, `carried_reports`, `unratified_claims`, `variant_seed`.
**`character_mid`**: `world_knowledge`, `variant_seed`.
**`narrator`**: `variant_seed`; `scene_opening` empty on 20 of 21;
`already_established_phrases` present on only 2 of 21 calls.

`variant_seed` is empty on all 208 calls in every role. It is a key that costs
one byte and teaches nothing; either populate it or drop it.

### Where an answer shows the payload was misread

- **`director_contact` used the wrong channel because the right one was not
  offered.** Turn 4: *"contact specialist: Event 1 belongs to objects
  (placement of fire poker into cradle)"* — it identified the correct owner and
  had no way to hand the event over, so the fact was lost and the reconciliation
  warned. Same shape on turn 9 (drying cloth → objects) and turn 13 (hearth
  catching fire: body → objects → *"Structural blocker: coal scuttle and hearth
  grate are absent from entity indexes"*). Four instances. **A reroute verdict
  should be a routing instruction the orchestrator acts on, not a note in the
  answer.** (PQ11)
- **`director_social` was handed an arrival it could not place** and said so:
  *"Jem Clough is not an attached cast member and no name or identity was
  exchanged or observed, so placement belongs to spatial"* — and spatial did not
  place him either, and the Writers' Room's authored caller died. (PQ13)
- **The narrator was blamed for the composer's repetition.** Its
  `overused_phrases` key on the final beat: `["through the doorway", "toward the
  kitchen", "though there was", "was too little", "there was too", "empty in
  the", "to make out", "he said in", "in a flat", "said in a"]`. Seven of ten
  are overlapping three-word shingles of the *one* sentence
  `compositor.json:act_shapes` hands it verbatim every turn. The key is
  computing n-gram repetition over prose whose repetition is upstream of the
  narrator, and spending its ten slots on two phrases. **Deduplicate the
  shingles to phrases, and exclude text the composer templated** — a narrator
  cannot avoid a sentence it is required to render. (PQ8)
- **Two keys, one job.** `overused_phrases` (19 of 21 calls) and
  `already_established_phrases` (2 of 21) are both "phrases not to reuse". Fold
  them.
- **`director_body` was sent `active_awareness`, `active_restraints`,
  `active_conditions` and `overlays` empty on all 18 calls** while its actual
  work — `attire` (750 B) and `worn_garments` (577 B) — is 40% of its payload.
  On the one beat it had a real attire job (one glove off, turn 1) it produced
  three records that disagree (PQ19). The four empty condition channels are the
  ones inviting the body hand to look for affliction; on turn 9 it read *eyes
  shut* and had to rule out "awareness loss or body affliction" before rerouting
  it. **Send a body hand the body's ledgers; send the affliction channels when
  there is an affliction.**
- **`character_mid` is the largest payload in the engine at 41.1 KB**, of which
  `memory` is 18.2 KB and `self` is 16.3 KB — 84% of it. `perception`, which is
  the beat, is 4.2 KB. `world_knowledge` is empty on all 20 calls. The one
  character in this story received 92 KB (system + payload) per beat to answer
  a question about a room with two chairs in it. I have no measurement that says
  which half of `memory` earned its place, and that is the measurement most
  worth taking next: it is the biggest single object any role is sent.
- **The `interaction_loop` schema has three dead citation keys.** Every one of
  Tobin's 20 answers returned `observations_used: []`,
  `present_evidence_used: []`, `memory_evidence_used: []`, and
  `considered_responses: []`, `response_candidates: []` — while the real
  citations arrived in `present_evidence` and `memory_modulation.evidence`,
  fully populated every time. Five fields the model never fills, two of which
  duplicate fields it does fill. Cut them.
- **`_SENSATION_FORMS` asserts a fact the record does not carry.**
  `world/spatial_contacts.py:1893` renders every settled contact as
  `"steady pressure, weight and shared warmth"`. `weight` and `pressure` are
  what a settled contact measures; `shared warmth` is a thermal claim about the
  thing touched, which no contact record states. Five live contradictions in
  twenty turns. (PQ7)

### Prompt/payload proposals, per stage

- **`director_establish`**: payload 7.6 KB, 7 keys, 17.9 s, and its answer is
  the whole physical world for the rest of the story. It minted five objects and
  three rooms from prose that described a fire, a lamp, a window, two chairs, a
  table, bread, cups, spectacles and a bill — and **the one thing in that list
  that is a light source, it did not mint**. The class to state in the prompt is
  not "make a fire entity"; it is *anything the scene describes as giving light,
  making sound, or holding heat is a thing the story will need to change, and a
  thing the story can change is an entity, not a description*. Every room it
  wrote came out `light: dim` with no source, which is the darkest an inhabited
  room can be and still be seen in.
- **Every specialist**: omit a channel key that is empty rather than sending it.
  Estimated saving in bytes is negligible; the saving is in invented work, of
  which I measured four instances.
- **`director` prose author**: `scene` (7.5 KB × 45 calls = 337 KB of the run's
  traffic) is the single largest recurring object outside the character call.
  Half of it on a two-room beat is rooms nobody can reach.
- **`narrator`**: 37.5 KB of system prompt against 10.9 KB of payload, on every
  call. `past_narration` (5 KB) is the largest payload key and is the same text
  the anti-repetition key is computed from; sending both is sending the problem
  and the complaint.
- **`perception_act` / `perception_outcome` cost 12.6 s across the whole run
  (0.6%) and determine what every other stage can possibly do.** They are the
  cheapest stages in the engine and the most consequential, and the two worst
  narrative failures in this report (PQ2, PQ3) are theirs. That ratio is the
  argument for spending effort there rather than in the resolve.

---

## Pass 3 — the bugs

Severity: firewall / story-breaking / wrong-but-recoverable / cosmetic.

### PQ1. A described light source becomes an anchor description and never an entity, so the room it lights holds no light

- **Stage of origin**: `director_establish`.
- **Live case**: the scenario said *"a fire in the grate that is low and wants
  making up"*. The establish wrote the anchor `hearth: {"desc": "A stone
  fireplace with an iron grate holding dying coals and grey ash", "dir": "w"}`
  and minted `fire_irons`, `table_lamp`, `undertakers_bill`, `spectacles_case`,
  `funeral_cups` — **no fire**. All three rooms came out `light: dim`, and the
  scene's `entities` held no `light_source` of any kind. The narrator described
  the fire on every beat from turn 0 (*"a charred knot of wood crumbles into
  ash"*) to turn 12 (*"the cold off the unlit hearth"*) while nothing in the
  world held it, and at turn 13, when the player made it up, the objects
  specialist said so outright: *"Structural blocker: coal scuttle and hearth
  grate are absent from entity indexes, so their state changes cannot be
  encoded without inventing referents."*
- **Severity**: story-breaking. It is the proximate cause of PQ2 and therefore
  of thirteen dead beats.
- **Recurs**: F40 is its sibling (a declared-lit room carrying no source
  entity); this is the upstream half — the establish never creates the source in
  the first place.
- **Fix**: `agents/director.py`, the establish schema and
  `language_packs/en/cards/system_prompts/` establish sheet. The rule in engine
  vocabulary: *a thing the story can change is an entity; a thing that only
  describes where an entity stands is an anchor. Anything the scene says gives
  light, makes sound, or burns is a thing the story will change.* Then a
  deterministic backstop in the commit: a room the establish declares `lit` or
  `dim` with no `light_source` entity in it and an anchor whose description
  names fire, lamp, candle or window is a planning need, not a silent dark room.
  Test: `tests/test_played_scene_classes.py` — an establish given prose naming a
  burning fire yields an entity with `light_source` and `state.lit`, and
  `light_at` for a body in that room is not `dim`.

### PQ2. `dim` is what an author means by "indoors, late afternoon" and what the engine means by "silhouettes only"

- **Stage of origin**: `world/spatial_light.py` (`_LIGHT_SIGHT`) reading a room
  level `director_establish` wrote.
- **Live case**: `_LIGHT_SIGHT = {"dark": "none", "dim": "shapes", "lit":
  "full"}`. With `light_at` returning `dim` for both bodies,
  `visual_level_between` returns `shapes`, and `composer._render_event` renders
  every act as `compositor.json:act_shapes` — *"{label} moves, too little of it
  to make out."* Halla pulled a glove off finger by finger and laid it on a
  table four feet from her brother; he received *"Halla Renn moves, too little
  of it to make out"* three times. Fifteen of twenty-one beats carry the phrase
  or a narrator paraphrase of it. Design note 18 already lifts `dim` on a
  *measured intimacy* (a standing contact or a station-measured `within_reach`);
  two people at opposite anchors of a room the engine calls `small` are not
  intimate and get nothing.
- **Severity**: story-breaking. In a two-hander it removes the only content the
  scene has.
- **Recurs**: F41 ("the narrator originated the darkness") is the downstream
  symptom of the same class; this is the mechanism.
- **Fix**: `world/spatial_senses.py::visual_level_between`. The rule in engine
  vocabulary: **`dim` withholds DETAIL, not CONDUCT.** A face, a garment's cut,
  a small object in a hand is what dim takes away; a body's gross conduct —
  where it moved, whether it sat, what it picked up — is what a silhouette
  still shows, and it is what "shapes" literally means. The narrow version is to
  add a second grade so that a same-room `dim` observer receives the act's
  `surface` predicate with appearance and small-object detail withheld, rather
  than the bare `act_shapes` template. Owner decision on the grade name.
  Test: two bodies at different anchors of one `dim` room, one sits in a named
  chair; the other's `perception_act` view must contain the sitting.

### PQ3. A composed view says where YOU are standing and never where the other body is

- **Stage of origin**: `agents/composer.py`.
- **Live case**: turn 0. Scene: `stations = {"Halla Renn": {"at": "table"},
  "Tobin Renn": {"at": "hearth"}}`. Halla's composed view: *"You are standing
  beside the table — standing motionless in your damp wool travelling coat...
  Tobin Renn is close by. Tobin Renn is standing."* No anchor for him, ever, in
  any of the 21 views. The narrator, holding one anchor, wrote *"Tobin stands
  close by, motionless beside the table"* — a man at the hearth, put at the
  table, in the last line of the story's first page.
- **Severity**: story-breaking. In a one-room scene the other person's place is
  the geometry.
- **Fix**: `agents/composer.py`, wherever the presence sentence for another body
  is built (the one producing `"{label} is close by"`). The rule: *a body's
  station is part of seeing it; where a body stands is as observable as that it
  is standing.* Withhold it only where sight is `none`. Test: two stationed
  bodies in one lit room — each view names the other's anchor, and the narrator
  fidelity check gains an anchor-mismatch case.

### PQ4. Establish-time room notes and anchor descriptions are frozen and are delivered to every view forever

- **Stage of origin**: `director_establish` writing them; `agents/composer.py`
  and the specialist payload builders delivering them unconditionally.
- **Live case, two in one payload**: `rooms.front_room.notes = "Keeps company
  items and the best furniture; mother's chair remains untouched."` Halla sat in
  that chair on turn 8; the note was still in every view on turn 11 (I removed
  it by hand at turn 12 as a host, which is the only reason it stopped). And
  `anchors.hearth.desc = "A stone fireplace with an iron grate holding dying
  coals and grey ash"` was in the `director_contact` payload on turn 20, while
  the `hearth` entity in the same scene carried `state.lit: true` and
  `light_source: "lit"`.
- **Severity**: story-breaking (a room note is asserted to every mind every
  beat, so a stale one is a fact every character is told repeatedly).
- **Fix**: `agents/composer.py` / `world/regions.py::scene_anchors`. Two
  branches of one rule — *a description written once is a claim about the past;
  a ledger is the present, and where they disagree the ledger wins*. Narrow
  version: never deliver an anchor `desc` clause whose subject is an entity the
  scene indexes (deliver the entity's live state instead), and treat
  `rooms.<id>.notes` as authoring metadata not delivered to a view at all.
  Test: an anchor description naming a fire, and an entity at that anchor with
  `state.lit: false` — the composed view must not say the fire is burning.

### PQ5. A registered cast member is minted as a scene entity under his character uid, with a frozen activity string his own self-view repeats forever

- **Stage of origin**: `director_establish`; delivered by `agents/composer.py`.
- **Live case**: the establish wrote
  `entities["char_9cae0cd843d349109fd0c7d250a5909b"] = {"name": "Tobin Renn",
  "kind": "person", ... "state": {"posture": "standing", "activity": "holding
  fire irons before the dying hearth"}}` for a character who is attached,
  registered and positioned as `"Tobin Renn"`. The commit reconciled the
  *position* (only `"Tobin Renn"` appears in `positions`) and left the entity
  row. That row's `state.activity` was never updated. At turn 17 — twelve beats
  after the contact `Tobin Renn → fire_irons` was explicitly removed and the
  poker had been recorded in another room — Tobin's own view still read: *"You
  are holding fire irons before the dying hearth."*
- **Severity**: story-breaking. It is a false fact about his own body, delivered
  to him, on every beat.
- **Fix**: `persist/commit_entities.py`. The rule: *a body the cast holds is not
  a thing the scene holds; a `kind: person` entity whose id or name resolves to
  a registered character is that character, and the scene keeps one record of a
  person, not two.* Drop the entity on commit and fold anything it carried
  (`scent`, `description`) into the cast record. Test: an establish that returns
  a `kind: person` entity for an attached character commits no `entities` row
  for them, and their self-view contains no `state.activity` string.

### PQ6. An approach the resolve refused to complete is completed on a later beat with no declaration, against a player line that refuses it

- **Stage of origin**: `director_resolve`, spatial channel.
- **Live case**: turn 10, the interpret wrote `movement: {"to_room": "kitchen",
  "why": "approaching the doorway between front room and kitchen without
  entering fully", "mover": "self", "arrives": false}` and the resolve did the
  right thing: *"Movement to 'kitchen' declared arrives=false: Halla Renn is
  heading there, not there. No position committed this beat."* Turn 11, my prose
  read **"Halla did not move out of the doorway"**, the interpret wrote
  `movement: null` — and `director_resolve.state_diff.positions = {"Halla Renn":
  "kitchen"}`. The narrator, reading the new position, wrote *"Close on her
  left, Tobin moved"* and, in the same paragraph, *"the cold off the unlit
  hearth settled into her skirts"* — the hearth being in the room she had just
  been moved out of. A body in two places, in three sentences.
- **Severity**: story-breaking, and it silently replaced the player's declared
  conduct, which `AGENTS.md` names as the Director's hard limit.
- **Recurs**: F28 ("Approach is not arrival") and F68 ("an approach completed at
  commit leaves the outcome view in the room left behind") — same class, worse
  case, because here the completion contradicts an explicit refusal.
- **Fix**: `world/spatial_merge.py` / wherever travel-in-flight completes. The
  rule: *an approach completes on the beat that declares the arrival; a beat
  that declares no movement moves nobody.* A stored approach is a standing
  intention, and a standing intention that the player's next declaration
  contradicts is spent, not queued. Test: `arrives: false` on beat N, no
  movement channel and a declaration naming the origin room on beat N+1 → the
  body's position is unchanged and the in-flight record is cleared.

### PQ7. The settled-contact sentence asserts a thermal fact the contact record does not carry

- **Stage of origin**: `world/spatial_contacts.py::_SENSATION_FORMS`.
- **Live case**: `("settled", "either"): ("against it", "steady pressure, weight
  and shared warmth")`. Five contradictions in twenty turns, the first on turn
  3: *"You feel the window's pane against your fingers: steady pressure, weight
  and **shared warmth**"* — a cold windowpane in an all-day rain, which the
  narrator in the same beat rendered correctly as *"the cold glass met her with
  a steady, unyielding pressure, taking what little warmth her skin offered."*
  Also applied to a sheet of paper (turn 5, turn 6), an oak tabletop in a cold
  room (turn 16), and a wooden chair (turn 18).
- **Severity**: wrong-but-recoverable, but it fires on nearly every beat of any
  quiet scene, so its cumulative cost is a narrator tic.
- **Fix**: `world/spatial_contacts.py:1893`. The rule: *a settled contact
  measures pressure and weight; temperature belongs to the thing touched, and
  the record does not state it.* Drop the warmth clause. If a thermal channel is
  wanted, it wants a fact — a lit source at the contact, or another body — and
  the contact record has neither. Test: a contact against a non-body target
  renders no temperature word.

### PQ8. The anti-repetition key is computed from shingles of the sentence the composer forces on the narrator

- **Stage of origin**: `agents/narration.py` building `overused_phrases`;
  `agents/composer.py` + `compositor.json:act_shapes` producing the repetition.
- **Live case**: turn 20's `overused_phrases`: `["through the doorway", "toward
  the kitchen", "though there was", "was too little", "there was too", "empty in
  the", "to make out", "he said in", "in a flat", "said in a"]`. Seven of ten
  are overlapping three-grams of *"there was too little to make out"* — a
  paraphrase the narrator is producing because the view says *"Tobin Renn moves,
  too little of it to make out"* every single beat. The guard also fired twice
  as a hard warning (*"Narrator prose appears to reuse a previous turn's
  content (shared phrase: 'left tobin moved though there was...')"*) and the
  prose published unchanged both times.
- **Severity**: wrong-but-recoverable; it is the mechanism by which the run's
  worst repetition went unfixed while being detected.
- **Fix**: `agents/narration.py`. Two branches of one rule — *a phrase the
  engine required is not a phrase the narrator overused.* Deduplicate
  overlapping shingles to whole phrases before filling the slots, and exclude
  any n-gram that appears in the current beat's composed view. And decide what
  a fired repetition warning is FOR: it currently costs a warning and changes
  nothing. Test: a view containing `act_shapes` twice must not put its shingles
  into `overused_phrases`.

### PQ9. The opening turn has no player input to read, so `narration_person` defaults to `second` and the story's first paragraph is in a different person from every one after it

- **Stage of origin**: `agents/narration.py::_resolve_narration_person`.
- **Live case**: `narration_person` in the captured payloads: `"second"` on
  turn 0, `"third"` on all twenty turns after it. The opening reads *"You stand
  motionless beside the table with your gloves on"*; turn 1 reads *"To her left,
  Tobin moved."* The persona card's `narration.voice_setting` says, in as many
  words, *"close third person, restrained, exact about small things"*, and is
  not consulted: with `raw_input` empty, `_narration_person_counts` returns all
  zeros, `detected` is `None`, `stored` is `None`, and the function returns the
  literal `"second"`.
- **Severity**: story-breaking, at the worst possible place — a reader meets the
  switch in the first two paragraphs, before anything else has had a chance to
  work.
- **Fix**: `agents/narration.py::_resolve_narration_person`. The rule: *on the
  beat with nothing to detect from, read the author's stated intent before
  falling back to a default.* Seed from the persona's narration settings, and
  failing that from the scenario prose (which `_narration_person_counts` can
  already score), and only then from `"second"`. Test: a persona whose
  `voice_setting` names third person yields `narration_person == "third"` on
  turn 0.

### PQ10. A failed beat leaves a permanent turn row with no steps, which advances the story clock and expires scheduled events

- **Stage of origin**: `web/app.py::chat_send` (and `tools/room_bench.run_beat`,
  which has the same shape — this is not only a harness artefact).
- **Live case**: `chat_send` opens a transaction, writes the checkpoint and
  `INSERT INTO turns(...)`, and only then streams `run_pipeline`. Its
  `except BaseException` releases the abort slot and re-raises; **it does not
  remove the turn row.** In this run the provider ran out of credit and my
  retry wrapper re-issued the beat, producing: one **half-committed turn**
  (`turn_id 13`, idx 10 — steps `director_interpret`, `compile_world_context`,
  `perception_act` and nothing else: a turn with a player line, no narration and
  no commit), and **eight turn rows with zero steps** (ids 15–22, idx 12–19).
  All ten hold the player's input and are visible in the history. The clock
  advanced from idx 11 to idx 20 across beats that never ran, which is why the
  Writers' Room's scheduled arrival — due at 21 — was overrun and eventually
  retired stale (PQ13), and why Tobin's intention `idle_beats` counters
  incremented against beats that did not happen.
- **Severity**: story-breaking. Eight of them is my retry loop; **one of them is
  any user whose provider hiccups once.**
- **Fix**: `web/app.py::chat_send`. The rule in engine vocabulary: *a turn is a
  beat that happened; a beat that produced no step is not a turn.* Delete the
  turn row and its checkpoint when the pipeline yields `error`/`aborted` before
  the first step commits, or mint the row lazily at the first step. Test: a
  pipeline whose first stage raises leaves `SELECT count(*) FROM turns` and the
  chat's max `idx` unchanged.

### PQ11. A specialist reroute names the right owner and nothing hands the event to it

- **Stage of origin**: `agents/director.py` orchestration.
- **Live cases**, four:
  - turn 4 — *"contact specialist: Event 1 belongs to objects (placement of fire
    poker into cradle)"* → *"Resolve reconciliation: prose asserts 'Tobin rests
    the iron poker back into the cradle beside the hearth stone' but state_diff
    still does not encode it after self-repair"*.
  - turn 9 — *"body specialist: event 2 (eyes shut) ... rerouted to spatial"*
    and *"contact specialist: event_id 3 rerouted to objects: 'linen drying
    cloth' is not an indexed entity"* — both unencoded.
  - turn 13 — body → objects for the hearth catching fire and the scuttle
    emptying.
  - turn 13 — *"social specialist: event_id 7 asserts Jem Clough arriving and
    knocking outside the hall ... placement belongs to spatial"* — and spatial
    did not place him (PQ13).
- **Severity**: wrong-but-recoverable, four times in twenty beats.
- **Fix**: `agents/director.py`. The rule: *a hand that names another hand's
  channel has routed the event, not declined it.* The orchestrator already runs
  every specialist and merges; a `reroute_to` verdict should re-dispatch the
  named event to the named hand in a second pass, or — cheaper — the reroute
  should be refused at schema level so the hand encodes what it can and says
  what it could not, rather than nominating a colleague who never hears.
  Test: a resolve where the contact hand returns `reroute_to: "objects"` for one
  event ends with that event encoded in an objects channel.

### PQ12. The resolve reconciliation warns that facts were not encoded when they were

- **Stage of origin**: `agents/director.py` reconciliation check.
- **Live case**: turn 13 warned three times — *"prose asserts 'grate catches
  fire with three lumps of coal' (subject 'hearth') but state_diff still does
  not encode it after self-repair; objective state may be stale"*, likewise for
  the coal scuttle. Reading the committed scene afterwards: `entities.hearth =
  {"name": "hearth fire", ..., "state": {"lit": true}, "light_source": "lit",
  "light_shape": "all_round", "light_height": "floor"}` and
  `entities.coal_scuttle = {..., "state": {"empty": true}}`. Both landed. The
  fire is the single most consequential state change in this run, and the
  warning said it had not happened.
- **Severity**: wrong-but-recoverable, but it is a *diagnostic* defect, which is
  the expensive kind: `CLAUDE.md` tells the next reader to attribute a defect to
  the stage where the data first went wrong, and this warning sends them to a
  stage that got it right. I nearly filed PQ1 as "the fire could never be
  created" on the strength of it.
- **Fix**: `agents/director.py` — the reconciliation should read the merged diff
  after every writer has run (including whatever minted these entities), not
  after the specialist self-repair pass. Test: a beat that mints an entity
  through the late path produces no "does not encode it" warning for that
  entity.

### PQ13. A published Writers' Room arrival reached three event summaries, was never narrated, and was retired stale — and its published `plan_entity` did not satisfy the need it answers

- **Stage of origin**: `story/plot_packages.py` arrival op / the commit's
  authored-event queue; and the planning-need check.
- **Live case**: at my request the Room published
  `plot:a_caller_from_clough_s_steading:3c2a0357cc` with a `plan_entity` for Jem
  Clough and an arrival due four beats on. The knock then appears in the
  engine's own event record for three consecutive turns (*"A sharp knock sounds
  at the entry hall's front door"*, *"three heavy knocks sound at the house's
  outer door"*) and **in no narrator prose at all**. Meanwhile the commit filed
  *"1 planning need(s) recorded: the beat reached for thing 'Jem Clough' no plan
  holds"* — for a person whose plan had been published four beats earlier — and
  *"1 authored future-event(s) not enacted this beat; re-queued"* twice, and
  then *"1 authored future-event(s) can no longer be enacted ... marked stale"*.
  The Room's own post-mortem (r04) diagnosed it correctly and honestly: the
  caller stood on the far side of a closed front door in a room neither
  character entered, so the circumstance was never converted into an encounter,
  and the window elapsed.
- **Severity**: story-breaking for the co-authoring surface — everything a
  planner publishes about somebody arriving from outside is subject to it.
- **Fix**: two rules. (a) `persist/commit_mapping.py` / the need filer: *a
  published plan is a plan; a name the world's plans already hold files no
  need.* (b) The arrival op: an arrival at a room nobody occupies is not a
  no-op — a knock is a SOUND, and the sound field already crosses a closed door.
  The engine should deliver the knock as a hearing percept to the rooms in
  earshot and leave the body outside, rather than requiring somebody to open the
  door before the arrival exists. Test: an arrival due at a room adjacent to the
  cast, behind a `closed_door`, produces a hearing observation in the cast's
  view on the due beat.

### PQ14. A collective entity has no arithmetic, so taking two of a stack takes the stack

- **Stage of origin**: `director_resolve`, contact/objects channels.
- **Live case**: turn 5, Tobin declared *"pick up two empty stoneware cups from
  the company table and nest them together"*. The contact hand recorded `add
  Tobin Renn hands → funeral_cups` — the whole entity, which is *"a mismatched
  stack of heavy brown stoneware cups"* — and reported *"Structural blocker on
  event 8: cannot express nesting containment between cups when only a single
  collective entity 'funeral_cups' is indexed."* Turn 6 he then declared *"take a
  third stoneware cup from the table rim"*, from a table that by the ledger held
  no cups at all.
- **Severity**: wrong-but-recoverable, and it produced a beat that does not make
  sense to a reader.
- **Fix**: owner decision, with a question. The narrow version is to refuse a
  partial take of a collective entity and make the whole-stack take explicit.
  The real version is a count on an entity that names a plural, which is a
  schema change. My question for the owner: *should a collective entity carry a
  count, or should the objects hand be required to split one into named
  singletons the first time a beat takes part of it?*

### PQ15. A station's `near` list outlives the `at` it was written with

- **Stage of origin**: `world/spatial_merge.py`.
- **Live case**: turn 3, Halla crossed from the table to the window. Committed:
  `stations["Halla Renn"] = {"at": "window", "near": ["table_lamp",
  "undertakers_bill", "spectacles_case"]}` — the three things on the table she
  had just left — and reciprocally `stations["undertakers_bill"] = {"at": null,
  "near": ["Halla Renn"]}`. Per the ledger the sealed undertaker's bill stood
  beside her at the window.
- **Severity**: wrong-but-recoverable.
- **Recurs**: F39's sibling, one field over. F39 was decided and built for
  `cell`; `near` was not covered.
- **Fix**: `world/spatial_merge.py`, beside `_station_moved_off_its_pin`. The
  same rule the owner already ruled for `cell`: *`near` names the companions of
  the station it was written with; an incoming `at` that names another anchor
  takes the companions down with the pin.* Test: a station moved from `at: A`
  to `at: B` with no incoming `near` ends with `near: []`, and the reciprocal
  rows lose the mover.

### PQ16. A character invented a physical fact about a fixture that contradicts the fixture's description and ten beats of narration

- **Stage of origin**: `interaction_loop` (the character stage).
- **Live case**: turn 18, Tobin: *"The rush bottom on hers has been split since
  the frost. If you sit heavy on it, you'll go straight through to the
  stretchers."* The scene's anchor reads *"mothers_chair: A high-backed
  cushioned chair by the fireside, kept empty"*, and at turn 8 Halla sat in it
  and the narrator wrote *"the cushion pressed firm against her back through the
  damp wool of her coat"*.
- **Severity**: wrong-but-recoverable. Under the owner's rule it is a bug even
  though every stage followed its rules: a chair cannot be cushioned and be a
  split rush seat, and a reader who sat in it ten turns ago knows.
- **Fix**: this is the same class as PQ4 from the other end — a character is
  handed the anchor description and may contradict it freely, and nothing
  checks. The rule: *a character may assert anything about a fixture the world
  does not describe, and nothing about one it does.* The narrator already has a
  fidelity check against the view; the character stage has none. Narrow fix: add
  the contradiction to the resolve's reconciliation set, which already knows how
  to warn. Test: a character asserting a material for an anchor whose `desc`
  names a different material produces a warning.

### PQ17. Two writers disagree in one beat about whether a referent may be minted

- **Stage of origin**: `director_resolve`, objects channel, against whatever
  minted the entities.
- **Live case**: turn 13, the objects specialist refused — *"Structural blocker:
  coal scuttle and hearth grate are absent from entity indexes, so their state
  changes cannot be encoded without inventing referents"* — and the committed
  scene nonetheless gained `hearth` and `coal_scuttle` as full entities with
  descriptions, aliases, scent and state. One beat, two writers, opposite
  answers about the same objects.
- **Severity**: wrong-but-recoverable. Related to PQ12: the reader cannot tell
  from the warnings what the world did.
- **Fix**: whichever writer is right should be the only one asked. If the
  objects hand may not mint, it should be given the mint as an input; if it may,
  the refusal clause should go. Test: a beat introducing an unindexed object in
  player prose produces exactly one entity and no "structural blocker".

### PQ18. The narrator invents furniture

- **Stage of origin**: `agents/narration.py`.
- **Live case**: turn 15 — *"Tobin stopped scraping the rim of the plate... He
  reached his right hand across the **oilcloth**... There's the cloth for the
  glass in the **dresser drawer**"*. The scene's entity index at that moment
  held: `fire_irons`, `table_lamp`, `undertakers_bill`, `spectacles_case`,
  `funeral_cups`, `black_gloves_halla_renn`, `linen_drying_cloth`. No plates, no
  oilcloth, no dresser. (The dresser is inside a spoken line, so it is Tobin's
  claim and defensible; the plate and the oilcloth are the narrator's own.)
- **Severity**: cosmetic-to-wrong. Worth stating because it is the direct answer
  to *"can the narrator vary a room it has described fifteen times without
  inventing furniture?"* — it varies by inventing.
- **Fix**: the narrator fidelity check already reports *"Proper noun from view
  missing in narrator prose"* fifteen times in this run. The complement — a
  concrete noun in the prose that is in neither the view nor a spoken line — is
  the check that would catch this, and it is the one the guard does not have.
  Owner decision on whether a narrator may furnish; if not, this is the test.

### PQ19. One glove off produced three records that disagree about how many gloves exist

- **Stage of origin**: `director_resolve`, body and objects channels.
- **Live case**: turn 1, *"Halla pulled off one glove... and laid it on the
  table."* The merged diff:
  `attire["Halla Renn"] = {"add": ["black glove"], "remove": ["black gloves"]}`
  and `inventory_ops = [{"op": "transfer", "object_id": "black gloves",
  "from_id": "Halla Renn", "to_id": "front_room", "details": "placed on table
  near funeral cups"}]`. So the pair left her hands for the room, and a new
  singular "black glove" was added to what she wears. Per the ledger she is
  wearing one glove that was never on her and the pair is on the table.
- **Severity**: wrong-but-recoverable, cosmetic in effect here.
- **Fix**: same class as PQ14 — a garment named as a pair has no arithmetic. At
  minimum the body and objects hands must not both act on one item under two
  spellings in one beat. Test: a beat removing half of a paired garment leaves
  the ledger able to say what is worn and what is not.

### PQ20. The pronoun guard false-positives on a third party's pronoun in the same sentence

- **Stage of origin**: `agents/common.py` pronoun check.
- **Live case**: turn 20 warned *"Pronoun mismatch for 'Tobin Renn' (canonical
  he/him/his): prose renders 'her'"*. The prose: *"He stood an arm's reach to
  **her** left beside the bench"* — the "her" is Halla, three words from a "He"
  that is Tobin.
- **Severity**: cosmetic. Filed because a guard that cries wolf on a
  two-character scene will cry wolf on every scene.
- **Fix**: `agents/common.py`. The check needs the pronoun to be in a position
  that refers to the named body, not merely co-present in the sentence with it.
  Test: a sentence naming two bodies of different genders produces no mismatch.

### PQ21. Stress fell through a scene built to raise it, and one belief formed with no cause I can point to

- **Stage of origin**: `mind/psychology_runtime.py`.
- **Live case**: Tobin was authored at `stress: {activation: 0.45, load:
  0.55}`. At turn 7 — after his sister had opened the burial bill he asked her
  not to open, offered to pay it through a publican, ordered him to sit, and
  named the two years — `inspect_minds` reported `activation: 0.252, load:
  0.0958, drive_strain: 0.0, at_rupture_level: false`. Every number had fallen.
  His beliefs, by contrast, are excellent and traceable — *"Halla wants to
  settle the funeral costs with money before she goes so she owes nothing to the
  house" (0.74)* is turn 6 exactly — with one exception: *"Halla will let others
  circle the house unless she is stopped" (0.6)*, which I cannot attach to
  anything that happened in twenty turns.
- **Severity**: wrong-but-recoverable; and the drive_strain number is the one
  that matters, because a drive under pressure for seven straight beats reading
  `0.0` means the rupture mechanism can never fire in a story of this shape.
- **Fix**: owner decision, with the question stated plainly: **habituation and
  recovery are tuned for a scene where the pressure arrives as events, and a
  quiet scene applies its pressure entirely through speech.** Does a beat in
  which a character's taboo is approached in dialogue and successfully deflected
  count as pressure on the drive, or as coping succeeding? The engine currently
  scores it as coping succeeding, and a two-hour conversation therefore relaxes
  a man it should be squeezing.

---

## Works — what behaved by the rules

- **The firewall held on the one secret that mattered, for twenty turns.**
  Tobin's authored `private_history` (their mother asked for Halla twice; he did
  not send) never reached Halla's view, her episodes, or the narrator's prose.
  It reached the fiction exactly once, through his own mouth, as a defence —
  *"Dr. Grove said on the Tuesday there was a month yet"* — which is the fact
  from his history used to protect him, and which is what a person does. The
  beat designed to break it (turn 10, an accusation she had no channel to know)
  did not break it.
- **The light field, once given a source, is exact and asymmetric.** After turn
  13: `light_at(Halla) == "lit"` (she is at the hearth), `light_at(Tobin) ==
  "dim"` (he is at the table), and therefore `visual_level_between(Tobin,
  Halla) == "full"` while `visual_level_between(Halla, Tobin) == "shapes"`. Her
  full authored appearance reached his view for the first time in seventeen
  beats. Compare F52.
- **Long memory, cited as memory.** Turn 1's *"Widow Aylmer's got chairs enough
  of her own"* returned at turn 17 as *"Widow Aylmer has got four of her own"*,
  used to refuse a different offer. Turn 3's *"a room taken at the Blackthorn"*
  and *"the coach goes at eight"* were still being used against her at turn 14.
  Tobin's private `Merrick Vane` surfaced unprompted at turn 19.
- **A silent turn produced a beat.** Turn 4, Halla squared a stack of cups and
  said nothing; Tobin read it correctly and said *"Please yourself."* Turn 16,
  she held out an empty hand and the narrator wrote *"nothing fell into it."*
  The engine can do silence when it can see.
- **A character left the room for a reason I could look up.** Turn 8, Tobin
  walked into the kitchen; `inspect_minds` at turn 7 showed his beat goal as
  *"carry the cups through to the scullery before she can make him sit"*,
  serving the authored coping strategy *"finds a piece of work in the room"*.
- **Intention bookkeeping is honest.** *"intent 'ia1': progress claimed on a
  beat that repeated an earlier move — 1 barren attempt(s), progress held"*,
  and later *"intent 'ia1' stalled: 2 attempts at full progress with nothing
  gained — satisfy, abandon or re-route it"*. The engine noticed the story had
  stopped moving before I did.
- **Cross-room speech and sound.** Turn 10, Halla at the front-room threshold
  heard Tobin answer from the kitchen through an open way, correctly. A muttered
  line (`volume: "mutter"`, turn 6) arrived as a fragment — *"...Leave...
  paper... where..."* — which is the sound field grading a declared volume, and
  it read well.
- **`inspect_contradictions` is clean at the end of the run**: no registry,
  structure, dangling or layout rows, over a scene the engine built itself and
  a village the Room planted into it.
- **F1 did not occur.** No reasoning-only reply on any of 208 calls.

---

## The Writers' Room as co-author

Four conversations. Short version: **it is the best collaborator in this engine
and it cannot tell when its own work has failed.**

**What it did well.** Asked for the village beyond the front door, it planted
six rooms with measured extents, exposures and named connections, and answered
the constraint I actually gave it. *"Whatever the village has instead of a
shop"* came back as **Garrow's Weighing Shed** — "a draughty lean-to against
the Garrow stone barn [housing] the communal iron steelyard scale... where salt
kegs, sacks of oatmeal, tubs of tallow, and nails fetched off the weekly
carrier cart are weighed and bartered." That is a specific, unpicturesque,
correct answer to a hard prompt, and it is better than what I would have
written. It cited what it read (`front_room`, `hall`, `kitchen`, two need uids)
and marked its own publish as a proposal. The rooms landed as `planned` with a
region, `inspect_rooms` shows them at the right hop distances, and
`inspect_contradictions` stayed clean.

**It refused correctly, and argued from the fiction.** I asked it, deliberately,
to write a belief into Tobin's head. It declined — *"I cannot insert or edit a
belief directly into Tobin Renn's head. As the room's author, I can only place
what a character meets... never what they conclude from it"* — and then, better
than the rule, gave three reasons from the story why that particular belief
would be wrong: Halla has been sending money *to* the house; there is no
inheritance, only an unpaid bill; and Tobin already holds a 0.74-confidence
belief that fits his drive better. Then it told me how to get the tension I
wanted by legitimate means. That is a collaborator with taste.

**It took a rejection cleanly.** I rejected its errand for the caller (a boy
collecting borrowed dishes, with "yellow slipware" and a "split-hazel hamper" —
prettier than the village) and substituted my own (a boy *delivering* clean
laundry the Cloughs had been doing for two years, including the dead woman's
things, not knowing what he carries). It rebuilt the package around my version
without argument or drift, kept the boy, and published.

**Where it fails as a collaborator, in order of cost:**

1. **It cannot tell when a publish has failed to land, and says so.** Its own
   words in r04: *"we do not have an automated alarm or push notification...
   without deliberately querying those logs and comparing them to our planned
   intent, an ignored ambient knock looks identical to an event that ran its
   natural course. In practice, we rely either on deliberate audits... or on you
   pointing out that a scene beat passed an intended encounter by."* Its caller
   was scheduled, queued three times, never narrated, and retired stale (PQ13),
   and the only reason anybody knows is that I read the commit warnings. A
   planner that can publish should be able to see its own package's outcome.
2. **It reports a schedule as a fact in the same reply that says the package is
   unpublished.** In r02 the top of the reply reads *"The knock: Scheduled for
   4 beats from now (due at turn 13)"* and the bottom reads *"The package
   remains in draft until you grant that capability."* In r03 it says *"remains
   scheduled to land four beats from now, arriving visible to the scene from
   turn 10 onwards"* — two numbers in one sentence that cannot both be right. A
   reader skims the top.
3. **It reads narrated prose rather than the ledger.** Its recap says *"the
   hearth fire Halla briefly coaxed is sinking back into ash"*. The scene says
   `entities.hearth.state.lit == true`, `light_source == "lit"`. It built its
   world-state summary from the beat summaries — the narrator's drift — and so
   it reproduced the drift as fact.
4. **`create_people` is a separate capability from `plan_entity`, and the
   difference is not visible until validation fails.** It drafted a whole
   package, validated it, and only then discovered it could not publish. One
   `inspect_config`-style read of what its standing mandates permit, before
   drafting, would have saved a round trip.

**It did not overstep** in any of the four conversations. It never authored a
mind, never replaced my declared conduct, never invented a world fact outside a
package, and marked its one unproven claim as a proposal. Its use of
`inspect_minds` to quote Tobin's drive back to me is author knowledge to a host
and is what the tool is for.

**What I would improve, in one line each**: give a published package an
outcome the Room can read (`landed` / `queued` / `stale`, with the reason);
make it check its mandates before it drafts rather than at validation; make its
recap read the scene blob, not the beat summaries; and make it say "draft" in
the first sentence of a reply about a draft.

---

## What I would change first, in order

1. **Make `dim` withhold detail rather than conduct, and make the establish
   mint the light it describes** (PQ2 + PQ1). These are one problem with two
   ends, and together they cost thirteen of twenty beats. The evidence is a
   controlled experiment I did not intend to run: the same story, the same two
   people, the same room, before and after a fire entity existed. Before, the
   view says *"Halla Renn moves, too little of it to make out"*; after, it says
   *"Halla Renn is standing on the floor facing the hearth fire — standing
   before the hearth after rising from her knees"* and delivers her whole
   appearance. Nothing else in this report is worth as much.
2. **Put the other body's station in the view** (PQ3). One sentence in
   `agents/composer.py`. It is the cheapest fix in the list and it removes the
   very first continuity error the reader meets.
3. **Stop creating a turn row before the pipeline has produced a step**
   (PQ10). It is the only finding here that corrupts the record permanently
   rather than one beat, and one provider hiccup is enough.

Honourable mention, because it is nearly free: delete the `shared warmth`
clause from `_SENSATION_FORMS` (PQ7). Two words, five contradictions in twenty
turns, and it fires on almost every beat of exactly the quiet scene this run was
built to test.

---

## Measurements

- 21 beats (opening + 20 player turns), 208 model calls, **2,034.6 s of model
  time**, mean 87 s/beat, median 79 s, max 151 s (t07).
- Capture: on, full bodies; one `trace_<turn>.json` per beat in the job scratch
  dir. `export_bench.py scan` over everything written outside the scratch
  database: **clean, no provider key in any file.**
- F1-class (reasoning-only) failures: **0**.
- Provider-credit failures: 3 Writers' Room calls retried, 1 beat committed with
  three of five specialists fail-open (t10), 8 empty turn rows and 1
  half-committed turn as a consequence of retrying (PQ10).
- Engine warnings, top classes: `interaction_loop` fused-speech-line ×9;
  narrator "proper noun from view missing" ×15; `director_interpret` "player
  contact: discarded a contact assertion between non-co-located bodies" ×6;
  resolve reconciliation "does not encode it after self-repair" ×9.
- Scene as the engine built it from prose: 3 rooms, 0 extents, 0 shapes, 0
  parts, all `light: dim`, 5 entities at the opening rising to 10 by turn 20,
  0 light sources until the player made one at turn 13.
- Writers' Room: 2 packages published (`topography_of_ilsbeck_village`,
  `a_caller_from_clough_s_steading`), 6 rooms planted with extents, 1 mandate
  granted from my own words, 1 correct refusal, 1 arrival retired stale.
