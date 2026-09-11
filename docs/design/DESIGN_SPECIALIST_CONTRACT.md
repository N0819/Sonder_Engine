# The specialist contract: hands resolve instructions, not narrative

**BUILT 2026-09-10.** The Director emits one list of categorized, numbered,
annotated spans; the hands receive their scene-scoped ledgers and their work
items and nothing of the beat; each record names the chunk it resolves. What
remains open is section 6 (record-shaped channels) and section 6a (the
room-mint agent), both registered in
[`UNBUILT.md`](../UNBUILT.md) §1.1, which is the authority on status rather
than this header. The measurements are real and dated; the target is the
owner's, stated 2026-09-09. This note exists because
`DESIGN_NARROW_MODEL_INTERFACE.md` — including the sections added the same day
— has been optimizing *around* the gap described here rather than at it.

## 1. The contract

> A specialist receives:
>
> 1. **The slice of persistent world state relevant to its task**, scoped to
>    the scene for efficiency — the ledgers it owns and what it needs to read
>    them against.
> 2. **One or more work items.** Each is a dissected chunk of player or
>    character input, carrying a **chronological id** and a **note in natural
>    language saying how the Director thinks it should resolve** — authorship,
>    not schema.
> 3. **Nothing else.** Not the beat's prose, not the Director's account of what
>    happened, not the other hands' work.
>
> The specialist is almost purely mechanical: it renders those work items onto
> the world through its own toolset — meaning **the structured output format
> its code reads**, not a tool-calling loop. A hand's channel vocabulary IS its
> toolset: `contact_ops` with its `op`/`relation`/`motion` fields, `attire`
> records, `inventory_ops`, and so on. That half is already built; the hand
> emits ops today and deterministic code applies them.
>
> The chronological ids exist for exactly one reason — the hands run in
> parallel and finish out of order, so the ids are how code puts the results
> back into beat order, and the order events reach perception.
>
> The Director never learns the ledger rules, because it never writes a ledger.
> The specialists are how the Director resolves its intents onto the world.

**The Director does not author prose at all.** It outputs events; the
specialists push them to the world. `resolved_event` is not a smaller part of
its job under this contract, it is none of it -- and it is not needed
downstream either, because perception composes from committed structured state
and the narrator renders from perception, never from the Director (verified:
`agents/narration.py` reads `perception_outcome.views.player`, and the only
mention of `resolved_event` in that module is a comment recording a past leak
that was closed).

