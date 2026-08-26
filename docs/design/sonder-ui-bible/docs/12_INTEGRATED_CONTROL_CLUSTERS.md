# 12. Integrated Control Clusters

## Principle

The workbench integrates controls that form one object and leaves quiet actions
bare when a frame would add noise. Clustering is structural, not decorative.

## Top-shelf cluster

Scene, Library, and Settings form one connected control with:

- one outer material frame;
- centered labels;
- shared internal hairlines;
- 4 px outer corners only;
- transparent idle cells;
- low-strength selected tint and lower accent edge;
- no gaps, individual card borders, icons, or numbers.

## Module tab cluster

When a shelf contains multiple modules:

- its 30 px bar becomes a tab strip;
- each tab is both selector and drag surface;
- tabs reorder naturally as the pointer crosses their midpoints;
- an insertion caret and animated neighboring tabs show the exact order;
- dropping on another title/tab strip joins that group;
- the action menu remains at the trailing edge.

One-module shelves use the same bar as a title, not a separate tab style.

## Composer cluster

The composer is one fixed-measure material object containing the input region
and Continue/Send/Stop cell. Shared edges are internal and square. Toolbar
collapse must not change its width.

## Parameter controls

Theme rows use a label, tabular output, and a two-pixel track. Their sliders
share one grid and use narrow handles. Color role swatches form a six-cell
strip. Ambient-light controls form one compact diagrammatic instrument.

## Bare controls

Use unframed controls when the symbol and location already explain the task:

- Characters portrait `−` and `+`;
- toolbar reveal labels at the canvas edge;
- unobtrusive Widget Shelf `+` triggers;
- splitter cues.

The hit region remains large enough even when visible chrome is minimal.

## Menus and alternatives

Each module action menu provides equivalent non-drag commands:

- Move left;
- Move right;
- Merge as tab;
- Separate tab;
- Float;
- Return to Widget Shelf.

Commands that cannot succeed at current shelf capacity are disabled with a
plain explanation.

## Cluster limits

- Never wrap the top shelf or a module tab strip into two rows.
- Overflow tabs use a compact overflow mechanism while preserving order.
- Do not group unrelated actions merely to reduce gaps.
- Destructive data actions do not belong in module-placement clusters.
- State changes never alter cluster dimensions.
