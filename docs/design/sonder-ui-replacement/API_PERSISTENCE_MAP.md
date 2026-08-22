# Current API and persistence boundary map

The storage column names server authority; it does not authorize direct client persistence.

| Method | Route | Server authority | Source |
|---|---|---|---|
| GET | `/` | settings or derived server projection | `web/app.py:555` |
| PUT | `/api/active_preset` | settings or derived server projection | `web/app.py:1843` |
| PUT | `/api/affect_habituation` | settings or derived server projection | `web/app.py:2163` |
| PUT | `/api/agent_models` | settings or derived server projection | `web/app.py:1533` |
| PUT | `/api/ambience` | settings or derived server projection | `web/app.py:1654` |
| GET | `/api/ambience/library` | settings or derived server projection | `web/app.py:6257` |
| GET | `/api/ambience/search` | settings or derived server projection | `web/app.py:6236` |
| PUT | `/api/attire_beneath` | settings or derived server projection | `web/app.py:2182` |
| GET | `/api/auto_promote` | settings or derived server projection | `web/app.py:3743` |
| PUT | `/api/auto_promote` | settings or derived server projection | `web/app.py:3756` |
| PUT | `/api/backdrops` | settings or derived server projection | `web/app.py:1644` |
| GET | `/api/bootstrap` | settings or derived server projection | `web/app.py:1427` |
| POST | `/api/characters` | reusable character records | `web/app.py:2638` |
| POST | `/api/characters/generate` | reusable character records | `web/app.py:2615` |
| POST | `/api/characters/import` | reusable character records | `web/app.py:2663` |
| DELETE | `/api/characters/{cid}` | reusable character records | `web/app.py:2789` |
| PUT | `/api/characters/{cid}` | reusable character records | `web/app.py:2779` |
| GET | `/api/characters/{cid}/export` | reusable character records | `web/app.py:2771` |
| POST | `/api/characters/{cid}/fill_appearance` | reusable character records | `web/app.py:2759` |
| POST | `/api/characters/{cid}/fill_psychology` | reusable character records | `web/app.py:2730` |
| POST | `/api/characters/{cid}/generate_greeting` | reusable character records | `web/app.py:2714` |
| POST | `/api/characters/{cid}/recover_greetings` | reusable character records | `web/app.py:2704` |
| POST | `/api/characters/{cid}/start` | reusable character records | `web/app.py:2678` |
| POST | `/api/chats` | chat/frame/world records and projections | `web/app.py:3146` |
| DELETE | `/api/chats/{cid}` | chat/frame/world records and projections | `web/app.py:3381` |
| GET | `/api/chats/{cid}` | chat/frame/world records and projections | `web/app.py:3411` |
| PUT | `/api/chats/{cid}` | chat/frame/world records and projections | `web/app.py:3244` |
| POST | `/api/chats/{cid}/abort` | chat/frame/world records and projections | `web/app.py:5130` |
| GET | `/api/chats/{cid}/ambience/oneshot/{name}` | chat/frame/world records and projections | `web/app.py:6266` |
| DELETE | `/api/chats/{cid}/ambience/pin` | chat/frame/world records and projections | `web/app.py:6314` |
| PUT | `/api/chats/{cid}/ambience/pin` | chat/frame/world records and projections | `web/app.py:6295` |
| GET | `/api/chats/{cid}/ambience/pins` | chat/frame/world records and projections | `web/app.py:6290` |
| GET | `/api/chats/{cid}/ambience/{signature}.audio` | chat/frame/world records and projections | `web/app.py:6220` |
| GET | `/api/chats/{cid}/attire` | chat/frame/world records and projections | `web/app.py:4466` |
| PUT | `/api/chats/{cid}/attire` | chat/frame/world records and projections | `web/app.py:4477` |
| GET | `/api/chats/{cid}/backdrop/{signature}.png` | chat/frame/world records and projections | `web/app.py:6060` |
| GET | `/api/chats/{cid}/background_config` | chat/frame/world records and projections | `web/app.py:4649` |
| PUT | `/api/chats/{cid}/background_config` | chat/frame/world records and projections | `web/app.py:4653` |
| POST | `/api/chats/{cid}/characters` | chat/frame/world records and projections | `web/app.py:3647` |
| DELETE | `/api/chats/{cid}/characters/{ch}` | chat/frame/world records and projections | `web/app.py:4035` |
| PUT | `/api/chats/{cid}/characters/{ch}/card` | chat/frame/world records and projections | `web/app.py:4045` |
| PUT | `/api/chats/{cid}/characters/{ch}/dialogue_color` | chat/frame/world records and projections | `web/app.py:4350` |
| GET | `/api/chats/{cid}/characters/{ch}/memories` | chat/frame/world records and projections | `web/app.py:4870` |
| POST | `/api/chats/{cid}/characters/{ch}/memories` | chat/frame/world records and projections | `web/app.py:5017` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/backfill` | chat/frame/world records and projections | `web/app.py:4987` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/consolidate` | chat/frame/world records and projections | `web/app.py:4972` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/coverage` | chat/frame/world records and projections | `web/app.py:5008` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/export` | chat/frame/world records and projections | `web/app.py:4916` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/import` | chat/frame/world records and projections | `web/app.py:4927` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/search` | chat/frame/world records and projections | `web/app.py:4891` |
| GET | `/api/chats/{cid}/characters/{ch}/memory-context` | chat/frame/world records and projections | `web/app.py:4948` |
| PUT | `/api/chats/{cid}/characters/{ch}/position` | chat/frame/world records and projections | `web/app.py:4262` |
| GET | `/api/chats/{cid}/characters/{ch}/private_history` | chat/frame/world records and projections | `web/app.py:4331` |
| PUT | `/api/chats/{cid}/characters/{ch}/private_history` | chat/frame/world records and projections | `web/app.py:4341` |
| GET | `/api/chats/{cid}/characters/{ch}/relationships` | chat/frame/world records and projections | `web/app.py:4961` |
| GET | `/api/chats/{cid}/dialogue_config` | chat/frame/world records and projections | `web/app.py:4516` |
| PUT | `/api/chats/{cid}/dialogue_config` | chat/frame/world records and projections | `web/app.py:4533` |
| GET | `/api/chats/{cid}/dramatic_irony` | chat/frame/world records and projections | `web/app.py:3701` |
| GET | `/api/chats/{cid}/fixed_points` | chat/frame/world records and projections | `web/app.py:4816` |
| POST | `/api/chats/{cid}/fixed_points` | chat/frame/world records and projections | `web/app.py:4826` |
| DELETE | `/api/chats/{cid}/fixed_points/{anchor_id}` | chat/frame/world records and projections | `web/app.py:4848` |
| GET | `/api/chats/{cid}/frames` | chat/frame/world records and projections | `web/app.py:4770` |
| POST | `/api/chats/{cid}/frames` | chat/frame/world records and projections | `web/app.py:4774` |
| GET | `/api/chats/{cid}/guest_invites` | chat/frame/world records and projections | `web/app.py:3916` |
| POST | `/api/chats/{cid}/guest_invites` | chat/frame/world records and projections | `web/app.py:3896` |
| DELETE | `/api/chats/{cid}/guest_invites/{gid}` | chat/frame/world records and projections | `web/app.py:3920` |
| GET | `/api/chats/{cid}/language` | chat/frame/world records and projections | `web/app.py:3211` |
| PUT | `/api/chats/{cid}/language` | chat/frame/world records and projections | `web/app.py:3228` |
| GET | `/api/chats/{cid}/living_world` | chat/frame/world records and projections | `web/app.py:4614` |
| PUT | `/api/chats/{cid}/living_world` | chat/frame/world records and projections | `web/app.py:4637` |
| DELETE | `/api/chats/{cid}/lorebook` | chat/frame/world records and projections | `web/app.py:3372` |
| POST | `/api/chats/{cid}/lorebook` | chat/frame/world records and projections | `web/app.py:3351` |
| GET | `/api/chats/{cid}/lorebooks` | chat/frame/world records and projections | `web/app.py:2266` |
| POST | `/api/chats/{cid}/lorebooks` | chat/frame/world records and projections | `web/app.py:3275` |
| DELETE | `/api/chats/{cid}/lorebooks/{lid}` | chat/frame/world records and projections | `web/app.py:3336` |
| PUT | `/api/chats/{cid}/lorebooks/{lid}` | chat/frame/world records and projections | `web/app.py:3300` |
| GET | `/api/chats/{cid}/paradox_policy` | chat/frame/world records and projections | `web/app.py:4801` |
| PUT | `/api/chats/{cid}/paradox_policy` | chat/frame/world records and projections | `web/app.py:4805` |
| GET | `/api/chats/{cid}/persona_private_history` | chat/frame/world records and projections | `web/app.py:4402` |
| PUT | `/api/chats/{cid}/persona_private_history` | chat/frame/world records and projections | `web/app.py:4415` |
| GET | `/api/chats/{cid}/personas` | chat/frame/world records and projections | `web/app.py:3761` |
| POST | `/api/chats/{cid}/personas` | chat/frame/world records and projections | `web/app.py:3806` |
| DELETE | `/api/chats/{cid}/personas/{pid}` | chat/frame/world records and projections | `web/app.py:3832` |
| PUT | `/api/chats/{cid}/personas/{pid}/station` | chat/frame/world records and projections | `web/app.py:3771` |
| GET | `/api/chats/{cid}/player_authority` | chat/frame/world records and projections | `web/app.py:4733` |
| PUT | `/api/chats/{cid}/player_authority` | chat/frame/world records and projections | `web/app.py:4748` |
| GET | `/api/chats/{cid}/player_view` | chat/frame/world records and projections | `web/app.py:4710` |
| GET | `/api/chats/{cid}/positions` | chat/frame/world records and projections | `web/app.py:4195` |
| GET | `/api/chats/{cid}/promises` | chat/frame/world records and projections | `web/app.py:3705` |
| GET | `/api/chats/{cid}/promotable` | chat/frame/world records and projections | `web/app.py:3697` |
| POST | `/api/chats/{cid}/promotions/confirm` | chat/frame/world records and projections | `web/app.py:3723` |
| POST | `/api/chats/{cid}/promotions/draft` | chat/frame/world records and projections | `web/app.py:3709` |
| GET | `/api/chats/{cid}/story_view` | chat/frame/world records and projections | `web/app.py:4679` |
| GET | `/api/chats/{cid}/style_guide` | chat/frame/world records and projections | `web/app.py:4499` |
| PUT | `/api/chats/{cid}/style_guide` | chat/frame/world records and projections | `web/app.py:4505` |
| GET | `/api/chats/{cid}/survival` | chat/frame/world records and projections | `web/app.py:4103` |
| PUT | `/api/chats/{cid}/survival` | chat/frame/world records and projections | `web/app.py:4108` |
| POST | `/api/chats/{cid}/turns` | chat/frame/world records and projections | `web/app.py:5070` |
| POST | `/api/chats/{cid}/turns/{idx}/player_input` | chat/frame/world records and projections | `web/app.py:3846` |
| GET | `/api/chats/{cid}/viewers` | chat/frame/world records and projections | `web/app.py:4725` |
| GET | `/api/chats/{cid}/vitals` | chat/frame/world records and projections | `web/app.py:4160` |
| GET | `/api/chats/{cid}/world` | chat/frame/world records and projections | `web/app.py:4420` |
| PUT | `/api/chats/{cid}/world` | chat/frame/world records and projections | `web/app.py:4430` |
| GET | `/api/default_prompts` | settings or derived server projection | `web/app.py:1773` |
| PUT | `/api/director_fanout_mode` | settings or derived server projection | `web/app.py:2139` |
| PUT | `/api/exemplars` | settings or derived server projection | `web/app.py:1613` |
| GET | `/api/extensions` | extension runtime/config/state/documents | `web/app.py:1860` |
| POST | `/api/extensions/install` | extension runtime/config/state/documents | `web/app.py:1882` |
| GET | `/api/extensions/ui.css` | extension runtime/config/state/documents | `web/app.py:2060` |
| GET | `/api/extensions/ui.js` | extension runtime/config/state/documents | `web/app.py:2051` |
| GET | `/api/extensions/updates` | extension runtime/config/state/documents | `web/app.py:1903` |
| DELETE | `/api/extensions/{eid}` | extension runtime/config/state/documents | `web/app.py:1924` |
| GET | `/api/extensions/{eid}/asset/{path:path}` | extension runtime/config/state/documents | `web/app.py:2115` |
| POST | `/api/extensions/{eid}/disable` | extension runtime/config/state/documents | `web/app.py:1932` |
| DELETE | `/api/extensions/{eid}/document` | extension runtime/config/state/documents | `web/app.py:2028` |
| GET | `/api/extensions/{eid}/document` | extension runtime/config/state/documents | `web/app.py:1996` |
| PUT | `/api/extensions/{eid}/document` | extension runtime/config/state/documents | `web/app.py:2008` |
| DELETE | `/api/extensions/{eid}/documents` | extension runtime/config/state/documents | `web/app.py:2038` |
| GET | `/api/extensions/{eid}/documents` | extension runtime/config/state/documents | `web/app.py:1975` |
| GET | `/api/extensions/{eid}/documents/verify` | extension runtime/config/state/documents | `web/app.py:1986` |
| POST | `/api/extensions/{eid}/enable` | extension runtime/config/state/documents | `web/app.py:1874` |
| GET | `/api/extensions/{eid}/state` | extension runtime/config/state/documents | `web/app.py:1937` |
| GET | `/api/extensions/{eid}/ui.css` | extension runtime/config/state/documents | `web/app.py:2082` |
| GET | `/api/extensions/{eid}/ui.js` | extension runtime/config/state/documents | `web/app.py:2070` |
| POST | `/api/extensions/{eid}/update` | extension runtime/config/state/documents | `web/app.py:1914` |
| POST | `/api/guest/input` | guest session/invite tables | `web/app.py:4010` |
| GET | `/api/guest/state` | guest session/invite tables | `web/app.py:3942` |
| PUT | `/api/image_model` | settings or derived server projection | `web/app.py:1591` |
| POST | `/api/join` | settings or derived server projection | `web/app.py:3926` |
| GET | `/api/language-packs` | installed language-pack projection | `web/app.py:3164` |
| GET | `/api/language-packs/{language_id}/ui` | installed language-pack projection | `web/app.py:3185` |
| DELETE | `/api/lore_entries/{eid}` | settings or derived server projection | `web/app.py:3139` |
| PUT | `/api/lore_entries/{eid}` | settings or derived server projection | `web/app.py:3067` |
| DELETE | `/api/lore_gen_jobs/{job_id}` | settings or derived server projection | `web/app.py:2422` |
| POST | `/api/lore_gen_jobs/{job_id}/resume` | settings or derived server projection | `web/app.py:2404` |
| DELETE | `/api/lorebook_links/{link_id}` | settings or derived server projection | `web/app.py:2362` |
| PUT | `/api/lorebook_links/{link_id}` | settings or derived server projection | `web/app.py:2348` |
| POST | `/api/lorebooks` | lorebook/entry/link records | `web/app.py:2895` |
| POST | `/api/lorebooks/import` | lorebook/entry/link records | `web/app.py:2458` |
| DELETE | `/api/lorebooks/{lid}` | lorebook/entry/link records | `web/app.py:2988` |
| GET | `/api/lorebooks/{lid}` | lorebook/entry/link records | `web/app.py:2876` |
| PUT | `/api/lorebooks/{lid}` | lorebook/entry/link records | `web/app.py:2918` |
| POST | `/api/lorebooks/{lid}/apply_plan` | lorebook/entry/link records | `web/app.py:2431` |
| POST | `/api/lorebooks/{lid}/entries` | lorebook/entry/link records | `web/app.py:3038` |
| GET | `/api/lorebooks/{lid}/export` | lorebook/entry/link records | `web/app.py:2994` |
| POST | `/api/lorebooks/{lid}/generate` | lorebook/entry/link records | `web/app.py:3024` |
| GET | `/api/lorebooks/{lid}/generate_job` | lorebook/entry/link records | `web/app.py:2393` |
| POST | `/api/lorebooks/{lid}/generate_plan` | lorebook/entry/link records | `web/app.py:2367` |
| GET | `/api/lorebooks/{lid}/links` | lorebook/entry/link records | `web/app.py:2321` |
| POST | `/api/lorebooks/{lid}/links` | lorebook/entry/link records | `web/app.py:2326` |
| POST | `/api/lorebooks/{lid}/move` | lorebook/entry/link records | `web/app.py:2248` |
| POST | `/api/lorebooks/{lid}/reinterpret` | lorebook/entry/link records | `web/app.py:3011` |
| POST | `/api/lorebooks/{lid}/reorder` | lorebook/entry/link records | `web/app.py:2257` |
| GET | `/api/maintenance/checkpoints` | checkpoint/maintenance operations | `web/app.py:2205` |
| POST | `/api/maintenance/checkpoints/compact` | checkpoint/maintenance operations | `web/app.py:2221` |
| PUT | `/api/max_output_tokens` | settings or derived server projection | `web/app.py:1740` |
| DELETE | `/api/memories/{mid}` | settings or derived server projection | `web/app.py:5064` |
| PUT | `/api/memories/{mid}` | settings or derived server projection | `web/app.py:5043` |
| GET | `/api/memory/embeddings` | settings or derived server projection | `web/app.py:1564` |
| POST | `/api/memory/embeddings/rebuild` | settings or derived server projection | `web/app.py:1579` |
| GET | `/api/nsfw` | settings or derived server projection | `web/app.py:2130` |
| PUT | `/api/nsfw` | settings or derived server projection | `web/app.py:2134` |
| GET | `/api/openrouter/endpoints` | settings or derived server projection | `web/app.py:1698` |
| PUT | `/api/openrouter_routing` | settings or derived server projection | `web/app.py:1684` |
| POST | `/api/personas` | reusable persona records | `web/app.py:2818` |
| POST | `/api/personas/generate` | reusable persona records | `web/app.py:2796` |
| POST | `/api/personas/import` | reusable persona records | `web/app.py:2838` |
| DELETE | `/api/personas/{pid}` | reusable persona records | `web/app.py:2870` |
| PUT | `/api/personas/{pid}` | reusable persona records | `web/app.py:2861` |
| GET | `/api/personas/{pid}/export` | reusable persona records | `web/app.py:2852` |
| POST | `/api/personas/{pid}/fill_appearance` | reusable persona records | `web/app.py:2766` |
| PUT | `/api/prompt_presets` | settings or derived server projection | `web/app.py:1784` |
| POST | `/api/prompt_presets/import` | settings or derived server projection | `web/app.py:1820` |
| DELETE | `/api/prompt_presets/{name}` | settings or derived server projection | `web/app.py:1834` |
| GET | `/api/prompt_presets/{name}/export` | settings or derived server projection | `web/app.py:1811` |
| POST | `/api/providers` | provider/model configuration | `web/app.py:2514` |
| DELETE | `/api/providers/{pid}` | provider/model configuration | `web/app.py:2593` |
| PUT | `/api/providers/{pid}` | provider/model configuration | `web/app.py:2521` |
| GET | `/api/providers/{pid}/image_models` | provider/model configuration | `web/app.py:2605` |
| GET | `/api/providers/{pid}/models` | provider/model configuration | `web/app.py:2598` |
| PUT | `/api/providers/{pid}/prompt_cache` | provider/model configuration | `web/app.py:2548` |
| PUT | `/api/reasoning_effort` | settings or derived server projection | `web/app.py:1710` |
| POST | `/api/steps/{sid}/activate` | settings or derived server projection | `web/app.py:5867` |
| POST | `/api/steps/{sid}/edit` | settings or derived server projection | `web/app.py:5857` |
| POST | `/api/steps/{sid}/reroll` | settings or derived server projection | `web/app.py:5810` |
| DELETE | `/api/turns/{tid}` | turn/step/narration records | `web/app.py:5880` |
| GET | `/api/turns/{tid}/ambience` | turn/step/narration records | `web/app.py:6170` |
| POST | `/api/turns/{tid}/ambience` | turn/step/narration records | `web/app.py:6187` |
| GET | `/api/turns/{tid}/backdrop` | turn/step/narration records | `web/app.py:6017` |
| POST | `/api/turns/{tid}/backdrop` | turn/step/narration records | `web/app.py:6032` |
| POST | `/api/turns/{tid}/branch` | turn/step/narration records | `web/app.py:5134` |
| PUT | `/api/turns/{tid}/input` | turn/step/narration records | `web/app.py:5542` |
| GET | `/api/turns/{tid}/narration` | turn/step/narration records | `web/app.py:5627` |
| POST | `/api/turns/{tid}/narration` | turn/step/narration records | `web/app.py:5648` |
| GET | `/api/turns/{tid}/pipeline` | turn/step/narration records | `web/app.py:5672` |
| PUT | `/api/turns/{tid}/prose` | turn/step/narration records | `web/app.py:5557` |
| POST | `/api/turns/{tid}/reroll` | turn/step/narration records | `web/app.py:5741` |
| POST | `/api/turns/{tid}/rerun` | turn/step/narration records | `web/app.py:5751` |
| POST | `/api/turns/{tid}/resume` | turn/step/narration records | `web/app.py:5778` |
| GET | `/api/ui` | UI language-pack projection | `web/app.py:3175` |
| PUT | `/api/ui-language` | UI language-pack projection | `web/app.py:3200` |
| GET | `/api/updates/check` | settings or derived server projection | `web/app.py:2197` |
| POST | `/api/updates/install` | settings or derived server projection | `web/app.py:2201` |
| GET | `/guest` | settings or derived server projection | `web/app.py:547` |
| GET | `/login` | settings or derived server projection | `web/app.py:589` |
| POST | `/login` | settings or derived server projection | `web/auth_routes.py:208` |
| POST | `/logout` | settings or derived server projection | `web/auth_routes.py:274` |
| POST | `/setup` | settings or derived server projection | `web/auth_routes.py:133` |
| GET | `/status` | settings or derived server projection | `web/auth_routes.py:123` |
| GET | `/ui-next` | settings or derived server projection | `web/app.py:560` |
| GET | `/ui-next/lab` | settings or derived server projection | `web/app.py:574` |
| GET | `/ui-next/runtime` | settings or derived server projection | `web/app.py:582` |
