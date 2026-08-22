# Current API and persistence boundary map

The storage column names server authority; it does not authorize direct client persistence.

| Method | Route | Server authority | Source |
|---|---|---|---|
| GET | `/` | settings or derived server projection | `web/app.py:556` |
| PUT | `/api/active_preset` | settings or derived server projection | `web/app.py:1845` |
| PUT | `/api/affect_habituation` | settings or derived server projection | `web/app.py:2165` |
| PUT | `/api/agent_models` | settings or derived server projection | `web/app.py:1535` |
| PUT | `/api/ambience` | settings or derived server projection | `web/app.py:1656` |
| GET | `/api/ambience/library` | settings or derived server projection | `web/app.py:6267` |
| GET | `/api/ambience/search` | settings or derived server projection | `web/app.py:6246` |
| PUT | `/api/attire_beneath` | settings or derived server projection | `web/app.py:2184` |
| GET | `/api/auto_promote` | settings or derived server projection | `web/app.py:3749` |
| PUT | `/api/auto_promote` | settings or derived server projection | `web/app.py:3762` |
| PUT | `/api/backdrops` | settings or derived server projection | `web/app.py:1646` |
| GET | `/api/bootstrap` | settings or derived server projection | `web/app.py:1429` |
| POST | `/api/characters` | reusable character records | `web/app.py:2640` |
| POST | `/api/characters/generate` | reusable character records | `web/app.py:2617` |
| POST | `/api/characters/import` | reusable character records | `web/app.py:2665` |
| DELETE | `/api/characters/{cid}` | reusable character records | `web/app.py:2791` |
| PUT | `/api/characters/{cid}` | reusable character records | `web/app.py:2781` |
| GET | `/api/characters/{cid}/export` | reusable character records | `web/app.py:2773` |
| POST | `/api/characters/{cid}/fill_appearance` | reusable character records | `web/app.py:2761` |
| POST | `/api/characters/{cid}/fill_psychology` | reusable character records | `web/app.py:2732` |
| POST | `/api/characters/{cid}/generate_greeting` | reusable character records | `web/app.py:2716` |
| POST | `/api/characters/{cid}/recover_greetings` | reusable character records | `web/app.py:2706` |
| POST | `/api/characters/{cid}/start` | reusable character records | `web/app.py:2680` |
| POST | `/api/chats` | chat/frame/world records and projections | `web/app.py:3150` |
| DELETE | `/api/chats/{cid}` | chat/frame/world records and projections | `web/app.py:3385` |
| GET | `/api/chats/{cid}` | chat/frame/world records and projections | `web/app.py:3416` |
| PUT | `/api/chats/{cid}` | chat/frame/world records and projections | `web/app.py:3248` |
| POST | `/api/chats/{cid}/abort` | chat/frame/world records and projections | `web/app.py:5140` |
| GET | `/api/chats/{cid}/ambience/oneshot/{name}` | chat/frame/world records and projections | `web/app.py:6276` |
| DELETE | `/api/chats/{cid}/ambience/pin` | chat/frame/world records and projections | `web/app.py:6324` |
| PUT | `/api/chats/{cid}/ambience/pin` | chat/frame/world records and projections | `web/app.py:6305` |
| GET | `/api/chats/{cid}/ambience/pins` | chat/frame/world records and projections | `web/app.py:6300` |
| GET | `/api/chats/{cid}/ambience/{signature}.audio` | chat/frame/world records and projections | `web/app.py:6230` |
| GET | `/api/chats/{cid}/attire` | chat/frame/world records and projections | `web/app.py:4475` |
| PUT | `/api/chats/{cid}/attire` | chat/frame/world records and projections | `web/app.py:4486` |
| GET | `/api/chats/{cid}/backdrop/{signature}.png` | chat/frame/world records and projections | `web/app.py:6070` |
| GET | `/api/chats/{cid}/background_config` | chat/frame/world records and projections | `web/app.py:4658` |
| PUT | `/api/chats/{cid}/background_config` | chat/frame/world records and projections | `web/app.py:4662` |
| POST | `/api/chats/{cid}/characters` | chat/frame/world records and projections | `web/app.py:3652` |
| DELETE | `/api/chats/{cid}/characters/{ch}` | chat/frame/world records and projections | `web/app.py:4043` |
| PUT | `/api/chats/{cid}/characters/{ch}/card` | chat/frame/world records and projections | `web/app.py:4054` |
| PUT | `/api/chats/{cid}/characters/{ch}/dialogue_color` | chat/frame/world records and projections | `web/app.py:4359` |
| GET | `/api/chats/{cid}/characters/{ch}/memories` | chat/frame/world records and projections | `web/app.py:4880` |
| POST | `/api/chats/{cid}/characters/{ch}/memories` | chat/frame/world records and projections | `web/app.py:5027` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/backfill` | chat/frame/world records and projections | `web/app.py:4997` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/consolidate` | chat/frame/world records and projections | `web/app.py:4982` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/coverage` | chat/frame/world records and projections | `web/app.py:5018` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/export` | chat/frame/world records and projections | `web/app.py:4926` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/import` | chat/frame/world records and projections | `web/app.py:4937` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/search` | chat/frame/world records and projections | `web/app.py:4901` |
| GET | `/api/chats/{cid}/characters/{ch}/memory-context` | chat/frame/world records and projections | `web/app.py:4958` |
| PUT | `/api/chats/{cid}/characters/{ch}/position` | chat/frame/world records and projections | `web/app.py:4271` |
| GET | `/api/chats/{cid}/characters/{ch}/private_history` | chat/frame/world records and projections | `web/app.py:4340` |
| PUT | `/api/chats/{cid}/characters/{ch}/private_history` | chat/frame/world records and projections | `web/app.py:4350` |
| GET | `/api/chats/{cid}/characters/{ch}/relationships` | chat/frame/world records and projections | `web/app.py:4971` |
| GET | `/api/chats/{cid}/dialogue_config` | chat/frame/world records and projections | `web/app.py:4525` |
| PUT | `/api/chats/{cid}/dialogue_config` | chat/frame/world records and projections | `web/app.py:4542` |
| GET | `/api/chats/{cid}/dramatic_irony` | chat/frame/world records and projections | `web/app.py:3707` |
| GET | `/api/chats/{cid}/fixed_points` | chat/frame/world records and projections | `web/app.py:4825` |
| POST | `/api/chats/{cid}/fixed_points` | chat/frame/world records and projections | `web/app.py:4835` |
| DELETE | `/api/chats/{cid}/fixed_points/{anchor_id}` | chat/frame/world records and projections | `web/app.py:4857` |
| GET | `/api/chats/{cid}/frames` | chat/frame/world records and projections | `web/app.py:4779` |
| POST | `/api/chats/{cid}/frames` | chat/frame/world records and projections | `web/app.py:4783` |
| GET | `/api/chats/{cid}/guest_invites` | chat/frame/world records and projections | `web/app.py:3924` |
| POST | `/api/chats/{cid}/guest_invites` | chat/frame/world records and projections | `web/app.py:3904` |
| DELETE | `/api/chats/{cid}/guest_invites/{gid}` | chat/frame/world records and projections | `web/app.py:3928` |
| GET | `/api/chats/{cid}/language` | chat/frame/world records and projections | `web/app.py:3215` |
| PUT | `/api/chats/{cid}/language` | chat/frame/world records and projections | `web/app.py:3232` |
| GET | `/api/chats/{cid}/living_world` | chat/frame/world records and projections | `web/app.py:4623` |
| PUT | `/api/chats/{cid}/living_world` | chat/frame/world records and projections | `web/app.py:4646` |
| DELETE | `/api/chats/{cid}/lorebook` | chat/frame/world records and projections | `web/app.py:3376` |
| POST | `/api/chats/{cid}/lorebook` | chat/frame/world records and projections | `web/app.py:3355` |
| GET | `/api/chats/{cid}/lorebooks` | chat/frame/world records and projections | `web/app.py:2268` |
| POST | `/api/chats/{cid}/lorebooks` | chat/frame/world records and projections | `web/app.py:3279` |
| DELETE | `/api/chats/{cid}/lorebooks/{lid}` | chat/frame/world records and projections | `web/app.py:3340` |
| PUT | `/api/chats/{cid}/lorebooks/{lid}` | chat/frame/world records and projections | `web/app.py:3304` |
| GET | `/api/chats/{cid}/paradox_policy` | chat/frame/world records and projections | `web/app.py:4810` |
| PUT | `/api/chats/{cid}/paradox_policy` | chat/frame/world records and projections | `web/app.py:4814` |
| GET | `/api/chats/{cid}/persona_private_history` | chat/frame/world records and projections | `web/app.py:4411` |
| PUT | `/api/chats/{cid}/persona_private_history` | chat/frame/world records and projections | `web/app.py:4424` |
| GET | `/api/chats/{cid}/personas` | chat/frame/world records and projections | `web/app.py:3767` |
| POST | `/api/chats/{cid}/personas` | chat/frame/world records and projections | `web/app.py:3812` |
| DELETE | `/api/chats/{cid}/personas/{pid}` | chat/frame/world records and projections | `web/app.py:3839` |
| PUT | `/api/chats/{cid}/personas/{pid}/station` | chat/frame/world records and projections | `web/app.py:3777` |
| GET | `/api/chats/{cid}/player_authority` | chat/frame/world records and projections | `web/app.py:4742` |
| PUT | `/api/chats/{cid}/player_authority` | chat/frame/world records and projections | `web/app.py:4757` |
| GET | `/api/chats/{cid}/player_view` | chat/frame/world records and projections | `web/app.py:4719` |
| GET | `/api/chats/{cid}/positions` | chat/frame/world records and projections | `web/app.py:4204` |
| GET | `/api/chats/{cid}/promises` | chat/frame/world records and projections | `web/app.py:3711` |
| GET | `/api/chats/{cid}/promotable` | chat/frame/world records and projections | `web/app.py:3703` |
| POST | `/api/chats/{cid}/promotions/confirm` | chat/frame/world records and projections | `web/app.py:3729` |
| POST | `/api/chats/{cid}/promotions/draft` | chat/frame/world records and projections | `web/app.py:3715` |
| GET | `/api/chats/{cid}/story_view` | chat/frame/world records and projections | `web/app.py:4688` |
| GET | `/api/chats/{cid}/style_guide` | chat/frame/world records and projections | `web/app.py:4508` |
| PUT | `/api/chats/{cid}/style_guide` | chat/frame/world records and projections | `web/app.py:4514` |
| GET | `/api/chats/{cid}/survival` | chat/frame/world records and projections | `web/app.py:4112` |
| PUT | `/api/chats/{cid}/survival` | chat/frame/world records and projections | `web/app.py:4117` |
| POST | `/api/chats/{cid}/turns` | chat/frame/world records and projections | `web/app.py:5080` |
| POST | `/api/chats/{cid}/turns/{idx}/player_input` | chat/frame/world records and projections | `web/app.py:3854` |
| GET | `/api/chats/{cid}/viewers` | chat/frame/world records and projections | `web/app.py:4734` |
| GET | `/api/chats/{cid}/vitals` | chat/frame/world records and projections | `web/app.py:4169` |
| GET | `/api/chats/{cid}/world` | chat/frame/world records and projections | `web/app.py:4429` |
| PUT | `/api/chats/{cid}/world` | chat/frame/world records and projections | `web/app.py:4439` |
| GET | `/api/default_prompts` | settings or derived server projection | `web/app.py:1775` |
| PUT | `/api/director_fanout_mode` | settings or derived server projection | `web/app.py:2141` |
| PUT | `/api/exemplars` | settings or derived server projection | `web/app.py:1615` |
| GET | `/api/extensions` | extension runtime/config/state/documents | `web/app.py:1862` |
| POST | `/api/extensions/install` | extension runtime/config/state/documents | `web/app.py:1884` |
| GET | `/api/extensions/ui.css` | extension runtime/config/state/documents | `web/app.py:2062` |
| GET | `/api/extensions/ui.js` | extension runtime/config/state/documents | `web/app.py:2053` |
| GET | `/api/extensions/updates` | extension runtime/config/state/documents | `web/app.py:1905` |
| DELETE | `/api/extensions/{eid}` | extension runtime/config/state/documents | `web/app.py:1926` |
| GET | `/api/extensions/{eid}/asset/{path:path}` | extension runtime/config/state/documents | `web/app.py:2117` |
| POST | `/api/extensions/{eid}/disable` | extension runtime/config/state/documents | `web/app.py:1934` |
| DELETE | `/api/extensions/{eid}/document` | extension runtime/config/state/documents | `web/app.py:2030` |
| GET | `/api/extensions/{eid}/document` | extension runtime/config/state/documents | `web/app.py:1998` |
| PUT | `/api/extensions/{eid}/document` | extension runtime/config/state/documents | `web/app.py:2010` |
| DELETE | `/api/extensions/{eid}/documents` | extension runtime/config/state/documents | `web/app.py:2040` |
| GET | `/api/extensions/{eid}/documents` | extension runtime/config/state/documents | `web/app.py:1977` |
| GET | `/api/extensions/{eid}/documents/verify` | extension runtime/config/state/documents | `web/app.py:1988` |
| POST | `/api/extensions/{eid}/enable` | extension runtime/config/state/documents | `web/app.py:1876` |
| GET | `/api/extensions/{eid}/state` | extension runtime/config/state/documents | `web/app.py:1939` |
| GET | `/api/extensions/{eid}/ui.css` | extension runtime/config/state/documents | `web/app.py:2084` |
| GET | `/api/extensions/{eid}/ui.js` | extension runtime/config/state/documents | `web/app.py:2072` |
| POST | `/api/extensions/{eid}/update` | extension runtime/config/state/documents | `web/app.py:1916` |
| POST | `/api/guest/input` | guest session/invite tables | `web/app.py:4018` |
| GET | `/api/guest/state` | guest session/invite tables | `web/app.py:3950` |
| PUT | `/api/image_model` | settings or derived server projection | `web/app.py:1593` |
| POST | `/api/join` | settings or derived server projection | `web/app.py:3934` |
| GET | `/api/language-packs` | installed language-pack projection | `web/app.py:3168` |
| GET | `/api/language-packs/{language_id}/ui` | installed language-pack projection | `web/app.py:3189` |
| GET | `/api/library` | Library projection and reversible lifecycle metadata | `web/library.py:285` |
| DELETE | `/api/library/{kind}/{item_id}/archive` | Library projection and reversible lifecycle metadata | `web/library.py:382` |
| PUT | `/api/library/{kind}/{item_id}/archive` | Library projection and reversible lifecycle metadata | `web/library.py:363` |
| DELETE | `/api/lore_entries/{eid}` | settings or derived server projection | `web/app.py:3143` |
| PUT | `/api/lore_entries/{eid}` | settings or derived server projection | `web/app.py:3071` |
| DELETE | `/api/lore_gen_jobs/{job_id}` | settings or derived server projection | `web/app.py:2424` |
| POST | `/api/lore_gen_jobs/{job_id}/resume` | settings or derived server projection | `web/app.py:2406` |
| DELETE | `/api/lorebook_links/{link_id}` | settings or derived server projection | `web/app.py:2364` |
| PUT | `/api/lorebook_links/{link_id}` | settings or derived server projection | `web/app.py:2350` |
| POST | `/api/lorebooks` | lorebook/entry/link records | `web/app.py:2899` |
| POST | `/api/lorebooks/import` | lorebook/entry/link records | `web/app.py:2460` |
| DELETE | `/api/lorebooks/{lid}` | lorebook/entry/link records | `web/app.py:2992` |
| GET | `/api/lorebooks/{lid}` | lorebook/entry/link records | `web/app.py:2880` |
| PUT | `/api/lorebooks/{lid}` | lorebook/entry/link records | `web/app.py:2922` |
| POST | `/api/lorebooks/{lid}/apply_plan` | lorebook/entry/link records | `web/app.py:2433` |
| POST | `/api/lorebooks/{lid}/entries` | lorebook/entry/link records | `web/app.py:3042` |
| GET | `/api/lorebooks/{lid}/export` | lorebook/entry/link records | `web/app.py:2998` |
| POST | `/api/lorebooks/{lid}/generate` | lorebook/entry/link records | `web/app.py:3028` |
| GET | `/api/lorebooks/{lid}/generate_job` | lorebook/entry/link records | `web/app.py:2395` |
| POST | `/api/lorebooks/{lid}/generate_plan` | lorebook/entry/link records | `web/app.py:2369` |
| GET | `/api/lorebooks/{lid}/links` | lorebook/entry/link records | `web/app.py:2323` |
| POST | `/api/lorebooks/{lid}/links` | lorebook/entry/link records | `web/app.py:2328` |
| POST | `/api/lorebooks/{lid}/move` | lorebook/entry/link records | `web/app.py:2250` |
| POST | `/api/lorebooks/{lid}/reinterpret` | lorebook/entry/link records | `web/app.py:3015` |
| POST | `/api/lorebooks/{lid}/reorder` | lorebook/entry/link records | `web/app.py:2259` |
| GET | `/api/maintenance/checkpoints` | checkpoint/maintenance operations | `web/app.py:2207` |
| POST | `/api/maintenance/checkpoints/compact` | checkpoint/maintenance operations | `web/app.py:2223` |
| PUT | `/api/max_output_tokens` | settings or derived server projection | `web/app.py:1742` |
| DELETE | `/api/memories/{mid}` | settings or derived server projection | `web/app.py:5074` |
| PUT | `/api/memories/{mid}` | settings or derived server projection | `web/app.py:5053` |
| GET | `/api/memory/embeddings` | settings or derived server projection | `web/app.py:1566` |
| POST | `/api/memory/embeddings/rebuild` | settings or derived server projection | `web/app.py:1581` |
| GET | `/api/nsfw` | settings or derived server projection | `web/app.py:2132` |
| PUT | `/api/nsfw` | settings or derived server projection | `web/app.py:2136` |
| GET | `/api/openrouter/endpoints` | settings or derived server projection | `web/app.py:1700` |
| PUT | `/api/openrouter_routing` | settings or derived server projection | `web/app.py:1686` |
| POST | `/api/personas` | reusable persona records | `web/app.py:2821` |
| POST | `/api/personas/generate` | reusable persona records | `web/app.py:2799` |
| POST | `/api/personas/import` | reusable persona records | `web/app.py:2841` |
| DELETE | `/api/personas/{pid}` | reusable persona records | `web/app.py:2873` |
| PUT | `/api/personas/{pid}` | reusable persona records | `web/app.py:2864` |
| GET | `/api/personas/{pid}/export` | reusable persona records | `web/app.py:2855` |
| POST | `/api/personas/{pid}/fill_appearance` | reusable persona records | `web/app.py:2768` |
| PUT | `/api/prompt_presets` | settings or derived server projection | `web/app.py:1786` |
| POST | `/api/prompt_presets/import` | settings or derived server projection | `web/app.py:1822` |
| DELETE | `/api/prompt_presets/{name}` | settings or derived server projection | `web/app.py:1836` |
| GET | `/api/prompt_presets/{name}/export` | settings or derived server projection | `web/app.py:1813` |
| POST | `/api/providers` | provider/model configuration | `web/app.py:2516` |
| DELETE | `/api/providers/{pid}` | provider/model configuration | `web/app.py:2595` |
| PUT | `/api/providers/{pid}` | provider/model configuration | `web/app.py:2523` |
| GET | `/api/providers/{pid}/image_models` | provider/model configuration | `web/app.py:2607` |
| GET | `/api/providers/{pid}/models` | provider/model configuration | `web/app.py:2600` |
| PUT | `/api/providers/{pid}/prompt_cache` | provider/model configuration | `web/app.py:2550` |
| PUT | `/api/reasoning_effort` | settings or derived server projection | `web/app.py:1712` |
| POST | `/api/steps/{sid}/activate` | settings or derived server projection | `web/app.py:5877` |
| POST | `/api/steps/{sid}/edit` | settings or derived server projection | `web/app.py:5867` |
| POST | `/api/steps/{sid}/reroll` | settings or derived server projection | `web/app.py:5820` |
| DELETE | `/api/turns/{tid}` | turn/step/narration records | `web/app.py:5890` |
| GET | `/api/turns/{tid}/ambience` | turn/step/narration records | `web/app.py:6180` |
| POST | `/api/turns/{tid}/ambience` | turn/step/narration records | `web/app.py:6197` |
| GET | `/api/turns/{tid}/backdrop` | turn/step/narration records | `web/app.py:6027` |
| POST | `/api/turns/{tid}/backdrop` | turn/step/narration records | `web/app.py:6042` |
| POST | `/api/turns/{tid}/branch` | turn/step/narration records | `web/app.py:5144` |
| PUT | `/api/turns/{tid}/input` | turn/step/narration records | `web/app.py:5552` |
| GET | `/api/turns/{tid}/narration` | turn/step/narration records | `web/app.py:5637` |
| POST | `/api/turns/{tid}/narration` | turn/step/narration records | `web/app.py:5658` |
| GET | `/api/turns/{tid}/pipeline` | turn/step/narration records | `web/app.py:5682` |
| PUT | `/api/turns/{tid}/prose` | turn/step/narration records | `web/app.py:5567` |
| POST | `/api/turns/{tid}/reroll` | turn/step/narration records | `web/app.py:5751` |
| POST | `/api/turns/{tid}/rerun` | turn/step/narration records | `web/app.py:5761` |
| POST | `/api/turns/{tid}/resume` | turn/step/narration records | `web/app.py:5788` |
| GET | `/api/ui` | UI language-pack projection | `web/app.py:3179` |
| PUT | `/api/ui-language` | UI language-pack projection | `web/app.py:3204` |
| GET | `/api/updates/check` | settings or derived server projection | `web/app.py:2199` |
| POST | `/api/updates/install` | settings or derived server projection | `web/app.py:2203` |
| GET | `/guest` | settings or derived server projection | `web/app.py:548` |
| GET | `/login` | settings or derived server projection | `web/app.py:590` |
| POST | `/login` | settings or derived server projection | `web/auth_routes.py:208` |
| POST | `/logout` | settings or derived server projection | `web/auth_routes.py:274` |
| POST | `/setup` | settings or derived server projection | `web/auth_routes.py:133` |
| GET | `/status` | settings or derived server projection | `web/auth_routes.py:123` |
| GET | `/ui-next` | settings or derived server projection | `web/app.py:561` |
| GET | `/ui-next/lab` | settings or derived server projection | `web/app.py:575` |
| GET | `/ui-next/runtime` | settings or derived server projection | `web/app.py:583` |
