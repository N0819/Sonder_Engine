# Frontend audit — `static/js/settings.js` and `static/js/world_browser.js`

2026-11-01, branch `worktree-jev-character-tracking` at `84f3de23`. The two audited
files and every server file cited below were unmodified in the working tree for the
whole audit. Another process was rewriting `agents/common*.py`, `AGENTS.md`,
`CLAUDE.md` and `docs/CODE_MAP.md` meanwhile, so AGENTS.md is cited from `HEAD`
(`git show HEAD:AGENTS.md`).

## Scope read

**Read in full, line by line:** `static/js/settings.js` 1-4167; `static/js/world_browser.js` 1-3995.

**Read in part, for the contracts these two files call (not audited themselves):**
- `static/js/utils.js` 1-266 (`t`, `api`, `streamPost`); `static/js/i18n-core.js` 1-250 (template rules, the DOM observer); `static/js/components.js` 1-170, 195-250, 515-700, 1207-1356 (`el`/`txt`, `modal`, `confirmModal`, `toast`, `backgroundTask`/`buttonTask`, form helpers, `fetchModels`, `modelCombobox`); `static/js/app.js` `boot()` and the error nets 1185-1221; `static/js/chat.js` 140-195 and 2068-2160 (vitals callers, pipeline-drawer map); `static/index.html` script and button lines.
- Server routes the two files call: `web/world_routes.py` 1-120, 340-548, 690-875, 1300-1410, 1459-1600, 1720-1830 and the return shape of every write; `web/app.py` 677-688, 1795-2110 (bootstrap), 2110-2370 (agent models, image/decision model, exemplars, debug capture, backdrops, ambience, research, OpenRouter routing), 3005-3032, 3293-3455 (providers), 3873-3891, 4359-4373, 5884-5928, 5964-6060, 6074-6097, 6222-6245.
- `llm/providers.py` 927-946 (`DEFAULT_BASES`), 1511-1600 (routing normaliser), 2022-2124 (`ROLES`), 5236-5255; `persist/checkpoints.py` 1325-1366; `mind/memory_vectors.py` 30-115; `world/spatial_fov.py` 595-640, 930-975; `world/spatial_barriers.py` 469-499, 558; `tools/extract_ui_catalog.py` (whole); `dressing/ambience.py:96`; `web/guest_access.py` TTLs; `web/auth_routes.py:42-45`.
- `static/styles.css`: only the modal and World Browser rules (433-440, 1017-1105, 1208, 1316), for F11. The rest of the stylesheet was not read.

**Run:** `node --check` on both files (both parse). A node probe that loads the shipped
`static/js/i18n-core.js` and `language_packs/ja/ui.json` and translates the exact
strings settings.js builds (`<review scratch>/fsw/i18n_probe.js`). A node probe running wbPlanFixture's branch
order against the layout solver's 54 fixture kinds (`<review scratch>/fsw/fixture_probe.js`). `.venv/bin/python`
snippets: `web.world_routes._apply_exits` on a dict scene; the server vocabularies;
read-only (`mode=ro`) reads of `engine.db` for checkpoint sizes and JSON parse rate, and for
scene names that collide with catalog keys. No test was run: no hypothesis needed one, and
nothing failed.

**Where each assignment question is answered:** (1) secrets → Structure notes § Secrets, F13, F15;
(2) registry duplication → Structure notes § Registry pairs, F8, F12, F14; (3) writes, 409s,
concurrency → Structure notes § How writes behave, F1, F2, F4, F9, F10, F11, F16; (4) XSS →
Structure notes § XSS sinks (none found); (5) performance → F3, Efficiency; (6) i18n → F7, F17;
(7) split notes → Structure notes § Split notes.

## Findings

20 findings: **CORRUPTION 4** (F1, F2, F5, F10), **PERF 1** (F3), **SILENT-NOOP 7** (F4, F7, F9,
F11, F14, F15, F16), **WRONG-SCENE 2** (F6, F17), **DEAD 3** (F12, F13, F18), **STALE-DOC 3**
(F8, F19, F20). No LEAK (both surfaces are host-only: nothing here reaches a mind's payload
except through the engine-normalised scene writes), no CRASH.

### F1 — Undo re-issues a whole-field snapshot: over card edits made after the drag, and onto a different room

- **Severity:** CORRUPTION. **Confidence:** CONFIRMED (traced end to end; not run in a browser).
- **Where:**
  - `static/js/world_browser.js:1850-1862`, the stack and its contract:
    ```js
    // keeps the inverse of the write just made; the map bar's Undo button runs
    // it and forgets it. A write from the card clears it, since the card's own
    // value is now what the server holds.
    ```
  - The remembered inverses are whole-field snapshots re-issued through the SELECTED room:
    `2538` `ctx.patchRoom({ parts: before }, …)`, `2572` `{ extent: before }`, `2591` `{ anchors: before }`,
    `2643` `ctx.patchDoorway(d.to, { offset: d.offset }, …)`; and `ctx.patchRoom` / `ctx.patchDoorway`
    read the room at CALL time (`3458-3460`: ``/rooms/${encodeURIComponent(state.selected)}``, `3474-3476`).
  - `ctx.undo.clear()` is called only at `3499, 3508, 3536, 3548, 3564, 3571, 3639` (moves/removals) and
    in `loadRoom` (`3924`) — never by a card write (`wbWrite` 204-214, `replaceCard` 3430-3437, `refresh` 3438).
  - `3425` `showRoom: id => { state.selected = id; selectTab("rooms"); }` sets the room BEFORE
    `selectTab` → `loadRoom(state.selected)`, whose reset is guarded by `if (id !== state.selected)` (3919).
- **Failure (a), over a card edit:** drag anchor `hearth` to the N wall (Undo = PATCH anchors S0). On the
  card, set `bar`'s height to `waist` (PATCH anchors S1; Undo untouched). Click Undo → `PATCH {anchors: S0}`:
  `bar`'s height is reverted too, and the toast says only "Undid: Moved hearth to the N wall". Same for
  parts (2538) and the extent (2572) after a card edit of them.
