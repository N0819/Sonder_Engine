# 17 — Displacement: what a worn garment no longer covers

STATUS: built with this note. Method: source read of `story/attire.py`/`persist/commit.py`
(file:line cited), corpus measured read-only against `engine.db` (63 chats,
387 stored attire diffs across all resolves, 336 live worn-garment records,
the chat 68/69/70 incident beats read directly). The enumeration was designed
against the corpus first and the imagination second, per the brief.

## The defect, and what it actually is

Live, chat 70: a travel jacket "pushed back off shoulders, bunched at
forearms over raised arms" — in the **condition** string. The ledger held
`state: "worn"`, `covers: torso, arms, waist`, and coverage is computed from
`state` + `covers` only, so the engine kept torso/arms/waist covered while
the narration wrote her out of the jacket. `advance()`'s clamp never fired
because nothing proposed a state change at all.

The ledger has two axes and the fiction has three:

- `state` — the ladder, PROGRESS TOWARD REMOVAL
  (`worn → loosened → open → removed`, `attire.GARMENT_STATES`);
- `condition` — free prose, WHAT HAS HAPPENED TO THE GARMENT'S FABRIC
  (wine, tears, blood), travelling with the garment;
- **displacement** — WHAT THE WORN GARMENT CURRENTLY COVERS. A jacket off
  the shoulders is fully "worn" on the ladder and undamaged in the fabric
  sense, but its coverage has changed — and coverage is exactly the fact
  perception and narration act on.

## What the corpus says (measured, all eras)

- Models put displacement in `conditions` because it is the only field that
  accepts a sentence: of 38 stored condition/state-dict notes, **14 (37%)
  carry displacement language**; 29 of 336 live worn records do. One stored
  condition states coverage outright in prose: *"parted fully open, no longer
  covering torso, waist, groin or legs"*.
- Chat 68 t7 is the field inviting the collapse: the model wrote a rung word,
  a displacement, and a wornness assertion into ONE condition string —
  *"hauled upward…, hem dragged to midriff, fabric bunched under arms —
  **loosened, still worn**"*. Three axes through the one field that takes a
  sentence.
- **A structured displacement channel already exists and models already
  reach for it.** `state_diff.attire.<body>.coverage`
  (`{garment: {region: [zones still covered]}}`) is prompt-taught
  (`llm/prompts.py` PARTIAL TORSO COVERAGE), coerced (`attire.coerce_diff_shape`),
  and committed (`commit.py apply_attire_diff` →
  `attire.apply_coverage_changes`) — but its vocabulary stops at
  `REGION_ZONES = {"torso": ("chest","midriff")}`. 8 coverage emissions exist
  in the corpus; **4 name regions outside torso and are silently dropped
  today** — including `{"sheer silk robe": {"torso": [], "groin": []}}`, a
  model expressing region-grain displacement in exactly the shape this note
  standardizes, discarded by the validator.
- Chat 68/69 t8 ("Elyra pulls Hinami's tank top off in one motion", which
  should remove in one beat, undamaged): the diff said `remove: ["tank
  top"]`; `resolve_garment("tank top", …)` resolves to "fitted tank top"
  correctly (hypothesis "partial-name removal may not resolve" — **refuted**,
  tested against the pure function). What the stored record plus the pure
  functions establish: `decisive_intent("she pulls the tank top off") ==
  False` — `_DECISIVE` matches "pulls off"/"pulls it off" but NOT a garment
  noun between verb and "off", the commonest English removal shape — so
  unless some other voice in the beat happened to carry a fixed decisive
  phrase, the one-rung clamp held that removal at `loosened`, the fiction
  moved on believing it off, and nothing told the Director the ladder had
  held it. (The live chat 68/69 scene blobs are NOT usable as evidence of
  where the ledger actually landed — the host hand-edited the ledger after
  the incident, and stored `steps`/`variants` rows, which no ledger edit
  touches, are the only behavioural record used here.)

So there are FOUR defects wearing one symptom, and the design must close all
of them: (1) region-grain displacement is inexpressible, (2) the decisive
vocabulary misses the commonest removal phrasing, (3) a clamped removal is
silent, so the ledger and the fiction diverge with no recovery loop, and
(4) the prompt's attire passage never names the three axes, so the model
routes everything through `conditions`.

