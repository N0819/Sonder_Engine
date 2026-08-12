# Generated Code Map

> Regenerate with `python tools/generate_code_map.py`. Do not hand-edit this file.

## Python modules

| Module | Lines | Purpose | Local dependencies |
|---|---:|---|---|
| `affect.py` | 1965 |  | `theory_of_mind` |
| `agents/__init__.py` | 88 | Backward-compatible facade for the role-specific agent package. | `agents.character`, `agents.common`, `agents.director`, `agents.loops`, `agents.mapping`, `agents.narration`, `agents.perception`, `agents.runtime`, `agents.storage`, `scene` |
| `agents/background.py` | 903 |  | `agents.common`, `background_claims`, `character_schema`, `commit`, `db`, `prompts`, `scene`, `schemas`, `spatial` |
| `agents/character.py` | 3277 | Private character decision agent. | `affect`, `agents.common`, `character_schema`, `db`, `frames`, `gaps`, `memory`, `place_purpose`, `prompts`, `psychology_runtime`, `scene`, `schemas`, `spatial`, `survival`, `theory_of_mind` |
| `agents/common.py` | 6066 | Shared normalization, lore, delivery, and perception helpers. | `attire`, `character_schema`, `crowds`, `db`, `llm_quality`, `memory`, `providers`, `scene`, `schemas`, `spatial`, `theory_of_mind` |
| `agents/composer.py` | 1475 |  | `agents.common`, `spatial` |
| `agents/director.py` | 7178 | Scene establishment, player interpretation, and objective resolution. | `agents.common`, `attire`, `character_schema`, `db`, `memory`, `paradox`, `prompts`, `providers`, `scene`, `schemas`, `spatial`, `survival` |
| `agents/loops.py` | 1038 | Reaction loops, interaction rounds, and deterministic micro-perception. | `agents.character`, `agents.common`, `character_schema`, `db`, `scene`, `spatial` |
| `agents/mapping.py` | 297 | Lore routing, cached recall, and retrieval staging. | `agents.common`, `character_schema`, `db`, `memory`, `prompts`, `scene` |
| `agents/narration.py` | 1012 | Player-facing narration agent. | `agents.common`, `character_schema`, `db`, `prompts`, `scene`, `schemas`, `spatial` |
| `agents/perception.py` | 4234 | Opening, action-onset, and outcome observer views. | `affect`, `agents`, `agents.common`, `character_schema`, `db`, `scene`, `spatial` |
| `agents/runtime.py` | 1038 | Pipeline plans, dispatch, streaming, cancellation, resume, and reruns. | `agents.background`, `agents.character`, `agents.common`, `agents.director`, `agents.loops`, `agents.mapping`, `agents.narration`, `agents.perception`, `agents.storage`, `character_schema`, `checkpoints`, `commit`, `db`, `pipeline_context`, `providers`, `scene` |
| `agents/storage.py` | 115 | Step and active-variant persistence helpers. | `db` |
| `ambience.py` | 2082 |  | `backdrops`, `db`, `outofband`, `weather` |
| `app.py` | 4850 | FastAPI application assembly, resource CRUD, turn control, and streaming endpoints. | `agents`, `ambience`, `attire`, `auth_routes`, `backdrops`, `character_schema`, `chat_archive`, `checkpoints`, `commit`, `db`, `frames`, `greetings`, `guest_access`, `importers`, `memory`, `paradox`, `pipeline_context`, `prompts`, `providers`, `scene`, `survival`, `updates` |
| `artifacts.py` | 568 |  | — |
| `attire.py` | 2619 |  | — |
| `auth_routes.py` | 175 | Typed host-authentication HTTP routes and cookie transport. | `guest_access` |
| `authored_events.py` | 124 |  | `db` |
| `backdrops.py` | 1258 |  | `db`, `logging_utils`, `outofband`, `spatial`, `weather` |
| `background_claims.py` | 466 |  | `db` |
| `canon_provenance.py` | 360 |  | — |
| `carriers.py` | 696 |  | `character_schema`, `crowds`, `db`, `degradation`, `living_world`, `scene`, `spatial` |
| `character_schema.py` | 1554 | Versioned character/persona defaults, normalization, accessors, and export payloads. | `attire`, `schemas` |
| `chat_archive.py` | 1110 | Typed, atomic chat archive export/import service and HTTP routes. | `character_schema`, `checkpoints`, `db`, `memory`, `schemas` |
| `checkpoints.py` | 1145 | Whole-chat snapshots and checkpoint restore orchestration. | `db`, `memory` |
| `comfort.py` | 306 |  | `spatial` |
| `commit.py` | 7444 | Validated persistence of scene, entities, cast, lore, relationships, events, and memories. | `affect`, `attire`, `character_schema`, `comfort`, `db`, `frames`, `mechanics`, `memory`, `paradox`, `prompts`, `providers`, `psychology_runtime`, `scene`, `spatial`, `spatial_frames`, `survival`, `theory_of_mind`, `weather` |
| `couriers.py` | 1090 |  | `carriers`, `crowds`, `degradation` |
| `crowds.py` | 608 |  | — |
| `db.py` | 1657 | SQLite schema, migrations, connection management, transactions, and key/value world access. | — |
| `degradation.py` | 171 |  | — |
| `frames.py` | 220 |  | `db` |
| `gaps.py` | 550 |  | `canon_provenance`, `db`, `logging_utils`, `providers`, `spatial`, `subjects` |
| `greetings.py` | 393 |  | `agents.runtime`, `agents.storage`, `character_schema`, `db`, `llm_quality`, `memory`, `prompts` |
| `guest_access.py` | 355 |  | `db` |
| `importers.py` | 2715 | Native and AI-assisted character, persona, and lorebook import/generation. | `character_schema`, `db`, `logging_utils`, `memory`, `prompts`, `providers` |
| `jobs.py` | 183 |  | `logging_utils` |
| `living_world.py` | 608 |  | `logging_utils`, `mechanics` |
| `llm_quality.py` | 505 | Strict JSON parsing, schema validation, and model-assisted repair. | `pipeline_context`, `providers`, `schemas` |
| `logging_utils.py` | 118 | Structured timing and observability helpers. | — |
| `lore_structure.py` | 242 |  | — |
| `mechanics.py` | 310 |  | `spatial`, `spatial_frames` |
| `memory.py` | 5433 | Lorebook graph, memory retrieval/consolidation, relationships, and vector search. | `db`, `frames`, `logging_utils`, `prompts`, `providers`, `theory_of_mind` |
| `offscreen.py` | 2158 |  | `logging_utils` |
| `outofband.py` | 276 |  | `logging_utils` |
| `paradox.py` | 489 |  | `character_schema`, `db`, `frames` |
| `pipeline_context.py` | 308 | Typed mutable context passed through a turn pipeline. | `db` |
| `pipeline_trace.py` | 413 | Privacy-conscious export, validation, and offline replay of persisted pipeline history. | `db` |
| `place_purpose.py` | 532 |  | `comfort`, `spatial`, `survival`, `theory_of_mind` |
| `prompt_cache.py` | 79 | Provider-specific prompt-cache helpers. | `providers` |
| `prompts.py` | 5434 | Default system prompts and prompt preset access. | `db` |
| `providers.py` | 2754 | Provider selection, retries, streaming, cancellation, model listing, and embeddings. | `db`, `logging_utils` |
| `psychology_runtime.py` | 502 |  | — |
| `routines.py` | 200 |  | — |
| `scene.py` | 1436 | Scene/cast/persona helpers, recent events, dialogue configuration, and private knowledge. | `attire`, `character_schema`, `db`, `spatial` |
| `schemas.py` | 4527 | Pydantic output contracts and semantic validation for agent payloads. | — |
| `spatial.py` | 7933 | Deterministic room, barrier, hearing, visibility, placement, and scene-diff logic. | `schemas`, `spatial_orientation` |
| `spatial_frames.py` | 1022 |  | `character_schema`, `db`, `frames`, `paradox`, `scene`, `spatial` |
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
| `scene_life()` | 479 | 120 lines |
| `_beat_for_presence()` | 109 | 80 lines |
| `_react_one()` | 843 | 61 lines |
| `_mint_blurbs()` | 668 | 57 lines |
| `background_react()` | 213 | 52 lines |
| `_place_block()` | 271 | 47 lines |
| `managed_presences()` | 365 | 46 lines |
| `_present_others()` | 796 | 45 lines |

