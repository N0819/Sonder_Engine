# Sonder Panels and Widget Catalog Mockup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking. Use `visualize:visualize` for the
> standalone artifact and `browser:control-in-app-browser` for live review.

**Goal:** Convert the standalone Atmospheric Workbench mockup into a functional
Panels prototype with editable global Panel tabs, three layout families, a
unified compact/expanded Widget Catalog, and a representative 19-Widget
skeleton registry.

**Architecture:** Keep the artifact self-contained in one HTML fragment. Add a
versioned mock-only Panel state model and Widget registry, render the three
shipped defaults from data, adapt the existing docking engine to registered
Widget instances, and drive both catalog presentations from the same registry
and filter state. Extend the existing iframe regression harness before each
behavioral increment; regenerate the localhost preview only after the harness
and live visual review pass.

**Tech Stack:** Standalone HTML fragment, product-scoped CSS, vanilla
JavaScript, native dialog/focus semantics, browser `localStorage` for mock-only
layout persistence, iframe/PointerEvent regression harness, Visualize renderer,
and in-app Chromium inspection.

**Spec:**
`docs/design/sonder-panels-and-widgets/README.md` and its linked design package.

## Global Constraints

- This plan changes only the standalone visualization source, its drag
  regression harness, and the generated preview. It does not change Sonder
  production routes, CSS, JavaScript, APIs, storage, or fingerprints.
- Editable source:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-workbench-calibration.html`.
- Regression harness:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-drag-regression.html`.
- Generated preview:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-workbench-calibration-preview.html`.
- Live URLs remain
  `http://127.0.0.1:8765/sonder-workbench-calibration.html` and
  `http://127.0.0.1:8765/sonder-drag-regression.html`.
- Panels are global across stories. Story-aware Widgets store no story id and
  strictly follow the mockup's one active story context.
- Scene, Library, and Settings are shipped editable Panel definitions, not
  hard-coded destinations or separate frontend products.
- The Panel tabs replace `.sonder-nav-cell`; the top shelf remains 40 px.
- The trailing **Widgets** launcher sits immediately before `.sonder-status`.
- One Widget registry drives default Panels, catalog cards, compact rows,
  placement compatibility, and skeleton rendering.
- The compact drawer overlays the Panel; it never changes Panel geometry or
  reading measure.
- The expanded catalog uses one contained modal layer over a dimmed and blurred
  background. It becomes full-screen at compact widths.
- Visual and Compact catalog modes expose the same definitions and Add actions.
- Dragging is optional. Add, Choose placement, keyboard, touch, and Widget
  actions remain complete routes.
- Existing drag behaviors remain: stable tab/shelf target ownership, invalid
  release restores origin, capacity is honest, and floating has no duplicate
  trailing ghost.
- The test query disables ordinary persisted state unless it supplies an
  explicit isolated persistence key.
- The fragment root remains `#sonder-calibration`; all custom selectors stay
  scoped below it.
- No network calls, `fetch`, XHR, WebSocket, external font binaries, or runtime
  application integration are added.
- Keep the editable fragment below 600 KB and the generated preview below
  750 KB.
- Preserve the existing atmospheric canvas, fixed transcript measure, 4 px
  material geometry, compact typography, reduced-motion support, and original
  user data in the repository's dirty worktree.
- The visualization files live outside Git. Execution checkpoints verify file
  content and behavior; they are not staged or committed.

## File Responsibility Map

### Editable artifact

`sonder-workbench-calibration.html` continues to own:

- product-scoped CSS and responsive states;
- top shelf and Panel-tab markup;
- reusable Panel surfaces, slots, docks, floating layer, dialogs, and catalog;
- `PANEL_TEMPLATES`, `SHIPPED_PANELS`, and `WIDGET_DEFINITIONS`;
- mock-only Panel persistence and migration;
- skeleton Widget rendering;
- catalog filtering, Visual/Compact rendering, and placement transition;
- current drag, tab, shelf, resize, float, and menu behavior.

Keep these responsibilities inside named regions of the existing style, markup,
and script rather than appending an unrelated second application below the
current one.

### Regression harness

`sonder-drag-regression.html` continues to own deterministic iframe loading,
pointer simulation, and pass/fail reporting. Extend it with Panel, catalog,
placement, persistence, responsive, and accessibility assertions. Preserve the
existing drag and capacity cases by updating their Widget ids after registry
migration.

### Generated preview

`sonder-workbench-calibration-preview.html` is generated from the editable
fragment after implementation. Never edit it directly.

## Skeleton Widget Set

The mockup registers exactly these 19 definitions in its first pass:

| ID | Name | Category | Context | Shape |
|---|---|---|---|---|
| `story.transcript` | Transcript | Story | active story/frame | wide stage |
| `story.composer` | Composer | Story | active story/frame | horizontal strip |
| `story.characters` | Characters (Story) | Story | active story | narrow roster |
| `story.turn-inspector` | Turn Inspector | Story | selected turn | wide inspector |
| `story.room-ambience` | Room Ambience | Story | active story/location | shallow strip |
| `library.workspace` | Library | Library | global with active-story filter | dominant workspace |
| `library.character-card` | Character Card | Library | selected Character | medium editor |
| `library.lore-entries` | Lore Entries | Library | selected Lorebook/entry | medium tree/editor |
| `systems.world-state` | World State | Systems | active story/frame | medium structural |
| `systems.living-world` | Living World | Systems | active story | medium controls |
| `systems.promise-ledger` | Promise Ledger | Systems | active story | narrow ledger |
| `systems.frames` | Frames | Systems | active story | medium timeline |
| `settings.provider-credentials` | Provider Credentials | Settings | global | medium/wide form |
| `settings.model-assignments` | Model Assignments | Settings | global | medium ledger |
| `settings.theme` | Theme | Settings | global/device | narrow/medium instrument |
| `settings.accessibility` | Accessibility | Settings | global/device | medium toggles |
| `settings.maintenance` | Maintenance | Settings | global | medium actions |
| `settings.prompt-editor` | Prompt Editor | Settings | global | wide editor |
| `extension.campaign` | Campaign | Extensions | extension-owned | medium workspace |

Default compositions:

- **Scene / `story-stage.v1`** — left: Characters (Story), Theme; center:
  Transcript, Composer; right: World State, plus a Room Ambience / Promise
  Ledger tab group.
- **Library / `focus-support.v1`** — dominant Library; supporting Character
  Card and Lore Entries.
- **Settings / `columns.v1` with three columns** — Provider Credentials, Model
  Assignments, Theme, Accessibility, Maintenance, and Prompt Editor.

Catalog-only until added: Turn Inspector, Living World, Frames, and Campaign.

---

### Task 1: Panel State and Top-Shelf Tabs

**Files:**
- Modify:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-drag-regression.html:16-219`
- Modify:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-workbench-calibration.html:206-335`
- Modify:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-workbench-calibration.html:2370-2379`
- Modify:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-workbench-calibration.html:2911-2933,3858-3864`

**Interfaces:**
- Consumes: existing 40 px top shelf, story lockup, status, and click event
  delegation.
- Produces: `PANEL_TEMPLATES`, `SHIPPED_PANELS`, `panelState`,
  `renderPanelTabs()`, `activatePanel(panelId)`, and the DOM contracts
  `[data-panel-tab]`, `[data-panel-create]`,
  `[data-widget-catalog-launcher]`, and `root.dataset.activePanel`.

