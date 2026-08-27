# 11. Icon Source and Usage

**Status:** Accepted mockup implementation contract

**Date:** 2026-08-26

## Decision

Sonder's Panels and Widgets mockup uses **real SVG artwork from the SVG Repo
Minimal UI Icons collection** as its primary icon language. Codex-generated,
AI-generated, hand-drawn replacement, emoji, Unicode-symbol, CSS-drawn, and
icon-font substitutes are prohibited when an appropriate collection SVG exists.

The interface favors icons over plain text where the symbol is familiar,
compact, and unambiguous. This is not permission to trade comprehension or
accessibility for visual density. Ambiguous, consequential, destructive,
stateful, first-use, and uncommon actions retain visible text or use an
icon-plus-label treatment.

## Source authority

The local source collection is:

- [artifact README](../../../artifacts/minimal-ui-icons/README.md);
- [source and provenance manifest](../../../artifacts/minimal-ui-icons/manifest.json);
- repository path: `artifacts/minimal-ui-icons/`;
- upstream collection:
  [SVG Repo Minimal UI Icons](https://www.svgrepo.com/collection/minimal-ui-icons/);
- upstream [licensing reference](https://www.svgrepo.com/page/licensing/).

Verified artifact snapshot:

| Evidence | Value |
|---|---|
| Collection pages | 36 |
| Manifest entries | 1,796 |
| SVG files | 1,796 |
| Unique source ids | 1,796 |
| Unique filenames | 1,796 |
| Manifest/file mismatches | 0 |
| Manifest license metadata | `CC0` on all 1,796 entries |
| Collection-page retrievals | 1,788 |
| Official-download fallbacks | 8 |
| `manifest.json` bytes | 670,453 |
| `manifest.json` SHA-256 | `66B2CBD9D4E5A9D40D959C49362D707225C16BEAA4A7163FC96F2484D6DA30CF` |

The source manifest, rather than a remembered collection-wide assumption, is
the provenance authority. Every selected icon must resolve to one manifest
entry and local file. If the collection is refreshed, its manifest and hash are
reviewed before the mockup mapping changes.

## Selection hierarchy

For every Widget identity and control:

1. search the local manifest by the intended user-facing concept and synonyms;
2. inspect actual candidate SVGs at target sizes and in all required themes;
3. choose the clearest collection asset with the closest optical family;
4. reuse one semantic icon for one concept across the workbench;
5. use visible text or icon-plus-label if no collection symbol is sufficiently
   clear;
6. request an explicit design exception before introducing artwork from any
   other source or creating a new icon.

Brand marks, novelty glyphs, and culturally narrow metaphors are not selected
for generic product actions merely because they are visually distinctive.
Opposing pairs such as play/stop, expand/collapse, mute/unmute, add/remove, and
lock/unlock must remain distinguishable at the smallest supported size.

## When icons replace or accompany text

| Treatment | Appropriate uses | Requirements |
|---|---|---|
| Icon only | Repeated, familiar, low-risk controls such as Close, Back, Forward, Search, Expand/Collapse, overflow, and drag handles | Accessible name; focus-visible treatment; tooltip on hover and focus where context does not already name it |
| Icon plus label | Primary actions, catalog launch/placement, Save/Use/Apply, uncommon actions, state changes, and controls encountered infrequently | The label remains the authoritative meaning; the icon improves scan speed |
| Label first | Destructive, irreversible, expensive, security-sensitive, or technically ambiguous actions | Never rely on a trash/warning/generic gear icon to communicate the consequence |
| Icon plus state text | Loading, warning, error, stale, success, muted, locked, connected, or unavailable status | State must not depend on icon, color, animation, or position alone |
| Decorative icon | Non-interactive visual reinforcement | Hidden from assistive technology; no duplicate accessible name |

An icon may replace a visible label at a narrow breakpoint only when the same
control remains recognizable in context and preserves its accessible name. The
wide layout may continue to use icon-plus-label when that improves learnability.

## Geometry and visual normalization

- Preserve the source `viewBox`, path geometry, line caps, joins, and relative
  proportions. Normalization must not redraw the artwork.
- Use the shared icon wrapper and a small supported size scale rather than
  independent per-control measurements.
- Monocolor assets may have paint normalized to `currentColor`; this changes
  theme integration, not geometry.
- Optically center the complete source viewBox. Do not crop paths to force every
  symbol into identical mathematical bounds.
- Icon color follows semantic control/status tokens. An icon does not introduce
  a new decorative accent palette.
- Touch targets remain at least 44 px even when the visible SVG is smaller.
- Disabled, hover, pressed, selected, focus, and high-contrast states belong to
  the host control; source paths do not encode them independently.

## Mockup implementation

The standalone HTML mockup uses a centralized, sanitized inline SVG symbol
sprite assembled from selected local files. Each symbol preserves the source
geometry and uses an id containing the SVG Repo source id. A single semantic
mapping resolves product concepts to sprite ids and records:

- semantic key;
- SVG Repo id and local filename;
- source detail URL;
- manifest license metadata;
- intended controls/Widgets;
- normalization performed, limited to safe paint/size integration.

The mockup never fetches icons from the internet at runtime. It does not paste
independent anonymous path data into each button. Reuse goes through the shared
sprite/mapping so changing a semantic selection is reviewable and consistent.

The source corpus audit found no `<script>`, `<foreignObject>`, common event
attributes, external/data `href`, missing SVG root, or missing `viewBox`.
Selected assets are still passed through the same static sanitizer before they
enter the sprite; provenance does not substitute for input safety.

## Widget and Catalog requirements

- Every Widget definition receives one semantic identifying icon drawn from the
  collection unless its stage-native presentation deliberately uses no visible
  identity mark outside edit/focus state.
- The Catalog uses the same identifying icon as the placed Widget. It does not
  invent a separate thumbnail glyph.
- Actions reuse the same semantic mappings across Widgets, Settings, Library,
  Story systems, extension shells, and responsive presentations.
- Extension-provided icons remain owner assets and receive an owner badge; they
  cannot impersonate a core semantic icon. A missing/unsafe extension icon uses
  a host-selected collection fallback.
- Representative miniatures may use collection icons but never make them the
  only evidence of Widget purpose, context, or state.

## Accessibility acceptance

Every interactive icon control must pass all of these checks:

1. an accessible name describes the action, not the artwork;
2. a stateful control exposes pressed/expanded/selected state semantically;
3. keyboard focus is visible in every theme and high-contrast mode;
4. hover-only explanation is duplicated on focus and is not required to operate;
5. adjacent icon-only controls remain distinguishable without color;
6. 200% zoom and narrow reflow preserve the action or an equivalent labeled
   route;
7. decorative SVGs are ignored by assistive technology;
8. status and consequence remain stated in text.

## Verification gates

Before a widget tranche is accepted in the mockup:

- every referenced semantic icon resolves to the central mapping;
- every mapping resolves to a local file and manifest entry;
- no remote icon URL, emoji, Unicode control symbol, icon font, CSS-drawn
  replacement, or generated icon appears in product chrome;
- icon-only controls have accessible names and correct state semantics;
- destructive/expensive/security actions retain visible consequence text;
- selected SVGs are compared at actual desktop, compact, touch, high-contrast,
  and solid-surface sizes;
- the regression harness proves that SVG hit targets do not change placement,
  drag, focus, or click behavior.

An exception requires a dated decision entry naming the missing concept,
collection search performed, alternate source/license, and why visible text was
insufficient.
