# 20. Content and Terminology

## Voice

Sonder speaks calmly, directly, and compactly. Use concrete verbs, sentence
case, and plain consequences. Avoid corporate filler, theatrical computer
language, jokes, exclamation marks, and raw implementation terms.

## Canonical names

- Scene
- Library
- Settings
- Characters
- Personas
- Lore
- Custom Theme
- Scene Effects
- AI Connections
- Widget Shelf
- left toolbar / right toolbar
- shelf
- tab group
- floating module
- canvas
- Full Atmospheric
- Deep Current
- Glass Density
- Bar Opacity
- Selected Strength
- Frost Level
- Ambient Light

`Play` is retired as the visible primary-workspace label. It may remain an
internal route or historical term until implementation migration completes.
`Inspector`, `rail`, `pane mode`, and `Story Tools Rail` are not names for the
new modular toolbars.

## Edge controls

The calibrated visible labels are `Open Toolbar LFT` and `Open Toolbar RGT`.
Accessible names and help text spell out `Open left toolbar` and `Open right
toolbar`. If later user testing replaces the visible abbreviations, it requires
one coherent pair rather than local variants.

## Module actions

Use result-oriented labels:

- Move to left toolbar;
- Move to right toolbar;
- Merge as tab;
- Separate into shelf;
- Float;
- Return to Widget Shelf;
- Locate in Workbench;
- Add to Workbench.

Do not use `Float target`, `dock zone 03`, `detach instance`, or other
implementation-facing wording.

## Story actions

Use `Open in Scene`, `Continue`, `Send`, `Stop`, `Edit`, `Reroll`, and
`Versions`. Use `Create Story`, `Save Character`, `Test Connection`, and other
verb-object forms when context is not obvious.

## Errors

An error states:

1. what failed;
2. why when known;
3. what the user can do;
4. whether their work and arrangement were preserved.

Example:

> Personas could not move to the right toolbar because all shelf spaces are in
> use. Merge it as a tab or return another module to the Widget Shelf.

## Localization

- Translate complete strings, never fragments.
- Allow at least 30% label expansion.
- Keep labels separate from technical values.
- Preserve user-authored names and story prose.
- Do not rely on English-only numeric prefixes for orientation.
- Visible `LFT`/`RGT` labels require localized equivalents or may be replaced by
  compact directional labels while accessible names remain explicit.