- [ ] **Step 1: Add failing top-shelf and Panel-switch tests**

  Add two `run(...)` cases to the harness:

  ```js
  run('Top shelf exposes Panel tabs, New Panel, and trailing Widgets', async (doc) => {
    const tabs = Array.from(doc.querySelectorAll('[data-panel-tab]'));
    const create = doc.querySelector('[data-panel-create]');
    const widgets = doc.querySelector('[data-widget-catalog-launcher]');
    const status = doc.querySelector('.sonder-status');
    assert(tabs.map((tab) => tab.textContent.trim()).join(',') === 'Scene,Library,Settings', 'Shipped Panel tabs are not Scene, Library, Settings');
    assert(create?.getAttribute('aria-label') === 'Create Panel', 'New Panel control is missing');
    assert(widgets && status && widgets.nextElementSibling === status, 'Widgets is not immediately before status');
    assert(doc.querySelectorAll('.sonder-nav-cell').length === 0, 'Fixed destination cells still exist');
  }),
  run('Panel activation changes active identity without changing the story', async (doc) => {
    const root = doc.getElementById('sonder-calibration');
    const story = doc.querySelector('.sonder-story-lockup strong').textContent;
    doc.querySelector('[data-panel-tab="panel-library"]').click();
    assert(root.dataset.activePanel === 'panel-library', 'Library Panel did not activate');
    assert(doc.querySelector('[data-panel-tab="panel-library"]').getAttribute('aria-selected') === 'true', 'Active Panel tab is not selected');
    assert(doc.querySelector('.sonder-story-lockup strong').textContent === story, 'Panel switch changed active-story identity');
  }),
  ```

- [ ] **Step 2: Run the harness and verify the two tests fail**

  Open `http://127.0.0.1:8765/sonder-drag-regression.html` in the in-app
  browser. Expected: the two new tests fail because `[data-panel-tab]` and the
  Widgets launcher do not exist; the existing 14 regression cases retain their
  prior result.

- [ ] **Step 3: Define initial Panel data and render the top shelf**

  Replace the fixed `.sonder-nav-cell` markup with a tablist and controls:

  ```html
  <nav class="sonder-panel-tabs" role="tablist" aria-label="Panels" data-panel-tabs></nav>
  <button class="sonder-panel-create" type="button" data-panel-create aria-label="Create Panel">+</button>
  <div class="sonder-story-lockup">...</div>
  <button class="sonder-catalog-launcher" type="button" data-widget-catalog-launcher aria-expanded="false" aria-controls="sonder-widget-catalog">
    <span aria-hidden="true">▦</span><span>Widgets</span>
  </button>
  <div class="sonder-status" aria-live="polite">...</div>
  ```

  Introduce the state and rendering signatures:

  ```js
  const PANEL_TEMPLATES = Object.freeze({
    'story-stage.v1': { id: 'story-stage.v1', family: 'story-stage', label: 'Story stage' },
    'focus-support.v1': { id: 'focus-support.v1', family: 'focus-support', label: 'Focus + support' },
    'columns.v1': { id: 'columns.v1', family: 'columns', label: 'Columns', columnCounts: [2, 3, 4, 5, 6] }
  });

  const SHIPPED_PANELS = Object.freeze([
    { id: 'panel-scene', origin: 'shipped.scene', name: 'Scene', templateId: 'story-stage.v1', widgets: [] },
    { id: 'panel-library', origin: 'shipped.library', name: 'Library', templateId: 'focus-support.v1', widgets: [] },
    { id: 'panel-settings', origin: 'shipped.settings', name: 'Settings', templateId: 'columns.v1', columnCount: 3, widgets: [] }
  ]);

  let panelState = {
    schema: 'sonder.mock.panels.v1',
    revision: 0,
    activePanelId: 'panel-scene',
    panels: structuredClone(SHIPPED_PANELS)
  };

  const panelTabs = root.querySelector('[data-panel-tabs]');
  const renderPanelTabs = () => {
    panelTabs.replaceChildren();
    panelState.panels.forEach((panel) => {
      const selected = panel.id === panelState.activePanelId;
      const tab = document.createElement('button');
      tab.type = 'button';
      tab.className = 'sonder-panel-tab';
      tab.dataset.panelTab = panel.id;
      tab.setAttribute('role', 'tab');
      tab.setAttribute('aria-selected', String(selected));
      tab.setAttribute('aria-controls', 'sonder-active-panel');
      tab.tabIndex = selected ? 0 : -1;
      tab.textContent = panel.name;
      panelTabs.append(tab);
    });
  };
  const activatePanel = (panelId) => {
    if (!panelState.panels.some((panel) => panel.id === panelId)) return;
    panelState.activePanelId = panelId;
    root.dataset.activePanel = panelId;
    renderPanelTabs();
    renderActivePanel();
  };
  ```

  `renderPanelTabs()` creates `role="tab"`, `data-panel-tab`,
  `aria-selected`, and a stable `aria-controls` value. Use event delegation;
  remove the old nav-cell selection block.

- [ ] **Step 4: Style the tab strip without changing top-shelf height**

  Change the top-shelf grid to:

  ```css
  grid-template-columns: 188px minmax(220px, auto) auto minmax(0, 1fr) auto auto;
  ```

  Panel tabs share one connected material strip, support horizontal overflow,
  and retain visible focus. New Panel remains adjacent to the strip. Widgets
  uses an explicit label at desktop widths and does not resemble the New Panel
  plus.

- [ ] **Step 5: Run the harness and verify the new tests pass**

  Reload the regression URL. Expected: 16/16 pass and the title begins `PASS`.

- [ ] **Step 6: Record the external-file checkpoint**

  Run:

  ```powershell
  Get-Item -LiteralPath 'C:\Users\Keptin\.codex\visualizations\2026\08\25\01a036e9-bd28-7ed3-86aa-c5a8fc74599d\sonder-workbench-calibration.html' | Select-Object Length,LastWriteTime
  ```

  Do not stage or commit the visualization file.

### Task 2: New Panel Dialog and Layout Templates

**Files:**
- Modify:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-drag-regression.html:16-219`
- Modify:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-workbench-calibration.html:2111-2341`
  (dialog/template CSS)
- Modify:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-workbench-calibration.html:2509-2532`
  (transient-layer markup)
- Modify:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-workbench-calibration.html:2911-3235,3821-3870`
  (Panel lifecycle)

**Interfaces:**
- Consumes: `PANEL_TEMPLATES`, `panelState`, `renderPanelTabs()`, and
  `activatePanel()` from Task 1.
- Produces: `[data-panel-dialog]`, `openPanelDialog()`,
  `createPanel({ name, templateId, columnCount })`, `duplicatePanel(panelId)`,
  `renamePanel(panelId, name)`, and `deletePanel(panelId)`.

- [ ] **Step 1: Add failing creation and template tests**

  ```js
  run('New Panel creates a named three-column Panel and activates it', async (doc) => {
    doc.querySelector('[data-panel-create]').click();
    const dialog = doc.querySelector('[data-panel-dialog]');
    assert(dialog && !dialog.hidden, 'New Panel dialog did not open');
    dialog.querySelector('[data-panel-name]').value = 'Director Desk';
    dialog.querySelector('[data-template-choice="columns.v1"]').click();
    dialog.querySelector('[data-column-count="3"]').click();
    dialog.querySelector('[data-create-panel]').click();
    const active = doc.querySelector('[data-panel-tab][aria-selected="true"]');
    assert(active?.textContent.trim() === 'Director Desk', 'Created Panel did not become active');
    assert(doc.getElementById('sonder-calibration').dataset.panelTemplate === 'columns', 'Created Panel did not use column layout');
    assert(doc.getElementById('sonder-calibration').dataset.panelColumns === '3', 'Created Panel did not retain three columns');
  }),
  run('Panel dialog offers story stage, focus support, and two through six columns', async (doc) => {
    doc.querySelector('[data-panel-create]').click();
    const dialog = doc.querySelector('[data-panel-dialog]');
    assert(dialog.querySelector('[data-template-choice="story-stage.v1"]'), 'Story-stage template is absent');
    assert(dialog.querySelector('[data-template-choice="focus-support.v1"]'), 'Focus-support template is absent');
    const columns = Array.from(dialog.querySelectorAll('[data-column-count]')).map((item) => item.dataset.columnCount);
    assert(columns.join(',') === '2,3,4,5,6', `Column choices are ${columns.join(',')}`);
  }),
  ```

