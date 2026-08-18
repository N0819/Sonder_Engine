# Audit — the `spatial.py` split

Status: working notes, per `docs/design/DESIGN_MODULE_LAYOUT.md` §"The split is
also the audit" and §"…a documentation reconciliation". Evidence, not
authority.

Produced while executing [`docs/design/SPLIT_SPATIAL.md`](../design/SPLIT_SPATIAL.md):
all 8,451 lines of `spatial.py` (199 top-level defs, 97 module-level
constants) were read in full before the first move, as the layout note
requires. **Every `file:line` below is as of the pre-split revision
(`418ab5b`, alpha 9.5).** Each finding names the extraction commit that moved
the code, so the entry stays findable after the line numbers change. Nothing
here was fixed during the split — flag, never fix.

Dead-symbol claims were verified by whole-repo grep (`-w`, all `*.py`),
counting references outside `spatial.py`; monkeypatching of `spatial` was
re-checked before executing (`setattr(spatial` / `monkeypatch.setattr("spatial`
/ `patch.object(spatial`): still zero hits, as the plan measured.

## Corrections to the split plan

The plan (`SPLIT_SPATIAL.md`) survived contact with the file almost intact.
Three boundary decisions its text does not state (its per-module line counts
imply them) plus one miscount, recorded here so the next reader does not
re-derive them:

- **`spatial_digest` belongs to geometry, not senses.** `room_layout`
  (geometry, 2860) calls it, and it depends only on `egocentric_frame` —
  leaving it with the sense graders would close a `geometry ↔ senses` cycle,
  a fifth instance of the shape the plan's §"Four cycles" pre-empts.
- **`_NEVER_STATIONED_KINDS` (3094) goes to containment**, because
  `_body_interior_holder` (containment, 3512) reads it and containment
  extracts before geometry; `derive_scene_stations` (geometry) imports it.
- **`_is_body_entity` (7347) goes to transit**, its home in the file, because
  containment (`_body_interior_holder`) needs it and transit extracts first.
  This matches the plan's ~363-line transit estimate.
- **"Six deferred function-local imports … lines 489, 1869, 1962, 5040, 6497,
  6704, 8395" lists seven lines.** Six break real cycles
  (`character_schema`, `language_runtime` ×2, `scene`, `survival` ×2); line
  6704 is `from collections import deque` — stdlib, deferred for no
  load-bearing reason. All seven stayed deferred, moved verbatim inside their
  functions (identity, senses ×2, merge ×2, prose, routing).

## Findings — flag, never fix

Format: claim · evidence (`file:line` at `418ab5b`) · the commit that moved it.

**F1. `_SCENT_BARRIERS` is a declared vocabulary its own function ignores**
(confirms plan defect 1). `spatial.py:252-263` defines it under 12 lines of
comment saying it gates scent; `scent_level` (265-319) never reads it,
restating the same rule as literal tuples at 313 and 315 — two
representations of one rule, free to drift. `tests/test_comms_channels.py:518`
asserts on the constant, which decides nothing. `AGENTS.md:64` documents it as
gating scent "the same way `_SIGHT_BARRIERS` gates sight" — true of the
latter, false of this one — and `docs/guides/ENGINEERING.md:274` lists it as a
live channel gate. Constant moved in the barriers commit; `scent_level` in the
senses commit.

**F2. Ten symbols have no caller anywhere in the repo** (confirms plan defect
2; every one re-verified at 0 external references): `comms_reach` (939),
`owned_region` (4049), `CONTACT_MANNERS` (3864), `CONTAINMENT_MODES` (3428),
`_reverse_dir` (6572), `CONTAINER_ENCLOSURES` (7344), `_SOUND_BARRIER_PHRASES`
(1885), `_SECTOR_PHRASES` (1892), `would_create_containment_cycle` (8411),
`validate_operations` (8424). All are part of the facade contract, so none
were deleted in the split. Moved in the senses, contacts, containment,
routing, transit and merge commits respectively.

