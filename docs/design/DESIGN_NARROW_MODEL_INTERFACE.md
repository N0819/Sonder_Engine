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