- [ ] **Step 2: Run the harness and verify both tests fail**

  Expected: 2 new failures naming the missing Panel dialog; the 16 prior tests
  retain their result.

- [ ] **Step 3: Add the native Panel dialog**

  Add one contained dialog with:

  - Name field;
  - three layout-family cards;
  - column-count row shown only for Columns;
  - Create and Cancel;
  - initial focus on Name;
  - Escape cancellation and launcher focus restoration.

  Use these lifecycle rules:

  ```js
  const nextPanelId = () => `panel-user-${crypto.randomUUID?.() || `${Date.now()}-${Math.random().toString(16).slice(2)}`}`;

  const createPanel = ({ name, templateId, columnCount = null }) => {
    const panel = {
      id: nextPanelId(),
      origin: null,
      name: String(name || 'Untitled Panel').trim().slice(0, 48) || 'Untitled Panel',
      templateId,
      ...(templateId === 'columns.v1' ? { columnCount: Number(columnCount) } : {}),
      widgets: []
    };
    panelState.panels.push(panel);
    panelState.revision += 1;
    activatePanel(panel.id);
    return panel;
  };
  ```

  `deletePanel()` refuses the last Panel. `duplicatePanel()` creates a new user
  Panel with copied configuration and new Panel/Widget instance ids.

- [ ] **Step 4: Add template surface classes**

  `renderActivePanel()` sets:

  ```js
  root.dataset.panelTemplate = PANEL_TEMPLATES[panel.templateId].family;
  root.dataset.panelColumns = panel.columnCount ? String(panel.columnCount) : '';
  ```

  Define `.sonder-panel-surface`, `.sonder-panel-zone`, and `.sonder-panel-slot`
  so an empty created Panel visibly demonstrates its selected geometry without
  exposing permanent edit outlines.

- [ ] **Step 5: Run the harness and verify 18/18 pass**

  Exercise Cancel once manually and verify focus returns to New Panel.

- [ ] **Step 6: Record the external-file checkpoint**

  Confirm the source remains below 600 KB. Do not edit the preview yet.

### Task 3: Widget Registry and Nineteen Skeleton Renderers

**Files:**
- Modify:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-drag-regression.html:16-219`
- Modify:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-workbench-calibration.html:336-1432,1577-2110`
  (Panel/Widget geometry)
- Modify:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-workbench-calibration.html:2381-2508`
  (replace static Widget bodies with render hosts)
- Modify:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-workbench-calibration.html:2911-3883`
  (registry, rendering, drag id migration)

**Interfaces:**
- Consumes: Panel definitions and layout surfaces from Tasks 1-2; existing
  `refreshGroup()`, `makeGroup()`, `normalizeDock()`, and drag engine.
- Produces: immutable `WIDGET_DEFINITIONS`, `widgetDefinition(type)`,
  `widgetFitsSlot(definition, slot)`,
  `createWidgetInstance(type, placement)`, `createWidgetModule(instance)`,
  `renderWidgetBody(type, body, instance)`, `renderActivePanel()`, and root
  attribute `data-widget-definition-count="19"`.

- [ ] **Step 1: Add failing registry/default-composition tests**

  Add three cases:

  ```js
  run('Skeleton registry exposes exactly nineteen definitions', async (doc) => {
    assert(doc.getElementById('sonder-calibration').dataset.widgetDefinitionCount === '19', 'Widget definition count is not nineteen');
  }),
  run('Scene default renders stage, strip, roster, system, and tabbed ledger Widgets', async (doc) => {
    const ids = ['story.transcript', 'story.composer', 'story.characters', 'settings.theme', 'systems.world-state', 'story.room-ambience', 'systems.promise-ledger'];
    ids.forEach((id) => assert(doc.querySelector(`[data-widget-type="${id}"]`), `${id} is missing from Scene`));
    const ambience = doc.querySelector('[data-widget-type="story.room-ambience"]');
    const promise = doc.querySelector('[data-widget-type="systems.promise-ledger"]');
    assert(ambience.closest('.sonder-widget-group') === promise.closest('.sonder-widget-group'), 'Room Ambience and Promise Ledger are not tabbed together');
  }),
  run('Library and Settings defaults render different Widget compositions', async (doc) => {
    doc.querySelector('[data-panel-tab="panel-library"]').click();
    assert(doc.querySelector('[data-widget-type="library.workspace"]'), 'Library workspace is absent');
    assert(doc.querySelector('[data-widget-type="library.character-card"]'), 'Character Card is absent');
    doc.querySelector('[data-panel-tab="panel-settings"]').click();
    assert(doc.querySelector('[data-widget-type="settings.provider-credentials"]'), 'Provider Credentials is absent');
    assert(doc.querySelector('[data-widget-type="settings.prompt-editor"]'), 'Prompt Editor is absent');
    assert(!doc.querySelector('[data-widget-type="story.transcript"]'), 'Scene Transcript leaked into Settings');
  }),
  ```

- [ ] **Step 2: Run the harness and verify three failures**

  Expected: registry-count and dynamic-composition assertions fail; the existing
  static Scene remains visible.

- [ ] **Step 3: Define the exact Widget metadata**

  Add one frozen array with all 19 entries:

  ```js
  const WIDGET_DEFINITIONS = Object.freeze([
    ['story.transcript', 'Transcript', 'story', 'active-story', 'stage', 2, 'single'],
    ['story.composer', 'Composer', 'story', 'active-story', 'strip', 2, 'single'],
    ['story.characters', 'Characters (Story)', 'story', 'active-story', 'narrow', 1, 'single'],
    ['story.turn-inspector', 'Turn Inspector', 'story', 'selected-turn', 'wide', 2, 'single'],
    ['story.room-ambience', 'Room Ambience', 'story', 'active-story', 'strip', 1, 'single'],
    ['library.workspace', 'Library', 'library', 'global-filtered', 'wide', 2, 'repeatable-config'],
    ['library.character-card', 'Character Card', 'library', 'selected-character', 'medium', 1, 'repeatable-config'],
    ['library.lore-entries', 'Lore Entries', 'library', 'selected-lore', 'medium', 1, 'repeatable-config'],
    ['systems.world-state', 'World State', 'systems', 'active-story', 'medium', 1, 'single'],
    ['systems.living-world', 'Living World', 'systems', 'active-story', 'medium', 1, 'single'],
    ['systems.promise-ledger', 'Promise Ledger', 'systems', 'active-story', 'narrow', 1, 'single'],
    ['systems.frames', 'Frames', 'systems', 'active-story', 'medium', 1, 'single'],
    ['settings.provider-credentials', 'Provider Credentials', 'settings', 'global', 'medium', 1, 'single'],
    ['settings.model-assignments', 'Model Assignments', 'settings', 'global', 'medium', 1, 'single'],
    ['settings.theme', 'Theme', 'settings', 'global-device', 'narrow', 1, 'single'],
    ['settings.accessibility', 'Accessibility', 'settings', 'global-device', 'medium', 1, 'single'],
    ['settings.maintenance', 'Maintenance', 'settings', 'global', 'medium', 1, 'single'],
    ['settings.prompt-editor', 'Prompt Editor', 'settings', 'global', 'wide', 2, 'single'],
    ['extension.campaign', 'Campaign', 'extensions', 'extension', 'medium', 1, 'single']
  ].map(([id, name, category, context, shape, minColumns, multiplicity]) => Object.freeze({
    id, name, category, context, shape, minColumns, multiplicity,
    keywords: `${name} ${category} ${context}`.toLowerCase()
  })));

  const widgetDefinition = (type) => WIDGET_DEFINITIONS.find((item) => item.id === type) || null;
  const widgetFitsSlot = (definition, slot) => {
    const columns = Number(slot.dataset.slotColumns || 1);
    const zone = slot.dataset.slotZone;
    if (columns < definition.minColumns) return false;
    if (definition.shape === 'stage' && !['stage-main', 'grid-main'].includes(zone)) return false;
    if (definition.shape === 'strip' && !['stage-composer', 'toolbar', 'grid'].includes(zone)) return false;
    return true;
  };
  root.dataset.widgetDefinitionCount = String(WIDGET_DEFINITIONS.length);
  ```

