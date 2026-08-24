# UI cleanup fix list

Status: implemented and verified locally
Owner: interface replacement
Audit date: 2026-08-23
Target branch: `interface`

This ledger collects the visual and interaction defects identified from the
supplied reference screenshots, source tracing, and a deterministic Playwright pass.
It is the working acceptance list for the cleanup. A row is complete only when
its regression test is green and the repaired browser render has been reviewed
at the applicable reference viewports.

## Audit coverage

The Playwright review covered Play, Library, Settings, New Story, authentication,
and guest surfaces at 1440x900, 1280x800, 1024x768, 768x1024, 430x932,
390x844, 360x800, 844x390, 1024x600, and a 200% zoom equivalent. It included
empty, populated, selected-detail, inspector, responsive-sheet, and reduced-
motion states. The supplied Design Bible screenshots remained the comparison
reference; deterministic intercepted API fixtures supplied authenticated state.

Severity follows the Design Bible quality rubric: P0 blocks use, P1 is a major
contract break, P2 is visible polish/consistency debt, and P3 is minor residue.

## Approved fix list

| ID | Priority | Surface | Status | Finding and evidence | Approved repair | Verification |
|---|---:|---|---|---|---|---|
| UI-001 | P1 | Shared overflow / Settings | Fixed | The first repair gave Settings a real detail-pane scroll range, but wheel input over the fixed header/category rail remained dead and keyboard paging from the navigation did not move the detail. This made the page still feel unscrollable unless the pointer happened to be over the right pane. | Keep `[data-settings-content]` as the only vertical owner, make it a named focusable region, clip the inert shell ancestors, and forward vertical wheel plus Page Up/Down/Home/End intent from surrounding Settings chrome. Preserve horizontal category gestures and independent search-result scrolling. Continue enforcing one named overflow owner on the other staged surfaces. | At 1440x900, 1024x600, 390x844, and 844x390, wheel over the category navigation and Page Down from its focused current link move `[data-settings-content]`; the workspace and document remain at `scrollTop == 0`, the final control remains reachable, and the page has no horizontal overflow. Search results retain their own wheel behavior. |
| UI-002 | P1 | Settings / appearance | Fixed | Interface density persists `data-density`, but no stylesheet consumes it. Compact, Comfortable, and Roomy all measured the same 92.09px row and spacing. Roomy also duplicates the accessibility preference. | Keep only Comfortable and Compact, migrate stored Roomy to Comfortable, and make Compact measurably tighten non-target spacing while retaining every control and minimum target. | Browser test compares representative row geometry and reload persistence. |
| UI-003 | P1 | Settings / atmosphere | Fixed | Visual effects writes `data-effects`; motion CSS reads `data-motion`; bootstrap reads legacy `appearance.motion`. Full, Reduced, and Off all retained 180ms motion, and Off did not reliably remove weather. | Make `appearance.effects` and `data-effects` canonical, read legacy `motion` only as migration input, and wire Full/Reduced/Off to motion tokens and decorative weather/backdrop behavior. | Browser tests measure duration, weather visibility, reload persistence, and legacy migration. |
| UI-004 | P2 | Settings / reading | Fixed | Story text size changes prose but gives no visible evidence when no story prose is on screen. | Add a compact prose preview inside Reading and effects that responds immediately without enlarging surrounding controls. | Browser test compares preview font size for Small and Extra large. |
| UI-005 | P1 | Settings / responsive | Fixed | Native Settings selects are 23px high. Search/select controls are 23–36px on phone, below the 44px touch contract. | Give Settings form controls a 36px desktop minimum and 44px compact/touch minimum; preserve full-row checkbox hit areas. | Playwright target scan at desktop, phone, landscape, and short-height viewports. |
| UI-006 | P1 | Play / inspector | Fixed | Navigating Library to Play can leave Library's `Choose an item` body under the `Story tools` title. Store notification invokes a subscriber removed earlier in the same snapshot loop. | Skip subscribers that are no longer live before invoking them. | Store regression plus Library-to-Play browser transition assertion. |
| UI-007 | P1 | Play empty state | Fixed | Empty Play offers only Open Library, leaves a large undifferentiated black stage, and still renders ten inert Story Tool buttons although no story can accept a tool. | Build a deliberate empty stage with primary New Story and secondary Open Library actions; replace inert tools with honest guidance until a story is open. | Empty-state browser test checks actions, dialog launch, inspector guidance, and absence of inert tool rows. |
| UI-008 | P1 | Story Tools | Fixed | Existing Narrow/Default/Wide states only change width; every state still shows index, icon, title, description, and chevron. The container query is a no-op. | Replace width-only states with exactly Expanded (icon + title + description), Compact (icon + title), and Rail (icon only). Migrate legacy Wide to Expanded and Narrow to Compact. | Browser test checks persisted cycle, width, accessible names, and per-mode visible content. |
| UI-009 | P1 | Story Tools | Fixed | Selecting a tool leaves all ten rows above the editor, often putting the editor below the fold. Compact widths cannot safely host editors. | Stage list and detail as separate views with an All tools back control. Temporarily present detail at expanded width, then restore the saved list mode on return. | Short-panel and responsive-sheet tests prove editor visibility, focus, back navigation, and restored mode. |
| UI-010 | P2 | Story Tools / icons | Fixed | Conditions reuses Clothing, Frames reuses Story, and Multiplayer reuses Cast. These are semantically unrelated substitutions. | Give conditions, frames, and multiplayer dedicated local SVG symbols and map each tool to its own icon. | Sprite/DOM test checks unique symbol references and accessible labels. |
| UI-011 | P2 | Shared icons | Fixed | Library More (`…`), Play More (`⋯`), New Story Close (`×`), Story Tool chevrons (`›`), and a Library state marker (`●`) use text-glyph stand-ins. | Replace action glyphs with the existing or new local SVG symbols; render the status marker as CSS geometry rather than text. | DOM/source regression ensures these controls contain SVG and no glyph fallback. |
| UI-012 | P1 | Library | Fixed | The left `Library / Scope / All Library` ledger and central `Library / Your story material` dashboard repeat hierarchy, counts, scope, and creation actions. `libraryHome()` is unconditional and the alternate toolbar path is dead. | Make the left rail category/scope navigation and the center the single searchable material ledger. Remove decorative totals and redundant scope context; keep one create/import action cluster. | Empty/populated Library tests assert one canonical heading, ledger, scope description, and create/import cluster. |
| UI-013 | P2 | Library terminology | Fixed | The same category is called Lore in the rail and Lorebooks in the dashboard. | Use Lore consistently in navigation, totals, headings, and accessible names. | Browser text assertion. |
| UI-014 | P1 | Shared responsive controls | Fixed | Playwright found 36–40px phone controls: Library search/scope/tabs, compact sheet actions, and the landscape Play empty action. | Enforce the 44px touch minimum for actionable controls in compact and phone/landscape layouts without inflating desktop density. | Target-size scan across the reference responsive matrix, including dialog and staged sheet controls. |
| UI-015 | P2 | Play composition | Fixed | Empty Play's stage is visually under-structured and reads as a broken blank region rather than a purposeful starting state. | Bound the empty state with the same stage rhythm, divider/accent language, concise orientation, and action hierarchy as the supplied reference. | Same-viewport screenshot comparison at desktop, phone, and short landscape. |
| UI-016 | P1 | Library / Play boundary | Fixed | Story selection and entering Play are separate user commitments and must not collapse into one click during cleanup. | Keep row activation as selection/detail only. Enter Play only from the explicit **Open in Play** action, retaining the Library route/query until that action is chosen. | Browser regression asserts selection remains on Library, reveals detail, and only the explicit action navigates to Play. |
| UI-017 | P1 | Settings / AI Connections | Fixed | The embeddings assignment exists but is buried with expert role routing and explains the model constraint more clearly than its value to a user. | Add a first-class **Memory search model (embeddings)** control beside the essential model configuration. Explain meaning-based recall, require a vector/embedding model, state that a model change requires rebuilding stored vectors, and link directly to Memory search maintenance. Keep unrelated specialist routing under Advanced. | Browser test changes the model, verifies the preserved assignment document and rebuild warning, then follows the maintenance route. |
| UI-018 | P1 | UI delivery / cache coherence | Fixed | Replacement CSS and JavaScript changed while the entry and asset graph continued to request `alpha98-ui1`. The server marks a matching released asset `immutable` for one year, so an already-open installation could keep the pre-cleanup bundle and appear completely unfixed after updating. | Rotate the complete entry/module graph to `alpha98-ui5-7fa758fa6df7` and derive the suffix from normalized bytes of every immutable replacement CSS, JavaScript, and SVG sprite asset. Make a reused or mismatched release identifier fail the runtime contract suite. | A fresh host response keeps HTML `no-store`; every entry import and module literal names the same fingerprinted release; matching released assets return the immutable cache policy; the fingerprint test changes whenever an immutable asset changes; a browser loading the updated entry requests the new asset URLs and boots without a mixed-release error. |
| UI-019 | P1 | Person authoring / controls | Fixed | Shared person editors created `ui-input` and `ui-textarea` controls while the replacement component contract styles `.ui-field__control`, leaving native gray inputs and inconsistent focus treatment. | Route every Character, Persona, story-card, Quick Start, and import control through the shared field-control class without changing its value or ownership contract. | The real component contains no `ui-input` or `ui-textarea` controls of its own; every visible text, number, select, file, and textarea control has `ui-field__control`, and focus/invalid states match the shared component at desktop and phone widths. |
| UI-020 | P1 | Person authoring / structured editing | Fixed | The workspace's blanket 44 px target selector overrode the intended 22 rem Advanced and 7 rem structured editor minimums; Advanced rendered about 51 px tall. | Lower the blanket selector specificity and express prose/structured editor sizes with logical `min-block-size` so target safety and authored editing space compose. | At 1440×900, computed Advanced minimum and rendered height are at least 352 px and structured field editors are at least 112 px; compact layouts retain one document scroll owner and reachable actions. |
| UI-021 | P1 | Person authoring / draft safety | Fixed | Discard draft sat beside Save and immediately erased the owner-scoped local draft without naming the document or consequence. | Open a native modal that names the document, explains restoration of the last Library version, defaults focus to Keep editing, and invokes discard only after the destructive confirmation. | With a dirty Mara Venn draft, Discard opens `Discard changes to Mara Venn?`; Escape or Keep editing preserves the draft and makes zero discard calls; `Discard local changes` makes exactly one call. |
| UI-022 | P1 | Person authoring / field language | Fixed | Ordinary sections mechanically exposed internal schema labels such as `Offscreen agent`, `Top p`, and hedonic structures, with no bounds or consequence-oriented help. | Use one semantic path registry for maintained fields, friendly group/field labels, appropriate text/number/select/checkbox/JSON controls, literal bounds, and help. Keep raw unknowns only in Additional fields and Advanced. | Character and Persona renders expose Creativity, Curiosity, Background activity, Starting mood, and Pain sensitivity; raw internal labels are absent from ordinary sections; 0–1 values carry literal bounds/help; edited values and unknown nested extension data round-trip unchanged. |
| UI-023 | P2 | Person authoring / hierarchy | Fixed | Up to nine peer tabs gave Quick Start and technical escape hatches the same visual weight as content sections, duplicated the Quick Start heading, and made compact navigation look clipped and overfull. | Keep only peer content sections as tabs. Stage Start a Story, Additional fields, and Advanced under one More disclosure, keep the active auxiliary label visible in its summary, and remove duplicate headings. | Character exposes six peer tabs and one More entry; Persona exposes four peer tabs and one More entry; More reveals only the applicable auxiliary tasks; choosing one leaves `More · <section>` visible and the panel contains one heading. |
| UI-024 | P2 | Person authoring / composition | Fixed | Back, save state, editor frame, and form actions read as four detached horizontal bands, leaving excess whitespace and weak action ownership. | Pair Back/save state in one topbar and place Discard/Save in a footer owned by the bordered editor frame while retaining a single vertical panel scroll owner. | At 1440×900, 1024×768, 390×844, 360×800, and 844×390, the footer is a direct editor child and in view, the topbar stays legible, page overflow is zero, and exactly one named vertical document owner exists. |
| UI-025 | P2 | Person authoring / compact navigation | Fixed | The compact section strip exposed every peer and technical tab at once with a conspicuous native overflow treatment; the currently selected auxiliary task could scroll entirely out of sight. | Limit the persistent strip to peer content tabs plus More, use a restrained thin overflow treatment, and make the More summary itself carry auxiliary selected state. | Phone, narrow-phone, short-desktop, and short-landscape browser cases retain 44 px targets, horizontal-only section overflow, a visible active auxiliary summary, no page overflow, and no focusable control in a hidden panel or closed disclosure. |
| UI-026 | P2 | Person authoring / visual evidence | Fixed | Initial evidence concentrated on one dense Character section and five viewports, leaving Persona, story-card, destructive, validation, localization, accessibility, and zoom states underrepresented. | Expand deterministic evidence across shared document owners, high-risk states, long localized labels, Accessibility Mode, and 200% zoom equivalent without treating work-in-progress screenshots as design authority. | Repeatable capture and browser tests cover Character, Persona, story-card, dirty discard, invalid Advanced JSON, English/Japanese copy, Accessibility Mode, 200% zoom equivalent, and the six reference geometry cases; every image is reviewed against the approved replacement composition. |
| UI-027 | P1 | Library / story Character card | Fixed | The detail action emitted `mode=story-card`, but Library route normalization did not admit that maintained mode and immediately rewrote it to ordinary view. Runtime-only tests therefore passed while the real browser never entered the shared story-card workspace. | Admit story-card as a bounded Library authoring mode only for a selected Character with a valid Story context; keep its existing story-owned load/save authority and immutable identity rules. | In the real application, select a Character used by a Story and choose Edit Story card; the URL retains `mode=story-card` and `story=<id>`, the shared person workspace opens, identifies Story Character card, disables Name, and loads/saves through the Story-owned routes. |
| UI-028 | P2 | Settings / alignment | Fixed | The search glyph used a fixed top offset, and section-specific empty status rows made the title-to-content gap vary between pages. | Center the glyph from the input's block size, remove empty status rows from layout, and retain one shared section rhythm. | Browser geometry checks the glyph center and equal section starts; desktop captures compare Experience, Content, Add-ons, and Maintenance at one viewport. |
| UI-029 | P1 | Settings / narrator voice | Fixed | Four independently sized textareas wrapped into an unstable two-row block and obscured their shared purpose. | Preserve four drafts behind a single textarea and four ARIA tabs with complete keyboard movement. | Browser tests prove draft retention, save payload, ARIA state, arrow/Home/End movement, and responsive layout at 1440×900, 390×844, and 844×390. |
| UI-030 | P2 | Settings / Add-ons | Fixed | Lifecycle buttons inconsistently repeated a terminal `(demo)` title marker and had weak visual boundaries. | Preserve authored extension titles, remove only a terminal case-insensitive `(demo)` from action labels and status copy, and add a subtle 0.5 px authored border to the action set. | A routed demo fixture retains `Campaign (demo)` while exposing Enable Campaign and Remove Campaign; source and computed-style assertions cover the border. |
| UI-031 | P2 | Settings / iconography | Fixed | Maintenance reused an artifacted update glyph rather than a semantically specific reviewed symbol. | Add the supplied wrench path to the local sprite and map Maintenance to it without a network or font dependency. | Sprite, allowlist, filled-icon, navigation-href, and routed-render checks pass. |
| UI-032 | P1 | Settings / themes | Fixed | Unsupported Legacy themes remained selectable while the curated set lacked the approved cyberpunk and warm-grey options. | Remove the Legacy selector, migrate its stale local field away, and add Neon Circuit plus a blue-free warm-greyscale Modern Slate. | Browser and source tests prove six curated choices, no Legacy control, first-paint support, reload persistence, and warm-neutral Modern Slate token ordering. |
| UI-033 | P2 | Shared controls | Fixed | Native selects retained sharp platform geometry and inconsistent height; shared Search, New Story, and related buttons used oversized bold labels and could misalign inline symbols. | Give shared selects a compact glass treatment and common chevron; center button content with restrained type and a fixed icon gap while preserving compact-layout target minimums. | Settings and Library browser tests cover select geometry, focus, disabled and touch states, plus-icon alignment, and no horizontal overflow. |