**F3. `spatial.py:1884` claims a use that does not exist** (confirms plan
defect 3): "English compatibility views for tests and audits" sits above two
constants (`_SOUND_BARRIER_PHRASES`, `_SECTOR_PHRASES`) that no test or audit
reads — stale pre-language-pack literals kept as a claim rather than a check.
Senses commit.

**F4. Two functions still speak the decommissioned `world_placements` shape**
(extends plan defect 4). `would_create_containment_cycle` (8411-8422) walks
`placements[id]["container_id"]`; `validate_operations` (8424-8451) validates
a `create_entity`/`move_entity`/`destination_id` op vocabulary no current
schema emits. Both dead (F2), both from the same era, and the scene's real
containment ledger has its own cycle handling three times over
(`carrier_chain` 3456, `normalize_scene_containment` 3702-3713,
`_hiding_holders` 3589). Containment and merge commits.

**F5. `_phrase_table` re-resolves the language pack on every call and swallows
every exception** (confirms plan defect 5). 1868-1873: `except Exception:
return {}` — a pack misconfiguration degrades silently to empty phrases, and
`sound_bearing` (1913) triggers three fresh lookups per invocation. The
"empty one fails silently" failure shape, in the compositor. Senses commit.

**F6. Shadow-by-case pairs** (confirms plan defect 6):
`_sound_barrier_phrases()`/`_SOUND_BARRIER_PHRASES` and
`_sector_phrases()`/`_SECTOR_PHRASES` (1876-1893) differ only in case — the
function is live, the constant dead (F2/F3). Both pairs kept together in the
senses commit.

**F7. `_BARRIER_ALIASES` has a duplicate dict key, and the first entry is
dead.** `"one_way_mirror": "window"` at 25→80 is silently overridden by
`"one_way_mirror": "one_way_window"` at 104 — a Python dict literal keeps the
later binding. The deliberate-ambiguity comment at 110-114 argues carefully
about `observation_window` and never mentions the key that actually collides.
The live behaviour (one-way) is almost certainly the intended one; the dead
line misleads the next reader adding a spelling. Barriers commit.

**F8. `contact_phrase`'s `subject_first=False` branch is dead and would be
wrong if resurrected.** No caller in the repo passes `subject_first`
(verified: 0 references); the branch (6125-6126) renders
`"{right} is under {left} ({manner})"`, bypassing the momentary-residue and
interior-topology rendering the rest of the function exists to enforce — a
future caller would get a raw act-manner rendered as standing state, the
exact defect the surrounding code documents fixing. Prose commit.

**F9. A comment in `spatial_facts` describes an order the code does not
have.** 6481-6482: "Light before anything else: it decides whether the rest
of this list is perceivable at all" — the light facts are appended AFTER the
exit-direction and co-located-people facts (6448-6465). The adjacent block
comments (6467-6480: contact nameability, size-before-contacts) describe code
two subsections further down, with unrelated statements interleaved. Comment
drift only; behaviour is consistent. Prose commit.

**F10. The scale-change `changed`-set computation exists twice, nearly
verbatim.** `containment_broken_by_scale_change` (3777-3785) and
`contacts_broken_by_scale_change` (4717-4725) each recompute which names
crossed `_SCALE_CONTACT_BREAK`, with cosmetically different zero-guards. A
future threshold or guard change must be made twice, and the two now live in
different modules (containment, contacts) — recorded so the duplication is a
known cost of the boundary rather than a surprise.

**F11. Seven hand-rolled walks each rebuild their own neighbour map from
`scene.rooms`**: `passable_neighbors`/`passable_route_next_step`/
`passable_route_exists`/`passable_path` and `nearby_rooms` (routing),
`sound_path` (senses), `ambient_scope` (transit). All consistent, all
re-deriving the same undirected graph per call. The plan's "clean future
seam" note (`spatial_topology`) is the right home for a shared builder; not
taken here.

