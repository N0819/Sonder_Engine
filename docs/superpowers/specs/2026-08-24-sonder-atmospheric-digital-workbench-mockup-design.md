# Sonder Atmospheric Digital Workbench Mockup

**Date:** 2026-08-24

**Status:** Approved for visual calibration

**Scope:** Exploratory standalone UI mockup only

**Authority:** This document is not part of the maintained Sonder Design Bible
and does not authorize production integration, route changes, persistence, or
backend work.

**Preserved artifact:** The evolved interactive calibration and its focused
browser regression harness are committed under
[`docs/experiments/sonder-atmospheric-workbench/`](../../experiments/sonder-atmospheric-workbench/README.md).
The artifact now explores floating modules, height-derived shelf capacity, and
deterministic tab and shelf drag interactions beyond this brief's original
static scope. That expansion remains exploratory and does not change this
document's production-authority boundary.

## Purpose

Create a visual calibration artifact for a new Sonder interface direction
without inheriting the current Design Bible's composition or visual grammar.
The artifact will test whether a modular creative workbench can combine:

- Prime Intellect's compact editorial navigation and atmospheric restraint;
- selective PS2-era raster-display character;
- a living full-screen atmospheric canvas;
- high-density, high-resolution typography; and
- a controlled Photoshop/VS Code-style docking model.

The calibration must establish a coherent visual object before any full
interactive docking prototype is attempted.

## Design thesis

> Sonder is a quiet fiction instrument made from black digital material,
> suspended over a living atmosphere.

The atmosphere is the dominant visual field. Story content is the dominant
human content. Chrome appears only where the user can operate the system.
Texture, color, and motion describe the behavior of that chrome rather than
decorating the entire screen.

## Scope boundaries

The calibration artifact will:

- be standalone and use seeded fictional content;
- contain no Sonder API calls or backend integration;
- contain no production route, storage, extension, or persistence behavior;
- demonstrate Focus and Workbench compositions at a 1600 x 900 target frame;
- provide bounded visual controls for comparing material intensity and activity;
- use static panel arrangements rather than a complete drag-and-drop engine.

The calibration artifact will not:

- modify the production UI;
- claim responsive, accessibility, localization, or feature-parity completion;
- implement floating windows, nested horizontal splits, or operating-system
  windows;
- reproduce Prime Intellect or ChungusHub markup, source, assets, or branding;
- establish a replacement production Design Bible.

## Workbench composition

The workbench shell remains stable while its central workspace changes. A
single compact top shelf contains three primary workspaces:

`SONDER / SCENE 01 / LIBRARY 02 / SETTINGS 03 / STORY IDENTITY / STATUS`

Scene is the default central workspace. Library and Settings may later use the
center for substantial work, while docked modules remain at the left and right
edges. For calibration, Scene stays active so the visual relationship between
story, atmosphere, and modules can be judged.

The story title is static identity, not a hidden switcher. Stories belong to
Library. The calibration does not add a second story-selection control.

## Module ownership

Ownership describes meaning, not placement:

- **Scene:** active-story and live-presentation modules, including Cast,
  Conditions, Frames, Scene Canvas, Backdrops, Ambience, and Scene Effects.
- **Library:** reusable or lifecycle material, including Stories, Characters,
  Personas, and Lore.
- **Settings:** application-wide configuration, including Custom Theme,
  accessibility, AI Connections, providers, and content defaults.

Modules from different owners may share a user-created tab group. A compact
source marker such as `SCN`, `LIB`, or `SET` identifies ownership without
dictating location.

## Controlled docking model

The eventual workbench has one left dock and one right dock. Each dock contains
vertical shelves; each shelf may contain a tab group.

- Dropping on a shelf tab bar joins that tab group.
- Dropping above or below a shelf creates a vertical division.
- A handle adjusts the boundary between adjacent shelves.
- A dock may collapse to its edge without losing arrangement.
- One module has one live location. Its source workspace points to the docked
  instance rather than creating a duplicate editor.