- [ ] **Step 4: Populate shipped Panel instance data**

  Give every instance a stable id distinct from its definition type. Use zone,
  group, order, active-tab, and optional span fields. Scene uses the exact
  default listed in this plan; Library and Settings use their listed defaults.

  ```js
  const instance = (id, type, zone, group, order, extra = {}) => ({
    id, type, zone, group, order, ...extra
  });

  const SHIPPED_PANEL_WIDGETS = Object.freeze({
    'panel-scene': [
      instance('scene-characters', 'story.characters', 'left-toolbar', 'scene-left-1', 0),
      instance('scene-theme', 'settings.theme', 'left-toolbar', 'scene-left-2', 1),
      instance('scene-transcript', 'story.transcript', 'stage-main', 'scene-main', 0),
      instance('scene-composer', 'story.composer', 'stage-composer', 'scene-composer', 0),
      instance('scene-world', 'systems.world-state', 'right-toolbar', 'scene-right-1', 0),
      instance('scene-ambience', 'story.room-ambience', 'right-toolbar', 'scene-right-2', 1, { active: true }),
      instance('scene-promises', 'systems.promise-ledger', 'right-toolbar', 'scene-right-2', 2)
    ],
    'panel-library': [
      instance('library-main', 'library.workspace', 'focus-main', 'library-main', 0, { span: 2 }),
      instance('library-character', 'library.character-card', 'support', 'library-support-1', 0),
      instance('library-lore', 'library.lore-entries', 'support', 'library-support-2', 1)
    ],
    'panel-settings': [
      instance('settings-providers', 'settings.provider-credentials', 'grid', 'settings-1', 0),
      instance('settings-models', 'settings.model-assignments', 'grid', 'settings-2', 1),
      instance('settings-theme', 'settings.theme', 'grid', 'settings-3', 2),
      instance('settings-accessibility', 'settings.accessibility', 'grid', 'settings-4', 3),
      instance('settings-maintenance', 'settings.maintenance', 'grid', 'settings-5', 4),
      instance('settings-prompts', 'settings.prompt-editor', 'grid', 'settings-6', 5, { span: 2 })
    ]
  });

  const createShippedPanels = () => structuredClone(SHIPPED_PANELS).map((panel) => ({
    ...panel,
    widgets: structuredClone(SHIPPED_PANEL_WIDGETS[panel.id] || [])
  }));

  panelState.panels = createShippedPanels();
  ```

- [ ] **Step 5: Implement all skeleton bodies**

  `renderWidgetBody()` dispatches to focused renderers:

  ```js
  const WIDGET_RENDERERS = Object.freeze({
    'story.transcript': renderTranscriptWidget,
    'story.composer': renderComposerWidget,
    'story.characters': renderCharactersWidget,
    'story.turn-inspector': renderTurnInspectorWidget,
    'story.room-ambience': renderAmbienceWidget,
    'library.workspace': renderLibraryWidget,
    'library.character-card': renderCharacterCardWidget,
    'library.lore-entries': renderLoreEntriesWidget,
    'systems.world-state': renderWorldStateWidget,
    'systems.living-world': renderLivingWorldWidget,
    'systems.promise-ledger': renderPromiseLedgerWidget,
    'systems.frames': renderFramesWidget,
    'settings.provider-credentials': renderProviderCredentialsWidget,
    'settings.model-assignments': renderModelAssignmentsWidget,
    'settings.theme': renderThemeWidget,
    'settings.accessibility': renderAccessibilityWidget,
    'settings.maintenance': renderMaintenanceWidget,
    'settings.prompt-editor': renderPromptEditorWidget,
    'extension.campaign': renderCampaignWidget
  });
  ```

  Use the existing story, theme, roster, effects, personas, and connection
  visual language where relevant. Each remaining renderer uses two to five
  representative controls/rows:

  - Turn Inspector: stage list and selected-stage technical excerpt;
  - Library: type/scope/search toolbar and four mixed resource rows;
  - Character Card: name, summary, active-story association, Edit;
  - Lore Entries: small tree and selected-entry excerpt;
  - World State: location, weather, time, structured Save affordance;
  - Living World: ceiling, consequence, obligation, and aftermath rows;
  - Promise Ledger: three chronological commitments and status;
  - Frames: Present/Past/Future rows plus Who's where summary;
  - Provider Credentials: two providers and connection state, no secret value;
  - Model Assignments: Default, Director, Mapping, and Narrator roles;
  - Accessibility: Solid surfaces, High contrast, Strong focus, Reduced motion;
  - Maintenance: updates, checkpoint storage, memory search, diagnostics;
  - Prompt Editor: preset tabs and a compact plain-text editor;
  - Campaign: extension badge, active campaign, objective, and extension owner.

  Transcript and Composer remain visually unboxed in ordinary mode while still
  exposing their Widget boundary and actions in Panel edit mode.

- [ ] **Step 6: Adapt legacy drag tests and selectors**

  Replace legacy ids consistently:

  ```text
  effects      -> systems.world-state
  personas     -> story.room-ambience
  connections  -> systems.promise-ledger
  characters   -> story.characters
  theme        -> settings.theme
  ```

  `data-widget-id` identifies the instance; `data-widget-type` identifies the
  definition. Update `widgetFor()` and action menus to use instance id while
  test selection uses type where instance identity is irrelevant.

- [ ] **Step 7: Run the harness and verify 21/21 pass**

  Confirm all 14 updated drag/capacity cases and seven Panel/registry cases pass.

- [ ] **Step 8: Inspect all three defaults at 1440 x 900**

  Switch Scene -> Library -> Settings. Verify the same story lockup remains,
  each composition is visibly distinct, and switching back restores Scene's
  exact dock/tab arrangement.

### Task 4: Compact Widget Catalog Drawer

**Files:**
- Modify:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-drag-regression.html:16-219`
- Modify:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-workbench-calibration.html:2111-2341`
  (catalog material)
- Modify:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-workbench-calibration.html:2513-2522`
  (replace Widget Shelf)
- Modify:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-workbench-calibration.html:2911-3235,3821-3870`
  (catalog state)

**Interfaces:**
- Consumes: `WIDGET_DEFINITIONS`, active Panel instance data, and the top-shelf
  launcher.
- Produces: `catalogState`, `openWidgetCatalog(options)`,
  `closeWidgetCatalog()`, `catalogResults()`, `renderWidgetCatalog()`, and DOM
  contracts `[data-widget-catalog]`, `[data-catalog-search]`,
  `[data-catalog-category]`, `[data-catalog-view]`, and
  `[data-catalog-result]`.

