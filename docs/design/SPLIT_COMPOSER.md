# Split plan — `agents/composer.py`

Status: **LANDED 2026-11-01**, one commit, applied by the verbatim splitter
(`--check` clean; `--apply` verified 309 former names resolve on the facade and all
248 moved names are the identical objects). Sixth of its kind after `SPLIT_SPATIAL.md`,
`SPLIT_COMMIT.md`, `SPLIT_DIRECTOR.md`, `SPLIT_MEMORY.md` and `SPLIT_COMMON.md`, written
in the last one's format to the rules of `docs/design/DESIGN_MODULE_LAYOUT.md`.

7,691 lines · 185 top-level defs/classes (183 functions, 2 classes) · 64
module-level assignments (63 below the import block plus `logger` inside it;
the anatomy counts them as 52 constants and 12 mutable values). 12 new modules
plus `agents/composer.py`.

**Lines 1–120 are the docstring (1–52) and the top-level import block
(54–120), which holds `logger = logging.getLogger(__name__)` at line 69 between
two imports.** They are RETAINED byte-for-byte by the facade
(`facade_keep_until_line = 120`). The twelve modules partition **lines
121–7691 exactly once** — 7,571 lines, verified by
`plans/composer_partition.py`, which parses the file, gives every top-level
statement the lines from the previous statement's end to its own end (so a
marker banner or a comment block travels with the statement after it), assigns
each by name, and recomputes the sibling reference graph from the AST
(function-local bindings honoured; annotations, defaults and decorators read —
the two places the memory split's extraction tool under-reported).

**No `@line:` entries are needed.** Below line 120 every top-level statement is
a `def`, a `class` or an assignment; the only other statement kinds in the file
(the docstring `Expr`, 13 imports) are all in the retained header. The two
decorators (`@dataclass` at 219 and 5965) are the first lines of their
classes' ranges.

## The section markers are 10 banners: 6 seams, 4 lies

| line | banner | verdict |
| --- | --- | --- |
| 124 | The IR | **Seam**, slightly wide: it also heads the pack accessors (`_compositor`, `_en`, `_t`, `_ling`, `_pack_words`) and the two splicers (`_lower_lead`, `_strip_sentence_ends`). All of it is `composer_common`. |
| 324 | Referring expressions | **Seam** (`_LABEL_DANGLING` … `_silhouette_labels`), the core of `composer_figures`. |
| 661 | Layer A -- shared admission helpers | **Seam**, but its last member `_surface_suddenness` (875–895) is an act-salience helper with one reader (`act_percept`), not an admission rule. |
| 899 | Layer A -- standing-state percepts | **LIE by size.** It heads 3,738 lines (897–4634) and swallows: the phrase splicers `_spliced_fragment`/`_bare_words`/`_noun_phrase` (read by every renderer), the referent resolver (`_names_a_body`, `_part_qualified`, `_no_engine_ids`, `_pose_referent`), the whole grammatical-person subsystem (which has two banners of its own nested inside it), `micro_round_percept(s)` (deliveries, not standing state — and dead) and `residue_percepts` (the non-awake floor). |
| 2223 | The first person of an authored line, where the rewrite knows the role | **LIE by omission.** The subsystem starts 214 lines earlier, unbannered (`_OBJECT_PRONOUN_FOLLOWERS` … `_action_target_second_person`, 2009–2219), and its core (`_second_to_first_rules`, `_first_person`) sits 4,900 lines later under the episode banner. |
| 2374 | A mind's own act, in its own first person, as its attempt | **LIE by run-on.** Honest for 2381–2683 (`own_attempt` and its grammar); after it, with no banner, run `pose_percepts` and every body percept to 3090 — 400 lines of poses, appearance, tells, ears and contacts filed under "a mind's own act". |
| 4638 | Layer A -- event percepts | **Seam** (speech, silence, communication, acts, substance, crossings to 5600). The split cuts it in two at 5356/5357 (`composer_speech` / `composer_acts`). |
| 5604 | Layer B -- rendering | **Seam with a second subsystem inside.** 5686–5962 is not rendering: `standing_verdicts`, `leads_the_beat`, `steady_sound`, `habituated`, `unheard_ceasing`, `as_beat`, `player_view_order` are the engine's own pack-independent decision, read by the Japanese adapter through the facade (AGENTS.md: "A language pack asks the same public seam and does not spell either half itself"). That is `composer_standing`; the English realisation around it is `composer_render`. It also defines `WEATHER_SOUND_TAG`/`WIND_SOUND_TAG`, which a Layer A builder 1,700 lines up reads. |
| 7088 | Layer B -- the episode renderer (memory mode) | **LIE by content.** Its first real members are `_second_to_first_rules`/`_first_person` (grammatical person, read by Layer A's `_fix_i_agreement` at 2243) and, further down, `_safe_renderer` (the adapter selector `render_view` and `field_shape_sentence` read too). Both move out; the banner itself stays true because it travels with the dead `_YOU_TO_ME` into `composer_episode`. |
| 7501 | Observations -- projected from the IR | **Seam** (`_FIDELITY_AMBIGUITY` … `perception_packet`). |

The anatomy also lists 4000/4022 ("What the eyes have" / "What the skin has");
those are comments INSIDE `weather_percepts`, not top-level markers.

## Modules

| module | lines | ranges | owns |
| --- | --- | --- | --- |
| `agents/composer_common.py` | 322 | 121–320, 1762–1849, 5990–5994, 6075–6084, 7444–7462 | Leaf: the typed IR (`Percept`, `PERCEPT_KINDS`, `CHANNELS`), the opaque ledger keys (`_short_hash`, `body_key`, `standing_key`, `_subject_prefix`), `_sense_graded`, the compositor-pack accessors (`_ENGLISH_COMPOSITOR`, `_EN_TEMPLATES`, `_compositor`, `_ling`, `_en`, `_t`, `_pack_words`), the phrase splicers (`_lower_lead`, `_strip_sentence_ends`, `_spliced_fragment`, `_bare_words`, `_noun_phrase`, `_cap`, `_join_clauses`) and `_safe_renderer`. Under target deliberately — it is the module that makes the graph acyclic. |
| `agents/composer_person.py` | 725 | 2008–2683, 7096–7144 | Grammatical person: an authored third-person line turned into the observer's second person for the view (`_pose_owner_second_person`, `_action_target_second_person`) and its own first person for memory and its own attempt (`_self_first_person`, `_fix_i_agreement`, `_said_as_mine`, `_mine_if_it_matters`, `_verbs_in_base`, `own_attempt`, `_second_to_first_rules`, `_first_person`). A second leaf: it reads nothing else in the family. |
| `agents/composer_figures.py` | 628 | 321–657, 1270–1560 | Who is here and what THIS observer calls them: referring expressions, ordinals, the stranger-label ladder (`assign_stranger_labels`), the sight-gated `observer_display_map`, silhouettes and dim figures, `_visible_room_label`, relative size, near-to-far depth, `presence_percepts`. |
| `agents/composer_bodies.py` | 771 | 1561–1761, 1866–2007, 2684–3090, 4614–4634 | Every percept ABOUT a body: extra parts, the referent resolver (`_names_a_body`, `_part_qualified`, `_ID_SHAPED`, `_display_for_id`, `_no_engine_ids`, `_pose_referent`, `_same_referent`), `pose_percepts` and its field tuples, appearance, cue, demeanor, the observer's own state, ears, contacts, bare regions, and the non-awake `residue_percepts`. |
| `agents/composer_speech.py` | 935 | 658–870, 4635–5356 | A line as one observer receives it: `concealed_from_observer`, addressee (`_line_refs`, `line_addressed`, `_addresses`), the hearing gate with its rescues (`line_hear_level`), manner/voice/tone/register, `speech_percept`, `_trace_percept`, own-name forms and catch, `_one_voice_each`/`_names_kept`, silence, `communication_percept`. |
| `agents/composer_acts.py` | 285 | 871–895, 1850–1865, 5357–5600 | An act, a substance and a crossing as one observer receives them: `_surface_suddenness`, `_sound_bearing_phrase`, `_peel_own_name`, `act_percept` (rear-arc hearing, sight grade, first-person copy), `substance_percept`, the arrival/departure bands, `crossing_percept`. Small and cohesive (the memory split had 144- and 180-line modules). |
| `agents/composer_fields.py` | 947 | 896–1269, 3091–3356, 3942–4248 | The place as standing sensory state: `environment_percept` and the light/sound shapes (`_clean_shape`, `_shape_signature`, `render_light_shape`, `render_sound_shape`, `aim_worth_naming`, `field_shape_sentence`), authored sensory events (`ambient_percepts`), distant sound, scent, a walk underway, the weather by sight/skin/ear (`weather_percepts`, `_storm_percepts`, `weather_sound_percepts`) and felt shakes. |
| `agents/composer_landscape.py` | 585 | 3357–3941 | Far sight: vistas, far places, far looks, `landscape_lines` (the layout every pack shares) and `compose_landscape_line` (the realiser every pack calls with its own template reader). |
| `agents/composer_things.py` | 365 | 4249–4613 | Things in the room: `thing_clause`, `thing_in_hand_clause`, readings (`thing_reading_text`, `thing_reading_percepts`), crowds/couriers/notices (`room_content_percepts`), `chatter_percepts`, and the production-dead `micro_round_percept(s)`. |
| `agents/composer_standing.py` | 455 | 5686–5757, 5784–5962, 6572–6581, 7498–7691 | The pack-independent half of Layer B: `STANDING_VERDICTS`/`standing_verdicts`, `leads_the_beat`, the steady-sound tags, `steady_sound`, `view_verdicts`, `habituated`, `unheard_ceasing`, `as_beat`, `player_view_order`, `carried_voices`, and the observation projection (`_FIDELITY_AMBIGUITY`, `OBSERVATION_DEFAULTS`, `compact_observation`, `observations_from_render`, `perception_packet`). |
| `agents/composer_render.py` | 1,208 | 5601–5685, 5758–5783, 5963–5989, 5995–6074, 6085–6571, 6582–7084 | The English reference VIEW renderer: standing order and English phrase tables, `_appearance_restates_label`, `RenderedView`, presence clause/group, body part, pose, features, openings, `_render_standing`, scent, ambient, voice line, `_render_event`, `_render_view_english` with its slot ordering, `render_view`. Over the 900 target and kept whole on purpose (see risk 3). |
| `agents/composer_episode.py` | 345 | 7085–7095, 7145–7443, 7463–7497 | The English reference EPISODE renderer (memory mode): the episode banner, the dead `_YOU_TO_ME`, `_GENERIC_LABELS`, `_episode_sentence`, what files as memory, `_render_episode_english`, `episode_signature`, `render_episode`. |
| `agents/composer.py` (stays) | ~230 | 1–120 + re-exports | Facade only: the retained header and an explicit re-export of all 248 moved names. |

Like `mind/memory.py`, the facade keeps **no domain code at all**: every
top-level definition below line 120 belongs to exactly one of the twelve.

### Why these twelve and not the suggested nine

The suggestion grouped "environment/landscape/light/scent" as one sibling; that
group is ~1,900 lines with weather and room contents, so it is three:
`composer_fields` (the near field), `composer_landscape` (far sight) and
`composer_things` (room contents). The grammatical-person machinery (725 lines,
used by poses, acts and memory) is its own leaf because no other home avoids a
cycle (move 1 below). The observation projection (194 lines) joins
`composer_standing` rather than standing alone, to stay inside twelve: both are
the language-independent consumers of a rendered view. If the owner prefers a
separate `composer_observations`, the cost is a 13th module and nothing else —
it imports `composer_common` only.

## Moves against file order

Three are FORCED by the DAG (leaving them in file-order homes is a cycle); the
rest are cohesion moves that a reviewer should see listed rather than discover.

**Cycle-breaking (forced):**

1. **`_second_to_first_rules` + `_first_person` (7096–7144) → `composer_person`.**
   Layer A's `_fix_i_agreement` (2243) calls `_first_person`; `_said_as_mine`
   and `_mine_if_it_matters` call it too. Left under the episode banner it makes
   `person → episode` while `episode → person` (`_said_as_mine`,
   `_verbs_in_base`) — a cycle. The dead `_YOU_TO_ME` (7092) stays in
   `composer_episode` so the episode banner it carries stays true there.
2. **`_safe_renderer` (7444–7462) → `composer_common`.** Read by
   `field_shape_sentence` (fields), `render_view` (render) and `render_episode`
   (episode). Left in episode: `fields → episode → render → fields`.
3. **`_cap` (5990–5994) and `_join_clauses` (6075–6084) → `composer_common`.**
   Read by `_shape_clauses`/`render_light_shape`/`render_sound_shape` (fields),
   `render_distant_sound`, landscape, things and every renderer. Left in render:
   `fields → render → fields`.

**Cohesion (not forced):**

4. `_spliced_fragment`, `_bare_words`, `_noun_phrase` (1762–1849) → common: the
   phrase splicers every builder and renderer share; filed today between the
   referent resolver and `_pose_referent`.
5. The admission helpers (658–870) → speech; `_surface_suddenness` (871–895)
   and `_sound_bearing_phrase` (1850–1865) → acts (one reader each:
   `act_percept`). `composer_acts` imports `concealed_from_observer` from
   `composer_speech` — no cycle (speech reads nothing of acts).
6. `residue_percepts` (4614–4634) → bodies (the non-awake floor is the body's
   own state, not room content).
7. `_STANDING_ORDER` … `_LANDSCAPE_SLOT` (5601–5685), `_appearance_restates_label`
   (5758–5783), `RenderedView` + `PLURAL_PLACES` (5963–5989) → render: their
   only in-family readers are English rendering. Keeping
   `_appearance_restates_label` out of standing keeps standing free of
   `composer_figures` (`_label_core`).
8. `VOICE_KEY_PREFIX`/`carried_voices` (6572–6581) → standing: both renderers
   read it (the Japanese adapter at `language_adapters/japanese.py:671`).
9. `WEATHER_SOUND_TAG`/`WIND_SOUND_TAG`/`HABITUATING_SOUND_TAGS` stay in
   standing with their comment block; `composer_fields` imports the two tags
   (`weather_sound_percepts`). Edge `fields → standing`, no cycle.

## The graph — a DAG, verified

```
composer_common    -> []
composer_person    -> []
composer_figures   -> common
composer_bodies    -> common, person
composer_speech    -> common
composer_acts      -> common, figures, person, speech
composer_landscape -> common
composer_things    -> common
composer_standing  -> common
composer_fields    -> common, standing
composer_render    -> bodies, common, fields, figures, landscape, person, speech, standing
composer_episode   -> bodies, common, landscape, person, render, speech, standing
```

Edge evidence (the names that carry each cross-sibling edge) is printed by
`plans/composer_partition.py`; the two heaviest are `render → standing` (ten
verdict/order functions) and `episode → render` (`_end_sentence`,
`_render_ambient`, `_render_pose`, `_render_scent`). **No sibling references
any symbol retained in the facade** — the facade's header defines one name,
`logger`, and that is the one header line that needs care (risk 2).

## Module-level mutable state

Twelve values, all dicts built at import. Grepped symbol by symbol across the
whole repository (engine, tests, tools, adapters): **no writer anywhere** — no
item assignment, no `.update`/`.pop`/`.clear`, no `global` statement (the file
has none), no ContextVar defined in the module. Every reader below reads the
SAME object, through its own import or the facade's re-export.

| value | home | readers |
| --- | --- | --- |
| `_ORDINAL_WORDS` | figures | `_label_core`, `_active_ordinal_words` (fallback), `_ordinal_word` |
| `_PRESENCE_DEPTH_TIERS` | figures | `_presence_sort_key` (called by `presence_percepts`, and by render's `_render_presence_group`) |
| `_COUNT_NAMES` | bodies | render's `_render_body_part` |
| `_ENGINE_CHANNEL_PERCEPT` | fields | `_ambient_channel` |
| `_SCENT_FIDELITY` | fields | `scent_percepts` |
| `_FELT_SALIENCE` | fields | `felt_percepts` |
| `_STANDING_ORDER` | render | `_render_view_english`; tests read it (`test_scent_percept.py`, `test_tells_reach_the_page.py`, `test_composer_percept_kinds.py`) |
| `_TIER_PHRASES` | render | `_presence_clause`, `_feature_items` |
| `_SIZE_PHRASES` | render | `_presence_clause`; `tests/test_acuity_proportionality.py:173` imports it |
| `_COUNT_WORDS` | render | `_render_presence_group` |
| `_FIDELITY_AMBIGUITY` | standing | `observations_from_render`; **`agents/loops.py:597`** reads `composer._FIDELITY_AMBIGUITY["shapes"]` through the facade |
| `OBSERVATION_DEFAULTS` | standing | `compact_observation`; **`agents/narration.py:1891,1893`** read it through the facade; `tests/test_schemas.py:183` |

`_ENGLISH_COMPOSITOR` and `_EN_TEMPLATES` look mutable and are not: the card
loader returns `mappingproxy` objects (checked at runtime). The frozensets and
tuples are immutable. A rebind across modules would be the silent failure and
there is none to make.

## Facade

`agents/composer.py` keeps lines **1–120 unchanged**. That block is part of the
contract, not tidiness:

- tests read imported names THROUGH the module object: `composer.hear_level`
  (5 test uses), `composer._muffled_fragment`, `composer.linguistic`; and two
  tests patch imported names (`voice_carries`, below). Those names must keep
  resolving on the facade even where a patch of them is inert;
- `logger` (line 69) stays here byte-for-byte.

Then an explicit re-export of all 248 moved names, private ones included, one
`from .composer_<x> import (...)` block per sibling in leaf-first order.
Explicit names, never `import *` (`project_check`'s undefined-name check skips
any module with a star import). No `__all__` (there is none today).
`composer._render_percept` (used once in `tests/test_composer.py:1036`) is not
defined today either; the test guards it with `hasattr`, and the facade must
not invent it.

**The external contract is wider than the anatomy reports.** The anatomy's
"3 prod files import the module object" misses the relative spelling
`from . import composer`. An AST count (attribute access on the imported
module object, plus `from agents.composer import`) finds **11 production
importers** — `agents/{background,character,director,director_movement,loops,
narration,perception}.py`, `language_adapters/japanese.py`,
`persist/commit_memory.py`, `tools/speech_replay.py`, `web/pipeline_views.py` —
and **92 distinct names used in production**, among them `thing_clause`,
`thing_in_hand_clause`, `sound_ceased_percept`, `line_addressed`, `_line_refs`,
`_sense_graded`, `_t`, `_peel_own_name`, `_visible_room_label` that the anatomy
lists as 0 prod. Re-exporting every name covers all of it; the point is that a
shortcut "re-export only what the anatomy lists" would break production, not
tests. (One stale comment, `world/spatial_light_field.py:1362`, names a
`composer._light_shape` that has never been the composer's — it is
`JapaneseRenderer._light_shape`.)

### Header of each sibling

Generated from the reference graph; every sibling starts with
`from __future__ import annotations` (the facade has it, and `Percept`'s and
`RenderedView`'s field annotations are strings under it — a sibling without it
would turn them into evaluated types). Deferred imports stay inside their
functions verbatim (35 of them; `from .common import split_sentences` etc.
resolve identically from a sibling in the same package).

```
composer_common:   import hashlib, logging; from collections.abc import Mapping
                   from dataclasses import dataclass, field
                   from language_runtime import LanguagePackError, current_language_id,
                       language_pack, linguistic, renderer_for
                   from world.spatial import sense_adjusted
                   logger = logging.getLogger("agents.composer")   # risk 2
composer_person:   import re; from language_runtime import linguistic
                   from .common import _base_from_third_person_s, _fix_you_agreement,
                       name_occurrence_pattern
composer_figures:  from .common import _recognizes, _unknown_actor_label, stranger_label_ladder
                   from story.scene import disguise_breaks_recognition
                   from world.spatial import body_cell, body_visibility, effective_anchors,
                       effective_station, entity_arc, entity_side, held_beam_falls_on,
                       proximity_rel, room_of, size_relation, visual_level_between
                   from .composer_common import Percept, _ENGLISH_COMPOSITOR, _compositor,
                       _noun_phrase, _sense_graded, _strip_sentence_ends, _t, body_key, standing_key
composer_bodies:   import re; from .common import _self_second_person
                   from world.spatial import _anchor_room_of, _clean_pose, _entities_named,
                       _entity_named, _is_body_entity, contact_thing_label, effective_anchors,
                       entity_arc, proximity_rel, room_of, same_subject, visual_level_between
                   from .composer_common import Percept, _ENGLISH_COMPOSITOR, _lower_lead,
                       _noun_phrase, _pack_words, _sense_graded, _strip_sentence_ends, _t,
                       body_key, standing_key
                   from .composer_person import _mine_if_it_matters,
                       _pose_owner_second_person, _self_first_person
composer_speech:   import dataclasses, re
                   from .common import _identity_token_set, _muffle_tokens, _muffled_fragment,
                       _quote_body, self_name_forms
                   from core.pipeline_context import note_step_decision
                   from language_runtime import linguistic
                   from world.spatial import hear_level, hearing_reason, into_another_ear,
                       sense_acuity_offset, spoken_to, voice_carries
                   from .composer_common import Percept, _ENGLISH_COMPOSITOR, _lower_lead,
                       _pack_words, _sense_graded, _short_hash, _strip_sentence_ends,
                       body_key, standing_key
composer_acts:     import re; from .common import _self_second_person
                   from core.pipeline_context import note_step_decision
                   from world.spatial import entity_arc, movement_heard_at_ear, room_of,
                       same_subject, sound_bearing
                   from .composer_common import Percept, _ling, _short_hash
                   from .composer_figures import _visible_room_label
                   from .composer_person import _action_target_second_person,
                       _mine_if_it_matters, _self_first_person
                   from .composer_speech import concealed_from_observer
composer_landscape: from .composer_common import Percept, _ENGLISH_COMPOSITOR, _cap, _en,
                       _noun_phrase, _short_hash, standing_key
composer_things:   from language_runtime import linguistic
                   from .composer_common import Percept, _cap, _en, _noun_phrase, _t, standing_key
composer_standing: import dataclasses; from .composer_common import _subject_prefix
composer_fields:   from story.provenance_text import strip_engine_provenance
                   from world.spatial import _sense_channel
                   from .composer_common import CHANNELS, Percept, _cap, _en, _join_clauses,
                       _noun_phrase, _safe_renderer, _subject_prefix, _t, logger, standing_key
                   from .composer_standing import WEATHER_SOUND_TAG, WIND_SOUND_TAG
composer_render:   from dataclasses import dataclass, field
                   from .common import _appearance_as_prose, _compose_residue_view,
                       _inject_dialogue, _observable_predicate
                   from .composer_bodies import EAR_STATES, _COUNT_NAMES
                   from .composer_common import Percept, _ENGLISH_COMPOSITOR, _bare_words, _cap,
                       _en, _join_clauses, _noun_phrase, _safe_renderer, _spliced_fragment,
                       _strip_sentence_ends, _subject_prefix, logger
                   from .composer_fields import render_distant_sound, render_light_shape,
                       render_sound_shape
                   from .composer_figures import _dim_figure, _label_core, _ordinal_label,
                       _presence_sort_key
                   from .composer_landscape import far_sight, is_landscape, landscape_lines,
                       render_landscape_line
                   from .composer_person import _said_as_mine
                   from .composer_speech import _can_say_the_voice, _feeling_heard,
                       _names_kept, _one_voice_each
                   from .composer_standing import appearance_delta, as_beat, asked_this_beat,
                       carried_voices, habituated, leads_the_beat, player_view_order,
                       standing_verdicts, unheard_ceasing, view_verdicts
composer_episode:  from .common import _appearance_as_prose, _base_from_third_person_s,
                       _compose_residue_view, _observable_predicate
                   from .composer_bodies import EAR_STATES
                   from .composer_common import _ENGLISH_COMPOSITOR, _cap, _en,
                       _safe_renderer, logger
                   from .composer_landscape import far_sight, is_landscape, landscape_lines,
                       render_landscape_line
                   from .composer_person import _first_person, _said_as_mine, _verbs_in_base
                   from .composer_render import _end_sentence, _render_ambient, _render_pose,
                       _render_scent
                   from .composer_speech import _feeling_heard, _names_kept, _one_voice_each
                   from .composer_standing import HABITUATING_SOUND_TAGS, standing_verdicts,
                       unheard_ceasing
```

After each step, regenerate the step's header from the AST and diff it against
what was written — the memory split found its tool's two under-reports
(`hashlib` bound by a function-local import; `-> Optional[...]` annotations)
exactly this way.

## Execution order

Leaf-first, one module per commit: 1 `composer_common` · 2 `composer_person` ·
3 `composer_figures` · 4 `composer_bodies` · 5 `composer_speech` ·
6 `composer_acts` · 7 `composer_landscape` · 8 `composer_things` ·
9 `composer_standing` · 10 `composer_fields` · 11 `composer_render` ·
12 `composer_episode` · 13 tooling + docs.

Commute notes: 1 and 2 commute (two leaves). After 1: 3, 5, 7, 8, 9 commute.
4 follows 1 and 2. 6 follows 2, 3, 5. 10 follows 9. 11 follows 3, 4, 5, 7, 9,
10. 12 follows 11.

## Monkeypatch / source-pin repoint table

An AST scan of every `setattr`/`patch.object`/`patch_seam` in `tests/` and
`tools/` finds exactly the anatomy's 7 sites aimed at `composer` (an 8th,
`tests/test_perception_establish_persona_name.py:41`, patches
`agents.perception._composer_establish` and is not this module's). Source pins:
**0** `inspect.getsource(composer)`, **0** `inspect.getsource(composer.<fn>)`,
**0** `composer.__file__`, **0** `"composer.py"` path literals, **0**
string-form patch targets.

| step | site | name | reader(s) after the split | action |
| --- | --- | --- | --- | --- |
| 5 | `tests/test_composer.py:1025` | `line_hear_level` | `speech_percept`, defined in the SAME sibling | **repoint → `agents.composer_speech`.** `check_facade_patch_targets` will NOT flag this site (it only sees names a sibling imports and calls; this one is defined there). It fails loudly instead: the real gate returns `full` and the test asserts `fidelity == "fragment"`. |
| 5 | `tests/test_composer.py:1027` | `voice_carries` | `speech_percept` (imported from `world.spatial` into `composer_speech`) | **repoint → `agents.composer_speech`.** The static check flags it from step 5. |
| 10 | `tests/test_japanese_renderer_parity.py:169` | `_safe_renderer` | `field_shape_sentence` (fields, step 10), `render_view` (render, step 11), `render_episode` (episode, step 12); defined in `composer_common` since step 1 | **repoint at step 10 with `patch_seam(monkeypatch, "agents.composer", "_safe_renderer", ...)`.** Step 10 is when a sibling first imports-and-calls it, so the static check fails `make structure` there — one step BEFORE the test's own reader (`render_view`) moves. A `setattr` on `agents.composer_render` cannot be written at step 10 (the module does not exist yet); `patch_seam` rebinds the facade (render_view's home until 11), common, fields, and later render and episode. |
| — | `tests/test_a_line_is_heard_from_where_it_was_spoken.py:385` | `act_percept` | `agents/perception.py` via `composer.act_percept` | none — read through the facade attribute; no sibling calls it |
| — | `tests/test_display_map_stage_route.py:208` | `observer_display_map` | `perception._co_present_company` via `composer.` | none |
| — | `tests/test_perception_proximity_floor.py:152` | `speech_percept` | `perception.perception_act` via `composer.` | none |
| — | `tests/test_disguise_reearns_on_transition.py:63` | `appearance_percept` | `perception` via `perception.composer.` | none |

Counts: **3 repoints** (setattr 3: two plain `setattr` to `composer_speech`,
one `patch_seam`), **0 getsource**, **0 `__file__`**, **0 path**. Four sites stay
as written because every reader is outside the family.

The two repointed test files then import a sibling by name
(`agents.composer_speech`, and nothing for `patch_seam`); `check_facade_import_direction`
allows a test that names a sibling it PATCHES.

## Tooling and docs (step 13)

- `tools/project_check.py`: `FACADE_FAMILIES["agents.composer"] = (ROOT / "agents", "composer")`.
  Registering it is what turns on both facade checks for this family; run
  `make structure` and read any inert-patch hits even where the test passes.
- `tools/generate_code_map.py`: `MODULE_PURPOSES` has no `agents.composer`
  entry today; add the facade's and one per sibling (the purposes in the JSON).
- `AGENTS.md`: the routing rows naming `agents/composer.py` (at least lines
  456, 505, 507, 510, 512, 558 and the invariants at 661/672/884) — keep the
  file name, add the sibling where a row names a function now living in one.
- `agents/README.md` line 12 and the "LEAF the roles share" paragraph;
  `CLAUDE.md` § Architecture (Perception paragraph and the `composer` LEAF
  sentence); `docs/design/DESIGN_MODULE_LAYOUT.md` (a fifth family).
- `EXTENSION_DEEP_IMPORTS` needs nothing (package-scoped). `tools/package_edges.json`
  needs nothing (no new package edge: every sibling import is `agents → agents`
  or an edge the facade already had).
- **Do NOT rewrite** the three `"agents.composer"` string literals that are
  namespace coordinates, not imports: `_ling`'s `linguistic("agents.composer", …)`
  (both packs key `linguistics.json` by it — en line 1963, ja line 2309) and
  `tools/build_japanese_pack.py:443`. `tests/test_room_minds.py:517` checks
  `seam.startswith("agents.composer")`, which every sibling name also satisfies.

## The three riskiest points

1. **Two inert-patch hazards with different detectors.** `line_hear_level`
   goes inert at step 5 with no static flag (same-sibling definition) and is
   caught only because its test asserts a fragment; `_safe_renderer` is flagged
   statically at step 10, one step before its test's reader moves, so the
   repoint must be `patch_seam`, not a setattr on a module that does not exist
   yet.
2. **The logger and the namespace literal.** Line 69 stays in the facade; four
   readers move (`_safe_renderer`, `field_shape_sentence`, `render_view`,
   `render_episode`). `composer_common`'s header defines
   `logger = logging.getLogger("agents.composer")` — the literal, so every log
   record keeps today's name and every sibling shares the facade's logger
   object; `__name__` there would silently rename them. Nothing in the repo
   filters on the name (checked), so this is about faithfulness, not tests. The
   `"agents.composer"` linguistics namespace must not be "fixed" to a sibling
   name, or every `_ling` lookup raises `LanguagePackError` in both packs.
3. **`composer_render` at 1,208 lines and three forced moves against file
   order.** The renderer is kept whole (cohesive: it is the English reference
   renderer, and its natural cut — 6085–6571 standing sentences vs 6582–7084
   events and assembly — would be a 13th module). The forced moves
   (`_first_person` 4,900 lines up, `_safe_renderer` and `_cap`/`_join_clauses`
   into common) are the only places a reviewer cannot rely on `git diff -M`
   locality; check them byte-for-byte.

## Defects noticed — do not fix here

Flagged for the audit (`audits/agents_composer.md`, with evidence), recorded
here so the split stays a move. Line numbers are pre-split.

1. `observations_from_render` (7618–7620) projects `directed_at_self` from
   percept data for lines whose words did not carry — the one field that lets
   the second representation outrun the view. Moves with step 9.
2. `observations_from_render` (7598) derives `phase: "change"` from `force`, an
   objective flag, so a body met for the first time is filed under
   `changes_noticed`. Step 9.
3. `ambient_percepts` (3166) admits every room-scoped event to an observer with
   no room. Step 10.
4. `_episode_sentence` (7195–7203) files a rear-arc heard act as a subject-less
   sight sentence, and has no `communication` branch at all. Step 12.
5. `pose_percepts`' key (2857–2861) hashes the referent's display label, so
   learning a name re-declares a pose `changed`. Step 4.
6. `_render_view_english`'s residue path (6803–6805) drops every carried voice
   key. Step 11.
7. Dead in production: `micro_round_percept(s)` (4557–4613), `_YOU_TO_ME`
   (7092), `DIM_FIGURES` (1284). They move as they are.
8. The episode banner (7087–7089) stays true only because it travels with the
   dead `_YOU_TO_ME`; when `_YOU_TO_ME` is deleted, the banner must move to
   `_GENERIC_LABELS`, not be deleted with it.
9. The module docstring (1–52), retained by the facade, describes one file
   ("imports common, spatial, scene only", "`build_*_percepts`"); it will
   describe twelve. Correct it in its own commit after the split.


## What actually happened

Applied 2026-11-01 by the review session's splitter in 32 s. The header's
`logger = logging.getLogger(__name__)` is reproduced in `composer_common` as
`getLogger("agents.composer")`, the same Logger object. Three patch sites were
repointed with `tests/helpers.py::patch_seam` (`line_hear_level`, `voice_carries`
→ `agents.composer_speech`; `_safe_renderer` → `agents.composer_common`, whose
readers are composer_fields, composer_render and composer_episode); the other
four patch sites read through the facade and needed nothing. `agents.composer`
joined `FACADE_FAMILIES`; the twelve siblings joined `MODULE_PURPOSES`.