- **Failure (b), onto another room:** drag in room A; open the Bodies tab; click any body's room link to
  room B (`1583`, `1543` → `ctx.showRoom`). Room B's map bar still offers Undo (`renderMapBar` 3682-3684)
  titled with A's label. Clicking it sends `PATCH /rooms/B {anchors: <A's snapshot>}`; `_apply_anchors`
  (`web/world_routes.py:1553-1598`, ending `room["anchors"] = out`) REPLACES B's anchors and accepts every
  wall-placed one (only a `cell` is checked against B's grid). Room B now holds room A's anchors. The extent
  undo resizes B to A's old extent; the doorway undo moves B's doorway to the same `to`, when B has one.
- **Fix:** capture the room id when the inverse is remembered and refuse (or target) that room explicitly;
  clear the stack on every successful write that is not the remembered one (in `wbWrite`'s success path);
  route `showRoom` through `loadRoom(id)`. Correct the comment and UNBUILT_PLANNING §2.26's "a write from the
  card clears it".
- **Test:** `browser_tests/test_world_browser.py` — (a) drag an anchor, change another anchor's height on the
  card, assert no `.wb-undo` (or that Undo leaves the height); (b) drag in room A, Bodies tab, follow a body
  into room B, assert no `.wb-undo`.

### F2 — The structured editors write whole lists from the card's last read: a beat's newer doorway, anchors, parts or garments are deleted or reverted

- **Severity:** CORRUPTION. **Confidence:** CONFIRMED (snippet).
- **Where (client):** exits `world_browser.js:818-820, 830, 874-876` (`stored.map(asExit)` built from the
  rendered `slice.record.adjacent`), windows `922-923, 934`; anchors `978-987, 1007-1010, 1066-1068, 2602-2604,
  3588-3590` (`copy()` of the rendered `slice.record.anchors`); parts `601-602, 2535`; attire `1438-1444`
  (this body's entry rebuilt from the render-time `entry`).
- **Where (server):** `web/world_routes.py:1459-1551` `_apply_exits` ("Replace the room's exits": an edge
  missing from the list loses its reciprocal edge and its passage record, `1510-1523`); `1553-1598`
  `_apply_anchors` (`room["anchors"] = out`); `web/app.py:5918-5926` `attire_put` replaces the named entry.
  No route carries a revision or precondition (`room_patch` 1749-1816).
- **When the card is stale:** the dialog is not gated on the story being idle (the Raw tab says so,
  `1648-1652`) — a turn already running when the dialog opened (its writes get 409 until it ends, and the
  re-read after a 409 reads the pre-commit scene), a second tab, or the Writers' Room's out-of-band package
  operations (web_routes audit F5).
- **Snippet** (`.venv/bin/python`, pure function, no DB):
  ```
  rendered = [{'to': 'parlour', 'barrier': 'open', 'dir': 'n'}]            # what the card read
  scene: hall.adjacent = [parlour, cellar(closed_door, e)]                  # a beat added cellar since
  _apply_exits(scene, 'hall', scene['rooms']['hall'], [dict(rendered[0], dir='ne')])
  hall   -> ['parlour']
  cellar -> []
  ```
- **Failure:** the host changes the parlour exit's bearing; the doorway the beat built to the cellar is
  removed from BOTH rooms and its passage record popped, under a "Saved." toast. Same shape: an anchor the
  beat added is deleted by any anchor edit in that room; a garment the beat took off is put back on by an
  edit to that body's notes. The Raw JSON tab guards exactly this window (re-read at save, compare, ask:
  `1683-1708`); the structured editors do not.
- **Fix (the class):** send a token of what was read with every list write (a hash of `record.adjacent` /
  `anchors` / `parts`, or of the body's entry) and answer 409 "this room changed since you opened it"; or
  write per item — the doorway routes (`POST`/`PATCH`/`DELETE /doorways`) already exist for one edge, so the
  card's barrier, bearing and remove controls need not send the room's full exit list. Per-item writes also
  confine a refused value to its own row (see Already registered, F44).
- **Test:** `tests/test_world_routes.py` — PATCH exits with a token taken before an edge was added → 409, and
  the edge survives.

### F3 — The checkpoint-conversion poll parses the whole checkpoint store every second, overlapping, and never stops when the dialog closes

- **Severity:** PERF (availability). **Confidence:** CONFIRMED (code; scan cost measured read-only).
- **Where:** `static/js/settings.js:3438-3466`:
  ```js
  const render = async () => {
    let d;
    try { d = await api("GET", "/api/maintenance/checkpoints"); }
    …
    if (p.running) {
      …
      if (!timer) timer = setInterval(render, 1000);
      return;
    }
    if (timer) { clearInterval(timer); timer = null; }
  ```
  Built by `renderUpdateStatus` (3569, 3603) on every update check that succeeds. Server:
  `web/app.py:3005-3019` always calls `checkpoint_storage_status()`, which "selects and `json.loads` every
  checkpoint blob in scope" (`persist/checkpoints.py:1339-1347, 1353-1364`). The route's docstring still says
  "Safe to poll: the status scan is sizes plus a one-entry probe per blob, not a full parse"
  (`web/app.py:3011-3012`).
- **Measured** on the owner's `engine.db` (`mode=ro`): 4,432 checkpoints, 2,814,489,774 characters of
  blob; the `length(blob)` pass alone took 14.8 s; `json.loads` ran at 83.5 MB/s over a 40-blob sample,
  so ~34 s more — **about 49 s per GET**.
- **Failure:** (1) every "⬆ Update" whose check succeeds costs one ~49 s full-store parse while the card
  reads "Checking checkpoint storage…"; "Convert now" costs another before it starts (`start_compaction`
  runs the same scan). (2) During a conversion the card issues a new ~49 s request every second without
  awaiting the previous one: about 49 in flight at steady state, enough to fill Starlette's default thread
  pool (40) so every synchronous route queues behind them, while the GIL-bound parses and the conversion
  slow one another. Closing the dialog does not stop it, and each reopen adds another interval. The sibling
  embedding poll was fixed for exactly this (`settings.js:2011-2016`: "Re-arming unconditionally kept a
  1.5s poll alive against a detached node"); this one was not.
- **Fix:** client — a `setTimeout` chain re-armed after each render resolves and only while
  `body.isConnected` (the embedding block's shape); server — return `progress` alone while a run is active
  and cache the scan on a write token; correct the docstring.
- **Test:** `browser_tests/test_checkpoint_compaction_ui.py` — close the dialog mid-run, assert no further
  GETs; and a run whose status call is slow issues at most one request at a time.

### F4 — Switching language while a turn runs: the story's refusal is shown in a toast the next line reloads away

- **Severity:** SILENT-NOOP. **Confidence:** CONFIRMED (reading).
- **Where:** `static/js/settings.js:3797-3817`:
  ```js
  } catch (e) {
    // A turn in flight refuses the change; the interface still moves.
    storyNote = " This story kept its language: " + e.message;
  }
  …
  toast(`Language changed.${storyNote}`, "ok");
  …
  try { sessionStorage.setItem(REOPEN_PROMPTS_KEY, "1"); } catch (e) {}
  return window.location.reload();
  ```
  Server: `web/app.py:4363` `_require_chat_idle(cid)` answers 409 while any pipeline of the chat runs.
- **Failure:** the host picks 日本語 during a beat. The interface and the prompt sheets switch; the story's
  PUT is refused; the toast that says so is destroyed by the reload on the next line (an `ok` toast is not
  mirrored to the console either, `components.js:546-547`); the Prompts menu reopens in Japanese; the
  story keeps English and nothing on screen says so. The note survives only when the interface language
  does not change (3820) — the less common case for a switch designed to move both together.
- **Fix:** carry the note across the reload beside `REOPEN_PROMPTS_KEY` and show it from
  `reopenPromptsIfRequested`; or refuse the whole switch while the open story is busy.
- **Test:** browser test with `/language` → 409 and `/ui-language` → 200: after the reload a warning toast
  names the language the story kept.

### F5 — Emptying a Dialogue-config number writes 0: promotion turns off and "max managed" drops to 1

- **Severity:** CORRUPTION (story configuration). **Confidence:** CONFIRMED.
- **Where:** `static/js/settings.js:516` `promote_after_addressed: +promoteAfter.value,` and `521-522`
  `max_managed: +maxManaged.value, max_reactors: +maxReactors.value`; `+""` is `0` (node). Server clamps:
  `web/app.py:6020-6021` promotion to [0, 99] — 0 means "never promotes anyone" (`settings.js:499`);
  `6240-6241` max_managed / max_reactors to at least 1.
- **The rule is stated two fields above and applied to two of the five integers:** `settings.js:294-303`
  "An emptied field saves what it showed, never 0" (`shownNumber`, used only at 517-518).
- **Failure:** a host clears "turns till auto-promotion" (3) to retype it and saves → promotion is off for
  the story under "Dialogue config saved."; clearing "max managed" (6) saves 1. (Emptied min/max lines or
  variance go out as `""` and come back as a 400 the global net shows — loud, but the background-config PUT
  after it is then skipped.)
- **Fix:** read every integer through `shownNumber` — the class, not three more fields.
- **Test:** a source pin that the dialogue save contains no `+<input>.value`, or a browser test emptying the field.

### F6 — "Add exit" on the room card defaults to `bars`, an impassable barrier

- **Severity:** WRONG-SCENE. **Confidence:** CONFIRMED.
- **Where:** `static/js/world_browser.js:869-870`:
  ```js
  const barrier = wbSelect(vocab.barriers, (vocab.barriers || [])[0] || "",
    { title: "Barrier", onchange: () => {} });
  ```
  `vocab.barriers` is `sorted(_VALID_BARRIERS)` (`web/world_routes.py:507`) = bars, closed_door, membrane,
  one_way_window, open, open_door, separated, unknown, wall, window; `_PASSABLE_BARRIERS = {"open",
  "open_door", "membrane"}` (`world/spatial_barriers.py:558`). The map's wall form chooses `open` on purpose
  (`3258`).
- **Failure:** a host joins two rooms from the card without touching the unlabelled select and gets a barred
  doorway nobody can walk through; the same act from the map yields an open one. The default came from an
  alphabetical sort, not a decision.
- **Fix:** one default for both add forms (`open` when the set holds it), stated once.
- **Test:** browser test or source pin that both forms pass the same default.

### F7 — English in the Japanese interface: sentences built with `+`, placeholders that swallow English, and labels the harvester rejects

- **Severity:** SILENT-NOOP (the pack's translation exists and never applies). **Confidence:** CONFIRMED (node probe).
- **Mechanism:** the catalog is harvested from string literals (`tools/extract_ui_catalog.py`); `t()` and the
  DOM observer match a text node's WHOLE trimmed text against a key or a `${}` template. A sentence built with
  `+` around a value is harvested as fragments that never match; a template whose placeholder holds English
  translates only its literal head; a lone lowercase token is refused by the harvester (`_message`'s
  `[a-z0-9_.:/-]+` rule) unless it sits in an option-label position.
- **Probe** (`node <review scratch>/fsw/i18n_probe.js`, shipped rules + `language_packs/ja/ui.json`):
  ```
  "Prompt caching on for OpenRouter."      => "プロンプトキャッシュon for OpenRouter."
  "Response limit saved: 20000 tokens."    => "応答制限を保存しました：20000 tokens."
  "Changing the embeddings model means …"  => "埋め込みモデルを変更すると、すでにすべてのメモリがstored has to be re-read …"
  "⚠ Paradox active: The crash"            => unchanged     "Reset to 20000"                 => unchanged
  "20000 is the recommended default"       => unchanged     "Values outside 1024–128000 …"   => unchanged
  "This link works once, … play as Mara. …" (whole invite paragraph)                            => unchanged
  "follow default", "reasoning: low", "style", "variance", "open", "revoke", "detach", "wall", "bare", "auto", "you" => unchanged
  ```
- **Sites.** Concatenation (the whole sentence stays English): `settings.js:1221-1224, 1672, 1819-1825` (the
  invite paragraph; its first fragment is in the ja pack as a broken sentence), `2000, 3442, 2033-2035,
  2066-2068, 2088, 2334, 2337, 2344, 2406, 3129` (`"reasoning: " + l` — `FORMAT_LABELS` at 3141-3150 was
  rewritten for exactly this and its sibling was not), `3241` (`"follow " + parent`), `3472, 3804`.
  Placeholder swallowing English: `2265-2266, 2329, 3179-3181`. Rejected lowercase labels: `506` "style",
  `509` "variance", `692` "auto", `877` "you", `1364` "canon", `1383` "open", `1809` "revoke", `1853` "detach",
  `4043` "local"; `world_browser.js:1030` "wall", `1045` "corner", `1466` "bare". Raw enum values shown as
  labels: `settings.js:752` (status), `1359` (book type), `1556`, `1675`, `1681` (paradox modes), `1919`
  (provenance), `2360` (sort); every World Browser select (`wbSelect`, `translate="no"` by design).
- **The enum-as-label half is unregistered** although `tools/extract_ui_catalog.py:407` says "Recorded in
  `docs/UNBUILT.md`" — no register mentions it.
- **Fix:** one string per sentence with `{var}` (`t("Reset to {n}", { n })`, the rule `settings.js:2781-2783`
  itself argues); whole literals per option (the `FORMAT_LABELS` shape) for effort and follow labels;
  capitalised strings for the lowercase buttons; authored labels with the enum as `value` for enum selects.
- **Test:** a project_check rule refusing `"<literal> " + <expr>` as an `el()`/`toast()` text argument; or run
  the probe over a list of runtime-built strings.

### F8 — The role help documents 11 of the 16 roles and calls every one a stage of the turn

- **Severity:** STALE-DOC. **Confidence:** CONFIRMED.
- **Where:** `static/js/settings.js:2814-2828`: "Setting only Default is enough to start playing … The rest let
  you assign a faster or cheaper model to a specific stage of each turn …", then entries for director, encoder,
  director_rooms, character_bg/mid/major, narrator, repair, utility, embeddings and the decision model.
  `providers.ROLES` (`llm/providers.py:2022-2124`, 16 printed) also has `skip_memory`, `story_planner`,
  `dramaturge`, `backdrop_prompt`, `ambience_prompt` — each commented "NEVER in the turn pipeline" or
  "out of band".
- **Failure:** five rows render (from `S.boot.roles`) with no explanation, under a sentence that tells a host
  lightening "a stage of each turn" that every row is one; nothing says story_planner and dramaturge run out
  of band at the Room's pace.
- **Fix:** ship a one-line description per role with `roles` in the bootstrap, from the comments that already
  live beside `ROLES`, and render the help from it.
- **Test:** pin that every `ROLES` member has a description.

### F9 — Controls that keep showing a value the server refused or never received

- **Severity:** SILENT-NOOP (low). **Confidence:** CONFIRMED (reading).
- The file states the rule (`settings.js:2254-2256`: "a box that reports what it asked for rather than what
  happened would show a state that is not real"), and three controls keep it (2229-2244, 2250-2271,
  `castRoomSelect` 1276-1308). These do not:
  - `723-726` persona select: `ps.onchange = () => api("PUT", "/api/chats/" + chatId, {…})`. A persona change
    during a turn is refused (`web/app.py:4384-4385`); the global net toasts it and the select keeps the new persona.
  - `1682-1685` paradox mode select; `2581-2588`, `2614-2620`, `2647-2653` the three global checkboxes
    (habituation, underneath, auto-promote); `710` the dialogue-colour swatch — none reverts on failure.
  - `2284` "↻ models": `fetchModels` (`components.js:1207-1211`) returns `[]` on ANY error and returns the
    cached list without refetching, so the button shows ✓ for a failed fetch and never refreshes a catalogue
    already cached (only a provider Save clears `S.models`).
  - `world_browser.js:1447` an emptied garment name is neither written nor reverted (the ledger keeps the
    name, the field stays blank); `578-586` an emptied extent side likewise.
- **Fix:** one helper — await the write, set the control from the answer, restore on failure (the
  `castRoomSelect` shape); for ↻, bypass the cache and report a failure.

### F10 — Settings forms write whole objects from the snapshot they rendered: with two tabs, the last writer silently wins

- **Severity:** CORRUPTION (configuration; low likelihood). **Confidence:** CONFIRMED (reading; no revision on any route).
- **Where:** the style guide (`settings.js:206-219`; "A PUT replaces the whole guide", 211-213); "Save all"
  (`3259-3350`, the whole agent-models map built from rendered rows); each provider row's Save (`2282`:
  name, kind and base URL as rendered — `2207-2210` already names "a rename typed in another tab" as the hazard
  for the cache box); prompt presets (`3735-3741`); exemplars (`2801-2808`); dialogue and background config
  (`511-523`).
- **Failure:** tab A sets the narrator to model X and saves; tab B, opened earlier, saves an unrelated row →
  the narrator is back on the old model under "Agent models saved."
- **Fix:** the Raw-tab pattern (re-read at save, compare the part the form owns, ask) or a revision token.

### F11 — Every World Browser write rebuilds the whole card: text typed into another field meanwhile is discarded, and on the refresh path the scroll collapses

- **Severity:** SILENT-NOOP. **Confidence:** PLAUSIBLE (traced; not run in a browser).
- **Where:** `replaceCard` → `wbRenderCard` (`world_browser.js:3430-3435`, `1224-1225` `host.innerHTML = ""`);
  `refresh` in the room zoom → `loadRoom` → `loadCard` (`3409`, `3897-3900`:
  `card.innerHTML = ""; card.append(el("div", …, "Loading…"))` across an `await`); the Bodies tab rebuilds
  every body (`1563-1564`). `wbText` commits on blur (`147`), so Tab from field A to B blurs A, and A's save
  rebuilds the card under B. `#modalbody` is the scroll container (`static/styles.css:440`).
