# 11 — Extra body parts as structured data

**Status: implemented** (see "What landed" at the end for the exact seams).

## The ask

An option in the attire/"underneath" system to tack on and define extra body
parts — tails, wings, horns, extra arms, tentacles — declaring **where they
emerge from** through deterministic menus (behind / in front / above / below)
rather than free prose.

## Why prose is not enough (measured)

Today an appendage lives only inside `embodiment.visible.summary` — one string
of prose. In the corpus snapshot (read-only, aggregates only):

- 9 of 45 `characters` sheets and 2 of 15 `personas` carry
  tail/wing/horn/ear words in `visible.summary`;
- 24 of 178 live attire ledger entries mention those words somewhere in
  free text (garment descriptions, `beneath` fields) — the tail keeps trying
  to get into the structured layer through whatever door is open;
- the perception prompt already has to *name tails explicitly* as a thing not
  to re-roll-call every beat (`llm/prompts.py` APPEARANCE NOVELTY paragraph).

Prose appendages cannot be gated per observer, cannot interact with clothing
coverage deterministically, and are re-invented (or forgotten) by every model
call. With the owner separately making perception a pure function of spatial
data, a part that exists only in a sentence is a part that layer cannot see.

## Where the data lives

**A part is body, so it lives on the card, in `embodiment`** — beside
`visible` (stable appearance) and `senses`/`interoception`. It is **not**
attire (`initial_outfit` / `scene.attire` stay clothing-only) and it is **not**
scene state:

```json
"embodiment": {
  "visible":     { ... },
  "extra_parts": [
    {"kind": "tail", "count": 1, "at": "waist", "aspect": "back",
     "through_clothing": true,
     "description": "long and russet-furred, expressive"}
  ],
  ...
}
```

This is the acuity/lexicon pattern: **author once, read live, never per
beat.** Consequences, each deliberate:

- **Persistence is free and complete.** Sheets already persist
  (`characters.sheet`, `personas.sheet`), already override per story
  (`chat_chars.sheet`, preserved by archives/branches/checkpoints), and card
  edits already cannot rekey in-story identity. No `core/db.py` migration, no
  `persist/chat_archive.py` change, no checkpoint or remap work. In the physical
  authority hierarchy the parts are *authored configuration*, like senses —
  not `world.scene` runtime state, not a `world_entities` projection.
- **Defaults are inert.** A sheet without `extra_parts` normalizes to `[]`,
  every renderer returns nothing, and every payload omits its key — byte
  identical to today. This was the non-negotiable requirement and it is the
  main reason the data is card-level and read-derived rather than a new scene
  ledger.
- **No new per-beat obligation.** Nothing asks the Director or mapping stage
  to maintain the parts (the measured `stations` failure mode). The Director
  *sees* them; it never writes them.
- **A story-specific tail is a per-story card edit** (`PUT
  /api/chats/{cid}/characters/{ch}/card`), which already exists and already
  survives branching. In-story *transformation* (Director grows/removes a part
  mid-beat) is deliberately out of scope — see residuals.

## The menus

Kept small, closed, and orthogonal. Defined in `story/character_schema.py`.

**Attachment region — `at`: one of `attire.REGIONS`**
(`head, torso, arms, hands, waist, groin, legs, feet`). Reusing the attire
vocabulary is the whole seam: clothing coverage, `region_visibility`, zone
logic and the region editor all already speak it, so "does the skirt cover the
tail's root" is answerable without a second anatomy. `waist` is the belt
line/base of the spine (where a tail emerges), per attire.py's own gloss.

**Aspect — which face of that region it emerges from:**

| value | physical meaning |
|---|---|
| `front` | the ventral/leading face — in front |
| `back` | the dorsal face — behind (tails, wings) |
| `top` | the upper surface — above (horns from the crown) |
| `underside` | the lower surface — below |
| `left` / `right` | one lateral side |
| `sides` | bilaterally, spread across both sides (extra arm pairs; `count` is the total) |

**Count** — integer 1..12, clamped. Count and aspect are orthogonal:
`wing, count 2, back` is one dorsal pair; `arm, count 2, sides` is one arm per
side.

**`through_clothing`** — the attire interaction, decided explicitly rather
than emergent:

- `true` (**default**): a garment covering the attachment region is worn
  *around* the part — the tail passes through the skirt, the wings through
  slits in the coat. The part stays visible while the region is covered.
  Default because it is what the fiction near-universally means, and because
  the failure mode of the other default is silently deleting the swaying-tail
  detail every time legs are clothed.
- `false`: the part is tucked *under* the clothing and is concealed exactly
  when garment coverage conceals its attachment region.

Vantage/containment/darkness concealment (the body-level verdicts of
`region_visibility`) always conceal the part either way — a tail through a
skirt is still invisible from inside a crate. A body is never concealed from
itself: the self row always carries its own parts (tucked ones annotated
`beneath clothing`), matching the self-knowledge floor.

