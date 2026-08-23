# Character and Persona Authoring Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move reusable Character, Persona, and story-specific Character-card editing into one focused, lossless Library authoring workspace.

**Architecture:** Keep `library-authoring-runtime.js` as the sole draft, revision, request, and persistence authority. Route person-authoring modes through a destination-owned workspace, suppress the contextual inspector without changing its persisted state, and compose a sectioned editor from a focused document-section module plus the existing generation and Quick Start services.

**Tech Stack:** Browser-native ES modules, DOM APIs, layered CSS, FastAPI routes, pytest source/API contracts, Playwright Chromium behavior tests.

**Spec:** `docs/superpowers/specs/2026-08-23-character-persona-authoring-workspace-design.md`

## Global Constraints

- The Design Bible and maintained `docs/guides/INTERFACE.md` remain visual and implementation authority.
- Reusable Characters, Personas, and story-specific Character cards use one presentation framework and their existing server contracts.
- Browser-local drafts remain owner-scoped; server documents change only after accepted Save.
- Unknown document fields must round-trip unchanged and remain reachable in Additional fields or Advanced.
- The parent Library category, scope, Story, query, sort, visibility, selection, and scroll position must survive authoring.
- Mobile and short-landscape retain every maintained capability with 44 by 44 CSS-pixel targets.
- New user-facing copy must be present in English and Japanese catalogs in the same release.
- All immutable replacement assets use one content-derived release identifier.

---

### Task 1: Lock the person-authoring route and workspace contract

**Files:**
- Modify: `tests/test_ui_character_persona_editor_contracts.py`
- Modify: `browser_tests/test_ui_character_persona_editor.py`
- Modify: `static/js/ui-next/library-authoring-view.js`
- Modify: `static/js/ui-next/destinations.js`
- Modify: `static/js/ui-next/inspector-host.js`

**Interfaces:**
- Consumes: `state.route`, `services.library`, `mountLibraryAuthoring(options)`.
- Produces: `isPersonAuthoringRoute(route) -> boolean` and `createLibraryAuthoringWorkspace(options) -> { element, teardown }`.

- [ ] **Step 1: Add failing source-contract coverage**

Add assertions proving the destination routes only Character/Persona
`edit|create|import|story-card` modes to the workspace and that the inspector
recognizes the same predicate:

```python
def test_people_authoring_owns_the_library_destination_workspace():
    view = (RUNTIME / "library-authoring-view.js").read_text(encoding="utf-8")
    destinations = (RUNTIME / "destinations.js").read_text(encoding="utf-8")
    inspector = (RUNTIME / "inspector-host.js").read_text(encoding="utf-8")
    assert "export function isPersonAuthoringRoute" in view
    assert "createLibraryAuthoringWorkspace" in destinations
    assert "isPersonAuthoringRoute(route)" in inspector
    assert "dataset.libraryAuthoring" in inspector
```

- [ ] **Step 2: Run the source contract and confirm RED**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_ui_character_persona_editor_contracts.py::test_people_authoring_owns_the_library_destination_workspace -q
```

Expected: failure because the exported route predicate and workspace factory do
not exist.

- [ ] **Step 3: Add the route predicate and workspace factory**

Implement the exact exports in `library-authoring-view.js`:

```js
export function isPersonAuthoringRoute(route) {
  if (route?.destination !== "library") return false;
  if (!["edit", "create", "import", "story-card"].includes(route.query?.mode)) return false;
  const segment = route.segments?.[0];
  const item = String(route.query?.item || "");
  return ["characters", "personas"].includes(segment)
    || /^(character|persona):[1-9][0-9]*$/.test(item);
}

