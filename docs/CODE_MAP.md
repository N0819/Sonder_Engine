# Generated Code Map

> Regenerate with `python tools/generate_code_map.py`. Do not hand-edit this file.

## Python modules

| Module | Lines | Purpose | Local dependencies |
|---|---:|---|---|
| `agents/__init__.py` | 100 | Backward-compatible facade for the role-specific agent package. | `agents.background`, `agents.character`, `agents.common`, `agents.director`, `agents.loops`, `agents.mapping`, `agents.narration`, `agents.perception`, `agents.runtime`, `agents.storage`, `story.scene` |
| `agents/background.py` | 2128 |  | `agents.common`, `core.db`, `llm.prompts`, `llm.schemas`, `persist.commit`, `story.character_schema`, `story.scene`, `world.background_claims`, `world.spatial` |
| `agents/character.py` | 4677 | Private character decision agent. | `agents.character_kernel`, `agents.common`, `agents.impossible_knowledge`, `core.db`, `core.frames`, `llm.prompts`, `llm.schemas`, `mind`, `mind.affect`, `mind.memory`, `mind.memory_judge`, `mind.psychology_runtime`, `mind.theory_of_mind`, `story`, `story.character_schema`, `story.scene`, `world.gaps`, `world.place_purpose`, `world.spatial`, `world.survival` |
| `agents/character_kernel.py` | 496 |  | — |
| `agents/common.py` | 11323 | Shared normalization, lore, delivery, and perception helpers. | `core.db`, `core.pipeline_context`, `llm.llm_quality`, `llm.prompts`, `llm.providers`, `llm.schemas`, `mind.memory`, `mind.theory_of_mind`, `persist.commit`, `story`, `story.character_schema`, `story.provenance_text`, `story.scene`, `world`, `world.spatial` |
| `agents/composer.py` | 5107 |  | `agents.common`, `core.pipeline_context`, `story.provenance_text`, `story.scene`, `world.spatial` |
| `agents/director.py` | 8290 | Scene establishment, player interpretation, and objective resolution. | `agents`, `agents.common`, `agents.director_contact`, `agents.director_evidence`, `agents.director_fanout`, `agents.director_floors`, `agents.director_lingua`, `agents.director_movement`, `agents.director_reconcile`, `agents.director_scopes`, `agents.director_views`, `core.db`, `llm`, `llm.prompts`, `llm.providers`, `llm.schemas`, `mind.memory`, `story`, `story.attire`, `story.character_schema`, `story.scene`, `world.causality`, `world.mechanics`, `world.paradox`, `world.spatial`, `world.survival` |
| `agents/director_contact.py` | 477 |  | `story.character_schema`, `world.spatial` |
| `agents/director_evidence.py` | 3711 |  | `agents.common`, `agents.director_lingua`, `agents.director_scopes`, `llm`, `story.character_schema`, `world.spatial` |
| `agents/director_fanout.py` | 1687 |  | `agents.common`, `agents.director_evidence`, `agents.director_scopes`, `core.db`, `story.character_schema`, `world.spatial`, `world.survival` |
| `agents/director_floors.py` | 2117 |  | `agents.common`, `agents.director_lingua`, `agents.director_movement`, `story.character_schema`, `story.scene`, `world.mechanics`, `world.spatial` |
| `agents/director_lingua.py` | 29 |  | — |
| `agents/director_movement.py` | 1839 |  | `agents.director_lingua`, `story.character_schema`, `world.mechanics`, `world.spatial` |
| `agents/director_prose.py` | 1019 |  | `agents.director_fanout`, `agents.director_scopes`, `core.db`, `llm`, `llm.prompts` |
| `agents/director_reconcile.py` | 610 |  | `agents.common`, `agents.director_evidence`, `agents.director_scopes`, `core.db`, `llm.schemas`, `story`, `world.spatial` |
| `agents/director_rooms.py` | 425 |  | — |
| `agents/director_scopes.py` | 1246 |  | `agents.director_lingua`, `agents.director_views`, `core.db`, `world.survival` |
| `agents/director_views.py` | 706 |  | `agents.common`, `story.character_schema`, `story.scene`, `world.background_claims` |
| `agents/dramaturge.py` | 348 |  | `core.db`, `core.logging_utils` |
| `agents/impossible_knowledge.py` | 232 |  | `agents.common`, `core.db`, `story.character_schema` |
| `agents/loops.py` | 1529 | Reaction loops, interaction rounds, and deterministic micro-perception. | `agents.character`, `agents.common`, `core.db`, `story.character_schema`, `story.scene`, `world.spatial` |
| `agents/mapping.py` | 665 | Lore routing, cached recall, and retrieval staging. | `agents.common`, `core.db`, `mind.memory`, `story.scene`, `world.spatial` |
| `agents/narration.py` | 2739 | Player-facing narration agent. | `agents`, `agents.common`, `core.db`, `llm.prompts`, `llm.schemas`, `story`, `story.character_schema`, `story.scene`, `world.spatial`, `world.weather` |
| `agents/offscreen_beat.py` | 333 |  | — |
| `agents/perception.py` | 7066 | Opening, action-onset, and outcome observer views. | `agents`, `agents.common`, `core.db`, `core.pipeline_context`, `mind`, `story`, `story.character_schema`, `story.scene`, `world.beat_ledger`, `world.scene_memo`, `world.spatial` |
| `agents/runtime.py` | 1768 | Pipeline plans, dispatch, streaming, cancellation, resume, and reruns. | `agents.background`, `agents.character`, `agents.common`, `agents.director`, `agents.loops`, `agents.mapping`, `agents.narration`, `agents.perception`, `agents.storage`, `core.db`, `core.pipeline_context`, `llm.providers`, `persist.checkpoints`, `persist.commit`, `story.character_schema`, `story.scene` |
| `agents/storage.py` | 103 | Step and active-variant persistence helpers. | `core.db`, `persist.steps` |
| `agents/story_planner.py` | 1747 |  | `core.db`, `core.logging_utils`, `story.room_calls` |
| `core/__init__.py` | 6 |  | — |
| `core/db.py` | 2911 | SQLite schema, migrations, connection management, transactions, and key/value world access. | `core.paths` |
| `core/frames.py` | 295 |  | `core.db` |
| `core/jobs.py` | 317 |  | `core.logging_utils` |
| `core/logging_utils.py` | 122 | Structured timing and observability helpers. | — |
| `core/outofband.py` | 392 |  | `core.logging_utils` |
| `core/paths.py` | 32 |  | — |
| `core/pipeline_context.py` | 535 | Typed mutable context passed through a turn pipeline. | `core.db` |
| `core/updates.py` | 399 |  | `core.paths` |
| `dressing/__init__.py` | 6 |  | — |
| `dressing/ambience.py` | 2103 |  | `core`, `core.db`, `core.paths`, `dressing.backdrops`, `world.weather` |
| `dressing/backdrops.py` | 1772 |  | `core`, `core.db`, `core.logging_utils`, `core.paths`, `persist.steps`, `world.day_cycle`, `world.spatial`, `world.weather` |
| `llm/__init__.py` | 6 |  | — |
| `llm/decisions.py` | 151 |  | `core.db` |
| `llm/llm_quality.py` | 1281 | Strict JSON parsing, schema validation, and model-assisted repair. | `core.pipeline_context`, `llm.prompts`, `llm.providers`, `llm.schemas` |
| `llm/prompt_cache.py` | 79 | Provider-specific prompt-cache helpers. | `llm.providers` |
| `llm/prompts.py` | 666 | Default system prompts and prompt preset access. | `core.db` |
| `llm/providers.py` | 4738 | Provider selection, retries, streaming, cancellation, model listing, and embeddings. | `core.db`, `core.logging_utils` |
| `llm/research_providers.py` | 247 |  | `core.db` |
| `llm/schemas.py` | 7677 | Pydantic output contracts and semantic validation for agent payloads. | — |
| `mind/__init__.py` | 6 |  | — |
| `mind/affect.py` | 2503 |  | `mind.theory_of_mind` |
| `mind/canon_provenance.py` | 398 |  | — |
| `mind/knowledge_circles.py` | 134 |  | `core.db` |
| `mind/memory.py` | 142 | Facade re-exporting every mind.memory_* name; holds no domain code of its own. | `core`, `core.db`, `core.logging_utils`, `llm.prompts`, `llm.providers`, `mind.memory_common`, `mind.memory_context`, `mind.memory_inference`, `mind.memory_lore_entries`, `mind.memory_lorebooks`, `mind.memory_read`, `mind.memory_relationships`, `mind.memory_retrieval`, `mind.memory_snapshot`, `mind.memory_summaries`, `mind.memory_time`, `mind.memory_vectors`, `mind.memory_write`, `mind.theory_of_mind` |
| `mind/memory_common.py` | 293 | Leaf helpers shared by every memory domain: vocabularies, blob/vector codecs, FTS query, cosine. | `core.db` |
| `mind/memory_context.py` | 720 | The character memory payload: where retrieval, summaries and active state become one context. | `core.db`, `llm.prompts`, `llm.providers`, `mind.memory_common`, `mind.memory_read`, `mind.memory_retrieval`, `mind.memory_summaries`, `mind.memory_time`, `mind.memory_write` |
| `mind/memory_inference.py` | 159 | Belief confidence at mint and at abandonment, and reconciliation across a mind's inferences. | `core.db`, `mind.memory_write`, `mind.theory_of_mind` |
| `mind/memory_judge.py` | 430 |  | `core.db`, `core.logging_utils`, `llm.prompts`, `llm.providers` |
| `mind/memory_lore_entries.py` | 867 | Lore entries: add/update/delete, embedding stamps and health, search_lore, per-character knowledge scoping. | `core.db`, `core.logging_utils`, `llm.providers`, `mind.memory_common`, `mind.memory_lorebooks`, `mind.memory_write` |
| `mind/memory_lorebooks.py` | 583 | The lorebook graph: hierarchy, links, inheritance modes, per-chat attachment and weights. | `core.db`, `core.logging_utils`, `mind.memory_common` |
| `mind/memory_read.py` | 440 | The one seam a mind reads its own memory through, and the host reads that deliberately cross characters. | `core`, `core.db`, `mind.memory_common`, `mind.memory_write` |
| `mind/memory_relationships.py` | 457 | The relationship graph: axis deltas from conduct and from inference, and the history behind them. | `core.db`, `mind.memory_common`, `mind.memory_write` |
| `mind/memory_retrieval.py` | 1242 | Hybrid retrieval: lexical and vector rankings fused by RRF, tilted by mood and importance, plus unbidden recall. | `core.db`, `core.logging_utils`, `llm.providers`, `mind.memory_common`, `mind.memory_read`, `mind.memory_write` |
| `mind/memory_snapshot.py` | 947 | Checkpoint and archive: vector addressing, the prepare/apply restore split, memory and lorebook dump/restore. | `core.db`, `core.logging_utils`, `llm.providers`, `mind.memory_common`, `mind.memory_lore_entries`, `mind.memory_summaries`, `mind.memory_write` |
| `mind/memory_summaries.py` | 765 | Autobiographical, hearsay and surmise summaries: search, support sets, windowed consolidation and backfill. | `core.db`, `llm.prompts`, `llm.providers`, `mind.memory_common`, `mind.memory_read`, `mind.memory_retrieval`, `mind.memory_write` |
| `mind/memory_time.py` | 332 |  | `core.db` |
| `mind/memory_vectors.py` | 789 | Rebuilding vectors after the embedding model changes: bank status, the rebuild, and its background run. | `core.db`, `core.logging_utils`, `llm.providers`, `mind.memory_common`, `mind.memory_retrieval`, `mind.memory_write` |
| `mind/memory_write.py` | 907 | How a memory becomes a row: normalisation, extraction, FTS mirror, the upsert, and the embedding-repair thread. | `core.db`, `core.logging_utils`, `llm.providers`, `mind.memory_common` |
| `mind/psychology_runtime.py` | 873 |  | — |
| `mind/theory_of_mind.py` | 740 |  | — |
| `persist/__init__.py` | 6 |  | — |
| `persist/chat_archive.py` | 1277 | Typed, atomic chat archive export/import service and HTTP routes. | `core.db`, `llm.schemas`, `mind.memory`, `persist.checkpoints`, `story.character_schema`, `story.room_conversation` |
| `persist/chat_delete.py` | 42 |  | `core.db` |
| `persist/checkpoints.py` | 1579 | Whole-chat snapshots and checkpoint restore orchestration. | `core.db`, `mind.memory` |
| `persist/commit.py` | 848 | Atomic commit orchestrator, per-turn lock, thin tail domains, and the facade re-exporting every commit_* name. | `core.db`, `core.frames`, `llm.prompts`, `llm.providers`, `mind`, `mind.memory`, `mind.theory_of_mind`, `persist.commit_attire`, `persist.commit_background`, `persist.commit_common`, `persist.commit_destruction`, `persist.commit_entities`, `persist.commit_ledgers`, `persist.commit_mapping`, `persist.commit_mechanics`, `persist.commit_memory`, `persist.commit_memory_write`, `persist.commit_place_graph`, `persist.commit_room_registry`, `persist.commit_scene_state`, `story`, `story.character_schema`, `story.scene`, `world.comfort`, `world.mechanics`, `world.paradox`, `world.spatial`, `world.spatial_frames`, `world.survival`, `world.weather` |
| `persist/commit_attire.py` | 1797 | The mutable clothing ledger: attire notes, shed/worn garment entities, the validated attire diff. | `persist.commit_common`, `story`, `story.attire`, `world.spatial` |
| `persist/commit_background.py` | 5223 | Background presences: tracking, identity folding, the reactor gate, promotion to cast. | `core.db`, `mind.memory`, `persist.commit_common`, `story.character_schema`, `story.scene`, `world.spatial`, `world.survival` |
| `persist/commit_common.py` | 713 | Leaf helpers shared across commit domains: scalar utilities, name/address roster, entity-id canonicalisation. | `core.db`, `mind.memory`, `story.character_schema`, `world.mechanics`, `world.spatial` |
| `persist/commit_destruction.py` | 414 | Single- and multi-book destruction cascades, retirement, and latency-gated news. | `core.db`, `mind.memory`, `persist.commit_common`, `world.mechanics`, `world.spatial`, `world.spatial_frames` |
| `persist/commit_entities.py` | 576 | world_entities projection of the scene commit, awareness gate, disguise supersession. | `core.db`, `persist.commit_common`, `story.character_schema`, `story.scene`, `world.spatial` |
| `persist/commit_ledgers.py` | 596 | Pending-obligation and world-pressure debt ledgers. | `core.db`, `core.pipeline_context`, `persist.commit_common` |
| `persist/commit_mapping.py` | 914 | Lore/book mapping commit: book ops, lore ops, canon fallback ops, offscreen-event normaliser. | `core.db`, `core.frames`, `mind.memory`, `persist.commit_common`, `story.character_schema`, `story.provenance_text`, `world.spatial` |
| `persist/commit_mechanics.py` | 469 | Transit/news sweeps, the world-event spine, information carriers, cast changes. | `core.db`, `persist.commit_common`, `persist.commit_scene_state`, `story.character_schema`, `story.scene`, `world.mechanics` |
| `persist/commit_memory.py` | 2103 | Pre-lock memory preparation: per-mind memories and the psychology deltas riding with them. | `core.db`, `mind`, `mind.memory`, `mind.theory_of_mind`, `persist.commit_background`, `persist.commit_common`, `persist.commit_place_graph`, `story.character_schema`, `world.charter`, `world.comfort`, `world.exposure`, `world.spatial`, `world.stimulation`, `world.survival` |
| `persist/commit_memory_write.py` | 354 | The durable memory write and its out-of-band consolidation twin. | `core.db`, `mind.memory`, `persist.commit_memory`, `story.character_schema`, `story.scene` |
| `persist/commit_place_graph.py` | 336 | Per-mind durable place graph and per-beat spatial experience. | `world.spatial` |
| `persist/commit_room_registry.py` | 581 | Room identity across frames: registry projection, mint dedup, renames, retirement, exit pruning. | `core.db`, `persist.commit_common`, `story.character_schema`, `world.spatial` |
| `persist/commit_scene_state.py` | 2843 | The prepared post-turn scene: pre-lock build, scene commit domain, book anchoring, ground advance. | `core.db`, `core.pipeline_context`, `mind.memory`, `persist.commit_attire`, `persist.commit_common`, `persist.commit_destruction`, `persist.commit_room_registry`, `story.character_schema`, `story.provenance_text`, `world.beat_ledger`, `world.mechanics`, `world.spatial`, `world.spatial_frames`, `world.weather` |
| `persist/llm_capture.py` | 455 |  | `core.db` |
| `persist/pipeline_trace.py` | 635 | Privacy-conscious export, validation, and offline replay of persisted pipeline history. | `core.db` |
| `persist/steps.py` | 150 |  | `core.db` |
| `story/__init__.py` | 6 |  | — |
| `story/artifacts.py` | 653 |  | `llm.prompts` |
| `story/attire.py` | 3624 |  | — |
| `story/authored_events.py` | 299 |  | `core.db` |
| `story/carriers.py` | 976 |  | `core.db`, `story.character_schema`, `story.scene`, `world`, `world.spatial` |
| `story/character_schema.py` | 2703 | Versioned character/persona defaults, normalization, accessors, and export payloads. | `llm.schemas`, `story` |
| `story/couriers.py` | 1170 |  | `story.carriers`, `world` |
| `story/dialogue_colors.py` | 268 |  | — |
| `story/greetings.py` | 1328 |  | `agents.runtime`, `core`, `core.db`, `core.logging_utils`, `llm.llm_quality`, `llm.prompts`, `mind.memory`, `mind.theory_of_mind`, `persist.steps`, `story.character_schema`, `story.importers`, `world.charter_runtime` |
| `story/history_routing.py` | 215 |  | — |
| `story/importers.py` | 3155 | Native and AI-assisted character, persona, and lorebook import/generation. | `core.db`, `core.logging_utils`, `llm.prompts`, `llm.providers`, `mind.memory`, `story.character_schema`, `story.scene` |
| `story/journey_history.py` | 481 |  | — |
| `story/location_design.py` | 439 |  | `core.db` |
| `story/lore_structure.py` | 248 |  | — |
| `story/mandates.py` | 600 |  | `core.db` |
| `story/naming.py` | 555 |  | `core.db`, `world.charter_identity` |
| `story/opening_plan.py` | 116 |  | `core.db` |
| `story/plot_packages.py` | 3794 |  | `world.spatial` |
| `story/prelude.py` | 188 |  | `core.db` |
| `story/provenance_text.py` | 132 |  | — |
| `story/room_bible.py` | 445 |  | `core.db` |
| `story/room_calls.py` | 241 |  | — |
| `story/room_citations.py` | 221 |  | — |
| `story/room_conversation.py` | 550 |  | `core.db` |
| `story/room_frontier.py` | 252 |  | `core.db` |
| `story/room_proposals.py` | 264 |  | `core.db` |
| `story/room_research.py` | 376 |  | `core.db` |
| `story/room_slice.py` | 556 |  | `story.attire` |
| `story/room_tools.py` | 1757 |  | `story.plot_packages`, `story.room_research`, `story.room_slice` |
| `story/scene.py` | 3035 | Scene/cast/persona helpers, recent events, dialogue configuration, and private knowledge. | `core.db`, `story`, `story.attire`, `story.character_schema`, `world.day_cycle`, `world.spatial` |
| `web/__init__.py` | 6 |  | — |
| `web/app.py` | 7861 | FastAPI application assembly, resource CRUD, turn control, and streaming endpoints. | `agents`, `agents.story_planner`, `core`, `core.db`, `core.frames`, `core.paths`, `dressing.ambience`, `dressing.backdrops`, `llm`, `llm.prompts`, `llm.providers`, `mind.memory`, `persist.chat_archive`, `persist.chat_delete`, `persist.checkpoints`, `persist.commit`, `persist.steps`, `story`, `story.character_schema`, `story.dialogue_colors`, `story.importers`, `story.prelude`, `story.scene`, `web`, `web.auth_routes`, `web.room_routes`, `web.world_routes`, `world`, `world.survival` |
| `web/auth_routes.py` | 279 | Typed host-authentication HTTP routes and cookie transport. | `web` |
| `web/guest_access.py` | 554 |  | `core.db` |
| `web/pipeline_views.py` | 42 |  | `agents.composer` |
| `web/room_routes.py` | 119 |  | `core.db`, `story` |
| `web/story_view.py` | 1029 |  | `core.db`, `persist.steps`, `world.charter_runtime`, `world.living_world` |
| `web/world_routes.py` | 2601 |  | `core`, `core.db`, `persist.commit`, `story`, `story.attire`, `story.character_schema`, `story.scene`, `world.charter`, `world.charter_runtime`, `world.spatial`, `world.weather` |
| `world/__init__.py` | 6 |  | — |
| `world/background_claims.py` | 598 |  | `core.db` |
| `world/beat_ledger.py` | 184 |  | — |
| `world/causal_completion.py` | 151 |  | — |
| `world/causal_program.py` | 387 |  | — |
| `world/causal_verification.py` | 705 |  | — |
| `world/causality.py` | 425 |  | `world.spatial` |
| `world/charter.py` | 524 |  | `world.charter_author`, `world.charter_chatter`, `world.charter_commitment`, `world.charter_decide`, `world.charter_drift`, `world.charter_economy`, `world.charter_feel`, `world.charter_figure`, `world.charter_identity`, `world.charter_intervene`, `world.charter_log`, `world.charter_mark`, `world.charter_mind`, `world.charter_model`, `world.charter_move`, `world.charter_needs`, `world.charter_news`, `world.charter_place`, `world.charter_plan`, `world.charter_politics`, `world.charter_practice`, `world.charter_promote`, `world.charter_roster`, `world.charter_run`, `world.charter_social`, `world.charter_space`, `world.charter_talk`, `world.charter_temper`, `world.charter_trigger` |
| `world/charter_author.py` | 813 |  | `world.charter_commitment`, `world.charter_economy`, `world.charter_figure`, `world.charter_mark`, `world.charter_mind`, `world.charter_model`, `world.charter_needs`, `world.charter_politics`, `world.charter_practice` |
| `world/charter_chatter.py` | 475 |  | `world.crowds` |
| `world/charter_commitment.py` | 292 |  | `world.charter_model` |
| `world/charter_creature.py` | 464 |  | `world.charter_harm`, `world.charter_model` |
| `world/charter_crowd.py` | 349 |  | `world.crowds` |
| `world/charter_decide.py` | 279 |  | `world.charter_model`, `world.charter_news` |
| `world/charter_drift.py` | 106 |  | `world.charter_model` |
| `world/charter_economy.py` | 444 |  | `world.charter_model` |
| `world/charter_enrol.py` | 431 |  | `world.charter_generate`, `world.charter_model`, `world.charter_needs`, `world.charter_roster`, `world.charter_surface` |
| `world/charter_feel.py` | 469 |  | `mind.psychology_runtime`, `world.charter_mark`, `world.charter_needs`, `world.charter_temper` |
| `world/charter_figure.py` | 140 |  | — |
| `world/charter_generate.py` | 1643 |  | `world.charter_identity`, `world.charter_model`, `world.charter_needs`, `world.charter_roster`, `world.charter_surface` |
| `world/charter_harm.py` | 264 |  | — |
| `world/charter_history.py` | 885 |  | — |
| `world/charter_identity.py` | 1199 |  | — |
| `world/charter_intervene.py` | 344 |  | `world.charter_model` |
| `world/charter_log.py` | 521 |  | `world.charter_commitment`, `world.charter_decide`, `world.charter_economy`, `world.charter_feel`, `world.charter_mark`, `world.charter_mind`, `world.charter_model`, `world.charter_needs`, `world.charter_news`, `world.charter_politics`, `world.charter_social`, `world.charter_temper` |
| `world/charter_mark.py` | 302 |  | — |
| `world/charter_mind.py` | 262 |  | — |
| `world/charter_model.py` | 927 |  | `world.charter_chatter`, `world.charter_figure`, `world.charter_harm`, `world.charter_mark` |
| `world/charter_move.py` | 667 |  | `world.charter_needs`, `world.charter_space` |
| `world/charter_needs.py` | 615 |  | `world.charter_model` |
| `world/charter_news.py` | 565 |  | `world.charter_mind`, `world.charter_model`, `world.charter_talk` |
| `world/charter_observe.py` | 645 |  | `world.charter_figure`, `world.charter_identity`, `world.charter_mind`, `world.spatial` |
| `world/charter_ops.py` | 384 |  | `world.charter_harm` |
| `world/charter_place.py` | 502 |  | `world.charter_identity`, `world.charter_model`, `world.charter_move`, `world.spatial` |
| `world/charter_plan.py` | 227 |  | `world.charter_drift`, `world.charter_model`, `world.charter_roster` |
| `world/charter_politics.py` | 161 |  | — |
| `world/charter_practice.py` | 1203 |  | `world.charter_commitment`, `world.charter_figure`, `world.charter_mind`, `world.charter_needs`, `world.charter_politics`, `world.charter_social`, `world.charter_talk` |
| `world/charter_predation.py` | 1063 |  | `world.charter_creature`, `world.charter_harm`, `world.charter_model`, `world.charter_move` |
| `world/charter_promote.py` | 612 |  | `world.charter_commitment`, `world.charter_feel`, `world.charter_politics`, `world.charter_social` |
| `world/charter_roster.py` | 134 |  | `world.charter_model` |
| `world/charter_run.py` | 1530 |  | `world`, `world.charter_commitment`, `world.charter_decide`, `world.charter_drift`, `world.charter_economy`, `world.charter_enrol`, `world.charter_feel`, `world.charter_figure`, `world.charter_harm`, `world.charter_intervene`, `world.charter_log`, `world.charter_mark`, `world.charter_mind`, `world.charter_model`, `world.charter_move`, `world.charter_needs`, `world.charter_news`, `world.charter_plan`, `world.charter_politics`, `world.charter_practice`, `world.charter_roster`, `world.charter_social`, `world.charter_space`, `world.charter_talk`, `world.charter_trigger` |
| `world/charter_runtime.py` | 5426 |  | `core`, `core.logging_utils`, `world.charter`, `world.charter_news`, `world.charter_surface`, `world.day_cycle`, `world.mechanics`, `world.spatial` |
| `world/charter_social.py` | 865 |  | `world.charter_politics` |
| `world/charter_space.py` | 337 |  | `world.spatial` |
| `world/charter_surface.py` | 364 |  | — |
| `world/charter_surgery.py` | 402 |  | — |
| `world/charter_talk.py` | 351 |  | `world.charter_mind`, `world.charter_politics`, `world.charter_roster` |
| `world/charter_temper.py` | 167 |  | — |
| `world/charter_trigger.py` | 881 |  | `world.charter_mark`, `world.charter_news`, `world.charter_practice` |
| `world/comfort.py` | 340 |  | `world.spatial` |
| `world/crowds.py` | 783 |  | `world.spatial` |
| `world/day_cycle.py` | 405 |  | — |
| `world/degradation.py` | 171 |  | — |
| `world/exposure.py` | 232 |  | `story`, `world.spatial`, `world.weather` |
| `world/gaps.py` | 459 |  | `core.db`, `mind.canon_provenance`, `world.spatial`, `world.subjects` |
| `world/living_world.py` | 639 |  | `core.logging_utils`, `world.mechanics` |
| `world/mechanics.py` | 1276 |  | `core`, `world.spatial`, `world.spatial_frames` |
| `world/offscreen.py` | 2305 |  | `core`, `core.logging_utils`, `llm.prompts` |
| `world/paradox.py` | 655 |  | `core.db`, `core.frames`, `story.character_schema`, `world.spatial` |
| `world/place_purpose.py` | 554 |  | `mind.theory_of_mind`, `world.comfort`, `world.spatial`, `world.survival` |
| `world/planned_entities.py` | 647 |  | `core.db` |
| `world/planning_needs.py` | 408 |  | — |
| `world/region_events.py` | 461 |  | — |
| `world/regions.py` | 586 |  | `world.spatial` |
| `world/routines.py` | 256 |  | `world.day_cycle` |
| `world/scene_memo.py` | 195 |  | — |
| `world/spatial.py` | 362 | Deterministic room, barrier, hearing, visibility, placement, and scene-diff logic. | `llm.schemas`, `world.spatial_barriers`, `world.spatial_contact_migration`, `world.spatial_contacts`, `world.spatial_containment`, `world.spatial_fov`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_levels`, `world.spatial_light`, `world.spatial_light_field`, `world.spatial_lint`, `world.spatial_merge`, `world.spatial_orientation`, `world.spatial_prose`, `world.spatial_routing`, `world.spatial_scent_field`, `world.spatial_senses`, `world.spatial_sound_field`, `world.spatial_substance`, `world.spatial_transit`, `world.spatial_walk` |
| `world/spatial_barriers.py` | 931 |  | `world.spatial_orientation` |
| `world/spatial_bubbles.py` | 526 |  | `world.spatial`, `world.spatial_frames` |
| `world/spatial_contact_migration.py` | 332 |  | `story.character_schema`, `world.spatial_contacts`, `world.spatial_identity` |
| `world/spatial_contacts.py` | 1948 |  | `world.spatial_containment`, `world.spatial_identity`, `world.spatial_transit` |
| `world/spatial_containment.py` | 3280 |  | `world.spatial_barriers`, `world.spatial_identity`, `world.spatial_transit` |
| `world/spatial_fov.py` | 1757 |  | `world.scene_memo`, `world.spatial_barriers`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_orientation` |
| `world/spatial_frames.py` | 2440 |  | `core.db`, `core.frames`, `story.character_schema`, `story.scene`, `world.paradox`, `world.spatial` |
| `world/spatial_geometry.py` | 2157 |  | `story.character_schema`, `world.scene_memo`, `world.spatial_barriers`, `world.spatial_contacts`, `world.spatial_containment`, `world.spatial_identity`, `world.spatial_orientation` |
| `world/spatial_identity.py` | 887 |  | — |
| `world/spatial_levels.py` | 244 |  | `world.spatial_orientation` |
| `world/spatial_light.py` | 508 |  | `world.spatial_barriers`, `world.spatial_geometry`, `world.spatial_identity` |
| `world/spatial_light_field.py` | 1246 |  | `world.scene_memo`, `world.spatial_barriers`, `world.spatial_containment`, `world.spatial_fov`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_light`, `world.spatial_orientation` |
| `world/spatial_lint.py` | 444 |  | `world.spatial_barriers`, `world.spatial_fov`, `world.spatial_geometry`, `world.spatial_orientation` |
| `world/spatial_merge.py` | 2601 |  | `llm.schemas`, `world.spatial_barriers`, `world.spatial_contact_migration`, `world.spatial_contacts`, `world.spatial_containment`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_levels`, `world.spatial_orientation`, `world.spatial_routing`, `world.spatial_senses`, `world.spatial_substance`, `world.spatial_transit` |
| `world/spatial_orientation.py` | 398 | Bearing math and reciprocal spatial-edge normalization. | — |
| `world/spatial_prose.py` | 404 |  | `world.spatial_contacts`, `world.spatial_containment`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_light` |
| `world/spatial_routing.py` | 1200 |  | `world.spatial_barriers`, `world.spatial_containment`, `world.spatial_geometry`, `world.spatial_light`, `world.spatial_orientation` |
| `world/spatial_scent_field.py` | 233 |  | `world.spatial_barriers` |
| `world/spatial_senses.py` | 1868 |  | `world.scene_memo`, `world.spatial_barriers`, `world.spatial_contacts`, `world.spatial_containment`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_light`, `world.spatial_orientation`, `world.spatial_routing` |
| `world/spatial_sound_field.py` | 3057 |  | `world.scene_memo`, `world.spatial_barriers`, `world.spatial_containment`, `world.spatial_fov`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_light_field`, `world.spatial_senses` |
| `world/spatial_substance.py` | 1128 |  | `world.spatial_contacts`, `world.spatial_identity` |
| `world/spatial_transit.py` | 670 |  | `world.spatial_barriers`, `world.spatial_identity` |
| `world/spatial_walk.py` | 411 |  | `world.spatial_fov`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_routing` |
| `world/stimulation.py` | 239 |  | `story`, `world.spatial` |
| `world/structure.py` | 1720 |  | `world.charter_model`, `world.regions`, `world.spatial` |
| `world/subjects.py` | 505 |  | `core.db`, `mind.canon_provenance`, `world.spatial` |
| `world/survival.py` | 489 |  | `core.db` |
| `world/weather.py` | 1411 |  | — |

