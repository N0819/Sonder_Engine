# Settings Controls and Custom Themes Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to
> implement this plan task by task.

**Goal:** Repair the reported Settings and Library control defects, add a safe
semantic custom-theme editor, and ship Neon Circuit plus a strictly
warm-grayscale Modern Slate theme.

**Architecture:** Keep appearance ownership in the existing preflight/runtime
pair. Add one pure custom-theme module for schema, color conversion, contrast,
and fixed-property application; use it from Settings and runtime appearance,
while preflight retains a synchronous dependency-free copy of the narrow
validation/application boundary. Extend existing Settings rendering rather
than creating a parallel page or persistence system.

**Tech stack:** Browser JavaScript ES modules, semantic HTML, scoped CSS,
Python/pytest static contracts, and Playwright browser tests.

**Specification:**
`docs/superpowers/specs/2026-08-23-settings-controls-and-custom-themes-design.md`

## Task 1: Lock shared control geometry and spacing with regressions

**Files:**

- Modify: `browser_tests/test_ui_settings.py`
- Modify: `browser_tests/test_ui_library.py`
- Modify: `tests/test_ui_foundation.py`
- Modify: `static/css/ui/components.css`
- Modify: `static/css/ui/settings.css`

1. Add browser assertions that the Settings search icon is centered against
   its input in comfortable, compact, and touch layouts; empty section status
   regions consume no height; and first-group offsets match across Settings
   categories.
2. Add browser assertions that representative Settings and Library selects use
   the shared radius, compact text, semantic fill, trailing chevron space, and
   density/touch heights.
3. Add browser assertions that Search and New Story use centered inline-flex
   icon/label geometry and compact text, including a centered plus icon.
4. Run:
   `.venv\Scripts\python.exe -m pytest browser_tests/test_ui_settings.py browser_tests/test_ui_library.py tests/test_ui_foundation.py -q`
   and confirm the new assertions fail for the existing fixed icon inset,
   empty status height, native selects, and baseline button layout.
5. Implement scoped shared select and button rules in `components.css`; center
   the search icon and collapse empty statuses in `settings.css`.
6. Rerun the focused command and keep all pre-existing geometry/touch contracts
   green.

## Task 2: Replace narrator textarea flow with one accessible tabbed editor

**Files:**

- Modify: `browser_tests/test_ui_settings.py`
- Modify: `static/js/ui-next/settings-view.js`
- Modify: `static/css/ui/settings.css`

1. Add a browser test that loads four distinct `/api/exemplars` values and
   requires one visible textarea, four tabs, correct ARIA relationships, and
   preserved inactive drafts.
2. Extend it to exercise click, Left/Right Arrow, Home, and End navigation,
   edit multiple slots, save, and assert the request still contains all four
   values in slot order.
3. Run only the new narrator tests and confirm failure against the four raw
   textareas.
4. Build the tablist and single textarea in `settings-view.js`, retaining the
   existing endpoint, limits, save flow, and optional empty slots.
5. Add the compact tab/editor layout and responsive wrapping rules in
   `settings.css`.
6. Rerun the narrator tests and the complete Settings browser file.

## Task 3: Make Add-ons actions coherent and install the Maintenance icon

**Files:**

- Modify: `browser_tests/test_ui_settings.py`
- Modify: `tests/test_ui_icon_system.py`
- Modify: `static/js/ui-next/settings-view.js`
- Modify: `static/css/ui/settings.css`
- Modify: `static/assets/icons/sonder-icons.svg`
- Modify: `static/js/ui/icons.js`

1. Add tests proving an extension title keeps `Campaign (demo)` while lifecycle
   actions and success/status copy say `Enable Campaign`, `Remove Campaign`,
   and equivalent forms without `demo`.
2. Add a computed-style assertion for the lifecycle actions' subtle 0.5px
   border without changing unrelated buttons.
3. Add icon contracts requiring a unique `icon-maintenance`, current-color
   filled rendering, sprite inventory exposure, and use by the Maintenance
   category while `icon-update` remains intact.
