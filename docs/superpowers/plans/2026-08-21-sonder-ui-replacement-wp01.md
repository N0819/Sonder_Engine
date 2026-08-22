# Sonder UI Replacement WP-01 Implementation Plan

> **Execution:** Implement task by task with focused tests first. Use the G1 review matrix in Task 8 before claiming the foundation complete.

**Goal:** Deliver the complete, reusable visual and interaction foundation for the replacement interface and lock Gate G1 without changing the classic host or adding product data flows.

**Architecture:** `/ui-next` remains an authenticated, isolated native-module entry. Shared replacement CSS lives under `static/css/ui/`; shared replacement JavaScript lives under `static/js/ui/`. Semantic tokens own all component color, geometry, spacing, type, motion, and layer decisions. A repo-local component laboratory at `/ui-next/lab` exercises every primitive and state without calling application APIs. Components use native HTML first, explicit constructors/controllers where behavior is required, and no legacy DOM mutation, polling, hidden controls, or `window.S` bridge.

**Reference:** `docs/superpowers/specs/2026-08-21-sonder-ui-full-replacement-design.md` § WP-01 and Gate G1; `docs/design/sonder-ui-bible/` chapters 6–11, 13, 19, 21, and 24.

**Candidate disposition:** Adapt the candidate token values and accessibility concepts after reconciliation. Accept the locally served SVG sprite only after inventory and lint checks. Reject its global element selectors, legacy token bridge, legacy-theme migration, glyph-replacement mutation observer, and compatibility-first component CSS. Retain the existing Antonio font payload and OFL record; the replacement uses robust system stacks and introduces no network font or icon dependency.

**Out of scope:** Application store/router/API work (WP-02), shell/navigation (WP-03), product surfaces (WP-04–WP-11), legacy-theme compatibility (WP-12), default-entry cutover (WP-14), and any engine or persistence behavior.

---

## Task 1: Lock the G1 contracts with source-level tests

**Files:**

- Add: `tests/test_ui_foundation.py`
- Add: `tests/test_ui_icon_system.py`
- Modify: `tests/test_ui_next_entry.py`

- [ ] Write failing tests that require the proposed CSS/JS responsibility boundaries, four curated theme files, local icon sprite and inventory, head-safe preflight, component lab entry, and authenticated `/ui-next/lab` route.
- [ ] Reject undocumented hex/rgb colors in component CSS, external font/icon URLs, emoji or platform-glyph primary icons, legacy stylesheet/script imports, `window.S`, polling, and global legacy DOM mutation.
- [ ] Require the Bible spacing, radius, control, type, motion, and z-layer token names and values; require reduced-motion handling and the full accessibility preference vocabulary.
- [ ] Require every SVG symbol to have a unique `icon-*` id, `viewBox="0 0 24 24"`, `currentColor`, and no embedded script/style/network reference.
- [ ] Run the focused tests and record the expected RED failures.

## Task 2: Build semantic tokens, typography, themes, and first-paint appearance

**Files:**

- Add: `static/css/ui/reset.css`
- Add: `static/css/ui/tokens.css`
- Add: `static/css/ui/typography.css`
- Add: `static/css/ui/themes/carbon-signal.css`
- Add: `static/css/ui/themes/ash-brass.css`
- Add: `static/css/ui/themes/midnight-ink.css`
- Add: `static/css/ui/themes/parchment-night.css`
- Add: `static/js/ui/appearance-preflight.js`
- Add: `static/js/ui/appearance.js`
- Modify: `static/ui-next.html`
- Delete: `static/css/ui-next-development.css`

- [ ] Define role-based semantic tokens for backgrounds, solid/translucent surfaces, text, borders, interaction, status, typography, spacing, radii, sizes, motion, focus, shadows, and named z bands. Component CSS may consume only semantic roles.
- [ ] Implement Carbon Signal as the default and the other three curated, genre-neutral palettes as data-attribute overrides.
- [ ] Preserve UI/prose/mono role separation, 17px/1.7/720px story prose defaults, 15/17/19/21 prose sizes, and safe system fallbacks. Do not remove the existing licensed Antonio files or OFL record.
- [ ] Run the tiny classic script in `<head>` before styles paint. It may only validate and stamp browser-local theme, prose-size, effects, color-scheme, and reduced-motion values. The ES module owns subsequent changes and events.
- [ ] Keep effects and surfaces independent. Provide solid surfaces, high contrast, strong focus, large UI/prose, roomy targets, status markers, and reduced-motion token overrides.
- [ ] Make native controls inherit font/color safely and remove browser defaults only where the replacement component layer restores semantics.
- [ ] Run source-level tests until GREEN and commit the visual-system foundation separately.

