# Audit: `web/app.py` (8,328 lines), 2026-11-01

Auditor scope: the whole file. The branch/clone ID-remap internals (`_remap_cp_blob`, `_build_world_id_remap`, `_deep_remap_ids` and siblings) were read for control flow only. Their persistence matrix belongs to another auditor and is not repeated here.

Scratch artefacts (all under `<review scratch>/webapp_audit/`):
- `routes.tsv` is the route inventory: line, method, path, function, sync/async, guards reached, writes reached. It covers all 230 `@app.*` routes, built by `routes.py`.
- `repro_disconnect.py` and `repro_disconnect_control.py` cover F1.
- `repro_liblink.py` covers F2.
- `repro_chardel.py` covers F3.
- `repro_openapi.py` covers F16.
- `repro_lang502.py` covers F14.
- `repro_codes.py` covers F15.
- `count_chat_get.py` produced the SQL statement counts.
- `route_overlap.py` checks registration-order overlaps.

Every snippet ran on a fresh scratch SQLite file under that directory. Nothing touched `engine.db`, except two read-only `mode=ro` counts.

## Scope read

**Read in full:** `web/app.py` lines 1–8328, in sequential chunks.

**Read in part, to trace a specific path (not audited):**
- `persist/checkpoints.py`: `_snapshot_lore` 112–186, `_restore_books` 382–527, `restore_checkpoint` 641–686, `_restore_chat_personas` 727–738, the chat_chars/char_frames restore 1176–1235, `PRESERVED_SETTING_KEYS` 986–1027, `refresh_checkpoint` 1862–1902, `propagate_memory_summaries_to_checkpoints` 1720–1772, compaction 1598–1648.
- `persist/chat_archive.py`: 260–340, router and export head.
- `agents/runtime.py`: `STEP_LABELS` 355–384, the `build_plan` excerpt 1092–1106, the `_restore_and_refresh` docstring 1565–1585, `run_pipeline` 2103–2195.
- `agents/offscreen_beat.py`: 255–300.
- `persist/commit_background.py`: the `promote_background_character` docstring 4929–4950.
- `world/charter_runtime.py`: `generate_lived_location` 1902–1975, `clear_lived_location_job` 523–527, `charter_speaker_records` 5663–5695.
- `extension_runtime/__init__.py`: `dispatch_route`, `activate`, `enabled_ids`.
- `extension_runtime/api.py`: 2335–2375, 2444–2490.
- `web/auth_routes.py`: 30–60. `web/world_routes.py`: 355–385. `web/guest_access.py`: `redeem_code`.
- `core/db.py`: `conn`/`transaction`/`q`/`qi`, `get_setting`, schema excerpts.
- `mind/memory_vectors.py`: `embedding_bank_status`. `llm/providers.py`: `embed_texts_meta`. `mind/memory_snapshot.py`: `prepare_chat_memory_restore`.
- `static/js/chat.js`: `openChat`, `runStream`, reroll/delete/narration-variant UI. Also `static/guest.html` 130–150, `static/js/editors.js` 920–955, `static/js/lorebooks.js` 1430–1480, and the `static/js/settings.js` dialogue panel.
- Installed `starlette/responses.py` (`StreamingResponse`), `anyio` `WorkerThread`, and the uvicorn `spec_version`.

**Tests run:** `tests/test_detached_turn.py` (7 passed). I ran no other test files; the repro snippets above stand in for them.

## Findings

Severity counts:

| Severity | Findings |
|---|---|
| LEAK | 1 (F4) |
| CORRUPTION | 8 (F2, F3, F6, F8, F9, F10, F11, F12) |
| WRONG-SCENE | 2 (F7, F13) |
| CRASH / availability | 4 (F1, F5, F14, F15) |
| STALE-DOC | 3 (F17, F18, F20) |
| DEAD / duplicate | 1 (F19) |
| Other: auth surface | 1 (F16) |

### F1 — A client that disconnects mid-turn freezes the whole server until the turn finishes

**Severity:** CRASH (availability). **Confidence:** CONFIRMED.

`web/app.py:978-998`, inside `_stream`:
```python
        try:
            if notice:
                yield json.dumps(notice) + "\n"
            while True:
                evt = evt_queue.get()
                ...
        finally:
            thread.join()
    return StreamingResponse(w(), media_type="application/x-ndjson")
```

**How it fails.** Starlette drives `w()` through `iterate_in_threadpool`. When the client goes away, the response task is cancelled. Uvicorn 0.35 reports ASGI `spec_version` 2.3, so Starlette's `listen_for_disconnect` task group handles this. The `iterate_in_threadpool` async generator is then torn down on the event-loop thread. That drops the last reference to `w()`, which closes it, and the `finally: thread.join()` runs on the event loop. The join waits for the drain thread, which runs the whole remaining pipeline. Until the turn commits, every other request hangs: other chats, polling, `GET /`, the guest page.

**Triggers.** Reloading, closing or navigating away from the tab mid-turn. A laptop sleep or network blip. A tunnel or proxy idle timeout. F17 makes the last one more likely: a scenario chat's first submission sends no bytes during the opening.

**How it was verified.** `repro_disconnect.py` calls the real `web.app._stream` as an ASGI app in-process (no server) with a generator of 15 events at 0.2 s each. The client disconnects after the first chunk. A 50 ms heartbeat task on the same loop measured:
- Disconnect, bare route: max event-loop stall **2.51 s**.
- Disconnect, through `BaseHTTPMiddleware` and the gzip middleware (the production stack): **2.30 s**.
- Control with no disconnect (`repro_disconnect_control.py`): max stall **0.09 s**.

The stall equals the pipeline's remaining run time. No test covers a disconnect. `tests/test_detached_turn.py` mentions it only in its docstring.

**Fix.** Do not join on `GeneratorExit`. Catch it and return; the drain thread already finishes the run on its own and releases the slot in `run_pipeline`'s `finally`. Keep the join, if wanted, only after `DONE` was dequeued.

**Test shape.** Drive `app._stream(slow_gen())` with a synthetic disconnect and assert the loop heartbeat never stalls more than about 0.3 s. The repro script is that test.

### F2 — One story's reroll deletes, or brings back, links between LIBRARY lorebooks for every story

**Severity:** CORRUPTION. **Confidence:** CONFIRMED.