## Explicitly investigated and not classified as defects

- Story text size is implemented for actual transcript prose; UI-004 adds
  discoverability rather than changing its existing scope.
- Native checkbox boxes are visually small, but the enclosing labeled Settings
  row is the hit target. The audit will measure the row rather than the painted
  checkbox square.
- Expected 404 responses from deliberately unmocked detail endpoints in capture
  fixtures are not production failures.
- Every sprite symbol's rendered fill-and-stroke bounds fit inside its declared
  view box. The earlier contact-sheet clipping was a measurement artifact from
  comparing the outer `<svg>` and external `<use>` layout boxes rather than the
  painted geometry; the supplied replacement artwork remains unchanged.
- Authentication, guest, and New Story composition otherwise matched their
  supplied references closely enough that this pass adds no redesign work to
  them beyond the icon and target-size rows above.

## Completed interaction-design follow-ups

These task-flow and capability requirements were reviewed before implementation
and are now part of the maintained Library contract:

| ID | Priority | Status | Observed problem | Approved direction | Browser verification after contract approval |
|---|---:|---|---|---|---|
| UI-FU-01 | P1 | Implemented | Character and Persona authoring was too dense for a contextual selection-detail pane, while a move could have broken route, selection, draft, and compact-layout behavior. | Use a focused destination-owned authoring workspace while keeping concise selection detail in the contextual pane outside authoring; preserve the approved Library hierarchy and inspector preference. | `test_person_workspace_restores_parent_route_scroll_focus_and_local_draft` proves filtered return, exact scroll, focus, draft, and section restoration. `test_person_workspace_geometry_has_one_scroll_owner_and_safe_targets` proves desktop, tablet, phone, and short-landscape staging with one scroll owner, no unused inspector track, 44 px controls, and reachable Save. |
| UI-FU-02 | P1 | Implemented | Capability parity with the maintained Character/Persona editor needed proof so a cleaner composition could not silently omit stored fields or established workflows. | Retain stored fields, advanced/raw access, generation, greetings, Quick Start and lived-location choices, import/export/duplicate, validation, recoverable drafts, and reusable versus story-specific editing in one shared framework. | `browser_tests/test_ui_character_persona_editor.py`, `browser_tests/test_ui_library_authoring.py`, and `tests/test_library_character_persona_authoring.py` exercise the maintained workflows; `CHARACTER_PERSONA_EDITOR_CAPABILITY_AUDIT.md` records the supported result and exact evidence for presentation gaps. |

