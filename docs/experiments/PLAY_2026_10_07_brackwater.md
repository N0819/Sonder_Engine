# Brackwater, the Corvina claim: a 30-beat harsh play run (2026-10-07)

Scratch story 166 on a copy of the owner's db, Full Text capture on, the
Writers' Room granted full authority. One protocol throughout: anything that
broke immersion stopped play; every stage of the beat was read against the
others (and the Room asked) until the earliest wrong datum was found; the
engine was repaired as a class, with a measurement on stored data and a test;
the beat was rerolled; play resumed. The final cut of the story is published
as an artifact, "The Corvina Claim" (https://claude.ai/artifact/ULprkxnXujGNyDkPdNy5p2,
private to the owner); the chat's portable archive, the raw findings log and
the page's source are kept in `output/brackwater-2026-10-07/` (git-ignored).

- Player: Tamsin Coyle, assessor for the River Underwriters (played by Claude).
- Cast: Hester Gale, the pilot (card); Abel Gale, her brother (a Room-planned
  person, promoted to a full character at beat 24).
- 30 kept beats (an opening and 29), about 15 rerolls and replays, 50
  commits. Kept beats ran a median 185 s (84-589 s); 747 model calls were
  captured for the chat across all runs.
- NanoGPT ran out of credit at beat 24 (0.014 USD left). On the owner's word
  every NanoGPT role moved to the same model on OpenRouter for the rest
  (scratch db only; the previous map is in `output/brackwater-2026-10-07/`).

## Verdict

