# Generated Code Map

> Regenerate with `python tools/generate_code_map.py`. Do not hand-edit this file.

## Python modules

| Module | Lines | Purpose | Local dependencies |
|---|---:|---|---|
| `affect.py` | 1965 |  | `theory_of_mind` |
| `agents/__init__.py` | 86 | Backward-compatible facade for the role-specific agent package. | `agents.character`, `agents.common`, `agents.director`, `agents.loops`, `agents.mapping`, `agents.narration`, `agents.perception`, `agents.runtime`, `agents.storage`, `scene` |
| `agents/background.py` | 889 |  | `agents.common`, `background_claims`, `character_schema`, `commit`, `db`, `prompts`, `scene`, `schemas`, `spatial` |
| `agents/character.py` | 3215 | Private character decision agent. | `affect`, `agents.common`, `character_schema`, `db`, `frames`, `gaps`, `memory`, `place_purpose`, `prompts`, `psychology_runtime`, `scene`, `schemas`, `spatial`, `survival`, `theory_of_mind` |
| `agents/common.py` | 5305 | Shared normalization, lore, delivery, and perception helpers. | `attire`, `character_schema`, `db`, `llm_quality`, `memory`, `providers`, `scene`, `schemas`, `spatial`, `theory_of_mind` |
| `agents/director.py` | 4921 | Scene establishment, player interpretation, and objective resolution. | `agents.common`, `attire`, `character_schema`, `db`, `memory`, `paradox`, `prompts`, `providers`, `scene`, `schemas`, `spatial` |
| `agents/loops.py` | 1010 | Reaction loops, interaction rounds, and deterministic micro-perception. | `agents.character`, `agents.common`, `character_schema`, `db`, `scene`, `spatial` |
| `agents/mapping.py` | 239 | Lore routing, cached recall, and retrieval staging. | `agents.common`, `character_schema`, `db`, `memory`, `prompts`, `scene` |
| `agents/narration.py` | 956 | Player-facing narration agent. | `agents.common`, `character_schema`, `db`, `prompts`, `scene`, `schemas`, `spatial` |
| `agents/perception.py` | 3962 | Opening, action-onset, and outcome observer views. | `affect`, `agents.common`, `character_schema`, `db`, `prompts`, `scene`, `spatial` |
| `agents/runtime.py` | 1009 | Pipeline plans, dispatch, streaming, cancellation, resume, and reruns. | `agents.background`, `agents.character`, `agents.common`, `agents.director`, `agents.loops`, `agents.mapping`, `agents.narration`, `agents.perception`, `agents.storage`, `character_schema`, `checkpoints`, `commit`, `db`, `pipeline_context`, `providers`, `scene` |
| `agents/storage.py` | 115 | Step and active-variant persistence helpers. | `db` |
| `ambience.py` | 2082 |  | `backdrops`, `db`, `outofband`, `weather` |
| `app.py` | 4808 | FastAPI application assembly, resource CRUD, turn control, and streaming endpoints. | `agents`, `ambience`, `attire`, `auth_routes`, `backdrops`, `character_schema`, `chat_archive`, `checkpoints`, `commit`, `db`, `frames`, `greetings`, `guest_access`, `importers`, `memory`, `paradox`, `pipeline_context`, `prompts`, `providers`, `scene`, `survival`, `updates` |
| `attire.py` | 1828 |  | — |
| `auth_routes.py` | 175 | Typed host-authentication HTTP routes and cookie transport. | `guest_access` |
| `authored_events.py` | 124 |  | `db` |
| `backdrops.py` | 1258 |  | `db`, `logging_utils`, `outofband`, `spatial`, `weather` |
| `background_claims.py` | 466 |  | `db` |
| `canon_provenance.py` | 360 |  | — |
| `carriers.py` | 164 |  | `character_schema`, `db`, `living_world`, `scene`, `spatial` |
| `character_schema.py` | 1383 | Versioned character/persona defaults, normalization, accessors, and export payloads. | `attire`, `schemas` |
| `chat_archive.py` | 1096 | Typed, atomic chat archive export/import service and HTTP routes. | `character_schema`, `checkpoints`, `db`, `memory`, `schemas` |
| `checkpoints.py` | 1096 | Whole-chat snapshots and checkpoint restore orchestration. | `db`, `memory` |
| `comfort.py` | 306 |  | `spatial` |
| `commit.py` | 6619 | Validated persistence of scene, entities, cast, lore, relationships, events, and memories. | `affect`, `attire`, `character_schema`, `comfort`, `db`, `frames`, `mechanics`, `memory`, `paradox`, `prompts`, `providers`, `psychology_runtime`, `scene`, `spatial`, `spatial_frames`, `survival`, `theory_of_mind`, `weather` |
| `db.py` | 1600 | SQLite schema, migrations, connection management, transactions, and key/value world access. | — |
| `frames.py` | 220 |  | `db` |
| `gaps.py` | 548 |  | `canon_provenance`, `db`, `logging_utils`, `providers`, `spatial`, `subjects` |
| `greetings.py` | 375 |  | `agents.runtime`, `agents.storage`, `character_schema`, `db`, `llm_quality`, `memory`, `prompts` |
| `guest_access.py` | 355 |  | `db` |
| `importers.py` | 2621 | Native and AI-assisted character, persona, and lorebook import/generation. | `character_schema`, `db`, `logging_utils`, `memory`, `prompts`, `providers` |
| `jobs.py` | 183 |  | `logging_utils` |
| `living_world.py` | 602 |  | `logging_utils`, `mechanics` |
| `llm_quality.py` | 292 | Strict JSON parsing, schema validation, and model-assisted repair. | `providers`, `schemas` |
| `logging_utils.py` | 118 | Structured timing and observability helpers. | — |
| `lore_structure.py` | 242 |  | — |
| `mechanics.py` | 310 |  | `spatial`, `spatial_frames` |
| `memory.py` | 5086 | Lorebook graph, memory retrieval/consolidation, relationships, and vector search. | `db`, `frames`, `logging_utils`, `prompts`, `providers`, `theory_of_mind` |
| `offscreen.py` | 1503 |  | `logging_utils` |
| `outofband.py` | 276 |  | `logging_utils` |
| `paradox.py` | 489 |  | `character_schema`, `db`, `frames` |
| `pipeline_context.py` | 248 | Typed mutable context passed through a turn pipeline. | `db` |
| `pipeline_trace.py` | 413 | Privacy-conscious export, validation, and offline replay of persisted pipeline history. | `db` |
| `place_purpose.py` | 532 |  | `comfort`, `spatial`, `survival`, `theory_of_mind` |
| `prompt_cache.py` | 79 | Provider-specific prompt-cache helpers. | `providers` |
| `prompts.py` | 4117 | Default system prompts and prompt preset access. | `db` |
| `providers.py` | 2025 | Provider selection, retries, streaming, cancellation, model listing, and embeddings. | `db` |
| `psychology_runtime.py` | 502 |  | — |
| `routines.py` | 200 |  | — |
| `scene.py` | 1424 | Scene/cast/persona helpers, recent events, dialogue configuration, and private knowledge. | `attire`, `character_schema`, `db`, `spatial` |
| `schemas.py` | 3910 | Pydantic output contracts and semantic validation for agent payloads. | — |
| `spatial.py` | 6358 | Deterministic room, barrier, hearing, visibility, placement, and scene-diff logic. | `schemas`, `spatial_orientation` |
| `spatial_frames.py` | 975 |  | `character_schema`, `db`, `frames`, `paradox`, `scene`, `spatial` |
| `spatial_orientation.py` | 246 | Bearing math and reciprocal spatial-edge normalization. | — |
| `subjects.py` | 449 |  | `canon_provenance`, `db`, `spatial` |
| `survival.py` | 320 |  | `db` |
| `theory_of_mind.py` | 703 |  | — |
| `updates.py` | 394 |  | — |
| `weather.py` | 808 |  | `spatial` |

## Largest top-level functions

### `affect.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_project_ops()` | 1178 | 137 lines |
| `appraise()` | 456 | 136 lines |
| `resolve_affect()` | 673 | 134 lines |
| `apply_intent_ops()` | 1000 | 132 lines |
| `normalize_wants()` | 813 | 87 lines |
| `validate_drive_shift()` | 1748 | 79 lines |
| `update_drive_strain()` | 1629 | 77 lines |
| `project_boundary()` | 1512 | 66 lines |

### `agents/background.py`

| Function | Start | Size |
|---|---:|---:|
| `scene_life()` | 465 | 120 lines |
| `_beat_for_presence()` | 109 | 76 lines |
| `_react_one()` | 829 | 61 lines |
| `_mint_blurbs()` | 654 | 57 lines |
| `background_react()` | 209 | 52 lines |
| `_place_block()` | 267 | 47 lines |
| `managed_presences()` | 361 | 46 lines |
| `_present_others()` | 782 | 45 lines |

