# Sonder UI Full Replacement Program Design

**Program date:** 2026-08-21

**Implementation baseline:** `1accd2892335138b0ee372a127ab1bf46dbe824b` (`interface`)

**Candidate baseline:** `73a380a0df2f6b139c98d66da9005489bd549d1d`

**Adoption audit:** `docs/design/SONDER_UI_DESIGN_BIBLE_ADOPTION_AUDIT_2026-08-21.md`

**Status:** adversarially self-reviewed; product-owner review pending;
source-level workstream plans follow separately

## Goal

Replace Sonder Engine's entire player-facing and host-facing web interface with
the supplied Design Bible system while preserving current engine behavior,
persistence, security, and supported extension contracts.

This is a full replacement. The old host shell is migration scaffolding, not a
permanent fallback and not part of the finished product.

## Self-review record

The 2026-08-21 adversarial review corrected six structural gaps in the first
program draft:

1. Program status now rolls up through `docs/UNBUILT.md`, Sonder's sole
   unfinished-work register, instead of creating a competing worklist.
2. New Story, authentication/host setup, and guest play are separate work
   packages because they have different authorities, risks, and release gates.
3. The extension host contract and a representative v1 adapter are proven with
   the runtime and shell, rather than discovering incompatibility after every
   destination is built.
4. Untrusted-content rendering, credential handling, and static-module cache
   versioning are explicit runtime contracts.
5. UI-affecting engine changes that land during the program have a drift and
   dual-surface policy, preventing the capability ledger from freezing at one
   old snapshot.
6. Novice and expert usability audits are release evidence, not optional
   follow-up research.

The review also assigns the current vitals/story-width collision recorded in
`docs/UNBUILT.md` section 1.66 to the replacement's Play/Story Tools work rather
than assuming deletion of the old layout automatically proves the defect class
closed.

## Definition of full replacement

The program is complete only when all of the following are true:

- Play, Library, Settings, New Story, authentication, host setup, guest play,
  dialogs, sheets, notices, tasks, editors, themes, and extension-hosted
  surfaces conform to the approved Design Bible.
- Desktop and mobile expose the same capabilities through layouts appropriate
  to each device class.
- `static/index.html` loads the new module-owned application rather than the
  current fixed chain of classic host scripts.
- The new application does not read or mutate `window.S`, poll host state, or
  invoke behavior by clicking hidden legacy controls.
- No old host control is hidden off-screen as an integration technique.
- The current classic host JavaScript, legacy host markup, obsolete host CSS,
  duplicate dialogs, and transitional bridges are deleted.
- The public extension v1 contract remains through an owned adapter implemented
  on the new host. Private DOM-ID dependencies are not promoted into public
  compatibility promises.
- Legacy themes may remain as theme compatibility data, as required by the
  Design Bible, but they do not retain the legacy application shell or redefine
  component geometry.
- Current font assets are preserved unless their licensing or product status is
  changed separately.
- Every requirement has implementation and verification evidence against the
  exact release commit.

## Authority and source use

Use these sources in this order:

1. Current `AGENTS.md`, `Design.md`, maintained `docs/guides/`, schemas,
   persistence code, server routes, and tests for engine and repository
   behavior.
2. The supplied Design Bible for the replacement's product, interaction,
   visual, responsive, accessibility, and content contracts.
3. Approved amendments recorded through the Design Bible change-control
   process.
4. The adoption audit for candidate salvage decisions and known defects.
5. The candidate implementation and screenshots as reusable source and visual
   evidence, never as proof that a current requirement is complete.
6. Current UI behavior as the capability baseline until its replacement passes
   the applicable gate.

The candidate is 78 commits behind the implementation baseline. Candidate
files are ported as scoped changes; the archive is never copied over the
repository.

The Design Bible begins as approved target design under `docs/design/`, because
that directory is context rather than current implementation authority.
The planned `INTERFACE.md` guide under `docs/guides/` becomes the maintained description of what the
current host actually implements and which Design Bible version it is moving
toward. At final cutover, the maintained guide records the completed contract;
the repository must never describe a future target as already built.

## Approaches considered

### Selected: progressive replacement on a separate application entry

Build the new native-module application beside the current host, using current
server APIs directly. Migrate complete workflows into the new application,
then switch the main entry and delete the old host after total parity and
release qualification.

This follows the reference architecture while preventing the candidate's most
serious problem: a new-looking shell that still operates the old application
through polling, globals, DOM IDs, and synthetic clicks.

### Rejected: copy and repair the candidate snapshot

This would save initial porting effort but mix 78 commits of baseline drift
with known incomplete routing, Library, Settings, localization, drafts,
mobile-vitals, and extension behavior. It also preserves legacy coupling as
the center of the new application.

### Rejected: restyle the current classic host in place

This would reach attractive screenshots quickly but leave the fixed global
script chain and multi-thousand-line UI files as the permanent architecture.
It cannot meet the full-replacement outcome without paying for a second rewrite
later.

### Rejected: introduce a framework and compiled frontend toolchain

