# Generated Code Map

> Regenerate with `python tools/generate_code_map.py`. Do not hand-edit this file.

## Python modules

| Module | Lines | Purpose | Local dependencies |
|---|---:|---|---|
| `affect.py` | 1100 |  | `theory_of_mind` |
| `agents/__init__.py` | 83 | Backward-compatible facade for the role-specific agent package. | `agents.character`, `agents.common`, `agents.director`, `agents.loops`, `agents.mapping`, `agents.narration`, `agents.perception`, `agents.runtime`, `agents.storage`, `scene` |
| `agents/background.py` | 250 |  | `agents.common`, `commit`, `db`, `prompts`, `schemas`, `spatial` |
| `agents/character.py` | 359 | Private character decision agent. | `affect`, `agents.common`, `character_schema`, `db`, `frames`, `memory`, `prompts`, `scene`, `schemas`, `spatial`, `theory_of_mind` |
| `agents/common.py` | 1841 | Shared normalization, lore, delivery, and perception helpers. | `character_schema`, `db`, `llm_quality`, `memory`, `providers`, `scene`, `schemas`, `spatial`, `theory_of_mind` |
| `agents/director.py` | 2427 | Scene establishment, player interpretation, and objective resolution. | `agents.common`, `character_schema`, `db`, `memory`, `paradox`, `prompts`, `providers`, `scene`, `schemas`, `spatial` |
| `agents/loops.py` | 472 | Reaction loops, interaction rounds, and deterministic micro-perception. | `agents.character`, `agents.common`, `character_schema`, `db`, `scene`, `spatial` |
| `agents/mapping.py` | 190 | Lore routing, cached recall, and retrieval staging. | `agents.common`, `character_schema`, `db`, `memory`, `prompts`, `scene` |
| `agents/narration.py` | 466 | Player-facing narration agent. | `agents.common`, `db`, `prompts`, `scene`, `schemas`, `spatial` |
| `agents/perception.py` | 1217 | Opening, action-onset, and outcome observer views. | `affect`, `agents.common`, `character_schema`, `db`, `prompts`, `scene`, `spatial` |
| `agents/runtime.py` | 900 | Pipeline plans, dispatch, streaming, cancellation, resume, and reruns. | `agents.background`, `agents.character`, `agents.common`, `agents.director`, `agents.loops`, `agents.mapping`, `agents.narration`, `agents.perception`, `agents.storage`, `character_schema`, `checkpoints`, `commit`, `db`, `pipeline_context`, `providers`, `scene` |
| `agents/storage.py` | 72 | Step and active-variant persistence helpers. | `db` |
| `app.py` | 3528 | FastAPI application, resource CRUD, import/export, turn control, and streaming endpoints. | `agents`, `character_schema`, `checkpoints`, `commit`, `db`, `frames`, `greetings`, `guest_access`, `importers`, `memory`, `paradox`, `pipeline_context`, `prompts`, `providers`, `scene`, `updates` |
| `authored_events.py` | 124 |  | `db` |
| `character_schema.py` | 639 | Versioned character/persona defaults, normalization, accessors, and export payloads. | — |
| `checkpoints.py` | 516 | Whole-chat snapshots and checkpoint restore orchestration. | `db`, `memory` |
| `commit.py` | 3374 | Validated persistence of scene, entities, cast, lore, relationships, events, and memories. | `affect`, `character_schema`, `db`, `frames`, `mechanics`, `memory`, `paradox`, `prompts`, `providers`, `scene`, `spatial`, `spatial_frames`, `theory_of_mind` |
| `db.py` | 1245 | SQLite schema, migrations, connection management, transactions, and key/value world access. | — |
| `frames.py` | 193 |  | `db` |
| `greetings.py` | 173 |  | `agents.runtime`, `agents.storage`, `character_schema`, `db`, `llm_quality`, `memory`, `prompts` |
| `guest_access.py` | 303 |  | `db` |
| `importers.py` | 1318 | Native and AI-assisted character, persona, and lorebook import/generation. | `character_schema`, `db`, `memory`, `prompts`, `providers` |
| `llm_quality.py` | 263 | Strict JSON parsing, schema validation, and model-assisted repair. | `providers`, `schemas` |
| `logging_utils.py` | 110 | Structured timing and observability helpers. | — |
| `mechanics.py` | 270 |  | `spatial`, `spatial_frames` |
| `memory.py` | 2095 | Lorebook graph, memory retrieval/consolidation, relationships, and vector search. | `db`, `frames`, `prompts`, `providers` |
| `paradox.py` | 486 |  | `db`, `frames` |
| `pipeline_context.py` | 168 | Typed mutable context passed through a turn pipeline. | `db` |
| `prompt_cache.py` | 79 | Provider-specific prompt-cache helpers. | `providers` |
| `prompts.py` | 1834 | Default system prompts and prompt preset access. | `db` |
| `providers.py` | 1041 | Provider selection, retries, streaming, cancellation, model listing, and embeddings. | `db` |
| `scene.py` | 693 | Scene/cast/persona helpers, recent events, dialogue configuration, and private knowledge. | `character_schema`, `db`, `spatial` |
| `schemas.py` | 1820 | Pydantic output contracts and semantic validation for agent payloads. | — |
| `spatial.py` | 1475 | Deterministic room, barrier, hearing, visibility, placement, and scene-diff logic. | — |
| `spatial_frames.py` | 871 |  | `character_schema`, `db`, `frames`, `paradox`, `scene`, `spatial` |
| `theory_of_mind.py` | 288 |  | — |
| `updates.py` | 254 |  | — |

