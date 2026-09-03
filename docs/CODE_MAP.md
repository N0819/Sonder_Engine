# Generated Code Map

> Regenerate with `python tools/generate_code_map.py`. Do not hand-edit this file.

## Python modules

| Module | Lines | Purpose | Local dependencies |
|---|---:|---|---|
| `agents/__init__.py` | 97 | Backward-compatible facade for the role-specific agent package. | `agents.background`, `agents.character`, `agents.common`, `agents.director`, `agents.loops`, `agents.mapping`, `agents.narration`, `agents.perception`, `agents.runtime`, `agents.storage`, `story.scene` |
| `agents/background.py` | 1653 |  | `agents.common`, `core.db`, `llm.prompts`, `llm.schemas`, `persist.commit`, `story.character_schema`, `story.scene`, `world.background_claims`, `world.spatial` |
| `agents/character.py` | 4160 | Private character decision agent. | `agents.common`, `core.db`, `core.frames`, `llm.prompts`, `llm.schemas`, `mind`, `mind.affect`, `mind.memory`, `mind.memory_judge`, `mind.psychology_runtime`, `mind.theory_of_mind`, `story.character_schema`, `story.scene`, `world.gaps`, `world.place_purpose`, `world.spatial`, `world.survival` |
| `agents/common.py` | 9284 | Shared normalization, lore, delivery, and perception helpers. | `core.db`, `core.pipeline_context`, `llm.llm_quality`, `llm.prompts`, `llm.providers`, `llm.schemas`, `mind.memory`, `mind.theory_of_mind`, `persist.commit`, `story`, `story.character_schema`, `story.provenance_text`, `story.scene`, `world`, `world.spatial` |
| `agents/composer.py` | 3450 |  | `agents.common`, `core.pipeline_context`, `story.provenance_text`, `story.scene`, `world.spatial` |
| `agents/director.py` | 4632 | Scene establishment, player interpretation, and objective resolution. | `agents.common`, `agents.director_contact`, `agents.director_evidence`, `agents.director_fanout`, `agents.director_floors`, `agents.director_lingua`, `agents.director_movement`, `agents.director_reconcile`, `agents.director_scopes`, `agents.director_views`, `core.db`, `llm`, `llm.prompts`, `llm.providers`, `llm.schemas`, `mind.memory`, `story`, `story.attire`, `story.character_schema`, `story.scene`, `world.paradox`, `world.spatial`, `world.survival` |
| `agents/director_contact.py` | 457 |  | `story.character_schema`, `world.spatial` |
| `agents/director_evidence.py` | 1187 |  | `agents.common`, `agents.director_lingua`, `llm`, `world.spatial` |
| `agents/director_fanout.py` | 830 |  | `agents.common`, `agents.director_evidence`, `agents.director_scopes`, `core.db`, `story.character_schema`, `world.spatial`, `world.survival` |
| `agents/director_floors.py` | 1586 |  | `agents.common`, `agents.director_lingua`, `story.character_schema`, `story.scene`, `world.mechanics`, `world.spatial` |
| `agents/director_lingua.py` | 29 |  | — |
| `agents/director_movement.py` | 1028 |  | `agents.director_lingua`, `story.character_schema`, `world.spatial` |
| `agents/director_reconcile.py` | 592 |  | `agents.common`, `agents.director_evidence`, `agents.director_scopes`, `core.db`, `story`, `world.spatial` |
| `agents/director_scopes.py` | 856 |  | `agents.director_views`, `core.db`, `world.survival` |
| `agents/director_views.py` | 627 |  | `agents.common`, `story.character_schema`, `story.scene`, `world.background_claims` |
| `agents/dramaturge.py` | 308 |  | `core.logging_utils` |
| `agents/loops.py` | 1337 | Reaction loops, interaction rounds, and deterministic micro-perception. | `agents.character`, `agents.common`, `core.db`, `story.character_schema`, `story.scene`, `world.spatial` |
| `agents/mapping.py` | 491 | Lore routing, cached recall, and retrieval staging. | `agents.common`, `core.db`, `mind.memory`, `story.scene`, `world.spatial` |
| `agents/narration.py` | 1953 | Player-facing narration agent. | `agents`, `agents.common`, `core.db`, `llm.prompts`, `llm.schemas`, `story.character_schema`, `story.scene`, `world.spatial`, `world.weather` |
| `agents/perception.py` | 4733 | Opening, action-onset, and outcome observer views. | `agents`, `agents.common`, `core.db`, `mind`, `story.character_schema`, `story.scene`, `world.mechanics`, `world.spatial` |
| `agents/runtime.py` | 1382 | Pipeline plans, dispatch, streaming, cancellation, resume, and reruns. | `agents.background`, `agents.character`, `agents.common`, `agents.director`, `agents.loops`, `agents.mapping`, `agents.narration`, `agents.perception`, `agents.storage`, `core.db`, `core.pipeline_context`, `llm.providers`, `persist.checkpoints`, `persist.commit`, `story.character_schema`, `story.scene` |
| `agents/storage.py` | 123 | Step and active-variant persistence helpers. | `core.db` |
| `agents/story_planner.py` | 938 |  | `core.logging_utils` |
| `core/__init__.py` | 6 |  | — |
| `core/db.py` | 2587 | SQLite schema, migrations, connection management, transactions, and key/value world access. | `core.paths` |
| `core/frames.py` | 220 |  | `core.db` |
| `core/jobs.py` | 317 |  | `core.logging_utils` |
| `core/logging_utils.py` | 122 | Structured timing and observability helpers. | — |
| `core/outofband.py` | 392 |  | `core.logging_utils` |
| `core/paths.py` | 32 |  | — |
| `core/pipeline_context.py` | 505 | Typed mutable context passed through a turn pipeline. | `core.db` |
| `core/updates.py` | 399 |  | `core.paths` |
| `dressing/__init__.py` | 6 |  | — |
| `dressing/ambience.py` | 2064 |  | `core`, `core.db`, `core.paths`, `dressing.backdrops`, `world.weather` |
| `dressing/backdrops.py` | 1313 |  | `core`, `core.db`, `core.logging_utils`, `core.paths`, `world.day_cycle`, `world.spatial`, `world.weather` |
| `llm/__init__.py` | 6 |  | — |
| `llm/llm_quality.py` | 813 | Strict JSON parsing, schema validation, and model-assisted repair. | `core.pipeline_context`, `llm.prompts`, `llm.providers`, `llm.schemas` |
| `llm/prompt_cache.py` | 79 | Provider-specific prompt-cache helpers. | `llm.providers` |
| `llm/prompts.py` | 516 | Default system prompts and prompt preset access. | `core.db` |
| `llm/providers.py` | 3840 | Provider selection, retries, streaming, cancellation, model listing, and embeddings. | `core.db`, `core.logging_utils` |
| `llm/research_providers.py` | 247 |  | `core.db` |
| `llm/schemas.py` | 5451 | Pydantic output contracts and semantic validation for agent payloads. | — |
| `mind/__init__.py` | 6 |  | — |
| `mind/affect.py` | 2406 |  | `mind.theory_of_mind` |
| `mind/canon_provenance.py` | 398 |  | — |
| `mind/knowledge_circles.py` | 134 |  | `core.db` |
| `mind/memory.py` | 137 | Facade re-exporting every mind.memory_* name; holds no domain code of its own. | `core`, `core.db`, `core.logging_utils`, `llm.prompts`, `llm.providers`, `mind.memory_common`, `mind.memory_context`, `mind.memory_inference`, `mind.memory_lore_entries`, `mind.memory_lorebooks`, `mind.memory_read`, `mind.memory_relationships`, `mind.memory_retrieval`, `mind.memory_snapshot`, `mind.memory_summaries`, `mind.memory_time`, `mind.memory_vectors`, `mind.memory_write`, `mind.theory_of_mind` |
| `mind/memory_common.py` | 255 | Leaf helpers shared by every memory domain: vocabularies, blob/vector codecs, FTS query, cosine. | `core.db` |
| `mind/memory_context.py` | 635 | The character memory payload: where retrieval, summaries and active state become one context. | `core.db`, `llm.prompts`, `llm.providers`, `mind.memory_common`, `mind.memory_retrieval`, `mind.memory_summaries`, `mind.memory_time`, `mind.memory_write` |
| `mind/memory_inference.py` | 154 | Belief confidence at mint and at abandonment, and reconciliation across a mind's inferences. | `core.db`, `mind.memory_write`, `mind.theory_of_mind` |
| `mind/memory_judge.py` | 430 |  | `core.db`, `core.logging_utils`, `llm.prompts`, `llm.providers` |
| `mind/memory_lore_entries.py` | 835 | Lore entries: add/update/delete, embedding stamps and health, search_lore, per-character knowledge scoping. | `core.db`, `core.logging_utils`, `llm.providers`, `mind.memory_common`, `mind.memory_lorebooks`, `mind.memory_write` |
| `mind/memory_lorebooks.py` | 583 | The lorebook graph: hierarchy, links, inheritance modes, per-chat attachment and weights. | `core.db`, `core.logging_utils`, `mind.memory_common` |
| `mind/memory_read.py` | 374 | The one seam a mind reads its own memory through, and the host reads that deliberately cross characters. | `core`, `core.db`, `mind.memory_common`, `mind.memory_write` |
| `mind/memory_relationships.py` | 241 | The relationship graph: axis deltas from conduct and from inference, and the history behind them. | `core.db`, `mind.memory_common`, `mind.memory_write` |
| `mind/memory_retrieval.py` | 1147 | Hybrid retrieval: lexical and vector rankings fused by RRF, tilted by mood and importance, plus unbidden recall. | `core.db`, `core.logging_utils`, `llm.providers`, `mind.memory_common`, `mind.memory_read`, `mind.memory_write` |
| `mind/memory_snapshot.py` | 820 | Checkpoint and archive: vector addressing, the prepare/apply restore split, memory and lorebook dump/restore. | `core.db`, `core.logging_utils`, `llm.providers`, `mind.memory_common`, `mind.memory_lore_entries`, `mind.memory_summaries`, `mind.memory_write` |
| `mind/memory_summaries.py` | 699 | Autobiographical, hearsay and surmise summaries: search, support sets, windowed consolidation and backfill. | `core.db`, `llm.prompts`, `llm.providers`, `mind.memory_common`, `mind.memory_read`, `mind.memory_retrieval`, `mind.memory_write` |
| `mind/memory_time.py` | 332 |  | `core.db` |
| `mind/memory_vectors.py` | 772 | Rebuilding vectors after the embedding model changes: bank status, the rebuild, and its background run. | `core.db`, `core.logging_utils`, `llm.providers`, `mind.memory_common`, `mind.memory_retrieval`, `mind.memory_write` |
| `mind/memory_write.py` | 829 | How a memory becomes a row: normalisation, extraction, FTS mirror, the upsert, and the embedding-repair thread. | `core.db`, `core.logging_utils`, `llm.providers`, `mind.memory_common` |
| `mind/psychology_runtime.py` | 749 |  | — |
| `mind/theory_of_mind.py` | 725 |  | — |
| `persist/__init__.py` | 6 |  | — |
| `persist/chat_archive.py` | 1274 | Typed, atomic chat archive export/import service and HTTP routes. | `core.db`, `llm.schemas`, `mind.memory`, `persist.checkpoints`, `story.character_schema`, `story.room_conversation` |
| `persist/chat_delete.py` | 42 |  | `core.db` |
| `persist/checkpoints.py` | 1450 | Whole-chat snapshots and checkpoint restore orchestration. | `core.db`, `mind.memory` |
| `persist/commit.py` | 767 | Atomic commit orchestrator, per-turn lock, thin tail domains, and the facade re-exporting every commit_* name. | `core.db`, `core.frames`, `llm.prompts`, `llm.providers`, `mind`, `mind.memory`, `mind.theory_of_mind`, `persist.commit_attire`, `persist.commit_background`, `persist.commit_common`, `persist.commit_destruction`, `persist.commit_entities`, `persist.commit_ledgers`, `persist.commit_mapping`, `persist.commit_mechanics`, `persist.commit_memory`, `persist.commit_memory_write`, `persist.commit_place_graph`, `persist.commit_room_registry`, `persist.commit_scene_state`, `story`, `story.character_schema`, `story.scene`, `world.comfort`, `world.mechanics`, `world.paradox`, `world.spatial`, `world.spatial_frames`, `world.survival`, `world.weather` |
| `persist/commit_attire.py` | 1458 | The mutable clothing ledger: attire notes, shed/worn garment entities, the validated attire diff. | `persist.commit_common`, `story`, `story.attire` |
| `persist/commit_background.py` | 3869 | Background presences: tracking, identity folding, the reactor gate, promotion to cast. | `core.db`, `mind.memory`, `persist.commit_common`, `story.character_schema`, `story.scene`, `world.spatial` |
| `persist/commit_common.py` | 595 | Leaf helpers shared across commit domains: scalar utilities, name/address roster, entity-id canonicalisation. | `core.db`, `mind.memory`, `story.character_schema`, `world.mechanics`, `world.spatial` |
| `persist/commit_destruction.py` | 411 | Single- and multi-book destruction cascades, retirement, and latency-gated news. | `core.db`, `mind.memory`, `persist.commit_common`, `world.mechanics`, `world.spatial`, `world.spatial_frames` |
| `persist/commit_entities.py` | 560 | world_entities projection of the scene commit, awareness gate, disguise supersession. | `core.db`, `persist.commit_common`, `story.character_schema`, `story.scene`, `world.spatial` |
| `persist/commit_ledgers.py` | 374 | Pending-obligation and world-pressure debt ledgers. | `core.db`, `core.pipeline_context`, `persist.commit_common` |
| `persist/commit_mapping.py` | 574 | Lore/book mapping commit: book ops, lore ops, canon fallback ops, offscreen-event normaliser. | `core.db`, `core.frames`, `mind.memory`, `persist.commit_common`, `story.character_schema`, `story.provenance_text`, `world.spatial` |
| `persist/commit_mechanics.py` | 387 | Transit/news sweeps, the world-event spine, information carriers, cast changes. | `core.db`, `persist.commit_common`, `persist.commit_scene_state`, `story.character_schema`, `story.scene`, `world.mechanics` |
| `persist/commit_memory.py` | 1794 | Pre-lock memory preparation: per-mind memories and the psychology deltas riding with them. | `core.db`, `mind`, `mind.memory`, `mind.theory_of_mind`, `persist.commit_background`, `persist.commit_common`, `persist.commit_place_graph`, `story.character_schema`, `world.comfort`, `world.spatial`, `world.stimulation`, `world.survival` |
| `persist/commit_memory_write.py` | 325 | The durable memory write and its out-of-band consolidation twin. | `core.db`, `mind.memory`, `persist.commit_memory`, `story.character_schema`, `story.scene` |
| `persist/commit_place_graph.py` | 321 | Per-mind durable place graph and per-beat spatial experience. | `world.spatial` |
| `persist/commit_room_registry.py` | 486 | Room identity across frames: registry projection, mint dedup, renames, retirement, exit pruning. | `core.db`, `persist.commit_common`, `story.character_schema`, `world.spatial` |
| `persist/commit_scene_state.py` | 1421 | The prepared post-turn scene: pre-lock build, scene commit domain, book anchoring, ground advance. | `core.db`, `core.pipeline_context`, `mind.memory`, `persist.commit_attire`, `persist.commit_common`, `persist.commit_destruction`, `persist.commit_room_registry`, `story.character_schema`, `story.provenance_text`, `world.mechanics`, `world.spatial`, `world.spatial_frames`, `world.weather` |
| `persist/llm_capture.py` | 229 |  | `core.db` |
| `persist/pipeline_trace.py` | 574 | Privacy-conscious export, validation, and offline replay of persisted pipeline history. | `core.db` |
| `story/__init__.py` | 6 |  | — |
| `story/artifacts.py` | 649 |  | `llm.prompts` |
| `story/attire.py` | 3358 |  | — |
| `story/authored_events.py` | 225 |  | `core.db` |
| `story/carriers.py` | 788 |  | `core.db`, `story.character_schema`, `story.scene`, `world`, `world.spatial` |
| `story/character_schema.py` | 2306 | Versioned character/persona defaults, normalization, accessors, and export payloads. | `llm.schemas`, `story` |
| `story/couriers.py` | 1122 |  | `story.carriers`, `world` |
| `story/dialogue_colors.py` | 268 |  | — |
| `story/greetings.py` | 1008 |  | `agents.runtime`, `agents.storage`, `core`, `llm.llm_quality`, `llm.prompts`, `mind.memory`, `mind.theory_of_mind`, `story.character_schema`, `story.importers` |
| `story/history_routing.py` | 215 |  | — |
| `story/importers.py` | 3124 | Native and AI-assisted character, persona, and lorebook import/generation. | `core.db`, `core.logging_utils`, `llm.prompts`, `llm.providers`, `mind.memory`, `story.character_schema`, `story.scene` |
| `story/journey_history.py` | 431 |  | — |
| `story/lore_structure.py` | 248 |  | — |
| `story/mandates.py` | 369 |  | `core.db` |
| `story/naming.py` | 555 |  | `core.db`, `world.charter_identity` |
| `story/plot_packages.py` | 2163 |  | — |
| `story/provenance_text.py` | 132 |  | — |
| `story/room_bible.py` | 421 |  | `core.db` |
| `story/room_conversation.py` | 485 |  | `core.db` |
| `story/room_frontier.py` | 217 |  | `core.db` |
| `story/room_proposals.py` | 264 |  | `core.db` |
| `story/room_research.py` | 371 |  | `core.db` |
| `story/room_tools.py` | 819 |  | `story.plot_packages`, `story.room_research` |
| `story/scene.py` | 2731 | Scene/cast/persona helpers, recent events, dialogue configuration, and private knowledge. | `core.db`, `story`, `story.attire`, `story.character_schema`, `world.day_cycle`, `world.spatial` |
| `web/__init__.py` | 6 |  | — |
| `web/app.py` | 6813 | FastAPI application assembly, resource CRUD, turn control, and streaming endpoints. | `agents`, `agents.story_planner`, `core`, `core.db`, `core.frames`, `core.paths`, `dressing.ambience`, `dressing.backdrops`, `llm`, `llm.prompts`, `llm.providers`, `mind.memory`, `persist.chat_archive`, `persist.chat_delete`, `persist.checkpoints`, `persist.commit`, `story`, `story.character_schema`, `story.dialogue_colors`, `story.importers`, `story.scene`, `web`, `web.auth_routes`, `web.room_routes`, `world`, `world.survival` |
| `web/auth_routes.py` | 279 | Typed host-authentication HTTP routes and cookie transport. | `web` |
| `web/guest_access.py` | 554 |  | `core.db` |
| `web/room_routes.py` | 119 |  | `core.db`, `story` |
| `web/story_view.py` | 1023 |  | `core.db`, `world.charter_runtime`, `world.living_world` |
| `world/__init__.py` | 6 |  | — |
| `world/background_claims.py` | 598 |  | `core.db` |
| `world/charter.py` | 479 |  | `world.charter_author`, `world.charter_chatter`, `world.charter_commitment`, `world.charter_decide`, `world.charter_drift`, `world.charter_economy`, `world.charter_feel`, `world.charter_figure`, `world.charter_identity`, `world.charter_intervene`, `world.charter_log`, `world.charter_mark`, `world.charter_mind`, `world.charter_model`, `world.charter_move`, `world.charter_needs`, `world.charter_news`, `world.charter_plan`, `world.charter_politics`, `world.charter_practice`, `world.charter_promote`, `world.charter_roster`, `world.charter_run`, `world.charter_social`, `world.charter_space`, `world.charter_talk`, `world.charter_temper`, `world.charter_trigger` |
| `world/charter_author.py` | 800 |  | `world.charter_commitment`, `world.charter_economy`, `world.charter_figure`, `world.charter_mark`, `world.charter_mind`, `world.charter_model`, `world.charter_politics`, `world.charter_practice` |
| `world/charter_chatter.py` | 443 |  | `world.crowds` |
| `world/charter_commitment.py` | 292 |  | `world.charter_model` |
| `world/charter_creature.py` | 363 |  | `world.charter_harm`, `world.charter_model` |
| `world/charter_crowd.py` | 276 |  | `world.crowds` |
| `world/charter_decide.py` | 279 |  | `world.charter_model`, `world.charter_news` |
| `world/charter_drift.py` | 106 |  | `world.charter_model` |
| `world/charter_economy.py` | 427 |  | `world.charter_model` |
| `world/charter_enrol.py` | 419 |  | `world.charter_generate`, `world.charter_model`, `world.charter_needs`, `world.charter_roster`, `world.charter_surface` |
| `world/charter_feel.py` | 444 |  | `mind.psychology_runtime`, `world.charter_mark`, `world.charter_needs`, `world.charter_temper` |
| `world/charter_figure.py` | 140 |  | — |
| `world/charter_generate.py` | 1320 |  | `world.charter_identity`, `world.charter_model`, `world.charter_needs`, `world.charter_roster`, `world.charter_surface` |
| `world/charter_harm.py` | 264 |  | — |
| `world/charter_history.py` | 873 |  | — |
| `world/charter_identity.py` | 1167 |  | — |
| `world/charter_intervene.py` | 343 |  | `world.charter_model` |
| `world/charter_log.py` | 510 |  | `world.charter_commitment`, `world.charter_decide`, `world.charter_economy`, `world.charter_feel`, `world.charter_mark`, `world.charter_mind`, `world.charter_model`, `world.charter_needs`, `world.charter_news`, `world.charter_politics`, `world.charter_social`, `world.charter_temper` |
| `world/charter_mark.py` | 302 |  | — |
| `world/charter_mind.py` | 262 |  | — |
| `world/charter_model.py` | 748 |  | `world.charter_chatter`, `world.charter_figure`, `world.charter_harm`, `world.charter_mark` |
| `world/charter_move.py` | 411 |  | `world.charter_space` |
| `world/charter_needs.py` | 297 |  | `world.charter_model` |
| `world/charter_news.py` | 517 |  | `world.charter_mind`, `world.charter_model`, `world.charter_talk` |
| `world/charter_observe.py` | 542 |  | `world.charter_figure`, `world.charter_identity`, `world.charter_mind`, `world.spatial` |
| `world/charter_plan.py` | 227 |  | `world.charter_drift`, `world.charter_model`, `world.charter_roster` |
| `world/charter_politics.py` | 161 |  | — |
| `world/charter_practice.py` | 1200 |  | `world.charter_commitment`, `world.charter_figure`, `world.charter_mind`, `world.charter_politics`, `world.charter_talk` |
| `world/charter_predation.py` | 712 |  | `world.charter_creature`, `world.charter_harm`, `world.charter_model`, `world.charter_move` |
| `world/charter_promote.py` | 604 |  | `world.charter_commitment`, `world.charter_feel`, `world.charter_politics`, `world.charter_social` |
| `world/charter_roster.py` | 134 |  | `world.charter_model` |
| `world/charter_run.py` | 1464 |  | `world`, `world.charter_commitment`, `world.charter_decide`, `world.charter_drift`, `world.charter_economy`, `world.charter_enrol`, `world.charter_feel`, `world.charter_figure`, `world.charter_harm`, `world.charter_intervene`, `world.charter_log`, `world.charter_mark`, `world.charter_mind`, `world.charter_model`, `world.charter_move`, `world.charter_needs`, `world.charter_news`, `world.charter_plan`, `world.charter_politics`, `world.charter_practice`, `world.charter_roster`, `world.charter_social`, `world.charter_space`, `world.charter_talk`, `world.charter_trigger` |
| `world/charter_runtime.py` | 3809 |  | `core`, `core.logging_utils`, `world.charter`, `world.charter_news`, `world.charter_surface`, `world.day_cycle`, `world.mechanics` |
| `world/charter_social.py` | 743 |  | `world.charter_politics` |
| `world/charter_space.py` | 167 |  | `world.spatial` |
| `world/charter_surface.py` | 341 |  | — |
| `world/charter_surgery.py` | 341 |  | — |
| `world/charter_talk.py` | 351 |  | `world.charter_mind`, `world.charter_politics`, `world.charter_roster` |
| `world/charter_temper.py` | 167 |  | — |
| `world/charter_trigger.py` | 881 |  | `world.charter_mark`, `world.charter_news`, `world.charter_practice` |
| `world/comfort.py` | 349 |  | `world.spatial` |
| `world/crowds.py` | 759 |  | `world.spatial` |
| `world/day_cycle.py` | 351 |  | — |
| `world/degradation.py` | 171 |  | — |
| `world/gaps.py` | 454 |  | `core.db`, `mind.canon_provenance`, `world.spatial`, `world.subjects` |
| `world/living_world.py` | 596 |  | `core.logging_utils`, `world.mechanics` |
| `world/mechanics.py` | 930 |  | `core`, `world.spatial`, `world.spatial_frames` |
| `world/offscreen.py` | 2238 |  | `core`, `core.logging_utils`, `llm.prompts` |
| `world/paradox.py` | 648 |  | `core.db`, `core.frames`, `story.character_schema`, `world.spatial` |
| `world/place_purpose.py` | 545 |  | `mind.theory_of_mind`, `world.comfort`, `world.spatial`, `world.survival` |
| `world/planned_entities.py` | 290 |  | `core.db` |
| `world/planning_needs.py` | 346 |  | — |
| `world/region_events.py` | 420 |  | — |
| `world/routines.py` | 208 |  | — |
| `world/spatial.py` | 241 | Deterministic room, barrier, hearing, visibility, placement, and scene-diff logic. | `llm.schemas`, `world.spatial_barriers`, `world.spatial_contact_migration`, `world.spatial_contacts`, `world.spatial_containment`, `world.spatial_fov`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_light`, `world.spatial_merge`, `world.spatial_orientation`, `world.spatial_prose`, `world.spatial_routing`, `world.spatial_senses`, `world.spatial_substance`, `world.spatial_transit` |
| `world/spatial_barriers.py` | 666 |  | `world.spatial_orientation` |
| `world/spatial_contact_migration.py` | 331 |  | `world.spatial_contacts`, `world.spatial_identity` |
| `world/spatial_contacts.py` | 1864 |  | `world.spatial_containment`, `world.spatial_identity`, `world.spatial_transit` |
| `world/spatial_containment.py` | 2980 |  | `world.spatial_barriers`, `world.spatial_identity`, `world.spatial_transit` |
| `world/spatial_fov.py` | 857 |  | `world.spatial_barriers`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_orientation` |
| `world/spatial_frames.py` | 1087 |  | `core.db`, `core.frames`, `story.character_schema`, `story.scene`, `world.paradox`, `world.spatial` |
| `world/spatial_geometry.py` | 1472 |  | `world.spatial_barriers`, `world.spatial_contacts`, `world.spatial_containment`, `world.spatial_identity`, `world.spatial_orientation` |
| `world/spatial_identity.py` | 498 |  | — |
| `world/spatial_light.py` | 240 |  | `world.spatial_barriers`, `world.spatial_geometry`, `world.spatial_identity` |
| `world/spatial_merge.py` | 1664 |  | `llm.schemas`, `world.spatial_barriers`, `world.spatial_contact_migration`, `world.spatial_contacts`, `world.spatial_containment`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_orientation`, `world.spatial_routing`, `world.spatial_senses`, `world.spatial_substance`, `world.spatial_transit` |
| `world/spatial_orientation.py` | 246 | Bearing math and reciprocal spatial-edge normalization. | — |
| `world/spatial_prose.py` | 397 |  | `world.spatial_contacts`, `world.spatial_containment`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_light` |
| `world/spatial_routing.py` | 1098 |  | `world.spatial_barriers`, `world.spatial_containment`, `world.spatial_light`, `world.spatial_orientation` |
| `world/spatial_senses.py` | 1281 |  | `world.spatial_barriers`, `world.spatial_contacts`, `world.spatial_containment`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_light`, `world.spatial_orientation`, `world.spatial_routing` |
| `world/spatial_substance.py` | 1128 |  | `world.spatial_contacts`, `world.spatial_identity` |
| `world/spatial_transit.py` | 517 |  | `world.spatial_barriers`, `world.spatial_identity` |
| `world/stimulation.py` | 239 |  | `story`, `world.spatial` |
| `world/structure.py` | 723 |  | `world.charter_model`, `world.spatial` |
| `world/subjects.py` | 500 |  | `core.db`, `mind.canon_provenance`, `world.spatial` |
| `world/survival.py` | 354 |  | `core.db` |
| `world/weather.py` | 840 |  | `world.spatial` |

## Largest top-level functions

### `agents/background.py`

| Function | Start | Size |
|---|---:|---:|
| `_react_one()` | 1474 | 180 lines |
| `_background_react()` | 421 | 176 lines |
| `scene_life()` | 1002 | 157 lines |
| `_demanded_presences()` | 816 | 118 lines |
| `_beat_for_presence()` | 171 | 80 lines |
| `_present_others()` | 1392 | 80 lines |
| `managed_presences()` | 671 | 78 lines |
| `_filtered_player_declaration()` | 92 | 77 lines |

### `agents/character.py`

| Function | Start | Size |
|---|---:|---:|
| `character_step()` | 2989 | 1172 lines |
| `_annotate_known_exits()` | 2340 | 458 lines |
| `_ground_observation_citations()` | 1337 | 306 lines |
| `_unanswered_question_note()` | 501 | 221 lines |
| `_destination_from_goals()` | 1906 | 109 lines |
| `sprint_offers()` | 2833 | 97 lines |
| `_recent_self_moves()` | 232 | 86 lines |
| `strip_beat_reissues()` | 938 | 82 lines |

### `agents/common.py`

| Function | Start | Size |
|---|---:|---:|
| `norm_sequence()` | 3473 | 284 lines |
| `_check_narrator_fidelity()` | 8775 | 208 lines |
| `presence_figures_for_room()` | 1808 | 177 lines |
| `_unknown_actor_label()` | 4233 | 152 lines |
| `_scrub_invented_dialogue()` | 7415 | 151 lines |
| `observer_body_regions()` | 1443 | 137 lines |
| `validated_player_state_assertions()` | 9096 | 121 lines |
| `_extract_authority_claims()` | 2860 | 120 lines |

### `agents/composer.py`

| Function | Start | Size |
|---|---:|---:|
| `observations_from_render()` | 3242 | 209 lines |
| `_render_view_english()` | 2741 | 153 lines |
| `pose_percepts()` | 1316 | 144 lines |
| `presence_percepts()` | 799 | 106 lines |
| `_pose_referent()` | 1017 | 91 lines |
| `_render_episode_english()` | 3043 | 84 lines |
| `_render_standing()` | 2599 | 82 lines |
| `observer_display_map()` | 437 | 80 lines |

### `agents/director.py`

| Function | Start | Size |
|---|---:|---:|
| `director_resolve()` | 2810 | 1789 lines |
| `director_interpret()` | 650 | 630 lines |
| `_reconcile_resolution()` | 1656 | 522 lines |
| `_run_specialists()` | 2380 | 263 lines |
| `director_establish()` | 315 | 159 lines |
| `_reconcile_interpretation()` | 1282 | 139 lines |
| `_specialist_repairs()` | 1483 | 119 lines |
| `_ground_public_evidence()` | 2685 | 112 lines |

### `agents/director_contact.py`

| Function | Start | Size |
|---|---:|---:|
| `_validated_player_contact_assertions()` | 57 | 130 lines |
| `_merge_player_contact_assertions()` | 189 | 85 lines |
| `_character_material_effects()` | 335 | 52 lines |
| `_validated_character_contact_endings()` | 276 | 51 lines |
| `_merge_character_material_effects()` | 389 | 35 lines |
| `_merge_character_contact_endings()` | 426 | 32 lines |
| `_drop_momentary_contact_adds()` | 29 | 19 lines |
| `_canonical_scene_subject()` | 49 | 6 lines |

### `agents/director_evidence.py`

| Function | Start | Size |
|---|---:|---:|
| `_evidence_present()` | 778 | 301 lines |
| `_merge_repair_into_diff()` | 507 | 59 lines |
| `_fold_derived_manifest_events()` | 1132 | 56 lines |
| `_interpret_coverage_corpus()` | 91 | 53 lines |
| `_subject_is_somewhere()` | 729 | 47 lines |
| `_strip_blank_diff_placeholders()` | 256 | 42 lines |
| `_omission_subject_encoded()` | 680 | 37 lines |
| `_manifest_items()` | 1086 | 37 lines |

### `agents/director_fanout.py`

| Function | Start | Size |
|---|---:|---:|
| `_specialist_payload()` | 285 | 269 lines |
| `_orchestration_scope_backstop()` | 680 | 151 lines |
| `_resolve_beat_view()` | 73 | 127 lines |
| `_interpret_beat_view()` | 202 | 40 lines |
| `_resolved_event_verdicts()` | 590 | 30 lines |
| `_author_emitted_channels()` | 642 | 25 lines |
| `_note_for()` | 260 | 24 lines |
| `fanout_is_parallel()` | 35 | 20 lines |

### `agents/director_floors.py`

| Function | Start | Size |
|---|---:|---:|
| `_bind_minted_entities_to_present_figures()` | 1427 | 160 lines |
| `_awareness_exits()` | 689 | 98 lines |
| `_release_attempts()` | 947 | 93 lines |
| `_conditions_view()` | 569 | 87 lines |
| `_narrated_destruction_subjects()` | 1207 | 79 lines |
| `_unsupported_character_awareness()` | 284 | 66 lines |
| `_restraint_exits()` | 1073 | 64 lines |
| `_clause_attributed_subjects()` | 406 | 57 lines |

### `agents/director_lingua.py`

| Function | Start | Size |
|---|---:|---:|
| `_ling()` | 16 | 14 lines |

### `agents/director_movement.py`

| Function | Start | Size |
|---|---:|---:|
| `_reconcile_near_group_positions()` | 157 | 276 lines |
| `_travel_continues()` | 838 | 109 lines |
| `_apply_following_movement()` | 524 | 88 lines |
| `_guard_approach_is_not_arrival()` | 949 | 80 lines |
| `_unreachable_position_writes()` | 613 | 68 lines |
| `_travel_in_flight_view()` | 787 | 49 lines |
| `_egocentric_exits()` | 29 | 48 lines |
| `_resolve_movement_mover()` | 683 | 37 lines |

### `agents/director_reconcile.py`

| Function | Start | Size |
|---|---:|---:|
| `_verify_already_true()` | 365 | 126 lines |
| `_scale_relation_conflicts()` | 211 | 107 lines |
| `_player_claim_findings()` | 60 | 80 lines |
| `_stamp_dialogue_articulation()` | 145 | 64 lines |
| `_acquit_addressed_events()` | 493 | 52 lines |
| `_route_repair_omissions()` | 553 | 40 lines |
| `_verify_no_referent()` | 336 | 27 lines |
| `_deep_audit_mode()` | 48 | 11 lines |

### `agents/director_scopes.py`

| Function | Start | Size |
|---|---:|---:|
| `_gate_facts()` | 612 | 76 lines |
| `_dispatch_specialists()` | 795 | 62 lines |
| `register_specialist()` | 470 | 49 lines |
| `_ruling_for()` | 727 | 39 lines |
| `_rebuild_channel_owners()` | 439 | 25 lines |
| `_unrouted_rulings()` | 768 | 25 lines |
| `_schema_list_channels()` | 253 | 23 lines |
| `reads_dialogue()` | 161 | 18 lines |

### `agents/director_views.py`

| Function | Start | Size |
|---|---:|---:|
| `_report_unowned_address_forms()` | 312 | 152 lines |
| `_report_observer_epithets()` | 241 | 69 lines |
| `_crowds_view()` | 466 | 68 lines |
| `_route_authorial_npc_beat()` | 65 | 48 lines |
| `_couriers_view()` | 536 | 32 lines |
| `_audit_fact_adjudications()` | 196 | 31 lines |
| `_round_conduct()` | 165 | 29 lines |
| `_artifacts_view()` | 570 | 29 lines |

### `agents/dramaturge.py`

| Function | Start | Size |
|---|---:|---:|
| `propose()` | 189 | 82 lines |
| `_payload()` | 131 | 36 lines |
| `revise()` | 273 | 36 lines |
| `player_visible_stream()` | 92 | 31 lines |
| `_file()` | 173 | 14 lines |
| `_call()` | 78 | 8 lines |
| `system_block()` | 125 | 4 lines |

### `agents/loops.py`

| Function | Start | Size |
|---|---:|---:|
| `interaction_loop()` | 618 | 649 lines |
| `deterministic_micro_perception()` | 196 | 144 lines |
| `reaction_loop()` | 1268 | 70 lines |
| `rehydrate_loop_views()` | 87 | 59 lines |
| `self_micro_view()` | 148 | 46 lines |
| `_drop_absent()` | 355 | 45 lines |
| `_isolated_wave()` | 575 | 41 lines |
| `_defer_to_unrun_reactor()` | 432 | 37 lines |

### `agents/mapping.py`

| Function | Start | Size |
|---|---:|---:|
| `compile_world_context()` | 309 | 148 lines |
| `rulebook_rows()` | 208 | 99 lines |
| `classify_movement()` | 129 | 38 lines |
| `_location_query_status()` | 169 | 33 lines |
| `merge_lore()` | 459 | 33 lines |
| `is_contained_destination()` | 95 | 32 lines |
| `_query()` | 68 | 25 lines |
| `_lore_row()` | 64 | 2 lines |

### `agents/narration.py`

| Function | Start | Size |
|---|---:|---:|
| `narrator()` | 1386 | 368 lines |
| `_ordered_beat_events()` | 523 | 230 lines |
| `_sensory_channels_manifest()` | 329 | 165 lines |
| `narrator_extra()` | 1793 | 161 lines |
| `_visible_portal_states()` | 845 | 88 lines |
| `_generate_narration()` | 1237 | 74 lines |
| `_render_observed_events()` | 1052 | 69 lines |
| `_resolve_narration_person()` | 114 | 66 lines |

### `agents/perception.py`

| Function | Start | Size |
|---|---:|---:|
| `_composer_outcome()` | 4278 | 456 lines |
| `perception_outcome()` | 2369 | 282 lines |
| `_composer_standing_percepts()` | 3467 | 221 lines |
| `perception_act()` | 1940 | 182 lines |
| `_composer_act()` | 3902 | 172 lines |
| `_outcome_event_stream()` | 665 | 152 lines |
| `_source_channels()` | 931 | 131 lines |
| `_scent_sources_for()` | 3297 | 129 lines |

### `agents/runtime.py`

| Function | Start | Size |
|---|---:|---:|
| `_run_pipeline()` | 997 | 330 lines |
| `build_plan()` | 738 | 109 lines |
| `resume_key_for_turn()` | 645 | 92 lines |
| `_load_extra_players()` | 50 | 74 lines |
| `_stream_one()` | 448 | 68 lines |
| `_stream_parallel()` | 517 | 60 lines |
| `_with_engine_notes()` | 388 | 55 lines |
| `run_pipeline()` | 1328 | 55 lines |

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

### `agents/story_planner.py`

| Function | Start | Size |
|---|---:|---:|
| `run_planner()` | 427 | 189 lines |
| `deliberate()` | 702 | 91 lines |
| `schedule_room_work()` | 884 | 55 lines |
| `_payload()` | 235 | 52 lines |
| `run_dramaturge_pass()` | 795 | 40 lines |
| `_run_task()` | 618 | 32 lines |
| `charter_planner()` | 360 | 30 lines |
| `planner_reply()` | 652 | 27 lines |

### `core/db.py`

| Function | Start | Size |
|---|---:|---:|
| `_migrate_chat_copies_to_overlays()` | 2085 | 133 lines |
| `init()` | 2376 | 113 lines |
| `_recover_scene_time_of_day()` | 2306 | 59 lines |
| `transaction()` | 1910 | 43 lines |
| `conn()` | 1870 | 38 lines |
| `_opening_time_of_day()` | 2250 | 30 lines |
| `_establish_time_of_day_from_variant()` | 2220 | 28 lines |
| `wset()` | 2545 | 23 lines |

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
| `_clear_turn_scoped_context()` | 119 | 36 lines |
| `submit()` | 71 | 35 lines |
| `_run()` | 157 | 23 lines |
| `story_rewound_past()` | 280 | 20 lines |
| `_finish()` | 182 | 17 lines |
| `drain()` | 238 | 17 lines |
| `reset()` | 302 | 16 lines |
| `cancel()` | 201 | 13 lines |

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
| `canonical_movement()` | 101 | 18 lines |
| `note_step_decision()` | 86 | 12 lines |
| `note_step_warning()` | 46 | 11 lines |
| `note_step_exchange()` | 75 | 9 lines |

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
| `generate_backdrop()` | 1119 | 115 lines |
| `room_projection()` | 566 | 73 lines |
| `visual_signature()` | 175 | 48 lines |
| `build_backdrop_request()` | 767 | 46 lines |
| `scene_after_turn()` | 730 | 35 lines |
| `branch_lineage()` | 256 | 34 lines |
| `compose_prompt()` | 884 | 34 lines |
| `compose_revision()` | 946 | 33 lines |

### `llm/llm_quality.py`

| Function | Start | Size |
|---|---:|---:|
| `complete_validated_json()` | 385 | 429 lines |
| `_targeted_field_patch()` | 188 | 63 lines |
| `output_ran_out_of_room()` | 77 | 47 lines |
| `_extract_balanced_object()` | 23 | 34 lines |
| `_step_json_schema()` | 354 | 29 lines |
| `_character_wire_schema()` | 329 | 23 lines |
| `strict_json_parse()` | 126 | 19 lines |
| `_accepted()` | 253 | 19 lines |

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
| `_relocate_character_identity()` | 414 | 31 lines |
| `character_prompt()` | 464 | 28 lines |
| `normalize_preset()` | 122 | 26 lines |
| `specialist_prompt()` | 323 | 23 lines |
| `_preset_override()` | 206 | 22 lines |
| `_assembled_sheets()` | 38 | 21 lines |
| `prose_author_prompt()` | 353 | 17 lines |

### `llm/providers.py`

| Function | Start | Size |
|---|---:|---:|
| `_chat_complete_once()` | 2514 | 321 lines |
| `chat_complete()` | 2247 | 119 lines |
| `async _chat_complete_async_once()` | 2956 | 115 lines |
| `async chat_complete_async()` | 2865 | 90 lines |
| `_sse_openai()` | 2097 | 86 lines |
| `async _sse_openai_async()` | 3072 | 70 lines |
| `_sse_anthropic()` | 2184 | 62 lines |
| `_embed_request()` | 3400 | 59 lines |

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
| `preprocess_llm_output()` | 4202 | 327 lines |
| `_lenient_coerce()` | 745 | 159 lines |
| `validate_llm_output_strict()` | 5322 | 130 lines |
| `semantic_output_errors()` | 5119 | 108 lines |
| `canonicalize_prose_markup()` | 4007 | 102 lines |
| `_uncross_concealed_speech()` | 4131 | 69 lines |
| `_coerce_list_valued_map()` | 128 | 57 lines |
| `_coerce_conditions()` | 3556 | 55 lines |

### `mind/affect.py`

| Function | Start | Size |
|---|---:|---:|
| `resolve_affect()` | 791 | 184 lines |
| `apply_intent_ops()` | 1207 | 164 lines |
| `appraise()` | 480 | 145 lines |
| `apply_project_ops()` | 1612 | 137 lines |
| `settle_intent_world_anchors()` | 1433 | 132 lines |
| `normalize_wants()` | 981 | 89 lines |
| `update_drive_strain()` | 2063 | 83 lines |
| `validate_drive_shift()` | 2189 | 79 lines |

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
| `_kw_scores()` | 186 | 31 lines |
| `surviving_character_ids()` | 239 | 17 lines |
| `_cos()` | 218 | 16 lines |
| `_b64_to_blob()` | 155 | 14 lines |
| `_ling()` | 13 | 10 lines |
| `_blob_to_b64()` | 144 | 10 lines |
| `_ids()` | 174 | 7 lines |
| `_storage_json()` | 169 | 4 lines |

### `mind/memory_context.py`

| Function | Start | Size |
|---|---:|---:|
| `build_character_memory_context()` | 241 | 383 lines |
| `_with_reading()` | 24 | 101 lines |
| `_origin_on_drift()` | 143 | 96 lines |
| `_summary_id()` | 138 | 3 lines |

### `mind/memory_inference.py`

| Function | Start | Size |
|---|---:|---:|
| `reconcile_inference_confidence()` | 85 | 70 lines |
| `_abandoned_confidence()` | 70 | 13 lines |
| `_mint_confidence_of()` | 56 | 12 lines |

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

### `mind/memory_lore_entries.py`

| Function | Start | Size |
|---|---:|---:|
| `search_lore()` | 421 | 93 lines |
| `knowledge_for_character()` | 742 | 93 lines |
| `backfill_lore_embedding_stamps()` | 515 | 71 lines |
| `duplicate_lorebook_tree_for_chat()` | 191 | 69 lines |
| `set_lore_overlay()` | 345 | 65 lines |
| `lore_embedding_health()` | 588 | 62 lines |
| `add_lore()` | 99 | 46 lines |
| `update_lore()` | 146 | 44 lines |

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
| `record_dispute()` | 239 | 84 lines |
| `update_memory()` | 187 | 51 lines |
| `visible_memory_rows()` | 51 | 45 lines |
| `raise_importance()` | 325 | 44 lines |
| `list_memories()` | 159 | 27 lines |
| `dramatic_irony_feed()` | 109 | 26 lines |
| `promise_ledger()` | 136 | 22 lines |
| `delete_memory()` | 371 | 3 lines |

### `mind/memory_relationships.py`

| Function | Start | Size |
|---|---:|---:|
| `update_relationships_from_inference()` | 183 | 55 lines |
| `apply_relationship_updates()` | 124 | 50 lines |
| `record_relationship_event()` | 84 | 25 lines |
| `relationship_history()` | 111 | 11 lines |
| `get_relationships()` | 59 | 7 lines |
| `save_relationships()` | 67 | 7 lines |
| `relationships_for_payload()` | 239 | 3 lines |

### `mind/memory_retrieval.py`

| Function | Start | Size |
|---|---:|---:|
| `search_memories()` | 471 | 335 lines |
| `contrast_memory()` | 967 | 125 lines |
| `_rank_normalized_importance()` | 408 | 61 lines |
| `recall_confidence()` | 873 | 58 lines |
| `recent_memory_buffer()` | 1106 | 41 lines |
| `_exact_cue_score()` | 96 | 33 lines |
| `_congruence_valence()` | 314 | 29 lines |
| `_warn_stranded_embeddings()` | 369 | 29 lines |

### `mind/memory_snapshot.py`

| Function | Start | Size |
|---|---:|---:|
| `import_character_memories()` | 453 | 109 lines |
| `restore_lorebook()` | 723 | 97 lines |
| `prepare_chat_memory_restore()` | 251 | 89 lines |
| `dump_chat_memories()` | 167 | 75 lines |
| `restore_memory_vectors()` | 111 | 54 lines |
| `restore_lore_overlays()` | 679 | 42 lines |
| `_foreign_persona_names()` | 410 | 41 lines |
| `apply_chat_memory_restore()` | 341 | 40 lines |

### `mind/memory_summaries.py`

| Function | Start | Size |
|---|---:|---:|
| `backfill_memory_summary_windows()` | 501 | 89 lines |
| `search_memory_summaries()` | 69 | 88 lines |
| `consolidate_character_memory()` | 592 | 75 lines |
| `derive_summary_support()` | 176 | 59 lines |
| `_write_consolidated_window()` | 403 | 57 lines |
| `save_memory_summary()` | 258 | 39 lines |
| `get_memory_summary()` | 30 | 38 lines |
| `memory_summary_coverage()` | 462 | 37 lines |

### `mind/memory_time.py`

| Function | Start | Size |
|---|---:|---:|
| `time_ago_span()` | 138 | 33 lines |
| `window_clock_readings()` | 302 | 31 lines |
| `current_clock_reading()` | 175 | 19 lines |
| `time_ago_phrase()` | 119 | 17 lines |
| `_rung()` | 90 | 14 lines |
| `elapsed_phrase()` | 110 | 7 lines |
| `_plural()` | 106 | 2 lines |

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
| `repair_pending_embeddings()` | 509 | 59 lines |
| `prepare_memory()` | 347 | 58 lines |
| `_extract_key_phrases()` | 173 | 48 lines |
| `_upsert_memory()` | 600 | 40 lines |
| `_row_memory()` | 307 | 39 lines |
| `_embed_in_request_sized_chunks()` | 677 | 37 lines |
| `repair_seed_salience()` | 799 | 30 lines |

### `mind/psychology_runtime.py`

| Function | Start | Size |
|---|---:|---:|
| `resolve_hedonic()` | 149 | 198 lines |
| `resolve_stress()` | 349 | 108 lines |
| `apply_belief_updates()` | 560 | 74 lines |
| `apply_association_updates()` | 636 | 49 lines |
| `_authored_beliefs()` | 512 | 46 lines |
| `cognitive_absorption()` | 705 | 45 lines |
| `_within_cap()` | 473 | 29 lines |
| `elapsed_psych_units()` | 132 | 15 lines |

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
| `_exportable_checkpoint_blob()` | 98 | 20 lines |
| `_exportable_world()` | 92 | 4 lines |
| `_model_validate()` | 120 | 4 lines |
| `_model_dump()` | 126 | 4 lines |

### `persist/chat_delete.py`

| Function | Start | Size |
|---|---:|---:|
| `delete_chat_data()` | 8 | 35 lines |

### `persist/checkpoints.py`

| Function | Start | Size |
|---|---:|---:|
| `snapshot_state()` | 16 | 190 lines |
| `_restore_checkpoint_body()` | 815 | 151 lines |
| `_restore_books()` | 265 | 148 lines |
| `compact_checkpoints()` | 1109 | 123 lines |
| `insert_world_tables()` | 501 | 105 lines |
| `ensure_checkpoint()` | 1298 | 53 lines |
| `propagate_memory_summaries_to_checkpoints()` | 1353 | 53 lines |
| `_verify_no_loss()` | 1057 | 50 lines |

### `persist/commit.py`

| Function | Start | Size |
|---|---:|---:|
| `_commit_all_locked()` | 454 | 314 lines |
| `commit_crowds()` | 267 | 149 lines |
| `commit_authored_events()` | 213 | 30 lines |
| `commit_narration_person()` | 181 | 29 lines |
| `_prepare_turn_commit()` | 431 | 12 lines |
| `commit_offscreen_epoch()` | 245 | 11 lines |
| `commit_all()` | 418 | 11 lines |
| `commit_offscreen_plans()` | 258 | 7 lines |

### `persist/commit_attire.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_attire_diff()` | 835 | 624 lines |
| `interpret_attire_notes()` | 251 | 115 lines |
| `_mint_shed_garments()` | 666 | 101 lines |
| `_fold_duplicate_shed_garments()` | 368 | 85 lines |
| `_fold_worn_garment_entities()` | 455 | 69 lines |
| `_merge_attire_regions()` | 30 | 65 lines |
| `_heal_attire_identity_keys()` | 97 | 61 lines |
| `_shed_record_candidates()` | 574 | 46 lines |

### `persist/commit_background.py`

| Function | Start | Size |
|---|---:|---:|
| `track_background_presences()` | 1443 | 752 lines |
| `pick_voice_demand()` | 2867 | 380 lines |
| `promote_background_character()` | 3393 | 344 lines |
| `_fold_duplicate_presences()` | 685 | 143 lines |
| `descriptor_bindings()` | 2514 | 100 lines |
| `auto_promote_background_characters()` | 3776 | 94 lines |
| `addressed_rooms()` | 2775 | 90 lines |
| `_mint_missing_presence_names()` | 1359 | 82 lines |

### `persist/commit_common.py`

| Function | Start | Size |
|---|---:|---:|
| `_names_heard_in()` | 248 | 63 lines |
| `_monotonic_elapsed()` | 72 | 53 lines |
| `_address_forms()` | 155 | 52 lines |
| `_resolve_roster_name()` | 462 | 47 lines |
| `_entity_alias_map()` | 521 | 47 lines |
| `charter_recognition_projection()` | 313 | 39 lines |
| `seed_mutual_recognition()` | 427 | 33 lines |
| `_registered_name_roster()` | 383 | 28 lines |

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
| `commit_world_entities()` | 215 | 346 lines |
| `_supersede_disguises()` | 96 | 74 lines |
| `_inherit_known_to()` | 172 | 41 lines |
| `_subjects_that_moved()` | 35 | 36 lines |
| `_subjects_targeted_by_an_action()` | 73 | 21 lines |
| `_is_gated_awareness()` | 17 | 16 lines |

### `persist/commit_ledgers.py`

| Function | Start | Size |
|---|---:|---:|
| `commit_world_pressure()` | 242 | 133 lines |
| `commit_obligations()` | 92 | 82 lines |
| `world_pressure_view()` | 198 | 22 lines |
| `_find_obligation()` | 59 | 21 lines |
| `pending_obligation_view()` | 38 | 20 lines |
| `_find_pressure()` | 222 | 18 lines |
| `_beats_open()` | 81 | 9 lines |

### `persist/commit_mapping.py`

| Function | Start | Size |
|---|---:|---:|
| `commit_mapping()` | 350 | 200 lines |
| `_apply_mapping_book_ops()` | 90 | 106 lines |
| `prepare_mapping_commit()` | 198 | 62 lines |
| `_setting_fact_needs()` | 262 | 47 lines |
| `_attach_committed_surface()` | 311 | 37 lines |
| `_file_engine_provenance()` | 60 | 28 lines |
| `_fact_is_covered()` | 557 | 18 lines |
| `_lore_for()` | 553 | 2 lines |

### `persist/commit_mechanics.py`

| Function | Start | Size |
|---|---:|---:|
| `commit_transit_sweep()` | 21 | 187 lines |
| `commit_information_carriers()` | 258 | 76 lines |
| `commit_cast_changes()` | 337 | 51 lines |
| `commit_world_event_spine()` | 210 | 46 lines |

### `persist/commit_memory.py`

| Function | Start | Size |
|---|---:|---:|
| `prepare_memory_commit()` | 386 | 1409 lines |
| `_cited_memory_ids()` | 80 | 76 lines |
| `_interior_relations_of()` | 329 | 55 lines |
| `_own_sequence_memory()` | 204 | 50 lines |
| `_intent_names_term()` | 288 | 39 lines |
| `_inference_memory_text()` | 256 | 30 lines |
| `_marked_for_memory()` | 158 | 24 lines |
| `_durable_dialogue_category()` | 57 | 22 lines |

### `persist/commit_memory_write.py`

| Function | Start | Size |
|---|---:|---:|
| `schedule_memory_consolidation()` | 78 | 85 lines |
| `commit_memories()` | 243 | 83 lines |
| `schedule_memory_tension_pass()` | 168 | 73 lines |
| `_consolidate_committed_memories()` | 22 | 51 lines |

### `persist/commit_place_graph.py`

| Function | Start | Size |
|---|---:|---:|
| `update_place_graph()` | 45 | 180 lines |
| `record_spatial_experience()` | 227 | 95 lines |

### `persist/commit_room_registry.py`

| Function | Start | Size |
|---|---:|---:|
| `dedup_minted_rooms()` | 132 | 113 lines |
| `_prepare_room_registry()` | 246 | 94 lines |
| `_refresh_relocated_location()` | 392 | 54 lines |
| `_apply_room_renames()` | 76 | 53 lines |
| `prune_dangling_exits()` | 448 | 39 lines |
| `_apply_room_registry()` | 342 | 28 lines |
| `_registry_alias_index()` | 53 | 22 lines |
| `sync_room_registry_with_scene()` | 371 | 19 lines |

### `persist/commit_scene_state.py`

| Function | Start | Size |
|---|---:|---:|
| `prepare_scene_commit()` | 607 | 765 lines |
| `_advance_day_cycle()` | 66 | 111 lines |
| `_merge_overlays()` | 537 | 68 lines |
| `sync_anchored_books()` | 195 | 66 lines |
| `_guard_occupied_mover_removal()` | 262 | 60 lines |
| `_dedupe_overlay_entries()` | 495 | 40 lines |
| `_advance_ground()` | 324 | 31 lines |
| `_overlay_ending_handles()` | 464 | 29 lines |

### `persist/llm_capture.py`

| Function | Start | Size |
|---|---:|---:|
| `record_exchange()` | 133 | 41 lines |
| `put_blob()` | 76 | 25 lines |
| `_payload_hashes()` | 110 | 21 lines |
| `exchanges_for_turn()` | 176 | 20 lines |
| `prune()` | 198 | 16 lines |
| `vacuum_blobs()` | 216 | 14 lines |
| `capture_enabled()` | 54 | 7 lines |
| `capture_bodies()` | 63 | 7 lines |

### `persist/pipeline_trace.py`

| Function | Start | Size |
|---|---:|---:|
| `validate_pipeline_trace()` | 174 | 128 lines |
| `export_turn_debug()` | 424 | 126 lines |
| `export_pipeline_trace()` | 80 | 92 lines |
| `replay_pipeline_trace()` | 304 | 68 lines |
| `write_pipeline_trace()` | 389 | 25 lines |
| `export_chat_debug()` | 552 | 23 lines |
| `_canonical_json()` | 45 | 14 lines |
| `load_pipeline_trace()` | 379 | 8 lines |

### `story/artifacts.py`

| Function | Start | Size |
|---|---:|---:|
| `run_artifacts()` | 183 | 202 lines |
| `schedule_artifact_wording()` | 475 | 66 lines |
| `mint_wording()` | 543 | 55 lines |
| `land_artifact_wording()` | 600 | 50 lines |
| `post_spoor()` | 420 | 48 lines |
| `reading_copy()` | 150 | 25 lines |
| `spoor_artifact()` | 397 | 21 lines |
| `new_artifact()` | 128 | 20 lines |

### `story/attire.py`

| Function | Start | Size |
|---|---:|---:|
| `advance()` | 2447 | 148 lines |
| `_attributed_scoped()` | 1785 | 139 lines |
| `normalize_regions()` | 516 | 133 lines |
| `garments_named_in()` | 2122 | 126 lines |
| `coerce_diff_shape()` | 1462 | 124 lines |
| `compact_line()` | 3217 | 123 lines |
| `perceptible_region_surfaces()` | 2718 | 100 lines |
| `apply_flat_change()` | 2820 | 89 lines |

### `story/authored_events.py`

| Function | Start | Size |
|---|---:|---:|
| `resolve_authored_events()` | 174 | 52 lines |
| `mint_authored_events()` | 107 | 47 lines |
| `_retired_text()` | 52 | 34 lines |
| `_event_id()` | 89 | 16 lines |
| `due_authored_events()` | 156 | 16 lines |

### `story/carriers.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_tellings()` | 590 | 199 lines |
| `advance_carriers()` | 124 | 137 lines |
| `_carriers()` | 395 | 73 lines |
| `_crowds_acquire()` | 263 | 56 lines |
| `persona_entry()` | 321 | 40 lines |
| `carried_reports_view()` | 470 | 36 lines |
| `_invented_claim()` | 527 | 34 lines |
| `_crowd_index()` | 563 | 25 lines |

### `story/character_schema.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_character_data()` | 1243 | 167 lines |
| `character_card_warnings()` | 2127 | 149 lines |
| `default_character_data()` | 697 | 125 lines |
| `_normalize_psychology()` | 314 | 83 lines |
| `_normalize_interior()` | 636 | 59 lines |
| `repair_character_shape()` | 1184 | 57 lines |
| `normalize_persona_data()` | 1411 | 55 lines |
| `_normalize_extra_parts()` | 547 | 52 lines |

### `story/couriers.py`

| Function | Start | Size |
|---|---:|---:|
| `run_couriers()` | 758 | 365 lines |
| `_exchange_stops()` | 536 | 220 lines |
| `advance_couriers()` | 283 | 78 lines |
| `_deliver()` | 463 | 71 lines |
| `new_courier()` | 221 | 47 lines |
| `_copy_of()` | 363 | 39 lines |
| `_player_name()` | 435 | 26 lines |
| `courier_uid()` | 157 | 15 lines |

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
| `start_story()` | 655 | 255 lines |
| `_seed_mind_state()` | 352 | 144 lines |
| `generate_greeting()` | 912 | 62 lines |
| `_seed_minds()` | 550 | 57 lines |
| `_route_mind_memories()` | 295 | 55 lines |
| `_seed_player_mind()` | 498 | 50 lines |
| `claim_greeting_mind()` | 609 | 44 lines |
| `extract_greeting()` | 123 | 35 lines |

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
| `apply_lorebook_plan()` | 2814 | 214 lines |
| `import_lorebook()` | 1615 | 212 lines |
| `draft_promoted_character()` | 739 | 142 lines |
| `_reinterpret_entries()` | 1488 | 126 lines |
| `fill_body_interior()` | 1236 | 122 lines |
| `_lore_gen_entry_batch()` | 2456 | 119 lines |
| `_run_lore_gen_job()` | 2579 | 112 lines |
| `fill_appearance()` | 1063 | 103 lines |

### `story/journey_history.py`

| Function | Start | Size |
|---|---:|---:|
| `compile_journey_history()` | 288 | 137 lines |
| `ground_journey_history()` | 169 | 92 lines |
| `_source_rows()` | 120 | 28 lines |
| `companion_of()` | 263 | 23 lines |
| `_model_value()` | 150 | 17 lines |
| `journey_event_count()` | 95 | 12 lines |
| `_content_key()` | 113 | 5 lines |
| `_text()` | 109 | 2 lines |

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
| `grant_mandate()` | 147 | 73 lines |
| `coverage()` | 243 | 16 lines |
| `_most_permissive()` | 287 | 15 lines |
| `expire_mandates()` | 222 | 14 lines |
| `fill_limit()` | 272 | 13 lines |
| `surprise_dial()` | 331 | 13 lines |
| `spend_limits()` | 304 | 12 lines |
| `beats_per_proposal()` | 346 | 12 lines |

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

### `story/plot_packages.py`

| Function | Start | Size |
|---|---:|---:|
| `publish_package()` | 1854 | 84 lines |
| `_package_checks()` | 1684 | 78 lines |
| `fire_due_clocks()` | 1979 | 77 lines |
| `normalize_package()` | 166 | 74 lines |
| `edit_package()` | 350 | 57 lines |
| `_world_snapshot()` | 475 | 52 lines |
| `draft_operation()` | 409 | 34 lines |
| `prepare_package()` | 1818 | 34 lines |

### `story/provenance_text.py`

| Function | Start | Size |
|---|---:|---:|
| `split_engine_provenance()` | 86 | 42 lines |
| `looks_like_engine_provenance()` | 81 | 3 lines |
| `strip_engine_provenance()` | 130 | 3 lines |

### `story/room_bible.py`

| Function | Start | Size |
|---|---:|---:|
| `fold()` | 357 | 52 lines |
| `render_block()` | 281 | 42 lines |
| `add_entry()` | 194 | 40 lines |
| `source_exists()` | 83 | 33 lines |
| `_row()` | 144 | 18 lines |
| `mark_paid()` | 236 | 16 lines |
| `_normalize_entry()` | 122 | 15 lines |
| `_evict()` | 180 | 12 lines |

### `story/room_conversation.py`

| Function | Start | Size |
|---|---:|---:|
| `converse_stream()` | 352 | 92 lines |
| `converse()` | 301 | 35 lines |
| `restore_room_messages()` | 456 | 30 lines |
| `status()` | 250 | 24 lines |
| `add_message()` | 164 | 23 lines |
| `normalize_mandate()` | 198 | 21 lines |
| `revoke_mandate()` | 231 | 17 lines |
| `messages()` | 148 | 14 lines |

### `story/room_frontier.py`

| Function | Start | Size |
|---|---:|---:|
| `rooms_ahead()` | 66 | 37 lines |
| `frontier_report()` | 105 | 29 lines |
| `record_spend()` | 173 | 14 lines |
| `fills_this_hour()` | 204 | 14 lines |
| `spend_this_hour()` | 189 | 13 lines |
| `_player_room()` | 53 | 11 lines |
| `record_fill()` | 155 | 11 lines |
| `record_measure()` | 136 | 8 lines |

### `story/room_proposals.py`

| Function | Start | Size |
|---|---:|---:|
| `file_proposal()` | 134 | 34 lines |
| `normalize_proposal()` | 64 | 31 lines |
| `judge_proposal()` | 170 | 30 lines |
| `revise_proposal()` | 202 | 21 lines |
| `settle_proposal()` | 225 | 17 lines |
| `_row()` | 97 | 9 lines |
| `_save()` | 108 | 9 lines |
| `record_pass()` | 244 | 7 lines |

### `story/room_research.py`

| Function | Start | Size |
|---|---:|---:|
| `web_search()` | 215 | 62 lines |
| `fetch_page()` | 279 | 49 lines |
| `tool_entries()` | 344 | 28 lines |
| `as_lore()` | 189 | 20 lines |
| `require_grant()` | 145 | 14 lines |
| `_save()` | 118 | 12 lines |
| `_load()` | 108 | 8 lines |
| `_with_templates()` | 330 | 8 lines |

### `story/room_tools.py`

| Function | Start | Size |
|---|---:|---:|
| `_t_inspect_contradictions()` | 475 | 71 lines |
| `_t_inspect_config()` | 399 | 69 lines |
| `_t_inspect_rooms()` | 186 | 49 lines |
| `_t_inspect_route()` | 237 | 44 lines |
| `_t_scan_lore()` | 125 | 33 lines |
| `_t_inspect_charters()` | 321 | 30 lines |
| `run_tool()` | 790 | 30 lines |
| `_t_inspect_reserved_identities()` | 286 | 26 lines |

### `story/scene.py`

| Function | Start | Size |
|---|---:|---:|
| `active_disguises()` | 583 | 82 lines |
| `normalize_transformed_parts()` | 674 | 60 lines |
| `recent_events_for_observer()` | 1804 | 59 lines |
| `_positive_presented_appearance()` | 871 | 58 lines |
| `awareness_conditions()` | 1200 | 58 lines |
| `normalize_style_guide()` | 2545 | 58 lines |
| `active_transformations()` | 736 | 54 lines |
| `director_context()` | 1864 | 53 lines |

### `web/app.py`

| Function | Start | Size |
|---|---:|---:|
| `turn_branch()` | 5562 | 450 lines |
| `chat_get()` | 3587 | 253 lines |
| `_remap_cp_blob()` | 1017 | 216 lines |
| `bootstrap()` | 1358 | 118 lines |
| `dlg_put()` | 4805 | 98 lines |
| `_stream()` | 663 | 91 lines |
| `chat_add_char()` | 3842 | 91 lines |
| `_ambience_payload()` | 6588 | 75 lines |

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

### `web/room_routes.py`

| Function | Start | Size |
|---|---:|---:|
| `room_say_stream()` | 78 | 27 lines |
| `room_thread()` | 52 | 10 lines |
| `room_say()` | 65 | 10 lines |
| `room_revoke()` | 108 | 6 lines |
| `_chat_and_frame()` | 44 | 5 lines |
| `room_status()` | 117 | 3 lines |

### `web/story_view.py`

| Function | Start | Size |
|---|---:|---:|
| `_living_world()` | 329 | 98 lines |
| `_people()` | 834 | 77 lines |
| `_player_view_in_frame()` | 964 | 60 lines |
| `player_view()` | 913 | 49 lines |
| `_story_view_in_frame()` | 451 | 46 lines |
| `_public_facts()` | 654 | 46 lines |
| `viewers()` | 517 | 36 lines |
| `_person_refs()` | 751 | 36 lines |

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

### `world/charter_author.py`

| Function | Start | Size |
|---|---:|---:|
| `_figure_dealing()` | 547 | 135 lines |
| `authored()` | 148 | 134 lines |
| `_figure_act()` | 309 | 78 lines |
| `acts_in_evidence()` | 723 | 53 lines |
| `preview_dealings()` | 494 | 43 lines |
| `dealing_answer()` | 453 | 39 lines |
| `has_standing()` | 389 | 35 lines |
| `good_named()` | 688 | 33 lines |

### `world/charter_chatter.py`

| Function | Start | Size |
|---|---:|---:|
| `participant_forms()` | 319 | 47 lines |
| `overheard_fragment()` | 228 | 44 lines |
| `window_acts()` | 74 | 34 lines |
| `relabel_fragment()` | 393 | 32 lines |
| `normalize_window_acts()` | 110 | 31 lines |
| `hum_rank()` | 155 | 29 lines |
| `participant_label()` | 368 | 23 lines |
| `fragment_phrase()` | 295 | 22 lines |

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
| `normalize_creature()` | 103 | 92 lines |
| `creature_neighbors()` | 236 | 32 lines |
| `normalize_spoor()` | 205 | 18 lines |
| `prey_capability()` | 326 | 14 lines |
| `predator_capability()` | 312 | 12 lines |
| `is_active()` | 280 | 11 lines |
| `room_fits()` | 225 | 9 lines |
| `hunger_of()` | 293 | 9 lines |

### `world/charter_crowd.py`

| Function | Start | Size |
|---|---:|---:|
| `members_of()` | 121 | 32 lines |
| `member_noun()` | 184 | 26 lines |
| `crowd_for()` | 252 | 25 lines |
| `engaged_turn()` | 81 | 20 lines |
| `composition_of()` | 212 | 18 lines |
| `mood_of()` | 232 | 18 lines |
| `presented()` | 103 | 16 lines |
| `_role_noun()` | 155 | 9 lines |

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
| `ensure_supply_points()` | 172 | 48 lines |
| `advance_economy()` | 275 | 47 lines |
| `caravan_exchange()` | 375 | 47 lines |
| `quote()` | 240 | 27 lines |
| `_holdings()` | 46 | 26 lines |
| `take_stock()` | 349 | 24 lines |
| `trade()` | 324 | 23 lines |

### `world/charter_enrol.py`

| Function | Start | Size |
|---|---:|---:|
| `enrol_person()` | 298 | 102 lines |
| `households_charter_key()` | 167 | 30 lines |
| `posts_for_role()` | 83 | 28 lines |
| `_room_distances()` | 199 | 21 lines |
| `_add_body()` | 261 | 20 lines |
| `lodging_charter_for()` | 141 | 19 lines |
| `reconcile_surface()` | 241 | 18 lines |
| `depart_guests()` | 402 | 18 lines |

### `world/charter_feel.py`

| Function | Start | Size |
|---|---:|---:|
| `advance_feel()` | 289 | 96 lines |
| `appraise_window()` | 192 | 95 lines |
| `felt_handoff()` | 415 | 30 lines |
| `normalize_feel()` | 163 | 16 lines |
| `strain_of()` | 394 | 13 lines |
| `_served_by_body()` | 181 | 9 lines |
| `_negligible()` | 387 | 5 lines |
| `overloaded_bodies()` | 409 | 4 lines |

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
| `close_plan()` | 668 | 323 lines |
| `_spread_berths()` | 530 | 84 lines |
| `_ensure_shift_crews()` | 336 | 62 lines |
| `narrate_actual_history()` | 1155 | 58 lines |
| `ensure_required_rooms()` | 993 | 53 lines |
| `_scale_populations()` | 452 | 51 lines |
| `resident_service_chronicle()` | 1058 | 47 lines |
| `ground_history_output()` | 1107 | 46 lines |

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
| `integrate_featured_resident()` | 733 | 129 lines |
| `ground_recent_history()` | 532 | 122 lines |
| `_recent_life_context()` | 260 | 87 lines |
| `ground_personal_history()` | 452 | 78 lines |
| `resident_history_packet()` | 349 | 73 lines |
| `featured_resident_private_habits()` | 148 | 47 lines |
| `_record_shared_recent_history()` | 656 | 40 lines |
| `featured_resident_seed()` | 112 | 34 lines |

### `world/charter_identity.py`

| Function | Start | Size |
|---|---:|---:|
| `materialize_body_names()` | 925 | 119 lines |
| `name_is_reserved()` | 556 | 65 lines |
| `refuse_harvested_material()` | 791 | 62 lines |
| `identity_aliases()` | 1125 | 38 lines |
| `_fill_empty_material()` | 752 | 37 lines |
| `_syllable_name()` | 154 | 36 lines |
| `reconstructs_a_reserved_name()` | 519 | 35 lines |
| `strip_reserved_pools()` | 855 | 34 lines |

### `world/charter_intervene.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_due()` | 177 | 157 lines |
| `_apply_relocate()` | 128 | 47 lines |
| `normalize_interventions()` | 82 | 29 lines |
| `normalize_mobilisation()` | 63 | 17 lines |
| `intervention_warnings()` | 113 | 5 lines |
| `watch_post_key()` | 120 | 2 lines |
| `watch_upkeep_key()` | 124 | 2 lines |

### `world/charter_log.py`

| Function | Start | Size |
|---|---:|---:|
| `scene_ledger()` | 275 | 217 lines |
| `life_of()` | 135 | 89 lines |
| `summarize()` | 63 | 70 lines |
| `own_state_of()` | 237 | 36 lines |
| `chronicle()` | 494 | 17 lines |
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
| `normalize_charter()` | 376 | 351 lines |
| `normalize_body()` | 182 | 123 lines |
| `body_of_an_authored_mind()` | 307 | 45 lines |
| `normalize_post()` | 144 | 36 lines |
| `normalize_upkeep()` | 111 | 31 lines |
| `_tags()` | 72 | 15 lines |
| `_string_list()` | 94 | 15 lines |
| `_optional_float()` | 366 | 8 lines |

### `world/charter_move.py`

| Function | Start | Size |
|---|---:|---:|
| `errands()` | 265 | 78 lines |
| `_advance()` | 143 | 44 lines |
| `walk()` | 345 | 30 lines |
| `_dispatch()` | 114 | 27 lines |
| `continue_walks()` | 189 | 27 lines |
| `_nearest()` | 240 | 23 lines |
| `_roll()` | 80 | 21 lines |
| `relocate()` | 218 | 20 lines |

### `world/charter_needs.py`

| Function | Start | Size |
|---|---:|---:|
| `advance_needs()` | 101 | 64 lines |
| `mood()` | 223 | 35 lines |
| `body_state()` | 266 | 32 lines |
| `pressure()` | 181 | 24 lines |
| `normalize_need()` | 73 | 16 lines |
| `unmet()` | 207 | 14 lines |
| `able()` | 167 | 12 lines |
| `seed_needs()` | 91 | 8 lines |

### `world/charter_news.py`

| Function | Start | Size |
|---|---:|---:|
| `check_reports()` | 360 | 92 lines |
| `claim_from_report()` | 179 | 44 lines |
| `report_from_claim()` | 225 | 38 lines |
| `_native_news_phrase()` | 265 | 30 lines |
| `decay_news()` | 454 | 26 lines |
| `news_claim()` | 310 | 24 lines |
| `charter_hours_of()` | 141 | 23 lines |
| `witness()` | 336 | 22 lines |

### `world/charter_observe.py`

| Function | Start | Size |
|---|---:|---:|
| `plan_public_evidence()` | 352 | 108 lines |
| `resolve_target_body()` | 273 | 77 lines |
| `apply_public_evidence()` | 462 | 74 lines |
| `evidence_claim()` | 127 | 40 lines |
| `_bodies_by_role()` | 238 | 33 lines |
| `_post_forms()` | 204 | 32 lines |
| `body_receives_evidence()` | 69 | 29 lines |
| `evidence_phrase()` | 104 | 21 lines |

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
| `opportunities()` | 908 | 123 lines |
| `enact()` | 1078 | 94 lines |
| `_afford_accuse()` | 654 | 70 lines |
| `_afford_ask()` | 516 | 65 lines |
| `_between()` | 331 | 50 lines |
| `offers()` | 1033 | 43 lines |
| `entanglement()` | 437 | 40 lines |
| `_afford_tell()` | 583 | 39 lines |

### `world/charter_predation.py`

| Function | Start | Size |
|---|---:|---:|
| `_attack()` | 251 | 118 lines |
| `_tribute()` | 504 | 95 lines |
| `predation_round()` | 371 | 67 lines |
| `run_registry()` | 647 | 60 lines |
| `read_spoor()` | 452 | 48 lines |
| `hunt_moves()` | 201 | 35 lines |
| `_company()` | 97 | 29 lines |
| `_prey_here()` | 177 | 22 lines |

### `world/charter_promote.py`

| Function | Start | Size |
|---|---:|---:|
| `remembered()` | 111 | 260 lines |
| `inherited_place_graph()` | 506 | 99 lines |
| `acquainted()` | 406 | 65 lines |
| `promotion_handoff()` | 373 | 23 lines |
| `private_rooms()` | 482 | 22 lines |
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
| `step()` | 425 | 972 lines |
| `_record_coarse_experiences()` | 242 | 160 lines |
| `run()` | 1399 | 66 lines |
| `_remember_experience()` | 154 | 32 lines |
| `_run_private_habits()` | 211 | 29 lines |
| `_social_events()` | 109 | 25 lines |
| `_record_social_experiences()` | 188 | 21 lines |
| `_settle_commitments()` | 404 | 19 lines |

### `world/charter_runtime.py`

| Function | Start | Size |
|---|---:|---:|
| `registry_warnings()` | 1697 | 182 lines |
| `_prepare_cast_histories()` | 559 | 172 lines |
| `_plan_lived_location()` | 1293 | 168 lines |
| `advance_snapshot()` | 2003 | 153 lines |
| `_generate_lived_location()` | 1521 | 122 lines |
| `presence_view()` | 3100 | 114 lines |
| `presim_registry()` | 875 | 104 lines |
| `generation_lore()` | 981 | 101 lines |

### `world/charter_social.py`

| Function | Start | Size |
|---|---:|---:|
| `update_ties()` | 608 | 78 lines |
| `normalize_ties()` | 545 | 61 lines |
| `update_judgments_from_minds()` | 311 | 56 lines |
| `derive_tie()` | 473 | 40 lines |
| `normalize_judgments()` | 257 | 35 lines |
| `_quantities()` | 423 | 29 lines |
| `tie_view()` | 705 | 29 lines |
| `_room()` | 203 | 23 lines |

### `world/charter_space.py`

| Function | Start | Size |
|---|---:|---:|
| `commons_places()` | 126 | 32 lines |
| `reach_map()` | 87 | 29 lines |
| `walk_route()` | 46 | 20 lines |
| `refresh_reach()` | 68 | 17 lines |
| `travel_rooms()` | 31 | 13 lines |
| `frequented_places()` | 160 | 8 lines |
| `charter_places()` | 118 | 6 lines |

### `world/charter_surface.py`

| Function | Start | Size |
|---|---:|---:|
| `surface_label()` | 209 | 39 lines |
| `settle_render()` | 310 | 32 lines |
| `deal_surface()` | 136 | 28 lines |
| `appearance_text()` | 275 | 25 lines |
| `surface_words()` | 250 | 23 lines |
| `surface_of()` | 185 | 13 lines |
| `_strings()` | 74 | 11 lines |
| `_home_post()` | 173 | 10 lines |

### `world/charter_surgery.py`

| Function | Start | Size |
|---|---:|---:|
| `plant_claim()` | 141 | 33 lines |
| `adjust_stock()` | 176 | 25 lines |
| `open_summons()` | 289 | 25 lines |
| `send_errand()` | 243 | 24 lines |
| `assign_post()` | 114 | 21 lines |
| `charter_shock()` | 221 | 20 lines |
| `harm_body()` | 269 | 18 lines |
| `apply_surgery()` | 325 | 17 lines |

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
| `apply_ops()` | 350 | 180 lines |
| `talk_view()` | 703 | 44 lines |
| `emerge()` | 532 | 38 lines |
| `drift()` | 184 | 35 lines |
| `advance_crowds()` | 603 | 32 lines |
| `normalize_band()` | 98 | 29 lines |
| `absorb()` | 572 | 29 lines |
| `describe()` | 648 | 21 lines |

### `world/day_cycle.py`

| Function | Start | Size |
|---|---:|---:|
| `clock_anchor()` | 261 | 33 lines |
| `label_phase()` | 214 | 21 lines |
| `charter_phase()` | 315 | 21 lines |
| `charter_hour()` | 338 | 14 lines |
| `clock_reading_hour()` | 199 | 13 lines |
| `describe()` | 296 | 13 lines |
| `label_hour()` | 237 | 12 lines |
| `day_length_hours()` | 129 | 11 lines |

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
| `mint_consequences()` | 339 | 100 lines |
| `record_obligations()` | 492 | 53 lines |
| `living_world_levels()` | 275 | 33 lines |
| `fired_consequences_at()` | 441 | 31 lines |
| `effective_depth()` | 232 | 27 lines |
| `owed_history()` | 547 | 24 lines |
| `attach_owed_history()` | 573 | 24 lines |
| `normalize_living_world()` | 193 | 20 lines |

### `world/mechanics.py`

| Function | Start | Size |
|---|---:|---:|
| `_tick_conditions()` | 746 | 112 lines |
| `read_time_diff()` | 172 | 110 lines |
| `_fire_due_events()` | 468 | 96 lines |
| `mechanics_sweep()` | 872 | 59 lines |
| `_schedule_new_arrivals()` | 566 | 44 lines |
| `time_diff_claims()` | 310 | 31 lines |
| `beat_end_elapsed()` | 343 | 31 lines |
| `_tick_spec()` | 691 | 28 lines |

### `world/offscreen.py`

| Function | Start | Size |
|---|---:|---:|
| `land_agent_tick()` | 1932 | 187 lines |
| `apply_plan_ops()` | 731 | 120 lines |
| `schedule_agent_ticks()` | 2121 | 118 lines |
| `schedule_profile_ticks()` | 1421 | 112 lines |
| `agent_context()` | 1599 | 109 lines |
| `advance_epoch()` | 986 | 98 lines |
| `advance_reactive_plans()` | 899 | 85 lines |
| `profile_summary_record()` | 1167 | 85 lines |

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

### `world/planned_entities.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_plan()` | 79 | 42 lines |
| `settle_rendered_plans()` | 228 | 41 lines |
| `plan_figure()` | 156 | 33 lines |
| `_contradicted_axis()` | 271 | 20 lines |
| `plans_in_view()` | 191 | 17 lines |
| `add_planned_entity()` | 138 | 16 lines |
| `reserved_plans()` | 210 | 16 lines |
| `plan_uid()` | 64 | 6 lines |

### `world/planning_needs.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_need()` | 115 | 57 lines |
| `file_planning_need()` | 229 | 25 lines |
| `drain_planning_needs()` | 303 | 25 lines |
| `planning_need()` | 174 | 17 lines |
| `schedule_planning_needs()` | 330 | 17 lines |
| `record_planning_needs()` | 256 | 16 lines |
| `fill_planning_need()` | 274 | 14 lines |
| `normalize_planning_needs()` | 193 | 12 lines |

### `world/region_events.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_wave()` | 274 | 137 lines |
| `normalize_region_event()` | 75 | 67 lines |
| `resolve_footprint()` | 166 | 46 lines |
| `plan_waves()` | 218 | 37 lines |
| `_graph()` | 154 | 10 lines |
| `_decay_steps()` | 257 | 6 lines |
| `harms_a_body()` | 144 | 4 lines |
| `_number()` | 70 | 3 lines |

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
| `effective_adjacent()` | 599 | 68 lines |
| `normalize_barrier()` | 286 | 67 lines |
| `neighbor_map()` | 484 | 58 lines |
| `normalize_scene_barriers()` | 371 | 32 lines |
| `passage_direction()` | 544 | 28 lines |
| `_barrier_against_its_own_name()` | 416 | 27 lines |
| `unresolved_barrier_words()` | 355 | 15 lines |
| `edge_passable()` | 585 | 12 lines |

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
| `apply_contact_ops()` | 1278 | 422 lines |
| `_clean_contact()` | 884 | 153 lines |
| `contacts_across_enclosure()` | 1079 | 68 lines |
| `normalize_scene_contacts()` | 1187 | 63 lines |
| `_mirrored_displacements()` | 331 | 50 lines |
| `_unnamed_touch_between_bodies()` | 825 | 47 lines |
| `_endpoint_is_body()` | 572 | 44 lines |
| `contacts_broken_by_scale_change()` | 1039 | 38 lines |

### `world/spatial_containment.py`

| Function | Start | Size |
|---|---:|---:|
| `derive_inventory_placements()` | 1190 | 143 lines |
| `materialize_named_stations()` | 2391 | 135 lines |
| `advance_room_transits()` | 2528 | 130 lines |
| `replace_engine_minted_interiors()` | 1891 | 123 lines |
| `mint_transferred_objects()` | 1084 | 104 lines |
| `release_declared_departures()` | 2672 | 97 lines |
| `place_enclosed_bodies()` | 2016 | 95 lines |
| `derive_containment_from_contacts()` | 358 | 90 lines |

### `world/spatial_fov.py`

| Function | Start | Size |
|---|---:|---:|
| `body_visibility()` | 736 | 70 lines |
| `body_cell()` | 344 | 58 lines |
| `feature_visibility()` | 677 | 57 lines |
| `_place_anchors()` | 275 | 48 lines |
| `shadowcast()` | 467 | 47 lines |
| `sight_digest()` | 815 | 43 lines |
| `_line()` | 435 | 30 lines |
| `observer_field()` | 583 | 28 lines |

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
| `invalidate_transferred_pose_details()` | 1022 | 113 lines |
| `derive_scene_stations()` | 1369 | 104 lines |
| `spatial_digest()` | 143 | 89 lines |
| `egocentric_frame()` | 55 | 86 lines |
| `invalidate_moved_body_pose_details()` | 894 | 79 lines |
| `invalidate_contact_bound_poses()` | 1137 | 72 lines |
| `normalize_scene_poses()` | 799 | 64 lines |
| `effective_anchors()` | 299 | 57 lines |

### `world/spatial_identity.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_scene_subjects()` | 371 | 115 lines |
| `canonical_subject_map()` | 273 | 87 lines |
| `room_of()` | 33 | 77 lines |
| `_live_subject_spellings()` | 219 | 52 lines |
| `same_subject()` | 127 | 28 lines |
| `_entities_named()` | 157 | 22 lines |
| `_positions_lookup()` | 10 | 21 lines |
| `_ci_get()` | 112 | 13 lines |

### `world/spatial_light.py`

| Function | Start | Size |
|---|---:|---:|
| `source_light()` | 87 | 51 lines |
| `light_at()` | 151 | 42 lines |
| `room_light()` | 41 | 33 lines |
| `effective_light()` | 195 | 29 lines |
| `_light_radius()` | 144 | 5 lines |
| `normalize_light()` | 35 | 4 lines |
| `light_blocks_sight()` | 226 | 3 lines |
| `_brighter()` | 79 | 2 lines |

### `world/spatial_merge.py`

| Function | Start | Size |
|---|---:|---:|
| `merge_scene_with_diff()` | 1070 | 595 lines |
| `_expire_transient_entity_state()` | 404 | 116 lines |
| `_shield_minted_edges()` | 808 | 95 lines |
| `apply_following_ops()` | 991 | 77 lines |
| `connect_orphan_new_rooms()` | 905 | 68 lines |
| `_merge_room()` | 147 | 64 lines |
| `_shield_standing_bearings()` | 683 | 61 lines |
| `_shield_standing_passage()` | 746 | 60 lines |

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
| `contact_sensation()` | 149 | 161 lines |
| `contact_phrase()` | 58 | 89 lines |
| `spatial_facts()` | 312 | 86 lines |
| `_interior_label()` | 26 | 30 lines |

### `world/spatial_routing.py`

| Function | Start | Size |
|---|---:|---:|
| `sprint_reach()` | 706 | 170 lines |
| `visible_adjacent_rooms()` | 946 | 153 lines |
| `corridor_sightlines()` | 561 | 88 lines |
| `spatial_rel()` | 265 | 83 lines |
| `_onward_exits()` | 878 | 66 lines |
| `passable_route_next_step()` | 365 | 46 lines |
| `stamp_sight_direction()` | 177 | 45 lines |
| `mutual_one_way_window()` | 133 | 42 lines |

### `world/spatial_senses.py`

| Function | Start | Size |
|---|---:|---:|
| `hear_level()` | 745 | 138 lines |
| `spatial_rel_between()` | 466 | 71 lines |
| `sound_bearing()` | 1036 | 69 lines |
| `visual_level_between()` | 607 | 65 lines |
| `scent_level()` | 37 | 56 lines |
| `_clean_comms_channel()` | 158 | 53 lines |
| `_opening_view_cap()` | 553 | 52 lines |
| `can_perceive_onset()` | 347 | 39 lines |

### `world/spatial_substance.py`

| Function | Start | Size |
|---|---:|---:|
| `_resolved_substance_add()` | 273 | 141 lines |
| `speech_articulation_impediment()` | 95 | 101 lines |
| `apply_contact_action_ops()` | 997 | 90 lines |
| `apply_substance_ops()` | 668 | 71 lines |
| `_same_pool()` | 458 | 50 lines |
| `_stock_consumed_by()` | 540 | 48 lines |
| `_standing_substance_pools()` | 625 | 41 lines |
| `resolve_substance_ops()` | 416 | 40 lines |

### `world/spatial_transit.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_transit_dock_edges()` | 285 | 170 lines |
| `sync_entity_interior_rooms()` | 108 | 60 lines |
| `ambient_scope()` | 489 | 29 lines |
| `infer_body_enclosures()` | 197 | 27 lines |
| `_is_body_entity()` | 62 | 26 lines |
| `_interior_entry_room()` | 170 | 25 lines |
| `containment_chain()` | 469 | 19 lines |
| `_interior_rooms_of()` | 90 | 16 lines |

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
| `prepare_frontier_expansion()` | 545 | 111 lines |
| `mint_frontier()` | 133 | 64 lines |
| `planned_room_brief()` | 366 | 54 lines |
| `materialize_planned_fringe()` | 240 | 45 lines |
| `plant_structure()` | 199 | 39 lines |
| `structure_warnings()` | 678 | 37 lines |
| `protect_planned_edges()` | 455 | 33 lines |
| `planned_context()` | 510 | 33 lines |

### `world/subjects.py`

| Function | Start | Size |
|---|---:|---:|
| `_resolve_room()` | 276 | 47 lines |
| `resolve_subject()` | 433 | 45 lines |
| `_resolve_character()` | 194 | 32 lines |
| `_lore_matches()` | 329 | 29 lines |
| `_resolve_from_lore()` | 360 | 29 lines |
| `_presence_reason()` | 166 | 26 lines |
| `_registry_room_matches()` | 249 | 25 lines |
| `_cast_matches()` | 121 | 22 lines |

### `world/survival.py`

| Function | Start | Size |
|---|---:|---:|
| `tick_vitals()` | 237 | 61 lines |
| `is_sealed_in()` | 199 | 36 lines |
| `apply_vitals_diff()` | 300 | 30 lines |
| `seed_vitals()` | 146 | 23 lines |
| `vitals_facts()` | 332 | 23 lines |
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
| GET | `/` | `index()` | `web/app.py:534` |
| PUT | `/api/active_preset` | `set_active()` | `web/app.py:1890` |
| PUT | `/api/affect_habituation` | `set_affect_habituation()` | `web/app.py:2210` |
| PUT | `/api/agent_models` | `put_agent_models()` | `web/app.py:1478` |
| PUT | `/api/ambience` | `put_ambience()` | `web/app.py:1634` |
| GET | `/api/ambience/library` | `ambience_library()` | `web/app.py:6753` |
| GET | `/api/ambience/search` | `ambience_search()` | `web/app.py:6732` |
| PUT | `/api/attire_beneath` | `set_attire_beneath()` | `web/app.py:2229` |
| POST | `/api/auth/login` | `auth_login()` | `web/auth_routes.py:209` |
| POST | `/api/auth/logout` | `auth_logout()` | `web/auth_routes.py:275` |
| POST | `/api/auth/setup` | `auth_setup()` | `web/auth_routes.py:134` |
| GET | `/api/auth/status` | `auth_status()` | `web/auth_routes.py:124` |
| GET | `/api/auto_promote` | `get_auto_promote()` | `web/app.py:3999` |
| PUT | `/api/auto_promote` | `set_auto_promote()` | `web/app.py:4012` |
| PUT | `/api/backdrops` | `put_backdrops()` | `web/app.py:1624` |
| GET | `/api/bootstrap` | `bootstrap()` | `web/app.py:1358` |
| POST | `/api/characters` | `char_create()` | `web/app.py:2685` |
| POST | `/api/characters/generate` | `char_generate()` | `web/app.py:2662` |
| POST | `/api/characters/import` | `char_import()` | `web/app.py:2710` |
| DELETE | `/api/characters/{cid}` | `char_del()` | `web/app.py:2896` |
| PUT | `/api/characters/{cid}` | `char_edit()` | `web/app.py:2886` |
| GET | `/api/characters/{cid}/export` | `char_export()` | `web/app.py:2878` |
| POST | `/api/characters/{cid}/fill_appearance` | `char_fill_appearance()` | `web/app.py:2866` |
| POST | `/api/characters/{cid}/fill_interior` | `char_fill_interior()` | `web/app.py:2824` |
| POST | `/api/characters/{cid}/fill_psychology` | `char_fill_psychology()` | `web/app.py:2791` |
| POST | `/api/characters/{cid}/generate_greeting` | `char_generate_greeting()` | `web/app.py:2775` |
| POST | `/api/characters/{cid}/recover_greetings` | `char_recover_greetings()` | `web/app.py:2765` |
| POST | `/api/characters/{cid}/start` | `character_start_story()` | `web/app.py:2734` |
| POST | `/api/chats` | `chat_new()` | `web/app.py:3333` |
| POST | `/api/chats/import` | `import_chat()` | `persist/chat_archive.py:272` |
| DELETE | `/api/chats/{cid}` | `chat_del()` | `web/app.py:3579` |
| GET | `/api/chats/{cid}` | `chat_get()` | `web/app.py:3587` |
| PUT | `/api/chats/{cid}` | `chat_edit()` | `web/app.py:3431` |
| POST | `/api/chats/{cid}/abort` | `chat_abort()` | `web/app.py:5558` |
| GET | `/api/chats/{cid}/ambience/oneshot/{name}` | `ambience_oneshot()` | `web/app.py:6762` |
| DELETE | `/api/chats/{cid}/ambience/pin` | `ambience_pin_delete()` | `web/app.py:6810` |
| PUT | `/api/chats/{cid}/ambience/pin` | `ambience_pin_put()` | `web/app.py:6791` |
| GET | `/api/chats/{cid}/ambience/pins` | `ambience_pins_get()` | `web/app.py:6786` |
| GET | `/api/chats/{cid}/ambience/{signature}.audio` | `ambience_audio()` | `web/app.py:6716` |
| GET | `/api/chats/{cid}/attire` | `attire_get()` | `web/app.py:4738` |
| PUT | `/api/chats/{cid}/attire` | `attire_put()` | `web/app.py:4749` |
| GET | `/api/chats/{cid}/backdrop/{signature}.png` | `backdrop_image()` | `web/app.py:6556` |
| GET | `/api/chats/{cid}/background_config` | `bg_cfg_get()` | `web/app.py:5049` |
| PUT | `/api/chats/{cid}/background_config` | `bg_cfg_put()` | `web/app.py:5053` |
| POST | `/api/chats/{cid}/characters` | `chat_add_char()` | `web/app.py:3842` |
| DELETE | `/api/chats/{cid}/characters/{ch}` | `chat_del_char()` | `web/app.py:4291` |
| PUT | `/api/chats/{cid}/characters/{ch}/card` | `chat_char_card_put()` | `web/app.py:4301` |
| PUT | `/api/chats/{cid}/characters/{ch}/dialogue_color` | `dialogue_color_put()` | `web/app.py:4606` |
| POST | `/api/chats/{cid}/characters/{ch}/fill_interior` | `chat_char_fill_interior()` | `web/app.py:2835` |
| GET | `/api/chats/{cid}/characters/{ch}/memories` | `mem_list()` | `web/app.py:5298` |
| POST | `/api/chats/{cid}/characters/{ch}/memories` | `mem_add()` | `web/app.py:5445` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/backfill` | `mem_backfill()` | `web/app.py:5415` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/consolidate` | `mem_consolidate()` | `web/app.py:5400` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/coverage` | `mem_coverage()` | `web/app.py:5436` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/export` | `mem_export()` | `web/app.py:5344` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/import` | `mem_import()` | `web/app.py:5355` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/search` | `mem_search()` | `web/app.py:5319` |
| GET | `/api/chats/{cid}/characters/{ch}/memory-context` | `memory_context_preview()` | `web/app.py:5376` |
| PUT | `/api/chats/{cid}/characters/{ch}/position` | `chat_char_position_put()` | `web/app.py:4518` |
| GET | `/api/chats/{cid}/characters/{ch}/private_history` | `ph_get()` | `web/app.py:4587` |
| PUT | `/api/chats/{cid}/characters/{ch}/private_history` | `ph_put()` | `web/app.py:4597` |
| GET | `/api/chats/{cid}/characters/{ch}/relationships` | `relationships_get()` | `web/app.py:5389` |
| GET | `/api/chats/{cid}/charters` | `charters_get()` | `web/app.py:4940` |
| PUT | `/api/chats/{cid}/charters` | `charters_put()` | `web/app.py:4961` |
| GET | `/api/chats/{cid}/charters/diagnostics` | `charters_diagnostics()` | `web/app.py:4979` |
| POST | `/api/chats/{cid}/charters/generate` | `charters_generate()` | `web/app.py:4991` |
| DELETE | `/api/chats/{cid}/charters/job` | `charters_job_clear()` | `web/app.py:5032` |
| GET | `/api/chats/{cid}/charters/job` | `charters_job_get()` | `web/app.py:5013` |
| GET | `/api/chats/{cid}/debug` | `chat_debug_export()` | `web/app.py:1853` |
| GET | `/api/chats/{cid}/dialogue_config` | `dlg_get()` | `web/app.py:4788` |
| PUT | `/api/chats/{cid}/dialogue_config` | `dlg_put()` | `web/app.py:4805` |
| GET | `/api/chats/{cid}/dramatic_irony` | `get_dramatic_irony_feed()` | `web/app.py:3941` |
| GET | `/api/chats/{cid}/export` | `export_chat()` | `persist/chat_archive.py:266` |
| GET | `/api/chats/{cid}/fixed_points` | `fixed_points_list()` | `web/app.py:5244` |
| POST | `/api/chats/{cid}/fixed_points` | `fixed_points_create()` | `web/app.py:5254` |
| DELETE | `/api/chats/{cid}/fixed_points/{anchor_id}` | `fixed_points_delete()` | `web/app.py:5276` |
| GET | `/api/chats/{cid}/frames` | `frames_list()` | `web/app.py:5198` |
| POST | `/api/chats/{cid}/frames` | `frames_create()` | `web/app.py:5202` |
| GET | `/api/chats/{cid}/guest_invites` | `list_guest_invites()` | `web/app.py:4172` |
| POST | `/api/chats/{cid}/guest_invites` | `create_guest_invite()` | `web/app.py:4152` |
| DELETE | `/api/chats/{cid}/guest_invites/{gid}` | `revoke_guest_invite()` | `web/app.py:4176` |
| GET | `/api/chats/{cid}/language` | `chat_language_get()` | `web/app.py:3398` |
| PUT | `/api/chats/{cid}/language` | `chat_language_put()` | `web/app.py:3415` |
| GET | `/api/chats/{cid}/living_world` | `living_world_get()` | `web/app.py:4905` |
| PUT | `/api/chats/{cid}/living_world` | `living_world_put()` | `web/app.py:4928` |
| DELETE | `/api/chats/{cid}/lorebook` | `detach_lore()` | `web/app.py:3570` |
| POST | `/api/chats/{cid}/lorebook` | `bind_lore()` | `web/app.py:3544` |
| GET | `/api/chats/{cid}/lorebooks` | `chat_lorebooks_owned()` | `web/app.py:2313` |
| POST | `/api/chats/{cid}/lorebooks` | `attach_lore()` | `web/app.py:3462` |
| DELETE | `/api/chats/{cid}/lorebooks/{lid}` | `detach_book()` | `web/app.py:3529` |
| PUT | `/api/chats/{cid}/lorebooks/{lid}` | `set_book_enabled()` | `web/app.py:3493` |
| GET | `/api/chats/{cid}/naming_profile` | `naming_profile_get()` | `web/app.py:5079` |
| PUT | `/api/chats/{cid}/naming_profile` | `naming_profile_put()` | `web/app.py:5091` |
| GET | `/api/chats/{cid}/paradox_policy` | `paradox_policy_get()` | `web/app.py:5229` |
| PUT | `/api/chats/{cid}/paradox_policy` | `paradox_policy_put()` | `web/app.py:5233` |
| GET | `/api/chats/{cid}/persona_private_history` | `pph_get()` | `web/app.py:4669` |
| PUT | `/api/chats/{cid}/persona_private_history` | `pph_put()` | `web/app.py:4682` |
| GET | `/api/chats/{cid}/personas` | `chat_list_extra_personas()` | `web/app.py:4017` |
| POST | `/api/chats/{cid}/personas` | `chat_add_persona()` | `web/app.py:4062` |
| DELETE | `/api/chats/{cid}/personas/{pid}` | `chat_del_persona()` | `web/app.py:4088` |
| PUT | `/api/chats/{cid}/personas/{pid}/station` | `chat_persona_station()` | `web/app.py:4027` |
| GET | `/api/chats/{cid}/player_authority` | `player_authority_get()` | `web/app.py:5161` |
| PUT | `/api/chats/{cid}/player_authority` | `player_authority_put()` | `web/app.py:5176` |
| GET | `/api/chats/{cid}/player_view` | `player_view_get()` | `web/app.py:5138` |
| GET | `/api/chats/{cid}/positions` | `chat_positions_get()` | `web/app.py:4451` |
| GET | `/api/chats/{cid}/promises` | `get_promise_ledger()` | `web/app.py:3945` |
| GET | `/api/chats/{cid}/promotable` | `list_promotable_presences()` | `web/app.py:3937` |
| POST | `/api/chats/{cid}/promotions/confirm` | `confirm_promotion()` | `web/app.py:3966` |
| POST | `/api/chats/{cid}/promotions/draft` | `draft_promotion()` | `web/app.py:3949` |
| GET | `/api/chats/{cid}/room` | `room_thread()` | `web/room_routes.py:52` |
| POST | `/api/chats/{cid}/room/mandates/{uid}/revoke` | `room_revoke()` | `web/room_routes.py:108` |
| POST | `/api/chats/{cid}/room/messages` | `room_say()` | `web/room_routes.py:65` |
| POST | `/api/chats/{cid}/room/messages/stream` | `room_say_stream()` | `web/room_routes.py:78` |
| GET | `/api/chats/{cid}/room/status` | `room_status()` | `web/room_routes.py:117` |
| GET | `/api/chats/{cid}/story_view` | `story_view_get()` | `web/app.py:5104` |
| GET | `/api/chats/{cid}/style_guide` | `style_guide_get()` | `web/app.py:4771` |
| PUT | `/api/chats/{cid}/style_guide` | `style_guide_put()` | `web/app.py:4777` |
| GET | `/api/chats/{cid}/survival` | `survival_get()` | `web/app.py:4359` |
| PUT | `/api/chats/{cid}/survival` | `survival_put()` | `web/app.py:4364` |
| POST | `/api/chats/{cid}/turns` | `turn_new()` | `web/app.py:5498` |
| POST | `/api/chats/{cid}/turns/{idx}/player_input` | `submit_extra_player_input()` | `web/app.py:4102` |
| GET | `/api/chats/{cid}/viewers` | `viewers_get()` | `web/app.py:5153` |
| GET | `/api/chats/{cid}/vitals` | `chat_vitals_get()` | `web/app.py:4416` |
| GET | `/api/chats/{cid}/world` | `world_get()` | `web/app.py:4687` |
| PUT | `/api/chats/{cid}/world` | `world_put()` | `web/app.py:4697` |
| PUT | `/api/debug_capture` | `put_debug_capture()` | `web/app.py:1589` |
| GET | `/api/default_prompts` | `default_prompts()` | `web/app.py:1789` |
| PUT | `/api/director_fanout_mode` | `set_director_fanout_mode()` | `web/app.py:2186` |
| PUT | `/api/exemplars` | `put_exemplars()` | `web/app.py:1558` |
| GET | `/api/extensions` | `extensions_list()` | `web/app.py:1907` |
| POST | `/api/extensions/install` | `extension_install()` | `web/app.py:1929` |
| GET | `/api/extensions/ui.css` | `extensions_ui_css()` | `web/app.py:2107` |
| GET | `/api/extensions/ui.js` | `extensions_ui()` | `web/app.py:2098` |
| GET | `/api/extensions/updates` | `extension_updates()` | `web/app.py:1950` |
| DELETE | `/api/extensions/{eid}` | `extension_remove()` | `web/app.py:1971` |
| GET | `/api/extensions/{eid}/asset/{path:path}` | `extension_asset()` | `web/app.py:2162` |
| POST | `/api/extensions/{eid}/disable` | `extension_disable()` | `web/app.py:1979` |
| DELETE | `/api/extensions/{eid}/document` | `extension_document_delete()` | `web/app.py:2075` |
| GET | `/api/extensions/{eid}/document` | `extension_document_get()` | `web/app.py:2043` |
| PUT | `/api/extensions/{eid}/document` | `extension_document_put()` | `web/app.py:2055` |
| DELETE | `/api/extensions/{eid}/documents` | `extension_documents_delete()` | `web/app.py:2085` |
| GET | `/api/extensions/{eid}/documents` | `extension_documents_list()` | `web/app.py:2022` |
| GET | `/api/extensions/{eid}/documents/verify` | `extension_documents_verify()` | `web/app.py:2033` |
| POST | `/api/extensions/{eid}/enable` | `extension_enable()` | `web/app.py:1921` |
| GET | `/api/extensions/{eid}/state` | `extension_state()` | `web/app.py:1984` |
| GET | `/api/extensions/{eid}/ui.css` | `extension_ui_css_one()` | `web/app.py:2129` |
| GET | `/api/extensions/{eid}/ui.js` | `extension_ui_one()` | `web/app.py:2117` |
| POST | `/api/extensions/{eid}/update` | `extension_update()` | `web/app.py:1961` |
| POST | `/api/guest/input` | `guest_input()` | `web/app.py:4266` |
| GET | `/api/guest/state` | `guest_state()` | `web/app.py:4198` |
| PUT | `/api/image_model` | `put_image_model()` | `web/app.py:1536` |
| POST | `/api/join` | `join_with_code()` | `web/app.py:4182` |
| GET | `/api/language-packs` | `language_packs_get()` | `web/app.py:3351` |
| GET | `/api/language-packs/{language_id}/ui` | `language_pack_ui()` | `web/app.py:3372` |
| DELETE | `/api/lore_entries/{eid}` | `lore_entry_delete()` | `web/app.py:3308` |
| PUT | `/api/lore_entries/{eid}` | `lore_entry_edit()` | `web/app.py:3232` |
| DELETE | `/api/lore_entries/{eid}/overlay` | `lore_entry_overlay_clear()` | `web/app.py:3320` |
| DELETE | `/api/lore_gen_jobs/{job_id}` | `lorebook_generate_discard()` | `web/app.py:2469` |
| POST | `/api/lore_gen_jobs/{job_id}/resume` | `lorebook_generate_resume()` | `web/app.py:2451` |
| DELETE | `/api/lorebook_links/{link_id}` | `lorebook_link_delete()` | `web/app.py:2409` |
| PUT | `/api/lorebook_links/{link_id}` | `lorebook_link_update()` | `web/app.py:2395` |
| POST | `/api/lorebooks` | `lore_create()` | `web/app.py:3007` |
| POST | `/api/lorebooks/import` | `lore_import()` | `web/app.py:2505` |
| DELETE | `/api/lorebooks/{lid}` | `lore_delete()` | `web/app.py:3099` |
| GET | `/api/lorebooks/{lid}` | `lore_get()` | `web/app.py:2983` |
| PUT | `/api/lorebooks/{lid}` | `lore_edit()` | `web/app.py:3029` |
| POST | `/api/lorebooks/{lid}/apply_plan` | `lorebook_apply_plan()` | `web/app.py:2478` |
| POST | `/api/lorebooks/{lid}/entries` | `lore_entry_create()` | `web/app.py:3149` |
| GET | `/api/lorebooks/{lid}/export` | `lore_export()` | `web/app.py:3105` |
| POST | `/api/lorebooks/{lid}/generate` | `lore_generate()` | `web/app.py:3135` |
| GET | `/api/lorebooks/{lid}/generate_job` | `lorebook_generate_job()` | `web/app.py:2440` |
| POST | `/api/lorebooks/{lid}/generate_plan` | `lorebook_generate_plan()` | `web/app.py:2414` |
| GET | `/api/lorebooks/{lid}/links` | `lorebook_links_get()` | `web/app.py:2368` |
| POST | `/api/lorebooks/{lid}/links` | `lorebook_link_create()` | `web/app.py:2373` |
| POST | `/api/lorebooks/{lid}/move` | `lorebook_move()` | `web/app.py:2295` |
| POST | `/api/lorebooks/{lid}/reinterpret` | `lore_reinterpret_route()` | `web/app.py:3122` |
| POST | `/api/lorebooks/{lid}/reorder` | `lorebook_reorder()` | `web/app.py:2304` |
| GET | `/api/maintenance/checkpoints` | `maintenance_checkpoints()` | `web/app.py:2252` |
| POST | `/api/maintenance/checkpoints/compact` | `maintenance_compact()` | `web/app.py:2268` |
| PUT | `/api/max_output_tokens` | `put_max_output_tokens()` | `web/app.py:1756` |
| DELETE | `/api/memories/{mid}` | `mem_del()` | `web/app.py:5492` |
| PUT | `/api/memories/{mid}` | `mem_edit()` | `web/app.py:5471` |
| GET | `/api/memory/embeddings` | `memory_embeddings_status()` | `web/app.py:1509` |
| POST | `/api/memory/embeddings/rebuild` | `memory_embeddings_rebuild()` | `web/app.py:1524` |
| GET | `/api/nsfw` | `get_nsfw()` | `web/app.py:2177` |
| PUT | `/api/nsfw` | `set_nsfw()` | `web/app.py:2181` |
| GET | `/api/openrouter/endpoints` | `get_openrouter_endpoints()` | `web/app.py:1714` |
| PUT | `/api/openrouter_routing` | `put_openrouter_routing()` | `web/app.py:1700` |
| POST | `/api/personas` | `persona_create()` | `web/app.py:2925` |
| POST | `/api/personas/generate` | `persona_generate()` | `web/app.py:2903` |
| POST | `/api/personas/import` | `persona_import()` | `web/app.py:2945` |
| DELETE | `/api/personas/{pid}` | `persona_del()` | `web/app.py:2977` |
| PUT | `/api/personas/{pid}` | `persona_edit()` | `web/app.py:2968` |
| GET | `/api/personas/{pid}/export` | `persona_export()` | `web/app.py:2959` |
| POST | `/api/personas/{pid}/fill_appearance` | `persona_fill_appearance()` | `web/app.py:2873` |
| PUT | `/api/prompt_presets` | `save_preset()` | `web/app.py:1800` |
| POST | `/api/prompt_presets/import` | `import_preset()` | `web/app.py:1867` |
| DELETE | `/api/prompt_presets/{name}` | `del_preset()` | `web/app.py:1881` |
| GET | `/api/prompt_presets/{name}/export` | `export_preset()` | `web/app.py:1827` |
| POST | `/api/providers` | `add_provider()` | `web/app.py:2561` |
| DELETE | `/api/providers/{pid}` | `del_provider()` | `web/app.py:2640` |
| PUT | `/api/providers/{pid}` | `put_provider()` | `web/app.py:2568` |
| GET | `/api/providers/{pid}/image_models` | `image_models()` | `web/app.py:2652` |
| GET | `/api/providers/{pid}/models` | `models()` | `web/app.py:2645` |
| PUT | `/api/providers/{pid}/prompt_cache` | `put_provider_prompt_cache()` | `web/app.py:2595` |
| PUT | `/api/reasoning_effort` | `put_reasoning_effort()` | `web/app.py:1726` |
| GET | `/api/research` | `get_research()` | `web/app.py:1675` |
| PUT | `/api/research` | `put_research()` | `web/app.py:1680` |
| POST | `/api/steps/{sid}/activate` | `step_activate()` | `web/app.py:6362` |
| POST | `/api/steps/{sid}/edit` | `step_edit()` | `web/app.py:6351` |
| POST | `/api/steps/{sid}/reroll` | `step_reroll()` | `web/app.py:6282` |
| DELETE | `/api/turns/{tid}` | `turn_del()` | `web/app.py:6376` |
| GET | `/api/turns/{tid}/ambience` | `turn_ambience()` | `web/app.py:6666` |
| POST | `/api/turns/{tid}/ambience` | `turn_ambience_resolve()` | `web/app.py:6683` |
| GET | `/api/turns/{tid}/backdrop` | `turn_backdrop()` | `web/app.py:6513` |
| POST | `/api/turns/{tid}/backdrop` | `turn_backdrop_generate()` | `web/app.py:6528` |
| POST | `/api/turns/{tid}/branch` | `turn_branch()` | `web/app.py:5562` |
| PUT | `/api/turns/{tid}/input` | `edit_input()` | `web/app.py:6014` |
| GET | `/api/turns/{tid}/narration` | `turn_narration_variants()` | `web/app.py:6099` |
| POST | `/api/turns/{tid}/narration` | `turn_narration_select()` | `web/app.py:6120` |
| GET | `/api/turns/{tid}/pipeline` | `pipeline_get()` | `web/app.py:6144` |
| PUT | `/api/turns/{tid}/prose` | `edit_prose()` | `web/app.py:6029` |
| POST | `/api/turns/{tid}/reroll` | `turn_reroll()` | `web/app.py:6213` |
| POST | `/api/turns/{tid}/rerun` | `turn_rerun()` | `web/app.py:6223` |
| POST | `/api/turns/{tid}/resume` | `turn_resume()` | `web/app.py:6250` |
| GET | `/api/turns/{turn_id}/debug` | `turn_debug_export()` | `web/app.py:1836` |
| GET | `/api/ui` | `ui_catalog_get()` | `web/app.py:3362` |
| PUT | `/api/ui-language` | `ui_language_put()` | `web/app.py:3387` |
| GET | `/api/updates/check` | `updates_check()` | `web/app.py:2244` |
| POST | `/api/updates/install` | `updates_install()` | `web/app.py:2248` |
| GET | `/guest` | `guest_page()` | `web/app.py:526` |
| GET | `/login` | `login_page()` | `web/app.py:544` |

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
| `turns` | `id`, `chat_id`, `idx`, `player_input`, `created`, `frame_id` |
| `steps` | `id`, `turn_id`, `key`, `label`, `ord`, `stale` |
| `variants` | `id`, `step_id`, `content`, `created`, `active`, `reasoning` |
| `llm_blobs` | `hash`, `bytes`, `body` |
| `llm_capture` | `id`, `turn_id`, `seq`, `step_key`, `role`, `requested`, `served`, `started`, `duration`, `ok`, `error`, `system_hash`, `payload_hashes`, `response_hash`, `reasoning_hash` |
| `memories` | `id`, `chat_id`, `char_id`, `turn_id`, `turn_idx`, `kind`, `category`, `provenance`, `salience`, `content`, `gist`, `key_phrases`, `entities`, `location`, `emotional_context`, `valence`, `arousal`, `--`, `--`, `--`, `encoding_valence`, `encoding_arousal`, `confidence`, `access_count`, `last_accessed`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `last_accessed_turn`, `embedding`, `cue_embedding`, `embedding_model`, `embedding_dim`, `archived`, `event_key`, `frame_id`, `--`, `--`, `--`, `--`, `importance`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `disputed`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `encoded_at_seconds` |
| `memory_vectors` | `vkey`, `embedding`, `cue_embedding`, `embedding_model`, `embedding_dim`, `created` |
| `memory_summaries` | `id`, `chat_id`, `char_id`, `scope`, `start_turn_idx`, `end_turn_idx`, `summary`, `key_phrases`, `unresolved_threads`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `support`, `embedding`, `embedding_model`, `embedding_dim`, `updated`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--` |
| `events` | `id`, `chat_id`, `turn_id`, `content` |
| `world` | `chat_id`, `key`, `value` |
| `checkpoints` | `id`, `chat_id`, `turn_idx`, `blob`, `created` |
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

