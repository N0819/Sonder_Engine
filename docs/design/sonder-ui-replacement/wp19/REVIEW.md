# WP-19 Unified Settings navigation review

**Review date:** 2026-08-24
**Surface:** Settings detail navigation across desktop, tablet, and mobile
**Result:** Accepted

## Contract reviewed

Settings detail pages now project the same four groups and thirteen rows as the
Settings overview: Connections, Appearance, Story & host, and Advanced. The
projection reuses each row's icon, title, availability, authoritative route, and
already-loaded state summary. There is one Settings information architecture;
the detail navigation no longer maintains a competing category list.

Desktop keeps the projection as a compact 240 px rail. At 1099 px and below,
the navigation moves into the Settings content owner and becomes four
accessible disclosure groups. The active detail's group is open by default,
selecting another group closes the previous group, and one group always remains
open. The selected row retains `aria-current="page"`. Detail content stays
full width beneath the disclosures; compact layouts have neither a sidebar nor
a horizontal category strip.

Existing detail hashes, runtime ownership, persistence, Settings search, and
the quiet overview route remain unchanged. Unavailable Turn details remains
unfocusable without an open Story.

## Visual evidence

`tools/capture_ui_settings_overview.py` loads the real replacement module
graph and stubs only public API responses.

| Viewport | Evidence | Review |
|---|---|---|
| Desktop, 1440x900 | `screenshots/desktop-1440.png` | The overview groups become a restrained rail, the active row is clear, and Settings content remains the only vertical owner. |
| Tablet, 1024x768 | `screenshots/tablet-1024.png` | The sidebar is gone; Connections opens as a full-width disclosure with the same labels and summaries as the overview. |
| Mobile, 390x844 | `screenshots/mobile-390.png` | Appearance opens by default, rows retain touch geometry, summaries remain readable, and there is no horizontal overflow. |
| Mobile alternate group, 390x844 | `screenshots/mobile-story-host-390.png` | Opening Story & host closes Appearance and reveals the corresponding overview rows in place. |
| Short landscape, 844x390 | `screenshots/landscape-844x390.png` | The compact disclosure composition survives short height without restoring a sidebar or category strip. |
| Short tablet, 1024x600 | `screenshots/tablet-short-1024x600.png` | Advanced opens in the disclosure projection before the full-width launcher detail at the supplied short-Settings height. |
| Overview to detail, 1440x900 | `screenshots/overview-to-detail-1440.png` | AI Connections preserves its authoritative detail composition while the grouped rail replaces the old category taxonomy. |
| Back return, 1440x900 | `screenshots/overview-return-1440.png` | Back returns to the overview and restores the launching row without changing the grouped hierarchy. |

## Supplied-reference comparison and approved differences

The supplied screenshot archive was verified at
`299ad1fbb7edd60255f2cd2bf160e43479fc382a355be9218f60308983d94fe0`
before comparison. The current renders were reviewed against these exact
same-viewport references:

- At 1440x900, `03_desktop_settings.png` remains authoritative for shell,
  header, 240 px rail, detail-column geometry, density, typography, and the
  Experience composition. The approved difference is navigation content: its
  flat six-category rail becomes the overview's four groups and thirteen task
  rows, including the quiet overview route.
- At 390x844, `11_mobile_settings.png` remains authoritative for the compact
  header, search, fixed destination bar, touch density, and single Settings
  scroll owner. The approved difference replaces its horizontal category strip
  with the same four overview groups as single-open, in-content disclosures.
- At 1024x600, `16_short_settings_advanced.png` remains authoritative for the
  Advanced launcher hierarchy, warning treatment, short-height density, and
  content ownership. The approved tablet behavior replaces its left sidebar
  with the grouped disclosures before the full-width detail.

These departures are one coordinated navigation change, not a new visual
language: the grouped Settings overview is the composition reference for group
order, rows, icons, summaries, frames, and separators. The change introduces no
second vocabulary, new setting owners, or alternate persistence.

## Focused verification

- Browser contracts pin the exact four-group order and thirteen-row projection.
- Mobile coverage pins the single-open disclosure behavior, touch geometry, and
  absence of horizontal overflow.
- Tablet coverage pins in-content navigation, active-group selection, current
  row state, and overview-owned summaries.
- The desktop, tablet, mobile, and short-landscape renders were compared at the
  recorded viewports against the approved overview hierarchy and shell rules.
