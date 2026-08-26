# 09. Typography

## Canonical font set

Sonder uses exactly three primary families:

- **Geist Sans**: navigation, module titles, controls, forms, Library, Settings,
  and player-facing explanations.
- **Geist Mono**: micro labels, values, status, coordinates, shortcuts, compact
  technical data, and the restrained machine layer.
- **Newsreader**: story title, narration, dialogue, and literary input where it
  belongs to the fiction.

Fallbacks must preserve metrics and role: a modern neutral sans, a restrained
mono, and a readable literary serif. Do not introduce display sci-fi fonts.

## Desktop scale

| Role | Family | Size / line | Weight |
|---|---|---:|---:|
| Micro coordinate/status | Geist Mono | 8-9 / 11-12 px | 400-500 |
| Detail metadata | Geist Mono or Sans | 9-10 / 12-14 px | 400-500 |
| Module tab | Geist Sans | 10 / 14 px | 500 |
| Module title | Geist Sans | 11 / 14 px | 500 |
| Top-shelf navigation | Geist Sans | 12 / 16 px | 500 |
| List name/default control | Geist Sans | 12 / 16 px | 400-500 |
| Local emphasized title | Geist Sans | 13 / 17 px | 400-500 |
| Story title | Newsreader | 12 / 16 px | 500 |
| Story prose | Newsreader | 15 / 1.62 | 400 |
| Exceptional setup heading | Geist Sans | 18-22 / 1.2 | 500-600 |

Ordinary pages must not introduce 26-36 px headings. Destination identity comes
from the top shelf and layout, not marketing-scale type.

## Story settings

Story prose and interface scaling remain independent. The default prose is
15 px at a 650 px measure. User preferences may increase prose size and width
without scaling module chrome. The composer follows the story/interface role of
its content while retaining a 12 px compact placeholder by default.

## Monospace discipline

Geist Mono is a precision layer, not the entire interface. Use it for:

- status and concise state values;
- numeric outputs and slider values;
- shortcuts and coordinates;
- source/system metadata;
- code, models, identifiers, and diagnostics.

Do not use it for Scene/Library/Settings, Characters, Personas, AI Connections,
long descriptions, dialogs, or ordinary form labels merely to appear technical.

## Uppercase

Uppercase is allowed for short state, source, shortcut, and coordinate labels.
Navigation and module titles use title case. Sentences use sentence case.
Tracking stays modest; tiny wide-tracked copy is decorative and nonconforming.

## Indices

Decorative `01`, `02`, `03`, figure numbers, and chapter codes are removed from
ordinary navigation and module bars. Numbers appear only when the underlying
content is ordered or the value itself is meaningful.

## Accessibility

Micro text may not carry essential information alone. Larger Interface remaps
roles as a system, preserves hierarchy, and allows reflow. Touch inputs may use
16 px internally where required to prevent browser zoom without changing the
visible desktop scale.
