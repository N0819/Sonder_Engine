# 13. Component Contracts

## Top shelf

- Height: 40 px.
- Material: Bar Opacity plus Frost Level.
- Layout: brand, integrated workspace cells, flexible story identity, status.
- Workspace labels: Scene, Library, Settings; centered; no indices.
- Story identity: read-only context.
- Status: concise text plus a non-color-only marker.

## Modular toolbar

- Left and right docks are peers.
- Default width: `min(286px, 18vw)`; adjustable 200-420 px.
- Body material follows Glass Density and Frost Level.
- Bar material follows Bar Opacity.
- Collapse animates opacity, translation, and workspace columns over 260 ms.
- Arrangement and width persist without changing module ownership.

## Shelf

- A shelf contains one module or one tab group.
- Shelf count is constrained by usable height, not tab count.
- Horizontal separator exposes a one-pixel cue inside a larger pointer/keyboard
  hit region.
- Adjacent shelf proportions are resizable and retained.
- A full dock does not show a new-shelf rail.

## Module and tab

- Bar height: 30 px.
- Title uses Geist Sans 11/14; tabs use 10/14.
- Bar/title is the drag surface; text selection is suppressed only during drag.
- Hover subtly raises opacity and edge light.
- Active tab uses Selected Strength plus a one-pixel lower edge.
- Tabs reorder by midpoint with immediate animated preview.
- Action menu exposes all placement commands.

## Drag preview

- The dragged module or compact tab proxy follows the pointer directly.
- There is no separately titled “float target” trailing behind it.
- Tab insertion uses a vertical caret and live tab reshuffle.
- Shelf insertion uses broad horizontal rails labeled by result.
- Docking uses an exact ghost outline at the destination.
- Floating uses the dragged object itself; the canvas need not display a second
  ghost.
- Invalid release restores origin without data or layout loss.

## Floating module

- Retains the standard module bar and 4 px material frame.
- Is constrained to the Scene workspace.
- Moves by its tab/title bar and may be resized where the module supports it.
- Can join any valid tab/shelf or return to the Widget Shelf.
- Must not cover the fixed composer by default placement.

## Widget Shelf

- Inventories all eligible modules and their location: Left, Right, Floating,
  or Stored.
- Opens from discreet edge `+` triggers or Settings/Library source actions.
- Supports drag-out and direct menu placement.
- Explicit return to the shelf removes a module from the active workspace; an
  arbitrary invalid drop does not.

## Characters module

- Rows show a portrait at approximately 90% of row height, name, optional
  location, and state.
- Five scale steps range from names-only to 141 px portraits.
- The smallest step hides portrait, location, and state.
- Borderless `−` and `+` sit bottom-right and highlight on hover/focus.
- Current character uses a restrained ambient edge/tint, not a bright card.

## Custom Theme module

- Six swatches edit Canvas ink, Glass panel, Control chrome, Ambient accent,
  Interface text, and Source accent.
- Glass Density, Bar Opacity, Selected Strength, and Frost Level each span
  0-100%.
- Ambient Light uses X/Y crosshairs, diamond position handle, and two circular
  radius/intensity controls.
- The color picker follows the same material, typography, and density.
- Preview is immediate; persistence and reset follow Settings ownership.

## Composer

- Stays centered to the reading measure and anchored near the bottom of Scene.
- Minimum height: 56 px.
- Input region and action cell share one material frame.
- Send becomes Stop only when cancellable; Continue is stable in width.
- Input and draft survive recoverable generation failure.

## Buttons and fields

- Free-standing outer radius: 4 px.
- Default desktop visual height: 24-30 px; touch hit target: 44 px.
- Primary action is restrained ambient material, not a saturated block.
- Focus, hover, selected, disabled, loading, error, and success are distinct
  without changing dimensions.
- Labels remain explicit; placeholders do not replace them.

## Dialogs, menus, and notices

- Use the same digital material with enough opacity for content risk.
- Align header, body, and actions to the compact spacing scale.
- Preserve focus containment/restoration and Escape where safe.
- Persistent errors remain inline; toasts are not the sole recovery route.
- Destructive confirmation names the object and consequence.