## The design

### 1. Coverage generalizes to region grain — the zone hypothesis, amended

Displacement lives in the EXISTING `covered_zones` / `coverage` machinery,
generalized: **every region a garment covers is coverable-or-not; the torso
keeps its finer zones**. Formally, `zones_of(region)` =
`REGION_ZONES.get(region, (region,))` — an unzoned region is its own single
zone. `{jacket: {torso: [], waist: []}}` is a jacket pushed off the shoulders
with the arms still in the sleeves; `{trousers: {legs: [], groin: []}}` is
trousers around the ankles — still worn, covering essentially nothing, NOT
removed; supplying the full zone list clears the override (pulled back up).

Why not the alternatives:

- **A new rung** ("displaced" in `GARMENT_STATES`): rejected. The ladder is
  one-dimensional progress toward removal; displacement is orthogonal (a
  displaced garment can be `worn` or `loosened`) and a rung cannot say WHICH
  regions. Inserting a rung also renumbers every stored state — the
  `_SOUND_LADDER` lesson (AGENTS.md): inserting a rung changes what its
  neighbours shift onto.
- **A new field**: rejected on the corpus's own evidence. The brief's hardest
  constraint is that a correct-but-unreachable field loses to a wrong-but-
  obvious one — and `coverage` is already taught, already emitted 8 times,
  already reached for at region grain 4 times. Generalizing the field the
  model already writes beats introducing a third spelling of coverage.
- **Zones for every region** (extending `REGION_ZONES` everywhere): rejected;
  `story/attire.py` says at the definition why zones are "deliberately not a second
  anatomy". Region grain suffices for every enumerated case; only the torso
  has measured play needing finer grain.
