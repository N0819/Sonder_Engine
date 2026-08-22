# Sonder UI Design Bible adoption audit

**Audit date:** 2026-08-21

**Current repository authority:** `1accd28` (branch `interface`, matching `origin/offscreen` after the offscreen fast-forward; `main`/`origin/main` remain at `09985af`)

**Candidate implementation baseline:** `73a380a0df2f6b139c98d66da9005489bd549d1d`

**Candidate baseline drift:** the current implementation head is 78 commits ahead

**Decision:** selectively adopt and harden; do not copy the candidate repository wholesale

## Purpose

This document decides how to use the supplied Sonder UI Design Bible, revision
candidate, screenshots, and revision audit. It is an adoption audit, not an
implementation plan and not an approval to make the attached documents
repository authority.

The attached documents are treated as proposed requirements and evidence from
another implementation effort. Current Sonder source, maintained guides,
runtime contracts, and tests remain authoritative until an adopted UI contract
is reviewed and committed here.

## Material reviewed

- `Sonder_UI_Design_Bible_1.0_2026-08-20.zip`
- `README(20260821-134753).md`
- `21_DESIGN_BIBLE_REVISION_AUDIT.md`
- `Sonder_Engine_UI_Design_Bible_Revision-main.zip`
- `Sonder_UI_Design_Bible_Revision_Screenshots.zip`
- current `Design.md`, `docs/CODE_MAP.md`, and maintained guides
- current frontend, authentication, guest, extension, localization, and browser
  test sources

The repository snapshot was refreshed after the offscreen work advanced
`interface` from `09985af` to `1accd28`. Those 12 commits changed no files under
`static/` or `web/` and did not change either current UI catalog, so they do not
alter the UI dispositions below.

The candidate adds roughly 2,677 lines and removes 248 lines across 25 frontend
files relative to its stated baseline. Its principal additions are four
remaster CSS files, nine native JavaScript modules, an SVG symbol sprite,
revised host/auth/guest markup, and remaster-specific tests.

## Evidence vocabulary

| Grade | Meaning |
|---|---|
| **Confirmed-current** | Read or executed against current `1accd28`. |
| **Verified-candidate** | Reproduced directly from the extracted candidate. |
| **Candidate-reported** | Claimed by the supplied audit but not reproduced in this environment. |
| **Visual-only** | Demonstrated by a supplied screenshot, without behavioral proof. |
| **Not demonstrated** | No adequate source, test, or runtime evidence was found. |

## Disposition vocabulary

| Decision | Meaning |
|---|---|
| **Accept** | The artifact can be brought forward with only current-baseline integration and normal review. |
| **Adapt** | Preserve the design or implementation core, but change its integration or fill bounded gaps. |
| **Rebuild** | Preserve the requirement or visual reference, but replace the candidate implementation. |
| **Reject** | Do not carry this candidate artifact or approach forward. |
| **Defer** | Keep current behavior until a later complete workflow slice replaces it. |

## Executive finding

The candidate is a credible visual and shell prototype, not a completed Design
Bible implementation. Its screenshots, design tokens, icon language,
responsive composition, theme direction, entry-page treatment, and much of its
new-story work are valuable. The safest and least wasteful path is to port those
parts onto current Sonder. This hybrid disposition describes which candidate
source is salvaged versus rebuilt; it does not describe the finished product.
The approved end state is a full replacement of the legacy host UI.

The candidate's product-depth and compatibility claims are materially ahead of
the implementation:

- its Library scopes change explanatory text but do not scope results;
- its Settings search filters only launchers in the active category, not all
  settings or aliases;
- its hash router does not open a story named by `#/play/<id>`, model transient
  sheets in history, or explain invalid targets;
- its state bridge polls the legacy global every 500 ms and detects only a small
  signature of possible changes;
- story tools and Settings launchers operate by clicking legacy DOM controls;
- its extension slot API is installed after the extension bundle has already
  loaded, has no slot consumers, and is not included in existing owner teardown;
- new remaster copy is hard-coded in English instead of using Sonder's UI
  language-pack path;
- mobile CSS hides both vitals surfaces rather than preserving the capability;
- legacy top-action controls are moved off-screen but remain focusable;
- the per-story composer-draft bridge has no test for switching stories while a
  non-empty draft is present;