### `agents/character.py`

| Function | Start | Size |
|---|---:|---:|
| `character_step()` | 2335 | 881 lines |
| `_annotate_known_exits()` | 1756 | 445 lines |
| `_ground_observation_citations()` | 816 | 263 lines |
| `_unanswered_question_note()` | 270 | 117 lines |
| `_destination_from_goals()` | 1334 | 109 lines |
| `sprint_offers()` | 2236 | 97 lines |
| `_recent_self_moves()` | 143 | 86 lines |
| `_verdict()` | 1178 | 72 lines |

### `agents/common.py`

| Function | Start | Size |
|---|---:|---:|
| `norm_sequence()` | 1533 | 193 lines |
| `_scrub_invented_dialogue()` | 4198 | 145 lines |
| `_check_narrator_fidelity()` | 5119 | 123 lines |
| `_extract_authority_claims()` | 1063 | 106 lines |
| `_perceptible_entities()` | 641 | 98 lines |
| `_check_presence_knowledge_channel()` | 3008 | 95 lines |
| `region_visibility()` | 502 | 92 lines |
| `_check_quote_attribution()` | 4852 | 91 lines |

### `agents/director.py`

| Function | Start | Size |
|---|---:|---:|
| `director_resolve()` | 3768 | 1154 lines |
| `director_interpret()` | 749 | 388 lines |
| `_reconcile_resolution()` | 3251 | 315 lines |
| `_reconcile_near_group_positions()` | 2242 | 201 lines |
| `_evidence_present()` | 2924 | 179 lines |
| `_reconcile_interpretation()` | 1294 | 119 lines |
| `_validated_player_contact_assertions()` | 133 | 115 lines |
| `director_establish()` | 584 | 114 lines |

### `agents/loops.py`

| Function | Start | Size |
|---|---:|---:|
| `interaction_loop()` | 372 | 568 lines |
| `deterministic_micro_perception()` | 45 | 96 lines |
| `reaction_loop()` | 941 | 70 lines |
| `_isolated_wave()` | 329 | 41 lines |
| `_defer_to_unrun_reactor()` | 186 | 37 lines |
| `_standing_pressure()` | 225 | 37 lines |
| `_perceptually_isolated()` | 292 | 35 lines |
| `_defer_to_focus()` | 156 | 28 lines |

### `agents/mapping.py`

| Function | Start | Size |
|---|---:|---:|
| `mapping_stage()` | 32 | 108 lines |
| `mapping_quick()` | 141 | 64 lines |
| `merge_lore()` | 207 | 33 lines |

### `agents/narration.py`

| Function | Start | Size |
|---|---:|---:|
| `narrator()` | 622 | 198 lines |
| `_ordered_beat_events()` | 254 | 143 lines |
| `narrator_extra()` | 821 | 136 lines |
| `_visible_portal_states()` | 486 | 100 lines |
| `_position_delta_payload()` | 430 | 54 lines |
| `_resolve_narration_person()` | 71 | 47 lines |
| `_generate_narration()` | 588 | 33 lines |
| `_player_sees_character()` | 399 | 29 lines |

### `agents/perception.py`

| Function | Start | Size |
|---|---:|---:|
| `perception_outcome()` | 3166 | 797 lines |
| `perception_act()` | 2460 | 517 lines |
| `_observer_scene_payload()` | 845 | 204 lines |
| `perception_establish()` | 2286 | 173 lines |
| `_previous_open_group_continuity()` | 155 | 117 lines |
| `_strip_self_narration()` | 1683 | 107 lines |
| `_inject_onset_speech()` | 1207 | 96 lines |
| `_source_channels()` | 1488 | 86 lines |

### `agents/runtime.py`

| Function | Start | Size |
|---|---:|---:|
| `_run_pipeline()` | 651 | 305 lines |
| `build_plan()` | 450 | 81 lines |
| `resume_key_for_turn()` | 395 | 54 lines |
| `run_pipeline()` | 957 | 53 lines |
| `_load_extra_players()` | 42 | 52 lines |
| `_stream_one()` | 249 | 48 lines |
| `_stream_parallel()` | 298 | 45 lines |
| `_rehydrate_loop_results()` | 603 | 41 lines |

### `agents/storage.py`

| Function | Start | Size |
|---|---:|---:|
| `save_step()` | 21 | 28 lines |
| `active_content()` | 50 | 17 lines |
| `mark_steps_stale()` | 85 | 12 lines |
| `delete_step()` | 106 | 10 lines |
| `_set_steps_stale()` | 77 | 7 lines |
| `clear_steps_stale()` | 98 | 7 lines |
| `variant_count()` | 68 | 4 lines |
| `step_is_stale()` | 73 | 3 lines |

### `ambience.py`

| Function | Start | Size |
|---|---:|---:|
| `resolve_ambience()` | 1671 | 221 lines |
| `_rank_candidates()` | 1083 | 105 lines |
| `refine_layers()` | 756 | 82 lines |
| `cached_ambience()` | 479 | 62 lines |
| `search_freesound()` | 1368 | 61 lines |
| `search_local()` | 888 | 54 lines |
| `_query_ladder()` | 1197 | 51 lines |
| `acoustic_fingerprint()` | 260 | 45 lines |

### `app.py`

| Function | Start | Size |
|---|---:|---:|
| `turn_branch()` | 3690 | 390 lines |
| `_remap_cp_blob()` | 666 | 194 lines |
| `chat_get()` | 2286 | 169 lines |
| `_stream()` | 279 | 91 lines |
| `lore_entry_edit()` | 2075 | 70 lines |
| `lore_edit()` | 1927 | 68 lines |
| `_ambience_payload()` | 4590 | 68 lines |
| `guest_state()` | 2725 | 66 lines |

### `attire.py`

| Function | Start | Size |
|---|---:|---:|
| `compact_line()` | 1689 | 131 lines |
| `normalize_regions()` | 318 | 125 lines |
| `decisive_targets()` | 1114 | 89 lines |
| `recover_shed_entity_changes()` | 775 | 87 lines |
| `dedupe_regions()` | 864 | 87 lines |
| `coerce_diff_shape()` | 1001 | 84 lines |
| `perceptible_region_surfaces()` | 1359 | 78 lines |
| `apply_flat_change()` | 1439 | 70 lines |

### `auth_routes.py`

| Function | Start | Size |
|---|---:|---:|
| `auth_login()` | 108 | 60 lines |
| `auth_setup()` | 69 | 36 lines |
| `_set_host_cookie()` | 47 | 9 lines |
| `auth_status()` | 59 | 7 lines |
| `auth_logout()` | 171 | 5 lines |

### `authored_events.py`

| Function | Start | Size |
|---|---:|---:|
| `resolve_authored_events()` | 90 | 35 lines |
| `mint_authored_events()` | 42 | 28 lines |
| `due_authored_events()` | 72 | 16 lines |
| `_event_id()` | 36 | 4 lines |

### `backdrops.py`

| Function | Start | Size |
|---|---:|---:|
| `generate_backdrop()` | 1064 | 115 lines |
| `room_projection()` | 526 | 73 lines |
| `visual_signature()` | 135 | 48 lines |
| `scene_after_turn()` | 690 | 35 lines |
| `build_backdrop_request()` | 727 | 35 lines |
| `branch_lineage()` | 216 | 34 lines |
| `compose_prompt()` | 833 | 34 lines |
| `compose_revision()` | 895 | 33 lines |

### `background_claims.py`

| Function | Start | Size |
|---|---:|---:|
| `settle_claims()` | 404 | 45 lines |
| `_verdicts()` | 359 | 43 lines |
| `novel_proper_nouns()` | 169 | 39 lines |
| `_mint()` | 210 | 27 lines |
| `prepare_canon()` | 332 | 25 lines |
| `write_canon()` | 306 | 24 lines |
| `canon_entry()` | 282 | 22 lines |
| `_known_variants()` | 144 | 17 lines |

### `canon_provenance.py`

| Function | Start | Size |
|---|---:|---:|
| `validate_provisional()` | 233 | 105 lines |
| `_node_id_errors()` | 199 | 32 lines |
| `promote()` | 340 | 21 lines |
| `unavailable()` | 178 | 19 lines |
| `outranks()` | 159 | 17 lines |
| `is_node_id()` | 133 | 9 lines |
| `may_assert_consequence()` | 150 | 7 lines |
| `is_canon()` | 144 | 4 lines |

### `carriers.py`

| Function | Start | Size |
|---|---:|---:|
| `advance_carriers()` | 64 | 101 lines |
| `reports_for_state()` | 46 | 16 lines |
| `_character_room()` | 34 | 10 lines |