4. Run the focused Settings Add-ons and icon tests and confirm failure.
5. Add a narrowly scoped terminal-demo-label helper and apply it only to
   lifecycle action/status copy. Add the action border rule.
6. Port the supplied 24x24 wrench path into `icon-maintenance`, expose it in the
   inventory, and update the category mapping.
7. Rerun the focused tests and visually inspect the rendered sprite.

## Task 4: Retire Legacy Themes and add the two curated palettes

**Files:**

- Modify: `tests/test_ui_foundation.py`
- Modify: `browser_tests/test_ui_settings.py`
- Modify: `static/js/ui-next/settings-view.js`
- Modify: `static/js/ui/appearance.js`
- Modify: `static/js/ui/appearance-preflight.js`
- Add: `static/css/ui/themes/neon-circuit.css`
- Add: `static/css/ui/themes/modern-slate.css`
- Modify: `static/ui-next.html`
- Modify: `static/ui-next-runtime.html`
- Modify: `static/ui-next-lab.html`
- Modify: `static/login.html`
- Modify: `static/guest.html`

1. Replace the legacy-theme browser contract with assertions that no Legacy
   Themes label/select or `data-legacy-theme` marker exists and that an old
   stored value is dropped without changing its mapped curated theme.
2. Add static/browser tests requiring six curated theme choices and matching
   first-paint/runtime allowlists.
3. Add token-level tests that Modern Slate's authored color literals are
   achromatic with subtly warm RGB ordering and that every interaction/status
   token remains grayscale. Add computed-style checks for warm-white focus and
   interaction states. Add a rendered smoke test for Neon Circuit.
4. Run the new theme tests and confirm failure.
5. Remove legacy rendering/application paths. Add the two identifiers to theme
   copy, runtime appearance, and preflight.
6. Implement both full semantic token stylesheets, load them on every entry
   that loads curated themes, and keep Modern Slate entirely warm grayscale.
7. Rerun the theme tests and affected auth/entry tests.

## Task 5: Build and test the safe custom-theme core

**Files:**

- Add: `static/js/ui/custom-theme.js`
- Add: `static/css/ui/themes/custom.css`
- Modify: `static/js/ui/appearance.js`
- Modify: `static/js/ui/appearance-preflight.js`
- Modify: `static/js/ui-next/bootstrap.js`
- Modify: `static/js/ui-next/storage.js`
- Modify: `static/ui-next.html`
- Modify: `static/ui-next-runtime.html`
- Modify: `static/ui-next-lab.html`
- Modify: `static/login.html`
- Modify: `static/guest.html`
- Add: `browser_tests/test_ui_custom_theme.py`
- Modify: `tests/test_ui_foundation.py`

1. Add pure-browser tests for normalization, hex/RGB conversion, exact schema
   import/export, contrast checks, background/panel distinction, and rejection
   of unknown keys, CSS, URLs, markup, malformed values, and unknown versions.
2. Add first-paint tests that valid dedicated storage applies only the eight
   fixed properties before module boot and invalid/malicious storage applies
   none. Add runtime tests for the same allowlist.
3. Add storage migration tests proving `legacyTheme` is removed while theme,
   density, effects, and valid custom colors survive.
4. Run the new custom-theme and storage/foundation groups and confirm failure.
5. Implement the pure module with frozen role metadata/defaults, strict
   `#RRGGBB` normalization, RGB conversion, WCAG contrast, palette validation,
   versioned import/export, and fixed-property application.
6. Implement matching synchronous preflight parsing/application, integrate the
   runtime appearance manager and bootstrap, and add the derived custom token
   stylesheet to all theme-bearing entries.
7. Normalize appearance persistence so old legacy members disappear and
   invalid custom payloads cannot become current state.
8. Rerun all custom-theme, storage, foundation, and entry tests.

## Task 6: Build and test the Custom Theme Settings experience

**Files:**

- Modify: `static/js/ui-next/settings-view.js`
- Modify: `static/css/ui/settings.css`
- Modify: `static/css/ui/components.css`
- Modify: `browser_tests/test_ui_custom_theme.py`
- Modify: `browser_tests/test_ui_settings.py`

