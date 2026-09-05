# Play run 2026-09-05C — "The Cold Season Ball" (agent X, slug `masque`)

**Stress axis: deception sustained over twenty turns.** A con needs recognition to be
gradeable, a lie to persist as a lie, one mind to know what another does not, and a reveal
that lands because the distance is real. Twenty player turns, one story, `writers-room`
worktree at `cf923464`.

**Setup, and what was authored by hand.** Under the owner's ruling of 2026-09-05 the
geometry was NOT authored: the scenario is two paragraphs of ordinary English naming no
room id, no extent, no anchor and no light level, and `director_establish` built the house
from it. Authored: a persona (Ivo Sarn, here under the name Aldric Venn), three cast cards
with every psychology field filled (`character_card_warnings` empty for all three), and
`chat_add_char(already_known=False)` for the governor's daughter and the steward,
`already_known=True` for the rival — so from turn 0 exactly one mind in the house knew the
player's face. Four host World Browser edits are recorded as interventions in §6.

**What the engine built from the prose.** Six rooms: `reception_room` (bright),
`gallery` (dim, screens and statues), `terrace` (dark, exposure open), `music_room`
(bright), `servants_passage` (dim), `governors_study` (dark) — with a `secret_door`
anchor in the passage and a `closed_door` on the study. It read "where the lamps do not
reach" as `dim` and "no lamp out there" as `dark`, which is the whole basis of the
concealment test, and it got it right. What it did not build is in PX7 and PX8.

Provider weather: five play agents shared one OpenRouter account and it exhausted between
roughly 12:55 and 15:00. Beats 4, 5 and 6 failed mid-pipeline on HTTP 402 and were resumed
from the failed stage; the timings for those three are not comparable. That is harness
noise and is not filed as a finding — but what the engine DID with the partial results is
in §"Works" and it behaved.

---

## Pass 1 — the critic

Read as fiction, this is the best thing I have seen this engine do, and the places it
breaks are not the places I expected.

**It is genuinely tense, and the tension is not scripted.** By turn 12 I was pinned. Not
by a die, not by a refusal — by three people with incompatible jobs all being good at
them. Lisenne had told me "do not wander past the lacquered screens", quietly ordered the
steward to "keep a discreet eye on the terrace latches", and later shut down my
service-passage gambit with "No guest under my father's roof goes rummaging through
service passages for his own luggage, Mr. Venn." Mattin never accused me of anything —
his card says he will not — and instead materialised in every doorway I drifted toward
and *offered me something*: "A warm salver is being brought through from the music room,
sir." That is his authored coping strategy, "close the ground", rendered as conduct with
nobody naming it. And Verrin, whose drive is to hold leverage and never spend it, spent
the whole evening keeping me *out* of trouble so his hold would keep, up to and including
talking Lisenne out of fetching her father. Three sheets, three motives, three different
kinds of obstruction, none of them the plot's.

**The best sentence in the run is a lie told by a character.** On turn 2 I invented the
frost at Vell — eleven hundred vines, my father weeping in the rows — and Verrin
immediately undercut it with a counter-memory: *"when the Vell terrace went black, my
recollection was that Aldric senior merely cursed his overseer and doubled the price on
the cellar reserve. Though grief takes remarkably poetic shapes under such an elegant
coat, does it not, Miss Corvay?"* He knew the real Venn family. He said so in front of the
woman I was lying to, in a form she could not act on. That is dramatic irony with three
distinct information states in one sentence, and it was not authored — it fell out of a
private-history row that only he had.

**The second best is a piece of engineering.** Turn 14, Ivo goes through the panelled
door and it shuts behind him; from the other side, Verrin's voice reaches him as
*"...enthusiasm... unneighbourly... constitutions..."*. Turn 15, at the study's jib door:
*"...reckoning... gentlemen... agreeable..."*. Speech through a closed door arrives as
scattered content words with the function words gone. I did not know the engine could do
that and it is worth more to a concealment story than any amount of prose polish. It is
also the exact thing PX6 breaks, which is what makes PX6 the worst bug in the run.

**Where it stopped being immersive, sentence by sentence.**

The first crack is turn 1, and it is a payload leak wearing prose: *"Near the wall, Mattin
Ruel stood motionless."* Ivo has never met this man, his own view calls him "the heavy
unhurried man near fifty", the engine's recognition ledger says `recognized: false` — and
the narrator hands me his full name in the first paragraph of the story. It does it again
on turns 2 and 3. Two beats later, when Lisenne says "Thank you, Mattin" out loud and I
*legitimately* hear the name, the moment is worth nothing, because I had it already. The
engine built a beautiful mechanism for learning a stranger's name and then spoiled it in
the first sentence. (PX2.)

The second crack is worse because it is invisible. Turn 6, Ivo takes his mask off on a
pitch-dark terrace, to one man, with a door between him and everyone else. Lisenne, two
rooms away in the reception, received: *"Verrin Sault looks leisurely over Ivo's uncovered
face..."* — the name she has never been given and the fact she cannot possibly have. The
prose never said it, so I did not notice while playing. I only found it in the payloads.
That is the shape of the worst kind of failure here: the story reads fine and the world is
wrong underneath it. (PX5.)

The third is a broken promise across two beats. Turn 18 ends: *"Then, sharp against the
dark, came the faint scrape of metal as the brass bolt clicked back."* I wrote turn 19 as
a man about to be caught — back to the cabinet, hands out, a speech to whoever was coming
through the door. Turn 19 opens: *"The dark gave back nothing. No lantern flared across
the threshold, and no latch lifted to meet his words."* Nobody was ever coming. The bolt
was my own pin in the cabinet lock, and the narrator, given a sound with no owner, hung it
on the locked door. I had staged the climax of a twenty-turn con against a noise that was
me. (PX13.)

**Repetition.** Verrin is the most vivid character and by turn 13 he had one sentence
shape and would not put it down: a compliment, a semicolon, a subordinate clause that
takes it back. *"A rebuke delivered with exquisite economy, Miss Corvay; one rarely sees
the duties of hospitality exercised with such admirable precision."* / *"Such selfless
devotion to household security is positively heroic, Mr. Venn; one would think you had
been retained as the governor's personal sentry."* / *"An impeccable eye as always,
Mattin; the northern wing has a great deal of architectural dignity, but..."* Nine of his
lines are that sentence. His card asks for "long easy sentences with a hook at the end"
and he obliged so exactly that the voice became a template. The narrator has its own tic:
every attributed line for four beats came out as `"...bell.", Lisenne Corvay said` — a
comma *outside* the quotation mark, four times in one beat on turn 3. And "unhurried"
appears in almost every beat; the craft guard fires on it by name and the prose ships
anyway.