## Largest top-level functions

### `agents/background.py`

| Function | Start | Size |
|---|---:|---:|
| `_react_one()` | 1924 | 205 lines |
| `_background_react()` | 448 | 182 lines |
| `scene_life()` | 1113 | 157 lines |
| `_demanded_presences()` | 900 | 144 lines |
| `_present_others()` | 1506 | 103 lines |
| `declare_charter_figures()` | 1765 | 102 lines |
| `_beat_for_presence()` | 194 | 84 lines |
| `managed_presences()` | 755 | 78 lines |

### `agents/character.py`

| Function | Start | Size |
|---|---:|---:|
| `character_step()` | 3443 | 1235 lines |
| `_annotate_known_exits()` | 2687 | 469 lines |
| `_ground_observation_citations()` | 1662 | 322 lines |
| `_unanswered_question_note()` | 561 | 237 lines |
| `_destination_from_goals()` | 2253 | 109 lines |
| `_recent_self_moves()` | 279 | 98 lines |
| `sprint_offers()` | 3191 | 97 lines |
| `_impossible_knowledge()` | 900 | 89 lines |

### `agents/character_kernel.py`

| Function | Start | Size |
|---|---:|---:|
| `_chosen_wants()` | 278 | 66 lines |
| `compact_character_evidence()` | 105 | 46 lines |
| `expand_character_evidence()` | 193 | 43 lines |
| `compile_character_kernel()` | 454 | 43 lines |
| `_compile_named_updates()` | 391 | 40 lines |
| `_rewrite_evidence_container()` | 153 | 38 lines |
| `bind_current_evidence_to_memory()` | 238 | 38 lines |
| `_compile_rows()` | 365 | 24 lines |

