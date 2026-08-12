# 18 — Dim light is a rendering fact up close, an admission fact at range

STATUS: built with this note. Method: source read (`spatial.py`,
`agents/common.py`, `agents/composer.py`, file:line cited), the incident
beat read from the corpus read-only (chat 70), light values across live
rooms measured by the tracer (349 of 395 rooms author no light, 40 `dim`,
3 `dark`, 3 `lit`).

## The incident, and the category error

Chat 70: Elyra kneeling over Hinami, same room, two standing contacts
(hands on stomach and waist) — and `region_visibility(Elyra → Hinami)`
returned every region concealed, `vantage: ["seen only in silhouette"]`.
The surfaces were computed correctly and discarded at the sight gate: the
room is `dim`, `spatial._LIGHT_SIGHT` maps `dim -> "shapes"`, and
`visual_level_between` applies the light verdict FLAT — distance can only
ever weaken sight further (`far`/`remote` cap), and nothing anywhere
strengthens it for closeness. Two bodies in continuous contact saw each
other as outlines.

The composer's own architecture names the error: **Layer A decides
admission (the information boundary); Layer B renders, decision-free.**
`dim` was making an ADMISSION decision — conceal every region of a body
your hands are on — for what is, at that distance, a RENDERING choice.
"You see her in the low amber light" carries every fact "you see her"
carries; the light belongs in how the sentence reads, not in whether the
observer may have it.

## The ladder of kind

Three rungs, distinguished by KIND rather than degree:

1. **Dim, up close** — light is a *description modifier*. Full admission;
   Layer B already renders the fact ("The light is dim." rides the
   standing environment percept, `composer._render_standing`) and stays
   decision-free.
2. **Dim, at range** — light *silhouettes*. Admission degrades to
   `shapes`: presence, outline, movement; no face, no worn-or-bare.
   Unchanged from today.
3. **Dark** — sight *fails*, at every range. Unchanged, deliberately: the
   touch channel already delivers what closeness in darkness legitimately
   gives (`contact_sensation` is continuous, and touch-only perception is
   cause-blind by design), and `light_at` already lets a carried source
   lift darkness beside its holder. Papering over darkness with proximity
   would replace a working channel with a leak.

`lit`/`bright` need nothing: they already admit fully.

## Where the gradations come from — computed, never authored

The corpus forbids the vocabulary solution: 349 of 395 live rooms author
no light at all, and the models that do author overwhelmingly write `dim`.
A five-rung word list would be dead on arrival — `spatial.DISTANCE_TIERS`
records that exact lesson ("29 surface forms, one value any code consumed
... data everyone writes and nothing can read"). So the rungs come from
**light × proximity**, both of which the engine computes:

- the light on the TARGET, per body (`light_at` — the torch prior art:
  lit beside its holder, a shape across the room);
- closeness, from measurements the engine already keeps.

## The channel discipline — what may strengthen sight

This change LOOSENS a gate in an engine where nearly every guard
subtracts, so the strengthening evidence is enumerated and closed. Sight
at `shapes` (dim) is lifted to `full` only when the pair is co-located
AND one of these POSITIVE measurements holds:

- **a standing contact between the two** (`scene.contacts`, either
  direction, `same_subject`-matched): hands on a body are the strongest
  closeness fact the engine records;
- **`proximity_rel == "within_reach"`**: same anchor or a mutual `near`
  station link — station-measured by construction.

Explicitly NOT evidence:

- **`proximity_rel == "near"`** — the documented trap: `near` is returned
  both as a measurement and as the no-station-data fallback, and the
  fallback dominates (6.7% of live bodies carry an anchored station).
  Strengthening on a default would un-dim every ordinary dim room. The
  fallback must never masquerade as a measurement.
- **cross-room sight** — an opening's view cone and distance caps stand;
  closeness is a same-room fact.
- **`dark`** — rung 3 above. A body across a dark room, or beside you in
  one, is a shape or nothing; touch speaks for itself.

The firewall justification is the firewall's own rule: a mind may know
anything it has a CHANNEL to. An observer with both hands on a body at
arm's reach in low light has one — the admission was wrong, not the
principle. The lift is bounded to exactly the pairs whose channel the
engine can prove.

## Where the change lives

`spatial.visual_level_between` — the one place body-to-body sight is
composed. `agents/common.region_visibility`'s own contract ("attribution
only ... never re-derived here where a second copy of that policy would
drift") is respected by changing nothing there; it, the composer's
presence/pose/appearance admission, `observer_body_regions`, narration's
visibility checks and the delivery gates all inherit the corrected answer
through the seam they already call.

## Rejected

- **A richer authored light vocabulary** ("gloom", "candlelit", five
  rungs of dimness): the corpus authors two values; the DISTANCE_TIERS
  lesson. Degree lives in prose (Layer B), not in the enum.
- **Strengthening at `near`**: the fallback trap above.
- **Strengthening in the dark**: touch already delivers; sight in
  darkness at contact would be a new channel invented, not an admission
  corrected.
- **Fixing it in `region_visibility`**: a second copy of the sight policy,
  the drift the function's comment exists to prevent.
- **A `proximity` parameter on `_LIGHT_SIGHT`'s map**: the map answers
  "what does this light carry" in the abstract; the composition belongs in
  `visual_level_between`, which already owns every other body-pair term
  (containment, crossing grace, view cones, distance caps).

## Also fixed while tracing (same beat, same seam)

1. **The truncated stranger label.** "The towering hooded stranger
   with smooth" — `_unknown_actor_label`'s 5-word cap cut a prepositional
   phrase mid-flight, one preposition over from the linking-participle
   truncation Design.md already records. The rule generalizes: when the
   cap actually truncated, a trailing dangling-word phrase (preposition +
   at most one following word) is trimmed back to the content head, so a
   cap-cut label ends on a whole phrase.
2. **The tripwire's cause, explained and closed.** `COMPOSER TRIPWIRE --
   unearned identity ['Elyra Voss'] reached the composed view of Hinami`
   fired every outcome beat because `spatial.contact_sensation` renders
   the OTHER party of a standing contact by canonical name with no
   identity floor — engine-written prose naming a body the observer does
   not recognize (Hinami's `known` ledger legitimately lacks Elyra: the
   name was never spoken in her hearing). The scrub caught it every time
   — the firewall held — but AGENTS.md's rule is that every payload
   handing a mind prose somebody else wrote needs the identity floor at
   the source. `contact_sensation` now takes `label_for`, and the
   composer path (the production path) names the partner through the
   observer's own display map, falling to "someone" rather than to the
   canonical name when the map cannot place a spelling. The legacy
   model-path payload site keeps canonical names deliberately — that
   payload feeds a model whose OUTPUT passes the identity scrub, the
   structural boundary on that path — and `_deliver_standing_sensations`
   currently has no callers at all (the composer builds contact percepts
   directly). The tripwire stays, as the backstop it was built to be.

## How we would know in the fiction that it is right

The incident beat, recomputed: Elyra's view of Hinami carries the torso
and waist surfaces ("Soft, tanned skin across the chest and stomach...")
with the dim light rendered as prose — while the same beat's view of a
body across the same dim room is still a silhouette, a body in a dark
room is still nothing, and Hinami's view names "the towering hooded
stranger" whole, with no tripwire note in `_engine_notes`. All four are
pinned as tests; the first and last are the player-visible facts Nathan
reported.
