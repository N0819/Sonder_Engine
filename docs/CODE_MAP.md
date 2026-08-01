# Generated Code Map

> Regenerate with `python tools/generate_code_map.py`. Do not hand-edit this file.

## Python modules

| Module | Lines | Purpose | Local dependencies |
|---|---:|---|---|
| `affect.py` | 1852 |  | `theory_of_mind` |
| `agents/__init__.py` | 86 | Backward-compatible facade for the role-specific agent package. | `agents.character`, `agents.common`, `agents.director`, `agents.loops`, `agents.mapping`, `agents.narration`, `agents.perception`, `agents.runtime`, `agents.storage`, `scene` |
| `agents/background.py` | 809 |  | `agents.common`, `background_claims`, `character_schema`, `commit`, `db`, `prompts`, `scene`, `schemas`, `spatial` |
| `agents/character.py` | 2219 | Private character decision agent. | `affect`, `agents.common`, `character_schema`, `db`, `frames`, `memory`, `place_purpose`, `prompts`, `psychology_runtime`, `scene`, `schemas`, `spatial`, `survival`, `theory_of_mind` |
| `agents/common.py` | 4091 | Shared normalization, lore, delivery, and perception helpers. | `attire`, `character_schema`, `db`, `llm_quality`, `memory`, `providers`, `scene`, `schemas`, `spatial`, `theory_of_mind` |
| `agents/director.py` | 3638 | Scene establishment, player interpretation, and objective resolution. | `agents.common`, `attire`, `character_schema`, `db`, `memory`, `paradox`, `prompts`, `providers`, `scene`, `schemas`, `spatial` |
| `agents/loops.py` | 552 | Reaction loops, interaction rounds, and deterministic micro-perception. | `agents.character`, `agents.common`, `character_schema`, `db`, `scene`, `spatial` |
| `agents/mapping.py` | 202 | Lore routing, cached recall, and retrieval staging. | `agents.common`, `character_schema`, `db`, `memory`, `prompts`, `scene` |
| `agents/narration.py` | 883 | Player-facing narration agent. | `agents.common`, `character_schema`, `db`, `prompts`, `scene`, `schemas`, `spatial` |
| `agents/perception.py` | 2458 | Opening, action-onset, and outcome observer views. | `affect`, `agents.common`, `character_schema`, `db`, `prompts`, `scene`, `spatial` |
| `agents/runtime.py` | 976 | Pipeline plans, dispatch, streaming, cancellation, resume, and reruns. | `agents.background`, `agents.character`, `agents.common`, `agents.director`, `agents.loops`, `agents.mapping`, `agents.narration`, `agents.perception`, `agents.storage`, `character_schema`, `checkpoints`, `commit`, `db`, `pipeline_context`, `providers`, `scene` |
| `agents/storage.py` | 92 | Step and active-variant persistence helpers. | `db` |
| `ambience.py` | 2043 |  | `backdrops`, `db`, `weather` |
| `app.py` | 4299 | FastAPI application assembly, resource CRUD, turn control, and streaming endpoints. | `agents`, `ambience`, `attire`, `auth_routes`, `backdrops`, `character_schema`, `chat_archive`, `checkpoints`, `commit`, `db`, `frames`, `greetings`, `guest_access`, `importers`, `memory`, `paradox`, `pipeline_context`, `prompts`, `providers`, `scene`, `survival`, `updates` |
| `attire.py` | 1123 |  | — |
| `auth_routes.py` | 143 | Typed host-authentication HTTP routes and cookie transport. | `guest_access` |
| `authored_events.py` | 124 |  | `db` |
| `backdrops.py` | 1143 |  | `db`, `spatial`, `weather` |
| `background_claims.py` | 287 |  | `db` |
| `character_schema.py` | 1297 | Versioned character/persona defaults, normalization, accessors, and export payloads. | `attire`, `schemas` |
| `chat_archive.py` | 1051 | Typed, atomic chat archive export/import service and HTTP routes. | `character_schema`, `checkpoints`, `db`, `memory`, `schemas` |
| `checkpoints.py` | 696 | Whole-chat snapshots and checkpoint restore orchestration. | `db`, `memory` |
| `comfort.py` | 295 |  | `spatial` |
| `commit.py` | 5338 | Validated persistence of scene, entities, cast, lore, relationships, events, and memories. | `affect`, `attire`, `character_schema`, `comfort`, `db`, `frames`, `mechanics`, `memory`, `paradox`, `prompts`, `providers`, `psychology_runtime`, `scene`, `spatial`, `spatial_frames`, `survival`, `theory_of_mind`, `weather` |
| `db.py` | 1343 | SQLite schema, migrations, connection management, transactions, and key/value world access. | — |
| `frames.py` | 193 |  | `db` |
| `greetings.py` | 330 |  | `agents.runtime`, `agents.storage`, `character_schema`, `db`, `llm_quality`, `memory`, `prompts` |
| `guest_access.py` | 328 |  | `db` |
| `importers.py` | 2462 | Native and AI-assisted character, persona, and lorebook import/generation. | `character_schema`, `db`, `memory`, `prompts`, `providers` |
| `llm_quality.py` | 292 | Strict JSON parsing, schema validation, and model-assisted repair. | `providers`, `schemas` |
| `logging_utils.py` | 118 | Structured timing and observability helpers. | — |
| `mechanics.py` | 274 |  | `spatial`, `spatial_frames` |
| `memory.py` | 3133 | Lorebook graph, memory retrieval/consolidation, relationships, and vector search. | `db`, `frames`, `logging_utils`, `prompts`, `providers`, `theory_of_mind` |
| `paradox.py` | 489 |  | `character_schema`, `db`, `frames` |
| `pipeline_context.py` | 184 | Typed mutable context passed through a turn pipeline. | `db` |
| `pipeline_trace.py` | 413 | Privacy-conscious export, validation, and offline replay of persisted pipeline history. | `db` |
| `place_purpose.py` | 532 |  | `comfort`, `spatial`, `survival`, `theory_of_mind` |
| `prompt_cache.py` | 79 | Provider-specific prompt-cache helpers. | `providers` |
| `prompts.py` | 3438 | Default system prompts and prompt preset access. | `db` |
| `providers.py` | 1977 | Provider selection, retries, streaming, cancellation, model listing, and embeddings. | `db` |
| `psychology_runtime.py` | 493 |  | — |
| `scene.py` | 1233 | Scene/cast/persona helpers, recent events, dialogue configuration, and private knowledge. | `attire`, `character_schema`, `db`, `spatial` |
| `schemas.py` | 3436 | Pydantic output contracts and semantic validation for agent payloads. | — |
| `spatial.py` | 4620 | Deterministic room, barrier, hearing, visibility, placement, and scene-diff logic. | `schemas`, `spatial_orientation` |
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
| `character_step()` | 1598 | 622 lines |
| `_annotate_known_exits()` | 1019 | 445 lines |
| `_destination_from_goals()` | 597 | 109 lines |
| `sprint_offers()` | 1499 | 97 lines |
| `_verdict()` | 441 | 72 lines |
| `_annotate_goal_currency()` | 882 | 67 lines |
| `_en_route()` | 951 | 66 lines |
| `_unbidden_trigger()` | 256 | 54 lines |

