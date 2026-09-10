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

## 3c-bis. CORRECTION: section 3c is right and out of order

Replayed 2026-09-09 against every captured Director ruling, through the real
dispatch predicate (`tools/dispatch_replay.py`). **Section 3c as written would
lose 178 productive specialist calls -- 38.3% of all the real work the hands
did.**

| categories-only dispatch, all beats | n |
|---|---|
| specialist calls scored | 1,156 |
| still dispatched by a category | 168 |
| skipped, hand had returned nothing (saved) | 276 |
| **skipped, hand HAD returned content** | **178** |

That is not a tuning problem. A hand that is not dispatched gets no prompt, no
payload and no output surface, so each of those 178 is a change some mind could
have observed that no ledger would carry.

**Why**, and it is one cause, not a scatter: **96% of the false negatives are
beats where the author filed no manifest at all.** Not a vocabulary gap -- zero
categories reached no channel. The manifest simply was not there, and
`ledger_notes` was carrying the entire ruling.

Counted directly over 416 prose-author outputs:

| | |
|---|---|
| manifest + notes | 28.6% |
| manifest only | 2.2% |
| **notes only** | **59.1%** |
| neither | 10.1% |
| **`changes_asserted` ABSENT** | **69.2%** |

And by stage: present on 56.9% of `director_resolve` outputs, and on **0.0% of
184 `director_interpret` outputs.**

Zero, because **`DirectorInterpret` HAS NO `changes_asserted` FIELD.** Checked
against the live schema: it declares `ledger_notes` and no manifest. So at
interpret there is no categorized ledger to route on, and routing by category is
not risky there -- it is impossible. Half of the design's own premise, that "the
ledger already exists", is true only at resolve.

**When a manifest IS filed, the design holds.** Restricted to those beats, the
false-negative rate is **2.9% (8 of 278 productive calls)**, and the diagnostic
puts all eight in one bucket: the manifest covered other hands and not this one.
That is manifest INCOMPLETENESS, which is a fixable property of one output, not
a wrong routing principle.

So the design is not refuted. It is out of order, and the corrected order for
the Director stages is:

1. **Give `DirectorInterpret` a `changes_asserted` field, and ask for it.**
   Until interpret writes a categorized ledger, it can only rule by addressing
   hands -- the exact thing 3c exists to delete.
2. **Get it filled every beat.** 69.2% absence is not the author being lazy;
   nothing requires the field, which is section 5's grammar question wearing
   its consequence. This is now the second place the stall blocks the design.
3. **Re-run `tools/dispatch_replay.py`. The gate is zero false negatives**, and
   the useful second run is `--filed-only`, which asks whether the manifest is
   COMPLETE rather than whether it is PRESENT. Conflating those two is what made
   3c look safe here in the first place.
4. **Only then remove the `ledger_notes` trigger.**

One limit on all of the above, stated because it bounds the numbers: the replay
reconstructs the dispatch view from captured output, which carries
`ledger_notes` and `changes_asserted` and not `pressure_ticks` or whatever
`_specialist_views` adds. 534 of the 1,156 calls were addressed by something it
cannot see and are excluded rather than counted. Read it as a lower bound on
today's dispatch and a directional read on the alternative.

The 82% self-disagreement in section 3c stands and still argues for one router
rather than two. What this correction adds is that the router which survives has
to be the one that is actually always there -- and today that is the notes, not
the categories.

## 3c-ter. THE BEATS: the manifest was filed, and named the wrong thing

Item 4 of section 6 ran on 2026-09-09. Twelve interpret beats, played live on
`google/gemini-3.8-flash` -- the model the owner's `agent_models` actually
points the Director at -- into a scratch database, provider rows mirrored
read-only from `engine.db` so the configuration under test is the shipped one.
Zero errors. Harness: `tools/interpret_beats.py`.