### `agents/character.py`

| Function | Start | Size |
|---|---:|---:|
| `character_step()` | 2344 | 934 lines |
| `_annotate_known_exits()` | 1765 | 445 lines |
| `_ground_observation_citations()` | 825 | 263 lines |
| `_unanswered_question_note()` | 279 | 117 lines |
| `_destination_from_goals()` | 1343 | 109 lines |
| `sprint_offers()` | 2245 | 97 lines |
| `_recent_self_moves()` | 148 | 90 lines |
| `_verdict()` | 1187 | 72 lines |

### `agents/common.py`

| Function | Start | Size |
|---|---:|---:|
| `norm_sequence()` | 1796 | 193 lines |
| `_scrub_invented_dialogue()` | 4698 | 145 lines |
| `_check_narrator_fidelity()` | 5700 | 125 lines |
| `_extract_authority_claims()` | 1326 | 106 lines |
| `_perceptible_entities()` | 904 | 98 lines |
| `_check_presence_knowledge_channel()` | 3343 | 95 lines |
| `region_visibility()` | 581 | 92 lines |
| `observer_body_regions()` | 675 | 92 lines |

### `agents/composer.py`

| Function | Start | Size |
|---|---:|---:|
| `render_view()` | 1086 | 90 lines |
| `render_episode()` | 1257 | 80 lines |
| `pose_percepts()` | 500 | 75 lines |
| `observations_from_render()` | 1401 | 75 lines |
| `_render_standing()` | 1004 | 53 lines |
| `speech_percept()` | 694 | 50 lines |
| `presence_percepts()` | 410 | 48 lines |
| `_render_presence_group()` | 888 | 45 lines |

### `agents/director.py`

| Function | Start | Size |
|---|---:|---:|
| `director_resolve()` | 5714 | 1310 lines |
| `director_interpret()` | 771 | 476 lines |
| `_reconcile_resolution()` | 3886 | 412 lines |
| `_evidence_present()` | 3067 | 232 lines |
| `_reconcile_near_group_positions()` | 2353 | 201 lines |
| `_run_specialists()` | 5435 | 187 lines |
| `_specialist_payload()` | 5225 | 133 lines |
| `_verify_already_true()` | 3593 | 126 lines |

### `agents/loops.py`

| Function | Start | Size |
|---|---:|---:|
| `interaction_loop()` | 400 | 568 lines |
| `deterministic_micro_perception()` | 46 | 123 lines |
| `reaction_loop()` | 969 | 70 lines |
| `_isolated_wave()` | 357 | 41 lines |
| `_defer_to_unrun_reactor()` | 214 | 37 lines |
| `_standing_pressure()` | 253 | 37 lines |
| `_perceptually_isolated()` | 320 | 35 lines |
| `_defer_to_focus()` | 184 | 28 lines |

### `agents/mapping.py`

| Function | Start | Size |
|---|---:|---:|
| `mapping_stage()` | 32 | 109 lines |
| `mapping_quick()` | 199 | 64 lines |
| `merge_lore()` | 265 | 33 lines |
| `_join_relevant_lore()` | 165 | 32 lines |

### `agents/narration.py`

| Function | Start | Size |
|---|---:|---:|
| `narrator()` | 659 | 217 lines |
| `_ordered_beat_events()` | 280 | 154 lines |
| `narrator_extra()` | 877 | 136 lines |
| `_visible_portal_states()` | 523 | 100 lines |
| `_resolve_narration_person()` | 78 | 66 lines |
| `_position_delta_payload()` | 467 | 54 lines |
| `_generate_narration()` | 625 | 33 lines |
| `_player_sees_character()` | 436 | 29 lines |

### `agents/perception.py`

| Function | Start | Size |
|---|---:|---:|
| `_composer_outcome()` | 3917 | 318 lines |
| `perception_outcome()` | 2823 | 298 lines |
| `perception_act()` | 2383 | 251 lines |
| `_observer_scene_payload()` | 864 | 212 lines |
| `_composer_act()` | 3796 | 119 lines |
| `_previous_open_group_continuity()` | 153 | 117 lines |
| `_strip_self_narration()` | 1662 | 107 lines |
| `perception_establish()` | 2275 | 107 lines |

### `agents/runtime.py`

