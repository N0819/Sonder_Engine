# Sonder All-Widget Mockup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking. Multi-agent execution is not part of
> this plan.

**Goal:** Create every Widget specified by the Panels and Widgets design
package in the Sonder Play workspace mockup, using the approved Minimal UI SVG
artifact and proving registry, state, placement, responsive, accessibility,
extension, and regression coverage.

**Architecture:** Extend the current standalone Panels mockup rather than
replacing it. One object-based Widget registry supplies 91 built-in definitions;
a separate owner-bound mock extension API contributes three representative
dynamic shapes. A centralized real-SVG symbol map, shared Widget anatomy, and a
generic state shell let every definition render distinctive ready content plus
all documented loading, empty, unavailable, conflict, destructive-review, and
failure states without duplicating application truth.

**Tech Stack:** Standalone HTML/CSS/vanilla JavaScript, local inline SVG symbol
sprite assembled from `artifacts/minimal-ui-icons`, browser `localStorage` for
mock-only Panel state, native dialog/focus semantics, iframe/PointerEvent
regression harness, Visualize preview renderer, and in-app Chromium review.

**Spec:**
`docs/design/sonder-panels-and-widgets/10_WIDGET_DESIGN_WORKBOOK.md` and
`docs/design/sonder-panels-and-widgets/11_ICON_SOURCE_AND_USAGE.md`.

## Global Constraints

- Current external source, preview, and harness are authoritative; earlier
  workbook hashes are historical evidence only.
- Canonical editable source:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-workbench-calibration.html`.
- Canonical regression harness:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-drag-regression.html`.
- Canonical generated preview:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-workbench-calibration-preview.html`.
- Perform edits with `apply_patch` against a writable staging copy under
  `C:/Users/Keptin/.codex/visualizations/2026/08/26/01a03f59-ba9f-7082-866d-da3a99ff4445/widget-build-staging/`;
  copy verified checkpoints to canonical paths without deleting unrelated
  visualization files.
- Preserve all 55 current regression cases. Update the obsolete exact-19 count
  assertions to the approved 91 built-in plus three dynamic definition model.
- The top-level Catalog contains 91 built-in definitions and three registered
  extension examples. Host session and the embedded extension Inspector
  renderer are not top-level definitions.
- All story-aware Widgets follow the one active Story and store no Story id in
  Panel state. Selection-following Widgets use typed mock selection channels.
- Every definition declares icon, context, role, shape, minimum columns,
  multiplicity, purpose, keywords, ready blueprint, and state list.
- Every product-chrome icon resolves to the local 1,796-entry Minimal UI
  manifest. Do not introduce generated artwork, emoji, Unicode control glyphs,
  icon fonts, CSS drawings, or runtime network loads.
- Preserve SVG path geometry and viewBox. Only safe paint normalization to
  `currentColor`, whitespace removal, and symbol-id wrapping are allowed.
- Familiar low-risk controls may be icon-only with accessible names. Primary,
  ambiguous, destructive, expensive, security-sensitive, and uncommon actions
  retain visible labels or icon-plus-label treatment.
- Catalog previews remain inert, representative, side-effect free, and free of
  secrets/private story data. All samples are synthetic.
- Preserve the canonical atmospheric canvas, fixed transcript measure, compact
  workbench density, restrained material, stage-native prose, top-shelf order,
  direct-drag Catalog behavior, reduced motion, solid surfaces, and high
  contrast.
- The visualization files live outside Git. Do not stage or commit them. Do not
  overwrite unrelated repository changes.

## Coverage Targets

| Family | Built-in definitions |
|---|---:|
| Story | 12 |
| Library and authoring | 19 |
| Story systems | 21 |
| Settings groups | 6 |
| Settings panels | 11 |
| Settings subwidgets | 22 |
| **Built-in total** | **91** |
| Dynamic extension examples | 3 |
| Embedded extension Inspector renderer | 1, not in Catalog |
| Evidence-backed non-Widget | Host session, not in Catalog |

## File Responsibility Map

### Staged and canonical mockup source

`sonder-workbench-calibration.html` owns:

- product-scoped CSS, responsive states, and Atmospheric Workbench composition;
- centralized sanitized SVG symbols and `ICON_DEFINITIONS` semantic mapping;
- `PANEL_TEMPLATES`, shipped Panels, and 91 built-in Widget definitions;
- mock extension registration and three representative dynamic definitions;
- ready-state blueprints, synthetic sample data, and state rendering;
- Catalog visual/compact results, direct placement, Widget chrome, menus,
  persistence, and selection/context state;
- a test-only `window.SonderWidgetMockup` inspection/state API when `?test` is
  present.

### Staged and canonical regression harness

`sonder-drag-regression.html` owns:

- the existing 55 Panel/Catalog/placement/persistence/drag cases;
- exact registry and inventory coverage assertions;
- icon provenance and accessible-control assertions;
- every-definition ready rendering and every-declared-state shell rendering;
- add/place/remove behavior across all supported shapes;
- extension disable/fault/retirement and embedded-renderer behavior;
- representative desktop, compact, phone, short-height, high-contrast, solid,
  reduced-motion, and 200%-zoom geometry checks.

### Design evidence

- `10_WIDGET_DESIGN_WORKBOOK.md` records implemented/reviewed state and artifact
  hashes only after live evidence exists.
- `11_ICON_SOURCE_AND_USAGE.md` remains the source/normalization contract.
- This plan records task completion checkboxes and verification commands.

---

### Task 1: Freeze Current State and Create Writable Staging

**Files:**
- Copy to staging: editable source, harness, and current preview.
- Read: `artifacts/minimal-ui-icons/manifest.json`.

**Interfaces:**
- Consumes: canonical source SHA
  `FE09FD5EC9837D2306F19D59D95C329793014AF4F19FA765F6C50D76D5D4BF99`
  and harness SHA
  `866C10D678DA95E974C94F9EC0691FE7112DF23AE3C51A079EA252ACA2F163A4`.
- Produces: byte-identical staged inputs and a recorded baseline result from
  the 55-case harness.

- [x] Copy the three canonical files into `widget-build-staging` with
  `Copy-Item -LiteralPath`, preserving filenames.
- [x] Verify source/harness hashes are unchanged in staging.
- [x] Load the canonical harness at
  `http://127.0.0.1:8765/sonder-drag-regression.html` and record the complete
  pass/fail result list.