- [ ] **Step 1: Add failing drawer, filter, and compact-mode tests**

  ```js
  run('Widgets launcher opens the overlay drawer without resizing the Panel', async (doc) => {
    const surface = doc.querySelector('.sonder-panel-surface');
    const before = surface.getBoundingClientRect();
    doc.querySelector('[data-widget-catalog-launcher]').click();
    const drawer = doc.querySelector('[data-widget-catalog]');
    const after = surface.getBoundingClientRect();
    assert(drawer && !drawer.hidden && drawer.dataset.catalogPresentation === 'drawer', 'Catalog drawer did not open');
    assert(Math.abs(before.width - after.width) < 1, 'Catalog drawer resized the Panel');
  }),
  run('Catalog category and search use the same nineteen-definition registry', async (doc) => {
    doc.querySelector('[data-widget-catalog-launcher]').click();
    doc.querySelector('[data-catalog-category="settings"]').click();
    const categories = new Set(Array.from(doc.querySelectorAll('[data-catalog-result]')).map((item) => item.dataset.widgetCategory));
    assert(categories.size === 1 && categories.has('settings'), 'Settings filter returned another category');
    const search = doc.querySelector('[data-catalog-search]');
    search.value = 'prompt';
    search.dispatchEvent(new Event('input', { bubbles: true }));
    const ids = Array.from(doc.querySelectorAll('[data-catalog-result]')).map((item) => item.dataset.widgetType);
    assert(ids.join(',') === 'settings.prompt-editor', `Prompt search returned ${ids.join(',')}`);
  }),
  run('Compact mode renders names-first rows with Add actions', async (doc) => {
    doc.querySelector('[data-widget-catalog-launcher]').click();
    doc.querySelector('[data-catalog-view="compact"]').click();
    const row = doc.querySelector('[data-catalog-result]');
    assert(row?.classList.contains('is-compact'), 'Compact result row was not rendered');
    assert(row.querySelector('[data-catalog-add]'), 'Compact result has no Add action');
    assert(!row.querySelector('.sonder-catalog-preview'), 'Compact result retained visual preview');
  }),
  ```

- [ ] **Step 2: Run and verify three catalog failures**

  Expected: the three cases fail because the old Widget Shelf has no catalog
  state or filters.

- [ ] **Step 3: Replace Widget Shelf markup with one Catalog drawer**

  Add a fixed catalog header containing title, Expand, Close, search, Visual /
  Compact, and the six primary filters in this exact order:

  ```js
  const CATALOG_CATEGORIES = Object.freeze([
    ['all', 'All'], ['story', 'Story'], ['library', 'Library'],
    ['systems', 'Systems'], ['settings', 'Settings'], ['extensions', 'Extensions']
  ]);
  ```

  Add secondary filters Favorites, Recent, On this Panel, and Fits this layout.
  Use `settings.theme` and `library.workspace` as initial Favorites, and use
  `story.characters`, `systems.world-state`, and
  `settings.provider-credentials` as the initial Recent order. On this Panel is
  computed from the active Panel instances; Fits this layout is computed from
  current slots. All four utility filters operate on the same result array.

- [ ] **Step 4: Implement one filter pipeline**

  ```js
  const catalogState = {
    open: false,
    presentation: 'drawer',
    view: 'visual',
    category: 'all',
    query: '',
    utility: null,
    placementFilter: null,
    returnFocusId: null,
    favorites: new Set(['settings.theme', 'library.workspace']),
    recent: ['story.characters', 'systems.world-state', 'settings.provider-credentials']
  };

  const activePanelInstances = () => panelState.panels.find((panel) => panel.id === panelState.activePanelId)?.widgets || [];
  const activePanelHasType = (type) => activePanelInstances().some((item) => item.type === type);
  const widgetFitsFilter = (definition, filter) => filter.slots.some((slot) => widgetFitsSlot(definition, slot));

  const catalogResults = () => WIDGET_DEFINITIONS.filter((definition) => {
    if (catalogState.category !== 'all' && definition.category !== catalogState.category) return false;
    const needle = catalogState.query.trim().toLowerCase();
    if (needle && !`${definition.name} ${definition.keywords}`.toLowerCase().includes(needle)) return false;
    if (catalogState.utility === 'favorites' && !catalogState.favorites.has(definition.id)) return false;
    if (catalogState.utility === 'recent' && !catalogState.recent.includes(definition.id)) return false;
    if (catalogState.utility === 'on-panel' && !activePanelHasType(definition.id)) return false;
    if (catalogState.utility === 'fits-layout') {
      const slots = Array.from(root.querySelectorAll('[data-panel-slot]'));
      if (!slots.some((slot) => widgetFitsSlot(definition, slot))) return false;
    }
    if (catalogState.placementFilter && !widgetFitsFilter(definition, catalogState.placementFilter)) return false;
    return true;
  });
  ```

  Visual cards show preview, name, purpose, context, shape, current-Panel count,
  Favorite, Add, and Choose placement. Compact rows show icon/name, category,
  context, size, count, and Add.

- [ ] **Step 5: Implement drawer focus and close behavior**

  Opening focuses search. Escape closes the drawer and returns focus to the
  top-shelf launcher. Search clears on full close; category and view remain in
  `catalogState`.

- [ ] **Step 6: Run the harness and verify 24/24 pass**

  Manually confirm the drawer overlays the right edge and does not move prose,
  composer, columns, or docks.

### Task 5: Expanded Visual and Compact Catalog Browser

**Files:**
- Modify:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-drag-regression.html:16-219`
- Modify:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-workbench-calibration.html:2111-2341`
  (expanded/modal CSS)
- Modify:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-workbench-calibration.html:2513-2522`
  (shared catalog layer)
- Modify:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-workbench-calibration.html:2911-3235,3780-3865`
  (presentation/focus)

**Interfaces:**
- Consumes: catalog state, filters, and render pipeline from Task 4.
- Produces: `[data-catalog-expand]`,
  `setCatalogPresentation('drawer' | 'expanded')`, root class
  `.is-catalog-expanded`, contained expanded focus, and drawer return.

- [ ] **Step 1: Add failing expansion and parity tests**

  ```js
  run('Expand opens a near-full-screen browser and blurs the background', async (doc) => {
    doc.querySelector('[data-widget-catalog-launcher]').click();
    doc.querySelector('[data-catalog-expand]').click();
    const catalog = doc.querySelector('[data-widget-catalog]');
    const shell = doc.querySelector('.sonder-window');
    const rect = catalog.getBoundingClientRect();
    assert(catalog.dataset.catalogPresentation === 'expanded', 'Catalog did not expand');
    assert(rect.width >= shell.getBoundingClientRect().width * .88, 'Expanded catalog is not nearly full width');
    assert(doc.getElementById('sonder-calibration').classList.contains('is-catalog-expanded'), 'Background blur state is absent');
  }),
  run('Drawer and expanded browser expose identical filtered Widget ids', async (doc) => {
    doc.querySelector('[data-widget-catalog-launcher]').click();
    doc.querySelector('[data-catalog-category="systems"]').click();
    const drawerIds = Array.from(doc.querySelectorAll('[data-catalog-result]')).map((item) => item.dataset.widgetType).join(',');
    doc.querySelector('[data-catalog-expand]').click();
    const expandedIds = Array.from(doc.querySelectorAll('[data-catalog-result]')).map((item) => item.dataset.widgetType).join(',');
    assert(drawerIds === expandedIds, `Catalog presentations disagree: ${drawerIds} / ${expandedIds}`);
  }),
  ```

- [ ] **Step 2: Run and verify two failures**

  Expected: 2 failures because Expand and expanded geometry do not exist.

- [ ] **Step 3: Implement shared expanded presentation**

  Keep one catalog element and change its data attribute/class. Expanded width
  is `min(94vw, 1480px)` and height is `min(92vh, 980px)`. Use one dim/blur
  backdrop below the catalog and above the Panel. Do not clone filter controls
  or result DOM.

- [ ] **Step 4: Implement modal focus behavior**

  Use two focus sentinels or a bounded `keydown` handler to cycle Tab within the
  expanded catalog. Escape returns to drawer, preserving category, query, view,
  and result scroll. A second Escape closes the drawer.

- [ ] **Step 5: Run the harness and verify 26/26 pass**

  Review Visual and Compact at 1600 x 900 and 1024 x 768. Confirm the blurred
  background remains recognizable but cannot compete with catalog text.

