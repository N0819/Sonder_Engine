# Generated Code Map

> Regenerate with `python tools/generate_code_map.py`. Do not hand-edit this file.

## Python modules

| Module | Lines | Purpose | Local dependencies |
|---|---:|---|---|
| `agents/__init__.py` | 96 | Backward-compatible facade for the role-specific agent package. | `agents.background`, `agents.character`, `agents.common`, `agents.director`, `agents.loops`, `agents.mapping`, `agents.narration`, `agents.perception`, `agents.runtime`, `agents.storage`, `story.scene` |
| `agents/background.py` | 1412 |  | `agents.common`, `core.db`, `llm.prompts`, `llm.schemas`, `persist.commit`, `story.character_schema`, `story.scene`, `world.background_claims`, `world.spatial` |
| `agents/character.py` | 3733 | Private character decision agent. | `agents.common`, `core.db`, `core.frames`, `llm.prompts`, `llm.schemas`, `mind`, `mind.affect`, `mind.memory`, `mind.memory_judge`, `mind.psychology_runtime`, `mind.theory_of_mind`, `story.character_schema`, `story.scene`, `world.gaps`, `world.place_purpose`, `world.spatial`, `world.survival` |
| `agents/common.py` | 8551 | Shared normalization, lore, delivery, and perception helpers. | `core.db`, `core.pipeline_context`, `llm.llm_quality`, `llm.prompts`, `llm.providers`, `llm.schemas`, `mind.memory`, `mind.theory_of_mind`, `persist.commit`, `story`, `story.character_schema`, `story.provenance_text`, `story.scene`, `world`, `world.spatial` |
| `agents/composer.py` | 3140 |  | `agents.common`, `story.provenance_text`, `story.scene`, `world.spatial` |
| `agents/director.py` | 4125 | Scene establishment, player interpretation, and objective resolution. | `agents.common`, `agents.director_contact`, `agents.director_evidence`, `agents.director_fanout`, `agents.director_floors`, `agents.director_lingua`, `agents.director_movement`, `agents.director_reconcile`, `agents.director_scopes`, `agents.director_views`, `core.db`, `llm`, `llm.prompts`, `llm.providers`, `llm.schemas`, `mind.memory`, `story`, `story.attire`, `story.character_schema`, `story.scene`, `world.paradox`, `world.spatial`, `world.survival` |
| `agents/director_contact.py` | 457 |  | `story.character_schema`, `world.spatial` |
| `agents/director_evidence.py` | 1044 |  | `agents.common`, `agents.director_lingua`, `llm`, `world.spatial` |
| `agents/director_fanout.py` | 660 |  | `agents.common`, `agents.director_evidence`, `agents.director_scopes`, `core.db`, `story.character_schema`, `world.spatial`, `world.survival` |
| `agents/director_floors.py` | 1355 |  | `agents.common`, `agents.director_lingua`, `story.character_schema`, `story.scene`, `world.mechanics`, `world.spatial` |
| `agents/director_lingua.py` | 29 |  | — |
| `agents/director_movement.py` | 969 |  | `agents.director_lingua`, `story.character_schema`, `world.spatial` |
| `agents/director_reconcile.py` | 592 |  | `agents.common`, `agents.director_evidence`, `agents.director_scopes`, `core.db`, `story`, `world.spatial` |
| `agents/director_scopes.py` | 673 |  | `agents.director_views`, `core.db`, `world.survival` |
| `agents/director_views.py` | 627 |  | `agents.common`, `story.character_schema`, `story.scene`, `world.background_claims` |
| `agents/loops.py` | 1245 | Reaction loops, interaction rounds, and deterministic micro-perception. | `agents.character`, `agents.common`, `core.db`, `story.character_schema`, `story.scene`, `world.spatial` |
| `agents/mapping.py` | 337 | Lore routing, cached recall, and retrieval staging. | `agents.common`, `core.db`, `llm.prompts`, `mind.memory`, `story.character_schema`, `story.scene` |
| `agents/narration.py` | 1853 | Player-facing narration agent. | `agents`, `agents.common`, `core.db`, `llm.prompts`, `llm.schemas`, `story.character_schema`, `story.scene`, `world.spatial`, `world.weather` |
| `agents/perception.py` | 4479 | Opening, action-onset, and outcome observer views. | `agents`, `agents.common`, `core.db`, `mind`, `story.character_schema`, `story.scene`, `world.mechanics`, `world.spatial` |
| `agents/runtime.py` | 1355 | Pipeline plans, dispatch, streaming, cancellation, resume, and reruns. | `agents.background`, `agents.character`, `agents.common`, `agents.director`, `agents.loops`, `agents.mapping`, `agents.narration`, `agents.perception`, `agents.storage`, `core.db`, `core.pipeline_context`, `llm.providers`, `persist.checkpoints`, `persist.commit`, `story.character_schema`, `story.scene` |
| `agents/storage.py` | 123 | Step and active-variant persistence helpers. | `core.db` |
| `core/__init__.py` | 6 |  | — |
| `core/db.py` | 2319 | SQLite schema, migrations, connection management, transactions, and key/value world access. | `core.paths` |
| `core/frames.py` | 220 |  | `core.db` |
| `core/jobs.py` | 308 |  | `core.logging_utils` |
| `core/logging_utils.py` | 45 | Structured timing and observability helpers. | — |
| `core/outofband.py` | 392 |  | `core.logging_utils` |
| `core/paths.py` | 32 |  | — |
| `core/pipeline_context.py` | 343 | Typed mutable context passed through a turn pipeline. | `core.db` |
| `core/updates.py` | 399 |  | `core.paths` |
| `dressing/__init__.py` | 6 |  | — |
| `dressing/ambience.py` | 2064 |  | `core`, `core.db`, `core.paths`, `dressing.backdrops`, `world.weather` |
| `dressing/backdrops.py` | 1319 |  | `core`, `core.db`, `core.logging_utils`, `core.paths`, `world.spatial`, `world.weather` |
| `llm/__init__.py` | 6 |  | — |
| `llm/llm_quality.py` | 755 | Strict JSON parsing, schema validation, and model-assisted repair. | `core.pipeline_context`, `llm.prompts`, `llm.providers`, `llm.schemas` |
| `llm/prompt_cache.py` | 79 | Provider-specific prompt-cache helpers. | `llm.providers` |
| `llm/prompts.py` | 494 | Default system prompts and prompt preset access. | `core.db` |
| `llm/providers.py` | 3439 | Provider selection, retries, streaming, cancellation, model listing, and embeddings. | `core.db`, `core.logging_utils` |
| `llm/schemas.py` | 5598 | Pydantic output contracts and semantic validation for agent payloads. | — |
| `mind/__init__.py` | 6 |  | — |
| `mind/affect.py` | 2406 |  | `mind.theory_of_mind` |
| `mind/canon_provenance.py` | 379 |  | — |
| `mind/memory.py` | 134 | Facade re-exporting every mind.memory_* name; holds no domain code of its own. | `core`, `core.db`, `core.logging_utils`, `llm.prompts`, `llm.providers`, `mind.memory_common`, `mind.memory_context`, `mind.memory_inference`, `mind.memory_lore_entries`, `mind.memory_lorebooks`, `mind.memory_read`, `mind.memory_relationships`, `mind.memory_retrieval`, `mind.memory_snapshot`, `mind.memory_summaries`, `mind.memory_time`, `mind.memory_vectors`, `mind.memory_write`, `mind.theory_of_mind` |
| `mind/memory_common.py` | 229 | Leaf helpers shared by every memory domain: vocabularies, blob/vector codecs, FTS query, cosine. | `core.db` |
| `mind/memory_context.py` | 635 | The character memory payload: where retrieval, summaries and active state become one context. | `core.db`, `llm.prompts`, `llm.providers`, `mind.memory_common`, `mind.memory_retrieval`, `mind.memory_summaries`, `mind.memory_time`, `mind.memory_write` |
| `mind/memory_inference.py` | 154 | Belief confidence at mint and at abandonment, and reconciliation across a mind's inferences. | `core.db`, `mind.memory_write`, `mind.theory_of_mind` |
| `mind/memory_judge.py` | 430 |  | `core.db`, `core.logging_utils`, `llm.prompts`, `llm.providers` |
| `mind/memory_lore_entries.py` | 645 | Lore entries: add/update/delete, embedding stamps and health, search_lore, per-character knowledge scoping. | `core.db`, `core.logging_utils`, `llm.providers`, `mind.memory_common`, `mind.memory_lorebooks`, `mind.memory_write` |
| `mind/memory_lorebooks.py` | 574 | The lorebook graph: hierarchy, links, inheritance modes, per-chat attachment and weights. | `core.db`, `core.logging_utils`, `mind.memory_common` |
| `mind/memory_read.py` | 374 | The one seam a mind reads its own memory through, and the host reads that deliberately cross characters. | `core`, `core.db`, `mind.memory_common`, `mind.memory_write` |
| `mind/memory_relationships.py` | 241 | The relationship graph: axis deltas from conduct and from inference, and the history behind them. | `core.db`, `mind.memory_common`, `mind.memory_write` |
| `mind/memory_retrieval.py` | 1147 | Hybrid retrieval: lexical and vector rankings fused by RRF, tilted by mood and importance, plus unbidden recall. | `core.db`, `core.logging_utils`, `llm.providers`, `mind.memory_common`, `mind.memory_read`, `mind.memory_write` |
| `mind/memory_snapshot.py` | 733 | Checkpoint and archive: vector addressing, the prepare/apply restore split, memory and lorebook dump/restore. | `core.db`, `llm.providers`, `mind.memory_common`, `mind.memory_lore_entries`, `mind.memory_summaries`, `mind.memory_write` |
| `mind/memory_summaries.py` | 699 | Autobiographical, hearsay and surmise summaries: search, support sets, windowed consolidation and backfill. | `core.db`, `llm.prompts`, `llm.providers`, `mind.memory_common`, `mind.memory_read`, `mind.memory_retrieval`, `mind.memory_write` |
| `mind/memory_time.py` | 332 |  | `core.db` |
| `mind/memory_vectors.py` | 772 | Rebuilding vectors after the embedding model changes: bank status, the rebuild, and its background run. | `core.db`, `core.logging_utils`, `llm.providers`, `mind.memory_common`, `mind.memory_retrieval`, `mind.memory_write` |
| `mind/memory_write.py` | 829 | How a memory becomes a row: normalisation, extraction, FTS mirror, the upsert, and the embedding-repair thread. | `core.db`, `core.logging_utils`, `llm.providers`, `mind.memory_common` |
| `mind/psychology_runtime.py` | 636 |  | — |
| `mind/theory_of_mind.py` | 725 |  | — |
| `persist/__init__.py` | 6 |  | — |
| `persist/chat_archive.py` | 1195 | Typed, atomic chat archive export/import service and HTTP routes. | `core.db`, `llm.schemas`, `mind.memory`, `persist.checkpoints`, `story.character_schema` |
| `persist/chat_delete.py` | 42 |  | `core.db` |
| `persist/checkpoints.py` | 1350 | Whole-chat snapshots and checkpoint restore orchestration. | `core.db`, `mind.memory` |
| `persist/commit.py` | 714 | Atomic commit orchestrator, per-turn lock, thin tail domains, and the facade re-exporting every commit_* name. | `core.db`, `core.frames`, `llm.prompts`, `llm.providers`, `mind`, `mind.memory`, `mind.theory_of_mind`, `persist.commit_attire`, `persist.commit_background`, `persist.commit_common`, `persist.commit_destruction`, `persist.commit_entities`, `persist.commit_ledgers`, `persist.commit_mapping`, `persist.commit_mechanics`, `persist.commit_memory`, `persist.commit_memory_write`, `persist.commit_place_graph`, `persist.commit_room_registry`, `persist.commit_scene_state`, `story`, `story.character_schema`, `story.scene`, `world.comfort`, `world.mechanics`, `world.paradox`, `world.spatial`, `world.spatial_frames`, `world.survival`, `world.weather` |
| `persist/commit_attire.py` | 1332 | The mutable clothing ledger: attire notes, shed/worn garment entities, the validated attire diff. | `persist.commit_common`, `story`, `story.attire` |
| `persist/commit_background.py` | 3206 | Background presences: tracking, identity folding, the reactor gate, promotion to cast. | `core.db`, `mind.memory`, `persist.commit_common`, `story.character_schema`, `story.scene`, `world.spatial` |
| `persist/commit_common.py` | 527 | Leaf helpers shared across commit domains: scalar utilities, name/address roster, entity-id canonicalisation. | `core.db`, `mind.memory`, `story.character_schema`, `world.mechanics`, `world.spatial` |
| `persist/commit_destruction.py` | 411 | Single- and multi-book destruction cascades, retirement, and latency-gated news. | `core.db`, `mind.memory`, `persist.commit_common`, `world.mechanics`, `world.spatial`, `world.spatial_frames` |
| `persist/commit_entities.py` | 560 | world_entities projection of the scene commit, awareness gate, disguise supersession. | `core.db`, `persist.commit_common`, `story.character_schema`, `story.scene`, `world.spatial` |
| `persist/commit_ledgers.py` | 302 | Pending-obligation and world-pressure debt ledgers. | `core.db`, `persist.commit_common` |
| `persist/commit_mapping.py` | 559 | Lore/book mapping commit: book ops, lore ops, canon fallback ops, offscreen-event normaliser. | `core.db`, `core.frames`, `llm.prompts`, `llm.providers`, `mind.memory`, `persist.commit_common`, `story.character_schema`, `story.provenance_text`, `world.spatial` |
| `persist/commit_mechanics.py` | 372 | Transit/news sweeps, the world-event spine, information carriers, cast changes. | `core.db`, `persist.commit_common`, `persist.commit_scene_state`, `story.character_schema`, `story.scene`, `world.mechanics` |
| `persist/commit_memory.py` | 1792 | Pre-lock memory preparation: per-mind memories and the psychology deltas riding with them. | `core.db`, `mind`, `mind.memory`, `mind.theory_of_mind`, `persist.commit_background`, `persist.commit_common`, `persist.commit_place_graph`, `story.character_schema`, `world.comfort`, `world.spatial`, `world.survival` |
| `persist/commit_memory_write.py` | 325 | The durable memory write and its out-of-band consolidation twin. | `core.db`, `mind.memory`, `persist.commit_memory`, `story.character_schema`, `story.scene` |
| `persist/commit_place_graph.py` | 321 | Per-mind durable place graph and per-beat spatial experience. | `world.spatial` |
| `persist/commit_room_registry.py` | 463 | Room identity across frames: registry projection, mint dedup, renames, retirement, exit pruning. | `core.db`, `persist.commit_common`, `story.character_schema`, `world.spatial` |
| `persist/commit_scene_state.py` | 1104 | The prepared post-turn scene: pre-lock build, scene commit domain, book anchoring, ground advance. | `core.db`, `mind.memory`, `persist.commit_attire`, `persist.commit_common`, `persist.commit_destruction`, `persist.commit_room_registry`, `story.character_schema`, `story.provenance_text`, `world.mechanics`, `world.spatial`, `world.spatial_frames`, `world.weather` |
| `persist/pipeline_trace.py` | 413 | Privacy-conscious export, validation, and offline replay of persisted pipeline history. | `core.db` |
| `story/__init__.py` | 6 |  | — |
| `story/artifacts.py` | 566 |  | `llm.prompts` |
| `story/attire.py` | 3158 |  | — |
| `story/authored_events.py` | 224 |  | `core.db` |
| `story/carriers.py` | 788 |  | `core.db`, `story.character_schema`, `story.scene`, `world`, `world.spatial` |
| `story/character_schema.py` | 2299 | Versioned character/persona defaults, normalization, accessors, and export payloads. | `llm.schemas`, `story` |
| `story/couriers.py` | 1122 |  | `story.carriers`, `world` |
| `story/dialogue_colors.py` | 268 |  | — |
| `story/greetings.py` | 1001 |  | `agents.runtime`, `agents.storage`, `core`, `llm.llm_quality`, `llm.prompts`, `mind.memory`, `mind.theory_of_mind`, `story.character_schema`, `story.importers` |
| `story/history_routing.py` | 197 |  | — |
| `story/importers.py` | 3124 | Native and AI-assisted character, persona, and lorebook import/generation. | `core.db`, `core.logging_utils`, `llm.prompts`, `llm.providers`, `mind.memory`, `story.character_schema`, `story.scene` |
| `story/journey_history.py` | 431 |  | — |
| `story/lore_structure.py` | 248 |  | — |
| `story/naming.py` | 353 |  | `core.db`, `world.charter_identity` |
| `story/provenance_text.py` | 132 |  | — |
| `story/scene.py` | 2602 | Scene/cast/persona helpers, recent events, dialogue configuration, and private knowledge. | `core.db`, `story`, `story.attire`, `story.character_schema`, `world.spatial` |
| `web/__init__.py` | 6 |  | — |
| `web/app.py` | 6507 | FastAPI application assembly, resource CRUD, turn control, and streaming endpoints. | `agents`, `core`, `core.db`, `core.frames`, `core.paths`, `dressing.ambience`, `dressing.backdrops`, `llm`, `llm.prompts`, `llm.providers`, `mind.memory`, `persist.chat_archive`, `persist.chat_delete`, `persist.checkpoints`, `persist.commit`, `story`, `story.character_schema`, `story.dialogue_colors`, `story.importers`, `story.scene`, `web`, `web.auth_routes`, `world`, `world.survival` |
| `web/auth_routes.py` | 279 | Typed host-authentication HTTP routes and cookie transport. | `web` |
| `web/guest_access.py` | 554 |  | `core.db` |
| `web/story_view.py` | 1023 |  | `core.db`, `world.charter_runtime`, `world.living_world` |
| `world/__init__.py` | 6 |  | — |
| `world/background_claims.py` | 598 |  | `core.db` |
| `world/charter.py` | 471 |  | `world.charter_author`, `world.charter_chatter`, `world.charter_commitment`, `world.charter_decide`, `world.charter_drift`, `world.charter_economy`, `world.charter_feel`, `world.charter_figure`, `world.charter_identity`, `world.charter_intervene`, `world.charter_log`, `world.charter_mark`, `world.charter_mind`, `world.charter_model`, `world.charter_move`, `world.charter_needs`, `world.charter_news`, `world.charter_plan`, `world.charter_politics`, `world.charter_practice`, `world.charter_promote`, `world.charter_roster`, `world.charter_run`, `world.charter_social`, `world.charter_space`, `world.charter_talk`, `world.charter_temper`, `world.charter_trigger` |
| `world/charter_author.py` | 318 |  | `world.charter_figure`, `world.charter_mark`, `world.charter_mind`, `world.charter_model`, `world.charter_politics`, `world.charter_practice` |
| `world/charter_chatter.py` | 371 |  | `world.crowds` |
| `world/charter_commitment.py` | 217 |  | `world.charter_model` |
| `world/charter_crowd.py` | 255 |  | `world.crowds` |
| `world/charter_decide.py` | 220 |  | `world.charter_model`, `world.charter_news` |
| `world/charter_drift.py` | 106 |  | `world.charter_model` |
| `world/charter_economy.py` | 401 |  | `world.charter_model` |
| `world/charter_feel.py` | 444 |  | `mind.psychology_runtime`, `world.charter_mark`, `world.charter_needs`, `world.charter_temper` |
| `world/charter_figure.py` | 140 |  | — |
| `world/charter_generate.py` | 692 |  | `world.charter_identity`, `world.charter_model`, `world.charter_needs`, `world.charter_roster` |
| `world/charter_history.py` | 873 |  | — |
| `world/charter_identity.py` | 716 |  | — |
| `world/charter_intervene.py` | 112 |  | `world.charter_model` |
| `world/charter_log.py` | 448 |  | `world.charter_commitment`, `world.charter_decide`, `world.charter_economy`, `world.charter_feel`, `world.charter_mark`, `world.charter_mind`, `world.charter_model`, `world.charter_needs`, `world.charter_news`, `world.charter_politics`, `world.charter_social`, `world.charter_temper` |
| `world/charter_mark.py` | 302 |  | — |
| `world/charter_mind.py` | 262 |  | — |
| `world/charter_model.py` | 604 |  | `world.charter_chatter`, `world.charter_figure`, `world.charter_mark` |
| `world/charter_move.py` | 210 |  | `world.charter_space` |
| `world/charter_needs.py` | 297 |  | `world.charter_model` |
| `world/charter_news.py` | 453 |  | `world.charter_mind`, `world.charter_model`, `world.charter_talk` |
| `world/charter_observe.py` | 299 |  | `world.charter_figure`, `world.charter_identity`, `world.charter_mind`, `world.spatial` |
| `world/charter_plan.py` | 227 |  | `world.charter_drift`, `world.charter_model`, `world.charter_roster` |
| `world/charter_politics.py` | 161 |  | — |
| `world/charter_practice.py` | 1200 |  | `world.charter_commitment`, `world.charter_figure`, `world.charter_mind`, `world.charter_politics`, `world.charter_talk` |
| `world/charter_promote.py` | 470 |  | `world.charter_commitment`, `world.charter_feel`, `world.charter_politics`, `world.charter_social` |
| `world/charter_roster.py` | 134 |  | `world.charter_model` |
| `world/charter_run.py` | 1320 |  | `world`, `world.charter_commitment`, `world.charter_decide`, `world.charter_drift`, `world.charter_economy`, `world.charter_feel`, `world.charter_figure`, `world.charter_intervene`, `world.charter_log`, `world.charter_mark`, `world.charter_mind`, `world.charter_model`, `world.charter_move`, `world.charter_needs`, `world.charter_news`, `world.charter_plan`, `world.charter_politics`, `world.charter_practice`, `world.charter_roster`, `world.charter_social`, `world.charter_space`, `world.charter_talk`, `world.charter_trigger` |
| `world/charter_runtime.py` | 2835 |  | `core`, `core.logging_utils`, `world.charter`, `world.charter_news`, `world.mechanics` |
| `world/charter_social.py` | 743 |  | `world.charter_politics` |
| `world/charter_space.py` | 101 |  | `world.spatial` |
| `world/charter_talk.py` | 344 |  | `world.charter_mind`, `world.charter_politics`, `world.charter_roster` |
| `world/charter_temper.py` | 167 |  | — |
| `world/charter_trigger.py` | 748 |  | `world.charter_mark`, `world.charter_news`, `world.charter_practice` |
| `world/comfort.py` | 349 |  | `world.spatial` |
| `world/crowds.py` | 759 |  | `world.spatial` |
| `world/degradation.py` | 171 |  | — |
| `world/gaps.py` | 454 |  | `core.db`, `mind.canon_provenance`, `world.spatial`, `world.subjects` |
| `world/living_world.py` | 596 |  | `core.logging_utils`, `world.mechanics` |
| `world/mechanics.py` | 930 |  | `core`, `world.spatial`, `world.spatial_frames` |
| `world/offscreen.py` | 2228 |  | `core`, `core.logging_utils`, `llm.prompts` |
| `world/paradox.py` | 648 |  | `core.db`, `core.frames`, `story.character_schema`, `world.spatial` |
| `world/place_purpose.py` | 545 |  | `mind.theory_of_mind`, `world.comfort`, `world.spatial`, `world.survival` |
| `world/routines.py` | 208 |  | — |
| `world/spatial.py` | 222 | Deterministic room, barrier, hearing, visibility, placement, and scene-diff logic. | `llm.schemas`, `world.spatial_barriers`, `world.spatial_contact_migration`, `world.spatial_contacts`, `world.spatial_containment`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_light`, `world.spatial_merge`, `world.spatial_orientation`, `world.spatial_prose`, `world.spatial_routing`, `world.spatial_senses`, `world.spatial_substance`, `world.spatial_transit` |
| `world/spatial_barriers.py` | 666 |  | `world.spatial_orientation` |
| `world/spatial_contact_migration.py` | 331 |  | `world.spatial_contacts`, `world.spatial_identity` |
| `world/spatial_contacts.py` | 1507 |  | `world.spatial_containment`, `world.spatial_identity`, `world.spatial_transit` |
| `world/spatial_containment.py` | 2610 |  | `world.spatial_barriers`, `world.spatial_identity`, `world.spatial_transit` |
| `world/spatial_frames.py` | 1087 |  | `core.db`, `core.frames`, `story.character_schema`, `story.scene`, `world.paradox`, `world.spatial` |
| `world/spatial_geometry.py` | 1197 |  | `world.spatial_barriers`, `world.spatial_contacts`, `world.spatial_containment`, `world.spatial_identity`, `world.spatial_orientation` |
| `world/spatial_identity.py` | 498 |  | — |
| `world/spatial_light.py` | 209 |  | `world.spatial_barriers`, `world.spatial_geometry`, `world.spatial_identity` |
| `world/spatial_merge.py` | 1586 |  | `llm.schemas`, `world.spatial_barriers`, `world.spatial_contact_migration`, `world.spatial_contacts`, `world.spatial_containment`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_orientation`, `world.spatial_routing`, `world.spatial_senses`, `world.spatial_substance`, `world.spatial_transit` |
| `world/spatial_orientation.py` | 246 | Bearing math and reciprocal spatial-edge normalization. | — |
| `world/spatial_prose.py` | 344 |  | `world.spatial_contacts`, `world.spatial_containment`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_light` |
| `world/spatial_routing.py` | 1098 |  | `world.spatial_barriers`, `world.spatial_containment`, `world.spatial_light`, `world.spatial_orientation` |
| `world/spatial_senses.py` | 1268 |  | `world.spatial_barriers`, `world.spatial_contacts`, `world.spatial_containment`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_light`, `world.spatial_orientation`, `world.spatial_routing` |
| `world/spatial_substance.py` | 1128 |  | `world.spatial_contacts`, `world.spatial_identity` |
| `world/spatial_transit.py` | 517 |  | `world.spatial_barriers`, `world.spatial_identity` |
| `world/structure.py` | 415 |  | `world.charter_model`, `world.spatial` |
| `world/subjects.py` | 500 |  | `core.db`, `mind.canon_provenance`, `world.spatial` |
| `world/survival.py` | 354 |  | `core.db` |
| `world/weather.py` | 840 |  | `world.spatial` |