export function createLibraryAuthoringWorkspace(options = {}) {
  const documentRef = options.document || document;
  const section = documentRef.createElement("section");
  section.className = "ui-person-workspace";
  section.dataset.personWorkspace = "true";
  const target = documentRef.createElement("div");
  target.className = "ui-person-workspace__mount";
  section.append(target);
  const mounted = mountLibraryAuthoring({ ...options, document: documentRef, target });
  return Object.freeze({ element: section, teardown: mounted.teardown });
}
```

In `destinations.js`, call that factory before ordinary `createLibraryView`.
In `inspector-host.js`, set `root.dataset.libraryAuthoring`, present neither the
desktop inspector nor compact overlay while the predicate is true, and keep the
persisted `panes` object unchanged.

- [ ] **Step 4: Run the focused source contracts**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_ui_character_persona_editor_contracts.py tests/test_ui_library_authoring_contracts.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit the workspace ownership seam**

```powershell
git add tests/test_ui_character_persona_editor_contracts.py static/js/ui-next/library-authoring-view.js static/js/ui-next/destinations.js static/js/ui-next/inspector-host.js
git commit -m "feat(ui): add person authoring workspace"
```

### Task 2: Build the shared sectioned document editor

**Files:**
- Create: `static/js/ui-next/library-editors/person-sections.js`
- Modify: `static/js/ui-next/library-editors/character-persona.js`
- Modify: `static/js/ui-next/bootstrap.js`
- Modify: `tests/test_ui_character_persona_editor_contracts.py`
- Modify: `browser_tests/test_ui_character_persona_editor.py`

**Interfaces:**
- Consumes: a complete cloned document, `state.kind`, `state.mode`, translator, and `onChange(path, value)`.
- Produces: `createPersonSectionEditor(options) -> { navigation, panels, firstInvalid(), activate(id), activeId }`.

- [ ] **Step 1: Add failing section and losslessness contracts**

Add source assertions for the shared section module and a browser test that
mounts a Character with an unknown top-level field:

```python
def test_shared_person_sections_keep_all_document_fields_reachable():
    sections = (RUNTIME / "library-editors" / "person-sections.js").read_text(encoding="utf-8")
    editor = (RUNTIME / "library-editors" / "character-persona.js").read_text(encoding="utf-8")
    for label in ("Basics", "Appearance", "History", "Inner life", "Opening", "Simulation", "Story presence", "Additional fields", "Advanced"):
        assert label in sections or label in editor
    assert "createPersonSectionEditor" in sections
    assert "unknownTopLevel" in sections
```

The browser assertion must verify an `extension_payload` object appears under
Additional fields and remains in the document passed to `services.authoring.stage`.

- [ ] **Step 2: Run the focused test and confirm RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_ui_character_persona_editor_contracts.py::test_shared_person_sections_keep_all_document_fields_reachable -q
```

Expected: missing `person-sections.js`.

- [ ] **Step 3: Implement the section registry and controls**

Create `person-sections.js` with:

```js
export const PERSON_SECTION_IDS = Object.freeze([
  "basics", "appearance", "history", "inner-life", "opening",
  "simulation", "story-presence", "additional", "advanced",
]);

export function createPersonSectionEditor({
  document: documentRef, current, kind, mode, t, onChange, onNameChange,
}) {
  // Build one tablist/navigation control and one panel per applicable section.
  // Partition top-level keys without deleting or normalizing their values.
  // Return activate/firstInvalid so the form coordinator owns validation focus.
}
```

Partition top-level document keys exactly as follows:

```js
const GROUPS = Object.freeze({
  identity: "basics",
  initial_outfit: "appearance",
  embodiment: "appearance",
  competence: "appearance",
  knowledge: "history",
  psychology: "inner-life",
  social: "inner-life",
  initial_state: "inner-life",
  opening: "opening",
  simulation: "simulation",
  narration: "story-presence",
});
```

Any unlisted key goes to `additional`. Arrays remain JSON textareas that call
`onChange` only after valid array JSON. `identity.uid` is disabled. Keep the
primary plain controls for name, aliases, pronouns, visible summary, public
history, and first message inside their assigned panels.

- [ ] **Step 4: Replace the monolithic field sequence with the shared module**

In `character-persona.js`, keep generation, Quick Start, Advanced Apply, Save,
Discard, and import orchestration. Replace `createSchemaSections` and the flat
primary field append with `createPersonSectionEditor`. Mount tools into Opening
for Characters and into the relevant generated panel for Personas; mount Quick
Start into its Character-only panel.

Add the module to the explicit bootstrap graph:

```js
libraryPersonSections: "./library-editors/person-sections.js?release=alpha98-ui2-3f44d1cc71ed",
```

The literal release is rotated in Task 6.

