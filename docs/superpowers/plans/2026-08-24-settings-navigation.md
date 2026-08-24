# Single-Method Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Settings overview-plus-anchor model with one grouped navigation and one real selected detail panel.

**Architecture:** Preserve the existing Settings routes and ownership, but resolve each grouped row to a panel key before rendering. The desktop rail and compact disclosures consume the same navigation projection; `#/settings` selects Theme, and no renderer calls `scrollIntoView()`.

**Tech Stack:** Browser JavaScript modules, layered CSS, Python/pytest, Playwright.

**Spec:** `docs/superpowers/specs/2026-08-24-ui-consistency-and-settings-design.md`

## Global Constraints

- Settings has one navigation method and one selected detail surface.
- `[data-settings-content]` is the only Settings vertical scroll owner.
- Existing Settings hashes, search aliases, persistence owners, and external destinations remain valid.
- Programmatic focus uses `{ preventScroll: true }`.
- Document and workspace scroll offsets remain zero.
- Compact controls retain 44 px touch targets.

---

### Task 1: Pin the single-method Settings contract

**Files:**
- Modify: `tests/test_ui_settings_contracts.py`
- Modify: `browser_tests/test_ui_settings_overview.py`
- Modify: `browser_tests/test_ui_settings.py`

**Interfaces:**
- Consumes: current `createSettingsView()` route and DOM contracts.
- Produces: failing regressions for one navigation model, real panels, and bounded scroll/focus.

- [ ] **Step 1: Replace the overview static contract**

Require the default route to resolve to Theme, forbid overview rendering, and
forbid the two ancestor-scrolling calls:

```python
def test_settings_uses_one_navigation_model_without_an_overview_surface():
    view = (ROOT / "static/js/ui-next/settings-view.js").read_text(encoding="utf-8")
    assert 'route.segments?.[0] || "experience"' in view
    assert 'data-settings-overview' not in view
    assert '"Settings overview"' not in view
    assert ".scrollIntoView(" not in view
    assert ".focus({ preventScroll: true })" in view
```

- [ ] **Step 2: Replace overview browser journeys with navigation journeys**

Keep the existing file temporarily to avoid a mechanical rename during the
behavioral red-green cycle. Replace its overview assertions with:

```python
def test_settings_entry_opens_one_grouped_navigation_and_theme_detail(page, ui_base_url):
    _open_settings(page, ui_base_url, route="#/settings")
    expect(page.get_by_role("navigation", name="Settings categories")).to_be_visible()
    expect(page.locator("[data-settings-overview]")).to_have_count(0)
    expect(page.get_by_role("link", name="Settings overview")).to_have_count(0)
    expect(page.get_by_role("link", name="Theme", exact=True)).to_have_attribute("aria-current", "page")
    expect(page.get_by_role("heading", name="Theme", level=2)).to_be_visible()
```

- [ ] **Step 3: Add the Accessibility route regression**

```python
def test_accessibility_is_a_real_panel_and_does_not_move_outer_scroll(page, ui_base_url):
    _open_settings(page, ui_base_url, route="#/settings/experience?control=accessibility")
    expect(page.get_by_role("heading", name="Accessibility", level=2)).to_be_visible()
    expect(page.get_by_text("Six restrained palettes.", exact=False)).to_have_count(0)
    state = page.evaluate("""() => ({
      document: document.documentElement.scrollTop,
      workspace: document.querySelector('.ui-shell__workspace').scrollTop,
      shellTop: document.querySelector('[data-settings-shell]').getBoundingClientRect().top,
      contentTop: document.querySelector('[data-settings-content]').scrollTop,
    })""")
    assert state == {"document": 0, "workspace": 0, "shellTop": 0, "contentTop": 0}
```

Extend `_open_settings()` with an optional `route` argument and use that value
as the requested hash. Keep its current default so existing callers remain
unchanged.

- [ ] **Step 4: Run the focused red gate**

Run:

```powershell
F:\git\Sonder_Engine\.venv\Scripts\python.exe -m pytest tests/test_ui_settings_contracts.py browser_tests/test_ui_settings_overview.py browser_tests/test_ui_settings.py::test_accessibility_is_a_real_panel_and_does_not_move_outer_scroll -q --basetemp=F:\git\Sonder_Engine\.tmp\settings-single-method-red
```

Expected: failures show that the overview still exists, Accessibility still
renders the complete Experience document, and the renderer still calls
`scrollIntoView()`.

### Task 2: Resolve routes to real Settings panels

**Files:**
- Modify: `static/js/ui-next/settings-view.js`
- Modify: `static/js/ui-next/settings-overview.js`

**Interfaces:**
- Consumes: `SETTINGS_OVERVIEW_GROUPS`, existing Settings routes, current rendering helpers.
- Produces: `settingsPanelKey(active, route) -> string` and one panel renderer per grouped Settings row.

- [ ] **Step 1: Rename the projection semantics without changing routes**

Within `settings-overview.js`, export the same immutable group data under the
navigation name and keep summaries as navigation metadata:

```javascript
export const SETTINGS_NAVIGATION_GROUPS = Object.freeze([/* existing ordered groups */]);

export function projectSettingsNavigation(input = {}) {
  return SETTINGS_NAVIGATION_GROUPS.map(group => ({
    ...group,
    rows: group.rows.map(row => ({ ...row, ...rowProjection(row.id, input) })),
  }));
}
```

Remove `renderSettingsOverview`; no code renders a dashboard ledger.

- [ ] **Step 2: Add a deterministic panel resolver**

Add beside `activeNavigationRow`:

```javascript
function settingsPanelKey(active, route) {
  if (active === "experience") {
    return {
      themes: "theme",
      reading: "reading",
      sound: "sound",
      accessibility: "accessibility",
    }[String(route.query?.control || "themes")] || "theme";
  }
  if (active === "ai-connections") {
    return route.query?.control === "models" ? "model-assignments" : "ai-connections";
  }
  if (active === "advanced") {
    return route.query?.tool === "story-data" ? "raw-story-data" : "prompt-editor";
  }
  return active;
}
```

Make `activeNavigationRow()` return this key for every internal Settings row.

- [ ] **Step 3: Split the Experience renderer by selected panel**

Change the current `experience(documentRef, services)` builder so it accepts a
panel key and appends only the selected group. Give each panel its own heading:

```javascript
function experience(documentRef, services, panelKey) {
  const panels = {
    theme: () => renderThemePanel(documentRef, services),
    reading: () => renderReadingPanel(documentRef, services),
    sound: () => renderSoundPanel(documentRef, services),
    accessibility: () => renderAccessibilityPanel(documentRef, services),
  };
  return panels[panelKey]?.() || panels.theme();
}
```

Retain the existing controls and event handlers inside the corresponding
panel builder. Place the cross-Experience reset inside Accessibility.

- [ ] **Step 4: Split AI and Advanced selected content**

Add a `panelKey` parameter to `aiConnections()` and `advanced()` and append
only the requested primary task. AI Connections retains provider/default
configuration; Model assignments retains its assignment disclosure and
supporting model selectors. Prompt editor and Raw story data each render their
own launcher/editor surface.

- [ ] **Step 5: Remove the overview branch from `createSettingsView()`**

Resolve the default to Experience/Theme and always render navigation plus one
detail:

```javascript
const requested = route.segments?.[0] || "experience";
const active = CATEGORIES.some(([id]) => id === requested) ? requested : "experience";
const panelKey = settingsPanelKey(active, route);
const groups = settingsNavigationGroups(documentRef, services, state);
const nav = categoryNav(documentRef, services, active, route, groups);
content.append(renderSettingsPanel(documentRef, services, state, active, panelKey, route));
body.append(nav, content);
```

Delete the `isOverview` branch and the overview-only focus restoration.

- [ ] **Step 6: Run the focused green gate**

Run the Task 1 command. Expected: all selected tests pass.

### Task 3: Make Settings scrolling and responsive navigation bounded

**Files:**
- Modify: `static/js/ui-next/settings-view.js`
- Modify: `static/css/ui/settings.css`
- Modify: `browser_tests/test_ui_settings.py`