- **Making condition prose executable** (deriving coverage from "pushed off
  the shoulders"): rejected — the module's own line ("without making a
  condition string such as 'hem rucked up' executable state") and the repo's
  standing rule that prose matching is never a boundary. Prose gets a
  DETECTOR, not an interpreter (§4).

### 2. Displacement is instant and reversible; the ladder is untouched

No step rule for displacement, deliberately (the owner's steer, confirmed
by the physics of every enumerated case): displacement is one gesture — a
skirt shoved up, a jacket shrugged half-off — with no intermediate state
worth a beat; and it is cheap to undo, which removal is not. The ladder's
asymmetric clamp exists because undressing is not cheap to undo. Making a
shove take three beats would be instant-undressing inverted: an engine
insisting on a middle the fiction does not have.

The two axes compose:

- **Displacement never moves the ladder.** A garment displaced off every
  region it covers is still `worn` (trousers at ankles) unless the diff also
  proposes a state move.
- **Removal from fully-displaced is one rung.** The clamp measures the gap
  from `max(rung(state), OPEN if the garment already covers nothing)` — a
  garment whose middle has already been played out on the coverage axis does
  not owe the ladder two more beats to leave the body. Partially displaced
  garments get no discount.
- **`removed` clears the overrides.** A garment off the body covers nothing
  and its displacement record is meaningless; clearing prevents a stale
  override resurfacing if the garment is ever re-worn (the chat 68/69
  hypothesis "what clears it" — removal clears, re-dressing starts fresh, a
  later coverage op replaces).
- **`decisive` continues to mean what it means** — intent lifts the ladder;
  displacement needs no lifting because it has no clamp.

### 3. The removal/displacement boundary — the steal, both directions

The new axis must not let "she yanks her shirt off" land as a shove
(garment off in the fiction, merely displaced in the ledger — the original
defect with the fields swapped), and the fix for that must not let "she
yanks her skirt up" land as a removal. One direction classifier serves both:

- **Vocabulary** (`attire._DECISIVE_GAP_OFF`): the decisive set now matches
  `pull/yank/tug/drag/haul/slip/take/lift/peel … <up to four words> … off`,
  EXCEPT when "off" is followed by a displacement anchor — a body place a
  garment is pushed off while staying on the body (`shoulders, shoulder,
  hips, waist, knees, thighs, ankles, arms, forearms, wrists, elbows`).
  "She pulls the tank top off" is now decisive; "the robe slips off her
  shoulder" is not. This is the measured chat-68 gap closed at its root.
- **The steal guard** (commit-side, deterministic): when a beat's `coverage`
  empties EVERY region a garment covers AND the beat's voices contain a
  removal-directed decisive phrase for that garment, the coverage claim is
  escalated to the removal it plainly was — proposed through the normal
  remove path with `decisive` standing, so it reaches `removed` and mints
  the floor object. Reported via `tell_director`.
- **Deliberately asymmetric default:** an ambiguous or displacement-directed
  phrase HONOURS the displacement. Wrongly keeping a garment on the body is
  recoverable next beat (and the §4 loop reports it); wrongly removing one
  destroys ledger state and mints an object. Escalate only on the clear
  signal.
- The three-axes-one-gesture stress case ("rips her shirt open"): `rips` is
  decisive vocabulary, `open` is a rung, the tear is a condition, and any
  coverage change rides `coverage` — all four can be written in one beat and
  nothing fights: the rung move is lifted by decisive, the condition
  persists on the garment, the coverage override says what the open shirt
  actually shows.

### 4. The deterministic floor: detectors and the recovery loop

Prompt-only contracts are what failed, so the floor is code; but prose must
not become executable, so the floor DETECTS and FEEDS BACK rather than
interpreting (the `leak_scan`/`tell_director` pairing, and the channel
`engine_notices` already delivers to the next resolve payload):

- **Displacement written only as prose**: a condition applied this beat that
  carries displacement language (`attire.displacement_language`, cues mined
  from the corpus) for a garment whose `coverage` this beat did not touch →
  warning + `tell_director` telling the resolve, next beat, exactly what to
  write (`attire.<body>.coverage = {<garment>: {<region>: []}}`). The chat-70
  jacket beat fires this.
- **Rung words inside a condition**: `"loosened"`/`"open"`/`"removed"` inside
  condition prose moves nothing (chat 68 t7) → warning + feedback naming the
  real channels. Extends the existing state/conditions collision sanitizer
  (`coerce_diff_shape`), which already re-routes a garment-keyed `state`
  dict; this catches the same confusion INSIDE the text.
- **A held removal is said out loud**: when the ladder clamps a proposed
  removal (`attire.removals_held`), the Director is told the garment is
  still at `loosened`/`open` and that the fiction, if it believes otherwise,
  must say so again (or decisively). This is the missing recovery loop that
  let chat 68 strand a tank top at `loosened` for thirty beats: the clamp
  stays, but it stops being silent.
- **The invert guard**: a coverage list that is non-empty but contains no
  recognizable zone (measured: `{"head": ["hair"]}`) is a garment asserted to
  still cover something we cannot read — it is IGNORED with a note, never
  read as "covers nothing". Only an explicit empty list means displaced-off.
  (The weather-`_SYNONYMS` rule: a term the vocabulary cannot read must keep
  what was there, because every default here is the mildest reading.)

### 5. The prompt names the three axes

The `state_diff.attire` passage is rewritten so each axis is nameable and
routed: the LADDER (how far toward off — `remove`/decisive), DISPLACEMENT
(what a still-worn garment covers — `coverage`, any region, instant,
reversible, cleared by writing the full list), and CONDITION (what happened
to the fabric — persists, travels). With the explicit rule that coverage
facts must never live only in a condition string, and region-grain examples
(jacket off the shoulders, skirt hiked, trousers at ankles) beside the
existing torso-zone one.

## The enumerated space, answered

| case | representation |
|---|---|
| skirt hiked to the waist | `{skirt: {groin: []}}` (legs too if fully gathered); reversal = write the full lists back |
| trousers around the ankles | `{trousers: {legs: [], groin: []}}` — worn, covering nothing, not removed; removal from here is one rung |
| jacket off shoulders, bunched at forearms | `{jacket: {torso: [], waist: []}}` — arms stay covered |
| sleeve pushed up / collar opened | below region grain: condition prose (presentation), or `{torso:["midriff"]}` for an opened collar exposing the chest |
| shirt untucked | condition prose; no coverage change until something is exposed |
| one shoulder down, the other up | not representable structurally (no left/right axis anywhere in REGIONS); condition carries the asymmetry, coverage stays conservative (covered until fully off the region). Deliberate coarseness, recorded in UNBUILT |
| robe held closed vs fallen open | the ladder's `open` rung is the fastening; what an open robe SHOWS is the coverage override — the two axes compose instead of overloading `open` |
| authored garment whose identity is displacement ("parts at the front…") | authored `covered_zones` on the card/regions entry — the same override, authored rather than played; survives normalize/rederive. Its *sheerness* is a transparency axis that does not exist — recorded in UNBUILT, not smuggled into coverage |
| displaced then removed | one rung (fully-displaced counts as `open` for the clamp); overrides cleared on `removed` |
| removed decisively while displaced | decisive already lifts the clamp; nothing new |
| someone else displaces/removes it | actor-agnostic diffs; `decisive_targets` already attributes actor vs target per body |
| displacement that reverses | write the full zone list; the override is popped, coverage returns — free both ways |

## Compatibility

No schema change: `covered_zones` is an existing per-garment dict inside
`scene.attire` regions; generalization widens accepted VALUES. Old blobs
(torso-only overrides, or none) read identically; archives, checkpoints,
branches and traces carry the dict opaquely; `dedupe_regions` and
`rederive_entry` stay idempotent. No migration. The thousands of existing
condition strings that encode state are deliberately NOT retro-executed
(prose is not state); they heal through play — the next beat that touches
the garment triggers the detectors — and through the attire editor, which
remains the authoring surface.

## The hand edit is a first-class path

The severity signal for this whole task is that the host went into the
ledger and fixed the state by hand — and `rederive_entry` exists precisely
because the editor once stored whatever the browser sent, forking the
wardrobe. Displacement therefore had to be hand-editable and hand-edit-proof
from day one:

- it SURVIVES an edit: `app.attire_put` re-derives every entry, and
  `normalize_regions`/`advance`/`dedupe_regions` all carry `covered_zones`
  through (with `_sync_spanning_garments` now keeping every copy of a
  spanning garment agreeing about it);
- it is EDITABLE: the region editor's coverage picker
  (`static/js/components.js fCoveragePicker`) now offers the coverage
  toggle for every covered region — an unzoned region is one "still
  covering" checkbox whose unchecked state writes `{region: []}` — rather
  than only the torso zones, so the correction Nathan made by hand is
  expressible in the UI instead of requiring raw-ledger surgery.

## How we know it is right

- The three incident beats replayed as tests: chat 70's jacket (condition-
  only displacement → detector fires, and the same beat expressed as
  `coverage` uncovers torso/waist while arms hold), chat 68 t7 (rung word in
  condition → detector), chat 68 t8 ("pulls the tank top off" → decisive →
  removed in one beat, undamaged, object minted).
