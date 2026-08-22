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
- Added the reference terminal glyph used by Advanced and Turn details.
- Preserved safe fallback behavior for invalid Settings deep links.

## Deliberately incomplete

- AI Connections still needs prompt-cache, generation-limit, image/ambience model, embedding,
  and advanced per-role controls from the current provider surface.
- Content, Add-ons, and Maintenance still need their reference panels.
- Settings search and legacy theme selection are not connected yet.
- The four Advanced launchers are visual ports only until their replacement editors are
  connected to current engine owners. They do not bridge to the legacy DOM.

## Evidence

- `screenshots/settings-1440.png`
- `screenshots/settings-390.png`
- `screenshots/settings-advanced-1024.png`
- `screenshots/settings-ai-1440.png`
- `screenshots/settings-ai-connect-1440.png`
- `57 passed` across Settings, shell, Play, and Library browser contracts.
- `node --check static/js/ui-next/settings-view.js`
- `git diff --check`