- the downloadable candidate omits the current LCARS font binaries.

These findings contradict the supplied release audit's conclusion that no P1
parity, routing, or unreachable-control issue remains. They do not make the
candidate worthless. They change its role from release candidate to high-value
porting source.

## Product and subsystem adoption matrix

| Subsystem | Bible/candidate intent | Candidate evidence | Current Sonder authority or collision | Finding | Decision | Required acceptance evidence |
|---|---|---|---|---|---|---|
| Design governance | Make one coherent Bible the UI authority with controlled deviations. | Thirty focused Bible chapters, templates, checklists, and a decision register. **Verified-candidate.** | `AGENTS.md`, `Design.md`, and `docs/guides/` are maintained authority; `docs/design/` is context. | The proposed governance is useful, but the attachment cannot appoint itself as authority. Requirements also overstate completed implementation. | **Adapt** | Reconcile the Bible with current contracts, record accepted deviations, and commit the approved version in the maintained guidance set or explicitly link it from that set. |
| North star and product character | Quiet, precise, genre-neutral instrument around the story. | Consistent visual treatment across 16 supplied states. **Visual-only.** | `Design.md` requires a genre-agnostic substrate and player-first fiction experience. | Direction is aligned with current product principles and avoids a genre-specific shell. | **Accept** | User design review plus live screenshots using current stories and extensions. |
| Tokens and soft-precision geometry | Semantic surfaces, compact radii, consistent spacing, typography, status, motion, and z-order. | `remaster-tokens.css`, `remaster-components.css`; source tests assert representative tokens. **Verified-candidate.** | Current `static/themes.css` and `static/styles.css` already own many layout/theme values. | Strong foundation, but it is layered over legacy selectors rather than completing a clean token boundary. | **Adapt** | Token inventory, contrast review, representative component states, and proof that legacy themes cannot change remaster geometry. |
| Curated themes | Carbon Signal default plus Ash and Brass, Midnight Ink, and Parchment Night; existing themes grouped as Legacy. | Theme registry, CSS variables, screenshots, and one browser persistence test. **Verified-candidate** for source; Chromium run **candidate-reported**. | Current theme storage and first-paint behavior live in `static/js/theme-init.js`, `static/js/themes.js`, and `static/themes.css`. | Direction and migration shape are sound. Candidate archive removal of current fonts is not. | **Adapt** | Current-theme migration tests, first-paint test, every curated theme at core states, legacy-theme smoke, and no deletion of current font assets. |
| Icon system | Local SVG monoline family, icon-first frequent actions, labels retained where needed. | Sprite contains at least 48 symbols; focused source test passes. **Verified-candidate.** | Current UI uses text, glyphs, emoji, and extension-provided icons. | Sprite and helper are reusable. The whole-body mutation enhancer is transitional and may repeatedly rescan all buttons during transcript/UI mutation. | **Adapt** | Accessibility-name audit, performance measurement on long/streaming stories, explicit component icons, and a retirement plan for heuristic glyph matching. |
| CSS architecture | Additive remaster layers override classic CSS while migration proceeds. | Four ordered CSS files and responsive screenshots. **Verified-candidate/visual-only.** | Current frontend is unbundled and load-order sensitive. Extension CSS may rely on documented tokens and existing host placement. | A controlled additive phase is appropriate, but `remaster-shell.css` uses many ID selectors and `!important` rules, including hiding legacy controls off-screen. It should not become permanent architecture. | **Adapt** | Specificity inventory, extension fixture, focus-order audit, and an explicit removal condition for every compatibility override. |
| Application shell | Play, Library, Settings; desktop left/center/right; mobile bottom navigation. | Real markup, CSS, router, shell module, and representative screenshots. **Verified-candidate/visual-only.** | Current IDs and classic scripts are used by host and extensions. | The shell is the strongest implementation asset. It should be ported behind a controlled switch before becoming default. | **Adapt** | Visible navigation journeys, no lost current capabilities, keyboard order, mobile safe areas, intermediate widths, and exact current-state preservation. |
| Router and history | Stable routes, deep links, useful fallbacks, Back closes sheets before destinations. | `router.js` parses three destinations and a first subpath. **Verified-candidate.** | Current story selection remains owned by `openChat`; existing overlays have their own lifecycle. | Candidate route depth is cosmetic. `#/play/<id>` is generated but not opened on route load; transient surfaces do not participate in history; invalid targets silently become Play. | **Rebuild** | Route contract tests for story IDs, Library scopes/items, Settings sections, inspector tools, Back/Forward, refresh, deleted/disabled targets, focus restoration, and plain fallback messages. |
| Host state boundary | New modules read current host data without creating a second store. | Candidate exports lexical `S` as `window.S`, reads it through `hostState`, and polls a six-field signature. **Verified-candidate.** | `static/js/utils.js` owns `S`; current async ownership guards protect stale responses and visible-story state. | Exporting the same object avoids a duplicate store, but indefinite polling and DOM-click integration are weak event boundaries. The signature misses renames and many same-count updates. `router.js` also bypasses the declared bridge. | **Rebuild** | One current-state facade, explicit events/selectors, no polling, no remaster module direct access to private globals, stale-response tests, and teardown. |
| Play reading surface | Story-first transcript, aligned literary composer, quiet chrome, backdrop framing. | Desktop, tablet, mobile, narrow, and empty screenshots; CSS mostly preserves current transcript markup. **Visual-only**, with source structure verified. | `static/js/chat.js`, backdrop/ambience/weather modules, and current browser tests own rendering and streaming behavior. | Visual composition is good and leverages mature current behavior instead of rewriting it. | **Adapt** | Real current story with long transcript, streaming, rerolls, frames, backdrops, weather, speech coloring, scrollback, reduced motion, and no line reflow. |
| Composer and drafts | Per-story recoverable drafts across navigation, failure, and refresh. | Local-storage draft code in `shell.js`; no targeted draft-switch browser test found. **Verified-candidate source; not demonstrated behavior.** | Current `runStream`, story switching, and error recovery own input clearing and request state. | Current key switching can retain the previous story's non-empty input when the selected story changes; it relies on incidental legacy behavior. | **Rebuild** | Story A/B draft isolation, refresh, failed send, successful send, abort, story deletion, storage failure, mobile keyboard, and no cross-story text leakage. |
| Turn status and actions | Clear Send/Stop/progress/cancel states without overwhelming prose. | Revised markup/CSS uses existing turn status and stream functions. Some current browser stream tests use the shell. **Candidate-reported** for full Chromium. | `static/js/chat.js` is behavioral authority. | Good visual adaptation; do not replace the working stream state machine. | **Adapt** | Visible current-browser tests for start, token, phase, early narration, abort, completion, retry/error, and session expiry. |
| Story tools inspector | Contextual right inspector; mobile full-screen surface; resize, pin, focus restoration. | `inspector.js` and responsive CSS implement shell lifecycle. **Verified-candidate source; visual-only behavior.** | Existing tools are modals/drawer entry points owned by `settings.js`, `chat.js`, ambience, and backdrop modules. | Launcher shell is reusable, but most tools immediately click legacy controls rather than render inside the inspector. Pinning does not create a complete tool-host contract. | **Adapt** shell; **rebuild** tool integration | Tool-by-tool ownership map, current story-switch tests, focus/resize/pin tests, mobile Back/Escape, active-run preservation, and zero hidden duplicate controls. |
| Condition/vitals | Keep condition indicators informative without covering story or composer. | Bible requires parity; candidate mobile CSS sets `#vitals,#vitals-npcs { display:none!important; }`. **Verified-candidate.** | Current vitals UI carries player and NPC condition information. | Candidate removes a capability on mobile instead of relocating or staging it. | **Rebuild** mobile treatment | Mobile-accessible condition route/HUD, collision tests, active-story accuracy, and parity review. |
| Unified Library shell | Stories, Characters, Personas, Lore in one destination with search, scope, recent records, and context. | Attractive shell, type tabs, current bootstrap counts, recent story list, and search. **Verified-candidate/visual-only.** | Current lists and full lore workspace already operate through `app.js` and `lorebooks.js`; association routes exist in `web/app.py`. | Shell and information architecture are valuable. It remains a wrapper around current side lists. | **Adapt** | Use current APIs and editors through explicit Library interfaces; test all content types, loading/error/empty states, and current-story accuracy. |
| Library scopes and association semantics | All, Current Story, Choose Story, Unassigned, Used in Multiple Stories; detach never deletes. | Selector and explanatory copy exist. `updateScopeNote` does not filter records or select a story. **Verified-candidate.** | Current chat-character/persona/lorebook associations and archives are server-owned. | This is presentation-only and must not be shipped as if scoped results are real. | **Rebuild** | Server-backed or authoritative client projection, scope fixtures, attach/detach/delete distinction, multi-story counts, unavailable records, and archive/branch integrity. |
| Library search, sorting, favorites, drafts | Global cross-type discovery and stable filters. | Search filters only current `#sidelist .item`; sorting/favorites/drafts are absent. **Verified-candidate.** | Current lists are type-specific and may not expose all required metadata. | Candidate does not satisfy the Bible contract. | **Rebuild** | Search index/data contract, filters, sorting, recent/favorite/draft definitions, URL persistence, loading/no-result distinction, and mobile parity. |
| Library editors | Routed desktop detail panes and mobile staged editors with recoverable drafts. | Candidate deliberately keeps complex editors in compatibility dialogs. **Candidate-reported deviation.** | Current editors and lore workspace contain mature field preservation and state guards. | Keep current editors during early shell adoption; do not rebuild them merely for visual consistency. Migrate one editor family at a time later. | **Defer**, then **adapt** | Field-completeness diff, draft/save/error tests, mobile interaction, localization, import/export, and unchanged persistence semantics. |
| Settings information architecture | Experience, AI Connections, Content, Add-ons, Maintenance, Advanced. | Indexed categories and grouped launchers. **Verified-candidate/visual-only.** | Current settings functionality is spread across `settings.js`, themes, extension menu, and host routes. | Category model and presentation are useful. | **Adapt** | Complete control inventory; every current setting maps to one new category and remains reachable on desktop/mobile. |
| Settings search and deep links | Search all settings and aliases; stable section/control routes. | Candidate filters launchers only inside the rendered category and routes only the category. **Verified-candidate.** | Current settings have no canonical search index. | Candidate is materially shallower than the requirement. | **Rebuild** | One searchable registry, aliases/localized terms, control-level focus, invalid target handling, and Back/Forward tests. |
| Settings actions and saving | Consistent save/failure/restart state; consequential changes explicit. | Candidate launchers click legacy buttons; no shared save-state implementation exists. **Verified-candidate.** | Current settings retain route-specific save and safety behavior. | Preserve working semantics until each settings group is explicitly migrated. | **Defer**, then **adapt** | Action inventory, failure injection, unsaved input preservation, destructive confirmations, scoped resets, and current route tests. |
| New Story and first run | Describe a Story, Use My Library, Start Blank; generation alone requires AI. | `app.js` adds three working routes, checks connectivity only for generation, and uses existing creation routes. **Verified-candidate source.** | Current `newChatWizard`, creation APIs, language choice, card warnings, and current first-run setup are authority. | This is one of the most reusable behavioral changes. It must be rebased over post-baseline first-run/card-warning work. | **Adapt** | All three visible journeys, provider absent/present, empty/existing Library, cancellation, validation, card warnings, language, current-story opening, mobile, and failure recovery. |
| Authentication | Shared visual language without weakening trusted-event, cooldown, lockout, or password behavior. | Candidate restyles `login.html`; existing focused browser tests remain. **Verified-candidate source; candidate-reported browser.** | `web/auth_routes.py`, `static/login.html`, and login lockout tests are authority. | Mostly presentational and suitable for selective port. | **Adapt** | Current lockout/trusted-event suite, autocomplete, error/live-countdown visibility, keyboard, mobile, and session redirect. |
| Guest play | Shared entry/play language while preserving join, polling, visibility, stale-response, and inline error behavior. | Candidate restyles `guest.html` and retains existing script. **Verified-candidate source; candidate-reported browser.** | `web/guest_access.py`, `static/guest.html`, and guest tests are authority. | Suitable for selective styling; must remain a separate lightweight surface with no host extension bundle. | **Adapt** | Join/resume, waiting/stale turn, send error, visibility pause, session end, keyboard/mobile, and no host-only information. |
| Accessibility preferences | Structural accessibility plus reversible contrast, focus, motion, scale, spacing, transparency, and status options. | Preference store, CSS token overrides, modal focus trap, and screenshots. **Verified-candidate source; limited behavior evidence.** | Current semantics, focus behavior, themes, and motion effects remain distributed across classic UI. | Good foundation, incomplete proof. Turning reduced motion off does not explicitly restore the previous effects preference; many pixel-sized legacy controls are outside the token system. | **Adapt** | Keyboard audit, focus order/restore, target-size sweep, reversible preference tests, text scaling/reflow, status without color, OS preferences, screen-reader notes, and all legacy dialogs. |
| Responsive/mobile shell | Safe areas, dynamic viewport, virtual-keyboard offset, full-screen inspector, bottom navigation. | CSS and 16 representative screenshots; two new geometry tests. **Verified-candidate/visual-only.** | Current responsive behavior and browser tests cover some mature components. | Strong direction, but screenshots at selected widths are not continuous resize or capability proof. | **Adapt** | Continuous resize sweep, 360–1440 widths, 640x360/844x390, zoom/text scaling, actual virtual keyboard, intermediate widths, no overflow, and capability matrix. |
| Localization and terminology | Plain player language through current UI language packs; user/story data never translated. | Candidate terminology is clear, but remaster modules and most new markup hard-code English. **Verified-candidate.** | `static/js/utils.js`, `static/js/i18n.js`, `language_packs/*/ui.json`, and localization tests own the rules. Current Japanese remains draft quality but is an active contract. | Candidate violates the proposed localization requirement and would create untranslated remaster surfaces. | **Rebuild** integration | Extract every new UI string, preserve `translate="no"` data boundaries, test long strings and non-English packs, and update catalog integrity tests. |
| Extension compatibility | Preserve v1, add versioned slots for Settings, Library, Play, destinations, and tasks. | `bridge.js` adds `uiVersion`, `registerSlot`, and `slots`. No consumers or tests were found. It loads after `/api/extensions/ui.js`. **Verified-candidate.** | `static/js/extensions.js` owns attribution, id-bound facades, failure containment, hot load/unload, and owner teardown. | Candidate v2 is nonfunctional as a page-load contract and bypasses teardown. Existing extensions load before `registerSlot` exists; registered slots are rendered nowhere. | **Reject** candidate v2; **preserve** v1; later **rebuild** v2 | Versioned public contract, page-load and hot-load registration, owner attribution, render consumers, error charging, disable/retire cleanup, route fallback, CSS containment, classic and ES-module fixtures. |
| Notifications, tasks, and errors | Shared persistent tasks and contextual recoverable errors; toasts only for acknowledgements. | Candidate mostly reuses legacy toast/activity surfaces; no comprehensive new task/error system. **Verified-candidate.** | Current components, background-task handling, standing extension notices, and route-specific errors are authority. | Visual styling can port now; behavioral unification is separate work. | **Adapt** visuals; **defer** behavioral consolidation | Inventory all async workflows, loading vs confirmed-empty states, cancellation, failure recovery, session expiry, notices, and no work loss. |
| Tests and release evidence | Close every requirement with source, browser, responsive, accessibility, extension, localization, performance, and full-suite evidence. | 13 remaster delivery tests pass locally; all nine modules pass `node --check`. Candidate reports 52 browser tests and 8,239 full tests. **Verified-candidate** only for the first two facts. | Current `docs/guides/TESTING.md` requires actual unbundled-browser testing for event wiring, navigation, focus, and persistence. | Most new delivery tests assert source strings. Only two new layout tests were found; the 52 count includes many pre-existing browser behaviors. Supplied historical passes do not prove a port onto the current implementation head. | **Adapt** test assets; **reject** historical pass as current acceptance | Red tests on current first, focused slice suite, actual current Chromium journeys, extension and localization gates, `make map`, `make structure`, full suite, and exact-head evidence. |
| Packaging and repository copy | Downloadable implementation can be copied into Sonder. | Full snapshot archive, packaging notice, deleted font binaries. **Verified-candidate.** | Current repo contains 78 later commits and post-baseline UI changes in `static/js/settings.js`, `static/js/lorebooks.js`, and English/Japanese UI catalogs. | Whole-tree copy would revert current engine and UI work. Archive line-ending normalization also obscures real diffs. | **Reject** | Apply selected changes as scoped patches against current files; preserve current binary assets and unrelated history; inspect every legacy-file diff. |
| Legacy removal | Remove old CSS, globals, IDs, and dialogs after migration. | Candidate retains classic scripts and hides some old controls. **Verified-candidate.** | Current extensions and mature workflows depend on documented globals and host-owned mount points. | Removal is appropriately deferred, but hidden duplicate controls are not a satisfactory steady state. | **Defer** | Supported-caller search, extension migration, browser replacement tests, localization closure, no off-screen focusables, and rollback no longer required. |

