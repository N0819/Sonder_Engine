# Generated Code Map

> Regenerate with `python tools/generate_code_map.py`. Do not hand-edit this file.

## Python modules

| Module | Lines | Purpose | Local dependencies |
|---|---:|---|---|
| `affect.py` | 1852 |  | `theory_of_mind` |
| `agents/__init__.py` | 86 | Backward-compatible facade for the role-specific agent package. | `agents.character`, `agents.common`, `agents.director`, `agents.loops`, `agents.mapping`, `agents.narration`, `agents.perception`, `agents.runtime`, `agents.storage`, `scene` |
| `agents/background.py` | 809 |  | `agents.common`, `background_claims`, `character_schema`, `commit`, `db`, `prompts`, `scene`, `schemas`, `spatial` |
| `agents/character.py` | 2227 | Private character decision agent. | `affect`, `agents.common`, `character_schema`, `db`, `frames`, `memory`, `place_purpose`, `prompts`, `psychology_runtime`, `scene`, `schemas`, `spatial`, `survival`, `theory_of_mind` |
| `agents/common.py` | 4277 | Shared normalization, lore, delivery, and perception helpers. | `attire`, `character_schema`, `db`, `llm_quality`, `memory`, `providers`, `scene`, `schemas`, `spatial`, `theory_of_mind` |
| `agents/director.py` | 3643 | Scene establishment, player interpretation, and objective resolution. | `agents.common`, `attire`, `character_schema`, `db`, `memory`, `paradox`, `prompts`, `providers`, `scene`, `schemas`, `spatial` |
| `agents/loops.py` | 553 | Reaction loops, interaction rounds, and deterministic micro-perception. | `agents.character`, `agents.common`, `character_schema`, `db`, `scene`, `spatial` |
| `agents/mapping.py` | 202 | Lore routing, cached recall, and retrieval staging. | `agents.common`, `character_schema`, `db`, `memory`, `prompts`, `scene` |
| `agents/narration.py` | 883 | Player-facing narration agent. | `agents.common`, `character_schema`, `db`, `prompts`, `scene`, `schemas`, `spatial` |
| `agents/perception.py` | 2473 | Opening, action-onset, and outcome observer views. | `affect`, `agents.common`, `character_schema`, `db`, `prompts`, `scene`, `spatial` |
| `agents/runtime.py` | 977 | Pipeline plans, dispatch, streaming, cancellation, resume, and reruns. | `agents.background`, `agents.character`, `agents.common`, `agents.director`, `agents.loops`, `agents.mapping`, `agents.narration`, `agents.perception`, `agents.storage`, `character_schema`, `checkpoints`, `commit`, `db`, `pipeline_context`, `providers`, `scene` |
| `agents/storage.py` | 92 | Step and active-variant persistence helpers. | `db` |
| `ambience.py` | 2043 |  | `backdrops`, `db`, `weather` |
| `app.py` | 4374 | FastAPI application assembly, resource CRUD, turn control, and streaming endpoints. | `agents`, `ambience`, `attire`, `auth_routes`, `backdrops`, `character_schema`, `chat_archive`, `checkpoints`, `commit`, `db`, `frames`, `greetings`, `guest_access`, `importers`, `memory`, `paradox`, `pipeline_context`, `prompts`, `providers`, `scene`, `survival`, `updates` |
| `attire.py` | 1195 |  | — |
| `auth_routes.py` | 143 | Typed host-authentication HTTP routes and cookie transport. | `guest_access` |
| `authored_events.py` | 124 |  | `db` |
| `backdrops.py` | 1143 |  | `db`, `spatial`, `weather` |
| `background_claims.py` | 287 |  | `db` |
| `character_schema.py` | 1319 | Versioned character/persona defaults, normalization, accessors, and export payloads. | `attire`, `schemas` |
| `chat_archive.py` | 1089 | Typed, atomic chat archive export/import service and HTTP routes. | `character_schema`, `checkpoints`, `db`, `memory`, `schemas` |
| `checkpoints.py` | 1016 | Whole-chat snapshots and checkpoint restore orchestration. | `db`, `memory` |
| `comfort.py` | 295 |  | `spatial` |
| `commit.py` | 5607 | Validated persistence of scene, entities, cast, lore, relationships, events, and memories. | `affect`, `attire`, `character_schema`, `comfort`, `db`, `frames`, `mechanics`, `memory`, `paradox`, `prompts`, `providers`, `psychology_runtime`, `scene`, `spatial`, `spatial_frames`, `survival`, `theory_of_mind`, `weather` |
| `db.py` | 1447 | SQLite schema, migrations, connection management, transactions, and key/value world access. | — |
| `frames.py` | 193 |  | `db` |
| `greetings.py` | 375 |  | `agents.runtime`, `agents.storage`, `character_schema`, `db`, `llm_quality`, `memory`, `prompts` |
| `guest_access.py` | 328 |  | `db` |
| `importers.py` | 2462 | Native and AI-assisted character, persona, and lorebook import/generation. | `character_schema`, `db`, `memory`, `prompts`, `providers` |
| `llm_quality.py` | 292 | Strict JSON parsing, schema validation, and model-assisted repair. | `providers`, `schemas` |
| `logging_utils.py` | 118 | Structured timing and observability helpers. | — |
| `mechanics.py` | 274 |  | `spatial`, `spatial_frames` |
| `memory.py` | 3626 | Lorebook graph, memory retrieval/consolidation, relationships, and vector search. | `db`, `frames`, `logging_utils`, `prompts`, `providers`, `theory_of_mind` |
| `paradox.py` | 489 |  | `character_schema`, `db`, `frames` |
| `pipeline_context.py` | 184 | Typed mutable context passed through a turn pipeline. | `db` |
| `pipeline_trace.py` | 413 | Privacy-conscious export, validation, and offline replay of persisted pipeline history. | `db` |
| `place_purpose.py` | 532 |  | `comfort`, `spatial`, `survival`, `theory_of_mind` |
| `prompt_cache.py` | 79 | Provider-specific prompt-cache helpers. | `providers` |
| `prompts.py` | 3470 | Default system prompts and prompt preset access. | `db` |
| `providers.py` | 1977 | Provider selection, retries, streaming, cancellation, model listing, and embeddings. | `db` |
| `psychology_runtime.py` | 493 |  | — |
| `scene.py` | 1234 | Scene/cast/persona helpers, recent events, dialogue configuration, and private knowledge. | `attire`, `character_schema`, `db`, `spatial` |
| `schemas.py` | 3500 | Pydantic output contracts and semantic validation for agent payloads. | — |
| `spatial.py` | 4638 | Deterministic room, barrier, hearing, visibility, placement, and scene-diff logic. | `schemas`, `spatial_orientation` |
| `spatial_frames.py` | 975 |  | `character_schema`, `db`, `frames`, `paradox`, `scene`, `spatial` |
| `spatial_orientation.py` | 184 | Bearing math and reciprocal spatial-edge normalization. | — |
| `survival.py` | 320 |  | `db` |
| `theory_of_mind.py` | 703 |  | — |
| `updates.py` | 394 |  | — |
| `weather.py` | 808 |  | `spatial` |

