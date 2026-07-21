# Generated Code Map

> Regenerate with `python tools/generate_code_map.py`. Do not hand-edit this file.

## Python modules

| Module | Lines | Purpose | Local dependencies |
|---|---:|---|---|
| `agents/__init__.py` | 81 | Backward-compatible facade for the role-specific agent package. | `agents.character`, `agents.common`, `agents.director`, `agents.loops`, `agents.mapping`, `agents.narration`, `agents.perception`, `agents.runtime`, `agents.storage`, `scene` |
| `agents/background.py` | 250 |  | `agents.common`, `commit`, `db`, `prompts`, `schemas`, `spatial` |
| `agents/character.py` | 158 | Private character decision agent. | `agents.common`, `character_schema`, `frames`, `memory`, `prompts`, `scene`, `schemas`, `spatial`, `theory_of_mind` |
| `agents/common.py` | 1302 | Shared normalization, lore, delivery, and perception helpers. | `character_schema`, `db`, `llm_quality`, `memory`, `providers`, `scene`, `schemas`, `spatial`, `theory_of_mind` |
| `agents/director.py` | 842 | Scene establishment, player interpretation, and objective resolution. | `agents.common`, `character_schema`, `db`, `memory`, `paradox`, `prompts`, `scene`, `schemas`, `spatial` |
| `agents/loops.py` | 428 | Reaction loops, interaction rounds, and deterministic micro-perception. | `agents.character`, `agents.common`, `character_schema`, `scene`, `spatial` |
| `agents/mapping.py` | 178 | Lore routing, cached recall, and retrieval staging. | `agents.common`, `character_schema`, `db`, `memory`, `prompts`, `scene` |
| `agents/narration.py` | 325 | Player-facing narration agent. | `agents.common`, `db`, `prompts`, `scene`, `schemas` |
| `agents/perception.py` | 657 | Opening, action-onset, and outcome observer views. | `agents.common`, `character_schema`, `db`, `prompts`, `scene`, `spatial` |
| `agents/runtime.py` | 881 | Pipeline plans, dispatch, streaming, cancellation, resume, and reruns. | `agents.background`, `agents.character`, `agents.common`, `agents.director`, `agents.loops`, `agents.mapping`, `agents.narration`, `agents.perception`, `agents.storage`, `character_schema`, `checkpoints`, `commit`, `db`, `pipeline_context`, `providers`, `scene` |
| `agents/storage.py` | 72 | Step and active-variant persistence helpers. | `db` |
| `app.py` | 3403 | FastAPI application, resource CRUD, import/export, turn control, and streaming endpoints. | `agents`, `character_schema`, `checkpoints`, `commit`, `db`, `frames`, `greetings`, `guest_access`, `importers`, `memory`, `paradox`, `pipeline_context`, `prompts`, `providers`, `scene` |
| `character_schema.py` | 574 | Versioned character/persona defaults, normalization, accessors, and export payloads. | — |
| `checkpoints.py` | 467 | Whole-chat snapshots and checkpoint restore orchestration. | `db`, `memory` |
| `commit.py` | 1550 | Validated persistence of scene, entities, cast, lore, relationships, events, and memories. | `character_schema`, `db`, `frames`, `memory`, `paradox`, `prompts`, `providers`, `scene`, `spatial`, `spatial_frames`, `theory_of_mind` |
| `db.py` | 1137 | SQLite schema, migrations, connection management, transactions, and key/value world access. | — |
| `frames.py` | 193 |  | `db` |
| `greetings.py` | 140 |  | `agents.runtime`, `agents.storage`, `character_schema`, `db`, `llm_quality`, `memory`, `prompts` |
| `guest_access.py` | 303 |  | `db` |
| `importers.py` | 1267 | Native and AI-assisted character, persona, and lorebook import/generation. | `character_schema`, `db`, `memory`, `prompts`, `providers` |
| `llm_quality.py` | 263 | Strict JSON parsing, schema validation, and model-assisted repair. | `providers`, `schemas` |
| `logging_utils.py` | 110 | Structured timing and observability helpers. | — |
| `memory.py` | 2002 | Lorebook graph, memory retrieval/consolidation, relationships, and vector search. | `db`, `frames`, `prompts`, `providers` |
| `paradox.py` | 486 |  | `db`, `frames` |
| `pipeline_context.py` | 168 | Typed mutable context passed through a turn pipeline. | `db` |
| `prompt_cache.py` | 79 | Provider-specific prompt-cache helpers. | `providers` |
| `prompts.py` | 1124 | Default system prompts and prompt preset access. | `db` |
| `providers.py` | 1041 | Provider selection, retries, streaming, cancellation, model listing, and embeddings. | `db` |
| `scene.py` | 498 | Scene/cast/persona helpers, recent events, dialogue configuration, and private knowledge. | `character_schema`, `db`, `spatial` |
| `schemas.py` | 1618 | Pydantic output contracts and semantic validation for agent payloads. | — |
| `spatial.py` | 537 | Deterministic room, barrier, hearing, visibility, placement, and scene-diff logic. | — |
| `spatial_frames.py` | 693 |  | `character_schema`, `db`, `frames`, `paradox`, `scene`, `spatial` |
| `theory_of_mind.py` | 288 |  | — |

