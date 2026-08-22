# 23. Anti-Patterns

## Purpose

This catalog names recurring failure modes so review discussions can be specific. These are not minor style preferences; repeated violations create visible inconsistency and UX friction.

## Visual anti-patterns

### Dark SaaS cards

Symptoms:

- large rounded cards;
- broad shadows;
- generous empty padding;
- every section floating independently;
- dashboard statistics without task value.

Correction:

- use continuous ledgers, section frames, split panes, and 3-5 px geometry;
- reserve cards for discrete objects or choices.

### Cyan flood

Symptoms:

- multiple large filled cyan controls;
- cyan selected cards, tabs, borders, links, and icons all at once;
- accent used as decoration.

Correction:

- reserve cyan for current selection, focus, and one immediate primary action;
- use neutral tone and hairline structure for ordinary grouping.

### Over-indexing

Symptoms:

- numbers on every row, button, field, and heading;
- decorative `01` labels with no navigational value;
- indices louder than the content.

Correction:

- use indices only for major destinations, tools, long ledgers, and real sequences.

### Monospace saturation

Symptoms:

- all navigation, headings, labels, and metadata rendered as monospace;
- interface feels like a terminal;
- small technical text becomes tiring.

Correction:

- restore sans-serif as the default UI voice;
- keep monospace for identifiers, indices, code, and diagnostics.

### Unstructured black space

Symptoms:

- a small content fragment floating in a large plain black region;
- no reading stage, contextual empty state, or deliberate alignment;
- interface looks unfinished.

Correction:

- maintain the content measure, stage treatment, contextual framing, and clear next action.

### Glass everywhere

Symptoms:

- every panel translucent;
- story imagery changes chrome hue;
- blur hurts performance and readability;
- no clear surface hierarchy.

Correction:

- use controlled glass only on contextual or atmospheric surfaces;
- keep dense forms and primary chrome more solid.

### Decorative HUD drift

Symptoms:

- scanlines, glowing brackets, crosshairs, dense grids, pulsing status lights;
- interface clashes with fantasy and contemporary stories.

Correction:

- use restrained instrument precision through geometry and alignment, not cockpit decoration.

## Alignment anti-patterns

### Icon-box drift

Symptoms:

- icons have different visible sizes;
- some sit high or low;
- labels shift based on SVG path bounds;
- chevrons and trailing actions wander.

Correction:

- fixed icon boxes, grid-authored SVGs, optical corrections recorded per icon, common alignment axes.

### Mixed control heights

Symptoms:

- adjacent buttons and inputs differ by 2-6 px;
- text looks vertically misaligned;
- clusters feel assembled rather than designed.

Correction:

- use tokenized heights and exact peer dimensions.

### Arbitrary padding

Symptoms:

- 7, 9, 11, 13, 15, 17 px values scattered across components;
- no repeated rhythm;
- adjacent panels feel unrelated.

Correction:

- use the spacing scale; document rare optical exceptions.

### State-induced layout shift

Symptoms:

- selected border becomes thicker;
- loading label changes button width;
- validation pushes actions unexpectedly;
- hover changes geometry.

Correction:

- reserve space; use inset or color changes; keep dimensions stable.

## Interaction anti-patterns

### Button field

Symptoms:

- five separate small buttons with repeated borders and gaps;
- weak relationship between actions;
- excessive visual noise.

Correction:

- use an Action Cluster when actions belong to one task.

### Cluster misuse

Symptoms:

- unrelated actions merged because they fit;
- destructive action beside primary action;
- mixed toggles and commands with unclear states;
- cluster wraps on mobile.

Correction:

- split by task, separate danger, move low-frequency actions to More, never wrap.

### Hover-only capability

Symptoms:

- essential actions appear only on mouse hover;
- touch and keyboard users cannot discover them.

Correction:

- maintain visible or focus-revealed routes; keep touch actions accessible.

### More-menu dumping ground

Symptoms:

- frequent actions hidden in More;
- menu order changes by screen;
- user must hunt for basic tasks.

Correction:

- direct display for frequent actions; stable More ordering for secondary actions.

### Duplicate homes

Symptoms:

- the same global feature appears in Play, Library, and Settings;
- users cannot predict where to return.

Correction:

- one primary home, optional contextual shortcut that links back to the canonical surface.

## UX anti-patterns

### Internal model first

Symptoms:

- onboarding asks about personas, roles, schemas, raw state, or prompts before the story goal is clear.

Correction:

- ask in player language; reveal internal structure after the user has a reason to understand it.

### Blocked first screen

Symptoms:

- missing AI provider prevents any story setup;
- user cannot start blank or use existing material.

Correction:

- gate only the generation action that requires AI.

### Mobile compression

Symptoms:

- desktop columns simply narrow;
- tiny labels, fixed-width fields, hidden actions, horizontal toolbars.

Correction:

- recompose into staged views, sheets, bottom navigation, and reduced visible actions.

### Empty state without recovery

Symptoms:

- "No data" or "Select an item" in a large blank panel;
- no create, import, or clear-filter action.

Correction:

- explain context and provide the next useful action.

### Save ambiguity

Symptoms:

- user cannot tell whether changes are saved;
- autosave and explicit save are mixed without explanation;
- leaving may lose long text.

Correction:

- hybrid saving with stable status and recoverable drafts.

### Technical error leakage

Symptoms:

- raw HTTP or stack errors shown as the primary message;
- no recovery guidance;
- user work disappears.

Correction:

- plain outcome, likely cause, next step, work-preservation statement; raw detail expandable in Advanced.

## Review rule

Finding one anti-pattern is not permission to patch only the visible instance. Review the component family and root cause so the same defect does not survive elsewhere.