## Largest top-level functions

### `affect.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_project_ops()` | 1079 | 137 lines |
| `resolve_affect()` | 585 | 134 lines |
| `apply_intent_ops()` | 907 | 126 lines |
| `appraise()` | 384 | 120 lines |
| `normalize_wants()` | 725 | 82 lines |
| `validate_drive_shift()` | 1635 | 79 lines |
| `update_drive_strain()` | 1516 | 77 lines |
| `goal_slot_currency()` | 1346 | 65 lines |

### `agents/background.py`

| Function | Start | Size |
|---|---:|---:|
| `scene_life()` | 425 | 105 lines |
| `_beat_for_presence()` | 105 | 62 lines |
| `_react_one()` | 755 | 55 lines |
| `background_react()` | 191 | 52 lines |
| `managed_presences()` | 321 | 46 lines |
| `_mint_blurbs()` | 592 | 45 lines |
| `_present_others()` | 708 | 45 lines |
| `_audience_map()` | 369 | 32 lines |

### `agents/character.py`

| Function | Start | Size |
|---|---:|---:|
| `character_step()` | 1599 | 629 lines |
| `_annotate_known_exits()` | 1020 | 445 lines |
| `_destination_from_goals()` | 598 | 109 lines |
| `sprint_offers()` | 1500 | 97 lines |
| `_verdict()` | 442 | 72 lines |
| `_annotate_goal_currency()` | 883 | 67 lines |
| `_en_route()` | 952 | 66 lines |
| `_unbidden_trigger()` | 257 | 54 lines |

### `agents/common.py`

| Function | Start | Size |
|---|---:|---:|
| `norm_sequence()` | 1070 | 161 lines |
| `_scrub_invented_dialogue()` | 3325 | 145 lines |
| `_extract_authority_claims()` | 810 | 106 lines |
| `_check_quote_attribution()` | 3863 | 91 lines |
| `_check_narrator_fidelity()` | 4130 | 84 lines |
| `_check_player_act_authority()` | 2417 | 81 lines |
| `_perceptible_entities()` | 433 | 78 lines |
| `authored_other_subject()` | 595 | 77 lines |

### `agents/director.py`

| Function | Start | Size |
|---|---:|---:|
| `director_resolve()` | 2692 | 952 lines |
| `director_interpret()` | 321 | 334 lines |
| `_reconcile_resolution()` | 2224 | 302 lines |
| `_reconcile_interpretation()` | 803 | 119 lines |
| `director_establish()` | 165 | 105 lines |
| `_awareness_exits()` | 1425 | 98 lines |
| `_evidence_present()` | 1988 | 97 lines |
| `_guard_approach_is_not_arrival()` | 2610 | 80 lines |

### `agents/loops.py`

| Function | Start | Size |
|---|---:|---:|
| `interaction_loop()` | 183 | 300 lines |
| `deterministic_micro_perception()` | 42 | 96 lines |
| `reaction_loop()` | 484 | 70 lines |
| `_defer_to_focus()` | 153 | 28 lines |
| `_drop_non_awake()` | 139 | 12 lines |

### `agents/mapping.py`

| Function | Start | Size |
|---|---:|---:|
| `mapping_stage()` | 32 | 98 lines |
| `mapping_quick()` | 131 | 72 lines |

### `agents/narration.py`

| Function | Start | Size |
|---|---:|---:|
| `narrator()` | 550 | 197 lines |
| `narrator_extra()` | 748 | 136 lines |
| `_visible_portal_states()` | 414 | 100 lines |
| `_ordered_beat_events()` | 242 | 83 lines |
| `_position_delta_payload()` | 358 | 54 lines |
| `_resolve_narration_person()` | 71 | 47 lines |
| `_generate_narration()` | 516 | 33 lines |
| `_player_sees_character()` | 327 | 29 lines |

### `agents/perception.py`

| Function | Start | Size |
|---|---:|---:|
| `perception_outcome()` | 1769 | 705 lines |
| `perception_act()` | 1171 | 429 lines |
| `perception_establish()` | 1003 | 167 lines |
| `_observer_scene_payload()` | 321 | 106 lines |
| `_redact_concealed_from_event()` | 1702 | 66 lines |
| `_strip_self_narration()` | 677 | 62 lines |
| `_touch_only_sources()` | 1601 | 62 lines |
| `_source_channels()` | 512 | 56 lines |

### `agents/runtime.py`

| Function | Start | Size |
|---|---:|---:|
| `_run_pipeline()` | 583 | 341 lines |
| `build_plan()` | 382 | 81 lines |
| `resume_key_for_turn()` | 327 | 54 lines |
| `run_pipeline()` | 925 | 53 lines |
| `_load_extra_players()` | 40 | 52 lines |
| `_stream_one()` | 218 | 48 lines |
| `_stream_parallel()` | 267 | 45 lines |
| `_rehydrate_loop_results()` | 535 | 41 lines |

### `agents/storage.py`

| Function | Start | Size |
|---|---:|---:|
| `save_step()` | 10 | 28 lines |
| `mark_steps_stale()` | 62 | 12 lines |
| `delete_step()` | 83 | 10 lines |
| `_set_steps_stale()` | 54 | 7 lines |
| `clear_steps_stale()` | 75 | 7 lines |
| `active_content()` | 39 | 5 lines |
| `variant_count()` | 45 | 4 lines |
| `step_is_stale()` | 50 | 3 lines |

### `ambience.py`

| Function | Start | Size |
|---|---:|---:|
| `resolve_ambience()` | 1670 | 203 lines |
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
| `turn_branch()` | 3361 | 387 lines |
| `_remap_cp_blob()` | 621 | 187 lines |
| `chat_get()` | 2136 | 118 lines |
| `_stream()` | 247 | 80 lines |
| `lore_entry_edit()` | 1925 | 70 lines |
| `lore_edit()` | 1777 | 68 lines |
| `_ambience_payload()` | 4161 | 63 lines |
| `chat_positions_get()` | 2735 | 62 lines |

### `attire.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_regions()` | 256 | 117 lines |
| `dedupe_regions()` | 579 | 82 lines |
| `coerce_diff_shape()` | 711 | 77 lines |
| `resolve_garment()` | 509 | 68 lines |
| `decisive_targets()` | 807 | 67 lines |
| `apply_flat_change()` | 999 | 66 lines |
| `advance()` | 876 | 56 lines |
| `describe()` | 951 | 46 lines |

