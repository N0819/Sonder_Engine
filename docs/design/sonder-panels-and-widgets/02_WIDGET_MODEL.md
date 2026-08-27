# 02. Widget Model

## Canonical term

**Widget** is the canonical product term for a movable, resizable, stackable,
or otherwise placeable projection of a Sonder capability.

The current Design Bible's **Module** term becomes historical where the two
refer to the same movable surface. Implementation code may retain internal
module names during migration, but player-facing documentation and new
contracts use Widget consistently.

## Definition, instance, and projection

The Widget system separates three identities:

### Widget definition

The registered capability type, such as `story.transcript`,
`library.workspace`, or `settings.theme`.

### Widget instance

One placed occurrence of a Widget definition in one Panel. It owns a stable
instance identifier, layout placement, instance configuration, and local
presentation state.

### Widget projection

The current content rendered by an instance from authoritative application
state. A projection changes when the active story, selected record, server
state, or extension state changes.

Multiple instances of one definition are allowed only when the definition's
multiplicity contract permits them. Each instance remains a single state owner;
two instances never share mutable draft state accidentally.

## Context classes

Every Widget declares one context class.

### Global

Global Widgets do not require an active story. Examples include the full
Library, Provider Credentials, Model Assignments, Add-ons, and Maintenance.

### Active story

Active-story Widgets always resolve against the currently loaded story.
Examples include Transcript, Composer, Cast, World State, Attire, Promise
Ledger, and Frames.

They never persist a story identifier and never expose story pinning.

### Selection following

Selection-following Widgets consume a typed selection published by another
Widget or by the application context. Examples include Character Card, Lore
Entry editor, Relationships, Memory Browser, and Turn Inspector.

A definition declares which selection types it accepts and what it renders
when no compatible selection exists. A selection from a prior story is cleared
when the active story changes.

### Global with contextual filtering

These Widgets query global resources while accepting an active-story filter.
The Library can show all resources, resources associated with the active story,
unassigned resources, or resources used by multiple stories.

The filter is configuration; the resource remains owned by its real global or
story authority.

## Widget registration contract

Each built-in or extension Widget registers one manifest containing at least:

```text
stable type identifier
schema version
localized name and description keys
semantic icon key and manifest-backed provenance entry
category and search keywords
context class and accepted selections
default and minimum dimensions
supported layout zones
collapse, stack, tab, float, and resize capabilities
multiplicity policy
default configuration
preview provider
runtime loader
configuration migration
extension owner when applicable
```

The Widget Catalog, placement engine, Panel persistence, accessibility layer,
and extension teardown all consume this same manifest. There is no parallel
hard-coded catalog inventory.

## Multiplicity

Definitions use one of these policies:

- **Single per Panel** — a second instance would create ambiguous control or
  duplicated draft ownership.
- **Repeatable** — multiple independent instances are useful.
- **Repeatable by configuration** — multiple instances are useful when filters,
  selection channels, or presentation modes differ.
- **Application singleton** — the capability has one movable instance across
  all Panels and another Panel locates or moves it rather than copying it.

The initial inventory records candidate policies, but each policy must be
confirmed against the owning runtime before implementation.

## Data ownership

A Widget is a projection, not a new data store.

- Story mutations continue through current story routes and services.
- Library records and associations retain their current authority.
- Settings save through their existing server- or device-owned boundaries.
- Credentials never enter general Panel or Widget persistence.
- Extension Widgets operate within declared extension permissions.
- A late async response cannot repaint a Widget after its Panel, story,
  selection, or instance owner changes.

Panel persistence may store identifiers and harmless presentation
configuration. It must not serialize authored sheets, world state, prompts,
credentials, transcript content, or model output into the layout envelope.

## Widget chrome

Every placed Widget uses the shared workbench material and a consistent chrome
contract:

- explicit title and the shared collection icon where the presentation role
  calls for a visible identity mark;
- context or state summary when useful;
- title/tab drag surface where direct manipulation is supported;
- Widget action menu;
- clear loading, empty, unavailable, error, and stale states;
- visible focus and non-color-only selection;
- no hidden duplicate controls.

The action menu exposes only operations supported by the current layout and
Widget manifest. Common actions include Move, Resize, Add to stack, Separate,
Float, Replace, Duplicate when allowed, and Remove from Panel.

Removing a Widget changes only the Panel arrangement. It never deletes the
underlying record, story system, Settings value, or extension.

Built-in identity and action icons follow the
[Icon Source and Usage](11_ICON_SOURCE_AND_USAGE.md) contract. The manifest
stores semantic keys rather than anonymous inline paths, so the Catalog,
placed Widget, responsive controls, and accessibility layer consume one
reviewed mapping.

## Presentation state

Widget-local presentation state may include:

- density or portrait scale;
- sort and filter configuration;
- selected subpanel;
- collapsed sections;
- active tab within the Widget;
- safe scroll restoration;
- linkage to a named selection channel.

Drafts and consequential edits remain owned by their real editor/runtime and
use record- or story-qualified ownership. They are not anonymous Widget state.

## Lifecycle and recoverability

A Widget instance may be:

- registered and ready;
- loading;
- ready with content;
- confirmed empty;
- awaiting an active story or selection;
- recoverably errored;
- stale and refreshing;
- unavailable because its extension is disabled;
- unsupported because its saved schema is newer than the host.

Unavailable or unsupported Widgets retain a recoverable placeholder and their
geometry. They do not silently disappear and collapse the Panel.
