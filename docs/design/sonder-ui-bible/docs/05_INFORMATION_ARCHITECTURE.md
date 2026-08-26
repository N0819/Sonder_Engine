# 05. Information Architecture

## Primary workspaces

Sonder has exactly three primary workspaces:

1. **Scene**
2. **Library**
3. **Settings**

Their labels are centered inside one integrated top-shelf control. They do not
carry `01`, `02`, `03`, icons, or detached button frames.

## Top shelf

The shelf is one 40 px material band containing:

- Sonder identity at the leading edge;
- the integrated Scene/Library/Settings cells;
- static current-story identity;
- concise global status at the trailing edge.

The story identity is not interactive story navigation. Story switching,
archive browsing, creation, and restore live in Library.

## Scene

Scene contains:

- the atmospheric canvas;
- story context and unboxed transcript;
- the fixed-measure composer and Continue/Send state;
- left and right modular toolbars;
- floating modules;
- toolbar reveal controls and Widget Shelf triggers.

Scene has two default compositions:

- **Workbench**: both toolbars open with the calibrated modules.
- **Focus**: both toolbars collapsed while the top shelf, story, composer, and
  discreet reveal controls remain.

## Library

Library is the full archive and authoring workspace for Stories, Characters,
Personas, Lore, associations, import/export, and lifecycle actions. It is the
only place that changes the active story.

Eligible Library sections expose a drag/move affordance that can place their
live module into a toolbar, tab group, or floating layer. The underlying record
continues to belong to Library.

## Settings

Settings is the full configuration workspace. Presentation is a normal
Settings category, not a fourth top-shelf destination. Custom Theme, Scene
Effects, AI Connections, and other eligible sections may be moved into the
workbench as live modules.

## Toolbars, shelves, and tabs

- The left and right toolbar are peer modular docks.
- Each dock contains vertically stacked shelves.
- Each shelf contains one module or a tab group.
- Tabs are naturally reorderable left/right.
- Dragging a tab to another title/tab strip joins that group.
- Dropping on a visible rail creates a shelf.
- Shelf boundaries and toolbar widths are adjustable.
- Collapsing a toolbar preserves its arrangement.

## Widget Shelf

The Widget Shelf is the inventory and recovery surface for modules. It shows
whether a module is Left, Right, Floating, or Stored. Dropping a module outside
all valid targets returns it to origin; removal occurs only through the
explicit Widget Shelf target or menu command.

## Ownership rule

No module may have two simultaneous live copies. Source workspaces locate or
activate the existing instance when a module is docked. Removing a module from
a toolbar returns it to the Widget Shelf; it does not delete data or capability.

## Secondary navigation

Use tabs for peer modules within one shelf, compact ledgers for categories, and
focused full-workspace views for substantial authoring. Do not reintroduce a
persistent left navigation rail, default right inspector, or parallel mobile
destination bar.
