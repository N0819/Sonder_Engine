# 18. Responsive and Mobile

## Principle

Mobile is not a reduced product and not a compressed desktop layout. It is the same capability model expressed through staged interaction, touch geometry, and progressive disclosure.

## Reference viewports

Design and test at minimum:

- 1440 x 900 desktop;
- 1280 x 800 desktop;
- 1024 x 768 small desktop/tablet landscape;
- 768 x 1024 tablet portrait;
- 430 x 932 large phone;
- 390 x 844 common phone;
- 360 x 800 narrow phone;
- 844 x 390 phone landscape;
- short-height desktop at 1024 x 600.

## Breakpoint strategy

Breakpoints should respond to available component space rather than arbitrary device names. Container queries are preferred for local components where practical.

Key transitions:

- three-zone desktop to two-pane layout;
- persistent inspector to overlay/sheet;
- Library multi-pane to list-to-detail;
- desktop rail to mobile bottom navigation;
- visible action cluster to reduced cluster plus More;
- side-by-side forms to stacked forms.

## Mobile primary navigation

- Play, Library, Settings remain visible in bottom navigation.
- Each item uses icon plus label.
- Active state uses restrained cyan and tone.
- Bottom navigation respects safe areas.
- The software keyboard may temporarily reduce or hide the bar only when the composer remains understandable and navigation restores reliably.

## Mobile headers

A mobile header should contain:

- Back when inside a subview;
- concise title;
- one or two essential actions;
- More for secondary actions.

Avoid horizontally scrolling toolbars in primary flows.

## Sheets and staged views

Use full-screen or near-full-screen sheets for:

- Story Tools;
- Library editors;
- Settings sections;
- complex pickers;
- import workflows;
- long forms.

Sheets require:

- stable header;
- explicit Back or Close;
- safe-area padding;
- scrollable body;
- sticky action footer when required;
- focus and keyboard management;
- preserved parent state.

## Touch targets

- Minimum interactive target: 44 x 44 px.
- Visual icon may remain 20-24 px inside the target.
- Adjacent targets must not overlap.
- Destructive actions should not sit immediately beside frequent actions without separation.

## Composer and software keyboard

- Composer remains above the software keyboard.
- Textarea growth must not push all story content off-screen.
- Send remains reachable with one thumb.
- Ambience utilities move to a second row, compact cluster, or sheet.
- Safe-area inset is applied beneath controls.
- Landscape short-height mode reduces secondary chrome before reducing text.

## Mobile lists

- Use full-width rows.
- Keep primary label and one line of useful metadata.
- Move low-frequency actions to More.
- Preserve search and scope.
- Return from detail to the same scroll position.
- Bring active horizontal filters into view automatically.

## Mobile forms

- Stack labels and controls.
- Use appropriate keyboard types.
- Keep error text near the field.
- Avoid tiny two-column grids.
- Sticky Save/Apply is appropriate for long explicit-save forms.
- Do not rely on hover tooltips; include visible help or an info action.

## Tablet

Tablet is not automatically mobile. At 768-1024 px, use available space to preserve two-pane views when content remains readable. Touch targets still apply.

## Landscape and short-height

Prioritize vertical space:

1. reduce decorative header height;
2. collapse nonessential descriptions;
3. move utilities into More;
4. cap technical panes;
5. preserve transcript and composer.

Do not hide the primary action or make the composer unusable.

## Responsive anti-patterns

- shrinking desktop panels until text and icons misalign;
- horizontal scrolling for primary navigation;
- hiding features with no mobile route;
- wrapping control clusters;
- relying on hover-revealed actions;
- desktop fixed widths inside mobile forms;
- bottom navigation covered by browser or safe-area UI;
- active category off-screen in a horizontal strip;
- modal boxes that exceed viewport height without internal scrolling.