- Every drag operation will eventually have an equivalent Move/Split/Join/
  Return/Close menu action.

The first full interaction prototype will permit two edge docks, vertical
shelves, tabs, resizing, collapsing, moving, and closing. It will not permit
floating windows or nested horizontal subdivisions.

## Calibration states

### Focus

- Scene occupies the center over the atmospheric canvas.
- Both edge docks are collapsed.
- The top shelf, story identity, transcript, and composer are visible.
- The frame must feel intentional and complete without relying on panels to
  create visual interest.

### Workbench

- The same Scene, canvas, transcript, and composer remain in place.
- The left dock contains a Characters shelf above a Custom Theme shelf.
- The right dock contains a Scene Effects shelf above a tabbed
  Personas / AI Connections shelf.
- Shelf proportions are adjustable in appearance, but fixed in the calibration.
- The composition must preserve a readable center and remain one coherent
  object despite mixed module ownership.

## Visual laws

1. The atmosphere owns the field.
2. Prose is content and receives no glass container.
3. Glass appears only on operable tool surfaces.
4. Raster texture exists within digital material, never as a page-wide overlay.
5. Motion communicates activity; idle material is static.
6. Functional color communicates state; canvas color communicates mood.
7. Hierarchy relies on spacing, opacity, and contrast before type size.
8. Only one region receives strong active emphasis at a time.
9. Every shelf, tab, composer surface, and top-shelf cell derives from one
   material family.
10. Decorative detail is removed whenever the composition improves without it.

## Typography

Chrome uses a compact technical mono or mono-grotesk voice. Story prose uses a
restrained literary serif so the fiction remains human and distinct from the
instrument around it.

Calibration scale:

- micro labels and coordinates: 9-10 px;
- metadata and indices: 10-11 px;
- controls and navigation: 11-12 px;
- module titles: 12-14 px;
- story identity: 14-16 px;
- story prose: 16-18 px.

Uppercase is limited to short machine labels. Explanations use sentence case.
Bold weight is rare. No marketing-scale display heading is permitted.

### Measured Prime Intellect reference profile

The live Prime Intellect hero was inspected at a 1586 x 901 CSS-pixel viewport
on 2026-08-24. These measurements are reference proportions, not copied source:

- navigation cells use `ABC Favorit Mono` at 12 px / 16 px, weight 400,
  uppercase, with no added letter spacing;
- each primary navigation cell is 124 x 30 px with 8 px horizontal padding and
  a 4 px gap to its neighbor;
- primary navigation glass uses 25-percent white, 88-percent white text,
  12 px backdrop blur, and square corners;
- the announcement strip is 36 px high with 14-percent black glass, 12 px
  backdrop blur, a 4.5-percent white lower border, and 13.12 px mono text;
- the hero eyebrow uses `ABC Favorit Mono` at 14 px / 14 px and 30-percent
  white;
- the hero title uses variable `Geist` at 36 px / 39.6 px, weight 400, and
  90-percent white;
- the title carries a restrained green-white wash over 9 seconds at 28-percent
  opacity plus a 44 px green text shadow at low opacity;
- hero body copy uses `Geist` at 18 px / 27 px, weight 400, 45-percent white,
  and a 480 px maximum measure;
- primary actions use `ABC Favorit Mono` at 12 px / 12 px in a 28 px square-
  cornered white control;
- secondary actions use the same mono at weight 500 over 10-percent white
  glass, a 16-percent white border, 12 px blur, and 10 px horizontal padding;
- the hero media field is 640 px high and edge-blends into a `#0e0e0e` surface
  over the outer 8 percent horizontally and final 18 percent vertically.

The site also registers variable `Geist Mono`, `ABC Favorit Mono` weights 400,
500, and 700, and `OCR X`; the observed hero primarily uses `Geist` plus
`ABC Favorit Mono`.

