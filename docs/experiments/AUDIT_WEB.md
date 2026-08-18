# Audit: `web/` and `extension_runtime/`, read whole

Working notes in the register of
[`AUDIT_DIRECTOR.md`](AUDIT_DIRECTOR.md) — flag, never fix; evidence as
`file:line`; anything unverified goes at the end under its own heading.

**Scope:** every line of `web/app.py` (5,772), `web/auth_routes.py` (176),
`web/guest_access.py` (355), `web/story_view.py` (670), `web/__init__.py` (6),
`extension_runtime/__init__.py` (2,182) and `extension_runtime/api.py` (2,201).
11,362 lines, read end to end.

**Baseline:** working tree at `4f33b17` (alpha 9.5+), 2026-08-18. Every
`file:line` is as of that tree. Nothing here was changed; `docs/UNBUILT.md` was
deliberately not touched (other agents in flight).

**Method for "no caller":** every literal `/api/...` string in `static/js/`,
`static/*.html`, `extensions/` and `browser_tests/` was extracted and matched
against the 205 declared routes with the path parameters expanded to regexes,
then each survivor was re-grepped by hand for concatenated spellings
(`"/api/turns/" + t.id`). A route below is claimed callerless only when both
passes returned zero.

---

## Part 1 — findings. FLAGGED, NOT FIXED.

### 1. `relationship_events` is missing from ALL THREE of `web/app.py`'s hand-maintained table lists

`web/app.py` keeps three separate enumerations of the chat's durable tables,
each maintained by hand. `relationship_events` — the ledger that answers *why*
a character's stance is where it is (`memory.relationship_history`,
`mind/memory.py:4627`) — is absent from every one of them, and it is the ONLY
table with a `chat_id` column that is absent from any of them.

**a) `turn_branch` never copies it.** `web/app.py:4972-4980` builds
`world_tables` from exactly eight keys:

```python
world_tables = json.loads(json.dumps({
    k: (blob.get(k) or [])
    for k in ("world_entities", "world_placements", "world_conditions",
              "scheduled_events", "world_events", "room_registry",
              "fiction_worlds", "fiction_locations")
}))
```

`persist/checkpoints.py:377` `insert_world_tables` *does* know how to write
`relationship_events` (it inserts them at `checkpoints.py:435-445`), and
`persist/chat_archive.py:915` lists nine tables including it. The branch path
lists eight. A branched story therefore starts with an empty
`relationship_events` table: every "why" behind every stance in the source
story is gone, silently, while the scalar graph in `chat_chars.state` comes
across intact — so the relationship panel reads normal and the history is
blank.

**b) `_remap_cp_blob` never remaps it.** `web/app.py:849-1041` remaps
`memories`, `memory_summaries`, `world`, `lore`, `lorebooks`,
`lorebook_links`, `chars`, `char_frames`, `frames`, `chat_personas`,
`world_entities`, `world_events`, `room_registry`, and then eight tables under
`world_id_remap` (`web/app.py:1022-1024`). `relationship_events` appears
nowhere, and its rows carry an integer `char_id` and an integer `frame_id`
(`core/db.py:657-659`).

`persist/chat_archive.py:938-945` states the rule for the live table and
enforces it:

> A stance's history follows the character it belongs to. An id that does not
> remap is DROPPED rather than carried across: the same integer means a
> different person in the new chat, and reattaching a grudge to whoever
> inherited the number is worse than losing it.

The checkpoint blobs imported alongside that live table get none of it. So a
portable import lands with correct live rows and with every checkpoint holding
the SOURCE database's `char_id`s — and the first rollback in the imported story
(`checkpoints.py:434`, `DELETE FROM relationship_events WHERE chat_id=?`, then
re-INSERT from the blob) replaces the correct rows with the wrong ones. That is
exactly the outcome `chat_archive` calls "worse than losing it", reached by the
one path nobody wrote a rule for. The `frame_id` half is worse in kind: it is
an FK to `frames(id)`, so after a branch the restored row points at the SOURCE
chat's frame row — valid to SQLite, wrong to every reader.

**c) `chat_del` does not list it.** `web/app.py:3015-3050` enumerates twenty
tables by name. `relationship_events` is not among them. This one is currently
benign — `PRAGMA foreign_keys=ON` (`core/db.py:1481`) plus
`ON DELETE CASCADE` on the column means the final `DELETE FROM chats` sweeps
it — but it is the third independent omission of the same table from the same
file, which is what makes the pattern the finding rather than the instance.