The supplied architecture explicitly chooses native ES modules without a
mandatory bundler, package manager, or network runtime. The candidate proves
the visual system can be delivered within that constraint. This program keeps
that decision and gains structure through small modules, JSDoc contracts,
explicit state/actions, and browser tests.

### Program amendment to the reference migration architecture

Reference requirement `ARCH-12` proposed one bridge owning legacy host globals
during an in-place migration. This program supersedes that mechanism: the
replacement runs at a separate authenticated entry and never calls classic host
globals. The old entry remains isolated until cutover. The only legacy adapter
inside the replacement is the documented public extension v1 API, which is a
supported external contract rather than a bridge to old host behavior.

This is not a scope reduction. It is the stronger boundary required by the
approved full-replacement outcome and by the adoption audit's rejection of
polling, `window.S`, synthetic clicks, and hidden duplicate controls. WP-00
records the amendment against `ARCH-12` in the imported traceability matrix.

## Target architecture

### Delivery model

- FastAPI continues serving the host, login, and guest entries.
- The replacement host is developed at a dedicated authenticated entry such as
  `/ui-next` until the cutover gate.
- Static source remains directly servable; there is no mandatory Node build.
- A small head-safe theme preflight runs before paint.
- The host loads one native ES-module bootstrap entry.
- Login and guest remain lightweight separate entries that share tokens and
  focused modules without loading the full host.

The exact development route is selected in the first source-level plan. It
must be host-authenticated, clearly non-default, and removable at cutover.

### Proposed source organization

```text
static/
  css/ui/
    reset.css
    tokens.css
    typography.css
    components.css
    shell.css
    utilities.css
    surfaces/
      play.css
      library.css
      settings.css
      entry.css
    themes/
      carbon-signal.css
      ash-brass.css
      midnight-ink.css
      parchment-night.css
      legacy.css
  assets/icons/
    sonder-icons.svg
  js/ui/
    bootstrap.js
    api/
    state/
    routing/
    i18n/
    tasks/
    components/
    shell/
    play/
    library/
    settings/
    entry/
    extensions/
    compatibility/
```

The source-level plans may refine leaf names, but they must preserve these
responsibility boundaries. A module may not become a new monolith merely
because it has an explicit import.

### State and action boundary

The application owns a small evented store with independently selectable
slices:

- session and bootstrap;
- navigation and transient history;
- active story identity and summary;
- transcript, variants, turn progress, and streaming state;
- per-story composer drafts;
- inspector and mobile-sheet state;
- Library query, scope, results, selection, and editor drafts;
- Settings index, section, validation, and save state;
- tasks, notices, and recoverable errors;
- appearance, theme, density, and accessibility preferences;
- extension registrations and lifecycle.

Server truth and browser presentation state stay distinct. Server objects are
not silently mutated in the store. Writes go through named action modules and
return explicit pending, success, validation, authentication, conflict, or
failure outcomes.

Every request whose response can become stale carries an abort signal or
request identity. A response for Story A or Library Item A cannot repaint the
surface after the user has selected B.

Eligible simple edits and removals return a bounded undo receipt or equivalent
reversible action. Undo is offered only where current persistence semantics make
it safe; destructive, structural, security-sensitive, installation, repair,
and expensive operations retain explicit confirmation and recovery instead.

### API boundary

One API client owns:

- JSON encoding and response parsing;
- authentication/session-expiry handling;
- abort and request correlation;
- server validation and conflict mapping;
- safe retry advice for idempotent operations;
- no automatic retry for destructive writes;
- long-running task identity and cancellation.

Existing routes remain authoritative. New presentation endpoints are permitted
when the replacement cannot truthfully implement a Design Bible workflow from
existing contracts. Examples may include aggregate Library scopes, cross-story
usage counts, or indexed settings metadata. Such endpoints must not duplicate
persistence authority or change fiction-engine semantics.

### Router contract

The router owns URL and history state, not business data. Its stable route
families are:

```text
#/play[/<story-id>]
#/play/<story-id>/tools/<tool-id>
#/library[/<type>][/<item-id>]
#/settings[/<section>][/<control-id>]
#/extensions/<extension-id>/<path>
```

Library scope, search, sort, and selection use documented route/query state.
Transient sheets add history entries so Back closes the top transient surface
before leaving its destination. Deleted, retired, unavailable, or disabled
targets fall back to the nearest useful parent and explain what happened.

### Component and CSS contract

- Components have explicit creation/update/cleanup APIs.
- Components own keyboard behavior, focus, localization, and busy/disabled
  semantics rather than leaving them to callers.
- Theme files set semantic values; they do not redefine layout or state meaning.
- CSS cascade layers and deterministic load order replace specificity warfare.
- Inline styles are reserved for measured runtime values, not ordinary visual
  declarations.
- Design tokens cover color, surfaces, typography, spacing, geometry, shadow,
  motion, z-order, density, target size, and reading measure.
- The component laboratory renders the complete applicable state matrix in all
  curated themes and accessibility modes.

### Localization boundary

