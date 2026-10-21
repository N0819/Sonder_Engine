# Generated Code Map

> Regenerate with `python tools/generate_code_map.py`. Do not hand-edit this file.

## Python modules

| Module | Lines | Purpose | Local dependencies |
|---|---:|---|---|
| `agents/__init__.py` | 100 | Backward-compatible facade for the role-specific agent package. | `agents.background`, `agents.character`, `agents.common`, `agents.director`, `agents.loops`, `agents.mapping`, `agents.narration`, `agents.perception`, `agents.runtime`, `agents.storage`, `story.scene` |
| `agents/background.py` | 3253 |  | `agents.common`, `core.db`, `llm.prompts`, `llm.schemas`, `persist.commit`, `story.character_schema`, `story.scene`, `world.background_claims`, `world.spatial` |
| `agents/character.py` | 5104 | Private character decision agent. | `agents`, `agents.character_evidence`, `agents.common`, `agents.impossible_knowledge`, `core.db`, `core.frames`, `llm.schemas`, `mind`, `mind.affect`, `mind.memory`, `mind.memory_judge`, `mind.psychology_runtime`, `mind.theory_of_mind`, `story`, `story.character_schema`, `story.scene`, `world.gaps`, `world.place_purpose`, `world.spatial`, `world.survival` |
| `agents/character_bare.py` | 1168 |  | `agents.common`, `llm.prompts`, `mind` |
| `agents/character_evidence.py` | 146 |  | — |
| `agents/character_tools.py` | 732 |  | `core.db` |
| `agents/common.py` | 12969 | Shared normalization, lore, delivery, and perception helpers. | `core.db`, `core.pipeline_context`, `llm.llm_quality`, `llm.prompts`, `llm.providers`, `llm.schemas`, `mind.memory`, `mind.theory_of_mind`, `persist.commit`, `story`, `story.character_schema`, `story.provenance_text`, `story.scene`, `world`, `world.spatial` |
| `agents/composer.py` | 7346 |  | `agents.common`, `core.pipeline_context`, `story.provenance_text`, `story.scene`, `world.spatial` |
| `agents/director.py` | 7987 | Scene establishment, player interpretation, and objective resolution. | `agents`, `agents.common`, `agents.director_contact`, `agents.director_evidence`, `agents.director_fanout`, `agents.director_floors`, `agents.director_lingua`, `agents.director_movement`, `agents.director_reconcile`, `agents.director_scopes`, `agents.director_views`, `core.db`, `llm`, `llm.prompts`, `llm.providers`, `llm.schemas`, `mind.memory`, `story`, `story.attire`, `story.character_schema`, `story.scene`, `world.causality`, `world.mechanics`, `world.paradox`, `world.spatial`, `world.survival` |
| `agents/director_contact.py` | 611 |  | `agents.common`, `story.character_schema`, `world.spatial` |
| `agents/director_evidence.py` | 4107 |  | `agents.common`, `agents.director_lingua`, `agents.director_scopes`, `llm`, `story.character_schema`, `world.spatial` |
| `agents/director_fanout.py` | 1121 |  | `agents.common`, `agents.director_evidence`, `agents.director_scopes`, `core.db`, `story.character_schema`, `world.spatial`, `world.survival` |
| `agents/director_floors.py` | 2548 |  | `agents.common`, `agents.director_lingua`, `agents.director_movement`, `story.character_schema`, `story.scene`, `world.mechanics`, `world.spatial` |
| `agents/director_layout.py` | 594 |  | — |
| `agents/director_lingua.py` | 29 |  | — |
| `agents/director_movement.py` | 3361 |  | `agents.director_lingua`, `story.character_schema`, `world.mechanics`, `world.spatial` |
| `agents/director_prose.py` | 4570 |  | `agents.director_fanout`, `agents.director_scopes`, `core.db`, `llm`, `llm.prompts`, `llm.providers`, `llm.schemas` |
| `agents/director_reconcile.py` | 559 |  | `agents.common`, `agents.director_evidence`, `agents.director_scopes`, `core.db`, `llm.schemas`, `story`, `world.spatial` |
| `agents/director_repair.py` | 1687 |  | `core.db`, `llm`, `llm.prompts` |
| `agents/director_rooms.py` | 2986 |  | — |
| `agents/director_scopes.py` | 608 |  | `agents.director_lingua`, `agents.director_views`, `core.db`, `world.survival` |
| `agents/director_views.py` | 760 |  | `agents.common`, `story.character_schema`, `story.scene`, `world.background_claims` |
| `agents/dramaturge.py` | 469 |  | `core.db`, `core.logging_utils`, `story.room_proposals` |
| `agents/impossible_knowledge.py` | 232 |  | `agents.common`, `core.db`, `story.character_schema` |
| `agents/loops.py` | 1975 | Reaction loops, interaction rounds, and deterministic micro-perception. | `agents`, `agents.character`, `agents.common`, `core.db`, `core.pipeline_context`, `story.character_schema`, `story.scene`, `world.spatial` |
| `agents/mapping.py` | 713 | Lore routing, cached recall, and retrieval staging. | `agents.common`, `core.db`, `mind.memory`, `story.scene`, `world.spatial` |
| `agents/narration.py` | 3196 | Player-facing narration agent. | `agents`, `agents.common`, `core.db`, `llm.prompts`, `llm.schemas`, `story`, `story.character_schema`, `story.scene`, `world.spatial`, `world.weather` |
| `agents/offscreen_beat.py` | 490 |  | — |
| `agents/perception.py` | 9299 | Opening, action-onset, and outcome observer views. | `agents`, `agents.common`, `core.db`, `core.pipeline_context`, `mind`, `story`, `story.character_schema`, `story.scene`, `world.beat_ledger`, `world.scene_memo`, `world.spatial` |
| `agents/runtime.py` | 2054 | Pipeline plans, dispatch, streaming, cancellation, resume, and reruns. | `agents.background`, `agents.character`, `agents.common`, `agents.director`, `agents.loops`, `agents.mapping`, `agents.narration`, `agents.perception`, `agents.storage`, `core.db`, `core.pipeline_context`, `llm.providers`, `persist.checkpoints`, `persist.commit`, `story.character_schema`, `story.scene` |
| `agents/storage.py` | 103 | Step and active-variant persistence helpers. | `core.db`, `persist.steps` |
| `agents/story_planner.py` | 3485 |  | `core.db`, `core.logging_utils`, `story.room_calls` |
| `core/__init__.py` | 6 |  | — |
| `core/code_version.py` | 205 |  | `core.paths` |
| `core/db.py` | 3138 | SQLite schema, migrations, connection management, transactions, and key/value world access. | `core.paths` |
| `core/frames.py` | 299 |  | `core.db` |
| `core/jobs.py` | 520 |  | `core.logging_utils` |
| `core/logging_utils.py` | 122 | Structured timing and observability helpers. | — |
| `core/outofband.py` | 392 |  | `core.logging_utils` |
| `core/paths.py` | 32 |  | — |
| `core/pipeline_context.py` | 603 | Typed mutable context passed through a turn pipeline. | `core.db` |
| `core/updates.py` | 399 |  | `core.paths` |
| `dressing/__init__.py` | 6 |  | — |
| `dressing/ambience.py` | 2103 |  | `core`, `core.db`, `core.paths`, `dressing.backdrops`, `world.weather` |
| `dressing/backdrops.py` | 1782 |  | `core`, `core.db`, `core.logging_utils`, `core.paths`, `persist.steps`, `world.day_cycle`, `world.spatial`, `world.weather` |
| `llm/__init__.py` | 6 |  | — |
| `llm/decisions.py` | 325 |  | `core.db` |
| `llm/json_mend.py` | 302 |  | — |
| `llm/llm_quality.py` | 2124 | Strict JSON parsing, schema validation, and model-assisted repair. | `core.pipeline_context`, `llm.prompts`, `llm.providers`, `llm.schemas` |
| `llm/prompt_cache.py` | 79 | Provider-specific prompt-cache helpers. | `llm.providers` |
| `llm/prompts.py` | 710 | Default system prompts and prompt preset access. | `core.db` |
| `llm/providers.py` | 5837 | Provider selection, retries, streaming, cancellation, model listing, and embeddings. | `core.db`, `core.logging_utils` |
| `llm/research_providers.py` | 247 |  | `core.db` |
| `llm/schemas.py` | 6934 | Pydantic output contracts and semantic validation for agent payloads. | — |
| `mind/__init__.py` | 6 |  | — |
| `mind/affect.py` | 2600 |  | `mind.theory_of_mind` |
| `mind/affect_appraisal.py` | 282 |  | `llm`, `llm.prompts` |
| `mind/affect_mix.py` | 844 |  | — |
| `mind/affect_pass.py` | 788 |  | `llm.prompts`, `mind` |
| `mind/canon_provenance.py` | 398 |  | — |
| `mind/character_jev.py` | 1139 |  | `llm`, `llm.prompts`, `mind.affect_appraisal` |
| `mind/knowledge_circles.py` | 134 |  | `core.db` |
| `mind/memory.py` | 154 | Facade re-exporting every mind.memory_* name; holds no domain code of its own. | `core`, `core.db`, `core.logging_utils`, `llm.prompts`, `llm.providers`, `mind.memory_common`, `mind.memory_context`, `mind.memory_inference`, `mind.memory_jev`, `mind.memory_links`, `mind.memory_lore_entries`, `mind.memory_lorebooks`, `mind.memory_read`, `mind.memory_relationships`, `mind.memory_retrieval`, `mind.memory_routes`, `mind.memory_snapshot`, `mind.memory_summaries`, `mind.memory_time`, `mind.memory_vectors`, `mind.memory_write`, `mind.theory_of_mind` |
| `mind/memory_common.py` | 293 | Leaf helpers shared by every memory domain: vocabularies, blob/vector codecs, FTS query, cosine. | `core.db` |
| `mind/memory_context.py` | 898 | The character memory payload: where retrieval, summaries and active state become one context. | `core.db`, `llm.prompts`, `llm.providers`, `mind.memory_common`, `mind.memory_jev`, `mind.memory_links`, `mind.memory_read`, `mind.memory_retrieval`, `mind.memory_summaries`, `mind.memory_time`, `mind.memory_write` |
| `mind/memory_inference.py` | 159 | Belief confidence at mint and at abandonment, and reconciliation across a mind's inferences. | `core.db`, `mind.memory_write`, `mind.theory_of_mind` |
| `mind/memory_jev.py` | 603 |  | `mind.memory_common`, `mind.memory_read`, `mind.memory_retrieval`, `mind.memory_write` |
| `mind/memory_judge.py` | 430 |  | `core.db`, `core.logging_utils`, `llm.prompts`, `llm.providers` |
| `mind/memory_links.py` | 289 |  | `mind.memory_common`, `mind.memory_read`, `mind.memory_write` |
| `mind/memory_lore_entries.py` | 867 | Lore entries: add/update/delete, embedding stamps and health, search_lore, per-character knowledge scoping. | `core.db`, `core.logging_utils`, `llm.providers`, `mind.memory_common`, `mind.memory_lorebooks`, `mind.memory_write` |
| `mind/memory_lorebooks.py` | 583 | The lorebook graph: hierarchy, links, inheritance modes, per-chat attachment and weights. | `core.db`, `core.logging_utils`, `mind.memory_common` |
| `mind/memory_read.py` | 471 | The one seam a mind reads its own memory through, and the host reads that deliberately cross characters. | `core`, `core.db`, `mind.memory_common`, `mind.memory_write` |
| `mind/memory_relationships.py` | 457 | The relationship graph: axis deltas from conduct and from inference, and the history behind them. | `core.db`, `mind.memory_common`, `mind.memory_write` |
| `mind/memory_retrieval.py` | 1248 | Hybrid retrieval: lexical and vector rankings fused by RRF, tilted by mood and importance, plus unbidden recall. | `core.db`, `core.logging_utils`, `llm.providers`, `mind.memory_common`, `mind.memory_read`, `mind.memory_write` |
| `mind/memory_routes.py` | 670 |  | `core.db` |
| `mind/memory_snapshot.py` | 1005 | Checkpoint and archive: vector addressing, the prepare/apply restore split, memory and lorebook dump/restore. | `core.db`, `core.logging_utils`, `llm.providers`, `mind.memory_common`, `mind.memory_lore_entries`, `mind.memory_summaries`, `mind.memory_time`, `mind.memory_write` |
| `mind/memory_summaries.py` | 765 | Autobiographical, hearsay and surmise summaries: search, support sets, windowed consolidation and backfill. | `core.db`, `llm.prompts`, `llm.providers`, `mind.memory_common`, `mind.memory_read`, `mind.memory_retrieval`, `mind.memory_write` |
| `mind/memory_time.py` | 350 |  | `core.db` |
| `mind/memory_vectors.py` | 789 | Rebuilding vectors after the embedding model changes: bank status, the rebuild, and its background run. | `core.db`, `core.logging_utils`, `llm.providers`, `mind.memory_common`, `mind.memory_retrieval`, `mind.memory_write` |
| `mind/memory_write.py` | 989 | How a memory becomes a row: normalisation, extraction, FTS mirror, the upsert, and the embedding-repair thread. | `core.db`, `core.logging_utils`, `llm.providers`, `mind.memory_common` |
| `mind/notebook.py` | 406 |  | `mind` |
| `mind/psychology_runtime.py` | 873 |  | — |
| `mind/theory_of_mind.py` | 861 |  | — |
| `mind/thoughts.py` | 131 |  | `core.db` |
| `persist/__init__.py` | 6 |  | — |
| `persist/about_backfill.py` | 310 |  | `core.db` |
| `persist/beat_order.py` | 287 |  | `core.db` |
| `persist/chat_archive.py` | 1286 | Typed, atomic chat archive export/import service and HTTP routes. | `core.db`, `llm.schemas`, `mind.memory`, `persist.checkpoints`, `story.character_schema`, `story.room_conversation` |
| `persist/chat_delete.py` | 42 |  | `core.db` |
| `persist/checkpoints.py` | 1892 | Whole-chat snapshots and checkpoint restore orchestration. | `core.db`, `mind.memory` |
| `persist/commit.py` | 914 | Atomic commit orchestrator, per-turn lock, thin tail domains, and the facade re-exporting every commit_* name. | `core.db`, `core.frames`, `llm.prompts`, `llm.providers`, `mind`, `mind.memory`, `mind.theory_of_mind`, `persist.commit_attire`, `persist.commit_background`, `persist.commit_common`, `persist.commit_destruction`, `persist.commit_entities`, `persist.commit_ledgers`, `persist.commit_mapping`, `persist.commit_mechanics`, `persist.commit_memory`, `persist.commit_memory_write`, `persist.commit_place_graph`, `persist.commit_room_registry`, `persist.commit_scene_state`, `story`, `story.character_schema`, `story.scene`, `world.comfort`, `world.mechanics`, `world.paradox`, `world.spatial`, `world.spatial_frames`, `world.survival`, `world.weather` |
| `persist/commit_attire.py` | 1797 | The mutable clothing ledger: attire notes, shed/worn garment entities, the validated attire diff. | `persist.commit_common`, `story`, `story.attire`, `world.spatial` |
| `persist/commit_background.py` | 5731 | Background presences: tracking, identity folding, the reactor gate, promotion to cast. | `core.db`, `mind.memory`, `persist.commit_common`, `story.character_schema`, `story.scene`, `world.spatial`, `world.survival` |
| `persist/commit_common.py` | 738 | Leaf helpers shared across commit domains: scalar utilities, name/address roster, entity-id canonicalisation. | `core.db`, `mind.memory`, `story.character_schema`, `world.mechanics`, `world.spatial` |
| `persist/commit_destruction.py` | 414 | Single- and multi-book destruction cascades, retirement, and latency-gated news. | `core.db`, `mind.memory`, `persist.commit_common`, `world.mechanics`, `world.spatial`, `world.spatial_frames` |
| `persist/commit_entities.py` | 644 | world_entities projection of the scene commit, awareness gate, disguise supersession. | `core.db`, `persist.commit_common`, `story.character_schema`, `story.scene`, `world.spatial` |
| `persist/commit_ledgers.py` | 598 | Pending-obligation and world-pressure debt ledgers. | `core.db`, `core.pipeline_context`, `persist.commit_common` |
| `persist/commit_mapping.py` | 860 | Lore/book mapping commit: book ops, lore ops, canon fallback ops, offscreen-event normaliser. | `core.db`, `core.frames`, `mind.memory`, `persist.commit_common`, `story.character_schema`, `story.provenance_text`, `world.spatial` |
| `persist/commit_mechanics.py` | 524 | Transit/news sweeps, the world-event spine, information carriers, cast changes. | `core.db`, `persist.commit_common`, `persist.commit_scene_state`, `story.character_schema`, `story.scene`, `world.mechanics` |
| `persist/commit_memory.py` | 2424 | Pre-lock memory preparation: per-mind memories and the psychology deltas riding with them. | `core.db`, `mind`, `mind.memory`, `mind.theory_of_mind`, `persist.commit_background`, `persist.commit_common`, `persist.commit_place_graph`, `story.character_schema`, `world.charter`, `world.comfort`, `world.exposure`, `world.spatial`, `world.stimulation`, `world.survival` |
| `persist/commit_memory_write.py` | 367 | The durable memory write and its out-of-band consolidation twin. | `core.db`, `mind.memory`, `persist.commit_memory`, `story.character_schema`, `story.scene` |
| `persist/commit_place_graph.py` | 336 | Per-mind durable place graph and per-beat spatial experience. | `world.spatial` |
| `persist/commit_room_registry.py` | 620 | Room identity across frames: registry projection, mint dedup, renames, retirement, exit pruning. | `core.db`, `persist.commit_common`, `story.character_schema`, `world.spatial` |
| `persist/commit_scene_state.py` | 3068 | The prepared post-turn scene: pre-lock build, scene commit domain, book anchoring, ground advance. | `core.db`, `core.pipeline_context`, `mind.memory`, `persist.commit_attire`, `persist.commit_common`, `persist.commit_destruction`, `persist.commit_room_registry`, `story.character_schema`, `story.provenance_text`, `world.beat_ledger`, `world.landscape`, `world.mechanics`, `world.spatial`, `world.spatial_frames`, `world.structure`, `world.weather` |
| `persist/llm_capture.py` | 604 |  | `core.db` |
| `persist/pipeline_trace.py` | 635 | Privacy-conscious export, validation, and offline replay of persisted pipeline history. | `core.db` |
| `persist/steps.py` | 150 |  | `core.db` |
| `story/__init__.py` | 6 |  | — |
| `story/artifacts.py` | 653 |  | `llm.prompts` |
| `story/attire.py` | 3699 |  | — |
| `story/authored_events.py` | 299 |  | `core.db` |
| `story/carriers.py` | 1369 |  | `core.db`, `core.logging_utils`, `story.character_schema`, `story.scene`, `world`, `world.spatial` |
| `story/character_schema.py` | 2781 | Versioned character/persona defaults, normalization, accessors, and export payloads. | `llm.schemas`, `story` |
| `story/couriers.py` | 1170 |  | `story.carriers`, `world` |
| `story/dialogue_colors.py` | 268 |  | — |
| `story/greetings.py` | 1340 |  | `agents.runtime`, `core`, `core.db`, `core.logging_utils`, `llm.llm_quality`, `llm.prompts`, `mind.affect_pass`, `mind.memory`, `mind.theory_of_mind`, `persist.steps`, `story.character_schema`, `story.importers`, `world.charter_runtime` |
| `story/history_routing.py` | 215 |  | — |
| `story/importers.py` | 3300 | Native and AI-assisted character, persona, and lorebook import/generation. | `core.db`, `core.logging_utils`, `llm.prompts`, `llm.providers`, `mind.memory`, `story.character_schema`, `story.scene` |
| `story/journey_history.py` | 487 |  | — |
| `story/location_design.py` | 577 |  | `core.db` |
| `story/lore_structure.py` | 248 |  | — |
| `story/mandates.py` | 809 |  | `core.db` |
| `story/naming.py` | 555 |  | `core.db`, `world.charter_identity` |
| `story/opening_plan.py` | 128 |  | `core.db` |
| `story/plot_packages.py` | 4550 |  | `world.spatial` |
| `story/prelude.py` | 189 |  | `core.db` |
| `story/provenance_text.py` | 132 |  | — |
| `story/room_bible.py` | 447 |  | `core.db` |
| `story/room_calls.py` | 249 |  | — |
| `story/room_citations.py` | 221 |  | — |
| `story/room_conversation.py` | 582 |  | `core.db` |
| `story/room_frontier.py` | 726 |  | `core.db` |
| `story/room_proposals.py` | 906 |  | `core.db` |
| `story/room_research.py` | 376 |  | `core.db` |
| `story/room_sketch.py` | 1227 |  | `core.logging_utils` |
| `story/room_slice.py` | 561 |  | `story.attire` |
| `story/room_tools.py` | 1791 |  | `story.plot_packages`, `story.room_research`, `story.room_slice` |
| `story/scene.py` | 3146 | Scene/cast/persona helpers, recent events, dialogue configuration, and private knowledge. | `core.db`, `story`, `story.attire`, `story.character_schema`, `world.day_cycle`, `world.spatial` |
| `web/__init__.py` | 6 |  | — |
| `web/app.py` | 8328 | FastAPI application assembly, resource CRUD, turn control, and streaming endpoints. | `agents`, `agents.story_planner`, `core`, `core.db`, `core.frames`, `core.paths`, `dressing.ambience`, `dressing.backdrops`, `llm`, `llm.prompts`, `llm.providers`, `mind.memory`, `persist.chat_archive`, `persist.chat_delete`, `persist.checkpoints`, `persist.commit`, `persist.steps`, `story`, `story.character_schema`, `story.dialogue_colors`, `story.importers`, `story.prelude`, `story.scene`, `web`, `web.auth_routes`, `web.room_routes`, `web.world_routes`, `world`, `world.survival` |
| `web/auth_routes.py` | 279 | Typed host-authentication HTTP routes and cookie transport. | `web` |
| `web/guest_access.py` | 554 |  | `core.db` |
| `web/pipeline_views.py` | 42 |  | `agents.composer` |
| `web/room_routes.py` | 119 |  | `core.db`, `story` |
| `web/storey_plan.py` | 306 |  | — |
| `web/story_view.py` | 1029 |  | `core.db`, `persist.steps`, `world.charter_runtime`, `world.living_world` |
| `web/world_routes.py` | 2893 |  | `core`, `core.db`, `persist.commit`, `story`, `story.attire`, `story.character_schema`, `story.scene`, `world.charter`, `world.charter_runtime`, `world.spatial`, `world.weather` |
| `world/__init__.py` | 6 |  | — |
| `world/background_claims.py` | 598 |  | `core.db` |
| `world/beat_ledger.py` | 184 |  | — |
| `world/causal_completion.py` | 165 |  | `world.causal_verification` |
| `world/causal_program.py` | 417 |  | — |
| `world/causal_verification.py` | 1189 |  | — |
| `world/causality.py` | 402 |  | `world.spatial` |
| `world/charter.py` | 524 |  | `world.charter_author`, `world.charter_chatter`, `world.charter_commitment`, `world.charter_decide`, `world.charter_drift`, `world.charter_economy`, `world.charter_feel`, `world.charter_figure`, `world.charter_identity`, `world.charter_intervene`, `world.charter_log`, `world.charter_mark`, `world.charter_mind`, `world.charter_model`, `world.charter_move`, `world.charter_needs`, `world.charter_news`, `world.charter_place`, `world.charter_plan`, `world.charter_politics`, `world.charter_practice`, `world.charter_promote`, `world.charter_roster`, `world.charter_run`, `world.charter_social`, `world.charter_space`, `world.charter_talk`, `world.charter_temper`, `world.charter_trigger` |
| `world/charter_author.py` | 813 |  | `world.charter_commitment`, `world.charter_economy`, `world.charter_figure`, `world.charter_mark`, `world.charter_mind`, `world.charter_model`, `world.charter_needs`, `world.charter_politics`, `world.charter_practice` |
| `world/charter_chatter.py` | 487 |  | `world.crowds` |
| `world/charter_commitment.py` | 292 |  | `world.charter_model` |
| `world/charter_creature.py` | 464 |  | `world.charter_harm`, `world.charter_model` |
| `world/charter_crowd.py` | 368 |  | `world.crowds` |
| `world/charter_decide.py` | 279 |  | `world.charter_model`, `world.charter_news` |
| `world/charter_drift.py` | 106 |  | `world.charter_model` |
| `world/charter_economy.py` | 444 |  | `world.charter_model` |
| `world/charter_enrol.py` | 431 |  | `world.charter_generate`, `world.charter_model`, `world.charter_needs`, `world.charter_roster`, `world.charter_surface` |
| `world/charter_feel.py` | 469 |  | `mind.psychology_runtime`, `world.charter_mark`, `world.charter_needs`, `world.charter_temper` |
| `world/charter_figure.py` | 140 |  | — |
| `world/charter_generate.py` | 1930 |  | `world.charter_identity`, `world.charter_model`, `world.charter_needs`, `world.charter_roster`, `world.charter_surface` |
| `world/charter_harm.py` | 264 |  | — |
| `world/charter_history.py` | 897 |  | — |
| `world/charter_identity.py` | 1270 |  | — |
| `world/charter_intervene.py` | 344 |  | `world.charter_model` |
| `world/charter_log.py` | 521 |  | `world.charter_commitment`, `world.charter_decide`, `world.charter_economy`, `world.charter_feel`, `world.charter_mark`, `world.charter_mind`, `world.charter_model`, `world.charter_needs`, `world.charter_news`, `world.charter_politics`, `world.charter_social`, `world.charter_temper` |
| `world/charter_mark.py` | 302 |  | — |
| `world/charter_mind.py` | 262 |  | — |
| `world/charter_model.py` | 931 |  | `world.charter_chatter`, `world.charter_figure`, `world.charter_harm`, `world.charter_mark` |
| `world/charter_move.py` | 674 |  | `world.charter_needs`, `world.charter_space` |
| `world/charter_needs.py` | 615 |  | `world.charter_model` |
| `world/charter_news.py` | 565 |  | `world.charter_mind`, `world.charter_model`, `world.charter_talk` |
| `world/charter_observe.py` | 664 |  | `world.charter_figure`, `world.charter_identity`, `world.charter_mind`, `world.spatial` |
| `world/charter_ops.py` | 384 |  | `world.charter_harm` |
| `world/charter_place.py` | 671 |  | `world.charter_identity`, `world.charter_model`, `world.charter_move`, `world.spatial` |
| `world/charter_plan.py` | 227 |  | `world.charter_drift`, `world.charter_model`, `world.charter_roster` |
| `world/charter_politics.py` | 161 |  | — |
| `world/charter_practice.py` | 1203 |  | `world.charter_commitment`, `world.charter_figure`, `world.charter_mind`, `world.charter_needs`, `world.charter_politics`, `world.charter_social`, `world.charter_talk` |
| `world/charter_predation.py` | 1063 |  | `world.charter_creature`, `world.charter_harm`, `world.charter_model`, `world.charter_move` |
| `world/charter_promote.py` | 612 |  | `world.charter_commitment`, `world.charter_feel`, `world.charter_politics`, `world.charter_social` |
| `world/charter_roster.py` | 134 |  | `world.charter_model` |
| `world/charter_run.py` | 1530 |  | `world`, `world.charter_commitment`, `world.charter_decide`, `world.charter_drift`, `world.charter_economy`, `world.charter_enrol`, `world.charter_feel`, `world.charter_figure`, `world.charter_harm`, `world.charter_intervene`, `world.charter_log`, `world.charter_mark`, `world.charter_mind`, `world.charter_model`, `world.charter_move`, `world.charter_needs`, `world.charter_news`, `world.charter_plan`, `world.charter_politics`, `world.charter_practice`, `world.charter_roster`, `world.charter_social`, `world.charter_space`, `world.charter_talk`, `world.charter_trigger` |
| `world/charter_runtime.py` | 5802 |  | `core`, `core.logging_utils`, `world.charter`, `world.charter_news`, `world.charter_surface`, `world.day_cycle`, `world.mechanics`, `world.spatial` |
| `world/charter_social.py` | 865 |  | `world.charter_politics` |
| `world/charter_space.py` | 337 |  | `world.spatial` |
| `world/charter_surface.py` | 364 |  | — |
| `world/charter_surgery.py` | 402 |  | — |
| `world/charter_talk.py` | 351 |  | `world.charter_mind`, `world.charter_politics`, `world.charter_roster` |
| `world/charter_temper.py` | 167 |  | — |
| `world/charter_trigger.py` | 881 |  | `world.charter_mark`, `world.charter_news`, `world.charter_practice` |
| `world/comfort.py` | 340 |  | `world.spatial` |
| `world/crowds.py` | 783 |  | `world.spatial` |
| `world/day_cycle.py` | 603 |  | — |
| `world/degradation.py` | 171 |  | — |
| `world/exposure.py` | 232 |  | `story`, `world.spatial`, `world.weather` |
| `world/frontage.py` | 1216 |  | `world.spatial` |
| `world/gaps.py` | 459 |  | `core.db`, `mind.canon_provenance`, `world.spatial`, `world.subjects` |
| `world/landscape.py` | 1761 |  | — |
| `world/layout_arrange.py` | 5169 |  | `world.layout_solver` |
| `world/layout_bridge.py` | 3833 |  | `world.layout_arrange`, `world.layout_solver`, `world.structure` |
| `world/layout_solver.py` | 3479 |  | — |
| `world/living_world.py` | 639 |  | `core.logging_utils`, `world.mechanics` |
| `world/mechanics.py` | 1602 |  | `core`, `world.spatial`, `world.spatial_frames` |
| `world/offscreen.py` | 2305 |  | `core`, `core.logging_utils`, `llm.prompts` |
| `world/paradox.py` | 655 |  | `core.db`, `core.frames`, `story.character_schema`, `world.spatial` |
| `world/place_names.py` | 267 |  | `world.charter_identity` |
| `world/place_purpose.py` | 554 |  | `mind.theory_of_mind`, `world.comfort`, `world.spatial`, `world.survival` |
| `world/planned_entities.py` | 714 |  | `core.db` |
| `world/planning_needs.py` | 439 |  | — |
| `world/region_events.py` | 461 |  | — |
| `world/regions.py` | 755 |  | `world.spatial` |
| `world/routines.py` | 256 |  | `world.day_cycle` |
| `world/scene_memo.py` | 206 |  | — |
| `world/site_plan.py` | 1689 |  | — |
| `world/spatial.py` | 452 | Deterministic room, barrier, hearing, visibility, placement, and scene-diff logic. | `llm.schemas`, `world.spatial_barriers`, `world.spatial_contact_migration`, `world.spatial_contacts`, `world.spatial_containment`, `world.spatial_fov`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_levels`, `world.spatial_light`, `world.spatial_light_field`, `world.spatial_lint`, `world.spatial_listener`, `world.spatial_merge`, `world.spatial_orientation`, `world.spatial_pack`, `world.spatial_prose`, `world.spatial_routing`, `world.spatial_scent_field`, `world.spatial_senses`, `world.spatial_sound_field`, `world.spatial_substance`, `world.spatial_transit`, `world.spatial_walk` |
| `world/spatial_barriers.py` | 960 |  | `world.spatial_orientation` |
| `world/spatial_bubbles.py` | 674 |  | `story.scene`, `world.spatial`, `world.spatial_frames` |
| `world/spatial_contact_migration.py` | 332 |  | `story.character_schema`, `world.spatial_contacts`, `world.spatial_identity` |
| `world/spatial_contacts.py` | 2019 |  | `world.spatial_containment`, `world.spatial_identity`, `world.spatial_transit` |
| `world/spatial_containment.py` | 3808 |  | `world.spatial_barriers`, `world.spatial_identity`, `world.spatial_transit` |
| `world/spatial_fov.py` | 2712 |  | `world.scene_memo`, `world.spatial_barriers`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_orientation` |
| `world/spatial_frames.py` | 2718 |  | `core.db`, `core.frames`, `story.character_schema`, `story.scene`, `world.paradox`, `world.spatial` |
| `world/spatial_geometry.py` | 2425 |  | `story.character_schema`, `world.scene_memo`, `world.spatial_barriers`, `world.spatial_contacts`, `world.spatial_containment`, `world.spatial_identity`, `world.spatial_orientation` |
| `world/spatial_identity.py` | 923 |  | — |
| `world/spatial_levels.py` | 250 |  | `world.spatial_orientation` |
| `world/spatial_light.py` | 848 |  | `world.scene_memo`, `world.spatial_barriers`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_orientation` |
| `world/spatial_light_field.py` | 1479 |  | `world.scene_memo`, `world.spatial_barriers`, `world.spatial_containment`, `world.spatial_fov`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_light`, `world.spatial_orientation` |
| `world/spatial_lint.py` | 858 |  | `world.spatial_barriers`, `world.spatial_fov`, `world.spatial_geometry`, `world.spatial_orientation` |
| `world/spatial_listener.py` | 782 |  | `world.spatial_sound_field` |
| `world/spatial_merge.py` | 2964 |  | `llm.schemas`, `world.spatial_barriers`, `world.spatial_contact_migration`, `world.spatial_contacts`, `world.spatial_containment`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_levels`, `world.spatial_orientation`, `world.spatial_routing`, `world.spatial_senses`, `world.spatial_substance`, `world.spatial_transit` |
| `world/spatial_orientation.py` | 468 | Bearing math and reciprocal spatial-edge normalization. | — |
| `world/spatial_pack.py` | 623 |  | `world.spatial_fov`, `world.spatial_geometry`, `world.spatial_lint` |
| `world/spatial_prose.py` | 410 |  | `world.spatial_contacts`, `world.spatial_containment`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_light` |
| `world/spatial_routing.py` | 1567 |  | `world.spatial_barriers`, `world.spatial_containment`, `world.spatial_geometry`, `world.spatial_light`, `world.spatial_orientation` |
| `world/spatial_scent_field.py` | 233 |  | `world.spatial_barriers` |
| `world/spatial_senses.py` | 2478 |  | `world.scene_memo`, `world.spatial_barriers`, `world.spatial_containment`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_light`, `world.spatial_orientation`, `world.spatial_routing` |
| `world/spatial_sound_field.py` | 5340 |  | `world.scene_memo`, `world.spatial_barriers`, `world.spatial_containment`, `world.spatial_fov`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_light_field`, `world.spatial_senses` |
| `world/spatial_substance.py` | 1198 |  | `world.spatial_contacts`, `world.spatial_identity` |
| `world/spatial_transit.py` | 1491 |  | `world.spatial_barriers`, `world.spatial_identity` |
| `world/spatial_walk.py` | 548 |  | `world.spatial_fov`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_routing` |
| `world/stimulation.py` | 239 |  | `story`, `world.spatial` |
| `world/structure.py` | 3205 |  | `world.charter_model`, `world.frontage`, `world.place_names`, `world.regions`, `world.spatial` |
| `world/subjects.py` | 505 |  | `core.db`, `mind.canon_provenance`, `world.spatial` |
| `world/survival.py` | 489 |  | `core.db` |
| `world/vistas.py` | 391 |  | — |
| `world/weather.py` | 1709 |  | — |

## Largest top-level functions

### `agents/background.py`

| Function | Start | Size |
|---|---:|---:|
| `_react_one()` | 3024 | 219 lines |
| `_background_react()` | 1004 | 192 lines |
| `declare_charter_figures()` | 2756 | 188 lines |
| `scene_life()` | 1774 | 176 lines |
| `_demanded_presences()` | 1535 | 148 lines |
| `_present_others()` | 2186 | 135 lines |
| `_player_declaration_caught()` | 512 | 130 lines |
| `_beat_for_presence()` | 644 | 106 lines |

### `agents/character.py`

| Function | Start | Size |
|---|---:|---:|
| `character_step()` | 3555 | 1550 lines |
| `_annotate_known_exits()` | 2780 | 469 lines |
| `_ground_observation_citations()` | 1784 | 293 lines |
| `_unanswered_question_note()` | 597 | 246 lines |
| `_destination_from_goals()` | 2346 | 109 lines |
| `_recent_self_moves()` | 278 | 98 lines |
| `sprint_offers()` | 3284 | 97 lines |
| `_impossible_knowledge()` | 1041 | 89 lines |

### `agents/character_bare.py`

| Function | Start | Size |
|---|---:|---:|
| `compile_bare()` | 711 | 372 lines |
| `_compile_notebook()` | 481 | 122 lines |
| `modules_for()` | 341 | 76 lines |
| `holding_from()` | 223 | 54 lines |
| `_appraisal()` | 1116 | 53 lines |
| `without_engine_numbers()` | 135 | 47 lines |
| `name_concealed_bodies()` | 670 | 39 lines |
| `anchor_tells()` | 1085 | 29 lines |

### `agents/character_evidence.py`

| Function | Start | Size |
|---|---:|---:|
| `compact_character_evidence()` | 28 | 45 lines |
| `bind_current_evidence_to_memory()` | 109 | 38 lines |
| `_rewrite_evidence_container()` | 75 | 32 lines |

### `agents/character_tools.py`

| Function | Start | Size |
|---|---:|---:|
| `look_then_answer()` | 618 | 107 lines |
| `tool_specs()` | 88 | 46 lines |
| `route_takes_tools()` | 76 | 10 lines |
| `_call_args()` | 604 | 6 lines |
| `_joined()` | 727 | 6 lines |
| `tools_enabled()` | 69 | 5 lines |
| `_order()` | 136 | 4 lines |

### `agents/common.py`

| Function | Start | Size |
|---|---:|---:|
| `norm_sequence()` | 4776 | 309 lines |
| `presence_figures_for_room()` | 2276 | 284 lines |
| `_check_narrator_fidelity()` | 12138 | 258 lines |
| `_scrub_unknown_identities()` | 6640 | 219 lines |
| `_summary_label()` | 6095 | 181 lines |
| `_scrub_invented_dialogue()` | 10546 | 151 lines |
| `observer_body_regions()` | 1750 | 140 lines |
| `_check_quote_attribution()` | 11710 | 131 lines |

### `agents/composer.py`

| Function | Start | Size |
|---|---:|---:|
| `_render_view_english()` | 6407 | 290 lines |
| `speech_percept()` | 4422 | 289 lines |
| `compose_landscape_line()` | 3392 | 229 lines |
| `presence_percepts()` | 1380 | 181 lines |
| `pose_percepts()` | 2373 | 178 lines |
| `act_percept()` | 5069 | 166 lines |
| `_render_episode_english()` | 6960 | 139 lines |
| `line_hear_level()` | 723 | 130 lines |

### `agents/director.py`

| Function | Start | Size |
|---|---:|---:|
| `director_resolve()` | 5377 | 2577 lines |
| `director_interpret()` | 1701 | 1108 lines |
| `_reconcile_resolution()` | 3162 | 521 lines |
| `_run_specialists()` | 3740 | 425 lines |
| `director_establish()` | 380 | 219 lines |
| `_reconcile_interpretation()` | 2836 | 172 lines |
| `_ground_public_evidence()` | 4304 | 116 lines |
| `_require_complete_entity_interiors()` | 4167 | 95 lines |

### `agents/director_contact.py`

| Function | Start | Size |
|---|---:|---:|
| `_validated_player_contact_assertions()` | 65 | 168 lines |
| `_merge_player_contact_assertions()` | 330 | 98 lines |
| `_player_contacts_held()` | 269 | 59 lines |
| `_character_material_effects()` | 489 | 52 lines |
| `_validated_character_contact_endings()` | 430 | 51 lines |
| `_merge_character_material_effects()` | 543 | 35 lines |
| `_carries_player_authority()` | 235 | 32 lines |
| `_merge_character_contact_endings()` | 580 | 32 lines |

### `agents/director_evidence.py`

| Function | Start | Size |
|---|---:|---:|
| `_evidence_present()` | 2076 | 359 lines |
| `causal_world_index()` | 3195 | 315 lines |
| `normalize_causal_ledger()` | 2802 | 288 lines |
| `restore_declared_quotes()` | 2630 | 151 lines |
| `beat_event_ledger()` | 1289 | 123 lines |
| `beat_timeline()` | 1176 | 111 lines |
| `_fold_derived_manifest_events()` | 4019 | 89 lines |
| `_span_items()` | 3646 | 86 lines |

### `agents/director_fanout.py`

| Function | Start | Size |
|---|---:|---:|
| `_specialist_payload()` | 601 | 320 lines |
| `_resolve_beat_view()` | 49 | 142 lines |
| `_interpret_beat_view()` | 203 | 64 lines |
| `_resolved_event_verdicts()` | 1031 | 54 lines |
| `_specialist_span_slice()` | 287 | 47 lines |
| `_beat_rooms()` | 409 | 40 lines |
| `_grid_view()` | 368 | 39 lines |
| `addressed_house()` | 539 | 36 lines |

### `agents/director_floors.py`

| Function | Start | Size |
|---|---:|---:|
| `_bind_minted_entities_to_present_figures()` | 1855 | 277 lines |
| `_stand_touching_figures()` | 1629 | 153 lines |
| `resolve_concealment_refs()` | 2218 | 121 lines |
| `_conditions_view()` | 597 | 103 lines |
| `strip_addressee_concealment()` | 2367 | 102 lines |
| `_awareness_exits()` | 733 | 98 lines |
| `_release_attempts()` | 991 | 93 lines |
| `_narrated_destruction_subjects()` | 1251 | 79 lines |

### `agents/director_layout.py`

| Function | Start | Size |
|---|---:|---:|
| `lay_out_buildings()` | 488 | 107 lines |
| `lay_out()` | 268 | 69 lines |
| `building_description()` | 386 | 65 lines |
| `_take_off_what_is_not_laid()` | 226 | 40 lines |
| `lay_out_opening_ground()` | 453 | 33 lines |
| `_briefed()` | 339 | 25 lines |
| `layout_tier_enabled()` | 134 | 20 lines |
| `layout_grounds_enabled()` | 113 | 19 lines |

### `agents/director_lingua.py`

| Function | Start | Size |
|---|---:|---:|
| `_ling()` | 16 | 14 lines |

### `agents/director_movement.py`

| Function | Start | Size |
|---|---:|---:|
| `_apply_following_movement()` | 1673 | 452 lines |
| `_reconcile_near_group_positions()` | 309 | 289 lines |
| `_travel_continues()` | 2912 | 191 lines |
| `walk_declared()` | 2555 | 136 lines |
| `walk_within_room()` | 2723 | 135 lines |
| `_guard_approach_is_not_arrival()` | 3198 | 103 lines |
| `follow_through_the_steps()` | 1461 | 91 lines |
| `_walk_short_of()` | 3105 | 91 lines |

### `agents/director_prose.py`

| Function | Start | Size |
|---|---:|---:|
| `run()` | 4092 | 345 lines |
| `encode()` | 3397 | 151 lines |
| `a_walk_is_its_owners()` | 2061 | 143 lines |
| `select_channels()` | 609 | 127 lines |
| `a_line_is_heard_never_sounded()` | 2762 | 95 lines |
| `entity_keys_name_held_things()` | 2865 | 86 lines |
| `rooms_named_by_part()` | 931 | 83 lines |
| `implied_tools()` | 1327 | 80 lines |

### `agents/director_reconcile.py`

| Function | Start | Size |
|---|---:|---:|
| `_verify_already_true()` | 367 | 126 lines |
| `_scale_relation_conflicts()` | 213 | 107 lines |
| `_player_claim_findings()` | 60 | 82 lines |
| `_stamp_dialogue_articulation()` | 147 | 64 lines |
| `_acquit_addressed_events()` | 495 | 63 lines |
| `_verify_no_referent()` | 338 | 27 lines |
| `_deep_audit_mode()` | 48 | 11 lines |
| `_public_omission()` | 143 | 2 lines |

### `agents/director_repair.py`

| Function | Start | Size |
|---|---:|---:|
| `_check_and_repair()` | 1495 | 182 lines |
| `battery()` | 643 | 88 lines |
| `apply_answers()` | 1361 | 83 lines |
| `plan_jobs()` | 769 | 75 lines |
| `native_failures()` | 369 | 64 lines |
| `_repair_group()` | 1116 | 64 lines |
| `continuation()` | 982 | 57 lines |
| `sentences()` | 124 | 45 lines |

### `agents/director_rooms.py`

| Function | Start | Size |
|---|---:|---:|
| `design_rooms()` | 1841 | 267 lines |
| `_predevelop_run()` | 2795 | 192 lines |
| `_doorways_that_fit()` | 1289 | 176 lines |
| `_derive_far_bearings()` | 1029 | 103 lines |
| `_check()` | 407 | 101 lines |
| `_pack()` | 751 | 98 lines |
| `_place_doorways()` | 917 | 92 lines |
| `_groundwork()` | 1577 | 82 lines |

### `agents/director_scopes.py`

| Function | Start | Size |
|---|---:|---:|
| `_gate_facts()` | 398 | 79 lines |
| `manifest_category_targets()` | 557 | 50 lines |
| `note_key_targets()` | 510 | 45 lines |
| `_rebuild_channel_owners()` | 286 | 25 lines |
| `_schema_list_channels()` | 220 | 23 lines |
| `_note_key_forms()` | 488 | 20 lines |
| `reads_dialogue()` | 129 | 18 lines |
| `channel_serves_stage()` | 270 | 4 lines |

### `agents/director_views.py`

| Function | Start | Size |
|---|---:|---:|
| `_report_unowned_address_forms()` | 369 | 154 lines |
| `_report_observer_epithets()` | 296 | 71 lines |
| `_crowds_view()` | 554 | 68 lines |
| `_route_authorial_npc_beat()` | 114 | 54 lines |
| `_scene_match_forms()` | 67 | 45 lines |
| `_objective_scene()` | 721 | 40 lines |
| `_couriers_view()` | 624 | 32 lines |
| `_audit_fact_adjudications()` | 251 | 31 lines |

### `agents/dramaturge.py`

| Function | Start | Size |
|---|---:|---:|
| `propose()` | 313 | 112 lines |
| `_payload()` | 220 | 58 lines |
| `player_visible_stream()` | 169 | 43 lines |
| `revise()` | 427 | 43 lines |
| `_file()` | 284 | 27 lines |
| `_call()` | 106 | 16 lines |
| `_answered()` | 146 | 11 lines |
| `_frame_turns()` | 134 | 10 lines |

### `agents/impossible_knowledge.py`

| Function | Start | Size |
|---|---:|---:|
| `impossible_knowledge_cues()` | 91 | 74 lines |
| `aired_in_story()` | 182 | 51 lines |
| `naming_tokens()` | 59 | 30 lines |
| `_spoken_texts()` | 167 | 13 lines |
| `folded_tokens()` | 54 | 3 lines |
| `_tokens()` | 50 | 2 lines |

### `agents/loops.py`

| Function | Start | Size |
|---|---:|---:|
| `interaction_loop()` | 1100 | 794 lines |
| `deterministic_micro_perception()` | 330 | 275 lines |
| `rehydrate_loop_views()` | 107 | 82 lines |
| `reaction_loop()` | 1895 | 81 lines |
| `_lines_left_with_player()` | 806 | 59 lines |
| `self_micro_view()` | 235 | 54 lines |
| `_reaction_owed()` | 755 | 49 lines |
| `_beat_onset_scene()` | 907 | 48 lines |

### `agents/mapping.py`

| Function | Start | Size |
|---|---:|---:|
| `compile_world_context()` | 471 | 208 lines |
| `rulebook_rows()` | 345 | 124 lines |
| `_transit_destination_needs()` | 163 | 77 lines |
| `classify_movement()` | 242 | 62 lines |
| `_location_query_status()` | 306 | 33 lines |
| `merge_lore()` | 681 | 33 lines |
| `contained_interior_holder()` | 131 | 30 lines |
| `is_contained_destination()` | 100 | 29 lines |

### `agents/narration.py`

| Function | Start | Size |
|---|---:|---:|
| `narrator()` | 2347 | 550 lines |
| `_ordered_beat_events()` | 1147 | 250 lines |
| `_sensory_channels_manifest()` | 783 | 241 lines |
| `narrator_extra()` | 2970 | 227 lines |
| `_visible_portal_states()` | 1532 | 124 lines |
| `_generate_narration()` | 2152 | 89 lines |
| `_position_delta_payload()` | 1443 | 87 lines |
| `_page_identity_scrub()` | 523 | 74 lines |

### `agents/offscreen_beat.py`

| Function | Start | Size |
|---|---:|---:|
| `run_offscreen_beat()` | 206 | 128 lines |
| `note_beat_movement()` | 413 | 43 lines |
| `schedule_offscreen_beats()` | 166 | 38 lines |
| `_file_stalled_needs()` | 458 | 33 lines |
| `offscreen_interpretation()` | 81 | 32 lines |
| `live_bubbles()` | 138 | 26 lines |
| `stalling_bodies()` | 386 | 25 lines |
| `is_offscreen_beat()` | 115 | 21 lines |

### `agents/perception.py`

| Function | Start | Size |
|---|---:|---:|
| `_composer_outcome_views()` | 7758 | 1309 lines |
| `_composer_act_views()` | 6929 | 556 lines |
| `_composer_standing_percepts()` | 6101 | 409 lines |
| `perception_outcome()` | 4113 | 322 lines |
| `perception_act()` | 3581 | 223 lines |
| `_outcome_event_stream()` | 981 | 199 lines |
| `_composer_establish_views()` | 6764 | 156 lines |
| `_visible_things()` | 5727 | 154 lines |

### `agents/runtime.py`

| Function | Start | Size |
|---|---:|---:|
| `_run_pipeline()` | 1450 | 476 lines |
| `build_plan()` | 908 | 193 lines |
| `_load_extra_players()` | 57 | 101 lines |
| `resume_key_for_turn()` | 812 | 95 lines |
| `run_pipeline()` | 1977 | 78 lines |
| `_stream_one()` | 573 | 68 lines |
| `_stream_parallel()` | 642 | 60 lines |
| `_rehydrate_side_channels()` | 1326 | 53 lines |

### `agents/storage.py`

| Function | Start | Size |
|---|---:|---:|
| `save_step()` | 19 | 36 lines |
| `mark_steps_stale()` | 73 | 12 lines |
| `delete_step()` | 94 | 10 lines |
| `_set_steps_stale()` | 65 | 7 lines |
| `clear_steps_stale()` | 86 | 7 lines |
| `variant_count()` | 56 | 4 lines |
| `step_is_stale()` | 61 | 3 lines |

### `agents/story_planner.py`

| Function | Start | Size |
|---|---:|---:|
| `run_planner()` | 1241 | 411 lines |
| `run_fill()` | 3118 | 167 lines |
| `deliberate()` | 2276 | 162 lines |
| `schedule_room_work()` | 3341 | 145 lines |
| `run_location_plan()` | 2015 | 136 lines |
| `run_dramaturge_pass()` | 2460 | 112 lines |
| `_payload()` | 718 | 108 lines |
| `_dramaturge_pass()` | 2585 | 108 lines |

### `core/code_version.py`

| Function | Start | Size |
|---|---:|---:|
| `check()` | 155 | 30 lines |
| `take_snapshot()` | 132 | 21 lines |
| `engine_source_files()` | 60 | 17 lines |
| `load_everything()` | 87 | 17 lines |
| `stream_notice()` | 195 | 11 lines |
| `held_files()` | 120 | 10 lines |
| `module_name()` | 79 | 6 lines |
| `_digest()` | 112 | 6 lines |

### `core/db.py`

| Function | Start | Size |
|---|---:|---:|
| `_migrate_chat_copies_to_overlays()` | 2517 | 156 lines |
| `init()` | 2831 | 140 lines |
| `_recover_scene_time_of_day()` | 2761 | 59 lines |
| `transaction()` | 2339 | 43 lines |
| `conn()` | 2299 | 38 lines |
| `_opening_time_of_day()` | 2705 | 30 lines |
| `db_read_token()` | 3030 | 30 lines |
| `_establish_time_of_day_from_variant()` | 2675 | 28 lines |

### `core/frames.py`

| Function | Start | Size |
|---|---:|---:|
| `is_memory_visible()` | 198 | 89 lines |
| `frame_lookup()` | 128 | 25 lines |
| `create_frame()` | 164 | 25 lines |
| `_frame_from_row()` | 93 | 11 lines |
| `is_recognized_in_frame()` | 289 | 11 lines |
| `frame_index()` | 116 | 10 lines |
| `get_frame()` | 106 | 8 lines |
| `list_frames()` | 155 | 7 lines |

### `core/jobs.py`

| Function | Start | Size |
|---|---:|---:|
| `submit()` | 91 | 57 lines |
| `cancel_from()` | 330 | 47 lines |
| `submit_latest()` | 150 | 39 lines |
| `_run()` | 240 | 39 lines |
| `_clear_turn_scoped_context()` | 202 | 36 lines |
| `story_rewound_past()` | 483 | 20 lines |
| `_finish_locked()` | 295 | 18 lines |
| `read_through()` | 379 | 18 lines |

### `core/logging_utils.py`

| Function | Start | Size |
|---|---:|---:|
| `configure_logging()` | 50 | 41 lines |
| `log_llm_call()` | 95 | 28 lines |
| `_configured_level()` | 26 | 11 lines |
| `_log_file_path()` | 39 | 9 lines |

### `core/outofband.py`

| Function | Start | Size |
|---|---:|---:|
| `drain_all()` | 376 | 17 lines |
| `stopped()` | 132 | 8 lines |

### `core/pipeline_context.py`

| Function | Start | Size |
|---|---:|---:|
| `sent_payload()` | 80 | 31 lines |
| `note_step_exchange()` | 113 | 23 lines |
| `canonical_movement()` | 176 | 21 lines |
| `note_step_decision()` | 159 | 14 lines |
| `note_step_warning()` | 48 | 11 lines |
| `_capturing()` | 147 | 10 lines |

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
| `resolve_ambience()` | 1686 | 222 lines |
| `_rank_candidates()` | 1083 | 105 lines |
| `refine_layers()` | 774 | 89 lines |
| `cached_ambience()` | 492 | 62 lines |
| `search_freesound()` | 1368 | 61 lines |
| `search_local()` | 885 | 54 lines |
| `_query_ladder()` | 1197 | 51 lines |
| `acoustic_fingerprint()` | 260 | 48 lines |

### `dressing/backdrops.py`

| Function | Start | Size |
|---|---:|---:|
| `generate_backdrop()` | 1580 | 116 lines |
| `room_projection()` | 902 | 79 lines |
| `build_backdrop_request()` | 1128 | 69 lines |
| `visual_signature()` | 210 | 59 lines |
| `_brief_sentences()` | 1278 | 51 lines |
| `compose_prompt()` | 1331 | 48 lines |
| `_camera_of()` | 793 | 44 lines |
| `room_brief()` | 856 | 44 lines |

### `llm/decisions.py`

| Function | Start | Size |
|---|---:|---:|
| `decide()` | 281 | 35 lines |
| `_post()` | 144 | 30 lines |
| `_foregone()` | 235 | 22 lines |
| `capture()` | 212 | 21 lines |
| `setting()` | 88 | 19 lines |
| `_batches()` | 264 | 15 lines |
| `_provider()` | 72 | 14 lines |
| `_http()` | 129 | 13 lines |

### `llm/json_mend.py`

| Function | Start | Size |
|---|---:|---:|
| `_decoder_edits()` | 153 | 57 lines |
| `mend_candidates()` | 265 | 38 lines |
| `_bracket_edits()` | 212 | 25 lines |
| `_bracket_fault()` | 80 | 22 lines |
| `_trailing_comma_at()` | 134 | 17 lines |
| `_string_start()` | 118 | 14 lines |
| `_repeated()` | 243 | 14 lines |
| `_loads()` | 60 | 8 lines |

### `llm/llm_quality.py`

| Function | Start | Size |
|---|---:|---:|
| `complete_validated_json()` | 1143 | 982 lines |
| `_targeted_field_patch()` | 554 | 100 lines |
| `note_provider_exchange()` | 829 | 68 lines |
| `_read_answer()` | 449 | 61 lines |
| `output_ran_out_of_room()` | 300 | 47 lines |
| `_answer_goes_on()` | 140 | 44 lines |
| `_read_json()` | 195 | 40 lines |
| `json_failure_diagnosis()` | 349 | 39 lines |

### `llm/prompt_cache.py`

| Function | Start | Size |
|---|---:|---:|
| `add_cache_breakpoint()` | 15 | 37 lines |
| `estimate_cacheable_tokens()` | 66 | 14 lines |
| `supports_prompt_caching()` | 7 | 7 lines |

### `llm/prompts.py`

| Function | Start | Size |
|---|---:|---:|
| `preset_import_document()` | 269 | 51 lines |
| `_encoder_pieces()` | 481 | 42 lines |
| `unified_specialist_prompt()` | 445 | 34 lines |
| `_relocate_character_identity()` | 616 | 28 lines |
| `normalize_preset()` | 116 | 26 lines |
| `_preset_override()` | 213 | 22 lines |
| `narrator_sections()` | 670 | 18 lines |
| `_director_sheets()` | 77 | 17 lines |

### `llm/providers.py`

| Function | Start | Size |
|---|---:|---:|
| `_chat_complete_once()` | 4319 | 395 lines |
| `chat_complete()` | 3945 | 180 lines |
| `_claude_cli_complete()` | 3813 | 130 lines |
| `async _chat_complete_async_once()` | 4927 | 130 lines |
| `_sse_openai()` | 3471 | 118 lines |
| `async chat_complete_async()` | 4834 | 92 lines |
| `_json_mode_recovery_stages()` | 3054 | 83 lines |
| `async _sse_openai_async()` | 5058 | 74 lines |

### `llm/research_providers.py`

| Function | Start | Size |
|---|---:|---:|
| `_fetch_html()` | 165 | 24 lines |
| `search()` | 86 | 16 lines |
| `fetch()` | 104 | 11 lines |
| `html_to_text()` | 153 | 10 lines |
| `configured()` | 59 | 9 lines |
| `_adapter()` | 75 | 9 lines |
| `_session()` | 70 | 3 lines |

### `llm/schemas.py`

| Function | Start | Size |
|---|---:|---:|
| `preprocess_llm_output()` | 5602 | 294 lines |
| `_lenient_coerce()` | 946 | 159 lines |
| `validate_llm_output_strict()` | 6796 | 139 lines |
| `semantic_output_errors()` | 6425 | 128 lines |
| `canonicalize_prose_markup()` | 5368 | 102 lines |
| `_coerce_station_table()` | 85 | 81 lines |
| `_uncross_concealed_speech()` | 5492 | 69 lines |
| `_coerce_list_valued_map()` | 168 | 57 lines |

### `mind/affect.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_intent_ops()` | 1319 | 193 lines |
| `resolve_affect()` | 816 | 189 lines |
| `appraise()` | 499 | 145 lines |
| `settle_intent_world_anchors()` | 1574 | 132 lines |
| `normalize_wants()` | 1011 | 118 lines |
| `apply_project_ops()` | 1805 | 98 lines |
| `update_drive_strain()` | 2233 | 86 lines |
| `validate_drive_shift()` | 2362 | 79 lines |

### `mind/affect_appraisal.py`

| Function | Start | Size |
|---|---:|---:|
| `read()` | 222 | 50 lines |
| `questions_for()` | 147 | 36 lines |
| `_labels()` | 115 | 9 lines |
| `_probabilities()` | 185 | 9 lines |
| `_read_event()` | 211 | 9 lines |
| `appraise()` | 274 | 9 lines |
| `_number()` | 196 | 7 lines |
| `_choice()` | 126 | 6 lines |

### `mind/affect_mix.py`

| Function | Start | Size |
|---|---:|---:|
| `emotions_from_act()` | 379 | 68 lines |
| `surface_and_undercurrent()` | 783 | 55 lines |
| `targets()` | 628 | 48 lines |
| `emotions_from_appraisal()` | 337 | 25 lines |
| `memory_emotions()` | 449 | 21 lines |
| `formed()` | 518 | 19 lines |
| `decay()` | 608 | 18 lines |
| `recalled()` | 568 | 17 lines |

### `mind/affect_pass.py`

| Function | Start | Size |
|---|---:|---:|
| `feel_seeded()` | 724 | 56 lines |
| `memories_from()` | 236 | 50 lines |
| `before_call()` | 447 | 44 lines |
| `_recall()` | 493 | 36 lines |
| `feelings_block()` | 689 | 31 lines |
| `why_read()` | 311 | 30 lines |
| `state_text()` | 415 | 28 lines |
| `after_call()` | 586 | 25 lines |

### `mind/canon_provenance.py`

| Function | Start | Size |
|---|---:|---:|
| `validate_provisional()` | 247 | 106 lines |
| `promote()` | 355 | 44 lines |
| `_node_id_errors()` | 213 | 32 lines |
| `unavailable()` | 192 | 19 lines |
| `outranks()` | 173 | 17 lines |
| `may_assert_consequence()` | 156 | 15 lines |
| `is_node_id()` | 139 | 9 lines |
| `is_canon()` | 150 | 4 lines |

### `mind/character_jev.py`

| Function | Start | Size |
|---|---:|---:|
| `after_questions()` | 624 | 310 lines |
| `state_text()` | 388 | 57 lines |
| `heard_question()` | 1072 | 42 lines |
| `moment_questions()` | 543 | 34 lines |
| `grade_point()` | 972 | 30 lines |
| `tells_asked()` | 255 | 25 lines |
| `belief_pair_questions()` | 1024 | 22 lines |
| `notes_in_play()` | 358 | 21 lines |

### `mind/knowledge_circles.py`

| Function | Start | Size |
|---|---:|---:|
| `join_circle()` | 79 | 22 lines |
| `leave_circle()` | 103 | 15 lines |
| `effective_circles()` | 120 | 15 lines |
| `identity_key()` | 47 | 10 lines |
| `story_circles()` | 63 | 6 lines |
| `_save()` | 71 | 6 lines |
| `_circle()` | 59 | 2 lines |

### `mind/memory_common.py`

| Function | Start | Size |
|---|---:|---:|
| `_kw_scores()` | 186 | 49 lines |
| `_lore_document()` | 253 | 18 lines |
| `surviving_character_ids()` | 277 | 17 lines |
| `_cos()` | 236 | 16 lines |
| `_b64_to_blob()` | 155 | 14 lines |
| `_ling()` | 13 | 10 lines |
| `_blob_to_b64()` | 144 | 10 lines |
| `_ids()` | 174 | 7 lines |

### `mind/memory_context.py`

| Function | Start | Size |
|---|---:|---:|
| `build_character_memory_context()` | 280 | 607 lines |
| `_with_reading()` | 30 | 121 lines |
| `_origin_on_drift()` | 177 | 94 lines |
| `_summary_id()` | 164 | 3 lines |

### `mind/memory_inference.py`

| Function | Start | Size |
|---|---:|---:|
| `reconcile_inference_confidence()` | 90 | 70 lines |
| `_abandoned_confidence()` | 75 | 13 lines |
| `_mint_confidence_of()` | 61 | 12 lines |

### `mind/memory_jev.py`

| Function | Start | Size |
|---|---:|---:|
| `memory_net()` | 201 | 124 lines |
| `jev_ponder_packet()` | 492 | 77 lines |
| `jev_memory_packet()` | 419 | 71 lines |
| `_graded_ponder()` | 571 | 33 lines |
| `memory_line()` | 327 | 29 lines |
| `grade_net()` | 381 | 24 lines |
| `named_in()` | 115 | 22 lines |
| `memory_state()` | 358 | 21 lines |

### `mind/memory_judge.py`

| Function | Start | Size |
|---|---:|---:|
| `review_minted_memories()` | 343 | 88 lines |
| `review_recall()` | 164 | 44 lines |
| `pending_tensions()` | 275 | 28 lines |
| `pending_subject()` | 250 | 23 lines |
| `_clean_tension()` | 141 | 21 lines |
| `_store_tensions()` | 305 | 19 lines |
| `_existing_tensions()` | 326 | 15 lines |
| `_parse()` | 127 | 12 lines |

### `mind/memory_links.py`

| Function | Start | Size |
|---|---:|---:|
| `form_memory_links()` | 80 | 107 lines |
| `pull_successors()` | 243 | 47 lines |
| `successors_of()` | 205 | 36 lines |
| `_linkable()` | 68 | 6 lines |
| `_order()` | 189 | 6 lines |
| `_quote()` | 76 | 2 lines |

### `mind/memory_lore_entries.py`

| Function | Start | Size |
|---|---:|---:|
| `search_lore()` | 442 | 104 lines |
| `knowledge_for_character()` | 774 | 93 lines |
| `set_lore_overlay()` | 359 | 72 lines |
| `backfill_lore_embedding_stamps()` | 547 | 71 lines |
| `duplicate_lorebook_tree_for_chat()` | 205 | 69 lines |
| `lore_embedding_health()` | 620 | 62 lines |
| `add_lore()` | 108 | 49 lines |
| `update_lore()` | 158 | 46 lines |

### `mind/memory_lorebooks.py`

| Function | Start | Size |
|---|---:|---:|
| `resolve_lorebook_graph()` | 226 | 85 lines |
| `monitoring_subtree()` | 423 | 78 lines |
| `restore_lorebook_links()` | 517 | 66 lines |
| `lorebook_manifest()` | 357 | 65 lines |
| `add_lorebook_link()` | 125 | 43 lines |
| `move_lorebook()` | 53 | 37 lines |
| `reorder_lorebook()` | 91 | 30 lines |
| `would_create_book_cycle()` | 25 | 27 lines |

### `mind/memory_read.py`

| Function | Start | Size |
|---|---:|---:|
| `record_dispute()` | 305 | 84 lines |
| `visible_memory_rows()` | 78 | 73 lines |
| `update_memory()` | 242 | 62 lines |
| `raise_importance()` | 422 | 44 lines |
| `record_memory_look()` | 391 | 29 lines |
| `list_memories()` | 214 | 27 lines |
| `dramatic_irony_feed()` | 164 | 26 lines |
| `memory_bank_cache()` | 51 | 25 lines |

### `mind/memory_relationships.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_witnessed_signals()` | 254 | 112 lines |
| `_because_by_target()` | 368 | 70 lines |
| `update_relationships_from_inference()` | 183 | 55 lines |
| `apply_relationship_updates()` | 124 | 50 lines |
| `record_relationship_event()` | 84 | 25 lines |
| `relationships_for_payload()` | 440 | 18 lines |
| `relationship_history()` | 111 | 11 lines |
| `get_relationships()` | 59 | 7 lines |

### `mind/memory_retrieval.py`

| Function | Start | Size |
|---|---:|---:|
| `search_memories()` | 544 | 306 lines |
| `contrast_memory()` | 1064 | 127 lines |
| `_rank_normalized_importance()` | 481 | 61 lines |
| `recall_confidence()` | 969 | 59 lines |
| `record_memory_access()` | 852 | 50 lines |
| `_mmr_select()` | 170 | 43 lines |
| `recent_memory_buffer()` | 1205 | 43 lines |
| `_exact_cue_score()` | 96 | 33 lines |

### `mind/memory_routes.py`

| Function | Start | Size |
|---|---:|---:|
| `answer()` | 433 | 202 lines |
| `route_questions()` | 166 | 35 lines |
| `_order_key()` | 254 | 31 lines |
| `_subject_lane()` | 326 | 24 lines |
| `_surest()` | 393 | 22 lines |
| `routed_ponder()` | 650 | 21 lines |
| `read_route()` | 208 | 17 lines |
| `_yes_shares()` | 352 | 17 lines |

### `mind/memory_snapshot.py`

| Function | Start | Size |
|---|---:|---:|
| `import_character_memories()` | 615 | 131 lines |
| `restore_lorebook()` | 907 | 98 lines |
| `dump_chat_memories()` | 278 | 95 lines |
| `prepare_chat_memory_restore()` | 382 | 94 lines |
| `restore_memory_vectors()` | 170 | 54 lines |
| `_foreign_persona_names()` | 570 | 43 lines |
| `restore_lore_overlays()` | 863 | 42 lines |
| `apply_chat_memory_restore()` | 477 | 40 lines |

### `mind/memory_summaries.py`

| Function | Start | Size |
|---|---:|---:|
| `backfill_memory_summary_windows()` | 567 | 89 lines |
| `search_memory_summaries()` | 69 | 88 lines |
| `_write_consolidated_window()` | 448 | 78 lines |
| `consolidate_character_memory()` | 658 | 75 lines |
| `derive_summary_support()` | 176 | 59 lines |
| `_consolidator_row()` | 403 | 43 lines |
| `save_memory_summary()` | 258 | 39 lines |
| `get_memory_summary()` | 30 | 38 lines |

### `mind/memory_time.py`

| Function | Start | Size |
|---|---:|---:|
| `time_ago_span()` | 150 | 33 lines |
| `window_clock_readings()` | 320 | 31 lines |
| `current_clock_reading()` | 187 | 19 lines |
| `time_ago_phrase()` | 131 | 17 lines |
| `_rung()` | 102 | 14 lines |
| `elapsed_phrase()` | 122 | 7 lines |
| `_plural()` | 118 | 2 lines |

### `mind/memory_vectors.py`

| Function | Start | Size |
|---|---:|---:|
| `rebuild_embeddings()` | 180 | 225 lines |
| `embedding_bank_status()` | 30 | 125 lines |
| `rebuild_checkpoint_embeddings()` | 444 | 124 lines |
| `repair_memory_cues()` | 593 | 111 lines |
| `start_rebuild_if_needed()` | 740 | 48 lines |
| `_run_rebuild()` | 712 | 26 lines |
| `_vector_key()` | 407 | 22 lines |
| `_rebuild_book_ids()` | 157 | 21 lines |

### `mind/memory_write.py`

| Function | Start | Size |
|---|---:|---:|
| `repair_pending_embeddings()` | 627 | 92 lines |
| `prepare_memory()` | 414 | 87 lines |
| `_extract_entities()` | 110 | 63 lines |
| `_extract_key_phrases()` | 174 | 48 lines |
| `_row_memory()` | 366 | 47 lines |
| `_upsert_memory()` | 751 | 47 lines |
| `_embed_in_request_sized_chunks()` | 837 | 37 lines |
| `repair_seed_salience()` | 959 | 30 lines |

### `mind/notebook.py`

| Function | Start | Size |
|---|---:|---:|
| `kept_when_no_room()` | 356 | 46 lines |
| `full_view()` | 218 | 38 lines |
| `view()` | 180 | 36 lines |
| `_people_and_things()` | 264 | 32 lines |
| `apply_notebook_ops()` | 324 | 30 lines |
| `_about_entries()` | 162 | 16 lines |
| `_drift_word()` | 146 | 14 lines |
| `_reminders_shown()` | 309 | 13 lines |

### `mind/psychology_runtime.py`

| Function | Start | Size |
|---|---:|---:|
| `resolve_hedonic()` | 176 | 231 lines |
| `resolve_stress()` | 409 | 126 lines |
| `apply_belief_updates()` | 638 | 120 lines |
| `apply_association_updates()` | 760 | 49 lines |
| `_authored_beliefs()` | 590 | 46 lines |
| `cognitive_absorption()` | 829 | 45 lines |
| `_within_cap()` | 551 | 29 lines |
| `elapsed_psych_units()` | 146 | 28 lines |

### `mind/theory_of_mind.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_mind_model_updates()` | 469 | 164 lines |
| `select_active_hypotheses()` | 769 | 62 lines |
| `rekey_place_claims()` | 331 | 53 lines |
| `_apply_note_op()` | 429 | 38 lines |
| `belief_credence()` | 669 | 37 lines |
| `claim_similarity()` | 234 | 35 lines |
| `mind_models_for_payload()` | 634 | 33 lines |
| `_same_belief()` | 270 | 26 lines |

### `mind/thoughts.py`

| Function | Start | Size |
|---|---:|---:|
| `beside_their_turns()` | 85 | 47 lines |
| `keep_thought()` | 47 | 23 lines |
| `recent_thoughts()` | 72 | 11 lines |
| `thoughts_kept()` | 38 | 7 lines |

### `persist/about_backfill.py`

| Function | Start | Size |
|---|---:|---:|
| `_backfill_chat()` | 232 | 57 lines |
| `_heard()` | 178 | 21 lines |
| `backfill_all()` | 291 | 20 lines |
| `_from_checkpoint()` | 99 | 19 lines |
| `_world_at()` | 120 | 16 lines |
| `_untagged()` | 64 | 14 lines |
| `_turn_steps()` | 138 | 14 lines |
| `_observer_card()` | 201 | 13 lines |

### `persist/beat_order.py`

| Function | Start | Size |
|---|---:|---:|
| `rewind_plan()` | 161 | 62 lines |
| `take_back()` | 250 | 28 lines |
| `_unseen_beat_of()` | 125 | 23 lines |
| `decide()` | 225 | 23 lines |
| `settled()` | 81 | 11 lines |
| `stamp_commit()` | 70 | 9 lines |
| `_running()` | 150 | 9 lines |
| `carried_notice()` | 280 | 8 lines |

### `persist/chat_archive.py`

| Function | Start | Size |
|---|---:|---:|
| `_exportable_checkpoint_blob()` | 99 | 20 lines |
| `_exportable_world()` | 93 | 4 lines |
| `_model_validate()` | 121 | 4 lines |
| `_model_dump()` | 127 | 4 lines |

### `persist/chat_delete.py`

| Function | Start | Size |
|---|---:|---:|
| `delete_chat_data()` | 8 | 35 lines |

### `persist/checkpoints.py`

| Function | Start | Size |
|---|---:|---:|
| `_restore_checkpoint_body()` | 1117 | 192 lines |
| `_restore_books()` | 382 | 148 lines |
| `compact_checkpoints()` | 1452 | 123 lines |
| `_snapshot_without_world()` | 192 | 117 lines |
| `insert_world_tables()` | 730 | 105 lines |
| `_snapshot_lore()` | 107 | 83 lines |
| `refresh_checkpoint()` | 1817 | 76 lines |
| `_cancel_jobs_the_restore_discards()` | 554 | 75 lines |

### `persist/commit.py`

| Function | Start | Size |
|---|---:|---:|
| `_commit_all_locked()` | 535 | 380 lines |
| `commit_crowds()` | 300 | 149 lines |
| `commit_authored_events()` | 246 | 30 lines |
| `commit_narration_person()` | 214 | 29 lines |
| `_refuse_a_taken_back_turn()` | 506 | 27 lines |
| `_refuse_an_ended_frame()` | 487 | 17 lines |
| `_prepare_turn_commit()` | 464 | 12 lines |
| `commit_offscreen_epoch()` | 278 | 11 lines |

### `persist/commit_attire.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_attire_diff()` | 1091 | 707 lines |
| `_mint_shed_garments()` | 720 | 128 lines |
| `interpret_attire_notes()` | 253 | 115 lines |
| `_reclaim_worn_shed_garments()` | 931 | 92 lines |
| `_fold_duplicate_shed_garments()` | 370 | 85 lines |
| `_fold_worn_garment_entities()` | 473 | 73 lines |
| `_merge_attire_regions()` | 32 | 65 lines |
| `_heal_attire_identity_keys()` | 99 | 61 lines |

### `persist/commit_background.py`

| Function | Start | Size |
|---|---:|---:|
| `track_background_presences()` | 2177 | 931 lines |
| `pick_voice_demand()` | 4313 | 444 lines |
| `promote_background_character()` | 4929 | 403 lines |
| `descriptor_bindings()` | 3866 | 156 lines |
| `_fold_duplicate_presences()` | 801 | 143 lines |
| `schedule_auto_promotion()` | 5609 | 123 lines |
| `addressed_rooms()` | 4190 | 121 lines |
| `select_auto_promotion()` | 5371 | 109 lines |

### `persist/commit_common.py`

| Function | Start | Size |
|---|---:|---:|
| `_names_heard_in()` | 248 | 74 lines |
| `add_engine_notice()` | 659 | 63 lines |
| `_monotonic_elapsed()` | 72 | 53 lines |
| `_address_forms()` | 155 | 52 lines |
| `_resolve_roster_name()` | 490 | 47 lines |
| `_entity_alias_map()` | 549 | 47 lines |
| `charter_recognition_projection()` | 338 | 39 lines |
| `seed_mutual_recognition()` | 452 | 36 lines |

### `persist/commit_destruction.py`

| Function | Start | Size |
|---|---:|---:|
| `_prepare_destruction()` | 193 | 155 lines |
| `_destruction_cascade()` | 125 | 66 lines |
| `_apply_destruction()` | 378 | 37 lines |
| `_chat_book_graph()` | 52 | 30 lines |
| `_finalize_destruction_news()` | 350 | 26 lines |
| `_audience_book_id()` | 103 | 20 lines |
| `_book_distances()` | 84 | 17 lines |
| `_destruction_book()` | 34 | 16 lines |

### `persist/commit_entities.py`

| Function | Start | Size |
|---|---:|---:|
| `commit_world_entities()` | 282 | 363 lines |
| `_supersede_disguises()` | 96 | 74 lines |
| `_with_sound_wakings()` | 229 | 51 lines |
| `_inherit_known_to()` | 172 | 41 lines |
| `_subjects_that_moved()` | 35 | 36 lines |
| `_subjects_targeted_by_an_action()` | 73 | 21 lines |
| `_is_gated_awareness()` | 17 | 16 lines |
| `_ended_in()` | 215 | 12 lines |

### `persist/commit_ledgers.py`

| Function | Start | Size |
|---|---:|---:|
| `commit_world_pressure()` | 441 | 158 lines |
| `commit_obligations()` | 261 | 83 lines |
| `causal_obligation_ops()` | 121 | 69 lines |
| `_demand_unheard_by()` | 209 | 50 lines |
| `_find_obligation()` | 59 | 34 lines |
| `_positioned_body_named()` | 392 | 27 lines |
| `_beats_open()` | 94 | 25 lines |
| `world_pressure_view()` | 368 | 22 lines |

### `persist/commit_mapping.py`

| Function | Start | Size |
|---|---:|---:|
| `commit_mapping()` | 624 | 232 lines |
| `_apply_mapping_book_ops()` | 148 | 106 lines |
| `_drop_needs_the_beat_answers()` | 500 | 83 lines |
| `prepare_mapping_commit()` | 256 | 66 lines |
| `_answering_bodies()` | 447 | 51 lines |
| `_file_opening_premise()` | 369 | 45 lines |
| `_attach_committed_surface()` | 585 | 37 lines |
| `_file_engine_provenance()` | 118 | 28 lines |

### `persist/commit_mechanics.py`

| Function | Start | Size |
|---|---:|---:|
| `commit_transit_sweep()` | 74 | 268 lines |
| `commit_information_carriers()` | 395 | 76 lines |
| `commit_cast_changes()` | 474 | 51 lines |
| `commit_world_event_spine()` | 344 | 49 lines |
| `town_for_sweep()` | 32 | 40 lines |

### `persist/commit_memory.py`

| Function | Start | Size |
|---|---:|---:|
| `prepare_memory_commit()` | 703 | 1722 lines |
| `_cited_memory_ids()` | 84 | 76 lines |
| `_own_sequence_memory()` | 398 | 57 lines |
| `_interior_relations_of()` | 564 | 55 lines |
| `_hearer_label()` | 287 | 48 lines |
| `_witnessed_signals()` | 236 | 44 lines |
| `_evidence_spans()` | 192 | 42 lines |
| `_memory_about()` | 659 | 42 lines |

### `persist/commit_memory_write.py`

| Function | Start | Size |
|---|---:|---:|
| `commit_memories()` | 244 | 124 lines |
| `schedule_memory_consolidation()` | 79 | 85 lines |
| `schedule_memory_tension_pass()` | 169 | 73 lines |
| `_consolidate_committed_memories()` | 23 | 51 lines |

### `persist/commit_place_graph.py`

| Function | Start | Size |
|---|---:|---:|
| `update_place_graph()` | 45 | 180 lines |
| `record_spatial_experience()` | 227 | 110 lines |

### `persist/commit_room_registry.py`

| Function | Start | Size |
|---|---:|---:|
| `_prepare_room_registry()` | 256 | 123 lines |
| `dedup_minted_rooms()` | 137 | 118 lines |
| `_refresh_relocated_location()` | 477 | 78 lines |
| `prune_dangling_exits()` | 557 | 64 lines |
| `_apply_room_registry()` | 381 | 57 lines |
| `_apply_room_renames()` | 78 | 56 lines |
| `_registry_alias_index()` | 55 | 22 lines |
| `sync_room_registry_with_scene()` | 456 | 19 lines |

### `persist/commit_scene_state.py`

| Function | Start | Size |
|---|---:|---:|
| `compose_beat_scene()` | 1663 | 750 lines |
| `prepare_scene_commit()` | 2415 | 533 lines |
| `_fold_duplicate_mints()` | 841 | 135 lines |
| `_advance_day_cycle()` | 74 | 124 lines |
| `derive_borne_containment()` | 1011 | 124 lines |
| `_refuse_unheld_transfers()` | 1137 | 103 lines |
| `_place_orphan_mints()` | 1242 | 70 lines |
| `_merge_overlays()` | 611 | 68 lines |

### `persist/llm_capture.py`

| Function | Start | Size |
|---|---:|---:|
| `record_room_exchange()` | 524 | 56 lines |
| `record_exchange()` | 182 | 49 lines |
| `referenced_blob_hashes()` | 375 | 41 lines |
| `_values()` | 149 | 26 lines |
| `latest_turn_id()` | 478 | 26 lines |
| `put_blob()` | 85 | 25 lines |
| `recording_outside_a_step()` | 299 | 25 lines |
| `_file_pending()` | 242 | 23 lines |

### `persist/pipeline_trace.py`

| Function | Start | Size |
|---|---:|---:|
| `export_turn_debug()` | 443 | 168 lines |
| `validate_pipeline_trace()` | 193 | 128 lines |
| `export_pipeline_trace()` | 99 | 92 lines |
| `replay_pipeline_trace()` | 323 | 68 lines |
| `write_pipeline_trace()` | 408 | 25 lines |
| `export_chat_debug()` | 613 | 23 lines |
| `_variant_digest()` | 65 | 17 lines |
| `_canonical_json()` | 45 | 14 lines |

### `persist/steps.py`

| Function | Start | Size |
|---|---:|---:|
| `active_mappings()` | 92 | 59 lines |
| `_parsed()` | 35 | 20 lines |
| `active_mapping()` | 70 | 20 lines |
| `active_content()` | 57 | 11 lines |

### `story/artifacts.py`

| Function | Start | Size |
|---|---:|---:|
| `run_artifacts()` | 183 | 203 lines |
| `schedule_artifact_wording()` | 476 | 69 lines |
| `mint_wording()` | 547 | 55 lines |
| `land_artifact_wording()` | 604 | 50 lines |
| `post_spoor()` | 421 | 48 lines |
| `reading_copy()` | 150 | 25 lines |
| `spoor_artifact()` | 398 | 21 lines |
| `new_artifact()` | 128 | 20 lines |

### `story/attire.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_regions()` | 659 | 161 lines |
| `_attributed_scoped()` | 1964 | 139 lines |
| `coerce_diff_shape()` | 1629 | 136 lines |
| `advance()` | 2626 | 136 lines |
| `garments_named_in()` | 2301 | 126 lines |
| `compact_line()` | 3558 | 123 lines |
| `perceptible_region_surfaces()` | 2891 | 100 lines |
| `apply_flat_change()` | 3132 | 93 lines |

### `story/authored_events.py`

| Function | Start | Size |
|---|---:|---:|
| `resolve_authored_events()` | 218 | 82 lines |
| `mint_authored_events()` | 147 | 47 lines |
| `_changed_text()` | 90 | 36 lines |
| `_retired_text()` | 54 | 34 lines |
| `_event_id()` | 129 | 16 lines |
| `due_authored_events()` | 196 | 16 lines |
| `_covers()` | 214 | 2 lines |

### `story/carriers.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_tellings()` | 1170 | 200 lines |
| `unbacked_claims()` | 928 | 158 lines |
| `advance_carriers()` | 207 | 125 lines |
| `names_nobody_holds()` | 842 | 84 lines |
| `_build_carriers()` | 579 | 77 lines |
| `_held_identity_roster()` | 773 | 67 lines |
| `_crowds_acquire()` | 334 | 55 lines |
| `standing_surfaces_reader()` | 154 | 51 lines |

### `story/character_schema.py`

| Function | Start | Size |
|---|---:|---:|
| `character_card_warnings()` | 2559 | 192 lines |
| `default_character_data()` | 726 | 146 lines |
| `normalize_character_data()` | 1588 | 132 lines |
| `_normalize_psychology()` | 315 | 83 lines |
| `normalize_persona_data()` | 1721 | 74 lines |
| `_normalize_native_shape()` | 1521 | 65 lines |
| `_normalize_interior()` | 665 | 59 lines |
| `repair_character_shape()` | 1284 | 57 lines |

### `story/couriers.py`

| Function | Start | Size |
|---|---:|---:|
| `run_couriers()` | 805 | 366 lines |
| `_exchange_stops()` | 593 | 210 lines |
| `advance_couriers()` | 335 | 83 lines |
| `_deliver()` | 520 | 71 lines |
| `new_courier()` | 273 | 47 lines |
| `_copy_of()` | 420 | 39 lines |
| `_player_name()` | 492 | 26 lines |
| `courier_edge_seconds()` | 143 | 22 lines |

### `story/dialogue_colors.py`

| Function | Start | Size |
|---|---:|---:|
| `resolve_cast_colors()` | 191 | 52 lines |
| `personality_digest()` | 84 | 48 lines |
| `_spread()` | 245 | 19 lines |
| `_derived_hue()` | 151 | 16 lines |
| `normalize_color()` | 69 | 13 lines |
| `_hue_from()` | 134 | 10 lines |
| `auto_dialogue_color()` | 169 | 9 lines |
| `_hue_of()` | 180 | 9 lines |

### `story/greetings.py`

| Function | Start | Size |
|---|---:|---:|
| `start_story()` | 796 | 446 lines |
| `_seed_mind_state()` | 359 | 144 lines |
| `generate_greeting()` | 1244 | 62 lines |
| `_seed_minds()` | 557 | 57 lines |
| `_route_mind_memories()` | 301 | 56 lines |
| `_seed_player_mind()` | 505 | 50 lines |
| `claim_greeting_mind()` | 616 | 44 lines |
| `_write_failed_setup()` | 751 | 37 lines |

### `story/history_routing.py`

| Function | Start | Size |
|---|---:|---:|
| `resolve_character_history_route()` | 142 | 64 lines |
| `_manual_route()` | 99 | 41 lines |
| `normalize_history_choice()` | 71 | 14 lines |
| `_distinct_words()` | 91 | 6 lines |
| `_matches()` | 87 | 2 lines |
| `route_uses_charter()` | 208 | 2 lines |

### `story/importers.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_lorebook_plan()` | 2990 | 214 lines |
| `import_lorebook()` | 1789 | 212 lines |
| `draft_promoted_character()` | 810 | 172 lines |
| `_reinterpret_entries()` | 1662 | 126 lines |
| `_lore_gen_entry_batch()` | 2630 | 119 lines |
| `fill_appearance()` | 1233 | 115 lines |
| `fill_body_interior()` | 1418 | 114 lines |
| `_run_lore_gen_job()` | 2753 | 112 lines |

### `story/journey_history.py`

| Function | Start | Size |
|---|---:|---:|
| `compile_journey_history()` | 310 | 171 lines |
| `ground_journey_history()` | 191 | 92 lines |
| `_model_value()` | 150 | 39 lines |
| `_source_rows()` | 120 | 28 lines |
| `companion_of()` | 285 | 23 lines |
| `journey_event_count()` | 95 | 12 lines |
| `_content_key()` | 113 | 5 lines |
| `_text()` | 109 | 2 lines |

### `story/location_design.py`

| Function | Start | Size |
|---|---:|---:|
| `check()` | 355 | 132 lines |
| `set_skeleton()` | 202 | 55 lines |
| `rooms_with_no_far_look()` | 259 | 29 lines |
| `resumable_draft()` | 122 | 28 lines |
| `set_history()` | 326 | 27 lines |
| `set_charter()` | 290 | 22 lines |
| `_reservation()` | 489 | 22 lines |
| `_require_open()` | 182 | 18 lines |

### `story/lore_structure.py`

| Function | Start | Size |
|---|---:|---:|
| `derive_knowledge()` | 195 | 54 lines |
| `parse_structure()` | 78 | 45 lines |
| `clean_title()` | 46 | 16 lines |
| `classify_title()` | 64 | 12 lines |
| `_matches()` | 160 | 12 lines |
| `_place_name()` | 151 | 7 lines |

### `story/mandates.py`

| Function | Start | Size |
|---|---:|---:|
| `grant_mandate()` | 396 | 84 lines |
| `_request()` | 293 | 29 lines |
| `expire_mandates()` | 482 | 28 lines |
| `request_open()` | 335 | 27 lines |
| `close_request()` | 512 | 26 lines |
| `_spend()` | 712 | 24 lines |
| `renew_mandate()` | 540 | 22 lines |
| `beats_per_proposal()` | 778 | 20 lines |

### `story/naming.py`

| Function | Start | Size |
|---|---:|---:|
| `minted_presence_name()` | 374 | 54 lines |
| `registered_identity_names()` | 299 | 52 lines |
| `_person_name_evidence()` | 161 | 51 lines |
| `story_naming_lanes()` | 267 | 30 lines |
| `phonology_lanes()` | 520 | 30 lines |
| `harvested_naming_profile()` | 237 | 28 lines |
| `_name_tokens()` | 133 | 26 lines |
| `_charter_naming_lanes()` | 108 | 23 lines |

### `story/opening_plan.py`

| Function | Start | Size |
|---|---:|---:|
| `present_bodies()` | 110 | 19 lines |
| `mint_opening_mandate()` | 58 | 14 lines |
| `opening_placements()` | 74 | 10 lines |
| `record_placement()` | 86 | 8 lines |
| `record_opening_plan()` | 100 | 8 lines |
| `opening_plan_record()` | 96 | 2 lines |

### `story/plot_packages.py`

| Function | Start | Size |
|---|---:|---:|
| `_package_checks()` | 3674 | 143 lines |
| `_preview_plan_rooms()` | 1098 | 125 lines |
| `fire_due_clocks()` | 4263 | 102 lines |
| `_plan_geometry()` | 781 | 93 lines |
| `_preview_plan_entity()` | 1354 | 91 lines |
| `_plan_edge()` | 912 | 84 lines |
| `publish_package()` | 4044 | 84 lines |
| `_reach_warning()` | 3825 | 81 lines |

### `story/prelude.py`

| Function | Start | Size |
|---|---:|---:|
| `begin_story()` | 127 | 63 lines |
| `player_wants()` | 103 | 22 lines |
| `awaiting_begin()` | 82 | 9 lines |
| `record_setup()` | 69 | 6 lines |
| `pending_setup()` | 63 | 4 lines |
| `record_prelude()` | 93 | 4 lines |
| `clear_setup()` | 77 | 3 lines |
| `prelude_record()` | 99 | 2 lines |

### `story/provenance_text.py`

| Function | Start | Size |
|---|---:|---:|
| `split_engine_provenance()` | 86 | 42 lines |
| `looks_like_engine_provenance()` | 81 | 3 lines |
| `strip_engine_provenance()` | 130 | 3 lines |

### `story/room_bible.py`

| Function | Start | Size |
|---|---:|---:|
| `fold()` | 383 | 52 lines |
| `render_block()` | 304 | 42 lines |
| `source_exists()` | 83 | 35 lines |
| `add_entry()` | 223 | 27 lines |
| `_validated()` | 196 | 25 lines |
| `mark_paid()` | 252 | 23 lines |
| `_row()` | 146 | 18 lines |
| `_normalize_entry()` | 124 | 15 lines |

### `story/room_calls.py`

| Function | Start | Size |
|---|---:|---:|
| `room_call()` | 69 | 47 lines |
| `room_max_tokens()` | 35 | 32 lines |
| `_reasoning()` | 137 | 12 lines |
| `_shape()` | 127 | 8 lines |
| `_requested()` | 118 | 7 lines |
| `memo_part()` | 246 | 4 lines |

### `story/room_citations.py`

| Function | Start | Size |
|---|---:|---:|
| `check_claims()` | 176 | 46 lines |
| `_harvest()` | 139 | 16 lines |
| `note_reads()` | 124 | 13 lines |
| `normalize_claim()` | 162 | 12 lines |
| `reading()` | 96 | 9 lines |
| `enter_reading()` | 107 | 9 lines |
| `rows_read()` | 118 | 4 lines |
| `_add()` | 157 | 3 lines |

### `story/room_conversation.py`

| Function | Start | Size |
|---|---:|---:|
| `converse_stream()` | 431 | 104 lines |
| `converse()` | 364 | 51 lines |
| `status()` | 299 | 38 lines |
| `restore_room_messages()` | 547 | 36 lines |
| `normalize_mandate()` | 225 | 26 lines |
| `add_message()` | 191 | 23 lines |
| `revoke_mandate()` | 280 | 17 lines |
| `_normalize_request()` | 253 | 15 lines |

### `story/room_frontier.py`

| Function | Start | Size |
|---|---:|---:|
| `frontier_report()` | 353 | 89 lines |
| `fill_signature()` | 559 | 50 lines |
| `_bodies_ahead()` | 250 | 39 lines |
| `fills_this_hour()` | 517 | 36 lines |
| `_rooms_within()` | 219 | 29 lines |
| `fill_due()` | 668 | 24 lines |
| `_actor_rooms()` | 291 | 23 lines |
| `looks_wanted()` | 316 | 23 lines |

### `story/room_proposals.py`

| Function | Start | Size |
|---|---:|---:|
| `keep_spared()` | 624 | 119 lines |
| `pass_due()` | 758 | 53 lines |
| `hand_back_briefs()` | 494 | 44 lines |
| `file_proposal()` | 286 | 41 lines |
| `normalize_proposal()` | 117 | 40 lines |
| `judge_proposal()` | 329 | 31 lines |
| `briefs_due()` | 540 | 25 lines |
| `_pass_log()` | 179 | 22 lines |

### `story/room_research.py`

| Function | Start | Size |
|---|---:|---:|
| `web_search()` | 220 | 62 lines |
| `fetch_page()` | 284 | 49 lines |
| `tool_entries()` | 349 | 28 lines |
| `as_lore()` | 194 | 20 lines |
| `require_grant()` | 150 | 14 lines |
| `_save()` | 123 | 12 lines |
| `_load()` | 113 | 8 lines |
| `_with_templates()` | 335 | 8 lines |

### `story/room_sketch.py`

| Function | Start | Size |
|---|---:|---:|
| `sketch_payload()` | 386 | 260 lines |
| `_plan()` | 825 | 239 lines |
| `_looks_payload()` | 302 | 82 lines |
| `run_sketch()` | 1153 | 75 lines |
| `_looks_op()` | 764 | 59 lines |
| `_file()` | 1084 | 56 lines |
| `_structure_for()` | 709 | 27 lines |
| `_looks_read()` | 738 | 24 lines |

### `story/room_slice.py`

| Function | Start | Size |
|---|---:|---:|
| `room_slices()` | 458 | 83 lines |
| `room_graph()` | 232 | 76 lines |
| `_plan_here()` | 408 | 48 lines |
| `_things_by_room()` | 380 | 26 lines |
| `room_index()` | 351 | 23 lines |
| `read_scene()` | 106 | 21 lines |
| `_registry()` | 166 | 21 lines |
| `cast_rooms()` | 330 | 19 lines |

### `story/room_tools.py`

| Function | Start | Size |
|---|---:|---:|
| `_t_inspect_contradictions()` | 798 | 201 lines |
| `_mind_of()` | 1138 | 148 lines |
| `_t_inspect_charters()` | 582 | 83 lines |
| `_t_inspect_config()` | 721 | 70 lines |
| `fit_result()` | 1721 | 64 lines |
| `_t_inspect_route()` | 295 | 53 lines |
| `_t_inspect_rooms()` | 244 | 49 lines |
| `_charter_post_rows()` | 421 | 45 lines |

### `story/scene.py`

| Function | Start | Size |
|---|---:|---:|
| `_positive_presented_appearance()` | 1008 | 66 lines |
| `get_scene()` | 464 | 65 lines |
| `disguises_from_rows()` | 727 | 65 lines |
| `normalize_transformed_parts()` | 801 | 60 lines |
| `recent_events_for_observer()` | 1981 | 59 lines |
| `awareness_conditions()` | 1366 | 58 lines |
| `normalize_style_guide()` | 2824 | 58 lines |
| `dialogue_budget()` | 2929 | 54 lines |

### `web/app.py`

| Function | Start | Size |
|---|---:|---:|
| `turn_branch()` | 6914 | 524 lines |
| `chat_get()` | 4522 | 315 lines |
| `_remap_cp_blob()` | 1434 | 216 lines |
| `bootstrap()` | 1923 | 179 lines |
| `dlg_put()` | 5965 | 108 lines |
| `turn_new()` | 6669 | 102 lines |
| `chat_add_char()` | 4839 | 95 lines |
| `guest_state()` | 5266 | 95 lines |

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

### `web/pipeline_views.py`

| Function | Start | Size |
|---|---:|---:|
| `saved_perception_packets()` | 8 | 35 lines |

### `web/room_routes.py`

| Function | Start | Size |
|---|---:|---:|
| `room_say_stream()` | 78 | 27 lines |
| `room_thread()` | 52 | 10 lines |
| `room_say()` | 65 | 10 lines |
| `room_revoke()` | 108 | 6 lines |
| `_chat_and_frame()` | 44 | 5 lines |
| `room_status()` | 117 | 3 lines |

### `web/storey_plan.py`

| Function | Start | Size |
|---|---:|---:|
| `storey_plan()` | 182 | 125 lines |
| `room_look()` | 78 | 38 lines |
| `_runs()` | 44 | 26 lines |
| `plan_scene()` | 149 | 25 lines |
| `fixture_kinds()` | 132 | 15 lines |
| `_flight_of()` | 118 | 12 lines |
| `_plan_of()` | 72 | 4 lines |
| `plan_levels()` | 176 | 4 lines |

### `web/story_view.py`

| Function | Start | Size |
|---|---:|---:|
| `_living_world()` | 335 | 98 lines |
| `_people()` | 840 | 77 lines |
| `_player_view_in_frame()` | 970 | 60 lines |
| `player_view()` | 919 | 49 lines |
| `_story_view_in_frame()` | 457 | 46 lines |
| `_public_facts()` | 660 | 46 lines |
| `viewers()` | 523 | 36 lines |
| `_person_refs()` | 757 | 36 lines |

### `web/world_routes.py`

| Function | Start | Size |
|---|---:|---:|
| `grid_view()` | 885 | 217 lines |
| `room_entity_patch()` | 1820 | 95 lines |
| `_apply_exits()` | 1459 | 92 lines |
| `_apply_doorway_fields()` | 2532 | 85 lines |
| `map_view()` | 1223 | 80 lines |
| `body_station_put()` | 1991 | 77 lines |
| `body_rows()` | 623 | 70 lines |
| `room_patch()` | 1750 | 67 lines |

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

### `world/beat_ledger.py`

| Function | Start | Size |
|---|---:|---:|
| `record_beat_events()` | 114 | 26 lines |
| `beat_events()` | 142 | 21 lines |
| `beat_event_order()` | 165 | 20 lines |
| `_clean_event()` | 94 | 18 lines |

### `world/causal_completion.py`

| Function | Start | Size |
|---|---:|---:|
| `execution_receipt()` | 29 | 97 lines |
| `event_execution_statuses()` | 143 | 23 lines |
| `annotate_event_execution()` | 128 | 13 lines |

### `world/causal_program.py`

| Function | Start | Size |
|---|---:|---:|
| `bind_items()` | 62 | 193 lines |
| `program_steps()` | 333 | 54 lines |
| `_rewrite_patch()` | 32 | 28 lines |
| `event_worlds()` | 268 | 28 lines |
| `program_from_history()` | 298 | 23 lines |
| `prune_program()` | 399 | 19 lines |
| `fold_steps()` | 257 | 9 lines |
| `_content()` | 323 | 8 lines |

### `world/causal_verification.py`

| Function | Start | Size |
|---|---:|---:|
| `_map_receipts()` | 286 | 126 lines |
| `_inventory_receipts()` | 674 | 99 lines |
| `_contact_receipts()` | 873 | 66 lines |
| `verify_patch()` | 1114 | 62 lines |
| `_substance_receipts()` | 794 | 61 lines |
| `_overlay_receipts()` | 1056 | 56 lines |
| `_rooms_receipts()` | 439 | 51 lines |
| `_weather_receipts()` | 592 | 49 lines |

### `world/causality.py`

| Function | Start | Size |
|---|---:|---:|
| `compile_transforms()` | 208 | 195 lines |
| `_merge_attire_record()` | 74 | 66 lines |
| `_merge_channel()` | 142 | 43 lines |
| `_stamp_from_event()` | 187 | 19 lines |
| `_merge_record()` | 55 | 17 lines |

### `world/charter_author.py`

| Function | Start | Size |
|---|---:|---:|
| `_figure_dealing()` | 560 | 135 lines |
| `authored()` | 149 | 134 lines |
| `_figure_act()` | 310 | 83 lines |
| `acts_in_evidence()` | 736 | 53 lines |
| `preview_dealings()` | 507 | 43 lines |
| `dealing_answer()` | 466 | 39 lines |
| `has_standing()` | 395 | 35 lines |
| `good_named()` | 701 | 33 lines |

### `world/charter_chatter.py`

| Function | Start | Size |
|---|---:|---:|
| `subject_label()` | 427 | 61 lines |
| `participant_forms()` | 319 | 47 lines |
| `overheard_fragment()` | 228 | 44 lines |
| `window_acts()` | 74 | 34 lines |
| `relabel_fragment()` | 393 | 32 lines |
| `normalize_window_acts()` | 110 | 31 lines |
| `hum_rank()` | 155 | 29 lines |
| `participant_label()` | 368 | 23 lines |

### `world/charter_commitment.py`

| Function | Start | Size |
|---|---:|---:|
| `observe_public_commitments()` | 76 | 92 lines |
| `normalize_commitments()` | 32 | 38 lines |
| `open_commitment()` | 225 | 37 lines |
| `advance_commitments()` | 181 | 25 lines |
| `answer_commitment()` | 264 | 22 lines |
| `commitment_view()` | 208 | 15 lines |
| `commitment_id()` | 26 | 4 lines |
| `_frame_terms()` | 72 | 2 lines |

### `world/charter_creature.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_creature()` | 133 | 163 lines |
| `creature_neighbors()` | 337 | 32 lines |
| `normalize_spoor()` | 306 | 18 lines |
| `prey_capability()` | 427 | 14 lines |
| `predator_capability()` | 413 | 12 lines |
| `is_active()` | 381 | 11 lines |
| `room_fits()` | 326 | 9 lines |
| `hunger_of()` | 394 | 9 lines |

### `world/charter_crowd.py`

| Function | Start | Size |
|---|---:|---:|
| `members_of()` | 121 | 49 lines |
| `member_noun()` | 215 | 41 lines |
| `crowd_for()` | 329 | 40 lines |
| `crowd_face()` | 298 | 29 lines |
| `_plural()` | 183 | 22 lines |
| `engaged_turn()` | 81 | 20 lines |
| `composition_of()` | 258 | 18 lines |
| `mood_of()` | 278 | 18 lines |

### `world/charter_decide.py`

| Function | Start | Size |
|---|---:|---:|
| `mobilisation_calls()` | 208 | 57 lines |
| `advance_decisions()` | 75 | 54 lines |
| `execute_orders()` | 159 | 47 lines |
| `normalize_decisions()` | 25 | 35 lines |
| `deliver_orders()` | 131 | 26 lines |
| `decision_view()` | 267 | 7 lines |
| `_leaders()` | 67 | 6 lines |
| `_order_id()` | 62 | 3 lines |

### `world/charter_drift.py`

| Function | Start | Size |
|---|---:|---:|
| `advance_level()` | 46 | 27 lines |
| `urgency()` | 90 | 17 lines |
| `starving_input()` | 31 | 13 lines |
| `hours_until_floor()` | 75 | 13 lines |
| `supply_factor()` | 18 | 11 lines |

### `world/charter_economy.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_economy()` | 74 | 96 lines |
| `caravan_exchange()` | 375 | 64 lines |
| `ensure_supply_points()` | 172 | 48 lines |
| `advance_economy()` | 275 | 47 lines |
| `quote()` | 240 | 27 lines |
| `_holdings()` | 46 | 26 lines |
| `take_stock()` | 349 | 24 lines |
| `trade()` | 324 | 23 lines |

### `world/charter_enrol.py`

| Function | Start | Size |
|---|---:|---:|
| `enrol_person()` | 302 | 110 lines |
| `households_charter_key()` | 171 | 30 lines |
| `posts_for_role()` | 87 | 28 lines |
| `_room_distances()` | 203 | 21 lines |
| `_add_body()` | 265 | 20 lines |
| `lodging_charter_for()` | 145 | 19 lines |
| `reconcile_surface()` | 245 | 18 lines |
| `depart_guests()` | 414 | 18 lines |

### `world/charter_feel.py`

| Function | Start | Size |
|---|---:|---:|
| `appraise_window()` | 192 | 112 lines |
| `advance_feel()` | 306 | 104 lines |
| `felt_handoff()` | 440 | 30 lines |
| `normalize_feel()` | 163 | 16 lines |
| `strain_of()` | 419 | 13 lines |
| `_served_by_body()` | 181 | 9 lines |
| `_negligible()` | 412 | 5 lines |
| `overloaded_bodies()` | 434 | 4 lines |

### `world/charter_figure.py`

| Function | Start | Size |
|---|---:|---:|
| `sight_figures()` | 73 | 27 lines |
| `normalize_figures()` | 33 | 19 lines |
| `figure_claim()` | 54 | 17 lines |
| `stale_figure_claims()` | 120 | 15 lines |
| `known_figures()` | 102 | 7 lines |
| `figure_spread()` | 111 | 7 lines |

### `world/charter_generate.py`

| Function | Start | Size |
|---|---:|---:|
| `close_plan()` | 1102 | 461 lines |
| `_spread_berths()` | 819 | 140 lines |
| `_json_call()` | 282 | 100 lines |
| `_featured_assignments()` | 1015 | 85 lines |
| `_ensure_shift_crews()` | 591 | 62 lines |
| `ensure_required_rooms()` | 1593 | 60 lines |
| `narrate_actual_history()` | 1764 | 58 lines |
| `_scale_populations()` | 707 | 50 lines |

### `world/charter_harm.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_harm()` | 141 | 85 lines |
| `advance_harm()` | 228 | 29 lines |
| `_successor()` | 119 | 20 lines |
| `head_posts()` | 99 | 18 lines |
| `capability_of()` | 88 | 9 lines |
| `normalize_condition()` | 79 | 3 lines |
| `is_gone()` | 84 | 2 lines |

### `world/charter_history.py`

| Function | Start | Size |
|---|---:|---:|
| `integrate_featured_resident()` | 745 | 141 lines |
| `ground_recent_history()` | 532 | 122 lines |
| `_recent_life_context()` | 260 | 87 lines |
| `ground_personal_history()` | 452 | 78 lines |
| `resident_history_packet()` | 349 | 73 lines |
| `_record_shared_recent_history()` | 656 | 48 lines |
| `featured_resident_private_habits()` | 148 | 47 lines |
| `flesh_resident_history()` | 706 | 37 lines |

### `world/charter_identity.py`

| Function | Start | Size |
|---|---:|---:|
| `materialize_body_names()` | 1009 | 119 lines |
| `name_is_reserved()` | 640 | 65 lines |
| `refuse_harvested_material()` | 875 | 62 lines |
| `derived_name_parts()` | 230 | 43 lines |
| `_stored_name_components()` | 360 | 43 lines |
| `title_for()` | 1130 | 41 lines |
| `identity_aliases()` | 1228 | 38 lines |
| `_fill_empty_material()` | 836 | 37 lines |

### `world/charter_intervene.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_due()` | 178 | 157 lines |
| `_apply_relocate()` | 128 | 48 lines |
| `normalize_interventions()` | 82 | 29 lines |
| `normalize_mobilisation()` | 63 | 17 lines |
| `intervention_warnings()` | 113 | 5 lines |
| `watch_post_key()` | 120 | 2 lines |
| `watch_upkeep_key()` | 124 | 2 lines |

### `world/charter_log.py`

| Function | Start | Size |
|---|---:|---:|
| `scene_ledger()` | 286 | 217 lines |
| `life_of()` | 135 | 90 lines |
| `summarize()` | 63 | 70 lines |
| `own_state_of()` | 238 | 46 lines |
| `chronicle()` | 505 | 17 lines |
| `window_note()` | 46 | 15 lines |

### `world/charter_mark.py`

| Function | Start | Size |
|---|---:|---:|
| `advance_marks()` | 220 | 43 lines |
| `_normalize_row()` | 183 | 26 lines |
| `mark_view()` | 284 | 19 lines |
| `normalize_marks()` | 163 | 18 lines |
| `held_marks()` | 265 | 17 lines |
| `_number()` | 154 | 7 lines |
| `_onset()` | 211 | 7 lines |

### `world/charter_mind.py`

| Function | Start | Size |
|---|---:|---:|
| `hear_claim()` | 100 | 78 lines |
| `decay_minds()` | 180 | 28 lines |
| `hear()` | 75 | 23 lines |
| `cap_minds()` | 210 | 19 lines |
| `divergence()` | 240 | 17 lines |
| `normalize_minds()` | 39 | 12 lines |
| `claim_from()` | 53 | 9 lines |
| `see()` | 64 | 9 lines |

### `world/charter_model.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_charter()` | 499 | 411 lines |
| `normalize_body()` | 231 | 162 lines |
| `body_of_an_authored_mind()` | 395 | 58 lines |
| `normalize_post()` | 144 | 45 lines |
| `normalize_body_station()` | 191 | 38 lines |
| `normalize_upkeep()` | 111 | 31 lines |
| `_phase_set()` | 477 | 20 lines |
| `_tags()` | 72 | 15 lines |

### `world/charter_move.py`

| Function | Start | Size |
|---|---:|---:|
| `errands()` | 411 | 122 lines |
| `_advance()` | 235 | 57 lines |
| `edge_seconds()` | 112 | 47 lines |
| `continue_walks()` | 294 | 41 lines |
| `place_body()` | 596 | 39 lines |
| `walk()` | 535 | 36 lines |
| `_dispatch()` | 201 | 32 lines |
| `relocate()` | 337 | 30 lines |

### `world/charter_needs.py`

| Function | Start | Size |
|---|---:|---:|
| `advance_needs()` | 329 | 83 lines |
| `feeding_upkeep()` | 191 | 74 lines |
| `mood()` | 532 | 44 lines |
| `needs_template()` | 289 | 38 lines |
| `ensure_needs()` | 132 | 36 lines |
| `body_state()` | 584 | 32 lines |
| `pressure()` | 435 | 31 lines |
| `normalize_need()` | 97 | 23 lines |

### `world/charter_news.py`

| Function | Start | Size |
|---|---:|---:|
| `check_reports()` | 406 | 92 lines |
| `claim_from_report()` | 225 | 44 lines |
| `report_from_claim()` | 271 | 38 lines |
| `_native_news_phrase()` | 311 | 30 lines |
| `decay_news()` | 500 | 28 lines |
| `news_claim()` | 356 | 24 lines |
| `charter_hours_of()` | 187 | 23 lines |
| `witness()` | 382 | 22 lines |

### `world/charter_observe.py`

| Function | Start | Size |
|---|---:|---:|
| `plan_public_evidence()` | 428 | 154 lines |
| `body_receives_evidence()` | 90 | 84 lines |
| `resolve_target_body()` | 349 | 77 lines |
| `apply_public_evidence()` | 584 | 74 lines |
| `evidence_claim()` | 203 | 40 lines |
| `_bodies_by_role()` | 314 | 33 lines |
| `_post_forms()` | 280 | 32 lines |
| `evidence_phrase()` | 180 | 21 lines |

### `world/charter_ops.py`

| Function | Start | Size |
|---|---:|---:|
| `_check()` | 145 | 40 lines |
| `_resolve_body_name()` | 311 | 38 lines |
| `_transfer()` | 258 | 30 lines |
| `apply_charter_ops()` | 351 | 29 lines |
| `normalize_charter_op()` | 117 | 26 lines |
| `_op_upkeep_fails()` | 225 | 25 lines |
| `_op_errand()` | 197 | 8 lines |
| `_employer_of()` | 101 | 7 lines |

### `world/charter_place.py`

| Function | Start | Size |
|---|---:|---:|
| `resolve_scene_placements()` | 565 | 100 lines |
| `heal_unbound_twins()` | 386 | 73 lines |
| `charter_placements()` | 198 | 69 lines |
| `lease_scene_bodies()` | 503 | 60 lines |
| `_station_and_facing()` | 150 | 46 lines |
| `_spelling_table()` | 346 | 33 lines |
| `lay_charter_bodies()` | 300 | 29 lines |
| `rooms_in_frame()` | 281 | 17 lines |

### `world/charter_plan.py`

| Function | Start | Size |
|---|---:|---:|
| `plan_watch()` | 87 | 115 lines |
| `tended_upkeeps()` | 204 | 24 lines |
| `criticality()` | 63 | 22 lines |
| `_post_urgency()` | 25 | 17 lines |
| `_assignable_cache()` | 44 | 17 lines |

### `world/charter_politics.py`

| Function | Start | Size |
|---|---:|---:|
| `attribute_blame()` | 121 | 41 lines |
| `normalize_politics()` | 74 | 16 lines |
| `spend_reluctance()` | 109 | 10 lines |
| `regard_pair()` | 54 | 8 lines |
| `regard_value()` | 64 | 8 lines |
| `_clamp_regard()` | 92 | 6 lines |
| `regard_key()` | 49 | 3 lines |
| `regard_map()` | 104 | 3 lines |

### `world/charter_practice.py`

| Function | Start | Size |
|---|---:|---:|
| `opportunities()` | 911 | 123 lines |
| `enact()` | 1081 | 94 lines |
| `_afford_accuse()` | 657 | 70 lines |
| `_afford_ask()` | 508 | 65 lines |
| `_between()` | 322 | 51 lines |
| `offers()` | 1036 | 43 lines |
| `entanglement()` | 429 | 40 lines |
| `_afford_tell()` | 575 | 39 lines |

### `world/charter_predation.py`

| Function | Start | Size |
|---|---:|---:|
| `hunt_moves()` | 298 | 189 lines |
| `_attack()` | 502 | 146 lines |
| `predation_round()` | 650 | 122 lines |
| `_tribute()` | 855 | 95 lines |
| `run_registry()` | 998 | 60 lines |
| `_scene_figures_at()` | 213 | 55 lines |
| `read_spoor()` | 803 | 48 lines |
| `_company()` | 133 | 29 lines |

### `world/charter_promote.py`

| Function | Start | Size |
|---|---:|---:|
| `remembered()` | 111 | 268 lines |
| `inherited_place_graph()` | 514 | 99 lines |
| `acquainted()` | 414 | 65 lines |
| `promotion_handoff()` | 381 | 23 lines |
| `private_rooms()` | 490 | 22 lines |
| `_news_phrase()` | 101 | 8 lines |

### `world/charter_roster.py`

| Function | Start | Size |
|---|---:|---:|
| `assignable()` | 94 | 21 lines |
| `stale_claims()` | 117 | 18 lines |
| `seed_roster()` | 45 | 17 lines |
| `observe()` | 77 | 15 lines |
| `decay_roster()` | 64 | 11 lines |

### `world/charter_run.py`

| Function | Start | Size |
|---|---:|---:|
| `step()` | 427 | 1022 lines |
| `_record_coarse_experiences()` | 244 | 160 lines |
| `run()` | 1451 | 80 lines |
| `_remember_experience()` | 156 | 32 lines |
| `_run_private_habits()` | 213 | 29 lines |
| `_social_events()` | 111 | 25 lines |
| `_record_social_experiences()` | 190 | 21 lines |
| `_settle_commitments()` | 406 | 19 lines |

### `world/charter_runtime.py`

| Function | Start | Size |
|---|---:|---:|
| `_plan_lived_location()` | 2023 | 254 lines |
| `registry_warnings()` | 2603 | 233 lines |
| `advance_snapshot()` | 3075 | 200 lines |
| `_prepare_cast_histories()` | 1042 | 199 lines |
| `_generate_lived_location()` | 2337 | 163 lines |
| `presence_view()` | 4972 | 163 lines |
| `_remap_generated_town()` | 1739 | 144 lines |
| `_voiced_presence()` | 4734 | 120 lines |

### `world/charter_social.py`

| Function | Start | Size |
|---|---:|---:|
| `update_ties()` | 730 | 78 lines |
| `normalize_ties()` | 667 | 61 lines |
| `update_judgments_from_minds()` | 422 | 54 lines |
| `signal_landing()` | 340 | 49 lines |
| `derive_tie()` | 595 | 40 lines |
| `normalize_judgments()` | 271 | 35 lines |
| `_signals_in_claim()` | 308 | 30 lines |
| `signals_in_public_evidence()` | 391 | 29 lines |

### `world/charter_space.py`

| Function | Start | Size |
|---|---:|---:|
| `room_traffic()` | 138 | 63 lines |
| `people_neighbors()` | 32 | 39 lines |
| `walk_route()` | 96 | 39 lines |
| `reach_map()` | 248 | 38 lines |
| `commons_places()` | 296 | 32 lines |
| `_route_on()` | 202 | 25 lines |
| `travel_rooms()` | 73 | 21 lines |
| `refresh_reach()` | 229 | 17 lines |

### `world/charter_surface.py`

| Function | Start | Size |
|---|---:|---:|
| `surface_label()` | 232 | 39 lines |
| `settle_render()` | 333 | 32 lines |
| `looks_profile()` | 108 | 31 lines |
| `deal_surface()` | 159 | 28 lines |
| `appearance_text()` | 298 | 25 lines |
| `surface_words()` | 273 | 23 lines |
| `surface_of()` | 208 | 13 lines |
| `_strings()` | 74 | 11 lines |

### `world/charter_surgery.py`

| Function | Start | Size |
|---|---:|---:|
| `send_errand()` | 272 | 56 lines |
| `plant_claim()` | 170 | 33 lines |
| `adjust_stock()` | 205 | 25 lines |
| `open_summons()` | 350 | 25 lines |
| `assign_post()` | 124 | 21 lines |
| `charter_shock()` | 250 | 20 lines |
| `harm_body()` | 330 | 18 lines |
| `vacate_post()` | 147 | 17 lines |

### `world/charter_talk.py`

| Function | Start | Size |
|---|---:|---:|
| `report_to_superiors()` | 302 | 50 lines |
| `converse()` | 207 | 49 lines |
| `report_up()` | 258 | 42 lines |
| `tell_ranking()` | 88 | 38 lines |
| `co_present()` | 128 | 34 lines |
| `tellable()` | 61 | 25 lines |
| `witnessed()` | 185 | 20 lines |
| `pair_up()` | 164 | 19 lines |

### `world/charter_temper.py`

| Function | Start | Size |
|---|---:|---:|
| `temperament_warnings()` | 129 | 39 lines |
| `normalize_temperament()` | 88 | 10 lines |
| `temperament_of()` | 100 | 10 lines |
| `_lane()` | 56 | 9 lines |
| `_held()` | 67 | 9 lines |
| `derived_temperament()` | 78 | 8 lines |
| `stress_profile_of()` | 120 | 7 lines |
| `interoception_of()` | 112 | 6 lines |

### `world/charter_trigger.py`

| Function | Start | Size |
|---|---:|---:|
| `fire_triggers()` | 629 | 148 lines |
| `_normalize_rule()` | 323 | 111 lines |
| `fire_institution_rules()` | 779 | 73 lines |
| `changes_from()` | 552 | 41 lines |
| `perceivable_change()` | 285 | 36 lines |
| `_cap_changes()` | 527 | 23 lines |
| `normalize_triggers()` | 436 | 20 lines |
| `prune_trigger_last()` | 595 | 20 lines |

### `world/comfort.py`

| Function | Start | Size |
|---|---:|---:|
| `_derive()` | 240 | 82 lines |
| `_posture_of()` | 207 | 31 lines |
| `_fields()` | 134 | 12 lines |
| `_entity_record()` | 166 | 12 lines |
| `_station_of()` | 194 | 11 lines |
| `_warm()` | 152 | 8 lines |
| `comfort_level()` | 324 | 8 lines |
| `rest_affording()` | 334 | 7 lines |

### `world/crowds.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_ops()` | 362 | 188 lines |
| `talk_view()` | 727 | 44 lines |
| `emerge()` | 552 | 38 lines |
| `drift()` | 187 | 35 lines |
| `advance_crowds()` | 623 | 32 lines |
| `normalize_band()` | 101 | 29 lines |
| `absorb()` | 592 | 29 lines |
| `describe()` | 668 | 25 lines |

### `world/day_cycle.py`

| Function | Start | Size |
|---|---:|---:|
| `seconds_until()` | 513 | 91 lines |
| `sun_light()` | 223 | 49 lines |
| `clock_hour()` | 400 | 38 lines |
| `clock_anchor()` | 349 | 33 lines |
| `clock_reading_hour()` | 278 | 24 lines |
| `display_hour()` | 440 | 23 lines |
| `charter_phase()` | 469 | 21 lines |
| `label_phase()` | 304 | 19 lines |

### `world/degradation.py`

| Function | Start | Size |
|---|---:|---:|
| `degrade()` | 110 | 27 lines |
| `lost_at()` | 153 | 19 lines |
| `_replace_phrases()` | 94 | 14 lines |
| `is_exhausted()` | 139 | 12 lines |
| `_collapse()` | 90 | 2 lines |

### `world/exposure.py`

| Function | Start | Size |
|---|---:|---:|
| `_derive()` | 151 | 57 lines |
| `_bare_fraction()` | 102 | 30 lines |
| `_wets()` | 134 | 15 lines |
| `discomfort_level()` | 218 | 15 lines |
| `_float()` | 210 | 6 lines |

### `world/frontage.py`

| Function | Start | Size |
|---|---:|---:|
| `_lay_siblings()` | 830 | 152 lines |
| `_place()` | 414 | 105 lines |
| `_lay_annexes()` | 988 | 92 lines |
| `_measure_street()` | 625 | 90 lines |
| `_take_back()` | 1082 | 90 lines |
| `_lay_block()` | 730 | 41 lines |
| `_freeze()` | 586 | 37 lines |
| `lay_frontages()` | 1174 | 37 lines |

### `world/gaps.py`

| Function | Start | Size |
|---|---:|---:|
| `_skeleton()` | 128 | 175 lines |
| `last_seen_update()` | 349 | 75 lines |
| `gap_for()` | 305 | 38 lines |
| `interim_for()` | 426 | 34 lines |
| `_record()` | 86 | 20 lines |
| `_subject_room()` | 114 | 12 lines |
| `_read_key()` | 73 | 4 lines |
| `_unavailable()` | 108 | 4 lines |

### `world/landscape.py`

| Function | Start | Size |
|---|---:|---:|
| `far_places()` | 757 | 386 lines |
| `looked_far()` | 1145 | 111 lines |
| `standing_looks_wanted()` | 1654 | 108 lines |
| `_place_forms()` | 1273 | 60 lines |
| `_said_as_a_word()` | 1335 | 48 lines |
| `_between()` | 665 | 45 lines |
| `_admit_look()` | 1416 | 43 lines |
| `_building_fronts()` | 1567 | 34 lines |

### `world/layout_arrange.py`

| Function | Start | Size |
|---|---:|---:|
| `_sub_rects()` | 2665 | 40 lines |
| `_sealed()` | 2831 | 38 lines |
| `_chk_cost()` | 2604 | 33 lines |
| `_reached()` | 2871 | 30 lines |
| `_steps()` | 2716 | 29 lines |
| `_hall_past()` | 752 | 25 lines |
| `_hall_fits()` | 723 | 24 lines |
| `solve_arranged()` | 5149 | 21 lines |

### `world/layout_bridge.py`

| Function | Start | Size |
|---|---:|---:|
| `planned_layout()` | 2888 | 484 lines |
| `_ground_plan()` | 1515 | 429 lines |
| `ground_breaches()` | 2273 | 350 lines |
| `spec_from_answers()` | 1267 | 246 lines |
| `_building()` | 709 | 224 lines |
| `hold_inventory()` | 1021 | 108 lines |
| `_ground_geometry()` | 3450 | 87 lines |
| `_stair_halls()` | 3590 | 79 lines |

### `world/layout_solver.py`

| Function | Start | Size |
|---|---:|---:|
| `_grounds()` | 2870 | 568 lines |
| `_place_fixtures()` | 2361 | 209 lines |
| `_place_blocks()` | 674 | 168 lines |
| `_place_doors()` | 1957 | 154 lines |
| `_things_at_doors()` | 2588 | 138 lines |
| `_doors_onto_their_ground()` | 2743 | 125 lines |
| `_prepare()` | 1495 | 107 lines |
| `_search()` | 1628 | 106 lines |

### `world/living_world.py`

| Function | Start | Size |
|---|---:|---:|
| `mint_consequences()` | 377 | 100 lines |
| `record_obligations()` | 530 | 53 lines |
| `living_world_levels()` | 313 | 33 lines |
| `fired_consequences_at()` | 479 | 31 lines |
| `attach_owed_history()` | 611 | 29 lines |
| `effective_depth()` | 270 | 27 lines |
| `owed_history()` | 585 | 24 lines |
| `normalize_living_world()` | 231 | 20 lines |

### `world/mechanics.py`

| Function | Start | Size |
|---|---:|---:|
| `_fire_due_events()` | 699 | 173 lines |
| `_tick_conditions()` | 1236 | 130 lines |
| `read_time_diff()` | 195 | 110 lines |
| `_schedule_new_arrivals()` | 908 | 92 lines |
| `mechanics_sweep()` | 1525 | 78 lines |
| `beat_time_block()` | 454 | 64 lines |
| `beat_time_from_spans()` | 333 | 55 lines |
| `unanswered_hazard_subjects()` | 1462 | 49 lines |

### `world/offscreen.py`

| Function | Start | Size |
|---|---:|---:|
| `land_agent_tick()` | 1999 | 187 lines |
| `advance_epoch()` | 1023 | 122 lines |
| `apply_plan_ops()` | 768 | 120 lines |
| `schedule_agent_ticks()` | 2188 | 118 lines |
| `agent_context()` | 1660 | 115 lines |
| `schedule_profile_ticks()` | 1482 | 112 lines |
| `advance_reactive_plans()` | 936 | 85 lines |
| `profile_summary_record()` | 1228 | 85 lines |

### `world/paradox.py`

| Function | Start | Size |
|---|---:|---:|
| `check_and_apply_paradox()` | 591 | 65 lines |
| `_apply_toll()` | 313 | 62 lines |
| `_force_restore_anchor()` | 543 | 46 lines |
| `_advance_paradox()` | 505 | 36 lines |
| `_trigger_paradox()` | 470 | 33 lines |
| `_apply_warden_stage()` | 401 | 29 lines |
| `_apply_hazard_stage()` | 283 | 28 lines |
| `_project_entity_row()` | 377 | 22 lines |

### `world/place_names.py`

| Function | Start | Size |
|---|---:|---:|
| `deal_place_name()` | 194 | 67 lines |
| `_frame()` | 80 | 31 lines |
| `pattern_filler()` | 113 | 11 lines |
| `resident_name_words()` | 148 | 11 lines |
| `spelling_key()` | 161 | 10 lines |
| `instance_of()` | 126 | 9 lines |
| `standing_fillers()` | 137 | 9 lines |
| `_opens_like()` | 183 | 9 lines |

### `world/place_purpose.py`

| Function | Start | Size |
|---|---:|---:|
| `mirror_told_affords()` | 366 | 91 lines |
| `witness_affords()` | 290 | 68 lines |
| `here_affords()` | 227 | 56 lines |
| `place_options()` | 498 | 43 lines |
| `_walked_hops()` | 476 | 20 lines |
| `felt_needs()` | 459 | 15 lines |
| `assumed_affords()` | 213 | 12 lines |
| `affords_here()` | 543 | 12 lines |

### `world/planned_entities.py`

| Function | Start | Size |
|---|---:|---:|
| `materialize_plans_in_sight()` | 290 | 168 lines |
| `normalize_plan()` | 123 | 96 lines |
| `project_planned_emissions()` | 227 | 61 lines |
| `plan_figure()` | 570 | 43 lines |
| `plan_state()` | 79 | 42 lines |
| `settle_rendered_plans()` | 652 | 41 lines |
| `_station_a_thing()` | 460 | 40 lines |
| `plan_answering()` | 506 | 26 lines |

### `world/planning_needs.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_need()` | 156 | 57 lines |
| `drain_planning_needs()` | 369 | 44 lines |
| `_fold_need()` | 270 | 27 lines |
| `record_planning_needs()` | 312 | 26 lines |
| `schedule_planning_needs()` | 415 | 25 lines |
| `planning_need()` | 215 | 17 lines |
| `fill_planning_need()` | 340 | 14 lines |
| `normalize_planning_needs()` | 234 | 12 lines |

### `world/region_events.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_wave()` | 277 | 142 lines |
| `normalize_region_event()` | 78 | 67 lines |
| `resolve_footprint()` | 169 | 46 lines |
| `plan_waves()` | 221 | 37 lines |
| `_stand_hazard()` | 421 | 31 lines |
| `_graph()` | 157 | 10 lines |
| `_decay_steps()` | 260 | 6 lines |
| `harms_a_body()` | 147 | 4 lines |

### `world/regions.py`

| Function | Start | Size |
|---|---:|---:|
| `backfill_regions()` | 679 | 65 lines |
| `inherit_regions()` | 510 | 55 lines |
| `normalize_regions()` | 78 | 52 lines |
| `lay_planned_region_far_look()` | 299 | 52 lines |
| `assign_regions()` | 567 | 50 lines |
| `room_pieces()` | 623 | 50 lines |
| `set_region_far_look()` | 231 | 34 lines |
| `set_region_look()` | 198 | 31 lines |

### `world/routines.py`

| Function | Start | Size |
|---|---:|---:|
| `residue_for()` | 194 | 63 lines |
| `entropy_facts()` | 165 | 27 lines |
| `routine_band()` | 117 | 25 lines |
| `occupancy_fact()` | 144 | 19 lines |
| `_roll()` | 106 | 9 lines |
| `_day_span()` | 97 | 7 lines |

### `world/scene_memo.py`

| Function | Start | Size |
|---|---:|---:|
| `scene_memo()` | 181 | 21 lines |
| `_fingerprint()` | 110 | 14 lines |
| `scene_read_parts()` | 96 | 12 lines |
| `clear_scene_memo()` | 204 | 3 lines |

### `world/site_plan.py`

| Function | Start | Size |
|---|---:|---:|
| `_layout()` | 974 | 408 lines |
| `_lay_group()` | 1384 | 112 lines |
| `_derive()` | 1498 | 93 lines |
| `plan_sight()` | 341 | 51 lines |
| `_spots()` | 743 | 36 lines |
| `_window_on_line()` | 290 | 35 lines |
| `_links()` | 814 | 34 lines |
| `derive_site_plans()` | 1622 | 33 lines |

### `world/spatial_barriers.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_barrier()` | 331 | 82 lines |
| `neighbor_map()` | 597 | 80 lines |
| `effective_adjacent()` | 753 | 73 lines |
| `normalize_scene_passages()` | 907 | 54 lines |
| `normalize_scene_barriers()` | 469 | 32 lines |
| `passage_direction()` | 679 | 28 lines |
| `_barrier_against_its_own_name()` | 514 | 27 lines |
| `barrier_fastening()` | 415 | 24 lines |

### `world/spatial_bubbles.py`

| Function | Start | Size |
|---|---:|---:|
| `bubble_split_decision()` | 276 | 132 lines |
| `detect_bubble()` | 524 | 53 lines |
| `couple_decision()` | 413 | 52 lines |
| `uncouple_decision()` | 470 | 46 lines |
| `detect_sibling_meeting()` | 637 | 38 lines |
| `_cross_link()` | 130 | 35 lines |
| `_clusters()` | 248 | 26 lines |
| `sibling_meet_decision()` | 609 | 26 lines |

### `world/spatial_contact_migration.py`

| Function | Start | Size |
|---|---:|---:|
| `contacts_from_entity_state()` | 82 | 137 lines |
| `_lift_valued_contact()` | 236 | 56 lines |
| `_drop_contradicted_state()` | 294 | 39 lines |
| `_part_from_key()` | 72 | 8 lines |
| `_manner_from_fragment()` | 64 | 6 lines |

### `world/spatial_contacts.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_contact_ops()` | 1396 | 444 lines |
| `_clean_contact()` | 928 | 168 lines |
| `normalize_scene_contacts()` | 1246 | 94 lines |
| `contacts_across_enclosure()` | 1138 | 68 lines |
| `_mirrored_displacements()` | 335 | 50 lines |
| `_unnamed_touch_between_bodies()` | 869 | 47 lines |
| `contact_thing_label()` | 797 | 42 lines |
| `_anchor_room_of()` | 755 | 40 lines |

### `world/spatial_containment.py`

| Function | Start | Size |
|---|---:|---:|
| `derive_inventory_placements()` | 1686 | 260 lines |
| `materialize_named_stations()` | 3177 | 135 lines |
| `advance_room_transits()` | 3314 | 130 lines |
| `replace_engine_minted_interiors()` | 2662 | 123 lines |
| `place_enclosed_bodies()` | 2787 | 108 lines |
| `mint_transferred_objects()` | 1580 | 104 lines |
| `release_declared_departures()` | 3458 | 97 lines |
| `materialize_enclosure_interiors()` | 2522 | 93 lines |

### `world/spatial_fov.py`

| Function | Start | Size |
|---|---:|---:|
| `body_visibility()` | 2498 | 155 lines |
| `body_cell()` | 1304 | 136 lines |
| `feature_visibility()` | 2225 | 112 lines |
| `_place_anchor()` | 809 | 105 lines |
| `_stand_cell()` | 1191 | 80 lines |
| `neighbour_feature_visibility()` | 2370 | 71 lines |
| `_room_field()` | 1863 | 59 lines |
| `_placed_neighbours()` | 1771 | 55 lines |

### `world/spatial_frames.py`

| Function | Start | Size |
|---|---:|---:|
| `infer_focus()` | 463 | 245 lines |
| `perform_split()` | 1223 | 202 lines |
| `open_couple()` | 2155 | 180 lines |
| `detect_and_reconcile()` | 2580 | 139 lines |
| `infer_facing()` | 810 | 132 lines |
| `perform_sibling_merge()` | 1792 | 123 lines |
| `_partition_side()` | 2384 | 105 lines |
| `infer_threshold_crossings()` | 323 | 96 lines |

### `world/spatial_geometry.py`

| Function | Start | Size |
|---|---:|---:|
| `_effective_anchors()` | 459 | 152 lines |
| `invalidate_transferred_pose_details()` | 1972 | 113 lines |
| `spatial_digest()` | 150 | 107 lines |
| `derive_scene_stations()` | 2322 | 104 lines |
| `invalidate_moved_body_place_details()` | 1764 | 102 lines |
| `egocentric_frame()` | 62 | 86 lines |
| `invalidate_moved_body_pose_details()` | 1654 | 79 lines |
| `invalidate_contact_bound_poses()` | 2087 | 75 lines |

### `world/spatial_identity.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_scene_subjects()` | 596 | 136 lines |
| `canonical_subject_map()` | 498 | 87 lines |
| `scene_names_body()` | 343 | 73 lines |
| `room_of()` | 92 | 68 lines |
| `scene_room_id()` | 828 | 57 lines |
| `_live_subject_spellings()` | 444 | 52 lines |
| `room_of_record()` | 162 | 37 lines |
| `_positions_lookup()` | 10 | 28 lines |

### `world/spatial_levels.py`

| Function | Start | Size |
|---|---:|---:|
| `infer_room_levels()` | 143 | 44 lines |
| `_edges()` | 101 | 21 lines |
| `floor_edges()` | 226 | 20 lines |
| `_over_pairs()` | 129 | 12 lines |
| `stack_of()` | 203 | 12 lines |
| `normalize_level()` | 63 | 8 lines |
| `declared_way()` | 82 | 8 lines |
| `edge_way()` | 73 | 7 lines |

### `world/spatial_light.py`

| Function | Start | Size |
|---|---:|---:|
| `room_light()` | 49 | 70 lines |
| `aim_of()` | 413 | 64 lines |
| `unsourced_light_rooms()` | 195 | 63 lines |
| `light_at()` | 702 | 57 lines |
| `source_light()` | 315 | 51 lines |
| `effective_light()` | 761 | 39 lines |
| `unsourced_light_notices()` | 268 | 34 lines |
| `_lamp_reach()` | 547 | 34 lines |

### `world/spatial_light_field.py`

| Function | Start | Size |
|---|---:|---:|
| `light_shape()` | 1231 | 133 lines |
| `light_sources()` | 591 | 98 lines |
| `_resolve_pointed_at()` | 522 | 67 lines |
| `compute_light_field()` | 915 | 67 lines |
| `_bounce()` | 807 | 59 lines |
| `_spill()` | 868 | 45 lines |
| `_aimed_at()` | 1410 | 43 lines |
| `held_beam_falls_on()` | 1366 | 42 lines |

### `world/spatial_lint.py`

| Function | Start | Size |
|---|---:|---:|
| `leaf_rows()` | 591 | 95 lines |
| `layout_warning()` | 779 | 76 lines |
| `layout_rooms()` | 397 | 69 lines |
| `room_layout_lint()` | 724 | 53 lines |
| `wall_loads()` | 186 | 49 lines |
| `_wall_rows()` | 243 | 43 lines |
| `_leaf_in_walk()` | 547 | 42 lines |
| `_shape_rows()` | 92 | 40 lines |

### `world/spatial_listener.py`

| Function | Start | Size |
|---|---:|---:|
| `own_noise_db()` | 244 | 58 lines |
| `_contact_cover_db()` | 185 | 53 lines |
| `movement_heard_at_ear()` | 664 | 45 lines |
| `voice_at_ear_db()` | 544 | 37 lines |
| `garment_over_ears_db()` | 147 | 36 lines |
| `next_hearing_ledger()` | 406 | 36 lines |
| `ear_cover_db()` | 119 | 26 lines |
| `loudest_at_ear()` | 466 | 25 lines |

### `world/spatial_merge.py`

| Function | Start | Size |
|---|---:|---:|
| `merge_scene_with_diff()` | 1817 | 890 lines |
| `_expire_transient_entity_state()` | 688 | 116 lines |
| `_merge_room()` | 192 | 115 lines |
| `_shield_standing_bearings()` | 970 | 107 lines |
| `sync_scene_passages()` | 1512 | 97 lines |
| `_shield_minted_edges()` | 1236 | 95 lines |
| `beat_movement_cuts()` | 2835 | 94 lines |
| `_mirror_symmetric_barriers()` | 1141 | 93 lines |

### `world/spatial_orientation.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_scene_bearings()` | 186 | 173 lines |
| `derived_edge_bearings()` | 398 | 71 lines |
| `strip_one_storey_verticals()` | 153 | 31 lines |
| `_spread_along_wall()` | 361 | 21 lines |
| `travel_bearing()` | 133 | 18 lines |
| `relative_bearing()` | 97 | 11 lines |
| `lateral_of()` | 110 | 11 lines |
| `turn_bearing()` | 64 | 10 lines |

### `world/spatial_pack.py`

| Function | Start | Size |
|---|---:|---:|
| `pack_anchors()` | 158 | 159 lines |
| `_full_lines()` | 514 | 107 lines |
| `doorway_places()` | 319 | 83 lines |
| `_end_to_end()` | 404 | 44 lines |
| `_would_fit()` | 450 | 21 lines |
| `_clear_on_the_map()` | 497 | 15 lines |
| `_along_wall()` | 115 | 13 lines |
| `_with_pins()` | 484 | 11 lines |

### `world/spatial_prose.py`

| Function | Start | Size |
|---|---:|---:|
| `contact_sensation()` | 151 | 172 lines |
| `contact_phrase()` | 60 | 89 lines |
| `spatial_facts()` | 325 | 86 lines |
| `_interior_label()` | 28 | 30 lines |

### `world/spatial_routing.py`

| Function | Start | Size |
|---|---:|---:|
| `sprint_reach()` | 1163 | 180 lines |
| `visible_adjacent_rooms()` | 1413 | 155 lines |
| `spatial_rel()` | 362 | 109 lines |
| `corridor_sightlines()` | 998 | 106 lines |
| `_onward_exits()` | 1345 | 66 lines |
| `_walk_steps()` | 862 | 65 lines |
| `attended_rooms()` | 493 | 61 lines |
| `rooms_walked_within()` | 754 | 54 lines |

### `world/spatial_scent_field.py`

| Function | Start | Size |
|---|---:|---:|
| `advance_scents()` | 143 | 53 lines |
| `normalize_scents()` | 87 | 28 lines |
| `scent_gradient()` | 215 | 19 lines |
| `scent_edges()` | 124 | 17 lines |
| `scent_word()` | 204 | 9 lines |
| `_keep()` | 117 | 5 lines |
| `scent_at()` | 198 | 4 lines |
| `normalize_scent_level()` | 82 | 3 lines |

### `world/spatial_senses.py`

| Function | Start | Size |
|---|---:|---:|
| `_hear_level()` | 1670 | 167 lines |
| `_opening_view_cap()` | 851 | 154 lines |
| `spatial_rel_between()` | 667 | 128 lines |
| `_visual_level_between()` | 1052 | 94 lines |
| `comms_reachable_rooms()` | 280 | 66 lines |
| `comms_link()` | 376 | 66 lines |
| `hearing_reason()` | 1839 | 65 lines |
| `scent_level()` | 39 | 56 lines |

### `world/spatial_sound_field.py`

| Function | Start | Size |
|---|---:|---:|
| `sound_sources()` | 2008 | 176 lines |
| `stamp_sound_relation()` | 3370 | 134 lines |
| `_voice_flood()` | 4789 | 98 lines |
| `room_sound_flood()` | 4697 | 90 lines |
| `spread()` | 1659 | 88 lines |
| `sound_shape()` | 5186 | 80 lines |
| `doorway_air_loss_db()` | 2725 | 74 lines |
| `distant_sounds()` | 4985 | 69 lines |

### `world/spatial_substance.py`

| Function | Start | Size |
|---|---:|---:|
| `_resolved_substance_add()` | 292 | 144 lines |
| `speech_articulation_impediment()` | 96 | 101 lines |
| `apply_contact_action_ops()` | 1067 | 90 lines |
| `apply_substance_ops()` | 726 | 62 lines |
| `_same_pool()` | 480 | 50 lines |
| `_stock_consumed_by()` | 593 | 48 lines |
| `_standing_substance_pools()` | 678 | 46 lines |
| `_substance_target_exists()` | 249 | 41 lines |

### `world/spatial_transit.py`

| Function | Start | Size |
|---|---:|---:|
| `settle_departures()` | 961 | 266 lines |
| `apply_transit_dock_edges()` | 688 | 236 lines |
| `evict_self_contained_entities()` | 486 | 89 lines |
| `sync_entity_interior_rooms()` | 138 | 84 lines |
| `journey_seconds()` | 1314 | 76 lines |
| `_release_dock_passages()` | 626 | 60 lines |
| `settle_link_conditions()` | 418 | 50 lines |
| `_is_body_entity()` | 63 | 49 lines |

### `world/spatial_walk.py`

| Function | Start | Size |
|---|---:|---:|
| `walk()` | 357 | 183 lines |
| `cell_path()` | 170 | 36 lines |
| `landing_cell()` | 270 | 36 lines |
| `_path_past_fixtures()` | 208 | 23 lines |
| `held_cells()` | 95 | 21 lines |
| `beside_named()` | 308 | 21 lines |
| `door_cell()` | 118 | 19 lines |
| `inside_the_door()` | 153 | 15 lines |

### `world/stimulation.py`

| Function | Start | Size |
|---|---:|---:|
| `stimulation_of()` | 134 | 106 lines |
| `responsive_regions()` | 78 | 23 lines |
| `_region_is_bare()` | 118 | 14 lines |
| `_body_is_unclothed()` | 103 | 13 lines |

### `world/structure.py`

| Function | Start | Size |
|---|---:|---:|
| `claim_frontier_spaces()` | 2843 | 207 lines |
| `mint_frontier()` | 1159 | 197 lines |
| `plant_structure()` | 1358 | 191 lines |
| `prepare_frontier_expansion()` | 2613 | 174 lines |
| `materialize_planned_fringe()` | 1551 | 149 lines |
| `hold_planned_fixtures()` | 2107 | 141 lines |
| `planned_room_brief()` | 1955 | 97 lines |
| `apply_planned_layout()` | 238 | 94 lines |

### `world/subjects.py`

| Function | Start | Size |
|---|---:|---:|
| `_resolve_room()` | 281 | 47 lines |
| `resolve_subject()` | 438 | 45 lines |
| `_resolve_character()` | 199 | 32 lines |
| `_lore_matches()` | 334 | 29 lines |
| `_resolve_from_lore()` | 365 | 29 lines |
| `_cast_matches()` | 121 | 27 lines |
| `_presence_reason()` | 171 | 26 lines |
| `_registry_room_matches()` | 254 | 25 lines |

### `world/survival.py`

| Function | Start | Size |
|---|---:|---:|
| `tick_vitals()` | 343 | 75 lines |
| `apply_vitals_diff()` | 420 | 45 lines |
| `is_sealed_in()` | 249 | 36 lines |
| `vitals_entry_key()` | 174 | 24 lines |
| `vitals_facts()` | 467 | 23 lines |
| `seed_vitals()` | 200 | 22 lines |
| `_stored_vitals()` | 151 | 21 lines |
| `add_air_denied()` | 303 | 19 lines |

### `world/vistas.py`

| Function | Start | Size |
|---|---:|---:|
| `obstructed()` | 245 | 47 lines |
| `visible_vistas()` | 294 | 42 lines |
| `normalize_vista()` | 72 | 40 lines |
| `what_a_look_finds()` | 361 | 31 lines |
| `air_from_weather()` | 187 | 19 lines |
| `outlooks()` | 222 | 17 lines |
| `looked_vistas()` | 342 | 17 lines |
| `beyond_the_horizon()` | 147 | 16 lines |

### `world/weather.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_weather()` | 436 | 170 lines |
| `weather_for_room()` | 1005 | 89 lines |
| `weather_course()` | 1376 | 77 lines |
| `weather_depth()` | 874 | 57 lines |
| `ground_after()` | 1591 | 52 lines |
| `weather_sound_words()` | 1171 | 38 lines |
| `weather_words()` | 1134 | 35 lines |
| `_derive_exposure()` | 706 | 32 lines |

## FastAPI routes

| Method | Path | Handler | Source |
|---|---|---|---|
| GET | `/` | `index()` | `web/app.py:685` |
| PUT | `/api/active_preset` | `set_active()` | `web/app.py:2668` |
| PUT | `/api/affect_habituation` | `set_affect_habituation()` | `web/app.py:2964` |
| PUT | `/api/agent_models` | `put_agent_models()` | `web/app.py:2104` |
| PUT | `/api/ambience` | `put_ambience()` | `web/app.py:2290` |
| GET | `/api/ambience/library` | `ambience_library()` | `web/app.py:8252` |
| GET | `/api/ambience/search` | `ambience_search()` | `web/app.py:8231` |
| PUT | `/api/attire_beneath` | `set_attire_beneath()` | `web/app.py:2983` |
| POST | `/api/auth/login` | `auth_login()` | `web/auth_routes.py:209` |
| POST | `/api/auth/logout` | `auth_logout()` | `web/auth_routes.py:275` |
| POST | `/api/auth/setup` | `auth_setup()` | `web/auth_routes.py:134` |
| GET | `/api/auth/status` | `auth_status()` | `web/auth_routes.py:124` |
| GET | `/api/auto_promote` | `get_auto_promote()` | `web/app.py:5000` |
| PUT | `/api/auto_promote` | `set_auto_promote()` | `web/app.py:5013` |
| PUT | `/api/backdrops` | `put_backdrops()` | `web/app.py:2280` |
| GET | `/api/bootstrap` | `bootstrap_response()` | `web/app.py:1876` |
| POST | `/api/characters` | `char_create()` | `web/app.py:3479` |
| POST | `/api/characters/generate` | `char_generate()` | `web/app.py:3456` |
| POST | `/api/characters/import` | `char_import()` | `web/app.py:3504` |
| DELETE | `/api/characters/{cid}` | `char_del()` | `web/app.py:3845` |
| PUT | `/api/characters/{cid}` | `char_edit()` | `web/app.py:3816` |
| GET | `/api/characters/{cid}/export` | `char_export()` | `web/app.py:3808` |
| POST | `/api/characters/{cid}/fill_appearance` | `char_fill_appearance()` | `web/app.py:3787` |
| POST | `/api/characters/{cid}/fill_interior` | `char_fill_interior()` | `web/app.py:3741` |
| POST | `/api/characters/{cid}/fill_psychology` | `char_fill_psychology()` | `web/app.py:3706` |
| POST | `/api/characters/{cid}/generate_greeting` | `char_generate_greeting()` | `web/app.py:3676` |
| POST | `/api/characters/{cid}/recover_greetings` | `char_recover_greetings()` | `web/app.py:3666` |
| POST | `/api/characters/{cid}/start` | `character_start_story()` | `web/app.py:3528` |
| POST | `/api/chats` | `chat_new()` | `web/app.py:4278` |
| POST | `/api/chats/import` | `import_chat()` | `persist/chat_archive.py:274` |
| DELETE | `/api/chats/{cid}` | `chat_del()` | `web/app.py:4514` |
| GET | `/api/chats/{cid}` | `chat_get()` | `web/app.py:4522` |
| PUT | `/api/chats/{cid}` | `chat_edit()` | `web/app.py:4376` |
| POST | `/api/chats/{cid}/abort` | `chat_abort()` | `web/app.py:6910` |
| GET | `/api/chats/{cid}/ambience/oneshot/{name}` | `ambience_oneshot()` | `web/app.py:8261` |
| DELETE | `/api/chats/{cid}/ambience/pin` | `ambience_pin_delete()` | `web/app.py:8309` |
| PUT | `/api/chats/{cid}/ambience/pin` | `ambience_pin_put()` | `web/app.py:8290` |
| GET | `/api/chats/{cid}/ambience/pins` | `ambience_pins_get()` | `web/app.py:8285` |
| GET | `/api/chats/{cid}/ambience/{signature}.audio` | `ambience_audio()` | `web/app.py:8215` |
| GET | `/api/chats/{cid}/attire` | `attire_get()` | `web/app.py:5874` |
| PUT | `/api/chats/{cid}/attire` | `attire_put()` | `web/app.py:5885` |
| GET | `/api/chats/{cid}/backdrop/{signature}.png` | `backdrop_image()` | `web/app.py:8054` |
| GET | `/api/chats/{cid}/background_config` | `bg_cfg_get()` | `web/app.py:6219` |
| PUT | `/api/chats/{cid}/background_config` | `bg_cfg_put()` | `web/app.py:6223` |
| POST | `/api/chats/{cid}/begin` | `chat_begin()` | `web/app.py:3636` |
| DELETE | `/api/chats/{cid}/bodies/{name}` | `body_presence_delete()` | `web/world_routes.py:2392` |
| PUT | `/api/chats/{cid}/bodies/{name}/pose` | `body_pose_put()` | `web/world_routes.py:2477` |
| PUT | `/api/chats/{cid}/bodies/{name}/room` | `body_room_put()` | `web/world_routes.py:2426` |
| PUT | `/api/chats/{cid}/bodies/{name}/station` | `body_station_put()` | `web/world_routes.py:1991` |
| POST | `/api/chats/{cid}/characters` | `chat_add_char()` | `web/app.py:4839` |
| DELETE | `/api/chats/{cid}/characters/{ch}` | `chat_del_char()` | `web/app.py:5382` |
| PUT | `/api/chats/{cid}/characters/{ch}/card` | `chat_char_card_put()` | `web/app.py:5396` |
| PUT | `/api/chats/{cid}/characters/{ch}/dialogue_color` | `dialogue_color_put()` | `web/app.py:5742` |
| POST | `/api/chats/{cid}/characters/{ch}/fill_appearance` | `chat_char_fill_appearance()` | `web/app.py:3794` |
| POST | `/api/chats/{cid}/characters/{ch}/fill_interior` | `chat_char_fill_interior()` | `web/app.py:3752` |
| POST | `/api/chats/{cid}/characters/{ch}/fill_psychology` | `chat_char_fill_psychology()` | `web/app.py:3713` |
| GET | `/api/chats/{cid}/characters/{ch}/memories` | `mem_list()` | `web/app.py:6469` |
| POST | `/api/chats/{cid}/characters/{ch}/memories` | `mem_add()` | `web/app.py:6616` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/backfill` | `mem_backfill()` | `web/app.py:6586` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/consolidate` | `mem_consolidate()` | `web/app.py:6571` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/coverage` | `mem_coverage()` | `web/app.py:6607` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/export` | `mem_export()` | `web/app.py:6515` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/import` | `mem_import()` | `web/app.py:6526` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/search` | `mem_search()` | `web/app.py:6490` |
| GET | `/api/chats/{cid}/characters/{ch}/memory-context` | `memory_context_preview()` | `web/app.py:6547` |
| PUT | `/api/chats/{cid}/characters/{ch}/position` | `chat_char_position_put()` | `web/app.py:5630` |
| GET | `/api/chats/{cid}/characters/{ch}/private_history` | `ph_get()` | `web/app.py:5715` |
| PUT | `/api/chats/{cid}/characters/{ch}/private_history` | `ph_put()` | `web/app.py:5730` |
| GET | `/api/chats/{cid}/characters/{ch}/relationships` | `relationships_get()` | `web/app.py:6560` |
| GET | `/api/chats/{cid}/charters` | `charters_get()` | `web/app.py:6110` |
| PUT | `/api/chats/{cid}/charters` | `charters_put()` | `web/app.py:6131` |
| GET | `/api/chats/{cid}/charters/diagnostics` | `charters_diagnostics()` | `web/app.py:6149` |
| POST | `/api/chats/{cid}/charters/generate` | `charters_generate()` | `web/app.py:6161` |
| DELETE | `/api/chats/{cid}/charters/job` | `charters_job_clear()` | `web/app.py:6202` |
| GET | `/api/chats/{cid}/charters/job` | `charters_job_get()` | `web/app.py:6183` |
| DELETE | `/api/chats/{cid}/charters/{charter_key}/bodies/{body_key}/station` | `charter_body_station_delete()` | `web/world_routes.py:2879` |
| PUT | `/api/chats/{cid}/charters/{charter_key}/bodies/{body_key}/station` | `charter_body_station_put()` | `web/world_routes.py:2812` |
| GET | `/api/chats/{cid}/debug` | `chat_debug_export()` | `web/app.py:2631` |
| GET | `/api/chats/{cid}/dialogue_config` | `dlg_get()` | `web/app.py:5948` |
| PUT | `/api/chats/{cid}/dialogue_config` | `dlg_put()` | `web/app.py:5965` |
| POST | `/api/chats/{cid}/doorways` | `doorway_create()` | `web/world_routes.py:2620` |
| DELETE | `/api/chats/{cid}/doorways/{room_id}/{to}` | `doorway_delete()` | `web/world_routes.py:2695` |
| PATCH | `/api/chats/{cid}/doorways/{room_id}/{to}` | `doorway_patch()` | `web/world_routes.py:2659` |
| GET | `/api/chats/{cid}/dramatic_irony` | `get_dramatic_irony_feed()` | `web/app.py:4942` |
| GET | `/api/chats/{cid}/export` | `export_chat()` | `persist/chat_archive.py:268` |
| GET | `/api/chats/{cid}/fixed_points` | `fixed_points_list()` | `web/app.py:6414` |
| POST | `/api/chats/{cid}/fixed_points` | `fixed_points_create()` | `web/app.py:6424` |
| DELETE | `/api/chats/{cid}/fixed_points/{anchor_id}` | `fixed_points_delete()` | `web/app.py:6446` |
| GET | `/api/chats/{cid}/frames` | `frames_list()` | `web/app.py:6368` |
| POST | `/api/chats/{cid}/frames` | `frames_create()` | `web/app.py:6372` |
| GET | `/api/chats/{cid}/guest_invites` | `list_guest_invites()` | `web/app.py:5200` |
| POST | `/api/chats/{cid}/guest_invites` | `create_guest_invite()` | `web/app.py:5180` |
| DELETE | `/api/chats/{cid}/guest_invites/{gid}` | `revoke_guest_invite()` | `web/app.py:5204` |
| GET | `/api/chats/{cid}/language` | `chat_language_get()` | `web/app.py:4343` |
| PUT | `/api/chats/{cid}/language` | `chat_language_put()` | `web/app.py:4360` |
| GET | `/api/chats/{cid}/living_world` | `living_world_get()` | `web/app.py:6075` |
| PUT | `/api/chats/{cid}/living_world` | `living_world_put()` | `web/app.py:6098` |
| DELETE | `/api/chats/{cid}/lorebook` | `detach_lore()` | `web/app.py:4507` |
| POST | `/api/chats/{cid}/lorebook` | `bind_lore()` | `web/app.py:4483` |
| GET | `/api/chats/{cid}/lorebooks` | `chat_lorebooks_owned()` | `web/app.py:3067` |
| POST | `/api/chats/{cid}/lorebooks` | `attach_lore()` | `web/app.py:4407` |
| DELETE | `/api/chats/{cid}/lorebooks/{lid}` | `detach_book()` | `web/app.py:4470` |
| PUT | `/api/chats/{cid}/lorebooks/{lid}` | `set_book_enabled()` | `web/app.py:4436` |
| GET | `/api/chats/{cid}/map` | `map_index()` | `web/world_routes.py:1372` |
| GET | `/api/chats/{cid}/map/plan` | `map_plan()` | `web/world_routes.py:1384` |
| GET | `/api/chats/{cid}/naming_profile` | `naming_profile_get()` | `web/app.py:6249` |
| PUT | `/api/chats/{cid}/naming_profile` | `naming_profile_put()` | `web/app.py:6261` |
| GET | `/api/chats/{cid}/paradox_policy` | `paradox_policy_get()` | `web/app.py:6399` |
| PUT | `/api/chats/{cid}/paradox_policy` | `paradox_policy_put()` | `web/app.py:6403` |
| GET | `/api/chats/{cid}/persona_private_history` | `pph_get()` | `web/app.py:5805` |
| PUT | `/api/chats/{cid}/persona_private_history` | `pph_put()` | `web/app.py:5818` |
| GET | `/api/chats/{cid}/personas` | `chat_list_extra_personas()` | `web/app.py:5018` |
| POST | `/api/chats/{cid}/personas` | `chat_add_persona()` | `web/app.py:5063` |
| DELETE | `/api/chats/{cid}/personas/{pid}` | `chat_del_persona()` | `web/app.py:5090` |
| PUT | `/api/chats/{cid}/personas/{pid}/station` | `chat_persona_station()` | `web/app.py:5028` |
| GET | `/api/chats/{cid}/player_authority` | `player_authority_get()` | `web/app.py:6331` |
| PUT | `/api/chats/{cid}/player_authority` | `player_authority_put()` | `web/app.py:6346` |
| GET | `/api/chats/{cid}/player_view` | `player_view_get()` | `web/app.py:6308` |
| GET | `/api/chats/{cid}/positions` | `chat_positions_get()` | `web/app.py:5563` |
| POST | `/api/chats/{cid}/prelude` | `chat_prelude()` | `web/app.py:3604` |
| GET | `/api/chats/{cid}/promises` | `get_promise_ledger()` | `web/app.py:4946` |
| GET | `/api/chats/{cid}/promotable` | `list_promotable_presences()` | `web/app.py:4938` |
| POST | `/api/chats/{cid}/promotions/confirm` | `confirm_promotion()` | `web/app.py:4967` |
| POST | `/api/chats/{cid}/promotions/draft` | `draft_promotion()` | `web/app.py:4950` |
| POST | `/api/chats/{cid}/regions` | `region_create()` | `web/world_routes.py:2728` |
| PATCH | `/api/chats/{cid}/regions/{region_id}` | `region_patch()` | `web/world_routes.py:1921` |
| POST | `/api/chats/{cid}/retry_start` | `chat_retry_start()` | `web/app.py:2574` |
| GET | `/api/chats/{cid}/room` | `room_thread()` | `web/room_routes.py:52` |
| POST | `/api/chats/{cid}/room/mandates/{uid}/revoke` | `room_revoke()` | `web/room_routes.py:108` |
| POST | `/api/chats/{cid}/room/messages` | `room_say()` | `web/room_routes.py:65` |
| POST | `/api/chats/{cid}/room/messages/stream` | `room_say_stream()` | `web/room_routes.py:78` |
| GET | `/api/chats/{cid}/room/status` | `room_status()` | `web/room_routes.py:117` |
| GET | `/api/chats/{cid}/rooms` | `rooms_index()` | `web/world_routes.py:696` |
| POST | `/api/chats/{cid}/rooms` | `room_create()` | `web/world_routes.py:2166` |
| DELETE | `/api/chats/{cid}/rooms/{room_id}` | `room_delete()` | `web/world_routes.py:2232` |
| GET | `/api/chats/{cid}/rooms/{room_id}` | `rooms_slice()` | `web/world_routes.py:859` |
| PATCH | `/api/chats/{cid}/rooms/{room_id}` | `room_patch()` | `web/world_routes.py:1750` |
| POST | `/api/chats/{cid}/rooms/{room_id}/entities` | `room_entity_create()` | `web/world_routes.py:2271` |
| DELETE | `/api/chats/{cid}/rooms/{room_id}/entities/{entity_id}` | `room_entity_delete()` | `web/world_routes.py:2307` |
| PATCH | `/api/chats/{cid}/rooms/{room_id}/entities/{entity_id}` | `room_entity_patch()` | `web/world_routes.py:1820` |
| GET | `/api/chats/{cid}/rooms/{room_id}/grid` | `rooms_grid()` | `web/world_routes.py:1306` |
| POST | `/api/chats/{cid}/rooms/{room_id}/presences` | `room_presence_create()` | `web/world_routes.py:2352` |
| GET | `/api/chats/{cid}/setup_log` | `chat_setup_log()` | `web/app.py:2607` |
| GET | `/api/chats/{cid}/story_view` | `story_view_get()` | `web/app.py:6274` |
| GET | `/api/chats/{cid}/style_guide` | `style_guide_get()` | `web/app.py:5931` |
| PUT | `/api/chats/{cid}/style_guide` | `style_guide_put()` | `web/app.py:5937` |
| GET | `/api/chats/{cid}/survival` | `survival_get()` | `web/app.py:5471` |
| PUT | `/api/chats/{cid}/survival` | `survival_put()` | `web/app.py:5476` |
| POST | `/api/chats/{cid}/turns` | `turn_new()` | `web/app.py:6669` |
| POST | `/api/chats/{cid}/turns/{idx}/player_input` | `submit_extra_player_input()` | `web/app.py:5104` |
| GET | `/api/chats/{cid}/viewers` | `viewers_get()` | `web/app.py:6323` |
| GET | `/api/chats/{cid}/vitals` | `chat_vitals_get()` | `web/app.py:5528` |
| GET | `/api/chats/{cid}/world` | `world_get()` | `web/app.py:5823` |
| PUT | `/api/chats/{cid}/world` | `world_put()` | `web/app.py:5833` |
| PUT | `/api/debug_capture` | `put_debug_capture()` | `web/app.py:2241` |
| PUT | `/api/decision_model` | `put_decision_model()` | `web/app.py:2187` |
| GET | `/api/default_prompts` | `default_prompts()` | `web/app.py:2471` |
| PUT | `/api/exemplars` | `put_exemplars()` | `web/app.py:2210` |
| GET | `/api/extensions` | `extensions_list()` | `web/app.py:2685` |
| POST | `/api/extensions/install` | `extension_install()` | `web/app.py:2707` |
| GET | `/api/extensions/ui.css` | `extensions_ui_css()` | `web/app.py:2885` |
| GET | `/api/extensions/ui.js` | `extensions_ui()` | `web/app.py:2876` |
| GET | `/api/extensions/updates` | `extension_updates()` | `web/app.py:2728` |
| DELETE | `/api/extensions/{eid}` | `extension_remove()` | `web/app.py:2749` |
| GET | `/api/extensions/{eid}/asset/{path:path}` | `extension_asset()` | `web/app.py:2940` |
| POST | `/api/extensions/{eid}/disable` | `extension_disable()` | `web/app.py:2757` |
| DELETE | `/api/extensions/{eid}/document` | `extension_document_delete()` | `web/app.py:2853` |
| GET | `/api/extensions/{eid}/document` | `extension_document_get()` | `web/app.py:2821` |
| PUT | `/api/extensions/{eid}/document` | `extension_document_put()` | `web/app.py:2833` |
| DELETE | `/api/extensions/{eid}/documents` | `extension_documents_delete()` | `web/app.py:2863` |
| GET | `/api/extensions/{eid}/documents` | `extension_documents_list()` | `web/app.py:2800` |
| GET | `/api/extensions/{eid}/documents/verify` | `extension_documents_verify()` | `web/app.py:2811` |
| POST | `/api/extensions/{eid}/enable` | `extension_enable()` | `web/app.py:2699` |
| GET | `/api/extensions/{eid}/state` | `extension_state()` | `web/app.py:2762` |
| GET | `/api/extensions/{eid}/ui.css` | `extension_ui_css_one()` | `web/app.py:2907` |
| GET | `/api/extensions/{eid}/ui.js` | `extension_ui_one()` | `web/app.py:2895` |
| POST | `/api/extensions/{eid}/update` | `extension_update()` | `web/app.py:2739` |
| POST | `/api/guest/input` | `guest_input()` | `web/app.py:5363` |
| GET | `/api/guest/state` | `guest_state()` | `web/app.py:5266` |
| PUT | `/api/image_model` | `put_image_model()` | `web/app.py:2165` |
| POST | `/api/join` | `join_with_code()` | `web/app.py:5210` |
| GET | `/api/language-packs` | `language_packs_get()` | `web/app.py:4296` |
| GET | `/api/language-packs/{language_id}/ui` | `language_pack_ui()` | `web/app.py:4317` |
| DELETE | `/api/lore_entries/{eid}` | `lore_entry_delete()` | `web/app.py:4253` |
| PUT | `/api/lore_entries/{eid}` | `lore_entry_edit()` | `web/app.py:4177` |
| DELETE | `/api/lore_entries/{eid}/overlay` | `lore_entry_overlay_clear()` | `web/app.py:4265` |
| DELETE | `/api/lore_gen_jobs/{job_id}` | `lorebook_generate_discard()` | `web/app.py:3223` |
| POST | `/api/lore_gen_jobs/{job_id}/resume` | `lorebook_generate_resume()` | `web/app.py:3205` |
| DELETE | `/api/lorebook_links/{link_id}` | `lorebook_link_delete()` | `web/app.py:3163` |
| PUT | `/api/lorebook_links/{link_id}` | `lorebook_link_update()` | `web/app.py:3149` |
| POST | `/api/lorebooks` | `lore_create()` | `web/app.py:3956` |
| POST | `/api/lorebooks/import` | `lore_import()` | `web/app.py:3259` |
| DELETE | `/api/lorebooks/{lid}` | `lore_delete()` | `web/app.py:4044` |
| GET | `/api/lorebooks/{lid}` | `lore_get()` | `web/app.py:3932` |
| PUT | `/api/lorebooks/{lid}` | `lore_edit()` | `web/app.py:3978` |
| POST | `/api/lorebooks/{lid}/apply_plan` | `lorebook_apply_plan()` | `web/app.py:3232` |
| POST | `/api/lorebooks/{lid}/entries` | `lore_entry_create()` | `web/app.py:4094` |
| GET | `/api/lorebooks/{lid}/export` | `lore_export()` | `web/app.py:4050` |
| POST | `/api/lorebooks/{lid}/generate` | `lore_generate()` | `web/app.py:4080` |
| GET | `/api/lorebooks/{lid}/generate_job` | `lorebook_generate_job()` | `web/app.py:3194` |
| POST | `/api/lorebooks/{lid}/generate_plan` | `lorebook_generate_plan()` | `web/app.py:3168` |
| GET | `/api/lorebooks/{lid}/links` | `lorebook_links_get()` | `web/app.py:3122` |
| POST | `/api/lorebooks/{lid}/links` | `lorebook_link_create()` | `web/app.py:3127` |
| POST | `/api/lorebooks/{lid}/move` | `lorebook_move()` | `web/app.py:3049` |
| POST | `/api/lorebooks/{lid}/reinterpret` | `lore_reinterpret_route()` | `web/app.py:4067` |
| POST | `/api/lorebooks/{lid}/reorder` | `lorebook_reorder()` | `web/app.py:3058` |
| GET | `/api/maintenance/checkpoints` | `maintenance_checkpoints()` | `web/app.py:3006` |
| POST | `/api/maintenance/checkpoints/compact` | `maintenance_compact()` | `web/app.py:3022` |
| PUT | `/api/max_output_tokens` | `put_max_output_tokens()` | `web/app.py:2438` |
| DELETE | `/api/memories/{mid}` | `mem_del()` | `web/app.py:6663` |
| PUT | `/api/memories/{mid}` | `mem_edit()` | `web/app.py:6642` |
| GET | `/api/memory/embeddings` | `memory_embeddings_status()` | `web/app.py:2138` |
| POST | `/api/memory/embeddings/rebuild` | `memory_embeddings_rebuild()` | `web/app.py:2153` |
| GET | `/api/nsfw` | `get_nsfw()` | `web/app.py:2955` |
| PUT | `/api/nsfw` | `set_nsfw()` | `web/app.py:2959` |
| GET | `/api/openrouter/endpoints` | `get_openrouter_endpoints()` | `web/app.py:2370` |
| PUT | `/api/openrouter_routing` | `put_openrouter_routing()` | `web/app.py:2356` |
| POST | `/api/personas` | `persona_create()` | `web/app.py:3874` |
| POST | `/api/personas/generate` | `persona_generate()` | `web/app.py:3852` |
| POST | `/api/personas/import` | `persona_import()` | `web/app.py:3894` |
| DELETE | `/api/personas/{pid}` | `persona_del()` | `web/app.py:3926` |
| PUT | `/api/personas/{pid}` | `persona_edit()` | `web/app.py:3917` |
| GET | `/api/personas/{pid}/export` | `persona_export()` | `web/app.py:3908` |
| POST | `/api/personas/{pid}/fill_appearance` | `persona_fill_appearance()` | `web/app.py:3803` |
| PUT | `/api/prompt_presets` | `save_preset()` | `web/app.py:2482` |
| POST | `/api/prompt_presets/import` | `import_preset()` | `web/app.py:2645` |
| DELETE | `/api/prompt_presets/{name}` | `del_preset()` | `web/app.py:2659` |
| GET | `/api/prompt_presets/{name}/export` | `export_preset()` | `web/app.py:2509` |
| POST | `/api/providers` | `add_provider()` | `web/app.py:3320` |
| DELETE | `/api/providers/{pid}` | `del_provider()` | `web/app.py:3434` |
| PUT | `/api/providers/{pid}` | `put_provider()` | `web/app.py:3327` |
| GET | `/api/providers/{pid}/image_models` | `image_models()` | `web/app.py:3446` |
| GET | `/api/providers/{pid}/models` | `models()` | `web/app.py:3439` |
| PUT | `/api/providers/{pid}/prompt_cache` | `put_provider_prompt_cache()` | `web/app.py:3355` |
| PUT | `/api/reasoning_effort` | `put_reasoning_effort()` | `web/app.py:2382` |
| GET | `/api/research` | `get_research()` | `web/app.py:2331` |
| PUT | `/api/research` | `put_research()` | `web/app.py:2336` |
| PUT | `/api/response_format` | `put_response_format()` | `web/app.py:2413` |
| POST | `/api/steps/{sid}/activate` | `step_activate()` | `web/app.py:7822` |
| POST | `/api/steps/{sid}/edit` | `step_edit()` | `web/app.py:7810` |
| POST | `/api/steps/{sid}/reroll` | `step_reroll()` | `web/app.py:7742` |
| DELETE | `/api/turns/{tid}` | `turn_del()` | `web/app.py:7837` |
| GET | `/api/turns/{tid}/ambience` | `turn_ambience()` | `web/app.py:8164` |
| POST | `/api/turns/{tid}/ambience` | `turn_ambience_resolve()` | `web/app.py:8181` |
| GET | `/api/turns/{tid}/backdrop` | `turn_backdrop()` | `web/app.py:8008` |
| POST | `/api/turns/{tid}/backdrop` | `turn_backdrop_generate()` | `web/app.py:8023` |
| POST | `/api/turns/{tid}/branch` | `turn_branch()` | `web/app.py:6914` |
| PUT | `/api/turns/{tid}/input` | `edit_input()` | `web/app.py:7440` |
| GET | `/api/turns/{tid}/narration` | `turn_narration_variants()` | `web/app.py:7539` |
| POST | `/api/turns/{tid}/narration` | `turn_narration_select()` | `web/app.py:7560` |
| GET | `/api/turns/{tid}/pipeline` | `pipeline_get()` | `web/app.py:7588` |
| PUT | `/api/turns/{tid}/prose` | `edit_prose()` | `web/app.py:7467` |
| POST | `/api/turns/{tid}/reroll` | `turn_reroll()` | `web/app.py:7673` |
| POST | `/api/turns/{tid}/rerun` | `turn_rerun()` | `web/app.py:7683` |
| POST | `/api/turns/{tid}/resume` | `turn_resume()` | `web/app.py:7710` |
| GET | `/api/turns/{tid}/status` | `turn_status()` | `web/app.py:6869` |
| GET | `/api/turns/{turn_id}/debug` | `turn_debug_export()` | `web/app.py:2518` |
| GET | `/api/ui` | `ui_catalog_get()` | `web/app.py:4307` |
| PUT | `/api/ui-language` | `ui_language_put()` | `web/app.py:4332` |
| GET | `/api/updates/check` | `updates_check()` | `web/app.py:2998` |
| POST | `/api/updates/install` | `updates_install()` | `web/app.py:3002` |
| GET | `/guest` | `guest_page()` | `web/app.py:622` |
| GET | `/login` | `login_page()` | `web/app.py:691` |

## Database tables

| Table | Columns |
|---|---|
| `schema_meta` | `key` |
| `providers` | `id`, `name`, `kind`, `base_url`, `api_key`, `enabled` |
| `settings` | `key`, `value` |
| `characters` | `id`, `name`, `sheet`, `source`, `created`, `resource_uid` |
| `personas` | `id`, `name`, `sheet`, `source`, `resource_uid` |
| `lorebooks` | `id`, `name`, `chat_id`, `origin_id`, `book_type`, `summary`, `resource_uid`, `parent_id`, `scope_world_id`, `scope_location_id`, `inheritance_mode`, `--`, `--`, `--`, `--`, `--`, `--`, `default_circles`, `sort_order`, `anchor_entity_id`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `retired_turn_id` |
| `lorebook_links` | `id`, `source_book_id`, `target_book_id`, `relation_type`, `label`, `notes`, `bidirectional`, `follow_for_retrieval`, `weight`, `sort_order`, `created` |
| `chat_lorebooks` | `chat_id`, `lorebook_id`, `origin_id`, `enabled` |
| `lore_entries` | `id`, `lorebook_id`, `keys`, `content`, `category`, `canon_locked`, `turn_added`, `embedding`, `title`, `knowledge_tag`, `knowledge_range`, `knowledge_locations`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--` |
| `lore_gen_jobs` | `id`, `lorebook_id`, `--`, `status`, `--`, `stage`, `--`, `--`, `--`, `params`, `--`, `--`, `plan`, `--`, `progress`, `error`, `--`, `--`, `--`, `owner`, `attempts`, `created`, `updated` |
| `chats` | `id`, `name`, `persona_id`, `lorebook_id`, `scenario`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `branched_from`, `created` |
| `chat_chars` | `chat_id`, `char_id`, `status`, `state`, `--`, `--`, `sheet`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `dialogue_color` |
| `chat_char_frames` | `chat_id`, `char_id`, `frame_id`, `status`, `state` |
| `chat_personas` | `chat_id`, `persona_id`, `status`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `frame_id` |
| `turn_player_inputs` | `id`, `chat_id`, `turn_idx`, `persona_id`, `input`, `created` |
| `guest_grants` | `id`, `chat_id`, `persona_id`, `code_hash`, `code_expires`, `redeemed_at`, `token_hash`, `token_expires`, `revoked`, `created` |
| `host_sessions` | `id`, `token_hash`, `created`, `expires` |
| `frames` | `id`, `chat_id`, `label`, `ordinal`, `kind`, `travelers`, `nonexistent_cast`, `created`, `parent_frame_id`, `split_turn_idx`, `merged_turn_idx` |
| `turns` | `id`, `chat_id`, `idx`, `player_input`, `created`, `frame_id`, `--`, `--`, `--`, `--`, `--`, `commit_seq`, `--`, `--`, `--`, `--`, `--`, `offscreen` |
| `steps` | `id`, `turn_id`, `key`, `label`, `ord`, `stale` |
| `variants` | `id`, `step_id`, `content`, `created`, `active`, `reasoning` |
| `llm_blobs` | `hash`, `bytes`, `body` |
| `llm_capture` | `id`, `turn_id`, `seq`, `step_key`, `role`, `requested`, `served`, `started`, `duration`, `ok`, `error`, `system_hash`, `payload_hashes`, `response_hash`, `reasoning_hash`, `--`, `--`, `--`, `--`, `--`, `response_format`, `reasoning_effort`, `max_tokens`, `finish_reason` |
| `llm_capture_pending` | `id`, `chat_id`, `seq`, `step_key`, `role`, `requested`, `served`, `started`, `duration`, `ok`, `error`, `system_hash`, `payload_hashes`, `response_hash`, `reasoning_hash`, `response_format`, `reasoning_effort`, `max_tokens`, `finish_reason` |
| `memories` | `id`, `chat_id`, `char_id`, `turn_id`, `turn_idx`, `kind`, `category`, `provenance`, `salience`, `content`, `gist`, `key_phrases`, `entities`, `location`, `emotional_context`, `valence`, `arousal`, `--`, `--`, `--`, `encoding_valence`, `encoding_arousal`, `confidence`, `access_count`, `last_accessed`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `last_accessed_turn`, `embedding`, `cue_embedding`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `vkey`, `embedding_model`, `embedding_dim`, `archived`, `event_key`, `frame_id`, `--`, `--`, `--`, `--`, `importance`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `disputed`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `encoded_at_seconds`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `feelings`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `about`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `supersedes` |
| `memory_vectors` | `vkey`, `embedding`, `cue_embedding`, `embedding_model`, `embedding_dim`, `created` |
| `memory_summaries` | `id`, `chat_id`, `char_id`, `scope`, `start_turn_idx`, `end_turn_idx`, `summary`, `key_phrases`, `unresolved_threads`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `support`, `embedding`, `embedding_model`, `embedding_dim`, `updated`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--` |
| `events` | `id`, `chat_id`, `turn_id`, `content` |
| `world` | `chat_id`, `key`, `value` |
| `checkpoints` | `id`, `chat_id`, `turn_idx`, `blob`, `created`, `--`, `--`, `--`, `commit_seq` |
| `room_messages` | `id`, `chat_id`, `frame_id`, `turn_idx`, `role`, `text`, `created` |
| `lore_overlays` | `id`, `chat_id`, `frame_id`, `entry_id`, `keys`, `content`, `category`, `title`, `knowledge_tag`, `knowledge_range`, `knowledge_locations`, `circles`, `canon_locked`, `embedding`, `embedding_model`, `embedding_dim`, `disposition`, `source_notes`, `turn_idx`, `created` |
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

### `static/js/ambience.js` (1095 lines)

Sections: Room ambience (`:2`); seamless looping (`:256`); one-shots (`:735`); the ambience panel (`:784`); the mix (`:802`).

Declared functions: `ambienceStored()`, `ambienceElement()`, `entryAudios()`, `ambiencePlayers()`, `applyAmbienceMute()`, `setAmbienceVolume()`, `ambienceLevel()`, `setLayerGain()`, `toggleAmbienceMute()`, `ambienceFadeClock()`, `ambienceEnsureSounding()`, `ambienceFadeMix()`, `armSeamlessLoop()`, `crossLoop()`, `retireEntries()`, `stopAmbience()`, `playAmbience()`, `armAmbienceUnlock()`, `ambienceWorking()`, `awaitAmbience()`, `resolveAmbience()`, `ambienceForTurn()`, `rerollAmbience()`, `ambienceOnVisibleTurn()`, `ambienceResetForRender()`, `updateAmbienceBtn()`, `playAmbienceOneshot()`, `ambienceCandidateRow()`, `ambienceLayerRow()`, `ambienceMixPanel()`, `openAmbiencePanel()`, `toggleAmbience()`, `syncAmbience()`.

### `static/js/app.js` (1373 lines)

Sections: Boot & sidebar (`:1`); and then nothing showed the report, so a host who installed a pack got (`:50`); New chat wizard (`:370`); NSFW (`:1058`); Composer (`:1086`); Init (`:1164`); Embedding reconciler progress (`:1224`).

Declared functions: `boot()`, `renderSide()`, `syncExtensionTabs()`, `renderChatSidebar()`, `failedSetupRow()`, `newChatWizard()`, `renderWizardChoice()`, `storyLanguagePacks()`, `defaultStoryLanguage()`, `wizardState()`, `wizardHistoryCharacters()`, `discardFailedStorySetup()`, `wizardFromScratch()`, `renderWizardPersona()`, `renderWizardCharacters()`, `renderWizardScenario()`, `runWizard()`, `renderCharacterSidebar()`, `renderPersonaSidebar()`, `renderLegacyLoreSidebar()`, `updateNSFWBtn()`, `toggleNSFW()`, `resizeComposer()`, `erCard()`, `erDismiss()`, `erPoll()`, `erWatch()`, `erOfferRebuild()`.

### `static/js/backdrops.js` (430 lines)

Sections: Scene backdrops (`:2`).

Declared functions: `backdropLayers()`, `backdropLuminance()`, `applyBackdropContrast()`, `releaseBackdropLayer()`, `clearBackdrop()`, `showBackdrop()`, `backdropWorking()`, `awaitBackdrop()`, `generateBackdrop()`, `backdropForTurn()`, `backdropOnVisibleTurn()`, `backdropResetForRender()`, `updateBackdropBtn()`, `toggleBackdrops()`, `syncBackdrops()`.

### `static/js/chat.js` (3527 lines)

Sections: The turn being read (`:1`); Colouring who spoke (`:201`); `dialogue_log` is committed per turn and arrives as `turn.speech` -- and (`:204`); Flipping between rerolls of the newest beat (`:1171`); Pipeline drawer: reading a step through a lens (`:1522`); Pipeline drawer (`:2158`); Relationship viewer (`:2597`); Memory browser (`:2676`); Private history (`:3464`).

Declared functions: `observeVisibleTurn()`, `openChat()`, `foldTypography()`, `decodeProseEntities()`, `splitEmphasis()`, `appendEmphasized()`, `quoteBody()`, `quotedRegions()`, `speechSpans()`, `paintProse()`, `proseEl()`, `renderFrameBar()`, `switchFrame()`, `syncComposerToFrame()`, `updateChatScopedButtons()`, `renderChat()`, `beginStory()`, `branchTurn()`, `editTurnInput()`, `editTurnProse()`, `liveReset()`, `friendlyPhase()`, `turnStatusStart()`, `turnStatusSet()`, `turnStatusStop()`, `_streamOn()`, `liveFlush()`, `liveAppend()`, `liveStep()`, `handleEvt()`, `inCurrentScope()`, `showNarrationEarly()`, `clearNarrationEarly()`, `resetRerollNav()`, `_mountRerollNav()`, `_paintRerollCount()`, `showRerollVariant()`, `abortActiveRun()`, `runStream()`, `confirmCheckpointRestore()`, `runReroll()`, `rerollTurn()`, `exportChat()`, `importChatModal()`, `perceiverViews()`, `loopMindIds()`, `specialistIds()`, `stepLenses()`, `perceiverLabel()`, `facetBadge()`, `lensLabel()`, `renderLensBar()`, `lensSlice()`, `specialistSlice()`, `proseContractRecord()`, `proseContractIds()`, `proseContractLabel()`, `proseContractSlice()`, `perceptionPacketSlice()`, `perceiverSlice()`, `mindSlice()`, `keySlice()`, `renderEngineNotes()`, `pipelineMapPanel()`, `openPipeline()`, `relMeter()`, `relationshipModal()`, `memModal()`, `exportCharacterMemories()`, `importCharacterMemoriesModal()`, `memQS()`, `memCharId()`, `loadMemoryBrowse()`, `getMemUI()`, `renderMemorySummary()`, `sortedMems()`, `renderMemoryList()`, `memoryCard()`, `fieldWrap()`, `reloadMemView()`, `runMemorySearch()`, `showNewMemoryForm()`, `checkMemoryCoverage()`, `backfillMemoryEras()`, `consolidateMemories()`, `previewMemoryContext()`, `chatPH()`, `personaPH()`.

### `static/js/chime.js` (179 lines)

Sections: Turn-completion chime (`:2`); Which other waits are worth a chime (`:110`).

Declared functions: `chimeContext()`, `chimeArm()`, `chimePlay()`, `chimeWatches()`, `chimeWorkFinished()`, `chimeSetMuted()`, `toggleChimeMute()`, `updateChimeBtn()`.

### `static/js/components.js` (1356 lines)

Sections: Modal (`:50`); Book covers (`:66`); confirm()/prompt() replacements (`:179`); Toasts (`:512`); Background tasks (`:557`); Form helpers (`:643`); Model picker (`:1206`); made for every combobox that already has a provider saved -- opened its (`:1236`).

Declared functions: `txt()`, `el()`, `coverOfRow()`, `coverOfTitle()`, `modal()`, `modalOwnership()`, `closeModal()`, `closeAllModals()`, `_confirmOverlay()`, `confirmModal()`, `promptModal()`, `promptModalWithToggle()`, `livedLocationControl()`, `attachStoryLorebook()`, `generateStoryLocation()`, `openLivedLocationDialog()`, `toastHost()`, `toast()`, `renderActivity()`, `elapsedLabel()`, `activityTicking()`, `backgroundTask()`, `buttonTask()`, `loadingBlock()`, `emptyState()`, `fText()`, `fArea()`, `fSelect()`, `fNum()`, `fLineList()`, `fStrList()`, `attireRegions()`, `attireRegionZones()`, `attireOptInZones()`, `fCoveragePicker()`, `fAttireGarments()`, `fList()`, `fAbilities()`, `fTraits()`, `fValues()`, `fBeliefs()`, `fCopingStrategies()`, `fAssociations()`, `fGoals()`, `fSenses()`, `fLatent()`, `extraPartAspects()`, `fExtraParts()`, `interiorLights()`, `fInteriorStations()`, `fPronouns()`, `phEditor()`, `fetchModels()`, `fetchImageModels()`, `modelCombobox()`, `emitChange()`, `load()`, `showDD()`.

### `static/js/editors.js` (1088 lines)

Sections: how many stations, and how many of them are new -- rather than letting a (`:62`); Carrying the fields an editor has no widget for (`:138`); Background-character promotion (`:916`); Import (file upload) (`:970`); Generate (`:1041`); Lorebook generate (`:1059`); Export (`:1076`).

Declared functions: `appearanceFillButton()`, `interiorFillButton()`, `defaultCharacterSheet()`, `carryUnpresentedFields()`, `greetingCarousel()`, `quickStartModal()`, `charEditor()`, `personaEditor()`, `promotionReviewModal()`, `promoteBackgroundPresence()`, `importModal()`, `generateModal()`, `generateLoreModal()`, `exportCharacter()`, `exportPersona()`, `exportLorebook()`.

### `static/js/extensions.js` (661 lines)

Sections: Extension host (`:2`); Registration attribution (`:20`); Failure containment (`:56`); ES module entries (`:86`); Registration surface (`:177`); Notices (`:222`); Host services (`:370`); The chat lifecycle, as a declared contract (`:401`); Host-internal accessors (`:483`); Hot load / unload (`:609`).

### `static/js/i18n-core.js` (250 lines)

Sections: The localization rules, once (`:3`).

Declared functions: `i18nCompileTemplates()`, `i18nMatchTemplate()`, `i18nTranslate()`, `i18nLocalize()`, `i18nObserve()`.

### `static/js/i18n.js` (34 lines)

### `static/js/lorebooks.js` (3823 lines)

Sections: Library sidebar (`:305`); Data loading (`:504`); Workspace (`:614`); Book metadata and tree operations (`:1212`); Entry editor (`:1725`); Lorebook relationships (`:2543`); Advanced generator (`:2994`); Interrupted-generation recovery (`:3216`).

Declared functions: `loreBookTypeIcon()`, `inheritanceModes()`, `knowledgeTags()`, `knowledgeRanges()`, `loreLinkTypes()`, `normalizeLoreBook()`, `loreOwnershipKey()`, `loreRootBooks()`, `loreBooksByParent()`, `loreBookMatches()`, `loreVisibleIds()`, `loreBookLabel()`, `parseStoredJSON()`, `loreField()`, `loreSelect()`, `loreBookOptions()`, `renderLoreLibrarySidebar()`, `renderNode()`, `loreStoryQuery()`, `loreBookIsLibrary()`, `loadLoreWorkspaceData()`, `collectLoreLinkTargets()`, `loreWorkspaceVisible()`, `renderLoreWorkspaceBody()`, `openLoreWorkspace()`, `renderLoreInspector()`, `selectTab()`, `buildLoreWorkspace()`, `renderWorkspaceTree()`, `renderNode()`, `renderTreeList()`, `renderLoreBookEditor()`, `moveLoreBook()`, `reorderLoreBook()`, `promoteLoreBook()`, `demoteLoreBook()`, `createSiblingLoreBook()`, `createLoreBookDialog()`, `refreshLoreUI()`, `renderLoreEntries()`, `renderList()`, `buildLoreEntryCard()`, `splitNumberList()`, `reinterpretLoreBook()`, `generateLoreEntriesPrompt()`, `buildDirectLoreRequest()`, `renderRelationshipOverview()`, `renderLoreRelationshipEditor()`, `renderRelationshipList()`, `showNewRelationshipForm()`, `renderLoreGenerator()`, `adoptGeneratorPlan()`, `generatorPlanMessage()`, `loreGenAgo()`, `refreshLoreGenRecovery()`, `normalizeGeneratorPlan()`, `renderLorePlanPreview()`, `renderOperations()`, `planStat()`, `renderAnalysisSection()`, `addPlanGroup()`, `stripPlanUIFields()`, `acceptedGeneratorPlan()`.

### `static/js/settings.js` (4167 lines)

Sections: Chat tool modals (`:1`); Condition tab (`:823`); Survival tracker (`:883`); Character relocation (`:1195`); API connections (`:1958`); Software updates (host-only; git fast-forward from GitHub origin) (`:3384`); Legacy checkpoint conversion (host-only maintenance) (`:3416`); Prompts (`:3650`); and be able to load that pack's own sheets to edit, rather than (`:3661`); Extensions (`:3840`).

Declared functions: `paradoxModes()`, `frameQuery()`, `charterDiagnosticsPanel()`, `selectTab()`, `dialogueColorControl()`, `save()`, `renderCastTab()`, `renderConditionTab()`, `hydrateConditionTab()`, `vitalMeter()`, `syncVitalsGutterNow()`, `syncVitalsGutter()`, `hideVitalsHud()`, `vitalsBlock()`, `refreshVitalsHud()`, `clearVitalsHud()`, `hydrateCastLocations()`, `castRoomLabel()`, `castRoomSelect()`, `renderLorebooksTab()`, `renderBookNode()`, `renderMultiplayerTab()`, `renderFramesTab()`, `renderFramesListPanel()`, `renderPersonaStationingPanel()`, `renderParadoxPanel()`, `renderBackgroundPresencesPanel()`, `renderGuestInvitePanel()`, `renderInsightsTab()`, `renderDramaticIronyPanel()`, `renderPromiseLedgerPanel()`, `embeddingBankBlock()`, `modelRecommendationsBlock()`, `renderFirstRunProviderSetup()`, `preferredBackdropSize()`, `renderFullApiSettings()`, `propagateToFollowers()`, `renderUpdateChecking()`, `renderUpdateError()`, `checkpointCompactionBlock()`, `renderUpdateStatus()`, `runUpdateInstall()`, `renderUpdateDone()`, `openPromptsModal()`, `reopenPromptsIfRequested()`, `extensionTrustNote()`, `extensionCapabilitySummary()`, `extensionSettingsSections()`, `openExtensionsMenu()`.

### `static/js/theme-init.js` (181 lines)

Declared functions: `readStored()`, `writeStored()`, `normaliseTheme()`, `normaliseProseSize()`, `applyTheme()`, `applyProseSize()`, `normaliseEffects()`, `applyEffects()`, `syncPageHidden()`.

### `static/js/themes.js` (159 lines)

Declared functions: `themePreview()`, `openAppearanceSettings()`.

### `static/js/utils.js` (266 lines)

Sections: API (`:105`); Download (`:245`); Card authoring warnings (`:254`).

Declared functions: `t()`, `watchUILanguage()`, `localizeDocument()`, `memoryCategories()`, `memoryProvenance()`, `hasDefaultModel()`, `safeId()`, `splitCL()`, `numOr()`, `taggedError()`, `errorDetailText()`, `api()`, `reportStaleCode()`, `streamPost()`, `downloadJSON()`, `showCardWarnings()`.

### `static/js/weather-fx.js` (638 lines)

Sections: Weather effects (`:2`); the tile (`:219`); the layers (`:292`); lifecycle (`:391`); lightning (`:481`); schedules nothing; the visibility handler re-enters through (`:507`).

Declared functions: `weatherFxLater()`, `weatherFxCancel()`, `weatherFxClearTimers()`, `weatherFxClearBolt()`, `weatherFxReduced()`, `weatherFxEffectsOff()`, `weatherFxSupported()`, `weatherFxHost()`, `weatherFxRandom()`, `weatherFxTile()`, `weatherFxReach()`, `weatherFxBuild()`, `weatherFxClearLayers()`, `weatherFxSetPlayState()`, `weatherFxStop()`, `weatherFxVisible()`, `weatherFxApply()`, `weatherFxStormy()`, `weatherFxScheduleFlash()`, `weatherFxFlash()`, `weatherFxOpenSky()`, `weatherFxBolt()`, `weatherFxThunder()`, `weatherFxForTurn()`.

### `static/js/world_browser.js` (3995 lines)

Sections: The World Browser (`:3`); with its room, station, pose, and its FULL attire ledger, (`:31`); Edit controls (`:113`); The tree (`:216`); The room card (`:296`); Townspeople (2026-09-05, DESIGN_CHARTER_PLACEMENT § the map) (`:419`); `size` is the word for the floor and `extent` its measurement, so the (`:546`); The Bodies tab: every body, and the attire editor (`:1362`); The Raw JSON tab: the two editors, unchanged (`:1634`); The map editor (`:1721`); the neighbours, faintly, where the field lays them (`:2057`); the room's cells, and the overlay's tint over them (`:2103`); the boundary as a line, with each doorway a gap in it (`:2143`); windows: each a thin line in its wall, never a gap in it (`:2202`); anchors: footprint cells, the id, a height mark (`:2240`); things placed by a position and a station (`:2282`); bodies: a marked cell with a facing tick; the unstationed in a lane (`:2320`); the lint, drawn at the thing each row concerns (`:2376`); the shape: parts as rectangles, the box's sides as handles (`:2432`); blank wall segments open a doorway; empty floor places a thing (`:2489`); the drops (`:2515`); through the doorways route, so a doorway declared from the far room (`:2626`); The dialog (`:3342`).

Declared functions: `wbStatusBadge()`, `wbRoomLabel()`, `wbSelect()`, `wbText()`, `wbCoalesced()`, `wbWrite()`, `wbRenderTree()`, `wbSection()`, `wbIndexRows()`, `wbCellOf()`, `wbCellText()`, `wbStationText()`, `wbPoseText()`, `wbMoveControl()`, `wbNumber()`, `wbBodyMove()`, `wbCharterUrl()`, `wbCharterStationBody()`, `wbSourceWord()`, `wbCharterWhere()`, `wbCharterRow()`, `wbPoseEditor()`, `wbLintRows()`, `wbRoomFields()`, `wbRegionLook()`, `wbExits()`, `wbWindows()`, `wbAnchors()`, `wbOccupant()`, `wbThing()`, `wbRenderCard()`, `wbGroupGarments()`, `wbLedgerEntry()`, `wbAttireEditor()`, `wbBodyKind()`, `wbCharterDetails()`, `wbRenderBodies()`, `wbRenderRaw()`, `wbSvg()`, `wbSvgPoint()`, `wbDraggable()`, `wbUndoStack()`, `wbWallOf()`, `wbOffsetAlong()`, `wbBearingBetween()`, `wbActivatable()`, `wbBoundary()`, `wbFocusRow()`, `wbFootprintLength()`, `wbRenderRoomMap()`, `centre()`, `partBox()`, `writeParts()`, `movePart()`, `dropPart()`, `sizePart()`, `resizePart()`, `writeExtent()`, `dropHandle()`, `nudgeHandle()`, `writeAnchors()`, `dropAnchor()`, `dropDoorway()`, `dropBody()`, `dropCharter()`, `dropThing()`, `wbRenderStructureMap()`, `wbPlanEl()`, `wbPlanFill()`, `wbPlanFrame()`, `wbPlanDefs()`, `wbPlanWalls()`, `wbPlanEdge()`, `wbPlanLabel()`, `wbPlanFixture()`, `wbPlanStair()`, `wbPlanLevelName()`, `wbRenderStoreyPlan()`, `wbPurposeSwatches()`, `wbPlanLegend()`, `wbRegionLegend()`, `wbMarksLegend()`, `wbMapPane()`, `wbWallForm()`, `wbCellForm()`, `wbMapNotes()`, `wbMapLegend()`, `openWorldBrowser()`, `moveRoute()`, `renderMapBar()`, `drawGrid()`, `loadGrid()`, `showStructure()`, `showPlan()`, `refreshIndex()`, `loadCard()`, `loadRoom()`, `selectTab()`.

### `static/js/writers_room.js` (799 lines)

Sections: The Writers' Room panel (`:3`); bd-panel for this element alone. (`:20`); Named limits (`:33`); Shape: docked / floating / closed (`:183`); Loading (`:240`); Sending (`:319`); The stream (`:352`); Rendering (`:427`); Building the panel (`:675`); Boot (`:788`).

Declared functions: `roomStoryText()`, `roomCls()`, `roomStoreGet()`, `roomStoreSet()`, `roomRestorePrefs()`, `roomClampWidth()`, `roomClampOpacity()`, `roomClampGeometry()`, `roomApplyShape()`, `roomOpen()`, `roomSetMode()`, `roomKey()`, `roomScope()`, `roomFrameQuery()`, `roomLoad()`, `roomLoadEarlier()`, `roomStartWatch()`, `roomStopWatch()`, `roomSend()`, `roomStream()`, `roomEvent()`, `roomRevoke()`, `roomRenderSoon()`, `roomRender()`, `roomRenderStatus()`, `roomRenderMandates()`, `roomRenderThread()`, `roomRenderCitations()`, `roomLiveNode()`, `roomBuild()`, `roomWireDrag()`, `track()`.