- Coverage/exposure invariants: `exposed_regions` lists a fully-displaced
  region while `wearing` still lists the garment; perception's
  `perceptible_region_surfaces` shows skin plus the displaced garment;
  `describe`/`compact_line` render the fact for the Director; a reroll or
  checkpoint restore reproduces it (pure functions, idempotent re-derive).
- The steal is tested in both directions: yank-off escalates, skirt-hike
  does not.

## The second incident, and the clamp inverted

The axis above did not close the case. A reroll of the same chat-70 beat,
taken with this note's work loaded, resolved a clean `remove: ["lightweight
travel jacket"]` — and the ledger came out `loosened` on every region, jacket
still in `wearing`, while the narration had it off. `advance()` clamped the
removal one rung because the beat did not read as decisive, and the probe
table says why:

    False  shrugs the jacket off        <- the natural phrasing for a jacket
    False  the jacket comes off
    False  pushes the jacket off her shoulders   <- correct, displacement
    True   peels the jacket off
    True   she takes the jacket off

That is the second time a wrong ledger's root cause was the completion
vocabulary missing one more way English says a garment came off — first
"pulls the tank top off", now "shrugs the jacket off", one word over from the
gap just patched. Two incidents in the same class is evidence about the
approach: enumerating completions is unwinnable.

