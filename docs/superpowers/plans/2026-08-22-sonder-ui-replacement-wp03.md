# Sonder UI replacement WP-03: application shell implementation plan

> Execute this plan in an isolated worktree from `interface`. Follow TDD for
> every behavioral task and keep `/` on the classic host. WP-03 builds the real
> replacement frame and closes G2; WP-04 and later packages replace the
> destination workflows inside it.

**Goal:** make `/ui-next` a real, responsive, authenticated Play / Library /
Settings application shell with truthful route/history/focus/scroll ownership,
an expert Go To launcher, and visible contained extension mounts, without
classic scripts, private DOM dependencies, hidden controls, or product claims
for workflows that later packages still own.

**Program authority:**

- `docs/superpowers/specs/2026-08-21-sonder-ui-full-replacement-design.md`
- `docs/guides/INTERFACE.md`
- `docs/guides/EXTENSIONS.md`
- `docs/guides/LANGUAGE_PACKS.md`
- `docs/design/sonder-ui-replacement/REQUIREMENTS_TRACEABILITY.md`
- `docs/design/sonder-ui-replacement/CANDIDATE_SALVAGE_LEDGER.md`
- `docs/design/sonder-ui-bible/docs/05_INFORMATION_ARCHITECTURE.md`
- `docs/design/sonder-ui-bible/docs/18_RESPONSIVE_AND_MOBILE.md`
- `docs/design/sonder-ui-bible/docs/22_UX_FLOWS_AND_EXPERT_ACCELERATION.md`

**Current integration head:** `4bfa23ab47fcc4afc5d81175fad7690a071441f5`

**Candidate disposition:** substantially adapt the three-zone composition,
indexed rail, neutral surfaces, and responsive transitions from the attached
candidate's `static/css/remaster-shell.css`. Adapt interaction ideas only from
`remaster/shell.js` and `remaster/inspector.js`. Rebuild routing, focus, scroll,
shortcuts, Go To, and extension hosting on the WP-02 services. Reject candidate
ID selectors, `!important` compatibility hiding, off-screen focusables,
`clickLegacy`, `window.S`, polling, mutation observers, inline style strings,
hard-coded English, fragile draft logic, global Settings actions in Play, and
the cosmetic `remaster/router.js` route depth.

## Responsibility boundaries

| Concern | Owner after WP-03 | Explicitly not owned here |
|---|---|---|
| Application frame and breakpoints | `static/css/ui/shell.css` | destination-specific product layout |
| Shell rendering/lifecycle | `static/js/ui-next/shell.js` | transcript, Library data model, Settings registry |
| Stable destination navigation | WP-02 router plus shell controller | inventing server selection truth |
| Scroll/focus restoration | stable route/region identities | retained DOM nodes or global scroll bags |
| Context inspector frame | responsive shell host | Story Tool implementations |
| Overlay stack | router layers plus foundation overlay primitive | legacy modal bridging |
| Shortcuts and Go To | one localized registry | workflow shortcuts owned by later packages |
| Extension placement | contained destination/view/tool/settings consumers | publishing extension v2 |
| Placeholder content | truthful unavailable/next-package states | pretend functional controls |
| Production entry | authenticated `/ui-next` only | changing `/` before G6 |

## Task 1: Pin the G2 shell contract and the candidate salvage boundary

**Files:**

- Add `tests/test_ui_shell_contracts.py`
- Add `browser_tests/test_ui_shell.py`
- Extend `tests/test_ui_next_entry.py`
- Extend `tests/test_ui_runtime_contracts.py`

1. Write failing source contracts for a semantic shell module/style, three and
   only three core destinations, one inspector host, one overlay host, one
   shortcut registry, one Go To controller, explicit release `wp03.1`, and no
   classic script, `window.S`, private host id, hidden duplicate, polling,
   mutation observer, inline style, or synthetic click dependency.
2. Write failing browser journeys for visible desktop and mobile navigation,
   route/refresh restoration, Back-unwinds-layer behavior, focus return,
   scroll ownership, typing guards, Go To, and representative extension mount/
   fault/unmount.
3. Pin the viewport/layout-state matrix: 360×800, 390×844, 430×932, 768×1024,
   844×390, 1024×600, 1024×768, 1280×800, 1440×900, and 640×360 as the
   200-percent zoom equivalent.
4. Record that the attached candidate files are reference input only; no
   candidate file is copied wholesale.
5. Run the focused files and record the expected missing-shell failures.
6. Commit `test(ui): define WP03 shell contracts`.

## Task 2: Advance one coherent replacement release

**Files:**

