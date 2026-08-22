# Sonder UI replacement WP-02: runtime boundaries implementation plan

> Execute this plan in an isolated worktree from `interface`. Follow TDD for
> every behavioral task and keep `/` on the classic host. WP-03, not this work
> package, owns the visible Play/Library/Settings shell.

**Goal:** make the replacement entry operate current Sonder through explicit,
testable runtime services without classic globals, private DOM dependencies,
polling, hidden controls, or a mandatory build toolchain.

**Program authority:**

- `docs/superpowers/specs/2026-08-21-sonder-ui-full-replacement-design.md`
- `docs/guides/INTERFACE.md`
- `docs/guides/EXTENSIONS.md`
- `docs/guides/LANGUAGE_PACKS.md`
- `docs/design/sonder-ui-replacement/REQUIREMENTS_TRACEABILITY.md`
- `docs/design/sonder-ui-replacement/CANDIDATE_SALVAGE_LEDGER.md`

**Current integration head:** `51600051e286e2224a667a2504ec54fae958419e`

**Candidate disposition:** adapt the candidate native `remaster/main.js` idea
only. Rebuild the router. Reject `remaster/bridge.js`, `window.S`, 500 ms
polling, `clickLegacy`, hidden controls, and the candidate's unconsumed v2 slot
API. Preserve the documented public v1 `window.Sonder` contract through one
narrow adapter backed by the new registry.

## Responsibility boundaries

| Concern | Owner after WP-02 | Explicitly not owned here |
|---|---|---|
| Boot and teardown | `static/js/ui-next/bootstrap.js` | destination rendering |
| Network and request identity | `static/js/ui-next/api.js` | server semantics or retries of consequential actions |
| Application state | `static/js/ui-next/store.js` | duplicated server truth |
| Route parsing/history contract | `static/js/ui-next/router.js` | final shell navigation UI |
| Interface language | `static/js/ui-next/localization.js` | story/model/user-content translation |
| Tasks/notices/errors | dedicated runtime services | destination-specific presentation |
| Browser-local state | `static/js/ui-next/storage.js` | credentials or server-owned records |
| Save sequencing | `static/js/ui-next/save-policy.js` | inventing undo for routes without receipts |
| Safe content/credentials | narrow rendering and submission modules | arbitrary HTML compatibility |
| Extension lifecycle | module registry plus v1 adapter | final slot placement or extension v2 publication |
| Release coherence | versioned native-module graph and response headers | a bundler/service worker |

## Task 1: Pin executable runtime contracts before implementation

**Files:**

- Add `tests/test_ui_runtime_contracts.py`
- Add `browser_tests/test_ui_runtime.py`
- Add `tests/test_ui_runtime_routes.py`

1. Write failing source contracts for the required runtime modules, one release
   identifier, the permitted state slices, no interval polling, no `window.S`,
   no hidden-control clicks, no direct `innerHTML`, and exactly one permitted
   global adapter name: `Sonder`.
2. Write failing browser contracts that dynamically import the services and
   exercise them without the classic scripts.
3. Write failing FastAPI contracts for the authenticated runtime harness and
   replacement cache headers.
4. Run the three files and record the expected missing-module/route failures.
5. Commit `test(ui): define WP02 runtime contracts`.

## Task 2: Add a coherent native-module release graph

**Files:**

- Add `static/js/ui-next/release.js`
- Add `static/js/ui-next/bootstrap.js`
- Modify `static/js/ui-next/main.js`
- Modify `static/ui-next.html`
- Modify `web/app.py`

1. Give the replacement graph one release id. The HTML loads the entry with a
   release query; the bootstrap imports every runtime dependency with that same
   query and refuses any module exporting a different release id before it
   starts services.
2. Send every host/login/guest/replacement HTML entry with `no-store` so an old
   document cannot name a new graph. Unversioned shared/classic assets must
   revalidate. Send release-query replacement JS, CSS, and icon assets with
   immutable private caching, and put the same query on every replacement
   entry asset reference. This changes cache coherence, not classic behavior.
3. Install a global error/rejection boundary that emits a sanitized runtime
   failure event and stable fatal state without exposing stack text to ordinary
   UI. Diagnostics may receive detail only when explicitly enabled.
