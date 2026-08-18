# Generated Code Map

> Regenerate with `python tools/generate_code_map.py`. Do not hand-edit this file.

## Python modules

| Module | Lines | Purpose | Local dependencies |
|---|---:|---|---|
| `agents/__init__.py` | 89 | Backward-compatible facade for the role-specific agent package. | `agents.character`, `agents.common`, `agents.director`, `agents.loops`, `agents.mapping`, `agents.narration`, `agents.perception`, `agents.runtime`, `agents.storage`, `story.scene` |
| `agents/background.py` | 964 |  | `agents.common`, `core.db`, `llm.prompts`, `llm.schemas`, `persist.commit`, `story.character_schema`, `story.scene`, `world.background_claims`, `world.spatial` |
| `agents/character.py` | 3408 | Private character decision agent. | `agents.common`, `core.db`, `core.frames`, `llm.prompts`, `llm.schemas`, `mind`, `mind.affect`, `mind.memory`, `mind.psychology_runtime`, `mind.theory_of_mind`, `story.character_schema`, `story.scene`, `world.gaps`, `world.place_purpose`, `world.spatial`, `world.survival` |
| `agents/common.py` | 6186 | Shared normalization, lore, delivery, and perception helpers. | `core.db`, `llm.llm_quality`, `llm.prompts`, `llm.providers`, `llm.schemas`, `mind.memory`, `mind.theory_of_mind`, `story`, `story.character_schema`, `story.scene`, `world`, `world.spatial` |
| `agents/composer.py` | 1725 |  | `agents.common`, `story.scene`, `world.spatial` |
| `agents/director.py` | 3652 | Scene establishment, player interpretation, and objective resolution. | `agents.common`, `agents.director_contact`, `agents.director_evidence`, `agents.director_fanout`, `agents.director_floors`, `agents.director_lingua`, `agents.director_movement`, `agents.director_reconcile`, `agents.director_scopes`, `agents.director_views`, `core.db`, `llm`, `llm.prompts`, `llm.providers`, `llm.schemas`, `mind.memory`, `story`, `story.character_schema`, `story.scene`, `world.paradox`, `world.spatial`, `world.survival` |
| `agents/director_contact.py` | 421 |  | `story.character_schema`, `world.spatial` |
| `agents/director_evidence.py` | 892 |  | `agents.common`, `agents.director_lingua`, `llm`, `world.spatial` |
| `agents/director_fanout.py` | 501 |  | `agents.common`, `agents.director_evidence`, `agents.director_scopes`, `core.db`, `story.character_schema`, `world.survival` |
| `agents/director_floors.py` | 678 |  | `agents.director_lingua`, `story.character_schema`, `story.scene` |
| `agents/director_lingua.py` | 22 |  | — |
| `agents/director_movement.py` | 938 |  | `agents.director_lingua`, `story.character_schema`, `world.spatial` |
| `agents/director_reconcile.py` | 424 |  | `agents.common`, `agents.director_evidence`, `agents.director_scopes`, `core.db`, `story`, `world.spatial` |
| `agents/director_scopes.py` | 601 |  | `agents.director_views`, `core.db`, `world.survival` |
| `agents/director_views.py` | 453 |  | `agents.common`, `story.character_schema`, `story.scene` |
| `agents/loops.py` | 1050 | Reaction loops, interaction rounds, and deterministic micro-perception. | `agents.character`, `agents.common`, `core.db`, `story.character_schema`, `story.scene`, `world.spatial` |
| `agents/mapping.py` | 297 | Lore routing, cached recall, and retrieval staging. | `agents.common`, `core.db`, `llm.prompts`, `mind.memory`, `story.character_schema`, `story.scene` |
| `agents/narration.py` | 1210 | Player-facing narration agent. | `agents.common`, `core.db`, `llm.prompts`, `llm.schemas`, `story.character_schema`, `story.scene`, `world.spatial`, `world.weather` |
| `agents/perception.py` | 4383 | Opening, action-onset, and outcome observer views. | `agents`, `agents.common`, `core.db`, `mind`, `story.character_schema`, `story.scene`, `world.spatial` |
| `agents/runtime.py` | 1116 | Pipeline plans, dispatch, streaming, cancellation, resume, and reruns. | `agents.background`, `agents.character`, `agents.common`, `agents.director`, `agents.loops`, `agents.mapping`, `agents.narration`, `agents.perception`, `agents.storage`, `core.db`, `core.pipeline_context`, `llm.providers`, `persist.checkpoints`, `persist.commit`, `story.character_schema`, `story.scene` |
| `agents/storage.py` | 123 | Step and active-variant persistence helpers. | `core.db` |
| `core/__init__.py` | 6 |  | — |
| `core/db.py` | 1685 |  | — |
| `core/frames.py` | 220 |  | `core.db` |
| `core/jobs.py` | 209 |  | `core.logging_utils` |
| `core/logging_utils.py` | 118 |  | — |
| `core/outofband.py` | 276 |  | `core.logging_utils` |
| `core/pipeline_context.py` | 312 |  | `core.db` |
| `core/updates.py` | 394 |  | — |
| `dressing/__init__.py` | 6 |  | — |
| `dressing/ambience.py` | 2090 |  | `core`, `core.db`, `dressing.backdrops`, `world.weather` |
| `dressing/backdrops.py` | 1262 |  | `core`, `core.db`, `core.logging_utils`, `world.spatial`, `world.weather` |
| `llm/__init__.py` | 6 |  | — |
| `llm/llm_quality.py` | 655 |  | `core.pipeline_context`, `llm.prompts`, `llm.providers`, `llm.schemas` |
| `llm/prompt_cache.py` | 79 |  | `llm.providers` |
| `llm/prompts.py` | 408 |  | `core.db` |
| `llm/providers.py` | 3158 |  | `core.db`, `core.logging_utils` |
| `llm/schemas.py` | 5253 |  | — |
| `mind/__init__.py` | 6 |  | — |
| `mind/affect.py` | 2186 |  | `mind.theory_of_mind` |
| `mind/canon_provenance.py` | 360 |  | — |
| `mind/memory.py` | 5496 |  | `core`, `core.db`, `core.logging_utils`, `llm.prompts`, `llm.providers`, `mind.theory_of_mind` |
| `mind/psychology_runtime.py` | 502 |  | — |
| `mind/theory_of_mind.py` | 703 |  | — |
| `persist/__init__.py` | 6 |  | — |
| `persist/chat_archive.py` | 1115 |  | `core.db`, `llm.schemas`, `mind.memory`, `persist.checkpoints`, `story.character_schema` |
| `persist/checkpoints.py` | 1149 |  | `core.db`, `mind.memory` |
| `persist/commit.py` | 575 |  | `core.db`, `core.frames`, `llm.prompts`, `llm.providers`, `mind`, `mind.memory`, `mind.theory_of_mind`, `persist.commit_attire`, `persist.commit_background`, `persist.commit_common`, `persist.commit_destruction`, `persist.commit_entities`, `persist.commit_ledgers`, `persist.commit_mapping`, `persist.commit_mechanics`, `persist.commit_memory`, `persist.commit_memory_write`, `persist.commit_place_graph`, `persist.commit_room_registry`, `persist.commit_scene_state`, `story`, `story.character_schema`, `story.scene`, `world.comfort`, `world.mechanics`, `world.paradox`, `world.spatial`, `world.spatial_frames`, `world.survival`, `world.weather` |
| `persist/commit_attire.py` | 862 |  | `persist.commit_common`, `story` |
| `persist/commit_background.py` | 1489 |  | `core.db`, `mind.memory`, `persist.commit_common`, `story.character_schema`, `story.scene`, `world.spatial` |
| `persist/commit_common.py` | 384 |  | `core.db`, `story.character_schema`, `world.mechanics`, `world.spatial` |
| `persist/commit_destruction.py` | 413 |  | `core.db`, `mind.memory`, `persist.commit_common`, `world.mechanics`, `world.spatial` |
| `persist/commit_entities.py` | 499 |  | `core.db`, `persist.commit_common`, `story.character_schema`, `story.scene`, `world.spatial` |
| `persist/commit_ledgers.py` | 302 |  | `core.db`, `persist.commit_common` |
| `persist/commit_mapping.py` | 490 |  | `core.db`, `core.frames`, `llm.prompts`, `llm.providers`, `mind.memory`, `persist.commit_common`, `story.character_schema`, `world.spatial` |
| `persist/commit_mechanics.py` | 348 |  | `core.db`, `persist.commit_common`, `persist.commit_scene_state`, `story.character_schema`, `story.scene`, `world.mechanics` |
| `persist/commit_memory.py` | 1486 |  | `core.db`, `mind`, `mind.memory`, `mind.theory_of_mind`, `persist.commit_background`, `persist.commit_common`, `persist.commit_place_graph`, `story.character_schema`, `world.comfort`, `world.survival` |
| `persist/commit_memory_write.py` | 230 |  | `core.db`, `mind.memory`, `persist.commit_memory`, `story.character_schema`, `story.scene` |
| `persist/commit_place_graph.py` | 274 |  | `world.spatial` |
| `persist/commit_room_registry.py` | 444 |  | `core.db`, `persist.commit_common`, `story.character_schema`, `world.spatial` |
| `persist/commit_scene_state.py` | 709 |  | `core.db`, `mind.memory`, `persist.commit_attire`, `persist.commit_common`, `persist.commit_destruction`, `persist.commit_room_registry`, `story.character_schema`, `world.spatial`, `world.spatial_frames`, `world.weather` |
| `persist/pipeline_trace.py` | 413 |  | `core.db` |
| `story/__init__.py` | 6 |  | — |
| `story/artifacts.py` | 565 |  | `llm.prompts` |
| `story/attire.py` | 2619 |  | — |
| `story/authored_events.py` | 124 |  | `core.db` |
| `story/carriers.py` | 696 |  | `core.db`, `story.character_schema`, `story.scene`, `world`, `world.living_world`, `world.spatial` |
| `story/character_schema.py` | 1634 |  | `llm.schemas`, `story` |
| `story/couriers.py` | 1090 |  | `story.carriers`, `world` |
| `story/dialogue_colors.py` | 248 |  | — |
| `story/greetings.py` | 413 |  | `agents.runtime`, `agents.storage`, `core`, `llm.llm_quality`, `llm.prompts`, `mind.memory`, `story.character_schema` |
| `story/importers.py` | 2618 |  | `core.db`, `core.logging_utils`, `llm.prompts`, `llm.providers`, `mind.memory`, `story.character_schema` |
| `story/lore_structure.py` | 242 |  | — |
| `story/scene.py` | 1944 |  | `core.db`, `story`, `story.character_schema`, `world.spatial` |
| `web/__init__.py` | 6 |  | — |
| `web/app.py` | 5772 |  | `agents`, `core`, `core.db`, `core.frames`, `core.pipeline_context`, `dressing.ambience`, `dressing.backdrops`, `llm`, `llm.prompts`, `llm.providers`, `mind.memory`, `persist.chat_archive`, `persist.checkpoints`, `persist.commit`, `story`, `story.character_schema`, `story.dialogue_colors`, `story.importers`, `story.scene`, `web`, `web.auth_routes`, `world`, `world.survival` |
| `web/auth_routes.py` | 176 |  | `web` |
| `web/guest_access.py` | 355 |  | `core.db` |
| `web/story_view.py` | 670 |  | `core.db` |
| `world/__init__.py` | 6 |  | — |
| `world/background_claims.py` | 466 |  | `core.db` |
| `world/comfort.py` | 306 |  | `world.spatial` |
| `world/crowds.py` | 608 |  | — |
| `world/degradation.py` | 171 |  | — |
| `world/gaps.py` | 542 |  | `core.db`, `core.logging_utils`, `llm.prompts`, `llm.providers`, `mind.canon_provenance`, `world.spatial`, `world.subjects` |
| `world/living_world.py` | 608 |  | `core.logging_utils`, `world.mechanics` |
| `world/mechanics.py` | 310 |  | `world.spatial`, `world.spatial_frames` |
| `world/offscreen.py` | 2125 |  | `core.logging_utils`, `llm.prompts` |
| `world/paradox.py` | 489 |  | `core.db`, `core.frames`, `story.character_schema` |
| `world/place_purpose.py` | 532 |  | `mind.theory_of_mind`, `world.comfort`, `world.spatial`, `world.survival` |
| `world/routines.py` | 200 |  | — |
| `world/spatial.py` | 166 |  | `llm.schemas`, `world.spatial_barriers`, `world.spatial_contact_migration`, `world.spatial_contacts`, `world.spatial_containment`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_light`, `world.spatial_merge`, `world.spatial_orientation`, `world.spatial_prose`, `world.spatial_routing`, `world.spatial_senses`, `world.spatial_substance`, `world.spatial_transit` |
| `world/spatial_barriers.py` | 411 |  | — |
| `world/spatial_contact_migration.py` | 331 |  | `world.spatial_contacts`, `world.spatial_identity` |
| `world/spatial_contacts.py` | 1167 |  | `world.spatial_containment`, `world.spatial_identity` |
| `world/spatial_containment.py` | 636 |  | `world.spatial_identity`, `world.spatial_transit` |
| `world/spatial_frames.py` | 1069 |  | `core.db`, `core.frames`, `story.character_schema`, `story.scene`, `world.paradox`, `world.spatial` |
| `world/spatial_geometry.py` | 951 |  | `world.spatial_barriers`, `world.spatial_contacts`, `world.spatial_containment`, `world.spatial_identity`, `world.spatial_orientation` |
| `world/spatial_identity.py` | 345 |  | — |
| `world/spatial_light.py` | 209 |  | `world.spatial_barriers`, `world.spatial_geometry`, `world.spatial_identity` |
| `world/spatial_merge.py` | 1037 |  | `llm.schemas`, `world.spatial_barriers`, `world.spatial_contact_migration`, `world.spatial_contacts`, `world.spatial_containment`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_orientation`, `world.spatial_senses`, `world.spatial_substance`, `world.spatial_transit` |
| `world/spatial_orientation.py` | 246 |  | — |
| `world/spatial_prose.py` | 336 |  | `world.spatial_contacts`, `world.spatial_containment`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_light` |
| `world/spatial_routing.py` | 923 |  | `world.spatial_barriers`, `world.spatial_containment`, `world.spatial_light`, `world.spatial_orientation` |
| `world/spatial_senses.py` | 1264 |  | `world.spatial_barriers`, `world.spatial_contacts`, `world.spatial_containment`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_light`, `world.spatial_orientation`, `world.spatial_routing` |
| `world/spatial_substance.py` | 602 |  | `world.spatial_contacts`, `world.spatial_identity` |
| `world/spatial_transit.py` | 414 |  | `world.spatial_barriers`, `world.spatial_identity` |
| `world/subjects.py` | 449 |  | `core.db`, `mind.canon_provenance`, `world.spatial` |
| `world/survival.py` | 320 |  | `core.db` |
| `world/weather.py` | 808 |  | `world.spatial` |

