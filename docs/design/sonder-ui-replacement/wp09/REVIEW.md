# WP09 New Story visual checkpoint

## Reference authority

- `04_desktop_new_story.png` for the modal frame and three-route choice ledger.
- The supplied candidate's `remaster-components.css` for measured route-card and compact-dialog geometry.
- Design Bible onboarding requirements `ONB-01` through `ONB-08`.

The supplied candidate contains the reference CSS and screenshot but no New Story JavaScript.
This package ports that composition onto current Sonder creation and association APIs.

## Implemented

- Replaced the two-path legacy wizard with one guided flow and the supplied three entry routes.
- Kept Start blank and saved-Library workflows usable without an AI provider.
- Allowed saved and generated personas, characters, and lore to be mixed before creation.
- Preserved setup progress as an owner-scoped browser-local draft with resume and discard.
- Added language selection, optional-field guidance, review/edit navigation, and explicit model-cost copy.
- Blocked only selected generation actions when no default text model is configured and linked recovery to AI Connections.
- Surfaced generated-card warnings before final story creation.
- Preserved the complete draft after API failure and allowed an in-place retry.
- Created only ordinary current-schema stories through the existing chat, persona, character, and lore routes.
- Ported compact New Story to a full-screen staged dialog with 44 px controls and no page overflow.

## Evidence

- `screenshots/new-story-choice-1440.png`
- `screenshots/new-story-details-1440.png`
- `screenshots/new-story-assets-1440.png`
- `screenshots/new-story-review-1440.png`
- `screenshots/new-story-choice-390.png`
- Focused browser contracts: `8 passed` in `browser_tests/test_ui_new_story.py`.
- Cross-surface browser regression: `87 passed` across New Story, Library, Settings,
  shell, and Play.
- Source contracts: `14 passed` across shell, Play, and Library.