4. Make `boot()` return an idempotent teardown function. A second boot first
   tears down listeners, controllers, extension registrations, and requests.
5. Prove a deliberately mismatched module release fails before `/api/bootstrap`
   or extension code runs.
6. Commit `feat(ui): add coherent native runtime boot`.

## Task 3: Build the shared API client and request-identity floor

**Files:**

- Add `static/js/ui-next/api.js`
- Add `static/js/ui-next/errors.js`
- Extend `browser_tests/test_ui_runtime.py`

1. Define normalized outcomes for network, session-expired, forbidden,
   validation, not-found, conflict, server, malformed-response, and aborted.
   Preserve status and bounded technical detail separately from player copy.
2. Support JSON, text, empty, and newline-delimited stream responses. Use
   same-origin credentials and no-store reads. Never automatically retry a
   consequential method.
3. Give each request channel a monotonically increasing identity and an abort
   controller. A newer request aborts the prior channel request; a late result
   cannot commit when its identity or selected owner no longer matches.
4. On 401, update session state, cancel outstanding work, and request a single
   navigation to `/login`. A valid 403 stays an inline forbidden outcome.
5. Carry an internal correlation id to tasks/diagnostics without logging bodies
   or credentials.
6. Prove stale reads, abort, malformed JSON, session expiry, and stream parsing
   in Chromium.
7. Commit `feat(ui): add request-safe API client`.

## Task 4: Implement the evented state store

**Files:**

- Add `static/js/ui-next/store.js`
- Extend `browser_tests/test_ui_runtime.py`

1. Define documented slices for session, route, story, transcript, composer,
   inspector, library, settings, tasks, notices, appearance, extensions, and
   diagnostics. Initial state distinguishes unrequested/loading/unavailable/
   empty/ready/error where applicable.
2. Provide immutable snapshots, scoped selectors, named actions, batched
   notifications, and deterministic unsubscribe/destroy behavior.
3. Refuse unknown slices and prevent subscribers from mutating stored objects.
4. Keep server projections separate from browser-local presentation state.
5. Prove event order, selector equality suppression, teardown, and copied
   extension state.
6. Commit `feat(ui): add evented application state`.

## Task 5: Establish truthful route and history semantics

**Files:**

- Add `static/js/ui-next/router.js`
- Extend `browser_tests/test_ui_runtime.py`

1. Parse and serialize stable hash routes for Play, Library, and Settings,
   optional nested segments, and bounded query values. Reject malformed,
   overlong, prototype-bearing, and unknown destinations.
2. Return a useful parent fallback plus a localized explanation; never silently
   claim the invalid target opened.
3. Model transient layers as history entries so Back closes the top layer
   before leaving the destination. Record focus-return identity without storing
   DOM nodes.
4. Start/stop `hashchange` and `popstate` listeners explicitly and avoid any
   polling.
5. Leave actual navigation, shell geometry, and destination mounts to WP-03.
6. Commit `feat(ui): define truthful route history`.

## Task 6: Add explicit localization and safe content boundaries

**Files:**

- Add `static/js/ui-next/localization.js`
- Add `static/js/ui-next/content.js`
- Modify `tools/extract_ui_catalog.py`
- Modify `language_packs/en/ui.json`
- Modify `language_packs/ja/ui.json`
- Extend runtime source/browser tests

1. Accept the active UI projection already carried by `/api/bootstrap`, validate
   language/direction/messages, compile specific template rules once, and
   expose `t(source, vars)` plus an explicit `localize(root)` pass. Standalone
   entries may use `/api/ui`; the host must not fetch a second catalog that can
   disagree with its bootstrap. Do not install a permanent mutation observer.
2. Translate authored interface copy only. Respect `translate="no"`,
   `data-no-i18n`, form values, user names, story prose, and model output.
3. Provide safe text creation through `textContent`. Provide a narrow rich-text
   sanitizer with an allowlist of structural tags/attributes and safe URL
   protocols; scripts, event attributes, styles, unsafe URLs, SVG, MathML, and
   unknown elements must not survive.
4. Exclude only the authenticated development laboratories from catalog
   extraction. Product entry copy enters English and Japanese catalogs in this
   task.
