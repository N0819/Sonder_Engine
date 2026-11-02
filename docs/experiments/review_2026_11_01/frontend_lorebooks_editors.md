# Audit — frontend: lorebooks, editors, Writers' Room, extensions, ambience, weather-fx, backdrops, chime

HEAD `84f3de23`, clean tree, 2026-11-01. 8,713 lines of `static/js/` in scope.
Severity tags beyond the brief's list, used where the brief's list has no frontend equivalent:
`SECURITY` (as the server auditor used it), `INPUT-LOSS` (an author's unsaved typing is discarded),
`I18N` (the UI renders untranslated or garbled text under the ja pack), `LANG-PACK` (engine prompt
text outside a language pack), `LOGIC` (low-impact correctness).

## Scope read

**Read in full, line by line:** `static/js/lorebooks.js` 1-3823, `static/js/editors.js` 1-1088,
`static/js/writers_room.js` 1-799, `static/js/extensions.js` 1-661, `static/js/ambience.js` 1-1095,
`static/js/weather-fx.js` 1-638, `static/js/backdrops.js` 1-430, `static/js/chime.js` 1-179.

**Read as context (only the ranges named):** `static/js/components.js` 1-140, 519-645 (`el`/`txt`/`modal`/
`toast`/`backgroundTask`/`buttonTask`); `static/js/i18n-core.js` 1-250 (whole); `static/js/utils.js`
20-60, 120-266 (`t`, `api`, `streamPost`, `showCardWarnings`); `static/js/app.js` 23-112, 1200-1215,
1355-1373; `static/js/chat.js` 582-595, 1116-1119; `static/js/settings.js` 3925-4120 (the 🧩 menu —
**the install/enable consent dialogs live here, not in extensions.js**); `static/index.html` script tags;
`web/app.py` 1275-1300, 1940-1960, 2005-2030, 2738-2746, 3000-3070, 3456-3476, 3640-3930, 3977-4007,
4067, 4079-4110, 4380-4404, 4966-4995, 5380-5470, 7942-7943, 8078-8145, 8289-8312; `web/room_routes.py`
40-140; `story/scene.py` 58-115, 434-447; `story/importers.py` 1101-1135, 1233-1310, 3204-3290;
`mind/memory_lorebooks.py` 25-90; `mind/memory_common.py` 41-56; `extension_runtime/__init__.py`
1660-1730, 2540-2627; `dressing/ambience.py` 150-200, 1567-1641; `tools/extract_ui_catalog.py` 80-260,
420-460; `docs/guides/EXTENSIONS.md` 1475-1520; the test files named under Structure notes (pins only).

**Skimmed only (not audited):** `persist/commit_background.py` 4929-5100 (promotion; see the Q2 note).

**Executed (all read-only / scratch):** node `vm` simulations of `chime.js` under blocked storage
(`scratchpad/fe_audit/chime_tdz.js`, `chime_null.js`); a node probe running runtime strings through
`i18n-core.js` against `language_packs/ja/ui.json` (`scratchpad/fe_audit/i18n_probe.js`, `probes*.json`);
a `.venv` snippet calling `mind.memory_lorebooks.move_lorebook` on a scratch DB (deleted afterwards);
a `mode=ro` count over `engine.db`. No test files were run.

## Findings

**Answers to the assignment's questions** (each points into the findings below).

- **Q1 — XSS.** No HTML-string sink in the eight files receives user- or model-authored data. Every
  lore, card, Room and notice string reaches the DOM through `el()` (`components.js:17-48`:
  `createTextNode`, `setAttribute`, `.value`) or `textContent`. `innerHTML` is only ever assigned `""`,
  except `weather-fx.js:574-582`, whose SVG is built from numbers (`innerWidth`, `toFixed`). There is no
  `eval`, `Function`, `insertAdjacentHTML` or `document.write`. Attribute sinks that carry data:
  `title`/`aria-label` (inert); **`ambience.js:826` `href: layer.credit_url` — any scheme is accepted, and
  an imported archive can reach it (F3)**; `backdrops.js:161` `` url("${url}") `` — the URL is
  server-built `/api/chats/<int>/backdrop/<signature>.png` (`web/app.py:7942-7943`), so it is safe;
  `extensions.js:150/641/647` load extension code, which is trusted with full access by design.
- **Q2 — Editors.** The client-side guard: on a per-story card the Name input is disabled
  (`editors.js:385-388`) and the uid is copied from the stored sheet (`:674`). The save still sends both
  fields. The server is the enforcement point and it holds. `chat_char_card_put` returns 400 on a name or
  uid change (`web/app.py:5418-5428`). `char_edit` writes the card each attachment is playing under into
  every attachment that has no card of its own, before a reusable-card rename lands (`:3815-3836`).
  Personas have no guard on either side (registered as UNBUILT_IDENTITY §1.104).
  **`initial_outfit`: yes, every save sends `initial_outfit: {regions}`.** `OWNED_SHEET_PATHS`
  (`editors.js:176`, used at 682 and 894) makes it override the stored subtree. This does not touch the
  story: no card route seeds attire, and `seed_initial_attire` returns early when the name already has a
  ledger entry (`story/scene.py:69-71`). Its only callers are scene materialisation, attach/promotion and
  the persona switch (`web/app.py:4380-4404`). The editor defects I found are elsewhere: F4, F5 and F10.
  *Not verified:* the promotion review exposes `identity.name` as raw JSON (`editors.js:925-946`), and
  the confirm route keys the new character by `character_name(sheet)`
  (`persist/commit_background.py:5013-5018`). I did not trace whether scene state keyed by the presence
  name follows an edited name.
- **Q3 — Lorebooks.** Only the server refuses cycles: `would_create_book_cycle`
  (`mind/memory_lorebooks.py:25-55`), confirmed by a snippet (it also refuses cross-scope parents,
  `:63-67`). The client offers descendants as parents and sends cyclic drops (F24), and no regression test
  covers the refusal. Every edit re-renders everything through `boot()` plus a workspace refetch (E1, E2).
  Drag state leaks (F7). Links: the client excludes self-links (`lorebooks.js:610`), and the DB has
  `CHECK(source<>target)` plus a unique index.
- **Q4 — Extensions UI.** `extensions.js` is only the in-page registry (`window.Sonder`). It holds no
  consent logic and sends no install or enable request. The dialogs are in `settings.js`:
  - **Install:** `confirmModal(source + "Nothing has reviewed this…")`, then
    `POST /api/extensions/install {source}` (`:4083-4101`). The extension arrives disabled.
  - **Enable:** `confirmModal(name + trust note + capability list)`, then
    `POST /api/extensions/{id}/enable` with no body, then `Sonder._load(id)` (`:3961-3993`).
  - **Remove:** a confirm, then `DELETE`. **Disable:** no dialog.
  - **Update:** no dialog at all (F2).

  Every request goes through `api()`: a same-origin fetch, with the cookie and
  `Content-Type: application/json`.

  **The client enforces nothing.** The dialogs only gate this page's own click handlers. The routes accept
  any request that carries the host cookie. That includes a same-site page — another port on the same host
  (server audit `web_routes_extensions.md` F1). It also includes any script already in the page: an
  enabled extension's UI code can call `Sonder.api("POST","/api/extensions/install",…)` and then
  `…/enable` with no dialog. That is consistent with the no-sandbox posture, but it means enabling one
  extension hands it consent for every other. The client cannot be the enforcement point; the fix belongs
  in `access_control`.

  **`Sec-Fetch-Site` is the right primary check:**
  - The browser sets it and a page cannot forge it. Refuse POST/PUT/PATCH/DELETE on `/api/*` when it is
    present and not `same-origin`.
  - When it is absent (older Safari), compare `Origin` with the request's own scheme://host:port.
  - As defence in depth, require `Content-Type: application/json` on unsafe methods. That forces a
    preflight this server never grants.

  **Compatibility, checked:** every unsafe request in `static/` already sends that header
  (`utils.js:143-149`, `streamPost` `:213`, `login.html:111-114`, `guest.html:85-88`), and none is
  cross-origin (there are no forms, no `FormData` and no `sendBeacon` in `static/`).

  This checks where a request came from; it does not enforce capabilities. It therefore does not
  contradict AGENTS.md ("capabilities are DISCLOSURE for the consent dialog, never enforcement").
- **Q5 — Audio/visual.**
  - **`play()` rejections:** all handled (`ambience.js:227, 286, 302, 401-415, 781`; chime uses
    `ctx.resume().catch`), so there is no console noise or unhandled-rejection toast. The real "stuck"
    risk is the unlock element that is never played (F21).
  - **weather-fx timers:** every timeout is kept in `WFX.timers` and cleared on stop, and a story change
    triggers stop (`backdrops.js:384/388`) — clean.
  - **ambience/backdrop timers:** the clocks are cleared on every render, but the result polls (up to 75 s
    and 210 s) are not cancelled on a story change (E6), and ambience state crosses stories (F8, F9).
  - **Thunder after hiding:** one already-scheduled thunderclap (up to 6.5 s) still fires after the tab
    hides, because `weather-fx.js:616-622` cancels only the flash timer. Trivial.
  - **weather-fx canvas resize:** there is no resizable canvas any more; the weather is CSS-animated
    tiles. Tiles are rasterised per `devicePixelRatio` and cached (`245-248`), but a DPR change (zoom,
    moving to another monitor) is not observed, so the old raster stays until the weather shape changes
    (`470-472`). The effect is cosmetic blur. The bolt reads `innerWidth`/`innerHeight` on each strike.
    `prefers-reduced-motion` is read at apply time only, with no change listener.
- **Q6 — i18n.** F11-F14 (all confirmed by the probe).
- **Q7 — Split notes.** See Structure notes.

### F1 — chime.js reads localStorage unguarded at parse time; a blocked store kills every `api()` call (and, the same way, ambience's controls)

- **Severity:** CRASH (the whole SPA). **Confidence:** CONFIRMED (node vm simulation).
- **Where:**
  ```js
  // static/js/chime.js:36-38
  const CHIME = {
    ctx: null,
    muted: localStorage.getItem("chime.muted") === "1",
  // static/js/chime.js:137-139
  function chimeWatches(method, url) {
    return CHIME_MUTATIONS.test(String(method || ""))
  // static/js/utils.js:138 — inside api(), BEFORE the fetch try block
    const chimed = typeof chimeWatches === "function" && chimeWatches(method, url);
  ```
  The same unguarded pattern appears in `ambience.js:94` (`ambienceStored`), `:144`, `:184`, and at parse
  time in `:1085-1086`.
- **Failure:**
  - **The trigger:** a profile where `localStorage` throws (SecurityError) or is `null` (Firefox
    `dom.storage.enabled=false`). The project treats this as supported: `theme-init.js:78-93`,
    `app.js:95-106`, `settings.js:3795` and `writers_room.js:142-150` all wrap storage in try/catch
    ("Private browsing and hardened browser profiles may block storage").
  - **chime.js:** line 38 throws during evaluation. `CHIME`, `CHIME_NOTES`, `CHIME_EXCLUDED`,
    `CHIME_MUTATIONS` and `CHIME_MIN_MS` stay in the TDZ for the life of the page, while the hoisted
    `chimeWatches` exists. So `api()` throws `ReferenceError: Cannot access 'CHIME_MUTATIONS' before
    initialization` on every call, GET included. `boot()` rejects ("Could not load the app: …",
    `app.js:1373`) and nothing works.
  - **ambience.js:** `:1085` throws the same way, so the four control bindings at `:1089-1095` are never
    made.
  - **Where only `setItem` throws** (quota): every `input` event on the volume slider raises through the
    global `error` net (`app.js:1215`).
- **Verified:** `scratchpad/fe_audit/chime_tdz.js` (getter throws SecurityError) and `chime_null.js`
  (`localStorage = null`) both print `api() guard threw: ReferenceError - Cannot access 'CHIME_MUTATIONS'
  before initialization` for POST and GET.
- **Fix:** read and write through try/catch helpers, as theme-init's `readStored`/`writeStored` do (default
  unmuted / 0.35). Optionally guard the chime hook in `api()` with try/catch, so an optional module can
  never fail every request. **Test:** the existing pins `tests/test_frontend_turn_signals.py:49-50` stay
  valid; add a pin that the read sits inside a `try`, or a node-vm test shaped like the scratch script.

