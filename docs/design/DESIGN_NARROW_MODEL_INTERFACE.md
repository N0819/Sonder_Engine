# The narrow model interface

Status: proposed. Evidence: `docs/experiments/PROMPT_LATENCY_2026_09_09.md`.

**The objective, in the owner's words: simplify the code's interface with the
LLM as much as possible while still allowing the full feature set.** The ask of
each stage should be the briefest statement of its role and its output shape;
everything a rule could say, a category should say instead, and code should
sort the categories.

This note establishes where that is possible, where it is not, and what has to
move into code before a sentence may be deleted from a sheet.

## 0. How much does a stage have to understand?

The question this design turns on: does a stage need to understand the system
it operates, or only what to hand back? Measured against the one sheet read
line by line -- the shared specialist core, 8,470 chars:

- **581 chars (7%)** say what you are and what you keep. The role.
- **7,889 chars (93%)** are the system. Which of two Director stages this call
  serves. That perception and every later turn render from committed structured
  state, never from prose. That a hold you fail to record does not exist. How
  to echo `event_id`s back so the engine can compose the beat without asking
  anyone twice. How to answer 'not_mine', and which of five hands to forward
  it to. What the engine will do to your output after you send it.

Every line of that 93% is true, and nearly all of it was earned by a live
defect. The claim of this design is narrower than "it is wasted": it is that
**almost none of it changes what the model should write.** A hand told "a hold
you fail to record does not exist" and a hand told "record every hold" emit the
same JSON. The first costs 0.29s per thousand tokens to say, on a call whose
entire answer is 77 tokens.

That is a hypothesis, not a measurement, and it is exactly what the pilot in
§6 exists to test -- because the honest counter-argument is that stakes and
consequence are part of how a model decides, and a sheet stripped to a schema
may encode less carefully rather than more briefly. The pilot answers it on the
same beats, not in the abstract.

The exception is where downstream consequence changes the ANSWER rather than
motivating it -- `erogenous` is the clearest case, and §4(d) is the list.

## 1. What the interface costs today

Measured over 146 complete turn-runs (evidence note, § 1-2). A median turn is
91.2s of model wall clock over 12.7 calls that buy 1.07x concurrency. The
Director's five specialists emit **43-222 tokens each against 8-9k token
sheets** and fit `duration = 1.8s + 0.29s per 1k input` on the shared default
model. They are prefill-bound: the ask is already almost nothing, and the cost
is entirely what they READ.

Hand-classified, the shared specialist core is **581 of 8,470 chars of role and
7,889 chars of everything else** -- which of two Director stages this call is,
how to echo `event_id`s back, how to say an event is not yours and name whose
it is, a five-hand routing table, and paragraph after paragraph of the engine
describing repairs it performs on the output regardless. Six of its ten
paragraphs exist ONLY because there are five hands. They do not shorten under
this design. They disappear.

## 2. The ledger already exists

`AssertedChange` (`llm/schemas.py`) is a flat entry with a `category` type tag,
a `subject`, a one-sentence `change`, and optional structured fields.
`_CATEGORY_CHANNELS` (`agents/director_scopes.py`) is the code that sorts a
category into a channel. Both exist today only to decide WHICH SPECIALIST TO
CALL. The proposal is to promote the ledger from a dispatch hint to the output
itself.

This is not the fan-out-versus-monolith experiment `director_scopes.py`
records, and the distinction is the whole design. The monolith asked one mind
for **39 typed channel shapes**; that is why its sheet was enormous and why it
lost. This asks for **one shape with a type tag**. The sheet shrinks because it
teaches one thing, not because it teaches less carefully.

Measured, what a hand adds over the entry that dispatched it is frequently one
field. Turn 4162, contact:

| the ledger already said | the hand replied, 10.3s and 9,919 input tokens later |
|---|---|
| `actor: Hinami, actor_part: buttocks, target: sand_shelf, target_part: surface` | the same four fields |
| `change: "…ending sitting contact."` | `op: "remove"` |

## 3. The boundary: events reduce, records do not

Twenty-five of the 39 declared channels appear in live output. They are two
kinds of thing, and conflating them is how a reduction quietly loses a feature.

