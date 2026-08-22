# Current API and persistence boundary map

The storage column names server authority; it does not authorize direct client persistence.

| Method | Route | Server authority | Source |
|---|---|---|---|
| GET | `/` | settings or derived server projection | `web/app.py:555` |
| PUT | `/api/active_preset` | settings or derived server projection | `web/app.py:1801` |
| PUT | `/api/affect_habituation` | settings or derived server projection | `web/app.py:2121` |
| PUT | `/api/agent_models` | settings or derived server projection | `web/app.py:1491` |
| PUT | `/api/ambience` | settings or derived server projection | `web/app.py:1612` |
| GET | `/api/ambience/library` | settings or derived server projection | `web/app.py:6215` |
| GET | `/api/ambience/search` | settings or derived server projection | `web/app.py:6194` |
| PUT | `/api/attire_beneath` | settings or derived server projection | `web/app.py:2140` |
| GET | `/api/auto_promote` | settings or derived server projection | `web/app.py:3701` |
| PUT | `/api/auto_promote` | settings or derived server projection | `web/app.py:3714` |
| PUT | `/api/backdrops` | settings or derived server projection | `web/app.py:1602` |
| GET | `/api/bootstrap` | settings or derived server projection | `web/app.py:1385` |
| POST | `/api/characters` | reusable character records | `web/app.py:2596` |
| POST | `/api/characters/generate` | reusable character records | `web/app.py:2573` |
| POST | `/api/characters/import` | reusable character records | `web/app.py:2621` |
| DELETE | `/api/characters/{cid}` | reusable character records | `web/app.py:2747` |
| PUT | `/api/characters/{cid}` | reusable character records | `web/app.py:2737` |
| GET | `/api/characters/{cid}/export` | reusable character records | `web/app.py:2729` |
| POST | `/api/characters/{cid}/fill_appearance` | reusable character records | `web/app.py:2717` |
| POST | `/api/characters/{cid}/fill_psychology` | reusable character records | `web/app.py:2688` |
| POST | `/api/characters/{cid}/generate_greeting` | reusable character records | `web/app.py:2672` |
| POST | `/api/characters/{cid}/recover_greetings` | reusable character records | `web/app.py:2662` |
| POST | `/api/characters/{cid}/start` | reusable character records | `web/app.py:2636` |
| POST | `/api/chats` | chat/frame/world records and projections | `web/app.py:3104` |
| DELETE | `/api/chats/{cid}` | chat/frame/world records and projections | `web/app.py:3339` |
| GET | `/api/chats/{cid}` | chat/frame/world records and projections | `web/app.py:3369` |
| PUT | `/api/chats/{cid}` | chat/frame/world records and projections | `web/app.py:3202` |
| POST | `/api/chats/{cid}/abort` | chat/frame/world records and projections | `web/app.py:5088` |
| GET | `/api/chats/{cid}/ambience/oneshot/{name}` | chat/frame/world records and projections | `web/app.py:6224` |
| DELETE | `/api/chats/{cid}/ambience/pin` | chat/frame/world records and projections | `web/app.py:6272` |
| PUT | `/api/chats/{cid}/ambience/pin` | chat/frame/world records and projections | `web/app.py:6253` |
| GET | `/api/chats/{cid}/ambience/pins` | chat/frame/world records and projections | `web/app.py:6248` |
| GET | `/api/chats/{cid}/ambience/{signature}.audio` | chat/frame/world records and projections | `web/app.py:6178` |
| GET | `/api/chats/{cid}/attire` | chat/frame/world records and projections | `web/app.py:4424` |
| PUT | `/api/chats/{cid}/attire` | chat/frame/world records and projections | `web/app.py:4435` |
| GET | `/api/chats/{cid}/backdrop/{signature}.png` | chat/frame/world records and projections | `web/app.py:6018` |
| GET | `/api/chats/{cid}/background_config` | chat/frame/world records and projections | `web/app.py:4607` |
| PUT | `/api/chats/{cid}/background_config` | chat/frame/world records and projections | `web/app.py:4611` |
| POST | `/api/chats/{cid}/characters` | chat/frame/world records and projections | `web/app.py:3605` |
| DELETE | `/api/chats/{cid}/characters/{ch}` | chat/frame/world records and projections | `web/app.py:3993` |
| PUT | `/api/chats/{cid}/characters/{ch}/card` | chat/frame/world records and projections | `web/app.py:4003` |
| PUT | `/api/chats/{cid}/characters/{ch}/dialogue_color` | chat/frame/world records and projections | `web/app.py:4308` |
| GET | `/api/chats/{cid}/characters/{ch}/memories` | chat/frame/world records and projections | `web/app.py:4828` |
| POST | `/api/chats/{cid}/characters/{ch}/memories` | chat/frame/world records and projections | `web/app.py:4975` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/backfill` | chat/frame/world records and projections | `web/app.py:4945` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/consolidate` | chat/frame/world records and projections | `web/app.py:4930` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/coverage` | chat/frame/world records and projections | `web/app.py:4966` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/export` | chat/frame/world records and projections | `web/app.py:4874` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/import` | chat/frame/world records and projections | `web/app.py:4885` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/search` | chat/frame/world records and projections | `web/app.py:4849` |
| GET | `/api/chats/{cid}/characters/{ch}/memory-context` | chat/frame/world records and projections | `web/app.py:4906` |
| PUT | `/api/chats/{cid}/characters/{ch}/position` | chat/frame/world records and projections | `web/app.py:4220` |
| GET | `/api/chats/{cid}/characters/{ch}/private_history` | chat/frame/world records and projections | `web/app.py:4289` |
| PUT | `/api/chats/{cid}/characters/{ch}/private_history` | chat/frame/world records and projections | `web/app.py:4299` |
| GET | `/api/chats/{cid}/characters/{ch}/relationships` | chat/frame/world records and projections | `web/app.py:4919` |
| GET | `/api/chats/{cid}/dialogue_config` | chat/frame/world records and projections | `web/app.py:4474` |
| PUT | `/api/chats/{cid}/dialogue_config` | chat/frame/world records and projections | `web/app.py:4491` |
| GET | `/api/chats/{cid}/dramatic_irony` | chat/frame/world records and projections | `web/app.py:3659` |
| GET | `/api/chats/{cid}/fixed_points` | chat/frame/world records and projections | `web/app.py:4774` |
| POST | `/api/chats/{cid}/fixed_points` | chat/frame/world records and projections | `web/app.py:4784` |
| DELETE | `/api/chats/{cid}/fixed_points/{anchor_id}` | chat/frame/world records and projections | `web/app.py:4806` |
| GET | `/api/chats/{cid}/frames` | chat/frame/world records and projections | `web/app.py:4728` |
| POST | `/api/chats/{cid}/frames` | chat/frame/world records and projections | `web/app.py:4732` |
| GET | `/api/chats/{cid}/guest_invites` | chat/frame/world records and projections | `web/app.py:3874` |
| POST | `/api/chats/{cid}/guest_invites` | chat/frame/world records and projections | `web/app.py:3854` |
| DELETE | `/api/chats/{cid}/guest_invites/{gid}` | chat/frame/world records and projections | `web/app.py:3878` |
| GET | `/api/chats/{cid}/language` | chat/frame/world records and projections | `web/app.py:3169` |
| PUT | `/api/chats/{cid}/language` | chat/frame/world records and projections | `web/app.py:3186` |
| GET | `/api/chats/{cid}/living_world` | chat/frame/world records and projections | `web/app.py:4572` |
| PUT | `/api/chats/{cid}/living_world` | chat/frame/world records and projections | `web/app.py:4595` |
| DELETE | `/api/chats/{cid}/lorebook` | chat/frame/world records and projections | `web/app.py:3330` |
| POST | `/api/chats/{cid}/lorebook` | chat/frame/world records and projections | `web/app.py:3309` |
| GET | `/api/chats/{cid}/lorebooks` | chat/frame/world records and projections | `web/app.py:2224` |
| POST | `/api/chats/{cid}/lorebooks` | chat/frame/world records and projections | `web/app.py:3233` |
| DELETE | `/api/chats/{cid}/lorebooks/{lid}` | chat/frame/world records and projections | `web/app.py:3294` |
| PUT | `/api/chats/{cid}/lorebooks/{lid}` | chat/frame/world records and projections | `web/app.py:3258` |
| GET | `/api/chats/{cid}/paradox_policy` | chat/frame/world records and projections | `web/app.py:4759` |
| PUT | `/api/chats/{cid}/paradox_policy` | chat/frame/world records and projections | `web/app.py:4763` |
| GET | `/api/chats/{cid}/persona_private_history` | chat/frame/world records and projections | `web/app.py:4360` |
| PUT | `/api/chats/{cid}/persona_private_history` | chat/frame/world records and projections | `web/app.py:4373` |
| GET | `/api/chats/{cid}/personas` | chat/frame/world records and projections | `web/app.py:3719` |
| POST | `/api/chats/{cid}/personas` | chat/frame/world records and projections | `web/app.py:3764` |
| DELETE | `/api/chats/{cid}/personas/{pid}` | chat/frame/world records and projections | `web/app.py:3790` |
| PUT | `/api/chats/{cid}/personas/{pid}/station` | chat/frame/world records and projections | `web/app.py:3729` |
| GET | `/api/chats/{cid}/player_authority` | chat/frame/world records and projections | `web/app.py:4691` |
| PUT | `/api/chats/{cid}/player_authority` | chat/frame/world records and projections | `web/app.py:4706` |
| GET | `/api/chats/{cid}/player_view` | chat/frame/world records and projections | `web/app.py:4668` |
| GET | `/api/chats/{cid}/positions` | chat/frame/world records and projections | `web/app.py:4153` |
| GET | `/api/chats/{cid}/promises` | chat/frame/world records and projections | `web/app.py:3663` |
| GET | `/api/chats/{cid}/promotable` | chat/frame/world records and projections | `web/app.py:3655` |
| POST | `/api/chats/{cid}/promotions/confirm` | chat/frame/world records and projections | `web/app.py:3681` |
| POST | `/api/chats/{cid}/promotions/draft` | chat/frame/world records and projections | `web/app.py:3667` |
| GET | `/api/chats/{cid}/story_view` | chat/frame/world records and projections | `web/app.py:4637` |
| GET | `/api/chats/{cid}/style_guide` | chat/frame/world records and projections | `web/app.py:4457` |
| PUT | `/api/chats/{cid}/style_guide` | chat/frame/world records and projections | `web/app.py:4463` |
| GET | `/api/chats/{cid}/survival` | chat/frame/world records and projections | `web/app.py:4061` |
| PUT | `/api/chats/{cid}/survival` | chat/frame/world records and projections | `web/app.py:4066` |
| POST | `/api/chats/{cid}/turns` | chat/frame/world records and projections | `web/app.py:5028` |
| POST | `/api/chats/{cid}/turns/{idx}/player_input` | chat/frame/world records and projections | `web/app.py:3804` |
| GET | `/api/chats/{cid}/viewers` | chat/frame/world records and projections | `web/app.py:4683` |
| GET | `/api/chats/{cid}/vitals` | chat/frame/world records and projections | `web/app.py:4118` |
| GET | `/api/chats/{cid}/world` | chat/frame/world records and projections | `web/app.py:4378` |
| PUT | `/api/chats/{cid}/world` | chat/frame/world records and projections | `web/app.py:4388` |
| GET | `/api/default_prompts` | settings or derived server projection | `web/app.py:1731` |
| PUT | `/api/director_fanout_mode` | settings or derived server projection | `web/app.py:2097` |
| PUT | `/api/exemplars` | settings or derived server projection | `web/app.py:1571` |
| GET | `/api/extensions` | extension runtime/config/state/documents | `web/app.py:1818` |
| POST | `/api/extensions/install` | extension runtime/config/state/documents | `web/app.py:1840` |
| GET | `/api/extensions/ui.css` | extension runtime/config/state/documents | `web/app.py:2018` |
| GET | `/api/extensions/ui.js` | extension runtime/config/state/documents | `web/app.py:2009` |
| GET | `/api/extensions/updates` | extension runtime/config/state/documents | `web/app.py:1861` |
| DELETE | `/api/extensions/{eid}` | extension runtime/config/state/documents | `web/app.py:1882` |
| GET | `/api/extensions/{eid}/asset/{path:path}` | extension runtime/config/state/documents | `web/app.py:2073` |
| POST | `/api/extensions/{eid}/disable` | extension runtime/config/state/documents | `web/app.py:1890` |
| DELETE | `/api/extensions/{eid}/document` | extension runtime/config/state/documents | `web/app.py:1986` |
| GET | `/api/extensions/{eid}/document` | extension runtime/config/state/documents | `web/app.py:1954` |
| PUT | `/api/extensions/{eid}/document` | extension runtime/config/state/documents | `web/app.py:1966` |
| DELETE | `/api/extensions/{eid}/documents` | extension runtime/config/state/documents | `web/app.py:1996` |
| GET | `/api/extensions/{eid}/documents` | extension runtime/config/state/documents | `web/app.py:1933` |
| GET | `/api/extensions/{eid}/documents/verify` | extension runtime/config/state/documents | `web/app.py:1944` |
| POST | `/api/extensions/{eid}/enable` | extension runtime/config/state/documents | `web/app.py:1832` |
| GET | `/api/extensions/{eid}/state` | extension runtime/config/state/documents | `web/app.py:1895` |
| GET | `/api/extensions/{eid}/ui.css` | extension runtime/config/state/documents | `web/app.py:2040` |
| GET | `/api/extensions/{eid}/ui.js` | extension runtime/config/state/documents | `web/app.py:2028` |
| POST | `/api/extensions/{eid}/update` | extension runtime/config/state/documents | `web/app.py:1872` |
| POST | `/api/guest/input` | guest session/invite tables | `web/app.py:3968` |
| GET | `/api/guest/state` | guest session/invite tables | `web/app.py:3900` |
| PUT | `/api/image_model` | settings or derived server projection | `web/app.py:1549` |
| POST | `/api/join` | settings or derived server projection | `web/app.py:3884` |
| GET | `/api/language-packs` | installed language-pack projection | `web/app.py:3122` |
| GET | `/api/language-packs/{language_id}/ui` | installed language-pack projection | `web/app.py:3143` |
| DELETE | `/api/lore_entries/{eid}` | settings or derived server projection | `web/app.py:3097` |
| PUT | `/api/lore_entries/{eid}` | settings or derived server projection | `web/app.py:3025` |
| DELETE | `/api/lore_gen_jobs/{job_id}` | settings or derived server projection | `web/app.py:2380` |
| POST | `/api/lore_gen_jobs/{job_id}/resume` | settings or derived server projection | `web/app.py:2362` |
| DELETE | `/api/lorebook_links/{link_id}` | settings or derived server projection | `web/app.py:2320` |
| PUT | `/api/lorebook_links/{link_id}` | settings or derived server projection | `web/app.py:2306` |
| POST | `/api/lorebooks` | lorebook/entry/link records | `web/app.py:2853` |
| POST | `/api/lorebooks/import` | lorebook/entry/link records | `web/app.py:2416` |
| DELETE | `/api/lorebooks/{lid}` | lorebook/entry/link records | `web/app.py:2946` |
| GET | `/api/lorebooks/{lid}` | lorebook/entry/link records | `web/app.py:2834` |
| PUT | `/api/lorebooks/{lid}` | lorebook/entry/link records | `web/app.py:2876` |
| POST | `/api/lorebooks/{lid}/apply_plan` | lorebook/entry/link records | `web/app.py:2389` |
| POST | `/api/lorebooks/{lid}/entries` | lorebook/entry/link records | `web/app.py:2996` |
| GET | `/api/lorebooks/{lid}/export` | lorebook/entry/link records | `web/app.py:2952` |
| POST | `/api/lorebooks/{lid}/generate` | lorebook/entry/link records | `web/app.py:2982` |
| GET | `/api/lorebooks/{lid}/generate_job` | lorebook/entry/link records | `web/app.py:2351` |
| POST | `/api/lorebooks/{lid}/generate_plan` | lorebook/entry/link records | `web/app.py:2325` |
| GET | `/api/lorebooks/{lid}/links` | lorebook/entry/link records | `web/app.py:2279` |
| POST | `/api/lorebooks/{lid}/links` | lorebook/entry/link records | `web/app.py:2284` |
| POST | `/api/lorebooks/{lid}/move` | lorebook/entry/link records | `web/app.py:2206` |
| POST | `/api/lorebooks/{lid}/reinterpret` | lorebook/entry/link records | `web/app.py:2969` |
| POST | `/api/lorebooks/{lid}/reorder` | lorebook/entry/link records | `web/app.py:2215` |
| GET | `/api/maintenance/checkpoints` | checkpoint/maintenance operations | `web/app.py:2163` |
| POST | `/api/maintenance/checkpoints/compact` | checkpoint/maintenance operations | `web/app.py:2179` |
| PUT | `/api/max_output_tokens` | settings or derived server projection | `web/app.py:1698` |
| DELETE | `/api/memories/{mid}` | settings or derived server projection | `web/app.py:5022` |
| PUT | `/api/memories/{mid}` | settings or derived server projection | `web/app.py:5001` |
| GET | `/api/memory/embeddings` | settings or derived server projection | `web/app.py:1522` |
| POST | `/api/memory/embeddings/rebuild` | settings or derived server projection | `web/app.py:1537` |
| GET | `/api/nsfw` | settings or derived server projection | `web/app.py:2088` |
| PUT | `/api/nsfw` | settings or derived server projection | `web/app.py:2092` |
| GET | `/api/openrouter/endpoints` | settings or derived server projection | `web/app.py:1656` |
| PUT | `/api/openrouter_routing` | settings or derived server projection | `web/app.py:1642` |
| POST | `/api/personas` | reusable persona records | `web/app.py:2776` |
| POST | `/api/personas/generate` | reusable persona records | `web/app.py:2754` |
| POST | `/api/personas/import` | reusable persona records | `web/app.py:2796` |
| DELETE | `/api/personas/{pid}` | reusable persona records | `web/app.py:2828` |
| PUT | `/api/personas/{pid}` | reusable persona records | `web/app.py:2819` |
| GET | `/api/personas/{pid}/export` | reusable persona records | `web/app.py:2810` |
| POST | `/api/personas/{pid}/fill_appearance` | reusable persona records | `web/app.py:2724` |
| PUT | `/api/prompt_presets` | settings or derived server projection | `web/app.py:1742` |
| POST | `/api/prompt_presets/import` | settings or derived server projection | `web/app.py:1778` |
| DELETE | `/api/prompt_presets/{name}` | settings or derived server projection | `web/app.py:1792` |
| GET | `/api/prompt_presets/{name}/export` | settings or derived server projection | `web/app.py:1769` |
| POST | `/api/providers` | provider/model configuration | `web/app.py:2472` |
| DELETE | `/api/providers/{pid}` | provider/model configuration | `web/app.py:2551` |
| PUT | `/api/providers/{pid}` | provider/model configuration | `web/app.py:2479` |
| GET | `/api/providers/{pid}/image_models` | provider/model configuration | `web/app.py:2563` |
| GET | `/api/providers/{pid}/models` | provider/model configuration | `web/app.py:2556` |
| PUT | `/api/providers/{pid}/prompt_cache` | provider/model configuration | `web/app.py:2506` |
| PUT | `/api/reasoning_effort` | settings or derived server projection | `web/app.py:1668` |
| POST | `/api/steps/{sid}/activate` | settings or derived server projection | `web/app.py:5825` |
| POST | `/api/steps/{sid}/edit` | settings or derived server projection | `web/app.py:5815` |
| POST | `/api/steps/{sid}/reroll` | settings or derived server projection | `web/app.py:5768` |
| DELETE | `/api/turns/{tid}` | turn/step/narration records | `web/app.py:5838` |
| GET | `/api/turns/{tid}/ambience` | turn/step/narration records | `web/app.py:6128` |
| POST | `/api/turns/{tid}/ambience` | turn/step/narration records | `web/app.py:6145` |
| GET | `/api/turns/{tid}/backdrop` | turn/step/narration records | `web/app.py:5975` |
| POST | `/api/turns/{tid}/backdrop` | turn/step/narration records | `web/app.py:5990` |
| POST | `/api/turns/{tid}/branch` | turn/step/narration records | `web/app.py:5092` |
| PUT | `/api/turns/{tid}/input` | turn/step/narration records | `web/app.py:5500` |
| GET | `/api/turns/{tid}/narration` | turn/step/narration records | `web/app.py:5585` |
| POST | `/api/turns/{tid}/narration` | turn/step/narration records | `web/app.py:5606` |
| GET | `/api/turns/{tid}/pipeline` | turn/step/narration records | `web/app.py:5630` |
| PUT | `/api/turns/{tid}/prose` | turn/step/narration records | `web/app.py:5515` |
| POST | `/api/turns/{tid}/reroll` | turn/step/narration records | `web/app.py:5699` |
| POST | `/api/turns/{tid}/rerun` | turn/step/narration records | `web/app.py:5709` |
| POST | `/api/turns/{tid}/resume` | turn/step/narration records | `web/app.py:5736` |
| GET | `/api/ui` | UI language-pack projection | `web/app.py:3133` |
| PUT | `/api/ui-language` | UI language-pack projection | `web/app.py:3158` |
| GET | `/api/updates/check` | settings or derived server projection | `web/app.py:2155` |
| POST | `/api/updates/install` | settings or derived server projection | `web/app.py:2159` |
| GET | `/guest` | settings or derived server projection | `web/app.py:547` |
| GET | `/login` | settings or derived server projection | `web/app.py:581` |
| POST | `/login` | settings or derived server projection | `web/auth_routes.py:208` |
| POST | `/logout` | settings or derived server projection | `web/auth_routes.py:274` |
| POST | `/setup` | settings or derived server projection | `web/auth_routes.py:133` |
| GET | `/status` | settings or derived server projection | `web/auth_routes.py:123` |
| GET | `/ui-next` | settings or derived server projection | `web/app.py:560` |
| GET | `/ui-next/lab` | settings or derived server projection | `web/app.py:574` |