## Largest top-level functions

### `agents/background.py`

| Function | Start | Size |
|---|---:|---:|
| `scene_life()` | 520 | 121 lines |
| `_beat_for_presence()` | 111 | 80 lines |
| `background_react()` | 215 | 78 lines |
| `_mint_blurbs()` | 710 | 75 lines |
| `_react_one()` | 903 | 62 lines |
| `managed_presences()` | 393 | 59 lines |
| `_place_block()` | 299 | 47 lines |
| `_present_others()` | 856 | 45 lines |

### `agents/character.py`

| Function | Start | Size |
|---|---:|---:|
| `character_step()` | 2449 | 960 lines |
| `_annotate_known_exits()` | 1813 | 445 lines |
| `_ground_observation_citations()` | 881 | 263 lines |
| `_unanswered_question_note()` | 285 | 117 lines |
| `_destination_from_goals()` | 1379 | 109 lines |
| `sprint_offers()` | 2293 | 97 lines |
| `_recent_self_moves()` | 155 | 90 lines |
| `_verdict()` | 1223 | 72 lines |

### `agents/common.py`

| Function | Start | Size |
|---|---:|---:|
| `norm_sequence()` | 1832 | 204 lines |
| `_scrub_invented_dialogue()` | 4868 | 145 lines |
| `_check_narrator_fidelity()` | 5825 | 125 lines |
| `_extract_authority_claims()` | 1340 | 122 lines |
| `observer_body_regions()` | 664 | 117 lines |
| `_strip_player_echo()` | 4671 | 101 lines |
| `_perceptible_entities()` | 918 | 98 lines |
| `_check_presence_knowledge_channel()` | 3385 | 95 lines |

### `agents/composer.py`

| Function | Start | Size |
|---|---:|---:|
| `_render_view_english()` | 1253 | 91 lines |
| `_render_episode_english()` | 1472 | 80 lines |
| `presence_percepts()` | 498 | 75 lines |
| `pose_percepts()` | 617 | 75 lines |
| `observations_from_render()` | 1651 | 75 lines |
| `speech_percept()` | 811 | 59 lines |
| `_episode_sentence()` | 1412 | 58 lines |
| `_render_standing()` | 1161 | 54 lines |

### `agents/director.py`

| Function | Start | Size |
|---|---:|---:|
| `director_resolve()` | 2145 | 1474 lines |
| `director_interpret()` | 404 | 534 lines |
| `_reconcile_resolution()` | 1294 | 445 lines |
| `_run_specialists()` | 1921 | 211 lines |
| `director_establish()` | 277 | 125 lines |
| `_reconcile_interpretation()` | 940 | 119 lines |
| `_specialist_repairs()` | 1121 | 119 lines |
| `_prose_gate_facts()` | 1803 | 92 lines |

### `agents/director_contact.py`

| Function | Start | Size |
|---|---:|---:|
| `_validated_player_contact_assertions()` | 35 | 116 lines |
| `_merge_player_contact_assertions()` | 153 | 85 lines |
| `_character_material_effects()` | 299 | 52 lines |
| `_validated_character_contact_endings()` | 240 | 51 lines |
| `_merge_character_material_effects()` | 353 | 35 lines |
| `_merge_character_contact_endings()` | 390 | 32 lines |
| `_canonical_scene_subject()` | 27 | 6 lines |

### `agents/director_evidence.py`

| Function | Start | Size |
|---|---:|---:|
| `_evidence_present()` | 552 | 232 lines |
| `_merge_repair_into_diff()` | 341 | 58 lines |
| `_fold_derived_manifest_events()` | 837 | 56 lines |
| `_interpret_coverage_corpus()` | 90 | 51 lines |
| `_omission_subject_encoded()` | 489 | 51 lines |
| `_strip_blank_diff_placeholders()` | 255 | 42 lines |
| `_manifest_items()` | 791 | 37 lines |
| `_normalize_diff_shape()` | 195 | 36 lines |

### `agents/director_fanout.py`

| Function | Start | Size |
|---|---:|---:|
| `_specialist_payload()` | 135 | 133 lines |
| `_orchestration_scope_backstop()` | 371 | 131 lines |
| `_interpret_beat_view()` | 83 | 35 lines |
| `_resolve_beat_view()` | 51 | 30 lines |
| `_resolved_event_verdicts()` | 302 | 30 lines |
| `fanout_is_parallel()` | 29 | 20 lines |
| `_index_addressed_events()` | 334 | 18 lines |
| `_stage_container()` | 270 | 14 lines |

### `agents/director_floors.py`

| Function | Start | Size |
|---|---:|---:|
| `_awareness_exits()` | 417 | 98 lines |
| `_narrated_destruction_subjects()` | 584 | 79 lines |
| `_clause_attributed_subjects()` | 245 | 50 lines |
| `_unsupported_player_awareness()` | 146 | 43 lines |
| `_untracked_restraint_subjects()` | 31 | 32 lines |
| `_awareness_view()` | 356 | 31 lines |
| `_sleep_elapsed()` | 325 | 29 lines |
| `_untracked_unconsciousness_subjects()` | 517 | 23 lines |

### `agents/director_lingua.py`

| Function | Start | Size |
|---|---:|---:|
| `_ling()` | 15 | 2 lines |

### `agents/director_movement.py`

| Function | Start | Size |
|---|---:|---:|
| `_reconcile_near_group_positions()` | 98 | 276 lines |
| `_travel_continues()` | 733 | 124 lines |
| `_apply_following_movement()` | 465 | 88 lines |
| `_guard_approach_is_not_arrival()` | 859 | 80 lines |
| `_unreachable_position_writes()` | 554 | 68 lines |
| `_travel_in_flight_view()` | 673 | 58 lines |
| `_egocentric_exits()` | 29 | 48 lines |
| `_resolve_movement_mover()` | 624 | 37 lines |

### `agents/director_reconcile.py`

| Function | Start | Size |
|---|---:|---:|
| `_verify_already_true()` | 197 | 126 lines |
| `_player_claim_findings()` | 51 | 80 lines |
| `_stamp_dialogue_articulation()` | 136 | 52 lines |
| `_acquit_addressed_events()` | 325 | 52 lines |
| `_route_repair_omissions()` | 385 | 40 lines |
| `_deep_audit_mode()` | 39 | 11 lines |
| `_public_omission()` | 132 | 2 lines |

### `agents/director_scopes.py`

| Function | Start | Size |
|---|---:|---:|
| `_gate_facts()` | 506 | 70 lines |
| `register_specialist()` | 364 | 49 lines |
| `_rebuild_channel_owners()` | 334 | 24 lines |
| `_dispatch_specialists()` | 578 | 24 lines |
| `_extension_specialist_call()` | 427 | 17 lines |
| `_schema_list_channels()` | 200 | 14 lines |
| `_shipped_transit_state()` | 446 | 12 lines |
| `unregister_specialists()` | 415 | 10 lines |

### `agents/director_views.py`