### `static/js/ambience.js` (1049 lines)

Sections: Room ambience (`:2`); seamless looping (`:214`); one-shots (`:689`); the ambience panel (`:738`); the mix (`:756`).

Declared functions: `ambienceStored()`, `ambienceElement()`, `entryAudios()`, `ambiencePlayers()`, `applyAmbienceMute()`, `setAmbienceVolume()`, `ambienceLevel()`, `setLayerGain()`, `toggleAmbienceMute()`, `ambienceFadeMix()`, `armSeamlessLoop()`, `crossLoop()`, `retireEntries()`, `stopAmbience()`, `playAmbience()`, `armAmbienceUnlock()`, `ambienceWorking()`, `awaitAmbience()`, `resolveAmbience()`, `ambienceForTurn()`, `rerollAmbience()`, `ambienceOnVisibleTurn()`, `ambienceResetForRender()`, `updateAmbienceBtn()`, `playAmbienceOneshot()`, `ambienceCandidateRow()`, `ambienceLayerRow()`, `ambienceMixPanel()`, `openAmbiencePanel()`, `toggleAmbience()`, `syncAmbience()`.

### `static/js/app.js` (1237 lines)

Sections: Boot & sidebar (`:1`); and then nothing showed the report, so a host who installed a pack got (`:18`); New chat wizard (`:267`); NSFW (`:922`); Composer (`:950`); Init (`:1028`); Embedding reconciler progress (`:1088`).