**F12. An authored room `size` outside the vocabulary is accepted silently
and grades as medium.** `effective_room_size` (2585-2587) returns any
non-empty authored string unvalidated; `proximity_rel` (2683) tests membership
in `("large","huge","vast")`, `_ROOM_COST` (6670) `.get(...)` defaults to 1,
`_opening_view_cap` (2222-2232) tests two literal tuples — so `size:
"enormous"` behaves as `medium` everywhere, indistinguishable from an
unauthored room. Same silent-unknown-enum shape as the pre-normalizer
`distance` field (1308-1314's own history). Geometry commit.

**F13. A mirrored threshold hardcoded on one side only.** `size_facts`
(6394) uses `ratio >= 6.7` as the inverse of `fits_in_other_hand`'s
`ratio <= 0.15` (`size_relation`, 3346); 1/0.15 = 6.67, and the two sides of
one boundary can drift independently. Containment commit.

**F14. `ambient_scope`'s docstring undersells the constant it reads.**
7666-7667 says "through open/open_door barriers"; `_AMBIENT_BARRIERS` (7641)
also passes `bars`. Transit commit (constant: barriers commit).

**F15. One unguarded room write in `apply_transit_dock_edges`.** The link
(portal) path does `rooms[a].setdefault("adjacent", []).append(...)` (7521)
after checking only `a in rooms` — the sole room write in the function not
`isinstance`-guarded; a malformed (non-dict) room record raises at merge time
instead of being skipped as everywhere else in the file. Transit commit.

**F16. Minor: `normalize_scene_containment` probes holder existence three
ways, one of them twice.** 3695-3696: `holder not in entities` is subsumed by
the case-insensitive probe, which is itself built by materialising a fresh
`{k: 1 for k in entities}` dict per record. Harmless; wasteful; the shape
suggests a missing key-set variant of `_ci_get`. Containment commit.

## What the code actually does, module by module

Written from the code, then checked against `Design.md`, `AGENTS.md`,
`docs/guides/`, and the design notes. "Docs right" entries are recorded
deliberately — they are what makes the exceptions credible.

### `spatial_identity.py`

Resolves what a name refers to: `room_of` (position lookup with case,
whitespace and — via a deferred `character_schema.fold_identity_key` import —
script folding), `_ci_get` (the tolerant dict read everything else leans on),
`_entity_named` (id/name/alias resolution), `same_subject` (the equality
floor for raw model output), `_position_of` (position through entity identity
rather than spelling), and the merge-time canonicalisation
(`canonical_subject_map` / `normalize_scene_subjects`) that folds every
subject-keyed ledger onto one spelling per being — only where the canonical
name is already live as a subject spelling, ambiguity folding nothing.

Docs checked: `Design.md` "One being has one name" row matches the code
exactly, including both narrowing rules and the eleven-test lesson its scope
carries. `AGENTS.md:67`'s "one being, one name" paragraph matches
(`normalize_scene_subjects` at merge, `same_subject` as the floor for raw
model output). Right.

### `spatial_barriers.py`

The barrier vocabulary: a 150-entry alias table, qualifier folding
(`open_shoji` is a shoji that is open), head-noun fallback, and
`unresolved_barrier_words` so an unreadable word is reported instead of
silently sealing a doorway as `wall`. `_barrier_against_its_own_name`
downgrades a *named* opening from `wall` to `closed_door` (never to open).
Owns the four class sets (`_SIGHT_BARRIERS`, `_PASSABLE_BARRIERS`,
`_AMBIENT_BARRIERS`, `_SCENT_BARRIERS` — the last dead, F1).

Docs checked: `AGENTS.md:64` is right about the four-questions doctrine,
`membrane` as the inverse of `window`, and `_SOUND_LADDER`'s
relative-step fragility — and wrong about `_SCENT_BARRIERS` (F1).
`docs/guides/ENGINEERING.md:273-276` ("Channel-by-channel barriers") and its
Diagram 5 are **stale twice over**: they name `_AMBIENT_BARRIERS` as the
*sound* gate, but sound is graded by `hear_level`'s own per-barrier branches
plus `_MATERIAL_SOUND_STEPS`/`_SOUND_LADDER` (and `_SOUND_WALK_BARRIERS` for
multi-hop propagation) — `_AMBIENT_BARRIERS` gates only `ambient_scope`'s
ambience component — and they name `_SCENT_BARRIERS` as the scent gate, which
nothing reads (F1). The doctrine the guide states is true; the constants it
cites for sound and scent are not the ones deciding.

### `spatial_transit.py`

Derived dock edges: a `parent_entity` room's exterior doorway is a *function*
of the entity's position and `state.transit`/`state.hatch`/`state.link`
(portals), recomputed idempotently at every merge — docked/open, closed,
sealed/in-transit (severed, or a `route_room` edge), arriving. `enclosure`
picks the barrier (`membrane` opaque in both states and overriding an
authored `open_door`; `transparent` → `window`; `barred` → `bars`).
`infer_body_enclosures` defaults a *body's* interior to `membrane` because
flesh is opaque whether or not a model remembered to say so;
`_is_body_entity` decides body-vs-box from `attire`/`scales` presence.
`containment_chain`/`ambient_scope` answer whose ambience can reach an
observer through the nesting.

Docs checked: `AGENTS.md:65` (containers/enclosure semantics) matches the
code precisely, including the `membrane`-overrides-authored-`open_door` rule
and `_ENTITY_DEFAULT_FIELDS` housing `enclosure`/`light_source`.
`CLAUDE.md`/`docs/guides/DATABASE.md`'s "scene blob is the single runtime
source of truth" framing is consistent with the derived-edge doctrine. Right.
(F14, F15 above.)

### `spatial_containment.py`

Two ledgers. Scale: clamped factors relative to a body's own baseline, size
tiers, `size_relation`'s capability report, deliberately not pruned by
position (someone shrunk offscreen is still shrunk). Containment: the
`contained` ledger plus the body-parented-interior-room form,
`_body_interior_holder` reading BOTH (the defect history in its docstring is
accurate), concealment via innermost-holder comparison, derived positions
(outermost carrier wins, written under the existing key spelling), and the
scale-change releases for both holds and containment.

Docs checked: `AGENTS.md:67/68/69` match the code (three enclosure
directions; carve-out scoping to bodies via `_is_body_entity`; carried
position derived, release explicit; scale not pruned by position; contacts
cancelled before the beat's own ops). `Design.md` "A body sealed inside
another body is IN it, not far from it" matches, cause by cause. Right.
(F4, F10, F13, F16.)

### `spatial_contacts.py`

The contact ledger. `_clean_contact` is the single door: refuses non-parts in
part slots (`_is_anatomical_part` — deny-list, permissive by design), derives
relation/motion from manner/detail for old records, and folds envelopment
spellings (an enveloping verb, an enclosing cavity in the actor slot, a
cavity gripping, or containment the scene already knows) onto the fixed
interior direction — actor's part is the enclosed one. Identity is
`(actor, actor_part, target, target_part)` with manner/detail excluded; an
unqualified part noun is a definite description (`_part_identity` /
`_same_appendage` / `_displaces`), so a re-described limb MOVES rather than
multiplies, with the same-beat and bare-vs-qualified carve-outs.
`apply_contact_ops` ages standing contacts on evidence beats (momentary
manners retire in one, holds in two), handles mirror re-assertion, interior
preservation against bare re-description, and the `cross` op. Region
identity (`canonical_region`/`_same_region`/`same_owned_region`) is
comparison-only and never rewrites stored text.

Docs checked: `AGENTS.md:70` matches in every particular it states (one
record; positions prune; definite-description displacement; both carve-outs;
no synonym table; `detail` excluded from identity). `Design.md` "One limb,
one place" and "An opening can express a hold" rows match. Right.

### `spatial_contact_migration.py`

Lifts contact the Director wrote into an entity's own `state` into real
contact records, three patterns: the documented `target`+`proximity` pair;
invented keys with a contact verb in the NAME; and pattern B — the verb in
the VALUE with the key naming the part. Converted keys are removed so one
contact has one record; lifted records go through `apply_contact_ops` with
ageing suppressed; `_drop_contradicted_state` retires a relational state key
the aged ledger already speaks for. The free-text `description` paragraph is
deliberately never parsed.

Docs checked: in-file doctrine only (no guide describes this subsystem by
name beyond `AGENTS.md:70`'s "anything that puts contact back into an
entity's `state` re-creates a copy nothing ages", which is exactly what this
module exists to reverse). Consistent.

### `spatial_substance.py`

Non-discrete matter: add/remove/clear ops resolved against pre-beat contact
topology (a release from an inserted part derives its interior destination;
contradictions discard the op with a report), placement vocabulary,
enclosure-beside-surface shed on write AND on read so stored rows heal,
pooling (`_same_pool` — same material, source, owned region; identity
excludes `source_part`/`amount`/`detail`), and conservation
(`_stock_consumed_by`: matter arriving somewhere left its origin region,
names never compared, whole-record retirement as the documented honest
limit). `speech_articulation_impediment` reads the standing contact ledger
for stifled/slurred speech formation. The long comment at 5713-5737
refusing a derived-ownership check is a *measured* refusal (72 hits, right
once, self-poisoning) and matches the code's absence of one.

Docs checked: no guide row describes substances in detail; the in-file
measured citations are self-consistent, and `AGENTS.md:43`'s "touch-only
sources get surface-translated event text" sits in composer, not here.
Nothing contradicted.

### `spatial_geometry.py`

Within-room position. Anchors (authored plus implicit `door:<to>`
pseudo-anchors with reciprocal bearings), the S1 read-time derivation layer —
`effective_station` (authored, else contact-derived, else crossing-derived),
`effective_facing` (authored, else focus-derived), `effective_room_size`
(authored, else name-keyword hint, else medium), `derive_scene_stations`
(contact seeds the ledger models never fill; last-resort identifier
recognition over `state.position`) — proximity tiers, sides/arcs and the
rear blind spot, poses (complete-snapshot replacement, fixture-tolerant
`relative_to`), threshold crossings (`crossing_of`), the egocentric frame and
its digest (`spatial_digest`, with `label_for` as the identity gate on
`ahead_entity`), and `room_layout`.

Docs checked: `AGENTS.md:71` and `Design.md` "Within-room position
(stations)" match (schema-declaration history, derive-from-contact,
derived-outlives-contact, plain-dict warning). `AGENTS.md:66` (crossings)
matches `crossing_of`/`THRESHOLD_CROSSING_BEATS`. Right. (F12.)

### `spatial_light.py`

The light ladder (`dark/dim/lit/bright`, absent-means-lit), room light vs
carried sources (`light_radius`: portable defaults to a pool, not the room),
`light_at` (ambient plus pool membership by proximity), `effective_light`
(spill lifts dark to dim through sight-passing edges, never further), and
the light→sight ceiling `_LIGHT_SIGHT` with `SIGHT_LEVELS` — kept here, not
in senses, because routing reads them (the plan's cycle 4).

Docs checked: `Design.md` "Dim light is a rendering fact up close" matches
(`_LIGHT_SIGHT` dim→shapes; the lift on measured intimacy lives in
`visual_level_between`, senses). Right.

### `spatial_routing.py`

Graph walks: `spatial_rel` (the room-to-room relation; observer's own edge
first, which is what makes `one_way_window` one declaration; distance
normalisation with unit parsing), passable adjacency/next-step/existence/path
(all deterministic, sorted-neighbour order), `nearby_rooms` (payload
trimming), `corridor_sightlines` (straight-line reading that coarsens with
distance), `sprint_reach` (decision-bounded running with the `known_rooms`
offer-side firewall), `_onward_exits` (full-sight-only doorway counting with
bearings), and `visible_adjacent_rooms` (forward and reverse edges,
light-gated, carried interiors withheld).

Docs checked: `Design.md:595-600` and `docs/design/DESIGN_RUNNING.md` match
the code (decision-bounded, `full_reach` renamed from `winded`, path
reconstruction, offer firewall). `AGENTS.md:52`'s two-guard movement doctrine
is about `agents/director.py` and correctly cites only `passable_route_*`
from here. Right. (F2: `_reverse_dir`; F11.)

### `spatial_senses.py`

What reaches a perceiver. Comms channels as world state (rooms OR carriers as
endpoints, `live`, one-way `broadcast`, `private`), voice-only by
construction. Sight grading (`sight_level`/`visual_level_between` with the
opening view-cone cap, distance cap, and the measured-intimacy lift),
`spatial_rel_between` — THE body-to-body relation builder, stamping
crossing/`inside_source`/`enclosed_from_source`/`source_enclosed`/
`concealed` — hearing (`hear_level` with material-shifted barriers and the
enclosure branches; `sound_walk_level`'s bounded loudness walk;
`sound_bearing`), scent (`scent_level`, F1), alarm, and the perceiver-senses
acuity gate (`sense_adjusted`: downward shifts free, upward capped so a shift
never mints content — `trace` only for hearing at +2).

Docs checked: `Design.md` "The enclosure directions fire on the paths that
deliver" matches — `spatial_rel_between` now has the production callers its
docstring claims (verified: `agents/perception.py`, `agents/loops.py`,
`agents/background.py`). `AGENTS.md:64`'s `_SOUND_LADDER` warning matches
`_material_shifted_barrier`/`sound_walk_level`'s membrane handling. Right,
except the F1/F3 items above.

### `spatial_prose.py`

Three renderers: `contact_phrase` (a standing contact as objective clause;
momentary manners render as residue; interior topology keeps
enclosure and endpoint separate), `contact_sensation` (the continuous percept
from ONE party's side, second person, `label_for` identity floor, bystanders
get ""), and `spatial_facts` (the narrator's ground-truth bundle: exits,
proximity/side/rear, light, vitals via deferred `survival` import, size,
containment, poses, contacts).

Docs checked: `Design.md` "A standing contact is a continuous percept" row
matches `contact_sensation` (asymmetric sides, momentary surface contacts
render settled residue, interior keeps kinematics); the identity-floor
addendum in "Dim light…" matches `label_for`. Right. (F8, F9.)

### `spatial_merge.py`

The deterministic scene merge. `merge_scene_with_diff` deep-copies (the
correctness boundary its comment defends), then: room/entity merges where a
schema default is silence (`_merge_room`/`_merge_entity` — the
edge-field-silence doctrine included), duplicate-key collapses for entities
and positions, `NON_ENTITY_FIELD_KEYS` refusal in both ledgers, removals,
body-enclosure inference, orphan-room attachment, dock edges, adjacency
dedupe, barrier/bearing normalisation (with the two one-sided-change shields
`_shield_standing_bearings`/`_shield_standing_passage`), contact migration,
scale (and the holds it breaks) before the beat's own ops, containment,
subject canonicalisation, derived positions, `repair_entity_positions`,
`prune_bodiless_positions`, following, substances before contact ops,
contacts, stations, poses, comms, vitals last.

Docs checked: `docs/guides/ENGINEERING.md:332-341` ("Merging is where hygiene
lives") summarises this order correctly, including the two load-bearing
orderings it calls out (substances while onset contact stands; scale before
the beat's contact ops). `Design.md` rows "A room created this turn is
reachable from somewhere", "A field name can never become an entity", and the
`_merge_entity` projection doctrine in `AGENTS.md:57` all match. Right.
(F4: `validate_operations`.)

## Facade

`spatial.py` remains as a pure re-export facade: every one of the 296 moved
names, plus the existing `spatial_orientation` and `schemas` re-exports, so
`from spatial import X` keeps working for every name importable today —
private names included (`tests/test_crowds.py:258-259` reads
`spatial._VALID_BARRIERS`/`_SIGHT_BARRIERS`,
`tests/test_continuous_contact_sensation.py:507-544` calls
`spatial._clean_contact`, both by attribute).
