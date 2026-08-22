# WP-02 runtime-boundary review

**Review source:** `c0465fdade03d840197f4351b69e4db6090cd269`  
**Evidence:** [seven-case browser report](wp02/runtime-report.json), [runtime browser contracts](../../../browser_tests/test_ui_runtime.py), [source contracts](../../../tests/test_ui_runtime_contracts.py), [current-route contracts](../../../tests/test_ui_runtime_routes.py), [WP-02 plan](../../superpowers/plans/2026-08-21-sonder-ui-replacement-wp02.md)  
**Scope:** build-free boot, application state, API/error handling, route history, localization/content safety, tasks/notices/diagnostics, browser-local state, save sequencing, and the extension-v1 migration boundary. The runtime page is an authenticated development fixture, not the replacement product shell.

## Security and data-loss review

Credential submission is restricted to the current authentication, guest-join,
and provider credential routes. Sensitive controls are cleared in `finally`;
credential-shaped values are rejected from the versioned local envelope and
redacted recursively from opt-in diagnostics. Bootstrap state is projected
through explicit server slices, with credential-shaped unknown fields removed
before the extension adapter can copy it. API diagnostics carry request and
correlation identity but never request bodies.

Untrusted rich content is rebuilt from a parsed allowlist. Scripts, event
attributes, inline styles, unsafe URLs, SVG, MathML, and unknown elements are
dropped; the sanitized result is assembled through DOM nodes rather than
assigned to `innerHTML`. The localization boundary translates catalogued
interface copy only and skips `translate="no"`, form values, editable content,
and story/user/model data.

Save policy is intentionally conservative. Only ordinary field and draft
updates may autosave; structural, destructive, security-sensitive, install,
connection, repair, generation, import, and unknown actions require an explicit
verb. Recoverable failures and conflicts retain the local draft. Undo accepts
only a bounded, matching, unexpired server receipt whose inverse is a safe
same-origin API operation.

**Decision:** acceptable foundation. Real editor validation, leave warnings,
copy/export recovery, destructive confirmations, and undo presentation remain
owned by their visible workflow packages and keep `SAVE-*` open.

## State, request, and route-race review

Server slices (`session`, `story`, `transcript`, `library`, `settings`, and
`extensions`) are separate from presentation slices (`route`, `composer`,
`inspector`, `tasks`, `notices`, `appearance`, and `diagnostics`). Inputs and
snapshots are copied and frozen. Mutations name their owning slice; batching
coalesces notifications; subscriptions have deterministic cleanup.

The API client gives each request a correlation id and each channel a monotonic
identity. Superseding a channel aborts the earlier request, and owner checks
reject a response whose story or record is no longer current. Writes are never
retried automatically. Each save owner has one serialized queue with revision
and request identity, so a late completion cannot overwrite a newer draft.

The router accepts only bounded known hash routes and bounded query data.
Malformed, overlong, prototype-bearing, missing, or retired targets fall back
to a useful parent reason. Transient dialogs and sheets occupy history entries,
so Back unwinds them before leaving a destination; focus restoration carries
an identity, never a retained DOM node. Boot, router, runtime-error, and
diagnostics listeners are removed on teardown. There is no polling or mutation
observer.

**Decision:** acceptable foundation. WP-03 must prove these semantics through
the real Play, Library, and Settings shell before G2 can close.

## Extension lifecycle review

The internal registry owns explicit destination, Library-type, Play-tool,
Add-ons-settings, task-provider, legacy surface, notice, and event slots.
Registrations, listeners, notices, assets, active views, and optional module
teardown are owner-attributed and removed together. Synchronous throws and
asynchronous rejections are contained; three faults retire the owner without
preventing the runtime from becoming ready.

The migration adapter exposes exactly one replacement global,
`window.Sonder`. Classic scripts use `_begin`/`_end` attribution; module
entries receive an id-bound facade that remains correct across `await`. Assets
load only through authenticated `/api/extensions/...` routes. The
representative v1 fixture proves copied state, host API calls, turn events,
classic and module registration, failure containment, active-view cleanup,
asset removal, teardown, and global removal without a private host DOM id.

**Decision:** the migration boundary is coherent, but it is deliberately not
extension v2. WP-03 must add visible consumers and WP-12 must prove installed
extension compatibility, routing, permissions/disclosure, CSS containment,
and the final v2 surface. `EXT-*` therefore remains open.

## Implementation-boundary review

The authenticated `/ui-next/runtime` fixture imports one release-coherent
native module graph and reads `/api/bootstrap` exactly once. It does not load
classic host scripts or race bootstrap against `/api/ui`. A mixed release
fails before services start. Teardown cancels requests and removes every
runtime service. Current FastAPI authentication, bootstrap/UI, reversible UI
language, and chat create/read/update/delete routes are exercised against a
temporary current database.

The replacement remains build-free: no Node, package manager, bundler, CDN,
network font, or network icon is required. The fixture does not pretend to be
Play, Library, or Settings and changes neither `/` nor current persistence.

**Decision:** WP-02 is complete without closing G2 or any cross-package
`ARCH-*` row. The actual responsive shell, route consumers, focus movement,
visible extension slots, login/guest entries, and cutover remain later work.

## Findings resolved during review

| Finding | Resolution |
|---|---|
| Generic 401 and registry fault tests did not prove the assembled host boot behavior. | Added host-runtime contracts: session expiry requests login once and fails closed; an extension asset failure is isolated and the runtime still becomes ready. |
| The runtime evidence recorder initially measured the native checkbox rather than its effective label target. | The recorder now measures the owning label and records every effective target size. |
| That corrected measurement exposed an undefined `--ui-target-min` reference and a 22.5 px mobile diagnostics target. | The fixture now uses `--ui-target-current`; a 390 px browser regression proves both controls are at least 44 px. |
| The browser matrix named deterministic evidence but had no WP-02 recorder. | Added `tools/capture_ui_runtime.py`; two consecutive complete captures produced byte-identical report and screenshot files. |
| A foundation test asserted the old single-fixture catalog-exclusion source spelling. | It now proves all three replacement entries are head-safe and both named development fixtures use the maintained exclusion set. |
| The global inventory classified top-level declarations inside native modules as classic browser globals. | The generator now detects module syntax, omits module-private declarations, retains explicit `window.*` writes, and has a mixed classic/module regression fixture. |

## Qualification result

The runtime evidence covers desktop, phone, keyboard focus, a 200-percent zoom
equivalent, long Japanese copy, contained extension asset failure, and session
expiry. All visual cases have zero horizontal overflow; phone, zoom, and
long-copy cases retain 44 px effective targets. The expected failed extension
request is the only console error, produces no page error, and leaves the host
ready. Session expiry leaves no adapter/global behind and requests `/login`
once.

WP-02 qualification completed on Windows with Chromium 149:

- runtime/source/server/browser focus: 110 passed;
- Python compile across every maintained source root: passed;
- generated code map, structure, documentation links, and catalog freshness:
  passed with no findings;
- full repository suite: 8,763 passed, 4 platform skips;
- complete browser suite: 96 passed;
- two consecutive complete runtime evidence captures: byte-identical across
  all seven report cases and six screenshots.

WP-02 is complete. G2 remains open for WP-03.