## Largest top-level functions

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
| `character_step()` | 44 | 115 lines |

### `agents/common.py`

| Function | Start | Size |
|---|---:|---:|
| `norm_sequence()` | 519 | 138 lines |
| `_check_narrator_fidelity()` | 1174 | 65 lines |
| `_strip_player_echo()` | 1022 | 56 lines |
| `_assert_plan_materialized()` | 77 | 55 lines |
| `_extract_authority_claims()` | 374 | 44 lines |
| `_inject_visible_actor()` | 890 | 41 lines |
| `canonicalize_positions()` | 785 | 35 lines |
| `_narration_person_counts()` | 1119 | 35 lines |

### `agents/director.py`

| Function | Start | Size |
|---|---:|---:|
| `director_resolve()` | 441 | 402 lines |
| `director_interpret()` | 125 | 260 lines |
| `director_establish()` | 57 | 67 lines |
| `_scan_for_untracked_restraint()` | 400 | 40 lines |

### `agents/loops.py`

| Function | Start | Size |
|---|---:|---:|
| `interaction_loop()` | 95 | 264 lines |
| `reaction_loop()` | 360 | 69 lines |
| `deterministic_micro_perception()` | 29 | 65 lines |

### `agents/mapping.py`

| Function | Start | Size |
|---|---:|---:|
| `mapping_stage()` | 31 | 80 lines |
| `mapping_quick()` | 112 | 67 lines |

### `agents/narration.py`

| Function | Start | Size |
|---|---:|---:|
| `narrator_extra()` | 198 | 128 lines |
| `narrator()` | 111 | 86 lines |
| `_resolve_narration_person()` | 24 | 47 lines |
| `_generate_narration()` | 86 | 24 lines |

### `agents/perception.py`

| Function | Start | Size |
|---|---:|---:|
| `perception_outcome()` | 342 | 316 lines |
| `perception_act()` | 174 | 167 lines |
| `perception_establish()` | 50 | 123 lines |

### `agents/runtime.py`

| Function | Start | Size |
|---|---:|---:|
| `_run_pipeline()` | 512 | 318 lines |
| `build_plan()` | 365 | 59 lines |
| `resume_key_for_turn()` | 310 | 54 lines |
| `run_pipeline()` | 831 | 51 lines |
| `_stream_one()` | 201 | 48 lines |
| `_stream_parallel()` | 250 | 45 lines |
| `_load_extra_players()` | 32 | 44 lines |
| `_rehydrate_loop_results()` | 470 | 41 lines |

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
| `chat_import()` | 2271 | 358 lines |
| `turn_branch()` | 2813 | 336 lines |
| `_remap_cp_blob()` | 532 | 135 lines |
| `chat_export()` | 2121 | 97 lines |
| `chat_get()` | 1478 | 94 lines |
| `confirm_promotion()` | 1640 | 73 lines |
| `lore_entry_edit()` | 1298 | 70 lines |
| `lore_edit()` | 1155 | 68 lines |

