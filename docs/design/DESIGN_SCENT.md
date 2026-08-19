# DESIGN_SCENT — what smells, and how a smell reaches a nose

Status: **Built (v1).** Standing smells and their delivery are in production;
decay, drift and travel are deliberately not built and are argued against
below.

Audience: whoever next touches `world/spatial_senses.py`, `agents/composer.py`,
`agents/perception.py`, or wonders why the narrator's smell row is no longer
always empty.

---

## 1. The situation this started from

Scent was a permission system with nothing to permit.

Every piece of the mechanism existed and was correct. `scent_level(rel)` graded
reach as `none | muffled | full` off `_SCENT_BARRIER_LEVELS` — a TABLE rather
than a set, because scent is the one channel of the four with degrees — and it
distinguished the three containment directions a live bug had to be measured to
separate. Cards could author a nose: `_SENSE_CHANNEL_ALIASES` mapped
smell/olfaction/nose onto the scent channel and `sense_adjusted` shifted the
grade from anosmic to preternatural. `agents/perception.py` computed
`scent_channel_to_sources` for every perceiver on every beat.
`agents/composer.py` declared `"smell"` in `CHANNELS`, and
`agents/narration.py` gave it a row in the narrator's per-sense manifest.

And nothing anywhere said what anything smells LIKE. No card, no scene entity,
no substance record, no `state_diff` channel. So no percept builder ever
emitted `channel="smell"`, `scent_channel_to_sources` was read by nobody
(`docs/experiments/AUDIT_PERCEPTION.md` F4/F5), and the narrator's smell row
said, in code, `"open air; nothing ledgered rides this channel"` — which was
true, and had been true on every beat of every story.

There was one apparent exception and it was not one. `sensory_events` on the
opening turn could carry `{kind: "smell", ...}`, and 2 of the 199 stored live
events do. But `composer.ambient_percepts` read `channel` and `room`, while
both packs' prompts ask for `kind` and `source_room` — so every authored
sensory event in the engine's life fell to channel `mixed` and was delivered to
every observer in the scene regardless of room. The prompt and its reader were
two spellings of one contract and nothing folded them.

## 2. What smells, and where the fact lives

The shape follows from what actually smells, in fiction and in fact. There are
three kinds of smelling thing, they are already three different kinds of record
in this engine, and the fact belongs on the record that already exists.

**A body has a standing smell.** A person, an animal, a thing: stable, part of
what it is. That is `embodiment.scent` on the card, sibling of
`embodiment.visible` — the olfactory counterpart of a body's stable appearance,
and deliberately clear of the two physical domains beside it. Clothing a
character was authored wearing is `initial_outfit`; matter that landed on them
during play is `scene.substances`. `character_scent`/`persona_scent` read it,
and `scene.scent_of` dispatches on card kind like `senses_of` and
`abilities_of`.

**An object has a smell.** Bread in an oven, lamp oil, a censer, a corpse. That
is `SceneEntityDef.scent` — the sibling of `light_source`, which is the field
saying what a thing emits on the OTHER non-visual channel. A lamp emits light;
an oven emits a smell; both are standing properties of the object rather than
events in a beat.

**Matter deposited somewhere smells, and it is the commonest case in play.**
Blood, smoke, spilled wine, perfume on a collar. `substance_ops` was already
moving matter around with a fiction-authored material name, a placement and an
amount; it gained `scent`. **This is why there is no fourth ledger and no new
Director channel.** The contact specialist already owns `substance_ops` and the
objects specialist already owns `entities`, so "the Director must be able to
emit scents" needed no new op, no new specialist, and no new field on
`StateDiff` — one more key on a record the Director already writes. Reusing an
existing ledger beats minting a parallel one, and the parallel one would have
had to answer, separately, every question the substance ledger has already
answered about pooling, removal and conservation.

### 2.1 The event case, and why it stayed where it was

A smell can be an EVENT rather than a state — something burning now, a sudden
reek. `sensory_events` already exists for exactly that, is room-scoped, and now
actually reads its own prompt's field names, so an opening's authored smell
lands on the smell channel in the room it belongs to.

The per-beat surface deliberately did not copy that shape. A transient reek in
play is almost always one of the two standing facts already covered — smoke
filling a room is matter with `placement: "room"`, a fire is an entity — and
the substance ledger delivers its own beat-delta percept the moment the deposit
lands. Adding a per-beat `sensory_events` channel would have meant a third
place to say "something smells", owned by which specialist is not obvious, with
no ledger behind it to remove it from later. The distinction the prompts now
teach is the one the engine can actually keep: a signal that flares and passes
is a sensory event, a thing that goes on smelling is an entity's `scent`, and
matter that landed and stayed is the matter ledger's.

### 2.2 Field placement traps, all of them previously sprung

