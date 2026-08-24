# Settings Controls and Custom Themes Design

**Status:** approved

**Date:** 2026-08-23

**Target branch:** `interface`

## Purpose

Repair the reported Settings and Library polish defects, replace the retired
legacy-theme control with safe user-authored color themes, and add two curated
themes without changing the replacement interface's information architecture
or engine-owned behavior.

The product owner approved this design on 2026-08-23. Modern Slate is amended
to be entirely warm grayscale: it uses no blue or other chromatic accent, and
its interaction color is a subdued warm white.

## Authority and scope

The maintained interface guide, supplied reference screenshots, Design Bible,
current routes and persistence, and approved replacement source remain the
implementation authorities. This specification is the approved change record
for the deliberate additions and refinements below.

In scope:

- Settings search alignment and section rhythm;
- the narrator voice-example editor;
- Add-ons action labels and affordances;
- the Maintenance navigation icon;
- removal of the unsupported Legacy Themes selector;
- two new curated themes and a constrained custom-theme editor;
- cohesive select and button geometry on replacement surfaces;
- focused regression tests, responsive browser renders, release rotation, and
  maintained interface documentation.

Out of scope:

- arbitrary CSS, custom fonts, layout overrides, background images, animation
  authoring, or executable theme payloads;
- redesigning Settings navigation, Library information architecture, or
  extension lifecycle behavior;
- changing backend APIs or engine persistence;
- restoring or supporting legacy themes.

## Confirmed causes

1. The Settings search icon is pinned by a fixed top inset while the input
   height changes by density and viewport. It therefore cannot remain
   vertically centered.
2. Add-ons leaves an empty live-status element with a minimum height and top
   margin after loading. Other sections do not, producing the apparent
   section-to-content spacing change.
3. Narrator examples are emitted as four unstructured textareas with no
   component layout contract, so native sizing creates an irregular wrapping
   arrangement.
4. Add-ons reuses an extension's complete display name, including a terminal
   `(demo)` qualifier, inside lifecycle action labels.
5. Maintenance reuses the generic update symbol instead of a dedicated icon.
6. Settings selects and shared buttons rely too heavily on browser defaults.
   Inconsistent text metrics and baseline layout make controls feel oversized,
   sharp, and visually disconnected from the glass surface language.

## Interaction design

### Settings search and vertical rhythm

The search icon occupies a fixed square inside the input and is centered using
the control's block midpoint, independent of density or responsive height. The
input keeps sufficient leading padding for the icon.

Every Settings section uses the same header-to-first-content rhythm. Empty
status regions collapse completely while retaining their live-region semantics
when populated. Status messages remain adjacent to the group they describe.

### Narrator voice examples

The four stored example slots remain unchanged, but the editor presents one
textarea at a time. A compact tablist above it contains `Example 1` through
`Example 4`; optional slots are identified in supporting text rather than by
changing the stored data shape.

- Selecting a tab swaps the visible draft without discarding unsaved edits in
  any slot.
- Left/Right Arrow, Home, and End navigate the tabs and update selection.
- The active tab exposes `aria-selected`, the textarea is associated with its
  active tab, and the component remains usable in a linear screen-reader flow.
- The existing character limit, four-slot maximum, and save endpoint remain
  authoritative.
- Save submits all four drafts. Empty optional slots remain valid.

### Add-ons

Extension cards keep their full authored title, including `(demo)` when it is
part of that title. Only action labels and action-result copy remove one
case-insensitive terminal `(demo)` qualifier. Other parenthetical text and any
non-terminal use are preserved.

Lifecycle actions receive a subtle 0.5px semantic border so their clickable
bounds are visible without becoming heavy outlined buttons. Existing enabled,
disabled, busy, focus, and error behavior is unchanged.

### Maintenance icon

The supplied `maintenance.svg` wrench becomes a dedicated local sprite symbol
named `icon-maintenance`. Its fill follows `currentColor`; it is used only by
the Maintenance category. The generic update icon remains available for update
actions.

### Select controls

Replacement-surface selects use the shared control system:

- a low 3–4px radius;
- compact 13px typography and restrained weight;
- 36px comfortable and 32px compact desktop heights;
- a minimum 44px touch height at touch breakpoints;
- semantic translucent canvas/surface fill and subtle border;
- a fixed trailing chevron column drawn from theme tokens;
- clear hover, disabled, and `focus-visible` states.

The same contract applies to Settings, Library, and matching replacement
controls. It does not style server-rendered or non-replacement pages globally.

### Buttons

Shared replacement buttons become inline flex containers with centered icons
and labels, a 6px gap, compact 13px text, and restrained emphasis. The existing
control heights and touch-target rules remain. This centers the New Story plus
symbol and removes the oversized/bold appearance from Search, New Story, and
similar actions without weakening hierarchy or accessible names.

## Theme design

