# Candidate salvage ledger

**Candidate:** `73a380a0df2f6b139c98d66da9005489bd549d1d`  
**Current program baseline:** `c1efafabee972be40f277b5f23f36e138d2a1d04`

This is a file-level evidence map, not work status. No row authorizes replacing
a current file with the older candidate snapshot. “Adapt” means port the named
core as a scoped patch and prove it against current contracts; “rebuild” keeps
the requirement or visual reference but not the mechanism.

| Candidate artifact | Disposition | Target | Acceptance evidence |
|---|---|---|---|
| `docs/design/sonder-ui-bible/**` | accept as reconciled reference | WP-00 | Imported manifest integrity; maintained `INTERFACE.md` authority boundary |
| `docs/design/sonder-ui-remaster/13_REQUIREMENTS_TRACEABILITY.md` | adapt | WP-00 | 170 unique rows, 15 families, current work-package ownership, audit corrections |
| other `docs/design/sonder-ui-remaster/**` | reference | applicable WP | Claims checked against current source; no historical status copied |
| `static/assets/icons/sonder-icons.svg` | accept into component laboratory | WP-01 | Provenance, SVG lint, accessible consumers, complete inventory |
| `candidate/static/css/remaster-tokens.css` | adapt | WP-01 | Semantic-token inventory, contrast, all component states, no duplicate theme truth |
| `candidate/static/css/remaster-components.css` | adapt | WP-01 | State laboratory, keyboard/touch behavior, reduced compatibility specificity |
| `candidate/static/css/remaster-shell.css` | adapt substantially | WP-03 | No hidden focusables/mobile capability loss/private-ID steady state |
| `candidate/static/css/remaster-entry.css` | adapt | WP-10, WP-11 | Current auth/guest behavior, localization, keyboard/mobile evidence |
| `static/js/remaster/icons.js` | adapt | WP-01 | Explicit icon consumers; bounded heuristic enhancement with retirement owner |
| `static/js/remaster/accessibility.js` | adapt | WP-01, WP-08 | Reversible preferences and complete component integration |
| `static/js/remaster/main.js` | adapt | WP-02 | Native bootstrap, explicit teardown, no implicit global/polling dependency |
| `static/js/remaster/router.js` | rebuild | WP-03 | Truthful story/item/tool deep links, history, fallback, focus restoration |
| `static/js/remaster/bridge.js` | reject mechanism | WP-02 | Explicit state/actions/events; no `window.S`, polling, DOM clicks, or embedded v2 API |
| `static/js/remaster/shell.js` | adapt interaction ideas | WP-03, WP-04 | Imported state contracts, draft isolation, no inline layout ownership |
| `static/js/remaster/inspector.js` | adapted shell; rebuilt hosting complete | WP-03, WP-05 | [G3 Story Tools review](G3_STORY_TOOLS_REVIEW.md): real mounts, route/history lifecycle, pin/resize/focus, staged mobile, and state preservation |
| `static/js/remaster/library.js` | rebuilt; visual hierarchy selectively adapted | WP-06 | [WP-06 Library review](WP06_LIBRARY_REVIEW.md): authoritative projection, scopes, search, associations, lifecycle, deep links, responsive detail, and 1,000-item bound |
| `static/js/remaster/settings.js` | adapt IA, rebuild registry | WP-08 | Global localized search/aliases, control routes, real mounts and save states |
| candidate `static/index.html` | reference and scoped adaptation only | WP-03, WP-04 | Current script/ID/API/extension behavior preserved; no whole-file copy |
| candidate `static/js/app.js` New Story changes | adapt | WP-09 | Current warnings/language/provider behavior plus all three journeys |
| candidate `static/js/chat.js` changes | adapt only when owned | WP-04 | [G3 Play review](G3_PLAY_REVIEW.md): current stream/reroll/frame/scrollback/extension behavior rebuilt without whole-file copying |
| candidate `static/js/theme-init.js` | adapt | WP-01, WP-12 | First-paint migration and every curated/Legacy state |
| candidate `static/js/themes.js` and `static/themes.css` | adapt | WP-12 | Semantic registry, retained current fonts, Legacy mapping, no layout ownership |
| candidate `static/login.html` | adapt presentation only | WP-10 | Trusted-event, cooldown, lockout, autocomplete, session tests |
| candidate `static/guest.html` | adapt presentation only | WP-11 | Lightweight entry, join/resume/error/visibility/session behavior |
| candidate `language_packs/*/ui.json` | merge keys, never replace | every surface WP | Catalog integrity, long/non-English strings, user-data translation boundary |
| `candidate/tests/test_ui_remaster_delivery.py` | reference; adapt only real tripwires | applicable WP | Behavioral tests lead; source checks cannot close workflows |
| `candidate/browser_tests/ui_helpers.py` | adapt | applicable WP | Visible, current-page helpers without hidden-control shortcuts |
| `candidate/browser_tests/test_ui_remaster_layout.py` | adapt | WP-03, WP-14 | Continuous width/zoom/capability evidence beyond selected screenshots |
| deletion of `static/fonts/*.woff2` | reject | WP-12 | Existing licensed local fonts remain present and usable |
| candidate extension slot API | reject and redesign | WP-12 | Page-load/hot-load registration, consumers, attribution, permissions, failure, teardown |
| candidate 500 ms state polling | reject | WP-02 | Zero replacement idle polling; explicit subscription and stale-result tests |
| candidate hidden legacy controls / `clickLegacy` | reject | WP-03, WP-13 | No off-screen focusables or synthetic compatibility actions |

The [adoption audit](../SONDER_UI_DESIGN_BIBLE_ADOPTION_AUDIT_2026-08-21.md)
contains the subsystem reasoning behind these dispositions.
