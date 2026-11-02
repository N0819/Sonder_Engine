# Generated Code Map

> Regenerate with `python tools/generate_code_map.py`. Do not hand-edit this file.

## Python modules

| Module | Lines | Purpose | Local dependencies |
|---|---:|---|---|
| `agents/__init__.py` | 101 | Backward-compatible facade for the role-specific agent package. | `agents.background`, `agents.character`, `agents.common`, `agents.director`, `agents.loops`, `agents.mapping`, `agents.narration`, `agents.perception`, `agents.runtime`, `agents.skip_stage`, `agents.storage`, `story.scene` |
| `agents/background.py` | 3436 |  | `agents.common`, `core.db`, `llm.prompts`, `llm.schemas`, `persist.commit`, `story.character_schema`, `story.scene`, `world.background_claims`, `world.spatial` |
| `agents/character.py` | 5485 | Private character decision agent. | `agents`, `agents.character_evidence`, `agents.common`, `agents.impossible_knowledge`, `core.db`, `core.frames`, `llm.schemas`, `mind`, `mind.affect`, `mind.memory`, `mind.memory_judge`, `mind.psychology_runtime`, `mind.theory_of_mind`, `story`, `story.character_schema`, `story.scene`, `world.gaps`, `world.place_purpose`, `world.spatial`, `world.survival` |
| `agents/character_bare.py` | 1210 |  | `agents.common`, `llm.prompts`, `mind` |
| `agents/character_evidence.py` | 146 |  | — |
| `agents/character_tools.py` | 732 |  | `core.db` |
| `agents/common.py` | 471 | Facade over the agents/common_* siblings (split 2026-11-01): shared normalization, lore, delivery, and perception helpers. | `agents.common_acts`, `agents.common_authority`, `agents.common_base`, `agents.common_beat`, `agents.common_bodies`, `agents.common_cast`, `agents.common_fidelity`, `agents.common_figures`, `agents.common_identity`, `agents.common_llm`, `agents.common_names`, `agents.common_narration`, `agents.common_rooms`, `agents.common_scrubs`, `agents.common_sequence`, `agents.common_views`, `core.db`, `core.pipeline_context`, `llm.llm_quality`, `llm.prompts`, `llm.providers`, `llm.schemas`, `mind.memory`, `mind.theory_of_mind`, `story`, `story.character_schema`, `story.provenance_text`, `story.scene`, `world`, `world.spatial` |
| `agents/common_acts.py` | 1312 | What a declared element is: act classification, communicative-act vocabulary, claim dispositions, target binding, the reaction/resolution gates. | `agents.common_base`, `agents.common_cast`, `agents.common_names`, `story.character_schema` |
| `agents/common_authority.py` | 930 | Director/player authority checks on resolved prose and contacts, the presence-knowledge floor, the player-authority ladder on claims. | `agents.common_base`, `agents.common_names`, `agents.common_scrubs`, `story.character_schema`, `story.scene`, `world.spatial` |
| `agents/common_base.py` | 170 | Leaf of the common family: the 'agents.common' pack lookup, coercion, quote/typography folding, markup stripping, English third-person morphology. | — |
| `agents/common_beat.py` | 999 | The beat's bookkeeping around its minds: the plan invariant, micro-round merging, who speaks and reacts next, declared goals, asserted state. | `agents.common_acts`, `agents.common_base`, `agents.common_cast`, `core.db`, `persist.commit`, `story.character_schema`, `story.scene`, `world.spatial` |
| `agents/common_bodies.py` | 810 | What one observer perceives of a body: attire views, exposure, extra parts, per-region visibility, containment spelling, the delivery gate. | `agents.common_base`, `core.db`, `story`, `story.character_schema`, `story.scene`, `world.spatial` |
| `agents/common_cast.py` | 667 | The registered cast inside the scene: identity keys, rooms, spelling policy, entity reconciliation, position canonicalisation, exclusion lists. | `core.pipeline_context`, `story.character_schema`, `world.spatial` |
| `agents/common_fidelity.py` | 1106 | The narrator page against its records: event order, quote/action attribution, position/portal/attire fidelity, _check_narrator_fidelity. | `agents.common_base`, `agents.common_names`, `agents.common_narration`, `story.character_schema` |
| `agents/common_figures.py` | 1173 | Who stands where this beat: charter and presence figures, creature stances, planned figures, the player's room ladder and resolver, the aperture. | `agents.common_base`, `agents.common_llm`, `agents.common_rooms`, `core.db`, `core.pipeline_context`, `llm.prompts`, `llm.providers`, `story.character_schema`, `story.scene`, `world.spatial` |
| `agents/common_identity.py` | 826 | The identity floor on payloads and views: observer label functions, the name scrub, act-surface admission, the last-pass identity scrub. | `agents.common_base`, `agents.common_cast`, `agents.common_figures`, `agents.common_names`, `agents.common_rooms`, `core.db`, `core.pipeline_context`, `story.character_schema`, `story.scene`, `world.spatial` |
| `agents/common_llm.py` | 195 | The model-call seam (_agent_json) and JSON recovery (jparse, the miscounted-closer mender). | `llm.llm_quality` |
| `agents/common_names.py` | 1258 | Names in any script: name tokens and recognition, sentence splitting, subject/pronoun tracking, the stranger-label grammar. | `agents.common_base`, `story.character_schema` |
| `agents/common_narration.py` | 865 | The narrator's own voice, measured: tics, rhythm, recycled shingles, person/tense counts, the pronoun-fidelity check. | `agents.common_base`, `agents.common_names`, `story.character_schema` |
| `agents/common_rooms.py` | 860 | What a room holds for a perceiver: crowds, chatter, couriers and notices, the room's prose, the Director's lore slice, the payload room set. | `agents.common_names`, `core.db`, `mind.memory`, `story.character_schema`, `story.provenance_text`, `story.scene`, `world`, `world.spatial` |
| `agents/common_scrubs.py` | 607 | Prose repair passes: the repeated-quote cap, dangling-speech healing, the player-echo strip, the invented-dialogue scrub, sentence dedupe. | `agents.common_base`, `agents.common_names` |
| `agents/common_sequence.py` | 1258 | A declared beat as the engine holds it: speech provenance, stage-direction excision, norm_sequence, duplicate collapse, event ids, the player token. | `agents.common_acts`, `agents.common_base`, `agents.common_names`, `llm.schemas` |
| `agents/common_views.py` | 822 | Deterministic sentences composed into a view: muffling, tone, self-reference and second-person rewriting, observable predicates, the residue view. | `agents.common_base`, `agents.common_names`, `story.character_schema`, `world.spatial` |
| `agents/composer.py` | 405 | Facade over the agents/composer_* siblings (split 2026-11-01): the view renderer every perception path calls into. | `agents.common`, `agents.composer_acts`, `agents.composer_bodies`, `agents.composer_common`, `agents.composer_episode`, `agents.composer_fields`, `agents.composer_figures`, `agents.composer_landscape`, `agents.composer_person`, `agents.composer_render`, `agents.composer_speech`, `agents.composer_standing`, `agents.composer_things`, `core.pipeline_context`, `story.provenance_text`, `story.scene`, `world.spatial` |
| `agents/composer_acts.py` | 321 | An act, a substance transfer and a crossing as one observer receives them: concealment, heard movement, the sight grade, the first-person copy. | `agents.common`, `agents.composer_common`, `agents.composer_figures`, `agents.composer_person`, `agents.composer_speech`, `core.pipeline_context`, `world.spatial` |
| `agents/composer_bodies.py` | 842 | Percepts about a body: poses and referents, extra parts, appearance, tells, the observer's own state, ears, contacts, bare regions, non-awake residue. | `agents.common`, `agents.composer_common`, `agents.composer_person`, `world.spatial` |
| `agents/composer_common.py` | 380 | Leaf of the composer family: the typed IR (Percept, RenderedView), ledger keys, compositor-pack accessors, shared phrase splicers, _safe_renderer. | `world.spatial` |
| `agents/composer_episode.py` | 423 | The English reference EPISODE renderer (memory mode): first-person sentences, what files as memory, render_episode, episode_signature. | `agents.common`, `agents.composer_bodies`, `agents.composer_common`, `agents.composer_landscape`, `agents.composer_person`, `agents.composer_render`, `agents.composer_speech`, `agents.composer_standing` |
| `agents/composer_fields.py` | 986 | The place as standing sensory state: room, light and sound, authored and distant sounds, scent, a walk underway, weather, thunder, felt shakes. | `agents.composer_common`, `agents.composer_standing`, `story.provenance_text`, `world.spatial` |
| `agents/composer_figures.py` | 695 | Who is here and what this observer calls them: referring expressions, the stranger-label ladder, the sight-gated display map, presence percepts. | `agents.common`, `agents.composer_common`, `story.scene`, `world.spatial` |
| `agents/composer_landscape.py` | 605 | Far sight: vistas, far places and far looks as lines (landscape_lines), realised in any pack's words (compose_landscape_line). | `agents.composer_common` |
| `agents/composer_person.py` | 743 | Grammatical person: a third-person line turned into the observer's second person for the view and first person for memory. | `agents.common` |
| `agents/composer_render.py` | 1286 | The English reference VIEW renderer: standing and event sentences, the presence roll-call, _render_view_english slot ordering, render_view. | `agents.common`, `agents.composer_bodies`, `agents.composer_common`, `agents.composer_fields`, `agents.composer_figures`, `agents.composer_landscape`, `agents.composer_person`, `agents.composer_speech`, `agents.composer_standing` |
| `agents/composer_speech.py` | 1007 | A line as one observer receives it: concealment, addressee, the hearing gate and its rescues, voice/tone/register, silence, described communication. | `agents.common`, `agents.composer_common`, `core.pipeline_context`, `world.spatial` |
| `agents/composer_standing.py` | 482 | Standing verdicts against the observer's ledger, what leads the beat, habituation, beat order, carried voices, observations_from_render. | `agents.composer_common` |
| `agents/composer_things.py` | 388 | Things in the room: placed or in hand, readings, crowds/couriers/notices, chatter, the micro-round delivery. | `agents.composer_common` |
| `agents/director.py` | 7837 | Scene establishment, player interpretation, and objective resolution. | `agents`, `agents.common`, `agents.director_contact`, `agents.director_evidence`, `agents.director_fanout`, `agents.director_floors`, `agents.director_lingua`, `agents.director_movement`, `agents.director_reconcile`, `agents.director_scopes`, `agents.director_views`, `core.db`, `llm`, `llm.prompts`, `llm.providers`, `llm.schemas`, `mind.memory`, `story`, `story.attire`, `story.character_schema`, `story.scene`, `world.causality`, `world.mechanics`, `world.paradox`, `world.spatial`, `world.survival` |
| `agents/director_contact.py` | 640 |  | `agents.common`, `story.character_schema`, `world.spatial` |
| `agents/director_evidence.py` | 4178 |  | `agents.common`, `agents.director_lingua`, `agents.director_scopes`, `llm`, `story.character_schema`, `world.spatial` |
| `agents/director_fanout.py` | 1096 |  | `agents.common`, `agents.director_evidence`, `agents.director_scopes`, `core.db`, `story.character_schema`, `world.spatial`, `world.survival` |
| `agents/director_floors.py` | 2544 |  | `agents.common`, `agents.director_lingua`, `agents.director_movement`, `story.character_schema`, `story.scene`, `world.mechanics`, `world.spatial` |
| `agents/director_layout.py` | 798 |  | — |
| `agents/director_lingua.py` | 29 |  | — |
| `agents/director_lots.py` | 557 |  | `world.lots` |
| `agents/director_movement.py` | 3499 |  | `agents.director_lingua`, `story.character_schema`, `world.mechanics`, `world.spatial` |
| `agents/director_prose.py` | 5687 |  | `agents.director_fanout`, `agents.director_scopes`, `core.db`, `llm`, `llm.prompts`, `llm.providers`, `llm.schemas` |
| `agents/director_reconcile.py` | 559 |  | `agents.common`, `agents.director_evidence`, `agents.director_scopes`, `core.db`, `llm.schemas`, `story`, `world.spatial` |
| `agents/director_repair.py` | 1790 |  | `core.db`, `llm`, `llm.prompts` |
| `agents/director_rooms.py` | 3021 |  | — |
| `agents/director_scopes.py` | 609 |  | `agents.director_lingua`, `agents.director_views`, `core.db`, `world.survival` |
| `agents/director_views.py` | 760 |  | `agents.common`, `story.character_schema`, `story.scene`, `world.background_claims` |
| `agents/dramaturge.py` | 478 |  | `core.db`, `core.logging_utils`, `story.room_proposals` |
| `agents/impossible_knowledge.py` | 232 |  | `agents.common`, `core.db`, `story.character_schema` |
| `agents/loops.py` | 2042 | Reaction loops, interaction rounds, and deterministic micro-perception. | `agents`, `agents.character`, `agents.common`, `core.db`, `core.pipeline_context`, `story.character_schema`, `story.scene`, `world.spatial` |
| `agents/mapping.py` | 780 | Lore routing, cached recall, and retrieval staging. | `agents.common`, `core.db`, `mind.memory`, `story.scene`, `world.spatial` |
| `agents/narration.py` | 3277 | Player-facing narration agent. | `agents`, `agents.common`, `core.db`, `llm.prompts`, `llm.schemas`, `story`, `story.character_schema`, `story.scene`, `world.spatial`, `world.weather` |
| `agents/offscreen_beat.py` | 490 |  | — |
| `agents/perception.py` | 408 | Facade over the agents/perception_* siblings (split 2026-11-01): the deterministic observer views at opening, onset and outcome. | `agents`, `agents.common`, `agents.perception_bodies`, `agents.perception_common`, `agents.perception_conduct`, `agents.perception_identity`, `agents.perception_onset`, `agents.perception_opening`, `agents.perception_outcome_stage`, `agents.perception_outcome_views`, `agents.perception_scrub`, `agents.perception_senses`, `agents.perception_standing`, `agents.perception_stream`, `core.db`, `core.pipeline_context`, `mind`, `story`, `story.character_schema`, `story.scene`, `world.beat_ledger`, `world.scene_memo`, `world.spatial` |
| `agents/perception_bodies.py` | 678 | A body's outward form: the turn's disguise and transformation reads (and their caches), what a disguise conceals and its tripwire terms, authored extra parts, card scents and body descriptions, attire. | `agents.common`, `story`, `story.character_schema`, `story.scene`, `world.spatial` |
| `agents/perception_common.py` | 357 | Leaf helpers every other sibling reads: the active pack's recognizer tables and the one sentence splitter, the observer-identity test, the human-seat test, the step's player-room stamp, and the per-ob. | `agents`, `core.db`, `world.spatial` |
| `agents/perception_conduct.py` | 612 | Readers of this beat's declared conduct: rapid movement and the open-group continuity rescue, where a line was said relative to a declared walk, a crossing's legs and the channel to every leg, the bea. | `agents.perception_common`, `agents.perception_senses`, `core.db`, `story.character_schema`, `world.spatial` |
| `agents/perception_identity.py` | 889 | Who and what an observer may name: the identity roster and the chat's identity space, worn roles and charter titles, recognition and attributed labels, stranger labels and self-forms, presence bodies . | `agents`, `agents.common`, `agents.perception_bodies`, `agents.perception_common`, `core.db`, `story.character_schema`, `story.scene`, `world.spatial` |
| `agents/perception_onset.py` | 965 | The action-onset pass (pass 1): `perception_act`, its composer region (`_composer_act`, `_composer_act_views`), and `beat_player_rooms`, runtime's early reading of the same declaration. | `agents`, `agents.common`, `agents.perception_bodies`, `agents.perception_common`, `agents.perception_conduct`, `agents.perception_identity`, `agents.perception_scrub`, `agents.perception_senses`, `agents.perception_standing`, `core.db`, `core.pipeline_context`, `story.character_schema`, `story.scene`, `world.scene_memo`, `world.spatial` |
| `agents/perception_opening.py` | 449 | The opening pass: `perception_establish` and its composer region (`_composer_establish`, `_composer_establish_views`, the opening's quoted lines). | `agents`, `agents.common`, `agents.perception_bodies`, `agents.perception_common`, `agents.perception_identity`, `agents.perception_scrub`, `agents.perception_senses`, `agents.perception_standing`, `core.db`, `story.character_schema`, `story.scene`, `world.scene_memo`, `world.spatial` |
| `agents/perception_outcome_stage.py` | 374 | The outcome stage entry point `perception_outcome`: composes the beat scene once, enriches the dialogue log, builds every perceiver and hands off to `_composer_outcome`. | `agents.common`, `agents.perception_bodies`, `agents.perception_common`, `agents.perception_identity`, `agents.perception_outcome_views`, `agents.perception_senses`, `agents.perception_stream`, `core.db`, `story.character_schema`, `story.scene`, `world.scene_memo`, `world.spatial` |
| `agents/perception_outcome_views.py` | 1501 | The outcome pass's composer region: `_composer_outcome` (sweep stamp, read pass) and `_composer_outcome_views`, the 1,309-line per-observer assembler moved whole. | `agents`, `agents.common`, `agents.perception_bodies`, `agents.perception_common`, `agents.perception_conduct`, `agents.perception_identity`, `agents.perception_scrub`, `agents.perception_senses`, `agents.perception_standing`, `agents.perception_stream`, `core.pipeline_context`, `story.character_schema`, `story.scene`, `world.scene_memo`, `world.spatial` |
| `agents/perception_scrub.py` | 902 | What a composed view may say and how it is finished: the self-narration strip and its quote-safe wrapper, the identity scrubs over act surfaces, authored prose and episodes, the composer tripwires and. | `agents`, `agents.common`, `agents.perception_common`, `agents.perception_identity`, `story.character_schema`, `world.spatial` |
| `agents/perception_senses.py` | 1165 | What reaches one observer's eyes and ears: the per-source sight and channel maps, sight detail and plain view, rooms behind and in view, the per-stage sound field, sleepers' hearing, ear cover and bla. | `agents`, `agents.common`, `agents.perception_common`, `core.db`, `core.pipeline_context`, `story.character_schema`, `story.scene`, `world.spatial` |
| `agents/perception_standing.py` | 1287 | One observer's standing state and its assembler: things read by hand, station or look, visible features, things and openings (with beam-lit rooms), scents, gated ambient events, the bare-region rows, . | `agents`, `agents.common`, `agents.perception_bodies`, `agents.perception_senses`, `story.scene`, `world.spatial` |
| `agents/perception_stream.py` | 1076 | The outcome beat as one ordered stream and the signs placed in it: settled declarations, causal spans and restored lines, the world-ordered stream, unanswered addresses, background beats, and the tell. | `agents`, `agents.common`, `agents.perception_scrub`, `agents.perception_senses`, `core.db`, `core.pipeline_context`, `mind`, `story.character_schema`, `story.scene`, `world.beat_ledger`, `world.spatial` |
| `agents/runtime.py` | 2415 | Pipeline plans, dispatch, streaming, cancellation, resume, and reruns. | `agents`, `agents.background`, `agents.character`, `agents.common`, `agents.director`, `agents.loops`, `agents.mapping`, `agents.narration`, `agents.perception`, `agents.skip_stage`, `agents.storage`, `core.db`, `core.pipeline_context`, `llm.providers`, `persist.checkpoints`, `persist.commit`, `story.character_schema`, `story.scene` |
| `agents/skip_stage.py` | 1247 |  | `core.db`, `llm.providers`, `world` |
| `agents/skip_work.py` | 793 |  | `world` |
| `agents/storage.py` | 103 | Step and active-variant persistence helpers. | `core.db`, `persist.steps` |
| `agents/story_planner.py` | 3520 |  | `core.db`, `core.logging_utils`, `story.room_calls` |
| `core/__init__.py` | 6 |  | — |
| `core/code_version.py` | 205 |  | `core.paths` |
| `core/db.py` | 3229 | SQLite schema, migrations, connection management, transactions, and key/value world access. | `core.paths` |
| `core/frames.py` | 299 |  | `core.db` |
| `core/jobs.py` | 529 |  | `core.logging_utils` |
| `core/logging_utils.py` | 122 | Structured timing and observability helpers. | — |
| `core/outofband.py` | 393 |  | `core.logging_utils` |
| `core/paths.py` | 32 |  | — |
| `core/pipeline_context.py` | 625 | Typed mutable context passed through a turn pipeline. | `core.db` |
| `core/updates.py` | 399 |  | `core.paths` |
| `dressing/__init__.py` | 6 |  | — |
| `dressing/ambience.py` | 2144 |  | `core`, `core.db`, `core.paths`, `dressing.backdrops`, `world.spatial`, `world.weather` |
| `dressing/backdrops.py` | 2029 |  | `core`, `core.db`, `core.logging_utils`, `core.paths`, `persist.steps`, `world.day_cycle`, `world.spatial`, `world.weather` |
| `llm/__init__.py` | 6 |  | — |
| `llm/decisions.py` | 364 |  | `core.db` |
| `llm/json_mend.py` | 302 |  | — |
| `llm/llm_quality.py` | 2219 | Strict JSON parsing, schema validation, and model-assisted repair. | `core.pipeline_context`, `llm.prompts`, `llm.providers`, `llm.schemas` |
| `llm/prompt_cache.py` | 79 | Provider-specific prompt-cache helpers. | `llm.providers` |
| `llm/prompts.py` | 719 | Default system prompts and prompt preset access. | `core.db` |
| `llm/providers.py` | 6210 | Provider selection, retries, streaming, cancellation, model listing, and embeddings. | `core.db`, `core.logging_utils` |
| `llm/research_providers.py` | 403 |  | `core.db` |
| `llm/schemas.py` | 7088 | Pydantic output contracts and semantic validation for agent payloads. | — |
| `mind/__init__.py` | 6 |  | — |
| `mind/affect.py` | 2642 |  | `mind.theory_of_mind` |
| `mind/affect_appraisal.py` | 282 |  | `llm`, `llm.prompts` |
| `mind/affect_mix.py` | 878 |  | — |
| `mind/affect_pass.py` | 826 |  | `llm.prompts`, `mind` |
| `mind/canon_provenance.py` | 398 |  | — |
| `mind/character_jev.py` | 1188 |  | `llm`, `llm.prompts`, `mind.affect_appraisal` |
| `mind/knowledge_circles.py` | 134 |  | `core.db` |
| `mind/memory.py` | 157 | Facade re-exporting every mind.memory_* name; holds no domain code of its own. | `core`, `core.db`, `core.logging_utils`, `llm.prompts`, `llm.providers`, `mind.memory_common`, `mind.memory_context`, `mind.memory_inference`, `mind.memory_jev`, `mind.memory_links`, `mind.memory_lore_entries`, `mind.memory_lorebooks`, `mind.memory_read`, `mind.memory_relationships`, `mind.memory_retrieval`, `mind.memory_routes`, `mind.memory_snapshot`, `mind.memory_summaries`, `mind.memory_time`, `mind.memory_vectors`, `mind.memory_write`, `mind.theory_of_mind` |
| `mind/memory_common.py` | 293 | Leaf helpers shared by every memory domain: vocabularies, blob/vector codecs, FTS query, cosine. | `core.db` |
| `mind/memory_context.py` | 930 | The character memory payload: where retrieval, summaries and active state become one context. | `core.db`, `llm.prompts`, `llm.providers`, `mind.memory_common`, `mind.memory_jev`, `mind.memory_links`, `mind.memory_read`, `mind.memory_retrieval`, `mind.memory_summaries`, `mind.memory_time`, `mind.memory_write` |
| `mind/memory_inference.py` | 159 | Belief confidence at mint and at abandonment, and reconciliation across a mind's inferences. | `core.db`, `mind.memory_write`, `mind.theory_of_mind` |
| `mind/memory_jev.py` | 642 |  | `mind.memory_common`, `mind.memory_read`, `mind.memory_retrieval`, `mind.memory_write` |
| `mind/memory_judge.py` | 430 |  | `core.db`, `core.logging_utils`, `llm.prompts`, `llm.providers` |
| `mind/memory_links.py` | 289 |  | `mind.memory_common`, `mind.memory_read`, `mind.memory_write` |
| `mind/memory_lore_entries.py` | 906 | Lore entries: add/update/delete, embedding stamps and health, search_lore, per-character knowledge scoping. | `core.db`, `core.logging_utils`, `llm.providers`, `mind.memory_common`, `mind.memory_lorebooks`, `mind.memory_write` |
| `mind/memory_lorebooks.py` | 583 | The lorebook graph: hierarchy, links, inheritance modes, per-chat attachment and weights. | `core.db`, `core.logging_utils`, `mind.memory_common` |
| `mind/memory_read.py` | 471 | The one seam a mind reads its own memory through, and the host reads that deliberately cross characters. | `core`, `core.db`, `mind.memory_common`, `mind.memory_write` |
| `mind/memory_relationships.py` | 457 | The relationship graph: axis deltas from conduct and from inference, and the history behind them. | `core.db`, `mind.memory_common`, `mind.memory_write` |
| `mind/memory_retrieval.py` | 1248 | Hybrid retrieval: lexical and vector rankings fused by RRF, tilted by mood and importance, plus unbidden recall. | `core.db`, `core.logging_utils`, `llm.providers`, `mind.memory_common`, `mind.memory_read`, `mind.memory_write` |
| `mind/memory_routes.py` | 667 |  | `core.db` |
| `mind/memory_snapshot.py` | 1017 | Checkpoint and archive: vector addressing, the prepare/apply restore split, memory and lorebook dump/restore. | `core.db`, `core.logging_utils`, `llm.providers`, `mind.memory_common`, `mind.memory_lore_entries`, `mind.memory_summaries`, `mind.memory_time`, `mind.memory_write` |
| `mind/memory_summaries.py` | 826 | Autobiographical, hearsay and surmise summaries: search, support sets, windowed consolidation and backfill. | `core`, `core.db`, `llm.prompts`, `llm.providers`, `mind.memory_common`, `mind.memory_read`, `mind.memory_retrieval`, `mind.memory_write` |
| `mind/memory_time.py` | 350 |  | `core.db` |
| `mind/memory_vectors.py` | 789 | Rebuilding vectors after the embedding model changes: bank status, the rebuild, and its background run. | `core.db`, `core.logging_utils`, `llm.providers`, `mind.memory_common`, `mind.memory_retrieval`, `mind.memory_write` |
| `mind/memory_write.py` | 1083 | How a memory becomes a row: normalisation, extraction, FTS mirror, the upsert, and the embedding-repair thread. | `core.db`, `core.logging_utils`, `llm.providers`, `mind.memory_common` |
| `mind/notebook.py` | 406 |  | `mind` |
| `mind/psychology_runtime.py` | 926 |  | — |
| `mind/skip_memories.py` | 1498 |  | `core.db`, `core.logging_utils`, `llm`, `llm.prompts`, `llm.providers`, `mind.memory` |
| `mind/theory_of_mind.py` | 861 |  | — |
| `mind/thoughts.py` | 131 |  | `core.db` |
| `persist/__init__.py` | 6 |  | — |
| `persist/about_backfill.py` | 321 |  | `core.db` |
| `persist/beat_order.py` | 287 |  | `core.db` |
| `persist/chat_archive.py` | 1584 | Typed, atomic chat archive export/import service and HTTP routes. | `core.db`, `llm.schemas`, `mind.memory`, `persist.checkpoints`, `story.character_schema`, `story.room_conversation` |
| `persist/chat_delete.py` | 51 |  | `core.db` |
| `persist/checkpoints.py` | 2063 | Whole-chat snapshots and checkpoint restore orchestration. | `core.db`, `mind.memory` |
| `persist/commit.py` | 908 | Atomic commit orchestrator, per-turn lock, thin tail domains, and the facade re-exporting every commit_* name. | `core.db`, `core.frames`, `llm.prompts`, `llm.providers`, `mind`, `mind.memory`, `mind.theory_of_mind`, `persist.commit_attire`, `persist.commit_background`, `persist.commit_common`, `persist.commit_destruction`, `persist.commit_entities`, `persist.commit_ledgers`, `persist.commit_mapping`, `persist.commit_mechanics`, `persist.commit_memory`, `persist.commit_memory_write`, `persist.commit_place_graph`, `persist.commit_room_registry`, `persist.commit_scene_state`, `persist.commit_skip`, `story`, `story.character_schema`, `story.scene`, `world.comfort`, `world.mechanics`, `world.paradox`, `world.spatial`, `world.spatial_frames`, `world.survival`, `world.weather` |
| `persist/commit_attire.py` | 1824 | The mutable clothing ledger: attire notes, shed/worn garment entities, the validated attire diff. | `persist.commit_common`, `story`, `story.attire`, `world.spatial` |
| `persist/commit_background.py` | 5936 | Background presences: tracking, identity folding, the reactor gate, promotion to cast. | `core.db`, `mind.memory`, `persist.commit_common`, `story.character_schema`, `story.scene`, `world.spatial`, `world.survival` |
| `persist/commit_common.py` | 738 | Leaf helpers shared across commit domains: scalar utilities, name/address roster, entity-id canonicalisation. | `core.db`, `mind.memory`, `story.character_schema`, `world.mechanics`, `world.spatial` |
| `persist/commit_destruction.py` | 414 | Single- and multi-book destruction cascades, retirement, and latency-gated news. | `core.db`, `mind.memory`, `persist.commit_common`, `world.mechanics`, `world.spatial`, `world.spatial_frames` |
| `persist/commit_entities.py` | 826 | world_entities projection of the scene commit, awareness gate, disguise supersession. | `core.db`, `persist.commit_common`, `story.character_schema`, `story.scene`, `world.spatial` |
| `persist/commit_ledgers.py` | 282 | The world-pressure ledger. | `core.db`, `core.pipeline_context`, `persist.commit_common` |
| `persist/commit_mapping.py` | 860 | Lore/book mapping commit: book ops, lore ops, canon fallback ops, offscreen-event normaliser. | `core.db`, `core.frames`, `mind.memory`, `persist.commit_common`, `story.character_schema`, `story.provenance_text`, `world.spatial` |
| `persist/commit_mechanics.py` | 524 | Transit/news sweeps, the world-event spine, information carriers, cast changes. | `core.db`, `persist.commit_common`, `persist.commit_scene_state`, `story.character_schema`, `story.scene`, `world.mechanics` |
| `persist/commit_memory.py` | 2611 | Pre-lock memory preparation: per-mind memories and the psychology deltas riding with them. | `core.db`, `mind`, `mind.memory`, `mind.theory_of_mind`, `persist.commit_background`, `persist.commit_common`, `persist.commit_place_graph`, `story.character_schema`, `world.charter`, `world.comfort`, `world.exposure`, `world.spatial`, `world.stimulation`, `world.survival` |
| `persist/commit_memory_write.py` | 455 | The durable memory write and its out-of-band consolidation twin. | `core.db`, `mind.memory`, `persist.commit_memory`, `story.character_schema`, `story.scene` |
| `persist/commit_place_graph.py` | 336 | Per-mind durable place graph and per-beat spatial experience. | `world.spatial` |
| `persist/commit_room_registry.py` | 662 | Room identity across frames: registry projection, mint dedup, renames, retirement, exit pruning. | `core.db`, `persist.commit_common`, `story.character_schema`, `world.spatial` |
| `persist/commit_scene_state.py` | 3165 | The prepared post-turn scene: pre-lock build, scene commit domain, book anchoring, ground advance. | `core.db`, `core.pipeline_context`, `mind.memory`, `persist.commit_attire`, `persist.commit_common`, `persist.commit_destruction`, `persist.commit_room_registry`, `story.character_schema`, `story.provenance_text`, `world.beat_ledger`, `world.landscape`, `world.mechanics`, `world.planned_entities`, `world.spatial`, `world.spatial_frames`, `world.structure`, `world.weather` |
| `persist/commit_skip.py` | 126 |  | `core.db` |
| `persist/llm_capture.py` | 623 |  | `core.db` |
| `persist/pipeline_trace.py` | 635 | Privacy-conscious export, validation, and offline replay of persisted pipeline history. | `core.db` |
| `persist/steps.py` | 150 |  | `core.db` |
| `story/__init__.py` | 6 |  | — |
| `story/artifacts.py` | 719 |  | `llm.prompts` |
| `story/attire.py` | 3902 |  | — |
| `story/authored_events.py` | 373 |  | `core.db` |
| `story/carriers.py` | 1490 |  | `core.db`, `core.logging_utils`, `story.character_schema`, `story.scene`, `world`, `world.spatial` |
| `story/character_schema.py` | 2848 | Versioned character/persona defaults, normalization, accessors, and export payloads. | `llm.schemas`, `story` |
| `story/couriers.py` | 1251 |  | `story.carriers`, `world` |
| `story/dialogue_colors.py` | 268 |  | — |
| `story/greetings.py` | 1367 |  | `agents.runtime`, `core`, `core.db`, `core.logging_utils`, `llm.llm_quality`, `llm.prompts`, `mind.affect_pass`, `mind.memory`, `mind.theory_of_mind`, `persist.steps`, `story.character_schema`, `story.importers`, `world.charter_runtime` |
| `story/history_routing.py` | 224 |  | — |
| `story/importers.py` | 3485 | Native and AI-assisted character, persona, and lorebook import/generation. | `core.db`, `core.logging_utils`, `llm.prompts`, `llm.providers`, `mind.memory`, `story.character_schema`, `story.scene` |
| `story/journey_history.py` | 514 |  | — |
| `story/location_design.py` | 577 |  | `core.db` |
| `story/lore_structure.py` | 253 |  | — |
| `story/mandates.py` | 903 |  | `core.db` |
| `story/naming.py` | 555 |  | `core.db`, `world.charter_identity` |
| `story/opening_plan.py` | 128 |  | `core.db` |
| `story/plot_packages.py` | 4919 |  | `core.logging_utils`, `world.spatial` |
| `story/prelude.py` | 189 |  | `core.db` |
| `story/provenance_text.py` | 152 |  | — |
| `story/room_bible.py` | 447 |  | `core.db` |
| `story/room_calls.py` | 249 |  | — |
| `story/room_citations.py` | 235 |  | — |
| `story/room_conversation.py` | 597 |  | `core.db` |
| `story/room_frontier.py` | 726 |  | `core.db` |
| `story/room_proposals.py` | 928 |  | `core.db` |
| `story/room_research.py` | 376 |  | `core.db` |
| `story/room_sketch.py` | 1252 |  | `core.logging_utils` |
| `story/room_slice.py` | 561 |  | `story.attire` |
| `story/room_tools.py` | 1841 |  | `story.plot_packages`, `story.room_research`, `story.room_slice` |
| `story/scene.py` | 3257 | Scene/cast/persona helpers, recent events, dialogue configuration, and private knowledge. | `core.db`, `story`, `story.attire`, `story.character_schema`, `world.day_cycle`, `world.spatial` |
| `web/__init__.py` | 6 |  | — |
| `web/app.py` | 8695 | FastAPI application assembly, resource CRUD, turn control, and streaming endpoints. | `agents`, `agents.story_planner`, `core`, `core.db`, `core.frames`, `core.paths`, `dressing.ambience`, `dressing.backdrops`, `llm`, `llm.prompts`, `llm.providers`, `mind.memory`, `persist.chat_archive`, `persist.chat_delete`, `persist.checkpoints`, `persist.commit`, `persist.steps`, `story`, `story.character_schema`, `story.dialogue_colors`, `story.importers`, `story.prelude`, `story.scene`, `web`, `web.auth_routes`, `web.room_routes`, `web.world_routes`, `world`, `world.survival` |
| `web/auth_routes.py` | 279 | Typed host-authentication HTTP routes and cookie transport. | `web` |
| `web/guest_access.py` | 554 |  | `core.db` |
| `web/pipeline_views.py` | 42 |  | `agents.composer` |
| `web/room_routes.py` | 119 |  | `core.db`, `story` |
| `web/storey_plan.py` | 306 |  | — |
| `web/story_view.py` | 1024 |  | `core.db`, `persist.steps`, `world.charter_runtime` |
| `web/world_routes.py` | 2989 |  | `core`, `core.db`, `persist.commit`, `story`, `story.attire`, `story.character_schema`, `story.scene`, `world.charter`, `world.charter_runtime`, `world.spatial`, `world.weather` |
| `world/__init__.py` | 6 |  | — |
| `world/background_claims.py` | 598 |  | `core.db` |
| `world/beat_ledger.py` | 185 |  | — |
| `world/causal_completion.py` | 165 |  | `world.causal_verification` |
| `world/causal_program.py` | 449 |  | — |
| `world/causal_verification.py` | 1252 |  | — |
| `world/causality.py` | 405 |  | `world.spatial` |
| `world/charter.py` | 524 |  | `world.charter_author`, `world.charter_chatter`, `world.charter_commitment`, `world.charter_decide`, `world.charter_drift`, `world.charter_economy`, `world.charter_feel`, `world.charter_figure`, `world.charter_identity`, `world.charter_intervene`, `world.charter_log`, `world.charter_mark`, `world.charter_mind`, `world.charter_model`, `world.charter_move`, `world.charter_needs`, `world.charter_news`, `world.charter_place`, `world.charter_plan`, `world.charter_politics`, `world.charter_practice`, `world.charter_promote`, `world.charter_roster`, `world.charter_run`, `world.charter_social`, `world.charter_space`, `world.charter_talk`, `world.charter_temper`, `world.charter_trigger` |
| `world/charter_author.py` | 813 |  | `world.charter_commitment`, `world.charter_economy`, `world.charter_figure`, `world.charter_mark`, `world.charter_mind`, `world.charter_model`, `world.charter_needs`, `world.charter_politics`, `world.charter_practice` |
| `world/charter_chatter.py` | 487 |  | `world.crowds` |
| `world/charter_commitment.py` | 298 |  | `world.charter_model` |
| `world/charter_creature.py` | 478 |  | `world.charter_harm`, `world.charter_model` |
| `world/charter_crowd.py` | 374 |  | `world.crowds` |
| `world/charter_decide.py` | 281 |  | `world.charter_model`, `world.charter_news` |
| `world/charter_drift.py` | 106 |  | `world.charter_model` |
| `world/charter_economy.py` | 460 |  | `world.charter_model` |
| `world/charter_enrol.py` | 433 |  | `world.charter_generate`, `world.charter_model`, `world.charter_needs`, `world.charter_roster`, `world.charter_surface` |
| `world/charter_feel.py` | 478 |  | `mind.psychology_runtime`, `world.charter_harm`, `world.charter_mark`, `world.charter_needs`, `world.charter_temper` |
| `world/charter_figure.py` | 140 |  | — |
| `world/charter_generate.py` | 1954 |  | `world.charter_identity`, `world.charter_model`, `world.charter_needs`, `world.charter_roster`, `world.charter_surface` |
| `world/charter_harm.py` | 285 |  | — |
| `world/charter_history.py` | 914 |  | — |
| `world/charter_identity.py` | 1290 |  | — |
| `world/charter_intervene.py` | 379 |  | `world.charter_model` |
| `world/charter_log.py` | 543 |  | `world.charter_commitment`, `world.charter_decide`, `world.charter_economy`, `world.charter_feel`, `world.charter_harm`, `world.charter_mark`, `world.charter_mind`, `world.charter_model`, `world.charter_needs`, `world.charter_news`, `world.charter_politics`, `world.charter_social`, `world.charter_temper` |
| `world/charter_mark.py` | 302 |  | — |
| `world/charter_mind.py` | 262 |  | — |
| `world/charter_model.py` | 972 |  | `world.charter_chatter`, `world.charter_figure`, `world.charter_harm`, `world.charter_mark` |
| `world/charter_move.py` | 758 |  | `world.charter_needs`, `world.charter_space` |
| `world/charter_needs.py` | 615 |  | `world.charter_model` |
| `world/charter_news.py` | 565 |  | `world.charter_mind`, `world.charter_model`, `world.charter_talk` |
| `world/charter_observe.py` | 709 |  | `world.charter_figure`, `world.charter_harm`, `world.charter_identity`, `world.charter_mind`, `world.spatial` |
| `world/charter_ops.py` | 424 |  | `world.charter_harm` |
| `world/charter_place.py` | 692 |  | `world.charter_harm`, `world.charter_identity`, `world.charter_model`, `world.charter_move`, `world.spatial` |
| `world/charter_plan.py` | 234 |  | `world.charter_drift`, `world.charter_model`, `world.charter_roster` |
| `world/charter_politics.py` | 161 |  | — |
| `world/charter_practice.py` | 1207 |  | `world.charter_commitment`, `world.charter_figure`, `world.charter_mind`, `world.charter_needs`, `world.charter_politics`, `world.charter_social`, `world.charter_talk` |
| `world/charter_predation.py` | 1085 |  | `world.charter_creature`, `world.charter_harm`, `world.charter_model`, `world.charter_move` |
| `world/charter_promote.py` | 670 |  | `world.charter_commitment`, `world.charter_feel`, `world.charter_politics`, `world.charter_social` |
| `world/charter_roster.py` | 134 |  | `world.charter_model` |
| `world/charter_run.py` | 1670 |  | `world`, `world.charter_commitment`, `world.charter_decide`, `world.charter_drift`, `world.charter_economy`, `world.charter_enrol`, `world.charter_feel`, `world.charter_figure`, `world.charter_harm`, `world.charter_intervene`, `world.charter_log`, `world.charter_mark`, `world.charter_mind`, `world.charter_model`, `world.charter_move`, `world.charter_needs`, `world.charter_news`, `world.charter_plan`, `world.charter_politics`, `world.charter_practice`, `world.charter_roster`, `world.charter_social`, `world.charter_space`, `world.charter_talk`, `world.charter_trigger` |
| `world/charter_runtime.py` | 6230 |  | `core`, `core.logging_utils`, `world.charter`, `world.charter_news`, `world.charter_surface`, `world.day_cycle`, `world.mechanics`, `world.spatial` |
| `world/charter_skip.py` | 1182 |  | `core.logging_utils` |
| `world/charter_social.py` | 870 |  | `world.charter_politics` |
| `world/charter_space.py` | 337 |  | `world.spatial` |
| `world/charter_surface.py` | 364 |  | — |
| `world/charter_surgery.py` | 445 |  | — |
| `world/charter_talk.py` | 354 |  | `world.charter_mind`, `world.charter_politics`, `world.charter_roster` |
| `world/charter_temper.py` | 167 |  | — |
| `world/charter_trigger.py` | 924 |  | `world.charter_mark`, `world.charter_news`, `world.charter_practice` |
| `world/comfort.py` | 439 |  | `world.spatial` |
| `world/crowds.py` | 783 |  | `world.spatial` |
| `world/day_cycle.py` | 613 |  | — |
| `world/degradation.py` | 228 |  | — |
| `world/exposure.py` | 232 |  | `story`, `world.spatial`, `world.weather` |
| `world/frontage.py` | 1216 |  | `world.spatial` |
| `world/gaps.py` | 465 |  | `core.db`, `mind.canon_provenance`, `world.spatial`, `world.subjects` |
| `world/landscape.py` | 1861 |  | — |
| `world/layout_arrange.py` | 5212 |  | `world.layout_solver` |
| `world/layout_bridge.py` | 4205 |  | `world.layout_arrange`, `world.layout_solver`, `world.lots`, `world.structure` |
| `world/layout_solver.py` | 3525 |  | — |
| `world/living_world.py` | 359 |  | `world.mechanics` |
| `world/lots.py` | 119 |  | — |
| `world/mechanics.py` | 1688 |  | `core`, `world.spatial`, `world.spatial_frames` |
| `world/offscreen.py` | 231 |  | — |
| `world/paradox.py` | 743 |  | `core.db`, `core.frames`, `story.character_schema`, `world.spatial` |
| `world/place_names.py` | 267 |  | `world.charter_identity` |
| `world/place_purpose.py` | 655 |  | `mind.theory_of_mind`, `world.comfort`, `world.spatial`, `world.survival` |
| `world/planned_entities.py` | 819 |  | `core.db` |
| `world/planning_needs.py` | 480 |  | — |
| `world/region_events.py` | 466 |  | — |
| `world/regions.py` | 755 |  | `world.spatial` |
| `world/routines.py` | 256 |  | `world.day_cycle` |
| `world/scene_memo.py` | 206 |  | — |
| `world/site_plan.py` | 1689 |  | — |
| `world/skip_itinerary.py` | 2048 |  | `world.spatial` |
| `world/spatial.py` | 468 | Deterministic room, barrier, hearing, visibility, placement, and scene-diff logic. | `llm.schemas`, `world.spatial_barriers`, `world.spatial_contact_migration`, `world.spatial_contacts`, `world.spatial_containment`, `world.spatial_fov`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_levels`, `world.spatial_light`, `world.spatial_light_field`, `world.spatial_lint`, `world.spatial_listener`, `world.spatial_merge`, `world.spatial_orientation`, `world.spatial_pack`, `world.spatial_prose`, `world.spatial_routing`, `world.spatial_scent_field`, `world.spatial_senses`, `world.spatial_sound_field`, `world.spatial_substance`, `world.spatial_transit`, `world.spatial_walk` |
| `world/spatial_barriers.py` | 1167 |  | `world.spatial_orientation` |
| `world/spatial_bubbles.py` | 674 |  | `story.scene`, `world.spatial`, `world.spatial_frames` |
| `world/spatial_contact_migration.py` | 384 |  | `story.character_schema`, `world.spatial_contacts`, `world.spatial_identity` |
| `world/spatial_contacts.py` | 2049 |  | `world.spatial_containment`, `world.spatial_identity`, `world.spatial_transit` |
| `world/spatial_containment.py` | 3897 |  | `world.spatial_barriers`, `world.spatial_identity`, `world.spatial_transit` |
| `world/spatial_fov.py` | 2802 |  | `world.scene_memo`, `world.spatial_barriers`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_orientation` |
| `world/spatial_frames.py` | 2793 |  | `core.db`, `core.frames`, `story.character_schema`, `story.scene`, `world.paradox`, `world.spatial` |
| `world/spatial_geometry.py` | 2487 |  | `story.character_schema`, `world.scene_memo`, `world.spatial_barriers`, `world.spatial_contacts`, `world.spatial_containment`, `world.spatial_identity`, `world.spatial_orientation` |
| `world/spatial_identity.py` | 1009 |  | — |
| `world/spatial_levels.py` | 250 |  | `world.spatial_orientation` |
| `world/spatial_light.py` | 855 |  | `world.scene_memo`, `world.spatial_barriers`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_orientation` |
| `world/spatial_light_field.py` | 1482 |  | `world.scene_memo`, `world.spatial_barriers`, `world.spatial_containment`, `world.spatial_fov`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_light`, `world.spatial_orientation` |
| `world/spatial_lint.py` | 858 |  | `world.spatial_barriers`, `world.spatial_fov`, `world.spatial_geometry`, `world.spatial_orientation` |
| `world/spatial_listener.py` | 782 |  | `world.spatial_sound_field` |
| `world/spatial_merge.py` | 3206 |  | `llm.schemas`, `world.spatial_barriers`, `world.spatial_contact_migration`, `world.spatial_contacts`, `world.spatial_containment`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_levels`, `world.spatial_orientation`, `world.spatial_routing`, `world.spatial_senses`, `world.spatial_substance`, `world.spatial_transit` |
| `world/spatial_orientation.py` | 479 | Bearing math and reciprocal spatial-edge normalization. | — |
| `world/spatial_pack.py` | 623 |  | `world.spatial_fov`, `world.spatial_geometry`, `world.spatial_lint` |
| `world/spatial_prose.py` | 476 |  | `world.spatial_contacts`, `world.spatial_containment`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_light` |
| `world/spatial_routing.py` | 1707 |  | `world.spatial_barriers`, `world.spatial_containment`, `world.spatial_geometry`, `world.spatial_light`, `world.spatial_orientation` |
| `world/spatial_scent_field.py` | 233 |  | `world.spatial_barriers` |
| `world/spatial_senses.py` | 2533 |  | `world.scene_memo`, `world.spatial_barriers`, `world.spatial_containment`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_light`, `world.spatial_orientation`, `world.spatial_routing` |
| `world/spatial_sound_field.py` | 5416 |  | `world.scene_memo`, `world.spatial_barriers`, `world.spatial_containment`, `world.spatial_fov`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_light_field`, `world.spatial_senses` |
| `world/spatial_substance.py` | 1198 |  | `world.spatial_contacts`, `world.spatial_identity` |
| `world/spatial_transit.py` | 1643 |  | `world.spatial_barriers`, `world.spatial_identity` |
| `world/spatial_walk.py` | 551 |  | `world.spatial_fov`, `world.spatial_geometry`, `world.spatial_identity`, `world.spatial_routing` |
| `world/stimulation.py` | 239 |  | `story`, `world.spatial` |
| `world/structure.py` | 3450 |  | `world.charter_model`, `world.frontage`, `world.lots`, `world.place_names`, `world.regions`, `world.spatial` |
| `world/subjects.py` | 520 |  | `core.db`, `mind.canon_provenance`, `world.spatial` |
| `world/survival.py` | 489 |  | `core.db` |
| `world/vistas.py` | 416 |  | — |
| `world/weather.py` | 1819 |  | — |

## Largest top-level functions

### `agents/background.py`

| Function | Start | Size |
|---|---:|---:|
| `_react_one()` | 3201 | 225 lines |
| `declare_charter_figures()` | 2912 | 209 lines |
| `_background_react()` | 1054 | 192 lines |
| `scene_life()` | 1867 | 176 lines |
| `_demanded_presences()` | 1624 | 152 lines |
| `_present_others()` | 2279 | 135 lines |
| `_player_declaration_caught()` | 562 | 130 lines |
| `_beat_for_presence()` | 694 | 106 lines |

### `agents/character.py`

| Function | Start | Size |
|---|---:|---:|
| `character_step()` | 3826 | 1660 lines |
| `_annotate_known_exits()` | 2948 | 466 lines |
| `_ground_observation_citations()` | 1903 | 293 lines |
| `_unanswered_question_note()` | 630 | 243 lines |
| `_destination_from_goals()` | 2465 | 108 lines |
| `_recent_self_moves()` | 311 | 98 lines |
| `sprint_offers()` | 3449 | 97 lines |
| `_impossible_knowledge()` | 1160 | 89 lines |

### `agents/character_bare.py`

| Function | Start | Size |
|---|---:|---:|
| `compile_bare()` | 753 | 372 lines |
| `_compile_notebook()` | 515 | 122 lines |
| `modules_for()` | 371 | 80 lines |
| `holding_from()` | 238 | 69 lines |
| `_appraisal()` | 1158 | 53 lines |
| `without_engine_numbers()` | 135 | 47 lines |
| `name_concealed_bodies()` | 712 | 39 lines |
| `anchor_tells()` | 1127 | 29 lines |

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

### `agents/common_acts.py`

| Function | Start | Size |
|---|---:|---:|
| `_extract_authority_claims()` | 1193 | 120 lines |
| `authored_other_subject()` | 797 | 90 lines |
| `prune_blocked_phase_changes()` | 605 | 80 lines |
| `observable_action_onset_text()` | 687 | 69 lines |
| `settle_sequence_dispositions()` | 512 | 61 lines |
| `_requires_reaction_phase()` | 935 | 53 lines |
| `scan_claims_for()` | 384 | 46 lines |
| `_scene_has_subject()` | 439 | 46 lines |

### `agents/common_authority.py`

| Function | Start | Size |
|---|---:|---:|
| `_check_presence_knowledge_channel()` | 344 | 116 lines |
| `_check_player_contact_authority()` | 818 | 113 lines |
| `_check_player_interiority_authority()` | 462 | 82 lines |
| `_check_player_act_authority()` | 735 | 81 lines |
| `_check_character_act_authority()` | 99 | 76 lines |
| `_check_prose_quote_authority()` | 182 | 69 lines |
| `apply_player_authority()` | 669 | 64 lines |
| `_check_character_speech_authority()` | 43 | 54 lines |

### `agents/common_base.py`

| Function | Start | Size |
|---|---:|---:|
| `_text_piece()` | 65 | 18 lines |
| `_contains_quote()` | 136 | 17 lines |
| `_dangling_speech()` | 25 | 16 lines |
| `strip_prose_markup()` | 122 | 12 lines |
| `_base_from_third_person_s()` | 159 | 12 lines |
| `_append_once()` | 89 | 9 lines |
| `_stem_token()` | 48 | 6 lines |
| `_join_text()` | 84 | 4 lines |

### `agents/common_beat.py`

| Function | Start | Size |
|---|---:|---:|
| `acted_upon_cast()` | 663 | 65 lines |
| `_asks_player()` | 335 | 64 lines |
| `validated_player_state_assertions()` | 818 | 63 lines |
| `merge_player_state_assertions()` | 914 | 63 lines |
| `_assert_plan_materialized()` | 32 | 55 lines |
| `widen_reactors_to_engaged()` | 600 | 54 lines |
| `_merge_character_results()` | 247 | 53 lines |
| `widen_reactors_to_hearers()` | 477 | 44 lines |

### `agents/common_bodies.py`

| Function | Start | Size |
|---|---:|---:|
| `observer_body_regions()` | 395 | 140 lines |
| `_perceptible_entities()` | 609 | 109 lines |
| `region_visibility()` | 293 | 100 lines |
| `_delivery_ok()` | 719 | 92 lines |
| `attire_view()` | 65 | 45 lines |
| `extra_part_phrase()` | 214 | 35 lines |
| `scene_extra_parts()` | 261 | 30 lines |
| `_subject_spellings()` | 537 | 29 lines |

### `agents/common_cast.py`

| Function | Start | Size |
|---|---:|---:|
| `cast_spelling_policy()` | 281 | 120 lines |
| `reconcile_cast_entity_names()` | 503 | 59 lines |
| `entity_room_by_name()` | 223 | 57 lines |
| `_conceal_from_targets_observer()` | 23 | 49 lines |
| `stamp_authored_interiors()` | 452 | 49 lines |
| `_cast_entity_claims()` | 403 | 47 lines |
| `ensure_cast_entities()` | 564 | 43 lines |
| `_present_cast_bodies()` | 156 | 40 lines |

### `agents/common_fidelity.py`

| Function | Start | Size |
|---|---:|---:|
| `_check_narrator_fidelity()` | 838 | 269 lines |
| `_check_quote_attribution()` | 399 | 131 lines |
| `_check_action_attribution()` | 61 | 71 lines |
| `_check_position_fidelity()` | 536 | 71 lines |
| `_check_event_order()` | 163 | 60 lines |
| `_check_speech_marking()` | 735 | 45 lines |
| `_introducing_subject()` | 354 | 43 lines |
| `_dialogue_tokens()` | 677 | 43 lines |

### `agents/common_figures.py`

| Function | Start | Size |
|---|---:|---:|
| `presence_figures_for_room()` | 55 | 324 lines |
| `present_charter_figures()` | 589 | 115 lines |
| `player_room_in()` | 920 | 90 lines |
| `rooms_in_view()` | 1012 | 86 lines |
| `_resolve_player_room()` | 830 | 77 lines |
| `lay_charter_figures()` | 411 | 61 lines |
| `beat_people_rows()` | 474 | 56 lines |
| `_creature_stance()` | 532 | 55 lines |

### `agents/common_identity.py`

| Function | Start | Size |
|---|---:|---:|
| `_scrub_unknown_identities()` | 593 | 234 lines |
| `observer_label_fn()` | 135 | 100 lines |
| `observer_name_scrub()` | 237 | 92 lines |
| `_act_surface_admission()` | 499 | 92 lines |
| `observer_view_label_fn()` | 57 | 60 lines |
| `_other_peoples_names()` | 331 | 57 lines |
| `scene_figures()` | 429 | 45 lines |
| `scrub_names_deep()` | 397 | 30 lines |

### `agents/common_llm.py`

| Function | Start | Size |
|---|---:|---:|
| `jparse()` | 139 | 57 lines |
| `_agent_json()` | 15 | 48 lines |
| `_mend_closers()` | 94 | 43 lines |
| `_closer_runs()` | 69 | 23 lines |

### `agents/common_names.py`

| Function | Start | Size |
|---|---:|---:|
| `_summary_label()` | 471 | 196 lines |
| `_cap_phrase()` | 344 | 125 lines |
| `_sentence_subjects()` | 1057 | 87 lines |
| `_unknown_actor_label()` | 259 | 57 lines |
| `_label_features()` | 687 | 56 lines |
| `split_sentences()` | 997 | 53 lines |
| `_subject_opener()` | 920 | 52 lines |
| `_predicate_heads()` | 1149 | 49 lines |

### `agents/common_narration.py`

| Function | Start | Size |
|---|---:|---:|
| `_check_pronoun_fidelity()` | 495 | 115 lines |
| `_overused_phrases()` | 123 | 80 lines |
| `_rhythm_report()` | 238 | 70 lines |
| `_check_narration_person_match()` | 703 | 58 lines |
| `_check_player_person()` | 612 | 51 lines |
| `_check_narration_tense_match()` | 825 | 41 lines |
| `_narration_tense_counts()` | 787 | 36 lines |
| `_person_marker_counts()` | 458 | 35 lines |

### `agents/common_rooms.py`

| Function | Start | Size |
|---|---:|---:|
| `chatter_for_room()` | 484 | 124 lines |
| `crowds_for_room()` | 79 | 114 lines |
| `charter_ground_for_room()` | 296 | 79 lines |
| `chatter_inputs()` | 195 | 76 lines |
| `couriers_for_room()` | 610 | 53 lines |
| `_contextual_rooms()` | 28 | 46 lines |
| `attending_this_room()` | 436 | 46 lines |
| `_ambient_blocked_slugs()` | 721 | 27 lines |

### `agents/common_scrubs.py`

| Function | Start | Size |
|---|---:|---:|
| `_scrub_invented_dialogue()` | 327 | 154 lines |
| `_strip_player_echo()` | 188 | 101 lines |
| `_dedupe_view_sentences()` | 535 | 73 lines |
| `_cap_repeated_quotes()` | 20 | 44 lines |
| `_heal_dangling_verb()` | 84 | 22 lines |
| `_protected_view_quotes()` | 131 | 20 lines |
| `_mask_quoted_spans()` | 513 | 14 lines |
| `_length_in_units()` | 163 | 12 lines |

### `agents/common_sequence.py`

| Function | Start | Size |
|---|---:|---:|
| `norm_sequence()` | 611 | 309 lines |
| `collapse_duplicate_events()` | 261 | 103 lines |
| `fuse_speech_run()` | 1008 | 66 lines |
| `split_stage_directions()` | 167 | 63 lines |
| `cut_short_speech()` | 410 | 51 lines |
| `repair_narrated_speech()` | 1142 | 40 lines |
| `_covered_by_spans()` | 54 | 37 lines |
| `player_communicated()` | 921 | 37 lines |

### `agents/common_views.py`

| Function | Start | Size |
|---|---:|---:|
| `self_reference_forms()` | 268 | 80 lines |
| `_self_second_person()` | 350 | 68 lines |
| `_observable_predicate()` | 495 | 61 lines |
| `_compose_residue_view()` | 724 | 45 lines |
| `_inject_dialogue()` | 177 | 41 lines |
| `_action_already_rendered()` | 558 | 40 lines |
| `_inject_visible_actor()` | 655 | 39 lines |
| `_muffled_fragment()` | 95 | 37 lines |

### `agents/composer_acts.py`

| Function | Start | Size |
|---|---:|---:|
| `act_percept()` | 102 | 172 lines |
| `_peel_own_name()` | 74 | 26 lines |
| `_surface_suddenness()` | 35 | 21 lines |
| `substance_percept()` | 276 | 16 lines |
| `crossing_percept()` | 306 | 16 lines |
| `_sound_bearing_phrase()` | 58 | 14 lines |

### `agents/composer_bodies.py`

| Function | Start | Size |
|---|---:|---:|
| `pose_percepts()` | 394 | 195 lines |
| `_pose_referent()` | 249 | 122 lines |
| `appearance_percept()` | 614 | 44 lines |
| `_part_qualified()` | 131 | 42 lines |
| `_no_engine_ids()` | 205 | 42 lines |
| `_names_a_body()` | 91 | 38 lines |
| `body_part_percepts()` | 54 | 35 lines |
| `ear_percepts()` | 719 | 31 lines |

### `agents/composer_common.py`

| Function | Start | Size |
|---|---:|---:|
| `_noun_phrase()` | 294 | 53 lines |
| `_sense_graded()` | 191 | 23 lines |
| `_spliced_fragment()` | 261 | 21 lines |
| `standing_key()` | 229 | 18 lines |
| `_safe_renderer()` | 364 | 17 lines |
| `_t()` | 67 | 15 lines |
| `_pack_words()` | 92 | 14 lines |
| `_lower_lead()` | 111 | 14 lines |

### `agents/composer_episode.py`

| Function | Start | Size |
|---|---:|---:|
| `_render_episode_english()` | 244 | 139 lines |
| `_episode_sentence()` | 89 | 125 lines |
| `_observed_conduct()` | 55 | 32 lines |
| `episode_signature()` | 385 | 22 lines |
| `render_episode()` | 409 | 15 lines |
| `_files_as_memory()` | 235 | 7 lines |

### `agents/composer_fields.py`

| Function | Start | Size |
|---|---:|---:|
| `environment_percept()` | 120 | 101 lines |
| `weather_percepts()` | 682 | 95 lines |
| `ambient_percepts()` | 441 | 92 lines |
| `weather_sound_percepts()` | 862 | 81 lines |
| `scent_percepts()` | 610 | 58 lines |
| `_clean_shape()` | 46 | 42 lines |
| `sound_ceased_percept()` | 243 | 40 lines |
| `distant_sound_percepts()` | 545 | 38 lines |

### `agents/composer_figures.py`

| Function | Start | Size |
|---|---:|---:|
| `presence_percepts()` | 515 | 181 lines |
| `observer_display_map()` | 303 | 82 lines |
| `assign_stranger_labels()` | 222 | 63 lines |
| `_ordinal_label()` | 162 | 35 lines |
| `_label_core()` | 68 | 30 lines |
| `_label_from_words()` | 100 | 25 lines |
| `_size_label()` | 446 | 25 lines |
| `_ladder_of()` | 199 | 21 lines |

### `agents/composer_landscape.py`

| Function | Start | Size |
|---|---:|---:|
| `compose_landscape_line()` | 369 | 229 lines |
| `vista_percepts()` | 23 | 76 lines |
| `landscape_percepts()` | 222 | 64 lines |
| `landscape_lines()` | 304 | 63 lines |
| `landscape_look_percepts()` | 172 | 48 lines |
| `_plain_ground()` | 288 | 14 lines |
| `_beside_on_one_bearing()` | 101 | 11 lines |
| `_far_line_text()` | 161 | 9 lines |

### `agents/composer_person.py`

| Function | Start | Size |
|---|---:|---:|
| `_verbs_in_base()` | 461 | 166 lines |
| `_pose_owner_second_person()` | 59 | 97 lines |
| `_action_target_second_person()` | 158 | 73 lines |
| `own_attempt()` | 629 | 66 lines |
| `_self_first_person()` | 281 | 48 lines |
| `_first_person()` | 709 | 35 lines |
| `_fix_i_agreement()` | 254 | 25 lines |
| `_opens_an_object()` | 415 | 23 lines |

### `agents/composer_render.py`

| Function | Start | Size |
|---|---:|---:|
| `_render_view_english()` | 933 | 297 lines |
| `_render_presence_group()` | 292 | 106 lines |
| `_render_standing()` | 662 | 99 lines |
| `_render_openings()` | 555 | 96 lines |
| `_render_event()` | 844 | 87 lines |
| `_presence_clause()` | 218 | 72 lines |
| `render_view()` | 1232 | 55 lines |
| `_render_pose()` | 451 | 50 lines |

### `agents/composer_speech.py`

| Function | Start | Size |
|---|---:|---:|
| `speech_percept()` | 361 | 292 lines |
| `line_hear_level()` | 108 | 130 lines |
| `communication_percept()` | 964 | 44 lines |
| `_carried_tone()` | 737 | 35 lines |
| `own_name_forms()` | 828 | 33 lines |
| `_names_kept()` | 884 | 32 lines |
| `silence_percept()` | 932 | 30 lines |
| `_one_voice_each()` | 331 | 28 lines |

### `agents/composer_standing.py`

| Function | Start | Size |
|---|---:|---:|
| `perception_packet()` | 418 | 65 lines |
| `standing_verdicts()` | 28 | 53 lines |
| `observations_from_render()` | 364 | 52 lines |
| `player_view_order()` | 241 | 26 lines |
| `compact_observation()` | 338 | 24 lines |
| `leads_the_beat()` | 124 | 23 lines |
| `asked_this_beat()` | 106 | 16 lines |
| `appearance_delta()` | 90 | 14 lines |

### `agents/composer_things.py`

| Function | Start | Size |
|---|---:|---:|
| `room_content_percepts()` | 194 | 83 lines |
| `chatter_percepts()` | 279 | 51 lines |
| `thing_reading_percepts()` | 154 | 38 lines |
| `thing_clause()` | 25 | 34 lines |
| `thing_reading_text()` | 120 | 32 lines |
| `micro_round_percepts()` | 361 | 28 lines |
| `micro_round_percept()` | 332 | 27 lines |
| `thing_in_hand_clause()` | 61 | 13 lines |

### `agents/director.py`

| Function | Start | Size |
|---|---:|---:|
| `director_resolve()` | 5417 | 2387 lines |
| `director_interpret()` | 1828 | 952 lines |
| `_reconcile_resolution()` | 3133 | 521 lines |
| `_run_specialists()` | 3719 | 425 lines |
| `director_establish()` | 382 | 219 lines |
| `_reconcile_interpretation()` | 2807 | 172 lines |
| `_ground_public_evidence()` | 4291 | 124 lines |
| `_causal_event_inputs()` | 4485 | 102 lines |

### `agents/director_contact.py`

| Function | Start | Size |
|---|---:|---:|
| `_validated_player_contact_assertions()` | 78 | 168 lines |
| `_merge_player_contact_assertions()` | 343 | 96 lines |
| `_player_contacts_held()` | 282 | 59 lines |
| `_validated_character_contact_endings()` | 441 | 58 lines |
| `_character_material_effects()` | 507 | 52 lines |
| `_merge_character_contact_endings()` | 598 | 43 lines |
| `_merge_character_material_effects()` | 561 | 35 lines |
| `_carries_player_authority()` | 248 | 32 lines |

### `agents/director_evidence.py`

| Function | Start | Size |
|---|---:|---:|
| `_evidence_present()` | 2065 | 359 lines |
| `causal_world_index()` | 3266 | 315 lines |
| `normalize_causal_ledger()` | 2867 | 294 lines |
| `restore_declared_quotes()` | 2652 | 163 lines |
| `beat_event_ledger()` | 1310 | 123 lines |
| `beat_timeline()` | 1197 | 111 lines |
| `_fold_derived_manifest_events()` | 4090 | 89 lines |
| `_span_items()` | 3717 | 86 lines |

### `agents/director_fanout.py`

| Function | Start | Size |
|---|---:|---:|
| `_specialist_payload()` | 584 | 321 lines |
| `_resolve_beat_view()` | 58 | 129 lines |
| `_interpret_beat_view()` | 199 | 56 lines |
| `_resolved_event_verdicts()` | 1006 | 54 lines |
| `_specialist_span_slice()` | 275 | 47 lines |
| `_beat_rooms()` | 392 | 40 lines |
| `_grid_view()` | 351 | 39 lines |
| `addressed_house()` | 522 | 36 lines |

### `agents/director_floors.py`

| Function | Start | Size |
|---|---:|---:|
| `_bind_minted_entities_to_present_figures()` | 1867 | 277 lines |
| `_stand_touching_figures()` | 1641 | 153 lines |
| `resolve_concealment_refs()` | 2207 | 121 lines |
| `_conditions_view()` | 598 | 103 lines |
| `strip_addressee_concealment()` | 2356 | 102 lines |
| `_awareness_exits()` | 734 | 98 lines |
| `_release_attempts()` | 996 | 93 lines |
| `_refuse_minted_cast_doubles()` | 2460 | 85 lines |

### `agents/director_layout.py`

| Function | Start | Size |
|---|---:|---:|
| `_lay_out_each()` | 692 | 107 lines |
| `lay_out()` | 276 | 69 lines |
| `lay_out_buildings()` | 645 | 45 lines |
| `_named_by_labels()` | 406 | 41 lines |
| `architect_lore()` | 567 | 41 lines |
| `_take_off_what_is_not_laid()` | 234 | 40 lines |
| `_lore_index()` | 496 | 34 lines |
| `lay_out_opening_ground()` | 610 | 33 lines |

### `agents/director_lingua.py`

| Function | Start | Size |
|---|---:|---:|
| `_ling()` | 16 | 14 lines |

### `agents/director_lots.py`

| Function | Start | Size |
|---|---:|---:|
| `planned_rooms_of()` | 134 | 164 lines |
| `expand_lot()` | 388 | 67 lines |
| `deal_berths()` | 329 | 57 lines |
| `expand_entered_lots()` | 498 | 53 lines |
| `lots_near()` | 457 | 26 lines |
| `lot_people()` | 61 | 24 lines |
| `lot_payload()` | 108 | 24 lines |
| `_door()` | 87 | 19 lines |

### `agents/director_movement.py`

| Function | Start | Size |
|---|---:|---:|
| `_apply_following_movement()` | 1694 | 452 lines |
| `_reconcile_near_group_positions()` | 311 | 289 lines |
| `_travel_continues()` | 3025 | 216 lines |
| `walk_within_room()` | 2753 | 143 lines |
| `walk_declared()` | 2585 | 136 lines |
| `_guard_approach_is_not_arrival()` | 3336 | 103 lines |
| `follow_through_the_steps()` | 1482 | 91 lines |
| `_walk_short_of()` | 3243 | 91 lines |

### `agents/director_prose.py`

| Function | Start | Size |
|---|---:|---:|
| `run()` | 5152 | 402 lines |
| `a_walk_is_its_owners()` | 2293 | 252 lines |
| `encode()` | 4407 | 154 lines |
| `select_channels()` | 695 | 146 lines |
| `the_account_places_its_own_body()` | 2839 | 135 lines |
| `a_line_is_heard_never_sounded()` | 3700 | 95 lines |
| `entity_keys_name_held_things()` | 3803 | 86 lines |
| `rooms_named_by_part()` | 1036 | 83 lines |

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
| `_check_and_repair()` | 1583 | 197 lines |
| `apply_answers()` | 1439 | 93 lines |
| `battery()` | 665 | 88 lines |
| `_repair_group()` | 1170 | 88 lines |
| `plan_jobs()` | 791 | 75 lines |
| `native_failures()` | 391 | 64 lines |
| `continuation()` | 1008 | 57 lines |
| `sentences()` | 125 | 45 lines |

### `agents/director_rooms.py`

| Function | Start | Size |
|---|---:|---:|
| `design_rooms()` | 1850 | 267 lines |
| `_predevelop_run()` | 2820 | 202 lines |
| `_doorways_that_fit()` | 1298 | 176 lines |
| `_derive_far_bearings()` | 1038 | 103 lines |
| `_check()` | 416 | 101 lines |
| `_pack()` | 760 | 98 lines |
| `_place_doorways()` | 926 | 92 lines |
| `_groundwork()` | 1586 | 82 lines |

### `agents/director_scopes.py`

| Function | Start | Size |
|---|---:|---:|
| `_gate_facts()` | 399 | 79 lines |
| `manifest_category_targets()` | 558 | 50 lines |
| `note_key_targets()` | 511 | 45 lines |
| `_rebuild_channel_owners()` | 287 | 25 lines |
| `_schema_list_channels()` | 221 | 23 lines |
| `_note_key_forms()` | 489 | 20 lines |
| `reads_dialogue()` | 131 | 18 lines |
| `channel_serves_stage()` | 271 | 4 lines |

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
| `revise()` | 427 | 52 lines |
| `player_visible_stream()` | 169 | 43 lines |
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
| `interaction_loop()` | 1153 | 808 lines |
| `deterministic_micro_perception()` | 331 | 284 lines |
| `rehydrate_loop_views()` | 108 | 82 lines |
| `reaction_loop()` | 1962 | 81 lines |
| `_lines_left_with_player()` | 859 | 59 lines |
| `self_micro_view()` | 236 | 54 lines |
| `_reaction_owed()` | 808 | 49 lines |
| `_beat_onset_scene()` | 960 | 48 lines |

### `agents/mapping.py`

| Function | Start | Size |
|---|---:|---:|
| `compile_world_context()` | 527 | 219 lines |
| `rulebook_rows()` | 401 | 124 lines |
| `_transit_destination_needs()` | 169 | 92 lines |
| `classify_movement()` | 276 | 71 lines |
| `_location_query_status()` | 349 | 46 lines |
| `merge_lore()` | 748 | 33 lines |
| `contained_interior_holder()` | 138 | 29 lines |
| `is_contained_destination()` | 100 | 27 lines |

### `agents/narration.py`

| Function | Start | Size |
|---|---:|---:|
| `narrator()` | 2418 | 556 lines |
| `_ordered_beat_events()` | 1189 | 252 lines |
| `_sensory_channels_manifest()` | 825 | 241 lines |
| `narrator_extra()` | 3047 | 231 lines |
| `_visible_portal_states()` | 1576 | 137 lines |
| `_generate_narration()` | 2223 | 89 lines |
| `_position_delta_payload()` | 1487 | 87 lines |
| `_page_identity_scrub()` | 523 | 80 lines |

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

### `agents/perception_bodies.py`

| Function | Start | Size |
|---|---:|---:|
| `_subject_disguise_context()` | 268 | 71 lines |
| `_composer_extra_parts()` | 369 | 45 lines |
| `_deliver_foreground_body_details()` | 163 | 43 lines |
| `_outward_form_transitions()` | 563 | 41 lines |
| `_body_descriptions()` | 440 | 40 lines |
| `_own_body_state()` | 482 | 38 lines |
| `_bare_body_details()` | 102 | 28 lines |
| `_attire_delta_text()` | 629 | 27 lines |

### `agents/perception_common.py`

| Function | Start | Size |
|---|---:|---:|
| `_standing_meta()` | 203 | 74 lines |
| `_composer_prev_ledger()` | 128 | 38 lines |
| `_stage_player_room()` | 102 | 24 lines |
| `_is_the_observer()` | 279 | 21 lines |
| `_learned_labels()` | 337 | 21 lines |
| `described_by()` | 302 | 17 lines |
| `_prior_ledger_entry()` | 321 | 14 lines |
| `_ling()` | 27 | 13 lines |

### `agents/perception_conduct.py`

| Function | Start | Size |
|---|---:|---:|
| `_previous_open_group_continuity()` | 138 | 117 lines |
| `_beat_movers()` | 390 | 41 lines |
| `_declares_rapid_movement()` | 35 | 40 lines |
| `_channel_to_every_leg()` | 489 | 36 lines |
| `_open_route_within()` | 77 | 32 lines |
| `_explicit_look_intent()` | 553 | 32 lines |
| `_speech_room_for()` | 280 | 31 lines |
| `_own_looks()` | 321 | 28 lines |

### `agents/perception_identity.py`

| Function | Start | Size |
|---|---:|---:|
| `present_label_fn()` | 752 | 138 lines |
| `_presence_bodies()` | 239 | 99 lines |
| `_composer_identity_space()` | 636 | 89 lines |
| `_co_present_company()` | 362 | 80 lines |
| `_identity_roster()` | 73 | 50 lines |
| `_composer_self_forms()` | 598 | 36 lines |
| `_composer_unknown_sources()` | 500 | 33 lines |
| `_attributed_label()` | 547 | 32 lines |

### `agents/perception_onset.py`

| Function | Start | Size |
|---|---:|---:|
| `_composer_act_views()` | 371 | 560 lines |
| `perception_act()` | 140 | 222 lines |
| `beat_player_rooms()` | 933 | 33 lines |
| `_composer_act()` | 364 | 5 lines |

### `agents/perception_opening.py`

| Function | Start | Size |
|---|---:|---:|
| `_composer_establish_views()` | 291 | 159 lines |
| `perception_establish()` | 108 | 114 lines |
| `_opening_line_percept()` | 250 | 39 lines |
| `_composer_establish()` | 244 | 4 lines |

### `agents/perception_outcome_stage.py`

| Function | Start | Size |
|---|---:|---:|
| `perception_outcome()` | 109 | 266 lines |
| `_outcome_perceiver()` | 72 | 35 lines |

### `agents/perception_outcome_views.py`

| Function | Start | Size |
|---|---:|---:|
| `_composer_outcome_views()` | 164 | 1338 lines |
| `_composer_outcome()` | 140 | 22 lines |

### `agents/perception_scrub.py`

| Function | Start | Size |
|---|---:|---:|
| `_strip_self_narration()` | 67 | 107 lines |
| `_touch_only_sources()` | 277 | 82 lines |
| `_composer_tripwires()` | 600 | 76 lines |
| `_redact_concealed_from_event()` | 393 | 72 lines |
| `_repaired_observations()` | 760 | 63 lines |
| `_strip_self_narration_quote_safe()` | 480 | 52 lines |
| `_composer_finish_observer()` | 857 | 46 lines |
| `_composer_authored_prose()` | 555 | 43 lines |

### `agents/perception_senses.py`

| Function | Start | Size |
|---|---:|---:|
| `_source_channels()` | 621 | 142 lines |
| `_sleep_hears_where()` | 355 | 120 lines |
| `_sight_detail()` | 838 | 81 lines |
| `_card_admitted()` | 234 | 49 lines |
| `_behind_rooms()` | 930 | 46 lines |
| `_dialogue_hear_level()` | 64 | 41 lines |
| `_own_name_forms()` | 285 | 34 lines |
| `_voice_sound_for()` | 1135 | 31 lines |

### `agents/perception_standing.py`

| Function | Start | Size |
|---|---:|---:|
| `_composer_standing_percepts()` | 876 | 412 lines |
| `_visible_openings()` | 652 | 159 lines |
| `_visible_things()` | 463 | 154 lines |
| `_scent_sources_for()` | 274 | 130 lines |
| `_things_read_by()` | 82 | 102 lines |
| `_gated_ambient_percepts()` | 230 | 33 lines |
| `_beam_lit_view()` | 813 | 30 lines |
| `_visible_features()` | 433 | 28 lines |

### `agents/perception_stream.py`

| Function | Start | Size |
|---|---:|---:|
| `_outcome_event_stream()` | 213 | 234 lines |
| `_delivered_manifest()` | 763 | 115 lines |
| `_unanswered_addresses()` | 513 | 110 lines |
| `_world_ordered_stream()` | 449 | 62 lines |
| `_background_beats()` | 880 | 60 lines |
| `_restore_declared_lines()` | 133 | 57 lines |
| `_cue_slots()` | 1023 | 54 lines |
| `_causal_outcome_sequences()` | 82 | 49 lines |

### `agents/runtime.py`

| Function | Start | Size |
|---|---:|---:|
| `_run_pipeline()` | 1736 | 552 lines |
| `build_plan()` | 1133 | 231 lines |
| `resume_key_for_turn()` | 1029 | 103 lines |
| `_load_extra_players()` | 59 | 101 lines |
| `run_pipeline()` | 2339 | 77 lines |
| `_stream_one()` | 603 | 68 lines |
| `_stream_parallel()` | 672 | 60 lines |
| `_run_parallel_group()` | 737 | 60 lines |

### `agents/skip_stage.py`

| Function | Start | Size |
|---|---:|---:|
| `skip_lives()` | 687 | 174 lines |
| `resolve_mind()` | 509 | 72 lines |
| `ask()` | 341 | 46 lines |
| `stretch_for_payload()` | 1194 | 46 lines |
| `judge_what_was_missing()` | 583 | 35 lines |
| `widen_reactors_to_skip_far_end()` | 1162 | 30 lines |
| `skip_block()` | 304 | 29 lines |
| `_share()` | 875 | 25 lines |

### `agents/skip_work.py`

| Function | Start | Size |
|---|---:|---:|
| `within_reach()` | 562 | 77 lines |
| `changes_of()` | 332 | 70 lines |
| `type_the_work()` | 436 | 62 lines |
| `work_payload()` | 259 | 57 lines |
| `work_scene()` | 678 | 44 lines |
| `things_changed()` | 724 | 38 lines |
| `settle_work()` | 641 | 35 lines |
| `type_mind()` | 404 | 30 lines |

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
| `run_planner()` | 1252 | 414 lines |
| `deliberate()` | 2296 | 177 lines |
| `run_fill()` | 3153 | 167 lines |
| `schedule_room_work()` | 3376 | 145 lines |
| `run_location_plan()` | 2029 | 136 lines |
| `_payload()` | 718 | 119 lines |
| `run_dramaturge_pass()` | 2495 | 112 lines |
| `_dramaturge_pass()` | 2620 | 108 lines |

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
| `init()` | 2895 | 167 lines |
| `_migrate_chat_copies_to_overlays()` | 2581 | 156 lines |
| `_recover_scene_time_of_day()` | 2825 | 59 lines |
| `transaction()` | 2403 | 43 lines |
| `conn()` | 2363 | 38 lines |
| `_opening_time_of_day()` | 2769 | 30 lines |
| `db_read_token()` | 3121 | 30 lines |
| `_establish_time_of_day_from_variant()` | 2739 | 28 lines |

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
| `cancel_from()` | 339 | 47 lines |
| `_clear_turn_scoped_context()` | 203 | 44 lines |
| `submit_latest()` | 150 | 39 lines |
| `_run()` | 249 | 39 lines |
| `story_rewound_past()` | 492 | 20 lines |
| `_finish_locked()` | 304 | 18 lines |
| `read_through()` | 388 | 18 lines |

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
| `drain_all()` | 377 | 17 lines |
| `stopped()` | 133 | 8 lines |

### `core/pipeline_context.py`

| Function | Start | Size |
|---|---:|---:|
| `sent_payload()` | 97 | 31 lines |
| `note_step_exchange()` | 130 | 23 lines |
| `canonical_movement()` | 193 | 21 lines |
| `note_step_decision()` | 176 | 14 lines |
| `note_step_warning()` | 48 | 11 lines |
| `_capturing()` | 164 | 10 lines |

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
| `resolve_ambience()` | 1727 | 222 lines |
| `_rank_candidates()` | 1124 | 105 lines |
| `refine_layers()` | 815 | 89 lines |
| `cached_ambience()` | 499 | 62 lines |
| `search_freesound()` | 1409 | 61 lines |
| `search_local()` | 926 | 54 lines |
| `acoustic_fingerprint()` | 262 | 53 lines |
| `_query_ladder()` | 1238 | 51 lines |

### `dressing/backdrops.py`

| Function | Start | Size |
|---|---:|---:|
| `generate_backdrop()` | 1827 | 116 lines |
| `room_projection()` | 1118 | 90 lines |
| `build_backdrop_request()` | 1355 | 69 lines |
| `_scene_bodies()` | 439 | 61 lines |
| `visual_signature()` | 236 | 59 lines |
| `_brief_sentences()` | 1505 | 51 lines |
| `compose_prompt()` | 1558 | 48 lines |
| `_camera_of()` | 1009 | 44 lines |

### `llm/decisions.py`

| Function | Start | Size |
|---|---:|---:|
| `decide()` | 286 | 38 lines |
| `_post()` | 144 | 35 lines |
| `_foregone()` | 240 | 22 lines |
| `capture()` | 217 | 21 lines |
| `setting()` | 88 | 19 lines |
| `_batches()` | 269 | 15 lines |
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
| `complete_validated_json()` | 1214 | 1006 lines |
| `_targeted_field_patch()` | 559 | 100 lines |
| `note_provider_exchange()` | 843 | 70 lines |
| `_read_answer()` | 449 | 66 lines |
| `_mended()` | 915 | 49 lines |
| `output_ran_out_of_room()` | 300 | 47 lines |
| `_answer_goes_on()` | 140 | 44 lines |
| `_read_json()` | 195 | 40 lines |

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
| `_encoder_pieces()` | 490 | 42 lines |
| `unified_specialist_prompt()` | 451 | 37 lines |
| `_relocate_character_identity()` | 625 | 28 lines |
| `normalize_preset()` | 116 | 26 lines |
| `_preset_override()` | 213 | 22 lines |
| `narrator_sections()` | 679 | 18 lines |
| `_director_sheets()` | 77 | 17 lines |

### `llm/providers.py`

| Function | Start | Size |
|---|---:|---:|
| `_chat_complete_once()` | 4579 | 412 lines |
| `chat_complete()` | 4200 | 180 lines |
| `_claude_cli_complete()` | 4060 | 138 lines |
| `async _chat_complete_async_once()` | 5204 | 131 lines |
| `_sse_openai()` | 3698 | 124 lines |
| `async chat_complete_async()` | 5111 | 92 lines |
| `_json_mode_recovery_stages()` | 3281 | 83 lines |
| `_sse_anthropic()` | 3823 | 83 lines |

### `llm/research_providers.py`

| Function | Start | Size |
|---|---:|---:|
| `_fetch_html()` | 294 | 44 lines |
| `_refuse_private()` | 206 | 24 lines |
| `search()` | 96 | 16 lines |
| `_peer_address()` | 232 | 15 lines |
| `_decode_page()` | 278 | 14 lines |
| `fetch()` | 114 | 11 lines |
| `html_to_text()` | 163 | 10 lines |
| `_page_charset()` | 266 | 10 lines |

### `llm/schemas.py`

| Function | Start | Size |
|---|---:|---:|
| `preprocess_llm_output()` | 5744 | 294 lines |
| `_lenient_coerce()` | 1008 | 159 lines |
| `validate_llm_output_strict()` | 6951 | 138 lines |
| `semantic_output_errors()` | 6571 | 132 lines |
| `canonicalize_prose_markup()` | 5510 | 102 lines |
| `_coerce_station_table()` | 85 | 81 lines |
| `_uncross_concealed_speech()` | 5634 | 69 lines |
| `_coerce_list_valued_map()` | 168 | 57 lines |

### `mind/affect.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_intent_ops()` | 1319 | 193 lines |
| `resolve_affect()` | 816 | 189 lines |
| `appraise()` | 499 | 145 lines |
| `settle_intent_world_anchors()` | 1574 | 132 lines |
| `normalize_wants()` | 1011 | 118 lines |
| `apply_project_ops()` | 1833 | 99 lines |
| `update_drive_strain()` | 2275 | 86 lines |
| `validate_drive_shift()` | 2404 | 79 lines |

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
| `surface_and_undercurrent()` | 817 | 55 lines |
| `targets()` | 628 | 48 lines |
| `rested_away()` | 760 | 26 lines |
| `emotions_from_appraisal()` | 337 | 25 lines |
| `memory_emotions()` | 449 | 21 lines |
| `formed()` | 518 | 19 lines |
| `decay()` | 608 | 18 lines |

### `mind/affect_pass.py`

| Function | Start | Size |
|---|---:|---:|
| `feel_seeded()` | 753 | 65 lines |
| `memories_from()` | 242 | 50 lines |
| `before_call()` | 460 | 48 lines |
| `_recall()` | 510 | 48 lines |
| `psychology_text()` | 377 | 31 lines |
| `feelings_block()` | 718 | 31 lines |
| `why_read()` | 317 | 30 lines |
| `state_text()` | 428 | 28 lines |

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
| `after_questions()` | 647 | 317 lines |
| `state_text()` | 408 | 57 lines |
| `heard_question()` | 1119 | 44 lines |
| `moment_questions()` | 563 | 34 lines |
| `grade_point()` | 1019 | 30 lines |
| `tells_asked()` | 275 | 25 lines |
| `belief_pair_questions()` | 1071 | 22 lines |
| `notes_in_play()` | 378 | 21 lines |

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
| `build_character_memory_context()` | 295 | 624 lines |
| `_with_reading()` | 30 | 121 lines |
| `_origin_on_drift()` | 177 | 95 lines |
| `_slice()` | 274 | 12 lines |
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
| `memory_net()` | 240 | 124 lines |
| `jev_ponder_packet()` | 531 | 77 lines |
| `jev_memory_packet()` | 458 | 71 lines |
| `without_names()` | 174 | 39 lines |
| `_graded_ponder()` | 610 | 33 lines |
| `memory_line()` | 366 | 29 lines |
| `grade_net()` | 420 | 24 lines |
| `named_in()` | 115 | 22 lines |

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
| `search_lore()` | 467 | 118 lines |
| `knowledge_for_character()` | 813 | 93 lines |
| `set_lore_overlay()` | 384 | 72 lines |
| `update_lore()` | 158 | 71 lines |
| `backfill_lore_embedding_stamps()` | 586 | 71 lines |
| `duplicate_lorebook_tree_for_chat()` | 230 | 69 lines |
| `lore_embedding_health()` | 659 | 62 lines |
| `add_lore()` | 108 | 49 lines |

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
| `answer()` | 452 | 202 lines |
| `route_questions()` | 165 | 35 lines |
| `_order_key()` | 254 | 31 lines |
| `_surest()` | 409 | 25 lines |
| `_subject_lane()` | 326 | 24 lines |
| `_yes_shares()` | 352 | 23 lines |
| `read_route()` | 207 | 18 lines |
| `_first_sure()` | 377 | 18 lines |

### `mind/memory_snapshot.py`

| Function | Start | Size |
|---|---:|---:|
| `import_character_memories()` | 627 | 131 lines |
| `dump_chat_memories()` | 278 | 107 lines |
| `restore_lorebook()` | 919 | 98 lines |
| `prepare_chat_memory_restore()` | 394 | 94 lines |
| `restore_memory_vectors()` | 170 | 54 lines |
| `_foreign_persona_names()` | 582 | 43 lines |
| `restore_lore_overlays()` | 875 | 42 lines |
| `apply_chat_memory_restore()` | 489 | 40 lines |

### `mind/memory_summaries.py`

| Function | Start | Size |
|---|---:|---:|
| `search_memory_summaries()` | 127 | 91 lines |
| `backfill_memory_summary_windows()` | 628 | 89 lines |
| `_write_consolidated_window()` | 509 | 78 lines |
| `consolidate_character_memory()` | 719 | 75 lines |
| `derive_summary_support()` | 237 | 59 lines |
| `visible_summary_rows()` | 40 | 47 lines |
| `_consolidator_row()` | 464 | 43 lines |
| `save_memory_summary()` | 319 | 39 lines |

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
| `repair_pending_embeddings()` | 687 | 104 lines |
| `prepare_memory()` | 414 | 87 lines |
| `_extract_entities()` | 110 | 63 lines |
| `_upsert_memory()` | 836 | 56 lines |
| `_extract_key_phrases()` | 174 | 48 lines |
| `_row_memory()` | 366 | 47 lines |
| `_repair_loop()` | 599 | 46 lines |
| `_embed_in_request_sized_chunks()` | 931 | 37 lines |

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
| `live_psychology()` | 812 | 50 lines |
| `apply_association_updates()` | 760 | 49 lines |
| `_authored_beliefs()` | 590 | 46 lines |
| `cognitive_absorption()` | 882 | 45 lines |
| `_within_cap()` | 551 | 29 lines |

### `mind/skip_memories.py`

| Function | Start | Size |
|---|---:|---:|
| `record_rows()` | 426 | 77 lines |
| `check_and_mend()` | 1122 | 68 lines |
| `run_skip_memories()` | 1396 | 61 lines |
| `ask_model()` | 986 | 52 lines |
| `_compose()` | 771 | 41 lines |
| `sentences()` | 866 | 37 lines |
| `write_rows()` | 1303 | 37 lines |
| `episodes_of()` | 637 | 35 lines |

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
| `_backfill_chat()` | 232 | 68 lines |
| `_heard()` | 178 | 21 lines |
| `backfill_all()` | 302 | 20 lines |
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
| `_rekey_in_place()` | 173 | 64 lines |
| `_rekey_world()` | 239 | 50 lines |
| `remap_row_character_ids()` | 310 | 22 lines |
| `_exportable_checkpoint_blob()` | 355 | 20 lines |
| `_rekey_handle()` | 156 | 15 lines |
| `_character_row_id()` | 129 | 13 lines |
| `world_character_ids()` | 334 | 13 lines |
| `_handle_prefixes()` | 144 | 10 lines |

### `persist/chat_delete.py`

| Function | Start | Size |
|---|---:|---:|
| `delete_chat_data()` | 8 | 44 lines |

### `persist/checkpoints.py`

| Function | Start | Size |
|---|---:|---:|
| `_restore_checkpoint_body()` | 1252 | 187 lines |
| `_restore_books()` | 382 | 170 lines |
| `compact_checkpoints()` | 1582 | 123 lines |
| `_snapshot_without_world()` | 192 | 117 lines |
| `insert_world_tables()` | 859 | 105 lines |
| `_cancel_jobs_the_restore_discards()` | 576 | 86 lines |
| `_snapshot_lore()` | 107 | 83 lines |
| `refresh_checkpoint()` | 1982 | 82 lines |

### `persist/commit.py`

| Function | Start | Size |
|---|---:|---:|
| `_commit_all_locked()` | 538 | 371 lines |
| `commit_crowds()` | 303 | 149 lines |
| `commit_authored_events()` | 253 | 30 lines |
| `commit_narration_person()` | 221 | 29 lines |
| `_refuse_a_taken_back_turn()` | 509 | 27 lines |
| `_refuse_an_ended_frame()` | 490 | 17 lines |
| `commit_offscreen_epoch()` | 285 | 16 lines |
| `_prepare_turn_commit()` | 467 | 12 lines |

### `persist/commit_attire.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_attire_diff()` | 1118 | 707 lines |
| `_mint_shed_garments()` | 749 | 126 lines |
| `interpret_attire_notes()` | 254 | 115 lines |
| `_reclaim_worn_shed_garments()` | 958 | 92 lines |
| `_fold_duplicate_shed_garments()` | 371 | 85 lines |
| `_fold_worn_garment_entities()` | 474 | 73 lines |
| `_merge_attire_regions()` | 33 | 65 lines |
| `_heal_attire_identity_keys()` | 100 | 61 lines |

### `persist/commit_background.py`

| Function | Start | Size |
|---|---:|---:|
| `track_background_presences()` | 2240 | 988 lines |
| `pick_voice_demand()` | 4459 | 467 lines |
| `promote_background_character()` | 5118 | 419 lines |
| `descriptor_bindings()` | 3998 | 156 lines |
| `_fold_duplicate_presences()` | 802 | 143 lines |
| `schedule_auto_promotion()` | 5814 | 123 lines |
| `addressed_rooms()` | 4336 | 121 lines |
| `select_auto_promotion()` | 5576 | 109 lines |

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
| `commit_world_entities()` | 398 | 429 lines |
| `_supersede_disguises()` | 96 | 73 lines |
| `_with_sound_wakings()` | 292 | 51 lines |
| `sync_world_entities_with_scene()` | 345 | 51 lines |
| `_inherit_known_to()` | 200 | 46 lines |
| `_subjects_that_moved()` | 35 | 36 lines |
| `_seconds_or_none()` | 248 | 28 lines |
| `_subjects_targeted_by_an_action()` | 73 | 21 lines |

### `persist/commit_ledgers.py`

| Function | Start | Size |
|---|---:|---:|
| `commit_world_pressure()` | 120 | 163 lines |
| `_positioned_body_named()` | 71 | 27 lines |
| `world_pressure_view()` | 47 | 22 lines |
| `_find_pressure()` | 100 | 18 lines |

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
| `prepare_memory_commit()` | 878 | 1734 lines |
| `_own_sequence_memory()` | 548 | 82 lines |
| `_cited_memory_ids()` | 84 | 76 lines |
| `_own_pronouns_in_scene()` | 467 | 65 lines |
| `_interior_relations_of()` | 739 | 55 lines |
| `_hearer_label()` | 287 | 48 lines |
| `_witnessed_signals()` | 236 | 44 lines |
| `_evidence_spans()` | 192 | 42 lines |

### `persist/commit_memory_write.py`

| Function | Start | Size |
|---|---:|---:|
| `commit_memories()` | 319 | 137 lines |
| `schedule_memory_consolidation()` | 79 | 85 lines |
| `schedule_memory_tension_pass()` | 244 | 73 lines |
| `_consolidate_committed_memories()` | 23 | 51 lines |
| `schedule_skip_memories()` | 173 | 45 lines |
| `cancel_discarded_skip_memories()` | 220 | 11 lines |

### `persist/commit_place_graph.py`

| Function | Start | Size |
|---|---:|---:|
| `update_place_graph()` | 45 | 180 lines |
| `record_spatial_experience()` | 227 | 110 lines |

### `persist/commit_room_registry.py`

| Function | Start | Size |
|---|---:|---:|
| `_prepare_room_registry()` | 298 | 123 lines |
| `dedup_minted_rooms()` | 179 | 118 lines |
| `_refresh_relocated_location()` | 519 | 78 lines |
| `prune_dangling_exits()` | 599 | 64 lines |
| `_apply_room_registry()` | 423 | 57 lines |
| `_rename_room_values()` | 87 | 45 lines |
| `_apply_room_renames()` | 134 | 42 lines |
| `_registry_alias_index()` | 55 | 22 lines |

### `persist/commit_scene_state.py`

| Function | Start | Size |
|---|---:|---:|
| `compose_beat_scene()` | 1691 | 774 lines |
| `prepare_scene_commit()` | 2467 | 548 lines |
| `_fold_duplicate_mints()` | 847 | 135 lines |
| `_advance_day_cycle()` | 75 | 124 lines |
| `derive_borne_containment()` | 1017 | 124 lines |
| `_refuse_unheld_transfers()` | 1143 | 116 lines |
| `_record_sensory_events()` | 1366 | 71 lines |
| `_place_orphan_mints()` | 1261 | 70 lines |

### `persist/commit_skip.py`

| Function | Start | Size |
|---|---:|---:|
| `commit_skip_lives()` | 39 | 73 lines |
| `_since_away()` | 114 | 13 lines |
| `_fold()` | 35 | 2 lines |

### `persist/llm_capture.py`

| Function | Start | Size |
|---|---:|---:|
| `record_exchange()` | 182 | 58 lines |
| `record_room_exchange()` | 543 | 56 lines |
| `referenced_blob_hashes()` | 394 | 41 lines |
| `_values()` | 149 | 26 lines |
| `prune()` | 366 | 26 lines |
| `latest_turn_id()` | 497 | 26 lines |
| `put_blob()` | 85 | 25 lines |
| `recording_outside_a_step()` | 308 | 25 lines |

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
| `run_artifacts()` | 185 | 236 lines |
| `schedule_artifact_wording()` | 519 | 78 lines |
| `mint_wording()` | 599 | 62 lines |
| `land_artifact_wording()` | 663 | 57 lines |
| `post_spoor()` | 456 | 56 lines |
| `reading_copy()` | 151 | 26 lines |
| `spoor_artifact()` | 433 | 21 lines |
| `new_artifact()` | 129 | 20 lines |

### `story/attire.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_regions()` | 714 | 161 lines |
| `garments_named_in()` | 2441 | 152 lines |
| `_attributed_scoped()` | 2099 | 144 lines |
| `coerce_diff_shape()` | 1751 | 136 lines |
| `advance()` | 2792 | 136 lines |
| `compact_line()` | 3761 | 123 lines |
| `apply_flat_change()` | 3298 | 118 lines |
| `perceptible_region_surfaces()` | 3057 | 100 lines |

### `story/authored_events.py`

| Function | Start | Size |
|---|---:|---:|
| `resolve_authored_events()` | 296 | 78 lines |
| `mint_authored_events()` | 192 | 45 lines |
| `_assertion_tokens()` | 257 | 37 lines |
| `_changed_text()` | 90 | 36 lines |
| `_retired_text()` | 54 | 34 lines |
| `_live_event_for()` | 168 | 22 lines |
| `_event_id()` | 136 | 21 lines |
| `due_authored_events()` | 239 | 12 lines |

### `story/carriers.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_tellings()` | 1280 | 211 lines |
| `unbacked_claims()` | 1038 | 158 lines |
| `advance_carriers()` | 307 | 134 lines |
| `names_nobody_holds()` | 952 | 84 lines |
| `_build_carriers()` | 690 | 76 lines |
| `_held_identity_roster()` | 883 | 67 lines |
| `standing_surfaces_reader()` | 234 | 62 lines |
| `_crowds_acquire()` | 443 | 57 lines |

### `story/character_schema.py`

| Function | Start | Size |
|---|---:|---:|
| `character_card_warnings()` | 2617 | 201 lines |
| `default_character_data()` | 757 | 146 lines |
| `normalize_character_data()` | 1648 | 131 lines |
| `_normalize_psychology()` | 346 | 83 lines |
| `normalize_persona_data()` | 1780 | 74 lines |
| `_normalize_native_shape()` | 1581 | 65 lines |
| `_normalize_interior()` | 696 | 59 lines |
| `repair_character_shape()` | 1315 | 57 lines |

### `story/couriers.py`

| Function | Start | Size |
|---|---:|---:|
| `run_couriers()` | 834 | 418 lines |
| `_exchange_stops()` | 618 | 214 lines |
| `advance_couriers()` | 339 | 88 lines |
| `_deliver()` | 530 | 86 lines |
| `new_courier()` | 277 | 47 lines |
| `_copy_of()` | 429 | 40 lines |
| `_player_name()` | 502 | 26 lines |
| `courier_edge_seconds()` | 144 | 22 lines |

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
| `start_story()` | 810 | 459 lines |
| `_seed_mind_state()` | 373 | 144 lines |
| `generate_greeting()` | 1271 | 62 lines |
| `_seed_minds()` | 571 | 57 lines |
| `_route_mind_memories()` | 315 | 56 lines |
| `_seed_player_mind()` | 519 | 50 lines |
| `extract_greeting()` | 129 | 49 lines |
| `claim_greeting_mind()` | 630 | 44 lines |

### `story/history_routing.py`

| Function | Start | Size |
|---|---:|---:|
| `resolve_character_history_route()` | 142 | 73 lines |
| `_manual_route()` | 99 | 41 lines |
| `normalize_history_choice()` | 71 | 14 lines |
| `_distinct_words()` | 91 | 6 lines |
| `_matches()` | 87 | 2 lines |
| `route_uses_charter()` | 217 | 2 lines |

### `story/importers.py`

| Function | Start | Size |
|---|---:|---:|
| `import_lorebook()` | 1957 | 226 lines |
| `apply_lorebook_plan()` | 3175 | 214 lines |
| `draft_promoted_character()` | 902 | 172 lines |
| `_reinterpret_entries()` | 1807 | 149 lines |
| `_lore_gen_entry_batch()` | 2815 | 119 lines |
| `fill_appearance()` | 1325 | 115 lines |
| `fill_body_interior()` | 1510 | 114 lines |
| `_run_lore_gen_job()` | 2938 | 112 lines |

### `story/journey_history.py`

| Function | Start | Size |
|---|---:|---:|
| `compile_journey_history()` | 337 | 171 lines |
| `ground_journey_history()` | 218 | 92 lines |
| `_model_value()` | 177 | 39 lines |
| `_source_rows()` | 147 | 28 lines |
| `memory_words()` | 41 | 24 lines |
| `companion_of()` | 312 | 23 lines |
| `journey_event_count()` | 122 | 12 lines |
| `_content_key()` | 140 | 5 lines |

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
| `derive_knowledge()` | 200 | 54 lines |
| `parse_structure()` | 78 | 50 lines |
| `clean_title()` | 46 | 16 lines |
| `classify_title()` | 64 | 12 lines |
| `_matches()` | 165 | 12 lines |
| `_place_name()` | 156 | 7 lines |

### `story/mandates.py`

| Function | Start | Size |
|---|---:|---:|
| `grant_mandate()` | 446 | 100 lines |
| `request_open()` | 335 | 32 lines |
| `_request()` | 293 | 29 lines |
| `close_request()` | 599 | 27 lines |
| `_spend()` | 806 | 24 lines |
| `renew_mandate()` | 628 | 22 lines |
| `coverage()` | 723 | 22 lines |
| `_update()` | 419 | 20 lines |

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
| `fire_due_clocks()` | 4559 | 166 lines |
| `_package_checks()` | 3836 | 148 lines |
| `_preview_plan_rooms()` | 1239 | 125 lines |
| `publish_package()` | 4294 | 97 lines |
| `_preview_plan_entity()` | 1494 | 91 lines |
| `_plan_geometry()` | 913 | 88 lines |
| `_plan_edge()` | 1039 | 84 lines |
| `_reach_warning()` | 3992 | 81 lines |

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
| `split_engine_provenance()` | 100 | 48 lines |
| `looks_like_engine_provenance()` | 95 | 3 lines |
| `strip_engine_provenance()` | 150 | 3 lines |

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
| `check_claims()` | 190 | 46 lines |
| `_harvest()` | 140 | 16 lines |
| `_add()` | 158 | 16 lines |
| `note_reads()` | 125 | 13 lines |
| `normalize_claim()` | 176 | 12 lines |
| `reading()` | 97 | 9 lines |
| `enter_reading()` | 108 | 9 lines |
| `rows_read()` | 119 | 4 lines |

### `story/room_conversation.py`

| Function | Start | Size |
|---|---:|---:|
| `converse_stream()` | 446 | 104 lines |
| `converse()` | 379 | 51 lines |
| `status()` | 314 | 38 lines |
| `normalize_mandate()` | 225 | 36 lines |
| `restore_room_messages()` | 562 | 36 lines |
| `add_message()` | 191 | 23 lines |
| `revoke_mandate()` | 290 | 22 lines |
| `_normalize_request()` | 263 | 15 lines |

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
| `keep_spared()` | 646 | 119 lines |
| `pass_due()` | 780 | 53 lines |
| `hand_back_briefs()` | 516 | 44 lines |
| `file_proposal()` | 306 | 43 lines |
| `normalize_proposal()` | 137 | 40 lines |
| `judge_proposal()` | 351 | 31 lines |
| `briefs_due()` | 562 | 25 lines |
| `_pass_log()` | 199 | 22 lines |

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
| `sketch_payload()` | 386 | 270 lines |
| `_plan()` | 850 | 239 lines |
| `_looks_payload()` | 302 | 82 lines |
| `run_sketch()` | 1178 | 75 lines |
| `_looks_op()` | 789 | 59 lines |
| `_file()` | 1109 | 56 lines |
| `_edge()` | 677 | 33 lines |
| `_structure_for()` | 734 | 27 lines |

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
| `_t_inspect_contradictions()` | 848 | 201 lines |
| `_mind_of()` | 1188 | 148 lines |
| `_t_inspect_charters()` | 582 | 124 lines |
| `_t_inspect_config()` | 771 | 70 lines |
| `fit_result()` | 1771 | 64 lines |
| `_t_inspect_route()` | 295 | 53 lines |
| `_t_inspect_rooms()` | 244 | 49 lines |
| `_charter_post_rows()` | 421 | 45 lines |

### `story/scene.py`

| Function | Start | Size |
|---|---:|---:|
| `get_scene()` | 490 | 83 lines |
| `disguises_from_rows()` | 815 | 77 lines |
| `awareness_conditions()` | 1479 | 73 lines |
| `_positive_presented_appearance()` | 1108 | 66 lines |
| `normalize_transformed_parts()` | 901 | 60 lines |
| `recent_events_for_observer()` | 2109 | 59 lines |
| `normalize_style_guide()` | 2873 | 58 lines |
| `private_knowledge_for()` | 3202 | 56 lines |

### `web/app.py`

| Function | Start | Size |
|---|---:|---:|
| `turn_branch()` | 7245 | 529 lines |
| `chat_get()` | 4739 | 326 lines |
| `_remap_cp_blob()` | 1545 | 245 lines |
| `bootstrap()` | 2063 | 179 lines |
| `guest_state()` | 5534 | 153 lines |
| `chat_char_position_put()` | 5959 | 107 lines |
| `turn_new()` | 7000 | 102 lines |
| `chat_add_char()` | 5067 | 95 lines |

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
| `_living_world()` | 344 | 91 lines |
| `_people()` | 835 | 77 lines |
| `_player_view_in_frame()` | 965 | 60 lines |
| `player_view()` | 914 | 49 lines |
| `_story_view_in_frame()` | 452 | 46 lines |
| `_public_facts()` | 655 | 46 lines |
| `viewers()` | 518 | 36 lines |
| `_person_refs()` | 752 | 36 lines |

### `web/world_routes.py`

| Function | Start | Size |
|---|---:|---:|
| `grid_view()` | 959 | 217 lines |
| `room_entity_patch()` | 1897 | 95 lines |
| `_apply_exits()` | 1533 | 92 lines |
| `_apply_doorway_fields()` | 2623 | 90 lines |
| `map_view()` | 1297 | 80 lines |
| `body_station_put()` | 2068 | 77 lines |
| `body_rows()` | 697 | 70 lines |
| `room_patch()` | 1827 | 67 lines |

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
| `record_beat_events()` | 115 | 26 lines |
| `beat_events()` | 143 | 21 lines |
| `beat_event_order()` | 166 | 20 lines |
| `_clean_event()` | 95 | 18 lines |

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
| `program_steps()` | 359 | 60 lines |
| `_rewrite_patch()` | 32 | 28 lines |
| `event_worlds()` | 268 | 28 lines |
| `program_from_history()` | 298 | 23 lines |
| `_strip_to()` | 336 | 21 lines |
| `prune_program()` | 431 | 19 lines |
| `fold_steps()` | 257 | 9 lines |

### `world/causal_verification.py`

| Function | Start | Size |
|---|---:|---:|
| `_map_receipts()` | 332 | 126 lines |
| `_inventory_receipts()` | 720 | 99 lines |
| `_contact_receipts()` | 919 | 66 lines |
| `_substance_receipts()` | 840 | 61 lines |
| `_overlay_receipts()` | 1102 | 56 lines |
| `_verify_patch()` | 1184 | 55 lines |
| `_rooms_receipts()` | 485 | 51 lines |
| `_weather_receipts()` | 638 | 49 lines |

### `world/causality.py`

| Function | Start | Size |
|---|---:|---:|
| `compile_transforms()` | 211 | 195 lines |
| `_merge_attire_record()` | 77 | 66 lines |
| `_merge_channel()` | 145 | 43 lines |
| `_stamp_from_event()` | 190 | 19 lines |
| `_merge_record()` | 58 | 17 lines |

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
| `observe_public_commitments()` | 78 | 92 lines |
| `normalize_commitments()` | 34 | 38 lines |
| `open_commitment()` | 231 | 37 lines |
| `advance_commitments()` | 183 | 25 lines |
| `answer_commitment()` | 270 | 22 lines |
| `commitment_view()` | 210 | 19 lines |
| `commitment_id()` | 28 | 4 lines |
| `_frame_terms()` | 74 | 2 lines |

### `world/charter_creature.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_creature()` | 138 | 180 lines |
| `creature_neighbors()` | 359 | 34 lines |
| `normalize_spoor()` | 328 | 18 lines |
| `prey_capability()` | 441 | 14 lines |
| `predator_capability()` | 427 | 12 lines |
| `is_active()` | 395 | 11 lines |
| `room_fits()` | 348 | 9 lines |
| `hunger_of()` | 408 | 9 lines |

### `world/charter_crowd.py`

| Function | Start | Size |
|---|---:|---:|
| `members_of()` | 121 | 55 lines |
| `member_noun()` | 221 | 41 lines |
| `crowd_for()` | 335 | 40 lines |
| `crowd_face()` | 304 | 29 lines |
| `_plural()` | 189 | 22 lines |
| `engaged_turn()` | 81 | 20 lines |
| `composition_of()` | 264 | 18 lines |
| `mood_of()` | 284 | 18 lines |

### `world/charter_decide.py`

| Function | Start | Size |
|---|---:|---:|
| `mobilisation_calls()` | 208 | 57 lines |
| `advance_decisions()` | 75 | 54 lines |
| `execute_orders()` | 159 | 47 lines |
| `normalize_decisions()` | 25 | 35 lines |
| `deliver_orders()` | 131 | 26 lines |
| `decision_view()` | 267 | 9 lines |
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
| `caravan_exchange()` | 391 | 64 lines |
| `ensure_supply_points()` | 172 | 48 lines |
| `advance_economy()` | 291 | 47 lines |
| `_holdings()` | 46 | 26 lines |
| `_quote()` | 257 | 26 lines |
| `take_stock()` | 365 | 24 lines |
| `trade()` | 340 | 23 lines |

### `world/charter_enrol.py`

| Function | Start | Size |
|---|---:|---:|
| `enrol_person()` | 302 | 110 lines |
| `households_charter_key()` | 171 | 30 lines |
| `posts_for_role()` | 87 | 28 lines |
| `_room_distances()` | 203 | 21 lines |
| `_add_body()` | 265 | 20 lines |
| `depart_guests()` | 414 | 20 lines |
| `lodging_charter_for()` | 145 | 19 lines |
| `reconcile_surface()` | 245 | 18 lines |

### `world/charter_feel.py`

| Function | Start | Size |
|---|---:|---:|
| `appraise_window()` | 193 | 112 lines |
| `advance_feel()` | 307 | 112 lines |
| `felt_handoff()` | 449 | 30 lines |
| `normalize_feel()` | 164 | 16 lines |
| `strain_of()` | 428 | 13 lines |
| `_served_by_body()` | 182 | 9 lines |
| `_negligible()` | 421 | 5 lines |
| `overloaded_bodies()` | 443 | 4 lines |

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
| `close_plan()` | 1118 | 464 lines |
| `_spread_berths()` | 830 | 145 lines |
| `_json_call()` | 293 | 100 lines |
| `_featured_assignments()` | 1031 | 85 lines |
| `_ensure_shift_crews()` | 602 | 62 lines |
| `ensure_required_rooms()` | 1612 | 60 lines |
| `narrate_actual_history()` | 1788 | 58 lines |
| `resident_service_chronicle()` | 1684 | 52 lines |

### `world/charter_harm.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_harm()` | 161 | 86 lines |
| `advance_harm()` | 249 | 29 lines |
| `_successor()` | 139 | 20 lines |
| `in_a_room()` | 88 | 18 lines |
| `head_posts()` | 119 | 18 lines |
| `capability_of()` | 108 | 9 lines |
| `normalize_condition()` | 79 | 3 lines |
| `is_gone()` | 84 | 2 lines |

### `world/charter_history.py`

| Function | Start | Size |
|---|---:|---:|
| `integrate_featured_resident()` | 762 | 141 lines |
| `ground_recent_history()` | 549 | 122 lines |
| `_recent_life_context()` | 277 | 87 lines |
| `ground_personal_history()` | 469 | 78 lines |
| `resident_history_packet()` | 366 | 73 lines |
| `_record_shared_recent_history()` | 673 | 48 lines |
| `featured_resident_private_habits()` | 165 | 47 lines |
| `flesh_resident_history()` | 723 | 37 lines |

### `world/charter_identity.py`

| Function | Start | Size |
|---|---:|---:|
| `materialize_body_names()` | 1029 | 119 lines |
| `name_is_reserved()` | 660 | 65 lines |
| `refuse_harvested_material()` | 895 | 62 lines |
| `derived_name_parts()` | 230 | 43 lines |
| `_stored_name_components()` | 360 | 43 lines |
| `title_for()` | 1150 | 41 lines |
| `identity_aliases()` | 1248 | 38 lines |
| `_fill_empty_material()` | 856 | 37 lines |

### `world/charter_intervene.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_due()` | 213 | 157 lines |
| `_apply_relocate()` | 163 | 48 lines |
| `normalize_interventions()` | 100 | 46 lines |
| `normalize_mobilisation()` | 81 | 17 lines |
| `_scheduled_end()` | 41 | 6 lines |
| `intervention_warnings()` | 148 | 5 lines |
| `watch_post_key()` | 155 | 2 lines |
| `watch_upkeep_key()` | 159 | 2 lines |

### `world/charter_log.py`

| Function | Start | Size |
|---|---:|---:|
| `scene_ledger()` | 288 | 237 lines |
| `life_of()` | 137 | 90 lines |
| `summarize()` | 65 | 70 lines |
| `own_state_of()` | 240 | 46 lines |
| `chronicle()` | 527 | 17 lines |
| `window_note()` | 48 | 15 lines |

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
| `normalize_charter()` | 539 | 412 lines |
| `normalize_body()` | 231 | 162 lines |
| `body_of_an_authored_mind()` | 395 | 58 lines |
| `normalize_post()` | 144 | 45 lines |
| `normalize_body_station()` | 191 | 38 lines |
| `normalize_upkeep()` | 111 | 31 lines |
| `_phase_set()` | 517 | 20 lines |
| `_tags()` | 72 | 15 lines |

### `world/charter_move.py`

| Function | Start | Size |
|---|---:|---:|
| `errands()` | 457 | 122 lines |
| `_advance()` | 261 | 60 lines |
| `edge_seconds()` | 117 | 52 lines |
| `_dispatch()` | 211 | 48 lines |
| `continue_walks()` | 333 | 48 lines |
| `walk()` | 581 | 40 lines |
| `place_body()` | 681 | 38 lines |
| `set_place()` | 646 | 33 lines |

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
| `plan_public_evidence()` | 460 | 167 lines |
| `body_receives_evidence()` | 91 | 90 lines |
| `resolve_target_body()` | 381 | 77 lines |
| `apply_public_evidence()` | 629 | 74 lines |
| `evidence_claim()` | 210 | 65 lines |
| `_bodies_by_role()` | 346 | 33 lines |
| `_post_forms()` | 312 | 32 lines |
| `evidence_phrase()` | 187 | 21 lines |

### `world/charter_ops.py`

| Function | Start | Size |
|---|---:|---:|
| `_check()` | 145 | 40 lines |
| `apply_charter_ops()` | 381 | 39 lines |
| `_resolve_body_name()` | 323 | 38 lines |
| `_transfer()` | 258 | 37 lines |
| `normalize_charter_op()` | 117 | 26 lines |
| `_op_upkeep_fails()` | 225 | 25 lines |
| `_house_of()` | 363 | 16 lines |
| `_op_depart()` | 303 | 11 lines |

### `world/charter_place.py`

| Function | Start | Size |
|---|---:|---:|
| `resolve_scene_placements()` | 586 | 100 lines |
| `heal_unbound_twins()` | 400 | 80 lines |
| `charter_placements()` | 199 | 75 lines |
| `lease_scene_bodies()` | 524 | 60 lines |
| `_station_and_facing()` | 151 | 46 lines |
| `lay_charter_bodies()` | 307 | 36 lines |
| `_spelling_table()` | 360 | 33 lines |
| `rooms_in_frame()` | 288 | 17 lines |

### `world/charter_plan.py`

| Function | Start | Size |
|---|---:|---:|
| `plan_watch()` | 87 | 122 lines |
| `tended_upkeeps()` | 211 | 24 lines |
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
| `hunt_moves()` | 306 | 189 lines |
| `_attack()` | 510 | 146 lines |
| `predation_round()` | 658 | 126 lines |
| `_tribute()` | 867 | 95 lines |
| `run_registry()` | 1020 | 60 lines |
| `_scene_figures_at()` | 221 | 55 lines |
| `read_spoor()` | 815 | 48 lines |
| `_company()` | 133 | 37 lines |

### `world/charter_promote.py`

| Function | Start | Size |
|---|---:|---:|
| `remembered()` | 153 | 283 lines |
| `inherited_place_graph()` | 572 | 99 lines |
| `acquainted()` | 472 | 65 lines |
| `_words()` | 114 | 37 lines |
| `promotion_handoff()` | 438 | 24 lines |
| `private_rooms()` | 548 | 22 lines |
| `_news_phrase()` | 101 | 11 lines |

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
| `step()` | 447 | 1128 lines |
| `_record_coarse_experiences()` | 264 | 160 lines |
| `run()` | 1577 | 94 lines |
| `_remember_experience()` | 165 | 43 lines |
| `_run_private_habits()` | 233 | 29 lines |
| `_social_events()` | 115 | 25 lines |
| `_record_social_experiences()` | 210 | 21 lines |
| `_settle_commitments()` | 426 | 19 lines |

### `world/charter_runtime.py`

| Function | Start | Size |
|---|---:|---:|
| `registry_warnings()` | 2723 | 270 lines |
| `_plan_lived_location()` | 2123 | 254 lines |
| `_prepare_cast_histories()` | 1112 | 199 lines |
| `presence_view()` | 5380 | 176 lines |
| `advance_snapshot()` | 3419 | 167 lines |
| `_generate_lived_location()` | 2437 | 163 lines |
| `_remap_generated_town()` | 1839 | 144 lines |
| `_voiced_presence()` | 5132 | 130 lines |

### `world/charter_skip.py`

| Function | Start | Size |
|---|---:|---:|
| `live_in_charter()` | 126 | 58 lines |
| `skip_windows()` | 316 | 43 lines |
| `_body_of_mind()` | 251 | 36 lines |
| `_stretches()` | 196 | 31 lines |
| `_a_way_exists()` | 1151 | 22 lines |
| `_char_id_of()` | 229 | 20 lines |
| `_seen_order()` | 1135 | 14 lines |
| `_charter_naming()` | 302 | 12 lines |

### `world/charter_social.py`

| Function | Start | Size |
|---|---:|---:|
| `update_ties()` | 735 | 78 lines |
| `normalize_ties()` | 672 | 61 lines |
| `update_judgments_from_minds()` | 422 | 54 lines |
| `signal_landing()` | 340 | 49 lines |
| `derive_tie()` | 600 | 40 lines |
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
| `send_errand()` | 303 | 68 lines |
| `plant_claim()` | 194 | 40 lines |
| `adjust_stock()` | 236 | 25 lines |
| `open_summons()` | 393 | 25 lines |
| `assign_post()` | 127 | 21 lines |
| `charter_shock()` | 281 | 20 lines |
| `_member_key()` | 169 | 19 lines |
| `move_body()` | 107 | 18 lines |

### `world/charter_talk.py`

| Function | Start | Size |
|---|---:|---:|
| `report_to_superiors()` | 303 | 52 lines |
| `converse()` | 208 | 49 lines |
| `report_up()` | 259 | 42 lines |
| `tell_ranking()` | 88 | 38 lines |
| `co_present()` | 128 | 35 lines |
| `tellable()` | 61 | 25 lines |
| `witnessed()` | 186 | 20 lines |
| `pair_up()` | 165 | 19 lines |

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
| `fire_triggers()` | 671 | 148 lines |
| `_normalize_rule()` | 323 | 123 lines |
| `fire_institution_rules()` | 821 | 73 lines |
| `changes_from()` | 594 | 41 lines |
| `perceivable_change()` | 285 | 36 lines |
| `_rulebase()` | 461 | 27 lines |
| `_cap_changes()` | 569 | 23 lines |
| `prune_trigger_last()` | 637 | 20 lines |

### `world/comfort.py`

| Function | Start | Size |
|---|---:|---:|
| `_derive()` | 339 | 82 lines |
| `_posture_of()` | 303 | 34 lines |
| `vocabulary()` | 151 | 21 lines |
| `_fields()` | 226 | 12 lines |
| `_entity_record()` | 262 | 12 lines |
| `_warm()` | 245 | 11 lines |
| `_station_of()` | 290 | 11 lines |
| `contains_word()` | 193 | 10 lines |

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
| `seconds_until()` | 523 | 91 lines |
| `sun_light()` | 230 | 49 lines |
| `clock_hour()` | 410 | 38 lines |
| `clock_anchor()` | 359 | 33 lines |
| `clock_reading_hour()` | 285 | 27 lines |
| `display_hour()` | 450 | 23 lines |
| `charter_phase()` | 479 | 21 lines |
| `label_phase()` | 314 | 19 lines |

### `world/degradation.py`

| Function | Start | Size |
|---|---:|---:|
| `degrade()` | 161 | 33 lines |
| `_replace_phrases()` | 139 | 20 lines |
| `_language()` | 114 | 19 lines |
| `lost_at()` | 210 | 19 lines |
| `is_exhausted()` | 196 | 12 lines |
| `_collapse()` | 135 | 2 lines |

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
| `_skeleton()` | 127 | 182 lines |
| `last_seen_update()` | 355 | 75 lines |
| `gap_for()` | 311 | 38 lines |
| `interim_for()` | 432 | 34 lines |
| `_record()` | 85 | 20 lines |
| `_subject_room()` | 113 | 12 lines |
| `_read_key()` | 72 | 4 lines |
| `_unavailable()` | 107 | 4 lines |

### `world/landscape.py`

| Function | Start | Size |
|---|---:|---:|
| `far_places()` | 757 | 413 lines |
| `looked_far()` | 1172 | 160 lines |
| `standing_looks_wanted()` | 1754 | 108 lines |
| `_place_forms()` | 1373 | 60 lines |
| `_said_as_a_word()` | 1435 | 48 lines |
| `_between()` | 665 | 45 lines |
| `_admit_look()` | 1516 | 43 lines |
| `_building_fronts()` | 1667 | 34 lines |

### `world/layout_arrange.py`

| Function | Start | Size |
|---|---:|---:|
| `_sub_rects()` | 2689 | 40 lines |
| `_sealed()` | 2855 | 38 lines |
| `_chk_cost()` | 2628 | 33 lines |
| `_reached()` | 2895 | 30 lines |
| `_steps()` | 2740 | 29 lines |
| `_hall_past()` | 784 | 25 lines |
| `_hall_fits()` | 755 | 24 lines |
| `solve_arranged()` | 5191 | 22 lines |

### `world/layout_bridge.py`

| Function | Start | Size |
|---|---:|---:|
| `planned_layout()` | 3260 | 484 lines |
| `_ground_plan()` | 1854 | 429 lines |
| `ground_breaches()` | 2645 | 350 lines |
| `_building()` | 1025 | 247 lines |
| `spec_from_answers()` | 1606 | 246 lines |
| `plan_buildings()` | 455 | 145 lines |
| `hold_inventory()` | 1360 | 108 lines |
| `_ground_geometry()` | 3822 | 87 lines |

### `world/layout_solver.py`

| Function | Start | Size |
|---|---:|---:|
| `_grounds()` | 2916 | 568 lines |
| `_place_fixtures()` | 2397 | 219 lines |
| `_place_blocks()` | 691 | 174 lines |
| `_place_doors()` | 1984 | 166 lines |
| `_things_at_doors()` | 2634 | 138 lines |
| `_doors_onto_their_ground()` | 2789 | 125 lines |
| `_prepare()` | 1528 | 107 lines |
| `_search()` | 1661 | 106 lines |

### `world/living_world.py`

| Function | Start | Size |
|---|---:|---:|
| `mint_consequences()` | 102 | 100 lines |
| `record_obligations()` | 255 | 52 lines |
| `fired_consequences_at()` | 204 | 31 lines |
| `attach_owed_history()` | 335 | 25 lines |
| `owed_history()` | 309 | 24 lines |
| `_squeeze()` | 98 | 2 lines |

### `world/lots.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_lot()` | 58 | 32 lines |
| `lot_marks()` | 92 | 13 lines |
| `is_unexpanded_lot()` | 107 | 6 lines |
| `_int()` | 51 | 5 lines |
| `unexpanded_lots()` | 115 | 5 lines |

### `world/mechanics.py`

| Function | Start | Size |
|---|---:|---:|
| `_fire_due_events()` | 720 | 168 lines |
| `_tick_conditions()` | 1308 | 126 lines |
| `_schedule_new_arrivals()` | 953 | 119 lines |
| `read_time_diff()` | 216 | 110 lines |
| `mechanics_sweep()` | 1616 | 73 lines |
| `beat_time_block()` | 475 | 64 lines |
| `beat_time_from_spans()` | 354 | 55 lines |
| `unanswered_hazard_subjects()` | 1530 | 49 lines |

### `world/offscreen.py`

| Function | Start | Size |
|---|---:|---:|
| `advance_epoch()` | 147 | 85 lines |
| `epoch_reasons()` | 60 | 39 lines |
| `_beat_id()` | 110 | 17 lines |
| `_beat_context()` | 129 | 16 lines |
| `_epoch_id()` | 101 | 7 lines |
| `_as_seconds()` | 53 | 5 lines |

### `world/paradox.py`

| Function | Start | Size |
|---|---:|---:|
| `check_and_apply_paradox()` | 673 | 71 lines |
| `_apply_toll()` | 383 | 62 lines |
| `_advance_paradox()` | 575 | 48 lines |
| `_force_restore_anchor()` | 625 | 46 lines |
| `_trigger_paradox()` | 540 | 33 lines |
| `_apply_warden_stage()` | 471 | 29 lines |
| `_apply_hazard_stage()` | 353 | 28 lines |
| `_entity_exists()` | 205 | 22 lines |

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
| `mirror_told_affords()` | 467 | 91 lines |
| `here_affords()` | 307 | 75 lines |
| `witness_affords()` | 389 | 68 lines |
| `place_options()` | 599 | 43 lines |
| `assumed_affords()` | 278 | 27 lines |
| `_walked_hops()` | 577 | 20 lines |
| `_keyed_lexicon()` | 237 | 19 lines |
| `_name_lexicon()` | 258 | 18 lines |

### `world/planned_entities.py`

| Function | Start | Size |
|---|---:|---:|
| `plans_in_sight()` | 386 | 177 lines |
| `normalize_plan()` | 144 | 96 lines |
| `project_planned_emissions()` | 248 | 91 lines |
| `plan_figure()` | 675 | 43 lines |
| `plan_state()` | 100 | 42 lines |
| `settle_rendered_plans()` | 757 | 41 lines |
| `_station_a_thing()` | 565 | 40 lines |
| `plan_answering()` | 611 | 26 lines |

### `world/planning_needs.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_need()` | 184 | 62 lines |
| `drain_planning_needs()` | 410 | 44 lines |
| `_fold_need()` | 311 | 27 lines |
| `record_planning_needs()` | 353 | 26 lines |
| `planning_need()` | 248 | 25 lines |
| `schedule_planning_needs()` | 456 | 25 lines |
| `fill_planning_need()` | 381 | 14 lines |
| `normalize_planning_needs()` | 275 | 12 lines |

### `world/region_events.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_wave()` | 282 | 142 lines |
| `normalize_region_event()` | 78 | 72 lines |
| `resolve_footprint()` | 174 | 46 lines |
| `plan_waves()` | 226 | 37 lines |
| `_stand_hazard()` | 426 | 31 lines |
| `_graph()` | 162 | 10 lines |
| `_decay_steps()` | 265 | 6 lines |
| `harms_a_body()` | 152 | 4 lines |

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

### `world/skip_itinerary.py`

| Function | Start | Size |
|---|---:|---:|
| `live_through()` | 1556 | 183 lines |
| `lay_over()` | 1765 | 50 lines |
| `journeys()` | 1303 | 41 lines |
| `expand_itinerary()` | 496 | 39 lines |
| `share_company()` | 2010 | 39 lines |
| `stretch_outcome()` | 1416 | 35 lines |
| `judge_without()` | 1858 | 32 lines |
| `default_day()` | 425 | 31 lines |

### `world/spatial_barriers.py`

| Function | Start | Size |
|---|---:|---:|
| `effective_adjacent()` | 930 | 103 lines |
| `neighbor_map()` | 758 | 96 lines |
| `normalize_barrier()` | 331 | 85 lines |
| `frontier_joins()` | 667 | 62 lines |
| `normalize_scene_passages()` | 1114 | 54 lines |
| `normalize_scene_barriers()` | 472 | 49 lines |
| `passage_direction()` | 856 | 28 lines |
| `_barrier_against_its_own_name()` | 542 | 27 lines |

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
| `contacts_from_entity_state()` | 126 | 141 lines |
| `_lift_valued_contact()` | 284 | 60 lines |
| `_drop_contradicted_state()` | 346 | 39 lines |
| `_verb_form()` | 79 | 10 lines |
| `_key_manner()` | 91 | 9 lines |
| `_part_from_key()` | 116 | 8 lines |
| `_manner_from_fragment()` | 108 | 6 lines |

### `world/spatial_contacts.py`

| Function | Start | Size |
|---|---:|---:|
| `apply_contact_ops()` | 1418 | 452 lines |
| `_clean_contact()` | 935 | 168 lines |
| `normalize_scene_contacts()` | 1253 | 94 lines |
| `contacts_across_enclosure()` | 1145 | 68 lines |
| `_mirrored_displacements()` | 342 | 50 lines |
| `_unnamed_touch_between_bodies()` | 876 | 47 lines |
| `contact_thing_label()` | 804 | 42 lines |
| `_anchor_room_of()` | 762 | 40 lines |

### `world/spatial_containment.py`

| Function | Start | Size |
|---|---:|---:|
| `derive_inventory_placements()` | 1775 | 260 lines |
| `materialize_named_stations()` | 3266 | 135 lines |
| `advance_room_transits()` | 3403 | 130 lines |
| `replace_engine_minted_interiors()` | 2751 | 123 lines |
| `mint_transferred_objects()` | 1653 | 120 lines |
| `place_enclosed_bodies()` | 2876 | 108 lines |
| `normalize_scene_containment()` | 963 | 98 lines |
| `release_declared_departures()` | 3547 | 97 lines |

### `world/spatial_fov.py`

| Function | Start | Size |
|---|---:|---:|
| `body_visibility()` | 2579 | 164 lines |
| `body_cell()` | 1357 | 136 lines |
| `feature_visibility()` | 2297 | 112 lines |
| `_place_anchor()` | 862 | 105 lines |
| `_stand_cell()` | 1244 | 80 lines |
| `neighbour_feature_visibility()` | 2451 | 71 lines |
| `_room_field()` | 1920 | 59 lines |
| `_placed_neighbours()` | 1828 | 55 lines |

### `world/spatial_frames.py`

| Function | Start | Size |
|---|---:|---:|
| `infer_focus()` | 463 | 245 lines |
| `perform_split()` | 1225 | 213 lines |
| `open_couple()` | 2222 | 188 lines |
| `detect_and_reconcile()` | 2655 | 139 lines |
| `infer_facing()` | 810 | 132 lines |
| `perform_sibling_merge()` | 1859 | 123 lines |
| `perform_merge()` | 1696 | 115 lines |
| `_partition_side()` | 2459 | 105 lines |

### `world/spatial_geometry.py`

| Function | Start | Size |
|---|---:|---:|
| `_effective_anchors()` | 461 | 165 lines |
| `invalidate_transferred_pose_details()` | 2036 | 112 lines |
| `spatial_digest()` | 152 | 107 lines |
| `derive_scene_stations()` | 2385 | 103 lines |
| `invalidate_moved_body_place_details()` | 1817 | 102 lines |
| `egocentric_frame()` | 64 | 86 lines |
| `invalidate_moved_body_pose_details()` | 1708 | 78 lines |
| `invalidate_contact_bound_poses()` | 2150 | 75 lines |

### `world/spatial_identity.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_scene_subjects()` | 652 | 136 lines |
| `canonical_subject_map()` | 554 | 87 lines |
| `scene_names_body()` | 395 | 77 lines |
| `room_of()` | 92 | 68 lines |
| `scene_room_id()` | 894 | 57 lines |
| `_live_subject_spellings()` | 500 | 52 lines |
| `room_of_record()` | 162 | 37 lines |
| `same_subject()` | 216 | 29 lines |

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
| `light_at()` | 704 | 57 lines |
| `source_light()` | 315 | 51 lines |
| `effective_light()` | 763 | 44 lines |
| `unsourced_light_notices()` | 268 | 34 lines |
| `_lamp_reach()` | 549 | 34 lines |

### `world/spatial_light_field.py`

| Function | Start | Size |
|---|---:|---:|
| `light_shape()` | 1234 | 133 lines |
| `light_sources()` | 594 | 98 lines |
| `_resolve_pointed_at()` | 525 | 67 lines |
| `compute_light_field()` | 918 | 67 lines |
| `_bounce()` | 810 | 59 lines |
| `_spill()` | 871 | 45 lines |
| `_aimed_at()` | 1413 | 43 lines |
| `held_beam_falls_on()` | 1369 | 42 lines |

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
| `merge_scene_with_diff()` | 1977 | 972 lines |
| `_shield_standing_bearings()` | 972 | 118 lines |
| `_expire_transient_entity_state()` | 690 | 116 lines |
| `_merge_room()` | 194 | 115 lines |
| `sync_scene_passages()` | 1525 | 97 lines |
| `_shield_minted_edges()` | 1249 | 95 lines |
| `beat_movement_cuts()` | 3077 | 94 lines |
| `_mirror_symmetric_barriers()` | 1154 | 93 lines |

### `world/spatial_orientation.py`

| Function | Start | Size |
|---|---:|---:|
| `normalize_scene_bearings()` | 197 | 173 lines |
| `derived_edge_bearings()` | 409 | 71 lines |
| `strip_one_storey_verticals()` | 164 | 31 lines |
| `travel_bearing()` | 133 | 29 lines |
| `_spread_along_wall()` | 372 | 21 lines |
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
| `contact_sensation()` | 211 | 178 lines |
| `contact_phrase()` | 115 | 94 lines |
| `spatial_facts()` | 391 | 86 lines |
| `_interior_label()` | 57 | 56 lines |
| `_owner_spellings()` | 41 | 14 lines |

### `world/spatial_routing.py`

| Function | Start | Size |
|---|---:|---:|
| `sprint_reach()` | 1272 | 184 lines |
| `visible_adjacent_rooms()` | 1538 | 170 lines |
| `corridor_sightlines()` | 1078 | 126 lines |
| `spatial_rel()` | 363 | 122 lines |
| `_onward_exits()` | 1458 | 78 lines |
| `_walk_steps()` | 925 | 65 lines |
| `attended_rooms()` | 554 | 61 lines |
| `rooms_walked_within()` | 817 | 54 lines |

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
| `_hear_level()` | 1708 | 167 lines |
| `_opening_view_cap()` | 870 | 154 lines |
| `spatial_rel_between()` | 686 | 128 lines |
| `_visual_level_between()` | 1071 | 94 lines |
| `comms_reachable_rooms()` | 280 | 66 lines |
| `comms_link()` | 376 | 66 lines |
| `hearing_reason()` | 1877 | 65 lines |
| `scent_level()` | 39 | 56 lines |

### `world/spatial_sound_field.py`

| Function | Start | Size |
|---|---:|---:|
| `sound_sources()` | 2008 | 176 lines |
| `stamp_sound_relation()` | 3407 | 157 lines |
| `_voice_flood()` | 4865 | 98 lines |
| `spread()` | 1659 | 88 lines |
| `sound_shape()` | 5262 | 80 lines |
| `doorway_air_loss_db()` | 2731 | 74 lines |
| `distant_sounds()` | 5061 | 69 lines |
| `tread_events()` | 3986 | 66 lines |

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
| `settle_departures()` | 1017 | 266 lines |
| `apply_transit_dock_edges()` | 689 | 236 lines |
| `evict_self_contained_entities()` | 487 | 89 lines |
| `sync_entity_interior_rooms()` | 139 | 84 lines |
| `journey_seconds()` | 1464 | 78 lines |
| `_release_dock_passages()` | 627 | 60 lines |
| `settle_link_conditions()` | 419 | 50 lines |
| `_is_body_entity()` | 64 | 49 lines |

### `world/spatial_walk.py`

| Function | Start | Size |
|---|---:|---:|
| `walk()` | 357 | 186 lines |
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
| `claim_frontier_spaces()` | 3087 | 207 lines |
| `mint_frontier()` | 1186 | 197 lines |
| `plant_structure()` | 1385 | 195 lines |
| `prepare_frontier_expansion()` | 2843 | 188 lines |
| `materialize_planned_fringe()` | 1582 | 160 lines |
| `hold_planned_fixtures()` | 2268 | 141 lines |
| `planned_room_brief()` | 2107 | 106 lines |
| `_lay_stub_on_its_plan()` | 348 | 95 lines |

### `world/subjects.py`

| Function | Start | Size |
|---|---:|---:|
| `_resolve_room()` | 296 | 47 lines |
| `resolve_subject()` | 453 | 45 lines |
| `_resolve_character()` | 201 | 32 lines |
| `_lore_matches()` | 349 | 29 lines |
| `_resolve_from_lore()` | 380 | 29 lines |
| `_cast_matches()` | 123 | 27 lines |
| `_presence_reason()` | 173 | 26 lines |
| `_registry_room_matches()` | 270 | 24 lines |

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
| `obstructed()` | 245 | 58 lines |
| `_visible_vistas()` | 319 | 42 lines |
| `normalize_vista()` | 72 | 40 lines |
| `what_a_look_finds()` | 386 | 31 lines |
| `air_from_weather()` | 187 | 19 lines |
| `outlooks()` | 222 | 17 lines |
| `looked_vistas()` | 367 | 17 lines |
| `beyond_the_horizon()` | 147 | 16 lines |

### `world/weather.py`

| Function | Start | Size |
|---|---:|---:|
| `_normalize_weather_record()` | 526 | 150 lines |
| `weather_for_room()` | 1115 | 89 lines |
| `weather_course()` | 1486 | 77 lines |
| `weather_depth()` | 984 | 57 lines |
| `ground_after()` | 1701 | 52 lines |
| `weather_sound_words()` | 1281 | 38 lines |
| `normalize_weather()` | 487 | 37 lines |
| `_derive_exposure()` | 810 | 37 lines |

## FastAPI routes

| Method | Path | Handler | Source |
|---|---|---|---|
| GET | `/` | `index()` | `web/app.py:693` |
| PUT | `/api/active_preset` | `set_active()` | `web/app.py:2808` |
| PUT | `/api/affect_habituation` | `set_affect_habituation()` | `web/app.py:3135` |
| PUT | `/api/agent_models` | `put_agent_models()` | `web/app.py:2244` |
| PUT | `/api/ambience` | `put_ambience()` | `web/app.py:2430` |
| GET | `/api/ambience/library` | `ambience_library()` | `web/app.py:8619` |
| GET | `/api/ambience/search` | `ambience_search()` | `web/app.py:8598` |
| PUT | `/api/attire_beneath` | `set_attire_beneath()` | `web/app.py:3154` |
| POST | `/api/auth/login` | `auth_login()` | `web/auth_routes.py:209` |
| POST | `/api/auth/logout` | `auth_logout()` | `web/auth_routes.py:275` |
| POST | `/api/auth/setup` | `auth_setup()` | `web/auth_routes.py:134` |
| GET | `/api/auth/status` | `auth_status()` | `web/auth_routes.py:124` |
| GET | `/api/auto_promote` | `get_auto_promote()` | `web/app.py:5246` |
| PUT | `/api/auto_promote` | `set_auto_promote()` | `web/app.py:5259` |
| PUT | `/api/backdrops` | `put_backdrops()` | `web/app.py:2420` |
| GET | `/api/bootstrap` | `bootstrap_response()` | `web/app.py:2016` |
| POST | `/api/characters` | `char_create()` | `web/app.py:3661` |
| POST | `/api/characters/generate` | `char_generate()` | `web/app.py:3638` |
| POST | `/api/characters/import` | `char_import()` | `web/app.py:3692` |
| DELETE | `/api/characters/{cid}` | `char_del()` | `web/app.py:4044` |
| PUT | `/api/characters/{cid}` | `char_edit()` | `web/app.py:4011` |
| GET | `/api/characters/{cid}/export` | `char_export()` | `web/app.py:4003` |
| POST | `/api/characters/{cid}/fill_appearance` | `char_fill_appearance()` | `web/app.py:3982` |
| POST | `/api/characters/{cid}/fill_interior` | `char_fill_interior()` | `web/app.py:3935` |
| POST | `/api/characters/{cid}/fill_psychology` | `char_fill_psychology()` | `web/app.py:3899` |
| POST | `/api/characters/{cid}/generate_greeting` | `char_generate_greeting()` | `web/app.py:3864` |
| POST | `/api/characters/{cid}/recover_greetings` | `char_recover_greetings()` | `web/app.py:3854` |
| POST | `/api/characters/{cid}/start` | `character_start_story()` | `web/app.py:3716` |
| POST | `/api/chats` | `chat_new()` | `web/app.py:4491` |
| POST | `/api/chats/import` | `import_chat()` | `persist/chat_archive.py:530` |
| DELETE | `/api/chats/{cid}` | `chat_del()` | `web/app.py:4731` |
| GET | `/api/chats/{cid}` | `chat_get()` | `web/app.py:4739` |
| PUT | `/api/chats/{cid}` | `chat_edit()` | `web/app.py:4589` |
| POST | `/api/chats/{cid}/abort` | `chat_abort()` | `web/app.py:7241` |
| GET | `/api/chats/{cid}/ambience/oneshot/{name}` | `ambience_oneshot()` | `web/app.py:8628` |
| DELETE | `/api/chats/{cid}/ambience/pin` | `ambience_pin_delete()` | `web/app.py:8676` |
| PUT | `/api/chats/{cid}/ambience/pin` | `ambience_pin_put()` | `web/app.py:8657` |
| GET | `/api/chats/{cid}/ambience/pins` | `ambience_pins_get()` | `web/app.py:8652` |
| GET | `/api/chats/{cid}/ambience/{signature}.audio` | `ambience_audio()` | `web/app.py:8582` |
| GET | `/api/chats/{cid}/attire` | `attire_get()` | `web/app.py:6236` |
| PUT | `/api/chats/{cid}/attire` | `attire_put()` | `web/app.py:6247` |
| GET | `/api/chats/{cid}/backdrop/{signature}.png` | `backdrop_image()` | `web/app.py:8421` |
| GET | `/api/chats/{cid}/background_config` | `bg_cfg_get()` | `web/app.py:6523` |
| PUT | `/api/chats/{cid}/background_config` | `bg_cfg_put()` | `web/app.py:6527` |
| POST | `/api/chats/{cid}/begin` | `chat_begin()` | `web/app.py:3824` |
| DELETE | `/api/chats/{cid}/bodies/{name}` | `body_presence_delete()` | `web/world_routes.py:2469` |
| PUT | `/api/chats/{cid}/bodies/{name}/pose` | `body_pose_put()` | `web/world_routes.py:2568` |
| PUT | `/api/chats/{cid}/bodies/{name}/room` | `body_room_put()` | `web/world_routes.py:2503` |
| PUT | `/api/chats/{cid}/bodies/{name}/station` | `body_station_put()` | `web/world_routes.py:2068` |
| POST | `/api/chats/{cid}/characters` | `chat_add_char()` | `web/app.py:5067` |
| DELETE | `/api/chats/{cid}/characters/{ch}` | `chat_del_char()` | `web/app.py:5708` |
| PUT | `/api/chats/{cid}/characters/{ch}/card` | `chat_char_card_put()` | `web/app.py:5722` |
| PUT | `/api/chats/{cid}/characters/{ch}/dialogue_color` | `dialogue_color_put()` | `web/app.py:6095` |
| POST | `/api/chats/{cid}/characters/{ch}/fill_appearance` | `chat_char_fill_appearance()` | `web/app.py:3989` |
| POST | `/api/chats/{cid}/characters/{ch}/fill_interior` | `chat_char_fill_interior()` | `web/app.py:3946` |
| POST | `/api/chats/{cid}/characters/{ch}/fill_psychology` | `chat_char_fill_psychology()` | `web/app.py:3906` |
| GET | `/api/chats/{cid}/characters/{ch}/memories` | `mem_list()` | `web/app.py:6800` |
| POST | `/api/chats/{cid}/characters/{ch}/memories` | `mem_add()` | `web/app.py:6947` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/backfill` | `mem_backfill()` | `web/app.py:6917` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/consolidate` | `mem_consolidate()` | `web/app.py:6902` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/coverage` | `mem_coverage()` | `web/app.py:6938` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/export` | `mem_export()` | `web/app.py:6846` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/import` | `mem_import()` | `web/app.py:6857` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/search` | `mem_search()` | `web/app.py:6821` |
| GET | `/api/chats/{cid}/characters/{ch}/memory-context` | `memory_context_preview()` | `web/app.py:6878` |
| PUT | `/api/chats/{cid}/characters/{ch}/position` | `chat_char_position_put()` | `web/app.py:5959` |
| GET | `/api/chats/{cid}/characters/{ch}/private_history` | `ph_get()` | `web/app.py:6068` |
| PUT | `/api/chats/{cid}/characters/{ch}/private_history` | `ph_put()` | `web/app.py:6083` |
| GET | `/api/chats/{cid}/characters/{ch}/relationships` | `relationships_get()` | `web/app.py:6891` |
| GET | `/api/chats/{cid}/charters` | `charters_get()` | `web/app.py:6414` |
| PUT | `/api/chats/{cid}/charters` | `charters_put()` | `web/app.py:6435` |
| GET | `/api/chats/{cid}/charters/diagnostics` | `charters_diagnostics()` | `web/app.py:6453` |
| POST | `/api/chats/{cid}/charters/generate` | `charters_generate()` | `web/app.py:6465` |
| DELETE | `/api/chats/{cid}/charters/job` | `charters_job_clear()` | `web/app.py:6506` |
| GET | `/api/chats/{cid}/charters/job` | `charters_job_get()` | `web/app.py:6487` |
| DELETE | `/api/chats/{cid}/charters/{charter_key}/bodies/{body_key}/station` | `charter_body_station_delete()` | `web/world_routes.py:2975` |
| PUT | `/api/chats/{cid}/charters/{charter_key}/bodies/{body_key}/station` | `charter_body_station_put()` | `web/world_routes.py:2908` |
| GET | `/api/chats/{cid}/debug` | `chat_debug_export()` | `web/app.py:2771` |
| GET | `/api/chats/{cid}/dialogue_config` | `dlg_get()` | `web/app.py:6311` |
| PUT | `/api/chats/{cid}/dialogue_config` | `dlg_put()` | `web/app.py:6318` |
| POST | `/api/chats/{cid}/doorways` | `doorway_create()` | `web/world_routes.py:2716` |
| DELETE | `/api/chats/{cid}/doorways/{room_id}/{to}` | `doorway_delete()` | `web/world_routes.py:2791` |
| PATCH | `/api/chats/{cid}/doorways/{room_id}/{to}` | `doorway_patch()` | `web/world_routes.py:2755` |
| GET | `/api/chats/{cid}/dramatic_irony` | `get_dramatic_irony_feed()` | `web/app.py:5170` |
| GET | `/api/chats/{cid}/export` | `export_chat()` | `persist/chat_archive.py:524` |
| GET | `/api/chats/{cid}/fixed_points` | `fixed_points_list()` | `web/app.py:6720` |
| POST | `/api/chats/{cid}/fixed_points` | `fixed_points_create()` | `web/app.py:6730` |
| DELETE | `/api/chats/{cid}/fixed_points/{anchor_id}` | `fixed_points_delete()` | `web/app.py:6752` |
| GET | `/api/chats/{cid}/frames` | `frames_list()` | `web/app.py:6673` |
| POST | `/api/chats/{cid}/frames` | `frames_create()` | `web/app.py:6677` |
| GET | `/api/chats/{cid}/guest_invites` | `list_guest_invites()` | `web/app.py:5446` |
| POST | `/api/chats/{cid}/guest_invites` | `create_guest_invite()` | `web/app.py:5426` |
| DELETE | `/api/chats/{cid}/guest_invites/{gid}` | `revoke_guest_invite()` | `web/app.py:5450` |
| GET | `/api/chats/{cid}/language` | `chat_language_get()` | `web/app.py:4556` |
| PUT | `/api/chats/{cid}/language` | `chat_language_put()` | `web/app.py:4573` |
| DELETE | `/api/chats/{cid}/lorebook` | `detach_lore()` | `web/app.py:4724` |
| POST | `/api/chats/{cid}/lorebook` | `bind_lore()` | `web/app.py:4696` |
| GET | `/api/chats/{cid}/lorebooks` | `chat_lorebooks_owned()` | `web/app.py:3248` |
| POST | `/api/chats/{cid}/lorebooks` | `attach_lore()` | `web/app.py:4620` |
| DELETE | `/api/chats/{cid}/lorebooks/{lid}` | `detach_book()` | `web/app.py:4683` |
| PUT | `/api/chats/{cid}/lorebooks/{lid}` | `set_book_enabled()` | `web/app.py:4649` |
| GET | `/api/chats/{cid}/map` | `map_index()` | `web/world_routes.py:1446` |
| GET | `/api/chats/{cid}/map/plan` | `map_plan()` | `web/world_routes.py:1458` |
| GET | `/api/chats/{cid}/naming_profile` | `naming_profile_get()` | `web/app.py:6554` |
| PUT | `/api/chats/{cid}/naming_profile` | `naming_profile_put()` | `web/app.py:6566` |
| GET | `/api/chats/{cid}/paradox_policy` | `paradox_policy_get()` | `web/app.py:6705` |
| PUT | `/api/chats/{cid}/paradox_policy` | `paradox_policy_put()` | `web/app.py:6709` |
| GET | `/api/chats/{cid}/persona_private_history` | `pph_get()` | `web/app.py:6158` |
| PUT | `/api/chats/{cid}/persona_private_history` | `pph_put()` | `web/app.py:6171` |
| GET | `/api/chats/{cid}/personas` | `chat_list_extra_personas()` | `web/app.py:5264` |
| POST | `/api/chats/{cid}/personas` | `chat_add_persona()` | `web/app.py:5309` |
| DELETE | `/api/chats/{cid}/personas/{pid}` | `chat_del_persona()` | `web/app.py:5336` |
| PUT | `/api/chats/{cid}/personas/{pid}/station` | `chat_persona_station()` | `web/app.py:5274` |
| GET | `/api/chats/{cid}/player_authority` | `player_authority_get()` | `web/app.py:6637` |
| PUT | `/api/chats/{cid}/player_authority` | `player_authority_put()` | `web/app.py:6652` |
| GET | `/api/chats/{cid}/player_view` | `player_view_get()` | `web/app.py:6614` |
| GET | `/api/chats/{cid}/positions` | `chat_positions_get()` | `web/app.py:5892` |
| POST | `/api/chats/{cid}/prelude` | `chat_prelude()` | `web/app.py:3792` |
| GET | `/api/chats/{cid}/promises` | `get_promise_ledger()` | `web/app.py:5174` |
| GET | `/api/chats/{cid}/promotable` | `list_promotable_presences()` | `web/app.py:5166` |
| POST | `/api/chats/{cid}/promotions/confirm` | `confirm_promotion()` | `web/app.py:5195` |
| POST | `/api/chats/{cid}/promotions/draft` | `draft_promotion()` | `web/app.py:5178` |
| POST | `/api/chats/{cid}/regions` | `region_create()` | `web/world_routes.py:2824` |
| PATCH | `/api/chats/{cid}/regions/{region_id}` | `region_patch()` | `web/world_routes.py:1998` |
| POST | `/api/chats/{cid}/retry_start` | `chat_retry_start()` | `web/app.py:2714` |
| GET | `/api/chats/{cid}/room` | `room_thread()` | `web/room_routes.py:52` |
| POST | `/api/chats/{cid}/room/mandates/{uid}/revoke` | `room_revoke()` | `web/room_routes.py:108` |
| POST | `/api/chats/{cid}/room/messages` | `room_say()` | `web/room_routes.py:65` |
| POST | `/api/chats/{cid}/room/messages/stream` | `room_say_stream()` | `web/room_routes.py:78` |
| GET | `/api/chats/{cid}/room/status` | `room_status()` | `web/room_routes.py:117` |
| GET | `/api/chats/{cid}/rooms` | `rooms_index()` | `web/world_routes.py:770` |
| POST | `/api/chats/{cid}/rooms` | `room_create()` | `web/world_routes.py:2243` |
| DELETE | `/api/chats/{cid}/rooms/{room_id}` | `room_delete()` | `web/world_routes.py:2309` |
| GET | `/api/chats/{cid}/rooms/{room_id}` | `rooms_slice()` | `web/world_routes.py:933` |
| PATCH | `/api/chats/{cid}/rooms/{room_id}` | `room_patch()` | `web/world_routes.py:1827` |
| POST | `/api/chats/{cid}/rooms/{room_id}/entities` | `room_entity_create()` | `web/world_routes.py:2348` |
| DELETE | `/api/chats/{cid}/rooms/{room_id}/entities/{entity_id}` | `room_entity_delete()` | `web/world_routes.py:2384` |
| PATCH | `/api/chats/{cid}/rooms/{room_id}/entities/{entity_id}` | `room_entity_patch()` | `web/world_routes.py:1897` |
| GET | `/api/chats/{cid}/rooms/{room_id}/grid` | `rooms_grid()` | `web/world_routes.py:1380` |
| POST | `/api/chats/{cid}/rooms/{room_id}/presences` | `room_presence_create()` | `web/world_routes.py:2429` |
| GET | `/api/chats/{cid}/setup_log` | `chat_setup_log()` | `web/app.py:2747` |
| GET | `/api/chats/{cid}/story_view` | `story_view_get()` | `web/app.py:6580` |
| GET | `/api/chats/{cid}/style_guide` | `style_guide_get()` | `web/app.py:6293` |
| PUT | `/api/chats/{cid}/style_guide` | `style_guide_put()` | `web/app.py:6299` |
| GET | `/api/chats/{cid}/survival` | `survival_get()` | `web/app.py:5800` |
| PUT | `/api/chats/{cid}/survival` | `survival_put()` | `web/app.py:5805` |
| POST | `/api/chats/{cid}/turns` | `turn_new()` | `web/app.py:7000` |
| POST | `/api/chats/{cid}/turns/{idx}/player_input` | `submit_extra_player_input()` | `web/app.py:5350` |
| GET | `/api/chats/{cid}/viewers` | `viewers_get()` | `web/app.py:6629` |
| GET | `/api/chats/{cid}/vitals` | `chat_vitals_get()` | `web/app.py:5857` |
| GET | `/api/chats/{cid}/world` | `world_get()` | `web/app.py:6177` |
| PUT | `/api/chats/{cid}/world` | `world_put()` | `web/app.py:6187` |
| PUT | `/api/debug_capture` | `put_debug_capture()` | `web/app.py:2381` |
| PUT | `/api/decision_model` | `put_decision_model()` | `web/app.py:2327` |
| GET | `/api/default_prompts` | `default_prompts()` | `web/app.py:2611` |
| PUT | `/api/exemplars` | `put_exemplars()` | `web/app.py:2350` |
| GET | `/api/extensions` | `extensions_list()` | `web/app.py:2825` |
| POST | `/api/extensions/install` | `extension_install()` | `web/app.py:2857` |
| GET | `/api/extensions/ui.css` | `extensions_ui_css()` | `web/app.py:3047` |
| GET | `/api/extensions/ui.js` | `extensions_ui()` | `web/app.py:3038` |
| GET | `/api/extensions/updates` | `extension_updates()` | `web/app.py:2880` |
| DELETE | `/api/extensions/{eid}` | `extension_remove()` | `web/app.py:2904` |
| GET | `/api/extensions/{eid}/asset/{path:path}` | `extension_asset()` | `web/app.py:3111` |
| POST | `/api/extensions/{eid}/disable` | `extension_disable()` | `web/app.py:2915` |
| DELETE | `/api/extensions/{eid}/document` | `extension_document_delete()` | `web/app.py:3015` |
| GET | `/api/extensions/{eid}/document` | `extension_document_get()` | `web/app.py:2983` |
| PUT | `/api/extensions/{eid}/document` | `extension_document_put()` | `web/app.py:2995` |
| DELETE | `/api/extensions/{eid}/documents` | `extension_documents_delete()` | `web/app.py:3025` |
| GET | `/api/extensions/{eid}/documents` | `extension_documents_list()` | `web/app.py:2962` |
| GET | `/api/extensions/{eid}/documents/verify` | `extension_documents_verify()` | `web/app.py:2973` |
| POST | `/api/extensions/{eid}/enable` | `extension_enable()` | `web/app.py:2846` |
| GET | `/api/extensions/{eid}/state` | `extension_state()` | `web/app.py:2924` |
| GET | `/api/extensions/{eid}/ui.css` | `extension_ui_css_one()` | `web/app.py:3069` |
| GET | `/api/extensions/{eid}/ui.js` | `extension_ui_one()` | `web/app.py:3057` |
| POST | `/api/extensions/{eid}/update` | `extension_update()` | `web/app.py:2891` |
| POST | `/api/guest/input` | `guest_input()` | `web/app.py:5689` |
| GET | `/api/guest/state` | `guest_state()` | `web/app.py:5534` |
| PUT | `/api/image_model` | `put_image_model()` | `web/app.py:2305` |
| POST | `/api/join` | `join_with_code()` | `web/app.py:5456` |
| GET | `/api/language-packs` | `language_packs_get()` | `web/app.py:4509` |
| GET | `/api/language-packs/{language_id}/ui` | `language_pack_ui()` | `web/app.py:4530` |
| DELETE | `/api/lore_entries/{eid}` | `lore_entry_delete()` | `web/app.py:4466` |
| PUT | `/api/lore_entries/{eid}` | `lore_entry_edit()` | `web/app.py:4390` |
| DELETE | `/api/lore_entries/{eid}/overlay` | `lore_entry_overlay_clear()` | `web/app.py:4478` |
| DELETE | `/api/lore_gen_jobs/{job_id}` | `lorebook_generate_discard()` | `web/app.py:3405` |
| POST | `/api/lore_gen_jobs/{job_id}/resume` | `lorebook_generate_resume()` | `web/app.py:3387` |
| DELETE | `/api/lorebook_links/{link_id}` | `lorebook_link_delete()` | `web/app.py:3344` |
| PUT | `/api/lorebook_links/{link_id}` | `lorebook_link_update()` | `web/app.py:3330` |
| POST | `/api/lorebooks` | `lore_create()` | `web/app.py:4168` |
| POST | `/api/lorebooks/import` | `lore_import()` | `web/app.py:3441` |
| DELETE | `/api/lorebooks/{lid}` | `lore_delete()` | `web/app.py:4256` |
| GET | `/api/lorebooks/{lid}` | `lore_get()` | `web/app.py:4144` |
| PUT | `/api/lorebooks/{lid}` | `lore_edit()` | `web/app.py:4190` |
| POST | `/api/lorebooks/{lid}/apply_plan` | `lorebook_apply_plan()` | `web/app.py:3414` |
| POST | `/api/lorebooks/{lid}/entries` | `lore_entry_create()` | `web/app.py:4307` |
| GET | `/api/lorebooks/{lid}/export` | `lore_export()` | `web/app.py:4262` |
| POST | `/api/lorebooks/{lid}/generate` | `lore_generate()` | `web/app.py:4293` |
| GET | `/api/lorebooks/{lid}/generate_job` | `lorebook_generate_job()` | `web/app.py:3376` |
| POST | `/api/lorebooks/{lid}/generate_plan` | `lorebook_generate_plan()` | `web/app.py:3349` |
| GET | `/api/lorebooks/{lid}/links` | `lorebook_links_get()` | `web/app.py:3303` |
| POST | `/api/lorebooks/{lid}/links` | `lorebook_link_create()` | `web/app.py:3308` |
| POST | `/api/lorebooks/{lid}/move` | `lorebook_move()` | `web/app.py:3230` |
| POST | `/api/lorebooks/{lid}/reinterpret` | `lore_reinterpret_route()` | `web/app.py:4279` |
| POST | `/api/lorebooks/{lid}/reorder` | `lorebook_reorder()` | `web/app.py:3239` |
| GET | `/api/maintenance/checkpoints` | `maintenance_checkpoints()` | `web/app.py:3177` |
| POST | `/api/maintenance/checkpoints/compact` | `maintenance_compact()` | `web/app.py:3203` |
| PUT | `/api/max_output_tokens` | `put_max_output_tokens()` | `web/app.py:2578` |
| DELETE | `/api/memories/{mid}` | `mem_del()` | `web/app.py:6994` |
| PUT | `/api/memories/{mid}` | `mem_edit()` | `web/app.py:6973` |
| GET | `/api/memory/embeddings` | `memory_embeddings_status()` | `web/app.py:2278` |
| POST | `/api/memory/embeddings/rebuild` | `memory_embeddings_rebuild()` | `web/app.py:2293` |
| GET | `/api/nsfw` | `get_nsfw()` | `web/app.py:3126` |
| PUT | `/api/nsfw` | `set_nsfw()` | `web/app.py:3130` |
| GET | `/api/openrouter/endpoints` | `get_openrouter_endpoints()` | `web/app.py:2510` |
| PUT | `/api/openrouter_routing` | `put_openrouter_routing()` | `web/app.py:2496` |
| POST | `/api/personas` | `persona_create()` | `web/app.py:4082` |
| POST | `/api/personas/generate` | `persona_generate()` | `web/app.py:4060` |
| POST | `/api/personas/import` | `persona_import()` | `web/app.py:4102` |
| DELETE | `/api/personas/{pid}` | `persona_del()` | `web/app.py:4138` |
| PUT | `/api/personas/{pid}` | `persona_edit()` | `web/app.py:4125` |
| GET | `/api/personas/{pid}/export` | `persona_export()` | `web/app.py:4116` |
| POST | `/api/personas/{pid}/fill_appearance` | `persona_fill_appearance()` | `web/app.py:3998` |
| PUT | `/api/prompt_presets` | `save_preset()` | `web/app.py:2622` |
| POST | `/api/prompt_presets/import` | `import_preset()` | `web/app.py:2785` |
| DELETE | `/api/prompt_presets/{name}` | `del_preset()` | `web/app.py:2799` |
| GET | `/api/prompt_presets/{name}/export` | `export_preset()` | `web/app.py:2649` |
| POST | `/api/providers` | `add_provider()` | `web/app.py:3502` |
| DELETE | `/api/providers/{pid}` | `del_provider()` | `web/app.py:3616` |
| PUT | `/api/providers/{pid}` | `put_provider()` | `web/app.py:3509` |
| GET | `/api/providers/{pid}/image_models` | `image_models()` | `web/app.py:3628` |
| GET | `/api/providers/{pid}/models` | `models()` | `web/app.py:3621` |
| PUT | `/api/providers/{pid}/prompt_cache` | `put_provider_prompt_cache()` | `web/app.py:3537` |
| PUT | `/api/reasoning_effort` | `put_reasoning_effort()` | `web/app.py:2522` |
| GET | `/api/research` | `get_research()` | `web/app.py:2471` |
| PUT | `/api/research` | `put_research()` | `web/app.py:2476` |
| PUT | `/api/response_format` | `put_response_format()` | `web/app.py:2553` |
| POST | `/api/steps/{sid}/activate` | `step_activate()` | `web/app.py:8164` |
| POST | `/api/steps/{sid}/edit` | `step_edit()` | `web/app.py:8152` |
| POST | `/api/steps/{sid}/reroll` | `step_reroll()` | `web/app.py:8084` |
| DELETE | `/api/turns/{tid}` | `turn_del()` | `web/app.py:8179` |
| GET | `/api/turns/{tid}/ambience` | `turn_ambience()` | `web/app.py:8531` |
| POST | `/api/turns/{tid}/ambience` | `turn_ambience_resolve()` | `web/app.py:8548` |
| GET | `/api/turns/{tid}/backdrop` | `turn_backdrop()` | `web/app.py:8375` |
| POST | `/api/turns/{tid}/backdrop` | `turn_backdrop_generate()` | `web/app.py:8390` |
| POST | `/api/turns/{tid}/branch` | `turn_branch()` | `web/app.py:7245` |
| PUT | `/api/turns/{tid}/input` | `edit_input()` | `web/app.py:7776` |
| GET | `/api/turns/{tid}/narration` | `turn_narration_variants()` | `web/app.py:7875` |
| POST | `/api/turns/{tid}/narration` | `turn_narration_select()` | `web/app.py:7896` |
| GET | `/api/turns/{tid}/pipeline` | `pipeline_get()` | `web/app.py:7930` |
| PUT | `/api/turns/{tid}/prose` | `edit_prose()` | `web/app.py:7803` |
| POST | `/api/turns/{tid}/reroll` | `turn_reroll()` | `web/app.py:8015` |
| POST | `/api/turns/{tid}/rerun` | `turn_rerun()` | `web/app.py:8025` |
| POST | `/api/turns/{tid}/resume` | `turn_resume()` | `web/app.py:8052` |
| GET | `/api/turns/{tid}/status` | `turn_status()` | `web/app.py:7200` |
| GET | `/api/turns/{turn_id}/debug` | `turn_debug_export()` | `web/app.py:2658` |
| GET | `/api/ui` | `ui_catalog_get()` | `web/app.py:4520` |
| PUT | `/api/ui-language` | `ui_language_put()` | `web/app.py:4545` |
| GET | `/api/updates/check` | `updates_check()` | `web/app.py:3169` |
| POST | `/api/updates/install` | `updates_install()` | `web/app.py:3173` |
| GET | `/guest` | `guest_page()` | `web/app.py:630` |
| GET | `/login` | `login_page()` | `web/app.py:699` |

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

### `static/js/ambience.js` (1134 lines)

Sections: Room ambience (`:2`); seamless looping (`:268`); one-shots (`:767`); the ambience panel (`:817`); the mix (`:835`).

Declared functions: `ambienceStoredRaw()`, `ambienceStore()`, `ambienceStored()`, `ambienceElement()`, `entryAudios()`, `applyAmbienceMute()`, `setAmbienceVolume()`, `ambienceLevel()`, `setLayerGain()`, `toggleAmbienceMute()`, `ambienceFadeClock()`, `ambienceEnsureSounding()`, `ambienceFadeMix()`, `armSeamlessLoop()`, `crossLoop()`, `retireEntries()`, `stopAmbience()`, `playAmbience()`, `armAmbienceUnlock()`, `ambienceWorking()`, `awaitAmbience()`, `resolveAmbience()`, `ambienceForTurn()`, `rerollAmbience()`, `ambienceOnVisibleTurn()`, `ambienceResetForRender()`, `updateAmbienceBtn()`, `playAmbienceOneshot()`, `ambienceCandidateRow()`, `ambienceLayerRow()`, `ambienceMixPanel()`, `openAmbiencePanel()`, `toggleAmbience()`, `syncAmbience()`.

### `static/js/app.js` (1353 lines)

Sections: Boot & sidebar (`:1`); and then nothing showed the report, so a host who installed a pack got (`:50`); New chat wizard (`:381`); NSFW (`:1032`); Composer (`:1062`); Init (`:1144`); Embedding reconciler progress (`:1204`).

Declared functions: `boot()`, `renderSide()`, `syncExtensionTabs()`, `renderChatSidebar()`, `failedSetupRow()`, `newChatWizard()`, `renderWizardChoice()`, `storyLanguagePacks()`, `defaultStoryLanguage()`, `wizardState()`, `wizardHistoryCharacters()`, `discardFailedStorySetup()`, `wizardFromScratch()`, `renderWizardPersona()`, `renderWizardCharacters()`, `renderWizardScenario()`, `runWizard()`, `renderCharacterSidebar()`, `renderPersonaSidebar()`, `updateNSFWBtn()`, `toggleNSFW()`, `resizeComposer()`, `erCard()`, `erDismiss()`, `erPoll()`, `erWatch()`, `erOfferRebuild()`.

### `static/js/backdrops.js` (430 lines)

Sections: Scene backdrops (`:2`).

Declared functions: `backdropLayers()`, `backdropLuminance()`, `applyBackdropContrast()`, `releaseBackdropLayer()`, `clearBackdrop()`, `showBackdrop()`, `backdropWorking()`, `awaitBackdrop()`, `generateBackdrop()`, `backdropForTurn()`, `backdropOnVisibleTurn()`, `backdropResetForRender()`, `updateBackdropBtn()`, `toggleBackdrops()`, `syncBackdrops()`.

### `static/js/chat.js` (3802 lines)

Sections: The turn being read (`:1`); Colouring who spoke (`:225`); `dialogue_log` is committed per turn and arrives as `turn.speech` -- and (`:228`); Flipping between rerolls of the newest beat (`:1267`); Pipeline drawer: reading a step through a lens (`:1758`); Pipeline drawer (`:2395`); Relationship viewer (`:2861`); Memory browser (`:2941`); Private history (`:3740`).

Declared functions: `observeVisibleTurn()`, `openChat()`, `foldTypography()`, `decodeProseEntities()`, `splitEmphasis()`, `appendEmphasized()`, `quoteBody()`, `quotedRegions()`, `speechSpans()`, `paintProse()`, `proseEl()`, `renderFrameBar()`, `switchFrame()`, `syncComposerToFrame()`, `updateChatScopedButtons()`, `renderChat()`, `turnElement()`, `renderChatAppend()`, `beginStory()`, `branchTurn()`, `editTurnInput()`, `editTurnProse()`, `liveReset()`, `friendlyPhase()`, `turnStatusStart()`, `turnStatusSet()`, `turnStatusStop()`, `_streamOn()`, `liveFlush()`, `liveAppend()`, `stepLabel()`, `liveStep()`, `handleEvt()`, `inCurrentScope()`, `showNarrationEarly()`, `clearNarrationEarly()`, `resetRerollNav()`, `_mountRerollNav()`, `_paintRerollCount()`, `showRerollVariant()`, `abortActiveRun()`, `runStream()`, `beginRun()`, `finishRun()`, `giveLineBack()`, `followRun()`, `followEnded()`, `newestTurnOfRun()`, `followRunningTurn()`, `confirmCheckpointRestore()`, `runReroll()`, `rerollTurn()`, `exportChat()`, `importChatModal()`, `perceiverViews()`, `loopMindIds()`, `specialistIds()`, `stepLenses()`, `perceiverLabel()`, `facetBadge()`, `lensLabel()`, `renderLensBar()`, `lensSlice()`, `specialistSlice()`, `proseContractRecord()`, `proseContractIds()`, `proseContractLabel()`, `proseContractSlice()`, `perceptionPacketSlice()`, `perceiverSlice()`, `mindSlice()`, `keySlice()`, `renderEngineNotes()`, `pipelineMapPanel()`, `closePipeline()`, `openPipeline()`, `relMeter()`, `relationshipModal()`, `memModal()`, `exportCharacterMemories()`, `importCharacterMemoriesModal()`, `memQS()`, `memCharId()`, `loadMemoryBrowse()`, `getMemUI()`, `renderMemorySummary()`, `sortedMems()`, `renderMemoryList()`, `memoryCard()`, `fieldWrap()`, `reloadMemView()`, `runMemorySearch()`, `showNewMemoryForm()`, `checkMemoryCoverage()`, `backfillMemoryEras()`, `consolidateMemories()`, `previewMemoryContext()`, `chatPH()`, `personaPH()`.

### `static/js/chime.js` (198 lines)

Sections: Turn-completion chime (`:2`); Which other waits are worth a chime (`:125`).

Declared functions: `chimeStoredMuted()`, `chimeContext()`, `chimeArm()`, `chimePlay()`, `chimeWatches()`, `chimeWorkFinished()`, `chimeSetMuted()`, `toggleChimeMute()`, `updateChimeBtn()`.

### `static/js/components.js` (1438 lines)

Sections: Modal (`:58`); Book covers (`:74`); confirm()/prompt() replacements (`:187`); Toasts (`:577`); Background tasks (`:622`); Form helpers (`:708`); Model picker (`:1273`); made for every combobox that already has a provider saved -- opened its (`:1318`).

Declared functions: `txt()`, `el()`, `coverOfRow()`, `coverOfTitle()`, `modal()`, `modalOwnership()`, `closeModal()`, `closeAllModals()`, `_confirmOverlay()`, `confirmModal()`, `promptModal()`, `promptModalWithToggle()`, `livedLocationControl()`, `attachStoryLorebook()`, `generateStoryLocation()`, `openLivedLocationDialog()`, `toastHost()`, `toast()`, `renderActivity()`, `elapsedLabel()`, `activityTicking()`, `backgroundTask()`, `buttonTask()`, `loadingBlock()`, `emptyState()`, `fText()`, `fArea()`, `fSelect()`, `fNum()`, `fLineList()`, `fStrList()`, `attireRegions()`, `attireRegionZones()`, `attireOptInZones()`, `fCoveragePicker()`, `fAttireGarments()`, `fList()`, `fAbilities()`, `fTraits()`, `fValues()`, `fBeliefs()`, `fCopingStrategies()`, `fAssociations()`, `fGoals()`, `fSenses()`, `fLatent()`, `extraPartAspects()`, `fExtraParts()`, `interiorLights()`, `fInteriorStations()`, `fPronouns()`, `phEditor()`, `cachedCatalogue()`, `fetchModels()`, `fetchImageModels()`, `modelCombobox()`, `emitChange()`, `load()`, `showDD()`.

### `static/js/editors.js` (1252 lines)

Sections: how many stations, and how many of them are new -- rather than letting a (`:62`); Carrying the fields an editor has no widget for (`:138`); A fill is a proposal over the FORM, never over the stored card (`:178`); Background-character promotion (`:1070`); Import (file upload) (`:1124`); Generate (`:1200`); Lorebook generate (`:1223`); Export (`:1240`).

Declared functions: `appearanceFillButton()`, `interiorFillButton()`, `defaultCharacterSheet()`, `carryUnpresentedFields()`, `cardPathValue()`, `setCardPathValue()`, `fillCardGaps()`, `proposalOverForm()`, `greetingCarousel()`, `quickStartModal()`, `charEditor()`, `personaEditor()`, `promotionReviewModal()`, `promoteBackgroundPresence()`, `importModal()`, `generateModal()`, `generateLoreModal()`, `exportCharacter()`, `exportPersona()`, `exportLorebook()`.

### `static/js/extensions.js` (661 lines)

Sections: Extension host (`:2`); Registration attribution (`:20`); Failure containment (`:56`); ES module entries (`:86`); Registration surface (`:177`); Notices (`:222`); Host services (`:370`); The chat lifecycle, as a declared contract (`:401`); Host-internal accessors (`:483`); Hot load / unload (`:609`).

### `static/js/i18n-core.js` (415 lines)

Sections: The localization rules, once (`:3`).

Declared functions: `i18nCompileTemplates()`, `i18nMatchTemplate()`, `i18nRuleIndex()`, `i18nCandidates()`, `i18nIsTranslation()`, `i18nLookup()`, `i18nCollapse()`, `i18nTranslate()`, `i18nLocalize()`, `i18nObserve()`.

### `static/js/i18n.js` (34 lines)

### `static/js/lorebooks.js` (3971 lines)

Sections: generating or reinterpreting its entries, its own fields, its place in (`:99`); Library sidebar (`:367`); Data loading (`:560`); Workspace (`:674`); Book metadata and tree operations (`:1267`); Entry editor (`:1821`); Lorebook relationships (`:2670`); Advanced generator (`:3136`); Interrupted-generation recovery (`:3358`).

Declared functions: `loreDragStart()`, `loreDraggedBook()`, `loreDescendantIds()`, `loreLibraryWriteConfirmed()`, `loreLibraryBook()`, `loreBookTypeIcon()`, `inheritanceModes()`, `knowledgeTags()`, `knowledgeRanges()`, `loreLinkTypes()`, `normalizeLoreBook()`, `loreOwnershipKey()`, `loreRootBooks()`, `loreBooksByParent()`, `loreBookMatches()`, `loreVisibleIds()`, `loreBookLabel()`, `parseStoredJSON()`, `loreField()`, `loreSelect()`, `loreBookOptions()`, `renderLoreLibrarySidebar()`, `renderNode()`, `loreStoryQuery()`, `loreBookIsLibrary()`, `loadLoreWorkspaceData()`, `collectLoreLinkTargets()`, `loreWorkspaceVisible()`, `renderLoreWorkspaceBody()`, `openLoreWorkspace()`, `renderLoreInspector()`, `selectTab()`, `buildLoreWorkspace()`, `renderWorkspaceTree()`, `renderNode()`, `renderTreeList()`, `renderLoreBookEditor()`, `moveLoreBook()`, `reorderLoreBook()`, `promoteLoreBook()`, `demoteLoreBook()`, `createSiblingLoreBook()`, `createLoreBookDialog()`, `refreshLoreUI()`, `renderLoreEntries()`, `renderList()`, `buildLoreEntryCard()`, `buildLoreEntryBody()`, `splitNumberList()`, `reinterpretLoreBook()`, `generateLoreEntriesPrompt()`, `buildDirectLoreRequest()`, `renderRelationshipOverview()`, `renderLoreRelationshipEditor()`, `renderRelationshipList()`, `showNewRelationshipForm()`, `renderLoreGenerator()`, `adoptGeneratorPlan()`, `generatorPlanMessage()`, `loreGenAgo()`, `refreshLoreGenRecovery()`, `normalizeGeneratorPlan()`, `renderLorePlanPreview()`, `renderOperations()`, `planStat()`, `renderAnalysisSection()`, `addPlanGroup()`, `stripPlanUIFields()`, `acceptedGeneratorPlan()`.

### `static/js/settings.js` (4343 lines)

Sections: Chat tool modals (`:1`); Condition tab (`:832`); Survival tracker (`:892`); Character relocation (`:1204`); API connections (`:1974`); no `boot()`, which re-downloaded every card and book to change one (`:2747`); Software updates (host-only; git fast-forward from GitHub origin) (`:3476`); Legacy checkpoint conversion (host-only maintenance) (`:3508`); Prompts (`:3765`); and be able to load that pack's own sheets to edit, rather than (`:3776`); Extensions (`:3970`).

Declared functions: `paradoxModes()`, `frameQuery()`, `charterDiagnosticsPanel()`, `selectTab()`, `dialogueColorControl()`, `save()`, `renderCastTab()`, `renderConditionTab()`, `hydrateConditionTab()`, `vitalMeter()`, `syncVitalsGutterNow()`, `syncVitalsGutter()`, `hideVitalsHud()`, `vitalsBlock()`, `refreshVitalsHud()`, `clearVitalsHud()`, `hydrateCastLocations()`, `castRoomLabel()`, `castRoomSelect()`, `renderLorebooksTab()`, `renderBookNode()`, `renderMultiplayerTab()`, `renderFramesTab()`, `renderFramesListPanel()`, `renderPersonaStationingPanel()`, `renderParadoxPanel()`, `renderBackgroundPresencesPanel()`, `renderGuestInvitePanel()`, `renderInsightsTab()`, `renderDramaticIronyPanel()`, `renderPromiseLedgerPanel()`, `embeddingBankBlock()`, `modelRecommendationsBlock()`, `renderFirstRunProviderSetup()`, `preferredBackdropSize()`, `settleSwitch()`, `renderFullApiSettings()`, `propagateToFollowers()`, `renderUpdateChecking()`, `renderUpdateError()`, `checkpointCompactionBlock()`, `renderUpdateStatus()`, `runUpdateInstall()`, `renderUpdateDone()`, `openPromptsModal()`, `reopenPromptsIfRequested()`, `extensionTrustNote()`, `extensionCapabilitySummary()`, `extensionEnableConsent()`, `extensionSettingsSections()`, `openExtensionsMenu()`.

### `static/js/theme-init.js` (181 lines)

Declared functions: `readStored()`, `writeStored()`, `normaliseTheme()`, `normaliseProseSize()`, `applyTheme()`, `applyProseSize()`, `normaliseEffects()`, `applyEffects()`, `syncPageHidden()`.

### `static/js/themes.js` (159 lines)

Declared functions: `themePreview()`, `openAppearanceSettings()`.

### `static/js/utils.js` (309 lines)

Sections: API (`:105`); Download (`:288`); Card authoring warnings (`:297`).

Declared functions: `t()`, `watchUILanguage()`, `localizeDocument()`, `memoryCategories()`, `memoryProvenance()`, `hasDefaultModel()`, `safeId()`, `splitCL()`, `numOr()`, `taggedError()`, `errorDetailText()`, `api()`, `reportStaleCode()`, `apiOrNull()`, `streamPost()`, `downloadJSON()`, `showCardWarnings()`.

### `static/js/weather-fx.js` (638 lines)

Sections: Weather effects (`:2`); the tile (`:219`); the layers (`:292`); lifecycle (`:391`); lightning (`:481`); schedules nothing; the visibility handler re-enters through (`:507`).

Declared functions: `weatherFxLater()`, `weatherFxCancel()`, `weatherFxClearTimers()`, `weatherFxClearBolt()`, `weatherFxReduced()`, `weatherFxEffectsOff()`, `weatherFxSupported()`, `weatherFxHost()`, `weatherFxRandom()`, `weatherFxTile()`, `weatherFxReach()`, `weatherFxBuild()`, `weatherFxClearLayers()`, `weatherFxSetPlayState()`, `weatherFxStop()`, `weatherFxVisible()`, `weatherFxApply()`, `weatherFxStormy()`, `weatherFxScheduleFlash()`, `weatherFxFlash()`, `weatherFxOpenSky()`, `weatherFxBolt()`, `weatherFxThunder()`, `weatherFxForTurn()`.

### `static/js/world_browser.js` (4127 lines)

Sections: The World Browser (`:3`); with its room, station, pose, and its FULL attire ledger, (`:31`); Edit controls (`:113`); The tree (`:269`); The room card (`:349`); Townspeople (2026-09-05, DESIGN_CHARTER_PLACEMENT § the map) (`:472`); `size` is the word for the floor and `extent` its measurement, so the (`:599`); The Bodies tab: every body, and the attire editor (`:1435`); The Raw JSON tab: the two editors, unchanged (`:1716`); The map editor (`:1803`); the neighbours, faintly, where the field lays them (`:2151`); the room's cells, and the overlay's tint over them (`:2197`); the boundary as a line, with each doorway a gap in it (`:2237`); windows: each a thin line in its wall, never a gap in it (`:2296`); anchors: footprint cells, the id, a height mark (`:2334`); things placed by a position and a station (`:2376`); bodies: a marked cell with a facing tick; the unstationed in a lane (`:2414`); the lint, drawn at the thing each row concerns (`:2470`); the shape: parts as rectangles, the box's sides as handles (`:2526`); blank wall segments open a doorway; empty floor places a thing (`:2583`); the drops (`:2609`); through the doorways route, so a doorway declared from the far room (`:2735`); The dialog (`:3454`).

Declared functions: `wbStatusBadge()`, `wbRoomLabel()`, `wbSelect()`, `wbText()`, `wbCoalesced()`, `wbWrite()`, `wbPatchRoomList()`, `wbAttireEntryOf()`, `wbRenderTree()`, `wbSection()`, `wbIndexRows()`, `wbCellOf()`, `wbCellText()`, `wbStationText()`, `wbPoseText()`, `wbMoveControl()`, `wbNumber()`, `wbBodyMove()`, `wbCharterUrl()`, `wbCharterStationBody()`, `wbSourceWord()`, `wbCharterWhere()`, `wbCharterRow()`, `wbPoseEditor()`, `wbLintRows()`, `wbRoomFields()`, `wbRegionLook()`, `wbExits()`, `wbNewDoorwayBarrier()`, `wbWindows()`, `wbAnchors()`, `wbOccupant()`, `wbThing()`, `wbRenderCard()`, `wbGroupGarments()`, `wbLedgerEntry()`, `wbAttireEditor()`, `wbBodyKind()`, `wbCharterDetails()`, `wbRenderBodies()`, `wbRenderRaw()`, `wbSvg()`, `wbSvgPoint()`, `wbDraggable()`, `wbUndoStack()`, `wbWallOf()`, `wbOffsetAlong()`, `wbBearingBetween()`, `wbActivatable()`, `wbBoundary()`, `wbFocusRow()`, `wbFootprintLength()`, `wbRenderRoomMap()`, `centre()`, `partBox()`, `writeParts()`, `movePart()`, `dropPart()`, `sizePart()`, `resizePart()`, `writeExtent()`, `dropHandle()`, `nudgeHandle()`, `writeAnchors()`, `dropAnchor()`, `dropDoorway()`, `dropBody()`, `dropCharter()`, `dropThing()`, `wbRenderStructureMap()`, `wbPlanEl()`, `wbPlanFill()`, `wbPlanFrame()`, `wbPlanDefs()`, `wbPlanWalls()`, `wbPlanEdge()`, `wbPlanLabel()`, `wbPlanFixture()`, `wbPlanStair()`, `wbPlanLevelName()`, `wbRenderStoreyPlan()`, `wbPurposeSwatches()`, `wbPlanLegend()`, `wbRegionLegend()`, `wbMarksLegend()`, `wbMapPane()`, `wbWallForm()`, `wbCellForm()`, `wbMapNotes()`, `wbMapLegend()`, `openWorldBrowser()`, `moveRoute()`, `renderMapBar()`, `drawGrid()`, `loadGrid()`, `showStructure()`, `showPlan()`, `refreshIndex()`, `loadCard()`, `loadRoom()`, `selectTab()`.

### `static/js/writers_room.js` (799 lines)

Sections: The Writers' Room panel (`:3`); bd-panel for this element alone. (`:20`); Named limits (`:33`); Shape: docked / floating / closed (`:183`); Loading (`:240`); Sending (`:319`); The stream (`:352`); Rendering (`:427`); Building the panel (`:675`); Boot (`:788`).

Declared functions: `roomStoryText()`, `roomCls()`, `roomStoreGet()`, `roomStoreSet()`, `roomRestorePrefs()`, `roomClampWidth()`, `roomClampOpacity()`, `roomClampGeometry()`, `roomApplyShape()`, `roomOpen()`, `roomSetMode()`, `roomKey()`, `roomScope()`, `roomFrameQuery()`, `roomLoad()`, `roomLoadEarlier()`, `roomStartWatch()`, `roomStopWatch()`, `roomSend()`, `roomStream()`, `roomEvent()`, `roomRevoke()`, `roomRenderSoon()`, `roomRender()`, `roomRenderStatus()`, `roomRenderMandates()`, `roomRenderThread()`, `roomRenderCitations()`, `roomLiveNode()`, `roomBuild()`, `roomWireDrag()`, `track()`.