### `character_schema.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_character_data()` | 308 | 89 lines |
| `default_character_data()` | 35 | 57 lines |
| `normalize_persona_data()` | 398 | 39 lines |
| `_coerce_appearance()` | 278 | 29 lines |
| `default_persona_data()` | 101 | 24 lines |
| `_normalize_latent()` | 242 | 21 lines |
| `senses_as_text()` | 536 | 20 lines |
| `_legacy_private_history()` | 209 | 19 lines |

### `checkpoints.py`

| Function | Start | Size |
|---|---:|---:|
| `snapshot_state()` | 12 | 116 lines |
| `_restore_books()` | 129 | 84 lines |
| `insert_world_tables()` | 288 | 62 lines |
| `_restore_checkpoint_body()` | 351 | 60 lines |
| `_restore_frames()` | 236 | 38 lines |
| `refresh_checkpoint()` | 437 | 31 lines |
| `restore_checkpoint()` | 214 | 21 lines |
| `ensure_checkpoint()` | 417 | 19 lines |

### `commit.py`

| Function | Start | Size |
|---|---:|---:|
| `prepare_memory_commit()` | 1103 | 177 lines |
| `track_background_presences()` | 492 | 138 lines |
| `prepare_mapping_commit()` | 804 | 132 lines |
| `commit_mapping()` | 938 | 120 lines |
| `commit_world_entities()` | 251 | 100 lines |
| `prepare_scene_commit()` | 121 | 93 lines |
| `_apply_mapping_book_ops()` | 729 | 74 lines |
| `_commit_all_locked()` | 1420 | 72 lines |

### `db.py`

| Function | Start | Size |
|---|---:|---:|
| `init()` | 1045 | 49 lines |
| `transaction()` | 948 | 36 lines |
| `conn()` | 923 | 23 lines |
| `_backfill_resource_uids()` | 1027 | 17 lines |
| `qi()` | 990 | 16 lines |
| `parse_scoped_world_key()` | 52 | 13 lines |
| `_execute_retry()` | 892 | 13 lines |
| `wget_for_frame()` | 1119 | 12 lines |

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
| `start_story()` | 80 | 61 lines |
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
| `generate_lorebook_plan()` | 956 | 135 lines |
| `import_lorebook()` | 806 | 114 lines |
| `apply_lorebook_plan()` | 1092 | 111 lines |
| `generate_lore_entries()` | 1203 | 65 lines |
| `_reinterpret_entries()` | 744 | 61 lines |
| `_jparse()` | 35 | 59 lines |
| `import_character()` | 416 | 59 lines |
| `import_persona()` | 476 | 56 lines |

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

### `memory.py`

| Function | Start | Size |
|---|---:|---:|
| `search_memories()` | 999 | 103 lines |
| `consolidate_character_memory()` | 1199 | 80 lines |
| `restore_lorebook()` | 1593 | 79 lines |
| `resolve_lorebook_graph()` | 331 | 76 lines |
| `lorebook_manifest()` | 453 | 65 lines |
| `duplicate_lorebook_tree_for_chat()` | 1735 | 58 lines |
| `prepare_chat_memory_restore()` | 1345 | 48 lines |
| `add_lorebook_link()` | 230 | 43 lines |

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
| `get_prompt()` | 1115 | 10 lines |
| `presets()` | 1106 | 2 lines |
| `active_preset()` | 1109 | 2 lines |
| `nsfw_enabled()` | 1112 | 2 lines |

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
| `private_knowledge_for()` | 455 | 44 lines |
| `recent_events()` | 201 | 36 lines |
| `is_player_speaker()` | 304 | 29 lines |
| `active_cast()` | 51 | 27 lines |
| `_ability_mod()` | 270 | 24 lines |
| `director_context()` | 238 | 22 lines |
| `interaction_limits()` | 360 | 18 lines |
| `cast_scene_context()` | 436 | 18 lines |

### `schemas.py`

| Function | Start | Size |
|---|---:|---:|
| `preprocess_llm_output()` | 1103 | 189 lines |
| `semantic_output_errors()` | 1489 | 76 lines |
| `validate_llm_output_strict()` | 1566 | 53 lines |
| `_coerce_str_list()` | 12 | 33 lines |
| `_coerce_considered_responses()` | 954 | 32 lines |
| `validate_llm_output()` | 1293 | 29 lines |
| `_coerce_conditions()` | 1017 | 27 lines |
| `_hoist_misplaced_entity_siblings()` | 1059 | 21 lines |

