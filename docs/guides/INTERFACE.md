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
2. This guide, [`UI_REFERENCE.md`](UI_REFERENCE.md), and an approved
   feature-specific interface specification.
3. For presentation covered by the supplied evidence, the matching reference
   screenshots and candidate visual source, interpreted through the Design
   Bible.
4. For general and uncovered presentation, the Design Bible's visual,
   responsive, accessibility, terminology, and interaction rules.
5. Existing interface presentation.

The current replacement's appearance gains no authority merely by being newer.
It must reproduce the supplied visual composition unless an approved
specification or recorded Design Bible deviation says otherwise. Candidate
behavior is never runtime authority: current server and engine contracts still
own data and effects.

The approved outcome is a **full replacement** of the classic host and player
interface. The product has one host application, not a legacy/replacement
selector. The replacement is now the authenticated production root; the
classic entry, scripts, and styles were removed in WP-13.
The program and gates are in
[`2026-08-21-sonder-ui-full-replacement-design.md`](../superpowers/specs/2026-08-21-sonder-ui-full-replacement-design.md),
and the completed G8 qualification is in the
[WP14 release audit](../design/sonder-ui-replacement/wp14/REVIEW.md).

WP-00 is complete and G0 is locked. The exact current-source captures,
performance ceilings, qualification commands, and all failures encountered
during qualification are recorded in
[`BASELINE_AND_BUDGETS.md`](../design/sonder-ui-replacement/BASELINE_AND_BUDGETS.md).
This establishes the control plane only; replacement product requirements stay
open until their owning work package provides implementation and evidence.

WP-01 establishes the G1 visual foundation under `static/css/ui/` and
`static/js/ui/`. Semantic tokens and curated-theme overrides own appearance;
component modules own focus, overlays, roving focus, live announcements, and
primitive state. The reviewed local SVG family is served from
`static/assets/icons/sonder-icons.svg`. The authenticated `/ui-next/lab`
component laboratory is a non-functional review surface: it performs no API
requests and owns no application truth. Its [G1 review and browser
matrix](../design/sonder-ui-replacement/G1_FOUNDATION_REVIEW.md) qualify the
foundation for reuse without claiming later product flows.

WP-02 establishes the replacement service graph under `static/js/ui-next/`.
The authenticated `/ui-next/runtime` fixture proves one release-coherent native
boot against current `/api/bootstrap`, explicit state slices, request identity,
route history, localization and content boundaries, task/notice/diagnostic
services, browser-local draft ownership, save sequencing, and a contained v1
extension adapter. Its [runtime review and browser
matrix](../design/sonder-ui-replacement/WP02_RUNTIME_REVIEW.md) qualify those
boundaries without claiming a product shell.

WP-03 closed G2 with the replacement application frame, now served at `/`. It owns
exactly three primary destinations (Play, Library, and Settings), four explicit
layout states, versioned route/focus/scroll restoration, the desktop and mobile
inspector frame, Go To, overlay/notice/task hosts, and the first visible
extension-v1 route consumer. The [G2 review and deterministic browser
matrix](../design/sonder-ui-replacement/G2_SHELL_REVIEW.md) qualify that shell
without claiming the destination workflows.

WP-04 established the accepted Play-core tranche of G3. One runtime-owned coordinator owns
selected story/frame identity, story loading, generation, stop/retry, reroll,
variants, mutations, and authoritative refresh across destination remounts.
The view owns the literary transcript, story-scoped composer, current story
and turn actions, explicit Play states, and responsive presentation. The
[G3 review and deterministic browser matrix](../design/sonder-ui-replacement/G3_PLAY_REVIEW.md)
qualified those behaviors without then claiming Story Tools or Library
lifecycle.

