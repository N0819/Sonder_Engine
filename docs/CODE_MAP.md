# Generated Code Map

> Regenerate with `python tools/generate_code_map.py`. Do not hand-edit this file.

## Python modules

| Module | Lines | Purpose | Local dependencies |
|---|---:|---|---|
| `agents/__init__.py` | 95 | Backward-compatible facade for the role-specific agent package. | `agents.background`, `agents.character`, `agents.common`, `agents.director`, `agents.loops`, `agents.mapping`, `agents.narration`, `agents.perception`, `agents.runtime`, `agents.storage`, `story.scene` |
| `agents/background.py` | 1100 |  | `agents.common`, `core.db`, `llm.prompts`, `llm.schemas`, `persist.commit`, `story.character_schema`, `story.scene`, `world.background_claims`, `world.spatial` |
| `agents/character.py` | 3560 | Private character decision agent. | `agents.common`, `core.db`, `core.frames`, `llm.prompts`, `llm.schemas`, `mind`, `mind.affect`, `mind.memory`, `mind.psychology_runtime`, `mind.theory_of_mind`, `story.character_schema`, `story.scene`, `world.gaps`, `world.place_purpose`, `world.spatial`, `world.survival` |
| `agents/common.py` | 6838 | Shared normalization, lore, delivery, and perception helpers. | `core.db`, `core.pipeline_context`, `llm.llm_quality`, `llm.prompts`, `llm.providers`, `llm.schemas`, `mind.memory`, `mind.theory_of_mind`, `persist.commit`, `story`, `story.character_schema`, `story.scene`, `world`, `world.spatial` |
| `agents/composer.py` | 2020 |  | `agents.common`, `story.scene`, `world.spatial` |
| `agents/director.py` | 3767 | Scene establishment, player interpretation, and objective resolution. | `agents.common`, `agents.director_contact`, `agents.director_evidence`, `agents.director_fanout`, `agents.director_floors`, `agents.director_lingua`, `agents.director_movement`, `agents.director_reconcile`, `agents.director_scopes`, `agents.director_views`, `core.db`, `llm`, `llm.prompts`, `llm.providers`, `llm.schemas`, `mind.memory`, `story`, `story.attire`, `story.character_schema`, `story.scene`, `world.paradox`, `world.spatial`, `world.survival` |
| `agents/director_contact.py` | 421 |  | `story.character_schema`, `world.spatial` |
| `agents/director_evidence.py` | 890 |  | `agents.common`, `agents.director_lingua`, `llm`, `world.spatial` |
| `agents/director_fanout.py` | 502 |  | `agents.common`, `agents.director_evidence`, `agents.director_scopes`, `core.db`, `story.character_schema`, `world.survival` |
| `agents/director_floors.py` | 1197 |  | `agents.common`, `agents.director_lingua`, `story.character_schema`, `story.scene`, `world.spatial` |
| `agents/director_lingua.py` | 29 |  | — |
| `agents/director_movement.py` | 969 |  | `agents.director_lingua`, `story.character_schema`, `world.spatial` |
| `agents/director_reconcile.py` | 424 |  | `agents.common`, `agents.director_evidence`, `agents.director_scopes`, `core.db`, `story`, `world.spatial` |
| `agents/director_scopes.py` | 610 |  | `agents.director_views`, `core.db`, `world.survival` |
| `agents/director_views.py` | 434 |  | `agents.common`, `story.character_schema`, `story.scene` |
| `agents/loops.py` | 1128 | Reaction loops, interaction rounds, and deterministic micro-perception. | `agents.character`, `agents.common`, `core.db`, `story.character_schema`, `story.scene`, `world.spatial` |
| `agents/mapping.py` | 330 | Lore routing, cached recall, and retrieval staging. | `agents.common`, `core.db`, `llm.prompts`, `mind.memory`, `story.character_schema`, `story.scene` |
| `agents/narration.py` | 1236 | Player-facing narration agent. | `agents`, `agents.common`, `core.db`, `llm.prompts`, `llm.schemas`, `story.character_schema`, `story.scene`, `world.spatial`, `world.weather` |
| `agents/perception.py` | 3637 | Opening, action-onset, and outcome observer views. | `agents`, `agents.common`, `core.db`, `mind`, `story.character_schema`, `story.scene`, `world.spatial` |
| `agents/runtime.py` | 1302 | Pipeline plans, dispatch, streaming, cancellation, resume, and reruns. | `agents.background`, `agents.character`, `agents.common`, `agents.director`, `agents.loops`, `agents.mapping`, `agents.narration`, `agents.perception`, `agents.storage`, `core.db`, `core.pipeline_context`, `llm.providers`, `persist.checkpoints`, `persist.commit`, `story.character_schema`, `story.scene` |
| `agents/storage.py` | 123 | Step and active-variant persistence helpers. | `core.db` |
| `core/__init__.py` | 6 |  | — |
| `core/db.py` | 1977 | SQLite schema, migrations, connection management, transactions, and key/value world access. | `core.paths` |
| `core/frames.py` | 220 |  | `core.db` |
| `core/jobs.py` | 308 |  | `core.logging_utils` |
| `core/logging_utils.py` | 45 | Structured timing and observability helpers. | — |
| `core/outofband.py` | 392 |  | `core.logging_utils` |
| `core/paths.py` | 32 |  | — |
| `core/pipeline_context.py` | 343 | Typed mutable context passed through a turn pipeline. | `core.db` |
| `core/updates.py` | 399 |  | `core.paths` |
| `dressing/__init__.py` | 6 |  | — |
| `dressing/ambience.py` | 2064 |  | `core`, `core.db`, `core.paths`, `dressing.backdrops`, `world.weather` |
| `dressing/backdrops.py` | 1269 |  | `core`, `core.db`, `core.logging_utils`, `core.paths`, `world.spatial`, `world.weather` |
| `llm/__init__.py` | 6 |  | — |
| `llm/llm_quality.py` | 693 | Strict JSON parsing, schema validation, and model-assisted repair. | `core.pipeline_context`, `llm.prompts`, `llm.providers`, `llm.schemas` |
| `llm/prompt_cache.py` | 79 | Provider-specific prompt-cache helpers. | `llm.providers` |
| `llm/prompts.py` | 453 | Default system prompts and prompt preset access. | `core.db` |
| `llm/providers.py` | 3283 | Provider selection, retries, streaming, cancellation, model listing, and embeddings. | `core.db`, `core.logging_utils` |
| `llm/schemas.py` | 5358 | Pydantic output contracts and semantic validation for agent payloads. | — |
| `mind/__init__.py` | 6 |  | — |
| `mind/affect.py` | 2189 |  | `mind.theory_of_mind` |
| `mind/canon_provenance.py` | 379 |  | — |
| `mind/memory.py` | 127 | Facade re-exporting every mind.memory_* name; holds no domain code of its own. | `core`, `core.db`, `core.logging_utils`, `llm.prompts`, `llm.providers`, `mind.memory_common`, `mind.memory_context`, `mind.memory_inference`, `mind.memory_lore_entries`, `mind.memory_lorebooks`, `mind.memory_read`, `mind.memory_relationships`, `mind.memory_retrieval`, `mind.memory_snapshot`, `mind.memory_summaries`, `mind.memory_vectors`, `mind.memory_write`, `mind.theory_of_mind` |
| `mind/memory_common.py` | 229 | Leaf helpers shared by every memory domain: vocabularies, blob/vector codecs, FTS query, cosine. | `core.db` |
| `mind/memory_context.py` | 557 | The character memory payload: where retrieval, summaries and active state become one context. | `core.db`, `llm.prompts`, `llm.providers`, `mind.memory_common`, `mind.memory_retrieval`, `mind.memory_summaries`, `mind.memory_write` |
| `mind/memory_inference.py` | 154 | Belief confidence at mint and at abandonment, and reconciliation across a mind's inferences. | `core.db`, `mind.memory_write`, `mind.theory_of_mind` |
| `mind/memory_lore_entries.py` | 540 | Lore entries: add/update/delete, embedding stamps and health, search_lore, per-character knowledge scoping. | `core.db`, `core.logging_utils`, `llm.providers`, `mind.memory_common`, `mind.memory_lorebooks`, `mind.memory_write` |
| `mind/memory_lorebooks.py` | 574 | The lorebook graph: hierarchy, links, inheritance modes, per-chat attachment and weights. | `core.db`, `core.logging_utils`, `mind.memory_common` |
| `mind/memory_read.py` | 345 | The one seam a mind reads its own memory through, and the host reads that deliberately cross characters. | `core`, `core.db`, `mind.memory_common`, `mind.memory_write` |
| `mind/memory_relationships.py` | 222 | The relationship graph: axis deltas from conduct and from inference, and the history behind them. | `core.db`, `mind.memory_common`, `mind.memory_write` |
| `mind/memory_retrieval.py` | 1006 | Hybrid retrieval: lexical and vector rankings fused by RRF, tilted by mood and importance, plus unbidden recall. | `core.db`, `core.logging_utils`, `llm.providers`, `mind.memory_common`, `mind.memory_read`, `mind.memory_write` |
| `mind/memory_snapshot.py` | 615 | Checkpoint and archive: vector addressing, the prepare/apply restore split, memory and lorebook dump/restore. | `core.db`, `llm.providers`, `mind.memory_common`, `mind.memory_lore_entries`, `mind.memory_summaries`, `mind.memory_write` |
| `mind/memory_summaries.py` | 688 | Autobiographical, hearsay and surmise summaries: search, support sets, windowed consolidation and backfill. | `core.db`, `llm.prompts`, `llm.providers`, `mind.memory_common`, `mind.memory_read`, `mind.memory_retrieval`, `mind.memory_write` |
| `mind/memory_vectors.py` | 772 | Rebuilding vectors after the embedding model changes: bank status, the rebuild, and its background run. | `core.db`, `core.logging_utils`, `llm.providers`, `mind.memory_common`, `mind.memory_retrieval`, `mind.memory_write` |
| `mind/memory_write.py` | 809 | How a memory becomes a row: normalisation, extraction, FTS mirror, the upsert, and the embedding-repair thread. | `core.db`, `core.logging_utils`, `llm.providers`, `mind.memory_common` |
| `mind/psychology_runtime.py` | 636 |  | — |
| `mind/theory_of_mind.py` | 725 |  | — |
| `persist/__init__.py` | 6 |  | — |
| `persist/chat_archive.py` | 1179 | Typed, atomic chat archive export/import service and HTTP routes. | `core.db`, `llm.schemas`, `mind.memory`, `persist.checkpoints`, `story.character_schema` |
| `persist/checkpoints.py` | 1300 | Whole-chat snapshots and checkpoint restore orchestration. | `core.db`, `mind.memory` |
| `persist/commit.py` | 594 | Atomic commit orchestrator, per-turn lock, thin tail domains, and the facade re-exporting every commit_* name. | `core.db`, `core.frames`, `llm.prompts`, `llm.providers`, `mind`, `mind.memory`, `mind.theory_of_mind`, `persist.commit_attire`, `persist.commit_background`, `persist.commit_common`, `persist.commit_destruction`, `persist.commit_entities`, `persist.commit_ledgers`, `persist.commit_mapping`, `persist.commit_mechanics`, `persist.commit_memory`, `persist.commit_memory_write`, `persist.commit_place_graph`, `persist.commit_room_registry`, `persist.commit_scene_state`, `story`, `story.character_schema`, `story.scene`, `world.comfort`, `world.mechanics`, `world.paradox`, `world.spatial`, `world.spatial_frames`, `world.survival`, `world.weather` |
| `persist/commit_attire.py` | 1047 | The mutable clothing ledger: attire notes, shed/worn garment entities, the validated attire diff. | `persist.commit_common`, `story`, `story.attire` |
| `persist/commit_background.py` | 1791 | Background presences: tracking, identity folding, the reactor gate, promotion to cast. | `core.db`, `mind.memory`, `persist.commit_common`, `story.character_schema`, `story.scene`, `world.spatial` |
| `persist/commit_common.py` | 408 | Leaf helpers shared across commit domains: scalar utilities, name/address roster, entity-id canonicalisation. | `core.db`, `mind.memory`, `story.character_schema`, `world.mechanics`, `world.spatial` |
| `persist/commit_destruction.py` | 411 | Single- and multi-book destruction cascades, retirement, and latency-gated news. | `core.db`, `mind.memory`, `persist.commit_common`, `world.mechanics`, `world.spatial`, `world.spatial_frames` |
| `persist/commit_entities.py` | 501 | world_entities projection of the scene commit, awareness gate, disguise supersession. | `core.db`, `persist.commit_common`, `story.character_schema`, `story.scene`, `world.spatial` |
| `persist/commit_ledgers.py` | 302 | Pending-obligation and world-pressure debt ledgers. | `core.db`, `persist.commit_common` |
| `persist/commit_mapping.py` | 492 | Lore/book mapping commit: book ops, lore ops, canon fallback ops, offscreen-event normaliser. | `core.db`, `core.frames`, `llm.prompts`, `llm.providers`, `mind.memory`, `persist.commit_common`, `story.character_schema`, `world.spatial` |
| `persist/commit_mechanics.py` | 364 | Transit/news sweeps, the world-event spine, information carriers, cast changes. | `core.db`, `persist.commit_common`, `persist.commit_scene_state`, `story.character_schema`, `story.scene`, `world.mechanics` |
| `persist/commit_memory.py` | 1505 | Pre-lock memory preparation: per-mind memories and the psychology deltas riding with them. | `core.db`, `mind`, `mind.memory`, `mind.theory_of_mind`, `persist.commit_background`, `persist.commit_common`, `persist.commit_place_graph`, `story.character_schema`, `world.comfort`, `world.survival` |
| `persist/commit_memory_write.py` | 244 | The durable memory write and its out-of-band consolidation twin. | `core.db`, `mind.memory`, `persist.commit_memory`, `story.character_schema`, `story.scene` |
| `persist/commit_place_graph.py` | 321 | Per-mind durable place graph and per-beat spatial experience. | `world.spatial` |
| `persist/commit_room_registry.py` | 444 | Room identity across frames: registry projection, mint dedup, renames, retirement, exit pruning. | `core.db`, `persist.commit_common`, `story.character_schema`, `world.spatial` |
| `persist/commit_scene_state.py` | 789 | The prepared post-turn scene: pre-lock build, scene commit domain, book anchoring, ground advance. | `core.db`, `mind.memory`, `persist.commit_attire`, `persist.commit_common`, `persist.commit_destruction`, `persist.commit_room_registry`, `story.character_schema`, `world.spatial`, `world.spatial_frames`, `world.weather` |
| `persist/pipeline_trace.py` | 413 | Privacy-conscious export, validation, and offline replay of persisted pipeline history. | `core.db` |
| `story/__init__.py` | 6 |  | — |
| `story/artifacts.py` | 565 |  | `llm.prompts` |
| `story/attire.py` | 2794 |  | — |
| `story/authored_events.py` | 124 |  | `core.db` |
| `story/carriers.py` | 764 |  | `core.db`, `story.character_schema`, `story.scene`, `world`, `world.living_world`, `world.spatial` |
| `story/character_schema.py` | 1840 | Versioned character/persona defaults, normalization, accessors, and export payloads. | `llm.schemas`, `story` |
| `story/couriers.py` | 1090 |  | `story.carriers`, `world` |
| `story/dialogue_colors.py` | 263 |  | — |
| `story/greetings.py` | 859 |  | `agents.runtime`, `agents.storage`, `core`, `llm.llm_quality`, `llm.prompts`, `mind.memory`, `mind.theory_of_mind`, `story.character_schema`, `story.importers` |
| `story/importers.py` | 2892 | Native and AI-assisted character, persona, and lorebook import/generation. | `core.db`, `core.logging_utils`, `llm.prompts`, `llm.providers`, `mind.memory`, `story.character_schema` |
| `story/lore_structure.py` | 248 |  | — |
| `story/scene.py` | 2344 | Scene/cast/persona helpers, recent events, dialogue configuration, and private knowledge. | `core.db`, `story`, `story.attire`, `story.character_schema`, `world.spatial` |
| `web/__init__.py` | 6 |  | — |
| `web/app.py` | 6206 | FastAPI application assembly, resource CRUD, turn control, and streaming endpoints. | `agents`, `core`, `core.db`, `core.frames`, `core.paths`, `dressing.ambience`, `dressing.backdrops`, `llm`, `llm.prompts`, `llm.providers`, `mind.memory`, `persist.chat_archive`, `persist.checkpoints`, `persist.commit`, `story`, `story.character_schema`, `story.dialogue_colors`, `story.importers`, `story.scene`, `web`, `web.auth_routes`, `world`, `world.survival` |
| `web/auth_routes.py` | 279 | Typed host-authentication HTTP routes and cookie transport. | `web` |
| `web/guest_access.py` | 554 |  | `core.db` |
| `web/story_view.py` | 881 |  | `core.db` |
| `world/__init__.py` | 6 |  | — |
| `world/background_claims.py` | 598 |  | `core.db` |
| `world/comfort.py` | 349 |  | `world.spatial` |
| `world/crowds.py` | 673 |  | `world.spatial` |
| `world/degradation.py` | 171 |  | — |
| `world/gaps.py` | 454 |  | `core.db`, `mind.canon_provenance`, `world.spatial`, `world.subjects` |
| `world/living_world.py` | 608 |  | `core.logging_utils`, `world.mechanics` |
| `world/mechanics.py` | 319 |  | `core`, `world.spatial`, `world.spatial_frames` |
| `world/offscreen.py` | 2223 |  | `core`, `core.logging_utils`, `llm.prompts` |
| `world/paradox.py` | 648 |  | `core.db`, `core.frames`, `story.character_schema`, `world.spatial` |
| `world/place_purpose.py` | 545 |  | `mind.theory_of_mind`, `world.comfort`, `world.spatial`, `world.survival` |
| `world/routines.py` | 208 |  | — |
| `world/spatial.py` | 195 | Deterministic room, barrier, hearing, visibility, placement, and scene-diff logic. | `llm.schemas`, `world.spatial_barriers`, `world.spatial_contact_migration`, `world.spatial_contacts`, `world.spatial_containment`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_light`, `world.spatial_merge`, `world.spatial_orientation`, `world.spatial_prose`, `world.spatial_routing`, `world.spatial_senses`, `world.spatial_substance`, `world.spatial_transit` |
| `world/spatial_barriers.py` | 509 |  | — |
| `world/spatial_contact_migration.py` | 331 |  | `world.spatial_contacts`, `world.spatial_identity` |
| `world/spatial_contacts.py` | 1155 |  | `world.spatial_containment`, `world.spatial_identity` |
| `world/spatial_containment.py` | 667 |  | `world.spatial_identity`, `world.spatial_transit` |
| `world/spatial_frames.py` | 1087 |  | `core.db`, `core.frames`, `story.character_schema`, `story.scene`, `world.paradox`, `world.spatial` |
| `world/spatial_geometry.py` | 967 |  | `world.spatial_barriers`, `world.spatial_contacts`, `world.spatial_containment`, `world.spatial_identity`, `world.spatial_orientation` |
| `world/spatial_identity.py` | 458 |  | — |
| `world/spatial_light.py` | 209 |  | `world.spatial_barriers`, `world.spatial_geometry`, `world.spatial_identity` |
| `world/spatial_merge.py` | 1206 |  | `llm.schemas`, `world.spatial_barriers`, `world.spatial_contact_migration`, `world.spatial_contacts`, `world.spatial_containment`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_orientation`, `world.spatial_routing`, `world.spatial_senses`, `world.spatial_substance`, `world.spatial_transit` |
| `world/spatial_orientation.py` | 246 | Bearing math and reciprocal spatial-edge normalization. | — |
| `world/spatial_prose.py` | 344 |  | `world.spatial_contacts`, `world.spatial_containment`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_light` |
| `world/spatial_routing.py` | 1102 |  | `world.spatial_barriers`, `world.spatial_containment`, `world.spatial_light`, `world.spatial_orientation` |
| `world/spatial_senses.py` | 1268 |  | `world.spatial_barriers`, `world.spatial_contacts`, `world.spatial_containment`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_light`, `world.spatial_orientation`, `world.spatial_routing` |
| `world/spatial_substance.py` | 611 |  | `world.spatial_contacts`, `world.spatial_identity` |
| `world/spatial_transit.py` | 410 |  | `world.spatial_barriers`, `world.spatial_identity` |
| `world/subjects.py` | 496 |  | `core.db`, `mind.canon_provenance`, `world.spatial` |
| `world/survival.py` | 341 |  | `core.db` |
| `world/weather.py` | 840 |  | `world.spatial` |

