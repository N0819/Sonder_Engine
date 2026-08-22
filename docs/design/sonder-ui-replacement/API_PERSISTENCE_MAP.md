# Current API and persistence boundary map

The storage column names server authority; it does not authorize direct client persistence.

| Method | Route | Server authority | Source |
|---|---|---|---|
| GET | `/` | settings or derived server projection | `web/app.py:555` |
| PUT | `/api/active_preset` | settings or derived server projection | `web/app.py:1793` |
| PUT | `/api/affect_habituation` | settings or derived server projection | `web/app.py:2113` |
| PUT | `/api/agent_models` | settings or derived server projection | `web/app.py:1483` |
| PUT | `/api/ambience` | settings or derived server projection | `web/app.py:1604` |
| GET | `/api/ambience/library` | settings or derived server projection | `web/app.py:6207` |
| GET | `/api/ambience/search` | settings or derived server projection | `web/app.py:6186` |
| PUT | `/api/attire_beneath` | settings or derived server projection | `web/app.py:2132` |
| GET | `/api/auto_promote` | settings or derived server projection | `web/app.py:3693` |
| PUT | `/api/auto_promote` | settings or derived server projection | `web/app.py:3706` |
| PUT | `/api/backdrops` | settings or derived server projection | `web/app.py:1594` |
| GET | `/api/bootstrap` | settings or derived server projection | `web/app.py:1377` |
| POST | `/api/characters` | reusable character records | `web/app.py:2588` |
| POST | `/api/characters/generate` | reusable character records | `web/app.py:2565` |
| POST | `/api/characters/import` | reusable character records | `web/app.py:2613` |
| DELETE | `/api/characters/{cid}` | reusable character records | `web/app.py:2739` |
| PUT | `/api/characters/{cid}` | reusable character records | `web/app.py:2729` |
| GET | `/api/characters/{cid}/export` | reusable character records | `web/app.py:2721` |
| POST | `/api/characters/{cid}/fill_appearance` | reusable character records | `web/app.py:2709` |
| POST | `/api/characters/{cid}/fill_psychology` | reusable character records | `web/app.py:2680` |
| POST | `/api/characters/{cid}/generate_greeting` | reusable character records | `web/app.py:2664` |
| POST | `/api/characters/{cid}/recover_greetings` | reusable character records | `web/app.py:2654` |
| POST | `/api/characters/{cid}/start` | reusable character records | `web/app.py:2628` |
| POST | `/api/chats` | chat/frame/world records and projections | `web/app.py:3096` |
| DELETE | `/api/chats/{cid}` | chat/frame/world records and projections | `web/app.py:3331` |
| GET | `/api/chats/{cid}` | chat/frame/world records and projections | `web/app.py:3361` |
| PUT | `/api/chats/{cid}` | chat/frame/world records and projections | `web/app.py:3194` |
| POST | `/api/chats/{cid}/abort` | chat/frame/world records and projections | `web/app.py:5080` |
| GET | `/api/chats/{cid}/ambience/oneshot/{name}` | chat/frame/world records and projections | `web/app.py:6216` |
| DELETE | `/api/chats/{cid}/ambience/pin` | chat/frame/world records and projections | `web/app.py:6264` |
| PUT | `/api/chats/{cid}/ambience/pin` | chat/frame/world records and projections | `web/app.py:6245` |
| GET | `/api/chats/{cid}/ambience/pins` | chat/frame/world records and projections | `web/app.py:6240` |
| GET | `/api/chats/{cid}/ambience/{signature}.audio` | chat/frame/world records and projections | `web/app.py:6170` |
| GET | `/api/chats/{cid}/attire` | chat/frame/world records and projections | `web/app.py:4416` |
| PUT | `/api/chats/{cid}/attire` | chat/frame/world records and projections | `web/app.py:4427` |
| GET | `/api/chats/{cid}/backdrop/{signature}.png` | chat/frame/world records and projections | `web/app.py:6010` |
| GET | `/api/chats/{cid}/background_config` | chat/frame/world records and projections | `web/app.py:4599` |
| PUT | `/api/chats/{cid}/background_config` | chat/frame/world records and projections | `web/app.py:4603` |
| POST | `/api/chats/{cid}/characters` | chat/frame/world records and projections | `web/app.py:3597` |
| DELETE | `/api/chats/{cid}/characters/{ch}` | chat/frame/world records and projections | `web/app.py:3985` |
| PUT | `/api/chats/{cid}/characters/{ch}/card` | chat/frame/world records and projections | `web/app.py:3995` |
| PUT | `/api/chats/{cid}/characters/{ch}/dialogue_color` | chat/frame/world records and projections | `web/app.py:4300` |
| GET | `/api/chats/{cid}/characters/{ch}/memories` | chat/frame/world records and projections | `web/app.py:4820` |
| POST | `/api/chats/{cid}/characters/{ch}/memories` | chat/frame/world records and projections | `web/app.py:4967` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/backfill` | chat/frame/world records and projections | `web/app.py:4937` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/consolidate` | chat/frame/world records and projections | `web/app.py:4922` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/coverage` | chat/frame/world records and projections | `web/app.py:4958` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/export` | chat/frame/world records and projections | `web/app.py:4866` |
| POST | `/api/chats/{cid}/characters/{ch}/memories/import` | chat/frame/world records and projections | `web/app.py:4877` |
| GET | `/api/chats/{cid}/characters/{ch}/memories/search` | chat/frame/world records and projections | `web/app.py:4841` |
| GET | `/api/chats/{cid}/characters/{ch}/memory-context` | chat/frame/world records and projections | `web/app.py:4898` |
| PUT | `/api/chats/{cid}/characters/{ch}/position` | chat/frame/world records and projections | `web/app.py:4212` |
| GET | `/api/chats/{cid}/characters/{ch}/private_history` | chat/frame/world records and projections | `web/app.py:4281` |
| PUT | `/api/chats/{cid}/characters/{ch}/private_history` | chat/frame/world records and projections | `web/app.py:4291` |
| GET | `/api/chats/{cid}/characters/{ch}/relationships` | chat/frame/world records and projections | `web/app.py:4911` |
| GET | `/api/chats/{cid}/dialogue_config` | chat/frame/world records and projections | `web/app.py:4466` |
| PUT | `/api/chats/{cid}/dialogue_config` | chat/frame/world records and projections | `web/app.py:4483` |
| GET | `/api/chats/{cid}/dramatic_irony` | chat/frame/world records and projections | `web/app.py:3651` |
| GET | `/api/chats/{cid}/fixed_points` | chat/frame/world records and projections | `web/app.py:4766` |
| POST | `/api/chats/{cid}/fixed_points` | chat/frame/world records and projections | `web/app.py:4776` |
| DELETE | `/api/chats/{cid}/fixed_points/{anchor_id}` | chat/frame/world records and projections | `web/app.py:4798` |
| GET | `/api/chats/{cid}/frames` | chat/frame/world records and projections | `web/app.py:4720` |
| POST | `/api/chats/{cid}/frames` | chat/frame/world records and projections | `web/app.py:4724` |
| GET | `/api/chats/{cid}/guest_invites` | chat/frame/world records and projections | `web/app.py:3866` |
| POST | `/api/chats/{cid}/guest_invites` | chat/frame/world records and projections | `web/app.py:3846` |
| DELETE | `/api/chats/{cid}/guest_invites/{gid}` | chat/frame/world records and projections | `web/app.py:3870` |
| GET | `/api/chats/{cid}/language` | chat/frame/world records and projections | `web/app.py:3161` |
| PUT | `/api/chats/{cid}/language` | chat/frame/world records and projections | `web/app.py:3178` |
| GET | `/api/chats/{cid}/living_world` | chat/frame/world records and projections | `web/app.py:4564` |
| PUT | `/api/chats/{cid}/living_world` | chat/frame/world records and projections | `web/app.py:4587` |
| DELETE | `/api/chats/{cid}/lorebook` | chat/frame/world records and projections | `web/app.py:3322` |
| POST | `/api/chats/{cid}/lorebook` | chat/frame/world records and projections | `web/app.py:3301` |
| GET | `/api/chats/{cid}/lorebooks` | chat/frame/world records and projections | `web/app.py:2216` |
| POST | `/api/chats/{cid}/lorebooks` | chat/frame/world records and projections | `web/app.py:3225` |
| DELETE | `/api/chats/{cid}/lorebooks/{lid}` | chat/frame/world records and projections | `web/app.py:3286` |
| PUT | `/api/chats/{cid}/lorebooks/{lid}` | chat/frame/world records and projections | `web/app.py:3250` |
| GET | `/api/chats/{cid}/paradox_policy` | chat/frame/world records and projections | `web/app.py:4751` |
| PUT | `/api/chats/{cid}/paradox_policy` | chat/frame/world records and projections | `web/app.py:4755` |
| GET | `/api/chats/{cid}/persona_private_history` | chat/frame/world records and projections | `web/app.py:4352` |
| PUT | `/api/chats/{cid}/persona_private_history` | chat/frame/world records and projections | `web/app.py:4365` |
| GET | `/api/chats/{cid}/personas` | chat/frame/world records and projections | `web/app.py:3711` |
| POST | `/api/chats/{cid}/personas` | chat/frame/world records and projections | `web/app.py:3756` |
| DELETE | `/api/chats/{cid}/personas/{pid}` | chat/frame/world records and projections | `web/app.py:3782` |
| PUT | `/api/chats/{cid}/personas/{pid}/station` | chat/frame/world records and projections | `web/app.py:3721` |
| GET | `/api/chats/{cid}/player_authority` | chat/frame/world records and projections | `web/app.py:4683` |
| PUT | `/api/chats/{cid}/player_authority` | chat/frame/world records and projections | `web/app.py:4698` |
| GET | `/api/chats/{cid}/player_view` | chat/frame/world records and projections | `web/app.py:4660` |
| GET | `/api/chats/{cid}/positions` | chat/frame/world records and projections | `web/app.py:4145` |
| GET | `/api/chats/{cid}/promises` | chat/frame/world records and projections | `web/app.py:3655` |
| GET | `/api/chats/{cid}/promotable` | chat/frame/world records and projections | `web/app.py:3647` |
| POST | `/api/chats/{cid}/promotions/confirm` | chat/frame/world records and projections | `web/app.py:3673` |
| POST | `/api/chats/{cid}/promotions/draft` | chat/frame/world records and projections | `web/app.py:3659` |
| GET | `/api/chats/{cid}/story_view` | chat/frame/world records and projections | `web/app.py:4629` |
| GET | `/api/chats/{cid}/style_guide` | chat/frame/world records and projections | `web/app.py:4449` |
| PUT | `/api/chats/{cid}/style_guide` | chat/frame/world records and projections | `web/app.py:4455` |
| GET | `/api/chats/{cid}/survival` | chat/frame/world records and projections | `web/app.py:4053` |
| PUT | `/api/chats/{cid}/survival` | chat/frame/world records and projections | `web/app.py:4058` |
| POST | `/api/chats/{cid}/turns` | chat/frame/world records and projections | `web/app.py:5020` |
| POST | `/api/chats/{cid}/turns/{idx}/player_input` | chat/frame/world records and projections | `web/app.py:3796` |
| GET | `/api/chats/{cid}/viewers` | chat/frame/world records and projections | `web/app.py:4675` |
| GET | `/api/chats/{cid}/vitals` | chat/frame/world records and projections | `web/app.py:4110` |
| GET | `/api/chats/{cid}/world` | chat/frame/world records and projections | `web/app.py:4370` |
| PUT | `/api/chats/{cid}/world` | chat/frame/world records and projections | `web/app.py:4380` |
| GET | `/api/default_prompts` | settings or derived server projection | `web/app.py:1723` |
| PUT | `/api/director_fanout_mode` | settings or derived server projection | `web/app.py:2089` |
| PUT | `/api/exemplars` | settings or derived server projection | `web/app.py:1563` |
| GET | `/api/extensions` | extension runtime/config/state/documents | `web/app.py:1810` |
| POST | `/api/extensions/install` | extension runtime/config/state/documents | `web/app.py:1832` |
| GET | `/api/extensions/ui.css` | extension runtime/config/state/documents | `web/app.py:2010` |
| GET | `/api/extensions/ui.js` | extension runtime/config/state/documents | `web/app.py:2001` |
| GET | `/api/extensions/updates` | extension runtime/config/state/documents | `web/app.py:1853` |
| DELETE | `/api/extensions/{eid}` | extension runtime/config/state/documents | `web/app.py:1874` |
| GET | `/api/extensions/{eid}/asset/{path:path}` | extension runtime/config/state/documents | `web/app.py:2065` |
| POST | `/api/extensions/{eid}/disable` | extension runtime/config/state/documents | `web/app.py:1882` |
| DELETE | `/api/extensions/{eid}/document` | extension runtime/config/state/documents | `web/app.py:1978` |
| GET | `/api/extensions/{eid}/document` | extension runtime/config/state/documents | `web/app.py:1946` |
| PUT | `/api/extensions/{eid}/document` | extension runtime/config/state/documents | `web/app.py:1958` |
| DELETE | `/api/extensions/{eid}/documents` | extension runtime/config/state/documents | `web/app.py:1988` |
| GET | `/api/extensions/{eid}/documents` | extension runtime/config/state/documents | `web/app.py:1925` |
| GET | `/api/extensions/{eid}/documents/verify` | extension runtime/config/state/documents | `web/app.py:1936` |
| POST | `/api/extensions/{eid}/enable` | extension runtime/config/state/documents | `web/app.py:1824` |
| GET | `/api/extensions/{eid}/state` | extension runtime/config/state/documents | `web/app.py:1887` |
| GET | `/api/extensions/{eid}/ui.css` | extension runtime/config/state/documents | `web/app.py:2032` |
| GET | `/api/extensions/{eid}/ui.js` | extension runtime/config/state/documents | `web/app.py:2020` |
| POST | `/api/extensions/{eid}/update` | extension runtime/config/state/documents | `web/app.py:1864` |
| POST | `/api/guest/input` | guest session/invite tables | `web/app.py:3960` |
| GET | `/api/guest/state` | guest session/invite tables | `web/app.py:3892` |
| PUT | `/api/image_model` | settings or derived server projection | `web/app.py:1541` |
| POST | `/api/join` | settings or derived server projection | `web/app.py:3876` |
| GET | `/api/language-packs` | installed language-pack projection | `web/app.py:3114` |
| GET | `/api/language-packs/{language_id}/ui` | installed language-pack projection | `web/app.py:3135` |
| DELETE | `/api/lore_entries/{eid}` | settings or derived server projection | `web/app.py:3089` |
| PUT | `/api/lore_entries/{eid}` | settings or derived server projection | `web/app.py:3017` |
| DELETE | `/api/lore_gen_jobs/{job_id}` | settings or derived server projection | `web/app.py:2372` |
| POST | `/api/lore_gen_jobs/{job_id}/resume` | settings or derived server projection | `web/app.py:2354` |
| DELETE | `/api/lorebook_links/{link_id}` | settings or derived server projection | `web/app.py:2312` |
| PUT | `/api/lorebook_links/{link_id}` | settings or derived server projection | `web/app.py:2298` |
| POST | `/api/lorebooks` | lorebook/entry/link records | `web/app.py:2845` |
| POST | `/api/lorebooks/import` | lorebook/entry/link records | `web/app.py:2408` |
| DELETE | `/api/lorebooks/{lid}` | lorebook/entry/link records | `web/app.py:2938` |
| GET | `/api/lorebooks/{lid}` | lorebook/entry/link records | `web/app.py:2826` |
| PUT | `/api/lorebooks/{lid}` | lorebook/entry/link records | `web/app.py:2868` |
| POST | `/api/lorebooks/{lid}/apply_plan` | lorebook/entry/link records | `web/app.py:2381` |
| POST | `/api/lorebooks/{lid}/entries` | lorebook/entry/link records | `web/app.py:2988` |
| GET | `/api/lorebooks/{lid}/export` | lorebook/entry/link records | `web/app.py:2944` |
| POST | `/api/lorebooks/{lid}/generate` | lorebook/entry/link records | `web/app.py:2974` |
| GET | `/api/lorebooks/{lid}/generate_job` | lorebook/entry/link records | `web/app.py:2343` |
| POST | `/api/lorebooks/{lid}/generate_plan` | lorebook/entry/link records | `web/app.py:2317` |
| GET | `/api/lorebooks/{lid}/links` | lorebook/entry/link records | `web/app.py:2271` |
| POST | `/api/lorebooks/{lid}/links` | lorebook/entry/link records | `web/app.py:2276` |
| POST | `/api/lorebooks/{lid}/move` | lorebook/entry/link records | `web/app.py:2198` |
| POST | `/api/lorebooks/{lid}/reinterpret` | lorebook/entry/link records | `web/app.py:2961` |
| POST | `/api/lorebooks/{lid}/reorder` | lorebook/entry/link records | `web/app.py:2207` |
| GET | `/api/maintenance/checkpoints` | checkpoint/maintenance operations | `web/app.py:2155` |
| POST | `/api/maintenance/checkpoints/compact` | checkpoint/maintenance operations | `web/app.py:2171` |
| PUT | `/api/max_output_tokens` | settings or derived server projection | `web/app.py:1690` |
| DELETE | `/api/memories/{mid}` | settings or derived server projection | `web/app.py:5014` |
| PUT | `/api/memories/{mid}` | settings or derived server projection | `web/app.py:4993` |
| GET | `/api/memory/embeddings` | settings or derived server projection | `web/app.py:1514` |
| POST | `/api/memory/embeddings/rebuild` | settings or derived server projection | `web/app.py:1529` |
| GET | `/api/nsfw` | settings or derived server projection | `web/app.py:2080` |
| PUT | `/api/nsfw` | settings or derived server projection | `web/app.py:2084` |
| GET | `/api/openrouter/endpoints` | settings or derived server projection | `web/app.py:1648` |
| PUT | `/api/openrouter_routing` | settings or derived server projection | `web/app.py:1634` |
| POST | `/api/personas` | reusable persona records | `web/app.py:2768` |
| POST | `/api/personas/generate` | reusable persona records | `web/app.py:2746` |
| POST | `/api/personas/import` | reusable persona records | `web/app.py:2788` |
| DELETE | `/api/personas/{pid}` | reusable persona records | `web/app.py:2820` |
| PUT | `/api/personas/{pid}` | reusable persona records | `web/app.py:2811` |
| GET | `/api/personas/{pid}/export` | reusable persona records | `web/app.py:2802` |
| POST | `/api/personas/{pid}/fill_appearance` | reusable persona records | `web/app.py:2716` |
| PUT | `/api/prompt_presets` | settings or derived server projection | `web/app.py:1734` |
| POST | `/api/prompt_presets/import` | settings or derived server projection | `web/app.py:1770` |
| DELETE | `/api/prompt_presets/{name}` | settings or derived server projection | `web/app.py:1784` |
| GET | `/api/prompt_presets/{name}/export` | settings or derived server projection | `web/app.py:1761` |
| POST | `/api/providers` | provider/model configuration | `web/app.py:2464` |
| DELETE | `/api/providers/{pid}` | provider/model configuration | `web/app.py:2543` |
| PUT | `/api/providers/{pid}` | provider/model configuration | `web/app.py:2471` |
| GET | `/api/providers/{pid}/image_models` | provider/model configuration | `web/app.py:2555` |
| GET | `/api/providers/{pid}/models` | provider/model configuration | `web/app.py:2548` |
| PUT | `/api/providers/{pid}/prompt_cache` | provider/model configuration | `web/app.py:2498` |
| PUT | `/api/reasoning_effort` | settings or derived server projection | `web/app.py:1660` |
| POST | `/api/steps/{sid}/activate` | settings or derived server projection | `web/app.py:5817` |
| POST | `/api/steps/{sid}/edit` | settings or derived server projection | `web/app.py:5807` |
| POST | `/api/steps/{sid}/reroll` | settings or derived server projection | `web/app.py:5760` |
| DELETE | `/api/turns/{tid}` | turn/step/narration records | `web/app.py:5830` |
| GET | `/api/turns/{tid}/ambience` | turn/step/narration records | `web/app.py:6120` |
| POST | `/api/turns/{tid}/ambience` | turn/step/narration records | `web/app.py:6137` |
| GET | `/api/turns/{tid}/backdrop` | turn/step/narration records | `web/app.py:5967` |
| POST | `/api/turns/{tid}/backdrop` | turn/step/narration records | `web/app.py:5982` |
| POST | `/api/turns/{tid}/branch` | turn/step/narration records | `web/app.py:5084` |
| PUT | `/api/turns/{tid}/input` | turn/step/narration records | `web/app.py:5492` |
| GET | `/api/turns/{tid}/narration` | turn/step/narration records | `web/app.py:5577` |
| POST | `/api/turns/{tid}/narration` | turn/step/narration records | `web/app.py:5598` |
| GET | `/api/turns/{tid}/pipeline` | turn/step/narration records | `web/app.py:5622` |
| PUT | `/api/turns/{tid}/prose` | turn/step/narration records | `web/app.py:5507` |
| POST | `/api/turns/{tid}/reroll` | turn/step/narration records | `web/app.py:5691` |
| POST | `/api/turns/{tid}/rerun` | turn/step/narration records | `web/app.py:5701` |
| POST | `/api/turns/{tid}/resume` | turn/step/narration records | `web/app.py:5728` |
| GET | `/api/ui` | UI language-pack projection | `web/app.py:3125` |
| PUT | `/api/ui-language` | UI language-pack projection | `web/app.py:3150` |
| GET | `/api/updates/check` | settings or derived server projection | `web/app.py:2147` |
| POST | `/api/updates/install` | settings or derived server projection | `web/app.py:2151` |
| GET | `/guest` | settings or derived server projection | `web/app.py:547` |
| GET | `/login` | settings or derived server projection | `web/app.py:573` |
| POST | `/login` | settings or derived server projection | `web/auth_routes.py:208` |
| POST | `/logout` | settings or derived server projection | `web/auth_routes.py:274` |
| POST | `/setup` | settings or derived server projection | `web/auth_routes.py:133` |
| GET | `/status` | settings or derived server projection | `web/auth_routes.py:123` |
| GET | `/ui-next` | settings or derived server projection | `web/app.py:560` |
