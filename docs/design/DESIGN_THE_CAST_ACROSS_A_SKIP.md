# Design: the cast lives through a time skip

**Status: PROPOSED 2026-10-21; nothing built.** This note brings together
three earlier owner designs and the owner's restatement of the same day:
- the timeskip half of `docs/UNBUILT_LIVING_WORLD.md` § 1.99d (2026-08-27);
- the dormancy ruling, `docs/design/DESIGN_OFFSCREEN_SUPERSEDED.md` § 3c
  (2026-09-17);
- the skip paragraph of `docs/design/DESIGN_WRITERS_ROOM_PLAN.md` (Phase D).

It adds a live probe of the two model calls the design needs: the question
put to a character, and the writer that turns a lived stretch into memories.
It answers the three questions § 1.99d left undecided, and states what the
owner still has to rule.

The owner, 2026-10-21:

> for time skips I think we need to seriously explore handing off major
> characters to charter, either their own or a towns having it based on
> their personality as much as possible and perhaps sending a prompt before
> the time skiped is initiated "A time skip of x length has been declared,
> what do you do for the duration of it?" and declaring things like sleep or
> what not is perfectly fine, and we can after the fact run a memory
> generator based on their declared actions or charter hand off.

## 0. The defect

**Probe finding F16** (the lighthouse story, 2026-10-21; job tmp
`fixes/stories/control.db`, chat 2):
- "Two days later the wind gets up from the west…" moved the story clock two
  days (`Design.md`, "A beat that passes over time moves the clock by it").
- Nobody else moved. The keeper stood in the lamp room through the whole
  span; the boatman sat in the channel for 77.7 story hours.
- In the skip beat nobody was asked anything (`flow.reactors: []`). The
  keeper's only memory of the two days is the storm heard through the walls.
- The next input framed the scene the writer wanted: "That night, when Elias
  comes down from the first watch and sits across the table from her with
  his tea…".
- `director_prose.a_walk_is_its_owners` dropped that framing whole, as the
  2026-10-07 ruling requires. But it made no offer
  (`authorial_offers: []`), so the keeper answered from upstairs and the
  resolve's prose retconned him down and back up again.

A writer fighting the machinery for an ordinary scene transition is the
campaign's own definition of a defect.

## 1. The shape

When the writer declares a skip, and before its far end is played:
1. **Ask.** Each major character is asked what they do for the duration.
   The answer is that mind's own declaration, so a walk is still its owner's.
2. **Execute.** Their answers run over the span the way the charter runs a
   resident's day: places, routes, sleep, meals, company. A deterministic
   floor decides what could not happen.
3. **Place.** Each of them is left where their own day ended.
4. **Remember.** Afterwards, each one's memories of the span are written from
   what reached that mind alone.

If the question fails, the mind falls back to the charter's ordinary day:
silence is sleep (Phase D).

This is § 1.99d's "temporary demotion and re-promotion with an intent query in
front of it", with § 3c's memory log as its last step.

## 2. The probe

Scripts and outputs are in job tmp `fixes/skip_probe/` (`probe.py`, `mint.py`,
`out_*.json`, `mint_out_*.json`). Each character's own captured payload
(`llm_capture` and `llm_blobs`) was replayed on its own model role, with only
the card replaced by a draft skip card. Ten calls cost $0.27 in all.

### 2.1 The question

| Who (model) | Span asked | Answer: stretches, seconds | At the end |
|---|---|---|---|
| Elias, keeper (glm-5.2) | two days | 8 routine + 6 plan, 11.9 s | kitchen, tea and the logbook |
| Elias, offered the writer's framing | two and a half days | 8 + 8, 11.3 s | "Sitting across the kitchen table from Rhona Carrick with his tea" |
| Pell, boatman, away (deepseek flash) | three days | 8 + 7, 7.6 s | the quay, the boat loaded for Tuesday |
| Nell, farm daughter (deepseek) | the rest of the night | 0 + 9, 4.7 s | building the morning fire |
| Davey, quay hand (deepseek) | the rest of the night | 0 + 6, 5.7 s | the morning haul on the quay |
| Corwin, watcher (glm-5.2) | a day | 7 + 3, 10.4 s | a new seat near the bar |
| Isolde, go-between (deepseek) | a week | 7 + 4, 5.4 s | the corner table, market night again |

