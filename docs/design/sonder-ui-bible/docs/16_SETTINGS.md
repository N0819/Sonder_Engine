# 16. Settings

## Purpose

Settings makes a complex engine configurable without placing every system on
the Scene canvas. It is a full workspace and the canonical home of detachable
configuration modules.

## Categories

- **Presentation**: canvas, Custom Theme, reading, interface scale, sound,
  motion/effects, language, and accessibility.
- **AI Connections**: providers, credentials, models, connection tests, and
  generation defaults.
- **Content**: content preferences, data handling, export, and deletion.
- **Add-ons**: extensions, permissions, state, and extension settings.
- **Maintenance**: updates, storage, backups, logs, repair, and rebuild.
- **Advanced**: prompts, raw parameters, diagnostics, experiments, and
  developer-facing controls.

Presentation is intentionally in Settings. It does not become a top-shelf
destination. Frequent access is solved by docking Custom Theme or another
eligible subsection.

## Workspace composition

Settings uses one compact searchable category/section navigator and one focused
detail workspace. It may use a single ledger, in-page anchors, or staged
overview/detail based on width; it must not recreate the old rail plus card
dashboard or expose a second Settings taxonomy.

## Detachable sections

An eligible section bar may be dragged or moved to a toolbar, tab group, or
floating layer. Its source then becomes `Locate in Workbench`. Full category
navigation, dangerous operations, and long editors remain in Settings.

One live module rule applies. Docking AI Connections or Custom Theme does not
create a second editor with independent save state.

## Custom Theme

Custom Theme exposes:

- six role swatches: Canvas ink, Glass panel, Control chrome, Ambient accent,
  Interface text, Source accent;
- Glass Density 0-100%, default 20%;
- Bar Opacity 0-100%, default 60%;
- Selected Strength 0-100%, default 6%;
- Frost Level 0-100%, default 50%;
- Ambient Light X/Y, radius, and intensity;
- canvas library and gradient authoring;
- Reset and save/preset actions.

All values update the live workbench preview immediately. Invalid palettes do
not replace the last valid applied palette. Save and reset ownership remains in
Settings even when the module is docked.

## Ambient-light instrument

The control depicts the screen with simple crosshairs. A diamond moves the
light source. Two concentric controls adjust size and intensity. Pointer,
keyboard arrows, Home/End, numeric values, and screen-reader labels provide
equivalent operation.

## Color picker

The picker is compact, frosted, and built from the same material. It provides
saturation/value, hue, swatch, hex, RGB, and eyedropper when available. It must
fit inside a docked Custom Theme module without overflowing the viewport.

## AI Connections

The compact module may show route health, selected models, and latency. Secret
entry, provider creation, and complex role mapping open the full Settings
workspace. Connection failures use plain language and retain safe input.

## Saving

- Presentation preview applies immediately and persists only after a valid
  theme update according to the implementation contract.
- Credentials require explicit Save/Connect.
- Long prompts retain drafts.
- Structural, expensive, destructive, or security-sensitive changes require
  explicit action.
- Leaving invalid unsaved work prompts the user.

## Dangerous operations

Delete, reset, repair, rebuild, and clear actions name the affected data,
reversibility, and consequence. They never appear in a draggable module merely
because the source section is detachable.
