# WP08 Settings visual checkpoint

## Reference authority

- `03_desktop_settings.png` for the 1440 x 900 Experience layout.
- `11_mobile_settings.png` for the 390 x 844 compact layout.
- `16_short_settings_advanced.png` for the 1024 x 600 Advanced layout.
- `docs/16_SETTINGS.md` in the supplied Design Bible for category and behavior requirements.
- The supplied candidate's `static/css/remaster-shell.css` for measured Settings geometry.

The candidate archive does not contain its imported `static/js/remaster/settings.js`.
This slice therefore ports the supplied HTML/CSS composition and screenshots onto the
current UI runtime instead of inventing a substitute runtime contract.

## Implemented

- Replaced the generic Settings placeholder with the reference frame and six-category ledger.
- Ported the Experience theme and accessibility groups.
- Kept appearance preferences browser-local and immediate.
- Synchronized the Accessibility Mode master control with every visible preference.
- Ported the Advanced launcher ledger and warning at its supplied short-desktop breakpoint.
- Ported the AI Connections provider ledger into the same reference field-grid treatment.
- Connected provider creation, existing-provider edits, credential-safe saves, connection tests,
  model discovery, and default-model saves to the current runtime APIs.
- Connected per-provider prompt caching and the provider-side response limit, always reflecting
  the server's returned cache state rather than the requested checkbox state.
- Added the required advanced disclosure for per-role model, reasoning, sampler, and ordered
  fallback assignments while preserving untouched role configuration fields.
- Connected embeddings-model change warnings, backdrop image configuration, backdrop enablement
  and continuity, and credential-safe local/Freesound ambience configuration.
- Connected Content preferences to the current adult-content, authored-underneath-detail, and
  recurring-extra promotion routes, with one explicit save and a scoped path to story export and
  deletion controls.
- Replaced the legacy extension panel with installed-state, trust and permission disclosures,
  safe-mode/load-failure recovery, update checks, staged install and enable consent, disable,
  update, and staged removal that explicitly preserves extension-owned story data.
- Replaced the Maintenance placeholder with explicit update checking/install staging and the
  resumable, equivalence-checked legacy-checkpoint conversion flow.
- Added localized-label/alias Settings search with control-level routes and focus restoration.
- Connected the Legacy selector through semantic curated-theme mappings without allowing classic
  theme CSS to own replacement layout.
- Connected Advanced's Prompt editor to the current preset projection and explicit preset-save
  route; the editor no longer depends on a legacy dialog or hidden control.
- Added staged embeddings repair and downloadable bounded/redacted interface diagnostics to
  Maintenance.
- Completed Experience's current reading-size, density, effects, story sound, turn notification,
  and interface-language controls alongside the supplied theme/accessibility treatment.
- Added current-route raw world and attire JSON editors under Advanced with load ownership,
  validation, explicit save, and no legacy modal bridge.
- Made advanced per-role samplers and ordered backup models editable without flattening untouched
  role configuration, and connected OpenRouter retention/fallback/upstream routing.
- Added story-scoped Living world controls sourced entirely from the server's built/permitted/
  effective ladder, including visible clamp explanations for unbuilt or disallowed depth.
- Completed the current prompt-preset lifecycle with selection, activation, explicit save,
  import, export, and staged deletion, and connected provider image-model discovery.
- Added the scoped, reversible Experience reset with a dedicated confirmation.
- Added a staged Content-form reset and routed portable story backups to the Library's
  per-story export owner instead of inventing an unsafe global export operation.
- Proved the complete Advanced prompt surface remains available without horizontal overflow
  at the supplied 390 px compact breakpoint.
- Added the reference terminal glyph used by Advanced and Turn details.
- Preserved safe fallback behavior for invalid Settings deep links.

## WP12 boundary

- Advanced Turn details routes to the replacement Play tool; raw world and attire editors remain
  inside Advanced and use current story routes.
- Add-ons settings registrations are mounted by the existing contained extension host, but
  installed v1/v2 corpus qualification remains WP12.

## Evidence

- `screenshots/settings-1440.png`
- `screenshots/settings-390.png`
- `screenshots/settings-advanced-1024.png`
- `screenshots/settings-ai-1440.png`
- `screenshots/settings-ai-connect-1440.png`
- `screenshots/settings-ai-models-1440.png`
- `screenshots/settings-ai-media-1440.png`
- `screenshots/settings-content-1440.png`
- `screenshots/settings-add-ons-1440.png`
- `screenshots/settings-maintenance-1440.png`
- `screenshots/settings-advanced-prompts-1440.png`
- `screenshots/settings-advanced-story-data-1440.png`
- `screenshots/settings-content-living-world-1440.png`
- `screenshots/settings-search-1440.png`
- `25 passed` in the focused Settings browser suite after Experience, raw-data, generation-default,
  OpenRouter, and Living world coverage.
- `node --check static/js/ui-next/settings-view.js`
- `git diff --check`