The write happens in `persist/checkpoints.py:512-527` (`_restore_books`), reached from every rewind route in this file (`turn_reroll`/`turn_rerun`/`turn_resume`/`step_reroll` through `run_pipeline`, and `turn_del` at `web/app.py:7876`):
```python
    managed_ids = sorted(set(old_to_new.values()))
    if managed_ids:
        ...
            f"DELETE FROM lorebook_links "
            f"WHERE source_book_id IN ({placeholders}) "
            f"AND target_book_id IN ({placeholders})",
    restore_lorebook_links(chat_id, old_to_new, links or [])
```

`old_to_new` deliberately maps library references (`checkpoints.py:408`, "map the snapshot id onto it so links follow", assigned at `:433`). So a link between two library books counts as "snapshot-owned". The snapshot itself says library state "is not this snapshot's business" (`checkpoints.py:147-152`).

**How it fails.** The host links library books A→B with `POST /api/lorebooks/{A}/links` (`web/app.py:3126`), a library-wide edit. Any story that has both books attached, and whose latest checkpoint predates the link, then rerolls or deletes its latest turn. The link is deleted for every story. The reverse also holds: a library link deleted after a checkpoint is re-inserted by that story's reroll.

**How it was verified.** `repro_liblink.py`: two library books attached to two chats, a checkpoint, `add_lorebook_link(A, B)`, then `restore_checkpoint(chat, 0)`. Links before: `[(1, 2)]`. After: `[]`.

**Fix.** Manage, snapshot and restore only links with at least one chat-owned endpoint. Exclude `library_kept` ids from `managed_ids` and from `dump_lorebook_links(book_ids)` in `_snapshot_lore`. This is the persist side; the app routes need no change.

**Test shape.** The repro, plus the inverse case: a deleted library link is not resurrected.

### F3 — Deleting a library character permanently breaks rewinds and branches of multi-frame stories that used them

**Severity:** CORRUPTION and CRASH. **Confidence:** CONFIRMED.

`web/app.py:3844-3848`:
```python
@app.delete("/api/characters/{cid}")
def char_del(cid: int):
    qi("DELETE FROM characters WHERE id=?", (cid,))
    qi("DELETE FROM chat_chars WHERE char_id=?", (cid,))
```

The FK cascade already removes `chat_chars`, `memories` and `chat_char_frames`, so the second statement is redundant. Checkpoint blobs keep `char_frames` rows for the character. Two inserts replay them unfiltered:
- `persist/checkpoints.py:1215-1220` inserts `chat_char_frames` from `b["char_frames"]`.
- `turn_branch` at `web/app.py:7134-7144` does the same from `blob["char_frames"]`.

`chat_char_frames.char_id` is `REFERENCES characters(id)`, so both inserts raise `IntegrityError` and the whole restore or branch rolls back.

The class is already handled elsewhere. Memories filter through `surviving_character_ids()` and `_restore_chat_personas` skips deleted personas (`checkpoints.py:732-736`). Its comment says it is "mirroring the chat_char_frames restore just above it", which does not filter.

**How it fails.** A multi-frame story has a character with a per-era override row. The host deletes the character from the library. The UI warns only "Delete character?" (`static/js/app.js:897`), not "removed from every story with all their memories". From then on:
- Reroll, rerun, resume and delete of that story's latest turn return 500.
- Branching from any turn whose checkpoint holds the row returns 500, permanently.

A turn running in any story with that character also loses its commit (memory insert FK failure, so the whole turn rolls back).

**How it was verified.** `repro_chardel.py`: chat, character, frame, `chat_char_frames` row, `ensure_checkpoint`, then the route's two DELETEs, then `restore_checkpoint`. Result: `restore FAILED: IntegrityError FOREIGN KEY constraint failed`.