## Largest top-level functions

### `agents/background.py`

| Function | Start | Size |
|---|---:|---:|
| `scene_life()` | 584 | 131 lines |
| `background_react()` | 298 | 91 lines |
| `_beat_for_presence()` | 157 | 80 lines |
| `_present_others()` | 948 | 80 lines |
| `_mint_blurbs()` | 784 | 75 lines |
| `_react_one()` | 1030 | 71 lines |
| `_filtered_player_declaration()` | 85 | 70 lines |
| `managed_presences()` | 458 | 58 lines |

### `agents/character.py`

| Function | Start | Size |
|---|---:|---:|
| `character_step()` | 2560 | 1001 lines |
| `_annotate_known_exits()` | 1911 | 458 lines |
| `_ground_observation_citations()` | 951 | 263 lines |
| `_unanswered_question_note()` | 325 | 163 lines |
| `_destination_from_goals()` | 1477 | 109 lines |
| `sprint_offers()` | 2404 | 97 lines |
| `_recent_self_moves()` | 158 | 90 lines |
| `_verdict()` | 1323 | 71 lines |

### `agents/common.py`

| Function | Start | Size |
|---|---:|---:|
| `norm_sequence()` | 2025 | 224 lines |
| `_check_narrator_fidelity()` | 6435 | 157 lines |
| `_scrub_invented_dialogue()` | 5446 | 151 lines |
| `_extract_authority_claims()` | 1537 | 120 lines |
| `_unknown_actor_label()` | 2590 | 118 lines |
| `cast_spelling_policy()` | 3111 | 118 lines |
| `observer_body_regions()` | 732 | 117 lines |
| `_perceptible_entities()` | 1059 | 109 lines |

### `agents/composer.py`

| Function | Start | Size |
|---|---:|---:|
| `pose_percepts()` | 673 | 92 lines |
| `_render_view_english()` | 1515 | 91 lines |
| `_render_episode_english()` | 1747 | 84 lines |
| `presence_percepts()` | 552 | 77 lines |
| `observations_from_render()` | 1946 | 75 lines |
| `speech_percept()` | 1037 | 62 lines |
| `_episode_sentence()` | 1685 | 60 lines |
| `_render_presence_group()` | 1247 | 59 lines |

### `agents/director.py`

| Function | Start | Size |
|---|---:|---:|
| `director_resolve()` | 2215 | 1519 lines |
| `director_interpret()` | 425 | 538 lines |
| `_reconcile_resolution()` | 1319 | 490 lines |
| `_run_specialists()` | 1991 | 211 lines |
| `director_establish()` | 289 | 134 lines |
| `_reconcile_interpretation()` | 965 | 119 lines |
| `_specialist_repairs()` | 1146 | 119 lines |
| `_prose_gate_facts()` | 1873 | 92 lines |

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
| `_evidence_present()` | 550 | 232 lines |
| `_merge_repair_into_diff()` | 339 | 58 lines |
| `_fold_derived_manifest_events()` | 835 | 56 lines |
| `_interpret_coverage_corpus()` | 90 | 51 lines |
| `_omission_subject_encoded()` | 487 | 51 lines |
| `_strip_blank_diff_placeholders()` | 253 | 42 lines |
| `_manifest_items()` | 789 | 37 lines |
| `_normalize_diff_shape()` | 193 | 36 lines |

### `agents/director_fanout.py`

| Function | Start | Size |
|---|---:|---:|
| `_specialist_payload()` | 135 | 134 lines |
| `_orchestration_scope_backstop()` | 372 | 131 lines |
| `_interpret_beat_view()` | 83 | 35 lines |
| `_resolve_beat_view()` | 51 | 30 lines |
| `_resolved_event_verdicts()` | 303 | 30 lines |
| `fanout_is_parallel()` | 29 | 20 lines |
| `_index_addressed_events()` | 335 | 18 lines |
| `_stage_container()` | 271 | 14 lines |

### `agents/director_floors.py`

| Function | Start | Size |
|---|---:|---:|
| `_awareness_exits()` | 585 | 98 lines |
| `_release_attempts()` | 843 | 93 lines |
| `_narrated_destruction_subjects()` | 1103 | 79 lines |
| `_unsupported_character_awareness()` | 281 | 66 lines |
| `_restraint_exits()` | 969 | 64 lines |
| `_clause_attributed_subjects()` | 403 | 57 lines |
| `_unsupported_player_awareness()` | 152 | 43 lines |
| `_sentence_cooccurrent_names()` | 230 | 41 lines |

### `agents/director_lingua.py`

| Function | Start | Size |
|---|---:|---:|
| `_ling()` | 16 | 14 lines |

### `agents/director_movement.py`

| Function | Start | Size |
|---|---:|---:|
| `_reconcile_near_group_positions()` | 98 | 276 lines |
| `_travel_continues()` | 779 | 109 lines |
| `_apply_following_movement()` | 465 | 88 lines |
| `_guard_approach_is_not_arrival()` | 890 | 80 lines |
| `_unreachable_position_writes()` | 554 | 68 lines |
| `_travel_in_flight_view()` | 728 | 49 lines |
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
| `_gate_facts()` | 515 | 70 lines |
| `register_specialist()` | 373 | 49 lines |
| `_rebuild_channel_owners()` | 343 | 24 lines |
| `_dispatch_specialists()` | 587 | 24 lines |
| `_schema_list_channels()` | 200 | 23 lines |
| `_extension_specialist_call()` | 436 | 17 lines |
| `_shipped_transit_state()` | 455 | 12 lines |
| `unregister_specialists()` | 424 | 10 lines |