### `agents/common.py`

| Function | Start | Size |
|---|---:|---:|
| `norm_sequence()` | 1068 | 161 lines |
| `_scrub_invented_dialogue()` | 3150 | 145 lines |
| `_extract_authority_claims()` | 808 | 106 lines |
| `_check_quote_attribution()` | 3688 | 91 lines |
| `_check_narrator_fidelity()` | 3944 | 84 lines |
| `_perceptible_entities()` | 431 | 78 lines |
| `authored_other_subject()` | 593 | 77 lines |
| `_check_pronoun_fidelity()` | 3480 | 76 lines |

### `agents/director.py`

| Function | Start | Size |
|---|---:|---:|
| `director_resolve()` | 2691 | 948 lines |
| `director_interpret()` | 320 | 334 lines |
| `_reconcile_resolution()` | 2223 | 302 lines |
| `_reconcile_interpretation()` | 802 | 119 lines |
| `director_establish()` | 164 | 105 lines |
| `_awareness_exits()` | 1424 | 98 lines |
| `_evidence_present()` | 1987 | 97 lines |
| `_guard_approach_is_not_arrival()` | 2609 | 80 lines |

### `agents/loops.py`

| Function | Start | Size |
|---|---:|---:|
| `interaction_loop()` | 182 | 300 lines |
| `deterministic_micro_perception()` | 41 | 96 lines |
| `reaction_loop()` | 483 | 70 lines |
| `_defer_to_focus()` | 152 | 28 lines |
| `_drop_non_awake()` | 138 | 12 lines |

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
| `perception_outcome()` | 1754 | 705 lines |
| `perception_act()` | 1157 | 428 lines |
| `perception_establish()` | 989 | 167 lines |
| `_observer_scene_payload()` | 319 | 106 lines |
| `_redact_concealed_from_event()` | 1687 | 66 lines |
| `_touch_only_sources()` | 1586 | 62 lines |
| `_source_channels()` | 510 | 56 lines |
| `_strip_self_narration()` | 675 | 51 lines |

### `agents/runtime.py`

| Function | Start | Size |
|---|---:|---:|
| `_run_pipeline()` | 582 | 341 lines |
| `build_plan()` | 381 | 81 lines |
| `resume_key_for_turn()` | 326 | 54 lines |
| `run_pipeline()` | 924 | 53 lines |
| `_load_extra_players()` | 39 | 52 lines |
| `_stream_one()` | 217 | 48 lines |
| `_stream_parallel()` | 266 | 45 lines |
| `_rehydrate_loop_results()` | 534 | 41 lines |

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
| `turn_branch()` | 3286 | 387 lines |
| `_remap_cp_blob()` | 598 | 187 lines |
| `chat_get()` | 2084 | 118 lines |
| `lore_entry_edit()` | 1873 | 70 lines |
| `lore_edit()` | 1725 | 68 lines |
| `_ambience_payload()` | 4086 | 63 lines |
| `chat_positions_get()` | 2683 | 62 lines |
| `_stream()` | 244 | 60 lines |