## Largest top-level functions

### `agents/background.py`

| Function | Start | Size |
|---|---:|---:|
| `_react_one()` | 1264 | 149 lines |
| `scene_life()` | 801 | 148 lines |
| `background_react()` | 312 | 137 lines |
| `_beat_for_presence()` | 170 | 80 lines |
| `_present_others()` | 1182 | 80 lines |
| `managed_presences()` | 523 | 78 lines |
| `_filtered_player_declaration()` | 91 | 77 lines |
| `_mint_blurbs()` | 1018 | 75 lines |

### `agents/character.py`

| Function | Start | Size |
|---|---:|---:|
| `character_step()` | 2648 | 1086 lines |
| `_annotate_known_exits()` | 1999 | 458 lines |
| `_ground_observation_citations()` | 1000 | 302 lines |
| `_unanswered_question_note()` | 340 | 192 lines |
| `_destination_from_goals()` | 1565 | 109 lines |
| `sprint_offers()` | 2492 | 97 lines |
| `_recent_self_moves()` | 173 | 90 lines |
| `_verdict()` | 1411 | 71 lines |

### `agents/common.py`

| Function | Start | Size |
|---|---:|---:|
| `norm_sequence()` | 3080 | 284 lines |
| `_check_narrator_fidelity()` | 8097 | 208 lines |
| `_scrub_invented_dialogue()` | 6737 | 151 lines |
| `observer_body_regions()` | 1347 | 137 lines |
| `_extract_authority_claims()` | 2466 | 120 lines |
| `_unknown_actor_label()` | 3705 | 118 lines |
| `cast_spelling_policy()` | 4264 | 118 lines |
| `crowds_for_room()` | 1489 | 113 lines |

