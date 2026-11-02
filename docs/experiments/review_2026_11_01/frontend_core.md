# Audit — frontend core (static/index.html, chat.js, app.js, components.js, utils.js, i18n*, theme*, guest/login), 2026-11-01

Tree: `worktree-jev-character-tracking` at `84f3de23` (clean). Read-only; no test run was needed (every claim
below is a code trace or a Node probe of `i18n-core.js` against the shipped catalogs; scripts kept in
`scratchpad/fe_core/`).

## Scope read

Read IN FULL, every line:

| file | lines |
|---|---|
| `static/index.html` | 1-215 |
| `static/js/chat.js` | 1-3530 |
| `static/js/app.js` | 1-1373 |
| `static/js/components.js` | 1-1356 |
| `static/js/utils.js` | 1-266 |
| `static/js/i18n-core.js` | 1-250 |
| `static/js/i18n.js` | 1-34 |
| `static/js/theme-init.js` | 1-181 |
| `static/js/themes.js` | 1-159 |
| `static/guest.html` | 1-253 |
| `static/login.html` | 1-267 |

Cross-checked (partial reads, only the ranges named): `web/app.py` 610-720 (shell, `/login`), 860-1000
(`_drain_on_own_thread`, `_detach`, `_stream`), 1795-1860 (bootstrap install half), 4522-4836 (`chat_get`),
5139-5175 (`_reject_resolved_beat`, `_submit_player_input`), 5225-5378 (`_guest_inputs_by_beat`, `guest_state`,
`guest_input`), 6668-6770 (`turn_new`), 6860-6900 (`turn_status`), 7587-7640 (`pipeline_get`), 7795-7835
(step edit/activate); `agents/runtime.py` 330-385 (`STEP_LABELS`), 596-690 (token events), 1085-1110,
1179-1197, 2053-2100, 2140-2175; `story/attire.py` 700-760, 840-890; `tools/extract_ui_catalog.py` 1-120,
299-360; `language_packs/{en,ja}/ui.json` (probed, not read); `static/js/chime.js` 74-100;
`static/js/extensions.js` 415-465; greps over `settings.js`, `lorebooks.js`, `writers_room.js`,
`world_browser.js`; tests `test_frontend_state_guards.py` 20-60, 315-360, `test_stale_surface.py` 254-360,
`test_frontend_global_namespace.py` 138-160, `test_frontend_localization_rules.py` (grep). Prior work read
for de-duplication: `docs/experiments/AUDIT_FRONTEND.md` (headings, §F, §G, §H, suspicions, chat.js part),
sibling audits `scratchpad/audits/web_app.md` (F1, F4) and `web_routes_extensions.md` (F8, F21, eff. #3).

Skimmed only, NOT audited: `editors.js`, `lorebooks.js`, `settings.js`, `writers_room.js`, `world_browser.js`,
`backdrops.js`, `ambience.js`, `weather-fx.js`, `chime.js` (beyond `chimePlay`), `extensions.js` (beyond
415-465), `static/styles.css` (two greps).

**State of the previous frontend audit's findings in my files** (`docs/experiments/AUDIT_FRONTEND.md`): #13
(no sync error net) FIXED (`app.js:1215-1221`); #14 (`narrator_extra` friendly label) FIXED (`chat.js:878`);
#17 (`isResolved/markResolved`) and #18 (`fList` `remove`) FIXED (gone); #20 (`#b-style`) FIXED
(`chat.js:576`).

## Findings

### F1 — The guest page prints a stale step's label, which carries a character's true name (client half of the server leak)

- **Severity:** LEAK. **Confidence:** CONFIRMED (trace). Server half already reported by
  `web_app.md` F4 and `web_routes_extensions.md` F8; this is the client side the orchestrator asked about.
- **Where:** `static/guest.html:141-147`
  ```js
  if (t.stale_from) {
    ...
    note.textContent = t.prose_stale
      ? `Superseded — this text was written before “${t.stale_from.label}” was re-run.`
      : `Partly out of date — steps from “${t.stale_from.label}” onward were not recomputed.`;
  ```
  fed by `web/app.py:5327-5334` (`"stale_from": {"ord","key","label"}` of the earliest stale step), whose
  label for a `character:<id>` step is `"Character · " + character_name_from_text(sheet)`
  (`agents/runtime.py:362`, `1098-1103`, autonomy 0, uncontested). Also `guest.html:155`
  `` `${state.chat_name} — playing as ${state.persona_name}` `` prints the story title, which greeting quick
  starts compose from the character's name (`web_app.md` F4).
- **Scenario:** autonomy-0 story with a co-player whose `narrator_extra` calls a character "the hooded
  woman". The host activates another variant of `perception_act` (`web/app.py:7832` marks every later step
  stale), so the earliest stale step is `character:12`. The guest's next 10 s poll renders "Partly out of
  date — steps from “Character · Mirelle Sulmirath” onward were not recomputed." The guest is not the host
  (AGENTS.md's X9 keep covers the host only), and this field never passed perception.
- **Fix:** the page should never print `stale_from.label`; say "an earlier stage" (or map `stale_from.key`
  through a reader-safe table with no names), and have `guest_state` stop sending the label (sibling F8's fix).
  Test shape: static test on `guest.html` that `stale_from.label` is not rendered + the server test sibling F8
  names (stale `character:<id>`, assert neither name nor key in the guest payload).

### F2 — A story that fails to load leaves `S.chatId` pointing at it while the page shows the previous story; Send plays the line there

- **Severity:** CORRUPTION (a turn committed to the wrong story). **Confidence:** CONFIRMED (trace).
- **Where:** `static/js/chat.js:150-164`
  ```js
  if (switching) { closeAllModals(); window.clearVitalsHud?.(); }
  S.chatId = id;
  let chat;
  try {
    chat = await api("GET", "/api/chats/" + id + ...);
  } catch (error) {
    if (loadSeq !== _chatLoadSeq || S.chatId !== id) return false;
    throw error;
  }
  ```
- **Scenario:** reader is in story A, clicks story B; `GET /api/chats/B` fails (server restarting, a 500
  from a malformed chat, a 404 for a chat deleted in another tab). `S.chatId` is now B, `S.chat` is still A's
  payload, `renderChat` never ran, so the transcript, header (`#chatname`) and frame pills are A's. The error
  toasts. The reader types the next line for A and presses Send: `app.js:1144-1147` posts
  `/api/chats/${S.chatId}/turns` — story B — with A's `S.currentFrameId` (null in the common case, so it is
  accepted). Every toolbar button (world, cast, attire, dialogue, style) also acts on B. The stream's
  `finally` then re-opens B, so the reader sees their A line appear as a beat of B. The `_chatLoadSeq` guard
  (pinned by `tests/test_frontend_state_guards.py:27-33`) protects ordering, not this rollback.
- **Fix:** remember the previous `S.chatId`/`S.currentFrameId` and restore them on a non-superseded failure
  (or assign `S.chatId` only after the fetch and keep the in-flight id in its own variable for the supersede
  check). Test shape: Node harness slicing `openChat` (the pattern `test_dialogue_color_wiring.py` uses) with
  `api` stubbed to reject; assert `S.chatId` is back to A.

### F3 — Enter confirms every confirm/prompt overlay whatever has focus, including its own Cancel button

- **Severity:** CORRUPTION (destructive confirms run on "Cancel"). **Confidence:** CONFIRMED (trace; no
  test covers overlay keys — grep of `tests/` and `browser_tests/`).
- **Where:** `static/js/components.js:208-213`
  ```js
  const cleanup = () => { backdrop.remove(); document.removeEventListener("keydown", keyHandler) };
  const keyHandler = e => {
    if (e.key === "Escape") onKeydown?.dismiss();
    if (e.key === "Enter") onKeydown?.confirm();
  };
  document.addEventListener("keydown", keyHandler);
  ```
- **Scenario:** "Delete story?" (`app.js:257`), "Delete character?" (`:897`), "Delete persona?" (`:976`),
  "Delete last turn?" (`chat.js:720`), "Permanently delete this memory?" (`chat.js:3139`), the checkpoint
  restore warning (`chat.js:1415`) and the paid embeddings rebuild offer (`app.js:1343-1352`, "Not now"). A
  keyboard user Shift+Tabs from the focused primary button to Cancel/"Not now" and presses Enter: the
  document listener runs during the keydown's bubble, before the button's own activation, `finish(true)`
  wins and the delete (or the paid rebuild) runs. Because nothing traps focus, the same happens from any
  element behind the overlay (Tab out to a sidebar story row + Enter = confirm AND open that story).
- **Fix:** handle Enter only when the event target is inside the box and is not a button (a focused button's
  own activation decides), stop propagation, and trap Tab inside the box. Test shape: browser test — open a
  delete confirm, focus Cancel, press Enter, assert the promise resolved `false` and no DELETE was sent.

### F4 — A pipeline that fails or is stopped inside the stream is read as a success: the typed line is lost, the "ready" chime sounds

- **Severity:** SILENT-NOOP (the restore-your-input path never fires for the commonest failure) + wrong
  chime. **Confidence:** CONFIRMED (trace, client and server).
- **Where:** `static/js/chat.js:1370-1398`
  ```js
  let ok = true;
  try { await streamPost(url, body, handleEvt); }
  catch (e) { ok = false; toast(`Pipeline failed: ${e.message}`, "err"); }
  finally { ...
    if (ok && S.chatId === run.chatId) _freshRunPending = true;
    await openChat(S.chatId, (ok && heldTurnId && ...) ? { sinceTurnId: heldTurnId } : {});
    if (ok && typeof chimePlay === "function") chimePlay();
  ```
  `handleEvt` only toasts `error` (`chat.js:1057-1062`) and `aborted` (`:1063-1064`). Server: a run that
  raises is caught by `_drain_on_own_thread` and sent as an in-stream
  `{"type":"error","fatal":true}` (`web/app.py:893-904`) on an HTTP 200 stream, after `run_pipeline` has
  DELETED a turn that saved no step (`agents/runtime.py:2151-2169`, `_discard_stepless_turn` — "One of them
  is any player whose provider hiccups once"). `app.js:1148-1155` gives the line back only on `ok === false`.
- **Scenario:** provider out of credit / network error on the first model call. The turn row holding the
  line is discarded server-side, the client toasts "Pipeline error: …", `ok` stays true: the composer is not
  refilled (it was cleared at `app.js:1141`), the transcript has no turn — the line is gone. The chime that
  `chat.js:1395-1397` says plays "Only on success" plays, and `_freshRunPending` marks the newest (older)
  turn fresh so its backdrop/ambience is commissioned at once. Same for Stop before the first stage saved
  (`aborted`). The comment at `chat.js:132-135` ("so does a run that failed") is also untrue for this path:
  the failed run takes the sliced refresh.
- **Fix:** have `runStream` record the terminal event (`done` / `error` / `aborted`) and set `ok` from it;
  refill the composer when the run ended without `done` and the line is not in a saved turn; chime and mark
  fresh only on `done`. Test shape: Node harness for `runStream` with `streamPost` stubbed to emit
  `{type:"error"}`; assert `chimePlay` not called, `_freshRunPending` false, the input restored.

### F5 — The pipeline drawer is not scoped to the story it was opened for: its runs, Stop, preview and exports act on whatever is open now

- **Severity:** WRONG-SCENE. **Confidence:** CONFIRMED (trace). Same class as the A73 rule at
  `chat.js:1100-1115`, missed on this surface.
- **Where:** `chat.js:2162-2170` (`openPipeline` captures no scope; nothing hides `#drawer` on a story or
  frame switch — the only reference to `#drawer` in `static/js` is this function); run buttons
  `chat.js:2260`, `2478-2482`, `2495-2499`, e.g.
  ```js
  await runStream(`/api/turns/${tid}/rerun`, { from_key: s.key }, { turnId: tid });
  ```
  so `runStream` stamps the run with the CURRENT story/frame (`chat.js:1335-1336`); "Export chat"
  `chat.js:2225-2226` and the map panel `chat.js:2096-2100` read `S.chatId` at click/toggle time; memory
  consolidate/backfill reopen `memModal(S.memoryCharacter)` in whatever story is open (`chat.js:3390-3392`,
  `3411-3413`).
- **Scenario:** open story A's drawer, switch to story B (`openChat` closes modals and the vitals HUD only,
  `chat.js:150-153`), click "▶ Run from here" on A's narrator step. `_activeRun = {chatId: B, turnId: A's}`:
  Stop posts `/api/chats/B/abort` (A's run cannot be stopped), `showNarrationEarly` passes
  `inCurrentScope(_activeRun)`, finds no `.turn[data-turn=A's id]` in B and appends A's prose as
  `#early-turn` into B's transcript (`chat.js:1155-1166`), and the `finally` sets `_freshRunPending` so B's
  newest turn commissions a backdrop at once — exactly the A73 effect `chat.js:1388-1391` says it prevents.
  A frame switch does the same within one story. "Export chat" exports B.
- **Fix:** capture `{chatId, frameId}` when `openPipeline` opens and pass it to every `runStream`, the export
  and the map panel; close the drawer in `openChat`'s `switching` branch and in `switchFrame` (or re-check
  scope on click); bind consolidate/backfill's reopen to the chat captured when they started. Test shape:
  static guard in the style of `test_stop_uses_the_context_captured_by_the_active_stream` asserting every
  `runStream(` inside `openPipeline` passes `chatId`/`frameId`.

