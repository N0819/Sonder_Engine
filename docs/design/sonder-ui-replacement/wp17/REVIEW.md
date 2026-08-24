# WP-17 Settings, themes, and shared controls review

**Review date:** 2026-08-23
**Surfaces:** Settings, curated and custom themes, shared buttons/selects, and
the Library control bar
**Result:** Accepted

## Contract reviewed

The package repairs the reported control-level inconsistencies without changing
the approved replacement information architecture. Settings keeps one detail
scroll owner and one section rhythm. Narrator examples remain four persisted
values behind a single tabbed editor. Extension titles remain authored data,
while lifecycle actions remove only a terminal `(demo)` marker. Maintenance now
uses the supplied local wrench symbol.

Unsupported Legacy-theme selection is gone. Neon Circuit extends the dark
technical theme family with restrained violet, cyan, and amber. Modern Slate is
entirely warm greyscale: every authored color is neutral or red-leading within a
narrow channel spread, and interaction uses subdued warm white rather than
blue. Custom Theme owns exactly eight semantic color roles. It accepts no CSS
or layout input, validates contrast before activation, and uses a versioned,
exact-key browser-local document for persistence and import/export.

Shared selects and buttons retain the existing component ownership. Selects
receive the glass surface, restrained radius, common chevron, and compact
desktop sizing while preserving 44 px touch targets. Buttons use restrained
type and centered inline-flex geometry so Search and New Story's icon/text pair
align without changing their actions.

## Browser evidence

`tools/capture_ui_theme_polish.py` loads the real replacement module graph and
stubs only public API responses. The 14 deterministic images cover the changed
Settings surfaces and the shared Library controls.

| Viewport | Evidence | Review |
|---|---|---|
| Settings search, 1440×900 | `screenshots/settings-search-1440.png` | Search glyph centers in the 36 px control and the result ledger aligns with the field. |
| Custom editor, 1440×900 | `screenshots/custom-theme-editor-1440.png` | Eight roles, preview, validation, and actions form one bounded semantic editor in the former Legacy location. |
| Neon Circuit, 1440×900 | `screenshots/neon-circuit-1440.png` | Violet ground, restrained cyan interaction, and amber attention preserve hierarchy and readable surfaces. |
| Modern Slate, 1440×900 | `screenshots/modern-slate-1440.png` | The complete application remains warm greyscale with subdued warm-white interaction and no blue cast. |
| Color dialog, 1440×900 | `screenshots/custom-color-dialog-1440.png` | Design-Bible overlay hierarchy, named modal, native color well, synchronized hex/RGB fields, validation, and clear actions. |
| Narrator tabs, 1440×900 | `screenshots/narrator-tabs-1440.png` | One editor replaces the irregular four-textarea wrap while retaining four visible tabs. |
| Add-ons, 1440×900 | `screenshots/add-ons-1440.png` | `Campaign (demo)` remains the title; Enable Campaign and Remove Campaign are coherent bordered actions. |
| Maintenance, 1440×900 | `screenshots/maintenance-1440.png` | The supplied wrench reads cleanly in the category rail and uses the same icon geometry as adjacent categories. |
| Custom editor, 390×844 | `screenshots/custom-theme-editor-390.png` | Swatches stage as two columns, actions wrap deliberately, and the page has no horizontal overflow. |
| Color dialog, 390×844 | `screenshots/custom-color-dialog-390.png` | The overlay becomes a bottom sheet with 44 px controls and all channels visible. |
| Narrator tabs, 390×844 | `screenshots/narrator-tabs-390.png` | Tabs wrap without clipping and the single editor remains reachable above fixed destination navigation. |
| Narrator tabs, 844×390 | `screenshots/narrator-tabs-844x390.png` | Short-height Settings keeps the detail pane as its scroll owner; tabs and editor remain vertically reachable. |
| Library controls, 1440×900 | `screenshots/library-controls-1440.png` | Search, selects, New Story, and import controls share restrained density and alignment. |
| Library controls, 390×844 | `screenshots/library-controls-390.png` | Shared controls retain 44 px touch geometry and the plus icon remains centered with its label. |

## Comparison and approved differences

The supplied defect screenshots establish the before-state for icon alignment,
section spacing, narrator wrapping, demo-labelled actions, Maintenance
iconography, native selects, and Library action typography. The repaired
captures retain the approved shell geometry, category order, restrained carbon
surface, technical metadata type, cyan interaction language, and mobile
destination staging. The approved differences are limited to the requested
control compositions, two curated palettes, and the validated semantic custom
theme editor. No new navigation level, dashboard, card grid, or browser-owned
runtime authority was introduced.

## Behavior and safety review

- The narrator tablist supports Arrow Left/Right, Home, and End, retains four
  drafts, and saves through the existing exemplar endpoint.
- Legacy appearance state is migration input only and disappears from the
  browser-local envelope when Experience renders or a theme is selected.
- Custom Theme writes only eight fixed properties. Unknown fields, malformed
  schema versions, CSS, URLs, markup, invalid colors, and failing contrast are
  rejected before activation.
- Opening a color role previews a valid palette only. Cancel and Escape restore
  the previous theme and focus; Save color updates the draft; Use Custom Theme
  is the explicit persistence boundary.
- Hex, RGB, native color-well, reset, import, export, first-paint preflight, and
  reload all use the same normalized validation path.
- Compact and touch layouts preserve the 44 px target contract and expose no
  horizontal page overflow.

## Verification

- `browser_tests/test_ui_settings.py`
- `browser_tests/test_ui_custom_theme.py`
- `browser_tests/test_ui_library.py`
- `tests/test_ui_foundation.py`
- `tests/test_ui_icon_system.py`
- `tests/test_ui_runtime_contracts.py`

Verification results on the reviewed candidate:

- focused foundation, icon, runtime, Settings, custom-theme, and Library gate:
  101 passed;
- complete browser suite: 234 passed;
- complete repository suite: 8,805 passed and 4 platform-specific skipped;
- generated code map and complete project structure check: passed;
- deterministic visual capture: 14 states completed and reviewed;
- immutable UI release: `alpha98-ui6-ff8a9b712a2d`.

The first complete repository run encountered two transient Windows directory-
rename permission errors in unrelated extension-install tests. Both exact tests
passed on fresh isolated reruns, and the complete unchanged parallel suite then
passed. No extension runtime source was changed by this package.