Earlier interfaces remain capability references only; they are not visual or
information-architecture authority.

## Separately scoped backlog

| ID | Priority | Status | Observed problem | Approved direction | Browser verification after feature approval |
|---|---:|---|---|---|---|
| UI-BL-01 | P2 | Fixed | The shipped theme choices did not provide a safe user-authored theme workflow, and unrestricted CSS would compromise layout, accessibility, and upgrade contracts. | Implement the approved eight-role semantic-token editor with preview, reset, contrast validation, and safe import/export. Arbitrary CSS and layout overrides remain out of bounds. | Browser tests create, preview, persist, reload, reset, export, and import at desktop and compact viewports; malformed, extra-key, low-contrast, CSS, URL, and markup payloads fall back safely without damaging the current theme. |
| UI-BL-02 | P2 | Planned | Direct category entry is efficient for repeat users but gives no clean scan-first map of where Settings tasks live or their current high-level state. | Make `#/settings` a grouped row ledger for Connections, Appearance, Story & host, and Advanced. Each row uses a local icon, plain title, optional owned summary, and chevron into an existing authoritative route. Keep search and every detailed page; copy no external assets, code, branding, or pixel values. | Verify ordered groups and routes, summary ownership, direct deep links, search, browser Back, focus/scroll restoration, unavailable Turn details, 44 px compact targets, and zero horizontal overflow across desktop, phone, short landscape, Japanese, large-interface, and 200-percent zoom-equivalent states. |