### F6 — A dropped or reloaded turn stream is never re-attached; the server's detach + status route exists and the SPA never uses it

- **Severity:** WRONG-SCENE. **Confidence:** CONFIRMED (trace).
- **Where:** `static/js/utils.js:212-243` (`streamPost`: one POST, no retry, no read timeout, no turn id
  until `done`), `chat.js:1370-1404` (a read error sets `ok=false`, hides Stop, clears `_activeRun`, enables
  Send), `app.js:1148-1155` (restores the typed line on `ok === false`). Server: `turn_new` documents
  `?detach=1` and "poll `GET /api/turns/{tid}/status` for the rest" (`web/app.py:6668-6676`, `6767-6769`),
  `_detach` says "come back for it" (`913-927`), `turn_status` (`6869-6900`); no file in `static/` calls
  either (grep for `detach`, `/status`). `chat_get` carries no running flag (`web/app.py:4815-4836`).
- **Scenario:** laptop sleep, Wi-Fi blip, proxy idle timeout or a reload mid-turn. The server keeps running
  the turn. The page toasts "Pipeline failed: network error", hides Stop (the run can no longer be aborted
  from the UI), re-enables Send and puts the line back in the composer. Pressing Send gets the 409 "A
  pipeline is already running…"; pressing it after the turn finished plays the same line a second time.
  After a reload nothing shows that a turn is running. Today `web_app.md` F1 (the `thread.join()` on
  disconnect blocks the event loop) makes the refresh in `finally` hang until the turn commits, which hides
  half of this; once that server fix lands, the page shows the half-written turn as "…" and nothing ever
  refreshes it.
