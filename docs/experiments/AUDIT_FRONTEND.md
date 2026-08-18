# Audit: the frontend — `static/js/*.js`, `static/index.html`, and `dressing/`

Working notes in the register of
[`AUDIT_DIRECTOR.md`](AUDIT_DIRECTOR.md) and
[`AUDIT_COMMIT.md`](AUDIT_COMMIT.md): findings are FLAGGED, never fixed, and
nothing outside this file was edited.

**Scope read end to end:** all 15 files under `static/js/` (16,618 lines),
`static/index.html` (178), and `dressing/backdrops.py` + `dressing/ambience.py`
(3,352). Cross-checked against `web/app.py`, `web/auth_routes.py`,
`tools/extract_ui_catalog.py`, `language_packs/en/ui.json`, `mind/memory.py`,
`agents/runtime.py`, `story/character_schema.py` and `persist/commit_background.py`.

**Baseline:** working tree at `4f33b17` (`Design.md` and `providers.py` locally
modified; neither is in this slice). Every `file:line` is as of that tree.

**`docs/UNBUILT.md` was deliberately not edited** — other agents are working
concurrently and it was declared off-limits to this task. Findings 3, 5, 8, 9
and 12 are the ones whose register entries someone should reconcile.

---

## Part 1 — findings. FLAGGED, NOT FIXED.

### A. Globals defined in two files

The exhaustive sweep found **exactly one** collision, and it is a live one.

#### 1. `loreModal` is defined in `editors.js` and silently replaced by `lorebooks.js` — 75 lines of dead code

`editors.js:857` declares `async function loreModal(lid)`, a complete 75-line
lorebook editor (rename, export, reinterpret, book-meta save, per-entry
keys/category/content/knowledge-tag editing). `lorebooks.js:636` then executes

```js
window.loreModal = openLoreWorkspace;
```

at top level. `lorebooks.js` loads AFTER `editors.js` (`static/index.html:158-161`),
and a top-level `function` declaration creates a writable property on the global
object — so the assignment overwrites it. **Every** call site reaches
`openLoreWorkspace`: `app.js:710`, `app.js:737`, `settings.js:1238`,
`editors.js:810`, `editors.js:849`, and the four recursive calls inside the dead
function's own body (`editors.js:876, 883, 917, 922`).

