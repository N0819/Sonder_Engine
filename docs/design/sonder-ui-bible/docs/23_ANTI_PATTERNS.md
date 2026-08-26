# 23. Anti-Patterns

## Generic glass dashboard

**Symptoms:** dark cards, blur, cyan accents, and modern fonts are present, but
the result is still a conventional dashboard.

**Correction:** restore the living canvas, integrated top shelf, unboxed prose,
fixed reading measure, modular docks, and shared material hierarchy. Ingredients
without composition do not constitute the style.

## Opaque sidebars

**Symptoms:** top shelf is frosted while sidebars become solid black columns.

**Correction:** toolbar bodies follow Glass Density; bars follow Bar Opacity;
both use Frost Level and canvas-derived ambient light.

## Detached primary buttons

**Symptoms:** Scene, Library, and Settings appear as three bordered buttons
floating inside or beside the top bar.

**Correction:** merge them into one connected shelf object with centered labels,
shared hairlines, and outer corners only.

## Numbered chrome

**Symptoms:** `01`, `02`, `03`, figure numbers, or machine codes decorate
destinations and module headers.

**Correction:** remove them. Use labels and spatial hierarchy. Numbers remain
only when the content itself is ordered or measured.

## Oversized type

**Symptoms:** destination headings reach 20-36 px, module text grows to body-copy
scale, or story prose looks low-resolution.

**Correction:** use the canonical 8-13 px UI hierarchy and 15 px prose default.
Reserve 18-22 px for exceptional setup/empty states.

## Sci-fi font saturation

**Symptoms:** every title and label is mono, uppercase, tracked, or rendered in
a display-tech font.

**Correction:** Geist Sans owns ordinary UI, Geist Mono owns small technical
values, and Newsreader owns fiction.

## CRT material simulation

**Symptoms:** scanlines, RGB pixels, grain, sparkling additive noise, dithering,
or animated screen texture overlays.

**Correction:** remove the layer. Use clean translucent material, fine bevels,
ambient light, and state accents.

## Chamfer confusion

**Symptoms:** 45-degree cut corners are added because the design calls for a
bevel.

**Correction:** use 4 px rounded corners with tonal top/bottom edges. No
chamfers.

## Redundant title switcher

**Symptoms:** clicking the current story title opens a story picker while
Library already owns the archive.

**Correction:** keep story identity informational and switching in Library.

## Permanent system exposure

**Symptoms:** all engine systems are visible in Scene, or Story Tools becomes a
fixed inspector regardless of use.

**Correction:** expose eligible systems through modules, Library, Settings, and
Widget Shelf. The default shows only what earns permanent space.

## Duplicate module state

**Symptoms:** Settings keeps one Custom Theme editor while a docked copy has its
own draft or controls.

**Correction:** one live instance. The source locates the existing module.

## Separate drag handles

**Symptoms:** a tiny glyph or handle must be grabbed while the title/tab looks
draggable, or dragging selects page text.

**Correction:** make the title/tab the drag surface, apply hover/cursor feedback,
and suppress selection only during an active drag.

## Ambiguous docking

**Symptoms:** tiny tab targets compete with above/below targets; the target
switches unexpectedly; no exact preview is shown.

**Correction:** reserve the full title strip for tabbing, use broad visible rails
for shelves, preview order live, and apply stable target ownership.

## Lagging float target

**Symptoms:** a second ghost trails the actual window or is labeled `Float
target`.

**Correction:** use the dragged module as the floating preview. The canvas itself
is the destination.

## Silent removal

**Symptoms:** dropping in arbitrary empty space removes a module or loses it.

**Correction:** invalid release restores origin. Only Widget Shelf target/menu
stores a module.

## Capacity lies

**Symptoms:** a full dock shows a shelf target, or tab count is mistaken for
shelf count.

**Correction:** compute capacity from usable height and count shelf groups only.

## Breathing story measure

**Symptoms:** composer and prose stretch when toolbars close and rewrap when
they open.

**Correction:** anchor them to a fixed reading token independent of dock tracks.

## Bottom-navigation fork

**Symptoms:** mobile replaces the integrated top shelf with a different bottom
navigation architecture.

**Correction:** preserve the top-shelf workspaces and stage toolbars/modules as
overlays or sheets.

## Decorative canvas chrome

**Symptoms:** crosshair glyphs, vertical lines, rulers, `Scene / Live`, or
unrelated diagnostic labels float over the story.

**Correction:** remove them unless they communicate a real current state. The
canonical low-contrast Story identity and scene/location figure label are
allowed instrument metadata; arbitrary numbers and decorative geometry are not.