What the answers showed:

- **Every answer reads as its character**, from that character's own aims and
  notebook:
  - The keeper will "not condemn what he has not examined", so he spends two
    days going over the Board's mechanism piece by piece.
  - The watcher changes his seat because "the big man noticed the grey coat".
  - The boatman posts the letter "before the pub gets its hooks in me".
- **The offer works.** Offered "you come down from the first watch and sit
  across the kitchen table from Rhona with your tea", the keeper put it in his
  own plan, with his own reason: "there are things that have been held for two
  days and a half that may or may not find their way to words". Without the
  offer he still ended in the kitchen, at a different hour.
- **Most places named outside the player's building do not exist.**
  - The boatman named ten places on a mainland the world holds as a single
    room, `The Mainland`.
  - The go-between's lodgings, warehouse row and back lanes are unbuilt.
  - Places inside known buildings mostly match, but by meaning rather than by
    spelling ("bedroom" for `Elias's Room`).
- **Plans lean on the player.** The keeper had 4–5 stretches "with" Rhona, the
  farm daughter 2 with Ash, and the quay hand 2 with Tamsin (he means to walk
  her home). The player is the author of their own body, so none of those can
  simply happen.
- **A plan can run past its span.** Asked only "until morning", the farm
  daughter planned the whole of the next day.
- **`doing` leaks intent.** The watcher's "watching the weathered woman's
  pouch in peripheral vision" and "let himself be seen walking so the town
  keeps filing him under 'quiet man who takes the air'" are not what anyone
  watching him would see. The turn card's "WHAT OTHERS GET OF YOU" rule has to
  carry over: `doing` is the visible surface, and intent goes in `why`.
- glm-5.2 wraps its JSON in a code fence. The engine's salvage parse already
  handles that.

### 2.2 The memory writer

The records were simulated by hand (no executor exists yet): the character's
own probe answer, the player's account where it places the player, plus
weather and outcomes. A draft card asked for 3–5 or 5–8 first-person memories
of 45–180 words, with "texture, never invention". The three calls took 7–15 s
each.

**As memory, it is what Phase D asked for: "not one line of I did x".**
- The boatman's record said only "it did not come off: the letter was not in
  your pocket". He wrote the strongest memory of the probe (valence -0.85):
  checking the jacket, the well, the thwart and the line locker, and ending
  "I have to go back to the rock and tell her I lost it".
- That is § 1.99d's "the simulation contradicts the stated intent, which is
  the interesting case and probably the point".
- The go-between folded six days of rounds into one memory, as asked.

**It also invents, in 8 of the 15 memories**, in three kinds:
- **Outcomes of the mind's own attempts:** the new mounting plate "sat true";
  the engine's knock is "louder now".
- **Other people's conduct and words:** "the clerk said less than I'd hoped",
  "that raised eyebrows", "the barman noticed". One memory puts a registered
  character "behind the bar" on the very night its record says he did not
  come.
- **A past event:** the boatman remembers "I tucked it in the pocket". In this
  database he never took the letter (the handover defect F15, since fixed).

So the writer needs a check pass. The line between texture and invention, for
people off the map, is the owner's call (§ 6).

**Second round, the same day (`skip_probe/mint2.py`, `t_*.json`).** The
same three records were rerun with a tighter card and with the mind's own
`memory` packet beside the record. The card's added lines:
- where the record gives no outcome, the memory stops at the attempt;
- nobody's words, looks or reactions appear beyond the record, a stranger's
  included;
- the past is only what `memory` and the card hold;
- the consequence is in the first person.

First, a correction to the count above. The boatman's "I tucked it in the
pocket" is not an invention. His own turn memory of that beat reads "What I
did: Pell Hardacre takes the sealed letter … and tucks it into the inside
pocket", and his notebook reads "Letter in the inside pocket". The world had
refused the take (F15, fixed in c9ba38e7), so the writer was faithful to what
he believed. The keeper's "pin sheared at 0214 … twenty-six minutes dark",
however, is not in his card or his memory, and in the rerun the writer quoted
the log entry again with a different time (0315).

