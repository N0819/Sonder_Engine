# 16. Settings

## Purpose

Settings should make a complex engine configurable without presenting a wall of internals.

## Categories

### Experience

- theme;
- interface scale and density;
- story typography and width;
- language;
- sound and notifications;
- motion and effects;
- transparency;
- Accessibility Mode and granular accessibility controls.

### AI Connections

- provider setup;
- credentials;
- model selection;
- connection tests;
- generation defaults;
- context/cost information where available;
- advanced per-role configuration behind disclosure.

### Content

- adult-content preference;
- safety-related presentation;
- data handling;
- exports and deletion;
- privacy-related explanation.

### Add-ons

- extension list;
- enable/disable state;
- permissions;
- update status;
- extension-specific settings.

### Maintenance

- application updates;
- storage use;
- backups;
- logs;
- repair and rebuild tools;
- database or cache maintenance in plain language.

### Advanced

- prompt editing;
- raw generation parameters;
- technical-detail stream;
- diagnostics;
- experimental features;
- developer-oriented controls.

## Layout

Desktop uses:

- searchable category column;
- full detail pane;
- sticky save/apply status where needed;
- section anchors for long pages.

Mobile uses:

- searchable category list;
- full-screen section pages;
- visible Back to category list;
- selected category brought into view when using horizontal subnavigation;
- sticky action footer for explicit Apply/Connect operations.

## Search

Settings search should match:

- labels;
- descriptions;
- common synonyms;
- old names where terminology changed;
- related concepts.

Results show category context and navigate directly to the setting. Search must not expose secret values.

## Section design

Settings sections use flat framed groups or continuous forms, not a dashboard of independent cards.

Each section should include:

- heading;
- concise description when the consequence is not obvious;
- controls aligned to a consistent field grid;
- save state;
- optional reset for that section;
- errors near affected controls.

## Advanced disclosure

Advanced settings remain a stable top-level category rather than an invisible "expert mode" that makes features appear and disappear.

Within Advanced:

- group by task;
- warn before expensive or dangerous changes;
- use monospace only for genuine technical data;
- include reset/default controls;
- explain when a change affects current stories versus future generation;
- preserve raw editors for expert use without making them the only editor.

## AI Connections UX

Provider setup should follow a staged pattern:

1. Choose provider.
2. Enter credentials or endpoint.
3. Test connection.
4. Choose default model.
5. Confirm and save.

The flow should explain failures in plain language and preserve entered values where safe. A user should not need to interpret an HTTP error before learning that the key is invalid or the server cannot be reached.

## Appearance and themes

Theme choices should use compact visual previews and clear names:

- Carbon Signal;
- Ash and Brass;
- Midnight Ink;
- Parchment Night;
- Legacy section.

Theme selection may use a ledger or card grid, but selection should be restrained. Do not fill a large card with cyan.

## Accessibility

Accessibility Mode is visible in Experience, not hidden inside Advanced. Individual controls remain available after the preset is enabled.

## Saving

- Browser-local appearance changes may apply immediately.
- Credentials require explicit Connect/Save.
- Expensive or structural changes require Apply.
- Long prompt editors retain drafts.
- Save status is visible.
- Leaving with invalid unsaved changes prompts the user.

## Dangerous operations

Delete, reset, rebuild, repair, or clear operations must:

- state the affected object;
- state whether the action is reversible;
- avoid ambiguous labels such as Confirm;
- require a dedicated confirmation for high-impact actions;
- separate the destructive action from ordinary control clusters.