### `agents/common.py`

| Function | Start | Size |
|---|---:|---:|
| `norm_sequence()` | 4289 | 294 lines |
| `_check_narrator_fidelity()` | 10595 | 252 lines |
| `presence_figures_for_room()` | 2180 | 232 lines |
| `_unknown_actor_label()` | 5130 | 185 lines |
| `_scrub_invented_dialogue()` | 9108 | 151 lines |
| `observer_body_regions()` | 1698 | 140 lines |
| `_check_quote_attribution()` | 10158 | 139 lines |
| `_scrub_unknown_identities()` | 5538 | 133 lines |

### `agents/composer.py`

| Function | Start | Size |
|---|---:|---:|
| `_render_view_english()` | 4396 | 234 lines |
| `speech_percept()` | 3047 | 183 lines |
| `presence_percepts()` | 1252 | 181 lines |
| `pose_percepts()` | 2050 | 150 lines |
| `act_percept()` | 3300 | 122 lines |
| `line_hear_level()` | 642 | 108 lines |
| `_pose_referent()` | 1730 | 107 lines |
| `_render_presence_group()` | 3864 | 106 lines |

### `agents/director.py`

| Function | Start | Size |
|---|---:|---:|
| `director_resolve()` | 5683 | 2574 lines |
| `director_interpret()` | 1361 | 949 lines |
| `_run_specialists()` | 3503 | 640 lines |
| `_reconcile_resolution()` | 2734 | 558 lines |
| `director_establish()` | 394 | 200 lines |
| `_reconcile_interpretation()` | 2312 | 172 lines |
| `mint_unreferenced_things()` | 5359 | 169 lines |
| `_specialist_repairs()` | 2546 | 134 lines |

### `agents/director_contact.py`

| Function | Start | Size |
|---|---:|---:|
| `_validated_player_contact_assertions()` | 59 | 148 lines |
| `_merge_player_contact_assertions()` | 209 | 85 lines |
| `_character_material_effects()` | 355 | 52 lines |
| `_validated_character_contact_endings()` | 296 | 51 lines |
| `_merge_character_material_effects()` | 409 | 35 lines |
| `_merge_character_contact_endings()` | 446 | 32 lines |
| `_drop_momentary_contact_adds()` | 31 | 19 lines |
| `_canonical_scene_subject()` | 51 | 6 lines |

### `agents/director_evidence.py`

| Function | Start | Size |
|---|---:|---:|
| `_evidence_present()` | 2059 | 359 lines |
| `normalize_causal_ledger()` | 2634 | 264 lines |
| `causal_world_index()` | 2938 | 176 lines |
| `beat_event_ledger()` | 1272 | 123 lines |
| `beat_timeline()` | 1177 | 93 lines |
| `_fold_derived_manifest_events()` | 3623 | 89 lines |
| `_span_items()` | 3250 | 86 lines |
| `span_slices()` | 1907 | 85 lines |

### `agents/director_fanout.py`

| Function | Start | Size |
|---|---:|---:|
| `_specialist_payload()` | 805 | 489 lines |
| `_resolve_beat_view()` | 78 | 156 lines |
| `_orchestration_scope_backstop()` | 1533 | 155 lines |
| `_interpret_beat_view()` | 246 | 65 lines |
| `_resolved_event_verdicts()` | 1404 | 54 lines |
| `_specialist_span_slice()` | 331 | 47 lines |
| `_beat_rooms()` | 498 | 40 lines |
| `_grid_view()` | 457 | 39 lines |

### `agents/director_floors.py`

| Function | Start | Size |
|---|---:|---:|
| `_bind_minted_entities_to_present_figures()` | 1628 | 232 lines |
| `resolve_concealment_refs()` | 1911 | 104 lines |
| `_conditions_view()` | 596 | 103 lines |
| `_awareness_exits()` | 732 | 98 lines |
| `_release_attempts()` | 990 | 93 lines |
| `strip_addressee_concealment()` | 2037 | 81 lines |
| `_narrated_destruction_subjects()` | 1250 | 79 lines |
| `unplaced_mints_needing_a_room()` | 1409 | 72 lines |

### `agents/director_lingua.py`

| Function | Start | Size |
|---|---:|---:|
| `_ling()` | 16 | 14 lines |

### `agents/director_movement.py`

| Function | Start | Size |
|---|---:|---:|
| `_reconcile_near_group_positions()` | 307 | 284 lines |
| `_apply_following_movement()` | 682 | 192 lines |
| `_travel_continues()` | 1532 | 149 lines |
| `walk_declared()` | 1276 | 124 lines |
| `_guard_approach_is_not_arrival()` | 1683 | 96 lines |
| `_unreachable_position_writes()` | 875 | 68 lines |
| `walk_within_room()` | 1411 | 68 lines |
| `crossing_legs()` | 1781 | 59 lines |

### `agents/director_prose.py`

| Function | Start | Size |
|---|---:|---:|
| `run()` | 820 | 127 lines |
| `ledger_from_events()` | 748 | 70 lines |
| `encode()` | 671 | 67 lines |
| `dispatch()` | 949 | 56 lines |
| `bind_new_places()` | 464 | 49 lines |
| `select_channels()` | 246 | 42 lines |
| `reconcile_rooms()` | 587 | 41 lines |
| `already_happened()` | 167 | 39 lines |

### `agents/director_reconcile.py`

| Function | Start | Size |
|---|---:|---:|
| `_verify_already_true()` | 368 | 126 lines |
| `_scale_relation_conflicts()` | 214 | 107 lines |
| `_player_claim_findings()` | 61 | 82 lines |
| `_stamp_dialogue_articulation()` | 148 | 64 lines |
| `_acquit_addressed_events()` | 496 | 63 lines |
| `_route_repair_omissions()` | 567 | 44 lines |
| `_verify_no_referent()` | 339 | 27 lines |
| `_deep_audit_mode()` | 49 | 11 lines |

### `agents/director_rooms.py`

| Function | Start | Size |
|---|---:|---:|
| `schedule_room_predevelopment()` | 350 | 76 lines |
| `design_rooms()` | 248 | 73 lines |
| `render_room()` | 121 | 51 lines |
| `_check()` | 194 | 31 lines |
| `_merge_room()` | 87 | 22 lines |
| `_inspect()` | 174 | 18 lines |
| `_shown()` | 234 | 12 lines |
| `prepared_rooms()` | 336 | 12 lines |

### `agents/director_scopes.py`

| Function | Start | Size |
|---|---:|---:|
| `_dispatch_specialists()` | 1135 | 112 lines |
| `_ruling_for()` | 972 | 102 lines |
| `_gate_facts()` | 732 | 79 lines |
| `register_specialist()` | 528 | 49 lines |
| `manifest_category_targets()` | 892 | 49 lines |
| `note_key_targets()` | 844 | 46 lines |
| `_unrouted_rulings()` | 1076 | 46 lines |
| `_rebuild_channel_owners()` | 497 | 25 lines |

### `agents/director_views.py`

| Function | Start | Size |
|---|---:|---:|
| `_report_unowned_address_forms()` | 315 | 154 lines |
| `_report_observer_epithets()` | 242 | 71 lines |
| `_crowds_view()` | 500 | 68 lines |
| `_route_authorial_npc_beat()` | 66 | 48 lines |
| `_objective_scene()` | 667 | 40 lines |
| `_couriers_view()` | 570 | 32 lines |
| `_audit_fact_adjudications()` | 197 | 31 lines |
| `_round_conduct()` | 166 | 29 lines |

### `agents/dramaturge.py`

| Function | Start | Size |
|---|---:|---:|
| `propose()` | 219 | 92 lines |
| `_payload()` | 139 | 58 lines |
| `revise()` | 313 | 36 lines |
| `player_visible_stream()` | 100 | 31 lines |
| `_call()` | 78 | 16 lines |
| `_file()` | 203 | 14 lines |
| `system_block()` | 133 | 4 lines |

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
| `interaction_loop()` | 773 | 680 lines |
| `deterministic_micro_perception()` | 318 | 181 lines |
| `rehydrate_loop_views()` | 96 | 82 lines |
| `reaction_loop()` | 1454 | 76 lines |
| `self_micro_view()` | 223 | 54 lines |
| `_drop_absent()` | 514 | 45 lines |
| `_isolated_wave()` | 730 | 41 lines |
| `_defer_to_unrun_reactor()` | 591 | 37 lines |

### `agents/mapping.py`

| Function | Start | Size |
|---|---:|---:|
| `compile_world_context()` | 423 | 208 lines |
| `rulebook_rows()` | 297 | 124 lines |
| `classify_movement()` | 194 | 62 lines |
| `_location_query_status()` | 258 | 33 lines |
| `merge_lore()` | 633 | 33 lines |
| `contained_interior_holder()` | 131 | 30 lines |
| `is_contained_destination()` | 100 | 29 lines |
| `_transit_destination_needs()` | 163 | 29 lines |

### `agents/narration.py`

| Function | Start | Size |
|---|---:|---:|
| `narrator()` | 1955 | 525 lines |
| `_ordered_beat_events()` | 836 | 230 lines |
| `_sensory_channels_manifest()` | 588 | 219 lines |
| `narrator_extra()` | 2541 | 199 lines |
| `_visible_portal_states()` | 1174 | 118 lines |
| `_generate_narration()` | 1788 | 89 lines |
| `_position_delta_payload()` | 1099 | 73 lines |
| `_resolve_narration_person()` | 171 | 71 lines |

### `agents/offscreen_beat.py`

| Function | Start | Size |
|---|---:|---:|
| `note_beat_movement()` | 256 | 43 lines |
| `schedule_offscreen_beats()` | 150 | 38 lines |
| `run_offscreen_beat()` | 190 | 37 lines |
| `_file_stalled_needs()` | 301 | 33 lines |
| `offscreen_interpretation()` | 81 | 32 lines |
| `stalling_bodies()` | 229 | 25 lines |
| `is_offscreen_beat()` | 115 | 21 lines |
| `live_bubbles()` | 138 | 10 lines |

### `agents/perception.py`

| Function | Start | Size |
|---|---:|---:|
| `_composer_outcome_views()` | 6225 | 842 lines |
| `_composer_act_views()` | 5526 | 443 lines |
| `_composer_standing_percepts()` | 4871 | 321 lines |
| `perception_outcome()` | 3228 | 290 lines |
| `perception_act()` | 2736 | 222 lines |
| `_outcome_event_stream()` | 835 | 200 lines |
| `_source_channels()` | 1414 | 142 lines |
| `_scent_sources_for()` | 4443 | 130 lines |

### `agents/runtime.py`

| Function | Start | Size |
|---|---:|---:|
| `_run_pipeline()` | 1276 | 385 lines |
| `build_plan()` | 815 | 176 lines |
| `_load_extra_players()` | 53 | 101 lines |
| `resume_key_for_turn()` | 719 | 95 lines |
| `_stream_one()` | 482 | 68 lines |
| `_stream_parallel()` | 551 | 60 lines |
| `run_pipeline()` | 1712 | 57 lines |
| `_with_engine_notes()` | 422 | 55 lines |

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
| `run_planner()` | 731 | 306 lines |
| `run_location_plan()` | 1289 | 117 lines |
| `deliberate()` | 1503 | 91 lines |
| `_payload()` | 475 | 78 lines |
| `_shown_transcript()` | 404 | 69 lines |
| `run_opening_plan()` | 1115 | 64 lines |
| `schedule_room_work()` | 1685 | 63 lines |
| `planner_reply()` | 1429 | 51 lines |

### `core/db.py`

| Function | Start | Size |
|---|---:|---:|
| `_migrate_chat_copies_to_overlays()` | 2293 | 156 lines |
| `init()` | 2607 | 140 lines |
| `_recover_scene_time_of_day()` | 2537 | 59 lines |
| `transaction()` | 2115 | 43 lines |
| `conn()` | 2075 | 38 lines |
| `_opening_time_of_day()` | 2481 | 30 lines |
| `db_read_token()` | 2803 | 30 lines |
| `_establish_time_of_day_from_variant()` | 2451 | 28 lines |

### `core/frames.py`

| Function | Start | Size |
|---|---:|---:|
| `is_memory_visible()` | 194 | 89 lines |
| `frame_lookup()` | 128 | 25 lines |
| `create_frame()` | 164 | 21 lines |
| `_frame_from_row()` | 93 | 11 lines |
| `is_recognized_in_frame()` | 285 | 11 lines |
| `frame_index()` | 116 | 10 lines |
| `get_frame()` | 106 | 8 lines |
| `list_frames()` | 155 | 7 lines |

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
| `canonical_movement()` | 108 | 21 lines |
| `note_step_decision()` | 91 | 14 lines |
| `note_step_warning()` | 46 | 11 lines |
| `note_step_exchange()` | 78 | 11 lines |

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
| `generate_backdrop()` | 1570 | 116 lines |
| `room_projection()` | 892 | 79 lines |
| `build_backdrop_request()` | 1118 | 69 lines |
| `visual_signature()` | 210 | 59 lines |
| `_brief_sentences()` | 1268 | 51 lines |
| `compose_prompt()` | 1321 | 48 lines |
| `_camera_of()` | 783 | 44 lines |
| `room_brief()` | 846 | 44 lines |

### `llm/decisions.py`

| Function | Start | Size |
|---|---:|---:|
| `_post()` | 81 | 30 lines |
| `decide()` | 113 | 29 lines |
| `_provider()` | 51 | 10 lines |
| `_url()` | 70 | 9 lines |
| `probability()` | 144 | 8 lines |
| `configured()` | 63 | 5 lines |

### `llm/llm_quality.py`

| Function | Start | Size |
|---|---:|---:|
| `complete_validated_json()` | 638 | 644 lines |
| `_targeted_field_patch()` | 268 | 98 lines |
| `note_provider_exchange()` | 577 | 59 lines |
| `_step_json_schema()` | 526 | 49 lines |
| `output_ran_out_of_room()` | 116 | 47 lines |
| `json_failure_diagnosis()` | 165 | 39 lines |
| `_extract_balanced_object()` | 59 | 37 lines |
| `_without_trailing_commas()` | 23 | 34 lines |

### `llm/prompt_cache.py`

| Function | Start | Size |
|---|---:|---:|
| `add_cache_breakpoint()` | 15 | 37 lines |
| `estimate_cacheable_tokens()` | 66 | 14 lines |
| `supports_prompt_caching()` | 7 | 7 lines |

### `llm/prompts.py`

| Function | Start | Size |
|---|---:|---:|
| `preset_import_document()` | 276 | 51 lines |
| `specialist_prompt()` | 340 | 38 lines |
| `_relocate_character_identity()` | 524 | 29 lines |
| `character_prompt()` | 572 | 28 lines |
| `_assembled_sheets()` | 38 | 26 lines |
| `normalize_preset()` | 126 | 26 lines |
| `unified_specialist_prompt()` | 421 | 23 lines |
| `_preset_override()` | 223 | 22 lines |

### `llm/providers.py`

| Function | Start | Size |
|---|---:|---:|
| `_chat_complete_once()` | 3307 | 317 lines |
| `chat_complete()` | 3020 | 139 lines |
| `async _chat_complete_async_once()` | 3835 | 126 lines |
| `_claude_cli_complete()` | 2894 | 124 lines |
| `_sse_openai()` | 2586 | 90 lines |
| `async chat_complete_async()` | 3744 | 90 lines |
| `_json_mode_recovery_stages()` | 2310 | 83 lines |
| `async _sse_openai_async()` | 3962 | 71 lines |

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
| `semantic_output_errors()` | 6711 | 585 lines |
| `preprocess_llm_output()` | 5629 | 357 lines |
| `_lenient_coerce()` | 836 | 159 lines |
| `validate_llm_output_strict()` | 7539 | 139 lines |
| `_causal_patch_errors()` | 6579 | 130 lines |
| `canonicalize_prose_markup()` | 5261 | 102 lines |
| `_coerce_station_table()` | 85 | 81 lines |
| `_uncross_concealed_speech()` | 5385 | 69 lines |

### `mind/affect.py`

| Function | Start | Size |
|---|---:|---:|
| `resolve_affect()` | 816 | 189 lines |
| `apply_intent_ops()` | 1293 | 172 lines |
| `appraise()` | 499 | 145 lines |
| `apply_project_ops()` | 1706 | 137 lines |
| `settle_intent_world_anchors()` | 1527 | 132 lines |
| `normalize_wants()` | 1011 | 118 lines |
| `update_drive_strain()` | 2157 | 86 lines |
| `validate_drive_shift()` | 2286 | 79 lines |

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
| `build_character_memory_context()` | 256 | 453 lines |
| `_with_reading()` | 27 | 107 lines |
| `_origin_on_drift()` | 160 | 94 lines |
| `_summary_id()` | 147 | 3 lines |