**So the clamp is inverted.** The Director owns objective causality; a
resolved `remove` IS the resolution, and the failure mode the clamp was built
against — instant undress — was always a model emitting `remove` while its
own prose narrated an in-progress act. The test now asks exactly that
question: `attire._PROCESS` recognizes the ways prose marks an act as STILL
IN PROGRESS (inchoatives — begins/starts/sets about; conatives — works AT,
tugs AT, fumbles, struggles; explicit partiality — halfway, inch by inch,
one button at a time), which is a smaller, more stable, more closed set than
every way to say a garment came off. `process_targets` attributes it per
body through the same attribution ladder as `decisive_targets` (now shared:
`_attributed_targets`, with a possessive-genitive tier added — "Hinami's
tank top" says whose even when two names share the sentence). The clamp
then fires ONLY when the beat reads as in-progress:

- resolved removal, no process reading → **lands** (the inverted default;
  an unrecognised phrasing now merely lets a removal land that the Director
  asserted anyway — the safe direction);
- resolved removal, process reading → held one rung, and SAID (the held-
  removal feedback from §4, reworded to name the in-progress reading);
- process reading + decisive act in the same beat ("stops fumbling and
  tears it off") → decisive wins — inside one sentence, a completion shape
  cancels the process reading before it ever reaches the clamp;
- intermediate jumps (`worn -> open`) still clamp to one rung: staged
  states are still the contract, stated in the prompt and held here.

The completion vocabulary survives where it belongs — `decisive` lifting a
process reading, and the steal guard's direction test — and got the shrug/
work/ease/slide verbs added while I was there; but no wordlist is on the
removal path's critical line anymore, which is the structural fix.

**The deeper point, answered: the ladder assumes fasteners.** `worn ->
loosened -> open` is a shirt or a corset; an open-front jacket has nothing
to loosen, so for it the middle rungs were fictions the engine invented and
then insisted on. The inversion dissolves this rather than modelling it: the
engine no longer *forces* a middle onto any garment — it only holds one when
the fiction itself is mid-act — and the TRUE middle of a fastenerless
garment is displacement, which the coverage axis now expresses ("shrugged
half off" = `{torso: [], waist: []}`, arms still in the sleeves). Per-garment
fastening metadata was considered and rejected: an authored burden on every
card, a cue-inference guess wrong exactly where it matters, and — after the
inversion — no remaining consumer, because nothing needs to know whether a
middle exists once the engine stops inventing middles.

## The third incident: the trigger had no subject

The inversion held — and the ledger held a garment at `loosened` anyway, a
third time. Chat 70 turn 9: `remove: ["fitted tank top"]` resolved, the
player's own input saying it came off over her head, the narrator throwing it
off the platform. Ledger: `loosened`.

This one is not a missing word, which is why it matters. The clamp fired
correctly on process language that was really there:

    Both crimson palms press flat against Hinami's bare skin just below the
    collarbones — warm, deliberate, fingers spreading wide — and BEGIN to
    drag slowly downward.

A sentence about hands. It names no garment, so `_attributed_targets` walked
its ladder past every garment tier and landed on the last resort — "exactly
one body is named in this sentence" — and marked Hinami as mid-undressing.
The clamp is per-body, so that held *every* removal proposed on her.

**The asymmetry the shared ladder concealed.** `decisive_targets` and
`process_targets` were unified onto one attribution implementation so the two
readings of a beat could not drift, and that was right — but the two
predicates are not equally licensed to use the ladder's non-garment tiers.
`_DECISIVE` is *intrinsically* about clothing: "Corin strips her clothes off
in one motion" names no garment the wardrobe knows, and falling to the named
body is the only way to read it. `_PROCESS` is not about anything.
`begins`, `starts`, `works at`, `tries to`, `halfway` are generic English
predicates over *any* act. `_PROCESS.search()` answers "is something in
progress"; it never answered "is the something an undressing", and the second
half was simply never asked.

**The fix is the missing half, not a wider ladder.** A process sentence must
now be about clothing before its attribution counts: a garment the body is
actually wearing (matched whole, exactly as the ladder's tier 1 matches it)
or a generic clothing word. Head nouns are deliberately *not* used for the
wardrobe half — `_garment_keys` reads the last word, and the live wardrobe
holds "sheer obsidian silk robe that parts with every movement", whose head
noun is "movement".

**Why enumerating here is allowed when enumerating completions was not.** The
second incident's lesson was that a wordlist must not sit on the critical
path of a removal. This one does not: it is a *gate on the clamp*, so a
garment word missing from it means the clamp does not fire and the Director's
resolved removal lands — the same safe direction the inversion was built to
guarantee. The dangerous direction here is a false *positive*, so the
promiscuous general-English words are left out on purpose: `hook` is what
fingers do to a hem, bare `tie` is what you do to hair, and `top` carries a
lookahead because "the top of her thigh" is not a garment.

**Still per-body, and that is still too coarse.** "She begins on the sash"
holds a jacket the same beat resolved off the same body. The attribution
ladder answers in bodies, and making it answer in garments is a real
redesign; the conjunction needed to hit it (one garment in progress, another
resolved off, same body, same beat) has not been observed live. Recorded in
`docs/UNBUILT.md` rather than bundled here.

## §6 — A removed garment is an object, not a fact about a body

The fourth incident, and the one that explains why there were three. Chat 70:
the jacket was resolved off, minted as a floor object — and kept its seat in
Hinami's card, `state: "removed"`, filed under `torso`, `waist` and `arms`,
carrying `"peeled off one shoulder, one arm freed from sleeve, hanging loose
from the other shoulder"` written four beats earlier. The object lay on the
stone in a different room.

Two records of one garment, disagreeing, and every reader of the ledger was
shown the wrong one. So the Director removed the same jacket a second time at
t10 — "the loose jacket still dangling from Hinami's remaining shoulder" — and
the narrator narrated the removal a third time at t11, while the Director's
own resolved event that beat correctly said it was "already pooled on the dark
stone". Three removals of one jacket, each of them right given what it was
shown.

**The rule, stated by the person who owns the fiction:** a piece of attire is
entirely uncoupled from its wearer when removed and preserves no relation. It
is just an object in the world. `removed` must mean it genuinely is not part
of their active card any more. They can return and put it back on, of course,
but that is another set of actions — and the region it vacated can be filled
by any attire, makeshift or otherwise.

**What the code already half-knew.** `advance()` cleared the *structured*
displacement record on removal and said why in a comment — "a garment off the
body covers nothing anywhere, and a stale override must not resurface
half-displaced". The prose condition saying the identical thing was carried
forward unconditionally, and the garment itself kept its seat. One fact,
three representations, one of them tidied.

**The shape of the fix.**

1. `advance()` drops a condition that reads as displacement when the state is
   `removed` — and only then. `"wine-stained down the front"` is true of the
   cloth and survives anything; `"hanging open"` was only ever true of a body
   wearing it. `worn_conditions_dropped` reports it, on the clamp's own
   principle: the drop is right and the silence would be the defect.
2. `release_removed_garments` prunes removed garments out of the wearer's
   regions entirely, called by the commit seam AFTER `_mint_shed_garments` —
   never before, because `newly_removed` reads the transition out of those
   very entries and an earlier prune would mean nothing ever reached the floor.

**The one relation that had to move rather than vanish.** `beneath` surfaces
only where something came off, and that was read off the removed garment still
sitting in the region. With the corpse gone, the signal had to become a fact
about the *region* — `uncovered: true`, set by the release, preserved through
`normalize_regions`. A region that was never covered has no flag and still
says `bare` and nothing more. Both readers (`describe` and
`perceptible_region_surfaces`) accept either that flag or a legacy `removed`
garment, because the editor, restored archives and every chat written before
this change all hold the old shape.

**Not a defect, checked:** `worn_by` on a shed entity names its FORMER wearer
and is load-bearing for `recover_shed_entity_changes`, which promotes an
explicitly-shed entity back into the attire diff when a model creates the
object but forgets the removal. `shed: true` disambiguates it.

## Left open (docs/UNBUILT.md)

- Left/right asymmetry (one shoulder down) — no lateral axis in REGIONS.
- Transparency ("sheer") — a garment that covers without concealing is a
  separate perception axis; today sheerness lives in prose only.
- Retro-repair of stale displacement prose in existing corpora — editor and
  play-through healing only, by design.
- The process clamp is scoped per BODY, not per garment: one garment being
  worked at holds every removal resolved on that body in the same beat.
