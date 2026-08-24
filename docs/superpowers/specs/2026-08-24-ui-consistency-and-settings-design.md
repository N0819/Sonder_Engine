# UI Consistency and Settings Design

**Date:** 2026-08-24  
**Status:** Proposed implementation contract  
**Branch:** `codex/ui-consistency`

## Purpose

Bring the replacement interface back into conformance with its maintained
design language while correcting the reported Settings, contextual-panel,
Library action, typography, and hard-edge defects.

The work must preserve engine-owned routes, persistence, accessibility,
localization, keyboard behavior, responsive staging, and the approved
replacement information architecture. It does not change story data, model
configuration semantics, or backend APIs.

## Coordination boundary

The concurrent Library single-workspace change owns the removal of the
persistent Library sub-sidebar, the placement of Library type and scope
controls, the canonical material ledger, and its responsive evidence. This
work must begin from that integrated `interface` commit.

Until that commit lands, this branch changes documentation only. After it
lands, rebase this branch and treat the integrated Library markup, CSS, tests,
release identifier, generated maps, and maintained guidance as authoritative.
Do not replay or overwrite the concurrent Library implementation.

The Library-specific inspector, close-track, row-action, typography, and
geometry corrections in this design are follow-on changes against the merged
single-workspace result.

## Design invariants

1. Settings has one navigation method and one selected detail surface.
2. The document and shell never scroll to reveal an internal Settings target.
3. Interface text uses the formal semantic type scale; story prose remains an
   independent preference.
4. Every visually free-standing framed surface uses the 3-5 px soft-precision
   geometry family. Four pixels is the default.
5. Zero-radius geometry is limited to internal shared edges, structural
   dividers, image crops, and surfaces flush to a viewport edge. The outer
   boundary of a free-standing ledger or control cluster still receives a
   radius.
6. Inspector width and resizing behavior belong to the inspector destination,
   not to a global presentation mode.
7. A close action removes both the contextual panel and its layout track.
8. A row More control performs row actions without also selecting or opening
   the row.
9. Accessibility retains at least 44 px touch targets and a real Large UI
   override even though the default interface becomes denser.

## 1. Single-method Settings

### Information architecture

Remove the scan-first Settings overview as a separate user-facing surface.
`#/settings` resolves to the Theme detail by default. The grouped navigation
is the sole Settings entry model:

- Connections
  - AI Connections
- Appearance
  - Theme
  - Reading & layout
  - Sound & motion
  - Accessibility
- Story & host
  - Content
  - Add-ons
  - Maintenance
  - Story imports & backups
- Advanced
  - Model assignments
  - Prompt editor
  - Turn details
  - Raw story data

Desktop shows the groups in a 240 px category rail beside one detail pane.
Tablet and mobile present the same groups as in-content disclosures above the
detail pane. Wide short-height layouts collapse inactive rail groups so the
rail itself does not become a second scroll owner.

There is no `Settings overview` row and no dashboard of current-value
summaries. Existing direct hashes, search aliases, and external destinations
remain accepted. Browser Back restores the prior route and focus without
requiring an overview waypoint.

### Real panels, not anchor simulation

Theme, Reading & layout, Sound & motion, and Accessibility render as distinct
detail panels. AI Connections and Model assignments are distinct panels.
Prompt editor and Raw story data are distinct panels. Content, Add-ons, and
Maintenance remain distinct panels. Story imports and Turn details continue
to open their authoritative Library and Story Tools destinations.

Legacy query-bearing hashes such as
`#/settings/experience?control=accessibility` remain valid, but the renderer
selects only the requested panel. It must not render the full Experience
document and then scroll to an anchor.

### Scroll and focus

`[data-settings-content]` is the only Settings vertical scroll owner. Route
changes set its `scrollTop` directly or restore a bounded saved offset. Panel
headings receive programmatic focus with `{ preventScroll: true }` when focus
movement is useful. Settings navigation must not call `scrollIntoView()`.

At every supported viewport and zoom state:

- `document.documentElement.scrollTop == 0`;
- `.ui-shell__workspace.scrollTop == 0`;
- the Settings root remains at the top of its destination track;
- the selected navigation row and detail heading are visible;
- opening Accessibility does not expose Theme, Reading, or Sound content.

## 2. Formal interface typography

### Token scale

The implementation must expose the Design Bible scale as CSS tokens:

| Role | Size | Line height |
|---|---:|---:|
| Micro | 11 px | 14 px |
| Metadata | 12 px | 16 px |
| Control | 13 px | 18 px |
| Interface body | 14 px | 20 px |
| Section heading | 16 px | 22 px |
| Page heading | 21 px | 28 px |
| Display heading | 28 px | 36 px |
| Story prose | 17 px default | 1.7 |

The default `.ui-app` interface text is 14/20. Standard controls use 13/18,
metadata uses 12/16, and navigational indices or technical micro-labels use
11/14. Page and section headings use their named tokens. Display text is
reserved for intentional onboarding or empty-state emphasis and is not the
ordinary page-heading size.

Story prose continues to use `--ui-prose-size` and the existing Small,
Standard, Large, and Extra large preference. Changing story text size must not
enlarge interface labels, inspector descriptions, buttons, or metadata.

### Migration and accessibility

Component styles consume semantic type and leading tokens rather than
one-off numeric `font-size` declarations or numeric `font` shorthands. A small
set of explicitly documented exceptions may exist for generated visual marks,
but not for ordinary readable text.

Large UI overrides the semantic interface tokens and control sizes together.
It remains visibly larger than the default. Mobile inputs retain a computed
16 px minimum where required to prevent unwanted browser zoom, without
changing the surrounding interface scale.

Library selection details use section, body, metadata, and control roles from
this same scale. They must not introduce a separate oversized inspector type
system.