5. Prove long localized text, placeholder preservation, direction, story-text
   exclusion, and hostile markup rejection.
6. Commit `feat(ui): add explicit localization and content safety`.

## Task 7: Add tasks, notices, recoverable errors, and diagnostics

**Files:**

- Add `static/js/ui-next/tasks.js`
- Add `static/js/ui-next/notices.js`
- Add `static/js/ui-next/diagnostics.js`
- Extend runtime tests

1. Tasks have stable ids, owner/request correlation, named phase, start/update/
   complete/fail/cancel lifecycle, optional progress, and explicit cancel
   callbacks. Elapsed time is derived on render demand; no timer runs at rest.
2. Notices are bounded, owner-attributed, dismissible, and distinguish
   acknowledgement from a persistent/recoverable problem. Clearing a condition
   removes its notice.
3. Recoverable errors keep user work and expose a retry callback only when the
   originating action is safe to retry.
4. Diagnostics are off by default, bounded when enabled, redact credential-like
   keys and values, and never write ordinary events to `console`.
5. Prove cleanup, bounds, redaction, retry classification, and no idle timers.
6. Commit `feat(ui): add runtime feedback services`.

## Task 8: Version browser-local state and enforce the credential firewall

**Files:**

- Add `static/js/ui-next/storage.js`
- Add `static/js/ui-next/credentials.js`
- Extend runtime tests

1. Use one namespaced, versioned envelope with independent appearance,
   navigation, pane, and draft records. Validate every read, migrate known old
   versions idempotently, discard only the malformed member, and fail safely on
   quota/security exceptions.
2. Scope drafts by record type and stable owner id. Never move a draft between
   stories or records merely because selection changed.
3. Recursively refuse password, passphrase, token, API-key, secret, session,
   cookie, join-code, and authorization material from storage and diagnostics.
4. Submit credentials through a narrow allowlisted form helper directly to an
   approved endpoint. Do not put credential values in the store, task payload,
   notice, URL, storage, or diagnostics; clear sensitive controls in `finally`.
5. Prove safe restoration, malformed/version migration, cross-story draft
   isolation, quota failure, and credential non-persistence.
6. Commit `feat(ui): add safe local state boundary`.

## Task 9: Define the shared save and undo policy

**Files:**

- Add `static/js/ui-next/save-policy.js`
- Extend runtime tests

1. Classify field edits/drafts as autosave-eligible; creation, deletion,
   attach/detach, import/export, generation, reroll, branch, update, and
   credential submission remain explicit actions and are never silently
   retried.
2. Model dirty, saving, saved, conflict, and recoverable-error states in a
   stable state slot. Sequence writes per owner and reject a response whose
   owner/revision/request identity is stale.
3. Preserve the draft on every failure. A conflict does not overwrite newer
   server or local state.
4. Accept undo only from a bounded server receipt naming the action, owner,
   inverse endpoint/method, and expiry. Never synthesize an inverse for a route
   that did not return one.
5. Prove rapid edits, owner switches, out-of-order responses, conflicts,
   explicit-action refusal, and expired/foreign undo receipts.
6. Commit `feat(ui): define safe save sequencing`.

## Task 10: Build the versioned extension registry and v1 adapter

**Files:**

- Add `static/js/ui-next/extensions.js`
- Add `static/js/ui-next/extensions-v1.js`
- Add `browser_tests/fixtures/ui_v1_extension.js`
- Extend runtime source/browser tests

1. Implement an internal owner-bound registry for destination, Library type,
   Play tool, Add-ons settings, task-provider, legacy sidebar/topbar/composer/
   view/step registrations, notices, and turn events. Registrations are data;
   WP-03 and later own their visible consumers.
2. Contain sync throws and async rejections, attribute faults, retire after the
   documented threshold, close owned active views, remove owned notices/
   listeners/registrations/assets, and call optional teardown hooks.
3. Preserve the documented v1 methods and `chats` namespace through exactly one
   global: `window.Sonder`. Classic bundles use `_begin`/`_end`; module entries
   receive an id-bound facade that survives `await`.
4. Load extension classic/module/CSS assets only through authenticated current
   routes. A failed extension never prevents the host runtime from becoming
   ready.