- [ ] **Step 5: Run source and browser component tests**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_ui_character_persona_editor_contracts.py -q
.\.venv\Scripts\python.exe -m pytest browser_tests/test_ui_character_persona_editor.py -q
```

Expected: complete pass, including Advanced JSON, unknown-field staging,
generation preview, Quick Start, and story-card behavior.

- [ ] **Step 6: Commit the shared editor framework**

```powershell
git add static/js/ui-next/library-editors/person-sections.js static/js/ui-next/library-editors/character-persona.js static/js/ui-next/bootstrap.js tests/test_ui_character_persona_editor_contracts.py browser_tests/test_ui_character_persona_editor.py
git commit -m "feat(ui): section person card editing"
```

### Task 3: Preserve Back, scroll, draft, focus, and validation state

**Files:**
- Modify: `static/js/ui-next/library-runtime.js`
- Modify: `static/js/ui-next/library-authoring-runtime.js`
- Modify: `static/js/ui-next/library-authoring-view.js`
- Modify: `static/js/ui-next/library-view.js`
- Modify: `tests/test_ui_library_authoring_contracts.py`
- Modify: `browser_tests/test_ui_library_authoring.py`

**Interfaces:**
- Consumes: the current normalized Library route and existing `presentation.scrolls` envelope.
- Produces: `authoring.returnToLibrary() -> boolean` and final-scroll capture on Library teardown.

- [ ] **Step 1: Add failing return-state behavior coverage**

Create a Playwright journey that starts on:

```text
#/library/characters?item=character%3A7&q=mara&scope=story&sort=recent&story=1&visibility=active
```

Scroll the Library content, enter Edit, change the name, move to another editor
section, invoke Back, and assert:

```python
expect(page).to_have_url(re.compile(r"item=character%3A7.*q=mara.*scope=story"))
assert page.evaluate("document.querySelector('.ui-library__content').scrollTop") == saved_scroll
expect(page.locator('[data-library-item="character:7"]')).to_be_focused()
```

Re-enter Edit and assert the locally staged name is restored.

- [ ] **Step 2: Run the journey and confirm RED**

```powershell
.\.venv\Scripts\python.exe -m pytest browser_tests/test_ui_library_authoring.py -k "person_workspace_restores" -q
```

Expected: the dedicated Back service or focus/scroll restoration is absent.

- [ ] **Step 3: Implement parent-route return**

Add `returnToLibrary` to the authoring runtime's returned service. It removes
`mode` and `session`, retains safe Library query keys, retains `item` for edit
and story-card, and uses replace navigation:

```js
const returnToLibrary = () => {
  const route = router.current();
  if (route?.destination !== "library") return false;
  const query = { ...(route.query || {}) };
  delete query.mode;
  delete query.session;
  if (["create", "import"].includes(active?.mode)) delete query.item;
  router.navigate({ destination: "library", segments: route.segments, query }, { replace: true });
  return true;
};
```

Wire the workspace Back and import Back controls to this service. After the
Library rerenders, focus `[data-library-item="${item}"]`, falling back to the
Library heading.

- [ ] **Step 4: Capture final list scroll before teardown**

In `createLibraryView`, call `services.library.saveScroll(routeIdentity,
scrollRegion.scrollTop)` in teardown before removing the passive listener.

- [ ] **Step 5: Implement validation section activation**

On Save with an empty required name or a field marked `aria-invalid=true`, call
the section controller's `firstInvalid()`, activate its panel, then focus the
control. Confirm no hidden control remains keyboard-focusable.

- [ ] **Step 6: Run focused state tests**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_ui_library_authoring_contracts.py browser_tests/test_ui_library_authoring.py -q
```

Expected: all pass.

- [ ] **Step 7: Commit state restoration**

```powershell
git add static/js/ui-next/library-runtime.js static/js/ui-next/library-authoring-runtime.js static/js/ui-next/library-authoring-view.js static/js/ui-next/library-view.js tests/test_ui_library_authoring_contracts.py browser_tests/test_ui_library_authoring.py
git commit -m "fix(ui): restore Library after authoring"
```

### Task 4: Implement responsive, accessible workspace geometry

