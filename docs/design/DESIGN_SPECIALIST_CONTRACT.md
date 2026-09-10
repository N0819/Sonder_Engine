# The specialist contract: hands resolve instructions, not narrative

**Nothing here is built; the gap is registered in
[`UNBUILT.md`](../UNBUILT.md) §1.1, which is the authority on its status rather
than this header.** The measurements are real and dated; the target is the
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