Declared functions: `boot()`, `renderSide()`, `syncExtensionTabs()`, `renderChatSidebar()`, `newChatWizard()`, `renderWizardChoice()`, `storyLanguagePacks()`, `defaultStoryLanguage()`, `wizardState()`, `wizardHistoryCharacters()`, `discardFailedStorySetup()`, `wizardFromScratch()`, `renderWizardPersona()`, `renderWizardCharacters()`, `renderWizardScenario()`, `runWizard()`, `renderCharacterSidebar()`, `renderPersonaSidebar()`, `renderLegacyLoreSidebar()`, `updateNSFWBtn()`, `toggleNSFW()`, `resizeComposer()`, `erCard()`, `erDismiss()`, `erPoll()`, `erWatch()`, `erOfferRebuild()`.

### `static/js/backdrops.js` (430 lines)

Sections: Scene backdrops (`:2`).

Declared functions: `backdropLayers()`, `backdropLuminance()`, `applyBackdropContrast()`, `releaseBackdropLayer()`, `clearBackdrop()`, `showBackdrop()`, `backdropWorking()`, `awaitBackdrop()`, `generateBackdrop()`, `backdropForTurn()`, `backdropOnVisibleTurn()`, `backdropResetForRender()`, `updateBackdropBtn()`, `toggleBackdrops()`, `syncBackdrops()`.

