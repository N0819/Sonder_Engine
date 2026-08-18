# Region visibility: concealment, applied to bodies

Status: **step 2 built (`f0721da`) and wired to perception (`56bd561`);
partial torso coverage built in the current unreleased development line.**
Written 2026-08-08 from a design conversation and updated 2026-08-09 after
the first live consumer and partial-coverage case landed.

`attire.concealing_garments` and `agents.common.region_visibility` exist and
are derived. `agents.common.observer_body_regions` is now their production
consumer: every perception pass receives only observer-safe body surfaces, and
adversarial tests prove concealed authored markers never enter the model
payload. `story/attire.py` still carries the four-state
ladder this note argues against; collapsing it is step 4 and is gated on the
re-measurement in step 1.

## Partial coverage inside a coarse region

The first production case exposed a distinction the original eight-region
model could not state: Hinami's tank top remained worn over her chest while its
rucked hem exposed her ribs and stomach. Treating all of `torso` as bare would
leak the chest description; treating all of it as covered loses the midriff.
Parsing "hem dragged to midriff" from a condition would make free prose a
second state machine.

The additive answer keeps `REGIONS` coarse for contact, injury, position and
facing, and gives only the torso a closed coverage axis: `chest | midriff`.
A garment may carry `covered_zones:{torso:[...]}`; absence means both zones,
and the list states which zones remain covered. The torso region may carry
`beneath_zones:{chest,midriff}`. The coarse `beneath` string remains the
backward-compatible answer only when the whole region is exposed; it is never
used for one-zone exposure.

Resolve authors the transition structurally through
`attire.<body>.coverage:{<garment>:{torso:[zones still covered]}}`. Commit
resolves the garment handle against the canonical wardrobe and stores the
coverage override with the garment. Perception derives a surface for each zone
and then applies the existing body-level vantage/containment gate. Thus a
payload may say `chest: fitted tank top; midriff: bare — faded scars`, but can
never receive the covered chest's body description merely because both zones
belong to `torso`.

This is deliberately not a general fine-grained anatomy. Add another zone axis
only when a measured story action needs independent coverage and an author can
supply its body description without inference.

## The proposal, in the author's words

> "instead of loosened i was thinking of just having removed be the only other
> state than worn, but have it so world objects can cover and entangle with
> body regions, in fact we should have visibility logic for body regions."

> "basically we do concealed or in cover from our prior design but onto
> individual body regions."

So: drop the garment state ladder to `worn | removed`, and express everything
the middle rungs were reaching for as **coverage of a region** — by garments,
by world objects, by containment — with **visibility derived per observer**,
in the vocabulary the engine already uses for concealed action.

## Why the ladder should go: it never ran

`GARMENT_STATES` is `("worn", "loosened", "open", "removed")` and `advance`
clamps a garment to one rung per beat, so that undressing has "a dramatic
middle worth staying in". Measured across 1,625 body snapshots in `engine.db`:

| state | count | share |
|---|---|---|
| `worn` | 3,321 | 94.0% |
| `removed` | 205 | 5.8% |
| `loosened` | 8 | **0.2%** |
| `open` | **0** | **never, once** |

205 removals against 8 loosenings. The clamp that is supposed to route every
removal through the middle is barely engaging, and half the vocabulary has
never been used by anything.

**One caveat on that denominator, and it matters.** The decisive-attribution
bug fixed in `a24e653` was flagging the ACTOR rather than the person being
undressed, so the clamp was firing on the wrong body for the commonest phrasing
("Corin strips her clothes off"). These numbers are of the broken behaviour.
Re-measure after a few stories on the fix before treating the ladder as dead —
this repo's own rule is that a mechanism should be counted firing against the
opportunities it had.

## Why coverage says more than a state word

`loosened` and `open` are trying to describe *how much a garment covers* using
an adjective about the garment. Coverage says it directly, and unlike the
adjective it is something code can act on:

- an open robe **covers torso, not groin** — a fact about regions that exposure,
  perception and weather protection can all read;
- `state: "open"` is a label nothing can compute from, which is why nothing
  ever did.

The dramatic middle survives, better expressed: not "the robe is open" but "the
robe no longer covers the groin". That is a real state change with real
consequences rather than a word in a field.

## The vocabulary already exists

Nothing here needs a new concept. It needs an existing one pointed at bodies.

| existing | today | under this design |
|---|---|---|
| `visibility: overt \| concealed` | an action or a spoken line | **also a body region** |
| `conceal_from: [names]` | who specifically cannot see an act | who specifically cannot see a region |
| `attire.covered_regions` / `exposed_regions` | binary, garments only | the seed of the derivation |
| `attire.attaches` | a hair clip covers nothing | unchanged, and the reason coverage ≠ presence |
| `spatial.hiding_holders_of` | a body shut inside something | one of the things that conceals a region |
| `_visible_rooms_for` (`67325ba`) | facing decides what you see | the same egocentric frame decides which regions face you |

`conceal_from` being **per-observer** is what makes the transfer honest rather
than cosmetic: region visibility is inherently per-observer. Someone standing
behind you cannot see your front, and the engine already computes facing,
`behind_sources` and `proximity_to_sources` for exactly this class of question.

> **Correction, found while building step 2.** The sentence above overreaches.
> "Someone behind you cannot see your front" is not derivable from anything on
> disk: `REGIONS` is `head, torso, arms, hands, waist, groin, legs, feet` and
> has **no front/back axis**, so there is no "front of the torso" to subtract.
> Vantage therefore applies at BODY level -- rear arc, sight level, containment
> -- which is what the engine actually computes. Per-region facing would be a
> new anatomical model, which is invention rather than the promotion this
> design claimed to be. Anyone reaching for it should cost it as new schema.