### `auth_routes.py`

| Function | Start | Size |
|---|---:|---:|
| `auth_setup()` | 69 | 36 lines |
| `auth_login()` | 108 | 28 lines |
| `_set_host_cookie()` | 47 | 9 lines |
| `auth_status()` | 59 | 7 lines |
| `auth_logout()` | 139 | 5 lines |

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
| `room_projection()` | 495 | 69 lines |
| `generate_backdrop()` | 1001 | 61 lines |
| `visual_signature()` | 106 | 46 lines |
| `request_backdrop()` | 1105 | 39 lines |
| `build_backdrop_request()` | 665 | 37 lines |
| `scene_after_turn()` | 628 | 35 lines |
| `branch_lineage()` | 185 | 34 lines |
| `compose_prompt()` | 773 | 34 lines |

### `background_claims.py`

| Function | Start | Size |
|---|---:|---:|
| `novel_proper_nouns()` | 148 | 39 lines |
| `settle_claims()` | 234 | 36 lines |
| `record_claims()` | 189 | 27 lines |
| `_known_variants()` | 123 | 17 lines |
| `claimant_credence()` | 272 | 16 lines |
| `unratified_claims()` | 218 | 14 lines |
| `is_title_only()` | 112 | 9 lines |
| `_strip_titles()` | 103 | 7 lines |

### `character_schema.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_character_data()` | 804 | 155 lines |
| `default_character_data()` | 391 | 88 lines |
| `_normalize_psychology()` | 238 | 80 lines |
| `repair_character_shape()` | 745 | 57 lines |
| `character_initial_active_state()` | 1120 | 48 lines |
| `normalize_persona_data()` | 960 | 47 lines |
| `_coerce_appearance()` | 666 | 45 lines |
| `_as_profile_list()` | 38 | 36 lines |

### `chat_archive.py`

| Function | Start | Size |
|---|---:|---:|
| `_model_validate()` | 54 | 4 lines |
| `_model_dump()` | 60 | 4 lines |

### `checkpoints.py`

| Function | Start | Size |
|---|---:|---:|
| `snapshot_state()` | 15 | 146 lines |
| `_restore_checkpoint_body()` | 490 | 136 lines |
| `compact_checkpoints()` | 735 | 118 lines |
| `_restore_books()` | 162 | 104 lines |
| `insert_world_tables()` | 341 | 81 lines |
| `ensure_checkpoint()` | 919 | 53 lines |
| `_verify_no_loss()` | 683 | 50 lines |
| `refresh_checkpoint()` | 973 | 44 lines |

### `comfort.py`

| Function | Start | Size |
|---|---:|---:|
| `_derive()` | 195 | 82 lines |
| `_is_body()` | 137 | 21 lines |
| `_posture_of()` | 173 | 20 lines |
| `_entity_record()` | 123 | 12 lines |
| `_station_of()` | 160 | 11 lines |
| `comfort_level()` | 279 | 8 lines |
| `rest_affording()` | 289 | 7 lines |
| `_tokens()` | 100 | 6 lines |

### `commit.py`

| Function | Start | Size |
|---|---:|---:|
| `prepare_memory_commit()` | 4257 | 993 lines |
| `prepare_scene_commit()` | 1644 | 445 lines |
| `track_background_presences()` | 2730 | 225 lines |
| `commit_world_entities()` | 2226 | 168 lines |
| `_prepare_destruction()` | 697 | 158 lines |
| `update_place_graph()` | 72 | 153 lines |
| `prepare_mapping_commit()` | 3572 | 133 lines |
| `commit_mapping()` | 3707 | 120 lines |

### `db.py`

| Function | Start | Size |
|---|---:|---:|
| `init()` | 1354 | 50 lines |
| `conn()` | 1201 | 38 lines |
| `transaction()` | 1241 | 36 lines |
| `_backfill_resource_uids()` | 1336 | 17 lines |
| `qi()` | 1299 | 16 lines |
| `data_version()` | 1278 | 14 lines |
| `parse_scoped_world_key()` | 52 | 13 lines |
| `_execute_retry()` | 1170 | 13 lines |

### `frames.py`

| Function | Start | Size |
|---|---:|---:|
| `is_memory_visible()` | 126 | 55 lines |
| `get_frame()` | 67 | 23 lines |
| `create_frame()` | 98 | 19 lines |
| `is_recognized_in_frame()` | 183 | 11 lines |
| `frame_ordinal()` | 119 | 5 lines |
| `list_frames()` | 92 | 4 lines |

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
| `redeem_code()` | 205 | 48 lines |
| `verify_host_login()` | 87 | 26 lines |
| `list_grants()` | 303 | 26 lines |
| `create_host_account()` | 62 | 23 lines |
| `verify_guest_token()` | 255 | 19 lines |
| `revoke_persona_grants()` | 276 | 13 lines |
| `revoke_grant()` | 291 | 10 lines |
| `create_host_session()` | 115 | 9 lines |

### `importers.py`

| Function | Start | Size |
|---|---:|---:|
| `import_lorebook()` | 1236 | 146 lines |
| `apply_lorebook_plan()` | 2274 | 124 lines |
| `_lore_gen_entry_batch()` | 1926 | 118 lines |
| `_run_lore_gen_job()` | 2048 | 112 lines |
| `fill_appearance()` | 986 | 92 lines |
| `import_character()` | 535 | 91 lines |
| `_lore_gen_structure()` | 1856 | 66 lines |
| `_lore_gen_context()` | 1679 | 65 lines |

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

### `mechanics.py`

| Function | Start | Size |
|---|---:|---:|
| `_fire_due_events()` | 110 | 63 lines |
| `_schedule_new_arrivals()` | 175 | 44 lines |
| `mechanics_sweep()` | 233 | 42 lines |
| `news_latency_seconds()` | 90 | 10 lines |
| `_expire_conditions()` | 221 | 10 lines |
| `stable_event_key()` | 68 | 6 lines |
| `_payload_of()` | 102 | 6 lines |

### `memory.py`

| Function | Start | Size |
|---|---:|---:|
| `search_memories()` | 1535 | 219 lines |
| `rebuild_checkpoint_embeddings()` | 3263 | 124 lines |
| `contrast_memory()` | 1789 | 117 lines |
| `rebuild_embeddings()` | 3108 | 116 lines |
| `consolidate_character_memory()` | 2104 | 95 lines |
| `restore_lorebook()` | 2668 | 79 lines |
| `monitoring_subtree()` | 580 | 78 lines |
| `resolve_lorebook_graph()` | 392 | 76 lines |

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
| `get_prompt()` | 3461 | 10 lines |
| `presets()` | 3452 | 2 lines |
| `active_preset()` | 3455 | 2 lines |
| `nsfw_enabled()` | 3458 | 2 lines |

