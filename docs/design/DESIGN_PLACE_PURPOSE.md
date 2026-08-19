# Design: what a place is FOR

**Status: v1 built** (`world/place_purpose.py`; commit writers wired beside
`record_spatial_experience` and after `apply_mind_model_updates` in
`persist/commit.py`; payload wiring in `agents/character.py`
(`perception.here_affords`, `memory.recalled_places`); PLACES AND WHAT THEY
ARE FOR prompt block; tests in `tests/test_place_purpose.py`). Build
decisions beyond this doc, each argued in `world/place_purpose.py`'s module
docstring:

- **`assumed` is derived at read time from the character's own place-graph
  node names and never stored** — a departure from the JSON example below,
  in service of the firewall rule beside it: an unperceived name cannot
  reach the lexicon because a graph node name exists only by walking,
  seeing, or (future basis) being told. Deriving also removes the need for
  displacement machinery — stored `witnessed`/`told` entries shadow the
  assumption by construction — and lets a lexicon fix reach every character
  retroactively.
- The type-inference line, drawn: trigger tokens only from own node NAMES
  (never prose); output is PURPOSE keys only, never structure or contents;
  membership requires story-free genericity; rendered as expectation.
- Witnessed v1 = own-vitals rise across consecutive commits settled in the
  same room (food/rest), plus `comfort.rest_affording` (rest — the seam
  comfort.py documented, taken deliberately; comfort itself still never
  pulls). The own-memory-row heuristic (signal 2) is deferred as the doc
  allows.
- `told` mirrors reconciled `stated_fact` beliefs onto EXISTING own nodes
  only; hearsay about a nodeless place stays in mind_models (no rid, no
  route — the same gate `_destination_from_goals` enforces). `sureness` is
  re-asked from `belief_credence` on every commit touch and a dead belief's
  entry is dropped (the mandatory drift rule below).
- Recall triggers at the 0.4 tier ("very hungry"/"tiring badly"), routes
  only over walked doorways (the en_route taken-edge firewall), caps at two
  entries, narrows to one then none under `cognitive_absorption`
  (0.5/0.85), and is suppressed when the standing room itself answers the
  need.
- Not built, plainly: witnessed drink/water/warmth (no thirst or cold vital
  → no deterministic signal), told-basis node minting, negative entries,
  and the "repair"/"social" affordances (no consumer; dead weight becomes a
  to-do list, risk 4).
- Persistence rides `chat_chars.state` (`affords` on graph nodes +
  `last_vitals`), the place-graph precedent — no schema/remap/archive
  change (decision recorded at `record_spatial_experience`).

A character should know that a tavern is where you get food, drink and
conversation; that a bedroom is where you rest; that a bed or a couch anywhere
affords lying down. Today the engine has no representation of purpose at all —
rooms carry `name`/`desc`/`notes`/`anchors`/`size` (`spatial.py:1047`) and
entities carry `kind`/`description`/`state` (`_ENTITY_DEFAULT_FIELDS`,
`spatial.py:2734`), and nothing anywhere says what a place is good for.

The consequence is that a hungry character has no way to turn hunger into a
destination. `world/survival.py` already gives them the feeling — "very hungry" at
`nourishment <= 0.4` (`survival.py:98-107`), delivered as `self.body_state`
(`agents/character.py:711`) — and then the feeling has nowhere to go.

---

## 1. Two different problems that look like one

**What the room I am standing in affords needs no memory.** It is perception:
a bed is visible, a hearth is warm, a table is laid. Derive it live from
co-present entities and room anchors and put it in the payload as
`perception.here_affords: ["rest (the bed)", "warmth (the hearth)"]`. Cheap,
always on, and only a structured echo of what the view prose already shows.

**What a place I am NOT in affords is memory**, and that is the part needing a
home. It goes on the place-graph node:

```json
"affords": {
  "food":  {"basis": "witnessed", "last": 71},
  "rest":  {"basis": "assumed",   "note": "it is an inn"},
  "drink": {"basis": "told",      "sureness": 0.7}
}
```

### Why the graph node, and not the three obvious alternatives

- **Not room metadata.** That is objective scene state. Reading it would be
  oracle knowledge: the character would know what a building is for without
  ever having seen, entered or heard of it.
- **Not a memory category.** Purpose would then be answered by retrieval
  ranking every time, and "where can I eat" is exactly the kind of question the
  engine's core principle says should be answered deterministically — where the
  engine can know reliably, it should say the answer rather than make the model
  re-derive it.
- **Not a new `mind_models` kind.** Hypotheses within a group explain each other
  away (`mind/theory_of_mind.py`), which is right for rival beliefs about a person
  and wrong here: "the Boar serves food" and "the Boar has a back door" are not
  competitors. This is the same reason place claims had to be rekeyed off the
  umbrella entity in the first place (`rekey_place_claims`).

Purpose is a **fact ledger about a place the character knows**, and the place
graph is precisely that ledger.

---

## 2. Three bases, three provenances

Every entry carries how the mind came to hold it. The basis is not decoration —
it decides display strength, override order, and what a contradiction does.

### `assumed` — cultural prior

A small deterministic lexicon in Python: tokens in a name or description the
character has **legitimately perceived** map to default affordances.

```
tavern, inn, alehouse   -> food, drink, social, shelter
bedroom, chamber, cot   -> rest
smithy, forge           -> repair, heat
well, pump, spring      -> water
```