### Task 6: Catalog Placement, Compatibility, and Existing Drag Integration

**Files:**
- Modify:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-drag-regression.html:16-219`
- Modify:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-workbench-calibration.html:1895-2110`
  (targets/proxy/edit state)
- Modify:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-workbench-calibration.html:2511-2532`
  (placement layer/menu)
- Modify:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-workbench-calibration.html:2934-3785,3821-3865`
  (placement engine)

**Interfaces:**
- Consumes: Widget metadata, `widgetFitsSlot()`, Panel slots, Catalog results,
  and existing
  `moveWidget()`, `beginDrag()`, `finishDrag()`, capacity, tab, float, and
  restore behavior.
- Produces: `findAutomaticPlacement(definition, panel)`, `addWidgetAuto(type)`,
  `beginCatalogPlacement(type, origin)`, `commitCatalogPlacement(target)`, and
  contextual catalog filters.

- [ ] **Step 1: Add four failing placement tests**

  ```js
  run('Add automatically places a compatible catalog-only Widget', async (doc) => {
    doc.querySelector('[data-widget-catalog-launcher]').click();
    doc.querySelector('[data-catalog-category="systems"]').click();
    doc.querySelector('[data-catalog-result][data-widget-type="systems.frames"] [data-catalog-add]').click();
    assert(doc.querySelector('[data-widget-type="systems.frames"]'), 'Frames was not placed');
    assert(doc.querySelector('[data-widget-announcement]').textContent.includes('Frames added'), 'Placement was not announced');
  }),
  run('Adding a Panel singleton twice preserves one instance', async (doc) => {
    doc.querySelector('[data-widget-catalog-launcher]').click();
    const add = doc.querySelector('[data-catalog-result][data-widget-type="systems.frames"] [data-catalog-add]');
    add.click();
    doc.querySelector('[data-widget-catalog-launcher]').click();
    doc.querySelector('[data-catalog-result][data-widget-type="systems.frames"] [data-catalog-add]')?.click();
    assert(doc.querySelectorAll('[data-widget-type="systems.frames"]').length === 1, 'Singleton Frames duplicated');
  }),
  run('Choose placement recedes the catalog and exposes compatible targets', async (doc) => {
    doc.querySelector('[data-widget-catalog-launcher]').click();
    doc.querySelector('[data-catalog-result][data-widget-type="story.turn-inspector"] [data-catalog-place]').click();
    assert(doc.getElementById('sonder-calibration').classList.contains('is-catalog-placing'), 'Placement mode did not begin');
    assert(doc.querySelectorAll('[data-placement-target]').length > 0, 'No compatible targets were exposed');
    doc.dispatchEvent(new doc.defaultView.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    assert(!doc.getElementById('sonder-calibration').classList.contains('is-catalog-placing'), 'Escape did not cancel placement');
  }),
  run('Empty slot opens the same Catalog with Fits this slot visible', async (doc) => {
    doc.querySelector('[data-panel-create]').click();
    const dialog = doc.querySelector('[data-panel-dialog]');
    dialog.querySelector('[data-panel-name]').value = 'Empty Columns';
    dialog.querySelector('[data-template-choice="columns.v1"]').click();
    dialog.querySelector('[data-column-count="2"]').click();
    dialog.querySelector('[data-create-panel]').click();
    doc.querySelector('[data-slot-add]').click();
    assert(doc.querySelector('[data-widget-catalog]').dataset.catalogFilter === 'slot', 'Slot filter was not applied');
    assert(doc.querySelector('[data-active-catalog-filter]').textContent.includes('Fits this slot'), 'Slot filter is not visible');
  }),
  ```

- [ ] **Step 2: Run and verify four failures**

  Expected: missing catalog Add/place handlers and slot filters.

- [ ] **Step 3: Add compatibility and automatic-placement functions**

  ```js
  const slotIsEmpty = (slot) => !slot.querySelector('[data-widget-id]');
  const slotAcceptsStack = (slot, definition) => {
    const group = slot.querySelector('.sonder-widget-group');
    if (!group || definition.shape === 'stage' || definition.shape === 'strip') return false;
    return Array.from(group.querySelectorAll('[data-widget-type]')).every((item) => item.dataset.widgetType !== definition.id);
  };

  const findAutomaticPlacement = (definition) => {
    const slots = Array.from(root.querySelectorAll('[data-panel-slot]'));
    return slots.find((slot) => slotIsEmpty(slot) && widgetFitsSlot(definition, slot))
      || slots.find((slot) => slotAcceptsStack(slot, definition));
  };
  ```

  Automatic placement never moves existing Widgets. When no target exists,
  preserve the catalog and display `Choose placement or make room on this
  Panel.`

- [ ] **Step 4: Integrate placed skeletons with the existing drag engine**

  A newly placed Widget uses `createWidgetModule()` and receives the same action
  menu, drag surface, tab behavior, float behavior, and invalid-drop recovery as
  default Widgets. Replace `Return to Widget Shelf` with `Remove from Panel` and
  add `Replace` and `Choose placement` commands.

- [ ] **Step 5: Implement explicit placement transition**

  Placement stores the catalog's presentation, filter, query, view, scroll, and
  initiating control id. The catalog recedes; compatible targets illuminate;
  confirmation places and offers Undo; Escape restores the catalog exactly.

- [ ] **Step 6: Update the legacy Widget Shelf capacity test**

  Replace the old storage/locate assertion with a Remove/Undo assertion while
  retaining destination-capacity coverage. Preserve all other drag regressions.

- [ ] **Step 7: Run the harness and verify 30/30 pass**

  Manually add Campaign to Settings, move it into a tab group, cancel one invalid
  drop, and confirm the original position is restored.

### Task 7: Persistence, Panel Menus, Reset Defaults, and Undo

**Files:**
- Modify:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-drag-regression.html:16-219`
- Modify:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-workbench-calibration.html:2111-2341`
  (Panel menu/Undo)
- Modify:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-workbench-calibration.html:2524-2532`
  (menus/notices)
- Modify:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-workbench-calibration.html:2911-3883`
  (serialize/hydrate/save)

**Interfaces:**
- Consumes: `panelState`, shipped definitions, dynamic Widget instances, and
  placement transactions.
- Produces: `PANEL_STORAGE_KEY`, `normalizePanelState(raw)`, `loadPanelState()`,
  `savePanelState()`, `serializeActivePanel()`, `hydratePanel(panel)`,
  `resetPanelToDefaults(panelId)`, `pushLayoutUndo(before, after)`, and
  `[data-panel-menu]`.

- [ ] **Step 1: Extend harness loading for isolated persistence**

  Change `loadWorkbench` to accept an options object:

  ```js
  const loadWorkbench = ({ height = 900, width = 1440, persistenceKey = '' } = {}) => new Promise((resolve, reject) => {
    const frame = document.createElement('iframe');
    frame.style.width = `${width}px`;
    frame.style.height = `${height}px`;
    const params = new URLSearchParams({ test: `${Date.now()}-${Math.random()}` });
    if (persistenceKey) params.set('persistence', persistenceKey);
    frame.src = `./sonder-workbench-calibration.html?${params}`;
    frame.addEventListener('load', async () => {
      try {
        frame.contentDocument.body.style.margin = '0';
        await nextFrame(frame.contentWindow);
        resolve(frame);
      } catch (error) {
        reject(error);
      }
    }, { once: true });
    document.body.append(frame);
  });
  ```

  Keep the existing wrapper compatible and pass the iframe to persistence
  tests:

  ```js
  const run = async (name, test, options = 900) => {
    const normalized = typeof options === 'number' ? { height: options } : options;
    const frame = await loadWorkbench(normalized);
    try {
      await test(frame.contentDocument, frame.contentWindow, frame);
      return { name, passed: true };
    } catch (error) {
      return { name, passed: false, error: error.message };
    } finally {
      if (normalized.persistenceKey) {
        frame.contentWindow.localStorage.removeItem(`sonder.mock.panels.v1.${normalized.persistenceKey}`);
      }
      frame.remove();
    }
  };

  const reloadWorkbench = (frame) => new Promise((resolve, reject) => {
    frame.addEventListener('load', async () => {
      try {
        frame.contentDocument.body.style.margin = '0';
        await nextFrame(frame.contentWindow);
        resolve(frame);
      } catch (error) {
        reject(error);
      }
    }, { once: true });
    frame.contentWindow.location.reload();
  });
  ```