- [x] Confirm the source reports `data-widget-definition-count="19"` after boot
  and the existing Catalog direct-drag cases pass.

### Task 2: Protect Full Inventory, Icon, and State Contracts in Tests

**Files:**
- Modify staged `sonder-drag-regression.html`.

**Interfaces:**
- Consumes: current same-origin iframe loader and `run(name, test, options)`.
- Produces: failing coverage tests requiring `builtInDefinitions`,
  `extensionDefinitions`, `iconDefinitions`, `renderState`, and
  `embeddedInspectorRenderers` from `window.SonderWidgetMockup`.

- [x] Replace the exact-19 test with exact counts: 91 built-ins, three dynamic
  extension examples, 94 Catalog definitions, one embedded renderer, and zero
  Host session definition.
- [x] Add a fixed-name test containing all 69 inventory names and a candidate
  test containing the 22 approved Settings subwidget names.
- [x] Add a unique-type test and category totals of Story 12, Library 19,
  Systems 21, Settings 39, and Extensions 3.
- [x] Add an icon test requiring every built-in definition and core action to
  resolve to SVG Repo id, filename, source URL, `CC0`, existing local manifest
  entry, and a rendered `<svg><use>` element with an accessible owner.
- [x] Add a state test iterating every definition's declared state ids through
  `renderState(type, stateId)` and asserting a title, visible state text,
  non-color-only marker, and no private/credential sample.
- [x] Add an all-definition placement test that creates each definition in a
  compatible test Panel, verifies one stable instance, removes it, and confirms
  Panel persistence stores only type/placement/configuration.
- [x] Freeze the prior 19-definition/55-case baseline before adding the new
  coverage; retain all unrelated legacy cases in the final 79-case harness.

### Task 3: Build the Real-SVG Icon Registry and Sprite

**Files:**
- Modify staged `sonder-workbench-calibration.html`.
- Read: `artifacts/minimal-ui-icons/*.svg` and `manifest.json`.