### `static/js/chat.js` (2978 lines)

Sections: The turn being read (`:1`); Colouring who spoke (`:172`); `dialogue_log` is committed per turn and arrives as `turn.speech` -- and (`:175`); Flipping between rerolls of the newest beat (`:977`); Pipeline drawer: reading a step through a lens (`:1291`); Pipeline drawer (`:1624`); Relationship viewer (`:2053`); Memory browser (`:2132`); Private history (`:2920`).

Declared functions: `observeVisibleTurn()`, `openChat()`, `foldTypography()`, `decodeProseEntities()`, `splitEmphasis()`, `appendEmphasized()`, `quoteBody()`, `quotedRegions()`, `speechSpans()`, `paintProse()`, `proseEl()`, `renderFrameBar()`, `switchFrame()`, `updateChatScopedButtons()`, `renderChat()`, `branchTurn()`, `editTurnInput()`, `editTurnProse()`, `liveReset()`, `friendlyPhase()`, `turnStatusStart()`, `turnStatusSet()`, `turnStatusStop()`, `_streamOn()`, `liveFlush()`, `liveAppend()`, `liveStep()`, `handleEvt()`, `showNarrationEarly()`, `clearNarrationEarly()`, `_mountRerollNav()`, `_paintRerollCount()`, `showRerollVariant()`, `abortActiveRun()`, `runStream()`, `confirmCheckpointRestore()`, `runReroll()`, `rerollTurn()`, `exportChat()`, `importChatModal()`, `perceiverViews()`, `loopMindIds()`, `specialistIds()`, `stepLenses()`, `perceiverLabel()`, `facetBadge()`, `lensLabel()`, `renderLensBar()`, `lensSlice()`, `specialistSlice()`, `perceiverSlice()`, `mindSlice()`, `keySlice()`, `renderEngineNotes()`, `openPipeline()`, `relMeter()`, `relationshipModal()`, `memModal()`, `exportCharacterMemories()`, `importCharacterMemoriesModal()`, `memQS()`, `memCharId()`, `loadMemoryBrowse()`, `getMemUI()`, `renderMemorySummary()`, `sortedMems()`, `renderMemoryList()`, `memoryCard()`, `fieldWrap()`, `reloadMemView()`, `runMemorySearch()`, `showNewMemoryForm()`, `checkMemoryCoverage()`, `backfillMemoryEras()`, `consolidateMemories()`, `previewMemoryContext()`, `chatPH()`, `personaPH()`.