- [ ] **Step 2: Add failing persistence, reset, and Undo tests**

  ```js
  run('A user Panel persists with its template and order', async (doc, view, frame) => {
    doc.querySelector('[data-panel-create]').click();
    const dialog = doc.querySelector('[data-panel-dialog]');
    dialog.querySelector('[data-panel-name]').value = 'Director Desk';
    dialog.querySelector('[data-template-choice="columns.v1"]').click();
    dialog.querySelector('[data-column-count="4"]').click();
    dialog.querySelector('[data-create-panel]').click();
    const createdId = doc.querySelector('[data-panel-tab][aria-selected="true"]').dataset.panelTab;
    await reloadWorkbench(frame);
    const reloaded = frame.contentDocument;
    const restored = reloaded.querySelector(`[data-panel-tab="${createdId}"]`);
    assert(restored?.textContent.trim() === 'Director Desk', 'User Panel did not return after reload');
    restored.click();
    assert(reloaded.getElementById('sonder-calibration').dataset.panelColumns === '4', 'Restored Panel lost its four-column template');
    assert(Array.from(reloaded.querySelectorAll('[data-panel-tab]')).at(-1) === restored, 'Restored Panel order changed');
  }, { persistenceKey: `panel-create-${Date.now()}-${Math.random()}` }),
  run('Reset Panel to Defaults restores Scene composition without changing story', async (doc, view) => {
    const story = doc.querySelector('.sonder-story-lockup strong').textContent;
    doc.querySelector('[data-widget-catalog-launcher]').click();
    doc.querySelector('[data-catalog-result][data-widget-type="systems.frames"] [data-catalog-add]').click();
    assert(doc.querySelector('[data-widget-type="systems.frames"]'), 'Frames was not added before reset');
    const sceneTab = doc.querySelector('[data-panel-tab="panel-scene"]');
    sceneTab.dispatchEvent(new view.MouseEvent('contextmenu', { bubbles: true, cancelable: true }));
    const reset = doc.querySelector('[data-panel-command="reset"]');
    assert(reset && !reset.hidden, 'Default Panel reset command is absent');
    reset.click();
    assert(!doc.querySelector('[data-widget-type="systems.frames"]'), 'Reset retained the added Frames Widget');
    assert(doc.querySelector('.sonder-story-lockup strong').textContent === story, 'Reset changed active story');
  }),
  run('Undo restores the exact removed Widget instance', async (doc) => {
    const world = doc.querySelector('[data-widget-type="systems.world-state"]');
    const instanceId = world.dataset.widgetId;
    const groupId = world.closest('.sonder-widget-group').dataset.widgetGroup;
    doc.querySelector(`[data-widget-actions="${instanceId}"]`).click();
    doc.querySelector('[data-widget-command="remove"]').click();
    assert(!doc.querySelector(`[data-widget-id="${instanceId}"]`), 'World State was not removed');
    doc.querySelector('[data-layout-undo]').click();
    const restored = doc.querySelector(`[data-widget-id="${instanceId}"]`);
    assert(restored, 'Undo did not restore World State');
    assert(restored.closest('.sonder-widget-group').dataset.widgetGroup === groupId, 'Undo changed the Widget group');
  }),
  ```

- [ ] **Step 3: Run and verify three failures**

  Expected: reloading loses state and reset/Undo controls are absent.

- [ ] **Step 4: Implement versioned mock persistence**

  ```js
  const params = new URLSearchParams(location.search);
  const explicitPersistenceKey = params.get('persistence');
  const PANEL_STORAGE_KEY = explicitPersistenceKey
    ? `sonder.mock.panels.v1.${explicitPersistenceKey}`
    : 'sonder.mock.panels.v1';
  const persistenceEnabled = !params.has('test') || Boolean(explicitPersistenceKey);

  const savePanelState = () => {
    if (!persistenceEnabled) return;
    localStorage.setItem(PANEL_STORAGE_KEY, JSON.stringify(panelState));
  };
  ```

  `normalizePanelState()` validates schema, ids, template ids, column range,
  Widget types, geometry bounds, and active Panel. Invalid data returns a fresh
  cloned shipped state and a visible recovery notice.

- [ ] **Step 5: Capture every valid layout mutation**

  Call one `commitPanelMutation(label, mutate)` boundary from Panel lifecycle,
  Add, explicit placement, drag finish, tab reorder, resize finish, float,
  replace, and remove. It captures before/after envelopes, increments revision,
  saves, announces, and publishes one Undo receipt.

- [ ] **Step 6: Add Panel menu and shipped reset**

  Right-click and an explicit Panel More control open the same menu. Default
  Panels show Rename, Duplicate, Reset Panel to Defaults. User Panels show
  Rename, Duplicate, Clear Widgets, Delete. Reset clones the current shipped
  definition and never changes story lockup, theme values, or skeleton content.

- [ ] **Step 7: Run the harness and verify 33/33 pass**

  Reload the direct mockup once without `?test`, verify layout persistence, then
  use Reset Defaults so the shared localhost preview returns to a deterministic
  Scene state.

### Task 8: Responsive, Keyboard, Focus, and Reduced-Motion Qualification