**Event-shaped channels** are lists of things that happened: `contact_ops`,
`contact_action_ops`, `substance_ops`, `inventory_ops`, `comms_ops`,
`sensory_events`, `introductions`, `telling_ops`, `crowd_ops`, `courier_ops`,
`artifact_ops`, `consequences`, `public_evidence`, `cast_changes`. A flat
ledger entry carries these natively -- most of their fields are already on
`AssertedChange`, and what is missing is small and shared: `op` (wanted by 5
channels), `relation` (4), `source` (4), `kind` (4), `motion`, `manner`,
`source_part`.

**Record-shaped channels** are maps keyed by subject describing a whole
record: `rooms`, `entities`, `conditions`, `attire`, `poses`, `stations`,
`overlays`, `vitals`, `containment`, `scales`, `time`, `weather`, `positions`.
A `rooms` entry can carry name, desc, adjacent, anchors, size, light, exposure,
extent, shape and parent_entity. `{category, subject, change}` cannot hold that,
and pretending otherwise is how the light field or a room's anchors go missing.

**But a record-shaped channel is only ever written when something CHANGES, and
the change is nearly always one field.** A beat that closes a door writes
`light`, not a room. So the reduction survives as a triple: the ledger entry
carries `subject` plus the field and its value, and code assembles the record.
The full record shape is needed exactly once -- at creation -- and creation is
already a distinguishable category.

So: **one entry shape, `{category, subject, change}` plus the ten recurring
named fields plus an open `props` map, routed by category.** One shape to
teach. Thirty-nine destinations for code to sort into.

## 3a. The compression is concept -> category, and the grammar delivers it

The owner's sharper statement of the whole design: **the biggest optimization
is compressing concepts into categories.** It is testable, and it holds.

Across the 32 specialist chunks there are 45 capitalised rule lead-ins -- the
sheets' own unit of "here is a concept you must understand". Classified against
what the schema already names:

| | n | |
|---|---|---|
| names a field or enum value on the chunk's own `Shape:` line | 21 | 47% |
| names an existing enum value under a different spelling | 6 | 13% |
| names a field, spelled as prose | 6 | 13% |
| compresses to a code guard | 6 | 13% |
| genuine boundary judgment, irreducible | 4 | 9% |
| exhortation to comply -- not a concept at all | 2 | 4% |

**39 of 45 (87%) are a category, a field, or a guard wearing a paragraph.**

The clearest cases are the ones where the prose is a single enum value's
definition written out longhand, on every call, forever:

- *"CROSSING AN ENDPOINT IS AN EXPLICIT TRANSITION, NOT A REPHRASE"* -- ~700
  chars defining `op: 'cross'`.
- *"AN ENVELOPMENT IS RECORDED FROM THE ENCLOSED SIDE"* -- ~400 chars defining
  `relation: 'interior'`, on a record the engine folds to that side anyway.
- *"CLOTHING IS THE LAYER BETWEEN TWO SURFACES, NEVER ONE OF THEM"* -- ~700
  chars saying: put it in `detail`.
- *"WHICH SIDE OF THE FIXTURE"* -- the two field names `at` and `near` ARE the
  concept.
- *"NINE OF THOSE KINDS ARE THE UNDERTAKING LEDGER'S WHOLE VOCABULARY"* -- a
  closed set the engine owns, which is a schema enum by `CLAUDE.md`'s own
  definition, currently spelled as a word list in prose.

**And this is where the missing grammar (§5) stops being a separate workstream
and becomes the delivery mechanism for the compression itself.** A category
name is a compressed concept only if the name actually reaches the model as a
constraint. `op: 'add'|'remove'|'clear'|'cross'` inside a JSON grammar is
enforced -- the model cannot emit anything else, and the word carries its own
meaning. Sent as prose to a model with no grammar, it is a suggestion, so every
value has to be argued for at length and the model still invents `pressure`,
`grip_quality` and `my_part`. The engine is currently paying for the longhand
BECAUSE it stopped sending the shorthand.

Two of the 45 deserve their own note: *"AND YOU MUST ACTUALLY WRITE IT"* and
*"AND YOU MUST ACTUALLY MOVE THEM"*. Those are not concepts, they are the sheet
asking the model to please comply -- which is the signature of a missing guard,
not a missing explanation. Where a sheet begs, write the check.

The irreducible four are worth naming because they are the real floor, and it
is low: *an announced plan is dialogue* (saying you will do a thing is not
doing it), *when someone steps out of a crowd*, *what counts as public
evidence*, and *what a room's size buys*. Each is a boundary between two
categories that a mind draws and a table cannot.