**"Tools" does not mean uncreative -- it means SCOPED.** (Owner, 2026-09-09:
*"they aren't fully uncreative tools even though that's a majority of their
job; attire and a few of the other specialized things are incredibly highly
scoped creativity vs the broad scope that is the main director call."*) A hand
names a garment, writes what a place is like, picks the word for a substance.
That is authorship, and it is meant to be there. The difference is the SIZE OF
THE SCOPE, not the presence of invention: the Director judges how a whole beat
unfolds and who could interfere; a hand invents only inside the one ledger it
owns, about the one thing it was asked to settle. Most of its job is
mechanical; the creative part is narrow and deep rather than broad.

This is why the contract subtracts the BEAT rather than subtracting judgement.
A hand given its ledgers and its instruction can still write the perfect word
for a garment. A hand given the whole beat starts making decisions about the
beat, which is the Director's scope and not its own.

**What the Director is FOR: how an input realistically unfolds.** Causality,
plausibility, timing, who could interfere and how. The specialists are its
RESOLUTION TOOLS -- the mechanism by which those judgements become world
state. That is the test for every sentence in its sheets: a rule about what a
valid `attire` record looks like, which endpoints a contact needs, or where a
substance may be placed is a LEDGER rule, and belongs to the hand that owns
the ledger. Measured today, the Director's sheets are 23.8k chars (interpret)
and 45.7k across 29 chunks (resolve), and a large share of that is exactly
those rules.

Two consequences worth stating, because they are the point rather than side
effects:

**The Director gets smaller, not just the hands.** Today it emits `sequence`
*and* `changes_asserted` — two decompositions of the same input — plus the
narrative, plus per-hand notes. Under this contract its output is a list of
`(chunk, category, id, note)`. It stops needing to know what a valid `attire`
record looks like, because it never writes one: it says *this belt is off,
resolve it*, and the hand that owns wardrobe knows the rest.

**It is the firewall principle one layer down.** The firewall says a mind may
not acquire a fact it had no channel to. This says a HAND should not be handed
the Director's account to re-derive what it was going to be told anyway. Both
subtract, and both are generative rather than restrictive: two hands that
cannot see the same prose cannot read it differently.

## 2. What a hand receives today

Measured over **632 resolve-side specialist calls** in the owner's `engine.db`
(`llm_capture.payload_hashes`, 2026-09-09).

**Correct already — the scoped world state.** Payload assembly is per-hand and
per-scene: `attire` (1,490 chars) and `body_parts` (802) to the body hand,
`substances` (1,180) and `contacts` (668) to contact, `rooms` (535) to spatial,
`worn_garments`, `overlays`, `active_conditions`, `entity_names`,
`contact_actions`, `scales`. Item 1 of the contract is built.

**Inverted — everything else.** Three channels reach the hand, and their
coverage is the exact opposite of the contract:

| channel | what it is | calls | size |
|---|---|---|---|
| `resolved_event` | the whole beat, as prose — the Director's account and intent | **632/632 (100%)** | 910 ch |
| `director_note` | what the Director asked of this hand | 311/632 (49%) | 147 ch |
| `changes_asserted` | the categorized events for this hand | 172/632 (27%) | 459 ch |

The channel that IS the contract is the smallest, least present and least
authoritative. The specialist core ranks them explicitly:

> `resolved_event` is the **AUTHORITATIVE** prose of what objectively happened
> … if it is absent the prose is your whole account of the beat; encode what
> the beat asserts and **never contradict the prose**.

against the conditional *"When `payload.changes_asserted` is present…"*. And
`payload["changes_asserted"]` is set only `if manifest` — only when the beat's
manifest has entries in that hand's categories.

**So 73% of specialist calls run on narrative alone.** The hands are not
resolving instructions. They are second interpreters of the same prose the
Director already wrote, deriving the events themselves as a private step.

## 3. What that costs, measured

That private derivation is not free, and it is most of the Director's wall
clock. Over twelve live interpret beats on `google/gemini-3.8-flash`:

| role | out tok/call | s/call | reasoning share |
|---|---|---|---|
| director | 3,478 | 20.3 | 68% |
| director_objects | 3,389 | 19.7 | **93%** |
| director_spatial | 2,885 | 18.0 | 90% |
| director_contact | 1,940 | 13.4 | **97%** |
| director_body | 1,726 | 10.6 | 91% |

`director_contact` spends about 4,978 characters of private trace to write 161.
Decode holds at ~160-172 tok/s, so wall clock is output tokens over that rate.
**The trace is the hand parsing prose back into ledger terms that the Director
already had in structured form and did not send.**

Two independent results from the same day corroborate it:

- `reasoning_effort=low` cut specialist time 82% (416.4s → 73.0s) with the
  manifest, categories and error count unchanged — the transcription is not
  what the thinking was for.
- It broke exactly one hand. `director_objects` began returning
  `{"entities": {}}` while claiming `resolved_events: [{status: "encoded"}]`,
  on beats where a thing came into being or was broken. That is the one place
  prose-parsing becomes a judgement call — and it is a judgement only because
  the event was not handed over. (Guarded since, in
  `_resolved_event_verdicts`; see `tools/false_encoded.py`.)

## 4. The gaps, precisely

**(a) The dissection exists but carries neither category nor id.** `sequence`
chunks the input well — `"I pull off my sword belt"` / `"drop it on the bench"`
/ `"sit down heavily"`, each with `attempt`, `observable`, `visibility`,
`conceal_from`, `targets`, `commitment`. It has no `category` and no
`event_id`.

**(b) Categories and ids live on a second, non-corresponding decomposition.**
`changes_asserted` decomposes the same input into *consequences*, not chunks.
On the belt beat: three chunks, three changes, no correspondence. On the letter
beat: two chunks, one change — the handover to Sera absent entirely. The model
is asked to decompose the same input twice, in two vocabularies free to
disagree, and only the second routes anywhere.

**(c) The manifest is defined as derived FROM the prose.** `AssertedChange`'s
own docstring: *"a persistent physical change its `resolved_event` asserts as
completed."* It is an index into the narrative rather than the primary
artifact, which is why it is incomplete and why the prose must be shipped
beside it. Making it primary is the inversion this note asks for.

**(d) The resolution intent is at the wrong granularity.** `AssertedChange` has
`category`, `event_id`, `subject`, `change` and endpoint fields — and **no
field for how the Director intends it to resolve**. `change` is *"one short
sentence stating the persistent change"*: description, not instruction. The
intent exists only as `ledger_notes: {specialist: line}` — one line per HAND,
aggregated across everything that hand does this beat, on 49% of calls.

**(e) The ids never reach the place order matters.** In `perception.py` the
`event_id` is used **only as a dedupe key**, and since `sequence` entries carry
no id it falls back to hashing `[actor, local_index, event]`. Ordering is
`order_key=idx` — position in a stream built by concatenating the player's
whole sequence, then each character's after it. There is no global chronology,
so an NPC acting *between* two player chunks cannot be represented in the order
it happened.

**A note on what the ids are NOT needed for.** The 32 delegated channels are a
**disjoint partition** — verified, no channel is owned by two hands — and
assembly replaces the author's content per granted channel. So parallel
out-of-order completion already cannot corrupt state, by construction. The ids
are unnecessary for the state merge and unimplemented for perception, which is
the only place they would do real work.

## 4a. THE TARGET OUTPUT FORMAT, in four fields

The owner, 2026-09-09, giving the shape the Director should emit -- one list,
one entry per chunk:

| field | what it is |
|---|---|
| the chunk | the dissected piece of player or character input itself |
| id | the chronological id |
| note | how the Director thinks THIS chunk should resolve |
| category | which ledger family it belongs to |

**And the Director does not need to know the specialists exist.** It is not
choosing a hand; it is being asked to categorize its own changes. Code turns a
category into a hand (`manifest_category_targets`, already built). That is
section 3c's original insight, finally in the right place: 3c tried to make it
true by DELETING the address, and was rejected because the manifest could not
carry the dispatch. It becomes true instead by making the categorized chunk the
only thing there is.

### What this collapses

Today the Director emits TWO decompositions of the same input, neither of which
is this:

- `sequence` -- the chunks, well dissected, with `type`, `attempt`,
  `observable`, `visibility`, `conceal_from`, `targets`, `commitment`, `verb`,
  `stage`, `intended_effects`, `asserted_effects`, `participants`,
  `requires_contacts`, `referents`, `phase`, `phase_id`, `depends_on` -- and no
  category and no id.
- `changes_asserted` -- consequences rather than chunks, with `category`,
  `event_id`, `note` (2026-09-09), `subject`, `change`, and ten endpoint fields
  (`actor`, `actor_part`, `target`, `target_part`, `contact_ref`, `action`,
  `intensity`, `rhythm`, `detail`, `substance`, `placement`,
  `target_interior`).

The target is one list of four-field entries. `changes_asserted` is already
three quarters of the way there -- it has `category`, `event_id` and now `note`
-- and what it lacks is the chunk itself: `change` is the Director's
DESCRIPTION of a consequence, not the piece of input the hand was asked to
settle.

### What has to move, and where the risk is

**The ten endpoint fields.** `actor`/`actor_part`/`target`/`target_part` exist
because "two simultaneous contacts involving the same actor are
indistinguishable" without them -- reconciliation matches a manifest entry
against the diff by them. Under the four-field format the HAND derives
endpoints from the chunk plus its own ledgers, which is exactly its scoped job
and exactly what it already does when it reads a chunk. But reconciliation
then loses the key it currently matches on, so `_evidence_present` needs a
different question. That is the load-bearing piece and it is not a rename.

**The record-shaped channels, again.** A four-field chunk entry is an EVENT.
`poses`, `overlays`, `conditions`, `attire` are whole current-state records
with frequently no chunk to hang on (section 6). Either they get a second
instruction shape or `body` has no work items at all.

**Sequencing.** `changes_asserted` is the reconciliation seam's one mechanism;
`sequence` is read by perception, the narrator, the floors and the reaction
loop. Neither can be replaced in one commit. The order that survives contact:
carry the chunk on the manifest entry first (additive), verify hands resolve
from it, then move `sequence`'s readers, then delete the second decomposition
-- with the endpoint-matching question answered before the first step, not
after.

## 4b. ANSWERED: the op carries the chunk id

Section 4a named one blocker. Reconciliation proves a manifest entry was
encoded by matching it against the diff ON THE ENDPOINT FIELDS
(`director_evidence.py` 1074-1098: `actor_part`, `target_part`), because "two
simultaneous contacts involving the same actor are indistinguishable"
otherwise. Four-field entries carry no endpoints, so that key disappears. The
owner's ruling (2026-09-09) was to answer this BEFORE migrating, not after.

**The obvious candidate fails on measurement.** `phase_sources` already exists
and is exactly the right shape -- a map of `"<channel>.<subject>" -> event_id`
the hand returns beside its channels, which would make reconciliation an id
lookup. `tools/provenance_coverage.py` over the live corpus:

    productive specialist calls : 484
      emitted phase_sources     : 123 (25%)
    `encoded` claims scored      : 291
      cited in phase_sources     : 199 (68%)
    channels written             : 631
      attributed to an event     : 144 (23%)

    role                productive   w/ sources   cited  uncited
    director_body               71            4       5       16
    director_contact           179           78     141       50
    director_objects            24            4       3        3
    director_social             91            0       0        0
    director_spatial           119           37      50       23

`director_social` has never emitted one, across 91 productive calls. An id-only
reconciliation built on this would report 32% of correctly-encoded events as
unencoded and buy a repair call for each.

**Why it fails is the useful part, and it is a rule rather than a fact about
this map.** `phase_sources` is a SECOND STRUCTURE, filled in beside the work.
The channels are what the hand is thinking about; the provenance map is
bookkeeping it must remember separately, and a second thing to remember is a
thing that gets forgotten. This is the same shape as the four-places rule one
level down: a field INSIDE the object the model is already writing gets
written; a parallel structure describing that object does not.

**So: the op carries the id.** Each channel entry gains a field naming the
chunk it resolves -- one small integer, inside the record the hand is already
composing, in the channel's own schema. Reconciliation becomes "does any op in
this hand's channels cite chunk N", which needs no endpoint text and no second
map.

Three things this buys beyond unblocking section 4a:

- **It is exact rather than heuristic.** `tools/echo_derivable.py` measured
  `_evidence_present` disagreeing with the hands' own verdicts on 29.8% of 329
  events -- the distance between a conservative verifier and an oracle
  (section 4a of `DESIGN_NARROW_MODEL_INTERFACE.md`). An id match has no such
  distance; the question stops being "does this text describe that op".
- **It is cheaper than what it replaces.** One integer against ten endpoint
  fields.
- **It answers the record-shaped channels too**, at least partly: a record
  restated for no chunk simply carries no id, which is a legible state rather
  than an unmatched entry.

**Not built.** It touches every delegated channel's schema and every chunk's
output shape, and it must land BEFORE the `sequence` migration rather than
alongside it -- that is what "answer it first" means. The measurement above is
the evidence that the cheaper option was tried and rejected on data.

## 4c. CHECKED: a hand that fires is doing real work

Every "productive call" figure in this document and in
`DESIGN_NARROW_MODEL_INTERFACE.md` counts a call as productive when any channel
came back non-empty (`dispatch_replay._produced`). That definition includes
doing nothing: a hand that re-emits a pose record byte-identically scores like
one that encoded a new pose. Since section 3c's rejection rests on "12 of 13
entries were committed", the definition is load-bearing and was worth checking.

`tools/should_it_have_fired.py` compares what each hand EMITTED against the
same channel in its OWN PAYLOAD -- what it was looking at when it answered --
and classifies every entry as new, changed, or byte-identical.

| hand | calls | did work | no-op | unjudged |
|---|---|---|---|---|
| `director_spatial` | 119 | **119** | 0 | 0 |
| `director_body` | 71 | 59 | 0 | 12 |
| `director_objects` | 24 | 19 | 0 | 5 |
| `director_contact` | 179 | — | — | 179 |
| `director_social` | 91 | — | — | 91 |
| **total** | **484** | **197** | **0** | 287 |

**197 of 197 judgeable calls changed the world. Zero no-ops.** Entry-level: 40
new, 318 changed, 5 byte-identical -- 1.4%.

The 287 unjudged emitted only op-shaped channels (`contact_ops`,
`public_evidence`, `inventory_ops`), which have no comparable ledger in the
payload because an op list and a record list are not the same shape. The
question does not arise there anyway: **an op IS an action.** A record can be
restated without changing anything; an operation cannot.

Three consequences:

- **Section 3c's rejection is stronger than it was argued.** Those 12 committed
  entries were not merely committed -- they were genuine changes to records.
- **The waste is entirely in the calls that return NOTHING**, of which this
  corpus has 730 against 484 that return something. Trimming what a firing hand
  does is optimizing the wrong end; not firing it is the whole prize.
- **The first cut of this tool got it wrong in the flattering direction**, and
  the way it did is worth keeping. It looked each emitted channel up in the
  payload by name, missed for every op-shaped channel (`contact_ops` emitted
  against a `contacts` ledger), and counted 803 unmatched entries as NEW --
  reporting 100% of 484 calls as productive work. A lookup that silently
  degrades to "assume the flattering answer" produces a number, and the number
  is the thing that gets quoted.

## 4d. BUILT: what the three steps actually changed

Landed 2026-09-09/10 in the order the owner set -- the endpoint question
answered first, then the chunk, then the retirement.

**1. The record names the chunk it resolves.** `from_event` on every typed
delegated record, and an id-first arm in `_evidence_present`. Additive: a
record naming nothing falls through to the check that ran before. Four things
had to be true and three were not -- typed models strip what they do not
declare; `AttireDiff`'s tolerant reader filed the id under `notes` as a
garment handle; an unset id serialised as `from_event: 0` on every record in
every stored diff; and the orchestration backstop compared provenance when it
meant to compare content.

**2. The chunk is the work item.** `sequence` carries `category`, the engine's
`event_id`, and `note`. Chunks dispatch, slice per hand, and ride in the
payload. One id space: chunks 1..N, the manifest continuing at N+1.

**3. The second decomposition is gone.** Neither sheet asks for
`changes_asserted`. The prose author's manifest block went 5,732 -> 2,012
chars. The field stays on both models and is still READ, because a stored
variant replayed from before the migration carries one and nothing else.

Measured on the closing run -- 12 beats, 0 errors, 0 `changes_asserted`
entries, 13 of 22 spans carrying a category and a note, 0 unroutable:

    I pull off my sword belt     body      remove sword belt from attire
    and drop it on the bench     objects   sword belt moved to bench
    then sit down heavily.       spatial   update posture to seated

**The leftovers, because the owner predicted them and they are the reusable
part.** Every one was a place that copied a shape rather than reading it:
`_fold_derived_manifest_events` renumbering from 1; `_normalize_omission_category`
folding a missing category onto `other` (which made every line of dialogue a
work item); `_interpret_beat_view`'s key allowlist; a sentence in
`prose_author_sheet/12.txt` still naming endpoints on a retired field;
`project_check` and three tests pinning the old block name; a
published-vocabulary guard reading a category list that no longer exists.

That last one ended up STRONGER. The vocabulary is now the five hand names,
and `manifest_category_targets` resolves a hand to every channel it owns -- so
five names reach all 32 channels, and a newly registered channel is reachable
the day it is added rather than when somebody remembers to publish a word for
it.

## 4e. THE DIRECTOR'S REASONING MODE: 62% cheaper, and it drifts

The owner asked for this to be tried across runs. Same twelve beats, same
model, the five specialists at `low` in both arms; the only difference is the
Director's own effort.

| | Director default | Director `low` |
|---|---|---|
| director s/call | 169.7s total | **64.3s (-62%)** |
| its reasoning trace | 3,220 ch | 136 ch |
| ALL Director time | 239.6s | **117.9s (-51%)** |
| spans categorized | 13/22 (59%) | 14/20 (70%) |
| errors | 0 | 0 |
| **unroutable categories** | **none** | **`geography` x2** |

The saving is the largest single number in this document. The cost is precise:
at `low` the Director's category vocabulary DRIFTS. It filed `geography` twice
for what `spatial` owns, on a run that was otherwise clean -- and a work item
in a category no hand answers to is a change the engine cannot deliver.

**Not fixed with a synonym table.** Folding `geography` onto `spatial` would be
the engine inventing vocabulary on the Director's behalf and getting it wrong
quietly, which is exactly what `_note_key_forms` refuses in as many words
("guessing that `transit` means `positions`..."). Instead `_unrouted_rulings`
now reports an unroutable CHUNK CATEGORY the same way it has always reported an
unroutable note key -- the next beat's author sees the word it used beside the
names that route, and corrects itself.

### RESOLVED: it was not drift, and it was not size

The owner's read -- *"I'm wondering if its failure there is because the prompt
is still rather large"* -- pointed at the prompt and was right about the place.
The mechanism was not length. Two faults, both mine, both the same shape:

**The sheet published two vocabularies for one set of things.**
`interpret_delegation_note.txt`, which is part of the interpret Director's own
prompt, labelled the five channel groups `BODIES`, `CONTACT AND MATTER`,
`OBJECTS`, `SOCIAL FABRIC` and **`GEOGRAPHY`** -- while the paragraph that asks
for a category names them `body / social / contact / objects / spatial`. The
model never invented `geography`; it used the nearest label the sheet gave it,
which is a fair reading of a sheet that says both. The group labels are now the
hand names.

**And the field was asked for without its value space.** The sequence paragraph
said "add `category` -- which family of record it belongs to" and enumerated
nothing, so the model had to bridge to a list in a different paragraph about a
different field. That is the same failure as the unroutable manifest of
2026-09-09, third occurrence: the key declared where it is asked, the values
declared somewhere else. The five are now named inline.

**Re-measured at `director=low` with only the inline naming in place** (the
group labels were still wrong on that run): 21 spans, 15 categorized (71%),
categories `objects/body/spatial/contact`, **UNROUTABLE: none**, 0 errors.
Naming the vocabulary where the field is asked for was sufficient on its own.

So the -62% stands with no measured encoding cost, and `low` on the Director
becomes a real option rather than a trade. Two caveats survive it: this
measures ENCODING and says nothing about whether the beats read as well, and
the unrouted-category report added above stays -- a vocabulary that drifted
once under one condition can drift again under another, and the point of the
report is that the next occurrence is visible rather than silent.

## 4f. THE SHEET IS NOT CUT DOWN, AND FLOW IS THE CLEAREST CASE

The owner, 2026-09-10: *"I feel as if scene flow can be determined in code. And
have you really been reviewing this prompt with my optimization philosophies?
It doesn't seem that cut down at all."* Both fair. The contract work ADDED
fields (`note`, `category`, `from_event`) and trimmed only what the retirement
forced. The interpret sheet is ~25k chars and the resolve lean ~44.5k.

### `flow.reactors` is already computed, then guessed, then corrected

The sheet asks for *"every awake character who could plausibly PERCEIVE this
beat"*. Perception in this engine is DETERMINISTIC -- no model, no role,
`agents/perception.py` imports no model seam at all. So the engine knows the
answer before it asks.

It also knows the asking does not work. The paragraph cites its own
measurement: **79% of beats with two or more witnesses named fewer reactors
than there were witnesses.** And `agents/runtime.py` then filters what the
model returned through a deterministic presence gate, with its own measured
reason:

> Chat 95, turns 4/5/8/14: `flow.reactors` named two cast members
> `scene.positions` had no entry for, in beats whose own `perception_act.views`
> listed observers ['75'] / ['74','75'] -- 6 `character_major` calls at 13-22s
> each on an empty perception base.

So the engine pays for a guess at a fact it holds, measures the guess wrong,
and corrects it afterwards -- and spends ~900 characters of every interpret
call trying to make the guess better.

**What is genuinely the model's here is PACING**: whether a character who could
respond should get a turn. `runtime.py` calls it "the Director's PACING
judgement" in as many words. That is a fifth of the paragraph, and the rest is
a witness list.

**Cut now, deferred, and why.** The paragraph is 1,319 -> 616 chars, keeping
the pacing instruction and dropping the witness tutorial. DERIVING the list is
a behaviour change to every beat -- it decides who speaks -- so it wants its
own measurement (does a story improve when every witness is a reactor?) rather
than landing unattended. Recorded rather than done.

### The rest of the interpret sheet, by the same test

What does this stage need in order to dissect input into spans, categorize
them, and say how each resolves? Measured, biggest first:

| chars | paragraph | verdict |
|---|---|---|
| 1,805 | ADDRESSEE PRIORITY | partly derivable -- `targets` plus who is present; the ambiguity rules are judgement |
| 1,352 | WHAT THE PLAYER SAYS HAPPENED, HAS HAPPENED | KEEP -- the authority contract is the stage's whole job |
| 1,346 | output shape | KEEP |
| 1,318 | Flow planning | CUT to 616; the rest wants the derivation above |
| 1,247 | OBSERVABLE SURFACE | KEEP -- it is the firewall at the span level |
| 1,232 | PLAYER AUTHORITY CONTRACT | KEEP |
| 996 | MOVEMENT DIRECTION | derivable -- `world/spatial_orientation.py` owns bearing math |
| 863 | FOLLOWING STATE | mostly reading a payload field back |
| 589 | LOCATION & SYSTEM DETECTION | name matching against `world_books`; code can do it |

That is the reduction programme, and it is not the same work as the contract:
the contract moved what the hands are TOLD, this moves what the Director is
asked to WORK OUT. Each row needs a guard written first and a live beat run
after, which is why none of them is landed here.

## 4g. THE SHARED SPAN, AND THE CHAIN THAT WAS SWALLOWING EVERY WORK ITEM

The owner, 2026-09-10: *"maybe a disected chunk falls into multiple categories
and needs to be digested by multiple specialists"*, and those are *"both
completed halves or thirds or quarters of a singular ledger"* rather than
competing answers. Then: *"we basically just need 5 chunks, 1 explaining each
hand and that it is working on one or more ledgers that you've also recieved,
and they can be shared chunks as I don't think the 5 hands need explanations
unique to them on how other hands work."*

Built, in that order:

- **`category` may name several families.** `_span_items` normalizes to a
  `categories` list and keeps `category` as its first entry, so a reader
  written before this still sees a string. Dispatch, the unrouted report and
  the per-hand slice all read every name.
- **Per-hand acquittal**, written BEFORE any span carried two categories.
  `_index_addressed_events` keys `event_id -> {by_hand: {...}}`, so a span
  whose wardrobe half is encoded and whose object half is not stays owed.
- **Five shared chunks**, `co_hands/<hand>.txt` in every story pack, each
  saying what THAT hand settles. A hand's sheet gains the chunk for every
  OTHER hand owning a span it received (`specialist_co_hands`, the same
  ownership table dispatch and acquittal read). Five files serve all twenty
  pairings because what the body hand settles is the same sentence whoever is
  reading it. Empty on the ordinary beat, which is the point.
- **Both sheets now permit two.** They said *"one of"*, so no beat would ever
  have produced one; the worked example in `OUTPUT_EXAMPLES` is what says the
  field takes a list rather than a comma-joined string.

### And then it was run, and none of it had ever reached a hand

`4d` reported the closing run as *"13 of 22 spans carrying a category and a
note"*. That measured what the Director EMITTED. Nothing measured what a hand
RECEIVED, and the answer was nothing at all -- four defects in series, each
invisible behind the one in front of it. All four found by playing beats
against `google/gemini-3.8-flash` (`tools/interpret_beats.py`).

**1. `norm_sequence` was eating the work item.** It rebuilds every element
from a fixed key list and the list never learned `category` or `note`. It runs
between the model and the beat view, so the span channel died before any hand
saw it. Beat 1: three correctly categorized spans with notes, three hands
dispatched, zero work items delivered. The objects hand, handed nothing,
invented ids off `phase_id`, spent 110s and 19,704 output tokens re-deriving
the beat, failed validation, and failed its repair -- two of the beat's six
calls. Fixed by restoring the two fields onto whatever the arm built, in ONE
place rather than five, and only onto the last element built from a source
element: a promoted stage direction is an act the Director never categorized,
and inheriting a category would hand a hand a span nobody wrote.

**2. Two id spaces in one payload.** With spans finally arriving, the contact
hand echoed `resolved_events[].event_id: "turn:2:player:0:action"`. It did not
invent that either: `player_declaration` carried each element's phase-graph id
under the same name `event_id` as the span's chronological number. Two
representations of "which event", free to disagree, in one payload. 16,180
output tokens and 96.9s, then a repair that returned no usable object. Fixed
by taking `event_id`, `category` and `note` OFF the declaration copy -- the
work items are `spans`, one list, and the phase graph is the engine's.

**3. A misfiled receipt was burning the records that came with it.** Both
`from_event` and `resolved_events[].event_id` are typed ints, and an
unrecognisable citation failed the whole call. A verdict on an id the hand was
never handed is discarded by `_resolved_event_verdicts` either way, so failing
bought nothing but the loss of the encoding it arrived with. Both now resolve
to 0 -- an id the engine never issues -- which keeps the miss visible to every
provenance count while leaving the answer intact.

**4. The gates were overruling the Director.** Scope was `gated union named`,
and `named` is empty whenever the ruling names only the hand -- which is
ALWAYS, because the Director's sheet asks for a category from the five hand
names and by design need not know a specialist's channels at all. Beat 1: the
Director filed "pull off my sword belt" under `body`; the wardrobe gate read
`anyone_wears` false over a bare-bodied scene; and the body hand ran and
answered `not_mine` about its own span -- *"Event 1 requires the
attire/wardrobe channel, which has no block on this sheet"* -- at 6,466 output
tokens and 37s. The gate table's docstring had already logged this exact case
as an open residual and chosen to backstop it. A backstop catches the record;
it does not get the call back.

A ruling that names a channel still meets the gates, which is where they have
something to add. A ruling that names only the hand now loads every ledger the
story keeps, filtered by `channel_serves_stage` -- because a channel this
stage cannot carry is not a prediction about the beat. Cost, on the assembled
sheets: 1.08x the two-chunk sheet for `body`, 2.17x for `social`, all of it
prefill, against a refused call that spends decode and returns nothing.

**Three tests pinned the rule this disproved** and were repinned with the live
evidence rather than worked around: `test_the_gate_fails_open_within_an_
addressed_hand` (now `..._a_hand_named_without_a_channel_keeps_its_whole_
ledger_set`), `test_scope_gates_out_channels_whose_subject_does_not_exist`
(the gates still measure the scene; `gated` is where the saving is visible),
and `test_resolve_still_fails_open_on_a_genuine_under_grant` (reached through
a channel-keyed ruling, the only way a hand can still be under-granted).


### Measured: the shared span, end to end

Three declarations written for the case, played against
`google/gemini-3.8-flash` (`tools/interpret_beats.py --beat`, 2026-09-10). The
`--beat` flag exists because the stock list measures the ORDINARY case, and a
capability the ordinary case never reaches needs inputs written for it: over
the stock twelve beats the Director filed 15 categorized spans and NONE of
them named two families, which is not evidence the capability fails.

    padlock the forge door shut        ["objects","spatial"]  encoded / encoded
    nail the shutter across the window ["objects","spatial"]  encoded / not_mine
    set the anvil across the doorway   ["objects","spatial"]  encoded / encoded

Three of three named two families, unprompted; both owners were handed the
span in their own payload; five of the six halves settled. The sixth is the
interesting one -- `spatial` answered `not_mine` and rerouted to `objects`,
because the window is in no room's edge list, so there was no passage for a
nailed shutter to block. An honest refusal with a reason, which is what the
verdict is for.

**FIVE OF THE FIVE INPUTS FIRST TRIED PRODUCED NOTHING, and the reason is the
sheet working.** Shoving, dragging and hauling a person, and tying a blindfold
over someone's eyes, all came back `commitment: contestable` with no category:
the interpret half refuses to span an act whose outcome is still contested,
because resolution owns those. A capability test on the interpret half needs
acts the player can simply DO.

### 5. The grant was built from the retired channel, so acquittal never ran

`state["event_ids"]` -- "which numbered events this specialist is answerable
for" -- read `_specialist_manifest_slice` alone. `changes_asserted` is retired:
no sheet asks for it and it has measured 0 entries on every beat of every live
run since. `_resolved_event_verdicts` discards any id outside the grant, so an
empty grant discarded EVERY verdict, and `orchestration.events_addressed` was
`{}` on every beat.

Which means per-hand acquittal -- the seam built first, deliberately, so a
half-settled span could never read as settled -- had never once run. Measured
on the padlock beat before the fix: one span, two hands, three correct
structured answers, and an `events_addressed` of `{}`.

The grant now reads BOTH slices and lives in one named function beside them
(`_granted_event_ids`), for the reason `_specialist_span_slice` is one
function: two spellings mean a hand judged on work it never got, or its answer
to real work thrown away. They share one id space by construction, so it is a
union and never a renumbering. After the fix, the same three beats:

    turn 1  span 1  by_hand {objects: encoded, spatial: encoded}
    turn 2  span 1  by_hand {objects: encoded, spatial: not_mine -> objects}
    turn 3  span 1  by_hand {objects: encoded, spatial: encoded}

**OPEN, and it is the owner's call.** `not_mine` is not in
`_SETTLING_VERDICTS`, so turn 2's span stays owed forever: one owner encoded
its half and the other reported, correctly, that it has no ledger to change.
Two readings, and the evidence does not choose between them. Either the
Director over-routed and a refusal that names another OWNER which settled the
span is itself a settlement -- both hands agree where the work belonged and it
got done there -- or the window genuinely should be an edge and the missing
edge is the real defect the owed span is pointing at. The second is a scene
built without that edge, not a contract failure, which is what makes the first
reading tempting and the measurement inconclusive.

**The reusable lesson, which is the same one four times.** Every defect here
was a second copy of something the engine already knew, or a reader still
pointed at the copy that was retired: a key list beside a schema, a phase id
beside a chronological id, a standing-state gate beside a ruling, a grant
built from the channel its replacement had emptied. *Is this fact stored
twice?* remains the question that finds them -- and its second half, asked
after a migration: *which copy is this reader holding?*

## 4h. MINT IT OR REFUSE IT WHOLE -- never half of it

The owner, 2026-09-10, on the shutter beat: *"Either it mints the window or
door or it refuses the whole span depending on player authority level."*

The beat that prompted it: one span categorized `["objects","spatial"]`,
"nail the shutter across the window". `objects` encoded a shutter. `spatial`
answered `not_mine` -- *"no forge room or door edge exists in the navigable
room graph"* -- and the beat kept a shutter nailed across a window that was in
no room's edge list. A half-settlement, which is the one outcome the rule
forbids.

Half the rule was already in the engine and is worth quoting, because it is
the same distinction one tier up (`director_reconcile._NO_REFERENT`):

> `rejected` denies that the change happened, which the player authority
> contract forbids for an asserted effect, while this accepts the effect and
> reports that there is nothing structured to encode it AS.

### The two arms, and which side of the seam each belongs on

**MINT is the hand's.** One clause in `director_note` -- the card every hand
carries, because this is about the contract and not any one subject: absence
is not a reason to decline a span. A declaration is how a thing comes to be
here, so give it the smallest honest record that makes the span true. Stated
as the class and its ONE exclusion rather than a list of mintable things
(a window, a door, a hook, a ledge -- English always has one more): what may
NOT be minted is what has no durable record anywhere, a quantity, a quality, a
stretch of time. That is `no_referent`, borrowed word for word from the core
repair's vocabulary rather than restated as a second one, and now a fourth
specialist verdict beside `encoded`, `already_true` and `not_mine`. It is
deliberately not a shade of `not_mine`: that word is a HAND-OFF and presumes
somebody else can hold the work, which is exactly what was false here.

**REFUSE is the engine's, and the hands are told nothing about it.** They run
BEFORE the dial is read, they are tools rather than policy, and a rule they had
to reason about would live in six places instead of one. So a hand always does
its job and the dial decides whether the work survives.

### What the refuse arm found, which was bigger than the shutter

`apply_player_authority` moves two labels -- the claim's scope to `intent`, the
element's commitment to `contestable` -- and that is everything it can do,
because it runs AFTER the fan-out. The hands have already written the record.
Measured on one beat under both dials, everything else equal:

    world_author  downgrades=0  state_assertions {"rooms":{"bay":{"desc":"dark now"}}}
    actor_only    downgrades=1  state_assertions {"rooms":{"bay":{"desc":"dark now"}}}

Byte-identical. **Under hard mode the player's world assertion was relabelled
an intention and the world kept the fact.** `Design.md` called the ladder
Built; what was built was the labelling.

`voided_span_ids` joins the two id spaces -- a downgrade names a sequence
POSITION (`claim:<index>:...`), a record cites a SPAN id (`from_event`) -- and
`void_span_records` drops every record citing a voided span, WHOLE, across
every owner. The walker is `prune_blocked_phase_changes` unchanged: it already
answers "is this record's event dead", it reads `from_event` as of the same
day, and the deferred-phase floor calls it the same way a few lines above. A
second walker would be a second answer to one question.

`world_author` is the default and grants everything, so there is nothing to
void and the pass costs one falsy check on every beat of every story nobody has
changed the dial for.

WHAT IT CANNOT REACH, stated because it bounds the guarantee: a record citing
no event. `from_event` is how a record says which span it settles, and a hand
that omits it leaves a record nothing can attribute -- the same limit the
deferred-phase floor has always had, and the reason provenance was put ON the
record rather than beside it.

### Measured, after

Three declarations naming things the world did not hold
(`tools/interpret_beats.py --beat`, google/gemini-3.8-flash):

    nail the shutter across the window   ["objects","spatial"]  encoded / encoded
    padlock the forge door shut          ["objects","spatial"]  encoded / encoded
    hang my apron on the hook by the door ["body","objects"]    encoded / encoded

Six of six halves settled, zero failures. The spatial hand minted the window
edge it had refused an hour earlier; the apron beat found a pairing across two
different hands, `body` taking it off the wardrobe and `objects` minting both
the apron and the hook, neither of which existed.

## 4i. RECONCILING THE SHARED SPAN: by id, then by place

A span settled by several hands is settled in several channels, and the halves
have to add up. The owner, 2026-09-10, in three steps:

> I smell duplicate potential, since they are part of the same ledger now I
> imagine we can reconcile through code somehow.
>
> Perhaps as part of the solution we can temporarily show the part of the world
> state the colaborating agents see ... conditional formating based on what
> hands are interacting.
>
> We need some sort of reconciliation code that pairs things together based on
> where they are supposed to happen.

### What was already there, and why it was not enough

Roughly fifteen cross-channel folds, each written after a specific failure and
each matching on NAMES -- `_fold_duplicate_mints`, `mint_transferred_objects`,
`_fold_worn_garment_entities`, `derive_worn_containment`, `derive_borne_
containment`, `derive_scene_stations`, the pose invalidations. They match on
names because until the span id there was nothing else to match on, and one of
them says so: `resolve_garment("coat", ["coat rack"])` matches on the head
noun.

The apron case is already cured by that machinery and was measured to confirm
it: `objects` minted `apron`, `body` shed the same garment, and
`_adopt_shed_record` adopted the objects hand's record rather than minting
`apron_corin` beside it. One entity, both hands' facts.

The pair this session made routine is NOT cured, and nothing in the tree
reconciles it: an entity and a passage. Measured on the padlock beat, merged
from the two hands' real output --

    padlock position : (unplaced)
    passages         : {}
    edge names it    : False

-- two true records and one lost fact. The barrier ladder answers three
questions (sight, passage, sound) and `closed_door` already answers all three
the way `locked` would, so a locked door is not a missing rung; what is missing
is anywhere to say that a THING fastens a WAY.

### The three pieces built

**1. The span's result exists.** `span_records` walks the merged diff once and
groups every record by the span it cites, with its path and channel. The only
reader of that id kept a SET of ids and discarded the records, which answers
"did anyone cite this" and nothing else -- which is exactly why every fold is
per-pair. `_cited_event_ids` is now a projection of it, because two walkers
over one field are how the two of them come to disagree.

**2. Place is the join.** `span_pairings` groups a span's records by where they
happen, in tokens the ENGINE issues: `room:<id>`, and `way:<a>|<b>` from
`passage_id_for`, sorted, so the two mirrored edges of one doorway collapse to
one place. A record the engine cannot place returns None and pairs with
nothing. `span_colocations` is the coarser sibling a reconciler wants: a
doorway belongs to each room it joins, so the padlock standing in the forge and
the door between the forge and the well finally meet.

Span plus place is two engine-issued facts, and it BOUNDS an identity question
that was previously scene-wide. It does not decide one: two lamps in a room are
two lamps, and the tree's measured over-merge -- boards folded into a satchel on
an alias overlap, twenty beats of empty containment ledger -- was a decision,
never a grouping.

**3. The hands see each other, shaped by who is interacting.** `co_hand_view`
gives each hand the identity slice of every OTHER owner of a span it received.
Five functions for twenty pairings, keyed on the hand being LOOKED AT, the same
collapse `co_hands/<hand>.txt` makes for the prose -- what the body hand holds
is one answer whoever asks. Identity ONLY, holding the line the unconditional
worn-garment index already drew: *"this widens who can be NAMED, not what is
KNOWN"*. And the ways carry the doorway's own id, not just its name, because a
hand handed a name has to invent where its record went while a hand handed the
id can say it -- the same token the pairing groups by, so both sides of the
seam spell the place one way.

### Still open

An entity has no field for a passage, so "the padlock is ON that doorway"
remains unsayable and the pairing groups them only by the room they share.
`PASSAGE_FIELDS` is `(barrier, name, material, width)` and a passage is keyed
by its room pair, so a fastening would be a new persistent field with the whole
`docs/guides/DATABASE.md` checklist behind it. Left for the owner, with a third
reading worth weighing: a padlock may not deserve to be an entity at all, and
if the doorway's own record carried the fastening then the objects hand's half
of that span would be nothing and the span would belong to `spatial` alone.

## 4k. THE CAUSALITY RECOMPILER

The owner's name for it, 2026-09-10 -- *"basically we are making a causality
recompiler after our director deciphers and resolves"* -- and the thesis it
serves:

> a system that can decipher any arbitrarily long series of events by a player
> or character and resolve it properly with proper respect to chronology and
> space. Even though its disecting and feeding it to paralel agents.

The Director DECIPHERS the input into numbered spans. The five hands RESOLVE
them in parallel, each blind to the others and to a scene that has not moved
since before the beat. This puts the beat back together.

### Everything it reads is an identifier something ISSUED

That is the whole property, and the reason the ids exist:

    WHEN    the chronological span number
    WHOM    the record's subject -- its key under the channel
    WHERE   a room or a doorway, `room:<id>` / `way:<a>|<b>`
    WHICH   the Director's item number for the thing

None of it is read out of prose, which is what makes the questions answerable
without a model -- the owner's *"so you can ask, what happened and where with
basically pure code"*, and then *"what happened to whom and when."*

    span_records           which records are one EVENT's outcome
    span_pairings          which are in one PLACE; span_colocations, by room
    beat_item_records      which are one THING, across spans
    item_survivors         which record an object is rendered FROM, and what
                           else is true of it
    apply_item_transforms  the chosen record receives every transform, in
                           chronological order
    span_slices            the beat cut into its spans
    beat_worlds            the world as it stood BEFORE each span
    beat_ledger            all of it as one flat, queryable table

### Transforms, not records

The owner's abstraction, and it is the right one for the whole fan-out:
*"what the specialists actually give us are transforms we can apply to
objects, even if it's an object the specialists freshly minted."* Identity is
the item number, order is the span number, and a freshly minted object is one
whose first transform happens to be its creation.

The priority for which record an object is rendered from, in the owner's own
order: **actually exists in the world even before this beat**, then **freshly
minted by the most relevant authority**, then first written. And *"the chosen
object must receive all transforms."*

That last rule found a bug in the first implementation. `_dedup_duplicate_
entity_keys` says *"the fresh record's state wins whole"* -- and THERE the
winner IS the fresh record, so keeping the winner's state and rescuing the
loser's structure is one sentence. On this ladder the winner is the STANDING
record, so the two halves come apart: identity from the survivor, state from
the latest transform. Read literally, a crate that stood before the beat and
was opened during it kept its name, gained its material, and lost the fact
that it was open.

### Five classes, so the authority can be written down

*"if the object is freshly minted potentially by multiple agents, we have to
decide which is the highest authority for rendering that object, it might be
case by case, but thankfully we only have 5 classess to work with."*

There was no answer at all before this. The ladder's second rung is "the
channel's own hand", and the partition is DISJOINT -- every record already sits
in its own hand's channel -- so that rung never discriminated between two
hands. Two mints of one thing tied there and fell through to a tiebreak that
ordered them BY PATH, letting `entities.tardis` beat `rooms.tardis_interior`
on the letter e.

`_MINT_AUTHORITY` is `objects, spatial, body, contact, social`, ordered by how
much of a thing's OWN identity the hand's channels carry: `entities` IS a
thing's identity record and `rooms` is a place's, while `attire` names a
garment as worn, contact names relations between things that already have
records, and social names what minds hold true about them. CASE BY CASE stays
open and is recorded rather than guessed: a beat that mints a PLACE should rank
`spatial` first, and the table does not yet ask what kind of thing it is. It is
a named ordered tuple so that question has ONE place to be answered when it has
been measured.

### And neither fact is discarded

*"in that case interior and entity are two seperate facts about one object"*,
*"neither should be discarded."*

The channel decides which is which, exactly, because the partition is
disjoint. Two records in ONE channel are one hand's two attempts at one thing
and fold. Two records in DIFFERENT channels are two separate facts about one
object; choosing which to render FROM is not a claim that the other is a
lesser truth, and `apply_item_transforms` touches only the duplicates. The
keys say so: `render_from`, `duplicates`, `other_facts`.

### The replay, and why the cones came free

`world/spatial_fov` is pure, derived and never stored, and `spatial_rel` /
`body_visibility` / `hear_level` take the SCENE as a parameter. So handing them
a different scene answers for that world, and the geometry is respected by
construction rather than by a rule a caller has to remember. Three pieces made
it possible: order (spans numbered in declared order), slicing (`span_slices`),
and a scene per step -- `preview_player_state_assertions` already applies a
diff to a scene COPY for the onset preview, so this generalizes one
intermediate world to N.

Measured, one beat and one question:

    before span 2   Corin in yard   same_room True    hear full
    before span 3   Corin in box    same_room False   hear full      (door open)
    end of beat     Corin in box    same_room False   hear fragment  (door shut)

Three answers, none from a model. Today every event in that beat is judged
against the last row, so the first two are unreachable.

**A SCALAR CHANNEL CANNOT CARRY ITS OWN PROVENANCE.** `positions` is
`dict[str, str]` -- a body's position is a bare string with nowhere to put a
citation -- and movement is the single most perception-relevant event a beat
has. `phase_sources` is the sidecar built for exactly that, already taught by
the sheets and already read by `prune_blocked_phase_changes`, so `span_slices`
reads it where a record cannot cite for itself. A record's own `from_event`
still wins where both exist.

### Open

The first consumer of the chronological id is still unbuilt: perception dedupes
on the PHASE-graph id and streams each actor's sequence by `enumerate`, so
nothing yet delivers events to a mind in the beat's order. `beat_worlds` is the
primitive that path needs, and wiring it must SUBSUME the existing
onset/deferred split rather than run beside it, or a continuation phase applies
twice.

## 4l. AN OBJECT THAT EXISTS AS TEXT FIRST, AND IS MADE REAL NEXT PASS

The close of the 2026-09-10 design thread, in the owner's words:

> the director specialists and recompiler should be able to handle anything
> that happens in a singular room, even multiple if there are things already
> interacting across rooms, but that cross room interaction becomes weird when
> you mint a room and go inside that room and mint an object inside that
> minted room.
>
> the location can be minted before the recompiler runs so you can genuinely
> render someone within the new location and even show them moving inside it,
> just yeah minting an object inside a minted space is yeah.
>
> we can use event text describe what happened and even within the new
> location so anyone looking gets the proper event as it should be resolved.
> An object exists, but is only text, then is made real with the next director.

### The asymmetry is the channel partition, not the recompiler

A BODY in a newly minted room needs no reconciliation at all. The spatial hand
owns `rooms` AND `positions` AND `stations` AND `poses`, so minting the box and
standing Corin in it is ONE hand's self-consistent answer from ONE payload.
Rendering someone in a room the beat just made, and moving them about inside
it, works with no recompiler involved.

An OBJECT in that room needs two hands and neither can finish. `objects` owns
`entities` and mints the console; it has no field in which to say where the
console is, and the merge reads only each hand's own channels from its result,
so a position it wrote would not be overruled -- it would never be looked for.
`spatial` owns `positions` and was never handed the console. The fact "the
console is in the box" belongs to no single hand's channel set.

That is the whole of the residual, and it is why the recompiler earns its keep
on exactly one fact here. Everything else in the scenario never crosses a hand
boundary.

### Two-phase existence

    PHASE 1  the object exists as EVENT TEXT. The beat renders what was done,
             in the place it was done, and every observer receives it.
    PHASE 2  the next Director pass gives it a row and a room.

**Waiting one pass converts the hard case into the easy one.** By the next
Director the minted room is standing state, so placing an object in it is an
ordinary origin-room placement -- the case the tree already handles. The
deferral does not work around the problem; it dissolves it. And the next pass
has not yet expended its authority to ask where, which the current one has: it
has already dissected and dispatched, and has no second question left.

### Why it costs perception nothing

`composer.act_percept` admits an action element's observable surface gated on
concealment, rear arc and sight. It never consults the object's row. So an
observer sees the levers pulled on the console in the box because that is what
was DONE, and would see it identically had the console carried a row all along.
The perception layer cannot tell the difference, which is the strongest
available statement that nothing was lost.

Nor is the world lied to. There is no wrong row; there is no row. Absence is
truthful where a guessed room is not -- and the object was TEXT before any hand
touched it, because the player wrote it. Deferring the row is the engine
declining to pretend it has finished bookkeeping it has not.

### The bound, and the handoff

During the window the object has NARRATIVE existence and not MECHANICAL
existence: nobody can take it, no query finds it, nothing reaches it. Correct
for one pass and corrosive if it ever stretched to several.

The handoff is clean because the recompiler DECLINES rather than guesses in
exactly this case. Measured: with the movement attributed to its span the whole
three-link chain resolves (`crate -> yard`, `console -> box`); without it the
position falls into the unattributed slice, is applied first, and the
intermediate world is incoherent -- an actor standing in a room the beat has
not minted yet -- so `span_mint_rooms` returns nothing for that mint rather
than placing it wrongly.

### What it needs before it is built

The natural channel is `generation_requests`, which files a typed planning
need -- and NOTHING in the tree drains a `thing` or a `room` need.
`drain_planning_needs` loops `kind="person"` only, so a deferred object filed
that way sits open forever. Either the deferral gets its own consumer, or it
rides the payload channel instead: interpret's unresolved question into
resolve's payload, the way `authority_downgrades` does, a seam built precisely
because `engine_notices` reaches the next beat and that was judged a beat too
late.

And the dependency worth removing first: the chain rests on the MOVEMENT being
attributable to a span, and movement is the one thing that structurally cannot
carry its own provenance (`positions: dict[str, str]`). It depends on
`phase_sources`, measured at 25% emission. The engine already knows which span
carried the declared movement, so it can stamp that attribution itself --
deterministic, no schema change, and it turns the fragile link into a derived
one.

## 4m. THE EVENT LEDGER: the beat, written into the world

The owner's chain, on why a character's act was being handled twice:
"shouldn't it go character -> director -> recompiler -> world -> perception?
Why would it be rendered twice?" Then the principle, and it is the whole
section: **"perception should only be reading the world."** And what the world
is obliged to keep: "just because a majority of these are temporary actions
and dialogues, does not mean they shouldn't be rendered in the world. The
world just renders them in the order declared and what isn't permanent is gone
after perception rolls."

**WHAT WAS MISSING WAS A PLACE, NOT A FACT.** A position, a pose, an attire
row, a contact, a sound all live on the scene, and perception reads them
there. The beat's own ACTS lived only in the declarations -- the player's
sequence, then each character's -- so the one thing perception could not read
from the world was the beat. It re-derived it by CONCATENATING those
declarations, which is a guess at chronology and always the same guess:
everything the player did, then everything anybody else did. Live, that
renders a player who speaks, walks out and is answered as though the answer
came before he left.

The recompiler removed the reason. `beat_timeline` already reassembles the
beat as ONE ordered list -- the author's own order, each element citing the
declaration it describes -- so the order exists; it just had nowhere to live.

**THE ARROW INTO THE WORLD, in three pieces.**

* `director_evidence.beat_event_ledger` turns the timeline into rows.
  EVERY element becomes one, not just the categorized ones: work items are the
  categorized SUBSET of the beat, and a glance that settles nothing is still
  something that happened. `director_resolve` puts them on its output as
  `beat_events`, after the last floor has run on the merge.
* `compose_beat_scene` writes them onto the scene. That is the ONE composition
  of "the scene this beat produced", shared by `perception_outcome` and the
  commit, and it runs BEFORE the narrator -- which is the whole reason it is
  not written where `sensory_events` is. `_record_sensory_events` runs during
  the commit, after the narrator, so its record reads empty during its own
  beat and stale a turn later; that is right for a record the NEXT beat's
  sound field reads and exactly wrong for one this beat renders from.
* `perception._world_ordered_stream` asks the world what order the beat
  happened in, and permutes the named entries into it.

**NOT A `state_diff` CHANNEL, deliberately.** The diff is partitioned into 32
channels each owned by exactly one hand, and every seam over it -- ownership,
span attribution, reconciliation -- rests on no channel having two authors.
The ledger is the ENGINE's reassembly of what the hands produced, so it
travels beside the diff rather than inside it.

**NOTHING SWEEPS IT, AND THAT IS THE DESIGN.** The record carries the beat
that wrote it and `beat_ledger.beat_events` refuses any other beat's --
`sensory_events`' own rule, stated there as "the beat number IS the lifetime".
A sweep is a second thing that has to run, on every path, forever, and the
path it misses is the one that renders a stale event as though it had just
happened. A reader that must prove the beat matches cannot fail that way: a
crashed turn, a resume, a reroll, a restored checkpoint and a branch all
inherit a record that answers `[]` the moment the number moves. That is what
"gone after perception rolls" means with nothing doing the going. An empty
beat still WRITES a record, because "this beat had no events" and "no beat has
spoken" are different answers.

**THE SURFACE COMES FROM THE CITATION, and that is the firewall's clause
rather than plumbing.** Three descriptions of one act exist: the actor's
`attempt`, in their own words, routinely carrying purpose and intent; the
engine's `observable`, the intent-free outward form an onlooker is entitled
to; and the author's prose, a third description again. Measured on the join --
the player declared "scratch runes of slow and soften", the outward form is
"crouches over the sill", the author wrote "works at the windowsill". A cited
row takes the second. An UNCITED row takes the author's words and there is no
leak in that: `from_declaration` is empty exactly when nobody declared the act
-- a consequence, a thing the world did back -- so there is no actor's purpose
to strip, and the empty `declared` says which kind of row it is. The scene
record is a strict projection onto `EVENT_FIELDS`, so `attempt` never reaches
it at all.

**THE REORDER MOVES ONLY WHAT THE WORLD NAMES.** Named entries are permuted
among the slots they already occupy; an entry the ledger does not cite keeps
its exact index. The first rule tried was "an unnamed entry takes the position
of the last named entry before it", and it is wrong in the direction that
matters: an unbound dialogue row, a background presence's beat and a silence
minted for an unanswered address are appended AFTER the whole declared stream
on purpose, and anchoring them to a named neighbour dragged all three into the
middle of the beat the moment that neighbour moved earlier. Caught by the
test, not by reading it. Fewer than two named entries reorders nothing --
one cannot disagree with itself about an order.

**THE CAP IS 64 EVENTS**, and it is not a pacing judgement. Twelve measured
full turns held five events per beat on average and never more than fourteen,
so nothing an author writes reaches it; it exists so a model looping a
sequence cannot grow an unbounded blob inside a scene that is deep-copied
several times a turn. The FIRST events are kept, because the ones past the cap
are the ones a runaway wrote.

**WHAT IS STILL NOT BUILT.** Perception takes its CHRONOLOGY from the world
and still builds the stream's CONTENT from the declarations -- the dialogue
binding, concealment, visibility and the communication surfaces are all still
read there. An uncited row (something nobody declared: a consequence, a thing
the world did back) is in the ledger and mints no stream entry, so the world
records it and no onlooker is yet shown it. Both are the next step, and the
ledger is the thing that makes them possible rather than the thing that does
them.

## 5. What already exists to build on

This is a rewire of proven mechanisms, not a green field. **The output half of
the contract is already built** — and that is the single most important thing
about the size of this change:

- **Each hand's toolset already exists as its channel vocabulary.** A hand
  emits `contact_ops` with `op`/`relation`/`motion`, or `attire` records, or
  `inventory_ops`, and deterministic code applies them. No tool-calling loop is
  wanted or needed; the structured output format IS the toolset. Nothing about
  what a hand EMITS has to change.
- **Scene-scoped payload assembly**, already per-hand and per-channel.
- **Engine-assigned chronological ids.** `_manifest_items` numbers 1..N in
  narration order and the model is never asked for the number, because *"an id
  it authored could repeat, skip, or reorder."*
- **Category routing.** `manifest_category_targets` resolves a category to the
  hand or channel that answers for it, through hand names, channel names,
  plural tolerance and pack aliases.
- **The disjoint channel partition**, which is what makes parallel hands safe.

**So the change is confined to what a hand RECEIVES.** Its output format, the
code that applies it, the channel ownership map and the scoped world-state
payload all stay as they are. What changes is that the second half of the
payload stops being narrative and becomes instructions.

## 6. The open question: record-shaped channels

**This is not solved and should not be papered over.**

A hand's ledgers are either EVENT-shaped (`contact_ops`, `inventory_ops`,
`substance_ops` — a thing that happened) or RECORD-shaped (`poses`, `overlays`,
`conditions`, `attire`, `entities`, `rooms` — the whole current state of a
subject, restated every beat).