### `mind/memory_inference.py`

| Function | Start | Size |
|---|---:|---:|
| `reconcile_inference_confidence()` | 90 | 70 lines |
| `_abandoned_confidence()` | 75 | 13 lines |
| `_mint_confidence_of()` | 61 | 12 lines |

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
| `raise_importance()` | 391 | 44 lines |
| `list_memories()` | 214 | 27 lines |
| `dramatic_irony_feed()` | 164 | 26 lines |
| `memory_bank_cache()` | 51 | 25 lines |
| `promise_ledger()` | 191 | 22 lines |

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
| `search_memories()` | 538 | 306 lines |
| `contrast_memory()` | 1058 | 127 lines |
| `_rank_normalized_importance()` | 475 | 61 lines |
| `recall_confidence()` | 963 | 59 lines |
| `record_memory_access()` | 846 | 50 lines |
| `_mmr_select()` | 170 | 43 lines |
| `recent_memory_buffer()` | 1199 | 43 lines |
| `_exact_cue_score()` | 96 | 33 lines |

### `mind/memory_snapshot.py`

| Function | Start | Size |
|---|---:|---:|
| `import_character_memories()` | 576 | 112 lines |
| `restore_lorebook()` | 849 | 98 lines |
| `prepare_chat_memory_restore()` | 372 | 89 lines |
| `dump_chat_memories()` | 277 | 86 lines |
| `restore_memory_vectors()` | 169 | 54 lines |
| `_foreign_persona_names()` | 531 | 43 lines |
| `restore_lore_overlays()` | 805 | 42 lines |
| `apply_chat_memory_restore()` | 462 | 40 lines |

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
| `repair_pending_embeddings()` | 547 | 92 lines |
| `prepare_memory()` | 348 | 73 lines |
| `_extract_entities()` | 110 | 63 lines |
| `_extract_key_phrases()` | 174 | 48 lines |
| `_upsert_memory()` | 671 | 45 lines |
| `_row_memory()` | 308 | 39 lines |
| `_embed_in_request_sized_chunks()` | 755 | 37 lines |
| `repair_seed_salience()` | 877 | 30 lines |

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
| `apply_mind_model_updates()` | 360 | 153 lines |
| `select_active_hypotheses()` | 648 | 62 lines |
| `rekey_place_claims()` | 305 | 53 lines |
| `belief_credence()` | 549 | 37 lines |
| `claim_similarity()` | 208 | 35 lines |
| `mind_models_for_payload()` | 514 | 33 lines |
| `_same_belief()` | 244 | 26 lines |
| `_elapsed()` | 272 | 26 lines |

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
| `_restore_checkpoint_body()` | 927 | 151 lines |
| `_restore_books()` | 367 | 148 lines |
| `compact_checkpoints()` | 1221 | 123 lines |
| `_snapshot_without_world()` | 191 | 117 lines |
| `insert_world_tables()` | 613 | 105 lines |
| `_snapshot_lore()` | 106 | 83 lines |
| `refresh_checkpoint()` | 1519 | 61 lines |
| `snapshot_blob()` | 50 | 54 lines |

### `persist/commit.py`

| Function | Start | Size |
|---|---:|---:|
| `_commit_all_locked()` | 481 | 368 lines |
| `commit_crowds()` | 294 | 149 lines |
| `commit_authored_events()` | 240 | 30 lines |
| `commit_narration_person()` | 208 | 29 lines |
| `_prepare_turn_commit()` | 458 | 12 lines |
| `commit_offscreen_epoch()` | 272 | 11 lines |
| `commit_all()` | 445 | 11 lines |
| `commit_offscreen_plans()` | 285 | 7 lines |

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
| `track_background_presences()` | 1971 | 875 lines |
| `pick_voice_demand()` | 3859 | 443 lines |
| `promote_background_character()` | 4448 | 393 lines |
| `_fold_duplicate_presences()` | 750 | 143 lines |
| `schedule_auto_promotion()` | 5101 | 123 lines |
| `addressed_rooms()` | 3736 | 121 lines |
| `descriptor_bindings()` | 3450 | 118 lines |
| `select_auto_promotion()` | 4880 | 92 lines |

### `persist/commit_common.py`

| Function | Start | Size |
|---|---:|---:|
| `_names_heard_in()` | 248 | 63 lines |
| `add_engine_notice()` | 634 | 63 lines |
| `_monotonic_elapsed()` | 72 | 53 lines |
| `_address_forms()` | 155 | 52 lines |
| `_resolve_roster_name()` | 465 | 47 lines |
| `_entity_alias_map()` | 524 | 47 lines |
| `charter_recognition_projection()` | 313 | 39 lines |
| `seed_mutual_recognition()` | 427 | 36 lines |

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
| `commit_world_entities()` | 215 | 362 lines |
| `_supersede_disguises()` | 96 | 74 lines |
| `_inherit_known_to()` | 172 | 41 lines |
| `_subjects_that_moved()` | 35 | 36 lines |
| `_subjects_targeted_by_an_action()` | 73 | 21 lines |
| `_is_gated_awareness()` | 17 | 16 lines |

### `persist/commit_ledgers.py`

| Function | Start | Size |
|---|---:|---:|
| `commit_world_pressure()` | 348 | 158 lines |
| `commit_obligations()` | 170 | 81 lines |
| `causal_obligation_ops()` | 107 | 61 lines |
| `commit_world_facts()` | 544 | 53 lines |
| `_find_obligation()` | 61 | 34 lines |
| `_positioned_body_named()` | 299 | 27 lines |
| `world_pressure_view()` | 275 | 22 lines |
| `pending_obligation_view()` | 40 | 20 lines |

### `persist/commit_mapping.py`

| Function | Start | Size |
|---|---:|---:|
| `commit_mapping()` | 667 | 223 lines |
| `_apply_mapping_book_ops()` | 142 | 106 lines |
| `_drop_needs_the_beat_answers()` | 543 | 83 lines |
| `prepare_mapping_commit()` | 250 | 76 lines |
| `_setting_fact_needs()` | 404 | 53 lines |
| `_answering_bodies()` | 490 | 51 lines |
| `_file_opening_premise()` | 355 | 47 lines |
| `_attach_committed_surface()` | 628 | 37 lines |

### `persist/commit_mechanics.py`

| Function | Start | Size |
|---|---:|---:|
| `commit_transit_sweep()` | 32 | 258 lines |
| `commit_information_carriers()` | 340 | 76 lines |
| `commit_cast_changes()` | 419 | 51 lines |
| `commit_world_event_spine()` | 292 | 46 lines |

### `persist/commit_memory.py`

| Function | Start | Size |
|---|---:|---:|
| `prepare_memory_commit()` | 584 | 1520 lines |
| `_cited_memory_ids()` | 83 | 76 lines |
| `_interior_relations_of()` | 489 | 55 lines |
| `_own_sequence_memory()` | 365 | 49 lines |
| `_hearer_label()` | 286 | 48 lines |
| `_witnessed_signals()` | 235 | 44 lines |
| `_evidence_spans()` | 191 | 42 lines |
| `_intent_names_term()` | 448 | 39 lines |

### `persist/commit_memory_write.py`

| Function | Start | Size |
|---|---:|---:|
| `commit_memories()` | 244 | 111 lines |
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
| `dedup_minted_rooms()` | 137 | 118 lines |
| `_prepare_room_registry()` | 256 | 115 lines |
| `_refresh_relocated_location()` | 438 | 78 lines |
| `prune_dangling_exits()` | 518 | 64 lines |
| `_apply_room_renames()` | 78 | 56 lines |
| `_apply_room_registry()` | 373 | 43 lines |
| `_registry_alias_index()` | 55 | 22 lines |
| `sync_room_registry_with_scene()` | 417 | 19 lines |

### `persist/commit_scene_state.py`

| Function | Start | Size |
|---|---:|---:|
| `compose_beat_scene()` | 1511 | 714 lines |
| `prepare_scene_commit()` | 2227 | 496 lines |
| `derive_borne_containment()` | 920 | 120 lines |
| `_fold_duplicate_mints()` | 767 | 118 lines |
| `_advance_day_cycle()` | 70 | 111 lines |
| `_refuse_unheld_transfers()` | 1042 | 102 lines |
| `_place_orphan_mints()` | 1146 | 70 lines |
| `_merge_overlays()` | 552 | 68 lines |

### `persist/llm_capture.py`

| Function | Start | Size |
|---|---:|---:|
| `record_exchange()` | 135 | 60 lines |
| `record_room_exchange()` | 379 | 52 lines |
| `referenced_blob_hashes()` | 237 | 36 lines |
| `put_blob()` | 78 | 25 lines |
| `latest_turn_id()` | 335 | 24 lines |
| `vacuum_blobs()` | 275 | 23 lines |
| `_payload_hashes()` | 112 | 21 lines |
| `exchanges_for_turn()` | 197 | 20 lines |

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
| `normalize_regions()` | 595 | 161 lines |
| `_attributed_scoped()` | 1899 | 139 lines |
| `coerce_diff_shape()` | 1564 | 136 lines |
| `advance()` | 2561 | 136 lines |
| `garments_named_in()` | 2236 | 126 lines |
| `compact_line()` | 3483 | 123 lines |
| `perceptible_region_surfaces()` | 2820 | 100 lines |
| `apply_flat_change()` | 3057 | 93 lines |

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
| `apply_tellings()` | 777 | 200 lines |
| `advance_carriers()` | 205 | 125 lines |
| `_build_carriers()` | 577 | 77 lines |
| `_crowds_acquire()` | 332 | 55 lines |
| `standing_surfaces_reader()` | 152 | 51 lines |
| `_carriers()` | 527 | 48 lines |
| `save_state()` | 431 | 43 lines |
| `persona_entry()` | 389 | 40 lines |

### `story/character_schema.py`

| Function | Start | Size |
|---|---:|---:|
| `character_card_warnings()` | 2499 | 174 lines |
| `default_character_data()` | 725 | 135 lines |
| `normalize_character_data()` | 1543 | 132 lines |
| `_normalize_psychology()` | 314 | 83 lines |
| `_normalize_native_shape()` | 1477 | 64 lines |
| `_normalize_interior()` | 664 | 59 lines |
| `repair_character_shape()` | 1240 | 57 lines |
| `normalize_persona_data()` | 1676 | 57 lines |

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
| `start_story()` | 784 | 446 lines |
| `_seed_mind_state()` | 357 | 144 lines |
| `generate_greeting()` | 1232 | 62 lines |
| `_seed_minds()` | 555 | 57 lines |
| `_route_mind_memories()` | 300 | 55 lines |
| `_seed_player_mind()` | 503 | 50 lines |
| `claim_greeting_mind()` | 614 | 44 lines |
| `_write_failed_setup()` | 739 | 37 lines |

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
| `apply_lorebook_plan()` | 2845 | 214 lines |
| `import_lorebook()` | 1644 | 212 lines |
| `draft_promoted_character()` | 739 | 142 lines |
| `_reinterpret_entries()` | 1517 | 126 lines |
| `_lore_gen_entry_batch()` | 2485 | 119 lines |
| `fill_body_interior()` | 1273 | 114 lines |
| `_run_lore_gen_job()` | 2608 | 112 lines |
| `fill_appearance()` | 1100 | 103 lines |

### `story/journey_history.py`

| Function | Start | Size |
|---|---:|---:|
| `compile_journey_history()` | 310 | 165 lines |
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
| `check()` | 260 | 89 lines |
| `set_skeleton()` | 146 | 47 lines |
| `set_history()` | 231 | 27 lines |
| `set_charter()` | 195 | 22 lines |
| `_reservation()` | 351 | 22 lines |
| `submitted_plan()` | 393 | 17 lines |
| `submit()` | 375 | 16 lines |
| `submitted_for()` | 422 | 12 lines |

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
| `grant_mandate()` | 303 | 82 lines |
| `_request()` | 200 | 29 lines |
| `expire_mandates()` | 387 | 28 lines |
| `request_open()` | 242 | 27 lines |
| `close_request()` | 417 | 26 lines |
| `renew_mandate()` | 445 | 22 lines |
| `coverage()` | 474 | 16 lines |
| `_most_permissive()` | 518 | 15 lines |

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
| `present_bodies()` | 98 | 19 lines |
| `mint_opening_mandate()` | 47 | 13 lines |
| `opening_placements()` | 62 | 10 lines |
| `record_placement()` | 74 | 8 lines |
| `record_opening_plan()` | 88 | 8 lines |
| `opening_plan_record()` | 84 | 2 lines |

### `story/plot_packages.py`

| Function | Start | Size |
|---|---:|---:|
| `_package_checks()` | 2972 | 143 lines |
| `_preview_plan_rooms()` | 1010 | 108 lines |
| `fire_due_clocks()` | 3545 | 102 lines |
| `publish_package()` | 3326 | 84 lines |
| `_reach_warning()` | 3117 | 79 lines |
| `normalize_package()` | 253 | 77 lines |
| `_tick_triggered_clocks()` | 3442 | 73 lines |
| `_plan_geometry()` | 771 | 68 lines |

### `story/prelude.py`

| Function | Start | Size |
|---|---:|---:|
| `begin_story()` | 127 | 62 lines |
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
| `fold()` | 381 | 52 lines |
| `render_block()` | 302 | 42 lines |
| `source_exists()` | 83 | 33 lines |
| `add_entry()` | 221 | 27 lines |
| `_validated()` | 194 | 25 lines |
| `mark_paid()` | 250 | 23 lines |
| `_row()` | 144 | 18 lines |
| `_normalize_entry()` | 122 | 15 lines |

### `story/room_calls.py`

| Function | Start | Size |
|---|---:|---:|
| `room_call()` | 69 | 39 lines |
| `room_max_tokens()` | 35 | 32 lines |
| `_reasoning()` | 129 | 12 lines |
| `_shape()` | 119 | 8 lines |
| `_requested()` | 110 | 7 lines |
| `memo_part()` | 238 | 4 lines |

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
| `converse_stream()` | 399 | 104 lines |
| `converse()` | 332 | 51 lines |
| `restore_room_messages()` | 515 | 36 lines |
| `normalize_mandate()` | 207 | 26 lines |
| `status()` | 281 | 24 lines |
| `add_message()` | 173 | 23 lines |
| `revoke_mandate()` | 262 | 17 lines |
| `_normalize_request()` | 235 | 15 lines |

### `story/room_frontier.py`

| Function | Start | Size |
|---|---:|---:|
| `frontier_report()` | 112 | 57 lines |
| `rooms_ahead()` | 74 | 36 lines |
| `_player_room()` | 53 | 19 lines |
| `record_spend()` | 208 | 14 lines |
| `fills_this_hour()` | 239 | 14 lines |
| `spend_this_hour()` | 224 | 13 lines |
| `record_fill()` | 190 | 11 lines |
| `record_measure()` | 171 | 8 lines |

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
| `web_search()` | 220 | 62 lines |
| `fetch_page()` | 284 | 49 lines |
| `tool_entries()` | 349 | 28 lines |
| `as_lore()` | 194 | 20 lines |
| `require_grant()` | 150 | 14 lines |
| `_save()` | 123 | 12 lines |
| `_load()` | 113 | 8 lines |
| `_with_templates()` | 335 | 8 lines |

### `story/room_slice.py`

| Function | Start | Size |
|---|---:|---:|
| `room_slices()` | 453 | 83 lines |
| `room_graph()` | 232 | 71 lines |
| `_plan_here()` | 403 | 48 lines |
| `_things_by_room()` | 375 | 26 lines |
| `room_index()` | 346 | 23 lines |
| `read_scene()` | 106 | 21 lines |
| `_registry()` | 166 | 21 lines |
| `cast_rooms()` | 325 | 19 lines |

### `story/room_tools.py`

| Function | Start | Size |
|---|---:|---:|
| `_t_inspect_contradictions()` | 766 | 201 lines |
| `_mind_of()` | 1106 | 148 lines |
| `_t_inspect_charters()` | 552 | 83 lines |
| `_t_inspect_config()` | 691 | 68 lines |
| `fit_result()` | 1687 | 64 lines |
| `_t_inspect_route()` | 295 | 53 lines |
| `_t_inspect_rooms()` | 244 | 49 lines |
| `_charter_body_rows()` | 460 | 38 lines |

### `story/scene.py`

| Function | Start | Size |
|---|---:|---:|
| `active_disguises()` | 685 | 82 lines |
| `_positive_presented_appearance()` | 976 | 66 lines |
| `normalize_transformed_parts()` | 776 | 60 lines |
| `recent_events_for_observer()` | 1949 | 59 lines |
| `awareness_conditions()` | 1334 | 58 lines |
| `normalize_style_guide()` | 2751 | 58 lines |
| `active_transformations()` | 838 | 54 lines |
| `dialogue_budget()` | 2856 | 54 lines |