Each of the three carriers had a trap the codebase had already hit on the field
beside it, and each is pinned in `tests/test_scent_ledgers.py`:

* `SceneEntityDef.scent` is a DECLARED field, because `model_dump()` drops what
  a model does not declare — the reason `enclosure` and `light_source` are
  declared.
* It is also listed in `spatial_merge._ENTITY_DEFAULT_FIELDS`, because the
  merge's tail loop copies unlisted keys verbatim and validation fills an
  absent field with its default first. Outside that map, the `None` on every
  beat that did not re-declare the oven would have overwritten its smell rather
  than reading as silence — which is precisely what made `enclosure` and
  `light_source` settable only at creation for as long as they were missing
  from it.
* On the substance record `scent` sits beside `amount` and `detail`, never
  among the identity fields, so a later release re-describing one pool updates
  how it smells now. Hashing it into `_substance_id` would file drying blood as
  a second puddle beside fresh — the `_same_pool` lesson, three saliva rows on
  one region across chat 69's turns 74/78/80.
* On a card the default is `""`. Every card in every existing story reads as no
  smell, byte-identical to the behaviour it already had, because an authoring
  gap must never mint a percept.

No schema-change checklist was needed: all three ride blobs that already
travel — the frame-scoped `world.scene` for entities and substances, the card
sheet for bodies — so checkpoints, branches and portable archives carry them
with nothing added.

## 3. How a smell reaches a nose

`perception._scent_sources_for` reads the three ledgers into the grader that
already existed, and hands the survivors to `composer.scent_percepts`, which
mints `Percept(kind="scent", channel="smell")`. It runs on the standing-percept
path all three perception stages share, so a smell is in a mind's view on every
beat rather than only at the opening — the failure `body_state_percept` has
(F6).

Nothing here restates the barrier table. Each source is graded by exactly the
relation its own channel already uses (`spatial_rel_between` for a body or an
entity, `spatial_rel` for matter lying in a room), so a closed door muffles a
smell and a wall stops it because `_SCENT_BARRIER_LEVELS` says so. A window is
the case worth naming: glass passes sight and stops air, and the two channels
are answered separately, as they always have been.

The card senses gate applies as it does everywhere: an anosmic card receives
nothing, a keen nose lifts a muffled smell to a whole one, and acuity never
opens a wall — `sense_adjusted` caps the one direction that adds, so from
`none` scent stays `none`, because a sealed wall is not something a nose
penetrates and `none` cannot say which it was.

One subtraction the barrier table cannot make, because there is no edge between
two rooms to consult: matter placed `interior` or `contained` has a body or a
vessel between it and the room, so its smell does not reach one. That is read
off the ledger's own `placement` rather than guessed.

A body does not smell itself. `others` excludes the observer, and a standing
fact true of every beat of a character's life is noise in a context window
rather than a percept.

## 4. Firewall question one — a muffled scent must arrive muffled

`scent_level` has returned three values since it was written, and downstream of
it the two that are not `none` were the same value. There was nothing for the
grade to be a grade OF.

The wrong answer is to mangle the string. What a half-open door withholds is
not the smell: the material crosses, and that is exactly what `muffled` means.
Degrading the phrase would be a lie about the physics and, worse, would need
language-specific string surgery in a layer whose whole contract is
decision-free realisation.

What genuinely does not cross is **which body the smell belongs to**.
Attribution is a second channel's work — you know the woodsmoke is his because
you can see him standing in it. So the degradation is structural: a muffled
scent is delivered UNATTRIBUTED, `source_label` withheld and `fidelity`
`degraded`. No string is mangled; a field is subtracted, which is the shape
nearly every guard in this engine has.

The same rule then answers a case nobody asked about and which would otherwise
have been wrong: a full-strength smell from a body in the same room that the
observer cannot SEE — a dark room — also arrives unattributed. The smell
crosses; the knowledge of whose it is was the other channel's to deliver and
that channel is shut.

Attribution therefore requires two things: `scent_level` full, and a real sight
channel to the source (the same `visual_level_between == "full"` and non-rear
test the appearance loop already uses), under the label this observer's display
map already earned.

## 5. Firewall question two — does a scent defeat a disguise?

**No, and it does not need to, because a scent percept carries a MATERIAL and
never a NAME.**

`story/scene.py::disguise_breaks_recognition` settled the shape of this
question for sight: a disguise conceals FEATURES, and identity is a separate
claim a disguise has to make explicitly. The temptation on a new channel is to
answer the identity question again, one way or the other — either "a smell
recognises through a hood" (which hands out a name the observer has no channel
to) or "a disguise seals the body" (which is false about every hood there has
ever been, and makes minds conclude less than their senses support).