## File-level disposition

| Candidate path | Decision | Notes |
|---|---|---|
| `docs/design/sonder-ui-bible/**` | **Adapt** | Import only after reconciling authority, contradictory completion claims, current extension/i18n contracts, and approved deviations. |
| `docs/design/sonder-ui-remaster/**` | **Reference** | Valuable requirements/history; do not copy implementation status as fact. |
| `static/assets/icons/sonder-icons.svg` | **Accept** into a spike | Retain accessible labels in consumers and verify license/provenance already recorded by the package. |
| `candidate/static/css/remaster-tokens.css` | **Adapt** | Strong semantic foundation; merge with existing variables deliberately. |
| `candidate/static/css/remaster-components.css` | **Adapt** | Keep components; reduce compatibility specificity and audit every state. |
| `candidate/static/css/remaster-shell.css` | **Adapt substantially** | Preserve layouts; remove hidden-focus traps, mobile capability deletion, and permanent legacy-ID dependence. |
| `candidate/static/css/remaster-entry.css` | **Adapt** | Suitable for auth/guest after behavior and localization verification. |
| `static/js/remaster/icons.js` | **Adapt** | Keep explicit icon helper; constrain and eventually retire heuristic whole-body enhancement. |
| `static/js/remaster/accessibility.js` | **Adapt** | Keep preference shape; make effects reversible and integrate every component family. |
| `static/js/remaster/main.js` | **Adapt** | Keep native-module entry; initialize only supported modules and provide teardown/test seams. |
| `static/js/remaster/router.js` | **Rebuild** | Candidate implements only destination switching, not the stated route contract. |
| `static/js/remaster/bridge.js` | **Rebuild** | Replace polling/DOM clicks; reject embedded extension v2 implementation. |
| `static/js/remaster/shell.js` | **Adapt** | Keep shell interactions; replace inline styles, polling dependency, and fragile draft logic. |
| `static/js/remaster/inspector.js` | **Adapt shell / rebuild hosting** | Keep layout/focus/resize ideas; define real tool mounts and history behavior. |
| `static/js/remaster/library.js` | **Rebuild behavior** | Reuse visual components; implement authoritative scopes, search, state, and editors. |
| `static/js/remaster/settings.js` | **Adapt IA / rebuild registry** | Reuse categories/theme presentation; build global searchable registry and real settings mounts. |
| `static/index.html` | **Adapt carefully** | Rebase markup onto current script IDs/order; never replace wholesale. |
| `static/js/app.js` candidate diff | **Adapt** | Three-route New Story is valuable; rebase onto current first-run and card-warning behavior. |
| `static/js/chat.js` candidate diff | **Adapt** | Turn index attribute is small; verify extensions/tests and avoid unrelated replacement. |
| `static/js/theme-init.js`, `themes.js`, `themes.css` | **Adapt** | Merge registry/tokens without deleting current fonts or theme behavior. |
| `static/login.html`, `static/guest.html` | **Adapt styling only** | Preserve current security/session/polling logic exactly unless separately tested. |
| `language_packs/*/ui.json` | **Merge, never replace** | Current catalogs changed after candidate baseline; all new remaster strings must be extracted. |
| Candidate snapshot: tests/test_ui_remaster_delivery.py | **Adapt** | Keep structural tripwires; add behavioral tests instead of treating source presence as closure. |
| Candidate snapshot: browser_tests/ui_helpers.py | **Adapt** | Useful visible navigation helpers. |
| Candidate snapshot: browser_tests/test_ui_remaster_layout.py | **Adapt** | Keep geometry checks; add full production-page journeys and continuous viewport coverage. |
| deleted `static/fonts/*.woff2` | **Reject deletion** | The candidate archive's redistribution choice must not delete assets already in Sonder. |