### `attire.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_regions()` | 256 | 101 lines |
| `dedupe_regions()` | 563 | 82 lines |
| `coerce_diff_shape()` | 668 | 77 lines |
| `resolve_garment()` | 493 | 68 lines |
| `decisive_targets()` | 764 | 67 lines |
| `apply_flat_change()` | 956 | 66 lines |
| `advance()` | 833 | 56 lines |
| `describe()` | 908 | 46 lines |

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
| `normalize_character_data()` | 803 | 155 lines |
| `default_character_data()` | 390 | 88 lines |
| `_normalize_psychology()` | 237 | 80 lines |
| `repair_character_shape()` | 744 | 57 lines |
| `character_initial_active_state()` | 1098 | 48 lines |
| `normalize_persona_data()` | 959 | 47 lines |
| `_coerce_appearance()` | 665 | 45 lines |
| `_as_profile_list()` | 37 | 36 lines |

### `chat_archive.py`

| Function | Start | Size |
|---|---:|---:|
| `_model_validate()` | 52 | 4 lines |
| `_model_dump()` | 58 | 4 lines |

### `checkpoints.py`

| Function | Start | Size |
|---|---:|---:|
| `snapshot_state()` | 12 | 142 lines |
| `_restore_checkpoint_body()` | 483 | 136 lines |
| `_restore_books()` | 155 | 104 lines |
| `insert_world_tables()` | 334 | 81 lines |
| `refresh_checkpoint()` | 653 | 44 lines |
| `_restore_frames()` | 282 | 38 lines |
| `ensure_checkpoint()` | 625 | 27 lines |
| `_preserved_settings()` | 456 | 25 lines |

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
| `prepare_memory_commit()` | 4042 | 957 lines |
| `prepare_scene_commit()` | 1619 | 445 lines |
| `track_background_presences()` | 2595 | 218 lines |
| `commit_world_entities()` | 2201 | 168 lines |
| `_prepare_destruction()` | 695 | 158 lines |
| `update_place_graph()` | 70 | 153 lines |
| `prepare_mapping_commit()` | 3424 | 133 lines |
| `commit_mapping()` | 3559 | 120 lines |

### `db.py`

| Function | Start | Size |
|---|---:|---:|
| `init()` | 1251 | 49 lines |
| `transaction()` | 1154 | 36 lines |
| `conn()` | 1129 | 23 lines |
| `_backfill_resource_uids()` | 1233 | 17 lines |
| `qi()` | 1196 | 16 lines |
| `parse_scoped_world_key()` | 52 | 13 lines |
| `_execute_retry()` | 1098 | 13 lines |
| `wget_for_frame()` | 1325 | 12 lines |

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
| `start_story()` | 145 | 107 lines |
| `generate_greeting()` | 254 | 58 lines |
| `extract_greeting()` | 95 | 24 lines |
| `_substitute_player_slot()` | 52 | 22 lines |
| `player_handle_for()` | 76 | 17 lines |
| `_strip_greeting_wrapping()` | 314 | 17 lines |
| `_override_narrator()` | 130 | 13 lines |
| `_greeting_record()` | 121 | 7 lines |

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
| `search_memories()` | 1267 | 226 lines |
| `contrast_memory()` | 1528 | 119 lines |
| `rebuild_embeddings()` | 2654 | 116 lines |
| `rebuild_checkpoint_embeddings()` | 2784 | 110 lines |
| `consolidate_character_memory()` | 1807 | 93 lines |
| `restore_lorebook()` | 2214 | 79 lines |
| `monitoring_subtree()` | 567 | 78 lines |
| `resolve_lorebook_graph()` | 379 | 76 lines |

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
| `get_prompt()` | 3429 | 10 lines |
| `presets()` | 3420 | 2 lines |
| `active_preset()` | 3423 | 2 lines |
| `nsfw_enabled()` | 3426 | 2 lines |

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
| `recent_events_for_observer()` | 697 | 59 lines |
| `director_context()` | 757 | 53 lines |
| `awareness_conditions()` | 418 | 47 lines |
| `private_knowledge_for()` | 1190 | 44 lines |
| `_seed_scene_initial_attire()` | 83 | 31 lines |
| `active_cast()` | 115 | 31 lines |
| `active_disguises()` | 310 | 31 lines |
| `normalize_style_guide()` | 1098 | 31 lines |

### `schemas.py`

| Function | Start | Size |
|---|---:|---:|
| `preprocess_llm_output()` | 2611 | 243 lines |
| `_lenient_coerce()` | 495 | 159 lines |
| `semantic_output_errors()` | 3230 | 113 lines |
| `validate_llm_output_strict()` | 3380 | 57 lines |
| `_coerce_conditions()` | 2383 | 50 lines |
| `_declared()` | 335 | 48 lines |
| `_coerce_station_table()` | 49 | 41 lines |
| `_coerce_evidence_refs()` | 1701 | 41 lines |

### `spatial.py`

