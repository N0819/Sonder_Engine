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

## Breadth: every observable change reaches a hand (added same day)

Numbering exposed the next layer. On the first live beat under it, two of six
events came back `not_mine` from the body specialist — *"slight quiver
throughout body"* and *"heavy heated breathing"* — and bought a 49.2s repair
call that asked the same specialist the same question again. It was right to
decline: those had no channel. The gap was upstream.

Two rules now govern the manifest, and they replace the old "persistent
changes only" framing:

**Always the closest matching category, never an omission.** An imperfect
category still reaches the hand that owns the ledger; an omitted change
reaches nobody and silently never happened. Visible physiology is `overlays`
where it marks the surface and `conditions` where it impairs; what a body can
still do is `vitals`.

**The only thing that stays off the manifest is a thought.** What a mind
privately felt, wanted, feared, decided or realised is not a change to the
world. Everything a body did or a world underwent that another present mind
could have observed belongs on the list, however small or brief. Attempts
remain excluded on their own grounds: an act that did not complete changed
nothing.

Structurally, the category vocabulary was narrower than the channel set, and
the difference was silent. `overlays` and `vitals` were owned by the body
specialist and reachable by no category at all — the same defect that killed
`contacts`/`substances`/`poses`/`stations` in 8.2, just not yet hit. Three
tests now hold the two sides level: every delegated channel must be reachable
by some category or listed as unreachable by design with a reason; every
category must route to a channel some specialist owns; every alias must
normalize onto a routed category. Adding a channel now costs a decision
rather than producing a silence.

## The omitted-thought ledger

`thoughts_omitted: [{subject, thought}]` on the resolve. **It commits
nothing.** No channel reads it, no specialist is handed it, no mind perceives
it, and it is never rendered to a player.

Its whole job is to make an honestly interior beat distinguishable from a beat
that lost its changes. Those two look identical from the outside — prose
asserting something, a diff carrying nothing — and the seams that watch for
the second were spending calls on the first. The deep audit receives it as
`declared_interior` and is told that a declared thought is not an omission,
with the one guard that matters: a thought that CAUSED an observable act does
not shield the act.

What it deliberately does NOT quiet is the tripwire. A successful roll or an
asserted effect-claim is proof the world moved, and no amount of declared
interiority accounts for an empty manifest there — that case is exactly what
the tripwire exists for, and the ledger is recorded beside it rather than
excusing it.

## Residuals

Two of the original three are closed; the record of how is part of the design.

- **Application ordering: closed as a proven invariant, deliberately not
  built.** Composition uses the ids for coverage and escalation, and that is
  all the ids are needed for, because diff application is order-independent
  across specialists *by construction*: every delegated channel has exactly
  one owner and assembly replaces whole channels, so no channel is ever
  interleaved from two model sources; every dict channel is a keyed
  end-state upsert; the only appliers that walk an op list against evolving
  state (`apply_contact_ops`, `apply_substance_ops`) have their entire
  read/write family — contact_ops, substance_ops, containment, scales —
  under the ONE contact specialist, so within-beat chronology *is* that
  specialist's own list order, preserved verbatim; and every genuinely
  order-coupled cross-channel pair is adjudicated by a deliberate fixed
  convention in `spatial.merge_scene_with_diff`, each with a stated causal
  reason (substances resolve against the PRE-BEAT contact topology and
  apply before contact removals; scale changes cancel contacts before the
  beat's own ops; stations derive after contacts settle; vitals last).
  Event-id ordering would re-litigate conventions each chosen deliberately —
  including the suspect case, a contact ending and a new contact on the same
  part in one beat, which lives entirely inside one specialist's one list.
  What would need ordering, and is therefore refused by the tripwire test
  (`test_diff_application_is_order_independent_by_construction`): a
  sequential-stateful op channel granted outside its family's owner; a new
  delegated op channel left unclassified; two owners writing one coupled
  family.
- **`already_true` verified: closed as a defect detector, deliberately not a
  truth prover.** The manifest's structure carries no *direction* — whether
  a change puts the garment on or takes it off lives only in its prose, and
  prose matching is the boundary this design exists to get away from; both
  end states are legitimate no-op targets, so an undirected "is it already
  so" check is vacuous. What is decidable is whether standing state can
  support *any* definite claim about the subject, and
  `_verify_already_true` refuses the acquittal where it provably cannot: a
  garment marked `removed` while still resident in regions (the chat 70/71
  corruption — a ledger a specialist could honestly misread), wearing/
  regions membership drift, a standing position naming a non-room, a
  contained body carrying its own disagreeing position. A refusal is a
  named defect (`recon.already_true_refused`, a warning, `tell_director`)
  and the omission still buys its owner repair; anything undecidable —
  contacts and conditions above all — falls through to the existing trust,
  now deliberately rather than by omission.
- The routed repair does not yet tell a specialist *which ids* it left
  unaddressed. It gets the omissions; the ids would make the second ask as
  precise as the first.
