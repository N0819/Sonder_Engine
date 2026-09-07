# Generated Code Map

> Regenerate with `python tools/generate_code_map.py`. Do not hand-edit this file.

## Python modules

| Module | Lines | Purpose | Local dependencies |
|---|---:|---|---|
| `agents/__init__.py` | 97 | Backward-compatible facade for the role-specific agent package. | `agents.background`, `agents.character`, `agents.common`, `agents.director`, `agents.loops`, `agents.mapping`, `agents.narration`, `agents.perception`, `agents.runtime`, `agents.storage`, `story.scene` |
| `agents/background.py` | 1692 |  | `agents.common`, `core.db`, `llm.prompts`, `llm.schemas`, `persist.commit`, `story.character_schema`, `story.scene`, `world.background_claims`, `world.spatial` |
| `agents/character.py` | 4256 | Private character decision agent. | `agents.common`, `core.db`, `core.frames`, `llm.prompts`, `llm.schemas`, `mind`, `mind.affect`, `mind.memory`, `mind.memory_judge`, `mind.psychology_runtime`, `mind.theory_of_mind`, `story.character_schema`, `story.scene`, `world.gaps`, `world.place_purpose`, `world.spatial`, `world.survival` |
| `agents/common.py` | 9932 | Shared normalization, lore, delivery, and perception helpers. | `core.db`, `core.pipeline_context`, `llm.llm_quality`, `llm.prompts`, `llm.providers`, `llm.schemas`, `mind.memory`, `mind.theory_of_mind`, `persist.commit`, `story`, `story.character_schema`, `story.provenance_text`, `story.scene`, `world`, `world.spatial` |
| `agents/composer.py` | 4327 |  | `agents.common`, `core.pipeline_context`, `story.provenance_text`, `story.scene`, `world.spatial` |
| `agents/director.py` | 5050 | Scene establishment, player interpretation, and objective resolution. | `agents.common`, `agents.director_contact`, `agents.director_evidence`, `agents.director_fanout`, `agents.director_floors`, `agents.director_lingua`, `agents.director_movement`, `agents.director_reconcile`, `agents.director_scopes`, `agents.director_views`, `core.db`, `llm`, `llm.prompts`, `llm.providers`, `llm.schemas`, `mind.memory`, `story`, `story.attire`, `story.character_schema`, `story.scene`, `world.paradox`, `world.spatial`, `world.survival` |
| `agents/director_contact.py` | 457 |  | `story.character_schema`, `world.spatial` |
| `agents/director_evidence.py` | 1261 |  | `agents.common`, `agents.director_lingua`, `llm`, `world.spatial` |
| `agents/director_fanout.py` | 944 |  | `agents.common`, `agents.director_evidence`, `agents.director_scopes`, `core.db`, `story.character_schema`, `world.spatial`, `world.survival` |
| `agents/director_floors.py` | 1922 |  | `agents.common`, `agents.director_lingua`, `story.character_schema`, `story.scene`, `world.mechanics`, `world.spatial` |
| `agents/director_lingua.py` | 29 |  | — |
| `agents/director_movement.py` | 1350 |  | `agents.director_lingua`, `story.character_schema`, `world.spatial` |
| `agents/director_reconcile.py` | 592 |  | `agents.common`, `agents.director_evidence`, `agents.director_scopes`, `core.db`, `story`, `world.spatial` |
| `agents/director_scopes.py` | 857 |  | `agents.director_views`, `core.db`, `world.survival` |
| `agents/director_views.py` | 627 |  | `agents.common`, `story.character_schema`, `story.scene`, `world.background_claims` |
| `agents/dramaturge.py` | 316 |  | `core.logging_utils` |
| `agents/loops.py` | 1388 | Reaction loops, interaction rounds, and deterministic micro-perception. | `agents.character`, `agents.common`, `core.db`, `story.character_schema`, `story.scene`, `world.spatial` |
| `agents/mapping.py` | 520 | Lore routing, cached recall, and retrieval staging. | `agents.common`, `core.db`, `mind.memory`, `story.scene`, `world.spatial` |
| `agents/narration.py` | 2294 | Player-facing narration agent. | `agents`, `agents.common`, `core.db`, `llm.prompts`, `llm.schemas`, `story.character_schema`, `story.scene`, `world.spatial`, `world.weather` |
| `agents/perception.py` | 5418 | Opening, action-onset, and outcome observer views. | `agents`, `agents.common`, `core.db`, `core.pipeline_context`, `mind`, `story.character_schema`, `story.scene`, `world.mechanics`, `world.spatial` |
| `agents/runtime.py` | 1471 | Pipeline plans, dispatch, streaming, cancellation, resume, and reruns. | `agents.background`, `agents.character`, `agents.common`, `agents.director`, `agents.loops`, `agents.mapping`, `agents.narration`, `agents.perception`, `agents.storage`, `core.db`, `core.pipeline_context`, `llm.providers`, `persist.checkpoints`, `persist.commit`, `story.character_schema`, `story.scene` |
| `agents/storage.py` | 123 | Step and active-variant persistence helpers. | `core.db` |
| `agents/story_planner.py` | 1265 |  | `core.logging_utils`, `story.room_calls` |
| `core/__init__.py` | 6 |  | — |
| `core/db.py` | 2614 | SQLite schema, migrations, connection management, transactions, and key/value world access. | `core.paths` |
| `core/frames.py` | 220 |  | `core.db` |
| `core/jobs.py` | 317 |  | `core.logging_utils` |
| `core/logging_utils.py` | 122 | Structured timing and observability helpers. | — |
| `core/outofband.py` | 392 |  | `core.logging_utils` |
| `core/paths.py` | 32 |  | — |
| `core/pipeline_context.py` | 521 | Typed mutable context passed through a turn pipeline. | `core.db` |
| `core/updates.py` | 399 |  | `core.paths` |
| `dressing/__init__.py` | 6 |  | — |
| `dressing/ambience.py` | 2072 |  | `core`, `core.db`, `core.paths`, `dressing.backdrops`, `world.weather` |
| `dressing/backdrops.py` | 1703 |  | `core`, `core.db`, `core.logging_utils`, `core.paths`, `world.day_cycle`, `world.spatial`, `world.weather` |
| `llm/__init__.py` | 6 |  | — |
| `llm/llm_quality.py` | 854 | Strict JSON parsing, schema validation, and model-assisted repair. | `core.pipeline_context`, `llm.prompts`, `llm.providers`, `llm.schemas` |
| `llm/prompt_cache.py` | 79 | Provider-specific prompt-cache helpers. | `llm.providers` |
| `llm/prompts.py` | 516 | Default system prompts and prompt preset access. | `core.db` |
| `llm/providers.py` | 3938 | Provider selection, retries, streaming, cancellation, model listing, and embeddings. | `core.db`, `core.logging_utils` |
| `llm/research_providers.py` | 247 |  | `core.db` |
| `llm/schemas.py` | 5686 | Pydantic output contracts and semantic validation for agent payloads. | — |
| `mind/__init__.py` | 6 |  | — |
| `mind/affect.py` | 2428 |  | `mind.theory_of_mind` |
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
| `mind/psychology_runtime.py` | 767 |  | — |
| `mind/theory_of_mind.py` | 725 |  | — |
| `persist/__init__.py` | 6 |  | — |
| `persist/chat_archive.py` | 1274 | Typed, atomic chat archive export/import service and HTTP routes. | `core.db`, `llm.schemas`, `mind.memory`, `persist.checkpoints`, `story.character_schema`, `story.room_conversation` |
| `persist/chat_delete.py` | 42 |  | `core.db` |
| `persist/checkpoints.py` | 1450 | Whole-chat snapshots and checkpoint restore orchestration. | `core.db`, `mind.memory` |
| `persist/commit.py` | 783 | Atomic commit orchestrator, per-turn lock, thin tail domains, and the facade re-exporting every commit_* name. | `core.db`, `core.frames`, `llm.prompts`, `llm.providers`, `mind`, `mind.memory`, `mind.theory_of_mind`, `persist.commit_attire`, `persist.commit_background`, `persist.commit_common`, `persist.commit_destruction`, `persist.commit_entities`, `persist.commit_ledgers`, `persist.commit_mapping`, `persist.commit_mechanics`, `persist.commit_memory`, `persist.commit_memory_write`, `persist.commit_place_graph`, `persist.commit_room_registry`, `persist.commit_scene_state`, `story`, `story.character_schema`, `story.scene`, `world.comfort`, `world.mechanics`, `world.paradox`, `world.spatial`, `world.spatial_frames`, `world.survival`, `world.weather` |
| `persist/commit_attire.py` | 1686 | The mutable clothing ledger: attire notes, shed/worn garment entities, the validated attire diff. | `persist.commit_common`, `story`, `story.attire` |
| `persist/commit_background.py` | 4273 | Background presences: tracking, identity folding, the reactor gate, promotion to cast. | `core.db`, `mind.memory`, `persist.commit_common`, `story.character_schema`, `story.scene`, `world.spatial` |
| `persist/commit_common.py` | 666 | Leaf helpers shared across commit domains: scalar utilities, name/address roster, entity-id canonicalisation. | `core.db`, `mind.memory`, `story.character_schema`, `world.mechanics`, `world.spatial` |
| `persist/commit_destruction.py` | 414 | Single- and multi-book destruction cascades, retirement, and latency-gated news. | `core.db`, `mind.memory`, `persist.commit_common`, `world.mechanics`, `world.spatial`, `world.spatial_frames` |
| `persist/commit_entities.py` | 560 | world_entities projection of the scene commit, awareness gate, disguise supersession. | `core.db`, `persist.commit_common`, `story.character_schema`, `story.scene`, `world.spatial` |
| `persist/commit_ledgers.py` | 465 | Pending-obligation and world-pressure debt ledgers. | `core.db`, `core.pipeline_context`, `persist.commit_common` |
| `persist/commit_mapping.py` | 754 | Lore/book mapping commit: book ops, lore ops, canon fallback ops, offscreen-event normaliser. | `core.db`, `core.frames`, `mind.memory`, `persist.commit_common`, `story.character_schema`, `story.provenance_text`, `world.spatial` |
| `persist/commit_mechanics.py` | 438 | Transit/news sweeps, the world-event spine, information carriers, cast changes. | `core.db`, `persist.commit_common`, `persist.commit_scene_state`, `story.character_schema`, `story.scene`, `world.mechanics` |
| `persist/commit_memory.py` | 1831 | Pre-lock memory preparation: per-mind memories and the psychology deltas riding with them. | `core.db`, `mind`, `mind.memory`, `mind.theory_of_mind`, `persist.commit_background`, `persist.commit_common`, `persist.commit_place_graph`, `story.character_schema`, `world.comfort`, `world.spatial`, `world.stimulation`, `world.survival` |
| `persist/commit_memory_write.py` | 325 | The durable memory write and its out-of-band consolidation twin. | `core.db`, `mind.memory`, `persist.commit_memory`, `story.character_schema`, `story.scene` |
| `persist/commit_place_graph.py` | 321 | Per-mind durable place graph and per-beat spatial experience. | `world.spatial` |
| `persist/commit_room_registry.py` | 521 | Room identity across frames: registry projection, mint dedup, renames, retirement, exit pruning. | `core.db`, `persist.commit_common`, `story.character_schema`, `world.spatial` |
| `persist/commit_scene_state.py` | 2273 | The prepared post-turn scene: pre-lock build, scene commit domain, book anchoring, ground advance. | `core.db`, `core.pipeline_context`, `mind.memory`, `persist.commit_attire`, `persist.commit_common`, `persist.commit_destruction`, `persist.commit_room_registry`, `story.character_schema`, `story.provenance_text`, `world.mechanics`, `world.spatial`, `world.spatial_frames`, `world.weather` |
| `persist/llm_capture.py` | 383 |  | `core.db` |
| `persist/pipeline_trace.py` | 596 | Privacy-conscious export, validation, and offline replay of persisted pipeline history. | `core.db` |
| `story/__init__.py` | 6 |  | — |
| `story/artifacts.py` | 649 |  | `llm.prompts` |
| `story/attire.py` | 3522 |  | — |
| `story/authored_events.py` | 299 |  | `core.db` |
| `story/carriers.py` | 788 |  | `core.db`, `story.character_schema`, `story.scene`, `world`, `world.spatial` |
| `story/character_schema.py` | 2306 | Versioned character/persona defaults, normalization, accessors, and export payloads. | `llm.schemas`, `story` |
| `story/couriers.py` | 1179 |  | `story.carriers`, `world` |
| `story/dialogue_colors.py` | 268 |  | — |
| `story/greetings.py` | 1008 |  | `agents.runtime`, `agents.storage`, `core`, `llm.llm_quality`, `llm.prompts`, `mind.memory`, `mind.theory_of_mind`, `story.character_schema`, `story.importers` |
| `story/history_routing.py` | 215 |  | — |
| `story/importers.py` | 3124 | Native and AI-assisted character, persona, and lorebook import/generation. | `core.db`, `core.logging_utils`, `llm.prompts`, `llm.providers`, `mind.memory`, `story.character_schema`, `story.scene` |
| `story/journey_history.py` | 431 |  | — |
| `story/lore_structure.py` | 248 |  | — |
| `story/mandates.py` | 594 |  | `core.db` |
| `story/naming.py` | 555 |  | `core.db`, `world.charter_identity` |
| `story/plot_packages.py` | 3163 |  | `world.spatial` |
| `story/provenance_text.py` | 132 |  | — |
| `story/room_bible.py` | 424 |  | `core.db` |
| `story/room_calls.py` | 130 |  | — |
| `story/room_citations.py` | 221 |  | — |
| `story/room_conversation.py` | 544 |  | `core.db` |
| `story/room_frontier.py` | 243 |  | `core.db` |
| `story/room_proposals.py` | 264 |  | `core.db` |
| `story/room_research.py` | 371 |  | `core.db` |
| `story/room_slice.py` | 509 |  | — |
| `story/room_tools.py` | 1619 |  | `story.plot_packages`, `story.room_research`, `story.room_slice` |
| `story/scene.py` | 2746 | Scene/cast/persona helpers, recent events, dialogue configuration, and private knowledge. | `core.db`, `story`, `story.attire`, `story.character_schema`, `world.day_cycle`, `world.spatial` |
| `web/__init__.py` | 6 |  | — |
| `web/app.py` | 6841 | FastAPI application assembly, resource CRUD, turn control, and streaming endpoints. | `agents`, `agents.story_planner`, `core`, `core.db`, `core.frames`, `core.paths`, `dressing.ambience`, `dressing.backdrops`, `llm`, `llm.prompts`, `llm.providers`, `mind.memory`, `persist.chat_archive`, `persist.chat_delete`, `persist.checkpoints`, `persist.commit`, `story`, `story.character_schema`, `story.dialogue_colors`, `story.importers`, `story.scene`, `web`, `web.auth_routes`, `web.room_routes`, `web.world_routes`, `world`, `world.survival` |
| `web/auth_routes.py` | 279 | Typed host-authentication HTTP routes and cookie transport. | `web` |
| `web/guest_access.py` | 554 |  | `core.db` |
| `web/room_routes.py` | 119 |  | `core.db`, `story` |
| `web/story_view.py` | 1023 |  | `core.db`, `world.charter_runtime`, `world.living_world` |
| `web/world_routes.py` | 2557 |  | `core`, `core.db`, `persist.commit`, `story`, `story.attire`, `story.character_schema`, `story.scene`, `world.charter`, `world.charter_runtime`, `world.spatial`, `world.weather` |
| `world/__init__.py` | 6 |  | — |
| `world/background_claims.py` | 598 |  | `core.db` |
| `world/charter.py` | 498 |  | `world.charter_author`, `world.charter_chatter`, `world.charter_commitment`, `world.charter_decide`, `world.charter_drift`, `world.charter_economy`, `world.charter_feel`, `world.charter_figure`, `world.charter_identity`, `world.charter_intervene`, `world.charter_log`, `world.charter_mark`, `world.charter_mind`, `world.charter_model`, `world.charter_move`, `world.charter_needs`, `world.charter_news`, `world.charter_place`, `world.charter_plan`, `world.charter_politics`, `world.charter_practice`, `world.charter_promote`, `world.charter_roster`, `world.charter_run`, `world.charter_social`, `world.charter_space`, `world.charter_talk`, `world.charter_temper`, `world.charter_trigger` |
| `world/charter_author.py` | 800 |  | `world.charter_commitment`, `world.charter_economy`, `world.charter_figure`, `world.charter_mark`, `world.charter_mind`, `world.charter_model`, `world.charter_politics`, `world.charter_practice` |
| `world/charter_chatter.py` | 443 |  | `world.crowds` |
| `world/charter_commitment.py` | 292 |  | `world.charter_model` |
| `world/charter_creature.py` | 464 |  | `world.charter_harm`, `world.charter_model` |
| `world/charter_crowd.py` | 282 |  | `world.crowds` |
| `world/charter_decide.py` | 279 |  | `world.charter_model`, `world.charter_news` |
| `world/charter_drift.py` | 106 |  | `world.charter_model` |
| `world/charter_economy.py` | 427 |  | `world.charter_model` |
| `world/charter_enrol.py` | 431 |  | `world.charter_generate`, `world.charter_model`, `world.charter_needs`, `world.charter_roster`, `world.charter_surface` |
| `world/charter_feel.py` | 444 |  | `mind.psychology_runtime`, `world.charter_mark`, `world.charter_needs`, `world.charter_temper` |
| `world/charter_figure.py` | 140 |  | — |
| `world/charter_generate.py` | 1418 |  | `world.charter_identity`, `world.charter_model`, `world.charter_needs`, `world.charter_roster`, `world.charter_surface` |
| `world/charter_harm.py` | 264 |  | — |
| `world/charter_history.py` | 873 |  | — |
| `world/charter_identity.py` | 1167 |  | — |
| `world/charter_intervene.py` | 344 |  | `world.charter_model` |
| `world/charter_log.py` | 510 |  | `world.charter_commitment`, `world.charter_decide`, `world.charter_economy`, `world.charter_feel`, `world.charter_mark`, `world.charter_mind`, `world.charter_model`, `world.charter_needs`, `world.charter_news`, `world.charter_politics`, `world.charter_social`, `world.charter_temper` |
| `world/charter_mark.py` | 302 |  | — |
| `world/charter_mind.py` | 262 |  | — |
| `world/charter_model.py` | 849 |  | `world.charter_chatter`, `world.charter_figure`, `world.charter_harm`, `world.charter_mark` |
| `world/charter_move.py` | 567 |  | `world.charter_space` |
| `world/charter_needs.py` | 297 |  | `world.charter_model` |
| `world/charter_news.py` | 517 |  | `world.charter_mind`, `world.charter_model`, `world.charter_talk` |
| `world/charter_observe.py` | 624 |  | `world.charter_figure`, `world.charter_identity`, `world.charter_mind`, `world.spatial` |
| `world/charter_ops.py` | 336 |  | `world.charter_harm` |
| `world/charter_place.py` | 453 |  | `world.charter_identity`, `world.charter_model`, `world.charter_move`, `world.spatial` |
| `world/charter_plan.py` | 227 |  | `world.charter_drift`, `world.charter_model`, `world.charter_roster` |
| `world/charter_politics.py` | 161 |  | — |
| `world/charter_practice.py` | 1200 |  | `world.charter_commitment`, `world.charter_figure`, `world.charter_mind`, `world.charter_politics`, `world.charter_talk` |
| `world/charter_predation.py` | 983 |  | `world.charter_creature`, `world.charter_harm`, `world.charter_model`, `world.charter_move` |
| `world/charter_promote.py` | 604 |  | `world.charter_commitment`, `world.charter_feel`, `world.charter_politics`, `world.charter_social` |
| `world/charter_roster.py` | 134 |  | `world.charter_model` |
| `world/charter_run.py` | 1477 |  | `world`, `world.charter_commitment`, `world.charter_decide`, `world.charter_drift`, `world.charter_economy`, `world.charter_enrol`, `world.charter_feel`, `world.charter_figure`, `world.charter_harm`, `world.charter_intervene`, `world.charter_log`, `world.charter_mark`, `world.charter_mind`, `world.charter_model`, `world.charter_move`, `world.charter_needs`, `world.charter_news`, `world.charter_plan`, `world.charter_politics`, `world.charter_practice`, `world.charter_roster`, `world.charter_social`, `world.charter_space`, `world.charter_talk`, `world.charter_trigger` |
| `world/charter_runtime.py` | 4390 |  | `core`, `core.logging_utils`, `world.charter`, `world.charter_news`, `world.charter_surface`, `world.day_cycle`, `world.mechanics`, `world.spatial` |
| `world/charter_social.py` | 743 |  | `world.charter_politics` |
| `world/charter_space.py` | 213 |  | `world.spatial` |
| `world/charter_surface.py` | 364 |  | — |
| `world/charter_surgery.py` | 370 |  | — |
| `world/charter_talk.py` | 351 |  | `world.charter_mind`, `world.charter_politics`, `world.charter_roster` |
| `world/charter_temper.py` | 167 |  | — |
| `world/charter_trigger.py` | 881 |  | `world.charter_mark`, `world.charter_news`, `world.charter_practice` |
| `world/comfort.py` | 349 |  | `world.spatial` |
| `world/crowds.py` | 759 |  | `world.spatial` |
| `world/day_cycle.py` | 351 |  | — |
| `world/degradation.py` | 171 |  | — |
| `world/gaps.py` | 454 |  | `core.db`, `mind.canon_provenance`, `world.spatial`, `world.subjects` |
| `world/living_world.py` | 596 |  | `core.logging_utils`, `world.mechanics` |
| `world/mechanics.py` | 1156 |  | `core`, `world.spatial`, `world.spatial_frames` |
| `world/offscreen.py` | 2299 |  | `core`, `core.logging_utils`, `llm.prompts` |
| `world/paradox.py` | 648 |  | `core.db`, `core.frames`, `story.character_schema`, `world.spatial` |
| `world/place_purpose.py` | 545 |  | `mind.theory_of_mind`, `world.comfort`, `world.spatial`, `world.survival` |
| `world/planned_entities.py` | 364 |  | `core.db` |
| `world/planning_needs.py` | 346 |  | — |
| `world/region_events.py` | 420 |  | — |
| `world/regions.py` | 582 |  | `world.spatial` |
| `world/routines.py` | 208 |  | — |
| `world/spatial.py` | 332 | Deterministic room, barrier, hearing, visibility, placement, and scene-diff logic. | `llm.schemas`, `world.spatial_barriers`, `world.spatial_contact_migration`, `world.spatial_contacts`, `world.spatial_containment`, `world.spatial_fov`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_light`, `world.spatial_light_field`, `world.spatial_lint`, `world.spatial_merge`, `world.spatial_orientation`, `world.spatial_prose`, `world.spatial_routing`, `world.spatial_scent_field`, `world.spatial_senses`, `world.spatial_sound_field`, `world.spatial_substance`, `world.spatial_transit` |
| `world/spatial_barriers.py` | 846 |  | `world.spatial_orientation` |
| `world/spatial_contact_migration.py` | 331 |  | `world.spatial_contacts`, `world.spatial_identity` |
| `world/spatial_contacts.py` | 1951 |  | `world.spatial_containment`, `world.spatial_identity`, `world.spatial_transit` |
| `world/spatial_containment.py` | 3049 |  | `world.spatial_barriers`, `world.spatial_identity`, `world.spatial_transit` |
| `world/spatial_fov.py` | 1628 |  | `world.spatial_barriers`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_orientation` |
| `world/spatial_frames.py` | 1126 |  | `core.db`, `core.frames`, `story.character_schema`, `story.scene`, `world.paradox`, `world.spatial` |
| `world/spatial_geometry.py` | 2027 |  | `world.spatial_barriers`, `world.spatial_contacts`, `world.spatial_containment`, `world.spatial_identity`, `world.spatial_orientation` |
| `world/spatial_identity.py` | 498 |  | — |
| `world/spatial_light.py` | 471 |  | `world.spatial_barriers`, `world.spatial_geometry`, `world.spatial_identity` |
| `world/spatial_light_field.py` | 1136 |  | `world.spatial_barriers`, `world.spatial_containment`, `world.spatial_fov`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_light`, `world.spatial_orientation` |
| `world/spatial_lint.py` | 444 |  | `world.spatial_barriers`, `world.spatial_fov`, `world.spatial_geometry`, `world.spatial_orientation` |
| `world/spatial_merge.py` | 2180 |  | `llm.schemas`, `world.spatial_barriers`, `world.spatial_contact_migration`, `world.spatial_contacts`, `world.spatial_containment`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_orientation`, `world.spatial_routing`, `world.spatial_senses`, `world.spatial_substance`, `world.spatial_transit` |
| `world/spatial_orientation.py` | 358 | Bearing math and reciprocal spatial-edge normalization. | — |
| `world/spatial_prose.py` | 404 |  | `world.spatial_contacts`, `world.spatial_containment`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_light` |
| `world/spatial_routing.py` | 1120 |  | `world.spatial_barriers`, `world.spatial_containment`, `world.spatial_light`, `world.spatial_orientation` |
| `world/spatial_scent_field.py` | 233 |  | `world.spatial_barriers` |
| `world/spatial_senses.py` | 1595 |  | `world.spatial_barriers`, `world.spatial_contacts`, `world.spatial_containment`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_light`, `world.spatial_orientation`, `world.spatial_routing` |
| `world/spatial_sound_field.py` | 2417 |  | `world.spatial_barriers`, `world.spatial_containment`, `world.spatial_fov`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_light_field`, `world.spatial_senses` |
| `world/spatial_substance.py` | 1128 |  | `world.spatial_contacts`, `world.spatial_identity` |
| `world/spatial_transit.py` | 522 |  | `world.spatial_barriers`, `world.spatial_identity` |
| `world/stimulation.py` | 239 |  | `story`, `world.spatial` |
| `world/structure.py` | 1465 |  | `world.charter_model`, `world.regions`, `world.spatial` |
| `world/subjects.py` | 500 |  | `core.db`, `mind.canon_provenance`, `world.spatial` |
| `world/survival.py` | 463 |  | `core.db` |
| `world/weather.py` | 916 |  | — |

## Largest top-level functions

### `agents/background.py`

| Function | Start | Size |
|---|---:|---:|
| `_react_one()` | 1513 | 180 lines |
| `_background_react()` | 440 | 176 lines |
| `scene_life()` | 1041 | 157 lines |
| `_demanded_presences()` | 835 | 138 lines |
| `_beat_for_presence()` | 190 | 80 lines |
| `_present_others()` | 1431 | 80 lines |
| `managed_presences()` | 690 | 78 lines |
| `_filtered_player_declaration()` | 111 | 77 lines |

### `agents/character.py`

| Function | Start | Size |
|---|---:|---:|
| `character_step()` | 3085 | 1172 lines |
| `_annotate_known_exits()` | 2436 | 458 lines |
| `_ground_observation_citations()` | 1417 | 322 lines |
| `_unanswered_question_note()` | 501 | 221 lines |
| `_destination_from_goals()` | 2002 | 109 lines |
| `sprint_offers()` | 2929 | 97 lines |
| `_recent_self_moves()` | 232 | 86 lines |
| `strip_beat_reissues()` | 938 | 82 lines |

### `agents/common.py`

| Function | Start | Size |
|---|---:|---:|
| `norm_sequence()` | 3714 | 284 lines |
| `_check_narrator_fidelity()` | 9395 | 236 lines |
| `presence_figures_for_room()` | 1901 | 211 lines |
| `_unknown_actor_label()` | 4474 | 152 lines |
| `_scrub_invented_dialogue()` | 7963 | 151 lines |
| `_check_quote_attribution()` | 8958 | 139 lines |
| `observer_body_regions()` | 1465 | 137 lines |
| `_scrub_unknown_identities()` | 4820 | 124 lines |

### `agents/composer.py`

| Function | Start | Size |
|---|---:|---:|
| `_render_view_english()` | 3550 | 217 lines |
| `observations_from_render()` | 4119 | 209 lines |
| `pose_percepts()` | 1757 | 149 lines |
| `presence_percepts()` | 1037 | 139 lines |
| `speech_percept()` | 2427 | 124 lines |
| `line_hear_level()` | 573 | 107 lines |
| `act_percept()` | 2589 | 103 lines |
| `environment_percept()` | 776 | 101 lines |

### `agents/director.py`

| Function | Start | Size |
|---|---:|---:|
| `director_resolve()` | 3072 | 1945 lines |
| `director_interpret()` | 803 | 665 lines |
| `_reconcile_resolution()` | 1856 | 522 lines |
| `_run_specialists()` | 2585 | 263 lines |
| `director_establish()` | 324 | 171 lines |
| `_reconcile_interpretation()` | 1470 | 139 lines |
| `_specialist_repairs()` | 1671 | 131 lines |
| `_ground_public_evidence()` | 2890 | 112 lines |

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
| `_evidence_present()` | 829 | 324 lines |
| `_merge_repair_into_diff()` | 515 | 59 lines |
| `_omission_subject_encoded()` | 711 | 57 lines |
| `_fold_derived_manifest_events()` | 1206 | 56 lines |
| `_interpret_coverage_corpus()` | 91 | 53 lines |
| `_subject_is_somewhere()` | 780 | 47 lines |
| `_strip_blank_diff_placeholders()` | 256 | 42 lines |
| `_manifest_items()` | 1160 | 37 lines |

### `agents/director_fanout.py`

| Function | Start | Size |
|---|---:|---:|
| `_specialist_payload()` | 362 | 306 lines |
| `_orchestration_scope_backstop()` | 794 | 151 lines |
| `_resolve_beat_view()` | 74 | 127 lines |
| `_interpret_beat_view()` | 203 | 40 lines |
| `_beat_rooms()` | 286 | 37 lines |
| `_anchor_names()` | 325 | 35 lines |
| `_resolved_event_verdicts()` | 704 | 30 lines |
| `_author_emitted_channels()` | 756 | 25 lines |

### `agents/director_floors.py`

| Function | Start | Size |
|---|---:|---:|
| `_bind_minted_entities_to_present_figures()` | 1467 | 198 lines |
| `resolve_concealment_refs()` | 1716 | 104 lines |
| `_awareness_exits()` | 715 | 98 lines |
| `_release_attempts()` | 973 | 93 lines |
| `_conditions_view()` | 595 | 87 lines |
| `strip_addressee_concealment()` | 1842 | 81 lines |
| `_narrated_destruction_subjects()` | 1233 | 79 lines |
| `_unsupported_character_awareness()` | 310 | 66 lines |

### `agents/director_lingua.py`

| Function | Start | Size |
|---|---:|---:|
| `_ling()` | 16 | 14 lines |

### `agents/director_movement.py`

| Function | Start | Size |
|---|---:|---:|
| `_reconcile_near_group_positions()` | 209 | 284 lines |
| `_travel_continues()` | 1083 | 109 lines |
| `_guard_approach_is_not_arrival()` | 1194 | 96 lines |
| `_apply_following_movement()` | 584 | 88 lines |
| `_unreachable_position_writes()` | 673 | 68 lines |
| `crossing_legs()` | 1292 | 59 lines |
| `_door_route()` | 843 | 57 lines |
| `declared_walk_leg()` | 912 | 54 lines |

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
| `_gate_facts()` | 613 | 76 lines |
| `_dispatch_specialists()` | 796 | 62 lines |
| `register_specialist()` | 471 | 49 lines |
| `_ruling_for()` | 728 | 39 lines |
| `_rebuild_channel_owners()` | 440 | 25 lines |
| `_unrouted_rulings()` | 769 | 25 lines |
| `_schema_list_channels()` | 254 | 23 lines |
| `reads_dialogue()` | 162 | 18 lines |

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
| `propose()` | 197 | 82 lines |
| `_payload()` | 139 | 36 lines |
| `revise()` | 281 | 36 lines |
| `player_visible_stream()` | 100 | 31 lines |
| `_call()` | 78 | 16 lines |
| `_file()` | 181 | 14 lines |
| `system_block()` | 133 | 4 lines |

### `agents/loops.py`

| Function | Start | Size |
|---|---:|---:|
| `interaction_loop()` | 669 | 649 lines |
| `deterministic_micro_perception()` | 235 | 156 lines |
| `reaction_loop()` | 1319 | 70 lines |
| `rehydrate_loop_views()` | 89 | 59 lines |
| `self_micro_view()` | 150 | 46 lines |
| `_drop_absent()` | 406 | 45 lines |
| `_isolated_wave()` | 626 | 41 lines |
| `_defer_to_unrun_reactor()` | 483 | 37 lines |

### `agents/mapping.py`

| Function | Start | Size |
|---|---:|---:|
| `compile_world_context()` | 338 | 148 lines |
| `rulebook_rows()` | 237 | 99 lines |
| `classify_movement()` | 158 | 38 lines |
| `_location_query_status()` | 198 | 33 lines |
| `merge_lore()` | 488 | 33 lines |
| `contained_interior_holder()` | 126 | 30 lines |
| `is_contained_destination()` | 95 | 29 lines |
| `_query()` | 68 | 25 lines |

### `agents/narration.py`

| Function | Start | Size |
|---|---:|---:|
| `narrator()` | 1668 | 389 lines |
| `_ordered_beat_events()` | 646 | 230 lines |
| `narrator_extra()` | 2118 | 177 lines |
| `_sensory_channels_manifest()` | 452 | 165 lines |
| `_visible_portal_states()` | 968 | 116 lines |
| `_generate_narration()` | 1510 | 83 lines |
| `_resolve_narration_person()` | 161 | 71 lines |
| `_render_observed_events()` | 1203 | 69 lines |

### `agents/perception.py`

| Function | Start | Size |
|---|---:|---:|
| `_composer_outcome()` | 4848 | 571 lines |
| `perception_outcome()` | 2679 | 291 lines |
| `_composer_standing_percepts()` | 3906 | 240 lines |
| `_composer_act()` | 4410 | 234 lines |
| `perception_act()` | 2225 | 207 lines |
| `_outcome_event_stream()` | 677 | 152 lines |
| `_source_channels()` | 1011 | 139 lines |
| `_scent_sources_for()` | 3626 | 129 lines |

### `agents/runtime.py`

| Function | Start | Size |
|---|---:|---:|
| `_run_pipeline()` | 1034 | 330 lines |
| `build_plan()` | 775 | 109 lines |
| `resume_key_for_turn()` | 682 | 92 lines |
| `_load_extra_players()` | 50 | 74 lines |
| `_stream_one()` | 448 | 68 lines |
| `_stream_parallel()` | 517 | 60 lines |
| `run_pipeline()` | 1415 | 57 lines |
| `_with_engine_notes()` | 388 | 55 lines |

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
| `run_planner()` | 663 | 256 lines |
| `deliberate()` | 1021 | 91 lines |
| `_shown_transcript()` | 359 | 69 lines |
| `schedule_room_work()` | 1203 | 63 lines |
| `_payload()` | 430 | 55 lines |
| `planner_reply()` | 958 | 40 lines |
| `run_dramaturge_pass()` | 1114 | 40 lines |
| `_run_task()` | 921 | 35 lines |

### `core/db.py`

| Function | Start | Size |
|---|---:|---:|
| `_migrate_chat_copies_to_overlays()` | 2102 | 133 lines |
| `init()` | 2393 | 123 lines |
| `_recover_scene_time_of_day()` | 2323 | 59 lines |
| `transaction()` | 1927 | 43 lines |
| `conn()` | 1887 | 38 lines |
| `_opening_time_of_day()` | 2267 | 30 lines |
| `_establish_time_of_day_from_variant()` | 2237 | 28 lines |
| `wset()` | 2572 | 23 lines |

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
| `resolve_ambience()` | 1661 | 221 lines |
| `_rank_candidates()` | 1073 | 105 lines |
| `refine_layers()` | 764 | 89 lines |
| `cached_ambience()` | 482 | 62 lines |
| `search_freesound()` | 1358 | 61 lines |
| `search_local()` | 875 | 54 lines |
| `_query_ladder()` | 1187 | 51 lines |
| `acoustic_fingerprint()` | 260 | 48 lines |

### `dressing/backdrops.py`

| Function | Start | Size |
|---|---:|---:|
| `generate_backdrop()` | 1509 | 115 lines |
| `room_projection()` | 857 | 79 lines |
| `visual_signature()` | 181 | 59 lines |
| `build_backdrop_request()` | 1074 | 52 lines |
| `_brief_sentences()` | 1207 | 51 lines |
| `compose_prompt()` | 1260 | 48 lines |
| `_camera_of()` | 748 | 44 lines |
| `room_brief()` | 811 | 44 lines |

### `llm/llm_quality.py`

| Function | Start | Size |
|---|---:|---:|
| `complete_validated_json()` | 426 | 429 lines |
| `_targeted_field_patch()` | 229 | 63 lines |
| `output_ran_out_of_room()` | 77 | 47 lines |
| `json_failure_diagnosis()` | 126 | 39 lines |
| `_extract_balanced_object()` | 23 | 34 lines |
| `_step_json_schema()` | 395 | 29 lines |
| `_character_wire_schema()` | 370 | 23 lines |
| `strict_json_parse()` | 167 | 19 lines |

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
| `_chat_complete_once()` | 2533 | 323 lines |
| `chat_complete()` | 2246 | 139 lines |
| `async _chat_complete_async_once()` | 3054 | 115 lines |
| `async chat_complete_async()` | 2963 | 90 lines |
| `_sse_openai()` | 2096 | 86 lines |
| `async _sse_openai_async()` | 3170 | 70 lines |
| `_sse_anthropic()` | 2183 | 62 lines |
| `_embed_request()` | 3498 | 59 lines |

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
| `preprocess_llm_output()` | 4420 | 327 lines |
| `_lenient_coerce()` | 769 | 159 lines |
| `validate_llm_output_strict()` | 5557 | 130 lines |
| `semantic_output_errors()` | 5354 | 108 lines |
| `canonicalize_prose_markup()` | 4225 | 102 lines |
| `_uncross_concealed_speech()` | 4349 | 69 lines |
| `_coerce_station_table()` | 85 | 65 lines |
| `_coerce_list_valued_map()` | 152 | 57 lines |

### `mind/affect.py`

| Function | Start | Size |
|---|---:|---:|
| `resolve_affect()` | 810 | 184 lines |
| `apply_intent_ops()` | 1226 | 164 lines |
| `appraise()` | 499 | 145 lines |
| `apply_project_ops()` | 1631 | 137 lines |
| `settle_intent_world_anchors()` | 1452 | 132 lines |
| `normalize_wants()` | 1000 | 89 lines |
| `update_drive_strain()` | 2082 | 86 lines |
| `validate_drive_shift()` | 2211 | 79 lines |

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
| `resolve_stress()` | 349 | 126 lines |
| `apply_belief_updates()` | 578 | 74 lines |
| `apply_association_updates()` | 654 | 49 lines |
| `_authored_beliefs()` | 530 | 46 lines |
| `cognitive_absorption()` | 723 | 45 lines |
| `_within_cap()` | 491 | 29 lines |
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
| `_commit_all_locked()` | 463 | 321 lines |
| `commit_crowds()` | 276 | 149 lines |
| `commit_authored_events()` | 222 | 30 lines |
| `commit_narration_person()` | 190 | 29 lines |
| `_prepare_turn_commit()` | 440 | 12 lines |
| `commit_offscreen_epoch()` | 254 | 11 lines |
| `commit_all()` | 427 | 11 lines |
| `commit_offscreen_plans()` | 267 | 7 lines |

### `persist/commit_attire.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_attire_diff()` | 1008 | 679 lines |
| `interpret_attire_notes()` | 251 | 115 lines |
| `_mint_shed_garments()` | 673 | 102 lines |
| `_fold_duplicate_shed_garments()` | 368 | 85 lines |
| `_reclaim_worn_shed_garments()` | 858 | 82 lines |
| `_fold_worn_garment_entities()` | 455 | 69 lines |
| `_merge_attire_regions()` | 30 | 65 lines |
| `_heal_attire_identity_keys()` | 97 | 61 lines |

### `persist/commit_background.py`

| Function | Start | Size |
|---|---:|---:|
| `track_background_presences()` | 1637 | 788 lines |
| `pick_voice_demand()` | 3230 | 421 lines |
| `promote_background_character()` | 3797 | 344 lines |
| `_fold_duplicate_presences()` | 740 | 143 lines |
| `descriptor_bindings()` | 2855 | 118 lines |
| `auto_promote_background_characters()` | 4180 | 94 lines |
| `addressed_rooms()` | 3141 | 87 lines |
| `_mint_missing_presence_names()` | 1553 | 82 lines |

### `persist/commit_common.py`

| Function | Start | Size |
|---|---:|---:|
| `_names_heard_in()` | 248 | 63 lines |
| `_monotonic_elapsed()` | 72 | 53 lines |
| `_address_forms()` | 155 | 52 lines |
| `_resolve_roster_name()` | 462 | 47 lines |
| `_entity_alias_map()` | 521 | 47 lines |
| `add_engine_notice()` | 607 | 43 lines |
| `charter_recognition_projection()` | 313 | 39 lines |
| `seed_mutual_recognition()` | 427 | 33 lines |

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
| `commit_world_facts()` | 413 | 53 lines |
| `world_pressure_view()` | 198 | 22 lines |
| `_find_obligation()` | 59 | 21 lines |
| `pending_obligation_view()` | 38 | 20 lines |
| `_find_pressure()` | 222 | 18 lines |
| `_beats_open()` | 81 | 9 lines |

### `persist/commit_mapping.py`

| Function | Start | Size |
|---|---:|---:|
| `commit_mapping()` | 529 | 201 lines |
| `_apply_mapping_book_ops()` | 100 | 106 lines |
| `_drop_needs_the_beat_answers()` | 405 | 83 lines |
| `prepare_mapping_commit()` | 208 | 62 lines |
| `_answering_bodies()` | 352 | 51 lines |
| `_setting_fact_needs()` | 272 | 47 lines |
| `_attach_committed_surface()` | 490 | 37 lines |
| `_file_engine_provenance()` | 70 | 28 lines |

### `persist/commit_mechanics.py`

| Function | Start | Size |
|---|---:|---:|
| `commit_transit_sweep()` | 31 | 228 lines |
| `commit_information_carriers()` | 309 | 76 lines |
| `commit_cast_changes()` | 388 | 51 lines |
| `commit_world_event_spine()` | 261 | 46 lines |

### `persist/commit_memory.py`

| Function | Start | Size |
|---|---:|---:|
| `prepare_memory_commit()` | 436 | 1396 lines |
| `_cited_memory_ids()` | 80 | 76 lines |
| `_interior_relations_of()` | 379 | 55 lines |
| `_own_sequence_memory()` | 254 | 50 lines |
| `_hearer_label()` | 193 | 48 lines |
| `_intent_names_term()` | 338 | 39 lines |
| `_inference_memory_text()` | 306 | 30 lines |
| `_marked_for_memory()` | 158 | 24 lines |

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
| `_prepare_room_registry()` | 246 | 104 lines |
| `prune_dangling_exits()` | 458 | 64 lines |
| `_refresh_relocated_location()` | 402 | 54 lines |
| `_apply_room_renames()` | 76 | 53 lines |
| `_apply_room_registry()` | 352 | 28 lines |
| `_registry_alias_index()` | 53 | 22 lines |
| `sync_room_registry_with_scene()` | 381 | 19 lines |

### `persist/commit_scene_state.py`

| Function | Start | Size |
|---|---:|---:|
| `prepare_scene_commit()` | 1205 | 951 lines |
| `derive_borne_containment()` | 828 | 113 lines |
| `_advance_day_cycle()` | 68 | 111 lines |
| `_fold_duplicate_mints()` | 682 | 110 lines |
| `_place_orphan_mints()` | 1008 | 71 lines |
| `_merge_overlays()` | 539 | 68 lines |
| `sync_anchored_books()` | 197 | 66 lines |
| `_refuse_unheld_transfers()` | 943 | 63 lines |

### `persist/llm_capture.py`

| Function | Start | Size |
|---|---:|---:|
| `record_room_exchange()` | 313 | 46 lines |
| `record_exchange()` | 135 | 41 lines |
| `put_blob()` | 78 | 25 lines |
| `latest_turn_id()` | 269 | 24 lines |
| `_payload_hashes()` | 112 | 21 lines |
| `exchanges_for_turn()` | 178 | 20 lines |
| `prune()` | 200 | 16 lines |
| `room_capture()` | 296 | 15 lines |

### `persist/pipeline_trace.py`

| Function | Start | Size |
|---|---:|---:|
| `export_turn_debug()` | 424 | 148 lines |
| `validate_pipeline_trace()` | 174 | 128 lines |
| `export_pipeline_trace()` | 80 | 92 lines |
| `replay_pipeline_trace()` | 304 | 68 lines |
| `write_pipeline_trace()` | 389 | 25 lines |
| `export_chat_debug()` | 574 | 23 lines |
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
| `advance()` | 2465 | 148 lines |
| `_attributed_scoped()` | 1803 | 139 lines |
| `normalize_regions()` | 534 | 133 lines |
| `garments_named_in()` | 2140 | 126 lines |
| `coerce_diff_shape()` | 1480 | 124 lines |
| `compact_line()` | 3381 | 123 lines |
| `perceptible_region_surfaces()` | 2736 | 100 lines |
| `apply_flat_change()` | 2973 | 100 lines |

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
| `run_couriers()` | 815 | 365 lines |
| `_exchange_stops()` | 593 | 220 lines |
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
| `grant_mandate()` | 297 | 82 lines |
| `_request()` | 194 | 29 lines |
| `expire_mandates()` | 381 | 28 lines |
| `request_open()` | 236 | 27 lines |
| `close_request()` | 411 | 26 lines |
| `renew_mandate()` | 439 | 22 lines |
| `coverage()` | 468 | 16 lines |
| `_most_permissive()` | 512 | 15 lines |

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
| `_package_checks()` | 2512 | 115 lines |
| `_preview_plan_rooms()` | 797 | 107 lines |
| `publish_package()` | 2832 | 84 lines |
| `_reach_warning()` | 2650 | 82 lines |
| `fire_due_clocks()` | 2957 | 77 lines |
| `normalize_package()` | 181 | 74 lines |
| `_world_snapshot()` | 495 | 66 lines |
| `edit_package()` | 370 | 57 lines |

### `story/provenance_text.py`

| Function | Start | Size |
|---|---:|---:|
| `split_engine_provenance()` | 86 | 42 lines |
| `looks_like_engine_provenance()` | 81 | 3 lines |
| `strip_engine_provenance()` | 130 | 3 lines |

### `story/room_bible.py`

| Function | Start | Size |
|---|---:|---:|
| `fold()` | 360 | 52 lines |
| `render_block()` | 281 | 42 lines |
| `add_entry()` | 194 | 40 lines |
| `source_exists()` | 83 | 33 lines |
| `_row()` | 144 | 18 lines |
| `mark_paid()` | 236 | 16 lines |
| `_normalize_entry()` | 122 | 15 lines |
| `_evict()` | 180 | 12 lines |

### `story/room_calls.py`

| Function | Start | Size |
|---|---:|---:|
| `room_call()` | 69 | 39 lines |
| `room_max_tokens()` | 35 | 32 lines |
| `_reasoning()` | 119 | 12 lines |
| `_requested()` | 110 | 7 lines |

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
| `restore_room_messages()` | 515 | 30 lines |
| `normalize_mandate()` | 207 | 26 lines |
| `status()` | 281 | 24 lines |
| `add_message()` | 173 | 23 lines |
| `revoke_mandate()` | 262 | 17 lines |
| `_normalize_request()` | 235 | 15 lines |

### `story/room_frontier.py`

| Function | Start | Size |
|---|---:|---:|
| `frontier_report()` | 103 | 57 lines |
| `rooms_ahead()` | 74 | 27 lines |
| `_player_room()` | 53 | 19 lines |
| `record_spend()` | 199 | 14 lines |
| `fills_this_hour()` | 230 | 14 lines |
| `spend_this_hour()` | 215 | 13 lines |
| `record_fill()` | 181 | 11 lines |
| `record_measure()` | 162 | 8 lines |

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

### `story/room_slice.py`

| Function | Start | Size |
|---|---:|---:|
| `room_slices()` | 421 | 68 lines |
| `_plan_here()` | 374 | 45 lines |
| `room_graph()` | 215 | 41 lines |
| `_things_by_room()` | 328 | 26 lines |
| `room_index()` | 299 | 23 lines |
| `_registry()` | 149 | 21 lines |
| `cast_rooms()` | 278 | 19 lines |
| `group_by_region()` | 181 | 18 lines |

### `story/room_tools.py`

| Function | Start | Size |
|---|---:|---:|
| `_t_inspect_contradictions()` | 792 | 162 lines |
| `_mind_of()` | 1096 | 148 lines |
| `_t_inspect_charters()` | 584 | 83 lines |
| `_t_inspect_config()` | 718 | 67 lines |
| `_t_inspect_rooms()` | 243 | 49 lines |
| `_t_inspect_route()` | 324 | 49 lines |
| `_charter_body_rows()` | 492 | 38 lines |
| `_rooms_named_alike()` | 981 | 38 lines |

### `story/scene.py`

| Function | Start | Size |
|---|---:|---:|
| `active_disguises()` | 583 | 82 lines |
| `normalize_transformed_parts()` | 674 | 60 lines |
| `recent_events_for_observer()` | 1804 | 59 lines |
| `_positive_presented_appearance()` | 871 | 58 lines |
| `awareness_conditions()` | 1200 | 58 lines |
| `normalize_style_guide()` | 2560 | 58 lines |
| `active_transformations()` | 736 | 54 lines |
| `director_context()` | 1864 | 53 lines |

### `web/app.py`

| Function | Start | Size |
|---|---:|---:|
| `turn_branch()` | 5590 | 450 lines |
| `chat_get()` | 3599 | 253 lines |
| `_remap_cp_blob()` | 1029 | 216 lines |
| `bootstrap()` | 1370 | 118 lines |
| `dlg_put()` | 4833 | 98 lines |
| `_stream()` | 675 | 91 lines |
| `chat_add_char()` | 3854 | 91 lines |
| `chat_char_position_put()` | 4530 | 83 lines |

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

### `web/world_routes.py`

| Function | Start | Size |
|---|---:|---:|
| `grid_view()` | 816 | 156 lines |
| `room_entity_patch()` | 1516 | 95 lines |
| `_apply_exits()` | 1180 | 92 lines |
| `_apply_doorway_fields()` | 2204 | 77 lines |
| `map_view()` | 1028 | 73 lines |
| `body_rows()` | 594 | 67 lines |
| `charter_body_station_put()` | 2476 | 64 lines |
| `room_create()` | 1838 | 63 lines |

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
| `members_of()` | 121 | 32 lines |
| `crowd_for()` | 252 | 31 lines |
| `member_noun()` | 184 | 26 lines |
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
| `close_plan()` | 730 | 323 lines |
| `_spread_berths()` | 543 | 84 lines |
| `_ensure_shift_crews()` | 349 | 62 lines |
| `ensure_required_rooms()` | 1083 | 60 lines |
| `narrate_actual_history()` | 1252 | 58 lines |
| `_scale_populations()` | 465 | 51 lines |
| `normalize_featured_residents()` | 634 | 47 lines |
| `resident_service_chronicle()` | 1155 | 47 lines |

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
| `normalize_charter()` | 433 | 395 lines |
| `normalize_body()` | 231 | 131 lines |
| `normalize_post()` | 144 | 45 lines |
| `body_of_an_authored_mind()` | 364 | 45 lines |
| `normalize_body_station()` | 191 | 38 lines |
| `normalize_upkeep()` | 111 | 31 lines |
| `_tags()` | 72 | 15 lines |
| `_string_list()` | 94 | 15 lines |

### `world/charter_move.py`

| Function | Start | Size |
|---|---:|---:|
| `errands()` | 363 | 78 lines |
| `_advance()` | 228 | 57 lines |
| `edge_seconds()` | 111 | 41 lines |
| `_dispatch()` | 194 | 32 lines |
| `walk()` | 443 | 30 lines |
| `place_body()` | 498 | 30 lines |
| `continue_walks()` | 287 | 27 lines |
| `_nearest()` | 338 | 23 lines |

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
| `plan_public_evidence()` | 410 | 132 lines |
| `resolve_target_body()` | 331 | 77 lines |
| `apply_public_evidence()` | 544 | 74 lines |
| `body_receives_evidence()` | 90 | 66 lines |
| `evidence_claim()` | 185 | 40 lines |
| `_bodies_by_role()` | 296 | 33 lines |
| `_post_forms()` | 262 | 32 lines |
| `evidence_phrase()` | 162 | 21 lines |

### `world/charter_ops.py`

| Function | Start | Size |
|---|---:|---:|
| `_check()` | 141 | 40 lines |
| `_transfer()` | 251 | 30 lines |
| `apply_charter_ops()` | 304 | 28 lines |
| `normalize_charter_op()` | 113 | 26 lines |
| `_op_upkeep_fails()` | 218 | 25 lines |
| `_employer_of()` | 97 | 7 lines |
| `_op_depart()` | 288 | 7 lines |
| `_charter_state()` | 90 | 5 lines |

### `world/charter_place.py`

| Function | Start | Size |
|---|---:|---:|
| `charter_placements()` | 198 | 69 lines |
| `resolve_scene_placements()` | 381 | 66 lines |
| `_station_and_facing()` | 150 | 46 lines |
| `_spelling_table()` | 346 | 33 lines |
| `lay_charter_bodies()` | 300 | 29 lines |
| `rooms_in_frame()` | 281 | 17 lines |
| `_dealt_cell()` | 132 | 12 lines |
| `scene_with_charter_bodies()` | 331 | 11 lines |

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
| `hunt_moves()` | 281 | 159 lines |
| `_attack()` | 455 | 146 lines |
| `_tribute()` | 775 | 95 lines |
| `predation_round()` | 603 | 89 lines |
| `run_registry()` | 918 | 60 lines |
| `read_spoor()` | 723 | 48 lines |
| `_scene_figures_at()` | 213 | 38 lines |
| `_company()` | 133 | 29 lines |

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
| `step()` | 426 | 972 lines |
| `_record_coarse_experiences()` | 243 | 160 lines |
| `run()` | 1400 | 78 lines |
| `_remember_experience()` | 155 | 32 lines |
| `_run_private_habits()` | 212 | 29 lines |
| `_social_events()` | 110 | 25 lines |
| `_record_social_experiences()` | 189 | 21 lines |
| `_settle_commitments()` | 405 | 19 lines |

### `world/charter_runtime.py`

| Function | Start | Size |
|---|---:|---:|
| `advance_snapshot()` | 2182 | 191 lines |
| `registry_warnings()` | 1856 | 182 lines |
| `_plan_lived_location()` | 1368 | 181 lines |
| `_prepare_cast_histories()` | 615 | 172 lines |
| `_generate_lived_location()` | 1609 | 154 lines |
| `presence_view()` | 3669 | 114 lines |
| `hearing_for_creatures()` | 2375 | 112 lines |
| `schedule_charter_ticks()` | 2738 | 107 lines |

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
| `walk_route()` | 46 | 39 lines |
| `commons_places()` | 172 | 32 lines |
| `reach_map()` | 133 | 29 lines |
| `_route_on()` | 87 | 25 lines |
| `refresh_reach()` | 114 | 17 lines |
| `travel_rooms()` | 31 | 13 lines |
| `frequented_places()` | 206 | 8 lines |
| `charter_places()` | 164 | 6 lines |

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
| `plant_claim()` | 170 | 33 lines |
| `adjust_stock()` | 205 | 25 lines |
| `open_summons()` | 318 | 25 lines |
| `send_errand()` | 272 | 24 lines |
| `assign_post()` | 124 | 21 lines |
| `charter_shock()` | 250 | 20 lines |
| `harm_body()` | 298 | 18 lines |
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
| `_tick_conditions()` | 824 | 128 lines |
| `read_time_diff()` | 172 | 110 lines |
| `_fire_due_events()` | 468 | 96 lines |
| `mechanics_sweep()` | 1098 | 59 lines |
| `_schedule_new_arrivals()` | 566 | 44 lines |
| `unanswered_hazard_subjects()` | 1042 | 42 lines |
| `time_diff_claims()` | 310 | 31 lines |
| `beat_end_elapsed()` | 343 | 31 lines |

### `world/offscreen.py`

| Function | Start | Size |
|---|---:|---:|
| `land_agent_tick()` | 1993 | 187 lines |
| `advance_epoch()` | 1023 | 122 lines |
| `apply_plan_ops()` | 768 | 120 lines |
| `schedule_agent_ticks()` | 2182 | 118 lines |
| `schedule_profile_ticks()` | 1482 | 112 lines |
| `agent_context()` | 1660 | 109 lines |
| `advance_reactive_plans()` | 936 | 85 lines |
| `profile_summary_record()` | 1228 | 85 lines |

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
| `project_planned_emissions()` | 138 | 61 lines |
| `normalize_plan()` | 79 | 51 lines |
| `settle_rendered_plans()` | 302 | 41 lines |
| `plan_figure()` | 228 | 35 lines |
| `_contradicted_axis()` | 345 | 20 lines |
| `plans_in_view()` | 265 | 17 lines |
| `add_planned_entity()` | 210 | 16 lines |
| `reserved_plans()` | 284 | 16 lines |

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

### `world/regions.py`

| Function | Start | Size |
|---|---:|---:|
| `backfill_regions()` | 508 | 65 lines |
| `inherit_regions()` | 343 | 51 lines |
| `assign_regions()` | 396 | 50 lines |
| `room_pieces()` | 452 | 50 lines |
| `set_region_look()` | 154 | 31 lines |
| `room_region()` | 248 | 25 lines |
| `set_region_name()` | 187 | 24 lines |
| `normalize_regions()` | 77 | 21 lines |

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
| `normalize_barrier()` | 310 | 82 lines |
| `effective_adjacent()` | 642 | 73 lines |
| `neighbor_map()` | 523 | 62 lines |
| `normalize_scene_passages()` | 796 | 51 lines |
| `normalize_scene_barriers()` | 410 | 32 lines |
| `passage_direction()` | 587 | 28 lines |
| `_barrier_against_its_own_name()` | 455 | 27 lines |
| `resolve_edge()` | 770 | 24 lines |

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
| `apply_contact_ops()` | 1350 | 422 lines |
| `_clean_contact()` | 943 | 153 lines |
| `normalize_scene_contacts()` | 1246 | 76 lines |
| `contacts_across_enclosure()` | 1138 | 68 lines |
| `_mirrored_displacements()` | 331 | 50 lines |
| `_unnamed_touch_between_bodies()` | 884 | 47 lines |
| `_endpoint_is_body()` | 572 | 44 lines |
| `contact_thing_label()` | 812 | 42 lines |

### `world/spatial_containment.py`

| Function | Start | Size |
|---|---:|---:|
| `derive_inventory_placements()` | 1259 | 143 lines |
| `materialize_named_stations()` | 2460 | 135 lines |
| `advance_room_transits()` | 2597 | 130 lines |
| `replace_engine_minted_interiors()` | 1960 | 123 lines |
| `mint_transferred_objects()` | 1153 | 104 lines |
| `release_declared_departures()` | 2741 | 97 lines |
| `place_enclosed_bodies()` | 2085 | 95 lines |
| `derive_containment_from_contacts()` | 358 | 90 lines |

### `world/spatial_fov.py`

| Function | Start | Size |
|---|---:|---:|
| `feature_visibility()` | 1292 | 111 lines |
| `_place_anchors()` | 490 | 107 lines |
| `body_cell()` | 712 | 76 lines |
| `body_visibility()` | 1507 | 70 lines |
| `neighbour_feature_visibility()` | 1436 | 69 lines |
| `room_field()` | 1089 | 61 lines |
| `_line()` | 823 | 52 lines |
| `_placed_neighbours()` | 1028 | 49 lines |

### `world/spatial_frames.py`

| Function | Start | Size |
|---|---:|---:|
| `infer_focus()` | 486 | 188 lines |
| `perform_split()` | 852 | 98 lines |
| `infer_threshold_crossings()` | 388 | 96 lines |
| `infer_companion_carry()` | 235 | 88 lines |
| `infer_vehicle_zones()` | 148 | 85 lines |
| `infer_facing()` | 676 | 71 lines |
| `perform_merge()` | 1028 | 69 lines |
| `detect_split()` | 806 | 44 lines |

### `world/spatial_geometry.py`

| Function | Start | Size |
|---|---:|---:|
| `invalidate_transferred_pose_details()` | 1577 | 113 lines |
| `derive_scene_stations()` | 1924 | 104 lines |
| `invalidate_moved_body_place_details()` | 1426 | 102 lines |
| `effective_anchors()` | 301 | 90 lines |
| `spatial_digest()` | 145 | 89 lines |
| `egocentric_frame()` | 57 | 86 lines |
| `invalidate_moved_body_pose_details()` | 1316 | 79 lines |
| `invalidate_contact_bound_poses()` | 1692 | 72 lines |

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
| `room_light()` | 41 | 70 lines |
| `unsourced_light_rooms()` | 148 | 63 lines |
| `light_at()` | 332 | 52 lines |
| `source_light()` | 268 | 51 lines |
| `effective_light()` | 386 | 39 lines |
| `unsourced_light_notices()` | 221 | 34 lines |
| `_declaration_is_the_only_account()` | 121 | 25 lines |
| `_sky_light()` | 113 | 6 lines |

### `world/spatial_light_field.py`

| Function | Start | Size |
|---|---:|---:|
| `light_shape()` | 1000 | 110 lines |
| `light_sources()` | 506 | 77 lines |
| `_bounce()` | 700 | 57 lines |
| `glare_between()` | 940 | 49 lines |
| `_spill()` | 759 | 45 lines |
| `compute_light_field()` | 806 | 43 lines |
| `ambient_floor_word()` | 385 | 41 lines |
| `light_geometry_exists()` | 247 | 33 lines |

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
| `merge_scene_with_diff()` | 1474 | 688 lines |
| `_expire_transient_entity_state()` | 551 | 116 lines |
| `_shield_standing_bearings()` | 833 | 107 lines |
| `_shield_minted_edges()` | 1075 | 95 lines |
| `sync_scene_passages()` | 1337 | 90 lines |
| `_merge_room()` | 154 | 84 lines |
| `apply_following_ops()` | 1258 | 77 lines |
| `_mirror_symmetric_barriers()` | 1004 | 69 lines |

### `world/spatial_orientation.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_scene_bearings()` | 135 | 137 lines |
| `derived_edge_bearings()` | 288 | 71 lines |
| `travel_bearing()` | 115 | 18 lines |
| `relative_bearing()` | 79 | 11 lines |
| `lateral_of()` | 92 | 11 lines |
| `normalize_bearing()` | 47 | 9 lines |
| `normalize_vertical()` | 65 | 8 lines |
| `_find_edge()` | 105 | 8 lines |

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
| `sprint_reach()` | 728 | 170 lines |
| `visible_adjacent_rooms()` | 968 | 153 lines |
| `corridor_sightlines()` | 570 | 101 lines |
| `spatial_rel()` | 265 | 88 lines |
| `_onward_exits()` | 900 | 66 lines |
| `passable_route_next_step()` | 370 | 46 lines |
| `stamp_sight_direction()` | 177 | 45 lines |
| `mutual_one_way_window()` | 133 | 42 lines |

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
| `_hear_level()` | 999 | 164 lines |
| `spatial_rel_between()` | 602 | 94 lines |
| `visual_level_between()` | 793 | 78 lines |
| `_opening_view_cap()` | 717 | 74 lines |
| `scent_level()` | 37 | 56 lines |
| `comms_reachable_rooms()` | 278 | 55 lines |
| `_clean_comms_channel()` | 158 | 53 lines |
| `comms_link()` | 363 | 49 lines |

### `world/spatial_sound_field.py`

| Function | Start | Size |
|---|---:|---:|
| `sound_sources()` | 1089 | 124 lines |
| `sound_shape()` | 2323 | 95 lines |
| `spread()` | 901 | 88 lines |
| `stamp_sound_relation()` | 1690 | 73 lines |
| `room_sound_flood()` | 2114 | 68 lines |
| `distant_sounds()` | 2258 | 59 lines |
| `far_path_gain()` | 1630 | 58 lines |
| `sound_field()` | 1580 | 42 lines |

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
| `apply_transit_dock_edges()` | 290 | 170 lines |
| `sync_entity_interior_rooms()` | 108 | 65 lines |
| `ambient_scope()` | 494 | 29 lines |
| `infer_body_enclosures()` | 202 | 27 lines |
| `_is_body_entity()` | 62 | 26 lines |
| `_interior_entry_room()` | 175 | 25 lines |
| `containment_chain()` | 474 | 19 lines |
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
| `claim_frontier_spaces()` | 1173 | 198 lines |
| `prepare_frontier_expansion()` | 966 | 142 lines |
| `materialize_planned_fringe()` | 423 | 122 lines |
| `mint_frontier()` | 222 | 104 lines |
| `plant_structure()` | 328 | 93 lines |
| `planned_context()` | 897 | 67 lines |
| `planned_room_brief()` | 707 | 62 lines |
| `structure_warnings()` | 1393 | 61 lines |

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
| `tick_vitals()` | 321 | 75 lines |
| `apply_vitals_diff()` | 398 | 41 lines |
| `is_sealed_in()` | 227 | 36 lines |
| `seed_vitals()` | 174 | 23 lines |
| `vitals_facts()` | 441 | 23 lines |
| `_stored_vitals()` | 151 | 21 lines |
| `add_air_denied()` | 281 | 19 lines |
| `set_air_denied()` | 302 | 17 lines |

### `world/weather.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_weather()` | 225 | 84 lines |
| `weather_for_room()` | 491 | 76 lines |
| `advance_weather()` | 721 | 65 lines |
| `weather_depth()` | 418 | 57 lines |
| `weather_words()` | 591 | 54 lines |
| `room_exposure()` | 311 | 43 lines |
| `ground_after()` | 840 | 38 lines |
| `_resolve()` | 192 | 27 lines |

## FastAPI routes

| Method | Path | Handler | Source |
|---|---|---|---|
| GET | `/` | `index()` | `web/app.py:546` |
| PUT | `/api/active_preset` | `set_active()` | `web/app.py:1902` |
| PUT | `/api/affect_habituation` | `set_affect_habituation()` | `web/app.py:2222` |
| PUT | `/api/agent_models` | `put_agent_models()` | `web/app.py:1490` |
| PUT | `/api/ambience` | `put_ambience()` | `web/app.py:1646` |
| GET | `/api/ambience/library` | `ambience_library()` | `web/app.py:6781` |
| GET | `/api/ambience/search` | `ambience_search()` | `web/app.py:6760` |
| PUT | `/api/attire_beneath` | `set_attire_beneath()` | `web/app.py:2241` |
| POST | `/api/auth/login` | `auth_login()` | `web/auth_routes.py:209` |
| POST | `/api/auth/logout` | `auth_logout()` | `web/auth_routes.py:275` |
| POST | `/api/auth/setup` | `auth_setup()` | `web/auth_routes.py:134` |
| GET | `/api/auth/status` | `auth_status()` | `web/auth_routes.py:124` |
| GET | `/api/auto_promote` | `get_auto_promote()` | `web/app.py:4011` |
| PUT | `/api/auto_promote` | `set_auto_promote()` | `web/app.py:4024` |
| PUT | `/api/backdrops` | `put_backdrops()` | `web/app.py:1636` |
| GET | `/api/bootstrap` | `bootstrap()` | `web/app.py:1370` |
| POST | `/api/characters` | `char_create()` | `web/app.py:2697` |
| POST | `/api/characters/generate` | `char_generate()` | `web/app.py:2674` |
| POST | `/api/characters/import` | `char_import()` | `web/app.py:2722` |
| DELETE | `/api/characters/{cid}` | `char_del()` | `web/app.py:2908` |
| PUT | `/api/characters/{cid}` | `char_edit()` | `web/app.py:2898` |
| GET | `/api/characters/{cid}/export` | `char_export()` | `web/app.py:2890` |
| POST | `/api/characters/{cid}/fill_appearance` | `char_fill_appearance()` | `web/app.py:2878` |
| POST | `/api/characters/{cid}/fill_interior` | `char_fill_interior()` | `web/app.py:2836` |
| POST | `/api/characters/{cid}/fill_psychology` | `char_fill_psychology()` | `web/app.py:2803` |
| POST | `/api/characters/{cid}/generate_greeting` | `char_generate_greeting()` | `web/app.py:2787` |
| POST | `/api/characters/{cid}/recover_greetings` | `char_recover_greetings()` | `web/app.py:2777` |
| POST | `/api/characters/{cid}/start` | `character_start_story()` | `web/app.py:2746` |
| POST | `/api/chats` | `chat_new()` | `web/app.py:3345` |
| POST | `/api/chats/import` | `import_chat()` | `persist/chat_archive.py:272` |
| DELETE | `/api/chats/{cid}` | `chat_del()` | `web/app.py:3591` |
| GET | `/api/chats/{cid}` | `chat_get()` | `web/app.py:3599` |
| PUT | `/api/chats/{cid}` | `chat_edit()` | `web/app.py:3443` |
| POST | `/api/chats/{cid}/abort` | `chat_abort()` | `web/app.py:5586` |
| GET | `/api/chats/{cid}/ambience/oneshot/{name}` | `ambience_oneshot()` | `web/app.py:6790` |
| DELETE | `/api/chats/{cid}/ambience/pin` | `ambience_pin_delete()` | `web/app.py:6838` |
| PUT | `/api/chats/{cid}/ambience/pin` | `ambience_pin_put()` | `web/app.py:6819` |
| GET | `/api/chats/{cid}/ambience/pins` | `ambience_pins_get()` | `web/app.py:6814` |
| GET | `/api/chats/{cid}/ambience/{signature}.audio` | `ambience_audio()` | `web/app.py:6744` |
| GET | `/api/chats/{cid}/attire` | `attire_get()` | `web/app.py:4766` |
| PUT | `/api/chats/{cid}/attire` | `attire_put()` | `web/app.py:4777` |
| GET | `/api/chats/{cid}/backdrop/{signature}.png` | `backdrop_image()` | `web/app.py:6584` |
| GET | `/api/chats/{cid}/background_config` | `bg_cfg_get()` | `web/app.py:5077` |
| PUT | `/api/chats/{cid}/background_config` | `bg_cfg_put()` | `web/app.py:5081` |
| DELETE | `/api/chats/{cid}/bodies/{name}` | `body_presence_delete()` | `web/world_routes.py:2064` |
| PUT | `/api/chats/{cid}/bodies/{name}/pose` | `body_pose_put()` | `web/world_routes.py:2149` |
| PUT | `/api/chats/{cid}/bodies/{name}/room` | `body_room_put()` | `web/world_routes.py:2098` |
| PUT | `/api/chats/{cid}/bodies/{name}/station` | `body_station_put()` | `web/world_routes.py:1678` |
| POST | `/api/chats/{cid}/characters` | `chat_add_char()` | `web/app.py:3854` |
| DELETE | `/api/chats/{cid}/characters/{ch}` | `chat_del_char()` | `web/app.py:4303` |
| PUT | `/api/chats/{cid}/characters/{ch}/card` | `chat_char_card_put()` | `web/app.py:4313` |
| PUT | `/api/chats/{cid}/characters/{ch}/dialogue_color` | `dialogue_color_put()` | `web/app.py:4634` |
| POST | `/api/chats/{cid}/characters/{ch}/fill_interior` | `chat_char_fill_interior()` | `web/app.py:2847` |
| GET | `/api/chats/{cid}/characters/{ch}/memories` | `mem_list()` | `web/app.py:5326` |
| POST | `/api/chats/{cid}/characters/{ch}/memories` | `mem_add()` | `web/app.py:5473` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/backfill` | `mem_backfill()` | `web/app.py:5443` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/consolidate` | `mem_consolidate()` | `web/app.py:5428` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/coverage` | `mem_coverage()` | `web/app.py:5464` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/export` | `mem_export()` | `web/app.py:5372` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/import` | `mem_import()` | `web/app.py:5383` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/search` | `mem_search()` | `web/app.py:5347` |
| GET | `/api/chats/{cid}/characters/{ch}/memory-context` | `memory_context_preview()` | `web/app.py:5404` |
| PUT | `/api/chats/{cid}/characters/{ch}/position` | `chat_char_position_put()` | `web/app.py:4530` |
| GET | `/api/chats/{cid}/characters/{ch}/private_history` | `ph_get()` | `web/app.py:4615` |
| PUT | `/api/chats/{cid}/characters/{ch}/private_history` | `ph_put()` | `web/app.py:4625` |
| GET | `/api/chats/{cid}/characters/{ch}/relationships` | `relationships_get()` | `web/app.py:5417` |
| GET | `/api/chats/{cid}/charters` | `charters_get()` | `web/app.py:4968` |
| PUT | `/api/chats/{cid}/charters` | `charters_put()` | `web/app.py:4989` |
| GET | `/api/chats/{cid}/charters/diagnostics` | `charters_diagnostics()` | `web/app.py:5007` |
| POST | `/api/chats/{cid}/charters/generate` | `charters_generate()` | `web/app.py:5019` |
| DELETE | `/api/chats/{cid}/charters/job` | `charters_job_clear()` | `web/app.py:5060` |
| GET | `/api/chats/{cid}/charters/job` | `charters_job_get()` | `web/app.py:5041` |
| DELETE | `/api/chats/{cid}/charters/{charter_key}/bodies/{body_key}/station` | `charter_body_station_delete()` | `web/world_routes.py:2543` |
| PUT | `/api/chats/{cid}/charters/{charter_key}/bodies/{body_key}/station` | `charter_body_station_put()` | `web/world_routes.py:2476` |
| GET | `/api/chats/{cid}/debug` | `chat_debug_export()` | `web/app.py:1865` |
| GET | `/api/chats/{cid}/dialogue_config` | `dlg_get()` | `web/app.py:4816` |
| PUT | `/api/chats/{cid}/dialogue_config` | `dlg_put()` | `web/app.py:4833` |
| POST | `/api/chats/{cid}/doorways` | `doorway_create()` | `web/world_routes.py:2284` |
| DELETE | `/api/chats/{cid}/doorways/{room_id}/{to}` | `doorway_delete()` | `web/world_routes.py:2359` |
| PATCH | `/api/chats/{cid}/doorways/{room_id}/{to}` | `doorway_patch()` | `web/world_routes.py:2323` |
| GET | `/api/chats/{cid}/dramatic_irony` | `get_dramatic_irony_feed()` | `web/app.py:3953` |
| GET | `/api/chats/{cid}/export` | `export_chat()` | `persist/chat_archive.py:266` |
| GET | `/api/chats/{cid}/fixed_points` | `fixed_points_list()` | `web/app.py:5272` |
| POST | `/api/chats/{cid}/fixed_points` | `fixed_points_create()` | `web/app.py:5282` |
| DELETE | `/api/chats/{cid}/fixed_points/{anchor_id}` | `fixed_points_delete()` | `web/app.py:5304` |
| GET | `/api/chats/{cid}/frames` | `frames_list()` | `web/app.py:5226` |
| POST | `/api/chats/{cid}/frames` | `frames_create()` | `web/app.py:5230` |
| GET | `/api/chats/{cid}/guest_invites` | `list_guest_invites()` | `web/app.py:4184` |
| POST | `/api/chats/{cid}/guest_invites` | `create_guest_invite()` | `web/app.py:4164` |
| DELETE | `/api/chats/{cid}/guest_invites/{gid}` | `revoke_guest_invite()` | `web/app.py:4188` |
| GET | `/api/chats/{cid}/language` | `chat_language_get()` | `web/app.py:3410` |
| PUT | `/api/chats/{cid}/language` | `chat_language_put()` | `web/app.py:3427` |
| GET | `/api/chats/{cid}/living_world` | `living_world_get()` | `web/app.py:4933` |
| PUT | `/api/chats/{cid}/living_world` | `living_world_put()` | `web/app.py:4956` |
| DELETE | `/api/chats/{cid}/lorebook` | `detach_lore()` | `web/app.py:3582` |
| POST | `/api/chats/{cid}/lorebook` | `bind_lore()` | `web/app.py:3556` |
| GET | `/api/chats/{cid}/lorebooks` | `chat_lorebooks_owned()` | `web/app.py:2325` |
| POST | `/api/chats/{cid}/lorebooks` | `attach_lore()` | `web/app.py:3474` |
| DELETE | `/api/chats/{cid}/lorebooks/{lid}` | `detach_book()` | `web/app.py:3541` |
| PUT | `/api/chats/{cid}/lorebooks/{lid}` | `set_book_enabled()` | `web/app.py:3505` |
| GET | `/api/chats/{cid}/map` | `map_index()` | `web/world_routes.py:1132` |
| GET | `/api/chats/{cid}/naming_profile` | `naming_profile_get()` | `web/app.py:5107` |
| PUT | `/api/chats/{cid}/naming_profile` | `naming_profile_put()` | `web/app.py:5119` |
| GET | `/api/chats/{cid}/paradox_policy` | `paradox_policy_get()` | `web/app.py:5257` |
| PUT | `/api/chats/{cid}/paradox_policy` | `paradox_policy_put()` | `web/app.py:5261` |
| GET | `/api/chats/{cid}/persona_private_history` | `pph_get()` | `web/app.py:4697` |
| PUT | `/api/chats/{cid}/persona_private_history` | `pph_put()` | `web/app.py:4710` |
| GET | `/api/chats/{cid}/personas` | `chat_list_extra_personas()` | `web/app.py:4029` |
| POST | `/api/chats/{cid}/personas` | `chat_add_persona()` | `web/app.py:4074` |
| DELETE | `/api/chats/{cid}/personas/{pid}` | `chat_del_persona()` | `web/app.py:4100` |
| PUT | `/api/chats/{cid}/personas/{pid}/station` | `chat_persona_station()` | `web/app.py:4039` |
| GET | `/api/chats/{cid}/player_authority` | `player_authority_get()` | `web/app.py:5189` |
| PUT | `/api/chats/{cid}/player_authority` | `player_authority_put()` | `web/app.py:5204` |
| GET | `/api/chats/{cid}/player_view` | `player_view_get()` | `web/app.py:5166` |
| GET | `/api/chats/{cid}/positions` | `chat_positions_get()` | `web/app.py:4463` |
| GET | `/api/chats/{cid}/promises` | `get_promise_ledger()` | `web/app.py:3957` |
| GET | `/api/chats/{cid}/promotable` | `list_promotable_presences()` | `web/app.py:3949` |
| POST | `/api/chats/{cid}/promotions/confirm` | `confirm_promotion()` | `web/app.py:3978` |
| POST | `/api/chats/{cid}/promotions/draft` | `draft_promotion()` | `web/app.py:3961` |
| POST | `/api/chats/{cid}/regions` | `region_create()` | `web/world_routes.py:2392` |
| PATCH | `/api/chats/{cid}/regions/{region_id}` | `region_patch()` | `web/world_routes.py:1617` |
| GET | `/api/chats/{cid}/room` | `room_thread()` | `web/room_routes.py:52` |
| POST | `/api/chats/{cid}/room/mandates/{uid}/revoke` | `room_revoke()` | `web/room_routes.py:108` |
| POST | `/api/chats/{cid}/room/messages` | `room_say()` | `web/room_routes.py:65` |
| POST | `/api/chats/{cid}/room/messages/stream` | `room_say_stream()` | `web/room_routes.py:78` |
| GET | `/api/chats/{cid}/room/status` | `room_status()` | `web/room_routes.py:117` |
| GET | `/api/chats/{cid}/rooms` | `rooms_index()` | `web/world_routes.py:664` |
| POST | `/api/chats/{cid}/rooms` | `room_create()` | `web/world_routes.py:1838` |
| DELETE | `/api/chats/{cid}/rooms/{room_id}` | `room_delete()` | `web/world_routes.py:1904` |
| GET | `/api/chats/{cid}/rooms/{room_id}` | `rooms_slice()` | `web/world_routes.py:790` |
| PATCH | `/api/chats/{cid}/rooms/{room_id}` | `room_patch()` | `web/world_routes.py:1464` |
| POST | `/api/chats/{cid}/rooms/{room_id}/entities` | `room_entity_create()` | `web/world_routes.py:1943` |
| DELETE | `/api/chats/{cid}/rooms/{room_id}/entities/{entity_id}` | `room_entity_delete()` | `web/world_routes.py:1979` |
| PATCH | `/api/chats/{cid}/rooms/{room_id}/entities/{entity_id}` | `room_entity_patch()` | `web/world_routes.py:1516` |
| GET | `/api/chats/{cid}/rooms/{room_id}/grid` | `rooms_grid()` | `web/world_routes.py:1104` |
| POST | `/api/chats/{cid}/rooms/{room_id}/presences` | `room_presence_create()` | `web/world_routes.py:2024` |
| GET | `/api/chats/{cid}/story_view` | `story_view_get()` | `web/app.py:5132` |
| GET | `/api/chats/{cid}/style_guide` | `style_guide_get()` | `web/app.py:4799` |
| PUT | `/api/chats/{cid}/style_guide` | `style_guide_put()` | `web/app.py:4805` |
| GET | `/api/chats/{cid}/survival` | `survival_get()` | `web/app.py:4371` |
| PUT | `/api/chats/{cid}/survival` | `survival_put()` | `web/app.py:4376` |
| POST | `/api/chats/{cid}/turns` | `turn_new()` | `web/app.py:5526` |
| POST | `/api/chats/{cid}/turns/{idx}/player_input` | `submit_extra_player_input()` | `web/app.py:4114` |
| GET | `/api/chats/{cid}/viewers` | `viewers_get()` | `web/app.py:5181` |
| GET | `/api/chats/{cid}/vitals` | `chat_vitals_get()` | `web/app.py:4428` |
| GET | `/api/chats/{cid}/world` | `world_get()` | `web/app.py:4715` |
| PUT | `/api/chats/{cid}/world` | `world_put()` | `web/app.py:4725` |
| PUT | `/api/debug_capture` | `put_debug_capture()` | `web/app.py:1601` |
| GET | `/api/default_prompts` | `default_prompts()` | `web/app.py:1801` |
| PUT | `/api/director_fanout_mode` | `set_director_fanout_mode()` | `web/app.py:2198` |
| PUT | `/api/exemplars` | `put_exemplars()` | `web/app.py:1570` |
| GET | `/api/extensions` | `extensions_list()` | `web/app.py:1919` |
| POST | `/api/extensions/install` | `extension_install()` | `web/app.py:1941` |
| GET | `/api/extensions/ui.css` | `extensions_ui_css()` | `web/app.py:2119` |
| GET | `/api/extensions/ui.js` | `extensions_ui()` | `web/app.py:2110` |
| GET | `/api/extensions/updates` | `extension_updates()` | `web/app.py:1962` |
| DELETE | `/api/extensions/{eid}` | `extension_remove()` | `web/app.py:1983` |
| GET | `/api/extensions/{eid}/asset/{path:path}` | `extension_asset()` | `web/app.py:2174` |
| POST | `/api/extensions/{eid}/disable` | `extension_disable()` | `web/app.py:1991` |
| DELETE | `/api/extensions/{eid}/document` | `extension_document_delete()` | `web/app.py:2087` |
| GET | `/api/extensions/{eid}/document` | `extension_document_get()` | `web/app.py:2055` |
| PUT | `/api/extensions/{eid}/document` | `extension_document_put()` | `web/app.py:2067` |
| DELETE | `/api/extensions/{eid}/documents` | `extension_documents_delete()` | `web/app.py:2097` |
| GET | `/api/extensions/{eid}/documents` | `extension_documents_list()` | `web/app.py:2034` |
| GET | `/api/extensions/{eid}/documents/verify` | `extension_documents_verify()` | `web/app.py:2045` |
| POST | `/api/extensions/{eid}/enable` | `extension_enable()` | `web/app.py:1933` |
| GET | `/api/extensions/{eid}/state` | `extension_state()` | `web/app.py:1996` |
| GET | `/api/extensions/{eid}/ui.css` | `extension_ui_css_one()` | `web/app.py:2141` |
| GET | `/api/extensions/{eid}/ui.js` | `extension_ui_one()` | `web/app.py:2129` |
| POST | `/api/extensions/{eid}/update` | `extension_update()` | `web/app.py:1973` |
| POST | `/api/guest/input` | `guest_input()` | `web/app.py:4278` |
| GET | `/api/guest/state` | `guest_state()` | `web/app.py:4210` |
| PUT | `/api/image_model` | `put_image_model()` | `web/app.py:1548` |
| POST | `/api/join` | `join_with_code()` | `web/app.py:4194` |
| GET | `/api/language-packs` | `language_packs_get()` | `web/app.py:3363` |
| GET | `/api/language-packs/{language_id}/ui` | `language_pack_ui()` | `web/app.py:3384` |
| DELETE | `/api/lore_entries/{eid}` | `lore_entry_delete()` | `web/app.py:3320` |
| PUT | `/api/lore_entries/{eid}` | `lore_entry_edit()` | `web/app.py:3244` |
| DELETE | `/api/lore_entries/{eid}/overlay` | `lore_entry_overlay_clear()` | `web/app.py:3332` |
| DELETE | `/api/lore_gen_jobs/{job_id}` | `lorebook_generate_discard()` | `web/app.py:2481` |
| POST | `/api/lore_gen_jobs/{job_id}/resume` | `lorebook_generate_resume()` | `web/app.py:2463` |
| DELETE | `/api/lorebook_links/{link_id}` | `lorebook_link_delete()` | `web/app.py:2421` |
| PUT | `/api/lorebook_links/{link_id}` | `lorebook_link_update()` | `web/app.py:2407` |
| POST | `/api/lorebooks` | `lore_create()` | `web/app.py:3019` |
| POST | `/api/lorebooks/import` | `lore_import()` | `web/app.py:2517` |
| DELETE | `/api/lorebooks/{lid}` | `lore_delete()` | `web/app.py:3111` |
| GET | `/api/lorebooks/{lid}` | `lore_get()` | `web/app.py:2995` |
| PUT | `/api/lorebooks/{lid}` | `lore_edit()` | `web/app.py:3041` |
| POST | `/api/lorebooks/{lid}/apply_plan` | `lorebook_apply_plan()` | `web/app.py:2490` |
| POST | `/api/lorebooks/{lid}/entries` | `lore_entry_create()` | `web/app.py:3161` |
| GET | `/api/lorebooks/{lid}/export` | `lore_export()` | `web/app.py:3117` |
| POST | `/api/lorebooks/{lid}/generate` | `lore_generate()` | `web/app.py:3147` |
| GET | `/api/lorebooks/{lid}/generate_job` | `lorebook_generate_job()` | `web/app.py:2452` |
| POST | `/api/lorebooks/{lid}/generate_plan` | `lorebook_generate_plan()` | `web/app.py:2426` |
| GET | `/api/lorebooks/{lid}/links` | `lorebook_links_get()` | `web/app.py:2380` |
| POST | `/api/lorebooks/{lid}/links` | `lorebook_link_create()` | `web/app.py:2385` |
| POST | `/api/lorebooks/{lid}/move` | `lorebook_move()` | `web/app.py:2307` |
| POST | `/api/lorebooks/{lid}/reinterpret` | `lore_reinterpret_route()` | `web/app.py:3134` |
| POST | `/api/lorebooks/{lid}/reorder` | `lorebook_reorder()` | `web/app.py:2316` |
| GET | `/api/maintenance/checkpoints` | `maintenance_checkpoints()` | `web/app.py:2264` |
| POST | `/api/maintenance/checkpoints/compact` | `maintenance_compact()` | `web/app.py:2280` |
| PUT | `/api/max_output_tokens` | `put_max_output_tokens()` | `web/app.py:1768` |
| DELETE | `/api/memories/{mid}` | `mem_del()` | `web/app.py:5520` |
| PUT | `/api/memories/{mid}` | `mem_edit()` | `web/app.py:5499` |
| GET | `/api/memory/embeddings` | `memory_embeddings_status()` | `web/app.py:1521` |
| POST | `/api/memory/embeddings/rebuild` | `memory_embeddings_rebuild()` | `web/app.py:1536` |
| GET | `/api/nsfw` | `get_nsfw()` | `web/app.py:2189` |
| PUT | `/api/nsfw` | `set_nsfw()` | `web/app.py:2193` |
| GET | `/api/openrouter/endpoints` | `get_openrouter_endpoints()` | `web/app.py:1726` |
| PUT | `/api/openrouter_routing` | `put_openrouter_routing()` | `web/app.py:1712` |
| POST | `/api/personas` | `persona_create()` | `web/app.py:2937` |
| POST | `/api/personas/generate` | `persona_generate()` | `web/app.py:2915` |
| POST | `/api/personas/import` | `persona_import()` | `web/app.py:2957` |
| DELETE | `/api/personas/{pid}` | `persona_del()` | `web/app.py:2989` |
| PUT | `/api/personas/{pid}` | `persona_edit()` | `web/app.py:2980` |
| GET | `/api/personas/{pid}/export` | `persona_export()` | `web/app.py:2971` |
| POST | `/api/personas/{pid}/fill_appearance` | `persona_fill_appearance()` | `web/app.py:2885` |
| PUT | `/api/prompt_presets` | `save_preset()` | `web/app.py:1812` |
| POST | `/api/prompt_presets/import` | `import_preset()` | `web/app.py:1879` |
| DELETE | `/api/prompt_presets/{name}` | `del_preset()` | `web/app.py:1893` |
| GET | `/api/prompt_presets/{name}/export` | `export_preset()` | `web/app.py:1839` |
| POST | `/api/providers` | `add_provider()` | `web/app.py:2573` |
| DELETE | `/api/providers/{pid}` | `del_provider()` | `web/app.py:2652` |
| PUT | `/api/providers/{pid}` | `put_provider()` | `web/app.py:2580` |
| GET | `/api/providers/{pid}/image_models` | `image_models()` | `web/app.py:2664` |
| GET | `/api/providers/{pid}/models` | `models()` | `web/app.py:2657` |
| PUT | `/api/providers/{pid}/prompt_cache` | `put_provider_prompt_cache()` | `web/app.py:2607` |
| PUT | `/api/reasoning_effort` | `put_reasoning_effort()` | `web/app.py:1738` |
| GET | `/api/research` | `get_research()` | `web/app.py:1687` |
| PUT | `/api/research` | `put_research()` | `web/app.py:1692` |
| POST | `/api/steps/{sid}/activate` | `step_activate()` | `web/app.py:6390` |
| POST | `/api/steps/{sid}/edit` | `step_edit()` | `web/app.py:6379` |
| POST | `/api/steps/{sid}/reroll` | `step_reroll()` | `web/app.py:6310` |
| DELETE | `/api/turns/{tid}` | `turn_del()` | `web/app.py:6404` |
| GET | `/api/turns/{tid}/ambience` | `turn_ambience()` | `web/app.py:6694` |
| POST | `/api/turns/{tid}/ambience` | `turn_ambience_resolve()` | `web/app.py:6711` |
| GET | `/api/turns/{tid}/backdrop` | `turn_backdrop()` | `web/app.py:6541` |
| POST | `/api/turns/{tid}/backdrop` | `turn_backdrop_generate()` | `web/app.py:6556` |
| POST | `/api/turns/{tid}/branch` | `turn_branch()` | `web/app.py:5590` |
| PUT | `/api/turns/{tid}/input` | `edit_input()` | `web/app.py:6042` |
| GET | `/api/turns/{tid}/narration` | `turn_narration_variants()` | `web/app.py:6127` |
| POST | `/api/turns/{tid}/narration` | `turn_narration_select()` | `web/app.py:6148` |
| GET | `/api/turns/{tid}/pipeline` | `pipeline_get()` | `web/app.py:6172` |
| PUT | `/api/turns/{tid}/prose` | `edit_prose()` | `web/app.py:6057` |
| POST | `/api/turns/{tid}/reroll` | `turn_reroll()` | `web/app.py:6241` |
| POST | `/api/turns/{tid}/rerun` | `turn_rerun()` | `web/app.py:6251` |
| POST | `/api/turns/{tid}/resume` | `turn_resume()` | `web/app.py:6278` |
| GET | `/api/turns/{turn_id}/debug` | `turn_debug_export()` | `web/app.py:1848` |
| GET | `/api/ui` | `ui_catalog_get()` | `web/app.py:3374` |
| PUT | `/api/ui-language` | `ui_language_put()` | `web/app.py:3399` |
| GET | `/api/updates/check` | `updates_check()` | `web/app.py:2256` |
| POST | `/api/updates/install` | `updates_install()` | `web/app.py:2260` |
| GET | `/guest` | `guest_page()` | `web/app.py:538` |
| GET | `/login` | `login_page()` | `web/app.py:556` |

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

### `static/js/settings.js` (4042 lines)

Sections: Chat tool modals (`:1`); Condition tab (`:857`); Survival tracker (`:917`); Character relocation (`:1229`); API connections (`:1962`); Software updates (host-only; git fast-forward from GitHub origin) (`:3271`); Legacy checkpoint conversion (host-only maintenance) (`:3303`); Prompts (`:3537`); and be able to load that pack's own sheets to edit, rather than (`:3548`); Extensions (`:3715`).

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

### `static/js/world_browser.js` (3269 lines)

Sections: The World Browser (`:3`); with its room, station, pose, and its FULL attire ledger, (`:31`); Edit controls (`:108`); The tree (`:165`); The room card (`:245`); Townspeople (2026-09-05, DESIGN_CHARTER_PLACEMENT § the map) (`:368`); `size` is the word for the floor and `extent` its measurement, so the (`:495`); The Bodies tab: every body, and the attire editor (`:1211`); The Raw JSON tab: the two editors, unchanged (`:1484`); The map editor (`:1525`); the neighbours, faintly, where the field lays them (`:1830`); the room's cells, and the overlay's tint over them (`:1871`); the boundary as a line, with each doorway a gap in it (`:1904`); anchors: footprint cells, the id, a height mark (`:1951`); things placed by a position and a station (`:1986`); bodies: a marked cell with a facing tick; the unstationed in a lane (`:2024`); the lint, drawn at the thing each row concerns (`:2080`); the shape: parts as rectangles, the box's sides as handles (`:2136`); blank wall segments open a doorway; empty floor places a thing (`:2193`); the drops (`:2217`); through the doorways route, so a doorway declared from the far room (`:2328`); The dialog (`:2710`).

Declared functions: `wbStatusBadge()`, `wbRoomLabel()`, `wbSelect()`, `wbText()`, `wbWrite()`, `wbRenderTree()`, `wbSection()`, `wbIndexRows()`, `wbCellOf()`, `wbCellText()`, `wbStationText()`, `wbPoseText()`, `wbMoveControl()`, `wbNumber()`, `wbBodyMove()`, `wbCharterUrl()`, `wbCharterStationBody()`, `wbSourceWord()`, `wbCharterWhere()`, `wbCharterRow()`, `wbPoseEditor()`, `wbLintRows()`, `wbRoomFields()`, `wbRegionLook()`, `wbExits()`, `wbAnchors()`, `wbOccupant()`, `wbThing()`, `wbRenderCard()`, `wbGroupGarments()`, `wbLedgerEntry()`, `wbAttireEditor()`, `wbBodyKind()`, `wbCharterDetails()`, `wbRenderBodies()`, `wbRenderRaw()`, `wbSvg()`, `wbSvgPoint()`, `wbDraggable()`, `wbUndoStack()`, `wbWallOf()`, `wbOffsetAlong()`, `wbBearingBetween()`, `wbActivatable()`, `wbBoundary()`, `wbFocusRow()`, `wbFootprintLength()`, `wbRenderRoomMap()`, `centre()`, `partBox()`, `writeParts()`, `movePart()`, `dropPart()`, `sizePart()`, `resizePart()`, `writeExtent()`, `dropHandle()`, `nudgeHandle()`, `writeAnchors()`, `dropAnchor()`, `dropDoorway()`, `dropBody()`, `dropCharter()`, `dropThing()`, `wbRenderStructureMap()`, `wbRegionLegend()`, `wbMarksLegend()`, `wbMapPane()`, `wbWallForm()`, `wbCellForm()`, `wbMapNotes()`, `wbMapLegend()`, `openWorldBrowser()`, `moveRoute()`, `renderMapBar()`, `drawGrid()`, `loadGrid()`, `showStructure()`, `refreshIndex()`, `loadCard()`, `loadRoom()`, `selectTab()`.

### `static/js/writers_room.js` (700 lines)

Sections: The Writers' Room panel (`:3`); bd-panel for this element alone. (`:20`); Named limits (`:33`); Shape: docked / floating / closed (`:148`); Loading (`:205`); Sending (`:274`); The stream (`:307`); Rendering (`:382`); Building the panel (`:576`); Boot (`:689`).

Declared functions: `roomCls()`, `roomStoreGet()`, `roomStoreSet()`, `roomRestorePrefs()`, `roomClampWidth()`, `roomClampOpacity()`, `roomClampGeometry()`, `roomApplyShape()`, `roomOpen()`, `roomSetMode()`, `roomKey()`, `roomFrameQuery()`, `roomLoad()`, `roomLoadEarlier()`, `roomStartWatch()`, `roomStopWatch()`, `roomSend()`, `roomStream()`, `roomEvent()`, `roomRevoke()`, `roomRender()`, `roomRenderStatus()`, `roomRenderMandates()`, `roomRenderThread()`, `roomRenderCitations()`, `roomLiveNode()`, `roomBuild()`, `roomWireDrag()`, `track()`.