### Legacy theme retirement

The Legacy Themes selector and `data-legacy-theme` runtime marker are removed.
On load, an old stored legacy selection is ignored and omitted from the next
saved appearance state. The user's already mapped curated theme remains
selected, so retirement does not unexpectedly recolor an existing interface.

### Curated themes

The existing four curated themes remain. Two more are added to the same theme
selection control and first-paint/runtime allowlists.

#### Neon Circuit

A restrained cyberpunk-inspired palette: carbon and dark-violet surfaces,
cyan interaction, modest violet information, and amber warnings. It uses the
existing component geometry and avoids scanlines, decorative HUD frames,
excessive bloom, and typography changes.

#### Modern Slate

An entirely warm-grayscale palette. Canvas, surfaces, borders, text, focus,
interaction, status, and callout tokens contain no blue or other chromatic
hue. Near-black surfaces lean subtly warm; interaction and focus use subdued
warm white, with stronger warm white for active states. Status distinctions use
labels, icons, markers, and luminance—not color alone.

### Custom theme model

Custom Theme replaces the retired legacy control in Experience. It edits eight
semantic base roles:

1. Background
2. Panel
3. Primary text
4. Muted text
5. Accent
6. Attention
7. Success
8. Danger

The page shows labeled swatches and a compact preview. Clicking a swatch opens
a Design Bible dialog with a native color plane, normalized hexadecimal input,
and Red/Green/Blue integer inputs. All representations stay synchronized.

The dialog previews valid edits immediately. `Save color` commits the role to
the custom-theme draft; `Cancel` restores the value from before the dialog was
opened. The page-level `Use Custom Theme` action validates, persists, and
activates the complete palette. `Reset` restores the shipped custom defaults.

Secondary Import and Export actions use versioned JSON containing only the
eight recognized roles. Import rejects unknown schema versions, missing roles,
extra executable/style fields, malformed colors, and invalid contrast. No CSS
text, custom property names, URLs, markup, or layout data are accepted.

### Derivation and application

A dedicated custom-theme stylesheet maps fixed `--ui-custom-*` base values to
the complete semantic token set. Raised/subtle surfaces, soft interaction
fills, and borders are deterministically derived with CSS color mixing. The
runtime writes only fixed, allowlisted custom properties after normalizing each
value to `#RRGGBB`.

The custom palette is stored in a versioned dedicated local key as well as the
normal appearance envelope. First-paint preflight reads the dedicated value
synchronously, validates its shape and colors, applies only the fixed property
allowlist, and then selects `custom`. Runtime appearance management uses the
same parser and allowlist. Invalid persisted data falls back to shipped custom
defaults and cannot inject a property name or value.

### Validation

The custom theme reports validation next to the preview and disables activation
until all checks pass:

- Primary text against Background and Panel: at least 4.5:1.
- Muted text against Background and Panel: at least 4.5:1.
- Accent/focus against Background and Panel: at least 3:1.
- Attention, Success, and Danger against Background and Panel: at least 3:1;
  any use as normal-sized text must independently meet 4.5:1.
- Background and Panel must remain visibly distinguishable.

Invalid field edits remain local to the open dialog and never replace the last
persisted valid theme. Error text identifies the role and failed relationship;
color is never the sole error signal.

## Responsive and accessibility contract

- Tabs and swatches wrap into deliberate rows without horizontal page scroll.
- The color dialog uses the standard centered desktop composition and the
  established mobile sheet behavior.
- All interactive controls retain visible keyboard focus, accessible names,
  and 44px touch targets where the interface touch contract requires them.
- Tab selection, color validation, saved state, and extension busy/disabled
  state are not communicated by color alone.
- Reduced motion remains respected; theme changes require no animation.

## Persistence and compatibility

The existing appearance state gains only recognized theme identifiers and a
validated custom palette. Migration removes `legacyTheme`, preserves the
current curated `theme`, and treats an unknown theme identifier as the existing
safe default. No backend state or API changes are required.

Every immutable frontend asset reference and module release marker is rotated
to one new content release as a single transaction, preserving the release
fingerprint contract and first-paint consistency.

## Verification and evidence

Implementation is complete only after:

- focused static contracts cover the dedicated icon, theme allowlists,
  release graph, safe custom-property allowlist, and removal of legacy theme;
- browser tests cover search centering, equal section rhythm, narrator keyboard
  tabs and four-value save, Add-ons labels/borders, select/button geometry,
  both curated themes, custom hex/RGB synchronization, validation,
  Save/Cancel/Reset, import/export, persistence, and first-paint behavior;
- deterministic desktop, tablet, mobile, landscape, and short-height renders
  are inspected beside the applicable supplied references;
- the focused frontend collection and repository gate pass;
- `docs/guides/INTERFACE.md` and the cleanup ledger record the resulting
  maintained contract and evidence.