| Function | Start | Size |
|---|---:|---:|
| `_report_observer_epithets()` | 230 | 69 lines |
| `_route_authorial_npc_beat()` | 54 | 48 lines |
| `_carried_reports_view()` | 408 | 46 lines |
| `_crowds_view()` | 301 | 40 lines |
| `_couriers_view()` | 343 | 32 lines |
| `_audit_fact_adjudications()` | 185 | 31 lines |
| `_round_conduct()` | 154 | 29 lines |
| `_artifacts_view()` | 377 | 29 lines |

### `agents/loops.py`

| Function | Start | Size |
|---|---:|---:|
| `interaction_loop()` | 412 | 568 lines |
| `deterministic_micro_perception()` | 48 | 133 lines |
| `reaction_loop()` | 981 | 70 lines |
| `_isolated_wave()` | 369 | 41 lines |
| `_defer_to_unrun_reactor()` | 226 | 37 lines |
| `_standing_pressure()` | 265 | 37 lines |
| `_perceptually_isolated()` | 332 | 35 lines |
| `_defer_to_focus()` | 196 | 28 lines |

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
| `narrator()` | 818 | 241 lines |
| `_ordered_beat_events()` | 422 | 154 lines |
| `narrator_extra()` | 1060 | 151 lines |
| `_sensory_channels_manifest()` | 296 | 124 lines |
| `_visible_portal_states()` | 665 | 100 lines |
| `_resolve_narration_person()` | 94 | 66 lines |
| `_position_delta_payload()` | 609 | 54 lines |
| `_standing_substance_clauses()` | 253 | 35 lines |

### `agents/perception.py`

| Function | Start | Size |
|---|---:|---:|
| `_composer_outcome()` | 4058 | 326 lines |
| `perception_outcome()` | 2890 | 297 lines |
| `perception_act()` | 2451 | 251 lines |
| `_observer_scene_payload()` | 808 | 212 lines |
| `_composer_act()` | 3931 | 125 lines |
| `_previous_open_group_continuity()` | 163 | 117 lines |
| `_strip_self_narration()` | 1639 | 107 lines |
| `perception_establish()` | 2343 | 107 lines |

### `agents/runtime.py`

| Function | Start | Size |
|---|---:|---:|
| `_run_pipeline()` | 755 | 306 lines |
| `build_plan()` | 550 | 85 lines |
| `_stream_one()` | 325 | 68 lines |
| `_load_extra_players()` | 46 | 59 lines |
| `run_pipeline()` | 1062 | 55 lines |
| `resume_key_for_turn()` | 495 | 54 lines |
| `_stream_parallel()` | 394 | 45 lines |
| `_rehydrate_loop_results()` | 707 | 41 lines |

### `agents/storage.py`

| Function | Start | Size |
|---|---:|---:|
| `save_step()` | 21 | 36 lines |
| `active_content()` | 58 | 17 lines |
| `mark_steps_stale()` | 93 | 12 lines |
| `delete_step()` | 114 | 10 lines |
| `_set_steps_stale()` | 85 | 7 lines |
| `clear_steps_stale()` | 106 | 7 lines |
| `variant_count()` | 76 | 4 lines |
| `step_is_stale()` | 81 | 3 lines |

### `core/db.py`

| Function | Start | Size |
|---|---:|---:|
| `init()` | 1592 | 50 lines |
| `conn()` | 1439 | 38 lines |
| `transaction()` | 1479 | 36 lines |
| `_backfill_resource_uids()` | 1574 | 17 lines |
| `qi()` | 1537 | 16 lines |
| `data_version()` | 1516 | 14 lines |
| `parse_scoped_world_key()` | 81 | 13 lines |
| `_execute_retry()` | 1408 | 13 lines |

### `core/frames.py`

| Function | Start | Size |
|---|---:|---:|
| `is_memory_visible()` | 126 | 82 lines |
| `get_frame()` | 67 | 23 lines |
| `create_frame()` | 98 | 19 lines |
| `is_recognized_in_frame()` | 210 | 11 lines |
| `frame_ordinal()` | 119 | 5 lines |
| `list_frames()` | 92 | 4 lines |

### `core/jobs.py`

| Function | Start | Size |
|---|---:|---:|
| `submit()` | 68 | 19 lines |
| `_run()` | 110 | 19 lines |
| `cancel()` | 145 | 13 lines |
| `_finish()` | 131 | 12 lines |
| `status()` | 169 | 10 lines |
| `is_stale()` | 192 | 10 lines |
| `_clear_turn_scoped_context()` | 100 | 8 lines |
| `cancel_chat()` | 160 | 7 lines |

### `core/logging_utils.py`

| Function | Start | Size |
|---|---:|---:|
| `log_llm_call()` | 91 | 28 lines |
| `measure_step()` | 72 | 18 lines |

### `core/outofband.py`

| Function | Start | Size |
|---|---:|---:|
| `stopped()` | 121 | 8 lines |

### `core/pipeline_context.py`

| Function | Start | Size |
|---|---:|---:|
| `note_step_warning()` | 34 | 11 lines |

### `core/updates.py`

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

### `dressing/ambience.py`

| Function | Start | Size |
|---|---:|---:|
| `resolve_ambience()` | 1679 | 221 lines |
| `_rank_candidates()` | 1091 | 105 lines |
| `refine_layers()` | 756 | 89 lines |
| `cached_ambience()` | 479 | 62 lines |
| `search_freesound()` | 1376 | 61 lines |
| `search_local()` | 896 | 54 lines |
| `_query_ladder()` | 1205 | 51 lines |
| `acoustic_fingerprint()` | 260 | 45 lines |

### `dressing/backdrops.py`

| Function | Start | Size |
|---|---:|---:|
| `generate_backdrop()` | 1068 | 115 lines |
| `room_projection()` | 526 | 73 lines |
| `visual_signature()` | 135 | 48 lines |
| `scene_after_turn()` | 690 | 35 lines |
| `build_backdrop_request()` | 727 | 35 lines |
| `branch_lineage()` | 216 | 34 lines |
| `compose_prompt()` | 833 | 34 lines |
| `compose_revision()` | 895 | 33 lines |

### `llm/llm_quality.py`

| Function | Start | Size |
|---|---:|---:|
| `complete_validated_json()` | 277 | 379 lines |
| `_targeted_field_patch()` | 188 | 57 lines |
| `output_ran_out_of_room()` | 77 | 47 lines |
| `_extract_balanced_object()` | 23 | 34 lines |
| `_step_json_schema()` | 250 | 25 lines |
| `strict_json_parse()` | 126 | 19 lines |
| `_strip_fences()` | 59 | 16 lines |
| `_dig()` | 161 | 12 lines |

### `llm/prompt_cache.py`

| Function | Start | Size |
|---|---:|---:|
| `add_cache_breakpoint()` | 15 | 37 lines |
| `estimate_cacheable_tokens()` | 66 | 14 lines |
| `supports_prompt_caching()` | 7 | 7 lines |

### `llm/prompts.py`

| Function | Start | Size |
|---|---:|---:|
| `preset_import_document()` | 208 | 45 lines |
| `normalize_preset()` | 89 | 26 lines |
| `_preset_override()` | 155 | 22 lines |
| `character_prompt()` | 351 | 21 lines |
| `specialist_prompt()` | 266 | 17 lines |
| `prose_author_prompt()` | 290 | 17 lines |
| `get_prompt_body()` | 386 | 17 lines |
| `preset_export_document()` | 191 | 15 lines |

### `llm/providers.py`

| Function | Start | Size |
|---|---:|---:|
| `_chat_complete_once()` | 2060 | 274 lines |
| `async _chat_complete_async_once()` | 2455 | 103 lines |
| `chat_complete()` | 1821 | 91 lines |
| `async chat_complete_async()` | 2364 | 90 lines |
| `_sse_openai()` | 1693 | 78 lines |
| `async _sse_openai_async()` | 2559 | 63 lines |
| `_embed_request()` | 2876 | 58 lines |
| `resolve_role_candidates()` | 1415 | 54 lines |

### `llm/schemas.py`

| Function | Start | Size |
|---|---:|---:|
| `preprocess_llm_output()` | 4094 | 343 lines |
| `_lenient_coerce()` | 660 | 149 lines |
| `validate_llm_output_strict()` | 5124 | 130 lines |
| `semantic_output_errors()` | 4941 | 103 lines |
| `canonicalize_prose_markup()` | 3899 | 102 lines |
| `_uncross_concealed_speech()` | 4023 | 69 lines |
| `_coerce_list_valued_map()` | 93 | 57 lines |
| `_coerce_evidence_refs()` | 2504 | 51 lines |

### `mind/affect.py`

| Function | Start | Size |
|---|---:|---:|
| `resolve_affect()` | 806 | 184 lines |
| `apply_project_ops()` | 1399 | 137 lines |
| `appraise()` | 513 | 136 lines |
| `apply_intent_ops()` | 1220 | 133 lines |
| `normalize_wants()` | 996 | 87 lines |
| `validate_drive_shift()` | 1969 | 79 lines |
| `update_drive_strain()` | 1850 | 77 lines |
| `_advance_intent()` | 1113 | 74 lines |

### `mind/canon_provenance.py`

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

### `mind/memory.py`

| Function | Start | Size |
|---|---:|---:|
| `build_character_memory_context()` | 2900 | 274 lines |
| `search_memories()` | 1911 | 228 lines |
| `rebuild_embeddings()` | 4868 | 213 lines |
| `embedding_bank_status()` | 4718 | 125 lines |
| `rebuild_checkpoint_embeddings()` | 5120 | 124 lines |
| `contrast_memory()` | 2174 | 117 lines |
| `_with_reading()` | 2670 | 101 lines |
| `_origin_on_drift()` | 2801 | 97 lines |

### `mind/psychology_runtime.py`

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

### `mind/theory_of_mind.py`

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

### `persist/chat_archive.py`

| Function | Start | Size |
|---|---:|---:|
| `_model_validate()` | 54 | 4 lines |
| `_model_dump()` | 60 | 4 lines |

### `persist/checkpoints.py`

| Function | Start | Size |
|---|---:|---:|
| `snapshot_state()` | 15 | 169 lines |
| `_restore_checkpoint_body()` | 563 | 141 lines |
| `compact_checkpoints()` | 813 | 118 lines |
| `insert_world_tables()` | 377 | 105 lines |
| `_restore_books()` | 185 | 104 lines |
| `ensure_checkpoint()` | 997 | 53 lines |
| `propagate_memory_summaries_to_checkpoints()` | 1052 | 53 lines |
| `_verify_no_loss()` | 761 | 50 lines |

### `persist/commit.py`

| Function | Start | Size |
|---|---:|---:|
| `_commit_all_locked()` | 349 | 226 lines |
| `commit_crowds()` | 229 | 82 lines |
| `commit_narration_person()` | 148 | 29 lines |
| `commit_authored_events()` | 180 | 25 lines |
| `_prepare_turn_commit()` | 326 | 12 lines |
| `commit_offscreen_epoch()` | 207 | 11 lines |
| `commit_all()` | 313 | 11 lines |
| `commit_offscreen_plans()` | 220 | 7 lines |

