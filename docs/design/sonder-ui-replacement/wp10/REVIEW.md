# WP10 host authentication visual checkpoint

## Reference authority

- `05_desktop_login.png` for the restrained host-access header, centered card,
  field geometry, and Carbon Signal treatment.
- Current `static/login.html` behavior and `web/auth_routes.py` for security authority.

## Implemented

- Replaced legacy login styling with shared replacement tokens, typography, controls, and theme.
- Ported the supplied single-purpose Sign in composition with visible labels and correct autocomplete.
- Applied the same focused composition to first-run host setup without changing its route or policy.
- Preserved trusted-event, repeat-key, in-flight, local cooldown, server lockout countdown,
  generic credential failure, redirect, and network failure behavior.
- Added polite inline live status for validation, cooldown, lockout, and server failures.
- Added a staged Sign out action to Maintenance that destroys only the current host session.
- Kept credentials out of general replacement state, storage, diagnostics, notices, and URLs.
- Preserved the existing single redirect on expired host sessions.

## Evidence

- `screenshots/login-1440.png`
- `screenshots/setup-1440.png`
- `screenshots/login-390.png`
- `browser_tests/test_ui_auth.py`
- `browser_tests/test_login_lockout.py`
- `browser_tests/test_session_expiry_redirect.py`

## Qualification

- 3 focused replacement auth and staged-sign-out browser checks.
- 3 existing lockout/cooldown browser checks.
- 4 combined auth and expired-session browser checks.
- 69 host authentication and transport policy checks.
- English extraction and English/Japanese catalog-key parity checks.