"Resolve this chunk onto the world" is a natural instruction for the first
kind. For the second it is not: a pose record is re-emitted whether or not the
pose changed, so there is frequently no *chunk* to attach the instruction to.

Measured consequence, 2026-09-09: of the 13 entries produced by hands a
categories-only dispatch would have skipped, **12 were committed, and 11 of 11
on record-shaped channels**. `director_body`'s four channels are ALL
record-shaped, which is why the manifest can never dispatch it — and why the
`ledger_notes` trigger could not be deleted (`§3c-quater`).

So the contract needs a second instruction shape, something nearer *"this
subject's record needs restating, and here is why"*, with its own answer to
what a chronological id means when nothing discrete happened. Until that is
designed, an event-only pipeline reaches `contact`, `objects` and `social`
cleanly and leaves `body` — the hand with the 76% empty-call rate — unaddressed.

## 6a. THE ONE EXCEPTION: minting a room is authorship

**Owner, 2026-09-09: "the only one that might benefit from some authorship is
spatial minting a new room or planned room with high fidelity."** Every hand
does some scoped invention (section 1); this is the far end of that scale, and
the one place the scope is arguably too large for the hand holding it.

Naming a garment or wording a substance is invention bounded by a thing that
already exists. A minted room is not: the hand is writing the place itself into
existence, and the words outlive the beat by an unbounded margin. Its own sheet says so:
`desc` is *"the only durable record of how this place reads"*, and *"descs do
not expire, so a place revisited long after is rendered from these words alone
-- thin descs are how the same room comes back a different room."* Names,
anchors, `light` and `quiet` are the same kind of writing.