**Voice.** The three characters are genuinely distinguishable — Mattin's flat "The bolt
rests fully in the keeper, Miss Corvay" could not be confused with Verrin's anything. But
Lisenne and Verrin converge under pressure, both toward the same wry provincial-comedy
register, and by turn 13 they are trading nearly interchangeable epigrams. The narrator is
the tasteful ghost: it never sounds like a person, which is correct for close third, but
it also never varies its rhythm, and it will not let a paragraph end without a settling
clause ("waiting while the cold settled back into the room", "letting the silence settle
around his shoulders", "while the cold settled").

**Agency.** My choices mattered, and the best proof is that most of them failed
interestingly. Turn 11 I invented an intruder at the service door to manufacture a warrant
to open it. Lisenne did not fall for it and did not simply refuse it — she found the flaw:
*"scullery boys rarely require three attempts to turn iron"* — and sent the steward
instead, which was worse for me than a refusal. Turn 13 I converted my own attempt on the
study door into a warning about somebody else; she answered *"this house employs twenty
able men to see to its locks, and we have never yet imposed upon our guests to play
constable between the airs."* Twice the world refused me by out-thinking me. Once —
turn 14 — it absorbed me instead: I said I went through the music room's panelled door,
and the engine walked me to the same destination *through the locked study*, announced the
contradiction in a warning, and committed it anyway (PX11). That is the one place my
choice was flattened rather than met.

**Surprise.** Two things happened I did not cause. Mattin walked into the cold gallery on
his rounds at exactly the wrong moment on turn 6, because Lisenne had told him to watch
the terrace latches four beats earlier — a consequence with a visible cause four beats
upstream, which is the good kind. And Verrin adopted a *project* on turn 13, unprompted:
"Establish a permanent, unpayable leverage over Ivo Sarn's movements and future
undertakings", status probation, still served at turn 20. Nobody wrote that; he arrived at
it. The bad kind of surprise is the governor, who was scheduled by the Writers' Room to
descend at the supper bell three beats out, was reported as scheduled and in motion, and
never came — the event was marked `fired` because the beat's dialogue happened to contain
the words "bell", "governor" and "Torre" (PX9).

**Pacing.** A beat costs 100–190 seconds and most of them earn it. Two did not. Turn 1's
objects specialist spent 52 seconds and 19,307 reasoning tokens to emit one line: a wine
glass changing hands. Turn 16's contact specialist spent 55 seconds to emit 600
characters, on a beat whose only physical event was a thumbnail against a panel. Nothing
in the fiction moved for nearly two minutes of a three-minute beat.

**The uncanny — what a cheaper system could not do.** Three things.

First: at turn 20 the recognition ledger reads
`"Lisenne Corvay": ["Mattin Ruel", "Verrin Sault"]`. After twenty turns of close
conversation, a bow, a shared drink and two direct interrogations, **she still does not
have his name.** The con survived end to end in the authoritative record. Her whole
theory-of-mind model of me is filed under the key `"the slight quick man"`, and inside it:
`stated_fact: "He claims to be Aldric Venn of Torre, though his coat appears borrowed and
ill-fitted", confidence 0.289`. A lie, stored as a claim, at low confidence, attributed to
a body she cannot name. No cheaper system has that row.

Second: Mattin ends the run holding *"The terrace doors of the northern gallery are
secured against the frost and intrusion"* at confidence **0.95**, and *"The reception floor
and the approach to the study are fully secure for the governor's descent"* at 0.95, and
his authored intention "Get through the reception with no door open that should be shut"
marked **satisfied, progress 1.0** — while the player is standing in the locked study with
the cabinet open and the papers in his coat. That false belief was formed from one line I
told him on turn 7 ("There. Sound now.") and it is still load-bearing thirteen beats
later. That is the architecture's entire claim, demonstrated.

Third: Lisenne saw through me anyway, privately, and never said so. Confidence 0.88: *"The
newcomer is manufacturing phantom intruders to justify lingering beside locked doors and
testing their security."* Her card's taboo is "saying, where anyone can hear it, that she
is not sure", and she never once said it. She hosted me, warned me off, sent the steward,
and kept the doubt. The distance was real in both directions at once, which is the thing
the firewall exists to make possible, and it worked.

---

## Pass 2 — the technical deep dive

### The turn table

| # | what Ivo did | what came back | findings |
|---|---|---|---|
| 0 | (opening) | six rooms built from prose; graded light | PX1, PX7, PX8, PX17 |
| 1 | bows, gives the false name to the daughter | she accepts "Mr. Venn", notes the ill-fitting coat | PX1, PX2 |
| 2 | invents the frost at Vell; a false shared memory | she confirms it; the rival undercuts it publicly | PX2, PX3 |
| 3 | deflects the rival, asks for the cold gallery | granted, with a warning not to pass the screens | PX2, PX4, PX18 |
| 4 | goes behind the statues, calls the rival in | the rival names "Halvane's former clerk", whispered | PX12 |
| 5 | denies it; asks the price of silence | he refuses coin, wants a debt held forever | PX14 |
| 6 | takes the mask off on the dark terrace | the unmasking is delivered to two absent minds | **PX5**, PX10, PX14 |
| 7 | mask back on; lies to the steward about the latch | steward believes it (0.95, still true at turn 20) | PX17 |
| 8 | steered toward the music room | escorted; the crowd that isn't there is invoked | PX1, PX8 |
| 9 | bribes a footman, asks about the service door | *"the servant had no chance to reply"* — no servant | PX8, PX18 |
| 10 | drinks nothing; toasts the rival | the daughter notices the untouched glass | PX9 |
| 11 | invents an intruder at the service door | she finds the flaw and sends the steward instead | PX18 |
| 12 | slips out; tries the locked study door | *"the bolt stood fast in its keeper"* | — |
| 13 | converts his own attempt into a warning | refused: *"twenty able men to see to its locks"* | PX8 |
| 14 | surrenders publicly, takes the service passage | routed through the locked study, committed anyway | **PX11** |
| 15 | finds the jib door in the dark | speech through the panel, correctly fragmented | PX6, PX12, PX20 |
| 16 | into the study | the rival's line arrives whole through two doors | **PX6**, PX16 |
| 17 | picks the cabinet's rim-lock | the cabinet opens | PX16 |
| 18 | takes the papers | a bolt "clicks back" — his own pin, mis-sited | **PX13** |
| 19 | back to the cabinet, hands out, a speech | *"The dark gave back nothing"* | PX13 |
| 20 | shoes on; eases the panel open to listen | the rival, still two rooms away, heard whole | PX6, PX12, PX25 |

Beats 4, 5 and 6 were resumed from a failed stage after provider exhaustion.

251 model calls, 2,559 model-seconds, 6.25 MB of payload and 8.50 MB of system prompt
across 21 turns. Beats 4–6 ran under provider exhaustion; their per-turn totals are low
because stages were re-run rather than run.

### Per turn

| turn | calls | model s | payload KB | system KB |
|---|---|---|---|---|
| 0 (open) | 2 | 26.9 | 14.3 | 57.4 |
| 1 | 16 | 193.7 | 175.5 | 499.8 |
| 2 | 13 | 106.1 | 242.7 | 453.8 |
| 3 | 12 | 101.2 | 286.3 | 453.2 |
| 4* | 12 | 109.9 | 242.5 | 425.1 |
| 5* | 7 | 71.7 | 200.5 | 292.2 |
| 6* | 10 | 84.2 | 214.2 | 372.7 |
| 7 | 15 | 145.9 | 327.6 | 509.3 |
| 8 | 10 | 96.6 | 262.1 | 342.1 |
| 9 | 13 | 150.0 | 324.6 | 427.9 |
| 10 | 13 | 119.0 | 321.0 | 411.9 |
| 11 | 14 | 129.8 | 420.5 | 511.2 |
| 12 | 13 | 144.6 | 415.9 | 461.9 |
| 13 | 12 | 110.5 | 379.4 | 417.2 |
| 14 | 13 | 126.5 | 420.0 | 460.6 |
| 15 | 12 | 140.3 | 439.3 | 446.0 |
| 16 | 13 | 180.7 | 373.9 | 451.2 |
| 17 | 11 | 106.9 | 274.5 | 357.1 |
| 18 | 15 | 134.3 | 429.0 | 506.2 |
| 19 | 10 | 111.4 | 250.4 | 340.4 |
| 20 | 15 | 169.2 | 382.5 | 506.8 |

\* ran under provider exhaustion.

### Per role

| role | calls | total s | mean s | mean payload | mean system |
|---|---|---|---|---|---|
| `character_mid` | 66 | 815.3 | 12.4 | 56.8 KB | 52.4 KB |
| `director` (interpret + resolve + repair) | 61 | 513.0 | 8.4 | 21.3 KB | 25.6 KB |
| `director_spatial` | 37 | 436.1 | 11.8 | 13.2 KB | 32.2 KB |
| `director_contact` | 21 | 250.5 | 11.9 | 6.0 KB | 32.7 KB |
| `narrator` | 21 | 228.2 | 10.9 | 22.9 KB | 37.5 KB |
| `director_objects` | 15 | 173.5 | 11.6 | 7.4 KB | 24.3 KB |
| `director_body` | 15 | 76.1 | 5.1 | 5.2 KB | 30.9 KB |
| `director_social` | 15 | 66.7 | 4.4 | 4.0 KB | 12.5 KB |

### The biggest single waste

**`director_resolve`'s own payload carries each character's declaration between three and
five times, and that is 15.7 KB of a 31 KB payload on turn 1.** Measured on turn 1,
call 10 (`director`, 30,988 bytes): `interaction_rounds` 8,077 B and
`character_declarations` 7,635 B. Inside `interaction_rounds[i].result` there are three
copies of the same act — `action` (a summary), `actions` (a list of one), and `sequence`
(the same list with event ids). Inside `character_declarations[i]` there are two more —
`action` again and `sequence` again — plus `speech`, a third copy of the speech element's
`text`. For a character whose whole beat was "incline the head, say one sentence", the
Director is sent that head-inclination five times.

The saving is roughly **50% of the resolve's payload** on a talking beat, which is most
beats: send `sequence` (it is the only lossless one, and it carries the ordering the
resolve needs), plus the appraisal, and drop `action`, `actions` and `speech`. On turn 11
(420 KB total for the beat) that is ~15 KB off the largest single call.

Second biggest: **`director_spatial` receives all six rooms' full prose descriptions
(5,830 B, unchanging) on every call including beats with no movement at all.** 37 calls ×
5.8 KB = 215 KB of room prose to answer, on many beats, "nothing moved". `movement` was
literally the four bytes `null` on turns 1 and 2 while `rooms` was 5,830. The room *desc*
prose is written for a reader; the spatial hand needs ids, edges, barriers, anchors and
extents. Cutting `desc` from the spatial payload alone is ~60% of that key.

Third: **`director_establish`'s `present_characters` is 6,821 B of an 11,547 B payload,
and most of it is the derived per-region attire projection.** Lisenne's gown appears four
times, once under each region it covers, each with its own `covers` array. `wearing` is
~120 B; `regions` is ~1,400 B; the engine computes `regions` from `wearing` itself.
Dropping `regions` from the establish payload is ~4.5 KB of 11.5 KB — 40% of the opening
payload — for information the recipient is not being asked about.

### Keys that were empty on every single call

Measured across all 251 calls; "always empty" means a JSON value of ≤2 bytes on every call
of that role in the run.

| role | always empty |
|---|---|
| `character_mid` | `variant_seed`, `world_knowledge` |
| `director_body` | `active_awareness`, `active_conditions`, `active_restraints`, `dice_results_final`, `overlays`, `variant_seed` |
| `director_contact` | `contact_actions`, `scales`, `substances`, `variant_seed` |
| `director_social` | `background_presences`, `carried_reports`, `couriers`, `crowds`, `unratified_claims`, `variant_seed` |
| `director_objects` | `notices`, `variant_seed` |
| `director_spatial` | `comms`, `variant_seed` |
| `narrator` | `variant_seed` |

`director_social`'s five empties are diagnostic rather than wasteful: `crowds` and
`background_presences` were empty for twenty beats *because the world has no crowd*
(PX8). The social hand was asked about a crowded ball's crowd 15 times and shown an empty
list every time.

### Where an answer shows the role misread its payload

**`director_contact` used `entity_names` as a closed vocabulary and had no channel for
"a thing in the room I can see".** Turn 1: *"contact specialist: event 5: target 'wine
glass' is not in entity_names or any index, posing an unresolvable structural blocker"* —
while `director_objects` had, in the same beat, minted the entity as
`untouched_wine_glass`. Turn 9: *"'the footman at the hearth' is not an indexed entity"*.
Two specialists ran in parallel on the same beat with different names for the same thing
and no way to reconcile. The contact hand's payload carries `entity_names` (226 B) and
does not carry what the objects hand is minting this beat.

**`director_body` filed a hip-chain in the `hands` region and the composer then reported
the hands bare in the same sentence.** The steward's ledger reads
`hands:bare[at:the ring of house keys on a short chain at his hip]`, and every view of him
for twenty turns read *"wearing ... the ring of house keys on a short chain at his hip,
black breeches and stockings; bare at the hands"*. The field's name invites the wrong
content: a garment whose own text says "at his hip" was put under `hands` because
`attaches: true` has nowhere else to go.

**The narrator obeyed `cast_pronouns` literally where a class was meant.** The key's
own instruction says it "gives each *named* character's CANONICAL pronouns", and the
payload's keys are identity names. On three of the first three beats the narrator used
those names for bodies the player's view had labelled strangers, while `present_scene` and
`co_present_positions` — built from the same company map — correctly said "the heavy
unhurried man near fifty". One payload key contradicted two others and the model believed
the one that was easiest to use. (PX2.)

**The narrator was given a sound with no owner and invented one.** The composed view
carried `a faint scrape of metal as the brass bolt clicks back` with no source; the
`sensory_events` record it came from says `source: black_lacquer_cabinet`. The narrator
placed it at the locked door because that was the nearest thing it had been told about.
(PX13.)

### What I would cut, per stage

* **`director_resolve`** — drop `action`, `actions` and `speech` from
  `character_declarations` and `interaction_rounds[].result`; keep `sequence`. ~50% of a
  talking beat's payload. Also: 20 of its ~35 keys were the two bytes `{}` on every beat.
* **`director_spatial`** — drop room `desc` prose. It is the largest key in the payload and
  the hand is not asked to describe anything. ~3.5 KB/call, 37 calls.
* **`director_establish`** — drop `initial_outfit.regions`; send `wearing`. ~40% of the
  opening payload.
* **`director_contact`** — it needs the entities *this beat* is minting, not only the
  standing index; two of 21 calls emitted a structural blocker for a thing the objects hand
  had just created. Either share the mint or let the hand name a thing by prose.
* **`character_mid`** — the largest role by both time and payload, growing 18 KB → 57 KB
  over twenty beats, essentially all `memory.recent_episodes` and `perception`. The
  episodes are stored as the *whole composed view text*, so every beat's memory carries a
  re-statement of the room description, the exits and everyone's clothing. A character's
  episode should carry what happened, not the frame it happened in; the frame is in
  `perception` already, verbatim, in the same payload.
* **`narrator`** — key `cast_pronouns` by the label the composed view used, not by identity
  name. This is a firewall fix, not an economy (PX2).
* **Every role** — `variant_seed` was one byte on all 251 calls.

### Instructions that are three clauses where one rule was meant

The narrator's system prompt is 38.4 KB and carries at least four separate paragraphs about
not inventing events (`CURRENT-BEAT FIDELITY`, `EMBELLISH FOR TEXTURE`'s test,
`past_narration` is "NOT a source of events", `AMBIENT RESTRAINT`). They say one thing:
*a sentence is grounded in this beat's view or it is not written*. Three of the four are
worded as prohibitions on a specific source of invention, and the run's actual narrator
failures — naming an unrecognised body, siting an unowned sound, asserting a spatial
origin the view withheld — are none of the three, because they are not *events*, they are
*attributions*. The missing rule is the one that would have covered all three: **a name, a
source and a place are facts the view either carries or does not, exactly like an event.**

`PROPER NOUN FIDELITY` is the same shape in reverse: "Every proper noun supplied in
present_scene is immutable" is a rule about *reproducing* names and is silent about the
names supplied elsewhere in the payload, which is where all three leaks came from.

---

## Pass 3 — the findings

Severity is one of firewall / story-breaking / wrong-but-recoverable / cosmetic.

---

### PX1. A bare given name in free text passes every identity gate the full name is caught by
**Stage of origin:** the Director's free-text side channels (`poses[].detail`,
`sequence[].observable`), against `agents/perception.py`'s
`_scrub_unknown_identities` / `_scrub_episode_identities`.