### `web/app.py`

| Function | Start | Size |
|---|---:|---:|
| `turn_branch()` | 6567 | 478 lines |
| `chat_get()` | 4262 | 315 lines |
| `_remap_cp_blob()` | 1266 | 216 lines |
| `bootstrap()` | 1744 | 160 lines |
| `dlg_put()` | 5705 | 98 lines |
| `turn_new()` | 6399 | 98 lines |
| `chat_add_char()` | 4579 | 95 lines |
| `guest_state()` | 5006 | 95 lines |

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
| `grid_view()` | 825 | 176 lines |
| `room_entity_patch()` | 1545 | 95 lines |
| `_apply_exits()` | 1209 | 92 lines |
| `body_station_put()` | 1707 | 77 lines |
| `_apply_doorway_fields()` | 2248 | 77 lines |
| `map_view()` | 1057 | 73 lines |
| `body_rows()` | 600 | 70 lines |
| `charter_body_station_put()` | 2520 | 64 lines |

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
| `execution_receipt()` | 20 | 92 lines |
| `event_execution_statuses()` | 129 | 23 lines |
| `annotate_event_execution()` | 114 | 13 lines |

### `world/causal_program.py`

| Function | Start | Size |
|---|---:|---:|
| `bind_items()` | 61 | 164 lines |
| `program_steps()` | 303 | 54 lines |
| `_rewrite_patch()` | 31 | 28 lines |
| `event_worlds()` | 238 | 28 lines |
| `program_from_history()` | 268 | 23 lines |
| `prune_program()` | 369 | 19 lines |
| `fold_steps()` | 227 | 9 lines |
| `_content()` | 293 | 8 lines |

### `world/causal_verification.py`

| Function | Start | Size |
|---|---:|---:|
| `_map_receipts()` | 73 | 78 lines |
| `_inventory_receipts()` | 361 | 78 lines |
| `_overlay_receipts()` | 580 | 56 lines |
| `verify_patch()` | 638 | 54 lines |
| `_rooms_receipts()` | 178 | 51 lines |
| `_contact_receipts()` | 457 | 47 lines |
| `_attire_receipts()` | 541 | 37 lines |
| `_time_receipts()` | 330 | 29 lines |

### `world/causality.py`

| Function | Start | Size |
|---|---:|---:|
| `compile_transforms()` | 208 | 218 lines |
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
| `subject_label()` | 427 | 49 lines |
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
| `members_of()` | 121 | 41 lines |
| `crowd_for()` | 310 | 40 lines |
| `member_noun()` | 200 | 37 lines |
| `crowd_face()` | 279 | 29 lines |
| `engaged_turn()` | 81 | 20 lines |
| `composition_of()` | 239 | 18 lines |
| `mood_of()` | 259 | 18 lines |
| `presented()` | 103 | 16 lines |

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
| `close_plan()` | 885 | 393 lines |
| `_json_call()` | 268 | 100 lines |
| `_spread_berths()` | 672 | 84 lines |
| `_featured_assignments()` | 812 | 71 lines |
| `_ensure_shift_crews()` | 478 | 62 lines |
| `ensure_required_rooms()` | 1308 | 60 lines |
| `narrate_actual_history()` | 1477 | 58 lines |
| `_scale_populations()` | 594 | 51 lines |

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
| `integrate_featured_resident()` | 745 | 129 lines |
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
| `materialize_body_names()` | 950 | 119 lines |
| `name_is_reserved()` | 581 | 65 lines |
| `refuse_harvested_material()` | 816 | 62 lines |
| `derived_name_parts()` | 225 | 43 lines |
| `_stored_name_components()` | 355 | 43 lines |
| `identity_aliases()` | 1157 | 38 lines |
| `_fill_empty_material()` | 777 | 37 lines |
| `_syllable_name()` | 154 | 36 lines |

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
| `normalize_charter()` | 495 | 411 lines |
| `normalize_body()` | 231 | 158 lines |
| `body_of_an_authored_mind()` | 391 | 58 lines |
| `normalize_post()` | 144 | 45 lines |
| `normalize_body_station()` | 191 | 38 lines |
| `normalize_upkeep()` | 111 | 31 lines |
| `_phase_set()` | 473 | 20 lines |
| `_tags()` | 72 | 15 lines |

### `world/charter_move.py`

| Function | Start | Size |
|---|---:|---:|
| `errands()` | 405 | 122 lines |
| `_advance()` | 229 | 57 lines |
| `edge_seconds()` | 112 | 41 lines |
| `continue_walks()` | 288 | 41 lines |
| `place_body()` | 590 | 38 lines |
| `walk()` | 529 | 36 lines |
| `_dispatch()` | 195 | 32 lines |
| `relocate()` | 331 | 30 lines |

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
| `plan_public_evidence()` | 418 | 145 lines |
| `resolve_target_body()` | 339 | 77 lines |
| `body_receives_evidence()` | 90 | 74 lines |
| `apply_public_evidence()` | 565 | 74 lines |
| `evidence_claim()` | 193 | 40 lines |
| `_bodies_by_role()` | 304 | 33 lines |
| `_post_forms()` | 270 | 32 lines |
| `evidence_phrase()` | 170 | 21 lines |

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
| `charter_placements()` | 198 | 69 lines |
| `resolve_scene_placements()` | 430 | 66 lines |
| `lease_scene_bodies()` | 381 | 47 lines |
| `_station_and_facing()` | 150 | 46 lines |
| `_spelling_table()` | 346 | 33 lines |
| `lay_charter_bodies()` | 300 | 29 lines |
| `rooms_in_frame()` | 281 | 17 lines |
| `_dealt_cell()` | 132 | 12 lines |

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
| `_plan_lived_location()` | 1963 | 248 lines |
| `registry_warnings()` | 2527 | 233 lines |
| `advance_snapshot()` | 2983 | 200 lines |
| `_prepare_cast_histories()` | 1034 | 172 lines |
| `_generate_lived_location()` | 2271 | 163 lines |
| `presence_view()` | 4624 | 160 lines |
| `_remap_generated_town()` | 1689 | 134 lines |
| `hearing_for_creatures()` | 3185 | 112 lines |

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
| `sun_light()` | 189 | 49 lines |
| `clock_anchor()` | 315 | 33 lines |
| `clock_reading_hour()` | 244 | 24 lines |
| `charter_phase()` | 369 | 21 lines |
| `label_phase()` | 270 | 19 lines |
| `charter_hour()` | 392 | 14 lines |
| `describe()` | 350 | 13 lines |
| `label_hour()` | 291 | 12 lines |

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
| `_tick_conditions()` | 914 | 130 lines |
| `read_time_diff()` | 173 | 110 lines |
| `_fire_due_events()` | 526 | 104 lines |
| `mechanics_sweep()` | 1203 | 74 lines |
| `beat_time_from_spans()` | 311 | 55 lines |
| `unanswered_hazard_subjects()` | 1140 | 49 lines |
| `_schedule_new_arrivals()` | 632 | 46 lines |
| `_answered_bodies()` | 1106 | 32 lines |

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
| `materialize_plans_in_sight()` | 278 | 141 lines |
| `normalize_plan()` | 123 | 84 lines |
| `project_planned_emissions()` | 215 | 61 lines |
| `plan_figure()` | 503 | 43 lines |
| `plan_state()` | 79 | 42 lines |
| `settle_rendered_plans()` | 585 | 41 lines |
| `_station_a_thing()` | 421 | 40 lines |
| `_contradicted_axis()` | 628 | 20 lines |

### `world/planning_needs.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_need()` | 144 | 57 lines |
| `_fold_need()` | 258 | 27 lines |
| `record_planning_needs()` | 300 | 26 lines |
| `drain_planning_needs()` | 357 | 25 lines |
| `schedule_planning_needs()` | 384 | 25 lines |
| `planning_need()` | 203 | 17 lines |
| `fill_planning_need()` | 328 | 14 lines |
| `normalize_planning_needs()` | 222 | 12 lines |

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
| `backfill_regions()` | 512 | 65 lines |
| `inherit_regions()` | 343 | 55 lines |
| `assign_regions()` | 400 | 50 lines |
| `room_pieces()` | 456 | 50 lines |
| `set_region_look()` | 154 | 31 lines |
| `room_region()` | 248 | 25 lines |
| `set_region_name()` | 187 | 24 lines |
| `normalize_regions()` | 77 | 21 lines |

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
| `scene_memo()` | 170 | 21 lines |
| `_fingerprint()` | 110 | 14 lines |
| `scene_read_parts()` | 96 | 12 lines |
| `clear_scene_memo()` | 193 | 3 lines |

### `world/spatial_barriers.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_barrier()` | 329 | 82 lines |
| `neighbor_map()` | 580 | 80 lines |
| `effective_adjacent()` | 724 | 73 lines |
| `normalize_scene_passages()` | 878 | 54 lines |
| `normalize_scene_barriers()` | 467 | 32 lines |
| `passage_direction()` | 662 | 28 lines |
| `_barrier_against_its_own_name()` | 512 | 27 lines |
| `barrier_fastening()` | 413 | 24 lines |

### `world/spatial_bubbles.py`

| Function | Start | Size |
|---|---:|---:|
| `bubble_split_decision()` | 231 | 99 lines |
| `couple_decision()` | 335 | 52 lines |
| `detect_bubble()` | 446 | 51 lines |
| `uncouple_decision()` | 392 | 46 lines |
| `_cross_link()` | 121 | 35 lines |
| `_clusters()` | 201 | 28 lines |
| `fuse_comms()` | 91 | 25 lines |
| `in_range_rooms()` | 179 | 20 lines |

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
| `apply_contact_ops()` | 1347 | 422 lines |
| `_clean_contact()` | 925 | 168 lines |
| `normalize_scene_contacts()` | 1243 | 76 lines |
| `contacts_across_enclosure()` | 1135 | 68 lines |
| `_mirrored_displacements()` | 332 | 50 lines |
| `_unnamed_touch_between_bodies()` | 866 | 47 lines |
| `contact_thing_label()` | 794 | 42 lines |
| `_anchor_room_of()` | 752 | 40 lines |

### `world/spatial_containment.py`

| Function | Start | Size |
|---|---:|---:|
| `derive_inventory_placements()` | 1431 | 203 lines |
| `materialize_named_stations()` | 2692 | 135 lines |
| `advance_room_transits()` | 2829 | 130 lines |
| `replace_engine_minted_interiors()` | 2192 | 123 lines |
| `mint_transferred_objects()` | 1325 | 104 lines |
| `release_declared_departures()` | 2973 | 97 lines |
| `place_enclosed_bodies()` | 2317 | 95 lines |
| `derive_containment_from_contacts()` | 496 | 90 lines |

### `world/spatial_fov.py`

| Function | Start | Size |
|---|---:|---:|
| `_place_anchors()` | 544 | 125 lines |
| `feature_visibility()` | 1416 | 111 lines |
| `body_cell()` | 784 | 76 lines |
| `body_visibility()` | 1631 | 75 lines |
| `neighbour_feature_visibility()` | 1560 | 69 lines |
| `room_field()` | 1165 | 62 lines |
| `_line()` | 895 | 52 lines |
| `_placed_neighbours()` | 1104 | 49 lines |

### `world/spatial_frames.py`

| Function | Start | Size |
|---|---:|---:|
| `infer_focus()` | 551 | 245 lines |
| `perform_split()` | 1262 | 200 lines |
| `open_couple()` | 1912 | 179 lines |
| `infer_facing()` | 898 | 132 lines |
| `_partition_side()` | 2140 | 105 lines |
| `detect_and_reconcile()` | 2336 | 105 lines |
| `infer_threshold_crossings()` | 411 | 96 lines |
| `infer_vehicle_zones()` | 158 | 88 lines |

### `world/spatial_geometry.py`

| Function | Start | Size |
|---|---:|---:|
| `_effective_anchors()` | 355 | 114 lines |
| `invalidate_transferred_pose_details()` | 1704 | 113 lines |
| `spatial_digest()` | 150 | 107 lines |
| `derive_scene_stations()` | 2054 | 104 lines |
| `invalidate_moved_body_place_details()` | 1548 | 102 lines |
| `egocentric_frame()` | 62 | 86 lines |
| `invalidate_moved_body_pose_details()` | 1438 | 79 lines |
| `invalidate_contact_bound_poses()` | 1819 | 75 lines |

### `world/spatial_identity.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_scene_subjects()` | 596 | 115 lines |
| `canonical_subject_map()` | 498 | 87 lines |
| `scene_names_body()` | 343 | 73 lines |
| `room_of()` | 92 | 68 lines |
| `_live_subject_spellings()` | 444 | 52 lines |
| `scene_room_id()` | 807 | 42 lines |
| `room_of_record()` | 162 | 37 lines |
| `_positions_lookup()` | 10 | 28 lines |

### `world/spatial_levels.py`

| Function | Start | Size |
|---|---:|---:|
| `infer_room_levels()` | 137 | 44 lines |
| `_edges()` | 95 | 21 lines |
| `floor_edges()` | 220 | 20 lines |
| `_over_pairs()` | 123 | 12 lines |
| `stack_of()` | 197 | 12 lines |
| `normalize_level()` | 57 | 8 lines |
| `declared_way()` | 76 | 8 lines |
| `edge_way()` | 67 | 7 lines |

### `world/spatial_light.py`

| Function | Start | Size |
|---|---:|---:|
| `room_light()` | 41 | 70 lines |
| `unsourced_light_rooms()` | 187 | 63 lines |
| `source_light()` | 307 | 51 lines |
| `light_at()` | 371 | 50 lines |
| `effective_light()` | 423 | 39 lines |
| `unsourced_light_notices()` | 260 | 34 lines |
| `_declaration_is_the_only_account()` | 160 | 25 lines |
| `_sky_light()` | 113 | 22 lines |

### `world/spatial_light_field.py`

| Function | Start | Size |
|---|---:|---:|
| `light_shape()` | 1002 | 129 lines |
| `light_sources()` | 516 | 94 lines |
| `_bounce()` | 727 | 57 lines |
| `compute_light_field()` | 833 | 47 lines |
| `_spill()` | 786 | 45 lines |
| `_aimed_at()` | 1177 | 43 lines |
| `held_beam_falls_on()` | 1133 | 42 lines |
| `ambient_floor_word()` | 395 | 41 lines |

### `world/spatial_lint.py`

| Function | Start | Size |
|---|---:|---:|
| `layout_rooms()` | 276 | 64 lines |
| `layout_warning()` | 393 | 48 lines |
| `_shape_rows()` | 90 | 40 lines |
| `_wall_rows()` | 184 | 31 lines |
| `_beared_neighbours()` | 247 | 27 lines |
| `_part_components()` | 145 | 21 lines |
| `room_layout_lint()` | 371 | 20 lines |
| `_embedding_rows()` | 342 | 19 lines |

### `world/spatial_merge.py`

| Function | Start | Size |
|---|---:|---:|
| `merge_scene_with_diff()` | 1559 | 785 lines |
| `_expire_transient_entity_state()` | 599 | 116 lines |
| `_shield_standing_bearings()` | 881 | 107 lines |
| `_merge_room()` | 187 | 99 lines |
| `_shield_minted_edges()` | 1123 | 95 lines |
| `beat_movement_cuts()` | 2472 | 94 lines |
| `sync_scene_passages()` | 1385 | 90 lines |
| `apply_following_ops()` | 1306 | 77 lines |

### `world/spatial_orientation.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_scene_bearings()` | 153 | 159 lines |
| `derived_edge_bearings()` | 328 | 71 lines |
| `travel_bearing()` | 133 | 18 lines |
| `relative_bearing()` | 97 | 11 lines |
| `lateral_of()` | 110 | 11 lines |
| `turn_bearing()` | 64 | 10 lines |
| `normalize_bearing()` | 47 | 9 lines |
| `normalize_vertical()` | 83 | 8 lines |

### `world/spatial_prose.py`

| Function | Start | Size |
|---|---:|---:|
| `contact_sensation()` | 151 | 166 lines |
| `contact_phrase()` | 60 | 89 lines |
| `spatial_facts()` | 319 | 86 lines |
| `_interior_label()` | 28 | 30 lines |

### `world/spatial_routing.py`

| Function | Start | Size |
|---|---:|---:|
| `sprint_reach()` | 804 | 174 lines |
| `visible_adjacent_rooms()` | 1048 | 153 lines |
| `spatial_rel()` | 266 | 109 lines |
| `corridor_sightlines()` | 644 | 101 lines |
| `_onward_exits()` | 980 | 66 lines |
| `stamp_sight_direction()` | 178 | 45 lines |
| `passable_route_exists()` | 487 | 44 lines |
| `passable_path()` | 758 | 44 lines |

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
| `_hear_level()` | 1141 | 181 lines |
| `_opening_view_cap()` | 778 | 107 lines |
| `spatial_rel_between()` | 666 | 91 lines |
| `_visual_level_between()` | 915 | 81 lines |
| `comms_reachable_rooms()` | 279 | 66 lines |
| `comms_link()` | 375 | 66 lines |
| `hear_level()` | 1074 | 57 lines |
| `scent_level()` | 38 | 56 lines |

