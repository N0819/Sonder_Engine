# Sonder UI Replacement WP-00 Implementation Plan

> **Required sub-skill:** Use `superpowers:executing-plans` to implement this plan task by task. Use `superpowers:test-driven-development` for executable behavior, `superpowers:verification-before-completion` before claiming G0, and `superpowers:finishing-a-development-branch` after the gate passes.

**Goal:** Establish the trustworthy control plane, current-source baseline, traceability, and isolated development entry required by G0 before replacement product code begins.

**Architecture:** Current Sonder source remains behavioral authority. The imported Design Bible is contextual design authority under `docs/design/`; the maintained `docs/guides/INTERFACE.md` reconciles it with engine, persistence, security, language-pack, and extension contracts. One generated inventory command records the current UI surfaces and integration seams. One browser recorder captures repeatable legacy behavior, screenshots, and performance measures. A separately authenticated `/ui-next` entry loads a native ES-module fixture without legacy host scripts or CSS and without changing `/`.

**Tech Stack:** FastAPI, native browser ES modules, Python 3.11+, standard-library source inspection, pytest, Playwright/Chromium, Markdown and JSON evidence.

**Spec:** `docs/superpowers/specs/2026-08-21-sonder-ui-full-replacement-design.md` § WP-00 and G0.

**Global Constraints:** Preserve the current database, API, authentication, guest, localization, extension-v1, archive/checkpoint, and information-firewall contracts. Do not copy the candidate tree wholesale. Do not make the replacement entry the default. `docs/UNBUILT.md` remains the sole unfinished-work status register; all ledgers created here are evidence and ownership maps, not competing roadmaps. Keep generated artifacts deterministic. Do not attribute the seven already-known Directive test-harness structure failures to this package.

---

## Task 1: Import and reconcile the design authority

**Files:**

- Add: `docs/design/sonder-ui-bible/**` from the 1.0 reference package
- Add: `docs/guides/INTERFACE.md`
- Modify: `docs/README.md`
- Modify: `docs/UNBUILT.md` §2.26
- Modify: `docs/CREDITS.md`

- [ ] Copy every file named by the Bible's `MANIFEST.md` into `docs/design/sonder-ui-bible/`, preserving names and contents.
- [ ] Verify the imported manifest with a deterministic Python one-liner: every listed file exists, byte counts and SHA-256 values match, and there are no unexpected files under the imported root.
- [ ] Write `docs/guides/INTERFACE.md` as current implementation authority. State the authority order, full-replacement outcome, native-module/no-required-build boundary, current server and persistence authority, UI string boundary, extension-v1 compatibility requirement, security/content-rendering rules, and the gate model.
- [ ] Record the accepted `ARCH-12` correction: there will be no single global compatibility bridge; temporary adapters are narrow, explicit, evented, owner-attributed, and deleted at cutover.
- [ ] Add the Bible and maintained interface guide to `docs/README.md` with the correct authority labels.
- [ ] Update §2.26 from “implementation has not started” to “WP-00 in progress,” link this plan, and preserve the entry as the single status authority.
- [ ] Add reference provenance and the supplied package to `docs/CREDITS.md`; do not imply ownership or a license not present in the package.
- [ ] Commit: `docs(ui): import and reconcile design bible`

## Task 2: Import the 170-row requirement matrix and assign ownership

**Files:**

- Add: `docs/design/sonder-ui-replacement/REQUIREMENTS_TRACEABILITY.md`
- Add: `tests/test_ui_replacement_control_plane.py`

- [ ] Create the focused test first. It must parse Markdown table rows, assert exactly 170 unique requirement IDs across the 15 declared families (including all 14 `A11Y` rows), require a valid WP-00–WP-14 owner for every row, and require the amended `ARCH-12` decision.
- [ ] Run `python -m pytest -q tests/test_ui_replacement_control_plane.py` and confirm the expected RED failure because the traceability artifact does not exist.
- [ ] Import the candidate's `13_REQUIREMENTS_TRACEABILITY.md` as evidence, replace historical workstream ownership with the program work-package ownership table from the spec, and add columns for disposition, current implementation/evidence, gate, and status.
- [ ] Apply all adoption-audit corrections: polling/global bridge rejected; deep routing, Library scopes/search, Settings registry, mobile vitals, localization, draft isolation, extension v2, and legacy removal remain open; candidate-reported passes are not current evidence.
- [ ] Mark every row `open` except WP-00 governance/baseline rows that this package actually closes. Do not copy candidate “conforming” claims as status.
- [ ] Run the focused test and confirm GREEN.
- [ ] Commit: `docs(ui): establish requirement ownership`

## Task 3: Build deterministic current-source inventories

**Files:**

- Add: `tools/ui_replacement_inventory.py`
- Add: `tests/test_ui_replacement_inventory.py`
- Add generated: `docs/design/sonder-ui-replacement/baseline/source-inventory.json`
- Add generated: `docs/design/sonder-ui-replacement/CAPABILITY_LEDGER.md`
- Add generated: `docs/design/sonder-ui-replacement/SURFACE_INVENTORY.md`
- Add generated: `docs/design/sonder-ui-replacement/API_PERSISTENCE_MAP.md`
- Add generated: `docs/design/sonder-ui-replacement/GLOBAL_DOM_INVENTORY.md`
- Add generated: `docs/design/sonder-ui-replacement/THEME_EXTENSION_INVENTORY.md`
- Add: `docs/design/sonder-ui-replacement/CANDIDATE_SALVAGE_LEDGER.md`