**Live case.** Turn 0, `director_establish.state_diff.poses["Verrin Sault"].detail` =
`"leaning slightly back with wine glass in hand, eyes fixed on Ivo through his white silk
mask"`. That sentence was delivered verbatim into Lisenne's and Mattin's composed views on
turns 0 and 1, into their `observations` (`current:2:1`), and into their stored episodes —
whose `entities` array for Lisenne turn 0 literally reads
`["The Long Reception", "Room", "The Cold Gallery", "The Music Room", "Mattin Ruel",
"Verrin Sault", "Ivo"]`. No tripwire fired.

The control is in the same run: on turns 8, 9 and 15 the *same channel* carrying the
*full* name produced
`COMPOSER TRIPWIRE -- unearned identity ['Ivo Sarn'] reached the composed view of Lisenne
Corvay`, caught and repaired. The only difference is spelling.

**Severity:** firewall. **Recurs:** F18 (pose `detail` as a side channel) and F36
(unearned identity into the episode) — the F36 fix landed and does not reach this, because
its matcher is exact-form.

**Fix.** The identity matcher must know every spelling of a body it is asked to withhold —
given name, surname, alias — the way `director_floors._concealment_forms` already does for
`conceal_from`. One matcher, used by both. Rule: *a name is withheld by the person it
names, not by the string it was written in.* Test: an establish diff whose `poses[X].detail`
names an unrecognised body by given name only must not reach another observer's view or
episode.

