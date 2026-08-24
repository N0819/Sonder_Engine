# Person Authoring Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the approved shared Character, Persona, and story-card workspace so its controls, field language, destructive actions, responsive hierarchy, and visual evidence meet the Design Bible.

**Architecture:** Keep `library-authoring-runtime.js` as the only draft and persistence authority. Refine the shared presentation in `person-sections.js`, `character-persona.js`, and `library-authoring.css`: one semantic field registry drives ordinary sections, technical fallbacks remain lossless under More/Advanced, and the editor frame owns its action footer and discard confirmation.

**Tech Stack:** Browser-native ES modules, DOM APIs, layered CSS, pytest contract tests, Playwright Chromium tests, deterministic screenshot capture.

**Spec:** `docs/superpowers/specs/2026-08-23-character-persona-authoring-workspace-design.md`

## Global Constraints

- Preserve the approved Design Bible and replacement composition; earlier interfaces remain capability references only.
- Reusable Characters, Personas, and story-specific Character cards continue to use one shared framework and existing server contracts.
- Unknown and extension-owned fields must round-trip unchanged through Additional fields and Advanced.
- No destructive draft action may occur without naming the affected document and consequence.
- Compact layouts retain every capability, 44 by 44 CSS-pixel targets, one vertical document scroll owner, and no page overflow.
- New user-facing copy must be present in English and Japanese catalogs in the same release.
- All immutable replacement assets must use one content-derived release identifier.

---

### Task 1: Lock component styling, editor sizing, and destructive safety

**Files:**
- Modify: `browser_tests/test_ui_character_persona_editor.py`
- Modify: `browser_tests/test_ui_library_authoring.py`
- Modify: `static/js/ui-next/library-editors/character-persona.js`
- Modify: `static/js/ui-next/library-editors/person-sections.js`
- Modify: `static/css/ui/library-authoring.css`

**Interfaces:**
- Consumes: `services.authoring.discard()`, current authoring state, shared `.ui-field__control` styling.
- Produces: styled controls, a 22rem Advanced editor, 7rem structured-list editors, and a named confirmation before dirty-draft reset.

- [x] **Step 1: Add failing browser assertions**

Add assertions that the rendered text, number, select, file, and textarea controls use `ui-field__control`; that computed Advanced and structured-list minimum block sizes are at least 352px and 112px on desktop; and that a dirty draft opens a `Discard changes to Mara Venn?` dialog whose Cancel preserves the draft while `Discard local changes` restores the saved document.

- [x] **Step 2: Run RED**

```powershell
.\.venv\Scripts\python.exe -m pytest browser_tests/test_ui_character_persona_editor.py browser_tests/test_ui_library_authoring.py -k "field_contract or advanced_editor_size or discard_confirmation" -q
```

Expected: failures on the native-gray control classes, 44px Advanced editor, and immediate discard call.

- [x] **Step 3: Implement the minimal shared correction**

Use `ui-field__control` for ordinary inputs/selects/textareas, add `ui-authoring-form__long` only to prose controls, lower the blanket target selector specificity with `:where()`, and express JSON minimums with `min-block-size`. Add a native modal dialog with Cancel and `ui-button--destructive`; call `services.authoring.discard()` only after confirmed dirty state.

- [x] **Step 4: Run GREEN**

Run the command from Step 2 and require a complete pass.

### Task 2: Replace raw ordinary-section keys with a semantic field registry

**Files:**
- Modify: `browser_tests/test_ui_character_persona_editor.py`
- Modify: `static/js/ui-next/library-editors/person-sections.js`
- Modify: `language_packs/en/ui.json`
- Modify: `language_packs/ja/ui.json`

**Interfaces:**
- Consumes: complete person documents and path-based `onChange(path, value)`.
- Produces: `FIELD_SPECS[path] -> { label, help, control, min, max, step, options }` plus an Additional-fields fallback for unregistered paths.

- [x] **Step 1: Add a failing semantic-field test**

Mount the real editor with Simulation, psychology, initial state, and an unknown nested extension field. Assert ordinary sections expose `Creativity`, `Curiosity`, `Background activity`, `Starting mood`, and `Pain sensitivity`; assert labels `Top p`, `Offscreen agent`, and `Hedonics` are absent; edit a bounded numeric field and verify the complete staged document remains lossless.

- [x] **Step 2: Run RED**

```powershell
.\.venv\Scripts\python.exe -m pytest browser_tests/test_ui_character_persona_editor.py -k "semantic_field_registry" -q
```

Expected: raw-key labels remain and numeric controls lack the approved bounds/help.

- [x] **Step 3: Implement the registry**

Define plain labels and help for every maintained ordinary path. Render complex structured lists as labeled JSON textareas, booleans as labeled checkboxes, bounded values with literal `min`, `max`, and `step`, and bounded enums as selects. Send unregistered paths to Additional fields without renaming or normalizing their stored values.

- [x] **Step 4: Run GREEN and catalog validation**

```powershell
.\.venv\Scripts\python.exe -m pytest browser_tests/test_ui_character_persona_editor.py -k "semantic_field_registry or shared_person_sections" -q
.\.venv\Scripts\python.exe tools\project_check.py
```

Expected: semantic/losslessness tests pass and both UI catalogs contain the new copy.

### Task 3: Refine hierarchy, Quick Start, and connected workspace geometry

**Files:**
- Modify: `browser_tests/test_ui_library_authoring.py`
- Modify: `static/js/ui-next/library-authoring-view.js`
- Modify: `static/js/ui-next/library-editors/character-persona.js`
- Modify: `static/js/ui-next/library-editors/person-sections.js`
- Modify: `static/css/ui/library-authoring.css`