### `spatial.py`

| Function | Start | Size |
|---|---:|---:|
| `visible_adjacent_rooms()` | 265 | 113 lines |
| `merge_scene_with_diff()` | 417 | 76 lines |
| `nearby_rooms()` | 213 | 51 lines |
| `spatial_rel()` | 117 | 48 lines |
| `hear_level()` | 166 | 43 lines |
| `_merge_room()` | 379 | 37 lines |
| `validate_operations()` | 510 | 28 lines |
| `normalize_scene_barriers()` | 70 | 22 lines |

### `spatial_frames.py`

| Function | Start | Size |
|---|---:|---:|
| `perform_split()` | 424 | 93 lines |
| `infer_companion_carry()` | 231 | 88 lines |
| `infer_vehicle_zones()` | 144 | 85 lines |
| `perform_merge()` | 595 | 69 lines |
| `detect_split()` | 378 | 44 lines |
| `detect_merge()` | 531 | 40 lines |
| `zone_groups()` | 321 | 30 lines |
| `detect_and_reconcile()` | 666 | 28 lines |

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

## FastAPI routes

| Method | Path | Handler | Source |
|---|---|---|---|
| GET | `/` | `index()` | `app.py:136` |
| PUT | `/api/active_preset` | `set_active()` | `app.py:764` |
| PUT | `/api/agent_models` | `put_agent_models()` | `app.py:743` |
| POST | `/api/auth/login` | `auth_login()` | `app.py:175` |
| POST | `/api/auth/logout` | `auth_logout()` | `app.py:190` |
| POST | `/api/auth/setup` | `auth_setup()` | `app.py:162` |
| GET | `/api/auth/status` | `auth_status()` | `app.py:153` |
| GET | `/api/bootstrap` | `bootstrap()` | `app.py:719` |
| POST | `/api/characters` | `char_create()` | `app.py:971` |
| POST | `/api/characters/generate` | `char_generate()` | `app.py:961` |
| POST | `/api/characters/import` | `char_import()` | `app.py:992` |
| DELETE | `/api/characters/{cid}` | `char_del()` | `app.py:1038` |
| PUT | `/api/characters/{cid}` | `char_edit()` | `app.py:1029` |
| GET | `/api/characters/{cid}/export` | `char_export()` | `app.py:1021` |
| POST | `/api/characters/{cid}/start` | `character_start_story()` | `app.py:1006` |
| POST | `/api/chats` | `chat_new()` | `app.py:1377` |
| POST | `/api/chats/import` | `chat_import()` | `app.py:2271` |
| DELETE | `/api/chats/{cid}` | `chat_del()` | `app.py:1460` |
| GET | `/api/chats/{cid}` | `chat_get()` | `app.py:1478` |
| PUT | `/api/chats/{cid}` | `chat_edit()` | `app.py:1383` |
| POST | `/api/chats/{cid}/abort` | `chat_abort()` | `app.py:2809` |
| GET | `/api/chats/{cid}/attire` | `attire_get()` | `app.py:1986` |
| PUT | `/api/chats/{cid}/attire` | `attire_put()` | `app.py:1993` |
| POST | `/api/chats/{cid}/characters` | `chat_add_char()` | `app.py:1574` |
| DELETE | `/api/chats/{cid}/characters/{ch}` | `chat_del_char()` | `app.py:1922` |
| GET | `/api/chats/{cid}/characters/{ch}/memories` | `mem_list()` | `app.py:2632` |
| POST | `/api/chats/{cid}/characters/{ch}/memories` | `mem_add()` | `app.py:2727` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/consolidate` | `mem_consolidate()` | `app.py:2716` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/export` | `mem_export()` | `app.py:2671` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/import` | `mem_import()` | `app.py:2682` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/search` | `mem_search()` | `app.py:2653` |
| GET | `/api/chats/{cid}/characters/{ch}/memory-context` | `memory_context_preview()` | `app.py:2692` |
| GET | `/api/chats/{cid}/characters/{ch}/private_history` | `ph_get()` | `app.py:1931` |
| PUT | `/api/chats/{cid}/characters/{ch}/private_history` | `ph_put()` | `app.py:1941` |
| GET | `/api/chats/{cid}/characters/{ch}/relationships` | `relationships_get()` | `app.py:2705` |
| GET | `/api/chats/{cid}/dialogue_config` | `dlg_get()` | `app.py:2002` |
| PUT | `/api/chats/{cid}/dialogue_config` | `dlg_put()` | `app.py:2006` |
| GET | `/api/chats/{cid}/dramatic_irony` | `get_dramatic_irony_feed()` | `app.py:1619` |
| GET | `/api/chats/{cid}/export` | `chat_export()` | `app.py:2121` |
| GET | `/api/chats/{cid}/fixed_points` | `fixed_points_list()` | `app.py:2084` |
| POST | `/api/chats/{cid}/fixed_points` | `fixed_points_create()` | `app.py:2094` |
| DELETE | `/api/chats/{cid}/fixed_points/{anchor_id}` | `fixed_points_delete()` | `app.py:2116` |
| GET | `/api/chats/{cid}/frames` | `frames_list()` | `app.py:2038` |
| POST | `/api/chats/{cid}/frames` | `frames_create()` | `app.py:2042` |
| GET | `/api/chats/{cid}/guest_invites` | `list_guest_invites()` | `app.py:1835` |
| POST | `/api/chats/{cid}/guest_invites` | `create_guest_invite()` | `app.py:1817` |
| DELETE | `/api/chats/{cid}/guest_invites/{gid}` | `revoke_guest_invite()` | `app.py:1839` |
| DELETE | `/api/chats/{cid}/lorebook` | `detach_lore()` | `app.py:1451` |
| POST | `/api/chats/{cid}/lorebook` | `bind_lore()` | `app.py:1435` |
| POST | `/api/chats/{cid}/lorebooks` | `attach_lore()` | `app.py:1395` |
| DELETE | `/api/chats/{cid}/lorebooks/{lid}` | `detach_book()` | `app.py:1420` |
| GET | `/api/chats/{cid}/paradox_policy` | `paradox_policy_get()` | `app.py:2069` |
| PUT | `/api/chats/{cid}/paradox_policy` | `paradox_policy_put()` | `app.py:2073` |
| GET | `/api/chats/{cid}/persona_private_history` | `pph_get()` | `app.py:1950` |
| PUT | `/api/chats/{cid}/persona_private_history` | `pph_put()` | `app.py:1963` |
| GET | `/api/chats/{cid}/personas` | `chat_list_extra_personas()` | `app.py:1715` |
| POST | `/api/chats/{cid}/personas` | `chat_add_persona()` | `app.py:1760` |
| DELETE | `/api/chats/{cid}/personas/{pid}` | `chat_del_persona()` | `app.py:1774` |
| PUT | `/api/chats/{cid}/personas/{pid}/station` | `chat_persona_station()` | `app.py:1725` |
| GET | `/api/chats/{cid}/promises` | `get_promise_ledger()` | `app.py:1623` |
| GET | `/api/chats/{cid}/promotable` | `list_promotable_presences()` | `app.py:1615` |
| POST | `/api/chats/{cid}/promotions/confirm` | `confirm_promotion()` | `app.py:1640` |
| POST | `/api/chats/{cid}/promotions/draft` | `draft_promotion()` | `app.py:1627` |
| POST | `/api/chats/{cid}/turns` | `turn_new()` | `app.py:2774` |
| POST | `/api/chats/{cid}/turns/{idx}/player_input` | `submit_extra_player_input()` | `app.py:1779` |
| GET | `/api/chats/{cid}/world` | `world_get()` | `app.py:1968` |
| PUT | `/api/chats/{cid}/world` | `world_put()` | `app.py:1972` |
| POST | `/api/guest/input` | `guest_input()` | `app.py:1897` |
| GET | `/api/guest/state` | `guest_state()` | `app.py:1863` |
| POST | `/api/join` | `join_with_code()` | `app.py:1845` |
| DELETE | `/api/lore_entries/{eid}` | `lore_entry_delete()` | `app.py:1370` |
| PUT | `/api/lore_entries/{eid}` | `lore_entry_edit()` | `app.py:1298` |
| DELETE | `/api/lorebook_links/{link_id}` | `lorebook_link_delete()` | `app.py:837` |
| PUT | `/api/lorebook_links/{link_id}` | `lorebook_link_update()` | `app.py:832` |
| POST | `/api/lorebooks` | `lore_create()` | `app.py:1133` |
| POST | `/api/lorebooks/import` | `lore_import()` | `app.py:875` |
| DELETE | `/api/lorebooks/{lid}` | `lore_delete()` | `app.py:1225` |
| GET | `/api/lorebooks/{lid}` | `lore_get()` | `app.py:1113` |
| PUT | `/api/lorebooks/{lid}` | `lore_edit()` | `app.py:1155` |
| POST | `/api/lorebooks/{lid}/apply_plan` | `lorebook_apply_plan()` | `app.py:861` |
| POST | `/api/lorebooks/{lid}/entries` | `lore_entry_create()` | `app.py:1269` |
| GET | `/api/lorebooks/{lid}/export` | `lore_export()` | `app.py:1231` |
| POST | `/api/lorebooks/{lid}/generate` | `lore_generate()` | `app.py:1255` |
| POST | `/api/lorebooks/{lid}/generate_plan` | `lorebook_generate_plan()` | `app.py:842` |
| GET | `/api/lorebooks/{lid}/links` | `lorebook_links_get()` | `app.py:805` |
| POST | `/api/lorebooks/{lid}/links` | `lorebook_link_create()` | `app.py:810` |
| POST | `/api/lorebooks/{lid}/move` | `lorebook_move()` | `app.py:787` |
| POST | `/api/lorebooks/{lid}/reinterpret` | `lore_reinterpret_route()` | `app.py:1243` |
| POST | `/api/lorebooks/{lid}/reorder` | `lorebook_reorder()` | `app.py:796` |
| DELETE | `/api/memories/{mid}` | `mem_del()` | `app.py:2768` |
| PUT | `/api/memories/{mid}` | `mem_edit()` | `app.py:2749` |
| GET | `/api/nsfw` | `get_nsfw()` | `app.py:769` |
| PUT | `/api/nsfw` | `set_nsfw()` | `app.py:773` |
| POST | `/api/personas` | `persona_create()` | `app.py:1055` |
| POST | `/api/personas/generate` | `persona_generate()` | `app.py:1045` |
| POST | `/api/personas/import` | `persona_import()` | `app.py:1075` |
| DELETE | `/api/personas/{pid}` | `persona_del()` | `app.py:1107` |
| PUT | `/api/personas/{pid}` | `persona_edit()` | `app.py:1098` |
| GET | `/api/personas/{pid}/export` | `persona_export()` | `app.py:1089` |
| PUT | `/api/prompt_presets` | `save_preset()` | `app.py:748` |
| DELETE | `/api/prompt_presets/{name}` | `del_preset()` | `app.py:755` |
| POST | `/api/providers` | `add_provider()` | `app.py:925` |
| DELETE | `/api/providers/{pid}` | `del_provider()` | `app.py:948` |
| PUT | `/api/providers/{pid}` | `put_provider()` | `app.py:932` |
| GET | `/api/providers/{pid}/models` | `models()` | `app.py:953` |
| POST | `/api/steps/{sid}/activate` | `step_activate()` | `app.py:3354` |
| POST | `/api/steps/{sid}/edit` | `step_edit()` | `app.py:3344` |
| POST | `/api/steps/{sid}/reroll` | `step_reroll()` | `app.py:3297` |
| DELETE | `/api/turns/{tid}` | `turn_del()` | `app.py:3367` |
| POST | `/api/turns/{tid}/branch` | `turn_branch()` | `app.py:2813` |
| PUT | `/api/turns/{tid}/input` | `edit_input()` | `app.py:3151` |
| GET | `/api/turns/{tid}/pipeline` | `pipeline_get()` | `app.py:3197` |
| PUT | `/api/turns/{tid}/prose` | `edit_prose()` | `app.py:3166` |
| POST | `/api/turns/{tid}/reroll` | `turn_reroll()` | `app.py:3228` |
| POST | `/api/turns/{tid}/rerun` | `turn_rerun()` | `app.py:3238` |
| POST | `/api/turns/{tid}/resume` | `turn_resume()` | `app.py:3265` |
| GET | `/guest` | `guest_page()` | `app.py:128` |
| GET | `/login` | `login_page()` | `app.py:140` |