| Function | Start | Size |
|---|---:|---:|
| `_run_pipeline()` | 680 | 305 lines |
| `build_plan()` | 479 | 81 lines |
| `resume_key_for_turn()` | 424 | 54 lines |
| `run_pipeline()` | 986 | 53 lines |
| `_load_extra_players()` | 45 | 52 lines |
| `_stream_one()` | 278 | 48 lines |
| `_stream_parallel()` | 327 | 45 lines |
| `_rehydrate_loop_results()` | 632 | 41 lines |

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
| `turn_branch()` | 3732 | 390 lines |
| `_remap_cp_blob()` | 667 | 194 lines |
| `chat_get()` | 2310 | 187 lines |
| `_stream()` | 280 | 91 lines |
| `lore_entry_edit()` | 2099 | 70 lines |
| `lore_edit()` | 1951 | 68 lines |
| `_ambience_payload()` | 4632 | 68 lines |
| `guest_state()` | 2767 | 66 lines |

### `artifacts.py`

| Function | Start | Size |
|---|---:|---:|
| `run_artifacts()` | 182 | 202 lines |
| `schedule_artifact_wording()` | 391 | 65 lines |
| `mint_wording()` | 458 | 59 lines |
| `land_artifact_wording()` | 519 | 50 lines |
| `reading_copy()` | 149 | 25 lines |
| `new_artifact()` | 127 | 20 lines |
| `artifact_voice()` | 94 | 11 lines |
| `posted_in_room()` | 115 | 10 lines |

### `attire.py`

| Function | Start | Size |
|---|---:|---:|
| `compact_line()` | 2440 | 161 lines |
| `advance()` | 1771 | 135 lines |
| `normalize_regions()` | 398 | 133 lines |
| `coerce_diff_shape()` | 1250 | 124 lines |
| `perceptible_region_surfaces()` | 2009 | 100 lines |
| `_attributed_targets()` | 1455 | 90 lines |
| `recover_shed_entity_changes()` | 1024 | 87 lines |
| `dedupe_regions()` | 1113 | 87 lines |

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
| `apply_tellings()` | 498 | 199 lines |
| `advance_carriers()` | 116 | 131 lines |
| `_carriers()` | 366 | 59 lines |
| `_crowds_acquire()` | 249 | 56 lines |
| `_invented_claim()` | 446 | 34 lines |
| `persona_entry()` | 307 | 33 lines |
| `reports_for_state()` | 93 | 21 lines |
| `_cast_index()` | 427 | 17 lines |

### `character_schema.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_character_data()` | 974 | 159 lines |
| `default_character_data()` | 553 | 95 lines |
| `_normalize_psychology()` | 293 | 83 lines |
| `repair_character_shape()` | 915 | 57 lines |
| `_normalize_extra_parts()` | 499 | 52 lines |
| `_as_profile_list()` | 38 | 50 lines |
| `normalize_persona_data()` | 1134 | 50 lines |
| `character_initial_active_state()` | 1348 | 48 lines |

### `chat_archive.py`

| Function | Start | Size |
|---|---:|---:|
| `_model_validate()` | 54 | 4 lines |
| `_model_dump()` | 60 | 4 lines |

### `checkpoints.py`

| Function | Start | Size |
|---|---:|---:|
| `snapshot_state()` | 15 | 169 lines |
| `_restore_checkpoint_body()` | 559 | 141 lines |
| `compact_checkpoints()` | 809 | 118 lines |
| `insert_world_tables()` | 377 | 105 lines |
| `_restore_books()` | 185 | 104 lines |
| `ensure_checkpoint()` | 993 | 53 lines |
| `propagate_memory_summaries_to_checkpoints()` | 1048 | 53 lines |
| `_verify_no_loss()` | 757 | 50 lines |

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
| `prepare_memory_commit()` | 5581 | 1202 lines |
| `prepare_scene_commit()` | 2265 | 425 lines |
| `commit_world_entities()` | 3147 | 283 lines |
| `apply_attire_diff()` | 1970 | 253 lines |
| `track_background_presences()` | 3947 | 231 lines |
| `_commit_all_locked()` | 7191 | 195 lines |
| `commit_transit_sweep()` | 2739 | 169 lines |
| `_prepare_destruction()` | 700 | 158 lines |

### `couriers.py`

| Function | Start | Size |
|---|---:|---:|
| `run_couriers()` | 747 | 344 lines |
| `_exchange_stops()` | 535 | 210 lines |
| `advance_couriers()` | 282 | 78 lines |
| `_deliver()` | 462 | 71 lines |
| `new_courier()` | 221 | 46 lines |
| `_copy_of()` | 362 | 39 lines |
| `_player_name()` | 434 | 26 lines |
| `courier_uid()` | 157 | 15 lines |

### `crowds.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_ops()` | 236 | 158 lines |
| `emerge()` | 396 | 38 lines |
| `drift()` | 136 | 35 lines |
| `advance_crowds()` | 467 | 32 lines |
| `absorb()` | 436 | 29 lines |
| `talk_view()` | 567 | 29 lines |
| `describe()` | 512 | 21 lines |
| `density()` | 92 | 15 lines |

### `db.py`

| Function | Start | Size |
|---|---:|---:|
| `init()` | 1564 | 50 lines |
| `conn()` | 1411 | 38 lines |
| `transaction()` | 1451 | 36 lines |
| `_backfill_resource_uids()` | 1546 | 17 lines |
| `qi()` | 1509 | 16 lines |
| `data_version()` | 1488 | 14 lines |
| `parse_scoped_world_key()` | 71 | 13 lines |
| `_execute_retry()` | 1380 | 13 lines |

### `degradation.py`

| Function | Start | Size |
|---|---:|---:|
| `degrade()` | 110 | 27 lines |
| `lost_at()` | 153 | 19 lines |
| `_replace_phrases()` | 94 | 14 lines |
| `is_exhausted()` | 139 | 12 lines |
| `_collapse()` | 90 | 2 lines |

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
| `_skeleton()` | 146 | 175 lines |
| `last_seen_update()` | 446 | 70 lines |
| `_medium_overlay()` | 327 | 57 lines |
| `gap_for()` | 386 | 54 lines |
| `interim_for()` | 518 | 33 lines |
| `_record()` | 78 | 22 lines |
| `_derived_resolution()` | 108 | 22 lines |
| `_subject_room()` | 132 | 12 lines |

### `greetings.py`