### F2 — "Update" runs an extension's new code with no consent and no capability re-disclosure

- **Severity:** SECURITY. **Confidence:** CONFIRMED (traced).
- **Where:**
  ```js
  // static/js/settings.js:4020-4022 — no confirmModal on this path
  update.onclick = async () => {
    await backgroundTask("Updating extension",
      () => api("POST", `/api/extensions/${encodeURIComponent(ext.id)}/update`),
  ```
  ```python
  # extension_runtime/__init__.py:2561, 2612-2617
  was_enabled = is_enabled(ext.id)
  ...
  reload()
  if was_enabled:
      try:
          activate(refresh=True)
  ```
- **Failure:** The host consented to v1's capability list at Enable (`settings.js:3963-3975`: "Disclosure
  that arrives after consent is not disclosure"). The remote then ships v2, with new capabilities or simply
  new code. One click on Update — there is no dialog — re-clones the remote and calls `reload()`. Because
  the extension was enabled, it then `activate()`s v2's `register(api)` inside the engine process. The new
  "Declares:" line appears in the row only afterwards. The route (`web/app.py:2738-2745`) is also open to
  the same-site blind POST described in the server audit's F1.
- **Fix:** show the Enable dialog on Update, with the new manifest's capability summary
  (`audit_extension_source()` already audits without applying). Server-side, record the capability set the
  host consented to at enable; when an update changes it, leave the extension installed but disabled until
  the host enables it again. **Test:** update a fixture extension whose manifest adds a capability, then
  assert `is_enabled` is False.