### `persist/commit_attire.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_attire_diff()` | 569 | 294 lines |
| `interpret_attire_notes()` | 155 | 115 lines |
| `_fold_duplicate_shed_garments()` | 272 | 85 lines |
| `_heal_attire_identity_keys()` | 32 | 72 lines |
| `_fold_worn_garment_entities()` | 359 | 69 lines |
| `_mint_shed_garments()` | 501 | 66 lines |
| `_adopt_shed_record()` | 446 | 34 lines |
| `_beat_voices()` | 106 | 25 lines |

### `persist/commit_background.py`

| Function | Start | Size |
|---|---:|---:|
| `track_background_presences()` | 534 | 341 lines |
| `pick_background_reactors()` | 1018 | 178 lines |
| `promote_background_character()` | 1269 | 97 lines |
| `auto_promote_background_characters()` | 1405 | 85 lines |
| `_presence_speech_verdict()` | 188 | 67 lines |
| `_at_post_within_earshot()` | 954 | 52 lines |
| `_is_inert_presence_candidate()` | 457 | 50 lines |
| `_character_address_of()` | 364 | 40 lines |

### `persist/commit_common.py`

| Function | Start | Size |
|---|---:|---:|
| `_names_heard_in()` | 168 | 53 lines |
| `_address_forms()` | 119 | 47 lines |
| `_entity_alias_map()` | 313 | 44 lines |
| `_monotonic_elapsed()` | 57 | 38 lines |
| `_registered_name_roster()` | 252 | 28 lines |
| `_known_name_roster()` | 223 | 27 lines |
| `_resolve_roster_name()` | 281 | 20 lines |
| `_form_in()` | 101 | 16 lines |

### `persist/commit_destruction.py`

| Function | Start | Size |
|---|---:|---:|
| `_prepare_destruction()` | 192 | 158 lines |
| `_destruction_cascade()` | 124 | 66 lines |
| `_apply_destruction()` | 380 | 34 lines |
| `_chat_book_graph()` | 51 | 30 lines |
| `_finalize_destruction_news()` | 352 | 26 lines |
| `_audience_book_id()` | 102 | 20 lines |
| `_book_distances()` | 83 | 17 lines |
| `_destruction_book()` | 33 | 16 lines |

### `persist/commit_entities.py`

| Function | Start | Size |
|---|---:|---:|
| `commit_world_entities()` | 213 | 287 lines |
| `_supersede_disguises()` | 94 | 74 lines |
| `_inherit_known_to()` | 170 | 41 lines |
| `_subjects_that_moved()` | 33 | 36 lines |
| `_subjects_targeted_by_an_action()` | 71 | 21 lines |
| `_is_gated_awareness()` | 17 | 14 lines |

### `persist/commit_ledgers.py`

| Function | Start | Size |
|---|---:|---:|
| `commit_world_pressure()` | 188 | 115 lines |
| `commit_obligations()` | 67 | 65 lines |
| `world_pressure_view()` | 144 | 22 lines |
| `_find_obligation()` | 45 | 21 lines |
| `pending_obligation_view()` | 24 | 20 lines |
| `_find_pressure()` | 168 | 18 lines |

### `persist/commit_mapping.py`

| Function | Start | Size |
|---|---:|---:|
| `commit_mapping()` | 292 | 142 lines |
| `prepare_mapping_commit()` | 161 | 129 lines |
| `_apply_mapping_book_ops()` | 57 | 103 lines |
| `normalize_offscreen_events()` | 21 | 35 lines |
| `_generate_fallback_ops()` | 460 | 31 lines |
| `_fact_is_covered()` | 441 | 18 lines |
| `_lore_for()` | 437 | 2 lines |

### `persist/commit_mechanics.py`

| Function | Start | Size |
|---|---:|---:|
| `commit_transit_sweep()` | 21 | 169 lines |
| `commit_information_carriers()` | 240 | 85 lines |
| `commit_world_event_spine()` | 192 | 46 lines |
| `commit_cast_changes()` | 328 | 21 lines |

### `persist/commit_memory.py`

| Function | Start | Size |
|---|---:|---:|
| `prepare_memory_commit()` | 223 | 1264 lines |
| `_cited_memory_ids()` | 64 | 76 lines |
| `_own_sequence_memory()` | 186 | 36 lines |
| `_marked_for_memory()` | 142 | 24 lines |
| `_durable_dialogue_category()` | 40 | 23 lines |
| `_salience_of()` | 176 | 8 lines |
| `_is_player()` | 172 | 3 lines |
| `_quote_body()` | 168 | 2 lines |

### `persist/commit_memory_write.py`

| Function | Start | Size |
|---|---:|---:|
| `commit_memories()` | 151 | 80 lines |
| `schedule_memory_consolidation()` | 77 | 72 lines |
| `_consolidate_committed_memories()` | 21 | 51 lines |

### `persist/commit_place_graph.py`

| Function | Start | Size |
|---|---:|---:|
| `update_place_graph()` | 33 | 153 lines |
| `record_spatial_experience()` | 188 | 87 lines |

### `persist/commit_room_registry.py`

| Function | Start | Size |
|---|---:|---:|
| `dedup_minted_rooms()` | 132 | 90 lines |
| `_prepare_room_registry()` | 223 | 76 lines |
| `_refresh_relocated_location()` | 350 | 54 lines |
| `_apply_room_renames()` | 76 | 53 lines |
| `prune_dangling_exits()` | 406 | 39 lines |
| `_apply_room_registry()` | 301 | 27 lines |
| `_registry_alias_index()` | 53 | 22 lines |
| `sync_room_registry_with_scene()` | 329 | 19 lines |

### `persist/commit_scene_state.py`

| Function | Start | Size |
|---|---:|---:|
| `prepare_scene_commit()` | 212 | 452 lines |
| `sync_anchored_books()` | 47 | 66 lines |
| `_guard_occupied_mover_removal()` | 114 | 63 lines |
| `_advance_ground()` | 179 | 31 lines |
| `_record_subject_last_seen()` | 686 | 24 lines |
| `commit_scene()` | 666 | 18 lines |
| `_anchor_current_room()` | 31 | 14 lines |

### `persist/pipeline_trace.py`

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

### `story/artifacts.py`

| Function | Start | Size |
|---|---:|---:|
| `run_artifacts()` | 183 | 202 lines |
| `schedule_artifact_wording()` | 392 | 65 lines |
| `mint_wording()` | 459 | 55 lines |
| `land_artifact_wording()` | 516 | 50 lines |
| `reading_copy()` | 150 | 25 lines |
| `new_artifact()` | 128 | 20 lines |
| `artifact_voice()` | 95 | 11 lines |
| `posted_in_room()` | 116 | 10 lines |

### `story/attire.py`

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

### `story/authored_events.py`

| Function | Start | Size |
|---|---:|---:|
| `resolve_authored_events()` | 90 | 35 lines |
| `mint_authored_events()` | 42 | 28 lines |
| `due_authored_events()` | 72 | 16 lines |
| `_event_id()` | 36 | 4 lines |

### `story/carriers.py`

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

### `story/character_schema.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_character_data()` | 974 | 159 lines |
| `default_character_data()` | 553 | 95 lines |
| `_normalize_psychology()` | 293 | 83 lines |
| `repair_character_shape()` | 915 | 57 lines |
| `_normalize_extra_parts()` | 499 | 52 lines |
| `_as_profile_list()` | 38 | 50 lines |
| `normalize_persona_data()` | 1134 | 50 lines |
| `character_initial_active_state()` | 1428 | 48 lines |

### `story/couriers.py`

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

### `story/dialogue_colors.py`

| Function | Start | Size |
|---|---:|---:|
| `personality_digest()` | 84 | 48 lines |
| `resolve_cast_colors()` | 177 | 46 lines |
| `_spread()` | 225 | 19 lines |
| `normalize_color()` | 69 | 13 lines |
| `auto_dialogue_color()` | 151 | 13 lines |
| `_hue_from()` | 134 | 10 lines |
| `_hue_of()` | 166 | 9 lines |
| `_hex_from_hsl()` | 146 | 3 lines |

### `story/greetings.py`

| Function | Start | Size |
|---|---:|---:|
| `start_story()` | 177 | 153 lines |
| `generate_greeting()` | 332 | 63 lines |
| `extract_greeting()` | 99 | 24 lines |
| `_substitute_player_slot()` | 56 | 22 lines |
| `player_handle_for()` | 80 | 17 lines |
| `_strip_greeting_wrapping()` | 397 | 17 lines |
| `_override_narrator()` | 134 | 13 lines |
| `_greeting_record()` | 125 | 7 lines |

### `story/importers.py`

| Function | Start | Size |
|---|---:|---:|
| `import_lorebook()` | 1296 | 212 lines |
| `_reinterpret_entries()` | 1169 | 126 lines |
| `apply_lorebook_plan()` | 2416 | 124 lines |
| `_lore_gen_entry_batch()` | 2068 | 118 lines |
| `_run_lore_gen_job()` | 2190 | 112 lines |
| `fill_appearance()` | 949 | 109 lines |
| `import_character()` | 444 | 92 lines |
| `generate_lore_entries()` | 2540 | 79 lines |

### `story/lore_structure.py`

| Function | Start | Size |
|---|---:|---:|
| `derive_knowledge()` | 195 | 48 lines |
| `parse_structure()` | 78 | 45 lines |
| `clean_title()` | 46 | 16 lines |
| `classify_title()` | 64 | 12 lines |
| `_matches()` | 160 | 12 lines |
| `_place_name()` | 151 | 7 lines |

### `story/scene.py`

| Function | Start | Size |
|---|---:|---:|
| `active_disguises()` | 379 | 82 lines |
| `normalize_transformed_parts()` | 470 | 60 lines |
| `recent_events_for_observer()` | 1186 | 59 lines |
| `_positive_presented_appearance()` | 667 | 58 lines |
| `active_transformations()` | 532 | 54 lines |
| `director_context()` | 1246 | 53 lines |
| `conceal_disguised_parts()` | 782 | 48 lines |
| `awareness_conditions()` | 907 | 47 lines |

### `web/app.py`

| Function | Start | Size |
|---|---:|---:|
| `turn_branch()` | 4644 | 400 lines |
| `chat_get()` | 3045 | 234 lines |
| `_remap_cp_blob()` | 849 | 194 lines |
| `bootstrap()` | 1163 | 98 lines |
| `_stream()` | 462 | 91 lines |
| `lore_entry_edit()` | 2749 | 70 lines |
| `lore_edit()` | 2600 | 68 lines |
| `_ambience_payload()` | 5554 | 68 lines |

### `web/auth_routes.py`

| Function | Start | Size |
|---|---:|---:|
| `auth_login()` | 109 | 60 lines |
| `auth_setup()` | 70 | 36 lines |
| `_set_host_cookie()` | 48 | 9 lines |
| `auth_status()` | 60 | 7 lines |
| `auth_logout()` | 172 | 5 lines |

### `web/guest_access.py`

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

### `web/story_view.py`

