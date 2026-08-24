# Inspector and Library Actions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make contextual-panel sizing destination-owned, remove the closed Library gap, and turn the story ellipsis into a contained row-action menu.

**Architecture:** The inspector host derives an inspector kind from the current route and stores Story Tools sizing independently from Library details. Shell grid allocation keys on actual open state. The merged Library row becomes a visual container with sibling selection and More controls, using the existing overlay controller for an anchored menu.

**Tech Stack:** Browser JavaScript modules, CSS grid/container queries, Playwright.

**Spec:** `docs/superpowers/specs/2026-08-24-ui-consistency-and-settings-design.md`

## Global Constraints

- Begin from the integrated Library single-workspace commit.
- Do not reintroduce a Library sub-sidebar or duplicate ledger.
- Story Tools retains 352/232/80 px expanded/compact/rail modes.
- Library details remains text-safe and never inherits rail mode.
- Closing a contextual panel removes its grid track immediately.
- More does not select the row or mutate the route.
- More retains an accessible 44 px hit target and visible focus.

---

### Task 1: Pin destination-owned inspector geometry

**Files:**
- Modify: `browser_tests/test_ui_shell.py`
- Modify: `browser_tests/test_ui_library.py`
- Modify: `browser_tests/test_ui_story_tools.py`
- Modify: `tests/test_ui_shell_contracts.py`

**Interfaces:**
- Consumes: current inspector host state and merged Library selection flow.
- Produces: failing width, resize-visibility, preference-restoration, and close-track regressions.

- [ ] **Step 1: Add Library width and rail-isolation coverage**

```python
def test_library_details_never_inherits_story_tools_rail(page, ui_base_url):
    # Put Story Tools in rail mode, navigate to Library, then select a story.
    inspector = page.locator("[data-shell-inspector]")
    expect(page.locator("html")).to_have_attribute("data-inspector-kind", "library-details")
    assert 320 <= inspector.bounding_box()["width"] <= 420
    expect(inspector.get_by_role("button", name="Resize Story Tools")).to_have_count(0)
```

- [ ] **Step 2: Add close-track coverage**

```python
def test_closing_library_details_removes_the_grid_track(page, ui_base_url):
    # Select a story, record open geometry, click Close, then measure again.
    page.get_by_role("button", name="Close Library details").click()
    expect(page.locator("html")).to_have_attribute("data-inspector-open", "false")
    assert page.locator("[data-shell-inspector]").bounding_box() is None
    columns = page.locator(".ui-shell").evaluate("node => getComputedStyle(node).gridTemplateColumns")
    assert len(columns.split()) == 2
```

- [ ] **Step 3: Add Story Tools preference restoration coverage**

Set compact, visit Library details, return to Play, and assert the Story Tools
inspector returns to 232 px and exposes its resize control.

- [ ] **Step 4: Run the inspector red gate**

```powershell
F:\git\Sonder_Engine\.venv\Scripts\python.exe -m pytest browser_tests/test_ui_shell.py browser_tests/test_ui_library.py browser_tests/test_ui_story_tools.py tests/test_ui_shell_contracts.py -q --basetemp=F:\git\Sonder_Engine\.tmp\inspector-kind-red
```

### Task 2: Implement inspector kinds and actual-open layout ownership

**Files:**
- Modify: `static/js/ui-next/inspector-host.js`
- Modify: `static/js/ui-next/shell.js`
- Modify: `static/css/ui/shell.css`
- Modify: `static/css/ui/story-tools.css`

**Interfaces:**
- Consumes: the inspector host's current route and pane state.
- Produces: `data-inspector-kind`, Story Tools-only size preference, and grid selectors gated by `data-inspector-open="true"`.

- [ ] **Step 1: Derive inspector kind in one host function**

```javascript
function inspectorKind(route) {
  if (route?.destination === "play") return "story-tools";
  if (route?.destination === "library") return "library-context";
  return "none";
}
```

Stamp the result on `documentElement.dataset.inspectorKind` during render and
clear it during teardown. The current route query remains authoritative for
which Library detail or authoring panel is mounted; do not introduce a second
selection field in store state.

- [ ] **Step 2: Restrict resizing to Story Tools**

Read and write the existing expanded/compact/rail preference only when
`inspectorKind(route) === "story-tools"`. Hide the resize control for all
other kinds. Library details uses its fixed semantic profile.

- [ ] **Step 3: Gate grid columns on actual open state**

Every Library three-column selector must include both:

```css
:root[data-destination="library"][data-inspector-open="true"][data-inspector-kind="library-context"]
```

Set its inspector token to 352 px with a 320 px minimum where the available
space permits. Keep existing sheet staging at compact breakpoints.

- [ ] **Step 4: Make close atomically clear presentation state**