### F3 — Ambience pin `url`/`preview` are stored unvalidated and travel in archives: the panel renders `url` as an `href` (any scheme), and the server `requests.get()`s `preview` (any host)

- **Severity:** SECURITY. **Confidence:** PLAUSIBLE (traced, not executed). The server half is outside my
  files.
- **Where:**
  - `ambience.js:825-827`: `el("a", { href: layer.credit_url, target: "_blank", rel: "noreferrer", … }, "source")`
  - `web/app.py:8135`: `"credit_url": layer.get("url") or ""`
  - `dressing/ambience.py:196-199`: copies `preview`, `license`, `username` and `url` verbatim for a
    freesound pin.
  - `dressing/ambience.py:1620-1641`: uses `choice.get("preview")` and `url=choice.get("url")`.
  - `dressing/ambience.py:1592`: `response = requests.get(url, …)`. The only check is the sound id, and
    "an unrecognised preview format is not evidence of a mismatch".
  - `dressing/ambience.py:150-155`: pins are an ordinary world key, so "`chat_archive` exports the whole
    `world` table".
- **Failure:** an imported story archive carries `world.ambience_pins = {"<room>": {"source":"freesound",
  "id":1, "preview":"http://<internal-host>/…", "url":"javascript:…"}}`. When that room's bed is resolved,
  the server fetches the internal URL and writes the body into the audio cache. The panel shows a "source"
  link whose href is the archive's `javascript:` URL. Whether clicking it executes depends on how the
  browser treats `javascript:` with `target=_blank` and `noreferrer`; I did not test it.
- **Fix:** in `_normalize_choice`, accept `url`/`preview` only as `https://` on freesound.org or its CDN,
  or drop a stored `preview` and always re-resolve by id (`_materialize` already does this when it is
  absent). In ambience.js, render the credit link only when the href matches `^https?:`. **Test:**
  `set_ambience_pin` with a `javascript:` or internal-host URL raises ValueError.

### F4 — Every card "fill" button rebuilds the editor from the STORED card plus the model's answer, discarding unsaved edits

- **Severity:** CORRUPTION — the card the author then saves is not what they typed. **Confidence:**
  CONFIRMED (traced).
- **Where:**
  ```js
  // static/js/editors.js:511-522 — "Fill psychology gaps" sends no draft
  const r = await api("POST", chatId === null ? `/api/characters/${c.id}/fill_psychology` : ..., { prompt: brief });
  const refreshed = { ...c, name: r.sheet?.identity?.name || c.name, sheet: JSON.stringify(r.sheet) };
  closeAllModals(); ... charEditor(refreshed, options);
  ```
  ```python
  # story/importers.py:1111 (psychology), :1256 and :1304 (appearance)
  stored = authored_card_for_fill("character", char_id, chat_id)
  merged = copy.deepcopy(stored)
  ```
  The appearance fill's `draft` (`editors.js:534-543`) carries only appearance, voice, parts and outfit,
  and only as model context. The interior fill's draft is the interior list alone (`:553`).
- **Failure:** the author types a drive essence and two traits, does not save, and clicks "✨ Fill
  psychology gaps" (tooltip: "populated fields are preserved"). The server sees the stored drive as empty
  and generates one. The editor reopens from the stored card plus the fill: the typed essence and traits
  are gone, the model's essence fills the field, and Save persists it. "Fill body & clothing" behaves the
  same way for every field outside appearance, and even inside it unless the model echoes the typed value.
  "Read the inside" behaves the same for everything except the interior.
- **Fix:** factor the Save serializer (`editors.js:672-756`) into one builder. Send its output as `draft` on
  all three fills, and merge into the draft rather than `stored` — or merge the proposal into the live
  widgets instead of reopening. **Test:** server test —
  `fill_character_psychology(..., draft=sheet_with_typed_drive)` with `chat_complete` patched keeps the
  typed drive.

### F5 — After any fill, "⚡ Quick start with this greeting" writes the unreviewed proposal to the reusable card

- **Severity:** CORRUPTION. **Confidence:** CONFIRMED (traced).
- **Where:**
  ```js
  // static/js/editors.js:259-266
  const stored = JSON.parse(character.sheet);
  const updated = { ...stored, opening: { ... } };
  api("PUT", "/api/characters/" + character.id, { sheet: updated })
  ```
- **Failure:** a fill reopens the editor as `charEditor(refreshed)`, where `refreshed.sheet` is the
  proposal (`:35-44`, `:98-103`, `:515-522`). The greeting carousel is built over that object
  (`greetingCarousel(c, …)`, `:382`). Quick start then PUTs the proposal — despite the variable name
  `stored` — without the author's Save. That contradicts "Nothing is written: the proposal reopens the
  editor unsaved, and the author's ordinary Save is still what commits it" (`:5-7`). Without a fill,
  Quick start writes the sheet as it was when the editor opened and silently drops every widget edit.
- **Fix:** have Quick start save through the same builder as Save, or refuse ("save the card first") when
  the editor holds a fill or edits. **Test:** a browser test, or a pin that the quick-start path uses the
  shared builder.

### F6 — Inside a story, the lore workspace keeps entry edits story-local but writes generated entries, reinterpretation, book metadata, moves, links and deletes into the shared library book

- **Severity:** CORRUPTION — one story's lore is published to every story that attaches the book.
  **Confidence:** CONFIRMED (every route traced; none takes `chat_id`).
- **Where:**
  - **Story-scoped:** `lorebooks.js:1760-1769` (+ Entry sends `chat_id`, and the server redirects to the
    canon book, `web/app.py:4105-4110`) and `:2148-2153` (an entry save sends `chat_id` and becomes an
    overlay).
  - **Library-scoped:**
    - `:2408-2413` — `POST /api/lorebooks/{id}/generate` with only `{prompt}`. That calls
      `generate_lore_entries(lid, brief)` (`web/app.py:4079-4084`), which calls
      `add_lore(lorebook_id, …)` (`story/importers.py:3204-3290`).
    - `:2271-2274` — reinterpret (`web/app.py:4067`).
    - `:1315-1330` — book PUT. `:1524-1527` — delete. `:3575-3581` — apply_plan.
    - `:2810-2823` and `:2961-2975` — link edits.
  - The header comment `:506-510`: "Edits made here write the story's overlay, never the shared library;
    additions land in the story's canon book."
- **Failure:** with story A open, the host opens library book "Harbour City", which is attached to A and
  to B. They click "✨ Generate entries" with a story-specific brief. Twelve entries land in the library
  book and are retrieved in story B. The "+ Entry" button in the same toolbar would have put the entry in
  A's canon. FEATURES.md's "an entry added from inside a story lands in the story's canon book" is true for
  one of the two add buttons.