- Modify every `static/js/ui-next/*.js` release constant/import
- Modify replacement HTML asset queries
- Modify affected runtime/entry/browser/source tests

1. Advance the replacement graph and entry assets from `wp02.1` to `wp03.1` in
   one mechanical change; do not leave a mixed query graph.
2. Keep the WP-02 mixed-release rejection and immutable-release cache contract.
3. Preserve `/ui-next/runtime` as the non-product boundary fixture while
   `/ui-next` becomes the application entry. The laboratory remains a
   development/evidence fixture.
4. Prove old/new module mixtures fail before bootstrap and a coherent WP-03
   graph still reads `/api/bootstrap` exactly once.
5. Commit `chore(ui): advance replacement release to WP03`.

## Task 3: Build semantic shell markup and adaptive geometry

**Files:**

- Replace the temporary body in `static/ui-next.html`
- Add `static/css/ui/shell.css`
- Extend shell source/browser contracts

1. Add landmarks for primary navigation, destination header, center workspace,
   contextual inspector, overlay root, notice/task regions, and mobile bottom
   navigation. Core destination controls use local SVG icons plus visible Play,
   Library, and Settings labels.
2. Implement four named layout states derived from available space:
   `compact`, `medium`, `wide`, and `expansive`. Use CSS/container behavior for
   geometry and a JS-readable state only where behavior genuinely changes.
3. Desktop keeps indexed navigation left, current work center, and a bounded
   right inspector. Medium collapses the inspector to overlay behavior. Mobile
   stages one surface and keeps three-item bottom navigation above safe areas.
4. Use logical properties, semantic tokens, local assets, and layer-owned CSS.
   No shell rule targets a classic id or hides a legacy control.
5. Preserve usable story measure and prevent continuous overlap among workspace,
   inspector, overlays, notices/tasks, and bottom navigation.
6. Prove zero horizontal overflow, 44 px touch targets, short-height behavior,
   safe-area padding, high contrast, reduced motion, solid surfaces, and large
   UI/prose composition across the matrix.
7. Commit `feat(ui): add responsive application frame`.

## Task 4: Bind the real shell to coherent runtime state

**Files:**

- Add `static/js/ui-next/shell.js`
- Modify `static/js/ui-next/bootstrap.js`
- Modify `static/js/ui-next/main.js`
- Extend store/runtime/shell tests

1. Treat `data-ui-next-entry="application"` as an authenticated host boot.
   Start the shell only after store, router, localizer, extensions, tasks,
   notices, diagnostics, and bootstrap projections are coherent.
2. Render from store selectors and registry change callbacks. Shell teardown
   unsubscribes selectors, listeners, resize/media hooks, overlay controllers,
   shortcuts, and extension mounts before runtime services stop.
3. Project bootstrap counts and safe labels only. Do not fetch destination data
   a second time, infer an active story not named by route/local presentation,
   or populate later workflow slices with decorative fixtures.
4. Give loading, unavailable, confirmed-empty, fallback, error, and ready
   states distinct shell presentation. Development wording is removed from the
   application entry.
5. Keep `window.Sonder` as the sole migration global and remove it on teardown.
6. Commit `feat(ui): bind shell to runtime state`.

## Task 5: Make navigation, restoration, and orientation truthful

**Files:**

- Modify `static/js/ui-next/router.js`
- Add `static/js/ui-next/navigation-state.js`
- Modify `static/js/ui-next/shell.js`
- Extend router/storage/browser tests

1. Define stable placeholder routes for Play, Library scopes, Settings
   sections, Story Tools, and namespaced extension views without claiming that
   later data/detail workflows exist. Unknown, deleted, disabled, or retired
   targets fall back to the nearest rendered parent with localized explanation.
2. On a hashless entry, restore only a previously validated stable route.
   Explicit deep links win. Persist destination/subview only after the router
   has canonicalized it.
3. Own scroll per stable route and named scroll region in the versioned local
   navigation record. Bound entry count/values; restore after the destination
   exists; returning from a detail/layer lands at the prior position.
4. Route changes focus the destination heading unless restoring a transient
   layer's explicit focus identity. Never retain DOM nodes in history or local
   storage.
5. Browser Back closes Go To, inspector sheets, and extension views before it
   leaves the current destination. Forward restores only a still-valid layer.
6. Every destination header shows current location, active scope/subview,
   parent route where applicable, truthful save availability, primary next
   action, and a stable More location without fake actions.
7. Commit `feat(ui): own shell navigation and restoration`.

## Task 6: Add truthful destination placeholders and the inspector frame

**Files:**

- Add `static/js/ui-next/destinations.js`
- Add `static/js/ui-next/inspector-host.js`
- Modify `static/js/ui-next/shell.js`
- Extend browser tests

