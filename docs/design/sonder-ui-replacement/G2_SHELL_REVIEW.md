# Gate G2 application-shell review

**UI source:** `49895c7f4f7e238b93b217dc8e980c3cec3d4fa6`
**UI tree SHA-256:** `1313bc4c50e7bdd435e5a73170ab977caccb2cd7b60bbdf53a73f349e6f5ca73`  
**Evidence:** [deterministic shell report](g2/shell-report.json), [screenshots](g2/screenshots/), [browser contracts](../../../browser_tests/test_ui_shell.py), [source contracts](../../../tests/test_ui_shell_contracts.py), [WP-03 plan](../../superpowers/plans/2026-08-22-sonder-ui-replacement-wp03.md)  
**Scope:** authenticated application frame, responsive navigation, route/focus/scroll restoration, contextual inspector, Go To, visible extension-v1 hosting, and the current-host boundary. Destination workflows remain owned by WP-04 through WP-12.

## Decision

Gate G2 is accepted for the application shell. `/ui-next` now presents one
real replacement frame with exactly three primary destinations: Play, Library,
and Settings. The frame owns its markup, CSS, routing, focus, scroll regions,
overlay hosts, shortcuts, and extension surfaces. `/` and the classic frontend
remain unchanged until the cutover package.

The shell is deliberately truthful about unfinished work. Play exposes the
selected-story boundary without inventing story data; Library exposes only
the four approved collections; Settings exposes only the six approved groups.
The dedicated workflows behind those summaries remain open and are not
represented as complete by this gate.

## Responsive and accessibility review

The evidence matrix covers 360, 390, 640, 768, 844, 1024, 1280, and 1440 px
wide viewports, including landscape, a short laptop, a 200-percent-zoom
equivalent, long Japanese copy, and the full accessibility preset. Every case
selected one of the explicit compact, medium, wide, or expansive layout
states. Every visual case reported zero horizontal overflow and retained all
three primary destinations.

Compact layouts use a bottom navigation with at least 64 px destination
targets in the ordinary phone capture. Go To remains a separate 44 px header
control and never covers a primary destination. Long labels are exposed in
full to accessibility APIs while their dense bottom-navigation presentation is
limited to two centered lines. The final review caught and fixed a CSS
containing-block defect that had placed Go To over the compact navigation when
surface blur was enabled.

Wide and expansive layouts keep navigation, workspace, and inspector in
separate grid columns. Medium layouts collapse navigation labels but preserve
the same routes and target sizes. The compact inspector is a focus-contained,
Back-owned sheet; the desktop inspector opens, closes, pins, and resizes
without covering the workspace. Overlays inert the complete shell background,
restore focus by stable identity, and do not double-consume Escape.

## Runtime, navigation, and failure review

Each shell capture made exactly one `/api/bootstrap` request and loaded only
replacement assets. No visual case produced a console error or page error.
The shell exposes `window.Sonder` for the bounded migration adapter and never
exposes the classic `window.S` global. The evidence scan found no credential,
API-key, join-code, cookie, or session-shaped text in the rendered surface.

The router accepts only declared routes and bounded query fields. Invalid
links explain the fallback at their safe parent. Navigation stores a versioned
route, named scroll regions, a focus identity, and bounded destination-local
state; it never retains a DOM node. Go To contains only real routes, owns its
keyboard behavior, remains touch reachable, and rejects shortcut collisions.
Typing, content-editable, IME, repeat, and teardown guards are covered.

An assembled 401 boot fails closed, requests `/login` exactly once, and leaves
neither frontend global behind. A 403 remains inline and does not disclose the
server's private detail. `/ui-next` remains host-only, so the static evidence
page is not itself a second production entry.

## Extension-host review

The shell visibly consumes the WP-02 registry through a labeled Add-ons route.
The successful evidence view mounts inside an owner-attributed region. The
failing view produces a localized unavailable state while the shell remains
ready. Unloading its owner removes the route and result, restores the safe
Add-ons parent, and leaves core navigation usable.

This closes the G2 consumer boundary only. It does not claim extension-v2,
installed-corpus compatibility, permissions disclosure, or the final CSS
isolation policy; those remain WP-12 responsibilities.

## Historical candidate disposition

The historical candidate at
`73a380a0df2f6b139c98d66da9005489bd549d1d` remained reference input. No
candidate file was copied wholesale.

| Candidate idea | Disposition in WP-03 |
|---|---|
| Three-area desktop frame and compact bottom navigation | Retained as information-architecture intent; rebuilt with semantic landmarks, explicit layout states, safe-area handling, and measured targets. |
| Contextual right rail / mobile drawer | Retained as an inspector concept; rebuilt as one lifecycle-owned host with route history, focus containment, pinning, sizing, and Back semantics. |
| Command-palette-style navigation | Retained as Go To; rebuilt from declared routes with roving active descendant, collision-safe shortcuts, localization, and touch access. |
| Candidate remaster shell CSS and inline layout rules | Rejected as implementation. The replacement uses semantic tokens and one shell layer with no classic-id selectors or hidden compatibility controls. |
| Candidate shell state polling and DOM synchronization | Rejected. Store/router subscriptions and explicit teardown are the only steady-state synchronization mechanisms. |
| Hidden classic controls and `clickLegacy` forwarding | Rejected. The replacement owns visible controls and never synthesizes classic UI actions. |
| Candidate extension slot API | Rejected as a contract. The WP-02 owner-attributed registry and migration adapter supply the visible G2 consumer. |
| Candidate full-page HTML and global app script | Rejected. The shell uses a release-coherent native ES-module graph and an explicit authenticated host entry. |

## Findings resolved during review

| Finding | Resolution |
|---|---|
| Compact Go To was visually reachable but its fixed positioning was captured by the blurred navigation containing block, placing it over Settings. | Compact navigation now uses its required solid surface and no backdrop filter; browser geometry proves Go To remains above the bottom navigation. |
| Very long Japanese destination labels expanded the bottom navigation and collided visually. | Compact labels retain their accessible full text but clamp presentation to two lines; the long-copy browser case measures the result. |
| Nested overlay Escape handling could close both the child surface and its parent history layer. | The overlay host stops the handled Escape event and restores focus once. |
| A view owner could unload while its Go To result or deep link remained active. | Registry subscriptions rebuild results and route invalidation returns to the safe Add-ons parent. |
| Dynamic shell copy initially sat outside the catalog source boundary. | All shell-owned copy is catalogued; English coverage is exact and the corresponding Japanese keys are present. |
| Performance resource arrival order made the JSON evidence nondeterministic. | The recorder sorts resource and API path lists; two consecutive complete captures are byte-identical. |

## Qualification evidence

The checked-in report contains 15 visual cases plus session expiry. Two
consecutive complete captures produced byte-identical JSON and PNG files after
resource ordering was normalized. Screenshots are full-page, animation-free,
and SHA-256 bound in the report. Chromium 149 on Windows produced the evidence.

Exact-source qualification on Windows completed with:

- 110 focused shell, runtime, source, current-server, and browser checks;
- Python compilation across every maintained source root;
- generated catalog, code map, structure, inventory, and drift checks;
- 8,769 repository tests passed with four expected platform skips;
- 119 browser tests passed;
- two consecutive complete G2 captures byte-identical across the JSON report
  and all 15 screenshots.

The isolated worktree structure check reports no finding. The merged root can
also report seven pre-existing `extensions/directive` integration-test facade
couplings because that local extension checkout exists only in the root; those
are recorded separately from replacement-UI findings. G2 acceptance does not
close destination workflow, final responsive, installed-extension, or cutover
requirements.