## Database tables

| Table | Columns |
|---|---|
| `schema_meta` | `key` |
| `providers` | `id`, `name`, `kind`, `base_url`, `api_key`, `enabled` |
| `settings` | `key`, `value` |
| `characters` | `id`, `name`, `sheet`, `source`, `created`, `resource_uid` |
| `personas` | `id`, `name`, `sheet`, `source`, `resource_uid` |
| `lorebooks` | `id`, `name`, `chat_id`, `origin_id`, `book_type`, `summary`, `resource_uid`, `parent_id`, `scope_world_id`, `scope_location_id`, `inheritance_mode`, `sort_order`, `anchor_entity_id` |
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
| `fiction_worlds` | `world_id`, `chat_id`, `parent_world_id`, `name`, `kind`, `payload`, `created_turn_id`, `retired_turn_id` |
| `fiction_locations` | `location_id`, `chat_id`, `world_id`, `parent_location_id`, `kind`, `name`, `payload` |
| `transit_edges` | `edge_id`, `chat_id`, `from_world_id`, `from_location_id`, `to_world_id`, `to_location_id`, `kind`, `payload` |

## Frontend JavaScript

### `static/js/app.js` (717 lines)

Sections: Boot & sidebar (`:1`); New chat wizard (`:188`); NSFW (`:588`); Composer (`:616`); Init (`:675`).

