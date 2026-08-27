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

**Rule 3 is overdue here, and this note is the debt.** §1.2, §1.3, §1.5, §1.13,
§1.17, §1.19 and both surviving §1.24 bullets were all found at alpha 6.0–6.9;
the tree is at alpha 9.6, so each has sat through ten-plus releases untouched.
Rule 3 gives two answers and neither is "leave it here": promote it, or admit it
is parked and move it to §8. Next reader to open this section owes one of those
for each of the eight.

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

- **Perception has no player-ACTION scrub, and the SPEECH scrub this entry
  used to name is dead code.** Chat 56 t10's fabricated lever grip reached the
  player's view as "I grip the console edge" with nothing between the Director
  and the narrator, and the Director-side guard is still the only thing
  standing there. `common._scrub_undeclared_player_speech` has **no production
  caller** (verified 2026-08-19: `agents/perception.py` imports it and calls it
  nowhere; only tests and `tools/perception_quality.py` reach it), because
  perception stopped asking a model to write views —
  `tests/test_perception_has_no_model.py` pins that. So the second independent
  floor this bullet used to ask for cannot be built the way it described: a
  player-action check would sit where `_composer_tripwires` does, on the
  composed view, and it would be a defect DETECTOR rather than a scrubber —
  which is the right shape, since a fabricated act in a composed view is an
  engine defect and scrubbing it would hide the bug instead of the leak.

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

**Narrowed 2026-08-19.** Reciprocity landed: a NEW passable edge whose standing
reciprocal reads `wall` is refused unless the same diff re-declares that side
passable — the mirror of `_shield_standing_passage`'s two-sided-sealing rule,
scoped to `wall` only, since a standing `closed_door` is openable from either
side and `one_way_window` asymmetry is deliberate vocabulary.

A room-EXISTENCE check was landed and then removed, which is worth recording so
nobody reaches for it again: `tests/test_spatial.py` pins a live west-wing
mapping flow where a corridor's edge is minted BEFORE the room exists, and
`neighbor_map` tolerates dangling edges by design. An existence rule has to wait
for room-and-edge minting to become atomic.

What remains is this entry's own conclusion — a stated BASIS for a new
adjacency between known rooms (`authored|walked|opened|generated_map|asserted`),
with the orchestrator rather than the model stamping the trusted values. That is
a schema and prompt change across the mapping and spatial specialists.

### 1.5 A character cannot revise a bearing they learned wrong

`disproven` fires when a doorway fails to exist. Nothing fires when a doorway
exists but the character remembers the wrong HEADING for it. After a bearing
corruption was fixed in the world, one character kept oscillating in exactly
the pockets whose bearings had been wrong while he learned them.

**Narrowed 2026-08-19, and it is a smaller entry than it read.** The place
graph is not the store holding the stale heading: `_confirm` overwrites
`rec["bearing"]` on every re-standing (`persist/commit_place_graph.py`), so a
walked doorway self-corrects at the next visit. What has no retraction path is
the LEARNED ASSOCIATION — `mind/psychology_runtime.py` weakens a belief only
when something disputes it, and nothing ever disputes a heading. Fix it there
or nowhere.

Related, and wider: a character can revise a belief about the world and has
almost no mechanism for revising a belief about themselves. Project
displacement is the only one.


### 1.7 JSON validation stalls cost beats

A model answering with a shape the schema does not admit costs the whole beat:
in a story it is a character who simply did nothing. Six-plus across one
experiment arm, then twice in eleven live turns on 2026-07-30.

**Every shape measured has been closed** — a `sequence` of bare sentences
(`_sequence_event_from_prose` reads such an entry as an ACTION unless the whole
string is a quotation, the safe reading rather than the likely one: typing
prose as speech would author an utterance AND transmit it to everyone in
earshot), the whole answer wrapped in one key of the model's own
(`_unwrap_envelope`), a staged lore `content` that was an object, and a
condition written as its own description. `_name_what_was_discarded` names what
was dropped for whatever still cannot be read, and the character step does have
a bounded schema-repair path (`agents/character.py` → `agents/common.py` →
`llm/llm_quality.complete_validated_json`).

**What remains open is the mixed sentence.** `Says, "Nobody leaves this room."`
keeps every word in its attempt text and is typed as an act, so a character in
the room may not receive it through the dialogue channel. Pinned as intended at
`tests/test_schema_leniency.py`. Deciding it needs the hearing path looked at,
not a better regex.


### 1.10 An entity's free-text `state` never ages, and a mind reads its own stale copy (S3-A8)

*(Absorbs §1.24's byte-identical bullet and §3.9's ageing bullet, 2026-08-19.
It was one defect written three times in three sections, which is most of why
it read as three small things.)*

Nothing reconciles an entity's free-text `state` / `description` against the
beat's resolution, and nothing retires a key the beat did not touch. A body's
`posture` / `activity` / `held_items` blob is overwritten only when a model
happens to rewrite it; `"breath": "caught"` and
`"voice_quality": "held_breath_steadying"` persist verbatim until it does.
`contacts` was the worst case and was fixed at the source — this is the rest of
the same disease.

**It is a READ-BACK LOOP, which is what makes it the worst thing on this list.**
`agents/perception.py` composes `composer.body_state_percept(entity_state)`
(`posture`, `activity`, `held_items`, channel `interoception`, source "you"), so
a stale blob is not merely bad prose: it is what the mind believes about its own
body, and it feeds the next declaration and the memory of the beat. A mind that
lowered its wrench still reads *"raised to chest level, aimed forward into the
dark"* as what it is doing now.

**Measured 2026-08-19.** The engine's own detector fires on **62 of 306
instrumented commits (20.3%), 122 instances** — subjects overwhelmingly the cast
mirrored as scene entities (Hinami 44, Tamamo 32, The Doctor 25). Of 599
`world_entities` rows, 408 (68.1%) carry a non-empty `state` dict; walking every
checkpoint in `chat_id, turn_idx` order and hashing each entity's `state` gives
**2,074 unchanged runs across 425 (chat, entity) pairs — median 1 turn, p90 14,
max 138, and 172 pairs hold a run of ≥15 turns byte-identical.**

An earlier "skip the update" fix was **reverted** as durable corruption;
`persist/commit_entities.py` now warns `"possible stale clause (S3-A8)"` and
commits the blob anyway, pinned deliberately by
`tests/test_pipeline_audit_leak_gaps.py` as *a signal, not a fix*. **The
reverted fix is the record of what not to do.** What this wants is an
ageing/reconciliation rule for free-text state keys, not another guard. No
schema change. Root cause — free-text state blobs with omission-only
reconciliation and `_PROTECTED_STATE_KEYS` — untouched.

**Narrowed 2026-08-19.** `breath` and `voice_quality` — the two keys measured
persisting verbatim — now expire on every merge unless the incoming diff
re-asserts them, across all entities including ones the diff never mentions.

**Narrowed 2026-08-25, because that rule was defeated by the cheapest model
behaviour there is.** Expiry counted a re-emission as an assertion, so a
specialist echoing its whole state blob back verbatim kept every momentary key
alive forever. Measured on chat 88 turns 53-67: the hand owning `entities`
re-emitted the blob nearly every beat, and `throat_action` set at turn 56 was
still standing at turn 67 — thirteen beats after the act it named. Two rules
answer it, both in `world/spatial_merge.py`:

- **An echo is silence.** A byte-identical re-emission of a value that was
  ALREADY ASSERTED no longer counts as re-assertion; only a CHANGED value
  does. The cost is real and accepted: while a model keeps restating a
  momentary fact word for word, the key stays expired — it does not come back
  and then go again. For the momentary vocabulary, byte-identical across two
  beats is stale by construction, and a genuinely continuing dynamic has its
  own channel that persists through silence by contract
  (`contact_action_ops`). The `_merge_entity` "a schema default is silence"
  analogy is weaker than it reads — a default is UNCHOSEN and an echo was
  emitted — so the 13-beat measurement is what carries the rule, not the
  analogy.

  **ASSERTED, not STANDING — corrected 2026-08-25, before it shipped.** The
  first form of this rule compared the incoming value only against the value
  standing in the scene, and expiry deletes exactly that value: the next
  identical echo found nothing standing, re-established the key, and the echo
  after that expired it again. Measured on that form, one diff merged six
  times running gave `gaze: downcast` / gone / `downcast` / gone / `downcast`
  / gone — a momentary key blinking forever, on precisely the
  verbatim-re-emission input the rule exists for, and worse for every reader
  of the committed blob than the stale value it replaced. So a value
  suppressed as an echo is remembered under the scene's
  `expired_entity_state`, and every later echo of it is silence too. The
  memory lives only as long as the echo run: a beat that says nothing about
  the key releases it, so a genuine re-assertion after a silence is still an
  assertion, and suppression is never a standing ban on a word. A scene whose
  bodies are not mid-echo carries no such key at all.
- **The vocabulary is a stated class, not a list of names.** `state` is open
  free text, so an allowlist can only ever name the momentary keys some story
  already wrote. It is now the exact keys `breath`, `breathing`,
  `voice_quality`, `expression`, `gaze` plus the process-suffix families
  `_action`, `_motion`, `_sensation`. Re-measured over all 77 stored scene
  blobs on 2026-08-25: the predicate captures 31 of 1,270 stored
  key-occurrences under nine distinct names (27 of them newly reachable) and
  none of the other 370 distinct keys — every one of those a configuration
  (`power_state`, `lock_status`, `held_items`, `posture`).

Two residues stay open, deliberately. `_register` is NOT a process family: a
till or a ledger named `x_register` is a thing, not a reading, so that family
fails OPEN — as does any momentary key without a process-shaped name (a bare
participle, an anatomy noun, `taste_register` in the corpus). Failing open is
the correct direction, because a lingering momentary key is stale prose the
next beat overwrites while a configuration key wrongly called momentary
silently DELETES authored state. The general answer for the residue is a
declarative transience marker on the entity-state schema — the model saying
whether a key is momentary — which is a schema change with its own
silence-default question and is not taken here.

`activity`, the sharpest read-back key, deliberately does NOT expire yet:
`tests/test_body_position.py` pins it as load-bearing standing state, and a
first attempt at expiring it broke that test. Which of the two contracts wins is
a product decision and has to be made before the key moves. `posture` and
`held_items` stay durable by design — those are the S3-A8 reconciliation
problem, not an ageing one.

The reviewer's proposed `raise` on an undeclared key was declined: entity
`state` is deliberately open free text that models write into, and
`_ENTITY_DEFAULT_FIELDS` establishes the opposite doctrine — an unlisted key is
copied, silence is never an erasure.

### 1.11 `ctx.warnings` reaches the pipeline drawer but not the story reader

**Landed, alpha 6.9**, except for an aggregate reader. Every warning is tagged
with the step that raised it (`pipeline_context.StepTaggedWarnings`, keyed off a
contextvar set in `compute_step`), persisted onto that step's saved content
under `_engine_notes`, and rendered above the step in the pipeline drawer
(`static/js/chat.js`). The tagging lives in the list rather than at the ~40 call
sites, so both spellings are caught including ones not written yet.

Why it was worth landing, on the record: perception dropped both sight sentences
out of a character's view of an embrace happening six feet in front of him (chat
38, turn idx 140), warned about it twice, and the warnings went nowhere. What
survived into his memory of that beat was a sound.

**Residual, and it is a roadmap wish rather than a defect:** there is no
aggregate view — no way to ask "which turns in this story had a view repaired",
which is the question that would have caught those six turns earlier. A warning
during a live run also still passes silently; only the persisted record shows
it.


### 1.11a Pacing still decides who may ANSWER, and that half is unmeasured

**The perception half landed 2026-08-19.** `perception_act` builds a perceiver
for every cast body the scene places somewhere (`_present_cast_bodies`), not
only for `flow.reactors`. Being in the room is what decides whether you saw it.
Free: perception makes no model call, and `agents/loops.py` reads
`flow.reactors` for itself, so who speaks and what the beat costs are unchanged.
Measured before: a witness was missing from `reactors` in 757 of 975
multi-witness beats (77.6%), and 1,639 of 4,292 character-presences (38.2%) got
no act view at all.

What stays open is the half the Director legitimately owns. `flow.reactors` is
a pacing judgement — who speaks this beat — and its quality is still unmeasured:
nothing checks that the people it picks are the people a reader would expect to
answer, and the prompt sharpening in alpha 6.9 moved the perception number
without anyone establishing what the pacing number should be. A beat where the
addressed party is left out is now a pacing defect only, which is the right
shape for it, and it is the one worth measuring next.

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
- **Nine payload markers is an attention budget.** `projects`, `en_route`,
  `adrift`, `ends_in`, `ground_fully_known`, `goal_reached`/`goal_held`,
  `fading`, `project_review`. Each is something a model must notice and act on,
  and attention is finite — at some point adding the tenth marker makes the
  ninth less likely to be read. Re-checked 2026-08-19: the LIST has not grown,
  but the markers have grown sub-keys (`closer_than_last_room` /
  `further_than_last_room` inside `en_route`, `beats_since_new_ground` beside
  `ground_fully_known`), so the budget is being spent without the count
  changing. Count what a model must READ, not what the payload is keyed by.
- **The place graph's distinct contribution is narrower than proposed.** With
  pruning gone, unpruned `known_exits` + `known_dead_ends` carry most of the
  routing information by themselves; the graph's remaining unique contributions
  are `disproven` retraction, walkedness surviving the recency window,
  reverse-declared `seen` edges, and bounded eviction. They are kept as
  graph-bounded *views* rather than a second authority, which is right while both
  exist — but two representations of one fact is the shape that produced
  `rekey_place_claims` and `reconcile_inference_confidence`. **If a third
  consumer appears, collapse them** — and one has arrived to be judged:
  `world/place_purpose.py` reads `state["place_graph"]` directly, for the
  `affords` ledger rather than for routing. **The condition has now FIRED and
  this is a decision that is due, not a watch item**: verified 2026-08-19, the
  graph has three module-level readers outside its own writer —
  `agents/character.py`, `world/place_purpose.py` and `persist/commit_memory.py`.
  Collapse them or state why three is the stable number.
- **The locomotion verb list is unproven in live play.** It was tuned against
  one live `resolved_event` and the existing suite, and it includes posture
  verbs that double as ordinary elaboration — "leans in", "settles". A character
  who declared a non-locomotive act and is then written as leaning toward
  someone fires a correction retry. That is the intended reading (leaning in IS
  a distance change, and distance is the character's to declare), but it is a
  judgement call made on one example and the false-positive rate is
  **unmeasured**. Blast radius is bounded — one retry, kept only if it lowers
  the violation count, so a spurious flag costs a call and cannot corrupt the
  beat. If it proves noisy the fix is to drop the posture verbs, not to widen
  the window. *(Moved from §1.1a, 2026-08-19.)*

*(Two further bullets — observation-text duplication and the gist ladder — were
recorded negative results with retry protocols rather than watch items, and
moved to [`experiments/MEASUREMENT_BACKLOG.md`](experiments/MEASUREMENT_BACKLOG.md)
§5 on 2026-08-19. Neither may be retried without the protocol stated there.)*


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

**The fragmentation half landed 2026-08-19.** Records now carry `entity_id` (a
stable scene-entity binding, made only when EXACTLY one body answers to the
identity) and `aka` (former spellings). A presence that acquires a proper name
mid-story keeps its dialogue turns, `addressed_turns`, sketch, blurb and
promotion progress across the rename, and promotion cleanup sweeps the
entity-bound and `aka`-connected spellings so an orphan cannot react alongside
its own sheet. The ledger's keys stay display-name strings, so the raw readers
named below need no change and no SQL migration was required —
`background_presences` is a frame-scoped world key and rides the existing
whole-`world` carriage.

The collision half above is UNCHANGED and still correct: ambiguity refuses to
merge, because an over-merge welds two characters into one and a split is the
recoverable direction.

### 1.18 The fallback is doing all the work

**Found 2026-08-01**, investigating whether embeddings could make the engine's
word tables "fire and catch" more often. Shelved deliberately after the
measurements pointed somewhere else. The attire half of this entry merged into
§2.14 on 2026-08-19; what is below is the EXPOSURE half, which is the one with
no owner.

**`weather.room_exposure` consults `_ENCLOSED_WORDS` only when `room.exposure`
is unset** — and `RoomDef.exposure` exists in the schema, the prompt says "give
every room an `exposure`", and it is set on **62 of 455 live rooms (13.6%,
re-measured read-only 2026-08-19; it was 8 of 289 when this was written)**. The
36-word list is deciding the other 393.

So the table is not the mechanism; it is the fallback that BECAME the mechanism
because the authoritative field is never populated. Worse, `room_exposure`
recomputes the guess from the room NAME on every read and never stores it, so a
wrong guess cannot be corrected by a host and changing the word list silently
rewrites the past.

**The proportionate fix, when it is wanted:** seed `exposure` once at commit
from the existing guess and STORE it, so downstream reads a stored fact that can
be edited; and emit a reconciliation signal when a room is created without one,
the same shape as `restraint_scan` and `unconsciousness_scan` already use. Then
the word list serves ~14% of rooms instead of 86% and its gaps stop mattering.

**Ask the same question of any other table first: is there an authoritative
field this is standing in for?** Where there is not (`_SPEECH_VERBS` parsing
model prose, `_BARRIER_ALIASES`), the table really is the mechanism and coverage
work is legitimate. The census that used to head this entry is stale and was
deleted: `world/spatial.py` is now a facade holding **0** constants.

**Rejected outright, measured with the real provider
(`perplexity/pplx-embed-v1-4b`, 2560d):** embeddings in any precision gate
("lifts her hand toward his face" vs "lowers her hand toward his face" cosine
**0.943**; "faint"/"faints" 0.784; "puts on"/"takes off" 0.612 — direction,
polarity and part of speech are invisible to cosine, and those are exactly what
`_inverted_motion_check` and `_UNCONSCIOUSNESS_CUE` turn on); embedding region
classification (nearest-exemplar 52% against the dumb `DEFAULT_REGION="torso"`
fallback at 72.5%); embedding identity matching for presences (an over-merge
welds two characters); `cheap_embed` for anything semantic (29.5%); and any
provider call inside the write lock (262 ms for one text against `core/db.py`'s
0.02 ms commit budget).


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
geometry: a body with no sensory channel is not described to a perceiver at all
(`visual_level_between` is consulted before any sentence exists, so the
composer mints no presence, pose or appearance percept for it — the guard moved
from the prose to the IR, and `_strip_unreachable_bodies` is gone with the rest
of the repair-over-prose layer), and `_subject_opener` (a leading article
belongs to the prose, not the name, so a body registered "A Dalek" is caught
when the prose writes "The Dalek's"). See `Design.md`.

**Absorbs §1.14 (2026-08-19)**, which said the same thing one body narrower —
`docs/archive/PROPOSAL_2026-08-06.md` already recorded them as one defect written
twice. §1.14's half: `director_resolve`'s passable-route backstop guards
`state_diff.positions` only when interpret DECLARED a movement, so a resolve
asserting a position on a beat with no declared movement reached commit with no
route, adjacency or authority check. Two-thirds of that headline is now paid by
`_unreachable_position_writes` (`agents/director_movement.py`, wired at
`agents/director.py`). What survives is the same unwritten rule as above, plus
the framing worth keeping: `movement` is the channel through which the player
says where they are going, and a stage that can relocate the player without it
is **authoring player conduct** — the boundary `_check_player_act_authority`
defends for speech and action, unguarded for position. The containment check in
`_guard_approach_is_not_arrival` is the start of the answer, not the whole of
it.

**Measured reach, 2026-08-19:** on turns played on or after 2026-08-01, a body's
room changed with no `movement.to_room` and no locomotion verb anywhere in the
declaration on **12.2%** of beats (91 of 745). That classifier deliberately
over-credits warrants — any locomotion word anywhere counts — so 91 is a FLOOR
and the true figure is higher by an unknown margin.


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

### 1.24 What the enclosure investigation found and did not fix