### `static/js/chime.js` (179 lines)

Sections: Turn-completion chime (`:2`); Which other waits are worth a chime (`:110`).

Declared functions: `chimeContext()`, `chimeArm()`, `chimePlay()`, `chimeWatches()`, `chimeWorkFinished()`, `chimeSetMuted()`, `toggleChimeMute()`, `updateChimeBtn()`.

### `static/js/components.js` (1254 lines)

Sections: Modal (`:38`); Book covers (`:54`); confirm()/prompt() replacements (`:167`); Toasts (`:500`); Background tasks (`:528`); Form helpers (`:614`); Model picker (`:1104`); made for every combobox that already has a provider saved -- opened its (`:1134`).

Declared functions: `txt()`, `el()`, `coverOfRow()`, `coverOfTitle()`, `modal()`, `modalOwnership()`, `closeModal()`, `closeAllModals()`, `_confirmOverlay()`, `confirmModal()`, `promptModal()`, `promptModalWithToggle()`, `livedLocationControl()`, `attachStoryLorebook()`, `generateStoryLocation()`, `openLivedLocationDialog()`, `toastHost()`, `toast()`, `renderActivity()`, `elapsedLabel()`, `activityTicking()`, `backgroundTask()`, `buttonTask()`, `loadingBlock()`, `emptyState()`, `fText()`, `fArea()`, `fSelect()`, `fNum()`, `fLineList()`, `fStrList()`, `fCoveragePicker()`, `fAttireGarments()`, `fList()`, `fAbilities()`, `fTraits()`, `fValues()`, `fBeliefs()`, `fCopingStrategies()`, `fAssociations()`, `fGoals()`, `fSenses()`, `fLatent()`, `fExtraParts()`, `fInteriorStations()`, `fPronouns()`, `phEditor()`, `fetchModels()`, `fetchImageModels()`, `modelCombobox()`, `emitChange()`, `load()`, `showDD()`.