The current Design Bible and approved replacement direction remain authoritative.
This ledger is the sole retained product-facing record; no separate intake
document is retained.

## Approved Design Bible deviations

### DEV-UI-2026-08-23-A: Library hierarchy calibration

- Category: calibration / information architecture correction
- Current reference rule: the supplied desktop Library screenshot contains a
  narrow ledger and a central material dashboard with repeated summary data.
- Approved rule: retain the reference's left-filter, central-work, right-detail
  geometry, but assign each fact and action once: navigation and filtering on
  the left, the material ledger in the center, and selection detail on the
  right.
- Rationale: the repeated Library/Scope and Your story material panels read as
  competing primary surfaces and create duplicate counts/actions.
- Responsive impact: compact layouts keep the established list-to-detail
  staging; no hidden duplicate controls are introduced.
- Accessibility/localization impact: fewer repeated landmarks and action names;
  stable accessible headings and one create/import cluster.
- Approval: approved as part of the 2026-08-23 cleanup scope.

### DEV-UI-2026-08-23-B: Story Tools presentation modes

- Category: component behavior revision
- Current reference rule: the inspector remembers a reasonable width; the
  implementation exposed three width-only states with the same content.
- Approved rule: three semantic modes are Expanded, Compact, and Rail, exposing
  icon + title + description, icon + title, and icon respectively. An open
  editor temporarily uses Expanded presentation.