### `agents/composer.py`

| Function | Start | Size |
|---|---:|---:|
| `observations_from_render()` | 2952 | 189 lines |
| `_render_view_english()` | 2463 | 149 lines |
| `pose_percepts()` | 1148 | 144 lines |
| `_pose_referent()` | 886 | 91 lines |
| `presence_percepts()` | 685 | 89 lines |
| `_render_episode_english()` | 2753 | 84 lines |
| `_render_standing()` | 2326 | 77 lines |
| `_pose_owner_second_person()` | 1000 | 76 lines |

### `agents/director.py`

| Function | Start | Size |
|---|---:|---:|
| `director_resolve()` | 2479 | 1613 lines |
| `director_interpret()` | 446 | 621 lines |
| `_reconcile_resolution()` | 1443 | 522 lines |
| `_run_specialists()` | 2147 | 224 lines |
| `director_establish()` | 303 | 141 lines |
| `_reconcile_interpretation()` | 1069 | 139 lines |
| `_specialist_repairs()` | 1270 | 119 lines |
| `_prose_gate_facts()` | 2029 | 92 lines |

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
| `_evidence_present()` | 635 | 301 lines |
| `_merge_repair_into_diff()` | 342 | 59 lines |
| `_omission_subject_encoded()` | 515 | 59 lines |
| `_fold_derived_manifest_events()` | 989 | 56 lines |
| `_interpret_coverage_corpus()` | 91 | 53 lines |
| `_subject_is_somewhere()` | 586 | 47 lines |
| `_strip_blank_diff_placeholders()` | 256 | 42 lines |
| `_manifest_items()` | 943 | 37 lines |

### `agents/director_fanout.py`

| Function | Start | Size |
|---|---:|---:|
| `_specialist_payload()` | 236 | 189 lines |
| `_orchestration_scope_backstop()` | 530 | 131 lines |
| `_resolve_beat_view()` | 55 | 125 lines |
| `_interpret_beat_view()` | 182 | 37 lines |
| `_resolved_event_verdicts()` | 461 | 30 lines |
| `fanout_is_parallel()` | 33 | 20 lines |
| `_index_addressed_events()` | 493 | 18 lines |
| `_stage_container()` | 427 | 16 lines |

### `agents/director_floors.py`

| Function | Start | Size |
|---|---:|---:|
| `_awareness_exits()` | 689 | 98 lines |
| `_release_attempts()` | 947 | 93 lines |
| `_conditions_view()` | 569 | 87 lines |
| `_narrated_destruction_subjects()` | 1207 | 79 lines |
| `_unsupported_character_awareness()` | 284 | 66 lines |
| `_restraint_exits()` | 1073 | 64 lines |
| `_clause_attributed_subjects()` | 406 | 57 lines |
| `_unplaced_minted_entities()` | 1287 | 52 lines |

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
| `_gate_facts()` | 561 | 87 lines |
| `register_specialist()` | 419 | 49 lines |
| `_rebuild_channel_owners()` | 388 | 25 lines |
| `_dispatch_specialists()` | 650 | 24 lines |
| `_schema_list_channels()` | 238 | 23 lines |
| `reads_dialogue()` | 146 | 18 lines |
| `_extension_specialist_call()` | 482 | 17 lines |
| `_shipped_transit_state()` | 501 | 12 lines |

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

### `agents/loops.py`

| Function | Start | Size |
|---|---:|---:|
| `interaction_loop()` | 560 | 615 lines |
| `deterministic_micro_perception()` | 138 | 144 lines |
| `reaction_loop()` | 1176 | 70 lines |
| `rehydrate_loop_views()` | 87 | 49 lines |
| `_drop_absent()` | 297 | 45 lines |
| `_isolated_wave()` | 517 | 41 lines |
| `_defer_to_unrun_reactor()` | 374 | 37 lines |
| `_standing_pressure()` | 413 | 37 lines |

### `agents/mapping.py`

| Function | Start | Size |
|---|---:|---:|
| `mapping_stage()` | 32 | 123 lines |
| `mapping_quick()` | 238 | 65 lines |
| `merge_lore()` | 305 | 33 lines |
| `_join_relevant_lore()` | 179 | 32 lines |
| `mapping_request_stages_a_room()` | 231 | 5 lines |

### `agents/narration.py`

| Function | Start | Size |
|---|---:|---:|
| `narrator()` | 1331 | 349 lines |
| `_ordered_beat_events()` | 509 | 230 lines |
| `narrator_extra()` | 1681 | 173 lines |
| `_sensory_channels_manifest()` | 326 | 154 lines |
| `_visible_portal_states()` | 831 | 88 lines |
| `_render_observed_events()` | 1038 | 69 lines |
| `_resolve_narration_person()` | 111 | 66 lines |
| `_generate_narration()` | 1196 | 60 lines |