| Function | Start | Size |
|---|---:|---:|
| `merge_scene_with_diff()` | 4335 | 241 lines |
| `sprint_reach()` | 3223 | 175 lines |
| `apply_transit_dock_edges()` | 3936 | 165 lines |
| `apply_contact_ops()` | 2704 | 149 lines |
| `contacts_from_entity_state()` | 2288 | 137 lines |
| `visible_adjacent_rooms()` | 3468 | 117 lines |
| `derive_scene_stations()` | 1303 | 104 lines |
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
| GET | `/` | `index()` | `app.py:163` |
| PUT | `/api/active_preset` | `set_active()` | `app.py:1110` |
| PUT | `/api/agent_models` | `put_agent_models()` | `app.py:922` |
| PUT | `/api/ambience` | `put_ambience()` | `app.py:1004` |
| GET | `/api/ambience/library` | `ambience_library()` | `app.py:4239` |
| GET | `/api/ambience/search` | `ambience_search()` | `app.py:4218` |
| PUT | `/api/attire_beneath` | `set_attire_beneath()` | `app.py:1124` |
| POST | `/api/auth/login` | `auth_login()` | `auth_routes.py:108` |
| POST | `/api/auth/logout` | `auth_logout()` | `auth_routes.py:139` |
| POST | `/api/auth/setup` | `auth_setup()` | `auth_routes.py:69` |
| GET | `/api/auth/status` | `auth_status()` | `auth_routes.py:59` |
| GET | `/api/auto_promote` | `get_auto_promote()` | `app.py:2296` |
| PUT | `/api/auto_promote` | `set_auto_promote()` | `app.py:2300` |
| PUT | `/api/backdrops` | `put_backdrops()` | `app.py:994` |
| GET | `/api/bootstrap` | `bootstrap()` | `app.py:867` |
| POST | `/api/characters` | `char_create()` | `app.py:1476` |
| POST | `/api/characters/generate` | `char_generate()` | `app.py:1466` |
| POST | `/api/characters/import` | `char_import()` | `app.py:1497` |
| DELETE | `/api/characters/{cid}` | `char_del()` | `app.py:1608` |
| PUT | `/api/characters/{cid}` | `char_edit()` | `app.py:1599` |
| GET | `/api/characters/{cid}/export` | `char_export()` | `app.py:1591` |
| POST | `/api/characters/{cid}/fill_appearance` | `char_fill_appearance()` | `app.py:1581` |
| POST | `/api/characters/{cid}/fill_psychology` | `char_fill_psychology()` | `app.py:1555` |
| POST | `/api/characters/{cid}/generate_greeting` | `char_generate_greeting()` | `app.py:1540` |
| POST | `/api/characters/{cid}/recover_greetings` | `char_recover_greetings()` | `app.py:1530` |
| POST | `/api/characters/{cid}/start` | `character_start_story()` | `app.py:1512` |
| POST | `/api/chats` | `chat_new()` | `app.py:1952` |
| POST | `/api/chats/import` | `import_chat()` | `chat_archive.py:163` |
| DELETE | `/api/chats/{cid}` | `chat_del()` | `app.py:2054` |
| GET | `/api/chats/{cid}` | `chat_get()` | `app.py:2084` |
| PUT | `/api/chats/{cid}` | `chat_edit()` | `app.py:1958` |
| POST | `/api/chats/{cid}/abort` | `chat_abort()` | `app.py:3282` |
| GET | `/api/chats/{cid}/ambience/oneshot/{name}` | `ambience_oneshot()` | `app.py:4248` |
| DELETE | `/api/chats/{cid}/ambience/pin` | `ambience_pin_delete()` | `app.py:4296` |
| PUT | `/api/chats/{cid}/ambience/pin` | `ambience_pin_put()` | `app.py:4277` |
| GET | `/api/chats/{cid}/ambience/pins` | `ambience_pins_get()` | `app.py:4272` |
| GET | `/api/chats/{cid}/ambience/{signature}.audio` | `ambience_audio()` | `app.py:4202` |
| GET | `/api/chats/{cid}/attire` | `attire_get()` | `app.py:2884` |
| PUT | `/api/chats/{cid}/attire` | `attire_put()` | `app.py:2891` |
| GET | `/api/chats/{cid}/backdrop/{signature}.png` | `backdrop_image()` | `app.py:4054` |
| GET | `/api/chats/{cid}/background_config` | `bg_cfg_get()` | `app.py:2966` |
| PUT | `/api/chats/{cid}/background_config` | `bg_cfg_put()` | `app.py:2970` |
| POST | `/api/chats/{cid}/characters` | `chat_add_char()` | `app.py:2204` |
| DELETE | `/api/chats/{cid}/characters/{ch}` | `chat_del_char()` | `app.py:2531` |
| PUT | `/api/chats/{cid}/characters/{ch}/card` | `chat_char_card_put()` | `app.py:2541` |
| GET | `/api/chats/{cid}/characters/{ch}/memories` | `mem_list()` | `app.py:3096` |
| POST | `/api/chats/{cid}/characters/{ch}/memories` | `mem_add()` | `app.py:3198` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/consolidate` | `mem_consolidate()` | `app.py:3187` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/export` | `mem_export()` | `app.py:3142` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/import` | `mem_import()` | `app.py:3153` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/search` | `mem_search()` | `app.py:3117` |
| GET | `/api/chats/{cid}/characters/{ch}/memory-context` | `memory_context_preview()` | `app.py:3163` |
| PUT | `/api/chats/{cid}/characters/{ch}/position` | `chat_char_position_put()` | `app.py:2747` |
| GET | `/api/chats/{cid}/characters/{ch}/private_history` | `ph_get()` | `app.py:2807` |
| PUT | `/api/chats/{cid}/characters/{ch}/private_history` | `ph_put()` | `app.py:2817` |
| GET | `/api/chats/{cid}/characters/{ch}/relationships` | `relationships_get()` | `app.py:3176` |
| GET | `/api/chats/{cid}/dialogue_config` | `dlg_get()` | `app.py:2926` |
| PUT | `/api/chats/{cid}/dialogue_config` | `dlg_put()` | `app.py:2930` |
| GET | `/api/chats/{cid}/dramatic_irony` | `get_dramatic_irony_feed()` | `app.py:2258` |
| GET | `/api/chats/{cid}/export` | `export_chat()` | `chat_archive.py:157` |
| GET | `/api/chats/{cid}/fixed_points` | `fixed_points_list()` | `app.py:3042` |
| POST | `/api/chats/{cid}/fixed_points` | `fixed_points_create()` | `app.py:3052` |
| DELETE | `/api/chats/{cid}/fixed_points/{anchor_id}` | `fixed_points_delete()` | `app.py:3074` |
| GET | `/api/chats/{cid}/frames` | `frames_list()` | `app.py:2996` |
| POST | `/api/chats/{cid}/frames` | `frames_create()` | `app.py:3000` |
| GET | `/api/chats/{cid}/guest_invites` | `list_guest_invites()` | `app.py:2444` |
| POST | `/api/chats/{cid}/guest_invites` | `create_guest_invite()` | `app.py:2426` |
| DELETE | `/api/chats/{cid}/guest_invites/{gid}` | `revoke_guest_invite()` | `app.py:2448` |
| DELETE | `/api/chats/{cid}/lorebook` | `detach_lore()` | `app.py:2045` |
| POST | `/api/chats/{cid}/lorebook` | `bind_lore()` | `app.py:2029` |
| GET | `/api/chats/{cid}/lorebooks` | `chat_lorebooks_owned()` | `app.py:1180` |
| POST | `/api/chats/{cid}/lorebooks` | `attach_lore()` | `app.py:1989` |
| DELETE | `/api/chats/{cid}/lorebooks/{lid}` | `detach_book()` | `app.py:2014` |
| GET | `/api/chats/{cid}/paradox_policy` | `paradox_policy_get()` | `app.py:3027` |
| PUT | `/api/chats/{cid}/paradox_policy` | `paradox_policy_put()` | `app.py:3031` |
| GET | `/api/chats/{cid}/persona_private_history` | `pph_get()` | `app.py:2826` |
| PUT | `/api/chats/{cid}/persona_private_history` | `pph_put()` | `app.py:2839` |
| GET | `/api/chats/{cid}/personas` | `chat_list_extra_personas()` | `app.py:2305` |
| POST | `/api/chats/{cid}/personas` | `chat_add_persona()` | `app.py:2350` |
| DELETE | `/api/chats/{cid}/personas/{pid}` | `chat_del_persona()` | `app.py:2374` |
| PUT | `/api/chats/{cid}/personas/{pid}/station` | `chat_persona_station()` | `app.py:2315` |
| GET | `/api/chats/{cid}/positions` | `chat_positions_get()` | `app.py:2683` |
| GET | `/api/chats/{cid}/promises` | `get_promise_ledger()` | `app.py:2262` |
| GET | `/api/chats/{cid}/promotable` | `list_promotable_presences()` | `app.py:2254` |
| POST | `/api/chats/{cid}/promotions/confirm` | `confirm_promotion()` | `app.py:2279` |
| POST | `/api/chats/{cid}/promotions/draft` | `draft_promotion()` | `app.py:2266` |
| GET | `/api/chats/{cid}/style_guide` | `style_guide_get()` | `app.py:2909` |
| PUT | `/api/chats/{cid}/style_guide` | `style_guide_put()` | `app.py:2915` |
| GET | `/api/chats/{cid}/survival` | `survival_get()` | `app.py:2598` |
| PUT | `/api/chats/{cid}/survival` | `survival_put()` | `app.py:2603` |
| POST | `/api/chats/{cid}/turns` | `turn_new()` | `app.py:3245` |
| POST | `/api/chats/{cid}/turns/{idx}/player_input` | `submit_extra_player_input()` | `app.py:2388` |
| GET | `/api/chats/{cid}/vitals` | `chat_vitals_get()` | `app.py:2650` |
| GET | `/api/chats/{cid}/world` | `world_get()` | `app.py:2844` |
| PUT | `/api/chats/{cid}/world` | `world_put()` | `app.py:2848` |
| POST | `/api/guest/input` | `guest_input()` | `app.py:2506` |
| GET | `/api/guest/state` | `guest_state()` | `app.py:2472` |
| PUT | `/api/image_model` | `put_image_model()` | `app.py:972` |
| POST | `/api/join` | `join_with_code()` | `app.py:2454` |
| DELETE | `/api/lore_entries/{eid}` | `lore_entry_delete()` | `app.py:1945` |
| PUT | `/api/lore_entries/{eid}` | `lore_entry_edit()` | `app.py:1873` |
| DELETE | `/api/lore_gen_jobs/{job_id}` | `lorebook_generate_discard()` | `app.py:1335` |
| POST | `/api/lore_gen_jobs/{job_id}/resume` | `lorebook_generate_resume()` | `app.py:1317` |
| DELETE | `/api/lorebook_links/{link_id}` | `lorebook_link_delete()` | `app.py:1276` |
| PUT | `/api/lorebook_links/{link_id}` | `lorebook_link_update()` | `app.py:1262` |
| POST | `/api/lorebooks` | `lore_create()` | `app.py:1703` |
| POST | `/api/lorebooks/import` | `lore_import()` | `app.py:1371` |
| DELETE | `/api/lorebooks/{lid}` | `lore_delete()` | `app.py:1795` |
| GET | `/api/lorebooks/{lid}` | `lore_get()` | `app.py:1683` |
| PUT | `/api/lorebooks/{lid}` | `lore_edit()` | `app.py:1725` |
| POST | `/api/lorebooks/{lid}/apply_plan` | `lorebook_apply_plan()` | `app.py:1344` |
| POST | `/api/lorebooks/{lid}/entries` | `lore_entry_create()` | `app.py:1844` |
| GET | `/api/lorebooks/{lid}/export` | `lore_export()` | `app.py:1801` |
| POST | `/api/lorebooks/{lid}/generate` | `lore_generate()` | `app.py:1830` |
| GET | `/api/lorebooks/{lid}/generate_job` | `lorebook_generate_job()` | `app.py:1306` |
| POST | `/api/lorebooks/{lid}/generate_plan` | `lorebook_generate_plan()` | `app.py:1281` |
| GET | `/api/lorebooks/{lid}/links` | `lorebook_links_get()` | `app.py:1235` |
| POST | `/api/lorebooks/{lid}/links` | `lorebook_link_create()` | `app.py:1240` |
| POST | `/api/lorebooks/{lid}/move` | `lorebook_move()` | `app.py:1162` |
| POST | `/api/lorebooks/{lid}/reinterpret` | `lore_reinterpret_route()` | `app.py:1818` |
| POST | `/api/lorebooks/{lid}/reorder` | `lorebook_reorder()` | `app.py:1171` |
| PUT | `/api/max_output_tokens` | `put_max_output_tokens()` | `app.py:1085` |
| DELETE | `/api/memories/{mid}` | `mem_del()` | `app.py:3239` |
| PUT | `/api/memories/{mid}` | `mem_edit()` | `app.py:3220` |
| GET | `/api/memory/embeddings` | `memory_embeddings_status()` | `app.py:945` |
| POST | `/api/memory/embeddings/rebuild` | `memory_embeddings_rebuild()` | `app.py:960` |
| GET | `/api/nsfw` | `get_nsfw()` | `app.py:1115` |
| PUT | `/api/nsfw` | `set_nsfw()` | `app.py:1119` |
| GET | `/api/openrouter/endpoints` | `get_openrouter_endpoints()` | `app.py:1048` |
| PUT | `/api/openrouter_routing` | `put_openrouter_routing()` | `app.py:1034` |
| POST | `/api/personas` | `persona_create()` | `app.py:1625` |
| POST | `/api/personas/generate` | `persona_generate()` | `app.py:1615` |
| POST | `/api/personas/import` | `persona_import()` | `app.py:1645` |
| DELETE | `/api/personas/{pid}` | `persona_del()` | `app.py:1677` |
| PUT | `/api/personas/{pid}` | `persona_edit()` | `app.py:1668` |
| GET | `/api/personas/{pid}/export` | `persona_export()` | `app.py:1659` |
| POST | `/api/personas/{pid}/fill_appearance` | `persona_fill_appearance()` | `app.py:1586` |
| PUT | `/api/prompt_presets` | `save_preset()` | `app.py:1094` |
| DELETE | `/api/prompt_presets/{name}` | `del_preset()` | `app.py:1101` |
| POST | `/api/providers` | `add_provider()` | `app.py:1421` |
| DELETE | `/api/providers/{pid}` | `del_provider()` | `app.py:1444` |
| PUT | `/api/providers/{pid}` | `put_provider()` | `app.py:1428` |
| GET | `/api/providers/{pid}/image_models` | `image_models()` | `app.py:1456` |
| GET | `/api/providers/{pid}/models` | `models()` | `app.py:1449` |
| PUT | `/api/reasoning_effort` | `put_reasoning_effort()` | `app.py:1060` |
| POST | `/api/steps/{sid}/activate` | `step_activate()` | `app.py:3885` |
| POST | `/api/steps/{sid}/edit` | `step_edit()` | `app.py:3875` |
| POST | `/api/steps/{sid}/reroll` | `step_reroll()` | `app.py:3828` |
| DELETE | `/api/turns/{tid}` | `turn_del()` | `app.py:3898` |
| GET | `/api/turns/{tid}/ambience` | `turn_ambience()` | `app.py:4152` |
| POST | `/api/turns/{tid}/ambience` | `turn_ambience_resolve()` | `app.py:4169` |
| GET | `/api/turns/{tid}/backdrop` | `turn_backdrop()` | `app.py:3979` |
| POST | `/api/turns/{tid}/backdrop` | `turn_backdrop_generate()` | `app.py:4027` |
| POST | `/api/turns/{tid}/branch` | `turn_branch()` | `app.py:3286` |
| PUT | `/api/turns/{tid}/input` | `edit_input()` | `app.py:3675` |
| GET | `/api/turns/{tid}/pipeline` | `pipeline_get()` | `app.py:3721` |
| PUT | `/api/turns/{tid}/prose` | `edit_prose()` | `app.py:3690` |
| POST | `/api/turns/{tid}/reroll` | `turn_reroll()` | `app.py:3759` |
| POST | `/api/turns/{tid}/rerun` | `turn_rerun()` | `app.py:3769` |
| POST | `/api/turns/{tid}/resume` | `turn_resume()` | `app.py:3796` |
| GET | `/api/updates/check` | `updates_check()` | `app.py:1139` |
| POST | `/api/updates/install` | `updates_install()` | `app.py:1143` |
| GET | `/guest` | `guest_page()` | `app.py:155` |
| GET | `/login` | `login_page()` | `app.py:167` |

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
| `memories` | `id`, `chat_id`, `char_id`, `turn_id`, `turn_idx`, `kind`, `category`, `provenance`, `salience`, `content`, `gist`, `key_phrases`, `entities`, `location`, `emotional_context`, `valence`, `arousal`, `confidence`, `access_count`, `last_accessed`, `embedding`, `cue_embedding`, `embedding_model`, `embedding_dim`, `archived`, `event_key`, `frame_id` |
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