Why it matters: it is the exact hazard `CLAUDE.md` warns about ("never rename a
shared JS function without grepping every file"), it is invisible to `node
--check` (a `function` redefinition is legal where a `const` one is not), and
the dead body is still maintained-looking code that a reader will edit expecting
an effect. It also drags a second corpse with it — see finding 15.

**Verification method, for the next auditor.** Two mechanical passes, both
clean apart from the above:

* Concatenating all 14 loaded files in load order and running `node --check`
  passes, which proves there is no duplicate top-level `const`/`let`/`class`
  anywhere (in a browser those collide across `<script>` tags as a hard
  `SyntaxError`, so a collision of that kind would mean the app does not boot).
* Running each file in a fresh `vm` context and diffing the global property
  names captures every top-level `function` and `var` (both hoisted, so an
  early DOM-access throw does not hide them). 343 names, **zero** cross-file
  duplicates. The only cross-file write to an already-owned name is the
  `window.loreModal` above; the other four `window.X = X` assignments
  (`app.js:987`, `settings.js:912`, `settings.js:1055-1056`,
  `lorebooks.js:636`) are same-file re-exports and are no-ops except that one.

### B. A global used in a file that loads before the file defining it

Fourteen sites, **all deferred into callbacks, none broken today**. Listed in
full because the category was asked for exhaustively, and because six of them
are unguarded and therefore only correct by load-order accident.

| name | used at | defined in | deferred? | guarded? |
|---|---|---|---|---|
| `chimeWatches` | `utils.js:220` | `chime.js` | yes (inside `api()`) | yes, `typeof` |
| `chimeArm` | `utils.js:221` | `chime.js` | yes | yes, `typeof` |
| `chimeWorkFinished` | `utils.js:265` | `chime.js` | yes | yes, `typeof` on line 264 |
| `boot` | `editors.js:34` (+ 8 more) | `app.js` | yes | **no** |
| `openChat` | `editors.js:212` | `chat.js` | yes | **no** |
| `renderSide` | `lorebooks.js:440` | `app.js` | yes | **no** |
| `boot` | `lorebooks.js:1416` | `app.js` | yes | **no** |
| `weatherFxForTurn` | `backdrops.js:290` | `weather-fx.js` | yes | yes, `typeof` |
| `weatherFxApply` | `backdrops.js:384` | `weather-fx.js` | yes | yes, `typeof` |
| `renderSide` | `chat.js:155` | `app.js` | yes | **no** |
| `newChatWizard` | `chat.js:508` | `app.js` | yes | **no** |
| `boot` | `chat.js:638` | `app.js` | yes | **no** |
| `boot` | `settings.js:1670` | `app.js` | yes | **no** |
| `renderSide` | `extensions.js:455` | `app.js` | yes | yes, `typeof` |

The asymmetry is the finding: `chat.js` guards the modules that load BEFORE it
(`backdropOnVisibleTurn`, `ambienceOnVisibleTurn`, `chimeArm`) with `typeof`,
and reaches FORWARD to `settings.js`/`app.js` through `window.clearVitalsHud?.()`,
`window.refreshVitalsHud?.()`, `window.erOfferRebuild?.()` — which is why those
three carry the `window.X = X` re-exports at `settings.js:912/1055/1056` and
`app.js:987`. But `boot`, `renderSide`, `openChat` and `newChatWizard` are
reached forward as bare identifiers with no guard at all. That is safe only
while `app.js` is the last host script; `static/index.html:166` already inserts
`extensions.js` between `themes.js` and `app.js`, so the tail of the order has
moved once already.

Also swept and **clean**: every identifier called as a function across the 15
files resolves to a declaration somewhere (no typo'd or removed callee), and
every `#id` selector used by JS exists in `static/index.html` or is created by
JS. Six ids in `index.html` are referenced only by CSS (`activity-head`,
`activity-title`, `app`, `modalhead`, `top`, `top-context`) — not a defect.

### C. Two representations of one rule

#### 2. `auto_promote` defaults ON in the API and OFF in the enforcement — and no UI writes either

Three copies of one rule, and two of them disagree:

* `persist/commit_background.py:1392-1402` — `_auto_promote_enabled()` returns
  true only for `("1","on","true","yes")`, so an **unset** setting is **OFF**.
  Its docstring says so explicitly: *"Off unless the host has explicitly
  switched it on."*
* `web/app.py:3375` — `GET /api/auto_promote` returns
  `get_setting("auto_promote") != "0"`, so an unset setting reports **ON**.
* `web/app.py:1236` — `bootstrap` ships `"auto_promote": get_setting("auto_promote") != "0"`,
  the same inverted default, to every browser.

On a fresh install (setting never written) the API and the bootstrap both say
promotion is enabled and the commit gate refuses it. Nothing notices because
**no JavaScript reads `S.boot.auto_promote` and nothing calls `GET`/`PUT
/api/auto_promote`** (verified by grep over `static/`, `browser_tests/` and
`tests/`; the only hits are bootstrap fixtures in `browser_tests/`).

Worse, the dialogue-config panel tells the reader the control exists:
`static/js/settings.js:450` renders *"Promotion also has to be switched on
globally in ⚙ API."* — and ⚙ API (`renderFullApiSettings`, `settings.js:1977-2853`)
has no such control. A host following that sentence finds nothing, and the two
places that would answer the question from the API answer it wrongly.

This is the highest-severity finding in the slice: a promotion gate whose
reported state is the inverse of its real one, with the only documented route to
change it pointing at a control that was never built.

#### 3. `LORE_INHERITANCE_MODES` exists four times; the create route validates none of them

* `mind/memory.py:55` — `LORE_INHERITANCE_MODES = ["inherit","isolated","reference_only"]`.
  **Read by nothing.** Grep over the whole tree returns the definition line only.
* `web/app.py:2622-2626` — the same three strings re-spelled as an inline tuple
  in `lore_edit` (`PUT /api/lorebooks/{lid}`), which raises 400 on anything else.
  This is the only validation in the system.
* `web/app.py:2586` — `lore_create` (`POST /api/lorebooks`) does
  `body.get("inheritance_mode") or "inherit"` and **inserts it unvalidated**.
  A create can therefore store a mode that the edit route will refuse, and that
  `retrieval` will read as an unknown string.
* `static/js/lorebooks.js:3-7` — a fourth copy, `LORE_INHERITANCE_MODES`, which
  is what actually confines the UI (`renderLoreBookEditor` at `lorebooks.js:1196`,
  `createLoreBookDialog` at `lorebooks.js:1536`).

Nothing ships the list through the bootstrap, so the browser's copy cannot
follow the engine's. Compare `offscreen_life_levels`, which the dialogue panel
gets from the server precisely so *"the menu cannot drift from the ladder the
engine actually implements"* (`settings.js:288-291`) — the same problem, solved
in one place and not the other.

#### 4. `MEMORY_CATEGORIES` / `MEMORY_PROVENANCE` are shipped by the server and ignored by the browser

`web/app.py:1182-1183` puts `memory_categories` and `memory_provenance` (from
`mind/memory.py:57-66`) into every bootstrap. `static/js/utils.js:183-184`
hard-codes both lists as `MEM_CATS`/`MEM_PROV` and uses them in five places
(`chat.js:2044, 2047, 2396, 2401, 2629, 2634`). The two agree today, term for
term and in the same order — which is exactly what makes the next edit
invisible: `mind/memory.py:940-941` and `:1408-1410` reject an unrecognised
category or provenance silently (`category if category in MEMORY_CATEGORIES
else _default_category(kind)`), so a term added server-side and missing from the
browser is simply absent from the dropdown, while one removed server-side is
offered in the dropdown and quietly rewritten on save.

The fix is already sitting in the payload and unread.

#### 5. `LORE_LINK_TYPES` and `DEFAULT_LORE_LINK_TYPES` are the same ten strings in two JS files, and one of them is unreachable

`app.js:3-14` (`LORE_LINK_TYPES`) and `lorebooks.js:9-20`
(`DEFAULT_LORE_LINK_TYPES`) are byte-identical 10-element arrays. Both exist as
a fallback for `S.boot.lorebook_link_types` (`web/app.py:1240`). But `boot()`
installs its copy unconditionally at `app.js:24-26`:

```js
if (!Array.isArray(S.boot.lorebook_link_types)) {
  S.boot.lorebook_link_types = LORE_LINK_TYPES;
}
```

so by the time any lore UI can run, `S.boot?.lorebook_link_types` is always
truthy and `lorebooks.js:51`'s `|| DEFAULT_LORE_LINK_TYPES` can never be taken.
`DEFAULT_LORE_LINK_TYPES` is dead, and the surviving copy is a third
representation of `mind/memory.py:32`'s `LOREBOOK_LINK_TYPES`.

#### 6. `static/js/i18n.js` re-implements `utils.js`'s translation rules, and one difference is already live

`i18n.js:26-56` and `utils.js:36-69` are two implementations of the same
template-matching algorithm (placeholder-key compilation, the `weight >= 3`
literal-text floor, the weight-descending sort, per-capture translation). The
header of `i18n.js:6-9` acknowledges this and asks that the RULES stay identical,
citing a divergence that already cost a whitespace bug.

They have drifted again, quietly: `utils.js:39-41` computes `anchored =
literals.join("").trim()` and weights on `anchored.length`; `i18n.js:33-36`
computes `weight: literals.join("").trim().length` — the same value by luck of
expression, so that pair is fine. The real divergence is the SKIP set:
`utils.js:130-131` defines `I18N_SKIP_TREE` and `I18N_SKIP_TEXT` and applies the
tree skip to **attributes as well as text** (`utils.js:168-173`), documented at
`utils.js:161-166` as a fix for a character named "Cast" getting a translated
tooltip. `i18n.js:81-92` applies no skip-tree filter to its attribute pass at
all. The login and guest pages are the only consumers, so the exposure is small
— but the rule the comment asks to be kept identical is not.

### D. Routes that exist and nothing calls; a UI that writes what nothing reads

Method: every `api(...)`/`streamPost(...)`/backtick `/api/...` literal in
`static/js/*.js` and `static/*.html` normalised against every
`@app.<verb>(...)`/`@router.<verb>(...)` in `web/app.py`, `web/auth_routes.py`,
`persist/chat_archive.py` and `web/guest_access.py`. **No JS call reaches a
route that does not exist** — every apparent orphan resolved to a
string-concatenated path. The other direction found ten.

#### 7. `PUT /api/exemplars` — the door was built and nothing opens it

`web/app.py:1342-1370`. Its own docstring is the finding:

> **THE SLOT EXISTED AND HAD NO DOOR.** `agents/narration.py` has always read
> `settings.exemplars`, and the narrator prompt has always carried a STYLE
> EXEMPLARS clause telling the model to study them for voice, rhythm and
> restraint — but nothing anywhere could write the setting, so the clause
> referred to an empty list on every install that has ever run.

The route was added to close that. **No JavaScript calls it**, and no JavaScript
reads `S.boot.exemplars` (`web/app.py:1189`) either. The narrator's STYLE
EXEMPLARS clause is still referring to an empty list on every install, one HTTP
layer further along than before.

#### 8. Nine more routes with no caller anywhere in the frontend

Verified by grep over `static/js/`, `static/*.html` and `browser_tests/`.

| route | `web/app.py` | note |
|---|---|---|
| `GET /api/ambience/library` | 5711 | docstring: *"so the picker can list it unfiltered"*. `openAmbiencePanel` (`ambience.js:818-927`) only ever calls `/api/ambience/search`. The picker has no unfiltered listing. |
| `GET /api/chats/{cid}/ambience/pins` | 5744 | the panel only knows the current room's pin, via `AMB.pinned` on the per-turn payload. |
| `GET /api/auto_promote`, `PUT /api/auto_promote` | 3373, 3377 | see finding 2. |
| `GET /api/chats/{cid}/story_view` | 4222 | docstring: *"Served to the host UI as well as to extensions … because a surface only extensions can reach is one nothing in this repository exercises."* No host UI code calls it. |
| `GET /api/chats/{cid}/player_view` | 4237 | same. |
| `GET /api/chats/{cid}/viewers` | 4247 | same. |
| `POST /api/chats/{cid}/turns/{idx}/player_input` | 3465 | the extra-player input path; the Multiplayer tab only issues invites. |
| `DELETE /api/chats/{cid}/personas/{pid}` | 3451 | `renderGuestInvitePanel` (`settings.js:1596-1678`) can ATTACH an extra player and revoke their invite, but has no detach. An attached persona is permanent from the UI. |
| `POST` / `DELETE /api/chats/{cid}/lorebook` (singular) | 2989, 3005 | sets `chats.lorebook_id`, which `agents/mapping.py:223` reads as the chat's canon book. The UI only uses the plural `/lorebooks` (`chat_lorebooks`). |
| `GET /api/language-packs`, `GET /api/language-packs/{id}/ui` | 2845, 2862 | the browser reads packs from `S.boot.language_packs` and `S.boot.ui_messages`. |

The extension document routes (`/api/extensions/{id}/document(s)`,
`.../documents/verify`, `.../asset/{id}`) are deliberately extension-facing
(reached through `Sonder.call`), not findings.

#### 9. `chat_lorebooks.enabled` can be read but never written

`core/db.py:191` declares it, `web/app.py:2968` and `:4885` INSERT it as `1`,
`mind/memory.py:481` reads it through `chat_lorebook_ids(..., enabled_only=)`,
`web/app.py:1989` and `:3169` return it to the browser (as `enabled` on
`GET /api/chats/{cid}/lorebooks` and on the chat payload). **Nothing anywhere
sets it to 0** — no `UPDATE chat_lorebooks SET enabled` exists in the tree — and
no JavaScript reads the field it is returned in. A per-story "mute this
lorebook" switch is fully plumbed through retrieval and has neither a writer nor
a reader.

#### 10. `blocked_by_other_frame` is computed, sent, and never read

`web/app.py:5179-5190` computes it and folds it into `editable`
(`editable = is_frame_latest and not blocked_by_other_frame`), then sends both.
`openPipeline` (`chat.js:1605-1955`) reads `p.editable`, `p.resumable`,
`p.resume_key`, `p.perceivers` and `p.steps`, and never `p.blocked_by_other_frame`.
So when a concurrently-live frame has advanced past this turn, the drawer simply
renders with Resume/use/reroll/edit missing and no explanation. The field that
would explain it is on the wire.

#### 11. `language_error` is surfaced by the bootstrap and shown nowhere

`web/app.py:1246-1247`, with the comment *"Surfaced rather than swallowed: the
host needs to know a pack they installed is not being used, and why."* No JS
reads `S.boot.language_error`. (`S.boot.extension_errors`, the next key down and
justified by the same comment, IS effectively covered — but through
`data.load_errors` from `GET /api/extensions` (`app.py:1583`,
`settings.js:3407-3411`), not through the bootstrap copy.)

Full bootstrap sweep, for completeness: of 46 keys, the ones no JavaScript reads
are `auto_promote`, `exemplars`, `language_error`, `extensions`,
`extension_errors`, `memory_categories`, `memory_provenance` and
`ambience_licenses`. Zero keys are read that the bootstrap does not send.

### E. Data the browser destroys

#### 12. Opening and saving a character card silently erases `simulation.sampler`, `simulation.curiosity` and `psychology.projects`

`web/app.py:2461-2468` (`PUT /api/characters/{cid}`) **replaces** the sheet
wholesale: `normalize_character_data(body["sheet"])` and `UPDATE characters SET
sheet=?`. There is no merge. `charEditor`'s Save (`editors.js:474-580`) rebuilds
the sheet field by field from its widgets, so anything without a widget is gone:

* `simulation.sampler` — `editors.js:491` writes a literal `sampler: {}` on every
  save, and `editors.js:51` seeds the same in `defaultCharacterSheet`. The value
  is live: `story/character_schema.py:1339` `character_sampler(sheet)` is read at
  `agents/character.py:3268` and passed to the model call. There is no UI to
  author it, and the editor destroys any that was imported or hand-written.
* `simulation.curiosity` — in the canonical default shape
  (`story/character_schema.py:563`) and read into the character payload at
  `agents/character.py:2773` via `character_curiosity`. Not written by the
  editor, so it silently reverts to `0.5` on every save.
* `psychology.projects` — `editors.js:505-529` builds `psychology` with
  `drive`, `capacity`, `traits`, `values`, `self_model`, `coping`,
  `stress_profile`, `learning` and nothing else. `character_projects`
  (`story/character_schema.py:1509`) reads `psychology.projects` and is consumed
  at `agents/character.py:2845`, `persist/commit.py:33` and
  `persist/commit_memory.py:803`. `CLAUDE.md` calls the card field *"a seeding
  tolerance"* — a host who uses it loses it the first time anyone opens the
  editor.

The class is the finding, not the three instances: **a full-replacement PUT
behind a field-by-field editor loses every field the editor does not know
about**, and `normalize_character_data`'s `_deep_defaults` backfill makes the
loss look like a deliberate value rather than an absence. The same shape applies
to `PUT /api/chats/{cid}/characters/{ch}/card` (`editors.js:562-568`).

### F. Silent tolerance of empty, missing or unknown values

#### 13. The global error net catches promise rejections only; a synchronous throw in a handler is still silent

`app.js:892-896` installs `unhandledrejection` with the comment *"Global safety
net: many onclick handlers `await api(...)` without a local catch, so a rejection
would otherwise fail silently ('nothing happens'). Surface it."* There is no
`window.onerror` and no `addEventListener("error", …)` anywhere in
`static/js/` (the one `"error"` listener, `ambience.js:376`, is on an `<audio>`
element).

So the failure mode the net was written to eliminate survives for every
synchronous throw. Two reachable examples:

* `charEditor` (`editors.js:225`) does `JSON.parse(c.sheet)` with no guard, from
  a bare `onclick: () => charEditor(character)` (`app.js:554`). A character row
  with malformed `sheet` produces exactly "clicking does nothing".
* `importModal` (`editors.js:783`) does `S.boot.lorebook_types.map(...)`
  unguarded, as does `renderCastTab` with `S.boot.personas` / `S.boot.characters`
  (`settings.js:581, 656`).

#### 14. `friendlyPhase` falls through to the raw technical label for `narrator_extra` and every extension step

`chat.js:703-726` `FRIENDLY_STEP_LABELS` covers thirteen keys and is missing
`narrator_extra` (`agents/runtime.py:628`, `"Narrator · render (other players)"`),
which is a real plan step for any chat with extra players. `friendlyPhase`
(`chat.js:733-744`) returns `label || "Working…"` for anything unmapped, so the
"friendly-by-default view so a long-running turn never looks like nothing is
happening, without requiring anyone to know what `perception_outcome` means"
(`chat.js:698-702`) reverts to the technical label on exactly the stage a
multiplayer chat spends time in. Extension-added steps (`_extension_splices`)
hit the same fall-through by construction.

Related and load-bearing: `chat.js:736` matches `/^Scene life/` against the
SERVER's label (`agents/runtime.py:654-656`). That is correct today only because
those labels are never translated — see finding 16.

### G. Dead code

#### 15. `editors.js`'s `loreModal` and its only unique caller

The 75-line body at `editors.js:857-931` is unreachable (finding 1). It drags
`generateLoreModal`'s second parameter with it: `editors.js:840`
`function generateLoreModal(lid, isChat)` never references `isChat` in its body
(verified — every other `isChat` hit in the file is `isChatCard`, a different
name inside `charEditor`). It is passed `false` from the dead `loreModal`
(`editors.js:880`) and `true` from the live `renderLorebooksTab`
(`settings.js:1250`), and both do the identical thing.

#### 16. `reopenExtensionsIfRequested` can never fire, and its comment names a writer that does not exist

`settings.js:3313` defines `REOPEN_EXTENSIONS_KEY = "sonder.reopenExtensions"`.
`settings.js:3600-3607` reads it. `app.js:1038-1040` calls the reader on boot.
**Nothing ever writes the key** — grep over `static/`, `tests/` and
`browser_tests/` returns only those three sites. The sibling
`REOPEN_PROMPTS_KEY` IS written, at `settings.js:3285`.

The comment above it (`settings.js:3596-3599`) is the second half of the finding:
*"Enabling and disabling no longer reload the page, so the only thing still
setting the marker is a language change — which does reload, and which can land
while this menu is open."* The language change that reloads is
`openPromptsModal`'s `langSel.onchange` (`settings.js:3258-3291`), and it sets
`REOPEN_PROMPTS_KEY` only. There is no language control in the extensions menu.

#### 17. `_confirmOverlay`'s `isResolved`/`markResolved` are never called

`components.js:196, 211`. `resolved` is initialised to `false`, returned through
two closures, and never written: all three consumers (`confirmModal:214`,
`promptModal:235`, `promptModalWithToggle:261`) track completion with their own
local `finished` flag and only ever call `overlay.cleanup()`.

#### 18. `fList` destructures a `remove` that no `buildRow` returns

`components.js:663`: `const { node, read, remove } = buildRow(item);` — `remove`
is unused, and none of the fourteen `buildRow` callbacks in `components.js`,
`editors.js` or `chat.js` returns one.

#### 19. `dressing/ambience.py:847` `refine_query` has zero callers and zero tests

Superseded by `refine_layers` (`ambience.py:756`), which
`resolve_ambience:1780` calls. Grep over the whole tree — including `tests/`,
`browser_tests/`, `tools/` and `docs/` — returns the definition and two comment
mentions of `compose_query` only. 31 lines, one model-call seam, dead.

#### 20. `#b-style` is a chat-scoped button that `updateChatScopedButtons` does not disable

`chat.js:474-484` disables `#b-world`, `#b-cast`, `#b-attire`, `#b-dlg` with the
comment *"…all no-op with no chat open (each checks `if (!S.chatId) return` at
the top of its own handler already) — disabling them when there's nothing for
them to act on turns a silent dead click into an honest, visibly-inert
control."* `$("#b-style")` (`settings.js:39-40`) opens with exactly that guard
and is not in the list. The class was named correctly and one member was left
out.