**Interfaces:**
- Consumes: existing section activation and active-section memory.
- Produces: short peer tab strips, a More disclosure for Quick Start/Additional/Advanced, a topbar joining Back and save state, and an action footer inside the editor frame.

- [x] **Step 1: Add failing hierarchy and viewport tests**

Assert the visible mobile strip contains at most the six peer content sections plus More; More exposes `Start a Story`, Additional fields, and Advanced; the active auxiliary label stays visible; Quick Start has one heading and uses `Save and start Story`; the connected footer stays in view at 390x844 and 844x390 without page overflow.

- [x] **Step 2: Run RED**

```powershell
.\.venv\Scripts\python.exe -m pytest browser_tests/test_ui_library_authoring.py -k "person_workspace_hierarchy or person_workspace_geometry" -q
```

Expected: nine peer tabs, duplicate Quick Start heading, and the detached footer fail the assertions.

- [x] **Step 3: Implement staged auxiliary sections and geometry**

Keep Basics, Appearance, History, Inner life, Opening, Simulation, and Story presence as peer tabs. Place Quick Start, Additional fields, and Advanced in one predictable More disclosure, update its summary to the active auxiliary label, remove nested duplicate headings, append the action footer inside `.ui-person-editor`, and align Back/save status in `.ui-authoring__topbar`.

- [x] **Step 4: Run GREEN across responsive cases**

Run the command from Step 2 and require 1440x900, 1024x768, 1024x600, 390x844, 360x800, and 844x390 cases to pass.

### Task 4: Update contracts, ledger, repeatable evidence, and release fingerprint

**Files:**
- Modify: `docs/guides/INTERFACE.md`
- Modify: `docs/superpowers/specs/2026-08-23-character-persona-authoring-workspace-design.md`
- Modify: `docs/design/sonder-ui-replacement/UI_CLEANUP_FIX_LIST.md`
- Modify: `docs/design/sonder-ui-replacement/wp16/REVIEW.md`
- Modify: `tools/capture_ui_person_editor.py`
- Modify: `docs/design/sonder-ui-replacement/wp16/screenshots/*.png`
- Modify: immutable UI release literals discovered by `tests/test_ui_runtime_contracts.py`

**Interfaces:**
- Consumes: the verified implementation and immutable-asset fingerprint algorithm.
- Produces: neutral authority text, Character/Persona/story-card and state evidence, and one coherent `alpha98-ui5-<12 hex>` release.

- [x] **Step 1: Record the approved polish contract**

Add ledger rows with priority, observed problem, approved direction, and concrete browser criteria. Amend WP-16 from unconditional acceptance to the verified polished result only after the named tests and captures pass.

- [x] **Step 2: Expand deterministic captures**

Capture Character desktop/mobile, Persona, story-card, dirty/discard confirmation, validation error, long-label, Accessibility Mode, and 200-percent zoom-equivalent states through public intercepted APIs and the real module graph.

- [x] **Step 3: Rotate the immutable release**

Compute the normalized fingerprint used by `_immutable_ui_fingerprint()`, replace every prior literal coherently, and recompute until `tests/test_ui_runtime_contracts.py` accepts the suffix.

- [x] **Step 4: Run focused gates**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_ui_runtime_contracts.py tests/test_ui_character_persona_editor_contracts.py tests/test_ui_library_authoring_contracts.py tests/test_library_character_persona_authoring.py browser_tests/test_ui_character_persona_editor.py browser_tests/test_ui_library_authoring.py -q
```

Expected: complete pass.

### Task 5: Complete exact-head verification and integration

**Files:**
- Review: all changed files

**Interfaces:**
- Consumes: the exact candidate commit.
- Produces: a reviewed, pushed `interface` commit with successful CI.

- [x] **Step 1: Run all local gates**

```powershell
.\.venv\Scripts\python.exe -m pytest browser_tests -q
.\.venv\Scripts\python.exe -m pytest -q -n auto
.\.venv\Scripts\python.exe tools\project_check.py
git diff --check
```

- [x] **Step 2: Review the complete diff**

Check every approved finding against implementation and browser evidence; correct all Critical or Important review findings.

- [x] **Step 3: Commit and push**

```powershell
git add browser_tests/test_ui_character_persona_editor.py browser_tests/test_ui_library_authoring.py static/js/ui-next/library-authoring-view.js static/js/ui-next/library-editors/character-persona.js static/js/ui-next/library-editors/person-sections.js static/css/ui/library-authoring.css language_packs/en/ui.json language_packs/ja/ui.json docs/guides/INTERFACE.md docs/superpowers/specs/2026-08-23-character-persona-authoring-workspace-design.md docs/superpowers/plans/2026-08-23-person-authoring-polish.md docs/design/sonder-ui-replacement/UI_CLEANUP_FIX_LIST.md docs/design/sonder-ui-replacement/wp16 tools/capture_ui_person_editor.py static/ui-next.html static/js static/css web/app.py tests/test_ui_runtime_contracts.py
git commit -m "fix(ui): polish person authoring"
git push origin interface
```

- [x] **Step 4: Verify the remote SHA and CI**

```powershell
gh run list --branch interface --limit 5 --json databaseId,status,conclusion,url,headSha
$run = gh run list --branch interface --limit 1 --json databaseId --jq '.[0].databaseId'
gh run watch $run --exit-status
```

Expected: `origin/interface` equals local HEAD and required GitHub Actions jobs succeed for that exact SHA.
