# Alpha 9.8 UI Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge Sonder alpha 9.8 into `interface` and expose every new player- and author-facing capability through the replacement UI without adding backend architecture.

**Architecture:** Merge the released backend unchanged, preserve the classic frontend deletion, and port the new workflows through a shared replacement lived-location module. Existing New Story, Library, Story Tool, Settings, async-owner, localization, extension, and cache boundaries remain authoritative.

**Tech Stack:** Python 3.11-3.13, FastAPI, unbundled browser ES modules, CSS, Playwright/pytest, Make.

**Spec:** `docs/superpowers/specs/2026-08-22-alpha98-ui-parity-design.md`

## Global Constraints

- This is a UI and frontend integration task; add no backend endpoint, schema, persistence, simulation, prompt, or agent architecture.
- Merge alpha 9.8 at `2ac1d162fe69b23c9b7bdbcc6a8efa8e6231c979` intact.
- Preserve deletion of the classic authenticated host files and their obsolete browser test.
- Current alpha 9.8 backend behavior owns truth; the replacement browser never stores a second Charter registry.
- Supplied screenshots own covered composition; the Design Bible and candidate source govern extensions.
- Use the existing local SVG icons, semantic tokens, 3-5 px geometry, and 44 px compact touch targets.
- Every request is owner-bound and rejects stale results.
- Every new behavior starts with a focused failing contract or real-browser test.
- UI copy enters the generated English and Japanese catalogs; user/model data remains untranslated.
- Do not restore `window.S`, polling, synthetic legacy clicks, hidden duplicate controls, or classic assets.

---

### Task 1: Integrate the alpha 9.8 release boundary

**Files:**
- Merge: `origin/main` into `codex/ui-alpha98`
- Modify conflict resolution: `AGENTS.md`
- Modify conflict resolution: `web/app.py`
- Modify conflict resolution: `tests/test_living_world.py`
- Regenerate later: `docs/CODE_MAP.md`
- Regenerate later: `language_packs/en/ui.json`
- Regenerate later: `language_packs/ja/ui.json`
- Regenerate later: `language_packs/ja/translation_exceptions.json`
- Preserve deletion: `static/index.html`
- Preserve deletion: `static/js/app.js`
- Preserve deletion: `static/js/components.js`
- Preserve deletion: `static/js/editors.js`
- Preserve deletion: `static/js/lorebooks.js`
- Preserve deletion: `static/js/settings.js`
- Preserve deletion: `browser_tests/test_ui_smoke.py`
- Preserve deletion: `tests/test_frontend_global_namespace.py`

**Interfaces:**
- Consumes: released alpha 9.8 routes including `GET/PUT /api/chats/{id}/charters`, `GET /api/chats/{id}/charters/diagnostics`, `POST /api/chats/{id}/charters/generate`, and the extended Character start route.
- Produces: a conflict-free tree with replacement host security/cache/Library behavior and all alpha 9.8 backend tests available unchanged.

- [ ] **Step 1: Preview and start the merge**

Run:

```powershell
git merge-base HEAD origin/main
git merge --no-commit --no-ff origin/main
```

Expected: the merge stops only on the previously previewed maintained-file,
generated-file, and classic modify/delete conflicts.

- [ ] **Step 2: Preserve the classic frontend deletion**

Run:

```powershell
git rm static/index.html static/js/app.js static/js/components.js static/js/editors.js static/js/lorebooks.js static/js/settings.js browser_tests/test_ui_smoke.py tests/test_frontend_global_namespace.py
```

Expected: none of those classic files remains in the merge result.

- [ ] **Step 3: Resolve maintained backend integration without redesign**

In `web/app.py`, retain the replacement `index(request)` route, authentication,
`ui_cache_policy`, Library routers, and `cleanup_library_state`. Accept the
released alpha 9.8 imports/routes and make `chat_del` call the released
`delete_chat_data(cid)` followed by `cleanup_library_state("story", cid)`.
Do not change the signatures or semantics of released Charter routes.

In `AGENTS.md` and `tests/test_living_world.py`, retain both non-conflicting
interface and alpha 9.8 guidance/tests. Leave generated conflicts for Task 6.

- [ ] **Step 4: Verify the merge has no unresolved entries**

Run:

```powershell
git diff --name-only --diff-filter=U
git status --short
```

Expected: no `U` entries; only deliberate merged modifications and generated
files remain staged/modified.

- [ ] **Step 5: Run the affected released backend tests**

Run:

```powershell
py -3.13 -m pytest --basetemp=.tmp\pytest-alpha98-merge -q tests/test_story_quick_start_history.py tests/test_fable_town.py tests/test_host_settings_surface.py tests/test_living_world.py tests/test_library_projection.py
```

Expected: all selected tests pass without contract edits.

- [ ] **Step 6: Commit the release integration**

```powershell
git add AGENTS.md web/app.py tests/test_living_world.py persist/chat_delete.py
git add -u
git commit -m "merge: integrate alpha 9.8"
```

---

### Task 2: Build the shared lived-location frontend module

**Files:**
- Create: `static/js/ui-next/lived-location.js`
- Modify: `static/css/ui/components.css`
- Modify: `static/js/ui-next/release.js`
- Test: `browser_tests/test_ui_new_story.py`

**Interfaces:**
- Consumes: `services.apiClient`, `services.localizer`, existing replacement input/button/disclosure classes.
- Produces: `normalizeHistoryCharacters(characters)`, `buildLivedLocationRequest(value, options)`, `mountLivedLocationFields(options)`, and `generateLivedLocation(options)`.

- [ ] **Step 1: Write a failing browser contract for the shared payload**

Add a browser test that opens New Story, selects lived-location preparation,
chooses one saved Character as `resident`, enters guidance, and submits. Capture
the `POST /api/chats/41/charters/generate` JSON body and assert the literal
payload:

```python
assert generated == [{
    "enabled": True,
    "brief": "A crowded orbital customs station",
    "horizon_hours": 720,
    "active_tail_hours": 96,
    "generate_history": True,
    "character_histories": [{
        "char_id": 9,
        "mode": "resident",
        "brief": "Two years on customs duty",
    }],
}]
```