### `providers.py`

| Function | Start | Size |
|---|---:|---:|
| `_chat_complete_once()` | 1356 | 206 lines |
| `async chat_complete_async()` | 1563 | 88 lines |
| `chat_complete()` | 1202 | 83 lines |
| `async _chat_complete_async_once()` | 1652 | 78 lines |
| `_sse_openai()` | 1096 | 62 lines |
| `async _sse_openai_async()` | 1731 | 53 lines |
| `resolve_role_candidates()` | 941 | 52 lines |
| `list_models()` | 1866 | 51 lines |

### `psychology_runtime.py`

| Function | Start | Size |
|---|---:|---:|
| `resolve_hedonic()` | 96 | 138 lines |
| `resolve_stress()` | 236 | 80 lines |
| `apply_belief_updates()` | 326 | 57 lines |
| `cognitive_absorption()` | 449 | 45 lines |
| `apply_association_updates()` | 385 | 44 lines |
| `elapsed_psych_units()` | 79 | 15 lines |
| `_float()` | 11 | 6 lines |
| `_authored_beliefs()` | 318 | 6 lines |

### `scene.py`

| Function | Start | Size |
|---|---:|---:|
| `recent_events_for_observer()` | 698 | 59 lines |
| `director_context()` | 758 | 53 lines |
| `awareness_conditions()` | 419 | 47 lines |
| `private_knowledge_for()` | 1191 | 44 lines |
| `_seed_scene_initial_attire()` | 84 | 31 lines |
| `active_cast()` | 116 | 31 lines |
| `active_disguises()` | 311 | 31 lines |
| `normalize_style_guide()` | 1099 | 31 lines |

### `schemas.py`

| Function | Start | Size |
|---|---:|---:|
| `preprocess_llm_output()` | 2675 | 243 lines |
| `_lenient_coerce()` | 517 | 159 lines |
| `semantic_output_errors()` | 3294 | 113 lines |
| `validate_llm_output_strict()` | 3444 | 57 lines |
| `_coerce_conditions()` | 2447 | 50 lines |
| `_declared()` | 357 | 48 lines |
| `_coerce_station_table()` | 49 | 41 lines |
| `_coerce_evidence_refs()` | 1723 | 41 lines |

### `spatial.py`