| Function | Start | Size |
|---|---:|---:|
| `_people()` | 515 | 77 lines |
| `player_view()` | 594 | 77 lines |
| `story_view()` | 174 | 51 lines |
| `_public_facts()` | 342 | 46 lines |
| `_person_refs()` | 432 | 36 lines |
| `_delivered()` | 254 | 24 lines |
| `_presence_ref()` | 470 | 24 lines |
| `viewers()` | 230 | 22 lines |

### `world/background_claims.py`

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

### `world/comfort.py`

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

### `world/crowds.py`

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

### `world/degradation.py`

| Function | Start | Size |
|---|---:|---:|
| `degrade()` | 110 | 27 lines |
| `lost_at()` | 153 | 19 lines |
| `_replace_phrases()` | 94 | 14 lines |
| `is_exhausted()` | 139 | 12 lines |
| `_collapse()` | 90 | 2 lines |

### `world/gaps.py`

| Function | Start | Size |
|---|---:|---:|
| `_skeleton()` | 147 | 175 lines |
| `last_seen_update()` | 438 | 70 lines |
| `gap_for()` | 378 | 54 lines |
| `_medium_overlay()` | 328 | 48 lines |
| `interim_for()` | 510 | 33 lines |
| `_record()` | 79 | 22 lines |
| `_derived_resolution()` | 109 | 22 lines |
| `_subject_room()` | 133 | 12 lines |

### `world/living_world.py`

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

### `world/mechanics.py`

| Function | Start | Size |
|---|---:|---:|
| `_fire_due_events()` | 110 | 98 lines |
| `_schedule_new_arrivals()` | 210 | 44 lines |
| `mechanics_sweep()` | 268 | 43 lines |
| `news_latency_seconds()` | 90 | 10 lines |
| `_expire_conditions()` | 256 | 10 lines |
| `stable_event_key()` | 68 | 6 lines |
| `_payload_of()` | 102 | 6 lines |

### `world/offscreen.py`

| Function | Start | Size |
|---|---:|---:|
| `land_agent_tick()` | 1819 | 187 lines |
| `schedule_agent_ticks()` | 2008 | 118 lines |
| `schedule_profile_ticks()` | 1358 | 113 lines |
| `apply_plan_ops()` | 682 | 110 lines |
| `advance_epoch()` | 927 | 98 lines |
| `profile_summary_record()` | 1108 | 86 lines |
| `advance_reactive_plans()` | 840 | 85 lines |
| `agent_adjudication()` | 1724 | 70 lines |

### `world/paradox.py`

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

### `world/place_purpose.py`

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

### `world/routines.py`

| Function | Start | Size |
|---|---:|---:|
| `residue_for()` | 156 | 45 lines |
| `entropy_facts()` | 128 | 26 lines |
| `routine_band()` | 84 | 22 lines |
| `occupancy_fact()` | 108 | 18 lines |
| `_roll()` | 73 | 9 lines |

### `world/spatial_barriers.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_barrier()` | 260 | 67 lines |
| `_barrier_against_its_own_name()` | 379 | 27 lines |
| `normalize_scene_barriers()` | 345 | 21 lines |
| `unresolved_barrier_words()` | 329 | 15 lines |
| `_barrier_exact()` | 249 | 9 lines |

### `world/spatial_contact_migration.py`

| Function | Start | Size |
|---|---:|---:|
| `contacts_from_entity_state()` | 81 | 137 lines |
| `_lift_valued_contact()` | 235 | 56 lines |
| `_drop_contradicted_state()` | 293 | 39 lines |
| `_part_from_key()` | 71 | 8 lines |
| `_manner_from_fragment()` | 63 | 6 lines |

### `world/spatial_contacts.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_contact_ops()` | 685 | 318 lines |
| `_clean_contact()` | 450 | 108 lines |
| `contacts_broken_by_scale_change()` | 560 | 50 lines |
| `normalize_scene_contacts()` | 612 | 45 lines |
| `_contained_inversion()` | 419 | 29 lines |
| `canonical_region()` | 181 | 28 lines |
| `_part_identity()` | 132 | 26 lines |
| `owned_region()` | 236 | 24 lines |

### `world/spatial_containment.py`

| Function | Start | Size |
|---|---:|---:|
| `_body_interior_holder()` | 312 | 75 lines |
| `normalize_scene_containment()` | 469 | 47 lines |
| `derive_contained_positions()` | 518 | 42 lines |
| `size_facts()` | 160 | 40 lines |
| `containment_broken_by_scale_change()` | 562 | 36 lines |
| `normalize_scene_scales()` | 83 | 34 lines |
| `_hiding_holders()` | 389 | 34 lines |
| `size_relation()` | 125 | 33 lines |

### `world/spatial_frames.py`

| Function | Start | Size |
|---|---:|---:|
| `infer_focus()` | 468 | 153 lines |
| `infer_threshold_crossings()` | 370 | 96 lines |
| `perform_split()` | 799 | 94 lines |
| `infer_companion_carry()` | 234 | 92 lines |
| `infer_vehicle_zones()` | 147 | 85 lines |
| `infer_facing()` | 623 | 71 lines |
| `perform_merge()` | 971 | 69 lines |
| `detect_split()` | 753 | 44 lines |

### `world/spatial_geometry.py`

| Function | Start | Size |
|---|---:|---:|
| `derive_scene_stations()` | 848 | 104 lines |
| `egocentric_frame()` | 50 | 80 lines |
| `spatial_digest()` | 132 | 61 lines |
| `effective_station()` | 312 | 55 lines |
| `normalize_scene_poses()` | 712 | 53 lines |
| `effective_anchors()` | 260 | 50 lines |
| `guessed_room_sizes()` | 436 | 50 lines |
| `normalize_scene_stations()` | 654 | 35 lines |

### `world/spatial_identity.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_scene_subjects()` | 253 | 80 lines |
| `canonical_subject_map()` | 176 | 66 lines |
| `_live_subject_spellings()` | 127 | 47 lines |
| `_position_of()` | 75 | 31 lines |
| `same_subject()` | 45 | 28 lines |
| `room_of()` | 10 | 18 lines |
| `_ci_get()` | 30 | 13 lines |
| `_entity_named()` | 108 | 10 lines |

### `world/spatial_light.py`

| Function | Start | Size |
|---|---:|---:|
| `source_light()` | 56 | 51 lines |
| `light_at()` | 120 | 42 lines |
| `effective_light()` | 164 | 29 lines |
| `room_light()` | 41 | 6 lines |
| `_light_radius()` | 113 | 5 lines |
| `normalize_light()` | 35 | 4 lines |
| `light_blocks_sight()` | 195 | 3 lines |
| `_brighter()` | 52 | 2 lines |

### `world/spatial_merge.py`

| Function | Start | Size |
|---|---:|---:|
| `merge_scene_with_diff()` | 690 | 318 lines |
| `apply_following_ops()` | 611 | 77 lines |
| `connect_orphan_new_rooms()` | 525 | 68 lines |
| `_merge_room()` | 128 | 64 lines |
| `_shield_standing_bearings()` | 400 | 61 lines |
| `_shield_standing_passage()` | 463 | 60 lines |
| `_dedup_duplicate_entity_keys()` | 340 | 58 lines |
| `_merge_entity()` | 223 | 55 lines |

### `world/spatial_orientation.py`

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

### `world/spatial_prose.py`

| Function | Start | Size |
|---|---:|---:|
| `contact_sensation()` | 107 | 144 lines |
| `spatial_facts()` | 253 | 84 lines |
| `contact_phrase()` | 22 | 83 lines |

### `world/spatial_routing.py`

| Function | Start | Size |
|---|---:|---:|
| `sprint_reach()` | 536 | 175 lines |
| `visible_adjacent_rooms()` | 781 | 143 lines |
| `corridor_sightlines()` | 388 | 85 lines |
| `spatial_rel()` | 80 | 70 lines |
| `_onward_exits()` | 713 | 66 lines |
| `nearby_rooms()` | 267 | 51 lines |
| `passable_path()` | 486 | 48 lines |
| `passable_route_next_step()` | 178 | 46 lines |

### `world/spatial_senses.py`

| Function | Start | Size |
|---|---:|---:|
| `hear_level()` | 730 | 138 lines |
| `spatial_rel_between()` | 464 | 71 lines |
| `sound_bearing()` | 1030 | 69 lines |
| `scent_level()` | 36 | 55 lines |
| `_clean_comms_channel()` | 156 | 53 lines |
| `_opening_view_cap()` | 551 | 52 lines |
| `visual_level_between()` | 605 | 52 lines |
| `can_perceive_onset()` | 345 | 39 lines |

### `world/spatial_substance.py`

| Function | Start | Size |
|---|---:|---:|
| `_resolved_substance_add()` | 180 | 122 lines |
| `apply_substance_ops()` | 475 | 82 lines |
| `speech_articulation_impediment()` | 40 | 63 lines |
| `_same_pool()` | 346 | 50 lines |
| `_stock_consumed_by()` | 425 | 48 lines |
| `resolve_substance_ops()` | 304 | 40 lines |
| `substance_event_clause()` | 567 | 36 lines |
| `_substance_target_exists()` | 155 | 23 lines |

### `world/spatial_transit.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_transit_dock_edges()` | 177 | 165 lines |
| `ambient_scope()` | 376 | 39 lines |
| `infer_body_enclosures()` | 89 | 27 lines |
| `_is_body_entity()` | 61 | 26 lines |
| `containment_chain()` | 356 | 19 lines |
| `_link_state()` | 147 | 14 lines |
| `_entity_exterior_room()` | 162 | 14 lines |
| `_closed_enclosure_barrier()` | 132 | 13 lines |

### `world/subjects.py`

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

### `world/survival.py`

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