- **Failure:** edit a pose's "detail", Tab, keep typing in "constraint": when the detail's write returns
  (a PUT plus four GETs), the card is rebuilt, the characters typed into "constraint" are gone and focus is on
  the page. On the refresh path the "Loading…" placeholder shrinks `#modalbody` while the slice loads, so the
  scroll position is clamped and the row being edited jumps away. The header promises "never a silent revert"
  (`77-81`); for every field except the one written, the rebuild is one.
- **Fix:** keep focus, selection and `scrollTop` across the rebuild (or patch only the written row), and never
  put a placeholder over a card that is being refreshed.
- **Test:** browser test typing into a second field while the first field's write is slowed.

### F12 — The bootstrap ships `ambience_licenses` and nothing reads it; settings.js types the three licences again

- **Severity:** DEAD (+ a duplicated vocabulary). **Confidence:** CONFIRMED (grep across `static/js`).
- **Where:** `web/app.py:2076` `"ambience_licenses": list(FREESOUND_LICENCES),` (also `_INSTALL_BLOCK_KEYS`,
  1809) — no reader in `static/js`. `static/js/settings.js:2689` and `2697-2698` hardcode
  `"Creative Commons 0"`, `"Attribution"`, `"Attribution NonCommercial"` (`dressing/ambience.py:96`). Equal
  today; the route drops unknown names silently (`web/app.py:2314-2316`), so a licence renamed server-side
  would quietly stop being requested.