WP-05 completes G3. A stable ten-tool registry owns Cast, World, Style,
Dialogue, Attire, Backdrops, Ambience, Conditions, Frames, and Multiplayer in
the desktop inspector and compact staged sheet. Structural editors preserve
complete server documents and owner-scoped drafts. The runtime owns backdrop,
weather, ambience, and completion-chime lifetime independently of inspector
DOM. The [Story Tools review and deterministic browser
matrix](../design/sonder-ui-replacement/G3_STORY_TOOLS_REVIEW.md) qualify all
current-story surfaces without claiming Library lifecycle or later global
Settings/editor packages.

WP-06 completes Library discovery and lifecycle. One server projection joins
Stories, reusable Characters, Personas, and Lore with their real story
associations; archive metadata remains separate from story state. Native
Library routes own scope, type, search, sort, visibility, selection, and
responsive detail staging. Existing guarded association routes remain the
only mutation authority. The [WP-06 review and deterministic browser
matrix](../design/sonder-ui-replacement/WP06_LIBRARY_REVIEW.md) qualify these
surfaces without claiming the long-form editors and complete action parity
owned by WP-07 or the later product-surface gate.

WP-12 closes G5 after the intervening Library-authoring, Settings, New Story,
authentication, and guest packages. Its curated/Legacy theme matrix and mixed
installed extension corpus prove the native UI API 2 facade, explicit v1
adapter, destination-specific consumers, owner teardown, plain-language
capability disclosure, and contained semantic-token CSS. The [WP12
review](../design/sonder-ui-replacement/wp12/REVIEW.md) records the visual and
296-test qualification.

WP-13 makes that replacement the only production host surface. `/` serves
`static/ui-next.html` behind the existing host-session gate; the classic entry,
global scripts, and classic styles no longer ship. `/ui-next/lab` and
`/ui-next/runtime` remain authenticated development fixtures, not product
alternatives. The [WP-13 review](../design/sonder-ui-replacement/wp13/REVIEW.md)
records capability reconciliation and deletion evidence.

Alpha 9.8 adds lived-location preparation and Charter inspection to that same
replacement composition. It does not add a fourth destination or a parallel
frontend product. New Story, Character Quick Start, and reusable Lore share one
location/history form; Dialogue owns the story-scoped institution ledger and
diagnostics; Settings links to that canonical Story Tool instead of editing a
second copy. The [alpha 9.8 parity review](../design/sonder-ui-replacement/wp15/REVIEW.md)
records the port, responsive renders, and current-endpoint evidence.

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
- Production uses `/`, a host-session-authenticated native module entry.
  Anonymous requests redirect to `/login`; the entry loads the replacement
  graph and one `/api/bootstrap` projection, with no classic host asset or idle
  polling. Component and runtime fixtures remain under `/ui-next/lab` and
  `/ui-next/runtime`.
- Browser-local migrations are versioned and idempotent. Consequential drafts
  are scoped to their real story or record, recoverable, and never silently
  moved between owners.
- The application store separates server slices (`session`, `story`,
  `transcript`, `library`, `settings`, `extensions`) from presentation slices
  (`route`, `composer`, `inspector`, `tasks`, `notices`, `appearance`,
  `atmosphere`, `diagnostics`). State enters by named owner actions and leaves as copied,
  frozen snapshots.
- The shared API client owns same-origin/no-store requests, response parsing,
  correlation identity, cancellation, and stale-owner rejection. It never
  retries a write automatically. A 401 requests login once; a 403 stays an
  in-context authorization result.
- Hash routes are bounded data. Stable destinations and subviews may survive a
  refresh; transient layers occupy history entries and carry focus-return
  identity rather than DOM nodes. Unknown or retired targets fall back to a
  useful parent explanation.
- Runtime modules and their entry assets carry one release id. Mixed cached
  releases fail before services start. HTML is `no-store`; versioned
  replacement assets are immutable for that release. The release id ends in a
  normalized content fingerprint covering every immutable replacement CSS,
  JavaScript, and sprite asset. Changing one of those assets therefore requires
  a new release id; the runtime contract test rejects a reused immutable URL.

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

