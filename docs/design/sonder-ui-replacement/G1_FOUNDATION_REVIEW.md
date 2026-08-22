# Gate G1 visual-foundation review

**Review source:** `aadc264` (exact 40-character SHA recorded in the browser report)  
**Evidence:** [15-case browser report](g1/foundation-report.json), [icon inventory](ICON_INVENTORY.md), [WP-01 plan](../../superpowers/plans/2026-08-21-sonder-ui-replacement-wp01.md)  
**Scope:** visual vocabulary, local icon family, accessible component primitives, and a non-functional shell composition specimen. No product data, routing, or API behavior is claimed.

## Review 1: product-flow applicability

The laboratory covers the states the replacement flows will need: ordinary,
selected, disabled, busy, complete, empty, no-results, recoverable error,
validation error, destructive confirmation, menu, tab, dialog, and sheet. The
shell specimen tests hierarchy and responsive composition only. It makes zero
API requests and cannot mutate story or host state, so WP-02 and later packages
remain responsible for all real application flows and async ownership.

**Decision:** applicable foundation; no product-flow requirement is closed by
the specimen.

## Review 2: visual system and shell composition

The component layer consumes semantic tokens; four curated themes override
roles rather than geometry. UI, prose, and diagnostic type roles are separate.
The local 24-unit monoline SVG sprite uses `currentColor`, is build-free, and
has an explicit runtime allowlist. The quiet shell hierarchy keeps story prose
central while navigation and tools remain subordinate.

**Decision:** conforms to the G1 Design Bible vocabulary. Curated-theme and
legacy-theme compatibility remain open until WP-12 exercises real surfaces.

## Review 3: responsive and accessibility behavior

Browser contracts exercise keyboard roving focus, dialog focus trap and
restoration, Escape dismissal, field/error relationships, OS reduced motion,
Accessibility Mode, granular presentation overrides, touch target size, and
horizontal overflow. The evidence matrix covers 360, 390, 640, 844, 1024, and
1440 CSS-pixel widths; portrait, short landscape, long-copy, and a 200-percent
zoom equivalent are included. Mobile interactive targets are at least 44 CSS
pixels in the tested laboratory.

**Decision:** G1 primitives are suitable for reuse. Program-wide `RESP-*` and
`A11Y-*` requirements remain open because every real workflow must prove them.

## Review 4: implementation and state ownership

Appearance preflight is a bounded head script; subsequent behavior is native
ES modules. Components own their semantics, focus behavior, cleanup, and state
changes without `window.S`, polling, mutation observers, hidden legacy
controls, external assets, or API access. The laboratory is protected by the
same host-session check as `/ui-next` and does not change the classic `/` entry.

**Decision:** responsibility boundaries are acceptable for WP-02/WP-03 reuse.

## Findings resolved during review

| Finding | Resolution |
|---|---|
| Visually hidden toggle inputs did not receive pointer clicks. | The native input now overlays its label while the styled switch remains presentational. |
| Dialog focus restoration captured the opener too early. | The overlay controller records the active opener when `show()` runs. |
| Segmented controls overflowed and fell below mobile target size. | They wrap, use border-box sizing, and join the mobile target rule. |
| Theme-card grid stretched control groups. | Stack content now aligns to the start. |
| Long row metadata and Accessibility Mode markers damaged narrow layouts. | Row internals and status-marker columns now have explicit responsive structure. |
| Sticky laboratory navigation appeared twice in full-page evidence. | The recorder returns to the document origin before capture. |
| Compact list rows hid the SVG but retained its wrapper gap. | The compact rule hides the icon wrapper. |
| The plan named 200-percent zoom but evidence only implied it. | A dedicated 640-by-360 CSS-pixel test and capture now model 1280-by-720 at 200 percent. |

## Gate result

**G1 locked.** Qualification completed on Windows with Chromium 149:

- source/server/control-plane/browser focus: 46 passed;
- generated code map and English UI catalog refreshed;
- Python compile across every maintained source root: passed;
- project structure checker: passed with no findings;
- full repository suite: 8,753 passed, 4 platform skips;
- complete browser suite: 68 passed;
- two consecutive complete evidence captures: byte-identical across all 16
  report and screenshot files.

This locks the reusable foundation and closes only `ICON-01` through
`ICON-10`. Cross-program theme, responsive, accessibility, localization,
architecture, and product-flow requirements remain open.
