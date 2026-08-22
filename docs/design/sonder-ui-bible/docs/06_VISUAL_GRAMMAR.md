# 06. Visual Grammar

## Visual model

Sonder uses three visual layers:

1. **Atmospheric content layer**: scene backdrops, story imagery, weather, and the reading field.
2. **Structural chrome layer**: navigation, headers, inspector frames, composer frame, and application surfaces.
3. **Control and feedback layer**: buttons, fields, clusters, focus, status, warnings, progress, and transient overlays.

These layers must remain distinct. Story atmosphere may appear behind the reading stage, but it must not unpredictably recolor navigation, settings, or text-heavy editors.

## Primary visual rules

### Quiet neutral grounds

Most of the interface is composed from carbon, charcoal, and subdued grey. Surface contrast should establish depth before borders or shadows are added.

### Hairline structure

Use one-pixel borders, separators, and accent edges to define structure. Avoid thick frames, double outlines, or decorative corner hardware.

### Deliberate negative space

Negative space must support focus or composition. Large empty black regions without structure are not atmospheric; they look unfinished.

Use negative space to:

- center the reading measure;
- separate navigation from content;
- create calm around a primary action;
- reveal scene imagery;
- allow dense controls to breathe.

Do not use negative space to compensate for missing hierarchy.

### Sparse accent

A region should rarely contain more than one strong cyan element and one amber callout. Accent is a signal, not a background treatment.

### Editorial alignment

Headings, metadata, content, controls, and dividers should share clear vertical and horizontal axes. The interface should look composed before it looks decorated.

### Restrained indexing

Indices such as `01`, `02`, or `FIG. 1` may organize primary destinations, major tools, or substantial content records. They must not appear on every button, label, or setting.

Indexing is appropriate for:

- Play, Library, Settings navigation;
- Story Tools sections;
- major setup routes;
- long Library ledgers;
- diagnostic or technical sequences.

Indexing is inappropriate for:

- ordinary form fields;
- dialog actions;
- short lists where labels are already clear;
- decorative numbering with no navigational value.

## Surface hierarchy

Use four surface levels:

- **Ground**: application background or scene stage.
- **Chrome**: navigation, headers, composer, persistent inspector.
- **Raised**: cards, list selections, menus, temporary panels.
- **Overlay**: dialogs, sheets, tooltips, toasts.

Each level must be visually distinct through tone and border. Do not create depth solely through large blur shadows.

## Glass policy

Sonder uses controlled technical glass, not unrestricted glassmorphism.

Glass may be used for:

- contextual inspector surfaces over atmospheric stages;
- compact floating utilities;
- transient sheets and popovers;
- story turn plates over a backdrop;
- marginal status plates.

Glass should not be used for:

- long text editors;
- dense settings forms;
- authentication forms;
- high-risk confirmation dialogs;
- surfaces over highly animated weather unless blur is disabled;
- surfaces whose readability depends on unknown imagery.

Every glass surface must have:

- a neutral tint;
- sufficient opacity;
- a solid-surface fallback;
- a performance fallback;
- a predictable border;
- no ambient hue shift into application chrome.

## Grid and technical motifs

Subtle grids, index marks, or technical rules may appear only where they organize space. They must remain faint and non-interactive.

The following are prohibited as persistent decoration:

- scanlines;
- animated noise;
- glowing wireframes;
- crosshair corners;
- circuit-board motifs;
- dense measurement ticks;
- artificial terminal text.

## Depth

Depth is created in this order:

1. tone;
2. border;
3. subtle inner highlight;
4. restrained shadow;
5. blur only where necessary.

Large floating shadows and pronounced elevation should be reserved for modal overlays or temporary surfaces that must separate from the application.

## Composition test

A conforming screen should still read clearly when:

- all accent colors are temporarily desaturated;
- all shadows are disabled;
- the scene backdrop is removed;
- labels become 30 percent longer.

If hierarchy collapses under those conditions, the composition is relying on decoration rather than structure.
