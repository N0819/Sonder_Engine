# Sonder Progressive Interface Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recompose Sonder's production interface around progressive disclosure while preserving every current runtime, persistence, localization, accessibility, and extension contract.

**Architecture:** Pure presentation-state contracts drive one adaptive shell and one contextual drawer. Destination modules keep their current service owners and adopt shared route-focus, field, app-header, media, and staged-detail components. Every phase uses focused browser behavior tests before implementation and records real Chromium evidence.

**Tech Stack:** Vanilla JavaScript ES modules, semantic HTML, CSS custom properties, FastAPI-owned APIs, pytest, Playwright, existing capture tools.

**Spec:** `docs/superpowers/specs/2026-08-24-sonder-progressive-interface-redesign.md`

## Global constraints

- Keep Play, Library, and Settings as the only top-level destinations.
- Do not add a frontend framework, runtime dependency, parallel store, or new server authority.
- Preserve current routes, drafts, write confirmation, stale-owner rejection, extension UI API, localization, and teardown contracts.
- Write a focused failing behavior test before each production behavior change and verify the expected failure.
- Use complete localized strings; never translate story/user data or store credentials in general state.
- Use logical CSS, 44 px touch targets, visible interactive focus, reduced motion, high contrast, large UI, roomy targets, RTL, and 200 percent zoom.
- Rotate the immutable UI release only after all source changes are integrated, then regenerate maps through repository tooling.

---

### Task 1: Foundation and responsive-state contracts

**Files:**
- Create: `static/js/ui/components/route-focus.js`
- Create: `static/js/ui/components/field.js`
- Create: `static/js/ui-next/layout-contract.js`
- Modify: `static/js/ui/components/index.js`
- Modify: `static/css/ui/tokens.css`
- Modify: `static/css/ui/components.css`
- Test: `browser_tests/test_ui_shell.py`
- Test: `browser_tests/test_ui_library.py`
- Test: `tests/test_ui_shell_contracts.py`

**Interfaces:**
- Produces `focusRouteTarget(target, { preventScroll })`, `createField(documentRef, options)`, `layoutStateFor(width, height)`, `canPinContext(input)`, and `contextMode(input)`.
- Keeps field controls on `.ui-field__control` and root state on stable data attributes.

- [ ] Add tests that route focus has no form-like ring while the next keyboard-focused control has the shared visible ring; run the named tests and confirm failure against direct `.focus()`.
- [ ] Add layout-contract tests for all four states, short landscape, 680 px pin threshold, and closed/overlay/pinned transitions; confirm the missing module fails.
- [ ] Implement the pure modules and canonical field primitive, export them, and update focus/field consumers.
- [ ] Calibrate 12/13/14/15/17/24 typography, 40/44 px controls, 6/9/14 px radii, and distinct surface roles across curated themes.
- [ ] Rerun focused shell/Library contracts and capture foundation states.

### Task 2: Adaptive shell, application header, and contextual drawer

**Files:**
- Create: `static/js/ui-next/components/app-header.js`
- Create: `static/js/ui-next/components/responsive-drawer.js`
- Modify: `static/ui-next.html`
- Modify: `static/js/ui-next/shell.js`
- Modify: `static/js/ui-next/inspector-host.js`
- Modify: `static/js/ui-next/navigation-state.js`
- Modify: `static/css/ui/shell.css`
- Test: `browser_tests/test_ui_shell.py`
- Test: `tests/test_ui_shell_contracts.py`

**Interfaces:**
- Consumes Task 1 layout and route-focus functions.
- Produces one header model, persisted `data-nav-collapsed`, and `data-context-mode="closed|overlay|pinned"`.

- [ ] Add failing tests for labeled wide rail, persisted collapse, compact app bar, explicit false inspector defaults, overlay Back/Escape/focus return, expansive-only pin, auto-unpin below 680 px, one mounted context view, no duplicate opener, and no viewport-matrix overflow.
- [ ] Replace competing shell CSS passes with one grid model and logical safe-area rules.
- [ ] Move compact title, Back, command, contextual action, and overflow into the app header; remove independent fixed controls and visible ordinals.
- [ ] Replace inspector size modes with closed/overlay/pinned drawer state while preserving current router layers and content mounts.
- [ ] Rerun shell tests and capture all nine required viewports in expanded, collapsed, overlay, and pinned states.