**Interfaces:**
- Consumes: one selected detail panel and grouped navigation.
- Produces: one vertical owner at every supported viewport and a non-scrolling focus path.

- [ ] **Step 1: Replace ancestor scrolling with direct bounded state**

Delete both `scrollIntoView()` calls. On route mount, set the content offset
directly and focus the panel heading without scrolling:

```javascript
requestAnimationFrame(() => {
  content.scrollTop = 0;
  content.querySelector(".ui-settings__section-head h2")?.focus({ preventScroll: true });
});
```

Give the selected heading `tabIndex = -1`. Do not move focus during ordinary
pointer navigation when that would surprise the user; preserve the router's
input modality behavior if already available.

- [ ] **Step 2: Remove the desktop navigation scroll owner**

Set ordinary `.ui-settings__categories` to `overflow: clip`. At wide
short-height viewports, enable the same single-open group behavior used by
compact disclosures while leaving the rail in its grid column. At 1099 px and
below, continue moving navigation inside `[data-settings-content]`, where it
shares the sole scroll owner.

- [ ] **Step 3: Expand the one-owner browser matrix**

For 1440x900, 1024x600, 390x844, 844x390, and a 720 px-high wide viewport,
assert:

```python
scroll_state = page.evaluate("""() => ({
  detail: document.querySelector('[data-settings-content]').scrollTop,
  navOverflow: getComputedStyle(document.querySelector('[data-settings-categories]')).overflowY,
  workspace: document.querySelector('.ui-shell__workspace').scrollTop,
  document: document.documentElement.scrollTop,
})""")
assert scroll_state["workspace"] == 0
assert scroll_state["document"] == 0
assert scroll_state["navOverflow"] not in {"auto", "scroll"}
```

- [ ] **Step 4: Run Settings browser coverage**

Run:

```powershell
F:\git\Sonder_Engine\.venv\Scripts\python.exe -m pytest browser_tests/test_ui_settings.py browser_tests/test_ui_settings_overview.py -q --basetemp=F:\git\Sonder_Engine\.tmp\settings-single-method-green
```

Expected: all tests pass at every viewport.

### Task 4: Reconcile Settings documentation and commit

**Files:**
- Modify: `docs/guides/INTERFACE.md`
- Modify: `docs/design/sonder-ui-replacement/UI_CLEANUP_FIX_LIST.md`
- Modify: `browser_tests/test_ui_settings_overview.py`
- Modify: `tools/capture_ui_settings_overview.py`

**Interfaces:**
- Consumes: verified one-method Settings implementation.
- Produces: maintained authority and evidence tooling that no longer claim an overview surface exists.

- [ ] **Step 1: Update maintained guidance**

Replace the scan-first overview contract with the grouped-navigation and
real-panel rules from the spec. Record the root cause: row-level navigation
was layered over category-level documents and used ancestor-scrolling anchors.

- [ ] **Step 2: Rename test and capture semantics in content**

Retain filenames until the final release reconciliation if a rename would add
unrelated churn, but change module docstrings, function names, screenshot
labels, and assertions from overview to navigation/detail terminology.

- [ ] **Step 3: Run documentation and Settings contracts**

```powershell
F:\git\Sonder_Engine\.venv\Scripts\python.exe -m pytest tests/test_ui_settings_contracts.py browser_tests/test_ui_settings.py browser_tests/test_ui_settings_overview.py -q --basetemp=F:\git\Sonder_Engine\.tmp\settings-contract-green
```

- [ ] **Step 4: Commit the Settings unit**

```powershell
git add static/js/ui-next/settings-view.js static/js/ui-next/settings-overview.js static/css/ui/settings.css tests/test_ui_settings_contracts.py browser_tests/test_ui_settings.py browser_tests/test_ui_settings_overview.py docs/guides/INTERFACE.md docs/design/sonder-ui-replacement/UI_CLEANUP_FIX_LIST.md tools/capture_ui_settings_overview.py
git commit -m "fix(settings): use one navigation model"
```