Declared functions: `boot()`, `renderSide()`, `renderChatSidebar()`, `newChatWizard()`, `renderWizardChoice()`, `wizardState()`, `wizardFromScratch()`, `renderWizardPersona()`, `renderWizardCharacters()`, `renderWizardScenario()`, `runWizard()`, `renderCharacterSidebar()`, `renderPersonaSidebar()`, `renderLegacyLoreSidebar()`, `updateNSFWBtn()`, `toggleNSFW()`, `resizeComposer()`.

### `static/js/chat.js` (1649 lines)

Sections: Scene mood (`:1`); Pipeline drawer (`:536`); Relationship viewer (`:820`); Memory browser (`:879`); Private history (`:1597`).

Declared functions: `detectSceneMood()`, `applySceneMood()`, `observeSceneMood()`, `openChat()`, `renderFrameBar()`, `switchFrame()`, `updateChatScopedButtons()`, `renderChat()`, `branchTurn()`, `editTurnInput()`, `editTurnProse()`, `liveReset()`, `friendlyPhase()`, `turnStatusStart()`, `turnStatusSet()`, `turnStatusStop()`, `liveStep()`, `handleEvt()`, `runStream()`, `confirmCheckpointRestore()`, `runReroll()`, `rerollTurn()`, `exportChat()`, `importChatModal()`, `openPipeline()`, `relMeter()`, `relationshipModal()`, `memModal()`, `exportCharacterMemories()`, `importCharacterMemoriesModal()`, `memQS()`, `memCharId()`, `loadMemoryBrowse()`, `getMemUI()`, `renderMemorySummary()`, `sortedMems()`, `renderMemoryList()`, `memoryCard()`, `fieldWrap()`, `reloadMemView()`, `runMemorySearch()`, `showNewMemoryForm()`, `consolidateMemories()`, `previewMemoryContext()`, `chatPH()`, `personaPH()`.