### Task 3: Grouped command palette

**Files:**
- Modify: `static/js/ui-next/go-to.js`
- Modify: `static/css/ui/shell.css`
- Test: `browser_tests/test_ui_shell.py`

**Interfaces:**
- Consumes current router, shortcut registry, Library/story/store projections, Story Tool registry, Settings definitions, and extension result providers.
- Produces grouped command results with label, description, route/action, and availability.

- [ ] Add failing tests for destinations, recent stories, New Story, current story, Library categories, Story Tools, Settings concepts, contextual actions, extension groups, keyboard selection, and omitted unavailable commands.
- [ ] Implement grouped semantic results using existing roving-focus utilities and one mobile/desktop opener.
- [ ] Verify `mod+k`, typing guards, route layers, focus return, long labels, and touch reachability.

### Task 4: Play hierarchy and composer

**Files:**
- Create: `static/js/ui-next/components/empty-resume-state.js`
- Modify: `static/js/ui-next/play-view.js`
- Modify: `static/css/ui/play.css`
- Modify: `language_packs/en/ui.json`
- Modify: `language_packs/ja/ui.json`
- Test: `browser_tests/test_ui_play.py`
- Test: `tests/test_ui_play_contracts.py`

**Interfaces:**
- Consumes existing `services.play`, `services.atmosphere`, story projection, draft, preview, retry, and mutation methods unchanged.
- Produces editorial user turns, focus-revealed actions, one composer plate, and a real-data resume state.

- [ ] Add failing tests for no permanent Story Tools panel, meaningful header data, no decorative status, editorial input echo, pointer focus reveal, coarse-pointer 44 px More, integrated composer, ambience disclosure, constrained-height geometry, and technical Advanced disclosure.
- [ ] Add failing empty/loading/generating/recoverable-error tests using current fixtures and real recent-story metadata.
- [ ] Implement the new header, turn menu staging, auto-growing composer, stop/retry states, and empty resume hierarchy without changing Play runtime calls.
- [ ] Remove Play grid decoration and verify prose measure/line breaks, scrollback stability, 500-turn budget, drafts, retry, reroll, versions, edit, branch, delete, archive, and atmosphere behavior.
- [ ] Capture empty, populated, long, focused, generating, error, backdrop, mobile keyboard approximation, and short-landscape states.

### Task 5: Library browser and staged filters/detail

**Files:**
- Create: `static/js/ui-next/components/media-row.js`
- Create: `static/js/ui-next/components/filter-sheet.js`
- Modify: `static/js/ui-next/library-view.js`
- Modify: `static/js/ui-next/library-authoring-view.js`
- Modify: `static/css/ui/library.css`
- Modify: `static/css/ui/library-authoring.css`
- Modify: `language_packs/en/ui.json`
- Modify: `language_packs/ja/ui.json`
- Test: `browser_tests/test_ui_library.py`
- Test: `browser_tests/test_ui_library_authoring.py`
- Test: `tests/test_ui_library_contracts.py`

**Interfaces:**
- Consumes Task 1 fields, Task 2 drawer, current Library route/query/runtime, and category-specific server projection.
- Produces shared semantic media rows, compact primary toolbar, filter sheet, active chips, and list/detail restoration.

- [ ] Add failing tests for canonical field controls, media/fallback rendering, absent ordinals, toolbar composition, staged secondary filters, active chips, first-result top within 240 px at 390 px, and no fake metadata.
- [ ] Add failing Back/Forward tests that preserve category, query, filters, sort, scroll, focus, selection, and owner-scoped drafts on compact and overlay detail.
- [ ] Implement category adapters and shared media rows using local imagery only; retain explicit Open in Play and row-menu nonselection.
- [ ] Remove the Library grid and default dense-ledger presentation while preserving Compact density.
- [ ] Rerun lifecycle, association, undo, archive, import, authoring, 1,000-item, offline, loading, error, empty, search, and long-result coverage; capture the full category matrix.

### Task 6: Grouped Story Tools

