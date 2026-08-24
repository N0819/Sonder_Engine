# Sonder Progressive Interface Redesign

**Date:** 2026-08-24  
**Status:** Approved for implementation  
**Authorization:** Product-owner implementation brief, 2026-08-24  
**Change class:** Design Bible Revision  
**Amendment:** [`../../design/sonder-ui-bible/amendments/2026-08-24-progressive-interface-redesign.md`](../../design/sonder-ui-bible/amendments/2026-08-24-progressive-interface-redesign.md)

## Outcome

Sonder remains a deep fiction workspace, but its production interface stops
showing that depth all at once. Play, Library, and Settings remain the only
top-level destinations. Play is the dominant reading and writing surface;
secondary capability appears through contextual drawers, staged detail views,
menus, filter sheets, and Advanced disclosures.

The redesign keeps the current vanilla ES-module application, hash router,
immutable store slices, services, local-state envelopes, localization,
accessibility utilities, extension contracts, and server authority. It changes
presentation and presentation-only state, not story semantics or persistence.

## Evidence and current-state inventory

The product-owner brief and the supplied `Sonder_UI_UX_Audit.md` identify the
same hierarchy defects. The verified screenshot archive remains available as
historical composition evidence at SHA-256
`299ad1fbb7edd60255f2cd2bf160e43479fc382a355be9218f60308983d94fe0`, but
the macro compositions explicitly replaced by this specification are no longer
conformance targets.

The implementation baseline is `interface` commit `93e07695`. Focused browser
coverage for shell, Play, Library, Story Tools, Settings, and New Story passes
at 130 tests. A deterministic before set is recorded under
`docs/design/sonder-ui-replacement/redesign/before/shell/`.

### Shell

- `shell.js` already owns the four layout names and the 720/1100/1440
  transitions, but the calculation is private and untested as a pure module.
- `shell.css` has a base layout followed by a late reference-conformance pass;
  both set rail, header, inspector, and compact geometry.
- `inspector-host.js` treats missing `open` and `pinned` values as true and
  retains Story Tool Expanded/Compact/Rail modes.
- wide Play therefore opens with a 352 px contextual panel and a duplicate
  Story Tools opener.
- compact Go To and the Play title are independently fixed, causing collision.
- route changes focus headings directly and expose a form-like browser outline.
- Go To owns `mod+k`, route layers, focus containment, and extension results,
  but presents a flat destination list rather than grouped commands.

### Play

- `play-runtime.js` owns story selection, drafts, generation, retry, stop,
  refresh, turn mutation, and stale-request rejection; it remains authoritative.
- `play-view.js` already renders recent story buttons, transcript previews,
  recoverable errors, turn operations, and atmosphere state.
- submitted player directions use bordered field-like plates.
- every generated turn exposes persistent Edit, Reroll, Versions, and More
  chrome.
- composer input, send/stop/retry, help, progress, mute, and volume are separate
  blocks rather than one integrated plate.
- Play and Library still include decorative grid backgrounds.

### Library

- `library-runtime.js` owns route/query projection, bounded recents/favorites,
  mutation receipts, undo lifetime, and stale-owner rejection.
- the view owns type, scope, story scope, query, sort, visibility, selection,
  and explicit Open in Play behavior.
- search and selects use the noncanonical `ui-input` class.
- filter controls occupy too much mobile height and visible row ordinals add no
  meaning.
- the projection exposes real summaries and associations but the default row
  treatment underuses available imagery and recognition metadata.
- wide detail already uses the contextual host; compact detail is history-owned.

### Story Tools

- the stable registry contains ten tools and the runtime owns story/frame/tool
  request identity and teardown.
- the flat list exposes numeric ordinals; shell CSS hard-codes `TOOLS / 08`.
- detail mode retains an icon-only horizontal switcher.
- the old Rail presentation compresses unfamiliar tools into ambiguous icons.

### Settings

- the current branch includes a grouped overview projection and server-confirmed
  persistence. Fresh `/api/settings` acknowledgement remains the save boundary.
- `settings-view.js` is 3,144 lines and combines definitions, navigation,
  search, route interpretation, rendering, focus, and every control family.
- current maintained guidance says the Settings root opens Theme and compact
  layouts show grouped disclosures plus detail. This specification supersedes
  that composition: compact layouts show overview or detail, never both.
- desktop keeps one category navigation and one detail with a single explicit
  scroll owner.