**It plays the interpret half and nothing else, on purpose.** What
`dispatch_replay` scores is one `director_interpret` step, which already fans
out to the prose author plus all five specialists; perception, every character,
resolve, the narrator and the off-screen rungs are most of a turn's wall clock
and contribute nothing the replay reads. Capture is flushed at each step's own
persist point rather than at the turn's commit, so stopping the pipeline at the
interpret step keeps its rows. Six calls a beat instead of about twenty.

What it costs, stated because it bounds every number here: nothing commits, so
the scene never advances and each beat's interpret reads the same world. That
makes it a poor STORY and a fair DISPATCH sample. The beats span the manifest's
category vocabulary rather than following one another -- which a linear
playthrough would not have done either.

### The result

The field WORKS. The author filed a manifest on **8 of 12 beats**, and the
entries are good: `"Corin has taken off his sword belt."`, `"The door between
the forge and market_square is shut."`, `"Corin is kneeling."` -- accurate,
scoped to one change each, and correctly ABSENT on the two beats that deserved
nothing (a question asked, and an attempt to take a ledger from a man's hands,
which is contestable and belongs to resolution). Section 3c-bis predicted the
field would be filled once it existed. It is.

**And every single entry routed to nobody.** `--filed-only` scored **8 false
negatives, 100% of productive calls.**

The cause is one word wide. The author used four category words --
`body`, `objects`, `spatial`, `contact` -- and three of the four are not in
`_CATEGORY_CHANNELS` at all. They are the names of the five SPECIALISTS.
`contact` routed only by coincidence, being both a hand's name and a category
alias for `contact_ops`.

**The model was doing exactly what the sheet told it.** The paragraph asked for
"`category`, one of the ledgers named above", and the only names above it are
the five hands, one line earlier, in `ledger_notes`'s own enumeration. The
sheet taught one closed vocabulary and the router accepted a different one, and
nothing in four places' worth of guards noticed, because the four-places rule is
about whether a FIELD is declared -- not about whether its VOCABULARY is.

That is the rule's blind spot, and it is worth stating on its own: **a field can
be present in every place the guard checks and still be unroutable, because a
key and its value space are declared in different places and only the key is
checked.**

### The fix: accept the vocabulary the sheet already teaches

`manifest_category_targets` (`agents/director_scopes.py`), read by dispatch
(`_ruling_for`) and by the payload slice (`_specialist_manifest_slice`).

The asymmetry it removes was never intentional. `note_key_targets` resolves a
`ledger_notes` key through hand names, retired hand names, channel names, plural
tolerance and the pack's own aliases, and its docstring calls itself "ONE
RESOLVER, read by dispatch". The manifest path beside it read `_CATEGORY_CHANNELS`
raw -- no hand names, no aliases, not even `.casefold()`. One field's vocabulary
was four times the other's and the resolver's own docstring said otherwise.

Given a choice between teaching a second twenty-four-word vocabulary to every
story and letting code accept the one the sheet already teaches, this takes the
second. It is the cheaper half, it is the half that does not grow a prompt, and
it is what section 0 argues the engine is for: the hand's name is a legitimate
answer to "which ledger", just a coarser one.

Coarser is the whole cost, and it is bounded. A category naming a CHANNEL grants
that channel. A category naming a HAND grants the hand its story's channels, by
the rule `_dispatch_specialists` already follows for a note keyed by hand alone
-- "a ruling that reached it is better evidence than a prediction that nothing
there could change". Fail-open, exactly as that gate already is.

Union, not fallback, and `contact` is the case that needs it: `note_key_targets`
stops at the first kind that matched, so resolving through it alone would have
dropped `contact_ops` -- the one channel the manifest had been naming correctly
all along.

**After: 0 false negatives, and 6 of 19 calls (32%) still saved.** The prompt's
misleading half-sentence is corrected in the same commit, so the next model is
not relying on the tolerance.

### What did NOT change, and why it matters

The pre-existing corpus is **unmoved**: still 8 filed-only false negatives, still
178 across all beats. The fix neither helped nor harmed it, which is the correct
result -- those rulings came from the resolve half, whose sheet does teach the
category vocabulary, so they never had the hand-name miss.

So there are two corpora with two different failure causes, and only one is now
closed.

