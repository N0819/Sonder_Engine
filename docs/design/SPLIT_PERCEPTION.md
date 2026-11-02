# Split plan — `agents/perception.py`

Status: **LANDED 2026-11-01**, one commit, applied by the verbatim splitter
(`--check` clean; `--apply` verified 352 former names resolve on the facade and all
185 moved names are the identical objects). Seventh of its kind after `SPLIT_SPATIAL.md`,
`SPLIT_COMMIT.md`, `SPLIT_DIRECTOR.md`, `SPLIT_MEMORY.md`, `SPLIT_COMMON.md` and
`SPLIT_COMPOSER.md`, written in `SPLIT_MEMORY.md`'s format.

9,323 lines · 168 top-level defs · 15 constants (13 the anatomy lists, plus the
tuple assignment `_MASK_PREFIX, _MASK_SUFFIX` at 5187 it does not) · 2
module-level dicts the anatomy flags MUTABLE (never mutated) · no `global`, no
`ContextVar`. 12 new modules plus `agents/perception.py`.

Lines 1–128 are the docstring and the first import block; **lines 771–825 are a
second module-level import block** (two blank lines, `from . import composer`,
`from .common import (...)` — 46 names). Both are RETAINED by the facade
byte-for-byte and reproduced in each sibling to the extent that sibling needs
them. The twelve modules partition **lines 129–770 and 826–9323 exactly once**:
ranges sum to **9,140**, and 9,140 + 128 + 55 = 9,323 (verified by an AST pass
over every top-level statement, each statement owning the blank lines and
comments above it; a scratch script outside the repository reproduced the table).

The whole file was read for this plan; the audit written from the same read is
`audits/agents_perception.md`.

## The section markers are 2 seams and 5 lies

The anatomy found two "markers" (3824, 3836). Neither is a section: both are
indented comments inside `_touch_only_sources`. The file's real dividers are
comment blocks at column 0:

- **4437–4461, `# ---- The composer path -- which is now the only path. ----`**
  is the one true seam: above it the three stage entry points and their
  helpers, below it the composer orchestration. It is also stale: it says
  `resolved_event` "is read in exactly one place … `_inverted_motion_check`",
  which has been a no-op since 2026-09-15. By the attach rule it travels with
  the statement below it, `_explicit_look_intent`, into
  `perception_conduct` — where it heads a look-verb reader and describes
  nothing near it. Carried verbatim; fix in its own commit.
- **6721–6740, the C12 read-pass note** above `_composer_establish` is an
  honest seam; it describes all three `_composer_*` regions and lands in
  `perception_opening` with the first of them.

Five blocks describe something that is not below them:

- 3326–3333 ("Vertical motion … `_RAISING` / `._LOWERING`") heads the CUT
  `_inverted_motion_check`; both pack tables have no reader (→ `perception_scrub`).
- 3916–3917 ("A sentence that opens with a bare pronoun continues …") heads
  `_REDACTED_NOTICE`; the regex it described moved to the pack (→ `perception_scrub`).
- 5246–5251 ("Where one authored predicate ends … as TYPOGRAPHY") heads
  `_composer_scrub_surface`, which splits nothing; the regex is gone (→ `perception_scrub`).
- 381–385 ("Sensory-channel cues in priority order") heads `_ling` but
  describes `_atom_channel`'s table — harmless, both land in `perception_common`.
- The file's ORDER is itself the largest lie: helpers sit where the model
  path once needed them, not near their readers — `_is_the_observer` and
  `_mover_is_a_body` inside the attire block (7551–7596), the ledger readers
  split across 4525, 4787 and 9128, `present_label_fn` last. That is why ten
  of the twelve modules are non-contiguous.

## Modules