## What is genuinely missing

**There is no spatial `cover` concept.** Grep across `world/spatial.py` and
`story/scene.py` finds none. A body behind a table, a counter, a thrown cloak is not
expressible today. That is the one new piece, and it is what "world objects can
cover" needs.

### Step 3 splits unevenly, and the cheap half is very cheap

Found while building step 2. "World objects can cover a region" is two
different problems wearing one phrase, and only one of them needs the missing
concept.

**Draped cover — a blanket over a sleeper, a cloak across a lap.** This needs
NO spatial concept at all. It is omnidirectional (everyone loses the same
regions, from every angle) and region-scoped, which is precisely how a garment
already behaves. So the object does not need a new relation: commit can mint it
into the body's own attire regions as a non-`attaches` garment when the
Director drapes it — the exact mirror of `_mint_shed_garments`, which already
turns a removed garment into a room object — and `region_visibility` attributes
it with **zero changes**, because it is a covering garment as far as the
coverage model is concerned.

What that costs: one commit-side path, and a decision about what happens when
the body moves (does the blanket travel, or fall?). What it buys: the whole
intuitive half of the feature, using machinery that already works in the
opposite direction.

**Line-of-sight cover — a table, a counter, a parapet.** This is the genuinely
new piece, and it is new because it is *directional*: whether the counter hides
your legs depends on where the observer is standing, which is not a fact about
you or about the counter but about the three of you. Sketch, deliberately not
built:

- an entity field `cover: {"height": "waist" | "chest" | "full"}` in
  `_ENTITY_DEFAULT_FIELDS`;
- derived per observer from what already exists — observer and body on opposite
  sides of the cover's anchor (`stations` plus `entity_side`/`_relative_sector`)
  conceals the regions at or below that height;
- surfaced as a fourth `by` kind, `{"cover": ["the oak table"]}`, which the
  existing one-key-dict shape absorbs without changing a single caller.

What that costs is the reason it is separated: a Pydantic declaration (mind the
`stations` `extra="ignore"` scar), a commit merge path, and archive/checkpoint/
branch handling — the full `docs/guides/DATABASE.md` checklist. It is real schema work
and should be costed as such rather than folded into "add object coverage".

**So the order within step 3 is: draped first, line-of-sight second, and they
should be judged separately.** Draped cover is close to free and delivers the
case most stories actually want. Line-of-sight cover is a feature.

## Cover and entanglement are two things, not one

Worth separating before either is built, because conflating them repeats a
mistake this module already made once:

- **Covering** — a blanket over a sleeping body, a cloak across someone's lap.
  Concerns *visibility*.
- **Entangling** — rope around the arms. Concerns *capability*: it covers
  almost nothing and restricts almost everything.

`attaches` exists precisely because a hair clip is **present without
covering**. A rope is the mirror: it **restricts without covering**. Entanglement
belongs with `contact_ops` — where contact is already modelled as a relation
between two bodies rather than a property of either — and with whatever gates
what an actor can attempt. It does not belong in the coverage table.

## Derived, not stored

Region visibility should be computed from coverage at read time, never written
into the scene.

The reason is a scar in this module: `wearing`, `state` and `regions` are three
representations of one fact, and they drifted — a live body once read
`['corset', 'worn', 'skirt']` with a phantom garment named after a state, while
its regions were clean. Every writer outside commit must now call
`rederive_entry` or they diverge again. A stored `visible` flag per region would
be a fourth representation of the same fact, with the same failure mode and no
new information.

`covered_regions`/`exposed_regions` are already derived. This extends them; it
does not add a parallel store.

## What breaks

- **`advance` loses its job.** With two states there is no rung to clamp. The
  pacing it enforced has to be re-expressed as coverage changing gradually, or
  deliberately abandoned — say which, because "it just became instant" is how
  the engine behaved before `advance` existed and it was a complaint.
- **`decisive_targets` may become unnecessary**, or may be re-aimed at coverage
  rate. It exists only to lift the one-rung limit.
- **`compact_line`'s `(state)` slot** narrows to worn/removed and gains
  coverage/visibility, which changes the payload shape — and payload shape
  changes are the class CLAUDE.md warns about, where nothing errors and prose
  reads subtly wrong fifty beats later. A/B on a long story with
  `tools/stability_run.py`.
- **Migration.** 39 of 56 live chats store attire with no region breakdown at
  all; they are migrated on read by `rederive_entry`, so they inherit whatever
  this becomes without a backfill. Anything holding `loosened`/`open` — 8 rows
  corpus-wide — maps to whatever coverage that garment implies, or to `worn`.

## Order, if this is built

1. Re-measure the state distribution after a few stories on `a24e653`. The
   number that justifies the whole change was taken against a bug.
2. Promote region visibility to a derived function over today's coverage, with
   the `overt|concealed` vocabulary and per-observer scoping. No schema change,
   no ladder change — it is purely additive and immediately useful to
   perception.
3. Add object coverage — **draped first** (no new concept; mint it as a
   covering garment), then line-of-sight cover, which is the part that needs
   the missing spatial concept and the schema work. See the split above.
4. Only then collapse the ladder, once visibility is carrying the weight the
   middle rungs were supposed to.

Steps 2 and 3 are useful on their own. Step 4 is the one that cannot be undone
cheaply, so it goes last.