## 3b. How bare can the question get, and the test for a category

The end of this road is a stage whose whole ask is a plain question -- **"what
makes sense to happen?"** -- with the schema carrying the shape and code
sorting the answer. For the prose author that question IS the job. For a
bookkeeping hand it is "what changed?". For a character, "what do you do?".

It works exactly to the degree the model shares the engine's conception of the
categories, and that is the constraint worth stating plainly, because it is
where a naive version of this fails. Asked bare, a model answers in prose.
Prose then has to become categories either by CODE reading it -- which
`CLAUDE.md` records failing four separate ways on 2026-08-29, each in whichever
direction its missing word pointed -- or by the model filling a grammar. So the
bare question is viable **paired with a grammar and not otherwise**: the
question supplies the intent, the grammar supplies the structure, and neither
alone is enough.

Which yields the test for whether a concept may become a bare category:

> **Does the word already mean this to a mind that has read the fiction?**

Where it does, the name carries the concept and the paragraph is deletable:
`cross`, `remove`, `interior`, `settled`, `moving`, `at`, `near`. A model needs
no instruction to know that `op: 'remove'` on a contact means the hold ended.

Where it does not, the paragraph is not explaining a rule -- it is defining
engine jargon, and the fix is to **rename the category until the paragraph is
unnecessary.** `amount_band` requires a paragraph. *a trace / a smear / a
soaking* requires none. `salience` requires a paragraph. *who would repeat
this* requires none. That is the compression done properly: not a shorter
explanation of the same name, a better name that needs none.

This also gives the reduction a stopping rule. A sheet is finished when every
remaining sentence is either the role, a field only a mind can fill (§4d), or
one of the four irreducible boundaries in §3a. Anything else is a name that has
not been chosen well enough yet.

## 3c. The Director should not know its specialists exist

The proposal that makes the rest of this cheap: **the Director emits a
categorized ledger and nothing else; code routes categories to hands.** It does
not require winning the fan-out-versus-monolith argument again. The hands stay.
They simply stop being addressable, and every sentence on both sides about
who-is-whose disappears with the addressing.

The Director currently rules to its bookkeepers through TWO fields:
`ledger_notes`, keyed by hand or channel, and `changes_asserted`, keyed by
category. `_specialist_addressed` dispatches a hand when EITHER names it. So
the model is doing the routing twice, in two vocabularies.

**Measured over 374 prose-author rulings, the two disagree 82% of the time.**

| | n | |
|---|---|---|
| hands named by `ledger_notes` == hands implied by `changes_asserted` categories | 68 | 18% |
| **disagree** | **306** | **82%** |
| ...notes name a hand no category implies | 289 | |
| ...a category implies a hand notes never named | 33 | |

The asymmetry is the whole story. **The notes are broader than the categories
289 times to 33** -- the model names more hands than its own manifest justifies,
dispatch fires on the union, and the extra hands are handed a beat with nothing
in their channels. That is where §1's empty rate comes from: `director_objects`
87% empty, `director_body` 76%. **The dispatch is not over-permissive by
accident; it is routed by a model's opinion about hands instead of by its own
categories, and the opinion is consistently wider.**

Fifteen more notes were keyed by a CATEGORY name (`substance`, `pose`,
`contact_action`) where a hand or channel name was expected -- the model mixing
the two vocabularies it was given, which is what happens when a system asks one
mind to hold two naming schemes for the same fact.

This is the engine's own most productive question answered against itself: the
same routing decision is stored twice and the two copies are free to disagree,
so they do, 82% of the time. Deleting `ledger_notes` and routing on
`changes_asserted` alone removes a whole vocabulary from the Director's sheet,
removes the five-hand table and `reroute_to`/`not_mine` from all five
specialist sheets, and makes dispatch deterministic -- which is a correctness
fix that happens to also be the latency fix.

Turn 4162 shows the failure end to end: the manifest filed "sand brushed from
her travel shorts" as `conditions`, `ledger_notes` addressed it to `objects`,
and the contact hand independently re-derived it as a fourth `contact_ops`
entry nobody asked for. One change, three routings, no two alike.

## 3d. Compress engine terms into concepts, and let code dissect them

The owner's last requirement, and the one that makes "what actually happens?" a
viable ask: **the engine's terms should become concepts that need no
explanation, and code should dissect and route them.** A stage's attention then
goes to the beat instead of to the vocabulary.