**Files:**
- Modify:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-drag-regression.html:16-219`
- Modify:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-workbench-calibration.html:1433-1667,2295-2341`
- Modify:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-workbench-calibration.html:2911-3883`

**Interfaces:**
- Consumes: Panel tabs, layout templates, catalog presentations, placement, and
  dialog/menu focus identities.
- Produces: compact Panel-tab overflow, full-screen compact Catalog, keyboard
  placement target navigation, focus restoration, and reduced-motion catalog /
  placement behavior.

- [ ] **Step 1: Add four failing responsive/accessibility tests**

  ```js
  run('Phone Catalog is full-screen and does not overflow horizontally', async (doc, view) => {
    const launcher = doc.querySelector('[data-widget-catalog-launcher]');
    assert(launcher && launcher.getBoundingClientRect().right <= view.innerWidth, 'Widgets launcher is unreachable');
    launcher.click();
    const rect = doc.querySelector('[data-widget-catalog]').getBoundingClientRect();
    assert(rect.left <= 1 && rect.right >= view.innerWidth - 1, 'Phone Catalog is not full-screen');
    assert(doc.documentElement.scrollWidth <= view.innerWidth + 1, 'Phone layout has horizontal document overflow');
  }, { width: 390, height: 844 }),
  run('Short-height expanded Catalog leaves useful result space', async (doc) => {
    doc.querySelector('[data-widget-catalog-launcher]').click();
    doc.querySelector('[data-catalog-expand]').click();
    const resultsRect = doc.querySelector('.sonder-catalog-results').getBoundingClientRect();
    assert(resultsRect.height >= 320, `Catalog results are only ${Math.round(resultsRect.height)}px tall`);
  }, { width: 1024, height: 600 }),
  run('Keyboard placement can select a target, confirm, and cancel', async (doc, view) => {
    doc.querySelector('[data-widget-catalog-launcher]').click();
    doc.querySelector('[data-catalog-result][data-widget-type="story.turn-inspector"] [data-catalog-place]').click();
    const firstTarget = doc.querySelector('[data-placement-target][tabindex="0"]');
    assert(firstTarget, 'Keyboard placement did not expose a focused target');
    doc.dispatchEvent(new view.KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
    const movedTarget = doc.activeElement;
    assert(movedTarget?.matches('[data-placement-target]'), 'ArrowRight did not move between placement targets');
    doc.dispatchEvent(new view.KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
    assert(doc.querySelector('[data-widget-type="story.turn-inspector"]'), 'Enter did not confirm placement');
    doc.querySelector('[data-widget-catalog-launcher]').click();
    doc.querySelector('[data-catalog-result][data-widget-type="extension.campaign"] [data-catalog-place]').click();
    doc.dispatchEvent(new view.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    assert(!doc.querySelector('[data-widget-type="extension.campaign"]'), 'Escape did not cancel Campaign placement');
    assert(doc.querySelector('[data-widget-announcement]').textContent.includes('cancelled'), 'Cancellation was not announced');
  }),
  run('Catalog focus returns through expanded, drawer, and launcher states', async (doc, view) => {
    const launcher = doc.querySelector('[data-widget-catalog-launcher]');
    launcher.click();
    doc.querySelector('[data-catalog-expand]').click();
    doc.dispatchEvent(new view.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    assert(doc.querySelector('[data-widget-catalog]').dataset.catalogPresentation === 'drawer', 'First Escape did not return to drawer');
    doc.dispatchEvent(new view.KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    assert(doc.querySelector('[data-widget-catalog]').hidden, 'Second Escape did not close drawer');
    assert(doc.activeElement === launcher, 'Focus did not return to Widgets launcher');
    const mediaRules = Array.from(doc.styleSheets).flatMap((sheet) => Array.from(sheet.cssRules || []));
    assert(mediaRules.some((rule) => String(rule.conditionText || '').includes('prefers-reduced-motion')), 'Reduced-motion catalog rules are absent');
  }),
  ```

- [ ] **Step 2: Run and verify four failures**

  Expected: compact catalog geometry and keyboard placement/focus assertions
  fail.

- [ ] **Step 3: Implement responsive staging**

  At `max-width: 860px`, close structured toolbars by default and stage them as
  overlays while preserving their Widget arrangement. At `max-width: 680px`,
  compact wordmark/story/status details, keep active Panel and Widgets
  identifiable, and make the Catalog full-screen. Do not introduce bottom
  navigation.

- [ ] **Step 4: Implement keyboard placement and menu parity**

  Placement state keeps an ordered compatible-target list and index:

  ```js
  const movePlacementFocus = (delta) => {
    if (!placementState?.targets.length) return;
    placementState.index = (placementState.index + delta + placementState.targets.length) % placementState.targets.length;
    const target = placementState.targets[placementState.index];
    target.focus();
    announceWidget(`${target.dataset.placementLabel}, ${placementState.index + 1} of ${placementState.targets.length}`);
  };
  ```

  Widget and Panel action menus expose every drag/contextmenu result without
  pointer precision.

- [ ] **Step 5: Complete focus and motion behavior**

  Store stable launcher/result ids rather than DOM references across rerenders.
  Under `prefers-reduced-motion: reduce`, remove catalog scale/slide, placement
  proxy interpolation, reflow animation, and blur transition while preserving
  final visibility and focus.

- [ ] **Step 6: Run the harness and verify 37/37 pass**

  Inspect the harness result list for zero failures rather than relying only on
  the document title.

### Task 9: Final Rendering and Visual Review

**Files:**
- Read/verify:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-workbench-calibration.html`
- Read/verify:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-drag-regression.html`
- Regenerate:
  `C:/Users/Keptin/.codex/visualizations/2026/08/25/01a036e9-bd28-7ed3-86aa-c5a8fc74599d/sonder-workbench-calibration-preview.html`

**Interfaces:**
- Consumes: complete behavior from Tasks 1-8.
- Produces: verified localhost mockup and generated preview with no production
  source changes.

- [ ] **Step 1: Run the complete regression harness fresh**

  Open `http://127.0.0.1:8765/sonder-drag-regression.html` and wait for
  completion. Expected: `37/37 passed`, title begins `PASS`, and no result row
  uses `.fail`.

- [ ] **Step 2: Review desktop states at 1600 x 900**

  Independently verify:

  - top shelf order: Sonder, Panel tabs, New Panel, story, Widgets, status;
  - Scene, Library, and Settings are visibly different editable layouts;
  - New Panel offers Story stage, Focus + support, and Columns 2-6;
  - right overlay drawer does not resize the Panel;
  - All/Story/Library/Systems/Settings/Extensions filters;
  - search and Visual/Compact results;
  - expanded catalog size, material, blur, and scroll ownership;
  - Add, Choose placement, contextual Fits this slot, cancel, and Undo;
  - Reset Panel to Defaults does not change active story;
  - every one of the 19 skeleton definitions is discoverable;
  - no legacy Widget Shelf or fixed destination cell remains.

- [ ] **Step 3: Review responsive states**

  Review at 1180 x 800, 1024 x 768, 768 x 1024, 430 x 932, 390 x 844,
  844 x 390, and 1024 x 600. Confirm no continuous overlap, unreachable
  launcher, clipped close control, horizontal document overflow, hidden Widget
  result, or composer obstruction.

- [ ] **Step 4: Review accessibility states**

  Exercise keyboard-only Panel tabs, catalog, filtering, Add, explicit
  placement, Widget menus, Panel context menu equivalent, dialogs, Escape,
  focus return, 200% zoom, reduced motion, solid surfaces, and high contrast.

- [ ] **Step 5: Regenerate the preview**

  Resolve the current bundled dependency paths with
  `codex_app__load_workspace_dependencies` if the cached paths have changed,
  then run the existing Visualize renderer:

  ```powershell
  C:\Users\Keptin\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe `
    C:\Users\Keptin\.codex\plugins\cache\openai-bundled\visualize\1.0.22\skills\visualize\scripts\render.py `
    C:\Users\Keptin\.codex\visualizations\2026\08\25\01a036e9-bd28-7ed3-86aa-c5a8fc74599d\sonder-workbench-calibration.html `
    C:\Users\Keptin\.codex\visualizations\2026\08\25\01a036e9-bd28-7ed3-86aa-c5a8fc74599d\sonder-workbench-calibration-preview.html
  ```

  Expected: exit zero and the preview path is printed.

- [ ] **Step 6: Verify artifact hygiene**

  Run:

  ```powershell
  $source = 'C:\Users\Keptin\.codex\visualizations\2026\08\25\01a036e9-bd28-7ed3-86aa-c5a8fc74599d\sonder-workbench-calibration.html'
  $preview = 'C:\Users\Keptin\.codex\visualizations\2026\08\25\01a036e9-bd28-7ed3-86aa-c5a8fc74599d\sonder-workbench-calibration-preview.html'
  $harness = 'C:\Users\Keptin\.codex\visualizations\2026\08\25\01a036e9-bd28-7ed3-86aa-c5a8fc74599d\sonder-drag-regression.html'
  if ((Get-Item -LiteralPath $source).Length -ge 600KB) { throw 'Editable source exceeds 600 KB' }
  if ((Get-Item -LiteralPath $preview).Length -ge 750KB) { throw 'Preview exceeds 750 KB' }
  if (Select-String -LiteralPath $source,$harness -Pattern 'fetch\(|XMLHttpRequest|WebSocket|window\.open') { throw 'External runtime call found' }
  if (Select-String -LiteralPath $source -Pattern 'sonder-nav-cell|Widget Shelf') { throw 'Retired fixed navigation or shelf copy remains' }
  ```

- [ ] **Step 7: Confirm repository scope**

  Run `git status -sb` in `F:/git/Sonder_Engine`. Expected: no mockup file is
  staged or tracked, and the pre-existing dirty repository files remain
  otherwise untouched. Report the live preview and harness URLs.
