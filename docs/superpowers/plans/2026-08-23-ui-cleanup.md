# Sonder UI cleanup implementation plan

> **Goal:** Repair the confirmed visual/interaction defects in the approved UI
> cleanup ledger and leave a verified local result on `interface` for review.

Status: corrective release implemented and verified; integration is approved.

Specification and acceptance ledger:
`docs/design/sonder-ui-replacement/UI_CLEANUP_FIX_LIST.md`.

## Task 1: Lock the defects with browser and store regressions

**Files:**

- Modify: `browser_tests/test_ui_settings.py`
- Modify: `browser_tests/test_ui_shell.py`
- Modify: `browser_tests/test_ui_play.py`
- Modify: `browser_tests/test_ui_story_tools.py`
- Modify: `browser_tests/test_ui_library.py`
- Modify: nearest store unit test under `browser_tests/` or `tests/`

Add focused tests for scrolling, working appearance preferences, minimum target
sizes, stale-subscriber notification, empty Play, semantic Story Tool modes and
detail staging, unique SVG icons, the single-purpose Library hierarchy, explicit
Story selection before Play, and first-class memory-search model guidance.
Run each nearest group and confirm it fails for the expected pre-fix reason.

## Task 2: Repair Settings geometry and appearance contracts

**Files:**

- Modify: `static/css/ui/shell.css`
- Modify: `static/css/ui/settings.css`
- Modify: `static/css/ui/tokens.css`
- Modify: `static/css/ui/play.css`
- Modify: `static/js/ui-next/settings-view.js`
- Modify: `static/js/ui-next/bootstrap.js`
- Modify: appearance/preflight module discovered from the code map

Constrain nested grid tracks, make the detail pane the scroll owner, add the
prose-size preview, implement Comfortable/Compact density consumers, normalize
legacy values, and make Effects the canonical persisted/runtime attribute.
Raise responsive control targets without expanding desktop Compact density.
Run the Settings and atmosphere browser groups green.

## Task 3: Repair state notification and empty Play

**Files:**

- Modify: `static/js/ui-next/store.js`
- Modify: `static/js/ui-next/play-view.js`
- Modify: `static/css/ui/play.css`

Ignore subscribers removed during the current notification. Replace empty
Play's inert tool list with honest inspector guidance and add New Story plus
Open Library actions in a deliberate empty-stage composition. Run the store,
shell-transition, and Play browser groups green.

## Task 4: Replace Story Tool resize states with semantic modes

**Files:**

- Modify: `static/js/ui-next/inspector-host.js`
- Modify: `static/js/ui-next/story-tools-view.js`
- Modify: `static/css/ui/story-tools.css`
- Modify: `static/css/ui/shell.css`

Implement Expanded, Compact, and Rail modes, migrate legacy persistence, hide
mode-inappropriate text while retaining accessible names/tooltips, and stage
the selected tool as a focused detail view with an All tools control. Run Story
Tools and shell browser groups green.

## Task 5: Give Library one hierarchy and replace glyph icons

**Files:**

- Modify: `static/js/ui-next/library-view.js`
- Modify: `static/css/ui/library.css`
- Modify: `static/js/ui-next/new-story.js`
- Modify: `static/css/ui/new-story.css`
- Modify: `static/css/ui/play.css`
- Modify: `static/assets/icons/sonder-icons.svg`

Keep Library filter/scope navigation on the left, make the center the canonical
material ledger, remove duplicate statistics/context/actions, retain compact
list-to-detail staging, standardize Lore terminology, and replace actionable
text glyphs with local SVG. Add unique SVG symbols for Conditions, Frames, and
Multiplayer. Run Library, Play, New Story, and icon regressions green.

## Task 6: Update maintained interface authority and the ledger

**Files:**

- Modify: `docs/guides/INTERFACE.md`
- Modify: `docs/design/sonder-ui-replacement/UI_CLEANUP_FIX_LIST.md`

Document cross-surface overflow ownership, canonical appearance values,
semantic Story Tool modes/migration, the calibrated Library responsibility
split, and responsive target rules. Reconcile the approved product requirements
into the cleanup ledger, keep authoring interaction design and capability parity
as immediate follow-ups, keep user-authored themes as a separately scoped
backlog feature, and retain no separate intake document. Mark fixed rows and
add verification evidence.

## Task 7: Render and verify

Capture repaired deterministic renders at every applicable reference viewport.
Compare them side by side with supplied references, inspect keyboard focus and
responsive sheet behavior, then run the complete browser collection, focused
catalog checks, and the repository's full pytest gate using the pinned virtual
environment. Remove only audit artifacts created by this run.

## Task 8: Hold for review

Review the final diff and report the verified local state. Do not commit or push
until the 2026-08-23 hold is explicitly lifted.

The hold was lifted on 2026-08-23 after live testing exposed that the deployed
browser could still retain the old immutable UI bundle.

## Task 9: Correct Settings input routing and release-cache coherence

**Files:**

- Modify: `static/js/ui-next/settings-view.js`
- Modify: `static/css/ui/settings.css`
- Modify: `static/ui-next.html` and the replacement release graph
- Modify: `web/app.py`
- Modify: `tests/test_ui_runtime_contracts.py`
- Modify: `browser_tests/test_ui_settings.py`

Forward vertical wheel and keyboard paging from fixed Settings chrome to the
one detail scroll owner while preserving nested and horizontal scrolling. Give
that owner explicit region/focus semantics. Replace the reused immutable asset
identifier with a content-fingerprinted release and make future asset edits
without a release rotation fail a source contract.

## Task 10: Re-audit, verify, and integrate

Replace the external-`use` layout-box icon assertion with actual fill-and-stroke
view-box measurement, rerun deterministic Settings captures and the full
responsive browser matrix, compare against the approved references, update the
ledger with the cache-delivery finding, run the complete repository gate, then
commit and push the verified correction to `interface`.
