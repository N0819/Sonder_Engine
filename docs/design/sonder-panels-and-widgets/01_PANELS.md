# 01. Panels

## Definition

A **Panel** is a global, named, ordered, user-editable workspace tab. It saves
an exact arrangement of Widget instances and layout geometry. It does not save
a copy of story content.

The Android home-screen-page analogy is useful: the page persists while the
applications on it continue to reflect current data. In Sonder, switching the
active story keeps the selected Panel and its geometry while active-story
Widgets refresh in place.

## Top-shelf role

The integrated 40 px top shelf contains, from leading to trailing edge:

1. Sonder identity;
2. a horizontally ordered Panel-tab strip;
3. **New Panel** adjacent to the Panel tabs;
4. current-story identity;
5. the global **Widgets** launcher;
6. concise global status.

Panel tabs replace the fixed Scene, Library, and Settings cells. They are
navigation between saved arrangements, not navigation to separate frontend
products.

When the tab strip exceeds available width, it scrolls or stages an overflow
list without shrinking labels into illegibility. Reordering Panels changes the
global saved order.

## Global ownership

Global means global across stories for the same host profile. Loading another
story does not select another Panel set and does not change Panel order,
layout, or Widget configuration.

This package does not yet claim that Panels synchronize between browsers,
devices, or hosts. Cross-device ownership depends on the selected persistence
backend.

## Strict active-story context

Every story-aware Widget binds to the single active story. There is no
story-picker or pinned-story setting inside a Widget.

On an active-story change:

1. the application publishes one new active-story identity;
2. active-story Widgets invalidate their prior projections;
3. each Widget loads against the same captured story identity;
4. late results from the prior story are rejected;
5. selection-following Widgets resolve a valid selection or clear it;
6. Panel geometry remains unchanged.

This prevents a transcript from showing one story while Cast, World State, or
Attire shows another.

## Shipped default Panels

Sonder ships three default Panel definitions:

- **Scene** — a story-reading and writing composition;
- **Library** — a discovery, association, and authoring composition;
- **Settings** — a configuration and maintenance composition.

These are defaults, not privileged destinations. They use the same storage,
editing, placement, and Widget contracts as a user-created Panel.

Users may:

- rename a default Panel;
- reorder it;
- add, move, resize, stack, or remove its Widgets;
- duplicate it into an ordinary user Panel;
- restore its current shipped default through **Reset Panel to Defaults**.

Reset restores that Panel's shipped name, layout template, Widget instances,
Widget geometry, and default Widget configuration. It never resets story data,
Library records, Settings values, credentials, extension data, or authored
content.

## User-created Panel lifecycle

A user-created Panel supports:

- create;
- name and optional compact identifying mark;
- reorder;
- duplicate;
- edit layout;
- clear Widgets while retaining the Panel;
- delete with explicit confirmation.

A user-created Panel has no shipped reset target. Its recovery operations are
Undo, Duplicate, Clear Widgets, or Delete Panel. The interface must not label
Clear as Reset Defaults.

At least one Panel must remain. Deleting the final Panel is refused or replaced
atomically with the shipped Scene default.

## Panel state layers

Panel behavior separates four layers:

| Layer | Examples | Lifetime |
|---|---|---|
| Panel definition | name, order, template, slots, Widget instances | global persistent |
| Widget configuration | size mode, scope token, filter, active tab | global to the Widget instance |
| Runtime context | active story, active frame, selected record or turn | current application context |
| Content projection | transcript, cast, world state, Settings values | authoritative runtime/server data |

Only the first two layers belong to the saved Panel definition.

## No-story state

With no active story, the active Panel remains intact. Active-story Widgets
stay in their saved locations and show a compact, explicit open-story state.
They do not disappear, collapse neighboring slots, or substitute sample story
data.

Global Widgets remain usable. The Library Widget remains the canonical way to
open or create a story.

## Panel switching

Switching Panels must preserve:

- active story and frame;
- ongoing generation ownership;
- composer draft ownership;
- authoritative server projections;
- transient work that cannot safely be discarded.

Panel switching changes composition, not application truth. A Widget may
unmount visually when absent from the destination Panel, but its owning runtime
service must preserve any work whose lifecycle exceeds the DOM mount.

## Edit mode

Ordinary use and layout editing are distinct states. Opening the Widget Catalog
does not itself mutate or unlock the Panel. Adding, moving, replacing, resizing,
or removing a Widget enters a bounded edit/placement interaction and saves only
after a valid result.

Edit mode exposes slots, insertion rails, compatibility cues, and Widget
actions without turning the whole interface into permanent layout chrome.

## Panel creation boundary

Panel creation will offer layout families such as a story stage with side
toolbars and a regular multi-column grid. The exact starter templates and
creation sequence are intentionally treated as the next design tranche. The
shared contract is fixed now: a template defines initial compatible slots, not
permanent restrictions on which product category a Panel may contain.

