# Interface implementation contract

This guide is the maintained authority for Sonder's player- and host-facing
web interface. It reconciles the visual and interaction direction in the
[UI Design Bible](../design/sonder-ui-bible/README.md) with the engine's
implemented contracts. Change this guide in the same commit as any interface
boundary it describes.

## Authority and outcome

For interface work, resolve disagreements in this order:

1. Engine behavior, persistence, security, information-firewall, archive,
   checkpoint, authentication, guest, and extension contracts in current
   source and maintained guides.
2. This guide and an approved feature-specific interface specification.
3. The Design Bible's visual, responsive, accessibility, terminology, and
   interaction rules.
4. Existing interface presentation.
5. Historical candidate implementation and screenshots.

The approved outcome is a **full replacement** of the classic host and player
interface. The finished product has one host application, not a permanent
legacy/replacement selector. The legacy shell remains the current production
entry only until the replacement closes every capability and passes cutover.
The program and gates are in
[`2026-08-21-sonder-ui-full-replacement-design.md`](../superpowers/specs/2026-08-21-sonder-ui-full-replacement-design.md),
while [`UNBUILT.md`](../UNBUILT.md) §2.26 is the sole status authority.

WP-00 is complete and G0 is locked. The exact current-source captures,
performance ceilings, qualification commands, and all failures encountered
during qualification are recorded in
[`BASELINE_AND_BUDGETS.md`](../design/sonder-ui-replacement/BASELINE_AND_BUDGETS.md).
This establishes the control plane only; replacement product requirements stay
open until their owning work package provides implementation and evidence.

## Runtime boundary

- The replacement is delivered by the existing FastAPI process, same-origin.
- Frontend source is native ES modules. A Node.js toolchain or bundling step is
  not required to run, test, package, or modify the interface.
- FastAPI routes and current persistence records remain authoritative. The UI
  does not introduce parallel story, character, persona, lore, settings,
  extension, task, or authentication stores.
- Client state is an explicit projection of server state plus bounded UI-only
  state. Every async result carries enough request/story/record identity to be
  rejected when stale.
- Development uses `/ui-next`, a separate host-session-authenticated native
  module entry. Anonymous requests redirect to `/login`; the entry does not
  load classic host assets, read API state, poll, or alter `/` until its owning
  work packages add those responsibilities and the cutover gate passes.
- Browser-local migrations are versioned and idempotent. Consequential drafts
  are scoped to their real story or record, recoverable, and never silently
  moved between owners.

## Integration rules

The replacement must not depend on:

- `window.S` or any new general-purpose host global;
- interval polling to notice ordinary host state changes;
- synthetic clicks on hidden legacy controls;
- off-screen or invisible duplicate controls;
- private DOM IDs as a supported extension contract;
- unconsumed registration slots or routes;
- a second client-side copy of server-owned truth.

`ARCH-12` from the historical requirement matrix is amended accordingly. There
is no single global compatibility bridge. A temporary adapter must be narrow,
explicitly owned, evented, attributed to its caller, independently testable,
and named for deletion at WP-13. Cross-module behavior goes through imported
interfaces or DOM events with documented payloads, not a mutable global bag.

The public extension v1 contract remains supported through an adapter on the
new host until the program explicitly changes that contract. Extension v2 is
not advertised until registration timing, rendering, permission, attribution,
failure containment, disable/retire cleanup, routing, and CSS containment all
have behavioral evidence. See [`EXTENSIONS.md`](EXTENSIONS.md).

## Content, credentials, and persistence

- Story prose and user-authored rich content are rendered through one reviewed
  content boundary. Untrusted HTML is not assigned directly to `innerHTML`.
- UI copy comes from the current language-pack catalog in the task that adds
  it. User and story data is marked and kept untranslated. See
  [`LANGUAGE_PACKS.md`](LANGUAGE_PACKS.md).
- Passwords, provider keys, join codes, and session material never enter the
  general application store, local storage, diagnostics, notices, URL state,
  or task history. Credential forms submit through their narrow route and
  discard their values.
- Presentation changes do not reinterpret persistence. Attach, detach, delete,
  archive, restore, branch, reroll, and checkpoint remain distinct server
  operations with their current transaction and authority boundaries.
- A destructive request names the exact object, requires the appropriate
  confirmation, and is never retried automatically.

## Product and responsive contract

The primary destinations are Play, Library, and Settings. Story Tools are
story-scoped; global configuration is not. New Story, host setup/sign-in, and
guest join/play are complete entry workflows rather than dialog fragments.

Desktop, tablet, portrait mobile, narrow mobile, landscape mobile, short-height
windows, 200-percent zoom, long localization, keyboard, pointer, and touch all
own the same capability ledger. Responsive staging may change placement and
density, but it may not hide a capability such as conditions/vitals or make a
control unreachable. Reading content, condition surfaces, utilities, and the
composer must never overlap continuously at supported sizes.

Loading, unavailable, confirmed empty, error, and stale states are distinct.
Recoverable errors stay in context; toasts acknowledge completed actions and
do not carry persistent work, failures, or choices.

## Design-system boundary

The Bible defines the quiet, precise, genre-neutral product character and the
semantic visual vocabulary. Curated themes change semantic tokens, never
layout. Legacy themes may map values into those tokens but do not own component
geometry. Icons come from the reviewed local SVG family and retain accessible
names where the symbol alone is not established.

Major screens and component families require four recorded reviews before
their package gate: product flow, visual system, responsive behavior, and
implementation/state preservation. A screenshot is evidence of presentation
only; it cannot close routing, persistence, mobile parity, accessibility,
localization, extension, or async-state requirements.

## Evidence and change control

Every replacement increment must:

1. own a coherent requirement and current-capability subset;
2. begin executable behavior with a failing focused test;
3. name the exact candidate assets it ports, if any;
4. verify current server and persistence semantics rather than reproducing a
   candidate snapshot;
5. run the narrow suite before the package gate;
6. update traceability and maintained guidance in the behavior commit;
7. refresh frontend drift against the current integration head;
8. remain independently reversible before cutover.

Evidence ledgers under `docs/design/sonder-ui-replacement/` are reproducible
maps and run records. They do not replace `UNBUILT.md`, cannot approve a
deviation, and cannot declare a work package complete. A deviation records the
affected requirement, reason, impact, owner, evidence, and approval in the
traceability matrix; unapproved missing mobile capability or data-loss/security
risk is release-blocking.

The default UI changes only at G6. Legacy implementation is deleted at G7. The
replacement is releasable only at G8 after exact-head behavioral, responsive,
accessibility, localization, extension, performance, novice, and expert proof.