| module | lines | ranges | owns |
| --- | --- | --- | --- |
| `agents/perception_common.py` | 338 | 379–458, 3391–3416, 4523–4574, 4787–4885, 7549–7571, 9126–9183 | Leaf. The active pack's recognizer access (`_ling`), the one sentence splitter, `_SIGHT_ASSERTION`'s English compat export, `_atom_channel`; the observer-identity test (`_is_the_observer`), the human-seat test, the step's player-room stamp; and the per-observer composer ledger: previous ledger, seen/standing/described, standing metadata, `described_by`, `_prior_ledger_entry`, `_learned_labels`. |
| `agents/perception_bodies.py` | 636 | 608–770, 3163–3323, 5130–5176, 5480–5545, 7509–7548, 7597–7755 | Leaf. A body's outward form: the turn's disguise/transformation reads and caches (`drop_body_condition_caches`), `_subject_disguise_context`, tripwire terms, authored extra parts, card scents and body descriptions, attire and appearance-ledger deltas, the observer's own body state, the bare-region parser, and the dead model-path fidelity floor (§1.45). **Every reader of `active_disguises`, `active_transformations`, `scene_extra_parts` and `conceal_disguised_parts` is here.** |
| `agents/perception_senses.py` | 1,017 | 336–378, 1356–1393, 1450–1813, 1946–2279, 2630–2677, 2733–2807, 3539–3578, 4575–4649 | What reaches one observer's eyes and ears: per-source sight and channel maps (`_source_channels`), `_sight_detail`, `_in_plain_view`, rooms behind and in view, the stage's sound field, sleepers' hearing, ear cover and blast, felt sound, a line's addressee (`_line_is_to`), comm channels, an unseen voice's bearing, register and sound. Over target; it is the senses gate and splits cleanly into hearing (~525) and sight (~490) if a 13th module is preferred (the DAG holds either way: both halves read only `perception_common`). |
| `agents/perception_conduct.py` | 565 | 129–335, 1394–1449, 1814–1945, 2280–2361, 4435–4522 | Readers of this beat's declared conduct: rapid movement and the open-group continuity rescue, where a line was said against a declared walk, a crossing's legs and the channel to every leg, movers and gaits, a walk left underway, an act's own looks, sweeps and handled things. |
| `agents/perception_identity.py` | 840 | 2362–2493, 2678–2732, 2808–3012, 3993–4048, 4903–5129, 7572–7596, 9184–9323 | Who and what an observer may name: identity roster and the chat's identity space, worn roles and charter titles, recognition and attributed labels, stranger labels and self-forms, presence bodies laid on the stage scene, co-present company, body-vs-thing tests, known places and far regions, `present_label_fn`. |
| `agents/perception_scrub.py` | 830 | 2494–2629, 3324–3390, 3804–3992, 5177–5429, 6534–6718 | What a composed view may say and how it is finished: the self-narration strip and its quote-safe wrapper, identity scrubs over act surfaces, authored prose and episodes, the composer tripwires and the disguise tripwire, the per-observer finish (repaired observations, company record, ledger entry), and the retired prose-surgery helpers kept for `story/scene.py`'s replay path and tests. |
| `agents/perception_stream.py` | 879 | 826–1355, 3013–3162, 4049–4110, 4650–4786 | The outcome beat as one ordered stream and the signs placed in it: settled declarations, causal spans and restored lines, the world-ordered stream, unanswered addresses, background beats, and the tell/demeanor manifest gated per observer with its cue slots. |
| `agents/perception_standing.py` | 1,204 | 459–607, 4886–4902, 5430–5479, 5546–6533 | `_composer_standing_percepts` (409 lines, moved whole) and everything only it reads: things read by hand, station or look, visible features, things and openings (beam-lit rooms), scents, gated ambient events, bare-region rows. Cohesive at the size the spec allows; `_AMBIENT_BEAT_BAND`/`_gated_ambient_percepts` are its only exports to the views. |
| `agents/perception_opening.py` | 347 | 3417–3538, 6719–6943 | The opening pass: `perception_establish` and its composer region (`_composer_establish`, `_opening_line_percept`, `_composer_establish_views`). |
| `agents/perception_onset.py` | 825 | 3579–3803, 6944–7508, 9091–9125 | The action-onset pass: `perception_act`, `_composer_act`, `_composer_act_views` (556 lines, moved whole), and `beat_player_rooms` (runtime's early reading of the same declaration). |
| `agents/perception_outcome_views.py` | 1,335 | 7756–9090 | `_composer_outcome` and `_composer_outcome_views` (1,309 lines, one function, moved whole). Over target by construction. |
| `agents/perception_outcome_stage.py` | 324 | 4111–4434 | `perception_outcome`: composes the beat scene once, enriches the dialogue log, builds every perceiver, hands off to `_composer_outcome`. |
| `agents/perception.py` (stays) | ~250 | 1–128, 771–825 | Facade only: both import blocks verbatim, then explicit re-exports of all 185 moved names. |

**Naming hazard, avoided on purpose.** `agents/__init__.py:81` re-exports the
FUNCTIONS `perception_act`, `perception_establish`, `perception_outcome` as
attributes of the `agents` package. A sibling named after any of them
(a module file called `perception_outcome` under `agents/`) would be bound as the package attribute of
the same name the first time it is imported, and which object
`agents.perception_outcome` names would then depend on import order. Hence
`_opening`, `_onset`, `_outcome_views`, `_outcome_stage`.

## The graph, and the two moves that exist only to break a cycle

```
perception_common        -> []
perception_bodies        -> []
perception_senses        -> common
perception_conduct       -> common, senses
perception_identity      -> common, bodies
perception_scrub         -> common, identity
perception_stream        -> senses, scrub
perception_standing      -> bodies
perception_opening       -> common, bodies, senses, identity, scrub, standing
perception_onset         -> common, bodies, senses, conduct, identity, scrub, standing
perception_outcome_views -> common, bodies, senses, conduct, identity, scrub, stream, standing
perception_outcome_stage -> common, bodies, senses, identity, stream, outcome_views
```

Verified acyclic from the anatomy's reference graph (cross-checked by an
independent AST pass over every top-level def: 0 differences). **No sibling
references a symbol retained in `agents/perception.py`** — the facade keeps no
code. Function-local imports (`from .director import …`, `from .common import
beat_people_rows`, `from persist.commit import …`) stay inside their functions
verbatim; `.director` and `.common` still resolve from `agents/`.