### `character_schema.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_character_data()` | 829 | 156 lines |
| `default_character_data()` | 411 | 93 lines |
| `_normalize_psychology()` | 258 | 80 lines |
| `repair_character_shape()` | 770 | 57 lines |
| `character_initial_active_state()` | 1184 | 48 lines |
| `normalize_persona_data()` | 986 | 47 lines |
| `_coerce_appearance()` | 691 | 45 lines |
| `_as_profile_list()` | 38 | 36 lines |

### `chat_archive.py`

| Function | Start | Size |
|---|---:|---:|
| `_model_validate()` | 54 | 4 lines |
| `_model_dump()` | 60 | 4 lines |

### `checkpoints.py`

| Function | Start | Size |
|---|---:|---:|
| `snapshot_state()` | 15 | 155 lines |
| `_restore_checkpoint_body()` | 510 | 141 lines |
| `compact_checkpoints()` | 760 | 118 lines |
| `_restore_books()` | 171 | 104 lines |
| `insert_world_tables()` | 350 | 92 lines |
| `ensure_checkpoint()` | 944 | 53 lines |
| `propagate_memory_summaries_to_checkpoints()` | 999 | 53 lines |
| `_verify_no_loss()` | 708 | 50 lines |

### `comfort.py`

| Function | Start | Size |
|---|---:|---:|
| `_derive()` | 206 | 82 lines |
| `_posture_of()` | 173 | 31 lines |
| `_is_body()` | 137 | 21 lines |
| `_entity_record()` | 123 | 12 lines |
| `_station_of()` | 160 | 11 lines |
| `comfort_level()` | 290 | 8 lines |
| `rest_affording()` | 300 | 7 lines |
| `_tokens()` | 100 | 6 lines |

### `commit.py`

| Function | Start | Size |
|---|---:|---:|
| `prepare_memory_commit()` | 5037 | 1144 lines |
| `prepare_scene_commit()` | 1849 | 393 lines |
| `commit_world_entities()` | 2620 | 283 lines |
| `track_background_presences()` | 3420 | 231 lines |
| `commit_transit_sweep()` | 2291 | 169 lines |
| `_prepare_destruction()` | 699 | 158 lines |
| `update_place_graph()` | 74 | 153 lines |
| `_commit_all_locked()` | 6417 | 144 lines |

### `db.py`

| Function | Start | Size |
|---|---:|---:|
| `init()` | 1507 | 50 lines |
| `conn()` | 1354 | 38 lines |
| `transaction()` | 1394 | 36 lines |
| `_backfill_resource_uids()` | 1489 | 17 lines |
| `qi()` | 1452 | 16 lines |
| `data_version()` | 1431 | 14 lines |
| `parse_scoped_world_key()` | 59 | 13 lines |
| `_execute_retry()` | 1323 | 13 lines |

### `frames.py`

| Function | Start | Size |
|---|---:|---:|
| `is_memory_visible()` | 126 | 82 lines |
| `get_frame()` | 67 | 23 lines |
| `create_frame()` | 98 | 19 lines |
| `is_recognized_in_frame()` | 210 | 11 lines |
| `frame_ordinal()` | 119 | 5 lines |
| `list_frames()` | 92 | 4 lines |

### `gaps.py`

| Function | Start | Size |
|---|---:|---:|
| `_skeleton()` | 144 | 175 lines |
| `last_seen_update()` | 444 | 70 lines |
| `_medium_overlay()` | 325 | 57 lines |
| `gap_for()` | 384 | 54 lines |
| `interim_for()` | 516 | 33 lines |
| `_record()` | 76 | 22 lines |
| `_derived_resolution()` | 106 | 22 lines |
| `_subject_room()` | 130 | 12 lines |

### `greetings.py`

| Function | Start | Size |
|---|---:|---:|
| `start_story()` | 174 | 123 lines |
| `generate_greeting()` | 299 | 58 lines |
| `extract_greeting()` | 96 | 24 lines |
| `_substitute_player_slot()` | 53 | 22 lines |
| `player_handle_for()` | 77 | 17 lines |
| `_strip_greeting_wrapping()` | 359 | 17 lines |
| `_override_narrator()` | 131 | 13 lines |
| `_greeting_record()` | 122 | 7 lines |

### `guest_access.py`

| Function | Start | Size |
|---|---:|---:|
| `redeem_code()` | 232 | 48 lines |
| `verify_host_login()` | 88 | 26 lines |
| `list_grants()` | 330 | 26 lines |
| `create_host_account()` | 63 | 23 lines |
| `verify_guest_token()` | 282 | 19 lines |
| `login_retry_after()` | 203 | 15 lines |
| `revoke_persona_grants()` | 303 | 13 lines |
| `revoke_grant()` | 318 | 10 lines |

### `importers.py`

| Function | Start | Size |
|---|---:|---:|
| `import_lorebook()` | 1329 | 212 lines |
| `_reinterpret_entries()` | 1202 | 126 lines |
| `apply_lorebook_plan()` | 2433 | 124 lines |
| `_lore_gen_entry_batch()` | 2085 | 118 lines |
| `_run_lore_gen_job()` | 2207 | 112 lines |
| `fill_appearance()` | 999 | 93 lines |
| `import_character()` | 536 | 91 lines |
| `_lore_gen_structure()` | 2015 | 66 lines |

### `jobs.py`

| Function | Start | Size |
|---|---:|---:|
| `_run()` | 85 | 18 lines |
| `submit()` | 67 | 16 lines |
| `cancel()` | 119 | 13 lines |
| `_finish()` | 105 | 12 lines |
| `status()` | 143 | 10 lines |
| `is_stale()` | 166 | 10 lines |
| `cancel_chat()` | 134 | 7 lines |
| `reset()` | 178 | 6 lines |

### `living_world.py`

| Function | Start | Size |
|---|---:|---:|
| `mint_consequences()` | 348 | 100 lines |
| `record_obligations()` | 498 | 53 lines |
| `living_world_levels()` | 284 | 33 lines |
| `fired_consequences_at()` | 450 | 28 lines |
| `effective_depth()` | 241 | 27 lines |
| `owed_history()` | 553 | 24 lines |
| `attach_owed_history()` | 579 | 24 lines |
| `normalize_living_world()` | 202 | 20 lines |

### `llm_quality.py`

| Function | Start | Size |
|---|---:|---:|
| `complete_validated_json()` | 89 | 204 lines |
| `_extract_balanced_object()` | 25 | 34 lines |
| `strict_json_parse()` | 61 | 27 lines |

### `logging_utils.py`

| Function | Start | Size |
|---|---:|---:|
| `log_llm_call()` | 91 | 28 lines |
| `measure_step()` | 72 | 18 lines |

### `lore_structure.py`

| Function | Start | Size |
|---|---:|---:|
| `derive_knowledge()` | 195 | 48 lines |
| `parse_structure()` | 78 | 45 lines |
| `clean_title()` | 46 | 16 lines |
| `classify_title()` | 64 | 12 lines |
| `_matches()` | 160 | 12 lines |
| `_place_name()` | 151 | 7 lines |

### `mechanics.py`

| Function | Start | Size |
|---|---:|---:|
| `_fire_due_events()` | 110 | 98 lines |
| `_schedule_new_arrivals()` | 210 | 44 lines |
| `mechanics_sweep()` | 268 | 43 lines |
| `news_latency_seconds()` | 90 | 10 lines |
| `_expire_conditions()` | 256 | 10 lines |
| `stable_event_key()` | 68 | 6 lines |
| `_payload_of()` | 102 | 6 lines |

### `memory.py`

| Function | Start | Size |
|---|---:|---:|
| `build_character_memory_context()` | 2659 | 274 lines |
| `search_memories()` | 1719 | 228 lines |
| `rebuild_embeddings()` | 4482 | 195 lines |
| `rebuild_checkpoint_embeddings()` | 4716 | 124 lines |
| `contrast_memory()` | 1982 | 117 lines |
| `_origin_on_drift()` | 2560 | 97 lines |
| `backfill_memory_summary_windows()` | 3064 | 89 lines |
| `restore_lorebook()` | 3717 | 79 lines |

### `offscreen.py`

| Function | Start | Size |
|---|---:|---:|
| `schedule_profile_ticks()` | 1353 | 113 lines |
| `apply_plan_ops()` | 664 | 110 lines |
| `profile_summary_record()` | 1090 | 99 lines |
| `advance_epoch()` | 909 | 98 lines |
| `advance_reactive_plans()` | 822 | 85 lines |
| `_normalize_plan_stages()` | 595 | 67 lines |
| `stochastic_ticks()` | 327 | 64 lines |
| `full_agent_candidates()` | 1235 | 55 lines |

### `outofband.py`

| Function | Start | Size |
|---|---:|---:|
| `stopped()` | 121 | 8 lines |

