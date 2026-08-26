# 06. Visual Grammar

## Four layers

Sonder is composed from four distinct layers:

1. **Canvas**: full atmospheric image or authored gradient.
2. **Story**: unboxed transcript and fixed reading measure.
3. **Digital material**: top shelf, module bars/bodies, composer, menus, and
   transient operation surfaces.
4. **Signal**: selection edges, status lamps, focus, progress, and drag targets.

Each layer has one job. The canvas supplies mood and environmental light; it
does not supply UI state. Signal color remains legible when the canvas changes.

## Atmospheric field

The canvas fills the viewport and remains visually continuous behind Scene.
The default canvas is a full atmospheric image with focal-position, luminance,
vignette, and reading-veil controls. Preset and custom gradients are equal
first-class options.

A faint diagrammatic grid may organize empty canvas space only when it remains
subordinate to the story. Decorative crosshairs, vertical rulers, detached
glyphs, or scene labels are not part of the default composition.

## Digital material

All operable chrome derives from one recipe:

- near-black role color;
- user-controlled alpha;
- local backdrop blur;
- one-pixel cool upper edge and dark lower edge;
- restrained internal lighting from the ambient-light field;
- 4 px rounded outer corners where the surface is free-standing.

Top-shelf cells, module bars, tab bars, toolbars, composer, color picker, menus,
and drag previews must look cut from the same material. Sidebars may not become
opaque blocks while the top shelf remains glass.

## Transparency hierarchy

- Canvas: fully visual.
- Module body: Glass Density.
- Bars and top-shelf cells: Bar Opacity.
- Selected surfaces: Bar/Glass base plus Selected Strength.
- Modal or high-risk text surface: raised toward opacity as required.
- Solid-surfaces mode: 100% opaque without changing hierarchy.

Never apply CSS `opacity` to a whole interactive subtree; mix alpha into
surface colors so text and focus remain independently legible.

## Texture policy

The canonical material has no CRT pixel mask, material grain, scanline,
sparkling noise, RGB separation, dither, or animated additive texture. Earlier
experiments with those motifs are rejected. Future texture requires a Design
Bible revision, not a local effect toggle.

## Accent discipline

Ambient cyan marks current selection and focus. Green marks ready or healthy.
Amber marks source/configuration/attention. Red marks failure or destructive
action. Large saturated fills are rare; edge, text, and low-strength tint are
preferred.

## Depth order

Create depth in this order:

1. transparency and backdrop separation;
2. one-pixel bevel edges;
3. restrained internal lighting;
4. small shadow for floating/overlay separation;
5. blur.

Do not compensate for weak hierarchy with large shadows, heavy borders, or
brighter accent.

## Composition tests

A conforming screen remains coherent when:

- the canvas is replaced with black;
- glass is made solid;
- accents are desaturated;
- blur is disabled;
- both toolbars are collapsed;
- all module bodies contain long real data.

If the result reads as a generic dashboard or loses orientation, the visual
grammar has not been implemented.