Every engine-authored UI string goes through the current language-pack
contract. User-authored names, story prose, model output, imported content, and
protocol values remain untranslated. The replacement cannot merge a surface
with hard-coded English and defer extraction.

### Content and credential safety

- User-authored names, imported content, model prose, extension strings, and
  server error detail are untrusted input.
- Ordinary rendering primitives create text nodes or assign `textContent`.
  Rich story rendering uses one reviewed sanitizer/renderer and cannot become a
  general `innerHTML` escape hatch for other surfaces.
- Translation lookup applies only to engine-authored UI strings and never turns
  user/model content into catalog keys.
- Provider credentials, session material, guest tokens, and password fields
  never enter browser-local drafts, route state, diagnostic logs, notices, or
  the general application store beyond the narrow lifetime required to submit
  them.
- The development entry has the same host authentication and extension-asset
  access controls as the production entry.

### Static version integrity

Native modules create a dependency graph that must update as one release. The
server and entries therefore need an explicit cache/version contract so a
browser cannot combine a new bootstrap with stale dependency modules. WP-02
selects and tests either release-versioned URLs or a cache policy that makes the
directly served module graph coherent. Theme preflight, extension assets, login,
and guest entries follow the same release-version rule where they share files.

### Extension boundary

The final host provides a versioned, owner-attributed extension surface with:

- Add-ons settings sections;
- Library content types or views;
- Story tools;
- destination views and route namespaces;
- composer controls where approved;
- task/notice providers;
- semantic tokens and host components or class contracts;
- failure charging, disable/retire cleanup, and route fallback.

The existing public v1 calls remain available through an adapter during the
supported migration. That adapter calls new host APIs and renders into new
owned slots; it does not recreate old private DOM IDs. The candidate's
`registerSlot` implementation is not used because it loads too late, renders
nothing, and is outside current teardown ownership.

## Program control artifacts

The replacement maintains these living artifacts:

1. **Requirement matrix** — imported from the reference and amended by the
   adoption audit; each row links implementation, automated evidence, manual
   evidence, and deviations.
2. **Capability ledger** — every current player-facing action, state, route,
   dialog, editor, task, extension slot, auth/guest behavior, and mobile path,
   mapped to its replacement.
3. **Candidate salvage ledger** — each candidate file or idea marked direct
   port, adapted port, visual reference, rebuilt, or rejected.
4. **API and persistence map** — current routes, ownership, writes, destructive
   actions, archive/checkpoint implications, and any approved new presentation
   endpoint.
5. **Global and DOM dependency inventory** — all current browser globals,
   forward references, private IDs, inline handlers, extension dependencies,
   and removal status.
6. **State and screenshot fixtures** — populated, empty, loading, offline,
   validation, error, long/localized, large-data, and active-turn cases.
7. **Deviation register** — requirement, evidence, desktop/mobile,
   accessibility, localization, migration, approval, and expiry.
8. **Verification record** — exact commit and command/browser/device evidence
   for each gate.

`docs/UNBUILT.md` receives one umbrella entry for the replacement and remains
the repository's only unfinished-work register. The detailed requirement,
capability, and salvage ledgers are execution evidence linked from that entry,
not independent status authorities. The umbrella entry is deleted in the same
commit that completes the final program gate, following the register's rules.

No aggregate percentage can close the program. A work package closes only when
its own requirements and capability rows are closed.

## Candidate salvage policy

### Port first, then verify

- `sonder-icons.svg` and its icon language;
- semantic token values and four curated theme directions;
- visual composition and responsive reference screenshots;
- shell, Play, Library, Settings, inspector, auth, and guest layout concepts;
- Soft-Precision Geometry and control-cluster styling;
- the three-route New Story interaction concept;
- accessibility preference vocabulary;
- candidate browser helpers and useful geometry fixtures.

### Adapt substantially

- shell markup and CSS;
- icon helper and explicit icon consumers;
- inspector lifecycle;
- Play composition and turn-state presentation;
- auth and guest presentation;
- theme preflight and migration;
- accessibility preferences;
- candidate test assets.

### Rebuild behind final contracts

- application state and actions;
- router and browser history;
- API client and error model;
- composer draft ownership;
- Library scopes, search, association model, and editors;
- Settings registry, search, deep links, and save behavior;
- Story Tool hosting;
- extension v2 and its lifecycle;
- localization integration.

### Never carry forward

- `window.S` as the new application's state source;
- interval polling for host changes;
- `clickLegacy` or synthetic activation of old controls;
- invisible off-screen legacy controls;
- mobile rules that hide vitals/condition capability;
- unconsumed extension slots;
- hard-coded remaster copy;
- archive-driven deletion of existing font assets;
- source-presence tests presented as behavioral closure.

## Program sequence