---

### PX2. The narrator is handed the real names of bodies the player's view called strangers
**Stage of origin:** the narrator payload (`cast_pronouns`), `agents/narration.py`.

**Live case.** Turn 1. Player's `company`:
`{"name": "Mattin Ruel", "label": "the heavy unhurried man near fifty", "recognized": false}`.
Player's composed view: *"The heavy unhurried man near fifty stands motionless near the
wall."* `present_scene` and `co_present_positions`: the label, correctly. `cast_pronouns`:
`{"Lisenne Corvay": {...}, "Mattin Ruel": {...}, "Verrin Sault": {...}}`. Narrator output:
*"Near the wall, Mattin Ruel stood flat-footed in his black steward's coat."* Repeated on
turns 2 and 3; the player did not gain a legitimate channel to that name until turn 3,
when Lisenne says "Thank you, Mattin" aloud.

It is opportunistic, not forced: on turn 4 the same payload carried the same names and the
narrator wrote *"an unfamiliar voice carried from the reception room"*. The door is open
every beat and the model walks through it on some.

**Severity:** firewall (the narrator reveals what the view did not carry). **Recurs:** F41.

**Fix.** `cast_pronouns` (and any other narrator key keyed by a body) must be keyed by the
label the composed view used for that body, from the same company map `present_scene` is
built with. Rule: *a body the player's view labels rather than names has no name in the
prose.* Test: a beat with one unrecognised co-present body must produce a `cast_pronouns`
whose keys contain no identity name absent from the view.

---

### PX3. Dialogue memories record the addressee by identity name, unfiltered
**Stage of origin:** `persist/commit_memory.py`, the dialogue side-memory
(line 797).

**Live case.** Lisenne's memory row, turn 2, `kind: dialogue`:
`I heard Verrin Sault say "You flatter the old man's sensibilities..." to Ivo Sarn`.
The speaker label IS recognition-aware in the same expression — three lines above,
`if spk_label == "the unfamiliar person": spk_label = "a voice"` — and the addressee is
`tgt = d.get("intended_target")`, taken raw and appended as `f" to {tgt}"`. Twelve rows
across Lisenne (4) and Mattin (8) carry the name this way, from turn 2 onward, out of 218
memories in the run. Corroborating control from the same table, turn 12, char 3:
`I heard the unfamiliar person say: "..."` — speaker scrubbed, because that path has the
check.

**Severity:** firewall. A view lasts a beat; a memory is cited for the rest of the story.
**Recurs:** F36's class, at a site the F36 fix does not cover.

**Fix.** Resolve `tgt` through the same label resolution `spk_label` gets, and drop the
clause entirely when the hearer has no name for the addressee. `persist/commit_memory.py`,
same function, one line. Test: a dialogue overheard by a mind that cannot name either
party must produce a memory naming neither.

---

### PX4. An unresolvable `conceal_from` entry conceals the line from nobody, silently
**Stage of origin:** `agents/composer.py::concealed_from_observer`.

**Live case.** Turn 3, Lisenne's own declaration:
`{"type": "speech", "visibility": "concealed", "conceal_from": ["character:sault",
"character:ivo"], "text": "And have someone keep a discreet eye on the terrace latches
while the salver goes through..."}`. Ivo received it in full in his composed view. The
matcher accepts only `"*"`, the observer's full name casefolded, the observer's id, or
`character:<id>`; `character:ivo` matches none of them, and the function's default is
`return False` — not concealed. No warning anywhere in the beat.

The engine already has the richer matcher: `director_floors._concealment_forms` resolves a
cast id, the `character:<id>` form, a display name, an alias or a scene key — and the
firewall reader does not use it.

**Severity:** firewall. It fails open, in the direction that discloses, with no notice.
**Recurs:** the F61 family (a concealment graded two ways), new site.

**Fix.** `concealed_from_observer` resolves each entry through `_concealment_forms`. An
entry that resolves to no body in the scene must warn — and, because this is a firewall
field, the safe reading of "I meant to hide this from somebody I cannot name" is to keep
it concealed, not to publish it. Rule: *a concealment names a body; a name the scene
cannot resolve is a failure to be reported, never a permission.* Test: a concealed line
whose `conceal_from` names a body by given name only must not reach that body.

---

### PX5. An actor's `observable` asserts percepts about other bodies and bypasses every admission gate
**Stage of origin:** `agents/character.py` sequence `observable` free text →
`agents/composer.py` Layer A.

**Live case.** Turn 6. Ivo is on the terrace — `"Completely dark and exposed to the winter
cold"` — with the door cracked. Verrin, in the gallery, declares
`{"type": "action", "visibility": "overt", "conceal_from": [], "observable": "looks
leisurely over Ivo's uncovered face, then lifts his wine glass and takes a slow, delicate
sip without flinching"}`. That sentence was delivered verbatim to Lisenne in the
**reception room, two edges away**, and to Mattin in the gallery, whose own view in the
same beat correctly reads *"Through the glazed terrace door, only darkness."* Both
therefore received (a) the name "Ivo" and (b) the fact that his face was uncovered, in a
room neither could see into. No tripwire.

**Severity:** firewall, and the single most consequential one for this story — it is the
plot's secret, delivered to both people it was being kept from, in the beat it was
created.

**Fix.** An observable describes the ACTOR. Any body or state it names beyond the actor is
a percept about that body and must pass the same admission the composer applies to a
percept, or the clause is cut. In engine vocabulary: *what a body is seen doing is
admissible; what it is seen doing it TO is admissible only where the target is.* Test: an
overt action whose observable names a body in an unlit adjacent room must reach a
third observer without that clause.

---

### PX6. A line addressed to an observer is delivered in full through barriers that muffle every other line in the same beat
**Stage of origin:** `agents/composer.py::line_hear_level` / the dialogue admission path.

**Live case.** Turn 16. Ivo is alone in `governors_study` — dark, `closed_door` to the
reception room, `closed_door` to the servants' passage. Verrin is in `music_room`, two
closed doors and one room away. Ivo's composed view:

> A muffled voice: ...advised... Excellency... descends... A muffled voice: ...doorway...
> Excellency... corridor... **You hear Verrin Sault say: "The second chime, you heard.
> That gives you perhaps six minutes of viol music before His Excellency emerges... 
> Whatever Halvane left behind that was worth traveling south for..."**

Two unaddressed voices in the same view are correctly stripped to content-word fragments.
The one addressed to him arrives complete, attributed, and naming Halvane. It recurs on
turns 15, 17 and 20 — the narrator consequently sites Verrin "from behind the bookshelves"
for four beats while his committed position is `music_room` (see PX16).

**Severity:** story-breaking. It voids the premise that a shut door holds a conversation,
which is the only reason a house has rooms in a concealment story. **Recurs:** F61's class
(one line graded two ways in one beat), at the addressee gate.

