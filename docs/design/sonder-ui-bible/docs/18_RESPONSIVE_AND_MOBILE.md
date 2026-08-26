# 18. Responsive and Mobile

## Principle

The Atmospheric Workbench adapts one mental model. It does not swap to the old
rail, inspector, card dashboard, or mobile bottom navigation at a breakpoint.

## Reference viewports

Review at minimum:

- 1600 x 900 canonical workbench;
- 1440 x 900 desktop;
- 1280 x 800 desktop;
- 1180 x 800 constrained three-column state;
- 1024 x 768 tablet landscape;
- 768 x 1024 tablet portrait;
- 430 x 932 and 390 x 844 phones;
- 360 x 800 narrow phone;
- 844 x 390 phone landscape;
- 1024 x 600 short height;
- 2160 px-tall workspace for four-shelf capacity.

## Width behavior

### Wide: above 1180 px

Both toolbars may remain open around a minimum 420 px Scene column. Default
toolbar width is `min(286px, 18vw)`.

### Constrained: 861-1180 px

Toolbars reduce toward 230 px. If the Scene cannot preserve its minimum and
fixed reading measure, collapse the least recently used toolbar rather than
compress the story.

### Compact: 860 px and below

The Scene uses the full content width. Toolbars are closed by default and open
as full-height edge overlays or staged module sheets using the same shelf/tab
model. The integrated top shelf remains the primary navigation. The calibrated
compact state keeps the active Scene cell visible and stages Library and
Settings inside one workspace chooser occupying the same top-shelf cluster; it
does not merely delete access to those workspaces.

### Phone: 680 px and below

The top shelf prioritizes the active workspace and one compact workspace
chooser. Scene, Library, and Settings remain the only destinations and remain
plain unnumbered labels inside that chooser. Brand, story identity, and status
may reduce to compact disclosures. No bottom navigation is introduced.

## Height behavior

Shelf capacity follows usable toolbar height:

```text
clamp(floor((usableDockHeight + 20) / 420), 2, 4)
```

Capacity is calculated independently of tabs. A height change makes new shelf
rails available only when a shelf can retain useful content. If height shrinks,
existing arrangements are preserved by tabbing, scrolling, or staged recovery;
modules are never silently discarded.

## Touch

- Hit regions are at least 44 px even when the visible bar remains 30 px.
- Long-press may begin drag only after clear feedback.
- Every drag action is available from the module action menu.
- Splitters expose keyboard/touch step controls.
- Tabs remain reorderable without requiring pixel-perfect drops.

## Composer and keyboard

The composer stays above the software keyboard, preserves its fixed reading
measure within available width, and remains reachable with one thumb. Open
module overlays cannot cover the focused input without a clear Back/Close path.

## Short height and landscape

Reduce in this order:

1. available shelf count;
2. secondary module metadata;
3. canvas-only ornament;
4. toolbar visibility;

The default 15 px prose may optically reduce to 13 px in the calibrated compact
state. A user-selected larger text size or Accessibility Mode overrides that
reduction. Never hide the composer or allow sticky chrome to consume the
viewport.

## State preservation

Workspace, module, tab, shelf, query, selection, scroll, and draft state survive
responsive transitions. Returning to a wider viewport restores the prior
arrangement when it is still valid.