- [ ] Write tests first against a small temporary fixture tree. Named breaks: a route, HTML surface, script, global, DOM ID, theme, or extension mount added to source but omitted from inventory; nondeterministic output; a capability without a replacement owner/disposition.
- [ ] Run `python -m pytest -q tests/test_ui_replacement_inventory.py` and confirm RED because the command does not exist.
- [ ] Implement a standard-library CLI that parses FastAPI route decorators, static HTML entry/script/style/ID surfaces, JavaScript browser globals and DOM-ID references, CSS theme declarations/custom properties, language UI catalogs, extension UI routes/mount points, and current persistence/API references. Emit stable sorted JSON and Markdown.
- [ ] Add hand-curated capability records for workflows source parsing cannot infer: Play/stream/reroll/frame/scrollback, Library CRUD/import/export/associations, Story Tools, settings categories, New Story, auth/session, guest, themes/accessibility, localization, extensions, notices/tasks, and archive/checkpoint flows. Each record must name current source/tests, replacement WP, mobile requirement, and disposition.
- [ ] Run the tool against the exact pre-package head `c99173dd8b7544d6ef7c53e9ed837fc0f841bbcc`; record that SHA and candidate baseline `73a380a0df2f6b139c98d66da9005489bd549d1d` in the output.
- [ ] Write the candidate salvage ledger from the adoption audit at file granularity: `accept`, `adapt`, `rebuild`, `reference`, `reject`, or `defer`, with acceptance evidence and target WP.
- [ ] Run focused tests, regenerate twice, and assert the second run produces no diff.
- [ ] Commit: `build(ui): generate replacement inventories`

## Task 4: Lock frontend drift and unfinished-defect ownership

**Files:**

- Add: `docs/design/sonder-ui-replacement/FRONTEND_DRIFT.md`
- Modify: `docs/design/sonder-ui-replacement/CAPABILITY_LEDGER.md`
- Modify: `docs/design/sonder-ui-replacement/REQUIREMENTS_TRACEABILITY.md`

- [ ] Compare `73a380a0df2f6b139c98d66da9005489bd549d1d..c99173dd8b7544d6ef7c53e9ed837fc0f841bbcc` for `static/`, `web/`, language catalogs, extension contracts, and browser/frontend tests. Classify every changed path as behavior, contract, presentation, test, or generated evidence.
- [ ] Record whether the candidate touched the same path and the required rebase rule. Never resolve a collision by replacing a current file with the older snapshot.
- [ ] Search all of `docs/UNBUILT.md` for player-facing/UI-related items. Link each to a requirement and work-package owner without removing the original register entry.
- [ ] Assign §1.66 to WP-05 and add the explicit replacement requirement: story content, vitals/conditions, floating utilities, and composer may never overlap continuously across the supported width/zoom matrix.
- [ ] Add a drift-refresh command to the inventory tool and document that it runs at every package integration.
- [ ] Run the control-plane and inventory tests.
- [ ] Commit: `docs(ui): lock drift and defect ownership`

## Task 5: Record current browser behavior, screenshots, and performance

**Files:**

- Add: `tools/capture_ui_baseline.py`
- Add: `tests/test_ui_baseline_recorder.py`
- Add generated: `docs/design/sonder-ui-replacement/baseline/current-ui-baseline.json`
- Add generated PNGs: `docs/design/sonder-ui-replacement/baseline/screenshots/**`
- Add: `docs/design/sonder-ui-replacement/BASELINE_AND_BUDGETS.md`

- [ ] Write tests first around recorder data validation and budget derivation. Reject missing journeys, non-finite measures, absent viewport metadata, unexpected network-idle traffic, and budgets tighter than the observed baseline without a recorded rationale.
- [ ] Run `python -m pytest -q tests/test_ui_baseline_recorder.py` and confirm RED because the recorder does not exist.
- [ ] Implement a Playwright recorder using controlled complete API fixtures. Capture current Play populated/empty/500-turn/streaming, Library/current lists at normal and scale loads, Settings, New Story entry, login, guest join, representative extension, desktop 1440×900, tablet 1024×768, mobile 390×844, narrow 360×640, landscape 844×390, and short 1280×640 states.
- [ ] Record boot-to-interactive, 500-turn render and scroll responsiveness, 1,000-record Library/list rendering and query response, effects-enabled frame cadence, repeated-navigation listener/DOM growth, and idle API request count. Keep story/user content synthetic and credentials absent.
- [ ] Store exact commit, browser version, platform, fixture sizes, viewport, repeat count, median, p95 where available, and screenshot hashes in JSON.
- [ ] Derive release budgets in `BASELINE_AND_BUDGETS.md`: no regression greater than 20% for boot or long-transcript p95 without evidence; zero steady-state polling requests while idle in the replacement; bounded DOM/listener growth after 50 navigation cycles; no long task above 200 ms attributable to replacement code in the measured journeys; no overlap/overflow at the recorded viewport matrix.
- [ ] Run the recorder twice enough to distinguish noise from a structural regression, retain the more conservative baseline, and validate the JSON through the focused tests.
- [ ] Commit: `test(ui): lock current browser baseline`