1. **The composer ledger moves to `perception_common`** (4525–4574,
   4789–4809, 4812–4885, 9128–9183). `present_label_fn` (identity) reads
   `described_by`; `_composer_finish_observer` (scrub) reads `_learned_labels`,
   `_prior_ledger_entry` and `_standing_meta`; and scrub reads identity's
   `_composer_unknown_sources`. Filed beside its writer (the finish, in scrub)
   the ledger makes `identity → scrub → identity`. Placing it in identity would
   also be acyclic, but would make identity the owner of the composer ledger —
   a different subject. The leaf is the honest home.
2. **`_saw_across_beat` (1370) and `_body_relocated` (1452) go to
   `perception_senses`, not with their textual neighbours** `_declared_arrival_room`
   and `_speech_room_for` (1396–1449, conduct). Their only reader is
   `_source_channels` (senses), and conduct reads senses' `_sight_reaches`
   (`_channel_to_every_leg`); left in conduct they make `senses → conduct → senses`.

The other relocations against file order are topic placements, not cycle
breakers: `_is_the_observer` and `_stage_player_room` down to common (read by
senses and by all three passes); `_mover_is_a_body`/`_source_is_a_body`/
`_thing_label`/`identity_bearing_sources` into identity; `_explicit_look_intent`
and `swept_this_beat` into conduct below every view; `_with_body_description`
and `_composer_bare_details` into standing, their only reader.

## Module-level mutable state

| state | home | readers / writers | rebinding |
| --- | --- | --- | --- |
| `_SELF_EXPOSED_REGION_CUES`, `_OTHER_EXPOSED_REGION_CUES` (dicts of compiled-regex tuples) | `perception_bodies` | read only by `_deliver_foreground_body_details` (same module; no production caller, UNBUILT_PLATFORM §1.45). No writer anywhere (repo grep). | none |

That is the whole of the module-level mutable state: no `global` statement, no
`ContextVar`. Everything the module caches lives on the `PipelineContext`
under STRING keys, so it is shared across siblings by object and cannot be
stranded by a move — with one tooling caveat:

| ctx key | writer (home) | readers (homes) |
| --- | --- | --- |
| `_DISGUISES_CACHE`/`_TRANSFORMATIONS_CACHE` constants → `"_active_disguises_cache"`/`"_active_transformations_cache"`, and `"_composer_extra_parts_cache"` | `_turn_disguises`, `_turn_transformations`, `_composer_extra_parts`; dropped by `drop_body_condition_caches` (all bodies) | bodies; `runtime._restore_and_refresh` and the bubble merge call the dropper through the facade |
| `"_previous_open_group_evidence"`, `"_beat_movers"` | conduct | conduct; outcome_views (`_beat_movers(ctx)` reads the cache the first call filled) |
| `"_own_name_forms"`, `"_sound_crowds"`, `"_persona_voice_sound"` | senses | senses; all three view modules read `ctx.get("_sound_crowds")` |
| `"_background_beats_cache"` | stream | stream |
| `"_composer_prev_ledger_cache"` | common | common |
| `"_composer_identity_space_cache"` | identity | identity |
| `"_composer_turn_ledger"` | opening, onset, outcome_views | common (`described_by`, `_prior_ledger_entry`), outcome_views |
| `"_composed_beat"`, `"outcome_scene"` | outcome_stage | outcome_views; `persist/commit_scene_state` |

The caveat: `tools/project_check.py::check_pipeline_side_channels` resolves
`ctx[_CONST] = …` through the WRITING module's own string constants
(`_module_string_constants(tree)`). `_DISGUISES_CACHE` and
`_TRANSFORMATIONS_CACHE` therefore move WITH their writers (both in bodies, as
planned); split from them, the two writes would stop being checked.

## Facade

`agents/perception.py` keeps **lines 1–128 and 771–825 byte-for-byte**, in
that order, and nothing else of the old file. Not tidiness: the anatomy counts
58 attribute uses through the module object, among them `perception.composer`,
`perception.contact_sensation`, `perception._present_cast_bodies`, and test
imports of `_recognizes`, `_sentence_subjects`, `_significant_name_tokens`,
`_act_surface_admission` — all bound only by those two blocks; 16 monkeypatch
sites target `active_disguises`/`active_transformations` on the module, which
must still resolve even where the patch is inert.

Then re-export every moved name, private ones included, from the twelve
siblings: **185 names** — the anatomy's 183 plus `_MASK_PREFIX` and
`_MASK_SUFFIX` (bound at 5187 by a tuple assignment the anatomy does not
list). Explicit imports, never `import *` (the undefined-name check skips a
star-importing module), no `__all__` (there is none today). 80 distinct names
are imported from the module repo-wide and 58 attribute uses go through it;
`getattr(module, name)` in `tools/perception_quality.py` (`_dialogue_hear_level`,
`_strip_self_narration`) is covered by the same re-exports.

## Execution order

Leaf-first, one module per commit:
0 (test-only, recommended) · 1 `perception_common` · 2 `perception_bodies` ·
3 `perception_senses` · 4 `perception_conduct` · 5 `perception_identity` ·
6 `perception_scrub` · 7 `perception_stream` · 8 `perception_standing` ·
9 `perception_opening` · 10 `perception_onset` · 11 `perception_outcome_views`
· 12 `perception_outcome_stage` · 13 tooling + docs.

Commute notes: 1 and 2 are both leaves and commute. 3 follows 1; 4 follows 1
and 3; 5 follows 1 and 2; 6 follows 5; 7 follows 3 and 6; 8 follows 2 and
commutes with 3–7. 9 follows 1, 2, 3, 5, 6, 8; 10 additionally follows 4; 11
follows 1–8; 12 follows 11 (and 2, 3, 5, 7).

**Step 0 — make every pin move-invariant before anything moves.** The five
module-source pins and the two file pins below can be rewritten against
function objects or the family BEFORE step 1, and then hold through every
step; done inside the step commits instead, three of them spend a window
vacuous (the silent kind). A `perception_family_sources()` test helper that
returns the facade plus every `agents/perception_*.py` the facade imports
(`tools/project_check.facade_siblings`) serves all three family pins. The 24
monkeypatches can likewise be made move-invariant now with
`tests/helpers.py::patch_seam`, which rebinds wherever the ORIGINAL object is
bound (before the move: the facade; after: facade and reader).