| Function | Start | Size |
|---|---:|---:|
| `start_story()` | 174 | 141 lines |
| `generate_greeting()` | 317 | 58 lines |
| `extract_greeting()` | 96 | 24 lines |
| `_substitute_player_slot()` | 53 | 22 lines |
| `player_handle_for()` | 77 | 17 lines |
| `_strip_greeting_wrapping()` | 377 | 17 lines |
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
| `import_lorebook()` | 1393 | 212 lines |
| `_reinterpret_entries()` | 1266 | 126 lines |
| `apply_lorebook_plan()` | 2513 | 124 lines |
| `_lore_gen_entry_batch()` | 2165 | 118 lines |
| `_run_lore_gen_job()` | 2287 | 112 lines |
| `fill_appearance()` | 1047 | 109 lines |
| `import_character()` | 545 | 91 lines |
| `generate_lore_entries()` | 2637 | 79 lines |

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
| `mint_consequences()` | 354 | 100 lines |
| `record_obligations()` | 504 | 53 lines |
| `living_world_levels()` | 290 | 33 lines |
| `fired_consequences_at()` | 456 | 28 lines |
| `effective_depth()` | 247 | 27 lines |
| `owed_history()` | 559 | 24 lines |
| `attach_owed_history()` | 585 | 24 lines |
| `normalize_living_world()` | 208 | 20 lines |

### `llm_quality.py`

| Function | Start | Size |
|---|---:|---:|
| `complete_validated_json()` | 158 | 348 lines |
| `output_ran_out_of_room()` | 89 | 47 lines |
| `_extract_balanced_object()` | 35 | 34 lines |
| `strict_json_parse()` | 138 | 19 lines |
| `_strip_fences()` | 71 | 16 lines |

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
| `build_character_memory_context()` | 2860 | 274 lines |
| `search_memories()` | 1911 | 228 lines |
| `rebuild_embeddings()` | 4805 | 213 lines |
| `embedding_bank_status()` | 4655 | 125 lines |
| `rebuild_checkpoint_embeddings()` | 5057 | 124 lines |
| `contrast_memory()` | 2174 | 117 lines |
| `_origin_on_drift()` | 2761 | 97 lines |
| `backfill_memory_summary_windows()` | 3265 | 89 lines |

### `offscreen.py`

| Function | Start | Size |
|---|---:|---:|
| `land_agent_tick()` | 1852 | 187 lines |
| `schedule_agent_ticks()` | 2041 | 118 lines |
| `schedule_profile_ticks()` | 1370 | 113 lines |
| `apply_plan_ops()` | 681 | 110 lines |
| `profile_summary_record()` | 1107 | 99 lines |
| `advance_epoch()` | 926 | 98 lines |
| `advance_reactive_plans()` | 839 | 85 lines |
| `agent_adjudication()` | 1758 | 69 lines |

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

### `pipeline_context.py`

| Function | Start | Size |
|---|---:|---:|
| `note_step_warning()` | 34 | 11 lines |

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
| `specialist_prompt()` | 2025 | 17 lines |
| `prose_author_prompt()` | 2110 | 15 lines |
| `get_prompt()` | 5425 | 10 lines |
| `presets()` | 5416 | 2 lines |
| `active_preset()` | 5419 | 2 lines |
| `nsfw_enabled()` | 5422 | 2 lines |

### `providers.py`

| Function | Start | Size |
|---|---:|---:|
| `_chat_complete_once()` | 1776 | 216 lines |
| `async chat_complete_async()` | 1993 | 88 lines |
| `chat_complete()` | 1544 | 84 lines |
| `async _chat_complete_async_once()` | 2082 | 84 lines |
| `_sse_openai()` | 1416 | 78 lines |
| `async _sse_openai_async()` | 2167 | 63 lines |
| `_embed_request()` | 2484 | 58 lines |
| `resolve_role_candidates()` | 1255 | 54 lines |

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
| `recent_events_for_observer()` | 751 | 59 lines |
| `director_context()` | 811 | 53 lines |
| `awareness_conditions()` | 472 | 47 lines |
| `private_knowledge_for()` | 1393 | 44 lines |
| `_seed_scene_initial_attire()` | 86 | 31 lines |
| `active_cast()` | 162 | 31 lines |
| `active_disguises()` | 364 | 31 lines |
| `normalize_style_guide()` | 1297 | 31 lines |

### `schemas.py`

| Function | Start | Size |
|---|---:|---:|
| `preprocess_llm_output()` | 3431 | 277 lines |
| `_lenient_coerce()` | 547 | 159 lines |
| `validate_llm_output_strict()` | 4401 | 127 lines |
| `semantic_output_errors()` | 4208 | 113 lines |
| `_coerce_evidence_refs()` | 2249 | 51 lines |
| `_coerce_conditions()` | 3171 | 50 lines |
| `_declared()` | 387 | 48 lines |
| `_coerce_station_table()` | 49 | 41 lines |

### `spatial.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_contact_ops()` | 4635 | 318 lines |
| `merge_scene_with_diff()` | 7593 | 296 lines |
| `sprint_reach()` | 6233 | 175 lines |
| `apply_transit_dock_edges()` | 6967 | 165 lines |
| `contact_sensation()` | 5798 | 144 lines |
| `hear_level()` | 1189 | 138 lines |
| `visible_adjacent_rooms()` | 6478 | 138 lines |
| `contacts_from_entity_state()` | 3950 | 137 lines |

### `spatial_frames.py`

