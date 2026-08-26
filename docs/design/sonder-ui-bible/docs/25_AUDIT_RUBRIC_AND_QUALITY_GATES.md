# 25. Audit Rubric and Quality Gates

## Audit dimensions

Review every major surface in seven dimensions:

1. canonical composition;
2. material and typography coherence;
3. module/docking behavior;
4. task clarity and state preservation;
5. responsive height and width behavior;
6. accessibility and input parity;
7. runtime integration and recovery.

## Severity

- **P0 Broken:** data loss, security/runtime authority regression, unreachable
  core workflow, or arrangement loss.
- **P1 High:** wrong macro composition, unusable docking, hidden capability,
  inaccessible drag-only workflow, broken responsive state, or persistent
  conflict with the canonical reference.
- **P2 Polish:** visible density, alignment, opacity, type, focus, or feedback
  defect that weakens cohesion.
- **P3 Refinement:** nonblocking calibration improvement.

No P0 may remain. No P1 may remain without a product-owner deviation.

## Same-viewport visual review

At 1600 x 900 compare the implementation directly with the standalone
Atmospheric Workbench preview. Review in this order:

1. full canvas and top-shelf silhouette;
2. toolbar widths, Scene measure, composer position;
3. shelf/tab geometry and module order;
4. type scale and role assignment;
5. glass, bars, frost, edges, and state strength;
6. details and optical alignment.

An implementation that merely contains the named controls does not pass.

## Required interaction evidence

- collapse/reopen each toolbar smoothly;
- composer/prose measure remains unchanged;
- resize each toolbar and shelf with pointer and keyboard;
- merge Personas onto Scene Effects as a tab without precision struggle;
- separate a merged tab;
- reorder left/middle/right tabs naturally;
- create shelves only at visible valid rails;
- reject impossible shelf drops at capacity;
- float without a lagging duplicate ghost;
- return explicitly to Widget Shelf;
- restore origin after invalid drop or Escape;
- reopen/locate every stored, docked, tabbed, and floating module;
- preserve arrangement across workspace/viewport changes.

## Required height evidence

- ordinary height exposes two shelf spaces per side;
- sufficiently tall height exposes three;
- 2160 px-tall workbench exposes four;
- tabs do not consume shelf count;
- shrinking height does not lose modules.

## Required theme evidence

- Glass Density reaches true 0% and 100%; default 20%;
- Bar Opacity reaches true 0% and 100%; default 60%;
- Selected Strength reaches true 0% and 100%; default 6%;
- Frost reaches true 0% and 100%; default 50%;
- bars across top shelf/module tabs respond together;
- all six color roles update correctly;
- ambient X/Y/radius/intensity work by pointer and keyboard;
- atmospheric and gradient canvases retain readable prose;
- no grain/noise/activity layer remains.

## Typography and geometry evidence

- Geist Sans/Mono/Newsreader roles match the canonical scale;
- no ordinary heading exceeds the allowed hierarchy;
- Scene/Library/Settings and module titles have no indices;
- all free-standing corners are rounded 4 px;
- no chamfers or unrelated card radius family remains;
- borderless portrait minus/plus work at all five steps.

## Responsive matrix

Capture 1600x900, 1440x900, 1280x800, 1180x800, 1024x768,
768x1024, 430x932, 390x844, 360x800, 844x390, 1024x600, and a
2160 px-tall state. Include Workbench, Focus, Library, Settings, Widget Shelf,
floating module, tab drag, shelf drag, solid surfaces, reduced motion, high
contrast, and long-label states.

## Completion evidence

- canonical and implementation screenshots side by side;
- interaction regression results;
- keyboard/touch notes;
- state and recovery matrix;
- responsive shelf-capacity evidence;
- theme boundary evidence;
- runtime contract tests;
- list of deliberate deviations with owner approval.