5. Do not publish extension v2. Keep new slots internal until WP-03/WP-12 prove
   registration timing, permission/attribution, consumers, routing, failure,
   and teardown.
6. Prove a representative v1 fixture registers, reads copied state, calls an
   API route, receives an event, fails safely, and fully unregisters without a
   private host DOM id.
7. Commit `feat(ui): add contained extension lifecycle`.

## Task 11: Boot an authenticated runtime harness against current routes

**Files:**

- Add `static/ui-next-runtime.html`
- Add `static/css/ui/runtime.css`
- Modify `static/ui-next.html`
- Modify `static/js/ui-next/bootstrap.js`
- Modify `web/app.py`
- Extend server/browser tests

1. Add host-session-authenticated `/ui-next/runtime`. The page shows only a
   compact runtime status/error/diagnostic harness, not a pretend product
   shell, and is excluded from production UI catalog extraction as a named
   development fixture.
2. Boot `/api/bootstrap` once through the new client, populate store slices,
   apply its language catalog/appearance, load enabled extension UI through the
   v1 adapter, and mark ready only after required services are coherent. Never
   race bootstrap against a second `/api/ui` read.
3. Exercise actual route shapes with FastAPI's temp database: authenticated
   bootstrap/UI reads, a reversible UI-language write, chat create/read/update/
   delete, 401 expiry, and 403 distinction. Browser tests use the same paths and
   verify request bodies/headers/identity without classic scripts.
4. Ensure teardown aborts requests and removes every listener/registration.
5. Confirm no API key, password, join code, cookie, or session material appears
   in DOM, state, storage, URL, notice, task, or diagnostics snapshots.
6. Commit `feat(ui): boot current Sonder runtime`.

## Task 12: Close WP-02 without over-claiming G2

**Files:**

- Add `docs/design/sonder-ui-replacement/WP02_RUNTIME_REVIEW.md`
- Modify `docs/design/sonder-ui-replacement/REQUIREMENTS_TRACEABILITY.md`
- Modify `docs/guides/INTERFACE.md`
- Modify `docs/guides/EXTENSIONS.md`
- Modify `docs/guides/LANGUAGE_PACKS.md`
- Modify `docs/UNBUILT.md` section 2.26
- Regenerate `docs/CODE_MAP.md` and replacement inventories/drift

1. Perform security/data-loss, state/race, extension lifecycle, and
   implementation-boundary reviews. Record every finding and resolution.
2. Add WP-02 evidence to `ARCH-*`, `SAVE-*`, `EXT-*`, localization, and
   verification rows, but close only requirements wholly owned and proven by
   this package. G2 remains open until WP-03 proves the real shell, focus,
   responsive routes, and visible extension consumers.
3. Regenerate English catalog, code map, structure artifacts, replacement
   inventories, and frontend drift against the integration head.
4. Run focused runtime/source/server/browser tests, compile all maintained
   source roots, `tools/project_check.py`, full pytest, and all browser tests.
5. Re-run deterministic runtime/release evidence where generated. Inspect the
   runtime harness at desktop, mobile, keyboard, 200-percent zoom equivalent,
   long Japanese copy, session expiry, and extension failure.
6. Commit `docs(ui): qualify WP02 runtime boundaries`, fast-forward into
   `interface`, refresh drift to the integrated SHA, re-run focused merged
   verification, then remove the worktree and merged branch.

## Gate checklist

- [x] Native boot and teardown work with no classic scripts.
- [x] The only replacement global is the documented v1 `window.Sonder` adapter.
- [x] API outcomes are normalized; 401, 403, abort, stale, malformed, and stream
      paths are behaviorally proven.
- [x] Store slices and browser-local envelopes have one owner each.
- [x] No idle polling or permanent mutation observer exists.
- [x] Route/history semantics are stable without claiming the WP-03 shell.
- [x] Interface localization cannot translate story/user/model content.
- [x] Unsafe rich content and credential persistence are rejected.
- [x] Save sequencing refuses stale writes and preserves drafts.
- [x] Mixed module releases fail closed.
- [x] Representative v1 extension load/fault/unload is complete.
- [x] Current engine, persistence, auth, guest, language, and classic host tests
      remain green.
- [x] WP-02 is complete; G2 remains open for WP-03.