### `static/js/editors.js` (1031 lines)

Sections: how many stations, and how many of them are new -- rather than letting a (`:53`); Carrying the fields an editor has no widget for (`:129`); Background-character promotion (`:859`); Import (file upload) (`:913`); Generate (`:984`); Lorebook generate (`:1002`); Export (`:1019`).

Declared functions: `appearanceFillButton()`, `interiorFillButton()`, `defaultCharacterSheet()`, `carryUnpresentedFields()`, `greetingCarousel()`, `quickStartModal()`, `charEditor()`, `personaEditor()`, `promotionReviewModal()`, `promoteBackgroundPresence()`, `importModal()`, `generateModal()`, `generateLoreModal()`, `exportCharacter()`, `exportPersona()`, `exportLorebook()`.

### `static/js/extensions.js` (657 lines)

Sections: Extension host (`:2`); Registration attribution (`:20`); Failure containment (`:56`); ES module entries (`:86`); Registration surface (`:177`); Notices (`:222`); Host services (`:368`); The chat lifecycle, as a declared contract (`:397`); Host-internal accessors (`:479`); Hot load / unload (`:605`).

### `static/js/i18n.js` (114 lines)

Declared functions: `translate()`, `apply()`.

### `static/js/lorebooks.js` (3775 lines)