### `world/weather.py`

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
| GET | `/` | `index()` | `web/app.py:381` |
| PUT | `/api/active_preset` | `set_active()` | `web/app.py:1565` |
| PUT | `/api/affect_habituation` | `set_affect_habituation()` | `web/app.py:1860` |
| PUT | `/api/agent_models` | `put_agent_models()` | `web/app.py:1263` |
| PUT | `/api/ambience` | `put_ambience()` | `web/app.py:1384` |
| GET | `/api/ambience/library` | `ambience_library()` | `web/app.py:5712` |
| GET | `/api/ambience/search` | `ambience_search()` | `web/app.py:5691` |
| PUT | `/api/attire_beneath` | `set_attire_beneath()` | `web/app.py:1879` |
| POST | `/api/auth/login` | `auth_login()` | `web/auth_routes.py:109` |
| POST | `/api/auth/logout` | `auth_logout()` | `web/auth_routes.py:172` |
| POST | `/api/auth/setup` | `auth_setup()` | `web/auth_routes.py:70` |
| GET | `/api/auth/status` | `auth_status()` | `web/auth_routes.py:60` |
| GET | `/api/auto_promote` | `get_auto_promote()` | `web/app.py:3374` |
| PUT | `/api/auto_promote` | `set_auto_promote()` | `web/app.py:3378` |
| PUT | `/api/backdrops` | `put_backdrops()` | `web/app.py:1374` |
| GET | `/api/bootstrap` | `bootstrap()` | `web/app.py:1163` |
| POST | `/api/characters` | `char_create()` | `web/app.py:2335` |
| POST | `/api/characters/generate` | `char_generate()` | `web/app.py:2313` |
| POST | `/api/characters/import` | `char_import()` | `web/app.py:2356` |
| DELETE | `/api/characters/{cid}` | `char_del()` | `web/app.py:2471` |
| PUT | `/api/characters/{cid}` | `char_edit()` | `web/app.py:2462` |
| GET | `/api/characters/{cid}/export` | `char_export()` | `web/app.py:2454` |
| POST | `/api/characters/{cid}/fill_appearance` | `char_fill_appearance()` | `web/app.py:2444` |
| POST | `/api/characters/{cid}/fill_psychology` | `char_fill_psychology()` | `web/app.py:2416` |
| POST | `/api/characters/{cid}/generate_greeting` | `char_generate_greeting()` | `web/app.py:2400` |
| POST | `/api/characters/{cid}/recover_greetings` | `char_recover_greetings()` | `web/app.py:2390` |
| POST | `/api/characters/{cid}/start` | `character_start_story()` | `web/app.py:2371` |
| POST | `/api/chats` | `chat_new()` | `web/app.py:2828` |
| POST | `/api/chats/import` | `import_chat()` | `persist/chat_archive.py:175` |
| DELETE | `/api/chats/{cid}` | `chat_del()` | `web/app.py:3015` |
| GET | `/api/chats/{cid}` | `chat_get()` | `web/app.py:3045` |
| PUT | `/api/chats/{cid}` | `chat_edit()` | `web/app.py:2919` |
| POST | `/api/chats/{cid}/abort` | `chat_abort()` | `web/app.py:4640` |
| GET | `/api/chats/{cid}/ambience/oneshot/{name}` | `ambience_oneshot()` | `web/app.py:5721` |
| DELETE | `/api/chats/{cid}/ambience/pin` | `ambience_pin_delete()` | `web/app.py:5769` |
| PUT | `/api/chats/{cid}/ambience/pin` | `ambience_pin_put()` | `web/app.py:5750` |
| GET | `/api/chats/{cid}/ambience/pins` | `ambience_pins_get()` | `web/app.py:5745` |
| GET | `/api/chats/{cid}/ambience/{signature}.audio` | `ambience_audio()` | `web/app.py:5675` |
| GET | `/api/chats/{cid}/attire` | `attire_get()` | `web/app.py:4052` |
| PUT | `/api/chats/{cid}/attire` | `attire_put()` | `web/app.py:4059` |
| GET | `/api/chats/{cid}/backdrop/{signature}.png` | `backdrop_image()` | `web/app.py:5522` |
| GET | `/api/chats/{cid}/background_config` | `bg_cfg_get()` | `web/app.py:4193` |
| PUT | `/api/chats/{cid}/background_config` | `bg_cfg_put()` | `web/app.py:4197` |
| POST | `/api/chats/{cid}/characters` | `chat_add_char()` | `web/app.py:3281` |
| DELETE | `/api/chats/{cid}/characters/{ch}` | `chat_del_char()` | `web/app.py:3643` |
| PUT | `/api/chats/{cid}/characters/{ch}/card` | `chat_char_card_put()` | `web/app.py:3653` |
| PUT | `/api/chats/{cid}/characters/{ch}/dialogue_color` | `dialogue_color_put()` | `web/app.py:3942` |
| GET | `/api/chats/{cid}/characters/{ch}/memories` | `mem_list()` | `web/app.py:4391` |
| POST | `/api/chats/{cid}/characters/{ch}/memories` | `mem_add()` | `web/app.py:4527` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/backfill` | `mem_backfill()` | `web/app.py:4497` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/consolidate` | `mem_consolidate()` | `web/app.py:4482` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/coverage` | `mem_coverage()` | `web/app.py:4518` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/export` | `mem_export()` | `web/app.py:4437` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/import` | `mem_import()` | `web/app.py:4448` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/search` | `mem_search()` | `web/app.py:4412` |
| GET | `/api/chats/{cid}/characters/{ch}/memory-context` | `memory_context_preview()` | `web/app.py:4458` |
| PUT | `/api/chats/{cid}/characters/{ch}/position` | `chat_char_position_put()` | `web/app.py:3859` |
| GET | `/api/chats/{cid}/characters/{ch}/private_history` | `ph_get()` | `web/app.py:3923` |
| PUT | `/api/chats/{cid}/characters/{ch}/private_history` | `ph_put()` | `web/app.py:3933` |
| GET | `/api/chats/{cid}/characters/{ch}/relationships` | `relationships_get()` | `web/app.py:4471` |
| GET | `/api/chats/{cid}/dialogue_config` | `dlg_get()` | `web/app.py:4094` |
| PUT | `/api/chats/{cid}/dialogue_config` | `dlg_put()` | `web/app.py:4111` |
| GET | `/api/chats/{cid}/dramatic_irony` | `get_dramatic_irony_feed()` | `web/app.py:3335` |
| GET | `/api/chats/{cid}/export` | `export_chat()` | `persist/chat_archive.py:169` |
| GET | `/api/chats/{cid}/fixed_points` | `fixed_points_list()` | `web/app.py:4337` |
| POST | `/api/chats/{cid}/fixed_points` | `fixed_points_create()` | `web/app.py:4347` |
| DELETE | `/api/chats/{cid}/fixed_points/{anchor_id}` | `fixed_points_delete()` | `web/app.py:4369` |
| GET | `/api/chats/{cid}/frames` | `frames_list()` | `web/app.py:4291` |
| POST | `/api/chats/{cid}/frames` | `frames_create()` | `web/app.py:4295` |
| GET | `/api/chats/{cid}/guest_invites` | `list_guest_invites()` | `web/app.py:3522` |
| POST | `/api/chats/{cid}/guest_invites` | `create_guest_invite()` | `web/app.py:3504` |
| DELETE | `/api/chats/{cid}/guest_invites/{gid}` | `revoke_guest_invite()` | `web/app.py:3526` |
| GET | `/api/chats/{cid}/language` | `chat_language_get()` | `web/app.py:2886` |
| PUT | `/api/chats/{cid}/language` | `chat_language_put()` | `web/app.py:2903` |
| GET | `/api/chats/{cid}/living_world` | `living_world_get()` | `web/app.py:4158` |
| PUT | `/api/chats/{cid}/living_world` | `living_world_put()` | `web/app.py:4181` |
| DELETE | `/api/chats/{cid}/lorebook` | `detach_lore()` | `web/app.py:3006` |
| POST | `/api/chats/{cid}/lorebook` | `bind_lore()` | `web/app.py:2990` |
| GET | `/api/chats/{cid}/lorebooks` | `chat_lorebooks_owned()` | `web/app.py:1964` |
| POST | `/api/chats/{cid}/lorebooks` | `attach_lore()` | `web/app.py:2950` |
| DELETE | `/api/chats/{cid}/lorebooks/{lid}` | `detach_book()` | `web/app.py:2975` |
| GET | `/api/chats/{cid}/paradox_policy` | `paradox_policy_get()` | `web/app.py:4322` |
| PUT | `/api/chats/{cid}/paradox_policy` | `paradox_policy_put()` | `web/app.py:4326` |
| GET | `/api/chats/{cid}/persona_private_history` | `pph_get()` | `web/app.py:3994` |
| PUT | `/api/chats/{cid}/persona_private_history` | `pph_put()` | `web/app.py:4007` |
| GET | `/api/chats/{cid}/personas` | `chat_list_extra_personas()` | `web/app.py:3383` |
| POST | `/api/chats/{cid}/personas` | `chat_add_persona()` | `web/app.py:3428` |
| DELETE | `/api/chats/{cid}/personas/{pid}` | `chat_del_persona()` | `web/app.py:3452` |
| PUT | `/api/chats/{cid}/personas/{pid}/station` | `chat_persona_station()` | `web/app.py:3393` |
| GET | `/api/chats/{cid}/player_authority` | `player_authority_get()` | `web/app.py:4254` |
| PUT | `/api/chats/{cid}/player_authority` | `player_authority_put()` | `web/app.py:4269` |
| GET | `/api/chats/{cid}/player_view` | `player_view_get()` | `web/app.py:4238` |
| GET | `/api/chats/{cid}/positions` | `chat_positions_get()` | `web/app.py:3795` |
| GET | `/api/chats/{cid}/promises` | `get_promise_ledger()` | `web/app.py:3339` |
| GET | `/api/chats/{cid}/promotable` | `list_promotable_presences()` | `web/app.py:3331` |
| POST | `/api/chats/{cid}/promotions/confirm` | `confirm_promotion()` | `web/app.py:3357` |
| POST | `/api/chats/{cid}/promotions/draft` | `draft_promotion()` | `web/app.py:3343` |
| GET | `/api/chats/{cid}/story_view` | `story_view_get()` | `web/app.py:4223` |
| GET | `/api/chats/{cid}/style_guide` | `style_guide_get()` | `web/app.py:4077` |
| PUT | `/api/chats/{cid}/style_guide` | `style_guide_put()` | `web/app.py:4083` |
| GET | `/api/chats/{cid}/survival` | `survival_get()` | `web/app.py:3710` |
| PUT | `/api/chats/{cid}/survival` | `survival_put()` | `web/app.py:3715` |
| POST | `/api/chats/{cid}/turns` | `turn_new()` | `web/app.py:4580` |
| POST | `/api/chats/{cid}/turns/{idx}/player_input` | `submit_extra_player_input()` | `web/app.py:3466` |
| GET | `/api/chats/{cid}/viewers` | `viewers_get()` | `web/app.py:4248` |
| GET | `/api/chats/{cid}/vitals` | `chat_vitals_get()` | `web/app.py:3762` |
| GET | `/api/chats/{cid}/world` | `world_get()` | `web/app.py:4012` |
| PUT | `/api/chats/{cid}/world` | `world_put()` | `web/app.py:4016` |
| GET | `/api/default_prompts` | `default_prompts()` | `web/app.py:1503` |
| PUT | `/api/director_fanout_mode` | `set_director_fanout_mode()` | `web/app.py:1836` |
| PUT | `/api/exemplars` | `put_exemplars()` | `web/app.py:1343` |
| GET | `/api/extensions` | `extensions_list()` | `web/app.py:1582` |
| POST | `/api/extensions/install` | `extension_install()` | `web/app.py:1597` |
| GET | `/api/extensions/ui.css` | `extensions_ui_css()` | `web/app.py:1757` |
| GET | `/api/extensions/ui.js` | `extensions_ui()` | `web/app.py:1748` |
| GET | `/api/extensions/updates` | `extension_updates()` | `web/app.py:1618` |
| DELETE | `/api/extensions/{eid}` | `extension_remove()` | `web/app.py:1639` |
| GET | `/api/extensions/{eid}/asset/{path:path}` | `extension_asset()` | `web/app.py:1812` |
| POST | `/api/extensions/{eid}/disable` | `extension_disable()` | `web/app.py:1647` |
| DELETE | `/api/extensions/{eid}/document` | `extension_document_delete()` | `web/app.py:1725` |
| GET | `/api/extensions/{eid}/document` | `extension_document_get()` | `web/app.py:1693` |
| PUT | `/api/extensions/{eid}/document` | `extension_document_put()` | `web/app.py:1705` |
| DELETE | `/api/extensions/{eid}/documents` | `extension_documents_delete()` | `web/app.py:1735` |
| GET | `/api/extensions/{eid}/documents` | `extension_documents_list()` | `web/app.py:1672` |
| GET | `/api/extensions/{eid}/documents/verify` | `extension_documents_verify()` | `web/app.py:1683` |
| POST | `/api/extensions/{eid}/enable` | `extension_enable()` | `web/app.py:1589` |
| GET | `/api/extensions/{eid}/state` | `extension_state()` | `web/app.py:1652` |
| GET | `/api/extensions/{eid}/ui.css` | `extension_ui_css_one()` | `web/app.py:1779` |
| GET | `/api/extensions/{eid}/ui.js` | `extension_ui_one()` | `web/app.py:1767` |
| POST | `/api/extensions/{eid}/update` | `extension_update()` | `web/app.py:1629` |
| POST | `/api/guest/input` | `guest_input()` | `web/app.py:3618` |
| GET | `/api/guest/state` | `guest_state()` | `web/app.py:3550` |
| PUT | `/api/image_model` | `put_image_model()` | `web/app.py:1321` |
| POST | `/api/join` | `join_with_code()` | `web/app.py:3532` |
| GET | `/api/language-packs` | `language_packs_get()` | `web/app.py:2846` |
| GET | `/api/language-packs/{language_id}/ui` | `language_pack_ui()` | `web/app.py:2863` |
| DELETE | `/api/lore_entries/{eid}` | `lore_entry_delete()` | `web/app.py:2821` |
| PUT | `/api/lore_entries/{eid}` | `lore_entry_edit()` | `web/app.py:2749` |
| DELETE | `/api/lore_gen_jobs/{job_id}` | `lorebook_generate_discard()` | `web/app.py:2120` |
| POST | `/api/lore_gen_jobs/{job_id}/resume` | `lorebook_generate_resume()` | `web/app.py:2102` |
| DELETE | `/api/lorebook_links/{link_id}` | `lorebook_link_delete()` | `web/app.py:2060` |
| PUT | `/api/lorebook_links/{link_id}` | `lorebook_link_update()` | `web/app.py:2046` |
| POST | `/api/lorebooks` | `lore_create()` | `web/app.py:2578` |
| POST | `/api/lorebooks/import` | `lore_import()` | `web/app.py:2156` |
| DELETE | `/api/lorebooks/{lid}` | `lore_delete()` | `web/app.py:2670` |
| GET | `/api/lorebooks/{lid}` | `lore_get()` | `web/app.py:2558` |
| PUT | `/api/lorebooks/{lid}` | `lore_edit()` | `web/app.py:2600` |
| POST | `/api/lorebooks/{lid}/apply_plan` | `lorebook_apply_plan()` | `web/app.py:2129` |
| POST | `/api/lorebooks/{lid}/entries` | `lore_entry_create()` | `web/app.py:2720` |
| GET | `/api/lorebooks/{lid}/export` | `lore_export()` | `web/app.py:2676` |
| POST | `/api/lorebooks/{lid}/generate` | `lore_generate()` | `web/app.py:2706` |
| GET | `/api/lorebooks/{lid}/generate_job` | `lorebook_generate_job()` | `web/app.py:2091` |
| POST | `/api/lorebooks/{lid}/generate_plan` | `lorebook_generate_plan()` | `web/app.py:2065` |
| GET | `/api/lorebooks/{lid}/links` | `lorebook_links_get()` | `web/app.py:2019` |
| POST | `/api/lorebooks/{lid}/links` | `lorebook_link_create()` | `web/app.py:2024` |
| POST | `/api/lorebooks/{lid}/move` | `lorebook_move()` | `web/app.py:1946` |
| POST | `/api/lorebooks/{lid}/reinterpret` | `lore_reinterpret_route()` | `web/app.py:2693` |
| POST | `/api/lorebooks/{lid}/reorder` | `lorebook_reorder()` | `web/app.py:1955` |
| GET | `/api/maintenance/checkpoints` | `maintenance_checkpoints()` | `web/app.py:1902` |
| POST | `/api/maintenance/checkpoints/compact` | `maintenance_compact()` | `web/app.py:1918` |
| PUT | `/api/max_output_tokens` | `put_max_output_tokens()` | `web/app.py:1470` |
| DELETE | `/api/memories/{mid}` | `mem_del()` | `web/app.py:4574` |
| PUT | `/api/memories/{mid}` | `mem_edit()` | `web/app.py:4553` |
| GET | `/api/memory/embeddings` | `memory_embeddings_status()` | `web/app.py:1294` |
| POST | `/api/memory/embeddings/rebuild` | `memory_embeddings_rebuild()` | `web/app.py:1309` |
| GET | `/api/nsfw` | `get_nsfw()` | `web/app.py:1827` |
| PUT | `/api/nsfw` | `set_nsfw()` | `web/app.py:1831` |
| GET | `/api/openrouter/endpoints` | `get_openrouter_endpoints()` | `web/app.py:1428` |
| PUT | `/api/openrouter_routing` | `put_openrouter_routing()` | `web/app.py:1414` |
| POST | `/api/personas` | `persona_create()` | `web/app.py:2500` |
| POST | `/api/personas/generate` | `persona_generate()` | `web/app.py:2478` |
| POST | `/api/personas/import` | `persona_import()` | `web/app.py:2520` |
| DELETE | `/api/personas/{pid}` | `persona_del()` | `web/app.py:2552` |
| PUT | `/api/personas/{pid}` | `persona_edit()` | `web/app.py:2543` |
| GET | `/api/personas/{pid}/export` | `persona_export()` | `web/app.py:2534` |
| POST | `/api/personas/{pid}/fill_appearance` | `persona_fill_appearance()` | `web/app.py:2449` |
| PUT | `/api/prompt_presets` | `save_preset()` | `web/app.py:1514` |
| POST | `/api/prompt_presets/import` | `import_preset()` | `web/app.py:1542` |
| DELETE | `/api/prompt_presets/{name}` | `del_preset()` | `web/app.py:1556` |
| GET | `/api/prompt_presets/{name}/export` | `export_preset()` | `web/app.py:1533` |
| POST | `/api/providers` | `add_provider()` | `web/app.py:2212` |
| DELETE | `/api/providers/{pid}` | `del_provider()` | `web/app.py:2291` |
| PUT | `/api/providers/{pid}` | `put_provider()` | `web/app.py:2219` |
| GET | `/api/providers/{pid}/image_models` | `image_models()` | `web/app.py:2303` |
| GET | `/api/providers/{pid}/models` | `models()` | `web/app.py:2296` |
| PUT | `/api/providers/{pid}/prompt_cache` | `put_provider_prompt_cache()` | `web/app.py:2246` |
| PUT | `/api/reasoning_effort` | `put_reasoning_effort()` | `web/app.py:1440` |
| POST | `/api/steps/{sid}/activate` | `step_activate()` | `web/app.py:5353` |
| POST | `/api/steps/{sid}/edit` | `step_edit()` | `web/app.py:5343` |
| POST | `/api/steps/{sid}/reroll` | `step_reroll()` | `web/app.py:5296` |
| DELETE | `/api/turns/{tid}` | `turn_del()` | `web/app.py:5366` |
| GET | `/api/turns/{tid}/ambience` | `turn_ambience()` | `web/app.py:5625` |
| POST | `/api/turns/{tid}/ambience` | `turn_ambience_resolve()` | `web/app.py:5642` |
| GET | `/api/turns/{tid}/backdrop` | `turn_backdrop()` | `web/app.py:5447` |
| POST | `/api/turns/{tid}/backdrop` | `turn_backdrop_generate()` | `web/app.py:5495` |
| POST | `/api/turns/{tid}/branch` | `turn_branch()` | `web/app.py:4644` |
| PUT | `/api/turns/{tid}/input` | `edit_input()` | `web/app.py:5046` |
| GET | `/api/turns/{tid}/narration` | `turn_narration_variants()` | `web/app.py:5113` |
| POST | `/api/turns/{tid}/narration` | `turn_narration_select()` | `web/app.py:5134` |
| GET | `/api/turns/{tid}/pipeline` | `pipeline_get()` | `web/app.py:5158` |
| PUT | `/api/turns/{tid}/prose` | `edit_prose()` | `web/app.py:5061` |
| POST | `/api/turns/{tid}/reroll` | `turn_reroll()` | `web/app.py:5227` |
| POST | `/api/turns/{tid}/rerun` | `turn_rerun()` | `web/app.py:5237` |
| POST | `/api/turns/{tid}/resume` | `turn_resume()` | `web/app.py:5264` |
| GET | `/api/ui` | `ui_catalog_get()` | `web/app.py:2853` |
| PUT | `/api/ui-language` | `ui_language_put()` | `web/app.py:2875` |
| GET | `/api/updates/check` | `updates_check()` | `web/app.py:1894` |
| POST | `/api/updates/install` | `updates_install()` | `web/app.py:1898` |
| GET | `/guest` | `guest_page()` | `web/app.py:373` |
| GET | `/login` | `login_page()` | `web/app.py:385` |

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
| `chat_chars` | `chat_id`, `char_id`, `status`, `state`, `--`, `--`, `sheet`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `dialogue_color` |
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