- **Fix:** on a stream error, find the latest turn and poll `GET /api/turns/{tid}/status` (keeping Stop bound
  to the captured chat/frame and the composer line withheld while `running`), or submit with `?detach=1` and
  render progress from the status route; add a `running` flag to the chat payload for the reload case. The
  poll interval/backoff is the owner's number. Test shape: browser test that aborts the stream response
  mid-turn and asserts the committed turn appears without a manual refresh.

### F7 — The guest transcript shows every beat the guest was never part of as "Waiting for this beat to resolve…", forever

- **Severity:** WRONG-SCENE. **Confidence:** CONFIRMED (trace). The opening-turn half is registered (see
  Already registered, UNBUILT_PLATFORM §1.62); beats before the guest joined and other frames' beats are not.
- **Where:** `web/app.py:5311-5325` lists every turn of the chat and sends `"prose": entry.get("prose", "")`
  where `entry` is this persona's `narrator_extra` render; `static/guest.html:132-139`
  ```js
  if (t.prose) { prose.className = "prose"; prose.textContent = t.prose; }
  else { prose.className = "waiting"; prose.textContent = "Waiting for this beat to resolve…"; }
  ```
- **Scenario:** a friend joins at beat 50. Beats 0-49 have no render for their persona, so the page shows
  fifty "Waiting for this beat to resolve…" rows above the first real one, permanently; in a multi-frame
  chat every other era's beat is listed the same way (the payload has no `frame_id`, so the page cannot
  tell). The one pending beat that IS theirs is indistinguishable from the fifty that never will be.
- **Fix:** have `guest_state` mark (or omit) committed beats with no render for this persona — before their
  first served beat and outside their station's frame — and render those as nothing or a quiet divider.
  Test shape: guest joins after N turns; `GET /api/guest/state`; assert the earlier beats are flagged and the
  page's waiting text is keyed on the flag.

### F8 — Story, character, persona, lorebook and speaker names, memory gists and chips are translated as if they were UI strings

- **Severity:** WRONG-SCENE (non-English UI). **Confidence:** CONFIRMED (trace + probe). The class
  `components.js:1-12` (`txt()`) and `world_browser.js` (83 `txt()`/`translate:"no"` uses) already solve;
  the core surfaces do not use it.
- **Where:** `el()` runs every string child and every `title`/`aria-label`/`placeholder`/`alt` through `t()`
  before insertion (`components.js:26-27`, `44-45`), and the observer translates any text node or attribute
  outside a `translate="no"` subtree (`i18n-core.js:220-249`). Unprotected user/model text:
  `app.js:201-204` (story name, text and `title`), `871` (character), `950` (persona), `497`/`711` (lorebook
  options), `560` (persona options), `656` (character checkbox labels); `chat.js:620-621` (`#chatname`
  textContent/title, translated by the observer), `501` (`title: span.speaker` on every tinted quote), `538`
  (frame label), `2655` (relationship names), `2958` (autobiographical summary), `2963-2964` (key-phrase
  chips), `2970-2974` (unresolved threads), `3172-3175` (memory gist text and title); `guest.html:119-149`
  (no `translate="no"` anywhere, so i18n.js's observer walks the guest's prose and their own pin). Captures
  of templates are translated too (`i18n-core.js:150-155`), so `aria-label: \`Rename ${chat.name}\`` renames
  the name as well.
- **Probe** (`scratchpad/fe_core/i18n_probe.js`, real `i18n-core.js` on `language_packs/ja/ui.json`):
  `"Tavern" => "酒場"`, `"Cast" => "キャスト"`, `"Player" => "プレイヤー"`, `"Room" => "ルーム"`,
  `"Continue" => "続ける"`, `"Search" => "検索"`; the ja pack has 250 single-word keys.
- **Scenario:** ja UI, a story named "Tavern" is listed and headed as 酒場; a persona "Player" shows
  プレイヤー; a key phrase "Map" in a memory reads 地図; a guest who types "Continue" sees 続ける as their own
  line.
- **Fix:** `txt()` for every user/model text child and `translate: "no"` on its element in these surfaces;
  make `el()` skip attribute translation when the element carries `translate="no"` (today `title` is
  translated even then, `components.js:26-27`); add `translate="no"` to `.turn` on `guest.html`. Test shape:
  extend `tests/test_frontend_localization_rules.py` with the sidebar label, `#chatname`, memory gist/chips
  and the guest turn.

### F9 — A guest's sent line vanishes until a beat takes it; the docstring says it is shown

- **Severity:** SILENT-NOOP. **Confidence:** CONFIRMED (trace).
- **Where:** `guest.html:229-244` (`send` posts `{idx: nextIdx}`, clears the box, refreshes);
  `web/app.py:5362-5378` stores it at `idx = next_idx` (an index with no turn row);
  `_guest_inputs_by_beat` puts it in `by_idx` (`5261-5262`) but `guest_state` emits only existing turn rows
  (`5316`), so the line is never sent. The docstring at `5238-5240` says a pending declaration "is still
  pending and still shown under the index it was filed under".