## Task 3: Adopt and validate the original local icon system

**Files:**

- Add: `static/assets/icons/sonder-icons.svg`
- Add: `static/js/ui/icons.js`
- Add: `docs/design/sonder-ui-replacement/ICON_INVENTORY.md`
- Modify: `docs/CREDITS.md`

- [ ] Copy the candidate sprite, then lint every symbol and manually reconcile naming, geometry, line treatment, selective fills, and required G1 state icons.
- [ ] Record every icon id, intended semantic use, allowed sizes, visible-label rule, and provenance in the inventory.
- [ ] Implement explicit `createIcon`, `createIconLabel`, and `setIconButton` helpers. They must validate icon names, hide decorative SVGs from assistive technology, and require accessible names for icon-only buttons.
- [ ] Do not scan/mutate arbitrary buttons, infer icons from English text, or translate legacy emoji at runtime.
- [ ] Prove the sprite is local, build-free, cacheable, `currentColor` driven, and has no external dependency.
- [ ] Commit the icon system separately.

## Task 4: Build static component primitives and complete state styling

**Files:**

- Add: `static/css/ui/components.css`
- Add: `static/css/ui/utilities.css`
- Add: `static/js/ui/components/primitives.js`

- [ ] Implement scoped replacement primitives for buttons (default/primary/quiet/destructive/icon), fields, textarea, select, checkbox, toggle, segmented control, tabs, menu, list row, card, cluster, dialog, sheet, notice, task status, skeleton, empty/no-result/error states, and confirmation.
- [ ] Cover default, hover, focus-visible, active, selected/pressed/checked, disabled, read-only, loading, success, warning, error, destructive, empty, and long-label states where applicable.
- [ ] Use native semantics and form relationships. Error helpers must set `aria-invalid` and `aria-describedby`; status components must pair icon/text/structure with color.
- [ ] Preserve 36px default, 32px compact, 40/48px prominent, and 44px mobile target contracts. No essential action may be hover-only.
- [ ] Use container queries for reusable row/card/cluster compaction and logical properties/safe-area utilities for future surfaces.
- [ ] Keep selectors within `.ui-*` component namespaces; do not style every legacy `button`, `input`, `details`, or `.card` globally.
- [ ] Commit static primitives separately.

## Task 5: Build keyboard, overlay, roving-focus, and live-region behavior

**Files:**

- Add: `static/js/ui/accessibility.js`
- Add: `static/js/ui/components/focus.js`
- Add: `static/js/ui/components/overlay.js`
- Add: `static/js/ui/components/roving-focus.js`
- Add: `static/js/ui/components/live-region.js`
- Add: `static/js/ui/components/index.js`

- [ ] Implement browser-local accessibility preferences with a coherent one-action Accessibility Mode plus independently adjustable granular settings.
- [ ] Respect operating-system reduced motion on first load without overwriting the user’s persisted effects choice.
- [ ] Implement dialog/sheet focus containment, Escape close where permitted, inert/background isolation, scroll locking, opener focus restoration, and safe behavior when the opener is removed.
- [ ] Implement ARIA tab/menu/segmented roving focus with Arrow/Home/End keyboard behavior and explicit selection/activation rules.
- [ ] Implement one restrained polite live-region announcer with duplicate suppression; never announce streaming token fragments.
- [ ] Keep every controller disposable and event-scoped. No polling interval, document-wide mutation observer, or implicit legacy adapter.
- [ ] Commit interactive primitives separately.

## Task 6: Build the repo-local component laboratory

**Files:**

- Add: `static/ui-next-lab.html`
- Add: `static/css/ui/lab.css`
- Add: `static/js/ui/lab.js`
- Modify: `web/app.py`
- Modify: `tests/test_ui_next_entry.py`

- [ ] Add authenticated `GET /ui-next/lab` with the same host-session boundary as `/ui-next`; anonymous callers redirect to `/login`; `/` remains unchanged.
- [ ] Render every primitive and relevant state from Tasks 3–5, including overlays, forms, task progression, skeleton/empty/no-result/error, confirmation, icon-only actions, long labels, and multiline localized-copy stress fixtures.
- [ ] Add a clearly labeled, non-functional shell-composition specimen (navigation rail, destination header, center reading surface, contextual panel, mobile navigation, and overlay band) solely to review hierarchy, spacing, surfaces, and z-order before WP-03 adds shell behavior.
- [ ] Add lab-only controls for all four curated themes, solid surfaces, reduced motion, Accessibility Mode, high contrast, large UI, large prose, roomy targets, and status markers.
- [ ] Make the lab useful without application API calls, timers, story data, classic scripts, or legacy CSS.
- [ ] Include semantic landmarks and section navigation so keyboard and screenshot tests can address stable examples.
- [ ] Commit the laboratory and authenticated route separately.