### `agents/director_views.py`

| Function | Start | Size |
|---|---:|---:|
| `_report_observer_epithets()` | 230 | 69 lines |
| `_route_authorial_npc_beat()` | 54 | 48 lines |
| `_crowds_view()` | 301 | 40 lines |
| `_couriers_view()` | 343 | 32 lines |
| `_audit_fact_adjudications()` | 185 | 31 lines |
| `_round_conduct()` | 154 | 29 lines |
| `_artifacts_view()` | 377 | 29 lines |
| `_carried_reports_view()` | 408 | 27 lines |

### `agents/loops.py`

| Function | Start | Size |
|---|---:|---:|
| `interaction_loop()` | 500 | 558 lines |
| `deterministic_micro_perception()` | 136 | 133 lines |
| `reaction_loop()` | 1059 | 70 lines |
| `rehydrate_loop_views()` | 85 | 49 lines |
| `_isolated_wave()` | 457 | 41 lines |
| `_defer_to_unrun_reactor()` | 314 | 37 lines |
| `_standing_pressure()` | 353 | 37 lines |
| `_cut_into_last_element()` | 48 | 35 lines |

### `agents/mapping.py`

| Function | Start | Size |
|---|---:|---:|
| `mapping_stage()` | 32 | 116 lines |
| `mapping_quick()` | 231 | 65 lines |
| `merge_lore()` | 298 | 33 lines |
| `_join_relevant_lore()` | 172 | 32 lines |
| `mapping_request_stages_a_room()` | 224 | 5 lines |

### `agents/narration.py`

| Function | Start | Size |
|---|---:|---:|
| `narrator()` | 833 | 252 lines |
| `_ordered_beat_events()` | 442 | 154 lines |
| `narrator_extra()` | 1086 | 151 lines |
| `_sensory_channels_manifest()` | 292 | 148 lines |
| `_visible_portal_states()` | 685 | 88 lines |
| `_resolve_narration_person()` | 82 | 66 lines |
| `_position_delta_payload()` | 629 | 54 lines |
| `_generate_narration()` | 792 | 40 lines |

### `agents/perception.py`

| Function | Start | Size |
|---|---:|---:|
| `_composer_outcome()` | 3310 | 328 lines |
| `perception_outcome()` | 1914 | 244 lines |
| `perception_act()` | 1553 | 171 lines |
| `_composer_act()` | 3091 | 129 lines |
| `_previous_open_group_continuity()` | 163 | 117 lines |
| `_composer_standing_percepts()` | 2854 | 116 lines |
| `_strip_self_narration()` | 860 | 107 lines |
| `_scent_sources_for()` | 2747 | 105 lines |

### `agents/runtime.py`

| Function | Start | Size |
|---|---:|---:|
| `_run_pipeline()` | 935 | 312 lines |
| `resume_key_for_turn()` | 581 | 92 lines |
| `build_plan()` | 674 | 89 lines |
| `_load_extra_players()` | 47 | 74 lines |
| `_stream_one()` | 384 | 68 lines |
| `_stream_parallel()` | 453 | 60 lines |
| `run_pipeline()` | 1248 | 55 lines |
| `_run_parallel_group()` | 518 | 46 lines |

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
| `init()` | 1829 | 105 lines |
| `conn()` | 1621 | 38 lines |
| `transaction()` | 1661 | 36 lines |
| `_column_addition_already_applied()` | 1778 | 18 lines |
| `_backfill_resource_uids()` | 1811 | 17 lines |
| `qi()` | 1719 | 16 lines |
| `data_version()` | 1698 | 14 lines |
| `parse_scoped_world_key()` | 91 | 13 lines |

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
| `submit()` | 71 | 35 lines |
| `_clear_turn_scoped_context()` | 119 | 27 lines |
| `_run()` | 148 | 23 lines |
| `story_rewound_past()` | 271 | 20 lines |
| `_finish()` | 173 | 17 lines |
| `drain()` | 229 | 17 lines |
| `reset()` | 293 | 16 lines |
| `cancel()` | 192 | 13 lines |

### `core/logging_utils.py`

| Function | Start | Size |
|---|---:|---:|
| `log_llm_call()` | 18 | 28 lines |

### `core/outofband.py`

| Function | Start | Size |
|---|---:|---:|
| `drain_all()` | 376 | 17 lines |
| `stopped()` | 132 | 8 lines |

### `core/pipeline_context.py`

| Function | Start | Size |
|---|---:|---:|
| `note_step_warning()` | 34 | 11 lines |

### `core/updates.py`

| Function | Start | Size |
|---|---:|---:|
| `check_updates()` | 295 | 53 lines |
| `install_updates()` | 350 | 50 lines |
| `_git()` | 80 | 41 lines |
| `_github_releases()` | 257 | 36 lines |
| `_upstream_ref()` | 144 | 24 lines |
| `_remote_tip()` | 180 | 15 lines |
| `_is_git_repo()` | 123 | 14 lines |
| `_repo_slug()` | 230 | 13 lines |

### `dressing/ambience.py`

| Function | Start | Size |
|---|---:|---:|
| `resolve_ambience()` | 1653 | 221 lines |
| `_rank_candidates()` | 1065 | 105 lines |
| `refine_layers()` | 756 | 89 lines |
| `cached_ambience()` | 479 | 62 lines |
| `search_freesound()` | 1350 | 61 lines |
| `search_local()` | 867 | 54 lines |
| `_query_ladder()` | 1179 | 51 lines |
| `acoustic_fingerprint()` | 260 | 45 lines |

### `dressing/backdrops.py`

| Function | Start | Size |
|---|---:|---:|
| `generate_backdrop()` | 1075 | 115 lines |
| `room_projection()` | 527 | 73 lines |
| `visual_signature()` | 136 | 48 lines |
| `build_backdrop_request()` | 728 | 41 lines |
| `scene_after_turn()` | 691 | 35 lines |
| `branch_lineage()` | 217 | 34 lines |
| `compose_prompt()` | 840 | 34 lines |
| `compose_revision()` | 902 | 33 lines |

### `llm/llm_quality.py`

| Function | Start | Size |
|---|---:|---:|
| `complete_validated_json()` | 304 | 390 lines |
| `_targeted_field_patch()` | 188 | 63 lines |
| `output_ran_out_of_room()` | 77 | 47 lines |
| `_extract_balanced_object()` | 23 | 34 lines |
| `_step_json_schema()` | 277 | 25 lines |
| `strict_json_parse()` | 126 | 19 lines |
| `_accepted()` | 253 | 19 lines |
| `_strip_fences()` | 59 | 16 lines |

### `llm/prompt_cache.py`

| Function | Start | Size |
|---|---:|---:|
| `add_cache_breakpoint()` | 15 | 37 lines |
| `estimate_cacheable_tokens()` | 66 | 14 lines |
| `supports_prompt_caching()` | 7 | 7 lines |

### `llm/prompts.py`

| Function | Start | Size |
|---|---:|---:|
| `preset_import_document()` | 259 | 51 lines |
| `normalize_preset()` | 122 | 26 lines |
| `_preset_override()` | 206 | 22 lines |
| `_assembled_sheets()` | 38 | 21 lines |
| `character_prompt()` | 408 | 21 lines |
| `specialist_prompt()` | 323 | 17 lines |
| `prose_author_prompt()` | 347 | 17 lines |
| `get_prompt_body()` | 431 | 17 lines |

### `llm/providers.py`

| Function | Start | Size |
|---|---:|---:|
| `_chat_complete_once()` | 2132 | 286 lines |
| `async _chat_complete_async_once()` | 2539 | 115 lines |
| `chat_complete()` | 1893 | 91 lines |
| `async chat_complete_async()` | 2448 | 90 lines |
| `_sse_openai()` | 1754 | 78 lines |
| `async _sse_openai_async()` | 2655 | 63 lines |
| `_sse_anthropic()` | 1833 | 59 lines |
| `_embed_request()` | 2975 | 58 lines |

### `llm/schemas.py`

| Function | Start | Size |
|---|---:|---:|
| `preprocess_llm_output()` | 4080 | 344 lines |
| `_lenient_coerce()` | 745 | 159 lines |
| `validate_llm_output_strict()` | 5229 | 130 lines |
| `semantic_output_errors()` | 5022 | 112 lines |
| `canonicalize_prose_markup()` | 3885 | 102 lines |
| `_uncross_concealed_speech()` | 4009 | 69 lines |
| `_coerce_list_valued_map()` | 128 | 57 lines |
| `_coerce_conditions()` | 3427 | 55 lines |

### `mind/affect.py`

| Function | Start | Size |
|---|---:|---:|
| `resolve_affect()` | 791 | 184 lines |
| `appraise()` | 480 | 145 lines |
| `apply_intent_ops()` | 1207 | 142 lines |
| `apply_project_ops()` | 1395 | 137 lines |
| `normalize_wants()` | 981 | 89 lines |
| `update_drive_strain()` | 1846 | 83 lines |
| `validate_drive_shift()` | 1972 | 79 lines |
| `_advance_intent()` | 1100 | 74 lines |

### `mind/canon_provenance.py`

| Function | Start | Size |
|---|---:|---:|
| `validate_provisional()` | 241 | 106 lines |
| `_node_id_errors()` | 207 | 32 lines |
| `promote()` | 349 | 31 lines |
| `unavailable()` | 186 | 19 lines |
| `outranks()` | 167 | 17 lines |
| `may_assert_consequence()` | 150 | 15 lines |
| `is_node_id()` | 133 | 9 lines |
| `is_canon()` | 144 | 4 lines |

### `mind/memory_common.py`

| Function | Start | Size |
|---|---:|---:|
| `_kw_scores()` | 177 | 31 lines |
| `_cos()` | 209 | 16 lines |
| `_b64_to_blob()` | 146 | 14 lines |
| `_ling()` | 13 | 10 lines |
| `_blob_to_b64()` | 135 | 10 lines |
| `_ids()` | 165 | 7 lines |
| `_storage_json()` | 160 | 4 lines |
| `summary_scope_for()` | 124 | 3 lines |

### `mind/memory_context.py`

| Function | Start | Size |
|---|---:|---:|
| `build_character_memory_context()` | 253 | 293 lines |
| `_with_reading()` | 23 | 101 lines |
| `_origin_on_drift()` | 154 | 97 lines |
| `_beats_ago_span()` | 126 | 21 lines |
| `_summary_id()` | 149 | 3 lines |

### `mind/memory_inference.py`

| Function | Start | Size |
|---|---:|---:|
| `reconcile_inference_confidence()` | 85 | 70 lines |
| `_abandoned_confidence()` | 70 | 13 lines |
| `_mint_confidence_of()` | 56 | 12 lines |

### `mind/memory_lore_entries.py`

| Function | Start | Size |
|---|---:|---:|
| `search_lore()` | 238 | 86 lines |
| `backfill_lore_embedding_stamps()` | 325 | 71 lines |
| `duplicate_lorebook_tree_for_chat()` | 168 | 62 lines |
| `lore_embedding_health()` | 398 | 62 lines |
| `_stamped_live_dimensions()` | 462 | 42 lines |
| `update_lore()` | 128 | 39 lines |
| `knowledge_for_character()` | 506 | 34 lines |
| `add_lore()` | 98 | 29 lines |

### `mind/memory_lorebooks.py`

| Function | Start | Size |
|---|---:|---:|
| `monitoring_subtree()` | 414 | 78 lines |
| `resolve_lorebook_graph()` | 226 | 76 lines |
| `restore_lorebook_links()` | 508 | 66 lines |
| `lorebook_manifest()` | 348 | 65 lines |
| `add_lorebook_link()` | 125 | 43 lines |
| `move_lorebook()` | 53 | 37 lines |
| `reorder_lorebook()` | 91 | 30 lines |
| `would_create_book_cycle()` | 25 | 27 lines |

### `mind/memory_read.py`

| Function | Start | Size |
|---|---:|---:|
| `record_dispute()` | 238 | 56 lines |
| `update_memory()` | 186 | 51 lines |
| `visible_memory_rows()` | 50 | 45 lines |
| `raise_importance()` | 296 | 44 lines |
| `list_memories()` | 158 | 27 lines |
| `dramatic_irony_feed()` | 108 | 26 lines |
| `promise_ledger()` | 135 | 22 lines |
| `delete_memory()` | 342 | 3 lines |

### `mind/memory_relationships.py`

| Function | Start | Size |
|---|---:|---:|
| `update_relationships_from_inference()` | 163 | 55 lines |
| `apply_relationship_updates()` | 113 | 41 lines |
| `record_relationship_event()` | 73 | 25 lines |
| `relationship_history()` | 100 | 11 lines |
| `get_relationships()` | 57 | 5 lines |
| `relationships_for_payload()` | 219 | 3 lines |
| `save_relationships()` | 63 | 2 lines |