```text
WP-00 Program control and baseline
  ├─> WP-01 Design system and component laboratory
  └─> WP-02 Runtime boundaries: API, state, routing, i18n, tasks
          └─> WP-03 Application shell and responsive navigation
                ├─> WP-04 Play core
                │     └─> WP-05 Story Tools and scene utilities
                ├─> WP-06 Library data model and discovery
                │     └─> WP-07 Library editors and authoring flows
                ├─> WP-08 Settings and accessibility control center
                └─> WP-09 New Story and first run

WP-01 + WP-02 entry contracts ────────> WP-10 Authentication and host setup
                                  └───> WP-11 Guest join and play
WP-01 + stable destination contracts ─> WP-12 Themes and extensions
WP-04 through WP-12 complete ─────────> WP-13 Cutover and legacy deletion
WP-13 complete ───────────────────────> WP-14 Release qualification
```

WP-01 and WP-02 may overlap after their shared contracts are recorded. After
WP-03 stabilizes, destination work may overlap only when file ownership and
shared contract changes are isolated. No destination may invent its own
tokens, router, save model, responsive rules, or error vocabulary.

### Reference requirement-family ownership

The reference traceability matrix contains 170 requirements across 15 named
families. WP-00 imports the individual rows, but their program ownership is
fixed here so none can disappear during decomposition.

| Family | Rows | Program owner(s) |
|---|---:|---|
| `GOV` | 10 | WP-00 establishes governance; WP-13 and WP-14 close it |
| `IA` | 10 | WP-03, with destination route evidence from WP-04 through WP-12 |
| `RESP` | 12 | WP-01 and WP-03 define it; every surface proves it; WP-14 closes it |
| `PLAY` | 16 | WP-04 and WP-05 |
| `LIB` | 16 | WP-06 and WP-07 |
| `SET` | 14 | WP-08 |
| `ONB` | 8 | WP-09 |
| `AUTH` | 6 | WP-10 and WP-11 |
| `THEME` | 13 | WP-01 and WP-12 |
| `ICON` | 10 | WP-01 and WP-12 |
| `A11Y` | 14 | WP-01 defines shared behavior; every surface proves it; WP-14 closes it |
| `SAVE` | 8 | WP-02 contract; WP-04, WP-07, WP-08, WP-09, and WP-11 workflows |
| `ARCH` | 14 | WP-02, WP-03, and WP-13 |
| `EXT` | 7 | WP-02 and WP-03 prove the boundary early; WP-08 and WP-12 complete it |
| `VER` | 12 | WP-00 establishes evidence; every gate contributes; WP-14 closes it |

Accessibility, content/terminology, responsive parity, localization, and state
completeness are cross-cutting Design Bible contracts. The 14 `A11Y` rows are
an explicit family; the remaining cross-cutting contracts also constrain every
applicable family. Each surface owns its applicable rows; WP-14 audits them
across the product.

## Work packages

### WP-00 — Program control, current baseline, and parity inventory

**Outcome:** a trustworthy control plane for the replacement.

**Deliverables:**

- reconcile and import the Design Bible under `docs/design/`, create the
  maintained `INTERFACE.md` guide under `docs/guides/`, update `docs/README.md`, and verify/update the one
  umbrella replacement entry already present in `docs/UNBUILT.md`;
- import its requirement matrix with audit corrections;
- create the complete capability, surface, API, global, DOM-ID, theme, and
  extension inventories;
- capture current baseline screenshots and browser behavior;
- record performance baselines for boot, 500-turn transcript, Library scale,
  active effects, and idle traffic;
- convert those measurements into recorded release budgets or explicit
  comparison thresholds before implementation can make the baseline harder to
  reproduce;
- identify frontend drift from `73a380a` to the implementation head;
- identify every UI-relevant entry already in `docs/UNBUILT.md`, including the
  story-width/vitals collision in section 1.66, and assign it to a replacement
  requirement rather than duplicating it;
- create the development entry and an isolated browser-test fixture without
  changing the default UI.

**Exit gate:** every current capability is mapped or explicitly proposed for
removal; baseline `make check` and `make test-browser` evidence is recorded;
all requirements have a work-package owner.

### WP-01 — Design system and component laboratory

**Outcome:** the visual and interaction foundation exists independently of any
destination.

**Deliverables:**

- port and reconcile tokens, typography, icons, curated themes, geometry,
  density, motion, z-order, and surface rules;
- verify the icon/font/theme asset provenance and retain the repository's
  licensed font payloads unless a separate asset decision replaces them;
- implement buttons, fields, text areas, selects, toggles, segmented controls,
  tabs, menus, list rows, cards, control clusters, dialogs, sheets, notices,
  task status, skeletons, empty/no-result/error states, and confirmation
  patterns;
- implement focus trap/restore, roving focus where appropriate, live-region
  restraint, and target-size guarantees;
- build a repository-local component laboratory used by Playwright and
  screenshot generation.

**Exit gate:** every applicable component state renders under four curated
themes, solid surfaces, reduced motion, Accessibility Mode, large UI/prose,
high contrast, and long localized text; semantic and keyboard tests pass; the
component system and primary shell composition receive an explicit visual-system
review before destination work scales.

### WP-02 — Runtime boundaries

**Outcome:** the new application can operate current Sonder without depending
on classic globals or DOM shims.

**Deliverables:**

