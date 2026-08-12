# 21 — Numbered beat events

## The problem this closes

Under the orchestrated Director (design note 19) the beat is written once and
encoded by several specialists at once. Something then has to answer: *did
everything the prose asserted actually reach objective state?*

Until now that question was answered by comparing text. The resolve's
`changes_asserted` manifest described each change in its own words; the
reconciliation seam looked at the merged `state_diff` and tried to decide
whether some entry in it was *the same change*. Every measured failure of that
seam was the comparison going wrong in a new way:

- a manifest naming the **garment** checked against a diff keyed on the
  **wearer**
- `"prior hand-to-stomach contact"` — a subject naming the **relation** —
  checked against the `contact_ops` that ended exactly that relation, and
  rejected because the text did not name a participant
- a contact's ended endpoint living in `crossed_target_part` while only
  `target_part` was read
- a within-room drop encoded as a station, checked by a rule that only looked
  at `positions`
- the repair's own correct verdict thrown away because its subject wording
  did not match the omission's

Each was fixed individually. The class was not: any new wording the model
invents reopens it.

Measured cost of the class, chat 71 turn 10, the same beat played three times:
`director_resolve` at **105s / 117s / 225s** against **14s** monolithic, with
6 of 11 manifest items reading as omissions against a diff that encoded them.
Every one of those false omissions bought a full-core repair call, which
answered "already encoded", whose answer was then discarded. Three false
`objective state may be stale` warnings shipped anyway.

## The design

**The Director numbers the beat, and the numbers round-trip.**

1. The resolve lists `changes_asserted` **in the order the changes happened**.
   The prompt says so explicitly: a hand leaving a waist and a hand arriving at
   one are two entries, in that order.
2. `_manifest_items` assigns `event_id` = 1..N in emission order. **The engine
   numbers, never the model** — an id the model authored could repeat, skip or
   reorder, and every downstream use assumes a dense sequence over exactly this
   manifest.
3. Each specialist's manifest slice — already filtered by category to the
   channels it owns — carries the ids. One filter builds both the payload and
   the record of which ids that specialist is *answerable for*; two spellings
   would let a specialist be judged on an event it never saw.
4. Each specialist returns `resolved_events: [{event_id, status}]`, one entry
   per id it was handed, ids copied exactly. Status is `encoded`,
   `already_true`, or `not_mine`.
5. Composition reads the ids. An event whose owner answered it with a settling
   verdict is settled; an event nobody addressed is a named gap.

## What the echo is, and what it is not

**It is evidence, not authority.** `encoded` is still checked against the
merged diff by `_evidence_present` — model output is provisional until
deterministic code validates it, and that does not change because the model
now says something about itself.

What the echo buys is knowing an event was *asked about by the mind that owns
it*. That is what makes a second call pointless. The measured waste was never
a missing answer; it was asking a specialist to repair a change it had already
correctly encoded, or correctly declined to re-encode, and then failing to
recognise the reply.

So the rule is narrow: **an answered event buys no second LLM call.** Detection
is untouched — the omission is still detected, still recorded, still visible in
the drawer. Only the escalation is suppressed, and only for events their owner
addressed.

Three guards keep the acquittal from becoming a way to go quiet:

- A verdict on an id the specialist was **not handed** is discarded. Otherwise
  a model echoing the whole manifest back would silence every omission in the
  beat.
- A specialist whose call **failed** acquits nothing. Fail-open must not become
  fail-silent: its events stay unaddressed and still escalate.
- `not_mine` **does not settle**. A specialist saying the change needs a
  channel it was not granted is reporting scope under-grant — a gap reported,
  which is exactly what the repair tier is for.

## Chronology

The ids are the beat's own order, which is a second thing the engine did not
have. Merge order across specialists was already deterministic (canonical
`SPECIALISTS` order, never completion order, so a reroll composes identically);
what was missing was any record of what happened *before* what. Ordering within
a channel survived because a channel is a list; ordering *across* channels —
the jacket coming off, then the jacket landing on the platform — did not.
Numbered events carry it, and carry it through the specialists unchanged.

## The monolithic path

Unchanged, and pinned by test. No specialist runs, so the addressed-event index
is empty and every omission falls through exactly as before. The manifest still
carries ids, which are simply unused there.

## Residuals

- Composition **uses** the ids for coverage and escalation; it does not yet
  order the *application* of the merged diff by them. Every delegated channel
  is currently an end-state assignment, so application order does not change
  the result — but that is a property of today's channels, not a guarantee, and
  a genuinely sequential pair of ops in two different channels would need it.
- `already_true` is trusted to suppress a repair, not to prove standing state
  carries the change. Verifying it against the scene per category is the
  natural next step and would let the seam distinguish "correctly no-op" from
  "quietly wrong" without a call.
- The routed repair does not yet tell a specialist *which ids* it left
  unaddressed. It gets the omissions; the ids would make the second ask as
  precise as the first.
