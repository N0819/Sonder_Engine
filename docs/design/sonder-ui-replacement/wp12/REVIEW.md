# WP12 theme and extension compatibility review

WP12 closes the G5 theme and extension package on the replacement host. It
does not change the engine extension API (`ext_api: 1`) or any backend runtime
authority. UI module versioning is independently declared as
`capabilities.ui.api`.

## Product flow

- Experience presents Carbon Signal, Ash and Brass, Midnight Ink, and
  Parchment Night as one curated set, plus a clearly labeled Legacy mapping.
- Add-ons displays declared capabilities, trust wording, enabled state, source,
  engine API, and per-extension UI API before lifecycle actions.
- Classic scripts receive only the explicit v1 `window.Sonder` adapter. Native
  modules declaring UI API 2 receive an owner-bound v2 facade.
- Play tools mount in Play, Library types in Library, and destination,
  legacy-view, and Add-ons settings registrations in Settings. A retired
  selected surface returns to that destination's safe parent.

## Visual system

- Curated and Legacy appearance changes only semantic `--ui-*` roles. Layout,
  component geometry, state naming, effects, and accessibility remain owned by
  the host.
- Bundled extension CSS uses owner-prefixed classes and public semantic tokens.
  The replacement contract does not include classic private helpers, DOM ids,
  global palette writes, or full-host stylesheet replacement.
- The bundled corpus is intentionally mixed: Cohesion is the classic v1
  fixture; Overlay and Campaign are ES-module UI v2 fixtures.

## Responsive and accessibility review

- Theme selection uses named native buttons and the Legacy mapping uses a
  labeled native select. Selection is exposed through text and `aria-pressed`,
  not color alone.
- Extension launchers and mounts retain normal destination reading order and
  use named regions. Lifecycle actions remain visible text buttons.
- The existing foundation matrix exercises all four curated semantic palettes;
  Settings contracts exercise independent effects, accessibility, mobile
  category staging, and Legacy mapping.

## State preservation and failure boundaries

- Registrations, notices, listeners, assets, and teardown callbacks are owned
  by extension id and removed together on disable, retirement, or the third
  contained fault.
- Module registration remains attributed across `await`; v1 ambient
  `_begin`/`_end` attribution is confined to the synchronous classic bundle.
- A failed import or render does not stop shell boot. A disappeared selected
  route reports the condition and navigates to its useful parent.
- Theme choice and effects remain browser-local presentation state; no story or
  host setting is reinterpreted.

## Evidence

- Curated themes: `screenshots/settings-theme-carbon-signal-1440.png`,
  `settings-theme-ash-brass-1440.png`,
  `settings-theme-midnight-ink-1440.png`, and
  `settings-theme-parchment-night-1440.png`.
- Legacy mapping: `screenshots/settings-theme-legacy-tavern-1440.png`.
- Installed v1/v2 disclosure:
  `screenshots/settings-add-ons-v1-v2-1440.png`.
- Deterministic capture: `tools/capture_ui_wp12.py`.
- Behavioral contracts: `browser_tests/test_ui_wp12.py`,
  `browser_tests/test_ui_foundation.py`, `browser_tests/test_ui_settings.py`,
  `browser_tests/test_ui_runtime.py`, and `browser_tests/test_ui_shell.py`.
- Source/runtime contracts: `tests/test_ui_wp12_contracts.py`,
  `tests/test_ui_foundation.py`, `tests/test_ui_shell_contracts.py`, and the
  extension discovery/module/surface/install suites.

## Qualification

The focused and integrated WP12 matrix passed on 2026-08-22:

```text
296 passed, 3 skipped in 38.05s
```

The three skips are the repository's existing Windows symlink capability
skips. The first run used pytest's default user temp directory and Windows
denied access; rerunning the identical command with workspace-local
`--basetemp .tmp/pytest-wp12` produced the result above.

G5 is closed. Cross-product final-browser, final-localization, and exact-head
release qualification remain owned by WP14.
