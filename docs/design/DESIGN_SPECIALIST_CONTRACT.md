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