## Largest top-level functions

### `affect.py`

| Function | Start | Size |
|---|---:|---:|
| `resolve_affect()` | 472 | 134 lines |
| `apply_intent_ops()` | 705 | 120 lines |
| `validate_drive_shift()` | 950 | 79 lines |
| `update_drive_strain()` | 828 | 78 lines |
| `normalize_wants()` | 612 | 72 lines |
| `leak_scan()` | 1043 | 44 lines |
| `detect_drive_rupture()` | 907 | 38 lines |
| `appraise()` | 355 | 36 lines |

### `agents/background.py`

| Function | Start | Size |
|---|---:|---:|
| `_react_one()` | 196 | 55 lines |
| `_beat_for_presence()` | 88 | 35 lines |
| `background_react()` | 141 | 32 lines |
| `_filtered_player_declaration()` | 59 | 27 lines |
| `_present_others()` | 175 | 19 lines |
| `_result()` | 125 | 14 lines |

### `agents/character.py`

| Function | Start | Size |
|---|---:|---:|
| `character_step()` | 111 | 249 lines |
| `_recent_self_lines()` | 73 | 36 lines |
| `_merge_standing_intentions()` | 56 | 15 lines |

### `agents/common.py`

| Function | Start | Size |
|---|---:|---:|
| `norm_sequence()` | 679 | 161 lines |
| `_extract_authority_claims()` | 435 | 90 lines |
| `_check_narrator_fidelity()` | 1713 | 65 lines |
| `_scrub_unknown_identities()` | 1004 | 57 lines |
| `_strip_player_echo()` | 1505 | 56 lines |
| `_assert_plan_materialized()` | 138 | 55 lines |
| `_dedupe_view_sentences()` | 1598 | 43 lines |
| `_unknown_actor_label()` | 907 | 41 lines |

### `agents/director.py`

| Function | Start | Size |
|---|---:|---:|
| `director_resolve()` | 1919 | 509 lines |
| `director_interpret()` | 200 | 301 lines |
| `_reconcile_resolution()` | 1624 | 224 lines |
| `_reconcile_interpretation()` | 649 | 119 lines |
| `_evidence_present()` | 1396 | 89 lines |
| `_narrated_destruction_subjects()` | 1022 | 79 lines |
| `director_establish()` | 132 | 67 lines |
| `_route_authorial_npc_cognition()` | 70 | 60 lines |

### `agents/loops.py`

| Function | Start | Size |
|---|---:|---:|
| `interaction_loop()` | 138 | 264 lines |
| `deterministic_micro_perception()` | 40 | 83 lines |
| `reaction_loop()` | 403 | 70 lines |
| `_drop_non_awake()` | 124 | 12 lines |

### `agents/mapping.py`

| Function | Start | Size |
|---|---:|---:|
| `mapping_stage()` | 31 | 88 lines |
| `mapping_quick()` | 120 | 71 lines |

### `agents/narration.py`

| Function | Start | Size |
|---|---:|---:|
| `narrator()` | 180 | 154 lines |
| `narrator_extra()` | 335 | 132 lines |
| `_resolve_narration_person()` | 50 | 47 lines |
| `_generate_narration()` | 155 | 24 lines |
| `_craft_tells()` | 138 | 16 lines |
| `_spatial_facts_field()` | 25 | 12 lines |

### `agents/perception.py`

| Function | Start | Size |
|---|---:|---:|
| `perception_outcome()` | 757 | 461 lines |
| `perception_act()` | 495 | 261 lines |
| `perception_establish()` | 346 | 148 lines |
| `_delivered_manifest()` | 196 | 47 lines |
| `_subject_disguise_context()` | 245 | 38 lines |
| `_observer_facing_sequence()` | 312 | 32 lines |
| `_disguise_leak_check()` | 285 | 25 lines |
| `_ambient_location_for()` | 87 | 20 lines |

### `agents/runtime.py`

| Function | Start | Size |
|---|---:|---:|
| `_run_pipeline()` | 531 | 318 lines |
| `build_plan()` | 372 | 71 lines |
| `resume_key_for_turn()` | 317 | 54 lines |
| `run_pipeline()` | 850 | 51 lines |
| `_stream_one()` | 208 | 48 lines |
| `_stream_parallel()` | 257 | 45 lines |
| `_load_extra_players()` | 39 | 44 lines |
| `_rehydrate_loop_results()` | 489 | 41 lines |

### `agents/storage.py`

| Function | Start | Size |
|---|---:|---:|
| `save_step()` | 10 | 19 lines |
| `mark_steps_stale()` | 53 | 12 lines |
| `_set_steps_stale()` | 45 | 7 lines |
| `clear_steps_stale()` | 66 | 7 lines |
| `active_content()` | 30 | 5 lines |
| `variant_count()` | 36 | 4 lines |
| `step_is_stale()` | 41 | 3 lines |