This catches a wrong route mode, wrong duration, missing identity mapping, or a
browser-only key leaking into the server payload.

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
py -3.13 -m pytest --basetemp=.tmp\pytest-lived-red -q browser_tests/test_ui_new_story.py -k lived_location_payload
```

Expected: FAIL because the replacement has no lived-location controls/request.

- [ ] **Step 3: Implement pure request normalization**

Create `lived-location.js` with pure exported builders. The core builder must
produce server data only:

```javascript
export function buildLivedLocationRequest(value = {}, options = {}) {
  if (!value.enabled) return null;
  const horizon = Math.max(0, Math.min(720, Number(value.horizonHours) || 0));
  const resolveId = options.resolveCharacterId || (() => null);
  const histories = (value.characterHistories || []).flatMap(row => {
    const charId = Number(resolveId(String(row.key)));
    return Number.isSafeInteger(charId) && charId > 0 ? [{
      char_id: charId,
      mode: row.mode || "auto",
      brief: String(row.brief || "").trim(),
    }] : [];
  });
  return {
    enabled: true,
    brief: String(value.brief || "").trim(),
    horizon_hours: horizon,
    active_tail_hours: Math.min(96, horizon),
    generate_history: horizon > 0,
    ...(histories.length ? { character_histories: histories } : {}),
  };
}
```

Add the field renderer using existing replacement field, disclosure, status,
and button classes. Route explanations and the 16-Character limit use plain
copy from the released UI but no inline styles or emoji icons.

- [ ] **Step 4: Implement owner-bound generation helper**

`generateLivedLocation` first attaches selected reusable Lore through
`POST /api/chats/{id}/lorebooks`, then calls
`POST /api/chats/{id}/charters/generate` with `lorebook_id` and the returned
story-owned `owning_lorebook_id`. It accepts caller-supplied channel, owner,
and `isCurrent` values and returns the authoritative server response.

- [ ] **Step 5: Run the focused test and verify GREEN**

Run the same command as Step 2. Expected: PASS.

- [ ] **Step 6: Commit the shared module**

```powershell
git add static/js/ui-next/lived-location.js static/css/ui/components.css browser_tests/test_ui_new_story.py static/js/ui-next/release.js
git commit -m "feat(ui): add lived-location controls"
```

---

### Task 3: Port alpha 9.8 New Story creation

**Files:**
- Modify: `static/js/ui-next/new-story.js`
- Modify: `static/css/ui/new-story.css`
- Test: `browser_tests/test_ui_new_story.py`

**Interfaces:**
- Consumes: Task 2's request builder/field renderer/generator.
- Produces: draft-backed optional lived-location configuration on all three New Story routes and exact incomplete-Story cleanup.

- [ ] **Step 1: Write failing behavior tests**

Add tests that prove:

```python
def test_blank_story_can_add_a_lived_location_without_other_generated_assets(...): ...
def test_story_review_names_location_history_and_character_routes(...): ...
def test_more_than_sixteen_full_characters_blocks_only_lived_location(...): ...
def test_failed_post_create_setup_deletes_only_the_incomplete_story(...): ...
def test_failed_cleanup_keeps_draft_and_links_the_surviving_story(...): ...
```

For cleanup, capture request methods and paths and assert the literal sequence
ends with `DELETE /api/chats/41`. For cleanup failure, assert the dialog still
contains the entered brief and exposes a `View incomplete Story` link.

- [ ] **Step 2: Run the New Story suite and verify RED**

```powershell
py -3.13 -m pytest --basetemp=.tmp\pytest-new-story-red -q browser_tests/test_ui_new_story.py
```

Expected: only the newly added tests fail for missing behavior.

- [ ] **Step 3: Extend the versioned setup draft**

Add `livedLocation` to `emptyDraft` and sanitize it in `restoreDraft`. Keep
browser-only keys until generated Character ids exist, then pass a literal
key-to-id resolver into `buildLivedLocationRequest`.

- [ ] **Step 4: Place controls in the approved three-step composition**

Describe/Library routes show the optional preparation after cast and Lore in
Step 2. Start Blank shows the same disclosure below its basic fields without
adding a route or step. The Step 3 review adds `Lived location` and `Character
pasts` rows only when selected.

- [ ] **Step 5: Implement exact cleanup and recovery**

Wrap only post-chat creation operations. On failure:

```javascript
try {
  await services.apiClient.delete(`/api/chats/${chatId}`, {
    channel: "new-story-cleanup", owner: DRAFT_OWNER,
  });
  throw originalError;
} catch (cleanupError) {
  if (cleanupError === originalError) throw originalError;
  throw Object.assign(new Error("Story setup failed and the incomplete Story could not be removed."), {
    incompleteStoryId: chatId,
    cause: originalError,
  });
}
```

Do not clear the local draft or prepared asset ids until successful generation
and navigation.

- [ ] **Step 6: Run the New Story suite and verify GREEN**

Run the Step 2 command. Expected: all New Story browser tests pass.

- [ ] **Step 7: Commit New Story parity**

```powershell
git add static/js/ui-next/new-story.js static/css/ui/new-story.css browser_tests/test_ui_new_story.py
git commit -m "feat(ui): port 9.8 story setup"
```

---

### Task 4: Port Character Quick Start and Lore generation

**Files:**
- Modify: `static/js/ui-next/library-editors/character-persona.js`
- Modify: `static/js/ui-next/library-authoring-runtime.js`
- Modify: `static/js/ui-next/library-view.js`
- Modify: `static/js/ui-next/library-runtime.js`
- Modify: `static/css/ui/library.css`
- Test: `browser_tests/test_ui_library_authoring.py`
- Test: `browser_tests/test_ui_library.py`

**Interfaces:**
- Consumes: Task 2's lived-location field renderer and generator.
- Produces: extended Quick Start payload and a guarded Lore-to-location action.

- [ ] **Step 1: Write failing Quick Start tests**

Capture the real Character start request and assert:

```python
assert request_json == {
    "persona_id": 3,
    "greeting_index": 0,
    "lorebook_id": 12,
    "already_known": False,
    "language": "en",
    "lived_location": {
        "enabled": True,
        "brief": "A hospital built into a cliff",
        "horizon_hours": 168,
        "active_tail_hours": 96,
        "generate_history": True,
        "character_history": {
            "mode": "resident",
            "brief": "Night-shift surgeon",
        },
    },
}
```

Also assert the public/private planning boundary and handoff copy are visible,
and a failed request retains every selected value.

- [ ] **Step 2: Write failing Lore action tests**

Add real-browser cases for current-Story availability, cross-Story refusal,
future-frame refusal, successful generation, return to the same Lore detail,
and the authoritative success summary.

- [ ] **Step 3: Run both focused files and verify RED**

```powershell
py -3.13 -m pytest --basetemp=.tmp\pytest-library98-red -q browser_tests/test_ui_library_authoring.py browser_tests/test_ui_library.py -k "quick_start or lived_location"
```

- [ ] **Step 4: Extend Quick Start without a second runtime owner**

The Character editor renders the fields, but `library-authoring-runtime.js`
continues to own save-before-start, request identity, error recovery, and Play
navigation. Change `quickStart` to accept one options object and send the exact
released payload.

- [ ] **Step 5: Add contextual Lore generation**

The Library detail view exposes the action only for Lore with a current Story.
`library-runtime.js` owns selection/story/frame guards and calls Task 2's
generator using a Library-owned request channel. A stale result cannot change
the currently selected item.

- [ ] **Step 6: Run focused tests and verify GREEN**

Run the Step 3 command. Expected: all selected tests pass.

- [ ] **Step 7: Commit Library entry points**

```powershell
git add static/js/ui-next/library-editors/character-persona.js static/js/ui-next/library-authoring-runtime.js static/js/ui-next/library-view.js static/js/ui-next/library-runtime.js static/css/ui/library.css browser_tests/test_ui_library_authoring.py browser_tests/test_ui_library.py
git commit -m "feat(ui): port 9.8 Library starts"
```

---

### Task 5: Port Charter inspection into Dialogue Story Tools

**Files:**
- Modify: `static/js/ui-next/story-tools/dialogue.js`
- Create: `static/js/ui-next/story-tools/charters.js`
- Modify: `static/js/ui-next/settings-view.js`
- Modify: `static/css/ui/story-tools.css`
- Modify: `static/css/ui/settings.css`
- Test: `browser_tests/test_ui_story_tools.py`
- Test: `browser_tests/test_ui_settings.py`
- Test: `tests/test_ui_story_author_tools_contracts.py`

**Interfaces:**
- Consumes: released Charter routes and Task 2's generation fields.
- Produces: `mountCharterSection(options)` and `mountCharterDiagnostics(options)` inside the Dialogue tool; Settings only links to this canonical owner.

- [ ] **Step 1: Write failing Charter Story Tool journeys**

Cover literal server fixtures for:

```python
CHARTER_RESPONSE = {
    "charters": {"items": {}},
    "character_history_routes": {},
    "character_journey_histories": {},
    "warnings": [],
}
```

and a populated response with one institution, one history route, warnings,
and diagnostics. Assert confirmed-empty copy, clamp copy at `inert`, summary
counts, diagnostic progressive disclosure, generation request, owner change,
and stale-response rejection.

- [ ] **Step 2: Write failing Settings ownership test**

Assert Settings uses alpha 9.8 world-clock terminology, says witnessing and
carrying are not settings, and exposes `Open Institution tools` rather than a
second Charter editor.

- [ ] **Step 3: Run focused tests and verify RED**

```powershell
py -3.13 -m pytest --basetemp=.tmp\pytest-charter-ui-red -q browser_tests/test_ui_story_tools.py browser_tests/test_ui_settings.py tests/test_ui_story_author_tools_contracts.py -k "charter or institution or living_world"
```

- [ ] **Step 4: Implement Charter presentation**

`charters.js` renders compact rows, history-route summaries, warnings, and
plain diagnostics. It computes counts only for display from the current server
response and stores none of them. Raw ledgers stay inside a native `details`
element. Story and Character names are created with text nodes and marked
untranslated.

- [ ] **Step 5: Integrate with Dialogue owner lifetime**

`dialogue.js` loads dialogue, background, living-world, and Charter documents
through the same `toolScope`. Saving continues to write only the three existing
configuration documents. Charter generation/diagnostics use separate scoped
requests and never enter the document editor draft.

- [ ] **Step 6: Update Settings terminology and link**

Keep the existing searchable living-world control. Replace stale descriptions
and add a routed button that opens Play with the Dialogue Story Tool selected;
do not fetch or render Charter registries in Settings.

- [ ] **Step 7: Run focused tests and verify GREEN**

Run the Step 3 command. Expected: all selected tests pass.

- [ ] **Step 8: Commit Story Tool parity**

```powershell
git add static/js/ui-next/story-tools/dialogue.js static/js/ui-next/story-tools/charters.js static/js/ui-next/settings-view.js static/css/ui/story-tools.css static/css/ui/settings.css browser_tests/test_ui_story_tools.py browser_tests/test_ui_settings.py tests/test_ui_story_author_tools_contracts.py
git commit -m "feat(ui): add Charter story tools"
```

---

### Task 6: Rebuild release, localization, guidance, and generated artifacts

**Files:**
- Modify: `static/ui-next.html`
- Modify: `static/js/ui-next/bootstrap.js`
- Modify: every changed module import/release declaration under `static/js/ui-next/`
- Modify: `web/app.py` release constant only
- Regenerate: `language_packs/en/ui.json`
- Regenerate: `language_packs/ja/ui.json`
- Regenerate: `language_packs/ja/translation_exceptions.json`
- Modify: `docs/guides/INTERFACE.md`
- Modify: `docs/design/sonder-ui-replacement/REQUIREMENTS_TRACEABILITY.md`
- Create: `docs/design/sonder-ui-replacement/wp15/REVIEW.md`
- Regenerate: `docs/CODE_MAP.md`

**Interfaces:**
- Consumes: Tasks 2-5 complete frontend graph.
- Produces: one cache-coherent alpha 9.8 replacement release and maintained evidence.

- [ ] **Step 1: Write a failing release/catalog contract**

Extend the existing replacement release test so it rejects mixed old/new query
identifiers and requires the new module to be reachable from the production
entry. Extend catalog checks by running the generator in check mode.

- [ ] **Step 2: Run the release/catalog checks and verify RED**

```powershell
py -3.13 -m pytest --basetemp=.tmp\pytest-release98-red -q tests/test_ui_next_entry.py tests/test_ui_catalog_extraction.py tests/test_language_pack_integrity.py tests/test_host_settings_surface.py
```

- [ ] **Step 3: Bump the graph to one identifier**

Use `alpha98-ui1` in HTML, backend cache policy, bootstrap import table, every
changed import query, and every changed module's `MODULE_RELEASE`. Do not mix
identifiers inside the graph.

- [ ] **Step 4: Regenerate catalogs and maps**

Run:

```powershell
py -3.13 tools/extract_ui_catalog.py
make map
make structure
```

- [ ] **Step 5: Record the maintained contract and review matrix**

Update `INTERFACE.md` with the shared frontend module and canonical Charter
Story Tool ownership. Add WP15 traceability rows for all 9.8 capabilities. The
review records product flow, visual system, responsive, implementation/state,
localization, and accessibility findings with exact commands/screenshots.

- [ ] **Step 6: Run the release/catalog checks and verify GREEN**

Run Step 2 plus `make structure`. Expected: all pass and generated files are
current.

- [ ] **Step 7: Commit release artifacts**

```powershell
git add static/ui-next.html static/js/ui-next static/css/ui web/app.py language_packs docs tests/test_ui_next_entry.py tests/test_ui_catalog_extraction.py tests/test_language_pack_integrity.py tests/test_host_settings_surface.py
git commit -m "docs(ui): qualify alpha 9.8 parity"
```

---

### Task 7: Visual qualification, full verification, and interface integration

**Files:**
- Add evidence: `docs/design/sonder-ui-replacement/wp15/screenshots/*.png`
- Update findings: `docs/design/sonder-ui-replacement/wp15/REVIEW.md`
- Merge completed branch into: `interface`

**Interfaces:**
- Consumes: completed alpha 9.8 replacement build.
- Produces: exact-head evidence and final commits on `interface`.

- [ ] **Step 1: Start the real host and capture the required states**

Use the project's actual authenticated host and the browser fixture patterns.
Capture New Story, Lore detail, Dialogue/Charter, and Settings at 1440x900,
1024x768, 768x1024, 430x932, 390x844, 360x800, 844x390, and 1024x600 as
applicable. Include loading, empty, populated, generation, validation, failure,
Japanese, and Accessibility Mode.

- [ ] **Step 2: Compare side by side with supplied references**

Check macro geometry first: shell regions, modal/inspector width, hierarchy,
action placement, and mobile staging. Then check spacing, density, type, icons,
colors, focus, and state. Record every approved difference; fix every
unapproved P0/P1 before proceeding.

- [ ] **Step 3: Run focused frontend and affected backend verification**

```powershell
py -3.13 -m pytest --basetemp=.tmp\pytest-alpha98-focused -q browser_tests/test_ui_new_story.py browser_tests/test_ui_library_authoring.py browser_tests/test_ui_library.py browser_tests/test_ui_story_tools.py browser_tests/test_ui_settings.py tests/test_story_quick_start_history.py tests/test_fable_town.py tests/test_ui_story_author_tools_contracts.py tests/test_ui_next_entry.py tests/test_ui_catalog_extraction.py tests/test_language_pack_integrity.py
```

- [ ] **Step 4: Run exact-head repository gates**

```powershell
make check
make test-browser
git diff --check
git status --short
```

Expected: all tests pass, generated artifacts are current, no whitespace
errors, and only intentional evidence changes remain.

- [ ] **Step 5: Commit final evidence if needed**

```powershell
git add docs/design/sonder-ui-replacement/wp15
git commit -m "docs(ui): record alpha 9.8 review"
```

- [ ] **Step 6: Merge into interface and reverify exact head**

From the primary checkout:

```powershell
git switch interface
git merge --no-ff codex/ui-alpha98
make check
make test-browser
git status -sb
git log -1 --oneline
```

Expected: `interface` contains alpha 9.8 ancestry and all parity commits, both
full gates pass at the merge commit, and the checkout is clean.