### `static/js/app.js` (918 lines)

Sections: Boot & sidebar (`:1`); New chat wizard (`:218`); NSFW (`:661`); Composer (`:689`); Init (`:755`); Embedding reconciler progress (`:798`).

Declared functions: `boot()`, `renderSide()`, `renderChatSidebar()`, `newChatWizard()`, `renderWizardChoice()`, `wizardState()`, `wizardFromScratch()`, `renderWizardPersona()`, `renderWizardCharacters()`, `renderWizardScenario()`, `runWizard()`, `renderCharacterSidebar()`, `renderPersonaSidebar()`, `renderLegacyLoreSidebar()`, `updateNSFWBtn()`, `toggleNSFW()`, `resizeComposer()`, `erCard()`, `erDismiss()`, `erPoll()`, `erWatch()`, `erOfferRebuild()`.

### `static/js/backdrops.js` (348 lines)

Sections: Scene backdrops (`:2`).

Declared functions: `backdropLayers()`, `backdropLuminance()`, `applyBackdropContrast()`, `clearBackdrop()`, `showBackdrop()`, `backdropWorking()`, `awaitBackdrop()`, `generateBackdrop()`, `backdropForTurn()`, `backdropOnVisibleTurn()`, `backdropResetForRender()`, `updateBackdropBtn()`, `toggleBackdrops()`, `syncBackdrops()`.