### `static/js/components.js` (436 lines)

Sections: Modal (`:18`); confirm()/prompt() replacements (`:77`); Toasts (`:167`); Background tasks (`:179`); Form helpers (`:249`); Model picker (`:377`).

Declared functions: `el()`, `modal()`, `closeModal()`, `closeAllModals()`, `_confirmOverlay()`, `confirmModal()`, `promptModal()`, `toast()`, `renderActivity()`, `elapsedLabel()`, `backgroundTask()`, `buttonTask()`, `loadingBlock()`, `emptyState()`, `fText()`, `fArea()`, `fSelect()`, `fNum()`, `fStrList()`, `fList()`, `fAbilities()`, `fTraits()`, `fValues()`, `fGoals()`, `fSenses()`, `fLatent()`, `fPronouns()`, `phEditor()`, `fetchModels()`, `modelCombobox()`, `emitChange()`, `load()`, `showDD()`.

### `static/js/editors.js` (421 lines)

Sections: Background-character promotion (`:192`); Import (file upload) (`:241`); Generate (`:300`); Lorebook generate (`:318`); Lorebooks (`:335`); Export (`:409`).

Declared functions: `defaultCharacterSheet()`, `charEditor()`, `personaEditor()`, `promotionReviewModal()`, `promoteBackgroundPresence()`, `importModal()`, `generateModal()`, `generateLoreModal()`, `loreModal()`, `exportCharacter()`, `exportPersona()`, `exportLorebook()`.