1. Play shows story-first empty/selection context, a single Story Tools entry,
   and no global configuration controls. It does not render a fake transcript,
   composer, send button, or tool result before WP-04/WP-05.
2. Library shows type/scope orientation and authoritative bootstrap counts, but
   no fake search result, favorite, draft, association, or editor behavior.
3. Settings shows the approved category orientation and plain next-step state,
   but no launcher that claims a setting is editable before WP-08.
4. The desktop inspector has bounded width/pin/open/close state in `panes` and
   never forces center content below its minimum. Medium/mobile use a routed
   sheet with explicit close/Back, focus containment/restoration, safe areas,
   and preserved parent scroll.
5. Tool placeholders are inert explanatory rows. No hidden legacy control,
   current modal, or synthetic click is mounted behind them.
6. Commit `feat(ui): add truthful shell destinations`.

## Task 7: Implement one guarded shortcut registry and Go To launcher

**Files:**

- Add `static/js/ui-next/shortcuts.js`
- Add `static/js/ui-next/go-to.js`
- Modify `static/js/ui-next/shell.js`
- Extend localization and browser tests

1. Register `Ctrl/Cmd+K` for Go To, `Ctrl/Cmd+,` for Settings where safe,
   `/` for the current surface's declared search owner, and Escape for the top
   transient layer. Later workflow shortcuts register through the same owner-
   attributed service.
2. Ordinary shortcuts do not fire from input, textarea, select,
   contenteditable, composing/IME, modified text entry, or an open modal that
   owns the key. The registry rejects duplicate core bindings and resolves
   extension collisions without replacing a core shortcut.
3. Go To is a localized dialog with search, roving result focus, empty/no-result
   states, plain context, Escape, Back history, and opener focus restoration.
   It accelerates but never replaces visible navigation.
4. Results include three core destinations, rendered stable subviews, and
   current registered extension destinations/views. No unbuilt story/item/
   control result is advertised.
5. All labels and shortcut help are catalogued; story and extension-provided
   data remains untranslated unless the extension supplied UI copy.
6. Commit `feat(ui): add guarded Go To navigation`.

## Task 8: Consume extension registrations through the shell boundary

**Files:**

- Add `static/js/ui-next/extension-host.js`
- Modify `static/js/ui-next/extensions.js`
- Modify `static/js/ui-next/shell.js`
- Extend the v1 fixture and browser tests

1. Render internal destination, Play-tool, Add-ons-settings, and task-provider
   registrations only in their declared hosts. Render v1 legacy views through a
   labeled Add-on Views secondary surface; never place them into core primary
   navigation or hand them private shell nodes.
2. Namespace stable view routes by owner plus registration id. Duplicate ids
   from different owners coexist; an extension cannot replace Play, Library,
   Settings, a core shortcut, or another owner's mount.
3. Mount through `registry.run`, contain sync/async failures, show a plain
   recoverable boundary, and retire through the WP-02 three-fault policy.
4. Registry change, disable, retire, route fallback, and runtime teardown must
   unmount the active view, remove its route/result/shortcut entries, restore
   focus, and leave the core shell operable.
5. Prove the representative v1 fixture visibly mounts, navigates, receives an
   event/API result, fails safely, and completely unmounts with zero private
   host id usage. This closes only the G2 shell boundary; extension v2 and
   installed compatibility remain WP-12.
6. Commit `feat(ui): host extensions in the shell`.

## Task 9: Verify current-server integration without changing authority

**Files:**

- Modify `web/app.py` only if the authenticated entry/cache contract requires it
- Extend `tests/test_ui_runtime_routes.py`
- Extend shell server/browser tests

1. Prove `/ui-next` remains host-session authenticated, `/` remains classic,
   and login/guest entries remain lightweight and unchanged.
2. Boot once from the current `/api/bootstrap`; verify current stories,
   characters, personas, lorebooks, language projection, extensions, and safe
   settings reach only their owned shell summaries.
3. Prove 401 redirects/requests login once, 403 stays inline, extension asset
   failure cannot block shell ready, and runtime teardown cancels in-flight
   shell work.
4. Verify no credential/session material reaches DOM, route, local state,
   notices/tasks, Go To results, extension state, or diagnostics.
5. Commit `test(ui): prove current shell integration`.

## Task 10: Close responsive, accessibility, localization, and visual review findings

**Files:**

- Extend `browser_tests/test_ui_shell.py`
- Extend `tests/test_ui_catalog_extraction.py`
- Modify shell source as findings require

