# Current API and persistence boundary map

The storage column names server authority; it does not authorize direct client persistence.

| Method | Route | Server authority | Source |
|---|---|---|---|
| GET | `/` | settings or derived server projection | `web/app.py:518` |
| PUT | `/api/active_preset` | settings or derived server projection | `web/app.py:1756` |
| PUT | `/api/affect_habituation` | settings or derived server projection | `web/app.py:2076` |
| PUT | `/api/agent_models` | settings or derived server projection | `web/app.py:1446` |
| PUT | `/api/ambience` | settings or derived server projection | `web/app.py:1567` |
| GET | `/api/ambience/library` | settings or derived server projection | `web/app.py:6170` |
| GET | `/api/ambience/search` | settings or derived server projection | `web/app.py:6149` |
| PUT | `/api/attire_beneath` | settings or derived server projection | `web/app.py:2095` |
| GET | `/api/auto_promote` | settings or derived server projection | `web/app.py:3656` |
| PUT | `/api/auto_promote` | settings or derived server projection | `web/app.py:3669` |
| PUT | `/api/backdrops` | settings or derived server projection | `web/app.py:1557` |
| GET | `/api/bootstrap` | settings or derived server projection | `web/app.py:1340` |
| POST | `/api/characters` | reusable character records | `web/app.py:2551` |
| POST | `/api/characters/generate` | reusable character records | `web/app.py:2528` |
| POST | `/api/characters/import` | reusable character records | `web/app.py:2576` |
| DELETE | `/api/characters/{cid}` | reusable character records | `web/app.py:2702` |
| PUT | `/api/characters/{cid}` | reusable character records | `web/app.py:2692` |
| GET | `/api/characters/{cid}/export` | reusable character records | `web/app.py:2684` |
| POST | `/api/characters/{cid}/fill_appearance` | reusable character records | `web/app.py:2672` |
| POST | `/api/characters/{cid}/fill_psychology` | reusable character records | `web/app.py:2643` |
| POST | `/api/characters/{cid}/generate_greeting` | reusable character records | `web/app.py:2627` |
| POST | `/api/characters/{cid}/recover_greetings` | reusable character records | `web/app.py:2617` |
| POST | `/api/characters/{cid}/start` | reusable character records | `web/app.py:2591` |
| POST | `/api/chats` | chat/frame/world records and projections | `web/app.py:3059` |
| DELETE | `/api/chats/{cid}` | chat/frame/world records and projections | `web/app.py:3294` |
| GET | `/api/chats/{cid}` | chat/frame/world records and projections | `web/app.py:3324` |
| PUT | `/api/chats/{cid}` | chat/frame/world records and projections | `web/app.py:3157` |
| POST | `/api/chats/{cid}/abort` | chat/frame/world records and projections | `web/app.py:5043` |
| GET | `/api/chats/{cid}/ambience/oneshot/{name}` | chat/frame/world records and projections | `web/app.py:6179` |
| DELETE | `/api/chats/{cid}/ambience/pin` | chat/frame/world records and projections | `web/app.py:6227` |
| PUT | `/api/chats/{cid}/ambience/pin` | chat/frame/world records and projections | `web/app.py:6208` |
| GET | `/api/chats/{cid}/ambience/pins` | chat/frame/world records and projections | `web/app.py:6203` |
| GET | `/api/chats/{cid}/ambience/{signature}.audio` | chat/frame/world records and projections | `web/app.py:6133` |
| GET | `/api/chats/{cid}/attire` | chat/frame/world records and projections | `web/app.py:4379` |
| PUT | `/api/chats/{cid}/attire` | chat/frame/world records and projections | `web/app.py:4390` |
| GET | `/api/chats/{cid}/backdrop/{signature}.png` | chat/frame/world records and projections | `web/app.py:5973` |
| GET | `/api/chats/{cid}/background_config` | chat/frame/world records and projections | `web/app.py:4562` |
| PUT | `/api/chats/{cid}/background_config` | chat/frame/world records and projections | `web/app.py:4566` |
| POST | `/api/chats/{cid}/characters` | chat/frame/world records and projections | `web/app.py:3560` |
| DELETE | `/api/chats/{cid}/characters/{ch}` | chat/frame/world records and projections | `web/app.py:3948` |
| PUT | `/api/chats/{cid}/characters/{ch}/card` | chat/frame/world records and projections | `web/app.py:3958` |
| PUT | `/api/chats/{cid}/characters/{ch}/dialogue_color` | chat/frame/world records and projections | `web/app.py:4263` |
| GET | `/api/chats/{cid}/characters/{ch}/memories` | chat/frame/world records and projections | `web/app.py:4783` |
| POST | `/api/chats/{cid}/characters/{ch}/memories` | chat/frame/world records and projections | `web/app.py:4930` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/backfill` | chat/frame/world records and projections | `web/app.py:4900` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/consolidate` | chat/frame/world records and projections | `web/app.py:4885` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/coverage` | chat/frame/world records and projections | `web/app.py:4921` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/export` | chat/frame/world records and projections | `web/app.py:4829` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/import` | chat/frame/world records and projections | `web/app.py:4840` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/search` | chat/frame/world records and projections | `web/app.py:4804` |
| GET | `/api/chats/{cid}/characters/{ch}/memory-context` | chat/frame/world records and projections | `web/app.py:4861` |
| PUT | `/api/chats/{cid}/characters/{ch}/position` | chat/frame/world records and projections | `web/app.py:4175` |
| GET | `/api/chats/{cid}/characters/{ch}/private_history` | chat/frame/world records and projections | `web/app.py:4244` |
| PUT | `/api/chats/{cid}/characters/{ch}/private_history` | chat/frame/world records and projections | `web/app.py:4254` |
| GET | `/api/chats/{cid}/characters/{ch}/relationships` | chat/frame/world records and projections | `web/app.py:4874` |
| GET | `/api/chats/{cid}/dialogue_config` | chat/frame/world records and projections | `web/app.py:4429` |
| PUT | `/api/chats/{cid}/dialogue_config` | chat/frame/world records and projections | `web/app.py:4446` |
| GET | `/api/chats/{cid}/dramatic_irony` | chat/frame/world records and projections | `web/app.py:3614` |
| GET | `/api/chats/{cid}/fixed_points` | chat/frame/world records and projections | `web/app.py:4729` |
| POST | `/api/chats/{cid}/fixed_points` | chat/frame/world records and projections | `web/app.py:4739` |
| DELETE | `/api/chats/{cid}/fixed_points/{anchor_id}` | chat/frame/world records and projections | `web/app.py:4761` |
| GET | `/api/chats/{cid}/frames` | chat/frame/world records and projections | `web/app.py:4683` |
| POST | `/api/chats/{cid}/frames` | chat/frame/world records and projections | `web/app.py:4687` |
| GET | `/api/chats/{cid}/guest_invites` | chat/frame/world records and projections | `web/app.py:3829` |
| POST | `/api/chats/{cid}/guest_invites` | chat/frame/world records and projections | `web/app.py:3809` |
| DELETE | `/api/chats/{cid}/guest_invites/{gid}` | chat/frame/world records and projections | `web/app.py:3833` |
| GET | `/api/chats/{cid}/language` | chat/frame/world records and projections | `web/app.py:3124` |
| PUT | `/api/chats/{cid}/language` | chat/frame/world records and projections | `web/app.py:3141` |
| GET | `/api/chats/{cid}/living_world` | chat/frame/world records and projections | `web/app.py:4527` |
| PUT | `/api/chats/{cid}/living_world` | chat/frame/world records and projections | `web/app.py:4550` |
| DELETE | `/api/chats/{cid}/lorebook` | chat/frame/world records and projections | `web/app.py:3285` |
| POST | `/api/chats/{cid}/lorebook` | chat/frame/world records and projections | `web/app.py:3264` |
| GET | `/api/chats/{cid}/lorebooks` | chat/frame/world records and projections | `web/app.py:2179` |
| POST | `/api/chats/{cid}/lorebooks` | chat/frame/world records and projections | `web/app.py:3188` |
| DELETE | `/api/chats/{cid}/lorebooks/{lid}` | chat/frame/world records and projections | `web/app.py:3249` |
| PUT | `/api/chats/{cid}/lorebooks/{lid}` | chat/frame/world records and projections | `web/app.py:3213` |
| GET | `/api/chats/{cid}/paradox_policy` | chat/frame/world records and projections | `web/app.py:4714` |
| PUT | `/api/chats/{cid}/paradox_policy` | chat/frame/world records and projections | `web/app.py:4718` |
| GET | `/api/chats/{cid}/persona_private_history` | chat/frame/world records and projections | `web/app.py:4315` |
| PUT | `/api/chats/{cid}/persona_private_history` | chat/frame/world records and projections | `web/app.py:4328` |
| GET | `/api/chats/{cid}/personas` | chat/frame/world records and projections | `web/app.py:3674` |
| POST | `/api/chats/{cid}/personas` | chat/frame/world records and projections | `web/app.py:3719` |
| DELETE | `/api/chats/{cid}/personas/{pid}` | chat/frame/world records and projections | `web/app.py:3745` |
| PUT | `/api/chats/{cid}/personas/{pid}/station` | chat/frame/world records and projections | `web/app.py:3684` |
| GET | `/api/chats/{cid}/player_authority` | chat/frame/world records and projections | `web/app.py:4646` |
| PUT | `/api/chats/{cid}/player_authority` | chat/frame/world records and projections | `web/app.py:4661` |
| GET | `/api/chats/{cid}/player_view` | chat/frame/world records and projections | `web/app.py:4623` |
| GET | `/api/chats/{cid}/positions` | chat/frame/world records and projections | `web/app.py:4108` |
| GET | `/api/chats/{cid}/promises` | chat/frame/world records and projections | `web/app.py:3618` |
| GET | `/api/chats/{cid}/promotable` | chat/frame/world records and projections | `web/app.py:3610` |
| POST | `/api/chats/{cid}/promotions/confirm` | chat/frame/world records and projections | `web/app.py:3636` |
| POST | `/api/chats/{cid}/promotions/draft` | chat/frame/world records and projections | `web/app.py:3622` |
| GET | `/api/chats/{cid}/story_view` | chat/frame/world records and projections | `web/app.py:4592` |
| GET | `/api/chats/{cid}/style_guide` | chat/frame/world records and projections | `web/app.py:4412` |
| PUT | `/api/chats/{cid}/style_guide` | chat/frame/world records and projections | `web/app.py:4418` |
| GET | `/api/chats/{cid}/survival` | chat/frame/world records and projections | `web/app.py:4016` |
| PUT | `/api/chats/{cid}/survival` | chat/frame/world records and projections | `web/app.py:4021` |
| POST | `/api/chats/{cid}/turns` | chat/frame/world records and projections | `web/app.py:4983` |
| POST | `/api/chats/{cid}/turns/{idx}/player_input` | chat/frame/world records and projections | `web/app.py:3759` |
| GET | `/api/chats/{cid}/viewers` | chat/frame/world records and projections | `web/app.py:4638` |
| GET | `/api/chats/{cid}/vitals` | chat/frame/world records and projections | `web/app.py:4073` |
| GET | `/api/chats/{cid}/world` | chat/frame/world records and projections | `web/app.py:4333` |
| PUT | `/api/chats/{cid}/world` | chat/frame/world records and projections | `web/app.py:4343` |
| GET | `/api/default_prompts` | settings or derived server projection | `web/app.py:1686` |
| PUT | `/api/director_fanout_mode` | settings or derived server projection | `web/app.py:2052` |
| PUT | `/api/exemplars` | settings or derived server projection | `web/app.py:1526` |
| GET | `/api/extensions` | extension runtime/config/state/documents | `web/app.py:1773` |
| POST | `/api/extensions/install` | extension runtime/config/state/documents | `web/app.py:1795` |
| GET | `/api/extensions/ui.css` | extension runtime/config/state/documents | `web/app.py:1973` |
| GET | `/api/extensions/ui.js` | extension runtime/config/state/documents | `web/app.py:1964` |
| GET | `/api/extensions/updates` | extension runtime/config/state/documents | `web/app.py:1816` |
| DELETE | `/api/extensions/{eid}` | extension runtime/config/state/documents | `web/app.py:1837` |
| GET | `/api/extensions/{eid}/asset/{path:path}` | extension runtime/config/state/documents | `web/app.py:2028` |
| POST | `/api/extensions/{eid}/disable` | extension runtime/config/state/documents | `web/app.py:1845` |
| DELETE | `/api/extensions/{eid}/document` | extension runtime/config/state/documents | `web/app.py:1941` |
| GET | `/api/extensions/{eid}/document` | extension runtime/config/state/documents | `web/app.py:1909` |
| PUT | `/api/extensions/{eid}/document` | extension runtime/config/state/documents | `web/app.py:1921` |
| DELETE | `/api/extensions/{eid}/documents` | extension runtime/config/state/documents | `web/app.py:1951` |
| GET | `/api/extensions/{eid}/documents` | extension runtime/config/state/documents | `web/app.py:1888` |
| GET | `/api/extensions/{eid}/documents/verify` | extension runtime/config/state/documents | `web/app.py:1899` |
| POST | `/api/extensions/{eid}/enable` | extension runtime/config/state/documents | `web/app.py:1787` |
| GET | `/api/extensions/{eid}/state` | extension runtime/config/state/documents | `web/app.py:1850` |
| GET | `/api/extensions/{eid}/ui.css` | extension runtime/config/state/documents | `web/app.py:1995` |
| GET | `/api/extensions/{eid}/ui.js` | extension runtime/config/state/documents | `web/app.py:1983` |
| POST | `/api/extensions/{eid}/update` | extension runtime/config/state/documents | `web/app.py:1827` |
| POST | `/api/guest/input` | guest session/invite tables | `web/app.py:3923` |
| GET | `/api/guest/state` | guest session/invite tables | `web/app.py:3855` |
| PUT | `/api/image_model` | settings or derived server projection | `web/app.py:1504` |
| POST | `/api/join` | settings or derived server projection | `web/app.py:3839` |
| GET | `/api/language-packs` | installed language-pack projection | `web/app.py:3077` |
| GET | `/api/language-packs/{language_id}/ui` | installed language-pack projection | `web/app.py:3098` |
| DELETE | `/api/lore_entries/{eid}` | settings or derived server projection | `web/app.py:3052` |
| PUT | `/api/lore_entries/{eid}` | settings or derived server projection | `web/app.py:2980` |
| DELETE | `/api/lore_gen_jobs/{job_id}` | settings or derived server projection | `web/app.py:2335` |
| POST | `/api/lore_gen_jobs/{job_id}/resume` | settings or derived server projection | `web/app.py:2317` |
| DELETE | `/api/lorebook_links/{link_id}` | settings or derived server projection | `web/app.py:2275` |
| PUT | `/api/lorebook_links/{link_id}` | settings or derived server projection | `web/app.py:2261` |
| POST | `/api/lorebooks` | lorebook/entry/link records | `web/app.py:2808` |
| POST | `/api/lorebooks/import` | lorebook/entry/link records | `web/app.py:2371` |
| DELETE | `/api/lorebooks/{lid}` | lorebook/entry/link records | `web/app.py:2901` |
| GET | `/api/lorebooks/{lid}` | lorebook/entry/link records | `web/app.py:2789` |
| PUT | `/api/lorebooks/{lid}` | lorebook/entry/link records | `web/app.py:2831` |
| POST | `/api/lorebooks/{lid}/apply_plan` | lorebook/entry/link records | `web/app.py:2344` |
| POST | `/api/lorebooks/{lid}/entries` | lorebook/entry/link records | `web/app.py:2951` |
| GET | `/api/lorebooks/{lid}/export` | lorebook/entry/link records | `web/app.py:2907` |
| POST | `/api/lorebooks/{lid}/generate` | lorebook/entry/link records | `web/app.py:2937` |
| GET | `/api/lorebooks/{lid}/generate_job` | lorebook/entry/link records | `web/app.py:2306` |
| POST | `/api/lorebooks/{lid}/generate_plan` | lorebook/entry/link records | `web/app.py:2280` |
| GET | `/api/lorebooks/{lid}/links` | lorebook/entry/link records | `web/app.py:2234` |
| POST | `/api/lorebooks/{lid}/links` | lorebook/entry/link records | `web/app.py:2239` |
| POST | `/api/lorebooks/{lid}/move` | lorebook/entry/link records | `web/app.py:2161` |
| POST | `/api/lorebooks/{lid}/reinterpret` | lorebook/entry/link records | `web/app.py:2924` |
| POST | `/api/lorebooks/{lid}/reorder` | lorebook/entry/link records | `web/app.py:2170` |
| GET | `/api/maintenance/checkpoints` | checkpoint/maintenance operations | `web/app.py:2118` |
| POST | `/api/maintenance/checkpoints/compact` | checkpoint/maintenance operations | `web/app.py:2134` |
| PUT | `/api/max_output_tokens` | settings or derived server projection | `web/app.py:1653` |
| DELETE | `/api/memories/{mid}` | settings or derived server projection | `web/app.py:4977` |
| PUT | `/api/memories/{mid}` | settings or derived server projection | `web/app.py:4956` |
| GET | `/api/memory/embeddings` | settings or derived server projection | `web/app.py:1477` |
| POST | `/api/memory/embeddings/rebuild` | settings or derived server projection | `web/app.py:1492` |
| GET | `/api/nsfw` | settings or derived server projection | `web/app.py:2043` |
| PUT | `/api/nsfw` | settings or derived server projection | `web/app.py:2047` |
| GET | `/api/openrouter/endpoints` | settings or derived server projection | `web/app.py:1611` |
| PUT | `/api/openrouter_routing` | settings or derived server projection | `web/app.py:1597` |
| POST | `/api/personas` | reusable persona records | `web/app.py:2731` |
| POST | `/api/personas/generate` | reusable persona records | `web/app.py:2709` |
| POST | `/api/personas/import` | reusable persona records | `web/app.py:2751` |
| DELETE | `/api/personas/{pid}` | reusable persona records | `web/app.py:2783` |
| PUT | `/api/personas/{pid}` | reusable persona records | `web/app.py:2774` |
| GET | `/api/personas/{pid}/export` | reusable persona records | `web/app.py:2765` |
| POST | `/api/personas/{pid}/fill_appearance` | reusable persona records | `web/app.py:2679` |
| PUT | `/api/prompt_presets` | settings or derived server projection | `web/app.py:1697` |
| POST | `/api/prompt_presets/import` | settings or derived server projection | `web/app.py:1733` |
| DELETE | `/api/prompt_presets/{name}` | settings or derived server projection | `web/app.py:1747` |
| GET | `/api/prompt_presets/{name}/export` | settings or derived server projection | `web/app.py:1724` |
| POST | `/api/providers` | provider/model configuration | `web/app.py:2427` |
| DELETE | `/api/providers/{pid}` | provider/model configuration | `web/app.py:2506` |
| PUT | `/api/providers/{pid}` | provider/model configuration | `web/app.py:2434` |
| GET | `/api/providers/{pid}/image_models` | provider/model configuration | `web/app.py:2518` |
| GET | `/api/providers/{pid}/models` | provider/model configuration | `web/app.py:2511` |
| PUT | `/api/providers/{pid}/prompt_cache` | provider/model configuration | `web/app.py:2461` |
| PUT | `/api/reasoning_effort` | settings or derived server projection | `web/app.py:1623` |
| POST | `/api/steps/{sid}/activate` | settings or derived server projection | `web/app.py:5780` |
| POST | `/api/steps/{sid}/edit` | settings or derived server projection | `web/app.py:5770` |
| POST | `/api/steps/{sid}/reroll` | settings or derived server projection | `web/app.py:5723` |
| DELETE | `/api/turns/{tid}` | turn/step/narration records | `web/app.py:5793` |
| GET | `/api/turns/{tid}/ambience` | turn/step/narration records | `web/app.py:6083` |
| POST | `/api/turns/{tid}/ambience` | turn/step/narration records | `web/app.py:6100` |
| GET | `/api/turns/{tid}/backdrop` | turn/step/narration records | `web/app.py:5930` |
| POST | `/api/turns/{tid}/backdrop` | turn/step/narration records | `web/app.py:5945` |
| POST | `/api/turns/{tid}/branch` | turn/step/narration records | `web/app.py:5047` |
| PUT | `/api/turns/{tid}/input` | turn/step/narration records | `web/app.py:5455` |
| GET | `/api/turns/{tid}/narration` | turn/step/narration records | `web/app.py:5540` |
| POST | `/api/turns/{tid}/narration` | turn/step/narration records | `web/app.py:5561` |
| GET | `/api/turns/{tid}/pipeline` | turn/step/narration records | `web/app.py:5585` |
| PUT | `/api/turns/{tid}/prose` | turn/step/narration records | `web/app.py:5470` |
| POST | `/api/turns/{tid}/reroll` | turn/step/narration records | `web/app.py:5654` |
| POST | `/api/turns/{tid}/rerun` | turn/step/narration records | `web/app.py:5664` |
| POST | `/api/turns/{tid}/resume` | turn/step/narration records | `web/app.py:5691` |
| GET | `/api/ui` | UI language-pack projection | `web/app.py:3088` |
| PUT | `/api/ui-language` | UI language-pack projection | `web/app.py:3113` |
| GET | `/api/updates/check` | settings or derived server projection | `web/app.py:2110` |
| POST | `/api/updates/install` | settings or derived server projection | `web/app.py:2114` |
| GET | `/guest` | settings or derived server projection | `web/app.py:510` |
| GET | `/login` | settings or derived server projection | `web/app.py:536` |
| POST | `/login` | settings or derived server projection | `web/auth_routes.py:208` |
| POST | `/logout` | settings or derived server projection | `web/auth_routes.py:274` |
| POST | `/setup` | settings or derived server projection | `web/auth_routes.py:133` |
| GET | `/status` | settings or derived server projection | `web/auth_routes.py:123` |
| GET | `/ui-next` | settings or derived server projection | `web/app.py:523` |