### `agents/perception.py`

| Function | Start | Size |
|---|---:|---:|
| `_composer_outcome()` | 4060 | 420 lines |
| `perception_outcome()` | 2250 | 277 lines |
| `_composer_standing_percepts()` | 3296 | 181 lines |
| `perception_act()` | 1826 | 177 lines |
| `_composer_act()` | 3687 | 169 lines |
| `_outcome_event_stream()` | 660 | 152 lines |
| `_source_channels()` | 926 | 131 lines |
| `_previous_open_group_continuity()` | 172 | 117 lines |

### `agents/runtime.py`

| Function | Start | Size |
|---|---:|---:|
| `_run_pipeline()` | 955 | 345 lines |
| `build_plan()` | 674 | 109 lines |
| `resume_key_for_turn()` | 581 | 92 lines |
| `_load_extra_players()` | 47 | 74 lines |
| `_stream_one()` | 384 | 68 lines |
| `_stream_parallel()` | 453 | 60 lines |
| `run_pipeline()` | 1301 | 55 lines |
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
| `init()` | 2112 | 109 lines |
| `_recover_scene_time_of_day()` | 2042 | 59 lines |
| `transaction()` | 1781 | 43 lines |
| `conn()` | 1741 | 38 lines |
| `_opening_time_of_day()` | 1986 | 30 lines |
| `_establish_time_of_day_from_variant()` | 1956 | 28 lines |
| `wset()` | 2277 | 23 lines |
| `_stamp_clock_display()` | 2018 | 22 lines |

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
| `generate_backdrop()` | 1125 | 115 lines |
| `room_projection()` | 572 | 73 lines |
| `visual_signature()` | 181 | 48 lines |
| `build_backdrop_request()` | 773 | 46 lines |
| `scene_after_turn()` | 736 | 35 lines |
| `branch_lineage()` | 262 | 34 lines |
| `compose_prompt()` | 890 | 34 lines |
| `compose_revision()` | 952 | 33 lines |

### `llm/llm_quality.py`

| Function | Start | Size |
|---|---:|---:|
| `complete_validated_json()` | 366 | 390 lines |
| `_targeted_field_patch()` | 188 | 63 lines |
| `output_ran_out_of_room()` | 77 | 47 lines |
| `_extract_balanced_object()` | 23 | 34 lines |
| `_step_json_schema()` | 335 | 29 lines |
| `strict_json_parse()` | 126 | 19 lines |
| `_accepted()` | 253 | 19 lines |
| `_character_wire_schema()` | 314 | 19 lines |

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
| `character_prompt()` | 442 | 28 lines |
| `_relocate_character_identity()` | 408 | 27 lines |
| `normalize_preset()` | 122 | 26 lines |
| `_preset_override()` | 206 | 22 lines |
| `_assembled_sheets()` | 38 | 21 lines |
| `specialist_prompt()` | 323 | 17 lines |
| `prose_author_prompt()` | 347 | 17 lines |

### `llm/providers.py`

| Function | Start | Size |
|---|---:|---:|
| `_chat_complete_once()` | 2155 | 288 lines |
| `async _chat_complete_async_once()` | 2564 | 115 lines |
| `chat_complete()` | 1907 | 100 lines |
| `async chat_complete_async()` | 2473 | 90 lines |
| `_sse_openai()` | 1768 | 78 lines |
| `async _sse_openai_async()` | 2680 | 63 lines |
| `_sse_anthropic()` | 1847 | 59 lines |
| `_embed_request()` | 3000 | 58 lines |

### `llm/schemas.py`

| Function | Start | Size |
|---|---:|---:|
| `preprocess_llm_output()` | 4299 | 344 lines |
| `_lenient_coerce()` | 745 | 159 lines |
| `validate_llm_output_strict()` | 5469 | 130 lines |
| `semantic_output_errors()` | 5262 | 112 lines |
| `canonicalize_prose_markup()` | 4104 | 102 lines |
| `_uncross_concealed_speech()` | 4228 | 69 lines |
| `_coerce_list_valued_map()` | 128 | 57 lines |
| `_coerce_conditions()` | 3645 | 55 lines |

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
| `knowledge_for_character()` | 557 | 88 lines |
| `search_lore()` | 248 | 86 lines |
| `backfill_lore_embedding_stamps()` | 335 | 71 lines |
| `duplicate_lorebook_tree_for_chat()` | 178 | 62 lines |
| `lore_embedding_health()` | 408 | 62 lines |
| `update_lore()` | 133 | 44 lines |
| `_stamped_live_dimensions()` | 472 | 42 lines |
| `add_lore()` | 98 | 34 lines |

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
| `import_character_memories()` | 443 | 109 lines |
| `restore_lorebook()` | 636 | 97 lines |
| `prepare_chat_memory_restore()` | 250 | 80 lines |
| `dump_chat_memories()` | 166 | 75 lines |
| `restore_memory_vectors()` | 110 | 54 lines |
| `_foreign_persona_names()` | 400 | 41 lines |
| `apply_chat_memory_restore()` | 331 | 40 lines |
| `vector_address()` | 27 | 35 lines |

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
| `_exportable_checkpoint_blob()` | 94 | 20 lines |
| `_exportable_world()` | 88 | 4 lines |
| `_model_validate()` | 116 | 4 lines |
| `_model_dump()` | 122 | 4 lines |

### `persist/chat_delete.py`

| Function | Start | Size |
|---|---:|---:|
| `delete_chat_data()` | 8 | 35 lines |

### `persist/checkpoints.py`

| Function | Start | Size |
|---|---:|---:|
| `snapshot_state()` | 15 | 174 lines |
| `_restore_checkpoint_body()` | 719 | 147 lines |
| `compact_checkpoints()` | 1009 | 123 lines |
| `_restore_books()` | 248 | 106 lines |
| `insert_world_tables()` | 442 | 105 lines |
| `ensure_checkpoint()` | 1198 | 53 lines |
| `propagate_memory_summaries_to_checkpoints()` | 1253 | 53 lines |
| `_verify_no_loss()` | 957 | 50 lines |

### `persist/commit.py`

| Function | Start | Size |
|---|---:|---:|
| `_commit_all_locked()` | 448 | 267 lines |
| `commit_crowds()` | 261 | 149 lines |
| `commit_authored_events()` | 207 | 30 lines |
| `commit_narration_person()` | 175 | 29 lines |
| `_prepare_turn_commit()` | 425 | 12 lines |
| `commit_offscreen_epoch()` | 239 | 11 lines |
| `commit_all()` | 412 | 11 lines |
| `commit_offscreen_plans()` | 252 | 7 lines |

### `persist/commit_attire.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_attire_diff()` | 796 | 537 lines |
| `interpret_attire_notes()` | 251 | 115 lines |
| `_fold_duplicate_shed_garments()` | 368 | 85 lines |
| `_mint_shed_garments()` | 655 | 73 lines |
| `_fold_worn_garment_entities()` | 455 | 69 lines |
| `_merge_attire_regions()` | 30 | 65 lines |
| `_heal_attire_identity_keys()` | 97 | 61 lines |
| `_shed_record_candidates()` | 574 | 46 lines |

### `persist/commit_background.py`

| Function | Start | Size |
|---|---:|---:|
| `track_background_presences()` | 1308 | 610 lines |
| `promote_background_character()` | 2740 | 334 lines |
| `pick_voice_demand()` | 2363 | 280 lines |
| `_fold_duplicate_presences()` | 685 | 143 lines |
| `descriptor_bindings()` | 2104 | 100 lines |
| `auto_promote_background_characters()` | 3113 | 94 lines |
| `_mint_missing_presence_names()` | 1224 | 82 lines |
| `_unresolved_address_fallback()` | 2013 | 71 lines |

### `persist/commit_common.py`

| Function | Start | Size |
|---|---:|---:|
| `_names_heard_in()` | 248 | 63 lines |
| `_monotonic_elapsed()` | 72 | 53 lines |
| `_address_forms()` | 155 | 52 lines |
| `_entity_alias_map()` | 453 | 47 lines |
| `seed_mutual_recognition()` | 386 | 33 lines |
| `_registered_name_roster()` | 342 | 28 lines |
| `_normalize_character_output()` | 34 | 27 lines |
| `_known_name_roster()` | 313 | 27 lines |

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
| `commit_world_pressure()` | 188 | 115 lines |
| `commit_obligations()` | 67 | 65 lines |
| `world_pressure_view()` | 144 | 22 lines |
| `_find_obligation()` | 45 | 21 lines |
| `pending_obligation_view()` | 24 | 20 lines |
| `_find_pressure()` | 168 | 18 lines |

### `persist/commit_mapping.py`

| Function | Start | Size |
|---|---:|---:|
| `prepare_mapping_commit()` | 200 | 153 lines |
| `commit_mapping()` | 355 | 144 lines |
| `_apply_mapping_book_ops()` | 96 | 103 lines |
| `normalize_offscreen_events()` | 60 | 35 lines |
| `_generate_fallback_ops()` | 525 | 35 lines |
| `_file_engine_provenance()` | 30 | 28 lines |
| `_fact_is_covered()` | 506 | 18 lines |
| `_lore_for()` | 502 | 2 lines |

### `persist/commit_mechanics.py`

| Function | Start | Size |
|---|---:|---:|
| `commit_transit_sweep()` | 21 | 187 lines |
| `commit_information_carriers()` | 258 | 76 lines |
| `commit_world_event_spine()` | 210 | 46 lines |
| `commit_cast_changes()` | 337 | 36 lines |

### `persist/commit_memory.py`

| Function | Start | Size |
|---|---:|---:|
| `prepare_memory_commit()` | 384 | 1409 lines |
| `_cited_memory_ids()` | 78 | 76 lines |
| `_interior_relations_of()` | 327 | 55 lines |
| `_own_sequence_memory()` | 202 | 50 lines |
| `_intent_names_term()` | 286 | 39 lines |
| `_inference_memory_text()` | 254 | 30 lines |
| `_marked_for_memory()` | 156 | 24 lines |
| `_durable_dialogue_category()` | 55 | 22 lines |

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
| `_prepare_room_registry()` | 223 | 94 lines |
| `dedup_minted_rooms()` | 132 | 90 lines |
| `_refresh_relocated_location()` | 369 | 54 lines |
| `_apply_room_renames()` | 76 | 53 lines |
| `prune_dangling_exits()` | 425 | 39 lines |
| `_apply_room_registry()` | 319 | 28 lines |
| `_registry_alias_index()` | 53 | 22 lines |
| `sync_room_registry_with_scene()` | 348 | 19 lines |

### `persist/commit_scene_state.py`