- raw theme and schema-shaped editors remain available, but move behind
  Advanced entry points.

### New Story and authoring

- New Story already owns three routes, local draft recovery, Back, validation,
  partial-story cleanup, retry, and lived-location setup.
- route choices expose decorative indices and the modal becomes form-heavy too
  early.
- person authoring already preserves unknown fields losslessly; its ordinary
  editor may stage raw representations more deeply without changing data
  authority.

## Responsive shell contract

One pure layout contract owns responsive classification and pin eligibility:

```js
export const SHELL_METRICS = Object.freeze({
  expandedRail: 192,
  collapsedRail: 72,
  contextDrawer: 352,
  minimumReadingMeasure: 680,
  horizontalAllowance: 64,
});

export function layoutStateFor(width, height) {
  if (width < 720 || (height <= 430 && width < 900)) return "compact";
  if (width < 1100) return "medium";
  if (width < 1440) return "wide";
  return "expansive";
}
```

- compact: stable top app bar, labeled bottom navigation, full-height contextual
  sheets or replacement detail views;
- medium: 72 px rail and overlay drawers;
- wide: 192 px labeled rail by default, user-collapsible to 72 px, overlay
  drawers;
- expansive: same rail, overlay drawer by default, optional explicit pin only
  when measured content remains at least 680 px.

The root exposes `data-layout-state`, `data-nav-collapsed`, and
`data-context-mode="closed|overlay|pinned"`. The shell retains stable `nav`,
`header`, `main`, `aside`/dialog, overlay, notice, and task landmarks. A compact
app header supplies title, Back when nested, command access, one contextual
action, and overflow only when needed. No destination independently fixes
header actions.

The local-state migration treats missing inspector values as closed and
unpinned. A prior explicit choice remains bounded and valid, but an unavailable
pin degrades to overlay without changing server state. One context content
instance is mounted at a time. Overlay Back and Escape remain router-owned;
focus returns to the opener.

## Shared presentation components

- `route-focus.js` focuses a noninteractive route target with a temporary class
  that suppresses only programmatic target decoration. Interactive
  `:focus-visible` remains unchanged.
- `field.js` creates the canonical labeled field shell and control class, with
  help/error association supplied through existing primitives.
- `app-header.js` projects destination/detail title and scoped actions without
  reading services directly.
- `responsive-drawer.js` calculates closed/overlay/pinned presentation and owns
  explicit teardown around the existing overlay controller.
- `media-row.js` renders a semantic item from a category-specific adapter. It
  never fabricates metadata and uses local imagery or intentional fallbacks.
- `filter-sheet.js` stages secondary filters and returns focus through the
  shared overlay contract.

Components accept localized complete strings from callers, expose stable data
attributes, and return teardown when they register listeners, overlays,
observers, timers, or subscriptions.

## Destination composition

### Play

- The story header contains real title/context, meaningful save/generation
  state, Story Tools, and one More menu. Missing context is omitted.
- The transcript remains centered serif prose at a 680-720 px measure.
- submitted directions use a restrained editorial rule/tone, never readonly
  field styling or chat bubbles.
- pointer layouts reveal secondary turn actions on hover/focus-within and keep
  them keyboard reachable; coarse pointers always show a 44 px More action.
- the composer is one raised plate with an auto-growing textarea and the
  current send/stop/retry action. Generation detail and ambience move into
  compact disclosures while using the existing runtime state.
- empty Play presents New Story first, then real recent stories with direct
  Continue actions, then Library. It omits unavailable metadata.
- loading, generation, preview/save, recoverable error, offline, unavailable,
  and empty transcript remain distinct and announce meaningful state.

### Library

- primary categories are All, Stories, Characters, Personas, and Lore when
  supported by the projection.
- the visible toolbar contains persistent search, compact sort, Filter, and the
  contextual New/import cluster. Scope, visibility, story associations, and
  secondary constraints move to a popover/sheet.
- active filters appear as removable chips only when active.
- category adapters feed shared media rows/cards with real image, summary, and
  association data. Missing images use initials or the local category icon.
- at 390 px the first ordinary result begins no more than 240 px below the
  destination-content top.
- wide selection opens the global overlay detail by default; compact selection
  replaces the list. Back restores route query, filters, sort, scroll, and focus.
- dense expert presentation remains available through the existing Compact
  preference rather than being the default.

### Story Tools

Every registry item belongs to exactly one group:

- Scene: Cast, World, Conditions, Attire;
- Presentation: Style, Dialogue, Backdrops, Ambience;
- Structure and collaboration: Frames, Multiplayer.

The grouped landing shows recent tools (maximum three unique IDs) followed by
labeled rows and descriptions. Detail shows Back, heading, group, controls,
and an optional labeled selector. Compact layouts expose list or detail, never
both. Numeric ordinals, decorative totals, Rail mode, and the icon-only detail
strip are deprecated.

### Settings

The user-facing concepts are:

1. Account and access;
2. AI and models;
3. Appearance and accessibility;
4. Story defaults and content;
5. Data, extensions, and maintenance;
6. Advanced.

Definitions and routing become separate from overview, detail, search, and
navigation renderers. Existing route segments remain compatibility inputs and
resolve to the new concepts. Desktop shows a 220-240 px navigation plus one
detail. Compact and medium show overview or detail; detail has sticky Back and
title. Search opens the matching detail and focuses/reveals the control.
`[data-settings-content]` remains the only vertical scroll owner. Theme defaults
show curated previews and comfort controls; semantic-color and JSON tools live
in Advanced Theme Editor. No setting is removed, and failed writes retain
drafts and persistent notices.

### New Story and editors

The three routes remain Describe a story, Use my Library, and Start blank,
without indices. The flow stages route, essential direction, applicable assets,
and review only where it prevents mistakes. Blank skips generated-asset steps.
Desktop uses a large setup surface; compact uses a full-height wizard with a
stable app bar and keyboard-safe action. Existing draft, cleanup, retry, and
lived-location contracts remain unchanged. Raw schema controls in person
authoring move behind an explicit Advanced disclosure without normalizing or
discarding unknown data.

## Visual system Revision

The approved default scale becomes 12/16 micro, 13/18 metadata, 14/20 control,
15/22 body, 17/24 section, 24/31 page, and 17/1.7 prose. Routine navigation and
tool labels never use micro text. Mobile inputs remain 16 px.

Controls target 40 px on ordinary desktop and 44 px on touch. The radius family
becomes 6 px small, 9 px medium, 14 px large, and semantic round. Large radii
are reserved for cards, drawers, and dialogs; ordinary controls are not pills.

Canvas, surface, raised surface, selected surface, and scrim must be perceptibly
distinct. Spacing and tone perform primary grouping; borders serve fields,
selection, and structural boundaries. Decorative grids and ambient cyan glow
are removed. Cyan signals primary action/selection/focus; amber signals warning
or judgment. All curated themes preserve those relationships.

Motion lasts roughly 120-220 ms and explains drawer, disclosure, or selection
continuity. Reduced motion, effects Off, high contrast, solid surfaces, large
UI, roomy targets, RTL, 200 percent zoom, and long labels remain functional.

## Data, error, and security boundaries

- No new server endpoint is required unless current projections prove
  insufficient during implementation; omitted metadata stays omitted.
- No client patch becomes authority for story, Library, or Settings data.
- server writes retain existing request identity, validation, refresh, and
  confirmation boundaries.
- credentials never enter general state, local storage, routes, diagnostics, or
  screenshots.
- raw diagnostics remain inside Advanced disclosures.
- all overlays are modal only while overlayed; pinned context never marks main
  inert.
- extensions retain current registered destinations/results and contained CSS.

## Verification

Each implementation phase begins with a focused failing behavior test, verifies
that failure, implements the smallest coherent change, reruns focused tests,
and captures the affected surfaces. Existing tests that pin superseded visual
decisions are replaced with behavior assertions; persistence, accessibility,
security, and capability tests are not weakened.

Final verification includes:

- 360x800, 390x844, 430x932, 768x1024, 1024x768, 1280x800,
  1440x900, 1920x1080, and 844x390;
- empty, populated, loading, generation, error, long-content, open/closed,
  overlay/pinned, search/filter, list/detail, deep-link, and draft states;
- keyboard focus, focus return, Back/Forward, Escape, touch targets, no
  horizontal overflow, single scroll owners, RTL/long-label stress, reduced
  motion, high contrast, and large UI;
- focused browser tests, complete browser suite, release/fingerprint checks,
  structure/map generation, and the full pinned-venv repository gate;
- final screenshots and desktop/tablet/mobile contact sheets under
  `docs/design/sonder-ui-replacement/redesign/after/`.

No claim of complete, responsive, or accessible is made without the matching
automated and visual evidence.