**Files:**
- Modify: `static/js/ui-next/story-tools-registry.js`
- Modify: `static/js/ui-next/story-tools-view.js`
- Modify: `static/js/ui-next/story-tools-runtime.js`
- Modify: `static/css/ui/story-tools.css`
- Modify: `language_packs/en/ui.json`
- Modify: `language_packs/ja/ui.json`
- Test: `browser_tests/test_ui_story_tools.py`
- Test: `browser_tests/test_ui_live_story_tools.py`
- Test: `tests/test_ui_story_tools_contracts.py`

**Interfaces:**
- Produces immutable `STORY_TOOL_GROUPS`, exact one-group validation, and a bounded recent-tool list of three IDs.
- Keeps tool IDs, routes, service owners, drafts, and tool-specific mounts unchanged.

- [ ] Add failing tests that every tool belongs to exactly one known group, group references are complete, and missing/duplicate membership throws.
- [ ] Add failing browser tests for grouped landing, descriptions, recent tools, no indices/count, Back/heading/group orientation, labeled selector, compact list-or-detail, browser Back, and opener focus return.
- [ ] Implement grouped list and detail; migrate old size preferences without rendering Rail or an icon-only switcher.
- [ ] Verify every live tool, unavailable story state, drafts, diagnostics, pinning distinction, touch targets, teardown, and mobile/landscape geometry; capture all tools and representative grouped states.

### Task 7: Settings module split and staged concepts

**Files:**
- Create: `static/js/ui-next/settings/settings-definitions.js`
- Create: `static/js/ui-next/settings/settings-overview.js`
- Create: `static/js/ui-next/settings/settings-navigation.js`
- Create: `static/js/ui-next/settings/settings-search.js`
- Create: `static/js/ui-next/settings/settings-detail.js`
- Create: `static/js/ui-next/settings/appearance.js`
- Create: `static/js/ui-next/settings/advanced-theme.js`
- Modify: `static/js/ui-next/settings-view.js`
- Modify: `static/js/ui-next/settings-overview.js`
- Modify: `static/css/ui/settings.css`
- Modify: `language_packs/en/ui.json`
- Modify: `language_packs/ja/ui.json`
- Test: `browser_tests/test_ui_settings.py`
- Test: `browser_tests/test_ui_settings_overview.py`
- Test: `tests/test_ui_settings_contracts.py`

**Interfaces:**
- Produces six user-concept groups, legacy-route resolution, overview/detail renderers, exact-control search, and Advanced Theme Editor.
- Consumes current settings services; server-confirmed projection remains the completion boundary.

- [ ] Add failing tests for desktop navigation-plus-one-detail, compact/medium overview-or-detail, sticky Back/title, deep link, Back scroll/focus restoration, exact-control search, single scroll owner, and six concept groups.
- [ ] Extract immutable definitions, route mapping, overview, navigation, search, and appearance modules without changing service calls.
- [ ] Move raw semantic colors and JSON import/export behind Advanced Theme Editor while keeping curated previews, reading comfort, scales, density, motion, and accessibility in the ordinary Appearance path.
- [ ] Preserve every current setting and rerun provider, model, narrator, content, extension, maintenance, persistence-failure, draft, long-detail, RTL/long-label, and accessibility coverage.
- [ ] Capture desktop, tablet, mobile overview/detail/search/deep-link/theme/advanced/error and short-height states.

### Task 8: New Story and authoring staging

**Files:**
- Modify: `static/js/ui-next/new-story.js`
- Modify: `static/css/ui/new-story.css`
- Modify: `static/js/ui-next/library-editors/character-persona.js`
- Modify: `static/css/ui/library-authoring.css`
- Modify: `language_packs/en/ui.json`
- Modify: `language_packs/ja/ui.json`
- Test: `browser_tests/test_ui_new_story.py`
- Test: `browser_tests/test_ui_character_persona_editor.py`

**Interfaces:**
- Keeps three route IDs, local draft envelope, create/generate APIs, partial cleanup, lived-location payload, and lossless unknown-field handling.
- Produces unnumbered route cards, route-specific steps, full-height compact wizard, and staged Advanced authoring data.