| Function | Start | Size |
|---|---:|---:|
| `infer_focus()` | 468 | 118 lines |
| `infer_threshold_crossings()` | 370 | 96 lines |
| `perform_split()` | 752 | 94 lines |
| `infer_companion_carry()` | 234 | 92 lines |
| `infer_vehicle_zones()` | 147 | 85 lines |
| `perform_merge()` | 924 | 69 lines |
| `infer_facing()` | 588 | 59 lines |
| `detect_split()` | 706 | 44 lines |

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
| GET | `/` | `index()` | `app.py:199` |
| PUT | `/api/active_preset` | `set_active()` | `app.py:1225` |
| PUT | `/api/agent_models` | `put_agent_models()` | `app.py:1006` |
| PUT | `/api/ambience` | `put_ambience()` | `app.py:1119` |
| GET | `/api/ambience/library` | `ambience_library()` | `app.py:4790` |
| GET | `/api/ambience/search` | `ambience_search()` | `app.py:4769` |
| PUT | `/api/attire_beneath` | `set_attire_beneath()` | `app.py:1259` |
| POST | `/api/auth/login` | `auth_login()` | `auth_routes.py:108` |
| POST | `/api/auth/logout` | `auth_logout()` | `auth_routes.py:171` |
| POST | `/api/auth/setup` | `auth_setup()` | `auth_routes.py:69` |
| GET | `/api/auth/status` | `auth_status()` | `auth_routes.py:59` |
| GET | `/api/auto_promote` | `get_auto_promote()` | `app.py:2591` |
| PUT | `/api/auto_promote` | `set_auto_promote()` | `app.py:2595` |
| PUT | `/api/backdrops` | `put_backdrops()` | `app.py:1109` |
| GET | `/api/bootstrap` | `bootstrap()` | `app.py:943` |
| POST | `/api/characters` | `char_create()` | `app.py:1702` |
| POST | `/api/characters/generate` | `char_generate()` | `app.py:1692` |
| POST | `/api/characters/import` | `char_import()` | `app.py:1723` |
| DELETE | `/api/characters/{cid}` | `char_del()` | `app.py:1834` |
| PUT | `/api/characters/{cid}` | `char_edit()` | `app.py:1825` |
| GET | `/api/characters/{cid}/export` | `char_export()` | `app.py:1817` |
| POST | `/api/characters/{cid}/fill_appearance` | `char_fill_appearance()` | `app.py:1807` |
| POST | `/api/characters/{cid}/fill_psychology` | `char_fill_psychology()` | `app.py:1781` |
| POST | `/api/characters/{cid}/generate_greeting` | `char_generate_greeting()` | `app.py:1766` |
| POST | `/api/characters/{cid}/recover_greetings` | `char_recover_greetings()` | `app.py:1756` |
| POST | `/api/characters/{cid}/start` | `character_start_story()` | `app.py:1738` |
| POST | `/api/chats` | `chat_new()` | `app.py:2178` |
| POST | `/api/chats/import` | `import_chat()` | `chat_archive.py:175` |
| DELETE | `/api/chats/{cid}` | `chat_del()` | `app.py:2280` |
| GET | `/api/chats/{cid}` | `chat_get()` | `app.py:2310` |
| PUT | `/api/chats/{cid}` | `chat_edit()` | `app.py:2184` |
| POST | `/api/chats/{cid}/abort` | `chat_abort()` | `app.py:3728` |
| GET | `/api/chats/{cid}/ambience/oneshot/{name}` | `ambience_oneshot()` | `app.py:4799` |
| DELETE | `/api/chats/{cid}/ambience/pin` | `ambience_pin_delete()` | `app.py:4847` |
| PUT | `/api/chats/{cid}/ambience/pin` | `ambience_pin_put()` | `app.py:4828` |
| GET | `/api/chats/{cid}/ambience/pins` | `ambience_pins_get()` | `app.py:4823` |
| GET | `/api/chats/{cid}/ambience/{signature}.audio` | `ambience_audio()` | `app.py:4753` |
| GET | `/api/chats/{cid}/attire` | `attire_get()` | `app.py:3213` |
| PUT | `/api/chats/{cid}/attire` | `attire_put()` | `app.py:3220` |
| GET | `/api/chats/{cid}/backdrop/{signature}.png` | `backdrop_image()` | `app.py:4600` |
| GET | `/api/chats/{cid}/background_config` | `bg_cfg_get()` | `app.py:3354` |
| PUT | `/api/chats/{cid}/background_config` | `bg_cfg_put()` | `app.py:3358` |
| POST | `/api/chats/{cid}/characters` | `chat_add_char()` | `app.py:2499` |
| DELETE | `/api/chats/{cid}/characters/{ch}` | `chat_del_char()` | `app.py:2860` |
| PUT | `/api/chats/{cid}/characters/{ch}/card` | `chat_char_card_put()` | `app.py:2870` |
| GET | `/api/chats/{cid}/characters/{ch}/memories` | `mem_list()` | `app.py:3484` |
| POST | `/api/chats/{cid}/characters/{ch}/memories` | `mem_add()` | `app.py:3615` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/backfill` | `mem_backfill()` | `app.py:3586` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/consolidate` | `mem_consolidate()` | `app.py:3575` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/coverage` | `mem_coverage()` | `app.py:3606` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/export` | `mem_export()` | `app.py:3530` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/import` | `mem_import()` | `app.py:3541` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/search` | `mem_search()` | `app.py:3505` |
| GET | `/api/chats/{cid}/characters/{ch}/memory-context` | `memory_context_preview()` | `app.py:3551` |
| PUT | `/api/chats/{cid}/characters/{ch}/position` | `chat_char_position_put()` | `app.py:3076` |
| GET | `/api/chats/{cid}/characters/{ch}/private_history` | `ph_get()` | `app.py:3136` |
| PUT | `/api/chats/{cid}/characters/{ch}/private_history` | `ph_put()` | `app.py:3146` |
| GET | `/api/chats/{cid}/characters/{ch}/relationships` | `relationships_get()` | `app.py:3564` |
| GET | `/api/chats/{cid}/dialogue_config` | `dlg_get()` | `app.py:3255` |
| PUT | `/api/chats/{cid}/dialogue_config` | `dlg_put()` | `app.py:3272` |
| GET | `/api/chats/{cid}/dramatic_irony` | `get_dramatic_irony_feed()` | `app.py:2553` |
| GET | `/api/chats/{cid}/export` | `export_chat()` | `chat_archive.py:169` |
| GET | `/api/chats/{cid}/fixed_points` | `fixed_points_list()` | `app.py:3430` |
| POST | `/api/chats/{cid}/fixed_points` | `fixed_points_create()` | `app.py:3440` |
| DELETE | `/api/chats/{cid}/fixed_points/{anchor_id}` | `fixed_points_delete()` | `app.py:3462` |
| GET | `/api/chats/{cid}/frames` | `frames_list()` | `app.py:3384` |
| POST | `/api/chats/{cid}/frames` | `frames_create()` | `app.py:3388` |
| GET | `/api/chats/{cid}/guest_invites` | `list_guest_invites()` | `app.py:2739` |
| POST | `/api/chats/{cid}/guest_invites` | `create_guest_invite()` | `app.py:2721` |
| DELETE | `/api/chats/{cid}/guest_invites/{gid}` | `revoke_guest_invite()` | `app.py:2743` |
| GET | `/api/chats/{cid}/living_world` | `living_world_get()` | `app.py:3319` |
| PUT | `/api/chats/{cid}/living_world` | `living_world_put()` | `app.py:3342` |
| DELETE | `/api/chats/{cid}/lorebook` | `detach_lore()` | `app.py:2271` |
| POST | `/api/chats/{cid}/lorebook` | `bind_lore()` | `app.py:2255` |
| GET | `/api/chats/{cid}/lorebooks` | `chat_lorebooks_owned()` | `app.py:1344` |
| POST | `/api/chats/{cid}/lorebooks` | `attach_lore()` | `app.py:2215` |
| DELETE | `/api/chats/{cid}/lorebooks/{lid}` | `detach_book()` | `app.py:2240` |
| GET | `/api/chats/{cid}/paradox_policy` | `paradox_policy_get()` | `app.py:3415` |
| PUT | `/api/chats/{cid}/paradox_policy` | `paradox_policy_put()` | `app.py:3419` |
| GET | `/api/chats/{cid}/persona_private_history` | `pph_get()` | `app.py:3155` |
| PUT | `/api/chats/{cid}/persona_private_history` | `pph_put()` | `app.py:3168` |
| GET | `/api/chats/{cid}/personas` | `chat_list_extra_personas()` | `app.py:2600` |
| POST | `/api/chats/{cid}/personas` | `chat_add_persona()` | `app.py:2645` |
| DELETE | `/api/chats/{cid}/personas/{pid}` | `chat_del_persona()` | `app.py:2669` |
| PUT | `/api/chats/{cid}/personas/{pid}/station` | `chat_persona_station()` | `app.py:2610` |
| GET | `/api/chats/{cid}/positions` | `chat_positions_get()` | `app.py:3012` |
| GET | `/api/chats/{cid}/promises` | `get_promise_ledger()` | `app.py:2557` |
| GET | `/api/chats/{cid}/promotable` | `list_promotable_presences()` | `app.py:2549` |
| POST | `/api/chats/{cid}/promotions/confirm` | `confirm_promotion()` | `app.py:2574` |
| POST | `/api/chats/{cid}/promotions/draft` | `draft_promotion()` | `app.py:2561` |
| GET | `/api/chats/{cid}/style_guide` | `style_guide_get()` | `app.py:3238` |
| PUT | `/api/chats/{cid}/style_guide` | `style_guide_put()` | `app.py:3244` |
| GET | `/api/chats/{cid}/survival` | `survival_get()` | `app.py:2927` |
| PUT | `/api/chats/{cid}/survival` | `survival_put()` | `app.py:2932` |
| POST | `/api/chats/{cid}/turns` | `turn_new()` | `app.py:3668` |
| POST | `/api/chats/{cid}/turns/{idx}/player_input` | `submit_extra_player_input()` | `app.py:2683` |
| GET | `/api/chats/{cid}/vitals` | `chat_vitals_get()` | `app.py:2979` |
| GET | `/api/chats/{cid}/world` | `world_get()` | `app.py:3173` |
| PUT | `/api/chats/{cid}/world` | `world_put()` | `app.py:3177` |
| PUT | `/api/director_orchestration` | `set_director_orchestration()` | `app.py:1239` |
| PUT | `/api/exemplars` | `put_exemplars()` | `app.py:1078` |
| POST | `/api/guest/input` | `guest_input()` | `app.py:2835` |
| GET | `/api/guest/state` | `guest_state()` | `app.py:2767` |
| PUT | `/api/image_model` | `put_image_model()` | `app.py:1056` |
| POST | `/api/join` | `join_with_code()` | `app.py:2749` |
| DELETE | `/api/lore_entries/{eid}` | `lore_entry_delete()` | `app.py:2171` |
| PUT | `/api/lore_entries/{eid}` | `lore_entry_edit()` | `app.py:2099` |
| DELETE | `/api/lore_gen_jobs/{job_id}` | `lorebook_generate_discard()` | `app.py:1499` |
| POST | `/api/lore_gen_jobs/{job_id}/resume` | `lorebook_generate_resume()` | `app.py:1481` |
| DELETE | `/api/lorebook_links/{link_id}` | `lorebook_link_delete()` | `app.py:1440` |
| PUT | `/api/lorebook_links/{link_id}` | `lorebook_link_update()` | `app.py:1426` |
| POST | `/api/lorebooks` | `lore_create()` | `app.py:1929` |
| POST | `/api/lorebooks/import` | `lore_import()` | `app.py:1535` |
| DELETE | `/api/lorebooks/{lid}` | `lore_delete()` | `app.py:2021` |
| GET | `/api/lorebooks/{lid}` | `lore_get()` | `app.py:1909` |
| PUT | `/api/lorebooks/{lid}` | `lore_edit()` | `app.py:1951` |
| POST | `/api/lorebooks/{lid}/apply_plan` | `lorebook_apply_plan()` | `app.py:1508` |
| POST | `/api/lorebooks/{lid}/entries` | `lore_entry_create()` | `app.py:2070` |
| GET | `/api/lorebooks/{lid}/export` | `lore_export()` | `app.py:2027` |
| POST | `/api/lorebooks/{lid}/generate` | `lore_generate()` | `app.py:2056` |
| GET | `/api/lorebooks/{lid}/generate_job` | `lorebook_generate_job()` | `app.py:1470` |
| POST | `/api/lorebooks/{lid}/generate_plan` | `lorebook_generate_plan()` | `app.py:1445` |
| GET | `/api/lorebooks/{lid}/links` | `lorebook_links_get()` | `app.py:1399` |
| POST | `/api/lorebooks/{lid}/links` | `lorebook_link_create()` | `app.py:1404` |
| POST | `/api/lorebooks/{lid}/move` | `lorebook_move()` | `app.py:1326` |
| POST | `/api/lorebooks/{lid}/reinterpret` | `lore_reinterpret_route()` | `app.py:2044` |
| POST | `/api/lorebooks/{lid}/reorder` | `lorebook_reorder()` | `app.py:1335` |
| GET | `/api/maintenance/checkpoints` | `maintenance_checkpoints()` | `app.py:1282` |
| POST | `/api/maintenance/checkpoints/compact` | `maintenance_compact()` | `app.py:1298` |
| PUT | `/api/max_output_tokens` | `put_max_output_tokens()` | `app.py:1200` |
| DELETE | `/api/memories/{mid}` | `mem_del()` | `app.py:3662` |
| PUT | `/api/memories/{mid}` | `mem_edit()` | `app.py:3641` |
| GET | `/api/memory/embeddings` | `memory_embeddings_status()` | `app.py:1029` |
| POST | `/api/memory/embeddings/rebuild` | `memory_embeddings_rebuild()` | `app.py:1044` |
| GET | `/api/nsfw` | `get_nsfw()` | `app.py:1230` |
| PUT | `/api/nsfw` | `set_nsfw()` | `app.py:1234` |
| GET | `/api/openrouter/endpoints` | `get_openrouter_endpoints()` | `app.py:1163` |
| PUT | `/api/openrouter_routing` | `put_openrouter_routing()` | `app.py:1149` |
| POST | `/api/personas` | `persona_create()` | `app.py:1851` |
| POST | `/api/personas/generate` | `persona_generate()` | `app.py:1841` |
| POST | `/api/personas/import` | `persona_import()` | `app.py:1871` |
| DELETE | `/api/personas/{pid}` | `persona_del()` | `app.py:1903` |
| PUT | `/api/personas/{pid}` | `persona_edit()` | `app.py:1894` |
| GET | `/api/personas/{pid}/export` | `persona_export()` | `app.py:1885` |
| POST | `/api/personas/{pid}/fill_appearance` | `persona_fill_appearance()` | `app.py:1812` |
| PUT | `/api/prompt_presets` | `save_preset()` | `app.py:1209` |
| DELETE | `/api/prompt_presets/{name}` | `del_preset()` | `app.py:1216` |
| POST | `/api/providers` | `add_provider()` | `app.py:1591` |
| DELETE | `/api/providers/{pid}` | `del_provider()` | `app.py:1670` |
| PUT | `/api/providers/{pid}` | `put_provider()` | `app.py:1598` |
| GET | `/api/providers/{pid}/image_models` | `image_models()` | `app.py:1682` |
| GET | `/api/providers/{pid}/models` | `models()` | `app.py:1675` |
| PUT | `/api/providers/{pid}/prompt_cache` | `put_provider_prompt_cache()` | `app.py:1625` |
| PUT | `/api/reasoning_effort` | `put_reasoning_effort()` | `app.py:1175` |
| POST | `/api/steps/{sid}/activate` | `step_activate()` | `app.py:4431` |
| POST | `/api/steps/{sid}/edit` | `step_edit()` | `app.py:4421` |
| POST | `/api/steps/{sid}/reroll` | `step_reroll()` | `app.py:4374` |
| DELETE | `/api/turns/{tid}` | `turn_del()` | `app.py:4444` |
| GET | `/api/turns/{tid}/ambience` | `turn_ambience()` | `app.py:4703` |
| POST | `/api/turns/{tid}/ambience` | `turn_ambience_resolve()` | `app.py:4720` |
| GET | `/api/turns/{tid}/backdrop` | `turn_backdrop()` | `app.py:4525` |
| POST | `/api/turns/{tid}/backdrop` | `turn_backdrop_generate()` | `app.py:4573` |
| POST | `/api/turns/{tid}/branch` | `turn_branch()` | `app.py:3732` |
| PUT | `/api/turns/{tid}/input` | `edit_input()` | `app.py:4124` |
| GET | `/api/turns/{tid}/narration` | `turn_narration_variants()` | `app.py:4191` |
| POST | `/api/turns/{tid}/narration` | `turn_narration_select()` | `app.py:4212` |
| GET | `/api/turns/{tid}/pipeline` | `pipeline_get()` | `app.py:4236` |
| PUT | `/api/turns/{tid}/prose` | `edit_prose()` | `app.py:4139` |
| POST | `/api/turns/{tid}/reroll` | `turn_reroll()` | `app.py:4305` |
| POST | `/api/turns/{tid}/rerun` | `turn_rerun()` | `app.py:4315` |
| POST | `/api/turns/{tid}/resume` | `turn_resume()` | `app.py:4342` |
| GET | `/api/updates/check` | `updates_check()` | `app.py:1274` |
| POST | `/api/updates/install` | `updates_install()` | `app.py:1278` |
| GET | `/guest` | `guest_page()` | `app.py:191` |
| GET | `/login` | `login_page()` | `app.py:203` |

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
| `relationship_events` | `id`, `chat_id`, `frame_id`, `char_id`, `target`, `axis`, `delta`, `triggers`, `note`, `provenance`, `turn_idx`, `created` |
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