## Mandatory corrections before any default switch

The following are release-blocking for the adopted UI even if the candidate
screenshots are approved:

1. Replace archive copying with scoped patches against the current implementation
   head.
2. Replace polling and DOM-click integration with a documented state/action
   boundary.
3. Make deep links and browser history truthful.
4. Implement real Library scopes/search/association semantics or label the
   surface explicitly as an unscoped compatibility view during development.
5. Preserve mobile access to condition/vitals information.
6. Remove off-screen focusable legacy controls.
7. Extract all new UI copy through the language-pack contract.
8. Preserve current extension v1 behavior; do not advertise extension v2 until
   registration, rendering, attribution, failure containment, and teardown all
   work.
9. Prove per-story draft isolation and failure recovery.
10. Re-run browser and full-repository verification on the exact final current
    head; historical candidate results are supporting evidence only.

## Recommended implementation order

### Slice 0: baseline and behavioral inventory

- Record the exact implementation head and preserve a clean rollback point.
- Capture current desktop/mobile behavior for Play, Library, Settings, New
  Story, auth, guest, and representative extensions.
- Add red browser tests for the compatibility failures identified above.
- Create the current-to-new capability map before hiding or moving controls.

### Slice 1: additive visual foundations and controlled shell

- Port the icon sprite, tokens, component primitives, curated theme registry,
  entry styling, and shell layout behind a controlled development switch.