### `static/js/chat.js` (1853 lines)

Sections: Scene mood (`:1`); Pipeline drawer (`:704`); Relationship viewer (`:1005`); Memory browser (`:1077`); Private history (`:1795`).

Declared functions: `detectSceneMood()`, `applySceneMood()`, `setSceneMood()`, `observeSceneMood()`, `openChat()`, `renderFrameBar()`, `switchFrame()`, `updateChatScopedButtons()`, `renderChat()`, `branchTurn()`, `editTurnInput()`, `editTurnProse()`, `liveReset()`, `friendlyPhase()`, `turnStatusStart()`, `turnStatusSet()`, `turnStatusStop()`, `pinLiveLog()`, `liveStep()`, `handleEvt()`, `abortActiveRun()`, `runStream()`, `confirmCheckpointRestore()`, `runReroll()`, `rerollTurn()`, `exportChat()`, `importChatModal()`, `openPipeline()`, `relMeter()`, `relationshipModal()`, `memModal()`, `exportCharacterMemories()`, `importCharacterMemoriesModal()`, `memQS()`, `memCharId()`, `loadMemoryBrowse()`, `getMemUI()`, `renderMemorySummary()`, `sortedMems()`, `renderMemoryList()`, `memoryCard()`, `fieldWrap()`, `reloadMemView()`, `runMemorySearch()`, `showNewMemoryForm()`, `consolidateMemories()`, `previewMemoryContext()`, `chatPH()`, `personaPH()`.