### `mind/memory_retrieval.py`

| Function | Start | Size |
|---|---:|---:|
| `search_memories()` | 406 | 284 lines |
| `contrast_memory()` | 834 | 117 lines |
| `_rank_normalized_importance()` | 343 | 61 lines |
| `recall_confidence()` | 740 | 58 lines |
| `recent_memory_buffer()` | 965 | 41 lines |
| `_exact_cue_score()` | 96 | 33 lines |
| `_congruence_valence()` | 249 | 29 lines |
| `_warn_stranded_embeddings()` | 304 | 29 lines |

### `mind/memory_snapshot.py`

| Function | Start | Size |
|---|---:|---:|
| `restore_lorebook()` | 520 | 95 lines |
| `prepare_chat_memory_restore()` | 235 | 75 lines |
| `import_character_memories()` | 374 | 63 lines |
| `dump_chat_memories()` | 165 | 61 lines |
| `restore_memory_vectors()` | 109 | 54 lines |
| `vector_address()` | 26 | 35 lines |
| `apply_chat_memory_restore()` | 311 | 35 lines |
| `dump_character_memories()` | 350 | 23 lines |

### `mind/memory_summaries.py`

| Function | Start | Size |
|---|---:|---:|
| `backfill_memory_summary_windows()` | 490 | 89 lines |
| `search_memory_summaries()` | 69 | 77 lines |
| `consolidate_character_memory()` | 581 | 75 lines |
| `derive_summary_support()` | 165 | 59 lines |
| `_write_consolidated_window()` | 392 | 57 lines |
| `save_memory_summary()` | 247 | 39 lines |
| `get_memory_summary()` | 30 | 38 lines |
| `memory_summary_coverage()` | 451 | 37 lines |

### `mind/memory_vectors.py`

| Function | Start | Size |
|---|---:|---:|
| `rebuild_embeddings()` | 178 | 213 lines |
| `embedding_bank_status()` | 28 | 125 lines |
| `rebuild_checkpoint_embeddings()` | 430 | 124 lines |
| `repair_memory_cues()` | 579 | 108 lines |
| `start_rebuild_if_needed()` | 723 | 48 lines |
| `_run_rebuild()` | 695 | 26 lines |
| `_vector_key()` | 393 | 22 lines |
| `_rebuild_book_ids()` | 155 | 21 lines |

### `mind/memory_write.py`

| Function | Start | Size |
|---|---:|---:|
| `_extract_entities()` | 109 | 63 lines |
| `repair_pending_embeddings()` | 491 | 59 lines |
| `prepare_memory()` | 336 | 51 lines |
| `_extract_key_phrases()` | 173 | 48 lines |
| `_upsert_memory()` | 582 | 38 lines |
| `_embed_in_request_sized_chunks()` | 657 | 37 lines |
| `_row_memory()` | 301 | 34 lines |
| `repair_seed_salience()` | 779 | 30 lines |

### `mind/psychology_runtime.py`

| Function | Start | Size |
|---|---:|---:|
| `resolve_hedonic()` | 96 | 138 lines |
| `resolve_stress()` | 236 | 108 lines |
| `apply_belief_updates()` | 447 | 74 lines |
| `apply_association_updates()` | 523 | 49 lines |
| `_authored_beliefs()` | 399 | 46 lines |
| `cognitive_absorption()` | 592 | 45 lines |
| `_within_cap()` | 360 | 29 lines |
| `elapsed_psych_units()` | 79 | 15 lines |

### `mind/theory_of_mind.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_mind_model_updates()` | 345 | 153 lines |
| `select_active_hypotheses()` | 633 | 62 lines |
| `rekey_place_claims()` | 293 | 50 lines |
| `belief_credence()` | 534 | 37 lines |
| `claim_similarity()` | 208 | 35 lines |
| `mind_models_for_payload()` | 499 | 33 lines |
| `_same_belief()` | 244 | 26 lines |
| `cap_mind_model_updates()` | 111 | 19 lines |

### `persist/chat_archive.py`

| Function | Start | Size |
|---|---:|---:|
| `_exportable_checkpoint_blob()` | 93 | 20 lines |
| `_exportable_world()` | 87 | 4 lines |
| `_model_validate()` | 115 | 4 lines |
| `_model_dump()` | 121 | 4 lines |

### `persist/checkpoints.py`

| Function | Start | Size |
|---|---:|---:|
| `snapshot_state()` | 15 | 174 lines |
| `_restore_checkpoint_body()` | 675 | 141 lines |
| `compact_checkpoints()` | 959 | 123 lines |
| `_restore_books()` | 248 | 106 lines |
| `insert_world_tables()` | 442 | 105 lines |
| `ensure_checkpoint()` | 1148 | 53 lines |
| `propagate_memory_summaries_to_checkpoints()` | 1203 | 53 lines |
| `_verify_no_loss()` | 907 | 50 lines |

### `persist/commit.py`

| Function | Start | Size |
|---|---:|---:|
| `_commit_all_locked()` | 363 | 231 lines |
| `commit_crowds()` | 243 | 82 lines |
| `commit_narration_person()` | 162 | 29 lines |
| `commit_authored_events()` | 194 | 25 lines |
| `_prepare_turn_commit()` | 340 | 12 lines |
| `commit_offscreen_epoch()` | 221 | 11 lines |
| `commit_all()` | 327 | 11 lines |
| `commit_offscreen_plans()` | 234 | 7 lines |

### `persist/commit_attire.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_attire_diff()` | 688 | 360 lines |
| `interpret_attire_notes()` | 208 | 115 lines |
| `_fold_duplicate_shed_garments()` | 325 | 85 lines |
| `_fold_worn_garment_entities()` | 412 | 69 lines |
| `_mint_shed_garments()` | 554 | 66 lines |
| `_merge_attire_regions()` | 29 | 65 lines |
| `_heal_attire_identity_keys()` | 96 | 61 lines |
| `_drop_overlay_conditions()` | 642 | 44 lines |

### `persist/commit_background.py`

| Function | Start | Size |
|---|---:|---:|
| `track_background_presences()` | 779 | 362 lines |
| `pick_background_reactors()` | 1284 | 186 lines |
| `promote_background_character()` | 1543 | 125 lines |
| `_fold_duplicate_presences()` | 451 | 88 lines |
| `auto_promote_background_characters()` | 1707 | 85 lines |
| `_presence_speech_verdict()` | 318 | 67 lines |
| `_at_post_within_earshot()` | 1220 | 52 lines |
| `_is_inert_presence_candidate()` | 702 | 50 lines |

### `persist/commit_common.py`

| Function | Start | Size |
|---|---:|---:|
| `_names_heard_in()` | 189 | 53 lines |
| `_address_forms()` | 140 | 47 lines |
| `_entity_alias_map()` | 334 | 47 lines |
| `_monotonic_elapsed()` | 72 | 38 lines |
| `_registered_name_roster()` | 273 | 28 lines |
| `_normalize_character_output()` | 34 | 27 lines |
| `_known_name_roster()` | 244 | 27 lines |
| `_resolve_roster_name()` | 302 | 20 lines |

### `persist/commit_destruction.py`

| Function | Start | Size |
|---|---:|---:|
| `_prepare_destruction()` | 193 | 155 lines |
| `_destruction_cascade()` | 125 | 66 lines |
| `_apply_destruction()` | 378 | 34 lines |
| `_chat_book_graph()` | 52 | 30 lines |
| `_finalize_destruction_news()` | 350 | 26 lines |
| `_audience_book_id()` | 103 | 20 lines |
| `_book_distances()` | 84 | 17 lines |
| `_destruction_book()` | 34 | 16 lines |

### `persist/commit_entities.py`

| Function | Start | Size |
|---|---:|---:|
| `commit_world_entities()` | 215 | 287 lines |
| `_supersede_disguises()` | 96 | 74 lines |
| `_inherit_known_to()` | 172 | 41 lines |
| `_subjects_that_moved()` | 35 | 36 lines |
| `_subjects_targeted_by_an_action()` | 73 | 21 lines |
| `_is_gated_awareness()` | 17 | 16 lines |

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
| `commit_mapping()` | 294 | 142 lines |
| `prepare_mapping_commit()` | 161 | 131 lines |
| `_apply_mapping_book_ops()` | 57 | 103 lines |
| `normalize_offscreen_events()` | 21 | 35 lines |
| `_generate_fallback_ops()` | 462 | 31 lines |
| `_fact_is_covered()` | 443 | 18 lines |
| `_lore_for()` | 439 | 2 lines |

### `persist/commit_mechanics.py`

| Function | Start | Size |
|---|---:|---:|
| `commit_transit_sweep()` | 21 | 170 lines |
| `commit_information_carriers()` | 241 | 85 lines |
| `commit_world_event_spine()` | 193 | 46 lines |
| `commit_cast_changes()` | 329 | 36 lines |

### `persist/commit_memory.py`

| Function | Start | Size |
|---|---:|---:|
| `prepare_memory_commit()` | 236 | 1270 lines |
| `_cited_memory_ids()` | 75 | 76 lines |
| `_own_sequence_memory()` | 199 | 36 lines |
| `_marked_for_memory()` | 153 | 24 lines |
| `_durable_dialogue_category()` | 52 | 22 lines |
| `_salience_of()` | 187 | 10 lines |
| `_ling()` | 35 | 9 lines |
| `_is_player()` | 183 | 3 lines |

### `persist/commit_memory_write.py`

| Function | Start | Size |
|---|---:|---:|
| `schedule_memory_consolidation()` | 78 | 85 lines |
| `commit_memories()` | 165 | 80 lines |
| `_consolidate_committed_memories()` | 22 | 51 lines |

### `persist/commit_place_graph.py`

| Function | Start | Size |
|---|---:|---:|
| `update_place_graph()` | 45 | 180 lines |
| `record_spatial_experience()` | 227 | 95 lines |

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
| `prepare_scene_commit()` | 211 | 533 lines |
| `sync_anchored_books()` | 49 | 66 lines |
| `_guard_occupied_mover_removal()` | 116 | 60 lines |
| `_advance_ground()` | 178 | 31 lines |
| `_record_subject_last_seen()` | 766 | 24 lines |
| `commit_scene()` | 746 | 18 lines |
| `_anchor_current_room()` | 33 | 14 lines |

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
| `advance()` | 1957 | 135 lines |
| `normalize_regions()` | 505 | 133 lines |
| `coerce_diff_shape()` | 1365 | 124 lines |
| `compact_line()` | 2653 | 123 lines |
| `perceptible_region_surfaces()` | 2195 | 100 lines |
| `_attributed_targets()` | 1579 | 90 lines |
| `recover_shed_entity_changes()` | 1131 | 87 lines |
| `dedupe_regions()` | 1220 | 87 lines |

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
| `apply_tellings()` | 566 | 199 lines |
| `advance_carriers()` | 125 | 131 lines |
| `_carriers()` | 385 | 59 lines |
| `_crowds_acquire()` | 258 | 56 lines |
| `persona_entry()` | 316 | 40 lines |
| `carried_reports_view()` | 446 | 36 lines |
| `_invented_claim()` | 503 | 34 lines |
| `_crowd_index()` | 539 | 25 lines |

### `story/character_schema.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_character_data()` | 1074 | 159 lines |
| `default_character_data()` | 590 | 102 lines |
| `_normalize_psychology()` | 314 | 83 lines |
| `repair_character_shape()` | 1015 | 57 lines |
| `character_card_warnings()` | 1756 | 54 lines |
| `_normalize_extra_parts()` | 536 | 52 lines |
| `_as_profile_list()` | 38 | 50 lines |
| `normalize_persona_data()` | 1234 | 50 lines |

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
| `resolve_cast_colors()` | 191 | 47 lines |
| `_spread()` | 240 | 19 lines |
| `_derived_hue()` | 151 | 16 lines |
| `normalize_color()` | 69 | 13 lines |
| `_hue_from()` | 134 | 10 lines |
| `auto_dialogue_color()` | 169 | 9 lines |
| `_hue_of()` | 180 | 9 lines |

### `story/greetings.py`

| Function | Start | Size |
|---|---:|---:|
| `_seed_mind_state()` | 350 | 144 lines |
| `start_story()` | 653 | 108 lines |
| `generate_greeting()` | 763 | 62 lines |
| `_seed_minds()` | 548 | 57 lines |
| `_route_mind_memories()` | 293 | 55 lines |
| `_seed_player_mind()` | 496 | 50 lines |
| `claim_greeting_mind()` | 607 | 44 lines |
| `extract_greeting()` | 121 | 35 lines |

### `story/importers.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_lorebook_plan()` | 2582 | 214 lines |
| `import_lorebook()` | 1383 | 212 lines |
| `_reinterpret_entries()` | 1256 | 126 lines |
| `_lore_gen_entry_batch()` | 2224 | 119 lines |
| `_run_lore_gen_job()` | 2347 | 112 lines |
| `draft_promoted_character()` | 732 | 109 lines |
| `fill_appearance()` | 1023 | 103 lines |
| `generate_lore_entries()` | 2796 | 97 lines |