Sections: Library sidebar (`:252`); Data loading (`:459`); Workspace (`:569`); Book metadata and tree operations (`:1175`); Entry editor (`:1679`); Lorebook relationships (`:2497`); Advanced generator (`:2948`); Interrupted-generation recovery (`:3168`).

Declared functions: `loreBookTypeIcon()`, `loreLinkTypes()`, `normalizeLoreBook()`, `loreOwnershipKey()`, `loreBooksByParent()`, `loreBookMatches()`, `loreVisibleIds()`, `loreBookLabel()`, `parseStoredJSON()`, `loreField()`, `loreSelect()`, `loreBookOptions()`, `renderLoreLibrarySidebar()`, `renderNode()`, `loreStoryQuery()`, `loreBookIsLibrary()`, `loadLoreWorkspaceData()`, `collectLoreLinkTargets()`, `loreWorkspaceVisible()`, `renderLoreWorkspaceBody()`, `openLoreWorkspace()`, `renderLoreInspector()`, `selectTab()`, `buildLoreWorkspace()`, `renderWorkspaceTree()`, `renderNode()`, `renderTreeList()`, `renderLoreBookEditor()`, `moveLoreBook()`, `reorderLoreBook()`, `promoteLoreBook()`, `demoteLoreBook()`, `createSiblingLoreBook()`, `createLoreBookDialog()`, `refreshLoreUI()`, `renderLoreEntries()`, `renderList()`, `buildLoreEntryCard()`, `splitNumberList()`, `reinterpretLoreBook()`, `generateLoreEntriesPrompt()`, `buildDirectLoreRequest()`, `renderRelationshipOverview()`, `renderLoreRelationshipEditor()`, `renderRelationshipList()`, `showNewRelationshipForm()`, `renderLoreGenerator()`, `adoptGeneratorPlan()`, `generatorPlanMessage()`, `loreGenAgo()`, `refreshLoreGenRecovery()`, `normalizeGeneratorPlan()`, `renderLorePlanPreview()`, `renderOperations()`, `planStat()`, `renderAnalysisSection()`, `addPlanGroup()`, `stripPlanUIFields()`, `acceptedGeneratorPlan()`.

