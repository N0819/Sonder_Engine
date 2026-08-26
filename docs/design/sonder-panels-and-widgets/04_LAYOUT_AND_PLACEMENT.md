# 04. Layout and Placement

## Purpose

A Panel layout defines the compatible places where Widgets may live. It is
neither a generic IDE docking tree nor a fixed product destination. Templates
give users a legible starting geometry; direct manipulation and explicit
commands let them adapt it.

## Layout vocabulary

### Template

The initial structural arrangement selected when a Panel is created or reset.
A template supplies zones, slots, spans, and responsive behavior.

### Zone

A named layout region with a behavior contract, such as a left toolbar, right
toolbar, reading stage, bottom composer strip, or regular column grid.

### Slot

One placement allocation inside a zone. A slot contains one Widget or one
Widget stack.

### Stack

Two or more compatible Widget instances sharing one slot through tabs or an
equivalent single-visible selection model.

### Floating Widget

A Widget placed above the Panel's structured zones. Floating is bounded to the
Panel workspace, constrained to the viewport, and never the only way to use a
capability.

## Starter layout families

The first creation design will select exact names, thumbnails, and defaults.
The architecture supports at least these families.

### Story stage

A fixed reading stage and composer surrounded by optional left and right
toolbars. This carries forward the calibrated atmospheric workbench and is the
natural shipped Scene default.

The reading measure remains stable when either toolbar collapses. Toolbars may
contain vertically arranged slots and Widget stacks.

### Regular columns

A uniform content grid with a user-selected column count. The intended range is
two through six columns when viewport width and minimum Widget sizes permit.
Widgets span one or more columns and rows.

Selecting six columns creates a finer placement grid; it does not require six
simultaneously visible Widgets.

### Focused workspace

One dominant content allocation plus smaller supporting allocations. This is
useful for Library authoring, raw story data, Prompt Editor, Memory Browser, or
other substantial surfaces that need more than a narrow toolbar.

These families share one slot, compatibility, persistence, and placement
model. A later layout family must not introduce a parallel Widget runtime.

## Template responsibilities

A template defines:

- zone identities and geometry;
- default slots and spans;
- which zones may grow;
- which zones may collapse or overlay;
- supported stacking behavior;
- reading/composer invariants where present;
- automatic-placement preference order;
- compact and narrow-screen adaptation;
- capacity rules.

A template does not restrict Widgets by product category. Compatibility is
based on dimensions and behavior. A Settings Widget may live beside Transcript
when its manifest and the chosen slot allow it.

## Widget compatibility

Placement evaluates both Widget and slot metadata:

- minimum and preferred dimensions;
- supported zone types;
- resize axes;
- stackability;
- toolbar suitability;
- whether a fixed reading or composer region is required;
- whether floating is allowed;
- whether another instance is permitted;
- responsive minimums.

An incompatible target does not activate. A constrained target explains the
requirement in plain language, for example:

> Provider Credentials needs a space at least two columns wide.

## Automatic placement

`Add` uses deterministic, least-disruptive placement:

1. use an empty compatible slot matching preferred size;
2. use another empty compatible slot with sufficient minimum size;
3. add to a compatible stack only when the definition permits it;
4. grow a flexible grid within the template's declared capacity;
5. otherwise keep the Panel unchanged and offer Choose placement.

Automatic placement does not silently move, resize, collapse, or remove
existing Widgets merely to make room.

## Explicit placement

Choose placement exposes only real compatible targets. The preview shows the
exact resulting span, stack, shelf, or floating bounds before confirmation.

Pointer flow:

- the Widget proxy remains attached to the pointer;
- insertion targets are generous and noncompeting;
- target ownership remains stable while crossing neighboring regions;
- invalid release restores the exact origin.

Keyboard/touch flow:

- enter placement through Add, Choose placement, or a Widget action;
- move among named compatible targets;
- announce destination, order, and size;
- confirm explicitly;
- Escape or Back cancels and restores origin.

## Moving and resizing

Moving a Widget changes its Panel placement only. Resize controls respect the
Widget's declared axes and minimums. Splitters expose a visible one-pixel cue
inside a larger pointer/touch/keyboard region.

When a resize would violate a neighboring Widget's minimum, the boundary stops
and explains the constraint. The system never creates hidden overflow that
makes controls unreachable.

## Stacks and tabs

A stack contains compatible peers in one slot. The active Widget is explicit
and persisted. Tabs reorder through midpoint insertion with a live preview.
Separating a Widget requires another valid target; at capacity the stack
remains intact.

Stacking is presentation. Each Widget instance keeps its own configuration and
runtime owner.

## Replace

Replace opens the Widget Catalog filtered to Widgets compatible with the
current slot. The outgoing Widget remains present until the replacement is
successfully placed.

Replacement preserves the slot geometry but does not transfer incompatible
Widget configuration. Undo restores the outgoing instance and its exact
configuration.

## Remove

Remove from Panel deletes the Widget instance from that Panel layout after a
recoverable confirmation where appropriate. It never deletes source data or
the registered Widget definition.

Removal offers Undo. An invalid drag is never interpreted as removal.

## Edit transactions and Undo

Each direct layout change is one transaction containing the before and after
Panel envelopes. A successful change saves atomically and offers Undo for a
bounded period.

Undo is scoped to the exact Panel revision. It does not overwrite a later
layout edit. When an intervening edit makes the receipt stale, the stale Undo
is removed rather than replayed over newer state.

## Capacity and overflow

Capacity is determined by usable geometry and Widget minimums, not an arbitrary
Widget count. When a viewport cannot express the saved arrangement, responsive
staging preserves every Widget through overlay, stack, scroll, or recovery
presentation. No Widget is silently discarded.

## Remaining layout-design tranche

The architecture is fixed, but the following product details require their own
focused design before implementation:

- exact starter-template set and names;
- Panel creation sequence and template preview treatment;
- initial column-count choices by viewport;
- whether users may convert an existing Panel between template families;
- the default automatic-placement preference within each template;
- precise floating bounds and overlap rules;
- whether a freeform layout is ever justified.