### `static/js/lorebooks.js` (3339 lines)

Sections: Library sidebar (`:240`); Data loading (`:447`); Workspace (`:562`); Book metadata and tree operations (`:1137`); Entry editor (`:1596`); Lorebook relationships (`:2333`); Advanced generator (`:2784`).

Declared functions: `loreBookTypeIcon()`, `loreLinkTypes()`, `normalizeLoreBook()`, `loreOwnershipKey()`, `loreBooksByParent()`, `loreBookMatches()`, `loreVisibleIds()`, `loreBookLabel()`, `parseStoredJSON()`, `loreField()`, `loreSelect()`, `loreBookOptions()`, `renderLoreLibrarySidebar()`, `renderNode()`, `loadLoreWorkspaceData()`, `collectLoreLinkTargets()`, `loreWorkspaceVisible()`, `renderLoreWorkspaceBody()`, `openLoreWorkspace()`, `renderLoreInspector()`, `selectTab()`, `buildLoreWorkspace()`, `renderWorkspaceTree()`, `renderNode()`, `renderTreeList()`, `renderLoreBookEditor()`, `moveLoreBook()`, `reorderLoreBook()`, `promoteLoreBook()`, `demoteLoreBook()`, `createSiblingLoreBook()`, `createLoreBookDialog()`, `refreshLoreUI()`, `renderLoreEntries()`, `renderList()`, `buildLoreEntryCard()`, `splitNumberList()`, `reinterpretLoreBook()`, `generateLoreEntriesPrompt()`, `buildDirectLoreRequest()`, `renderRelationshipOverview()`, `renderLoreRelationshipEditor()`, `renderRelationshipList()`, `showNewRelationshipForm()`, `renderLoreGenerator()`, `normalizeGeneratorPlan()`, `renderLorePlanPreview()`, `renderOperations()`, `planStat()`, `renderAnalysisSection()`, `addPlanGroup()`, `stripPlanUIFields()`, `acceptedGeneratorPlan()`.

### `static/js/settings.js` (1269 lines)

Sections: Chat tool modals (`:1`); API connections (`:795`); Prompts (`:1237`).

Declared functions: `selectTab()`, `renderCastTab()`, `renderLorebooksTab()`, `renderBookNode()`, `renderMultiplayerTab()`, `renderFramesTab()`, `renderFramesListPanel()`, `renderPersonaStationingPanel()`, `renderParadoxPanel()`, `renderBackgroundPresencesPanel()`, `renderGuestInvitePanel()`, `renderInsightsTab()`, `renderDramaticIronyPanel()`, `renderPromiseLedgerPanel()`, `modelRecommendationsBlock()`, `renderFirstRunProviderSetup()`, `renderFullApiSettings()`, `propagateToFollowers()`.

### `static/js/utils.js` (105 lines)

Sections: API (`:30`); Download (`:98`).

Declared functions: `hasDefaultModel()`, `safeId()`, `splitCL()`, `numOr()`, `api()`, `streamPost()`, `downloadJSON()`.