### The eight that remain, and why item 5 is still blocked

Read individually (`tools/dispatch_residuals.py`), the 8 are not a vocabulary problem and
not obviously a LOSS:

- turn 4144, `spatial`: the note reads **"No position changes; both remain at
  the bed in the den."** The hand ran and emitted `poses`.
- turn 4144, `body`: the note reads **"arousal state unchanged (hardened). No
  new overlays or conditions."** The hand ran and emitted `overlays`.
- turn 3812, `objects`: the note reports a sash *resting* where it already was.
  The hand emitted `entities` and `inventory_ops`.
- turn 3628, `spatial`: Hinami *remains* contained where she already was. The
  hand emitted `poses` and `rooms`.

The pattern in six of the eight is a note carrying a CONTINUING state, which the
manifest correctly omits because a continuing state is not a change, followed by
a hand re-encoding it. In two of them the note explicitly says nothing changed
and the hand emits anyway.

**`dispatch_replay`'s acceptance criterion cannot see this.** `_produced` counts
any non-empty channel as productive, so it cannot tell "encoded a new change"
from "re-asserted a standing fact" from "contradicted its own ruling". On these
eight it is answering a question next to the one being asked.

That is not a reason to trust the criterion less on the beats above -- there,
the lost content was plainly new. It is a reason item 5 cannot be decided from
this number. Deleting the `ledger_notes` trigger is a bet that those 8 are
redundancy; the measurement that would settle it compares each hand's output
against the committed `state_diff`, and does not exist yet.

**Item 5 is therefore BLOCKED on a measurement, not on a gate.** Recorded rather
than guessed: a 2.9% false-negative rate that is probably redundancy is exactly
the shape of number that gets rounded to zero by someone who wants the change.

## 3c-quater. VERDICT ON 3c: the manifest cannot dispatch a record-keeping hand

Section 3c-ter left item 5 blocked on a measurement that did not exist: whether
the content a categories-only dispatch would skip was worth keeping.
`tools/dispatch_survival.py` is that measurement. It compares each skipped
hand's own output against the MERGED `state_diff` the turn committed -- the
`director_resolve` step's active variant, which is what `persist/commit.py`
reads -- so "did this reach the world" is answered by the world.

**It did. 12 of the 13 entries the eight skipped hands produced were
committed (92%), and 11 of 11 on record-shaped channels (100%).**

    record  channels : 11 of 11 entries committed
    event   channels :  1 of  2

Dropping the `ledger_notes` dispatch trigger would not have saved those calls.
It would have deleted committed world state.

### Why, and it is structural rather than statistical

A hand's ledgers come in two shapes, and section 3 already names the split.
EVENT-shaped channels (`contact_ops`, `inventory_ops`, `substance_ops`) record
a thing that happened. RECORD-shaped channels (`poses`, `overlays`,
`conditions`, `entities`, `rooms`) carry the whole current state of a subject,
restated every beat.

`changes_asserted` counts CHANGES. So it can only ever address the first kind.
A pose record is re-emitted whether or not the pose changed, and the Director is
RIGHT to file no manifest entry for it -- nothing changed, so nothing is
asserted. Which means **the manifest can never be the thing that dispatches the
hand that keeps a record-shaped ledger.** No amount of better category
vocabulary fixes that; the two fields answer different questions, exactly as
the interpret sheet says they do.

Sorted by hand, this is sharpest at the extreme:

| hand | its channels | can the manifest dispatch it? |
|---|---|---|
| `body` | attire, conditions, vitals, overlays | **never** -- all four are record-shaped |
| `spatial` | positions, rooms, stations, poses + comms_ops | only for `comms_ops` |
| `objects` | entities, destruction + inventory_ops, artifact_ops, sensory_events | partly |
| `contact` | containment, scales + contact_ops, contact_action_ops, substance_ops | mostly |
| `social` | cast_changes, introductions, world_facts, crowd_ops, courier_ops, telling_ops | mostly |

