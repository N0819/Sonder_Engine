# 19. Accessibility and Personalization

## Design position

The default interface preserves the approved visual reference. Structural accessibility is mandatory. Visual changes that materially alter contrast, transparency, motion, density, or typography are available through an Accessibility Mode preset and granular controls.

## Structural requirements

All player-facing surfaces must provide:

- semantic landmarks;
- correct control roles;
- accessible names for icon-only controls;
- logical heading hierarchy;
- full keyboard operation;
- visible focus;
- focus containment and restoration in dialogs/sheets;
- no essential hover-only action;
- touch targets appropriate for mobile;
- browser text scaling without broken layouts;
- errors described in text;
- status not communicated by color alone;
- reduced-motion support from first paint.

## Accessibility Mode preset

Accessibility Mode enables a recommended combination of:

- high contrast;
- solid surfaces or reduced transparency;
- stronger focus indicators;
- reduced motion;
- larger interface text;
- larger story text;
- increased spacing and touch targets;
- color-independent status markers.

After enabling the preset, each option remains independently editable.

## Granular controls

### High contrast

Strengthens text, borders, selected state, and status differentiation. It should not invert the entire design or introduce uncontrolled bright surfaces.

### Solid surfaces

Disables or substantially reduces glass and backdrop transparency while preserving hierarchy.

### Strong focus

Uses a more prominent 2-3 px focus treatment and optional focus fill.

### Reduced motion

Removes nonessential transitions, weather movement, parallax, and animated stage effects. It should not merely slow them.

### Larger UI

Scales navigation, controls, labels, and hit targets without scaling story prose unless requested.

### Larger story text

Scales prose and composer independently.

### Increased spacing

Moves Comfortable density toward larger row heights and gaps.

### Color-independent status

Adds icons, labels, patterns, or shapes so warning, success, selected, and error states remain distinguishable.

## Contrast policy

Default primary text and critical controls should aim for strong contrast. Secondary nonessential metadata may remain quieter to preserve the reference treatment, but it must not carry essential information alone. Accessibility Mode corrects low-contrast secondary presentation.

## Keyboard model

- Tab reaches primary regions and controls in a logical order.
- Arrow keys operate tabs, segmented selectors, menus, and roving-focus toolbars where appropriate.
- Escape closes transient layers when safe.
- Focus returns to the invoking control.
- Keyboard users can reach turn actions, Story Tools, Library row actions, Settings search, and dialog actions.
- Focus does not become trapped in code editors or extension views.

## Screen-reader behavior

- Primary destinations expose current state.
- Dialogs and sheets have labels and descriptions.
- Save state and background work are announced politely.
- Raw token streaming is not announced by default.
- Repeated decorative indices are hidden when they add no semantic value.
- Icon-only controls expose action-specific labels.
- Error summaries link to affected fields when practical.

## Personalization

Personalization should improve comfort without changing meaning:

- curated themes;
- Legacy themes;
- interface density;
- interface scale;
- prose size and width;
- motion/effects level;
- transparency;
- pinned Story Tools;
- remembered pane width;
- notification and sound preferences.

Personalization settings should be browser-local unless there is a clear account-level reason to synchronize them.

## Accessibility review states

Every major surface must be reviewed in:

- default reference mode;
- Accessibility Mode;
- solid surfaces only;
- reduced motion only;
- largest UI size;
- largest prose size;
- keyboard only;
- touch only;
- 200 percent browser zoom;
- long localized labels.
