# Current API and persistence boundary map

The storage column names server authority; it does not authorize direct client persistence.

| Method | Route | Server authority | Source |
|---|---|---|---|
| GET | `/` | settings or derived server projection | `web/app.py:562` |
| PUT | `/api/active_preset` | settings or derived server projection | `web/app.py:1840` |
| PUT | `/api/affect_habituation` | settings or derived server projection | `web/app.py:2160` |
| PUT | `/api/agent_models` | settings or derived server projection | `web/app.py:1530` |
| PUT | `/api/ambience` | settings or derived server projection | `web/app.py:1651` |
| GET | `/api/ambience/library` | settings or derived server projection | `web/app.py:6391` |
| GET | `/api/ambience/search` | settings or derived server projection | `web/app.py:6370` |
| PUT | `/api/attire_beneath` | settings or derived server projection | `web/app.py:2179` |
| GET | `/api/auto_promote` | settings or derived server projection | `web/app.py:3872` |
| PUT | `/api/auto_promote` | settings or derived server projection | `web/app.py:3885` |
| PUT | `/api/backdrops` | settings or derived server projection | `web/app.py:1641` |
| GET | `/api/bootstrap` | settings or derived server projection | `web/app.py:1424` |
| POST | `/api/characters` | reusable character records | `web/app.py:2660` |
| POST | `/api/characters/generate` | reusable character records | `web/app.py:2619` |
| POST | `/api/characters/generate-preview` | reusable character records | `web/app.py:2643` |
| POST | `/api/characters/import` | reusable character records | `web/app.py:2685` |
| GET | `/api/characters/new-document` | reusable character records | `web/app.py:2612` |
| DELETE | `/api/characters/{cid}` | reusable character records | `web/app.py:2857` |
| PUT | `/api/characters/{cid}` | reusable character records | `web/app.py:2812` |
| POST | `/api/characters/{cid}/duplicate` | reusable character records | `web/app.py:2830` |
| GET | `/api/characters/{cid}/export` | reusable character records | `web/app.py:2804` |
| POST | `/api/characters/{cid}/fill_appearance` | reusable character records | `web/app.py:2792` |
| POST | `/api/characters/{cid}/fill_psychology` | reusable character records | `web/app.py:2763` |
| POST | `/api/characters/{cid}/generate_greeting` | reusable character records | `web/app.py:2747` |
| POST | `/api/characters/{cid}/recover_greetings` | reusable character records | `web/app.py:2726` |
| POST | `/api/characters/{cid}/recover_greetings_preview` | reusable character records | `web/app.py:2737` |
| POST | `/api/characters/{cid}/start` | reusable character records | `web/app.py:2700` |
| POST | `/api/chats` | chat/frame/world records and projections | `web/app.py:3270` |
| DELETE | `/api/chats/{cid}` | chat/frame/world records and projections | `web/app.py:3508` |
| GET | `/api/chats/{cid}` | chat/frame/world records and projections | `web/app.py:3539` |
| PUT | `/api/chats/{cid}` | chat/frame/world records and projections | `web/app.py:3368` |
| POST | `/api/chats/{cid}/abort` | chat/frame/world records and projections | `web/app.py:5264` |
| GET | `/api/chats/{cid}/ambience/oneshot/{name}` | chat/frame/world records and projections | `web/app.py:6400` |
| DELETE | `/api/chats/{cid}/ambience/pin` | chat/frame/world records and projections | `web/app.py:6448` |
| PUT | `/api/chats/{cid}/ambience/pin` | chat/frame/world records and projections | `web/app.py:6429` |
| GET | `/api/chats/{cid}/ambience/pins` | chat/frame/world records and projections | `web/app.py:6424` |
| GET | `/api/chats/{cid}/ambience/{signature}.audio` | chat/frame/world records and projections | `web/app.py:6354` |
| GET | `/api/chats/{cid}/attire` | chat/frame/world records and projections | `web/app.py:4598` |
| PUT | `/api/chats/{cid}/attire` | chat/frame/world records and projections | `web/app.py:4609` |
| GET | `/api/chats/{cid}/backdrop/{signature}.png` | chat/frame/world records and projections | `web/app.py:6194` |
| GET | `/api/chats/{cid}/background_config` | chat/frame/world records and projections | `web/app.py:4781` |
| PUT | `/api/chats/{cid}/background_config` | chat/frame/world records and projections | `web/app.py:4785` |
| POST | `/api/chats/{cid}/characters` | chat/frame/world records and projections | `web/app.py:3775` |
| DELETE | `/api/chats/{cid}/characters/{ch}` | chat/frame/world records and projections | `web/app.py:4166` |
| PUT | `/api/chats/{cid}/characters/{ch}/card` | chat/frame/world records and projections | `web/app.py:4177` |
| PUT | `/api/chats/{cid}/characters/{ch}/dialogue_color` | chat/frame/world records and projections | `web/app.py:4482` |
| GET | `/api/chats/{cid}/characters/{ch}/memories` | chat/frame/world records and projections | `web/app.py:5004` |
| POST | `/api/chats/{cid}/characters/{ch}/memories` | chat/frame/world records and projections | `web/app.py:5151` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/backfill` | chat/frame/world records and projections | `web/app.py:5121` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/consolidate` | chat/frame/world records and projections | `web/app.py:5106` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/coverage` | chat/frame/world records and projections | `web/app.py:5142` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/export` | chat/frame/world records and projections | `web/app.py:5050` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/import` | chat/frame/world records and projections | `web/app.py:5061` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/search` | chat/frame/world records and projections | `web/app.py:5025` |
| GET | `/api/chats/{cid}/characters/{ch}/memory-context` | chat/frame/world records and projections | `web/app.py:5082` |
| PUT | `/api/chats/{cid}/characters/{ch}/position` | chat/frame/world records and projections | `web/app.py:4394` |
| GET | `/api/chats/{cid}/characters/{ch}/private_history` | chat/frame/world records and projections | `web/app.py:4463` |
| PUT | `/api/chats/{cid}/characters/{ch}/private_history` | chat/frame/world records and projections | `web/app.py:4473` |
| GET | `/api/chats/{cid}/characters/{ch}/relationships` | chat/frame/world records and projections | `web/app.py:5095` |
| GET | `/api/chats/{cid}/dialogue_config` | chat/frame/world records and projections | `web/app.py:4648` |
| PUT | `/api/chats/{cid}/dialogue_config` | chat/frame/world records and projections | `web/app.py:4665` |
| GET | `/api/chats/{cid}/dramatic_irony` | chat/frame/world records and projections | `web/app.py:3830` |
| GET | `/api/chats/{cid}/fixed_points` | chat/frame/world records and projections | `web/app.py:4948` |
| POST | `/api/chats/{cid}/fixed_points` | chat/frame/world records and projections | `web/app.py:4958` |
| DELETE | `/api/chats/{cid}/fixed_points/{anchor_id}` | chat/frame/world records and projections | `web/app.py:4980` |
| GET | `/api/chats/{cid}/frames` | chat/frame/world records and projections | `web/app.py:4902` |
| POST | `/api/chats/{cid}/frames` | chat/frame/world records and projections | `web/app.py:4906` |
| GET | `/api/chats/{cid}/guest_invites` | chat/frame/world records and projections | `web/app.py:4047` |
| POST | `/api/chats/{cid}/guest_invites` | chat/frame/world records and projections | `web/app.py:4027` |
| DELETE | `/api/chats/{cid}/guest_invites/{gid}` | chat/frame/world records and projections | `web/app.py:4051` |
| GET | `/api/chats/{cid}/language` | chat/frame/world records and projections | `web/app.py:3335` |
| PUT | `/api/chats/{cid}/language` | chat/frame/world records and projections | `web/app.py:3352` |
| GET | `/api/chats/{cid}/living_world` | chat/frame/world records and projections | `web/app.py:4746` |
| PUT | `/api/chats/{cid}/living_world` | chat/frame/world records and projections | `web/app.py:4769` |
| DELETE | `/api/chats/{cid}/lorebook` | chat/frame/world records and projections | `web/app.py:3499` |
| POST | `/api/chats/{cid}/lorebook` | chat/frame/world records and projections | `web/app.py:3478` |
| GET | `/api/chats/{cid}/lorebooks` | chat/frame/world records and projections | `web/app.py:2263` |
| POST | `/api/chats/{cid}/lorebooks` | chat/frame/world records and projections | `web/app.py:3402` |
| DELETE | `/api/chats/{cid}/lorebooks/{lid}` | chat/frame/world records and projections | `web/app.py:3463` |
| PUT | `/api/chats/{cid}/lorebooks/{lid}` | chat/frame/world records and projections | `web/app.py:3427` |
| GET | `/api/chats/{cid}/paradox_policy` | chat/frame/world records and projections | `web/app.py:4933` |
| PUT | `/api/chats/{cid}/paradox_policy` | chat/frame/world records and projections | `web/app.py:4937` |
| GET | `/api/chats/{cid}/persona_private_history` | chat/frame/world records and projections | `web/app.py:4534` |
| PUT | `/api/chats/{cid}/persona_private_history` | chat/frame/world records and projections | `web/app.py:4547` |
| GET | `/api/chats/{cid}/personas` | chat/frame/world records and projections | `web/app.py:3890` |
| POST | `/api/chats/{cid}/personas` | chat/frame/world records and projections | `web/app.py:3935` |
| DELETE | `/api/chats/{cid}/personas/{pid}` | chat/frame/world records and projections | `web/app.py:3962` |
| PUT | `/api/chats/{cid}/personas/{pid}/station` | chat/frame/world records and projections | `web/app.py:3900` |
| GET | `/api/chats/{cid}/player_authority` | chat/frame/world records and projections | `web/app.py:4865` |
| PUT | `/api/chats/{cid}/player_authority` | chat/frame/world records and projections | `web/app.py:4880` |
| GET | `/api/chats/{cid}/player_view` | chat/frame/world records and projections | `web/app.py:4842` |
| GET | `/api/chats/{cid}/positions` | chat/frame/world records and projections | `web/app.py:4327` |
| GET | `/api/chats/{cid}/promises` | chat/frame/world records and projections | `web/app.py:3834` |
| GET | `/api/chats/{cid}/promotable` | chat/frame/world records and projections | `web/app.py:3826` |
| POST | `/api/chats/{cid}/promotions/confirm` | chat/frame/world records and projections | `web/app.py:3852` |
| POST | `/api/chats/{cid}/promotions/draft` | chat/frame/world records and projections | `web/app.py:3838` |
| GET | `/api/chats/{cid}/story_view` | chat/frame/world records and projections | `web/app.py:4811` |
| GET | `/api/chats/{cid}/style_guide` | chat/frame/world records and projections | `web/app.py:4631` |
| PUT | `/api/chats/{cid}/style_guide` | chat/frame/world records and projections | `web/app.py:4637` |
| GET | `/api/chats/{cid}/survival` | chat/frame/world records and projections | `web/app.py:4235` |
| PUT | `/api/chats/{cid}/survival` | chat/frame/world records and projections | `web/app.py:4240` |
| POST | `/api/chats/{cid}/turns` | chat/frame/world records and projections | `web/app.py:5204` |
| POST | `/api/chats/{cid}/turns/{idx}/player_input` | chat/frame/world records and projections | `web/app.py:3977` |
| GET | `/api/chats/{cid}/viewers` | chat/frame/world records and projections | `web/app.py:4857` |
| GET | `/api/chats/{cid}/vitals` | chat/frame/world records and projections | `web/app.py:4292` |
| GET | `/api/chats/{cid}/world` | chat/frame/world records and projections | `web/app.py:4552` |
| PUT | `/api/chats/{cid}/world` | chat/frame/world records and projections | `web/app.py:4562` |
| GET | `/api/default_prompts` | settings or derived server projection | `web/app.py:1770` |
| PUT | `/api/director_fanout_mode` | settings or derived server projection | `web/app.py:2136` |
| PUT | `/api/exemplars` | settings or derived server projection | `web/app.py:1610` |
| GET | `/api/extensions` | extension runtime/config/state/documents | `web/app.py:1857` |
| POST | `/api/extensions/install` | extension runtime/config/state/documents | `web/app.py:1879` |
| GET | `/api/extensions/ui.css` | extension runtime/config/state/documents | `web/app.py:2057` |
| GET | `/api/extensions/ui.js` | extension runtime/config/state/documents | `web/app.py:2048` |
| GET | `/api/extensions/updates` | extension runtime/config/state/documents | `web/app.py:1900` |
| DELETE | `/api/extensions/{eid}` | extension runtime/config/state/documents | `web/app.py:1921` |
| GET | `/api/extensions/{eid}/asset/{path:path}` | extension runtime/config/state/documents | `web/app.py:2112` |
| POST | `/api/extensions/{eid}/disable` | extension runtime/config/state/documents | `web/app.py:1929` |
| DELETE | `/api/extensions/{eid}/document` | extension runtime/config/state/documents | `web/app.py:2025` |
| GET | `/api/extensions/{eid}/document` | extension runtime/config/state/documents | `web/app.py:1993` |
| PUT | `/api/extensions/{eid}/document` | extension runtime/config/state/documents | `web/app.py:2005` |
| DELETE | `/api/extensions/{eid}/documents` | extension runtime/config/state/documents | `web/app.py:2035` |
| GET | `/api/extensions/{eid}/documents` | extension runtime/config/state/documents | `web/app.py:1972` |
| GET | `/api/extensions/{eid}/documents/verify` | extension runtime/config/state/documents | `web/app.py:1983` |
| POST | `/api/extensions/{eid}/enable` | extension runtime/config/state/documents | `web/app.py:1871` |
| GET | `/api/extensions/{eid}/state` | extension runtime/config/state/documents | `web/app.py:1934` |
| GET | `/api/extensions/{eid}/ui.css` | extension runtime/config/state/documents | `web/app.py:2079` |
| GET | `/api/extensions/{eid}/ui.js` | extension runtime/config/state/documents | `web/app.py:2067` |
| POST | `/api/extensions/{eid}/update` | extension runtime/config/state/documents | `web/app.py:1911` |
| POST | `/api/guest/input` | guest session/invite tables | `web/app.py:4141` |
| GET | `/api/guest/state` | guest session/invite tables | `web/app.py:4073` |
| PUT | `/api/image_model` | settings or derived server projection | `web/app.py:1588` |
| POST | `/api/join` | settings or derived server projection | `web/app.py:4057` |
| GET | `/api/language-packs` | installed language-pack projection | `web/app.py:3288` |
| GET | `/api/language-packs/{language_id}/ui` | installed language-pack projection | `web/app.py:3309` |
| GET | `/api/library` | Library projection and reversible lifecycle metadata | `web/library.py:310` |
| GET | `/api/library/authoring/{kind}/{item_id}` | Library projection and reversible lifecycle metadata | `web/library_authoring.py:253` |
| DELETE | `/api/library/{kind}/{item_id}/archive` | Library projection and reversible lifecycle metadata | `web/library.py:407` |
| PUT | `/api/library/{kind}/{item_id}/archive` | Library projection and reversible lifecycle metadata | `web/library.py:388` |
| DELETE | `/api/lore_entries/{eid}` | settings or derived server projection | `web/app.py:3263` |
| PUT | `/api/lore_entries/{eid}` | settings or derived server projection | `web/app.py:3191` |
| DELETE | `/api/lore_gen_jobs/{job_id}` | settings or derived server projection | `web/app.py:2419` |
| POST | `/api/lore_gen_jobs/{job_id}/resume` | settings or derived server projection | `web/app.py:2401` |
| DELETE | `/api/lorebook_links/{link_id}` | settings or derived server projection | `web/app.py:2359` |
| PUT | `/api/lorebook_links/{link_id}` | settings or derived server projection | `web/app.py:2345` |
| POST | `/api/lorebooks` | lorebook/entry/link records | `web/app.py:3019` |
| POST | `/api/lorebooks/import` | lorebook/entry/link records | `web/app.py:2455` |
| DELETE | `/api/lorebooks/{lid}` | lorebook/entry/link records | `web/app.py:3112` |
| GET | `/api/lorebooks/{lid}` | lorebook/entry/link records | `web/app.py:3000` |
| PUT | `/api/lorebooks/{lid}` | lorebook/entry/link records | `web/app.py:3042` |
| POST | `/api/lorebooks/{lid}/apply_plan` | lorebook/entry/link records | `web/app.py:2428` |
| POST | `/api/lorebooks/{lid}/entries` | lorebook/entry/link records | `web/app.py:3162` |
| GET | `/api/lorebooks/{lid}/export` | lorebook/entry/link records | `web/app.py:3118` |
| POST | `/api/lorebooks/{lid}/generate` | lorebook/entry/link records | `web/app.py:3148` |
| GET | `/api/lorebooks/{lid}/generate_job` | lorebook/entry/link records | `web/app.py:2390` |
| POST | `/api/lorebooks/{lid}/generate_plan` | lorebook/entry/link records | `web/app.py:2364` |
| GET | `/api/lorebooks/{lid}/links` | lorebook/entry/link records | `web/app.py:2318` |
| POST | `/api/lorebooks/{lid}/links` | lorebook/entry/link records | `web/app.py:2323` |
| POST | `/api/lorebooks/{lid}/move` | lorebook/entry/link records | `web/app.py:2245` |
| POST | `/api/lorebooks/{lid}/reinterpret` | lorebook/entry/link records | `web/app.py:3135` |
| POST | `/api/lorebooks/{lid}/reorder` | lorebook/entry/link records | `web/app.py:2254` |
| GET | `/api/maintenance/checkpoints` | checkpoint/maintenance operations | `web/app.py:2202` |
| POST | `/api/maintenance/checkpoints/compact` | checkpoint/maintenance operations | `web/app.py:2218` |
| PUT | `/api/max_output_tokens` | settings or derived server projection | `web/app.py:1737` |
| DELETE | `/api/memories/{mid}` | settings or derived server projection | `web/app.py:5198` |
| PUT | `/api/memories/{mid}` | settings or derived server projection | `web/app.py:5177` |
| GET | `/api/memory/embeddings` | settings or derived server projection | `web/app.py:1561` |
| POST | `/api/memory/embeddings/rebuild` | settings or derived server projection | `web/app.py:1576` |
| GET | `/api/nsfw` | settings or derived server projection | `web/app.py:2127` |
| PUT | `/api/nsfw` | settings or derived server projection | `web/app.py:2131` |
| GET | `/api/openrouter/endpoints` | settings or derived server projection | `web/app.py:1695` |
| PUT | `/api/openrouter_routing` | settings or derived server projection | `web/app.py:1681` |
| POST | `/api/personas` | reusable persona records | `web/app.py:2911` |
| POST | `/api/personas/generate` | reusable persona records | `web/app.py:2871` |
| POST | `/api/personas/generate-preview` | reusable persona records | `web/app.py:2894` |
| POST | `/api/personas/import` | reusable persona records | `web/app.py:2931` |
| GET | `/api/personas/new-document` | reusable persona records | `web/app.py:2865` |
| DELETE | `/api/personas/{pid}` | reusable persona records | `web/app.py:2993` |
| PUT | `/api/personas/{pid}` | reusable persona records | `web/app.py:2954` |
| POST | `/api/personas/{pid}/duplicate` | reusable persona records | `web/app.py:2968` |
| GET | `/api/personas/{pid}/export` | reusable persona records | `web/app.py:2945` |
| POST | `/api/personas/{pid}/fill_appearance` | reusable persona records | `web/app.py:2799` |
| PUT | `/api/prompt_presets` | settings or derived server projection | `web/app.py:1781` |
| POST | `/api/prompt_presets/import` | settings or derived server projection | `web/app.py:1817` |
| DELETE | `/api/prompt_presets/{name}` | settings or derived server projection | `web/app.py:1831` |
| GET | `/api/prompt_presets/{name}/export` | settings or derived server projection | `web/app.py:1808` |
| POST | `/api/providers` | provider/model configuration | `web/app.py:2511` |
| DELETE | `/api/providers/{pid}` | provider/model configuration | `web/app.py:2590` |
| PUT | `/api/providers/{pid}` | provider/model configuration | `web/app.py:2518` |
| GET | `/api/providers/{pid}/image_models` | provider/model configuration | `web/app.py:2602` |
| GET | `/api/providers/{pid}/models` | provider/model configuration | `web/app.py:2595` |
| PUT | `/api/providers/{pid}/prompt_cache` | provider/model configuration | `web/app.py:2545` |
| PUT | `/api/reasoning_effort` | settings or derived server projection | `web/app.py:1707` |
| POST | `/api/steps/{sid}/activate` | settings or derived server projection | `web/app.py:6001` |
| POST | `/api/steps/{sid}/edit` | settings or derived server projection | `web/app.py:5991` |
| POST | `/api/steps/{sid}/reroll` | settings or derived server projection | `web/app.py:5944` |
| DELETE | `/api/turns/{tid}` | turn/step/narration records | `web/app.py:6014` |
| GET | `/api/turns/{tid}/ambience` | turn/step/narration records | `web/app.py:6304` |
| POST | `/api/turns/{tid}/ambience` | turn/step/narration records | `web/app.py:6321` |
| GET | `/api/turns/{tid}/backdrop` | turn/step/narration records | `web/app.py:6151` |
| POST | `/api/turns/{tid}/backdrop` | turn/step/narration records | `web/app.py:6166` |
| POST | `/api/turns/{tid}/branch` | turn/step/narration records | `web/app.py:5268` |
| PUT | `/api/turns/{tid}/input` | turn/step/narration records | `web/app.py:5676` |
| GET | `/api/turns/{tid}/narration` | turn/step/narration records | `web/app.py:5761` |
| POST | `/api/turns/{tid}/narration` | turn/step/narration records | `web/app.py:5782` |
| GET | `/api/turns/{tid}/pipeline` | turn/step/narration records | `web/app.py:5806` |
| PUT | `/api/turns/{tid}/prose` | turn/step/narration records | `web/app.py:5691` |
| POST | `/api/turns/{tid}/reroll` | turn/step/narration records | `web/app.py:5875` |
| POST | `/api/turns/{tid}/rerun` | turn/step/narration records | `web/app.py:5885` |
| POST | `/api/turns/{tid}/resume` | turn/step/narration records | `web/app.py:5912` |
| GET | `/api/ui` | UI language-pack projection | `web/app.py:3299` |
| PUT | `/api/ui-language` | UI language-pack projection | `web/app.py:3324` |
| GET | `/api/updates/check` | settings or derived server projection | `web/app.py:2194` |
| POST | `/api/updates/install` | settings or derived server projection | `web/app.py:2198` |
| GET | `/guest` | settings or derived server projection | `web/app.py:554` |
| GET | `/login` | settings or derived server projection | `web/app.py:585` |
| POST | `/login` | settings or derived server projection | `web/auth_routes.py:208` |
| POST | `/logout` | settings or derived server projection | `web/auth_routes.py:274` |
| POST | `/setup` | settings or derived server projection | `web/auth_routes.py:133` |
| GET | `/status` | settings or derived server projection | `web/auth_routes.py:123` |
| GET | `/ui-next/lab` | settings or derived server projection | `web/app.py:570` |
| GET | `/ui-next/runtime` | settings or derived server projection | `web/app.py:578` |
