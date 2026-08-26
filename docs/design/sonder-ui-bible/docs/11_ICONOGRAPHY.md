# 11. Iconography

## Principle

Icons are quiet functional marks. Labels carry orientation. The workbench must
not depend on a field of unexplained symbols.

## Use

- Use the original Sonder SVG family for global actions, status, menus, and
  unfamiliar commands.
- Use a fixed 16, 20, or 24 px optical box.
- Use `currentColor`; semantic state comes from the component.
- Provide an accessible name and tooltip for icon-only actions.
- Keep one outline/filled grammar within a control group.

## Visible labels

Scene, Library, Settings, Characters, Custom Theme, Scene Effects, Personas,
AI Connections, and Widget Shelf remain text labels. Do not replace them with
icons, abbreviations, or numeric codes.

## Allowed typographic controls

Borderless `+` and `−` are the canonical Characters portrait-scale controls.
They are typographic operations rather than substitute icons and must have
44 px-capable hit regions on touch plus accessible names. A conventional close
mark may be used in a compact transient surface when its accessible name is
explicit.

## Drag communication

The tab or module title itself is the drag surface. A separate decorative
window-handle glyph is not required. Hover may brighten the bar and cursor;
dragging uses `grabbing`, a live tab insertion marker, shelf rail, or snap
outline.

## Product mark

The Sonder mark may remain a small geometric lockup at the leading edge of the
top shelf. It must not generate decorative crosshair lines, rulers, or glyphs
inside the Scene canvas.

## Prohibited

- unlabeled icon registries;
- emoji as product controls;
- decorative sci-fi glyphs;
- numeric destination icons;
- mixed stroke weights in one bar;
- icons that duplicate visible labels without adding state;
- a separate drag-handle symbol when the tab/title is already draggable;
- hard-coded multicolor SVG controls.