**And removing the prose took away an input it was using.**
`DESIGN_ROOM_FIDELITY.md` records the spatial hand doing exactly this: *"the
road run's spatial hand read the sentence and wrote `{w: 15, d: 20}, round`
from it."* That is a transcription tool reading narrative to author a place,
which is the contract's problem in miniature -- and the answer is not to give
the prose back, because under this contract the Director is not writing prose
for it to read.

What the hand still has when it mints today: the dissected chunk, its
`director_note` and per-event notes, the room index, and -- when they exist --
`planned_rooms` and `mapping_scene_proposal`. What it no longer has is anybody's
rendering of what the place is like.

**The owner's proposal: spatial calls a specialised room-mint agent**, for the
two cases that need one:

- a **planned** room, created by the Story Planner and not yet fleshed out;
- a **new** room, created by a player declaration.

That fits the existing split rather than inventing one:
`DESIGN_ROOM_FIDELITY.md` already rules that *"the Director writes extents on a
live room; the WRITERS' ROOM writes them on a planned one"*, so authorship of
places is already understood to belong somewhere other than the beat's hands.
A mint agent would take the plan, the purpose, the lore and the declaration --
the things a place should be written from -- rather than a beat's narration,
which is what it happened to have.

**Not built, and not to be built on this evidence alone.** It is a new model
role: it needs its own scope, its own gate (mint is rare, and a role that runs
on every beat is the wrong shape), and a measurement of what room fidelity
actually is today before and after. Registered here so the gap the prose
removal opened is on the record rather than discovered later as thin descs.

## 7. What this supersedes

`DESIGN_NARROW_MODEL_INTERFACE.md` is evidence, and its measurements stand. Its
PROPOSALS are largely answers to the wrong question, because every one of them
assumes the hands read prose:

- §3c (drop the `ledger_notes` trigger) — rejected on its own evidence, and the
  deeper reason is here: the manifest was never the hands' input, so it was
  never load-bearing enough to route on.
- §3d (eight concept kinds) — closed; the model already answers with five hand
  names.
- §4a / §7 (cut the shared core) — the core is 39% `resolved_events` protocol
  and the rest is rules the Director holds *because* the hands were never given
  structured input. Trimming it optimizes the symptom.
- §9 (reasoning effort) — real, and worth setting; but 90-97% of specialist
  output is trace spent parsing prose, so the honest description of that lever
  is that it makes the wrong architecture cheaper.
