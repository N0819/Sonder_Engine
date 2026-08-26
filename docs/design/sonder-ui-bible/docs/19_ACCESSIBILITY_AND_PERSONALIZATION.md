# 19. Accessibility and Personalization

## Position

The compact atmospheric reference is the default. Accessibility is not a
different product skin; it is equivalent control and readable material within
the same workbench architecture.

## Structural requirements

Every surface provides:

- semantic landmarks and workspace-current state;
- correctly labeled tabs, toolbars, separators, dialogs, and status;
- logical keyboard order and visible focus;
- non-drag commands for all module placement and ordering;
- focus containment/restoration for overlays and Widget Shelf;
- text errors and non-color status;
- reduced-motion support from first paint;
- browser zoom and text scaling without lost controls;
- 44 px touch hit regions where touch input is expected.

## Module keyboard model

Module action menus provide Move left/right, Merge as tab, Separate, Float, and
Return to Widget Shelf. Arrow keys resize vertical/horizontal separators in
announced steps. Tab strips use arrow navigation and an accessible reorder
command. Escape cancels a drag and restores the exact origin.

## Theme accessibility

- Every color role has a name and textual value.
- Range controls announce 0-100 values and their effect.
- Ambient X/Y, radius, and intensity expose numeric values and keyboard input.
- Invalid contrast is explained before a theme can be persisted.
- Essential state never depends on faint text or color alone.

## Presets and controls

Accessibility controls include:

- Solid surfaces;
- High contrast;
- Strong focus;
- Reduced motion;
- Larger interface;
- Larger story text;
- Roomy controls/hit targets;
- Color-independent status;
- Canvas/effects reduction.

Each control remains independently editable after any preset is applied.

## Compact text

Eight-to-ten-pixel text is allowed only for supplementary coordinates, values,
and status. It may not be the sole label for an essential action. Larger
Interface scales the role system together; it does not selectively inflate
headings and break cohesion.

## Transparency and contrast

Glass controls must pass contrast against the worst supported canvas. A local
veil or higher material alpha is preferred to text outlines. Solid surfaces
remove blur/transparency without changing layout. High contrast strengthens
text, edge, focus, and selection while preserving restrained accent semantics.

## Screen readers

- Workspace changes announce Scene, Library, or Settings.
- Module location changes announce destination and order.
- Shelf capacity and invalid destinations are explained.
- Saving/generation status is polite and concise.
- Decorative canvas/grid layers are hidden.
- Story prose remains ordinary readable document content.