Both are wrong for the same reason: the engine should not be answering it at
all. The percept says `tallow and cold iron`. The label on it, when there is
one, is whatever this observer's display map has already earned for that body —
so a disguise that conceals identity yields the stranger's descriptor here
exactly as it does for presence and pose, and a disguise that only hides
features leaves the name intact here exactly as it does there. There is one
recognition answer in the engine and the smell channel reads it rather than
re-deciding it.

What a mind then does with `the hooded figure smells of tallow and cold iron`
is the interesting part, and it is the mind's: it may recall that this is the
smell of someone it knows and conclude who is under the hood. That is the good
fiction, it is arrived at legitimately from the mind's own memories, and it is
**defeasible** — two bodies can wear one perfume, which is a plot rather than a
bug. Inference is the product, not the risk.

Two consequences of the same rule, both deliberate:

* **An entity's smell is never attributed at all.** The composer admits no
  percept for the objects standing in a room, so naming the oven on the smell
  channel would be this channel delivering a fact about the room's contents
  that no channel gated. The smell arrives; the oven does not.
* **A substance is attributed to what it is ON, never to the body it came
  FROM.** This is the standing form of the cause-blindness
  `substance_event_clause` already keeps for the beat's own delta: matter on a
  collar says what it smells of, never whose body it left.

## 6. What was deliberately not built

**Decay.** A smell does not fade. Blood stays `wet iron` until the Director
re-describes the deposit or removes it. This is the honest v1: the substance
ledger's `amount` is free text and nothing can order "a small spill" against
"the remainder" (see `_stock_consumed_by`'s own note on the same limit), so a
decay rule would need either a clock on every record or a model call per beat
to age them. The authoring surface already carries the answer — a re-described
deposit updates its smell, which is how `drying iron, going sweet` gets into
the ledger — and the prompt now asks for exactly that. If decay is built later
it belongs on the substance record as an explicit age, not as a heuristic over
prose.

**Travel and drift.** A smell does not move with air. There is no wind model,
no upwind/downwind, no scent trail left in a room a body has walked out of.
Barriers grade reach and that is all: a smell is where its source is, at full
strength or muffled through one edge. A trail — the tracking case, which is a
genuinely good mechanic — needs a per-room decaying residue ledger and is a
larger feature than this one; it is recorded here rather than half-implemented,
and `docs/UNBUILT.md` §6.12 points at this list.

**Multi-hop reach.** Hearing has `sound_walk_level` and a hop budget that the
card's `range` extends. Scent does not walk: it is graded across ONE edge and
stops. A body two rooms away is not smelled however keen the nose, because
`sense_range_class` has no consumer on this channel. That is a real asymmetry
with hearing and it is left as one until a story wants it.

**A body smelling itself.** Argued in §3.

**Smell in the interaction micro-loop.** `deterministic_micro_perception` grades
hearing and sight per micro-round; scent is standing state and is delivered
once per beat by the stage views. A smell that changes inside a micro-round is
not a case this engine can currently produce.

## 7. Where the pieces are

| Concern | Lives in |
|---|---|
| Barrier grading | `world/spatial_barriers._SCENT_BARRIER_LEVELS`, `world/spatial_senses.scent_level` |
| Perceiver acuity | `world/spatial_senses.sense_adjusted`, `_SENSE_CHANNEL_ALIASES` |
| A body's standing smell | card `embodiment.scent`; `character_scent`/`persona_scent`/`scene.scent_of` |
| An object's smell | `schemas.SceneEntityDef.scent`, `spatial_merge._ENTITY_DEFAULT_FIELDS` |
| Deposited matter's smell | the substance record's `scent` (`world/spatial_substance.py`) |
| An authored opening signal | `sensory_events[].kind`, read by `composer._ambient_channel` |
| Source gathering + attribution | `agents/perception._scent_sources_for`, `_body_scents` |
| The percept | `agents/composer.scent_percepts`, kind `scent`, channel `smell` |
| Rendering | `composer._render_scent`, `language_adapters/japanese.JapaneseRenderer._scent`, `scent_*` compositor templates in both packs |
| Delivery to the narrator | `narration._sensory_channels_manifest`, via `observations_from_render` |

Tests: `tests/test_scent_ledgers.py` (the three carriers and their traps),
`tests/test_scent_percept.py` (the percept and both renderers),
`tests/test_scent_delivery.py` (grading, attribution, and both firewall
questions), `tests/test_ambient_channel_scope.py` (the prompt/reader fold).

**Undecided, and cheap to settle from the corpus once stories have smells in
them:** whether a body should receive its OWN card scent. Currently it does not
— habituation, and a standing fact true of every beat is noise in a context
window — which is right for a person's own skin and arguably wrong for blood
somebody has just been drenched in, though that case is a substance and IS
delivered. *(Moved from `docs/UNBUILT.md` §6.12 on 2026-08-19; the other four
open items in that entry were already this note's §6, so they were deleted
rather than duplicated.)*