| Function | Start | Size |
|---|---:|---:|
| `prepare_scene_commit()` | 363 | 692 lines |
| `sync_anchored_books()` | 81 | 66 lines |
| `_guard_occupied_mover_removal()` | 148 | 60 lines |
| `_dedupe_overlay_entries()` | 281 | 40 lines |
| `_merge_overlays()` | 323 | 38 lines |
| `_advance_ground()` | 210 | 31 lines |
| `_establish_time_of_day()` | 36 | 27 lines |
| `_record_subject_last_seen()` | 1081 | 24 lines |

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
| `schedule_artifact_wording()` | 392 | 66 lines |
| `mint_wording()` | 460 | 55 lines |
| `land_artifact_wording()` | 517 | 50 lines |
| `reading_copy()` | 150 | 25 lines |
| `new_artifact()` | 128 | 20 lines |
| `artifact_voice()` | 95 | 11 lines |
| `posted_in_room()` | 116 | 10 lines |

### `story/attire.py`

| Function | Start | Size |
|---|---:|---:|
| `advance()` | 2254 | 141 lines |
| `normalize_regions()` | 516 | 133 lines |
| `garments_named_in()` | 1947 | 126 lines |
| `coerce_diff_shape()` | 1471 | 124 lines |
| `compact_line()` | 3017 | 123 lines |
| `perceptible_region_surfaces()` | 2518 | 100 lines |
| `_attributed_targets()` | 1685 | 90 lines |
| `apply_flat_change()` | 2620 | 89 lines |

### `story/authored_events.py`

| Function | Start | Size |
|---|---:|---:|
| `resolve_authored_events()` | 173 | 52 lines |
| `mint_authored_events()` | 107 | 46 lines |
| `_retired_text()` | 52 | 34 lines |
| `_event_id()` | 89 | 16 lines |
| `due_authored_events()` | 155 | 16 lines |

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
| `normalize_character_data()` | 1236 | 167 lines |
| `character_card_warnings()` | 2120 | 149 lines |
| `default_character_data()` | 697 | 118 lines |
| `_normalize_psychology()` | 314 | 83 lines |
| `_normalize_interior()` | 636 | 59 lines |
| `repair_character_shape()` | 1177 | 57 lines |
| `normalize_persona_data()` | 1404 | 55 lines |
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
| `start_story()` | 654 | 249 lines |
| `_seed_mind_state()` | 351 | 144 lines |
| `generate_greeting()` | 905 | 62 lines |
| `_seed_minds()` | 549 | 57 lines |
| `_route_mind_memories()` | 294 | 55 lines |
| `_seed_player_mind()` | 497 | 50 lines |
| `claim_greeting_mind()` | 608 | 44 lines |
| `extract_greeting()` | 122 | 35 lines |

### `story/history_routing.py`

| Function | Start | Size |
|---|---:|---:|
| `resolve_character_history_route()` | 124 | 64 lines |
| `_manual_route()` | 81 | 41 lines |
| `normalize_history_choice()` | 53 | 14 lines |
| `_distinct_words()` | 73 | 6 lines |
| `_matches()` | 69 | 2 lines |
| `route_uses_charter()` | 190 | 2 lines |

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

### `story/naming.py`

| Function | Start | Size |
|---|---:|---:|
| `minted_presence_name()` | 300 | 54 lines |
| `_person_name_evidence()` | 154 | 37 lines |
| `registered_identity_names()` | 244 | 33 lines |
| `harvested_naming_profile()` | 193 | 28 lines |
| `_name_tokens()` | 126 | 26 lines |
| `_charter_naming_lanes()` | 101 | 23 lines |
| `story_naming_lanes()` | 223 | 19 lines |
| `story_identity_reservation()` | 279 | 14 lines |

### `story/provenance_text.py`

| Function | Start | Size |
|---|---:|---:|
| `split_engine_provenance()` | 86 | 42 lines |
| `looks_like_engine_provenance()` | 81 | 3 lines |
| `strip_engine_provenance()` | 130 | 3 lines |

### `story/scene.py`

| Function | Start | Size |
|---|---:|---:|
| `active_disguises()` | 569 | 82 lines |
| `normalize_transformed_parts()` | 660 | 60 lines |
| `recent_events_for_observer()` | 1790 | 59 lines |
| `_positive_presented_appearance()` | 857 | 58 lines |
| `awareness_conditions()` | 1186 | 58 lines |
| `active_transformations()` | 722 | 54 lines |
| `director_context()` | 1850 | 53 lines |
| `get_scene()` | 366 | 52 lines |

### `web/app.py`

| Function | Start | Size |
|---|---:|---:|
| `turn_branch()` | 5288 | 418 lines |
| `chat_get()` | 3357 | 253 lines |
| `_remap_cp_blob()` | 1004 | 211 lines |
| `bootstrap()` | 1335 | 104 lines |
| `_stream()` | 650 | 91 lines |
| `dlg_put()` | 4550 | 79 lines |
| `_ambience_payload()` | 6282 | 75 lines |
| `lore_entry_edit()` | 3035 | 70 lines |

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
| `authored()` | 101 | 104 lines |
| `_figure_act()` | 232 | 62 lines |
| `_pair_situations()` | 76 | 23 lines |
| `_body_act()` | 207 | 23 lines |
| `action_instances()` | 296 | 23 lines |
| `_refusal()` | 71 | 3 lines |

### `world/charter_chatter.py`

| Function | Start | Size |
|---|---:|---:|
| `overheard_fragment()` | 228 | 44 lines |
| `window_acts()` | 74 | 34 lines |
| `participant_label()` | 319 | 34 lines |
| `normalize_window_acts()` | 110 | 31 lines |
| `hum_rank()` | 155 | 29 lines |
| `fragment_phrase()` | 295 | 22 lines |
| `subject_label()` | 355 | 17 lines |
| `hum_phrase()` | 186 | 16 lines |

### `world/charter_commitment.py`

| Function | Start | Size |
|---|---:|---:|
| `observe_public_commitments()` | 76 | 80 lines |
| `normalize_commitments()` | 32 | 38 lines |
| `advance_commitments()` | 169 | 25 lines |
| `commitment_view()` | 196 | 15 lines |
| `commitment_id()` | 26 | 4 lines |
| `_frame_terms()` | 72 | 2 lines |

### `world/charter_crowd.py`

| Function | Start | Size |
|---|---:|---:|
| `composition_of()` | 176 | 33 lines |
| `members_of()` | 121 | 32 lines |
| `crowd_for()` | 231 | 25 lines |
| `engaged_turn()` | 81 | 20 lines |
| `mood_of()` | 211 | 18 lines |
| `presented()` | 103 | 16 lines |
| `_role_noun()` | 155 | 9 lines |
| `_plural()` | 166 | 8 lines |

### `world/charter_decide.py`

| Function | Start | Size |
|---|---:|---:|
| `advance_decisions()` | 75 | 54 lines |
| `execute_orders()` | 159 | 47 lines |
| `normalize_decisions()` | 25 | 35 lines |
| `deliver_orders()` | 131 | 26 lines |
| `decision_view()` | 208 | 7 lines |
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
| `caravan_exchange()` | 349 | 47 lines |
| `quote()` | 240 | 27 lines |
| `_holdings()` | 46 | 26 lines |
| `trade()` | 324 | 23 lines |
| `_keyed()` | 28 | 16 lines |

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
| `close_plan()` | 283 | 200 lines |
| `ensure_required_rooms()` | 485 | 53 lines |
| `resident_service_chronicle()` | 550 | 47 lines |
| `ground_history_output()` | 599 | 46 lines |
| `_featured_assignments()` | 236 | 45 lines |
| `_ensure_shift_crews()` | 188 | 41 lines |
| `narrate_actual_history()` | 647 | 38 lines |
| `_json_call()` | 112 | 22 lines |

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
| `materialize_body_names()` | 520 | 119 lines |
| `name_is_reserved()` | 405 | 56 lines |
| `identity_aliases()` | 674 | 38 lines |
| `derived_name_parts()` | 154 | 32 lines |
| `normalize_naming_profile()` | 71 | 28 lines |
| `extension_profile()` | 215 | 28 lines |
| `_safe_format()` | 44 | 25 lines |
| `_stored_name_components()` | 273 | 24 lines |

### `world/charter_intervene.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_due()` | 50 | 57 lines |
| `normalize_interventions()` | 18 | 23 lines |
| `intervention_warnings()` | 43 | 5 lines |

### `world/charter_log.py`

| Function | Start | Size |
|---|---:|---:|
| `scene_ledger()` | 226 | 204 lines |
| `life_of()` | 135 | 89 lines |
| `summarize()` | 63 | 70 lines |
| `chronicle()` | 432 | 17 lines |
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
| `normalize_charter()` | 299 | 284 lines |
| `normalize_body()` | 170 | 68 lines |
| `body_of_an_authored_mind()` | 240 | 45 lines |
| `normalize_upkeep()` | 110 | 31 lines |
| `normalize_post()` | 143 | 25 lines |
| `_tags()` | 71 | 15 lines |
| `_string_list()` | 93 | 15 lines |
| `priority_rank()` | 597 | 8 lines |

### `world/charter_move.py`

| Function | Start | Size |
|---|---:|---:|
| `errands()` | 102 | 52 lines |
| `relocate()` | 66 | 34 lines |
| `walk()` | 156 | 29 lines |
| `_roll()` | 43 | 21 lines |
| `homecomings()` | 187 | 18 lines |
| `furthest_travelled()` | 207 | 4 lines |

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
| `check_reports()` | 296 | 92 lines |
| `claim_from_report()` | 133 | 36 lines |
| `report_from_claim()` | 171 | 34 lines |
| `decay_news()` | 390 | 26 lines |
| `_native_news_phrase()` | 207 | 24 lines |
| `news_claim()` | 246 | 24 lines |
| `witness()` | 272 | 22 lines |
| `known_news()` | 425 | 18 lines |

### `world/charter_observe.py`

| Function | Start | Size |
|---|---:|---:|
| `plan_public_evidence()` | 148 | 90 lines |
| `apply_public_evidence()` | 240 | 53 lines |
| `body_receives_evidence()` | 68 | 29 lines |
| `evidence_claim()` | 117 | 29 lines |
| `_observer_scene()` | 54 | 12 lines |
| `evidence_phrase()` | 103 | 12 lines |
| `_identity_forms()` | 33 | 6 lines |
| `_is_concealed()` | 47 | 5 lines |

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

### `world/charter_promote.py`

| Function | Start | Size |
|---|---:|---:|
| `remembered()` | 111 | 260 lines |
| `acquainted()` | 406 | 65 lines |
| `promotion_handoff()` | 373 | 23 lines |
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
| `step()` | 398 | 864 lines |
| `_record_coarse_experiences()` | 236 | 160 lines |
| `run()` | 1264 | 57 lines |
| `_remember_experience()` | 148 | 32 lines |
| `_run_private_habits()` | 205 | 29 lines |
| `_social_events()` | 103 | 25 lines |
| `_record_social_experiences()` | 182 | 21 lines |
| `_event()` | 78 | 3 lines |

### `world/charter_runtime.py`

