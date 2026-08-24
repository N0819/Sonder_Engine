# Grouped Settings Overview Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to
> implement this plan task by task in a new isolated worktree after UI6 lands.

**Goal:** Add a clean grouped Settings home that routes users to existing
authoritative Settings and Library controls while preserving deep links,
search, persistence, and engine ownership.

**Architecture:** Make `#/settings` a presentation-only index. The overview
reads existing bootstrap and browser-local projections for optional summaries,
then routes into the unchanged detail composition. It owns no settings values,
mutations, discovery calls, or parallel navigation state.

**Tech stack:** Browser JavaScript ES modules, semantic HTML, scoped CSS,
Python/pytest static contracts, and Playwright browser tests.

**Specification:**
`docs/superpowers/specs/2026-08-23-settings-overview-design.md`

## Task 1: Lock route and information-architecture contracts

**Files:**

- Modify: `tests/test_ui_settings_contracts.py`
- Modify: `browser_tests/test_ui_settings.py`
- Modify: `static/js/ui-next/router.js`
- Modify: `static/js/ui-next/shell.js`
- Modify: `static/js/ui-next/settings-view.js`

1. Add static assertions for the four semantic groups and their ordered row
   targets from the specification. Assert every detailed Settings URL remains
   accepted and that no overview row introduces a new persistence/API owner.
2. Add browser tests proving `#/settings`, the global Settings destination, and
   `mod+,` open the overview while direct category/tool URLs still open their
   current detail.
3. Run the new tests and confirm the existing default-to-Experience behavior
   fails the overview contract.
4. Admit the empty Settings segment as `overview`; keep every existing segment
   and query contract unchanged.
5. Rerun the route tests before rendering the overview.

## Task 2: Build a pure overview projection

**Files:**

- Add: `static/js/ui-next/settings-overview.js`
- Modify: `static/js/ui-next/bootstrap.js`
- Modify: `static/js/ui-next/settings-view.js`
- Add: `browser_tests/test_ui_settings_overview.py`

1. Add pure-browser tests for ordered groups, exact route targets, active theme,
   reading/density, effects/sound, accessibility summary, provider/default-model
   summary, and safe descriptive fallbacks.
2. Add negative tests proving projection makes no fetch, provider discovery,
   update check, extension mutation, persistence write, or model call.
3. Implement immutable group/row definitions and a pure summary projector from
   the existing Settings state, appearance manager, accessibility state, and
   already-present extension projection only.
4. Keep absent/loading data non-blocking and never synthesize an authoritative
   count.
5. Rerun the pure projection tests.

## Task 3: Render the grouped ledger with existing primitives

**Files:**

- Modify: `static/js/ui-next/settings-overview.js`
- Modify: `static/js/ui-next/settings-view.js`
- Modify: `static/css/ui/settings.css`
- Modify: `static/js/ui/icons.js` only if a required semantic icon is absent
- Modify: `static/assets/icons/sonder-icons.svg` only if a reviewed local icon
  is absent
- Modify: `browser_tests/test_ui_settings_overview.py`

1. Add browser assertions for one heading/ledger per group, one full-row link,
   icon-title-summary-chevron order, visible dividers, semantic local sprite
   references, and no nested buttons/forms/toggles.
2. Add interaction assertions for click, Enter, focus ring, unavailable Turn
   details without a Story, and Story imports/backups crossing transparently to
   Library.
3. Render the overview beneath the existing Settings header. Omit the category
   rail on overview only; detailed pages retain it and gain one quiet Settings
   overview link.
4. Style one readable ledger column using existing semantic tokens, typography,
   row geometry, and chevron. Do not introduce a dashboard grid or copied pixel
   measurements.
5. Rerun the overview browser file.

## Task 4: Preserve search, history, focus, and responsive behavior

**Files:**

- Modify: `static/js/ui-next/settings-view.js`
- Modify: `static/js/ui-next/navigation-state.js` only if its current bounded
  record cannot restore the overview row
- Modify: `static/css/ui/settings.css`
- Modify: `browser_tests/test_ui_settings_overview.py`
- Modify: `browser_tests/test_ui_settings.py`

1. Add tests that Settings search from overview opens the exact detailed
   control and Back returns to the overview with its scroll and launching-row
   focus restored.
2. Add 1440×900, 1024×768, 390×844, 360×800, 844×390, large-interface,
   Japanese, reduced-motion, and 200-percent zoom-equivalent cases.
3. Assert zero horizontal page overflow, one vertical owner, 44 px compact
   targets, no clipped title/summary/chevron, and no focusable control in an
   unavailable row.
4. Implement only the bounded navigation-state and responsive CSS needed by
   those failures.
5. Rerun complete Settings and shell browser suites.

## Task 5: Visual review, maintained authority, and release rotation

**Files:**

- Add: `tools/capture_ui_settings_overview.py`
- Add: `docs/design/sonder-ui-replacement/wp18/REVIEW.md`
- Add: `docs/design/sonder-ui-replacement/wp18/screenshots/*.png`
- Modify: `docs/guides/INTERFACE.md`
- Modify: `docs/design/sonder-ui-replacement/UI_CLEANUP_FIX_LIST.md`
- Modify: replacement release literals, entries, server policy, and active
  release tests as one immutable transaction

1. Capture overview desktop, phone, and short-landscape states plus overview →
   detail → Back at a matching viewport.
2. Compare grouping, row hierarchy, summary restraint, separator rhythm, and
   responsive staging with the approved Sonder composition. Record that the
   supplied grouped-settings image informed composition only.
3. Update maintained interface ownership and mark UI-BL-02 fixed only after the
   browser evidence is reviewed.
4. Rotate the complete immutable UI release from the normalized final asset
   fingerprint and rerun the release/mixed-graph contracts.
5. Run focused overview/Settings/shell tests, the complete browser suite,
   generated code-map and structure checks, then the complete repository suite.
6. Inspect the scoped diff, commit on its isolated branch, integrate into
   `interface`, push, and verify the exact remote head.