**`kind`** is a free noun on purpose — anatomy is open-ended and every story
invents some (`world/spatial.py`'s own words). The closed menus are *where*, never
*what*. The kind doubles as the contact handle.

## Interaction with contacts, poses, scales, containment

`StateDiff.contact_ops` (`schemas.py:1746`) carries `actor_part` /
`target_part` / `target_interior` as free text, and `world/spatial.py`'s part
identity is structural, not a vocabulary: `_part_identity("tail")` →
`("tail", "")`, `_same_appendage("tail", "tail spade")` is already true (that
pair is the *measured live example* in the docstring at `spatial.py:2612`).
So a declared part is a valid contact endpoint **today, with zero schema
change**; what the declaration adds is that the Director is shown the part
exists (so it stops being invented per beat) and perception can deliver it.
`poses`, `scales` and `containment` never read the card at all — a
declaration cannot corrupt them, and the regression tests pin the contact
path end to end.

## The seams (what reads the field)

1. **`story/character_schema.py`** — vocabulary constants
   (`EXTRA_PART_ASPECTS`), `_normalize_extra_parts` (tolerant: bare strings
   become `{kind}`, invalid menu values fall to a per-kind placement guess or
   the mildest default, count clamped), wired into all four normalize paths
   (native/legacy × character/persona); accessors `character_extra_parts` /
   `persona_extra_parts`.
2. **`agents/common.py`** — `extra_part_phrase`/`extra_parts_lines`
   (deterministic rendering: `tail — emerges from the back of the waist,
   passes through clothing; <description>`), `scene_extra_parts(cast,
   persona, player_name)` building `{body: parts}` for bodies that have any,
   and `observer_body_regions(..., extra_parts=...)` delivering a gated
   `"parts"` list on each body row using the same `region_visibility`
   verdicts the region surfaces use. A body with parts but no attire entry
   still gets a row (bare hands are bare, not unmodelled).
3. **`agents/perception.py`** — `_observer_scene_payload` takes the map and
   passes it through; the opening/act/outcome stages build it once per stage
   from `ctx.cast` + persona. The body-detail fidelity floor
   (`_deliver_foreground_body_details`) reads rows by `.get("regions")` and is
   unaffected.
4. **`agents/character.py`** — the `_self` payload carries `body_parts`
   (own parts, always, tucked or not: a mind knows its own body — same
   rationale as the interoception/attire lines beside it).
5. **`agents/director.py` / `story/scene.py`** — the entitled Director sees parts
   in `cast_scene_context` (establish), `present_characters`/`player`
   (interpret), and a `scene.body_parts` map beside the compact attire lines
   (resolve). Static config renders byte-identically every beat, so it is
   prefix-cache friendly.
6. **`llm/prompts.py`** — one sentence each for perception (a `parts` list on a
   body row is authored, real, gated for this observer; never invent one
   absent from it) and resolve (part names are valid contact endpoints;
   through-clothing parts stay visible when the region is covered).
7. **UI** — `fExtraParts` in `static/js/components.js` (kind text, count
   number, region select, aspect select, through-clothing checkbox,
   description), wired into the character and persona editors in
   `static/js/editors.js`. The menus are literal `<select>`s over the closed
   vocabularies.

## What was rejected

- **Parts as new attire regions.** `attire.REGIONS` is closed and every
  renderer walks it in fixed order (`compact_line`'s cacheable shape depends
  on that). Dynamic per-body regions would ripple through every attire
  function for a case clothing mostly doesn't need — a garment *covering* a
  tail (tail sock) is deferred rather than distorting the region model.
- **Parts in `scene.attire` entries.** The ledger is the mutable clothing
  story; parts are body. CLAUDE.md keeps those domains distinct, and the
  wearing/state/regions drift history shows what a fourth cohabiting
  representation costs.
- **Parts in the scene blob (seeded like attire).** Would need commit,
  archive, checkpoint, branch and projection work, and would freeze a card
  edit out of a running story. Live card reads mean fixing the sheet fixes
  the body, which is the behaviour the psychology lessons argue for.
- **A synonym table folding part names.** Forbidden in spatial identity for
  a measured reason (`tail_spade` is a place on a tail, not `tail` blurred).
  The per-kind *placement guess* used when `at` is unauthored is an authoring
  default visible in the editor — the same philosophy as
  `attire.region_of`'s cue table — never an identity fold.

## Residuals (deferred; `docs/UNBUILT.md` §6.10 points here)

- Director-driven in-story part transformation (grow/lose a part as a beat
  outcome) — needs a scene-level override ledger with commit/archive/restore
  work; the per-story card edit covers the authored case today.
- Garments that cover a part itself (tail sock, wing binder) — needs
  part-keyed coverage, i.e. the attire model learning non-REGIONS slots.
- Generator/import prompts emitting `extra_parts` (today they write prose
  summaries; the import path tolerates but does not extract).
- `importers.character_import_warnings` for a part whose `kind` word also
  appears in `visible.summary` prose (double description). The warner is
  part-aware in the OTHER direction only: it fires when body prose names a part
  the sheet does not declare (`_prose_names_a_part` against `_PART_WORDS`, and
  only when `embodiment.extra_parts` is empty), which is the failure that costs
  a kitsune nine invisible tails. The double-describe case is the mirror and is
  cheaper to be wrong about, so it is unflagged.