- **Fix:** when `S.chatId && loreBookIsLibrary(state.selected)`, either route generation and apply into the
  story's canon, as `lore_entry_create` does, or put an explicit "this changes the shared library
  (N stories)" confirmation on each library-scoped action. Correct the comment at `:506-510`. **Test:** a
  route test that generate with `chat_id` lands in canon, or a frontend pin that every library-scoped
  action inside a story confirms.

### F7 — Drag state: the sidebar never clears `loreUI.dragId`, and every drop target trusts any `text/plain` or that stale id, so a foreign drop moves a lorebook

- **Severity:** CORRUPTION. **Confidence:** PLAUSIBLE (read; not run in a browser).
- **Where:**
  - `lorebooks.js:377-384`: sidebar `ondragstart` sets `loreUI.dragId`; the row has no `ondragend`
    anywhere in `367-410`, and `:398-409` never clears the id.
  - `:1012-1016` and `:1028-1031`:
    `Number(event.dataTransfer.getData("text/plain") || loreUI.dragId)`.
  - `:1187-1203`: the root zone's `ondragover` calls `preventDefault()` for any drag, and the zone carries
    the `filedrop` class, so it looks like the import drop zone (`editors.js:980`).
- **Failure:** drag book 7 in the sidebar and release it on empty space, or press Esc; `dragId` stays 7.
  Later, drop an image file on "Drop here to move to root". `getData` returns `""`, the handler falls back
  to 7, and `moveLoreBook(7, null, null)` re-roots the book with the toast "Lorebook moved." Dragging a
  selected "12" onto a tree row moves book 12 under that row. During `dragover`, browsers return `""` from
  `getData`, so the rows always decide on the stale id.
- **Fix:** use a private MIME type (`application/x-sonder-lorebook`) and check
  `dataTransfer.types.includes(…)` in every dragover and drop; ignore `text/plain`; clear `dragId` on the
  sidebar's `dragend`. **Test:** a browser test that drops a file on the root zone after a cancelled
  sidebar drag and asserts no move request.

### F8 — Ambience keeps the previous story's turn and room after a story switch: 🎲 rerolls that story's room, and enabling or unlocking plays its bed in the new one

- **Severity:** WRONG-SCENE (the sound) plus a write to the wrong story. **Confidence:** CONFIRMED on the
  client (every write of `AMB.turnId`/`AMB.signature` traced); the server effect is taken from the code
  comment at `ambience.js:623-624`.
- **Where:**
  - `ambience.js:546` `AMB.turnId = turnId;` and `:566` `AMB.signature = state.signature || null;` are
    their only writers.
  - `ambienceResetForRender` (`:681-697`) resets `wanted`, `room` and `playingRoom` — not `turnId`,
    `signature`, `roomName`, `pinned` or `silent`.
  - `:724` `reroll.disabled = !on || !AMB.signature;`
  - `:632-638` `resolveAmbience(AMB.turnId, AMB.signature, { reroll: true, layer })`
  - `:437-438` (the unlock) and `:1058` (the toggle) both call `ambienceForTurn(AMB.turnId…)`.
- **Failure:** switch from story A to an empty story B. No `ambienceOnVisibleTurn` ever fires there, so
  🎲 stays enabled. Clicking it POSTs `/api/turns/<A's turn>/ambience {reroll:true}` — "the server
  remembers the refusal" (`:623-624`) — and `playAmbience` starts A's new bed under B. Turning ambience on,
  or the pointerdown unlock, plays A's bed in B in the same way.
- **Fix:** in the chat-change branch of `ambienceResetForRender`, also null `turnId`, `signature`,
  `roomName`, `pinned`, `silent` and `reason`. Capture `S.chatId` before each await in
  `rerollAmbience`/`ambienceForTurn` and drop a result that arrives for another chat (the `inCurrentScope`
  rule `chat.js:1116` and `writers_room.js` already follow). **Test:** a browser test — open A, switch to
  an empty B, assert 🎲 is disabled.

### F9 — "Off" does not stop a bed already being searched for: the in-flight resolution starts playback after the toggle

- **Severity:** SILENT-NOOP — the off switch does not take effect. **Confidence:** CONFIRMED (traced).
- **Where:** `ambience.js:607-619`. After `await resolveAmbience(...)`, the gate is
  `if (found.token === AMB.wanted || found.signature === AMB.signature)` and then `playAmbience(...)`, with
  no `AMB.enabled` check. `toggleAmbience` turning off (`:1042-1061`) sets `enabled = false` and calls
  `stopAmbience()`, but leaves `wanted` and `signature` set. `rerollAmbience` (`:637-645`) has the same
  gap.
- **Failure:** the reader settles on a turn whose bed is being commissioned (the query model call alone
  measures about 27 s, `:486-487`) and switches ambience off. About 30 s later the bed starts, under a
  button that reads "Room ambience: off". The module's own rule is "Switched off means SILENT"
  (`:573-576`).
- **Fix:** make `playAmbience` return early when `!AMB.enabled`, or re-check `enabled` and the captured
  chat after every await. **Test:** the same browser harness as F8.

### F10 — "Generate character" drops the card warnings its route returns

- **Severity:** SILENT-NOOP. **Confidence:** CONFIRMED (traced).
- **Where:** `editors.js:1050-1054` `onSuccess: async () => { await boot() }`, while `web/app.py:3475-3476`
  returns `{"id": cid, "sheet": sheet, "warnings": character_card_warnings(sheet)}`. The helper
  `showCardWarnings` (`utils.js:255-266`) exists for exactly this: "the warnings used to reach exactly ONE
  of nine card-producing surfaces".
- **Failure:** a generated card with an empty `psychology.drive` — the failure CLAUDE.md spends a page on —
  is created silently. Of the ten card-producing surfaces, this is the only one whose browser side never
  shows the warnings. `tests/test_host_settings_surface.py:340-343` only counts `showCardWarnings(` ≥ 5 in
  editors.js, so it passes.
- **Fix:** `onSuccess: async r => { await boot(); showCardWarnings(r); }`. **Test:** tighten the pin so it
  checks each surface, the generate path included.

### F11 — UI messages containing a line break are never translated, although the ja pack has them

- **Severity:** I18N. **Confidence:** CONFIRMED (catalog lookup plus probe).
- **Where:** the harvester normalises whitespace into the key (`tools/extract_ui_catalog.py:187`
  `value = " ".join(str(value or "").split())`). The runtime looks up the raw string (`i18n-core.js:132`),
  and its template matcher skips every regex-free rule for a source with a line break (`:113`).
  Instances in scope:
  - `ambience.js:708-712` — `…${playing}\nClick for sound options`, the 🎧 button tooltip.
  - `lorebooks.js:2293-2296` — `"Describe the lore entries to generate.\n\n" + …`, the generate dialog's
    placeholder.
- **Verified:** `language_packs/ja/ui.json` holds both normalised keys (e.g.
  `部屋の雰囲気：…サウンドオプションはこちらをクリック`), and the probe returns both strings unchanged.