### `world/spatial_sound_field.py`

| Function | Start | Size |
|---|---:|---:|
| `sound_sources()` | 1363 | 135 lines |
| `sound_shape()` | 2966 | 92 lines |
| `spread()` | 1083 | 88 lines |
| `stamp_sound_relation()` | 2130 | 87 lines |
| `room_sound_flood()` | 2663 | 73 lines |
| `far_path_gain()` | 2041 | 66 lines |
| `distant_sounds()` | 2814 | 59 lines |
| `sound_field()` | 1971 | 44 lines |

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
| `apply_transit_dock_edges()` | 436 | 172 lines |
| `evict_self_contained_entities()` | 314 | 89 lines |
| `sync_entity_interior_rooms()` | 131 | 65 lines |
| `_is_body_entity()` | 62 | 49 lines |
| `ambient_scope()` | 642 | 29 lines |
| `infer_body_enclosures()` | 225 | 27 lines |
| `_interior_entry_room()` | 198 | 25 lines |
| `containment_chain()` | 622 | 19 lines |

### `world/spatial_walk.py`

| Function | Start | Size |
|---|---:|---:|
| `walk()` | 248 | 156 lines |
| `cell_path()` | 166 | 24 lines |
| `door_cell()` | 114 | 19 lines |
| `held_cells()` | 95 | 17 lines |
| `inside_the_door()` | 149 | 15 lines |
| `free_cell_near()` | 206 | 14 lines |
| `anchor_stand_cell()` | 222 | 14 lines |
| `paces_for()` | 67 | 12 lines |

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
| `claim_frontier_spaces()` | 1407 | 207 lines |
| `plant_structure()` | 495 | 173 lines |
| `prepare_frontier_expansion()` | 1204 | 147 lines |
| `materialize_planned_fringe()` | 670 | 120 lines |
| `mint_frontier()` | 389 | 104 lines |
| `planned_context()` | 1127 | 75 lines |
| `planned_room_brief()` | 937 | 62 lines |
| `structure_warnings()` | 1646 | 61 lines |

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

### `world/weather.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_weather()` | 424 | 163 lines |
| `weather_for_room()` | 921 | 86 lines |
| `advance_weather()` | 1163 | 78 lines |
| `weather_words()` | 1023 | 59 lines |
| `weather_depth()` | 790 | 57 lines |
| `ground_after()` | 1321 | 51 lines |
| `_derive_exposure()` | 679 | 32 lines |
| `anchor_exposure()` | 863 | 29 lines |

## FastAPI routes

