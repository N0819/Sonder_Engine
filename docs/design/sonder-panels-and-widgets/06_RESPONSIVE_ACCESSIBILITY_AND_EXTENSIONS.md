# 06. Responsive, Accessibility, and Extensions

## One architecture

Panels, Widgets, and the Widget Catalog retain one mental model across desktop,
tablet, phone, short-height windows, zoom, keyboard, pointer, and touch.
Responsive staging may change placement and density; it may not hide a Widget
capability or replace Panels with unrelated navigation.

## Top shelf

Wide layouts show Sonder identity, Panel tabs, New Panel, current story,
Widgets, and status.

As width contracts:

1. story code and secondary status detail compact;
2. the Panel-tab strip becomes horizontally scrollable or exposes overflow;
3. New Panel and Widgets retain explicit accessible names;
4. visible text may collapse to an icon only where the meaning remains clear;
5. the active Panel remains identifiable without color alone.

The Widgets launcher remains on the trailing side before status. It is not
moved into a hidden Settings destination at small sizes.

## Icons and control labels

The [Icon Source and Usage](11_ICON_SOURCE_AND_USAGE.md) contract applies at
every viewport. Real collection SVGs may replace visible text where the action
is familiar, repeated, low risk, and unambiguous in context. Icon-only controls
retain accessible names, focus-visible treatment, semantic pressed/expanded
state, and focus-accessible explanation where needed.

Primary, ambiguous, destructive, expensive, security-sensitive, and uncommon
actions retain visible text or icon-plus-label treatment. Status uses icon plus
text and never relies on shape, color, animation, or position alone. Touch
targets remain at least 44 px regardless of visible SVG size.

## Catalog responsiveness

### Desktop and wide tablet

- compact catalog is a right-side overlay drawer;
- expanded catalog is a centered near-full-screen browser;
- primary filters remain visible in a fixed header;
- results own one scroll region.

### Portrait tablet and phone

- the drawer becomes a full-height edge sheet or full-screen catalog;
- the expanded browser is full-screen;
- filter tabs may horizontally scroll with a visible selected state;
- secondary utility filters may move into a labeled Filters sheet;
- Visual and Compact remain available when preview size is meaningful.

### Short height and landscape

- reduce preview height and secondary metadata first;
- preserve search, selected category, Add, Close, and placement recovery;
- avoid fixed headers that consume most of the viewport;
- never cover the focused composer without a clear Back/Close path.

## Responsive Panel layouts

A template defines how its zones stage when the viewport cannot express saved
geometry. Valid strategies include:

- collapse a toolbar while preserving its arrangement;
- open a toolbar or zone as an overlay;
- retain a stack and stage its active Widget;
- give the active Widget a focused full-width state;
- allow a bounded internal scroll owner;
- restore the wide arrangement when space returns.

Responsive staging does not rewrite the user's saved wide geometry. No Widget
is silently removed because the current viewport is small.

## Keyboard model

All catalog and layout operations have non-drag routes.

- Panel tabs use standard tab semantics and arrow navigation.
- Panel reorder has explicit Move left/right commands.
- Widget results are reachable in logical result order.
- Add performs deterministic automatic placement.
- Choose placement moves through named compatible targets.
- Widget action menus expose move, resize, stack, separate, replace, and remove
  where supported.
- Splitters resize in announced steps.
- Escape cancels the current transient action and restores the exact origin.

## Focus

- Opening the drawer moves focus to its search or heading according to the
  initiating action.
- Expanded catalog contains focus.
- Placement moves focus to the placement proxy or first compatible target.
- Cancel returns to the originating card/action with filters and result
  position preserved.
- Closing the catalog restores the top-shelf or contextual launcher.
- Replacing or removing a Widget moves focus to a stable nearby control and
  announces the result.

No service stores a DOM node as durable focus identity. Focus restoration uses
stable Panel, Widget, result, and action identifiers.

## Screen readers and announcements

Announce:

- active Panel changes;
- Panel reorder, creation, reset, and deletion;
- active-story changes once, not once per Widget;
- Widget name, context class, size requirement, and current-Panel count in the
  catalog;
- placement targets, order, span, and incompatibility reasons;
- successful add, move, replace, remove, and Undo;
- loading, empty, error, stale, and missing-extension states.

Status must not depend on color, translucency, animation, or spatial position
alone.

## Touch

- actionable hit regions are at least 44 px;
- long-press drag begins only after clear feedback;
- tap Add and Choose placement provide complete alternatives;
- placement targets are large and stable;
- Back cancels the current placement or staged catalog level;
- software keyboard appearance does not hide search, Close, or the active
  composer.

## Motion and material

Background blur and catalog transitions follow the shared Atmospheric Digital
Workbench material. Reduced motion removes structural animation while
preserving state changes and focus movement. Solid surfaces and high contrast
remove transparency or strengthen edges without changing catalog architecture.

Blur is decorative. The expanded catalog must retain sufficient opaque
material and contrast against the worst supported canvas.

## Localization

- labels allow at least 30% expansion;
- complete strings localize, not fragments;
- Panel and Widget user-authored names remain untranslated;
- filter labels may compact but retain explicit accessible names;
- search synonyms are locale-aware;
- truncation never removes the only differentiator between Story and Library
  variants.

## Extension registration

Extensions register Widgets through the same Widget manifest and owner-bound UI
contract as built-ins. A valid extension Widget declares:

- stable owner-qualified type;
- name, description, category, and keywords;
- context and selection requirements;
- size and placement capabilities;
- multiplicity;
- preview provider;
- runtime loader and teardown;
- configuration schema and migrations;
- required permissions.

Extension Widgets appear under Extensions and may also be found by All, search,
Favorites, Recent, On this Panel, and compatibility filters.

## Extension isolation

- Preview rendering receives a bounded, non-secret input projection.
- Catalog browsing does not mount the full extension runtime.
- Extension CSS stays owner-prefixed and mount-contained.
- Disable, failure, or removal tears down listeners, requests, and resources.
- A missing extension leaves a recoverable placeholder with geometry intact.
- Re-enabling a compatible extension restores the Widget instance.
- An extension cannot register a hidden duplicate of a host control or bypass
  placement, focus, or accessibility contracts.

## Performance budgets

The catalog must remain proportional to visible results rather than total live
Widget runtimes. Use bounded metadata, lazy preview loading, preview
virtualization when necessary, request cancellation, and owner-scoped teardown.

Performance qualification should measure:

- first drawer open;
- expanded browser open;
- category switch;
- Visual/Compact switch;
- search latency with the full built-in and extension registry;
- start/cancel/confirm placement;
- active-story refresh with several visible story Widgets;
- compact mobile and 200% zoom behavior.
