# 08. Spacing, Alignment, and Density

## Spacing scale

All spacing should come from this scale unless a documented optical correction is required:

| Token | Value |
|---|---:|
| `space-0` | 0 px |
| `space-1` | 2 px |
| `space-2` | 4 px |
| `space-3` | 6 px |
| `space-4` | 8 px |
| `space-5` | 12 px |
| `space-6` | 16 px |
| `space-7` | 20 px |
| `space-8` | 24 px |
| `space-9` | 32 px |
| `space-10` | 40 px |
| `space-11` | 48 px |

Use 6 px and 12 px deliberately; they help Sonder remain compact without becoming cramped.

## Density modes

Sonder supports two presentation densities:

- **Comfortable**: default for new users and touch devices.
- **Compact**: optional on desktop for experienced users and dense management surfaces.

Compact mode must reduce padding and nonessential metadata spacing. It must not reduce hit targets below the desktop minimum, hide labels required for understanding, or change feature availability.

## Control heights

| Control | Desktop comfortable | Desktop compact | Touch/mobile |
|---|---:|---:|---:|
| Small inline control | 30 px | 28 px | 44 px |
| Default button/input | 36 px | 32 px | 44 px |
| Prominent action | 40 px | 36 px | 48 px |
| Icon button | 32-36 px | 28-32 px | 44 px |
| Navigation row | 40-44 px | 36-40 px | 48 px |

Equivalent controls in one region must have exactly the same height.

## Panel padding

- Compact panel: 12 px.
- Default panel: 16 px.
- Spacious reading/setup panel: 20-24 px.
- Mobile edge padding: 16 px default, 12 px only at very narrow widths.

Do not mix 9, 13, 17, and 19 px padding values across peer components.

## Alignment axes

Every screen should establish clear axes for:

- left edge of headings;
- left edge of body content;
- start of field labels;
- start of field controls;
- trailing actions;
- icon centers;
- dividers;
- reading measure.

Controls that appear to belong to one row must share a common vertical center or text baseline.

## Baseline rules

- Icon and label combinations use an explicit icon box and a shared line-height.
- Text buttons align labels optically, not through arbitrary top padding.
- Monospace indices align to the cap-height of adjacent labels.
- Badges align to the text baseline or vertical center consistently; they must not float a few pixels high.
- Chevrons and trailing icons occupy a fixed trailing column.
- Form help text starts on the same horizontal axis as the control, not the label unless the layout explicitly uses stacked fields.

## Optical tolerance

During polish review:

- peer control heights should differ by 0 px;
- icon centers should differ by no more than 1 px optically;
- text baselines in a row should differ by no more than 1 px;
- repeated left and right insets should differ by no more than 1 px;
- border thickness should not change across states;
- state changes should not shift layout.

## Icon spacing

- Icon to short label: 6 px.
- Icon to long label: 8 px.
- Icon-only controls: center within a fixed square box.
- Leading icons in lists: fixed 20 or 24 px column.
- Trailing actions: fixed-width action region or integrated cluster.

Never let individual SVG view boxes determine layout spacing.

## List and ledger rhythm

A list row should use:

- fixed or minimum row height;
- predictable leading icon/index column;
- flexible main text column;
- optional metadata column;
- fixed trailing action region.

Long labels may wrap to a second line. When they do, the action region remains aligned and the row grows deliberately. Do not allow labels to collide with actions or force controls into irregular narrow columns.

## Negative space

Negative space should be structured. When content is short:

- maintain the reading column;
- use a subtle stage treatment or contextual empty state;
- keep the composer anchored;
- avoid centering small fragments in an enormous undifferentiated black field.

## Responsive density

Density changes at breakpoints must be semantic:

- reduce simultaneous columns;
- move secondary actions to overflow;
- increase touch height;
- preserve content padding;
- remove nonessential metadata before shrinking text;
- avoid horizontal compression that produces misalignment.