**Register `agents.perception` in `FACADE_FAMILIES` at step 1, not step 13.**
The inert-patch check is the only thing that sees a patch every grep missed
(the memory split found seven that way, at step 13, after all twelve moves).
Registered with the first sibling, it guards steps 2–12 as they land.

### Monkeypatch repoints — 24 sites, each in its step's commit (or step 0 via `patch_seam`)

| step | name patched | sites | repoint to | if missed |
| --- | --- | --- | --- | --- |
| 2 | `active_disguises`, `active_transformations` | `test_visible_body_delivery.py:346,358`; `test_body_condition_cache.py:87,91`; `test_physical_transformation.py:232,238` (string targets `"agents.perception.<name>"`); `test_disguise_tripwire_after_transformation.py:46,48,54,56,63,65,79,81`; `test_disguise_hides_extra_parts.py:148,150` | `agents.perception_bodies` (readers `_turn_disguises`/`_turn_transformations`) | **silent for two tests**: `_Ctx` (chat 74) then reads the scratch DB's empty `world_conditions`, so `test_a_transformed_body_has_no_concealed_terms` (expects `[]`) and `test_the_tripwire_stays_silent_once_the_glamour_is_dropped` (expects no warning) stay green for the wrong reason; the rest fail loudly |
| 2 | `scene_extra_parts`, `conceal_disguised_parts` | `test_disguise_hides_extra_parts.py:146,158` | `agents.perception_bodies` (reader `_composer_extra_parts`) | loud (asserted call order) |
| 9 | `_composer_establish` | `test_perception_establish_persona_name.py:41` (string target) | `"agents.perception_opening._composer_establish"` (reader `perception_establish`) | the real composer runs; loud or vacuous depending on DB fixture |
| 10 | `_composer_act` | `test_perception_room_change_channels.py:312`; `test_perception_uid_position.py:178` | `agents.perception_onset` (reader `perception_act`) | loud (captured perceivers missing) |
| 11 | `_composer_outcome_views`, `swept_this_beat` | `test_the_sweep_marker_is_stamped_before_the_pass.py:42,43` | `agents.perception_outcome_views` — **both**: the reader is `_composer_outcome`, so `swept_this_beat` is patched where it is READ, not in `perception_conduct` where it is defined | loud |
| 12 | `_composer_outcome` | `test_pipeline_audit.py:378` | `agents.perception_outcome_stage` (reader `perception_outcome`) | loud |

No name is read from two siblings, so none strictly needs `patch_seam`; it is
recommended for the 16 `active_*` sites because the imported name stays bound
in the facade's retained block as well.

### Source and file pins — 16 + 2

Eleven of the sixteen `inspect.getsource` pins already name a FUNCTION and
survive any move unchanged, because the facade re-exports the same object:
`test_player_room_one_ordering.py:240` (`_composer_act_views`),
`test_far_looks.py:639` (`_composer_standing_percepts`),
`test_tells_reach_the_page.py:96` (`_delivered_manifest`),
`test_onset_audience_is_presence.py:38` (`perception_act`),
`test_perception_self_narration.py:115,118` (`_composer_finish_observer`,
`_composer_tripwires`), `test_charter_placement.py:510` (`_presence_bodies`),
`test_perception_identity_gate.py:747` (`_identity_roster`),
`test_beat_ledger.py:666` (`_outcome_event_stream`),
`test_composed_beat_scene.py:221` (`perception_outcome`),
`test_speaking_turns.py:206` (`_composer_outcome_views`).

Five pin the MODULE and must be repointed (step 0):

| site | asserts | pin instead | breaks at |
| --- | --- | --- | --- |
| `test_perception_identity_gate.py:748` | `"_worn_identity(nm, bodies, sc, titles_of)"` in module | `inspect.getsource(perception._composer_outcome_views)` (text at 8102) | step 11, loud |
| `test_perception_sentence_split.py:78` | module binds `_SENTENCE_SPLIT` exactly once | the FAMILY's sources, count == 1 (a module-level binding; no function holds it) | step 1, loud (count 0) |
| `test_the_sky_reaches_the_body_under_it.py:203` | `"weather_percepts"`, `"weather_for_room(sc, room, name)"` in module | `inspect.getsource(perception._composer_standing_percepts)` (6276–6277) | step 8, loud |
| `test_what_stands_between.py:276` | `"composer.landscape_look_percepts(found)"`, `'p["own_looks"] = _own_looks('` | `_composer_standing_percepts` (6294) and `_composer_outcome_views` (8308) | steps 8 and 11, loud |
| `test_speaking_turns.py:203` | `"micro_round_percepts(" not in` module | the FAMILY's sources | **step 11, silently vacuous** |