The constraint that keeps this honest: a plain term must still be a CLOSED SET
THE ENGINE OWNS, or code cannot dissect it and we are back to reading free prose
-- the failure `CLAUDE.md` records four ways on 2026-08-29. This is not a move
from enums to prose. It is the same enums, spelled so the name carries its own
meaning. `CLAUDE.md` already licenses exactly this: a closed set the engine owns
and can enumerate is a schema; what it forbids is a list trying to anticipate
how English will phrase something.

**The ask.** One question, and a list of what changed:

> What actually happens? Then: what is different now that was not before?

**The kinds.** `changes_asserted.category` currently carries ~20 values that are
channel names (`cast_changes`, `contact_action`, `remove_adjacent`). A mind
answering "what is different now" does not think in channels. Eight kinds cover
the delegated channels, and code maps kind-plus-fields onto the 39:

| kind | what it means | routes to |
|---|---|---|
| `touch` | who is holding, pressing, inside or against what | contact_ops, contact_action_ops, containment |
| `mess` | matter that moved and stayed moved | substance_ops |
| `clothing` | what someone is wearing, or no longer is | attire |
| `body` | what afflicts, marks or is spent on a body | conditions, vitals, overlays, scales |
| `thing` | what exists, is carried, is broken | entities, inventory_ops, destruction, artifact_ops |
| `place` | where bodies are, how they are arranged, what a room is | positions, rooms, poses, stations, adjacency |
| `people` | who arrived, left, or learned a name | cast_changes, introductions |
| `word` | speech with a consequence that outlives the beat | telling_ops, crowd_ops, courier_ops, comms_ops |

**The terms.** Each row is a paragraph the sheet no longer has to carry:

| today | as a concept | the paragraph it replaces |
|---|---|---|
| `op: 'add'` | `began` | -- |
| `op: 'remove'` | `ended` | "CONTACT PERSISTS until you end it" |
| `op: 'clear'` | `let go of everything` | -- |
| `op: 'cross'` | `pushed past` | "CROSSING AN ENDPOINT IS AN EXPLICIT TRANSITION", ~700 chars |
| `relation: 'surface'` | `against` | -- |
| `relation: 'interior'` | `inside` | "AN ENVELOPMENT IS RECORDED FROM THE ENCLOSED SIDE", ~400 chars |
| `motion: 'settled'` | `still` | "ALWAYS emit both. They answer different questions" |
| `actor_part` | `with` | as in *touched it **with** her hand* |
| `target_part` | `on` | as in *rested **on** his shoulder* |
| `target_interior` | `enclosed by` | the target_interior/target_part distinction paragraph |
| `erogenous` | `arousing to them` | still needs its one sentence -- it is irreducible |
| `amount_band` | `how much: a trace / a smear / a soaking / a flood` | its whole definition |
| `salience` | `who would repeat this` | its whole definition |
| `poses.support` | `held up by` | -- |
| `poses.constraint` | `cannot move because` | -- |
| `rooms.exposure` | `open to the sky` | -- |
| `entities.ubiquitous` | `everywhere in this world` | -- |
| `conditions.severity` | `how bad` | -- |

**And the terms that should not reach a model at all.** These are bookkeeping the
engine assigns, echoes and links; every sentence teaching them is a sentence
about the machine rather than the beat:

`event_id` -- the engine numbers the manifest in narrated order already
(`_manifest_items` assigns it, "never by the model").
`resolved_events`, `phase_sources` -- the echo-back that only exists so dispatch
can tell an answered id from an unanswered one; with code routing there is
nothing to echo.
`contact_ref` -- code links an effect to its relation.
`reroute_to`, `not_mine` -- gone with §3c.

**The test for any row of this table**, from §3b: does the word already mean this
to a mind that has read the fiction? `pushed past` does. `cross` does not,
which is why it costs 700 chars. Where a proposed concept still needs a
paragraph, it is not compressed yet -- keep renaming, do not start explaining.
Where the concept is genuinely irreducible, keep one sentence and no more; the
measured list of those is four boundaries plus `erogenous`.

## 4. What must move into code before a sentence is deleted

`AGENTS.md` already states the test: **whose fault would a failure be?** A
model DECLINING to cooperate producing a bad state is code's job; a model not
KNOWING something is the sentence's job. Applied to `contact_ops` (12,440
chars), every rule falls into one of four buckets.