**Interfaces:**
- Produces:

  ```js
  const ICON_DEFINITIONS = Object.freeze({
    'action.close': { id: 511000, filename: '...', sourceUrl: '...', license: 'CC0', symbol: 'mi-511000' }
  });
  const createIcon = (key, { label = null, decorative = true, className = '' } = {}) => SVGElement;
  ```

- [x] Select a visually coherent collection SVG for every Widget identity and
  shared action/status semantic, preferring reuse over near-duplicate meanings.
- [x] Inspect selected SVGs at 12, 16, 18, 20, and 24 px; reject candidates that
  collapse, become ambiguous, or form weak opposing pairs.
- [x] Add a hidden inline symbol sprite preserving source viewBox/path geometry
  and using source-id symbol names.
- [x] Add `ICON_DEFINITIONS` entries with manifest provenance and a helper that
  creates `<svg><use>` without anonymous path copies.
- [x] Replace the current `▦`, `×`, plus/minus, arrows, overflow, drag, audio,
  and status glyphs in product chrome with mapped SVGs. Keep visible labels per
  the icon-versus-label contract.
- [x] Run icon tests and inspect all four themes plus solid/high-contrast modes.

### Task 4: Expand the Registry Schema and Register 91 Built-ins

**Files:**
- Modify staged `sonder-workbench-calibration.html` registry region.

**Interfaces:**
- Replaces positional `widgetDefinition(...)` with:

  ```js
  const widgetDefinition = ({
    id, name, category, context, role, shape, minColumns, multiplicity,
    purpose, keywords, icon, states, blueprint
  }) => Object.freeze({ ... });
  ```

- Produces: frozen `BUILT_IN_WIDGET_DEFINITIONS` with exact family totals and
  a merged read-only `WIDGET_DEFINITIONS` view.

- [x] Convert the current 19 entries to object manifests without changing their
  behavior or identifiers.
- [x] Correct audited identities/copy: Character Relationships is read-only;
  Dramatic Irony and Promise Ledger are subjective memory projections; World
  State normal editing is typed/read-only until safe; Persona Private History
  is primary-Persona only.
- [x] Add the remaining Story definitions to reach 12.
- [x] Add the remaining Library/authoring definitions to reach 19.
- [x] Add the remaining Story-system definitions to reach 21.
- [x] Add six Settings groups, eleven Settings panels, and 22 registered
  Settings subwidgets to reach 39 Settings definitions.
- [x] Keep Host session only as Maintenance content and assert it has no type.
- [x] Derive category counts and `root.dataset.widgetDefinitionCount` from the
  registry; do not hard-code counts in presentation code.
- [x] Run registry/name/count/search/category tests.

### Task 5: Add the Shared Widget Anatomy and Documented State Shell

**Files:**
- Modify staged `sonder-workbench-calibration.html` CSS and renderer regions.

**Interfaces:**
- Produces:

  ```js
  const renderWidgetReady = (definition, instance, mode) => HTMLElement;
  const renderWidgetState = (definition, stateId, mode) => HTMLElement;
  const setWidgetDemoState = (instanceId, stateId) => boolean;
  ```

- [x] Implement stage-native, Instrument, Module, and Workspace/editor anatomy
  with the existing 4 px workbench geometry and one scroll owner.
- [x] Add normalized state families: loading, empty, unavailable, access denied,
  stale, dirty, saving, conflict, review/confirmation, running/progress,
  partial/refused, success, offline, and error.
- [x] Preserve each definition's explicit state ids as manifest data and map
  them to the normalized shell plus definition-specific copy.
- [x] Add a mock-only state chooser to the Widget action menu. It must use an
  icon-plus-label entry, remain absent outside the mockup, and never persist as
  product data.
- [x] Ensure Catalog miniatures always render safe representative ready content;
  state exploration happens in placed/focused Widgets.
- [x] Run every-declared-state tests and verify focus/ARIA live announcements.

### Task 6: Build All 12 Story Widgets

**Files:**
- Modify staged source ready-blueprint data, renderers, and scoped CSS.

**Interfaces:**
- Produces distinctive ready renderers for Transcript, Composer, Story and
  Frame Context, Turn Progress, Live Technical Detail, Turn Versions, Turn
  Inspector, Player Condition, Cast Condition, Room Ambience, Scene Backdrop,
  and Background Work.

- [x] Preserve the rich Transcript, Composer, Character roster, World State,
  ambience, and Promise blueprints already used by Scene.
