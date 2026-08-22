# 11. Iconography

## Principle

Sonder uses an original, genre-neutral technical SVG family. Icons should feel related through geometry and stroke, not through overt science-fiction motifs.

## Construction grids

Supported grids:

- 16 px for dense secondary actions;
- 20 px for default interface actions;
- 24 px for navigation and prominent actions.

Icons must be authored on the intended grid and tested at actual display size. Scaling a 24 px icon down to 16 px is not an acceptable substitute for a 16 px drawing when the result becomes muddy.

## Stroke and shape

- Default 20 px stroke: approximately 1.5 px.
- Default 24 px stroke: approximately 1.75 px.
- Use round or lightly softened joins and caps where they improve clarity.
- Avoid hairline 1 px strokes for core actions.
- Avoid heavy 2.5-3 px strokes except filled or alert symbols.
- Use filled regions selectively for active, recording, stop, warning, or destructive states.

## Color

Icons use `currentColor` by default. Semantic color comes from the component state, not hard-coded SVG values.

Multicolor icons are prohibited in ordinary controls. Illustrative empty-state graphics may use multiple semantic tones but remain restrained.

## Optical box

Every icon component provides:

- a fixed square layout box;
- a fixed SVG view box;
- explicit inline/block size;
- `display: block` inside the box;
- optical centering adjustments when the visual mass is asymmetric.

An icon's raw path bounds must not determine button alignment.

## Optical centering

Common corrections:

- play/send triangles shift slightly right;
- chevrons may shift toward the direction of travel;
- pin icons may sit slightly high;
- speaker icons may need horizontal compensation;
- circular arrows must be centered by visible mass, not the circle's mathematical bounds.

Corrections should be recorded per icon, not patched with arbitrary margins in each usage site.

## Labels

Icon-only controls are appropriate when:

- the symbol is globally familiar;
- the action is repeated often;
- a tooltip and accessible name are present;
- the consequence is low risk;
- the control is not the only route to an unfamiliar feature.

Visible labels are required for:

- unfamiliar Sonder-specific concepts;
- destructive or expensive actions;
- onboarding choices;
- primary navigation on mobile unless space is exceptionally constrained;
- actions whose icons are ambiguous in user testing.

## Icon inventory families

### Global and navigation

Play, Library, Settings, Search, Menu, Back, Forward, Close, More, Pin, Unpin, Expand, Collapse.

### Story

Send, Stop, Reroll, Versions, Edit Turn, Continue, Branch, World, Cast, Persona, Lore, Style, Dialogue, Attire, Backdrop, Ambience, Chime, Volume, Mute.

### Library

Story, Character, Persona, Lorebook, Import, Export, Duplicate, Archive, Restore, Delete, Link, Unlink, Used In, Favorite, Recent.

### Settings and system

Appearance, Reading, Language, Accessibility, AI Connection, Model, Key/Credential, Test Connection, Extension, Update, Backup, Storage, Logs, Repair, Prompt, Diagnostics, Experiment.

### Status

Info, Success, Warning, Error, Pending, Saving, Saved, Offline, Locked, Restricted, Loading.

## Forbidden practices

- emoji as primary UI icons;
- platform-dependent text glyphs such as `U+2715 close glyph`, `U+2630 menu glyph`, or `U+27A4 send glyph` where an SVG exists;
- mixing outline and filled styles arbitrarily;
- different stroke weights in one cluster;
- icons without accessible names;
- icons vertically aligned through text baseline hacks;
- unique icons for identical actions in different screens;
- the same icon used for unrelated concepts.

## Review procedure

Every icon set must be reviewed in:

- default and compact density;
- light and dark text tones within curated themes;
- 100 and 200 percent browser zoom;
- touch controls;
- selected, disabled, warning, and destructive states;
- adjacent icon clusters;
- screenshots with actual labels.