From the same live story as the enclosure fixes (`Design.md`, "A body sealed
inside another body"). These were observed in the same sweep, are real, and
were left alone deliberately — each needs a decision rather than a repair.

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

**A derived observation carries one channel for a compound sentence.** The
re-derivation assigns a single `channel` per atom, so a sentence carrying both
a sound and a scent ("breath comes in short gasps, the air thick with...") is
filed under one of them and the other becomes unattributed. Minor, and the fix
is either sentence splitting before classification or a multi-channel atom;
both are more invasive than the defect.

*(Two bullets left this entry on 2026-08-19: "one being, two names" is landed
(`world/spatial_identity.normalize_scene_subjects`; `CHANGELOG.md`), and the
byte-identical-state bullet merged into §1.10, which is where the same finding
was already written twice more.)*


### 1.27 Residuals from the speech-channel investigation

Found in the same pass. The attire-blob accumulation is now fixed (`persist/commit.py`
rebuilds `state` from `attire.flat_state` unconditionally and keeps only notes
`attire.is_derived_state_note` says were authored; `tests/
test_attire_commit_stored_shape.py`). The rest are open.

- Two `remember_lines` were dropped whole across 12 turns because the character
  cited event ids that do not exist. The guard is right to drop an ungrounded
  citation; the cost is that the line the character chose to keep is discarded
  rather than salvaged with its citation stripped. Given Phase 4a measured
  these as the highest-yield rows in the bank (3.3x baseline retrieval), losing
  one to a malformed reference is expensive.

*(Two bullets left this entry on 2026-08-19: the `manner`/`contained` bullet was
verbatim §1.28's second, and the intent-stall bullet is built —
`mind/affect.py`'s `_INTENT_STALL_AFTER = 2` sets `status="dormant"` once a goal
sits barren at its ceiling.)*


### 1.28 Residuals from the contact-sensation work

Landed 2026-08-04: `spatial.contact_sensation` and
`agents.perception._deliver_standing_sensations` (see `Design.md` § A standing
contact is a continuous percept, tests in
`tests/test_continuous_contact_sensation.py`). These are what the same
investigation found and did not close.

- **Partial interior contact still does not populate full containment.**
  Contact sensation no longer asks free-text `manner` to carry two axes:
  `relation: surface|interior` and `motion: settled|moving` now independently
  drive rendering, with backward-compatible derivation for old rows. That
  closes the perception ambiguity, but an interior contact still does not
  populate `contained`, so the §1.24 enclosure-direction work does not fire on
  it. Whether it should remains a design question: partial containment is not
  the same as being sealed inside something, and the two remain separate code
  paths describing overlapping physical situations.

  **The third path now exists and is routed** (2026-08-25). There were always
  three, not two: the ledger form (`contained`), the contact form
  (`relation: interior`), and the PLACE form -- a room whose `parent_entity`
  is the body around it. Nothing converted anything into the third, so an
  enclosure a beat declared stayed a one-line ledger entry and its occupant's
  position derived, every merge, to the holder's own room.
  `spatial.place_enclosed_bodies` closes that: a `mode: interior` record plus
  a holder that HAS interior rooms becomes a real position inside them, and
  contact hygiene admits an enclosure-joined pair so the touch channel across
  the boundary survives the move. A holder with no interior rooms is
  untouched. The migration was MEASURED rather than asserted: all 77 stored
  scenes were re-merged with an empty diff on the branch and on `main` and the
  results compared whole -- 76 byte-identical, and the one that differs is the
  story that already stands in this shape, where a surface contact between a
  body and the body it is inside now survives room hygiene instead of being
  severed. The follow-ons below are what that landing did not close.
- **The two spellings of "this room is that entity's interior" agree only for
  bodies.** `sync_entity_interior_rooms` derives `entities[eid].interior_rooms`
  from `rooms[rid].parent_entity`, and is scoped to bodies on purpose. The
  index is not only an index: `agents/director_scopes.py` gates the destruction
  specialist on it and `persist/commit_scene_state.py` folds it into the set of
  rooms the mapping stage may not prune. Measured read-only against the live
  corpus while the landing was being repaired: 53 rooms carry `parent_entity`,
  15 of them across 13 chats are NOT indexed on their entity, and every one of
  those 15 belongs to a non-body -- lift cars, turbolifts, a ship, a police
  box. Deriving them would switch a Director specialist on in five stories and
  make six stories' interiors permanently un-prunable, untested and unasked
  for. The two spellings still ought to agree everywhere; making them agree is
  a change with a blast radius, and it needs its own landing with those two
  readers tested rather than a free ride on a body-interior fix.
- **A non-body inside a place-form interior is in no view.** `contents_of`
  answers the carry ledger for anything; `interior_occupants` answers the place
  form for BODIES only, because it feeds prose that says an occupant "goes
  where you go" and because `positions` keys objects and fixtures by entity id
  -- an engine handle, which is not a name anybody in the fiction has heard.
  So a lamp dropped inside a body-place is currently in nobody's account of
  anything: the holder cannot see into its own interior (the membrane is opaque
  in both directions, correctly) and is told nothing about what is in there
  that is not a body. The fix is a percept for the objects of an interior room,
  not a widening of this one function.
- **A story-written mint never gets the card's chain, and has to grow one.**
  `replace_engine_minted_interiors` swaps the engine's own one-room mint for
  an authored chain only where that room still carries EXACTLY the key set
  `_mint_minimal_interior` writes. Anything the story has since written on it
  -- a description, a crossing time, a declared `exposure` or `size`, a second
  room -- is lived topology the card does not get to overwrite, so the
  replacement skips and the story grows its chain station by station through
  `materialize_named_stations` or the spatial specialist's `rooms` channel.
  Measured live 2026-08-25 against a scratch copy of the author's corpus with
  the card filled: chat 90's stub is replaced and its occupant advances on the
  clock from the first silent beat; chat 91's carries `exposure: "enclosed"`
  and `size: "tight"` and is left standing, correctly and permanently. What is
  missing is an author-facing way to say "this stub was the engine's guess,
  take the card's chain instead" -- a per-holder re-derive, which is an
  authoring surface rather than a merge rule and must not be a looser trigger.
- **A persona cannot author an interior.** `stamp_authored_interiors` walks
  the CAST, and a player persona is not in it, so the field is deliberately
  absent from `default_persona_data`/`normalize_persona_data` and has no
  persona accessor -- a field with no reader is what `llm/schemas.py` deleted
  29 models over. `tests/test_card_interior_spec.py` pins the absence, so a
  reader cannot appear without the field appearing with it.
- **A non-body holder never gets an engine-minted interior.** Not a taxonomy
  preference: `sync_entity_interior_rooms` and `infer_body_enclosures` are
  both body-scoped, so a minted crate or lift-car interior is never indexed
  and never defaulted opaque, `apply_transit_dock_edges` derives an
  `open_door`, and an occupant `containment_hides` was concealing becomes one
  visible from the room outside -- information EXPANSION. Serving a container
  the same way needs the non-body enclosure default first, which is its own
  landing with the bullet above it.
- **An exterior conduit declares a crossing time nothing can direct.** A room
  may now carry `transit_seconds`, and `world.spatial_containment` carries an
  occupant onward on the simulation clock -- but only inside a
  `parent_entity` enclosure, because "onward" is derived as "strictly farther
  from the way in" and the way in is `_interior_entry_room`'s `dock_exit`
  marker, which only an enclosure has. A river reach, a conveyor hall or a
  sloped chute between two ordinary rooms therefore has no derivable
  direction. The field is READ and REFUSED there with a named notice through
  `crossing_report` ("this place declares a crossing time and the engine
  cannot derive which way is onward outside an enclosure"), never a guessed
  move -- so the declaration is not silently ignored, and what is missing is
  said out loud. THE MISSING FACT IS A DIRECTION SOURCE for rooms with no
  dock marker: a per-edge `downstream` flag, or a room-level flow direction.
  Pinned by `tests/test_room_transit_clock.py`.
- **Every stored card's interior is still empty until somebody runs the
  fill.** The reader now exists on BOTH card surfaces --
  `POST /api/characters/{cid}/fill_interior` for the reusable card and
  `POST /api/chats/{cid}/characters/{ch}/fill_interior` for the per-story one
  -- and reads a card's own prose ONCE, at authoring time, proposing the
  structured chain with its magnitudes; there is still deliberately no
  runtime prose-duration parser, because one is shaped by the phrasings one
  story happens to use. What remains is that running it is an authoring act,
  and it has to be run on the card THIS STORY READS: `scene.active_cast`
  resolves `chat_chars.sheet` over `characters.sheet`, and measured read-only
  2026-08-25, 13 of 116 `chat_chars` rows carry a per-story sheet, so a story
  that has its own card is filled from the story-card editor (Cast -> ✏️
  card) and a story that does not is filled from the reusable one. 0 of the
  79 stored sheets (61 characters, 18 personas) carry a non-empty
  `embodiment.interior`, so every live story is byte-identical to before this
  landing until its author opens the card the story reads, presses the
  button, reviews the stations and saves.
- **A region the ledger names that an authored chain omits is dropped rather
  than placed.** `materialize_named_stations` gate 5: where the holder's
  inside is a card-declared chain and the occupant stands mid-way along it, a
  standing contact naming a region no station matches mints nothing, and
  `_restation_interior_contact` re-derives the ledger's region from the room
  the occupant is actually in. It is a SUBTRACTION and the alternative was
  measured worse -- on a scratch corpus copy with the card filled, the graft
  chained the omitted region DEEPER than the entry station and walked the
  occupant outward into it, where she held for fourteen beats -- but the
  region the beat named is still a fact the engine now discards. THE MISSING
  FACT IS WHERE IN THE CHAIN IT BELONGS: the card states an order and the
  ledger states a name, and nothing relates them. The author's own fix today
  is to add the station to the card, which is why this is a residual rather
  than a defect; a real one needs a way to say "between these two".
- **Two read-only Director views lag the floored clock.** A resolved beat
  that asserts no readable time is now charged `UNCLAIMED_BEAT_SECONDS`, and
  three readers of the beat's end clock apply it through
  `world.mechanics.beat_end_elapsed` -- the scene commit, the memory commit
  and the perception mirror, which are the three that decide what is STORED.
  `agents.director_floors._sleep_elapsed` and `_conditions_view` are the
  fourth reader and are NOT floored: they take `sd_time=None` on pre-resolve
  calls, so a blanket floor would be wrong there. BOUNDED: they lag by at
  most `UNCLAIMED_BEAT_SECONDS` per silent beat, and the only decision they
  gate is `_NATURAL_SLEEP_SECONDS = 28800`, which a ten-second lag cannot
  flip. Closing it needs those views given a resolved-beat flag.
- **Interior passage is undirected.** Interior stations connect by `membrane`
  in both directions, because the barrier vocabulary has no directed-passage
  value: `one_way_window`'s asymmetry is SIGHT only, and `neighbor_map`
  (`world/spatial_barriers.py`) is undirected by documented design across four
  walks. "Passable inward, and outward only on the container's own action"
  therefore needs its own vocabulary work in the `one_way_window` mould. Until
  then, going back out against the body around you is what it already is: a
  contested act for the reaction/dice machinery, not graph structure.
  Untouched by the crossing landing above and deliberately not consumed by
  it: `_onward_room` only ever walks strictly DEEPER, so it needs no
  outbound-passability fact and closing this one would change none of its
  answers.
- **A room cannot carry a hazard.** A place-form interior is exactly where "a
  place that acts on the bodies in it over time" becomes expressible -- and
  there is no room field for it, no sweep that ticks one, and no capability
  that suppresses one. Declaring `RoomDef.hazard` ahead of a reader would be a
  field nothing reads, which `llm/schemas.py` deleted 29 models over; the seam
  is registered here instead, to land with its consumer.
- **A body that regrows inside a place-form interior is not auto-released.**
  `containment_broken_by_scale_change` reads the `contained` ledger only, and
  the handoff empties it. A scale change that makes the enclosure absurd
  therefore releases nothing, and the Director/movement backstop is the only
  thing that governs the exit. The scale rule and the place form need to meet.
- **The occupied-body-is-a-place clause is English-only.** `language_packs/en`
  carries it in the spatial specialist's `rooms` chunk; the `ja` pack keeps
  the old text, so a Japanese story's specialist is not told it owns this.
  The card-side `interior_note` fragment is NOT in this class and cannot be:
  the pack loader checks every story pack's `system_prompts` card against
  English key by key, so an EN-only fragment fails the `ja` pack's load
  outright -- measured 2026-08-25. Both packs carry it, and the Japanese copy
  is a model draft like the rest of that pack.
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
- **A hover is not a contact, and there is nowhere else for it.** A measured
  "two inches of visible space" between two mouths is real fiction with real
  tension, and `contacts` can only say touching or nothing. It lives in entity
  `state`, where nothing ages it (§1.10): `_drop_contradicted_state` retires
  such a key only where a standing contact already speaks for that part, so a
  genuine hover with no contact survives unaged. A near-contact tier — or a
  `manner` that means "not quite" — would cover it. *(Moved from §3.9,
  2026-08-19.)*
- **An orphaned relational value is dropped rather than folded.** When
  `thumb_touch: "feather_light_at_ear_base"` is retired by a standing thumb
  contact, its qualifier is discarded instead of merged into that contact's
  `detail`. Folding it was rejected for now: matching the right contact by part
  name is the same guesswork the whole change exists to remove, and a wrong
  `detail` is a sentence the narrator will repeat. *(Moved from §3.9,
  2026-08-19.)*

*(Bullet 1 — "`contacts` accepts a part slot that does not name a body" — was
struck 2026-08-19: `world/spatial_contacts.py` now refuses a non-anatomical
actor_part or target_part at the commit seam, in the one place every contact
passes through.)*


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

### 1.30 The background-claims lane has fired seven times, all one way

**Updated 2026-08-18.** The entry used to read "has never once fired", and that
was true when measured 2026-08-08: 0 claims across 17 chats playing at
`scene_life=full` over 2,114 turns and 46 tracked presences. Re-measured
read-only against the live database, the lane has now produced **7 claims, all
7 ratified, 0 contradicted, 0 expired**, in one chat.

Seven is not evidence the lane works. Until `5ab591e` `_verdicts` inferred
adoption from any four-character reference appearing anywhere in the resolved
event of the beat being settled, and `background_react` runs AFTER
`director_resolve` — so the text was written before the presence spoke, every
claim settled on the beat that produced it, and contradiction and expiry could
not fire. A three-outcome design collapsed onto its one irreversible branch,
and it is invisible because ratification is the branch that looks like success.
Inferred adoption now requires a LATER beat. **The seven rows stay** (owner
decision 3): canon is write-once, and repairing persisted story data is the
owner's call. Two of the seven carry a raw engine uid as a speaker and one
establishes a DENIAL as truth.

So the fire rate still has to be measured, on a run under the repaired gate. A
lane whose only firings happened through a defect gives no chances, not a
rate.

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

Its triggers lived in a MIGRATION while `init()` skips every migration for a
fresh database, so any Sonder database created since that change had the table,
no triggers and nothing in it.

**That half is fixed, and it was never the dangerous half.** The same drift hit
`lore_fts`, which is NOT dead — it supplies the 0.35 keyword term of
`search_lore` — so every install created in that window ranked lore on the
vector term alone, scoring 0.0 for every entry, silently. All six triggers now
live in `SCHEMA` as `CREATE TRIGGER IF NOT EXISTS`, v30->v31 rebuilds both
indexes (required for correctness, not backfill: live triggers over a desynced
external-content index corrupt it on the next UPDATE), and
`TestFreshEqualsMigrated` now holds fresh and migrated `sqlite_master` equal so
the class cannot recur.

What remains here is only the removal of the dead table itself.

Found while extracting the memory model into Nullo Engine, which dropped it on
this measurement rather than porting it. Removal here needs a migration and
should confirm the rowcount is not load-bearing for anything outside the repo
first.

### 1.37 The aversive half of the stress model is live and unobserved

**Landed 2026-08-19.** `resolve_stress` weights `threat` at 0.55 and derived it
from `appraisal["goal_impacts"]`; `affect.appraise` returns the normalised list
under `"impacts"` and writes no key by that name, so the loop never ran and
threat was 0.0 on every beat of every story. Measured before: 33 characters
carried a resolved stress block, `overloaded` had fired ZERO times ever, and
strain never reached half its threshold. The channel is now an explicit
keyword-only argument (`goal_impacts=`), so the next omission is a TypeError
rather than a zero.

**It is a behavioural change and nobody has watched it yet.** Every character
in every story can now accumulate strain, and `overloaded` — strain-only, and
never once fired — can fire. The watched rows are `overloaded` and `load`: if
they now fire constantly the weights are wrong in the other direction, and the
0.55 was set against a term that was always zero, so it has never actually been
calibrated against anything. Re-measure after a run of real beats before
trusting the number.

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


### 1.40 A restore racing a mid-flight consolidation call

All that remains of the 216-second turn investigation (chat 71 turn 10). The
diagnosis, the three per-stage findings, what landed against them, and the
correction to the "empty specialists" misreading are in
[`experiments/MEASUREMENT_BACKLOG.md`](experiments/MEASUREMENT_BACKLOG.md) §3 —
they are method and measurement, not a defect.

**The one open defect.** The cancel in `restore_checkpoint` is COOPERATIVE
(between characters), so a restore arriving while one character's consolidation
LLM call is in flight can still land a summary computed from pre-restore rows,
and the cursor on that summary row then skips the window. Seconds-wide, needs a
reroll to coincide with the ~10-turn consolidation cadence, and the summary
layer is reconstructible (`backfill_memory_summary_windows` can rebuild) — but
it is a window the old synchronous design did not have, opened by moving
consolidation out of band (`schedule_memory_consolidation` → `core/jobs.py`).
Recorded rather than closed.

**Also unclosed, and it is now a lookup rather than an inference:** `narrator`
at 29.5s was attributed to the bounded rewrite ladder from code structure alone.
The per-call ledger (`_engine_notes.llm_calls`) stamps every narrator call on
the stored variant, so the next slow narrator beat answers this directly —
including whether the orchestrated path makes a rewrite MORE likely.


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

### 1.45 A dead helper family with passing tests and no production caller

**Reduced 2026-08-18.** The original entry named seven; the composer repair
closed four of them (`perception._inject_onset_sequence`,
`_inject_onset_speech`, `_strip_onset_rendering`, `_self_cannot_see_own_surface`
are gone, and `tests/test_self_surface_when_enclosed.py`'s two
`inspect.getsource` assertions on statement order inside the first went with
them in `6d843e2`). **Widened 2026-08-19: it is a FAMILY of seven, not three.** Re-verified by
grepping every non-test module — each of these has no production caller, only
the `agents/__init__.py` facade re-export and tests:

| Symbol | Where |
|---|---|
| `common._inject_visible_actor` | `agents/common.py` |
| `common._inject_action` | `agents/common.py` |
| `common._normalise_views` | `agents/common.py` |
| `common._ensure_environment` | `agents/common.py` |
| `common._fallback_perception_views` | `agents/common.py` |
| `common._perceptible_entities` | `agents/common.py` |
| `perception._deliver_foreground_body_details` | `agents/perception.py` |

So each has passing tests and no effect, which is the worst combination
available: it reads as a live floor. Six test files pin them —
`test_perception_appearance.py`, `test_perception_identity_gate.py`,
`test_enclosed_act_leak.py`, `test_player_person_discipline.py`,
`test_observable_injection.py`, `test_scene_identity_hygiene.py`.

**Three other register entries were describing behaviour inside this family and
were struck on the same reading**: §3.2 C3 (`_normalise_views` writes through an
unmatched view key) and §3.2 B4 (`_ensure_environment` does not check darkness)
are both dead paths, not live gates. `knows_identity` is the same shape one
layer over — set at six sites in `agents/perception.py` and READ NOWHERE — which
is what made §3.1 E1 unreachable.

`_inject_dialogue` and `_compose_residue_view` are the two siblings that ARE
live, both through `agents/composer.py` (and `_compose_residue_view` also
through `language_adapters/japanese.py`).

Every one of them was a repair over MODEL PROSE, and perception no longer
produces any: chronology is `Percept.order_key`, concealment is a per-percept
gate, and a rendered view is realised from percepts alone. So this is not an
oversight per symbol, it is one retirement that took its own callers with it
and left the helpers standing.

`_deliver_foreground_body_details`' two jobs appear to be superseded by the
composer IR rather than missing. The appearance half is done by
`composer.appearance_percept` → `"You see {desc}."`, which carries the same
`_appearance_as_prose` output including the `wearing:` clause. The
contradiction-stripping half looks for phrases ("no clear figure visible",
"cannot see them") that do not occur: **0 of 5,499 stored views across the
corpus contain any of them**, because the model-authored perception path that
produced them is gone.

So the likely correct change is deletion — of the whole family and of the tests
that keep it looking alive, in one commit. It is filed rather than done because it is a
judgement about design intent — whether these were meant to be deterministic
floors that were never wired — and because `agents/__init__.py` is a
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

- contact and substance clauses (`spatial_prose.contact_sensation`,
  `spatial_substance.substance_event_clause`) — these reach the view AND the
  memory episode, so they are written permanently into a non-English
  character's memory bank;
- `scene.appearance_of`'s glue (`"; wearing: "`, `"; clothing state: "`), whose
  separators are also parsed back by `story/attire.py` and `agents/perception.py`,
  so translating them breaks the readers unless all three move together;
- `story/attire.py`'s ledger phrases (`"bare at the %s"`), which are persisted and
  served raw to the attire panel — a later translation does not repair stories
  already written;
- `world/paradox.py`'s `_HAZARD_WOUND_NOTE`, appended to room notes;
- the first-person memory episodes minted in `persist/commit.py` and `world/offscreen.py`
  (`"I said …"`, `"I tried to …"`, the drive-rupture memory).

The fix is not to translate the strings where they sit: each is either
literal-coupled to a parser or persisted, so the real work is moving the
clause construction behind the compositor card and migrating what is stored.
Sized as its own change, not a follow-up patch.

**`LanguagePack.fallback` is a dead contract, and the choice is drop or
keep — not "wire or drop".** The field is parsed
(`language_runtime/__init__.py:154`), published on the pack (`:118`), and
validated to point at an installed pack (`:272`) — and no lookup anywhere
consults it. A pack declaring `"fallback": "en"` gets no fallback behaviour of
any kind. Corrected 2026-08-18: a fallback RESOLVER is unreachable by
construction, so implementing one is not an option on the table.
`installed_language_packs` refuses to load at all if a story pack is missing
any system prompt id or any card leaf path the English pack has, and refuses a
UI pack missing any source message — so the miss a fallback would answer
cannot occur while the pack is installed, and if it could occur the pack is
already rejected. What is left is a decision between deleting the field and
keeping it as a declared lineage marker with the docstring saying so.
Declared-and-ignored is the same invisible-failure shape as
`capabilities.ui.css` was, and that one shipped unnoticed for a release.

**A story does not record which pack version wrote it.** Chats stamp
`story_language` and nothing else — not the pack's `version`, adapter or
translation status. So when a pack's wording or recognition tables change under
an existing story there is nothing to reconstruct the old linguistic behaviour
from: a memory minted under `ja 0.2.0-beta` is indistinguishable from one minted
under a later revision, and a story played across a pack upgrade has beats
produced under different linguistic rules with nothing on disk saying so.
Acceptable while old pack versions are not retained, but a
`story_language_pack_version` stamp beside `story_language` is one key and would
at least make a behaviour change explicable afterwards — and it is only useful
if added BEFORE the packs start moving. *(This was written twice in this entry;
folded 2026-08-19.)*

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

*(Two bullets left this entry on 2026-08-19 — RTL acceptance and the
deliberately broad UI catalog scanner. Both are facts a pack AUTHOR needs before
starting rather than defects in a story, and are now in
[`guides/LANGUAGE_PACKS.md`](guides/LANGUAGE_PACKS.md).)*


### 1.50 Residuals from the speaking-device repair (chat 80)


The repair that keyed one presence per body, gated background speech on
personhood, and stopped `state_diff` field names becoming entities left three
things deliberately unfixed:

- **`dialogue_turns` carries no provenance.** The ledger cannot say whether a
  dialogue turn was Director-authored (the fiction voicing this presence) or
  backstop-authored (this stage voicing itself into its own future
  qualification). So chat 80's merged Scranton Reality Anchors record keeps
  the two turns the backstop should never have authored, and a kind-undecided
  presence stays `promotable` on such history. The speech gate makes the
  history inert — an undecided presence needs `routed_to_background` or
  `flow.addressed_to` to speak, and auto-promotion additionally demands
  deliberate `addressed_turns` — but splitting provenance would also let
  ambient requalification (at-post, mentioned) return for an undecided
  presence whose history is genuinely the Director's, which the uniform rule
  currently denies (a "dalek war machine" standing silent until re-engaged).
- **Not every reader of `background_presences` folds.** The gate, the stage,
  the manager roster, the promotion list and commit read through
  `_fold_duplicate_presences`; the known-name rosters in `agents/director.py`
  and `agents/perception.py` and the subject index in `world/subjects.py` read raw
  and see a split ledger until the next commit heals it. They consume name
  lists, so the cost is a duplicate spelling for at most one beat.
- **`_STATE_DIFF_SIBLING_FIELDS` is still hand-maintained.**
  `schemas.NON_ENTITY_FIELD_KEYS` is computed from the models' own
  declarations, but the hoist's sibling list is not, so a new StateDiff
  channel is refused as an entity everywhere while its hoist-up repair needs
  the list edited by hand.

### 1.51 Residuals from immutable people identity (Directive hardening §1)

The people projection (`story_view._people`, schema 3) now keys every join
and every anonymous id on immutable identity
(`docs/design/DIRECTIVE_HARDENING_REPORT.md` §1). Two things were
deliberately left. The report's §2 is NOT among them: the executable
full-pipeline correction proof is built
(`tests/test_director_correction_pipeline.py`, commit 4ede534), so both
hardening items are closed.

- **The identity ledger still speaks names, on both sides.** `known` is
  keyed by the VIEWER's name and grants name strings. So two same-named
  viewers share one knowledge row; a granted name that several roster
  members bear admits every bearer (the projection lists all of them because
  it cannot know which one the viewer actually met — correct under "decide
  nothing", but coarser than a ledger of ids would be); and a grant matching
  no roster member's current name resolves to nobody, so a viewer who knows
  only a card-authored alias gets no roster entry. The projection
  deliberately does not join card aliases: knowing a name is not knowing its
  bearer, and an alias→id join here would disclose exactly that link. The
  real fix is the ledger itself granting immutable ids, which is
  perception's change to make, not the facade's.
- **An unregistered background presence has no immutable id to ride.** Its
  ref degrades to its tracked name — honest, because that name IS its
  identity in this engine (`commit._fold_duplicate_presences` keys one
  record per body under its first-seen spelling) — so a deliberate canonical
  rename of an unregistered presence re-keys its viewer-scoped id, where a
  cast member's survives. A presence that matters enough to be renamed
  probably matters enough to promote.

### 1.52 The monolith-split audit: what is still open

The 2026-08-18 split of `world/spatial.py`, `persist/commit.py` and
`agents/director.py` required somebody to read all 24,783 lines once. Nothing
else in this project does. Everything that reading turned up was written down
and NOT repaired — a fix inside a move commit destroys the property that made
the move reviewable, which is that `git diff -M` reads as pure renames. Full
detail, each finding carrying `file:line` as of `418ab5b`:
[`experiments/AUDIT_SPATIAL.md`](experiments/AUDIT_SPATIAL.md) (F1–F16),
[`experiments/AUDIT_COMMIT.md`](experiments/AUDIT_COMMIT.md) (14),
[`experiments/AUDIT_DIRECTOR.md`](experiments/AUDIT_DIRECTOR.md) (D1–D13); repair
plan in [`design/AUDIT_REPAIR_PLAN.md`](design/AUDIT_REPAIR_PLAN.md). Each landed
row was deleted in the commit that landed it, which is why the shipped list is
in `CHANGELOG.md` and not here.

**One row is open, re-verified 2026-08-19.**

- **COMMIT-10** — `prepare_mapping_commit`'s `proposed_specifics` is a
  permanently empty payload field that teaches every mapping call about an input
  that cannot occur. `persist/commit_mapping.py` sets `specifics = []`, never
  mutates it, and sends it. No pack card mentions it, so this is a code-only
  change. **Blocked on an owner decision**: removing it changes what every
  mapping call is taught it may be handed, and a field a model is told it can
  fill is a different instruction from one it is not.

*(DIRECTOR D11 — a test asserting on `director.py`'s source layout — was struck
2026-08-19: `tests/test_style_guide.py` contains no `open(` at all; it reads
payloads through `_payloads_sent`. The class it warned about survives and is
now stated in [`guides/TESTING.md`](guides/TESTING.md) § Assertions that read
source instead of running it.)*

**Not a defect, but the honest ceiling on what the split bought.** The
functions that made these files unreadable did not get smaller — re-measured
2026-08-19 over the twelve engine roots, so this is the whole population and
not a sample:

| function | lines | file |
|---|---|---|
| `director_resolve` | 1,519 | `agents/director.py` |
| `prepare_memory_commit` | 1,270 | `persist/commit_memory.py` |
| **`character_step`** | **1,001** | `agents/character.py` |
| `interaction_loop` | 558 | `agents/loops.py` |
| `import_chat` | 541 | `persist/chat_archive.py` |
| `director_interpret` | 538 | `agents/director.py` |
| `prepare_scene_commit` | 510 | `persist/commit_scene_state.py` |

Seven functions over 500 lines, and `character_step` is the one this entry did
not previously name — the earlier version of this paragraph listed
`director_resolve`, `prepare_memory_commit` and `merge_scene_with_diff` (322
lines, reaching into nine modules). Splitting files does not split functions.

**The file-level census, recorded so it stops being rediscovered.** Measured
the same day, `engine_python_paths()` as the denominator: **116 engine modules,
8 over 3,000 lines, 21 over 1,500** — `agents/common.py` 6,838, `web/app.py`
6,206, `mind/memory.py` 5,676, `llm/schemas.py` 5,358, `agents/director.py`
3,767, `agents/perception.py` 3,637, `agents/character.py` 3,560,
`llm/providers.py` 3,283. (Counts drift by tens of lines between commits;
the shape is the point.)

This is a MEASUREMENT, not a proposal, and specifically not a proposal for a
per-file line budget. A 1,500/3,000 gate would fire on 21 of 116 files on the
day it shipped, so it would ship with a 21-entry exception list — the shape of
gate that gets waived rather than obeyed. And three of the eight largest are
already spoken for by decisions recorded elsewhere: `agents/director.py`'s
residual is Phase 2 by design
([`design/DESIGN_MODULE_LAYOUT.md`](design/DESIGN_MODULE_LAYOUT.md)),
`agents/character.py` decomposition is declined by name in §2.19, and
`web/app.py` and `mind/memory.py` are named in `CLAUDE.md` as orchestration
seams not to be broadly rewritten. The number that is actionable is the
function column above; the file column exists so the next reader does not
spend an afternoon re-deriving it and conclude it is news.


### 1.56 The project tier's occasion now arrives, and is declined

v4 made the review beat reachable (`Design.md`'s project row has the diagnosis:
one condition written twice, so the only moment a first project could be
adopted was conditional on already having one). Re-measured read-only against
the live `engine.db` on 2026-08-18, **329 turns after that fix landed**:

| | |
|---|---|
| `chat_chars` rows | 100 |
| banks carrying `interior.projects` / `former_projects` at all | 32 |
| banks carrying a `project_review` | **6** |
| banks holding a project | **0** |
| banks holding a former project | **0** |

So the fix worked and the tier still has never been used. The failure has
MOVED, not closed: it was "the occasion cannot occur", and it is now "the
occasion occurs and the character does not take it". Those want different
evidence. The candidates, none of them measured yet:

- the adoption deliberation refuses everything — it is built to refuse a task
  wearing the word, and may be refusing legitimate candidates too;
- the review beat's payload reaches the model but loses to a drive-serving want
  in the same beat, which is the exact mechanism that made the shrine lose nine
  beats running at intention weight 0.8 against 1.0;
- `project_review` fires on beats where nothing is a plausible life's work.

Do not change a gate on this until one of the three is measured. The v4 lesson
is that the previous gate change was correct and did not produce an adoption,
and a second blind change would make the two indistinguishable.

**A long phase-chain arc, measured whole (2026-08-25).** The clearest single
case the corpus holds, filed here because it is evidence for the three
candidates above rather than a fourth defect. Chat 88, char 72, 67 turns: six
sequential dynamic intentions `i1`-`i6`, each one phase of a single continuing
engagement, every one of them carrying `serves_drive: ""`. `interior.projects`
and `former_projects` are `[]` for the entire arc, and the two authored
standing intentions sit at progress 0.0 throughout. Task closings — the beats
`project_boundary` opens its review on — occurred at turns 6, 19, 22, 33, 39
and 46, and produced no adoption. The engagement itself is a project wearing a
chain of intention clothes: durable but not eternal, able to name a place,
and repeatedly re-authored as a fresh completable goal because that is the only
tier the mind could reach for.

This is deliberately NOT coded around. `docs/design/DESIGN_LONG_TERM_GOALS.md`
and `CLAUDE.md` are explicit that projects form dynamically through
`project_ops` under the adoption deliberation and that seeding is not the
authoring surface, so the candidate fix is on the invitation/adoption surface —
why six successive task-closed reviews produced no adopt — not a seeding
change. The world-closed intention floor
(`affect.settle_intent_world_anchors`, landed 2026-08-25, `Design.md`'s
conformance row) closes the STUCK TAIL of such a chain — chat 88's `i6` was
`active` for thirteen turns after the world left the station it named — but it
does not create the tier that would have carried the arc, and a closed tail
just returns the mind to forming the seventh phase-shaped intention.

**Absorbs §1.23(d) and §7's "why 3 of 31" bullet (2026-08-19) — one zero written
three times.** Do not confuse the two denominators: `tools/fire_rates.py` reports
`has ever held a project 9.68% (3/31)` across characters with any project
history, while the table above counts LIVE banks and gets 0. Both say the tier
is essentially unentered; only the second is the recent engine. The measurement
that would separate the three candidates is filed at
[`experiments/MEASUREMENT_BACKLOG.md`](experiments/MEASUREMENT_BACKLOG.md) §1 —
it is the smallest number in the corpus with the largest documented effect
(`CLAUDE.md` records projects as what made NPCs pass the maze without altering
their drives), so measure it before enriching anything in the world layer.


### 1.57 Two per-item tags in `OFFSCREEN_WORLD_COMPLETION.md` overstate what is built

`docs/design/OFFSCREEN_WORLD_COMPLETION.md` is a design note and its per-item
tags are one of the four rival status surfaces `docs/README.md` names. Checked
against source 2026-08-18; recorded here because `UNBUILT.md` is the register
and the note is argument.

- **§2 "Build crowds and persistent fixtures — BUILT (2026-08-10)"** claimed
  all five ordered steps were in the tree, and two were not. Step 1 ("a
  stationary crowd blob visible to ordinary perception") landed 2026-08-18:
  `composer.room_content_percepts` mints the crowd, the courier and the posted
  notice as `ambient` percepts from the per-observer dicts perception had been
  computing and dropping. Step 2 ("persistent location fixtures": barkeeps,
  vendors, guards, attendants, regulars belonging to a LOCATION and
  re-meetable) still has no implementation anywhere; background presences are
  scene-scoped and are a different thing. Steps 3–5 (density as terrain,
  movement/splitting, one-way emergence) are real: `world/crowds.py`'s
  `density`/`terrain`/`drift`, `advance_crowds`/`split_band`, and `emerge`.
  **So the item is still not BUILT, for one step instead of two.**
- **§5's "`offscreen_log` has exactly one reader, `gaps.interim_for`"** is
  wrong: there are three read sites — `world/gaps.py:268` (the consumer),
  `world/offscreen.py:464` (`append_offscreen_log`'s own read-modify-write) and
  `world/spatial_frames.py:906`/`1053` (frame fork and merge copying the key).
  The claim it supports — that no diagnostic surface exists to spoiler-gate —
  survives, since only one of the three is a reader in the sense meant. The
  sentence is what is wrong, not the conclusion.


### 1.59 A channel census over persisted `state_diff`s cannot see `phase_sources`

**Measured 2026-08-25**, deconstraint branch. A census of all 28 `state_diff`
channels over 2,723 resolved turns reported `phase_sources` as **never used,
not once** — and the census is structurally blind to it, not reporting a fact.
`agents/director.py:3903` pops the key IN PLACE out of `out["state_diff"]`
before the resolve step row is written, exactly as its docstring says
("consumed before persistence"), so **a persisted `state_diff` cannot carry
it**. Where it CAN be seen — `director_interpret.state_assertions` — it fires
23 times in the same corpus.

It is asked for unconditionally in `language_packs/en/prompt_policy.json` for
all six specialists and `director_resolve_lean`, and read by
`agents/common.py:485` `prune_blocked_phase_changes` at
`agents/director.py:780` and `:3903`. It is a live causal floor. Recorded here
because a later reader who repeats the census and trusts it will delete a
working one on "0 uses" evidence.

The same caution, weaker, covers `contradicted_claims` (asked for, 725 stored
diffs carry the key, 0 non-empty) and `ratified_claims` (1,876 present, 1
non-empty): both gate on `unratified_claims_present`, and
`agents/director_scopes.py`'s `_CHANNEL_GATES` granted that scope **0 times in
1,346 orchestrated Director stages**. They have not had a fair measurement yet;
§1.30 is the entry that owns them.

### 1.60 The interpret sheet and `agents/common.py` state opposite rules about concealed speech

**Found 2026-08-25**, deconstraint branch, in passing; NOT fixed here because
it is a concealment path and either direction is a firewall decision.

`prompts.director_interpret` says: *"Concealing the surrounding action
(stepping aside, opening a channel) does NOT by itself hide what is said — the
speech element itself needs its own visibility/conceal_from."*
`agents/common.py:2936-2955` does the opposite: it propagates a concealed
action's `conceal_from` onto every speech element not explicitly
`overt`/loud/shout, on the stated grounds that weak models mark the ACTION
concealed and leave the speech bare.

Both behaviours are defensible; they cannot both be the rule. A model told the
opposite of what the engine does will mis-set the field in whichever direction
it believes, and the prompt is what decides which. Settle it, then make the
loser follow the winner — do not leave the sheet arguing with the code.

### 1.58 Schema-touching work deferred by owner policy 4

The 2026-08-18 repair wave authorised **exactly one** schema migration
(`persona_carrier_state`, landed as SCHEMA_VERSION 30 — the player's carrier
envelope was the one carrier home outside `FRAME_SCOPED_WORLD_KEYS`, so what
the player witnessed in one era survived a rewind or a branch). Every other
schema-touching finding was deferred here rather than half-done, on the
principle that a migration deserves its own pass, its own testing and its own
release. This entry is that paperwork. Each row below is CONFIRMED against
source; none is speculative.

The checklist every one of them owes is `docs/guides/DATABASE.md` §
"Schema-change checklist" — eight steps, and the ones that actually bite here
are 4 (export/import payloads), 5 (checkpoint snapshot AND restore) and 6
(branch/clone id remapping in `web/app.py`). A frame-scoping change owes one
more that the checklist does not name, because it is specific to this engine:
**a bare `wget` redirects on the AMBIENT frame and is the caller's era only by
accident**, so every read site has to be re-examined for whether it wants
`wget_for_frame` with an explicit frame, not merely left alone.

- **PERSISTENCE-F17 — three world keys are not frame-scoped while seventeen
  siblings are.** `world_pressures` (`persist/commit_ledgers.py:150,227,299`),
  `background_claims` (`world/background_claims.py`, six sites) and
  `engine_notices` (re-verified 2026-08-19: `agents/director.py` reads it at two
  sites, and the WRITERS are `persist/commit_mechanics.py`,
  `persist/commit_destruction.py` and `persist/commit_scene_state.py` — the
  last was missing from this row)
  are plain `wget`/`wset`. So a pressure raised in one era, a claim ratified in
  one era and a notice raised in one era are all visible from every other era,
  and a rewind does not retract them. Adding a key to
  `FRAME_SCOPED_WORLD_KEYS` is not itself a migration — the scoping is a key
  rewrite at the storage layer — but the EXISTING rows keep the unscoped key
  and would go silent on the next read, so the data migration (re-key each row
  to the era that wrote it, or to the ambient frame) is the work.
- **RUNTIME-11 — `world_conditions` has no `frame_id`.** Same shape, different
  storage: this is a real column on a real table (`core/db.py:716`), and
  `story/scene.awareness_conditions` queries `WHERE chat_id=? AND
  kind='awareness' AND active=1` with no era filter at all. A character
  knocked unconscious in one era is unconscious in every era of that chat.
  `world_events` already carries `frame_id` as an explicit FK, so the shape to
  copy exists; the migration is the column, the backfill, and the
  `world_conditions` readers.
- **PERSISTENCE-F15's gate half.** The writers half is not deferred and landed;
  moving `_backfill_resource_uids` behind the version gate bumps
  `SCHEMA_VERSION`, so it waits for the same pass.
- **PERSISTENCE-F5's drop half.** The three deprecated macro-geography tables
  (`fiction_worlds`, `fiction_locations`, `transit_edges`). The doc correction
  landed; dropping them is a schema change. `transit_edges` is the cheap one —
  nothing snapshots, exports or restores it, so there is nothing to migrate.
- **RUNTIME-6's stored-data purge.** The write-side fix landed — the
  `candidates` payload is no longer persisted with each step. The
  already-written payloads remain: measured read-only on the owner's install
  2026-08-18, **590 variant rows carrying 7.16 MB of `candidates`**. A purge is
  an UPDATE over live stories' saved steps, which is why it is here and not in
  a tidy-up commit. That number GREW between the audit (4.9 MB) and this
  measurement, which is the argument for doing it rather than against: the
  write side is fixed, so the cost is now fixed too and will not grow again.
- **The four dead settings keys** — §1.51b, kept there because the diagnosis is
  there. Listed again here because the repair is the same kind of thing: a
  migration that deletes rows from live stories at next launch.


### 1.60 `generalization_tags` promises a mechanism that does not exist

`AssociationProfile.generalization_tags` (`story/character_schema.py:225`) is
normalized, editable (`static/js/components.js:745`), archived with the sheet,
and serialised to the character as prose inside `learned_associations`. What it
is NOT is a generaliser: nothing deterministic reads it, and
`psychology_runtime.apply_association_updates` moves `appraisal_bias`,
`response_tendency` and `strength` and never touches this one. So a tag an
author writes is a note to the model, and a tag the runtime could have LEARNED
never appears.

Kept rather than deleted, and the measurement is the reason: read-only on the
live database 2026-08-18, **all 78 authored associations carry tags, and 87 of
the 152 in the interior ledgers do**. Deleting the field discards authored work
in three quarters of the places it exists. The choice — build the generaliser,
or withdraw the promise the field's NAME makes — is an owner's, and either way
`static/js/components.js` is the other half of whichever answer wins. Audit
MIND-F16.

### 1.61 Half the prompt ids are outside the prompt/schema drift check

`tools/project_check.py`'s `check_prompt_schema_ops` exists because the same
defect landed three times in two days — a prompt asking for an `_ops` field the
stage's model does not have, so Pydantic drops every op silently (`project_ops`
cost an entire tier of psychology: "has ever held a project: 0 of 14 banks").
It iterates `schemas.SCHEMA_MAP` plus `PROMPT_MODEL_ALIASES`.

Measured 2026-08-18: **21 of 41 prompt ids are inside the check and 20 are
outside it**, and they are outside STRUCTURALLY rather than by oversight —
there is no Pydantic model to check them against, because their outputs are
consumed as raw dicts. The twenty: `ambience_prompt`, `artifact_wording`,
`fill_appearance`, `fill_character_psychology`, `generator_character`,
`generator_greeting`, `generator_lorebook`, `generator_lorebook_entries`,
`generator_persona`, `import_character_reinterpret`,
`import_persona_reinterpret`, `lore_reinterpret`, `memory_consolidate`,
`offscreen_agent_adjudicate`, `offscreen_agent_attempt`, `offscreen_profile`,
`patch_json_field`, `position_resolver`, `promote_character`, `repair_json`.

The generator group is the sharp one: `book_ops`, `link_ops` and `entry_ops`
are asked for by name in those prompts and opened as raw dicts on the other
side, which is exactly the `entry_ops`/`entries` defect the check was built
for, sitting where the check cannot see it. **Blocked on an owner decision** —
"how should the generator prompts be typed" is an API-shape question about
`llm/schemas.py`, not a checker change, and typing them is what makes the
checker cover them for free. Audit TOOLS-S3.

### 1.62 An extra player has no opening turn

Two halves of one repair, in two files, both confirmed 2026-08-18:

- `agents/runtime.establishment_plan` is a fixed five-step list
  (`mapping_stage`, `director_establish`, `perception_establish`, `narrator`,
  `commit`) and never appends `narrator_extra`, which `build_plan` does append
  on every normal turn when the chat has extra players in this frame.
- `agents/perception.perception_establish` builds perceivers for `"player"` and
  for each cast member, and no `extra:<pid>` perceiver at all — `perception_act`
  and `perception_outcome` both do (`agents/perception.py:2051`).

So a co-player attached before the story opens receives no view of the opening
scene and no render of it; the first thing they see is turn 1. Nothing warns —
the plan is simply shorter. `agents/narration.py:1119` already reads
`establish_views.get(f"extra:{pid_key}")` before falling back to the outcome
views, so the narrator half is waiting for a key nothing writes, which is why
this reads as built until you go looking for the producer. Audit RUNTIME-4.


### 1.65 A condition subject written as a scene uid names nobody

Found while landing restraint and awareness exits
([`DESIGN_RESTRAINT_AND_AWARENESS_EXITS.md`](design/DESIGN_RESTRAINT_AND_AWARENESS_EXITS.md)
§ Residuals). `world_conditions` rows in chats 24 and 25 carry a **subject
written as a scene-entity uid**, which matches no perceiver's display name —
so those rows are inert under any selector, including the widened ones, and
the gate they describe has never fired for the body they describe.

This is not created by the kind widening and is not fixed by widening
further: chat 26 holds a canonically-spelled `awareness` row with the same
uid-subject shape and is equally inert. The two faults look alike from the
symptom (a condition that does nothing) and are unrelated at the cause — one
was a vocabulary the reader did not recognise, this one is an IDENTITY the
reader cannot resolve.

The fix is identity folding — `same_subject` / `normalize_scene_subjects`
territory — applied to condition subjects, so a uid and the display name it
belongs to are one subject. It is its own change with its own tests because
folding `world_conditions` subjects touches the commit path, the restore
path, and branch/clone ID remapping, which is the checklist in
[`guides/DATABASE.md`](guides/DATABASE.md) rather than a predicate edit.

Three smaller residuals from the same note, deliberately not landed with it:

- **One metaphorical `_RELEASE_CUE` false positive** ("breaks free of her
  paralysing fear") and its mirror class (a possessive object like "pulls
  Hinami's file free", unreachable today only because the apostrophe breaks
  the cue's lookahead chain). Both need noun semantics a regex does not
  have; the cost is a warned, recoverable ending, and prose saying a
  physically-restrained body "breaks free" is nearly always literal.
- **Restraint synonym and holder-field tables are English** — the same
  standing gap `_RESTRAINT_SYNONYMS` had before that work. Owner decision 2
  (route recognizers through the packs) covers the class.
- **`consciousness` rows stay unread forever** by design: the word does not
  say which way the body is crossing. If a model starts writing them at
  volume the fix is the prompt, not the predicate.

### 1.66 The story column's floor overrides the room it reserved

`syncVitalsGutter` (`static/js/settings.js`) computes `--story-width` as
`clamp(STORY_MIN_WIDTH, shellWidth - 2*reserve, STORY_MAX_WIDTH)`, where
`reserve` is the widest float that has to sit beside the column. The
reservation is correct and the clamp silently defeats it: when
`shellWidth - 2*reserve < STORY_MIN_WIDTH` the column is pushed back up to 720
and the float it was making room for lands ON it.

Found by the browser suite 2026-08-19, the first run after the CI job stopped
being skipped: at a 1400px window the reservation asked for a 650px column, the
floor forced 720, and the ambience controls sat **27px inside the input box** —
over the right-hand end of the field being typed into.

**The instance is fixed and the class is not.** The container queries that shed
the slider and then stop floating are now derived from the cluster's measured
widths (`static/styles.css`, `@container composer`). The same hole is open on
the LEFT: `VITALS_MIN_GUTTER + 12` is 198, so a shell narrower than
`720 + 396 = 1116` with the tracker visible reserves room the clamp then
refuses to give, **and nothing reports it**.

Two shapes of real fix, neither taken: let the column go below
`STORY_MIN_WIDTH` when a float genuinely needs the room (readability loses to
not-overlapping), or make the floats' own container queries the single
mechanism and drop the JS reservation (one mechanism instead of two that can
disagree). The second is closer to how the ambience cluster already behaves.
Whichever wins, `browser_tests/test_ui_smoke.py` holds the invariant and should
gain a tracker-side case.


### 1.67 Subject spellings outside the scene blob are not folded

**Landed 2026-08-19**, to
[`DESIGN_SUBJECT_SPELLING_AUTHORITY.md`](design/DESIGN_SUBJECT_SPELLING_AUTHORITY.md):
a registered cast character's canonical spelling is the SHEET's
`identity.name`; every other being keeps the scene entity's own `name`.
Enforced by `common.reconcile_cast_entity_names` at both Director stage bodies
and on both sides of the merge at commit, so the cast-free merge fold reads an
entity record that is already right. `common.cast_spelling_policy` is the one
table both hand-rolled copies now call, the alias fold is reachable for a
name-keyed entity, and `orientation` joined `_SUBJECT_KEYED`. Measured on the
live corpus: 4 entity records renamed (chats 27, 65, 81, 82), 8 scenes healed,
21 ledger keys folded, 62 of 70 scenes byte-identical.

What is NOT folded is every durable store OUTSIDE the scene blob that holds a
subject spelling — `world_conditions` (§1.65, the same gap with its own commit,
restore and branch/clone exposure), `subject_last_seen`, and the
background-presence recognition ledgers. Each is a read-side consumer that
already resolves through identity or must learn to; rewriting them is per-store
work with its own `DATABASE.md` checklist, deliberately out of scope of the
scene fold. Close §1.65 next, citing that note for direction.

Two smaller residuals from the same landing:

- **`canonicalize_positions` still refuses aliases**, and correctly:
  `positions` keys objects and unregistered presences beside people, so a
  generic alias ("The Oncoming Storm") could name a genuinely separate entity
  and folding it would move an object into a person. It is now a stated
  `aliases=False` on the shared policy rather than a second table, but the
  underlying question — how to tell a person's alias from an object's name
  without the scene in scope — is unanswered, and it is why the entity
  reconciliation exists.
- **Two entity records for one character are left alone** by the
  reconciliation, because renaming both would mint the duplicate key
  `_dedup_duplicate_entity_keys` exists to collapse. That is a merge defect
  with its own owner; the pass declines rather than racing it.

### 1.68 A barrier's appearance, and knowing how it works, are both in the room note

**Landed 2026-08-19:** a `one_way_window` declared from both sides is a
contradiction, so sight subtracts in both directions and the pair is reported
once per chat — to the developer as a warning and to the Director as an engine
notice naming the blind side it must declare. `sight_contradictions_told` makes
a scene that was ALREADY contradictory before the check existed get told once
rather than never.

The subtraction is a holding position with a known cost: the watching side
loses a view it should have had until somebody names the direction. It is
accepted because a gap plays wrong obviously and the notice says what to fix,
where the leak it replaces — chat 82's restrained subject watching her
interviewer through a mirror her own room note called opaque — is not noticed
until it has been true for fifty beats.

**Also landed 2026-08-20, the structured strand:** `spatial_digest` rendered
each adjacency edge identically to both rooms it joins, so the blind side was
handed the far room's name and the word `one_way_window` in the narrator's own
`spatial_frame` — the middle and bottom rows of the table below, arriving
through the payload rather than through a room note. Chat 78 t3: a restrained
player whose whole perception output was two PA lines was narrated a figure
"beyond the one-way window". The edge is now dropped from the digest on the
side it is a wall from; the watching side is unchanged.

**The open half is that one physical object is described in three registers and
the engine only has one place to put them.** Owner's statement of it, 2026-08-19:

> Sarah should know that the glass is one way... but not by looking at it, yes
> she can see through it on her side... but she only knows it's one way from
> prior info.

Three different questions, three different homes, and today all three live in
`rooms[x].notes`, which is authored once and served to everyone standing in the
room:

| question | where it belongs | today |
|---|---|---|
| who can see through it | the edge barrier, directional | the mutual declaration cancels it |
| what it LOOKS like from each side | edge-scoped prose, delivered per side | one note per room, so both sides get both |
| *knowing* it is one-way | the character's knowledge — a briefing, a memory | the note, so the subject is told too |

Chat 82 shows all three failing at once. The cell's note reads "The mirrored
side of the two-way glass offers no visibility to the annex" — a statement
about the FAR side's optics, handed to the woman restrained in the cell, who
has no channel to it. Standing beside a mirror is not a channel to how the
mirror works. Two sentences later the same view says she sees the annex and
everyone in it, because the geometry disagreed with the prose.

The fix is to move barrier prose onto the edge, where it can be rendered per
side, and to leave "it is one-way" out of the scene entirely — it is prior
knowledge, and the engine already has knowledge records. That is a schema
change (owner policy 4, §1.58) plus a migration for every scene whose barrier
prose currently sits in a room note, which is why only the deterministic half
landed. Until then a room note may still tell an occupant something the room
does not show, and no guard reads prose well enough to catch it.

### 1.69 Three other sentence splitters still have no abbreviations

**Landed on 2026-08-19 for the three splitters in `agents/`.**
`common.split_sentences` rejoins a fragment whose predecessor ends in a
`_SENTENCE_ABBREVIATIONS` token (language-pack data, because "a period may end
an abbreviation" is a fact about a writing system), and `_sentence_subjects`,
the perception redactor and the two narration fidelity checks all route through
it. `_subject_opener` gained the matching admission: a title standing
immediately before a name opens that name's sentence.

**Still splitting on a bare period, and there are THREE, not four** (title
corrected 2026-08-19; the body always said three): `common._VIEW_SENTENCE_SPLIT_RE`
(the view deduper — a different contract, its split keeps the separators
interleaved), `dressing/backdrops.py` and `tools/perception_retrieval.py`. **None
of them decides what a mind receives**, so none can produce the chat 82 failure;
they can only mis-count a sentence. Watch item, not a defect.

The token set is deliberately not every abbreviation — "etc." and "Ph.D."
genuinely end sentences, and rejoining there welds two real ones together. It
holds the class that essentially never ends a sentence and does routinely
precede a NAME, which is the shape that made the split damaging.


### 1.71 `nature` is the designed answer and it is almost never asked

`BlurbMintEntry.nature` (`llm/schemas.py`, `PRESENCE_NATURES = person | thing |
voice`) exists precisely so the engine stops deriving animacy from a noun the
model chose in passing. Its own docstring calls that "an enumeration
treadmill": `_INERT_ENTITY_KINDS` reached 50 entries and
`_ANIMATE_ENTITY_KINDS` 35, "and a kind string still cannot separate a
suppression device from a dalek war machine."

**It is only answered on the `scene_life` path.** `background._mint_blurbs`
runs over MANAGED presences, which exist under `scene_life: ambient|full`; at
the default level no presence is ever asked what it is. Measured over the live
corpus: **not one tracked presence carries a `nature`**, so every consumer
falls through to the graded guesses, and 16 of them land in `undecided` — 14
machines and 2 Daleks, exactly the pair the docstring says a noun cannot
separate.

Two gates now read that verdict, and they read it with opposite conservatism
because they ask different questions — may this thing act (silence is cheap)
versus is this name protected (a wrongly-protected name renders a machine as
"the unfamiliar person" in the room's own description). The identity floor
settles `undecided` on CONDUCT, which separates the live corpus perfectly and
is honest about what it cannot see: a genuine person who has never spoken and
whose kind is neither animate nor inert.

The fix is to ask the question. Either widen the blurb pass to every newly
tracked presence — it is one batched call per room, and the answer is frozen
once — or ask the Director for it at entity creation, which is a schema change
(owner policy 4, §1.58). Until then the answer is inferred, and the inference
is documented rather than reliable.

### 1.72 `placement` and `add[].covers` are documented, passed, and inert

Found wiring §2.14's guessed-span report (2026-08-19). Both prompts tell the
Director where to say a garment is worn when the name does not imply it —
`add:[{name:'linen shirt',covers:['legs','groin']}]` and
`placement:{'<garment>':['<region>',...]}`, with the reasoning spelled out
("underwear on the head, a belt across the chest, a shirt worn as trousers…
the variations have no end and no word list reaches them"). Neither works
through the commit path.

`story.attire.apply_flat_change` honours `placement` perfectly — called
directly with `({}, ["nagajuban"], placement={"nagajuban": [...]})` it returns
`torso, legs, groin`, each garment stamped `placed: True`. `commit_attire`
passes the same argument at the same call (`persist/commit_attire.py:845`,
`placement=d.get("placement")`), and the stored result is **torso alone**.

The cause is ORDER, not plumbing. The `add` loop puts the garment into
`cur["wearing"]` first; `_before = attire_model.normalize_regions(cur)` then
DERIVES its span from the cue tables before `placement` is ever consulted; and
`apply_flat_change` finds the garment already placed and leaves it where the
tables put it. The authored answer arrives after the guess has been made and
loses to it.

No test covers the surface end to end — searching `tests/` for `placement`
finds only `displacement`, an unrelated feature whose name contains it, which
is how a documented authoring channel stayed inert without a single red run.

Not fixed here because the fix is a reorder inside a function with a long
measured history (the decisive-removal rule, the steal guard, the shed-object
minting and the region derivation all read `_before`), and it wants its own
pass with the ordering stated as an invariant: an AUTHORED span is not a guess
to be improved, so it must be applied before anything derives one. Until then,
`guessed_spans` reports these garments — which is the right report, since
nothing did in fact know where they go.


### 1.73 The chronological-padding brake stops the inner loop only

Found 2026-08-20 by adversarial verification of the memory-probe harness.
`search_memories` pads its selection with chronological neighbours of the top
3 selected episodes, documented (MEMORY.md §5, and the in-code intent) as "up
to k+2 total" — but the `len(expanded) >= k + 2` brake sits inside the inner
neighbour-pair loop and never breaks the outer `selected[:3]` loop, so the
payload can reach k+6; k+4 was observed live on both measured banks. Present
since before the 2026-08 retrieval work (equal at the frozen-probe baseline),
and measured as deciding nothing: zero probe verdicts on any bank in any
state came via padding rows. Not fixed in the branch that found it because
shrinking payloads is a retrieval behaviour change that needs its own probe
run; the fix is moving the brake to the outer loop (or checking it before
each append) and re-measuring with `tools/memory_probe_harness.py`.




### 1.74 A memory import carries the other story's persona verbatim

Found 2026-08-19 while theorizing the pre-story tier
([`design/DESIGN_PRESTORY_MEMORY.md`](design/DESIGN_PRESTORY_MEMORY.md)).
`import_character_memories` (`mind/memory_snapshot.py:374`) is the additive
path behind `POST /api/chats/{cid}/characters/{ch}/memories/import`, and it
copies `content` from the export straight into the new chat's bank. Every other
cross-story read scrubs the previous story's player handle through
`player_handle_for`; this one does not, so importing a bank moves one player's
persona name into another player's story as fact a mind can recall. That is the
plain shape of a firewall leak: a mind acquires a name it has no channel to.

Two smaller faults in the same function. `archived` is not in the prepared
dict, so retired memories come back alive on import. `frame_id` is never set,
so it falls through to whatever the ambient contextvar happens to hold at
import time rather than to the frame the host is importing into -- the same
class as the B5 thread-pool defect in
`tests/test_fable_audit_memory_consolidation.py`, which was fixed by passing
the value explicitly instead of trusting the ambient default.

Dropping `turn_id`/`turn_idx` is NOT a fault -- the docstring argues for it and
the argument holds. It is what makes this function the engine's existing,
unlabelled `inherit` mode for memory, which is why §2.20 begins from it rather
than from a blank page.

### 1.75 A batch refused for being too large degrades instead of splitting

Found 2026-08-19 while building the LongMemEval converter, which hit it twice
before it was understood.

`_embed_with_retry` (`llm/providers.py:3236`) sends whatever list it is handed
and, on any exception, replaces the WHOLE batch with crc32 hashes stamped
`cheap:crc32:256`. Nothing anywhere chunks by request size. The embeddings
provider caps a request at 120,000 tokens, and that cap is nowhere in this
codebase.

The retry makes it worse rather than better. A 400 for oversized input is
DETERMINISTIC -- it fails identically on every attempt -- so the retry ladder
spends its budget proving a fact it already had, and then degrades, when the
remedy was available from the first failure. The distinction the engine is
missing: **a request refused for being too large is a batching failure, not a
provider failure, and the answer is to split it, not to hash it.** A rate limit
or a dropped connection genuinely warrants degrade-after-retry; this does not.

`rebuild_embeddings` is safe by accident and by design: `_REBUILD_BATCH = 32`
keeps requests small, and it explicitly refuses to write a fallback over a real
vector. `prepare_memories_batch`/`add_memories_batch` (`mind/memory_write.py`)
have neither guard -- one `embed_texts_meta` call for the entire list, and the
write proceeds on whatever comes back.

That puts the exposure on `import_character_memories`, whose list size is
whatever the host's export file holds. Measured against the live corpus at
1.5x content length over four characters per token, which is a floor rather
than an inflation because the cue text is shorter than the document:

| bank | rows | content chars | est. request tokens | over the cap |
|---|---|---|---|---|
| 63/35 | 657 | 340,595 | 127,723 | YES |
| 64/35 | 657 | 340,012 | 127,504 | YES |
| 59/35 | 654 | 339,843 | 127,441 | YES |
| 38/35 | 572 | 285,306 | 106,989 | no |

So exporting the largest character in the corpus and importing him into a new
story returns `{"ok": true}` and produces a bank that is keyword-only --
`cheap:crc32:256` measures 0% paraphrase recall (MEMORY.md section 4). The
failure is one WARNING line in a log nobody reads during an import, and the
symptom arrives later as a character who cannot recall anything unless the
words match. This is the same function 1.74 is already filed against, and it is
the path 2.20 would build on.

Two fixes, and the first is not optional if the second lands: split on a token
budget before the request rather than after the refusal, and refuse to WRITE a
fallback batch nobody asked for -- the rule `rebuild_embeddings` already
states in its own docstring, applied to the batch writer that lacks it.

### 1.76 `recall_confidence` measures distribution shape, and absence has the same shape as presence

Measured 2026-08-19 against LongMemEval (MIT), the first retrieval instrument
whose questions nobody on this project wrote
([`experiments/AUDIT_MEMORY.md`](experiments/AUDIT_MEMORY.md) asked for one;
`tools/longmemeval_to_bank.py` builds it). 10,960 rows in one bank, 470
positive probes and **30 negatives whose answers are absent by construction**
-- twice the hand-authored negative set that
[`experiments/MEMORY_IMPROVEMENTS.md`](experiments/MEMORY_IMPROVEMENTS.md) §5
could offer, and independent of this engine.

Two results, and the second one is the entry.

**The threshold does not survive scale.** Holding the query AND its target rows
fixed and growing only the distractor mass (so nothing about the question or
its answer changes):

| rows | hit rate | median lift | min lift on a hit | negative median |
|---|---|---|---|---|
| 500 | 100% | 3.708 | 3.098 | 2.654 |
| 1,000 | 100% | 4.702 | 3.852 | 3.379 |
| 2,500 | 100% | 5.769 | 4.597 | 4.389 |
| 5,000 | 100% | 6.204 | 4.943 | 5.127 |
| 10,960 | 100% | 7.086 | 5.526 | 5.934 |

The same question with the same answer scores nearly twice the lift purely
because the bank grew. `_RECALL_ABSTAIN_LIFT = 1.7` was calibrated where lifts
ran 1.724-2.3, on banks of at most 657 rows. At 500 rows on this corpus even
the NEGATIVES score 2.654. A z-score against the bank's own distribution is
scale-dependent by construction, so an absolute sigma threshold cannot hold
across bank sizes -- and a thousand-turn story is the case the signal was
built for.

**And recalibrating cannot fix it, because the negatives drift at the same
rate.** Positives climb 1.9x across the sweep, negatives 2.2x. The gap between
"the answer is in this bank" and "the answer does not exist anywhere" stays at
roughly ONE SIGMA at every scale and never widens. Over the full 500-probe run
the two populations overlap almost entirely: positives median 6.197 (min
3.555), negatives median 5.934 (min 4.249). True abstention on the shipped
threshold: **0 of 30**. False abstention: 0 of 399, which is only reassuring
until you notice nothing fires at all.

The reason is structural rather than numerical. A query whose answer is absent
still retrieves topically related rows and still produces a peaked distribution
relative to the bank mean. Presence and absence have the SAME SHAPE; only the
CONTENT of the top rows differs, and a statistic over scores cannot read
content. MEMORY_IMPROVEMENTS.md §5 reached the edge of this from the other
side -- "sharper teeth need row-level evidence... not a better threshold" -- and
this is the measurement that closes it.

**Its one production reader is gone, 2026-08-20.** It annotated the character
payload with `nothing_comes_back_clearly`; that call is removed, which also
removes a second full bank scan per character per beat. Nothing replaced it,
so **the engine currently has no abstention signal at all** -- a mind is never
told its own recall came back empty. That is a deliberate absence rather than
an oversight: the statistic fired 0 of 30 times, so removing it took away
nothing that ever happened.

The row-level replacement was attempted the same day and is unmeasured. A
reading pass over the top-k (`mind/memory_judge.review_recall`) answers the
question properly, but the arm that would price it -- 470 positives and 30
negatives -- was abandoned at 3 of 90 after two invalid runs and roughly two
minutes per call. **The number that matters is FALSE abstention**: a positive
probe the reviewer calls empty is a mind told it does not remember something
it does, which would be strictly worse than an inert statistic. Until that is
measured, do not wire it.

What survives: the signal fails open, and it has never falsely suppressed a
real recall in any measurement. So it is inert rather than harmful, and there
is no urgency to remove it. What it must not do is be trusted, cited as an
abstention mechanism, or extended to another lane. The honest replacements are
row-level (a cross-encoder or an entailment check over the top-k, which reads
what the rows SAY), and the honest interim is to stop calling this an
abstention floor.

Related: 2.16 records the floor as the surviving half of that entry and should
be read with this beside it; 2.20 notes the separate reason the signal cannot
fire early in a story (`_RECALL_CONFIDENCE_MIN_BANK = 40`, which the median
bank does not reach until turn 10).

### 1.79 Four readers spell the same tolerant ledger lookup

`story.attire.entry_for` is the shared casefold-tolerant lookup of a body's
attire entry, added because `scene.visible_body_text` did a bare `.get(name)`
and a case-variant identity key therefore found no garment for a dressed body
— a gate that failed OPEN, delivering the face a covering conceals. Three
inline copies of the same fallback remain in `agents/common.py` (around the
`observer_body_regions`, region-coverage and per-body ledger reads). They are
correct today and independently maintained, which is the same second-copy risk
`_co_present_company` was just collapsed to remove. Adopting `entry_for` at all
three is pure subtraction and wants no design decision.

The key is unreliable in the first place because
`persist.commit_attire._heal_attire_identity_keys` heals on the WRITE path and
nothing heals on the read path. Healing on read, or canonicalising the key at
one boundary, would retire all four call sites rather than unify them.

### 1.78 One authored body field reaches no reader

**Found:** the same beat, asking why the same engine renders one body richly
and another thinly.

`character_appearance` (`story/character_schema.py:1447`) and
`persona_appearance` (`:1690`) return `embodiment.visible.summary` and nothing
else. `visible.build`, `visible.face`, `visible.hair`, `visible.eyes` and
`visible.distinctive_features` are offered in the card editor, normalized,
persisted, archived — and read, outside `character_schema` itself, by exactly
one thing: `_prose_names_a_part`, a card-warning heuristic. No view, no
narrator, no memory ever receives them.

So how a body renders is decided by which field its author happened to fill.
Measured on one pair: Mirelle's summary is a full paragraph and she arrives
with skin, hair, eyes, horns, tail and wings; Hinami's summary is "A young
woman appearing in golden fox ears and six golden tails." and her equally
detailed `build`/`face`/`hair`/`eyes` reach nobody.

`_coerce_appearance` (`:963`) already folds these fields into the summary —
but only from `embodiment.<key>`, where an older sheet MISPLACED them. A card
that puts them in the correct place, `embodiment.visible.<key>`, is the one
that loses them. Either compose them the way the misplaced ones are composed,
or stop offering fields the engine does not read.

**Four of the five landed.** `build`, `face`, `hair` and `eyes` are delivered.
`_coerce_appearance` projects the located three into
`embodiment.visible.regions.head.visible_zones` on every normalize — no new
authoring surface, no re-authoring, and one correct answer per field — and
`attire.uncovered_zone_text` gates them on the mirror of the `beneath` rule:
delivered until something covers the region, delivered again when it comes off
or is pushed aside. `build` is not located, so nothing worn can cover it and it
rides beside the summary. Delivery is on the description path only
(`perception._body_descriptions`), behind the sight and arc gates that were
already there, and the stranger LABEL still comes from the summary alone so an
observer holding a silhouette gains nothing. See `Design.md`.

**`distinctive_features` remains.** It is offered in the editor, kept through
every normalize, carried in archives, and read by exactly one thing —
`_prose_names_a_part`, a card-warning heuristic. It is also the natural source
for the stranger descriptor that `observer_display_map` currently cuts from
`visible.summary`, so the field literally named "what distinguishes this
person" is not used to distinguish them. `character_card_warnings` says so, on
every card-producing surface.


### 1.79 What the Living World audit found

**Found:** the 2026-08-24 survey behind `docs/guides/LIVING_WORLD.md` — eleven
agents over `world/living_world.py`, `world/offscreen.py`, the twenty-nine
`charter_*` modules, background life and the lifecycle paths. The guide states
the behaviour; these are the places the behaviour is wrong.

**Defects.**

- ~~**The string `"false"` opts a character INTO paid off-screen ticks.**~~
  **Landed.** `character_schema.authored_bool` reads the word a human wrote,
  both card readers use it, and `character_card_warnings` tells the author
  that whatever produced the sheet is not writing booleans. Original finding:
  `character_offscreen_agent` applies `bool()`, and `bool("false")` is `True`.
  The legacy branch applies the same `bool()`, so neither path is safe
  (`story/character_schema.py:1166`, `:1400`). An imported or hand-edited sheet
  carrying `"offscreen_agent": "false"` buys model calls. The card default is a
  real boolean, so this reaches only sheets that have been through a text
  editor or a lenient importer — which is exactly where it will not be noticed.
- ~~**Two `cap=0` off-by-ones**~~ **Landed** — both now bound before they
  append, matching `profile_candidates`, which already did. Original finding:
  `full_agent_candidates(cap=0)` returns one candidate
  (`world/offscreen.py:1338`) and `fired_consequences_at(cap=0)` returns one
  item (`world/living_world.py:463`). Unreachable from today's callers, which
  guard `cap <= 0` first; inherited by any new caller. `profile_candidates`
  has the correct shape beside one of them (`:1399`).
- ~~**Charter diagnostics leak across frames.**~~ **Landed** —
  `charter_runtime._event_frame` filters the listing to the requested era, in
  Python because `scheduled_events` has no frame column and the scoping rides
  in the payload. Original finding: `charter_diagnostics` selects
  `scheduled_events` with `seed LIKE 'charter:%'` and no `frame_id` predicate
  (`world/charter_runtime.py:1161`), so the diagnostics surface for one era
  lists charter events minted in every era of the chat — unlike `registry_for`
  beside it, which is frame-scoped.
- **Frame split and merge drop Charter and off-screen state.** A split seeds
  the away frame from seven parent keys and `charters`, `offscreen_epoch` and
  `offscreen_plans` are not among them (`world/spatial_frames.py:844`); a merge
  reconciles four keys, so nothing a Charter, a plan or a standing intention
  did in the away frame comes back (`:998`). Whether that is a defect or a
  deliberate severance is undecided — it is undocumented either way, which is
  the part that is certainly wrong.
- **`pick_background_reactors` has no room filter.** `here` is computed and
  used for only two of the eight qualifying signals
  (`persist/commit_background.py:1541`), so a presence with dialogue history in
  a room the player left ten turns ago still qualifies and can be picked.
  `managed_presences` DOES filter by ambient scope
  (`agents/background.py:553`), so the two paths disagree about co-presence.

**Untested.** No test in the suite covers Charter, Living World or off-screen
state across archive, branch or checkpoint. The coverage is real — every table
and key involved is in `chat_archive.WORLD_TABLES` and
`checkpoints.snapshot_state` — but it is inferred from those lists rather than
demonstrated, and the frame-split gap above is what an untested inference
looks like when it is wrong.

**Unwired.** `world/structure.py`'s frontier-expansion trio —
`materialize_planned_fringe` (`:184`), `prepare_frontier_expansion` (`:266`),
`apply_frontier_mutations` (`:350`) — is exported at `:410` and has no
production caller anywhere in `agents/`, `persist/`, `web/`, `story/` or
`tools/`.

**Docstrings that overstate, each now contradicted by the guide.** Fix the
docstring or fix the code; do not leave both.

- "five approaches" in `world/living_world.py:1` and `web/app.py:4547` —
  `LIVING_WORLD_APPROACHES` has four. Approach C became core carrier physics.
- ~~`pick_background_reactors` returning `[]` as "the common case"~~ —
  **withdrawn, and worth recording as a method note.** The audit reasoned from
  the code that `dialogue_turns` is a standalone qualifying signal and records
  are pruned only by promotion, so any presence that has spoken once qualifies
  forever. The reading is right and the conclusion is false: measured over 816
  live `background_react` steps in nine chats, the backstop produced a reaction
  on 0–10% of beats, and 41 of 69 tracked presences have non-empty
  `dialogue_turns`. Something downstream of that disjunct — the `roster` /
  `voiced_this_beat` exclusion is the candidate — keeps it quiet. The
  docstring stands. A code reading is a hypothesis; this corpus can answer it
  directly, and the first draft of `LIVING_WORLD.md` shipped the hypothesis as
  fact.
- `ambient` withholding "a line directed at one of them"
  (`story/scene.py:2087`, `agents/background.py:559`) — the test is divergent
  hear levels, not direction.
- `agents/background.py:16` naming the gate `pick_background_reactor`
  (singular); the stage calls the plural with `cap`.
- `agents/background.py:32` calling `pending_reply` "a one-beat debt"; the
  write sets `expires_turn = turn_idx + 2`.
- `world/charter_run.py:20` saying the consequence-fuse wiring is "deliberately
  NOT done here" — it exists, in `charter_runtime`.
- `world/charter_model.py`'s "five primitives" headline, against four
  normalizers, with `normalize_body` outside the five; and its `authority`
  described as "a closed list" where `normalize_post` closes nothing
  (`:145`). The real closed set is `charter_decide.ORDER_ACTIONS`.


### 1.80 A spoken line shorter than four characters is invisible, and takes the next one with it

**Found:** building the narrator placeholder protocol, 2026-08-24.

`_QUOTE_BODY_RE` matches an opening quote mark, then a run of at least
**four** non-quote characters, then a closing mark. That `{4,}` means a quoted
line of three characters or fewer -- `"No."`, `"Aye."`, `"Sir."` -- never
matches, so DIALOGUE FIDELITY does not check it and the narrator may drop it
freely.

**The second half is worse than the first.** The two quote marks the regex
skipped do not disappear; they pair with their neighbours. Given two short
lines in one view, the span BETWEEN them matches instead:

    'Picard says in a flat voice: "No." Riker says in a quiet voice: "No."'
    -> [' Riker says in a quiet voice: ']

So the check can be handed the composer's own attribution formula as though it
were a delivered line, and then complain that the narrator failed to reproduce
it. Every fidelity finding on a beat containing an odd number of sub-four
character quotes is therefore suspect.

`agents/common._dialogue_tokens` guards its own output with
`_reads_as_attribution`, because feeding that span to the narrator as a line to
PLACE would print `Riker says in a quiet voice:` inside quotation marks. The
underlying regex is untouched: raising `{4,}` to `{1,}` would admit stray
inch-marks and initials as dialogue, and the right fix is probably to match
quoted spans pairwise rather than by content length -- `static/js/chat.js`
already does exactly that (`quotedRegions`) for the speaker tinting, and its
comment explains why the region rather than the match is the unit.


### 1.81 A part-qualified pose support is invisible to the pose sweeper

**Found:** closing the chat-87 view-register class, 2026-08-25.

`_pose_referent` now resolves `<owner>.<part>` through its owner, and
`normalize_scene_subjects` folds the owner half so one field holds one
spelling. `normalize_scene_poses` was not touched: it still checks a support
against `positions` and the room's `anchors` **by whole string**, so
`Kestrel.hand` matches neither and the sweeper never clears it. The pose keeps
naming a body after that body has left the room.

Adjacent and real, and deliberately left out of the render fix: it changes
what gets CLEARED rather than what gets rendered, and it belongs with the
contact-bound pose invalidation rather than with the referent resolver.

### 1.82 Two narrator checks that fire and buy nothing

**Found:** the same day, adding them.

`_check_speech_marking` and `_check_attire_fidelity` score the page against
records the payload was already entitled to, and both ship as plain warnings
-- not in `_ENFORCEABLE_PREFIXES`, so neither buys a correction rewrite.

That is the right default and not the right resting place. Promotion is a
MEASUREMENT: 0fec229 measured the reuse check being fooled 4 of 5 times by the
attribution label, and demoted the ordering check on exactly that evidence.
Each enforceable firing costs a whole narrator call, so the question for both
is their false-positive rate over a live run, and nobody has counted yet.


### 1.83 A beat that names only where the clock ENDS ages no body at all

**Found:** 2026-08-25, closing the `state_diff.time` vocabulary.

The vitals tick inside `world.spatial_merge.merge_scene_with_diff` asks
`world.mechanics.time_diff_duration` how long the beat took, and that helper
is handed the time block ALONE — no previous clock. So it can answer from
`duration_seconds`, or from the span between a parseable `start_seconds` and
`end_seconds`, and from an absolute-only diff it answers 0.0. Hunger, thirst,
fatigue and every other vitals channel therefore do not move across a beat
that says only "the clock now reads N", which is precisely the shape the
clock reader was just taught to accept (5 such diffs in the live corpus: chat
74 turns 55 and 60, chat 88 turns 61, 64 and 66).

The 0.0 is deliberate and is the safe half of the trade, which is why this is
a residual and not a defect to fix in place: under-ageing a body is
recoverable, and ageing it by the story's whole elapsed history — which is
what subtracting nothing from an absolute position would do — is not. The
argument is written at `time_diff_duration` itself; this entry exists because
a docstring is only found by someone already reading that function.

The repair is a seam widening, not a guard: `merge_scene_with_diff` has no
previous-clock parameter, and the callers that would have to supply one
include perception's mid-turn merges, where the "previous" clock is a
different question. Do it with the seam, not around it.

**The seam now exists, and this entry is still open.** `merge_scene_with_diff`
gained a keyword-only `clock_seconds` when a passage learned to carry its
occupants on the clock (`world.spatial_containment.advance_room_transits`),
and both stored-side callers pass the same end-of-beat value through
`world.mechanics.beat_end_elapsed`. The vitals tick was deliberately NOT
rewired onto it: this entry is about which QUANTITY ages a body, and moving
it from `time_diff_duration` to a clock delta is a change to how every
survival channel advances, which wants its own measurement rather than a
free ride. Note also that a beat charged `UNCLAIMED_BEAT_SECONDS` shares
this entry's shape exactly -- the clock moves and the bodies do not -- so
the floor makes the class visible on 130 more corpus beats without widening
it.


### 1.84 A condition with no declared end and no owning floor still stands forever

**Found:** 2026-08-25, landing the due-tick sweep. Half of that landing; this
is the half that was deliberately NOT shipped.

A condition now has three ways to be seen and two ways to end. It can end on
the clock (`expires_at`, `world.mechanics._expire_conditions`) or by an act
(the Director re-emitting the same `condition_id` with `active: 0`, which
`_conditions_view` finally equips it to do by showing every live row's id).
What it still has is no way to end when the fiction simply moved on and
nobody said so. Measured read-only on the author's `engine.db` 2026-08-25:
444 `world_conditions` rows across 50 chats, 363 active, and **360 of those
active rows carry no `expires_at` at all** — spread over 106 distinct free-
text `kind` strings, so no per-kind duration table could hold the class.

The mechanism designed for it was an idle-review backstop in the same sweep:
a row that declares no clock end and whose family owns no deterministic exit
(`story.scene.condition_exit_owner` returns None) closes with a stated reason
after long idleness. It was deferred because BOTH of its arms were measured
to close zero of the 360 rows they were built for:

* the **simulation-clock arm** needed 24 story hours (86,400s). No chat in
  the corpus has ever reached it: the maximum `simulation_clock.elapsed_
  seconds` over 74 chats is 29,145 (chat 40) and the median is 372.5. The
  threshold is 209x the p90 of the 76 authored condition durations (414s),
  and unreachable in every story that exists.
* the **turn arm** needed `last_asserted_turn_idx`, which this landing began
  stamping at the write — so it exists only on rows written after it, and
  not one of the 360 legacy rows has it.

A simulation-second twin of that stamp (`last_asserted_at_seconds`) shipped
with the landing and was removed in the repair pass the same day: nothing read
it, `_conditions_view` already reports `age_seconds` off `started_at`, and the
arm that would have wanted it is the clock arm this entry says should probably
be dropped. A field nothing reads is worse than no field, and that rule does
not stop applying to the fields this landing added. If the clock arm is ever
argued for rather than assumed, the stamp is two lines in
`persist/commit_entities.commit_world_entities` and belongs in the commit that
argues it.

Shipping it would have been a mechanism whose measured effect is zero while
its register entry claimed the rows "drain organically", which is the exact
failure mode this table already has too much of. The two things it needs are
both small and both real work: (1) an initialization op in the sweep that
stamps `last_asserted_turn_idx` on un-stamped rows the first time it sees
them (the `next_tick` initialization is the shape to copy), and (2) a
turn-count threshold argued from something — `mind/affect.py`'s
`_INTENT_DORMANT_AFTER` of 30 turns is a borrowed constant, not a measured
one. The clock arm should probably be dropped rather than lowered: story
clocks in this corpus do not move far enough to carry a rule.

The cost asymmetry that justifies building it at all is the awareness floor's
own, generalized: closing a condition wrongly costs one beat the Director can
re-narrate, and never closing one is the 360-row ledger.

**And the ledger is now charged per beat.** `active_conditions` reaches the
Director in `director_interpret`, in `director_resolve` and inside the body
specialist's payload, so a live row is spelled three times a beat (four for a
gated awareness row, which `active_awareness` also carries). The view is
capped at 40 rows and one corpus chat carries 24 active at once, so the worst
case is real and recurring rather than theoretical. Two separate reductions
are available and neither is free: closing the un-owned rows (this entry) so
the ledger is short, or composing the Director's condition blocks once per
beat instead of once per stage. The first is the one with the design argument
behind it; the second is a payload-assembly change and should not be made
before somebody measures what the three copies actually cost.


### 1.85 A memory's age off a per-beat estimate, not a per-beat record

**Found:** 2026-08-26, landing `memories.encoded_at_seconds`.

Every memory now carries the simulation-clock reading it was written at, and
`mind/memory_time.py` names the interval off that reading alone -- so a single
delivered memory is exact and needs nothing here. A SUMMARY WINDOW is the gap:
it names a range of turn indices and carries no reading of its own, so the ends
have to be resolved to fiction time by some other route.

Today `window_clock_readings` resolves them by reading the stored stamps back
off the memories that window actually consolidated. Those are real recorded
values, not an estimate, and they are right whenever the window minted this
character anything at all. Two cases they cannot answer: a window whose rows
have since been archived away, and a window that minted this character nothing
(the character was gated out, or simply silent, for the whole stretch). Both
fall back to the qualitative phrase, which is honest and slightly poorer.

The same gap has a second face: the v34 migration backfills existing rows at
`turn_idx * world.mechanics.UNCLAIMED_BEAT_SECONDS`. That constant is the rate
the live clock already charges a beat that claimed no duration, so backfilled
rows come out consistent with new ones by construction rather than by an
invented number -- but a story whose beats mostly DID declare durations has a
bank dated by a flat 10s/beat that its own clock never followed.

**What closes both:** one row per committed turn holding the reading that turn
ended at -- a per-turn clock history, written where `persist/commit_scene_state`
already stores `simulation_clock`, rolled back with the turn like any other
committed row. `window_clock_readings` is the named seam: its BODY changes and
nothing downstream does, because every caller already takes
`(opened_at, closed_at)` or a qualitative refusal. The backfill becomes
re-derivable for any chat whose history survives.

Not urgent: the fallback is a phrase rather than a wrong number, which is the
posture this whole change insists on. Worth doing when something wants to date
a window whose memories are gone -- long-bank archival is the likely trigger.


### 1.80 Residuals from the change tier

Landed with `Design.md` § A view leads with what changed: a player view is now
partitioned into a beat half and a background half by
`composer.standing_verdicts`, reading each observer's own previous ledger.
Three things that work names for and does not close.

- **The content hash is LEXICAL, so a re-wording reads as a change.** A
  standing key's content half hashes the rendered fields, and a specialist
  that re-phrases a pose or a contact manner without moving anything mints a
  new hash. Measured on the replayed corpus (chats 86-92, 389 player views),
  the beat half carries 16.9% contact and 7.2% pose atoms per beat, and some
  unknown share of that is re-phrasing rather than movement. **The cost is
  bounded and is not an information leak**: every sentence still realises
  admitted percept data, so a false "changed" verdict buys a re-description
  the observer was already entitled to, never a fact they were not. Semantic,
  wording-invariant keys are the fix and they are a separate change with a
  separate argument — a pose is not obviously equal to a paraphrase of
  itself, and deciding it is has consequences for memory minting too.
- **The episode renderer keeps its own changed-list logic.**
  `_render_episode_english` still asks `dedupe_key not in prev_standing` plus
  `force`/`prev_described` directly rather than calling `standing_verdicts`.
  It is correct as it stands (the split key is still an exact match), but it
  is a second spelling of one rule, which is the shape this repo has watched
  drift before — the Japanese adapter's copy of the player delta rule had
  already drifted once when this work found it. Unifying it is a tidy-up, not
  a defect.
- **An adapter that implements `render_view` without calling
  `standing_verdicts` re-forks the rule.**
  `tests/test_japanese_renderer_parity.py` compares the two renderers'
  beat/background classification AND the order of their spans, so the shipped
  pack cannot drift silently; a THIRD pack could. The classification half of
  that comparison shipped a beat behind the ordering half: the first version
  of the ordering test rendered a beat containing exactly one member, which
  orders correctly whatever the rule says, and it passed while the Japanese
  adapter emitted the changed standing percepts before the events. The three
  private composer names the pack reached across for are now public
  (`leads_the_beat`, `as_beat`, `ACTIVE_STANDING_KINDS`) and the ordering
  itself is `composer.player_view_order`, which both renderers call, so the
  ORDER is no longer a thing a pack can hold an opinion about. What a pack
  still spells for itself is admission -- the appearance and standing-dedupe
  branches -- and that is the remaining fork. A malformed adapter still falls
  through to the English reference renderer, which carries the tier, so the
  failure mode is wording rather than information.

One thing the replay surfaced that is NOT a residual, recorded so the next
reader does not re-open it: the stored corpus shows a structured overlay
reaching the page as a Python `repr` (`currently {'name': 'tail',
'description': '...'}`, chat 89, every beat). `story/scene.appearance_of`
already renders overlay dicts by description and has since before this work;
those rows are historical prose, not live behaviour. A stored view is a
record of what an older engine composed, and reading one as evidence about
the current one is the mistake this paragraph exists to stop.


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

(Corrected 2026-08-19: this entry previously read "Verified absent: no
`relationship_events` table exists". It does — `core/db.py:663`, with a
writer, a reader, archive, checkpoint and branch-remap support, its own test
file, and **341 live rows**. A register that states the opposite of the
schema is worse than one that says nothing.)

### 2.3 Teach the heuristic import to read `description`

**Closes debt #3.** No LLM required: fall back to `description` for
`self_model.summary` and voice notes when `personality` is empty, and warn
specifically when a heuristic import lands below a populated-field threshold.

The heuristic path derives psychology from the card's `personality` field, so a
v2 card that puts everything in `description` — common — yields a sparse first
pass. The opt-in v3 gap-filler mitigates sparse old cards but does not remove the
value of a better deterministic first pass.
`character_card_warnings` now fires on all ten surfaces that hand back a card
(`8ddcc1e`), so a heuristic import that lands sparse is reported wherever it
was made; what is still missing is the populated-field THRESHOLD that would
make "sparse" a warning of its own.

### 2.5 Complete automatic canon lock

Age-based locking is built (`persist/commit.py` locks chat-canon entries older than 20
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

It decomposes: gap-history plus delta-summary is the valuable 80% and is the
same generator as §2.8; the negotiation protocol is the hard, novel half and can
trail behind it. Mapping proposes the gap; the character may refuse on integrity
grounds only; refusals are capped and tagged (identity-violation counts half,
preference counts full); on exhaustion the last proposal becomes canon.
*Conservative defaults, costly exceptions.*

**Steps 1–5 of the build order landed** (bg-life work, 2026-08): `gaps.gap_for`
plus the `subject_last_seen` ledger, the chat-level `offscreen_life` ceiling,
`offscreen.stochastic_ticks`, typed `reactive` plan stages, and
`offscreen.schedule_agent_ticks`. Step 2's per-character half landed as an
IMPORTANCE override (`simulation.offscreen_importance`, read by
`offscreen.importance_for`) rather than a per-character RUNG — deliberately: the
ladder answers what a character MAY do, importance answers how much they matter,
and one vocabulary answering both is the `flow.reactors` defect re-minted. The
rung opt-in that step 4 wanted now exists as `simulation.offscreen_agent`
(`world/offscreen.py`), so that residual is closed too.

**Steps 6 and 7 are what is left, and they are absent entirely.** Verified
2026-08-19: `reactivation`, `negotiat` and `refusal_budget` return **zero** hits
across every non-test module.

- **6. Reactivation proposal.**
- **7. Negotiation** — refusal budgets, tagging, stalemate-eats-canon.

Precedent that did not exist when the note was written: `world/background_claims.py`
is exactly the "commit invention as claims, not facts" mechanism its decision 3
asks for, built for background presences.


### 2.8 Richer off-screen life

Deterministic scheduling exists; what is missing is the world visibly having
moved while you were away. Most of the cast needs no tick at all — the gap is
generated at re-contact, so cost stays `O(re-contact)`. The exception is the
character advancing a plan whose consequences the player meets *before* meeting
them: you cannot lose a race that was never run.

**Almost all of it has landed** and the record is in `CHANGELOG.md` and
`Design.md`: the `offscreen_life` ladder as a chat-level ceiling, a model-free
seeded `stochastic` rung, out-of-band profile ticks on a frame-scoped
`offscreen_epoch`, `world_events` as the objective spine (schema v27, with
checkpoint/archive/branch/migration), carrier delivery and couriers, caravans
and artifact carriers, and typed `reactive` plans that require a same-beat
declared basis. `character_agent` is marked built in the UI.

**One bullet is open, and it verifies.**

- **The stored `offscreen_log` history is still mixed** across four legacy
  shapes (`{actor, tick}`, `{event}`, `{who, event}`, `{description}` all appear
  in the same field across eight live chats) plus the new record shape.
  `commit_mapping.normalize_offscreen_events` coerces on the WRITE path only
  (`persist/commit_mapping.py`, called once at the mapping commit); nothing
  migrates what is already stored, and every reader coerces for itself. Cheap
  while nothing computes over the history, and a trap for the first thing that
  does.

**Direction changed 2026-08-21, and it reopens this entry.** The goal is now
*relatively high-fidelity off-screen simulation performed in code*, with model
calls reserved for the aperture (interpretation at contact, and promotion when
a background body becomes someone the player talks to). The premise this entry
was written under — that the deterministic spine is a cheap floor and fidelity
above it is bought with calls — was measured false: a per-turn sweep of 1,000
bodies × 100 belief facets is 193 ms in plain Python, 500,000 facets is 845 ms,
off the critical path against a ~22.5 s character call. Recorded at
`design/DESIGN_LIVING_WORLD.md` §8.1 and
`design/OFFSCREEN_WORLD_ARCHITECTURE.md` §1.1; the worked case is
`design/DESIGN_INSTITUTIONS_AND_UPKEEP.md` (deterministic vertical slice built).

What remains in this register:

- **The `offscreen_log` migration above still blocks any consumer of that
  legacy history, but no longer blocks Charter's current-state slice.** Charter
  owns a new typed, frame-scoped registry and writes incidents through
  `scheduled_events` -> `world_events`; it never reads `offscreen_log`.
  Backfilling Charter history from older play, or building any cross-system
  retrospective over the legacy log, must migrate the four shapes first.
- **Institutions and upkeep — deeper realism and product authoring.** The five
  genre-neutral primitives, pure simulator, frame-scoped epoch job, guarded
  persistence, consequence mint, destination aftermath and per-presence slice
  are built. The current `/api/chats/{cid}/charters` surface is structured but
  raw. Still open: upkeep readings as beliefs rather than ground truth,
  fractional labor/service, travel and handover time, body refusal/projects,
  recovery-place requirements, nested charters, adaptive safe ensemble
  batching for Charter people, and a
  guided authoring UI with templates. Deliberately NOT called `stations`:
  that word already means a body's within-room position.
- **Typed belief facets for what travels off screen.** Contradiction over
  prose is semantic, which is why deterministic dispute detection was refuted;
  over `(owner, subject, facet_type, value)` it is a key comparison. Scope it
  to a small closed vocabulary whose values are REFERENCES (entity, room,
  `event_id`) rather than strings — a reference needs no hand-authored
  mutation graph, which is the tuning burden that measurably hurt the one
  published system at this scale. Facets must be a derived index over
  `world_events`, never a parallel store; the precedent is
  `composer.observations_from_render`, where the second representation is
  re-derived so it cannot expand the information budget.
- **Two rules the extra fidelity must not be allowed to break**, stated here
  because they are cheap to lose: storage grows with *incident* rather than
  time (recompute from the clock at contact, commit only branches —
  `world/routines.py` is the standard), and the world never forgets while
  minds do (the objective spine is monotonic; culling unreachable facts makes
  the world observer-relative).


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

`dressing/ambience.py` mixes up to three simultaneous beds (`tone` / `weather` /
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

### 2.14 Clothing regions: the guess is reported, the authored answer is inert

**The report landed 2026-08-19.** `attire.guessed_spans` had no production
caller — its own docstring described the hand-off in the present tense while
the loop stayed open. It now runs at the attire commit seam and tells the
Director, which is the only stage with the fiction in front of it and can
answer with `coverage`. Told rather than repaired, because the cue tables are
the thing that does not know, so a second deterministic guess would be the same
guess. Measured while it was open: 110 of 560 live worn garment records carry a
span the tables guessed, twenty of them a nagajuban sitting on the torso alone,
so those bodies report legs and groin bare while wearing a full-length
under-kimono.

The open half moved to **§1.72**: the authoring surface the Director is being
pointed at does not work. `placement` and `add[].covers` are documented in both
prompts, passed correctly at the call site, and lost to an ordering bug before
they are applied. Until that lands, the report asks for something the engine
cannot yet accept — which is worth knowing when reading the warnings.

### 2.15 Movement is an arrival, never a crossing

**Raised 2026-08-02**, after "step outside" landed correctly and still read
wrong. A turn that moved a body rendered the destination and nothing else, so a
plaza crossing or an elevator ride read as a cut.

**Two-thirds landed 2026-08-14, verified 2026-08-19.** A journey is now a
standing thing: a declared walk survives a beat that says nothing about it and
advances one edge per beat (`director_movement._travel_continues`,
`scene.approach`), a long edge takes two (`_LONG_EDGE_DISTANCES`), and the leg
is computed BEFORE the prose is written and handed to the author as
`travel_in_flight`, so the scenery changes on the page in the same breath as
everything else. That decided need (1) against the Narrator — the ENGINE owns
the crossing and the Director may only stop it (`travel_interrupted`) — and need
(3) is met by the `adjacent`/`near`/`far`/`remote` tier the edges already carry,
so a doorway step is unaffected.

**Need (2) is open, and it was always the hard one: what a body PERCEIVES
mid-crossing.** The honest answer is "both rooms, briefly" — the same union
`_source_channels` computes across a beat, and possibly the same mechanism.
Today a mid-walk body is simply IN the room the leg put it in, so a corridor
crossed over two beats is perceived as two rooms in sequence rather than as a
passage between them. Truthful, and thin, which is what this entry was raised
about.

**Related, from the alpha 6.3 physical-ledger work (moved from §3.9,
2026-08-19):** nothing derives a station from within-room movement INTENT ("she
crosses to the hearth"), because there is no within-room approach concept for it
to read — room-level `scene.approach` is the only staged-movement memory there
is.


### 2.16 A summary window should be an INDEX over raw memory, not more prose

**Raised 2026-08-02; verdict recorded 2026-08-19/20.** The strong form below
— route retrieval through the winning window — was MEASURED AND REFUSED:
window-first routing scored 6–7/12 against flat retrieval's 10/12 on the live
corpus ([`experiments/AUDIT_MEMORY.md`](experiments/AUDIT_MEMORY.md) §3.6),
the compounding P(right window) × P(right row) is real, and RAPTOR's and
MemTree's own ablations independently agree (audit §4.3). Do not rebuild it
without evidence that beats all three. What survives of this entry:

- **The "nothing convincing" floor this entry said did not exist now does** —
  `memory_retrieval.recall_confidence`, a per-query NQC/WIG-shape signal
  against the bank's own score distribution, calibrated at zero measured
  false abstention across both corpus states
  ([`experiments/MEMORY_IMPROVEMENTS.md`](experiments/MEMORY_IMPROVEMENTS.md)
  §5). It annotates the passive lane (`nothing_comes_back_clearly`); it is
  deliberately NOT extended to the ponder lane (measured: it would falsely
  abstain on a diffuse pattern-over-session query whose answer was
  delivered).
- **Still live, with the audit's evidence behind them**: windows entering the
  same RRF fusion as first-class candidates (audit §4.3 item 1), and the
  window's deterministic `start/end_turn_idx` as a temporal BOOST when the
  query carries a temporal cue (item 2) — the index shape this entry wanted,
  without the routing it feared.

The original argument, kept for the record:

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

**Correction, 2026-08-19: the turn range is not missing.**
`memory_summaries.start_turn_idx` and `end_turn_idx` exist in `core/db.py` and
have since the table shipped. What is missing is the RETRIEVAL SHAPE above and
the prompt contract below, not the column.

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
nothing convincing -- and the "nothing convincing" signal that this paragraph
said did not exist is now `recall_confidence` (see the verdict block above).


### 2.17 Memory reliability after temporal separation

**Shelved 2026-08-02.** The benchmark that produced this list — the controlled
chat-38 embedding and character-question comparison, seven isolated questions
per arm — is measurement, and moved to
[`experiments/MEASUREMENT_BACKLOG.md`](experiments/MEASUREMENT_BACKLOG.md) on
2026-08-19 along with the integration-pass landing record. Its headline, kept
because every priority below is ranked against it: semantic answers passed
**7/7** against lexical-only **5/7**, relevant evidence reached the payload in
**5/5** historical cases against **2/5**, and relevant earlier windows **5/5 vs
0/5** — while raw-memory MRR was LOWER for semantic (0.207 vs 0.400), because
lexical put its two exact-word successes at rank 1 and missed the other three
entirely. Reliable retrieval is not yet reliable conduct, and that is what this
list is for.

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

*(Item 8 — "audit summaries against their source rows" — was struck 2026-08-19:
per-clause `support` with `support_refs` + `epistemic_origin` is in `core/db.py`'s
`memory_summaries` and written by `mind/memory.py` at consolidation, derived
host-side so it costs no model call. Its convergence with §2.16 stands.)*

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
rather than creating another one-off question script. It is no longer married
to chat 38: `--cases-file` loads a case bank
(`tools/memory_probes/behavioral_chat63_char35.json` is the first), and the
retrieval-side probe harness is `tools/memory_probe_harness.py` with its
frozen sets under `tools/memory_probes/`
([`experiments/MEMORY_IMPROVEMENTS.md`](experiments/MEMORY_IMPROVEMENTS.md)).

---


### 2.18 The orchestrated Director: what is left after it landed

**LANDED 2026-08-14.** The fan-out is the only Director path: there is no
`DEFAULT_PROMPTS["director_resolve"]`, no `director_orchestration` setting,
and `director_fanout_mode` chooses concurrency rather than a different set of
hands. `Design.md`'s conformance row says Built, and it is right.

This entry used to be the whole proposal — the argument, the measurements,
the retracted framings and the build log — with its landing recorded in a
paragraph at the bottom. A reader triaging §2 read the shipped architecture
as an open experiment, and this register is supposed to WIN when the status
lists disagree. The argument and the numbers live in
[`design_notes/19-director-orchestration.md`](../design_notes/19-director-orchestration.md)
and in the alpha 9.2 changelog; what belongs here is only what is still
unbuilt:

- **The prose author's PAYLOAD is still the full monolithic one.** Its SHEET
  was carved (14 duty chunks, `_PROSE_DUTY_GATES`); the payload was not. The
  next real token win.
- **`director_interpret`'s own sheet is not chunked.** The delegated channels
  are suppressed at the source (`llm/prompts.interpret_delegation_note`, called from `agents/director.py`; the constant `INTERPRET_DELEGATION_NOTE` this entry used to name does not exist — corrected 2026-08-19), but the blocks
  teaching them still load on every call.
- **The specialist chunks have never been rewritten for leanness.** Permitted
  — they exist only on the orchestrated path, so there is no monolith to keep
  them compatible with.
- **The offscreen SIMULATOR** (out-of-band propose/ratify) remains
  owner-deferred. The `offscreen` specialist ships the ops surface only, and
  schedules nothing.
- **The replaced-channel warning rate has never been re-measured live.**
  Stored variants hold only the MERGED output, so the after-rate cannot be
  read from run 20's own beats.
- **Provider cache affinity is configuration, not code.** Run 20 diagnosed
  the 19% prefix-cache rate as provider replica routing rather than byte
  instability; honest ceiling ~57%, since the per-beat payload is inherently
  uncacheable. Recorded rather than chased.


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
judgement?* Psychology persistence already is not — `mind/psychology_runtime.py`
does it deterministically from permitted inputs. If other pre- or post-work is
bundled into the same call, that is separable without touching the decision at
all, and is where any character-side decomposition should start.


### 2.20 Characters begin every story with no past they can recall

**HIGH PRIORITY.** Raised 2026-08-19; the full argument, with its measurements,
refusals and falsifier, is
[`design/DESIGN_PRESTORY_MEMORY.md`](design/DESIGN_PRESTORY_MEMORY.md). This
entry exists so the register names it; that note is the authority.

The measured shape: no memory row in the live corpus has a `turn_idx` below
zero, so the first thing that ever happened to any character is turn 0 of the
story they are in. Their semantic self is rich and their episodic self is
empty.

The diagnosis is not the obvious one. 56 of 58 cards carry
`knowledge.public_history` and it is delivered to the deciding mind every beat
(`agents/character.py`), so the past is not absent -- it is **unrecallable and
unforgettable at once**. It has no `when`, no epistemic origin, and no id
`_ground_observation_citations` will accept, so a mind may mention its history
but may never cite it as evidence for a belief, an appraisal or a dispute. It
never entered the retrieval layer.

The substrate is already half-built and already broken on four counts.
`turn_idx IS NULL` rows are admitted by the read seam and already described to
minds as "before this story's recorded turns" (`mind/memory_context.py`, with a
test pinning the string), and two live mint sites produce them. But the
old-memory temporal cue is gated on `ti is not None`, so the one query language
that names the pre-story past cannot reach the only rows that hold it; those
rows never consolidate; they never archive; and they count toward two floors
calibrated on lived banks.

Why "generate a backstory" is the wrong first move, in arithmetic rather than
taste: the median bank holds 11.5 rows at turn 3, the recent buffer excludes
turn-less rows, and `contrast_memory` scores by subtracting overlap -- which is
near zero for material from another decade, making authored rows
penalty-free by construction. Twenty seeded episodes would clear the contrast
gate at turn 0 and BE the character's entire recall for the opening beats. A
thick authored childhood does not read as depth; it reads as haunting.

Related and separately actionable: §1.74 (the import path already performs an
unlabelled `inherit`, with a live persona leak), and the fact that
`recall_confidence` cannot fire below 40 rows -- which the median bank does not
reach until turn 10, precisely the window this entry is about.

Partial prototype answer (2026-08-21, `offscreen-charter-prototype` branch,
unwired): `world/charter_promote.remembered` converts a background body's
charter life into `prepare_memory`-vocabulary rows under one selection rule --
minted only from what changed a tracked ledger, the routine compressed to one
semantic row per post, the whole list capped and flat in quiet time (a
30-day famine month: 89 watches stood became 6 memories). It answers the
haunting warning above for the PROMOTION case only; characters authored with
a past, and the retrieval-layer plumbing this entry is really about, are
untouched. Its firewall tests (unheard blame does not cross, the register
does not cross) are the promotion-leak tests
`DESIGN_INSTITUTIONS_AND_UPKEEP.md` §12a called for.

**Several story-start slices have since landed (2026-08-22), and narrow rather
than close this entry.** `story.history_routing` now resolves conservative
automatic and author-locked routes before generation; only fixed or bounded-
moving residents enter Charter. Resident handoff now produces separate career
and recent-life summaries plus 10–16 ordered, identified personal episodes,
constrained to the pre-named roster, real rooms/duties, actual anchors, card
and author guidance. Each episode is an independent memory row; a sparse result
aborts instead of becoming canon. The planner still sees only public placement
material. `story.journey_history` is the
itinerary backend: cited mode compiles card/lore journeys and explicit
generated mode may invent a bounded event ledger. Greeting launch and the
multi-character Story Quick Start expose one route and optional past guidance
per selected character before turn zero; diagnostics show the resulting
handoff.

**The itinerary backend converged on the resident one (2026-08-26).** It had
been the resident path's poor sibling on four measured axes and is no longer:
the event count is the author's (`journey_event_count`, default 12 against the
resident target of 12, band 3–20) rather than a hardcoded 6/8; each event
carries the resident vocabulary's `tone`/`lesson`/`valence`/`arousal`/
`salience`, imported from `world.charter_history` rather than restated, so a
journey row reaches retrieval with the same things to rank on (measured before:
59 of 91 prestory memories at exactly salience 0.6); the ordinal welding
(`"<when>: Early in my travels, …"`) is gone, because when and place have their
own retrievable fields; the first-person requirement is enforced by the
pack-scoped `_FIRST_PERSON_RE` the narration-person machinery already reads,
as a grounding drop rather than a second instruction; and the lived-location
brief now reaches the generator as `arrival_brief`, so the last events may run
toward the place the story opens at. Arriving still is not residing: residence
remains a `story.history_routing` topology decision this generator never makes.

Still unbuilt on that axis: `importance` stays NULL on both paths by design
(NULL reads as the salience and only a consequence the engine can point at
revises it), so mint-time ranking is salience alone.

Still unbuilt: deeper resident eras beyond the recent-life window, direct
Scene Life use of the compact reciprocal episode records before a background
resident is promoted, and claim-level verification of authored/canon traveler
history.

Do **not** generalize that slice by making every selected character a Charter
resident. The full routing argument and authoring proposal now lives in
[`design/DESIGN_CHARACTER_HISTORY_ROUTING.md`](design/DESIGN_CHARACTER_HISTORY_ROUTING.md).
Charter is the right history backend when continuity is organized by a fixed
place or a moving institution (a garrison, court, prison, caravan or starship
crew). It is the wrong backend for an eccentric traveler whose past is a
sequence of journeys, or for a heavily authored/canonical figure whose history
is not engine authority to replace.

The remaining authoring design should complete three independent axes rather
than one genre-specific class enum:

1. **Continuity anchor:** fixed place / moving institution / itinerary /
   unanchored.
2. **Past authority:** simulated / authored lore / imported prior play /
   controlled mixture.
3. **Opening relationship:** resident / returning / visiting / just arrived.

Fixed or institution-anchored story-start simulation now routes through Charter.
The itinerary ledger is built for greeting launch and Story Quick Start but
still needs stronger
claim-level canon verification, obligation/carrier projection, explicit
arrival intersections, reuse outside story start, and measurement over an
adversarial corpus. Imported continuity still needs the identity-safe repair
in §1.74. The hand-built-from-scratch path still needs cast selection before it
can offer per-character routes. A traveler must continue to arrive with
itinerary and authored continuity, never an inferred local career.

### 2.21 An install with no embeddings provider retrieves worse than one with no vectors

Measured 2026-08-19/20, [`experiments/CRC32_CONTROL.md`](experiments/CRC32_CONTROL.md).
Roadmap rather than defect: nothing is broken for an install that HAS an
embeddings provider, and the population this affects is the one that has never
configured one -- which is every install on its first run.

Six arms over the same 10,960-row LongMemEval bank, 470 independent probes:

| arm | hits / 470 |
|---|---|
| real embeddings, 2560d | 399 |
| crc32 16384 | 337 |
| **no vector channel at all** (BM25 + exact cue) | **338** |
| crc32 4096 | 336 |
| crc32 1024 | 323 |
| **crc32 256, the shipped fallback** | **289** |

**The fallback scores 49 probes BELOW switching the vector rankings off.** It
carries 2.15 of the 4.5 RRF weight while correlating with real similarity at
r = 0.028 over 7,998,000 row pairs, so its noise displaces genuine keyword
candidates out of the payload. Widening does not rescue it: the width curve
saturates exactly at the no-vector line, because there is no signal to sharpen.
A character n-gram sketch is a near-duplicate detector -- it answers "is this
the same text", and it was standing in for "does this mean the same thing".

**Scope, which is easy to get wrong and was got wrong once already.** When a
real provider IS configured, a fallback row is already excluded from both
vector rankings by the compatibility check at `memory_retrieval.py:440`
(`sem = 0.0`, `cue = 0.0`, counted as stranded), AND queued for the background
repair thread, AND caught by `rebuild_embeddings` afterwards. That path is
correct and needs nothing. The harm lands only where crc32 IS the configured
model, because then the keys match and the hash participates fully.

**The change**: on an unresolvable embeddings role, contribute no vector
ranking rather than a hash one. `search_memories` already drops empty rank
lists, so BM25 and exact-cue carry the query at 338 instead of 289, with no
migration.

**What must NOT be done, and why the obvious version of this is wrong**: do not
remove the `cheap:crc32:256` stamp. `embedding_bank_status`,
`_warn_stranded_embeddings`, the repair queue (`note_failed_embedding_write`
selects on it) and `rebuild_embeddings`' `want_fallback` all key on that stamp
existing. The stamp is the marker that says "this engine failed a write and
may finish it later"; deleting it strands exactly the rows the repair thread
is for. Keep the stamp, change what retrieval does with it.

Keep the sketch itself. It is correct for the two jobs it is actually good at:
offline/test operation without a provider, and near-duplicate detection --
measured 99.1% precise against real cosine 0.95, which is a genuinely useful
tool for finding the forty near-identical descriptions of one room in a bank.

**BUILT 2026-08-20**, and the shipped arm scores higher than the one this
entry proposed. `search_memories` now contributes no vector ranking on a
fallback batch -- one flag, `rank_by_vector`, gating the semantic, cue-vector
and aspect rankings, using the same `embedded.fallback` test
`recall_confidence` has always made. `contrast_memory` makes the same refusal
for a sharper reason: that axis REWARDS distance, so a hash there would not
merely fail to find the true contrast, it would nominate rows for unbidden
recall by coin flip while reporting a semantic reason. (Its own docstring
already recorded that the semantic half was deliberately absent until real
vectors existed; this restores that.)

Measured on the same bank, probes and k
([`experiments/CRC32_CONTROL.md`](experiments/CRC32_CONTROL.md) §8):
**289 -> 346**, against the 338 this entry expected. Both control arms
reproduced their recorded numbers EXACTLY -- 289 for ranking on the hash, 338
for dropping the vector channel entirely -- which is what makes the third arm
a comparison rather than a coincidence.

The extra eight probes are the confound `CRC32_CONTROL.md` §2 could not
remove, resolved in the sketch's favour. The 338 arm dropped the vectors
entirely, so MMR redundancy fell back to Jaccard. The shipped change keeps
`_vector` populated -- the hash is refused as a memory-versus-QUERY relevance
signal and kept as a memory-versus-MEMORY near-duplicate signal, which is the
one job §6 measured it to be near-exact at and then declined to propose
without an end-to-end number. This is that number.

**And `search_memory_summaries` deliberately does NOT make the refusal.**
There the hash competes against nothing: refusing it returns no windows at
all, where refusing it in `search_memories` just lets BM25 and exact-cue carry
the query. What it costs in the window lane is the ORDER of a set of the
character's own summaries, each carrying its own turn range -- arbitrary
selection of real autobiography, rather than real material displaced by noise.
The asymmetry is stated at the call site so it reads as a decision rather than
an omission.

`tests/test_no_provider_retrieval.py` (8 tests) pins all three boundaries: the
stamp survives, the sketch keeps the near-duplicate job, and an install with a
real provider is untouched. Three of them fail if `rank_by_vector` is forced
back to True.

*Found while landing this*: three tests in `test_embedding_rebuild.py` had been
asserting that `"semantic match"` fires, on a bank with no embeddings provider
-- so a rebuild's "restored semantic reach" and an aspect's own rank list were
both being demonstrated on crc32 noise. The properties are real; they now run
against a stubbed provider that reports `fallback=False`.

### 2.22 Exact-cue matching scans the whole bank, and an index is what it wants

Measured 2026-08-20, [`experiments/RETRIEVAL_COST.md`](experiments/RETRIEVAL_COST.md).
Roadmap rather than defect: the 4.9x constant-factor fix landed, and what is
left is an algorithm choice that only bites at a scale no live bank has reached
yet.

`_exact_cue_score` runs once per ROW per query. Profiled over 8 queries on a
10,960-row bank it was 79.9 of 89.9 seconds -- **89% of all retrieval time**,
against roughly 10% for the vector scan, which is the opposite of where this
project assumed the cost was. Guarding the word-boundary regex with a
substring test and caching compiled patterns took `search_memories` from
4,732 ms to 968 ms with an identical verdict set on all 470 LongMemEval
probes.

That is a constant factor. The complexity is unchanged: every row is still
visited to ask whether any of its cues appears in the query, and the answer is
no for almost all of them.

**The shape the problem actually has is an inverted index**, and this codebase
already runs one for the neighbouring ranking: `_lexical_memory_ranking` asks
SQLite FTS which rows match, rather than asking every row whether it matches.
An `cue -> row ids` index over `key_phrases`, `entities` and `location` would
make the exact ranking O(matching rows) instead of O(bank), and the matching
set is tiny by construction -- that is what makes the cue signal worth having.

Two things to settle before building it, neither hard, both easy to get wrong:

- **Substring semantics.** The phrase branch matches when a stored phrase is a
  substring of the QUERY (and, for short queries, the reverse). An FTS index is
  token-based, so it would need the cue tokenised and the substring rule
  re-derived from token adjacency, or the index used as a candidate filter with
  the exact rule re-run only on the candidates. The second is safer and still
  removes almost all the work.
- **Write cost.** The index has to be maintained on every mint and every cue
  repair. `repair_memory_cues` rewrites cues in bulk, so the rebuild path needs
  to be part of the design rather than an afterthought.

The vector scan is now the largest remaining term and is still a Python loop
over BLOB-decoded rows with no cache. Holding a bank's vectors as one
contiguous matrix is the standard fix, but after this change it is worth about
a tenth of what it looked worth before it -- which is the reason to measure
before optimising, recorded here because this entry got that backwards once
already.

### 2.23 Four of the seven memory kinds cannot be minted

Measured 2026-08-20 while chasing why preference recall is the worst class in
the LongMemEval benchmark (15/30 with real embeddings, 7/30 lexical --
[`experiments/CRC32_CONTROL.md`](experiments/CRC32_CONTROL.md)).

`MEMORY_KINDS` promises seven: `episodic`, `dialogue`, `inference`,
`semantic`, `relationship`, `promise`, `intention`. Every mint site in
`persist/commit_memory.py` hardcodes its kind -- `dialogue` at 580, `episodic`
at 637 and 715, `inference` at 743 -- so no model chooses one and no path
produces the other four. The live corpus agrees exactly: 5,353 `episodic`,
3,576 `inference`, 425 `dialogue`, 253 legacy `episode`, one stray `belief`,
and **zero `semantic`, `relationship` or `intention`**.

Kind barely reaches ranking today (only `inference` is read, for belief
weighting), so this is not a retrieval bug on its own. What it means is that a
stable fact about a person has nowhere to live.

**The retrieval consequence this entry first claimed is REFUTED, measured
2026-08-20.** The claim was that a preference stored as the EPISODE of the
moment it was mentioned drags that moment's location, turn and cast into its
retrieval document, and that a question about a preference has to compete with
all of it. Tested directly on the 15 missed preference probes by embedding the
stored document against the bare content:

    query vs stored DOCUMENT   median cosine 0.4047
    query vs CONTENT alone     median cosine 0.3994

Dropping every incidental makes it slightly WORSE, and content beats document
on 9 of 15 -- a coin flip. Metadata dilution is not the mechanism.

**What the measurement found instead** is that misses are simply far from
their answers in embedding space, and that this is not specific to
preferences:

    other HIT          median cos 0.5334
    preference HIT     median cos 0.4817
    preference MISS    median cos 0.3561
    other MISS         median cos 0.3311

Hits sit near 0.50 and misses near 0.33-0.36 regardless of class. That is the
question-versus-statement asymmetry -- "what do I like to do on weekends" and
"I took the coast path again on Saturday" occupy different regions -- and no
storage change closes it. Preferences are hardest because a preference is
stated once, casually, in language furthest from the category a question names.

So the SHAPE of this entry survives and its retrieval argument does not:
`semantic` is unreachable and stable facts have nowhere to live, which matters
for 2.20's authored past. It is not the reason preference recall is 15/30.

Related: 2.20 wants exactly this shape for a different reason -- an authored
past is mostly semantic rather than episodic, and the same missing tier is why
it has nowhere to go.

### 2.24 A superseded belief is read before its correction

Measured 2026-08-20 across three independently generated fiction worlds,
[`experiments/SYNTHETIC_BANK.md`](experiments/SYNTHETIC_BANK.md). Roadmap
rather than defect: retrieval is not failing, ordering is, and the engine
already contains the mechanism that would settle it.

A `superseded` fact plants a belief and, 60-400 beats later, the observation
that overturns it. The probe targets the correction and antitargets the belief:

| | |
|---|---|
| correction reaches the payload | 16/18 (89%) |
| correction OUTRANKS the stale belief | **8/18 (44%)** |
| median rank of the stale row | **2** |

So the mind is handed both versions and shown the outdated one first, more
often than not.

The mechanism is structural. The four fused rankings -- semantic 1.0,
cue-vector 1.15, keyword 1.1, exact 1.25 -- contain **no recency term**;
recency enters only when the QUERY carries a temporal cue
(`_temporal_mode`). A belief and its correction therefore compete on text
alone, and a question about a belief matches the STATEMENT of that belief more
closely than the later observation that overturns it. Nothing prefers the
newer row because nothing knows which is newer.

**Do not fix this with a recency tie-break.** That arm is already measured and
rejected: newest-first scored tuned 24->21 and held-out 10->13, "three probes
each way, a lottery, not a rule"
([`experiments/MEMORY_IMPROVEMENTS.md`](experiments/MEMORY_IMPROVEMENTS.md) §4).
A global recency preference trades one arbitrary ordering for another.

**CORRECTED 2026-08-20, and the correction inverts this entry.** The reading
above treats the ordering as the problem and assumes a mind needs help
NOTICING. Measured, it does not. `tools/benchmark_memory_rationality.py` hands
a character the belief and its refutation through the production payload and
asks the question; a judge that never sees the payload classifies the answer
against the plan's two facts. Across three independently generated worlds,
with the character prompt carrying NO instruction to look for conflicts:

| verdict | n=18 |
|---|---|
| named the contradiction | **15 (83%)** |
| stated the corrected fact silently | 2 (11%) |
| **took the superseded belief** | **0 (0%)** |
| neither | 1 (6%) |

Zero failures, despite the stale row being ranked HIGHER in the majority of
cases. The `when` stamp on each row is apparently enough. An arm run WITH a
clause inviting the character to name disagreements scored LOWER on conflict
(4/6 against 6/6), so the behaviour is not prompt-induced -- if anything the
invitation got in the way.

So the ordering defect above is real and cosmetic. What is expensive is not
that a mind reads the stale row first; it reads both, dates both, and resolves
them. Fixing the ranking would change a number and not a behaviour.

**What is actually missing is a channel, not a capability.** Characters are
articulating "I believed X, then I saw Y" in prose, in production, right now --
and it evaporates, because the only way into `disputed` is a structured
`memory_disputes` field the model has to volunteer separately from the prose
it already wrote. That is why the count is 1 in 9,608 while the behaviour runs
at 83%.

Two pieces, and the first is much cheaper than this entry originally implied:

- **Capture what is already said.** The field exists, the commit path handles
  it, the payload renders it as `i_now_read_this_differently`. The gap is
  asking for it in a form the engine can store, on a beat where the mind has
  just done it anyway.
- **Create the occasion.** Genuinely open. In this measurement a question was
  aimed squarely at the contradicted fact; real play does not do that, and a
  contradiction sitting unremarked among twenty other rows may never surface.
  This is where deterministic detection belongs -- two rows, one subject,
  separated in time, both in the payload -- and it stays an OCCASION rather
  than a conclusion, because nothing outside a mind may decide which of its
  memories is true.

**BUILT 2026-08-20, in two parts.** The measurement above located the gap
precisely, and it was not where this entry first put it.

*The grounding was the barrier.* A dispute's evidence was grounded in the
`present` namespace, so a re-reading citing the LATER MEMORY that overturned
the belief -- which is what characters actually cite, 15 times in 18 -- was
dropped as ungrounded before it ever reached storage. Both the code and the
prompt said "what this beat showed you", so this was a stated design rather
than an oversight; it is now widened to admit a memory this mind holds, and
refused only for the disputed memory itself. Firewall-safe on the invariant's
own terms: both rows are its own, legitimately acquired, and one re-reading
another is inference inside a single head. The decisive argument is that
`ponder` exists for exactly this -- a lane built for a mind to go looking
through its own memory, whose output the dispute rule was then refusing.

*And a dispute is now an addendum rather than an overwrite.* `record_dispute`
insists the event stays exactly as it was, but the READING did not get that
protection: a second re-reading replaced the first and only bumped a counter,
so the mechanism built to preserve a memory's history destroyed the history of
how it had been read. Every superseded reading is now kept with the evidence
that produced it, bounded at 8, with the latest still at the top level so no
existing reader moves.

*The rumination watch.* Widening the grounding lets a mind revise its past
from its own memories, round and round, with no new input. That is not
forbidden -- a mind is allowed to keep thinking -- but it can no longer happen
invisibly: `tests/test_dispute_addendum.py` pins that four re-readings citing
one source are distinguishable from three citing three, which a bare counter
could never separate.

**BUILT 2026-08-20, and the entry's own premise was refuted on the way.**

The reading above -- and every version of this entry before it -- says the
dispute lane is starved because nothing ASKS. The asking was built and
measured, and it makes minds dispute LESS.

On a neutral beat, with both rows already in the payload, a character asked
what is on its mind:

| | |
|---|---|
| no occasion offered | **16/16 (100%)** |
| handed the pair and the subject | **13/16 (81%)** |

That is the third measured instance of one shape in a single day. The conduct
table above records an arm run WITH a clause inviting the character to name
disagreements scoring 4/6 against an unled 6/6, and
[`experiments/SYNTHETIC_BANK.md`](experiments/SYNTHETIC_BANK.md) 6 records the
same. **Telling a mind to notice something makes it notice less**, reliably
enough now to plan around.

**What is actually missing is CO-PRESENCE, and the number is absolute:**

| | |
|---|---|
| unaimed beat, ordinary recall, no ponder | |
| both halves of a contradiction in the payload together | **0 / 18 (0%)** |

Never, not rarely. Every one of the sixteen successful disputes had both rows
present, and in every case the ponder lane is what put them there. Ponder
fires roughly 1 turn in 332; `record_dispute` fires 1 in 9,608. That ratio was
the finding, and it was sitting in this file the whole time.

So this entry's FIRST suggested direction was correct and the two that were
buildable were not: *"the ponder lane already does it accidentally... making
ponder more likely on a subject a character has beliefs about may be the whole
fix, and it needs no detector."*

**What shipped.** `schedule_memory_tension_pass` runs after commit, beside
consolidation, and reads what a mind just recorded against what it already
held. It stores the SUBJECT of anything that does not sit together; a later
beat runs that subject as a retrieval and hands over whatever returns
(`resurfaced_without_asking`). The mind receives ROWS. It is never told they
disagree -- which is both the measured-better behaviour and the only version
that respects this entry's own rule that nothing outside a mind may decide
which of its memories is true. Labelled `unbidden_subject` rather than
`query_i_chose_last_turn`, because this mind did not ask and saying it did
would be the engine speaking for a character (compare 1.11i).

Out of band for a measured reason: the reading pass costs **114s** against a
24-row payload and completed 20 of 36 calls in band. Its two failure modes
were budget rather than classification -- `RemoteDisconnected` was already
retryable and merely exhausted three attempts, and a reasoning model ate the
reply whole at 700 tokens and again at 6000.

**The reviewer discriminates better than any character model measured**, and it
is the same deepseek that scores worst as a character (n=18 scorable):

| | belief that turned out unfounded | the world simply changed |
|---|---|---|
| named the planted pair | **11/13 (85%)** | **1/5 (20%)** |

Zero tensions invented from nothing across 36 cases. The gap of +65 compares
with glm-5p2-fast +46, grok-4.3 +1, deepseek-v4-pro -20 as CHARACTERS on the
same axis. The framing does the work, not the weights.

**What is still open.**

- **The unaimed case is bounded but not closed.** Every dispute arm keeps the
  ponder query in the payload, and that query is itself a pointer. The
  genuinely unaimed case -- both rows present through ordinary recall alone --
  could not be arranged, because it happens 0 times in 18. That is evidence
  for the finding rather than a hole in it, but it is not the same as having
  measured it.
- **Whether the shipped retrieval raises the live rate.** 1 in 9,608 is the
  number to beat and it can only be read off a real corpus over many beats.
- **A mind has no record of HAVING pondered.** `memory_ponder` is popped when
  consumed and no row is minted, so a character that has asked itself the same
  question five times cannot notice. Deliberately not built: a row per ponder
  is noise, and it changes what gets minted. It is the same shape as the
  rumination watch on disputes, which chose legibility over prohibition.

**The original reading, kept because it was the reasoning at the time:**

**The engine already has the right shape and never reaches it.**
`record_dispute` is wired end to end -- proposed in the character's output,
committed by `persist/commit_memory_write.py`, stored on the row, and rendered
to the mind as `i_now_read_this_differently` -- and it has fired **once in
9,608 live memories**. The gate is that `memory_disputes` is entirely
model-initiated: a character must spontaneously volunteer that it now reads a
memory differently, and nothing detects a contradiction or offers the
occasion. Compare `ponder`, also model-initiated, also rare (7 uses in 2,328
turns).

The shape of a fix, in the engine's own vocabulary: a mind handed two rows
about the same subject, separated in time, is being handed an occasion to
revise, and the payload can say so without deciding the answer. That is the
firewall-safe direction -- give the mind the material, never make it conclude
less. What must NOT be built is a deterministic contradiction detector that
decides which row is true; nothing outside a mind is entitled to that.

**Not established, and the honest caveat**: both rows usually reach the
payload, and each carries `when` ("about N beats ago"), so the character HAS
the material to prefer the newer one. Whether it does is a conduct question and
is unmeasured. Ordering matters because it decides what is read first, not
whether the answer is present. 18 probes is also a small set, reported with its
denominator.

### 2.25 Two retrieval ideas measured, one rejected, one parked

Measured 2026-08-20 against the 470-probe LongMemEval bank while looking for
what else would raise recall. Recorded so neither is retried without new
evidence.

**HyDE (embed a hypothetical answer, fuse it as an aspect) -- REJECTED.**
The motivation was sound and is worth keeping: misses sit at 0.33-0.36 cosine
from their answers while hits sit near 0.50 (2.23), which is the ordinary
question-versus-statement asymmetry, and writing what the remembered moment
would have SOUNDED like is the standard answer to it. Measured on 30 probes
that miss, it rescued 3 (10%). Measured on 40 that hit, it broke 1 (2%). Hits
outnumber misses six to one, so the extrapolated net is **+7 rescued against
-10 broken**. Measuring only the rescue rate would have made this look like a
win; the breakage arm is the whole finding.

**Query decomposition (split the question into clauses, fuse each as an
aspect) -- PARKED, not rejected.** Deterministic split on relational
connectives, clauses of three or more words, capped at three. Across all 470:
399 -> 402, **rescued 3, broken 0**. Strictly non-destructive on this
instrument and free at runtime, since aspects ride the same embedding call as
the query. Not shipped because +3 on one bank is inside the noise of a single
instrument and it has no conduct arm -- the same standard that let the
`_RECALL_LIMIT` change through. Cheap to revisit: `search_memories` already
accepts `aspects`, so this is a caller-side change with no plumbing.

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
- **C2 / E2 — the identity floor is TOKEN-BASED, which is one finding and was
  written as two** *(merged 2026-08-19)*. Forms under three characters and
  single-token are never scrubbed, and `_unknown_actor_label` strips only name
  and alias tokens — so a short or common-word name escapes the floor at one
  end, and a unique identity-bearing EPITHET in the appearance survives into the
  label at the other. `_COMMON_WORD_NAMES` is a separate, exact-case mitigation,
  not a fix. Both are the same channel and want the same answer: identity
  carried structurally on the event rather than matched out of prose (§4.2).
- **D1 residual — a paraphrase with a fresh explicit subject still escapes**
  `_redact_concealed_from_event`. The function's own docstring names this
  residual and names the structural answer: carry identity on the event.

*(E1 was struck 2026-08-19: `knows_identity` is WRITE-ONLY — set at six sites in
`agents/perception.py` and read nowhere — so the inconsistency it named with the
title-tolerant `_recognizes` (`agents/common.py`) cannot be reached. See §1.45.)*


### 3.2 Concealment gates not applied everywhere

- **X3 — `conceal_from` without `visibility: "concealed"` bypasses the
  background declaration filter**, which consults `visibility` only. Every other
  guard in `agents/background.py` fail-closes on `conceal_from` independently,
  precisely because models half-comply. *Latent, no test.*
- **X7 — half closed.** The player-input half is fixed: `pick_background_reactors`
  now qualifies a presence from `overt_declaration_text(ctx)` rather than
  `ctx.input`, with the reason at the call site (*"a whispered name used to
  qualify its own presence"*). What survives is the other reader in the same
  function — `resolved_event` is counted as a raw string with no concealment
  gate, so a concealed act the Director wrote into the beat's event text still
  raises a presence's pick priority (`persist/commit_background.py`).
- **X19 — `_llm_resolve_player_room` receives the private thought**, for a call
  whose only output is a position key.

*(Three bullets were struck 2026-08-19. **A8 residual** is deliberate, not open:
the channel is closed — `_p_disguise` is discarded at the `_composer_act` call —
and what remains is a tripwire whose own docstring says *"A WARNING, never a
scrubber."* **B4** (`_ensure_environment` does not check darkness) and **C3**
(stray view keys survive `_normalise_views`) both describe helpers with no
production caller; see §1.45's dead family.)*


### 3.3 Sense and awareness gaps

- **F4 residual — action delivery in the micro-loop is boolean visual rather
  than graded.** The sense-profile half landed: `agents/loops.py` reads
  `character_senses(observer_sheet)` and threads it into `_delivery_ok` and
  `sense_adjusted`. Speech is graded there; an action is still a yes/no gate
  followed by a whole sentence, so a half-seen act arrives entire or not at
  all, where a half-heard line arrives as a fragment.
- **Perception prose is not bound by the audibility layer.** Live data shows a
  view narrating "difficult to parse from this distance" while the deterministic
  layer had already ruled the speech fully audible. The deterministic layer is
  right; the prose should be CONSTRAINED by it rather than free to contradict
  it — same family as F4, and the same answer (the delivery verdict decides the
  sentence, not the other way round). *(Promoted out of §8 on 2026-08-19: it
  cites live data showing prose contradicting the deterministic verdict, which
  makes it a defect rather than an idea.)*
- **F6 / S3-A5 residual — `spatial.spatial_digest` still renders the authored
  room name behind every edge, including rooms never visited.** The perception
  payload was fixed (unseen edges keep their barrier, lose `to`/`to_name`);
  the digest that reaches the **narrator** was not, and the same digest is
  what every character navigates by (`agents/character.py`,
  `spatial_prose._annotate_known_exits`, which maps the rendered NAME back to
  a room id) — so matching perception's shape here is a change to that
  contract, not a one-line gate.
  **The directional half landed 2026-08-20**: an edge that is a wall only from
  THIS side is no longer rendered at all, so the blind side of a
  `one_way_window` stops naming the room behind it and the barrier keyword
  that says how it works (chat 78 t3 — see §1.68). Scoped to edges the
  observer-side resolution makes more restrictive than the record, because an
  adjacency declaring no barrier normalizes to `wall` for everyone and
  dropping those would take real exits out of every navigation payload.
- **F7 — `known_pronouns` releases pronouns on unverified mind-model keys.**
  `agents/character.py` keys off `set(relationships) | set(mind_models)`, which
  is the unvalidated set.


### 3.4 Multiplayer

All multiplayer-only — but **not** unreached, which is how this preamble used to
read: 135 `narrator_extra` steps across 3 chats (measured 2026-08-19).

- **S3-A6 — `narrator_extra` lacks the consciousness gate and fidelity facts.**
  It ships `spatial_frame` unconditionally and its payload has no
  `player_awareness` key, unlike the primary narrator path.
- **S3-B2 — extra players' speech has neither speaker guard.** `_player_aliases`
  covers the primary persona only.
- **S3-B4 — the interpret-stage split is unchecked for extras.**
  `_reconcile_interpretation` coverage-checks only the primary input.
- **X12 — the onset pass is primary-player-only**, so the reaction-gate and
  `targets` guarantees never run for extras' sequences at onset. *Degradation.*

*(X11 was struck 2026-08-19: it could not be verified against source, and
`perception_act` handles no extras at all — which changes the shape of the claim
rather than confirming it. If it is real it is a face of X12; re-raise it there
with evidence. X9 — the host reads co-players' private thoughts — is not a code
bug but a product boundary, and moved to `AGENTS.md` § Information boundaries
with the other deliberate keeps.)*


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
  `persist/chat_archive.py` resolves an archive integer against whatever local row holds
  that id, then attaches the archive's `chat_chars.state` to it. Memories are
  safe. Legacy path only.
- **P5 / P8** are defects, filed at §1.8 and §1.9.

### 3.6 Deliberately kept

Moved to [`AGENTS.md`](../AGENTS.md) § Information boundaries on 2026-08-19. It
is a keep-list by construction — each item pinned by a test asserting the
current behaviour — which makes it an INVARIANT rather than unfinished work, and
an invariant belongs where somebody about to change the code will read it. A7
and E3 were dropped in the move as overtaken: per-observer payloads mean the
perceiver set in `_state_reaches_anyone` is one name, and outcome extras'
hardcoded `knows_identity` is advisory against a field nothing reads (§1.45).


### 3.7 Test gaps

`tests/test_pipeline_audit_leak_gaps.py` covers D1, D2, B3, B5, X14, F1, F2/P1,
S3-A4, S3-A5, S3-A8, X18 and X4. **A1 still has no dedicated test**, and it is a
confirmed leak class. B4 was listed beside it until 2026-08-19 and is struck: it
names `_ensure_environment`, which has no production caller (§1.45's dead
family), so a test there would pin a dead path.

### 3.8 A structural risk, not a finding

`agents/perception.py` does **not** call `common._delivery_ok`; it uses
`hear_level` and `_in_plain_view` directly, while `agents/loops.py` routes
everything through `_delivery_ok`. Two families of delivery gate now exist and
can drift apart. Consolidating them is the cheap insurance.

### 3.9 Residuals of the alpha 6.3 physical-ledger work

Dissolved 2026-08-19 — every bullet had a better home and two of them were being
written twice:

- entity `state` has no ageing of any kind → **§1.10**, which is the same finding
  and now carries the measurement;
- a hover is not a contact, and an orphaned relational value is dropped rather
  than folded → **§1.28**, beside the rest of the contact-sensation residuals;
- a garment moving between bodies keeps no identity →
  [`design_notes/17-garment-displacement.md`](../design_notes/17-garment-displacement.md)
  § Left open;
- nothing derives a station from within-room movement INTENT → **§2.15**, which
  is where the within-room approach concept would have to come from.


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

**The tier itself has landed.** `mind/canon_provenance.py` carries the seven
dispositions verbatim — `imported_canon`, `resolved_fact`, `player_claim`,
`spatial_generation`, `character_belief`, `narrator_audit`, `inferred_mapping`
— under `PROVISIONAL`, with `outranks` claiming only that provisional sits
below all seven and deliberately declining to rank them against each other,
because nothing has measured that and inventing an order would be a decision
taken by accident. Wired into `world/gaps.py`, `world/offscreen.py`, `world/subjects.py` and
`world/living_world.py`; `tests/test_canon_provenance.py`.

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

Verified absent: no revision concept in `core/db.py`, `persist/commit.py` or `core/frames.py`.

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

Decompression-bomb limits are in `story/importers.py`. There is no upload or
content-length guard in `web/app.py`. Needed before the service is treated as safe
beyond a trusted local environment.

---

### 4.7 Does the engine grow a material model at all?

Moved to [`DESIGN_MATERIAL_MODEL.md`](design/DESIGN_MATERIAL_MODEL.md) on
2026-08-19. Displacement with no magnitude to order it (was §4.7) and two
spellings of one region on one body (was §4.8) are one undecided question about
MATTER, not two defects; the note holds both and the argument for keeping them
together.

**Addendum 2026-08-25 — the question was asked again and answered NO
MECHANISM.** A ledger-accumulation pass over four scene ledgers reached the
substance ledger and deliberately built nothing: no expiry timer, no cap, no
displacement, no region fold. The note's standing reasons hold (the amount
vocabulary is not a magnitude; conservation already means matter on a moved
body moves with it; the fold point exists but the ruling is world law the
engine refuses to hard-code), and `AGENTS.md` forbids the universal timer
outright.

What WAS built is addressability, because the measured cause of remove-op
disuse turned out not to be prompt wording: the specialist that owns
`substance_ops` had never been shown the standing records or their
`substance_id`s, so the removal its own sheet documents could not be written
at all. Its payload now carries both of its ledgers with their ids
(`world.spatial.substance_ledger_index` / `contact_action_ledger_index`), which
is what makes the note's prompt-efficacy hypothesis testable for the first
time.

Survey 2026-08-25, for whoever reopens this: 5 of 77 stored scene blobs carry
substance records at all, holding 10, 9, 9, 9 and 3 rows — and four of the
five are branches of one story. There is no runaway. Re-measure the 38-adds /
5-removes ratio on stories played AFTER the ids started arriving before
treating a missing mechanism as the explanation.


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
new optional list op, like `obligations`; persist in `persist/commit.py` with dedup and a
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

*Low severity, cosmetic.* On the turn a background presence promotes to cast,
the player's view can render it "the unfamiliar person" for one turn: promotion
runs at commit, after that turn's perception, so the canonical name is not yet
in the observer's `known` set. The alias/variant fallback (`_recognizes`) and a
full mutual roster in `promote_background_character` shipped; what remains is
that the roster registers only the canonical `character_name(sheet)` with no
aliases or variants, and that the **attach** path in `web/app.py` seeds only
player↔character, never cast↔cast. Test: promote a presence the player
addressed by name, assert that turn's view of it is not anonymized.

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
- **Location-themed population and the chorus presence (§4).** Not built and now
  with no artifact at all: `AggregateEntity` was declared in `llm/schemas.py`
  and consumed by nothing, and was deleted rather than wired. The design has
  neither an implementation nor a schema to point at.
- **The narrator dilution clause (§5)** — no tension-gated ambient suppression.
- **The `digest`/`interim` tier typology (§3.1)** — only `blurb` was built.
- **The prompt fix for §3.8** — a blurb tell should be available colour, not a
  required beat.

### 6.2 Extensions — [`EXTENSIONS_DESIGN.md`](design/EXTENSIONS_DESIGN.md)

**What shipped across five batches (9.0–9.6) is not listed here** — it was a
changelog inside a register. Disposition: `Design.md`'s **Third-party
extensions** row; developer surface:
[`docs/guides/EXTENSIONS.md`](guides/EXTENSIONS.md). Two things a reader of this
entry needs and would not find there: the Tier 0–3 ladder (story packs as rung
1) was **abandoned**, not deferred — design note §2 says why, so it is not debt
— and every refusal from the Directive review's hardening list carries its
argument in
[`DESIGN_FRAME_COHERENT_READS.md`](design/DESIGN_FRAME_COHERENT_READS.md)'s
"Refused" section. *(Collapsed 2026-08-19.)*

Still missing:

- **A model lane cannot be declared without Python.** `api.add_model_lane` is
  built, but declaring one happens in `register(api)`, so a data-only extension
  cannot have one — the smaller half of declarative advisor stages below. Nor
  can a lane ship a SUGGESTED model: a manifest choosing a model is an install
  choosing spend.
- **No BINARY/blob storage.** `api.documents` stores JSON only and refuses
  above 128 KiB, because a story document is a `world` row that rides every
  checkpoint. A large asset — image pack, audio, a multi-megabyte export — has
  no home surviving an extension update (`data_path` is replaced by re-clone).
  Deliberately left: the right shape (content-addressed like `memory_vectors`,
  or plain files outside story history) depends on whether the asset needs to
  ride checkpoints at all.
- **Declarative advisor stages** — a stage as data (role, prompt, input-scope
  whitelist, anchor) for authors who write no code. Genuinely useful; no longer a
  prerequisite for anything.
- **Pre/post hooks on `compute_step`**, and the two routing hooks that were
  designed alongside `on_character_payload` but not built: `on_admission` and
  `on_view`, which would let an extension alter what perception ADMITS rather
  than only what the assembled payload carries.
- **An extension still cannot reach the Director's PROSE AUTHOR**, though the
  narrator seam is built. A registered specialist family writes its channel to
  the merged `state_diff` and nothing narrates it *from there*; closing it means
  a prose-chunk registry with
  `test_every_delegated_block_has_exactly_one_owner` extended across the
  boundary. Deliberately left — the narrator seam already delivers the
  reader-visible result without touching a one-owner invariant.
- **`tools/project_check.py --extension <path>`** — the author-facing
  self-check. The checks exist and the AUDIT half has a Python entry point
  (`extension_runtime.audit_extension_source`); the lints have no way in from
  outside.
- **Phase 2: the reviewed registry.** Every field it needs (id, version,
  `sha256`, `provenance`, and now `source_url`/`source_ref`/`commit`) is
  already written at install time, so this is an addition rather than a
  migration.
- **A zip or folder install cannot be checked for updates.** Only a repository
  source has something to ask; an `ETag`/`Last-Modified` probe is cheap and not
  universally honoured, so it was left out rather than shipped as a check that
  is right most of the time. Reported as `checkable: false` with the reason.
- **Update checks are manual.** There is no periodic sweep and no notification
  badge; the host presses a button. A background check is a network call per
  installed extension on a schedule nobody asked for, and wants a rate limit
  and a stored last-checked time before it is worth having.
- **Scoped clients**, which is what would make third-party frontends real for
  non-host players: scoped stream and chat reads, `client`-scope tokens. A
  firewall decision, and it deserves its own design note before code.
- **Documents are not frame-scoped.** `api.state` has a per-era counterpart
  (`api.frame_state` → `extf:<id>`) and `api.documents` does not: a document
  row is `ext:<id>:doc:<path>`, which is chat-global like the namespace it sits
  in. A campaign holding per-era documents would need an `extf:` document
  store, and nothing has wanted one yet.
- **`extension_runtime/` is outside the UI catalog's reach.**
  `tools/extract_ui_catalog.py` scans root `*.py` and `agents/*.py`, so the
  dozen-odd registration errors surfacing in the Extensions menu are never
  harvested and never translated — while the four living in `agents/director.py`
  are, which would make one list four-sixteenths Japanese. Fix: add the package
  to the scanner and translate the set.
- **`Sonder._unload` cannot undo side effects**, only registrations and the two
  injected elements. A monkeypatched global, a timer or a `document`-level
  listener survives a disable. Inherent to the no-sandbox posture; stated in the
  guide so an author can compensate.
- **Two "absent means absent" edges in `player_view["people"]`.** A fact can
  only carry `authored_public` provenance today — nothing mines memories to
  affirm a `what_i_was_told` role, so experience-sourced facts stay absent
  rather than deduced — and a ledger name that resolves to no cast member or
  persona is omitted, because an unregistered presence has no stable id until
  promotion makes one.
- **The archive does not DECLARE its extension schema.** Export/import
  round-trips `ext:<id>`/`extf:<id>` state, char state and documents without a
  version or an enumeration, so an importer cannot tell a complete carriage from
  a partial one. Raised by the Directive hardening list; left until a second
  home exists, because a version number with one member is one nobody reads.
- **No read-snapshot token.** The same review asks for a read transaction so a
  DTO combining several domains cannot straddle a concurrent write. Not built,
  and deliberately not folded into the frame-coherence work, because it is a
  different axis: `at_frame` chooses an ERA, a snapshot would fix a MOMENT.
  `tests/test_extensions.py::test_no_capability_is_declared_for_work_that_is_not_built`
  names it as today's example of a capability that must not be declared.
- ~~The host's own `story_view`/`player_view` HTTP routes take no `frame`
  parameter.~~ **Built 2026-08-19.** Both routes take `frame`, omitted rather
  than defaulted when the caller does not ask — the underlying default is a
  sentinel meaning "the latest committed turn across every frame", and `None`
  is a different question that would be validated as a frame id. The entry
  said to wait for a consumer; the reason to build it anyway is that an
  asymmetry between two doors onto one room is its own defect: one surface
  could compose a frame-coherent read and its HTTP twin could not say which
  era it wanted.

### 6.3 Greeting-seeded openings — [`GREETING_IMPORT_DESIGN.md`](design/GREETING_IMPORT_DESIGN.md)

About 60% shipped in alpha 1.4, under a materially different architecture — the
narrator **does** run on turn 0 and its prose is overridden afterwards, rather
than the design's pre-baked variants plus resume. **The extraction's scope has
since outgrown this note**: what a greeting may put inside a MIND — beliefs,
stances, opening affect, for every person present rather than the card's owner
alone — moved to
[`DESIGN_GREETING_MINDS.md`](design/DESIGN_GREETING_MINDS.md) and is built
(extractor v2). Still unbuilt and still wanted:

- **Ingest-time extraction caching — the WRITE half only.** The read half
  landed with extractor v2: `story/greetings.py` stamps
  `extractor_version = EXTRACTOR_VERSION` where the extraction is MINTED
  (not where it is filed, so a copy made by an archive, an editor or a hand
  written card cannot claim a provenance it does not have), and
  `_usable_stored_extraction` replays a stored blob only if this extractor
  made it — unstamped means older than the stamp, and the stored blob is the
  one path into turn-0 seeding that never passes through today's schema.
  What is still missing is anything to replay: `story/importers.py` and the
  first-message fallback both write `"extraction": None`, so extraction runs
  lazily at launch and is discarded every time.
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
- **The verbatim-preservation invariant test.** The knowledge-boundary half of
  this pair now exists and is stronger than the design asked for —
  `tests/test_greeting_minds.py` pins the player-naming forced reveal in
  every mind, the identity floor on a stranger start, and the refusal of
  player affect/stances with the refusal made visible — but nothing asserts
  that imported greeting prose reaches the page byte-for-byte.

### 6.4 Place purpose — [`DESIGN_PLACE_PURPOSE.md`](design/DESIGN_PLACE_PURPOSE.md)

v1 is built. What was deliberately not built, each with its stated reason, is
that note's own "Not built, plainly" line plus the deferred own-memory-row
heuristic (signal 2). *(Restated here until 2026-08-19.)*


### 6.5 Place graph

The walkable-edge defect is §1.6; the redundancy watch is §1.12.

- **`basis: "told"` has no PLACE-GRAPH writer**, deliberately. Moved to
  [`DESIGN_PLACE_PURPOSE.md`](design/DESIGN_PLACE_PURPOSE.md) on 2026-08-19 —
  testimony can say what a place you already know is FOR; it cannot mint the
  place, and a future testimony writer needs a structured claim field, not a
  parser over prose.
- **Do not remove the three-valued frontier semantics.** `_frontier_hops` returns
  `None` (spent), `0` (live but unmeasurable), or `N`. The middle value exists for
  saves written before the graph — a walked room with no recorded exits can
  honestly be called neither spent nor near. It is not defensive padding; removing
  it would make old saves read as exhausted.
- **Live sight correctly outranks the remembered gradient.** Recorded because it
  looked like a gap and was not: `visibly_no_way_through` pre-empts the distance
  verdict via the existing `_VERDICTS` precedence, which is the right order.

### 6.6 Psychology as pressure — [`DESIGN_PSYCHOLOGY_AS_PRESSURE.md`](design/DESIGN_PSYCHOLOGY_AS_PRESSURE.md)

(a) and (b) shipped; (e) declined by design. Open: (c) deterministic inclination
beside the raw sheet, and (d) a trait as a disposition rather than a switch —
both argued at length in that note under their own letters, including the
constraint that (c) must RELOCATE salience rather than add it. *(Restated here
until 2026-08-19.)*


### 6.7 Long-term goals — [`DESIGN_LONG_TERM_GOALS.md`](design/DESIGN_LONG_TERM_GOALS.md)

v1–v3 are built, including goal-slot currency. The three undecided questions —
whether a renewed intention should cost something, whether displacement should
feed the drive-strain ledger, and whether drive and project both weighing 1.0
needs revisiting — are that note's "Not yet decided" list. *(Restated here until
2026-08-19.)*


### 6.8 Living world — [`DESIGN_LIVING_WORLD.md`](design/DESIGN_LIVING_WORLD.md)

Phase 1 (branch `living-floors`) built the deterministic floors of A
(`world/routines.py`), B (`living_world.mint_consequences` +
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
  since landed as `story/couriers.py` (positions on `passable_path` routes,
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

The card field, the `region_visibility`-gated delivery, the Director payloads
and the editor menus are built; what was deliberately not built is that note's
"Residuals" list. *(Restated here until 2026-08-19.)*


### 6.11 Garment displacement — [`../design_notes/17-garment-displacement.md`](../design_notes/17-garment-displacement.md)

Region-grain displacement is built; what is left open — left/right asymmetry,
transparency, and retro-repair of stale displacement prose — is that note's
"Left open" list, with each item's argument above it. *(Restated here until
2026-08-19.)*


### 6.12 Scent — [`DESIGN_SCENT.md`](design/DESIGN_SCENT.md)

v1 is built; the five things deliberately not built — decay, travel and drift,
multi-hop reach, an entity's smell never attributed, and whether a body receives
its OWN card scent — are all in that note (§5, §6, and §7's closing paragraph),
each with the argument for leaving it out. *(Restated here until 2026-08-19.)*


### 6.13 Paradox consequences — [`DESIGN_PARADOX_CONSEQUENCES.md`](design/DESIGN_PARADOX_CONSEQUENCES.md)

All three decisions in that note are built; its three deliberately-open edges (a
warden outliving the wound it guards, cross-frame scenes, a toll with no restore
path) live in the note's §5, not here. None is urgent for the reason the note
records: no live story has ever opened a paradox. *(Restated here until
2026-08-19.)*


### 6.14 Close-contact causality — [`CLOSE_CONTACT_SCENARIO_AUDIT_2026-08-23.md`](experiments/CLOSE_CONTACT_SCENARIO_AUDIT_2026-08-23.md)

Alpha 9.8.1 landed the phase/dependency floor, typed communicative acts, typed
referents, contact actions and substance conservation this audit asked for.
Three residuals survive it, all genre-neutral and all stated in the audit's
own words:

- **A typed observation/result ledger.** A test whose finding gates a later
  action still has no record with an id, observer, subject, method, bounded
  finding, time and provenance for a conditional phase to reference. Branch
  truth is therefore read out of prose, which is the audit's weakest measured
  judgment (the surgical arm can still proceed after a finding falsifies an
  explicit "only if"). The same ledger serves a surgeon checking numbness, a
  mechanic testing pressure, a dancer checking balance, a hacker validating
  access, and a fighter checking whether a grip took.
- **Deterministic contact-bound pose invalidation is only partial.**
  Support/pin/grapple facts are dropped when their contact ends; a stale
  *detail* fragment (`underhook`) can still survive one evidence beat while a
  replacement (`overhook`) is established, so contact refinement remains less
  exact than the prose that produced it.
- **Durable procedure results and device state.** A splint, dressing,
  anesthetic, finding or aftercare plan is still reduced to a generic
  condition or to prose, so a material procedure leaves no typed thing a
  later beat can check.

Also open from the same run: direct-object and instrument pronouns
(`kisses her`, `takes Alice's hand with her left hand`) are solved by the
compatibility anaphora repair rather than by typed referents, which exist but
are not yet emitted on every action surface.


## 7. Experiments not yet run

Moved to
[`docs/experiments/MEASUREMENT_BACKLOG.md`](experiments/MEASUREMENT_BACKLOG.md)
§1 on 2026-08-19. An unrun experiment is unfinished work, not a broken thing —
which is the argument for keeping it with the evidence rather than in a defect
register.


## 8. Parked

Not scheduled, not committed to a phase. Kept so they are not lost and not
accidentally built. Four feature WISHES that were here — salience-driven
personal lore, per-character retrieval depth, belief-revision salience and an
optional minimap — moved to [`docs/design/IDEAS.md`](design/IDEAS.md) on
2026-08-19; a wish is not a defect, and one earns its way back here only by
someone measuring a live story where its absence makes the engine wrong.

- **`providers.chat_complete_async` is dead.** Defined and called from nowhere
  but its own retry loop — `web/app.py` no longer imports it either, so the
  only three references in the tree are its own definition, its recursive call
  and `_chat_complete_async_once` (`llm/providers.py`). The threading model
  works and the `contextvars` discipline is built around it, so the
  recommendation is to delete the function rather than build on it.
- **`llm/prompt_cache.py` is dead** — no importer anywhere — and its
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
- **Perception prose bound by the audibility layer.** Live data shows perception
  narrating "difficult to parse from this distance" while the deterministic layer
  had already ruled the speech fully audible. The deterministic layer is right;
  the prose should be constrained by it rather than free to contradict it.
- **Remove the deprecated macro schema.** `fiction_worlds`, `fiction_locations`
  and `transit_edges` are dead — nothing in the runtime reads or writes them — but
  they are still created, snapshotted, restored and exported. Removal is planned
  and needs a migration.