| Writer | Memories with an invention | Serious ones | Words each | Cost per set |
|---|---|---|---|---|
| glm-5.2, first card | 8 of 15 | 3: a registered mind placed where he was not; how the mechanism fits; the 0214 times | 91-181 | about $0.05 |
| glm-5.2, tight card | about 7 of 15 | the keeper's whole log entries with times; the plate "half a millimetre off" | 59-171 | about $0.05 |
| deepseek flash (`character_mid`), tight card | 3-4 of 15, all mild | none; one slip swapped who watched the gear from below | 72-115 | about $0.004 |

**What the rerun showed:**
- **The tight card helps glm-5.2 only partly.** The strangers' reactions
  mostly went, and guesses now arrive hedged ("or I thought I did"). But a
  character whose nature runs to exact detail draws invented exact detail.
- **The cheap model held closest to the record and stayed in voice:** "I took
  the log down and went back through it to the March pin and the August belt
  … I read them twice".
- **A broad model checker is not a check.** Asked to flag every unsupported
  statement, deepseek flash (`director`) flagged none of the first card's
  inventions in two sets, and flagged facts the record gives in a third.
- **So the check pass in § 4.6 is two things:**
  - a deterministic floor for the most damaging kind: a number, time or count
    in a memory that neither the record nor `memory` holds;
  - narrow per-memory questions to Jev ("does anyone besides {name} act or
    speak in this memory?"), never one open "find the inventions".

### 2.3 Cost

| Call | Cost | Time |
|---|---|---|
| The question, mid tier (deepseek flash) | about $0.004 | 5–8 s |
| The question, major tier (glm-5.2) | about $0.015–0.02 | 10–12 s |
| The memory writer (utility, glm-5.2) | about $0.02–0.06 | 7–15 s |

- One skip costs about $0.03–0.08 per cast member, against a played turn's
  $0.058.
- The questions run in parallel, so a skip beat waits about as long as the
  slowest one.
- The memory writer runs out of band (§ 4.6), as § 3c requires.
- Skips are rare: 5 of the probes' 35 beats.

## 3. What exists, and what blocks it

These come from three read-only surveys, 2026-10-21.

**The charter can run a resident, not a cast member.**
- It steps a 48 h skip as twelve 4 h windows
  (`world/charter_runtime.py:advance_snapshot`, `MAX_CATCHUP_HOURS` 720,
  `CHARTER_BUDGET_SECONDS["time_skip"]` 60 s). Bodies walk routes at edge
  costs (`world/charter_move.py`), and needs are rest, sustenance, health and
  company (`world/charter_needs.py`).
- But during play, `world/charter_run.py:step` excludes every bound body: "may
  put their name on a watch bill, but may not walk, tire, feel, or speak for
  them". `simulate_bound` lifts that for a whole run, never for one body.
- It has no itinerary. There is no "until", errands last one window, and
  posts carry no hours.
- It has no sleep state: rest is a need, not awareness or vitals.
- Personality has no typed input. Temperament is derived from the body key,
  and habits from a word list over the card.
- Nothing hands a body back, except promotion's `promotion_handoff`, which
  deletes the cognition stores.
- Most stories have no charter at all: 18 of the owner's 153 chats, and none
  of the three probes.

**The skip path changes nothing for the cast.**
- `agents/runtime.py:build_plan` never reads `time`. A skip beat's reactors
  may be empty, and those that run read the stored clock and scene (§ 1.166's
  first residual).
- The commit's arithmetic over a skip
  (`persist/commit_scene_state.py:prepare_scene_commit`):
  - **Vitals:** 48 h awake leaves stamina "spent" and nourishment "faint with
    hunger", where survival is on.
  - **Sleep:** an asleep row ends 8 h after the beat
    (`director_floors._NATURAL_SLEEP_SECONDS`), and sleep counts only from the
    pre-beat state.
  - **Affect:** it decays only for minds that acted.
  - **Intentions, projects and promises** are aged by beats, so a skip is one
    beat.
- The weather takes one rung per beat (F20, lane l27). The boatman's boat had
  no `eta_seconds`, so it never arrived (F18, lane l25).

**The character call has no span.**
- Its card (`character_bare.txt`) frames one stretch "until someone else must
  answer".
- There is no sleep field: sleep is `do` text, which the encoder turns into
  awareness.
- The clock reaches the character as a part of the day only.

**Memory has precedents, none for a skip.**
- The turn memory is deterministic (`persist/commit_memory.py`).
- Off-screen memories exist only for:
  - the opt-in off-screen agent (`world/offscreen.py`): a deterministic one
    line, "I set out to…";
  - promotion seeds (`story/importers.py`): strictly from the body's own
    quoted evidence;
  - the charter's own deterministic `remembered()`
    (`world/charter_promote.py`);
  - the pre-story historian (`world/charter_history.py`), which is licensed
    to invent minor conversations.
- `world/gaps.py:interim_for` hands a returning character a free record as
  payload. Payload is not memory, as § 3c says.

## 4. The design

### 4.1 When

The skip stage runs when **the input set the time**
(`director_prose.the_input_set_the_time` returns a block) and the skip is at
least `SKIP_LIVED_SECONDS`. That threshold is the owner's (§ 6); 3600 s is
proposed.

A resolve's own stretch, in a beat whose input passed no time, is ordinary
beat time and does not trigger the stage.

The plan is built from the stored interpret output, so a rerun rebuilds the
same plan.

### 4.2 Who is asked

- **Every active cast member in the player's frame**, asleep ones included.
  Their payload says they are under, and their answer begins with sleep.
- **Dormant cast**, away with no bubble, such as the boatman. This is § 3c's
  tier, and a skip is where most of their life passes. Whether every skip asks
  every dormant member is the owner's call (§ 6).
- **Never the player.** The account is the player's span, and the engine
  places the player only where the account does.
- **Not bubble cast.** Their frame keeps its own clock (frame-scoped, merged
  at reunion as today), which is a residual.
- **Not the town's residents or background presences.** The charter already
  carries its residents through the skip, unchanged.

### 4.3 The question

**A new plan stage** sits between `compile_world_context` and
`perception_act`. Adding a stage is the `agents/README.md` checklist: four
registries, which nothing checks agree.

**One call per mind, in parallel.** Each answer comes from that mind's own
inputs alone: its ordinary character payload (self, memory, its perception at
the skip's start, relationships, notebook), plus:
- **the span** in its own terms: a length, and "until" a part of the day with
  a day count, the engine's own `{days, until_phase}` vocabulary;
- **offers** addressed to it (§ 4.3.1).

**The card** is a sibling of `character_bare.txt` (en and ja). It is the
probe's draft, amended by what the probe found:
- `doing` is what a stranger watching would see, and its intent goes in `why`;
- stay inside the span;
- name places as you know them;
- only your own doing, never how it turns out;
- sleep is an answer.

**The answer** has four parts:
- `routine`: one ordinary day, part of the day to part of the day;
- `plan`: in order, what departs from the routine, each entry with `day`,
  `from`, `until`, `where`, `doing`, `asleep`, `with` and `why`;
- `at_the_end`;
- `on_your_mind`.

Measured: both models used the split sensibly, and a week fitted in seven
routine stretches and four exceptions.

#### 4.3.1 Offers: the account's framing of another mind

The account sometimes writes another mind's conduct. Today the engine handles
it in two ways:
- **Their walk is dropped** by `a_walk_is_its_owners`.
- **Their thought or response** is rerouted as `comes_to_you`
  (`agents/director_views.py:_route_authorial_npc_beat`).

The dropped walk should travel the same road, as an offer to its owner. At a
skip, the offer is shown in that mind's question; mid-scene, it is an
ordinary `comes_to_you` offer.

The ruling stands: the move happens only if the mind declares it. The probe
says minds take a fitting offer up.

### 4.4 Execution: handing them to the charter

One deterministic executor, pure code, in either of two homes. This keeps the
ruling: off screen is code, and the mind declared its own day.

- **(a) The town's charter, where the story has one.** The cast member is
  enrolled for the span as a body with an *itinerary*:
  - the charter's own planners (watch, errands, homecomings) yield to it
    wherever it speaks;
  - where it is silent, the charter's needs-driven day runs them.
  - This needs `simulate_bound` per body rather than per run, and an itinerary
    primitive.
  - The charter's per-body `experiences` and co-presence join the mind's log.
- **(b) Their own, where there is no charter** (most stories). The same
  itinerary runs with no institution: routes and travel time over the place
  graph (`charter_move`'s edge costs), sleep, meals and company.

**Places.** Each `where` is resolved in three steps:
1. exactly, against the mind's own place graph and the rooms it knows;
2. through Jev, the engine's free-text-to-closed-option tool, over those same
   known places plus "none of these". This finds `Elias's Room` for
   "bedroom", and `The Mainland` for the boatman's harbour;
3. otherwise, as an **off-map label**.

An off-map label invents no room. The mind is *away at* that label. A
planning need is a room some beat reaches for, not every place a plan names.

**Time.** Stretches run in order from the span's start, in absolute seconds,
clipped to the span (the farm daughter's overrun).
- Travel between rooms eats the start of the next stretch.
- A stretch that cannot happen fails with a typed reason: no route, a shut way
  the mind cannot pass, or a thing it needs and does not hold.

**Company.** Two minds in the same room, or at the same off-map label, over
overlapping time each receive the other's `doing`, never their `why`. This is
a per-observer log, the firewall's shape.

**The player** is placed only where the account places them (the interpret's
typed events).
- A stretch "with" the player is the mind's own side of it.
- They share the room only where the account puts the player there.
- A writer who wants the days lived together writes them into the account,
  and the minds see that as an offer.

**The body.**
- An asleep stretch is sleep: the vitals' sleep rate, and awareness at the far
  end if the last stretch is asleep.
- A lived day is a fed one unless the plan says otherwise.
- Company comes from co-presence.
- Affect decays over the span for every asked mind.

**Things.**
- **Phase 1:** a stretch that names a thing the mind carries checks that the
  mind holds it. If it does not, the stretch fails ("it was not on you"), as
  the boatman's letter would have.
- **Phase 2:** moving things during a skip.

**Weather.** Each stretch carries the sky where the mind stood, from the
weather model stepped once per drift window (F20's fix).

**Output, per mind:**
- **a log:** its own stretches with outcomes, what it saw of whoever shared
  its place, the weather and its sleep;
- **a far-end state:** a room or an off-map label, awake or asleep, and its
  needs.

The log is the skip stage's output, a step variant, so a reroll and a rerun
work as for every stage. It is never stored in charter `minds`, by § 2 of the
superseded note: the charter owns where a person was and what they did, never
what a mind knows.

### 4.5 The far end

- **Each mind is placed** where its last stretch left it: a move by its own
  declaration. If that place is an off-map label, the mind is away there,
  meaning dormant with a typed whereabouts. That record is new: planning needs
  have no "whereabouts" kind.
- **A mind asleep at the far end** gets an awareness row that starts when its
  sleep did, so the natural 8 h exit counts from the right hour.
- **The rest of the beat** (`perception_act`, the reactor gates, the resolve)
  receives these placements as onset previews. Today those gates read the
  stored scene.
- **A mind's far-end call** carries its own log as payload (the `interim_for`
  precedent). Its memories arrive out of band behind it, so the far end never
  waits for the writer.

### 4.6 The memories

- **One call per mind, after the commit, out of band** (§ 3c). The input is
  that mind's own log and its card, for voice. Never another mind's plan, the
  account beyond what reached it, or the Director's prose.
- **The rows follow Phase D's shape**, each occasion its own row:
  - **content:** 45–180 words, with valence, arousal and consequence; one
    memory may hold the ordinary run of the days;
  - **count:** scaled to the span, with the scale the owner's (§ 6);
  - **provenance:** `witnessed` (§ 3c), plus a skip origin mark (the
    Writers' Room plan's open question 3, recommended yes);
  - **time:** `encoded_at_seconds` at each occasion's own time within the
    span, and the skip beat's `turn_idx`;
  - **keys:** stable `event_key`s, so a rerun replaces rows rather than adding
    them.
- **A check pass, because the probe's writer invented in 8 of 15.** For each
  memory, Jev asks whether it states any of:
  1. conduct, words or decisions of a registered mind or the player that the
     log does not hold;
  2. an outcome of the mind's own attempt that the log does not give;
  3. a past event before the span that the mind's memory does not hold.

  A flagged memory is rewritten once, and if it still fails, its flagged
  sentences go.
- **Projects and intentions** a stretch served are credited, mapped by Jev as
  `mind/character_jev.py` already maps notebook commitments to
  `project_ops`. This is phase 2. Today a skip is one beat to their ageing.

*Built 2026-10-21 (`mind/skip_memories.py`; `Design.md`, "A mind remembers the days a
skip passed over"): the job, the writer on its own `skip_memory` row, the count as a
ceiling, the numbers floor, ONE of the three questions above (others' conduct -- the
build spec's narrowing) with a rewrite and a drop, and the rows. What it leaves is
`docs/UNBUILT_LIVING_WORLD.md` § 1.99d.*

### 4.7 The three questions § 1.99d left open

1. **One call or one per character?** One per character.
   - Each answer must come from that mind's own inputs.
   - One prompt holding several minds' private contexts is a leak by
     construction.
   - Running in parallel costs no wall clock.
2. **How do projects and intentions seed the charter's wants?** They are
   already in the question's payload, and the answer is the projection. The
   Writers' Room plan's "explicit, reversible projection of the card" is what
   a character does when asked. A second copy in the charter would be a
   second representation of a mind.
3. **What happens when the simulation contradicts the stated intent?**
   - The stretch fails with its typed reason, and the writer is told.
   - The probe's best memory came from exactly that.

### 4.8 The rulings this keeps

- A walk is its owner's (2026-10-07):
  - every move is the mind's own declaration;
  - the account's framing of another mind is an offer, never authorship.
- Pure code off screen, an LLM on screen (2026-09-14):
  - the question is the mind declaring, as on screen;
  - the executor is code.
- The charter owns where a person is and what they did, never what a mind
  knows, wants or remembers (superseded note § 2).
- The firewall:
  - logs are per observer;
  - the writer sees one mind's log;
  - the check holds the writer to it.
- Efficiency never removes function, and every cap is named (§ 6).

## 5. Build order

- **Phase 0, small and useful alone:** the dropped walk becomes an offer
  (§ 4.3.1), mid-scene and at a skip.
- **Phase 1, the core, needing no charter:**
  - the stage, card (en and ja) and schema;
  - the executor for case (b): places with the Jev fallback, routes, sleep,
    company, the holding check, clipping to the span;
  - the far-end placements and onset previews, and the log as payload;
  - the out-of-band writer with its check pass, and the origin mark.
  - Proved by replaying the lighthouse from idx 8 with its next input, and by
    a tavern night.
- **Phase 2:**
  - the town charter (case (a)): per-body `simulate_bound`, the itinerary its
    planners yield to, the hand-back;
  - things moved in a skip;
  - crediting projects and intentions;
  - dormant cast at every skip;
  - bubbles.
- **Phase 3:**
  - two plans that seek each other, resolved as an encounter rather than a
    shared room;
  - the psychology of the span beyond decay.
- **Prerequisites in flight:**
  - F18: an arrival is priced when no eta was written;
  - F20: the sky moves by the hours.

## 6. For the owner

1. **The trigger.** `SKIP_LIVED_SECONDS`, proposed one hour. Below it, the
   ordinary beat covers the stretch.
2. **Dormant cast.** Asked at every skip, which is proposed, or only some?
3. **How many memories.** Proposed: one per 12 lived hours, at least one, at
   most eight (a week gives eight).
4. **Strangers in skip memories.** "Texture" for unnamed people off the map,
   as the pre-story historian's "minor conversations" are, or held strictly to
   the log? Registered minds and the player are always strict.
5. **Off-map whereabouts.** A mind whose day ends somewhere unbuilt is away
   there. It comes back through its next skip's plan, or through a beat that
   reaches for it (the Room builds the place then). Is that the rule?
6. **The writer's model.** Measured in § 2.2's second round, the cheaper
   model with the tight card was the most faithful at a tenth of the cost.
   Recommended: deepseek flash (the `character_mid` route), with the tight
   card and the two-part check.
7. **The player's account placing a cast member under `world_author`**, which
   was the earlier option 1. With offers, the probe says the mind usually
   takes the framing up. Recommended: offers, not authority.
