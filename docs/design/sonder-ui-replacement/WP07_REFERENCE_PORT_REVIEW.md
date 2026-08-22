# WP-07 reference-first shell, Library, and Play correction

**Reference implementation:** `73a380a0df2f6b139c98d66da9005489bd549d1d`

**Reference screenshots:** `02_desktop_library.png`,
`10_mobile_library.png`, and `14_tablet_library.png` from the supplied
Design Bible revision screenshot archive.

The Play correction uses `01_desktop_play.png`, `09_mobile_play.png`, and
`15_tablet_play.png` from the same archive.

**Status:** corrective visual slice accepted for continued WP-07 work; this is
not the complete WP-07 or product-surface gate.

## Correction

The earlier replacement Library used a wide text rail, a generic category
rail, a form-heavy central list, and a persistent right inspector. That was a
different composition from the supplied implementation and screenshots.

This slice ports the reference composition onto the current runtime:

- compact indexed primary rail;
- fixed Library scope/list pane;
- Library/Scope breadcrumb, All Library heading, search, scope selector, four
  content tabs, story ledger, and bottom New story/Import cluster;
- Your story material overview with four indexed totals, recent-story ledger,
  and Scope/Context frame;
- tablet stacking of the overview context below recent stories;
- mobile pane-only staging with the existing bottom destination navigation;
- item detail continuing through the existing current-runtime inspector and
  compact sheet rather than candidate polling, globals, or legacy clicks.

It also replaces the divergent Play dashboard composition with the reference
reading surface:

- 58px current-story bar with Story Tools and story actions;
- centered atmospheric transcript with turn rules, player-input frames, and
  literary prose treatment;
- full-width persistent composer aligned to the transcript measure;
- ledger-style Story Tools panel with icons and descriptive rows;
- compact Play header, composer, and bottom destination navigation;
- all ten current runtime tools retained, including the post-reference Frames
  and Multiplayer capabilities.

## Source use

| Reference source | Current port |
|---|---|
| `static/index.html` Library and primary-nav hierarchy | `static/ui-next.html`, `static/js/ui-next/library-view.js` |
| `static/css/remaster-shell.css` rail, Library pane, overview, and breakpoints | `static/css/ui/shell.css`, `static/css/ui/library.css` |
| `static/js/remaster/library.js` visual hierarchy and summary/context vocabulary | Safe DOM construction in `static/js/ui-next/library-view.js` |
| Candidate `window.S`, polling, `innerHTML`, and legacy clicks | Not ported |
| `static/index.html` Play hierarchy and `remaster-shell.css` Play rules | `static/js/ui-next/play-view.js`, `static/css/ui/play.css` |
| Candidate Story Tools launcher ledger | Current-runtime `story-tools-view.js` and `story-tools.css` |

Current `library-runtime.js`, API projections, mutations, stale-result guards,
undo receipts, routing, localization, and inspector ownership remain intact.
The shell exposes only the active destination and whether Library has a selected
item as bounded presentation attributes.

## Same-viewport evidence

| Reference | Corrective render |
|---|---|
| Desktop, 1440x900 | [`library-1440.png`](wp07/screenshots/library-1440.png) |
| Tablet, 768x1024 | [`library-768.png`](wp07/screenshots/library-768.png) |
| Mobile, 390x844 | [`library-390.png`](wp07/screenshots/library-390.png) |
| Play desktop, 1440x900 | [`play-1440.png`](wp07/screenshots/play-1440.png) |
| Play tablet, 768x1024 | [`play-768.png`](wp07/screenshots/play-768.png) |
| Play mobile, 390x844 | [`play-390.png`](wp07/screenshots/play-390.png) |

The fixture data differs from the supplied screenshots, so item names and
counts are not pixel-comparison inputs. The reviewed inputs are shell and pane
geometry, region order, responsive staging, hierarchy, density, action
placement, dividers, typography roles, and interaction framing.

## Behavioral evidence

- `browser_tests/test_ui_library.py`
- `browser_tests/test_ui_shell.py`
- `tests/test_ui_library_contracts.py`
- `tests/test_ui_shell_contracts.py`

The focused corrective gate passed all 42 tests after the final optical cleanup.

The focused Play, Story Tools, and shell gate passed all 63 tests after the
reference port and responsive cleanup.

## Remaining UI-only work

- Apply the same source-first comparison to selected-item/detail and WP-07
  authoring states before accepting their presentation.
- Continue Settings, entry, dialog, and remaining responsive surfaces
  from their matching supplied screenshots and candidate files.
- Keep service and server architecture unchanged unless a visible current
  capability cannot be connected through its existing owner.