- [x] Implement visible-turn identity shared by Versions, Inspector, ambience,
  and backdrop without changing current-frame physiological Widgets.
- [x] Implement friendly Turn Progress separately from bounded technical detail.
- [x] Add version browsing plus separately labeled `Use` treatment.
- [x] Add Turn Inspector embedded extension-renderer region and stored-variant
  identity without making it a Catalog definition.
- [x] Add condition vitals, synthetic cast rows, backdrop continuity controls,
  and task rows with safe representative content.
- [x] Run Story count, ready-render, state, placement, and Scene-composition
  tests at desktop/phone/short-height sizes.

### Task 7: Build All 19 Library and Authoring Widgets

**Files:**
- Modify staged source ready-blueprint data, renderers, and scoped CSS.

**Interfaces:**
- Produces one bounded synthetic Library projection shared by filtered Library
  Widgets and selection channels for Character, Persona, Lorebook, and Lore
  entry workspaces.

- [x] Implement the Library plus Stories, Characters Library/Story, Personas
  Library/Story, Lore Library, and Lorebooks Story filtered projections.
- [x] Implement New Story, Character Card, Story Character Card, Persona Card,
  and Greetings/Quick Start workspaces with qualified draft indicators.
- [x] Implement Lore Entry Tree, Lore Entry Editor, Lorebook Details, Lore
  Relationships, and Lore Generator with distinct structural/authoring states.
- [x] Implement Lived-in Location Builder as the sole generation owner and link
  Institution widgets to it rather than duplicating controls.
- [x] Keep previews synthetic, bounded, and free of authored card/Lore text.
- [x] Run Library count, selection-following, no-selection, draft/conflict,
  compact staging, and placement tests.

### Task 8: Build All 21 Story-System Widgets

**Files:**
- Modify staged source ready-blueprint data, renderers, and scoped CSS.

**Interfaces:**
- Produces system-group renderers for cast/world, configuration ladders,
  institution evidence, private-memory projections, multiplayer, frames, and
  paradox/fixed-point authoring.

- [x] Implement Cast, Background Presences, World State, and Attire with typed
  owner boundaries and no raw replacement shortcut.
- [x] Implement Genre and Style, Dialogue and Agency, Off-screen Life, Living
  World, and Background Life/Scene Life with exact engine vocabulary.
- [x] Implement Institutions and Charter plus separate host-only Institution
  Diagnostics and Builder handoff.
- [x] Implement read-only Character Relationships, Memory Browser, Character
  and Persona Private History, Dramatic Irony, and subjective Promise Ledger.
- [x] Implement Multiplayer and Guest Invites, Frames, Who's Where, and Time
  Paradox/Fixed Points with consequence-labelled representative actions.
- [x] Run Systems count, privacy boundary, read-only authority, frame scope,
  state, placement, and responsive tests.

### Task 9: Build the Settings Hierarchy and 22 Subwidgets

**Files:**
- Modify staged source ready-blueprint data, renderers, and scoped CSS.

**Interfaces:**
- Produces summary-only group renderers, full panel renderers, and movable
  subwidget renderers bound to shared mock owner ids.

- [x] Build six summary/navigation groups with zero mutation or fetch behavior.
- [x] Build eleven canonical panels: Provider credentials, Model assignments,
  Theme, Reading & layout, Sound & motion, Accessibility, Content, Add-ons,
  Maintenance, Prompt editor, and Raw story data.
- [x] Build the seven provider/AI subwidgets and distinguish Story ambience/
  backdrop runtime owners from Settings configuration owners.
- [x] Build the seven appearance/content subwidgets with one device-preference
  owner and explicit active-Story Living World scope.
- [x] Build Installed extensions, Install extension, Sonder updates, Checkpoint
  storage, Memory-search repair, Diagnostics, Prompt preset/editor, and Raw
  clothing data.
- [x] Keep Host session as a labeled Maintenance section and never a Catalog
  result or draggable command.
- [x] Demonstrate shared owner ids, retained long drafts, one polling/task lease,
  secrets never read back, and read-only raw-clothing prerequisite state.
- [x] Run exact Settings counts, group-no-mutation, owner-sharing, secret/privacy,
  state, placement, and responsive tests.