### `static/js/app.js` (941 lines)

Sections: Boot & sidebar (`:1`); New chat wizard (`:218`); NSFW (`:661`); Composer (`:689`); Init (`:767`); Embedding reconciler progress (`:810`).

Declared functions: `boot()`, `renderSide()`, `renderChatSidebar()`, `newChatWizard()`, `renderWizardChoice()`, `wizardState()`, `wizardFromScratch()`, `renderWizardPersona()`, `renderWizardCharacters()`, `renderWizardScenario()`, `runWizard()`, `renderCharacterSidebar()`, `renderPersonaSidebar()`, `renderLegacyLoreSidebar()`, `updateNSFWBtn()`, `toggleNSFW()`, `resizeComposer()`, `erCard()`, `erDismiss()`, `erPoll()`, `erWatch()`, `erOfferRebuild()`.

### `static/js/backdrops.js` (422 lines)

Sections: Scene backdrops (`:2`).

Declared functions: `backdropLayers()`, `backdropLuminance()`, `applyBackdropContrast()`, `releaseBackdropLayer()`, `clearBackdrop()`, `showBackdrop()`, `backdropWorking()`, `awaitBackdrop()`, `generateBackdrop()`, `backdropForTurn()`, `backdropOnVisibleTurn()`, `backdropResetForRender()`, `updateBackdropBtn()`, `toggleBackdrops()`, `syncBackdrops()`.