## 3. Site-wide soft-precision geometry

### Geometry rule

Use the existing tokens:

- `--ui-radius-sm: 3px` for compact controls and nested items;
- `--ui-radius-md: 4px` for ordinary controls, rows, cards, empty states, and
  free-standing framed groups;
- `--ui-radius-lg: 5px` for dialogs, inspectors, composer surfaces, and larger
  panels;
- `--ui-radius-round` only for genuinely circular or pill-shaped objects.

The default bevel is tonal: a one-pixel neutral border, a restrained inner-top
highlight where the surface needs depth, and no literal clipped corner. The
work must not add glossy gradients, oversized rounding, or repeated chamfers.

### Required audit

Audit every stylesheet and rendered destination, including Play, Library,
Library authoring, Settings, Story Tools, New Story, authentication, guest and
runtime states, dialogs, menus, empty/loading/error states, and the component
lab.

Known defects include, but are not limited to:

- the Play `Choose a story to begin` empty-state frame;
- the Story Tools `Choose a story to use Story Tools` state frame;
- the Settings theme ledger and extension-consent frame;
- New Story route and asset-section outer frames;
- free-standing tool and Charter ledgers;
- any Library frame that remains square after the single-workspace change.

Rows inside a rounded ledger, joined control segments, tab-to-panel shared
edges, and structural separators remain square at their shared internal edges.
The group owns the rounded outer boundary and clips its children.

### Enforcement

Add a browser geometry audit that inspects visible, fully framed surfaces and
requires a computed 3 px, 4 px, or 5 px outer radius. Intentional structural
square geometry must carry an explicit semantic exemption rather than relying
on an undocumented selector allowlist.

Add a static contract that rejects radius values outside `0`, `3px`, `4px`,
`5px`, and the semantic round token. A new zero-radius free-standing surface
must fail review.

## 4. Destination-owned inspectors and Library row actions

### Inspector presentation

Story Tools retains three presentation modes:

- expanded: 352 px;
- compact: 232 px;
- rail: 80 px.

Those modes remain a Story Tools preference. They do not apply to Library
details or other text inspectors.

Library selection details use a text-safe contextual width of 352 px with a
320 px minimum on wide layouts. The Library inspector does not expose the
Story Tools resize control and never enters rail mode. At compact widths it is
staged as the existing sheet/detail presentation. Returning to Play restores
the last Story Tools preference.

The inspector host exposes the active inspector kind to layout CSS. Grid-track
allocation keys on both inspector kind and actual open state. Closing Library
details immediately clears the selection presentation, marks the inspector
closed, and removes the third grid track; it must not leave a blank column.

### Story More action

The story row is one visual card containing two sibling interactive controls:

- a primary selection control occupying the card body;
- a trailing bare ellipsis button inside the card boundary.

The ellipsis has no separate framed-button appearance, but retains an
accessible name, visible focus state, keyboard operation, and at least a 44 px
hit target. It opens an anchored row-action menu. It must not select the story,
open Library details, mutate the route, or trigger the primary row action.

Escape and outside click close the menu and restore focus to the ellipsis.
Menu actions use the existing authoritative story operations. Nested buttons
are forbidden; the two controls remain siblings inside the row container.

## Verification

### Test-first regressions

Write each regression before its implementation and observe the expected
failure:

1. Settings has no overview surface or overview navigation row.
2. Accessibility navigation renders only Accessibility and leaves every outer
   scroll offset at zero.
3. Every Settings row resolves to one real detail panel or authoritative
   external destination.
4. Interface text and headings compute to the formal default scale; story
   prose preferences remain independent; Large UI remains larger.
5. The known Play and Story Tools empty-state frames compute to a 4 px radius.
6. The cross-destination geometry audit reports no unapproved free-standing
   hard edge.
7. Library details cannot inherit Story Tools rail mode.
8. Closing Library details removes the inspector grid track.
9. The story ellipsis remains inside the visual row and opens its menu without
   selecting the story.

### Responsive and visual evidence

Compare real browser renders against the supplied references and current
approved compositions at:

- 1440x900 desktop;
- 1024x768 tablet;
- 1024x600 short tablet;
- 390x844 phone;
- 844x390 short landscape;
- desktop at 200 percent browser zoom or its equivalent constrained viewport.

Capture Settings Theme and Accessibility, Play empty state, Play with Story
Tools empty state, populated Library with details open and closed, Library row
menu, New Story, and representative authoring/dialog states. Verify keyboard,
touch targets, no horizontal overflow, one intended vertical owner, focus
return, localization, and console output.

### Repository gates

Run the narrow static and browser regressions first, then all affected browser
files, generated code-map and structure checks when required, the complete
browser suite, and the full repository test suite. Reconcile the immutable
release identifier once after all behavioral changes are stable.

## Delivery sequence

1. Wait for the Library single-workspace commit to pass its gates and land on
   `interface`.
2. Rebase this branch onto that exact commit and re-read the merged Library
   markup, CSS, tests, and maintained guidance.
3. Implement single-method Settings and its scroll/focus regressions.
4. Implement semantic typography tokens and migrate readable UI text.
5. Implement the site-wide geometry audit and repair every discovered framed
   surface.
6. Implement destination-owned inspector geometry, close-track behavior, and
   the merged story-row action menu.
7. Reconcile docs, localization, generated maps, immutable release graph,
   responsive evidence, and complete verification.

## Out of scope

- Reintroducing the old Library sub-sidebar or old interface.
- Changing Library scope/type semantics delivered by the concurrent task.
- Backend API, database, story-runtime, model-routing, or persistence changes.
- Literal polygon chamfers as the default panel language.
- Blanket `border-radius: 4px !important` styling.
- Enlarging story prose or interface controls to compensate for layout defects.