### `app.py`

| Function | Start | Size |
|---|---:|---:|
| `chat_import()` | 2362 | 378 lines |
| `turn_branch()` | 2924 | 350 lines |
| `_remap_cp_blob()` | 588 | 154 lines |
| `chat_export()` | 2194 | 98 lines |
| `chat_get()` | 1578 | 94 lines |
| `lore_entry_edit()` | 1398 | 70 lines |
| `lore_edit()` | 1255 | 68 lines |
| `_stream()` | 272 | 60 lines |

### `authored_events.py`

| Function | Start | Size |
|---|---:|---:|
| `resolve_authored_events()` | 90 | 35 lines |
| `mint_authored_events()` | 42 | 28 lines |
| `due_authored_events()` | 72 | 16 lines |
| `_event_id()` | 36 | 4 lines |

### `character_schema.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_character_data()` | 314 | 89 lines |
| `default_character_data()` | 35 | 63 lines |
| `normalize_persona_data()` | 404 | 39 lines |
| `character_initial_active_state()` | 506 | 33 lines |
| `_coerce_appearance()` | 284 | 29 lines |
| `default_persona_data()` | 107 | 24 lines |
| `character_standing_intentions()` | 540 | 24 lines |
| `_normalize_latent()` | 248 | 21 lines |

### `checkpoints.py`

| Function | Start | Size |
|---|---:|---:|
| `snapshot_state()` | 12 | 126 lines |
| `_restore_books()` | 139 | 90 lines |
| `insert_world_tables()` | 304 | 81 lines |
| `_restore_checkpoint_body()` | 386 | 74 lines |
| `_restore_frames()` | 252 | 38 lines |
| `refresh_checkpoint()` | 486 | 31 lines |
| `restore_checkpoint()` | 230 | 21 lines |
| `ensure_checkpoint()` | 466 | 19 lines |

### `commit.py`

| Function | Start | Size |
|---|---:|---:|
| `prepare_memory_commit()` | 2666 | 385 lines |
| `prepare_scene_commit()` | 974 | 220 lines |
| `track_background_presences()` | 1607 | 169 lines |
| `_prepare_destruction()` | 417 | 158 lines |
| `prepare_mapping_commit()` | 2240 | 132 lines |
| `commit_world_entities()` | 1325 | 123 lines |
| `commit_mapping()` | 2374 | 120 lines |
| `_commit_all_locked()` | 3218 | 98 lines |

### `db.py`

| Function | Start | Size |
|---|---:|---:|
| `init()` | 1153 | 49 lines |
| `transaction()` | 1056 | 36 lines |
| `conn()` | 1031 | 23 lines |
| `_backfill_resource_uids()` | 1135 | 17 lines |
| `qi()` | 1098 | 16 lines |
| `parse_scoped_world_key()` | 52 | 13 lines |
| `_execute_retry()` | 1000 | 13 lines |
| `wget_for_frame()` | 1227 | 12 lines |

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
| `start_story()` | 80 | 94 lines |
| `extract_greeting()` | 30 | 24 lines |
| `_override_narrator()` | 65 | 13 lines |
| `_greeting_record()` | 56 | 7 lines |

### `guest_access.py`

| Function | Start | Size |
|---|---:|---:|
| `redeem_code()` | 198 | 48 lines |
| `verify_host_login()` | 81 | 26 lines |
| `list_grants()` | 278 | 26 lines |
| `create_host_account()` | 62 | 17 lines |
| `verify_guest_token()` | 248 | 16 lines |
| `revoke_grant()` | 266 | 10 lines |
| `create_host_session()` | 109 | 9 lines |
| `verify_host_session()` | 120 | 9 lines |

### `importers.py`

| Function | Start | Size |
|---|---:|---:|
| `generate_lorebook_plan()` | 1007 | 135 lines |
| `import_lorebook()` | 856 | 115 lines |
| `apply_lorebook_plan()` | 1143 | 111 lines |
| `import_character()` | 427 | 72 lines |
| `generate_lore_entries()` | 1254 | 65 lines |
| `_reinterpret_entries()` | 794 | 61 lines |
| `_jparse()` | 35 | 59 lines |
| `import_persona()` | 526 | 56 lines |

### `llm_quality.py`

| Function | Start | Size |
|---|---:|---:|
| `complete_validated_json()` | 89 | 175 lines |
| `_extract_balanced_object()` | 25 | 34 lines |
| `strict_json_parse()` | 61 | 27 lines |

### `logging_utils.py`

| Function | Start | Size |
|---|---:|---:|
| `log_llm_call()` | 91 | 20 lines |
| `measure_step()` | 72 | 18 lines |

### `mechanics.py`

| Function | Start | Size |
|---|---:|---:|
| `_fire_due_events()` | 110 | 61 lines |
| `_schedule_new_arrivals()` | 173 | 42 lines |
| `mechanics_sweep()` | 229 | 42 lines |
| `news_latency_seconds()` | 90 | 10 lines |
| `_expire_conditions()` | 217 | 10 lines |
| `stable_event_key()` | 68 | 6 lines |
| `_payload_of()` | 102 | 6 lines |