| Function | Start | Size |
|---|---:|---:|
| `registry_warnings()` | 1512 | 160 lines |
| `_prepare_cast_histories()` | 644 | 141 lines |
| `_generate_lived_location()` | 1361 | 113 lines |
| `_plan_lived_location()` | 1250 | 109 lines |
| `generation_lore()` | 962 | 101 lines |
| `cross_charter_gossip()` | 1843 | 92 lines |
| `charter_diagnostics()` | 2077 | 86 lines |
| `normalize_registry()` | 335 | 73 lines |

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
| `reach_map()` | 65 | 29 lines |
| `refresh_reach()` | 46 | 17 lines |
| `travel_rooms()` | 31 | 13 lines |
| `charter_places()` | 96 | 6 lines |

### `world/charter_talk.py`

| Function | Start | Size |
|---|---:|---:|
| `report_to_superiors()` | 295 | 50 lines |
| `converse()` | 200 | 49 lines |
| `report_up()` | 251 | 42 lines |
| `tell_ranking()` | 88 | 38 lines |
| `co_present()` | 128 | 27 lines |
| `tellable()` | 61 | 25 lines |
| `witnessed()` | 178 | 20 lines |
| `pair_up()` | 157 | 19 lines |

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
| `fire_triggers()` | 575 | 144 lines |
| `_normalize_rule()` | 302 | 87 lines |
| `changes_from()` | 498 | 41 lines |
| `perceivable_change()` | 264 | 36 lines |
| `_cap_changes()` | 473 | 23 lines |
| `normalize_triggers()` | 391 | 20 lines |
| `prune_trigger_last()` | 541 | 20 lines |
| `trigger_view()` | 721 | 17 lines |

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
| `land_agent_tick()` | 1922 | 187 lines |
| `schedule_agent_ticks()` | 2111 | 118 lines |
| `schedule_profile_ticks()` | 1411 | 112 lines |
| `apply_plan_ops()` | 731 | 110 lines |
| `agent_context()` | 1589 | 109 lines |
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
| `apply_contact_ops()` | 993 | 350 lines |
| `_clean_contact()` | 628 | 124 lines |
| `contacts_across_enclosure()` | 794 | 68 lines |
| `normalize_scene_contacts()` | 902 | 63 lines |
| `_unnamed_touch_between_bodies()` | 569 | 47 lines |
| `contacts_broken_by_scale_change()` | 754 | 38 lines |
| `_restation_interior_contact()` | 864 | 36 lines |
| `_contained_inversion()` | 478 | 29 lines |

### `world/spatial_containment.py`

| Function | Start | Size |
|---|---:|---:|
| `materialize_named_stations()` | 2021 | 135 lines |
| `advance_room_transits()` | 2158 | 130 lines |
| `replace_engine_minted_interiors()` | 1521 | 123 lines |
| `derive_inventory_placements()` | 855 | 108 lines |
| `release_declared_departures()` | 2302 | 97 lines |
| `place_enclosed_bodies()` | 1646 | 95 lines |
| `derive_containment_from_contacts()` | 344 | 90 lines |
| `materialize_enclosure_interiors()` | 1393 | 81 lines |

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
| `derive_scene_stations()` | 1094 | 104 lines |
| `spatial_digest()` | 140 | 89 lines |
| `egocentric_frame()` | 52 | 86 lines |
| `invalidate_contact_bound_poses()` | 862 | 72 lines |
| `normalize_scene_poses()` | 789 | 64 lines |
| `effective_station()` | 348 | 55 lines |
| `poses_broken_by_scale_change()` | 936 | 52 lines |
| `effective_anchors()` | 296 | 50 lines |

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
| `merge_scene_with_diff()` | 1066 | 521 lines |
| `_expire_transient_entity_state()` | 400 | 116 lines |
| `_shield_minted_edges()` | 804 | 95 lines |
| `apply_following_ops()` | 987 | 77 lines |
| `connect_orphan_new_rooms()` | 901 | 68 lines |
| `_merge_room()` | 143 | 64 lines |
| `_shield_standing_bearings()` | 679 | 61 lines |
| `_shield_standing_passage()` | 742 | 60 lines |

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

### `world/structure.py`

