# 05. Information Architecture

## Primary destinations

Sonder has three primary destinations:

1. **Play**
2. **Library**
3. **Settings**

These names are short, plain, and player-facing. They remain stable across desktop and mobile.

## Play

Play contains:

- active story title and context;
- transcript;
- composer;
- turn progress and background work relevant to the story;
- scene ambience and immediate playback controls;
- Story Tools for Cast, World, Style, Dialogue, Attire, Backdrops, Ambience, and other current-story controls;
- contextual history, versions, rerolls, and turn actions.

Global application controls do not belong in the Play header.

## Library

Library contains reusable and story-associated material:

- Stories;
- Characters;
- Personas;
- Lore;
- imports and exports;
- recent and favorite items;
- search and type filters;
- story scopes;
- associations and usage information.

Library scopes:

- All Library;
- Current Story;
- Choose a Story;
- Unassigned;
- Used in Multiple Stories.

Scopes are filters and associations, not ownership folders. Detaching an item from a story must not delete or relocate the reusable record.

## Settings

Settings uses these top-level categories:

- **Experience**: appearance, reading, language, sound, notifications, motion, transparency, accessibility.
- **AI Connections**: providers, models, credentials, connection tests, generation defaults.
- **Content**: adult-content preferences, data handling, imports, exports, deletion, privacy-related presentation.
- **Add-ons**: extensions and permissions.
- **Maintenance**: updates, storage, backups, logs, repair tools.
- **Advanced**: prompts, raw parameters, diagnostics, technical detail, experiments, developer-facing controls.

## Desktop spatial model

Desktop uses three conceptual zones:

- **Left**: destination and selection navigation.
- **Center**: current content or work.
- **Right**: contextual inspector or detail.

The right inspector may be resized or pinned. It should never force the story below a usable reading measure.

## Mobile spatial model

Mobile uses:

- persistent bottom navigation for Play, Library, Settings;
- one primary content surface at a time;
- full-screen Story Tools and editors;
- sheets for temporary contextual actions;
- explicit Back behavior;
- retained context when returning to Play.

## Secondary navigation

Secondary navigation should use the simplest appropriate pattern:

- category rail on wide desktop;
- tab or segmented selector for a small set of peer views;
- searchable list for many categories;
- staged list-to-detail flow on mobile;
- More menu for low-frequency actions.

Avoid nesting more than three visible navigation levels. If a fourth level appears necessary, reconsider the grouping or use in-content sections.

## Search

Search is contextual by default:

- Library search searches Library material.
- Settings search searches settings and help text.
- Story Tools search, if added, searches current-story tools only.

A global Go To launcher may provide expert navigation without replacing visible primary navigation.

## Orientation requirements

Every destination must show:

- where the user is;
- what scope or item is active;
- how to return to the parent level;
- whether changes are saved;
- what the primary action is;
- where secondary actions are located.