- Keep current routes, data, scripts, and extension v1 contract authoritative.
- Build the evented host-state/action facade before porting product behavior.

This slice is the adoption checkpoint. If the candidate shell cannot operate on
current state without expanding DOM-click shims, retain the visual assets and
rebuild the shell logic cleanly.

### Slice 2: Play as a complete workflow

- Port the shell/header/transcript/composer composition.
- Implement draft isolation, Story Tools hosting, mobile conditions, focus,
  history, and current streaming/error states.
- Verify backdrops, ambience, weather, frames, rerolls, extensions, and long
  transcript performance.

### Slice 3: Library semantics before Library polish

- Define the authoritative Library projection and association queries.
- Implement truthful scopes, global search, sorting, states, and item routes.
- Preserve current editors initially; migrate editor families only after the
  shell semantics pass.

### Slice 4: Settings registry

- Build one category/search/alias/route registry.
- Mount existing safe settings behaviors through explicit adapters.
- Migrate each settings group with save/failure/reset tests rather than hiding
  legacy buttons and clicking them.

### Slice 5: first use, auth, and guest

- Rebase the candidate's three-route New Story work.
- Port entry styling while retaining current auth and guest behavior.
- Complete localization, mobile keyboard, and recovery journeys.

### Slice 6: extensions, themes, and compatibility retirement