| Function | Start | Size |
|---|---:|---:|
| `prepare_frontier_expansion()` | 266 | 82 lines |
| `materialize_planned_fringe()` | 184 | 45 lines |
| `plant_structure()` | 143 | 39 lines |
| `structure_warnings()` | 370 | 37 lines |
| `planned_context()` | 231 | 33 lines |
| `composed_scene()` | 89 | 26 lines |
| `mint_frontier()` | 117 | 24 lines |
| `normalize_structure()` | 24 | 22 lines |

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
| GET | `/` | `index()` | `web/app.py:521` |
| PUT | `/api/active_preset` | `set_active()` | `web/app.py:1751` |
| PUT | `/api/affect_habituation` | `set_affect_habituation()` | `web/app.py:2071` |
| PUT | `/api/agent_models` | `put_agent_models()` | `web/app.py:1441` |
| PUT | `/api/ambience` | `put_ambience()` | `web/app.py:1562` |
| GET | `/api/ambience/library` | `ambience_library()` | `web/app.py:6447` |
| GET | `/api/ambience/search` | `ambience_search()` | `web/app.py:6426` |
| PUT | `/api/attire_beneath` | `set_attire_beneath()` | `web/app.py:2090` |
| POST | `/api/auth/login` | `auth_login()` | `web/auth_routes.py:209` |
| POST | `/api/auth/logout` | `auth_logout()` | `web/auth_routes.py:275` |
| POST | `/api/auth/setup` | `auth_setup()` | `web/auth_routes.py:134` |
| GET | `/api/auth/status` | `auth_status()` | `web/auth_routes.py:124` |
| GET | `/api/auto_promote` | `get_auto_promote()` | `web/app.py:3744` |
| PUT | `/api/auto_promote` | `set_auto_promote()` | `web/app.py:3757` |
| PUT | `/api/backdrops` | `put_backdrops()` | `web/app.py:1552` |
| GET | `/api/bootstrap` | `bootstrap()` | `web/app.py:1335` |
| POST | `/api/characters` | `char_create()` | `web/app.py:2546` |
| POST | `/api/characters/generate` | `char_generate()` | `web/app.py:2523` |
| POST | `/api/characters/import` | `char_import()` | `web/app.py:2571` |
| DELETE | `/api/characters/{cid}` | `char_del()` | `web/app.py:2757` |
| PUT | `/api/characters/{cid}` | `char_edit()` | `web/app.py:2747` |
| GET | `/api/characters/{cid}/export` | `char_export()` | `web/app.py:2739` |
| POST | `/api/characters/{cid}/fill_appearance` | `char_fill_appearance()` | `web/app.py:2727` |
| POST | `/api/characters/{cid}/fill_interior` | `char_fill_interior()` | `web/app.py:2685` |
| POST | `/api/characters/{cid}/fill_psychology` | `char_fill_psychology()` | `web/app.py:2652` |
| POST | `/api/characters/{cid}/generate_greeting` | `char_generate_greeting()` | `web/app.py:2636` |
| POST | `/api/characters/{cid}/recover_greetings` | `char_recover_greetings()` | `web/app.py:2626` |
| POST | `/api/characters/{cid}/start` | `character_start_story()` | `web/app.py:2595` |
| POST | `/api/chats` | `chat_new()` | `web/app.py:3114` |
| POST | `/api/chats/import` | `import_chat()` | `persist/chat_archive.py:258` |
| DELETE | `/api/chats/{cid}` | `chat_del()` | `web/app.py:3349` |
| GET | `/api/chats/{cid}` | `chat_get()` | `web/app.py:3357` |
| PUT | `/api/chats/{cid}` | `chat_edit()` | `web/app.py:3212` |
| POST | `/api/chats/{cid}/abort` | `chat_abort()` | `web/app.py:5284` |
| GET | `/api/chats/{cid}/ambience/oneshot/{name}` | `ambience_oneshot()` | `web/app.py:6456` |
| DELETE | `/api/chats/{cid}/ambience/pin` | `ambience_pin_delete()` | `web/app.py:6504` |
| PUT | `/api/chats/{cid}/ambience/pin` | `ambience_pin_put()` | `web/app.py:6485` |
| GET | `/api/chats/{cid}/ambience/pins` | `ambience_pins_get()` | `web/app.py:6480` |
| GET | `/api/chats/{cid}/ambience/{signature}.audio` | `ambience_audio()` | `web/app.py:6410` |
| GET | `/api/chats/{cid}/attire` | `attire_get()` | `web/app.py:4483` |
| PUT | `/api/chats/{cid}/attire` | `attire_put()` | `web/app.py:4494` |
| GET | `/api/chats/{cid}/backdrop/{signature}.png` | `backdrop_image()` | `web/app.py:6250` |
| GET | `/api/chats/{cid}/background_config` | `bg_cfg_get()` | `web/app.py:4775` |
| PUT | `/api/chats/{cid}/background_config` | `bg_cfg_put()` | `web/app.py:4779` |
| POST | `/api/chats/{cid}/characters` | `chat_add_char()` | `web/app.py:3612` |
| DELETE | `/api/chats/{cid}/characters/{ch}` | `chat_del_char()` | `web/app.py:4036` |
| PUT | `/api/chats/{cid}/characters/{ch}/card` | `chat_char_card_put()` | `web/app.py:4046` |
| PUT | `/api/chats/{cid}/characters/{ch}/dialogue_color` | `dialogue_color_put()` | `web/app.py:4351` |
| POST | `/api/chats/{cid}/characters/{ch}/fill_interior` | `chat_char_fill_interior()` | `web/app.py:2696` |
| GET | `/api/chats/{cid}/characters/{ch}/memories` | `mem_list()` | `web/app.py:5024` |
| POST | `/api/chats/{cid}/characters/{ch}/memories` | `mem_add()` | `web/app.py:5171` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/backfill` | `mem_backfill()` | `web/app.py:5141` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/consolidate` | `mem_consolidate()` | `web/app.py:5126` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/coverage` | `mem_coverage()` | `web/app.py:5162` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/export` | `mem_export()` | `web/app.py:5070` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/import` | `mem_import()` | `web/app.py:5081` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/search` | `mem_search()` | `web/app.py:5045` |
| GET | `/api/chats/{cid}/characters/{ch}/memory-context` | `memory_context_preview()` | `web/app.py:5102` |
| PUT | `/api/chats/{cid}/characters/{ch}/position` | `chat_char_position_put()` | `web/app.py:4263` |
| GET | `/api/chats/{cid}/characters/{ch}/private_history` | `ph_get()` | `web/app.py:4332` |
| PUT | `/api/chats/{cid}/characters/{ch}/private_history` | `ph_put()` | `web/app.py:4342` |
| GET | `/api/chats/{cid}/characters/{ch}/relationships` | `relationships_get()` | `web/app.py:5115` |
| GET | `/api/chats/{cid}/charters` | `charters_get()` | `web/app.py:4666` |
| PUT | `/api/chats/{cid}/charters` | `charters_put()` | `web/app.py:4687` |
| GET | `/api/chats/{cid}/charters/diagnostics` | `charters_diagnostics()` | `web/app.py:4705` |
| POST | `/api/chats/{cid}/charters/generate` | `charters_generate()` | `web/app.py:4717` |
| DELETE | `/api/chats/{cid}/charters/job` | `charters_job_clear()` | `web/app.py:4758` |
| GET | `/api/chats/{cid}/charters/job` | `charters_job_get()` | `web/app.py:4739` |
| GET | `/api/chats/{cid}/dialogue_config` | `dlg_get()` | `web/app.py:4533` |
| PUT | `/api/chats/{cid}/dialogue_config` | `dlg_put()` | `web/app.py:4550` |
| GET | `/api/chats/{cid}/dramatic_irony` | `get_dramatic_irony_feed()` | `web/app.py:3686` |
| GET | `/api/chats/{cid}/export` | `export_chat()` | `persist/chat_archive.py:252` |
| GET | `/api/chats/{cid}/fixed_points` | `fixed_points_list()` | `web/app.py:4970` |
| POST | `/api/chats/{cid}/fixed_points` | `fixed_points_create()` | `web/app.py:4980` |
| DELETE | `/api/chats/{cid}/fixed_points/{anchor_id}` | `fixed_points_delete()` | `web/app.py:5002` |
| GET | `/api/chats/{cid}/frames` | `frames_list()` | `web/app.py:4924` |
| POST | `/api/chats/{cid}/frames` | `frames_create()` | `web/app.py:4928` |
| GET | `/api/chats/{cid}/guest_invites` | `list_guest_invites()` | `web/app.py:3917` |
| POST | `/api/chats/{cid}/guest_invites` | `create_guest_invite()` | `web/app.py:3897` |
| DELETE | `/api/chats/{cid}/guest_invites/{gid}` | `revoke_guest_invite()` | `web/app.py:3921` |
| GET | `/api/chats/{cid}/language` | `chat_language_get()` | `web/app.py:3179` |
| PUT | `/api/chats/{cid}/language` | `chat_language_put()` | `web/app.py:3196` |
| GET | `/api/chats/{cid}/living_world` | `living_world_get()` | `web/app.py:4631` |
| PUT | `/api/chats/{cid}/living_world` | `living_world_put()` | `web/app.py:4654` |
| DELETE | `/api/chats/{cid}/lorebook` | `detach_lore()` | `web/app.py:3340` |
| POST | `/api/chats/{cid}/lorebook` | `bind_lore()` | `web/app.py:3319` |
| GET | `/api/chats/{cid}/lorebooks` | `chat_lorebooks_owned()` | `web/app.py:2174` |
| POST | `/api/chats/{cid}/lorebooks` | `attach_lore()` | `web/app.py:3243` |
| DELETE | `/api/chats/{cid}/lorebooks/{lid}` | `detach_book()` | `web/app.py:3304` |
| PUT | `/api/chats/{cid}/lorebooks/{lid}` | `set_book_enabled()` | `web/app.py:3268` |
| GET | `/api/chats/{cid}/naming_profile` | `naming_profile_get()` | `web/app.py:4805` |
| PUT | `/api/chats/{cid}/naming_profile` | `naming_profile_put()` | `web/app.py:4817` |
| GET | `/api/chats/{cid}/paradox_policy` | `paradox_policy_get()` | `web/app.py:4955` |
| PUT | `/api/chats/{cid}/paradox_policy` | `paradox_policy_put()` | `web/app.py:4959` |
| GET | `/api/chats/{cid}/persona_private_history` | `pph_get()` | `web/app.py:4414` |
| PUT | `/api/chats/{cid}/persona_private_history` | `pph_put()` | `web/app.py:4427` |
| GET | `/api/chats/{cid}/personas` | `chat_list_extra_personas()` | `web/app.py:3762` |
| POST | `/api/chats/{cid}/personas` | `chat_add_persona()` | `web/app.py:3807` |
| DELETE | `/api/chats/{cid}/personas/{pid}` | `chat_del_persona()` | `web/app.py:3833` |
| PUT | `/api/chats/{cid}/personas/{pid}/station` | `chat_persona_station()` | `web/app.py:3772` |
| GET | `/api/chats/{cid}/player_authority` | `player_authority_get()` | `web/app.py:4887` |
| PUT | `/api/chats/{cid}/player_authority` | `player_authority_put()` | `web/app.py:4902` |
| GET | `/api/chats/{cid}/player_view` | `player_view_get()` | `web/app.py:4864` |
| GET | `/api/chats/{cid}/positions` | `chat_positions_get()` | `web/app.py:4196` |
| GET | `/api/chats/{cid}/promises` | `get_promise_ledger()` | `web/app.py:3690` |
| GET | `/api/chats/{cid}/promotable` | `list_promotable_presences()` | `web/app.py:3682` |
| POST | `/api/chats/{cid}/promotions/confirm` | `confirm_promotion()` | `web/app.py:3711` |
| POST | `/api/chats/{cid}/promotions/draft` | `draft_promotion()` | `web/app.py:3694` |
| GET | `/api/chats/{cid}/story_view` | `story_view_get()` | `web/app.py:4830` |
| GET | `/api/chats/{cid}/style_guide` | `style_guide_get()` | `web/app.py:4516` |
| PUT | `/api/chats/{cid}/style_guide` | `style_guide_put()` | `web/app.py:4522` |
| GET | `/api/chats/{cid}/survival` | `survival_get()` | `web/app.py:4104` |
| PUT | `/api/chats/{cid}/survival` | `survival_put()` | `web/app.py:4109` |
| POST | `/api/chats/{cid}/turns` | `turn_new()` | `web/app.py:5224` |
| POST | `/api/chats/{cid}/turns/{idx}/player_input` | `submit_extra_player_input()` | `web/app.py:3847` |
| GET | `/api/chats/{cid}/viewers` | `viewers_get()` | `web/app.py:4879` |
| GET | `/api/chats/{cid}/vitals` | `chat_vitals_get()` | `web/app.py:4161` |
| GET | `/api/chats/{cid}/world` | `world_get()` | `web/app.py:4432` |
| PUT | `/api/chats/{cid}/world` | `world_put()` | `web/app.py:4442` |
| GET | `/api/default_prompts` | `default_prompts()` | `web/app.py:1681` |
| PUT | `/api/director_fanout_mode` | `set_director_fanout_mode()` | `web/app.py:2047` |
| PUT | `/api/exemplars` | `put_exemplars()` | `web/app.py:1521` |
| GET | `/api/extensions` | `extensions_list()` | `web/app.py:1768` |
| POST | `/api/extensions/install` | `extension_install()` | `web/app.py:1790` |
| GET | `/api/extensions/ui.css` | `extensions_ui_css()` | `web/app.py:1968` |
| GET | `/api/extensions/ui.js` | `extensions_ui()` | `web/app.py:1959` |
| GET | `/api/extensions/updates` | `extension_updates()` | `web/app.py:1811` |
| DELETE | `/api/extensions/{eid}` | `extension_remove()` | `web/app.py:1832` |
| GET | `/api/extensions/{eid}/asset/{path:path}` | `extension_asset()` | `web/app.py:2023` |
| POST | `/api/extensions/{eid}/disable` | `extension_disable()` | `web/app.py:1840` |
| DELETE | `/api/extensions/{eid}/document` | `extension_document_delete()` | `web/app.py:1936` |
| GET | `/api/extensions/{eid}/document` | `extension_document_get()` | `web/app.py:1904` |
| PUT | `/api/extensions/{eid}/document` | `extension_document_put()` | `web/app.py:1916` |
| DELETE | `/api/extensions/{eid}/documents` | `extension_documents_delete()` | `web/app.py:1946` |
| GET | `/api/extensions/{eid}/documents` | `extension_documents_list()` | `web/app.py:1883` |
| GET | `/api/extensions/{eid}/documents/verify` | `extension_documents_verify()` | `web/app.py:1894` |
| POST | `/api/extensions/{eid}/enable` | `extension_enable()` | `web/app.py:1782` |
| GET | `/api/extensions/{eid}/state` | `extension_state()` | `web/app.py:1845` |
| GET | `/api/extensions/{eid}/ui.css` | `extension_ui_css_one()` | `web/app.py:1990` |
| GET | `/api/extensions/{eid}/ui.js` | `extension_ui_one()` | `web/app.py:1978` |
| POST | `/api/extensions/{eid}/update` | `extension_update()` | `web/app.py:1822` |
| POST | `/api/guest/input` | `guest_input()` | `web/app.py:4011` |
| GET | `/api/guest/state` | `guest_state()` | `web/app.py:3943` |
| PUT | `/api/image_model` | `put_image_model()` | `web/app.py:1499` |
| POST | `/api/join` | `join_with_code()` | `web/app.py:3927` |
| GET | `/api/language-packs` | `language_packs_get()` | `web/app.py:3132` |
| GET | `/api/language-packs/{language_id}/ui` | `language_pack_ui()` | `web/app.py:3153` |
| DELETE | `/api/lore_entries/{eid}` | `lore_entry_delete()` | `web/app.py:3107` |
| PUT | `/api/lore_entries/{eid}` | `lore_entry_edit()` | `web/app.py:3035` |
| DELETE | `/api/lore_gen_jobs/{job_id}` | `lorebook_generate_discard()` | `web/app.py:2330` |
| POST | `/api/lore_gen_jobs/{job_id}/resume` | `lorebook_generate_resume()` | `web/app.py:2312` |
| DELETE | `/api/lorebook_links/{link_id}` | `lorebook_link_delete()` | `web/app.py:2270` |
| PUT | `/api/lorebook_links/{link_id}` | `lorebook_link_update()` | `web/app.py:2256` |
| POST | `/api/lorebooks` | `lore_create()` | `web/app.py:2864` |
| POST | `/api/lorebooks/import` | `lore_import()` | `web/app.py:2366` |
| DELETE | `/api/lorebooks/{lid}` | `lore_delete()` | `web/app.py:2956` |
| GET | `/api/lorebooks/{lid}` | `lore_get()` | `web/app.py:2844` |
| PUT | `/api/lorebooks/{lid}` | `lore_edit()` | `web/app.py:2886` |
| POST | `/api/lorebooks/{lid}/apply_plan` | `lorebook_apply_plan()` | `web/app.py:2339` |
| POST | `/api/lorebooks/{lid}/entries` | `lore_entry_create()` | `web/app.py:3006` |
| GET | `/api/lorebooks/{lid}/export` | `lore_export()` | `web/app.py:2962` |
| POST | `/api/lorebooks/{lid}/generate` | `lore_generate()` | `web/app.py:2992` |
| GET | `/api/lorebooks/{lid}/generate_job` | `lorebook_generate_job()` | `web/app.py:2301` |
| POST | `/api/lorebooks/{lid}/generate_plan` | `lorebook_generate_plan()` | `web/app.py:2275` |
| GET | `/api/lorebooks/{lid}/links` | `lorebook_links_get()` | `web/app.py:2229` |
| POST | `/api/lorebooks/{lid}/links` | `lorebook_link_create()` | `web/app.py:2234` |
| POST | `/api/lorebooks/{lid}/move` | `lorebook_move()` | `web/app.py:2156` |
| POST | `/api/lorebooks/{lid}/reinterpret` | `lore_reinterpret_route()` | `web/app.py:2979` |
| POST | `/api/lorebooks/{lid}/reorder` | `lorebook_reorder()` | `web/app.py:2165` |
| GET | `/api/maintenance/checkpoints` | `maintenance_checkpoints()` | `web/app.py:2113` |
| POST | `/api/maintenance/checkpoints/compact` | `maintenance_compact()` | `web/app.py:2129` |
| PUT | `/api/max_output_tokens` | `put_max_output_tokens()` | `web/app.py:1648` |
| DELETE | `/api/memories/{mid}` | `mem_del()` | `web/app.py:5218` |
| PUT | `/api/memories/{mid}` | `mem_edit()` | `web/app.py:5197` |
| GET | `/api/memory/embeddings` | `memory_embeddings_status()` | `web/app.py:1472` |
| POST | `/api/memory/embeddings/rebuild` | `memory_embeddings_rebuild()` | `web/app.py:1487` |
| GET | `/api/nsfw` | `get_nsfw()` | `web/app.py:2038` |
| PUT | `/api/nsfw` | `set_nsfw()` | `web/app.py:2042` |
| GET | `/api/openrouter/endpoints` | `get_openrouter_endpoints()` | `web/app.py:1606` |
| PUT | `/api/openrouter_routing` | `put_openrouter_routing()` | `web/app.py:1592` |
| POST | `/api/personas` | `persona_create()` | `web/app.py:2786` |
| POST | `/api/personas/generate` | `persona_generate()` | `web/app.py:2764` |
| POST | `/api/personas/import` | `persona_import()` | `web/app.py:2806` |
| DELETE | `/api/personas/{pid}` | `persona_del()` | `web/app.py:2838` |
| PUT | `/api/personas/{pid}` | `persona_edit()` | `web/app.py:2829` |
| GET | `/api/personas/{pid}/export` | `persona_export()` | `web/app.py:2820` |
| POST | `/api/personas/{pid}/fill_appearance` | `persona_fill_appearance()` | `web/app.py:2734` |
| PUT | `/api/prompt_presets` | `save_preset()` | `web/app.py:1692` |
| POST | `/api/prompt_presets/import` | `import_preset()` | `web/app.py:1728` |
| DELETE | `/api/prompt_presets/{name}` | `del_preset()` | `web/app.py:1742` |
| GET | `/api/prompt_presets/{name}/export` | `export_preset()` | `web/app.py:1719` |
| POST | `/api/providers` | `add_provider()` | `web/app.py:2422` |
| DELETE | `/api/providers/{pid}` | `del_provider()` | `web/app.py:2501` |
| PUT | `/api/providers/{pid}` | `put_provider()` | `web/app.py:2429` |
| GET | `/api/providers/{pid}/image_models` | `image_models()` | `web/app.py:2513` |
| GET | `/api/providers/{pid}/models` | `models()` | `web/app.py:2506` |
| PUT | `/api/providers/{pid}/prompt_cache` | `put_provider_prompt_cache()` | `web/app.py:2456` |
| PUT | `/api/reasoning_effort` | `put_reasoning_effort()` | `web/app.py:1618` |
| POST | `/api/steps/{sid}/activate` | `step_activate()` | `web/app.py:6056` |
| POST | `/api/steps/{sid}/edit` | `step_edit()` | `web/app.py:6045` |
| POST | `/api/steps/{sid}/reroll` | `step_reroll()` | `web/app.py:5976` |
| DELETE | `/api/turns/{tid}` | `turn_del()` | `web/app.py:6070` |
| GET | `/api/turns/{tid}/ambience` | `turn_ambience()` | `web/app.py:6360` |
| POST | `/api/turns/{tid}/ambience` | `turn_ambience_resolve()` | `web/app.py:6377` |
| GET | `/api/turns/{tid}/backdrop` | `turn_backdrop()` | `web/app.py:6207` |
| POST | `/api/turns/{tid}/backdrop` | `turn_backdrop_generate()` | `web/app.py:6222` |
| POST | `/api/turns/{tid}/branch` | `turn_branch()` | `web/app.py:5288` |
| PUT | `/api/turns/{tid}/input` | `edit_input()` | `web/app.py:5708` |
| GET | `/api/turns/{tid}/narration` | `turn_narration_variants()` | `web/app.py:5793` |
| POST | `/api/turns/{tid}/narration` | `turn_narration_select()` | `web/app.py:5814` |
| GET | `/api/turns/{tid}/pipeline` | `pipeline_get()` | `web/app.py:5838` |
| PUT | `/api/turns/{tid}/prose` | `edit_prose()` | `web/app.py:5723` |
| POST | `/api/turns/{tid}/reroll` | `turn_reroll()` | `web/app.py:5907` |
| POST | `/api/turns/{tid}/rerun` | `turn_rerun()` | `web/app.py:5917` |
| POST | `/api/turns/{tid}/resume` | `turn_resume()` | `web/app.py:5944` |
| GET | `/api/ui` | `ui_catalog_get()` | `web/app.py:3143` |
| PUT | `/api/ui-language` | `ui_language_put()` | `web/app.py:3168` |
| GET | `/api/updates/check` | `updates_check()` | `web/app.py:2105` |
| POST | `/api/updates/install` | `updates_install()` | `web/app.py:2109` |
| GET | `/guest` | `guest_page()` | `web/app.py:513` |
| GET | `/login` | `login_page()` | `web/app.py:531` |

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
| `memories` | `id`, `chat_id`, `char_id`, `turn_id`, `turn_idx`, `kind`, `category`, `provenance`, `salience`, `content`, `gist`, `key_phrases`, `entities`, `location`, `emotional_context`, `valence`, `arousal`, `--`, `--`, `--`, `encoding_valence`, `encoding_arousal`, `confidence`, `access_count`, `last_accessed`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `last_accessed_turn`, `embedding`, `cue_embedding`, `embedding_model`, `embedding_dim`, `archived`, `event_key`, `frame_id`, `--`, `--`, `--`, `--`, `importance`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `disputed`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `--`, `encoded_at_seconds` |
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