- [ ] Add failing tests for unnumbered whole-card choices, route-specific step skipping, app-bar Back/title, sticky keyboard-safe action, and raw-data Advanced disclosure.
- [ ] Implement the staged compositions without changing draft, resume/discard, validation, creation, cleanup, retry, or warning boundaries.
- [ ] Rerun all three creation routes, draft recovery, validation, creation failure, lived location, person editor, unknown-field, and responsive tests; capture every setup stage and failure state.

### Task 9: Cross-surface visual and accessibility hardening

**Files:**
- Modify: `static/css/ui/tokens.css`
- Modify: `static/css/ui/components.css`
- Modify: `static/css/ui/themes/carbon-signal.css`
- Modify: `static/css/ui/themes/ash-brass.css`
- Modify: `static/css/ui/themes/midnight-ink.css`
- Modify: `static/css/ui/themes/parchment-night.css`
- Modify: `static/css/ui/themes/neon-circuit.css`
- Modify: `static/css/ui/themes/modern-slate.css`
- Modify: `static/css/ui/themes/custom.css`
- Modify: `static/css/ui/shell.css`
- Modify: `static/css/ui/play.css`
- Modify: `static/css/ui/library.css`
- Modify: `static/css/ui/story-tools.css`
- Modify: `static/css/ui/settings.css`
- Modify: `static/css/ui/new-story.css`
- Test: `browser_tests/test_ui_shell.py`
- Test: `browser_tests/test_ui_play.py`
- Test: `browser_tests/test_ui_library.py`
- Test: `browser_tests/test_ui_story_tools.py`
- Test: `browser_tests/test_ui_settings.py`
- Test: `browser_tests/test_ui_new_story.py`

**Interfaces:**
- Consumes the revised semantic token family; themes override color values only.
- Produces perceptibly distinct canvas/surface/raised/selected/scrim roles across every curated theme.

- [ ] Add or update viewport-matrix tests for document overflow, 40 px desktop controls, 44 px touch controls, focus visibility, RTL, 30-percent label expansion, 200-percent zoom, reduced motion, high contrast, large UI, roomy targets, and short landscape.
- [ ] Remove remaining decorative grids, excessive cyan glow, micro routine labels, and border-only grouping; calibrate all curated themes.
- [ ] Inspect same-fixture captures for overlap, clipping, dead space, control density, duplicate actions, focus, radii, surface tiers, composer obstruction, list/detail staging, and pin measure.
- [ ] Fix every P0/P1 visual or interaction finding and rerun the affected focused suite before final capture.

### Task 10: Release integration and qualification

**Files:**
- Modify: all immutable UI release references through the repository release procedure
- Modify: `docs/guides/INTERFACE.md`
- Modify: `docs/guides/UI_REFERENCE.md`
- Modify: `Design.md` and `docs/UNBUILT.md` only for implemented status changes
- Create: `docs/design/sonder-ui-replacement/redesign/REVIEW.md`
- Create: `docs/design/sonder-ui-replacement/redesign/after/desktop-contact-sheet.png`
- Create: `docs/design/sonder-ui-replacement/redesign/after/tablet-contact-sheet.png`
- Create: `docs/design/sonder-ui-replacement/redesign/after/mobile-contact-sheet.png`
- Create: `docs/design/sonder-ui-replacement/redesign/after/state-contact-sheet.png`
- Regenerate: `docs/CODE_MAP.md`

**Interfaces:**
- Produces one normalized immutable UI fingerprint and final evidence/report paths.

- [ ] Derive one fresh release fingerprint after all JS/CSS/sprite changes and update HTML, module imports, server references, catalogs, tests, and generated map coherently.
- [ ] Run focused browser files, full `browser_tests`, compile, structure/map freshness, and the full pinned-venv test suite; record exact counts and failures.
- [ ] Capture and visually inspect desktop, tablet, mobile, short-landscape, empty, populated, loading, generation, error, long-content, overlay, pinned, focus, RTL, and accessibility states.
- [ ] Build desktop, tablet, mobile, and state contact sheets and record viewport-by-viewport findings in `REVIEW.md`.
- [ ] Review the complete diff for unrelated formatting, sensitive/private context, stale release IDs, missing localization, duplicate mounts/listeners, and undocumented deviations.
- [ ] Commit coherent implementation slices, merge the verified branch to `interface`, push with GitHub CLI network permission, and verify the exact remote head and CI when repository workflow permits.
