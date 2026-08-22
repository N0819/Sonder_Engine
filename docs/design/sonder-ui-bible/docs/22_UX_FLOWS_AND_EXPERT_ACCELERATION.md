# 22. UX Flows and Expert Acceleration

## UX doctrine

The interface should serve two groups without splitting into separate products:

- new users who need orientation and a clear next action;
- experienced users who need speed, density, and direct access.

The strategy is progressive disclosure plus invisible acceleration.

## New-user path

A new user should be able to:

1. create or sign into the host account;
2. understand Play, Library, and Settings;
3. connect an AI provider when generation is requested;
4. create a story through one of three plain routes;
5. enter Play with a clear next action;
6. discover Story Tools when needed;
7. find reusable material in Library.

The first-run path must not require understanding personas, lore inheritance, model roles, raw prompts, or world-state JSON.

## Returning-user path

Returning users should see:

- last active story;
- recent stories;
- preserved reading position;
- remembered inspector state;
- visible connection or save problems only when relevant;
- quick access to New Story and Library.

## Experienced-user acceleration

### Keyboard shortcuts

Core recommended shortcuts:

- `Ctrl/Cmd+K`: Go To / command-search launcher when implemented;
- `Ctrl/Cmd+Enter`: Send story input;
- `Esc`: close transient layer or return one staged level;
- `/`: focus current-surface search when not editing text;
- `Ctrl/Cmd+,`: Settings when platform/browser conventions allow.

Shortcuts must be discoverable in tooltips, More menus, or a shortcut reference. They must not conflict with text editing.

### Go To launcher

A global launcher is a preferred expert accelerator, not a replacement for visible navigation. It may search:

- destinations;
- stories and Library items;
- Settings sections;
- Story Tools;
- common actions.

New users can ignore it entirely. Results use plain labels and show context.

### Pinned tools

Users may pin frequent Story Tools or Library scopes. Pinning should not create duplicate controls or a crowded header. A small fixed capacity is preferable to unlimited accumulation.

### Recents

Recent stories and Library items should be available where they reduce repeated search. Recents must remain secondary to the current context.

### Compact density

Compact density is a user preference for desktop. It reduces row and panel padding while preserving legibility, hit targets, labels, and state clarity.

### Stable More menus

Low-frequency actions belong in predictable More menus. An action should not move between direct display and More unpredictably at the same width and state.

## Core flow reviews

### Create story

- User can choose a route without AI connection.
- Generation asks for connection only when needed.
- Draft survives Back/exit.
- Review explains created records.
- Result opens in Play.

### Continue story

- Input is obvious.
- Turn state is visible.
- Stop is available when possible.
- New turn does not disrupt scrollback review.
- Error preserves input.

### Add character to story

- User can search Library.
- User understands whether the character is reusable.
- Attach does not duplicate unexpectedly.
- Remove from story is not Delete.

### Edit long lore

- Draft is retained.
- Save state is visible.
- Validation is near the field.
- Raw/advanced structure is optional.
- Mobile editor remains usable with keyboard.

### Connect provider

- Staged setup.
- Test result is plain.
- Secret handling is clear.
- Failure preserves safe input.
- Default model selection follows connection.

### Change appearance

- Applies immediately where safe.
- Does not alter story data.
- Reset is available.
- Accessibility controls remain independent.

## Friction budget

A common action should generally be reachable within:

- one action from its primary context;
- two actions from a predictable destination;
- three actions only for advanced or high-risk functions.

If a frequently used action requires repeated navigation through unrelated categories, the flow needs redesign.

## Complexity budget

The default Play surface should expose:

- the story;
- composer;
- current status;
- one route to Story Tools;
- only the most immediate utility controls.

Everything else must earn permanent space through frequency and context.