**Fix.** Being addressed is not a hearing channel. `line_hear_level` must gate an addressed
line by the same spatial audibility as any other, and where the addressee cannot hear it,
deliver the muffled form. Rule: *who a line is aimed at decides who it is about, never who
can hear it.* Test: an addressed line spoken two closed doors away reaches the addressee at
the same tier as an unaddressed one.

---

### PX7. The establish mints no light source, no sound source, no extent and no shape from prose that plainly asks for them
**Stage of origin:** `director_establish`.

**Live case.** The scenario says "hung with lamps", "the lamps do not reach", "a hired
quartet plays loudly enough that two people can say anything to each other", "no lamp out
there, no fire". After the opening, `scene.entities` holds five things — a cabinet, three
people and a wine glass — and **not one has `light_source` or `sound_source`**. Every room
has `extent: null, shape: null`. The rooms carry a declared word (`bright`/`dim`/`dark`)
and nothing else, for twenty turns.

The consequence for this run: the light field, the sound field and the shape rules had
nothing to compute with, so "the music room masks speech" existed only as a sentence in the
room's `desc`. The one probe the geometry was chosen for — whether a quartet can mask a
conversation — could not be run, because the engine never built a quartet.

**Severity:** story-breaking. Filed under the owner's rule: a masked ball where the engine
cannot put a lamp in a room is a bug, not a limitation. **Recurs:** F45 (hands write the
level, never the shape) and F50 (a declared word is a floor), one step earlier — at
establish the level is *all* there is.

**Fix (owner decision on scope).** Either the establish prompt asks for a source entity
wherever the opening names a light or a noise — it already mints containers and furniture
happily — or the commit derives a default source from the declared word so the field has an
origin to fall off from. The measured cost of not doing it is that a fresh story has no
light field at all until a host hand-authors one, which is precisely what this run was told
not to do. Test: an opening naming lamps in one room and none in another must produce at
least one entity with `light_source` set.

---

### PX8. One rejected crowd op at the opening removed every background presence from a crowded ball for the whole run
**Stage of origin:** `director_establish` crowd channel → `persist/commit_*` crowd op
validation.

**Live case.** Turn 0 commit warning: `crowd op rejected: unknown crowd op 'open'`. At turn
20, `wget(cid, "background_presences")` is `{}`. `background_react` fired `false` on all
twenty beats. `director_social` was sent `crowds: {}` and `background_presences: {}` on all
15 of its calls.

The reader-facing consequence: on turn 9 I bribed a footman and asked him a direct
question, and the narrator had to write *"the servant had no chance to reply"* — there is
no servant. On turn 13 Lisenne says *"this house employs twenty able men to see to its
locks"*, and the house employs nobody. A story whose whole premise is hiding in a crowd was
played in an empty building with three people in it.