- native bootstrap entry and global error boundary;
- shared API client and normalized error outcomes;
- evented state store, selectors, actions, cleanup, and request identity;
- route parser/history/fallback contract;
- UI localization adapter and catalog extraction integration;
- task, notice, and recoverable-error services;
- versioned browser-local storage for appearance, navigation, pane state, and
  drafts;
- the shared save policy, including visible save states, stale-write refusal,
  safe undo receipts, and explicit-action classification;
- coherent static-module cache/version behavior across host, login, guest, and
  shared assets;
- safe text/rich-content rendering primitives and narrow credential submission
  paths;
- the versioned extension registry/lifecycle contract plus a representative v1
  adapter fixture, before destination slots are finalized;
- explicit development diagnostics without ordinary-player log noise.

**Exit gate:** a test harness boots with no current host scripts, performs
authenticated reads/writes through the real route shapes, survives session
expiry, aborts stale reads, restores safe presentation state, rejects unsafe
content insertion, never persists credential material, cannot load a mixed
module release, runs the representative v1 extension fixture, and introduces
no unregistered globals beyond the documented extension adapter.

### WP-03 — Application shell and responsive navigation

**Outcome:** the final Play/Library/Settings frame works across all supported
layout states.

**Deliverables:**

- indexed desktop navigation, mobile bottom navigation, destination headers,
  center workspace, right inspector host, overlay stack, and safe areas;
- compact, medium, wide, and expansive layout states;
- deep links, refresh restoration, transient-sheet history, fallback messages,
  focus restoration, and scroll-state ownership;
- one shortcut registry plus a Go To launcher for expert navigation, with
  localized labels, extension collision handling, and guards that prevent
  ordinary shortcuts from firing while the user is typing;
- extension destination boundary;
- no global settings controls in Play.

**Exit gate:** the three destinations and nested placeholder routes pass
pointer, touch, and keyboard journeys across the full viewport matrix with no
horizontal overflow, hidden capability, or legacy script/DOM dependency. A
representative v1 extension mounts, navigates, fails safely, and unmounts
through the shell boundary before G2 closes.

### WP-04 — Play core

**Outcome:** reading, composing, streaming, stopping, retrying, rerolling, and
variant navigation work entirely in the new application.

**Deliverables:**

- story selection/open/switch/rename/archive and no-story state;
- transcript rendering, scrollback, emphasis, speaker handling, variants, turn
  actions, and long-history virtualization/performance behavior;
- literary composer, per-story drafts, send/stop/retry, validation, session
  loss, and failure recovery;
- current turn progress and optional technical detail through Advanced;
- reroll semantics that preserve Sonder's checkpoint/rollback authority;
- background tasks and notices that do not obscure the story.

**Exit gate:** all Play-core capability rows pass in the new entry, including
Story A/B draft isolation, stale response protection, active stream lifecycle,
500-turn transcript performance, keyboard/mobile composer behavior, and no
prose reflow from chrome state.

### WP-05 — Story Tools, conditions, and scene utilities

**Outcome:** every current-story tool is module-owned and context-safe.

**Deliverables:**

- Cast, World, Style, Dialogue, Attire, Backdrops, Ambience, conditions/vitals,
  frames, multiplayer/guest administration, and turn-detail placement;
- desktop inspector pin/resize/replace/close behavior;
- mobile full-screen staged tools and Back behavior;
- backdrop, weather, ambience, chime, and effects integration;
- replacement tests for the `docs/UNBUILT.md` section 1.66 defect class: no
  condition/vitals or utility rail may overlap the story/composer when minimum
  reading measure competes with a measured side reservation;
- story-switch invalidation and running-task preservation.

**Exit gate:** every tool has desktop/mobile routes and full state coverage;
opening, pinning, resizing, closing, or switching tools cannot reset transcript
position, drafts, active turns, media state, or selected story. Conditions
remain available on mobile.

### WP-06 — Library data model, discovery, and associations

**Outcome:** the unified Library tells the truth about reusable records and
their story associations.

**Deliverables:**

- authoritative Library projection for Stories, Characters, Personas, and
  Lore;
- All, Current Story, Choose Story, Unassigned, and Used in Multiple Stories
  scopes;
- cross-type search, filters, sorting, recents, favorites, drafts, counts, and
  no-result/error/loading states;
- item routes, selection, usage/association summaries, attach/detach semantics,
  and delete/archive distinction;
- bounded undo for safe recent detach/archive/simple metadata operations, while
  true destructive deletion remains explicit;
- any narrowly required presentation endpoints and their tests.

**Exit gate:** scope and association fixtures match database truth; detaching
never deletes reusable material; stale requests cannot replace the current
selection; desktop split and mobile staged navigation have feature parity.

### WP-07 — Library editors and authoring workflows

**Outcome:** all asset management leaves legacy dialogs and becomes a coherent
Library workflow.

**Deliverables:**

- story overview and management;
- Character and Persona editors with every current field preserved;
- Lore workspace, hierarchy, entries, relationships, generation, recovery, and
  long-form editing;