## Task 7: Exercise semantics, keyboard behavior, themes, and responsive geometry

**Files:**

- Add: `browser_tests/test_ui_foundation.py`
- Add: `tools/capture_ui_foundation.py`
- Add generated: `docs/design/sonder-ui-replacement/g1/foundation-report.json`
- Add generated PNGs: `docs/design/sonder-ui-replacement/g1/screenshots/**`

- [ ] Write browser tests before completing behaviors. Named breaks: missing accessible name/state/relationship; focus escapes; focus does not restore; roving keyboard rules fail; status is color-only; reduced motion arrives after paint; target is undersized; horizontal page overflow appears; console/page/API errors occur.
- [ ] Test desktop 1440×900, tablet 1024×768, mobile 390×844, narrow 360×640, short landscape 844×390, and 200% zoom-equivalent geometry.
- [ ] Exercise all four curated themes and the required preference matrix. Full pairwise coverage is sufficient where dimensions do not interact; every dimension must also run once with Accessibility Mode and long-copy stress.
- [ ] Capture deterministic screenshots for component families and viewports. Store exact commit, browser/platform, viewport, preference tuple, screenshot hash, overflow, target-size, contrast-proxy, and error results in JSON.
- [ ] Inspect the screenshots directly and record any approved limitations. Fix clipping, overlap, illegible state, unstable scene-tint influence, or misleading hierarchy before G1.
- [ ] Commit browser contracts and evidence separately.

## Task 8: Close and integrate Gate G1

**Files:**

- Add: `docs/design/sonder-ui-replacement/G1_FOUNDATION_REVIEW.md`
- Modify: `docs/design/sonder-ui-replacement/REQUIREMENTS_TRACEABILITY.md`
- Modify: `docs/guides/INTERFACE.md`
- Modify: `docs/UNBUILT.md` §2.26
- Regenerate: replacement inventories and frontend drift evidence through their owning command

- [ ] Perform four explicit reviews: product-flow applicability, visual-system and shell-composition conformance, responsive/accessibility behavior, and implementation/state ownership. Record findings and resolutions in the G1 review.
- [ ] Close only G1-owned requirements fully proven by this package (especially `ICON-*`). Add partial WP-01 evidence without closing cross-program `RESP-*`, `A11Y-*`, or WP-12 theme compatibility requirements prematurely.
- [ ] Run focused source/server/browser tests, replacement inventory/control-plane tests, `make map`, `make structure`, `make check`, and `make test-browser`. The seven already-baselined Directive structure findings are the only permitted external exception.
- [ ] Regenerate evidence twice and require a clean second run. Search the diff for raw colors outside theme/token files, external assets, emoji/glyph controls, polling, legacy selectors/imports, placeholders, TODOs, and accidental root-entry changes.
- [ ] Update §2.26 to `WP-01 complete; G1 foundation locked` only after every G1 proof item passes.
- [ ] Integrate the isolated branch into `interface`, refresh frontend drift against the integrated head, and verify the focused G1 suite on the merged branch.

## Plan self-review

- [x] **Complete:** every WP-01 deliverable and G1 proof item has an owning task, artifact, and verification path.
- [x] **Replacement-safe:** the plan does not import the candidate shell or patch legacy controls; every shared primitive is replacement-scoped.
- [x] **Boundary-safe:** no API, store, routing, persistence, engine, extension, or default-entry behavior is changed.
- [x] **Design-faithful:** the four curated themes, typography roles, geometry, density, motion, z-order, surfaces, state vocabulary, icons, and accessibility controls are explicit.
- [x] **Testable:** source checks catch architectural drift; browser tests exercise semantics and interaction; generated screenshots/report cover visual and responsive state.
- [x] **TDD-ready:** each executable behavior has named RED conditions before implementation.
- [x] **No false closure:** cross-program responsive/accessibility rows and WP-12 legacy-theme obligations remain open unless later packages prove them end to end.
- [x] **Provenance-safe:** the existing licensed font payload is retained, the candidate SVG is locally reviewed/inventoried, and no network asset is introduced.