### `paradox.py`

| Function | Start | Size |
|---|---:|---:|
| `check_and_apply_paradox()` | 440 | 50 lines |
| `_apply_toll()` | 278 | 48 lines |
| `_trigger_paradox()` | 363 | 30 lines |
| `_advance_paradox()` | 395 | 30 lines |
| `_apply_hazard_stage()` | 248 | 28 lines |
| `add_fixed_point()` | 123 | 19 lines |
| `get_all_paradoxes()` | 166 | 17 lines |
| `_apply_warden_stage()` | 328 | 17 lines |

### `pipeline_trace.py`

| Function | Start | Size |
|---|---:|---:|
| `validate_pipeline_trace()` | 174 | 128 lines |
| `export_pipeline_trace()` | 80 | 92 lines |
| `replay_pipeline_trace()` | 304 | 68 lines |
| `write_pipeline_trace()` | 389 | 25 lines |
| `_canonical_json()` | 45 | 14 lines |
| `load_pipeline_trace()` | 379 | 8 lines |
| `_decode_variant_content()` | 71 | 7 lines |
| `_trace_digest()` | 65 | 4 lines |

### `place_purpose.py`

| Function | Start | Size |
|---|---:|---:|
| `mirror_told_affords()` | 344 | 91 lines |
| `witness_affords()` | 268 | 68 lines |
| `here_affords()` | 216 | 45 lines |
| `place_options()` | 476 | 43 lines |
| `_walked_hops()` | 454 | 20 lines |
| `felt_needs()` | 437 | 15 lines |
| `assumed_affords()` | 202 | 12 lines |
| `affords_here()` | 521 | 12 lines |

### `prompt_cache.py`

| Function | Start | Size |
|---|---:|---:|
| `add_cache_breakpoint()` | 15 | 37 lines |
| `estimate_cacheable_tokens()` | 66 | 14 lines |
| `supports_prompt_caching()` | 7 | 7 lines |

### `prompts.py`

| Function | Start | Size |
|---|---:|---:|
| `get_prompt()` | 4108 | 10 lines |
| `presets()` | 4099 | 2 lines |
| `active_preset()` | 4102 | 2 lines |
| `nsfw_enabled()` | 4105 | 2 lines |

### `providers.py`

| Function | Start | Size |
|---|---:|---:|
| `_chat_complete_once()` | 1404 | 206 lines |
| `async chat_complete_async()` | 1611 | 88 lines |
| `chat_complete()` | 1250 | 83 lines |
| `async _chat_complete_async_once()` | 1700 | 78 lines |
| `_sse_openai()` | 1144 | 62 lines |
| `async _sse_openai_async()` | 1779 | 53 lines |
| `resolve_role_candidates()` | 989 | 52 lines |
| `list_models()` | 1914 | 51 lines |

### `psychology_runtime.py`

| Function | Start | Size |
|---|---:|---:|
| `resolve_hedonic()` | 96 | 138 lines |
| `resolve_stress()` | 236 | 89 lines |
| `apply_belief_updates()` | 335 | 57 lines |
| `cognitive_absorption()` | 458 | 45 lines |
| `apply_association_updates()` | 394 | 44 lines |
| `elapsed_psych_units()` | 79 | 15 lines |
| `_float()` | 11 | 6 lines |
| `_authored_beliefs()` | 327 | 6 lines |

### `routines.py`

| Function | Start | Size |
|---|---:|---:|
| `residue_for()` | 156 | 45 lines |
| `entropy_facts()` | 128 | 26 lines |
| `routine_band()` | 84 | 22 lines |
| `occupancy_fact()` | 108 | 18 lines |
| `_roll()` | 73 | 9 lines |

### `scene.py`

| Function | Start | Size |
|---|---:|---:|
| `recent_events_for_observer()` | 750 | 59 lines |
| `director_context()` | 810 | 53 lines |
| `awareness_conditions()` | 471 | 47 lines |
| `private_knowledge_for()` | 1381 | 44 lines |
| `_seed_scene_initial_attire()` | 85 | 31 lines |
| `active_cast()` | 161 | 31 lines |
| `active_disguises()` | 363 | 31 lines |
| `normalize_style_guide()` | 1289 | 31 lines |

### `schemas.py`

| Function | Start | Size |
|---|---:|---:|
| `preprocess_llm_output()` | 2967 | 245 lines |
| `_lenient_coerce()` | 517 | 159 lines |
| `semantic_output_errors()` | 3634 | 113 lines |
| `validate_llm_output_strict()` | 3809 | 102 lines |
| `_coerce_conditions()` | 2738 | 50 lines |
| `_declared()` | 357 | 48 lines |
| `_coerce_station_table()` | 49 | 41 lines |
| `_coerce_evidence_refs()` | 1852 | 41 lines |

### `spatial.py`

| Function | Start | Size |
|---|---:|---:|
| `merge_scene_with_diff()` | 6018 | 296 lines |
| `apply_contact_ops()` | 3489 | 254 lines |
| `sprint_reach()` | 4679 | 175 lines |
| `apply_transit_dock_edges()` | 5392 | 165 lines |
| `contacts_from_entity_state()` | 2804 | 137 lines |
| `hear_level()` | 976 | 120 lines |
| `visible_adjacent_rooms()` | 4924 | 117 lines |
| `contact_sensation()` | 4273 | 115 lines |

### `spatial_frames.py`

| Function | Start | Size |
|---|---:|---:|
| `infer_threshold_crossings()` | 369 | 96 lines |
| `perform_split()` | 705 | 94 lines |
| `infer_companion_carry()` | 233 | 92 lines |
| `infer_vehicle_zones()` | 146 | 85 lines |
| `infer_focus()` | 467 | 72 lines |
| `perform_merge()` | 877 | 69 lines |
| `infer_facing()` | 541 | 59 lines |
| `detect_split()` | 659 | 44 lines |

### `spatial_orientation.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_scene_bearings()` | 135 | 112 lines |
| `travel_bearing()` | 115 | 18 lines |
| `relative_bearing()` | 79 | 11 lines |
| `lateral_of()` | 92 | 11 lines |
| `normalize_bearing()` | 47 | 9 lines |
| `normalize_vertical()` | 65 | 8 lines |
| `_find_edge()` | 105 | 8 lines |
| `opposite_bearing()` | 58 | 2 lines |

### `subjects.py`

| Function | Start | Size |
|---|---:|---:|
| `_resolve_room()` | 248 | 47 lines |
| `resolve_subject()` | 405 | 45 lines |
| `_resolve_character()` | 166 | 32 lines |
| `_lore_matches()` | 301 | 29 lines |
| `_resolve_from_lore()` | 332 | 29 lines |
| `_registry_room_matches()` | 221 | 25 lines |
| `_cast_matches()` | 97 | 22 lines |
| `_presence_reason()` | 142 | 22 lines |

### `survival.py`

| Function | Start | Size |
|---|---:|---:|
| `tick_vitals()` | 201 | 61 lines |
| `apply_vitals_diff()` | 264 | 32 lines |
| `seed_vitals()` | 121 | 23 lines |
| `is_sealed_in()` | 176 | 23 lines |
| `vitals_facts()` | 298 | 23 lines |
| `vital_label()` | 160 | 14 lines |
| `vitals_of()` | 146 | 12 lines |
| `_clamp()` | 110 | 5 lines |

### `theory_of_mind.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_mind_model_updates()` | 322 | 158 lines |
| `select_active_hypotheses()` | 611 | 62 lines |
| `rekey_place_claims()` | 270 | 50 lines |
| `claim_similarity()` | 213 | 35 lines |
| `mind_models_for_payload()` | 481 | 33 lines |
| `belief_credence()` | 516 | 33 lines |
| `cap_mind_model_updates()` | 99 | 19 lines |
| `due_for_reappraisal()` | 688 | 16 lines |

### `updates.py`

| Function | Start | Size |
|---|---:|---:|
| `check_updates()` | 290 | 53 lines |
| `install_updates()` | 345 | 50 lines |
| `_git()` | 75 | 41 lines |
| `_github_releases()` | 252 | 36 lines |
| `_upstream_ref()` | 139 | 24 lines |
| `_remote_tip()` | 175 | 15 lines |
| `_is_git_repo()` | 118 | 14 lines |
| `_repo_slug()` | 225 | 13 lines |

### `weather.py`

| Function | Start | Size |
|---|---:|---:|
| `weather_for_room()` | 446 | 71 lines |
| `normalize_weather()` | 206 | 69 lines |
| `weather_depth()` | 373 | 57 lines |
| `weather_words()` | 549 | 54 lines |
| `advance_weather()` | 656 | 43 lines |
| `ground_after()` | 753 | 38 lines |
| `room_exposure()` | 277 | 30 lines |
| `_resolve()` | 173 | 27 lines |