- **Fix:** build the licence choice from `S.boot.ambience_licenses` (the B24 pattern), or drop the key.

### F13 — The Freesound key can never be cleared: `PUT /api/ambience`'s `clear_key` has no caller

- **Severity:** DEAD (a server parameter nothing passes) / missing control. **Confidence:** CONFIRMED (grep:
  `static/`, `tests/`, `browser_tests/`, `extensions/`).
- **Where:** `web/app.py:2311-2312` `if body.get("clear_key"): set_setting("freesound_key", "")` (docstring:
  "Clearing is explicit"); `static/js/settings.js:2682-2710` sends only `freesound_key` (blank keeps). The
  research block beside it has "Clear key" (2747-2753). Provider rows have no clear either (replace, or delete
  the provider).
- **Fix:** a "Clear key" button beside the Freesound field.

### F14 — Saving OpenRouter routing from the panel deletes a stored `order`

- **Severity:** SILENT-NOOP (configuration loss). **Confidence:** CONFIRMED.
- **Where:** `llm/providers.py:1524` `_ROUTING_LIST_KEYS = ("order", "only", "ignore")`; `PUT
  /api/openrouter_routing` rebuilds the block from the body alone (`web/app.py:2346-2357`);
  `static/js/settings.js:2433-2440` never sends `order` (the panel has no field for it).