- **Fix (the class):** on a miss, `i18nTranslate` retries with `source.replace(/\s+/g, " ").trim()`; or the
  harvester keeps the line break and the matcher's regex path (`:84-85`) handles it. **Test:** run the
  probe as a test over every harvested message that contains `\n`.

### F12 — Messages built with `+` or with English sub-phrases render garbled under ja, because the template matcher picks a shorter unrelated rule

- **Severity:** I18N. **Confidence:** CONFIRMED (probe output below).
- **Where (runtime string → what a ja reader sees):**
  - `lorebooks.js:668-669` "Lorebook workspace — Harbour" → `伝承帳workspace — Harbour` (it matched
    `Lorebook ${book.id}`).
  - `lorebooks.js:2441-2446` "Generated 3 lore entries." → `3 lore件のエントリを生成しました。`;
    "Generated 1 lore entry." → `1 lore entry. を生成しました`. This is the plural ternary that `:3591-3595`
    says not to write.
  - `lorebooks.js:3588-3599` → `ブック Applied lorebook plan: 2 件、エントリ 5 件、リンク 1 件。`
  - `lorebooks.js:3299-3300` and `:3332-3334` → `サーバーで5 minutes agoに開始されました。3 of 10 entries
    generated. It keeps running…` (`loreGenAgo` at `:3242-3259` is English, and the tail is
    concatenated).
  - `lorebooks.js:3465-3468` and `:3234-3235` → entirely English.
  - `editors.js:559-560` and `:850` "Edit story card — Hinami" → `story card — Hinamiを編集`.
  - `editors.js:1035-1036` and `:1053-1054` "Character imported." → `キャラクター imported.`;
    "Persona import failed" → English. `:1006`/`:1044` "Import character" → `characterをインポート`.
  - `editors.js:299-301`, `:324`, `:949`, `:932-934`, `:987`, `:996` → English.
  - `ambience.js:479/531` → `環境音：no matching sound for Courtyard — 🎲 reroll …`; the aria-label at
    `:815` → `room レイヤーのレベル`.
- **Fix (the class):** one `t("…{var}…", {vars})` call per sentence, with a complete key, as
  `writers_room.js:328`, `:392-406` and `:528-538` already do. Translate sub-phrases (`loreGenAgo`, kind
  names) before interpolating them, and stop building sentences from
  `kind.charAt(0).toUpperCase() + …`. **Test:** the probe set, run as a test against each pack.

### F13 — Lower-case one-word UI labels are never harvested, so they stay English in every pack

- **Severity:** I18N. **Confidence:** CONFIRMED (the probe returns every one unchanged).
- **Where:**
  - lorebooks.js: "library" (`819`), "canon" (`1107`), "unreachable" (`1123`), "locked" (`2066`,
    `2101`), "incoming"/"outgoing" (`2773`), "bidirectional" (`2793`, `2944`).
  - editors.js: the knowledge levels "common", "scholarly", "esoteric" (`650-652`).
  - ambience.js: the role labels "room", "weather", "detail" (`808`, shown at `833` and inside `815`).

  The cause is `tools/extract_ui_catalog.py:249`:
  `if not label_position and re.fullmatch(r"[a-z0-9_.:/-]+", value): return None`. `label_position` is set
  only for `[value, "label"]` option pairs (`:438-445`).
- **Fix:** route visible enum labels through a label table the harvester already recognises (the option
  pairs), or capitalise them. **Test:** a catalog-coverage assertion for these literals.

### F14 — Lore names and titles written by users or models pass through `t()` and the document observer, so one that collides with a catalog key renders translated

- **Severity:** I18N (display only — inputs and textareas are left alone, so nothing is saved translated).
  **Confidence:** CONFIRMED (probe: "Cast" → キャスト, "Close" → 閉じる, "Book" → ブック).