| Function | Start | Size |
|---|---:|---:|
| `merge_scene_with_diff()` | 4353 | 241 lines |
| `sprint_reach()` | 3241 | 175 lines |
| `apply_transit_dock_edges()` | 3954 | 165 lines |
| `apply_contact_ops()` | 2722 | 149 lines |
| `contacts_from_entity_state()` | 2306 | 137 lines |
| `visible_adjacent_rooms()` | 3486 | 117 lines |
| `derive_scene_stations()` | 1321 | 104 lines |
| `hear_level()` | 750 | 100 lines |

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
| `normalize_scene_bearings()` | 118 | 67 lines |
| `travel_bearing()` | 98 | 18 lines |
| `relative_bearing()` | 62 | 11 lines |
| `lateral_of()` | 75 | 11 lines |
| `normalize_bearing()` | 47 | 9 lines |
| `_find_edge()` | 88 | 8 lines |
| `opposite_bearing()` | 58 | 2 lines |

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
| GET | `/` | `index()` | `app.py:166` |
| PUT | `/api/active_preset` | `set_active()` | `app.py:1133` |
| PUT | `/api/agent_models` | `put_agent_models()` | `app.py:945` |
| PUT | `/api/ambience` | `put_ambience()` | `app.py:1027` |
| GET | `/api/ambience/library` | `ambience_library()` | `app.py:4314` |
| GET | `/api/ambience/search` | `ambience_search()` | `app.py:4293` |
| PUT | `/api/attire_beneath` | `set_attire_beneath()` | `app.py:1147` |
| POST | `/api/auth/login` | `auth_login()` | `auth_routes.py:108` |
| POST | `/api/auth/logout` | `auth_logout()` | `auth_routes.py:139` |
| POST | `/api/auth/setup` | `auth_setup()` | `auth_routes.py:69` |
| GET | `/api/auth/status` | `auth_status()` | `auth_routes.py:59` |
| GET | `/api/auto_promote` | `get_auto_promote()` | `app.py:2348` |
| PUT | `/api/auto_promote` | `set_auto_promote()` | `app.py:2352` |
| PUT | `/api/backdrops` | `put_backdrops()` | `app.py:1017` |
| GET | `/api/bootstrap` | `bootstrap()` | `app.py:890` |
| POST | `/api/characters` | `char_create()` | `app.py:1528` |
| POST | `/api/characters/generate` | `char_generate()` | `app.py:1518` |
| POST | `/api/characters/import` | `char_import()` | `app.py:1549` |
| DELETE | `/api/characters/{cid}` | `char_del()` | `app.py:1660` |
| PUT | `/api/characters/{cid}` | `char_edit()` | `app.py:1651` |
| GET | `/api/characters/{cid}/export` | `char_export()` | `app.py:1643` |
| POST | `/api/characters/{cid}/fill_appearance` | `char_fill_appearance()` | `app.py:1633` |
| POST | `/api/characters/{cid}/fill_psychology` | `char_fill_psychology()` | `app.py:1607` |
| POST | `/api/characters/{cid}/generate_greeting` | `char_generate_greeting()` | `app.py:1592` |
| POST | `/api/characters/{cid}/recover_greetings` | `char_recover_greetings()` | `app.py:1582` |
| POST | `/api/characters/{cid}/start` | `character_start_story()` | `app.py:1564` |
| POST | `/api/chats` | `chat_new()` | `app.py:2004` |
| POST | `/api/chats/import` | `import_chat()` | `chat_archive.py:172` |
| DELETE | `/api/chats/{cid}` | `chat_del()` | `app.py:2106` |
| GET | `/api/chats/{cid}` | `chat_get()` | `app.py:2136` |
| PUT | `/api/chats/{cid}` | `chat_edit()` | `app.py:2010` |
| POST | `/api/chats/{cid}/abort` | `chat_abort()` | `app.py:3357` |
| GET | `/api/chats/{cid}/ambience/oneshot/{name}` | `ambience_oneshot()` | `app.py:4323` |
| DELETE | `/api/chats/{cid}/ambience/pin` | `ambience_pin_delete()` | `app.py:4371` |
| PUT | `/api/chats/{cid}/ambience/pin` | `ambience_pin_put()` | `app.py:4352` |
| GET | `/api/chats/{cid}/ambience/pins` | `ambience_pins_get()` | `app.py:4347` |
| GET | `/api/chats/{cid}/ambience/{signature}.audio` | `ambience_audio()` | `app.py:4277` |
| GET | `/api/chats/{cid}/attire` | `attire_get()` | `app.py:2936` |
| PUT | `/api/chats/{cid}/attire` | `attire_put()` | `app.py:2943` |
| GET | `/api/chats/{cid}/backdrop/{signature}.png` | `backdrop_image()` | `app.py:4129` |
| GET | `/api/chats/{cid}/background_config` | `bg_cfg_get()` | `app.py:3018` |
| PUT | `/api/chats/{cid}/background_config` | `bg_cfg_put()` | `app.py:3022` |
| POST | `/api/chats/{cid}/characters` | `chat_add_char()` | `app.py:2256` |
| DELETE | `/api/chats/{cid}/characters/{ch}` | `chat_del_char()` | `app.py:2583` |
| PUT | `/api/chats/{cid}/characters/{ch}/card` | `chat_char_card_put()` | `app.py:2593` |
| GET | `/api/chats/{cid}/characters/{ch}/memories` | `mem_list()` | `app.py:3148` |
| POST | `/api/chats/{cid}/characters/{ch}/memories` | `mem_add()` | `app.py:3250` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/consolidate` | `mem_consolidate()` | `app.py:3239` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/export` | `mem_export()` | `app.py:3194` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/import` | `mem_import()` | `app.py:3205` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/search` | `mem_search()` | `app.py:3169` |
| GET | `/api/chats/{cid}/characters/{ch}/memory-context` | `memory_context_preview()` | `app.py:3215` |
| PUT | `/api/chats/{cid}/characters/{ch}/position` | `chat_char_position_put()` | `app.py:2799` |
| GET | `/api/chats/{cid}/characters/{ch}/private_history` | `ph_get()` | `app.py:2859` |
| PUT | `/api/chats/{cid}/characters/{ch}/private_history` | `ph_put()` | `app.py:2869` |
| GET | `/api/chats/{cid}/characters/{ch}/relationships` | `relationships_get()` | `app.py:3228` |
| GET | `/api/chats/{cid}/dialogue_config` | `dlg_get()` | `app.py:2978` |
| PUT | `/api/chats/{cid}/dialogue_config` | `dlg_put()` | `app.py:2982` |
| GET | `/api/chats/{cid}/dramatic_irony` | `get_dramatic_irony_feed()` | `app.py:2310` |
| GET | `/api/chats/{cid}/export` | `export_chat()` | `chat_archive.py:166` |
| GET | `/api/chats/{cid}/fixed_points` | `fixed_points_list()` | `app.py:3094` |
| POST | `/api/chats/{cid}/fixed_points` | `fixed_points_create()` | `app.py:3104` |
| DELETE | `/api/chats/{cid}/fixed_points/{anchor_id}` | `fixed_points_delete()` | `app.py:3126` |
| GET | `/api/chats/{cid}/frames` | `frames_list()` | `app.py:3048` |
| POST | `/api/chats/{cid}/frames` | `frames_create()` | `app.py:3052` |
| GET | `/api/chats/{cid}/guest_invites` | `list_guest_invites()` | `app.py:2496` |
| POST | `/api/chats/{cid}/guest_invites` | `create_guest_invite()` | `app.py:2478` |
| DELETE | `/api/chats/{cid}/guest_invites/{gid}` | `revoke_guest_invite()` | `app.py:2500` |
| DELETE | `/api/chats/{cid}/lorebook` | `detach_lore()` | `app.py:2097` |
| POST | `/api/chats/{cid}/lorebook` | `bind_lore()` | `app.py:2081` |
| GET | `/api/chats/{cid}/lorebooks` | `chat_lorebooks_owned()` | `app.py:1232` |
| POST | `/api/chats/{cid}/lorebooks` | `attach_lore()` | `app.py:2041` |
| DELETE | `/api/chats/{cid}/lorebooks/{lid}` | `detach_book()` | `app.py:2066` |
| GET | `/api/chats/{cid}/paradox_policy` | `paradox_policy_get()` | `app.py:3079` |
| PUT | `/api/chats/{cid}/paradox_policy` | `paradox_policy_put()` | `app.py:3083` |
| GET | `/api/chats/{cid}/persona_private_history` | `pph_get()` | `app.py:2878` |
| PUT | `/api/chats/{cid}/persona_private_history` | `pph_put()` | `app.py:2891` |
| GET | `/api/chats/{cid}/personas` | `chat_list_extra_personas()` | `app.py:2357` |
| POST | `/api/chats/{cid}/personas` | `chat_add_persona()` | `app.py:2402` |
| DELETE | `/api/chats/{cid}/personas/{pid}` | `chat_del_persona()` | `app.py:2426` |
| PUT | `/api/chats/{cid}/personas/{pid}/station` | `chat_persona_station()` | `app.py:2367` |
| GET | `/api/chats/{cid}/positions` | `chat_positions_get()` | `app.py:2735` |
| GET | `/api/chats/{cid}/promises` | `get_promise_ledger()` | `app.py:2314` |
| GET | `/api/chats/{cid}/promotable` | `list_promotable_presences()` | `app.py:2306` |
| POST | `/api/chats/{cid}/promotions/confirm` | `confirm_promotion()` | `app.py:2331` |
| POST | `/api/chats/{cid}/promotions/draft` | `draft_promotion()` | `app.py:2318` |
| GET | `/api/chats/{cid}/style_guide` | `style_guide_get()` | `app.py:2961` |
| PUT | `/api/chats/{cid}/style_guide` | `style_guide_put()` | `app.py:2967` |
| GET | `/api/chats/{cid}/survival` | `survival_get()` | `app.py:2650` |
| PUT | `/api/chats/{cid}/survival` | `survival_put()` | `app.py:2655` |
| POST | `/api/chats/{cid}/turns` | `turn_new()` | `app.py:3297` |
| POST | `/api/chats/{cid}/turns/{idx}/player_input` | `submit_extra_player_input()` | `app.py:2440` |
| GET | `/api/chats/{cid}/vitals` | `chat_vitals_get()` | `app.py:2702` |
| GET | `/api/chats/{cid}/world` | `world_get()` | `app.py:2896` |
| PUT | `/api/chats/{cid}/world` | `world_put()` | `app.py:2900` |
| POST | `/api/guest/input` | `guest_input()` | `app.py:2558` |
| GET | `/api/guest/state` | `guest_state()` | `app.py:2524` |
| PUT | `/api/image_model` | `put_image_model()` | `app.py:995` |
| POST | `/api/join` | `join_with_code()` | `app.py:2506` |
| DELETE | `/api/lore_entries/{eid}` | `lore_entry_delete()` | `app.py:1997` |
| PUT | `/api/lore_entries/{eid}` | `lore_entry_edit()` | `app.py:1925` |
| DELETE | `/api/lore_gen_jobs/{job_id}` | `lorebook_generate_discard()` | `app.py:1387` |
| POST | `/api/lore_gen_jobs/{job_id}/resume` | `lorebook_generate_resume()` | `app.py:1369` |
| DELETE | `/api/lorebook_links/{link_id}` | `lorebook_link_delete()` | `app.py:1328` |
| PUT | `/api/lorebook_links/{link_id}` | `lorebook_link_update()` | `app.py:1314` |
| POST | `/api/lorebooks` | `lore_create()` | `app.py:1755` |
| POST | `/api/lorebooks/import` | `lore_import()` | `app.py:1423` |
| DELETE | `/api/lorebooks/{lid}` | `lore_delete()` | `app.py:1847` |
| GET | `/api/lorebooks/{lid}` | `lore_get()` | `app.py:1735` |
| PUT | `/api/lorebooks/{lid}` | `lore_edit()` | `app.py:1777` |
| POST | `/api/lorebooks/{lid}/apply_plan` | `lorebook_apply_plan()` | `app.py:1396` |
| POST | `/api/lorebooks/{lid}/entries` | `lore_entry_create()` | `app.py:1896` |
| GET | `/api/lorebooks/{lid}/export` | `lore_export()` | `app.py:1853` |
| POST | `/api/lorebooks/{lid}/generate` | `lore_generate()` | `app.py:1882` |
| GET | `/api/lorebooks/{lid}/generate_job` | `lorebook_generate_job()` | `app.py:1358` |
| POST | `/api/lorebooks/{lid}/generate_plan` | `lorebook_generate_plan()` | `app.py:1333` |
| GET | `/api/lorebooks/{lid}/links` | `lorebook_links_get()` | `app.py:1287` |
| POST | `/api/lorebooks/{lid}/links` | `lorebook_link_create()` | `app.py:1292` |
| POST | `/api/lorebooks/{lid}/move` | `lorebook_move()` | `app.py:1214` |
| POST | `/api/lorebooks/{lid}/reinterpret` | `lore_reinterpret_route()` | `app.py:1870` |
| POST | `/api/lorebooks/{lid}/reorder` | `lorebook_reorder()` | `app.py:1223` |
| GET | `/api/maintenance/checkpoints` | `maintenance_checkpoints()` | `app.py:1170` |
| POST | `/api/maintenance/checkpoints/compact` | `maintenance_compact()` | `app.py:1186` |
| PUT | `/api/max_output_tokens` | `put_max_output_tokens()` | `app.py:1108` |
| DELETE | `/api/memories/{mid}` | `mem_del()` | `app.py:3291` |
| PUT | `/api/memories/{mid}` | `mem_edit()` | `app.py:3272` |
| GET | `/api/memory/embeddings` | `memory_embeddings_status()` | `app.py:968` |
| POST | `/api/memory/embeddings/rebuild` | `memory_embeddings_rebuild()` | `app.py:983` |
| GET | `/api/nsfw` | `get_nsfw()` | `app.py:1138` |
| PUT | `/api/nsfw` | `set_nsfw()` | `app.py:1142` |
| GET | `/api/openrouter/endpoints` | `get_openrouter_endpoints()` | `app.py:1071` |
| PUT | `/api/openrouter_routing` | `put_openrouter_routing()` | `app.py:1057` |
| POST | `/api/personas` | `persona_create()` | `app.py:1677` |
| POST | `/api/personas/generate` | `persona_generate()` | `app.py:1667` |
| POST | `/api/personas/import` | `persona_import()` | `app.py:1697` |
| DELETE | `/api/personas/{pid}` | `persona_del()` | `app.py:1729` |
| PUT | `/api/personas/{pid}` | `persona_edit()` | `app.py:1720` |
| GET | `/api/personas/{pid}/export` | `persona_export()` | `app.py:1711` |
| POST | `/api/personas/{pid}/fill_appearance` | `persona_fill_appearance()` | `app.py:1638` |
| PUT | `/api/prompt_presets` | `save_preset()` | `app.py:1117` |
| DELETE | `/api/prompt_presets/{name}` | `del_preset()` | `app.py:1124` |
| POST | `/api/providers` | `add_provider()` | `app.py:1473` |
| DELETE | `/api/providers/{pid}` | `del_provider()` | `app.py:1496` |
| PUT | `/api/providers/{pid}` | `put_provider()` | `app.py:1480` |
| GET | `/api/providers/{pid}/image_models` | `image_models()` | `app.py:1508` |
| GET | `/api/providers/{pid}/models` | `models()` | `app.py:1501` |
| PUT | `/api/reasoning_effort` | `put_reasoning_effort()` | `app.py:1083` |
| POST | `/api/steps/{sid}/activate` | `step_activate()` | `app.py:3960` |
| POST | `/api/steps/{sid}/edit` | `step_edit()` | `app.py:3950` |
| POST | `/api/steps/{sid}/reroll` | `step_reroll()` | `app.py:3903` |
| DELETE | `/api/turns/{tid}` | `turn_del()` | `app.py:3973` |
| GET | `/api/turns/{tid}/ambience` | `turn_ambience()` | `app.py:4227` |
| POST | `/api/turns/{tid}/ambience` | `turn_ambience_resolve()` | `app.py:4244` |
| GET | `/api/turns/{tid}/backdrop` | `turn_backdrop()` | `app.py:4054` |
| POST | `/api/turns/{tid}/backdrop` | `turn_backdrop_generate()` | `app.py:4102` |
| POST | `/api/turns/{tid}/branch` | `turn_branch()` | `app.py:3361` |
| PUT | `/api/turns/{tid}/input` | `edit_input()` | `app.py:3750` |
| GET | `/api/turns/{tid}/pipeline` | `pipeline_get()` | `app.py:3796` |
| PUT | `/api/turns/{tid}/prose` | `edit_prose()` | `app.py:3765` |
| POST | `/api/turns/{tid}/reroll` | `turn_reroll()` | `app.py:3834` |
| POST | `/api/turns/{tid}/rerun` | `turn_rerun()` | `app.py:3844` |
| POST | `/api/turns/{tid}/resume` | `turn_resume()` | `app.py:3871` |
| GET | `/api/updates/check` | `updates_check()` | `app.py:1162` |
| POST | `/api/updates/install` | `updates_install()` | `app.py:1166` |
| GET | `/guest` | `guest_page()` | `app.py:158` |
| GET | `/login` | `login_page()` | `app.py:170` |

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
| `lore_entries` | `id`, `lorebook_id`, `keys`, `content`, `category`, `canon_locked`, `turn_added`, `embedding`, `title`, `knowledge_tag`, `knowledge_range`, `knowledge_locations`, `entry_uid`, `importance`, `aliases`, `scope`, `relations`, `source_notes` |
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
| `memories` | `id`, `chat_id`, `char_id`, `turn_id`, `turn_idx`, `kind`, `category`, `provenance`, `salience`, `content`, `gist`, `key_phrases`, `entities`, `location`, `emotional_context`, `valence`, `arousal`, `confidence`, `access_count`, `last_accessed`, `embedding`, `cue_embedding`, `embedding_model`, `embedding_dim`, `archived`, `event_key`, `frame_id`, `--`, `--`, `--`, `--`, `importance`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `disputed` |
| `memory_vectors` | `vkey`, `embedding`, `cue_embedding`, `embedding_model`, `embedding_dim`, `created` |
| `memory_summaries` | `id`, `chat_id`, `char_id`, `scope`, `start_turn_idx`, `end_turn_idx`, `summary`, `key_phrases`, `unresolved_threads`, `embedding`, `embedding_model`, `embedding_dim`, `updated` |
| `events` | `id`, `chat_id`, `turn_id`, `content` |
| `world` | `chat_id`, `key`, `value` |
| `checkpoints` | `id`, `chat_id`, `turn_idx`, `blob`, `created` |
| `world_events` | `event_id`, `chat_id`, `turn_id`, `occurred_at`, `duration_seconds`, `kind`, `location_id`, `payload`, `seed`, `committed` |
| `world_entities` | `entity_id`, `chat_id`, `kind`, `subtype`, `name`, `payload`, `created_turn_id`, `retired_turn_id` |
| `world_placements` | `chat_id`, `subject_id`, `relation`, `container_id`, `detail` |
| `world_conditions` | `condition_id`, `chat_id`, `subject_id`, `kind`, `started_at`, `expires_at`, `next_tick`, `payload`, `active` |
| `scheduled_events` | `event_id`, `chat_id`, `due_at`, `kind`, `location_id`, `payload`, `seed`, `status` |
| `room_registry` | `chat_id`, `room_uid`, `owning_book_id`, `parent_entity`, `name`, `aliases`, `payload`, `created_turn_id`, `retired_turn_id` |
| `fiction_worlds` | `world_id`, `chat_id`, `parent_world_id`, `name`, `kind`, `payload`, `created_turn_id`, `retired_turn_id` |
| `fiction_locations` | `location_id`, `chat_id`, `world_id`, `parent_location_id`, `kind`, `name`, `payload` |
| `transit_edges` | `edge_id`, `chat_id`, `from_world_id`, `from_location_id`, `to_world_id`, `to_location_id`, `kind`, `payload` |

