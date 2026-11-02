# Split plan — `agents/common.py`

Status: **LANDED 2026-11-01**, one commit, applied by the verbatim splitter
(`--check` clean: 0 errors, 3 import-order warnings; `--apply` verified 426 former
names resolve on the facade and all 354 moved names are the identical objects).
Fifth of its kind, after [`SPLIT_SPATIAL.md`], [`SPLIT_COMMIT.md`],
[`SPLIT_DIRECTOR.md`] and [`SPLIT_MEMORY.md`], and written to the rules in
`docs/design/DESIGN_MODULE_LAYOUT.md`: verbatim moves, the facade keeps the
filename and re-exports every former top-level name (private ones included),
leaf-first, flag never fix.

12,971 lines · 292 top-level defs/classes · 61 assignments (58 constants + 3
mutable literals) · 3 other top-level statements (`for` @310, `del` @313,
`from persist.commit import _normalize_character_output` @7525) · 16 new modules
plus `agents/common.py`.

**Lines 1–70 are the docstring and the module-level import block.** The facade
retains them byte-for-byte (`facade_keep_until_line = 70`). The sixteen siblings
partition **lines 71–12971 exactly once — 12,901 lines** (the tool that made the
table below sums the ranges and checks every statement is owned once; a free
comment block or blank run attaches to the statement that follows it).

**Verified by a dry run, not only by reading.** The partition was generated into
a scratch package outside the repository
and imported against the real tree: the facade exposes exactly the original
module's names (0 missing, 0 extra), every function's `inspect.getsource` is
byte-identical to the original, no sibling imports the facade, the sibling graph
imports with no cycle, and six pure functions answer identically (`norm_sequence`,
`split_stage_directions`, `_unknown_actor_label`, `cut_short_speech`,
`communication_verb`, `_classify_action_commitment`). The same scratch package
was used to demonstrate the inert-patch cases in the repoint table.

## The section markers are 1 seam and the comment blocks are the lies

The file carries exactly **one** marker: `12792 # ---- What the player asserts
is true before anyone reacts to it ----`. It is honest — it heads the three
player-state-assertion functions and runs to EOF (all three go to
`common_beat`). Everything else is unmarked; the seams in the module table were
found by reading, confirmed against the intra-module reference graph.

What a split executor must not trust are the **orphaned comment blocks** — the
explanation of a word list that moved to `language_packs/*/cards/linguistics.json`
left behind above whatever statement now follows it. The verbatim rule carries
each of them into a sibling, attached to an unrelated statement, exactly as
`commit_common.py` inherited a wrong `# ---- Mapping commit ----`. They are not
to be fixed in the move commits; they are listed so a reviewer is not surprised:

| line | the comment describes | it sits above (and moves with) | lands in |
|---|---|---|---|
| 6533–6547 | the quoted-span regex and its single-quote rule (`_QUOTED_SPAN_RE`, pack) | `_SURFACE_CLAUSE_SPLIT` | `common_identity` |
| 7988–7990 | `_NAME_LEADERS` (pack) | `_player_name_forms` | `common_names` |
| 8266–8267 | `_NEW_SUBJECT_RE` (pack) | `_predicate_heads` | `common_names` |
| 10014–10026 | the colon healer, two stacked drafts that contradict each other ("Drop the orphaned lead-in" / "The lead-in TEXT is kept") | `_heal_dangling_colon` | `common_scrubs` |
| 10276–10279 | "Content words whose repetition is a genuine tic … must carry at least one of these" — the list is `_TIC_STOPWORDS`, i.e. the inverse | `_overused_phrases` | `common_narration` |
| 10815–10827 | `_NARRATION_DOUBLED_QUOTE_RE` / `_NARRATION_DANGLING_QUOTE_RE` (pack) and third-person evidence | `_MARKUP_TAG_RE` | `common_narration` |
| 10925–10929 | "Third-person paradigms screened by `_check_pronoun_fidelity`" | `_pronoun_to_group` | `common_names` (the check it describes stays in `common_narration`) |
| 10942–10948 | "Splits a sentence into clauses" — the clause splitter is `_CLAUSE_SPLIT` (pack) | `_SENTENCE_SPLIT` (the SENTENCE splitter) | `common_names` |
| 11843–11844 | `_LOOK_VERB_RE` (pack) | `_check_position_fidelity` | `common_fidelity` |
| 11961–11964 | the deleted `_YOU_INTERIOR` check, as if live | the note that it was removed | `common_fidelity` |