### `static/js/app.js` (1042 lines)

Sections: Boot & sidebar (`:1`); New chat wizard (`:270`); NSFW (`:750`); Composer (`:778`); Init (`:856`); Embedding reconciler progress (`:899`).

Declared functions: `boot()`, `renderSide()`, `syncExtensionTabs()`, `renderChatSidebar()`, `newChatWizard()`, `renderWizardChoice()`, `storyLanguagePacks()`, `defaultStoryLanguage()`, `wizardState()`, `wizardFromScratch()`, `renderWizardPersona()`, `renderWizardCharacters()`, `renderWizardScenario()`, `runWizard()`, `renderCharacterSidebar()`, `renderPersonaSidebar()`, `renderLegacyLoreSidebar()`, `updateNSFWBtn()`, `toggleNSFW()`, `resizeComposer()`, `erCard()`, `erDismiss()`, `erPoll()`, `erWatch()`, `erOfferRebuild()`.

### `static/js/backdrops.js` (430 lines)

Sections: Scene backdrops (`:2`).

Declared functions: `backdropLayers()`, `backdropLuminance()`, `applyBackdropContrast()`, `releaseBackdropLayer()`, `clearBackdrop()`, `showBackdrop()`, `backdropWorking()`, `awaitBackdrop()`, `generateBackdrop()`, `backdropForTurn()`, `backdropOnVisibleTurn()`, `backdropResetForRender()`, `updateBackdropBtn()`, `toggleBackdrops()`, `syncBackdrops()`.