### `static/js/chat.js` (2400 lines)

Sections: The turn being read (`:1`); Flipping between rerolls of the newest beat (`:642`); Pipeline drawer: reading a step through a lens (`:940`); Pipeline drawer (`:1146`); Relationship viewer (`:1482`); Memory browser (`:1554`); Private history (`:2342`).

Declared functions: `observeVisibleTurn()`, `openChat()`, `renderFrameBar()`, `switchFrame()`, `updateChatScopedButtons()`, `renderChat()`, `branchTurn()`, `editTurnInput()`, `editTurnProse()`, `liveReset()`, `friendlyPhase()`, `turnStatusStart()`, `turnStatusSet()`, `turnStatusStop()`, `_streamOn()`, `liveFlush()`, `liveAppend()`, `liveStep()`, `handleEvt()`, `showNarrationEarly()`, `clearNarrationEarly()`, `_mountRerollNav()`, `_paintRerollCount()`, `showRerollVariant()`, `abortActiveRun()`, `runStream()`, `confirmCheckpointRestore()`, `runReroll()`, `rerollTurn()`, `exportChat()`, `importChatModal()`, `perceiverViews()`, `loopMindIds()`, `stepLenses()`, `perceiverLabel()`, `facetBadge()`, `lensLabel()`, `renderLensBar()`, `lensSlice()`, `perceiverSlice()`, `mindSlice()`, `keySlice()`, `renderEngineNotes()`, `openPipeline()`, `relMeter()`, `relationshipModal()`, `memModal()`, `exportCharacterMemories()`, `importCharacterMemoriesModal()`, `memQS()`, `memCharId()`, `loadMemoryBrowse()`, `getMemUI()`, `renderMemorySummary()`, `sortedMems()`, `renderMemoryList()`, `memoryCard()`, `fieldWrap()`, `reloadMemView()`, `runMemorySearch()`, `showNewMemoryForm()`, `checkMemoryCoverage()`, `backfillMemoryEras()`, `consolidateMemories()`, `previewMemoryContext()`, `chatPH()`, `personaPH()`.