- create, duplicate, rename, import, export, generate, attach, detach, archive,
  delete, and promotion flows where currently supported;
- hybrid autosave/explicit-save policy, drafts, validation, conflicts, failure
  recovery, safe bounded undo, and leave protection;
- mobile list-to-detail/editor staging.

**Exit gate:** field-completeness diffs show no silent data loss; import/export
and interrupted-generation tests pass; long drafts survive navigation and
failures; all old asset-management dialogs have replacement routes.

### WP-08 — Settings and accessibility control center

**Outcome:** every host setting is indexed, searchable, routed, and saved
through the new UI.

**Deliverables:**

- Experience, AI Connections, Content, Add-ons, Maintenance, and Advanced;
- one localized settings registry containing labels, aliases, help, route,
  permissions, save policy, and component renderer;
- global Settings search and control-level deep links;
- provider/model/credential setup and connection tests;
- themes, language, sound, notifications, effects, density, and accessibility;
- adult-content presentation, updates, storage, backup/checkpoint, repair,
  prompts, diagnostics, experiments, and extension management;
- validation, save/saving/saved/failed, restart-required, scoped reset, and
  destructive confirmation behavior;
- bounded undo for simple settings edits/removals where persistence semantics
  make reversal safe.

**Exit gate:** every current settings control has exactly one intentional
destination; aliases and localized search reach it; mobile retains all
capabilities; consequential actions never autosave; failure injection preserves
input and explains recovery.

### WP-09 — New Story and first run

**Outcome:** every player can create an ordinary Sonder story through the
approved guided paths without introducing a parallel simplified data model.

**Deliverables:**

- Describe a Story, Use My Library, and Start Blank with resumable setup draft;
- provider-optional manual creation and provider-aware generation;
- current language, character/persona/lore selection, validation, card
  warnings, and final ordinary story creation;
- review/edit navigation, save/resume/discard, failure recovery, and explicit
  model-cost boundaries;
- empty-Library and unavailable-provider recovery paths.

**Exit gate:** all three creation paths complete on desktop/mobile with and
without a provider as applicable; setup drafts are isolated and recoverable;
every result is an ordinary current-schema story that opens in Play.

### WP-10 — Authentication, host setup, and session lifecycle

**Outcome:** the replacement login and first-host experience preserves the
current security boundary and gives session loss a predictable recovery path.

**Deliverables:**

- first-host setup, sign-in, sign-out, reauthentication, and session-expiry
  presentation;
- trusted-event, password, cooldown, lockout countdown, redirect, autocomplete,
  and network/server failure behavior;
- narrow credential submission that does not enter general state, storage,
  diagnostics, or notices;
- shared entry tokens/components without loading the full host application;
- safe restoration of non-secret navigation/draft context after successful
  reauthentication where current semantics permit it.

**Exit gate:** current auth policy tests remain unchanged and green; setup,
login, invalid credentials, cooldown, lockout, sign-out, restart, session
expiry, and reauthentication journeys pass on desktop/mobile; accessibility and
localization states are complete.

### WP-11 — Guest join and guest play

**Outcome:** guests receive the new reading/composer experience without access
to host-only data, settings, routes, or extension code.

**Deliverables:**

- join-code entry, redemption, session resume, guest transcript/composer,
  turn submission, busy state, and session end;
- preservation of current polling, visibility pause, stale-response, and
  in-flight request guards behind explicit guest-owned state;
- connection-loss, retry, host-unavailable, expired/revoked-session, and inline
  error recovery;
- guest draft preservation within the allowed session lifecycle;
- lightweight entry assets with no host extension bundle or host-only state.

**Exit gate:** join/resume/send/busy/error/visibility/revocation/expiry journeys
pass on desktop/mobile; no ordinary recoverable error uses `alert`; browser and
route evidence proves host-only information and extensions never reach the
guest entry.

### WP-12 — Themes, extensions, and compatibility contracts

**Outcome:** the replacement is a stable host platform rather than a closed
application.

**Deliverables:**

- complete Carbon Signal, Ash and Brass, Midnight Ink, and Parchment Night;
- Legacy theme mapping to semantic tokens without layout ownership;
- versioned extension v2 registrations, slots, route namespace, permissions,
  token contract, lifecycle, attribution, failure containment, and teardown;
- public extension v1 adapter implemented on the new host;
- representative classic and ES-module extension fixtures;
- CSS containment rules and documented limits on private DOM dependence;
- source-level SVG icon completion.

**Exit gate:** curated theme/accessibility matrices pass; representative Legacy
themes remain usable; v1 and v2 fixtures pass load/hot-load/disable/retire/error
journeys; a retired extension cannot strand a route or surface; extension CSS
cannot silently corrupt core layout within the supported contract.

### WP-13 — Default cutover and legacy deletion

**Outcome:** the replacement becomes the only host UI implementation.

**Deliverables:**

- point the authenticated root at the replacement entry;
- remove the development route/flag;
- delete old host markup, classic script loading, compatibility click paths,
  hidden controls, old host CSS, and duplicate dialogs;
