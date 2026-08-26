# Sonder Panels, Widgets, and Widget Catalog

**Status:** Active design draft

**Date:** 2026-08-25

**Applies to:** Sonder Engine player- and host-facing web interface

## Purpose

This package defines a proposed revision of Sonder's Atmospheric Digital
Workbench. It replaces fixed top-level Scene, Library, and Settings
destinations with user-editable **Panels**, makes every eligible front-facing
surface a **Widget**, and replaces the recovery-only Widget Shelf with a
searchable, visual **Widget Catalog**.

The revision keeps the workbench's visual character: the living atmospheric
canvas, compact digital material, fixed reading measure, restrained typography,
direct manipulation, and responsive staging. It changes how users compose and
navigate the interface.

## Product thesis

> A Panel is a global saved arrangement of Widgets. The arrangement stays the
> same across stories; active-story Widgets refresh their content when the
> loaded story changes.

Sonder no longer treats Scene, Library, or Settings as privileged application
destinations. They become shipped default Panels containing useful default
Widget arrangements. Users may edit them, duplicate them, rename them, create
new Panels, and restore a shipped Panel's default arrangement.

## Locked direction recorded by this package

- Panels are global across stories.
- Story-aware Widgets strictly follow the active story; Widgets cannot pin
  themselves to another story.
- Panel layout is saved independently of story content.
- Every eligible story, Library, system, Settings, and extension surface is
  represented through the same Widget model.
- Scene, Library, and Settings ship as editable default Panels rather than
  hard-coded top-level routes.
- The top shelf becomes a series of user-created and editable Panel tabs.
- The Widget Catalog has one registry and two presentations:
  - a compact right-side overlay drawer;
  - a near-full-screen browser over a blurred background.
- Both catalog presentations support Visual and Compact result modes.
- The persistent **Widgets** launcher sits on the right side of the top shelf,
  immediately before global status.
- Contextual add, replace, and add-tab controls open the same catalog with
  compatibility filters applied.
- Dragging is never the only placement path.

## Package map

- [01 Panels](01_PANELS.md) — Panel identity, lifecycle, defaults, and active-story behavior.
- [02 Widget Model](02_WIDGET_MODEL.md) — Widget definitions, instances, context classes, and ownership.
- [03 Widget Catalog](03_WIDGET_CATALOG.md) — launcher, drawer, expanded browser, filters, search, and discovery.
- [04 Layout and Placement](04_LAYOUT_AND_PLACEMENT.md) — layout templates, slots, docking, automatic placement, and undo.
- [05 State, Persistence, and Migration](05_STATE_PERSISTENCE_AND_MIGRATION.md) — saved state boundaries, versioning, recovery, and story switching.
- [06 Responsive, Accessibility, and Extensions](06_RESPONSIVE_ACCESSIBILITY_AND_EXTENSIONS.md) — equivalent control across input modes and extension lifecycle.
- [07 Widget Inventory](07_WIDGET_INVENTORY.md) — initial complete catalog inventory derived from current Main systems and Interface Settings.
- [08 Decision Register](08_DECISION_REGISTER.md) — accepted outcomes, affected Design Bible decisions, and deliberately open choices.
- [09 Adoption and Change Control](09_ADOPTION_AND_CHANGE_CONTROL.md) — authority impact and the documentation/artifact changes required for adoption.
- [10 Widget Design Workbook](10_WIDGET_DESIGN_WORKBOOK.md) — complete first-pass, source-backed visual and interaction specifications for every fixed Widget, eligible Settings subwidget, and supported extension shape.

## Authority relationship

The current [Sonder UI Design Bible](../sonder-ui-bible/README.md) remains the
authoritative interface direction until this revision is adopted through its
change-control process. This package is intentionally separate because it
changes locked decisions about primary navigation, fixed workspaces, module
multiplicity, and the Widget Shelf.

Current engine behavior, persistence, security, information-firewall,
authentication, extension, and server ownership remain authoritative. Panels
and Widgets project those systems; they do not create parallel application
truth.

## Non-goals

This package does not:

- change story, character, persona, lore, Settings, or extension server
  ownership;
- allow a Widget to bind to a story other than the active story;
- make the Widget Catalog a second Library or content-search interface;
- require every Widget to support every size or layout zone;
- authorize hidden duplicate controls or duplicate unsynchronized state;
- select a final persistence backend or cross-device synchronization policy;
- define the final visual thumbnails for every Widget.