### `static/js/components.js` (855 lines)

Sections: Modal (`:18`); Book covers (`:34`); confirm()/prompt() replacements (`:147`); Toasts (`:269`); Background tasks (`:281`); Form helpers (`:367`); Model picker (`:716`).

Declared functions: `el()`, `coverOfRow()`, `coverOfTitle()`, `modal()`, `modalOwnership()`, `closeModal()`, `closeAllModals()`, `_confirmOverlay()`, `confirmModal()`, `promptModal()`, `promptModalWithToggle()`, `toast()`, `renderActivity()`, `elapsedLabel()`, `activityTicking()`, `backgroundTask()`, `buttonTask()`, `loadingBlock()`, `emptyState()`, `fText()`, `fArea()`, `fSelect()`, `fNum()`, `fLineList()`, `fStrList()`, `fCoveragePicker()`, `fAttireGarments()`, `fList()`, `fAbilities()`, `fTraits()`, `fValues()`, `fBeliefs()`, `fCopingStrategies()`, `fAssociations()`, `fGoals()`, `fSenses()`, `fLatent()`, `fPronouns()`, `phEditor()`, `fetchModels()`, `fetchImageModels()`, `modelCombobox()`, `emitChange()`, `load()`, `showDD()`.

### `static/js/editors.js` (900 lines)

Sections: Background-character promotion (`:659`); Import (file upload) (`:708`); Generate (`:779`); Lorebook generate (`:797`); Lorebooks (`:814`); Export (`:888`).

