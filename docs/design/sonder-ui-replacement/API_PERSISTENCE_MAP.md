# Current API and persistence boundary map

The storage column names server authority; it does not authorize direct client persistence.

| Method | Route | Server authority | Source |
|---|---|---|---|
| GET | `/` | settings or derived server projection | `web/app.py:518` |
| PUT | `/api/active_preset` | settings or derived server projection | `web/app.py:1742` |
| PUT | `/api/affect_habituation` | settings or derived server projection | `web/app.py:2062` |
| PUT | `/api/agent_models` | settings or derived server projection | `web/app.py:1432` |
| PUT | `/api/ambience` | settings or derived server projection | `web/app.py:1553` |
| GET | `/api/ambience/library` | settings or derived server projection | `web/app.py:6156` |
| GET | `/api/ambience/search` | settings or derived server projection | `web/app.py:6135` |
| PUT | `/api/attire_beneath` | settings or derived server projection | `web/app.py:2081` |
| GET | `/api/auto_promote` | settings or derived server projection | `web/app.py:3642` |
| PUT | `/api/auto_promote` | settings or derived server projection | `web/app.py:3655` |
| PUT | `/api/backdrops` | settings or derived server projection | `web/app.py:1543` |
| GET | `/api/bootstrap` | settings or derived server projection | `web/app.py:1326` |
| POST | `/api/characters` | reusable character records | `web/app.py:2537` |
| POST | `/api/characters/generate` | reusable character records | `web/app.py:2514` |
| POST | `/api/characters/import` | reusable character records | `web/app.py:2562` |
| DELETE | `/api/characters/{cid}` | reusable character records | `web/app.py:2688` |
| PUT | `/api/characters/{cid}` | reusable character records | `web/app.py:2678` |
| GET | `/api/characters/{cid}/export` | reusable character records | `web/app.py:2670` |
| POST | `/api/characters/{cid}/fill_appearance` | reusable character records | `web/app.py:2658` |
| POST | `/api/characters/{cid}/fill_psychology` | reusable character records | `web/app.py:2629` |
| POST | `/api/characters/{cid}/generate_greeting` | reusable character records | `web/app.py:2613` |
| POST | `/api/characters/{cid}/recover_greetings` | reusable character records | `web/app.py:2603` |
| POST | `/api/characters/{cid}/start` | reusable character records | `web/app.py:2577` |
| POST | `/api/chats` | chat/frame/world records and projections | `web/app.py:3045` |
| DELETE | `/api/chats/{cid}` | chat/frame/world records and projections | `web/app.py:3280` |
| GET | `/api/chats/{cid}` | chat/frame/world records and projections | `web/app.py:3310` |
| PUT | `/api/chats/{cid}` | chat/frame/world records and projections | `web/app.py:3143` |
| POST | `/api/chats/{cid}/abort` | chat/frame/world records and projections | `web/app.py:5029` |
| GET | `/api/chats/{cid}/ambience/oneshot/{name}` | chat/frame/world records and projections | `web/app.py:6165` |
| DELETE | `/api/chats/{cid}/ambience/pin` | chat/frame/world records and projections | `web/app.py:6213` |
| PUT | `/api/chats/{cid}/ambience/pin` | chat/frame/world records and projections | `web/app.py:6194` |
| GET | `/api/chats/{cid}/ambience/pins` | chat/frame/world records and projections | `web/app.py:6189` |
| GET | `/api/chats/{cid}/ambience/{signature}.audio` | chat/frame/world records and projections | `web/app.py:6119` |
| GET | `/api/chats/{cid}/attire` | chat/frame/world records and projections | `web/app.py:4365` |
| PUT | `/api/chats/{cid}/attire` | chat/frame/world records and projections | `web/app.py:4376` |
| GET | `/api/chats/{cid}/backdrop/{signature}.png` | chat/frame/world records and projections | `web/app.py:5959` |
| GET | `/api/chats/{cid}/background_config` | chat/frame/world records and projections | `web/app.py:4548` |
| PUT | `/api/chats/{cid}/background_config` | chat/frame/world records and projections | `web/app.py:4552` |
| POST | `/api/chats/{cid}/characters` | chat/frame/world records and projections | `web/app.py:3546` |
| DELETE | `/api/chats/{cid}/characters/{ch}` | chat/frame/world records and projections | `web/app.py:3934` |
| PUT | `/api/chats/{cid}/characters/{ch}/card` | chat/frame/world records and projections | `web/app.py:3944` |
| PUT | `/api/chats/{cid}/characters/{ch}/dialogue_color` | chat/frame/world records and projections | `web/app.py:4249` |
| GET | `/api/chats/{cid}/characters/{ch}/memories` | chat/frame/world records and projections | `web/app.py:4769` |
| POST | `/api/chats/{cid}/characters/{ch}/memories` | chat/frame/world records and projections | `web/app.py:4916` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/backfill` | chat/frame/world records and projections | `web/app.py:4886` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/consolidate` | chat/frame/world records and projections | `web/app.py:4871` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/coverage` | chat/frame/world records and projections | `web/app.py:4907` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/export` | chat/frame/world records and projections | `web/app.py:4815` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/import` | chat/frame/world records and projections | `web/app.py:4826` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/search` | chat/frame/world records and projections | `web/app.py:4790` |
| GET | `/api/chats/{cid}/characters/{ch}/memory-context` | chat/frame/world records and projections | `web/app.py:4847` |
| PUT | `/api/chats/{cid}/characters/{ch}/position` | chat/frame/world records and projections | `web/app.py:4161` |
| GET | `/api/chats/{cid}/characters/{ch}/private_history` | chat/frame/world records and projections | `web/app.py:4230` |
| PUT | `/api/chats/{cid}/characters/{ch}/private_history` | chat/frame/world records and projections | `web/app.py:4240` |
| GET | `/api/chats/{cid}/characters/{ch}/relationships` | chat/frame/world records and projections | `web/app.py:4860` |
| GET | `/api/chats/{cid}/dialogue_config` | chat/frame/world records and projections | `web/app.py:4415` |
| PUT | `/api/chats/{cid}/dialogue_config` | chat/frame/world records and projections | `web/app.py:4432` |
| GET | `/api/chats/{cid}/dramatic_irony` | chat/frame/world records and projections | `web/app.py:3600` |
| GET | `/api/chats/{cid}/fixed_points` | chat/frame/world records and projections | `web/app.py:4715` |
| POST | `/api/chats/{cid}/fixed_points` | chat/frame/world records and projections | `web/app.py:4725` |
| DELETE | `/api/chats/{cid}/fixed_points/{anchor_id}` | chat/frame/world records and projections | `web/app.py:4747` |
| GET | `/api/chats/{cid}/frames` | chat/frame/world records and projections | `web/app.py:4669` |
| POST | `/api/chats/{cid}/frames` | chat/frame/world records and projections | `web/app.py:4673` |
| GET | `/api/chats/{cid}/guest_invites` | chat/frame/world records and projections | `web/app.py:3815` |
| POST | `/api/chats/{cid}/guest_invites` | chat/frame/world records and projections | `web/app.py:3795` |
| DELETE | `/api/chats/{cid}/guest_invites/{gid}` | chat/frame/world records and projections | `web/app.py:3819` |
| GET | `/api/chats/{cid}/language` | chat/frame/world records and projections | `web/app.py:3110` |
| PUT | `/api/chats/{cid}/language` | chat/frame/world records and projections | `web/app.py:3127` |
| GET | `/api/chats/{cid}/living_world` | chat/frame/world records and projections | `web/app.py:4513` |
| PUT | `/api/chats/{cid}/living_world` | chat/frame/world records and projections | `web/app.py:4536` |
| DELETE | `/api/chats/{cid}/lorebook` | chat/frame/world records and projections | `web/app.py:3271` |
| POST | `/api/chats/{cid}/lorebook` | chat/frame/world records and projections | `web/app.py:3250` |
| GET | `/api/chats/{cid}/lorebooks` | chat/frame/world records and projections | `web/app.py:2165` |
| POST | `/api/chats/{cid}/lorebooks` | chat/frame/world records and projections | `web/app.py:3174` |
| DELETE | `/api/chats/{cid}/lorebooks/{lid}` | chat/frame/world records and projections | `web/app.py:3235` |
| PUT | `/api/chats/{cid}/lorebooks/{lid}` | chat/frame/world records and projections | `web/app.py:3199` |
| GET | `/api/chats/{cid}/paradox_policy` | chat/frame/world records and projections | `web/app.py:4700` |
| PUT | `/api/chats/{cid}/paradox_policy` | chat/frame/world records and projections | `web/app.py:4704` |
| GET | `/api/chats/{cid}/persona_private_history` | chat/frame/world records and projections | `web/app.py:4301` |
| PUT | `/api/chats/{cid}/persona_private_history` | chat/frame/world records and projections | `web/app.py:4314` |
| GET | `/api/chats/{cid}/personas` | chat/frame/world records and projections | `web/app.py:3660` |
| POST | `/api/chats/{cid}/personas` | chat/frame/world records and projections | `web/app.py:3705` |
| DELETE | `/api/chats/{cid}/personas/{pid}` | chat/frame/world records and projections | `web/app.py:3731` |
| PUT | `/api/chats/{cid}/personas/{pid}/station` | chat/frame/world records and projections | `web/app.py:3670` |
| GET | `/api/chats/{cid}/player_authority` | chat/frame/world records and projections | `web/app.py:4632` |
| PUT | `/api/chats/{cid}/player_authority` | chat/frame/world records and projections | `web/app.py:4647` |
| GET | `/api/chats/{cid}/player_view` | chat/frame/world records and projections | `web/app.py:4609` |
| GET | `/api/chats/{cid}/positions` | chat/frame/world records and projections | `web/app.py:4094` |
| GET | `/api/chats/{cid}/promises` | chat/frame/world records and projections | `web/app.py:3604` |
| GET | `/api/chats/{cid}/promotable` | chat/frame/world records and projections | `web/app.py:3596` |
| POST | `/api/chats/{cid}/promotions/confirm` | chat/frame/world records and projections | `web/app.py:3622` |
| POST | `/api/chats/{cid}/promotions/draft` | chat/frame/world records and projections | `web/app.py:3608` |
| GET | `/api/chats/{cid}/story_view` | chat/frame/world records and projections | `web/app.py:4578` |
| GET | `/api/chats/{cid}/style_guide` | chat/frame/world records and projections | `web/app.py:4398` |
| PUT | `/api/chats/{cid}/style_guide` | chat/frame/world records and projections | `web/app.py:4404` |
| GET | `/api/chats/{cid}/survival` | chat/frame/world records and projections | `web/app.py:4002` |
| PUT | `/api/chats/{cid}/survival` | chat/frame/world records and projections | `web/app.py:4007` |
| POST | `/api/chats/{cid}/turns` | chat/frame/world records and projections | `web/app.py:4969` |
| POST | `/api/chats/{cid}/turns/{idx}/player_input` | chat/frame/world records and projections | `web/app.py:3745` |
| GET | `/api/chats/{cid}/viewers` | chat/frame/world records and projections | `web/app.py:4624` |
| GET | `/api/chats/{cid}/vitals` | chat/frame/world records and projections | `web/app.py:4059` |
| GET | `/api/chats/{cid}/world` | chat/frame/world records and projections | `web/app.py:4319` |
| PUT | `/api/chats/{cid}/world` | chat/frame/world records and projections | `web/app.py:4329` |
| GET | `/api/default_prompts` | settings or derived server projection | `web/app.py:1672` |
| PUT | `/api/director_fanout_mode` | settings or derived server projection | `web/app.py:2038` |
| PUT | `/api/exemplars` | settings or derived server projection | `web/app.py:1512` |
| GET | `/api/extensions` | extension runtime/config/state/documents | `web/app.py:1759` |
| POST | `/api/extensions/install` | extension runtime/config/state/documents | `web/app.py:1781` |
| GET | `/api/extensions/ui.css` | extension runtime/config/state/documents | `web/app.py:1959` |
| GET | `/api/extensions/ui.js` | extension runtime/config/state/documents | `web/app.py:1950` |
| GET | `/api/extensions/updates` | extension runtime/config/state/documents | `web/app.py:1802` |
| DELETE | `/api/extensions/{eid}` | extension runtime/config/state/documents | `web/app.py:1823` |
| GET | `/api/extensions/{eid}/asset/{path:path}` | extension runtime/config/state/documents | `web/app.py:2014` |
| POST | `/api/extensions/{eid}/disable` | extension runtime/config/state/documents | `web/app.py:1831` |
| DELETE | `/api/extensions/{eid}/document` | extension runtime/config/state/documents | `web/app.py:1927` |
| GET | `/api/extensions/{eid}/document` | extension runtime/config/state/documents | `web/app.py:1895` |
| PUT | `/api/extensions/{eid}/document` | extension runtime/config/state/documents | `web/app.py:1907` |
| DELETE | `/api/extensions/{eid}/documents` | extension runtime/config/state/documents | `web/app.py:1937` |
| GET | `/api/extensions/{eid}/documents` | extension runtime/config/state/documents | `web/app.py:1874` |
| GET | `/api/extensions/{eid}/documents/verify` | extension runtime/config/state/documents | `web/app.py:1885` |
| POST | `/api/extensions/{eid}/enable` | extension runtime/config/state/documents | `web/app.py:1773` |
| GET | `/api/extensions/{eid}/state` | extension runtime/config/state/documents | `web/app.py:1836` |
| GET | `/api/extensions/{eid}/ui.css` | extension runtime/config/state/documents | `web/app.py:1981` |
| GET | `/api/extensions/{eid}/ui.js` | extension runtime/config/state/documents | `web/app.py:1969` |
| POST | `/api/extensions/{eid}/update` | extension runtime/config/state/documents | `web/app.py:1813` |
| POST | `/api/guest/input` | guest session/invite tables | `web/app.py:3909` |
| GET | `/api/guest/state` | guest session/invite tables | `web/app.py:3841` |
| PUT | `/api/image_model` | settings or derived server projection | `web/app.py:1490` |
| POST | `/api/join` | settings or derived server projection | `web/app.py:3825` |
| GET | `/api/language-packs` | installed language-pack projection | `web/app.py:3063` |
| GET | `/api/language-packs/{language_id}/ui` | installed language-pack projection | `web/app.py:3084` |
| DELETE | `/api/lore_entries/{eid}` | settings or derived server projection | `web/app.py:3038` |
| PUT | `/api/lore_entries/{eid}` | settings or derived server projection | `web/app.py:2966` |
| DELETE | `/api/lore_gen_jobs/{job_id}` | settings or derived server projection | `web/app.py:2321` |
| POST | `/api/lore_gen_jobs/{job_id}/resume` | settings or derived server projection | `web/app.py:2303` |
| DELETE | `/api/lorebook_links/{link_id}` | settings or derived server projection | `web/app.py:2261` |
| PUT | `/api/lorebook_links/{link_id}` | settings or derived server projection | `web/app.py:2247` |
| POST | `/api/lorebooks` | lorebook/entry/link records | `web/app.py:2794` |
| POST | `/api/lorebooks/import` | lorebook/entry/link records | `web/app.py:2357` |
| DELETE | `/api/lorebooks/{lid}` | lorebook/entry/link records | `web/app.py:2887` |
| GET | `/api/lorebooks/{lid}` | lorebook/entry/link records | `web/app.py:2775` |
| PUT | `/api/lorebooks/{lid}` | lorebook/entry/link records | `web/app.py:2817` |
| POST | `/api/lorebooks/{lid}/apply_plan` | lorebook/entry/link records | `web/app.py:2330` |
| POST | `/api/lorebooks/{lid}/entries` | lorebook/entry/link records | `web/app.py:2937` |
| GET | `/api/lorebooks/{lid}/export` | lorebook/entry/link records | `web/app.py:2893` |
| POST | `/api/lorebooks/{lid}/generate` | lorebook/entry/link records | `web/app.py:2923` |
| GET | `/api/lorebooks/{lid}/generate_job` | lorebook/entry/link records | `web/app.py:2292` |
| POST | `/api/lorebooks/{lid}/generate_plan` | lorebook/entry/link records | `web/app.py:2266` |
| GET | `/api/lorebooks/{lid}/links` | lorebook/entry/link records | `web/app.py:2220` |
| POST | `/api/lorebooks/{lid}/links` | lorebook/entry/link records | `web/app.py:2225` |
| POST | `/api/lorebooks/{lid}/move` | lorebook/entry/link records | `web/app.py:2147` |
| POST | `/api/lorebooks/{lid}/reinterpret` | lorebook/entry/link records | `web/app.py:2910` |
| POST | `/api/lorebooks/{lid}/reorder` | lorebook/entry/link records | `web/app.py:2156` |
| GET | `/api/maintenance/checkpoints` | checkpoint/maintenance operations | `web/app.py:2104` |
| POST | `/api/maintenance/checkpoints/compact` | checkpoint/maintenance operations | `web/app.py:2120` |
| PUT | `/api/max_output_tokens` | settings or derived server projection | `web/app.py:1639` |
| DELETE | `/api/memories/{mid}` | settings or derived server projection | `web/app.py:4963` |
| PUT | `/api/memories/{mid}` | settings or derived server projection | `web/app.py:4942` |
| GET | `/api/memory/embeddings` | settings or derived server projection | `web/app.py:1463` |
| POST | `/api/memory/embeddings/rebuild` | settings or derived server projection | `web/app.py:1478` |
| GET | `/api/nsfw` | settings or derived server projection | `web/app.py:2029` |
| PUT | `/api/nsfw` | settings or derived server projection | `web/app.py:2033` |
| GET | `/api/openrouter/endpoints` | settings or derived server projection | `web/app.py:1597` |
| PUT | `/api/openrouter_routing` | settings or derived server projection | `web/app.py:1583` |
| POST | `/api/personas` | reusable persona records | `web/app.py:2717` |
| POST | `/api/personas/generate` | reusable persona records | `web/app.py:2695` |
| POST | `/api/personas/import` | reusable persona records | `web/app.py:2737` |
| DELETE | `/api/personas/{pid}` | reusable persona records | `web/app.py:2769` |
| PUT | `/api/personas/{pid}` | reusable persona records | `web/app.py:2760` |
| GET | `/api/personas/{pid}/export` | reusable persona records | `web/app.py:2751` |
| POST | `/api/personas/{pid}/fill_appearance` | reusable persona records | `web/app.py:2665` |
| PUT | `/api/prompt_presets` | settings or derived server projection | `web/app.py:1683` |
| POST | `/api/prompt_presets/import` | settings or derived server projection | `web/app.py:1719` |
| DELETE | `/api/prompt_presets/{name}` | settings or derived server projection | `web/app.py:1733` |
| GET | `/api/prompt_presets/{name}/export` | settings or derived server projection | `web/app.py:1710` |
| POST | `/api/providers` | provider/model configuration | `web/app.py:2413` |
| DELETE | `/api/providers/{pid}` | provider/model configuration | `web/app.py:2492` |
| PUT | `/api/providers/{pid}` | provider/model configuration | `web/app.py:2420` |
| GET | `/api/providers/{pid}/image_models` | provider/model configuration | `web/app.py:2504` |
| GET | `/api/providers/{pid}/models` | provider/model configuration | `web/app.py:2497` |
| PUT | `/api/providers/{pid}/prompt_cache` | provider/model configuration | `web/app.py:2447` |
| PUT | `/api/reasoning_effort` | settings or derived server projection | `web/app.py:1609` |
| POST | `/api/steps/{sid}/activate` | settings or derived server projection | `web/app.py:5766` |
| POST | `/api/steps/{sid}/edit` | settings or derived server projection | `web/app.py:5756` |
| POST | `/api/steps/{sid}/reroll` | settings or derived server projection | `web/app.py:5709` |
| DELETE | `/api/turns/{tid}` | turn/step/narration records | `web/app.py:5779` |
| GET | `/api/turns/{tid}/ambience` | turn/step/narration records | `web/app.py:6069` |
| POST | `/api/turns/{tid}/ambience` | turn/step/narration records | `web/app.py:6086` |
| GET | `/api/turns/{tid}/backdrop` | turn/step/narration records | `web/app.py:5916` |
| POST | `/api/turns/{tid}/backdrop` | turn/step/narration records | `web/app.py:5931` |
| POST | `/api/turns/{tid}/branch` | turn/step/narration records | `web/app.py:5033` |
| PUT | `/api/turns/{tid}/input` | turn/step/narration records | `web/app.py:5441` |
| GET | `/api/turns/{tid}/narration` | turn/step/narration records | `web/app.py:5526` |
| POST | `/api/turns/{tid}/narration` | turn/step/narration records | `web/app.py:5547` |
| GET | `/api/turns/{tid}/pipeline` | turn/step/narration records | `web/app.py:5571` |
| PUT | `/api/turns/{tid}/prose` | turn/step/narration records | `web/app.py:5456` |
| POST | `/api/turns/{tid}/reroll` | turn/step/narration records | `web/app.py:5640` |
| POST | `/api/turns/{tid}/rerun` | turn/step/narration records | `web/app.py:5650` |
| POST | `/api/turns/{tid}/resume` | turn/step/narration records | `web/app.py:5677` |
| GET | `/api/ui` | UI language-pack projection | `web/app.py:3074` |
| PUT | `/api/ui-language` | UI language-pack projection | `web/app.py:3099` |
| GET | `/api/updates/check` | settings or derived server projection | `web/app.py:2096` |
| POST | `/api/updates/install` | settings or derived server projection | `web/app.py:2100` |
| GET | `/guest` | settings or derived server projection | `web/app.py:510` |
| GET | `/login` | settings or derived server projection | `web/app.py:522` |
| POST | `/login` | settings or derived server projection | `web/auth_routes.py:208` |
| POST | `/logout` | settings or derived server projection | `web/auth_routes.py:274` |
| POST | `/setup` | settings or derived server projection | `web/auth_routes.py:133` |
| GET | `/status` | settings or derived server projection | `web/auth_routes.py:123` |