The public extension v1 contract remains supported through a narrow adapter.
Extension UI v2 is the native owner-bound module facade, selected by
`capabilities.ui.api: 2`; missing or version 1 declarations receive the v1
compatibility facade. Every renderable slot has a destination-specific
consumer, and disable/retire/failure teardown removes its routes and owned
resources. Supported extension CSS is owner-prefixed, mount-contained, and
uses public semantic tokens. See [`EXTENSIONS.md`](EXTENSIONS.md).

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

The G2 shell makes this topology executable. Wide layouts use a left
navigation rail, central destination workspace, and right contextual inspector.
Medium layouts retain the same routes in a compact rail. Compact layouts use a
three-item bottom navigation and move Go To to the header; the inspector becomes
a focus-contained, Back-owned sheet. Stable routes, named scroll regions, and
focus identities are data. No shell service retains a DOM node across a route
or refresh. Unfinished destination work is presented as a bounded truthful
summary, never as a synthetic call into the classic interface.

Desktop, tablet, portrait mobile, narrow mobile, landscape mobile, short-height
windows, 200-percent zoom, long localization, keyboard, pointer, and touch all
own the same capability ledger. Responsive staging may change placement and
density, but it may not hide a capability such as conditions/vitals or make a
control unreachable. Reading content, condition surfaces, utilities, and the
composer must never overlap continuously at supported sizes.

Compact layouts give every actionable control a minimum 44 px target. Desktop
density may reduce non-target spacing and keep native fields at a 36 px minimum,
but it never shrinks the compact/touch target contract.

Loading, unavailable, confirmed empty, error, and stale states are distinct.
Recoverable errors stay in context; toasts acknowledge completed actions and
do not carry persistent work, failures, or choices.

### Play-core ownership

- `static/js/ui-next/play-runtime.js` is the sole client owner of selected
  story/frame loads and active generation lifetime. Every async result is
  checked against captured owner identity; navigation does not retarget a run.
- `static/js/ui-next/play-view.js` is a projection. Destination remounts may
  replace its DOM and listeners, but cannot own or cancel the run, selected
  story, or browser-local draft.
- Drafts use the WP-02 versioned local envelope and the stable
  `chat-{id}:frame-{id}` owner. A send clears the draft only when an accepted
  response exists; a pre-acceptance failure preserves it and exposes Retry.
- `static/js/ui-next/prose.js` builds prose from text and reviewed elements.
  Model HTML is never parsed as document markup. Interface copy localizes;
  story names, player input, prose, dialogue, and raw technical data do not.
- Turn streaming is incremental and does not collect token history. Friendly
  status is first-level; bounded technical events remain under Advanced. The
  current extension registry receives post-host `turn:*` events without a
  general-purpose browser global.
- Reroll, narration selection, edit, branch, delete, rename, pipeline detail,
  and portable export delegate to current server routes. The browser never
  reconstructs checkpoints or invents archive/lifecycle authority.
- Transcript scroll is internal and named. Initial/current reading stays
  pinned; prior-turn review preserves its offset and announces a New turn
  affordance without stealing scroll.
- Compact Play retains every current action and a minimum 44 px target.
  Short-landscape treatment prioritizes the active field and primary action;
  safe-area padding belongs to the composer and bottom navigation.

### Story Tools and atmosphere ownership

- `story-tools-registry.js` is the complete current-story tool list.
  `story-tools-runtime.js` captures story, frame, tool, mount, and request
  sequence; a late response cannot repaint another owner.
- Wide layouts mount Story Tools in the right inspector with exactly three
  semantic list modes: Expanded shows icon, title, and description; Compact
  shows icon and title; Rail shows the icon with its accessible name and
  tooltip intact. Legacy `wide`, `default`, and `narrow` values migrate to
  Expanded, Expanded, and Compact. A selected tool uses Expanded presentation,
  retains a compact icon switcher, and exposes `All tools` to restore the saved
  list mode. Medium and compact layouts mount the same module in a
  focus-contained staged sheet. Tool changes preserve Play draft, scroll, run,
  and media state.
