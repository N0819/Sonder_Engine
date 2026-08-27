# 08. Decision Register

## Accepted product decisions

| ID | Decision | Accepted outcome |
|---|---|---|
| PWC-001 | Workspace model | Top-level workspaces become user-created and editable Panels. |
| PWC-002 | Panel scope | Panels and their layouts are global across stories. |
| PWC-003 | Story context | Story-aware Widgets strictly follow the one active story. No story pinning. |
| PWC-004 | Default Panels | Scene, Library, and Settings ship as editable default layouts, not privileged destinations. |
| PWC-005 | Default recovery | A shipped Panel may be reset to its current shipped default without resetting product data or Settings. |
| PWC-006 | Widget scope | Every eligible story, Library, system, Settings, and extension surface uses the shared Widget model. |
| PWC-007 | Top shelf | The fixed destination cluster becomes an ordered Panel-tab strip with New Panel. |
| PWC-008 | Catalog model | One Widget Catalog supplies the compact drawer and expanded browser. |
| PWC-009 | Catalog launcher | Widgets sits on the top shelf's trailing side immediately before global status. |
| PWC-010 | Catalog drawer | Launcher opens a right-side overlay drawer that does not resize the Panel. |
| PWC-011 | Expanded catalog | Expanded browsing uses a near-full-screen surface over a dimmed/blurred background. |
| PWC-012 | Catalog density | Both catalog presentations offer Visual and Compact results. |
| PWC-013 | Catalog categories | Primary filters are All, Story, Library, Systems, Settings, and Extensions. |
| PWC-014 | Contextual launch | Empty-slot Add, Replace, Add tab, and toolbar Add use the same catalog with visible compatibility filters. |
| PWC-015 | Placement access | Drag is optional; Add, Choose placement, keyboard, touch, and Widget menus provide equivalent control. |
| PWC-016 | Story resource model | Characters (Story) filters reusable Characters by active-story association; Library may show all reusable resources and their associations. |
| PWC-017 | Icon source and usage | Real SVGs from the local SVG Repo Minimal UI Icons artifact are the primary icon language; favor icons where clear, retain labels where meaning or consequence requires them, and do not generate substitutes without an explicit exception. |

## Architectural consequences

| ID | Consequence | Required boundary |
|---|---|---|
| PWC-C01 | A Panel is composition, not server truth. | Layout persistence excludes story and credential content. |
| PWC-C02 | One Widget type may have multiple instances where useful. | Multiplicity is manifest-owned; every instance has independent presentation identity and explicit shared data ownership. |
| PWC-C03 | Story switching refreshes several Widgets. | One captured active-story identity and stale-result rejection protect every projection. |
| PWC-C04 | Catalog previews cover many systems. | Preview providers are lightweight, non-interactive, and side-effect free. |
| PWC-C05 | Layouts outlive releases and extensions. | Panel and Widget configuration are versioned and recover with placeholders. |
| PWC-C06 | Default Panels are editable. | Shipped origins and versioned reset definitions remain separate from user data. |
| PWC-C07 | Settings groups and panels may both be Widgets. | Composite and direct projections share one runtime/save owner. |
| PWC-C08 | Icon choices are reusable product semantics, not anonymous decoration. | One manifest-backed semantic mapping, centralized SVG sprite, accessible names, and provenance govern built-in icon use. |

## Design Bible decisions affected

This revision requires formal adoption because it changes or qualifies current
Design Bible 2.0 locked outcomes.

| Existing decision | Current outcome | Panels revision |
|---|---|---|
| DB2-02 | Exactly Scene, Library, Settings workspaces | User-created Panels; Scene, Library, Settings are defaults. |
| DB2-03 | Integrated fixed three-cell primary navigation | Ordered editable Panel tabs plus New Panel. |
| DB2-05 | Scene owns the modular story workspace | Scene becomes the shipped story-stage Panel definition. |
| DB2-06 | Center Scene plus peer side docks | One supported Panel template rather than universal desktop layout. |
| DB2-07 | One live instance per Module | One live state owner per Widget instance; repeated definitions allowed only by manifest policy. |
| DB2-08 | Library/Settings source ownership with detachable modules | Ownership remains, but any eligible surface may project as a Widget without a privileged destination. |
| DB2-09 | Widget Shelf inventories/reclaims modules | Widget Catalog discovers, places, replaces, locates, and recovers Widgets. |
| DB2-14 | Focus is both Scene toolbars collapsed | Focus becomes a state of the story-stage template rather than a global workspace doctrine. |
| DB2-27 | Mobile keeps fixed three-workspace top shelf | Mobile keeps the top shelf but stages the Panel-tab model. |

The revision preserves current outcomes for atmospheric material, stable story
measure, typography, geometry, restrained motion, genre neutrality, accessible
placement, and current runtime ownership unless a later record says otherwise.

## Open design tranches

These are deliberately open choices, not missing requirements in the accepted
foundation.

### Panel creation and templates

- exact starter-template set and names;
- template thumbnails and creation flow;
- default two-to-six-column choices by viewport;
- conversion between template families;
- freeform layout policy.

### Widget contract qualification

- final multiplicity policy for every inventory entry;
- exact minimum and preferred geometry;
- which Widgets support float, toolbar, grid, stack, or focused-only zones;
- selection-channel semantics;
- safe preview implementation per Widget.

### Persistence

- browser-local versus host-profile server ownership;
- cross-device synchronization, if any;
- layout import/export and sharing;
- conflict user experience beyond revision refusal.

### Catalog calibration

- exact drawer width and expanded-browser measurements;
- default category and sort order;
- whether Visual or last-used mode wins on first launch after migration;
- preview density and virtualization threshold;
- keyboard shortcut, if any;
- exact per-Widget icon mapping and narrow-screen filter staging within the accepted icon-source contract.

### Migration

- mapping existing fixed routes and Widget Shelf state into default Panels;
- treatment of currently docked application-singleton Modules;
- default-layout update policy after major releases;
- extension adoption timetable.

## Decision rule

A later implementation may choose a value only where this register identifies a
calibration or open tranche. It may not silently restore fixed destinations,
story-pinned Widgets, separate drawer/browser inventories, or inaccessible
drag-only placement.
