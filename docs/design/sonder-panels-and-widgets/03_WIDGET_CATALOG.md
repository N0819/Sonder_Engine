# 03. Widget Catalog

## Purpose

The **Widget Catalog** is the one discovery, placement, and recovery surface
for all built-in and extension Widgets. It must remain useful both to a new user
who recognizes Widgets visually and to an expert who wants to scan names
quickly.

The catalog replaces the current recovery-oriented Widget Shelf. It does not
replace Library content search or Settings navigation.

## Launcher

The top shelf places a persistent **Widgets** button immediately before global
status on the trailing side:

```text
Sonder | Panel tabs... | New Panel | Active Story | Widgets | Status
```

The launcher uses an icon plus the visible label `Widgets` where width allows.
It never uses a bare plus because the plus adjacent to Panel tabs means **New
Panel**. On narrow screens the label may collapse while the accessible name
remains `Open Widget Catalog`.

The launcher stays available on every Panel and has an active state while
either catalog presentation is open.

## Icon language

Catalog and Widget chrome follow the accepted
[Icon Source and Usage](11_ICON_SOURCE_AND_USAGE.md) contract. Identifying and
action icons come from the local manifest-backed SVG Repo Minimal UI Icons
artifact. The Catalog and placed Widget reuse the same semantic icon mapping;
they do not paste anonymous paths or create separate thumbnail glyphs.

Familiar, repeated, low-risk controls may be icon-only with explicit accessible
names. Primary, ambiguous, destructive, expensive, security-sensitive, and
first-use actions keep visible labels or icon-plus-label treatment. At narrow
widths, visible text collapses only when context keeps the control recognizable
and its accessible name remains intact.

## One catalog, two presentations

The catalog has one result model, filter state, registry, and placement engine.
It renders in two presentations.

### Compact drawer

The default launcher action opens a right-side overlay drawer. The drawer:

- overlays rather than resizes the active Panel;
- keeps its search, primary filters, view toggle, and Expand control fixed;
- owns one internal result scroll region;
- supports Visual and Compact results;
- closes with Escape and restores focus to the launcher;
- preserves the active Panel's layout and reading measure.

### Expanded browser

Expand opens a centered browser using approximately 90-94% of the usable
viewport. It dims and blurs the Panel behind it, contains focus, and gives the
result area enough room for meaningful visual previews.

Its fixed header contains:

- `Widgets` title;
- search;
- Visual/Compact toggle;
- primary category filters;
- Close.

On narrow screens it becomes a full-screen sheet rather than a small modal.

Closing the expanded browser returns to the compact drawer. Closing the drawer
returns focus to the top-shelf launcher.

## Primary taxonomy

Primary filters describe capability ownership, not application destinations:

- **All**
- **Story**
- **Library**
- **Systems**
- **Settings**
- **Extensions**

Each Widget has one stable primary category. Search keywords may cross
categories. Settings results preserve the six Interface Settings group headings
and place the eleven Settings panels underneath them.

Utility filters are visually secondary:

- Favorites;
- Recent;
- On this Panel;
- Fits current layout or slot.

## Search

Catalog search covers Widget name, description, category, common synonyms,
system terms, Settings group, and extension name. It does not search live
story content or Library records.

Searching `character` may find Characters (Story), Character Card,
Relationships, and Memory Browser. Searching a character's authored name must
remain the responsibility of the relevant story or Library Widget.

Search text is session-only and clears when the catalog fully closes. Category,
view mode, favorites, and optional sort preference may persist globally.

## Visual results

Visual mode uses preview cards containing:

- representative, non-interactive miniature;
- Widget name;
- one-line purpose;
- category;
- context label such as `Active story`, `Global`, or `Follows selection`;
- default/minimum shape cue;
- current-Panel count or location;
- Favorite;
- Add and Choose placement actions as applicable.

Previews are lightweight and side-effect free. They do not instantiate the
full live Widget, create duplicate subscriptions, expose credentials, mutate
state, or require a loaded story. A neutral sample is used when current data
would be unsafe or unavailable.

## Compact results

Compact mode is a dense names-first list, not a squeezed card grid. It keeps a
small identifying mark and shows the essential columns:

```text
Widget | Category | Context | Size | On this Panel | Add
```

Descriptions and compatibility details remain available through focus, hover,
or a labeled details disclosure. Settings group headings remain visible.

The selected Visual or Compact preference applies to both the drawer and the
expanded browser unless a later usability test proves that separate
preferences are necessary.

## Placement entry points

The top-shelf launcher is the permanent entry. Contextual controls open the
same catalog with bounded filters:

- empty slot `Add Widget` -> `Fits this slot`;
- Widget `Replace` -> compatible replacements;
- stack `Add tab` -> stack-compatible Widgets;
- toolbar `Add Widget` -> toolbar-compatible Widgets.

Filters applied by context are visible and removable. The catalog never hides
that it is showing a restricted result set.

## Add and choose placement

`Add` performs safe automatic placement in the best compatible open location
and offers Undo.

`Choose placement` or pointer drag starts explicit placement:

1. the expanded browser recedes;
2. background blur clears;
3. compatible slots and insertion targets illuminate;
4. a correctly sized placement proxy follows the pointer or keyboard focus;
5. confirmation saves the layout;
6. cancellation restores the catalog's exact filter and scroll state.

Dragging is never the only route. Keyboard and touch users can select a Widget,
move among compatible targets, confirm, or cancel.

## Availability and context

Active-story Widgets remain discoverable without a loaded story. Their catalog
cards are labeled `Active story`; they are not disabled merely because the
current content context is absent.

The placed Widget shows its no-story state until a story loads. Strict
active-story binding means the catalog never exposes a story picker or pinning
control.

## Counts and duplicates

Results distinguish:

- `Add`;
- `Already on this Panel`;
- `Add another`;
- `On this Panel x2`;
- `Located on another Panel` for an application-singleton definition.

The manifest's multiplicity policy supplies this behavior. The catalog does
not infer it from DOM presence.

## Empty and error states

No-results states name the active filters and offer Clear search or Clear
filters. Registry or preview failure remains inline and does not prevent other
Widgets from loading. Placement failure preserves the source Panel and returns
the user to the catalog with a plain explanation and recovery action.

## Performance boundary

Opening the catalog loads manifest metadata and lightweight previews only.
Full Widget code and live data subscriptions load when the Widget is placed or
when an explicitly supported detailed preview needs them.