`director_body` is the hand with the 76% empty-call rate section 6 wanted to
attack, and it is precisely the hand the manifest is structurally incapable of
addressing. The proposal aimed at the one target it could not hit.

### The two notes that looked like the strongest case for 3c, read properly

Turn 4144 carried the two most quotable notes in the corpus:

- `spatial`: *"No position changes; both remain at the bed in the den."*
- `body`: *"arousal state unchanged (hardened). No new overlays or conditions."*

Both hands ran anyway, and section 3c-ter read that as a hand contradicting its
own ruling -- redundancy, and therefore a saving. Compared against what the hand
was SHOWN (`llm_capture.payload_hashes` keeps the payload), it is not:

    shown: flush = [{active: true,  "A bright flush spreads across her face..."}]
    emit : flush = [{active: false, "A bright flush spreads across her face..."},
                    {active: true,  "A DEEPENED flush spreads across her face..."}]

The hand retired the standing overlay and wrote a deepened replacement. That is
the retire-and-replace transition a record-shaped ledger is kept by, and both
entries committed. The note was accurate at the level it speaks -- no NEW kind
of overlay -- and the work was real.

**The lesson generalises past this note.** "The hand emitted something its
ruling did not announce" is not evidence of waste, because on a record-shaped
channel the ruling and the ledger are not counting the same things. Any future
measurement of specialist redundancy has to compare against what the hand was
SHOWN, not against what the Director SAID.

### Ruling

**Item 5 is REJECTED, not deferred.** `ledger_notes` stays a dispatch trigger.
Section 3c's "the Director should not know its specialists exist" survives only
in the half that 3c-ter already delivered: code resolves whatever vocabulary the
author uses, so the author need not know which name is a hand and which is a
ledger. It does not extend to deleting the address itself.

What this costs the plan: the 87%/76% empty-call rates stay on the table as a
target, and the lever that was going to reach them does not exist. Section 7's
sheet reduction is now the largest remaining item, and it is a token
optimization rather than a call-count one.

**What a real call-count saving would need**, recorded so it is not
re-proposed from scratch: a way to tell, deterministically and before the call,
that none of a hand's record-shaped subjects can have changed this beat. That is
a question about the beat's gates and the scene, not about the Director's
ruling, and `_dispatch_specialists` already computes something close to it (the
gates it consults when a hand is addressed by name alone). Whether those gates
are sharp enough to dispatch ON is unmeasured, and it is a different experiment
from this one.

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

**(e) THE ENGINE DROPS IT AND TELLS THE DIRECTOR.** Added 2026-09-09 after
reading the code behind two of the (a) claims above, and it is the bucket that
was missing rather than a refinement of one. `contacts_across_enclosure`
"returns the dropped rows; appends one finished sentence per row to `report`",
and the unmatched-cross rule is a bare `continue` beside
`report("discarded a contact crossing that did not match the standing interior
endpoint")`. Neither repairs. Both are loud.

That is NOT the same as (a), and the difference decides whether a sentence may
go. A repair means the beat is right whatever the model does. A drop-and-report
means the beat is WRONG ONCE and the Director is told in time for the next one
-- so deleting the sentence trades "never happens" for "happens, then is
corrected a beat later", and one beat of wrong world state is exactly the
failure this engine treats as a machine fault rather than model variance.
**Sentences in (e) stay.** Two of the seven rules section 4 filed under (a) --
"a cross that matches no standing endpoint is rejected" and "contacts between
separated bodies are dropped" -- are (e), which their own wording said and the
bucket did not: *rejected* and *dropped* are not *repaired*. The ~3,000 chars
"delete on sight" is an over-claim by at least those two.

**THE CHECK THAT MAKES (a) SAFE, and it is not optional.** A sentence saying
"the engine drops X" may be deleted only if the engine REPAIRS X. Where it
drops, the sentence is the only thing preventing silent data loss, and deleting
it converts a repair into a hole. Where it drops AND REPORTS, see (e): the hole
is announced rather than silent, which is better and is still a hole. Every rule cut must be traced to the guard
that makes it unnecessary, and where no guard exists the guard is written
FIRST. These rules are a graveyard of live defects; the commit that removes one
is the commit that must prove it cannot come back.