**Fix.** Filter `char_frames` by `surviving_character_ids()` at both inserts, as memories already are. Separately, consider refusing or warning on `char_del` while the character is attached to stories (owner's call).

**Test shape.** The repro, asserting the restore succeeds and the row is dropped. A twin goes through `turn_branch`.

### F4 — The guest page shows a character's true name in the "superseded" note

**Severity:** LEAK (player-facing slice). **Confidence:** path CONFIRMED by reading; trigger PLAUSIBLE.

`web/app.py:5320-5335` (`guest_state`):
```python
        earliest = min(rows, key=lambda r: r["ord"]) if rows else None
        turns.append({ ...
            "stale_from": {"ord": earliest["ord"], "key": earliest["key"],
                           "label": earliest["label"]} if earliest else None,
```

Step labels for parallel character steps are `"Character · {name}"`, using the character's true name. That comes from `agents/runtime.py:362`, applied at `:1101-1103` when autonomy is 0 and the beat is uncontested. `static/guest.html:141-146` renders it verbatim: `Partly out of date — steps from “Character · Mirelle” onward were not recomputed.`

**How it fails.** A guest plays a persona that has not learned Mirelle's name; its `narrator_extra` prose says "the hooded woman". The host, on a story at autonomy 0, edits or activates a variant of `perception_act` on the latest turn. Downstream steps are marked stale, so the earliest stale step is `character:<id>`. The guest's 10-second poll then prints the name. The same class shows in `chat_name` (and `join_with_code`'s `chat_name`): greeting quick starts title the story `"<Character> — <Persona>"` (`story/greetings.py:886`).

The host-side `chat_get` sending labels is fine; the host is the author.

**How it was verified.** Traced `step_label` → `steps.label` → `guest_state` → `guest.html`. I did not run it live.

**Fix.** Send the guest a phase name with no cast fields, e.g. `STEP_LABELS[key.split(":")[0]]` unformatted ("Character"). Decide separately whether the story title is persona-safe.

**Test shape.** Mark a `character:N` step stale and assert the name is absent from the `guest_state` JSON.

### F5 — Extension routes run synchronously on the event loop

**Severity:** CRASH (availability) / PERF. **Confidence:** CONFIRMED by trace.

`web/app.py:2912-2936`:
```python
@app.api_route("/api/extensions/{eid}/x/{path:path}", methods=[...])
async def extension_route(eid: str, path: str, request: Request):
    ...
        result = extension_runtime.dispatch_route(
            _extension_id(eid), request.method, path, query=..., body=body)
```

FastAPI only moves `def` endpoints to the threadpool; an `async def` runs on the loop. `dispatch_route` (`extension_runtime/__init__.py:1514-1542`) does the following on the loop thread:
- calls `activate()`, which reads settings and possibly scans for extensions;
- calls the extension's handler synchronously.

Handlers can do heavy work. The bundled `campaign-demo` `/start` calls `api.provision_story` (a whole archive import in a transaction). `api.generate_lived_location` is documented "SYNCHRONOUS, AND IT IS NOT QUICK … minutes" (`extension_runtime/api.py:2455`). While that runs, every request to the server waits. It also does all its DB work on the loop thread's own connection.

**Fix.** `result = await run_in_threadpool(extension_runtime.dispatch_route, ...)` (Starlette's helper, which copies contextvars). Keep the `await request.json()` as is.

**Test shape.** An extension route that sleeps 1 s, plus a concurrent `GET /api/nsfw`, asserting the second answers in under 0.2 s.

### F6 — `confirm_promotion` writes cast, scene and presence state with no idle guard

**Severity:** CORRUPTION / WRONG-SCENE. **Confidence:** PLAUSIBLE.

`web/app.py:4966-4997` calls `promote_background_character(...)` under `_era` only. Its sibling `chat_add_char` holds `_require_chat_idle` (`:4843-4846`) "because attaching mid-turn seeds attire and positions into a scene the pipeline is about to overwrite". The promote writer's own docstring says its writes "stay in the turn thread because the turn rewrites `scene`, `background_presences` and `known` wholesale" (`persist/commit_background.py:4944-4948`). The commit also prepares its scene before taking the write lock (`persist/commit.py:573`).

**How it fails.** The host confirms a promotion while a beat runs; the UI gates nothing (`static/js/editors.js:945`). The new chat_chars row lands, but the turn's commit overwrites the scene from its pre-lock preparation. Her position is lost, and the presence record can be re-recorded beside the new cast member, so one person exists twice.

**Fix.** `_require_chat_idle(cid)` (or `_require_frame_idle` for the era) at the top, like `chat_add_char`.

**Test shape.** With a fake `ABORTS` slot held, assert 409.

### F7 — The `since_turn_id` slice permanently strands a turn that was in flight at the previous read

**Severity:** WRONG-SCENE (render). **Confidence:** PLAUSIBLE.

`web/app.py:4668-4673` slices by `turns.id > since`. The events and stale queries (4628-4656) do the same. The docstring (4526-4547) argues "THE TRANSCRIPT … ONLY EVER GROWS AT THE END". But turn rows are inserted when a beat starts, not when it commits. This is true for off-screen beats (`agents/offscreen_beat.py:283-285`) and for any concurrent frame.

**How it fails.** The client computes `heldTurnId` as the max id it holds (`static/js/chat.js:1353-1358`) and splices (`:171-173`):
1. The player's beat P1 commits and schedules a bubble beat B1, whose row (id 101) exists with empty prose.
2. The post-beat refresh (since=99) returns P1 and B1, B1 still blank.
3. The next beat's refresh uses since=101, which excludes B1.

B1's prose, speech and stale flags are never re-read until a whole reload or story switch. Switching to the bubble's frame (a client-side filter) shows it blank.

**How it was verified.** Traced the server slice, the client splice and the off-screen row insertion. I did not run it live; it depends on timing.

**Fix (server side).** Also return every turn whose commit landed after the since-turn's commit (`commit_seq > (SELECT commit_seq … WHERE id=since)`). Alternatively, have the client send the lowest id it holds without a commit.

**Test shape.** Turn A committed, turn B uncommitted, read with since=A; then commit B, add C, read with since=B. Assert B's prose is returned.

### F8 — Chat export takes no guard and no snapshot, and the guard's docstring says it does

**Severity:** CORRUPTION (PLAUSIBLE) / STALE-DOC (CONFIRMED).

`_require_chat_idle`'s docstring (`web/app.py:725-729`) says it is "Used for every operation that isn't safely frame-local … branch, export/import". `persist/chat_archive.py` has no idle check (grep finds no `running_frames`, `ABORTS` or `_require`). `export_chat` (281-340) issues about 15 separate autocommit `SELECT`s, including per-turn, per-step and per-variant loops.

**How it fails.** The host exports while a beat commits; off-screen beats run unprompted. The turn, steps and world rows can come from opposite sides of the commit. That gives an archive whose world is after turn N but whose turn N lacks its narrator or commit step, and an import reproduces the torn state.

**Fix.** Read the export inside one read transaction (`BEGIN` on the reading connection), or refuse while running. Fix the docstring.

**Test shape.** Interleave a commit between two export reads, using a monkeypatched hook in `export_chat`.

### F9 — `POST /api/chats/{cid}/lorebook {"lorebook_id": null}` unbinds canon without carrying it into checkpoints

**Severity:** CORRUPTION. **Confidence:** CONFIRMED by trace.

`web/app.py:4488-4493`:
```python
    src = body["lorebook_id"]
    if not src:
        qi("UPDATE chats SET lorebook_id=NULL WHERE id=?", (cid,))
        return {"lorebook_id": None}
```

Its twin `detach_lore` (`:4506-4511`) runs the same UPDATE and then `_refresh_rewindable_checkpoints(cid)`. The restore re-binds the snapshot's canon (`persist/checkpoints.py:505-508`), so the next reroll silently undoes the unbind. The null path is a pinned, supported API (`tests/test_app_audit_transactionality.py:332-336`); the UI uses DELETE, so only API and extension callers hit it.

**Fix.** Call `_refresh_rewindable_checkpoints(cid)` before returning, or delegate to `detach_lore`.

**Test shape.** Bind, checkpoint, unbind via the null path, restore, and assert `lorebook_id` is NULL.

### F10 — Changes to a story's retrieval reach survive a reroll for attach/enable/detach, but not for links or moves

**Severity:** CORRUPTION (class inconsistency). **Confidence:** CONFIRMED by trace.

`_refresh_rewindable_checkpoints` (`web/app.py:1036-1061`) exists because "Retrieval is snapshotted with the turn, so the checkpoint has to move with the books or a rewind restores the old reach". It is called from attach, enable, detach, bind and unbind only (4432, 4466, 4479, 4503, 4510).

The following routes change reach for the story's own books but never refresh:
- `lorebook_link_create`, `lorebook_link_update`, `lorebook_link_delete` (3126-3165), where `follow_for_retrieval` and `weight` are reach.
- `lorebook_move` and `lorebook_reorder` (3048-3064), where parent and inheritance are reach.

The restore puts parents (`checkpoints.py:473`), links (512-527) and entries (466) back. So a host who links two of the story's books and rerolls loses the link. That is the exact symptom the attach refresh was written for ("attaching a book after Tamamo's beat, then rerolling the page, detached it again").

The reroll confirm (`static/js/chat.js:1407-1421`) says "lorebook edits" are reverted, which is untrue for attachments and true for links. This needs the owner's ruling on which lorebook edits are configuration (carried) and which are story facts (reverted), stated once.

**Test shape.** Link two chat-owned books after a checkpoint, reroll, assert the link survives (or the documented opposite).

### F11 — Two writers accept a frame id that is not the chat's

**Severity:** CORRUPTION (low). **Confidence:** CONFIRMED by reading.

- `charters_generate` (`web/app.py:6160-6179`) passes the query `frame_id` straight to `generate_lived_location`, which never validates it (`world/charter_runtime.py:1902-1935`). Its sibling `charters_put` validates through `_era`, and the extension twin calls `_validate_frame` (`extension_runtime/api.py:2479`).
- `_story_overlay_edit` (`web/app.py:4147-4168`) passes `body["frame_id"]` to `set_lore_overlay`. The FK only checks that some frame exists, so another chat's frame is accepted.

**How it fails.** `POST /api/chats/1/charters/generate?frame_id=<chat 2's frame or a future id>` plants frame-scoped `world` rows keyed to a frame chat 1 does not have. Frame ids are global and reusable as max+1, so a later frame can inherit them.

**Fix.** Call `_frame_of(cid, frame_id)` first in both. This is one rule: a frame id from a request is validated where it enters.

### F12 — The "interrupted generation" escape hatch is only reachable over raw HTTP, and it clears a live job

**Severity:** SILENT-NOOP / CORRUPTION (low). **Confidence:** CONFIRMED by reading.

`GET` and `DELETE /api/chats/{cid}/charters/job` (`web/app.py:6182-6215`) have no caller in `static/`, `tests/` or `tools/` (grep). Yet the refusal a host actually sees tells them to "clear the job (DELETE /api/chats/<id>/charters/job)" (`world/charter_runtime.py:1960-1963`). That request needs the host session cookie; no button sends it.

`clear_lived_location_job` (`charter_runtime.py:523-527`) wipes the job unconditionally. Clearing while a generation is live in-process removes the only thing the "A LIVE ONE" guard (1964ff) reads, which permits a second concurrent town.

**Fix.** Add a UI affordance (or have the refusal offer one). Refuse to clear a job whose owner is this process and whose status is `running`.

### F13 — `turn_narration_select` lacks the turn-idle guard its sibling holds for the same race

**Severity:** WRONG-SCENE (low). **Confidence:** CONFIRMED (missing guard); consequence PLAUSIBLE.

`web/app.py:7559-7584` checks only `_require_latest(turn, later_only=True)`. `edit_prose` (`:7472-7482`) names this race and guards it with `_require_turn_idle`: "Whichever `UPDATE variants SET active=0` lands second wins, and the edit either vanishes or silences the beat the pipeline just produced".

**How it fails.** A select issued while a reroll of the same turn runs (second tab, or an out-of-process client) can re-activate an old rendering after the run wrote its new one. The in-tab UI blocks this with `S.busy` (`chat.js:1273`).

**Fix.** `_require_turn_idle(turn)`.

**Test shape.** Hold the frame slot and assert 409.

### F14 — Six routes turn their own 400 into a 502 "generation failed"

**Severity:** CRASH-class error reporting (low). **Confidence:** CONFIRMED.

`_require_story_language` raises `HTTPException(400)` inside a `try` whose `except Exception` re-raises 502:
- `_psychology_fill` 3696-3703
- `_interior_fill` 3730-3738
- `_appearance_fill` 3772-3784
- `char_generate_greeting` 3684-3688
- `lorebook_generate_plan` 3171-3190
- `lore_reinterpret_route` 4069-4073 (theoretical)

**How it was verified.** `repro_lang502.py`: `_require_story_language -> 400`; `_psychology_fill -> 502 Psychology fill failed: 400: language pack 'zz-nope' is not installed`. The same holds for `_interior_fill` and `_appearance_fill`.

**Fix.** Resolve the language before the `try`, or add `except HTTPException: raise`.

### F15 — One missing-resource condition gets 404, 500 or 200 depending on the route

**Severity:** CRASH (500s). **Confidence:** CONFIRMED.

`repro_codes.py` results:

| Routes | Response for a missing chat or resource |
|---|---|
| `style_guide_put`, `bg_cfg_put`, `frames_create` | unhandled `IntegrityError` → 500 |
| `chat_get` | 404 |
| `dlg_get` | 200 with defaults |
| `char_edit`, `persona_edit` | 200 `{"ok": true}`, nothing written |
| `mem_del`, `chat_del` | 200 |

Unchecked `wset` callers also hit the FK 500: `dlg_put`, `living_world_put`, `pph_put` and `naming_profile_put` (`world.chat_id REFERENCES chats`).

**Fix.** A shared `_chat_or_404(cid)` (`web/world_routes.py:359` already has one) at the head of every chat-scoped writer, and 404 on zero-row updates for `char_edit` and `persona_edit`.

### F16 — FastAPI's `/openapi.json`, `/docs` and `/redoc` are public

**Severity:** auth surface, not firewall (low). **Confidence:** CONFIRMED.

`app = FastAPI(title="Sonder Engine", version="1.0", lifespan=lifespan)` (`web/app.py:407`) keeps the default docs routes. `access_control` (696-716) gates only `/api/*`.

`repro_openapi.py` with no cookie:
- `/api/chats`: 401
- `/openapi.json`: 200, listing 214 paths
- `/docs`: 200
- `/redoc`: 200

That gives any peer that can reach the port (the startup banner warns about LAN binds and tunnels) the full route and parameter inventory. No document mentions these routes.

**Fix.** `FastAPI(..., docs_url=None, redoc_url=None, openapi_url=None)`, or gate them in `access_control`.

**Test shape.** Enumerate `app.routes` and assert every non-allowlisted path starts with `/api/`.

### F17 — `turn_new`'s "answers at once" (detach) is false on a scenario chat's first submission

**Severity:** STALE-DOC plus latency. **Confidence:** CONFIRMED by reading.

The docstring (`web/app.py:6670-6676`) promises `?detach=1` answers `{"turn_id", "running": true}` "at once". Lines 6755-6761 first run `_plan_opening` (a Story Planner model call) and, when the first line is a beat, `_run_the_opening` (the whole turn-0 pipeline, events discarded) inside the request. On the streamed path the client receives no bytes for that whole time, and a disconnect then feeds F1.

**Fix.** Run the opening inside the drain thread: a generator that yields the opening's events, then the player's turn. Or document the wait.

### F18 — `_shutdown_engine` says "Daemon threads mean nothing HANGS", but pipeline threads are not daemons

**Severity:** STALE-DOC. **Confidence:** CONFIRMED by reading.

`_drain_on_own_thread` creates `threading.Thread(target=lambda: context.run(run))` (`web/app.py:907-909`) without `daemon=`. Daemon status is inherited, and AnyIO's `WorkerThread` (`anyio/_backends/_asyncio.py:981-990`) is non-daemon. The shutdown (357-395) neither aborts nor tracks these threads.

The result: Ctrl-C, or a `make run` reload, waits for every in-flight turn (minutes) after the lifespan has already "finished". Whether to abort with a bounded join or to wait for the commit is the owner's call; the docstring should say which.

### F19 — Dialogue-colour resolution is written twice

**Severity:** DEAD / duplicate. **Confidence:** CONFIRMED.

`chat_get` (4583-4606) inlines the same cast resolution and Charter-speaker loop, with the same swallow, as `_resolved_dialogue_colors` (5772-5801). That is two copies free to drift. `chat_get` should call the helper with the rows it already read.

### F20 — `_INSTALL_BLOCK_KEYS` omits `attire_opt_in_zones`

**Severity:** STALE-DOC / PERF (low). **Confidence:** CONFIRMED.

The stated class (1785-1801) is "a value that changes only when the installation changes". `attire_opt_in_zones` (1978-1979, from `attire.OPT_IN_ZONES`) is install-constant but was left out of the frozenset (1802-1812). It is re-sent in the variable half on every boot.

## Efficiency

**E1 — Every post-beat refresh makes an embedding-provider network round trip.** `chat_get` → `embedding_bank_status(chat_id=cid)` (`web/app.py:4776-4784`) → `embed_texts_meta(["status"], retry=None)` (`mind/memory_vectors.py:64`). That call skips every cache and memory: "it alone asks the wire every time" (`llm/providers.py:5838-5846`).
- Hotness: the client calls `openChat` after every run (`static/js/chat.js:1393`), on every story open, and after every edit.
- Cost: one provider round trip, billed, per beat. With the endpoint down, each refresh waits for the connect failure.
- Gain: skip the probe when `since_turn_id` is set. The docstring and Design.md describe it as a chat-open check.

**E2 — `turn_branch` holds the global write lock for the whole copy.** Inside `with transaction()` (6963-7430) it runs per-turn, per-step and per-variant SELECT and INSERT loops, then `json.loads`, `_remap_cp_blob` and `json.dumps` over every checkpoint up to idx.
- Measured read-only on the largest chat (64): 171 turns, 1,535 steps, 2,002 variants (about 5.6k statements); 171 checkpoints, 227 MB (avg 1.3 MB, max 3.3 MB).
- `json.loads`+`json.dumps` alone took **4.1 s**, before the remap and before writing 227 MB.
- Effect: every other writer in the process (other chats' commits, `qi` from any route, backdrop and ambience jobs) blocks on `_write_lock` for that long.
- Gain: parse source blobs before taking the lock (the chat is idle-gated); use `INSERT … SELECT` for steps and variants per turn. That saves seconds of global lock per branch of a long story.

**E3 — Extension routes run on the event loop.** See F5.

**E4 — `bootstrap()` rebuilds and re-hashes the 767 KB install half on every boot,** even when `known_install` matches (`bootstrap_response` 1895-1906). The code's own bench puts the build at 29.7 ms, and `boot()` has 61 call sites. The same pass reads 45 statements, including `jev_url` ×4 and `jev_provider` ×3 (counted with `count_chat_get.py`). Gain: cache `(install_json, version)` keyed on the UI language and the pack/prompt fingerprint.

**E5 — `chat_get` costs 62 SQL statements on a toy chat** (2 characters, 5 books, 5 turns), and 61 on the `since` slice. The slice saves bytes, not queries. The cost is about 9 statements per book:
- the `chat_lorebook_ids` graph walk (links ×2, parent and children, chat_id per book);
- `chat_get`'s own per-book `SELECT * FROM lorebooks` and `chat_lorebooks` (4706-4720);
- `agent_models` read 4 times.

The cost grows with books, not turns. It is small per call (milliseconds), but it runs every beat. Gain: one JOIN for the book list, and pass one `agent_models` read through.

**E6 — Recompute gates compute `beat_order.rewind_plan` two to four times per request:** `_require_latest` 1115, `_require_rewindable` 1137, `turn_del` 1855 and `decide` 1861. `edit_input` and `pipeline_get` compute it again. Small, but avoidable: pass the plan down.

**E7 — `turn_del` deletes variants one step at a time** (7878-7885). One `DELETE … WHERE step_id IN (SELECT id FROM steps WHERE turn_id=?)` does it. Trivial.

**E8 — `bootstrap()` builds providers one at a time:** `_provider_public` runs a `SELECT *` and five predicate calls per provider (1929, 3295-3317). Trivial at today's counts.

## Already registered

- **UNBUILT_IDENTITY §1.104** (persona has no per-story copy). `persona_edit` (`web/app.py:3916-3923`) renames or edits the player in every story at once. It has none of the identity protection `char_edit` (3827-3836) and `chat_char_card_put` (5419-5427) apply. `persona_del` (3925-3928) has the same root: stories fall back to "The Stranger", and positions keyed by the old name are orphaned.
- **UNBUILT_PIPELINE §1.183** (a no-scenario chat's first line is unanswerable). That is the remaining half of the `turn_new` opening split, and it is related to F17's synchronous opening.

## Structure notes

### Answers to the assignment's questions

**(1) Auth on every route.** No route uses `Depends`. The single gate is the `access_control` middleware (696-716), keyed on `request.url.path`:

| Path class | Who may call | Status |
|---|---|---|
| `/api/*` | host session cookie | gated |
| `PUBLIC_API_PATHS` (`/api/join`, `/api/ui`, `/api/auth/{status,setup,login,logout}`) | anyone | intended |
| `GUEST_ALLOWED_API_PATHS` (`/api/guest/state`, `/api/guest/input`) | guest cookie only; a host gets 403 "Guest session required" | intended |
| `/`, `/login`, `/guest`, the `/static` mount | anyone | intended |
| `/openapi.json`, `/docs`, `/docs/oauth2-redirect`, `/redoc` | anyone | a gap (F16) |

The app holds 268 routes: 230 in `web.app`, 23 in world_routes, 5 in room_routes, 4 in auth, 2 in the archive service, 4 FastAPI docs.
- **Guests cannot reach any host mutation.** The allowlist matches exact paths; `guest_state` and `guest_input` read only `request.state.guest_grant`.
- **The guest surface still leaks labels** (F4).
- **Guest input has no length cap and accepts any idx ≥ 0.** Each idx is one upserted row, so the table is unbounded but slow to fill. Hardening only.
- **No cross-chat ownership checks are needed.** The model is single-tenant: the host owns every chat. Sub-resource ids that cross chats are F11.
- **Split hazard: auth is a path prefix.** A route moved under any non-`/api/` prefix becomes public silently. Every path must stay byte-identical (see the test in F16).

**(2) `_begin_pipeline_or_409` and idle guards.** From `routes.tsv`:
- **Slot-claiming (atomic):** `turn_new`, `turn_reroll`, `turn_rerun`, `turn_resume`, `step_reroll`.
- **Chat-wide idle:** `chat_language_put`; `chat_edit` (persona change only); attach/enable/detach/bind/unbind lore; `chat_del`; `chat_add_char`; `chat_persona_station`; `chat_add_persona`; `chat_del_char`; `chat_char_card_put`; `survival_put`; `chat_char_position_put`; `ph_put`; `world_put`; `attire_put`; `turn_branch`; `edit_input` (with `allow=stop`); `step_edit`/`step_activate`/`turn_del` through `_require_rewindable`.
- **Frame-local:** `chat_begin`, `charters_put`, `charters_generate`.
- **Turn-local:** `edit_prose`.
- **Unguarded but should be:** `confirm_promotion` (F6) and `turn_narration_select` (F13).
- **Unguarded and fine:** the chat-scoped settings writers (`style_guide`, `dialogue_config`, `living_world`, `background_config`, `naming_profile`, `player_authority`, `paradox_policy`, `persona_private_history`, fixed points, ambience pins). These are `SET_BY_HAND` keys (`persist/checkpoints.py:916`): preserved across restores and never rewritten by the commit, so a mid-turn write only changes the later stages of that beat.
- **Unguarded, outside this file's turn model:** memory routes, lore routes, global settings, extension documents.
- **Hold no slot:** `turn_branch`, `turn_del` and step edits check idle once and claim nothing. `turn_del` re-decides under the lock; `turn_branch`'s comment "nothing runs while a branch is taken" (6939-6940) overstates this, because `turn_new` and the off-screen scheduler can start a beat during the branch. The effect is limited to an understated `commit_seq`.
- **Over-strict:** `edit_input` waits for every frame (except stop frames) even for an old turn, while `edit_prose` was relaxed to turn-local on 2026-10-13.

**(3) Streaming and cancellation.**
- **`_stream`'s `w()`:** it holds no DB connection or lock. The producer and client are decoupled by an unbounded `queue.Queue`, so a slow client only grows memory by the turn's events.
- **The defect is F1:** the `finally` join runs on the event loop after a disconnect. If `w()` never started (disconnect before the first chunk), close is a no-op and nothing stalls.
- **Pipeline exceptions:** `_drain_on_own_thread` turns them into a final `{"type":"error","fatal":true}` line, then a clean 200 end. That is the documented protocol.
- **`_detach`:** drops that line entirely (only logged), so `turn_status` can report "not running, not committed" but never why.
- **`json.dumps(e)` in `w()`:** uses the default `allow_nan=True`, so a NaN in any event would emit a non-JSON line. No instance found; note only.

**(4) One active variant; rerun checkpoints.**
- **One active variant per step holds on every path in this file:** `edit_prose`, `step_edit`, `step_activate` and `turn_narration_select` deactivate and activate in one transaction; `turn_branch` copies `active` verbatim; `turn_del` deletes.
- **Stale marking is not atomic with the swap:** in `step_edit`/`step_activate` the downstream stale marking and `_mark_applied_step_stale` run outside the swap's transaction (7817-7818, 7832-7833). A crash between them leaves an edit with unstaled downstream steps; that is the exact class `edit_prose`'s comment warns about.
- **Later checkpoints:**
  - **Rewind:** a rewind sweeps checkpoints above the restored turn in the restore's own transaction (`sweep_later`, `persist/checkpoints.py:1273-1279`).
  - **`turn_del`:** drops everything above the newest remaining idx (7896-7900).
  - **What can go:** only discarded lineage (taken-back off-screen beats, a branch-written idx+1).
- **What the UI warns:** the reroll confirm warns that world, memories, lorebooks and cast revert (`chat.js:1407-1421`; partly untrue, see F10). The delete confirm says only "Delete last turn?". Off-screen beats taken back are announced after the fact (`chat.js:730-733`, `1018`).

**(5) Settings caching and races.**
- **Settings are read per request:** `get_setting` is one SELECT each, with no cache. `bootstrap()` costs 45 statements. `_bundle_revision_cache` caches only the static bundle's hash, keyed on mtime and size.
- **Benign race in `_bundle_revision`:** it writes `key` before `token` without a lock, so a concurrent request can serve the previous token once.
- **Global settings are read at every LLM call:** `agent_models`, efforts, formats, `max_output_tokens`, the active preset. A mid-turn PUT changes the rest of the running turn. That is by design, but there is no turn-level snapshot: e.g. an embeddings-role switch mid-turn writes the commit's memories under the new model.
- **`chat_language_put` is correctly guarded.**

**(6) Threads.**
- **`_RECONCILE_THREAD`:** daemon, named, joined for 1 s at shutdown. The `global` rebind is read only inside this module; tests patch and read it through the module object, which is a split hazard (below).
- **Pipeline drain threads:** non-daemon, unnamed, untracked, never aborted at shutdown (F18).
- **Started from request handlers:**
  - `start_rebuild_if_needed`: daemon `embedding-rebuild`.
  - `start_compaction`: unnamed daemon.
  - The embedding-repair daemon.

  None is drained at shutdown or tracked, which is the hazard the reconcile join was added for.
- **Reload does not double threads:** uvicorn's reloader starts a fresh process. It does, however, wait for in-flight pipeline threads (F18).

**(7) Error handling.**
- **Deliberate 200-with-error-body:** `memory_embeddings_status`, `maintenance_checkpoints`, `put_agent_models`' bank field, `chat_setup_log`'s turns, `_bootstrap_code`, `_bootstrap_extensions`, `_bootstrap_language`. All are documented non-fatal reporting.
- **Silent swallows in `chat_get`:** Charter colours (4602), repair queue (4774), bank (4783), instrumentation (4811). Also `_branch_protected_identity_ids`' persona read (1292); a failure there would let a branch rekey the player's position key.
- **Mis-coded:** F14 and F15.
- **Misattributed errors:** `lore_import` reports any non-reinterpret failure, including DB errors, as 400; `char_generate` and `persona_generate` report DB failures as 502 "generation failed".

**(8) Efficiency.** See the Efficiency section.
- **`chat_get`:** 8 direct `q()` sites, 2 of them in the per-book loop; 62 statements in total for a toy chat, plus one network probe.
- **JSON round-trips:** `chat_get` re-encodes every participant's sheet (`json.loads` → normalize → `json.dumps`) per call. Needed for the private-history override.
- **`world_get`:** `json.loads` every world row of the chat, then FastAPI re-encodes them. That could be spliced from stored text the way `_json_object_merge` does, but it is an editor surface.
- **`_JSON_WIRE`:** correct as used, a constant, never mutated.

### (9) The 20 top-level markers, plus one that is not a seam

| # | Lines | Marker | What it really holds | Proposed home |
|---|---|---|---|---|
| — | 1-173 | (import block) | `code_version.take_snapshot()` at 7 (must stay first); **`STATIC_ROOT` at 31, a computed constant inside the import block**; 2 mid-block import groups | facade, but see `STATIC_ROOT` below |
| 1 | 175-611 | App setup | reconcile thread, bind helpers, startup/shutdown, `lifespan`, **`app`**, gzip middleware + responder, `add_middleware`/`include_router`s, mid-file import + `_seat_story_planner()` side effect (599-601), `EXEMPLAR_*`, `/static` mount | `app_core` (leaf) |
| 2 | 612-718 | Host/guest access control | **mostly the shell:** `guest_page`, `_SHELL_ASSET_RE`, `_bundle_revision_cache`, `render_shell`, `index`, `login_page`; then `access_control` | `app_shell` |
| 3 | 719-1734 | Helpers | four concerns in 1,016 lines: guards (724-862), streaming (864-998), turn lookups and rewind gates (1000-1166), the remap family (1168-1680), resource/lore helpers (1681-1733); `import logging` at 720 is a mid-file import | `app_guards` (leaf), `app_stream`, `app_remap` |
| 4 | 1735-2672 | BOOTSTRAP & SETTINGS | also `turn_debug_export`, `chat_retry_start`, `chat_setup_log`, `chat_debug_export` (turn/chat routes) and the shared `_default_authoring_language`/`_require_story_language` | `app_settings`; the language helpers go to `app_guards` |
| 5 | 2673-2993 | Extensions | also the nsfw, affect-habituation and attire-beneath settings | `app_extensions`; the settings move to `app_settings` |
| 6 | 2994-3033 | Self-update | also the checkpoint-maintenance routes | `app_settings` |
| 7 | 3034-3292 | LOREBOOK TREE & LINKS | mid-file imports (3035-3046), `chat_lorebooks_owned`, `lore_import` | `app_lore` |
| 8 | 3293-3453 | PROVIDERS | `_provider_public` (also read by `bootstrap`) | `app_providers` (or `app_settings`) |
| 9 | 3454-3849 | CHARACTERS | also the story-launch routes `character_start_story`, `chat_prelude`, `chat_begin`, `_lived_location_llm_detail` | `app_cards`; launch routes go to `app_chats`; the helper to `app_guards` |
| 10 | 3850-3929 | PERSONAS | — | `app_cards` |
| 11 | 3930-4275 | LOREBOOKS | — | `app_lore` |
| 12 | 4276-4934 | CHATS | also the UI-language routes | `app_chats` |
| 13 | 4935-5176 | Background-presence promotion | also the irony/promise feeds, auto-promote, extra personas, co-player input | `app_chats` |
| 14 | 5177-6466 | Guest invites | **1,290 lines, mostly not guests:** cast cards, survival, vitals, positions, private history, colours, world editor, attire, style guide, dialogue config, living world, charters, background config, naming, story views, player authority, frames, paradox, fixed points, and the `_chat_archive_service` construction (6450-6465, another mid-file import) | guests go to `app_chats`; 5381-6448 to `app_story_state`; the archive service to `app_remap` |
| 15 | 6467-6666 | MEMORIES | — | `app_memories` |
| 16 | 6667-7516 | TURNS & PIPELINE | `turn_new` + opening helpers, `turn_status`, `chat_abort`, **`turn_branch` (6913-7437)**, `edit_input`, `edit_prose` | `app_turns`; `turn_branch` to `app_branch` (with or beside `app_remap`) |
| (16b) | 7181 | `# --- Lorebook Tree Cloning ---` | **indented inside `turn_branch`**. The anatomy counts it as a section marker; it is not a seam | — |
| 17 | 7517-7706 | Narration variants | also `pipeline_get`, `_perceiver_names`, reroll, rerun | `app_turns` |
| 18 | 7707-7902 | Pipeline resume endpoint | also step reroll/edit/activate and `turn_del` | `app_turns` |
| 19 | 7903-8064 | SCENE BACKDROPS | — | `app_media` |
| 20 | 8065-8314 | ROOM AMBIENCE | — | `app_media` |
| — | 8315-8328 | (tail) | `code_version.load_everything()` + `check()` | facade, **last**, after every sibling import |

**What must move down so no sibling imports the facade:**
- **`app_core`:** `app`; `_pipeline_logger`; `EXEMPLAR_MAX_*` (read by `bootstrap` and `put_exemplars`).
- **`STATIC_ROOT`:** it lives at line 31 inside the byte-for-byte import block. The facade keeping it gives two bindings, so test_host_surface_transport.py:111's patch of `app.STATIC_ROOT` goes inert for `render_shell`. The plan must decide this explicitly.
- **`app_guards`:** every guard and gate, `_player_input`, the language helpers, `_lived_location_llm_detail`, `_require_lorebook`/`_require_lore_entry`, `_ensure_resource_uid`, `_delete_book`, `_refresh_rewindable_checkpoints`, `_latest_turn*`.
- **`app_stream`:** `_DRAIN_DONE`, the drain functions.
- **`app_shell`:** `_bundle_revision_cache`, `_SHELL_ASSET_RE`.
- **`app_settings`:** `_JSON_WIRE`, `_INSTALL_BLOCK_KEYS`.
- **`app_media`:** `_BACKDROP_SIGNATURE`.
- **`app_remap`:** `_chat_archive_service`.
- **The rebind pair:** `_RECONCILE_THREAD` must stay in the same module as both its rebinding writer (`_reconcile_embedding_bank`) and its reader (`_shutdown_engine`).

**Mutable state:**

| Name | Home | Mutation | Who reads it | Split note |
|---|---|---|---|---|
| `_RECONCILE_THREAD` | `app_core` | rebound by `global` | `_shutdown_engine` | test_embedding_rebuild.py:491 patches it and reads `app_module._RECONCILE_THREAD` after `_reconcile_embedding_bank()`; through a facade re-export the read is stale None and the patch is inert. Repoint both to `web.app_core` |
| `_bundle_revision_cache` | `app_shell` | mutated in place, unlocked, from request threads | `_bundle_revision` | test_host_surface_transport.py:112 rebinds it; repoint |
| `_JSON_WIRE` | `app_settings` | never mutated | `_bootstrap_split`, `bootstrap_response`, tools, tests | — |
| `app` | `app_core` | decorated at import | — | sibling import order = route registration order; `route_overlap.py` found no full-match overlaps among all 268 routes, so order cannot change dispatch |
| middleware order | facade / `app_core` | — | — | keep gzip added before `access_control`, so `access_control` stays outermost |
| `_chat_archive_service` | `app_remap` | single instance | `extension_runtime/api.py:2347-2349` (`app._chat_archive_service.import_chat`) | — |
| `_unloaded` | facade tail | written once | — | — |

**Patch repoints beyond the anatomy's list:**
- `tools/mood_story_drive.py:61` rebinds `app._detach = _sync`, relying on `turn_new` "looking `_detach` up at call time". After the split this is inert, and the tool silently runs turns asynchronously. Repoint it to the sibling holding `turn_new`.
- `_begin_pipeline_or_409` and `_latest_turn_in_frame` are defined in `app_guards`, but the patched readers are in `app_turns`. Patch the readers' module.
- `image_model` and `ui_language` are read by two siblings each; use `patch_seam`.

**Facade back-imports by production code:**
- `web/world_routes.py:378` (`_refuse_for_an_off_screen_beat`, call-time). `world_routes` also duplicates `_require_chat_idle` as `_require_idle` (366-385, without `allow`).
- `extension_runtime/api.py:2472` (`_require_frame_idle`, plus `story_language_scope`, which is really `language_runtime`'s).

After the split both should import the guards leaf. Flag; do not fix in the split.

**Registration style the split must follow:**
- **Existing siblings** use `APIRouter(prefix=...)` included from app.py: auth, room, world ×6. `persist/chat_archive.py` uses `add_api_route` on a service router.
- **A verbatim move** keeps `@app.get(...)` and therefore needs `app` from a leaf. `tools/generate_code_map.py` (128-185) resolves both styles: any `X.<method>(path)` decorator, prefixed only when `X` is a local `APIRouter`. So `tests/test_code_map_generator.py::test_code_map_applies_local_api_router_prefixes` keeps passing either way.
- **`check_asgi_targets`** constrains only the launchers' `uvicorn web.app:app`, which stays valid while the facade exports `app`.

**Monoliths in miniature:** `turn_branch` 525, `chat_get` 316, `_remap_cp_blob` 216, `bootstrap` 179, `dlg_put` 109, `turn_new` 103, `chat_add_char` 96, `guest_state` 96, `chat_char_position_put` 84, `lore_entry_edit` 75, `character_start_story` 74.

**Leftover instrumentation:** `chat_get`'s `chat_read` INFO line (4786-4812), paired with `turn_committed` (885-895), was written for a 2026-08-08 stale-snapshot hypothesis. It still logs on every read and every run. Ask whether that hunt is closed.

**Latent trap:** `ambience_search(q: str, …)` (8231) shadows the module's DB helper `q` inside the function. It is harmless today; the first DB call added there raises `TypeError`.

## Docs checked

| Claim | Held? |
|---|---|
| AGENTS.md § `web/app.py` "Turns, rerolls, checkpoints, resume, and async streaming" | Partly. The streaming is a sync generator over a dedicated thread, not async |
| AGENTS.md routing rows: positions routes (529), `GET /api/chats/{cid}/lorebooks` ownership (543), per-story card edits keeping name and uid immutable (551 vs 5419-5427), `chat_add_char` recognition (545) | Held |
| AGENTS.md "Avoid broad rewrites of web/app.py…" | n/a, advisory |
| docs/guides/PIPELINE.md:36 "`web.app.turn_new` writes TWO turns in the slot" | Held (6755-6761) |
| docs/guides/DATABASE.md:574 "Branch/clone ID remapping in `web/app.py`" | Held (location only; matrix is another auditor's) |
| docs/guides/EXTENSIONS.md:1459 "`access_control` gates" `ui.js` | Held (`/api/extensions/ui.js`) |
| Design.md "Changing the embedding model is safe" row: probe "while a host waits for a chat to open" | Held, but incomplete: it also runs on every post-beat refresh (E1) |
| `_require_chat_idle` docstring: export/import use it | **Failed** (F8) |
| `chat_get` docstring: "ONLY EVER GROWS AT THE END" | **Failed** under concurrent frames (F7) |
| `turn_new` docstring: detach "answers at once" | **Failed** on the first scenario beat (F17) |
| `_shutdown_engine` docstring: "Daemon threads mean nothing HANGS" | **Failed** for pipeline threads (F18) |
| `turn_branch` comment: "nothing runs while a branch is taken" | Overstated; no slot is held |
| `agents/runtime.py:1574` (`_restore_and_refresh` docstring) quotes `turn_del` as `DELETE … turn_idx>=?` | **Stale.** The statement is now `turn_idx > COALESCE(MAX(idx), -1)` (`web/app.py:7896-7900`) |
| `tools/project_check.py:2926` `MEMORY_WRITERS`: "the manual add route passes no event_key, so it inserts" | Partly stale. `mem_add` forwards `body.get("event_key", "")`: empty from the UI, but a client-supplied key reaches `add_memory`'s keyed path |
| `edit_prose` comment: both siblings wrap the deactivate/activate pair in a transaction | Held. But `turn_narration_select` lacks the idle half (F13) |
| `_INSTALL_BLOCK_KEYS` comment (the class rule) | Drifted by one key (F20) |
| `SelectiveGZipMiddleware` docstring (text-only, streams excluded, no private Starlette API) | Held, by reading and by the existing tests |
| `access_control` comment: "Every /api/* request must carry …" | Held for `/api/*`; the docs routes sit outside it (F16) |