- **Scenario:** the guest sends "I check the door." The box empties and nothing on the page shows the line
  until the host runs a beat. A guest who thinks it failed and sends again silently REPLACES it
  (`_submit_player_input` upserts on `(chat, idx, persona)`, `5169-5175`).
- **Fix:** return the guest's pending line(s) beyond the last turn (`pending_input`) and render it as
  "queued"; correct the docstring. Test shape: `guest_input` then `guest_state` → the pending line is present.

### F10 — One failed poll ends the guest's live view for good; a later successful send does not resume it

- **Severity:** SILENT-NOOP. **Confidence:** CONFIRMED (trace).
- **Where:** `guest.html:172-178`
  ```js
  } catch (e) {
    headSub.textContent = "Connection lost — " + e.message;
    stopPolling();
  ```
  `startPolling` is called only from join and session restore (`106`, `222`); the visibility handler needs
  `polling` (`206-208`); `send` → `refresh` succeeds but never restarts it (`237`).
- **Scenario:** the host restarts the server (routine after a commit) or a proxy returns one 502. The guest
  page stops polling permanently; after the server is back, even a successful send refreshes once and the
  transcript then never updates again until a manual reload. The comment says this path is for "A
  revoked/expired session"; any error takes it.
- **Fix:** stop only on 401/403; otherwise keep polling with a backoff (interval is the owner's), and call
  `startPolling()` after any successful refresh while stopped. Test shape: static test that `stopPolling` in
  `refresh`'s catch is gated on an auth status; browser test with one injected 500.

### F11 — Composed English the catalog can never match, and two catalog entries that can never fire

- **Severity:** SILENT-NOOP (ja pack entries inert; English on a Japanese page). **Confidence:** CONFIRMED
  (probe).
- **Mechanism:** a `"literal " + variable` string is a runtime message with no key: the extractor joins only
  literal-literal runs (`tools/extract_ui_catalog.py:113-133`) and keeps the fragment, which never matches.
- **Probe** (same script, ja): `"Hinami is deciding what to do"` stays English (`chat.js:904`; the catalog
  key `is deciding what to do` => 何をすべきか決めている is dead — no runtime string equals it);
  `"12 memories recalled"` (`chat.js:3014-3017`), `"Turn 12"` (`3033`), `"Summary through turn 40"`
  (`2980-2981`), `"last: turn 7"` (`2658`), `"last shift triggered by event e12"` (`2673`),
  `"Hinami hasn't formed any tracked opinions…"` (`2646`), `"How Hinami currently feels…"` (`2650`),
  `"Adds to Hinami's existing memories…"` (`2831`), `"Source: library. Saving stores…"` (`3483-3484`,
  `3513`), `"Reading story.json…"`/`"Loaded story.json ✓"` (`1473`, `1479`, `2836`), `"⇉ ran concurrently
  with …"` (`2041`), `"Map unavailable: …"`, `"Load error: …"`, `"Search error: …"`, `"Error: …"`
  (`2155`, `2924`, `3258`, `3463`), `"<label>  (stale)"` drawer headings (`2586`), `"NSFW: ON"` (`app.js:1067`;
  `NSFW: OFF` does translate, so the button flips language), `"covers: …"`/`"worn at: …"`/`"<region> zones
  still covered:"` (`components.js:776-777`, `810-812`), `"Could not reach the server. …"` (`utils.js:155-158`)
  — all returned unchanged. Half-English: `"Rebuilding Hinami's earlier eras" => "Hinami's earlier erasを再構築中"`
  (`chat.js:3386`, `3406` interpolate `name + "'s earlier eras"` inside the template).
- **Second dead entry:** `STEP_LABELS["character"] = "Character · {name}"` (`agents/runtime.py:362`) is a
  Python format string; the catalog holds it verbatim (ja `キャラクター · {name}`) but the browser only ever
  sees the formatted label. `"Character · Hinami"` is translated only BY ACCIDENT, through
  `settings.js:350`'s unrelated `` `Character ${charId}` `` template (capture `· Hinami`); delete that
  fallback and every character step in the drawer and the live log reverts to English.
- **Fix:** compose through `t()` placeholders (`t("{name} is deciding what to do", {name})`, which the
  extractor harvests as one key), and translate step labels from `key` + name rather than the formatted
  label. Test shape: catalog test that flags a JS string literal adjacent to `+ variable` inside an `el(`,
  `toast(` or `.textContent =` (the probe list is the seed).

### F12 — `FRIENDLY_SUBAGENTS` is never read; its comment promises a progress line nothing produces

- **Severity:** DEAD (+ STALE-DOC). **Confidence:** CONFIRMED (grep of the whole repo: one definition, one
  test that uses the line only as a slice delimiter).
- **Where:** `chat.js:885-895`: "Sub-agents that run INSIDE a stage … so the progress line names them instead
  of leaving the stage looking stuck." No reader in `static/`; no event in the stream names a sub-agent
  (`agents/runtime.py` emits only `step_start`, `token`, `step`, `done`, `aborted`; `notice` and
  `generation_reset` come from elsewhere). Introduced `f2cd626c`; never wired.
- **Fix:** delete it — and change `tests/test_frontend_state_guards.py:335`, which slices
  `FRIENDLY_STEP_LABELS` up to `"const FRIENDLY_SUBAGENTS"` — or emit sub-agent events and read them.

### F13 — `friendlyPhase`'s scene-life branch returns the string the table already returns; its comment says the opposite

- **Severity:** DEAD (+ STALE-DOC). **Confidence:** CONFIRMED (trace).
- **Where:** `chat.js:898-901`
  ```js
  // A stage whose plan label already names the mode (the scene manager) should
  // keep that name rather than be flattened back to a generic one.
  if (/^Scene life/.test(String(label || ""))) return "Bringing the room to life";
  if (FRIENDLY_STEP_LABELS[key]) return FRIENDLY_STEP_LABELS[key];
  ```
  The step key is always `background_react` (`agents/runtime.py:1179`, `1182-1197`), and
  `FRIENDLY_STEP_LABELS.background_react` is `"Bringing the room to life"` (`chat.js:882`). It also couples
  to the server's English label text.
- **Fix:** delete the branch, or give scene life its own phrase if the distinction is wanted.

### F14 — `renderLegacyLoreSidebar` is unreachable, cannot work if reached, and its Cancel creates a lorebook

- **Severity:** DEAD. **Confidence:** CONFIRMED (grep).
- **Where:** `app.js:128-133` falls back to it only when `renderLoreLibrarySidebar` (`lorebooks.js:307`) is
  undefined, i.e. when `lorebooks.js` failed to load — then its own rows and "+ Lorebook" call
  `openLoreWorkspace`, also `lorebooks.js` (`:689`), and throw. Inside, `app.js:1039`
  `const name = await promptModal("Lorebook name?") || "New lorebook";` turns Cancel (`null`) into a POST.
- **Fix:** delete the function and the `typeof` branch (index.html's own rule says a core script is not
  guarded).

### F15 — Ctrl+Enter is handled twice; with no story open it stacks two "New story" wizards

- **Severity:** WRONG-SCENE (minor). **Confidence:** CONFIRMED (trace).
- **Where:** `app.js:1117-1126` (on `#input`) and `app.js:1186-1193` (on `document`, gated on
  `document.activeElement === $("#input")`, not on `defaultPrevented`) both call `$("#send").click()`.
- **Scenario:** with a story open the second click is swallowed by `S.busy`/disabled Send; with none,
  `#send` (`app.js:1133-1136`) calls `newChatWizard()` twice and `modal()` pushes the first wizard under the
  second (`components.js:107-115`); without a provider it raises two toasts and two API dialogs.
- **Fix:** drop the document-level copy. Test shape: static test that only one listener clicks `#send`.

### F16 — Two quick 📖 clicks stack two turns' pipelines in the drawer

- **Severity:** WRONG-SCENE (debug surface). **Confidence:** CONFIRMED (trace).
- **Where:** `chat.js:2163-2170` clears `D` BEFORE `await api(...)/pipeline`, and nothing checks after the
  await; `2283`, `2596` append. The payload carries every variant's reasoning, so the window is seconds.
- **Fix:** a sequence guard like `_chatLoadSeq`, clearing after the await.

### F17 — A reroll arrow that fails to save leaves the transcript showing a rendering the server did not activate

- **Severity:** WRONG-SCENE (minor). **Confidence:** PLAUSIBLE (needs a refused POST).
- **Where:** `chat.js:1286-1303` paints and advances `RR.index` first, and the `catch` only toasts.
- **Scenario:** the POST is refused (409: a run started in another tab). The page shows variant 3; the
  story's record is variant 2, and the next beat is written against variant 2.
- **Fix:** on failure repaint the previously active variant and restore `RR.index`.

### F18 — Comments that describe code that is not there

- **Severity:** STALE-DOC. **Confidence:** CONFIRMED.
- `chat.js:1572-1574`: "The Director's five specialists, in the order the fan-out dispatches them … a
  specialist added or renamed in agents/director.py needs nothing here" — the fan-out was deleted 2026-09-27
  (CLAUDE.md); the `specialist` lens now serves only pre-2026-09-27 records (prose-contract records take
  the first branch, `chat.js:1596-1600`). Same at `1587-1592`.
- `chat.js:197-200` ("Purely a client-side filter/view-selector -- see S.currentFrameId…") is orphaned above
  the prose section; it belongs to `switchFrame` at `chat.js:542`.
- `chat.js:132-135` and `1395-1397` — see F4.

## Efficiency

1. **The translator scans all 446 template rules for every string that is not a catalog key — ~0.11 ms a
   miss, measured, in English as much as in Japanese.** `i18n-core.js:129-157`. Node 24 over the shipped
   catalogs (`scratchpad/fe_core/i18n_bench2.js`, `i18n_bench3.js`): 10,000 misses = 1.18-1.32 s on ja and
   1.10-1.35 s on en; a 10k-name loop over the rules alone = 1.12 s; the exact-key lookup is 0.0002 ms.
   The English pack is an identity map (2,896 of 2,897 entries equal their key; the other is
   `language.name`), so on en every miss is pure waste. Hot callers: `renderChat` (per beat) pays one miss
   per tinted quote (`chat.js:501`); `renderSide` (per beat via `openChat:184`, and per `boot()`) about
   eleven scans per story row (name ×2, five name-bearing `aria-label` templates sorted near the end, icons);
   the MEMORY BROWSER builds up to 1,000 cards (`limit: 1000`, `chat.js:2913`) and in ja the
   MutationObserver re-translates el()'s already-Japanese output — ~45 text nodes/attributes per card
   (14 field labels, 17 `<option>`s, badges, buttons, placeholders) — ≈ 5 ms a card, **≈ 5 s of main
   thread per 1,000-card render** in ja and ≈ 0.7 s in en (estimate = measured unit × counted calls), paid
   again on every sort change, save, archive and delete (`reloadMemView`). **Fix:** skip the template scan
   when the catalog is the identity pack; index rules by first literal (and suffix for the 66 rules whose
   first literal is empty); stop the observer re-translating strings that are catalog VALUES. Gain: 10-100×
   on misses; seconds → tens of ms for the ja memory browser.
2. **The memory browser builds a full editor for every memory card up front** (`chat.js:3040-3214`: ~40
   elements, two selects with 17 options, ~30 `t()` calls per card, inside a collapsed `<details>`). Build
   the fields on the card's first `toggle`. Gain ≈ 20-40× fewer elements on open/sort/reload.
3. **`renderChat` rebuilds the whole transcript after every beat although `openChat` fetched only the new
   turns** (`chat.js:182-185` → `582-761`: `M.innerHTML = ""`, every turn re-painted through `paintProse` /
   `speechSpans`, every turn re-observed). Per beat, per frame switch, per reroll. Append the slice and
   re-render only the previous-last turn (its reroll/delete buttons move). Gain O(new) vs O(story).
4. **`renderSide()` on every `openChat`** (`chat.js:184`), i.e. after every beat, rebuilding every story row
   (and paying item 1 per row) when at most the highlight changed. Toggle `.on` on same-story refreshes.
5. **The guest page re-downloads and re-renders the whole transcript every 10 s** (`guest.html:119-152`,
   `194-204`): `msgsEl.innerHTML = ""`, every turn rebuilt, then `scrollTop = scrollHeight` — so a guest who
   scrolled up to reread is yanked to the bottom and loses any selection every 10 s. Server half is
   `web_routes_extensions.md` efficiency #3 (`active_mappings(..., after_turn_id=)` exists). Client: append
   by `idx`, keep the scroll unless already at the bottom.
6. **The drawer re-fetches the entire pipeline (every step, every variant, every reasoning trace) after each
   action** (`chat.js:2265`, `2458`, `2483`, `2500`, `2559` → `openPipeline(tid)`). Per click; payload grows
   with rerolls. Re-fetch the touched step.
7. Low: `boot()` → `localizeDocument()` (`app.js:45`, `utils.js:47-51`) walks every text node of the
   document, transcript included, on each of its ~60 call sites; `SHOW_TEXT` cannot prune `translate="no"`
   subtrees (`i18n-core.js:171-187`). A walker with an element filter returning `FILTER_REJECT` for the skip
   tree makes it O(chrome).

## Already registered

- **`docs/UNBUILT_PLATFORM.md` §1.62 "An extra player has no opening turn"** — the opening beat never gets a
  `narrator_extra`, which is why it is one of F7's permanent "Waiting…" rows. F7's other rows (beats before
  the guest joined, other frames' beats) are not in the register.
- **AGENTS.md keep X9** (moved out of UNBUILT §3.4) — the host reading co-players' step content is a product
  boundary; F1 is a GUEST reading the host's step labels and is not covered by it.
- Grepped and NOT registered: `stale_from`, `guest.html`, `FRIENDLY_*`, `friendlyPhase`, `streamPost`,
  `detach`, `turn_status`, `_confirmOverlay`/`confirmModal`, `openChat`, `openPipeline`, `txt(`, `chimePlay`,
  `localizeDocument`, `memModal`, `renderLegacyLoreSidebar` (all `docs/UNBUILT*.md`).

## Structure notes

### XSS (question 1) — no finding

Every `innerHTML` in scope assigns `""` (clearing): `guest.html:120`; `app.js:117, 118, 388, 557, 595, 599,
697`; `components.js:123, 152, 164, 176, 563, 1244, 1296, 1347`; `chat.js:520, 584, 836, 1652, 2036, 2119,
2125, 2154, 2165, 2349, 2350, 2379, 2380, 2388, 2623, 2634, 2643, 2902, 2922, 2951, 3012, 3244, 3256, 3458,
3462`. No `outerHTML`, `insertAdjacentHTML`, `document.write`, `DOMParser` anywhere in `static/js` (grep of
all 18 files). Model prose reaches the DOM only as text: `paintProse`/`appendEmphasized` (`chat.js:335-509`,
`createTextNode`; the emphasis allowlist builds elements this code creates; `<font>` becomes a class from
`[a-z]+`), `txt()` (player input, prose editor), `el()` text children, `textContent` (guest page, live log,
drawer `<pre>`). Style values are constants or server-normalised colours assigned to `style.color`. The
only place model content meets foreign code is the extension step renderer (`chat.js:2377-2386`, hands
`content` and a `<pre>` to `Sonder._stepRenderer`) — the extension's responsibility. Latent trap in `el()`:
`selected`/`checked` set TRUE for any value, `false` included (`components.js:23-24`); every current caller
uses the presence idiom (`...(cond ? {checked: ""} : {})`, 80+ sites grepped), so no live bug.

### Step-label registries (question 2)

- Server `agents/runtime.py:355-375` `STEP_LABELS`: 18 keys = 15 step keys + 3 label variants
  (`background_react.ambient`, `background_react.full`, `narrator.establish`); `character` is the template
  for `character:<id>`.
- Client `chat.js:859-883` `FRIENDLY_STEP_LABELS`: 14 keys, a different vocabulary (reader phrases), not a
  copy. Only in STEP_LABELS: `character` (handled by the prefix strip `chat.js:902-905`, which regex-matches
  the server's English `Character ·`), `background_react.ambient/.full` (label variants of key
  `background_react`; the redundant branch of F13), `narrator.establish` (variant of key `narrator`). Only in
  FRIENDLY: none. `tests/test_frontend_state_guards.py:315-337` holds FRIENDLY ⊇ `STEP_HANDLERS`.
- Further copies of step names in the client: `_NARRATION_STEPS` (`chat.js:1121`), `PROSE_CONTRACT_CALLS`
  (`1796-1802`, role names), `stepLenses`' shape tests. With CLAUDE.md's four server registries that is six.
- UI catalog: all 18 `STEP_LABELS` values are keys in en and ja; `Character · {name}` can never match (F11);
  the friendly character phrase has no template (F11); `FRIENDLY_STEP_LABELS` values are all keys (they are
  plain literals the JS sweep harvests). Two client regexes read the server's ENGLISH label
  (`chat.js:900`, `903`); a server-side translation of `STEP_LABELS` would break the name strip silently.

### SSE / polling (question 3)

- The turn stream is NDJSON over `fetch` POST, not `EventSource`: no automatic reconnect, no backoff, no
  resume, so no duplicate-after-reconnect either. A read error ends the run client-side (F6); in-stream
  `error`/`aborted` end it as a success (F4). `streamPost` swallows exceptions thrown by the HANDLER as well
  as parse errors (`utils.js:238`, `242` `catch (e) { }`), so a bug in `handleEvt` is invisible (no console);
  no concrete throwing path found today — latent.
- `since_turn_id`: used by the SPA after an append (`chat.js:1355-1358`, `1393-1394`, `136-174`); server
  slices by `id > since` (`web/app.py:4627-4673`), client keeps `id <= turns_since` — consistent.
  `after_turn_id` is server-only (`active_mappings`). The guest route has no slice parameter (efficiency 5).
- Guest poll: fixed 10 s, skipped while hidden, refresh on visibility return, in-flight dedupe
  (`guest.html:162-216`); stops on the first error (F10); no backoff.
- Other timers: `turnStatusStart` 1 s while running (`chat.js:916-926`), `activityTicking` 1 s while tasks
  run (`components.js:579-590`), `erWatch` 1.5 s while a rebuild runs (`app.js:1308-1314`). All self-stopping.

### Module-level mutable state and its writers (question 4)

- `window.X =`: `erOfferRebuild` (`app.js:1321`), `Sonder` (`extensions.js:661`), `SONDER_APPEARANCE`
  (`theme-init.js:145`), `syncVitalsGutter`/`clearVitalsHud`/`refreshVitalsHud` (`settings.js:1049`,
  `1192-1193`), `openWorldBrowser` (`world_browser.js:3995`).
- `S` (`utils.js:3-16`) written from several files: `S.chat` (chat.js `openChat`; app.js:226 rename;
  settings.js:701, 3801), `S.chatId` (chat.js:154; app.js:264), `S.boot` (app.js:35; patched by
  ambience.js:1052, backdrops.js:412, settings.js:2488-2491 — all non-install keys, so the cached install
  half `bootInstall` is never mutated), `S.nsfw`/`S.tab`/`S.uiCatalog`/`S.uiLanguage` (app.js),
  `S.uiTemplateRules` (app.js, utils.js), `S.modal*` (components.js), `S.models`/`S.imageModels`
  (components.js), `S.busy`/`S.currentFrameId`/`S.memoryCharacter` (chat.js; `S.memoryCharacter` is never
  cleared and outlives a story switch — F5's reopen case).
- chat.js private state (read/written only by chat.js — grep): `_visibleTurnObserver`, `_chatLoadSeq`,
  `_activeRun`, `_freshTurnId`, `_freshRunPending`, `_turnStatusTimer/_turnStatusStart`, `_streamTgl`,
  `_liveBuf`, `_liveFlushQueued`, `RR`, `EARLY_TURN_ID`. components.js: `pendingCover`, `_activityTicker`.
  app.js: `languagePackErrorReported`, `bootInstall`, `_composerResizeQueued`, `ER`. utils.js:
  `staleCodeReported`.
- Listeners: no per-render leak found. Document listeners are added once at load (`components.js:90`,
  `chat.js:849`, `1310`, `app.js:1111-1126`, `1174`, `1200`, `1215`); `_confirmOverlay` removes its own;
  `modelCombobox` removes its document listener lazily on the first click after detach
  (`components.js:1332-1338`) — note that a stacked `modal()` detaches the parent, so a combobox in a parent
  modal would lose its outside-click close (no current caller opens a nested `modal()` over a combobox).
  `observeVisibleTurn` is NOT disconnected on `renderChat`'s two early returns (`chat.js:597-642`): the old
  IntersectionObserver keeps the previous transcript's detached DOM alive until the next populated render.
- `localStorage`: `sonder.ui.theme`, `sonder.ui.proseSize`, `sonder.ui.effects` (validated against closed
  sets, `theme-init.js:95-131`), `sideCollapsed` (`=== "1"`, `app.js:95-105`), `storyLanguage` (written by
  `app.js:756` AND `settings.js:3795`; validated against the story packs on read, `app.js:409-415`);
  outside my files `ambience.*`, `chime.muted`, writers-room keys; `sessionStorage` `sonder.reopenPrompts`.
  The extractor harvested `sideCollapsed`, `storyLanguage`, `DOMContentLoaded`, `GET`, `POST`, `Escape`,
  `ArrowLeft` into the UI catalog as "messages" (inert identity entries).

### Accessibility (question 6)

- `#modal` (`index.html:136-144`) has no `role="dialog"`, `aria-modal` or `aria-labelledby`; `modal()`
  focuses the first input only (`components.js:126-129`), traps nothing, and `closeModal()` does not return
  focus to the opener (`146-165`). The confirm/prompt overlay (`195-223`) likewise has no role and no trap,
  which is what lets F3's Enter fire from behind it.
- Main input: `#input` has an `aria-label`, Ctrl+Enter sends (twice, F15). It is reachable by Tab only
  after every turn's `.tbtns` buttons (4-6 per turn, hidden by opacity and still focusable,
  `styles.css:341-344`) — about 1,200 stops on a 300-turn story; Shift+Tab from the end of the page reaches
  it in ~6. No skip link or focus shortcut.
- Error toasts share the `polite` live region (`index.html:156`); an `assertive` region for `err` would
  announce failures.

### Monoliths in miniature

`openPipeline` (`chat.js:2162-2598`, 437 lines, one function with nested closures), `renderChat`
(`582-761`), `memoryCard` (`3040-3214`), `memModal` (`2680-2808`), `runStream` (`1332-1405`);
`components.js` `livedLocationControl` (`304-445`), `modelCombobox` (`1220-1356`), `fCoveragePicker`
(`737-838`); `app.js` `renderChatSidebar` (`182-309`), `runWizard` (`762-852`).

### Two representations free to disagree

Client copies of server constants: `app.js:743-746` "at most 16 full characters" vs
`CAST_HISTORY_REQUEST_CAP = 16` (`world/charter_runtime.py:62`); `components.js:425`
`Math.min(96, horizon)` vs `DEFAULT_PRESIM_TAIL_HOURS = 96.0` (`charter_runtime.py:55`); `components.js:420`
(720 h ceiling), `360` (3..20 journey events), `399` ("10–16 separate memories" in prose). The bootstrap
already ships the attire and memory vocabularies for exactly this reason (`components.js:683-697`).

### Other notes

- `/login` and `/guest` load `/static/js/i18n-core.js`, `i18n.js`, `theme-init.js` without the `?v=`
  bundle token the SPA's shell gets (`guest.html:10-12`, `login.html:10-12`; `web/app.py:646-694` rewrites
  `index.html` only; `/login` is a bare `FileResponse`, `:690-694`). Starlette sends no `Cache-Control`, so
  browsers may heuristically reuse an old `i18n-core.js` beside a new `i18n.js` after an upgrade. PLAUSIBLE.
- `extensions.js:422-425`, `459-460` `typeof`-guard `openChat`/`renderSide`/`renderChat`, which
  `index.html:161-168` says no file does; its own comment justifies it (an extension view on a page without
  the chat module). `boot` is called from 8 files, not "four".

### Split notes for chat.js (question 7)

Natural sections (line ranges):

| # | lines | section | top-level names |
|---|---|---|---|
| 1 | 1-121 | visible-turn tracking + run-scoped state | `_visibleTurnObserver`, `_chatLoadSeq`, `_activeRun`, `_freshTurnId`, `_freshRunPending`, `observeVisibleTurn` |
| 2 | 123-195 | story navigation (sliced refresh) | `openChat` |
| 3 | 201-516 | prose painting (dialogue tint, emphasis) — pure but for `proseEl` | `_FOLD_PAIRS`, `foldTypography`, `_EMPHASIS_TAGS`, `_EMPHASIS_RE`, `decodeProseEntities`, `splitEmphasis`, `appendEmphasized`, `quoteBody`, `quotedRegions`, `speechSpans`, `paintProse`, `proseEl` |
| 4 | 518-580 | frames, composer sync, scoped buttons | `renderFrameBar`, `switchFrame`, `syncComposerToFrame`, `updateChatScopedButtons` |
| 5 | 582-832 | transcript render + turn actions | `renderChat`, `beginStory`, `branchTurn`, `editTurnInput`, `editTurnProse` |
| 6 | 834-1079 | live log, status line, event handler | `liveReset`, `FRIENDLY_STEP_LABELS`, `FRIENDLY_SUBAGENTS`, `friendlyPhase`, `turnStatusStart/Set/Stop`, `_streamOn`, `_liveBuf`, `liveFlush`, `liveAppend`, `liveStep`, `handleEvt` |
| 7 | 1081-1172 | narration preview | `inCurrentScope`, `_NARRATION_STEPS`, `EARLY_TURN_ID`, `showNarrationEarly`, `clearNarrationEarly` |
| 8 | 1174-1323 | reroll browsing | `RR`, `resetRerollNav`, `_mountRerollNav`, `_paintRerollCount`, `showRerollVariant` |
| 9 | 1325-1431 | the run | `abortActiveRun`, `runStream`, `confirmCheckpointRestore`, `runReroll`, `rerollTurn` |
| 10 | 1433-1523 | story import/export | `exportChat`, `importChatModal` |
| 11 | 1525-2066 | pipeline lenses | `perceiverViews` … `renderEngineNotes`, `PROSE_CONTRACT_CALLS`, `proseContract*`, `perceptionPacketSlice` |
| 12 | 2068-2598 | pipeline map panel + drawer | `pipelineMapPanel`, `openPipeline` |
| 13 | 2600-2677 | relationship viewer | `relMeter`, `relationshipModal` |
| 14 | 2679-3465 | memory browser | `memModal` and 16 helpers |
| 15 | 3467-3530 | private history | `chatPH`, `personaPH` |

Names other files call (grep of every `static/js/*.js` and `static/*.html` for each of chat.js's 107
top-level names; comments excluded): `openChat` (app.js, editors.js:344, settings.js:1596,
extensions.js:425 guarded), `renderChat` (app.js:74, 266; settings.js:702, 2137; extensions.js:460
guarded), `runStream` + `abortActiveRun` + `exportChat` + `importChatModal` (app.js:1144, 1159, 243, 305),
`inCurrentScope` (writers_room.js:296, 383, 418), `relationshipModal`, `memModal`, `chatPH`, `personaPH`
(settings.js:782, 778, 786, 732). Everything else is private to chat.js. No other file uses a chat.js name
at top level (scan of column-0 lines of every other file). chat.js's own parse-time statements are only
`$("#streamtgl").addEventListener(...)` (`849`, needs utils.js `$`) and
`document.addEventListener("keydown", ...)` (`1310`), plus constant initialisers.

Proposed split (all in chat.js's current slot, between `chime.js` and `writers_room.js`):

1. `prose.js` — sections 3 (≈315 lines). Callee of 5, 7, 8 (call time only).
2. `chat.js` — sections 1, 2, 4, 5, 10 (≈600). Keep `_activeRun`, `_freshRunPending`, `_freshTurnId` here:
   `observeVisibleTurn` writes the latter two and `runStream` (file 3) writes all three at call time.
3. `turn_run.js` — sections 6-9 (≈600). Holds both parse-time listeners (need only utils.js).
4. `pipeline_drawer.js` — sections 11-12 (≈1,075). Calls `runStream`, `confirmCheckpointRestore` (file 3)
   and `wbRenderRoomMap` (world_browser.js, guarded) at call time.
5. `memory_browser.js` — sections 13-15 (≈930). Called only by settings.js at call time.

Order `prose.js → chat.js → turn_run.js → pipeline_drawer.js → memory_browser.js`. Because no file calls a
chat.js name at parse time, any order inside the slot is correct at runtime; this one keeps callees before
callers. Constraints: top-level `let`/`const` in classic scripts share ONE global lexical scope (not
`window` properties) — no name may be declared in two files (`tests/test_frontend_global_namespace.py:57`
enforces it), and cross-file reads of `let` state are fine at call time. Cost of the split: 15 test/tool
files read `static/js/chat.js` by path (`test_stale_surface.py`, `test_reasoning_trace_survives.py`,
`test_pipeline_perception_rendering.py`, `test_dialogue_color_wiring.py`, `test_frontend_turn_signals.py`,
`test_ui_catalog_extraction.py`, `test_frontend_state_guards.py`, `test_frontend_weather_null_payload.py`,
`test_frontend_server_vocabularies.py`, `test_a_prose_beat_is_tabbed_by_its_calls.py`,
`test_host_surface_transport.py`, `test_pipeline_perspectives.py`, `tools/extract_ui_catalog.py` (comment
only — it globs `static/js/*.js`), `tools/bench/chat_payload_cost.py`, `browser_tests/test_prose_emphasis.py`),
several slicing functions out for Node — they need a path map or a concatenation helper. The shell's
bundle token covers new files automatically (`web/app.py:646-683`); CLAUDE.md, AGENTS.md and the
`index.html` comments name the load order and must be updated with it; `make map`.

## Docs checked

| claim | where | verdict |
|---|---|---|
| Script load order `i18n-core → utils → components → editors → lorebooks → backdrops → ambience → weather-fx → chime → chat → writers_room → world_browser → settings → themes → extensions → app` | CLAUDE.md § Architecture, AGENTS.md § Frontend | HOLDS (`index.html:179-209`) |
| i18n-core.js is loaded by login/guest before i18n.js, "which load no other SPA script" | AGENTS.md § Frontend | HOLDS, except both also load `theme-init.js` |
| i18n.js "NOT loaded by index.html" | `i18n.js:6-8` | HOLDS |
| `boot`/`renderSide`/`openChat`/`newChatWizard` "reached … from four files … deliberately NOT typeof-guarded" | `index.html:161-168` | PARTLY — extensions.js guards three of them by its own documented exception; `boot` has 8 calling files |
| Never translate story text; `txt()` / `translate="no"` | `components.js:1-12`, `i18n-core.js:18-34` | HOLDS for the transcript; FAILS on the sidebar, header, memory browser and guest page (F8) |
| "so does a run that failed … refreshes whole" | `chat.js:132-135` | FAILS for in-stream failures (F4) |
| "Only on success … a chime that means 'ready' must not also mean 'gone wrong'" | `chat.js:1395-1397` | FAILS (F4) |
| "give the player their typed input back instead of silently eating it" | `app.js:1149-1150` | FAILS when the server discards the turn (F4) |
| FRIENDLY_SUBAGENTS "so the progress line names them" | `chat.js:885-888` | FAILS (F12) |
| scene-life branch "keep that name rather than be flattened" | `chat.js:898-899` | FAILS (F13) |
| specialists "in the order the fan-out dispatches them" | `chat.js:1572-1574` | STALE (F18) |
| `_detach`: "submit a turn WITHOUT holding a connection open … and come back for it" | `web/app.py:913-927` | Server HOLDS; no client comes back (F6) |
| pending declaration "still shown under the index it was filed under" | `web/app.py:5238-5240` | FAILS on the guest page (F9) |
| guest refresh catch is for "A revoked/expired session" | `guest.html:173-174` | PARTLY — every error takes it (F10) |
| "A reconcile the server begins at STARTUP is never polled for" | `app.js:1233-1240` | HOLDS (honest open decision) |
| Global error net covers sync throws too | `app.js:1206-1221` | HOLDS, but `streamPost` swallows handler throws before they reach it |
| X9: the host reads co-players' step content (keep) | AGENTS.md § gaps that are deliberate | HOLDS for the SPA; does not cover F1 (a guest reading host labels) |
| Every shell asset gets one bundle revision token | `web/app.py:636-645` | HOLDS for `index.html`; login/guest are not covered (Other notes) |