The firewall answer: the trigger token is earned — they read the sign, heard the
name, saw the room — and mapping "tavern" to "food" is ordinary cultural
competence, the same license under which the character speaks the language.

**Constraints that keep this honest:**
- It is the *weakest* basis. It renders as an expectation — "you would expect
  food there" — never as knowledge.
- It is the first thing displaced by contradiction, and it must not appear at
  all once a `witnessed` or `told` entry exists for the same affordance.
- **If the lexicon is ever consulted for a name the character has not
  perceived, that is a firewall breach, not a tuning problem.**
- Keep it under ~30 generic entries. Story-specific culture ("in this city,
  bathhouses are where deals are made") belongs in lore, which already has a
  gated delivery path in `knowledge_for_character` (`memory.py:2084`) with
  `knowledge_tag` and `knowledge_range: local`. This lexicon must never grow
  into a parallel lore system.

### `witnessed` — learned by living it

Derived at commit from the character's **own** just-minted memory rows and
**own** vitals deltas. Never from the objective event row: that row is
entitled, and `recent_events` scrubbing exists precisely because it leaks
(`AGENTS.md:166`).

Two signals, in order of confidence:

1. **Own-vitals delta** — their `nourishment` or `stamina` rose while they were
   in this room. They ate here; they rested here. This is interoception about
   their own body and is unimpeachable. *Build this one first.*
2. **Own memory row** minted this beat at this `location` matching an
   affordance verb pattern. A heuristic; it can wait.

### `told` — hearsay

A `stated_fact` place claim mentioning an affordance, already rekeyed onto the
place by `rekey_place_claims`. Commit mirrors it onto the node with the claim's
capped confidence as `sureness`.

The mind-model hypothesis remains the revisable belief; the node entry is a
denormalised read-model of it. **`sureness` must be refreshed from
`belief_credence` (`theory_of_mind.py:516`) on every commit touch** — see the
drift risk below.

---

## 3. From "I am hungry" to going somewhere

Deterministic bridge, model-owned decision. The same division of labour as the
rest of the engine: stress biases the next deliberation but does not select
behaviour (`psychology_runtime.py:125`).

When a vital crosses its felt threshold — the labels at `survival.py:98-107`
already define what is worth feeling — the payload gains, under `memory`:

```json
"recalled_places": [
  {"name": "Gilded Boar", "affords": "food", "basis": "witnessed",
   "as_you_remember_it": "two rooms north, off the square"}
]
```

Nearest matching node by graph BFS, at most two entries, capped by
`cognitive_absorption` exactly as route recall is.

The engine guarantees only that the mind **remembers the option**. Whether
hunger becomes an intention, and the intention becomes movement, is the
character's. This is the same shape as the URGENT SITUATIONAL FACTS rule in the
character prompt (`prompts.py:782`): *the option must exist; the refusal may be
theirs.* A character too proud, too frightened or too task-fixated to go and eat
is in character. A character who never thinks of it is a blind spot.

No new drive machinery. When survival is off, nothing triggers.

---

## 4. Risks

**The lexicon asserting a false genre prior.** The sharp edge. A tavern that is
a front; a culture where taverns are not for eating. Mitigated by rendering
`assumed` as expectation, by displacing it on first contradiction, and by
keeping it small. Not mitigable by tuning — if it ever fires on an unperceived
name it is a firewall breach and must be treated as one.

**Witnessed-affordance derivation drifting toward the event row.** A future
"cheaper" implementation that reads `director_resolve` output per character
would leak entitled information. The design uses own-vitals and own-memory
precisely to avoid this, and any such change must be rejected in review.

**Purpose double-storage drift.** The node's `told` entry denormalises a
mind-model claim. If the belief is later explained away, a stale node entry
keeps steering navigation toward a place the character no longer believes in.
Refreshing `sureness` from `belief_credence` at each commit touch is
**mandatory**. This is the same class of bug that
`reconcile_inference_confidence` exists to prevent for memories.

**Affordance as a to-do list.** A character shown a tidy list of what a place is
for may start behaving like a questing algorithm — eat, drink, rest, repeat.
The counter is that `recalled_places` surfaces at most two entries, only on a
felt need, and never becomes a want. If playtesting shows characters
mechanically servicing needs, the fault is here and the fix is fewer entries,
not better prompting.

---

## 5. Experiment that would settle it

A town-scale fixture: 20 named rooms, 3 affordance sites (tavern, well, bed).
Measure **beats from hunger onset to reaching food**, with and without
`recalled_places`. The mechanism works if the number falls and the *route*
still reads like a person walking rather than a solver.

## `basis: "told"` has no PLACE-GRAPH writer, deliberately

*(Moved from `docs/UNBUILT.md` §6.5 on 2026-08-19. Recorded because someone
reading the node shape will otherwise assume hearsay EDGES exist.)*

The distinction matters, because the affordance ledger one layer over does
write `told`: `place_purpose` mirrors `stated_fact` hypotheses onto nodes
resolved `by_name` as `{basis: "told", sureness, about, claim}`. Testimony can
say what a place you already know is FOR; it cannot mint the place.

The approved design derived hearsay EDGES from `stated_fact` place claims, and
implementing it revealed that deriving *connectivity* from free text means
text-mining it — the non-deterministic derivation this engine refuses
everywhere else. `told` remains an accepted value on a graph node with no code
path behind it. **A future testimony writer needs a structured claim field
naming the two places and the direction, not a parser over prose.** This was
the design document being wrong, not the implementation.
