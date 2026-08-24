# Grouped Settings Overview Design

## Status

Approved for the next Settings work package. This overview follows the current
UI6 control-and-theme release; it is not folded into that immutable asset graph.

## Goal

Give Settings a calm, scan-first home that answers two questions before the
user opens a detailed page: where does this setting live, and what is its
current high-level state? Preserve every existing Settings category, deep link,
search result, persistence owner, and engine API.

## Composition

`#/settings` becomes a grouped overview rather than silently opening
Experience. It uses the approved replacement shell and Settings header, then a
single readable ledger without the category rail. Opening any row enters the
existing detailed Settings composition, including its category navigation.
Browser Back returns to the overview with scroll and focus restored.

Each group has a restrained uppercase semantic heading and one bounded row
ledger. A row contains, in order:

1. a reviewed local semantic icon;
2. a plain-language title;
3. an optional concise current-state summary aligned opposite the title; and
4. the local chevron icon.

The full row is one link with one accessible name and at least the current
44 px touch target. Dividers separate rows; there are no nested cards, inline
forms, toggles, accordions, or duplicate action buttons on the overview.

## Information architecture

### Connections

- **AI Connections** → `#/settings/ai-connections`
  - Summary: configured provider count and current default model when already
    present in the bootstrap projection.

### Appearance

- **Theme** → `#/settings/experience?control=themes`
  - Summary: active curated or Custom Theme name.
- **Reading & layout** → `#/settings/experience?control=reading`
  - Summary: current prose size and Comfortable/Compact density.
- **Sound & motion** → `#/settings/experience?control=sound`
  - Summary: Full/Reduced/Off effects and muted/unmuted story sound.
- **Accessibility** → `#/settings/experience?control=accessibility`
  - Summary: Standard, Accessibility Mode, or the count of granular overrides.

### Story & host

- **Content** → `#/settings/content`
  - Summary: story boundaries, narrator voice, and living-world ceilings.
- **Add-ons** → `#/settings/add-ons`
  - Summary: enabled/installed counts only when the owned extension projection
    is already available; otherwise a stable descriptive summary.
- **Maintenance** → `#/settings/maintenance`
  - Summary: updates, storage conversion, memory search, and diagnostics.
- **Story imports & backups** → `#/library/stories`
  - Summary: explicitly says it opens Library, whose story-scoped routes own
    import, portable export, and deletion.

### Advanced

- **Model assignments** → `#/settings/ai-connections?control=models`
- **Prompt editor** → `#/settings/advanced?tool=prompts`
- **Turn details** → the maintained Play/Turn-details route; when no Story is
  open, show `Open a Story first` and do not create a dead navigation target.
- **Raw story data** → `#/settings/advanced?tool=story-data`

Raw clothing data remains available inside Advanced but does not need a peer
overview row; the index is a clean task map, not a dump of every technical
tool.

## Navigation and search

- The global Settings destination and `mod+,` open `#/settings`.
- Existing category and tool URLs remain byte-for-byte compatible.
- Settings search remains in the header on overview and detail pages. Results
  continue to open the exact detailed control, never an overview row.
- Detailed pages gain a quiet **Settings overview** back link before the
  category ledger. It is ordinary navigation, not a second browser history
  implementation.
- Focus restoration uses the existing navigation-state owner. Returning from a
  detailed page focuses the row that launched it and restores overview scroll.

## Summary ownership

Overview summaries are projections only. They may read values already owned by
bootstrap, browser-local appearance/accessibility state, or an existing
Settings service. They may not trigger provider discovery, update checks,
extension mutation, checkpoint conversion, model calls, or new persistence.
Unavailable and loading summaries remain concise and non-blocking. A summary
cannot be the only place a state or warning is exposed.

## Responsive and accessibility contract

- Wide and expansive layouts use one centered ledger with a readable maximum
  measure; they do not become a dashboard grid.
- Compact layouts retain the same group and row order, stack a long summary
  beneath its label when needed, and never horizontally scroll the page.
- Row title, summary, and chevron remain aligned under large-interface,
  high-contrast, Japanese, 200-percent zoom-equivalent, and short-height states.
- Group headings label their ledgers; the current summary is included in each
  row's accessible description without duplicating visible text.
- Focus, hover, pressed, unavailable, and current states use semantic tokens
  and are not communicated by color alone.
- Reduced motion changes no access path and the overview introduces no
  decorative animation.

## Visual boundary

The supplied grouped-settings image is a composition reference for sorting,
row hierarchy, summaries, and restrained separators. Sonder keeps its own
approved shell, typography roles, semantic colors, icon sprite, spacing scale,
and responsive staging. No external source code, assets, branding, or exact
pixel values are copied.

## Verification

- Static contracts hold the overview route, semantic group order, local icon
  use, and unchanged detailed route set.
- Browser tests cover every row target and summary source, direct deep links,
  Settings search, browser Back, scroll/focus restoration, no-Story Turn
  details, and unavailable async summaries.
- Geometry tests cover 1440×900, 1024×768, 390×844, 360×800, 844×390, and a
  200-percent zoom equivalent with zero horizontal overflow and 44 px compact
  targets.
- Deterministic screenshots compare the overview and one detail transition at
  desktop, phone, and short landscape against the approved Sonder reference
  composition and this recorded extension.