The close handler clears the Library selection presentation and inspector-open
state in the same synchronous event turn before route/state follow-up work.
Do not leave `data-library-selection="true"` as an independent grid trigger.

- [ ] **Step 5: Run the inspector green gate**

Run the Task 1 command. Expected: all tests pass.

### Task 3: Pin the contained story More interaction

**Files:**
- Modify: `browser_tests/test_ui_library.py`
- Modify: `tests/test_ui_library_contracts.py`

**Interfaces:**
- Consumes: merged single-workspace story ledger.
- Produces: failing containment, event-isolation, keyboard, and focus-return contracts.

- [ ] **Step 1: Add DOM and geometry assertions**

```python
row = page.locator('[data-library-row="story"]').first
more = row.get_by_role("button", name="Story actions")
row_box, more_box = row.bounding_box(), more.bounding_box()
assert more_box["x"] >= row_box["x"]
assert more_box["x"] + more_box["width"] <= row_box["x"] + row_box["width"]
assert more_box["width"] >= 44 and more_box["height"] >= 44
assert more.evaluate("node => getComputedStyle(node).borderStyle") == "none"
```

- [ ] **Step 2: Add event-isolation assertions**

Click More and assert the action menu opens while the current route,
selection id, and Library details visibility remain unchanged. Press Escape
and assert the menu closes and More regains focus. Repeat with keyboard Enter.

- [ ] **Step 3: Run the row-action red gate**

```powershell
F:\git\Sonder_Engine\.venv\Scripts\python.exe -m pytest browser_tests/test_ui_library.py tests/test_ui_library_contracts.py -q --basetemp=F:\git\Sonder_Engine\.tmp\library-more-red
```

### Task 4: Implement the contained action menu

**Files:**
- Modify: `static/js/ui-next/library-view.js`
- Modify: `static/css/ui/library.css`
- Modify: `static/js/ui-next/library-runtime.js` only if an existing action lacks a public runtime method

**Interfaces:**
- Consumes: existing `createOverlayController` and authoritative story operations.
- Produces: sibling row controls and an anchored menu that never invokes selection as a side effect.

- [ ] **Step 1: Make the visual row the container**

Render the list item as the bordered/radius-owning card. Append a primary
selection button and a trailing More button as siblings. The primary button
keeps the current select/open behavior.

- [ ] **Step 2: Open a menu from More without propagation**

```javascript
more.addEventListener("click", event => {
  event.preventDefault();
  event.stopPropagation();
  openStoryActions({ anchor: more, item, services });
});
```

Build the menu with the shared overlay controller. Use existing story actions
only; unavailable actions are omitted or disabled according to their current
authority.

- [ ] **Step 3: Apply bare-icon presentation**

Remove visible background and border from More. Keep it 44x44, align it inside
the card padding, preserve the standard focus ring, and give the row outer
frame `var(--ui-radius-md)` with clipped internal paint.

- [ ] **Step 4: Run the row-action green gate**

Run the Task 3 command. Expected: all tests pass.

### Task 5: Reconcile inspector documentation and commit

**Files:**
- Modify: `docs/guides/INTERFACE.md`
- Modify: `docs/design/sonder-ui-replacement/UI_CLEANUP_FIX_LIST.md`
- Modify: affected browser capture tooling

**Interfaces:**
- Consumes: verified inspector and row-action behavior.
- Produces: maintained destination-owned presentation contract and responsive evidence.

- [ ] **Step 1: Update the inspector ownership contract**

Document that expanded/compact/rail are Story Tools modes, Library details is
text-safe and non-resizable, compact Library details stages as a sheet, and
grid allocation requires actual open state.

- [ ] **Step 2: Record the row-action contract**

Document sibling controls, contained geometry, no selection side effect, and
keyboard/focus behavior.

- [ ] **Step 3: Run affected browser suites**

```powershell
F:\git\Sonder_Engine\.venv\Scripts\python.exe -m pytest browser_tests/test_ui_library.py browser_tests/test_ui_library_authoring.py browser_tests/test_ui_shell.py browser_tests/test_ui_story_tools.py browser_tests/test_ui_play.py -q --basetemp=F:\git\Sonder_Engine\.tmp\inspector-library-green
```

- [ ] **Step 4: Commit the inspector unit**

```powershell
git add static/js/ui-next/inspector-host.js static/js/ui-next/shell.js static/js/ui-next/library-view.js static/js/ui-next/library-runtime.js static/css/ui/shell.css static/css/ui/story-tools.css static/css/ui/library.css browser_tests tests docs/guides/INTERFACE.md docs/design/sonder-ui-replacement/UI_CLEANUP_FIX_LIST.md
git commit -m "fix(ui): make inspectors destination-owned"
```