**Files:**
- Modify: `static/css/ui/library.css`
- Modify: `static/css/ui/library-authoring.css`
- Modify: `tests/test_ui_character_persona_editor_contracts.py`
- Modify: `browser_tests/test_ui_library_authoring.py`

**Interfaces:**
- Consumes: `.ui-person-workspace`, `.ui-person-editor__nav`, `.ui-person-editor__panel`, root `data-library-authoring`.
- Produces: one scroll owner, visible selected section, sticky actions, and compact full-screen staging.

- [ ] **Step 1: Add failing geometry and accessibility assertions**

At 1440×900, 1024×768, 390×844, and 844×390 assert:

```python
expect(page.locator("[data-person-workspace]")).to_be_visible()
expect(page.locator(".ui-library__filters")).to_have_count(0)
expect(page.get_by_role("complementary", name="Library details")).to_be_hidden()
expect(page.get_by_role("button", name="Save character")).to_be_in_viewport()
```

Measure every visible interactive target at a minimum of 44×44 CSS pixels on
compact layouts, verify exactly one workspace body has vertical overflow, and
verify hidden panels contain no focusable descendants.

- [ ] **Step 2: Run compact browser cases and confirm RED**

```powershell
.\.venv\Scripts\python.exe -m pytest browser_tests/test_ui_library_authoring.py -k "person_workspace_geometry" -q
```

Expected: missing workspace layout selectors or inspector suppression.

- [ ] **Step 3: Add desktop and tablet layout**

Implement:

```css
.ui-person-workspace {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  min-inline-size: 0;
  min-block-size: 0;
  block-size: 100%;
}

.ui-person-editor {
  display: grid;
  grid-template-columns: minmax(11rem, 14rem) minmax(0, 1fr);
  min-block-size: 0;
}

.ui-person-editor__body {
  min-block-size: 0;
  overflow: auto;
  overscroll-behavior: contain;
}
```

Use the current Design Bible tokens, a readable main-column measure, and no
new card-grid language.

- [ ] **Step 4: Add compact and short-landscape staging**

Below the existing compact/short-height breakpoint, make the section navigator
a horizontally scrollable semantic strip with the selected item brought into
view, stack controls, keep 1rem form font size, and keep Back/Save in the stable
header/action geometry. Hide descriptions before reducing controls.

- [ ] **Step 5: Run the browser viewport matrix**

```powershell
.\.venv\Scripts\python.exe -m pytest browser_tests/test_ui_library_authoring.py -q
```

Expected: all authoring journeys pass in Chromium.

- [ ] **Step 6: Commit responsive geometry**

```powershell
git add static/css/ui/library.css static/css/ui/library-authoring.css tests/test_ui_character_persona_editor_contracts.py browser_tests/test_ui_library_authoring.py
git commit -m "style(ui): stage person editor responsively"
```

### Task 5: Update maintained contracts, ledger, and visual evidence

**Files:**
- Modify: `docs/guides/INTERFACE.md`
- Modify: `docs/design/sonder-ui-bible/docs/26_DECISION_REGISTER.md`
- Modify: `docs/design/sonder-ui-bible/CHANGELOG.md`
- Modify: `docs/design/sonder-ui-replacement/UI_CLEANUP_FIX_LIST.md`
- Modify: `docs/design/sonder-ui-replacement/CHARACTER_PERSONA_EDITOR_CAPABILITY_AUDIT.md`
- Create: `docs/design/sonder-ui-replacement/wp16/REVIEW.md`
- Create: `docs/design/sonder-ui-replacement/wp16/screenshots/person-editor-1440.png`
- Create: `docs/design/sonder-ui-replacement/wp16/screenshots/person-editor-1024.png`
- Create: `docs/design/sonder-ui-replacement/wp16/screenshots/person-editor-390.png`
- Create: `docs/design/sonder-ui-replacement/wp16/screenshots/person-editor-844x390.png`
- Create: `tools/capture_ui_person_editor.py`

**Interfaces:**
- Consumes: the implemented workspace and browser viewport matrix.
- Produces: maintained authority text, neutral completion evidence, and repeatable captures.

- [ ] **Step 1: Add the maintained interface contract**

