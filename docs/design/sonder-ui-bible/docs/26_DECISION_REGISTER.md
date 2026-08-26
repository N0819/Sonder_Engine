# 26. Decision Register

Design Bible 2.0 replaces the 1.x visual and composition decisions where they
differ. Changes require [29 Change Control](29_CHANGE_CONTROL.md).

| ID | Decision | Locked outcome |
|---|---|---|
| DB2-01 | Product metaphor | Atmospheric Digital Workbench. |
| DB2-02 | Primary workspaces | Scene, Library, Settings. |
| DB2-03 | Primary navigation | One integrated top-shelf cluster; no indices or icons. |
| DB2-04 | Story identity | Informational in top shelf; switching belongs to Library. |
| DB2-05 | Scene | Full canvas, unboxed prose, fixed-measure composer, modular side toolbars. |
| DB2-06 | Desktop layout | Center Scene plus peer left/right docks; no left rail/right inspector doctrine. |
| DB2-07 | Module model | One live instance; dock, tab, shelf, float, or store. |
| DB2-08 | Source ownership | Library/Settings own data; eligible sections can be placed in workbench. |
| DB2-09 | Widget recovery | Widget Shelf inventories and restores modules; invalid drop restores origin. |
| DB2-10 | Drag surface | Module title/tab itself, not a separate handle glyph. |
| DB2-11 | Tab behavior | Natural midpoint reorder with live insertion and neighbor animation. |
| DB2-12 | Shelf behavior | Broad explicit rails; height-derived capacity from two to four. |
| DB2-13 | Floating | Dragged module is preview; no lagging float ghost/label. |
| DB2-14 | Focus | Either toolbar collapses independently; both collapsed is Focus. |
| DB2-15 | Stable reading | Prose/composer measure does not change with dock state. |
| DB2-16 | Canvas | Full Atmospheric default plus preset and configurable gradients. |
| DB2-17 | Theme model | Six color roles, four material sliders, and ambient-light instrument. |
| DB2-18 | Material defaults | Glass 20%, Bars 60%, Selected 6%, Frost 50%. |
| DB2-19 | Material range | Every material slider spans 0-100%. |
| DB2-20 | Texture | No CRT grain, scanlines, dithering, animated noise, or material activity. |
| DB2-21 | Geometry | One 4 px rounded bevel for every free-standing surface; no chamfers. |
| DB2-22 | Fonts | Geist Sans + Geist Mono + Newsreader. |
| DB2-23 | Type scale | 8-13 px ordinary UI, 15 px default prose, no marketing-scale destination titles. |
| DB2-24 | Character roster | Five portrait scales from names-only to 141 px portrait view. |
| DB2-25 | Portrait controls | Borderless minus/plus at Characters bottom-right. |
| DB2-26 | Motion | Static at rest; only purposeful structural/direct-manipulation transitions. |
| DB2-27 | Mobile | Same top-shelf architecture; toolbars stage as overlays/sheets; no bottom nav fork. |
| DB2-28 | Accessibility | All drag operations have keyboard/menu equivalents and state announcements. |
| DB2-29 | Genre neutrality | Shell stays neutral; canvas/theme carries mood. |
| DB2-30 | Historical authority | Old screenshots, candidate, amendment, and current UI are evidence, not target presentation. |

## Interpretation rules

1. Reproduce the whole canonical composition before local polish.
2. Runtime truth is adapted into the workbench; obsolete presentation is not
   preserved for convenience.
3. One clear owner and one live module beat duplicate shortcuts.
4. Deliberate subtraction beats exposing every available system.
5. Accessibility changes material and scale without replacing architecture.
6. Any new texture, destination, navigation frame, or geometry family requires
   a formal revision.