- remove `window.S` and polling bridges;
- remove or module-migrate remaining behavior in `utils.js`, `components.js`,
  `editors.js`, `lorebooks.js`, `backdrops.js`, `ambience.js`, `weather-fx.js`,
  `chime.js`, `chat.js`, `settings.js`, `themes.js`, and `app.js`;
- retain only explicitly supported public extension adapters and Legacy theme
  data;
- update `docs/guides/ENGINEERING.md`, `docs/guides/EXTENSIONS.md`,
  the maintained `INTERFACE.md` guide, `docs/guides/LANGUAGE_PACKS.md`,
  `docs/guides/TESTING.md`, `docs/README.md`, feature inventory, structure
  checks, and generated code map.

**Exit gate:** source search finds no supported caller of removed globals/IDs;
the application boots with no legacy host file; there is no fallback shell;
every capability ledger row is closed; clean-install and upgraded-install
journeys both reach the same new UI.

### WP-14 — Release qualification and adversarial audit

**Outcome:** the exact release commit is proven complete rather than inferred
from work-package success.

**Deliverables:**

- complete Chromium journeys and required Firefox/WebKit smoke coverage;
- continuous resize plus the full screenshot/input matrix;
- keyboard, accessibility-tree, practical screen-reader, touch, safe-area,
  virtual-keyboard, 200-percent zoom, and long-localization evidence;
- four-theme, Legacy, solid, high-contrast, reduced-motion, large-interface,
  and color-independent state matrices;
- performance comparison for boot, idle, transcript, Library, effects, and
  repeated navigation/listener cleanup;
- extension compatibility and localization reports;
- novice audit covering destination recognition, first story creation,
  hesitation, misleading labels, dead ends, and error recovery;
- expert audit covering action counts, shortcuts, recents, search, persistent
  panes/filters, compact density, and whether More hides frequent actions;
- final surface/capability audit and independent search for partial legacy
  treatments;
- delete the UI replacement umbrella entry from `docs/UNBUILT.md` only after
  the exact-head evidence closes every linked requirement;
- exact-head `make check`, `make test-browser`, and packaging evidence.

**Exit gate:** no open P0; no open P1 without explicit product-owner deviation;
no unapproved missing capability; measured performance meets the WP-00 budgets
or has an approved evidence-backed deviation; all traceability rows are closed;
release package and screenshots reproduce the reviewed result.

## Gate model

| Gate | Decision enabled | Required proof |
|---|---|---|
| G0 — Baseline locked | Start replacement source work | WP-00 inventories, drift classification, clean baseline gates |
| G1 — Foundations accepted | Build product surfaces | Component laboratory, runtime harness, accessibility/theme states, visual-system review |
| G2 — Shell contract stable | Allow destination work to overlap | Router/history/focus/responsive tests, representative v1 extension adapter, no legacy dependency |
| G3 — Play parity | Treat new host as viable for real play | WP-04 and WP-05 capability closure, long-play and stream evidence |
| G4 — Product-surface parity | Stop adding features to the old product surfaces | WP-06 through WP-11 closure and data-loss/security review |
| G5 — Host compatibility | Freeze extension/theme contracts | WP-12 lifecycle and theme matrices |
| G6 — Cutover eligible | Switch root entry | All capability rows closed; no open P0/P1; rollback rehearsal |
| G7 — Legacy eliminated | Remove fallback and freeze deletion | WP-13 source search, clean/upgraded install, docs/map/structure |
| G8 — Release qualified | Merge/release | WP-14 exact-commit evidence package, novice/expert audits |

Passing a later-looking screenshot cannot waive an earlier gate.

## Increment and review model

This program document does not prescribe one enormous source-level plan. Each
work package receives its own implementation plan immediately before execution,
after the contracts it depends on are stable. That keeps file paths and tests
accurate while preserving the whole-program destination.

WP-05, WP-07, WP-08, and WP-12 are themselves too broad for one source-level
plan. They must be decomposed into independently gateable subplans: Story Tool
families; story/character-persona/lore authoring; Settings category groups; and
theme/extension contract families respectively. A subplan may share a work
package gate, but it must own a distinct capability set and test cycle.

Each implementation task must:

1. close a coherent requirement/capability subset;
2. begin with a failing behavioral or structural test appropriate to the
   contract;
3. port only the candidate artifacts named in its salvage ledger entries;
4. run the narrow test first and the work-package gate before review;
5. update traceability and maintained guidance in the same commit as behavior;
6. be independently reviewable and reversible before cutover;
7. avoid unrelated engine refactors and preserve unrelated branch work.

Every major screen or component family receives the four Design Bible reviews
before its work-package gate: product flow, visual system, responsive behavior,
and implementation/state preservation. A single code review is not a substitute
for those four perspectives, though one review session may record all four.

The `interface` branch is the program integration line. Larger work packages
should execute in isolated worktrees/branches and integrate only after their
gate passes. Current engine branches may continue advancing; every integration
refreshes the frontend drift check rather than replacing current files with an
older snapshot.

### Ongoing repository-change policy