### H. Untranslated user-facing strings

#### 21. `tools/extract_ui_catalog.py` promises two Python tables that do not exist, and every pipeline step label falls through the gap

`tools/extract_ui_catalog.py:260-265`:

```python
READER_FACING_TABLES = {
    "agents/runtime.py": {"FRIENDLY_STEP_LABELS", "STEP_LABELS"},
    ...
}
```

above the comment *"Each entry here is a promise that the table's values are
interface copy."* **Neither symbol exists in `agents/runtime.py`, or anywhere in
Python** — grep over the tree returns only this line. `_table_strings` returns an
empty set when no module-level assignment matches, so the entry contributes
nothing and fails silently.

`FRIENDLY_STEP_LABELS` does exist — in `static/js/chat.js:703`. The Python-side
labels it is meant to cover are inline literals inside `build_plan`
(`agents/runtime.py:554, 560, 562, 563, 589, 593, 597, 608, 614, 615, 628, 645,
700-703`) and `_background_stage_label` (`:654, 656`). `_python_messages` only
harvests exception/`HTTPException`/`JSONResponse` arguments and the named
tables, so none of them is harvested.

Measured against `language_packs/en/ui.json`: `"Director · resolve"`,
`"Director · interpret & flow plan"`, `"Narrator · render"`,
`"Perception · pass 2 — the outcome"` and every sibling are **MISSING** from the
catalog, while the JS friendly names (`"Setting the scene"`, `"Writing the
scene"`, …) are present. Those labels are reader-visible in three places:
`liveStep` (`chat.js:839`) writes them into `#live`, `openPipeline`
(`chat.js:1942`) renders `s.label` as each step's `<h4>`, and `friendlyPhase`
(`chat.js:743`) returns the raw label for any key it does not map — which is
`narrator_extra` and every extension step (finding 14).

#### 22. Four explanatory paragraphs exceed the extractor's 500-character cap and are dropped whole

`_message` (`tools/extract_ui_catalog.py:182`) rejects any candidate with
`len(value) > 500`. The extractor's own `+`-joining pass
(`:108-129`) correctly welds multi-line concatenations into one message, which
is what pushes these past the cap. Measured, all four are the longest
explanatory paragraphs in the settings and card editors and none is in
`en/ui.json`:

| chars | file:line | opening |
|---|---|---|
| 698 | `static/js/editors.js:408` (and the identical copy at `:646`) | "Each garment covers part of a body, which is what lets the story undress someone one piece at a time…" |
| 574 | `static/js/settings.js:2404` | "— shape, never content. When a stage's output fails validation, this model is asked about…" |
| 556 | `static/js/settings.js:2228` | "With this on, a room's later pictures — lights out, rain, mud, wreckage — are edits of…" |
| 553 | `static/js/settings.js:176` | "Who decides what your declaration achieved. Under full authorship — the default…" |

These are precisely the strings a non-English reader most needs: each explains a
setting whose consequence is not visible from the control.

Secondary, in the same family: `settings.js:176-177` writes the smart quotes as
`“` / `”` escapes, and the extractor's unescape pass
(`:359-365`) handles `\n \t \r \/ \" \' \\` only — so even under the cap that
key would enter the catalog with a literal backslash-u sequence and never match
the runtime string.

#### 23. Every lowercase single-word enum label is rejected, and dozens are on screen

`_message` (`tools/extract_ui_catalog.py:215`) drops any candidate matching
`[a-z0-9_.:/-]+` unless it is in `label_position` — and `_option_labels`
(`:337-344`) only recognises a *literal* `["value","label"]` pair or a literal
`el("option", …, "text")`. Every list rendered from a JS variable is invisible to
it. Measured against `en/ui.json`:

* `MEM_CATS` (`utils.js:183`, rendered at `chat.js:2044`, `:2396`, `:2629`):
  `episode`, `dialogue`, `promise`, `relationship`, `person`, `place`,
  `semantic`, `intention`, `emotion`, `self`, `inference` — **all 11 MISSING**.
* `MEM_PROV` (`utils.js:184`, rendered at `chat.js:2047`, `:2401`, `:2634`):
  `witnessed`, `heard`, `told`, `read`, `inferred`, `remembered` — **all 6
  MISSING**.
