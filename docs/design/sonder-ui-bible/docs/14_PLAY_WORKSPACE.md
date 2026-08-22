# 14. Play Workspace

## Purpose

Play is the story-first destination. Its default state should invite reading and writing, not configuration.

## Desktop composition

Desktop uses:

- left primary navigation;
- central story stage;
- optional right contextual inspector;
- composer anchored beneath the story;
- scene status and background work placed without covering reading content.

The story stage should remain visually dominant even when the inspector is open.

## Header

The Play header should contain only:

- current story title;
- optional story/frame context;
- compact story-level More menu;
- Story Tools entry or inspector state;
- essential connection or save status when relevant.

It must not contain Appearance, updates, provider configuration, prompts, extensions, or maintenance controls.

## Transcript

### Reading measure

- Default maximum story width: approximately 720 px.
- User-adjustable through reading settings.
- Player input and narration share the same overall column.
- A backdrop appearing must not change line wrapping.

### Turn structure

Each turn may include:

- optional turn index or subtle sequence marker;
- player input echo;
- narration;
- stale/superseded explanation;
- version navigation;
- contextual action cluster.

The index should remain quiet. It is a structural aid, not the primary content.

### Turn actions

Desktop default:

```text
[ Edit | Reroll | Versions | More ]
```

Mobile default:

```text
[ Edit | Reroll | More ]
```

Actions should remain visible on touch devices. On pointer devices they may become quieter at rest but must remain discoverable through focus and not disappear entirely from keyboard use.

### Long transcripts

- Off-screen turns may use content visibility or virtualization.
- The newest turns remain fully measured to prevent scroll jumps.
- Scroll position must remain stable when tools open or close.
- Returning from Library or Settings restores the previous place.
- New content should not force-scroll a user who is reviewing older turns without a clear "new turn" affordance.

## Composer

### Core structure

The composer contains:

- literary serif textarea;
- Send or Stop action;
- concise status/help;
- optional integrated utility cluster.

The textarea and prose should feel like parts of the same reading/writing system.

### Utility cluster

Ambience and immediate playback controls may form an Instrument Cluster:

```text
[ Mute | Volume | Change sound | Chime | More ]
```

The cluster must not overlap the input or Send action. It should move to a secondary row, sheet, or More menu when width is limited.

### Send behavior

- `Ctrl/Cmd+Enter` sends on desktop.
- Mobile uses a visible Send action and may optionally support keyboard send conventions without surprising multiline entry.
- Empty input behavior must be explained if it has story meaning.
- Stop replaces Send only while generation is cancellable.
- Loading state must not cause the button width to jump.

## Story Tools inspector

Primary tools include:

1. Cast
2. World
3. Style
4. Dialogue
5. Attire
6. Backdrops
7. Ambience
8. Related story configuration

The exact names may be refined for clarity, but ordinary UI should remain plain.

The inspector header uses an integrated cluster for Pin, Collapse, More, and Close. Tools may use indices when they improve scan order.

### Pinning

Experienced users may pin frequently used tools. Pinning should:

- persist per browser or user;
- not add a second duplicate action elsewhere;
- remain reversible;
- not crowd the novice default state;
- adapt on mobile by pinning to Story Tools favorites rather than creating permanent side panels.

## Scene imagery and atmosphere

- Backdrops belong to the central stage.
- Navigation, Settings, and text-heavy editors remain neutral.
- Story turn plates may become translucent over imagery.
- Weather stays behind interactive UI.
- Reduced effects and solid surfaces remain available.
- No backdrop state may reflow prose or hide the composer.

## Status and background work

Turn progress should answer:

- what is happening;
- whether the user can stop it;
- whether the user can leave the screen;
- how long it has been running when useful.

Raw technical stage output belongs in Advanced or an explicitly enabled technical-detail surface, not the default Play header.

## Empty Play

When no story is active, show:

- a concise welcome or orientation statement;
- primary action: New Story;
- secondary action: Open from Library;
- recent story shortcuts when available;
- AI connection prompt only if required for the selected action.

Do not show an empty black reading field with a small centered sentence and no clear route forward.

## Mobile Play

Mobile preserves:

- story title and context;
- transcript;
- composer;
- turn actions;
- Story Tools;
- ambience and status;
- versions and editing.

It changes presentation through:

- bottom navigation;
- full-screen Story Tools;
- sticky or keyboard-aware composer;
- fewer visible turn actions before More;
- full-width reading layout with safe padding;
- stable Back behavior.