- Rationale: every mode must produce a useful information-density tradeoff and
  the selected tool must remain immediately usable.
- Responsive impact: phone/tablet continue to use the full-screen sheet; mode
  labels never replace accessible names or tooltips.
- Persistence impact: legacy `wide` maps to Expanded, `narrow` to Compact, and
  `default` to Expanded.
- Approval: approved as part of the 2026-08-23 cleanup scope.

## Foundation cleanup record

Implementation and local verification completed on 2026-08-23.

- `.venv\Scripts\python.exe -m pytest browser_tests -q
  --basetemp=F:\git\Sonder_Engine\.tmp\ui_cleanup_browser_gate`:
  201 passed.
- `.venv\Scripts\python.exe -m pytest -q -n auto
  --basetemp=F:\git\Sonder_Engine\.tmp\ui_cleanup_full_gate`:
  8,800 passed and 4 platform-specific tests skipped.
- Deterministic Library and Story Tools capture reports covered 54 responsive
  cases with zero horizontal-overflow, continuous-overlap, undersized compact-
  target, or page-error findings. Settings Experience captures at 1440x900,
  1024x600, 390x844, and 844x390 confirmed owned scroll ranges, 44px compact
  controls, and the 352px / 232px / 80px semantic Story Tool presentations.
- Same-viewport Play, Library, Settings, and Story Tools renders were reviewed
  against the supplied reference composition. The only retained differences
  are the two approved deviations recorded above; audit screenshots and fixture
  output remain the product-direction comparison evidence.