Why it matters: this is the exact shape `docs/guides/DATABASE.md`'s
schema-change checklist exists to catch (step 6, "Branch/clone ID remapping in
`web/app.py` when IDs are embedded"). The table has embedded ids, was added
with checkpoint and archive coverage, and the branch/remap step was skipped —
and nothing anywhere compares the four lists.

### 2. The consent dialog discloses no capabilities, and the engine's own capability list is dead

`AGENTS.md` § extensions row: "Manifest `capabilities` are DISCLOSURE for the
consent dialog, never enforcement." `Design.md:258`: "manifest capabilities are
disclosure for the consent dialog, not a sandbox."
`docs/guides/EXTENSIONS.md:78-80`: "Every entry is parsed, **displayed to the
host on the consent dialog**, and used to compute the trust class."

The consent dialog is `static/js/settings.js:3428-3430`:

```js
if (!enabled && !await confirmModal(
      `Enable ${ext.name || ext.id}?\n\n${extensionTrustNote(ext)}`,
      { confirmLabel: "Enable" })) return;
```

`extensionTrustNote` (`settings.js:3326-3336`) returns one of three fixed
sentences keyed on `ext.trust`. The capability summary
(`extensionCapabilitySummary`, `settings.js:3338-3352`) is computed at
`settings.js:3422` and rendered into the extension's ROW — not into the
dialog. So the one moment the field exists for shows none of it.

And the summary itself is a second, hand-written list that has drifted from
the engine's. `extension_runtime/__init__.py:61-67` declares the authority:

```python
KNOWN_CAPABILITIES = (
    "stages", "chat_state", "char_state", "characters", "routing", "python",
    "ui", "system", "routes", "commit_domains",
)
```

`extensionCapabilitySummary` names six of those ten: `stages`, `chat_state`,
`characters`, `routing`, `system`, `ui`. The four it never mentions are
`python` (runs code in the engine's process), `commit_domains` (runs inside the
turn's transaction and, with `on_error="fail"`, can roll the turn back —
`api.py:1489-1500`), `routes` (serves HTTP under the host session), and
`char_state` (writes into a mind's `chat_chars.state`). Those are the four a
host would most want named.

`KNOWN_CAPABILITIES` is read by NOTHING — grep over the whole tree returns the
definition and no other line. It is a comment wearing a tuple: the engine
cannot check its own list against the manifest, against the loader, or against
the browser's copy of it. This is finding 1/9's shape from `AUDIT_DIRECTOR.md`
one layer up — a registry frozen against the extension seam — except here the
registry is not merely frozen, it is unread.

### 3. Safe mode, plus any enable/disable/remove, permanently wipes the host's enabled set

`enabled_ids()` (`extension_runtime/__init__.py:316-332`) returns `[]` when
`safe_mode()` is on, and otherwise filters the stored set down to what is
currently *installed and loadable*. `_write_enabled` (`__init__.py:337-341`)
stores exactly what it is handed. `enable_extension` (`:346-356`) and
`disable_extension` (`:358-362`) both compute their new set FROM `enabled_ids()`:

```python
_write_enabled(enabled_ids() + [ext_id])           # enable
_write_enabled([item for item in enabled_ids() if item != ext_id])  # disable
```

Two consequences, both silent:

* **In safe mode, every toggle is a wipe.** `SONDER_EXTENSIONS_SAFE=1` is
  documented (`docs/guides/EXTENSIONS.md:32-35`) as "the escape hatch for an
  extension that breaks the app badly enough that you cannot reach the menu to
  disable it" — i.e. the intended workflow is *boot safe, open the menu, turn
  the culprit off*. Doing that calls `disable_extension`, which writes
  `[] minus culprit` = `[]`, deleting every OTHER extension's enablement
  forever. `remove_extension` (`:2158`) calls `disable_extension`
  unconditionally at `:2173`, so removing one extension in safe mode does the
  same. The UI actively promises the opposite (`static/js/settings.js:3400-3405`:
  "Restart without the safe-mode flag to load them again").
* **A broken manifest loses its enablement on the next toggle of anything.** An
  extension whose `manifest.json` stops parsing is in `load_errors()` and not
  in `installed_extensions()`, so `enabled_ids()` drops it; the next
  enable/disable of an unrelated extension persists that drop. Fix the
  manifest and the extension is off, with nothing saying why.

Both contradict the rule this module states for itself in
`keep_orphan_lane_rows` (`__init__.py:1372-1389`): "removal takes the code,
never the host's choices". The enable set is the host's choice; a filtered READ
is being used as a WRITE.

### 4. `PUT /api/exemplars` has no caller anywhere — the narrator's STYLE EXEMPLARS clause still always sees `[]`

`web/app.py:1342-1370`. Its own docstring is the diagnosis:

> THE SLOT EXISTED AND HAD NO DOOR. `agents/narration.py` has always read
> `settings.exemplars`, and the narrator prompt has always carried a STYLE
> EXEMPLARS clause telling the model to study them for voice, rhythm and
> restraint -- but nothing anywhere could write the setting, so the clause
> referred to an empty list on every install that has ever run.

The reader is still live and unconditional — `agents/narration.py:990` and
`agents/narration.py:1141` both do
`json.loads(get_setting("exemplars") or "[]")`. `bootstrap` publishes the value
(`web/app.py:1189`). The route validates, bounds and stores it. And the string
`exemplars` appears **zero** times in `static/`, `extensions/` and
`browser_tests/`. The door was fitted to the server and never to the house: the
STYLE EXEMPLARS clause refers to an empty list on every install that has ever
run, exactly as before, and the route that was supposed to end that is
unreachable from the product.

### 5. `_apply_world_id_remap` is dead, and it is the third copy of a rule kept in sync by hand

`web/app.py:772-802`. Zero callers — grep over the whole tree returns only the
`def`. It is a near-duplicate of two live blocks:

* `_remap_cp_blob`'s tail, `web/app.py:1021-1040`
* `turn_branch`'s world pass, `web/app.py:4946-4985`

All three walk the same eight-table tuple (`web/app.py:790-791`, `1022-1023`,
`4974-4976`), all three call `_deep_remap_ids` + `_remap_row_json_fields`, and
all three also deep-remap `blob["world"]` with slightly different handling of
JSON-in-a-string values (`:797-800` vs `:1030-1040` vs `:4947-4960`). The dead
one is the only version that does NOT try `world_id_remap.get(v, v)` on a
non-JSON string, which the branch version does at `:4956`. So the three copies
already disagree, and the one that disagrees is the one nothing exercises. Same
class as `AUDIT_DIRECTOR.md` finding 10.

### 6. An extension that FAILED to register still colours every Director and narrator payload

`_deregister(ext_id, error=...)` keeps the extension's record alive
(`extension_runtime/__init__.py:560` and `:582`:
`_registered[ext_id] = _Registration(ext_id, error=error)`), and
`_activate_one` installs `_apis[ext_id]` at `:594` *before* it imports the
entry at `:597`. The hook dispatchers all iterate `record.<hook list>`, which
is empty for a failed record — so hooks are correctly dead. But the two
DECLARATIVE seams iterate the registry keys instead:

```python
with _lock:
    ids = sorted(_registered)          # __init__.py:925 and :959
...
    block = api.narration_context(chat_id).get()   # :938
    record = api.director_context(chat_id).get(phase)  # :972
```

So an extension whose `register(api)` raised — shown in the menu as "failed to
load", with every hook stripped and its stages unregistered — keeps injecting
its stored `NarrationBlock` and `DirectorBlock` text into
`payload["extension_context"]` on every beat, of every phase, forever. The
module docstring's promise (`__init__.py:16-18`, "a malformed extension lands
in `load_errors()` and its siblings load normally"; `web/app.py:1200-1252`, "a
malformed extension must cost the host its own row in the panel, never the
application's entry point") holds for the code and not for the standing blocks.
A campaign rule from a dead extension is the worst version of this: it shapes
what the Director *believes happened*, which propagates into state, perception
and memory (`api.py:1660-1667` says exactly that).

### 7. `PRESERVED_SETTING_KEYS` omits four reader-facing dials, so a branch and a reroll silently revert them

`turn_branch` overlays the source chat's CURRENT settings onto the
branch-point world at `web/app.py:4922-4926`, for the stated reason
(`:4916-4921`): "Turn NPC autonomy up at turn 60, branch from turn 20, and the
branch opened with the old dial because the change postdates the checkpoint."
The list it walks is `persist/checkpoints.py:487-510`, four keys:
`dialogue_config`, `background_config`, `style_guide`, `story_language`.

These `world` keys are written by host-authoring routes in `web/app.py` and are
NOT on that list:

| key | route | writer |
|---|---|---|
| `living_world` | `PUT /api/chats/{cid}/living_world` (`app.py:4176`) | `world/living_world.py:196` |
| `player_authority` | `PUT /api/chats/{cid}/player_authority` (`app.py:4267`) | `story/scene.py:1709` |
| `survival` / `survival_shows_npcs` | `PUT /api/chats/{cid}/survival` (`app.py:3711`) | `world/survival.py:54` |
| `presence_id_namespace` | minted by `player_view` | `web/story_view.py:412` |

`player_authority` is the one that matters. `Design.md` § Hard mode makes it the
setting a story's whole premise can rest on, and the route refuses rather than
normalizes an unreadable value for exactly that reason (`app.py:4267-4276`:
"the cost is the player silently keeping or losing authorship of the world").
A host who switches a live story to `actor_only` at turn 40 and then rerolls
turn 40 gets `world_author` back with no notice — and a branch taken from an
earlier turn opens under whatever mode was in force then. The same argument the
overlay was written for applies verbatim to all four, and the list is
maintained by hand in a different file from every one of its members.

### 8. `story_view` / `player_view` pair the LATEST TURN'S frame with the PRESENT frame's world

`web/story_view.py:80-91` opens by naming the hazard:

> `frame_id=None` means "whatever frame the story is actually on", which is
> what a caller outside the pipeline wants: `db.active_frame_id` is a
> ContextVar set for the duration of a turn, so a route reading it gets the
> default and not the answer.

It then fixes it for `turns` only. Every world read that follows goes through
`wget`, which routes a frame-scoped key by that same unset contextvar
(`core/db.py:69-80`), and `scene`, `known` and `simulation_clock` are all in
`FRAME_SCOPED_WORLD_KEYS` (`core/db.py:24-26`):

* `story_view.py:189` — `scene = get_scene(chat_id, chat)`
* `story_view.py:630` — `scene = get_scene(chat_id)`
* `story_view.py:549` and `:651` — `wget(chat_id, "known", {})`
* `story_view.py:196` and `:637` — `simulation_clock(chat_id)`

Meanwhile `_frame_of(turn)` (`:94-101`) reports the frame of the latest turn
*across every frame*. So for any multi-frame story whose latest turn is not in
the present frame, `story_view` reports frame 5's label beside the present
frame's rooms, positions and clock, and `player_view` filters a viewer against
the present frame's recognition ledger while dating everything from frame 5's
turn. Both are versioned reads sold to third parties (`STORY_VIEW_SCHEMA = 3`,
`:60`) as "canonical story state" and "a security boundary", and both are
answering about a world nobody is standing in.

The same read pattern runs through `web/app.py`'s authoring routes
(`chat_positions_get:3789`, `chat_vitals_get:3762`, `attire_get:4055`,
`attire_put:4059`, `chat_char_position_put:3841`, `world_get:4020`,
`world_put:4023`, `survival_put`'s seeding at `:3739`). There it is at least
defensible as "an author edits the present frame" — but none of those routes
accepts a `frame_id`, so with a multi-frame story there is no spelling of "move
this character in the era we are actually playing".

### 9. Nine more routes with no caller anywhere in the repository

Verified zero, by the method at the head of this document:

| route | `web/app.py` |
|---|---|
| `GET` / `PUT /api/auto_promote` | `:3373-3380` |
| `GET /api/language-packs` | `:2845` |
| `GET /api/language-packs/{language_id}/ui` | `:2862` |
| `POST /api/chats/{cid}/lorebook` (`bind_lore`) | `:2989` |
| `DELETE /api/chats/{cid}/lorebook` (`detach_lore`) | `:3005` |
| `DELETE /api/chats/{cid}/personas/{pid}` (`chat_del_persona`) | `:3451` |
| `POST /api/chats/{cid}/turns/{idx}/player_input` | `:3465` |
| `GET /api/chats/{cid}/story_view` | `:4222` |
| `GET /api/chats/{cid}/player_view` | `:4237` |
| `GET /api/chats/{cid}/viewers` | `:4247` |
| `GET /api/chats/{cid}/ambience/pins` | `:5744` |
| `GET /api/ambience/library` | `:5711` |
| `POST /api/auth/logout` | `web/auth_routes.py:169` |

Three of these are worth calling out individually rather than as a list.

**`PUT /api/auto_promote` is the only way to change the setting**, and nothing
can call it: `bootstrap` publishes `auto_promote` (`app.py:1224`) and no
JavaScript file mentions the string. Autonomous background-to-cast promotion is
on by default (`get_setting("auto_promote") != "0"`) and can only be switched
off by editing the database — the same "a switch a host cannot find is a switch
that becomes folklore" the `affect_habituation` route was added to end
(`app.py:1213-1218`).

**`story_view` / `player_view` / `viewers` are called by nobody, including the
extensions.** `story_view_get`'s docstring (`app.py:4222-4227`) says they are
"Served to the host UI as well as to extensions because it is the same question
either asks — and because a surface only extensions can reach is one nothing in
this repository exercises." Both halves are false: `static/js/` never fetches
them, and `extensions/campaign-demo/` reaches the reads through the Python
facade (`api.story_view` → `web/story_view.py` directly, `api.py:1971`,
`:2007`, `:2015`), not over HTTP. Nothing in this repository exercises the HTTP
surface at all.

**`POST /api/auth/logout` exists and nothing signs out.** The host cookie is
`max_age = HOST_SESSION_TTL` = 30 days, `SameSite=Strict`
(`auth_routes.py:21`, `:54-61`). The route deletes the session row and the
cookie (`:169-174`). No page offers it.

### 10. `load_errors()` rows carry `dir`; the UI reads `err.id`, so a broken extension is never named

`_scan` builds error rows as `{"dir": directory.name, "error": str(exc)}`
(`extension_runtime/__init__.py:280-281` and `:285-286`), and
`_bootstrap_extensions` builds `{"dir": "", "error": str(exc)}`
(`web/app.py:1152`). No producer ever writes an `id` key. The consumer is
`static/js/settings.js:3409`:

```js
el("b", {}, `${err.id || "an extension"} failed to load`),
```

So the panel always says "an extension failed to load", with the message but
never the directory — while the loader has had the directory name in hand the
whole time. `docs/guides/EXTENSIONS.md:37-38` promises "a malformed extension
lands in `load_errors()` **with a reason**"; the reason survives, the identity
does not. Two representations of one record, and the field name is the drift.

### 11. Eighteen unused imports in `web/app.py`, and three duplicated ones

AST-checked (name imported, never referenced outside its own import
statement), and none is a facade re-export that tests monkeypatch — grep for
`app.<name>` over `tests/` and `browser_tests/` returns zero for every one:

* `web/app.py:19` (`llm.providers`): `chat_complete`, `chat_complete_async`,
  `token_sink`, `cancel_event`, `resolve_role`, `agent_models`, `Aborted`
* `web/app.py:28` (`core.pipeline_context`): `PipelineContext`, `ChatData`,
  `TurnData`
* `web/app.py:74` (`persist.commit`): `commit_all`, `_known_name_roster`
* `web/app.py:77` (`llm.prompts`): `get_prompt`, `nsfw_enabled`
* `web/app.py:88` (`mind.memory`): `add_memories_batch`, `dump_chat_memories`,
  `dump_memory_summaries`, `dump_lorebook_links`

`commit_all` and the four `llm.providers` call seams are the interesting ones:
they are the shape of a facade that used to exist. The route layer no longer
calls the pipeline or a provider directly at all.

Separately, `web/app.py:1927-1932` re-imports `restore_lorebook_links`,
`get_lorebook_links` and `LOREBOOK_LINK_TYPES` from `mind.memory`, all three of
which are already imported at `:88-97`.

### 12. A local-directory install skips every ceiling `_audit_tree` exists to apply

`_audit_tree` (`extension_runtime/__init__.py:1849-1855`) states its own rule:

> A clone is not extracted, so `_safe_extract` never sees it -- and a git
> repository can hold symlinks and gigabytes just as happily as a zip can.
> **The rules that govern what may be installed should not depend on how it
> travelled.**

`install_extension` calls it for `git` (`:1930`) and `_safe_extract` covers
`zip` (`:1953`). The `local` branch (`:1959-1966`) calls neither:

```python
origin = Path(source).expanduser()
if not origin.is_dir():
    raise ExtensionError(f"not a directory: {source}")
shutil.copytree(origin, staged, dirs_exist_ok=True,
                symlinks=False, ignore=shutil.ignore_patterns(
                    "__pycache__", "*.pyc", ".git"))
```

So a folder install is bound by none of `MAX_ARCHIVE_MEMBERS`,
`MAX_EXTRACTED_BYTES`, or the symlink refusal — and `symlinks=False` means
copytree DEREFERENCES symlinks rather than refusing them, so a link in the
source folder is copied through as its target's contents. The install path is
host-initiated, so this is a robustness gap rather than a privilege one; it is
listed because the rule is written down two hundred lines above the code that
does not follow it. `update_extension` correctly audits (`:2098`), and it can
only ever take a git source.

### 13. Two dispatch helpers take a parameter they never read

* `apply_plan_splices(plan, chat_id=None)` — `extension_runtime/__init__.py:686`.
  `chat_id` appears in the signature and nowhere in the 45-line body. The
  caller passes it (`agents/runtime.py:213`). It cannot be used, by the
  docstring's own first load-bearing property ("Pure function of durable
  settings + manifests" — a per-chat splice would break
  `resume_key_for_turn`), so the parameter reads as an invitation to break
  resume.
* `notify_step_saved(ctx, key, content)` — `extension_runtime/__init__.py:739`.
  `ctx` is unreferenced in the body, and the docstring says so deliberately
  ("the observer gets the saved key and content, never the context"). Keeping
  the parameter is the one thing that makes the guarantee look optional.

### 14. `_scan`'s staging comment describes a naming convention nothing uses

`extension_runtime/__init__.py:275-278`:

```python
# `.staging-*` and friends: a half-written download in flight is not an
# installed extension, and reporting it as a broken one is noise.
if directory.name.startswith("."):
    continue
```

`install_extension` and `update_extension` stage through
`tempfile.TemporaryDirectory(dir=root)` (`:1917`, `:2093`), which produces
`tmpXXXXXXXX`, not `.staging-*`. Nothing in the tree ever creates a
dot-prefixed directory under `extensions/`. What actually keeps a staging
directory out of the scan is the `manifest.json` check on the next line
(`:279-280`) — the staged bundle's manifest sits one level deeper. The guard
the comment credits has never fired; the guard that works is undocumented.

### 15. `apply_plan_splices` silently drops any `ext:` anchor, undocumented

`extension_runtime/__init__.py:722-726`:

```python
# `character:<id>` is the runtime's reserved dynamic namespace and
# is planned as a parallel group; splicing into the middle of one
# would silently serialize it.
if core.startswith("character:") or core.startswith("ext:"):
    continue
```

The comment justifies `character:` and says nothing about `ext:`.
`api.add_stage`'s docstring (`api.py:1436-1442`) documents only the
`after:`/`before:` shape and validates only that. So an extension that anchors
its second stage after its first — `anchor="after:ext:my-ext:pulse"`, the
obvious way to order two of your own stages — is accepted at registration,
appears in `registered_stages()`, and is never planned on any turn. No warning,
no load error, no row anywhere saying it did not run.

### 16. `GET /api/extensions/{eid}/state` answers only half an extension's per-story state

`web/app.py:1651-1656` returns `wget(chat_id, f"ext:{eid}")` and nothing else.
Since the frame-scoped home was added (`api.frame_state` → `extf:<id>`,
`api.py:2115-2141`, `core/db.py:58`), an extension has two per-story homes and
the route knows about one. `docs/guides/EXTENSIONS.md:1401` bills it as "that
extension's per-story state", and `Sonder.extState(extId)`
(`static/js/extensions.js:394`) is the browser's only way to read it — so an
extension whose mission state lives in `frame_state` (which is what the
docstring recommends for exactly that: "a mission advanced in one era was
advanced in every era") gets `null` from its own panel. The route also does not
check that the chat exists, and does not require the extension to be enabled or
even installed beyond the id regex (`_extension_id`, `app.py:1567-1570`).

### 17. `asset_path` serves any file from an installed-but-DISABLED extension

`extension_runtime/asset_path` (`__init__.py:1420-1441`) checks installed,
relative, non-traversing, contained and is-a-file. It does not check
`is_enabled`. Its two sibling servers do (`extension_script:1531`,
`extension_styles:1547`, both `if ... not is_enabled(ext.id): return ""`), and
both also short-circuit under safe mode. So `GET /api/extensions/{eid}/asset/
extension.py` returns the Python source of an extension the host has switched
off, and safe mode does not stop it. Host-session-gated, so this is a
consistency gap rather than an exposure; it is listed because the enable check
is present on the two neighbouring routes and absent here, which is how a
future reader concludes it is not needed.

### 18. `edit_prose` writes two statements outside a transaction, unlike both of its siblings

`web/app.py:5083-5088`:

```python
qi("UPDATE variants SET active=0 WHERE step_id=?", (step["id"],))
qi(
    "INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
    (step["id"], json.dumps(content, ensure_ascii=False), time.time()),
)
```

`step_edit` (`:5343-5347`) and `turn_narration_select` (`:5155-5157`) do the
identical pair inside `with transaction():`. A crash between the two here
leaves the narrator step with ZERO active variants, which
`AGENTS.md` § Persistence boundaries names as an invariant ("exactly one active
variant should exist per materialized step"). `edit_prose` also takes neither
`_require_latest` (deliberate, and argued at `:5072-5080`) nor
`_require_chat_idle` (not argued anywhere) — so a prose edit issued during a
running reroll of the same turn races the pipeline's own variant write.

### 19. The presence-id namespace is a secret that rides the portable archive and `GET /api/chats/{cid}/world`

`web/story_view.py:400-412` states the property the namespace exists for:

> a derivative computed only from canonical values is invertible by
> enumeration no matter how it is hashed, and "cannot confirm a guessed
> identity" is the property the id is for.

It is stored as a plain `world` row (`:412`, `:415-428`), explicitly so that it
inherits checkpoints, archives and branches with no carriage code. That is
correct for continuity and it also means the secret is exported: it is in
`chat_archive`'s `export["world"]` (`persist/chat_archive.py:229`), in every
checkpoint blob (`checkpoints.snapshot_state`), and returned in full by
`GET /api/chats/{cid}/world` (`web/app.py:4019-4021`). Anyone holding a shared
archive of the story can recompute `_viewer_presence_id(namespace, viewer, ref)`
for every viewer/ref pair and de-anonymise every `body:` id in any
`player_view` of it. Narrow — both readers are host-only and an archive is
already a full disclosure of the story — but the docstring claims the id is
"invertible by nobody", and against a shared archive it is invertible by
anybody.

### 20. `story_view.viewers()` keys the player on the denormalised `personas.name`

`web/story_view.py:238-242`:

```python
persona = q("SELECT p.id, p.name FROM personas p JOIN chats c "
            "ON c.persona_id=p.id WHERE c.id=?", (chat_id,), one=True)
if persona:
    out.append({"id": "player", "name": persona["name"], "kind": "player"})
```

`web/app.py:5432-5437` (`_backdrop_player`) says why that is the wrong column:

> The same `persona_of`/`persona_name` pair used by `commit.py` and the cast
> routes -- deliberately not the denormalised `personas.name` column, which
> diverges from the sheet.

That name is then used as the join key into the identity ledger
(`story_view.py:549`, `:651`: `wget(chat_id, "known", {}).get(name)`), which is
keyed by the SHEET's identity name. Where the two diverge the player's `knows`
and `people` come back empty and, under "absent means absent", read as "this
person recognises nobody" rather than as a lookup miss.

Second half of the same defect: when the chat has no persona attached, the
query returns nothing and `viewers()` emits no `"player"` entry at all, so
`player_view(cid, "player")` raises `ValueError` → HTTP 404. Every other reader
in the engine falls back to `persona_of`'s `"The Stranger"`
(`story/scene.py:327-335`), which IS the name the scene is keyed by — so the
one read sold as "what one person in the story may be shown" is the one that
cannot see the default player. `_cast` (`:119-137`) does the right thing for
characters, reading `character_name_from_text(sheet)`.

### 21. `GET /api/extensions/updates` has no wall-clock bound

`check_updates()` (`extension_runtime/__init__.py:2059-2062`) loops
`check_update` over every installed extension, each of which runs one
`git ls-remote` with `GIT_TIMEOUT_SECONDS = 120` (`:1721`, `:1802-1806`).
Ten installed extensions on an unreachable network is a twenty-minute
request holding a threadpool worker. The docstring's promise — "One
`ls-remote` each, no download, which is what makes an update CHECK cheap enough
to run for every installed extension at once" (`:1837-1840`) — is about
bandwidth and is silent on latency, which is what actually bounds a route.

### 22. Four routes 500 on a missing body key instead of 400

`bind_lore` `body["lorebook_id"]` (`web/app.py:2991`), `chat_add_persona`
`body["persona_id"]` (`:3416`), `create_guest_invite` `body["persona_id"]`
(`:3579`), `submit_extra_player_input` `body["persona_id"]` (`:3476`). Every
neighbouring route uses `body.get(...)` and raises `HTTPException(400, ...)` —
`chat_add_char` at `:3282-3284` is the model. Two of the four are on the
callerless list (finding 9), which is presumably why nobody hit them.

---

## Part 2 — what the code actually does, checked against the documents

Verdicts: **RIGHT** / **STALE** / **LOST**, per `AUDIT_DIRECTOR.md`.

### `web/app.py` — application assembly, middleware, streaming

Two ASGI layers, both written here rather than taken from Starlette.
`SelectiveGZipMiddleware` (`:227-346`) compresses on the response's CONTENT
TYPE, excluding `application/x-ndjson` and `text/event-stream`, and holds the
`http.response.start` message until the first body chunk so the size is known;
it uses `zlib` directly with `Z_SYNC_FLUSH` per chunk. The comment explains
both reasons (Starlette's `GZipResponder` buffers, stalling the turn stream;
and its `.send_with_gzip` internal vanished on Starlette 0.50 while
`requirements.txt`'s range still resolves there). `access_control` (`:389-409`)
is added AFTER the gzip middleware and therefore runs OUTSIDE it — correct:
a 401 is produced before any compression decision. Deny-by-default on `/api/*`,
with `PUBLIC_API_PATHS` and `GUEST_ALLOWED_API_PATHS` as exact-match frozensets
owned by `web/auth_routes.py`.

`_stream` (`:459-547`) runs the pipeline generator on one dedicated thread
inside one `contextvars.copy_context()`, relaying through a queue, because
Starlette's `iterate_in_threadpool` copies a fresh context per `next()` and
would lose `active_frame_id`/`cancel_event` after the first yield. The
consumer batches everything already queued into one yield.

**Docs: RIGHT.** `docs/guides/PIPELINE.md` § Streaming describes the event
vocabulary (`step_start`/`token`/`step`/`done`/`aborted`) and this layer emits
it unchanged; `CLAUDE.md`'s "`web/app.py` is an orchestration seam" is exactly
what these two classes are.

### `web/app.py` — concurrency gates

Four guards, and the distinction between them is real and correct:
`_require_chat_idle` (`:415-427`, whole-chat, for anything not frame-local),
`_require_frame_idle` (`:429-437`, fresh turn creation only),
`_require_latest` (`:583-621`, recompute: latest-of-its-own-frame AND no other
frame past this play-order point), `_require_turn_resolved` (`:623-647`).
`_begin_pipeline_or_409` (`:439-452`) is honest that the earlier checks are
advisory and `begin_pipeline`'s atomic register is the actual race closer.
`turn_new` (`:4576-4643`) claims the pipeline slot BEFORE inserting the turn
row, serialises the checkpoint snapshot OUTSIDE the write transaction, and
re-takes it under the lock only if `db.data_version()` moved.

**Docs: RIGHT.** No maintained doc describes these in detail; the code's own
comments are the specification and they are internally consistent. The one gap
is finding 18 (`edit_prose` takes no idle guard while `edit_input` at `:5044`
does, for a reason that applies equally).

### `web/app.py` — branch / clone / ID remapping

`turn_branch` (`:4644-5039`) is one transaction that clones frames (two passes
for the self-referential `parent_frame_id`), `chat_chars`, `chat_char_frames`,
turns/steps/variants/events, memories and summaries from the branch-point
checkpoint, the lorebook tree (two passes for `parent_id`), links only where
both endpoints exist, the world KV with frame-key rescoping and world-id
remapping, the normalized world tables through `insert_world_tables`, the
multiplayer roster and queued inputs, every earlier checkpoint through
`_remap_cp_blob`, and a final checkpoint at `idx+1`.
`_branch_protected_identity_ids` (`:716-740`) keeps cast and player identity
strings out of the world-id remap, which is what stopped the "unspecified
location after branch" defect.

**Docs: RIGHT in shape, INCOMPLETE in coverage.** `AGENTS.md`'s routing row
("New persistent fields need: … branch/clone ID remapping in `web/app.py` if
applicable") and `docs/guides/DATABASE.md`'s checklist step 6 describe a
process this file is the endpoint of; `relationship_events` went through the
schema, read/commit, archive and checkpoint steps and never reached this one
(finding 1). Nothing in the code or the docs cross-checks the four lists
against each other, which is why the omission is invisible.

### `web/app.py` — routes

205 route declarations. Every one is under `/api/` except `/`, `/login` and
`/guest`, which is what makes the access-control middleware total. The backdrop
and ambience media routes are deliberately under `/api/` rather than a
`StaticFiles` mount, with the reason stated (`:5400-5410`, `:5626-5635`): a
mount would put an enumerable dump of every room in every story outside the
middleware. Signature parameters are hex-regex-validated before they reach a
filesystem path (`_BACKDROP_SIGNATURE`, `:5414`).

Configuration routes normalize rather than reject, with one deliberate
exception argued in place: `player_authority_put` (`:4267-4287`) refuses an
unreadable mode because "the cost is the player silently keeping or losing
authorship of the world". `dlg_put` (`:4108-4155`), `bg_cfg_put`
(`:4198-4218`), `living_world_put` (`:4176-4187`) and `style_guide_put`
(`:4085-4094`) all normalize. Ladders (`offscreen_life_levels`,
`player_authority.modes`, `living_world.approaches`) are served from the
engine's own tables rather than copied into the menu, with `built` marked by
the engine — the anti-drift discipline `AGENTS.md` asks for, applied.

**Docs: RIGHT**, with thirteen routes nothing calls (finding 9) and one
docstring that asserts callers it does not have (`story_view_get`, `:4222`).

### `web/auth_routes.py`

176 lines, and it does exactly what its module docstring claims: request
validation, response status, and cookie transport, with all state in
`guest_access`. `MAX_PASSWORD_LENGTH` bounds PBKDF2 CPU before the verify.
`auth_login` checks `login_retry_after()` before the hash, returns a real
countdown and a `Retry-After` header, distinguishes "no account exists" (409,
argued as leaking nothing since `/status` already says so) from a wrong
credential (401, deliberately generic), and clears the failure ledger on
success. `PUBLIC_API_PATHS` and `GUEST_ALLOWED_API_PATHS` are frozensets here
and consumed by `app.py`'s middleware — one definition, one reader.

**Docs: RIGHT.** `AGENTS.md`'s "Host authentication and guest access" row points
here and to `guest_access.py`, and the ownership split matches. The only gap is
that `POST /api/auth/logout` has no caller (finding 9).

### `web/guest_access.py`

Host password as salted PBKDF2-SHA256 at 200k iterations; every session token
and join code stored only as SHA-256. `create_host_account` wraps
existence-check, username, salt, hash and the first session in one
`BEGIN IMMEDIATE`, closing both the crash-between-writes hole and the
two-setup-request race. `verify_host_login` compares UTF-8 BYTES rather than
`str` through `compare_digest`, because the `str` overload is ASCII-only and a
non-ASCII username would have 500'd every login forever.

`redeem_code` is the piece worth checking closely, and it is right: the SELECT
is a pre-check, the `redeemed_at IS NULL` predicate on the UPDATE is the guard,
and because `qi` returns `lastrowid` rather than a row count the winner is
confirmed by reading `token_hash` back. Two separate sliding windows (join,
login), the login one counting FAILURES only and cleared by a success.
`verify_guest_token` re-joins `chat_personas … status='active'`, so a stale or
hand-edited row still fails closed independently of the
`revoke_persona_grants` lifecycle hook.

**Docs: RIGHT.** The module docstring is a complete and accurate statement of
the model; `docs/guides/DATABASE.md`'s housekeeping note ("`guest_grants` /
`host_sessions` — see `web/guest_access.py` and `web/auth_routes.py`") points
at the right owners. One unpoliced edge: expired `host_sessions` rows are never
pruned — `verify_host_session` filters on `expires > ?` so they are inert, but
they accumulate for the life of the install.

### `web/story_view.py`

Two reads with a genuinely different contract, and the module argues the
difference before it codes it. `story_view` is objective and versioned;
`player_view` is built ONLY from what the engine already delivered (the
perception step's own `views` / `observations` / `company` for that viewer id,
the viewer's own memory rows, their own `relationships`, the identity ledger's
`known` list) and re-decides nothing. `_delivered` prefers
`perception_outcome` over `perception_act` because the earlier one is a
mid-beat state a later stage may have corrected. `_step_content` deliberately
does NOT use `agents.storage.active_content`, to keep the agent runtime out of
a panel refresh's import graph.

The `people` roster (schema 2 → 3) is the sharpest part. Recognition is the
identity ledger's answer joined name-to-ENTRIES (so two bearers of one granted
name stay two people); observation is the composer's own per-beat delivered
record, and an unrecognised body gets the composer's label plus
`_viewer_presence_id(namespace, viewer_id, ref)` — a viewer-scoped,
story-salted SHA-1 of an IMMUTABLE identity ref, so a rename moves
`display_name` and never `id`, two viewers never share an id, and a disguised
acquaintance's known name and observed body deliberately do not join.
`_presence_ref` degrades correctly through name-collision to the name itself
(the honest ref for an unregistered background presence) to the composer's
opaque key.

**Docs: RIGHT.** Every checkable clause of `Design.md:258`'s long extensions
row about `player_view` — built from delivered material, omits rather than
defaults, `people` re-keyed onto immutable identity in schema 3, ids never
derived from names, disguise does not join, allowlisted `facts`/`fact_sources`
— was checked against this file and holds. `docs/design/DIRECTIVE_HARDENING_REPORT.md`
§1 is implemented as written. The frame-scoping defect (finding 8), the
`personas.name` key (finding 20) and the exported namespace secret (finding 19)
are gaps in the implementation, not in the description.

### `extension_runtime/__init__.py`

Discovery is lazy and per-item, exactly as the docstring claims: a module-level
cache filled by a function, `_load_manifest` raising `ExtensionError` for every
failure mode including bad JSON, and `_scan` catching per directory so one
broken extension costs itself. The manifest never names a module path — only a
FILE, resolved and containment-checked before execution (`_module_name` at
`:497`, `_import_entry` at `:507`), and the extension's directory is registered
as a PACKAGE rather than put on `sys.path`, with the argument for that written
out (`:518-528`: a sibling `db.py` would shadow the engine's).

The dispatch helpers are total where they claim to be and pointedly not where
they claim not to be: `run_commit_domains` (`:791-830`) re-raises a domain
registered `on_error="fail"` because "swallowing that here would make the
option a lie", and everything else logs and returns the safe value.
`dispatch_character_payload` / `dispatch_narration_payload` /
`dispatch_director_payload` all fingerprint the payload BEFORE the call, with a
worked explanation of why comparing the returned object to the passed one
returns an empty diff for the ordinary in-place mutation — the attribution
guarantee would otherwise be silently void.

Install is staged, validated and moved with `os.replace`. `_safe_extract`
checks paths, absolute names, symlink bits and the DECLARED size against
ceilings before a byte is written, then re-counts what actually landed rather
than trusting the central directory. Git sources are restricted to http(s) and
`file://`, never `--recurse-submodules`, `--`-terminated so a URL cannot be
read as a flag, and run under `GIT_TERMINAL_PROMPT=0`.

**Docs: RIGHT** on everything above; `Design.md:258` and
`docs/guides/EXTENSIONS.md` §§1-3, 9-10 were checked clause by clause against
this file. The four defects are findings 2, 3, 6 and 12 — and note that
`AUDIT_DIRECTOR.md` findings 1 and 9 (the frozen `_DELEGATED_CHANNELS`, and an
extension specialist's list channel silently replaced by `{}`) are now CLOSED:
`agents/director_scopes.py:343-357` rebuilds both `_DELEGATED_CHANNELS` and
`_LIST_DELEGATED` on every registration, `register_specialist` takes
`list_channels` (`:364-405`), and `api.add_director_specialist`'s docstring
states the requirement and the failure it prevents (`api.py:1539-1544`).

### `extension_runtime/api.py`

The facade is bound to one id and every durable thing an extension touches is
namespaced under it: `ext:<id>` (chat-global world), `extf:<id>` (per-frame
world, prefix in `db.FRAME_SCOPED_WORLD_PREFIXES`), `ext:<id>` in
`chat_chars.state`, `ext:<id>` in `settings`, and `ext:<id>:doc:<path>` rows
for the document store. The design argument is stated once and holds: those
tables are carried WHOLESALE by checkpoints, archives and branches with no
per-key knowledge, so an extension inherits rewind/export/clone without a line
in `DATABASE.md`'s checklist.

The write gate is real and consistently applied: `ExtState.set` and
`DocumentStore.put`/`delete`/`delete_prefix` raise outside a commit scope, the
`_now` forms are the named escape hatch, `CommitView` passes `gated=False`
because it runs inside the turn's transaction, and `NarrationBlock` /
`DirectorBlock` / `request_bind` are ungated with the reason (a host action has
no transaction to belong to). `_write_char_state` (`:812-828`) does a
read-modify-write through `story.scene.set_char_state` and warns in the
docstring against building a fresh dict.

`document_path` refuses traversal by CONSTRUCTION — a segment must START with
an alphanumeric, so `.` and `..` are unspellable — rather than by a denylist.
`_canonical_document` sizes and hashes the sorted-key/tight-separator form so
`verify` checks content rather than formatting. `list` and `verify` read the
RAW row and parse themselves, because they must survive the damaged rows they
exist to report. `_rows` escapes LIKE metacharacters and re-filters
segment-aware so `missions` never matches `missions2/1`.

`DirectorResult` hands over deep copies, carries no model handle, and the
`Correction` value type exists so a validator states a violation rather than
editing the beat — "the Director would have no idea its answer had been changed
underneath it". `provision_story` validates every argument BEFORE the archive is
touched and applies the whole bootstrap inside one transaction, over
`chat_archive`'s importer rather than a second scenario format.

**Docs: RIGHT.** `docs/guides/EXTENSIONS.md` and `Design.md:258` describe this
file accurately, including the refusals (`ChatAccess` has no way to post prose,
and says why; `add_model_lane` refuses a name that is a host role; a repository
that renames its own id is refused rather than updated into). The gaps found
are all on the OTHER side of the facade: the consent dialog (finding 2), the
enabled set (finding 3), the block seams surviving a failed register
(finding 6), and the two dead parameters (finding 13).

**What an extension can do that the docstrings say it cannot:** nothing found.
Every "cannot" checked resolves to a real refusal in code —
`api.add_director_specialist`'s channel namespacing
(`director_scopes.register_specialist`), `add_model_lane`'s host-role refusal
(`api.py:1785-1790`), `add_route`'s `/x/` namespacing (`app.py:1770-1786`),
`asset_path`'s resolved-path containment, `_import_entry`'s escape check.
**What the docstrings promise that the code does not deliver:** three, all
already listed — capability disclosure at consent (2), an extension's state
route covering both homes (16), and an anchor on another extension's stage
being accepted and then never planned (15).

### Cross-document verdicts

| document | verdict |
|---|---|
| `Design.md:258` "Third-party extensions — **Partial**" | **RIGHT** except one clause: "manifest capabilities are disclosure for the consent dialog" describes an intent the dialog does not implement (finding 2). Every other checkable clause — per-item discovery, trust class from what it can actually do, the five persistence homes, `extf:` frame state, model lanes, the Director/narration blocks and hooks, `on_director_result`'s one re-resolution, `provision_story`'s atomicity, the package import, schema-3 `player_view` — verified against source |
| `AGENTS.md` § "Extensions: the loader, the developer facade…" row | **RIGHT** — the three named load-bearing properties all hold: plan splices are a pure function of durable settings and manifests, every dispatch helper the core calls is total (with `run_commit_domains`'s documented `fail` exception), and the four `ext:<id>` homes inherit carriage without a schema change. "Manifest `capabilities` are DISCLOSURE … do not add a guard there and call it a boundary" is honoured in the code; the disclosure itself is missing at the point of consent |
| `AGENTS.md` § "Host authentication and guest access" row | **RIGHT** — ownership split between `auth_routes.py` and `guest_access.py` matches the code exactly |
| `AGENTS.md` § "Authoring edits to live positions (GM relocation)" row | **RIGHT** — `chat_char_position_put` (`app.py:3822`) writes only `scene.positions`, requires an idle chat, validates room ids against the scene, and queues no narrator beat, precisely as described |
| `docs/guides/DATABASE.md` schema-change checklist, step 6 | **RIGHT as a rule, UNENFORCED in fact** — `relationship_events` completed steps 1-5 and 8 and skipped 6 (finding 1) |
| `docs/guides/EXTENSIONS.md` §2 "Every entry is parsed, displayed to the host on the consent dialog" | **STALE** — the parse is real, the display is not (finding 2) |
| `docs/guides/EXTENSIONS.md` §1 safe mode / §5 enable set | **STALE** — "boots with nothing enabled" is true; the implied durability of the enabled set across a safe-mode session is not (finding 3) |
| `docs/guides/EXTENSIONS.md` §10 HTTP surface table | **RIGHT** — every route listed exists with the shape described |
| `docs/guides/PIPELINE.md` § Streaming | **RIGHT** — `_stream` emits the documented event vocabulary and the stable-context reasoning matches `db.py`'s `active_frame_id` note |

**Nothing was found built-and-quietly-lost** except one thing, and it is the
same class `AGENTS.md` § "Whether a mechanism actually fires" warns about:
`PUT /api/exemplars` exists, works, is bounded and validated, and cannot be
reached from the product (finding 4). The narrator's STYLE EXEMPLARS clause has
run against `[]` on every install that has ever run, before and after the fix.

---

## Unverified suspicions

Recorded because they are the right shape and I could not prove them without
running the server or the suite, both of which were out of bounds for this task.

* **`_stream`'s `thread.join()` on client disconnect.** `web/app.py:545` joins
  the pipeline thread in the generator's `finally`. If the browser drops the
  connection mid-turn, Starlette closes the generator and this blocks the ASGI
  worker until the pipeline finishes (potentially a minute or more). Probably
  intended — the alternative is orphaning the thread — but I could not confirm
  which worker it blocks or whether it can deadlock against
  `_require_chat_idle`.
* **`SelectiveGZipMiddleware` and a bodiless response.** `route`
  (`:295-329`) holds `http.response.start` until a body message arrives. Every
  ASGI response I know of sends at least one `http.response.body`, but a 304 or
  a `HEAD` handled by a future Starlette could in principle send none, and the
  held start message would never go out. Not reproduced.
* **`player_view` writes during a running pipeline.** `_presence_namespace`
  (`web/story_view.py:415-428`) `wset`s a `world` row from a GET route with no
  `_require_chat_idle`. `world_put` guards exactly this class of write
  (`app.py:4028-4031`). Whether a single-key upsert can actually interleave
  badly with a commit transaction I did not test.
* **`chat_get`'s import of `agents.active_content`.** `web/app.py:38` pulls the
  agent runtime into the import graph of every chat read, which
  `web/story_view.py:104-110` deliberately avoids for the same question. I did
  not measure whether it costs anything.
* **Extension load ordering as an unspecified contract.** `_registered` is a
  dict filled in `sorted(enabled_ids())` order and every dispatcher iterates
  `_registered.values()`, so hook order is alphabetical by extension id.
  `validate_director_result` documents its ordering (`:996-999`); the payload
  and narration dispatchers do not, and two extensions rewriting the same
  top-level key resolve last-writer-wins by id. Whether that is intended or
  merely what happened, I could not establish from the docs.