When the engine works it is a better roleplay partner than most: a pilot with
a secret and visible tells, who negotiates her own terms ("That house opens to
my knock or it doesn't open tonight"); a brother whose drive and taboo shape
the scene the moment he has a mind ("Not here. Not with her standing there");
and a firewall that produces dramatic irony on its own -- Hester honestly
misidentified a reed-cutter as one of the chapel keepers in the fog, off
screen, and handed the player that false lead three beats later. The
Room-planted clue chain (the coat at the third stake, the receipt in its
pocket, the casks hidden under the grain) is a real mystery.

When it breaks, it breaks where the player can see it, and the worst seam is
the same one every time: **getting two people from one room to another
together.** Six of the fifteen-odd stops in this run were a companion, a
follower or a vessel not ending up where the page put them. The second seam
is **a question the world never answered** -- a read with no words, a look
that found nothing, a whisper meant to carry -- after which the narrator fills
the gap, usually with the opposite of the record.

## Fixed during the run

Each commit names its class, the case that found it, the measurement, and the
test. Grouped by layer; in order within each group.

### The Writers' Room and the opening
- 284aa601 a JSON answer held back until whole is asked again without JSON mode (NanoGPT first token = total time)
- 74817909 the prelude is shown what the launch screen settled about the place
- 1b77cdf1 a town plan is read in the shape the model wrote it; a dead chain is said (320/320 unable)
- 55b6fadd the Room files lore into the chat's own canon, minted on first filing
- 4508bc02 the Room sees whose post it is, not only who stands it this hour
- 044bfebe a town the Room drafted and the wall stopped is resumed, not redone
- dbd2694b the Room can file lore before the first beat
- 8bf09192 a scenario story's first line is a beat, and whoever it speaks to can answer
- d97f4a66 (owner ruling) a tie from before the story is recognition, planned both ways
- c937fc40 (owner ruling) the Room decides who lives in the place it plans, when the launch left it open

### Voices, the charter, presences
- 0d688f15 a card's voice register is what a listener hears
- c1bc3189 a person the beat mints is present on the beat that mints them
- ac81095a a voice from another room says where it came from; a background voice does not repeat itself
- 3ce27982 a background voice knows its own house and does not supply what it does not know
- 00ed87db a background voice remembers what it said, and is not handed its act back
- 6c5f6a63 a charter voice is handed words, never the engine's keys ("body_recovered x3" read as three corpses)
- 388baf32 / 21b1b81e the town's public knowledge reaches the minds that live in it; not the player's briefing
- 0f631886 (+c0d3a24b) a planned person the beat speaks to is there, and his name stays his own
- 52505473 a person the scene stands is a body in the view, never a thing by name
- 2bca0667 / 0c5c7cde words said once are said once; one question is one address
- 39f3fc2f (owner ask) bystanders share one unaddressed voice a beat; anyone spoken to still answers
- 6931b7ce a planned person with a presence record keeps his look
- e2b43bee (owner ask) people in a room talk to each other, and it lasts while you are there (threads, steps 1-2; `docs/design/DESIGN_CONVERSATION_THREADS.md`)
- f374a8ca a voice's service reaches the commit: `hands_over`/`still_owes` were dropped by `_react_one` from the day they were built (model set still_owes 11x and hands_over 3x; 0 of 342 stored declarations carried either)
- e1c0e035 a figure that answered before the resolve owes no reply (11 of 121 pre-resolve answers were re-asked the next beat)
- 156a6da9, superseded by 222ed01b: a word that names a thing the scene holds does not name a person (the oilskin man "addressed" by every line about the coat, four beats running)
- e777ac3c a promoted presence keeps the place its body stood (the brother placed outside his own house; his confession came through the door)

### Movement and agency
- 571a0244 the player's own walk is spelled "self", at ingest
- 57e4cf99 a line its speaker declared before an act is heard before that act
- 121f5048 (+74d76c6c, owner ruling) a mind goes only where its own declaration takes it -- the player's included
- edd3b18b a line goes first to the one its speaker named
- 5ed7cec3 three more paths stop moving people: the companion carry deleted (30 stored boardings, 2 firings, both wrong); the near-group repair holds a body that walked; the floor drops the near-claims written for a refused move
- ffe4185a / 95d5bc47 a cast member a bubble returns this beat is asked -- by the planner and by the loop (the causality bubble's first run in play; drift guard between the two hand copies of the widening list)
- c5431390 a walk begun is a movement, whether or not it arrives this beat (encoder card)
- e103f55a a walk the encoder wrote as a position is still its owner's walk

### Perception, sight and the page
- 97d2f418 the name scrub never cuts a cast member's surname out of a relative's name
- 9335bed7 (owner ask) what stands between hides what is behind it; a look far off is answered; no placeholders
- 88940a2f a sound source's switch is always `state.running` (the bell rang forever on `ringing: false`)
- da3c834f the player's conclusions are the player's to draw (narrator rule 4)
- 08aa0e64 a thing that acts is called what it is, not "the unfamiliar person" ("You are in the deck of the unfamiliar person")
- f2c217b2 a room's description in a view ends where a sentence ends ("the open fen stretc."; 8.8% of rooms over the cap)
- 4511919a a typed fact lives in its field, and a note it makes untrue is rewritten (lantern `lit: true` beside "unlit")
- 4d50e099 a thing looked at closely tells you what it is like (a declared look was never a read)
- 566add56 an act that asks the world something is answered by it (the receipt was read and the page never said what it said; answered on the first sample after)

## Ranked open findings: what still breaks play

1. **Companion travel** (F88, F92, F101; beat 22 failed three times). A
   declared follow is not a follow: `follow_op` is set on 8 of 4,207 stored
   interprets, because no card has asked for it since the causal Director was
   replaced. The interpret pins the player to one destination, chosen before
   the companion has declared where she goes and before the room author builds
   the place they are walking to; the player-agency floor then stops the
   encoder's follow because the destinations differ; and the follow carry never
   moves the player by design. A companion's line on a shared walk is graded
   from wherever the onset put the player (Hester's whispered instructions,
   lost twice). Symptom on the page: the narrator walks the player to a door
   the world never reached.
2. **A vessel moving within the room it set off from is in no room** (F92).
   The encoder wrote "noses into the reed and stops" as a departure with no
   route, and the 2026-09-25 transit ruling drops a route that names the room
   it left -- right for a TARDIS leaving a beach, wrong for a boat sculling down
   one channel. Its passengers could not see out (the coat a boat's length off
   was invisible), could not be reached, and could not step off.
3. **The narrator answers what the view does not** (F96, F98, F94 before the
   fixes). Asked a direct question the view could not answer ("trodden or
   cut?"), it invented the answer, and the invention was the opposite of the
   record each time. The upstream fixes (reads and looks answered) remove the
   commonest trigger; the narrator still has no clause against it, and the
   owner's no-placeholder ruling pushes it to fill.
4. **Light reach** (F95). A lantern lights the room it is in; the channel its
   beam points into stays dark, so a look at a thing beyond the gunwale reads
   nothing.
5. **Encoder reliability** (F91, F93). An invented write hung on an unrelated
   event (the player's lantern put out on a hull-graze) passed the repair,
   whose wrong-write check acts at 0.8 with measured recall 0.78; one missing
   brace in 3,287 characters, slipped again on the single repair attempt, lost
   a whole beat (2 of 386 encoder answers in the run).
6. **The presence ledger holds things as people** (F83): 4 of 17 tracked
   presences in this chat are objects (the tide bell, a brass storm lantern,
   the Grebe, a wool coat), through the inert-kind deny-list. Each is one act
   away from being voiced or labelled as a person.
7. **A plot-central planned person is played by the stateless background
   reactor** (F102) until a human promotes him: the brother got one line a beat
   and no mind. Promotion fixed it at once.
8. **Smaller**: a figure repeating his own line verbatim eighteen beats later
   (F100; own-words memory spans three rows); a character inventing a
   townsperson, filed correctly as a claim (F99); a stage direction inside
   spoken text and a whisper declared for a line meant to carry through a door
   (F104); the generator's unread `distinctive_features` (F12).
9. **Cost and latency**: kept beats median 185 s, worst 589 s; one
   `perception_act` took 169 s; the Writers' Room still spends minutes a reply
   (F5, F16, F19, F30 from the first half of the run).

## Decisions for the owner

Each is a design call the run could not make for you; a recommendation where
the evidence supports one.

- **D1 (F101, F88). Should a player's declared follow carry her?**
  Recommended: yes -- restore `follow_op` to the interpret and character cards,
  and let the follow carry move the player when the follow is her own
  declaration ("their walk is their own declaration" is then honoured, not
  overridden).
- **D2 (F92). A vessel moving within one room.** Recommended: keep the
  09-25 rule for leaving a room, but let a vessel whose transit names no other
  space stay in the room it set off from (route = departed_from) rather than
  in no room.
- **D3 (F95). Should a pointed lantern light what it points at in the next
  room?**
- **D4 (F91). The repair's wrong-write threshold** (0.8; recall 0.78).
- **D5 (F93). A second, fresh encoder attempt** after a malformed repair,
  before the causal stage aborts the beat.
- **D6 (F99). Characters inventing townspeople**: leave as claims, or have
  the Room ratify them?
- **D7 (F102). Auto-promotion for a Room-planned person** the player keeps
  addressing.
- **D8. Numbers named for you**: the thread constants (`THREADS_PER_ROOM` 1,
  `THREAD_LINES_PER_EXCHANGE` 3, `THREAD_MAX_EXCHANGES` 6, `THREAD_IDLE_BEATS`
  2, `THREAD_PARTICIPANTS_MAX` 3); `ROOM_PROSE_CHARS` 600 (it drops whole
  closing sentences on 8.8% of rooms).
- Carried from the first half of the run: F72 a world pressure needs an
  actor (the bell rang with no ringer); F60/F61 voice and light constants;
  far-look description for unvisited places; F66 a cast member made local
  after launch knows no charter body; F31 rerolls erase the Room's published
  work; the efficiency pair (carried-report scoping, the doorway search); F38.

## Notes on method

- Three times a page read well over a broken world: turn 11 was rated strong
  from the page alone while its state had the pilot back in the chapel; a
  third of the stops in this run were found only by comparing the page to
  `positions`. Read the state, not only the page.
- `run_pipeline` is a generator; a replay that does not iterate it runs
  nothing, and every trace attached to it reports zero calls.
- Turn ids are reused after a delete: a turn id in the findings log refers to
  the run it was logged against.

## Addendum: where the tokens went, and where the prose comes from

After an outside critique of the published story (over-interpreted gestures,
a "second dialogue track" of white knuckles and held breaths, nautical
similes homogenising voices, quiet beats as heavy as dramatic ones), an
eight-agent workflow measured the run and adversarially checked every
proposal against the code and data. Full results:
`output/brackwater-2026-10-07/tokens_and_prose_workflow.json` (git-ignored).

**The prose is engine-fed.** Of 55 body-tension motifs on 25 of 30 pages,
54 trace to a record the engine delivered; one is the narrator's own.
- Characters declare two tells every beat (33 of 34 replies at
  `jev.MAX_TELLS=2`).
- `affect.tell_gate` blocked none: every subtlety fell between 0.397 and
  0.668, and the observer floor was 0.70.
- Cue records are ordered after every event, so 16 of 29 pages end on a
  tell.
- 25 of the 39 "sign, then its meaning" glosses arrived pre-written in the
  free-text `how`, `demeanor` ("X seems ...") and cue fields. The observable
  floor that `do` has does not apply to them.
- All 34 demeanor strings were distinct, so the ledger re-delivered one
  every beat.
- Page length is uncorrelated with what happened (r = 0.02). The card's
  "Cutting REALLOCATES, it does not shrink" forbids a short page.

**A narrator restraint clause, A/B tested, did not work.** Twelve calls,
$0.58, on the exact captured requests:
- no consistent length or motif effect;
- the "don't gloss" half failed on 4 of 5 turns, because the model renders
  delivered text as delivered;
- fidelity was intact in both arms.

The fix belongs where cue, demeanor and manner text is written. A
deterministic em-dash rewrite would move the glosses, not remove them:
103 dashes, but only about 14 of the 39 glosses hinge on one.

Landed at the source 2026-10-08: one tell a reply, asked for only when the
moment presses; the tell gate counted on one scale (an absent advantage adds
nothing); each cue placed at the line or act it showed at; the card's
observable floor for how/demeanor/tells; an unchanged demeanor keeps its
words. A/B on six captured Hester calls (12 calls, $0.75): tells 15 -> 10
written, glosses 9 -> 2, both soft.

**Where the money and time went.** All-in cost was about $0.47 per kept
beat (rerolls, the Room and predevelopment included); the kept pipeline
alone was about $0.23 per turn.
- The encoder is 41-52% of USD. None of its 224 calls read a cache; its
  repair calls are 51% of its input, re-sending the same world sections;
  and it ships full records for rooms 3+ hops away (67% of room text, named
  in 14 of 2,834 sends).
- The Writers' Room is 46% of input and 75% of output tokens, but only
  about 16% of USD (DeepSeek is cheap and caches well). Its 21 background
  fill jobs (371 calls) produced nothing that reached a page or a mind; 17
  of the 21 had no open need.
- The narrator's output is about 95% reasoning trace, about 30 s per beat.
- Jev is about 40% of per-beat input tokens, at well under a cent.

**Verified token proposals.** Every one came back "partial" (smaller than
first claimed) or "refuted". In descending value:
1. Gate Room fills on a real frontier change: 49-60% fewer Room calls, no
   page change in this run. The verifier adds a root cause: the frontier
   measure counts only planned stubs.
2. Encoder prompt caching: settle Gemini's cache-write price on OpenRouter
   with one probe first. Then choose among a system-part cache marker
   (-20% or +1%), repair as a continuation of the main call (-21% to -77%),
   or a per-stage world block (-20% to -64%).
3. Scope the encoder's rooms and carried reports: -9% to -16% of encoder
   input. Needs a replay check; the hop cap is the owner's.
4. Narrator reasoning off, behind a fiction-quality A/B: up to about
   -30 s and about $0.02-0.05 per beat. Also drop the grammar's duplicate
   `text` field: 15 of 40 calls wrote the page twice, and one runaway hit
   the 50k cap.
5. Smaller items:
   - room predevelopment never shortened an in-beat run;
   - the in-turn room author gets a full rooms ledger it never inspects;
   - JSON-schema stalls cost about 16 s per beat through the format ladder;
   - Gemini's flex tier is half price.

Refuted: dropping the room author's raw room records (the rendered
`surroundings` is not a superset), and queueing fills after acceptance
(erasure follows the checkpoint, not the queue).

**Found outside the lanes, for the backlog:**
- Declaration ids collide across interaction-loop rounds. Turn 4610: Abel's
  loud "Hester - stay on the walk" was logged as a mutter with round 0's
  tone.
- The narrator fidelity checker misfires on short-trace pages.

**The narrator lane, 2026-10-08.** Patched: the narrator grammar no longer offers `text`/`paragraph_count`; a length stop whose output was mostly answer is asked again at its own budget instead of escalated (`providers.answer_ran_away`); the card's length floor and its 'hits hard' clause gave way to 'a page weighs what its beat weighed'. A VOICE section naming `private_voice_setting`/`register` as how the page sounds was built, measured and withheld (below). A/B on the six captured requests: 24 calls, $0.67, Wafer pinned, all on the new grammar; arms were (a) old card at low, (b) new card at low, (c) new card with reasoning off.
- Every delivered line was placed exactly once in all 24 answers, and none wrote `text` (5 of 12 had, on the same requests the day before).
- Length did not move: quiet-beat medians 181.5 words (a) and 201.5 (b), six samples each; dramatic totals 838 and 804. The card is not the length lever.
- At low effort, 97% of output was trace. Median per call on Wafer: 67 s (a) and 44 s (b). Traces ran from 0.7k to 19.7k tokens.
- Reasoning off ran a median 3.7 s and $0.0026 a call (against about $0.036), but broke a rule on 4 of 6 beats: the player's walk re-narrated with a mind-read ('Hester plainly could'); a door 'held' against an open portal state; conclusions drawn for the player, with an invented 'dead man's coat' and `{{new_specifics: []}}` printed in the prose; invented history and nautical similes on Abel. Off is not a default; the owner's 'low' stands.
- New card: 3 of 9 samples slipped. One cue was dropped because its own text said 'without her noticing'; one sampling drift re-rendered the beat and wrote the player's compliance; one gave a smell a source and confirmed a claim, justified in the trace as 'Tamsin's dry voice'. Old card: 0 of 9. Small n, but the voice slip and the traces' 11 voice mentions against 4 are why the VOICE section was not landed.