Declared functions: `appearanceFillButton()`, `defaultCharacterSheet()`, `greetingCarousel()`, `quickStartModal()`, `charEditor()`, `personaEditor()`, `promotionReviewModal()`, `promoteBackgroundPresence()`, `importModal()`, `generateModal()`, `generateLoreModal()`, `loreModal()`, `exportCharacter()`, `exportPersona()`, `exportLorebook()`.

### `static/js/lorebooks.js` (3594 lines)

Sections: Library sidebar (`:241`); Data loading (`:448`); Workspace (`:545`); Book metadata and tree operations (`:1145`); Entry editor (`:1604`); Lorebook relationships (`:2341`); Advanced generator (`:2792`); Interrupted-generation recovery (`:3012`).

Declared functions: `loreBookTypeIcon()`, `loreLinkTypes()`, `normalizeLoreBook()`, `loreOwnershipKey()`, `loreBooksByParent()`, `loreBookMatches()`, `loreVisibleIds()`, `loreBookLabel()`, `parseStoredJSON()`, `loreField()`, `loreSelect()`, `loreBookOptions()`, `renderLoreLibrarySidebar()`, `renderNode()`, `loadLoreWorkspaceData()`, `collectLoreLinkTargets()`, `loreWorkspaceVisible()`, `renderLoreWorkspaceBody()`, `openLoreWorkspace()`, `renderLoreInspector()`, `selectTab()`, `buildLoreWorkspace()`, `renderWorkspaceTree()`, `renderNode()`, `renderTreeList()`, `renderLoreBookEditor()`, `moveLoreBook()`, `reorderLoreBook()`, `promoteLoreBook()`, `demoteLoreBook()`, `createSiblingLoreBook()`, `createLoreBookDialog()`, `refreshLoreUI()`, `renderLoreEntries()`, `renderList()`, `buildLoreEntryCard()`, `splitNumberList()`, `reinterpretLoreBook()`, `generateLoreEntriesPrompt()`, `buildDirectLoreRequest()`, `renderRelationshipOverview()`, `renderLoreRelationshipEditor()`, `renderRelationshipList()`, `showNewRelationshipForm()`, `renderLoreGenerator()`, `adoptGeneratorPlan()`, `generatorPlanMessage()`, `loreGenAgo()`, `refreshLoreGenRecovery()`, `normalizeGeneratorPlan()`, `renderLorePlanPreview()`, `renderOperations()`, `planStat()`, `renderAnalysisSection()`, `addPlanGroup()`, `stripPlanUIFields()`, `acceptedGeneratorPlan()`.

### `static/js/settings.js` (2495 lines)

Sections: Chat tool modals (`:1`); Condition tab (`:435`); Survival tracker (`:495`); Character relocation (`:709`); API connections (`:1400`); Software updates (host-only; git fast-forward from GitHub origin) (`:2341`); Prompts (`:2463`).

Declared functions: `selectTab()`, `renderCastTab()`, `renderConditionTab()`, `hydrateConditionTab()`, `vitalMeter()`, `syncVitalsGutter()`, `hideVitalsHud()`, `vitalsBlock()`, `refreshVitalsHud()`, `clearVitalsHud()`, `hydrateCastLocations()`, `castRoomLabel()`, `castRoomSelect()`, `renderLorebooksTab()`, `renderBookNode()`, `renderMultiplayerTab()`, `renderFramesTab()`, `renderFramesListPanel()`, `renderPersonaStationingPanel()`, `renderParadoxPanel()`, `renderBackgroundPresencesPanel()`, `renderGuestInvitePanel()`, `renderInsightsTab()`, `renderDramaticIronyPanel()`, `renderPromiseLedgerPanel()`, `embeddingBankBlock()`, `modelRecommendationsBlock()`, `renderFirstRunProviderSetup()`, `preferredBackdropSize()`, `renderFullApiSettings()`, `propagateToFollowers()`, `renderUpdateChecking()`, `renderUpdateError()`, `renderUpdateStatus()`, `runUpdateInstall()`, `renderUpdateDone()`.

### `static/js/theme-init.js` (117 lines)

Declared functions: `readStored()`, `writeStored()`, `normaliseTheme()`, `normaliseProseSize()`, `applyTheme()`, `applyProseSize()`.

### `static/js/themes.js` (117 lines)

Declared functions: `themePreview()`, `openAppearanceSettings()`.

### `static/js/utils.js` (109 lines)

Sections: API (`:34`); Download (`:102`).

Declared functions: `hasDefaultModel()`, `safeId()`, `splitCL()`, `numOr()`, `api()`, `streamPost()`, `downloadJSON()`.

### `static/js/weather-fx.js` (502 lines)

Sections: Weather effects (`:2`); the tile (`:161`); the layers (`:234`); lifecycle (`:302`); lightning (`:359`).

Declared functions: `weatherFxReduced()`, `weatherFxSupported()`, `weatherFxHost()`, `weatherFxRandom()`, `weatherFxTile()`, `weatherFxReach()`, `weatherFxBuild()`, `weatherFxClearLayers()`, `weatherFxStop()`, `weatherFxVisible()`, `weatherFxApply()`, `weatherFxStormy()`, `weatherFxScheduleFlash()`, `weatherFxFlash()`, `weatherFxOpenSky()`, `weatherFxBolt()`, `weatherFxThunder()`, `weatherFxForTurn()`.