### `static/js/app.js` (1192 lines)

Sections: Boot & sidebar (`:1`); and then nothing showed the report, so a host who installed a pack got (`:18`); New chat wizard (`:267`); NSFW (`:877`); Composer (`:905`); Init (`:983`); Embedding reconciler progress (`:1043`).

Declared functions: `boot()`, `renderSide()`, `syncExtensionTabs()`, `renderChatSidebar()`, `newChatWizard()`, `renderWizardChoice()`, `storyLanguagePacks()`, `defaultStoryLanguage()`, `wizardState()`, `wizardHistoryCharacters()`, `discardFailedStorySetup()`, `wizardFromScratch()`, `renderWizardPersona()`, `renderWizardCharacters()`, `renderWizardScenario()`, `runWizard()`, `renderCharacterSidebar()`, `renderPersonaSidebar()`, `renderLegacyLoreSidebar()`, `updateNSFWBtn()`, `toggleNSFW()`, `resizeComposer()`, `erCard()`, `erDismiss()`, `erPoll()`, `erWatch()`, `erOfferRebuild()`.

### `static/js/backdrops.js` (430 lines)

Sections: Scene backdrops (`:2`).

Declared functions: `backdropLayers()`, `backdropLuminance()`, `applyBackdropContrast()`, `releaseBackdropLayer()`, `clearBackdrop()`, `showBackdrop()`, `backdropWorking()`, `awaitBackdrop()`, `generateBackdrop()`, `backdropForTurn()`, `backdropOnVisibleTurn()`, `backdropResetForRender()`, `updateBackdropBtn()`, `toggleBackdrops()`, `syncBackdrops()`.

### `static/js/chat.js` (2911 lines)

Sections: The turn being read (`:1`); Colouring who spoke (`:172`); `dialogue_log` is committed per turn and arrives as `turn.speech` -- and (`:175`); Flipping between rerolls of the newest beat (`:978`); Pipeline drawer: reading a step through a lens (`:1292`); Pipeline drawer (`:1616`); Relationship viewer (`:1986`); Memory browser (`:2065`); Private history (`:2853`).

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

### `static/js/lorebooks.js` (3714 lines)

Sections: Library sidebar (`:252`); Data loading (`:459`); Workspace (`:556`); Book metadata and tree operations (`:1162`); Entry editor (`:1666`); Lorebook relationships (`:2436`); Advanced generator (`:2887`); Interrupted-generation recovery (`:3107`).

Declared functions: `loreBookTypeIcon()`, `loreLinkTypes()`, `normalizeLoreBook()`, `loreOwnershipKey()`, `loreBooksByParent()`, `loreBookMatches()`, `loreVisibleIds()`, `loreBookLabel()`, `parseStoredJSON()`, `loreField()`, `loreSelect()`, `loreBookOptions()`, `renderLoreLibrarySidebar()`, `renderNode()`, `loadLoreWorkspaceData()`, `collectLoreLinkTargets()`, `loreWorkspaceVisible()`, `renderLoreWorkspaceBody()`, `openLoreWorkspace()`, `renderLoreInspector()`, `selectTab()`, `buildLoreWorkspace()`, `renderWorkspaceTree()`, `renderNode()`, `renderTreeList()`, `renderLoreBookEditor()`, `moveLoreBook()`, `reorderLoreBook()`, `promoteLoreBook()`, `demoteLoreBook()`, `createSiblingLoreBook()`, `createLoreBookDialog()`, `refreshLoreUI()`, `renderLoreEntries()`, `renderList()`, `buildLoreEntryCard()`, `splitNumberList()`, `reinterpretLoreBook()`, `generateLoreEntriesPrompt()`, `buildDirectLoreRequest()`, `renderRelationshipOverview()`, `renderLoreRelationshipEditor()`, `renderRelationshipList()`, `showNewRelationshipForm()`, `renderLoreGenerator()`, `adoptGeneratorPlan()`, `generatorPlanMessage()`, `loreGenAgo()`, `refreshLoreGenRecovery()`, `normalizeGeneratorPlan()`, `renderLorePlanPreview()`, `renderOperations()`, `planStat()`, `renderAnalysisSection()`, `addPlanGroup()`, `stripPlanUIFields()`, `acceptedGeneratorPlan()`.

### `static/js/settings.js` (4030 lines)

Sections: Chat tool modals (`:1`); Condition tab (`:929`); Survival tracker (`:989`); Character relocation (`:1301`); API connections (`:2034`); Software updates (host-only; git fast-forward from GitHub origin) (`:3259`); Legacy checkpoint conversion (host-only maintenance) (`:3291`); Prompts (`:3525`); and be able to load that pack's own sheets to edit, rather than (`:3536`); Extensions (`:3703`).

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