`ABC Favorit Mono` is a licensed commercial typeface and the inspected site
loads trial binaries. The mockup must not copy, embed, redistribute, or hotlink
those binaries. It will preserve the measured typography and geometry using a
licensed open mono substitute, with `Geist` retained where legally available.

## Geometry and spacing

- The top shelf is 38-42 px high.
- Module headers are approximately 28-32 px high.
- Corners are square or optically softened by no more than 2 px.
- Divisions use one-pixel hairlines and subtle light/dark bevel relationships.
- Controls align to a small repeated spacing rhythm rather than isolated custom
  padding.
- The transcript remains centered and readable while the docks occupy the
  margins.
- Pills, rounded dashboard cards, and detached floating-card shadows are absent.

## Digital material

All operable chrome derives from one layered recipe:

1. neutral black glass at approximately 70-85 percent opacity;
2. local backdrop blur;
3. a cool one-pixel upper edge and darker lower bevel;
4. a restrained internal lighting gradient;
5. a low-opacity raster or RGB-subpixel field in unoccupied material areas; and
6. localized environmental color blooming beneath the material.

The raster field never crosses prose or reduces label clarity. It becomes most
visible in active tab fills, empty header areas, docking targets, and activity
states. The material must remain convincing when raster, canvas, and motion are
individually disabled.

## Color and canvas

Chrome remains predominantly neutral graphite. Bright color occupies only a
small fraction of the frame.

- cool cyan marks the current Scene or selected workspace;
- phosphor green marks ready, saved, or available state;
- muted amber marks caution, configuration, or pending attention;
- desaturated red is reserved for destructive actions and genuine failure;
- violet and blue-green may appear as environmental light but not as additional
  status systems.

The canvas acts as the workbench's light source. Calibration includes:

- one full atmospheric image treatment with controlled focal position,
  luminance, vignette, and transcript veil; and
- one authored gradient treatment with two or three stops, grain, vignette, and
  restrained environmental bloom.

The canvas may tint glass edges but cannot redefine functional colors.

## Motion and signature behavior

Idle presentation is static. Activity may produce slow illumination movement
behind or within the digital material. The calibration will demonstrate three
signature behaviors:

1. raster illumination inside the active top-shelf cell;
2. a diagrammatic docking-target treatment; and
3. a slow light wake through the active surface during generation.

The calibration includes an activity toggle so the idle and active material can
be compared directly. It excludes persistent scanlines, glitching, text
flicker, animated noise, and ornamental looping motion.

## Calibration variants

The same geometry and content will be shown with three bounded material
intensities:

- **Editorial:** raster and environmental bloom are barely visible;
- **Instrument:** the recommended target, with selective visible digital
  material and restrained activity light;
- **Phosphor:** a deliberately stronger comparison that tests the boundary
  before the style becomes themed or tiring.

Only material intensity changes between variants. Layout, content, spacing, and
typography remain fixed so the comparison measures style rather than preference
for a different composition.

## Review gates

The calibration is not accepted because it contains the requested ingredients.
It must pass these visual reviews:

- **Composition pass:** flat grayscale geometry already feels deliberate.
- **Squint pass:** attention resolves to Scene, prose, and one active module.
- **Grayscale pass:** hierarchy survives without accents.
- **Texture-off pass:** the frame remains a strong modern interface.
- **Background-off pass:** chrome still reads as one designed object on black.
- **Motion-off pass:** state remains understandable while static.
- **Crop pass:** adjacent fragments appear to belong to one product.
- **Density pass:** no isolated oversized control breaks the high-resolution
  scale.
- **Subtraction pass:** ornamental details that do not improve the whole are
  removed.

Any result that reads as a generic dashboard wearing glass, glow, and raster
effects is rejected rather than polished.

## Approval sequence

1. Review Focus and Workbench at the target viewport.
2. Select or tune the material intensity using the fixed comparison.
3. Approve typography, canvas behavior, and the three signature behaviors.
4. Only then create the interactive docking mockup.
5. Production architecture and Design Bible reconciliation remain separate,
   explicitly unauthorized work.