### `memory.py`

| Function | Start | Size |
|---|---:|---:|
| `search_memories()` | 1089 | 103 lines |
| `consolidate_character_memory()` | 1289 | 80 lines |
| `restore_lorebook()` | 1683 | 79 lines |
| `monitoring_subtree()` | 530 | 78 lines |
| `resolve_lorebook_graph()` | 342 | 76 lines |
| `lorebook_manifest()` | 464 | 65 lines |
| `duplicate_lorebook_tree_for_chat()` | 1825 | 58 lines |
| `prepare_chat_memory_restore()` | 1435 | 48 lines |

### `paradox.py`

| Function | Start | Size |
|---|---:|---:|
| `check_and_apply_paradox()` | 437 | 50 lines |
| `_apply_toll()` | 276 | 47 lines |
| `_trigger_paradox()` | 360 | 30 lines |
| `_advance_paradox()` | 392 | 30 lines |
| `_apply_hazard_stage()` | 246 | 28 lines |
| `add_fixed_point()` | 121 | 19 lines |
| `get_all_paradoxes()` | 164 | 17 lines |
| `_apply_warden_stage()` | 325 | 17 lines |

### `prompt_cache.py`

| Function | Start | Size |
|---|---:|---:|
| `add_cache_breakpoint()` | 15 | 37 lines |
| `estimate_cacheable_tokens()` | 66 | 14 lines |
| `supports_prompt_caching()` | 7 | 7 lines |

### `prompts.py`

| Function | Start | Size |
|---|---:|---:|
| `get_prompt()` | 1825 | 10 lines |
| `presets()` | 1816 | 2 lines |
| `active_preset()` | 1819 | 2 lines |
| `nsfw_enabled()` | 1822 | 2 lines |

### `providers.py`

| Function | Start | Size |
|---|---:|---:|
| `_chat_complete_once()` | 584 | 156 lines |
| `async chat_complete_async()` | 741 | 87 lines |
| `chat_complete()` | 479 | 82 lines |
| `async _chat_complete_async_once()` | 829 | 58 lines |
| `resolve_role_candidates()` | 282 | 52 lines |
| `list_models()` | 943 | 47 lines |
| `_sse_openai()` | 401 | 46 lines |
| `_sse_anthropic()` | 448 | 30 lines |

### `scene.py`

| Function | Start | Size |
|---|---:|---:|
| `private_knowledge_for()` | 650 | 44 lines |
| `recent_events()` | 385 | 36 lines |
| `active_disguises()` | 190 | 31 lines |
| `director_context()` | 422 | 29 lines |
| `is_player_speaker()` | 499 | 29 lines |
| `disguised_visible_appearance()` | 223 | 28 lines |
| `_ability_mod()` | 461 | 28 lines |
| `active_cast()` | 51 | 27 lines |

### `schemas.py`

| Function | Start | Size |
|---|---:|---:|
| `preprocess_llm_output()` | 1237 | 193 lines |
| `semantic_output_errors()` | 1691 | 76 lines |
| `validate_llm_output_strict()` | 1768 | 53 lines |
| `_coerce_str_list()` | 12 | 33 lines |
| `_coerce_considered_responses()` | 1088 | 32 lines |
| `validate_llm_output()` | 1431 | 29 lines |
| `_coerce_conditions()` | 1151 | 27 lines |
| `_hoist_misplaced_entity_siblings()` | 1193 | 21 lines |

### `spatial.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_transit_dock_edges()` | 1107 | 137 lines |
| `visible_adjacent_rooms()` | 864 | 113 lines |
| `merge_scene_with_diff()` | 1319 | 112 lines |
| `egocentric_frame()` | 513 | 80 lines |
| `passable_route_exists()` | 336 | 53 lines |
| `hear_level()` | 390 | 53 lines |
| `nearby_rooms()` | 447 | 51 lines |
| `spatial_rel()` | 285 | 48 lines |

### `spatial_frames.py`

| Function | Start | Size |
|---|---:|---:|
| `perform_split()` | 601 | 94 lines |
| `infer_companion_carry()` | 231 | 88 lines |
| `infer_vehicle_zones()` | 144 | 85 lines |
| `infer_focus()` | 363 | 72 lines |
| `perform_merge()` | 773 | 69 lines |
| `infer_facing()` | 437 | 59 lines |
| `detect_split()` | 555 | 44 lines |
| `infer_came_from()` | 321 | 40 lines |

### `theory_of_mind.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_mind_model_updates()` | 166 | 91 lines |
| `mind_models_for_payload()` | 258 | 31 lines |
| `claim_similarity()` | 130 | 22 lines |
| `cap_mind_model_updates()` | 99 | 16 lines |
| `decayed_confidence()` | 116 | 8 lines |
| `_elapsed()` | 153 | 7 lines |
| `_clamp01()` | 88 | 6 lines |
| `_tokens()` | 125 | 4 lines |

### `updates.py`

