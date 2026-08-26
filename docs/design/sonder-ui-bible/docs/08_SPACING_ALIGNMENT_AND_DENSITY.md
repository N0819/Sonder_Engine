# 08. Spacing, Alignment, and Density

## Density doctrine

The default workbench is compact. It is designed for modern high-resolution
displays rather than enlarged desktop controls. Accessibility and touch modes
increase targets deliberately; there is no visually spacious default mode that
changes the product's character.

## Spacing scale

| Token | Value |
|---|---:|
| `space-0` | 0 px |
| `space-1` | 2 px |
| `space-2` | 4 px |
| `space-3` | 6 px |
| `space-4` | 8 px |
| `space-5` | 10 px |
| `space-6` | 12 px |
| `space-7` | 16 px |
| `space-8` | 20 px |
| `space-9` | 24 px |
| `space-10` | 32 px |

Use 2, 4, 6, 8, and 12 px most often. Large empty areas belong to the canvas
and reading composition, not to padding inside controls.

## Canonical dimensions

| Element | Reference |
|---|---:|
| Top shelf | 40 px |
| Module/title/tab bar | 30 px |
| Desktop compact control | 24-30 px |
| Composer minimum height | 56 px |
| Default toolbar width | `min(286px, 18vw)` |
| Toolbar resize range | 200-420 px |
| Reading width | `clamp(320px, 43vw, 680px)` |
| Story prose measure | 650-680 px |
| Touch target | 44 px minimum hit region |

## Stable center

The transcript and composer are centered to their own reading token. Opening
or closing a toolbar must not stretch their measure. Prose must not rewrap when
toolbars animate, and the Continue/Send cell must not grow into abandoned dock
space.

## Toolbar shelves

Usable dock height determines shelf capacity:

```text
capacity = clamp(floor((usableDockHeight + 20) / 420), 2, 4)
```

Two shelves are available at ordinary heights, three when each can retain a
usable body, and four on very tall displays such as 2160 px. Tab count never
consumes additional shelf capacity. Full docks do not advertise impossible
new-shelf targets.

## Character roster scale

Characters provide five steps:

| Step | Portrait | Row | Visible secondary content |
|---|---:|---:|---|
| Compact names | none | 28 px | names only |
| Standard | 47 px | 52 px | name, location, state |
| Medium | 72 px | 78 px | name, location, state |
| Large | 96 px | 102 px | name, location, state |
| Portrait | 141 px | 147 px | name, location, state |

Portraits occupy approximately 90% of row height. Borderless minus and plus
controls sit at the bottom-right of the Characters module.

## Alignment

- Top-shelf titles are centered within equal conceptual cells.
- Module titles, tabs, trailing metadata, and action menus share one baseline.
- Fields use fixed value/output columns where repeated.
- Tabs reorder without changing bar height.
- Splitter hit regions may be larger than their visible one-pixel cue.
- Drag previews align to the actual destination, not an offset proxy.

## Responsive density

Remove secondary metadata before reducing core text. Increase hit regions for
touch without inflating visible chrome. Short height reduces available shelves,
never transcript/composer usability.