### Task 10: Register and Render Extension Shapes

**Files:**
- Modify staged source registry, renderers, Catalog, and extension-state demo.

**Interfaces:**
- Produces:

  ```js
  registerExtensionWidget(ownerId, manifest) => unregister
  retireExtensionOwner(ownerId, reason) => void
  registerInspectorRenderer(ownerId, stepKey, renderer) => unregister
  ```

- [x] Register synthetic Atlas Campaign Clock, Trail Location Notes, and Mythic
  Settings examples through the owner-bound API after built-in boot.
- [x] Validate namespace, context, geometry, multiplicity, state schema,
  teardown, trust disclosure, and icon fallback before Catalog insertion.
- [x] Demonstrate enabled, disabled, schema-migration, fault, third-fault retired,
  unavailable placeholder, re-enabled, and removed states.
- [x] Render one extension step inside Turn Inspector and a safe host fallback
  when its owner is disabled; do not add the renderer to the Catalog.
- [x] Keep task-provider, notice, event, and legacy compatibility kinds outside
  the Widget registry.
- [x] Run extension counts, owner teardown, placeholder, fault isolation,
  embedded fallback, icon fallback, and placement tests.

### Task 11: Complete Catalog, Placement, Responsive, and Accessibility Parity

**Files:**
- Modify staged source Catalog/placement CSS and JavaScript.
- Modify staged harness.

**Interfaces:**
- Consumes: all 94 registered definitions and four presentation roles.
- Produces: equivalent visual/compact discovery and pointer/keyboard/touch
  placement for every eligible definition.

- [x] Verify search name/synonym coverage and exact category totals over all 94
  current definitions.
- [x] Preserve whole-miniature pointer lift, Space pickup, arrow target movement,
  Enter placement, Escape cancellation, and Catalog restoration.
- [x] Derive placement compatibility from shape/minimum geometry and keep
  focused-only/raw workspaces out of unsafe toolbar/phone float targets.
- [x] Verify singleton unavailable, repeatable-by-configuration, dynamic
  extension removal, Undo, reset, persistence migration, and missing-definition
  placeholders.
- [x] Review 1600x900, 1180x800, 1024x768, 768x1024, 430x932, 390x844,
  844x390, and 1024x600 plus 200% zoom.
- [x] Verify keyboard-only operation, 44 px touch targets, visible focus,
  reduced motion, solid surfaces, high contrast, long labels, no color-only
  state, and no horizontal document overflow.
- [x] Run the complete staged harness with zero failing rows (`79/79`).

### Task 12: Publish Verified Canonical Artifacts and Evidence

**Files:**
- Copy verified staged source/harness to canonical paths.
- Regenerate canonical preview.
- Modify: `docs/design/sonder-panels-and-widgets/10_WIDGET_DESIGN_WORKBOOK.md`.
- Update this plan's checkboxes.

**Interfaces:**
- Produces: canonical live source, preview, harness, hashes, and documented
  requirement-by-requirement evidence.

- [x] Copy source and harness only after the staged full harness passes.
- [x] Regenerate preview with the installed Visualize renderer; never hand-edit
  the preview.
- [x] Run the canonical harness fresh and inspect every result row for failure.
- [x] Compare canonical source and preview at all required viewports against the
  Atmospheric Workbench and Design Bible, recording approved differences.
- [x] Verify exact definition/state/icon coverage, no runtime network calls,
  source/preview size, no generated icon substitutes, and no retired navigation
  or Widget Shelf behavior.
- [x] Record source, preview, harness, and icon-selection hashes plus browser
  screenshots/review evidence in the workbook.
- [x] Run `git diff --check`, documentation link/placeholder/whitespace audits,
  and `git status -sb`; preserve unrelated repository changes.

## Plan Self-Review

- Spec coverage: all 69 fixed definitions, 22 registered Settings subwidgets,
  Host session disposition, three dynamic extension shapes, one embedded
  renderer, real SVG source, state rendering, placement, responsive,
  accessibility, and final evidence have explicit tasks.
- No placeholder work is delegated to an unnamed later phase.
- Type consistency: registry, icon, state, extension, and test interfaces are
  defined before dependent tasks use them.
- Execution choice: inline execution is required by the active collaboration
  constraints; this plan does not dispatch subagents.