* `ATTIRE_REGIONS` (`components.js:446`, rendered as checkbox labels at
  `components.js:525`, region rows at `:621`, and `<option>`s at `:800`):
  `torso`, `waist`, `head`, `arms`, `hands`, `legs`, `feet` MISSING (`groin` is
  present, from an unrelated sentence).
* Ability levels (`components.js:676`): `novice`, `competent`, `expert`,
  `master` — MISSING.
* Knowledge tags (`lorebooks.js:1823`): `common`,
  `scholarly`, `esoteric` — MISSING. Range (`lorebooks.js:1828`): `global`
  MISSING.
* `EXTRA_PART_ASPECTS` (`components.js:794`, rendered at `:802`): `front`,
  `back`, `top`, `underside`, `left`, `right`, `sides` — MISSING.
* `fCoveragePicker`'s summary word `"auto"` (`components.js:499`) — MISSING.

The MEM_CATS/MEM_PROV case compounds with finding 4: the server ships the
canonical lists, the browser hard-codes them, and the extractor cannot see
either — so the memory browser's two most-used dropdowns are English in every
language pack.

### I. Comments describing behaviour the code no longer has

#### 24. `dressing/ambience.py` contradicts itself about server-side music filtering

`ambience.py:994-997`, above `_MUSIC_CATEGORY`:

> Freesound's own taxonomy … Requested as a field **and, where a layer may not
> have music at all, excluded server-side so they are never fetched.**

`ambience.py:1286-1291`, inside `_freesound_page`, says the opposite and is the
one that matches the code:

> Music cannot be excluded here the way the licence is: `category` is a field
> Freesound will RETURN but not one its search server will filter on —
> `category:"Music"` narrows, `-category:"Music"` answers 400 "undefined field
> category". So it comes back with every result and is weighed in
> `_rank_candidates` instead.

The actual filter string (`ambience.py:1291-1292`) is
`"duration:[%d TO %d] license:(%s)"` — no category term. The first comment
describes a filter that was tried, refused by the API, and removed; a reader
auditing the weather layer's music veto is told the hard exclusion happens at
the server when it happens entirely in `_rank_candidates`.

#### 25. `build_backdrop_request`'s docstring names a key the function does not return

`dressing/backdrops.py:730-733`:

> Returns `{room, signature, cached, source}` — `source` being the
> perception-derived, people-stripped setting text an image prompt is written
> from.

The function returns `{room, room_name, signature, cached, place, time,
location, weather}` (`:740-761`). There is no `source` key; the
perception-derived text is `flavour`, and it was deliberately moved OUT of this
function for the performance reason spelled out at `:664-682` — a note the
function's own body then repeats at `:1109-1112` (*"`req.get` is not a fallback
for a missing key — the key is gone"*). The docstring is the one place still
describing the pre-move shape.

#### 26. The embedding-reconciler card claims to show a startup rebuild it never polls for

`app.js:900-909`:

> …the server reconciles the bank in the background at startup and whenever the
> `embeddings` role changes. **This is the only place a host ever sees that
> happen**: a card that appears when there is work, counts it down, says so when
> it is finished, and removes itself.

`erWatch` (`app.js:974`) is the only thing that starts the poll, and its only
caller is `erOfferRebuild` (`app.js:988`), which runs solely when the host has
just CONFIRMED a rebuild from the offer dialog. Nothing polls at boot. A
reconcile the server began at startup runs entirely invisibly; the card only
ever shows work the reader personally authorised.

#### 27. `openAmbiencePanel`'s picker cannot list the library, and the route that would says it can

Pairs with finding 8. `web/app.py:5711` — *"Everything in the local library, so
the picker can list it unfiltered."* The picker (`ambience.js:818-927`) has a
search box and a Search button and no listing path. For a host on the `local`
source with an unhelpfully-named library, there is no way to see what is in it.

### J. Response shape

#### 28. `POST /api/turns/{tid}/backdrop` omits `room_id` and `weather`, and the browser caches its payload under the turn id

`web/app.py:5494-5518` (POST) returns
`{enabled, configured, room, signature, status, ready, url}`.
`web/app.py:5446-5490` (GET) returns those plus `room_id` and `weather`, both
with comments explaining why the browser needs them:
*"The room's IDENTITY, not its display name … Two rooms can share a name; they
cannot share this"* and *"What the weather overlay should draw over this room"*.

`awaitBackdrop` (`backdrops.js:196`) returns its `first` argument — the POST
payload — without polling whenever the POST already answers `ready`, and
`generateBackdrop` (`backdrops.js:236`) then does
`BD.byTurn.set(turnId, res)`. The cached entry for that turn now lacks both
fields, so a later `backdropForTurn` for the same turn calls
`weatherFxForTurn(state)` with `state.weather === undefined` → `weatherFxApply(null)`
→ the weather overlay is torn down, and sets `BD.shownRoom = null`, defeating
the same-room hold at `backdrops.js:300-306`.