## 4a. MEASURED: the echo is not derivable, so 39% of the shared core stays

The five specialist cores are five copies of one document. Measured
2026-09-09: ~8.4-9.0k chars each, **89% byte-identical**, differing only in the
opening role paragraph and the entitlement paragraph. Split into sentences, 40
of ~45 appear in ALL five.

**They have not drifted**, which is worth recording because five copies of a
rule normally do: no sentence appears in three or four cores and is missing
from another. The duplication is a maintenance hazard that has not yet gone
wrong.

**Sixteen of those forty sentences -- about 3,300 characters, 39% of the shared
core, carried by every dispatched hand -- are the `resolved_events` echo and
the `not_mine`/`reroute_to` reroute protocol.** Section 3d listed exactly these
among the terms that "should not reach a model at all", on the reasoning that
they die with section 3c. Section 3c-quater rejected 3c, so they do not die on
their own, and the question had to be asked directly.

Section 4's test governs. The engine already treats an unanswered id as
unaddressed and repairs it, so deleting the echo would lose no DATA -- it would
cost repair calls. It is therefore worth deleting only if code can DERIVE the
same verdict. `_evidence_present` is the obvious candidate, because it already
does this job one step later: it checks a claimed encoding against the merged
`state_diff` before believing it.

`tools/echo_derivable.py` replays every captured specialist call that carried
both an echo and the numbered manifest it answers, and scores the code-derived
verdict against the hand's own. **329 events. Code agrees 70.2%.**

    encoded        220 agree /  75 disagree  (75%)
    already_true     9 agree /  18 disagree  (33%)
    not_mine         2 agree /   5 disagree  (29%)

**The expensive direction is 75 of 329 (23%): the hand said `encoded` and the
committed diff does not show it by this test.** Every one of those would buy a
repair call for a change that was already carried. That is not a saving; at a
scoped specialist call each, it is a large regression bought with a 3.3k-char
prompt reduction worth about a tenth of a second.

**Ruling: the echo stays. The 39% is not cuttable.**

The reason generalises, and it is the more useful half. `_evidence_present` is
a VERIFIER, deliberately conservative -- built to check a claim cheaply, with a
shallow containment fallback for categories it does not model. That is the
right shape for refusing to believe a false `encoded` and the wrong shape for
originating the verdict, because a verifier's false negatives are free and an
oracle's are not. **A check that is good enough to doubt an answer is not
thereby good enough to replace it**, and the 29.8% is the distance between
those two jobs.

Note also what the disagreements are ABOUT: `contacts` dominates, and the
contact ledger is the one whose identity is a composite (endpoints, parts,
interiors) rather than a subject name. That is a hint about where
`_evidence_present` is weakest, not an argument that the hands were wrong.

**What this costs the plan.** Section 7's "93% proposed cut, shared specialist
core first" was the largest remaining item, and its largest single component is
now closed by measurement. The 39% stays; of the remaining 24 sentences, the
role and entitlement paragraphs are per-hand rather than shared, the firewall
and output-shape rules are section 4's buckets (c) and (d), and what is left is
too small to be worth the risk of a prompt edit that reaches every story.
Section 7 should be re-scoped to a single CHUNK -- `contact_ops` at 12,440
chars is the candidate section 4 already analysed -- and a chunk is only loaded
when its channel is in scope, so the saving is narrower than the core's would
have been.

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

## 5a. THE BIGGEST OPTIMIZATION IN THIS DOCUMENT IS ALREADY BUILT AND SWITCHED OFF

Everything above is worth doing and none of it is worth as much as this.

`_apply_json_mode`'s own docstring (`llm/providers.py:2177-2199`) carries the
engine's measurement of what an ENFORCED grammar does, five trials per mode:

```
narrator    none 2/5 valid   json_object 0/5   json_schema 5/5
character   none 4/5 valid   json_object 4/5   json_schema 5/5
```

and, in the same docstring:

> it is faster, because a constrained model cannot pad: `character` went
> **53.4s/2029 tokens to 15.3s/587**, a 3.5x cut on the heaviest role in the
> pipeline.

That is the same effect this note measured from the other side: section 3d's
scaffolding count found `character_major` spending ~701 tokens a call on
punctuation and key names, and a grammar is what stops a model padding.

**It is not running.** `providers_no_json_schema` holds
`google/gemini-3.8-flash`, which every Director specialist inherits from
`default`. Live `character_major` output measures **2,520 tokens a call** --
*above* the docstring's unconstrained 2,029 and four times its constrained 587.
The heaviest role in the pipeline is running unconstrained, and falling back to
`json_object`, which the same docstring measures as WORSE THAN SENDING NOTHING
on a prose-leading prompt.

**How it got switched off, and why that is the defect rather than the
configuration.** Read together:

- `_SCHEMA_STALL_LIMIT = 2` (`providers.py:1920`). Two stalls.
- A stall is not a refusal. `_note_json_schema_stalled` counts "a schema request
  that was accepted and then never answered" -- which is also what a timeout,
  a loaded host, or a bad minute looks like.
- The decision is PERSISTED to the `providers_no_json_schema` setting
  (`:1926`, `:1951-1953`), so it survives the process.
- **There is no way back.** `_NO_JSON_SCHEMA` is only ever `.add`-ed
  (`:1945`, `:1975`, `:2034`). No `discard`, no expiry, no re-test, anywhere in
  the module. The only exit is editing the setting by hand.

So two transient timeouts permanently disable the largest single speedup the
engine has, for that model, forever, and nothing ever asks again. Nothing is
wrong with preferring a grammar, memoising a refusal, or falling back; what is
wrong is that a LATENCY symptom is treated as a CAPABILITY verdict, and a
capability verdict is written down in ink.

**What it is worth.** `character` is 37.7s of a 91.2s median turn (section 1).
If the docstring's 3.5x holds for this model, restoring the grammar is roughly
**23 seconds off a 91-second turn -- about 25% -- with no prompt rewritten, no
rule deleted, and no guard to write.** The whole reduction programme above,
executed perfectly, was worth ~15s and 93 refutations.

Three things this changes elsewhere in this note:

1. Section 5's "retest the stall" is not step one of the prompt work. It is the
   work, and the prompt work is the follow-on.
2. Section 3c-bis's precondition -- a manifest reliably filled -- is this. A
   field nothing enforces is the reason `changes_asserted` is absent 69.2% of
   the time.
3. Section 3d's argument for renaming enum values gets stronger, not weaker: a
   grammar transmits the closed set as a constraint, so the name is all the
   model gets and all it needs.

**The fix is not to clear the setting.** That re-tests once and re-blacklists on
the next bad minute. The fix is that a stall-derived blacklist must expire and
be re-tested, and that the threshold for writing one down permanently should be
higher than two -- with a rejection (a 400, which IS a capability verdict) kept
permanent as it is today. Clearing the live setting is worth doing once, by
hand, to measure the payoff -- but only after the entry can heal.

## 5b. CORRECTION to 5a, and the narrative-quality question

**5a scoped the blacklist wrong.** `providers_no_json_schema` holds provider 3
plus `google/gemini-3.7-flash` / `gemini-3.8-flash`. Resolved against live
`agent_models`:

| role | model | grammar |
|---|---|---|
| `character_major` | fireworks `glm-5p3-fast` | **sent** |
| `narrator` | `z-ai/glm-5.3` | **sent** |
| `story_planner` | `deepseek-v4-flash` | **sent** |
| `director` (prose author) | gemini-3.8-flash *(inherits default)* | BLOCKED |
| all five specialists | gemini-3.8-flash *(inherits default)* | BLOCKED |

So `character_major` is NOT running unconstrained, and 5a's "~23s, about 25% of
a turn" was wrong -- it priced the heaviest role into a fix that does not touch
it. What is blocked is the **six Director roles**: the prose author, whose two
stages are 25.4s of the turn and whose output is 45.2% scaffolding, and five
specialists that are prefill-bound and would gain little decode time. The
realistic prize is the prose author's padding plus the correctness win on the
specialists -- worth having, not worth a quarter of the turn.

