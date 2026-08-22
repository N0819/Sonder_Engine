# WP-03 application-shell review findings

**Review date:** 2026-08-22
**Scope:** the authenticated `/ui-next` shell at G2, before Play, Library, and
Settings product workflows are implemented.

## Product-flow review

- Play, Library, and Settings are the only primary destinations. The same
  navigation element becomes the mobile bottom bar; there is no hidden second
  set of controls.
- The temporary landing panel and its laboratory/runtime links are gone.
- Play contains only story context and the Story Tools entry. The nonfunctional
  More button was removed instead of being presented as an action.
- Library counts come from the one bootstrap projection. Settings category
  names are orientation copy, not editable controls. Empty, unavailable, and
  invalid-link states do not claim later workflows are complete.
- Go To contains only routes that the shell can currently render. Extension
  views appear as explicitly labelled Add-on Views and never become a fourth
  primary destination.

## Visual-system review

- The frame uses the WP-01 tokens, four curated theme sheets, local SVG sprite,
  square geometry, indexed rail, restrained borders, and neutral chrome.
- The attached candidate informed the indexed rail and three-zone composition.
  Its private ids, hidden classic controls, `!important` rules, global state,
  synthetic clicks, polling, mutation observers, and cosmetic route switching
  were not carried over.
- Headers preserve an orientation line, one level-one destination heading,
  context, save truth, and the context-panel action. Later workflow actions are
  not mocked into the frame.

## Responsive review

- Compact, medium, wide, and expansive are executable layout states selected
  from viewport geometry, including short landscape behavior.
- The compact shell retains the three-item bottom navigation, safe-area
  padding, a staged inspector sheet, and one 44px-or-larger Go To control.
- A long-Japanese plus large-UI run found the fixed Go To control trapped in
  the navigation stacking context beneath the wrapping header. The compact
  navigation stacking context and header text reservation were corrected; the
  pointer journey now passes without horizontal page overflow.
- The full reference matrix passes with every primary destination visible and
  at least 44 CSS pixels high. The 640×360 case stands in for 200-percent zoom
  on a 1280×720 CSS workspace.

## Accessibility and localization review

- The frame exposes skip navigation, named navigation/main/complementary
  landmarks, a single level-one heading, current-page state, named dialogs and
  sheets, focus containment/restoration, and restrained live regions.
- Back closes inspector and Go To layers before leaving their destination.
  Focus identities and scroll offsets are serializable strings/numbers; no DOM
  node is retained in history or browser-local state.
- Shortcut dispatch rejects collisions and ignores ordinary shortcuts during
  input, selection, contenteditable work, key repeat, and IME composition.
- Dynamic shell copy is now inside the replacement UI catalog boundary. English
  and Japanese catalogs have exact key parity, and the long-Japanese test also
  exercises high contrast, solid surfaces, strong focus, large UI/prose, roomy
  targets, and reduced motion together.

## Deferred by design

Transcript/composer behavior, Library browsing/editing, Settings editing,
auth/guest visual replacement, public extension v2, compatibility mode,
cutover, and classic deletion remain owned by WP-04 through WP-14. G2 evidence
must not close any of those requirements.