1. Add browser tests for eight labeled swatches, opening the Design Bible
   dialog, synchronized native/hex/RGB fields, valid live preview, Save Color,
   Cancel rollback, page-level activation, Reset, and persistence after reload.
2. Add invalid-contrast tests that require relationship-specific inline text,
   a disabled activation action, and preservation of the last valid persisted
   theme.
3. Add import/export round-trip and malicious/extra-field rejection tests.
4. Add keyboard, focus return, mobile-sheet, touch-target, and no-horizontal-
   overflow assertions.
5. Run the new browser file and confirm failure.
6. Render the semantic swatch grid, preview, actions, and one shared color
   dialog in `settings-view.js`, reusing the standard dialog composition and
   pure custom-theme module.
7. Style the editor and responsive dialog using existing tokens and component
   geometry; do not introduce custom layout/theme escape hatches.
8. Rerun the custom-theme and complete Settings browser suites.

## Task 7: Rotate the immutable release and update maintained authority

**Files:**

- Modify: all replacement JS module release literals/import queries under
  `static/js/ui-next/` and `static/js/ui/`
- Modify: `static/ui-next.html`
- Modify: `static/ui-next-runtime.html`
- Modify: `static/ui-next-lab.html`
- Modify: `static/login.html`
- Modify: `static/guest.html`
- Modify: `web/app.py`
- Modify: release-literal expectations under `tests/` and `browser_tests/`
- Modify: `docs/guides/INTERFACE.md`
- Modify: `docs/design/sonder-ui-replacement/UI_CLEANUP_FIX_LIST.md`

1. Run the release-fingerprint contract to obtain the expected normalized
   immutable-asset suffix after all frontend edits are stable.
2. Replace the complete old release identifier transactionally across entries,
   modules, server cache policy, and tests; rerun until the fingerprint and
   mixed-release checks pass.
3. Document shared control geometry, narrator tabs, Legacy retirement, curated
   theme identifiers, fixed custom-theme roles/schema/validation, and safe
   preflight ownership in `INTERFACE.md`.
4. Mark the custom-theme cleanup item implemented and append concrete test and
   visual evidence to the cleanup ledger.
5. Run `git diff --check` and the focused static contract collection.

## Task 8: Responsive visual comparison and full verification

**Files:**

- Modify only if a verified defect is found in the files above.

1. Start the test host using the repository's documented browser-test command.
2. Capture Settings Experience, Add-ons, Maintenance, Content narrator, and
   Library at the matching desktop, tablet, mobile, mobile-landscape, and
   short-height reference viewports.
3. Compare each capture side by side with the supplied reference screenshot at
   the same viewport. Check spacing, wrapping, focus, dialog staging, scroll
   ownership, and all six curated/custom palettes. Record intentional approved
   differences.
4. Run the focused UI gate:
   `.venv\Scripts\python.exe -m pytest tests/test_ui_foundation.py tests/test_ui_icon_system.py tests/test_ui_runtime_contracts.py browser_tests/test_ui_settings.py browser_tests/test_ui_custom_theme.py browser_tests/test_ui_library.py -q`.
5. Run the complete browser collection, then the repository's documented full
   pytest gate. Fix any regression at its source and rerun the affected narrow
   test before repeating the gate.
6. Inspect `git diff`, `git diff --check`, and `git status --short`; preserve the
   pre-existing `.tmp/` reference material outside the commit.
7. Commit the verified implementation and documentation, push `interface`, and
   report the exact tests, render evidence, commit, and remote state.

## Next approved work package: grouped Settings overview

The clean scan-first Settings index is deliberately queued after this UI6
control-and-theme release so its information-architecture change receives its
own regressions, visual comparison, immutable release, and integration proof.
It keeps every detailed page and search path, while making `#/settings` a
grouped row ledger with semantic icons, concise current-state summaries, and
direct chevron navigation.

- Design:
  `docs/superpowers/specs/2026-08-23-settings-overview-design.md`
- Implementation plan:
  `docs/superpowers/plans/2026-08-23-settings-overview.md`