- **Where:** `lorebooks.js:2040-2063` (an entry's title as a plain child and as its `title` attribute),
  `:2604-2617` and `:2763` (book names in the relationship views), `:416` (`title: book.name`), `:668-669`
  (modal title). The mechanism: `components.js:41-45` runs non-verbatim children through `t()`, and the
  observer (`i18n-core.js:162-212`) walks everything not under `translate="no"`.
- **Fix:** apply the rule `writers_room.js:91-114` states — story text goes in `txt()` and its element
  carries `translate="no"`. `lorebooks.js:3607-3611` already does this for the refused-operations list.
  **Test:** a pin in the style of the Writers' Room ones.

### F15 — `Sonder.refresh()` and `_unregister()` re-mount the open extension view and every composer control; the guide says refresh "redraw[s] the sidebar and transcript"

- **Severity:** INPUT-LOSS plus STALE-DOC. **Confidence:** CONFIRMED (read).
- **Where:**
  - `extensions.js:458-464`: `refresh()` calls `renderSide`, `renderChat`, `_renderTopBar`,
    `_renderComposer` and `_renderView`.
  - `:530-546`: `_renderView` removes `#ext-view` and calls `render(container)` again.
  - `:593-595`: `_unregister` re-renders all of them.
  - Callers: `settings.js:3990`, `:4007` and `:4030`, and `extensions.js:173` (after every module
    `register`). The guide: `docs/guides/EXTENSIONS.md:1497`.
- **Failure:** extension B's full-window view is open with typed input. Any of these re-creates the view
  from scratch, losing input and scroll: enabling or disabling another extension, a module extension
  finishing its async `register` after boot, or a third extension hitting three strikes. `render` runs
  again with no teardown signal, so an interval B started inside it now runs twice.
- **Fix:** re-render only the registry that changed, and never re-mount a view whose registration is
  unchanged. Add an optional `unmount(container)` for views and composer controls. Correct §7.1 of the
  guide. **Test:** a browser test — open a view, call `Sonder.refresh()`, assert the same container node.

### F16 — The three-strikes toast says "was disabled", but the extension stays enabled server-side

- **Severity:** STALE-DOC (user-facing copy). **Confidence:** CONFIRMED (read).
- **Where:** `extensions.js:79-83` calls `_unregister(owner)` and then
  `` toast(`Extension "${owner}" was disabled after repeated errors.`, "err") ``. No API call is made, so
  its pipeline stages keep running every turn and the 🧩 menu still shows it as enabled.
- **Fix:** say what actually happened ("its interface was removed for this session; it is still enabled —
  disable it under 🧩"), or POST disable after the host confirms.

### F17 — The workspace's "Generate entries" dialog writes English prompt directives in the browser, and a second dialog for the same route sends the bare prompt

- **Severity:** LANG-PACK. **Confidence:** CONFIRMED that the text is English and client-side; the effect on
  output was not measured.
- **Where:**
  - `lorebooks.js:2498-2541` `buildDirectLoreRequest`: seven English "focus" paragraphs plus a
    duplicate-avoidance sentence, sent as `{prompt}`.
  - `editors.js:1060-1074` `generateLoreModal`, used by `settings.js:1393` (the Cast › Lorebooks ✨
    button), posts the raw textarea to the same `POST /api/lorebooks/{id}/generate`.
  - AGENTS.md's routing table puts prompt text in `language_packs/<id>/cards/system_prompts/`.
- **Failure:** a Japanese story's generation is given English instructions as its request. The "Avoid
  duplicate subjects and preserve existing entries" toggle (`:2320-2326`, `:2371-2373`) only swaps an English
  sentence; nothing deterministic changes. The two buttons for one route tell the model different things.
  *Outside my files:* `lore_generate` (`web/app.py:4079-4084`) opens no `language_scope`, while its sibling
  `generate_plan` (`:3170-3172`) does.
- **Fix:** send `focus` and `preserve_existing` as fields, move the paragraphs into the
  `generator_lorebook` card in both packs, and have the Cast-tab button open the same dialog. **Test:** the
  pack-parity tests then cover the moved text.

### F18 — A third browser copy of LOREBOOK_TYPES has already drifted, and `loreSelect` silently selects the first option for a value outside its list

- **Severity:** DEAD / drift, with latent CORRUPTION. **Confidence:** CONFIRMED (the two lists diffed);
  reachability is low.
- **Where:** the fallback at `lorebooks.js:1222-1233` lists 7 types; `mind/memory_common.py:41-44` has 8
  (it adds `vehicle`). `:1636-1639` falls back to `["general"]` for the same field. `loreSelect`
  (`:252-273`) marks no option selected when the value is missing, so the browser shows the first one.
- **Failure:** this only happens when `S.boot.lorebook_types` is absent — the cached-JavaScript case the
  file's header gives as the reason the fallbacks exist. A vehicle book's Book tab then shows "general", and
  Save PUTs `book_type: "general"`, silently re-typing it. Vehicle books carry engine behaviour
  (`tests/test_vehicle_lorebooks.py`).
- **Fix:** one `lorebookTypes()` reader, like `inheritanceModes()`, with a fallback that
  `tests/test_card_editor_vocabularies.py` holds equal to the Python list. Make `loreSelect` keep an
  unknown stored value as an extra option. **Test:** extend the vocabulary-equality test.

### F19 — The Writers' Room clears the note before sending and never restores it on a refusal or network error

- **Severity:** INPUT-LOSS. **Confidence:** CONFIRMED (read).
- **Where:** `writers_room.js:334` `box.value = "";`, then `:339-343`
  `try { await roomStream(text); } catch (error) { toast(...) }`. `web/room_routes.py:91-98` refuses before
  the stream starts (404 for a missing frame or story, 400).
- **Failure:** the server restarts while the host types a long brief. Send shows "Could not reach the
  server…" and the note is gone.
- **Fix:** restore `box.value = text` in the catch when no `room_message` event arrived. **Test:** a browser
  test with a routed 500.

### F20 — Dead code in lorebooks.js

- **Severity:** DEAD. **Confidence:** CONFIRMED (grep over `static/`, `tests/`, `browser_tests/`, `tools/`).
- **Where:**
  - `loreUI.plan` (`:49`) has no reader or writer; the plan lives on `state.plan`.
  - `loreBookLabel` (`:223-225`) has no caller anywhere.
  - `addPlanGroup`'s `rerender` parameter (`:3715`) is passed three times (`:3507`, `:3521`, `:3539`) and
    never used.
- **Fix:** delete them.

### F21 — The autoplay "unlock" element is never played; the comments credit it with unlocking audio

- **Severity:** DEAD plus STALE-DOC. **Confidence:** CONFIRMED that the element is dead; PLAUSIBLE for the
  WebKit loop (not run).
- **Where:**
  - `ambience.js:123-129`: `ambiencePlayers()` creates `AMB.primed`. Its only caller is `:1048`; it is
    muted at `:139`; nothing ever calls `play()` on it.
  - The comments at `:123-125` and `:1045-1047` say this click "unlocks" audio.
  - Real playback starts in `begin()` after `canplay` (`:386-417`), outside any gesture, and the
    pointerdown unlock (`:431-442`) re-enters that same async path.
- **Failure:** in engines that need transient activation per element (WebKit), a refused start re-arms on
  every click, re-creating and re-downloading the layers without ever playing.
- **Fix:** either delete `primed` and the comments, or really unlock — in the toggle and unlock handlers,
  synchronously `play()` a silent element (or resume an AudioContext) before any await.

### F22 — docs/guides/FEATURES.md:712-713 describes a backdrop panel the code no longer draws

- **Severity:** STALE-DOC. **Confidence:** CONFIRMED (read).
- **Where:** FEATURES.md says "the prose on its own near-opaque panel, tuned from the image's own
  brightness". `backdrops.js:44-64` uses a fixed veil (`BD_VEIL = 0.62`, "a fixed strength") and a panel
  at 0.34-0.50 opacity ("roughly 60% transparent"); only the panel tint follows the image's luminance
  (`:107-114`).
- **Fix:** rewrite the bullet.

### F23 — weather-fx's SVG markup is published as UI messages in both packs

- **Severity:** DEAD (catalog). **Confidence:** CONFIRMED (`en/ui.json` holds 3 such keys).
- **Where:** `weather-fx.js:574-582`. The keys are `'<svg width="100%" height="100%" viewBox="0 0'`,
  `'" stroke-width="1.2"/>'` and the `preserveAspectRatio…` fragment, each "translated" as itself. Nothing
  ever looks them up.
- **Fix:** build the bolt with `createElementNS`, or have `_message` reject markup.

### F24 — Lorebook cycles: the client offers them, only the server refuses, and the Book save is not atomic

- **Severity:** LOGIC (low). **Confidence:** CONFIRMED (the server refusal by snippet).
- **Where:** `lorebooks.js:1241-1243`
  `compatibleParents = state.books.filter(candidate => candidate.id !== book.id)` offers descendants. The
  drag handlers refuse only self (`:405`, `:1032`). `:1315-1341` PUTs first and moves second.
- **Failure:** pick a descendant as Parent and Save. The PUT (name, type, summary, scope, order) commits,
  then the move returns 400 "would create a cycle". The error toast reads as if nothing was saved, and the
  view is not refreshed.
- **Verified:** snippet — `move_lorebook(A, C)` with C a grandchild of A raises
  `ValueError: Cannot move lorebook: would create a cycle`. A grep shows no test in `tests/` calls
  `would_create_book_cycle` or tries a cyclic move.
- **Fix:** exclude descendants from the select (walk `parent_id` as `loreVisibleIds` does), and move first
  or send the parent in the PUT. **Test:** `POST /api/lorebooks/{a}/move {parent_id: c}` → 400.

## Efficiency

1. **E1 — `refreshLoreUI` (`lorebooks.js:1720-1723`) after every lore edit.** Hot: once per user action in
   the workspace (entry save, add, delete or revert; link save, create or delete; move, reorder, canon,
   apply). Each call does `boot()`, which:
   - downloads `/api/bootstrap` (`web/app.py:2017-2020` sends every character's and persona's full sheet,
     every library book and every chat — measured `mode=ro` on the owner's DB: 70 characters with 890 KiB
     of sheet JSON, 19 personas with 56 KiB, 154 chats);
   - walks the whole document for i18n (`app.js:45`);
   - rebuilds the observer and re-renders the sidebar.

   It then re-fetches the workspace (2-3 GETs) and rebuilds the tree, every entry card and the
   relationship panel. **Gain:** large. Patch locally — replace the one saved card from the PUT response,
   and edit `S.boot.lorebooks` for a move — and call `boot()` only when book identity changes (create,
   delete, rename).
2. **E2 — Every entry card is built in full even while collapsed** (`lorebooks.js:1863-1865`, `1883-2261`).
   Each card is about 70 elements including `<option>`s, plus 3-4 `JSON.parse` calls. The largest library
   book in the owner's DB has 310 entries, so about 20k elements are built — and localized by the observer
   — on every E1 refresh and every debounced search. **Gain:** about 90% — build the card body on the
   first `toggle` of the `<details>`.
3. **E3 — `Sonder.refresh()` (`extensions.js:458-464`) re-renders the whole transcript.** `renderChat`
   (`chat.js:582-595`) rebuilds `#msgs` and clears the backdrop and ambience per-turn caches, which then
   re-fetch. It runs once per ES-module extension at boot (`:173`) and after every enable, disable, update
   or remove. **Gain:** proportional to transcript length × module extensions. Refresh only the changed
   registry.
4. **E4 — The Writers' Room rebuilds the whole thread once per animation frame while a reply streams**
   (`writers_room.js:451-484`, `545-578`). A 60-message page is rebuilt up to 60 times a second for the
   length of the reply. **Gain:** update only `roomLiveNode` during streaming, and rebuild the thread on
   `room_message`/`room_done`.
5. **E5 — The plan preview renders the plan JSON twice** — the raw `<pre>` at `:3550` plus one `<pre>` per
   op at `:3774` — and rebuilds everything on Accept all / Reject all (`:3632`, `:3646`). Small to moderate
   for 200-entry plans.
6. **E6 — Obsolete polls survive a story switch:** ambience polls for up to 75 s (`ambience.js:452-462`),
   backdrops for up to 210 s (`backdrops.js:196-205`), and their toasts can surface in the next story. Small.

## Already registered

- **UNBUILT_IDENTITY §1.104** — the persona has no per-story copy. The client side: `personaEditor`'s Name
  is editable with no warning (`editors.js:805`); the server's `persona_edit` (`web/app.py:3916-3923`) has
  none of `char_edit`'s handling. Not counted as a finding.
- **UNBUILT_PLATFORM §6.2** — `Sonder._unload` cannot undo side effects (timers, document listeners,
  globals). F15 is a different defect: re-mounting while an extension is still enabled.
- **UNBUILT_PERCEPTION §2.11** (weather rendering limits) and **§2.12** (ambience capped at three layers, no
  Web Audio).
- **UNBUILT_PLANNING §2.35, bullet "The recap cites what it read" — the register looks STALE.** Both
  "remaining" halves appear built: the Planner is handed `CONTRACT_TEXT` (`agents/story_planner.py:561-566`),
  the panel renders unsupported claims among the proposals (`writers_room.js:595-637`), and
  `browser_tests/test_writers_room_citations.py` covers it. The register entry should be updated.
- **Cross-reference (not an UNBUILT entry):** the server-side CSRF on `/api/extensions/*` is
  `audits/web_routes_extensions.md` F1. Q4 above gives the client's half.

## Structure notes

**SPLIT NOTES — `lorebooks.js` (3,823 lines).**

Natural sections:

| Lines | Section | Contents |
|---|---|---|
| 1-303 | vocabulary + pure helpers | `LORE_INHERITANCE_MODES_FALLBACK`, `DEFAULT_LORE_LINK_TYPES`, `loreUI`, `loreBookTypeIcon`, `inheritanceModes`, `KNOWLEDGE_*_FALLBACK`, `knowledgeTags/Ranges`, `loreLinkTypes`, `normalizeLoreBook`, `loreOwnershipKey`, `loreRootBooks`, `loreBooksByParent`, `loreBookMatches`, `loreVisibleIds`, `loreBookLabel` (dead), `parseStoredJSON`, `loreField`, `loreSelect`, `loreBookOptions` |
| 305-502 | library sidebar | `renderLoreLibrarySidebar` |
| 504-612 | data loading | `loreStoryQuery`, `loreBookIsLibrary`, `loadLoreWorkspaceData`, `collectLoreLinkTargets` |
| 614-873 | workspace shell | `loreWorkspaceVisible`, `renderLoreWorkspaceBody`, `openLoreWorkspace`, `renderLoreInspector`, `buildLoreWorkspace` |
| 875-1210 | workspace tree | `renderWorkspaceTree` (one 335-line function) |
| 1212-1723 | book metadata + tree ops | `renderLoreBookEditor` (325 lines), `moveLoreBook`, `reorderLoreBook`, `promoteLoreBook`, `demoteLoreBook`, `createSiblingLoreBook`, `createLoreBookDialog`, `refreshLoreUI` |
| 1725-2267 | entry editor | `renderLoreEntries`, `buildLoreEntryCard` (379 lines), `splitNumberList` |
| 2269-2541 | direct generation | `reinterpretLoreBook`, `generateLoreEntriesPrompt`, `buildDirectLoreRequest` |
| 2543-2992 | relationships | `renderRelationshipOverview`, `renderLoreRelationshipEditor`, `renderRelationshipList`, `showNewRelationshipForm` |
| 2994-3823 | advanced generator | `renderLoreGenerator`, `adoptGeneratorPlan`, `generatorPlanMessage`, `loreGenAgo`, `refreshLoreGenRecovery`, `normalizeGeneratorPlan`, `renderLorePlanPreview`, `planStat`, `renderAnalysisSection`, `addPlanGroup`, `stripPlanUIFields`, `acceptedGeneratorPlan` |

- **Globals other files call:**
  - `settings.js`: `loreBookTypeIcon`, `normalizeLoreBook`, `loreRootBooks`, `loreBooksByParent`,
    `openLoreWorkspace`.
  - `app.js`: `renderLoreLibrarySidebar`, `openLoreWorkspace`.
  - `editors.js`: `openLoreWorkspace` (at `:1030` and `:1069`).

  All of these sit in sections 1-4 and 6.
- **lorebooks.js calls out to:** `components.js` (`el`, `txt`, `modal`, `closeModal`, `modalOwnership`,
  `confirmModal`, `promptModal`, `toast`, `backgroundTask`, `buttonTask`, `loadingBlock`, `emptyState`,
  `openLivedLocationDialog`); `utils.js` (`api`, `splitCL`, `numOr`, `$`); `editors.js` (`importModal`,
  `exportLorebook`); `app.js` (`boot`, `renderSide`).
- **Parse-time calls:** none. The top level is `const` initialisers and function declarations only;
  `loreUI` holds two `new Set()`.
- **Tests that read `static/js/lorebooks.js` by path and pin its text:**
  - `test_frontend_lorebook_tree.py:32/46/52` (`function loreRootBooks(books)` appears once; the inline
    missing-parent rule) and `:126` (lorebooks.js loads before settings.js).
  - `test_frontend_server_vocabularies.py:34/71-72`.
  - `test_card_editor_vocabularies.py:51/133-136` (the three fallback arrays).
  - `test_frontend_state_guards.py:16/155-165` (the `renderLoreWorkspaceBody` → `openLoreWorkspace`
    block, in that order).
  - `test_host_settings_surface.py:31/172-174` (the canon POST/DELETE strings).
  - `test_frontend_global_namespace.py:103` (the shared `?v=` revision) and its check that no top-level
    name is declared in two files — that check is what guards a split, since `tools/project_check.py`
    scans JS only for patch debris.
- **Proposed split** (4 files). Only function declarations move. Every `const` stays in the core file: a
  browser holding a cached old lorebooks.js beside a new part file would otherwise redeclare a `const`,
  which is a SyntaxError that drops the whole second file.
  1. `lorebooks.js` — core, lines 1-1723 (about 1,720 lines): vocabulary, helpers, sidebar, data, shell,
     tree, book editor and tree ops, `refreshLoreUI`. Every test pin stays where it is. Load position
     unchanged (after editors.js).
  2. `lore_entries.js` — lines 1725-2541 (about 815): entry list and card, direct generation, reinterpret.
     Load immediately after lorebooks.js.
  3. `lore_relations.js` — lines 2543-2992 (about 450): relationship overview, editor and new-link form.
  4. `lore_generator.js` — lines 2994-3823 (about 830): advanced generator, recovery, plan preview. Load
     before backdrops.js.

  Every cross-file reference is resolved when called, not at load (`renderLoreInspector`'s tab table and
  `buildLoreWorkspace`'s `renderRelationshipOverview`), so files 2-4 may load in any order as long as they
  precede settings.js and app.js. The same commit must add the three `<script>` tags with the same `?v=`
  revision, bump that revision, and extend the tuple at `test_frontend_global_namespace.py:103`. The
  harvester globs `static/js/*.js`, so the catalog needs no change. Merging files 3 and 4 gives the 3-file
  variant.
- **editors.js:** `charEditor` (`373-787`, 415 lines) is a monolith in miniature. Its seams: field
  construction `384-495`, fill buttons `499-555`, layout `557-660`, save serializer `662-785`.
  `personaEditor` (`789-914`) duplicates the identity, attire and embodiment widgets, the 12-line attire
  help paragraph (`586-597` is verbatim `859-870`) and the embodiment serializer (`688-702` against
  `895-902`). A shared `embodimentWidgets(sheet)` / `readEmbodiment(f)` pair is the seam, and the natural
  home for F4's full-draft builder.
- **Module-level mutable state and its writers:**
  - lorebooks `loreUI` — written by the sidebar, tree, inspector, entry list and render body.
  - writers_room `ROOM`, `roomRenderFrame`, `roomRenderKeepScroll`.
  - extensions `Sonder._*` registries (`register*`, `_unregister`, `notify`, `_fault`) and `_owner`
    (begin/end and the facade).
  - ambience `AMB` (`ambienceForTurn`, `playAmbience`, the toggles, the panel), `AMB_ONESHOTS`,
    `_ambienceUnlockArmed`.
  - backdrops `BD`, weather-fx `WFX`, chime `CHIME`.
- **Parse-time side effects:**
  - `ambience.js:1085-1095` — storage reads and four `$()` bindings, unguarded (F1).
  - `backdrops.js:430` — `$("#b-backdrop").onclick`, unguarded.
  - `chime.js:36-42` (F1) and `:178-179`.
  - `weather-fx.js:616-638` — document and window listeners.
  - `writers_room.js:790-799` — an IIFE: guarded storage, DOM build, resize listener.
  - `extensions.js:661` — `window.Sonder`.
  - lorebooks.js and editors.js: none.
- **Pattern:** async click handlers without `buttonTask`, so nothing stops a double submit. Errors are not
  silent: they reach the global unhandled-rejection toast (`app.js:1200-1204`). Sites: `lorebooks.js:1759`
  (+ Entry — a double click makes two "New entry" rows), `:2218`, `:2241`, `:2809`, `:2834`, `:2960`;
  `ambience.js:966`, `:1028`.

## Docs checked

- **CLAUDE.md "never permit a card edit to rekey the in-story identity name or uid"** — HOLDS for
  characters: the client disables Name, the server returns 400 (`web/app.py:5418-5428`), and a
  reusable-card rename gives each attachment its card first (`:3815-3836`). Personas are registered
  (§1.104).
- **CLAUDE.md "`seed_initial_attire` … no card read or edit may overwrite clothing already changed"** —
  HOLDS (`story/scene.py:69-71`; no card route seeds).
- **CLAUDE.md "`character_card_warnings` … runs on all ten surfaces"** — HOLDS on the server; the browser
  shows them on 9 of 10 (F10).
- **CLAUDE.md / AGENTS.md frontend load order** — HOLDS (`static/index.html` matches exactly).
- **AGENTS.md "capabilities are DISCLOSURE for the consent dialog, never enforcement"** — HOLDS, but the
  Update path skips the disclosure moment entirely (F2).
- **AGENTS.md routing: prompt TEXT lives in `language_packs/<id>/cards/system_prompts/`** — VIOLATED by
  `buildDirectLoreRequest` (F17).
- **FEATURES.md "an entry added from inside a story lands in the story's canon book"** — PARTIAL: true for
  + Entry, false for Generate entries (F6).
- **FEATURES.md "near-opaque panel, tuned from the image's own brightness"** — STALE (F22).
- **docs/guides/EXTENSIONS.md §7.1 `refresh()` "redraw the sidebar and transcript"** — INCOMPLETE (F15).
- **`lorebooks.js:506-510` "Edits made here write the story's overlay, never the shared library"** —
  PARTIAL (F6).
- **`writers_room.js:27-31` "Every stored preference … inside try/catch"** — HOLDS (`142-150`).
- **`weather-fx.js:41-43` "costs nothing when there is no weather … tears them down"** — HOLDS
  (`393-404`).
- **`ambience.js:18-20` "if playback is refused anyway, the next click anywhere resumes it"** — PARTIAL:
  resume works in sticky-activation engines, but the `primed` element the comments credit does nothing
  (F21).
- **`backdrops.js:14-16` "With it off … never commissions one"** — HOLDS (`314`).
- **`extensions.js:11-17` "NOTHING it does may take the reader's story down"** — HOLDS for throws (`_safe`,
  three strikes); F15 is the one way a sibling extension's view is damaged.
- **`editors.js:5-7` "Nothing is written … the author's ordinary Save is still what commits it"** —
  VIOLATED by Quick start after a fill (F5).