The module docstring ("Shared coercion, validation, lore, sequence, and
perception helpers") and `tools/generate_code_map.py`'s purpose line ("Shared
normalization, lore, delivery, and perception helpers") are the other lie: lore
is three live functions and two dead ones; the file's mass is the identity
floor, the Director/narrator fidelity checks, charter figures and sequence
normalisation.

## Modules

| module | lines | ranges (after attachment) | owns |
|---|---:|---|---|
| `agents/common_base.py` | 155 | 76–113, 992–1025, 5299–5308, 6861–6915, 9199–9202, 9577–9590 | The leaf every sibling stands on: `_ling`/`_text` (pack lookup under the `"agents.common"` key), `_dangling_speech` + its two English compat views, `_stem_token`, `_dict`/`_list`/`_dict_list`, `_text_piece`/`_join_text`, `_append_once`, the typography fold, markup strip and `_contains_quote`, `_quote_body`, `_base_from_third_person_s`. Under target deliberately — it is what makes the graph acyclic. |
| `agents/common_llm.py` | 182 | 3979–4160 | The model-call seam and JSON recovery: `_agent_json`, `jparse`, `_mend_closers`/`_closer_runs`/`MEND_CLOSER_EDITS`. Kept separate because it is THE seam 25 test sites patch and `tests/helpers.py::MODEL_SEAMS` names. |
| `agents/common_names.py` | 1,105 | 5309–5432, 5791–5830, 5878–6409, 6503–6532, 7987–8323, 10924–10965 | Names in any script: tokens, floors and recognition; sentence splitting (`split_sentences`, `_SENTENCE_SPLIT`), subject and pronoun tracking (`_sentence_subjects`, `_predicate_heads`, `_strip_subject`, `_pronoun_to_group`, `_pronoun_group`), title/occurrence patterns (`_subject_opener` + its LRU), and the stranger-label grammar (`_unknown_actor_label` … `stranger_label_ladder`, `_strip_identity_tokens`). |
| `agents/common_cast.py` | 646 | 1085–1134, 6916–7511 | The registered cast in the scene: `character_scene_keys`, `character_room`, `cast_room`, `entity_room_by_name`, `_present_cast_bodies`, `normalize_character_refs`, `cast_spelling_policy`, entity claims/stamping/reconcile/ensure, `canonicalize_positions`, `drop_room_keyed_positions`, and `_conceal_from_targets_observer` (an exclusion list read against an observer's handles). |
| `agents/common_bodies.py` | 774 | 1392–1889, 3216–3398, 6410–6502 | What one observer can perceive of a body: attire views/exposure facts/owner refs, extra parts, `region_visibility`, `observer_body_regions`, enclosure spelling (`_subject_spellings`, `_enclosure_of`, `_enclosure_conceals`), `_perceptible_entities` (+ `_ENTITY_LOOKUP_ONLY_FIELDS`), `_delivery_ok`. |
| `agents/common_rooms.py` | 834 | 1345–1391, 1890–2249, 2959–3215, 4161–4330 | What a room holds for a perceiver: `_contextual_rooms`, crowds (`CROWDS_KEY`, `crowds_for_room`, `charter_ground_for_room`, `charter_crowds_for_room`, `chatter_inputs`, `_standing`), `attending_this_room`, `chatter_for_room`, `couriers_for_room`, `artifacts_for_room`, the lore slice (`_books`, `_book_weights`, `lore_for`, the two dead ambient-slug helpers) and room prose (`room_prose`, `whole_sentences`, `_room_notes_for_view`, `_room_notes_from_lore`). |
| `agents/common_figures.py` | 1,101 | 2250–2958, 12398–12789 | Who stands where this beat: `charter_titles`, `presence_figures_for_room`, `charter_view_for_rooms`, `lay_charter_figures`, `beat_people_rows`, `_creature_stance`, `present_charter_figures`, planned/reserved figures, `dwellings_in_reach`, the player-room ladder (`_llm_resolve_player_room`, `_resolve_player_room`, `_frame_has_no_player`, `player_room_in`) and the aperture (`rooms_in_view`, `_aperture_centers`, `figures_in_view`). |
| `agents/common_identity.py` | 733 | 5433–5790, 5831–5877, 6533–6860 | The identity floor applied: `observer_label_fn`, `observer_view_label_fn`, `_presence_surface`, `_uncarded_person`, `observer_name_scrub`, `_other_peoples_names`, `scrub_names_deep`, `scene_figures`, `_act_surface_admission` (+ `_SURFACE_CLAUSE_SPLIT`), `_scrub_unknown_identities`. |
| `agents/common_acts.py` | 1,213 | 71–75, 114–855, 3513–3978 | What a declared element is and what resolution made of it: interior/autonomous classification, the communicative-act table (+ the `for`/`del` that build `_COMMUNICATION_FORMS`), referents, claim scans and dispositions, onset surfaces, `authored_other_subject`, `bind_sequence_targets`, the reaction/resolution gates (+ `_REACTIVE_STAGES`, moved from line 73 to its only reader), commitment classification and `_extract_authority_claims`. |
| `agents/common_sequence.py` | 1,231 | 856–991, 4331–5298, 7553–7671, 7979–7986 | A declared beat as the engine holds it: player-speech provenance, stage-direction excision, `norm_sequence` and its helpers, duplicate collapse, speech fusion, event ids (`assign_event_ids`, `_stable_event_key`), `_lore_fingerprint`, narrated-speech repair, `substitute_player_token`, `player_speech_lines`. |
| `agents/common_beat.py` | 913 | 1026–1084, 1135–1344, 3399–3512, 7512–7552, 7672–7978, 12790–12971 | The beat's bookkeeping around its minds: `_assert_plan_materialized`, `_character_by_id`, the `_MERGE_*` tables and `_merge_character_results`, loop helpers (`_asks_player`, `_next_speaker_candidates`, …), `_append_micro_view`, **the `@7525` re-export import**, `declared_goal`, reactor widening (`widen_reactors_*`, `acted_upon_cast`, `AIMED_ELEMENT_TYPES`), and the player's state assertions (the one marker's section). |
| `agents/common_scrubs.py` | 569 | 9153–9198, 9965–10209, 10544–10821 | Prose repair passes: `_cap_repeated_quotes`, the dangling-speech healers, `_protected_view_quotes`, `_echo_fold`, `_strip_player_echo`, `_collapse_empty_quote_debris`, `_scrub_invented_dialogue`/`_scrub_undeclared_player_speech`, the view-sentence mask and dedupe. |
| `agents/common_authority.py` | 829 | 8324–9152 | Authority on resolved prose and contacts: character speech/act authority, prose-quote authority, `director_may_voice`, the presence-knowledge channel floor, player interiority/act/contact authority, and the player-authority ladder (`_claim_authority_kind`, `downgraded_sequence_indices`, `apply_player_authority`). |
| `agents/common_views.py` | 748 | 9203–9576, 9591–9964 | Deterministic sentences composed into a view: muffling, `_tone_clause`, `_inject_dialogue`, `self_name_forms`, `self_reference_forms`, `_self_second_person`/`_fix_you_agreement`, `_observable_predicate`, `_compose_residue_view`, and the dead injection/fallback family (UNBUILT_PLATFORM §1.45). |
| `agents/common_narration.py` | 804 | 10210–10543, 10822–10923, 10966–11333 | The narrator's voice, measured: tics, rhythm, shingles, person counts and sentences, tense counts, `_check_pronoun_fidelity`, `_check_player_person`, the person and tense match checks. |
| `agents/common_fidelity.py` | 1,064 | 11334–12397 | The narrator page against its records: event order, quote attribution, action attribution, position/portal/attire fidelity, speech marking, `_dialogue_tokens`, `_check_narrator_fidelity`. |
| `agents/common.py` (stays) | 70 + re-exports | 1–70 | Facade only (below). |

Two siblings sit slightly over the 1,200-line guidance (`common_acts` 1,213,
`common_sequence` 1,231). Both are one subject each; splitting either would
separate the claim scans from the dispositions they settle, or the speech arm of
`norm_sequence` from the helpers only it calls.

## Moves against file order

The naive range split has exactly one cycle, and the rest of the moves are
layering:

1. **Cycle-breaking — `_SENTENCE_SPLIT` (10949), `_pronoun_to_group` (10930),
   `_pronoun_group` (10951) move from the narration block to `common_names`.**
   `split_sentences` defaults to `_SENTENCE_SPLIT` and `_sentence_subjects`
   reads both pronoun helpers, while every narration check reads `split_sentences`
   and `_name_tokens`: left in place, `names → narration → names`.
2. **Cycle-breaking — `_quote_body` (9201) moves to `common_base`.** Read by
   `common_base._contains_quote` itself and by six siblings (sequence,
   authority, scrubs, views, fidelity, base). Left in the view block it closes
   `base → views → base`.
3. **Layering — the typography block (6861–6915: `_TYPOGRAPHY_FOLD`,
   `_fold_typography`, `_PROSE_MARKUP_RE`, `strip_prose_markup`,
   `_contains_quote`) moves to `common_base`.** Its file-order neighbour is the
   identity scrub; left there, `views` and `fidelity` would import
   `common_identity` for a string fold.
4. **Layering — `_base_from_third_person_s` (9579) moves to `common_base`.**
   `communication_verb` (acts) and the view rewriters both read it; left in
   `common_views`, the low-level `acts` would import the view composer.
5. **Layering — `_append_once` (5300) moves to `common_base`.** Only the view
   injectors read it; left in place, `views → sequence` for a nine-line string
   helper.
6. **`_REACTIVE_STAGES` (73) goes to `common_acts`**, beside its only reader
   `_requires_reaction_phase`. Not a cycle; it is the first statement of the
   file and belongs to no other subject.

Everything else moves as contiguous blocks. `git diff -M` will read the six
moves above as deletions/additions inside other hunks; the reviewer checks them
by name against this list.

## The sibling graph (a DAG, verified by import)

```
common_base       -> []
common_llm        -> []
common_cast       -> []
common_names      -> base
common_bodies     -> base
common_rooms      -> names
common_figures    -> base, llm, rooms
common_identity   -> base, cast, figures, names
common_acts       -> base, cast, names
common_sequence   -> acts, base
common_beat       -> acts, base, cast
common_scrubs     -> base
common_authority  -> base, names, scrubs
common_views      -> base, names
common_narration  -> base, names
common_fidelity   -> base, names, narration
```

No sibling references a symbol retained in `agents/common.py`; the facade keeps
no code. `common_beat` carries the one eager cross-package import that lived
mid-file (`@7525`, `from persist.commit import _normalize_character_output`).
Verified safe in any position: a fresh `import persist.commit` loads no
`agents.*` module (persist reaches `agents.common` only through deferred
imports in `commit_attire`, `commit_memory`, `commit_background`,
`commit_scene_state`), so the import that was placed at line 7525 "to dodge a
cycle" no longer needs its position — and none of the file's 62 deferred imports
dodges a cycle today either (each target was imported fresh and loads no
`agents.*` module; the persist→agents deferred imports on the OTHER side are the
real cycle dodges, and `tools/package_edges.json` already counts them as
deferred). Moved verbatim, it stays mid-module in `common_beat` with its
`# noqa: E402,F401`.

## Module-level mutable state

| state | home | readers / writers | rebind? |
|---|---|---|---|
| `_REACTIVE_STAGES` (set literal) | `common_acts` | read by `_requires_reaction_phase` only; never written | no |
| `COMMUNICATION_ACT_VERBS` (dict) | `common_acts` | read by `communication_verb` and the `@310` loop; one test imports it; never written after import | no |
| `_COMMUNICATION_FORMS` (dict) | `common_acts` | filled once at import by `@310` (`setdefault`), read by `communication_act`; `@313` deletes the loop names `_act/_forms/_form` — the facade must not try to re-export those three | no |
| `_subject_opener`'s `lru_cache(maxsize=_SUBJECT_OPENER_CACHE)` | `common_names` | every call writes it; no `cache_clear` caller in the repo | no (object travels with the function) |
| caller-owned memos (`inputs["memo"]`, `["standing"]`, `["ground_memo"]`, `["figure_memo"]`, `["placement_memo"]`, `["presence_ledger"]`; `ctx["_rooms_in_view_cache"]`, `["_figures_in_view_cache"]`, `["_books"]`, `["_book_weights"]`, `["_player_room"]`) | callers' dicts | written by `common_rooms` and `common_figures` into ONE shared `inputs` dict; read across the two | mutation of a shared object, never a rebind — safe |

There is no `global` or `nonlocal` statement anywhere in the file, and no
`ContextVar` is defined here (`figures_in_view` sets and resets `core.db`'s
`active_frame_id`, a shared object).

## Facade

`agents/common.py` keeps **lines 1–70 unchanged** and then re-exports every
moved name, leaf-first, one relative `from .common_<x> import (…)` block per
sibling (the `agents` package style; `facade_siblings` reads relative and
absolute spellings alike), explicit names, no star, no `__all__`, plus
`_normalize_character_output` from `common_beat` (it was a module binding).

The header is part of the contract, which the anatomy report under-counted:
it matched only `from agents.common import …`, and fourteen role modules import
`from .common import …` (relative). Resolving those, **248 distinct names are
used from outside the module, 9 of them names `common.py` only imports**
(`character_name`, `room_of`, `normalized_character_of_row`,
`cap_mind_model_updates`, `chat_complete`, `get_prompt`,
`normalize_speech_volume`, `scene_names_body`, `_normalize_character_output`),
and tests patch three more header names on the facade (`chat_complete`,
`get_prompt`, `persona_of`). Trimming "unused" imports from the facade breaks
`agents/__init__.py`, `character.py`, `director.py`, `perception.py` and
`offscreen_beat.py` at import.

## Execution order

Leaf-first, one module per commit: 1 `common_base` · 2 `common_llm` ·
3 `common_names` · 4 `common_cast` · 5 `common_bodies` · 6 `common_rooms` ·
7 `common_figures` · 8 `common_identity` · 9 `common_acts` · 10 `common_sequence` ·
11 `common_beat` · 12 `common_scrubs` · 13 `common_authority` · 14 `common_views` ·
15 `common_narration` · 16 `common_fidelity` · 17 tooling + docs.

Commute notes: 2 (`llm`) and 4 (`cast`) depend on nothing in the family and can
land at any point; 3, 5, 12, 14 need only 1 (and 14 needs 3); 6 follows 3; 7
follows 2 and 6; 8 follows 3, 4, 7; 9 follows 3 and 4; 10 and 11 follow 9 (11
also 4); 13 follows 3 and 12; 15 follows 3; 16 follows 15.

Each sibling starts `from __future__ import annotations` (the original's
annotations are strings; `ClaimScan(NamedTuple)` keeps working either way) and
imports from the header modules only what its own statements read — the dry-run
generator computed those sets; reuse it rather than hand-picking, and remember
the memory split's two lessons (a function-local `import` is not a module
binding; annotation names count). `q` appears as a LOCAL in `common_scrubs`,
`common_authority` and `common_fidelity` (comprehension and local variables) —
a naive free-name pass reports `core.db.q` as needed there; it is not.

## Monkeypatch, source-pin and path-pin repoints

46 patch sites aim at `agents.common` (40 `setattr(common, …)`, 6 string-form
`setattr("agents.common.<name>", …)`; no `patch.object`, `mock.patch`,
`setitem` or direct assignment; no `patch_seam` call targets this module).
0 `inspect.getsource(<module>)` pins, 0 `__file__` pins, 1 path pin.

| step | site(s) | name | reader after the split | decision |
|---|---|---|---|---|
| — | 25 sites: `tests/test_room_designer.py:350`; `tests/test_a_room_in_view_is_built_before_anyone_walks_in.py:113,429,609,666,708,998,1038,1081,1172,1222,1271,1300,1340`; `tests/test_room_is_captured.py:431`; `tests/test_a_room_brief_is_designed_once_and_continued_at_most_n_times.py:86,107,147,200,320`; `tests/test_ambience.py:895`; `tests/test_a_planned_building_is_laid_out_by_relations.py:777,870,903`; `tests/test_a_room_built_ahead_stands_before_the_beat_touches_it.py:75` | `_agent_json` | no reader inside the family; every reader re-imports it from the FACADE at call time (`director_rooms.py:2812`, `director_layout.py:169`, `skip_stage.py:380`, `dressing/ambience.py:803`, `dressing/backdrops.py:1452`) | **no repoint** — the facade attribute is what they read (demonstrated on the dry-run package) |
| — | `tests/test_replay_defects_h.py:303,329` | `present_charter_figures` | `director._figures_in_view` re-imports it from `.common` at call time | **no repoint** |
| 7 | `tests/test_rooms_in_view.py:133,166` | `present_charter_figures` | `figures_in_view`, same sibling | → `agents.common_figures` (both assert by ABSENCE: inert, they stay green) |
| 7 | `tests/test_no_player_no_resolver_call.py:30` (absence), `:52` (spy) ; `tests/test_a_townsperson_is_never_the_player.py:30` (absence) ; `tests/test_perception_identity_gate.py:771` (absence), `:786` (absence) | `_llm_resolve_player_room` | `_resolve_player_room`, same sibling | → `agents.common_figures` |
| 7 | `tests/test_the_player_is_not_a_stove.py:38,61,102,114` (string form) | `_llm_resolve_player_room` | same | → `"agents.common_figures._llm_resolve_player_room"` |
| 7 | `tests/test_the_player_is_not_a_stove.py:82,83` (string form) | `chat_complete`, `get_prompt` | `_llm_resolve_player_room` reads its own sibling's import bindings | → `"agents.common_figures.chat_complete"` / `".get_prompt"` (inert, the REAL provider is called) |
| 7 | `tests/test_player_room_one_ordering.py:50`; `tests/test_a_line_is_heard_from_where_it_was_spoken.py:476`; `tests/test_perception_room_change_channels.py:313` | `_resolve_player_room` | `player_room_in`, same sibling | → `agents.common_figures` |
| 7 | `tests/test_player_room_one_ordering.py:121` | `persona_of` | `player_room_in` (also read in `common_beat`, `common_identity`) | → `agents.common_figures` (the reader under test); `patch_seam(monkeypatch, "story.scene", "persona_of", …)` if a test ever exercises more than one |
| 7 | `tests/test_model_seams.py:37` | `chat_complete` | the test checks the import-time alias a REAL caller holds; after the split that caller is `common_figures` | → `agents.common_figures`. Not inert (the facade still binds the name), but `check_facade_patch_targets` FLAGS it once the family is registered — `common_figures` imports and calls `chat_complete` |
| 9 | `tests/test_claim_disposition_single_scan.py:98` | `scan_claims_for` | `_claim_realized`, `adjudicated_player_action_text`, same sibling | → `agents.common_acts` (fails loudly if missed) |
| 5 | `tests/test_delivery_gate_not_universal.py:26` (`DEFINING_MODULE = "common.py"`) | path pin | the AST scan of `agents/*.py` | → `"common_bodies.py"` (passes either way — `"common.py" not in sites` stays trivially true — which is why it must follow the text) |

Counts: **19 `setattr` repoints (13 attribute-form, 6 string-form), 1 path pin,
0 `getsource`, 0 `__file__`; 27 sites need none.** Of the 18 that go inert,
`check_facade_patch_targets` would catch exactly one (`persona_of`, which a
sibling imports and calls); it does not see a name DEFINED in a sibling and
called there, and it does not read string-form patches at all. The other 17
must be repointed from this table, in the step that moves their reader.

Not patch sites, but named for the record: `tests/helpers.py:113`
(`MODEL_SEAMS`) and `tests/model_seams.py:43` (`MODEL_DOORS`) both list
`("agents.common", "_agent_json")` as the DEFINING module. Their identity sweep
still patches every holder (the facade, `common_llm`, every role module), and
`tests/test_composer_admission_gate.py:142` / `tests/test_composer_pipeline.py:36`
still find `("agents.common", "_agent_json")` in the patched list, so nothing
fails; only the "defining" comment goes stale.

## Step 17 — tooling and documents

- `tools/project_check.py`: `FACADE_FAMILIES["agents.common"] = (ROOT / "agents", "common")`.
  No other module in `agents/` starts with `common_`, so `facade_siblings` reads
  exactly the sixteen.
- `tools/generate_code_map.py`: sixteen `MODULE_PURPOSES` entries (the purpose
  strings are in `SPLIT_COMMON.json`) and a facade purpose for `agents.common`;
  then `make map`.
- `AGENTS.md`: 16 lines name `agents/common.py` with symbols; repoint each to the
  owning sibling — `_delivery_ok`, `attire_view`, `extra_part_phrase`,
  `scene_extra_parts`, `observer_body_regions` → bodies; `bind_sequence_targets`,
  `settle_sequence_dispositions`, `prune_blocked_phase_changes` → acts;
  `STEP_MARK`, `_carry_step_mark`, `norm_sequence` → sequence;
  `presence_figures_for_room`, `present_charter_figures`, `charter_view_for_rooms`,
  `dwellings_in_reach`, `planned_figures_in_view`, `reserved_plan_figures` →
  figures; `_unknown_actor_label` and the label family → names;
  `self_reference_forms`, `_self_second_person`, `_fix_you_agreement`,
  `_compose_residue_view` → views; `_scrub_unknown_identities` → identity;
  `_check_narrator_fidelity` → fidelity; `_check_player_person`,
  `_check_narration_person_match` → narration. Line 431's `_AUTONOMY_VERBS` is a
  pack key, not a symbol (pre-existing; see the audit).
- `agents/README.md`, `docs/design/DESIGN_MODULE_LAYOUT.md` (a fifth family),
  `CLAUDE.md:105` (the one-way rule now covers sixteen siblings; note that
  NOTHING enforces it today — see the audit's Docs-checked section).
- Do **not** touch the string `"agents.common"` anywhere — it is the language
  pack's namespace (6 call sites in this file: `_ling`, `_dangling_speech` ×2,
  `_SPEECH_CUE`, `_act_surface_admission`, `_strip_identity_tokens`; 20 more in
  `agents/*.py` and `language_adapters/`; the top-level key of both
  `linguistics.json` files; `tools/build_japanese_pack.py:261`). A dotted name
  in a string is not an import.

## The three riskiest points

1. **The inert-patch class is almost invisible to the gate here.** Seventeen of
   eighteen sites that go inert when steps 7 and 9 land are not seen by
   `check_facade_patch_targets`, and nine of them assert by absence
   (`test_rooms_in_view.py:133,166`, `test_no_player_no_resolver_call.py:30`,
   `test_a_townsperson_is_never_the_player.py:30`,
   `test_perception_identity_gate.py:771,786`,
   `test_the_player_is_not_a_stove.py:38,102,114`) — they stay green while
   proving nothing, and an inert `_llm_resolve_player_room` stub lets the real
   resolver reach `chat_complete`. Repoint from the table, then read each test's
   assertions, not its exit status.
2. **`"agents.common"` is a coordinate, not a module path.** A sweep that
   rewrites dotted names after the move re-keys every `_ling` lookup in the
   family (and in `composer`, `narration`, `language_adapters/japanese.py`);
   renaming the pack key to match would make it silent.
3. **The facade header carries more than the anatomy counted.** Relative imports
   were invisible to it: 248 names are used from outside, 9 of them only
   imported here, and the mid-file `@7525` import exists only to re-export
   `_normalize_character_output` to `character.py`. The header must stay
   byte-for-byte and `common_beat` must keep the `@7525` statement; both fail
   loudly if broken, which is the good kind — the silent kind is point 1.

## Defects noticed — do not fix here

Flagged in full, with evidence and line numbers, in
`docs/experiments/REVIEW_2026_11_01.md` (the review's audit record, which carries the findings made while reading the file).
The ones a mover will literally carry across: the dead pair
`_ambient_blocked_slugs`/`_keys_reference_blocked` (`common_rooms`), the stub
`_check_action_direction` that returns `[]` under a 40-line docstring
(`common_fidelity`), the six dead injection helpers already registered as
UNBUILT_PLATFORM §1.45 (`common_views`, `common_bodies`), the `realized_event_ids`
branch no producer can reach (`common_acts`), the false "owes `story.scene`
nothing" comment (`common_narration`), the orphan comments tabled above, and the
Japanese-pack class (whitespace tokens, ASCII sentence ends, `\b` boundaries,
an LRU keyed without the language) spread across `names`, `identity`, `acts`,
`sequence`, `authority`, `views`, `narration` and `fidelity`.


## What actually happened

Applied 2026-11-01 by the review session's splitter (an AST tool: `symtable`-based
free-name analysis with annotations collected separately, so neither of the two
`SPLIT_MEMORY.md` extraction bugs can recur; a verbatim-partition assertion; a
sibling DAG check; and a post-write re-import that compares every former name
against the original module's namespace). The three import-time side effects the
check warned about (`for`/`del` at 310-313, the late `from persist.commit import`
at 7525) moved with their blocks into `common_acts` and `common_beat` and ran in
the same order at import. `agents.common` joined `FACADE_FAMILIES`, the sixteen
siblings joined `MODULE_PURPOSES`, and the test seam tables in `tests/helpers.py`
and `tests/model_seams.py` now name the DEFINING sibling (`agents.common_llm`) for
`_agent_json`. The monkeypatch repoints listed above were made in the same commit;
two the plan missed (`tests/test_replay_defects_h.py:303,329`,
`present_charter_figures`) were found by the splitter's repoint table and
repointed too. The splitter's own finding worth keeping: `project_check`'s
`check_facade_patch_targets` never reads string-form `setattr("pkg.mod.name")`
patches and cannot see a reader that DEFINES the patched name in its own sibling,
so ten of these repoints would have gone silently inert under the gate alone.
