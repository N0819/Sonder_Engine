# 15. Library

## Purpose

Library is the single place for finding, creating, connecting, importing, exporting, and maintaining story material.

It must support both mental models:

- "Show me everything I own."
- "Show me everything connected to this story."

## Core model

Library contains:

- Stories;
- Characters;
- Personas;
- Lore;
- recent items;
- favorites or pinned items where implemented;
- story associations;
- import/export tools;
- search and filtering.

## Scope selector

The primary Library scope selector includes:

- All Library;
- Current Story;
- Choose a Story;
- Unassigned;
- Used in Multiple Stories.

The selector should be an integrated control or a compact scope picker, not a row of unrelated buttons.

Story scopes are views over associations. They do not create ownership folders.

## Desktop layout

Preferred wide layout:

- left category/scope column;
- central searchable item ledger;
- right detail/editor pane.

The detail pane may collapse when no item is selected. The central ledger should expand rather than leave a large empty region.

At narrower desktop/tablet widths, use list-to-detail navigation or a two-pane layout.

## Mobile layout

Mobile uses:

- persistent Library title and scope;
- search;
- type filter;
- full-width item list;
- full-screen detail/editor after selection;
- predictable Back to the prior filtered list;
- retained scroll position and query.

## Search

Search should cover:

- item names;
- summaries/descriptions;
- relevant tags or categories;
- story associations;
- lore keys where useful.

Search state remains visible. No-results state suggests clearing filters or changing scope.

## Type filters

Type filters may use a segmented selector when labels fit:

```text
[ All | Stories | Characters | Personas | Lore ]
```

On narrow mobile widths, use a compact filter sheet or select. Do not shrink labels into unreadable abbreviations.

## Item ledger

Each row should include:

- leading icon or index;
- primary name;
- item type when not already filtered;
- concise secondary metadata;
- usage or story association when relevant;
- selected state;
- trailing action cluster or More.

Suggested action cluster:

```text
[ Open | Duplicate | Export | More ]
```

Delete and Archive normally live in More, separated from ordinary actions.

## Story-scoped view

A selected story scope may show:

- story overview;
- attached characters;
- player persona;
- connected lore;
- recent activity;
- unresolved or missing references;
- shared items used elsewhere.

The view should resemble a coherent collection without implying that attached items cease to be globally reusable.

## Associations

Attach and detach actions must use plain language:

- Add to story;
- Remove from story;
- Used in 3 stories;
- Set as player persona.

Avoid database language such as link row, join, foreign key, or binding in ordinary UI.

## Create and import

The primary Library action is contextual:

- New Story in Stories;
- New Character in Characters;
- New Persona in Personas;
- New Lorebook in Lore;
- Add or Import in broader views.

Use split actions only when the relationship is clear:

```text
[ New Character | v ]
```

The menu may offer Import or Generate. Do not hide the ordinary creation route behind a dropdown.

## Editors

Editors should be dedicated surfaces rather than oversized generic dialogs when the content is long or structured.

Editing contract:

- clear title and item type;
- save state;
- recoverable draft for long text;
- sections with plain labels;
- advanced/raw representation behind disclosure;
- story usage visible but not dominant;
- import warnings and validation near affected content.

## Empty and first-use states

Library home should show:

- recent stories or assets when available;
- one clear create action;
- one clear import action;
- short explanation of reusable material;
- story scope only when a story exists.

Avoid a dashboard of decorative statistic cards with little action value.

## Expert acceleration

Experienced users benefit from:

- saved search/scope state;
- keyboard focus for search;
- recent items;
- duplicate/export in integrated row clusters;
- multi-select and bulk actions when justified;
- compact density;
- quick switcher or Go To launcher.

These features should not add permanent complexity for new users.