### `story/lore_structure.py`

| Function | Start | Size |
|---|---:|---:|
| `derive_knowledge()` | 195 | 54 lines |
| `parse_structure()` | 78 | 45 lines |
| `clean_title()` | 46 | 16 lines |
| `classify_title()` | 64 | 12 lines |
| `_matches()` | 160 | 12 lines |
| `_place_name()` | 151 | 7 lines |

### `story/scene.py`

| Function | Start | Size |
|---|---:|---:|
| `active_disguises()` | 459 | 82 lines |
| `normalize_transformed_parts()` | 550 | 60 lines |
| `recent_events_for_observer()` | 1590 | 59 lines |
| `_positive_presented_appearance()` | 747 | 58 lines |
| `awareness_conditions()` | 1076 | 58 lines |
| `active_transformations()` | 612 | 54 lines |
| `director_context()` | 1650 | 53 lines |
| `conceal_disguised_parts()` | 862 | 48 lines |

### `web/app.py`

| Function | Start | Size |
|---|---:|---:|
| `turn_branch()` | 5023 | 406 lines |
| `chat_get()` | 3311 | 234 lines |
| `_remap_cp_blob()` | 996 | 211 lines |
| `bootstrap()` | 1327 | 104 lines |
| `_stream()` | 642 | 91 lines |
| `dlg_put()` | 4433 | 79 lines |
| `_ambience_payload()` | 5981 | 75 lines |
| `lore_entry_edit()` | 2967 | 70 lines |

### `web/auth_routes.py`

| Function | Start | Size |
|---|---:|---:|
| `auth_login()` | 209 | 63 lines |
| `auth_setup()` | 134 | 58 lines |
| `request_is_local()` | 58 | 21 lines |
| `_set_guest_cookie()` | 102 | 19 lines |
| `_rate_limited()` | 194 | 12 lines |
| `_set_host_cookie()` | 90 | 10 lines |
| `public_mode()` | 81 | 7 lines |
| `auth_status()` | 124 | 7 lines |

### `web/guest_access.py`

| Function | Start | Size |
|---|---:|---:|
| `redeem_code()` | 382 | 48 lines |
| `sweep_expired_access()` | 488 | 39 lines |
| `verify_host_login()` | 157 | 36 lines |
| `_parse_password_record()` | 98 | 32 lines |
| `list_grants()` | 529 | 26 lines |
| `create_host_account()` | 132 | 23 lines |
| `claim_login_attempt()` | 350 | 22 lines |
| `verify_guest_token()` | 432 | 19 lines |

### `web/story_view.py`

| Function | Start | Size |
|---|---:|---:|
| `_people()` | 692 | 77 lines |
| `_player_view_in_frame()` | 822 | 60 lines |
| `player_view()` | 771 | 49 lines |
| `_public_facts()` | 512 | 46 lines |
| `_story_view_in_frame()` | 315 | 40 lines |
| `viewers()` | 375 | 36 lines |
| `_person_refs()` | 609 | 36 lines |
| `_viewer_memories()` | 447 | 32 lines |

### `world/background_claims.py`

| Function | Start | Size |
|---|---:|---:|
| `_verdicts()` | 475 | 58 lines |
| `settle_claims()` | 535 | 46 lines |
| `canon_entry()` | 346 | 41 lines |
| `novel_proper_nouns()` | 180 | 39 lines |
| `prepare_canon()` | 415 | 32 lines |
| `_mint()` | 221 | 29 lines |
| `write_canon()` | 389 | 24 lines |
| `_named_in_record()` | 449 | 24 lines |

### `world/comfort.py`

| Function | Start | Size |
|---|---:|---:|
| `_derive()` | 249 | 82 lines |
| `_posture_of()` | 216 | 31 lines |
| `_is_body()` | 180 | 21 lines |
| `_fields()` | 134 | 12 lines |
| `_entity_record()` | 166 | 12 lines |
| `_station_of()` | 203 | 11 lines |
| `_warm()` | 152 | 8 lines |
| `comfort_level()` | 333 | 8 lines |

### `world/crowds.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_ops()` | 284 | 160 lines |
| `talk_view()` | 617 | 44 lines |
| `emerge()` | 446 | 38 lines |
| `drift()` | 184 | 35 lines |
| `advance_crowds()` | 517 | 32 lines |
| `normalize_band()` | 98 | 29 lines |
| `absorb()` | 486 | 29 lines |
| `describe()` | 562 | 21 lines |

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
| `_skeleton()` | 128 | 175 lines |
| `last_seen_update()` | 349 | 70 lines |
| `gap_for()` | 305 | 38 lines |
| `interim_for()` | 421 | 34 lines |
| `_record()` | 86 | 20 lines |
| `_subject_room()` | 114 | 12 lines |
| `_read_key()` | 73 | 4 lines |
| `_unavailable()` | 108 | 4 lines |

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
| `_fire_due_events()` | 111 | 96 lines |
| `mechanics_sweep()` | 267 | 53 lines |
| `_schedule_new_arrivals()` | 209 | 44 lines |
| `news_latency_seconds()` | 91 | 10 lines |
| `_expire_conditions()` | 255 | 10 lines |
| `stable_event_key()` | 69 | 6 lines |
| `_payload_of()` | 103 | 6 lines |

### `world/offscreen.py`

| Function | Start | Size |
|---|---:|---:|
| `land_agent_tick()` | 1917 | 187 lines |
| `schedule_agent_ticks()` | 2106 | 118 lines |
| `schedule_profile_ticks()` | 1406 | 112 lines |
| `apply_plan_ops()` | 731 | 110 lines |
| `agent_context()` | 1584 | 109 lines |
| `advance_epoch()` | 976 | 98 lines |
| `advance_reactive_plans()` | 889 | 85 lines |
| `profile_summary_record()` | 1157 | 85 lines |

### `world/paradox.py`

| Function | Start | Size |
|---|---:|---:|
| `check_and_apply_paradox()` | 584 | 65 lines |
| `_apply_toll()` | 312 | 56 lines |
| `_force_restore_anchor()` | 536 | 46 lines |
| `_advance_paradox()` | 498 | 36 lines |
| `_trigger_paradox()` | 463 | 33 lines |
| `_apply_warden_stage()` | 394 | 29 lines |
| `_apply_hazard_stage()` | 282 | 28 lines |
| `_project_entity_row()` | 370 | 22 lines |

### `world/place_purpose.py`

| Function | Start | Size |
|---|---:|---:|
| `mirror_told_affords()` | 357 | 91 lines |
| `witness_affords()` | 281 | 68 lines |
| `here_affords()` | 224 | 50 lines |
| `place_options()` | 489 | 43 lines |
| `_walked_hops()` | 467 | 20 lines |
| `felt_needs()` | 450 | 15 lines |
| `assumed_affords()` | 210 | 12 lines |
| `affords_here()` | 534 | 12 lines |

### `world/routines.py`

| Function | Start | Size |
|---|---:|---:|
| `residue_for()` | 164 | 45 lines |
| `entropy_facts()` | 136 | 26 lines |
| `routine_band()` | 92 | 22 lines |
| `occupancy_fact()` | 116 | 18 lines |
| `_roll()` | 81 | 9 lines |

### `world/spatial_barriers.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_barrier()` | 282 | 67 lines |
| `neighbor_map()` | 469 | 41 lines |
| `_barrier_against_its_own_name()` | 401 | 27 lines |
| `normalize_scene_barriers()` | 367 | 21 lines |
| `unresolved_barrier_words()` | 351 | 15 lines |
| `_barrier_exact()` | 271 | 9 lines |
| `route_memory_barrier()` | 461 | 3 lines |

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
| `apply_contact_ops()` | 673 | 318 lines |
| `_clean_contact()` | 450 | 108 lines |
| `normalize_scene_contacts()` | 600 | 45 lines |
| `contacts_broken_by_scale_change()` | 560 | 38 lines |
| `_contained_inversion()` | 419 | 29 lines |
| `canonical_region()` | 181 | 28 lines |
| `_part_identity()` | 132 | 26 lines |
| `owned_region()` | 236 | 24 lines |

### `world/spatial_containment.py`

| Function | Start | Size |
|---|---:|---:|
| `_body_interior_holder()` | 322 | 75 lines |
| `normalize_scene_containment()` | 479 | 60 lines |
| `derive_contained_positions()` | 541 | 42 lines |
| `size_facts()` | 170 | 40 lines |
| `size_relation()` | 131 | 37 lines |
| `normalize_scene_scales()` | 89 | 34 lines |
| `_hiding_holders()` | 399 | 34 lines |
| `scale_changed_names()` | 585 | 30 lines |

### `world/spatial_frames.py`

| Function | Start | Size |
|---|---:|---:|
| `infer_focus()` | 486 | 153 lines |
| `infer_threshold_crossings()` | 388 | 96 lines |
| `perform_split()` | 817 | 94 lines |
| `infer_companion_carry()` | 235 | 88 lines |
| `infer_vehicle_zones()` | 148 | 85 lines |
| `infer_facing()` | 641 | 71 lines |
| `perform_merge()` | 989 | 69 lines |
| `detect_split()` | 771 | 44 lines |

### `world/spatial_geometry.py`

| Function | Start | Size |
|---|---:|---:|
| `derive_scene_stations()` | 864 | 104 lines |
| `egocentric_frame()` | 50 | 80 lines |
| `spatial_digest()` | 132 | 61 lines |
| `effective_station()` | 312 | 55 lines |
| `normalize_scene_poses()` | 728 | 53 lines |
| `effective_anchors()` | 260 | 50 lines |
| `guessed_room_sizes()` | 452 | 50 lines |
| `normalize_scene_stations()` | 670 | 35 lines |

### `world/spatial_identity.py`

| Function | Start | Size |
|---|---:|---:|
| `canonical_subject_map()` | 268 | 87 lines |
| `normalize_scene_subjects()` | 366 | 80 lines |
| `room_of()` | 33 | 77 lines |
| `_live_subject_spellings()` | 219 | 47 lines |
| `same_subject()` | 127 | 28 lines |
| `_entities_named()` | 157 | 22 lines |
| `_positions_lookup()` | 10 | 21 lines |
| `_ci_get()` | 112 | 13 lines |

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
| `merge_scene_with_diff()` | 865 | 342 lines |
| `_shield_minted_edges()` | 603 | 95 lines |
| `apply_following_ops()` | 786 | 77 lines |
| `connect_orphan_new_rooms()` | 700 | 68 lines |
| `_merge_room()` | 129 | 64 lines |
| `_shield_standing_bearings()` | 478 | 61 lines |
| `_shield_standing_passage()` | 541 | 60 lines |
| `_dedup_duplicate_entity_keys()` | 418 | 58 lines |

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
| `contact_sensation()` | 113 | 144 lines |
| `contact_phrase()` | 22 | 89 lines |
| `spatial_facts()` | 259 | 86 lines |

### `world/spatial_routing.py`

| Function | Start | Size |
|---|---:|---:|
| `sprint_reach()` | 705 | 175 lines |
| `visible_adjacent_rooms()` | 950 | 153 lines |
| `corridor_sightlines()` | 557 | 85 lines |
| `spatial_rel()` | 264 | 83 lines |
| `_onward_exits()` | 882 | 66 lines |
| `passable_path()` | 655 | 48 lines |
| `passable_route_next_step()` | 361 | 46 lines |
| `stamp_sight_direction()` | 176 | 45 lines |

### `world/spatial_senses.py`

| Function | Start | Size |
|---|---:|---:|
| `hear_level()` | 732 | 138 lines |
| `spatial_rel_between()` | 466 | 71 lines |
| `sound_bearing()` | 1023 | 69 lines |
| `scent_level()` | 37 | 56 lines |
| `_clean_comms_channel()` | 158 | 53 lines |
| `_opening_view_cap()` | 553 | 52 lines |
| `visual_level_between()` | 607 | 52 lines |
| `can_perceive_onset()` | 347 | 39 lines |

### `world/spatial_substance.py`

| Function | Start | Size |
|---|---:|---:|
| `_resolved_substance_add()` | 180 | 129 lines |
| `apply_substance_ops()` | 484 | 82 lines |
| `speech_articulation_impediment()` | 40 | 63 lines |
| `_same_pool()` | 353 | 50 lines |
| `_stock_consumed_by()` | 434 | 48 lines |
| `resolve_substance_ops()` | 311 | 40 lines |
| `substance_event_clause()` | 576 | 36 lines |
| `_substance_target_exists()` | 155 | 23 lines |

### `world/spatial_transit.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_transit_dock_edges()` | 178 | 170 lines |
| `ambient_scope()` | 382 | 29 lines |
| `infer_body_enclosures()` | 90 | 27 lines |
| `_is_body_entity()` | 62 | 26 lines |
| `containment_chain()` | 362 | 19 lines |
| `_link_state()` | 148 | 14 lines |
| `_entity_exterior_room()` | 163 | 14 lines |
| `_closed_enclosure_barrier()` | 133 | 13 lines |