## Task 6: Add the isolated authenticated replacement entry via TDD

**Files:**

- Add: `static/ui-next.html`
- Add: `static/js/ui-next/main.js`
- Add: temporary WP-00 development stylesheet (removed by WP-01)
- Modify: `web/app.py`
- Add: `tests/test_ui_next_entry.py`
- Add: `browser_tests/test_ui_next_entry.py`

- [ ] Write the server test first. Named breaks: anonymous requests can open `/ui-next`; authenticated requests do not receive the fixture; `/` changes; or the new route exposes host data itself.
- [ ] Run `python -m pytest -q tests/test_ui_next_entry.py` and confirm RED with a 404 for `/ui-next`.
- [ ] Add `GET /ui-next`. Verify the host-session cookie at the route, redirect anonymous callers to `/login`, and serve the replacement entry only to a valid host session. Do not modify the API middleware or root route.
- [ ] Write the browser test first. Named breaks: classic host scripts/styles load, the module fails to boot, semantic landmarks/heading are absent, or the page emits console/page errors.
- [ ] Run `python -m pytest -q browser_tests/test_ui_next_entry.py` and confirm RED before adding entry assets.
- [ ] Add a minimal semantic development shell whose only responsibility is to prove the native-module entry, version marker, and test seam. It must load no legacy host CSS/JS, use no `window.S`, make no API request, create no polling timer, and contain no hidden legacy controls. WP-01 and WP-02, not this fixture, own design tokens and application state.
- [ ] Run the focused Python and browser tests and confirm GREEN.
- [ ] Re-run the legacy root/session-expiry browser tests to prove the default UI is unchanged.
- [ ] Update the surface inventory and traceability evidence for the new development entry.
- [ ] Commit: `feat(ui): add isolated replacement entry`

## Task 7: Close and review the G0 package

**Files:**

- Modify: `docs/guides/INTERFACE.md`
- Modify: `docs/UNBUILT.md` §2.26
- Modify: `docs/design/sonder-ui-replacement/REQUIREMENTS_TRACEABILITY.md`
- Modify generated inventories/evidence only through their owning commands

- [ ] Run the focused WP-00 suite:
  `python -m pytest -q tests/test_ui_replacement_control_plane.py tests/test_ui_replacement_inventory.py tests/test_ui_baseline_recorder.py tests/test_ui_next_entry.py browser_tests/test_ui_next_entry.py`.
- [ ] Run `make map` and `make structure`; classify only the already-baselined seven Directive root-import findings as pre-existing if they reproduce unchanged.
- [ ] Run `make check` and `make test-browser`. Record exact commands, commit, counts, duration, and every failure in the baseline evidence. G0 may use only the named pre-existing structure exception; any new failure blocks integration.
- [ ] Regenerate all inventories/baselines and confirm `git diff --exit-code` for deterministic artifacts.
- [ ] Review the complete diff against every WP-00 deliverable and every G0 proof item. Search for placeholders, historical status claims, unmapped requirements, omitted current capabilities, secrets/story content, and accidental default-entry changes.
- [ ] Update `docs/UNBUILT.md` to “WP-00 complete; G0 baseline locked” only if the package meets its exit gate. Keep §2.26 until WP-14.
- [ ] Update the requirement matrix with exact evidence links; do not close product requirements merely because they have an owner.
- [ ] Commit: `docs(ui): lock G0 replacement baseline`
- [ ] Integrate the worktree branch into `interface` without replacing unrelated branch work, then refresh the drift record against the new integration head.

## Plan self-review

- [x] **Completeness:** every WP-00 deliverable and G0 proof item from the program spec has an owning task; all 170 reference requirements, including the previously miscounted 14-row `A11Y` family, have program ownership; no TODO or implementation placeholder remains.
- [x] **Spec alignment:** the plan creates control/evidence infrastructure and a development seam only; it does not begin WP-01 visual foundations or change the default host UI.
- [x] **Task decomposition:** governance, traceability, inventories, drift, browser evidence, and the entry seam have separate commits and focused tests.
- [x] **Buildability:** paths, commands, expected RED failures, generated artifacts, and acceptance conditions are explicit.
- [x] **Authority consistency:** `docs/UNBUILT.md` remains the sole work-status register; the Bible remains design context; `INTERFACE.md` becomes maintained current authority.
- [x] **Naming consistency:** the route is `/ui-next`; assets use `ui-next`; program ownership uses WP-00–WP-14; the baseline head is `c99173dd8b7544d6ef7c53e9ed837fc0f841bbcc`.
- [x] **Safety:** no database migration, default-entry switch, extension-contract change, credential capture, or historical whole-tree copy is authorized by WP-00.