File pins: `test_perception_has_no_model.py:50` (`_tree()` parses
`perception.__file__`) and `:182` (`"_agent_json" not in open(perception.__file__)`).
Both must read the family. At step 9 `_fn("perception_establish")` raises
StopIteration (loud), but from step 1 onward
`test_the_module_neither_imports_nor_calls_a_model_seam` checks only the
facade's imports and calls — **the structural proof that the firewall's
deterministic floor imports no model seam would pass while blind to 9,140
lines.** No `"perception.py"` path literal exists in tests or tools
(grepped; the matches are prose in docstrings).

### Step 13 is not optional

- `tools/project_check.py`: `FACADE_FAMILIES["agents.perception"] = (ROOT / "agents", "perception")` (at step 1, above).
- `tools/generate_code_map.py`: a `MODULE_PURPOSES` entry per sibling (the 12 purposes in the JSON); keep `agents.perception` as the facade's.
- `AGENTS.md`: 28 lines name `agents/perception.py` or `perception.<fn>`; the routing rows that name the FILE as a symbol's home get the sibling (431, 456, 505, 511, 516 above all).
- `agents/README.md` (lines 9–11, the role list; 56, the role-import graph — the `perception → director` edge now leaves from conduct, onset and outcome_views).
- `CLAUDE.md` (§ Architecture's Perception sentence; and line 109's facade list, which already omits `mind.memory`).
- `docs/design/DESIGN_MODULE_LAYOUT.md` (a fifth split), `docs/CODE_MAP.md` (`make map`).
- `EXTENSION_DEEP_IMPORTS` needs nothing: `agents` is a package, so the siblings are covered the day they exist.

## Defects noticed — do not fix here

Recorded in full, with evidence, in `audits/agents_perception.md`; listed so
the split stays a move. None changes a line of this plan.

1. The sense card does not gate the environment or any sound builder (F1): a
   blind card is told "You can see the hearth … There is a silver coin at the
   long oak counter"; a deaf card hears the generator and the kettle.
2. Heard tells ignore the hearing card and the hearing rule (F2).
3. An act concealed from ONE observer is dropped for every observer at outcome (F3).
4. Uncited outcome lines are graded on a field built without the beat's events (F4).
5. `_tell_acuity` disagrees with the engine's acuity reader on 6 of 8 spellings (F5).
6. English literals reach Japanese views ("a figureが入ってくる。") (F6).
7. The disguise tripwire never fires on Japanese text and never checks a cast member's disguise (F7).
8. Ten perceiver payload fields are computed every stage and read by nothing (F9),
   plus dead pack tables and test-only helpers (F10, F11).
9. The comment and docstring set that still describes the model path (F12) —
   the composer banner above all, which moves into `perception_conduct`.


## What actually happened

Applied 2026-11-01 by the review session's splitter in 32 s. The facade keeps the
header (1-128) and, through the plan's `facade_also_keeps`, the mid-file import
block (773-825) in original order after the re-exports; `_MASK_PREFIX`/`_MASK_SUFFIX`
(line 5187, missed by the anatomy) are re-exported like every other name. Twenty-four
patch sites, five module-level `inspect.getsource(perception)` pins and two
`perception.__file__` pins were repointed in the same commit: the absence tests and
the no-model-seam AST test now walk the facade AND every sibling, so the invariant
they protect covers the whole family. `agents.perception` joined `FACADE_FAMILIES`;
the twelve siblings joined `MODULE_PURPOSES`. Sibling names avoid
`perception_act`/`_establish`/`_outcome`, which `agents/__init__.py` re-exports as
functions (a same-named submodule would rebind the package attribute).