## Frontend JavaScript

### `static/js/ambience.js` (929 lines)

Sections: Room ambience (`:2`); seamless looping (`:213`); one-shots (`:636`); the ambience panel (`:685`); the mix (`:703`).

Declared functions: `ambienceStored()`, `ambienceElement()`, `entryAudios()`, `ambiencePlayers()`, `applyAmbienceMute()`, `setAmbienceVolume()`, `ambienceLevel()`, `setLayerGain()`, `toggleAmbienceMute()`, `ambienceFadeMix()`, `armSeamlessLoop()`, `crossLoop()`, `retireEntries()`, `stopAmbience()`, `playAmbience()`, `armAmbienceUnlock()`, `ambienceWorking()`, `awaitAmbience()`, `resolveAmbience()`, `ambienceForTurn()`, `rerollAmbience()`, `ambienceOnVisibleTurn()`, `ambienceResetForRender()`, `updateAmbienceBtn()`, `playAmbienceOneshot()`, `ambienceCandidateRow()`, `ambienceLayerRow()`, `ambienceMixPanel()`, `openAmbiencePanel()`, `toggleAmbience()`, `syncAmbience()`.

### `static/js/app.js` (934 lines)

Sections: Boot & sidebar (`:1`); New chat wizard (`:218`); NSFW (`:661`); Composer (`:689`); Init (`:767`); Embedding reconciler progress (`:810`).