Reachability is narrow but real: the POST answers `ready` only when the image
landed between the GET miss and the POST — a second tab, or a rescroll landing
on a turn another poll just filled. `BD.byTurn` is cleared on every `renderChat`
(`backdropResetForRender`, `backdrops.js:372`), so the stale entry does not
survive a re-render. Flagged because the two routes are a matched pair
everywhere else and the ambience twin gets this right: `GET` and `POST
/api/turns/{tid}/ambience` both return through the single
`_ambience_payload` (`web/app.py:5554`, docstring: *"The one shape both ambience
routes answer with"*).

#### 29. Ambience payload fields the browser never reads

`_ambience_payload` sends a top-level `gain` (`web/app.py:5572`, the room-scoped
level) and a `track` object (`:5618-5621`, *"What is actually playing, so the
reader can see (and credit) it. The Freesound licences in play require
attribution"*). Neither is read: `ambience.js:521` sets `AMB.track` from
`state.layers[0]` instead, deliberately and with its reason at `ambience.js:502-505`,
and per-layer gain is read from `layer.gain`. `layer.query` is also unread.
Not a defect — but the server's `track` is now a second, unread representation
of the credit line the licences depend on, and the comment on it claims a
consumer it does not have.

---

## Unverified suspicions

Listed separately because I could not close them without running the app, the
suite, or the browser tests — all of which were out of bounds for this task.

* **`getMemUI` resolves three `<select>`s by index.** `chat.js:2279-2292` reads
  `layout.querySelectorAll(".toolbar select")[0..2]` as category / provenance /
  sort. The toolbar is built at `chat.js:2096-2101` in that order today, so it
  is correct — but adding a fourth control to the memory toolbar in any position
  but last silently rewires all three. Same shape for `resultLabel`, resolved as
  `.memory-main > .small.dim` (`chat.js:2287`).
* **`_visibleTurnObserver` and `RR` are module-global while `openChat` is
  re-entrant.** `chat.js` guards `openChat` with `_chatLoadSeq` and `RR` with
  `turnEl.isConnected` (`chat.js:1008`), which looks sufficient, but I did not
  trace every interleaving of a fast story switch against an in-flight
  `_mountRerollNav`.
* **`el()` translates `title`/`aria-label`/`placeholder` at construction
  (`components.js:26-28`) while `localizeDocument` translates them again from
  the MutationObserver (`utils.js:174-179`).** Double translation is idempotent
  for a catalog whose values are not themselves keys; I did not check
  `language_packs/ja/ui.json` for a value that is also a key.
* **`_VISUAL_REGISTER` multi-word terms.** `dressing/backdrops.py:370-425`
  contains `"blood spatter"`, `"torture chamber"`, `"torture device"`, and the
  substitution looks the replacement up by `m.group(0).casefold()`
  (`:466`). The regex is built from `re.escape`d literals so an exact match is
  guaranteed, and longest-first ordering (`:436`) puts the multi-word forms
  ahead of their prefixes — I believe this is correct but did not exercise it.
* **`dlg_put` recomputes the autonomy-derived keys on every save**
  (`web/app.py:4147-4148`), and the browser never sends them
  (`settings.js:460-470`). That looks deliberate — autonomy is the single dial
  — but it means any direct API caller that pinned a derived limit loses it the
  next time a host presses Save in the panel.

---

## Part 2 — what the frontend actually does, file by file

No document stated this before; this is the first. Load order is
`static/index.html`: `theme-init.js` in `<head>`, then
`utils → components → editors → lorebooks → backdrops → ambience → weather-fx →
chime → chat → settings → themes → extensions → app`, then
`/api/extensions/ui.js`.

**Note for the maintained docs:** both `CLAUDE.md` § Architecture and
`AGENTS.md` § Frontend state the order and both are STALE.
`CLAUDE.md` omits `extensions.js`; `AGENTS.md` omits `ambience.js`,
`weather-fx.js`, `chime.js` and `extensions.js`. `i18n.js` is in neither, and
correctly so — it is not loaded by `index.html` at all (see below).

### `theme-init.js` (181) — head, before first paint

**Owns** appearance-as-browser-local-state: theme id, prose size, and the
three-level effects power control. An IIFE; exports exactly one global,
`window.SONDER_APPEARANCE` (`:145`), carrying the storage keys, the defaults,
the `themes` and `effectsLevels` tables, `applyTheme`/`applyProseSize`/`applyEffects`,
and three `current*` readers. Applies all three from `localStorage` at load
(`:163-165`) — that is why it is in `<head>`: a light/dark flash otherwise.
Broadcasts `sonder-theme-change`, `sonder-prose-size-change` and
`sonder-effects-change` on `window`. Also stamps `body.page-hidden` from
`document.hidden` (`:176-180`), the CSS hook for "nobody is looking at this",
here rather than in `app.js` so the login and guest pages get it too.

**Depends on:** nothing. **Routes:** none — appearance never touches the server.
**Consumers:** `themes.js` (the whole Appearance modal), `weather-fx.js`
(`weatherFxEffectsOff`, and the `sonder-effects-change` listener at `:544`),
`app.js` (`resizeComposer` on `sonder-prose-size-change`), `settings.js`
(`syncVitalsGutter` on `sonder-theme-change`).

### `utils.js` (311) — the shared floor

**Owns** `$`/`$$`, the single mutable app state `S`, the gettext-style UI
lookup, the HTTP seam, and the download helper.

**Exports:** `$`, `$$`, `S`, `t`, `watchUILanguage`, `localizeDocument`,
`I18N_SKIP_TREE`, `I18N_SKIP_TEXT`, `MEM_CATS`, `MEM_PROV`, `hasDefaultModel`,
`safeId`, `splitCL`, `numOr`, `taggedError`, `api`, `streamPost`, `downloadJSON`.

`t(source, vars)` is source-English-as-message-id with two template rules
compiled once into `S.uiTemplateRules` (`:36-53`): a key of pure placeholders is
rejected below three characters of literal text, and rules sort by how much
literal text they anchor. Captures are themselves translated (`:63-67`).
`localizeDocument` walks text nodes and the four chrome attributes, honouring
`translate="no"`/`[data-no-i18n]` as a subtree opt-out and `textarea`/`input`
as a content-only one. `watchUILanguage` installs the permanent MutationObserver
(childList + subtree + the four attributes) that keeps dynamically-built DOM
localized.

`api(method, url, body)` is the one JSON seam: `cache: no-store`, 401 →
`location.href = "/login"` (403 deliberately does not redirect — a valid
guest-scoped session), body parsed for `detail`/`error`, and the chime armed on
the way in and rung on the way out. `streamPost` is the NDJSON reader for the
pipeline stream, with the same 401 contract. `taggedError(kind, message)` is the
shared tag the backdrop and ambience poll loops classify their endings by
(`failed` / `notfound` / `slow` / `gone`).

**Depends on:** `chime.js` (deferred, guarded). **Routes:** whatever its callers
pass.

### `components.js` (993) — the widget library

**Owns** DOM construction, the modal singleton and its stack, the
confirm/prompt replacements, toasts, the background-task panel, every form
control, and the model picker.

**Exports (45):** `txt`, `el`, `coverOfRow`, `coverOfTitle`, `modal`,
`modalOwnership`, `closeModal`, `closeAllModals`, `_confirmOverlay`,
`confirmModal`, `promptModal`, `promptModalWithToggle`, `toastHost`, `toast`,
`renderActivity`, `elapsedLabel`, `activityTicking`, `backgroundTask`,
`buttonTask`, `loadingBlock`, `emptyState`, `fText`, `fArea`, `fSelect`,
`fNum`, `fLineList`, `fStrList`, `fCoveragePicker`, `fAttireGarments`, `fList`,
`fAbilities`, `fTraits`, `fValues`, `fBeliefs`, `fCopingStrategies`,
`fAssociations`, `fGoals`, `fSenses`, `fLatent`, `fExtraParts`, `fPronouns`,
`phEditor`, `fetchModels`, `fetchImageModels`, `modelCombobox`, plus the
constants `BOOK_COVERS`, `ATTIRE_REGIONS`, `ATTIRE_REGION_ZONES`,
`ATTIRE_COVERAGE`, `EXTRA_PART_ASPECTS`.

`el()` is the one construction path and runs every string child and the four
chrome attributes through `t()` BEFORE insertion; `txt()` is the escape hatch
for story text, and is why `translate="no"` on the transcript works at all.
`modal()` is a singleton over `#modal`/`#modalbody` with a real stack
(`S.modalStack`) holding LIVE nodes, so a confirm opened over an editor restores
the editor's attached listeners. `modalOwnership(body)` mints a token so async
work can ask whether it still owns the dialog. `confirmModal`/`promptModal`
deliberately bypass that stack with their own `.confirm-overlay` appended to
`<body>`. `backgroundTask` is the activity-panel wrapper (label, `onSuccess`,
`successMessage`, `errorPrefix`, `onError`, `onFinally`); `buttonTask` is the
inline one, and marks errors `__handled` so `app.js`'s net does not re-toast.
`modelCombobox` is the provider+model picker with sequence-guarded catalogue
loads, an `opts.suggest` narrowing filter, an `opts.extra` merged suggestion
list, and a self-removing document click handler.

**Depends on:** `utils.js` (`$`, `S`, `t`, `el`'s consumers, `splitCL`, `api`).
**Routes:** `GET /api/providers/{pid}/models`, `GET /api/providers/{pid}/image_models`.
**Backend pairing:** `ATTIRE_REGIONS`/`ATTIRE_REGION_ZONES` mirror
`story/attire.py`'s closed region set; `EXTRA_PART_ASPECTS` mirrors
`story/character_schema.py:470`'s `EXTRA_PART_ASPECTS`. Coverage `auto` is sent as a
flag, never resolved here, because `attire.py` owns the cue table.

### `editors.js` (942) — character, persona, import, generate

**Owns** the two big card editors and the four small dialogs around them.

**Exports (15):** `appearanceFillButton`, `defaultCharacterSheet`,
`greetingCarousel`, `quickStartModal`, `charEditor`, `personaEditor`,
`promotionReviewModal`, `promoteBackgroundPresence`, `importModal`,
`generateModal`, `generateLoreModal`, `loreModal` (dead — finding 1),
`exportCharacter`, `exportPersona`, `exportLorebook`.

`charEditor(c, {chatId})` serves three shapes from one form: new character,
library character, and per-story card (`isChatCard`, which disables the name
field and routes the save to the chat-scoped card endpoint). It reads and writes
the whole `character_schema` sheet field by field — see finding 12 for what it
does not carry. `greetingCarousel` is the swipeable greeting editor whose
`read()` feeds back into the main Save. `personaEditor` is the narrower twin.
`promotionReviewModal` is deliberately raw JSON + a per-line memory list rather
than a second bespoke form.

**Depends on:** `components.js` (every `f*` builder, `modal`, `toast`,
`backgroundTask`), `utils.js` (`api`, `splitCL`, `downloadJSON`), and forward
onto `boot`/`openChat`/`loreModal`.
**Routes:** `POST /api/{characters,personas}/{id}/fill_appearance`,
`POST /api/characters/{id}/fill_psychology`,
`POST /api/characters/{id}/generate_greeting`,
`POST /api/characters/{id}/recover_greetings`,
`POST /api/characters/{id}/start`,
`PUT|POST /api/characters`, `PUT|POST /api/personas`,
`PUT /api/chats/{cid}/characters/{ch}/card`,
`POST /api/chats/{cid}/promotions/{draft,confirm}`,
`POST /api/{characters,personas,lorebooks}/import`,
`POST /api/{characters,personas}/generate`,
`POST /api/lorebooks/{lid}/generate`,
`GET /api/{characters,personas,lorebooks}/{id}/export`,
plus the dead `loreModal`'s `GET|PUT /api/lorebooks/{lid}`,
`PUT|DELETE /api/lore_entries/{eid}`, `POST /api/lorebooks/{lid}/{entries,reinterpret}`.

### `lorebooks.js` (3,606) — the lorebook workspace

**Owns** the library sidebar, the three-panel workspace modal (tree / inspector
/ connections), the entry editor, the relationship editor, and the advanced
generator with its interrupted-run recovery.

**Exports (51 functions + `LORE_INHERITANCE_MODES`, `DEFAULT_LORE_LINK_TYPES`,
`loreUI`).** The load-bearing ones: `renderLoreLibrarySidebar` (the "Lore" tab),
`openLoreWorkspace` (the single persistent modal — the whole reason
`window.loreModal` is reassigned), `loadLoreWorkspaceData`, `buildLoreWorkspace`,
`renderWorkspaceTree`, `renderLoreInspector`, `renderLoreEntries`,
`buildLoreEntryCard`, `renderLoreBookEditor`, `renderRelationshipOverview`,
`renderLoreRelationshipEditor`, `renderLoreGenerator`,
`refreshLoreGenRecovery`, `renderLorePlanPreview`, `acceptedGeneratorPlan`,
`normalizeLoreBook`, `loreVisibleIds`, `parseStoredJSON`, `splitNumberList`.

`loreUI` is the module's own persistent view state (selection, tab, expanded
sets, filters, drag id, and the `rendering`/`renderOwner` pair that makes an
in-place body swap safe). The workspace is ONE modal reused in place —
`openLoreWorkspace` only calls `modal()` when `loreWorkspaceVisible()` is false —
which is the fix for `modal()`'s stacking behaviour piling up identical windows.
`loadLoreWorkspaceData` deliberately reads OWNERSHIP
(`GET /api/chats/{cid}/lorebooks`) rather than reachability, so a book the chat
owns but nothing hangs off is still editable; the server's `retrievable` flag is
rendered as an "unreachable" badge (`:1053-1064`). Both filter inputs are
debounced at 120ms. The generator tab's recovery banner asks
`GET /api/lorebooks/{lid}/generate_job` on every open and offers
restore / resume / discard against the server's job row, since that row — not
this tab's memory — is what survives a closed tab.

**Depends on:** `components.js`, `utils.js`, `editors.js` (`importModal`,
`exportLorebook`), and forward onto `boot`/`renderSide`.
**Routes:** `GET|PUT|DELETE /api/lorebooks/{lid}`, `POST /api/lorebooks`,
`GET /api/chats/{cid}/lorebooks`, `GET|POST /api/lorebooks/{lid}/links`,
`PUT|DELETE /api/lorebook_links/{id}`,
`POST /api/lorebooks/{lid}/{move,reorder,entries,reinterpret,generate,generate_plan,apply_plan}`,
`GET /api/lorebooks/{lid}/generate_job`,
`POST|DELETE /api/lore_gen_jobs/{id}[/resume]`,
`PUT|DELETE /api/lore_entries/{eid}`.

### `backdrops.js` (430) — the picture behind the transcript

**Owns** the two cross-fading image layers, the readability scrim, the
per-signature generation dedupe, and the two-clock commissioning policy.

**Exports (15):** `BD` (module state), `BD_SETTLE_MS`/`BD_DWELL_MS`,
`BD_VEIL`/`BD_PANEL_MIN`/`BD_PANEL_MAX`, `BD_POLL_MS`/`BD_POLL_LIMIT`,
`backdropLayers`, `backdropLuminance`, `applyBackdropContrast`,
`releaseBackdropLayer`, `clearBackdrop`, `showBackdrop`, `backdropWorking`,
`awaitBackdrop`, `generateBackdrop`, `backdropForTurn`, `backdropOnVisibleTurn`,
`backdropResetForRender`, `updateBackdropBtn`, `toggleBackdrops`,
`syncBackdrops`.

The policy is the design: reading an existing picture is free and follows the
scroll at 220ms; COMMISSIONING one costs money and waits 2s of dwell (skipped
for a freshly generated turn, which is flagged `opts.fresh`). A miss holds the
previous image only while it is a picture of the SAME room (`state.room_id !==
BD.shownRoom` → `clearBackdrop`). `releaseBackdropLayer` drops a faded layer's
bitmap so a long story does not accumulate GPU textures. The contrast pass reads
the middle band's Rec. 709 luma and sets `--bd-veil`/`--bd-panel`, after
revealing the image so a canvas failure cannot leave a paid-for picture
invisible. `BD.failed` blacklists only a RECORDED verdict (`kind === "failed"`),
never a timeout or a cancellation.

**Depends on:** `utils.js` (`$`, `api`, `taggedError`), `components.js` (`el`,
`toast`), and forward onto `weather-fx.js` (guarded).
**Routes:** `GET|POST /api/turns/{tid}/backdrop`, `PUT /api/backdrops`.
**Backend pairing:** `dressing/backdrops.py` — see below.

### `ambience.js` (982) — the sound of the room

The audio twin of `backdrops.js`, same two-clock policy, same signature dedupe,
same "hold only within the same room" rule — plus mixing.

**Exports (31 + `AMB`, the fade/loop/poll constants, `AMB_ONESHOTS`,
`AMB_ONESHOT_TAKES`, `AMB_ROLE_LABEL`).** Key ones: `playAmbience`
(cross-fades a whole MIX at once, every layer loaded to `canplay` before the
fade starts), `armSeamlessLoop`/`crossLoop` (each layer keeps a second `<audio>`
on the same file and hands over across the seam with an equal-power curve,
because `loop = true` audibly stops for MP3 encoder padding), `ambienceForTurn`,
`ambienceOnVisibleTurn`, `resolveAmbience`, `awaitAmbience`, `rerollAmbience`,
`playAmbienceOneshot`, `openAmbiencePanel`, `ambienceMixPanel`,
`ambienceLayerRow`, `toggleAmbience`, `toggleAmbienceMute`, `setAmbienceVolume`,
`setLayerGain`, `syncAmbience`.

Mute and volume are client-only and sticky in `localStorage`, restored
synchronously at load (`:975-977`) so no bed can start before the reader's own
mute is known. Unlike backdrops, "off" means SILENT — a paid-for picture costs
nothing to keep showing, a sound has to stop. A `silent` room is a RESOLVED
state with `ready: true`, so it crossfades to quiet and is never re-asked.
The panel credits every layer's uploader and licence, because the Freesound
licences require it.

**Depends on:** `utils.js`, `components.js`. **Consumers:** `weather-fx.js`
calls `playAmbienceOneshot` for thunder — routed through here rather than played
directly so a thunderclap cannot ignore the mute button.
**Routes:** `GET|POST /api/turns/{tid}/ambience`,
`GET /api/chats/{cid}/ambience/oneshot/{name}`,
`GET /api/ambience/search`, `PUT|DELETE /api/chats/{cid}/ambience/pin`,
`PUT /api/ambience`.

### `weather-fx.js` (548) — rain, snow and lightning

**Owns** the precipitation overlay and the storm.

**Exports (19 + `WFX` and eight tuning tables):** `weatherFxApply` (the one entry
point), `weatherFxForTurn` (called by `backdrops.js` with the per-turn payload),
`weatherFxBuild`, `weatherFxTile`, `weatherFxStop`, `weatherFxVisible`,
`weatherFxStormy`, `weatherFxScheduleFlash`, `weatherFxFlash`, `weatherFxBolt`,
`weatherFxThunder`, `weatherFxOpenSky`, `weatherFxReach`, `weatherFxReduced`,
`weatherFxEffectsOff`, `weatherFxSupported`, `weatherFxHost`,
`weatherFxClearLayers`, `weatherFxRandom`.

Not a particle system: one deterministically-generated seamless tile per layer,
handed to CSS as a repeating background and moved by a `transform` animation —
compositor work, no JavaScript per frame. Three layers at different tile sizes,
speeds and opacities, with snow additionally carrying a per-layer sway wrapper
whose periods do not divide each other. Rebuilds only when the LOOK changes
(`kind|intensity|wind|reach|severity`), so consecutive turns in one room do not
restart every drop mid-fall. Lightning is separate DOM + timers because a flash
has to hand a timestamp to the audio layer. `weatherFxVisible` reads
`weather_visible` and falls back to the older narrower `sky_visible`; the drawn
BOLT is gated on `sky_visible` specifically, because a channel drawn under an
awning is wrong. Pauses everything on `visibilitychange` and re-applies on
`sonder-effects-change`.

**Depends on:** `components.js` (`el`), `ambience.js` (`playAmbienceOneshot`,
guarded), `theme-init.js` (the effects level, read off `document.documentElement.dataset`).
**Routes:** none directly — it is fed `state.weather` from the backdrop payload.

### `chime.js` (179) — "your turn is ready"

**Owns** the completion chime. **Exports (8 + `CHIME`, `CHIME_NOTES`,
`CHIME_EXCLUDED`, `CHIME_MUTATIONS`, `CHIME_MIN_MS`):** `chimeContext`,
`chimeArm`, `chimePlay`, `chimeWatches`, `chimeWorkFinished`, `chimeSetMuted`,
`toggleChimeMute`, `updateChimeBtn`.

Synthesised (two sine tones through a gain envelope) so there is nothing to
fetch at the moment it is needed, and scheduled on `ctx.currentTime` rather than
`setTimeout` so it sounds identical from a backgrounded tab — the only place it
matters. Armed on the gesture that STARTS the wait (`api()` on the way in, and
`runStream`), not the one that ends it. The rule for which waits earn a chime is
DURATION, not a route list: any `POST`/`PUT`/`PATCH` taking ≥4s, excluding
`/backdrops?/` and `/ambience/` (whose results announce themselves). Mute is
global and sticky in `localStorage`.

**Depends on:** `utils.js` (`$`). **Routes:** none.

### `chat.js` (2,875) — the transcript, the run, and the pipeline drawer

The largest and most load-bearing file. **Owns**: which turn is being read, the
transcript render, dialogue tinting, inline emphasis, the streaming run, the
narration preview, reroll browsing, the pipeline drawer with its lens system,
the relationship viewer, and the whole memory browser.

**Exports (78).** Grouped by what they own:

* **Visible-turn tracking** — `observeVisibleTurn`, with the module state
  `_visibleTurnObserver`, `_freshTurnId`, `_freshRunPending`. ONE
  `IntersectionObserver` and one notion of "the turn being read", so the picture
  and the sound can never disagree about which room the reader is in. `fresh` is
  keyed by turn id rather than a one-shot boolean, because the work it authorises
  is deferred past `BD_SETTLE_MS`.
* **Prose painting** — `foldTypography`, `decodeProseEntities`, `splitEmphasis`,
  `appendEmphasized`, `quoteBody`, `quotedRegions`, `speechSpans`, `paintProse`,
  `proseEl`. Never `innerHTML`: model output reaching an HTML parser is an
  injection surface. Emphasis is a closed allowlist of eleven tag names
  (`_EMPHASIS_TAGS`) converted into elements this code creates, with `<font>`
  carrying an ink NAME resolved to a CSS class, never a colour value. Runs nest
  recursively. Dialogue tinting matches each logged quote into the prose it is
  required by DIALOGUE FIDELITY to appear in, and colours the whole QUOTED
  REGION rather than the matched substring — which is what handles the narrator
  legitimately merging several `dialogue_log` entries into one utterance.
* **Rendering** — `openChat` (sequence-guarded against out-of-order navigation),
  `renderChat`, `renderFrameBar`, `switchFrame`, `updateChatScopedButtons`,
  `branchTurn`, `editTurnInput`, `editTurnProse`.
* **The run** — `runStream`, `runReroll`, `rerollTurn`, `abortActiveRun`,
  `confirmCheckpointRestore`, `handleEvt`, `liveReset`, `liveStep`,
  `liveAppend`/`liveFlush` (token deltas buffered per step and flushed once per
  animation frame — the naive `textContent +=` is quadratic in transcript
  length), `turnStatusStart`/`Set`/`Stop`, `friendlyPhase`,
  `FRIENDLY_STEP_LABELS`, `FRIENDLY_SUBAGENTS`, `showNarrationEarly`,
  `clearNarrationEarly`. `_activeRun` pins the story and frame a run started in,
  so Stop aborts the pipeline that is actually running rather than whatever is
  on screen. `handleEvt` re-emits five event types to `window.Sonder` AFTER the
  host has handled them.
* **Reroll browsing** — `RR`, `_mountRerollNav`, `_paintRerollCount`,
  `showRerollVariant`, and the ←/→ key handler. Newest turn only; selecting a
  variant marks nothing stale, because which rendering the reader sees is
  presentation.
* **The pipeline drawer** — `openPipeline`, `stepLenses`, `perceiverViews`,
  `loopMindIds`, `specialistIds`, `lensSlice`, `specialistSlice`,
  `perceiverSlice`, `mindSlice`, `keySlice`, `renderLensBar`, `lensLabel`,
  `facetBadge`, `perceiverLabel`, `renderEngineNotes`. A step is read through a
  LENS derived from its CONTENT, not declared per key, so a stage that grows a
  field gets a button for it. Four kinds, in priority order: `specialist` (the
  Director's prose author plus its six specialists, sourced from
  `content.orchestration.specialists`), `perceiver` (`content.views`), `mind`
  (loop rounds), `key` (the generic fallback). An extension-owned step key
  renders through `Sonder._stepRenderer`.
* **Relationship viewer and memory browser** — `relMeter`,
  `relationshipModal`, `memModal` and its sixteen helpers, plus `chatPH` and
  `personaPH` for private history.

**Depends on:** everything above it, plus `settings.js`/`app.js` forward via
`window.X?.()`.
**Routes:** `GET /api/chats/{id}`, `DELETE|PUT /api/turns/{id}[/input|/prose]`,
`POST /api/turns/{id}/{branch,reroll,resume,rerun}`,
`GET|POST /api/turns/{id}/narration`, `GET /api/turns/{id}/pipeline`,
`POST /api/steps/{id}/{activate,reroll,edit}`,
`POST /api/chats/{cid}/turns` (stream), `POST /api/chats/{cid}/abort`,
`GET|POST /api/chats/{cid}/export|import`,
`GET /api/chats/{cid}/characters/{ch}/{relationships,memories,memories/search,memories/export,memories/import,memories/coverage,memories/consolidate,memories/backfill,memory-context,private_history}`,
`PUT|DELETE /api/memories/{id}`,
`GET|PUT /api/chats/{cid}/persona_private_history`.

### `settings.js` (3,607) — every configuration surface

**Owns** the six top-toolbar modals other than Appearance and Prompts-adjacent
ones, the cast/lorebooks/condition/insights/multiplayer/frames tabs, the whole
API-connections panel, software updates, the prompts editor, and the extensions
menu. Binds `#b-world`, `#b-attire`, `#b-style`, `#b-dlg`, `#b-cast`, `#b-api`,
`#b-update`, `#b-prompts`, `#b-extensions` at load.

**Exports (43 + `VITAL_ROWS`, `MODEL_RECOMMENDATIONS`, `REOPEN_PROMPTS_KEY`,
`REOPEN_EXTENSIONS_KEY`, `EXTENSION_UPDATES`, and the vitals/story-width
constants).** Notable groups:

* **Cast tab** — `renderCastTab`, `dialogueColorControl` (the swatch shows the
  RESOLVED colour and edits the host's PICK; "auto" clears the pick rather than
  storing the derived value, so the colour keeps following the card),
  `hydrateCastLocations`, `castRoomSelect`, `castRoomLabel`,
  `renderBackgroundPresencesPanel`.
* **Condition** — `renderConditionTab`, `hydrateConditionTab`, `vitalMeter`,
  `vitalsBlock`, `refreshVitalsHud`, `clearVitalsHud`, `hideVitalsHud`, and the
  gutter measurement `syncVitalsGutterNow`/`syncVitalsGutter`. That measurement
  is the most delicate layout code in the app: it reads `#composer` and
  `#composer-inner` geometry plus the ambience cluster's width, then writes
  `--vitals-*` and the global `--story-width`. All reads precede all writes,
  it is coalesced to one pass per frame, and it is driven by `resize`,
  `sonder-theme-change`, and two `ResizeObserver`s (`#composer` for the sidebar
  collapsing, `#ambience-bar` because it is absolutely positioned and cannot
  report its own growth by resizing a parent).
* **Frames and paradox** — `renderFramesTab`, `renderFramesListPanel`,
  `renderPersonaStationingPanel`, `renderParadoxPanel`.
* **Insights** — `renderInsightsTab`, `renderDramaticIronyPanel`,
  `renderPromiseLedgerPanel`. Deliberately host-only meta views across every
  character's private memories at once.
* **API connections** — `renderFirstRunProviderSetup` (the one-button path for
  zero providers), `renderFullApiSettings` (providers, response limit,
  OpenRouter upstream routing, scene backdrops, affect habituation, attire
  "beneath", room ambience, Director fan-out concurrency, then the per-role
  model rows), `modelRecommendationsBlock`, `embeddingBankBlock`,
  `preferredBackdropSize`. The role rows implement follow-Default as a live
  binding: a following role is left UNSET on save so it keeps deferring
  dynamically rather than pinning today's snapshot, and `embeddings` may never
  follow, because a chat model there degrades to the local hash without a word.
  Extension model lanes render last, with the full generic row.
* **Updates and maintenance** — `renderUpdateChecking`/`Error`/`Status`/`Done`,
  `runUpdateInstall`, `checkpointCompactionBlock`.
* **Prompts** — `openPromptsModal`, `reopenPromptsIfRequested`. One control sets
  the prompt sheets, the interface language and the open story's language
  together; a language change reloads the page and leaves a sessionStorage
  marker to come back here.
* **Extensions** — `openExtensionsMenu`, `extensionTrustNote`,
  `extensionCapabilitySummary`, `extensionSettingsSections`,
  `reopenExtensionsIfRequested` (dead — finding 16). Enabling is the consent
  moment and carries the trust warning; it hot-loads through `Sonder._load`
  rather than reloading the page.

**Routes:** roughly sixty, the largest single consumer in the frontend. The
distinctive ones: `GET|PUT /api/chats/{cid}/{world,attire,style_guide,language,survival,player_authority,dialogue_config,background_config,living_world,vitals,positions,frames,personas,paradox_policy,fixed_points,guest_invites,promotable,dramatic_irony,promises}`,
`PUT /api/chats/{cid}/characters/{ch}/{dialogue_color,position}`,
`PUT /api/{ui-language,agent_models,reasoning_effort,max_output_tokens,image_model,backdrops,ambience,affect_habituation,attire_beneath,director_fanout_mode,openrouter_routing,active_preset,prompt_presets}`,
`GET|PUT|DELETE /api/providers[/{id}[/prompt_cache]]`,
`GET /api/openrouter/endpoints`, `GET|POST /api/memory/embeddings[/rebuild]`,
`GET|POST /api/maintenance/checkpoints[/compact]`,
`GET|POST /api/updates/{check,install}`,
`GET|POST|DELETE /api/extensions[...]`.

### `themes.js` (159) — the Appearance modal

**Owns** the visual presentation of `theme-init.js`'s state. **Exports:**
`themePreview`, `openAppearanceSettings`, `appearanceButton`. Reads
`window.SONDER_APPEARANCE` and does nothing if it is absent. Theme cards with a
drawn miniature, a prose-size segmented control, the effects segmented control
with its description line, and a reset. Binds `#b-theme`.

**Depends on:** `theme-init.js`, `components.js`. **Routes:** none.

### `extensions.js` (657) — the extension host

**Owns** every registry an extension's UI talks to. Defines exactly one global,
`window.Sonder` (`:657`); no top-level DOM access, so it cannot break the boot
it precedes.

**Public surface:** `registerSidebarTab`, `registerTopBarButton`, `registerView`,
`registerComposerControl`, `registerSettingsSection`, `registerStepRenderer`,
`on`/`off`/`emit`, `notify`/`dismissNotice`/`notices`, `state`, `api`, `call`,
`extState`, `refresh`, `openView`/`closeView`, and the `chats` namespace
(`list`, `get`, `create`, `open`, `branch`, `narration`, `selectNarration`,
`reroll`).

**Host-internal:** `_begin`/`_end` (ownership attribution around the classic
`ui.js` bundle), `_facade`/`_publicNames`/`_publicNamespaces`/`_loadModule` (the
ES-module path, which binds the owner per call rather than relying on ambient
state that an `await` would leak), `_safe`/`_fault` (three-strikes retirement),
`_unregister`, `_load`/`_unload`/`_dropAssets`/`_elementId` (hot load, because a
`<script>` tag loads once and a page served while an extension was off holds
zero bytes of it), `_sidebarTabs`, `_stepRenderer`, `_settingsFor`,
`_renderTopBar`/`_renderComposer`/`_renderView`/`_renderNotices`/`_renderSidebarTab`.

The doctrine is `app.js`'s `typeof fn === "function"` guard made systematic:
every extension callback runs through `_safe`, a throw is charged to its owner,
and three throws retire that extension's whole interface. Deliberately absent
and documented as such: posting an assistant message.

**Depends on:** `utils.js` (`S`, `window.api`), `chat.js` (`openChat`, guarded),
`app.js` (`renderSide`, guarded). **Routes:** `/api/extensions/{id}/...` via
`call`, plus whatever `chats.*` forwards.

### `app.js` (1,042) — boot, sidebar, wizard, composer

**Owns** the entry point and everything the shell needs.

**Exports (25 + `LORE_LINK_TYPES`, `ER`):** `boot`, `renderSide`,
`syncExtensionTabs`, `renderChatSidebar`, `renderCharacterSidebar`,
`renderPersonaSidebar`, `renderLegacyLoreSidebar`, `newChatWizard` and its five
step functions (`renderWizardChoice`, `renderWizardPersona`,
`renderWizardCharacters`, `renderWizardScenario`, `runWizard`) plus
`wizardState`, `wizardFromScratch`, `storyLanguagePacks`,
`defaultStoryLanguage`, `updateNSFWBtn`, `toggleNSFW`, `resizeComposer`,
`erCard`, `erDismiss`, `erPoll`, `erWatch`, `erOfferRebuild`.

`boot()` fetches `/api/bootstrap`, installs the UI catalog and language,
localizes the document, starts the language observer, syncs the two optional
media modules (guarded), renders the sidebar, and renders the transcript only
when no chat is open. It runs at the bottom of the file (`:1029`), with
`reopenPromptsIfRequested` and `reopenExtensionsIfRequested` behind it.
`syncExtensionTabs` rebuilds extension tabs into `#tabs` on every `renderSide`,
which is what makes a disabled or retired extension lose its tab.
`renderLegacyLoreSidebar` is the fallback used only if `lorebooks.js` failed to
load. The wizard is three steps landing in ordinary persona/character records —
quick start is a fast way to fill them in, not a separate mode. `resizeComposer`
is coalesced per frame and reads its ceiling from CSS rather than repeating the
number. The `ER` block is the embedding-reconciler progress card (see
finding 26).

**Routes:** `GET /api/bootstrap`, `POST|PUT|DELETE /api/chats[/{id}]`,
`DELETE /api/{characters,personas}/{id}`,
`POST /api/{personas,characters}/generate`, `POST /api/chats/{id}/characters`,
`POST /api/lorebooks`, `PUT /api/nsfw`,
`GET|POST /api/memory/embeddings[/rebuild]`.

### `i18n.js` (106) — NOT loaded by `index.html`

Standalone localization for `static/login.html:7` and `static/guest.html:7`,
which deliberately do not load the SPA. Its header states the reason: the host
page gets the same behaviour from `utils.js` + `app.js`, and running both meant
a second catalog fetch, a second permanent observer, and a race over which one
localized a node first. Fetches `GET /api/ui`, compiles the same template rules,
and installs the same MutationObserver. See finding 6 for the drift.

### `static/index.html` (178)

56 ids. Structure: `#app` → `#side` (`#tabs`, `#sidelist`, `#sideactions`) +
`#main` (`#top` with `#chatname`/`#framebar`/`#streamtgl`/`#topactions`,
`#vitals-npcs`, `#msgs`, `#turnstatus`, `#live`, `#composer` with
`#composer-inner` and `#ambience-bar`, `#vitals`) + `#drawer`, then the `#modal`
singleton, `#activity`, `#toasts`.

Three placement decisions are load-bearing and commented in the file:
`#ambience-bar` is a SIBLING of `#composer-inner` (inside that wrapper it would
take width from the input, which carries the prose column's measure);
`#vitals` is a SIBLING of `#composer` (as a child it painted under
`#composer-inner` and z-index could not reliably win); `#live` carries
`translate="no"` because it streams model tokens.
`/api/extensions/ui.css` is the last stylesheet so an extension theme is in
effect before first paint; `/api/extensions/ui.js` is the last script so it
registers against a fully-defined host.

### `dressing/backdrops.py` (1,262) — the picture, server side

**Owns** the prompt projection, the cache key, generation, continuity, and the
out-of-band queue. Runs entirely outside the turn pipeline.

Three rules, all verified against the code:

1. **The prompt is built from STRUCTURED spatial data with spoiler categories
   dropped by construction.** `room_projection` (`:526`) is a WHITELIST over
   `_PLACE_FIELDS = ("name","desc","light")` plus light sources, exits,
   overlays, weather and time. `notes` is deliberately excluded despite
   describing the room, because it is freeform and carries occupants;
   `scene.location` is excluded because historical checkpoints carry stale
   labels.
2. **Backdrops depict the room EMPTY.** Falls out of rule 1 for everything but
   `rooms[id].desc`, which live data proved carries populations — so that one
   field additionally goes through `place_desc` → `_setting_only` → the
   `_PERSON_WORDS`/`_BODY_WORDS` sentence filters, then `to_visual_register`.
3. **A cache key is a room plus its VISIBLE state.** `visual_signature`
   (`:135`) hashes the PROJECTED description, the time bucket, the viewer's
   light, the light sources, the room-scoped weather WORDS, and the three
   `VISUAL_STYLE_KEYS`. `director_notes`/`mapping_notes` are excluded because
   they never touch a pixel — a live story lost every backdrop when they were
   in the key.

`to_visual_register` (`:442`) rewrites charged vocabulary into what the eye sees
("blood" → "dark red staining"), applied to both the prompt and the key through
the same path so they cannot drift. `generate_backdrop` (`:1068`) holds a
per-signature lock, re-checks the cache inside it, computes the expensive
`arrival_flavour` only past every cache check, and now records
`edit_attempted`/`edit_used`/`edit_error` so a silently-failing continuity edit
is countable. `_QUEUE` (`outofband.Queue`) makes the POST return immediately;
`force` supersedes rather than joins.

**Frontend pairing:** `build_backdrop_request` (`:727`) is the read path both
routes use; `weather` on it is the room-scoped answer `weather-fx.js` draws
from, handed over already scoped *"so the frontend cannot draw rain into a
cellar by reading the wrong field."*

### `dressing/ambience.py` (2,090) — the sound, server side

The audio twin, same three rules with one deliberate difference each: the query
is structured and occupant-free for the same whitelist reason, ambience is the
room's tone and not its population (a crowd murmur appearing when a character
walks in would report presence through a channel perception never authorised),
and the cache key is the room plus its AUDIBLE state — which excludes `light`
entirely, where `visual_signature` treats it as the largest term.

Distinctive machinery, all frontend-visible:

* **Layers** (`LAYER_ROLES`, `MAX_LAYERS`, `compose_layers:727`). A room is
  rarely one sound; the weather layer carries the sky's own attenuation as its
  gain, which is impossible to express with one clip. `_ambience_payload` sends
  them as the `layers` array `ambience.js` mixes.
* **The reuse threshold** (`fingerprint_similarity:327`, `reusable_manifest:1488`).
  `_REUSE_EXACT = ("room","time","weather","anchors")` must match outright;
  everything else is graded at 0.5. Calibrated against a real run.
* **The query ladder** (`_query_ladder:1205`, `search_freesound:1376`).
  Freesound ANDs query terms, so every full room query returns nothing;
  broadening is mandatory. Prefix rungs plus single-term probes, and the caller
  keeps going until a rung returns a recording that is actually OF the room
  (`_GOOD_FIT`), returning the best it saw rather than the first thing it found.
* **Role vetoes** (`role_veto:1023`). The weather layer may never be music,
  thunder or wildlife — a hard filter with no fallback, because a rain layer
  that is a guitar is worse than no rain layer.
* **Silence as a resolved state.** `refine_layers` may answer `silent`, which is
  cached like any other manifest so a quiet room settles once. `ambience.js`
  renders it as an explicit "Nothing to hear in this room" rather than as a
  stalled search.
* **`AmbienceNotFound`** (`:2012`) exists so `ambience_error_kind` can hand the
  browser `notfound` vs `failed`, which is what `taggedError` in `utils.js`
  keys the toast's severity and give-up decision on.

---

## Cross-document verdicts

| document | verdict |
|---|---|
| `CLAUDE.md` § Frontend script order | **STALE** — omits `extensions.js` |
| `AGENTS.md` § Frontend script order | **STALE** — omits `ambience.js`, `weather-fx.js`, `chime.js`, `extensions.js` |
| `AGENTS.md` routing row "Browser UI" | **RIGHT** |
| `AGENTS.md` routing row "Inspecting a turn" | **RIGHT** — every named symbol (`openPipeline`, `perceiverViews`, `perceiverSlice`, `renderEngineNotes`, `liveStep`) exists and does what the row says |
| `AGENTS.md` routing row "Weather, and how much of it a room gets" | **RIGHT** — the sight/sound channel split is honoured on both sides (`visual_signature` uses `"sight"`, `acoustic_fingerprint` uses `"sound"`) |
| `AGENTS.md` routing row "Authoring edits to live positions" | **RIGHT** |
| `tools/extract_ui_catalog.py` `READER_FACING_TABLES` | **STALE** — names two symbols that do not exist (finding 21) |
| `dressing/ambience.py` `_MUSIC_CATEGORY` comment | **STALE** — contradicted by the code and by its own sibling comment (finding 24) |
| `dressing/backdrops.py` `build_backdrop_request` docstring | **STALE** — names a `source` key the function does not return (finding 25) |

Nothing in this slice was found built-and-quietly-lost on the JavaScript side:
every mechanism the maintained docs claim for the browser was located, live and
reachable. The losses are all on the SEAM — a route with no caller (findings
7, 8), a setting with no control (2), a stored flag with no writer (9), a field
on the wire that nothing reads (10, 11, 29), and a card field the editor
destroys on save (12).