| Function | Start | Size |
|---|---:|---:|
| `check_updates()` | 169 | 48 lines |
| `_github_releases()` | 131 | 36 lines |
| `install_updates()` | 219 | 36 lines |
| `_upstream_ref()` | 73 | 24 lines |
| `_git()` | 37 | 22 lines |
| `_repo_slug()` | 104 | 13 lines |
| `_incoming_tags()` | 119 | 10 lines |
| `_is_git_repo()` | 61 | 5 lines |

## FastAPI routes

| Method | Path | Handler | Source |
|---|---|---|---|
| GET | `/` | `index()` | `app.py:140` |
| PUT | `/api/active_preset` | `set_active()` | `app.py:840` |
| PUT | `/api/agent_models` | `put_agent_models()` | `app.py:819` |
| POST | `/api/auth/login` | `auth_login()` | `app.py:179` |
| POST | `/api/auth/logout` | `auth_logout()` | `app.py:194` |
| POST | `/api/auth/setup` | `auth_setup()` | `app.py:166` |
| GET | `/api/auth/status` | `auth_status()` | `app.py:157` |
| GET | `/api/auto_promote` | `get_auto_promote()` | `app.py:1757` |
| PUT | `/api/auto_promote` | `set_auto_promote()` | `app.py:1761` |
| GET | `/api/bootstrap` | `bootstrap()` | `app.py:794` |
| POST | `/api/characters` | `char_create()` | `app.py:1058` |
| POST | `/api/characters/generate` | `char_generate()` | `app.py:1048` |
| POST | `/api/characters/import` | `char_import()` | `app.py:1079` |
| DELETE | `/api/characters/{cid}` | `char_del()` | `app.py:1138` |
| PUT | `/api/characters/{cid}` | `char_edit()` | `app.py:1129` |
| GET | `/api/characters/{cid}/export` | `char_export()` | `app.py:1121` |
| POST | `/api/characters/{cid}/recover_greetings` | `char_recover_greetings()` | `app.py:1111` |
| POST | `/api/characters/{cid}/start` | `character_start_story()` | `app.py:1093` |
| POST | `/api/chats` | `chat_new()` | `app.py:1477` |
| POST | `/api/chats/import` | `chat_import()` | `app.py:2362` |
| DELETE | `/api/chats/{cid}` | `chat_del()` | `app.py:1560` |
| GET | `/api/chats/{cid}` | `chat_get()` | `app.py:1578` |
| PUT | `/api/chats/{cid}` | `chat_edit()` | `app.py:1483` |
| POST | `/api/chats/{cid}/abort` | `chat_abort()` | `app.py:2920` |
| GET | `/api/chats/{cid}/attire` | `attire_get()` | `app.py:2059` |
| PUT | `/api/chats/{cid}/attire` | `attire_put()` | `app.py:2066` |
| POST | `/api/chats/{cid}/characters` | `chat_add_char()` | `app.py:1674` |
| DELETE | `/api/chats/{cid}/characters/{ch}` | `chat_del_char()` | `app.py:1973` |
| GET | `/api/chats/{cid}/characters/{ch}/memories` | `mem_list()` | `app.py:2743` |
| POST | `/api/chats/{cid}/characters/{ch}/memories` | `mem_add()` | `app.py:2838` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/consolidate` | `mem_consolidate()` | `app.py:2827` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/export` | `mem_export()` | `app.py:2782` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/import` | `mem_import()` | `app.py:2793` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/search` | `mem_search()` | `app.py:2764` |
| GET | `/api/chats/{cid}/characters/{ch}/memory-context` | `memory_context_preview()` | `app.py:2803` |
| GET | `/api/chats/{cid}/characters/{ch}/private_history` | `ph_get()` | `app.py:1982` |
| PUT | `/api/chats/{cid}/characters/{ch}/private_history` | `ph_put()` | `app.py:1992` |
| GET | `/api/chats/{cid}/characters/{ch}/relationships` | `relationships_get()` | `app.py:2816` |
| GET | `/api/chats/{cid}/dialogue_config` | `dlg_get()` | `app.py:2075` |
| PUT | `/api/chats/{cid}/dialogue_config` | `dlg_put()` | `app.py:2079` |
| GET | `/api/chats/{cid}/dramatic_irony` | `get_dramatic_irony_feed()` | `app.py:1719` |
| GET | `/api/chats/{cid}/export` | `chat_export()` | `app.py:2194` |
| GET | `/api/chats/{cid}/fixed_points` | `fixed_points_list()` | `app.py:2157` |
| POST | `/api/chats/{cid}/fixed_points` | `fixed_points_create()` | `app.py:2167` |
| DELETE | `/api/chats/{cid}/fixed_points/{anchor_id}` | `fixed_points_delete()` | `app.py:2189` |
| GET | `/api/chats/{cid}/frames` | `frames_list()` | `app.py:2111` |
| POST | `/api/chats/{cid}/frames` | `frames_create()` | `app.py:2115` |
| GET | `/api/chats/{cid}/guest_invites` | `list_guest_invites()` | `app.py:1886` |
| POST | `/api/chats/{cid}/guest_invites` | `create_guest_invite()` | `app.py:1868` |
| DELETE | `/api/chats/{cid}/guest_invites/{gid}` | `revoke_guest_invite()` | `app.py:1890` |
| DELETE | `/api/chats/{cid}/lorebook` | `detach_lore()` | `app.py:1551` |
| POST | `/api/chats/{cid}/lorebook` | `bind_lore()` | `app.py:1535` |
| POST | `/api/chats/{cid}/lorebooks` | `attach_lore()` | `app.py:1495` |
| DELETE | `/api/chats/{cid}/lorebooks/{lid}` | `detach_book()` | `app.py:1520` |
| GET | `/api/chats/{cid}/paradox_policy` | `paradox_policy_get()` | `app.py:2142` |
| PUT | `/api/chats/{cid}/paradox_policy` | `paradox_policy_put()` | `app.py:2146` |
| GET | `/api/chats/{cid}/persona_private_history` | `pph_get()` | `app.py:2001` |
| PUT | `/api/chats/{cid}/persona_private_history` | `pph_put()` | `app.py:2014` |
| GET | `/api/chats/{cid}/personas` | `chat_list_extra_personas()` | `app.py:1766` |
| POST | `/api/chats/{cid}/personas` | `chat_add_persona()` | `app.py:1811` |
| DELETE | `/api/chats/{cid}/personas/{pid}` | `chat_del_persona()` | `app.py:1825` |
| PUT | `/api/chats/{cid}/personas/{pid}/station` | `chat_persona_station()` | `app.py:1776` |
| GET | `/api/chats/{cid}/promises` | `get_promise_ledger()` | `app.py:1723` |
| GET | `/api/chats/{cid}/promotable` | `list_promotable_presences()` | `app.py:1715` |
| POST | `/api/chats/{cid}/promotions/confirm` | `confirm_promotion()` | `app.py:1740` |
| POST | `/api/chats/{cid}/promotions/draft` | `draft_promotion()` | `app.py:1727` |
| POST | `/api/chats/{cid}/turns` | `turn_new()` | `app.py:2885` |
| POST | `/api/chats/{cid}/turns/{idx}/player_input` | `submit_extra_player_input()` | `app.py:1830` |
| GET | `/api/chats/{cid}/world` | `world_get()` | `app.py:2019` |
| PUT | `/api/chats/{cid}/world` | `world_put()` | `app.py:2023` |
| POST | `/api/guest/input` | `guest_input()` | `app.py:1948` |
| GET | `/api/guest/state` | `guest_state()` | `app.py:1914` |
| POST | `/api/join` | `join_with_code()` | `app.py:1896` |
| DELETE | `/api/lore_entries/{eid}` | `lore_entry_delete()` | `app.py:1470` |
| PUT | `/api/lore_entries/{eid}` | `lore_entry_edit()` | `app.py:1398` |
| DELETE | `/api/lorebook_links/{link_id}` | `lorebook_link_delete()` | `app.py:924` |
| PUT | `/api/lorebook_links/{link_id}` | `lorebook_link_update()` | `app.py:919` |
| POST | `/api/lorebooks` | `lore_create()` | `app.py:1233` |
| POST | `/api/lorebooks/import` | `lore_import()` | `app.py:962` |
| DELETE | `/api/lorebooks/{lid}` | `lore_delete()` | `app.py:1325` |
| GET | `/api/lorebooks/{lid}` | `lore_get()` | `app.py:1213` |
| PUT | `/api/lorebooks/{lid}` | `lore_edit()` | `app.py:1255` |
| POST | `/api/lorebooks/{lid}/apply_plan` | `lorebook_apply_plan()` | `app.py:948` |
| POST | `/api/lorebooks/{lid}/entries` | `lore_entry_create()` | `app.py:1369` |
| GET | `/api/lorebooks/{lid}/export` | `lore_export()` | `app.py:1331` |
| POST | `/api/lorebooks/{lid}/generate` | `lore_generate()` | `app.py:1355` |
| POST | `/api/lorebooks/{lid}/generate_plan` | `lorebook_generate_plan()` | `app.py:929` |
| GET | `/api/lorebooks/{lid}/links` | `lorebook_links_get()` | `app.py:892` |
| POST | `/api/lorebooks/{lid}/links` | `lorebook_link_create()` | `app.py:897` |
| POST | `/api/lorebooks/{lid}/move` | `lorebook_move()` | `app.py:874` |
| POST | `/api/lorebooks/{lid}/reinterpret` | `lore_reinterpret_route()` | `app.py:1343` |
| POST | `/api/lorebooks/{lid}/reorder` | `lorebook_reorder()` | `app.py:883` |
| DELETE | `/api/memories/{mid}` | `mem_del()` | `app.py:2879` |
| PUT | `/api/memories/{mid}` | `mem_edit()` | `app.py:2860` |
| GET | `/api/nsfw` | `get_nsfw()` | `app.py:845` |
| PUT | `/api/nsfw` | `set_nsfw()` | `app.py:849` |
| POST | `/api/personas` | `persona_create()` | `app.py:1155` |
| POST | `/api/personas/generate` | `persona_generate()` | `app.py:1145` |
| POST | `/api/personas/import` | `persona_import()` | `app.py:1175` |
| DELETE | `/api/personas/{pid}` | `persona_del()` | `app.py:1207` |
| PUT | `/api/personas/{pid}` | `persona_edit()` | `app.py:1198` |
| GET | `/api/personas/{pid}/export` | `persona_export()` | `app.py:1189` |
| PUT | `/api/prompt_presets` | `save_preset()` | `app.py:824` |
| DELETE | `/api/prompt_presets/{name}` | `del_preset()` | `app.py:831` |
| POST | `/api/providers` | `add_provider()` | `app.py:1012` |
| DELETE | `/api/providers/{pid}` | `del_provider()` | `app.py:1035` |
| PUT | `/api/providers/{pid}` | `put_provider()` | `app.py:1019` |
| GET | `/api/providers/{pid}/models` | `models()` | `app.py:1040` |
| POST | `/api/steps/{sid}/activate` | `step_activate()` | `app.py:3479` |
| POST | `/api/steps/{sid}/edit` | `step_edit()` | `app.py:3469` |
| POST | `/api/steps/{sid}/reroll` | `step_reroll()` | `app.py:3422` |
| DELETE | `/api/turns/{tid}` | `turn_del()` | `app.py:3492` |
| POST | `/api/turns/{tid}/branch` | `turn_branch()` | `app.py:2924` |
| PUT | `/api/turns/{tid}/input` | `edit_input()` | `app.py:3276` |
| GET | `/api/turns/{tid}/pipeline` | `pipeline_get()` | `app.py:3322` |
| PUT | `/api/turns/{tid}/prose` | `edit_prose()` | `app.py:3291` |
| POST | `/api/turns/{tid}/reroll` | `turn_reroll()` | `app.py:3353` |
| POST | `/api/turns/{tid}/rerun` | `turn_rerun()` | `app.py:3363` |
| POST | `/api/turns/{tid}/resume` | `turn_resume()` | `app.py:3390` |
| GET | `/api/updates/check` | `updates_check()` | `app.py:857` |
| POST | `/api/updates/install` | `updates_install()` | `app.py:861` |
| GET | `/guest` | `guest_page()` | `app.py:132` |
| GET | `/login` | `login_page()` | `app.py:144` |

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
| `chats` | `id`, `name`, `persona_id`, `lorebook_id`, `scenario`, `created` |
| `chat_chars` | `chat_id`, `char_id`, `status`, `state` |
| `chat_char_frames` | `chat_id`, `char_id`, `frame_id`, `status`, `state` |
| `chat_personas` | `chat_id`, `persona_id`, `status`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `frame_id` |
| `turn_player_inputs` | `id`, `chat_id`, `turn_idx`, `persona_id`, `input`, `created` |
| `guest_grants` | `id`, `chat_id`, `persona_id`, `code_hash`, `code_expires`, `redeemed_at`, `token_hash`, `token_expires`, `revoked`, `created` |
| `host_sessions` | `id`, `token_hash`, `created`, `expires` |
| `frames` | `id`, `chat_id`, `label`, `ordinal`, `kind`, `travelers`, `nonexistent_cast`, `created`, `parent_frame_id`, `split_turn_idx`, `merged_turn_idx` |
| `turns` | `id`, `chat_id`, `idx`, `player_input`, `created`, `frame_id` |
| `steps` | `id`, `turn_id`, `key`, `label`, `ord`, `stale` |
| `variants` | `id`, `step_id`, `content`, `created`, `active` |
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