### `static/js/chime.js` (179 lines)

Sections: Turn-completion chime (`:2`); Which other waits are worth a chime (`:110`).

Declared functions: `chimeContext()`, `chimeArm()`, `chimePlay()`, `chimeWatches()`, `chimeWorkFinished()`, `chimeSetMuted()`, `toggleChimeMute()`, `updateChimeBtn()`.

### `static/js/components.js` (962 lines)

Sections: Modal (`:18`); Book covers (`:34`); confirm()/prompt() replacements (`:147`); Toasts (`:269`); Background tasks (`:297`); Form helpers (`:383`); Model picker (`:823`).

Declared functions: `el()`, `coverOfRow()`, `coverOfTitle()`, `modal()`, `modalOwnership()`, `closeModal()`, `closeAllModals()`, `_confirmOverlay()`, `confirmModal()`, `promptModal()`, `promptModalWithToggle()`, `toastHost()`, `toast()`, `renderActivity()`, `elapsedLabel()`, `activityTicking()`, `backgroundTask()`, `buttonTask()`, `loadingBlock()`, `emptyState()`, `fText()`, `fArea()`, `fSelect()`, `fNum()`, `fLineList()`, `fStrList()`, `fCoveragePicker()`, `fAttireGarments()`, `fList()`, `fAbilities()`, `fTraits()`, `fValues()`, `fBeliefs()`, `fCopingStrategies()`, `fAssociations()`, `fGoals()`, `fSenses()`, `fLatent()`, `fExtraParts()`, `fPronouns()`, `phEditor()`, `fetchModels()`, `fetchImageModels()`, `modelCombobox()`, `emitChange()`, `load()`, `showDD()`.

### `static/js/editors.js` (942 lines)

Sections: Background-character promotion (`:701`); Import (file upload) (`:750`); Generate (`:821`); Lorebook generate (`:839`); Lorebooks (`:856`); Export (`:930`).

Declared functions: `appearanceFillButton()`, `defaultCharacterSheet()`, `greetingCarousel()`, `quickStartModal()`, `charEditor()`, `personaEditor()`, `promotionReviewModal()`, `promoteBackgroundPresence()`, `importModal()`, `generateModal()`, `generateLoreModal()`, `loreModal()`, `exportCharacter()`, `exportPersona()`, `exportLorebook()`.

### `static/js/lorebooks.js` (3609 lines)

Sections: Library sidebar (`:241`); Data loading (`:448`); Workspace (`:545`); Book metadata and tree operations (`:1152`); Entry editor (`:1611`); Lorebook relationships (`:2356`); Advanced generator (`:2807`); Interrupted-generation recovery (`:3027`).

Declared functions: `loreBookTypeIcon()`, `loreLinkTypes()`, `normalizeLoreBook()`, `loreOwnershipKey()`, `loreBooksByParent()`, `loreBookMatches()`, `loreVisibleIds()`, `loreBookLabel()`, `parseStoredJSON()`, `loreField()`, `loreSelect()`, `loreBookOptions()`, `renderLoreLibrarySidebar()`, `renderNode()`, `loadLoreWorkspaceData()`, `collectLoreLinkTargets()`, `loreWorkspaceVisible()`, `renderLoreWorkspaceBody()`, `openLoreWorkspace()`, `renderLoreInspector()`, `selectTab()`, `buildLoreWorkspace()`, `renderWorkspaceTree()`, `renderNode()`, `renderTreeList()`, `renderLoreBookEditor()`, `moveLoreBook()`, `reorderLoreBook()`, `promoteLoreBook()`, `demoteLoreBook()`, `createSiblingLoreBook()`, `createLoreBookDialog()`, `refreshLoreUI()`, `renderLoreEntries()`, `renderList()`, `buildLoreEntryCard()`, `splitNumberList()`, `reinterpretLoreBook()`, `generateLoreEntriesPrompt()`, `buildDirectLoreRequest()`, `renderRelationshipOverview()`, `renderLoreRelationshipEditor()`, `renderRelationshipList()`, `showNewRelationshipForm()`, `renderLoreGenerator()`, `adoptGeneratorPlan()`, `generatorPlanMessage()`, `loreGenAgo()`, `refreshLoreGenRecovery()`, `normalizeGeneratorPlan()`, `renderLorePlanPreview()`, `renderOperations()`, `planStat()`, `renderAnalysisSection()`, `addPlanGroup()`, `stripPlanUIFields()`, `acceptedGeneratorPlan()`.

### `static/js/settings.js` (2880 lines)

Sections: Chat tool modals (`:1`); Condition tab (`:544`); Survival tracker (`:604`); Character relocation (`:843`); API connections (`:1534`); Software updates (host-only; git fast-forward from GitHub origin) (`:2582`); Legacy checkpoint conversion (host-only maintenance) (`:2614`); Prompts (`:2848`).

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