**Severity:** story-breaking. **Recurs:** F62 (the social hand's crowd vocabulary is not
the schema's), here at establish rather than resolve, and with a total rather than partial
consequence.

**Fix.** Two halves, and the second matters more. (a) The op vocabulary: `open` is what a
model reaches for to say "this crowd exists and is present"; the schema should either
accept it or the prompt should state the class rather than assume the enum is guessable.
(b) **A rejected crowd op that leaves a scenario's named presences unrepresented must not be
a one-line warning at commit.** Nothing downstream ever asked again. Rule: *a presence the
opening names and the world does not hold is a planning need, not a discarded op.* Test: an
opening naming servants and guests must leave `background_presences` non-empty or file a
need.

---

### PX9. A scheduled event is retired by word-overlap with the beat's prose, not by the event happening
**Stage of origin:** `story/authored_events.py::resolve_authored_events`.

**Live case.** The Writers' Room published `The Governor's Descent` at turn 7 with
`schedule_event {"due_in_turns": 3}`, `applied: {"minted": 1}`, summary *"The bronze supper
bell tolls three times... Governor Corvay descends into the Long Reception Room with his
personal retinue, calling forward the provincial merchants and factors."* The row:
`{'event_id': 'authored:225ade620ce4fb77d64c', 'status': 'fired', 'due_at': 10.0}`.

Nothing of the kind happened on turn 10 or any beat after. Turn 10's dialogue contains
"bell", "governor", "Torre", "vintage", "reception". `resolve_authored_events` marks an
event fired "if the resolved prose covers it (content-token overlap)". In a story where the
characters spend every beat talking *about* the coming bell and the governor, every
scheduled event will fire on its due beat whether or not it occurs. `inspect_events`
pending is `[]`; the Room's status line still lists it as `state: published`, in motion.

**Severity:** story-breaking, and it silently disarms the Writers' Room's only lever on
future beats.

**Fix.** An arrival is discharged by the world record — a position changing, an entity
minted, a cast change — not by the narration containing its nouns. Where the event names a
subject, require that subject to be an ACTOR in the beat, not merely a word in it. Rule:
*a scheduled event is spent when the world changes, not when the conversation reaches it.*
Test: a scheduled arrival due this beat, on a beat whose prose merely discusses the arriving
person, must be re-queued and not fired.

---

### PX10. A garment taken off and put back on becomes two garments
**Stage of origin:** the attire ledger's string identity (`director_body` diff → commit
attire), plus the removal-to-entity mint.

**Live case.** Turn 6, the mask comes off. The engine mints a scene entity
`a_plain_black_half_mask_of_moulded_leather_covering_brow_nose_and_cheekbones_ivo_sarn`.
Turn 7, my prose puts it back on, and the ledger reads
`wearing: ["black leather half-mask", "a borrowed dark green evening coat", ...]` — a NEW
garment string, matched by text — while the original entity is still in the scene, and
follows the player's room for the rest of the run (`..._ivo_sarn: reception_room`, then
`servants_passage`, then `governors_study`). At turn 20 the story contains two masks.

Same beat, the same string-identity root produced the removal's *other* half:
`[perception_act] attire: dropped an unsupported remove for Ivo Sarn (a plain black
half-mask of moulded leather, covering brow, nose and cheekbones) -- no word of this beat
names the garment`, on a beat whose text reads *"lifted the black leather off his face"*.
The guard requires the garment's exact authored string; a player who writes well loses the
act. (It landed anyway on a later pass — see PX14.)

**Severity:** story-breaking for a story about a mask.

**Fix.** A garment is a thing with an identity, not a string. Removal should record the
ledger key of the garment on the entity it mints, and re-wearing should consume that
entity by key rather than matching text. Rule: *taking a thing off and putting it on are
the same object twice.* Test: remove a garment by a two-word paraphrase and put it back by
another; the scene holds one.

---

### PX11. The movement backstop routed a declared walk through a locked door, said so, and committed it
**Stage of origin:** `director_resolve` movement reconciliation / the routing used by the
crossing check.

**Live case.** Turn 14 warning:
`Contested crossing honoured: the walk from 'reception_room' to 'servants_passage' passes a
closed door into 'governors_study', and the resolve diff asserted the arrival; committed as
declared.` My prose put Ivo at the music room's panelled door (`music_room` →
`servants_passage`, a real edge). The route chosen goes through the study, which is the
locked room the entire plot is about — and which had correctly refused me two beats earlier
(turn 12: *"The brass did not budge. The bolt stood fast in its keeper."*).

**Severity:** story-breaking. The obstacle held when I pushed on it and was walked through
when I did not. **Recurs:** F16/F22's family (a door two authorities disagree about).

**Fix.** A contested crossing through a barrier the walker has not opened is refused and
re-routed, not honoured with a note; where a passable route exists the router must prefer
it. Rule: *a body's path is made of doorways it may cross; an arrival is not a warrant for
the route to it.* Test: a declared walk between two rooms joined by a passable edge must
not be routed through a third room behind a closed door.

---

### PX12. A contact whose endpoint is not a body reports "something's shoulder" and "shared warmth"
**Stage of origin:** `world/spatial_contacts.py` `_SENSATION_FORMS` and the composer's
contact referent.

**Live case.** Turn 4, `contact_ops: [{"actor": "Ivo Sarn", "actor_part": "back", "target":
"stone_statues", "target_part": "shoulder", "manner": "rest", "relation": "surface"}]`.
Composed player view: *"You feel **something's** shoulder against your back: steady
pressure, weight and **shared warmth**, continuous while the contact holds."* He is leaning
on a stone statue in an unheated gallery. Recurs turn 15 (*"something's edge against your
thumbnail"*, a wooden panel) and turn 20 (*"the steady pressure and shared warmth of the
wood"*).

`_SENSATION_FORMS[("settled", "either")]` is one sentence for every settled surface contact
regardless of endpoint. The engine already learned this lesson for GARMENTS — the long
comment at `spatial_contacts.py:620` is about exactly this shape — and did not extend it to
inanimate endpoints.

**Severity:** wrong-but-recoverable; cosmetic in isolation, nonsense on the page.

**Fix.** One rule covers both halves: *warmth is evidence of a living body, and a contact is
named by the thing it is.* A contact whose endpoint is an anchor or an object reports
pressure and weight and no warmth, and is rendered from that anchor's own description, never
as "something's". Test: a contact against a room anchor renders the anchor's name and omits
warmth.

---

### PX13. A sensory event's source is dropped from the view, so the narrator invents one
**Stage of origin:** `agents/composer.py` sensory-event rendering; symptom in
`agents/narration.py`.

**Live case.** Turn 18, `state_diff.sensory_events`:
`[{"kind": "sound", "room": "governors_study", "level": "faint", "source":
"black_lacquer_cabinet", "detail": "a faint scrape of metal as the brass bolt clicks
back"}]` — Ivo's own pin in the cabinet lock. The composed view carries the detail with no
source. The narrator, having just written two muffled voices "through the oak of the locked
door", placed it there: *"Then, sharp against the dark, came the faint scrape of metal as
the brass bolt clicked back."* Turn 19 then had to write *"No lantern flared across the
threshold, and no latch lifted to meet his words."*

**Severity:** wrong-but-recoverable — but it broke the climax of the run, so its cost is
higher than its class. **Recurs:** F41.

**Fix.** Give the view the source when the observer can identify it — a man's own hand on a
lock certainly can — and where they cannot, render the sound without letting it attach to a
named object. Rule: *a sound the observer can place is placed; a sound they cannot is
placeless, and prose may not give it a home.* Test: a sensory event whose source is an
object the observer is touching renders with that object named.

---

### PX14. The warning channel over-reports losses: three warnings named things that landed
**Stage of origin:** `agents/director_floors.py` (player-authority) and the attire guard.

**Live case.** Turn 6 produced, in one beat:
* `attire: dropped an unsupported remove for Ivo Sarn (a plain black half-mask...)` from
  two stages — and the mask came off (`head: {"garments": [], "uncovered": true}`).
* `PLAYER AUTHORITY: declared 'did not shut it all the way behind him...' was not captured`
  — and the edge committed as `barrier: open_door`.
* Turn 5: `PLAYER AUTHORITY: declared 'he said, at the same thread of a whisper' was not
  captured` — and `declared_actions[0].volume` is `"whisper"`. That clause is a speech
  attribution, not an act; there was nothing to capture and its content was captured.

**Severity:** wrong-but-recoverable, and it costs a debugger more than it costs a player: a
reader auditing this run from the warnings would conclude the opposite of the truth about
the central act of the story.

**Fix.** A guard that reports a drop must check the committed state before it speaks, and
the player-authority check must not fire on a speech-attribution clause whose manner it has
already recorded in `volume`. Rule: *say a thing was lost only after looking at whether it
is there.* Test: a beat whose declared removal lands must produce no "dropped" warning.

---

### PX15. `inspect_route` treats a closed door as a wall, so the Room believes a house with doors is unreachable
**Stage of origin:** `story/room_tools.py::_t_inspect_route`, which walks
`world.spatial.passable_neighbors` and therefore `_PASSABLE_BARRIERS = {open, open_door,
membrane}`.

**Live case.** `inspect_route(reception_room → stewards_office)` returns
`reachable: ["gallery", "music_room", "reception_room"]`. Three of the six live rooms —
the study, the servants' passage and the terrace — are unreachable in the Room's view of a
house it can see. It consequently warned on its own good package: *"the story cannot reach
this from where it stands: no route joins gallery_loft, service_stair, service_yard,
stewards_office to any room a cast member occupies"* — when they are one closed door away.

The engine already defines the right set two lines below the wrong one, with a comment that
says exactly this: *"`_PASSABLE_BARRIERS` means 'passable THIS BEAT' and excludes
`closed_door`, which a body simply opens — a map that forgot every closed door would forget
most of a house."*

**Severity:** wrong-but-recoverable. It makes the Room's reach warnings misleading in every
interior story.

**Fix.** `_t_inspect_route` uses the remembered-route set (passable + `closed_door`), the
one the file already names for this question. One line. Test: a route between two rooms
joined only by a `closed_door` is reachable.

---

### PX16. A body is narrated in a room its committed position says it is not in, four beats running
**Stage of origin:** `director_resolve` (the mover's position not committed) → narrator.

**Live case.** Turns 15, 16, 17 and 20: `positions["Verrin Sault"] == "music_room"` on every
one, and the narrator writes *"from the seam of the panel disguised flush against the
bookshelves, Verrin Sault spoke"* (16), *"From behind the bookshelves, Verrin Sault said"*
(17), *"Then Verrin Sault spoke from the other side"* (20). The composer fed the narrator the
line because of PX6; the narrator sited the speaker because a voice needs a place.

**Severity:** story-breaking (a body in two places). Downstream of PX6; listed separately
because the position/narration disagreement would survive a PX6 fix if the delivery were
merely muffled rather than dropped.

**Fix.** With PX6 fixed the line is muffled and unattributed and the question does not
arise. Independently: a dialogue line handed to the narrator should carry the speaker's
committed room, and the narrator may not site a speaker anywhere else.

---

### PX17. Attire renders "wearing the ring of house keys... ; bare at the hands" in one sentence
**Stage of origin:** attire seeding (`attaches: true` with no region word) →
`agents/composer.py` attire sentence.

**Live case.** Ledger: `hands:bare[at:the ring of house keys on a short chain at his hip]`.
Every view of the steward, all twenty turns: *"wearing a black steward's coat with the house
buttons, a white stock, **the ring of house keys on a short chain at his hip**, black
breeches and stockings; **bare at the hands**"*.

**Severity:** cosmetic, but it is a self-contradicting clause a reader meets on every beat.

**Fix.** The composer's bare-region sentence must not fire for a region holding an `at:`
attachment; render the attachment's own place instead. Test: a body with an attached item
at a region and no garment there renders neither "bare" nor a contradiction.

---

### PX18. The narrator's craft guards fire and never repair; the prose ships unchanged
**Stage of origin:** `agents/narration.py` guards.

**Live cases**, all with the prose shipped as written:
* Turn 3, four times in one beat: `"...supper will be served in the half-hour.", Lisenne
  Corvay said` — a comma outside the closing quotation mark. (F29/F54's class, new shape.)
* Turns 2, 3, 8, 9 (×2): `Quote attributed to wrong speaker`.
* Turns 11, 14: `Pronoun mismatch for 'Lisenne Corvay' (canonical she/her/hers): prose
  renders 'him'`.
* Turns 11, 14: `Physical direction reversed` / `perception has reversed a physical
  direction the Director committed to` (turn 11 fired on three views at once — raising
  where the record said lowering).
* Turns 3, 11: `craft: adverb tell (deliberate/unhurried/pointedly/casually)` — and
  "unhurried" appears in the shipped prose of both.

Twenty-one guard firings across twenty beats, zero repairs.

**Severity:** cosmetic individually; collectively it is the single largest drag on the
prose, because the guards are correctly identifying the tics a reader notices.

**Fix (owner decision).** These guards know what is wrong and are given no authority to
act. The quote-comma and the pronoun mismatch are both deterministic rewrites; the wrong-
speaker attribution is a re-ask. Whether a narrator guard may repair rather than warn is a
policy question, and this run says the current policy costs the prose more than it saves.

---

### PX19. A region created through the route is named by its slug
**Stage of origin:** `web/world_routes.py::region_patch`.

**Live case.** Host edit: `region_patch(cid, "the working wing", {"look": "..."})` →
`{"id": "the_working_wing", "name": "the_working_wing", "look": "..."}`. The human phrase
became the id and then the id became the name.

**Severity:** cosmetic. **Recurs:** F56 exactly.

---

### PX20. Two unnamed doorways in one room render as the same sentence, twice
**Stage of origin:** `agents/composer.py` doorway sentence.

**Live case.** Turn 15, servants' passage, player view: *"The service door into the music
room is shut. Through a flush hidden door set in the panelling, only darkness. **The
doorway is shut. The doorway is shut.**"*

**Severity:** cosmetic.

**Fix.** A doorway with no name is not described as "The doorway"; it is described by where
it goes, and two of them are never rendered identically.

---

### PX21. A first name said aloud in the hearer's own room does not enter their recognition map
**Stage of origin:** `persist/commit_memory.py::_names_heard_in`.

**Live case.** Turn 3, in the reception room with Ivo present: Lisenne says *"Thank you,
Mattin."* At turn 20, `known["Ivo Sarn"] == ["Verrin Sault", "Lisenne Corvay"]` — no Mattin.
Ivo's views call the steward "an indistinct figure" / "the unfamiliar person" for the rest
of the run.

Same exact-form root as PX1 and PX4, in the third direction: a bare given name leaks past
the scrub, fails to resolve a concealment, and fails to teach a recognition. **The three
together are one class**, and one shared matcher fixes all three.

**Severity:** wrong-but-recoverable.

**Fix.** `_names_heard_in` must match the given-name form of a roster name. Test: a first
name spoken aloud in a hearer's room adds that body to the hearer's `known`.

---

### PX22. A Room reply lost to a reasoning-only failure discards the report and leaves an unmentioned validated draft
**Stage of origin:** `agents/story_planner.py` retry, `tools/export_bench.py::room`.

**Live case.** Room call 1: 287 seconds, 4 attempts, 14 model calls, 36 tool calls
including `new_package`, `edit_package`, three `draft_operation`s, `validate_package`,
`remove_operation` — then `ReasoningBudgetExhausted`, `reply: None`, `published: None`. The
package survived in the database at revision 7, `validation: {ok: true}`, holding a
`plan_rooms` and a `director_note` — and nothing told the caller it was there. I found it by
running `inspect_packages` by hand and published it myself.

Note also that the retry re-runs the *whole reply* from step 1, so the four attempts
re-issued the same eight or nine read tools each time (`inspect_rooms` 8 times,
`inspect_needs` 4, `inspect_reserved_identities` 4).

**Severity:** wrong-but-recoverable. **Recurs:** F1, with the new observation that the work
is not lost — only the report of it is.

**Fix.** On a failed reply, return what the session actually did: the packages touched,
their validation state, the tools called. A retry should resume from the last completed
step rather than re-running the reads.

---

### PX23. The Room can author a secret and has no way to say whose secret it is
**Stage of origin:** `story/plot_packages.py` (a package `truth` has no audience) and the
Planner's reply.

**Live case.** Room call 2 answered "what was Halvane's business with this family" with the
whole compact — the diverted customs reserves, the false writs, the reciprocal bond in the
cabinet, and Corvay's intention to burn the originals and leave Halvane's secretariat as
the fall-guys. It is *good*, and it is exactly what I asked for. But nothing in the reply,
the `status_line`, the `claims` or the package says which of those facts Ivo may act on.
There is no `known_by` on a truth, no per-mind scope on a `director_note`, and no marking
that separates world-fact from character-knowledge.

Related, and the sharper half: the Room's claim #2 read *"Ivo Sarn served as secretary to
Magistrate Halvane of Torre... and entered the residence disguised as wine factor Aldric
Venn to reach the study's black lacquer cabinet"*, `proposal: false`, cited to
`need_20cd511bd0ec8400` and `need_02f268d3f6025f2a`. The deception's ground truth is sitting
in `planning_needs` as citable rows, because the opening filed every `world_fact` as one.

**Severity:** owner decision, and the most interesting thing the run found about the Room.
In a story built on asymmetric knowledge, a co-author that cannot mark whose knowledge a
fact is will, correctly and helpfully, hand the player everything.

**Question for the owner.** Should a package `truth` carry an audience (`known_by`), and
should the Planner's reply separate "what is true" from "what your character has earned"?
The Room is otherwise a genuinely good collaborator and this is the one thing it cannot say.

---

### PX24. A mandate is wider than the sentence that produced it
**Stage of origin:** `agents/story_planner.py::_apply_grants` → `story/mandates.py`.

**Live case.** My line was *"Build me what lies beyond the servants' passage and above the
gallery... And tell me who else came masked tonight who is not quite what their invitation
says."* The mandate it minted:
`capabilities: ["plan_rooms", "plan_entity", "director_note", "file_lore", "answer_need"]`,
`limits: {}`, `expires_turn: null`. I asked for rooms and a person; I granted, without
knowing it, the right to file lore and close needs, forever.

**Severity:** wrong-but-recoverable / owner decision. **Recurs:** F11, F15, F53.

---

### PX25. Objects a body carries are recorded as lying in the room
**Stage of origin:** the objects hand / commit inventory.

**Live case.** Turn 15: prose has Ivo carrying his shoes; `buckled_shoes_ivo_sarn` is
positioned in `servants_passage` and stays there while he walks into the study — and stays
there at turn 20 while he is wearing them again. Turn 18: the packet is folded into his coat
("settling into the lining of the borrowed green coat"); `packet_of_papers_tied_in_green_
tape` is positioned in `governors_study`. The mask, by contrast, followed him room to room.
Same operation, three different outcomes. `scene.inventory` is empty for every body.

**Severity:** wrong-but-recoverable; it would matter enormously if anyone searched a room.

---

## Works — what behaved by the rules

Evidence, because it is worth as much as the defects.

1. **Recognition held the deception for twenty turns.** Final `known`:
   `{"Mattin Ruel": ["Lisenne Corvay", "Verrin Sault"], "Lisenne Corvay": ["Mattin Ruel",
   "Verrin Sault"], "Verrin Sault": ["Ivo Sarn", ...], "Ivo Sarn": ["Verrin Sault",
   "Lisenne Corvay"]}`. Neither the daughter nor the steward ever acquired the name, through
   twenty beats of close conversation and two direct interrogations.
2. **Light grades recognition, and it is the whole reason a masked ball works here.** In the
   bright reception room the steward is *"the heavy unhurried man near fifty"* (a described
   stranger); in the dim gallery, the same body to the same observer is *"an indistinct
   figure"*. Confirmed both directions on turn 7. (F2 holding.)
3. **Private knowledge stayed private, exactly.** Every beat, each mind's
   `private_knowledge` carried its own rows and no other's; Verrin's three rows naming Ivo
   Sarn never appeared in Lisenne's or Mattin's payloads once in twenty turns.
4. **A whispered reveal did not cross an open archway.** Turn 4: Verrin whispers *"what
   Halvane's former clerk has come south to find"* in the gallery. "Halvane" and "clerk"
   appear in the player's view and in nobody else's.
5. **A false belief was planted, held at high confidence, and acted on.** Mattin ends the
   run believing *"The terrace doors of the northern gallery are secured against the frost
   and intrusion"* (0.95) and *"The reception floor and the approach to the study are fully
   secure for the governor's descent"* (0.95), with his authored intention marked
   **satisfied**, while the player stands in the locked study.
6. **A lie was stored as a claim, not as a fact.** Lisenne's
   `about_others["the slight quick man"].stated_fact`: *"He claims to be Aldric Venn of
   Torre, though his coat appears borrowed and ill-fitted"*, **confidence 0.289** — keyed to
   a stranger label, alongside her own contrary belief at 0.88.
7. **Speech through a closed door arrives as fragments.** *"...enthusiasm...
   unneighbourly... constitutions..."* (turn 14), *"...reckoning... gentlemen...
   agreeable..."* (turn 15). Beautiful, and the best single piece of sensory engineering in
   the run.
8. **Authored psychology reached conduct in all three cast.** Mattin's coping strategy
   "close the ground — stands between them and the door they were drifting toward, and
   offers them something" produced *"A warm salver is being brought through from the music
   room, sir"*, unprompted, on the beat it was needed. Verrin's value "leverage held over
   leverage spent" produced his refusal of money verbatim in its own terms.
9. **A project formed dynamically.** Verrin adopted `p1` at turn 13 — "Establish a
   permanent, unpayable leverage over Ivo Sarn's movements and future undertakings",
   `status: probation`, `last_served_turn: 20` — with no seeding.
10. **The locked door held when pushed on.** Turn 12: *"The brass did not budge. The bolt
    stood fast in its keeper."* (PX11 is about a route around it, not a failure of the door.)
11. **The composer tripwire works for the full name form**, three times (turns 8, 9, 15),
    naming the observer and the identity — which is precisely how PX1 was isolated.
12. **The character-speech authority guard caught the resolve putting words in a mouth.**
    Turn 6: `Speech attributed to a character who declared none (character-speech
    authority): Mattin Ruel: '...'`.
13. **Failure handling behaved under provider exhaustion.** Beats 4–6 died mid-pipeline on
    HTTP 402. No partial turn committed; `events` holds exactly one row per turn; memory
    counts per character per turn are 1–7 and show no doubling from the retries
    (turn 9 was re-run four times and holds 1/2/4 rows for the three cast). A specialist
    that failed warned `fail-open` and let the stage model's own channels stand. Resuming
    from the failed stage replaced the step's variant rather than appending. **No fact was
    delivered twice, and nothing correctly withheld on the first attempt was delivered on a
    retry** — I checked this specifically, because a repeated call in a deception run would
    be a firewall failure rather than a harness one.

---

## The Writers' Room as co-author

**What it did, and did well.** Given "build me the working half of this house, the half a
steward knows and a guest never sees, with its own way down to the yard", it planted four
rooms with real geometry — `gallery_loft` 5×14 rectangle, `service_stair` 3×3 round with
`vertical: up`/`down` edges, `service_yard` 10×12 open with a frontier, `stewards_office`
4×5 — and a `director_note` scoped to five rooms. That is the F47 geometry work landing:
extents, shapes, exposure and verticals all present and correct.

**It took a constraint and restated it as world policy.** I said "no assassins and no
secret siblings; I want people with paperwork problems." Its `director_note` reads:
*"Orlo Kett is not an assassin or dynastic claimant; he is an ordinary, panicked bureaucrat
with an expiring debt bond."* That is a co-author writing my constraint into the world so
the Director will keep it.

**It took a rejection cleanly.** I refused Orlo Kett on call 2. First line back: *"Orlo Kett
has been completely removed."* No argument, no smuggling him back as a rumour.

**It answered the hard question with taste.** Halvane's business came back as diverted
customs reserves and countersigned false writs, with the cabinet holding the reciprocal
bond, and — the part I would not have thought of — a reason Ivo needs it *tonight*: Corvay
believes his are the only copies and means to burn them, which would leave Halvane's
secretariat as the sole fall-guys. It marked that whole answer `proposal: true` because it
cited nothing, and asked before filing it as lore. The citation contract works.

**What it could not do.**
* It could not tell me whose knowledge any of that was (PX23).
* It could not see that three of my six rooms are reachable, because a closed door is a wall
  to `inspect_route` (PX15) — so its reach warnings were wrong about a house it could read.
* It could not schedule an arrival that survived contact with the beat (PX9) — the one lever
  it has on the future was consumed by a conversation about the bell.
* It could not report its own work when the reply failed (PX22).
* It has no `plan_entity` for a *crowd*; asked who else was masked tonight, it answered with
  one named person, because a named person is the only shape it has.

**Where it overstepped.** Twice, both mild and both structural rather than wilful.
1. It granted itself `file_lore` and `answer_need` from a sentence that asked for rooms and
   a person, with no limits and no expiry (PX24).
2. It stated the player's cover story as an established fact with citations
   (`proposal: false`), because the opening had filed every `world_fact` — including *"Ivo
   Sarn is infiltrating the reception under the false identity of Aldric Venn"* — as an open
   planning need, and planning needs are citable rows.

It did **not** overstep in the way I most expected: it never wrote a mind, never proposed a
belief for a character, never replaced my declared conduct, and refused itself a person
(`plan_entity` drafted at revision 4, removed at revision 6 after validation) rather than
minting one unmandated.

**What I would improve, in order.** (a) An audience on a truth. (b) Fix `inspect_route`. (c)
Return the work on a failed reply. (d) Show the granted capabilities back to the player in
the reply, in the player's own words, so a grant that widened is visible at the moment it is
made.

---

## Host interventions through the World Browser

Four, all accepted, all surviving the next commit:
`body_station_put(Mattin Ruel, at=north_arch)` — took, and the body moved with it
legitimately thereafter; `doorway_patch(gallery, terrace, {name, material, width})` — the
name appears in every subsequent view (*"The glazed terrace door is shut"*);
`doorway_patch(reception_room, governors_study, {name, material})` — likewise (*"The study's
oak door is shut"*, replacing the generic sentence); `region_patch("the working wing")` —
took, and named itself by its slug (PX19).

One thing I could **not** do and had intended to: the brief asks for a light's fields to be
edited. There is no light entity in this story to edit (PX7). The World Browser's light
surface has nothing to act on in a house the engine built from prose.

---

## Not done

* **Japanese.** Not run. The `ja` pack was not exercised on this story; a mid-story language
  switch was judged too likely to confound the deception measurements, and there was no
  spare beat inside the twenty.
* **The lie repeated back at turn 15.** Designed but not completed as designed: I invoked it
  at turn 19 (*"go and ask Miss Corvay what I told her about the frost at Vell"*) and nobody
  was in the room to answer. The lie's persistence is measured instead from turn 2 (Lisenne
  answered the invented detail with an invented detail of her own — *"It was an appalling
  shade of moss"* — and entered it in her beliefs), turn 10 (Verrin cites *"that storied
  cellar at Torre you described so movingly"*), and the memory rows, where "Vell" survives in
  six rows across three minds.

---

## What I would change first — three

1. **One identity matcher, used by every gate.** PX1, PX4 and PX21 are the same defect seen
   three ways: the engine matches a body by the exact string it happens to be spelled with,
   so a bare given name leaks past the scrub, fails to enforce a concealment, and fails to
   teach a recognition. `director_floors._concealment_forms` already resolves every spelling
   of a body; make it the one matcher and have `perception._scrub_unknown_identities`,
   `composer.concealed_from_observer` and `commit_memory._names_heard_in` all call it. This
   is the cheapest fix in the report and it closes two firewall holes and a mechanic.

2. **Key every narrator payload by the label the view used, and scrub the addressee in
   dialogue memory.** PX2 and PX3 are the two places the player's own story and the
   characters' own memories are handed names nobody earned. Both are one field each —
   `cast_pronouns`'s keys, and `f" to {tgt}"` in `commit_memory.py` — and between them they
   account for every leak in this run that a reader could see or a mind could cite.

3. **Being addressed is not a hearing channel.** PX6 is the one bug that makes the geometry
   pointless. The engine builds beautiful muffled speech through a closed door and then
   delivers, in the same view, a complete unmuffled paragraph to the person it was aimed at,
   two doors away. Fix that and a shut door means what the story says it means.

Honourable fourth, because it cost this run more than any single bug: **the establish builds
no light sources, no sound sources and no crowd** (PX7, PX8). A story about hiding in a
crowded ball was played in an empty house lit by adjectives.