| Method | Path | Handler | Source |
|---|---|---|---|
| GET | `/` | `index()` | `web/app.py:640` |
| PUT | `/api/active_preset` | `set_active()` | `web/app.py:2414` |
| PUT | `/api/affect_habituation` | `set_affect_habituation()` | `web/app.py:2734` |
| PUT | `/api/agent_models` | `put_agent_models()` | `web/app.py:1906` |
| PUT | `/api/ambience` | `put_ambience()` | `web/app.py:2062` |
| GET | `/api/ambience/library` | `ambience_library()` | `web/app.py:7801` |
| GET | `/api/ambience/search` | `ambience_search()` | `web/app.py:7780` |
| PUT | `/api/attire_beneath` | `set_attire_beneath()` | `web/app.py:2753` |
| POST | `/api/auth/login` | `auth_login()` | `web/auth_routes.py:209` |
| POST | `/api/auth/logout` | `auth_logout()` | `web/auth_routes.py:275` |
| POST | `/api/auth/setup` | `auth_setup()` | `web/auth_routes.py:134` |
| GET | `/api/auth/status` | `auth_status()` | `web/auth_routes.py:124` |
| GET | `/api/auto_promote` | `get_auto_promote()` | `web/app.py:4740` |
| PUT | `/api/auto_promote` | `set_auto_promote()` | `web/app.py:4753` |
| PUT | `/api/backdrops` | `put_backdrops()` | `web/app.py:2052` |
| GET | `/api/bootstrap` | `bootstrap_response()` | `web/app.py:1707` |
| POST | `/api/characters` | `char_create()` | `web/app.py:3209` |
| POST | `/api/characters/generate` | `char_generate()` | `web/app.py:3186` |
| POST | `/api/characters/import` | `char_import()` | `web/app.py:3234` |
| DELETE | `/api/characters/{cid}` | `char_del()` | `web/app.py:3575` |
| PUT | `/api/characters/{cid}` | `char_edit()` | `web/app.py:3546` |
| GET | `/api/characters/{cid}/export` | `char_export()` | `web/app.py:3538` |
| POST | `/api/characters/{cid}/fill_appearance` | `char_fill_appearance()` | `web/app.py:3517` |
| POST | `/api/characters/{cid}/fill_interior` | `char_fill_interior()` | `web/app.py:3471` |
| POST | `/api/characters/{cid}/fill_psychology` | `char_fill_psychology()` | `web/app.py:3436` |
| POST | `/api/characters/{cid}/generate_greeting` | `char_generate_greeting()` | `web/app.py:3406` |
| POST | `/api/characters/{cid}/recover_greetings` | `char_recover_greetings()` | `web/app.py:3396` |
| POST | `/api/characters/{cid}/start` | `character_start_story()` | `web/app.py:3258` |
| POST | `/api/chats` | `chat_new()` | `web/app.py:4008` |
| POST | `/api/chats/import` | `import_chat()` | `persist/chat_archive.py:273` |
| DELETE | `/api/chats/{cid}` | `chat_del()` | `web/app.py:4254` |
| GET | `/api/chats/{cid}` | `chat_get()` | `web/app.py:4262` |
| PUT | `/api/chats/{cid}` | `chat_edit()` | `web/app.py:4106` |
| POST | `/api/chats/{cid}/abort` | `chat_abort()` | `web/app.py:6563` |
| GET | `/api/chats/{cid}/ambience/oneshot/{name}` | `ambience_oneshot()` | `web/app.py:7810` |
| DELETE | `/api/chats/{cid}/ambience/pin` | `ambience_pin_delete()` | `web/app.py:7858` |
| PUT | `/api/chats/{cid}/ambience/pin` | `ambience_pin_put()` | `web/app.py:7839` |
| GET | `/api/chats/{cid}/ambience/pins` | `ambience_pins_get()` | `web/app.py:7834` |
| GET | `/api/chats/{cid}/ambience/{signature}.audio` | `ambience_audio()` | `web/app.py:7764` |
| GET | `/api/chats/{cid}/attire` | `attire_get()` | `web/app.py:5614` |
| PUT | `/api/chats/{cid}/attire` | `attire_put()` | `web/app.py:5625` |
| GET | `/api/chats/{cid}/backdrop/{signature}.png` | `backdrop_image()` | `web/app.py:7603` |
| GET | `/api/chats/{cid}/background_config` | `bg_cfg_get()` | `web/app.py:5949` |
| PUT | `/api/chats/{cid}/background_config` | `bg_cfg_put()` | `web/app.py:5953` |
| POST | `/api/chats/{cid}/begin` | `chat_begin()` | `web/app.py:3366` |
| DELETE | `/api/chats/{cid}/bodies/{name}` | `body_presence_delete()` | `web/world_routes.py:2108` |
| PUT | `/api/chats/{cid}/bodies/{name}/pose` | `body_pose_put()` | `web/world_routes.py:2193` |
| PUT | `/api/chats/{cid}/bodies/{name}/room` | `body_room_put()` | `web/world_routes.py:2142` |
| PUT | `/api/chats/{cid}/bodies/{name}/station` | `body_station_put()` | `web/world_routes.py:1707` |
| POST | `/api/chats/{cid}/characters` | `chat_add_char()` | `web/app.py:4579` |
| DELETE | `/api/chats/{cid}/characters/{ch}` | `chat_del_char()` | `web/app.py:5122` |
| PUT | `/api/chats/{cid}/characters/{ch}/card` | `chat_char_card_put()` | `web/app.py:5136` |
| PUT | `/api/chats/{cid}/characters/{ch}/dialogue_color` | `dialogue_color_put()` | `web/app.py:5482` |
| POST | `/api/chats/{cid}/characters/{ch}/fill_appearance` | `chat_char_fill_appearance()` | `web/app.py:3524` |
| POST | `/api/chats/{cid}/characters/{ch}/fill_interior` | `chat_char_fill_interior()` | `web/app.py:3482` |
| POST | `/api/chats/{cid}/characters/{ch}/fill_psychology` | `chat_char_fill_psychology()` | `web/app.py:3443` |
| GET | `/api/chats/{cid}/characters/{ch}/memories` | `mem_list()` | `web/app.py:6199` |
| POST | `/api/chats/{cid}/characters/{ch}/memories` | `mem_add()` | `web/app.py:6346` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/backfill` | `mem_backfill()` | `web/app.py:6316` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/consolidate` | `mem_consolidate()` | `web/app.py:6301` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/coverage` | `mem_coverage()` | `web/app.py:6337` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/export` | `mem_export()` | `web/app.py:6245` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/import` | `mem_import()` | `web/app.py:6256` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/search` | `mem_search()` | `web/app.py:6220` |
| GET | `/api/chats/{cid}/characters/{ch}/memory-context` | `memory_context_preview()` | `web/app.py:6277` |
| PUT | `/api/chats/{cid}/characters/{ch}/position` | `chat_char_position_put()` | `web/app.py:5370` |
| GET | `/api/chats/{cid}/characters/{ch}/private_history` | `ph_get()` | `web/app.py:5455` |
| PUT | `/api/chats/{cid}/characters/{ch}/private_history` | `ph_put()` | `web/app.py:5470` |
| GET | `/api/chats/{cid}/characters/{ch}/relationships` | `relationships_get()` | `web/app.py:6290` |
| GET | `/api/chats/{cid}/charters` | `charters_get()` | `web/app.py:5840` |
| PUT | `/api/chats/{cid}/charters` | `charters_put()` | `web/app.py:5861` |
| GET | `/api/chats/{cid}/charters/diagnostics` | `charters_diagnostics()` | `web/app.py:5879` |
| POST | `/api/chats/{cid}/charters/generate` | `charters_generate()` | `web/app.py:5891` |
| DELETE | `/api/chats/{cid}/charters/job` | `charters_job_clear()` | `web/app.py:5932` |
| GET | `/api/chats/{cid}/charters/job` | `charters_job_get()` | `web/app.py:5913` |
| DELETE | `/api/chats/{cid}/charters/{charter_key}/bodies/{body_key}/station` | `charter_body_station_delete()` | `web/world_routes.py:2587` |
| PUT | `/api/chats/{cid}/charters/{charter_key}/bodies/{body_key}/station` | `charter_body_station_put()` | `web/world_routes.py:2520` |
| GET | `/api/chats/{cid}/debug` | `chat_debug_export()` | `web/app.py:2377` |
| GET | `/api/chats/{cid}/dialogue_config` | `dlg_get()` | `web/app.py:5688` |
| PUT | `/api/chats/{cid}/dialogue_config` | `dlg_put()` | `web/app.py:5705` |
| POST | `/api/chats/{cid}/doorways` | `doorway_create()` | `web/world_routes.py:2328` |
| DELETE | `/api/chats/{cid}/doorways/{room_id}/{to}` | `doorway_delete()` | `web/world_routes.py:2403` |
| PATCH | `/api/chats/{cid}/doorways/{room_id}/{to}` | `doorway_patch()` | `web/world_routes.py:2367` |
| GET | `/api/chats/{cid}/dramatic_irony` | `get_dramatic_irony_feed()` | `web/app.py:4682` |
| GET | `/api/chats/{cid}/export` | `export_chat()` | `persist/chat_archive.py:267` |
| GET | `/api/chats/{cid}/fixed_points` | `fixed_points_list()` | `web/app.py:6144` |
| POST | `/api/chats/{cid}/fixed_points` | `fixed_points_create()` | `web/app.py:6154` |
| DELETE | `/api/chats/{cid}/fixed_points/{anchor_id}` | `fixed_points_delete()` | `web/app.py:6176` |
| GET | `/api/chats/{cid}/frames` | `frames_list()` | `web/app.py:6098` |
| POST | `/api/chats/{cid}/frames` | `frames_create()` | `web/app.py:6102` |
| GET | `/api/chats/{cid}/guest_invites` | `list_guest_invites()` | `web/app.py:4940` |
| POST | `/api/chats/{cid}/guest_invites` | `create_guest_invite()` | `web/app.py:4920` |
| DELETE | `/api/chats/{cid}/guest_invites/{gid}` | `revoke_guest_invite()` | `web/app.py:4944` |
| GET | `/api/chats/{cid}/language` | `chat_language_get()` | `web/app.py:4073` |
| PUT | `/api/chats/{cid}/language` | `chat_language_put()` | `web/app.py:4090` |
| GET | `/api/chats/{cid}/living_world` | `living_world_get()` | `web/app.py:5805` |
| PUT | `/api/chats/{cid}/living_world` | `living_world_put()` | `web/app.py:5828` |
| DELETE | `/api/chats/{cid}/lorebook` | `detach_lore()` | `web/app.py:4245` |
| POST | `/api/chats/{cid}/lorebook` | `bind_lore()` | `web/app.py:4219` |
| GET | `/api/chats/{cid}/lorebooks` | `chat_lorebooks_owned()` | `web/app.py:2837` |
| POST | `/api/chats/{cid}/lorebooks` | `attach_lore()` | `web/app.py:4137` |
| DELETE | `/api/chats/{cid}/lorebooks/{lid}` | `detach_book()` | `web/app.py:4204` |
| PUT | `/api/chats/{cid}/lorebooks/{lid}` | `set_book_enabled()` | `web/app.py:4168` |
| GET | `/api/chats/{cid}/map` | `map_index()` | `web/world_routes.py:1161` |
| GET | `/api/chats/{cid}/naming_profile` | `naming_profile_get()` | `web/app.py:5979` |
| PUT | `/api/chats/{cid}/naming_profile` | `naming_profile_put()` | `web/app.py:5991` |
| GET | `/api/chats/{cid}/paradox_policy` | `paradox_policy_get()` | `web/app.py:6129` |
| PUT | `/api/chats/{cid}/paradox_policy` | `paradox_policy_put()` | `web/app.py:6133` |
| GET | `/api/chats/{cid}/persona_private_history` | `pph_get()` | `web/app.py:5545` |
| PUT | `/api/chats/{cid}/persona_private_history` | `pph_put()` | `web/app.py:5558` |
| GET | `/api/chats/{cid}/personas` | `chat_list_extra_personas()` | `web/app.py:4758` |
| POST | `/api/chats/{cid}/personas` | `chat_add_persona()` | `web/app.py:4803` |
| DELETE | `/api/chats/{cid}/personas/{pid}` | `chat_del_persona()` | `web/app.py:4830` |
| PUT | `/api/chats/{cid}/personas/{pid}/station` | `chat_persona_station()` | `web/app.py:4768` |
| GET | `/api/chats/{cid}/player_authority` | `player_authority_get()` | `web/app.py:6061` |
| PUT | `/api/chats/{cid}/player_authority` | `player_authority_put()` | `web/app.py:6076` |
| GET | `/api/chats/{cid}/player_view` | `player_view_get()` | `web/app.py:6038` |
| GET | `/api/chats/{cid}/positions` | `chat_positions_get()` | `web/app.py:5303` |
| POST | `/api/chats/{cid}/prelude` | `chat_prelude()` | `web/app.py:3334` |
| GET | `/api/chats/{cid}/promises` | `get_promise_ledger()` | `web/app.py:4686` |
| GET | `/api/chats/{cid}/promotable` | `list_promotable_presences()` | `web/app.py:4678` |
| POST | `/api/chats/{cid}/promotions/confirm` | `confirm_promotion()` | `web/app.py:4707` |
| POST | `/api/chats/{cid}/promotions/draft` | `draft_promotion()` | `web/app.py:4690` |
| POST | `/api/chats/{cid}/regions` | `region_create()` | `web/world_routes.py:2436` |
| PATCH | `/api/chats/{cid}/regions/{region_id}` | `region_patch()` | `web/world_routes.py:1646` |
| POST | `/api/chats/{cid}/retry_start` | `chat_retry_start()` | `web/app.py:2320` |
| GET | `/api/chats/{cid}/room` | `room_thread()` | `web/room_routes.py:52` |
| POST | `/api/chats/{cid}/room/mandates/{uid}/revoke` | `room_revoke()` | `web/room_routes.py:108` |
| POST | `/api/chats/{cid}/room/messages` | `room_say()` | `web/room_routes.py:65` |
| POST | `/api/chats/{cid}/room/messages/stream` | `room_say_stream()` | `web/room_routes.py:78` |
| GET | `/api/chats/{cid}/room/status` | `room_status()` | `web/room_routes.py:117` |
| GET | `/api/chats/{cid}/rooms` | `rooms_index()` | `web/world_routes.py:673` |
| POST | `/api/chats/{cid}/rooms` | `room_create()` | `web/world_routes.py:1882` |
| DELETE | `/api/chats/{cid}/rooms/{room_id}` | `room_delete()` | `web/world_routes.py:1948` |
| GET | `/api/chats/{cid}/rooms/{room_id}` | `rooms_slice()` | `web/world_routes.py:799` |
| PATCH | `/api/chats/{cid}/rooms/{room_id}` | `room_patch()` | `web/world_routes.py:1493` |
| POST | `/api/chats/{cid}/rooms/{room_id}/entities` | `room_entity_create()` | `web/world_routes.py:1987` |
| DELETE | `/api/chats/{cid}/rooms/{room_id}/entities/{entity_id}` | `room_entity_delete()` | `web/world_routes.py:2023` |
| PATCH | `/api/chats/{cid}/rooms/{room_id}/entities/{entity_id}` | `room_entity_patch()` | `web/world_routes.py:1545` |
| GET | `/api/chats/{cid}/rooms/{room_id}/grid` | `rooms_grid()` | `web/world_routes.py:1133` |
| POST | `/api/chats/{cid}/rooms/{room_id}/presences` | `room_presence_create()` | `web/world_routes.py:2068` |
| GET | `/api/chats/{cid}/setup_log` | `chat_setup_log()` | `web/app.py:2353` |
| GET | `/api/chats/{cid}/story_view` | `story_view_get()` | `web/app.py:6004` |
| GET | `/api/chats/{cid}/style_guide` | `style_guide_get()` | `web/app.py:5671` |
| PUT | `/api/chats/{cid}/style_guide` | `style_guide_put()` | `web/app.py:5677` |
| GET | `/api/chats/{cid}/survival` | `survival_get()` | `web/app.py:5211` |
| PUT | `/api/chats/{cid}/survival` | `survival_put()` | `web/app.py:5216` |
| POST | `/api/chats/{cid}/turns` | `turn_new()` | `web/app.py:6399` |
| POST | `/api/chats/{cid}/turns/{idx}/player_input` | `submit_extra_player_input()` | `web/app.py:4844` |
| GET | `/api/chats/{cid}/viewers` | `viewers_get()` | `web/app.py:6053` |
| GET | `/api/chats/{cid}/vitals` | `chat_vitals_get()` | `web/app.py:5268` |
| GET | `/api/chats/{cid}/world` | `world_get()` | `web/app.py:5563` |
| PUT | `/api/chats/{cid}/world` | `world_put()` | `web/app.py:5573` |
| PUT | `/api/debug_capture` | `put_debug_capture()` | `web/app.py:2017` |
| GET | `/api/default_prompts` | `default_prompts()` | `web/app.py:2217` |
| PUT | `/api/director_fanout_mode` | `set_director_fanout_mode()` | `web/app.py:2710` |
| PUT | `/api/exemplars` | `put_exemplars()` | `web/app.py:1986` |
| GET | `/api/extensions` | `extensions_list()` | `web/app.py:2431` |
| POST | `/api/extensions/install` | `extension_install()` | `web/app.py:2453` |
| GET | `/api/extensions/ui.css` | `extensions_ui_css()` | `web/app.py:2631` |
| GET | `/api/extensions/ui.js` | `extensions_ui()` | `web/app.py:2622` |
| GET | `/api/extensions/updates` | `extension_updates()` | `web/app.py:2474` |
| DELETE | `/api/extensions/{eid}` | `extension_remove()` | `web/app.py:2495` |
| GET | `/api/extensions/{eid}/asset/{path:path}` | `extension_asset()` | `web/app.py:2686` |
| POST | `/api/extensions/{eid}/disable` | `extension_disable()` | `web/app.py:2503` |
| DELETE | `/api/extensions/{eid}/document` | `extension_document_delete()` | `web/app.py:2599` |
| GET | `/api/extensions/{eid}/document` | `extension_document_get()` | `web/app.py:2567` |
| PUT | `/api/extensions/{eid}/document` | `extension_document_put()` | `web/app.py:2579` |
| DELETE | `/api/extensions/{eid}/documents` | `extension_documents_delete()` | `web/app.py:2609` |
| GET | `/api/extensions/{eid}/documents` | `extension_documents_list()` | `web/app.py:2546` |
| GET | `/api/extensions/{eid}/documents/verify` | `extension_documents_verify()` | `web/app.py:2557` |
| POST | `/api/extensions/{eid}/enable` | `extension_enable()` | `web/app.py:2445` |
| GET | `/api/extensions/{eid}/state` | `extension_state()` | `web/app.py:2508` |
| GET | `/api/extensions/{eid}/ui.css` | `extension_ui_css_one()` | `web/app.py:2653` |
| GET | `/api/extensions/{eid}/ui.js` | `extension_ui_one()` | `web/app.py:2641` |
| POST | `/api/extensions/{eid}/update` | `extension_update()` | `web/app.py:2485` |
| POST | `/api/guest/input` | `guest_input()` | `web/app.py:5103` |
| GET | `/api/guest/state` | `guest_state()` | `web/app.py:5006` |
| PUT | `/api/image_model` | `put_image_model()` | `web/app.py:1964` |
| POST | `/api/join` | `join_with_code()` | `web/app.py:4950` |
| GET | `/api/language-packs` | `language_packs_get()` | `web/app.py:4026` |
| GET | `/api/language-packs/{language_id}/ui` | `language_pack_ui()` | `web/app.py:4047` |
| DELETE | `/api/lore_entries/{eid}` | `lore_entry_delete()` | `web/app.py:3983` |
| PUT | `/api/lore_entries/{eid}` | `lore_entry_edit()` | `web/app.py:3907` |
| DELETE | `/api/lore_entries/{eid}/overlay` | `lore_entry_overlay_clear()` | `web/app.py:3995` |
| DELETE | `/api/lore_gen_jobs/{job_id}` | `lorebook_generate_discard()` | `web/app.py:2993` |
| POST | `/api/lore_gen_jobs/{job_id}/resume` | `lorebook_generate_resume()` | `web/app.py:2975` |
| DELETE | `/api/lorebook_links/{link_id}` | `lorebook_link_delete()` | `web/app.py:2933` |
| PUT | `/api/lorebook_links/{link_id}` | `lorebook_link_update()` | `web/app.py:2919` |
| POST | `/api/lorebooks` | `lore_create()` | `web/app.py:3686` |
| POST | `/api/lorebooks/import` | `lore_import()` | `web/app.py:3029` |
| DELETE | `/api/lorebooks/{lid}` | `lore_delete()` | `web/app.py:3774` |
| GET | `/api/lorebooks/{lid}` | `lore_get()` | `web/app.py:3662` |
| PUT | `/api/lorebooks/{lid}` | `lore_edit()` | `web/app.py:3708` |
| POST | `/api/lorebooks/{lid}/apply_plan` | `lorebook_apply_plan()` | `web/app.py:3002` |
| POST | `/api/lorebooks/{lid}/entries` | `lore_entry_create()` | `web/app.py:3824` |
| GET | `/api/lorebooks/{lid}/export` | `lore_export()` | `web/app.py:3780` |
| POST | `/api/lorebooks/{lid}/generate` | `lore_generate()` | `web/app.py:3810` |
| GET | `/api/lorebooks/{lid}/generate_job` | `lorebook_generate_job()` | `web/app.py:2964` |
| POST | `/api/lorebooks/{lid}/generate_plan` | `lorebook_generate_plan()` | `web/app.py:2938` |
| GET | `/api/lorebooks/{lid}/links` | `lorebook_links_get()` | `web/app.py:2892` |
| POST | `/api/lorebooks/{lid}/links` | `lorebook_link_create()` | `web/app.py:2897` |
| POST | `/api/lorebooks/{lid}/move` | `lorebook_move()` | `web/app.py:2819` |
| POST | `/api/lorebooks/{lid}/reinterpret` | `lore_reinterpret_route()` | `web/app.py:3797` |
| POST | `/api/lorebooks/{lid}/reorder` | `lorebook_reorder()` | `web/app.py:2828` |
| GET | `/api/maintenance/checkpoints` | `maintenance_checkpoints()` | `web/app.py:2776` |
| POST | `/api/maintenance/checkpoints/compact` | `maintenance_compact()` | `web/app.py:2792` |
| PUT | `/api/max_output_tokens` | `put_max_output_tokens()` | `web/app.py:2184` |
| DELETE | `/api/memories/{mid}` | `mem_del()` | `web/app.py:6393` |
| PUT | `/api/memories/{mid}` | `mem_edit()` | `web/app.py:6372` |
| GET | `/api/memory/embeddings` | `memory_embeddings_status()` | `web/app.py:1937` |
| POST | `/api/memory/embeddings/rebuild` | `memory_embeddings_rebuild()` | `web/app.py:1952` |
| GET | `/api/nsfw` | `get_nsfw()` | `web/app.py:2701` |
| PUT | `/api/nsfw` | `set_nsfw()` | `web/app.py:2705` |
| GET | `/api/openrouter/endpoints` | `get_openrouter_endpoints()` | `web/app.py:2142` |
| PUT | `/api/openrouter_routing` | `put_openrouter_routing()` | `web/app.py:2128` |
| POST | `/api/personas` | `persona_create()` | `web/app.py:3604` |
| POST | `/api/personas/generate` | `persona_generate()` | `web/app.py:3582` |
| POST | `/api/personas/import` | `persona_import()` | `web/app.py:3624` |
| DELETE | `/api/personas/{pid}` | `persona_del()` | `web/app.py:3656` |
| PUT | `/api/personas/{pid}` | `persona_edit()` | `web/app.py:3647` |
| GET | `/api/personas/{pid}/export` | `persona_export()` | `web/app.py:3638` |
| POST | `/api/personas/{pid}/fill_appearance` | `persona_fill_appearance()` | `web/app.py:3533` |
| PUT | `/api/prompt_presets` | `save_preset()` | `web/app.py:2228` |
| POST | `/api/prompt_presets/import` | `import_preset()` | `web/app.py:2391` |
| DELETE | `/api/prompt_presets/{name}` | `del_preset()` | `web/app.py:2405` |
| GET | `/api/prompt_presets/{name}/export` | `export_preset()` | `web/app.py:2255` |
| POST | `/api/providers` | `add_provider()` | `web/app.py:3085` |
| DELETE | `/api/providers/{pid}` | `del_provider()` | `web/app.py:3164` |
| PUT | `/api/providers/{pid}` | `put_provider()` | `web/app.py:3092` |
| GET | `/api/providers/{pid}/image_models` | `image_models()` | `web/app.py:3176` |
| GET | `/api/providers/{pid}/models` | `models()` | `web/app.py:3169` |
| PUT | `/api/providers/{pid}/prompt_cache` | `put_provider_prompt_cache()` | `web/app.py:3119` |
| PUT | `/api/reasoning_effort` | `put_reasoning_effort()` | `web/app.py:2154` |
| GET | `/api/research` | `get_research()` | `web/app.py:2103` |
| PUT | `/api/research` | `put_research()` | `web/app.py:2108` |
| POST | `/api/steps/{sid}/activate` | `step_activate()` | `web/app.py:7401` |
| POST | `/api/steps/{sid}/edit` | `step_edit()` | `web/app.py:7390` |
| POST | `/api/steps/{sid}/reroll` | `step_reroll()` | `web/app.py:7321` |
| DELETE | `/api/turns/{tid}` | `turn_del()` | `web/app.py:7415` |
| GET | `/api/turns/{tid}/ambience` | `turn_ambience()` | `web/app.py:7713` |
| POST | `/api/turns/{tid}/ambience` | `turn_ambience_resolve()` | `web/app.py:7730` |
| GET | `/api/turns/{tid}/backdrop` | `turn_backdrop()` | `web/app.py:7557` |
| POST | `/api/turns/{tid}/backdrop` | `turn_backdrop_generate()` | `web/app.py:7572` |
| POST | `/api/turns/{tid}/branch` | `turn_branch()` | `web/app.py:6567` |
| PUT | `/api/turns/{tid}/input` | `edit_input()` | `web/app.py:7047` |
| GET | `/api/turns/{tid}/narration` | `turn_narration_variants()` | `web/app.py:7132` |
| POST | `/api/turns/{tid}/narration` | `turn_narration_select()` | `web/app.py:7153` |
| GET | `/api/turns/{tid}/pipeline` | `pipeline_get()` | `web/app.py:7177` |
| PUT | `/api/turns/{tid}/prose` | `edit_prose()` | `web/app.py:7062` |
| POST | `/api/turns/{tid}/reroll` | `turn_reroll()` | `web/app.py:7252` |
| POST | `/api/turns/{tid}/rerun` | `turn_rerun()` | `web/app.py:7262` |
| POST | `/api/turns/{tid}/resume` | `turn_resume()` | `web/app.py:7289` |
| GET | `/api/turns/{tid}/status` | `turn_status()` | `web/app.py:6522` |
| GET | `/api/turns/{turn_id}/debug` | `turn_debug_export()` | `web/app.py:2264` |
| GET | `/api/ui` | `ui_catalog_get()` | `web/app.py:4037` |
| PUT | `/api/ui-language` | `ui_language_put()` | `web/app.py:4062` |
| GET | `/api/updates/check` | `updates_check()` | `web/app.py:2768` |
| POST | `/api/updates/install` | `updates_install()` | `web/app.py:2772` |
| GET | `/guest` | `guest_page()` | `web/app.py:577` |
| GET | `/login` | `login_page()` | `web/app.py:646` |

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
| `llm_capture` | `id`, `turn_id`, `seq`, `step_key`, `role`, `requested`, `served`, `started`, `duration`, `ok`, `error`, `system_hash`, `payload_hashes`, `response_hash`, `reasoning_hash`, `--`, `--`, `--`, `--`, `--`, `response_format`, `reasoning_effort`, `max_tokens`, `finish_reason` |
| `memories` | `id`, `chat_id`, `char_id`, `turn_id`, `turn_idx`, `kind`, `category`, `provenance`, `salience`, `content`, `gist`, `key_phrases`, `entities`, `location`, `emotional_context`, `valence`, `arousal`, `--`, `--`, `--`, `encoding_valence`, `encoding_arousal`, `confidence`, `access_count`, `last_accessed`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `last_accessed_turn`, `embedding`, `cue_embedding`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `vkey`, `embedding_model`, `embedding_dim`, `archived`, `event_key`, `frame_id`, `--`, `--`, `--`, `--`, `importance`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `disputed`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `encoded_at_seconds` |
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

### `static/js/ambience.js` (1095 lines)

Sections: Room ambience (`:2`); seamless looping (`:256`); one-shots (`:735`); the ambience panel (`:784`); the mix (`:802`).

Declared functions: `ambienceStored()`, `ambienceElement()`, `entryAudios()`, `ambiencePlayers()`, `applyAmbienceMute()`, `setAmbienceVolume()`, `ambienceLevel()`, `setLayerGain()`, `toggleAmbienceMute()`, `ambienceFadeClock()`, `ambienceEnsureSounding()`, `ambienceFadeMix()`, `armSeamlessLoop()`, `crossLoop()`, `retireEntries()`, `stopAmbience()`, `playAmbience()`, `armAmbienceUnlock()`, `ambienceWorking()`, `awaitAmbience()`, `resolveAmbience()`, `ambienceForTurn()`, `rerollAmbience()`, `ambienceOnVisibleTurn()`, `ambienceResetForRender()`, `updateAmbienceBtn()`, `playAmbienceOneshot()`, `ambienceCandidateRow()`, `ambienceLayerRow()`, `ambienceMixPanel()`, `openAmbiencePanel()`, `toggleAmbience()`, `syncAmbience()`.

### `static/js/app.js` (1372 lines)

Sections: Boot & sidebar (`:1`); and then nothing showed the report, so a host who installed a pack got (`:50`); New chat wizard (`:369`); NSFW (`:1057`); Composer (`:1085`); Init (`:1163`); Embedding reconciler progress (`:1223`).

Declared functions: `boot()`, `renderSide()`, `syncExtensionTabs()`, `renderChatSidebar()`, `failedSetupRow()`, `newChatWizard()`, `renderWizardChoice()`, `storyLanguagePacks()`, `defaultStoryLanguage()`, `wizardState()`, `wizardHistoryCharacters()`, `discardFailedStorySetup()`, `wizardFromScratch()`, `renderWizardPersona()`, `renderWizardCharacters()`, `renderWizardScenario()`, `runWizard()`, `renderCharacterSidebar()`, `renderPersonaSidebar()`, `renderLegacyLoreSidebar()`, `updateNSFWBtn()`, `toggleNSFW()`, `resizeComposer()`, `erCard()`, `erDismiss()`, `erPoll()`, `erWatch()`, `erOfferRebuild()`.

### `static/js/backdrops.js` (430 lines)