## FastAPI routes

| Method | Path | Handler | Source |
|---|---|---|---|
| GET | `/` | `index()` | `app.py:198` |
| PUT | `/api/active_preset` | `set_active()` | `app.py:1221` |
| PUT | `/api/agent_models` | `put_agent_models()` | `app.py:1002` |
| PUT | `/api/ambience` | `put_ambience()` | `app.py:1115` |
| GET | `/api/ambience/library` | `ambience_library()` | `app.py:4748` |
| GET | `/api/ambience/search` | `ambience_search()` | `app.py:4727` |
| PUT | `/api/attire_beneath` | `set_attire_beneath()` | `app.py:1235` |
| POST | `/api/auth/login` | `auth_login()` | `auth_routes.py:108` |
| POST | `/api/auth/logout` | `auth_logout()` | `auth_routes.py:171` |
| POST | `/api/auth/setup` | `auth_setup()` | `auth_routes.py:69` |
| GET | `/api/auth/status` | `auth_status()` | `auth_routes.py:59` |
| GET | `/api/auto_promote` | `get_auto_promote()` | `app.py:2549` |
| PUT | `/api/auto_promote` | `set_auto_promote()` | `app.py:2553` |
| PUT | `/api/backdrops` | `put_backdrops()` | `app.py:1105` |
| GET | `/api/bootstrap` | `bootstrap()` | `app.py:942` |
| POST | `/api/characters` | `char_create()` | `app.py:1678` |
| POST | `/api/characters/generate` | `char_generate()` | `app.py:1668` |
| POST | `/api/characters/import` | `char_import()` | `app.py:1699` |
| DELETE | `/api/characters/{cid}` | `char_del()` | `app.py:1810` |
| PUT | `/api/characters/{cid}` | `char_edit()` | `app.py:1801` |
| GET | `/api/characters/{cid}/export` | `char_export()` | `app.py:1793` |
| POST | `/api/characters/{cid}/fill_appearance` | `char_fill_appearance()` | `app.py:1783` |
| POST | `/api/characters/{cid}/fill_psychology` | `char_fill_psychology()` | `app.py:1757` |
| POST | `/api/characters/{cid}/generate_greeting` | `char_generate_greeting()` | `app.py:1742` |
| POST | `/api/characters/{cid}/recover_greetings` | `char_recover_greetings()` | `app.py:1732` |
| POST | `/api/characters/{cid}/start` | `character_start_story()` | `app.py:1714` |
| POST | `/api/chats` | `chat_new()` | `app.py:2154` |
| POST | `/api/chats/import` | `import_chat()` | `chat_archive.py:174` |
| DELETE | `/api/chats/{cid}` | `chat_del()` | `app.py:2256` |
| GET | `/api/chats/{cid}` | `chat_get()` | `app.py:2286` |
| PUT | `/api/chats/{cid}` | `chat_edit()` | `app.py:2160` |
| POST | `/api/chats/{cid}/abort` | `chat_abort()` | `app.py:3686` |
| GET | `/api/chats/{cid}/ambience/oneshot/{name}` | `ambience_oneshot()` | `app.py:4757` |
| DELETE | `/api/chats/{cid}/ambience/pin` | `ambience_pin_delete()` | `app.py:4805` |
| PUT | `/api/chats/{cid}/ambience/pin` | `ambience_pin_put()` | `app.py:4786` |
| GET | `/api/chats/{cid}/ambience/pins` | `ambience_pins_get()` | `app.py:4781` |
| GET | `/api/chats/{cid}/ambience/{signature}.audio` | `ambience_audio()` | `app.py:4711` |
| GET | `/api/chats/{cid}/attire` | `attire_get()` | `app.py:3171` |
| PUT | `/api/chats/{cid}/attire` | `attire_put()` | `app.py:3178` |
| GET | `/api/chats/{cid}/backdrop/{signature}.png` | `backdrop_image()` | `app.py:4558` |
| GET | `/api/chats/{cid}/background_config` | `bg_cfg_get()` | `app.py:3312` |
| PUT | `/api/chats/{cid}/background_config` | `bg_cfg_put()` | `app.py:3316` |
| POST | `/api/chats/{cid}/characters` | `chat_add_char()` | `app.py:2457` |
| DELETE | `/api/chats/{cid}/characters/{ch}` | `chat_del_char()` | `app.py:2818` |
| PUT | `/api/chats/{cid}/characters/{ch}/card` | `chat_char_card_put()` | `app.py:2828` |
| GET | `/api/chats/{cid}/characters/{ch}/memories` | `mem_list()` | `app.py:3442` |
| POST | `/api/chats/{cid}/characters/{ch}/memories` | `mem_add()` | `app.py:3573` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/backfill` | `mem_backfill()` | `app.py:3544` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/consolidate` | `mem_consolidate()` | `app.py:3533` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/coverage` | `mem_coverage()` | `app.py:3564` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/export` | `mem_export()` | `app.py:3488` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/import` | `mem_import()` | `app.py:3499` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/search` | `mem_search()` | `app.py:3463` |
| GET | `/api/chats/{cid}/characters/{ch}/memory-context` | `memory_context_preview()` | `app.py:3509` |
| PUT | `/api/chats/{cid}/characters/{ch}/position` | `chat_char_position_put()` | `app.py:3034` |
| GET | `/api/chats/{cid}/characters/{ch}/private_history` | `ph_get()` | `app.py:3094` |
| PUT | `/api/chats/{cid}/characters/{ch}/private_history` | `ph_put()` | `app.py:3104` |
| GET | `/api/chats/{cid}/characters/{ch}/relationships` | `relationships_get()` | `app.py:3522` |
| GET | `/api/chats/{cid}/dialogue_config` | `dlg_get()` | `app.py:3213` |
| PUT | `/api/chats/{cid}/dialogue_config` | `dlg_put()` | `app.py:3230` |
| GET | `/api/chats/{cid}/dramatic_irony` | `get_dramatic_irony_feed()` | `app.py:2511` |
| GET | `/api/chats/{cid}/export` | `export_chat()` | `chat_archive.py:168` |
| GET | `/api/chats/{cid}/fixed_points` | `fixed_points_list()` | `app.py:3388` |
| POST | `/api/chats/{cid}/fixed_points` | `fixed_points_create()` | `app.py:3398` |
| DELETE | `/api/chats/{cid}/fixed_points/{anchor_id}` | `fixed_points_delete()` | `app.py:3420` |
| GET | `/api/chats/{cid}/frames` | `frames_list()` | `app.py:3342` |
| POST | `/api/chats/{cid}/frames` | `frames_create()` | `app.py:3346` |
| GET | `/api/chats/{cid}/guest_invites` | `list_guest_invites()` | `app.py:2697` |
| POST | `/api/chats/{cid}/guest_invites` | `create_guest_invite()` | `app.py:2679` |
| DELETE | `/api/chats/{cid}/guest_invites/{gid}` | `revoke_guest_invite()` | `app.py:2701` |
| GET | `/api/chats/{cid}/living_world` | `living_world_get()` | `app.py:3277` |
| PUT | `/api/chats/{cid}/living_world` | `living_world_put()` | `app.py:3300` |
| DELETE | `/api/chats/{cid}/lorebook` | `detach_lore()` | `app.py:2247` |
| POST | `/api/chats/{cid}/lorebook` | `bind_lore()` | `app.py:2231` |
| GET | `/api/chats/{cid}/lorebooks` | `chat_lorebooks_owned()` | `app.py:1320` |
| POST | `/api/chats/{cid}/lorebooks` | `attach_lore()` | `app.py:2191` |
| DELETE | `/api/chats/{cid}/lorebooks/{lid}` | `detach_book()` | `app.py:2216` |
| GET | `/api/chats/{cid}/paradox_policy` | `paradox_policy_get()` | `app.py:3373` |
| PUT | `/api/chats/{cid}/paradox_policy` | `paradox_policy_put()` | `app.py:3377` |
| GET | `/api/chats/{cid}/persona_private_history` | `pph_get()` | `app.py:3113` |
| PUT | `/api/chats/{cid}/persona_private_history` | `pph_put()` | `app.py:3126` |
| GET | `/api/chats/{cid}/personas` | `chat_list_extra_personas()` | `app.py:2558` |
| POST | `/api/chats/{cid}/personas` | `chat_add_persona()` | `app.py:2603` |
| DELETE | `/api/chats/{cid}/personas/{pid}` | `chat_del_persona()` | `app.py:2627` |
| PUT | `/api/chats/{cid}/personas/{pid}/station` | `chat_persona_station()` | `app.py:2568` |
| GET | `/api/chats/{cid}/positions` | `chat_positions_get()` | `app.py:2970` |
| GET | `/api/chats/{cid}/promises` | `get_promise_ledger()` | `app.py:2515` |
| GET | `/api/chats/{cid}/promotable` | `list_promotable_presences()` | `app.py:2507` |
| POST | `/api/chats/{cid}/promotions/confirm` | `confirm_promotion()` | `app.py:2532` |
| POST | `/api/chats/{cid}/promotions/draft` | `draft_promotion()` | `app.py:2519` |
| GET | `/api/chats/{cid}/style_guide` | `style_guide_get()` | `app.py:3196` |
| PUT | `/api/chats/{cid}/style_guide` | `style_guide_put()` | `app.py:3202` |
| GET | `/api/chats/{cid}/survival` | `survival_get()` | `app.py:2885` |
| PUT | `/api/chats/{cid}/survival` | `survival_put()` | `app.py:2890` |
| POST | `/api/chats/{cid}/turns` | `turn_new()` | `app.py:3626` |
| POST | `/api/chats/{cid}/turns/{idx}/player_input` | `submit_extra_player_input()` | `app.py:2641` |
| GET | `/api/chats/{cid}/vitals` | `chat_vitals_get()` | `app.py:2937` |
| GET | `/api/chats/{cid}/world` | `world_get()` | `app.py:3131` |
| PUT | `/api/chats/{cid}/world` | `world_put()` | `app.py:3135` |
| PUT | `/api/exemplars` | `put_exemplars()` | `app.py:1074` |
| POST | `/api/guest/input` | `guest_input()` | `app.py:2793` |
| GET | `/api/guest/state` | `guest_state()` | `app.py:2725` |
| PUT | `/api/image_model` | `put_image_model()` | `app.py:1052` |
| POST | `/api/join` | `join_with_code()` | `app.py:2707` |
| DELETE | `/api/lore_entries/{eid}` | `lore_entry_delete()` | `app.py:2147` |
| PUT | `/api/lore_entries/{eid}` | `lore_entry_edit()` | `app.py:2075` |
| DELETE | `/api/lore_gen_jobs/{job_id}` | `lorebook_generate_discard()` | `app.py:1475` |
| POST | `/api/lore_gen_jobs/{job_id}/resume` | `lorebook_generate_resume()` | `app.py:1457` |
| DELETE | `/api/lorebook_links/{link_id}` | `lorebook_link_delete()` | `app.py:1416` |
| PUT | `/api/lorebook_links/{link_id}` | `lorebook_link_update()` | `app.py:1402` |
| POST | `/api/lorebooks` | `lore_create()` | `app.py:1905` |
| POST | `/api/lorebooks/import` | `lore_import()` | `app.py:1511` |
| DELETE | `/api/lorebooks/{lid}` | `lore_delete()` | `app.py:1997` |
| GET | `/api/lorebooks/{lid}` | `lore_get()` | `app.py:1885` |
| PUT | `/api/lorebooks/{lid}` | `lore_edit()` | `app.py:1927` |
| POST | `/api/lorebooks/{lid}/apply_plan` | `lorebook_apply_plan()` | `app.py:1484` |
| POST | `/api/lorebooks/{lid}/entries` | `lore_entry_create()` | `app.py:2046` |
| GET | `/api/lorebooks/{lid}/export` | `lore_export()` | `app.py:2003` |
| POST | `/api/lorebooks/{lid}/generate` | `lore_generate()` | `app.py:2032` |
| GET | `/api/lorebooks/{lid}/generate_job` | `lorebook_generate_job()` | `app.py:1446` |
| POST | `/api/lorebooks/{lid}/generate_plan` | `lorebook_generate_plan()` | `app.py:1421` |
| GET | `/api/lorebooks/{lid}/links` | `lorebook_links_get()` | `app.py:1375` |
| POST | `/api/lorebooks/{lid}/links` | `lorebook_link_create()` | `app.py:1380` |
| POST | `/api/lorebooks/{lid}/move` | `lorebook_move()` | `app.py:1302` |
| POST | `/api/lorebooks/{lid}/reinterpret` | `lore_reinterpret_route()` | `app.py:2020` |
| POST | `/api/lorebooks/{lid}/reorder` | `lorebook_reorder()` | `app.py:1311` |
| GET | `/api/maintenance/checkpoints` | `maintenance_checkpoints()` | `app.py:1258` |
| POST | `/api/maintenance/checkpoints/compact` | `maintenance_compact()` | `app.py:1274` |
| PUT | `/api/max_output_tokens` | `put_max_output_tokens()` | `app.py:1196` |
| DELETE | `/api/memories/{mid}` | `mem_del()` | `app.py:3620` |
| PUT | `/api/memories/{mid}` | `mem_edit()` | `app.py:3599` |
| GET | `/api/memory/embeddings` | `memory_embeddings_status()` | `app.py:1025` |
| POST | `/api/memory/embeddings/rebuild` | `memory_embeddings_rebuild()` | `app.py:1040` |
| GET | `/api/nsfw` | `get_nsfw()` | `app.py:1226` |
| PUT | `/api/nsfw` | `set_nsfw()` | `app.py:1230` |
| GET | `/api/openrouter/endpoints` | `get_openrouter_endpoints()` | `app.py:1159` |
| PUT | `/api/openrouter_routing` | `put_openrouter_routing()` | `app.py:1145` |
| POST | `/api/personas` | `persona_create()` | `app.py:1827` |
| POST | `/api/personas/generate` | `persona_generate()` | `app.py:1817` |
| POST | `/api/personas/import` | `persona_import()` | `app.py:1847` |
| DELETE | `/api/personas/{pid}` | `persona_del()` | `app.py:1879` |
| PUT | `/api/personas/{pid}` | `persona_edit()` | `app.py:1870` |
| GET | `/api/personas/{pid}/export` | `persona_export()` | `app.py:1861` |
| POST | `/api/personas/{pid}/fill_appearance` | `persona_fill_appearance()` | `app.py:1788` |
| PUT | `/api/prompt_presets` | `save_preset()` | `app.py:1205` |
| DELETE | `/api/prompt_presets/{name}` | `del_preset()` | `app.py:1212` |
| POST | `/api/providers` | `add_provider()` | `app.py:1567` |
| DELETE | `/api/providers/{pid}` | `del_provider()` | `app.py:1646` |
| PUT | `/api/providers/{pid}` | `put_provider()` | `app.py:1574` |
| GET | `/api/providers/{pid}/image_models` | `image_models()` | `app.py:1658` |
| GET | `/api/providers/{pid}/models` | `models()` | `app.py:1651` |
| PUT | `/api/providers/{pid}/prompt_cache` | `put_provider_prompt_cache()` | `app.py:1601` |
| PUT | `/api/reasoning_effort` | `put_reasoning_effort()` | `app.py:1171` |
| POST | `/api/steps/{sid}/activate` | `step_activate()` | `app.py:4389` |
| POST | `/api/steps/{sid}/edit` | `step_edit()` | `app.py:4379` |
| POST | `/api/steps/{sid}/reroll` | `step_reroll()` | `app.py:4332` |
| DELETE | `/api/turns/{tid}` | `turn_del()` | `app.py:4402` |
| GET | `/api/turns/{tid}/ambience` | `turn_ambience()` | `app.py:4661` |
| POST | `/api/turns/{tid}/ambience` | `turn_ambience_resolve()` | `app.py:4678` |
| GET | `/api/turns/{tid}/backdrop` | `turn_backdrop()` | `app.py:4483` |
| POST | `/api/turns/{tid}/backdrop` | `turn_backdrop_generate()` | `app.py:4531` |
| POST | `/api/turns/{tid}/branch` | `turn_branch()` | `app.py:3690` |
| PUT | `/api/turns/{tid}/input` | `edit_input()` | `app.py:4082` |
| GET | `/api/turns/{tid}/narration` | `turn_narration_variants()` | `app.py:4149` |
| POST | `/api/turns/{tid}/narration` | `turn_narration_select()` | `app.py:4170` |
| GET | `/api/turns/{tid}/pipeline` | `pipeline_get()` | `app.py:4194` |
| PUT | `/api/turns/{tid}/prose` | `edit_prose()` | `app.py:4097` |
| POST | `/api/turns/{tid}/reroll` | `turn_reroll()` | `app.py:4263` |
| POST | `/api/turns/{tid}/rerun` | `turn_rerun()` | `app.py:4273` |
| POST | `/api/turns/{tid}/resume` | `turn_resume()` | `app.py:4300` |
| GET | `/api/updates/check` | `updates_check()` | `app.py:1250` |
| POST | `/api/updates/install` | `updates_install()` | `app.py:1254` |
| GET | `/guest` | `guest_page()` | `app.py:190` |
| GET | `/login` | `login_page()` | `app.py:202` |

