# 10. Color, Surfaces, and Themes

## Semantic color model

Color is assigned by meaning, not by component.

- **Cyan**: selection, focus, primary immediate action, active navigation, links, current context.
- **Amber**: warning, attention, pending operational state, important callout.
- **Green**: success, connected, complete, healthy.
- **Red**: error, destructive action, blocked state.
- **Neutral**: ordinary surfaces, secondary actions, inactive state, structure.

Status must not rely on color alone. Use text, icon, marker, or shape as a second channel.

## Accent budget

A typical screen should use cyan on:

- the active primary destination;
- the focused or selected local item;
- one primary action;
- links or interactive detail as needed.

Avoid multiple large cyan fills. Most buttons should remain neutral until hover, selection, or active state.

Amber should be rarer than cyan. It is not a secondary decorative accent; it signals attention or operational context.

## Carbon Signal reference palette

The following values are the reference starting point for the default theme:

| Token | Reference value | Purpose |
|---|---|---|
| `ground-0` | `#080B0D` | deepest application ground |
| `ground-1` | `#0C1114` | main content ground |
| `surface-1` | `#11181C` | persistent chrome |
| `surface-2` | `#172126` | raised surfaces |
| `surface-3` | `#1D292F` | hover/selected neutral layer |
| `text-1` | `#E6ECEF` | primary text |
| `text-2` | `#A7B2B7` | secondary text |
| `text-3` | `#77858C` | subdued metadata |
| `border-1` | `#263238` | standard hairline |
| `border-2` | `#35454D` | strong/focus-adjacent border |
| `accent-cyan` | `#54CFE2` | selection and primary action |
| `accent-cyan-soft` | `rgba(84,207,226,.14)` | selected tint |
| `accent-amber` | `#D5A64A` | warning and callout |
| `success` | `#69B98F` | success/connected |
| `error` | `#D56B75` | error/destructive |

Values may be tuned through documented visual calibration, but the semantic relationships must remain intact.

## Surface behavior

### Ground

The ground may include a subtle radial tonal shift or story backdrop. It must remain quiet enough that content and chrome are stable.

### Persistent chrome

Navigation, composer, settings shells, and primary inspectors use neutral surfaces with high enough opacity to resist scene tint.

### Raised surfaces

Cards, list selection, menus, and local panels use a small tonal step plus a hairline border. Do not use a large shadow as their primary distinction.

### Overlay surfaces

Dialogs and sheets use stronger separation and a scrim. High-risk or text-heavy overlays should be more opaque than contextual glass.

## Controlled transparency

Recommended opacity ranges:

- persistent chrome over backdrop: 0.90-0.97;
- inspector/context panel: 0.84-0.94;
- turn plate over imagery: 0.36-0.62 with readability treatment;
- floating compact utility: 0.82-0.92;
- solid-surfaces mode: 1.0.

Blur is optional and should remain mild, generally 2-6 px. Blur must be removed when animated weather, low-power mode, reduced effects, or browser support makes it expensive or unreliable.

## Curated themes

### Carbon Signal

Charcoal and carbon grounds, signal cyan, amber operational callouts. Default and calibration reference.

### Ash and Brass

Warm graphite, muted brass primary accent, restrained cool-blue secondary accent. It should feel material and neutral, not steampunk.

### Midnight Ink

Deep blue-black, desaturated violet, and silver-blue. It should feel quiet and nocturnal, not neon.

### Parchment Night

Dark umber and ink grounds, warm cream text, patinated teal or subdued brass accents. It should support fantasy and historical reading without literal paper texture or ornamental borders.

### Legacy

Existing themes remain available through a compatibility layer. They are clearly labeled Legacy and are not allowed to define new component geometry or state semantics.

## Theme invariants

Every curated theme must preserve:

- surface hierarchy;
- cyan-equivalent selection semantics;
- amber-equivalent warning semantics;
- readable focus;
- selected versus hover distinction;
- error/success differentiation;
- controlled glass behavior;
- the same geometry and component dimensions.

Themes may change mood and palette. They may not change interaction meaning.

## Scene backdrop rules

- Scene imagery belongs to the story stage, not the application frame.
- Navigation and settings must not shift hue with the scene.
- Text plates must maintain readability without reflowing line length when a backdrop appears.
- Weather and scene effects must sit behind interactive chrome.
- Backdrop visibility must have a solid and effects-off fallback.