### `static/js/app.js` (734 lines)

Sections: Boot & sidebar (`:1`); New chat wizard (`:188`); NSFW (`:605`); Composer (`:633`); Init (`:692`).

Declared functions: `boot()`, `renderSide()`, `renderChatSidebar()`, `newChatWizard()`, `renderWizardChoice()`, `wizardState()`, `wizardFromScratch()`, `renderWizardPersona()`, `renderWizardCharacters()`, `renderWizardScenario()`, `runWizard()`, `renderCharacterSidebar()`, `renderPersonaSidebar()`, `renderLegacyLoreSidebar()`, `updateNSFWBtn()`, `toggleNSFW()`, `resizeComposer()`.

### `static/js/chat.js` (1649 lines)

Sections: Scene mood (`:1`); Pipeline drawer (`:536`); Relationship viewer (`:820`); Memory browser (`:879`); Private history (`:1597`).

Declared functions: `detectSceneMood()`, `applySceneMood()`, `observeSceneMood()`, `openChat()`, `renderFrameBar()`, `switchFrame()`, `updateChatScopedButtons()`, `renderChat()`, `branchTurn()`, `editTurnInput()`, `editTurnProse()`, `liveReset()`, `friendlyPhase()`, `turnStatusStart()`, `turnStatusSet()`, `turnStatusStop()`, `liveStep()`, `handleEvt()`, `runStream()`, `confirmCheckpointRestore()`, `runReroll()`, `rerollTurn()`, `exportChat()`, `importChatModal()`, `openPipeline()`, `relMeter()`, `relationshipModal()`, `memModal()`, `exportCharacterMemories()`, `importCharacterMemoriesModal()`, `memQS()`, `memCharId()`, `loadMemoryBrowse()`, `getMemUI()`, `renderMemorySummary()`, `sortedMems()`, `renderMemoryList()`, `memoryCard()`, `fieldWrap()`, `reloadMemView()`, `runMemorySearch()`, `showNewMemoryForm()`, `consolidateMemories()`, `previewMemoryContext()`, `chatPH()`, `personaPH()`.