- Every integration compares current UI, server routes, language catalogs,
  extension contracts, and browser tests with the last program baseline.
- A newly landed player-facing capability receives a capability-ledger and
  requirement owner before the replacement branch absorbs it.
- Before G4, a capability required on the currently released legacy UI may need
  a minimal legacy presentation, but its replacement path is implemented in the
  same program window; the old implementation is never treated as the new
  design source.
- After G4, legacy product-surface feature work is frozen except for security,
  data-loss, or release-blocking corrections. New ordinary capability work
  targets the replacement.
- A backend or schema change that affects UI truth updates both its maintained
  guide and the replacement contract in the same integration.

## Test strategy

### During a task

- Use focused Python tests for route, persistence, auth, language-pack, and
  extension-server behavior.
- Use browser tests for event wiring, focus, history, persistence, async races,
  state visibility, responsive layout, and actual user journeys.
- Use component fixtures for systematic state/theme/accessibility coverage.
- Use source/structure checks only as tripwires, never as proof a workflow
  works.

### At a work-package gate

- run all focused tests owned by the package;
- run affected cross-destination browser journeys;
- run the relevant viewport/theme/accessibility matrix;
- inspect the capability and requirement ledgers for omissions;
- refresh generated catalogs/maps when their source changed;
- run `make check` and `make test-browser` when shared contracts or release
  surfaces changed.

### At release

Run the full reference verification hierarchy from the Design Bible against the
exact release commit. Historical candidate test counts are evidence about the
candidate only and never satisfy a current gate.

## Failure, rollback, and data safety

- The new UI uses current server records; it does not create a parallel story,
  character, persona, lore, settings, or extension persistence model.
- Browser-local migrations are versioned, idempotent, and retain unknown old
  values until a user confirms replacement where practical.
- Editor drafts are bounded, versioned, scoped to their true record/story, and
  exportable or recoverable for consequential long-form work.
- Before G6, rollback means returning to the old root entry or reverting scoped
  frontend commits; no irreversible database migration is allowed merely for
  presentation.
- G6 includes a rollback rehearsal, but the released G8 product contains no
  supported legacy shell.
- Any server-backed rename reads the old value through a documented migration
  period and proves upgraded installations retain behavior.
- Destructive writes identify the exact object and do not retry automatically.
- Authentication, guest sessions, rerolls, checkpoints, archives, and
  extension commit domains keep their current authority.

## Primary risks and controls

| Risk | Program control |
|---|---|
| Candidate baseline drift | Scoped porting, drift check at every integration, current tests as authority |
| Attractive shell masking incomplete behavior | Capability ledger and workflow gates; no screenshot-only closure |
| New monolith replacing old monolith | Responsibility-based modules, contract freeze at G1/G2, file review |
| State races and cross-story leakage | Request identity/abort, per-record draft keys, adversarial switching tests |
| Library ownership/association corruption | Server-truth fixtures, detach/delete separation, database guide review |
| Mobile capability loss | Same ledger for desktop/mobile; missing mobile action is P1 |
| Localization added late | UI strings enter through catalogs in the task that creates them |
| Extension breakage | Public v1 adapter, v2 lifecycle tests, representative fixtures, no private-ID promise |
| Legacy CSS contaminating new UI | Separate entry and styles during development; no classic sheets in final entry |
| Cutover before deletion is safe | G6 eligibility, rollback rehearsal, G7 clean/upgraded-install proof |
| Engine behavior changes hidden in UI work | Diff classification, maintained guides, full suite, separate justification |
| Performance loss on long stories | WP-00 baselines, 500-turn fixture, listener/DOM growth checks, effects gates |

## Explicit non-goals

- redesigning story generation, agents, prompts, world simulation, or the
  information firewall;
- replacing FastAPI or the current persistence model;
- adding a mandatory frontend build toolchain;
- retaining the old host shell as a user-selectable finished product;
- guaranteeing compatibility with extensions that mutate undocumented private
  host DOM;
- using the UI replacement as permission for unrelated repository cleanup;
- declaring completion from candidate test records, source-string assertions,
  or selected screenshots.

## Program completion checklist

- [x] All WP-00 through WP-14 exit gates pass on recorded commits.
- [x] All Design Bible requirements and adoption-audit corrections are linked
      to current implementation and evidence.
- [x] Every current capability is present, explicitly approved for removal, or
      superseded by a documented equivalent.
- [x] The final host entry loads no legacy host scripts or styles.
- [x] No `window.S`, state polling, synthetic legacy clicks, hidden controls,
      or duplicate legacy dialogs remain.
- [x] Public extension compatibility and Legacy theme behavior match their
      documented final contracts.
- [x] Desktop/mobile parity, localization, accessibility, theme, performance,
      and long-content evidence is complete.
- [x] Maintained guides, feature inventory, UI catalog, structure checks, and
      generated code map describe the replacement accurately.
- [x] Exact-head `make check` and `make test-browser` pass.
- [x] Final adversarial audit has no unapproved P0 or P1 finding.

Only then is the Sonder UI replacement finished.
