# Typography and Soft Geometry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce the formal small-interface type scale and eliminate unapproved hard-edged free-standing surfaces across the UI.

**Architecture:** Define semantic typography and bevel tokens once, migrate component CSS to them, and enforce conformance through static and rendered-browser audits. Structural internal seams remain square only when their containing outer frame owns the radius.

**Tech Stack:** Layered CSS custom properties, Python static contracts, Playwright computed-style audits.

**Spec:** `docs/superpowers/specs/2026-08-24-ui-consistency-and-settings-design.md`

## Global Constraints

- Interface body text is 14/20 by default.
- Controls, metadata, micro labels, sections, pages, and display text use the exact Design Bible scale.
- Story prose remains independent through `--ui-prose-size`.
- Large UI increases semantic type and control tokens together.
- Free-standing framed surfaces use 3 px, 4 px, or 5 px radii; 4 px is the default.
- Viewport-flush panes and internal shared edges may remain square.
- Literal clipped-corner chamfers are not the default geometry.

---

### Task 1: Pin semantic typography tokens

**Files:**
- Modify: `tests/test_ui_next_entry.py`
- Modify: `browser_tests/test_ui_foundation.py`
- Modify: `static/css/ui/tokens.css`
- Modify: `static/css/ui/typography.css`

**Interfaces:**
- Consumes: current CSS token layer and appearance attributes.
- Produces: `--ui-text-*` and `--ui-leading-*` tokens plus verified default and Large UI computed sizes.

- [ ] **Step 1: Add a failing static token contract**

```python
def test_formal_interface_type_scale_is_tokenized():
    css = (ROOT / "static/css/ui/tokens.css").read_text(encoding="utf-8")
    for declaration in (
        "--ui-text-micro: 11px", "--ui-leading-micro: 14px",
        "--ui-text-meta: 12px", "--ui-leading-meta: 16px",
        "--ui-text-control: 13px", "--ui-leading-control: 18px",
        "--ui-text-body: 14px", "--ui-leading-body: 20px",
        "--ui-text-section: 16px", "--ui-leading-section: 22px",
        "--ui-text-page: 21px", "--ui-leading-page: 28px",
        "--ui-text-display: 28px", "--ui-leading-display: 36px",
    ):
        assert declaration in css
```

- [ ] **Step 2: Add a failing browser scale contract**

Render representative body, control, metadata, section, page, display, and
prose nodes in the component lab. Assert computed size/line-height pairs and
then enable `data-a11y-large-ui="true"` to assert every interface role grows
while prose remains at its selected size.

- [ ] **Step 3: Define the tokens and semantic classes**

Add the exact scale to `tokens.css`. In `typography.css`, set:

```css
:where(.ui-app, .ui-lab) {
  font-size: var(--ui-text-body);
  line-height: var(--ui-leading-body);
}
.ui-heading--1 { font-size: var(--ui-text-page); line-height: var(--ui-leading-page); }
.ui-heading--2 { font-size: var(--ui-text-section); line-height: var(--ui-leading-section); }
.ui-heading--3 { font-size: var(--ui-text-body); line-height: var(--ui-leading-body); }
.ui-heading--display { font-size: var(--ui-text-display); line-height: var(--ui-leading-display); }
```

Add these Large UI overrides (112.5 percent rounded to whole pixels):

```css
:root[data-a11y-large-ui="true"] {
  --ui-text-micro: 12px;
  --ui-leading-micro: 16px;
  --ui-text-meta: 14px;
  --ui-leading-meta: 18px;
  --ui-text-control: 15px;
  --ui-leading-control: 20px;
  --ui-text-body: 16px;
  --ui-leading-body: 23px;
  --ui-text-section: 18px;
  --ui-leading-section: 25px;
  --ui-text-page: 24px;
  --ui-leading-page: 32px;
  --ui-text-display: 32px;
  --ui-leading-display: 41px;
}
```

Do not override `--ui-prose-size` from Large UI; the independent Large prose
preference remains its owner.

- [ ] **Step 4: Run the token red-green gate**

```powershell
F:\git\Sonder_Engine\.venv\Scripts\python.exe -m pytest tests/test_ui_next_entry.py browser_tests/test_ui_foundation.py -q --basetemp=F:\git\Sonder_Engine\.tmp\type-tokens-green
```

### Task 2: Migrate readable component text to the formal scale

**Files:**
- Modify: `static/css/ui/components.css`
- Modify: `static/css/ui/shell.css`
- Modify: `static/css/ui/play.css`
- Modify: `static/css/ui/library.css`
- Modify: `static/css/ui/library-authoring.css`
- Modify: `static/css/ui/settings.css`
- Modify: `static/css/ui/story-tools.css`
- Modify: `static/css/ui/new-story.css`
- Modify: `static/css/ui/auth.css`
- Modify: `static/css/ui/guest.css`
- Modify: `static/css/ui/entry.css`
- Modify: `static/css/ui/runtime.css`
- Modify: `static/css/ui/lab.css`
- Test: `tests/test_ui_next_entry.py`

**Interfaces:**
- Consumes: Task 1 semantic type and leading tokens.
- Produces: component CSS without one-off readable-text sizes.

- [ ] **Step 1: Add a failing raw-size audit**

Scan component styles for numeric `font-size` declarations and numeric sizes
inside `font` shorthands. Permit `tokens.css`, prose-size variables, and the
mobile 16 px input safeguard only:

```python
def test_readable_component_text_uses_semantic_type_tokens():
    offenders = []
    for path in (ROOT / "static/css/ui").rglob("*.css"):
        if path.name in {"tokens.css"} or "themes" in path.parts:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"font-size\s*:\s*(?:\d|\.)", line):
                if "mobile-input-text-safeguard" not in line:
                    offenders.append(f"{path.relative_to(ROOT)}:{number}")
    assert offenders == []
```

Add a second pattern for numeric `font:` shorthands and require semantic
variables there as well.

- [ ] **Step 2: Replace values by semantic role**

Map each readable selector deliberately:

- navigation indices and kickers -> micro;
- supporting labels and state summaries -> metadata;
- buttons, inputs, selects, tabs -> control;
- descriptions and ordinary copy -> body;
- card/group headings -> section;
- destination headings -> page;
- only onboarding/emphasis headings -> display;
- transcript/story narration -> prose.

Use both size and line-height tokens. Do not mechanically map every previous
15 px declaration to body without checking its semantic role.

- [ ] **Step 3: Verify the reported review/detail density**

In Library browser coverage, assert selected detail title is 16 px, ordinary
description is 14 px, metadata is 12 px, and action controls are 13 px. Assert
the same computed roles on Story Tools state copy and Settings panels.

- [ ] **Step 4: Run affected visual contracts**

```powershell
F:\git\Sonder_Engine\.venv\Scripts\python.exe -m pytest tests/test_ui_next_entry.py browser_tests/test_ui_foundation.py browser_tests/test_ui_library.py browser_tests/test_ui_settings.py browser_tests/test_ui_story_tools.py browser_tests/test_ui_play.py -q --basetemp=F:\git\Sonder_Engine\.tmp\type-migration-green
```

### Task 3: Pin the free-standing geometry audit

**Files:**
- Modify: `tests/test_ui_next_entry.py`
- Modify: `browser_tests/test_ui_foundation.py`
- Modify: `static/css/ui/components.css`

**Interfaces:**
- Consumes: existing radius tokens and rendered replacement destinations.
- Produces: explicit `data-ui-square-geometry` exemption semantics and computed-style audit helpers.

- [ ] **Step 1: Add a failing known-defect test**

```python
def test_empty_and_status_frames_use_the_default_bevel(page, ui_base_url):
    # Open Play without a story and Story Tools without a story.
    for selector in (".ui-play__state", ".ui-story-tools__state"):
        radius = page.locator(selector).evaluate(
            "node => getComputedStyle(node).borderTopLeftRadius"
        )
        assert radius == "4px"
```

- [ ] **Step 2: Add a cross-destination framed-surface scanner**

For each visible element, collect computed border widths, border styles,
bounding box, outer radii, and `data-ui-square-geometry`. Treat an element as
fully framed when all four sides have a visible nonzero border and it is not
flush to the viewport. Require at least a 3 px radius unless the explicit
structural exemption is present. Return selector-like identity and geometry
for every offender.

- [ ] **Step 3: Add the static radius-domain contract**

Parse `border-radius` declarations and allow only `0`, tokenized sm/md/lg,
`3px`, `4px`, `5px`, and semantic round. Mixed corner declarations may use
zero only at shared internal edges.

- [ ] **Step 4: Run the geometry red gate**

```powershell
F:\git\Sonder_Engine\.venv\Scripts\python.exe -m pytest tests/test_ui_next_entry.py browser_tests/test_ui_foundation.py -q --basetemp=F:\git\Sonder_Engine\.tmp\geometry-red
```

Expected: the Play and Story Tools named boxes fail at `0px`; the scanner
reports every additional visible square outer frame.

### Task 4: Repair every audited free-standing frame

**Files:**
- Modify: all audited files under `static/css/ui/`
- Modify: affected markup under `static/js/ui-next/` only where an explicit structural exemption is required
- Modify: `browser_tests/test_ui_foundation.py`

**Interfaces:**
- Consumes: Task 3 offender report.
- Produces: zero unapproved hard-edged free-standing surfaces.

- [ ] **Step 1: Repair the named defects first**

Apply `var(--ui-radius-md)` and restrained inner-top tone to:

```css
.ui-play__state,
.ui-story-tools__state,
.ui-settings__theme-ledger,
.ui-settings__extension-consent,
.ui-new-story__routes,
.ui-new-story__asset-section {
  border-radius: var(--ui-radius-md);
  box-shadow: inset 0 1px color-mix(in srgb, var(--ui-color-text) 3%, transparent);
}
```

Add `overflow: clip` to rounded ledgers/clusters so internal square rows do not
paint through the outer corners.

- [ ] **Step 2: Classify every remaining offender**

For each scanner result:

- assign md to an ordinary frame;
- assign lg to a large panel/dialog;
- assign sm to a compact nested control;
- move rounding to the containing outer group when the result is an internal
  row;
- add `data-ui-square-geometry="structural"` only for a viewport-flush pane,
  image crop, or genuine divider that has no free-standing outer corner.

- [ ] **Step 3: Run the complete geometry matrix**

Exercise Play empty/active, Story Tools empty/detail, Settings, populated and
empty Library, Library authoring, New Story, dialogs, auth/guest/runtime, and
the component lab at desktop, tablet, phone, and short landscape.

- [ ] **Step 4: Commit typography and geometry**

```powershell
git add static/css/ui static/js/ui-next tests/test_ui_next_entry.py browser_tests/test_ui_foundation.py browser_tests/test_ui_library.py browser_tests/test_ui_settings.py browser_tests/test_ui_story_tools.py browser_tests/test_ui_play.py
git commit -m "style(ui): enforce type and bevel tokens"
```