### `world/subjects.py`

| Function | Start | Size |
|---|---:|---:|
| `_resolve_room()` | 272 | 47 lines |
| `resolve_subject()` | 429 | 45 lines |
| `_resolve_character()` | 190 | 32 lines |
| `_lore_matches()` | 325 | 29 lines |
| `_resolve_from_lore()` | 356 | 29 lines |
| `_registry_room_matches()` | 245 | 25 lines |
| `_cast_matches()` | 121 | 22 lines |
| `_presence_reason()` | 166 | 22 lines |

### `world/survival.py`

| Function | Start | Size |
|---|---:|---:|
| `tick_vitals()` | 224 | 61 lines |
| `apply_vitals_diff()` | 287 | 30 lines |
| `seed_vitals()` | 146 | 23 lines |
| `is_sealed_in()` | 199 | 23 lines |
| `vitals_facts()` | 319 | 23 lines |
| `_stored_vitals()` | 123 | 21 lines |
| `vital_label()` | 183 | 14 lines |
| `vitals_of()` | 171 | 10 lines |

### `world/weather.py`

| Function | Start | Size |
|---|---:|---:|
| `weather_for_room()` | 454 | 76 lines |
| `normalize_weather()` | 225 | 69 lines |
| `weather_depth()` | 381 | 57 lines |
| `weather_words()` | 554 | 54 lines |
| `advance_weather()` | 661 | 49 lines |
| `ground_after()` | 764 | 38 lines |
| `room_exposure()` | 296 | 30 lines |
| `_resolve()` | 192 | 27 lines |

## FastAPI routes

| Method | Path | Handler | Source |
|---|---|---|---|
| GET | `/` | `index()` | `web/app.py:519` |
| PUT | `/api/active_preset` | `set_active()` | `web/app.py:1743` |
| PUT | `/api/affect_habituation` | `set_affect_habituation()` | `web/app.py:2063` |
| PUT | `/api/agent_models` | `put_agent_models()` | `web/app.py:1433` |
| PUT | `/api/ambience` | `put_ambience()` | `web/app.py:1554` |
| GET | `/api/ambience/library` | `ambience_library()` | `web/app.py:6146` |
| GET | `/api/ambience/search` | `ambience_search()` | `web/app.py:6125` |
| PUT | `/api/attire_beneath` | `set_attire_beneath()` | `web/app.py:2082` |
| POST | `/api/auth/login` | `auth_login()` | `web/auth_routes.py:209` |
| POST | `/api/auth/logout` | `auth_logout()` | `web/auth_routes.py:275` |
| POST | `/api/auth/setup` | `auth_setup()` | `web/auth_routes.py:134` |
| GET | `/api/auth/status` | `auth_status()` | `web/auth_routes.py:124` |
| GET | `/api/auto_promote` | `get_auto_promote()` | `web/app.py:3643` |
| PUT | `/api/auto_promote` | `set_auto_promote()` | `web/app.py:3656` |
| PUT | `/api/backdrops` | `put_backdrops()` | `web/app.py:1544` |
| GET | `/api/bootstrap` | `bootstrap()` | `web/app.py:1327` |
| POST | `/api/characters` | `char_create()` | `web/app.py:2538` |
| POST | `/api/characters/generate` | `char_generate()` | `web/app.py:2515` |
| POST | `/api/characters/import` | `char_import()` | `web/app.py:2563` |
| DELETE | `/api/characters/{cid}` | `char_del()` | `web/app.py:2689` |
| PUT | `/api/characters/{cid}` | `char_edit()` | `web/app.py:2679` |
| GET | `/api/characters/{cid}/export` | `char_export()` | `web/app.py:2671` |
| POST | `/api/characters/{cid}/fill_appearance` | `char_fill_appearance()` | `web/app.py:2659` |
| POST | `/api/characters/{cid}/fill_psychology` | `char_fill_psychology()` | `web/app.py:2630` |
| POST | `/api/characters/{cid}/generate_greeting` | `char_generate_greeting()` | `web/app.py:2614` |
| POST | `/api/characters/{cid}/recover_greetings` | `char_recover_greetings()` | `web/app.py:2604` |
| POST | `/api/characters/{cid}/start` | `character_start_story()` | `web/app.py:2578` |
| POST | `/api/chats` | `chat_new()` | `web/app.py:3046` |
| POST | `/api/chats/import` | `import_chat()` | `persist/chat_archive.py:257` |
| DELETE | `/api/chats/{cid}` | `chat_del()` | `web/app.py:3281` |
| GET | `/api/chats/{cid}` | `chat_get()` | `web/app.py:3311` |
| PUT | `/api/chats/{cid}` | `chat_edit()` | `web/app.py:3144` |
| POST | `/api/chats/{cid}/abort` | `chat_abort()` | `web/app.py:5019` |
| GET | `/api/chats/{cid}/ambience/oneshot/{name}` | `ambience_oneshot()` | `web/app.py:6155` |
| DELETE | `/api/chats/{cid}/ambience/pin` | `ambience_pin_delete()` | `web/app.py:6203` |
| PUT | `/api/chats/{cid}/ambience/pin` | `ambience_pin_put()` | `web/app.py:6184` |
| GET | `/api/chats/{cid}/ambience/pins` | `ambience_pins_get()` | `web/app.py:6179` |
| GET | `/api/chats/{cid}/ambience/{signature}.audio` | `ambience_audio()` | `web/app.py:6109` |
| GET | `/api/chats/{cid}/attire` | `attire_get()` | `web/app.py:4366` |
| PUT | `/api/chats/{cid}/attire` | `attire_put()` | `web/app.py:4377` |
| GET | `/api/chats/{cid}/backdrop/{signature}.png` | `backdrop_image()` | `web/app.py:5949` |
| GET | `/api/chats/{cid}/background_config` | `bg_cfg_get()` | `web/app.py:4549` |
| PUT | `/api/chats/{cid}/background_config` | `bg_cfg_put()` | `web/app.py:4553` |
| POST | `/api/chats/{cid}/characters` | `chat_add_char()` | `web/app.py:3547` |
| DELETE | `/api/chats/{cid}/characters/{ch}` | `chat_del_char()` | `web/app.py:3935` |
| PUT | `/api/chats/{cid}/characters/{ch}/card` | `chat_char_card_put()` | `web/app.py:3945` |
| PUT | `/api/chats/{cid}/characters/{ch}/dialogue_color` | `dialogue_color_put()` | `web/app.py:4250` |
| GET | `/api/chats/{cid}/characters/{ch}/memories` | `mem_list()` | `web/app.py:4770` |
| POST | `/api/chats/{cid}/characters/{ch}/memories` | `mem_add()` | `web/app.py:4906` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/backfill` | `mem_backfill()` | `web/app.py:4876` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/consolidate` | `mem_consolidate()` | `web/app.py:4861` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/coverage` | `mem_coverage()` | `web/app.py:4897` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/export` | `mem_export()` | `web/app.py:4816` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/import` | `mem_import()` | `web/app.py:4827` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/search` | `mem_search()` | `web/app.py:4791` |
| GET | `/api/chats/{cid}/characters/{ch}/memory-context` | `memory_context_preview()` | `web/app.py:4837` |
| PUT | `/api/chats/{cid}/characters/{ch}/position` | `chat_char_position_put()` | `web/app.py:4162` |
| GET | `/api/chats/{cid}/characters/{ch}/private_history` | `ph_get()` | `web/app.py:4231` |
| PUT | `/api/chats/{cid}/characters/{ch}/private_history` | `ph_put()` | `web/app.py:4241` |
| GET | `/api/chats/{cid}/characters/{ch}/relationships` | `relationships_get()` | `web/app.py:4850` |
| GET | `/api/chats/{cid}/dialogue_config` | `dlg_get()` | `web/app.py:4416` |
| PUT | `/api/chats/{cid}/dialogue_config` | `dlg_put()` | `web/app.py:4433` |
| GET | `/api/chats/{cid}/dramatic_irony` | `get_dramatic_irony_feed()` | `web/app.py:3601` |
| GET | `/api/chats/{cid}/export` | `export_chat()` | `persist/chat_archive.py:251` |
| GET | `/api/chats/{cid}/fixed_points` | `fixed_points_list()` | `web/app.py:4716` |
| POST | `/api/chats/{cid}/fixed_points` | `fixed_points_create()` | `web/app.py:4726` |
| DELETE | `/api/chats/{cid}/fixed_points/{anchor_id}` | `fixed_points_delete()` | `web/app.py:4748` |
| GET | `/api/chats/{cid}/frames` | `frames_list()` | `web/app.py:4670` |
| POST | `/api/chats/{cid}/frames` | `frames_create()` | `web/app.py:4674` |
| GET | `/api/chats/{cid}/guest_invites` | `list_guest_invites()` | `web/app.py:3816` |
| POST | `/api/chats/{cid}/guest_invites` | `create_guest_invite()` | `web/app.py:3796` |
| DELETE | `/api/chats/{cid}/guest_invites/{gid}` | `revoke_guest_invite()` | `web/app.py:3820` |
| GET | `/api/chats/{cid}/language` | `chat_language_get()` | `web/app.py:3111` |
| PUT | `/api/chats/{cid}/language` | `chat_language_put()` | `web/app.py:3128` |
| GET | `/api/chats/{cid}/living_world` | `living_world_get()` | `web/app.py:4514` |
| PUT | `/api/chats/{cid}/living_world` | `living_world_put()` | `web/app.py:4537` |
| DELETE | `/api/chats/{cid}/lorebook` | `detach_lore()` | `web/app.py:3272` |
| POST | `/api/chats/{cid}/lorebook` | `bind_lore()` | `web/app.py:3251` |
| GET | `/api/chats/{cid}/lorebooks` | `chat_lorebooks_owned()` | `web/app.py:2166` |
| POST | `/api/chats/{cid}/lorebooks` | `attach_lore()` | `web/app.py:3175` |
| DELETE | `/api/chats/{cid}/lorebooks/{lid}` | `detach_book()` | `web/app.py:3236` |
| PUT | `/api/chats/{cid}/lorebooks/{lid}` | `set_book_enabled()` | `web/app.py:3200` |
| GET | `/api/chats/{cid}/paradox_policy` | `paradox_policy_get()` | `web/app.py:4701` |
| PUT | `/api/chats/{cid}/paradox_policy` | `paradox_policy_put()` | `web/app.py:4705` |
| GET | `/api/chats/{cid}/persona_private_history` | `pph_get()` | `web/app.py:4302` |
| PUT | `/api/chats/{cid}/persona_private_history` | `pph_put()` | `web/app.py:4315` |
| GET | `/api/chats/{cid}/personas` | `chat_list_extra_personas()` | `web/app.py:3661` |
| POST | `/api/chats/{cid}/personas` | `chat_add_persona()` | `web/app.py:3706` |
| DELETE | `/api/chats/{cid}/personas/{pid}` | `chat_del_persona()` | `web/app.py:3732` |
| PUT | `/api/chats/{cid}/personas/{pid}/station` | `chat_persona_station()` | `web/app.py:3671` |
| GET | `/api/chats/{cid}/player_authority` | `player_authority_get()` | `web/app.py:4633` |
| PUT | `/api/chats/{cid}/player_authority` | `player_authority_put()` | `web/app.py:4648` |
| GET | `/api/chats/{cid}/player_view` | `player_view_get()` | `web/app.py:4610` |
| GET | `/api/chats/{cid}/positions` | `chat_positions_get()` | `web/app.py:4095` |
| GET | `/api/chats/{cid}/promises` | `get_promise_ledger()` | `web/app.py:3605` |
| GET | `/api/chats/{cid}/promotable` | `list_promotable_presences()` | `web/app.py:3597` |
| POST | `/api/chats/{cid}/promotions/confirm` | `confirm_promotion()` | `web/app.py:3623` |
| POST | `/api/chats/{cid}/promotions/draft` | `draft_promotion()` | `web/app.py:3609` |
| GET | `/api/chats/{cid}/story_view` | `story_view_get()` | `web/app.py:4579` |
| GET | `/api/chats/{cid}/style_guide` | `style_guide_get()` | `web/app.py:4399` |
| PUT | `/api/chats/{cid}/style_guide` | `style_guide_put()` | `web/app.py:4405` |
| GET | `/api/chats/{cid}/survival` | `survival_get()` | `web/app.py:4003` |
| PUT | `/api/chats/{cid}/survival` | `survival_put()` | `web/app.py:4008` |
| POST | `/api/chats/{cid}/turns` | `turn_new()` | `web/app.py:4959` |
| POST | `/api/chats/{cid}/turns/{idx}/player_input` | `submit_extra_player_input()` | `web/app.py:3746` |
| GET | `/api/chats/{cid}/viewers` | `viewers_get()` | `web/app.py:4625` |
| GET | `/api/chats/{cid}/vitals` | `chat_vitals_get()` | `web/app.py:4060` |
| GET | `/api/chats/{cid}/world` | `world_get()` | `web/app.py:4320` |
| PUT | `/api/chats/{cid}/world` | `world_put()` | `web/app.py:4330` |
| GET | `/api/default_prompts` | `default_prompts()` | `web/app.py:1673` |
| PUT | `/api/director_fanout_mode` | `set_director_fanout_mode()` | `web/app.py:2039` |
| PUT | `/api/exemplars` | `put_exemplars()` | `web/app.py:1513` |
| GET | `/api/extensions` | `extensions_list()` | `web/app.py:1760` |
| POST | `/api/extensions/install` | `extension_install()` | `web/app.py:1782` |
| GET | `/api/extensions/ui.css` | `extensions_ui_css()` | `web/app.py:1960` |
| GET | `/api/extensions/ui.js` | `extensions_ui()` | `web/app.py:1951` |
| GET | `/api/extensions/updates` | `extension_updates()` | `web/app.py:1803` |
| DELETE | `/api/extensions/{eid}` | `extension_remove()` | `web/app.py:1824` |
| GET | `/api/extensions/{eid}/asset/{path:path}` | `extension_asset()` | `web/app.py:2015` |
| POST | `/api/extensions/{eid}/disable` | `extension_disable()` | `web/app.py:1832` |
| DELETE | `/api/extensions/{eid}/document` | `extension_document_delete()` | `web/app.py:1928` |
| GET | `/api/extensions/{eid}/document` | `extension_document_get()` | `web/app.py:1896` |
| PUT | `/api/extensions/{eid}/document` | `extension_document_put()` | `web/app.py:1908` |
| DELETE | `/api/extensions/{eid}/documents` | `extension_documents_delete()` | `web/app.py:1938` |
| GET | `/api/extensions/{eid}/documents` | `extension_documents_list()` | `web/app.py:1875` |
| GET | `/api/extensions/{eid}/documents/verify` | `extension_documents_verify()` | `web/app.py:1886` |
| POST | `/api/extensions/{eid}/enable` | `extension_enable()` | `web/app.py:1774` |
| GET | `/api/extensions/{eid}/state` | `extension_state()` | `web/app.py:1837` |
| GET | `/api/extensions/{eid}/ui.css` | `extension_ui_css_one()` | `web/app.py:1982` |
| GET | `/api/extensions/{eid}/ui.js` | `extension_ui_one()` | `web/app.py:1970` |
| POST | `/api/extensions/{eid}/update` | `extension_update()` | `web/app.py:1814` |
| POST | `/api/guest/input` | `guest_input()` | `web/app.py:3910` |
| GET | `/api/guest/state` | `guest_state()` | `web/app.py:3842` |
| PUT | `/api/image_model` | `put_image_model()` | `web/app.py:1491` |
| POST | `/api/join` | `join_with_code()` | `web/app.py:3826` |
| GET | `/api/language-packs` | `language_packs_get()` | `web/app.py:3064` |
| GET | `/api/language-packs/{language_id}/ui` | `language_pack_ui()` | `web/app.py:3085` |
| DELETE | `/api/lore_entries/{eid}` | `lore_entry_delete()` | `web/app.py:3039` |
| PUT | `/api/lore_entries/{eid}` | `lore_entry_edit()` | `web/app.py:2967` |
| DELETE | `/api/lore_gen_jobs/{job_id}` | `lorebook_generate_discard()` | `web/app.py:2322` |
| POST | `/api/lore_gen_jobs/{job_id}/resume` | `lorebook_generate_resume()` | `web/app.py:2304` |
| DELETE | `/api/lorebook_links/{link_id}` | `lorebook_link_delete()` | `web/app.py:2262` |
| PUT | `/api/lorebook_links/{link_id}` | `lorebook_link_update()` | `web/app.py:2248` |
| POST | `/api/lorebooks` | `lore_create()` | `web/app.py:2796` |
| POST | `/api/lorebooks/import` | `lore_import()` | `web/app.py:2358` |
| DELETE | `/api/lorebooks/{lid}` | `lore_delete()` | `web/app.py:2888` |
| GET | `/api/lorebooks/{lid}` | `lore_get()` | `web/app.py:2776` |
| PUT | `/api/lorebooks/{lid}` | `lore_edit()` | `web/app.py:2818` |
| POST | `/api/lorebooks/{lid}/apply_plan` | `lorebook_apply_plan()` | `web/app.py:2331` |
| POST | `/api/lorebooks/{lid}/entries` | `lore_entry_create()` | `web/app.py:2938` |
| GET | `/api/lorebooks/{lid}/export` | `lore_export()` | `web/app.py:2894` |
| POST | `/api/lorebooks/{lid}/generate` | `lore_generate()` | `web/app.py:2924` |
| GET | `/api/lorebooks/{lid}/generate_job` | `lorebook_generate_job()` | `web/app.py:2293` |
| POST | `/api/lorebooks/{lid}/generate_plan` | `lorebook_generate_plan()` | `web/app.py:2267` |
| GET | `/api/lorebooks/{lid}/links` | `lorebook_links_get()` | `web/app.py:2221` |
| POST | `/api/lorebooks/{lid}/links` | `lorebook_link_create()` | `web/app.py:2226` |
| POST | `/api/lorebooks/{lid}/move` | `lorebook_move()` | `web/app.py:2148` |
| POST | `/api/lorebooks/{lid}/reinterpret` | `lore_reinterpret_route()` | `web/app.py:2911` |
| POST | `/api/lorebooks/{lid}/reorder` | `lorebook_reorder()` | `web/app.py:2157` |
| GET | `/api/maintenance/checkpoints` | `maintenance_checkpoints()` | `web/app.py:2105` |
| POST | `/api/maintenance/checkpoints/compact` | `maintenance_compact()` | `web/app.py:2121` |
| PUT | `/api/max_output_tokens` | `put_max_output_tokens()` | `web/app.py:1640` |
| DELETE | `/api/memories/{mid}` | `mem_del()` | `web/app.py:4953` |
| PUT | `/api/memories/{mid}` | `mem_edit()` | `web/app.py:4932` |
| GET | `/api/memory/embeddings` | `memory_embeddings_status()` | `web/app.py:1464` |
| POST | `/api/memory/embeddings/rebuild` | `memory_embeddings_rebuild()` | `web/app.py:1479` |
| GET | `/api/nsfw` | `get_nsfw()` | `web/app.py:2030` |
| PUT | `/api/nsfw` | `set_nsfw()` | `web/app.py:2034` |
| GET | `/api/openrouter/endpoints` | `get_openrouter_endpoints()` | `web/app.py:1598` |
| PUT | `/api/openrouter_routing` | `put_openrouter_routing()` | `web/app.py:1584` |
| POST | `/api/personas` | `persona_create()` | `web/app.py:2718` |
| POST | `/api/personas/generate` | `persona_generate()` | `web/app.py:2696` |
| POST | `/api/personas/import` | `persona_import()` | `web/app.py:2738` |
| DELETE | `/api/personas/{pid}` | `persona_del()` | `web/app.py:2770` |
| PUT | `/api/personas/{pid}` | `persona_edit()` | `web/app.py:2761` |
| GET | `/api/personas/{pid}/export` | `persona_export()` | `web/app.py:2752` |
| POST | `/api/personas/{pid}/fill_appearance` | `persona_fill_appearance()` | `web/app.py:2666` |
| PUT | `/api/prompt_presets` | `save_preset()` | `web/app.py:1684` |
| POST | `/api/prompt_presets/import` | `import_preset()` | `web/app.py:1720` |
| DELETE | `/api/prompt_presets/{name}` | `del_preset()` | `web/app.py:1734` |
| GET | `/api/prompt_presets/{name}/export` | `export_preset()` | `web/app.py:1711` |
| POST | `/api/providers` | `add_provider()` | `web/app.py:2414` |
| DELETE | `/api/providers/{pid}` | `del_provider()` | `web/app.py:2493` |
| PUT | `/api/providers/{pid}` | `put_provider()` | `web/app.py:2421` |
| GET | `/api/providers/{pid}/image_models` | `image_models()` | `web/app.py:2505` |
| GET | `/api/providers/{pid}/models` | `models()` | `web/app.py:2498` |
| PUT | `/api/providers/{pid}/prompt_cache` | `put_provider_prompt_cache()` | `web/app.py:2448` |
| PUT | `/api/reasoning_effort` | `put_reasoning_effort()` | `web/app.py:1610` |
| POST | `/api/steps/{sid}/activate` | `step_activate()` | `web/app.py:5756` |
| POST | `/api/steps/{sid}/edit` | `step_edit()` | `web/app.py:5746` |
| POST | `/api/steps/{sid}/reroll` | `step_reroll()` | `web/app.py:5699` |
| DELETE | `/api/turns/{tid}` | `turn_del()` | `web/app.py:5769` |
| GET | `/api/turns/{tid}/ambience` | `turn_ambience()` | `web/app.py:6059` |
| POST | `/api/turns/{tid}/ambience` | `turn_ambience_resolve()` | `web/app.py:6076` |
| GET | `/api/turns/{tid}/backdrop` | `turn_backdrop()` | `web/app.py:5906` |
| POST | `/api/turns/{tid}/backdrop` | `turn_backdrop_generate()` | `web/app.py:5921` |
| POST | `/api/turns/{tid}/branch` | `turn_branch()` | `web/app.py:5023` |
| PUT | `/api/turns/{tid}/input` | `edit_input()` | `web/app.py:5431` |
| GET | `/api/turns/{tid}/narration` | `turn_narration_variants()` | `web/app.py:5516` |
| POST | `/api/turns/{tid}/narration` | `turn_narration_select()` | `web/app.py:5537` |
| GET | `/api/turns/{tid}/pipeline` | `pipeline_get()` | `web/app.py:5561` |
| PUT | `/api/turns/{tid}/prose` | `edit_prose()` | `web/app.py:5446` |
| POST | `/api/turns/{tid}/reroll` | `turn_reroll()` | `web/app.py:5630` |
| POST | `/api/turns/{tid}/rerun` | `turn_rerun()` | `web/app.py:5640` |
| POST | `/api/turns/{tid}/resume` | `turn_resume()` | `web/app.py:5667` |
| GET | `/api/ui` | `ui_catalog_get()` | `web/app.py:3075` |
| PUT | `/api/ui-language` | `ui_language_put()` | `web/app.py:3100` |
| GET | `/api/updates/check` | `updates_check()` | `web/app.py:2097` |
| POST | `/api/updates/install` | `updates_install()` | `web/app.py:2101` |
| GET | `/guest` | `guest_page()` | `web/app.py:511` |
| GET | `/login` | `login_page()` | `web/app.py:523` |