Declared functions: `boot()`, `renderSide()`, `renderChatSidebar()`, `newChatWizard()`, `renderWizardChoice()`, `wizardState()`, `wizardFromScratch()`, `renderWizardPersona()`, `renderWizardCharacters()`, `renderWizardScenario()`, `runWizard()`, `renderCharacterSidebar()`, `renderPersonaSidebar()`, `renderLegacyLoreSidebar()`, `updateNSFWBtn()`, `toggleNSFW()`, `resizeComposer()`, `erCard()`, `erDismiss()`, `erPoll()`, `erWatch()`, `erOfferRebuild()`.

### `static/js/backdrops.js` (378 lines)

Sections: Scene backdrops (`:2`).

Declared functions: `backdropLayers()`, `backdropLuminance()`, `applyBackdropContrast()`, `releaseBackdropLayer()`, `clearBackdrop()`, `showBackdrop()`, `backdropWorking()`, `awaitBackdrop()`, `generateBackdrop()`, `backdropForTurn()`, `backdropOnVisibleTurn()`, `backdropResetForRender()`, `updateBackdropBtn()`, `toggleBackdrops()`, `syncBackdrops()`.

### `static/js/chat.js` (1843 lines)

Sections: The turn being read (`:1`); Pipeline drawer (`:694`); Relationship viewer (`:995`); Memory browser (`:1067`); Private history (`:1785`).

Declared functions: `observeVisibleTurn()`, `openChat()`, `renderFrameBar()`, `switchFrame()`, `updateChatScopedButtons()`, `renderChat()`, `branchTurn()`, `editTurnInput()`, `editTurnProse()`, `liveReset()`, `friendlyPhase()`, `turnStatusStart()`, `turnStatusSet()`, `turnStatusStop()`, `_streamOn()`, `liveFlush()`, `liveAppend()`, `liveStep()`, `handleEvt()`, `abortActiveRun()`, `runStream()`, `confirmCheckpointRestore()`, `runReroll()`, `rerollTurn()`, `exportChat()`, `importChatModal()`, `openPipeline()`, `relMeter()`, `relationshipModal()`, `memModal()`, `exportCharacterMemories()`, `importCharacterMemoriesModal()`, `memQS()`, `memCharId()`, `loadMemoryBrowse()`, `getMemUI()`, `renderMemorySummary()`, `sortedMems()`, `renderMemoryList()`, `memoryCard()`, `fieldWrap()`, `reloadMemView()`, `runMemorySearch()`, `showNewMemoryForm()`, `consolidateMemories()`, `previewMemoryContext()`, `chatPH()`, `personaPH()`.

### `static/js/components.js` (871 lines)

Sections: Modal (`:18`); Book covers (`:34`); confirm()/prompt() replacements (`:147`); Toasts (`:269`); Background tasks (`:297`); Form helpers (`:383`); Model picker (`:732`).

