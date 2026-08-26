# 14. Scene Workspace

## Purpose

Scene is the story-first atmospheric workspace. It is where users read, write,
continue, and arrange the live instruments they need. The default composition
must feel complete with both toolbars open and with both collapsed.

## Composition

From back to front:

1. full atmospheric or gradient canvas;
2. controlled wash, vignette, and optional faint diagrammatic grid;
3. centered transcript near the lower half of the stage;
4. fixed-measure composer near the bottom;
5. left and right modular toolbars;
6. floating modules and transient docking feedback;
7. integrated top shelf.

There is no default left navigation rail, right inspector, story card, or
boxed prose region.

## Top shelf

Scene is selected in the integrated Scene/Library/Settings cluster. The current
story identity remains visible but does not open a switcher. Status shows a
concise state such as Ready, Saving, Generating, or Offline. The removed
`Scene / Live` text must not return as redundant canvas chrome.

## Transcript

- Maximum measure: 650-680 px.
- Default prose: Newsreader 15 px / 1.62.
- Story title: Newsreader 12 px / 16 px.
- Chapter/source detail: Geist Mono 9 px / 12 px when meaningful.
- Prose remains unboxed and receives a background wash/text shadow only as
  needed for canvas contrast.
- Toolbars opening or closing never reflow existing prose.
- Scroll position remains stable across module and workspace changes.

## Composer

The composer is centered to the reading measure rather than stretched between
toolbars. It contains the input/draft area, concise shortcut/context metadata,
and a stable Continue/Send/Stop cell. Dock collapse never expands it.

The draft remains present after recoverable failure, workspace navigation, or
module rearrangement. Generation status does not replace the story with raw
pipeline telemetry.

## Default Workbench arrangement

Left toolbar:

1. Characters
2. Custom Theme

Right toolbar:

1. Scene Effects
2. Personas / AI Connections tab group

This arrangement is a useful default, not a restriction. User changes persist
per workspace/profile as appropriate.

## Focus composition

Focus collapses both toolbars with a smooth 260 ms transition. The canvas,
prose, composer, story identity, status, and low-opacity `Open Toolbar LFT` /
`Open Toolbar RGT` edge controls remain. The controls highlight on hover,
focus, and activation without becoming visually loud at rest.

## Toolbar interaction

- Resize a toolbar from its inner edge between 200 and 420 px.
- Resize adjacent shelves with their separator.
- Drag a title/tab onto another title/tab strip to merge.
- Drag a tab left/right to reorder it naturally.
- Drag to a visible shelf rail to create a shelf.
- Drag over a collapsed edge to reveal that toolbar.
- Drag onto the Scene canvas to float.
- Use the explicit return target or action menu to store in Widget Shelf.
- Invalid release restores origin.

## Drop clarity

Tab and shelf targets must occupy generous, noncompeting regions. The title/tab
strip always wins tab intent. Shelf rails exist only in real gaps/capacity.
The preview remains attached to the pointer, and neighboring tabs/shelves move
to show the resulting arrangement before release.

## Character portraits

The Characters module ships at Standard portraits. Borderless minus/plus
controls step through Compact names, Standard, Medium, Large, and Portrait
view. Compact names removes portraits, locations, and state rather than leaving
empty columns.

## Empty Scene

When no story is active, keep the same atmospheric shell and offer concise
actions to create a story or open Library. Do not populate empty toolbars with
developer controls, and do not create a marketing-style hero.