The claim about the blacklist ITSELF stands unchanged and is the part worth
fixing: `_SCHEMA_STALL_LIMIT = 2`, a stall is indistinguishable from a timeout,
the verdict is persisted, and `_NO_JSON_SCHEMA` is only ever `.add`-ed -- no
discard, no expiry, no re-test anywhere in the module.

**Does a grammar cost narrative quality?** The owner's question, and the corpus
can answer it because three roles run grammar-on today. Prose-bearing field,
per role:

| role | grammar | n | mean chars | median | TTR |
|---|---|---|---|---|---|
| `narrator` (`prose`) | **ON** | 171 | **1,076** | 1,020 | **0.087** |
| `director` (`resolved_event`) | off | 222 | 1,023 | 948 | 0.083 |

The grammar-on role writes marginally LONGER prose with marginally MORE varied
vocabulary than the grammar-off one. `character_major`, also grammar-on, emits
2,413 tokens of content per call -- `appraisal` 783, `active_state` 464,
`sequence` 326 -- which is not a starved model.

The mechanism says why, and it is the thing to hold onto: **a JSON grammar
constrains STRUCTURE, not string contents.** Inside a string value the sampler
is free to the closing quote, so prose is sampled exactly as it would be
unconstrained. What the grammar removes is the freedom to invent structure --
extra keys, repeated fields, padding around content. That is what "cannot pad"
means in `_apply_json_mode`'s docstring, and it is why the 2029->587 measurement
there should be read as a structural saving rather than the model saying less.

**Two honest limits.** This is a BETWEEN-ROLE comparison -- different models,
different jobs, different prompts -- not a controlled A/B, so it can only say
that constrained roles are not visibly thinner, never that the grammar is free.
The real test is one role, both ways, on the same beats.

And a second correction while here: this note earlier described nine field names
as "invented ... silently discarded". Re-checked per role, most are legitimate
fields of the emitting role's own schema and the survey had compared them
against `AssertedChange` instead -- `visibility` is a real `sequence` field
(382 occurrences on `director`, 157 on `character_major`). What remains
genuinely unexplained is a handful of single-digit occurrences, and some of
those are on a grammar-ON role, which the invention story does not fit. The
argument for the grammar rests on enforcement and padding, not on that claim.

## 6. Order of work -- STATUS as of 2026-09-09

Branch `worktree-prompt-latency-evidence`. Every number below is measured, and
the harnesses that produced it are checked in and re-runnable.

**DONE**

1. **The grammar blacklist heals** (`llm/providers.py`, 7 tests). A stall
   suspends for 24h and is re-tested; a 400 stays permanent; the stall tally
   clears with the suspension; suspensions get their own settings row; legacy
   rows rehydrate as suspensions. Was: `_NO_JSON_SCHEMA` only ever `.add`-ed,
   so two timeouts disabled a model's grammar forever and nothing re-asked.
   `_SCHEMA_STALL_LIMIT` stays 2 -- the threshold was never the defect, the
   permanence was.
2. **`changes_asserted` mirrored onto `DirectorInterpret`** (9 tests). Four
   places, which is what it takes for a model to write a field: the schema, the
   output shape, the delegation note's closed enumeration, and
   `OUTPUT_EXAMPLES`. `AssertedChange` lifted so both halves share one type;
   the interpret view numbers its manifest instead of returning `[]`.
   `test_at_interpret_only_the_notes_address` pinned the opposite and is
   rewritten with the reasoning.
3. **Japanese parity deferred, loudly** -- `DEFERRED_PACK_PARITY` (a tuple, so
   it cannot widen into "skip the check"), a notice printed on every
   `make structure`, a skip naming the debt, and `UNBUILT.md` section 1.0.