### `static/js/components.js` (436 lines)

Sections: Modal (`:18`); confirm()/prompt() replacements (`:77`); Toasts (`:167`); Background tasks (`:179`); Form helpers (`:249`); Model picker (`:377`).

Declared functions: `el()`, `modal()`, `closeModal()`, `closeAllModals()`, `_confirmOverlay()`, `confirmModal()`, `promptModal()`, `toast()`, `renderActivity()`, `elapsedLabel()`, `backgroundTask()`, `buttonTask()`, `loadingBlock()`, `emptyState()`, `fText()`, `fArea()`, `fSelect()`, `fNum()`, `fStrList()`, `fList()`, `fAbilities()`, `fTraits()`, `fValues()`, `fGoals()`, `fSenses()`, `fLatent()`, `fPronouns()`, `phEditor()`, `fetchModels()`, `modelCombobox()`, `emitChange()`, `load()`, `showDD()`.

### `static/js/editors.js` (597 lines)

Sections: Background-character promotion (`:362`); Import (file upload) (`:411`); Generate (`:476`); Lorebook generate (`:494`); Lorebooks (`:511`); Export (`:585`).

Declared functions: `defaultCharacterSheet()`, `greetingCarousel()`, `quickStartModal()`, `charEditor()`, `personaEditor()`, `promotionReviewModal()`, `promoteBackgroundPresence()`, `importModal()`, `generateModal()`, `generateLoreModal()`, `loreModal()`, `exportCharacter()`, `exportPersona()`, `exportLorebook()`.

