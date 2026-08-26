# 07. Widget Inventory

## Review basis

This inventory combines:

- front-facing engine surfaces reviewed from Main at
  `0c3f779935e329753c449a1910dd738cca4fb721`;
- the Settings hierarchy reviewed from Interface at
  `42294868812791fd9eee523ddbc47ce3af0d15bb`;
- dynamic extension surfaces registered at runtime.

Settings names and groups follow
[`SETTINGS_NAVIGATION_GROUPS`](../../../static/js/ui-next/settings-overview.js).
Main actions such as import, export, delete, confirm, and generate remain actions
inside their owning Widget unless they have enough durable state and independent
purpose to become a Widget themselves.

This is the catalog inventory. Runtime owner, minimum geometry, multiplicity,
safe draft behavior, and individual design/disposition are audited in the
[Widget Design Workbook](10_WIDGET_DESIGN_WORKBOOK.md).

## Granularity rules

A surface is a Widget candidate when it:

- provides a durable view or control surface rather than a momentary command;
- can identify one real runtime/data owner;
- can define meaningful minimum geometry;
- has a useful loading, empty, and error state;
- can survive Panel switching or unmount without losing work;
- is understandable when discovered independently in the Widget Catalog.

A composite Widget may contain smaller eligible Widgets without copying server
truth. For example, a Settings group Widget may navigate its member panels,
while an individual Settings panel Widget opens directly to one member. Draft
and save ownership must remain shared and explicit.

## Story Widgets

These Widgets follow the active story unless noted otherwise.

| Widget | Context | Purpose |
|---|---|---|
| Transcript | Active story/frame | Read story turns and current narration. |
| Composer | Active story/frame | Write, continue, send, and stop story input. |
| Story and Frame Context | Active story | Show current story and frame identity without becoming a second story picker. |
| Turn Progress | Active story/run | Show friendly generation phase, elapsed state, stop/retry where owned. |
| Live Technical Detail | Active story/run | Show bounded live internal-stage detail. |
| Turn Inspector | Selected turn | Inspect saved pipeline stages, lenses, specialists, and rerun/edit operations. |
| Turn Versions | Selected turn | Navigate rerolls, variants, branching, and turn mutations. |
| Player Condition | Active story | Show player bodily condition and vitals. |
| Cast Condition | Active story | Show tracked participant conditions. |
| Room Ambience | Active story/location | Control current room ambience and playback. |
| Scene Backdrop | Active story/location | Show and control current visual backdrop/presentation. |
| Background Work | Global/runtime | Show owned tasks, long work, and activity without becoming technical telemetry by default. |

## Library and Authoring Widgets

| Widget | Context | Purpose |
|---|---|---|
| Library | Global with optional active-story filter | Search, filter, sort, and manage Stories, Characters, Personas, and Lore. |
| Stories | Global | Focus the Library projection on Stories and lifecycle actions. |
| Characters (Library) | Global with associations | Show every reusable Character and its story associations. |
| Characters (Story) | Active story | Show Characters attached to the active story and resolve story-specific overrides. |
| Personas (Library) | Global with associations | Show reusable Personas and their story/player associations. |
| Personas (Story) | Active story | Show primary and additional Personas attached to the active story. |
| Lore (Library) | Global with associations | Show reusable Lorebooks and their story associations. |
| Lorebooks (Story) | Active story | Show canon, attached, disabled, and story-owned Lorebooks for the active story. |
| New Story | Global workflow | Create a story through quick start or authored setup. |
| Character Card | Selected Character | Edit a reusable Character document. |
| Story Character Card | Selected active-story Character | Edit the story-specific Character override while preserving the reusable source. |
| Persona Card | Selected Persona | Edit a reusable Persona document. |
| Greetings and Quick Start | Selected Character | Author greetings and launch Character quick start. |
| Lore Entry Tree | Selected Lorebook | Browse Lore entries and hierarchy. |
| Lore Entry Editor | Selected Lore entry | Author the selected Lore entry. |
| Lorebook Details | Selected Lorebook | Edit book metadata and scope. |
| Lore Relationships | Selected Lorebook/entry | Inspect and edit Lore relationships. |
| Lore Generator | Selected Lorebook | Plan, preview, generate, and apply Lore entries. |
| Lived-in Location Builder | Selected story/Character/Lore context | Prepare a lived location through the one current engine operation. |

## Story-System Widgets

