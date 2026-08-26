# 22. UX Flows and Expert Acceleration

## Doctrine

The default arrangement teaches the workbench by example. Experienced users
gain speed by rearranging modules, collapsing toolbars, using direct commands,
and preserving state—not by enabling a separate expert interface.

## Open a story

1. Open Library.
2. Select a Story in the archive.
3. Choose Open in Scene.
4. Scene restores its canvas, transcript, composer, and saved module layout.

The story title in the top shelf never starts a competing picker.

## Enter Focus

1. Collapse left or right toolbar independently, or choose Focus for both.
2. Toolbars animate out without changing prose/composer width.
3. Edge labels remain faint but discoverable.
4. Reopen restores exact shelves, tabs, widths, and active tabs.

## Merge modules as tabs

1. Drag a module title or tab.
2. Move over the destination title/tab strip.
3. The entire strip becomes the tab target and shows an insertion caret.
4. Existing tabs shift to preview order.
5. Release commits; Escape or invalid release restores origin.

The same result is available through `Merge as tab`.

## Create or reorder shelves

1. Begin module drag.
2. Available shelf rails appear only where capacity exists.
3. Hovering a rail shows the exact new shelf outline and rearranges neighbors.
4. Release commits and the nearest splitter becomes adjustable.

At full capacity, the UI offers tab targets instead of impossible rails.

## Separate a tab

Drag the tab to a valid shelf rail or choose `Separate into shelf`. If capacity
is full, explain why and keep the tab in place. No tab becomes trapped inside a
group.

## Float and store

- Release over Scene to float the dragged module itself.
- Use the explicit return target/menu to store it in Widget Shelf.
- Invalid blank-space release is not deletion.
- Widget Shelf locates any existing instance and allows direct placement.

## Customize presentation

1. Open Settings > Presentation or locate Custom Theme.
2. Adjust canvas, role colors, glass, bars, selection, frost, and ambient light.
3. Preview updates live.
4. Save a valid theme or reset.
5. Dock Custom Theme for frequent tuning without moving Presentation out of
   Settings.

## Character scale

Use borderless minus/plus at the Characters module's lower-right. Each action
moves one deterministic step and announces the resulting mode. The minimum is
names only; the maximum is portrait view.

## Keyboard acceleration

- `Ctrl/Cmd+Enter`: Send when available.
- `Escape`: cancel drag/close transient layer/return one staged level.
- Arrow keys: navigate/reorder tabs and resize focused separators.
- Module menu: complete placement control without pointer drag.
- Search shortcuts remain contextual to Library or Settings.

## Persistence

Persist toolbar open state, widths, shelf proportions, module location, tab
order, active tabs, character portrait scale, valid theme, and relevant
workspace context. Persistence must be versioned and recover safely when a
module is removed or a viewport cannot express the prior arrangement.
