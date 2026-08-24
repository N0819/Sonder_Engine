# WP-18 Grouped Settings overview review

**Review date:** 2026-08-23
**Surface:** Settings overview and overview-to-detail navigation
**Result:** Accepted

## Contract reviewed

`#/settings` is now a scan-first home rather than an alias for Experience. It
keeps one readable ledger column and four ordered groups: Connections,
Appearance, Story & host, and Advanced. Every available row is one semantic
link with a local icon, plain title, concise owned-state summary, and chevron.
There are no nested forms, toggles, action buttons, or new setting owners.

The overview projects only bootstrap state already held by Settings, current
browser-local presentation preferences, and the loaded extension slice. It
does not discover providers, check updates, load extensions, call a model, or
write a setting merely by rendering. Missing state receives descriptive copy
rather than an invented count. Turn details has no navigation target until a
Story is open.

Existing category, control, and Advanced-tool hashes remain unchanged. Search
still opens the exact detailed control. Detailed Settings pages retain the
category ledger and now include a quiet Settings overview link. Browser Back
restores the overview scroll offset and the row or search field that launched
the detail.

## Visual evidence

`tools/capture_ui_settings_overview.py` loads the real replacement module graph
and stubs only public API responses.

| Viewport | Evidence | Review |
|---|---|---|
| Overview, 1440×900 | `screenshots/overview-1440.png` | One centered ledger, restrained headings, aligned summaries, local icons, and calm separators fit the approved Sonder shell. |
| Overview, 1024×768 | `screenshots/overview-1024.png` | The same hierarchy narrows without becoming a dashboard grid or clipping long summaries. |
| Overview, 390×844 | `screenshots/overview-390.png` | Summaries stage beneath titles, chevrons remain aligned, rows retain touch geometry, and the fixed destination bar covers no focused control. |
| Overview, 844×390 | `screenshots/overview-844x390.png` | Short landscape keeps the Settings content as its single vertical owner and preserves the same route order. |
| Detail, 1440×900 | `screenshots/overview-detail-1440.png` | AI Connections keeps its existing authoritative detail composition and gains the quiet overview entry before the category ledger. |
| Back return, 1440×900 | `screenshots/overview-return-1440.png` | The launching AI Connections row regains keyboard focus without disturbing the ledger's visual hierarchy. |

## Comparison and boundary

The supplied ChungusHub image informed only the sorting pattern: semantic group
labels, full-row navigation, restrained summaries, and separators. Sonder keeps
its approved shell, type roles, semantic colors, icon sprite, spacing scale,
responsive staging, routes, and runtime ownership. No external source code,
assets, branding, or exact pixel measurements were copied.

## Focused verification

- Ordered static group/route and no-side-effect source contracts pass.
- The new overview browser file covers route targets, summaries, unavailable
  Turn details, keyboard activation, global Settings navigation, `mod+,`,
  search, Back, focus/scroll restoration, compact target size, and horizontal
  overflow.
- The directly affected Settings and shell browser gate passes 68 tests.
- The integrated immutable replacement graph is coherent at
  `alpha98-ui8-eb87a8415bda`.
