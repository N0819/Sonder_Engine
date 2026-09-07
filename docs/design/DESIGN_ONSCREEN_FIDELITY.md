# Onscreen fidelity: a charter body renders deeper while it is being looked at

Status: PROPOSED, 2026-09-06. Owner's framing, verbatim: *"render them
temporarily in high fidelity with increased cognition and action potential
until they are off screen again."*

## The gap, measured

Charter has become a psychology engine. The onscreen surface is still the
one built when Charter was a roster.

**Jalzenus Huxverwood**, a containment guard in chat 115
(`site_17_sector_four_cadre`), as the charter holds him:

* a name, a rank, competences, a berth, a condition;
* a full authored surface — commanding stature, athletic build, measured
  gait, bronzed, tight brown bun, mid-thirties, with marks;
* a **mind holding nine claims** about named colleagues: who he believes is
  available, their competences, their strength;
* an **experiences** log of real social events — *he asked another sentinel
  about a facilities technician, at security checkpoint four, at hour 684.*

That charter's `experiences` field is **202 KB**; its `minds` are **35 KB**.

What `agents/background.py` is handed when he walks on screen:

> a `sketch` — `role_hint`, `station_room`.

"Member of site_17_sector_four_cadre, standing in the corridor." Two hundred
kilobytes of lived history, and a role hint reaches the page.

## What this is NOT

**It is not promotion.** `charter_promote` is a one-way door: it mints
memories, creates a character, and the body never goes back. This is
reversible and mints nothing. The body remains a charter body throughout;
only the resolution at which it is rendered and reasoned changes, and it
drops back the moment nobody is looking.

**It is not `scene_life`.** That ladder (`off | ambient | full`,
`BACKGROUND_LIFE_DESIGN.md`) governs how much ambient life a scene shows and
how voicing is batched — a scene-wide quantity. This is a per-body depth,
orthogonal to it, and the two compose: how many presences speak is
scene_life's question; how deeply any one of them thinks is this one's.

**It is not a new Director specialist.** Specialists are carved by CHANNEL
ownership; a body's conduct needs positions, poses, contact and conditions —
every other hand's channels. Nothing about the conduct needs a new owner.
What was missing was never a hand competent to move a body, but a stage that
decides what the body DOES, which is `background_react`'s job description.

## The four upgrades

1. **Its own perception view, not a sketch.** Charter bodies are already laid
   onto the perception scene (`lay_charter_bodies`) and creatures already
   declare `senses`, so the view is buildable today. It acts on what it can
   sense rather than on a replayed self-description — and the firewall covers
   it as it covers everyone.

2. **Its own interior, bounded.** What it knows (`minds`, already decayed and
   provenance-kept), what it has lived (`experiences`), how it feels (`feel`,
   `strain_toll`, `condition`), who it regards how (`politics`), what it is
   committed to (`commitments`, `ties`), its `practices`. THIS BODY'S ONLY —
   the boundary is already written in the stage's own docstring, "never the
   institution's register or another body's interior"; only the content is
   missing.

3. **Declaration, not reaction.** The stage runs after `director_resolve`, so
   it can only answer a beat already decided — its docstring is written in
   reactive verbs throughout (*react, answer, reply*). A body with an
   interior should DECLARE in the same band characters do, and the Director
   should resolve what it declared. `reaction_loop` is the precedent for a
   pre-resolve stage that declares rather than appends.

4. **Per-beat cognition while visible.** The charter clock is hourly, and
   that is what makes an onscreen body inert. Measured on the descent run:
   63 turns of story is **0.2375 story hours**, over which the carbonic
   stalker's hunger moved **0.0036** — from 0.7000 to 0.6964. Nothing driven
   by that clock can change inside a scene.

## What bounds it

**Promotion's own warning applies and is the main risk**: a thick past *"does
not read as depth; it reads as haunting."* Four hundred windows of standing
the same watch are all true, all boring, and will crowd the story's own
material out of the payload.

Promotion already solved this and its selection rule is reusable without
reusing promotion itself: something is carried because it CHANGED A TRACKED
LEDGER, and the routine that changed nothing is carried only as its
aggregate. That is what bounds 202 KB into a payload, and it is the reason
not to invent a second selection rule.

## The cost model, measured

**Perception is free.** `agents/perception.py` is deterministic -- there is
no `perception` model role in `providers.ROLES` and the module imports no
model seam at all -- so composing a view for a charter body costs
computation and not a call. Every presence in scope can act on its own real
view rather than a sketch, including the ones that never speak.

**Calls are the scarce thing, and the stage has TWO paths with opposite
cost models.** The per-presence backstop is N calls, and says so:

> One independent reactive beat per gated presence. At cap == 1 this is a
> single call. For cap > 1 each extra reacts to the same beat blind to the
> others -- the accepted tradeoff vs. a single batched call is N calls for
> possibly-similar reactions.

That is why `background_config.max_reactors` defaults to 1 with a hard
ceiling of 3: the cap exists BECAUSE it does not batch. The scene-manager
path at `scene_life: ambient|full` is the batched one --
`BACKGROUND_LIFE_DESIGN.md`: *"Voicing is batched. One call per turn per
ambient scope, holding every presence in it."*

**So this upgrade targets the BATCHED path.** What scales for "depth
whenever they are on screen" is one call per ambient scope carrying several
interiors, not three calls of one interior each. The per-presence backstop
is left alone: answering a body that was directly addressed and owes a
reply is a different job, already correctly scoped.

The remaining cost is therefore PAYLOAD SIZE rather than call count -- N
views plus N interiors in one call -- which is exactly what promotion's
significance test is for, and the reason to reuse that rule rather than any
of the machinery around it.

**Cost stays gated.** Fidelity is a STATE — the body is rendered deeper while
it is on screen — but a model call is still demand-driven. The current gate
(`pick_voice_demand`) is the right mechanism and the wrong triggers: all four
of them (addressed, owed a reply, acted toward an authored mind, emerged from
a crowd) assume a thing that participates in conversation. A body with an
interior has more reasons to act than being spoken to, and a deaf predator
satisfies none of them structurally.

## The creature is the degenerate case

A carbonic stalker's interior is hunger, senses and a prey table, and it was
the instance that exposed all of this: it tracked the cast by scent across
five rooms, arrived, stood in the room with them for four beats, and turned
for its berth. Everything needed to move it was already owned by an existing
hand; nothing had told any hand there was anything to move
(`docs/UNBUILT.md` §§1.149, 1.150).

## Open, and deliberately not decided here

* Whether the fidelity state is explicit (a flag on the body while onscreen)
  or purely derived from co-presence each beat.
* Whether declaration replaces the reactive path or runs beside it during a
  transition.
* Where the plan move lands exactly — `agents/runtime.py` is flagged in
  CLAUDE.md as an orchestration seam affecting reruns, variants, streaming
  and commits, and this change touches four registries, not one.