- Design extension v2 separately from the candidate bridge and ship it only
  with complete lifecycle proof.
- Migrate representative extensions and legacy themes.
- Remove compatibility CSS, globals, and duplicate controls only after every
  supported caller and test is migrated.

## Acceptance gates for every slice

Every slice must supply:

- code and requirements mapped to the exact current head;
- a focused red/green regression set;
- actual unbundled-browser journeys, not source assertions alone;
- desktop, tablet, mobile portrait, narrow, landscape, short-height, and
  intermediate-width evidence where applicable;
- keyboard/focus and mobile touch evidence;
- localization and user-data translation-boundary evidence;
- extension compatibility evidence when a host mount or token changes;
- no engine, persistence, archive, checkpoint, or information-boundary drift;
- focused tests first, then `make map`, `make structure`, the relevant browser
  suite, and the full repository gate before integration.

## Final recommendation

Proceed with a **hybrid adoption**.

Here, hybrid means selective candidate-source adoption. It does not mean
shipping old and new host interfaces together. The complete program ends with
the legacy shell, compatibility CSS, hidden controls, obsolete dialogs, and
classic host implementation removed after their replacements pass their gates.

The candidate likely saves most of the visual-design effort and a meaningful
portion of shell, theme, entry, icon, responsive, and New Story implementation
work. It does not save the product-depth work for Library, Settings, routing,
state integration, localization, extensions, or complete accessibility proof.

Do not choose between “copy everything” and “start over.” Port the strong
artifacts into a controlled current-head slice, and use the first shell spike to
decide exactly how much of the remaining JavaScript deserves adaptation versus
replacement.