### `static/js/settings.js` (4126 lines)

Sections: Chat tool modals (`:1`); Condition tab (`:941`); Survival tracker (`:1001`); Character relocation (`:1313`); API connections (`:2046`); Software updates (host-only; git fast-forward from GitHub origin) (`:3355`); Legacy checkpoint conversion (host-only maintenance) (`:3387`); Prompts (`:3621`); and be able to load that pack's own sheets to edit, rather than (`:3632`); Extensions (`:3799`).

Declared functions: `frameQuery()`, `charterDiagnosticsPanel()`, `selectTab()`, `dialogueColorControl()`, `save()`, `renderCastTab()`, `renderConditionTab()`, `hydrateConditionTab()`, `vitalMeter()`, `syncVitalsGutterNow()`, `syncVitalsGutter()`, `hideVitalsHud()`, `vitalsBlock()`, `refreshVitalsHud()`, `clearVitalsHud()`, `hydrateCastLocations()`, `castRoomLabel()`, `castRoomSelect()`, `renderLorebooksTab()`, `renderBookNode()`, `renderMultiplayerTab()`, `renderFramesTab()`, `renderFramesListPanel()`, `renderPersonaStationingPanel()`, `renderParadoxPanel()`, `renderBackgroundPresencesPanel()`, `renderGuestInvitePanel()`, `renderInsightsTab()`, `renderDramaticIronyPanel()`, `renderPromiseLedgerPanel()`, `embeddingBankBlock()`, `modelRecommendationsBlock()`, `renderFirstRunProviderSetup()`, `preferredBackdropSize()`, `renderFullApiSettings()`, `propagateToFollowers()`, `renderUpdateChecking()`, `renderUpdateError()`, `checkpointCompactionBlock()`, `renderUpdateStatus()`, `runUpdateInstall()`, `renderUpdateDone()`, `openPromptsModal()`, `reopenPromptsIfRequested()`, `extensionTrustNote()`, `extensionCapabilitySummary()`, `extensionSettingsSections()`, `openExtensionsMenu()`.

### `static/js/theme-init.js` (181 lines)

Declared functions: `readStored()`, `writeStored()`, `normaliseTheme()`, `normaliseProseSize()`, `applyTheme()`, `applyProseSize()`, `normaliseEffects()`, `applyEffects()`, `syncPageHidden()`.

### `static/js/themes.js` (159 lines)

Declared functions: `themePreview()`, `openAppearanceSettings()`.

### `static/js/utils.js` (375 lines)

Sections: API (`:235`); Download (`:354`); Card authoring warnings (`:363`).

Declared functions: `t()`, `watchUILanguage()`, `localizeDocument()`, `memoryCategories()`, `memoryProvenance()`, `hasDefaultModel()`, `safeId()`, `splitCL()`, `numOr()`, `taggedError()`, `errorDetailText()`, `api()`, `streamPost()`, `downloadJSON()`, `showCardWarnings()`.

### `static/js/weather-fx.js` (548 lines)

Sections: Weather effects (`:2`); the tile (`:178`); the layers (`:251`); lifecycle (`:329`); lightning (`:387`); the exact cost this file exists to avoid. Rain has no wrapper and no (`:527`).

Declared functions: `weatherFxReduced()`, `weatherFxEffectsOff()`, `weatherFxSupported()`, `weatherFxHost()`, `weatherFxRandom()`, `weatherFxTile()`, `weatherFxReach()`, `weatherFxBuild()`, `weatherFxClearLayers()`, `weatherFxStop()`, `weatherFxVisible()`, `weatherFxApply()`, `weatherFxStormy()`, `weatherFxScheduleFlash()`, `weatherFxFlash()`, `weatherFxOpenSky()`, `weatherFxBolt()`, `weatherFxThunder()`, `weatherFxForTurn()`.

### `static/js/writers_room.js` (638 lines)

Sections: The Writers' Room panel (`:3`); bd-panel for this element alone. (`:20`); Named limits (`:33`); Shape: docked / floating / closed (`:143`); Loading (`:200`); Sending (`:265`); The stream (`:296`); Rendering (`:370`); Building the panel (`:514`); Boot (`:627`).

Declared functions: `roomCls()`, `roomStoreGet()`, `roomStoreSet()`, `roomRestorePrefs()`, `roomClampWidth()`, `roomClampOpacity()`, `roomClampGeometry()`, `roomApplyShape()`, `roomOpen()`, `roomSetMode()`, `roomKey()`, `roomFrameQuery()`, `roomLoad()`, `roomLoadEarlier()`, `roomStartWatch()`, `roomStopWatch()`, `roomSend()`, `roomStream()`, `roomEvent()`, `roomRevoke()`, `roomRender()`, `roomRenderStatus()`, `roomRenderMandates()`, `roomRenderThread()`, `roomLiveNode()`, `roomBuild()`, `roomWireDrag()`, `track()`.