4. **Beats played, the gate failed, and the cause was one word wide**
   (section 3c-ter). Twelve
   live interpret beats on the shipped model: the manifest was filed on 8 of
   12 with accurate entries, and every one of them routed to NOBODY -- the
   author answered with the five HAND names, which the sheet taught it one
   line earlier and which `_CATEGORY_CHANNELS` does not contain. 8 false
   negatives, 100% of productive calls. `manifest_category_targets` makes the
   manifest speak the note key's vocabulary (8 tests); after it, 0 false
   negatives with 32% of calls still saved, and the sheet's misleading
   half-sentence is corrected so the next model does not lean on the
   tolerance.

5. **Removing the `ledger_notes` dispatch trigger: REJECTED, with the
   measurement that decides it** (section 3c-quater, `tools/dispatch_survival.py`).
   12 of the 13 entries the eight skipped hands produced were COMMITTED, and 11
   of 11 on record-shaped channels. The reason is structural: `changes_asserted`
   counts changes, record-shaped ledgers restate whole current state every beat,
   so the manifest can never dispatch the hand that keeps one -- and `body`,
   whose four channels are all record-shaped and whose empty-call rate (76%) was
   the target, is the hand it can never address at all. `ledger_notes` stays.
   The 87%/76% empty-call rates stay on the table with no lever that reaches
   them; a deterministic pre-call gate on record-shaped subjects is the next
   idea and is a different experiment.

**NEXT, in order**

6. **The renames** (section 3d). Independent of 5, cheap, and the one
   part of the trial no skeptic contested -- subject to the naming test's
   second clause: the engine must own the new name everywhere it is compared
   (`enclosure: 'membrane'` is the counter-example that earned that clause).
7. **Reduce ONE sheet -- RE-SCOPED to a chunk, because the core's largest
   component is closed** (section 4a). The five cores are 89% identical and
   have not drifted; 39% of what they share is the `resolved_events` echo,
   and `tools/echo_derivable.py` shows code can only derive that verdict 70.2%
   of the time, with 75 of 329 events landing in the direction that BUYS a
   repair call. The echo stays. What remains of the core is per-hand role text
   plus section 4's buckets (c) and (d), which is too little to justify a
   prompt edit that reaches every story. The candidate is now `contact_ops`
   (12,440 chars), which section 4 already bucketed -- and a chunk loads only
   when its channel is in scope, so the saving is narrower than the core's
   would have been. Every deleted rule still traced to a guard WRITTEN FIRST,
   not cited after: the trial produced 39 bad guard claims from agents that had
   been told exactly this, in bold.
8. **The consolidated check pass**, deferred by mandate while iterating:
   regenerate `docs/CODE_MAP.md`, `make structure`, full parallel suite, then
   empty `DEFERRED_PACK_PARITY`. The English pass is not finished while that
   tuple is non-empty.

**PARKED, with reasons**

- The grammar A/B on the prose author. Section 5b already shows constrained
  roles are not visibly thinner; not on the critical path, and it costs live
  calls.
- Dropping JSON for a lighter format (section 5b): refuted at 99.4% clean
  parse, and it points the wrong way on invented keys.
- The character stage's 37.7s. Already grammar-on, and 51% of its output is
  `appraisal` + `active_state`, which is the product rather than the fat.

**Honest expectation, revised down.** Median turn is 91.2s. The call-count
saving is GONE: item 5 was where it lived, and section 3c-quater rejects it on
the engine's own committed output. What remains (items 6 and 7) is token
reduction on sheets that are 0.7-4.6k against an 8-9k prose author, and the
measured relationship is `duration ~= 1.8s + 0.29s/1k input` -- so a 93% cut to
the shared specialist core is worth roughly a second per dispatched hand, not
the 15-25s this section claimed while item 5 was still open.

The correctness findings remain the larger return, and that is now the honest
summary of the whole document rather than a consolation: section 3c's 82%
self-disagreement, the manifest's unroutable vocabulary (3c-ter), the
record-versus-event split that decides dispatch (3c-quater), and the six engine
defects in `NARROW_INTERFACE_TRIAL_2026_09_09.md`.

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
