# 07. Soft-Precision Geometry

## Principle

> One rounded 4 px bevel, repeated everywhere a free edge is visible.

Sonder does not use chamfered corners. The word bevel describes tonal edge
construction—upper highlight, lower shadow, and a slight rounded corner—not a
cut diagonal silhouette.

## Radius contract

| Token | Value | Use |
|---|---:|---|
| `radius-none` | 0 px | internal shared edges, flush viewport edges, tracks |
| `radius-default` | 4 px | every free-standing bar, panel, field, button, menu, composer, and preview |
| `radius-round` | 999 px | circular handles, lamps, and genuinely round indicators only |

Three- and five-pixel variants from the former Bible are retired. Equivalent
surfaces use 4 px without component-by-component interpretation.

## Shared edges

When cells touch inside one object:

- the object owns the 4 px outer radius;
- internal cells use 0 px at shared edges;
- adjacent borders collapse to one hairline;
- the first and last cell inherit the appropriate outer corners;
- hover, selected, and focus states never change geometry.

This rule governs the top shelf, tab groups, composer action cells, color
swatches, segmented controls, and adjacent toolbar shelves.

## Tonal bevel

A standard material edge uses:

- 1 px top/leading highlight at low opacity;
- 1 px bottom/trailing dark edge;
- optional faint inner top highlight;
- no metallic gradient, embossed lip, or corner bracket.

## Floating geometry

A floating module retains the same 4 px frame and bar as a docked module. It
may add a compact shadow for canvas separation, but it must not become a
different card family.

## Focus geometry

Focus follows the 4 px shape with an inset or 2 px offset ring. Splitters and
bare plus/minus controls use a line/text treatment plus an adequately sized
invisible hit area.

## Prohibited geometry

- 45-degree chamfers;
- 8-20 px dashboard-card radii;
- pill navigation;
- mixed 3/4/5 px component radii;
- sharp free-standing boxes;
- rounded section-title capsules;
- borders that become thicker when selected;
- floating windows with unrelated rounded-card styling.