Under Library ownership in `INTERFACE.md`, record the destination takeover,
shared framework, local/server save wording, parent-route restoration, and
inspector-state preservation. Do not describe implementation provenance.

- [ ] **Step 2: Record the Design Bible extension**

Add a decision-register row naming the focused person-authoring workspace as an
extension of Library editors, and add a changelog entry with desktop, compact,
accessibility, localization, and migration impact.

- [ ] **Step 3: Capture four real-browser screenshots**

Implement `tools/capture_ui_person_editor.py` using the existing capture helper
patterns. It must stub only public API responses, load the real ES-module graph,
open a dense Character's Inner life section, wait for fonts/layout stability,
and save the four named PNGs.

Run:

```powershell
.\.venv\Scripts\python.exe tools/capture_ui_person_editor.py
```

Expected: four non-empty PNG files at the exact paths above.

- [ ] **Step 4: Write the WP-16 review**

Record viewport, behavior, keyboard, reduced-motion, comparison, and approved
difference evidence. Update the capability audit's partial/missing rows with
the exact test or screenshot proving support.

- [ ] **Step 5: Close the follow-up ledger rows**

Set UI-FU-01 and UI-FU-02 to implemented only after every named browser
criterion has passed. Preserve user-authored themes as separate backlog.

- [ ] **Step 6: Run documentation and privacy checks**

```powershell
git diff --check
rg -n -i "private conversation|personal commentary|feedback attribution|Codex chat" docs/guides/INTERFACE.md docs/design/sonder-ui-bible docs/design/sonder-ui-replacement docs/superpowers
```

Expected: `git diff --check` is clean and the privacy scan returns no matches.

- [ ] **Step 7: Commit documentation and evidence**

```powershell
git add docs/guides/INTERFACE.md docs/design/sonder-ui-bible docs/design/sonder-ui-replacement tools/capture_ui_person_editor.py
git commit -m "docs(ui): record person editor evidence"
```

### Task 6: Rotate the immutable release and run completion gates

**Files:**
- Modify: all files containing the prior `alpha98-ui2-...` release literal
- Modify: `tests/test_ui_runtime_contracts.py` only if the immutable graph gains a new owned path not already covered by recursive discovery

**Interfaces:**
- Consumes: every immutable replacement CSS, JavaScript, and SVG asset.
- Produces: one `alpha98-ui3-<12 hex>` release literal matching the normalized content fingerprint.

- [ ] **Step 1: Compute the normalized immutable fingerprint**

Use the same algorithm as `_immutable_ui_fingerprint()` in
`tests/test_ui_runtime_contracts.py`: sorted relative path, NUL separator,
release token replaced with `__UI_RELEASE__`, CRLF normalized to LF, SHA-256
truncated to 12 hex characters.

- [ ] **Step 2: Replace the release literal coherently**

Replace the previous release in replacement HTML, all replacement ES modules,
`static/js/ui/icons.js`, `web/app.py`, and release-specific source assertions.
Use `alpha98-ui3-<computed fingerprint>` and recompute until the fingerprint
test agrees.

- [ ] **Step 3: Run focused UI and API tests**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_ui_runtime_contracts.py tests/test_ui_character_persona_editor_contracts.py tests/test_ui_library_authoring_contracts.py tests/test_library_character_persona_authoring.py browser_tests/test_ui_character_persona_editor.py browser_tests/test_ui_library_authoring.py -q
```

Expected: all pass.

- [ ] **Step 4: Run the complete browser suite**

```powershell
.\.venv\Scripts\python.exe -m pytest browser_tests -q
```

Expected: all browser tests pass.

- [ ] **Step 5: Run the complete repository gate**

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe tools/project_check.py
git diff --check
git status --short
```

Expected: pytest and project checks pass, diff check is clean, and only the
intentional implementation files are modified.

- [ ] **Step 6: Commit the coherent release**

```powershell
git add static web tests browser_tests
git commit -m "build(ui): rotate person editor release"
```

- [ ] **Step 7: Push and verify CI**

```powershell
git push origin interface
gh run list --branch interface --limit 5 --json databaseId,status,conclusion,url,headSha
gh run watch <run-id> --exit-status
```

Expected: `origin/interface` equals local HEAD and every required GitHub Actions
job succeeds for that SHA.
