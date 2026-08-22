# 12. Integrated Control Clusters

## Principle

> Related controls should share a visual structure whenever doing so strengthens their semantic relationship and reduces repeated chrome.

A Control Cluster presents multiple independently interactive segments as one integrated instrument. It replaces a row of disconnected buttons with one outer frame, subtle internal separation, consistent geometry, and distinct per-segment states.

The pattern is preferred, not universal. The deciding question is:

> Would users describe these controls as parts of one task, or as separate decisions?

If they are parts of one task, a cluster is usually appropriate.

## Cluster types

### Action Cluster

Multiple related commands affecting the same object or context.

```text
[ Edit | Reroll | Versions | More ]
```

Use for:

- turn actions;
- Library record actions;
- inspector header actions;
- import/export/duplicate groups;
- undo/redo groups.

### Segmented Selector

Mutually exclusive choices.

```text
[ All | Stories | Characters | Lore ]
```

Use radio-group or tab semantics. One segment is selected at a time.

### Split Action

One primary action plus a related menu.

```text
[ Create story | v ]
```

Use only when the menu genuinely modifies or expands the primary action.

### Instrument Cluster

A mixed assembly of action, state, or continuous controls.

```text
[ Mute | Volume | Change sound | Settings ]
```

Use for ambience, playback, generation state, scale, or other persistent utilities.

## Visual anatomy

A conforming cluster has:

- one outer surface;
- one outer border;
- 4 px default outer radius;
- no gaps between segments;
- zero internal radii;
- subtle one-pixel separators;
- consistent segment height;
- fixed icon boxes;
- hover and pressed state confined to one segment;
- focus that clearly identifies the focused segment;
- no double borders.

Separators should be slightly inset vertically, generally occupying 55-70 percent of the control height. They must not read as a heavy table grid.

## Segment sizing

- Compact icon segment: 28-32 px desktop, 44 px touch.
- Default icon segment: 32-36 px desktop, 44 px touch.
- Text segment: content width plus 10-14 px horizontal padding per side.
- More segment: fixed compact width.
- Continuous control segment: receives a defined minimum and maximum width.

## State model

### Resting

Shared neutral surface and low-contrast separators.

### Hover

Only the hovered segment changes tone. The group silhouette remains unchanged.

### Pressed

The segment uses a restrained inset or darker tonal state. Avoid exaggerated translation.

### Selected

Use a soft accent tint, stronger label, or thin accent edge. Avoid turning every selected segment into a bright filled cyan tile.

### Focused

Use an inset 2 px focus outline or carefully clipped outer ring on the focused segment. Keyboard users must be able to identify the exact segment.

### Disabled

Only the affected segment becomes disabled unless the whole instrument is unavailable. Neighboring segments must retain normal contrast and interactivity.

### Loading

Replace the affected segment's icon or label with progress. Do not block the full cluster unless the whole task is locked.

### Destructive

Destructive actions normally sit outside the cluster or behind More. When inclusion is necessary:

- separate the segment with a stronger divider;
- keep it neutral at rest;
- introduce red on hover/focus and confirmation;
- never place Delete beside a primary action without separation.

## Semantics and keyboard behavior

- Action Cluster: `role="toolbar"` where appropriate; each segment remains a button.
- Segmented Selector: tabs, radio group, or pressed buttons based on behavior.
- Split Action: two buttons with related accessible labels.
- Instrument Cluster: grouped controls with a shared accessible label.
- Arrow-key navigation may use roving focus for dense clusters.
- Tab order must not become excessive; a toolbar may be one tab stop with arrow navigation when implemented correctly.

## Labels and discovery

New or unfamiliar actions should retain labels. Expert compact mode may reduce familiar actions to icons, but tooltips, shortcuts, and accessible names remain mandatory.

Do not use icon-only clusters as the default merely because they look clean.

## Mobile adaptation

Clusters must not wrap.

On mobile:

- maintain 44 px touch segments;
- show no more than approximately three frequent actions before More;
- move low-frequency actions to overflow;
- convert long segmented selectors to a select or staged filter when labels no longer fit;
- keep the selected segment visible;
- avoid horizontal scrolling unless the cluster is clearly a selector and the active item is brought into view.

Example:

```text
Desktop: [ Edit | Reroll | Versions | Duplicate | More ]
Mobile:  [ Edit | Reroll | More ]
```

The omitted actions remain available through More.

## Good candidates in Sonder

- Turn controls.
- Composer ambience utilities.
- Inspector Pin, Collapse, More, Close.
- Library Open, Duplicate, Export, More.
- Story scope and asset-type selectors.
- Theme, text-size, and density selectors.
- Undo/redo and version navigation.
- Dialog footer actions when tightly related.

## Misuse

Do not cluster:

- unrelated actions that happen to share a row;
- navigation with destructive commands;
- toggles and immediate commands without clear state treatment;
- more than five or six visible segments on desktop;
- long text actions that become hard to scan;
- controls with different heights;
- a primary action with several equally loud alternatives;
- actions whose boundaries become unclear on touch devices.
