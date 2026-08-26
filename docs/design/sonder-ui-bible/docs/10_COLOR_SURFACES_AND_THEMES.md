# 10. Color, Surfaces, and Themes

## Theme model

A Sonder theme is a complete workbench material definition:

- canvas;
- six editable color roles;
- Glass Density;
- Bar Opacity;
- Selected Strength;
- Frost Level;
- ambient-light position, size, and intensity;
- accessibility overrides.

The old fixed Carbon Signal/Ash and Brass/Midnight Ink/Parchment Night doctrine
is retired. Presets may be shipped, but they use this same model and do not
define different component systems.

## Deep Current default

| Role | Default | Meaning |
|---|---|---|
| Canvas ink | `#06090A` | deepest canvas/gradient ground |
| Glass panel | `#040708` | module bodies and composer |
| Control chrome | `#0B1213` | top shelf, title bars, tabs |
| Ambient accent | `#94D9D0` | selection, focus, environmental light |
| Interface text | `#EFF4F1` | UI text source color |
| Source accent | `#D2B57A` | source/configuration/attention |
| Ready | `#86EF79` | ready/healthy state |
| Error | `#DF7B70` | failure/destructive state |

Derived text alpha:

- primary: 88%;
- muted: 46%;
- faint: 27% and never essential alone.

## Material controls

Every listed slider spans 0-100%:

| Control | Default | Effect |
|---|---:|---|
| Glass Density | 20% | alpha of module bodies and composer |
| Bar Opacity | 60% | top shelf cells, module bars, tabs, handles, and related bars |
| Selected Strength | 6% | ambient tint added to selected/current surfaces |
| Frost Level | 50% | blur from 0 to 24 px; 50% = 12 px |

Bar Opacity applies consistently to Scene/Library/Settings cells, module title
bars, tab bars, splitters, toolbar reveal controls, and Widget Shelf chrome.
No family may use an unrelated fixed opacity.

## Canvas library

Full Atmospheric is the default. The canvas library also includes named
gradient presets such as Deep Current and user-authored gradients with two or
three color stops, direction/focal point, luminance, vignette, and reading
veil. A canvas can be previewed without changing story data.

## Ambient light

The ambient-light control is a screen-proportion field:

- crosshairs represent screen X/Y;
- a central diamond sets light position;
- one circular handle controls radius/size;
- one circular handle controls intensity;
- position, radius, and intensity provide keyboard-adjustable values;
- the preview updates the canvas and glass together.

Reference default: X 68%, Y 38%, radius 54%, intensity 64%.

## Color picker

The picker uses the same compact digital material. It includes a saturation/
value plane, hue strip, live swatch, eyedropper where supported, RGB fields,
hex value, and explicit accessible labels. It must not fall back to a visually
unrelated browser control when a custom picker is available; native fallback
remains acceptable for reliability.

## State semantics

- Ambient accent: current, selected, focus, active drag target.
- Ready green: connected, saved, available, complete.
- Source amber: edited, source-owned, configuration attention, pending.
- Error red: failure, blocked, destructive confirmation.

State never relies on color alone.

## Fallbacks

Solid surfaces force material alpha to 100% and may disable blur. Reduced
effects removes expensive canvas effects. Neither fallback changes geometry,
workspace ownership, or selected-state meaning.