- Cast, Conditions, Frames, and Multiplayer project current guarded routes.
  They do not create parallel character, condition, frame, invite, or guest
  authority in browser state.
- World, Style, Dialogue, and Attire are explicit-save structural tools.
  Complete JSON remains available where summary controls cannot faithfully
  cover the document. Drafts clear only after accepted save or explicit
  discard; story language never rewrites host UI language.
- `atmosphere-runtime.js` owns backdrop/ambience request de-duplication, media
  tokens, visibility pause, unlock, mute, volume, and optional completion
  chime. Only mute, volume, and chime preferences persist locally; URLs,
  credits, story data, and credentials do not.
- Backdrop and weather layers are absolute behind Play and cannot affect prose
  measure or composer geometry. Effects Off removes decorative weather while
  reduced motion makes it static. Pending generation uses an explicit status
  check and never an idle interval.
- Mute and Volume remain beside the composer. Provider/source configuration,
  pins, reroll, credits, unlock, and chime stay in the contextual tool.

### Library ownership

- `web/library.py` is the public Library projection. It exposes bounded,
  public summaries and real story associations without returning authored
  sheets, private history, runtime state, credentials, or model output.
- A story scope is a filter over associations. It never relocates a reusable
  Character, Persona, or Lore source into a story-owned client record.
  Story-owned lore remains distinguishable from reusable lore and appears only
  in the relevant story projection.
- `library-runtime.js` owns route/query requests and mutation receipts. Every
  result is checked against the captured route and item/story owner; accepted
  writes refresh the server projection instead of patching a second client
  association model.
- Archive and restore use `library_item_state`. Archive changes discovery only;
  it does not change story membership or enter checkpoints and exports. Delete
  is a separate explicit operation and has no optimistic undo.
- Character removal means dormant, not erased. A primary Persona cannot be
  detached through Library. Lore detach targets the story copy and preserves
  the reusable origin. The existing running-story guard owns mutation refusal.
- Undo is in-memory, owner-bound, exact-operation, and expires after twelve
  seconds. It is offered only for sound inverses; no receipt or story data is
  persisted in browser-local presentation state.
- Wide/expansive layouts assign each responsibility once: the left pane owns
  category and scope navigation, the center owns the single searchable/sortable
  material ledger and create/import actions, and the right pane owns selected
  item detail. Decorative duplicate totals, recent lists, and scope summaries
  are not parallel authorities. Medium/compact layouts retain the central
  ledger and stage detail in the Back-owned inspector sheet. Direct
  selected-item links stage that sheet once; Back returns to the retained ledger
  rather than reopening it.
- Activating a Story row selects it and reveals Library detail; it never enters
  Play. Only the explicit `Open in Play` action commits that navigation. Until
  then the Library route, scope, filters, selection, and scroll remain owned by
  Library.
- Only favorites, recents, per-route scroll, and the last safe route enter the
  versioned local presentation envelope, each with a hard bound. They never
  make an archived, missing, or server-rejected item appear available.
- Reusable Character, reusable Persona, and story-specific Character-card
  editing use one focused Library authoring framework. Entering authoring
  replaces the Library destination body while leaving concise selection detail
  as the inspector's responsibility outside authoring. The inspector is hidden
  for the task without changing its persisted open, pin, or size preference.
- The shared authoring framework assigns maintained fields through one semantic
  path registry to Basics, Appearance, History, and the applicable Character or
  Persona sections. The registry owns plain labels, consequence-oriented help,
  control type, numeric bounds, and enumerated choices. Internal schema keys do
  not appear in ordinary sections. Unknown fields remain literal and lossless
  under More > Additional fields and in Advanced; the client never drops or
  normalizes a stored field merely because it lacks a dedicated control.
- Peer content sections remain the visible tab set. Character Start a Story,
  Additional fields, and Advanced are staged under one More disclosure whose
  summary names the active auxiliary section. Start a Story uses the explicit
  `Save and start Story` boundary and does not become a parallel workflow.