## Database tables

| Table | Columns |
|---|---|
| `schema_meta` | `key` |
| `providers` | `id`, `name`, `kind`, `base_url`, `api_key`, `enabled` |
| `settings` | `key`, `value` |
| `characters` | `id`, `name`, `sheet`, `source`, `created`, `resource_uid` |
| `personas` | `id`, `name`, `sheet`, `source`, `resource_uid` |
| `lorebooks` | `id`, `name`, `chat_id`, `origin_id`, `book_type`, `summary`, `resource_uid`, `parent_id`, `scope_world_id`, `scope_location_id`, `inheritance_mode`, `sort_order`, `anchor_entity_id`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `retired_turn_id` |
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
| `world_entities` | `entity_id`, `chat_id`, `kind`, `subtype`, `name`, `payload`, `created_turn_id`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `retired_turn_id` |
| `world_placements` | `chat_id`, `subject_id`, `relation`, `container_id`, `detail` |
| `world_conditions` | `condition_id`, `chat_id`, `subject_id`, `kind`, `started_at`, `expires_at`, `next_tick`, `payload`, `active` |
| `scheduled_events` | `event_id`, `chat_id`, `due_at`, `kind`, `location_id`, `payload`, `seed`, `status` |
| `room_registry` | `chat_id`, `room_uid`, `owning_book_id`, `parent_entity`, `name`, `aliases`, `payload`, `created_turn_id`, `retired_turn_id` |
| `fiction_worlds` | `world_id`, `chat_id`, `parent_world_id`, `name`, `kind`, `payload`, `created_turn_id`, `retired_turn_id` |
| `fiction_locations` | `location_id`, `chat_id`, `world_id`, `parent_location_id`, `kind`, `name`, `payload` |
| `transit_edges` | `edge_id`, `chat_id`, `from_world_id`, `from_location_id`, `to_world_id`, `to_location_id`, `kind`, `payload` |

## Frontend JavaScript

### `static/js/ambience.js` (1049 lines)

Sections: Room ambience (`:2`); seamless looping (`:214`); one-shots (`:689`); the ambience panel (`:738`); the mix (`:756`).