Sections: Scene backdrops (`:2`).

Declared functions: `backdropLayers()`, `backdropLuminance()`, `applyBackdropContrast()`, `releaseBackdropLayer()`, `clearBackdrop()`, `showBackdrop()`, `backdropWorking()`, `awaitBackdrop()`, `generateBackdrop()`, `backdropForTurn()`, `backdropOnVisibleTurn()`, `backdropResetForRender()`, `updateBackdropBtn()`, `toggleBackdrops()`, `syncBackdrops()`.

### `static/js/chat.js` (3314 lines)

Sections: The turn being read (`:1`); Colouring who spoke (`:201`); `dialogue_log` is committed per turn and arrives as `turn.speech` -- and (`:204`); Flipping between rerolls of the newest beat (`:1126`); Pipeline drawer: reading a step through a lens (`:1477`); Pipeline drawer (`:1945`); Relationship viewer (`:2384`); Memory browser (`:2463`); Private history (`:3251`).

Declared functions: `observeVisibleTurn()`, `openChat()`, `foldTypography()`, `decodeProseEntities()`, `splitEmphasis()`, `appendEmphasized()`, `quoteBody()`, `quotedRegions()`, `speechSpans()`, `paintProse()`, `proseEl()`, `renderFrameBar()`, `switchFrame()`, `updateChatScopedButtons()`, `renderChat()`, `beginStory()`, `branchTurn()`, `editTurnInput()`, `editTurnProse()`, `liveReset()`, `friendlyPhase()`, `turnStatusStart()`, `turnStatusSet()`, `turnStatusStop()`, `_streamOn()`, `liveFlush()`, `liveAppend()`, `liveStep()`, `handleEvt()`, `inCurrentScope()`, `showNarrationEarly()`, `clearNarrationEarly()`, `resetRerollNav()`, `_mountRerollNav()`, `_paintRerollCount()`, `showRerollVariant()`, `abortActiveRun()`, `runStream()`, `confirmCheckpointRestore()`, `runReroll()`, `rerollTurn()`, `exportChat()`, `importChatModal()`, `perceiverViews()`, `loopMindIds()`, `specialistIds()`, `stepLenses()`, `perceiverLabel()`, `facetBadge()`, `lensLabel()`, `renderLensBar()`, `lensSlice()`, `specialistSlice()`, `perceptionPacketSlice()`, `perceiverSlice()`, `mindSlice()`, `keySlice()`, `renderEngineNotes()`, `pipelineMapPanel()`, `openPipeline()`, `relMeter()`, `relationshipModal()`, `memModal()`, `exportCharacterMemories()`, `importCharacterMemoriesModal()`, `memQS()`, `memCharId()`, `loadMemoryBrowse()`, `getMemUI()`, `renderMemorySummary()`, `sortedMems()`, `renderMemoryList()`, `memoryCard()`, `fieldWrap()`, `reloadMemView()`, `runMemorySearch()`, `showNewMemoryForm()`, `checkMemoryCoverage()`, `backfillMemoryEras()`, `consolidateMemories()`, `previewMemoryContext()`, `chatPH()`, `personaPH()`.

### `static/js/chime.js` (179 lines)

Sections: Turn-completion chime (`:2`); Which other waits are worth a chime (`:110`).

Declared functions: `chimeContext()`, `chimeArm()`, `chimePlay()`, `chimeWatches()`, `chimeWorkFinished()`, `chimeSetMuted()`, `toggleChimeMute()`, `updateChimeBtn()`.

### `static/js/components.js` (1324 lines)

Sections: Modal (`:38`); Book covers (`:54`); confirm()/prompt() replacements (`:167`); Toasts (`:500`); Background tasks (`:545`); Form helpers (`:631`); Model picker (`:1174`); made for every combobox that already has a provider saved -- opened its (`:1204`).

Declared functions: `txt()`, `el()`, `coverOfRow()`, `coverOfTitle()`, `modal()`, `modalOwnership()`, `closeModal()`, `closeAllModals()`, `_confirmOverlay()`, `confirmModal()`, `promptModal()`, `promptModalWithToggle()`, `livedLocationControl()`, `attachStoryLorebook()`, `generateStoryLocation()`, `openLivedLocationDialog()`, `toastHost()`, `toast()`, `renderActivity()`, `elapsedLabel()`, `activityTicking()`, `backgroundTask()`, `buttonTask()`, `loadingBlock()`, `emptyState()`, `fText()`, `fArea()`, `fSelect()`, `fNum()`, `fLineList()`, `fStrList()`, `attireRegions()`, `attireRegionZones()`, `fCoveragePicker()`, `fAttireGarments()`, `fList()`, `fAbilities()`, `fTraits()`, `fValues()`, `fBeliefs()`, `fCopingStrategies()`, `fAssociations()`, `fGoals()`, `fSenses()`, `fLatent()`, `extraPartAspects()`, `fExtraParts()`, `interiorLights()`, `fInteriorStations()`, `fPronouns()`, `phEditor()`, `fetchModels()`, `fetchImageModels()`, `modelCombobox()`, `emitChange()`, `load()`, `showDD()`.

### `static/js/editors.js` (1075 lines)

Sections: how many stations, and how many of them are new -- rather than letting a (`:62`); Carrying the fields an editor has no widget for (`:138`); Background-character promotion (`:903`); Import (file upload) (`:957`); Generate (`:1028`); Lorebook generate (`:1046`); Export (`:1063`).

Declared functions: `appearanceFillButton()`, `interiorFillButton()`, `defaultCharacterSheet()`, `carryUnpresentedFields()`, `greetingCarousel()`, `quickStartModal()`, `charEditor()`, `personaEditor()`, `promotionReviewModal()`, `promoteBackgroundPresence()`, `importModal()`, `generateModal()`, `generateLoreModal()`, `exportCharacter()`, `exportPersona()`, `exportLorebook()`.

### `static/js/extensions.js` (661 lines)

Sections: Extension host (`:2`); Registration attribution (`:20`); Failure containment (`:56`); ES module entries (`:86`); Registration surface (`:177`); Notices (`:222`); Host services (`:370`); The chat lifecycle, as a declared contract (`:401`); Host-internal accessors (`:483`); Hot load / unload (`:609`).

### `static/js/i18n-core.js` (188 lines)

Sections: The localization rules, once (`:3`).

Declared functions: `i18nCompileTemplates()`, `i18nTranslate()`, `i18nLocalize()`, `i18nObserve()`.

### `static/js/i18n.js` (34 lines)

### `static/js/lorebooks.js` (3823 lines)

Sections: Library sidebar (`:305`); Data loading (`:504`); Workspace (`:614`); Book metadata and tree operations (`:1212`); Entry editor (`:1725`); Lorebook relationships (`:2543`); Advanced generator (`:2994`); Interrupted-generation recovery (`:3216`).

Declared functions: `loreBookTypeIcon()`, `inheritanceModes()`, `knowledgeTags()`, `knowledgeRanges()`, `loreLinkTypes()`, `normalizeLoreBook()`, `loreOwnershipKey()`, `loreRootBooks()`, `loreBooksByParent()`, `loreBookMatches()`, `loreVisibleIds()`, `loreBookLabel()`, `parseStoredJSON()`, `loreField()`, `loreSelect()`, `loreBookOptions()`, `renderLoreLibrarySidebar()`, `renderNode()`, `loreStoryQuery()`, `loreBookIsLibrary()`, `loadLoreWorkspaceData()`, `collectLoreLinkTargets()`, `loreWorkspaceVisible()`, `renderLoreWorkspaceBody()`, `openLoreWorkspace()`, `renderLoreInspector()`, `selectTab()`, `buildLoreWorkspace()`, `renderWorkspaceTree()`, `renderNode()`, `renderTreeList()`, `renderLoreBookEditor()`, `moveLoreBook()`, `reorderLoreBook()`, `promoteLoreBook()`, `demoteLoreBook()`, `createSiblingLoreBook()`, `createLoreBookDialog()`, `refreshLoreUI()`, `renderLoreEntries()`, `renderList()`, `buildLoreEntryCard()`, `splitNumberList()`, `reinterpretLoreBook()`, `generateLoreEntriesPrompt()`, `buildDirectLoreRequest()`, `renderRelationshipOverview()`, `renderLoreRelationshipEditor()`, `renderRelationshipList()`, `showNewRelationshipForm()`, `renderLoreGenerator()`, `adoptGeneratorPlan()`, `generatorPlanMessage()`, `loreGenAgo()`, `refreshLoreGenRecovery()`, `normalizeGeneratorPlan()`, `renderLorePlanPreview()`, `renderOperations()`, `planStat()`, `renderAnalysisSection()`, `addPlanGroup()`, `stripPlanUIFields()`, `acceptedGeneratorPlan()`.

### `static/js/settings.js` (4022 lines)

Sections: Chat tool modals (`:1`); Condition tab (`:801`); Survival tracker (`:861`); Character relocation (`:1173`); API connections (`:1936`); Software updates (host-only; git fast-forward from GitHub origin) (`:3251`); Legacy checkpoint conversion (host-only maintenance) (`:3283`); Prompts (`:3517`); and be able to load that pack's own sheets to edit, rather than (`:3528`); Extensions (`:3695`).

Declared functions: `paradoxModes()`, `frameQuery()`, `charterDiagnosticsPanel()`, `selectTab()`, `dialogueColorControl()`, `save()`, `renderCastTab()`, `renderConditionTab()`, `hydrateConditionTab()`, `vitalMeter()`, `syncVitalsGutterNow()`, `syncVitalsGutter()`, `hideVitalsHud()`, `vitalsBlock()`, `refreshVitalsHud()`, `clearVitalsHud()`, `hydrateCastLocations()`, `castRoomLabel()`, `castRoomSelect()`, `renderLorebooksTab()`, `renderBookNode()`, `renderMultiplayerTab()`, `renderFramesTab()`, `renderFramesListPanel()`, `renderPersonaStationingPanel()`, `renderParadoxPanel()`, `renderBackgroundPresencesPanel()`, `renderGuestInvitePanel()`, `renderInsightsTab()`, `renderDramaticIronyPanel()`, `renderPromiseLedgerPanel()`, `embeddingBankBlock()`, `modelRecommendationsBlock()`, `renderFirstRunProviderSetup()`, `preferredBackdropSize()`, `renderFullApiSettings()`, `propagateToFollowers()`, `renderUpdateChecking()`, `renderUpdateError()`, `checkpointCompactionBlock()`, `renderUpdateStatus()`, `runUpdateInstall()`, `renderUpdateDone()`, `openPromptsModal()`, `reopenPromptsIfRequested()`, `extensionTrustNote()`, `extensionCapabilitySummary()`, `extensionSettingsSections()`, `openExtensionsMenu()`.

### `static/js/theme-init.js` (181 lines)

Declared functions: `readStored()`, `writeStored()`, `normaliseTheme()`, `normaliseProseSize()`, `applyTheme()`, `applyProseSize()`, `normaliseEffects()`, `applyEffects()`, `syncPageHidden()`.

### `static/js/themes.js` (159 lines)

Declared functions: `themePreview()`, `openAppearanceSettings()`.

### `static/js/utils.js` (245 lines)

Sections: API (`:105`); Download (`:224`); Card authoring warnings (`:233`).

Declared functions: `t()`, `watchUILanguage()`, `localizeDocument()`, `memoryCategories()`, `memoryProvenance()`, `hasDefaultModel()`, `safeId()`, `splitCL()`, `numOr()`, `taggedError()`, `errorDetailText()`, `api()`, `streamPost()`, `downloadJSON()`, `showCardWarnings()`.

### `static/js/weather-fx.js` (638 lines)

Sections: Weather effects (`:2`); the tile (`:219`); the layers (`:292`); lifecycle (`:391`); lightning (`:481`); schedules nothing; the visibility handler re-enters through (`:507`).

Declared functions: `weatherFxLater()`, `weatherFxCancel()`, `weatherFxClearTimers()`, `weatherFxClearBolt()`, `weatherFxReduced()`, `weatherFxEffectsOff()`, `weatherFxSupported()`, `weatherFxHost()`, `weatherFxRandom()`, `weatherFxTile()`, `weatherFxReach()`, `weatherFxBuild()`, `weatherFxClearLayers()`, `weatherFxSetPlayState()`, `weatherFxStop()`, `weatherFxVisible()`, `weatherFxApply()`, `weatherFxStormy()`, `weatherFxScheduleFlash()`, `weatherFxFlash()`, `weatherFxOpenSky()`, `weatherFxBolt()`, `weatherFxThunder()`, `weatherFxForTurn()`.

### `static/js/world_browser.js` (3369 lines)

Sections: The World Browser (`:3`); with its room, station, pose, and its FULL attire ledger, (`:31`); Edit controls (`:113`); The tree (`:216`); The room card (`:296`); Townspeople (2026-09-05, DESIGN_CHARTER_PLACEMENT § the map) (`:419`); `size` is the word for the floor and `extent` its measurement, so the (`:546`); The Bodies tab: every body, and the attire editor (`:1262`); The Raw JSON tab: the two editors, unchanged (`:1534`); The map editor (`:1621`); the neighbours, faintly, where the field lays them (`:1926`); the room's cells, and the overlay's tint over them (`:1967`); the boundary as a line, with each doorway a gap in it (`:2000`); anchors: footprint cells, the id, a height mark (`:2047`); things placed by a position and a station (`:2082`); bodies: a marked cell with a facing tick; the unstationed in a lane (`:2120`); the lint, drawn at the thing each row concerns (`:2176`); the shape: parts as rectangles, the box's sides as handles (`:2232`); blank wall segments open a doorway; empty floor places a thing (`:2289`); the drops (`:2313`); through the doorways route, so a doorway declared from the far room (`:2424`); The dialog (`:2806`).

Declared functions: `wbStatusBadge()`, `wbRoomLabel()`, `wbSelect()`, `wbText()`, `wbCoalesced()`, `wbWrite()`, `wbRenderTree()`, `wbSection()`, `wbIndexRows()`, `wbCellOf()`, `wbCellText()`, `wbStationText()`, `wbPoseText()`, `wbMoveControl()`, `wbNumber()`, `wbBodyMove()`, `wbCharterUrl()`, `wbCharterStationBody()`, `wbSourceWord()`, `wbCharterWhere()`, `wbCharterRow()`, `wbPoseEditor()`, `wbLintRows()`, `wbRoomFields()`, `wbRegionLook()`, `wbExits()`, `wbAnchors()`, `wbOccupant()`, `wbThing()`, `wbRenderCard()`, `wbGroupGarments()`, `wbLedgerEntry()`, `wbAttireEditor()`, `wbBodyKind()`, `wbCharterDetails()`, `wbRenderBodies()`, `wbRenderRaw()`, `wbSvg()`, `wbSvgPoint()`, `wbDraggable()`, `wbUndoStack()`, `wbWallOf()`, `wbOffsetAlong()`, `wbBearingBetween()`, `wbActivatable()`, `wbBoundary()`, `wbFocusRow()`, `wbFootprintLength()`, `wbRenderRoomMap()`, `centre()`, `partBox()`, `writeParts()`, `movePart()`, `dropPart()`, `sizePart()`, `resizePart()`, `writeExtent()`, `dropHandle()`, `nudgeHandle()`, `writeAnchors()`, `dropAnchor()`, `dropDoorway()`, `dropBody()`, `dropCharter()`, `dropThing()`, `wbRenderStructureMap()`, `wbRegionLegend()`, `wbMarksLegend()`, `wbMapPane()`, `wbWallForm()`, `wbCellForm()`, `wbMapNotes()`, `wbMapLegend()`, `openWorldBrowser()`, `moveRoute()`, `renderMapBar()`, `drawGrid()`, `loadGrid()`, `showStructure()`, `refreshIndex()`, `loadCard()`, `loadRoom()`, `selectTab()`.

### `static/js/writers_room.js` (796 lines)

Sections: The Writers' Room panel (`:3`); bd-panel for this element alone. (`:20`); Named limits (`:33`); Shape: docked / floating / closed (`:180`); Loading (`:237`); Sending (`:316`); The stream (`:349`); Rendering (`:424`); Building the panel (`:672`); Boot (`:785`).

Declared functions: `roomStoryText()`, `roomCls()`, `roomStoreGet()`, `roomStoreSet()`, `roomRestorePrefs()`, `roomClampWidth()`, `roomClampOpacity()`, `roomClampGeometry()`, `roomApplyShape()`, `roomOpen()`, `roomSetMode()`, `roomKey()`, `roomScope()`, `roomFrameQuery()`, `roomLoad()`, `roomLoadEarlier()`, `roomStartWatch()`, `roomStopWatch()`, `roomSend()`, `roomStream()`, `roomEvent()`, `roomRevoke()`, `roomRenderSoon()`, `roomRender()`, `roomRenderStatus()`, `roomRenderMandates()`, `roomRenderThread()`, `roomRenderCitations()`, `roomLiveNode()`, `roomBuild()`, `roomWireDrag()`, `track()`.