- Corrective Experience captures now record both the top and final control at
  1440x900, 1024x600, and 390x844 after wheel input over the category rail.
  The complete UI entry/module graph uses release
  `alpha98-ui5-7fa758fa6df7`, whose suffix matches the normalized immutable
  CSS/JavaScript/SVG content fingerprint.
- `.venv\Scripts\python.exe tools\project_check.py` now accepts the regenerated
  English catalog and Japanese `All tools` entry. Its remaining failures are
  seven direct-import findings inside the installed
  `extensions/directive/tests/integration/test_atomic_provisioning.py`; that
  extension boundary is outside this UI cleanup and was not modified here.

The approval hold was lifted on 2026-08-23; integration to `interface` is
authorized.

## Person-authoring polish record

The shared Character, Persona, and story-specific Character-card polish was
verified on 2026-08-23 before integration.

- The focused UI contract and persistence gate passed 25 tests.
- The focused real-browser editor and Library gate passed 27 tests.
- The complete browser suite passed 219 tests.
- The complete repository suite passed 8,802 tests with 4 platform-specific
  skips.
- The repeatable WP-16 capture produced 13 reviewed states spanning the six
  reference geometries, both reusable document kinds, story-owned editing,
  discard confirmation, invalid structured input, Japanese, Accessibility
  Mode, and a 200-percent zoom equivalent.
- Catalog extraction found 922 English source messages with a matching
  Japanese key set.
- The complete immutable UI graph remains coherent at
  `alpha98-ui5-7fa758fa6df7`.
- `tools/project_check.py` continues to report only the seven previously
  recorded direct-import findings in the installed Directive extension test;
  this UI change does not modify that extension boundary.

## Settings and theme polish record

The Settings, curated/custom theme, and shared-control package was verified on
2026-08-23 before integration.

- The focused foundation, icon, runtime, Settings, custom-theme, and Library
  gate passed 101 tests.
- The complete browser suite passed 234 tests.
- The complete repository suite passed 8,805 tests with 4 platform-specific
  skips after two unrelated Windows directory-rename flakes passed on exact
  isolated reruns.
- The repeatable WP-17 capture produced 14 reviewed states spanning desktop,
  phone, and short-landscape Settings plus desktop and phone Library controls.
- The generated code map and complete project structure check passed.
- The complete immutable UI graph is coherent at
  `alpha98-ui6-57d168ae23cf`.
- The grouped Settings overview requested during final review is recorded as
  UI-BL-02 with its own design and executable follow-up plan; it is intentionally
  not mixed into the frozen UI6 asset graph.