- Person authoring has one vertical document scroll owner. Wide layouts use a
  restrained section rail; compact and short-landscape layouts stage the same
  peer sections plus More as a horizontal strip. Back and save state share one
  topbar, and the editor frame owns the persistent action footer. Hidden panels
  and closed More controls leave the focus order, visible controls retain the
  44 px interaction target, structured editors retain useful authored height,
  and the page itself does not become a second scroll owner.
- Save state distinguishes `Saved to Library` from `Draft saved on this
  device`. Back removes authoring-only route keys while preserving category,
  scope, Story, query, sort, visibility, selection, and the exact parent-route
  scroll. A returned selection receives focus, and an owner-scoped local draft
  and section choice survive re-entry.
- Discard draft is the one destructive local action. It opens a modal that
  names the document and explains that the last Library version will be
  restored; only the explicit destructive confirmation invokes the runtime's
  discard operation.

### Settings and appearance ownership

- The shell gives the destination track `minmax(0, 1fr)`. Settings gives its
  detail track the same bound and makes `[data-settings-content]` the vertical
  scroll owner. The document body is never relied on to reveal clipped settings
  in desktop, short-height, or compact layouts. The detail owner is a named,
  keyboard-focusable region. Vertical wheel and Page Up/Down/Home/End intent
  from the surrounding Settings header or category navigation is forwarded to
  it; a nested result list keeps its own scrolling, and horizontal category
  gestures remain horizontal.
- Story text size changes prose only. The Experience page includes a local prose
  preview so the setting remains discoverable without an open Story; nearby
  labels and controls retain their interface size.
- Interface density has two values: Comfortable and Compact. Compact reduces
  non-target Settings spacing while preserving all controls and target minimums.
  The retired Roomy density migrates to Comfortable; the separate accessibility
  preference `Roomy controls` remains the authority for enlarged controls.
- Visual effects has three values: Full, Reduced, and Off. `appearance.effects`
  is the persisted envelope field and `data-effects` is the CSS contract. The
  older `appearance.motion` value is migration input only. Reduced shortens or
  removes decorative movement; Off zeroes motion tokens and removes decorative
  weather. OS reduced-motion and the granular accessibility preference may
  further reduce motion, never increase it.
- AI Connections presents `Memory search model (embeddings)` as essential model
  configuration beside the Default summary, not as an expert role assignment.
  Its copy explains meaning-based recall and the vector-model requirement.
  Changing it names the required stored-vector rebuild and links to the existing
  Memory search maintenance operation. Unrelated specialist roles, sampling,
  and backup models remain under Advanced model assignments.
- A server-owned setting is announced as saved only after its mutation succeeds
  and a fresh `/api/settings` projection is accepted into the `settings` server
  slice. Navigation and remounts therefore read the value the engine reports,
  not the startup bootstrap copy or an optimistic form value. A failed mutation
  or confirmation keeps the entered form intact and publishes a visible problem;
  network, server, and unreadable-response failures remain in the shell notice
  host until explicitly dismissed.
- Every Settings category starts its detail ledger at the same block offset.
  The Settings search icon is centered from the input's actual block size rather
  than a fixed top coordinate, so density and touch sizing cannot displace it.
- Narrator voice examples retain four independent persisted passages but expose
  one editor at a time through an ARIA tablist. Arrow Left/Right, Home, and End
  move between the tabs without discarding unsaved drafts.
- Extension titles preserve the extension-authored name, including a terminal
  `(demo)` marker. Lifecycle actions derive a clean action name with only that
  terminal marker removed, and every action has the shared subtle control
  border. Maintenance uses the reviewed local wrench symbol.

### Alpha 9.8 lived-location ownership

- `lived-location.js` is the shared presentation adapter for New Story,
  Character Quick Start, reusable Lore, and Story Tools. It normalizes only
  browser drafts and maps them to the released alpha 9.8 request documents; it
  does not simulate institutions, routes, history, or information movement.
