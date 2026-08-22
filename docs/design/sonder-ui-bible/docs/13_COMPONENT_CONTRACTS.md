# 13. Component Contracts

## Purpose

Every reusable component must have a visual and behavioral contract. One-off CSS that resembles a component is not a component.

## Buttons

### Primary

- One dominant primary action per local decision region.
- Cyan fill or strong accent edge, depending on context.
- Plain action label.
- Disabled, loading, focus, and pressed states required.
- Do not use for passive selection.

### Secondary

- Neutral surface and border.
- Used for ordinary actions.
- Hover may introduce a subtle cyan border or tint.

### Ghost

- No persistent frame unless hovered/focused.
- Use in quiet toolbars and headers.
- Must retain a visible hit target.

### Danger

- Neutral or lightly red at rest.
- Red becomes stronger on hover/focus and confirmation.
- Destructive confirmation must state the object and consequence.

### Icon button

- Fixed square box.
- Original SVG icon.
- Tooltip and accessible name.
- 3-4 px radius.
- No text glyph fallback in final production.

## Inputs and textareas

- Labels are explicit; placeholders do not replace labels.
- Help text explains consequence, not obvious mechanics.
- Focus uses cyan border and controlled ring.
- Error state uses red plus text and an icon/marker.
- Long editors retain drafts.
- Mobile inputs use a safe font size and keyboard-appropriate input type.
- Inline save state appears near the field group or editor header.

## Selects and comboboxes

- Use a select for a bounded set of options.
- Use a combobox for searchable or large sets.
- Trailing chevron occupies a fixed column.
- Selected values must not collide with the chevron.
- Native controls may be used where they improve mobile reliability, provided visual alignment remains acceptable.

## Switches and checkboxes

- Use a switch for immediate on/off state.
- Use a checkbox for selection, consent, or multi-choice.
- Labels remain clickable.
- Explain consequences beneath consequential switches.
- Do not hide the state inside color alone.

## Tabs and segmented selectors

- Use for peer views at the same hierarchy.
- Keep the set short.
- Selected state uses tone, text strength, and a restrained accent marker.
- Avoid pill tabs.
- Mobile may scroll a category strip only when the active category is automatically visible.

## Navigation rail

- Play, Library, Settings remain visible and stable.
- Indices may support the label but never replace it.
- Active state is obvious through accent edge, tone, and text/icon treatment.
- The product lockup remains compact and genre-neutral.
- Extension destinations must follow the same spacing and icon contract.

## Page and section headers

A header contains, in order:

1. optional eyebrow or index;
2. title;
3. optional description or context;
4. optional action cluster.

Do not place headings inside arbitrary dark bars. A header surface is justified only when it is persistent, sticky, or structurally separates a pane.

## Lists and ledgers

- Rows share a stable grid.
- Primary label and secondary metadata are visually distinct.
- Selection and hover are different states.
- Actions use a trailing cluster or More menu.
- Empty results explain how to recover.
- Bulk actions appear only after selection.
- Long labels wrap before actions disappear.

## Cards

Cards are not the default solution for grouping. Use them only when content is a discrete object or decision.

A card should have:

- 4 px radius;
- one-pixel border;
- minimal shadow;
- clear internal hierarchy;
- no excessive padding;
- no decorative gradient unless it communicates state.

Prefer continuous ledgers, section frames, and split panes over a dashboard of disconnected cards.

## Inspector

- Right-side contextual surface on desktop.
- Full-screen or large sheet on mobile.
- Header contains title, context, and integrated Pin/Collapse/More/Close cluster.
- Tool list uses clear names and optional indices.
- Active tool state remains visible.
- Inspector remembers reasonable width and pinned state.
- Inspector content does not silently autosave high-risk changes.

## Dialogs and sheets

- Dialogs are for focused decisions, confirmations, or short editors.
- Large editing workflows should use a dedicated page, inspector, or full-screen sheet.
- Header, body, and footer align to the same inset.
- Primary action appears at the trailing end; Cancel or Back remains available.
- Focus is trapped and restored.
- Escape closes when safe.
- Mobile dialogs generally become full-screen sheets.

## Toasts and notices

- Toasts confirm transient outcomes.
- Persistent problems use inline notices or status panels.
- Toasts contain a concise title and optional one-line detail.
- Do not use toast-only error reporting for work the user must fix.
- Multiple toasts stack without covering primary navigation or composer.

## Empty states

Every empty state includes:

- plain explanation;
- one primary next action;
- optional secondary action;
- no decorative illustration that overwhelms the task;
- no technical cause unless useful.

## Loading and progress

- Skeletons are appropriate for predictable content structure.
- Spinners are appropriate for short, indeterminate waits.
- Long operations need a label, progress or elapsed state, and background behavior.
- The user must know whether they can leave the surface safely.

## Menus and More

- More contains low-frequency contextual actions.
- Menu order follows frequency, then danger.
- Destructive actions are separated.
- Checkable states use clear markers.
- Menus close on selection, Escape, and outside click.
- The trigger remains visually associated with the object or window it controls.

## Tooltips

- Use for icon meaning, shortcut hints, or concise clarification.
- Do not hide essential instructions in tooltips.
- Delay should be short enough for discovery but not intrusive.
- Touch interfaces need an alternate discovery path.