## Database tables

| Table | Columns |
|---|---|
| `schema_meta` | `key` |
| `providers` | `id`, `name`, `kind`, `base_url`, `api_key`, `enabled` |
| `settings` | `key`, `value` |
| `characters` | `id`, `name`, `sheet`, `source`, `created`, `resource_uid` |
| `personas` | `id`, `name`, `sheet`, `source`, `resource_uid` |
| `lorebooks` | `id`, `name`, `chat_id`, `origin_id`, `book_type`, `summary`, `resource_uid`, `parent_id`, `scope_world_id`, `scope_location_id`, `inheritance_mode`, `sort_order`, `anchor_entity_id`, `--`, `--`, `--`, `--`, `retired_turn_id` |
| `lorebook_links` | `id`, `source_book_id`, `target_book_id`, `relation_type`, `label`, `notes`, `bidirectional`, `follow_for_retrieval`, `weight`, `sort_order`, `created` |
| `chat_lorebooks` | `chat_id`, `lorebook_id`, `origin_id`, `enabled` |
| `lore_entries` | `id`, `lorebook_id`, `keys`, `content`, `category`, `canon_locked`, `turn_added`, `embedding`, `title`, `knowledge_tag`, `knowledge_range`, `knowledge_locations`, `entry_uid`, `importance`, `aliases`, `scope`, `relations`, `source_notes`, `--`, `--`, `--`, `--`, `embedding_model`, `embedding_dim` |
| `lore_gen_jobs` | `id`, `lorebook_id`, `--`, `status`, `--`, `stage`, `--`, `--`, `--`, `params`, `--`, `--`, `plan`, `--`, `progress`, `error`, `--`, `--`, `--`, `owner`, `attempts`, `created`, `updated` |
| `chats` | `id`, `name`, `persona_id`, `lorebook_id`, `scenario`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `branched_from`, `created` |
| `chat_chars` | `chat_id`, `char_id`, `status`, `state`, `--`, `--`, `sheet` |
| `chat_char_frames` | `chat_id`, `char_id`, `frame_id`, `status`, `state` |
| `chat_personas` | `chat_id`, `persona_id`, `status`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `frame_id` |
| `turn_player_inputs` | `id`, `chat_id`, `turn_idx`, `persona_id`, `input`, `created` |
| `guest_grants` | `id`, `chat_id`, `persona_id`, `code_hash`, `code_expires`, `redeemed_at`, `token_hash`, `token_expires`, `revoked`, `created` |
| `host_sessions` | `id`, `token_hash`, `created`, `expires` |
| `frames` | `id`, `chat_id`, `label`, `ordinal`, `kind`, `travelers`, `nonexistent_cast`, `created`, `parent_frame_id`, `split_turn_idx`, `merged_turn_idx` |
| `turns` | `id`, `chat_id`, `idx`, `player_input`, `created`, `frame_id` |
| `steps` | `id`, `turn_id`, `key`, `label`, `ord`, `stale` |
| `variants` | `id`, `step_id`, `content`, `created`, `active`, `reasoning` |
| `memories` | `id`, `chat_id`, `char_id`, `turn_id`, `turn_idx`, `kind`, `category`, `provenance`, `salience`, `content`, `gist`, `key_phrases`, `entities`, `location`, `emotional_context`, `valence`, `arousal`, `--`, `--`, `--`, `encoding_valence`, `encoding_arousal`, `confidence`, `access_count`, `last_accessed`, `embedding`, `cue_embedding`, `embedding_model`, `embedding_dim`, `archived`, `event_key`, `frame_id`, `--`, `--`, `--`, `--`, `importance`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `disputed` |
| `memory_vectors` | `vkey`, `embedding`, `cue_embedding`, `embedding_model`, `embedding_dim`, `created` |
| `memory_summaries` | `id`, `chat_id`, `char_id`, `scope`, `start_turn_idx`, `end_turn_idx`, `summary`, `key_phrases`, `unresolved_threads`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `support`, `embedding`, `embedding_model`, `embedding_dim`, `updated`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--` |
| `events` | `id`, `chat_id`, `turn_id`, `content` |
| `world` | `chat_id`, `key`, `value` |
| `checkpoints` | `id`, `chat_id`, `turn_idx`, `blob`, `created` |
| `world_events` | `event_id`, `chat_id`, `turn_id`, `frame_id`, `occurred_at`, `duration_seconds`, `kind`, `location_id`, `payload`, `seed`, `committed` |
| `world_entities` | `entity_id`, `chat_id`, `kind`, `subtype`, `name`, `payload`, `created_turn_id`, `retired_turn_id` |
| `world_placements` | `chat_id`, `subject_id`, `relation`, `container_id`, `detail` |
| `world_conditions` | `condition_id`, `chat_id`, `subject_id`, `kind`, `started_at`, `expires_at`, `next_tick`, `payload`, `active` |
| `scheduled_events` | `event_id`, `chat_id`, `due_at`, `kind`, `location_id`, `payload`, `seed`, `status` |
| `room_registry` | `chat_id`, `room_uid`, `owning_book_id`, `parent_entity`, `name`, `aliases`, `payload`, `created_turn_id`, `retired_turn_id` |
| `fiction_worlds` | `world_id`, `chat_id`, `parent_world_id`, `name`, `kind`, `payload`, `created_turn_id`, `retired_turn_id` |
| `fiction_locations` | `location_id`, `chat_id`, `world_id`, `parent_location_id`, `kind`, `name`, `payload` |
| `transit_edges` | `edge_id`, `chat_id`, `from_world_id`, `from_location_id`, `to_world_id`, `to_location_id`, `kind`, `payload` |

## Frontend JavaScript

### `static/js/ambience.js` (982 lines)

Sections: Room ambience (`:2`); seamless looping (`:214`); one-shots (`:689`); the ambience panel (`:738`); the mix (`:756`).

Declared functions: `ambienceStored()`, `ambienceElement()`, `entryAudios()`, `ambiencePlayers()`, `applyAmbienceMute()`, `setAmbienceVolume()`, `ambienceLevel()`, `setLayerGain()`, `toggleAmbienceMute()`, `ambienceFadeMix()`, `armSeamlessLoop()`, `crossLoop()`, `retireEntries()`, `stopAmbience()`, `playAmbience()`, `armAmbienceUnlock()`, `ambienceWorking()`, `awaitAmbience()`, `resolveAmbience()`, `ambienceForTurn()`, `rerollAmbience()`, `ambienceOnVisibleTurn()`, `ambienceResetForRender()`, `updateAmbienceBtn()`, `playAmbienceOneshot()`, `ambienceCandidateRow()`, `ambienceLayerRow()`, `ambienceMixPanel()`, `openAmbiencePanel()`, `toggleAmbience()`, `syncAmbience()`.

### `static/js/app.js` (934 lines)

Sections: Boot & sidebar (`:1`); New chat wizard (`:218`); NSFW (`:661`); Composer (`:689`); Init (`:767`); Embedding reconciler progress (`:810`).

Declared functions: `boot()`, `renderSide()`, `renderChatSidebar()`, `newChatWizard()`, `renderWizardChoice()`, `wizardState()`, `wizardFromScratch()`, `renderWizardPersona()`, `renderWizardCharacters()`, `renderWizardScenario()`, `runWizard()`, `renderCharacterSidebar()`, `renderPersonaSidebar()`, `renderLegacyLoreSidebar()`, `updateNSFWBtn()`, `toggleNSFW()`, `resizeComposer()`, `erCard()`, `erDismiss()`, `erPoll()`, `erWatch()`, `erOfferRebuild()`.

### `static/js/backdrops.js` (422 lines)

Sections: Scene backdrops (`:2`).

Declared functions: `backdropLayers()`, `backdropLuminance()`, `applyBackdropContrast()`, `releaseBackdropLayer()`, `clearBackdrop()`, `showBackdrop()`, `backdropWorking()`, `awaitBackdrop()`, `generateBackdrop()`, `backdropForTurn()`, `backdropOnVisibleTurn()`, `backdropResetForRender()`, `updateBackdropBtn()`, `toggleBackdrops()`, `syncBackdrops()`.

### `static/js/chat.js` (2338 lines)

Sections: The turn being read (`:1`); Flipping between rerolls of the newest beat (`:593`); Pipeline drawer: reading a step through a lens (`:891`); Pipeline drawer (`:1084`); Relationship viewer (`:1420`); Memory browser (`:1492`); Private history (`:2280`).

Declared functions: `observeVisibleTurn()`, `openChat()`, `renderFrameBar()`, `switchFrame()`, `updateChatScopedButtons()`, `renderChat()`, `branchTurn()`, `editTurnInput()`, `editTurnProse()`, `liveReset()`, `friendlyPhase()`, `turnStatusStart()`, `turnStatusSet()`, `turnStatusStop()`, `_streamOn()`, `liveFlush()`, `liveAppend()`, `liveStep()`, `handleEvt()`, `_mountRerollNav()`, `_paintRerollCount()`, `showRerollVariant()`, `abortActiveRun()`, `runStream()`, `confirmCheckpointRestore()`, `runReroll()`, `rerollTurn()`, `exportChat()`, `importChatModal()`, `perceiverViews()`, `loopMindIds()`, `stepLenses()`, `perceiverLabel()`, `facetBadge()`, `lensLabel()`, `renderLensBar()`, `lensSlice()`, `perceiverSlice()`, `mindSlice()`, `keySlice()`, `renderEngineNotes()`, `openPipeline()`, `relMeter()`, `relationshipModal()`, `memModal()`, `exportCharacterMemories()`, `importCharacterMemoriesModal()`, `memQS()`, `memCharId()`, `loadMemoryBrowse()`, `getMemUI()`, `renderMemorySummary()`, `sortedMems()`, `renderMemoryList()`, `memoryCard()`, `fieldWrap()`, `reloadMemView()`, `runMemorySearch()`, `showNewMemoryForm()`, `checkMemoryCoverage()`, `backfillMemoryEras()`, `consolidateMemories()`, `previewMemoryContext()`, `chatPH()`, `personaPH()`.

### `static/js/chime.js` (179 lines)

Sections: Turn-completion chime (`:2`); Which other waits are worth a chime (`:110`).

Declared functions: `chimeContext()`, `chimeArm()`, `chimePlay()`, `chimeWatches()`, `chimeWorkFinished()`, `chimeSetMuted()`, `toggleChimeMute()`, `updateChimeBtn()`.

### `static/js/components.js` (925 lines)

Sections: Modal (`:18`); Book covers (`:34`); confirm()/prompt() replacements (`:147`); Toasts (`:269`); Background tasks (`:297`); Form helpers (`:383`); Model picker (`:786`).

Declared functions: `el()`, `coverOfRow()`, `coverOfTitle()`, `modal()`, `modalOwnership()`, `closeModal()`, `closeAllModals()`, `_confirmOverlay()`, `confirmModal()`, `promptModal()`, `promptModalWithToggle()`, `toastHost()`, `toast()`, `renderActivity()`, `elapsedLabel()`, `activityTicking()`, `backgroundTask()`, `buttonTask()`, `loadingBlock()`, `emptyState()`, `fText()`, `fArea()`, `fSelect()`, `fNum()`, `fLineList()`, `fStrList()`, `fCoveragePicker()`, `fAttireGarments()`, `fList()`, `fAbilities()`, `fTraits()`, `fValues()`, `fBeliefs()`, `fCopingStrategies()`, `fAssociations()`, `fGoals()`, `fSenses()`, `fLatent()`, `fPronouns()`, `phEditor()`, `fetchModels()`, `fetchImageModels()`, `modelCombobox()`, `emitChange()`, `load()`, `showDD()`.

### `static/js/editors.js` (924 lines)

Sections: Background-character promotion (`:683`); Import (file upload) (`:732`); Generate (`:803`); Lorebook generate (`:821`); Lorebooks (`:838`); Export (`:912`).

Declared functions: `appearanceFillButton()`, `defaultCharacterSheet()`, `greetingCarousel()`, `quickStartModal()`, `charEditor()`, `personaEditor()`, `promotionReviewModal()`, `promoteBackgroundPresence()`, `importModal()`, `generateModal()`, `generateLoreModal()`, `loreModal()`, `exportCharacter()`, `exportPersona()`, `exportLorebook()`.

### `static/js/lorebooks.js` (3609 lines)

Sections: Library sidebar (`:241`); Data loading (`:448`); Workspace (`:545`); Book metadata and tree operations (`:1152`); Entry editor (`:1611`); Lorebook relationships (`:2356`); Advanced generator (`:2807`); Interrupted-generation recovery (`:3027`).

Declared functions: `loreBookTypeIcon()`, `loreLinkTypes()`, `normalizeLoreBook()`, `loreOwnershipKey()`, `loreBooksByParent()`, `loreBookMatches()`, `loreVisibleIds()`, `loreBookLabel()`, `parseStoredJSON()`, `loreField()`, `loreSelect()`, `loreBookOptions()`, `renderLoreLibrarySidebar()`, `renderNode()`, `loadLoreWorkspaceData()`, `collectLoreLinkTargets()`, `loreWorkspaceVisible()`, `renderLoreWorkspaceBody()`, `openLoreWorkspace()`, `renderLoreInspector()`, `selectTab()`, `buildLoreWorkspace()`, `renderWorkspaceTree()`, `renderNode()`, `renderTreeList()`, `renderLoreBookEditor()`, `moveLoreBook()`, `reorderLoreBook()`, `promoteLoreBook()`, `demoteLoreBook()`, `createSiblingLoreBook()`, `createLoreBookDialog()`, `refreshLoreUI()`, `renderLoreEntries()`, `renderList()`, `buildLoreEntryCard()`, `splitNumberList()`, `reinterpretLoreBook()`, `generateLoreEntriesPrompt()`, `buildDirectLoreRequest()`, `renderRelationshipOverview()`, `renderLoreRelationshipEditor()`, `renderRelationshipList()`, `showNewRelationshipForm()`, `renderLoreGenerator()`, `adoptGeneratorPlan()`, `generatorPlanMessage()`, `loreGenAgo()`, `refreshLoreGenRecovery()`, `normalizeGeneratorPlan()`, `renderLorePlanPreview()`, `renderOperations()`, `planStat()`, `renderAnalysisSection()`, `addPlanGroup()`, `stripPlanUIFields()`, `acceptedGeneratorPlan()`.

### `static/js/settings.js` (2816 lines)

Sections: Chat tool modals (`:1`); Condition tab (`:544`); Survival tracker (`:604`); Character relocation (`:843`); API connections (`:1534`); Software updates (host-only; git fast-forward from GitHub origin) (`:2518`); Legacy checkpoint conversion (host-only maintenance) (`:2550`); Prompts (`:2784`).

Declared functions: `selectTab()`, `renderCastTab()`, `renderConditionTab()`, `hydrateConditionTab()`, `vitalMeter()`, `syncVitalsGutterNow()`, `syncVitalsGutter()`, `hideVitalsHud()`, `vitalsBlock()`, `refreshVitalsHud()`, `clearVitalsHud()`, `hydrateCastLocations()`, `castRoomLabel()`, `castRoomSelect()`, `renderLorebooksTab()`, `renderBookNode()`, `renderMultiplayerTab()`, `renderFramesTab()`, `renderFramesListPanel()`, `renderPersonaStationingPanel()`, `renderParadoxPanel()`, `renderBackgroundPresencesPanel()`, `renderGuestInvitePanel()`, `renderInsightsTab()`, `renderDramaticIronyPanel()`, `renderPromiseLedgerPanel()`, `embeddingBankBlock()`, `modelRecommendationsBlock()`, `renderFirstRunProviderSetup()`, `preferredBackdropSize()`, `renderFullApiSettings()`, `propagateToFollowers()`, `renderUpdateChecking()`, `renderUpdateError()`, `checkpointCompactionBlock()`, `renderUpdateStatus()`, `runUpdateInstall()`, `renderUpdateDone()`.

### `static/js/theme-init.js` (181 lines)

Declared functions: `readStored()`, `writeStored()`, `normaliseTheme()`, `normaliseProseSize()`, `applyTheme()`, `applyProseSize()`, `normaliseEffects()`, `applyEffects()`, `syncPageHidden()`.

### `static/js/themes.js` (159 lines)

Declared functions: `themePreview()`, `openAppearanceSettings()`.

### `static/js/utils.js` (146 lines)

Sections: API (`:49`); Download (`:139`).

Declared functions: `hasDefaultModel()`, `safeId()`, `splitCL()`, `numOr()`, `taggedError()`, `api()`, `streamPost()`, `downloadJSON()`.

### `static/js/weather-fx.js` (548 lines)

Sections: Weather effects (`:2`); the tile (`:178`); the layers (`:251`); lifecycle (`:329`); lightning (`:387`); the exact cost this file exists to avoid. Rain has no wrapper and no (`:527`).

Declared functions: `weatherFxReduced()`, `weatherFxEffectsOff()`, `weatherFxSupported()`, `weatherFxHost()`, `weatherFxRandom()`, `weatherFxTile()`, `weatherFxReach()`, `weatherFxBuild()`, `weatherFxClearLayers()`, `weatherFxStop()`, `weatherFxVisible()`, `weatherFxApply()`, `weatherFxStormy()`, `weatherFxScheduleFlash()`, `weatherFxFlash()`, `weatherFxOpenSky()`, `weatherFxBolt()`, `weatherFxThunder()`, `weatherFxForTurn()`.