- New Story keeps lived-location choices inside its existing recoverable setup
  draft. The review names the place and Character-past horizon before creation.
  Once `/api/chats` succeeds, setup uses the released lore attachment and
  `/api/chats/{id}/charters/generate` routes. A failed post-create setup deletes
  the incomplete Story through the released Story deletion route; if cleanup
  itself fails, the draft retains an explicit link to that Story.
- Character Quick Start sends the released `lorebook_id`, `already_known`,
  `language`, and `lived_location` fields through its existing save-before-start
  runtime. Public resident-card disclosure and private Character-history
  delivery are stated beside the controls.
- Reusable Lore may prepare a location only for the current Story at its present
  frame. The action attaches through the existing lore route, then calls the
  released Charter generator. The selected Lore, Story, route, and request owner
  are captured so a late result cannot repaint another detail.
- Dialogue remains the canonical home for story-scoped institutions. Its
  Charter section reads `/charters`, expands `/charters/diagnostics` on demand,
  and offers explicit generation from attached Story Lore. Settings owns only
  living-world ceilings and a link to this tool.
- Witnessing, telling, reading, and carrying information are story events, not
  UI settings. The replacement exposes that boundary in plain language and
  never invents a browser-side rumor, courier, resident, or world-clock model.
- Institution names and warnings are engine data and remain untranslated. New
  interface copy enters both English and Japanese catalogs in the same release.

## Design-system boundary

The Bible defines the quiet, precise, genre-neutral product character and the
semantic visual vocabulary. Curated themes change semantic tokens, never
layout. Unsupported Legacy-theme selection is no longer exposed. Icons come
from the reviewed local SVG family and retain accessible names where the symbol
alone is not established.

The curated themes are Carbon Signal, Ash & Brass, Midnight Ink, Parchment
Night, Neon Circuit, and Modern Slate. Modern Slate is a deliberately warm
greyscale palette: no authored token leans blue, and interaction uses subdued
warm white. Appearance preflight applies the chosen theme synchronously before
the module graph starts. Effects, contrast, text size, reduced motion, and
Accessibility Mode remain independent preferences rather than theme side
effects.

Custom Theme is an eight-role semantic editor for background, panel, primary
text, muted text, accent, attention, success, and danger. It previews changes
locally and accepts only normalized colors in a versioned exact-key document.
Text contrast, non-text contrast, and background/panel distinction must pass
before activation. Import rejects unknown fields, CSS, URLs, markup, malformed
versions, and unsafe colors; application can write only the eight fixed custom
properties. Hex, RGB, reset, import, and export are alternate interfaces to the
same validated palette. The browser-local theme is synchronous on first paint.

Foundation source responsibilities are fixed: `tokens.css` defines geometry,
motion, type, layering, and semantic color roles; theme files only override
semantic values; `components.css` owns reusable component geometry; entry and
laboratory styles compose those pieces without redefining their contracts.
Shared selects use the glass surface, restrained logical radius, one chevron,
and 36 px comfortable / 32 px compact desktop geometry while retaining the 44
px touch minimum. Shared buttons use centered inline-flex content, restrained
13 px type, and icon/text gaps so symbols such as New Story's plus align with
their label.
`appearance-preflight.js` is the only pre-module behavior and may only stamp
validated browser-local appearance before paint. Accessibility preferences are
independent overrides, with Accessibility Mode applying the documented bundle
without preventing a later granular choice.

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
maps and run records. The WP14 review and closed traceability matrix are the
release record. A future deviation records the affected requirement, reason,
impact, owner, evidence, and approval in the traceability matrix; unapproved
missing mobile capability or data-loss/security risk is release-blocking.

The default UI changed at G6, legacy implementation was deleted at G7, and the
replacement passed G8 behavioral, responsive, accessibility, localization,
extension, performance, novice, and expert qualification.