### `static/js/lorebooks.js` (3339 lines)

Sections: Library sidebar (`:240`); Data loading (`:447`); Workspace (`:562`); Book metadata and tree operations (`:1137`); Entry editor (`:1596`); Lorebook relationships (`:2333`); Advanced generator (`:2784`).

Declared functions: `loreBookTypeIcon()`, `loreLinkTypes()`, `normalizeLoreBook()`, `loreOwnershipKey()`, `loreBooksByParent()`, `loreBookMatches()`, `loreVisibleIds()`, `loreBookLabel()`, `parseStoredJSON()`, `loreField()`, `loreSelect()`, `loreBookOptions()`, `renderLoreLibrarySidebar()`, `renderNode()`, `loadLoreWorkspaceData()`, `collectLoreLinkTargets()`, `loreWorkspaceVisible()`, `renderLoreWorkspaceBody()`, `openLoreWorkspace()`, `renderLoreInspector()`, `selectTab()`, `buildLoreWorkspace()`, `renderWorkspaceTree()`, `renderNode()`, `renderTreeList()`, `renderLoreBookEditor()`, `moveLoreBook()`, `reorderLoreBook()`, `promoteLoreBook()`, `demoteLoreBook()`, `createSiblingLoreBook()`, `createLoreBookDialog()`, `refreshLoreUI()`, `renderLoreEntries()`, `renderList()`, `buildLoreEntryCard()`, `splitNumberList()`, `reinterpretLoreBook()`, `generateLoreEntriesPrompt()`, `buildDirectLoreRequest()`, `renderRelationshipOverview()`, `renderLoreRelationshipEditor()`, `renderRelationshipList()`, `showNewRelationshipForm()`, `renderLoreGenerator()`, `normalizeGeneratorPlan()`, `renderLorePlanPreview()`, `renderOperations()`, `planStat()`, `renderAnalysisSection()`, `addPlanGroup()`, `stripPlanUIFields()`, `acceptedGeneratorPlan()`.

### `static/js/settings.js` (1378 lines)

Sections: Chat tool modals (`:1`); API connections (`:795`); Software updates (host-only; git fast-forward from GitHub origin) (`:1237`); Prompts (`:1346`).

Declared functions: `selectTab()`, `renderCastTab()`, `renderLorebooksTab()`, `renderBookNode()`, `renderMultiplayerTab()`, `renderFramesTab()`, `renderFramesListPanel()`, `renderPersonaStationingPanel()`, `renderParadoxPanel()`, `renderBackgroundPresencesPanel()`, `renderGuestInvitePanel()`, `renderInsightsTab()`, `renderDramaticIronyPanel()`, `renderPromiseLedgerPanel()`, `modelRecommendationsBlock()`, `renderFirstRunProviderSetup()`, `renderFullApiSettings()`, `propagateToFollowers()`, `renderUpdateChecking()`, `renderUpdateError()`, `renderUpdateStatus()`, `runUpdateInstall()`, `renderUpdateDone()`.

### `static/js/utils.js` (105 lines)

Sections: API (`:30`); Download (`:98`).

Declared functions: `hasDefaultModel()`, `safeId()`, `splitCL()`, `numOr()`, `api()`, `streamPost()`, `downloadJSON()`.