### `static/js/chat.js` (2875 lines)

Sections: The turn being read (`:1`); Colouring who spoke (`:172`); `dialogue_log` is committed per turn and arrives as `turn.speech` -- and (`:175`); Flipping between rerolls of the newest beat (`:966`); Pipeline drawer: reading a step through a lens (`:1280`); Pipeline drawer (`:1604`); Relationship viewer (`:1957`); Memory browser (`:2029`); Private history (`:2817`).

Declared functions: `observeVisibleTurn()`, `openChat()`, `foldTypography()`, `decodeProseEntities()`, `splitEmphasis()`, `appendEmphasized()`, `quoteBody()`, `quotedRegions()`, `speechSpans()`, `paintProse()`, `proseEl()`, `renderFrameBar()`, `switchFrame()`, `updateChatScopedButtons()`, `renderChat()`, `branchTurn()`, `editTurnInput()`, `editTurnProse()`, `liveReset()`, `friendlyPhase()`, `turnStatusStart()`, `turnStatusSet()`, `turnStatusStop()`, `_streamOn()`, `liveFlush()`, `liveAppend()`, `liveStep()`, `handleEvt()`, `showNarrationEarly()`, `clearNarrationEarly()`, `_mountRerollNav()`, `_paintRerollCount()`, `showRerollVariant()`, `abortActiveRun()`, `runStream()`, `confirmCheckpointRestore()`, `runReroll()`, `rerollTurn()`, `exportChat()`, `importChatModal()`, `perceiverViews()`, `loopMindIds()`, `specialistIds()`, `stepLenses()`, `perceiverLabel()`, `facetBadge()`, `lensLabel()`, `renderLensBar()`, `lensSlice()`, `specialistSlice()`, `perceiverSlice()`, `mindSlice()`, `keySlice()`, `renderEngineNotes()`, `openPipeline()`, `relMeter()`, `relationshipModal()`, `memModal()`, `exportCharacterMemories()`, `importCharacterMemoriesModal()`, `memQS()`, `memCharId()`, `loadMemoryBrowse()`, `getMemUI()`, `renderMemorySummary()`, `sortedMems()`, `renderMemoryList()`, `memoryCard()`, `fieldWrap()`, `reloadMemView()`, `runMemorySearch()`, `showNewMemoryForm()`, `checkMemoryCoverage()`, `backfillMemoryEras()`, `consolidateMemories()`, `previewMemoryContext()`, `chatPH()`, `personaPH()`.

### `static/js/chime.js` (179 lines)

Sections: Turn-completion chime (`:2`); Which other waits are worth a chime (`:110`).

Declared functions: `chimeContext()`, `chimeArm()`, `chimePlay()`, `chimeWatches()`, `chimeWorkFinished()`, `chimeSetMuted()`, `toggleChimeMute()`, `updateChimeBtn()`.

### `static/js/components.js` (993 lines)

Sections: Modal (`:38`); Book covers (`:54`); confirm()/prompt() replacements (`:167`); Toasts (`:289`); Background tasks (`:317`); Form helpers (`:403`); Model picker (`:843`); made for every combobox that already has a provider saved -- opened its (`:873`).

Declared functions: `txt()`, `el()`, `coverOfRow()`, `coverOfTitle()`, `modal()`, `modalOwnership()`, `closeModal()`, `closeAllModals()`, `_confirmOverlay()`, `confirmModal()`, `promptModal()`, `promptModalWithToggle()`, `toastHost()`, `toast()`, `renderActivity()`, `elapsedLabel()`, `activityTicking()`, `backgroundTask()`, `buttonTask()`, `loadingBlock()`, `emptyState()`, `fText()`, `fArea()`, `fSelect()`, `fNum()`, `fLineList()`, `fStrList()`, `fCoveragePicker()`, `fAttireGarments()`, `fList()`, `fAbilities()`, `fTraits()`, `fValues()`, `fBeliefs()`, `fCopingStrategies()`, `fAssociations()`, `fGoals()`, `fSenses()`, `fLatent()`, `fExtraParts()`, `fPronouns()`, `phEditor()`, `fetchModels()`, `fetchImageModels()`, `modelCombobox()`, `emitChange()`, `load()`, `showDD()`.

### `static/js/editors.js` (942 lines)

Sections: Background-character promotion (`:701`); Import (file upload) (`:750`); Generate (`:821`); Lorebook generate (`:839`); Lorebooks (`:856`); Export (`:930`).

Declared functions: `appearanceFillButton()`, `defaultCharacterSheet()`, `greetingCarousel()`, `quickStartModal()`, `charEditor()`, `personaEditor()`, `promotionReviewModal()`, `promoteBackgroundPresence()`, `importModal()`, `generateModal()`, `generateLoreModal()`, `loreModal()`, `exportCharacter()`, `exportPersona()`, `exportLorebook()`.

### `static/js/extensions.js` (657 lines)

Sections: Extension host (`:2`); Registration attribution (`:20`); Failure containment (`:56`); ES module entries (`:86`); Registration surface (`:177`); Notices (`:222`); Host services (`:368`); The chat lifecycle, as a declared contract (`:397`); Host-internal accessors (`:479`); Hot load / unload (`:605`).

### `static/js/i18n.js` (106 lines)

Declared functions: `translate()`, `apply()`.

### `static/js/lorebooks.js` (3606 lines)

Sections: Library sidebar (`:241`); Data loading (`:448`); Workspace (`:545`); Book metadata and tree operations (`:1152`); Entry editor (`:1611`); Lorebook relationships (`:2355`); Advanced generator (`:2806`); Interrupted-generation recovery (`:3026`).

Declared functions: `loreBookTypeIcon()`, `loreLinkTypes()`, `normalizeLoreBook()`, `loreOwnershipKey()`, `loreBooksByParent()`, `loreBookMatches()`, `loreVisibleIds()`, `loreBookLabel()`, `parseStoredJSON()`, `loreField()`, `loreSelect()`, `loreBookOptions()`, `renderLoreLibrarySidebar()`, `renderNode()`, `loadLoreWorkspaceData()`, `collectLoreLinkTargets()`, `loreWorkspaceVisible()`, `renderLoreWorkspaceBody()`, `openLoreWorkspace()`, `renderLoreInspector()`, `selectTab()`, `buildLoreWorkspace()`, `renderWorkspaceTree()`, `renderNode()`, `renderTreeList()`, `renderLoreBookEditor()`, `moveLoreBook()`, `reorderLoreBook()`, `promoteLoreBook()`, `demoteLoreBook()`, `createSiblingLoreBook()`, `createLoreBookDialog()`, `refreshLoreUI()`, `renderLoreEntries()`, `renderList()`, `buildLoreEntryCard()`, `splitNumberList()`, `reinterpretLoreBook()`, `generateLoreEntriesPrompt()`, `buildDirectLoreRequest()`, `renderRelationshipOverview()`, `renderLoreRelationshipEditor()`, `renderRelationshipList()`, `showNewRelationshipForm()`, `renderLoreGenerator()`, `adoptGeneratorPlan()`, `generatorPlanMessage()`, `loreGenAgo()`, `refreshLoreGenRecovery()`, `normalizeGeneratorPlan()`, `renderLorePlanPreview()`, `renderOperations()`, `planStat()`, `renderAnalysisSection()`, `addPlanGroup()`, `stripPlanUIFields()`, `acceptedGeneratorPlan()`.

### `static/js/settings.js` (3607 lines)

Sections: Chat tool modals (`:1`); Condition tab (`:686`); Survival tracker (`:746`); Character relocation (`:1058`); API connections (`:1749`); Software updates (host-only; git fast-forward from GitHub origin) (`:2865`); Legacy checkpoint conversion (host-only maintenance) (`:2897`); Prompts (`:3131`); and be able to load that pack's own sheets to edit, rather than (`:3142`); Extensions (`:3309`).

Declared functions: `selectTab()`, `dialogueColorControl()`, `save()`, `renderCastTab()`, `renderConditionTab()`, `hydrateConditionTab()`, `vitalMeter()`, `syncVitalsGutterNow()`, `syncVitalsGutter()`, `hideVitalsHud()`, `vitalsBlock()`, `refreshVitalsHud()`, `clearVitalsHud()`, `hydrateCastLocations()`, `castRoomLabel()`, `castRoomSelect()`, `renderLorebooksTab()`, `renderBookNode()`, `renderMultiplayerTab()`, `renderFramesTab()`, `renderFramesListPanel()`, `renderPersonaStationingPanel()`, `renderParadoxPanel()`, `renderBackgroundPresencesPanel()`, `renderGuestInvitePanel()`, `renderInsightsTab()`, `renderDramaticIronyPanel()`, `renderPromiseLedgerPanel()`, `embeddingBankBlock()`, `modelRecommendationsBlock()`, `renderFirstRunProviderSetup()`, `preferredBackdropSize()`, `renderFullApiSettings()`, `propagateToFollowers()`, `renderUpdateChecking()`, `renderUpdateError()`, `checkpointCompactionBlock()`, `renderUpdateStatus()`, `runUpdateInstall()`, `renderUpdateDone()`, `openPromptsModal()`, `reopenPromptsIfRequested()`, `extensionTrustNote()`, `extensionCapabilitySummary()`, `extensionSettingsSections()`, `openExtensionsMenu()`, `reopenExtensionsIfRequested()`.

### `static/js/theme-init.js` (181 lines)

Declared functions: `readStored()`, `writeStored()`, `normaliseTheme()`, `normaliseProseSize()`, `applyTheme()`, `applyProseSize()`, `normaliseEffects()`, `applyEffects()`, `syncPageHidden()`.

### `static/js/themes.js` (159 lines)

Declared functions: `themePreview()`, `openAppearanceSettings()`.

### `static/js/utils.js` (311 lines)

Sections: API (`:214`); Download (`:304`).

Declared functions: `t()`, `watchUILanguage()`, `localizeDocument()`, `hasDefaultModel()`, `safeId()`, `splitCL()`, `numOr()`, `taggedError()`, `api()`, `streamPost()`, `downloadJSON()`.

### `static/js/weather-fx.js` (548 lines)

Sections: Weather effects (`:2`); the tile (`:178`); the layers (`:251`); lifecycle (`:329`); lightning (`:387`); the exact cost this file exists to avoid. Rain has no wrapper and no (`:527`).

Declared functions: `weatherFxReduced()`, `weatherFxEffectsOff()`, `weatherFxSupported()`, `weatherFxHost()`, `weatherFxRandom()`, `weatherFxTile()`, `weatherFxReach()`, `weatherFxBuild()`, `weatherFxClearLayers()`, `weatherFxStop()`, `weatherFxVisible()`, `weatherFxApply()`, `weatherFxStormy()`, `weatherFxScheduleFlash()`, `weatherFxFlash()`, `weatherFxOpenSky()`, `weatherFxBolt()`, `weatherFxThunder()`, `weatherFxForTurn()`.
