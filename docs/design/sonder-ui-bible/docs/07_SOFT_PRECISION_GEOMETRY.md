# 07. Soft-Precision Geometry

## Principle

> Tight, engineered corners with enough softness to avoid feeling brittle, harsh, or overly technical.

Sonder favors tight corners, not sharp edges and not soft SaaS rounding. Geometry should feel lightly machined rather than cut from glass or inflated from plastic.

## Radius scale

| Token | Value | Primary use |
|---|---:|---|
| `radius-compact` | 3 px | compact controls, icon buttons, menu rows, segmented controls, inline fields |
| `radius-default` | 4 px | buttons, inputs, list rows, cards, navigation elements, control clusters |
| `radius-panel` | 5 px | dialogs, inspectors, composer surfaces, larger panels, prominent containers |
| `radius-round` | 999 px | status dots, avatar crops, progress indicators, genuinely pill-shaped tags only |

Four pixels is the default. Three and five pixels exist to express scale, not theme variation.

## Square geometry

Zero-radius corners are permitted only when the corner is not visually free-standing:

- a panel flush to a viewport edge;
- a continuous table or ledger grid;
- an image crop;
- an internal segment inside a control cluster;
- adjacent surfaces that share one outer frame;
- structural dividers.

Ordinary interactive controls must not use completely sharp free-standing corners.

## Nested radius relationship

Nested geometry follows a descending relationship:

- outer panel: 5 px;
- nested card or list container: 4 px;
- controls inside: 3-4 px;
- internal cluster segments: 0 px except at the outer ends.

Do not place a 5 px control inside a 4 px card or a 12 px card inside a 5 px panel.

## Bevel interpretation

The desired bevel is tonal, not a literal cut corner.

Use:

- one-pixel neutral border;
- a faint top or inner highlight;
- a minimal lower-edge shadow or tonal shift;
- restrained state changes.

Avoid:

- glossy gradients;
- thick embossed frames;
- strong inset shadows;
- metallic shine;
- repeated 45-degree chamfers;
- glowing corner brackets.

Literal chamfers may be used only for rare operational callouts where the shape itself communicates exceptional state. They must never become the default panel language.

## Adjacent controls

When controls touch:

- the group owns the outer radius;
- internal controls have zero radius at shared edges;
- borders do not double in thickness;
- focus remains visible on the individual control;
- separators remain subtle.

## Focus geometry

Focus indicators must follow the control's shape. A focus ring may sit 2 px outside the control or use a 2 px inset treatment inside a cluster. It must not turn a 4 px control into a large rounded glow.

## Mobile geometry

Mobile uses the same 3-5 px language. Touch targets grow through height, padding, and spacing, not larger radii.

## Geometry violations

The following are defects:

- 8-20 px card radii in ordinary application surfaces;
- pill-shaped navigation buttons without semantic reason;
- different radii for equivalent controls;
- a rounded card containing sharp buttons or the reverse;
- rounded backgrounds behind plain section headings;
- literal chamfers repeated across every panel;
- focus rings with a different radius family;
- border thickness changing between idle and selected states and causing layout shift.