Declared functions: `ambienceStored()`, `ambienceElement()`, `entryAudios()`, `ambiencePlayers()`, `applyAmbienceMute()`, `setAmbienceVolume()`, `ambienceLevel()`, `setLayerGain()`, `toggleAmbienceMute()`, `ambienceFadeMix()`, `armSeamlessLoop()`, `crossLoop()`, `retireEntries()`, `stopAmbience()`, `playAmbience()`, `armAmbienceUnlock()`, `ambienceWorking()`, `awaitAmbience()`, `resolveAmbience()`, `ambienceForTurn()`, `rerollAmbience()`, `ambienceOnVisibleTurn()`, `ambienceResetForRender()`, `updateAmbienceBtn()`, `playAmbienceOneshot()`, `ambienceCandidateRow()`, `ambienceLayerRow()`, `ambienceMixPanel()`, `openAmbiencePanel()`, `toggleAmbience()`, `syncAmbience()`.

### `static/js/app.js` (1063 lines)

Sections: Boot & sidebar (`:1`); and then nothing showed the report, so a host who installed a pack got (`:18`); New chat wizard (`:267`); NSFW (`:748`); Composer (`:776`); Init (`:854`); Embedding reconciler progress (`:914`).

Declared functions: `boot()`, `renderSide()`, `syncExtensionTabs()`, `renderChatSidebar()`, `newChatWizard()`, `renderWizardChoice()`, `storyLanguagePacks()`, `defaultStoryLanguage()`, `wizardState()`, `wizardFromScratch()`, `renderWizardPersona()`, `renderWizardCharacters()`, `renderWizardScenario()`, `runWizard()`, `renderCharacterSidebar()`, `renderPersonaSidebar()`, `renderLegacyLoreSidebar()`, `updateNSFWBtn()`, `toggleNSFW()`, `resizeComposer()`, `erCard()`, `erDismiss()`, `erPoll()`, `erWatch()`, `erOfferRebuild()`.

### `static/js/backdrops.js` (430 lines)

Sections: Scene backdrops (`:2`).

Declared functions: `backdropLayers()`, `backdropLuminance()`, `applyBackdropContrast()`, `releaseBackdropLayer()`, `clearBackdrop()`, `showBackdrop()`, `backdropWorking()`, `awaitBackdrop()`, `generateBackdrop()`, `backdropForTurn()`, `backdropOnVisibleTurn()`, `backdropResetForRender()`, `updateBackdropBtn()`, `toggleBackdrops()`, `syncBackdrops()`.

### `static/js/chat.js` (2911 lines)

Sections: The turn being read (`:1`); Colouring who spoke (`:172`); `dialogue_log` is committed per turn and arrives as `turn.speech` -- and (`:175`); Flipping between rerolls of the newest beat (`:978`); Pipeline drawer: reading a step through a lens (`:1292`); Pipeline drawer (`:1616`); Relationship viewer (`:1986`); Memory browser (`:2065`); Private history (`:2853`).

Declared functions: `observeVisibleTurn()`, `openChat()`, `foldTypography()`, `decodeProseEntities()`, `splitEmphasis()`, `appendEmphasized()`, `quoteBody()`, `quotedRegions()`, `speechSpans()`, `paintProse()`, `proseEl()`, `renderFrameBar()`, `switchFrame()`, `updateChatScopedButtons()`, `renderChat()`, `branchTurn()`, `editTurnInput()`, `editTurnProse()`, `liveReset()`, `friendlyPhase()`, `turnStatusStart()`, `turnStatusSet()`, `turnStatusStop()`, `_streamOn()`, `liveFlush()`, `liveAppend()`, `liveStep()`, `handleEvt()`, `showNarrationEarly()`, `clearNarrationEarly()`, `_mountRerollNav()`, `_paintRerollCount()`, `showRerollVariant()`, `abortActiveRun()`, `runStream()`, `confirmCheckpointRestore()`, `runReroll()`, `rerollTurn()`, `exportChat()`, `importChatModal()`, `perceiverViews()`, `loopMindIds()`, `specialistIds()`, `stepLenses()`, `perceiverLabel()`, `facetBadge()`, `lensLabel()`, `renderLensBar()`, `lensSlice()`, `specialistSlice()`, `perceiverSlice()`, `mindSlice()`, `keySlice()`, `renderEngineNotes()`, `openPipeline()`, `relMeter()`, `relationshipModal()`, `memModal()`, `exportCharacterMemories()`, `importCharacterMemoriesModal()`, `memQS()`, `memCharId()`, `loadMemoryBrowse()`, `getMemUI()`, `renderMemorySummary()`, `sortedMems()`, `renderMemoryList()`, `memoryCard()`, `fieldWrap()`, `reloadMemView()`, `runMemorySearch()`, `showNewMemoryForm()`, `checkMemoryCoverage()`, `backfillMemoryEras()`, `consolidateMemories()`, `previewMemoryContext()`, `chatPH()`, `personaPH()`.

### `static/js/chime.js` (179 lines)

Sections: Turn-completion chime (`:2`); Which other waits are worth a chime (`:110`).

Declared functions: `chimeContext()`, `chimeArm()`, `chimePlay()`, `chimeWatches()`, `chimeWorkFinished()`, `chimeSetMuted()`, `toggleChimeMute()`, `updateChimeBtn()`.

### `static/js/components.js` (992 lines)

Sections: Modal (`:38`); Book covers (`:54`); confirm()/prompt() replacements (`:167`); Toasts (`:288`); Background tasks (`:316`); Form helpers (`:402`); Model picker (`:842`); made for every combobox that already has a provider saved -- opened its (`:872`).

Declared functions: `txt()`, `el()`, `coverOfRow()`, `coverOfTitle()`, `modal()`, `modalOwnership()`, `closeModal()`, `closeAllModals()`, `_confirmOverlay()`, `confirmModal()`, `promptModal()`, `promptModalWithToggle()`, `toastHost()`, `toast()`, `renderActivity()`, `elapsedLabel()`, `activityTicking()`, `backgroundTask()`, `buttonTask()`, `loadingBlock()`, `emptyState()`, `fText()`, `fArea()`, `fSelect()`, `fNum()`, `fLineList()`, `fStrList()`, `fCoveragePicker()`, `fAttireGarments()`, `fList()`, `fAbilities()`, `fTraits()`, `fValues()`, `fBeliefs()`, `fCopingStrategies()`, `fAssociations()`, `fGoals()`, `fSenses()`, `fLatent()`, `fExtraParts()`, `fPronouns()`, `phEditor()`, `fetchModels()`, `fetchImageModels()`, `modelCombobox()`, `emitChange()`, `load()`, `showDD()`.

### `static/js/editors.js` (937 lines)

Sections: Carrying the fields an editor has no widget for (`:63`); Background-character promotion (`:767`); Import (file upload) (`:819`); Generate (`:890`); Lorebook generate (`:908`); Export (`:925`).

Declared functions: `appearanceFillButton()`, `defaultCharacterSheet()`, `carryUnpresentedFields()`, `greetingCarousel()`, `quickStartModal()`, `charEditor()`, `personaEditor()`, `promotionReviewModal()`, `promoteBackgroundPresence()`, `importModal()`, `generateModal()`, `generateLoreModal()`, `exportCharacter()`, `exportPersona()`, `exportLorebook()`.

### `static/js/extensions.js` (657 lines)

Sections: Extension host (`:2`); Registration attribution (`:20`); Failure containment (`:56`); ES module entries (`:86`); Registration surface (`:177`); Notices (`:222`); Host services (`:368`); The chat lifecycle, as a declared contract (`:397`); Host-internal accessors (`:479`); Hot load / unload (`:605`).

### `static/js/i18n.js` (114 lines)

Declared functions: `translate()`, `apply()`.

### `static/js/lorebooks.js` (3688 lines)

Sections: Library sidebar (`:252`); Data loading (`:459`); Workspace (`:556`); Book metadata and tree operations (`:1162`); Entry editor (`:1666`); Lorebook relationships (`:2410`); Advanced generator (`:2861`); Interrupted-generation recovery (`:3081`).

Declared functions: `loreBookTypeIcon()`, `loreLinkTypes()`, `normalizeLoreBook()`, `loreOwnershipKey()`, `loreBooksByParent()`, `loreBookMatches()`, `loreVisibleIds()`, `loreBookLabel()`, `parseStoredJSON()`, `loreField()`, `loreSelect()`, `loreBookOptions()`, `renderLoreLibrarySidebar()`, `renderNode()`, `loadLoreWorkspaceData()`, `collectLoreLinkTargets()`, `loreWorkspaceVisible()`, `renderLoreWorkspaceBody()`, `openLoreWorkspace()`, `renderLoreInspector()`, `selectTab()`, `buildLoreWorkspace()`, `renderWorkspaceTree()`, `renderNode()`, `renderTreeList()`, `renderLoreBookEditor()`, `moveLoreBook()`, `reorderLoreBook()`, `promoteLoreBook()`, `demoteLoreBook()`, `createSiblingLoreBook()`, `createLoreBookDialog()`, `refreshLoreUI()`, `renderLoreEntries()`, `renderList()`, `buildLoreEntryCard()`, `splitNumberList()`, `reinterpretLoreBook()`, `generateLoreEntriesPrompt()`, `buildDirectLoreRequest()`, `renderRelationshipOverview()`, `renderLoreRelationshipEditor()`, `renderRelationshipList()`, `showNewRelationshipForm()`, `renderLoreGenerator()`, `adoptGeneratorPlan()`, `generatorPlanMessage()`, `loreGenAgo()`, `refreshLoreGenRecovery()`, `normalizeGeneratorPlan()`, `renderLorePlanPreview()`, `renderOperations()`, `planStat()`, `renderAnalysisSection()`, `addPlanGroup()`, `stripPlanUIFields()`, `acceptedGeneratorPlan()`.

### `static/js/settings.js` (3798 lines)

Sections: Chat tool modals (`:1`); Condition tab (`:696`); Survival tracker (`:756`); Character relocation (`:1068`); API connections (`:1801`); Software updates (host-only; git fast-forward from GitHub origin) (`:3026`); Legacy checkpoint conversion (host-only maintenance) (`:3058`); Prompts (`:3292`); and be able to load that pack's own sheets to edit, rather than (`:3303`); Extensions (`:3470`).

Declared functions: `frameQuery()`, `selectTab()`, `dialogueColorControl()`, `save()`, `renderCastTab()`, `renderConditionTab()`, `hydrateConditionTab()`, `vitalMeter()`, `syncVitalsGutterNow()`, `syncVitalsGutter()`, `hideVitalsHud()`, `vitalsBlock()`, `refreshVitalsHud()`, `clearVitalsHud()`, `hydrateCastLocations()`, `castRoomLabel()`, `castRoomSelect()`, `renderLorebooksTab()`, `renderBookNode()`, `renderMultiplayerTab()`, `renderFramesTab()`, `renderFramesListPanel()`, `renderPersonaStationingPanel()`, `renderParadoxPanel()`, `renderBackgroundPresencesPanel()`, `renderGuestInvitePanel()`, `renderInsightsTab()`, `renderDramaticIronyPanel()`, `renderPromiseLedgerPanel()`, `embeddingBankBlock()`, `modelRecommendationsBlock()`, `renderFirstRunProviderSetup()`, `preferredBackdropSize()`, `renderFullApiSettings()`, `propagateToFollowers()`, `renderUpdateChecking()`, `renderUpdateError()`, `checkpointCompactionBlock()`, `renderUpdateStatus()`, `runUpdateInstall()`, `renderUpdateDone()`, `openPromptsModal()`, `reopenPromptsIfRequested()`, `extensionTrustNote()`, `extensionCapabilitySummary()`, `extensionSettingsSections()`, `openExtensionsMenu()`.

### `static/js/theme-init.js` (181 lines)

Declared functions: `readStored()`, `writeStored()`, `normaliseTheme()`, `normaliseProseSize()`, `applyTheme()`, `applyProseSize()`, `normaliseEffects()`, `applyEffects()`, `syncPageHidden()`.

### `static/js/themes.js` (159 lines)

Declared functions: `themePreview()`, `openAppearanceSettings()`.

### `static/js/utils.js` (346 lines)

Sections: API (`:235`); Download (`:325`); Card authoring warnings (`:334`).

Declared functions: `t()`, `watchUILanguage()`, `localizeDocument()`, `memoryCategories()`, `memoryProvenance()`, `hasDefaultModel()`, `safeId()`, `splitCL()`, `numOr()`, `taggedError()`, `api()`, `streamPost()`, `downloadJSON()`, `showCardWarnings()`.

### `static/js/weather-fx.js` (548 lines)

Sections: Weather effects (`:2`); the tile (`:178`); the layers (`:251`); lifecycle (`:329`); lightning (`:387`); the exact cost this file exists to avoid. Rain has no wrapper and no (`:527`).

Declared functions: `weatherFxReduced()`, `weatherFxEffectsOff()`, `weatherFxSupported()`, `weatherFxHost()`, `weatherFxRandom()`, `weatherFxTile()`, `weatherFxReach()`, `weatherFxBuild()`, `weatherFxClearLayers()`, `weatherFxStop()`, `weatherFxVisible()`, `weatherFxApply()`, `weatherFxStormy()`, `weatherFxScheduleFlash()`, `weatherFxFlash()`, `weatherFxOpenSky()`, `weatherFxBolt()`, `weatherFxThunder()`, `weatherFxForTurn()`.