Declared functions: `el()`, `coverOfRow()`, `coverOfTitle()`, `modal()`, `modalOwnership()`, `closeModal()`, `closeAllModals()`, `_confirmOverlay()`, `confirmModal()`, `promptModal()`, `promptModalWithToggle()`, `toastHost()`, `toast()`, `renderActivity()`, `elapsedLabel()`, `activityTicking()`, `backgroundTask()`, `buttonTask()`, `loadingBlock()`, `emptyState()`, `fText()`, `fArea()`, `fSelect()`, `fNum()`, `fLineList()`, `fStrList()`, `fCoveragePicker()`, `fAttireGarments()`, `fList()`, `fAbilities()`, `fTraits()`, `fValues()`, `fBeliefs()`, `fCopingStrategies()`, `fAssociations()`, `fGoals()`, `fSenses()`, `fLatent()`, `fPronouns()`, `phEditor()`, `fetchModels()`, `fetchImageModels()`, `modelCombobox()`, `emitChange()`, `load()`, `showDD()`.

### `static/js/editors.js` (900 lines)

Sections: Background-character promotion (`:659`); Import (file upload) (`:708`); Generate (`:779`); Lorebook generate (`:797`); Lorebooks (`:814`); Export (`:888`).

Declared functions: `appearanceFillButton()`, `defaultCharacterSheet()`, `greetingCarousel()`, `quickStartModal()`, `charEditor()`, `personaEditor()`, `promotionReviewModal()`, `promoteBackgroundPresence()`, `importModal()`, `generateModal()`, `generateLoreModal()`, `loreModal()`, `exportCharacter()`, `exportPersona()`, `exportLorebook()`.

### `static/js/lorebooks.js` (3609 lines)

Sections: Library sidebar (`:241`); Data loading (`:448`); Workspace (`:545`); Book metadata and tree operations (`:1152`); Entry editor (`:1611`); Lorebook relationships (`:2356`); Advanced generator (`:2807`); Interrupted-generation recovery (`:3027`).

Declared functions: `loreBookTypeIcon()`, `loreLinkTypes()`, `normalizeLoreBook()`, `loreOwnershipKey()`, `loreBooksByParent()`, `loreBookMatches()`, `loreVisibleIds()`, `loreBookLabel()`, `parseStoredJSON()`, `loreField()`, `loreSelect()`, `loreBookOptions()`, `renderLoreLibrarySidebar()`, `renderNode()`, `loadLoreWorkspaceData()`, `collectLoreLinkTargets()`, `loreWorkspaceVisible()`, `renderLoreWorkspaceBody()`, `openLoreWorkspace()`, `renderLoreInspector()`, `selectTab()`, `buildLoreWorkspace()`, `renderWorkspaceTree()`, `renderNode()`, `renderTreeList()`, `renderLoreBookEditor()`, `moveLoreBook()`, `reorderLoreBook()`, `promoteLoreBook()`, `demoteLoreBook()`, `createSiblingLoreBook()`, `createLoreBookDialog()`, `refreshLoreUI()`, `renderLoreEntries()`, `renderList()`, `buildLoreEntryCard()`, `splitNumberList()`, `reinterpretLoreBook()`, `generateLoreEntriesPrompt()`, `buildDirectLoreRequest()`, `renderRelationshipOverview()`, `renderLoreRelationshipEditor()`, `renderRelationshipList()`, `showNewRelationshipForm()`, `renderLoreGenerator()`, `adoptGeneratorPlan()`, `generatorPlanMessage()`, `loreGenAgo()`, `refreshLoreGenRecovery()`, `normalizeGeneratorPlan()`, `renderLorePlanPreview()`, `renderOperations()`, `planStat()`, `renderAnalysisSection()`, `addPlanGroup()`, `stripPlanUIFields()`, `acceptedGeneratorPlan()`.

### `static/js/settings.js` (2669 lines)

Sections: Chat tool modals (`:1`); Condition tab (`:435`); Survival tracker (`:495`); Character relocation (`:734`); API connections (`:1425`); Software updates (host-only; git fast-forward from GitHub origin) (`:2371`); Legacy checkpoint conversion (host-only maintenance) (`:2403`); Prompts (`:2637`).

Declared functions: `selectTab()`, `renderCastTab()`, `renderConditionTab()`, `hydrateConditionTab()`, `vitalMeter()`, `syncVitalsGutterNow()`, `syncVitalsGutter()`, `hideVitalsHud()`, `vitalsBlock()`, `refreshVitalsHud()`, `clearVitalsHud()`, `hydrateCastLocations()`, `castRoomLabel()`, `castRoomSelect()`, `renderLorebooksTab()`, `renderBookNode()`, `renderMultiplayerTab()`, `renderFramesTab()`, `renderFramesListPanel()`, `renderPersonaStationingPanel()`, `renderParadoxPanel()`, `renderBackgroundPresencesPanel()`, `renderGuestInvitePanel()`, `renderInsightsTab()`, `renderDramaticIronyPanel()`, `renderPromiseLedgerPanel()`, `embeddingBankBlock()`, `modelRecommendationsBlock()`, `renderFirstRunProviderSetup()`, `preferredBackdropSize()`, `renderFullApiSettings()`, `propagateToFollowers()`, `renderUpdateChecking()`, `renderUpdateError()`, `checkpointCompactionBlock()`, `renderUpdateStatus()`, `runUpdateInstall()`, `renderUpdateDone()`.

### `static/js/theme-init.js` (181 lines)

Declared functions: `readStored()`, `writeStored()`, `normaliseTheme()`, `normaliseProseSize()`, `applyTheme()`, `applyProseSize()`, `normaliseEffects()`, `applyEffects()`, `syncPageHidden()`.

### `static/js/themes.js` (159 lines)

Declared functions: `themePreview()`, `openAppearanceSettings()`.

### `static/js/utils.js` (109 lines)

Sections: API (`:34`); Download (`:102`).

Declared functions: `hasDefaultModel()`, `safeId()`, `splitCL()`, `numOr()`, `api()`, `streamPost()`, `downloadJSON()`.

### `static/js/weather-fx.js` (548 lines)

Sections: Weather effects (`:2`); the tile (`:178`); the layers (`:251`); lifecycle (`:329`); lightning (`:387`); the exact cost this file exists to avoid. Rain has no wrapper and no (`:527`).

Declared functions: `weatherFxReduced()`, `weatherFxEffectsOff()`, `weatherFxSupported()`, `weatherFxHost()`, `weatherFxRandom()`, `weatherFxTile()`, `weatherFxReach()`, `weatherFxBuild()`, `weatherFxClearLayers()`, `weatherFxStop()`, `weatherFxVisible()`, `weatherFxApply()`, `weatherFxStormy()`, `weatherFxScheduleFlash()`, `weatherFxFlash()`, `weatherFxOpenSky()`, `weatherFxBolt()`, `weatherFxThunder()`, `weatherFxForTurn()`.