| Widget | Context | Purpose |
|---|---|---|
| Cast | Active story | Manage participants, state, positions, colors, activation, and story-card access. |
| Background Presences | Active story | Inspect and promote unsheeted recurring presences. |
| World State | Active story/frame | Inspect structured world state; edit only through specialized typed owners. |
| Attire | Active story/frame | Inspect and edit participant clothing and state. |
| Genre and Style | Active story | Configure story language, genre, tone, authority, weather, condition visibility, and author guidance. |
| Dialogue and Agency | Active story | Configure autonomy, initiative, NPC exchange, silence, and prose pacing. |
| Off-screen Life | Active story | Set the simulation ceiling and paid off-screen actor limits. |
| Living World | Active story | Configure clocks, aftermath, consequences, obligations, and related ceilings. |
| Institutions and Charter | Active story | Configure lived-town generation and inspect story institutions. |
| Institution Diagnostics | Active story/institution | Inspect Charter histories, state, and diagnostics. |
| Background Life / Scene Life | Active story | Configure managed background activity, reactors, and promotion threshold. |
| Character Relationships | Selected active-story Character | Inspect relationship evidence and projections. |
| Memory Browser | Selected active-story Character | Search, filter, add, edit, archive, import/export, consolidate, and repair memories. |
| Character Private History | Selected active-story Character | Inspect and author story-qualified private history. |
| Persona Private History | Active story's primary Persona | Inspect and author the primary Persona private-history override. |
| Dramatic Irony | Active story | Inspect non-witnessed character-held information across minds. |
| Promise Ledger | Active story | Inspect subjective promise memories chronologically. |
| Multiplayer and Guest Invites | Active story | Manage additional Personas, invitations, and guest state. |
| Frames | Active story | Create and manage diegetic eras and continuity. |
| Who's Where | Active story | Station attached Personas in frames. |
| Time Paradox and Fixed Points | Active story | Configure paradox resolution and inspect fixed points. |

## Settings Group Widgets

Settings group Widgets are global composite entry points. They preserve the
Interface hierarchy while making each group placeable.

| Widget | Member panels |
|---|---|
| Account and access | Provider credentials |
| AI and models | Model assignments |
| Appearance and accessibility | Theme; Reading & layout; Sound & motion; Accessibility |
| Story defaults and content | Content |
| Data, extensions, and maintenance | Add-ons; Maintenance |
| Advanced | Prompt editor; Raw story data |

## Settings Panel Widgets

These eleven identities follow the current Interface navigation registry.

| Group | Widget | Content owned by the panel |
|---|---|---|
| Account and access | Provider credentials | Connections and credentials, default model, memory-search model, response limit, conditional OpenRouter routing, scene backdrops, room ambience. |
| AI and models | Model assignments | Role assignments, provider/model selection, reasoning/sampling controls, and backup assignments. |
| Appearance and accessibility | Theme | Curated themes and Custom Theme authoring. |
| Appearance and accessibility | Reading & layout | Story text, interface density, and visual-effects presentation. |
| Appearance and accessibility | Sound & motion | Story sound, turn notifications, motion, and interface language. |
| Appearance and accessibility | Accessibility | Visual, reading, motion, and control accommodations plus Reset Experience. |
| Story defaults and content | Content | Content permissions, underneath descriptions, recurring-extra promotion, affect habituation, narrator voice examples, and Living World controls. |
| Data, extensions, and maintenance | Add-ons | Installed extensions, permissions, status, updates, extension settings, safe-mode/failure states, and extension installation. |
| Data, extensions, and maintenance | Maintenance | Sonder updates, checkpoint storage, memory-search repair, diagnostics, and host session. |
| Advanced | Prompt editor | Prompt preset and prompt-sheet authoring. |
| Advanced | Raw story data | Raw current-story data plus the raw clothing-data variant. |

## Eligible Settings Subwidgets

The following contained instruments are independently useful and should be
audited for direct Widget registration rather than being reachable only through
their parent Settings panel:

- Connections and credentials;
- Default model;
- Memory-search model;
- Response limit;
- OpenRouter routing;
- Scene backdrops;
- Room ambience;
- Custom Theme;
- Story reading and layout;
- Story sound;
- Accessibility controls;
- Content preferences;
- Narrator voice examples;
- Living World controls;
- Installed extensions;
- Install extension;
- Sonder updates;
- Checkpoint storage;
- Memory-search repair;
- Diagnostics;
- Host session;
- Prompt preset/editor;
- Raw clothing data.

Subwidget registration does not authorize a second independent draft or save
owner. Parent and child projections must coordinate through the same runtime
service.

## Extension Widgets

Extensions contribute definitions dynamically rather than receiving fixed
hard-coded catalog entries.

Initial supported shapes include:

- compact/sidebar-style Widget;
- substantial full-workspace Widget;
- Settings Widget or settings contribution;
- Turn Inspector renderer embedded in the owning Turn Inspector rather than
  advertised as an unrelated top-level Widget.

Examples from the reviewed bundled extension surface include Cohesion,
Campaign, and Story Frame. Installed/enablement state determines availability.

## Not standalone Widgets by default

These remain infrastructure or actions unless later evidence establishes a
durable independent surface:

- confirmation dialogs;
- login and guest-join gates;
- toasts and notices;
- import/export confirmation steps;
- destructive confirmation;
- single generate, reroll, delete, rename, or archive buttons;
- extension step renderers already contained by Turn Inspector;
- transient drag previews and placement targets.