**(a) The engine already does it; the sentence is the engine describing
itself.** Garment-as-party is repaired; envelopment is folded onto the enclosed
side; duplicate ops are collapsed; contact left in entity state is lifted out;
a cross that matches no standing endpoint is rejected; re-asserting a part
retires its old spot; contacts between separated bodies are dropped. ~3,000
chars. **Delete on sight -- with one check, below.**

**(b) Code can decipher it from the sentence the ledger already carries.** `op`
("…*ending* sitting contact" -> remove), `manner` (already "one concise
physical verb"), and largely `relation`/`motion`.

**(c) Code must enforce it as a floor, not ask for it.** "The player's own body
acts only when the player said so" is firewall-class. It becomes a validation
rule, not a paragraph.

**(d) Genuinely irreducible -- only a mind can fill it.** `erogenous`. The
sheet says so itself: *"yours to judge, and nothing else can."* It depends on
the anatomy this fiction established for this body, and there is no table that
answers it.

**THE CHECK THAT MAKES (a) SAFE, and it is not optional.** A sentence saying
"the engine drops X" may be deleted only if the engine REPAIRS X. Where it
drops, the sentence is the only thing preventing silent data loss, and deleting
it converts a repair into a hole. Every rule cut must be traced to the guard
that makes it unnecessary, and where no guard exists the guard is written
FIRST. These rules are a graveyard of live defects; the commit that removes one
is the commit that must prove it cannot come back.

## 5. Do the schema work before the prompt work

`providers_no_json_schema` in the owner's settings contains
`google/gemini-3.8-flash` -- **the model every Director specialist inherits
from `default`.** It arrived there through `_note_json_schema_stalled`: the
grammar was accepted and then never answered, repeatedly, so the engine stopped
sending one.

**Every specialist call therefore runs with no JSON grammar at all.** That is
why 9,154 chars of prose `Shape:` lines exist across 32 chunks, and why much of
the surrounding prose exists -- there is nothing structural to lean on.

It shows in the output. Live specialist responses contain field names that are
in no schema: `pressure`, `grip_quality`, `my_part`, `their_part`, `through`,
`visibility`, `contact_type`, `contact_id`, `target_entity`. Pydantic's
`extra='ignore'` strips them (`llm/schemas.py` already carries a comment about
an earlier instance of exactly this), so the model is inventing keys and the
engine is silently discarding what they carried.

Retest the stall before rewriting a word of prompt. If that model answers a
grammar now, the output shape leaves the token budget entirely and the invented
keys stop, which is a larger simplification than any prose edit and does not
risk a behaviour change.

## 6. Order of work

1. **Retest the `json_schema` stall** on the current default model. Settings
   change, no behaviour risk, and it may remove the need for §3's prose shape
   entirely.
2. **Pilot one hand: `director_contact`.** It sets the specialist batch clock
   44% of the time and is the one call that does not fit the cost model (7.6s
   against a fit of 4.5s). Trace each rule to its guard per §4, keep the old
   sheet behind the preset system, A/B on the same beats, report wall clock and
   correctness.
3. **Grow the ledger entry** by the shared fields in §3 and route by category.
4. **Collapse the specialist phase** once the entry carries the event-shaped
   channels. This is where the ~15s/turn is: the phase is serial after the
   prose author, not concurrent with it.

## 7. What this does not fix

The character stage is 37.7s, 41% of the turn, and decode-bound at 2,520 output
tokens. Its `self` payload is **14,193 tokens, larger than its own 13,846-token
sheet**, with `memory` a further 5,158. No amount of sheet brevity reaches it.
It has its own reductions available -- nine of its 27 output fields are filled
on 1% of calls or fewer and three never -- but 51% of its output is `appraisal`
and `active_state`, which is the engine's product and not its fat.

## 8. Standing risks

- A reduction is real only if it still says everything the children said. Write
  down the case each deleted rule was written for and check the merged sheet
  states it; a case surviving only by implication is a dropped case.
- A ledger entry that fits a channel imperfectly must not be routed by
  approximation. `_CATEGORY_CHANNELS` currently reaches no channel for several
  categories; an entry reaching no destination must be reported, never dropped.
- Every deletion is a behaviour change to every story, not an edit. Watch the
  beats after each one for what it licensed.
