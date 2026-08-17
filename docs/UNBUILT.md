# Unbuilt work — the register

Everything designed, proposed, or found-and-deferred that is **not in the code
today**, in one place. Compiled 2026-07-29 against alpha 6.1 by re-verifying
every claim in every design and audit document against source.

**This file is the only worklist.** `CHANGELOG.md` and the git log are the
history; the surviving design notes keep the *argument* for an item and are
linked from it, but they no longer carry their own status lists — those drifted,
which is why this file exists.

It also **replaces five audit documents**, which were erased once their live
findings were folded in here: the 2026-07-19 architecture audit, the
information-pipeline leak sweep, the enterprise_d_v2 audit backlog, the
Fable adversarial-review follow-ups (all six closed), and the place-graph review.
Roughly 60% of the pipeline sweep and all six review items had already shipped,
and a reader taking those documents at face value would have chased about forty
closed findings. What survived is below, with enough mechanism detail to act on
without them. Their reasoning is in git history and in `CHANGELOG.md`.

**Partially re-verified 2026-07-31** against alpha 6.3. Entries confirmed still
true against source this pass: §1.1, §1.3, §1.6, §1.11, §1.13, §2.3, §2.5,
§3.2 B1-residual (§2.14's `fStrList` was confirmed then and has since been
converted at eight of its ten sites). Entries **corrected** this pass: §1.13
(the enum is real, but the validation seam the pipeline uses does not enforce
it), and the present-beat citation entry, whose premise was stale — the ids it
asked for already existed and already reached the payload; only the prompt
never learned. That one has since landed and is deleted per rule 1; the record
is `Design.md` § Structural debt #1. §1.4 (`sqlite-vec`) was
re-decided and **landed** — its either/or was wrong, since wiring the vector
index would have regressed the information firewall — and is deleted per rule 1;
`docs/guides/RESEARCH.md` §1.4 carries the reasoning. The embedding-model
cliff that entry pointed at (§1.15, "changing the embedding model silently
erases semantic recall") is also gone: a provider is configured, the bank is
migrated, and the mismatch guard and the resumable rebuild it prescribed both
exist — `memory.embedding_bank_status`, `rebuild_embeddings`,
`rebuild_checkpoint_embeddings`, `repair_pending_embeddings`. See `Design.md`
§ Changing the embedding model is safe. Everything else below
still carries its 2026-07-29 verification date and should be re-checked before
being acted on — rule 2 exists because this file's claims go stale faster than
the code does, and two of the ten checked this pass had.

Rules that keep it honest:

1. Delete an entry in the same commit that lands it. Do not mark it done here.
2. Cite a symbol, not a line number. Line citations in this repo's docs went
   stale within days — that is most of why the audits had to go.
3. If an entry has sat untouched through three releases, either promote it or
   admit it is parked and move it to §8.
4. Findings keep their original ids (P-, F-, S3-, X-, Gap-) so old commit
   messages and test docstrings still resolve.

---

## 1. Known defects

Live bugs and unfinished corrections — places the engine is currently wrong,
not places it is merely thin.

### 1.1a Conduct authority: what the guards still do not reach

**Found:** landing the character-authority guards (chat 56 t1391). The defect
they fix is closed; these are the edges they deliberately do not cover.

- **A player who declared an act is guarded only against taking hold of the
  WORLD.** `_check_player_act_authority`'s widened scope fires on a
  manipulation verb with a direct object that is neither the player's own body
  nor anything their declaration mentions. Gestures, expressions and undeclared
  movement are still unflagged on a beat where the player declared any action —
  the same "separating elaboration from addition needs more than a verb list"
  problem the character check punts on, narrowed here to the case that
  demonstrably replays into the next beat. `_MANIPULATION_STEMS` and
  `_OWN_BODY_NOUNS` are hand-built, tuned against one live chat and the
  existing suite, and their false-positive rate in live play is **unmeasured**.
  Blast radius is bounded the same way — one retry, kept only if it lowers the
  count — so a spurious flag costs a call and cannot corrupt the beat.

- **Perception has no player-ACTION scrub, and its player-SPEECH scrub no
  longer runs either.** Chat 56 t10's fabricated lever grip reached the
  player's view as "I grip the console edge" with nothing between the Director
  and the narrator, and the Director-side guard is still the only thing
  standing there, so a fabrication that survives its one retry propagates.
  What has changed is the shape of the gap, not its size. The scrub this entry
  used to name as the mouth's protection,
  `agents.common._scrub_undeclared_player_speech`, has **no production caller**
  — it is imported by `agents/perception.py` and called nowhere, kept alive
  only by tests and `tools/perception_quality.py`. Perception stopped needing
  it when it stopped asking a model to write views: `_per_observer_model_views`
  is gone (`tests/test_perception_has_no_model.py` pins its absence), the view
  is realised from percepts, and undeclared player speech has no seam to enter
  through. What survives is `_scrub_invented_dialogue` inside
  `_composer_tripwires`, deliberately **warn-only** and correctly so — a line
  in a composed view that does not match the delivered-line ground truth is an
  ENGINE defect, and scrubbing it would hide the bug rather than the leak. So
  the second independent floor this bullet used to ask for cannot be built the
  way it described; a player-action check would have to sit where the
  tripwires do, on the composed view, and it would be a defect detector rather
  than a scrubber.

- **A character who declared a non-locomotive act is guarded only against
  MOVEMENT.** Handing something over, drawing a weapon, striking — additions
  that are not movement — are still unflagged for a character who declared
  any act at all. This is the same "separating elaboration from addition
  needs more than a verb list" problem the player check punted on, and it is
  punted on here for the same reason. Movement was carved out because
  distance decides what perception delivers and what contact is possible, so
  getting it wrong has consequences beyond the sentence.

- **`_check_prose_quote_authority` ignores quoted spans under three words.**
  A readout reading `"STABLE"` and the word `"safe"` in scare quotes are not
  utterances, and there is no way to tell them from a genuinely invented
  `"Run."` without reading the sentence around them. Short fabricated lines
  survive; the speech check catches them only if an attribution verb is
  present.

- **The locomotion verb list is unproven in live play.** It was tuned against
  one live resolved_event and the existing suite, and it includes posture
  verbs that double as ordinary elaboration — "leans in", "settles". A
  character who declared a non-locomotive act and is then written as leaning
  toward someone will fire a correction retry. That is the intended reading
  (leaning in IS a distance change, and distance is the character's to
  declare), but it is a judgement call made on one example, and the honest
  status is that the false-positive rate is unmeasured. The blast radius is
  bounded — one retry, kept only if it lowers the violation count, so a
  spurious flag costs a call and cannot corrupt the beat — but if it proves
  noisy the fix is to drop the posture verbs, not to widen the window.

- **All of it is prose matching**, with everything §3.1 says about that.

### 1.2 Nothing validates the geometry of an asserted doorway

**Found:** live, alpha 6.0 session. **Do this before any multi-location story
with several characters.**

The scene merge accepts an adjacency a model asserts, with no check that the two
rooms *could* be adjacent. Measured: `r0204 <-> r0303` in the maze scene — a
diagonal in a grid maze, geometrically impossible by construction — sat in the
world model for hundreds of turns and was walked as a real doorway.

`spatial._shield_standing_bearings` protects the bearings of *existing* edges.
Nothing guards the creation of a *new* one.

Why it matters beyond mazes: a Director inventing a connection between two
locations is what happens in a village or a household when a model reaches for a
shortcut, and a fabricated doorway becomes part of every character's map and
every route computed over it. The maze has coordinates to check against; a
general scene may not, so the honest fix may be "require a stated basis for a
new edge" rather than a geometric test.

### 1.3 `survival.py`'s sleep-recovery branch is dead

`tick_vitals(..., asleep=)` is derived from `scene.contained[x]["mode"] ==
"asleep"` — a **containment** mode ("carried", "pocket", …), never an awareness
level. The set is always effectively empty: **nobody has ever recovered stamina
by sleeping.**

Consequence already paid: natural waking had to be keyed on the simulation clock
(eight hours) rather than on the rest a body actually needed, because "rested" is
not currently computable. Fix the source and the better rule becomes available.

### 1.5 A character cannot revise a bearing they learned wrong

`disproven` fires when a doorway fails to exist. Nothing fires when a doorway
exists but the character remembers the wrong heading for it. After a bearing
corruption was fixed in the world, one character kept oscillating in exactly the
pockets whose bearings had been wrong while he learned them — the world was
corrected, his map of it was not.

Related to the broader gap: a character can revise a belief about the world and
has almost no mechanism for revising a belief about themselves. Project
displacement is currently the only one.

### 1.6 See-through barriers mint walkable edges

**Real in story play; cannot affect the maze arms** (generated and authored
mazes have only `open` edges).

`update_place_graph`'s doorway filter (`commit.py`, two sites) excludes only
`wall`. But `spatial._SIGHT_BARRIERS` is `{"open", "open_door", "window",
"bars"}`, so a barred window or a pane of glass between two rooms records a
walkable graph edge. You can see through a barred window; you cannot walk
through one. Confirmed directly: a `window` between A and B yields
`edges from A: {'B': {'last_confirmed': 1, 'bearing': 'e', 'basis': 'seen'}}`.

This matters more since `_frontier_hops` replaced `_frontier_beyond`: the old
answer was a boolean ("is there new ground that way"), and a wrong boolean is
merely vague. The new one is a distance rendered to the character as *"the
nearest door you have never taken lies about 3 rooms down that way"*. A wrong
distance is a specific falsehood about their own remembered ground, and the kind
a character acts on.

**Not a one-line filter** — it requires deciding what a *route* means to a
remembering mind, and neither existing set answers that question:

| set | means | wrong here because |
|---|---|---|
| `_SIGHT_BARRIERS` | can be seen through | includes glass and bars |
| `_PASSABLE_BARRIERS` | passable **this beat** | excludes `closed_door`, which a character can simply open |

The set wanted is roughly `_PASSABLE_BARRIERS | {"closed_door"}` — *a way I could
go through, now or by opening it* — and possibly `locked_door` too, since a
remembered route past a locked door is still a route if you expect to get a key.
That is a judgement about the character's model of a route, so it wants deciding
rather than defaulting.

**Scope note.** The legacy `known_exits` ledger is worse and always has been: it
records every declared adjacency including solid `wall` edges, and
`_annotate_known_exits` merges it into the same BFS adjacency. The graph is a
strict improvement rather than a regression, and this predates it. Any fix must
also cover the legacy writer in `record_spatial_experience`, or the wall edges
simply re-enter through the merge.

### 1.7 JSON validation stalls cost beats

Six-plus across one experiment arm: `mind_model_updates` missing required
fields, `sequence` emitted as a non-list, occasionally prose instead of JSON.
Model-side, and the harness skips the beat and continues — but each one is a lost
turn, and in a story it would be a character who simply did nothing.

The character step already has a bounded decision-continuity review combining
verbatim repetition, potential semantic-move repetition, and spent-intention
use (`agents/character.py`); it is still not the schema-failure repair path.
Worth deciding whether another bounded retry belongs there too.

Measured again on a three-turn live run, 2026-07-30, and closed for the shape
that caused it: `preprocess_llm_output` dropped any `sequence` element that
was not a dict, so a model answering with a list of *sentences* — `["Kess
turns to the customs clerk and asks him to witness the sale."]` — arrived at
validation with an empty sequence and failed "sequence is empty despite
nonempty player input". Repair and every fallback ran against that message,
which was false, and the turn died. Twice in eleven live turns, on two
different scenarios, identically on both Pydantic majors.

`_sequence_event_from_prose` now reads such an entry as an ACTION unless the
whole string is a quotation, and `_name_what_was_discarded` names what was
dropped for whatever still cannot be read. The action default is the safe
reading rather than the likely one: typing prose as speech would author an
utterance AND transmit it to everyone in earshot, while typing speech as an
action under-informs the room. **What remains open is the mixed sentence** —
`Says, "Nobody leaves this room."` keeps every word in its attempt text but
is typed as an act, so a character in the room may not receive it through
the dialogue channel. Deciding that needs the hearing path looked at, not a
better regex.

A fourth shape cost a turn the same way and is closed the same way: the whole
answer wrapped in one key of the model's own (`{"the_director_outputs":
{...}}`), every declared field present and correct one level too deep. The
step failed as "rooms is empty; positions is empty" — a model that answered
nothing, when it had answered everything — and the repair prompt inherited
that false complaint. `_unwrap_envelope` opens it only when the single key is
not itself a field and what is inside is recognised.

Two other shapes cost turns on the same run and are also closed, both
non-divergent across majors and both the same mistake one layer down: a
staged lore entry whose `content` was an object (`_room_notes_from_lore` did
`content[:600]` on a dict and killed the turn), and a condition written as
its own description, `{"generator_fuel": ["The generator is running low..."]}`
against `dict[str, list[dict]]`. Neither is exotic; both are what a model
does when the field name reads like an invitation to prose.

### 1.8 Promotion seeds are minted from the objective event (P5)

`importers.py`'s promotion path uses the full `resolved_event` of every turn
mentioning the name — **including concealed acts, with no perception filter** —
and `commit.py` writes the result with `provenance: "witnessed"`. The autonomous
promotion path has no reviewer, so a promoted background character begins life
holding entitled information tagged as though they had seen it.

The widest surviving instance of "the omniscient record re-enters a later
context".

### 1.10 Entity `state` staleness is instrumented, not fixed (S3-A8)

Nothing reconciles an entity's free-text `state` / `description` against the
beat's resolution. An earlier "skip the update" fix was **reverted** as durable
corruption; `commit.py` now only emits a `"possible stale clause (S3-A8)"`
warning and commits the blob anyway. `tests/test_pipeline_audit_leak_gaps.py`
pins this deliberately as *a signal, not a fix*. Root cause — free-text state
blobs with omission-only reconciliation and `_PROTECTED_STATE_KEYS` — untouched.

### 1.11 `ctx.warnings` reaches the pipeline drawer but not the story reader

**Mostly landed, alpha 6.9.** Every warning is now tagged with the step that
raised it (`pipeline_context.StepTaggedWarnings`, keyed off a contextvar set in
`compute_step`) and persisted onto that step's saved content under
`_engine_notes`, which the pipeline drawer renders above the step. The
tagging lives in the list rather than at the ~40 call sites so that both
spellings — `ctx.warnings.append` and `ctx.add_warning` — are caught, including
ones not written yet.

What made this worth landing is on the record: perception dropped both sight
sentences out of a character's view of an embrace happening six feet in front
of him (chat 38, turn idx 140), warned about it twice, and the warnings went
nowhere. What survived into his memory of that beat was a sound.

What remains: the channel is still developer-facing, visible only to somebody
who opens the drawer on a specific turn. There is no aggregate view — no way to
ask "which turns in this story had a view repaired", which is the question that
would have caught the above six turns earlier than it was caught. A warning
during a run also still passes silently; only the persisted record shows it.

### 1.11a `flow.reactors` answers two different questions

`perception_act`'s perceiver list **is** `flow.reactors`: pass 1 iterates the
cast and `continue`s on anyone not in it, with no spatial or sensory reasoning
of its own. So one field decides both *who legitimately perceived the act* — a
perception question, answerable from the scene — and *who may respond to it* — a
pacing question that is the Director's to judge. Every other layer of this
engine keeps those apart.

The consequence is that a present, awake, watching character omitted from
`reactors` perceives the onset never. Their entire account of the beat is
`perception_outcome`, and they take no part in it. Rerolling perception cannot
change this; only `director_interpret` can.

Measured on the stored corpus, using the engine's own answer for who was
present (who received an outcome view): **435 of 551 beats with two or more
character witnesses had at least one witness missing from `reactors`** — 79%.
Live in chat 38: t121–t127 ran seven consecutive beats with two witnesses and
neither in `reactors`; at t140 the Doctor stood at the genkan watching an
embrace the resolved event says he watched with bright interest, was not a
reactor, and did nothing. Two independent rerolls of `director_interpret`
produced the same set both times, so it is not sampling noise.

Alpha 6.9 sharpened the prompt clause — it now says reactors is permission
to respond rather than a requirement, explicitly not "who was addressed", and
cites the 79%. Confirmed in conduct on the beat that prompted it: chat 38 t140
re-interpreted to `reactors: [35, 41]` and `perception_act` built views for
both. Still only one beat; re-measure the query above before believing the
rate moved.

**Widening `reactors` immediately exposed a second, larger defect downstream**
— being a reactor did not mean getting a character step. See §1.11b.

The structural fix is to separate the two fields — an onset audience derived
from the scene, and a reactor set the Director chooses from it — which is not
done. Cost is the reason to think before doing it: every added reactor is a
character-step LLM call, and widening it wholesale would make crowded scenes
both expensive and chattier than anyone asked for.

### 1.11b Reactors stranded by another character's touch — FIXED, alpha 6.9

Kept as a record because the shape recurs. The interaction loop's early exits
end the BEAT, and the commonest of them (`_requires_director_resolution`) fires
on any declared act carrying a target — a hug returned, a hand on a shoulder, a
glance answered. The addressed character is deliberately queued first, so the
ordinary shape was: the addressed character touches somebody, the loop breaks,
every other reactor is never called.

Measured before the fix: **153 of 196 beats with two or more reactors left at
least one reactor never called at all**; 106 of those stopped on that one exit.

A character who never ran has no appraisal, hence no `goal_impacts`, hence no
drive strain from a beat aimed at them; no psychology commit; and no memory of
having chosen to stay quiet — while the narrator, seeing nothing, is free to
render the absence as a deliberate silence nobody chose. `_defer_to_focus`
already patched exactly this for `tom_triggers` characters; this was the
general case it had been a special case of.

Fixed by reading `initial_parallel_reactors`, which had been sitting in
`DEFAULT_INTERACTION_CONFIG` unread: the first wave of reactors is simultaneous
IN THE FICTION — everyone is answering the player's already-fixed declaration
and none has seen another's response, because none exists yet — so the wave
declares blind and micro-perception is delivered only once every member is
done. Exits are evaluated for the wave as a whole. After the wave, one speaker
at a time, unchanged, because a character replying to another character really
is responding to something they just heard. Parallel in the fiction, not in
execution: `character_step` writes through `ctx`, so threading it would race.

The residual is §1.11a above: the two questions are still one field.

### 1.11c Lore names people it has no business naming — FIXED, alpha 6.9

`knowledge_for_character` gates WHICH lore entries reach a mind, by knowledge
tag and range. Nothing gated who those entries were allowed to NAME, and the
mapping stage writes lore during play using canonical names — so an entry
written from a beat one character stood in arrives, at another character, fully
identified.

Live (chat 38, t140). Tamamo had met the Doctor one beat earlier and her
`known` ledger was empty. Every prose surface agreed on what she could call
him — her view, `ahead_entity`, her micro-perception deliveries all said "the
lean energetic man" — and `world_knowledge` handed her an entry opening "As The
Doctor and Hinami walk deeper into the Deck 14 corridor". A starship corridor,
delivered into a Kyoto shrine. She addressed him as "Doctor" in the same beat
and wrote "the lean energetic man now identified as Doctor" into her own
active concerns, where it persisted.

Corpus: 65 lore entries across 22 chats name a cast member; 16 written during
play.

Fixed with the identity floor that already existed one field away.
`agents/common.observer_name_scrub` is `observer_label_fn` for a paragraph
rather than a single name — same `known` map, same `_unknown_actor_label` — and
`scrub_names_deep` walks the payload so `content`, `title` and `keys` are all
covered. The player is gated like any other body, since play-written lore names
them more than anyone. Whole-word and alias-aware, longest form first. Quoted
spans are deliberately NOT exempt the way perception exempts them: a lore entry
is not a transcript, and prose quoting somebody naming a person still tells the
reader who they are.

**The shape, not the instance, is the finding.** Perception scrubs prose per
observer; every OTHER payload that hands a mind somebody else's words is a
place this can recur. `ahead_entity` was the first (alpha 6.7), this is the
second. Nothing systematically enumerates the rest.

### 1.11d A heard line could be delivered and then scrubbed away — FIXED, alpha 6.9

`perception_outcome` injects each audible line into a view, and THEN runs four
passes that remove text: the identity floor, the player-speech scrub, the
invented-dialogue scrub, and a sentence dedupe. Each is right on its own; none
knows a line the hearing gate already granted might be inside what it takes,
and nothing re-checked afterwards.

Live (chat 38, t137): the Doctor walked beside the player and spoke four times
— `normal` volume, same room, open barrier, nothing concealed. Her view ends
`"...as we scan the mist-shrouded surroundings together. Yeah, I bet I will.\""`
— an orphaned tail with a closing quote and no opening, which is the signature
of a partial quoted span removed from the middle of a delivered line. The other
three lines are absent entirely.

Measured against each turn's own checkpoint positions, so earshot is not
guesswork: **30 of 1549 lines spoken by somebody standing in the player's own
room never reached the player's view** (1.9%), across seven chats.

Nothing downstream could catch it: the narrator's dialogue-fidelity check
compares the PROSE against the VIEW, so a line already lost from the view is
one the check agrees is not missing. A guard built for this exact failure one
stage later was no help at all.

Fixed with a floor at the end of the per-perceiver loop — every line the gate
delivered at `full` clarity is re-checked after the scrub chain and re-injected
if gone, reporting each restoration. Re-injection is safe by construction: the
bodies come from the Director's `dialogue_log` and passed that perceiver's own
hearing gate, which is what the scrubs exist to distinguish from.

**Residual: the floor compensates, it does not diagnose.** Which of the four
passes ate the line is still unidentified — the warning now says a restoration
happened, not who caused it, and the pre-scrub view is not persisted. The
orphaned-quote signature suggests a quoted-span scrub taking a partial span,
but that is inference from the wreckage rather than a traced cause.

A separate, smaller finding from the same sweep: **17 lines that DID reach the
player's view were never rendered into prose**, all in July turns, none since
the narrator's dialogue-fidelity check landed (0 in 241 August lines). The drop
rate scaled with how many people spoke in the beat — 0.5% at one speaker, 3.0%
at two, 10.3% at three — which is the shape to re-measure if it returns.

### 1.11e Two speakers welded into one quoted span — FIXED, alpha 6.9

DIALOGUE FIDELITY asks whether each line SURVIVED into the prose. It cannot ask
whether the line ended up in the right person's mouth, and both questions have
the same answer when two speakers' lines are merged into one quoted span: every
body is present verbatim, so the check passes while the reader is told the
wrong character said half of it.

Live (chat 38, t140). The view had them properly separated, one attributed
clause each — `... says: "Be at ease, both of you."` then `The Doctor says:
"Tamamo. A pleasure."` — and the prose rendered `"Be at ease, both of you.
Tamamo. A pleasure." The Doctor's voice carries clean across the clearing`.
Also t39 of the same chat, where the whole of Guinan's line was absorbed into
the Doctor's.

Swept across the corpus: 5 stored instances (t39 recurs in four branch
descendants of one beat), 2 distinct beats, out of 1082 multi-speaker beats.
Rare — but the exposure is rising, because the interaction loop's first wave
(§1.11b) makes two-speaker beats far more common than they were.

Fixed by a new fidelity check reading `event_order`, which is already gated to
lines that reached the player's view, so prose that rightly omits an unheard
line cannot be accused of merging it. Bodies under 15 characters are ignored:
a short line can sit inside a longer one by coincidence and a false positive
costs a rewrite. Added to `_ENFORCEABLE_PREFIXES`, so the existing repair loop
rewrites rather than merely warning. Zero false positives across the 1082
beats.

### 1.11f A nod ended the beat — FIXED, alpha 6.9.1

`_requires_director_resolution` ends the BEAT in `interaction_loop`, so its bar
should be "nobody can sensibly respond until the world says what happened". It
was instead "this act involves another person": any action with a non-empty
`targets` list.

In a conversation every piece of ordinary body language is aimed at whoever you
are talking to. Live, chat 38 t144–t147 — the player deliberately stayed silent
for four consecutive turns to let two characters talk — and all four ended after
a single exchange, on "offering a small nod of acknowledgment to Tamamo",
"pivots one golden ear toward the Doctor", "shifts gaze fully to the Doctor",
"remains motionless with steady gaze on Tamamo". Nobody can contest a nod.

Corpus-wide: **1002 of 1439 character-declared actions were asserted, immediate
and targeted** — 70% of everything a character does was ending the beat. Every
character action in the corpus carries `stage: "immediate"` and no effects, so
those fields cannot discriminate; `commitment` can, and it is the Director's own
answer to this exact question. Only 82 of the 1439 are `contestable`, and they
read like it: "Tightens grip on the caught prey's shoulder, wrenching upward",
"Closes the 1.5-meter gap in two quick steps".

Now gated on `commitment == "contestable"`, with the conflict-verb list kept as
a backstop under a mislabelled commitment — it also covers movement
(`leave`/`enter`), which needs resolution however confidently it is declared.
Re-classified against the stored corpus: 858 declarations no longer end the
beat, 177 still do, and 8 newly do (six are movement, correctly).

**This is a large pacing change and it is unverified in play.** The measurement
says which declarations change class; it cannot say whether the resulting
conversations are better. Watch for the opposite failure — beats that run on
past their natural end — and note that `max_micro_rounds` (4 at autonomy 50) is
now the thing actually bounding an exchange rather than the first targeted
gesture.

### 1.11g Nobody knew they had been asked something — FIXED, alpha 6.9.1

`interaction.expects_response` is written on every character result and was
consumed in exactly one place: `_recent_self_moves`, as `expected_answer`,
which tells a character *I* asked something. Nothing told a character that
somebody had asked *them*.

Live, chat 38 t144–t147 — the player stayed silent for four turns so two
characters could talk. Tamamo put a direct request to the Doctor on three
consecutive beats; on the last two he said nothing at all. Nothing about his
reasoning is broken: he KNEW about the question (it is in his
`observations_used`, recalled from memory), weighed answering, and rejected it
at inhibition 0.4 against "shrine etiquette favors waiting rather than filling
silence", selecting "remain silent and observant to give Tamamo room to
respond". Both were waiting for the other, and she filled the gap with more
questions and by turning back to the player who had deliberately stepped out.

Three fixes, all from records the engine already had:

- `decision.awaiting_your_answer` {from, asked, turns_ago} when a character was
  addressed with `expects_response` and has not spoken since — and when the
  PLAYER asked them, which is the larger half and the one a character-result
  path can never see, since the player has no `interaction` block. That case
  reads `flow.addressed_to` (where "who did the player mean" is already
  decided) and does use the question mark, because there is no
  `expects_response` on a player declaration and inventing one would mean
  guessing at intent the Director never recorded. 809 beats in the corpus carry
  player speech aimed at a named character; 363 contain a question. Deliberately not
  keyed on a question mark: every ask in the live case was an imperative
  ("describe its dimensional nature in your own terms", "Name one way its
  dimensions interface with established boundaries") and punctuation would have
  missed all of them. Reaches back three beats only; an ask nobody has picked
  up in longer has been dropped by the scene. The prompt is explicit that
  refusing, deflecting or declining are answers — what is not permitted is
  failing to notice.
- `decision.player_quiet_for_beats` once the player's silence has lasted more
  than one beat, because one is not the same event as four. One quiet beat is
  something they just did mid-exchange; several is somebody who has stepped
  back to watch, and reading it afresh each beat is what produced "Hinami, you
  have gone quiet after such proud words" and "Hinami, your presence here is a
  quiet joy".
- Whoever owes an answer is queued FIRST in `interaction_loop`, ahead even of
  direct address. Order had fallen back to cast-registration once the player
  went quiet, so the Doctor opened every beat — speaking before Tamamo asked,
  so his line could never be the answer.

The ordering is derived rather than declared. A Director field stating "A asked
B" was considered and rejected: the Director cannot see this better than the
record can, since `expects_response` and `addresses` are already written by the
character who asked, and a second spelling of one fact drifts and then
disagrees.

**Unverified in play**, like §1.11f which it sits beside. The mechanism is
measured against the stored turns — the two ignored requests are surfaced
correctly, and the ordering flips — but whether the resulting conversation
reads better has not been observed.

### 1.11h The person being answered was inside the blind wave — FIXED, alpha 6.9.1

The first wave (§1.11b) rests on a claim: its members are answering the same
thing and none has seen another's response, because none exists yet. That holds
when everyone is reacting to the PLAYER. It is false when one member is
answering another — the answer is FOR the asker, who is the addressee rather
than a bystander, and the question they are owed an answer to already exists
from the previous beat.

Live, chat 59 t146, one beat after §1.11g shipped. The Doctor owed Tamamo an
answer and was correctly queued first, but she was in the same blind instant.
Her present evidence was "dim light... gravel... Hinami stands perfectly still"
— his answer nowhere in it — and she selected "rephrase the dimensional
question freshly to the Doctor". Given a second round she then heard him and
acknowledged by restating his own terms back. On the page: an answer, then the
question it had just answered, then the answer read back to the person who gave
it.

Neither mind misbehaved. Both acted correctly on the information they had, and
the information was wrong by construction.

The asker now steps out of the first wave and speaks in the next round, having
actually heard the answer. They keep their place at the front of the queue, so
nobody loses a turn — the order changes. Mutual debt (each owing the other)
would defer everyone and stall the beat, so the queue order breaks that tie.

One thing this exposed: `_next_speaker_candidates` looks for somebody NEW to
bring in, and "no eligible respondent" ended the beat without checking whether
the queue still held anyone. That would have dropped the deferred asker
entirely — the same stranding the wave exists to prevent, one round later.

**Still unverified in play**, like §1.11f and §1.11g. The wave shipped hours
before this was found, so chat 59 is very nearly the entire corpus for it: this
is one clear case reasoned from mechanism, not a rate.

### 1.11i The engine spoke for a silent player — FIXED, alpha 6.9.2

Every player-authority check compares the Director's output against what the
player declared. With an EMPTY input there is nothing to compare against, and
nothing guarded that direction.

Live, chat 59 t154. Input empty; `director_interpret` emitted speech "Kaa Sama
Kaa Sama! You're cooking is simply to good to not indulge in." and action
"steps inside the shrine and looks around at the familiar sight of home" —
both the player's turn-150 declaration, verbatim, four beats stale. Tamamo
thanked her for praise she had not given.

Corpus: 10 turns carry an empty player input, 2 invented player speech (the
other newly, "something reassuring"). Small sample, but the failure mode is the
one the architecture exists to prevent.

Now deterministic: an empty input clears `sequence`, `speech`, `action` and
`actions` before anything reads them, warns, and tells the Director on the next
beat that silence is the whole declaration. Silence still reaches characters
through `_player_silence_note`; what no longer reaches them is words.

### 1.11j A repeated question hid inside a different beat — FIXED, alpha 6.9.2

`_recent_self_moves` records the SELECTED MOVE, which is what the beat was busy
with. A character who asks something while cooking writes the cooking there, so
a repeated question hides inside three different-sounding moves and neither
guard sees it.

Live, chat 59 t152–t154. Tamamo asked the Doctor for his impression of the hall
on three consecutive beats, after Hinami had already asked and he had already
answered. Her ledger held all three lines with `expected_answer: True` on each.
`_first_repeated_move` returned None — it compared "continue preparing the meal
at the hearth" against "lightly reassure Hinami and acknowledge the home
compliment" — and the exact-line guard found nothing, because the three are
lexical paraphrases sharing almost no wording.

The ledger now projects `asked` apart from `said`, and the repeat check
compares question against question at a lower threshold than the move
comparison (two prose summaries share incidental vocabulary; two restatements
of one request often share none).

**Measured, and honestly imperfect.** Swept over the corpus: 594 beats where a
character asked something, 47 flagged (7.9%), roughly half of them genuine
re-asks by inspection — including the documented Saturn/dragons loop at 1.00.
The rest share a question skeleton without sharing a subject. Left at 0.5
because this opens a bounded contextual review rather than vetoing a line, so a
false positive costs a paragraph and a miss costs the failure. 0.6 would halve
the flags and still catch the live case, but only just — it scores 0.600
exactly. That is the next stop if the reviews read as churn.

### 1.12 Watch items

Not defects yet. Each is a measured shape that will become one silently.

- **Arousal now has a ceiling where it had a floor.** Withdrawing the false
  satisfaction stand-down exposed the somatic lift underneath it. A body at
  saturated, unreleased appetite climbs to the arousal ceiling in about five
  beats and pins there until release. Probably right — the arc has a designed
  exit — but it is the same missing-equilibrium shape as the bug it replaced,
  pointing the other way. Watch whether a long unreleased stretch reads as
  sustained or as stuck.
- **`circling` fires on routine movement in familiar space.** Honest for a maze;
  likely wrong for a resident crossing their own home several times in a scene.
- **Nine payload keys is an attention budget.** `projects`, `en_route`,
  `adrift`, `ends_in`, `ground_fully_known`, `goal_reached`/`goal_held`,
  `fading`, `project_review`. Each is something a model must notice and act on,
  and attention is finite — at some point adding the tenth marker makes the ninth
  less likely to be read.
- **`logging_utils.TurnMetrics` and `measure_step` have no callers and now
  never will.** Per-stage timing landed as a per-call ledger instead
  (`_engine_notes.llm_calls`, `Design.md` § Turn shape), because what the slow-turn
  investigations needed was WHICH CALLS a stage paid for, not stage totals the
  `steps`/`variants` timestamps already yield. The two survivors are dead code
  wearing a plausible name, which is how a reader spends an hour deciding
  whether to wire them. Delete them.
- **The place graph's distinct contribution is narrower than proposed.** With
  pruning gone, unpruned `known_exits` + `known_dead_ends` carry most of the
  routing information by themselves; the graph's remaining unique contributions
  are `disproven` retraction, walkedness surviving the recency window,
  reverse-declared `seen` edges, and bounded eviction. They are kept as
  graph-bounded *views* rather than a second authority, which is right while both
  exist — but two representations of one fact is the shape that produced
  `rekey_place_claims` and `reconcile_inference_confidence`. **If a third
  consumer appears, collapse them** — and one has arrived to be judged:
  `place_purpose.py` reads `state["place_graph"]` directly, for the `affords`
  ledger rather than for routing. Whether an affordance reader counts is the
  judgement this bullet exists to force; it is a second MODULE on the graph
  either way, which is the condition, not the intent.
- **The observation text repeats the view and cannot be trimmed away.** Each
  atom's `observed.text` is a span of the same scrubbed prose the character
  already has in `perception.view` — measured on chat 72, 737 B of atom text
  against a 757 B view, 97% byte-identical. Shortening it to an opening-words
  locator was built, measured and **reverted**: a rendered atom is front-loaded
  with its attribution, so an eight-word window spends itself on
  `Hinami says in a nostalgic voice:` and cuts the clause that carried the beat
  (`"He never saw my ears or tails."` arrived as `"He never ..."`). The
  duplication is the price of the atom being *addressable* — `present_evidence_used`
  cites it, and the model paraphrases it into `fact`. Any future attempt must
  keep the content and drop the frame, not the reverse, and must be measured
  against `tools/benchmark_memory_temporal.py --case anomaly_now --case boundary`
  before it ships. ~464 B per character per beat; the smallest item in the
  payload and the only one with a proven mechanism of harm.
- **A gist reads like a conclusion — the fidelity ladder is BUILT, MEASURED and
  NOT SHIPPED.** Delivering the far half of the recall slate as its gist alone
  is psychologically right and costs nothing in content: gists of the target
  memories carry 100% of the scored term groups the details do, and the
  benchmark's content checks were 20/20 in both arms. It still regressed, and
  not where anyone was watching. With half the slate condensed, the character
  stopped consulting the PRESENT: asked "the anomaly is flaring right now,
  isn't it?", the arm with the ladder cited a present observation 14/30 against
  25/30 without it (Fisher p≈0.006), answering a question about now entirely
  from memory. The mechanism is that a full episode is discursive and obviously
  past, while a one-line gist is answer-shaped — so condensed memory
  out-competes a prose view for a question the view should have owned. Worth
  ~3.3 KB per character per beat (−11% of the memory context). Any retry must
  restore the present lane's weight FIRST and prove it on `--case anomaly_now
  --repeats 20`; keying the ladder better will not help, because the ladder's
  key is not what fails. Two keys were tested and both are unusable anyway:
  retrieval rank puts the row a question actually needed at rank ≥10 a third of
  the time (88 scored retrievals), and `importance` does not separate at all
  (median 0.69 on needed rows against 0.68 on the rest of the bank).

### 1.13 `ActionStage` is classified and the resolve path never reads it

`schemas.ActionStage` (`immediate|preparation|approach|contact|sustained`) is
filled in by `director_interpret` on every action element and read, on the
resolve path, by **nothing**. Its only consumer anywhere is
`agents/common._requires_reaction_phase`. So the interpret has been correctly
classifying "this act has not landed yet" since the beginning, to no effect —
which is what let the blizzard beat resolve an approach as an arrival
(`Design.md`, "Approach is not arrival"; the fix routes around `stage` via
`MovementDecl.arrives` rather than through it).

Two things follow, neither done:

- **The other unlanded stages have no consequence either.** `preparation` means
  the act is setup, not the thing; the live corpus has 8 of them, 2 with an
  `inventory_ops` in the same beat. `initiation` appears 9 times and **is not a
  member of the enum at all** — the model invents it and it passes validation
  untouched, so any guard keying on the declared values silently misses those
  beats. Either the enum is enforced or it is not a closed set. Re-verified
  2026-07-31, now with the mechanism: a direct `ActionElement(stage=
  "initiation")` DOES raise, so the enum is real — but
  `validate_llm_output("director_interpret", …)` returns the element with
  `stage: "initiation"` intact and **no errors**. The closed set is enforced
  nowhere the pipeline actually passes through. Settle it at that seam.
- **`sustained` is the interesting one and the least safe to act on.** 250 live
  beats are staged sustained, 128 of which move somebody, 62 open a contact and
  53 mint a condition — and most of those are correct, because a sustained act
  is ONGOING rather than unfinished. Anything that treats sustained as
  "not landed" will be wrong most of the time. What is missing is the
  distinction between an act that continues and an act that has not yet
  completed, and the schema does not carry it.

### 1.14 A resolve-asserted position has no authority check

`director_resolve`'s passable-route backstop guards `state_diff.positions` only
when interpret DECLARED a movement (`if isinstance(mv, dict) and
mv.get("to_room")`). When it declares none, the resolve's own position
assertion reaches commit with no route check, no adjacency check and no
authority check — it can put the player anywhere in the graph. Live corpus: 13
beats where the resolve moved the player with no declared movement, of which
several are legitimate (being carried, an asserted crossing the interpret did
not model) and several are not.

The honest rule is not obvious, which is why this is a register entry rather
than a guard: a resolve legitimately moves a player who is carried, dragged,
falling or riding, and each of those declares no movement either. The
containment check in `_guard_approach_is_not_arrival` is the start of the
answer, not the whole of it.

The wider point: `movement` is the channel through which the player says where
they are going, and a stage that can relocate the player without it is
authoring player conduct — the same boundary `_check_player_act_authority`
defends for speech and action, unguarded for position.

### 1.16 A greeting's knowledge seeds outrank everything the story then lives

**Found 2026-08-01**, investigating chat 53 ("Run!"). Separate from the
establishment-sequence defect that investigation started from, which is fixed;
these are the parts of the same launch that were left alone.

`greetings.start_story` routes `greeting_interpret`'s `knowledge_seeds` into
character memory. The four seeds it wrote for that launch:

```
sal 1.00  The Doctor knows that Daleks are among the most dangerous creatures
          in the universe, and their presence on Earth is a serious threat.
sal 1.00  The Doctor is aware that Hinami has six tail fox ears ...
sal 1.00  The Doctor has a deep-seated fear of Daleks, but he masks it with
          bravado and excitement.
sal 1.00  The Doctor is always on the lookout for new companions, and Hinami's
          ... make them a candidate.
```

The one memory the actual pipeline minted that turn: salience 0.78, first
person, about what happened.

Five distinct problems, none of them covered by a test —
`tests/test_greetings.py` has 30 tests and none touches seed routing:

1. ~~**Salience is the model's unbounded self-report, and it says 1.00.**~~
   **Fixed in alpha 6.6.** Capped at 0.7, just under the 0.72 consolidation
   floor, so a seed decays like anything the character went on to actually
   live. The cap is at the WRITE (`greetings._seed_salience`), not only in
   `GreetingKnowledgeSeed`: `start_story` reads `rec["extraction"]`, a stored
   extraction persisted on the character card at import time, so cards written
   before the cap — or edited by hand — reach the routing site without ever
   passing through the schema. Both are capped; the write is the boundary that
   matters. Covered by `TestKnowledgeSeedRouting`.
2. **Third person, about the character.** The schema's own example is first
   person (`"I have been waiting here for three nights for a courier."`); the
   prompt never states the voice, and the model wrote what reads as a wiki
   summary of him into his own memory.
3. **Invented psychology.** Two of the four are dispositions, not knowledge.
   `director_interpret`'s prompt says flatly "You never author psychology";
   `greeting_interpret`'s asks for what the character "knows, remembers, feels,
   or intends", which invites it. His card already carried the real, better
   version (a Time War `private_history` entry, a `drive.taboo`), served
   through `private_knowledge_for` — so the seed is a flattened knockoff of
   authored material, competing with it.
4. **Outside canon, which the same launch's establishment correctly refused.**
   The prose says "EXTERMINATE", "the thing", "a blue box" — never "Dalek",
   never "Earth". `director_establish` respected that and named the creature
   "The Metal Hunter" with `dalek` demoted to an alias. `greeting_interpret`
   went full canon in the same launch, against its own prompt rule ("Names are
   opaque labels; import no outside canon"). The character's private memory and
   the objective world now disagree about what the enemy is and what planet
   they are on.
5. ~~**`already_known=False` does not reach the seeds.**~~ **Fixed** —
   `greetings.player_handle_for` + `_substitute_player_slot`. See `Design.md`,
   "A character calls the player what they may legitimately call them".
   One residual: the fiction may justify knowledge the engine cannot account
   for — The Doctor could know she was running because the TARDIS has a
   scanner — but there is no scanner in the scene: no anchor, no entity, no
   `world_fact`. The seed asserts a conclusion whose channel does not exist.
   That is a smaller and more general problem than the name leak was, and it
   belongs with §3.1 rather than here.

**Items 2, 3 and 4 are now prompt rules** (`greeting_interpret`): write the
seed first person as the character holds it, never third person about
themselves; author no psychology, because dispositions are on the card already
and a flattened seed copy competes with the authored version; and the
no-outside-canon rule restated inside the seed instruction, which is where it
was being broken. Treat all three as **unproven until observed in conduct** —
two separate correct sheet edits have already failed to change behaviour
(`CLAUDE.md`), and a prompt rule is the same kind of claim. Nothing tests them,
because nothing offline can.

~~seeds carry no `event_key`, so a re-launch or greeting swipe duplicates
them~~ — **half wrong, and now moot.** Seeds carry an `event_key` as of alpha
6.6 (`greeting_seed:<sha1 of content>`), so routing one twice updates a single
row. But there was never a duplication bug to fix: `start_story` creates a
fresh chat every time and is the only site that routes seeds, so a re-launch is
a different story with its own copy, which is correct. The `event_key` buys
identity and a safely repeatable launch, not deduplication.

**Also unbuilt from that design, and cheap:** `start_story` uses exactly two
fields of the extraction (`time`, `knowledge_seeds`). The `rooms`, `positions`,
`entities`, `attire`, `character_state`, `player_room`, `location` and
`scene_description` it spent most of the prompt producing are discarded, and
`director_establish` re-derives the world independently from the raw prose.
That is why the two disagree about the creature: two interpretations of one
passage, and the discarded one is the only one that read it as a greeting.


### 1.17 A generic name cannot count

**Found 2026-08-01**, investigating chat 57 ("Run! ⎇10"), where scene life was
on, the Dalek was speaking, and the ledger still looked wrong.

`background_presences` is keyed by whatever string the prose used. Chat 57 held
ONE Dalek entity in one room and three presences tracking it — `A Dalek` (from
turn 0, 10 speaking turns), `Dalek` (turn 19) and `The Dalek` (turn 23) — split
by nothing but the article. Each carried its own dialogue history, so the same
creature had three partial memories of itself and none knew what the others had
said; `max_managed: 6` counted all three; and promotion thresholds were measured
against a third of the evidence.

**Fixed as far as it can be**: `_presence_identity` ignores a leading article,
`_resolve_presence_name` files a new spelling under the established one, and
`_fold_duplicate_presences` heals a story already carrying the split on its next
turn. Articles only — a title is often the only thing telling two background
figures apart ("the guard" and "the captain" are not one presence), unlike
roster matching where `strip_name_titles` is right.

**What is NOT fixed, and cannot be at this layer.** `A Dalek` and `The Dalek`
are one creature when the room holds one and two when it holds two, and nothing
in the strings can distinguish those cases. The merge is therefore gated on the
scene showing at most one such body (`_bodies_answering_to`), because an
over-merge silently welds two characters into one and a split is only a naming
problem. That gate is a guard, not an answer: with three Daleks in a room the
engine has three presences it cannot tell apart, and the first one to speak
collects everything.

The real fix is that an unregistered presence should be identified by the scene
ENTITY it belongs to — entities already have stable ids (`45c0c640bb354e97`),
and the ledger should key on that, falling back to the name only for presences
with no entity (a voice through a door). That is a schema change to
`background_presences` plus a migration, and it wants doing before any story
seriously tries to run a crowd of identical bodies.

Until then, the practical guidance is the one the failure teaches: **a fiction
with several of the same thing needs several names.** The engine cannot count
`a Dalek`.

### 1.18 The fallback is doing all the work

**Found 2026-08-01**, investigating whether embeddings could make the engine's
word tables "fire and catch" more often. Shelved deliberately after the
measurements pointed somewhere else. Recorded so nobody re-derives it.

The engine carries **196 hand-maintained word tables** (30 in `spatial.py`, 29
in `agents/common.py`, 19 in `weather.py`). Two of them decide physical facts
and were measured against the live database:

| table | matches |
|---|---|
| `weather._ENCLOSED_WORDS` (36 entries) | 42.6% of 155 distinct live room names |
| `attire._REGION_CUES` (154 entries) | 53.3% of 152 distinct live garment names |

**Embeddings are not the fix, measured.** With the real provider
(`perplexity/pplx-embed-v1-4b`, 2560d):

* Region classification: nearest-exemplar 52%, sentence-prototype 47.5%,
  leave-one-out on the cue table itself 52.7% — all LOSING to the dumb
  `DEFAULT_REGION="torso"` fallback at 72.5%, because the unknown tail is
  "…uniform", "…suit", "casual clothing", whose right answer is torso.
* Binary membership is easier and still unsafe: on 20 hand-labelled real room
  names the table scores 10/20 and the best embedding threshold 15/20, but the
  distributions OVERLAP — "back alley" (0.413) outranks "cargo bay 3" (0.305),
  "command deck" (0.332) and "cozy inn" (0.378). No threshold separates them.
* The precision gates are immune by construction: "she lifts her hand toward
  his face" vs "she lowers her hand toward his face" cosine **0.943**;
  "faint"/"faints" 0.784; "puts on"/"takes off" 0.612. Direction, polarity and
  part of speech are invisible to cosine, and those are exactly what
  `_inverted_motion_check` and `_UNCONSCIOUSNESS_CUE` turn on.
* Latency 262 ms for one text against `db.py`'s 0.02 ms commit budget, so
  nothing of this shape may enter the write path regardless.

**What the numbers actually pointed at.** `weather.room_exposure` consults
`_ENCLOSED_WORDS` only when `room.exposure` is unset — and `RoomDef.exposure`
exists in the schema, the prompt says "give every room an `exposure`", and it
is set on **8 of 289 rooms (2.8%)**. The 36-word list is deciding 281 of them.
`scene.attire[].regions` is authored on **13 of 135 entries (9.6%)**, so the
cue table decides the rest.

So the tables are not the mechanism; they are the fallback that became the
mechanism because the authoritative field is never populated. Worse,
`room_exposure` recomputes the guess from the room NAME on every read and
never stores it, so a wrong guess cannot be corrected by a user and changing
the word list silently rewrites the past.

**The proportionate fix, when it is wanted:** seed `exposure` once at commit
from the existing guess and STORE it, so downstream reads a stored fact that
can be edited; and emit a reconciliation signal when a room is created without
one, the same shape as `restraint_scan` and `unconsciousness_scan` already
use. Then the word list serves ~3% of rooms instead of 97% and its gaps stop
mattering. Same question first for any other table: **is there an
authoritative field this is standing in for?** Where there is not
(`_SPEECH_VERBS` parsing model prose, `_BARRIER_ALIASES`), the table really is
the mechanism and coverage work is legitimate.

**Rejected outright:** embeddings in any precision gate; embedding region
classification; embedding identity matching for presences (an over-merge welds
two characters); `cheap_embed` for anything semantic (29.5% on the region
task); any provider call inside the write lock.

### 1.19 An unregistered presence has no name to be called by

**Found 2026-08-02**, fixing the Dalek whose acts never rendered (chat 58,
"Run! ⎇10 ⎇20", t23). Shelved deliberately: the fix is a change to the identity
gate, and widening that on a hunch is worse than the wrong label.

Two defects behind that turn were fixed. `cast_room` could not map a background
presence's NAME to its uid-keyed position, so `spatial_rel(None, room)` called
a machine standing in the player's own alley "remote, no known spatial channel"
and the hearing gate dropped its line for every observer — 47 of 78 background
lines corpus-wide never reached a view. And `_ordered_beat_events` collected
only a reaction's `dialogue_log_entry`, never its `action`, so a presence's act
reached the narrator nowhere. Both are closed; see `Design.md`.

**What is still wrong.** The act now renders, attributed to **"the unfamiliar
person"**. `wget(58, "known")` is `{"Hinami": ["The Doctor"], "The Doctor":
["Hinami"]}` — the Dalek is not in it, so `_speaker_display` sends it to
`_unknown_actor_label`, which derives a short descriptor from the actor's
appearance summary. An entity has no cast sheet, so there is no appearance, and
it falls through to the generic string. Wrong twice over: a Dalek is not a
person, and it is not unfamiliar — she had been warned about them and had just
thrown a rock at this one.

**The fix, and why it is not in yet.** The recognition gate exists so a
perceiver does not use a PROPER NAME they have not earned. An unregistered
presence's `name` is not that: it is authored as a descriptor — `A Dalek`,
`station engineer`, `Docking Control Operator` — and entities carry no
`identity`/`uid`/`known_to` machinery at all (both entities in chat 58 have
`identity: None`). So an entity should display under its own name, and only a
cast character's name should have to be earned.

Not done because the label is decided in two places and perception's is the
authority: perception wrote "something rolls forward a half-meter" and "The
Doctor steps between her and **the source**" into that same view. Fixing the
narrator's binding alone would leave the page and the view disagreeing about
what the player is looking at. The change wants both ends and an adversarial
identity pass, since every widening of this gate is a candidate identity leak —
the exact failure `_unknown_actor_label` was built to close when a label
derived from an appearance summary leaked the canonical name inside it.

### 1.20 A body's room changes with no warrant, and the scene never recovers

**Found 2026-08-02**, investigating chat 58 ("Run! ⎇10 ⎇20"), where the final
turn's perception made no narrative sense and `director_resolve` produced
incoherent output on strong models. Shelved deliberately: the guard is easy to
write and easy to write WRONG, and getting it wrong blocks legitimate movement
in every story.

Nothing validates that a position change was earned. `state_diff.positions` is
merged as written, so the Director can relocate a body on a beat where nothing
moved, and every later beat inherits it.

Measured, from each turn's own `state_diff`:

| turn | player input | positions written |
|---|---|---|
| t23–24 | throws a rock, ducks | everyone `alley_room` |
| **t25** | *"You pick up a rock again and chuck it… at the Dalek's eyestalk"* | **Doctor + Hinami → `street_outside`**, a room minted this turn |
| t26 | rolls behind a dumpster | Dalek → `street_outside` |
| t27 | dashes for the TARDIS | Hinami → `alley_room`; the other two stay |
| t28 | charges in, slams the doors | Hinami → `tardis_console_room` |

Nobody moved at t25. The map itself is fine — `tardis_console_room —(closed
door)— alley_room —(open)— street_outside` — and the TARDIS is in the alley.
The POSITIONS are wrong, and the whole fight is written as happening at the
TARDIS doors while two of its three participants stand a room away.

Everything downstream follows, and none of it is separately broken:

- `spatial_rel(tardis_console_room, street_outside)` is `separated`/`far`, so
  the Doctor's `normal`-volume lines reach Hinami only through
  `_dialogue_hear_level`'s by-name floor. That floor is NOT the bug: put the
  Doctor where the fiction puts him and `hear_level(closed_door, "normal")` is
  `fragment` — a muffled voice through slammed doors, exactly right.
- The Doctor declared *"steps between Hinami and the advancing Dalek"* and
  *"Hinami—behind me, now!"* for someone two rooms away behind a door she had
  just slammed. Correct conduct given his view; the view was wrong.
- `director_resolve` is then asked to resolve one continuous fight between
  three bodies the geometry says cannot see, hear or reach each other. There
  is no coherent resolution of that input. A stronger model returns more
  confident nonsense — which is what "failing even on strong models" looks
  like from the outside.

The scene also contradicts itself in prose by t28: `alley_room.desc` says "a
blue box appeared and vanished, leaving only empty air… The TARDIS is no
longer here" while `positions` still holds the TARDIS entity in `alley_room`,
and `tardis_console_room.desc` says the doors "stand sealed" while its own
`notes` say they "now stand open". And the Dalek's position key changed from
its entity uid (t23–24) to its name (t26 on), orphaning the entity record —
§1.17's fragmentation, in `positions` this time rather than
`background_presences`.

**The rule wants to be:** a body's room may only change with a warrant this
beat. **Why it is not written yet:** there are three warrants and only two are
legible. The player's `director_interpret.movement.to_room` is explicit, and a
character's declared locomotive action is inspectable — but Director-driven NPC
movement (someone walks in, someone flees) has no signal beyond the resolve's
own prose naming them moving, which is exactly the fuzzy test that would make
the guard either useless or a blocker on ordinary play. Prove that third
warrant before writing the guard; a check that silently pins NPCs in place is
worse than the drift it replaces.

Two consequences of the same investigation ARE fixed, because they hold on any
geometry: `_strip_unreachable_bodies` (a body with no sensory channel is not
described to a perceiver) and `_subject_opener` (a leading article belongs to
the prose, not the name, so a body registered "A Dalek" is caught when the
prose writes "The Dalek's"). See `Design.md`.

### 1.21 A character's origin cannot be reached by similarity, and 53 banks have none to reach

**Found 2026-08-02**, implementing summary windows. **Mostly landed 2026-08-02**
— the payload half is built (`earlier_in_my_life`, see `Design.md`). **The
origin-era ranking question is now landed** — `build_character_memory_context`
surfaces the earliest first-hand summary window under `where_i_came_from` when
a drift signal fires (goal held 12+ beats, a project adrift 8+ beats, or a
mood sign-flip from baseline). See `Design.md`, "Origin-era retrieval on drift".

The old hole is repairable and the host exposes it: the memory UI calls
`backfill_memory_summary_windows`. Reconstructed windows are also propagated
into every eligible pre-turn checkpoint (`end_turn_idx < checkpoint.turn_idx`),
so a later reroll cannot silently restore the legacy singleton and erase the
repair. Chat 38 was repaired from its pre-change backup on 2026-08-02: 41
summary windows are live again and 109 eligible checkpoints carry them.

**Still unmeasured:** conduct. Everything above measures payload composition.
Whether a character behaves differently for having their earlier chapters is a
maze-arm question, not a one-turn read.

### 1.22 One window answers most beats, because every view describes the same person

**Found 2026-08-02**, measuring the window layer against chat 38's real
perception views rather than hand-written probes. **Re-tested and rejected
2026-08-02.** Against 27 historical beats, using the era most represented in
the raw semantic retriever's top 16 as the reference, the unchanged window
ranker reached 70.4% top-1 / 81.5% top-2 agreement. Stripping the appearance
tail reduced that to 63.0% / 77.8%; adding goal, mood and concern aspect RRF
reduced it further to 48.1% / 74.1%. Neither change shipped.

Asked a query that NAMES an era, the layer is accurate: "the replicator logs,
the miso soup and the mochi" returns windows (50,59) and (60,69) at 0.486/0.409;
"the Jefferies tube and the phase-doubled conduits" returns (90,99) and (80,89).
Raw recall agrees -- it returns turns 50-66 and 89-106 for the same two.

Asked a REAL view, it collapses. Across 30 of the Doctor's actual
`perception_act` views spanning turns 30-117, the origin window (0,9) wins **24
of 30 beats**, including deep inside the Deck-14 anomaly, and **7 of his 11
windows are never returned at all**.

The cause is that a real view is mostly a description of who is standing there,
and in a two-hander that never changes. His views nearly all describe Hinami,
and the window that describes her most is the one where they met. The layer is
ranking on the constant component of the beat instead of the variable one.

**What was tried and did not work.** Hubness correction -- subtract each
window's mean similarity across all views, so a window that matches everything
matches nothing. Measured against raw recall's era as reference, it made
targeting WORSE (median distance 12 turns vs 7; 4/30 exact-era hits vs 6/30).
Recorded because it is the obvious first idea.

**What did help, partially.** Every view carries a boilerplate tail -- `You see
A beautiful young woman appearing in her early twenties, with golden fox ears
and six golden tails.; wearing: modern casual attire.` -- identical on every
beat and ~24% of an average view's length. Stripping it FROM THE RETRIEVAL
QUERY ONLY (not from the view the character reads) drops the hub from 24/30 to
19/30 and lifts two starved windows from 1 pick to 4 each. Cheap and worth
doing, but it is not the whole cause.

**The initially proposed fix did not fit this layer.** Raw memories are short
enough for aspect fusion to help; chapter summaries are already compressed and
the added rank lists pulled them away from the era selected by raw recall.
Boilerplate stripping also removed useful identity/context signal along with
the constant tail. The remaining problem needs a different candidate and the
same historical replay before it lands.


---

### 1.23 Memory, psychology and capacity — landed 2026-08-03

Raised in review, planned, measured, then built. **The measurements changed
the plan more than any argument did**: two shelf items were cancelled, one was
inverted outright, and the harness written to make the plan honest found three
dead mechanisms nobody had gone looking for. What follows is the record; the
work itself is in `Design.md` and the tests named below.

#### The through-line: fire rate before enrichment

Every mechanism examined fell into one of three states, and the state was
never obvious from reading the code.

| mechanism | fires | note |
|---|---|---|
| aspect rankings | **constantly** — top-16 membership in 39/40 | argued dead, is the most active thing in retrieval |
| `unbidden_probe` / `manifest` / `mind_model_updates` | 98-100% | |
| `relationship_updates` / `memory_effects` | 88-89% | |
| `remember_lines` | 78% of eligible beats | |
| `intent_ops` | 79% | |
| salience | always, **compressed** — p10-p90 spread 0.27, 70% of rows in 0.6-0.8 | |
| `encoding_valence` | 20.7% overall; 2 of 37 banks ever record a non-zero one | `NOT NULL DEFAULT 0.0` hides the rest |
| importance revision | **0.14%** (9 of 6,480) | read one field; the field that answers it fires 89% |
| disputes | **0.00%** (0 of 181 eligible beats) | reachable, never occasioned |
| **projects** | **0 of 14 banks have ever held one** | the tier was unreachable from empty |
| `initial_parallel_reactors` | never, until 6.9.1 | |
| `BehaviorController` | never, until 6.9 | |
| `ActionStage` (§1.13) | never | |

**No mechanism should be enriched before its fire rate is known.** Three of
these were assumed live and were not; one was argued dead and is load-bearing;
one was an entire tier of psychology, with the longest single block in the
character prompt behind it, that had never once run.

#### What was built

**Phase 0 — `tools/fire_rates.py`.** Per-mechanism fire rates over the corpus,
`--last N` per chat, `--chat`, `--json`. Read-only; opens the database
`mode=ro` so it is safe against a live `engine.db`.

Its whole discipline is the DENOMINATOR. `memory_disputes` measured against
every memory row reads 0 of 6,480 — a number that sounds catastrophic and
means nothing, because the field did not exist for most of that corpus.
Measured against the beats that could have carried one it reads 0 of 181,
beside a sibling introduced in the same commit, on the same 181 results,
firing 78%. That second pair is a diagnosis. A mechanism with no opportunities
reports `no chances`, never 0%. Tests: `tests/test_fire_rates.py`.

It found the dead project tier on its first run.

**Phase 1 — salience respacing, and the fix that was nearly a weight
increase.** `tools/salience_replay.py` replays real recall against the real
bank with the term live, deleted, and spread. It needs no embedding provider:
a probe's own stored vector is the query and the turn cutoff is the beat it
formed on, so each probe is an honest "what did this mind have to hand", and
it copies the database first because `search_memories` bumps `access_count`.

270 probes, top-16 membership moved:

| arm | moved |
|---|---|
| the term deleted entirely | 35.2% |
| percentile-normalised to [0,1] | 59.6% |
| stretched 3x about the mean | 47.0% |
| respaced inside the bank's own range | **15.2%** |

The term was never silent, and **both planned fixes moved retrieval more than
deleting the term did** — values occupy a 0.27-wide band, so mapping them onto
[0,1] multiplies this term's influence by ~3.7 while reordering nothing. A
weight change wearing the word "normalisation". What shipped is
`memory._rank_normalized_importance`: rank-normalise inside the visible rows'
own p10-p90, so ordering and influence budget both hold and only spacing
moves. The defect it fixes is that discrimination currently depends on how the
minting model happened to spread its numbers that day. Tests:
`tests/test_salience_respacing.py`.

**Phase 2a — disputes are reachable; they were never asked for properly.**
`tests/test_dispute_reachability.py` builds the occasion the corpus never
produced — a stranger remembered as kind, seen this beat picking a pocket —
and walks a model-shaped dispute through schema coercion, citation grounding,
the commit collector, `record_dispute`, and the projection that hands the
re-reading back next beat. Every stage holds, including the three refusals: it
cannot reach another mind's memory, cannot locate one never delivered, and
never edits what it re-reads.

So 0/181 is an absence of occasions, and the prompt was the other half. The
instruction was two prohibitions and one abstract permission, next to
`memory_effects` — which fires 89% and names four concrete occasions. CLAUDE.md
records the same shape twice from the maze arms: bare prohibitions invert. It
now names five occasions (a disguise, a staged kindness, a lie, the wrong
person, an arranged scene) and keeps both constraints.

**Phase 2b — importance was reading the rarest field a character emits.**
Measured over the 83 results that could supply any candidate signal:

| signal | fires |
|---|---|
| `mind_model_updates` evidence citing a stored memory | 6 of 83 |
| `belief_updates` evidence citing a stored memory | 1 of 83 |
| `memory_effects`, disposition `integrated` | **74 of 83** |

`_cited_memory_ids` read only the first. It now reads all three;
`resisted`/`dismissed` still do not count, and `only_unrevised=True` still
holds each memory to one lift for its whole life, so this widens the
population that can be lifted once, never the amount. Tests:
`tests/test_importance_signal.py`.

**Phase 2c — the project tier could not be entered from empty.** One condition
written twice: `affect.project_boundary` opened `if not projects: return None`,
and the payload guarded `if isinstance(_preview, dict) and
_self.get("projects")`. The prompt names the review beat as the occasion to
emit `project_ops` — and the review beat required a project. The
payload-affordance rule (`Design.md` § Structural debt #1) from a new
direction: there the payload made the asked-for thing harder to reach, here
it withholds the occasion entirely, and no prompt argues with a key that is
never present. Arrival still needs a project to arrive at; a task closing and
the scene or frame changing no longer do. Tests:
`tests/test_project_tier_reachable.py`.

**Phase 3 — capacity as an authored spectrum.** `psychology.capacity`, one of
`narrow / focused / ordinary / broad / wide`, scaling the want and intention
caps (1/2 through 5/6) and narrowed one further by cognitive absorption. The
want cap binds 79.6% of live banks at mean 2.65 — not a safety valve, the shape
of every character's attention, authored once by whoever picked 3. Precedent:
`theory_of_mind.sheet_capacity`.

Projects stay off the ladder deliberately: `PROJECT_CAP` is a DRAMATIC limit,
and a character allowed six projects has lost the displacement rule that makes
one mean anything.

`ordinary` is exactly the pair that shipped, and unset is stored as `""` rather
than backfilled — the first version backfilled `ordinary`, which made "the
author chose the middle" and "nobody has seen this field" the same value and
silently killed the import warning written to prevent exactly that. The
character is told its own ceiling (`self.attention`) rather than having wants
culled without being told the decision existed. Editor control included. Tests:
`tests/test_attentional_capacity.py`.

**Phase 4a — `remember_lines` measured, and NOT gated.**
`tools/remember_lines.py`, over 1,633 turns and 146 marks:

| | |
|---|---|
| landed as a memory row | 125/146 (85.6%) |
| the fixed phrase list had it too | **0/125 (0.0%)** |
| only this character's judgement kept it | 125/125 |
| retrieved later, kept by judgement | 38/125 (30.4%) |
| retrieved later, every non-dialogue row | 587/6,326 (9.3%) |

Zero overlap with the phrase list and 3.3x the baseline retrieval rate. A
budget or novelty gate would throttle the highest-yield rows in the bank, so
neither was built. Two things the measurement could not answer are recorded
rather than guessed: `why` is present on 146 of 146 marks and so predicts
nothing, and 21 marks matched no row. The discriminator needs no schema change
— the phrase list is a pure function of the quote, so a kept line the list
would have rejected is one only this character preserved. Tests:
`tests/test_remember_lines_telemetry.py`.

**Phase 4b — summary support sets.** `memory_summaries.support` (schema v25),
one entry per clause: `{claim, support_refs, epistemic_origin}`. Derived
host-side by content-word overlap against the window's own memories at
consolidation — no model call, because an audit trail produced by the same kind
of process it audits is not one — and scoped to the summary's own epistemic
class, so a first-hand clause cannot be supported by hearsay. Refs are
`event_key`s, so checkpoint rollback and branching need no remapping. An empty
support set is the finding: the clause generalises, compresses, or was
invented, and it is now countable. Tests: `tests/test_summary_support.py`.

**Phase 5 — time travel, and the traveller who came back.**
`tests/test_time_travel_memory.py` covers the five flagged shapes. One was
broken: `is_memory_visible` granted a traveller continuity by checking the
travellers list of the frame they are STANDING IN, and the present is the
implicit frame with no row, synthesised by `get_frame(None)` with an empty
travellers list. So the clause could never fire in the present — a character
who visited the year 5000 and walked home could not recall one moment of it.
Everything while standing there, nothing once back where they live.

Fixed by also honouring the travellers list of the frame the memory was FORMED
in. Safe because every caller arrives through `visible_memory_rows`, which has
already filtered `char_id=?`: the only question this rule ever answers is
whether a mind may reach its OWN experience. A native of the present is not a
traveller of the future frame and still sees nothing.

#### Cancelled by measurement

**Importance saturation.** The predicted failure was a permanently-elevated
tier accumulating over a long life. Importance is revised on 9 of 6,480
memories; the monotonic ramp is not a risk because it does not run. The
three-way split is not needed. What the measurement found instead became
Phases 1 and 2b.

**Spreading salience.** See Phase 1 — the planned fix moved retrieval more than
deleting the term.

**A budget or novelty gate on `remember_lines`.** See Phase 4a.

**Dispute histories** stay deferred. The prompt fix is landed and unmeasured;
the fire-rate harness is what will say whether disputes now happen at all, and
a history is worth building when there is something to have a history of.

#### Still open

- `encoding_valence` is `NOT NULL DEFAULT 0.0`, so "recorded neutral" and
  "never recorded" are the same stored value. A fire rate given up at schema
  time. Only 2 of 37 banks have ever written a non-zero one.
- Mood congruence blends encoded tone with incoming mood 75/25
  (`memory._congruence_valence`). **Principled but unmeasurable**: 738 memories
  carry both values, exactly 2 disagree in sign, and neither field has ever
  gone below -0.05 in the banks that have the column. These stories are warm;
  the "opposite feeling pushes down" half has never fired. Revisit with a story
  that goes dark.
- `character:<id>` parallel steps fire on 3 of 1,633 turns. Either the gate is
  wrong or the branch is vestigial; nobody has asked which.
- Whether the project tier now fires. Re-run `tools/fire_rates.py` after a
  story or two and read `has ever held a project`.

### 1.24 What the enclosure investigation found and did not fix

From the same live story as the enclosure fixes (`Design.md`, "A body sealed
inside another body"). These were observed in the same sweep, are real, and
were left alone deliberately — each needs a decision rather than a repair.

**One being, two names — now folded at merge.** *(landed)* The enabling
condition behind five of the six defects fixed in that pass: a character can be
registered cast AND present as a scene entity with its own id, with nothing
joining the two records. `normalize_scene_subjects` now folds every
subject-keyed ledger onto one spelling per being before anything resolves one
ledger against another, so `==` is correct again because there is nothing left
for it to be wrong about. `same_subject` stays as the floor for raw model
output that never went through a merge.

The scope was the hard part and getting it wrong was worse than the defect:
the first version folded on identity alone and broke eleven tests, because
`positions` legitimately keys objects, fixtures and unregistered presences by
entity id and readers resolve them that way. Two rules keep it narrow — fold
only when the canonical name is ALREADY live as a subject spelling elsewhere in
the scene (the defect is two records for one being, not "ids ought to be
names"), and an id differing from its name only by case is its own evidence and
does not count. Ambiguity still folds nothing: two entities named "A Dalek" are
two Daleks.

**Body scale is not a perception input.** `hear_level` takes a volume, a
barrier, a proximity and a vouched flag; it does not take a size. A body at
0.05 scale shouting and a body at 1.0 shouting are the same event to the
engine, and the same is true of what a tiny body can smell or be smelled at.
`scales` is already in the scene and already gates contacts and containment, so
the input exists; what does not exist is a defensible curve. Measure before
picking one.

**World pressure does not ask whether anyone can reach it.** Live, an
"Unlatched window" pressure kept demanding a tick — `must_tick_this_beat` —
while the only character who could have acted on it was sealed inside another
body and had no sensory channel to the room at all. A pressure nobody can
perceive or reach is not stalled, it is suspended, and forcing it to advance
puts a beat's weight on something the scene cannot honour. The reachability
test now exists (`enclosed_from_source`); nothing consumes it here yet.

**An entity's state can go byte-identical while the prose names it.** Warned
three times in this story: "this beat's prose names it, but its
posture/description came through byte-identical". The warning is right and
nothing acts on it. Whether that should be a repair, a re-ask, or left as
telemetry is undecided.

**A derived observation carries one channel for a compound sentence.** The
re-derivation assigns a single `channel` per atom, so a sentence carrying both
a sound and a scent ("breath comes in short gasps, the air thick with...") is
filed under one of them and the other becomes unattributed. Minor, and the fix
is either sentence splitting before classification or a multi-channel atom;
both are more invasive than the defect.


### 1.25 Every character call re-ingests 12,400 cacheable tokens, because a name sits at byte 32

Measured 2026-08-03 while benchmarking nano-gpt subscription models. Not fixed:
the fix is one line, and the evidence that it is WORTH making is incomplete in
a specific way described below.

**The defect.** `prompts.DEFAULT_PROMPTS["character"]` opens

    "You are the decision process of {name}, not a narrator..."

with `{name}` at **byte 32 of a 55,558-character prompt**. A provider caches a
PREFIX — the hit runs from the start of the message to the first byte that
differs — so two characters in the same beat share only the ~8 tokens before
the name, and the other ~13,880 tokens of byte-identical contract are
re-ingested cold, per character, per turn. Every other system prompt in the
engine has zero template variables and is already maximally cacheable
(`director_resolve` 13,794 tok, `perception` 5,885, `narrator` 5,488,
`director_interpret` 4,205, `mapping_stage` 3,122). `variant_seed` is already
last in every payload, so the nonce is not implicated.

**Measured across 14 subscription models** (`tools/cache_probe.py`, two calls
per arm: the same prompt as `Elyndra` then as `Hinami`, which is what a real
multi-cast beat does). `relocated` moves the name clause to the end of the
prompt; `split` leaves the wording untouched and sends the contract as its own
message:

| model | as-is | relocated | split |
|---|---|---|---|
| `zai-org/glm-4.7` | 1% | **99%** | **99%** |
| `mistralai/mistral-large-3-675b` | 0% | **99%** | **99%** |
| `google/gemma-4-26b-a4b-it` | 43% | **98%** | 0% |
| `moonshotai/kimi-k2.5` | 0% | **98%** | 1% |
| `moonshotai/kimi-k2.6` | 0% | 0% | **98%** |
| `inclusionai/ling-3.0-flash` | 0% | 64% | 64% |
| nemotron 550b / super-120b, `Qwen3-Next-80B`, `glm-5.2`, `qwen3.5-397b`, `deepseek-v4-flash` | 0% | 0% | 0% |

**`as-is` is 0% on every model that caches at all.** Four recover 98–99% when
the name moves. Live confirmation from a 10-turn run: overall cache hit rate
**18.9%** (46,784 of 247,374 prompt tokens), with `character`, `director` and
`narrator` calls all at **0** while `perception` — which fires 7x in seconds
and stays warm — hit 5,440–5,696 per call.

**Why it is not fixed.**

1. **A cache hit is not a speed win, and may be a loss.** On
   `gemma-4-26b-a4b-it` relocation took a call from **33.1s to 4.0s**. On
   `kimi-k2.6` the 98%-cached arm ran **5.3s → 34.6s**, 6.5x SLOWER. `glm-4.7`
   improved modestly (10.6s → 7.3s); `ling-3.0` got slower. Cache support,
   cache benefit and raw latency are three independent properties, and only
   the first has been measured properly. `tools/cache_latency.py` (cold call 1
   vs warm calls 2-5, fixed output length) exists to settle it and has not been
   run to completion.
2. **There is no universal layout.** `kimi-k2.5` wants `relocated` and gets 1%
   from `split`; `kimi-k2.6` is the exact inverse; `gemma` wants `relocated`
   and gets 0% from `split`. Any fix has to be verified per model rather than
   adopted as a general improvement.
3. **Byte 32 of a system prompt is high-salience real estate.** "You are
   {name}" opening the contract may be doing real work for character
   adherence, and moving it is exactly the class of change CLAUDE.md warns
   about: nothing errors, and a character reads subtly wrong fifty beats later.
   `split` avoids this — same tokens, same order, only the message boundary
   moves — which is why it is the preferred shape where it works.

**What to do when this is picked up.** Run `tools/cache_latency.py` first. If
warm calls are not reliably faster on the models actually in use, this entry
closes as "measured, not worth it" and the prompt is left alone. If they are,
prefer `split` over `relocated` (no wording change), verify per model, and
A/B on a long story with `tools/stability_run.py` — a character-adherence
regression will not show up in a test suite.

**Related, unfixed:** caching is a property of the MODEL and the layout jointly,
and nothing in the model-selection process accounts for it. `Qwen/Qwen3.6-35B-A3B`
cached 0 of 188 live calls; `nex-agi/nex-n2-pro` cached 63 of 79. On a pipeline
this prefill-dominated (27k-token director payloads), that may outweigh every
latency difference measured in `docs/experiments/bench-2026-08-03/RESULTS.md`.

**Update 2026-08-08 — the switch this entry needed now exists, and the wrong
file was nearly used to settle it.** Prompt caching is a per-provider checkbox
in ⚙ API (`prompt_cache_enabled_for`, `PUT /api/providers/{pid}/prompt_cache`),
so arm 1 above — "is a cache hit actually faster on the models in use" — can now
be A/B'd on a real story rather than only in `tools/cache_latency.py`.

Two traps found while building it, both worth writing down because both produce
a confident wrong answer:

- **`docs/experiments/bench-2026-08-03/*.log` cannot answer this question.** All 62 cache
  reads across its 267 timed calls come from ONE model, `nex-agi/nex-n2-pro`,
  and none of the logged models is a Claude. The engine's breakpoint is gated on
  `_model_is_anthropic`, so it never marked any of them — those `cached_tokens`
  are the provider's own implicit caching. Splitting that file cached-vs-uncached
  compares one model against all the others, and duly produces a spurious 2x
  "caching penalty" at 1200+ response tokens (83.70s vs 42.36s, n=8). The real
  measurement is the `tools/cache_probe.py` table above, which controls for
  model by construction.
- **The live config caches nothing.** As of 2026-08-08 no configured role runs a
  Claude model (`minimax/minimax-m3`, `moonshotai/kimi-k2.6`, `x-ai/grok-4.20`,
  `inception/mercury-2`), so the engine's marking is inert on this install and
  the new checkbox changes nothing until a role points at a Claude. Note that
  `kimi-k2.6` — currently `default` and `character_mid` — is the model whose
  98%-cached arm ran **6.5x slower** in the table above.

### 1.26 Speech-channel smuggling — landed 2026-08-04

Found in chat 62 (12 turns, character roles on `moonshotai/kimi-k2.6`
non-thinking, Director on `x-ai/grok-4.20`). A character wrote stage directions
into the `text` of its speech elements, so body movements were delivered as
SOUND: lost to a listener who could not hear, ground into fragments by
muffling, and — the one that matters — narrated by ear to a listener who could
hear but not see. Flow, not knowledge; the person touched would have felt it.

`agents.common.split_stage_directions` excises the span in `norm_sequence` and
re-files it as the action element it should have been, before the speech it was
buried in, inheriting that line's concealment. Full record in `CHANGELOG.md`
§ alpha 7.0; tests in `tests/test_speech_channel_smuggling.py`. It also closed
a second symptom that looked unrelated: the Director re-rendering the stage
direction as prose, which no longer matched the declaration, so the
verbatim-speech guard dropped the line as invented on 7 of 12 turns against 7
of 1,715 corpus-wide.

**Not measured yet:** whether the promoted actions change how often the
Director ends a beat. Every one arrives with `commitment` classified from its
own text, and `_requires_director_resolution` reads that field (see alpha
6.9.1). A stage direction reading as contestable would end beats that used to
continue. Re-run `tools/fire_rates.py` after a story or two.

### 1.27 Residuals from the speech-channel investigation

Found in the same pass. The attire-blob accumulation is now fixed (`commit.py`
rebuilds `state` from `attire.flat_state` unconditionally and keeps only notes
`attire.is_derived_state_note` says were authored; `tests/
test_attire_commit_stored_shape.py`). The rest are open.

- `manner` on a `contacts` row is free text with no engine semantics, so a
  contact describing one body partly inside another does not populate
  `contained` and none of the §1.24 enclosure-direction work fires on it.
  Whether it should is a design question — partial containment is not the same
  as being sealed inside something — but the two are currently unrelated code
  paths that describe overlapping physical situations.
- Two `remember_lines` were dropped whole across 12 turns because the character
  cited event ids that do not exist. The guard is right to drop an ungrounded
  citation; the cost is that the line the character chose to keep is discarded
  rather than salvaged with its citation stripped. Given Phase 4a measured
  these as the highest-yield rows in the bank (3.3x baseline retrieval), losing
  one to a malformed reference is expensive.
- `intent 'ia2'/'ia3': already at full progress, nothing gained` repeated on
  three consecutive turns, escalating to `stalled ... satisfy, abandon or
  re-route it`. The intention ledger has no way to retire an intent the
  character keeps re-serving at ceiling, so the warning fires forever and the
  character keeps spending declarations on it.


### 1.28 Residuals from the contact-sensation work

Landed 2026-08-04: `spatial.contact_sensation` and
`agents.perception._deliver_standing_sensations` (see `Design.md` § A standing
contact is a continuous percept, tests in
`tests/test_continuous_contact_sensation.py`). These are what the same
investigation found and did not close.

- **`contacts` accepts a part slot that does not name a body.** A live ledger
  holds `actor_part: "physical reaction"` against `target_part: "laughter"`.
  Nothing rejects it at the Director, so it is carried, aged and re-asserted
  like a real contact. `spatial._is_anatomical_part` is a FLOOR at the renderer
  — it declines to describe a sensation nobody could have — and the record is
  still wrong where it is written. The right fix validates the slot on the way
  into the scene commit. A permissive check is the only kind available: anatomy
  is open-ended and every story invents some, so the test can only reject what
  is affirmatively not a part.
- **Partial interior contact still does not populate full containment.**
  Contact sensation no longer asks free-text `manner` to carry two axes:
  `relation: surface|interior` and `motion: settled|moving` now independently
  drive rendering, with backward-compatible derivation for old rows. That
  closes the perception ambiguity, but an interior contact still does not
  populate `contained`, so the §1.24 enclosure-direction work does not fire on
  it. Whether it should remains a design question: partial containment is not
  the same as being sealed inside something, and the two remain separate code
  paths describing overlapping physical situations.
- **Observation metadata is computed and consumed by nothing.** `intensity`,
  `suddenness`, `ambiguity` and `directed_at_self` are re-derived from the
  scrubbed view for every atom, cost tokens on every character payload, and
  have no reader in code — `intensity` does not appear anywhere in the
  character prompt either. They are also nearly constant: `intensity` is 0.35
  on **96.7%** of 7,508 observations, and only 18 distinct
  (intensity, suddenness, ambiguity) tuples exist corpus-wide, because the cue
  lists behind them are an adventure vocabulary (explosions, gunshots, alarms,
  agony). Either give them a consumer or stop computing them; a field that
  tells a character every percept is equally important is worse than no field.
- **`directed_at_self` mislabels the intransitive own-body case.** Of 590
  observations opening on the perceiver's own body, **64.7%** carry
  `directed_at_self: false`, because `_SELF_DIRECTED` recognises only
  agent-first constructions ("grips your", "against you") and "Your body keeps
  spasming" matches none of them. Fixed for the deterministic sensation clause
  only, keyed on its verb rather than on a bare leading `your` — "your
  companion steps back" is not about the perceiver, and a broad rule would
  claim it is. Inert until the field above has a consumer.
- **The atom budget collapses channels.** `_observation_spans` merges
  smallest-first to fit `_MAX_OBSERVATION_ATOMS = 8`, and merging two spans of
  different channels marks the result `mixed`. That accounts for 16.6% of
  `mixed` observations — secondary to the 83.4% that matched no cue at all, but
  it means a beat arriving through MORE senses loses more channel information
  than a simple one.


### 1.29 Parallel reaction chains, and the isolated wave that is shelved for them

Written, tested, switched off 2026-08-04. `agents.loops._perceptually_isolated`
and `_isolated_wave` exist and are covered by
`tests/test_interaction_first_wave.py`; `parallel_isolated_reactors` is
`False` in `DEFAULT_INTERACTION_CONFIG`.

**The rule is right.** The beat now opens with ONE character so causality can
build (§ alpha 7.2), and the one honest exception is a reactor who could not
possibly perceive the opener -- separate room, no sight, nothing audible.
Sequencing those two claims an order no reader could detect, and running them
in one instant is what offscreen simulation needs.

**Why it is off.** Every reactor in a beat today is somebody the player can
hear, so the branch would never fire on a real story and its first live run
would be its first exercise. It is switched off until there is offscreen life
to run through it.

**The loose end whoever turns it on inherits.** Isolation is tested at `loud`,
not at `shout`. The engine's own model says a shout carries a FRAGMENT between
far separated rooms, so testing at `shout` makes nothing anywhere isolated and
the branch dead; testing at `loud` means a character who actually shouts can
reach somebody the wave already treated as unreachable. The honest fix is
re-running an isolated reactor when a shout was in fact declared, which needs
the declaration first and so needs the loop restructured.

**Where this is going.** `_isolated_wave` grows greedily and checks each
candidate against every member already in the wave, because two characters
together in a far room can hear each other and belong in sequence with one
another even though both are isolated from the opener. That is already the
shape of the real feature: the cast partitions into perceptual components, and
each component is its own **reaction chain** -- sequential within itself,
genuinely parallel with the others. The current code produces the partition's
first slice; the generalisation is to run every component as a chain rather
than only admitting the isolated ones to one opening wave.

**Interruption is solved, declaratively.** Landed 2026-08-04 -- `interrupts`
on a speech or action element, resolved against who actually spoke and who
could actually hear them, with `agents.common.cut_short_speech` breaking the
interrupted line at a breath point. See `CHANGELOG.md` and
`tests/test_interruption.py`. It needed no change to ordering, which was the
point: a character later in the chain has already heard the line they want to
cut off.

Still open there: the Director does not yet adjudicate an interrupted ACTION.
The element is marked `interrupted: true` and the Director resolves it like any
other attempt, so a reach that got grabbed and a reach that did not are handed
over identically -- the flag is written and nothing reads it. Giving it force
is a Director rule about which of two colliding attempts survives intact, and
it is the natural companion to `commitment: "contestable"`.

### 1.30 The background-claims lane has never once fired

Measured 2026-08-08, against the live corpus: **0 claims ever recorded, across
17 chats playing at `scene_life=full` over the corpus's 2,114 turns and 46
tracked presences.** That is the real denominator -- an earlier 0-of-29 was
measured against beats, which undercounts the opportunities and made the
silence look like sparse data instead of a dead lane. The lane's entire
downstream -- `background_claims.record_claims`, `unratified_claims` riding
every resolve payload, `settle_claims`, `write_canon`, `canon_provenance` --
has processed nothing, ever. It is built, tested, documented, and has never
run on a single live datum: the exact shape the fire-rate rule in `AGENTS.md`
exists for.

Why, structurally: a claim only enters the lane when `scene_life` output
survives `_claimed_refs` -- either the model volunteers `asserts` (it never
has) or `novel_proper_nouns` finds a capitalized phrase not already in
`_known_world_names` (managed presences mostly answer about things already
named). Nothing else in the engine mints claims. The lane is therefore held
shut by prompt compliance alone, in both directions -- nothing enters it, and
if something ever does, the read-back path it ratifies into is **ungated**:
`write_canon` writes `category="other"` rows, `knowledge_for_character` gates
only `category="knowledge"`, `search_lore` has no observer parameter, and the
audience known at mint time is discarded, so a future per-mind gate cannot be
built on the read side without re-plumbing provenance through
`canon_provenance` (currently written and never read by anything epistemic).

For whoever builds the lane's first real producer (the generated-gossip plan):
land the producer and the read-side gate in the same change, or the first
claim ever ratified becomes knowledge every mind in the chat reads back
without having been in the room for it. And re-measure the fire rate after --
a lane that has never fired gives `no chances`, not 0%, and the first nonzero
denominator is the first evidence the mechanism exists.

### 1.31 The Director cannot name what the player is carrying

`agents/director._carried_reports_view` walks `active_cast` and reads `cstate`.
The player's held reports live in `carriers.PERSONA_STATE_KEY` (a persona has
no `chat_chars` row), so they are invisible to the one stage that has to name a
`world_event_id` in a `courier_ops` or telling op.

The mechanism underneath works — a scratch drive shows the player acquiring a
surface, paying a rider, and the claim arriving two retellings fainter. But in
a real story the Director is asked to encode "I send word east about the thing
I just watched" while holding an empty list, so it has nothing to name. The
carrier half landed in `7b81e8a`; this is what stops it reaching production.

Roughly five lines: route that view through `carriers._carriers` rather than
`active_cast`. Its own docstring already records this exact defect — an id the
Director was never shown — having been fixed there once before, which is the
argument for fixing the enumeration rather than the symptom.

### 1.32 A region assertion has an owner only by slot position

`spatial.owned_region` now makes a region UNAMBIGUOUS: `(who, where)`, so no
comparison can collapse one body's mouth into another's. It cannot make an
assertion TRUE. A slot's position is what names its owner, so a mis-slotted
`{target: Hinami, target_part: glans}` still yields a well-formed token.

A check derived from the scene's own history was built and measured against
every stored beat, each turn judged against its own pre-beat checkpoint:

    contacts     70 fires / 2,036 assertions
    substances    2 fires /    30 assertions
    true positives: 1

The false positives are ordinary anatomy — hand, waist, chest, mouth, lips —
whose first mention in a story happened to be the other body, and the rule
deadlocks: a common region asserted first on body A can never afterwards be
asserted on body B, because every attempt is cleared before it can become
evidence. It is also self-poisoning. Turn 62 of the reference story flags
`glans` on the wrong body (the true positive); turn 64 flags it on the RIGHT
body, because turn 62's own error had by then become the scene's belief. One
wrong assertion inverts the check for everything after — the exact failure
mode the investigation started from. Removed in `a851ea0`, numbers recorded in
place.

**Direction: the owner must be ASSERTED, not derived.** An owner qualifier on
the region slot, so the Director says whose mouth it is rather than the engine
inferring it. Schema plus prompt. This is what would actually close turn 62,
and it is the only route left that does not require an anatomy model.

### 1.33 An interpret that says nothing costs two model calls

Measured on a 51-beat authored playthrough: 42 of 50 final interprets carried
a degenerate sequence element — `attempt: "waits"`, `observable: "waits"`,
empty `verb`, no targets, no effects — for inputs as plain as *"I draw the
sword."* `interpret_repair` fired 25/50, reported `repaired=True` 25/25, and
left `unresolved` 25/25: its output was a byte-identical `waits` element,
because the repair sets `repaired` merely on the list being non-empty. The
deterministic re-check then still failed, which forced `mapping_stage` on all
25 (correlation exactly 1:1 with the clean turns running `mapping_quick`).

So half those turns paid two sequential model calls that produced nothing, and
— the part that is not about latency — **the player's declared act was dropped
from causality on those beats.**

Config-specific: across 1,886 interprets in the live corpus the repair fires
11.8% overall, 6.0% over the last 100 turns, and genuinely changes output
54–71% of the time. `"waits"` appears nowhere in engine source, so it is
model-emitted, plausibly `llm_quality`'s repair minimally satisfying the schema
after a primary call returned `{}`.

Two additive fixes, neither removing a stage: treat a sequence whose only
element has an empty `verb` and no targets or effects as a validation failure,
so the existing same-call repair fixes it before `_reconcile_interpretation`
runs; and make `recon["repaired"]` require the re-check to actually pass, so
the metric stops reporting 100% success on a 0% success rate.

### 1.35 `memories_fts` is dead, and has been for some time

9,545 rows in the live database and **zero readers anywhere in the repo** —
`grep memories_fts` outside the schema, trigger and migration statements
returns nothing. `memory_retrieval_fts`, at 10,696 rows, is the one retrieval
actually uses.

Worse than unused: its triggers live in a MIGRATION, and `init()` skips every
migration for a fresh database. So any Sonder database created since that
change has the table, no triggers, and nothing in it — and nothing has ever
noticed, in either direction. It is carried through export, import and every
schema check.

Found while extracting the memory model into Nullo Engine, which dropped it on
this measurement rather than porting it. Removal here needs a migration and
should confirm the rowcount is not load-bearing for anything outside the repo
first.

### 1.36 The suite's database redirect runs after collection

`tests/conftest.py::_never_the_real_database` is a session-scoped autouse
fixture, and fixtures run *after* collection. A test module that touches `db`
at IMPORT time — a module-level query, or a constant computed from one — still
reaches `engine.db` before the redirect is in force.

Latent rather than firing: no current test module appears to do it. But the
fixture exists because three prompt-cache tests once passed or failed on
whether a checkbox was ticked in the live database, and the hole it was written
to close is not fully closed. The next module-level query reopens it silently.

Nullo Engine closed the equivalent by setting its database env var at conftest
**import**, which pytest guarantees precedes every test module, and pinning it
with a test that asserts the redirect is in force. The same fix applies here.


### 1.37 The aversive half of the stress model has never run

`psychology_runtime.resolve_stress` reads `threat` off
`appraisal["goal_impacts"]` and weights it **0.55** — more than every other
aversive term combined. Its only production caller (`commit.py`, the
`new_stress = psychology_runtime.resolve_stress(...)` site) passes
`affect.appraise`'s **return value**, which is exactly:

    ['dA', 'dV', 'dominant', 'drive_impact', 'emotions']

There is no `goal_impacts` key in it and there never has been. `.get()` returns
`[]`, so **`threat` has always been 0.0.**

The corpus signature is unmistakable — 78 banks, 27 with a resolved stress
block:

    strain      min 0.0197   median 0.0454   max 0.3608
    load        min 0.0000   median 0.0041   max 0.5949
    activation  min 0.0680   median 0.5222   max 0.7984
    overloaded fired                          0 of 27

Strain never reaches half its own threshold, `overloaded` has never once
fired, and the activation median is almost entirely the non-aversive DRIVE
term — which is the half that does work. Characters can be excited. They
cannot be threatened.

The fix is to pass the impacts, not the appraisal: the caller has
`goal_impacts` in hand at that line. Take the parameter separately rather than
reaching into a dict, so there is no shape a caller can pass that silently
omits it — Nullo's port did that and it is the fold-on-the-way-in answer
rather than a guard someone must remember.

**Not fixed here, and it wants a decision.** The one-line version changes the
emotional trajectory of every existing character in the corpus: bodies that
have never felt threat would start accruing strain and crossing thresholds
that have never been crossed. That is a behavioural change to a live product,
not a silent correction, and the fire-rate row to watch afterwards is
`overloaded` moving off zero.

Found while porting the module into Nullo Engine, by an agent reading each
function's arguments after having first dismissed all three by their module
name.

### 1.38 A line addressed by epithet is addressed to nobody

`director_resolve` writes `intended_target` on every dialogue entry, and both
readers of it — `composer._addresses` and `perception._addresses` — match it
against the observer's canonical NAME by casefolded equality. Measured live
(three-model playthrough, 2026-08-12, `mix2.db` turn 1): both of Bryn's lines
carried `"intended_target": "young smith's apprentice"` — the appearance label
perception mints for strangers — where the target was the player, Corin. Every
equality test failed.

Two things ride that answer, and they are not the same kind of thing:

- `directed_at_self` on the speech percept — presentation and salience;
- `line_hear_level`'s **addressed rescue**, which is an ADMISSION decision: a
  quiet line plainly naming you is audible to you when it would otherwise not
  be. So a whisper aimed at the player by epithet is silently not delivered.

The obvious fix — also match `intended_target` against the epithets
`common.self_reference_forms` mints for that observer — is not taken here on
purpose. It LOOSENS an admission gate on a string match, and this engine's
guards subtract; a false positive delivers a line to someone it was not aimed
at. `design_notes/20-observer-epithet-floor.md` closed the prose half of this
defect deterministically and reports the structured half back through
`tell_director` (`director._report_observer_epithets`) so the Director stops
producing it. Before closing the gate, measure how often `intended_target`
fails to match any body at all across the stored corpus — if the Director
stops writing epithets once it is told, the gate never needs touching.

### 1.39 Micro-perception deliveries bypass the composer's identity floor

Pre-existing, and now visible beside §1.38.
`loops.deterministic_micro_perception` composes each delivered sentence with
`_observable_predicate(display, surface)` and applies **no** self-reference
rewrite at all — not the epithet floor added in note 20, and not the older
name-based `_self_second_person` every other delivery site runs. So a
character whose own name or minted epithet appears in another actor's
`observable` surface reads about themselves in the third person in their own
micro-view, and that text flows verbatim into their next character step and
their memory of the beat. (The player is unaffected: `_composer_outcome` skips
the `player` key when merging `micro_by_pid`.)

These additions also arrive at `_composer_outcome` **pre-rendered** and are
appended after the composed view, so they carry none of the percept-level
gates either — the residual already noted in
`design_notes/13-composer-build.md` ("the micro loop should emit percepts").
One fix covers both: emit percepts.


### 1.40 The slow turn was model-call multiplicity, and the harness plays too few beats to see it

Measured 2026-08-12, on chat 71 turn 10 (played live 07:01:32–07:05:09,
216s from `interaction_loop` to `commit` against harness predictions of
roughly a third of that). Diagnosed from the persisted `steps`/`variants`
timestamps, the turn's own stored stage outputs, and an offline reproduction
against a copy of the database — not from the harness. Three findings, one
per anomalous stage, and none of them is corpus size:

- **`commit` 45.8s (harness 4–8s): ~29.5s of it is the first
  autobiographical consolidation, reproduced and timed.** Turn 10 is the
  first beat where `memory.maybe_consolidate_character_memory` fires
  (`current_turn_idx - last_turn >= 10` with `last_turn=0`), and
  `_write_consolidated_window` runs on the **`utility`** role — which is
  configured nowhere and is not in `providers.ROLE_FALLBACKS`, so it falls
  through to `default` (NanoGPT `zai-org/glm-latest`). Reproduction against
  a copy of the live database, real providers: consolidation of the
  34-memory window took **29.47s, 27.38s of it the one LLM call**
  (`llm_call role=utility … duration=27.38s`). The rest of the commit window
  is a handful of paced embedding calls (measured: 2.69s for a 4-text batch
  that ate one 429 penalty; 0.93s single) plus sub-second deterministic
  work. Mapping was `{"skipped": "nothing new to commit"}` — no mapping LLM
  call, no lore embeddings, so the chat's lore volume (7 entries) and the
  2,152-entry database total are both irrelevant. The consolidation runs
  synchronously inside the commit stage's wall clock even though it is
  post-transaction and reconstructible; every other post-transaction spend
  (offscreen ticks, artifact wording, promotion) already went out-of-band.
- **`director_resolve` 105.5s (harness 22–50s): the 8.2 code, not a stale
  build.** The stored resolve output carries `orchestration.prose_scope`
  (granted/gated_out), which exists only at `ab3daad` — `40755ee` has no
  `_prose_author_scope` — so the 06:58 process was running the merged 8.2
  tree (merge landed 06:51:40) and the delegation-leak/lean-core fixes
  explain **none** of the gap. What the record shows instead: an intimate,
  physically busy beat dispatched **5 of 6 specialists** (`"ran": true` for
  body, social, contact, objects, spatial), the reconciliation self-repair
  fired an extra sequential core call (`"repaired": true`) — and it bought
  nothing (`state_diff still does not encode it after self-repair` warnings,
  `channels_replaced: []` on every specialist). The harness's 22–50s band
  was earned on beats with narrow dispatch and no repair pass.
- **`narrator` 29.5s (harness 6–15s): payload is windowed (LIMIT 4 prose
  turns, scene-scoped fields — nothing O(corpus)); the multiplier is the
  bounded rewrite ladder** (`_generate_narration` fidelity-correction and
  craft passes: up to 3 calls). Inference from code structure, not
  measurement — the live per-call log lines died with the process, before the
  per-call ledger landed.

**Nothing on the turn path scales with corpus.** Measured on the 2.1 GB
copy: a full-corpus `memories_fts` MATCH is 2.3ms, the chat-scoped vector
fetch 0.5ms; the resolve/narrator payloads are scene-scoped and windowed;
mapping skips when nothing is staged. The 2.1 GB database and the DB-wide
lore/memory totals are red herrings for turn latency.

**Why the harness is blind, and what answers it.** A fresh run of ≤10 turns
(idx 0–9) can never reach the consolidation cadence, rarely trips wide
specialist dispatch or a repair/rewrite retry, and, at the time this was
measured, nothing on the live path persisted how long a stage took, so a slow
live turn left only stage-total timestamps behind. `tools/stability_run.py` exists for
exactly this: it drives real turns against the longest stories on a copy
and parses per-role `llm_call` durations. Run it against long chats either
side of any latency-relevant change.

**What landed against this (2026-08-12):**

- **Consolidation is out-of-band** (`commit.schedule_memory_consolidation` →
  `jobs.py`, beside the offscreen ticks): deduped per chat, abandonable
  between characters, silent-per-character on failure, cancelled
  cooperatively by `restore_checkpoint`. The ~29.5s leaves the commit
  stage's wall clock entirely. `tests/test_consolidation_out_of_band.py`.
- **`utility` inherits `mapping`** in `providers.ROLE_FALLBACKS` before
  falling to `default` — the settings guidance has always paired
  "mapping/utility" as the cheap mechanical lane, so an unset utility now
  lands on the fast model the host already picked instead of their most
  expensive one. The settings-panel role notes say so.
  **Reverted 2026-08-13** (`providers.ROLE_FALLBACKS` is now empty; every
  unset role follows `default`). It fixed the cost by means of an
  inheritance no host could see, and the same mechanism was lying to hosts
  on the six Director specialists. The defect this bullet was answering —
  the call sitting inside the commit window — is fixed by the out-of-band
  scheduling above and stays fixed; an unset `utility` on a slow default
  now costs money and background time, not the player's wall clock. If a
  background lane returns to the turn's critical path it needs its own role
  **set**, not a fallback re-added under it.
- **Reconciliation repair goes to the CHANNEL'S OWNER on the orchestrated
  path** (`agents/director.py` `_route_repair_omissions` /
  `_specialist_repairs`): an omission in a delegated channel is re-asked of
  its owning specialist — one scoped ~1s call, same beat view, same
  entitlement slice, additive merge — and only player claims and
  undelegated categories still buy the full-core `resolve_repair` call.
  Detection unchanged; monolithic path byte-identical. Found and fixed
  beside it: `_CATEGORY_CHANNELS` was keyed on raw category spellings while
  every reader looks up `_normalize_omission_category` output, so contact/
  substance/pose manifest entries could never reach the scope backstop; and
  a repair delta's `stations` were silently dropped by
  `_merge_repair_into_diff`.
- **The per-call ledger** — `_engine_notes.llm_calls` on each saved variant,
  `{step_key, role, requested, served, in, out, cached, duration, kind}` per
  call, offered by `providers._log_usage` and attributed by contextvar so the
  specialist fan-out and the parallel groups land on the right step — is what
  turns the narrator question below from an inference into a lookup.

**Correction (2026-08-12, live variants v26625/v26634/v26643, turn 2354):
the "empty specialists" reading of these rerolls was wrong.** Two separate
investigations read `channels_replaced: []` as "the specialists assembled
nothing" — but that field counts AUTHOR content that lost to ownership, and
a compliant lean author leaves delegated channels empty, so `[]` is the
healthy state. The merged diffs on all three rerolls carry the specialists'
encodings (`attire.Hinami.remove` the jacket, `contact_ops`
remove(stomach)+add(waist), the entity shed, an inventory drop, a station);
a granted channel's post-assembly content can only be the specialist's,
because assembly assigns `container[key] = owned` unconditionally. What
actually broke was the deterministic EVIDENCE CHECKER
(`_evidence_present`): each class gated on the manifest's free-text
`subject` naming one particular kind of thing (the wearer for attire, a
participant for contacts, a `positions` key for a placement) while the
model words subjects freely ("lightweight travel jacket", "contact_end",
"prior hand-to-stomach contact") — so coverage flickered reroll to reroll
with the wording, 5 of 11 live manifest items read as omissions against
diffs that encoded them, the Tier-2 repair fired on the false positives,
answered "already_encoded", lost that verdict to an exact-subject
disposition match, and false "objective state may be stale" warnings
shipped. Fixed: attire also checks garment handles inside wearer entries;
structured manifest endpoints bypass the contacts subject gate (they ARE
the subject); a `cross` op covers its ended endpoint via
`crossed_target_part`; a within-room drop filed under `positions` is
covered by its station; disposition matching carries the same substring
tolerance as every other subject comparison in the seam; and each
specialist's dispatch record now carries `channels_filled` so the next
investigation can see assembly working. Replayed against the live diffs:
9/11 covered (was 6/11) — the two residuals are genuine part-noun
disagreements between the model's own manifest and its encoding
(waist/hip, fingers/hand), correctly detected and deliberately not folded
by a synonym table (`_same_appendage` is structural by design).
`tests/test_resolve_reconciliation.py` (live-shape fixtures),
`tests/test_director_orchestration.py`
(`test_a_specialist_encoded_beat_buys_no_repair_and_no_warning`).

**Residuals, recorded:**

- **`narrator` 29.5s remains an inference** (the fidelity/craft rewrite
  ladder, up to 3 calls). The ledger now stamps every narrator call on the
  stored variant, so the next slow narrator beat answers this directly —
  including whether the orchestrated path makes a rewrite MORE likely,
  which nothing in `_generate_narration` reads orchestration state to
  suggest, but which only the ledger on a real beat can rule out.
- **A restore racing a mid-flight consolidation call**: the cancel in
  `restore_checkpoint` is cooperative (between characters), so a restore
  arriving while one character's consolidation LLM call is in flight can
  still land a summary computed from pre-restore rows, and the cursor on
  that summary row then skips the window. Seconds-wide, needs a reroll to
  coincide with the ~10-turn cadence, and the summary layer is
  reconstructible (`backfill_memory_summary_windows` can rebuild) — but it
  is a window the synchronous design did not have, recorded rather than
  closed.


### 1.41 Surface-affect habituation ships default-off; flipping it is a decision this entry exists to force

The saturation defect is measured and the fix is landed and validated
offline (`affect_habituation`, CHANGELOG Unreleased; replay evidence in
`tools/affect_replay.py` against chat 71's checkpoints), but the setting
defaults to the shipped behaviour, so **every live story still has the
defect until somebody flips it**: a surface at the ceiling stays there, and
a climax cannot out-score its own build-up. What the flip should wait for is
one live story played with it on and read for feel — the replay proves the
trajectory shape (plateau ~0.83, releases 0.92–0.94 on chat 71; sub-0.80
conduct moving a mean 0.012), but felt tone in prose is the thing no
counter measures. Two calibration facts for whoever tunes it next: the
compression must stay top-slice (a uniform gain strong enough to help chat
71 cost the warm long story chat 38 a story-wide ~0.1 valence shift —
medicine landing on health), and accumulation must read the STIMULUS (the
uncompressed target), not the body's own dampened surface, which stalls at
a feedback fixed point (measured: s froze at 0.40 exactly). Residuals
accepted knowingly: a spike that arrives mid-plateau on the same axis is
compressed like the plateau (only the hedonic release pierces — shock fires
chronically there and model novelty is noise); and a fast build that pins
within ~6 beats starts paying before its plateau formally begins. Both are
visible in the replay table; neither has a decidable discriminator in
stored data today.

Also recorded here from the same investigation, judged fine as they stand:
Elyra's climax minting no `awareness` condition while Hinami's did is the
Director describing two different bodies (one collapsed, one did not), and
the moment's structural carriage for Elyra exists regardless — her hedonic
charge hit 1.0, `released` fired, and the charge zeroed next beat, which is
the drive-feed loop working; a `drive_shift` there would have been WRONG
(a peak inside one's own drive confirms it — the hard drive lesson is about
strain never moving a drive, not success moving it).

### 1.43 Recognition under a disguise is a boolean where the question is graded

**Found:** the disguise floors (2026-08-15). Design in
[`design/DESIGN_DISGUISE_AND_RECOGNITION.md`](design/DESIGN_DISGUISE_AND_RECOGNITION.md) §5.

`conceals_identity` now separates a disguise that covers what a body is
recognised BY from one that covers something else, which was the collapse
worth fixing first. Three things it still cannot express:

1. **Coverage vs familiarity.** A stranger and a spouse are not equally fooled
   by the same hood. The comparison wants what the disguise covers against
   what *this* observer knows the subject by, and there is currently only one
   answer for everybody.
2. **Circumstantial defeat.** A hood blows back; an illusion falters; someone
   takes hold of the concealed feature. `contact` and `spatial` both hold
   facts bearing on this and neither is consulted.
3. **Witnessing grants knowledge** — watching a disguise go on or come off
   should add the witness to `known_to` with nobody declaring it. **This is
   the highest-value item of the three and is purely deterministic**:
   perception already knows exactly who received the beat.

Deliberately NOT a seventh Director specialist: recognition is a per-observer
question and the Director emits one diff for everybody, so a specialist could
only ever produce the single room-wide verdict `known_to` already is. Every
other per-observer perceptual question here (`hear_level`,
`region_visibility`, `visual_level_between`, scent, containment, darkness) is
a deterministic ladder over typed data, and perception calls no model at all.

### 1.44 A concealed feature can leak through an attire description

**Found:** the same investigation, by reading a live wardrobe rather than by a
failure — it has not fired yet.

A garment's authored `description` is free prose and is delivered through
`observer_body_regions`, which gates by region visibility and knows nothing
about disguises. A live hair clip is described as *"pinned into her
copper-gold hair near the left fox ear"* while a `physical_disguise` on that
body lists `fox ears` in `concealed_terms`. The moment that region renders to
an unaware observer, the disguise is undone by an accessory.

`disguised_visible_appearance` scrubs the body summary and
`conceal_disguised_parts` drops authored parts; the attire ledger is the third
surface a body is described through and nothing scrubs it. The fix is the
existing rule applied to one more surface — a garment description reaching an
observer who is not in `known_to` should have concealed terms removed, and a
description that is *only* the concealed feature should fall back to the
garment name.

### 1.42 The story column's clearance for the ambience cluster cannot be honoured

**Found:** rebuilding the `lcars` theme (2026-08-14), by an automated geometry
check rather than by eye — the overlap is small enough to read as a design
choice.

`settings.js:syncVitalsGutterNow` computes a `reserve` explicitly meant to keep
the centred story column clear of the two things floating over it: the
condition tracker on the left, the ambience cluster on the right. For the
cluster it reserves `ambWidth + 20`. Then:

```js
const storyWidth = Math.round(Math.min(
  STORY_MAX_WIDTH,                                       // 1080
  Math.max(STORY_MIN_WIDTH, shellWidth - reserve * 2),   // 720 floor
));
```

**The 720px floor silently outranks the reserve.** When the shell is narrower
than `720 + 2 * (ambWidth + 20)`, the column keeps its 720 and the clearance is
simply not taken. At a 1440px window with the stock 286px sidebar the shell is
1154 and the cluster measures 212, so the requirement is 1184 — 30px short. The
send button therefore ends 7px past the cluster's left edge and sits under the
mute control.

`[measured]` at 1440x900, one browser: `send right 1223 | ambience left 1216 |
gap -7px`. Identical in `sonder`, `tavern`, `stone`, `ink` and `lcars`, because
the arithmetic is shared — this is not a themed defect. It worsens in either
direction the layout can move: a theme that widens the sidebar takes it
straight off the shell (a 24px spine took the gap to -19px, which is how it was
found), and the cluster grows again whenever a track is playing.

Two honest resolutions, neither taken here because both change shared layout
and this was found inside a theme change:

1. **Let the column shrink.** Lower `STORY_MIN_WIDTH` when the alternative is
   an overlap. Costs reading measure at narrow widths, which is exactly what
   the floor was defending.
2. **Un-float the cluster earlier.** `styles.css` already un-floats it at
   `@container composer (max-width:900px)`; the threshold should be the
   computed `720 + 2 * (ambWidth + 20)` rather than a guessed 900. This is the
   better fix — it preserves the measure and gives up only the float, which is
   the cheaper of the two things.

Related and already landed: a `ResizeObserver` on `#ambience-bar`
(`settings.js`), because the cluster is absolutely positioned and so cannot
report its own growth by resizing `#composer` — the reserve was *additionally*
going stale whenever the bar changed width after first paint. That fixes the
staleness. It does not fix the floor, which is this entry.


### 1.45 `_inject_visible_actor` is imported everywhere and called nowhere

`agents/common._inject_visible_actor` has **zero production call sites**. Its
three siblings in the same file are all wired (`_inject_dialogue` 3,
`_compose_residue_view` 2, `_inject_action` 1); this one is imported by
`agents/perception.py` and re-exported from `agents/__init__.py`, and only
`tests/test_perception_appearance.py` and `tests/test_perception_identity_gate.py`
ever call it. So it has passing tests and no effect, which is the worst
combination available: it reads as a live floor.

Both of its jobs appear to be superseded by the composer IR rather than
missing. The appearance half is done by `composer.appearance_percept` →
`"You see {desc}."`, which carries the same `_appearance_as_prose` output
including the `wearing:` clause. The contradiction-stripping half looks for
phrases ("no clear figure visible", "cannot see them") that do not occur:
**0 of 5,499 stored views across the corpus contain any of them**, because the
model-authored perception path that produced them is gone.

So the likely correct change is deletion, of the helper and of the two tests
that keep it looking alive. It is filed rather than done because it is a
judgement about design intent — whether this was meant to be a deterministic
floor that was never wired — and because `agents/__init__.py` is a
compatibility facade that replay may depend on.

Corrected while finding it: an earlier note in this session's handoff claimed
the attire string never reaches perception at all. It does. It is emitted on
FIRST MENTION and again when a structural change re-earns it (`force=True` on
`appearance_percept`, gated by the render ledger), which is why sampling a run
of turns with neither shows nothing. Measured live, chat 76 turn 60, in a
player observation: `"...wearing charcoal pinstripe suit, light blue dress
shirt, ..."`. Not a defect — the suppression of per-beat repetition is the
design.


### 1.46 A transformation's parts are repaired on read, never at the source

`scene.normalize_transformed_parts` coerces a `physical_transformation`'s
`parts` onto `attire.REGIONS` and `EXTRA_PART_ASPECTS` and salvages the
off-menu text into `description`, on the `rederive_entry` precedent — so
stored conditions heal lazily and the malformed phrase ("emerge from the
fluffy, pointed, golden of the top of the head") stopped reaching anyone.

**The body specialist still writes the free text.** Its contract was not
changed, so every new transformation mints the same shape and is repaired
downstream on every read. `character_schema._normalize_extra_parts` shows what
the closed menus look like at the authoring surface; the specialist prompt
should say the same thing, and then the read-path repair becomes a floor
rather than a working part.

### 1.47 `contract_bench`'s specialist payloads are the flaw the shootout exists to document

`tools/director_shootout.py` was written because `contract_bench` sent a
927-character payload and reported a model at 3.95s that took 47.4s in a live
turn — the bench was sending about 4,400 system tokens against a real
director's 27,000, and mis-ranked the most expensive role in the pipeline.

The six specialist payloads added in alpha 8.4.4 are synthetic two-character
scenes and have exactly that flaw at smaller magnitude. They make the
specialists benchable at all, which they were not; they should be rebuilt from
a real chat the way `director_shootout` builds its own before anyone ranks a
model for a tiering decision on them.


### 1.48 Language packs: what is not finished

The pack machinery is built and English is byte-identical to before the
extraction. What is unfinished is the one non-English pack and the surfaces
the language layer does not own.

**Japanese has never been reviewed by a native speaker.** `language_packs/ja`
ships `translation_status: model-draft`, `version: 0.2.0-beta`. It has been
checked for structural integrity — every canonical protocol span survives
translation, every regex compiles, capture-group counts match English, no
mask markers leaked — and none of that is a judgement about whether the
Japanese reads naturally, whether a cue is too broad, or whether the register
is right for fiction. Until it is read by someone who speaks it, treat
`story: true` for `ja` as a claim about coverage, not about quality.

**Story content authored outside the language layer stays English.** Layer B
renders admitted percepts through the pack, but several producers build reader-
facing clauses themselves and hand them over as data:

- `spatial.py` contact and substance clauses (`contact_sensation`,
  `substance_event_clause`) — these reach the view AND the memory episode, so
  they are written permanently into a non-English character's memory bank;
- `scene.appearance_of`'s glue (`"; wearing: "`, `"; clothing state: "`), whose
  separators are also parsed back by `attire.py` and `agents/perception.py`,
  so translating them breaks the readers unless all three move together;
- `attire.py`'s ledger phrases (`"bare at the %s"`), which are persisted and
  served raw to the attire panel — a later translation does not repair stories
  already written;
- `paradox.py`'s `_HAZARD_WOUND_NOTE`, appended to room notes;
- the first-person memory episodes minted in `commit.py` and `offscreen.py`
  (`"I said …"`, `"I tried to …"`, the drive-rupture memory).

The fix is not to translate the strings where they sit: each is either
literal-coupled to a parser or persisted, so the real work is moving the
clause construction behind the compositor card and migrating what is stored.
Sized as its own change, not a follow-up patch.

**Japanese still has open items from its first native review.** The review
(the pack's first) fixed the sentence architecture, but three things were
identified and not done:

- **Co-presence is not grouped.** English merges several present bodies into
  one sentence and counts indistinct figures (`_render_presence_group`); the
  Japanese adapter renders one sentence per body, so four people in a room
  give four clauses of identical shape, each ending 「…にいる。」 The pack's
  `dim_figures`, `count_words` and `join` are authored for this and unused.
  Worse in Japanese than English, because the sentence-final morphology
  repeats too.
- **Two dialogue renderers still coexist and disagree.** `agents/common.py`'s
  `_inject_dialogue` and `language_adapters/japanese.py`'s `_speech` both
  render speech; they now agree on articulation and tone, but they are two
  implementations of one contract and should be one.
- **`_tone_clause` picks its frame by English morphology** (noun-suffix and
  article tests) even for Japanese input. It is harmless today only because
  all three Japanese tone templates are the same string; editing one will
  surprise whoever does it. The durable fix is the prompt contract's new
  requirement that `tone` be a 体言, plus a single frame.

**"句点 inside 「」" is not normalised.** Standard Japanese practice omits the
closing 句点 inside quotation marks; the engine emits whatever the model wrote.

**RTL is accepted and unimplemented.** `manifest.direction: "rtl"` validates,
reaches `document.documentElement.dir`, and nothing else: there are no
`[dir=...]` rules in `static/`, and the stylesheets use physical `left`/`right`
properties throughout. Both shipped packs are `ltr`, so no RTL pack has ever
been rendered. A pack declaring `rtl` today gets a mirrored text direction over
an unmirrored layout.

**The UI catalog scanner is deliberately broad.** `tools/extract_ui_catalog.py`
harvests string literals, so roughly 4% of the 2006 English messages are code
fragments, selectors and markup that never render. They are carried as
`translation_exceptions.json` entries rather than filtered, which keeps the
parity check honest but hands translators strings they must not touch.

**Provenance is not recorded per story.** A chat stores `story_language` and
nothing else — not the pack version, adapter, or translation status it was
played under. A story played across a pack upgrade has beats produced under
different linguistic rules with nothing on disk saying so. Judged acceptable
while old pack versions are not retained, but a `story_language_pack_version`
stamp would at least make a behaviour change explicable afterwards.


## 2. Roadmap

Features the architecture intends and has not built. Ordered by value per unit
of risk; items 2.2–2.3 repay the structural debt in
[`../Design.md`](../Design.md) § Structural debt.

### 2.2 Make stance auditable

**Closes debt #2.** Move relationships out of the `world` KV blob into a
`relationship_events` table: one row per delta, with target, axis, magnitude,
trigger event id and turn. Keep the current graph as a derived projection,
exactly as `world_entities` is derived from the scene. Then make
`trigger_event_ids` mandatory and tighten the clamp toward the specified ±0.05.

Today `apply_relationship_updates` accepts `trigger_event_ids` but treats them as
optional, with explicit handling for "a routine trigger-less delta"; there is no
change log, only the current value plus a `salient_event` string. There is no way
to answer "why does she distrust him?" from the record. The founding design
specifies ~0.05 per ordinary interaction; the schema clamps at ±0.2.

Verified absent: no `relationship_events` table exists.

### 2.3 Teach the heuristic import to read `description`

**Closes debt #3.** No LLM required: fall back to `description` for
`self_model.summary` and voice notes when `personality` is empty, and warn
specifically when a heuristic import lands below a populated-field threshold.

The heuristic path derives psychology from the card's `personality` field, so a
v2 card that puts everything in `description` — common — yields a sparse first
pass. The opt-in v3 gap-filler mitigates sparse old cards but does not remove the
value of a better deterministic first pass.
`importers.character_import_warnings` exists but fires only on the import path.

### 2.4 Hard mode — enforce `PlayerAuthorityMode`

The most interesting item on the list: it is the one that lets the engine's
original thesis be played *as written* without taking the dial away from anyone
who prefers otherwise.

`schemas.PlayerAuthorityMode` exists as an enum and is **consumed nowhere** —
verified, one site in the whole tree. Wire it: per-chat setting, adjudication of
assertions in `director_interpret`, and a refusal path.

| Mode | The player controls |
|---|---|
| `actor_only` | The protagonist's attempts, speech, and immediate bodily conduct. Assertions become *claims* the director adjudicates and may refuse |
| `explicit_outcomes` | The above, plus declared completed effects on the protagonist's own actions |
| `world_author` | The above, plus external events, entities, time, and world assertions (**today's behaviour**) |

Two design notes to settle before building:

1. **A refused assertion must not silently vanish.** The player wrote it for a
   reason. The honest behaviours are to translate it into an attempt ("you reach
   for the key") or to surface the refusal explicitly. Silently dropping player
   text is the one thing the engine's authority contract has never done, and hard
   mode must not become the exception.
2. **Mode is per-chat, not global**, and a mid-story change should be recorded,
   since it changes what earlier turns meant.

### 2.5 Complete automatic canon lock

Age-based locking is built (`commit.py` locks chat-canon entries older than 20
turns; locked entries reject in-place mapping updates). Add the remaining
specified rule so facts **referenced multiple times** lock before the age
threshold. Verified absent: no reference counter on `lore_entries`.

Cheap, and it is what stops long-run lore drift.

### 2.6 Scene-boundary coherence pass

Established-earlier wins unless the later fact is load-bearing for an active
thread, in which case the older is retconned *with a logged entry*. The logging
is the point: a silent retcon is the failure mode. Verified absent.

### 2.7 Reactivation negotiation

The largest unbuilt subsystem, and the one that makes a large cast feel alive
rather than merely stored. Argument:
[`OFFSCREEN_LIFE_DESIGN.md`](design/OFFSCREEN_LIFE_DESIGN.md).

It decomposes: gap-history plus delta-summary is the valuable 80% and is the same
generator as §2.8; the negotiation protocol is the hard, novel half and can trail
behind it. Mapping proposes the gap; the character may refuse on integrity
grounds only; refusals are capped and tagged (identity-violation counts half,
preference counts full); on exhaustion the last proposal becomes canon.
*Conservative defaults, costly exceptions.*

Build order, first three landed (bg-life work, 2026-08):

1. ~~**The gap generator**~~ — landed as `gaps.gap_for` plus the
   `subject_last_seen` ledger and the `agents/character.py` reader
   (`while_you_were_offscreen`). Subject-agnostic; ids via
   `subjects.resolve_subject`.
2. **Wire `BehaviorController` per character — superseded in part.** The
   chat-level ceiling landed in alpha 6.9; the per-character half landed as an
   IMPORTANCE override (`simulation.offscreen_importance` on the sheet, read by
   `offscreen.importance_for`) rather than a per-character rung, deliberately:
   the ladder answers what a character MAY do, importance answers how much they
   matter, and one vocabulary answering both questions is the `flow.reactors`
   defect re-minted. A per-character RUNG opt-in remains the right shape for
   step 4's villain ticks and is still open.
3. ~~**`stochastic` at scene boundaries.**~~ — landed as
   `offscreen.stochastic_ticks`: a real seeded draw against standing
   intentions, no model call, written through `offscreen.append_offscreen_log`.
4. ~~**Typed `reactive` plan stages.**~~ Grounded same-beat declarations,
   frame-scoped stages, typed time/event triggers, and pre-adjudicated effects
   now execute without a model call.
5. ~~**`character_agent` ticks** — villain, count cap, knowledge firewall.~~ — landed as `offscreen.schedule_agent_ticks`: one
   reduced Director-adjudicated turn per opted-in candidate on the
   world epoch, capped by `max_offscreen_actors`, contexted only by
   the fail-closed `agent_context`, landing atomically under
   epoch/base-turn/per-subject guards.
6. **Reactivation proposal.**
7. **Negotiation** — refusal budgets, tagging, stalemate-eats-canon.

Precedent that did not exist when the note was written: `background_claims.py`
is exactly the "commit invention as claims, not facts" mechanism its decision 3
asks for, built for background presences.

### 2.8 Richer off-screen life

Deterministic scheduling exists; what is missing is the world visibly having
moved while you were away. Most of the cast needs no tick at all — the gap is
generated at re-contact, so cost stays `O(re-contact)`. The exception is the
character advancing a plan whose consequences the player meets *before* meeting
them: you cannot lose a race that was never run.

**Step 2 of `OFFSCREEN_LIFE_DESIGN.md`'s build order landed in alpha 6.9.**
`BehaviorController`'s ladder is now the `offscreen_life` setting on
`dialogue_config` — a chat-level ceiling, settable in the NPC dialogue panel,
gated twice (the dormant cast is withheld from the mapping payload below
`stochastic`, and the commit-side write is gated again). `max_offscreen_actors`
bounds it. Two corrections that fell out of wiring it:

- The engine was **already running an ungated off-screen simulation**. The
  mapping-commit prompt asked for ticks on every scene change and commit logged
  whatever came back, with no dial, no bound, and no reader.
- `MappingCommitOut.offscreen_events` is typed `list[dict]` with no inner
  model, and the model duly invented a shape per call: `{actor, tick}`,
  `{event}`, `{who, event}` and `{description}` all appear in the same field
  across eight live chats. `commit.normalize_offscreen_events` now coerces
  them to `{actor, tick}` on the way in. The stored history is still mixed —
  nothing reads it yet, so nothing has had to care.

Landed since (bg-life work, 2026-08): `offscreen_log` has a reader —
`gaps._skeleton` windows it into every gap and `gaps.interim_for` delivers it
at re-contact as `while_you_were_offscreen`. The `stochastic` rung is now the
specified one — a seeded, replayable, model-free draw
(`offscreen.stochastic_ticks`); the model is no longer asked for ticks at any
level and a volunteered `offscreen_events` is refused on the write path.
Resolution above the free rung is importance × distance
(`offscreen.resolution_for`), recomputed per tick, with the medium
(profile-summary) rung produced OUT OF BAND on the shared world epoch
(`offscreen.schedule_profile_ticks` → `jobs.submit`, base_turn-stamped,
rollback- and epoch-guarded at landing, never cancelled by a turn starting) and every
tick stored as a validated provisional record (`canon_provenance`).

The earlier “scene boundary” wiring was not a boundary: it tested
`director_establish`, which normally exists only on turn 0, inside mapping's
skip-prone commit path. Unreleased development moves it into its own atomic
commit domain and records a frame-scoped `offscreen_epoch` on opening,
top-level location change, crossed in-world hour, or due event. The epoch and
log ride the existing whole-world checkpoint, and completed background work
must still match the restored epoch before landing. `tools/fire_rates.py` now
measures epoch opportunities, seeded fires, candidate selection, and scheduled
profile jobs against their actual denominators.

The fired-event substrate is no longer open. Schema v27 activates
`world_events` as a frame-scoped, chat-partitioned objective spine; the transit
domain promotes only events mechanics actually fired. It landed with
checkpoint restore, portable archive, branch id/payload/FK remapping, deletion,
legacy migration, and fidelity tests. `gaps` reads it first and falls back to
legacy fired scheduled rows without double-delivering a promoted event.

The first carrier delivery slice is now built: a non-empty public witnessed
surface is acquired only by a registered character physically at the event,
stored in that holder's frame-specific state, moved with their actual position,
and exposed only to their private character agent. Co-location never broadcasts
it. Crowd carriers, explicit copy events, subtractive degradation at copies,
bounded fan-out, and couriers/letters (`couriers.py`: position on a
`passable_path` route, clock-driven movement, perception surface, and
question/silence interception — a silenced rider's message never arrives)
have since landed, and the last two C legs landed in unreleased
development: caravans (a `stops` list on the courier object — dwelling
charged on the clock, two-way news exchange with the standing crowd,
surfaces and notices at each stop) and artifact carriers (`artifacts.py`:
a claim posted where the poster stands, acquired only by reading,
stopped by tearing down, with the authored-wording ceiling minted out of
band and landed only while the bill still stands). C is closed.

Landed next in unreleased development: **`reactive` is now behavior, not merely
permission.** A Director resolve may encode `offscreen_plan_ops`, but commit
requires the named registered character to have declared its basis on that
same beat. Plans are bounded frame-scoped state; typed time/event triggers can
fire only an effect adjudicated when the plan opened. There is no model call,
adaptation, or new invention at firing. Crossing a plan deadline itself creates
an epoch, and checkpoint restore rewinds the plan stage/history with the world.

Still open:

The full `character_agent` rung has now landed
(`offscreen.schedule_agent_ticks`, scheduled from the commit tail beside the
profile producer). Cards expose an explicit `simulation.offscreen_agent`
opt-in (default false); deterministic `full_agent_candidates` selects only
dormant opted-in minds with their own active authored plan or carried evidence
newer than their last paid tick, capped by `max_offscreen_actors`. Each
candidate gets one reduced turn out of band: the fail-closed `agent_context`
(allowlist; no scene parameter to forget to leave out), ONE character call
proposing a bounded attempt or plan abandonment, ONE Director adjudication
that alone may declare a consequence — validated by `mint_consequences` into
`scheduled_events` under a stable id and promoted to `world_events` by the
ordinary spine when it fires — and one atomic landing (own-trail movement,
plan advance, provisional log record, event-keyed autobiographical memory)
guarded inside a single transaction by the current epoch, the base turn, and
a per-subject `last_epoch_id` stamp, so a reroll or restore replays rather
than double-lands. `character_agent` is now marked built in the UI.
- **The stored `offscreen_log` history is still mixed** across the four legacy
  shapes plus the new record shape; readers coerce, nothing migrates.

### 2.9 Predictive staging

Pre-stage lore and plausible NPCs for likely-next locations. Pure latency win, no
correctness implication, which is why it ranks below the integrity work.

### 2.10 Session digest

A short end-of-session synthesis that re-anchors on resume. Small, and it
directly addresses the "coming back after a week" experience.

### 2.11 Weather rendering is rain, snow and lightning only

`static/js/weather-fx.js` draws falling precipitation and storm flashes for
rooms whose `weather_for_room(...)["weather_visible"]` is true, scaled by
`visible_reach`, and thunder follows each flash on a distance-shaped delay.
Not built:

- **the picture disagrees with the overlay under cover.** `weather_visible`
  was split from `sky_visible` so a porch draws the rain it is sheltering
  from, but `weather_words(..., "sight")` — which writes the backdrop image
  prompt — is still gated on `sky_visible` and `falls_on_you`. So a sheltered
  lane gets rain drawn over a picture generated as though it were dry. Fixing
  it means teaching the sight channel a third phrase ("rain beyond the
  eaves"), which moves `visual_signature` and re-generates every sheltered
  room's image — a cost worth choosing deliberately rather than in passing.

- **fog and wind have no visual.** Fog is the obvious next one and is a screen
  tint rather than falling weather, so it wants its own layer rather than a
  tile.
- **the fall is periodic.** Three tiled layers translating at different speeds
  is what a particle engine's randomness was traded for, and it is the reason
  the overlay costs almost nothing — but it is a loop, where particles never
  repeated. Watching one layer alone would show it; watching all three
  together, so far, does not.
- **snow does not settle** and rain does not streak a window. Both want a
  second, slower buffer that the current single-pass loop has no place for.

### 2.12 Ambience layering is capped at three, and has no sends

`ambience.py` mixes up to three simultaneous beds (`tone` / `weather` /
`extra`), each with its own gain, rerollable and pinnable per layer. What is
still absent:

- **no reverb or filtering.** A muffled room gets a different *recording*
  rather than the same one behind a low-pass, because the player is plain
  `<audio>` elements. Real filtering means an `AudioContext`, which needs its
  own unlock gesture — see the note in `ambience.js` on why Web Audio was not
  used for the crossfade either.
- **layers do not duck.** Nothing lowers the room tone when a louder element
  arrives; the gains are static per layer.
- **no per-layer loop offsets**, so two beds fetched at the same length can
  phase against each other audibly on long stays.
- **the loop overlap hides a seam, it cannot fix a clip.** `armSeamlessLoop`
  crossfades a bed into itself, which removes the hole at the file boundary but
  not a recording whose end does not belong beside its beginning — a passing
  car at 0:58 still arrives every 0:58. Freesound exposes no loopability
  descriptor (`ac_loop` is undefined on its search server), so `_LOOP_WORDS`
  guesses from tags; nothing measures the actual seam.

### 2.13 Matching a recording to a room is keyword overlap, not hearing

Freesound ANDs the terms of a query, so the seven- and eight-word acoustic
descriptions this module composes match *nothing at all*; `_query_ladder`
broadens until something comes back, and `_rank_candidates` then judges what
came back against the room's own words rather than the crowd's rating. That is
what a bath scene needs to stop being given falling roof tiles. What it still
cannot do:

- **it compares words, not sounds.** `fit` is set-overlap between a query and a
  recording's name and tags, with plurals folded and a penalty list of event
  words. A perfectly-tagged recording of the wrong place still scores; an
  untagged recording of exactly the right one scores nothing. Embeddings over
  the tag vocabulary would be the honest fix.
- **a room named in fiction has no acoustic vocabulary at all.** When the model
  writes proper nouns through into the query, the ladder strips them to
  something generic and the fallback to the room's own words hits the same
  wall — `Design.md`'s "describe the sound, never the fiction" rule is enforced
  only by the prompt.
- **`fit` is computed but never shown.** The picker lists candidates in ranked
  order without saying why, and a host who disagrees has no handle on it.

---

### 2.14 Clothing regions: what is still rough

The model, the authoring surface, the generator and the visibility switch are
all built (`Design.md`, "Clothing by body region"). What remains:

- **`attire.region_of` and `_SPANNING_CUES` are keyword tables.** Qipao, sari,
  thawb, abaya, kimono, toga and their spans are now in them, but the tables are
  still English word lists: a garment they do not know lands on the torso alone,
  which reads as "naked from the waist down" the moment it comes off. The
  coverage picker is the escape hatch — a garment whose coverage is set by hand
  is never re-guessed — and the DETECTOR now exists too: `attire.span_is_a_guess`
  and `guessed_spans` name every garment whose span came from a cue table rather
  than from an author, with `placed` marking hand-set coverage so it is never
  re-flagged. It is **unwired** — no production caller, only tests — and its own
  docstring says where it belongs: the commit seam, handed to the Director. So
  the wrong span is still only discovered when something undresses oddly, but
  the remaining work is one call, not a mechanism. A garment
  that is only SOMETIMES full-length (a tunic, a sleeved vs. sleeveless shirt)
  is deliberately left single-region.
- **`beneath` is authored per region, but the body's fallback is one string.**
  `describe()` fills an unauthored region from `embodiment.visible.summary`,
  which describes a whole person — so an unauthored region says the same thing
  as every other unauthored region. Acceptable while the alternative is making
  authors fill seven fields, but it reads flatly when several regions are bare
  at once.
- **`fStrList` fragments any list entry containing a comma.** It joins with
  ", " and reads back by splitting on ",", so a generated
  `"Nine golden tails from the lower back, shifting with mood"` was saved back
  as two features and `"vermillion, white, and gold"` as three. Found on a
  generated card, where it matters most: the generator writes prose entries,
  and the mangling happens the moment an author keeps them.
  **Eight of the ten call sites have since moved to `fLineList`** — Protected
  beliefs, Pride triggers, Shame triggers, Recovery supports, Characteristic
  stress signs, Voice markers, Excluded knowledge titles and Active concerns,
  beside `embodiment.visible.distinctive_features` — leaving exactly the two
  the entry always argued should stay: Aliases, at the character and persona
  editors, which is the one field that is comma-natured by nature. `fStrList`
  itself still splits on commas, so it remains a trap for any future caller
  handed a clause; the fix if one appears is `fLineList`, not a smarter split.
- **the reader has no view of it.** Regions exist in the card editor and in
  every prompt, but the story panel still shows the flat `wearing` list, so a
  reader cannot see that a robe is open, or that a shirt is stained, without
  inferring it from prose.
- **`decisive_targets` is sentence matching.** It reads a beat's prose to decide
  whose clothes came off at once, attributing by garment, then first person in
  the player's own input, then a sole name. It gets the actor-vs-target case
  right and the ambiguous cases wrong-but-slow (nobody hurries), and it decides
  only SPEED, never who may know what — but it is prose matching, and §3.1
  applies to it as much as anywhere. A structured "this act was decisive"
  signal on the declaration would retire it.
- **the process clamp is scoped per body, not per garment.** `process_targets`
  answers "whose undressing is still in progress" in BODIES, so "she begins on
  the sash" holds a jacket the same beat resolved off the same body. Making
  the shared attribution ladder answer in garments is a real redesign of
  `attire._attributed_targets` and of `advance`'s `process` flag; the
  conjunction needed to hit it (one garment mid-act, another resolved off, same
  body, same beat) has not been seen live. Design note 17 §"third incident".

---

### 2.15 Movement is an arrival, never a crossing

**Raised 2026-08-02**, after "step outside" landed correctly and still read
wrong.

**Half landed 2026-08-14; needs (2) below and nothing else.** A journey is
now a standing thing rather than a single hop: a declared walk survives a
beat that says nothing about it and advances one edge per beat
(`agents/director._travel_continues`, `scene.approach`), a long edge takes
two beats (`_LONG_EDGE_DISTANCES`), and the leg is computed BEFORE the prose
is written and handed to the author as `travel_in_flight`, so the scenery
changes on the page in the same breath as everything else. Need (1) is
therefore decided, and decided against the Narrator: the ENGINE owns the
crossing, the Director may only stop it (`travel_interrupted`), and no stage
is asked to infer a passage from a `moved` flag. Need (3) is met by the
distance tier rather than a new gate.

What is still missing is need (2), and it is the perception question the
entry always said was the hard one — see the paragraph that names it below.

The original statement, kept because the craft argument still holds for the
half that has not landed:

A turn that moves a body renders the destination and nothing else. The engine
has no representation of the crossing itself, so `positions` changes, the new
room's view is composed, and the beat reads as a cut: the body was there, now it
is here. For a step through a doorway that is fine. For anything with distance
in it — crossing a plaza, walking a corridor, riding an elevator between floors
— it flattens the part of the movement the player was interested in.

The player's own framing, which is the design: **narrate the movement, then the
arrival, then what the surroundings turn out to be.** Three beats of one action
rather than one snapshot of its result.

This is craft, not a defect, and it is recorded here so it stays separable from
the two things it kept getting confused with:

- `northern_plaza` reading empty was **not** distance. That room was an island
  — no edge reached it in either direction — so "looking around" correctly
  reported the only neighbour the map admitted. Fixed by
  `connect_orphan_new_rooms`; see `Design.md`.
- A view built only from the END state was a separate defect again, fixed by
  `_source_channels(prev_sc=…)`.

Neither of those would have been fixed by travel narration, and travel
narration would not have fixed either of them. What it WOULD change is a beat
that is currently correct and thin.

**What it needs.** (1) DONE — the engine owns the crossing: it computes the
leg deterministically before the prose exists and the Director may only
interrupt it. (3) DONE — gated on the `adjacent`/`near`/`far`/`remote` tier
the edges already carry, so a doorway step is unaffected.

(2) STILL OPEN, and it is the one that was always hardest: what a body
PERCEIVES mid-crossing. The honest answer is "both rooms, briefly" — the
same union `_source_channels` computes across a beat, and possibly the same
mechanism. Today a mid-walk body is simply IN the room the leg put it in, so
a corridor crossed over two beats is perceived as two rooms in sequence
rather than as a passage between them. That is a truthful account and a thin
one, which is exactly what this entry was raised about.

### 2.16 A summary window should be an INDEX over raw memory, not more prose

**Raised 2026-08-02**, in review of the summary-window work, and the right
destination for that layer rather than a defect in what landed.

Today the earlier windows travel *beside* raw recall: two paragraphs added to a
payload that separately ranks sixteen raw memories. That is the supplemental
form -- cheapest, and measurement says it is not redundant (14% mean overlap
with what raw recall already surfaced). It is not the strong form.

The strong form uses a window's **turn range** rather than its prose:

```
what does this beat remind me of
        -> rank the windows            (which stretch of my life)
        -> take that window's turns    (an index, not a payload)
        -> rank raw memories INSIDE it (the actual episodes)
```

The summary stops being autobiography dumped into context and becomes an index
over eras; the raw rows stay the episodic evidence. A character then recalls the
way recall works -- find the period, then the moments in it -- instead of one
flat similarity sweep over everything they have ever known.

**What it needs first.** The turn-range semantics are *emergent, not
contractual*. `memory_consolidate` says "merge the new batch into an updated
summary"; nothing in it promises a window describes its own range. It happens to
(3-16% carried text, measured), because the same prompt also demands
low-salience detail be shed. An index built on that would rest on behaviour a
prompt edit could silently revoke. Either the prompt states it, or something
measures it and refuses to steer when it fails.

**And a fallback for when the index is empty**, which for 53 of 67 live banks it
is over their opening turns (§1.21). A progressive form answers both -- rank raw
memories normally, and only reach for a window when the first pass returns
nothing convincing -- but "nothing convincing" needs an absolute confidence
signal, and the cosine band is 0.45-0.55 wide for everything, which is exactly
the floor that does not exist.

### 2.17 Memory reliability after temporal separation

**Shelved 2026-08-02**, updated after the controlled chat-38 embedding and
character-question benchmark. Seven isolated questions per arm used the same
prompt and payload schema. After correcting one deterministic phrase scorer
miss (“never stated” vs “never said”), semantic answers passed **7/7** versus
lexical-only **5/7**, and both grounded 100% of citations. Relevant evidence
reached the payload in **5/5** historical cases vs **2/5**, and relevant
earlier windows in **5/5 vs 0/5**. Raw-memory MRR was lower for semantic
(0.207 vs 0.400) because lexical put its two exact-word successes at rank 1
and missed the other three entirely, while semantic reached all five, often
through the summary-window layer. These are the next measurements and
mechanisms that would make reliable retrieval become reliable conduct.

**Integration pass landed 2026-08-02.** The character contract now has
separate present and past evidence lanes; current state is absent from the
memory branch; micro-round observations have unique ids; raw memory projection
contains no database/retrieval internals; summary prose cannot independently
reinforce durable state. Psychology now receives bounded, grounded
`memory_modulation`, absorption narrows deliberative recall without deleting
the automatic-recognition lane, dialogue keep-reasons survive minting, disputes
use exact stable refs plus present cause, and `memory_effects` distinguishes
retrieval from influence. Schema v24 records before-event and post-appraisal
affect. These close the implementation half of items 5 and 10 and most of 9;
item 4 has bounded effect telemetry but not the author-facing retrieval-event
ledger described below.

The modulation lane now also admits a mild memory-evoked body/threat response
without collapsing time: `somatic_echo` and `threat_bias` require exact past
evidence, are capped to 0.2, and are carried for one beat under
`active_state.memory_echo` with `temporal_source: remembered_past`. They
cannot write current somatic pain/pleasure, injury, goal impact, or a claim that
the remembered danger is present.

Deliberate query-setting is built as the private `ponder` sequence action. One
bounded query with a concrete reason is committed to the character's own state,
retrieved in an explicitly labelled `deliberate_recall` lane on top of normal
recall next character turn, then consumed. Ponder is absent from the default
output shape and requires a concrete reason. A useful result may raise a new
query immediately; receiving results alone is explicitly not a reason to do
so. What remains unbuilt is behavioural measurement of when characters choose
it well, not the mechanism.

**Remaining priority order:**

1. **Evaluate behaviour, not only answers.** Build a repeatable memory maze in
   which a character must recognise someone, honour a remembered promise,
   navigate from walked ground, reject a contradicted belief, and distinguish
   witnessed evidence from inference. Score the chosen acts. The existing
   benchmark proves reachability and temporal typing; it does not yet prove a
   memory changes conduct at the right moment.
2. **Separate recall confidence from claim credence completely.** The new
   `epistemic_origin` / `memory_form` names the axes and prevents provenance
   ambiguity, but a numeric recall-strength axis is still absent. A mind may confidently
   remember that it once inferred something while still assigning that
   inference low truth-confidence. Carry `memory_recall_confidence` beside
   `claim_credence`; never let retrieval itself promote the latter. Chat 38's
   kitsune probe exposed the ambiguity: the stored inference was 0.287 while
   the answer about having made that inference reported 0.75 confidence.
3. **Finish interior summary holes for legacy characters.** Chat 38's repaired
   live state has 41 windows and leading coverage is restored, but bounded
   absences remain between surviving windows (substantive coverage: Doctor
   419/452, Picard 8/17, Guinan 25/29). The current backfiller deliberately
   repairs only the destroyed leading era. An interior-hole repair needs the
   same inspect-on-copy discipline and checkpoint propagation.
4. **Log retrieval as an author-facing auditable event.** `memory_effects` now
   records model-declared influence and unbidden recall consumes it, but
   `access_count` still says only that a row was
   returned, but not the query, ranking reasons, score, whether it was cited,
   or whether it influenced conduct. A bounded `memory_retrieval_events`
   ledger should record those separately so false recall, unused payload and
   hub memories become measurable.
5. **Finish retrieval/rehearsal telemetry.** Merely being placed in context
   still does not strengthen a memory; `memory_evidence_used`,
   `memory_effects`, belief citation, and disputes now distinguish four later
   stages. Persist those distinctions in the proposed bounded ledger before
   adopting any accessibility/rehearsal policy.
6. **Retrieve counterevidence with uncertain beliefs.** When a low-confidence
   inference is decision-relevant, surface its strongest supporting and
   disputing rows together. This is the authoritative counterpart to
   non-authoritative contrast recall and prevents repeated one-sided retrieval
   from laundering a guess into certainty.
7. **Tune by query class, never with one global semantic weight.** Label real
   questions as exact quotation/name, place/navigation, thematic paraphrase,
   promise/obligation, or provenance. Tune and evaluate each separately. On
   chat 38 semantic retrieval greatly improved total relevance while the
   lexical fallback sometimes found the first exact hit sooner; both signals
   are useful in different proportions.
8. **Audit summaries against their source rows.** Consolidation can silently
   promote inference or hearsay into unqualified prose. Every summary claim
   should be traceable to source memory ids and retain the strongest applicable
   provenance/credence constraint. This naturally converges with §2.16's
   stronger design: summaries as indexes over evidence rather than substitute
   evidence.
9. **Retry semantically unsupported present-evidence use before accepting conduct.** In
   one final semantic trial the Doctor correctly denied that the anomaly was
   active, but supported the denial only with the memory of closing it and did
   not cite the quiet present. The output guard now warns and never fabricates
   a citation. The stronger next step is one bounded retry when a present
   observation exists but `present_evidence_used` supplies none, then accept the
   omission with an audit warning if the retry does not improve it.
10. **Measure the clarified provenance contract.** `epistemic_origin` and
    `memory_form` now name how the claim was acquired versus what representation
    is being recalled. In one prior
    trial the Doctor correctly said Hinami told him her name, cited the exact
    witnessed line, then labeled the answer `remembered` rather than `heard`.
    The prose was right and the typed provenance was wrong because the field
    can be read as "how I know" or "what kind of memory this is." A future
    contract should name those two axes separately rather than prompt harder.

**Measured non-solutions — do not retry without new evidence:**

- Globally stripping appearance boilerplate from summary queries made
  historical-window targeting worse.
- Adding goal/mood/unresolved-thread aspects to summary-window ranking made it
  worse again; the raw-memory result does not transfer to summary prose.
- Always including the origin window spends attention every beat for something
  usually irrelevant. The landed drift-triggered origin rule is the bounded
  form.
- Replacing lexical ranking with embeddings alone throws away the fallback's
  exact-match strength. The measured answer is fusion, then query-class tuning.

The reusable instrument is `tools/benchmark_memory_temporal.py`; extend it
rather than creating another one-off question script.

---

### 2.18 The Director as an orchestrator over scoped specialists

**Raised 2026-08-12**, from the owner: *"the director is the single most
complex task, and most failure prone. Anything to reduce its payload may
increase its reliability."*

**What is measured.** `director_resolve` reads 18,718 tokens of static
instruction sheet plus a ~7,500-token payload — the prompt is 71% of a median
call. Roughly 10–11k of those tokens are conditional machinery, and a typical
beat needs 2–4k of it. Six op families have never fired once across all 2,243
stored resolves (`courier_ops`, `crowd_ops`, `telling_ops`, `artifact_ops`,
`offscreen_plan_ops`, `destruction`), while costing ~1,870 tokens of
instruction on every call. Near-dead: `cast_changes` 0.5%, `overlays` 0.4%,
`weather` 0.1%, `containment` 1.9%.

`director_resolve` is also the only stage that can produce an uncommittable
turn: `_prepare_turn_commit` reads its `state_diff` and any raise there kills
the beat. Character output cannot — it is not a persistence authority. And 84%
of all rerolls begin at a Director stage, with 6.1% of turns needing three or
more attempts.

**The proposal.** An orchestrating Director over specialists, each OWNING a
subset of `state_diff` channels, behind one prose author.

**The argument that distinguishes it from conditional prompt assembly**:
*a specialist that is not dispatched costs nothing at all.* Not a smaller
prompt block — no prompt, no payload, no output surface, and no chance to
emit the channel wrongly. Mechanics not in play this beat are cold-stored
rather than merely trimmed.

**RETRACTED (owner, 2026-08-12): the framing of conditional assembly as the
ALTERNATIVE.** They are levels of one hierarchy, not competitors:
orchestration gives ownership, parallelism and fault isolation; conditional
assembly INSIDE each specialist gives the token savings. Measured over the
same corpus, a specialist that runs at all almost always touches exactly one
of its own channels (objects 1.11 of 5, social 1.10 of 4, body 1.13 of 4,
contact 1.22 of 4, spatial 1.52 of 6), so the orchestrator grants each
specialist a per-beat SCOPE — the set of its channels with possible work —
and the specialist's sheet is assembled from exactly those channels' chunks.
Dispatch is `bool(scope)`: one computation, so the two gating levels cannot
disagree, and one backstop covers both (a channel outside every served scope
that ships content anyway reaches `tell_director`).

It also answers the prefill objection that sank the first analysis. That
analysis assumed N shards each need the shared dynamic context, so fan-out
multiplies prefill. Scoped specialists do not: an attire specialist needs the
wardrobe, not the room graph, and on an ordinary beat only one or two run at
all. Total prefill can fall below today's single 26k call rather than
multiplying it.

**The offscreen family's 0% is a placeholder, not a verdict.** Read the wrong
way that number says "delete it"; it says the world outside the scene is
declared and unbuilt. Crowds moving, couriers carrying news, plans advancing
while nobody watches — plausibly as complex a task as the whole present
Director, and the specialist most likely to become the LARGEST rather than the
smallest. It is an argument for this architecture: a monolith cannot absorb an
offscreen simulator without every ordinary beat paying for it, which is part of
why the capability has stayed at zero. Pinned for development. Its gate reads
scene contents today and will need revisiting the moment "somewhere else is
happening" stops being visible from the current room.

**Per-specialist models.** A narrow specialist may not need a frontier model.
`agent_models` already keys configuration by role, so a lean fast model for a
scoped structural task and a frontier model for the prose author is a
configuration change rather than new machinery. Untested, and one of the more
interesting things the experiment can measure.

**What it must not become.** THE GATE HAS TO FAIL OPEN. If the orchestrator
decides "no attire this beat" and there was an attire change, the change is
silently lost — no warning, no retry, nothing in the ledger. That is this
codebase's recurring failure class, not a hypothetical: `entry_ops`,
`offscreen_plan_ops` and `project_ops` each cost a measurement, and the
`ForwardRef` blind spot in `tools/project_check.py` (2026-08-12) hid the guard
built to catch exactly it. A gating decision is a new silent-drop surface and
is the one thing that could make the Director LESS durable.

Two things make it survivable, both precedented here: gating already exists
(`build_plan` omits stages from `interpret.flow`; `pick_background_reactor`
returns `None` deterministically on most turns), and the backstop is a
deterministic post-check in the shape of `changes_asserted` reconciliation —
if the resolved prose asserts a change and no specialist owned it, say so.
Pointed at the gate rather than at the channel.

**What stays with the orchestrator, not the specialists.** The cross-channel
judgments: the movement backstop validates against the MERGED diff, substance
destinations derive from contact topology, a `scales` change cancels contacts
before the beat's own contact ops, containment derives positions. These cannot
be seen from inside one channel, which means the orchestrator is not purely a
router.

**Also settled, so the experiment does not re-litigate it.** Splitting the
PROSE from the DIFF is refused, not deferred: prose↔diff reconciliation is the
largest measured defect class in resolve's warnings, and blind concurrent
peers make it structurally unfixable rather than merely error-prone. One prose
author, structure owned against it — the alpha-8.0 perception pattern.

**How it gets judged.** Not on argument. `providers.py` now records the model
that actually SERVED each call (`_note_served_model`), because the corpus
behind every number above was served by a router silently substituting models
and cannot be segmented. A pinned model plus per-call attribution is a
precondition for the experiment meaning anything. The success metric is the
existing deterministic detectors — reconciliation omissions, authority
residuals, uncommittable turns — not a subjective read.

**Built (branch `director-orchestration`):** all six specialists — `body`,
`social`, `contact`, `objects`, `spatial` (the movement backstop stays with
the orchestrator, judging the MERGED diff), and `offscreen` (its OPS
surface and gate only: crowds/couriers/tellings/plans/hearsay-verdicts,
genuinely dispatchable the moment its subjects exist in scene and cold in
practice because the corpus has never contained them; the SIMULATOR stays
deferred) — shared between BOTH Director stages (interpret dispatches the
same definitions, scoped to the player's declaration, merging into
`state_assertions` before the deterministic validators). It shipped behind
the `director_orchestration` setting at default OFF; that flag is gone —
see the LANDED paragraph below. Per-beat channel SCOPE
drives dispatch AND per-specialist sheet assembly (chunked prompts,
`prompts.specialist_prompt`; structure enforced by
`tools/project_check.py`); the fan-out is genuinely PARALLEL and never
streams (canonical-order assembly, failure isolation under concurrency,
Aborted propagation — measured: five specialists at 0.5s collapse from
2.50s sequential to 0.51s, 9ms overhead); scope_report {granted, served,
produced} persists on each step; the single scope backstop reports through
`tell_director`; per-specialist roles are separable in `_log_usage`;
detector parity and every joint pinned by
`tests/test_director_orchestration.py`.

**LANDED 2026-08-14. The flag and the monolithic sheet are both gone**, which
closes the "flag on vs. off before it may default on" measurement condition
by answering it: the fan-out is the only Director path. It is more stable,
costs fewer tokens and less wall clock, so a switch preserving the losing
path only preserved a way to make the engine worse. The registry entry for
the unsplit sheet went with it — nothing sent it, so a preset key for it was
folklore — and every `RESOLVE_*` segment it was assembled from now belongs
to exactly one specialist or to the prose author's sheet, held there by
`test_every_delegated_block_has_exactly_one_owner`. What replaced the switch
is a CONCURRENCY choice, `director_fanout_mode`, parallel by default:
sequential exists for a provider that will not take concurrent requests, and
is not a fallback to the monolith (same hands, same scopes, same canonical
assembly). Two defects surfaced in the same pass and are fixed: the chunked
sheets were assembled per beat rather than read from the registry, so their
preset entries were editable and UNREAD — a host could rewrite the body
specialist's sheet, save, and the engine would send the stock one (all six
are registered now and an override replaces the sheet whole); and a
specialist repair could only mend or stay silent, so a hand asked to encode
something already carried shipped a staleness warning against a change it
had just certified — its `resolved_events` echo is read back off the repair
call now, with `already_true` verified against standing state exactly as a
dispatch verdict is. The prose author's OWN sheet is scoped the
same way (second carve, same mechanism): 14 prose-duty chunks
(`prompts.PROSE_AUTHOR_SHEET`/`prose_author_prompt`) gated on scene state
by `_PROSE_DUTY_GATES` from the same `_gate_facts` call, fail-open at
every level, never-gated contract blocks (firewall, manifest,
player-asserted facts, dialogue log, authority, pressure-OPEN) enforced by
`check_prose_author_chunks`, shipped-duty audit folded into the same scope
backstop, granted/gated_out persisted as `orchestration.prose_scope`.
Numbers (design note 19, end): prose-author core 6.3k tok, ~6.7–7.6k
typical, 9.3k fail-open ceiling, vs the 21.1k monolith; typical-beat floor
~9.1k total; the heaviest fail-open physical beats reach ~21k total but
spread over parallel sub-7.6k calls. Run 20 (14 beats, real
models, 2026-08-12) hardened the delegation from rhetorical to structural:
the prose author's stated output shape no longer carries the delegated
channels at all (`_PROSE_AUTHOR_OUTPUT_SHAPE` — the full shape was the
template the model kept filling, 18 discarded-channel emissions in 14
beats, pure output-token latency), and interpret gets
`INTERPRET_DELEGATION_NOTE` appended at the call site only when the flag
is on, overriding its own "FULL state_diff structure ... no subset"
instruction (design note 19, run-20 section). **What remains:** slicing
the prose author's PAYLOAD (still the full monolithic payload — the next
real token win); leaning interpret's own sheet by chunks (the delegated
channels are suppressed at the source now, but the blocks teaching them
still load); optional leaner rewrites of the specialist chunks (permitted
— they exist only on the orchestrated path); the offscreen SIMULATOR
(owner-deferred, out-of-band propose/ratify per the note above);
re-measuring the replaced-channel warning rate on a live run (the stored
variants hold only the MERGED output, so the after-rate cannot be read
from run 20's own beats); provider cache affinity (run 20 diagnosed the
19% prefix-cache rate as provider replica routing, not byte instability —
hits were constant sheet-sized prefixes, misses all-or-nothing; honest
ceiling ~57% with the per-beat payload inherently uncacheable; a
pinned/dedicated instance is configuration, not code, and is recorded
rather than chased). Two shape traps the same run surfaced are
closed in `schemas.py` rather than the prompts: a single value under a
`dict[str, list]` channel (`overlays`/`conditions`, StateDiff and the body
specialist) now wraps to the list of one, and a bare-string
`evidence` citation coerces like the list-of-strings form always did —
each had been costing a full temperature-0 repair round.


### 2.19 Character: scope the sheet, do not split the judgement

**Raised 2026-08-12**, alongside §2.18. Recorded so a future session does not
reach for the decomposition first.

The character step is the pipeline's largest single cost (~38.8s median, ~56%
of the turn on a one-reactor beat) and its sheet is the second largest prompt
in the engine: **48 named rule blocks in ~15,100 tokens**. The obvious thought
is to do to it what §2.18 does to the Director. Two halves of that thought,
and they come apart.

**SCOPING GENERALISES. SPLITTING PROBABLY DOES NOT.**

Many of those 48 blocks are plainly conditional and have structural
preconditions that are checkable the same way a specialist's scope is:
`SOMEONE IS WAITING ON YOU` (is anyone actually waiting), `ON PROBATION` and
`GOAL EXHAUSTION` (is a goal actually in that state), `PAIN AND PLEASURE` and
`ATTENTION UNDER STRESS` (is there any), `AUTHORIAL OFFERS` (were any made),
`SPATIAL FRAME` (is there anywhere to go), `UNBIDDEN MEMORY`. Assembling the
sheet from the blocks that apply gets the token and reliability win with **one
call, one mind, one coherent decision** — nothing about the judgement changes.

Splitting the judgement is the part to resist. The Director emits 34 mostly
independent state channels, which is what makes ownership meaningful there.
A character emits a DECISION: speech, action, affect, wants and belief updates
are facets of one act of judgement, and coherence IS the deliverable rather
than a constraint on it. Splitting "what she says" from "what she does" from
"how she feels about it" produces incoherence, not modularity — the prose/diff
join problem again, and worse, because there is no representation to reconcile
against, only a mind that either held together or did not.

**THE FIREWALL OBJECTION IS VOID, and should not be revived.** An earlier
draft of this argued that character sub-agents would multiply the firewall
surface. They would not. The character agent enforces nothing: it receives a
view that perception and spatial already scrubbed, deterministically since
alpha 8.0. Slices of an already-scrubbed view contain nothing the whole view
did not, so no new boundary exists and there is no new place to leak. A leak
there would be perception's failure and would have reached the single
character call identically. The boundary is upstream and singular; do not
re-argue this.

**The genuinely open question is narrower:** *what in that call is not the
judgement?* Psychology persistence already is not — `psychology_runtime.py`
does it deterministically from permitted inputs. If other pre- or post-work is
bundled into the same call, that is separable without touching the decision at
all, and is where any character-side decomposition should start.


## 3. Information-pipeline leaks still open

Ids are the erased pipeline sweep's own. Severity vocabulary: **leak** (a mind
receives what it did not earn) / **degradation** (a mind is denied what it did
earn, or is told something false about its own perception) / **corruption**
(durable state made wrong) / **latent** (mechanism real, crossing model-gated).

**The single largest item in this file**, on which the pipeline sweep and the
architecture audit converged independently: **structured signals with stable
identity, rather than prose matching, as the concealment and identity boundary.**
Everything in §3.1 is a symptom of its absence, and `grep signal_id` returns
nothing repo-wide. See §4.2.

### 3.1 Prose matching as a boundary

Materially improved — `_surface_translate_event` now fails closed, speaker
attribution is structured, `_redact_concealed_from_event` is casefolded,
word-anchored and pronoun-continuation-aware — but **not eliminated**.

- **C1 — quoted spans are an identity smuggling channel**, and the whitelist
  that guards them is loose: `body == L or body in L or L in body`, so any
  short genuine line ("yes") whitelists every fabricated quote containing it.
  Quotes are exempt from the identity scrub by design. Both passes now run the
  check — `_scrub_invented_dialogue` inside `_composer_tripwires`, reached from
  `_composer_finish_observer`, so the act pass is no longer the blind one — but
  it is **warn-only** in both, which is the right call and worth stating as
  such: a composed view is realised from percepts, so dialogue in it that does
  not match the delivered-line ground truth is an ENGINE defect, and scrubbing
  it would hide the bug instead of the leak. The loose whitelist therefore
  costs a missed WARNING now rather than a missed scrub.
- **C2 — short and common-word names escape the identity floor.** Forms under
  three characters and single-token are never scrubbed. `_COMMON_WORD_NAMES` is a
  separate, exact-case mitigation, not a fix for this.
- **D1 residual — a paraphrase with a fresh explicit subject still escapes**
  `_redact_concealed_from_event`. The function's own docstring names this
  residual and names the structural answer: carry identity on the event.
- **E1 — `knows_identity` uses strict membership** where `_scrub_view_for` uses
  the title-tolerant `_recognizes`. Inconsistent; over-anonymizes.
- **E2 — `_unknown_actor_label` strips only name and alias tokens**, so a unique
  identity-bearing epithet in the appearance survives into the label. By design,
  but it is the same channel.

### 3.2 Concealment gates not applied everywhere

- **A8 residual — `_disguise_leak_check` is warn-only.** The channel itself is
  closed: `_act_payload` is gone with the model-authored views, `_composer_act`
  is never handed `p_disguise`, and `concealed_truth` is minted only in
  `_subject_disguise_context` and now reaches no payload in either pass. What
  survives is the builder for the retired `action_onset` dict, which sets
  `subject_disguise` and is read by nothing — dead code that reads like a live
  leak, which is the reason to say so here rather than leave it to a grep.
- **B4 residual — `_ensure_environment` does not check darkness** on the "is here
  with you" branch. Containment is now gated; light is not. *No dedicated test.*
- **B5 residual — the micro-view append is still post-scrub**, running after the
  identity and invented-dialogue scrubs.
- **C3 — stray view keys survive normalization**, and the exposure went with
  the composer rewrite rather than being fixed. `_normalise_views` still writes
  through any unmatched key, so a view keyed by a non-awake character's name is
  neither folded nor overwritten by the residue — but it has no production
  caller left; only `tests/test_pipeline_audit.py` reaches it. *Dead path, not
  a live gate.*
- **X3 — `conceal_from` without `visibility: "concealed"` bypasses the
  background declaration filter**, which consults `visibility` only. Every other
  guard in `agents/background.py` fail-closes on `conceal_from` independently,
  precisely because models half-comply. *Latent, no test.*
- **X7 — gate salience reads raw input.** `commit.py` counts `resolved_event`
  mentions with no concealment gate, so a concealed declaration naming a presence
  still raises its pick priority.
- **X19 — `_llm_resolve_player_room` receives the private thought**, for a call
  whose only output is a position key.

### 3.3 Sense and awareness gaps

- **F4 residual — action delivery in the micro-loop is boolean visual rather
  than graded.** The sense-profile half landed: `agents/loops.py` reads
  `character_senses(observer_sheet)` and threads it into `_delivery_ok` and
  `sense_adjusted`. Speech is graded there; an action is still a yes/no gate
  followed by a whole sentence, so a half-seen act arrives entire or not at
  all, where a half-heard line arrives as a fragment.
- **F6 / S3-A5 residual — `spatial.spatial_digest` is still ungated** and
  renders every edge's authored room name, including rooms never visited. The
  perception payload was fixed (unseen edges keep their barrier, lose
  `to`/`to_name`); the digest that reaches the **narrator** was not.
- **F7 — `known_pronouns` releases pronouns on unverified mind-model keys.**
  `agents/character.py` keys off `set(relationships) | set(mind_models)`, which
  is the unvalidated set.

### 3.4 Multiplayer

All multiplayer-only, which is why they survived.

- **S3-A6 — `narrator_extra` lacks the consciousness gate and fidelity facts.**
  It ships `spatial_frame` unconditionally and its payload has no
  `player_awareness` key, unlike the primary narrator path.
- **S3-B2 — extra players' speech has neither speaker guard.** `_player_aliases`
  covers the primary persona only.
- **S3-B4 — the interpret-stage split is unchecked for extras.**
  `_reconcile_interpretation` coverage-checks only the primary input.
- **X11 — extra-player concealed speech has only one defence.** Perception's
  concealment list gets extras' concealed *actions* but not their concealed
  *speech*, and the dialogue-fidelity floor whitelists all extras' speech
  including concealed — so a leaked co-player whisper would not be scrubbed.
  *Plausible.*
- **X12 — the onset pass is primary-player-only**, so the reaction-gate and
  `targets` guarantees never run for extras' sequences at onset. *Degradation.*
- **X9 — the host reads co-players' private thoughts.** Full step content streams
  to the initiator (always the host) and is embedded in archives. Not a code bug
  — the host is the trust root — but an unstated product boundary, recorded so it
  stays a decision.

### 3.5 Persistence

- **P6 — the knowledge-tag door is the widest lore-to-mind channel.**
  `knowledge_for_character` delivers any `knowledge`-category entry with
  `range='global'` and a matching coarse tag to every tag-holder, with zero
  encounter tracking; category, tag and range are model-proposed at
  `mapping_commit` with only vocabulary validation. **One mis-filed secret is
  instantly in every character's `world_knowledge`.**
- **P7 — `known` introductions are validated by model judgment** over the
  objective log: the mapping model judges from `beat_dialogue_log` /
  `beat_resolved_event`, concealed lines included, and the engine takes its
  verdict. The application gate is materially tighter than when this was
  written — roster resolution, then a positive presence test on BOTH parties
  (an introduction between two people who were both absent used to pass once
  the roster admitted offscreen characters, trading a missed edge for an
  invented one, which is worse because a wrong edge is indistinguishable from a
  right one afterwards), then `is_recognized_in_frame`. What is untouched is
  the judgement itself and the fact that **recognition never decays or
  retracts**: there is no path that un-learns a face. *Plausible.*
- **X24 — the legacy-archive raw-id fallback grafts interior state.**
  `chat_archive.py` resolves an archive integer against whatever local row holds
  that id, then attaches the archive's `chat_chars.state` to it. Memories are
  safe. Legacy path only.
- **P5 / P8** are defects, filed at §1.8 and §1.9.

### 3.6 Deliberately kept

Recorded so nobody "fixes" them by accident. Each is pinned by a test asserting
the current behaviour.

- **B1 (sound half) — opaque is not soundproof.** Containment gates sight and
  scent, deliberately not sound.
- **B2 — the comm/shape floor delivers across any barrier on `intended_target`.**
  The residual risk lives in director tagging, not here.
- **F5 — `observable` falls back to the raw `attempt`.**
- **A7 — the one-reaching-perceiver rule** in `_state_reaches_anyone`. Now moot
  in the live path: per-observer payloads mean the perceiver set is one name.
- **X5 — the scene-manager `full`-mode `audience[name]="none"` annotation** is an
  annotation on a shared context rather than structure. `ambient` correctly
  refuses divergence.
- **E3 — outcome extra players get `knows_identity: True` hardcoded.** Advisory
  only.

### 3.7 Test gaps

`tests/test_pipeline_audit_leak_gaps.py` covers D1, D2, B3, B5, X14, F1, F2/P1,
S3-A4, S3-A5, S3-A8, X18 and X4. **A1 and B4 still have no dedicated test**, and
A1 is a confirmed leak class.

### 3.8 A structural risk, not a finding

`agents/perception.py` does **not** call `common._delivery_ok`; it uses
`hear_level` and `_in_plain_view` directly, while `agents/loops.py` routes
everything through `_delivery_ok`. Two families of delivery gate now exist and
can drift apart. Consolidating them is the cheap insurance.

### 3.9 Residuals of the alpha 6.3 physical-ledger work

Four things the ledgers still cannot say, all deliberately left rather than
guessed at.

**A hover is not a contact, and there is nowhere else for it.** A measured
"two inches of visible space" between two mouths is real fiction with real
tension, and `contacts` can only say touching or nothing. It currently lives
(or lived) in entity `state`, where nothing ages it. `_drop_contradicted_state`
retires such a key only where a standing contact already speaks for that part;
a genuine hover with no contact survives, unaged, exactly as before. A
near-contact tier — or a `manner` that means "not quite" — would cover it.

**Entity `state` still has no ageing of any kind.** Nothing retires
`"breath": "caught"` or `"voice_quality": "held_breath_steadying"` either; they
persist verbatim until the model happens to overwrite them. Contact was the
worst case because perception reads it as present truth, and that one is fixed
at the source — but the disease is wider than the part that was treated.

**An orphaned relational value is dropped rather than folded.** When
`thumb_touch: "feather_light_at_ear_base"` is retired by a standing thumb
contact, its qualifier is discarded instead of merged into that contact's
`detail`. Folding it was rejected for now: matching the right contact by part
name is the same guesswork the whole change exists to remove, and a wrong
`detail` is a sentence the narrator will repeat.

**A garment moving between bodies keeps no identity.** `_mint_shed_garments`
carries a garment's condition onto the floor and back, but "the coat she lent
him" is a different coat record from "her coat" the moment it lands on him.
`resolve_garment` is per-body by construction.

Also unbuilt, from the same work: nothing derives a station from within-room
movement INTENT ("she crosses to the hearth"), because there is no within-room
approach concept for it to read — room-level `scene.approach` is the only
staged-movement memory there is.

---

## 4. Architecture gaps

From the erased 2026-07-19 audit. Its Gap 1 was conceptual, Gap 2 and Gap 7 are
now largely closed, and Gap 4 is partial. These are what remain. Its Priority 3
is done bar one item, and Priority 4 is done — the suite it measured at 527 tests
now stands at 3,112. Gap 3 / Priority 0 (overlapping physical authorities) is
gone too, and was settled the OPPOSITE way to the direction it recommended: it
asked for the scene to be generated from the normalized tables, and
consolidation made the frame-scoped `world.scene` blob the sole runtime
authority with `world_entities` a derived projection and `world_placements`
decommissioned. The matrix it said was "verified absent" is published in
`docs/guides/DATABASE.md` and pinned by `tests/test_world_authority_consolidation.py`,
whose `test_world_placements_have_no_runtime_writer` fails if the model forks
again.

### 4.2 Gap 4 residual / Priority 1 — evidence-carrying perception

**The headline item, now half of it.** Mind models carry confidence and
evidence, and confidence can still blend smoothly while resting on duplicated,
circular or mutually dependent evidence.

The reference half landed: `MindHypothesis.evidence` is
`list[EvidenceRef]` rather than free text, and `agents.character.ground_refs`
holds `mind_model_updates`, `belief_updates` and `association_updates` to ids
actually delivered to this mind — an update whose evidence does not resolve is
DROPPED, not warned about, and derived summary prose is refused
(`allow_summaries=False`) so a summary cannot launder itself into a durable
belief.

What is still missing is the DISCRIMINATOR. `EvidenceRef` carries `event_id`
and `fact` and nothing that says whether the evidence was witnessed, reported,
inferred, or copied from another belief — so two references can resolve
perfectly and still be the same claim arriving twice. Without that, revision
cannot discount a circular report or preserve competing hypotheses, and no
`signal_id` exists anywhere in the tree.

The same primitive is what §3.1 needs to stop matching on prose, and what
`current:<perceiver>:<n>` already mints for the present beat. **Two of this
file's largest items are one missing structure.** The adversarial-test half of
this priority has shipped.

### 4.3 Gap 5 — canon validation needs provenance tiers

Mapping is privileged and can turn proposals into durable lore. Player
assertions, resolved objective events, imported canon, staged spatial
necessities, character beliefs and narrator wording should not enter the same
"proposed fact" pool. §3.5's P6 and P7 are this gap seen from the other side.

**The tier itself has landed.** `canon_provenance.py` carries the seven
dispositions verbatim — `imported_canon`, `resolved_fact`, `player_claim`,
`spatial_generation`, `character_belief`, `narrator_audit`, `inferred_mapping`
— under `PROVISIONAL`, with `outranks` claiming only that provisional sits
below all seven and deliberately declining to rank them against each other,
because nothing has measured that and inventing an order would be a decision
taken by accident. Wired into `gaps.py`, `offscreen.py`, `subjects.py` and
`living_world.py`; `tests/test_canon_provenance.py`.

Two things remain, and they are the ones with teeth:

- **Promotion out of the provisional tier is an explicit `NotImplementedError`
  seam** (`canon_provenance.promote`). It belongs to the Director —
  `state_diff.ratified_claims` → `background_claims.settle_claims`, which today
  sets a status flag in the world-KV blob and writes nothing into canon. That
  missing write is the whole of it, and it was left out so the tier could land
  without touching the Director seam.
- **The mapping path is not routed through it**, which is the privilege this
  gap was opened about: mapping can still turn a proposal into durable lore
  without a disposition. §3.5's P6 and P7 are the same gap seen from the read
  side, and §1.30's warning applies — the read-side gate and the first real
  producer must land together.

### 4.4 Gap 6 / Priority 2 — frame/global conflict control

Frame-scoped world keys, memory visibility and character overlays permit genuine
concurrent play. Lorebooks, entities, placements, conditions and scheduled events
remain chat-global, so two frames may prepare against different snapshots and
merge into one shared domain later.

**Recommended direction:** decide domain by domain whether it is frame-local,
immutable across frames, append-only with temporal coordinates, shared but
revision-checked, or merged through an explicit paradox rule. **At minimum,
prepared commits touching shared canon should carry a base revision and reject or
reprepare when the revision changed before commit.**

Verified absent: no revision concept in `db.py`, `commit.py` or `frames.py`.

### 4.5 Gap 8 — uniform cost against non-uniform uncertainty

The engine self-gates background reactions and caches mapping, but stage
selection is otherwise coarse. A quiet continuation and a multi-party spatially
contested action do not need the same validation budget.

**Recommended direction:** a deterministic risk score from action complexity,
observer count, spatial novelty, authority claims, contradiction count and
state-diff breadth — used to select validation depth, model tier, repair count,
and whether a sanity pass is worth its cost. Any such checker validates
invariants and deltas; it never rewrites prose or decides story outcomes.

Verified absent.

### 4.6 Priority 3 residual — request-size limits

Decompression-bomb limits are in `importers.py`. There is no upload or
content-length guard in `app.py`. Needed before the service is treated as safe
beyond a trusted local environment.

---

### 4.7 Matter has no volume, so nothing can wash anything away

The substance ledger accumulates. Coalescing landed (`9a6bc3c`) — same material,
same source, same region, same body is one pool a later release re-describes —
and conservation landed, so swallowing empties the mouth. What is missing is
DISPLACEMENT: a more abundant fluid arriving on a region carrying away what was
already there.

It was deliberately not built, twice, for reasons that still hold:

- **The amount vocabulary is not a magnitude.** Of 39 stored terms, `trace`,
  `moderate`, `small` and `copious` order as English, but `coating` is a
  distribution, `oozing` a rate, `remainder` purely relative with no magnitude
  at all, `dustpan full` container-relative, and `hot, viscous torrent` buries
  its magnitude among temperature and viscosity.
- **The precedent makes it a no-op on the reported case.** Following
  `affect.CAPACITY_LADDER`, an unreadable term takes the mildest rung — and the
  reported case is spelled `coating` versus `light coating`, so neither would
  ever displace the other. Making it fire requires ruling that a distributed
  film outranks a droplet, which is a physical model of fluids, not a reading
  of a word.
- **The reported case is cross-substance** (one fluid washing away a different
  one). `_same_pool` deliberately keeps different substances apart, and
  deciding that A dilutes B needs a miscibility model the engine has no
  representation for and § Genre boundary forbids hard-coding.

Separately and much cheaper: **wiping already works and is almost never used.**
`op: remove` / `op: clear` exist and the Director can emit them. Measured
corpus-wide: 38 adds and deposits against 5 removes, and zero removes after
turn 38 of the reference story. That is prompt efficacy, not a missing
mechanism, and it is worth trying before any material model is designed.

**Open question this section exists to force: does the engine grow a material
model at all?** Everything above is blocked on that answer rather than on
difficulty.

### 4.8 Two regions on one body, spelled differently, are two regions

`mouth` and `oral cavity` mint separate substance rows on the same body.
`AGENTS.md` forbids a body-part synonym table with a measured reason
(`tail_spade` is a nameable place on a tail, not `tail` blurred), and that pair
shares no word, so no structural rule reaches it.

`spatial.canonical_region` is now the single fold point for every region
comparison in the ledger, so if the substance ledger is judged to warrant an
exception the contact ledger does not, there is exactly one place to add it.
Explicitly NOT made moot by `owned_region`: qualifying which body owns a region
is orthogonal to folding two spellings of one region on one body.


## 5. Deferred backlog

From the erased enterprise_d_v2 40-turn audit backlog. Its P1 (pronoun fidelity)
and P3 (dialogue dedupe) shipped, as did the variant/alias half of P7. Each entry
below is written to be resumable cold: symptom, root cause, fix, test.

### 5.1 P2 — ambient repetition, deterministic

**Symptom.** "The bridge hums" recurs across a run. An AMBIENT RESTRAINT prompt
rule reduced but did not eliminate it — **reworded variants slip the exact-word-run
diff** in `_already_established_phrases`, which is still exact six-word shingles.

**Adjacent mechanism that is not this.** `_overused_phrases` (exact 3-gram
cross-block tic ban, wired into the narrator) now catches literal recurrence. It
does not catch the reworded variant, which is the whole point of this item.

**Fix.** Extend recent-cue dedupe to ambient set-dressing: a small per-chat ledger
of recently-used ambient sensation lemmas (hum/thrum, klaxon, flicker,
door-open), fuzzy-matched by stem/lemma rather than exact word-run against the
draft; drop or warn on a re-mention not flagged as changed. Sits beside
`already_established_phrases` in `agents/narration.py` / `agents/common.py`.

**Test.** "The bridge hums." established in recent prose; a new draft "the ambient
hum of the bridge" is caught despite the reworded surface.

### 5.2 P4 — `established_facts` continuity ledger

**Symptom.** Second-act amnesia: a character contradicts a fact the whole room
established — one character said "I can't translate it" nine turns after the log
was translated in front of them; another's relief flipped to fear across adjacent
turns.

**Fix.** A world-KV `established_facts` ledger. Emit from `director_resolve` as a
new optional list op, like `obligations`; persist in `commit.py` with dedup and a
cap, mirroring `commit_obligations`; inject the recent N into every co-present
character payload alongside `world_knowledge`, with a prompt rule: *settled
on-page facts may be disputed, never forgotten or contradicted.*

Note the existing `world_facts` path feeds lore, not character payloads — this is
a separate, always-included ledger.

**Test.** Establish a fact at turn N; assert it appears in a later turn's
character payload and that the prompt carries the no-contradict rule.

Verified absent: zero occurrences of `established_facts` in source.

### 5.3 P5 — route player-authored NPC acts through the character reaction

**State.** Director-prompt rules (NPC acts belong to the NPC; being acted upon is
not passive) make the resolve *render* the reaction. It is not routed through the
actual `reaction_loop`, so the NPC gets no genuine agent-generated interiority or
choice for the beat.

**Root cause.** `_requires_reaction_phase` gates a reaction on
`commitment == "contestable"` — still literally `if event.get("commitment") !=
"contestable": return False`. A player physical act on an NPC is `asserted`
(player authority), so the NPC never enters the reaction loop. Separately, a
player-*authored* NPC volitional act executes as an objective event with no
character-agent call at all. Reactor derivation remains spatial-only.

**Fix.** (a) In `director_interpret`, when a player action targets a present,
volitional, sheeted character with a conflict verb, add that character to the
beat's reactors **even when the player's act is `asserted`** — the reaction is the
NPC's *response*, not a contest over whether the player's act succeeded. (b) When
the player declares a volitional act *by* an NPC, hand it to that NPC's character
agent to adopt (supplying interiority and voice) or refuse. Both touch the
delicate director/reaction seam — go test-first, small.

**Test.** A player "grab X" beat produces a reaction step for X; a player-authored
"X lunges" beat calls X's character agent.

### 5.4 P6 — room-boundary scene-truth

**Symptom.** A door closed at turn 31 silently reopened at 32; by 33, characters
in the adjacent room were speaking *into* the closed room and one was effectively
inside it. An information-integrity failure in an engine whose premise is the
information barrier.

**Root cause.** Not the perception *rules* — they gate same-room, closed-door and
wall correctly. It is scene *state*: door state and positions drift, so perception
is fed a wrong co-present set.

**Adjacent coverage that is not this.** Portal state is now first-class in the
scene blob, `apply_transit_dock_edges` recomputes edges from hatch/transit phase
with authored-barrier preservation, and the narrator receives `portal_states`
plus a fidelity check. That is narrator-render fidelity, not the scene-state drift
and co-present-set construction this item specifies.

**Fix.** Build the perceiver's co-present set strictly from `world.scene` room
membership plus open-door adjacency; ensure a door's closed state persists across
turns unless an action changes it; ensure a character led into a room has their
position updated. Add a hard invariant check in the commit path.

**Test.** Close a door at turn N; at N+1 assert it is still closed and that a
character in the adjacent room is not in the occupant's co-present set.

### 5.5 P7 remainder — promotion-turn identity binding

*Low severity, cosmetic.*

**Symptom.** On the turn a background presence promotes to cast, the player's view
can render it "the unfamiliar person" for one turn.

**Root cause.** Autonomous promotion runs at commit, *after* that turn's
perception, so the promoted character's canonical name is not yet in the
observer's `known` set during that turn — compounded by a name-variant mismatch
(seeded "Data" vs promoted "Lt. Commander Data").

**What shipped.** The alias/variant fallback (`_recognizes`), and
`promote_background_character` now seeds a full mutual roster.

**What remains.** It registers only the canonical `character_name(sheet)` with no
aliases or variants, and the **attach** path in `app.py` seeds only
player↔character, never cast↔cast.

**Test.** Promote a presence the player addressed by name; assert the observer's
view of it that turn is not anonymized.

---

## 6. Design-note residuals

Features their design notes argue for that are not built. The note holds the
argument; only the gap is listed here.

### 6.1 Background life — [`BACKGROUND_LIFE_DESIGN.md`](design/BACKGROUND_LIFE_DESIGN.md)

Most of §3 shipped in alpha 4.0. What did not:

- **The digest lifecycle (§3.5)** — the largest piece. Only the raw `recent` ring
  buffer exists (`BACKGROUND_RECENT_TAIL = 4`). No `digest`, no compaction, no
  freeze-while-unobserved, no prune, no `last_seen_clock`.
- **Promotion conversion (§3.6)** — `importers.draft_promoted_character` reads
  the `events` table's `dialogue_log` and event text through
  `_promotion_evidence`, never `blurb` or `recent`, so a promoted presence
  loses the ledger the engine had been keeping about it and is rebuilt from
  the objective record instead (which is also §1.8's leak). The threshold half
  of this is closed by a different counter than the one proposed: promotion is
  gated on `addressed_turns` (`commit._promote_after_addressed`), which counts
  only DELIBERATE interaction — the Director marking a presence as the
  player's addressee, or the player naming them. `AUTO_PROMOTE_DIALOGUE_THRESHOLD
  = 3` still counts manager conduct, but it no longer decides, so an
  `ambient_turns` counter is no longer the thing wanted.
- **Interim filler on return (§3.9)** — no `interim` field, no `last_seen_clock`.
- **Canon-referenced blurbs (§3.8.1)** — no `canon_ref` field; substituted by a
  style-guide-level canon licence.
- **The separation eval (§3.3.1)** — the deterministic leak floor is built; the
  proposed measurement of real cross-presence leak rate has no artifact in-tree.
- **Location-themed population and the chorus presence (§4).** `AggregateEntity`
  is declared in `schemas.py` and unconsumed.
- **The narrator dilution clause (§5)** — no tension-gated ambient suppression.
- **The `digest`/`interim` tier typology (§3.1)** — only `blurb` was built.
- **The prompt fix for §3.8** — a blurb tell should be available colour, not a
  required beat.

### 6.2 Extensions — [`EXTENSIONS_DESIGN.md`](design/EXTENSIONS_DESIGN.md)

**Built in 9.0.** The `extensions/` loader with per-item isolation and computed
trust classes, `enabled_extensions`, the `SonderExtensionAPI` facade, the
plan-splice registry at named anchors, `on_step`/`on_turn_committed`, the four
`ext:<id>` state homes with the committed-turn write gate, character reads
including settled psychology, `window.Sonder` with sidebar tabs / step renderers
/ stream events / three-strikes retirement, the `/api/extensions` routes,
install from directory or URL with zip-slip and symlink refusal and atomic
`os.replace`, enable/disable/remove in the 🧩 menu, and the `cohesion-demo`
reference extension. Developer documentation:
[`docs/guides/EXTENSIONS.md`](guides/EXTENSIONS.md).

The tier ladder (Tier 0–3, story packs as rung 1) was **abandoned**, not
deferred — design note §2 records why. Do not treat its absence as debt.

A second batch closed the surfaces the first release left open: `ui.css` is
served (as its own document, linked after the host's sheets), enable/disable
hot-load in the browser through `Sonder._load`/`_unload`, extensions serve their
own routes under `/api/extensions/<id>/x/`, `api.add_commit_domain` runs inside
the turn's transaction, `api.on_character_payload` is the attributed routing
seam, `api.llm_json`/`llm_text` give a model call on any configured role,
`api.add_director_specialist` adds a seventh Director family, and
`check_extension_manifests`/`check_extension_imports` lint the tree.

Still missing:

- **Declarative advisor stages** — a stage as data (role, prompt, input-scope
  whitelist, anchor) for authors who write no code. Genuinely useful; no longer a
  prerequisite for anything.
- **Pre/post hooks on `compute_step`**, and the two routing hooks that were
  designed alongside `on_character_payload` but not built: `on_admission` and
  `on_view`, which would let an extension alter what perception ADMITS rather
  than only what the assembled payload carries.
- **An extension specialist cannot reach the prose author.**
  `PROSE_AUTHOR_SHEET` and `test_every_delegated_block_has_exactly_one_owner`
  are in-tree, so a registered family writes its channel to the merged
  `state_diff` and nothing narrates it. Documented in the guide rather than
  fixed; closing it means a prose-chunk registry with the one-owner test
  extended across the boundary.
- **`tools/project_check.py --extension <path>`** — the author-facing self-check
  that runs the same two lints against an unbundled extension before shipping.
  The checks exist; the CLI entry point does not.
- **Phase 2: the reviewed registry.** Every field it needs (id, version,
  `sha256`, `provenance`) is already written at install time, so this is an
  addition rather than a migration.
- **Scoped clients**, which is what would make third-party frontends real for
  non-host players: scoped stream and chat reads, `client`-scope tokens. A
  firewall decision, and it deserves its own design note before code.
- **Frame-scoped extension state.** `ext:<id>` world keys are chat-global (not in
  `FRAME_SCOPED_WORLD_KEYS`), so they are shared across eras.
- **`extension_runtime/` is outside the UI catalog's reach.**
  `tools/extract_ui_catalog.py` scans root `*.py` and `agents/*.py`, so the
  dozen-odd extension registration errors that surface in the Extensions menu's
  error field are never harvested and never translated — while the four that
  happen to live in `agents/director.py` are. Recorded as verbatim exceptions
  rather than translated, because four of sixteen would make one list half
  Japanese. Fix is to add the package to the scanner and translate the set.
- **`Sonder._unload` cannot undo side effects**, only registrations and the two
  injected elements. A monkeypatched global, a timer or a `document`-level
  listener survives a disable. Inherent to the no-sandbox posture; stated in the
  guide so an author can compensate.

### 6.3 Greeting-seeded openings — [`GREETING_IMPORT_DESIGN.md`](design/GREETING_IMPORT_DESIGN.md)

About 60% shipped in alpha 1.4, under a materially different architecture — the
narrator **does** run on turn 0 and its prose is overridden afterwards, rather
than the design's pre-baked variants plus resume. Still unbuilt and still wanted:

- **Ingest-time extraction caching.** `importers.py` always writes
  `"extraction": None`; extraction runs lazily at launch and is discarded, not
  persisted. No `extractor_version` stamping.
- **The `private_history` write.** Seeds route to character memory only.
  Idempotency itself is closed and by a better key than the design named: each
  seed carries `greeting_seed:<sha1(content)[:16]>` and the batch upserts on
  `(chat, character, event_key)`, so a retried or partially-failed launch
  updates one row rather than writing a second, and editing or reordering the
  greeting cannot orphan the old row the way a positional key would. It
  deliberately does not dedupe ACROSS launches — `start_story` creates a fresh
  chat each time, so a second launch is a different story entitled to its own
  copy.
- **`player_slot` and escalation.** `GreetingInterpret` has only a flat
  `player_room`; no `hard_attributes`, no `pronoun_tokens`, no conflict detection.
- **Turn-0 greeting swipe** (`greeting_swipe`, `refresh_checkpoint(cid, 0)`).
- **Two named invariant tests** — verbatim preservation and knowledge boundary —
  do not exist.

### 6.4 Place purpose — [`DESIGN_PLACE_PURPOSE.md`](design/DESIGN_PLACE_PURPOSE.md)

v1 is built. Deliberately not built, each for a stated reason: witnessed
drink/water/warmth (no thirst or cold vital, so no deterministic signal),
told-basis node MINTING (told-basis affordances on a node the mind already
holds are built — `place_purpose` mirrors them from reconciled `stated_fact`
hypotheses; what testimony may not do is bring a place into existence),
negative entries, and the `repair`/`social` affordances
(no consumer — dead weight becomes a to-do list). The own-memory-row heuristic
(signal 2) is deferred as the doc allows.

### 6.5 Place graph

The walkable-edge defect is §1.6; the redundancy watch is §1.12.

- **`basis: "told"` has no PLACE-GRAPH writer**, deliberately — and the
  distinction matters, because the affordance ledger one layer over does write
  it: `place_purpose` mirrors `stated_fact` hypotheses onto nodes resolved
  `by_name` as `{basis: "told", sureness, about, claim}`. Testimony can say
  what a place you already know is FOR; it cannot mint the place. The approved design derived
  hearsay edges from `stated_fact` place claims, and implementing it revealed
  that deriving *connectivity* from free text means text-mining it — the
  non-deterministic derivation this engine refuses everywhere else. `told`
  remains an accepted value with no code path. **A future testimony writer needs
  a structured claim field naming the two places and the direction, not a parser
  over prose.** Recorded because someone reading the node shape will otherwise
  assume hearsay edges exist. This was the design document being wrong, not the
  implementation.
- **Do not remove the three-valued frontier semantics.** `_frontier_hops` returns
  `None` (spent), `0` (live but unmeasurable), or `N`. The middle value exists for
  saves written before the graph — a walked room with no recorded exits can
  honestly be called neither spent nor near. It is not defensive padding; removing
  it would make old saves read as exhausted.
- **Live sight correctly outranks the remembered gradient.** Recorded because it
  looked like a gap and was not: `visibly_no_way_through` pre-empts the distance
  verdict via the existing `_VERDICTS` precedence, which is the right order.

### 6.6 Psychology as pressure — [`DESIGN_PSYCHOLOGY_AS_PRESSURE.md`](design/DESIGN_PSYCHOLOGY_AS_PRESSURE.md)

(a) and (b) shipped; (e) declined by design. Open:

- **(c) Deterministic inclination beside the raw sheet.** Deferred, not
  rejected — landing it alongside (a)/(b) would confound the measurement that
  decides whether it is needed. It must **relocate** salience, not add it: the raw
  sheet has to be demoted in the same change that introduces the derived view, or
  the character gets two heavy citable blocks instead of one.
- **(d) A trait as a disposition, not a switch.** Whether this needs explicit
  representation or emerges once (b) and (c) land is the open question.

### 6.7 Long-term goals — [`DESIGN_LONG_TERM_GOALS.md`](design/DESIGN_LONG_TERM_GOALS.md)

v1–v3 are built, including goal-slot currency. Undecided:

- Whether a renewed intention should **cost** something, so renewal is a decision
  rather than a reflex. Without a cost, "renew" is always the cheapest answer and
  nothing is ever given up.
- Whether **displacement should feed the drive-strain ledger** — giving up a
  drive-serving project is plausibly a strain event.
- Whether drive and project both weighing 1.0 needs revisiting. Current position:
  no. Revisit only if a measured run shows a project-serving want being *emitted
  and then losing* to a drive want, which is a different failure from the one
  observed.

### 6.8 Living world — [`DESIGN_LIVING_WORLD.md`](design/DESIGN_LIVING_WORLD.md)

Phase 1 (branch `living-floors`) built the deterministic floors of A
(`routines.py`), B (`living_world.mint_consequences` +
`mechanics._fire_due_events`) and D (`place_obligations` +
`attach_owed_history`), plus the settings ladder for all five approaches
(`LIVING_WORLD_BUILT` is the declared/built authority). Held for phase 2,
which starts when the epistemic-leak audit branch merges:

- **C, the rumor ledger floor** — deliberately NOT the document's §3
  delay-line as written: the author's constraints (design doc §9, verbatim)
  require **carriers with positions and routes** the player can intercept,
  the anti-protagonist priority rule (propagation interest computed from the
  event, reputation downstream of delivery, the null result as the
  load-bearing test), and invented gossip entering through
  `background_claims` + the provisional tier as its first real producer
  (the lane measured 0-of-29). *Carriers with positions and routes have
  since landed as `couriers.py` (positions on `passable_path` routes,
  clock-driven movement, interception/silencing that stops delivery); the
  claims-lane producer and reputation rules remain as stated.*
- ~~**E, the antagonist ladder** — rungs 1 and 3 per §5; waits on C because a
  race lost without an information trail reads as the engine cheating.~~ —
  landed: the reactive floor fires authored stages, and the adaptive ceiling
  (`offscreen.schedule_agent_ticks`) adapts only from character-owned carrier
  evidence, C's trail having landed first.
- **The ceilings of A, B, D** — ensemble tick, consequence chaining
  (needs a significance flag *computed from event properties*, never the
  subject — §9.3), obligation-aware pre-generation. All documented as
  extension points only; `LIVING_WORLD_BUILT` marks these three unbuilt and
  `effective_depth` runs a requested ceiling as the floor. When one lands,
  it lands behind the rung `LIVING_WORLD_REQUIRES` already declares
  (`stochastic` for the A-D ceilings, `character_agent` for both depths of
  E): the off-screen ladder is the one authority ceiling, and a mechanism
  must never acquire authority the ladder did not grant.
- **Obligation retirement at honour time** — `attach_owed_history` still
  annotates a place's lore hits after the place has been generated (accrual
  stops structurally; attachment does not), and nothing yet marks a debt
  honoured. Harmless while obligations are rare; close it before C makes
  places chatty.

### 6.9 Character-agent output audit — [`../design_notes/09-character-agent-audit.md`](../design_notes/09-character-agent-audit.md)

Optimization audit (2026-08-11) of `character_step`'s output contract on the
owner's corpus snapshot, recent era n=404 calls. Verdict worth keeping: the
stage does NOT have `director_resolve`'s 84%-discard profile — ~85-90% of its
~1,974 output tokens/call is genuine product, and the psychology division of
labor (model authors appraisal, `psychology_runtime`/`affect` own persistence)
is already right. The note holds the measurements. The instrumentation, the
stress/hedonic template shrink, the goal-slot derivation and the observation
wrapper compaction landed 2026-08-11 (Design.md rows "The character contract
asks only for what commit reads" and "A second model call says it happened");
still open:

- **`considered_responses`** — schema-documented viewer-only scratch
  (`schemas.CharacterOutput`, beside `_coerce_considered_responses`, and still
  required by the prompt's own JSON shape), duplicates the consumed
  `response_candidates` in
  137/404 calls (re-measured 130/401). Engine-unread is NOT the bar: a
  freeform pre-list is plausibly chain-of-thought that seeds better
  candidates, so the gate is a cheap `contract_bench`-style A/B on stored
  payloads, not a grep. Drop it from the required JSON only if the A/B shows
  no candidate-quality cost. ~0.8s/call.
- **Read the second-call notes before designing a bounded-delta retry.**
  Every retry/repair rung now writes one `_engine_notes` line naming its
  path and duration. After a few sessions the deciding number is: fires of
  `"decision review retry"` per 100 character calls, times the mean duration
  those lines carry. Below ~5 fires/100 the full re-solve costs ~1-2s/turn
  amortized and is not worth a design that risks coherence between a
  regenerated sequence and a pinned appraisal; at ~15+/100 with ~30s
  durations it is the largest remaining lever in the stage.
- **NOT approved for cutting:** appraisal prose scratch
  (`goal_relevance`/`expectation`/`uncertainty`/`emotion`, ~130 tok/call) is
  engine-unread but sits upstream of numeric axes that are non-default in
  98-100% of emissions — a `contract_bench`-style A/B on stored payloads is
  the gate, not a grep.
- **Payload reordering for a longer cached prefix — gated on the affinity
  measurement.** The character payload opens with mostly-stable sheet-derived
  fields but places volatile `active_state` seventh, ahead of stable
  voice/senses/abilities/attire, so the cross-turn shared prefix breaks
  ~1-2k tokens in where it could run ~4-5k. Moving the volatile `self`
  fields after the stable block would lengthen the prefix implicit caching
  can reuse — but unlike the `user` routing hint this changes what the model
  reads in what order, which is a quality question needing its own argument.
  Do not build until the cache-affinity hint has run for a few sessions and
  `_log_usage`'s `cached_tokens` shows (a) hits landing at all, and (b) hits
  consistently stopping near the system-prompt boundary rather than deeper —
  only that pattern makes the reorder worth a quality A/B.

### 6.10 Extra body parts — [`../design_notes/11-extra-body-parts.md`](../design_notes/11-extra-body-parts.md)

The card field (`embodiment.extra_parts`, closed attachment/aspect menus),
the region_visibility-gated perception delivery, the Director payloads and
the editor menus are built. Deliberately not built:

- **Director-driven transformation** — growing or losing a part as a beat
  outcome. Needs a scene-level override ledger with commit/archive/checkpoint/
  branch work; the per-story card edit covers the authored case today.
- **Garments that cover a part itself** (a tail sock, a wing binder) — needs
  part-keyed coverage, i.e. the attire model learning slots outside its
  closed `REGIONS`. `through_clothing: false` covers the tucked case.
- **An import warning for a part described twice** — a declared `kind` whose
  word also lives in `visible.summary` prose double-describes the body.
  `importers.character_import_warnings` is part-aware in the OTHER direction
  only: it fires when body prose names a part the sheet does not declare
  (`_prose_names_a_part` against `_PART_WORDS`, and only when
  `embodiment.extra_parts` is empty), which is the failure that costs a
  kitsune nine invisible tails. The double-describe case is the mirror and is
  cheaper to be wrong about, so it is unflagged.

### 6.11 Garment displacement — [`../design_notes/17-garment-displacement.md`](../design_notes/17-garment-displacement.md)

Region-grain displacement (the third clothing axis) is built; deliberately
left open:

- **Left/right asymmetry** — "one shoulder down, the other up" has no
  structural home: `REGIONS` carries no lateral axis anywhere (contacts and
  injury share the same coarseness). Condition prose carries the asymmetry;
  coverage stays conservative (covered until fully off the region). Adding
  laterality would be a whole-body vocabulary change, not an attire one.
- **Transparency** — the authored "sheer black silk robe" covers without
  concealing, and the ledger has no axis for it: a covered region is a
  concealed region to `region_visibility`. Today sheerness lives in the
  garment's name/description prose only. A `conceals: full|sheer|net` axis
  on the garment would be the shape, but it is a perception-grading change
  and needs its own design pass.
- **Retro-repair of stale displacement prose** — the corpus holds condition
  strings that encode state from before the axis existed. Deliberately not
  retro-executed (prose is not state); they heal when a beat next touches
  the garment (the detectors fire and feed the Director the channel) or by
  hand in the region editor, which now expresses displacement directly.
---

## 7. Experiments not yet run

Measurements the design notes name as the thing that would settle a question. An
unrun experiment is unfinished work, not a broken thing.

- **The gods expand the maze** —
  [`DESIGN_MAZE_EXPANSION.md`](experiments/DESIGN_MAZE_EXPANSION.md). Designed, not built;
  depends on nothing not already in the engine. Needs a second SVG whose western
  7×7 is byte-identical to `maze7x7-a11.svg`, an explicit `--expand` flag so
  `--resume`'s fingerprint guard is overridden rather than weakened, a
  deterministic seam check, and an interlude variant carrying the announcement.
  The question is the one never asked: **can a mind revise a map it already
  trusts?** Two arms from one snapshot, one announced and one silent.
- **A14 — one configuration end to end without intervention.** The A11–A13 rows
  cannot support a clean before/after performance claim because the configuration
  changed underneath them. The only thing missing from that table.
- **The psychology-as-pressure re-measure** — the same maze arm with (a) and (b)
  only, re-counting *"Given his X"* per beat, *"torn between"* per beat, and
  violations of a stated value. Gates §6.6's proposal (c).
- **A village-scale run** — several characters, thirty turns, ordinary places. A
  different instrument from the maze, which is saturated and stopped producing
  new findings after A13. §1.2, §1.3 and the `circling` watch item are the ones
  most likely to bite it.
- **A town-scale place-purpose fixture** — 20 named rooms, 3 affordance sites.
  Measure beats from hunger onset to reaching food, with and without
  `recalled_places`. It works if the number falls and the route still reads like a
  person walking rather than a solver.
- **The running ablation** — a map with a genuine long corridor and a `large`
  hall, run twice by one character, once with `sprint_reach` ablated. It works if
  beats-to-goal falls while **moves**-to-goal does not.
- **The surface-comfort property test** — a body parked on a bed for 30 beats ends
  with stamina up, `charge` unchanged, absorption below 0.25, and at least one
  departure-capable want intact. If any of the four fails, the anti-attractor
  design is wrong and no amount of constant-tweaking fixes it.
- **Prompt efficacy for crowds, tellings and projects.** The first playthrough
  with the model side unauthored (`tools/model_playthrough.py`; artefacts in
  `demos/vale-model-played-14-*`) handed every 8.0 mechanism an explicit
  occasion across 11 Director resolves, on two independent models. Reached for
  and correctly encoded: `courier_ops` (both), `artifact_ops` (one) — and those
  were refused for a structural reason since fixed, not a bad encoding, so
  those two prompts land. Never declared once, by either model, on any
  occasion: `crowd_ops` (a packed market square, then listening to it),
  `tell_ops` (telling a named character what the player saw), `project_ops` (a
  stated multi-stage intention). The gap is now isolated — the same commit path
  drove all three to 100% acceptance under `demos/ashen-quest-51-*`, where a
  human wrote the ops. When rewriting those clauses: a bare prohibition
  inverts, and naming a concrete occasion is what works. Re-run the harness
  afterwards and compare; the artefacts are checked in.
- **`make test-browser` for the early-narration render** (`126009c`).
  Playwright is not installed on the machine it was written on, so it was
  checked with `node --check` and a stub DOM instead.
- **Full narrator token streaming.** Only the conservative half landed —
  render on the narrator `step` event. Streaming the tokens themselves would
  put the first word at ~75% of a turn instead of 100%, but the narrator
  re-runs on a fidelity or craft rewrite on roughly a quarter of turns, so it
  needs a re-stream or a visible "revising" state first.

### From the alpha 8.4.4 measurements

All four are named by
[`WORLD_METABOLISM_FIRE_RATES.md`](experiments/WORLD_METABOLISM_FIRE_RATES.md)
or by the work that shipped in that release. Ordered by expected value.

- **Why 3 of 31 characters have ever formed a PROJECT.** `tools/fire_rates.py`
  reports `has ever held a project 9.68% (3/31)`, mean 0.03 against a cap of 2,
  and the row's own note says the tier is unreachable if that is zero.
  `CLAUDE.md` records projects as what made NPCs pass the maze without altering
  their drives, and as the tier carrying "go home, take the injured one to a
  doctor" — an NPC walking somewhere for a durable reason is the oldest
  spontaneous-event engine there is. Whether the gap is the adoption
  deliberation refusing, probation lapsing, or the prompt never reaching is
  unmeasured. **Smallest number in the corpus with the largest documented
  effect; measure this before enriching anything in the world layer.**
- **Why the Director never declares a crowd, courier or caravan.** Every
  off-screen row reads `no chances` — the precondition never arose. The ops
  exist and are contracted. Unreachable, unread, or never applicable to the
  stories played so far? Those have entirely different fixes, and the answer
  decides whether a pre-planning sidecar is the right shape or a second inert
  layer on top of the first.
- **Whether `sensory_channels` changes the prose.** It is wired, tested and
  firewall-argued, and payload-to-behaviour coupling is model-mediated. Same
  beat, same model, before and after, is the only thing that settles it.
- **Whether touch/smell scarcity is delivery starvation or story mix.** A
  checkpoint replay counting beats where the scene held standing player
  contacts or substances while `observations["player"]` carried no touch span.
  Gates the substrate half of any further sensory work.

## 8. Parked

Not scheduled, not committed to a phase. Kept so they are not lost and not
accidentally built.

- **`providers.chat_complete_async` is dead.** Defined, imported by `app.py`,
  and called from nowhere but its own retry loop. The threading model works and
  the `contextvars` discipline is built around it, so the recommendation is to
  delete the import rather than build on it.
- **`prompt_cache.py` is dead** — no importer anywhere — and its
  `estimate_cacheable_tokens` heuristic is wrong by 5x to 262x on every stage.
  `AGENTS.md` still names it as the watch-file for cacheability.
- **`agents/common._agent_json`'s docstring** describes the ladder as "one
  temperature-0 repair, then per-candidate fallback" and no longer mentions the
  length escalation added in `c9c1fbe`.

- **A conformance test for `Design.md`.** Its status table is prose. A test
  asserting each "Built" row still resolves to real code — symbol exists, module
  imports, field present — would make that file self-checking the way `make
  structure` keeps `CODE_MAP.md` honest. Highest-leverage idea here: it prevents
  exactly the drift this compilation had to repair.
- **A leak-injection suite.** Deliberately plant a forbidden fact in a character's
  world record and assert it never surfaces in that character's output across N
  turns. The firewall is the engine's central claim and is currently protected by
  construction plus targeted tests.
- **Salience-driven personal lore.** *"This reminds you of a festival you walked,
  long ago"* — fired on genuine resonance, silent otherwise. Fired every beat it
  is a tic; fired rarely and on-key it reads as soul.
- **Per-character retrieval depth** as an explicit dial beside tier and
  temperature — spend deep retrieval only on pivotal beats. Today the only depth
  control is the absorption-driven `_recall_cap`.
- **Belief-revision salience.** Provenance makes revision *possible*; making the
  moment of revision itself high-salience is what lets a betrayal recontextualise
  forty turns and land as betrayal rather than confusion.
- **Perception prose bound by the audibility layer.** Live data shows perception
  narrating "difficult to parse from this distance" while the deterministic layer
  had already ruled the speech fully audible. The deterministic layer is right;
  the prose should be constrained by it rather than free to contradict it.
- **An optional minimap.** A read of the ledger the spatial architecture already
  maintains — nodes are rooms, edges are adjacency with barrier state, plus a
  containment breadcrumb. **The one non-negotiable constraint: it must be an
  epistemic view, not an omniscient one** — the character's own mental map, i.e.
  fog-of-war. A minimap drawn from objective truth would be a spatial information
  leak, the exact failure the perception firewall exists to prevent, rendered
  visually. Topological, not geometric; opt-in; degrades to nothing when the space
  is not well-structured. Doubles as a coherence/debug view.
- **Remove the deprecated macro schema.** `fiction_worlds`, `fiction_locations`
  and `transit_edges` are dead — nothing in the runtime reads or writes them — but
  they are still created, snapshotted, restored and exported. Removal is planned
  and needs a migration.
