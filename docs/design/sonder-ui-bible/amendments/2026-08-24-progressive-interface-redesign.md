# DB-2026-08-24 Progressive interface redesign

**Identifier:** DB-2026-08-24  
**Date:** 2026-08-24  
**Author/reviewer:** Product owner and implementation review  
**Category:** Revision  
**Approval status:** Approved by product-owner implementation brief  
**Specification:** [`../../../superpowers/specs/2026-08-24-sonder-progressive-interface-redesign.md`](../../../superpowers/specs/2026-08-24-sonder-progressive-interface-redesign.md)

## Affected authority

This Revision amends the macro composition and calibrated visual rules in:

- 02 Reference Translation;
- 03 Product Character;
- 05 Information Architecture;
- 06 Visual Grammar;
- 07 Soft-Precision Geometry;
- 08 Spacing, Alignment, and Density;
- 09 Typography;
- 12 Integrated Control Clusters;
- 13 Component Contracts;
- 14 Play Workspace;
- 15 Library;
- 16 Settings;
- 17 New Story and First Run;
- 18 Responsive and Mobile;
- 22 UX Flows and Expert Acceleration;
- 23 Anti-Patterns;
- 24 Tokens and Measurements;
- 25 Audit Rubric and Quality Gates;
- 26 Decision Register;
- `docs/guides/INTERFACE.md` and `docs/guides/UI_REFERENCE.md`.

The Design Bible North Star, three-destination architecture, editorial prose,
genre neutrality, runtime ownership, accessibility, and progressive-disclosure
principles remain unchanged.

## Current rules replaced

| Superseded rule | Revised rule |
|---|---|
| compact 56-72 px navigation rail is the ordinary wide-desktop composition | wide and expansive desktop default to a labeled 176-200 px rail, explicitly collapsible to 64-72 px |
| right inspector may be persistent by default on wide Play | contextual surfaces default closed and overlay; pinning is explicit and expansive-only when at least 680 px remains for primary content |
| inspector Expanded/Compact/Rail modes and icon-only detail switcher | one grouped labeled landing and one oriented detail; Rail and unlabeled switchers are deprecated |
| indices may decorate primary destinations, tools, long Library ledgers, setup routes, and themes | decorative indices are absent from ordinary navigation and content; numbers appear only when order is user-meaningful |
| mute and volume remain beside the composer | ambience is secondary to the integrated composer and moves to a compact popover and/or Ambience tool |
| Library default is a dense ledger with all filters exposed | Library defaults to recognition-rich media rows/cards with a compact toolbar and staged secondary filters |
| compact Settings combines grouped disclosure navigation and selected detail | compact and medium Settings show overview or detail, never both; desktop retains category navigation plus one detail |
| supplied screenshots lock the covered macro composition | screenshots remain historical evidence and behavior inventory; this approved Revision controls replaced macro composition |

This Revision changes composition and disclosure, not the compact visual
foundation. The 3/4/5 px radius family, 11/12/13/14 px
micro/metadata/control/body scale, 36 px ordinary desktop controls, flat
neutral button surfaces, and restrained one-pixel selection markers remain
authoritative. Touch layouts retain 44 px targets without requiring every
desktop control to render as a 44 px box.

## Rationale and evidence

The current interface makes internal structure permanently visible: a default
Story Tools column, numeric registries, dense filter taxonomies, small technical
labels, and simultaneous mobile navigation/detail. The product-owner brief and
the source-informed `Sonder_UI_UX_Audit.md` both find that capability depth is
valuable but must be progressively disclosed.

Verified before evidence is recorded under
`docs/design/sonder-ui-replacement/redesign/before/`. Final same-fixture,
same-viewport evidence will be linked from the implementation review under
`docs/design/sonder-ui-replacement/redesign/after/`.

## Impact

### Desktop

The labeled rail improves destination recognition. Context drawers overlay by
default and pin only when measured space permits. Play remains centered and
dominant; Library and Settings retain expert density as an opt-in.

### Tablet

The shell uses a compact rail with overlay drawers. Library, Settings, and Story
Tools stage list/detail instead of squeezing desktop panes.

### Mobile and short landscape

A stable app bar owns title, Back, command, and contextual action. Bottom
navigation remains labeled. Detail and tool surfaces replace their parent view
or open as full-height sheets. Composer and action geometry respect dynamic
viewport height and safe areas.

### Accessibility

Interactive focus remains visible; only programmatic noninteractive route focus
loses the form-like ring. Touch targets remain at least 44 px. Overlays contain
and restore focus, Back/Escape retain layer ownership, pinned context never
inerts main, and reduced-motion/high-contrast/large-UI/roomy-target modes remain
first-class.

### Localization

New copy uses complete catalog strings. Layouts allow at least 30 percent label
growth, preserve RTL logical alignment, and remove English-dependent numeric
decoration from primary orientation.

### Migration

Existing server routes, persisted settings, drafts, and extension contracts do
not change. Browser-local pane state gains explicit false defaults and a
bounded navigation-collapse preference. Deprecated inspector size values map
to the grouped landing without preserving Rail presentation. Existing Settings
route segments remain compatibility inputs to the new conceptual groups.

## Deprecations

- permanent-by-default contextual inspector;
- Story Tool Rail mode and icon-only detail switcher;
- decorative destination/tool/Library/theme/New Story ordinals;
- persistent Play/Library grid backgrounds;
- destination-specific fixed compact header actions;
- simultaneous compact Settings overview and detail;
- raw schema and theme controls in ordinary default paths.

New code and examples must use the revised patterns. Historical review records
remain evidence of the releases they qualified, not reusable authorization for
deprecated composition.