- **Fix:** send the stored block's unrendered keys through, the dialogue route's own rule ("falls back to WHAT
  IS ALREADY STORED", `web/app.py:5967-5976`).

### F15 — Changing a provider's kind keeps the previous kind's base URL

- **Severity:** SILENT-NOOP (the connection points at the wrong host). **Confidence:** CONFIRMED (reading).
- **Where:** `static/js/settings.js:2197-2198` (kind select and base-URL input, no `onchange`), `2282` (Save
  sends both as rendered). Requests use the stored URL directly (`llm/providers.py:4374, 4958, 5210, 5243,
  5412` `prov["base_url"]`); `DEFAULT_BASES` applies only on create (`web/app.py:3321`).
- **Failure:** openai → anthropic keeps `https://api.openai.com/v1`; → claude_cli executes that string as the
  CLI path (`llm/providers.py:3719-3720`).
- **Fix:** on a kind change, replace a base URL that is empty or equals the old kind's preset with the new
  kind's preset.

### F16 — Two writes that report success after a step failed

- **Severity:** SILENT-NOOP. **Confidence:** CONFIRMED (reading).
- `static/js/world_browser.js:1684-1685` (Raw JSON save): `try { current = await api("GET", path); } catch (e) {
  current = null; }` then `if (current !== null && JSON.stringify(current) !== base)` — a failed re-read skips
  the stale-write question, and the PUT (a DELETE-and-rewrite of the world table, `1639-1641`) proceeds.
- `static/js/world_browser.js:3623-3628` (add a room through a wall): the doorway-offset PATCH ends in
  `.catch(() => null)` and the toast says "Added X through the N wall." — the doorway sits at its seeded place,
  not where the host clicked.
- **Fix:** a failed re-read is "cannot check — ask"; toast the offset failure.

### F17 — Names drawn on the room and structure maps (and in the settings panels) are translated when they equal an interface word

- **Severity:** WRONG-SCENE (display), latent. **Confidence:** PLAUSIBLE.
- **The class** is `components.js:1-12`'s ("a character named 'Cast'"): `el()` translates string children, and
  the observer translates any text node outside `translate="no"`. The World Browser's card and tree wrap names in
  `txt()` + `translate="no"`, and the storey plan sets it on its SVG (`world_browser.js:3099`) — but
  `wbRenderRoomMap`'s SVG (`1993-1997`) and `wbRenderStructureMap`'s (`2746-2750`) do not, and they draw names as
  text: `2085` (neighbour room), `2270` (anchor id), `2307` (thing), `2354` (body), `2842-2848` (room, occupants);
  the pipeline drawer's host (`chat.js:2077`) neither. settings.js passes names straight to `el()`: `721, 751, 797`
  (characters), `876, 1106` (bodies), `1355` (lorebooks), `1555, 1632` (frames), `1643, 1795, 1861` (personas),
  `1695` (fixed points), `1755` (presences), `1918, 1947, 1921, 1949` (names and memory gists), `330`.
- **Evidence:** under the ja pack `Storage` → 物置, `Window` → 窓, `Cast` → キャスト (probe). Exposure today:
  0 of 385 distinct room names across 145 scenes in the owner's DB equal a ja key.
- **Fix:** `translate="no"` on both map SVGs (one attribute each); `txt()` for data children in settings.js.

### F18 — wbPlanFixture draws every solver "barrel" as a counter; the barrel branch is unreachable for that kind

- **Severity:** DEAD (cosmetic). **Confidence:** CONFIRMED (probe).
- **Where:** `static/js/world_browser.js:3007` `} else if (is("bar", "counter", "desk", "workbench")) {` precedes
  `3013` `} else if (is("barrel", "pond", "spring", "pool", "well")) {`, and `is` matches substrings (`2983`).
  "barrel" is a layout-solver kind (`world/layout_solver.py:99`). Over the solver's 54 kinds, barrel is the only
  one drawn by a branch other than the one naming it. Ported from `tools/layout_lab/page.html:250, 256`.
- **Fix:** try exact names across all branches before substrings (or move the barrel branch above).

### F19 — World Browser documentation that no longer holds

- **Severity:** STALE-DOC. **Confidence:** CONFIRMED.
- `world_browser.js:1853-1854` "A write from the card clears it" (F1); the same sentence in UNBUILT_PLANNING §2.26.
- `world_browser.js:73-75` "NO CLOSED SET IS TYPED INTO THIS FILE" (AGENTS.md:532 "NO CLOSED SET IS TYPED INTO
  THE BROWSER"): the selects do read `vocab`, but the file types `WB_PLAN_GROUP` (2899-2906, room purposes), the
  fixture-kind lists (2984-3037), `wbFootprintLength` (1944-1948, a copy of `world/spatial_fov.py:605-606`, equal
  today) and the literals `"open"` (2167, 3140, 3258), `"cone"` (1200), `"ground"`/`"way"` (2916-2917).
- `world_browser.js:2029` `const range = ctx.vocab.extent || { min: 2, max: 24 };` — the engine's range is 2..96
  (`EXTENT_MAX_PACES`).
- AGENTS.md:532 "every attire edit is the WHOLE ledger through `attire_put`" — the editor sends one body's entry
  (`world_browser.js:1438-1444`; the route's own comment, `web/app.py:5899-5903`).
- `docs/guides/FEATURES.md:770-771` "(dragged into the room, it loses its wall and is placed by seed again)" — a
  drop on a non-wall cell pins the anchor (`world_browser.js:2617-2619`), as the same paragraph says two lines later.

### F20 — Guide and server sentences about the settings panel that the panel contradicts

- **Severity:** STALE-DOC. **Confidence:** CONFIRMED.
- `docs/guides/FEATURES.md:425-435` "World mechanisms, each with its own switch … the settings panel says what it
  actually runs as rather than what you selected" — no static file calls `/api/chats/{cid}/living_world`
  (`web/app.py:6074-6097`; its only callers are in `tests/test_living_world.py`), and the Dialogue panel says these
  are "Not settings" (`settings.js:440-446`).
- `web/app.py:4364-4366` "this route is issued on every style-guide save" — the only caller of `PUT
  /api/chats/{cid}/language` is the Prompts language switch (`settings.js:3799`); the style modal's language
  selects were removed (`settings.js:48-51`).
- `web/app.py:2141` "cheap enough to poll (two COUNTs plus an in-memory snapshot)" — `embedding_bank_status`
  makes a live embedding request first (`mind/memory_vectors.py:64`) and up to eight COUNTs (77-115); the panel
  polls it every 1.5 s during a rebuild (`settings.js:2016`).
- `web/app.py:3011-3012` "Safe to poll … not a full parse" (F3).

## Efficiency

Cheapest fix and largest gain first.

1. **The checkpoint status poll (F3).** Where: `settings.js:3438-3466` → `web/app.py:3005-3019` →
   `persist/checkpoints.py:1325-1366`. Hot: once per "⬆ Update" open (when the check succeeds), and once a
   second, overlapping, for the whole of a conversion. Measured ~49 s of server work per call on the owner's
   2.8 GB checkpoint store. Gain: a conversion stops starving the server; a glance at Updates stops costing a
   full-store parse. Fix: the `setTimeout`-while-connected shape (client) plus progress-only answers while a run
   is active (server).

2. **Opening ⚙ API fans out one live upstream catalogue request per role row.** Where: every role row builds a
   `modelCombobox` (`settings.js:3160-3201`, followers primed with Default's provider), plus backups and the
   decision row (2890); each primes `load(+cp, { open: false })` (`components.js:1354`) → `fetchModels`, which
   caches only when a request RESOLVES (`components.js:1208-1209`), so all of them start before the first
   returns. `list_models` has no server cache (`llm/providers.py:5236-5255`), and the catalogues are large
   (336-652 models, `settings.js:2931-2932`). Hot: the first ⚙ API open per page load, and again after any
   provider Save (`delete S.models[p.id]`, 2282). Gain: up to ~17 identical upstream requests → one per provider.
   Fix: memoize the in-flight promise per provider in `fetchModels`/`fetchImageModels`. The same open also runs
   `GET /api/memory/embeddings` (a live embedding probe plus up to eight COUNTs; F20).

3. **Whole-scene layout lint, three times per World Browser gesture.** `_lint_rows` runs in `rooms_index`,
   `_decorated_slice` (every slice and every room/entity/doorway write's answer) and `rooms_grid`/`map_index`
   (`web/world_routes.py:413-427, 704, 826-827, 1317, 1376`); 22-58 ms per pass on the owner's chats 63/175/172
   (web_routes audit, Efficiency 1).

   | Gesture | Requests | Lint passes |
   |---|---|---|
   | open the dialog (Rooms) | `/rooms`, `/positions`, slice, grid | 3 |
   | select another room | slice, grid | 2 |
   | card field or map drag through the room/entity/doorway routes (`replaceCard`) | write, `/rooms`, `/positions`, grid | 3 |
   | station, pose, near, region, charter, move (`ctx.refresh`, room zoom) | write, `/rooms`, `/positions`, slice, grid | 3 |
   | add a room through a wall (`addRoom`) | POST room, PATCH doorway, `/rooms`, `/positions`, slice, grid | 5 |
   | any write on the Bodies tab | write, `/rooms`, `/positions`, full Bodies rebuild | 1 |

   Client-side saving: `replaceCard` re-reads the index (the tree) even for fields the tree cannot show (`desc`,
   `notes`, `light`, `exposure`, `far_look`); skipping it there saves one pass and two requests per text edit. The
   larger gain is the server memo on the scene's write token (the web_routes auditor's fix).

4. **`boot()` after nearly every settings change.** 24 call sites in settings.js (1849, 1879, 2124, 2135, 2236,
   2264, 2282, 2283, 2305, 2328, 2441, 2548, 2584, 2616, 2649, 2706, 2743, 2750, 2804, 3347, 3722, 3739, 3755,
   3768). Each is a `/api/bootstrap` whose non-install half was ~1.23 MB on the owner's 307-body database
   (`web/app.py:1796-1798`: 2,002,515 bytes, of which 767,608 is the install half), the server's install-half
   rebuild (web_app audit E4), a whole-document `localizeDocument()` walk and a sidebar re-render — to change one
   boolean. Hot: per settings click. Fix: set the changed `S.boot` fields from each route's answer, as the
   debug-capture Save already does (`settings.js:2488-2491`); keep `boot()` where a list changes (providers,
   presets).

5. **The Bodies tab builds every body's full editors, open or folded.** `wbRenderBodies` (`world_browser.js:1574-1627`)
   creates each scene body's pose editor (six inputs, two datalists) and attire editor (every region, every
   garment, a checkbox per region, the notes) inside folded `<details>`, on opening the tab and after every write
   made on it. Fix: build a body's editors on its first `toggle` open (`ctx.openBodies` already tracks it).

6. **The embedding-rebuild poll** (`settings.js:2016`, every 1.5 s while a rebuild runs) makes a live
   embedding request per tick through `embedding_bank_status` (web_app audit E1). Poll `rebuild_progress()` alone
   while running; ask for the status once at the end.

7. Minor: every card rebuild is walked a second time by the i18n observer; the Prompts modal renders one textarea
   per default prompt (the ~520 KB `default_prompts`) on each language change (`settings.js:3683-3705`); `$$(".pta")`
   (3684) queries the whole document.

## Already registered

- **UNBUILT_WORLD §1.66** — the story-column floor overriding the reservation in `syncVitalsGutter`: still as
  described (`settings.js:1002-1010`, `Math.max(STORY_MIN_WIDTH, shellWidth - reserve * 2)`).
- **UNBUILT_PLANNING §2.26** — the World Browser's and the map editor's residual gaps ("Undo is ONE step and only
  for a drag"). Two of its sentences are now wrong: "a write from the card clears it" (F1), and the first bullet
  still lists a body's pose ("shown on the Bodies tab, not edited") and creating or retiring a room as not done,
  while `wbPoseEditor` (`world_browser.js:496-526`), `addRoom` (3618-3632) and `removeRoom` (3633-3642) exist —
  the bullet below it says so.
- **UNBUILT_PLANNING §2.35 (F44)** — the Director's anchor `dir: "c"` refused by the editor. The full-map anchor
  write amplifies it: one anchor carrying `c` makes EVERY anchor edit in that room fail with 400, since
  `_apply_anchors` refuses the whole map (`web/world_routes.py:1577-1580`) and the card always sends the whole map.
  Per-item writes (F2's fix) confine it to that row.
- **UNBUILT_PERCEPTION §2.34** — the map editor's `pointed_at` check narrower than `aim_of`; the client offers
  bearings, the room's stationable anchors and other things (`world_browser.js:1154-1156`).
- Not registers, but filed by other auditors of this fleet and seen from the client:
  - web_routes F4 (`world_entities` never written by the browser's entity routes): the client reads only
    scene-derived views (`/rooms`, slice, grid, map — all `rooms.read_scene`), so it neither masks nor reveals the
    stale projection; a regression test has to be server-side.
  - web_routes F10 (a moved body keeps the old room's pose support and detail): the client shows the stale
    `support`/`detail` verbatim (Bodies summary `1605-1607`, pose editor `515-525`) and nothing flags a support
    naming no anchor of the new room — it surfaces the bug rather than masking it.
  - web_routes F14 (doorway `desc` accepted, never written): the card sends it (`803`), says "Saved." and
    re-renders the empty field.
  - web_routes F5 (unlocked read-modify-write): the arrow-key nudges (`1840-1846`) fire one write per key repeat
    without awaiting the last; F2 here is the different, client-side stale-copy half of the same class.

## Structure notes

### Split notes — `static/js/settings.js` (4,167 lines)

Natural sections:

| Lines | Section | Parse-time effects |
|---|---|---|
| 1-26 | `PARADOX_MODES_FALLBACK`, `paradoxModes`, `frameQuery` (shared with world_browser.js) | — |
| 34-236 | Genre & style modal | `$("#b-style").onclick` |
| 238-526 | Dialogue config modal (charter rows, background life) | `$("#b-dlg").onclick` |
| 528-615 | `charterDiagnosticsPanel` | — |
| 617-666 | Cast modal shell and tabs | `$("#b-cast").onclick` |
| 668-881 | `dialogueColorControl`, `renderCastTab`, Condition tab | — |
| 883-1193 | vitals HUD, story-column width, `syncVitalsGutter*` | `window.syncVitalsGutter`, resize + `sonder-theme-change` listeners, two `ResizeObserver`s (`#composer`, `#ambience-bar`), `window.clearVitalsHud`/`refreshVitalsHud` |
| 1195-1311 | relocation: `hydrateCastLocations`, `castRoomLabel` (shared), `castRoomSelect` | — |
| 1313-1956 | Lorebooks, Multiplayer, Frames (frames, stationing, paradox), background presences, guest invites, Insights | — |
| 1958-2185 | `MODEL_RECOMMENDATIONS`, `embeddingBankBlock`, first-run setup, `preferredBackdropSize` | — |
| 2187-3372 | `renderFullApiSettings` (one 1,186-line function: providers 2191-2305, response limit 2307-2344, OpenRouter 2346-2448, debug capture 2450-2504, backdrops 2506-2570, feeling 2572-2605, clothing 2607-2636, cast acquisition 2638-2669, ambience 2671-2717, research 2719-2754, exemplars 2756-2809, agent models 2811-3350, sign-out 3352-3371) | — |
| 3374-3382 | API modal | `$("#b-api").onclick` |
| 3384-3648 | Software updates, checkpoint conversion | `$("#b-update").onclick` |
| 3650-3838 | Prompts modal, `reopenPromptsIfRequested` | `$("#b-prompts").onclick` |
| 3840-4167 | Extensions menu | `$("#b-extensions").onclick` |

Proposed split (five files, all where settings.js loads now except the first):

1. `settings_story.js` — 1-615 plus `castRoomLabel` (moved from 1247): helpers, Genre & style, Dialogue,
   charter diagnostics (~640 lines). Load it **before** `world_browser.js` (after `writers_room.js`): that removes
   today's inversion, where world_browser.js calls two settings.js globals (`frameQuery`, `castRoomLabel`) that
   load after it and are safe only because they are reached from clicks.
2. `settings_cast.js` — 617-882 and 1195-1956 minus `castRoomLabel`: the Cast modal and its six tabs (~1,030).
3. `vitals_hud.js` — 883-1193 (~310). All of settings.js's parse-time listeners live here; `#composer` and
   `#ambience-bar` must exist at parse (they do: the scripts sit at the end of `<body>`). Callers:
   `chat.js:152, 188` (`window.clearVitalsHud?.()`, `window.refreshVitalsHud?.()`), `settings.js:227`,
   `renderConditionTab`/`vitalsBlock` (`VITAL_ROWS`, `vitalMeter`).
4. `settings_api.js` — 1958-3382 (~1,425); a follow-up should cut `renderFullApiSettings` into its thirteen block
   builders.
5. `settings_host.js` — 3384-4167 (~785): updates, Prompts (`reopenPromptsIfRequested` is called by
   `app.js:1369-1370`), Extensions (reaches `Sonder` from extensions.js, which loads later, at click time).

New order: `… → chat.js → writers_room.js → settings_story.js → world_browser*.js → settings_cast.js →
vitals_hud.js → settings_api.js → settings_host.js → themes.js → extensions.js → app.js`. One binder per button
must survive (`settings.js:28-32`: a second top-level `onclick` in a later file silently wins).

### Split notes — `static/js/world_browser.js` (3,995 lines)

| Lines | Section |
|---|---|
| 1-111 | header, `WB_GROUPS`, `wbStatusBadge`, `wbRoomLabel` |
| 113-214 | edit controls: `wbSelect`, `wbText`, `wbCoalesced`, `wbWrite` |
| 216-294 | the tree |
| 296-1360 | the room card: cells/stations, move controls, townspeople (419-490), pose editor, lint rows, `wbRoomFields` (548-702), `wbRegionLook`, `wbExits` (762-882), `wbWindows`, `wbAnchors` (966-1078), `wbOccupant`, `wbThing`, `wbRenderCard` (1224-1360) |
| 1362-1632 | Bodies tab: garments/ledger, `wbAttireEditor` (1422-1523), body kinds, townspeople details, `wbRenderBodies` |
| 1634-1719 | Raw JSON tab |
| 1721-2722 | map primitives (`wbSvg`, `wbDraggable`, `wbUndoStack`, wall/offset/bearing math, `wbBoundary`, `wbFocusRow`, `wbFootprintLength`) and `wbRenderRoomMap` (1951-2722, 772 lines) |
| 2724-2887 | `wbRenderStructureMap` |
| 2889-3177 | the layout-lab port: `WB_PLAN_*`, `wbPlan*`, `wbRenderStoreyPlan` |
| 3179-3340 | legends, the pane, the wall and cell forms, map notes |
| 3342-3979 | `openWorldBrowser` (636 lines; the `ctx` object 3415-3662) |
| 3981-3995 | `$("#b-world").onclick`, `$("#b-attire").onclick`, `window.openWorldBrowser` (the only parse-time effects) |

Proposed split (five files, in this order at world_browser.js's current position): `wb_plan.js` (2889-3340, ~450;
the room map draws with its `wbPlan*` primitives) → `wb_map.js` (1721-2887, ~1,165; keep the global
`wbRenderRoomMap`, which `chat.js:2120-2121` calls for the pipeline drawer) → `wb_card.js` (1-1360) →
`wb_bodies.js` (1362-1719) → `world_browser.js` (3342-3995: the dialog and the bindings). Nothing crosses files at
parse time.

**Tests that read these files by path** and must follow a split: 18 test files read `static/js/settings.js`
(e.g. `tests/test_frontend_state_guards.py`, `test_reading_surface.py`, `test_provider_fallbacks.py`,
`test_host_settings_surface.py`), 5 read `static/js/world_browser.js` (`test_frontend_coalesced_redraws.py` slices
`wbCoalesced`/`wbWrite`, `test_frontend_state_guards.py`, `test_world_routes.py`, `test_card_editor_vocabularies.py`,
`test_attire_write_lands_on_the_ledger_key.py`). `tests/test_frontend_global_namespace.py` reads the load list from
`index.html`, so new files are covered automatically; `render_shell` rewrites every `?v=` token (`web/app.py:677-681`).

### Globals other files call

- From settings.js: `frameQuery`, `castRoomLabel` (world_browser.js); `window.clearVitalsHud`,
  `window.refreshVitalsHud` (chat.js:152, 188); `reopenPromptsIfRequested` (app.js:1369-1370); `window.syncVitalsGutter`
  (browser tests, `tests/test_ui_themes.py`). Tests also name `charterDiagnosticsPanel`, `checkpointCompactionBlock`,
  `extensionSettingsSections`, `PARADOX_MODES_FALLBACK`, `STORY_MIN/MAX_WIDTH`, `VITALS_MIN_GUTTER` and the `render*`
  panels.
- From world_browser.js: `wbRenderRoomMap` (chat.js:2120-2121); `window.openWorldBrowser` has no runtime caller
  beyond its own buttons (tests read it as source).
- settings.js calls, at click time: `boot` (app.js), `openChat`, `renderChat`, `memModal`, `relationshipModal`,
  `chatPH`, `personaPH` (chat.js), `charEditor`, `exportLorebook`, `generateLoreModal`, `promoteBackgroundPresence`
  (editors.js), `openLoreWorkspace`, `normalizeLoreBook`, `loreBooksByParent`, `loreRootBooks`, `loreBookTypeIcon`
  (lorebooks.js), `openLivedLocationDialog`, `modelCombobox`, `fetchModels`, `fetchImageModels`, `backgroundTask`,
  `modalOwnership`, `confirmModal` (components.js), `syncAmbience` (ambience.js), `downloadJSON` (utils.js), `Sonder`
  (extensions.js).

### Module-level mutable state

- settings.js: `_vitalsGutterQueued` (1039; written by `syncVitalsGutter`), `EXTENSION_UPDATES` (3882; written at
  4024 and 4106-4107), `extensionsDialog` (3919; written at 4164). It also writes shared state: `S.chat.dialogue_colors`
  (701), `S.boot.decision_capture/llm_capture_*/log_level` (2488-2491), `S.chat.chat.story_language` (3801).
- world_browser.js: none — every piece of state lives in `openWorldBrowser`'s closure (`state`, `ctx`).

### Monoliths in miniature

`renderFullApiSettings` (settings.js:2187-3372, 1,186 lines), `wbRenderRoomMap` (world_browser.js:1951-2722, 772),
`openWorldBrowser` (3344-3979, 636), the Dialogue handler (settings.js:238-526), `openExtensionsMenu` (3921-4165),
the Genre & style handler (42-236), `wbRenderCard`, `wbExits`, `wbAnchors`, `wbAttireEditor`, `wbPlanFixture`.

### Hazards and duplication worth knowing before a split

- **Shadowed globals:** `const S = WB_CELL` (world_browser.js:1953) and `const S = WB_MINI` (2728) shadow the state
  object `S` inside a 772-line and a 160-line function — any future `S.chatId` there reads `undefined` off a number;
  `t` (the translator) is shadowed in `wbPlanLabel` (2968), `wbPlanFixture` (2996) and `wbPlanStair` (3067);
  `location` (window.location) in `openWorldBrowser` (3394). None is used wrongly today.
- **Six copies of the room-PATCH closure** (world_browser.js:553-559, 765-771, 897-903, 971-977, 1231-1237,
  3458-3464), three of the doorway PATCH (781-787, 904-910, 3474-3481), five of the station PUT (1085-1091, 1594-1602,
  3465-3471, 3492-3494, 3557-3559); `asExit`/`isWindow` twice (772/812, 893/896); `castRoomLabel` (settings.js:1247)
  and `wbRoomLabel` (world_browser.js:107) state one rule.
- **Debris:** settings.js:244-245 repeats `if (S.chatId !== chatId) return;` on consecutive lines.

### Registry pairs (assignment question 2)

| Client | Server source | Result |
|---|---|---|
| provider-kind selects `Object.keys(S.boot.provider_presets)` (2109, 2197, 2303) | `DEFAULT_BASES`, 16 kinds | shipped — no copy |
| `MODEL_RECOMMENDATIONS` keys (1965-1981) | `DEFAULT_BASES` | 15 of 16 (all but `generic`), none extra |
| `EMBED_BY_KIND` (2948-2967) | kinds | `openrouter`, `nanogpt` exist |
| role rows `S.boot.roles` + `extension_lanes` | `ROLES` (16) | shipped |
| `ROLE_ORDER` (2869-2873) | `ROLES` | its 6 names all exist |
| role help (2817-2828) | `ROLES` | 11 of 16 described — **F8** |
| effort fallback (3124) | `REASONING_EFFORTS` | equal |
| `FORMAT_LABELS` (3141-3150) | `RESPONSE_FORMATS` | equal |
| output-token fallback (2313-2314) | `MAX_OUTPUT_TOKENS_*` | equal (20000 / 1024 / 128000) |
| quantisations (2365) | `OPENROUTER_QUANTIZATIONS` | equal minus `unknown` (deliberate) |
| routing sort (2359) | `_ROUTING_SORTS` | equal; `order` not offered — **F14** |
| debug bodies and levels (2459-2466) | `put_debug_capture` (`web/app.py:2255-2263`) | equal |
| ambience sources (2677-2679) | `put_ambience` (`web/app.py:2300-2303`) | equal |
| licences (2689, 2697-2698) | `FREESOUND_LICENCES` (shipped, unread) | equal — **F12** |
| exemplar fallback 5 / 2000 (2764-2765) | `EXEMPLAR_MAX_*` | equal |
| `PARADOX_MODES_FALLBACK` (10) | `paradox.MODES` | equal |
| `AUTHORITY_LABELS` keys (115-122) | `PLAYER_AUTHORITY_MODES` | equal |
| weather (57-61), tense (72-75) | `WEATHER_SEVERITIES`, `NARRATION_TENSES` | equal |
| scene life (268-271), number bounds (274-299) | `bg_cfg_put`/`dlg_put` clamps, `BUBBLE_RADIUS_*` | equal |
| dialogue style (250) | `_VERBOSITY_PLACE` keys; `dlg_put` stores `style` unvalidated | equal set |
| `VITAL_ROWS` keys (885-890) | `survival.VITALS` | equal |
| frame kinds (1568-1571) | `create_frame` (default `other`, `spatial` refused) | no closed set server-side |
| trust classes (3853-3863) | `_trust_class` | equal; unknown → the "runs code" text (fail-safe) |
| decision-model suggestion `/jev|typesafe/` (2896) | `decisions.DEFAULT_MODEL` `typesafe/jev-1.13` | matches |
| "thirty days" (3360), "30 minutes" (1819) | `HOST_SESSION_TTL`, `JOIN_CODE_TTL` | equal |
| World Browser selects | `vocabulary()` | shipped |
| `WB_GROUPS`, `WB_CHARTER_SOURCE`, `wbBodyKind`, pose hints | `GROUPS`, `PLACEMENT_SOURCES`, `BODY_KINDS`, `_POSE_FIELDS` | equal |
| `wbFootprintLength` (1944-1948) | `spatial_fov.py:605-606` | equal |
| `opacities[0]`, `shapes[0]`, `light_heights[-1]` assumptions | `OPACITIES`, `SHAPES`, `LIGHT_HEIGHTS` | hold (`opaque`, `rectangle`, `full`) |
| extent fallback {2, 24} (2029) | 2..96 | **disagrees** — F19 |
| add-exit default `barriers[0]` | `_PASSABLE_BARRIERS` | `bars` — **F6** |
| `WB_PLAN_GROUP`, fixture kinds | lab port, solver kinds | `barrel` — **F18** |

### Secrets (assignment question 1)

- No key ever reaches the browser: `_provider_public` pops `api_key` and returns `has_key`
  (`web/app.py:3295-3305`); ambience and research answer `has_key` only (2317, 2323-2327; bootstrap 2074-2075).
- The provider, Freesound, research and first-run key inputs are `type=password` (2110, 2202-2206, 2682-2685,
  2729-2732), rendered empty with a placeholder that says whether a key is set; `el()` sets `value` as a property
  (`components.js:22`), so no key sits in a DOM attribute.
- A provider row's Save sends `api_key: ak.value` every time; blank keeps the stored key (`web/app.py:3328-3340`).
  A typed key stays in the field (the row is not re-rendered after Save) and is re-sent by a later Save of that row —
  harmless.
- No `console.log`/`debug`/`info` in either file. `toast()` mirrors error and warning toasts to the console
  (`components.js:546-547`); no route read formats a key into its error text.
- Gaps: a provider key can be replaced but not cleared (delete the provider); the Freesound key cannot be cleared
  at all (F13); the key inputs carry no `autocomplete="new-password"`, so a password manager may offer to store an
  API key as a site password (hardening only).

### XSS sinks (assignment question 4)

None found. Every `innerHTML` assignment in both files is `= ""` (23 in settings.js, 40 in world_browser.js); no
`insertAdjacentHTML`, `outerHTML`, `document.write`, `eval` or `new Function`. Text goes in through `el()` text nodes
(`components.js:42-46`), `txt()`, `createTextNode` (`wbSvg` 1796) and `textContent` (settings.js:1221, 2000, 3442;
world_browser.js:2969, 3107, 3131, 3145, 3156, 3161, 3174); `confirmModal` renders its message through `el()`
(`components.js:236-238`). Attributes go through `setAttribute` only (`el()`, `wbSvg` 1787-1799, `wbPlanEl` 2908-2913),
so model-written names in `data-*`, `title` and `aria-label` are inert; selectors built from model ids use `CSS.escape`
(e.g. 2195, 2274, 2621, 2658). `style` attributes interpolate numbers or one of `wbPlanFill`'s nine fixed values
(2066, 2119, 2138, 3184, 3337; settings 903, 1349, 3458). Model-generated room names and descriptions, release notes
(3586) and extension descriptions (4055) all land as text.

### How writes behave (assignment question 3)

- **World Browser:** no optimistic updates. Every write awaits the server, then re-renders from its answer
  (`replaceCard`) or re-reads (`refresh`); a refusal — the 409 "This chat still has an active pipeline…"
  (`web/world_routes.py:381-383`) included — is toasted in the server's words and followed by a re-read
  (`wbWrite` 204-214): surfaced, not swallowed. Gaps: F1, F2, F11, F16. No polling: the dialog never re-reads on its
  own, so a beat that commits while it is open is invisible until the next gesture (the root of F2).
- **Settings:** most saves are bare `await api()` in `onclick` handlers, surfaced by the global
  `unhandledrejection` net (`app.js:1200-1204`). Exceptions: F4 (lost to a reload); the debug-capture save shows a
  generic "Could not save debug capture." and drops the server's 400 text (2493-2494); the presences, irony and
  promise panels show "Could not load." (1767-1769, 1923-1925, 1951-1953); a failed personas read renders as "No
  extra players attached yet." (1789, 1857). Multi-PUT saves are not atomic — style (survival → style guide →
  authority, 203-226), dialogue (→ background, 512-523), "Save all" (agent models → efforts → formats → decision
  model, 3341-3346), backdrops (image model → backdrops, 2545-2547): a failure midway leaves the earlier PUTs applied
  with the modal open. Optimistic controls: F9. Two tabs: F10.

## Docs checked

| Claim | Where | Holds? |
|---|---|---|
| Script load order `… chat.js → writers_room.js → world_browser.js → settings.js → themes.js → extensions.js → app.js` | CLAUDE.md; AGENTS.md:1027 | Yes (`static/index.html:179-209`) |
| GM relocation lives in the settings.js cast tab, idle-only, no narrator beat | AGENTS.md:529 | Yes (`castRoomSelect` 1255-1311 reverts on a refusal) |
| settings.js keeps `frameQuery`, `castRoomLabel` and no longer binds `#b-world`/`#b-attire` | AGENTS.md:532; settings.js:28-32 | Yes |
| "every attire edit is the WHOLE ledger through `attire_put`" | AGENTS.md:532 | **No** — one body's entry (F19) |
| "only the registered cast moves between rooms" | AGENTS.md:532 | **No** (web_routes F25) — `moveRoute` uses `PUT /bodies/{name}/room` for the player and presences (3666-3672) |
| "NO CLOSED SET IS TYPED INTO THE BROWSER: every select reads vocab" | AGENTS.md:532; world_browser.js:73-75 | Selects: yes. The file: **no** (F19) |
| World Browser writes refused with 409 while a pipeline runs | AGENTS.md:532 | Yes, and the client surfaces it (`wbWrite`) |
| "A write from the card clears it" (Undo) | world_browser.js:1853-1854; UNBUILT_PLANNING §2.26 | **No** (F1) |
| "card is re-rendered from the server's answer either way -- never a silent revert" | world_browser.js:77-81 | For the field written; **not** for others being typed (F11) |
| "an attire edit sends THIS BODY'S ENTRY ALONE" | world_browser.js:59-64 | Yes (1438-1444) |
| `opacities[0]` blocks sight; `shapes[0]` is the unset shape; the last light height is a ceiling light | world_browser.js:2242-2244, 3738, 2287-2290 | Yes |
| `wbFootprintLength` is "the engine's table" | world_browser.js:1941-1943 | Yes (`spatial_fov.py:605-606`) |
| "The server never sends the stored key back … an empty field means leave it unchanged" | settings.js:2199-2201 | Yes (`web/app.py:3295-3340`) |
| Role help: Default suffices, embeddings never inherits | settings.js:2817 | Yes (`ROLE_FALLBACKS = {}`) |
| Role help: the rest are "a specific stage of each turn" | settings.js:2817 | **No** (F8) |
| `role_fallbacks` "is empty today" | settings.js:3236-3240 | Yes |
| Invite "expires in 30 minutes"; "Your sign-in lasts thirty days" | settings.js:1819, 3360 | Yes (`JOIN_CODE_TTL`, `HOST_SESSION_TTL`) |
| "An emptied field saves what it showed, never 0" | settings.js:294-297 | Two of five fields (F5) |
| "a box that reports what it asked for … would show a state that is not real" | settings.js:2254-2256 | Rule kept by 3 controls, broken by 6 (F9) |
| The embedding poll stops on a detached panel | settings.js:2011-2016 | Yes; its sibling does not (F3) |
| "Safe to poll: … not a full parse" | web/app.py:3011-3012 | **No** (F3; `persist/checkpoints.py:1339-1347` says so itself) |
| "cheap enough to poll (two COUNTs plus an in-memory snapshot)" | web/app.py:2141 | **No** (F20) |
| "this route is issued on every style-guide save" | web/app.py:4364-4366 | **No** (F20) |
| "World mechanisms, each with its own switch … the settings panel says what it actually runs as" | docs/guides/FEATURES.md:425-435 | **No** (F20) |
| An anchor dragged into the room "is placed by seed again" | docs/guides/FEATURES.md:770-771 | **No** (F19) |
| "Undo takes back the last drag, one step" | FEATURES.md (World Browser); Design.md:218 | Exists; defects in F1 |
| The pipeline drawer's map draws | Design.md:194 | Yes (`wbRenderRoomMap` tolerates `currentSlice()` null, 2438) |
| The enum-label gap is "Recorded in `docs/UNBUILT.md`" | tools/extract_ui_catalog.py:407 | **No** — no register has it (F7) |
| `txt()` keeps story text out of the translator | components.js:1-12 | Holds in world_browser.js's card and tree; not on its two map SVGs nor in settings.js (F17) |
| Insights are host-only, not in `GUEST_ALLOWED_API_PATHS` | settings.js:1889-1895 | Yes (`web/auth_routes.py:42-45` allows two paths) |
