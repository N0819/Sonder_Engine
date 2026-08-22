# WP11 guest entry and Play visual checkpoint

## Reference authority

- `06_mobile_guest_join.png` for the lightweight header, join card, copy,
  field geometry, and mobile spacing.
- Current `static/guest.html`, `/api/join`, `/api/guest/state`, and
  `/api/guest/input` behavior for guest access authority.

## Implemented

- Replaced the guest entry presentation in place with the supplied mobile
  composition and shared replacement tokens, fields, buttons, card, and theme.
- Kept the guest page lightweight: it loads no host shell or host application
  JavaScript.
- Preserved code redemption, HttpOnly-cookie resume, authoritative state fetch,
  serialized polling, hidden-tab suspension, and stale-prose disclosure.
- Replaced blocking send alerts with a polite inline composer status.
- Preserved the last transcript and unsent input when refresh or send fails.
- Added a visible connection-loss notice and explicit Reconnect action without
  clearing guest state.
- Added busy, focus, status, keyboard, and 44px mobile-control behavior.

## Evidence

- `screenshots/guest-join-430.png`
- `screenshots/guest-play-mobile.png`
- `screenshots/guest-play-1440.png`
- `browser_tests/test_ui_guest.py`
- `tests/test_guest_page.py`
- `tests/test_stale_surface.py`

## Qualification

- 3 focused guest entry, inline-failure, recovery, draft, and viewport browser checks.
- 93 combined replacement-surface browser checks.
- 99 guest, stale-surface, lightweight-theme-entry, and catalog checks.
- English extraction and English/Japanese catalog-key parity.