1. Exercise pointer, touch, and keyboard journeys at every reference viewport,
   plus long Japanese copy, 200-percent zoom equivalent, Accessibility Mode,
   high contrast, solid surfaces, large UI/prose, and reduced motion.
2. Verify landmark order, one H1 per destination, current-page semantics,
   accessible icon labels, dialog/sheet naming, live-region restraint, focus
   visibility, no focus behind overlays, and 44 px touch targets.
3. Verify primary navigation never scrolls horizontally, mobile safe areas are
   honored, landscape reduces secondary chrome first, and no destination,
   Story Tools route, Go To, or extension-view launcher becomes unreachable.
4. Regenerate English UI copy, complete Japanese parity, and prove long labels
   wrap/truncate only where meaning remains available.
5. Conduct and record product-flow, visual-system, responsive, and
   implementation/state-preservation reviews. Fix every P0/P1 and record all
   other findings with explicit disposition.
6. Commit `fix(ui): resolve G2 shell review findings`.

## Task 11: Capture deterministic G2 evidence

**Files:**

- Add `tools/capture_ui_shell.py`
- Add generated `docs/design/sonder-ui-replacement/g2/shell-report.json`
- Add generated screenshots under `docs/design/sonder-ui-replacement/g2/screenshots/`
- Add `docs/design/sonder-ui-replacement/G2_SHELL_REVIEW.md`

1. Capture at least desktop, medium, tablet portrait, common phone, narrow
   phone, phone landscape, short desktop, zoom equivalent, long Japanese,
   Accessibility Mode, Go To, inspector sheet, and extension mount/failure.
2. Record exact source commit/tree hash, browser/platform, layout state,
   overflow, target sizes, landmarks, focus result, visible capabilities,
   console/page errors, API request counts, screenshot hashes, and sensitive-
   data scan.
3. Run two complete captures and require byte-identical report/screenshots.
4. The review names every candidate idea retained and rejected and confirms
   screenshots are presentation evidence only.
5. Commit `test(ui): capture G2 application shell`.

## Task 12: Qualify WP-03 and close G2 without over-claiming later workflows

**Files:**

- Modify `docs/design/sonder-ui-replacement/REQUIREMENTS_TRACEABILITY.md`
- Modify `docs/guides/INTERFACE.md`
- Modify `docs/guides/EXTENSIONS.md`
- Modify `docs/guides/LANGUAGE_PACKS.md`
- Modify `docs/UNBUILT.md` section 2.26
- Regenerate `docs/CODE_MAP.md` and replacement inventories/drift

1. Add exact WP-03 evidence to `IA-*`, `RESP-*`, `A11Y-*`, `ARCH-*`,
   `EXT-*`, and verification rows. Close only shell requirements whose real
   route/focus/responsive/extension consumers are complete. Leave destination
   data, Play, Library, Settings, auth/guest, compatibility, and cutover rows
   open.
2. Regenerate English catalog, code map, structure artifacts, replacement
   inventories, and frontend drift against the integration head.
3. Run shell/runtime/source/server/browser focus, compile all maintained source
   roots, `tools/project_check.py`, full pytest, and all browser tests. Record
   the seven existing root-only Directive integration-test facade findings
   separately from replacement UI findings.
4. Re-run deterministic shell/release evidence. Inspect every capture at native
   size and verify keyboard, 200-percent zoom equivalent, long Japanese,
   session expiry, extension failure, Back/Forward, and scroll restoration.
5. Commit `docs(ui): lock G2 application shell`, fast-forward into `interface`,
   refresh drift to the integrated SHA, re-run focused merged verification,
   and remove the clean worktree and merged branch.

## G2 gate checklist

- [ ] `/ui-next` is the real authenticated replacement shell; `/` is unchanged.
- [ ] Play, Library, and Settings are always visibly reachable.
- [ ] Desktop left/center/right and mobile bottom/staged models are proven.
- [ ] Compact, medium, wide, and expansive states have executable geometry.
- [ ] Route, refresh, Back/Forward, focus, and scroll ownership are truthful.
- [ ] Go To and shortcuts are localized, discoverable, guarded, and collision-safe.
- [ ] Play contains no global Settings controls or fake workflow actions.
- [ ] Inspector and overlay lifecycle preserve parent state and focus.
- [ ] Representative v1 extension mount/fault/unmount is visible and contained.
- [ ] No classic script, private DOM id, hidden control, polling, mutation
      observer, synthetic click, mixed release, or extra global is required.
- [ ] Full viewport, touch, keyboard, accessibility, and localization evidence passes.
- [ ] Current engine, persistence, auth, guest, language, and classic host tests remain green.
- [ ] WP-03 is complete and G2 is locked; WP-04 is next.
