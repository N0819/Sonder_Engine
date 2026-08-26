# 10. Widget Design Workbook

**Status:** Complete first-pass Widget design; mockup translation pending

**Started:** 2026-08-26

**Applies to:** the Panels mockup and the later production Widget conversion

## Purpose

This is the living design record for Sonder's individual Widgets. The package's
earlier chapters define Panels, the Widget model, the Catalog, placement,
persistence, responsive behavior, and the complete candidate inventory. This
workbook answers the next question for every inventory entry:

> What real capability does this Widget preserve, and how should that
> capability look, behave, resize, recover, and communicate inside the new
> Atmospheric Digital Workbench?

The workbook is deliberately source-backed. Main establishes the real behavior
that must not be lost. Design Bible 2.0 and the canonical Atmospheric Workbench
establish visual and interaction grammar. Current source and maintained guides
remain authoritative for runtime ownership, saves, security, async identity,
and extension behavior.

Repository documents provide constraints and evidence. They do not replace the
product request or silently expand this tranche into production implementation.

## Documentation map

### Widget-system package

The complete primary package is:

1. [Panels](01_PANELS.md)
2. [Widget Model](02_WIDGET_MODEL.md)
3. [Widget Catalog](03_WIDGET_CATALOG.md)
4. [Layout and Placement](04_LAYOUT_AND_PLACEMENT.md)
5. [State, Persistence, and Migration](05_STATE_PERSISTENCE_AND_MIGRATION.md)
6. [Responsive, Accessibility, and Extensions](06_RESPONSIVE_ACCESSIBILITY_AND_EXTENSIONS.md)
7. [Widget Inventory](07_WIDGET_INVENTORY.md)
8. [Decision Register](08_DECISION_REGISTER.md)
9. [Adoption and Change Control](09_ADOPTION_AND_CHANGE_CONTROL.md)
10. this Widget Design Workbook.

### Presentation and interaction authority

- [Interface implementation contract](../../guides/INTERFACE.md)
- [UI reference and porting contract](../../guides/UI_REFERENCE.md)
- [Sonder UI Design Bible 2.0](../sonder-ui-bible/README.md)
- Design Bible foundation chapters 00-13
- [Scene Workspace](../sonder-ui-bible/docs/14_SCENE_WORKSPACE.md)
- [Responsive and Mobile](../sonder-ui-bible/docs/18_RESPONSIVE_AND_MOBILE.md)
- [Accessibility and Personalization](../sonder-ui-bible/docs/19_ACCESSIBILITY_AND_PERSONALIZATION.md)
- [Content and Terminology](../sonder-ui-bible/docs/20_CONTENT_AND_TERMINOLOGY.md)
- [Motion, Sound, and Feedback](../sonder-ui-bible/docs/21_MOTION_SOUND_AND_FEEDBACK.md)
- [UX Flows and Expert Acceleration](../sonder-ui-bible/docs/22_UX_FLOWS_AND_EXPERT_ACCELERATION.md)
- [Anti-Patterns](../sonder-ui-bible/docs/23_ANTI_PATTERNS.md)
- [Tokens and Measurements](../sonder-ui-bible/docs/24_TOKENS_AND_MEASUREMENTS.md)
- [Decision Register](../sonder-ui-bible/docs/26_DECISION_REGISTER.md)
- [Change Control](../sonder-ui-bible/docs/29_CHANGE_CONTROL.md)
- [Canonical Atmospheric Workbench](../../experiments/sonder-atmospheric-workbench/README.md)

The two existing mockup implementation plans remain useful execution history,
but they do not decide an individual Widget's final visual design. In
particular, the later direct-drag correction controls Catalog result behavior;
it does not turn a miniature into a marketplace card or add per-result action
buttons.

### Active Panels mockup target

The Widget designs in this workbook target the current **Sonder Play workspace
UI mockup**, not an inferred future composition:

- live preview:
  `http://127.0.0.1:8765/sonder-workbench-calibration-preview.html`;
- editable source:
  `C:\Users\Keptin\.codex\visualizations\2026\08\25\01a036e9-bd28-7ed3-86aa-c5a8fc74599d\sonder-workbench-calibration.html`;
- rendered preview:
  `C:\Users\Keptin\.codex\visualizations\2026\08\25\01a036e9-bd28-7ed3-86aa-c5a8fc74599d\sonder-workbench-calibration-preview.html`;
- regression harness:
  `C:\Users\Keptin\.codex\visualizations\2026\08\25\01a036e9-bd28-7ed3-86aa-c5a8fc74599d\sonder-drag-regression.html`.

Artifact identity recorded on 2026-08-26:

| File | Bytes | SHA-256 |
|---|---:|---|
| editable source | 415,867 | `FAD6E865392391ABFE60797FD5B5A7CD8D05251FC496BA2A5D1A62CB693A52BA` |
| rendered preview | 483,824 | `6BD572E6149E40F7424FABE4509A00A78EBF0A667540E025350BA40F577F996D` |
| regression harness | 50,445 | `E855DEA8C8E86BAFDECFAABC3111A913F794134C022CFB902CCE017C25017870` |

The live inspection found:

- Scene, Library, and Settings rendered as editable Panel tabs;
- exactly nineteen registry-driven Widget miniatures;
- a single centered Catalog with whole-preview pointer and keyboard placement;
- stage-native Transcript and integrated Composer already represented in both
  the Scene Panel and the Catalog;
- no per-result marketplace action row;
- `53/53 passed` in the regression harness.

This is the working mockup target for new Widget visual designs. It remains a
work-in-progress artifact until the Panels revision is adopted and a new
hash-identified repository reference is frozen through change control.

### Main capability evidence

The first audit uses `Main@0c3f779935e329753c449a1910dd738cca4fb721`,
verified against the GitHub repository on 2026-08-26. Main's classic layout is
not presentation authority. These files are capability and ownership evidence:

- `static/index.html` — visible transcript, progress, technical-detail,
  composer, ambience, condition, and background-work surfaces;
- `static/js/chat.js` — story/frame load identity, transcript rendering,
  turn actions, narration variants, progress, streaming, early narration,
  reroll, abort, pipeline inspection, and atmosphere coordination;
- `static/js/app.js` — composer sizing, keyboard submission, send, Stop, and
  failed-submit restoration;
- `static/styles.css` — current geometry evidence only, not target styling;
- current routes and server handlers — mutation and persistence authority.

## Design method

Three starting approaches were considered:

| Approach | Strength | Failure mode | Outcome |
|---|---|---|---|
| Restyle Main one surface at a time | Fast visual familiarity | Preserves the old page structure and tangles unrelated capabilities | Rejected |
| Draw attractive miniatures before tracing behavior | Fast mockup coverage | Produces decorative shells that omit real states and actions | Rejected |
| Audit capability, identify its owner, then translate it through the Bible | Preserves product truth and produces testable visual contracts | Requires deliberate work per Widget | Selected |

Each Widget therefore moves through the same sequence:

1. trace the complete user-visible capability on Main;
2. name the one real runtime, save, and draft owner;
3. separate content from infrastructure and momentary commands;
4. choose its Widget surface role and supported placements;
5. design anatomy, hierarchy, states, and interaction;
6. specify desktop, constrained, compact, short-height, touch, keyboard,
   reduced-motion, solid-surface, and high-contrast behavior;
7. define an inert Catalog miniature using the same visual identity;
8. record mockup acceptance evidence before marking the design reviewed.

## Where the work starts

The first tranche is **Story reading and writing**:

1. Transcript;
2. Composer;
3. Story and Frame Context;
4. Turn Progress;
5. Live Technical Detail;
6. Turn Versions;
7. Turn Inspector.

Transcript and Composer come first because they establish the hardest shared
rules: prose is not a panel, reading measure is stable, the composer is a
raised instrument, story/frame identity cannot drift, drafts and generation
outlive mounts, and compact staging must never cover the active input.

Starting with a visually simpler ledger would defer those decisions and make
every later mockup easier to draw but less trustworthy.

## Shared Widget presentation roles

Every capability is a Widget, but not every Widget wears the same amount of
material. The role controls presentation only; it does not create another data
or persistence model.

| Role | Use | Ordinary chrome |
|---|---|---|
| Stage-native | Literary or atmospheric content that must remain part of the canvas | Unboxed content; identity and action chrome appear on focus, selection, or Panel edit |
| Instrument | A compact operable object such as Composer or Ambient Light | One integrated material object with stable control clusters |
| Module | Roster, ledger, status, or bounded tool | Standard 30 px title/tab bar and material body |
| Workspace/editor | Substantial search, authoring, or structural editing | Dominant allocation with one explicit header, one scroll owner, and owner-qualified draft state |

This classification resolves a real tension between the Widget model's need
for discoverable identity and the Bible's rule that prose is not a panel.
Stage-native Widgets retain a semantic name, Catalog identity, focus treatment,
action menu, and edit-mode drag surface without putting the transcript in a
permanent glass card. If adopted, this exception must be reflected in the
Widget Model and Component Contracts chapters rather than implemented as an
undocumented one-off.

## Working decisions

| ID | Decision | Outcome |
|---|---|---|
| WDW-001 | Capability floor | Main behavior is audited before drawing each Widget; old layout is not copied. |
| WDW-002 | Runtime authority | A Widget projects one existing owner. Layout state never becomes story, draft, or server truth. |
| WDW-003 | Visual families | Stage-native, Instrument, Module, and Workspace/editor are presentation roles within one Widget model. |
| WDW-004 | Catalog previews | Previews are inert representative miniatures rendered from the same anatomy as placed Widgets. |
| WDW-005 | Mockup honesty | Unsupported operations appear as representative states, not fake working data or decorative controls. |
| WDW-006 | First tranche | Transcript and Composer define the story-stage contract before supporting Widgets are designed. |
| WDW-007 | Shared run projection | Story Context, Turn Progress, and Live Technical Detail consume one owner-qualified story/run service rather than creating three subscriptions or fetch paths. |
| WDW-008 | Audience boundary | Turn Progress uses calm player-facing language; Live Technical Detail alone exposes engine-stage identity and raw output. |
| WDW-009 | Honest progress | Generation has no invented percentage or fixed step count. Progress reports elapsed time, the current friendly phase, and real concurrency only. |
| WDW-010 | Complete coverage | The workbook is complete only when every fixed inventory entry, every eligible Settings subwidget, and every supported extension shape has an individual design or an explicit evidence-backed non-Widget disposition. |
| WDW-011 | Family contracts | A family contract may carry repeated layout, accessibility, state, and persistence rules, but every Widget still needs its own identity, owner, purpose, actions, geometry, Catalog miniature, and acceptance delta. |
| WDW-012 | Preview before mutation | Version arrows browse locally. Activating a narration or step variant requires a separately labelled Use action and fresh server eligibility. |
| WDW-013 | Explicit placement wins | The legacy passive cast-condition visibility setting seeds a starter layout only; it never hides an explicitly placed Cast Condition Widget. |
| WDW-014 | Visible-turn atmosphere | Backdrop and ambience follow the turn being read, while physiological Widgets remain on current frame state. |
| WDW-015 | Library projection | Filtered Library Widgets share one bounded server projection; full destructive lifecycle and long authoring stay with the canonical Library workspace. |
| WDW-016 | Safe Lore authoring | Independently mounted Lore editors require conditional revision or a serialized edit lease before writes are enabled. |
| WDW-017 | Specialized world writes | World State does not expose the existing all-frame raw replacement as an ordinary frame editor; specialized owners and Raw Story Data retain their boundaries. |
| WDW-018 | No fictional edit authority | Character Relationships remains read-only until an evidence-preserving typed route exists. UI inventory wording cannot create mutation authority. |
| WDW-019 | Subjective ledgers | Dramatic Irony and Promise Ledger label memory projections as character-held beliefs/promises; they never claim objective truth or Charter lifecycle state. |
| WDW-020 | Settings groups navigate | The six group Widgets summarize and locate canonical panels; they never fetch, mutate, or duplicate forms. |
| WDW-021 | One settings owner | A panel and each placed subwidget bind one scope-qualified draft, save service, task/poll owner, and fresh authoritative projection. |
| WDW-022 | Dangerous commands stay contained | Host session is not a Widget because its only behavior is sign out; raw/destructive tools stay in their full owner treatment until stated safety prerequisites exist. |
| WDW-023 | Extension manifest boundary | Only owner-bound definitions with explicit context, geometry, multiplicity, state, lifecycle, and trust metadata enter the Catalog; infrastructure and embedded renderers do not. |

## Design progress

| Tranche | Widgets | State |
|---|---|---|
| Story reading and writing | Transcript; Composer | First design drafted below |
| Story context and runs | Story and Frame Context; Turn Progress; Live Technical Detail | First design drafted below |
| Turn review | Turn Versions; Turn Inspector | First design drafted below |
| Atmosphere and condition | Player Condition; Cast Condition; Room Ambience; Scene Backdrop; Background Work | First design drafted below |
| Library and authoring | All entries in the Library and Authoring inventory | First design drafted below |
| Story systems | All entries in the Story-System inventory | First design drafted below |
| Settings | Six groups; eleven panels; all 23 eligible subwidgets | First design/disposition drafted below |
| Extensions | Compact, full-workspace, Settings, and embedded Inspector shapes | First host/presentation contracts drafted below |

The source of truth for total coverage remains the
[complete Widget Inventory](07_WIDGET_INVENTORY.md), so this workbook does not
create a second drifting inventory.

## Coverage accounting

The current inventory contains **69 fixed Widget definitions**:

| Fixed family | Count | Workbook state |
|---|---:|---|
| Story | 12 | 12 drafted; complete |
| Library and authoring | 19 | 19 drafted; complete |
| Story systems | 21 | 21 drafted; complete |
| Settings groups | 6 | 6 drafted; complete |
| Settings panels | 11 | 11 drafted; complete |
| **Fixed total** | **69** | **69 drafted; complete** |

It also contains **23 eligible Settings subwidgets**. Twenty-two have registered
Widget designs and Host session has an explicit evidence-backed non-Widget
disposition. Dynamic extension coverage defines compact, substantial workspace,
Settings contribution, and an embedded Turn Inspector renderer that is
deliberately not a top-level Catalog entry.

Completion therefore means:

1. all 69 fixed definitions have a design record;
2. all 23 eligible Settings subwidgets have a design or explicit non-Widget
   disposition;
3. all supported extension shapes have host and presentation contracts;
4. every record names one owner and safe persistence boundary;
5. the coverage audit matches this workbook back to the inventory without
   relying on implied or grouped names.

All five conditions are represented in this draft. The final verification
section records the mechanical name/count audit and any remaining design-to-
mockup prerequisites.

The counts are an audit aid, not another registry. Any inventory change updates
this accounting in the same design pass.

---

# Widget design: Transcript

**Design state:** First draft, ready for mockup translation

**Type:** `story.transcript`

**Category:** Story

**Context:** Active story and active frame

**Presentation role:** Stage-native

**Multiplicity:** Single per Panel; the definition may appear on multiple
Panels because only the active Panel mounts its projection

## User purpose

Read the active frame as continuous fiction, understand which player action
led to each beat, compare the newest beat's narration variants, and reach the
real turn operations without turning the reading surface into a control grid.

## Main capability floor

Main proves that Transcript currently:

- rejects stale story loads and renders the selected story and frame;
- shows player input followed by narration for each turn;
- colors delivered dialogue from the committed speech index without inserting
  unsafe model HTML;
- distinguishes stale or superseded prose and names the earliest stale stage;
- opens pipeline detail, edits player input, edits narration, branches from a
  turn, rerolls the latest turn, and deletes the latest turn;
- browses the newest turn's saved narration variants in place;
- shows finished narration before the entire pipeline tail commits, then
  replaces that preview with the authoritative refreshed turn;
- keeps one visible-turn identity so backdrop and ambience follow the beat the
  reader is actually reading;
- owns transcript scrolling and long-story rendering behavior.

These behaviors are the floor. The permanent icon row and classic page frame
are not.

## Ownership

- The active-story runtime owns selected story/frame identity, loading,
  generation, mutations, and stale-result rejection.
- The server owns turns, variants, stale state, branches, and all mutation
  effects.
- Transcript owns only its local reading presentation: selected visible turn,
  safe scroll restoration, and whether its contextual action menu is open.
- The shared atmosphere runtime consumes the Transcript's published visible
  turn. Transcript does not own audio or backdrop lifetime.
- Selecting a turn publishes one typed `turn` selection for Turn Versions and
  Turn Inspector. It does not copy pipeline data into Panel persistence.

## Anatomy

1. **Literary heading** — current story title in Newsreader 12/16. An optional
   frame label appears only when frames exist and is plain context, not a
   switcher.
2. **Turn stream** — one readable document flow at a 650-680 px maximum measure.
3. **Player action** — restrained Sans or Mono lead-in above the resulting
   prose, visually distinct without becoming a chat bubble.
4. **Narration** — Newsreader 15/1.62 by default, unboxed over the reading veil.
5. **Turn state line** — appears only for stale, superseded, streaming-preview,
   or recovery state.
6. **Inline version control** — previous, `n of total`, next for the newest turn
   only when more than one narration exists.
7. **Turn actions** — one labeled `Turn actions` menu on the focused or selected
   turn; touch selection reveals it without hover.
8. **New turn affordance** — appears when new prose arrives while the reader is
   reviewing history; activation returns to the newest beat.

The normal reading state has no permanent `Transcript` title bar or glass body.
The region retains the accessible name `Transcript`. Panel edit mode introduces
a 30 px `Transcript` bar and exact placement outline, then removes them on edit
completion. This is the stage-native chrome contract, not hidden duplicate UI.

## Visual and material treatment

- The atmospheric canvas remains continuous behind the Widget.
- A local reading veil or text shadow protects contrast; no card boundary
  encloses prose.
- Selection uses a faint ambient leading edge or marker beside the selected
  turn, never a filled message card.
- Player action uses Interface text at muted strength; narration remains the
  human center.
- Stale state uses Source amber plus explicit text. Failure uses Error red plus
  a recovery action. Neither state relies on tint alone.
- Turn controls use the same 4 px material and compact typography as the
  workbench, but they remain subordinate to prose.

## Placement and geometry

| Contract | Value |
|---|---|
| Minimum useful size | 320 x 280 px |
| Preferred reading measure | 650-680 px |
| Preferred allocation | Dominant story stage |
| Supported zones | story stage; focused dominant; medium/wide grid |
| Unsupported zones | left/right narrow toolbar; composer strip |
| Resize | container may grow; prose measure stops at the reading token |
| Stack | Allowed only in focused/grid allocations, never in the shipped story-stage reading slot |
| Float | Not supported; a floating Transcript would turn the literary center into a window |
| Collapse | Not supported inside the story-stage template |

Opening, closing, or resizing surrounding Widgets never changes the prose
measure or rewraps existing turns. Extra width becomes atmosphere, not longer
lines.

## Interaction design

- Scrolling away from the newest turn suspends automatic scroll following.
- A newly committed turn never steals the reader's position; it exposes `New
  turn` instead.
- Version arrows are scoped to the focused Transcript/turn context. They do not
  claim global arrow keys while another control has focus.
- `Inspect turn` publishes selection and focuses the placed Turn Inspector. If
  none is placed, the shared Catalog opens already filtered to Turn Inspector;
  no hidden inspector is mounted.
- `Edit input` and `Edit narration` use owner-bound transient editors. Editing
  narration states plainly that recorded events and world state do not change.
- `Branch from here` remains available for any eligible turn and reports its
  background task without blocking reading.
- `Reroll` and `Delete` appear only where the server permits them. Reroll names
  checkpoint rollback consequences before confirmation. Delete names the exact
  latest turn.
- The most visible turn publishes atmosphere identity after a stable dwell;
  narration just generated for the reader may publish immediately.

## States

| State | Presentation | Behavior and recovery |
|---|---|---|
| Awaiting story | Quiet stage with `Open Library` and `Create Story` | Widget retains its slot; no sample story is fabricated |
| Loading | Existing safe projection dims slightly with `Loading story` | Late prior-story results are rejected |
| Confirmed empty | Story title plus `The scene has not begun` | Composer remains the primary next action |
| Ready at newest | Full literary flow; no extra status chrome | Scroll follows only while the reader remains at the end |
| Reviewing history | Visible selected-turn marker | New content raises `New turn` without moving scroll |
| Narration preview | Newest beat marked `Finishing this turn` | Authoritative refresh replaces the preview in place |
| Stale/superseded | Plain explanation beside affected beat | Inspect or rerun actions appear only when authorized |
| Refresh failed | Inline problem at the preserved prior projection | Retry refresh; reading position and prior content remain |
| Story changed | Immediate context invalidation, then loading state | Frame-invalid selection and turn selection clear together |

## Responsive and accessibility behavior

- Wide and constrained layouts preserve the fixed reading measure.
- Compact layouts use the full available width with 12-16 px side breathing
  room; default prose may reduce to the Bible's calibrated 13 px only when no
  user text override is active.
- The Transcript is the one vertical story scroll owner. The document and
  Panel shell do not compete with it.
- Each turn is ordinary document content with a navigable landmark or heading
  strategy appropriate to the final markup.
- Turn actions have explicit labels, visible focus, and 44 px touch hit regions.
- Dialogue color is supplementary; speaker text remains understandable without
  color.
- Reduced motion removes preview/reflow interpolation. Solid surfaces alter
  only the reading veil and control material, not literary layout.
- Screen readers receive one concise announcement for a new turn, stale state,
  version change, or failed refresh; prose itself is not duplicated into a
  live region.

## Persisted presentation state

Safe Panel-level per-instance state may include density only. Selected turn and
bounded scroll restoration are story/frame-qualified runtime presentation
state and must stay with that owner rather than enter the global Panel
envelope. Panel persistence must not include prose, turn payloads, variant
content, turn id, story id, frame id, pipeline data, or atmosphere URLs.

Story/frame identity comes from current application context. A restored
selected turn is accepted only if it still belongs to that context; otherwise
the Widget returns to the newest valid turn.

## Catalog miniature

The miniature shows a small story title, one muted player action, two short
Newsreader narration passages, and a restrained `1 / 3` version indicator. It
uses neutral representative text, no current story data, no active controls,
and no technical pipeline imagery. The entire miniature is the direct-drag or
keyboard placement surface.

## Current mockup fit

The active mockup already establishes the right foundation: an unboxed article
over the atmospheric stage and the same article anatomy inside the Catalog
miniature. The first functional pass must add the missing turn boundaries,
player-action treatment, selection, version state, actions, new-turn recovery,
and non-ready states without turning that article into a standard module card.

## Mockup acceptance

- Prose is visibly unboxed and remains the strongest reading layer.
- The miniature and placed Widget are recognizably the same design.
- Toolbars can open/close without changing a captured prose line break.
- A selected turn reveals every preserved operation through one compact menu.
- Version comparison works without opening technical detail.
- New-turn arrival preserves a historical reading position.
- Awaiting, loading, empty, preview, stale, and refresh-failed states are all
  demonstrable without fabricated live data.
- Desktop, compact phone, short landscape, solid, reduced-motion, keyboard,
  and touch states retain the capability.

---

# Widget design: Composer

**Design state:** First draft, ready for mockup translation

**Type:** `story.composer`

**Category:** Story

**Context:** Active story and active frame

**Presentation role:** Instrument

**Multiplicity:** Single per Panel; multiple Panels may project the same one
story/frame-qualified draft owner, but only the active Panel mounts a Composer

## User purpose

Write or continue the active story, understand whether the input will Continue
or Send, stop the exact generation that was started, and keep authored text
safe across recoverable failure, Panel switching, responsive staging, and
Widget remount.

## Main capability floor

Main proves that Composer currently:

- accepts an empty submission to establish or continue the scene;
- accepts written action/dialogue and submits it to the active story/frame;
- grows with input up to a viewport-aware ceiling;
- supports `Ctrl/Cmd+Enter` while preserving ordinary multiline entry;
- disables duplicate submission while a run is active;
- changes from Send to Stop during generation;
- binds Stop to the story/frame where the run actually began, even if the user
  browses elsewhere;
- restores cleared input after an immediate failed start;
- arms optional completion audio at the initiating gesture;
- refreshes the authoritative story after the run and reports failure plainly.

The classic full-bleed footer, adjacent ambience buttons, and permanent page
position are not part of that capability contract.

## Ownership

- The application runtime owns active story/frame identity, the one active
  generation, submission, abort, completion, and refresh.
- The draft service owns text under the stable active story/frame owner. A
  Widget instance never stores an anonymous draft in the Panel envelope.
- Composer owns only local field focus, selection, measured height, and compact
  presentation disclosures.
- Turn Progress owns detailed friendly progress; Live Technical Detail owns
  raw stage output; Room Ambience owns audio controls. Composer does not absorb
  those Widgets merely because Main placed related controls nearby.

## Anatomy

1. **Context line** — concise active frame or input mode only when it changes
   what submission means. It never repeats the story picker.
2. **Literary input** — a borderless or near-borderless textarea inside the
   shared raised plate.
3. **Shortcut/status line** — muted `Ctrl/Cmd+Enter` guidance, draft recovery,
   or a concise generation state; absent when it adds no information.
4. **Stable action cell** — `Continue`, `Send`, `Stop`, or recoverable `Retry`
   within one fixed-width shared-edge cell.
5. **Widget actions** — placement and configuration menu available from the
   plate's focus/edit treatment, not mixed with story submission.

The input and action cell form one integrated object with 4 px outer corners
and square shared edges. The Composer is raised digital material; it is not a
chat bubble, command line, or oversized card.

## Button semantics

| Condition | Primary label | Result |
|---|---|---|
| Empty trimmed draft, ready | Continue | Establish or continue the scene with empty input |
| Non-empty draft, ready | Send | Submit the exact draft to the active story/frame |
| Current context owns the cancellable run | Stop | Abort that captured run; never retarget to current UI state |
| Start was not accepted and draft is intact | Retry | Repeat the same owner-qualified submission after explicit activation |
| No active story | No submission label | Show `Open Library` and `Create Story` instead of pretending the field can send |

The action cell retains a stable width across labels so the input measure does
not breathe. Stop uses an explicit label and state marker rather than a red
square alone.

## Visual and material treatment

- The plate uses Glass panel at the configured Glass Density and Frost Level.
- The action cell uses Control chrome at Bar Opacity.
- Focus follows the 4 px outer object and also makes field focus explicit.
- Ready, saving, blocked, and failed states use text plus restrained semantic
  color; no state changes border thickness or component size.
- Literary input uses the story/interface role appropriate to authored fiction;
  placeholder and shortcut text remain compact Sans.
- A growing draft adds vertical writing space without increasing width or
  pushing the active action below the viewport.

## Placement and geometry

| Contract | Value |
|---|---|
| Minimum useful size | 320 x 56 px |
| Preferred width | Same 650-680 px reading measure as Transcript |
| Expanded input ceiling | The lesser of 240 px and roughly 35% of usable Panel height |
| Supported zones | story composer strip; focused support strip; wide grid row spanning enough columns |
| Unsupported zones | narrow left/right toolbar; ordinary tab stack; floating layer |
| Resize | Vertical growth within the ceiling; width remains layout-owned |
| Stack | Not supported |
| Float | Not supported |
| Collapse | Not while it is the story-stage Composer |

The shipped story-stage template anchors Composer near the lower edge without
making it viewport-global. A different Panel may place it in another compatible
wide allocation, but the software keyboard and active field must always remain
reachable.

## Draft and submission behavior

- Draft identity is `active story + active frame`, never Panel id or Widget
  instance id.
- Switching Panels or unmounting Composer does not discard or retarget a draft.
- Switching stories invalidates the visible draft projection and loads the new
  owner; the prior draft remains recoverable under its prior owner.
- Activation captures story id, frame id, draft revision, and request identity
  before submitting.
- A pre-acceptance failure leaves text and selection recoverable and exposes
  Retry. An accepted submission clears only the matching draft revision, so
  typing begun after activation cannot be erased by a late response.
- The active run outlives Composer's DOM. Panel switching does not cancel it.
- If the user changes story while a run continues, the new story's Composer
  never inherits Stop or completion state. Persistent global status retains the
  named run and its Stop action until the original owner settles.
- Completion refreshes authoritative Transcript/story state before announcing
  ready. Optional chime remains an atmosphere/runtime preference, not Composer
  persistence.

## States

| State | Presentation | Behavior and recovery |
|---|---|---|
| Awaiting story | Compact explanation with `Open Library` and `Create Story` | Slot and geometry remain intact |
| Ready, empty | Placeholder plus `Continue` | Empty submission remains intentional and accessible |
| Ready, drafted | Authored text plus `Send` | Owner-qualified draft saves through its existing service |
| Starting | Input remains visible; action is temporarily busy | Duplicate activation is refused |
| Running here | Drafted submission is represented without becoming editable; action is `Stop` | Stop addresses the captured story/frame run |
| Running elsewhere | Current Composer is ready only when runtime permits; global status names the other run | It never shows the other story's draft or retargets Stop |
| Pre-accept failure | Draft retained with inline explanation and `Retry` | Focus returns to the field or Retry according to the initiating path |
| Refresh failure after accepted run | Input state follows accepted ownership; inline story-refresh problem remains | Retry refresh, not duplicate generation |
| Offline/blocked | Draft remains editable where safe; submission explains why unavailable | No automatic write retry |

## Responsive and accessibility behavior

- Wide layouts align exactly with Transcript's reading token.
- Constrained layouts preserve width independently of surrounding toolbar
  state.
- Phone layouts use available width and safe-area padding. The software
  keyboard may reduce visible Transcript space but never cover the field or
  action cell.
- Short landscape prioritizes the active field and action; secondary context
  and shortcut copy disappear before the input shrinks below usefulness.
- The textarea has an explicit accessible name; placeholder is not its only
  label.
- `Ctrl/Cmd+Enter` submits; Shift+Enter and unmodified Enter remain text entry.
- Touch exposes a 44 px action target while keeping the visible workbench
  geometry compact.
- Status changes announce once. Streaming tokens and elapsed ticks do not
  repeatedly announce through Composer.
- Reduced motion removes height/reflow interpolation. Solid and high-contrast
  modes preserve the integrated cluster and focus order.

## Persisted presentation state

Panel persistence may retain safe instance configuration such as preferred
input density or expanded/collapsed helper copy. It never stores draft text,
story/frame identity, request state, submitted input, credentials, or run
events.

Draft persistence remains with the qualified draft owner. Generation state
remains with the runtime owner. This separation permits multiple Panels to
contain Composer without creating multiple draft truths.

## Catalog miniature

The miniature shows the integrated raised plate, two short representative
input lines, and a stable `Send` cell. It does not blink a caret, submit, show
real drafts, expose a fake Stop state, or include ambience controls. The whole
miniature is the Catalog placement surface.

## Current mockup fit

The active mockup already uses the correct integrated plate, fixed action cell,
and faithful Catalog miniature. Its current helper says `Enter to send` and
`Shift + Enter for line break`. Main and Design Bible 2.0 instead use
`Ctrl/Cmd+Enter` as the deliberate submission shortcut while ordinary text
entry remains editing. The functional Widget build must correct the helper copy
and keyboard behavior rather than treating the placeholder as authority.

## Mockup acceptance

- Empty and written states clearly distinguish Continue from Send.
- Send, Stop, and Retry preserve one stable action-cell width.
- Composer and Transcript share the same captured reading measure while side
  regions open and close.
- Autosizing reaches its ceiling without covering the latest prose or leaving
  the action unreachable.
- A simulated pre-acceptance failure visibly preserves the draft.
- Panel switching preserves the draft and a simulated active run without a
  second live Composer owner.
- No-story, ready, running, running-elsewhere, failure, offline, phone-keyboard,
  short-landscape, keyboard, touch, reduced-motion, and solid states are
  demonstrable.
- The Catalog miniature is immediately recognizable as the placed Composer and
  contains no marketplace action button.

---

# Shared boundary: story context and live runs

Story and Frame Context, Turn Progress, and Live Technical Detail are designed
together because they observe the same moving boundary. They are not three
independent owners of story state or three ways to run generation.

The application runtime publishes one owner-qualified projection:

```text
story owner = story id + selected frame id
run owner   = story owner + run id

story context ──> Story and Frame Context
friendly run ───> Turn Progress
attributed events ──> Live Technical Detail
```

The projection has these rules:

- `Present` is the null frame identity, not a synthetic frame created by a
  Widget.
- A frame change is a routed story-context change. Transcript, Composer, Story
  and Frame Context, and every story-qualified tool move to the same owner.
- A run captures its story and frame before generation begins. No later Panel,
  route, or frame selection may retarget Stop, Retry, events, or completion.
- Switching story/frame invalidates all three visible projections together.
  Late loads or run events for the prior owner are rejected from the newly
  selected story.
- The run continues if its initiating Widget or Panel unmounts. Persistent
  global status owns cross-Panel visibility and cancellation in that case.
- A Widget may subscribe to a derived view, but it may not open a second stream,
  refetch the story on every event, or retain a private competing run ledger.
- Panel persistence stores presentation preferences only. Story identity,
  selected frame, elapsed time, run ids, raw output, and failure records remain
  with their established runtime owners.

The stable top shelf may continue to name the active story and report the
global `Ready`/`Generating` condition. It is wayfinding, not a fourth detailed
Widget. These Widgets add context or depth without turning the shelf into a
dashboard.

Main proves the capability floor. Current replacement source already provides
the stronger async seam: `play-runtime.js` qualifies selection and generation
by story/frame owner, rejects stale loads, keeps the active run outside the
view, and refreshes authoritative story state after completion. The Widget
conversion must preserve that seam rather than reintroducing Main's global DOM
ownership.

---

# Widget design: Story and Frame Context

**Design state:** First draft, ready for mockup translation

**Catalog name:** Story and Frame Context

**Placed title:** Story Context

**Type:** `story.context`

**Category:** Story

**Context:** Active story and active frame

**Presentation role:** Module

**Multiplicity:** Single per Panel; the definition may appear on multiple
Panels because all instances project the same application-owned context

## User purpose

Confirm which story and temporal frame the current Panel is using, and switch
among existing frames without opening a second story picker or turning a small
orientation Widget into the Frames authoring workspace.

## Main capability floor

Main proves that story/frame context currently:

- identifies the loaded story before transcript and turn operations render;
- treats `Present` as the null/default frame;
- lists frames by their human label and preserves kind/ordinal metadata;
- switches Transcript and subsequent submission to the selected frame;
- keeps frame selection in browser-tab presentation state because the server
  has no single global current frame;
- clears an invalid remembered frame when a story no longer contains it;
- hides the frame bar when there is only one available frame.

Current replacement source moves the selected frame into the Play route,
qualifies the stable owner as `chat + frame`, and gives full frame creation,
travelers, non-existent cast, and participant stationing to the separate
Frames story tool. Those ownership improvements are authoritative.

The old full-width page heading, duplicated story menu, and compact breakpoint
that simply hides frame navigation are not part of the capability contract.

## Ownership and non-overlap

- Play/application runtime owns the selected story, selected frame, story
  payload, routing, load cancellation, and authoritative refresh.
- Story Context projects that identity and invokes the existing owner-qualified
  frame-open operation. It does not mutate the story or frame records directly.
- Library owns choosing a different story. This Widget names the current story
  but never grows a second recent-story picker.
- The Frames Widget owns creation, relationship-to-present metadata, travelers,
  non-existent cast, and stationing. Story Context only switches among frames
  that already exist.
- Transcript and Composer consume the context; neither one becomes its owner.
- The top shelf may repeat only the minimum global story identity needed for
  persistent wayfinding. This Widget is the detailed local projection.

## Anatomy

1. **Module bar** — `Story Context`, a quiet context glyph, and ordinary Widget
   actions. It adds no `Current story` eyebrow.
2. **Story identity** — the story title as the primary line and an optional
   short story code or saved-state note as the secondary line. The title is not
   styled like a button.
3. **Frame summary** — `Present` or the selected frame label, followed by a
   compact kind/ordinal descriptor when it adds meaning.
4. **Frame switcher** — existing frames in story order. Two or three may use a
   segmented row; longer sets use one compact listbox trigger and menu so labels
   do not wrap into an accidental card grid.
5. **Owner action** — `Open Frames` reaches the full Frames Widget/workspace.
   It is secondary and appears only when that capability is available.

Turn count may appear as muted context beside the story identity when the
authoritative story payload already provides it. It is never fetched
separately, and it disappears before story/frame identity at constrained
sizes.

## Visual and material treatment

- Use the standard 30 px Module bar and Glass body.
- The story title uses compact Sans hierarchy. Frame labels are data and use
  Sans; ordinal/code fragments may use Mono.
- The selected frame uses the workbench's restrained active indicator, not a
  filled navigation pill or timeline card.
- Frame kind is supporting metadata, not a color-coded taxonomy.
- No illustration, oversized story cover, breadcrumb trail, or dashboard KPI
  is introduced.

## Placement and geometry

| Contract | Value |
|---|---|
| Minimum useful size | 200 x 112 px |
| Preferred size | 286 x 164 px |
| Supported zones | left/right toolbar; compact or medium grid; focused support region |
| Unsupported zones | composer strip; reading-stage center |
| Resize | Width and height within declared Module bounds |
| Stack | Supported with other story-context Modules |
| Float | Supported as a bounded reference Module, never as a modal substitute |
| Collapse | Supported; collapsed summary retains selected frame, not the full story title twice |

The default Scene Panel does not place this Widget merely to repeat its top
shelf and stage context. It enters the Catalog for custom Panels and may be
included by a later template only where it replaces, rather than duplicates,
another detailed context surface.

## Behavior

- Selecting a frame invokes the same route/open operation used by the host.
- During navigation, the selected option remains visually stable while the
  module enters loading state; Transcript and Composer use the same new owner.
- A successful change moves focus to the Story Context summary unless the
  activation originated from pointer input and the opened destination provides
  a clearer focus target.
- A failed change restores the last authoritative selection and leaves a plain
  inline explanation with `Try again`.
- If a frame disappears after refresh, the runtime selects `Present`, explains
  the fallback once, and never preserves the missing id in Panel state.
- `Open Frames` opens or focuses the registered Frames Widget. It does not fake
  an embedded editor when no compatible placement is available.
- Switching Panels never changes story or frame by itself.

## States

| State | Presentation | Behavior and recovery |
|---|---|---|
| No active story | `No story open` with `Open Library` and `Create Story` | No disabled frame control is shown |
| Loading story | Stable module skeleton for title and frame summary | Prior story data is not presented as current |
| Present only | Story title plus `Present`; no redundant switcher | `Open Frames` remains available when supported |
| Multiple frames | Selected summary plus ordered switcher | Selection updates the shared story owner |
| Frame changing | Selected target and concise loading state | Duplicate activation is ignored |
| Missing remembered frame | `Present` plus one-time fallback explanation | Missing id is discarded from route/presentation state |
| Story unavailable/offline | Preserved geometry and plain error | Retry the owner-qualified story load or return to Library |

## Responsive and accessibility behavior

- Narrow toolbar placement changes a segmented frame row into one labelled
  select/menu before labels wrap or truncate beyond recognition.
- Compact phone staging preserves story title, selected frame, and frame switch
  access. Turn count and kind/ordinal metadata disappear first.
- A toolbar staged as an overlay receives the same current frame and does not
  create a mobile-only navigation model.
- The frame control is labelled `Story frame`; the selected item uses
  `aria-current` or the native selected semantic, not color alone.
- Keyboard order is title context, frame control, `Open Frames`, then Widget
  actions according to the common Module contract.
- Touch targets are at least 44 px even when visible rows remain compact.
- Loading and fallback changes announce once. Merely tabbing between frame
  options does not announce the story title repeatedly.
- Reduced motion removes selection interpolation. Solid and high-contrast modes
  preserve the selected marker and focus boundary.

## Persisted presentation state

Panel persistence may retain collapsed state and an explicit compact/detailed
display preference. It never stores story id, frame id, frame records, route,
turn count, or loading/error state.

Selected story/frame remains application route and runtime state. This keeps
two instances synchronized and prevents a saved Panel from silently reopening
a stale temporal branch.

## Catalog miniature

The miniature shows a representative story title, `Present`, and two short
frame labels in the placed Widget's compact hierarchy. It is inert: no real
story names, selected route, dropdown, create action, or fake editing. The
whole miniature remains the direct-drag placement surface.

## Current mockup fit

This Widget is not among the active mockup's recorded nineteen definitions.
Add it to the Catalog as a custom-placement Widget; do not insert it into the
default Scene composition where the top shelf and stage already communicate
enough context. The Catalog count will increase when the next design slice is
translated, so the recorded nineteen-item artifact remains evidence of the
baseline rather than a final inventory ceiling.

## Mockup acceptance

- Present-only, multiple-frame, changing, missing-frame, no-story, offline,
  narrow-toolbar, phone, keyboard, touch, reduced-motion, solid, and
  high-contrast states are demonstrable.
- Switching the miniature's placed test instance changes the same visible
  owner used by Transcript and Composer.
- Frame switching never changes the selected story or opens a second story
  chooser.
- `Open Frames` reaches the one full frame-authoring owner.
- Two Story Context instances remain synchronized without sharing Panel layout
  preferences.
- No default Scene duplicate is introduced solely because the Widget exists.

---

# Widget design: Turn Progress

**Design state:** First draft, ready for mockup translation

**Type:** `story.turn-progress`

**Category:** Story

**Context:** Active story/frame run

**Presentation role:** Module

**Multiplicity:** Single per Panel; multiple instances may project one run

## User purpose

Know that generation is still working, understand its current activity in
plain language, see how long it has taken, and stop or safely retry the exact
run without reading engine internals.

## Main capability floor

Main proves that friendly progress currently:

- appears when a run begins and identifies the current phase;
- translates known engine stages, Scene Life work, character turns, and
  subagents into player-facing language;
- preserves an extension-provided label when the host has no friendly mapping;
- reports elapsed whole seconds;
- reports real parallel work as `+N running alongside`;
- exposes Stop for the captured run;
- distinguishes reset/retry, error, aborted, and completed outcomes;
- disappears after the run instead of leaving a false busy state.

Current replacement source preserves owner-qualified run lifetime, friendly
phase mapping, elapsed time, Stop, accepted-versus-retryable failure, and the
authoritative completion refresh. It does not yet expose Main's parallel count
in its public run projection. That is a capability gap for the shared runtime
adapter, not permission to invent a count in the Widget.

Main's location inside the composer footer and its mixed technical disclosure
are not part of this capability contract.

## Ownership and non-overlap

- The run coordinator owns run identity, captured story/frame, phase mapping,
  start time, concurrency facts, accepted state, Stop, retry eligibility,
  completion, and refresh.
- Turn Progress renders the friendly derived projection and delegates Stop or
  Retry to that coordinator. It never infers phase from Transcript text.
- Composer retains the primary submission action and may show a concise
  `Generating`/`Stop` state while mounted. Turn Progress is the durable detailed
  projection and must agree with it.
- Live Technical Detail owns raw stage keys, event types, token output, resets,
  and warnings. Turn Progress never exposes those merely to fill space.
- Background Work/global status owns a run after the user navigates to another
  story. A newly selected story's Turn Progress does not impersonate the old
  owner.

## Anatomy

1. **Module bar** — `Turn Progress`, run-state marker, and ordinary Widget
   actions.
2. **Current phase** — one prominent friendly line such as `Writing the scene`
   or `Mara is deciding what to do`.
3. **Time and concurrency** — elapsed Mono time plus an optional truthful
   `2 working alongside` note. Empty concurrency is omitted.
4. **Outcome line** — used only for retry, stopping, stopped, refresh, or error
   information. It does not become a permanent history feed.
5. **Run action** — `Stop` while cancellable, `Stopping…` while settling, or
   `Retry` only when the runtime confirms that the failed start was not
   accepted and the same owner-qualified operation remains safe.

At larger sizes the Module may show up to three recent friendly phase labels as
a quiet completed/current trail. This is presentation derived from the current
run only, not a promised pipeline or persisted history. It disappears entirely
at the minimum height.

## Honest progress model

Sonder's pipeline can branch, run extension steps, repeat work, and perform
parallel character or specialist operations. Therefore this Widget has:

- no percentage;
- no determinate progress bar;
- no fixed number of steps;
- no estimated finish time;
- no animation that implies a known remaining distance.

The trustworthy progress facts are current friendly phase, elapsed time, real
concurrency, cancellability, and final outcome. An indeterminate activity mark
may move gently when motion is enabled, but its shape never fills toward 100%.

## Visual and material treatment

- Use the standard Module bar and Glass body.
- Friendly phase is the strongest body line in compact Sans.
- Elapsed time is quiet Mono. It does not become a stopwatch spectacle.
- The run-state marker uses text plus a restrained semantic accent; it never
  pulses the entire Widget or changes geometry.
- Stop is an explicit labelled action. Destructive color is restrained because
  stopping generation is recoverable control, not deletion.
- A recent-phase trail, when visible, uses short text rows and one current
  marker rather than a vertical dashboard timeline.

## Placement and geometry

| Contract | Value |
|---|---|
| Minimum useful size | 200 x 92 px |
| Preferred size | 286 x 152 px |
| Horizontal support size | 320 x 76 px |
| Supported zones | left/right toolbar; compact or medium grid; focused support strip |
| Unsupported zones | reading-stage center; composer action cell |
| Resize | Width and height within Module bounds; recent trail appears only with capacity |
| Stack | Supported with other status/reference Modules |
| Float | Supported as a bounded run monitor |
| Collapse | Supported; collapsed state retains friendly phase and Stop when a run is active |

The default Scene Panel keeps the top shelf's concise global state and
Composer's immediate run action. Turn Progress is Catalog-first rather than a
mandatory third copy in the starter composition.

## Behavior

- When the active story owns no run, the Widget presents quiet `Ready` state;
  it does not disappear and collapse the surrounding layout.
- Start changes to `Getting started…` immediately from coordinator state, then
  adopts emitted friendly phases.
- Elapsed time is computed from the captured start time so remounts do not
  restart the clock.
- Parallel count appears only from a real group/coordinator fact. It clears when
  the group settles.
- Stop always addresses the captured run, disables after activation, and reads
  `Stopping…` until the coordinator settles.
- A generation reset reports `Trying that step again` with the runtime reason
  only when the reason is safe player-facing copy. It does not reset elapsed
  time or imply a second turn.
- Completion holds `Turn complete` briefly, then returns to `Ready` only after
  authoritative story refresh. The brief hold is presentation, not persisted
  run state.
- A retryable pre-acceptance failure exposes `Retry`. An accepted failure or
  refresh failure explains the next safe action without offering duplicate
  generation.
- Navigating away replaces this Widget with the new context's state. Persistent
  global status continues to name and control the prior run.

## States

| State | Presentation | Behavior and recovery |
|---|---|---|
| No active story | `Open a story to see turn progress` | `Open Library` may be offered; no run controls |
| Ready | Quiet ready marker | Stable geometry, no fake history |
| Starting | `Getting started…` plus elapsed time | Duplicate generation activation refused by runtime |
| Running | Friendly phase, elapsed, optional real concurrency, `Stop` | Phase changes do not move the action |
| Retrying a step | `Trying that step again` plus safe reason when available | Same run and elapsed clock continue |
| Stopping | `Stopping generation` and disabled `Stopping…` | Wait for authoritative settlement |
| Stopped | Brief `Generation stopped` | Return to Ready after story refresh |
| Completed/refreshing | `Turn complete · Saving the story` | Ready only after authoritative refresh |
| Retryable failure | Plain failure and `Retry` | Retry repeats the exact unaccepted operation |
| Non-retryable failure | Plain failure without generation Retry | Offer the runtime's safe refresh/recovery route |
| Run belongs elsewhere | Current story's Ready/no-run state | Global status, not this Widget, owns the other run |

## Responsive and accessibility behavior

- In a narrow toolbar, phase wraps to two lines before concurrency or recent
  trail is shown. The action remains visible.
- In short height, recent phases disappear first, then secondary outcome copy;
  friendly phase, elapsed time, and active Stop remain.
- Compact phone overlays preserve the same Widget rather than moving progress
  into a mobile-only bottom navigation item.
- The phase/outcome container is one polite status region. It announces phase
  and outcome changes, not every elapsed-second tick.
- The activity mark is decorative when the text already communicates state.
- Stop and Retry have explicit names and 44 px touch targets. Focus returns to
  the stable Module state after settlement.
- Reduced motion freezes the indeterminate marker. Solid and high-contrast
  modes retain text, state marker, focus, and action boundaries.

## Persisted presentation state

Panel persistence may retain collapsed state and whether the recent friendly
trail is shown. It never stores run id, story/frame owner, phase, start time,
elapsed time, concurrency, failures, or action eligibility.

## Catalog miniature

The miniature shows representative `Writing the scene`, `00:42`, `2 working
alongside`, and a visible `Stop` action within the real compact anatomy. It is
inert, uses no timer, does not pulse, and never attaches to a real run. The
whole miniature is the direct-drag surface.

## Current mockup fit

This Widget is not in the recorded nineteen-definition registry. Add it to the
Catalog without inserting it by default beside the top-shelf status and
Composer. Its miniature should make the distinction from Background Work
visible: Turn Progress is one current story turn; Background Work summarizes
asynchronous work beyond that local run.

## Mockup acceptance

- Ready, starting, running, parallel, retrying-step, stopping, stopped,
  completed/refreshing, retryable failure, non-retryable failure,
  run-elsewhere, narrow, short-height, phone, keyboard, touch, reduced-motion,
  solid, and high-contrast states are demonstrable.
- No state displays a percentage, step total, finish estimate, or invented
  concurrency.
- Elapsed time survives Widget and Panel remount without becoming persistent
  Panel data.
- Stop and Retry address the initiating story/frame operation after navigation
  changes.
- Phase announcements occur once while elapsed ticks remain silent.
- Composer, top shelf, and Turn Progress report compatible states without
  becoming three independent run owners.

---

# Widget design: Live Technical Detail

**Design state:** First draft, ready for mockup translation

**Type:** `story.live-technical-detail`

**Category:** Story

**Context:** Active story/frame run

**Presentation role:** Workspace/editor

**Multiplicity:** Single per Panel; multiple instances may observe one bounded
live event buffer

## User purpose

Inspect what the engine is doing during the current turn, including attributed
stage output, parallel work, resets, warnings, and failure details, without
forcing technical language into the player's normal writing flow.

## Main capability floor

Main proves that live technical detail currently:

- can be opened while generation is already in progress;
- creates attributed rows for stage starts and streamed output;
- distinguishes stages running in parallel;
- marks completed stages;
- clears/restarts affected output when generation emits a reset and explains
  that retry;
- reports aborted and error events;
- batches token-driven DOM updates to one animation frame rather than rewriting
  the entire log for every token;
- emits generation events to extensions only after host handling.

Current replacement source already keeps a bounded 120-entry, owner-qualified
non-token event trail, but projects only `type`, `key`, `label`, and `reason`.
That metadata trail is useful scaffolding; it does not satisfy Main's raw live
output floor. The shared runtime adapter must provide a safely rendered,
bounded attributed stream without putting raw tokens into the global store on
every network event.

The classic checkbox, unstructured full-width `<pre>`, and permanent proximity
to Composer are not part of the capability contract.

## Ownership and non-overlap

- The generation/run coordinator owns the one network stream, event ordering,
  run identity, abort, reset semantics, and completion.
- A bounded live-detail adapter owns batching, stage attribution, safe text
  normalization, and the current run's transient display buffer.
- Live Technical Detail renders that adapter. Mounting another instance creates
  another view, not another stream or buffer owner.
- Turn Progress owns friendly phase, elapsed time, and normal Stop/Retry
  reassurance. This Widget may repeat the current run state in its header only
  to orient technical inspection.
- Turn Inspector owns persisted, completed-turn pipeline evidence and versioned
  detail. Live Technical Detail does not refetch or pretend to preserve that
  history. On completion it hands off with `Open in Turn Inspector` when a turn
  id exists.
- Notices/global status own user-facing failure recovery. Raw detail may explain
  more, but it never becomes the only place a failure is communicated.
- The extension registry receives normalized host-handled events from the
  runtime. The Widget does not broadcast DOM text or untrusted raw markup.

## Anatomy

1. **Workspace bar** — `Live Technical Detail`, an `Advanced` qualifier, current
   run state, and ordinary Widget actions.
2. **View controls** — `Follow output` and `Wrap lines`. These are presentation
   controls, not stream pause/resume controls.
3. **Stage rail** — ordered attributed stage rows with technical key/label,
   running/completed/reset/error state, and parallel-group marker.
4. **Output viewport** — the selected stage's safely rendered plain-text output
   in Mono, with its own scroll owner and preserved selection.
5. **Event notices** — inline reset, warning, abort, error, and truncation
   markers at the point they occurred.
6. **Completion handoff** — `Open in Turn Inspector` after a completed turn is
   addressable; absent while live or when no persisted turn exists.

The first mockup may combine stage rail and output into stacked disclosure rows
at medium width, but it must preserve attribution. A single anonymous log is
not an acceptable compact mode.

## Visual and material treatment

- Use Workspace/editor material with one explicit 30 px bar and one internal
  scroll owner.
- Technical keys, timestamps when present, and output use Mono; stage labels
  and controls use compact Sans.
- Running, complete, reset, warning, and error states use glyph + text +
  restrained semantic accent. Raw output does not become a rainbow console.
- Parallel work is shown by a shared group marker or adjacency rule, not by
  overlapping animated cards.
- Output is assigned with text semantics only. It is never interpreted as HTML,
  Markdown, a localization key, or a source of controls.
- The surface is intentionally denser than player-facing Widgets but remains an
  Atmospheric Workbench module, not a pasted developer terminal.

## Placement and geometry

| Contract | Value |
|---|---|
| Minimum useful size | 320 x 220 px |
| Preferred size | 640 x 420 px |
| Supported zones | focused dominant region; medium/wide grid; compatible technical stack; bounded floating layer |
| Unsupported zones | narrow toolbar; composer strip; reading-stage center |
| Resize | Both axes; rail becomes stacked disclosures below useful split width |
| Stack | Supported with Turn Inspector and other technical review Widgets |
| Float | Supported within Panel bounds and minimum size |
| Collapse | Supported; collapsed header reports only live/complete/error state |

Placing this Widget must not reduce Transcript below its minimum reading
measure. In the shipped Scene template it is Catalog-only; an expert Panel or
temporary floating placement is the expected use.

## Live buffer and performance contract

- The network stream is consumed once by the run coordinator.
- The adapter groups output by run and stage and schedules visual publication
  no more than once per animation frame.
- Appending output never rebuilds every prior row or moves the user's text
  selection.
- The buffer is bounded for the current run. When earlier live output is
  trimmed, a stable marker says `Earlier live output was omitted` and the
  completion handoff points to Turn Inspector when durable detail exists.
- Closing, moving, stacking, or remounting the Widget does not affect the run.
  Reopening during that same run attaches to the existing bounded buffer.
- The transient buffer is discarded when its run is no longer the active live
  inspection owner. It is not serialized into Panel persistence or local draft
  storage.
- `Follow output` follows the selected stage only while the viewport is already
  pinned near its end. Scrolling upward automatically turns follow off without
  pausing collection.
- `Wrap lines` changes presentation only. Copy preserves the underlying text.

## Event behavior

- `step_start` creates or activates an attributed stage and records parallel
  membership when the runtime supplies it.
- Token/output events append to that stage through the batched adapter.
- Completion marks the exact stage complete without clearing its output.
- Reset marks the affected attempt, preserves a concise reset record, and opens
  a fresh attempt region for the retried output. It never silently overwrites
  the evidence the user was inspecting.
- Abort ends live following and marks the run stopped.
- Error marks the responsible stage when known and also leaves normal
  player-facing recovery to Turn Progress/notices.
- Late events for a settled or nonmatching run owner are rejected.
- Extension events are exposed only after the host has normalized and handled
  them; extensions never receive the Widget's rendered DOM.

## States

| State | Presentation | Behavior and recovery |
|---|---|---|
| No active story | Explanation that technical detail follows a story turn | No fake log or disabled terminal controls |
| Ready/no run | Empty attributed workspace with `Start a turn to see live detail` | Remains available for expert layout planning |
| Attaching mid-run | Stable stage rail skeleton and `Connecting to this run…` | Attaches to existing coordinator buffer; no second stream |
| Streaming | Attributed stages and batched output | Follow/wrap controls remain operable |
| User scrolled back | `Follow output` off, visible new-output marker | Collection continues without stealing scroll |
| Parallel stages | Shared group marker on concurrently active stages | Ordering remains deterministic within attributed events |
| Reset/retrying | Prior attempt marked reset; new attempt region active | Reason shown as plain text when supplied |
| Truncated | Omission marker at trimmed boundary | Continue live; use Turn Inspector after completion |
| Stopping/stopped | Header and final event marker | No further auto-follow after settlement |
| Error | Responsible stage and safe technical detail | Normal retry/recovery remains outside the raw log |
| Complete | Stable final live buffer plus handoff | `Open in Turn Inspector` opens durable completed evidence |
| Completed turn unavailable | Final transient buffer without handoff | Explain that durable detail is unavailable; do not fabricate it |

## Responsive and accessibility behavior

- Below useful split width, each stage becomes a keyboard-operable disclosure
  with its output directly below; attribution never disappears.
- On phone, the Widget stages as a full-height Panel overlay with its own close
  route and safe-area padding. It does not become a tiny console under Composer.
- Short landscape favors the stage rail and selected output; secondary control
  labels may compact to icons only when their accessible names remain explicit.
- The raw output viewport uses `translate="no"`, preserves whitespace, supports
  text selection/copy, and has an accessible name including the selected stage.
- Raw tokens are not a live region. The header politely announces only run,
  reset, error, and completion transitions.
- Stage disclosures, follow, wrap, and handoff are fully keyboard operable.
  Focus is not dragged to the newest output.
- Touch controls meet 44 px targets even though output typography remains dense.
- Reduced motion disables follow interpolation and animated running markers.
  Solid and high-contrast modes preserve attribution, state, selection, and
  focus without relying on glass or color.

## Persisted presentation state

Panel persistence may retain selected presentation density, line wrapping,
follow preference, and collapsed state. Current stage selection may remain in
the mounted instance while that stage exists, but it is not serialized and
must safely fall back when the stage disappears.

It never stores raw output, run events, run id, story/frame identity, error
payloads, request/correlation ids, provider data, prompts, credentials, or
completion history.

## Catalog miniature

The miniature shows an `Advanced` marker, three representative attributed
stages, one short Mono output fragment, and restrained running/complete marks.
It contains no real prompt/output, timer, provider, request id, blinking caret,
or fake live subscription. The whole miniature is the direct-drag surface.

## Current mockup fit

This Widget is not in the recorded nineteen-definition registry. Add it to the
Catalog as an advanced custom-placement Widget. Its miniature should be visibly
wider/denser than Turn Progress and Turn Inspector: live attributed output is
the identity, not a generic activity spinner or a saved-turn form.

The prototype may use representative stage/output text, but it must implement
follow-off-on-scroll, disclosure, reset, truncation, completion-handoff, and
responsive staging as real mock interactions before the design is marked
reviewed.

## Mockup acceptance

- Ready, mid-run attach, streaming, scrolled-back, parallel, reset, truncated,
  stopping, stopped, error, complete, no-durable-turn, narrow, phone,
  short-landscape, keyboard, touch, reduced-motion, solid, and high-contrast
  states are demonstrable.
- Two instances observe one simulated run without creating duplicate streams or
  divergent stage order.
- High-frequency simulated tokens publish at most once per animation frame and
  do not rebuild prior output.
- Scrolling up stops follow without stopping collection or stealing selection.
- Reset preserves a marked prior attempt and attributes the new attempt.
- Raw output is always plain text and never localized or interpreted as markup.
- Completion links to Turn Inspector only when a durable turn id exists.
- Panel persistence contains no run or raw-output data.

---

# Shared boundary: selected-turn review

Turn Versions and Turn Inspector answer different questions about one saved
turn. They share selection and mutation ownership without sharing a surface.

```text
active story + active frame
            │
            └── selected turn
                  ├── narration versions ──> Turn Versions
                  └── stored steps/evidence ──> Turn Inspector
```

The selected-turn service is transient application presentation state:

- Its identity is `active story + active frame + turn id`, never a bare turn id.
- Opening `Versions` or `Turn details` from Transcript selects that exact turn
  before focusing or placing the corresponding Widget.
- A compact turn navigator in either Widget changes the one shared selection.
  It is not another Transcript and shows no independent story picker.
- When story or frame changes, a selected turn that does not belong to the new
  owner is discarded. The latest saved turn in that frame becomes the default
  only when the destination needs a turn.
- Selection is not serialized in Panel state and cannot pin a Widget to a
  different story. Layout may persist; story data may not.
- Loads and mutations capture the qualified selection and reject late results
  after selection changes.
- All mutations pass through the Play/runtime service and refresh the
  authoritative story before either Widget claims success.
- A current generation may make a selected turn temporarily non-editable.
  Neither Widget bypasses the chat/frame pipeline gates.

Turn Versions is the literary/presentational history of a beat. Turn Inspector
is the engine evidence that produced and committed it. A narration variant may
change what the saved beat reads like without changing the already-committed
world; a pipeline step variant may change what a rerun would use and therefore
has a different safety contract.

The current replacement already centralizes variants, input/prose edits,
deletion, pipeline loads, and branching in `play-runtime.js`. Its view still
opens Versions and Turn details as one-off dialogs. Widget conversion replaces
those dialogs with shared selected-turn projections; it does not duplicate
their routes or move mutation authority into Panel instances.

The shared selected-turn service does not exist yet. Current one-off loads have
no selection revision predicate and a dialog may outlive the story that opened
it. Building the service and routing every result through its qualified
`isCurrent` guard is a prerequisite for independently mounted Widgets.

---

# Widget design: Turn Versions

**Design state:** First draft, ready for mockup translation

**Type:** `story.turn-versions`

**Category:** Story

**Context:** Selected turn in the active story/frame

**Presentation role:** Workspace/editor

**Multiplicity:** Single per Panel; all instances observe the shared selected
turn while retaining only harmless view preferences

## User purpose

Read the available narration renderings of one beat, choose which generated
version the Transcript uses where the server permits it, and reach the real
turn-level edit, reroll, branch, and delete operations with their consequences
made explicit.

## Main capability floor

Main and the current routes prove that turn versions currently:

- load every narrator variant for a selected turn in stable creation order;
- identify the active variant and render it with the turn's speech index and
  dialogue colors rather than as flat raw text;
- move cyclically through previous/next versions and report `N of M`;
- permit active narration selection only for the latest eligible turn;
- treat narration selection as presentation: committed events, world state,
  memory, and lore are not rerun or marked stale;
- allow a free-text narration edit as another presentational variant, including
  on an older turn while the chat is idle;
- allow player-input editing, marking the latest affected pipeline stale where
  required by the server;
- reroll only the latest eligible turn and stream the resulting generation;
- create a new story branch from an eligible historical turn;
- delete only the latest eligible turn after destructive confirmation;
- refuse mutations while the relevant pipeline/chat gate is active.

Main changes the active version as each arrow is pressed. The modernization
retains selection capability but separates **preview** from **Use this
version**. Browsing is local and reversible; only the explicit action writes.
This prevents an exploratory arrow key from silently changing the story.

## Ownership and non-overlap

- Selected-turn service owns the qualified turn selection.
- Play/runtime owns variant loads, active-version mutation, player-input edit,
  narration edit, reroll, branch, deletion, story refresh, and eligibility.
- Turn Versions owns only preview index and local open/closed edit treatments.
- Transcript remains the reading owner and reflects the active version after
  authoritative refresh. It may launch this Widget but does not keep a second
  version state.
- Turn Inspector owns step variants, reasoning, rerun/resume, and step edits.
- Turn Progress and Live Technical Detail own any reroll once generation
  starts. Turn Versions shows a concise handoff state rather than embedding
  another run monitor.
- Branch creation belongs to global/background task ownership once accepted;
  the Widget cannot cancel it by unmounting.

## Anatomy

1. **Workspace bar** — `Turn Versions`, selected turn number, latest/historical
   status, and ordinary Widget actions.
2. **Turn navigator** — previous turn, concise input excerpt/turn index, and next
   turn. It changes the shared selected-turn owner.
3. **Version navigator** — `Previous version`, `N of M`, `Next version`, plus
   `Active` on the server-selected rendering.
4. **Literary preview** — one narration rendering at the canonical 650-680 px
   measure, using the same prose/speech renderer as Transcript.
5. **Selection action** — `Use this version` appears only when the preview is
   not active and the server says selection is eligible.
6. **Consequence note** — concise fixed copy: selecting or editing narration
   changes the words shown, not the world and memory already recorded.
7. **Turn actions** — `Edit input`, `Edit narration`, `Reroll`, `Branch here`,
   and `Delete latest turn` appear only when their authoritative capability is
   available. Destructive or generative actions remain explicit.

The Widget never places prose versions side by side by default. Side-by-side
cards break reading measure and encourage visual diffing of literary prose.
One faithful preview plus version navigation is the designed comparison model.

## Version and mutation behavior

- Variant load is owner-qualified and may not block Transcript rendering.
- Previous/next updates local preview immediately and never writes.
- `Use this version` captures turn id, variant id, and selection revision. On
  success it refreshes the story and marks the returned active variant. On
  failure it preserves the preview and reports that the story was unchanged.
- Arrow keys navigate versions only while focus is in the version navigator or
  literary preview. They do not intercept cursor movement in editors or the
  whole Panel.
- A single-version turn shows `Only one narration version` and no disabled
  previous/next controls.
- `Edit narration` creates an owner-qualified draft separate from Panel state.
  Save inserts/activates the authoritative presentation variant; Cancel leaves
  the story unchanged.
- `Edit input` explains that changing the latest input can make generated steps
  stale. The server, not the Widget, decides the exact staleness result.
- `Reroll` repeats Main's explicit warning that world state, memories, lore, and
  later changes covered by restoration return to the start-of-turn checkpoint.
  Accepted reroll hands off to the shared run coordinator.
- `Branch here` creates a new story from the selected checkpoint through the
  established background task. It opens the new story only after the server
  returns its identity.
- Delete is offered only for the server-eligible latest turn. Its confirmation
  states that the story returns to before that turn and that this UI has no
  undo.
- After deletion, selection moves to the new latest turn or an empty state; it
  never retains the deleted id.

## Visual and material treatment

- Use Workspace/editor material with one explicit 30 px bar.
- The preview remains literary content on canvas-toned material inside the
  Workspace, not a stack of glass cards.
- Version navigation and actions use compact Control chrome. `Active` is a
  restrained semantic label, not a filled marketing badge.
- Consequence notes use quiet Sans and never compete with prose.
- Turn input excerpts and version counts may use Mono for identity; prose uses
  the configured story reading typography.
- Generative/destructive actions are grouped away from ordinary version
  browsing so accidental activation is difficult.

## Placement and geometry

| Contract | Value |
|---|---|
| Minimum useful size | 360 x 280 px |
| Preferred size | 700 x 520 px |
| Supported zones | focused dominant region; medium/wide grid; selected-turn stack; bounded floating layer |
| Unsupported zones | narrow toolbar; composer strip |
| Resize | Both axes while preserving the prose measure ceiling |
| Stack | Supported with Turn Inspector; inactive peer remains mounted only according to stack policy |
| Float | Supported within Panel bounds and minimum size |
| Collapse | Supported; collapsed header retains selected turn and unsaved-editor marker |

## States

| State | Presentation | Behavior and recovery |
|---|---|---|
| No active story | `Open a story to review turns` | Offer Library, no turn controls |
| No turns in frame | `This frame has no saved turns yet` | Keep selected-turn owner empty |
| Loading selection | Stable turn/version skeleton | Reject late prior-turn response |
| No narrator output | `This turn has no saved narration version` | Keep turn actions that remain independently eligible |
| One version | One literary preview and `Only one narration version` | No inert arrows |
| Multiple versions, active | Active preview and version navigation | Browsing changes preview only |
| Multiple versions, previewing | Non-active preview plus `Use this version` when eligible | Cancel/reselect active without a write |
| Historical/read-only selection | Versions remain readable; server-blocked actions explain why | Branch/edit narration remain only if separately eligible |
| Editing input | Owner-qualified draft and consequence copy | Save through runtime; Cancel leaves source intact |
| Editing narration | Literary draft and presentation-only copy | Save creates/activates variant after refresh |
| Reroll running | Stable selected turn with handoff to Turn Progress | No duplicate mutation controls |
| Branch creating | Named background task state | Unmount does not cancel accepted work |
| Mutation conflict | Plain pipeline/eligibility explanation | Refresh eligibility; never force the write |
| Load/save failure | Preview or draft retained with exact failed operation | Retry only that load/save where safe |
| Selected turn deleted/missing | Selection falls to authoritative latest/empty | Explain the change once |

## Responsive and accessibility behavior

- Wide layouts center the literary preview at the Transcript reading measure.
- Medium layouts place version navigation above preview and actions below.
- Narrow/phone staging uses a full-height Panel overlay; turn and version
  navigators remain sticky within the Widget while prose owns the scroll.
- Short landscape hides the input excerpt and consequence note before reducing
  preview readability or action reachability.
- Version count is announced as `Version N of M`; active status is text, not
  color alone.
- Version arrow keys are scoped and documented. Editors retain normal text
  navigation and composition behavior.
- Edit fields have explicit labels and unsaved state. Focus returns to the
  invoking action after Cancel or successful save.
- Touch actions meet 44 px targets; previous/next remain separate targets.
- Reduced motion removes preview crossfade. Solid and high-contrast modes
  preserve selected/active distinction, focus, and consequence grouping.

## Persisted presentation state

Panel persistence may retain preferred preview density, wrap preference, and
collapsed state. It never stores selected turn, previewed/active variant,
literary edit drafts, story/frame ids, eligibility, branch response, or run
state.

Edit drafts remain in the qualified draft service as
`story + frame + turn + edit kind`. Merely previewing another generated version
is transient and requires no recovery prompt because it has not changed data.

## Catalog miniature

The miniature shows `Turn 18`, `Version 2 of 3`, one short literary paragraph,
and an `Active` marker on a different representative version state. It contains
no real story prose, working arrows, fake unsaved draft, or destructive action.
The whole miniature is the direct-drag surface.

## Current mockup fit

Turn Versions is not in the recorded nineteen-definition registry. Add
`story.turn-versions` as a wide selected-turn Workspace. It should visually pair
with the existing Turn Inspector miniature without looking identical: literary
preview is Versions' identity; attributed structured evidence is Inspector's.

It remains Catalog-first. Transcript's per-turn actions are the normal launch
path, and placing the Widget gives that launch a durable destination rather
than creating another permanent default Scene region.

## Mockup acceptance

- No-story, no-turn, loading, one-version, previewing, active, historical,
  editing-input, editing-narration, reroll, branch, delete, eligibility
  conflict, missing-turn, error, narrow, phone, short-landscape, keyboard,
  touch, reduced-motion, solid, and high-contrast states are demonstrable.
- Browsing versions makes no write; `Use this version` is the only generated
  version-selection commit.
- The preview uses the same speech/color rendering as Transcript at the same
  reading measure.
- Mutation availability follows server eligibility rather than `is latest`
  styling alone.
- Reroll hands off to one shared run; Branch survives Panel unmount.
- Edit drafts survive compatible Widget remount and never enter Panel layout
  persistence.
- Two instances share selected turn and active server version without sharing
  local preview index or editor focus.

---

# Widget design: Turn Inspector

**Design state:** First draft, ready for mockup translation

**Type:** `story.turn-inspector`

**Category:** Story

**Context:** Selected saved turn in the active story/frame

**Presentation role:** Workspace/editor

**Multiplicity:** Single per Panel; all instances observe one selected turn and
one authoritative completed pipeline

## User purpose

Inspect how a saved turn was interpreted, perceived, decided, narrated, and
committed; read each step through the relevant mind/specialist/perceiver lens;
and perform the real resume, rerun, step-version, or step-edit operations only
when the engine proves they are safe.

## Main capability floor

Main and the pipeline routes prove that Turn Inspector currently:

- loads ordered saved pipeline steps for any selected turn;
- exposes every stored variant per step and identifies the active variant;
- reports step key, label, order, and stale state;
- maps bare perceiver ids to historical participant/player names;
- derives readable lenses for perception views, character-loop minds,
  specialist ownership, or ordinary structured keys;
- retains a full JSON view while offering targeted human-readable slices;
- separates model reasoning from validated/committed content behind an explicit
  disclosure;
- shows engine notes including real parallel membership, provider/model call
  kind and attribution, input/output/cached token counts, duration, and
  warnings;
- reports whether the turn is editable, blocked by another frame, resumable,
  and which step would resume next;
- can activate another stored step variant, reroll only one step, run the
  pipeline from a step, resume an incomplete turn, and edit supported step
  content when the server says the turn is editable;
- refreshes the Inspector after mutations and runs generation through the same
  pipeline coordinator.

Current replacement `pipeline-inspector.js` preserves the strongest reading
improvements—specialist/perceiver/mind lenses, engine notes, reasoning, and
step-version browsing—but its current dialog does not expose Main's
editability, blocked-frame explanation, resume, variant activation, step edit,
step reroll, or run-from-here actions. Those are capability gaps the Widget
design explicitly restores through current routes and safety gates.

Main also carries two safety repairs that the current Interface branch has not
yet integrated: discarded recompute lineage deletes downstream checkpoints,
and editing/activating an applied commit step marks that step stale. Inspector
mutation controls remain unavailable until those guards and their Main
regressions are present in the production runtime. Presentation completeness
must not get ahead of recompute integrity.

## Ownership and non-overlap

- Selected-turn service owns qualified turn selection.
- Pipeline read service owns saved steps, variants, historical name map,
  eligibility, blocked-frame state, and resume key.
- Play/run coordinator owns resume, rerun, step reroll, Stop, live events,
  completion, and story refresh.
- Step edit draft service owns unsaved content under
  `story + frame + turn + step + source variant`.
- Turn Inspector owns only selected step, selected read lens, previewed step
  variant, disclosures, scroll, and edit surface state.
- Turn Versions owns narrator-only literary variants and story-level mutations.
  Inspector may expose the narrator step as engine evidence but never becomes a
  second prose-history browser.
- Live Technical Detail owns transient current-run output. Inspector remains
  saved evidence; starting a rerun hands live following to that Widget.
- Extension step renderers remain embedded within the owning step. They are not
  separately advertised top-level Widgets.

## Anatomy

1. **Workspace bar** — `Turn Inspector`, selected turn, saved/incomplete/stale
   status, and ordinary Widget actions.
2. **Turn navigator** — changes the shared selected turn without opening a
   second Transcript.
3. **Eligibility strip** — `Saved`, `Incomplete · next: Narration`, `Read only`,
   or `Blocked by activity in another frame`, followed by Resume when valid.
4. **Step rail** — ordered stage labels with active-variant, stale, warning, and
   incomplete markers. Technical keys remain secondary.
5. **Step variant navigator** — previews prior/next stored variants with an
   explicit `Use this step version` action only when eligible.
6. **Lens bar** — context-aware choices: `Written by`, `Seen by`, `Decided by`,
   structured keys, and `{ } JSON`.
7. **Evidence viewport** — safe plain-text or registered extension rendering of
   the selected lens. It owns the main scroll.
8. **Engine notes** — parallel group, LLM role/provider/model, in/out tokens,
   duration, and warnings in a compact technical ledger.
9. **Reasoning disclosure** — closed by default and explicitly described as
   unvalidated model reasoning, not fiction or committed state.
10. **Step/run actions** — `Edit step`, `Reroll only this step`, `Run from here`,
    or `Resume turn` according to server eligibility and step shape.

## Reading and lens behavior

- The first selected step is the first incomplete/stale step when resumable;
  otherwise the first ordered step. User selection remains stable across a
  refresh when that step still exists.
- Lens choices are derived from the selected active/previewed content, never a
  fixed global toolbar.
- Specialist view separates prose-author-owned fields from delegated channels,
  names granted/filled/gated channels, failed specialists, and reconciliation
  repairs without rewriting source content. It also retains replaced-channel,
  manifest-event, resolved-event, and repair-error evidence when stored rather
  than collapsing it out of the human-readable lens.
- Perceiver view names the observer and shows only that stored view and its
  observations.
- Mind view groups stored rounds/results for the chosen character.
- Key view renders one structured field. JSON renders the whole stored content.
- Empty, null, missing, failed, and gated-out are distinct plain-text states.
- Raw content and reasoning use `textContent`/plain-text semantics. Only a
  registered trusted extension renderer may create structured DOM, and the host
  still owns containment, error isolation, and labelling.

## Mutation and draft behavior

- Previewing another step variant is local and never activates it implicitly.
- `Use this step version` explains that downstream results may become stale and
  invokes the current step-activation route only when `editable` is true.
- `Edit step` creates a qualified draft from the exact source variant/revision.
  If the source changes before save, the Widget reports a conflict and never
  overwrites it silently.
- Step editor selection/schema follows the registered step editor. Unsupported
  content remains read-only; raw JSON is not automatically an unrestricted
  write form.
- `Reroll only this step` re-enters generation at that step under the existing
  restore/staleness rules. `Run from here` reruns the selected step and every
  owned successor. Both use explicit consequence copy and the shared run
  coordinator.
- `Resume turn` is offered only when the server returns both `resumable` and a
  resume key. The key is orientation, not authority; the server rechecks.
- `blocked_by_other_frame` receives a named explanation. The Widget never
  converts a false `editable` into a generic disabled screen or bypass.
- While a mutation/run is active, edit controls settle into read-only state.
  Live phase/Stop belongs to Turn Progress and Live Technical Detail.
- After a successful mutation or run, authoritative story and pipeline data are
  reloaded before stale/active/complete markers change.

## Visual and material treatment

- Use the densest Workspace/editor treatment in the story family, with one
  30 px bar and one primary evidence scroll owner.
- Step rail and engine notes use compact Sans/Mono. Evidence uses Mono unless a
  trusted renderer supplies a more legible structured projection.
- Status combines glyph, text, and restrained accent. Stale and incomplete are
  not represented by opacity alone.
- Lens controls are compact tabs/segments, not decorative pills.
- Reasoning is visually and semantically separated from validated content.
- The Inspector is advanced tooling, but it keeps the Atmospheric Workbench's
  material, spacing, radii, and control grammar rather than imitating a generic
  developer console.

## Placement and geometry

| Contract | Value |
|---|---|
| Minimum useful size | 420 x 320 px |
| Preferred size | 880 x 600 px |
| Supported zones | focused dominant region; wide grid; selected-turn technical stack; bounded floating layer |
| Unsupported zones | narrow toolbar; composer strip; reading-stage center |
| Resize | Both axes; step rail becomes a labelled selector below split threshold |
| Stack | Supported with Turn Versions and compatible technical review Widgets |
| Float | Supported within Panel bounds and minimum size |
| Collapse | Supported; collapsed header retains selected turn and incomplete/error marker |

## States

| State | Presentation | Behavior and recovery |
|---|---|---|
| No active story | `Open a story to inspect turns` | No fake pipeline |
| No selected/saved turn | `Select a saved turn` or frame-empty explanation | Transcript launch or navigator supplies selection |
| Loading | Stable rail/evidence skeleton | Reject stale prior selection response |
| No materialized steps | Empty evidence with saved turn identity | Refresh; do not fabricate standard stages |
| Complete, read-only | Ordered steps and evidence without mutation actions | All lenses/variants remain inspectable |
| Editable | Eligibility strip and applicable step/run actions | Server rechecks every write |
| Incomplete/resumable | Next step identified with `Resume turn` | Resume hands off to shared run |
| Blocked by other frame | Named block explanation | Navigate to activity/global status; no bypass |
| Stale step/downstream | Stale markers and consequence explanation | Choose edit/rerun path only when eligible |
| Previewing step variant | Variant count and non-active preview | Explicit Use action required |
| Editing step | Qualified draft/editor and source revision | Save, conflict, Cancel, and recovery are explicit |
| Rerun/resume active | Saved evidence remains stable and controls read-only | Live state belongs to run Widgets |
| Extension renderer failed | Host error boundary and raw safe fallback | Other steps/renderers continue |
| Malformed variant | Plain parse failure with raw stored text option | Never execute or discard content |
| Load/mutation failure | Exact operation and retained view/draft | Retry safe read/write only |
| Selected turn missing | Shared selection falls to authoritative latest/empty | Explain once |

## Responsive and accessibility behavior

- Wide layout uses rail + evidence split. Medium layout may narrow the rail but
  never the evidence below readable width.
- Below the split threshold, step rail becomes a labelled step selector above
  lens controls. The selected step's status remains visible.
- Phone staging uses a full-height Panel overlay. Evidence, not the outer page,
  owns scrolling; engine notes and reasoning remain disclosures.
- Short landscape hides secondary notes before step identity, evidence, or
  applicable recovery action.
- Step selector, variants, lenses, disclosures, and actions are keyboard
  operable with visible focus. Focus does not jump on stream/refresh.
- Status labels include text. Raw evidence and reasoning are not live regions;
  load/mutation outcomes announce once.
- Evidence preserves whitespace, selection, copy, and `translate="no"`.
- Touch targets meet 44 px while technical rows remain visually compact.
- Reduced motion removes rail/viewport transition. Solid and high-contrast
  modes preserve step, lens, stale, warning, and focus distinctions.

## Persisted presentation state

Panel persistence may retain rail width, selected density, line wrapping,
collapsed state, and safe disclosure preferences. It never stores selected
turn, step ids, variant ids, lens content, reasoning, provider/model data,
tokens, warnings, eligibility, resume key, or run state.

Selected step/lens/previewed variant may remain mounted-instance state only.
Edit drafts stay in their qualified owner and are invalidated or conflicted
against source revision; they never enter the Panel envelope.

## Catalog miniature

The miniature shows a compact ordered step rail, one selected step, `Seen by`
lenses, a short structured evidence fragment, and one warning marker. It uses
representative safe data, no real reasoning/provider/request values, no fake
running stream, and no working rerun action. The whole miniature is the
direct-drag surface.

## Current mockup fit

`story.turn-inspector` is already one of the active mockup's nineteen registry
definitions, but it currently receives only a generic wide miniature. Replace
that generic preview with the designed attributed step/lens anatomy. Do not add
a second definition.

The Widget remains Catalog-first and compatible with a Turn Versions stack.
Launching `Turn details` from Transcript should select the turn and focus an
existing Inspector, place one in a compatible target, or stage a temporary
owner surface according to the common launch contract.

## Mockup acceptance

- No-story, no-turn, loading, no-steps, complete-read-only, editable,
  resumable, blocked-frame, stale, variant-preview, step-edit, conflict,
  rerun/resume, failed renderer, malformed data, load/mutation error,
  missing-turn, narrow, phone, short-landscape, keyboard, touch,
  reduced-motion, solid, and high-contrast states are demonstrable.
- Perceiver, mind, specialist, structured-key, and full-JSON lenses show
  distinct representative shapes without changing stored content.
- Reasoning is closed by default and labelled unvalidated; evidence remains
  selectable safe text.
- Step variant browsing does not write; Use/Edit/Reroll/Run/Resume availability
  follows server eligibility.
- Rerun/resume creates one shared live run and never a private Inspector stream.
- An extension renderer failure falls back safely without breaking other steps.
- Panel persistence contains no turn, step, pipeline, reasoning, or draft data.

---

# Shared boundary: condition, atmosphere, and work

These five Widgets may be visible around the same Scene, but they do not form a
single dashboard and do not share one state owner.

| Projection | Context clock | Owner |
|---|---|---|
| Player and Cast Condition | Current active story/frame state | One frame-qualified vitals service, split by `is_player` |
| Room Ambience | Turn currently being read and its room signature | Atmosphere/media runtime plus server ambience/cache/pins |
| Scene Backdrop | Turn currently being read and its visual signature | Atmosphere/media runtime plus server backdrop/cache |
| Background Work | Global accepted work across destinations | Task service and registered task providers |

The distinction between **current state** and **visible-turn atmosphere** is
intentional. Scrolling to a prior beat may show and play that beat's room, but
it must not make the player's current lungs, injuries, or the cast's current
condition travel backward in time.

Transcript publishes one visible-turn observation shared by backdrop and
ambience. When the reader is pinned to the end, the latest committed turn is
visible. When they dwell on a prior turn, cached atmosphere follows that turn's
room/signature. A new turn under the same story/frame owner is a context change
for atmosphere even though the route owner did not change.

Atmosphere follows these common rules:

- Cached media may apply immediately when enabled and safe to play.
- Commissioning new media waits for the configured visible-turn dwell so
  scrolling through history does not spend provider work on every crossed beat.
- The current explicit status-check policy remains valid: a Widget never starts
  a private polling loop. A future server-task bridge may deliver completion to
  Background Work and the atmosphere runtime; until then pending media offers
  `Check status`.
- Backdrop and ambience media are authenticated, private, immutable by content
  revision, and released when no longer visible/playing.
- Media changes never alter Transcript/Composer geometry.
- Story/turn changes reject late prior-context media results.
- Settings owns provider, source, credentials, licences, global enablement, and
  generation defaults. Scene Widgets own the current scene result and its
  direct playback/generation controls.

Condition follows one-fetch fan-out: Player Condition and Cast Condition
subscribe to one frame-qualified vitals response. Two placed Widgets never
issue competing requests or create different refresh clocks.

---

# Widget design: Player Condition

**Design state:** First draft, ready for mockup translation

**Type:** `story.player-condition`

**Category:** Story

**Context:** Current active story/frame

**Presentation role:** Module

**Multiplicity:** Single per Panel; multiple instances share one vitals
projection

## User purpose

See the player's current bodily condition beside the story without opening a
world editor or inferring health from prose.

## Capability and ownership

The authoritative frame-scoped vitals projection provides player identity and
four engine-labelled measures: air, stamina, nourishment/satiation, and injury.
`survival_get`, `survival_put`, and `/vitals` retain server ownership; the
Widget filters the shared response to `is_player`.

The Widget is read-only. Genre and Style/Story configuration owns whether
survival tracking is enabled and performs atomic enablement plus frame seeding
while the chat is idle. World State and the engine own actual physical change.

Main kept the player's condition beside Composer. Current replacement improves
request guards and accessible meters but exposes the player only inside a
combined Conditions tool. This Widget restores the passive projection without
absorbing the configuration toggle.

## Anatomy and behavior

1. **Module bar** — `Player Condition`, player name when it disambiguates, and
   ordinary Widget actions.
2. **Condition summary** — one calm engine-provided textual summary where
   available; never a guessed diagnosis.
3. **Vital rows** — label, accessible meter, and concise value/state for air,
   stamina, nourishment, and injury in the engine's authoritative order.
4. **Owner action** — `Open Story Style` when tracking is off or configuration
   is needed.

Meters use engine scale direction and labels. The Widget does not assume that a
higher numeric injury value is healthier, recolor every row, or convert
different measures into one synthetic health score.

The story-stage template may stage Player Condition in the closest compatible
support allocation to Composer when tracking is enabled, but it never narrows
the 650-680 px writing/reading measure. An explicitly placed Widget remains
present in its disabled/empty state rather than vanishing from a saved layout.

## Geometry, states, and responsive contract

| Contract | Value |
|---|---|
| Minimum useful size | 200 x 120 px |
| Preferred size | 260 x 180 px |
| Horizontal support size | 320 x 88 px |
| Supported zones | left/right toolbar; compact grid; story support strip |
| Unsupported zones | reading-stage center; composer action cell |
| Stack / Float / Collapse | Stack yes; bounded float yes; collapse yes with worst current condition retained |

| State | Presentation and recovery |
|---|---|
| No story | `Open a story to see player condition`; Library action only |
| Loading | Stable four-row skeleton; no prior owner presented as current |
| Tracking off | `Condition tracking is off` and `Open Story Style` |
| Unseeded/empty | `No player condition has been recorded for this frame` and refresh/configuration route |
| Ready | Current four vitals with engine labels and semantics |
| Offline/error | Plain explanation and owner-qualified Retry; last confirmed values may remain labelled `Last known` |

At narrow width, rows remain one label + meter + state; detailed values compact
before labels truncate. Horizontal support mode uses two columns only when each
meter retains a useful accessible label and visual length. Phone overlays keep
the same Module. Each meter has a programmatic name/value/min/max (or text state
when not numeric), and no update is announced unless its meaningful band
changes. Touch, reduced-motion, solid, and high-contrast modes retain 44 px
actions, text labels, focus, and non-color state.

## Persistence, miniature, and acceptance

Panel persistence may retain collapsed state and compact/detailed density. It
never stores vitals, player identity, tracking status, story/frame ids, or last
known data.

The Catalog miniature shows four representative labelled meters and one calm
summary with no real player data or animated values.

Acceptance requires no-story, loading, disabled, empty, ready, last-known,
offline/error, toolbar, horizontal, phone, keyboard, touch, reduced-motion,
solid, and high-contrast states; two instances must share one request and the
Widget must never mutate or synthesize condition.

---

# Widget design: Cast Condition

**Design state:** First draft, ready for mockup translation

**Type:** `story.cast-condition`

**Category:** Story

**Context:** Current active story/frame

**Presentation role:** Module

**Multiplicity:** Single per Panel; multiple instances share one vitals
projection

## User purpose

Scan the current bodily condition of tracked non-player participants without
mixing physiology with cast membership, position, or character editing.

## Capability and ownership

Cast Condition consumes the same frame-qualified `/vitals` response as Player
Condition and filters to non-player bodies. It is read-only. Cast owns roster,
activation, position, color, and story-card access; World State/engine owns
physical truth; Genre and Style owns tracking and condition-visibility
configuration.

Main offered both a full condition view and an optional passive `Others`
projection. Current replacement retains the setting `Show cast condition beside
the story` but has no passive consumer and always shows returned cast inside
the combined Conditions tool.

In the Widget model, explicit placement supersedes that legacy visibility
toggle. Migration uses the setting only to decide whether the starter Scene
layout initially includes Cast Condition. Once a user adds, removes, or moves
the Widget, Panel layout is authoritative and a placed Widget is never hidden
by the old preference.

## Anatomy and behavior

1. **Module bar** — `Cast Condition`, count of tracked bodies, and Widget
   actions.
2. **Filter/sort row** — compact `All`, `Needs attention`, and current story
   order/name sort when enough cast exists. Filters are presentation only.
3. **Participant rows** — identity, concise condition summary, and the most
   relevant engine-labelled vital state; disclosure opens all available vitals.
4. **Owner action** — `Open Cast` reaches membership/position management;
   `Open Story Style` reaches condition configuration.

`Needs attention` is derived only from engine-provided bands/labels, never a
new medical threshold. Empty cast, hidden/unavailable data, and all-clear are
distinct.

## Geometry, states, and responsive contract

| Contract | Value |
|---|---|
| Minimum useful size | 220 x 180 px |
| Preferred size | 286 x 320 px |
| Supported zones | left/right toolbar; medium grid; focused support region |
| Unsupported zones | composer strip; reading-stage center |
| Stack / Float / Collapse | Stack yes; bounded float yes; collapse yes with attention count retained |

States cover no story, loading, tracking off, no tracked cast, no available
condition data, ready/all-clear, ready/attention, offline/error with labelled
last-known rows, and participant removal during refresh. The list preserves
stable identity and focus; it does not reorder on every numeric tick unless the
user explicitly selected attention sort.

Narrow rows show name + summary and disclose details. Phone staging uses one
list scroll owner; participant disclosures remain keyboard-operable and 44 px
on touch. Meaningful summary changes announce at most once per participant, not
every meter update. Reduced-motion, solid, and high-contrast modes preserve
selection, attention text, focus, and meter semantics.

## Persistence, miniature, and acceptance

Panel persistence may retain collapsed state, filter, sort, and row-density
preference. It never stores cast ids, conditions, vitals, story/frame ids, or
expanded participant health records.

The Catalog miniature shows three representative participant rows with calm
summary/meter shapes. It uses no real names or alarming red-card treatment.

Acceptance requires the full state set, shared one-fetch behavior with Player
Condition, stable participant identity, explicit-placement migration from
`show_npcs`, correct non-player filtering, owner navigation, narrow/phone,
keyboard/touch, reduced-motion, solid, and high-contrast proof.

---

# Widget design: Room Ambience

**Design state:** First draft, ready for mockup translation

**Type:** `story.room-ambience`

**Category:** Story

**Context:** Visible turn and its room/acoustic signature

**Presentation role:** Instrument

**Multiplicity:** Single per Panel; playback remains one device-level atmosphere
runtime regardless of instance count

## User purpose

Hear and control the soundscape for the room currently being read, understand
whether it is cached, silent, pending, or unavailable, and deliberately tune or
pin the resolved mix without opening provider credentials.

## Capability and ownership

The ambience engine derives an occupant-free acoustic signature from room,
time, weather, and damage; resolves local-library or Freesound sources; caches
silence or up to three layers; and stores per-room full-mix pins. The atmosphere
runtime owns browser audio nodes, unlock, page-visibility pause, crossfade,
seamless loop overlap, master/layer gain, and current visible-turn binding.

Settings owns global enablement, source, credentials, licences, local library,
and generation defaults. Story sound Settings owns completion chime. Room
Ambience does not repeat those controls merely because the current replacement
tool co-locates them.

The design restores Main's automatic cached playback, visible-turn chronology,
seamless/crossfaded room changes, source search/audition, full-mix pins, and
per-layer control. It retains the replacement runtime's owner guards, audio
survival across unmount, page-hidden pause, authenticated immutable media, and
explicit pending-status policy.

The known current regression is prohibited: `payload.enabled === false` always
silences and releases current ambience even when audio is unlocked and cached
layers are ready.

## Anatomy

1. **Instrument bar** — `Room Ambience`, room label, Playing/Silent/Pending
   state, and Widget actions.
2. **Primary transport** — labelled Unlock when required, Mute/Unmute, and
   master volume. Mute never masquerades as global disable.
3. **Mix summary** — up to three resolved layer names/source hints, current
   full-mix pin state, and safe licence/source attribution where required.
4. **Layer controls** — disclosure with per-layer gain, audition/mute, and
   reroll-one-layer where the server supports it.
5. **Mix actions** — `Pin this mix`/`Clear room pin`, `Reroll mix`, and `Check
   status` while pending.
6. **Sound browser** — a staged subview for local/search results, audition, and
   selecting the server-supported pin/mix operation. It is not a credentials
   editor.
7. **Owner action** — `Open Ambience Settings` for source/global setup.

Weather-triggered one-shots are scheduled by the atmosphere runtime from
authoritative weather timing. A manual audition may preview a sound, but the
Widget does not invent lightning or thunder events.

## Playback and async behavior

- A cached ready mix for the visible turn crossfades in after audio is unlocked
  and global ambience is enabled.
- A visible-turn change checks cache immediately, retains the prior mix only
  within the same room where continuity is correct, and otherwise fades to the
  new cached/silent state without geometry changes.
- An uncached signature commissions only after visible-turn dwell and queue
  admission. Pending state offers `Check status`; no private polling loop.
- A truthful server-task bridge may update the runtime and Background Work when
  available. Until then the pending task stays represented by this Widget.
- MP3/other compressed loops overlap seams and crossfade layers; leaving the
  page pauses output, returning resumes only if context is still current.
- Reroll mix/layer preserves prior audible playback until a replacement is
  ready or an authoritative silence result settles.
- Pin writes the complete resolved mix, not only its first layer. A pin result
  refreshes server truth before the control changes.
- Search/audition never auto-plays without the initiating gesture and never
  stores licence acceptance or credentials in Panel state.
- Removing or unmounting the Widget does not stop the application atmosphere;
  Mute/Disable are explicit operations. Removing the Scene Backdrop likewise
  does not affect audio.

## Geometry, states, and responsive contract

| Contract | Value |
|---|---|
| Minimum useful size | 220 x 132 px |
| Preferred size | 286 x 280 px |
| Supported zones | left/right toolbar; compact/medium grid; story support strip |
| Unsupported zones | composer action cell; reading-stage prose layer |
| Stack / Float / Collapse | Stack yes; bounded float yes; collapse yes with Mute and state retained |

States cover no story/turn, audio locked, globally disabled, unconfigured,
loading, cached ready, playing, muted, silent-with-reason, absent/not requested,
dwelling before request, pending, status-checking, rerolling while prior mix
plays, pinned, library loading/empty/error, source/licence unavailable,
offline/error, and visible-turn superseded.

Narrow mode retains state, Mute, and master volume; mix/layers move behind one
disclosure. Phone staging gives the sound browser a full-height subview. Every
gain control has a layer-qualified name and numeric value; state announcements
do not repeat loop progress. Touch targets meet 44 px. Reduced motion removes
visual crossfade while audio crossfade may remain; a reduced-sensory setting may
disable automatic playback separately. Solid/high-contrast modes preserve
transport, state, pins, and focus without glass/color dependence.

## Persistence, miniature, current mockup, and acceptance

Device preferences may retain unlock capability as browser policy permits,
mute, master/layer gain, and reduced-sensory playback. Server ambience settings
and room pins retain their established owners. Panel persistence retains only
collapse/density/browser-disclosure state—never audio buffers, media URLs,
search results, pins, licences, credentials, visible turn, or pending jobs.

The Catalog miniature shows a restrained waveform/mix, three layer marks,
Playing, Mute, and a pinned-mix indicator. It is silent and inert.

`story.room-ambience` already exists in the nineteen-definition mockup and has a
placed right-toolbar instance. Refine that definition/instance rather than
adding another. Preserve its compact atmospheric identity while adding staged
mix/library states.

Acceptance requires every named state; enabled=false silence; visible-turn
chronology; same-owner new-turn refresh; dwell-before-spend; no polling;
seamless loops/crossfades; full-mix pin; per-layer reroll/gain; search/audition;
unmount survival; page visibility; narrow/phone; keyboard/touch;
reduced-motion/sensory; solid/high-contrast; and zero Transcript/Composer
geometry movement.

---

# Widget design: Scene Backdrop

**Design state:** First draft, ready for mockup translation

**Type:** `story.scene-backdrop`

**Category:** Story

**Context:** Visible turn and its room/visual signature

**Presentation role:** Stage-native

**Multiplicity:** Single per Panel; one instance owns the Panel's story backdrop
layer while generation/cache remain application services

## User purpose

See the room and atmosphere behind the story currently being read, understand
its generation state, and deliberately generate or reroll the image without
turning scene art into a content card or moving the literary layout.

## Capability and ownership

The backdrop engine derives an occupant-free image request from visible room
state, light, time, scoped weather, visual style, branch lineage, and optional
room-anchor continuity. Server/cache owns signature deduplication, queued
generation, authenticated private PNGs, and immutable content revision.

Scene Backdrop is the Panel's actual atmospheric background layer, not a small
controller that leaves an unowned image behind when removed. Its quiet controls
appear on focus/edit or from the Widget action surface. Settings owns model,
provider, size, global enablement, and continuity policy.

The design restores Main's visible-turn observer, dwell-before-commission,
same-room continuity, decoded dual-layer crossfade, luminance-aware scrim, and
release of faded GPU textures. It retains the replacement's explicit disabled,
unconfigured, absent, pending, ready, and error states plus force-reroll.

## Anatomy and behavior

1. **Stage image layers** — current and incoming decoded images behind the
   stable scrim and literary content.
2. **Atmosphere treatment** — luminance-informed scrim plus weather/light layer
   from authoritative turn context; never hard-coded generic rain over every
   room.
3. **Quiet status edge** — room label and Disabled/Generating/Ready/Error shown
   only when state needs attention or the Widget has focus.
4. **Control cluster** — `Generate`, `Reroll image`, `Check status`, and `Open
   Backdrop Settings` according to state.
5. **Widget edit affordance** — stage-layer selection/move/remove action that
   never competes with Transcript selection or turn actions.

Cached media applies immediately for the visible turn. Absent media waits for
visible-turn dwell, then enqueues once per signature. Pending state does not
poll privately. A newly committed turn under the same story/frame owner
re-evaluates visible context and may change the image.

Decode completes before crossfade. If a new image fails to decode, the prior
same-room image may remain visibly labelled `Previous backdrop`; a different
room falls back to the atmospheric base rather than displaying the wrong room.
Reroll preserves the prior correct image until the replacement settles. Faded
images release object/media resources.

Removing Scene Backdrop leaves the stage's base color, ambient light, weather
policy, Transcript, and Composer intact; it removes the generated visual layer
for that Panel. Another Panel may include its own backdrop projection over the
same cached visible-turn media.

## Geometry, states, and responsive contract

| Contract | Value |
|---|---|
| Minimum useful size | The full compatible story-stage backdrop zone |
| Preferred size | Entire story-stage canvas behind stable toolbars and literary measure |
| Supported zones | story-stage backdrop layer; focused atmospheric canvas |
| Unsupported zones | toolbars; ordinary grid cells; composer strip; floating layer |
| Stack / Float / Collapse | Not stackable, floatable, or collapsible; removable/recoverable through the Widget Shelf |

States cover no story/turn, globally disabled, unconfigured, loading cache,
absent/dwell, pending, checking, cached ready, decoding, crossfading, stable,
rerolling with prior image, silent/base fallback, offline/error, stale result
rejected, and removed. Control/status treatment must be demonstrable without
moving prose.

Tablet/phone uses the same backdrop crop policy and safe focal treatment; it
does not convert the image into a hero card above prose. Short landscape
reduces visual contrast/detail before reducing readable story measure. Alt text
does not narrate generated decoration into the reading order; generation/state
controls remain named and keyboard/touch operable. Reduced motion swaps after
decode without crossfade. Reduced effects/data may use the atmospheric base or
cached-only mode. Solid/high-contrast keeps controls legible and may suppress
the image while preserving layout and state.

## Persistence, miniature, current mockup, and acceptance

Panel persistence stores presence in the backdrop zone and safe crop/treatment
preference only. It never stores media bytes/URLs, prompts, signatures,
provider/model identity, pending jobs, visible turn, or generation results.

The Catalog miniature shows a room-toned backdrop, stable center reading strip,
and a quiet Ready edge treatment. It uses representative art only and has no
working Generate control.

The active mockup visually contains a backdrop but does not register it as a
Widget. Add `story.scene-backdrop`, assign the existing stage layer to it, and
preserve the exact calibrated shell/reading geometry. Removing and restoring it
through the Shelf must prove that atmosphere is now Widget-owned rather than a
permanent anonymous CSS background.

Acceptance requires every named state; visible-turn chronology; same-owner
turn refresh; dwell/dedupe/no-polling; decode-before-swap; same-room retention;
luminance scrim; resource release; force-reroll; removed/recovered behavior;
tablet/phone/short-height; keyboard/touch; reduced-motion/effects/data;
solid/high-contrast; and zero literary reflow.

---

# Widget design: Background Work

**Design state:** First draft, ready for mockup translation

**Type:** `runtime.background-work`

**Category:** System

**Context:** Global runtime

**Presentation role:** Module

**Multiplicity:** Single per Panel; every instance projects the same task
service and registered providers

## User purpose

See which accepted operations are still running after their initiating surface
is left, understand phase and elapsed time, cancel only genuinely cancellable
work, and inspect recent completion/failure without opening raw telemetry.

## Capability and ownership

Main supplied a global activity count, label, spinner, and live elapsed time for
long work while the user continued elsewhere. Current `createTaskService`
provides the stronger record: owner, request/correlation identity, lifecycle,
phase, optional real progress, elapsed time, summary/error, cancellation
callback, and bounded terminal retention. It currently has no visible consumer.

Background Work projects only tasks truthfully registered with that service or
a host-approved `task-provider`. It does not infer work from spinners, inspect
network requests, or fabricate a bridge to server `core.jobs`/out-of-band media
queues. Server-owned jobs become visible only after a generic authenticated
projection delivers stable identity and lifecycle. Until then, their owning
Widgets retain Pending/Check status.

Turn generation may appear here as one global task row so navigation cannot
orphan it. Turn Progress remains its friendly detailed local Widget. Notices
remain the durable communication/retry owner for failures; Background Work is
the activity/history projection.

## Anatomy and behavior

1. **Module bar** — `Background Work`, active count, and Widget actions.
2. **Active work list** — task name, owner/destination context, current phase,
   elapsed time, and real progress only when the task supplies a determinate
   value.
3. **Task action** — `Cancel` only when the registered task supplies a current
   cancel capability; disabled/fake cancellation is never shown.
4. **Recent results** — bounded completed, failed, and cancelled rows with
   summary/time. Failure links to its owning surface or notice; it does not dump
   technical stack data.
5. **Filter** — `Active` and `Recent` when terminal history exists. Empty state
   replaces both rather than showing disabled tabs.

Task records keep stable row identity and order by accepted/start time. Elapsed
time is computed from the task clock and survives Widget remount without being
persisted. Optional percentage is shown only for a task that declares a real
bounded progress contract; indeterminate work receives no fake fill.

Cancel captures task id/revision, changes to `Cancelling…`, and waits for
authoritative task settlement. Removing the Widget never cancels work. A task
provider failure is isolated and represented as provider unavailable without
breaking host tasks.

The persistent top shelf may show the active count and focus/open Background
Work. It is an entry point, not a second task list.

## Geometry, states, and responsive contract

| Contract | Value |
|---|---|
| Minimum useful size | 220 x 140 px |
| Preferred size | 320 x 280 px |
| Supported zones | left/right toolbar; compact/medium grid; global support region; bounded float |
| Unsupported zones | composer strip; reading-stage center |
| Stack / Float / Collapse | Stack yes; bounded float yes; collapse yes with active count and highest-priority phase retained |

States cover no work, one/many running, mixed determinate/indeterminate,
cancellable/noncancellable, cancelling, completed, failed, cancelled, provider
loading/unavailable/error, task removed by retention, offline, and task owner
destination unavailable. A removed terminal row is ordinary retention, not a
failure.

Narrow rows wrap task name before phase; elapsed and available Cancel remain.
Phone staging uses one list scroll owner. Active count and lifecycle changes
announce once; elapsed ticks and indeterminate motion are silent. Touch actions
meet 44 px. Reduced motion freezes spinners; solid/high-contrast preserves
state text, progress, focus, and cancellation affordance.

## Persistence, miniature, and acceptance

Panel persistence may retain collapsed state, Active/Recent view, and density.
It never stores task rows, elapsed/progress, request/correlation ids,
cancellation functions, errors, provider payloads, story ids, or history.
Client task retention remains page-local and bounded by the service.

The Catalog miniature shows two representative tasks—one indeterminate phase
and one real bounded progress row—plus an active count. It has no timer,
working Cancel, real operation name, or fake server job.

Background Work is absent from the active nineteen-definition registry. Add it
as a global Module and connect the top-shelf activity count to focus/place it.
It is Catalog-first rather than permanently occupying the default Scene.

Acceptance requires every named lifecycle/provider state; truthful progress;
stable elapsed across remount; cancel capability/settlement; unmount survival;
host/provider isolation; top-shelf focus; no inferred server jobs; no duplicate
Turn Progress owner; narrow/phone; keyboard/touch; reduced-motion;
solid/high-contrast; and zero task data in Panel persistence.

---

# Shared boundary: Library and authoring

Library is the one archive, association, lifecycle, and long-form authoring
owner. Placeable filtered Widgets do not create parallel collections.

## One projection service

Library, Stories, Characters (Library), Personas (Library), and Lore (Library)
consume one bounded `/api/library` projection. The runtime owns route/query
requests, captured `canonicalHash`, accepted mutation receipts, refresh, and
stale-result rejection. Story scope is an association filter, not an ownership
folder.

Each filtered Widget may retain independent harmless configuration—type is
fixed by its definition while story scope, search, sort, visibility, and density
may differ. All instances still read one normalized server projection and
delegate writes to one Library runtime.

The full Library Workspace owns:

- category, scope, search, sort, Filters, visibility, selection, and scroll;
- focused record detail and lifecycle actions;
- association to stories;
- create/import/export/archive/restore/delete boundaries;
- entry into focused authoring;
- `Add to Workbench` / `Locate Widget` for eligible filtered views.

Filtered placeable views are compact operational projections. They may select,
filter, associate, activate/dormant, archive/restore with bounded exact undo,
and open their canonical detail. Permanent delete, import, complex creation,
and long-form authoring focus the full Library rather than growing a second
modal workflow inside a toolbar Widget.

## Shared ledger and authoring contracts

Ledger rows use compact names, restrained metadata, one selected treatment, and
a trailing 44 px More target that does not select the row. They are never
ornamental cards, statistic tiles, or fabricated indexes. Loading/refreshing
preserves confirmed rows; empty and no-results name the active scope; error
preserves query/filter state and offers owner-qualified Retry.

Substantial editors replace the owning Library body or occupy a focused
Workspace Widget. They share:

- one qualified document owner and one recoverable local draft;
- content-derived revision/expected-revision conflict where the server supports
  it, with explicit prerequisite where it does not;
- one document scroll owner, compact semantic sections, and a persistent
  Back/save-state/action bar;
- `Saved to Library` versus `Draft saved on this device` language;
- lossless Additional fields/Advanced preservation for unknown and
  extension-owned data;
- named Discard confirmation that restores the last Library version;
- exact parent query, filter, sort, selection, scroll, and focus restoration;
- compact/phone staged detail with explicit Back, never a second mobile archive.

Panel persistence may store only harmless projection configuration and bounded
Library presentation preferences. It never stores authored sheets, associations,
archive receipts, generation output, invite secrets, story/frame ids, or editor
drafts. Draft and undo services retain their existing qualified/bounded owners.

---

# Widget design: Library

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `library.workspace` |
| Context | Global with optional active-story association filter |
| Role | Workspace/editor |
| Multiplicity | Repeatable by configuration; one runtime/data projection |
| Minimum / preferred | 520 x 360 px / dominant Panel workspace |
| Placement | focused dominant; wide grid; not toolbar or float |

## Purpose, anatomy, and behavior

Browse and manage Stories, Characters, Personas, and Lore from the one
canonical archive without entering Scene merely by selecting a Story.

The Workspace contains one compact toolbar (category, persistent search, sort,
Filters, contextual create/import), active-filter chips, one recognition-rich
ledger, and one focused detail state. Wide layouts may reveal detail beside the
ledger only when the composition retains one primary navigation method and one
scroll owner; compact layouts stage ledger then detail with Back.

Selecting a Story opens Library detail. Only `Open in Scene` changes the active
story and returns to Scene. Create/import/delete/long authoring stay here.
Archive changes discovery only; association remains. Exact twelve-second undo
is shown only for sound inverse mutations. Delete has explicit confirmation and
no optimistic undo.

States cover initial loading, background refreshing with retained rows,
all-empty, filtered no-results, offline/error, unavailable selected record,
mutation saving/failure, archive undo, focused detail, and focused authoring.
Route changes reject stale results and restore prior scroll/focus on Back.

The Catalog miniature shows the compact toolbar, six ledger rows across two
record kinds, one selected row, and focused-detail edge—no dashboard cards or
real data. Acceptance requires every state, route/selection ownership,
selection-not-navigation, exact Back restoration, undo expiry, compact staging,
keyboard row/More semantics, touch, reduced motion, solid/high contrast, and
zero authored data in Panel persistence.

## Current mockup fit

`library.workspace` already exists in the nineteen-definition registry and the
shipped Library Panel. Refine the existing definition/miniature; do not add a
parallel Library destination or record grid.

---

# Widget design: Stories

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `library.stories` |
| Context | Global Library projection |
| Role | Module, expanding to focused Library detail |
| Multiplicity | Repeatable by configuration |
| Minimum / preferred | 240 x 220 px / 360 x 420 px |
| Placement | toolbar; medium grid; compatible Library stack; bounded float |

## Purpose and contract

Keep a compact searchable Story ledger available on any Panel and reach the
real story detail/lifecycle owner quickly.

Rows show name, premise/status excerpt, primary Persona, turn/updated metadata
already present in the public projection, archive state, and selection. Actions
are `Open detail in Library`, explicit `Open in Scene`, New Story, export, and
archive/restore with sound bounded undo. Editing name/premise/primary Persona,
branching, import, and delete focus the full Library authoring/detail owner.

Selecting a row never opens Scene. No row invents cover art or counts absent
from the bounded projection. Search/sort/archive visibility are instance
configuration over shared data.

States follow the shared ledger plus no Stories, no search results, archived
only, active-story unavailable, mutation/undo, and story removed during
refresh. Collapsed summary retains result count and current active-story match,
not a selected story id.

Panel persistence may retain filter/sort/search preference only; selection,
story records, and undo stay out. The miniature shows three restrained Story
rows and an explicit Scene arrow on one selected detail, not a card carousel.
Acceptance proves selection-versus-Open-in-Scene, lifecycle delegation, shared
refresh, bounded undo, empty/error, responsive rows, keyboard More, and no
second story picker.

---

# Widget design: Characters (Library)

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `library.characters` |
| Context | Global with optional story-association filter |
| Role | Module |
| Multiplicity | Repeatable by configuration |
| Minimum / preferred | 240 x 240 px / 360 x 440 px |
| Placement | toolbar; medium grid; Library stack; bounded float |

## Purpose and contract

Browse reusable Characters and their real Story associations, then add, wake,
rest, locate, or open the selected Character without copying its sheet.

The runtime owner is the shared bounded Library projection and association
mutation service; the Widget owns only its filter, density, and selection.

Rows may show a real local portrait at densities that support it, name,
active/dormant state, and bounded association metadata. Actions are `Open
Character Card`, `Add to Story`, activate/dormant within an association, `Open
story-specific card`, duplicate/export, and archive/restore where safe. Create,
import, permanent lifecycle, and long editing focus Library.

Adding captures Character + target Story; accepted writes refresh the shared
projection. Remove means dormant, not erased. Association and archive inverse
actions receive the exact bounded undo only when valid.

States add no Characters, no association matches, target Story unavailable,
already associated, association guarded by running story, dormant, archived,
and mutation conflict to the shared ledger states. The miniature shows four
compact people rows with one real-portrait-shaped fallback and association
marks, not oversized profile cards.

Persistence stores filter/density only. Acceptance proves reusable identity,
multi-story associations, dormant semantics, shared data/no sheet fetch,
selection/open-card focus, safe undo, and all responsive/accessibility modes.

---

# Widget design: Characters (Story)

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `story.characters` |
| Context | Active story/frame |
| Role | Module |
| Multiplicity | Single per Panel |
| Minimum / preferred | 220 x 240 px / 286 x 420 px |
| Placement | left/right toolbar; medium grid; story roster stack; bounded float |

## Purpose and contract

Browse the reusable Character sources associated with the active Story and
open the correct reusable or Story-specific document without becoming a second
live Cast controller.

The Widget is the Library association projection filtered to the active Story:
Character name/source, association, reusable/story override availability, and
archive/source status. It may add a reusable Character to the Story and open
either Character Card or Story Character Card through the shared Library
runtime. Live active/dormant state, position, dialogue color, and participant
runtime actions belong to Cast.

Cast Condition owns physiology; Character Relationships, Memory Browser, and
private history own their selected-person records. This strict split preserves
PWC-016 and prevents two toolbar rosters from showing different live state.

States cover no story, loading, no associated Characters, source missing,
archived reusable source, Story override available, association guard,
mutation saving/error, and association removed. Panel persistence stores
sort/filter/collapse only. The miniature uses four compact associated-source
rows and override marks, with no position or condition data.

`story.characters` already exists and is placed in the active mockup. Refine
the definition and add Cast separately; do not leave Cast controls inside this
association Widget. Acceptance proves story invalidation, association versus
override, owner launch, strict Cast non-overlap, current mockup geometry, and
all compact/accessibility states.

---

# Widget design: Personas (Library)

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `library.personas` |
| Context | Global with optional story-association filter |
| Role | Module |
| Multiplicity | Repeatable by configuration |
| Minimum / preferred | 240 x 220 px / 360 x 420 px |
| Placement | toolbar; medium grid; Library stack; bounded float |

## Purpose and contract

Browse reusable Personas and distinguish primary from additional Story
associations without treating a player identity as a Character.

Rows show name, reusable identity, bounded associations, and primary/additional
role. Actions are `Open Persona Card`, add as additional Persona, activate or
rest an additional Persona, duplicate/export, and archive/restore. Changing a
Story's primary Persona focuses Story authoring. A primary Persona cannot be
detached through this projection.

States include empty/no-results, primary-only target Story, already additional,
guarded active Story, archived, source unavailable, and mutation/undo errors.
Panel persistence stores filters/density only. The miniature shows three
compact identities with explicit Primary/Additional text. Acceptance proves
role semantics, primary detach prohibition, associations, shared projection,
safe undo, owner launch, and responsive/accessibility behavior.

---

# Widget design: Personas (Story)

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `story.personas` |
| Context | Active story/frame |
| Role | Module |
| Multiplicity | Single per Panel |
| Minimum / preferred | 240 x 220 px / 320 x 380 px |
| Placement | toolbar; medium grid; story setup stack; bounded float |

## Purpose and contract

Show the active Story's primary player identity and additional Personas in one
coherent roster while delegating their distinct mutations correctly.

The first section shows the primary Persona and `Edit Story setup`/`Open
Persona Card`. The second lists additional Personas with attach/detach,
active/dormant, station/frame, and guarded guest-invite entry points through the
Multiplayer owner. Empty means `No additional players`; it never implies the
Story has no primary Persona.

Detach is confirmed and cannot target the primary Persona. Guest secrets are
one-time results presented by Multiplayer and never stored here. Changing the
primary Persona belongs to Story authoring; stationing belongs Who's Where/
Frames; this Widget may summarize but does not duplicate their editors.

States cover no story, loading, missing primary source, no additional players,
ready, invite pending/one-time handoff, detach confirmation, pipeline guard,
mutation/error, and participant removed. Persistence stores collapse/section
preference only. The miniature shows one Primary row and two Additional rows.
Acceptance proves the composite owners, distinct empty semantics, no secret
persistence, guarded detach, story invalidation, and responsive/accessibility.

---

# Widget design: Lore (Library)

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `library.lore` |
| Context | Global with optional story-association filter |
| Role | Module |
| Multiplicity | Repeatable by configuration |
| Minimum / preferred | 240 x 240 px / 380 x 440 px |
| Placement | toolbar; medium grid; Library stack; bounded float |

## Purpose and contract

Browse reusable Lorebooks, distinguish story-owned Lore, and manage real Story
associations without flattening lore hierarchy into cards.

Rows show book title, reusable/story-owned origin, bounded association count,
archive state, and selected-book summary. Actions are `Open Lore workspace`,
attach/detach reusable copy, archive/restore, and contextual `Prepare lived-in
location`. Create/import/export/permanent lifecycle and book/entry editing focus
the canonical Lore workspace.

Detach targets the Story copy and preserves its reusable origin. Story-owned
records are visible only in their Story scope and are not offered invalid
global association mutations. The current replacement's lack of create/edit
actions is a presentation gap; this design restores access through the one Lore
workspace rather than inline forms.

States cover no Lorebooks, no association matches, story-owned-only, archived,
attach/detach guarded, missing source, mutation/undo, and load/error. Panel
persistence stores filters/density only. The miniature uses a compact tree/book
mark and three ledger rows, not book-cover cards. Acceptance proves origin,
association detach semantics, owner launch, lived-location context, shared
projection, and all responsive/accessibility states.

---

# Widget design: Lorebooks (Story)

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `story.lorebooks` |
| Context | Active story/frame |
| Role | Workspace/editor |
| Multiplicity | Single per Panel |
| Minimum / preferred | 420 x 320 px / 760 x 560 px |
| Placement | focused dominant; wide grid; lore stack; bounded float above minimum |

## Purpose and contract

Understand and manage the active Story's complete Lore ownership/retrieval
surface: canon, attached, disabled, story-owned, reusable origin, hierarchy,
and reachability.

One compact book tree/ledger owns selection. The detail names ownership versus
retrieval, canon binding, enabled/disabled state, origin, parent/inheritance,
and entry/relation counts already available from the authoritative routes.
Actions attach/detach reusable Lore, enable/disable, make/clear canon, open
Details, Entries, Relationships, Generator, or Lived-in Location in the shared
Lore selection context.

The server returns owned books even when not currently retrieval-reachable;
the Widget must not hide them or equate disabled with detached. Main's full Lore
manager is capability evidence; its old panes and unsafe draft behavior are not
presentation/runtime authority. The missing replacement surface is restored
through current routes and the focused Lore family contracts below.

States cover no story, loading, no owned/attached books, canon only, attached,
disabled, orphaned-owned, missing origin, mutation guard, partial detail load,
offline/error, and selection removed. Compact/phone stages book list then detail
with Back and exact selection restoration. Panel persistence stores tree
expansion/density only—not Story, selection, books, retrieval state, or drafts.

The miniature shows a compact hierarchical book list with Canon/Attached/
Disabled labels and one selected detail. Acceptance proves ownership versus
reachability, full book recovery, shared Lore selection, canonical operations,
stale-owner guards, staged mobile, keyboard tree, and safe persistence.

---

# Widget design: New Story

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `library.new-story` |
| Context | Global workflow |
| Role | Workspace/editor |
| Multiplicity | Application singleton; another launch locates the active workflow |
| Minimum / preferred | 520 x 420 px / dominant Panel workspace |
| Placement | focused dominant only; not toolbar, stack, or float |

## Purpose and contract

Create one coherent Story through `Describe`, `Use my Library`, or `Start blank`
while preserving all setup work and making every generated/reusable attachment
explicit before creation.

The qualified owner is `new-story/current`. One step rail/compact progress
header stages route choice, Story premise/setup, Persona, Characters, Lore,
optional lived-in location, and Review. Generated reusable cards remain
previews until accepted/saved; Review names which durable records will be
created or attached.

Creation first establishes the Story, then attaches selected/generated
material and runs optional lived-location setup through released routes. If a
post-create step fails, the workflow deletes the incomplete Story. If cleanup
also fails, it preserves the draft and exposes the exact Story link rather than
hiding an orphan.

States cover first use, recovered draft, each route, empty material, missing AI
configuration, generation running/preview/failure, validation warning, Review,
creating, post-create cleanup, cleanup failed with Story link, success/open in
Scene, offline, and discard confirmation. Back never loses a completed step.

One document scroll owner, sticky Back/Continue/Review/Create actions, 44 px
touch targets, labelled progress, and compact full-width stages satisfy the
shared authoring/mobile contract. Panel persistence stores placement only;
draft/generation/recovery remains with `new-story/current`.

The miniature shows the three start routes, a short step trail, and Review—not
fake generated characters. New Story is absent from the nineteen-definition
registry and should be added as an application-singleton workflow. Acceptance
proves every state, recovered draft, preview-before-write, exact attachment,
cleanup/cleanup-failure, duplicate launch locate, responsive/accessibility, and
no Story data in Panel persistence.

---

# Widget design: Character Card

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `library.character-card` |
| Context | Selected reusable Character |
| Role | Workspace/editor |
| Multiplicity | Repeatable by selection channel; one shared draft per document owner |
| Minimum / preferred | 460 x 360 px / 780 x 620 px |
| Placement | focused dominant; wide grid; authoring stack; bounded float above minimum |

## Purpose and contract

Author the complete reusable Character document without losing unknown fields
or confusing reusable truth with one Story's live override.

The owner is `character:<id>` plus content revision. The shared authoring frame
provides Back/save state, semantic Basics, Appearance, History, Psychology and
applicable content sections, one document scroll, and More for Start a Story,
Additional fields, and Advanced. Unknown/extension fields remain literal and
lossless.

Save uses `expected_revision`; conflict preserves both the device draft and
new server version for deliberate reconciliation. Discard names the Character
and restores the last Library version. Before-unload protection follows dirty
owner state, not Widget mount count.

Appearance, psychology, and greeting generation are preview-only until the
user accepts into the draft and saves. Duplicate/export/archive remain Library
lifecycle operations exposed through the owner menu; they never silently save
the open draft.

States cover no selection, loading, ready/saved, dirty/device-saved, saving,
saved, conflict, generation running/preview/failure, invalid Additional fields,
permission/load error, source archived/missing, and discard confirmation. Two
instances editing the same Character bind one draft and show an `Editing in
another view` coordination state rather than fork.

Panel persistence stores section/density/scroll preference only; selected id,
sheet, revision, draft, generation output, and conflict versions stay out. The
miniature shows compact semantic sections and a Saved/Draft marker, no real
sheet. `library.character-card` already exists in the mockup; refine it.

Acceptance proves lossless unknown fields, revision conflict, draft recovery,
discard/before-unload, preview-before-save generation, shared draft across
instances, reusable/story boundary, Back restoration, phone/short landscape,
keyboard/touch, reduced motion, solid/high contrast.

---

# Widget design: Story Character Card

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `story.character-card` |
| Context | Selected Character in the active story |
| Role | Workspace/editor |
| Multiplicity | Repeatable by selection channel; one shared draft per story-qualified owner |
| Minimum / preferred | 460 x 360 px / 780 x 620 px |
| Placement | focused dominant; wide grid; authoring stack; bounded float above minimum |

## Purpose and contract

Edit the Story-specific effective Character sheet while preserving its reusable
source and every live runtime record that is not part of the document.

The owner is `story-character:<active story>:<character>`. It uses the shared
Character editor, labels itself `Story version`, and shows the reusable source
as a read-only origin link. Save targets the story-card route; rename/rekey and
cross-story targeting are unavailable.

The server preserves reusable sheet, live mood/stress, memories, relationships,
body state, and other runtime ledgers while synchronizing the qualified private
history. A running pipeline blocks save. Switching active story clears an
incompatible selection and never retargets the draft.

The current route has no optimistic revision token. Independently mounted
editing requires a server revision/conditional-write contract or a single
serialized edit lease before this Widget can be production-writable. Until
then it may render read-only detail but must not offer unsafe last-write-wins.

States add no active story, Character not attached, reusable source missing,
read-only pending revision support, pipeline blocked, source changed, and
participant detached to the shared editor states. Persistence stores harmless
section/density only. The miniature adds a clear `Story version` origin marker.

Acceptance proves story invalidation, reusable preservation, runtime-ledger
preservation, pipeline guard, safe revision prerequisite, private-history
coordination, shared draft, responsive/accessibility, and no story id/sheet in
Panel persistence.

---

# Widget design: Persona Card

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `library.persona-card` |
| Context | Selected reusable Persona |
| Role | Workspace/editor |
| Multiplicity | Repeatable by selection channel; one shared draft per owner |
| Minimum / preferred | 440 x 340 px / 760 x 580 px |
| Placement | focused dominant; wide grid; authoring stack; bounded float above minimum |

## Purpose and contract

Author a reusable player Persona through the same lossless document framework
without exposing Character-only psychology, greeting, or Quick Start tools.

Owner `persona:<id>` plus revision controls draft, save, conflict, discard,
Additional fields, Advanced, Back restoration, duplicate/export/archive, and
appearance-generation preview. Persona sections and help use player-identity
language and preserve all stored unknown fields.

States and responsive/accessibility follow Character Card, minus Character-only
generation/sections, plus primary/additional association context where useful.
No association mutation occurs inside the document editor.

Persistence stores section/density only. The miniature shows Persona-labelled
semantic sections and draft status, visually related to but distinguishable
from Character Card. Acceptance proves revision conflict, lossless preservation,
preview-before-save, correct section exclusion, shared draft, association
non-ownership, responsive/accessibility, and safe persistence.

---

# Widget design: Greetings and Quick Start

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `library.greetings-quick-start` |
| Context | Selected reusable Character plus available Personas |
| Role | Workspace/editor |
| Multiplicity | Single per Panel; shares the selected Character document owner |
| Minimum / preferred | 380 x 320 px / 620 x 520 px |
| Placement | focused/medium-wide grid; Character authoring stack; bounded float |

## Purpose and contract

Author the selected Character's opening messages and deliberately start a Story
from one greeting without creating a second Character draft.

The greeting editor reads/writes `opening.first_message` and greeting entries
inside `character:<id>`'s shared document draft. Generation is preview-only and
recoverable. The Quick Start subview holds only owner-keyed in-memory choices:
Persona, greeting, optional Lore/known state, language, and lived-location
setup.

Quick Start is unavailable until both a Persona and a non-empty greeting are
real. If the Character document is dirty, the primary boundary is `Save and
start Story`; save must succeed before `/characters/{id}/start`. A failed start
keeps the saved Character, choices, and a retryable error; it does not create a
second anonymous draft.

Public resident-card and private Character-history consequences of lived
location are stated beside those choices. The Widget never claims that
co-location or UI selection creates knowledge.

States cover no Character, Character loading/dirty/conflict, no Persona, no
greeting, ready, generating/preview/failure, saving before start, starting,
start failure, success/open Scene, and source missing. Panel persistence stores
only section/collapse; greeting text stays in Character draft and Quick Start
choices stay in their owner-keyed runtime map.

The miniature shows two greeting excerpts, one selected, a Persona line, and
`Save and start Story`; it never launches or generates. Acceptance proves shared
Character draft, preview recovery, capability-gated action, save-before-start,
failure preservation, lived-location disclosure, responsive/accessibility, and
no duplicate document owner.

---

# Shared boundary: Lore selection and authoring

Lore Entry Tree, Entry Editor, Lorebook Details, Relationships, Generator, and
Lived-in Location consume typed Library selection rather than storing book or
entry ids in Panel layout.

- Lorebook selection is `origin/scope + book id`; entry selection is qualified
  by that book.
- Changing active story clears an incompatible story-owned book but does not
  erase a reusable global selection merely because Scene changed.
- Tree/list reads, document reads, relationships, and generation jobs use
  separate request channels under the one selected Lore owner.
- Structural writes refresh book/tree truth and repair selection if the target
  moved or disappeared.
- Main's Lore UI has no safe persistent draft or optimistic revision. Before
  independently mounted Details/Entry/Relationship editors become writable,
  their routes require conditional revision or a serialized edit lease.
- Loading failure is never converted to an empty collection.
- Compact layouts stage tree/list, detail/editor, and generator review as
  explicit Back-owned states with exact filter/selection/focus restoration.

---

# Widget design: Lore Entry Tree

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `library.lore-entries` |
| Context | Selected Lorebook |
| Role | Module expanding to focused structural workspace |
| Multiplicity | Repeatable by selection channel |
| Minimum / preferred | 260 x 300 px / 420 x 560 px |
| Placement | toolbar; medium grid; Lore stack; bounded float |

## Purpose and contract

Navigate a selected Lorebook's hierarchy and perform explicit structural
operations without embedding the full entry editor in every row.

The runtime owner is the selected Lorebook tree projection plus its
revision-qualified structural mutation service.

The Module owns filter, expanded nodes, keyboard tree focus, and selected entry
projection. Actions create root/child/sibling, move/reorder, promote/demote, and
open Entry Editor. Pointer drag is optional; Move controls and keyboard commands
provide equivalent exact targets. Structural mutations capture book + entry +
parent/order revision and refresh authoritative tree.

States cover no book, loading first open, refreshing in place, no entries, no
filter matches, selected entry moved/removed, structure conflict, partial/missing
parent, offline/error, and story scope invalidated. Tree selection is transient;
Panel persistence may retain density and bounded expansion/filter preference,
not book/entry ids or tree data.

The Catalog miniature uses a five-node hierarchy with one selected child and
visible depth, not a generic file explorer. `library.lore-entries` already
exists in the nineteen-definition mockup; refine it as the Tree and add the
separate Editor definition below.

Acceptance proves ARIA tree/keyboard movement, pointer/keyboard operation
parity, stale structural conflict, error-versus-empty, selection repair,
compact staging, touch, reduced motion, solid/high contrast, and safe
persistence.

---

# Widget design: Lore Entry Editor

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `library.lore-entry-editor` |
| Context | Selected Lore entry |
| Role | Workspace/editor |
| Multiplicity | Repeatable by selection channel; one draft per entry owner |
| Minimum / preferred | 420 x 360 px / 720 x 620 px |
| Placement | focused dominant; wide grid; Lore stack; bounded float above minimum |

## Purpose and contract

Author the selected Lore entry's title/keys/category/content, canon lock,
importance, aliases, scope, knowledge rules, entry relations, and source notes
through one recoverable explicit-save document.

Owner is `lorebook + entry + revision`. Semantic sections keep prose/content
primary and stage retrieval/scope metadata under compact sections; Additional
fields preserve unknown data losslessly. Save is conditional/serialized as
required by the Lore prerequisite. Delete names the entry and relationship/
child consequence before confirmation.

Creating an entry may seed a server default, but the editor immediately owns a
recoverable draft and clearly distinguishes `Not yet saved` from saved source.
Closing/unmount never loses the qualified draft. Lore Generator remains the
plan/review/apply owner; this editor does not offer an immediate-write `Generate
entries` shortcut.

States cover no entry, loading, new unsaved, saved, dirty/device-saved, saving,
conflict, validation, source moved/deleted, read-only revision prerequisite,
delete confirmation/failure, permission/offline/error. Persistence stores
section/density only; no content, ids, draft, or revision.

The miniature shows title, retrieval keys, and a substantial content field with
Draft state. Acceptance proves lossless fields, conditional conflict, draft
recovery, delete consequence, tree selection coordination, no generator
shortcut, responsive/accessibility, and safe persistence.

---

# Widget design: Lorebook Details

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `library.lorebook-details` |
| Context | Selected Lorebook |
| Role | Workspace/editor |
| Multiplicity | Repeatable by selection channel; one draft per book owner |
| Minimum / preferred | 400 x 340 px / 680 x 560 px |
| Placement | focused/medium-wide grid; Lore stack; bounded float above minimum |

## Purpose and contract

Edit selected book metadata, scope, parent/inheritance, and ordering while
making canon and subtree consequences explicit.

The owner is selected Lorebook + revision. Actions save metadata, create
child/sibling, move/reorder, export, make/clear canon, and delete. Canon changes
and structure writes refresh the shared Lore tree; delete names subtree and
story-association consequences and requires confirmation.

Global reusable, story-owned, canon, attached, disabled, and inherited states
use literal owner labels. A book cannot be made to look globally reusable by
editing presentation scope. Unknown metadata is preserved under Additional.

States cover no book, loading, saved/dirty/saving/conflict, canon/attached/
disabled/inherited, invalid parent, structure conflict, subtree-delete warning,
source removed, read-only revision prerequisite, offline/error. Persistence
stores section/density only.

The miniature shows title, scope/origin, parent, Canon, and Draft markers.
Acceptance proves ownership labels, conditional save, structure/tree refresh,
canon authority, subtree warning, responsive/accessibility, and no book data in
Panel persistence.

---

# Widget design: Lore Relationships

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `library.lore-relationships` |
| Context | Selected Lorebook/entry |
| Role | Module/editor |
| Multiplicity | Repeatable by selection channel; one link draft per owner |
| Minimum / preferred | 300 x 280 px / 520 x 520 px |
| Placement | toolbar above minimum; medium grid; Lore stack; bounded float |

## Purpose and contract

Inspect and edit real Lore relationships without treating hierarchy,
associations, or textual mentions as links.

The list names direction, relation type, target, label, weight, bidirectional,
and retrieval-follow status. Selecting/new opens one editor for type, target,
label, notes, weight, bidirectional, and follow flags. Save is explicit and
conditional/serialized; Delete names the relationship and confirms.

An optional compact direction diagram may clarify one selected link but never
becomes a force graph or alternative navigation system. Empty (`No
relationships`) and fetch failure are always distinct—repairing Main's silent
`links=[]` failure collapse.

States cover no book/entry, loading, empty, ready, new/dirty/saving/conflict,
invalid/missing target, target scope unavailable, delete, source removed,
read-only revision prerequisite, offline/error. Persistence stores filter/
density only; no links, ids, notes, or drafts.

The miniature shows three directed rows and one Follow marker. Acceptance
proves direction semantics, explicit error, conditional save/delete, target
validation, tree/detail coordination, responsive/accessibility, and safe
persistence.

---

# Widget design: Lore Generator

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `library.lore-generator` |
| Context | Selected Lorebook |
| Role | Workspace/editor |
| Multiplicity | Single per selected generation owner; another launch locates the job |
| Minimum / preferred | 520 x 400 px / 860 x 660 px |
| Placement | focused dominant; wide grid; Lore generation stack; not toolbar/float |

## Purpose and contract

Plan, inspect, selectively approve, and atomically apply generated Lore
operations without allowing generation to write directly into the book.

The flow stages plan mode, depth/target/timeout/permissions, explicit Generate,
server job progress/status, and a review ledger of proposed books, links, and
entries. Each operation can be accepted/rejected before one explicit Apply.
Generation writes nothing to Lore; Apply alone mutates through the durable job.

The server generation-job id owns progress across Widget/Panel/server restart.
The Widget never persists it in Panel layout; it rediscovers restorable jobs
through the selected Lore owner. Pending work uses `Check status` or a truthful
Background Work task bridge, never an idle polling interval.

Discard cancels/retires an unapplied job after confirmation. Apply is guarded
against source revision changes and reports partial/unusable/refused operations
individually; it never claims success from a merely completed generation.

States cover no book, planning, validation, submitting, running, interrupted/
resumable, finished/restorable, partial plan, empty/unusable proposal, review
with accept/reject, source changed, applying, applied, partial/refused apply,
discarding/cancelled, expired/missing job, offline/error. One scroll owner and
staged phone plan/review satisfy the authoring contract.

The miniature shows Plan → Review → Apply, six proposal rows with mixed
acceptance, and no fake generation animation. Acceptance proves no-write-before-
Apply, durable job restoration, no polling, per-operation review, revision
guard, partial/refused truth, discard, duplicate-launch locate,
responsive/accessibility, and zero job/output in Panel persistence.

---

# Widget design: Lived-in Location Builder

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `library.lived-location-builder` |
| Context | Active Story plus selected New Story/Character/Lore/Story-tool host |
| Role | Workspace/editor |
| Multiplicity | Single per qualified host owner |
| Minimum / preferred | 420 x 340 px / 720 x 580 px |
| Placement | focused/medium-wide grid; compatible host stack; bounded float above minimum |

## Purpose and contract

Prepare an engine-owned lived location from an explicit brief, history horizon,
and Character route/guidance, then invoke the one released generation operation
through the currently viable host context.

The shared adapter normalizes only browser drafts. It never simulates
institutions, routes, residents, history, carriers, knowledge, or clocks. The
visible context banner names exactly what will happen:

- New Story: choices remain inside `new-story/current` and run after Story
  creation/attachment;
- Character Quick Start: choices share the selected Character start owner and
  save-before-start boundary;
- reusable Lore with current Story: attach that Lore, then generate at Present;
- active Story tool: use selected attached Lore and call Charter generation.

If only one route is executable, the Widget executes it directly after review
rather than showing a redundant mode chooser. If several host selections are
valid, the context selector names their consequences and never changes the
active Story implicitly.

Fields are place brief, past/history horizon, language where applicable, and
per-Character route/guidance plus known/private disclosure. Review names the
place, Story, Lore attachment, resident-card exposure, private-history delivery,
and additive generation. Existing institutions are never replaced or deleted.

States cover no active Story where execution requires one, no compatible host
selection, reusable Lore at non-Present frame, loading source, draft/recovered
host draft, review, attaching Lore, generating, partial host failure, cleanup
path inherited from New Story, success with created institution summary,
pipeline guard, stale owner, offline/error. Draft persistence always belongs to
the host; Panel persistence stores only collapse/density.

The miniature shows a named context, brief, horizon, two Character routes, and
Review—not invented residents or a simulated map. Acceptance proves all four
host modes, direct single viable action, captured owner, attach-then-generate,
New Story cleanup inheritance, additive-only result, public/private disclosure,
no browser simulation, responsive/accessibility, and safe persistence.

---

# Shared boundary: Story-System Widgets

Story-System Widgets follow the active Story and, where declared, its active
frame or selected participant/institution. They never persist or pin a Story
id. `story-tools-runtime.js` remains the model for captured
`story + frame + tool + request` ownership, cancellation, and stale-result
rejection.

The current ten Story Tools bundle several inventory identities into shared
forms. Splitting their presentation does not authorize competing server
documents:

- Dialogue and Agency and Off-screen Life share typed slices of
  `dialogue_config` through one merge/save service.
- Background Life owns `background_config` plus only its promotion-threshold
  slice of `dialogue_config`.
- Living World owns one `living_world` service used by both Scene and Settings
  projections.
- Genre and Style coordinates four real owners—style guide, Story language,
  survival/condition policy, and player authority—with separate save receipts
  instead of pretending four sequential writes are atomic.
- Player/Cast Condition, Cast, Attire, World State, private histories, and
  selected-mind Widgets remain separate projections even where raw World data
  could technically overwrite them.

Every accepted write refreshes authoritative normalized data. A Widget never
changes its Saved state because the first of several writes happened to
succeed. Engine-authored names, warnings, institution data, beliefs, memories,
and world content remain untranslated data.

---

# Widget design: Cast

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `systems.cast` |
| Context | Active story; positions active-frame qualified |
| Role | Module |
| Multiplicity | Single per Panel |
| Minimum / preferred | 240 x 280 px / 320 x 480 px |
| Placement | toolbar; medium grid; world/cast stack; bounded float |

## Purpose and contract

Operate the active Story's live participant roster: attach a reusable
Character, set active/dormant state, position a participant in a current-frame
room or off screen, choose pinned/automatic dialogue color, and open the
Story Character Card.

Story and positions load once under the captured owner. Each immediate mutation
gets a row-level busy state and disables only conflicting controls until server
refresh; double submits are refused. Attach may seed initial attire and queue an
arrival; dormancy queues departure; manual position is silent/non-narrated;
dialogue color can repaint Transcript. Consequence copy appears at the action,
not in a generic warning wall.

Characters (Story) owns reusable association/source discovery. Cast Condition
owns physiology; Attire owns clothing; Who's Where owns Persona frame station.

States cover no story, loading, empty, ready, dormant, off-screen/no position,
room unavailable, source missing, row saving, pipeline-guard refusal,
participant changed/removed, offline/error. Persistence stores sort/collapse
only. The miniature shows four live rows with active/location/color marks.
Cast is absent from the nineteen registry and must be added separately from
`story.characters`.

Acceptance proves attach/dormant consequences, frame-qualified position,
automatic color, row busy/error restoration, owner launches, strict association/
condition/attire boundaries, responsive/accessibility, and safe persistence.

---

# Widget design: Background Presences

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `systems.background-presences` |
| Context | Active story |
| Role | Module with staged promotion review |
| Multiplicity | Single per Panel |
| Minimum / preferred | 280 x 260 px / 420 x 520 px |
| Placement | toolbar above minimum; medium grid; cast stack; bounded float |

## Purpose and contract

Inspect recurring unsheeted presences and deliberately promote an eligible one
into a reusable, active Story Character after reviewing exactly what will be
created.

Rows show engine identity, first/last turn, dialogue/mention evidence, and
promotable/not-yet status. `Prepare promotion` starts an owner-qualified model
task and produces a recoverable review draft: editable Character sheet plus
per-line starter memories, collision/alias warnings, target membership, initial
position/attire/recognition, and irreversible consequence.

`Confirm promotion` is the only write. It mints the reusable Character and Story
membership/runtime state, then removes all presence aliases from future
background identity; past turns remain unchanged. Double submit is impossible.
Cancel retains or discards the draft explicitly. Background Life/global Content
owns automatic promotion policy.

States cover no story, loading, no presences, none promotable, ready, drafting,
draft failure/cancel, review/dirty, identity collision, confirming, confirmed
with Character link, partial/rejected confirmation, stale presence, offline/
error. Draft belongs `story + presence + evidence revision`; Panel stores only
density/collapse.

The miniature shows three presence evidence rows and one `Review promotion`
state, never a fake generated sheet. Acceptance proves model-task handoff,
recoverable review, collision warning, forward-only confirmation, alias cleanup,
past-turn preservation, automatic-policy boundary, responsive/accessibility,
and no draft in Panel data.

---

# Widget design: World State

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `systems.world-state` |
| Context | Active story/frame |
| Role | Workspace/editor |
| Multiplicity | Single per Panel |
| Minimum / preferred | 360 x 300 px / 700 x 560 px |
| Placement | focused/medium-wide grid; world stack; bounded float above minimum |

## Purpose and contract

Inspect and explicitly author bounded structured current-frame world records
without granting a normal Widget an all-frame raw replacement operation.

The existing `/world` route returns and replaces every raw world KV row across
frames. Its delete-and-reinsert PUT can overwrite Cast, Attire, conditions, and
other specialized owners and has no confirmation. That operation moves to Raw
Story Data/maintenance; it is not the normal World State save path.

World State shows current location and structured Rooms, Entities, Placements,
Standing Conditions, and other frame records from a new bounded projection.
Each supported structured editor uses typed fields and a current-frame
conditional save. Until that bounded route exists, the Widget is read-only and
offers `Open Raw Story Data` with the all-frame consequence named.

States cover no story, loading, truly empty editable frame, read-only pending
bounded route, ready, dirty/saving/conflict, running-pipeline guard, invalid
room/entity reference, normalized reload, offline/error. Empty never blocks
creation of the first structured record. Panel stores section/density only.

`systems.world-state` already exists and is placed in the mockup. Replace its
metric-only/raw-JSON identity with structured summary/sections while preserving
the compact placed preview. The Catalog miniature shows a synthetic room/entity
summary and a `Structured view` marker, never raw state. Acceptance proves
current-frame scope, no raw
whole-world write, typed validation, conditional conflict, first-record flow,
specialized-owner protection, and responsive/accessibility.

---

# Widget design: Attire

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `systems.attire` |
| Context | Active story/frame |
| Role | Workspace/editor |
| Multiplicity | Single per Panel |
| Minimum / preferred | 380 x 320 px / 720 x 600 px |
| Placement | focused/medium-wide grid; character-state stack; bounded float |

## Purpose and contract

Inspect and silently author the complete current-frame attire ledger through
wearer, garment, body-region layering, visible state, condition, attachment,
coverage, and `beneath` relationships—without forcing users into raw JSON.

One qualified draft loads wearer summaries and opens a structured layer editor
for head, torso, arms, hands, waist, groin, legs, and feet. Garment operations
add/remove/reorder layers and edit worn/loosened/open/removed state, condition,
description, attachment, and coverage. Save submits one ledger, then reloads
the server-normalized `wearing/state/regions` representation before claiming
Saved.

Attire edits change fiction state and future visibility/prompts but do not
narrate themselves. Character Card owns initial outfit; Content owns whether
underneath prose may surface. Because current `attire_put` lacks a pipeline
guard, production editing requires the same idle/conditional-write protection
as other live world writers.

States cover no story, loading, empty/add first wearer, ready, dirty/device
draft, saving/normalized, conflict, active-pipeline read-only, invalid layering/
coverage, wearer removed, offline/error. Advanced lossless JSON remains a
secondary escape hatch, not the only editor. Persistence stores section/density
only; draft remains owner-qualified.

The miniature shows two wearer silhouettes as region/layer ledgers, not bodies
or clothing art. Acceptance proves all regions/states, layer ordering,
normalization reload, pipeline guard, silent consequence, draft recovery,
lossless Advanced, responsive/accessibility, and safe persistence.

---

# Widget design: Genre and Style

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `systems.genre-style` |
| Context | Active story; survival seeding active-frame qualified |
| Role | Workspace/editor |
| Multiplicity | Single per Panel |
| Minimum / preferred | 400 x 340 px / 720 x 600 px |
| Placement | focused/medium-wide grid; story-setup stack; bounded float |

## Purpose and contract

Configure how the active Story is written and interpreted: genre, tone, weather
severity, Director/Mapping notes, avoid guidance, Story language, player
authority, and bodily-condition policy.

Four explicit owner sections replace today's misleading all-or-nothing Save:

1. Style Guide saves genre/tone/weather/notes/avoid.
2. Story Language saves the Story/model language and names missing-pack impact;
   host interface language remains Settings-owned.
3. Player Authority saves the mode, explains interpretation consequences, and
   shows the current grant/change-history summary.
4. Condition Policy saves tracking and starter-layout cast visibility; enabling
   seeds player/active-cast vitals atomically in the selected frame, disabling
   stops ticks without deleting records.

Each section has its own draft/receipt/refresh. `Save all` may orchestrate them
only while reporting each result independently; partial success is never
labelled wholly Saved. Player/Cast Condition own the resulting projection.

States cover no story, aggregate loading with section isolation, missing
language pack, condition unseeded/seeded, authority consequence, section dirty/
saving/saved/failure, partial Save all, active pipeline constraint where served,
normalized reload, offline. Panel stores selected section/density only.

The miniature shows Genre/Tone, Story language, Authority, and Condition policy
as four compact owner cells. Acceptance proves independent receipts, partial
truth, language boundary, authority history, survival seeding/preservation,
visibility migration, draft recovery, responsive/accessibility.

---

# Widget design: Dialogue and Agency

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `systems.dialogue-agency` |
| Context | Active story |
| Role | Workspace/editor |
| Multiplicity | Single per Panel |
| Minimum / preferred | 380 x 320 px / 680 x 560 px |
| Placement | focused/medium-wide grid; story-setup stack; bounded float |

## Purpose and contract

Set registered-character conversation pacing and agency without absorbing
background management or Living World ceilings.

The scoped `dialogue_config` editor owns pacing style, min/max lines, variance,
autonomy, NPC initiative, NPC-to-NPC dialogue, stop on player address, stop on
question, silence ends exchange, opening reactors 1-12, and isolated opening
reactors. Engine-derived micro-round/character-call budgets are read-only
consequence summaries, never additional dials.

The shared dialogue-config service merges this field slice against confirmed
server truth, preserves unknown/future keys, clamps through the server, and
reloads normalized values. Off-screen Life and Background Life use other slices
of the same service; their unsaved drafts cannot be overwritten by this save.
Changes during a live turn are labelled `Applies to the next turn`.

States cover no story, loading, ready, dirty/saving/saved, numeric/order
validation, normalized clamp, active-run next-turn state, shared-document
conflict, offline/error. Panel stores section/density only.

The miniature shows autonomy/pacing and opening-reactor controls with a derived
budget line. Acceptance proves exact field ownership, future-key preservation,
shared-slice coordination, derived budget, next-turn semantics,
responsive/accessibility, and no Background/Living fields.

---

# Widget design: Off-screen Life

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `systems.offscreen-life` |
| Context | Active story |
| Role | Module/editor |
| Multiplicity | Single per Panel |
| Minimum / preferred | 260 x 220 px / 420 x 420 px |
| Placement | toolbar above minimum; medium grid; world-systems stack; bounded float |

## Purpose and contract

Choose the Story's off-screen simulation **ceiling** and paid-actor cap while
showing what that ceiling permits, costs, and whether current Living World
machinery requires it.

The ladder uses the engine vocabulary and descriptions: inert, deterministic,
reactive, stochastic, character_agent. Each rung shows built status and
plain-language consequence. `max_offscreen_actors` is 0-12; zero disables paid
ticks without erasing the chosen ceiling. Character Card owns per-character
agent opt-in.

The Widget edits only its `dialogue_config` slice through the shared service and
shows requested versus effective/required ceiling from Living World. It never
promises that permitted work must happen, and it never exposes physical
information carriers as a toggle.

The runtime owner is the active Story's dialogue-configuration projection and
save service; Character Cards retain per-Character opt-in ownership.

States cover no story, loading, all rungs built/unavailable future rung,
requested/effective clamp, cap zero, no opted-in candidates, dirty/saving/
conflict, active-run next-turn application, offline/error. Panel stores
collapse/density only.

The miniature shows the five-rung ladder, selected ceiling, effective marker,
and actor cap. Acceptance proves engine vocabulary/descriptions, ceiling-not-
instruction copy, zero-cap semantics, Living World dependency, Character opt-in
boundary, shared save, responsive/accessibility.

---

# Widget design: Living World

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `systems.living-world` |
| Context | Active story only |
| Role | Workspace/editor |
| Multiplicity | Single per Panel |
| Minimum / preferred | 380 x 320 px / 660 x 560 px |
| Placement | focused/medium-wide grid; world-systems stack; bounded float |

## Purpose and contract

Configure the four currently built autonomous-world approaches—Routine and
residue, Scheduled consequence, Places that owe a history, and Antagonist
ladder—without suggesting truth or information broadcasts.

Each approach shows requested Off/Floor/Ceiling, built status, required
off-screen ceiling, permitted/effective depth, description, and cost. Defaults
are all Off. One shared `living_world` service serves this Widget and the
Settings subwidget; there is one draft/save owner and a fresh accepted server
projection after every save.

The Widget never falls back to the first Library Story when no active Story
exists. Physical witnessing, speech, carriers, couriers, artifacts, and gossip
remain engine physics, not configurable approaches. A fired consequence is
fact; knowledge still moves by route.

States cover no story, loading, all off, mixed requested/effective,
off-screen-ceiling clamp, unavailable/unbuilt future approach, dirty/saving/
confirmed, conflict, active-run next-turn effect, offline/error. Panel stores
section/density only.

`systems.living-world` exists in the nineteen registry; refine it rather than
adding a duplicate. The miniature shows four approach rows with requested and
effective markers/cost. Acceptance proves four-not-five authority, no fallback
Story, one shared Settings owner, clamp/cost truth, default Off, information
boundary, responsive/accessibility.

---

# Widget design: Institutions and Charter

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `systems.institutions-charter` |
| Context | Active story/frame |
| Role | Workspace/editor |
| Multiplicity | Single per Panel |
| Minimum / preferred | 420 x 340 px / 760 x 620 px |
| Placement | focused/medium-wide grid; institution stack; bounded float |

## Purpose and contract

Inspect and configure story institutions/Charters—their resident bodies,
posts, clocks, upkeeps, markets, obligations, orders, judgments, and
character-history routes—without duplicating lived-location generation.

Reads/writes include the active frame explicitly. The ledger counts bodies from
the authoritative `charter.state.bodies` shape, names warnings literally, and
selects an institution for structured summaries/configuration through Charter
routes. Raw registry replacement is never the default editor.

`Prepare another lived location` becomes `Open Lived-in Location Builder` with
the selected attached Lore/context. This Widget may explain opening-history and
off-screen clamps but does not own that draft or generation request.

The runtime owner is the frame-qualified Charter registry/service. The Widget
owns only its selected institution and presentation state.

States cover no story, loading, no institutions, ready, warnings, selected
institution missing, no attached Lore for builder, frame mismatch, dirty/
saving/conflict for supported Charter config, background Charter landing,
offline/error. Engine diagnostics remain in the separate host-only Widget.
Panel stores section/tree/density only.

The miniature shows two institutions, body/post/upkeep counts, and one warning
without real names/private data. Acceptance proves frame query, real body shape,
rich sections, structured write authority, builder handoff, no browser
simulation, stale landing visibility, responsive/accessibility.

---

# Widget design: Institution Diagnostics

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `systems.institution-diagnostics` |
| Context | Active story/frame plus selected institution/body |
| Role | Workspace/editor (read-only advanced evidence) |
| Multiplicity | Single per Panel |
| Minimum / preferred | 460 x 340 px / 820 x 620 px |
| Placement | focused/medium-wide grid; institution technical stack; bounded float |

## Purpose and contract

Inspect host-only Charter summaries, warnings, commitments, economy, decisions,
history, refused interventions, featured-resident histories, and body-specific
life/beliefs/judgments through structured evidence rather than one raw JSON
dump.

Institution and optional body selection qualify the diagnostics route including
frame. Overview sections stay readable; full evidence/raw JSON remains a
closed disclosure. The Widget is read-only. Diagnostics are never cognition
input, player/guest projection, localization source, or Panel persistence.

The runtime owner is the frame-qualified Charter diagnostics projection; no
client-side cache becomes diagnostic truth.

States cover no story/institution, not loaded, loading on demand, empty result,
ready, selected body absent, warning/refused interventions, malformed section,
offline/error. A host-permission boundary prevents content from mounting for a
guest; the Catalog miniature uses synthetic counts/warnings only.

Acceptance proves institution/body filtering, frame scope, structured sections,
lazy full evidence, host-only enforcement, error-versus-empty,
plain-text/translate-no private evidence, responsive/accessibility, and zero
diagnostic data in persistence/preview.

---

# Widget design: Background Life / Scene Life

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `systems.background-life` |
| Context | Active story |
| Role | Workspace/editor |
| Multiplicity | Single per Panel |
| Minimum / preferred | 360 x 300 px / 620 x 520 px |
| Placement | focused/medium grid; story-systems stack; bounded float |

## Purpose and contract

Configure unsheeted presence reactions, managed Scene Life, and the threshold
that may make an addressed presence eligible for automatic Character promotion.

The Widget owns `scene_life` Off/Ambient/Full, `max_managed` 1-8,
`max_reactors` 1-3, and the promotion-after-addressed threshold 0-99 through
coordinated `background_config` plus the exact shared `dialogue_config` slice.
Global Content owns automatic-acquisition permission; effective promotion
requires both owners and real presence/activity evidence.

Off shows the reactor cap and explains individually selected reactions. Ambient
and Full show managed cap, information boundary, cost, and Full's directed-line
risk. Irrelevant controls leave focus order rather than remaining misleadingly
enabled. Promotion copy says it **may generate a permanent Character**, at most
one per beat; manual review belongs Background Presences.

States cover no story, loading, each mode, global auto-promotion off, threshold
zero, promotion effectively eligible, dirty/saving/partial two-document result,
shared conflict, active-run next-turn effect, offline/error. Each underlying
document receives its own receipt; partial success is explicit.

The miniature shows Off/Ambient/Full, the applicable cap, and a promotion
eligibility summary. Acceptance proves dependency-driven controls, information/
cost copy, exact caps, global permission, may-promote consequence, shared save,
manual-promotion boundary, responsive/accessibility.

---

# Widget design: Character Relationships

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `systems.character-relationships` |
| Context | Selected active-story Character and active frame |
| Role | Module |
| Multiplicity | Repeatable by selection channel |
| Minimum / preferred | 280 x 260 px / 460 x 500 px |
| Placement | toolbar above minimum; medium grid; character-mind stack; bounded float |

## Purpose and contract

Inspect one Character's private directed stance toward known others: trust,
familiarity, emotional valence, fear, respect, suspicion, last turn, salient
event, and stored notes.

The authoritative route is read-only. Despite the inventory's earlier “edit”
wording, no lawful host edit route exists; raw scalar writes would desynchronize
the relationship graph from append-only per-axis evidence. The Widget therefore
offers no edit control until a typed evidence-preserving mutation contract is
built. World State/Raw Story Data cannot substitute.

The runtime owner is the selected Character's private relationship projection;
the Widget owns only sort, density, and selection-following state.

Rows name target and all available axes with neutral meters/text; no universal
reputation score. Salient event is a source link when addressable. The Widget
does not fabricate unavailable history from the internal evidence ledger.

States cover no story/selection, Character detached, loading, empty, ready,
target missing, private access denied, stale frame/selection, offline/error.
Host-only data never enters guest/player projection or Catalog examples.
Panel stores sort/density only.

The miniature uses synthetic directed rows and two axis meters. Acceptance
proves holder→subject direction, every field, read-only authority, privacy,
checkpoint/frame refresh, error/empty, selection following,
responsive/accessibility, and no relationship data persistence.

---

# Widget design: Memory Browser

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `systems.memory-browser` |
| Context | Selected active-story Character; viewer frame qualified |
| Role | Workspace/editor |
| Multiplicity | Single per Panel; one selected-mind operation owner |
| Minimum / preferred | 520 x 400 px / 900 x 680 px |
| Placement | focused dominant; wide grid; character-mind stack; not toolbar |

## Purpose and contract

Search, inspect, add, edit, archive, permanently delete, import/export,
consolidate, preview exact agent context, and rebuild earlier summary eras for
one Character's private memory without crossing the mind/frame firewall.

The Workspace has compact filter/search (including semantic search), a
chronological memory ledger, selected-memory detail/editor, provenance/frame/
turn/category/importance/archive fields, and an owner action rail. Agent Context
Preview renders the exact qualified context the Character would receive; it is
not objective World truth.

Writes use one captured `story + Character + frame + memory/revision` owner.
Add/edit retain drafts and explicit save. Archive removes ordinary recent/
consolidation use according to engine rules but is not permanent deletion.
Delete removes the row and FTS mirror and requires irreversible confirmation.

Import is additive, strips foreign turn ids, preserves archive state, and
enforces the foreign-player-name firewall unless the host chooses the explicit
override after consequence review. Export names that it writes private mind
data to a portable file. Consolidation performs a model call, protects promise/
relationship/intention rows, and archives only eligible older low-importance
memories. `Rebuild earlier eras` backfills missing summary windows without
archiving or moving the live cursor and propagates them to checkpoints.

Memory-search embedding repair belongs Settings. Generic cue repair is not
offered because no supported route exists.

States cover no selection, loading, empty, no filter/semantic matches, ready,
dirty/saving/conflict, archived, import preview/firewall/refusal/result,
exporting/failure, consolidation running/partial/failure, context preview,
earlier-era coverage/rebuilding, permanent delete, stale frame/selection,
offline/error. Long tasks register with Background Work and survive unmount.

Panel stores filters/sort/density only; no memory, private export, draft,
semantic results, task, or Character id. The miniature uses synthetic redacted
memory rows/provenance and never private content. Acceptance proves every
operation/consequence, mind/frame firewall, import protection, consolidation
exclusions, backfill semantics, task ownership, responsive/accessibility, and
safe persistence.

---

# Widget design: Character Private History

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `systems.character-private-history` |
| Context | Selected Character attached to active story |
| Role | Workspace/editor |
| Multiplicity | Repeatable by selection channel; one shared history draft per owner |
| Minimum / preferred | 360 x 300 px / 620 x 540 px |
| Placement | focused/medium grid; character authoring stack; bounded float |

## Purpose and contract

Author the Story-qualified private-history entries a Character may know, with
explicit `content`, `about`, and exact `known_by` recipients, while preserving
the reusable fallback boundary.

The owner is `active story + Character + private-history revision` and is shared
with Story Character Card's same field. Two surfaces bind one draft/lease; they
cannot last-write-win. Save whole-replaces the Story-local list. Saving `[]`
shadows the reusable-sheet fallback, so the confirmation names that consequence.
A future `Use reusable history` action requires a real delete-override route;
the Widget does not fake reset by saving empty.

These entries are private knowledge. The owner sees all; another Character
receives only entries naming their exact normalized identity in `known_by`.
Checkpoint restore may revert Story Character history, and the Widget refreshes
accordingly.

Production writes require conditional revision or a serialized edit lease.
States cover no story/selection, detached, loading inherited/local source,
empty inherited/local override, dirty/device-saved, saving/conflict, shadow-
fallback warning, checkpoint change, invalid recipient, read-only prerequisite,
offline/error. No import/export is invented.

Panel stores section/density only. The miniature uses synthetic redacted entries
and recipient chips. Acceptance proves shared Story Character draft, knowledge
filter, fallback/empty semantics, checkpoint behavior, revision gate,
responsive/accessibility, and no private data in previews/persistence.

---

# Widget design: Persona Private History

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `systems.persona-private-history` |
| Context | Active story's primary Persona |
| Role | Workspace/editor |
| Multiplicity | Single per Panel |
| Minimum / preferred | 360 x 300 px / 620 x 520 px |
| Placement | focused/medium grid; Persona authoring stack; bounded float |

## Purpose and contract

Author the active Story's primary Persona private-history override, including
content, preserved `about`, and exact `known_by` recipients.

Current server authority has no `persona_id`; it supports only the Story's
primary Persona. The Widget states that scope and does not pretend additional
Personas are writable. Expanding to selected attached Personas requires a new
qualified route first.

The owner is `active story + primary Persona + history revision`, shared with
any Story setup surface that edits the same override. Saving whole-replaces the
world key; `[]` shadows reusable fallback and receives explicit warning. Unlike
Character history, this authoring key is intentionally preserved across reroll/
checkpoint restore. About data is never dropped merely because Main hid it.

Knowledge reaches Characters only through exact `known_by`; player-readable
greeting seeds enter only after story revelation. Production writes require
conditional revision/lease.

States mirror Character Private History plus primary Persona missing/changed,
additional Persona unsupported, and reroll-preserved confirmation. Persistence
and miniature use no private data. Acceptance proves primary-only truth,
preserved about, known-by firewall, fallback/empty warning, reroll preservation,
revision gate, shared owner, responsive/accessibility.

---

# Widget design: Dramatic Irony

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `systems.dramatic-irony` |
| Context | Active story, host-only |
| Role | Module |
| Multiplicity | Single per Panel |
| Minimum / preferred | 280 x 240 px / 460 x 500 px |
| Placement | toolbar above minimum; medium grid; knowledge stack; bounded float |

## Purpose and contract

Inspect non-archived, non-`witnessed` memory rows across Characters—information
a Character holds through heard/told/read/inferred provenance—not “player-known
truth” and not proof that the belief is objectively false.

Rows show Character, provenance, turn/frame where available, gist/content, and
`Open in Memory Browser`. Newest comes first. The Widget is read-only and
host-only. It never compares against Transcript/World, labels a belief true/
false, or leaks across the guest surface.

States cover no story, loading, confirmed empty, ready, Character/memory source
missing, stale story, access denied, offline/error. Panel stores filter/density
only. The miniature says `Unshared character knowledge` and uses synthetic
redacted rows rather than provocative secrets.

Acceptance proves provenance semantics, no player-known/objective claim,
read-only authority, privacy, memory-owner link, error/empty,
responsive/accessibility, and safe preview/persistence.

---

# Widget design: Promise Ledger

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `systems.promise-ledger` |
| Context | Active story, host-only |
| Role | Module |
| Multiplicity | Single per Panel |
| Minimum / preferred | 240 x 220 px / 360 x 460 px |
| Placement | toolbar; medium grid; knowledge stack; bounded float |

## Purpose and contract

Read the Story's **remembered promises** chronologically across Characters.
This is a projection of non-archived `category=promise` memory rows, not the
Charter typed commitment lifecycle and not a deduplicated objective contract
tracker.

Rows show Character holder, turn, gist/content, and `Open in Memory Browser`.
Oldest comes first. The Widget does not infer promisor, recipient, open/kept/
broken status, merge several minds' versions, or allow direct mutation.
Promise memories remain protected from consolidation aging by the mind owner.

States cover no story, loading, confirmed empty, ready, duplicate-looking
subjective rows, source missing, stale story, host access denied, offline/error.
Panel stores density/collapse only.

`systems.promise-ledger` exists and is placed in the active mockup; refine its
copy/miniature to say `Remembered promises` and avoid the current `3 open`
objective-status implication. Acceptance proves chronological subjective rows,
no Charter/status inference, privacy, Memory Browser link, responsive/
accessibility, and safe persistence.

---

# Widget design: Multiplayer and Guest Invites

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `systems.multiplayer-invites` |
| Context | Active story, host-only |
| Role | Module/editor |
| Multiplicity | Single per Panel |
| Minimum / preferred | 280 x 260 px / 460 x 500 px |
| Placement | toolbar above minimum; medium grid; story-setup stack; bounded float |

## Purpose and contract

Attach additional reusable Personas and securely create, copy, inspect, revoke,
or expire their guarded guest invitations.

The runtime owner is the active Story's attachment/grant service; one-time
invite results remain ephemeral service state rather than Widget persistence.

Rows distinguish additional Persona, invite pending, guest connected, expiry,
revoked/expired recent status where the server provides it, and detach. Attach
uses existing Personas; `Create Persona` delegates to Persona Card/New authoring.
Detach requires confirm and transactionally dormants attachment/revokes grants.

Create Invite has row busy state and returns a single-use 30-minute code; the
Persona-scoped guest token lasts 24 hours. Only hashes rest server-side;
redemption is atomic/rate-limited. The one-time URL is an ephemeral live result,
never Panel/local/session storage. Copy is explicit. Revoke/expiry/story change
immediately clears any revealed dead URL.

The Widget names public-tunnel/`SONDER_PUBLIC` safety prerequisites before
offering a shareable external URL. Guest middleware remains limited to guest
state/input; no host route or private Widget content crosses it.

States cover no story, loading, no additional players, ready, attaching,
invite creating/revealed/copied/pending/connected/expired/revoked, detach confirm,
pipeline guard, public sharing unavailable, stale Persona/grant, offline/error.
Panel stores collapse only.

The miniature uses two synthetic additional Personas and Pending/Connected
labels, never a URL/code. Acceptance proves all security lifetimes, ephemeral
clearing, busy/double-submit, detach transaction, primary/non-primary boundary,
guest isolation, responsive/accessibility.

---

# Widget design: Frames

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `systems.frames` |
| Context | Active story with active-frame marker |
| Role | Workspace/editor |
| Multiplicity | Single per Panel |
| Minimum / preferred | 360 x 300 px / 640 x 540 px |
| Placement | focused/medium grid; story-setup stack; bounded float |

## Purpose and contract

List/open Present and declared diegetic frames and create a new past/future/
other frame with explicit continuity rules.

Rows show label, ordinal, relationship to Present, travelers retaining memory
continuity, cast not yet existing/recognized, and Current. `Open frame` uses the
shared Story Context route. Creation has a recoverable owner-qualified draft
for label, ordinal, kind, travelers, and nonexistent cast, with consequence
copy explaining memory visibility/recognition/frame-scoped state.

Create is immediate/durable only after Review and row-level busy state. The
backend has no edit/delete route; the Widget offers neither. `spatial` remains
engine-created and is not a user option. Persona stationing is removed to Who's
Where.

States cover no story, loading, Present only, multiple/current, draft/review,
creating, validation, participant changed, pipeline/paradox guard when served,
offline/error. Panel stores density/collapse only; create draft stays qualified.

`systems.frames` exists in the nineteen registry; refine it and split stationing.
The miniature shows Present plus two ordered frames and continuity counts.
Acceptance proves no edit/delete invention, draft/review, consequences, spatial
exclusion, shared open, Who's Where split, responsive/accessibility.

---

# Widget design: Who's Where

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `systems.whos-where` |
| Context | Active story and frame roster |
| Role | Module |
| Multiplicity | Single per Panel |
| Minimum / preferred | 240 x 220 px / 360 x 420 px |
| Placement | toolbar; medium grid; Frames/Multiplayer stack; bounded float |

## Purpose and contract

Station each additional Persona in Present or a declared frame without
changing frame definitions, attachments, or invitations.

Rows pair one attached additional Persona with a labelled frame selector.
Immediate PUT captures Story/persona/source/target and enters row busy state.
On failure the Widget reloads authoritative stationing and restores the select;
it never leaves an optimistic false position.

Unknown/unattached targets, any active chat pipeline, and movement into/out of
an active-paradox frame are rejected. The error names the blocking frame;
unrelated-frame paradoxes do not disable other moves. Multiplayer owns attach/
detach/invite; Frames owns definitions.

States cover no story, loading, no additional Personas, Present only, ready,
moving, target frame removed, Persona detached, active pipeline, relevant
paradox block, offline/error. Panel stores sort/collapse only.

The miniature shows three Persona→frame rows with one blocked marker. Acceptance
proves exact owner/target, failed reload, scoped paradox blocking, no primary
Persona/attachment/frame editing, responsive/accessibility, safe persistence.

---

# Widget design: Time Paradox and Fixed Points

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `systems.paradox-fixed-points` |
| Context | Active story and operative frames |
| Role | Workspace/editor |
| Multiplicity | Single per Panel |
| Minimum / preferred | 420 x 340 px / 740 x 600 px |
| Placement | focused/medium-wide grid; Frames stack; bounded float |

## Purpose and contract

Configure paradox policy and fixed-point anchors, and inspect active paradoxes
with their real frame, severity, and consequences.

Policy fields are mode, escalation rate, and toll radius. Fixed Point fields
are entity, label, required-exists, optional frame, and optional per-anchor
mode. The active ledger shows all current paradoxes by operative frame/severity/
mode and links blocking context to Who's Where/Frames.

Writes are immediate but reviewed. Removing a Fixed Point requires explicit
confirmation and names material consequences. Hazard may consume/restore rooms;
toll irreversibly decays travelers' private memory confidence; warden/bureau
may create entities; severity ceiling may force-restore scene/world-entity
truth. The Widget does not offer a generic “resolve” button absent a real route.

Host authoring is private. What a mind may perceive remains frame-gated by the
engine; raw paradox diagnostics do not enter cognition or guest surfaces.

States cover no story, loading, no anchors/paradoxes, ready, one/multiple active,
dirty/review/saving, invalid entity/frame/mode, anchor removal confirm,
pipeline/station/branch blocked context, source changed, offline/error. Panel
stores section/density only.

The miniature shows policy, two anchors, and one frame-qualified severity row
using synthetic data. Acceptance proves every route field (including those
Main omitted), destructive confirmation, consequence copy, scoped blockers,
host/privacy boundary, no invented resolution, responsive/accessibility, safe
persistence.

---

# Shared boundary: Settings Widgets

Settings has one immutable six-group/eleven-row navigation registry, one
selected detail owner, and one search taxonomy. Making groups, panels, and
eligible instruments placeable does not create parallel Settings structures.

## Group, panel, and subwidget roles

- **Group Widgets** are navigation/summary Modules. They read already-loaded
  Settings, extension, and device state only. They never fetch, discover,
  mutate, or render duplicate forms. Activating a member locates/focuses its
  existing Widget or opens the one canonical Settings detail.
- **Panel Widgets** are the full maintained Settings rows. They preserve one
  detail scroll owner and all real controls for that row.
- **Subwidgets** are independently useful instruments detached from a panel.
  Parent and child bind the same draft/save service. `Locate in Workbench`
  replaces `Add` when the one live module already exists.

Server-owned Settings are Saved only after mutation succeeds and a fresh
authoritative Settings projection is accepted. Device-owned appearance,
accessibility, sound, and layout preferences use the versioned local preference
owner. Failed saves preserve form values and publish a visible problem. Long
prompts, connection forms, Custom Theme, installation sources, and raw JSON use
qualified recoverable drafts; simple toggles are not anonymous Panel state.

Settings Widgets never link to parallel Story/Library ownership. Story imports,
deletion, Turn details, Character/Lore authoring, and Institution tools remain
with their canonical Widgets. Active-Story Settings instruments render a
no-story state; they never fall back to the first Library Story.

Group summaries remain bounded and side-effect free. Compact/phone staging uses
one focused detail with Back; no rail + dashboard + detail combination and no
mobile bottom navigation. Dangerous reset, repair, rebuild, clear, remove, raw
save, and sign-out actions name data, reversibility, and consequence and stay in
their full owner treatment even when a compact status subwidget is placed.

---

# Widget design: Account and access

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `settings.group.account-access` |
| Context / role | Global / Settings group Module |
| Multiplicity | Single per Panel |
| Minimum / preferred | 240 x 112 px / 320 x 150 px |

The Module summarizes configured provider count, connection health already in
state, and default-model presence, then offers one member row: Provider
credentials. It never displays or accepts a secret. Activation locates/focuses
the panel or opens canonical Settings detail.

States are loading summary, no providers, configured, provider problem, and
member unavailable. Persistence stores collapse only. The miniature shows one
provider-health summary and the member row with synthetic names. Acceptance
proves no discovery/network side effect, no secret, one navigation owner,
locate/open behavior, and shared group responsiveness/accessibility.

---

# Widget design: AI and models

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `settings.group.ai-models` |
| Context / role | Global / Settings group Module |
| Multiplicity | Single per Panel |
| Minimum / preferred | 240 x 112 px / 320 x 150 px |

The Module summarizes the already-loaded Default assignment and count of
explicit role assignments, then exposes Model assignments. It does not query
provider models or edit routing. Empty means `No default model`, not an error.

Its summary owner is the already-loaded Settings projection; it owns no model
draft, discovery, or save operation.

States cover loading summary, no default, inherited roles, explicit roles, and
unavailable panel. Persistence stores collapse only. The miniature shows
Default plus a bounded role count. Acceptance proves summary-only behavior,
correct default/inheritance language, locate/open, and group accessibility.

---

# Widget design: Appearance and accessibility

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `settings.group.appearance-accessibility` |
| Context / role | Global device / Settings group Module |
| Multiplicity | Single per Panel |
| Minimum / preferred | 240 x 190 px / 320 x 250 px |

The Module summarizes current theme, prose size/density, sound/effects state,
and accessibility override count from already-loaded device preferences. Member
rows are Theme, Reading & layout, Sound & motion, and Accessibility in the
maintained order.

Its summary owner is the versioned device-preference projection; all editors
remain with the member Widgets.

It never applies a preview or resets preferences. States cover standard,
Custom Theme, muted/reduced/off effects, Accessibility Mode/override count, and
unreadable migrated preference fallback. Persistence stores collapse only. The
miniature uses four compact rows and semantic swatches from the current theme.
Acceptance proves live summary updates without independent state, stable order,
locate/open, and all group modes.

---

# Widget design: Story defaults and content

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `settings.group.story-content` |
| Context / role | Global / Settings group Module |
| Multiplicity | Single per Panel |
| Minimum / preferred | 240 x 112 px / 320 x 150 px |

The Module summarizes that Content owns story boundaries, narrator voice, and
Living World defaults/ceilings, then exposes the one Content member. It does not
project the active Story's actual settings or mutate defaults.

Its summary owner is the already-loaded global Settings projection; it owns no
Content or active-Story draft.

States cover loaded, server Settings unavailable, and Content member
unavailable. Persistence stores collapse only. The miniature shows three
bounded summary phrases and the member row. Acceptance proves global-default
language, no active-story confusion, locate/open, and group accessibility.

---

# Widget design: Data, extensions, and maintenance

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `settings.group.data-extensions-maintenance` |
| Context / role | Global / Settings group Module |
| Multiplicity | Single per Panel |
| Minimum / preferred | 240 x 144 px / 320 x 190 px |

The Module summarizes installed/enabled extension counts and bounded
maintenance status already loaded, then exposes Add-ons and Maintenance. It
does not discover updates, scan storage, or load extensions merely to render.

Its summary owner is the already-loaded extension/maintenance projection; the
group owns no task, poll loop, or action lease.

States cover extension summary loading, none installed, enabled/disabled mix,
safe mode/failure summary, maintenance attention already known, and member
unavailable. Persistence stores collapse only. The miniature shows two member
rows and a synthetic enabled count. Acceptance proves zero background work from
summary rendering, locate/open, and group accessibility.

---

# Widget design: Advanced

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `settings.group.advanced` |
| Context / role | Global with active-story availability / Settings group Module |
| Multiplicity | Single per Panel |
| Minimum / preferred | 240 x 144 px / 320 x 190 px |

The Module exposes Prompt editor and Raw story data with explicit Advanced
language. Summary names the active prompt preset and whether a Story is open;
it never loads prompt sheets or raw world data.

Its summary owner is the already-loaded Settings plus active-context projection;
the group owns no prompt or raw-data draft.

Raw story data remains visible but unavailable with `Open a Story first`; the
group does not silently select another Story. States cover loaded/no Story,
prompt preset unavailable, and member unavailable. Persistence stores collapse
only. The miniature shows two technical rows and an Advanced marker with no
raw content. Acceptance proves availability truth, no fetch, locate/open,
host-only technical labelling, and group accessibility.

---

# Widget design: Provider credentials

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `settings.provider-credentials` |
| Context / role | Global host / Settings panel workspace |
| Multiplicity | Single live owner across panel and detached instruments |
| Minimum / preferred | 420 x 360 px / 720 x 620 px |
| Placement | focused Settings detail; wide grid; bounded float |

This panel owns provider connections, credentials, the Default model,
memory-search model, response limit, OpenRouter routing, scene-backdrop model,
and room-ambience provider configuration. It is a technical setup workspace,
not an account dashboard. Provider rows show kind, display name, endpoint,
configured-secret state, and last explicitly requested connection result.

Add/Edit uses an owner-qualified recoverable draft. A blank secret preserves
the stored secret; no secret is ever read back, previewed, persisted in Panel
state, or retained after successful save. `Connect/Test` is an explicit remote
action with row busy state. The design adds a server-supported `Clear secret`
operation before offering that control; current delete capability must be
surfaced deliberately rather than simulated by a blank value.

Every server mutation is complete only after a fresh Settings projection is
accepted. Default/model/routing fields remain bound to their shared subwidget
owners. Provider model discovery is optional evidence, never a prerequisite
for entering a server-supported identifier. Contradictory OpenRouter allow/
deny choices and unconfigured provider/model pairs are reported before save.

States cover loading, no providers, configured/unconfigured secret, editing,
testing/success/failure, saving/confirmed/failure, provider removed while
editing, unsupported provider capability, and offline. Long connection drafts
survive remount; transient test results do not.

The miniature contains synthetic provider names and `Secret configured`, never
an endpoint token. Acceptance proves secret handling, blank-preserves behavior,
fresh projection, shared subwidget owners, capability/validation truth,
responsive staging, keyboard operation, and no automatic network calls.

---

# Widget design: Model assignments

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `settings.model-assignments` |
| Context / role | Global host / Settings panel workspace |
| Multiplicity | Single live assignment owner |
| Minimum / preferred | 460 x 380 px / 820 x 660 px |
| Placement | focused Settings detail; wide grid; bounded float |

This panel assigns provider, model, reasoning, supported samplers, and ordered
backups for every runtime role. An unset role says `Uses Default`; it never
silently names the Director or another hidden parent. Extension-provided roles
join the same owner and table rather than appearing in a second settings tree.

Rows are filterable and may expand for advanced controls. Capability metadata
governs which reasoning/sampler fields appear; unsupported controls are absent,
not merely disabled. Provider/model text remains editable when discovery is
unavailable, with explicit unverified state.

The whole assignment set saves as one reviewed draft. Production migration
requires a transactional or revision-qualified route; the current two-write
sequence is not treated as atomic. A conflict preserves the draft and offers
reload/compare. Resetting a row means inherit Default and is reversible until
Save. The Default model instrument shares this same assignment owner.

States cover loading, inherited/all-explicit/mixed, no Default, provider/model
unavailable, unverified identifier, capability mismatch, dirty/saving/
confirmed/conflict/failure, extension role added/removed, and offline. The
miniature shows Default plus three synthetic roles and inheritance chips.
Acceptance proves every role, exact inheritance semantics, one reviewed save,
extension lanes, capability gating, shared owner, and responsive/accessibility.

---

# Widget design: Theme

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `settings.theme` |
| Context / role | Global device / Settings panel workspace |
| Multiplicity | Single live appearance owner |
| Minimum / preferred | 400 x 360 px / 760 x 640 px |
| Placement | focused Settings detail; wide grid; bounded float |

Theme presents the Design Bible 2.0 curated themes and the shared Custom Theme
editor. Deep Current is the baseline. Each preset previews on the real shell
materials, semantic status colors, text, controls, and canvas—not isolated
swatches—and commits immediately through the versioned device-preference owner.

Custom Theme is one movable child owner, never a second editor. Invalid drafts
may be inspected but cannot become active. Cancelling preview restores the last
valid active theme. Import is parsed and reviewed before it touches the draft;
export excludes unrelated preferences.

States cover preset selected/previewed, custom valid/invalid/imported-dirty,
device persistence failure, migrated legacy palette, reduced-effects preview,
and unsupported color input. The miniature uses semantic theme samples from
the active palette. Acceptance proves Bible roles/materials, Deep Current,
invalid-never-applies, preview rollback, one Custom Theme draft, device-local
persistence, color-independent status, and responsive/accessibility.

---

# Widget design: Reading & layout

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `settings.reading-layout` |
| Context / role | Global device / Settings panel module-editor |
| Multiplicity | Single live reading-preference owner |
| Minimum / preferred | 320 x 300 px / 560 x 520 px |
| Placement | focused Settings detail; medium grid; bounded float |

The panel owns story text size, reading density, measure/line-height when the
runtime supports them, and the Full/Reduced/Off visual-effects tier. A live
synthetic prose sample demonstrates hierarchy and reflow without showing story
content. Effects remain here until a deliberate Settings taxonomy change; the
Sound & motion summary links to this exact owner rather than duplicating it.

Simple selections apply immediately through the versioned device-preference
service. Large story text and roomy controls are projections of the same
accessibility keys, so changes stay synchronized with Accessibility controls.
`Reset reading` restores only this bounded family and states the overlap.

States cover standard/compact, each supported size/effects tier, accessibility
override, migrated fallback, persistence failure, and narrow preview. The
miniature is the prose sample plus current values. Acceptance proves one owner
for overlaps, usable targets, reduced/off effects, deterministic reset,
responsive reflow, zoom, keyboard, and no private preview content.

---

# Widget design: Sound & motion

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `settings.sound-motion` |
| Context / role | Global device plus host language / Settings panel module-editor |
| Multiplicity | Single live sound-preference owner |
| Minimum / preferred | 320 x 300 px / 560 x 520 px |
| Placement | focused Settings detail; medium grid; bounded float |

The panel owns story volume, mute, turn-complete chime, and host interface
language. Story sound binds the same atmosphere runtime used in Scene; a placed
child moves that owner rather than creating another live mixer. `Preview chime`
is offered only when the browser can execute it and never unlocks audio without
a user gesture.

Sound preferences apply immediately to the device. Interface language is a
server-owned explicit Apply action, confirmed through a fresh Settings
projection, and says `Applies after reload`. Motion/effects are summarized with
a `Locate Reading & layout` action because their owner remains there; no
duplicate motion switches appear.

States cover normal/muted, browser audio locked, previewing/unavailable,
language dirty/saving/confirmed/failure/reload-required, device persistence
failure, and offline. The miniature shows bounded sound status and language,
never an audio waveform. Acceptance proves shared Scene runtime, gesture-safe
preview, separate persistence scopes, honest motion ownership, reset behavior,
and responsive/accessibility.

---

# Widget design: Accessibility

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `settings.accessibility` |
| Context / role | Global device / Settings panel workspace |
| Multiplicity | Single live accessibility owner |
| Minimum / preferred | 360 x 340 px / 640 x 580 px |
| Placement | focused Settings detail; medium-wide grid; bounded float |

Accessibility exposes Mode plus solid surfaces, high contrast, color-
independent status markers, reduced motion/canvas effects, strong focus, large
interface, large story text, and roomy controls. Mode is a convenience bundle;
granular changes recompute its state rather than hiding which preferences are
active. Story size and layout overlaps bind the same device keys.

Every change applies immediately and has a perceivable, non-motion-dependent
preview. `Reset Experience` remains a staged panel action: it lists theme,
reading, effects, sound, and accessibility preferences it will reset and says
stories and host Settings are unchanged. It must reset hidden/migrated keys as
well as visible controls.

States cover Mode on/off/mixed, individual overrides, migration fallback,
device persistence failure, reset review/applied/failure, and forced OS/browser
preference. The miniature uses synthetic control/status examples. Acceptance
proves WCAG-oriented keyboard/focus/status behavior, complete reset, shared
overlap ownership, reduced motion, 200% zoom/reflow, and no color-only meaning.

---

# Widget design: Content

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `settings.content` |
| Context / role | Global host plus explicit active story / Settings panel workspace |
| Multiplicity | Single live owner per scope-qualified instrument |
| Minimum / preferred | 420 x 380 px / 760 x 680 px |
| Placement | focused Settings detail; wide grid; bounded float |

Content composes three independently movable owners: global Content
preferences, global Narrator voice examples, and active-story Living World
controls. Strong section headers and scope labels prevent global defaults from
being mistaken for Story state. No open Story produces an explicit unavailable
Living World section; it never selects the first Library Story.

The global preference set saves as one reviewed transaction. Until the server
offers transactional/revision-qualified mutation, partial failure is surfaced
as `Some settings changed—reload server truth` rather than a false all-or-
nothing failure. Voice and Living World retain their own save owners and states.

States compose loading, global ready/dirty/saving/failure, no Story, story
loading/clamped/conflict, voice dirty, and offline without collapsing distinct
consequences into one banner. The miniature uses scope-labelled synthetic
summaries. Acceptance proves scope separation, no fallback Story, one owner per
child, fresh authoritative projections, retained drafts, consequence copy,
and responsive/accessibility.

---

# Widget design: Add-ons

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `settings.add-ons` |
| Context / role | Global host / Settings panel workspace |
| Multiplicity | Single extension-list/action coordinator |
| Minimum / preferred | 440 x 380 px / 820 x 680 px |
| Placement | focused Settings detail; wide grid; bounded float |

Add-ons owns the installed-extension listing/action coordinator and the install
source draft. Installed and Install subwidgets consume those same services;
mounting several surfaces cannot duplicate listings, update checks, busy state,
registration reload, or trust prompts.

Rows show enabled/disabled, safe mode, load/fault state, declared access,
unreviewed/trusted disclosure, and update state. Enable and install stage code-
access consequences. Install validates and lands disabled. Update repeats trust
review when fetched code/disclosure changed, unregisters the prior owner, and
reloads enabled registrations before reporting completion. Remove confirms
file deletion and explicitly says story data is retained.

States cover loading/failure/empty, safe mode, enabled/disabled/fault-retired,
checking/update available/current/updating, enabling/disabling/removing,
install draft/review/installing/result, registration reload failure, stale
listing, and offline. Long install source drafts survive remount; update results
are coordinator state.

The miniature uses synthetic extensions and disclosure chips. Acceptance
proves owner-bound lifecycle/teardown, repeated trust review, disabled install,
safe mode, no duplicate operations, enabled UI reload, failure containment,
responsive/accessibility, and no extension code/content in previews.

---

# Widget design: Maintenance

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `settings.maintenance` |
| Context / role | Global host / Settings panel workspace |
| Multiplicity | Single maintenance coordinator with movable instruments |
| Minimum / preferred | 420 x 380 px / 760 x 680 px |
| Placement | focused Settings detail; wide grid; bounded float |

Maintenance composes updates, checkpoint storage, memory-search repair,
diagnostics, and host-session controls. Each instrument keeps its own
consequence class while a shared coordinator owns polling, background-task
identity, current status, and action leases. A parent and placed child never
start duplicate one-second loops or repairs.

The runtime owner is that maintenance coordinator plus each server instrument;
the panel contributes composition and no parallel task state.

All mutating actions use Review before Start. Update names dirty-checkout and
restart consequences; checkpoint conversion names rollback-history storage and
equivalence protection; memory rebuild names possible paid provider use;
diagnostics names its redacted bounded payload; sign out names exactly the
browser session it destroys and the host/device data it preserves.

States compose unchecked/checking/current/available/dirty/restart-required,
checkpoint current/legacy/running/refused, memory current/stale/running/error,
diagnostics ready/exporting/failure, session ready/sign-out review, background
work continuing, and offline. The panel does not store task progress.

The miniature uses synthetic bounded status only. Acceptance proves shared
polling/task leases, confirmations and reversibility copy, paid-call boundary,
redacted diagnostics, sign-out scope, unmount survival, responsive/accessibility.

---

# Widget design: Prompt editor

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `settings.prompt-editor` |
| Context / role | Global host / Settings panel workspace |
| Multiplicity | Single live `settings-prompts` owner |
| Minimum / preferred | 520 x 420 px / 920 x 720 px |
| Placement | focused Settings detail; wide grid only; bounded large float |

Prompt editor and its eligible Prompt preset/editor instrument are two
placements of the same owner, never two editors. The workspace owns selected
preset, language, fragment-aware sheets, named save, activate, import/export,
and confirmed delete. `Default` is read-only; deleting the active preset falls
back to Default only after server confirmation.

Long sheets use an owner-qualified recoverable draft with explicit dirty state,
leave protection, and server revision. Save/activate/import/delete finish only
after a fresh Settings projection. Import receives a unique name and is
validated for language, object shape, and resolvable fragments before review.
Export contains only the selected preset.

States cover loading, Default/custom selected, active/inactive, clean/dirty/
device-saved, validation findings, saving/confirmed/conflict/failure,
activating, importing preview/refused/result, exporting, delete review, and
external preset change. Panel state stores only layout/search.

The miniature shows synthetic sheet names and dirty/active state, never prompt
text. Acceptance proves one live draft, long-draft retention, conflict safety,
all validations/actions, Default protections, fresh projection, responsive
large-workspace behavior, keyboard tabs, and no prompt content in previews.

---

# Widget design: Raw story data

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `settings.raw-story-data` |
| Context / role | Explicit active story and Present frame / Settings lab workspace |
| Multiplicity | Single live raw-data owner per story |
| Minimum / preferred | 520 x 420 px / 920 x 720 px |
| Placement | focused Advanced detail only; not draggable/floating |

Raw story data is the canonical contained lab for whole-world JSON and raw
Present-frame clothing JSON. It is intentionally not a general utility Widget:
the destructive editor remains in Settings, while the eligible Raw clothing
instrument can only project/locate its corresponding section until a safer
structured owner exists.

The user explicitly chooses the open Story; no route query/no open Story means
unavailable, never first-Library fallback. Load creates a recoverable draft
qualified by Story, frame, record revision, and kind. Save requires valid JSON,
idle pipeline for both kinds, review of the exact target and replacement
domains, conditional revision, server normalization, authoritative reload, and
shared Story/Scene refresh. Clothing explicitly says it re-derives wearing,
state, and regions and currently targets Present only.

States cover no Story, explicit target/loading, clean/dirty/device-saved,
parse/schema finding, review/saving/confirmed/conflict/failure, pipeline busy,
frame/story changed, normalized server result, and offline. Nothing raw enters
Panel persistence, previews, diagnostics, guest surfaces, or cognition.

The miniature is unavailable/redacted status only. Acceptance proves explicit
targeting, no fallback, draft retention, revision and idle gates, confirmation,
authoritative refresh, clothing normalization/Present truth, privacy, keyboard
editor support, and compact focus staging.

---

# Widget design: Connections and credentials

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `settings.connections` |
| Context / role | Global host / technical module-editor |
| Multiplicity | Single live provider-connection owner |
| Minimum / preferred | 340 x 280 px / 600 x 520 px |
| Placement | medium grid; Provider credentials stack; bounded float |

The instrument lists provider kind/name, endpoint, configured-secret state, and
the last explicit connection check. Add/Edit and Test bind the Provider
credentials panel's recoverable connection draft/action service. Blank secret
means preserve; `Clear secret` appears only with a real server operation and
review. Successful mutation accepts a fresh Settings projection.

States cover empty, configured/unconfigured, editing, secret preserved/
replaced/clear review, testing/success/failure, saving/conflict/failure, and
offline. The miniature uses synthetic names and no endpoint/secret. Acceptance
proves one owner, no secret readback/persistence, no automatic test, retained
draft, capability truth, fresh projection, responsive/accessibility.

---

# Widget design: Default model

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `settings.default-model` |
| Context / role | Global host / compact module-editor |
| Multiplicity | Single live default-assignment owner |
| Minimum / preferred | 260 x 180 px / 380 x 260 px |
| Placement | toolbar above minimum; AI stack; bounded float |

Select provider/model for the `default` runtime role and show how many roles
currently inherit it. The value is bound to Model assignments' same draft; a
change in either surface appears in both before save. Discovery suggestions are
evidence only, and free entry remains available when the server accepts it.

States cover unset, selected, unverified/unavailable identifier, dirty/saving/
confirmed/conflict/failure, and no providers. The miniature shows a synthetic
model plus inheritance count. Acceptance proves exact Default inheritance,
shared draft, no hidden Director fallback, capability truth, and compact/
accessible selection.

---

# Widget design: Memory-search model

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `settings.memory-search-model` |
| Context / role | Global host / compact module-editor |
| Multiplicity | Single live embeddings-assignment owner |
| Minimum / preferred | 280 x 200 px / 420 x 300 px |
| Placement | toolbar above minimum; AI/Maintenance stack; bounded float |

Configure the provider/model used for memory-search embeddings and display the
current index compatibility status. Saving the assignment never silently starts
a rebuild. If the new model makes existing vectors stale, the result links to
the one Memory-search repair owner with explicit paid-call consequence.

States cover unset, compatible, changed/rebuild recommended, unverified model,
dirty/saving/confirmed/conflict/failure, and provider unavailable. The
miniature shows synthetic identifiers and `Index current/stale`, never memory.
Acceptance proves assignment versus repair separation, shared Settings owner,
fresh projection, no automatic paid work, and responsive/accessibility.

---

# Widget design: Response limit

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `settings.response-limit` |
| Context / role | Global host / compact module-editor |
| Multiplicity | Single live setting owner |
| Minimum / preferred | 240 x 160 px / 340 x 220 px |
| Placement | toolbar; AI stack; bounded float |

Set the runtime maximum output tokens within the server-authoritative
1024–128000 range. The control shows the exact numeric value, validates before
save, and states `Applies to the next model call`; it does not promise prose
length or cost. Invalid input is never silently coerced in the interface.

States cover inherited/default, valid dirty, below/above range, saving/
confirmed/conflict/failure, and server-normalized result. The miniature uses a
synthetic bounded value. Acceptance proves range, next-call timing, fresh
projection, explicit normalization, keyboard numeric input, and compact reflow.

---

# Widget design: OpenRouter routing

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `settings.openrouter-routing` |
| Context / role | Global host / technical module-editor |
| Multiplicity | Single live routing-policy owner |
| Minimum / preferred | 340 x 280 px / 620 x 520 px |
| Placement | medium grid; Provider credentials stack; bounded float |

When the selected connection is OpenRouter, edit ordered provider preferences,
allow and deny slugs, privacy/data policy, and provider pinning. The server's
ordering capability is visible rather than discarded. Other provider kinds
render `Not applicable` with a locate action; they do not show inert controls.

Contradictory allow/deny/pin choices block Save and identify exact entries.
Discovery may suggest canonical slugs but does not replace free entry. States
cover not applicable, empty policy, dirty/invalid, discovery unavailable,
saving/confirmed/conflict/failure, and selected connection removed. The
miniature uses synthetic slugs. Acceptance proves every server field,
contradiction handling, capability gating, shared owner, and accessible ordered
editing.

---

# Widget design: Scene backdrops

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `settings.scene-backdrops` |
| Context / role | Global host / compact module-editor |
| Multiplicity | Single live backdrop-configuration owner |
| Minimum / preferred | 280 x 220 px / 440 x 340 px |
| Placement | toolbar above minimum; AI/appearance stack; bounded float |

Configure backdrop generation provider/model, enabled state, and continuity
policy. This Settings instrument owns only provider/configuration. Scene owns
contextual Generate/Reroll and current-image presentation; no story image or
prompt appears here.

Enabling an unconfigured or capability-incompatible model is refused before
save. The configuration saves transactionally/revision-qualified rather than
the current sequential writes. States cover off, ready, unconfigured,
unsupported, dirty/saving/confirmed/conflict/failure, and provider removed.
The miniature shows configuration status only. Acceptance proves ownership
split, validated enable, atomic intent, fresh projection, and accessible reflow.

---

# Widget design: Room ambience

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `settings.room-ambience` |
| Context / role | Global host / compact module-editor |
| Multiplicity | Single live ambience-configuration owner |
| Minimum / preferred | 300 x 240 px / 480 x 400 px |
| Placement | medium grid; Provider credentials/Sound stack; bounded float |

Configure ambience source (`Local folder` or `Freesound`), source-qualified
folder/API credential, enabled state, and licence policy. This is distinct from
`story.room-ambience`, which generates/edits the selected room's descriptive
ambience data; both feed the same runtime but own different records.

Only fields relevant to the selected source appear. A blank API secret
preserves it; clear requires a real reviewed operation. Secret input is removed
from the DOM after save. Enabling incomplete source configuration is refused.

States cover off, local ready/missing folder, Freesound ready/missing secret,
licence refusal, dirty/saving/confirmed/conflict/failure, and source changed.
The miniature shows source/readiness only. Acceptance proves source gating,
secret safety, no story-data overlap, fresh projection, and accessibility.

---

# Widget design: Custom Theme

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `settings.custom-theme` |
| Context / role | Global device / theme workspace-editor |
| Multiplicity | Single live Custom Theme draft |
| Minimum / preferred | 420 x 380 px / 780 x 680 px |
| Placement | focused/medium-wide grid; Theme stack; bounded float |

Author the Design Bible workbench roles—Canvas ink, Glass panel, Control
chrome, Ambient accent, Interface text, and Source accent—plus semantic status
colors, density, bar opacity, selected strength, frost, Ambient Light X/Y/
radius/intensity, and canvas/gradient treatment. Native color, hex, RGB, and
eyedropper inputs converge on the same validated field.

The runtime owner is the versioned device-theme service; all placements bind
one recoverable Custom Theme draft.

The recoverable draft is separate from the last valid active theme. `Preview`
temporarily applies the complete draft; `Use` validates and persists it;
`Cancel preview` restores the prior theme. Reset restores the safe Custom Theme
draft but does not silently activate it. Import is parsed/reviewed; export is
only this schema, versioned for migration from the retired eight-role palette.

States cover clean/dirty/device-saved, valid/invalid field, previewing, imported
legacy/migrated, using/selected, reset review, device persistence failure, and
unsupported eyedropper. The miniature shows semantic materials from the last
valid theme, not an invalid draft. Acceptance proves every Bible control,
invalid-never-applies, rollback, schema migration, one draft across placements,
contrast/status checks, responsive staging, and keyboard accessibility.

---

# Widget design: Story reading and layout

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `settings.story-reading-layout` |
| Context / role | Global device / compact module-editor |
| Multiplicity | Single live reading-preference owner |
| Minimum / preferred | 280 x 220 px / 440 x 360 px |
| Placement | medium grid; Reading/Accessibility stack; bounded float |

Place story text size, reading density, and Full/Reduced/Off effects beside a
synthetic live prose sample. The instrument moves the same owner used by the
Reading & layout panel. Large story text/roomy overlaps are visibly attributed
to Accessibility and update in both surfaces.

Selections apply immediately through versioned device preferences. States
cover each value, accessibility override, migrated fallback, persistence
failure, and narrow sample reflow. The miniature is the redacted prose sample.
Acceptance proves one overlap owner, immediate truthful preview, reduced/off
effects, deterministic reset/locate, 200% zoom, and keyboard operation.

---

# Widget design: Story sound

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `settings.story-sound` |
| Context / role | Global device with Scene runtime / compact module-editor |
| Multiplicity | Single live sound owner across Settings and Scene |
| Minimum / preferred | 240 x 180 px / 360 x 260 px |
| Placement | toolbar above minimum; Sound/Scene stack; bounded float |

Control story volume, mute, and turn-complete chime through the one atmosphere
runtime. A Scene placement and Settings placement are two locations of the same
module, not synchronized duplicates. Optional `Preview chime` requires a user
gesture and disappears when playback is unavailable.

States cover normal/muted, chime on/off, browser audio locked, previewing/
unavailable, device persistence failure, and runtime unavailable. The miniature
contains only values/status. Acceptance proves one live mixer, immediate
device persistence, gesture-safe preview, Reset Experience integration,
keyboard range semantics, and compact reflow.

---

# Widget design: Accessibility controls

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `settings.accessibility-controls` |
| Context / role | Global device / module-editor |
| Multiplicity | Single live accessibility owner |
| Minimum / preferred | 320 x 280 px / 520 x 480 px |
| Placement | medium grid; Accessibility stack; bounded float |

Expose Accessibility Mode and every granular preference: solid surfaces, high
contrast, color-independent status, reduced motion/canvas, strong focus, large
interface, large story text, and roomy controls. Mode can be mixed when a
granular preference diverges. Reading/layout overlaps are the same keys.

Changes apply immediately. The dangerous breadth of `Reset Experience` remains
in the full Accessibility panel; this instrument offers `Locate reset`, not a
compact destructive shortcut. States cover Mode on/off/mixed, overrides,
forced platform preference, migration, and persistence failure. The miniature
uses accessible synthetic controls/status. Acceptance proves complete keys,
one owner, no color-only status, focus/target/zoom/reflow, and safe reset split.

---

# Widget design: Content preferences

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `settings.content-preferences` |
| Context / role | Global host / module-editor |
| Multiplicity | Single live content-preference draft |
| Minimum / preferred | 320 x 280 px / 540 x 460 px |
| Placement | medium grid; Content stack; bounded float |

Edit adult story content, card underneath descriptions, recurring-extra
promotion, and affect habituation with the same consequence copy as the full
Content panel. Reset changes the draft only; Save is explicit.

The runtime owner is the global server Settings projection and its shared
content-preference draft/save service.

The four values must land transactionally/revision-qualified. Until that route
exists, partial writes are reconciled by reloading server truth and clearly
identifying which values changed; the UI never claims rollback it did not
perform. Failed save retains the draft for compare/retry.

States cover clean/dirty, saving/confirmed/conflict/partial/failure, server
normalization, and offline. The miniature shows synthetic On/Off values only.
Acceptance proves all four consequences, future-beat timing, transactional
intent, fresh projection, shared panel draft, and responsive/accessibility.

---

# Widget design: Narrator voice examples

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `settings.narrator-voice` |
| Context / role | Global host / module-editor |
| Multiplicity | Single live exemplar draft |
| Minimum / preferred | 380 x 300 px / 660 x 540 px |
| Placement | focused/medium grid; Content stack; bounded float |

Author the server-limited voice-example passages in one tabbed textarea. One
passage is visible at a time; Left/Right/Home/End move ARIA tabs, and drafts
survive switches, placement changes, and remount. Copy states that every saved
passage joins every narrator call as style guidance, never story fact.

The runtime owner is the global exemplar service and one recoverable shared
draft qualified by its server revision.

Save trims and drops blank passages, validates count/length before mutation,
then accepts a fresh Settings projection. `Clear all` is a reviewed draft
action followed by Save. Dirty leave gets an explicit keep/discard/cancel gate.

States cover empty, selected slot, dirty/device-saved, count/length finding,
saving/confirmed/conflict/failure, server-clamped legacy value, and offline.
The miniature shows slot count/dirty state, never authored passage text.
Acceptance proves limits, runtime consequence copy, retained draft, tab
keyboard model, fresh projection, privacy, and responsive focus staging.

---

# Widget design: Living World controls

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `settings.living-world-controls` |
| Context / role | Explicit active story / module-editor |
| Multiplicity | Single live owner shared with Story Living World |
| Minimum / preferred | 360 x 320 px / 620 x 560 px |
| Placement | focused/medium grid; Content/Living World stack; bounded float |

Configure the engine-owned Routine and residue, Scheduled consequence, Places
that owe a history, and Antagonist ladder approaches at Off/Floor/Ceiling. It
shares the `story.living-world` service and draft; Settings and Story placements
cannot edit independently. Scope is the explicitly active Story only.

Each row shows requested, built, permitted, and effective truth plus cost/
consequence. Unbuilt tiers are informative and not selectable. Save accepts the
normalized PUT response and immediately reloads the authoritative Story
projection so clamps cannot remain stale. `All off` is a reviewed draft action.

States cover no Story, loading/error, ready, requested/effective clamp, unbuilt
or policy-forbidden tier, dirty/saving/confirmed/conflict/failure, Story changed,
and offline. The miniature uses synthetic tier/status only. Acceptance proves
all four engine definitions, no first-Library fallback, one owner with Story,
effective refresh, carrier boundary copy, and responsive/accessibility.

---

# Widget design: Installed extensions

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `settings.installed-extensions` |
| Context / role | Global host / module-editor |
| Multiplicity | Single shared extension-list/action coordinator |
| Minimum / preferred | 340 x 300 px / 620 x 560 px |
| Placement | focused/medium grid; Add-ons stack; bounded float |

List installed extensions with enabled/disabled, safe mode, load/fault state,
declared access/trust, and update status. Enable, disable, check, update, and
remove use Add-ons' same listing/action coordinator and row leases. Enable and
changed-code update stage disclosure review; remove names file deletion and
retained story data.

States cover loading/failure/empty, enabled/disabled/fault-retired, safe mode,
checking/current/update available/updating, enabling/disabling, remove review,
registration reload failure, stale listing, and offline. The miniature uses
synthetic entries/disclosures. Acceptance proves one listing/poll/action owner,
owner teardown/reload, repeated trust review, failure isolation, and accessible
responsive rows.

---

# Widget design: Install extension

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `settings.install-extension` |
| Context / role | Global host / compact module-editor |
| Multiplicity | Single live install draft/action lease |
| Minimum / preferred | 300 x 220 px / 500 x 360 px |
| Placement | medium grid; Add-ons stack; bounded float |

Accept a supported extension source, validate it, preview package identity and
declared access, then stage the unreviewed-code consequence. Installation lands
disabled and does not register browser/runtime code. The source draft is
recoverable and shared with Add-ons; successful install clears it.

The runtime owner is Add-ons' install coordinator and one recoverable source
draft/action lease.

States cover empty/dirty/device-saved, validating, malformed/hostile/refused,
review ready, installing, installed-disabled, duplicate/version conflict,
cleanup failure, and offline. The miniature contains a synthetic source and no
real repository/user path. Acceptance proves staging/atomic landing, disabled
result, trust copy, no double-submit, retained draft, and accessibility.

---

# Widget design: Sonder updates

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `settings.sonder-updates` |
| Context / role | Global host / maintenance module |
| Multiplicity | Single update coordinator/action lease |
| Minimum / preferred | 280 x 220 px / 440 x 340 px |
| Placement | toolbar above minimum; Maintenance stack; bounded float |

Explicitly check for Sonder updates and, when safe, review/install one. Check is
the only remote read and never starts on mount. Install names checkout mutation,
dirty-worktree refusal, service interruption, and required restart; it remains
a confirmed full-width action when the module is compact.

The runtime owner is the shared update coordinator and its single check/install
action lease.

States cover unchecked/checking/error, current/available, dirty/refused,
install review/installing/failure, installed/restart-required, and version
changed. The miniature shows synthetic status only. Acceptance proves no
automatic network work, dirty protection, one lease, restart truth, background
continuity, responsive confirmation, and keyboard accessibility.

---

# Widget design: Checkpoint storage

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `settings.checkpoint-storage` |
| Context / role | Global host / maintenance module |
| Multiplicity | Single background-task/poll owner |
| Minimum / preferred | 300 x 240 px / 480 x 380 px |
| Placement | medium grid; Maintenance stack; bounded float |

Inspect checkpoint storage compatibility and, after review, start resumable
conversion. Copy states that conversion rewrites rollback-history storage, does
not re-embed/delete story content, skips converted entries, and leaves any
failed equivalence check untouched.

The shared maintenance coordinator owns the task and polling across unmounts
and placements. States cover checking/error, none/current/legacy, review,
running with bounded progress, partially complete, equivalence refused, failed,
and completed. The miniature uses synthetic counts. Acceptance proves one task/
poll loop, resumability, equivalence safety, unmount survival, and accessibility.

---

# Widget design: Memory-search repair

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `settings.memory-search-repair` |
| Context / role | Global host / maintenance module |
| Multiplicity | Single background-task/poll owner |
| Minimum / preferred | 300 x 240 px / 480 x 380 px |
| Placement | medium grid; Maintenance/AI stack; bounded float |

Inspect vector-index compatibility and explicitly rebuild when stale. Review
names the selected embeddings provider/model, possible paid calls, asynchronous
work, and that story/memory records are preserved. Changing the model merely
marks repair recommended; it never auto-starts this action.

States cover checking/error, current/stale/model missing, review, queued/running
with progress, provider failure/partial, completed, and assignment changed
during run. The shared coordinator owns task/polling. The miniature shows
synthetic status/counts only. Acceptance proves paid-work consent, no automatic
start, one task owner, retained memories, unmount survival, and accessibility.

---

# Widget design: Diagnostics

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `settings.diagnostics` |
| Context / role | Global device/host session / compact maintenance module |
| Multiplicity | Single snapshot action owner |
| Minimum / preferred | 240 x 170 px / 360 x 240 px |
| Placement | toolbar; Maintenance stack; bounded float |

Describe and download the bounded redacted interface-event snapshot produced
by the diagnostics service. It is not a server-log viewer and offers no repair.
Copy guarantees credentials and request bodies are excluded; preview shows only
event count/time range and redaction policy, never event text.

States cover ready/no events, preparing/exported/failure, snapshot service
unavailable, and policy version changed. No diagnostic content enters Panel
persistence or the catalog miniature. Acceptance proves bounded scope,
redaction, accurate non-server language, user-initiated download, and accessible
compact behavior.

---

# Subwidget disposition: Host session

**Disposition:** Not a Widget; retain as a full Maintenance panel section

Current Host session is one dangerous `Sign out` command plus consequence copy.
It has no recurring inspectable surface or independently useful live owner, so
it fails the inventory's Widget eligibility rule and the Design Bible rule that
dangerous operations do not ride draggable modules.

Maintenance shows authenticated-session status and owns the staged sign-out
action. Confirmation says it destroys only this browser's authenticated
session, preserves host stories/Settings and device drafts, and redirects to
login. Group/module summaries may say `Host session active` but cannot execute
sign out. Acceptance proves no catalog entry/type/placement, no compact sign-out
shortcut, exact preservation copy, and one canonical action owner.

---

# Widget design: Prompt preset/editor

**Design state:** First draft, ready for mockup translation

| Contract | Value |
|---|---|
| Type | `settings.prompt-preset-editor` |
| Context / role | Global host / large workspace-editor |
| Multiplicity | Alias placement of the single `settings-prompts` owner |
| Minimum / preferred | 520 x 420 px / 920 x 720 px |
| Placement | focused Advanced workspace; wide grid only; bounded large float |

This eligible instrument is the movable workspace form of Prompt editor, not a
second editor. It exposes preset selection, language, fragment-aware sheets,
save named preset, activate, import/export, and confirmed delete with the exact
same recoverable draft, revision, notices, and action leases.

States and acceptance are those of Prompt editor: Default protection, active/
selected/dirty, retained long draft, validation, saving/conflict/failure,
activation, import preview/refusal, export, and delete review. The miniature
shows synthetic sheet metadata only. Acceptance additionally proves moving the
instrument leaves one draft and the Settings route locates it rather than
mounting another copy.

---

# Widget design: Raw clothing data

**Design state:** First draft with production-write prerequisites

| Contract | Value |
|---|---|
| Type | `settings.raw-clothing-data` |
| Context / role | Explicit active story, Present frame / technical module-workspace |
| Multiplicity | Single live raw-attire owner per story |
| Minimum / preferred | 420 x 340 px / 740 x 620 px |
| Placement | focused Advanced workspace; no toolbar or phone float |

Inspect and, only when safe prerequisites exist, edit the Present-frame raw
attire JSON. It is the movable section of Raw story data and shares that exact
qualified draft/action owner. It states that save re-derives `wearing`, `state`,
and `regions`; it never implies arbitrary-frame support because the route does
not accept `frame_id`.

Production mutation requires explicit Story targeting, idle-pipeline guard,
conditional revision, staged replacement review, server-normalized result,
authoritative reload, and shared Scene refresh. Until all exist, the placed
instrument is read-only with `Open in Raw story data`; it does not call the
current unsafe write.

States cover no Story, loading/ready/redacted preview, read-only prerequisite,
dirty/device-saved once enabled, parse/schema finding, review/saving/conflict/
failure, pipeline busy, Story changed, and normalized result. Preview/catalog/
Panel persistence contains no raw clothing. Acceptance proves Present-only
truth, re-derivation, shared owner, safety gate, privacy, responsive focused
editing, and keyboard editor behavior.

---

# Shared boundary: Extension Widget host

Extensions contribute definitions dynamically; the core catalog does not
hard-code Cohesion, Campaign, Story Frame, or any other extension product.
Installed, enabled, successfully registered owner state determines availability.
The extension is trusted host code, not a sandbox: capability and permission
copy is disclosure/consent, while owner attribution, route/asset containment,
secret-safe calls, teardown, and fault retirement are enforced host boundaries.

The current `destination`, `library-type`, `play-tool`, `addon-settings`, and
legacy `view` registrations are source adapters, not sufficient Widget
manifests. A native owner-bound `registerWidget` contract (or explicit adapters
that fill every field) must provide:

| Field | Contract |
|---|---|
| Identity | owner-namespaced immutable type `ext:<owner>:<id>` and definition version |
| Presentation | localized title/description, semantic host icon, role, miniature renderer or safe host fallback |
| Context | context class, accepted selection kinds, unavailable copy, and canonical destination affinity |
| Geometry | minimum/preferred/maximum size, allowed zones, compact/full shape, and responsive modes |
| Instances | single/repeatable policy and owner-qualified instance key |
| State | extension-owned schema/version, migration, bounded host persistence declaration, and reset behavior |
| Actions | declared action ids/consequences, async busy/cancel/task ownership, and host confirmation requirements |
| Lifecycle | owner-bound mount, sync/async teardown, availability subscription, and contained fault fallback |
| Trust | manifest trust class and declared access shown before enable/update, explicitly not a sandbox |

The host validates shape/identity/geometry before catalog insertion, supplies a
fresh mount root and frozen context projection, and never grants private host
DOM helpers or arbitrary outer navigation. Calls stay within the owner's `/x/`
route; assets stay within its containment-checked `/asset/` path. Story/model
text is data, not translatable UI. Extension CSS uses owner-prefixed selectors
and public semantic tokens and must not write root tokens or host selectors;
this is a supported-code contract, not a security boundary.

Disable, remove, update, retirement, or teardown immediately destroys every
live instance, callback, task subscription, notice, listener, and asset. A
persisted Panel placement becomes a host-rendered unavailable placeholder with
`Open Add-ons` and `Remove placement`; no retired extension code executes.
Re-enable may rehydrate only after definition/schema validation. Sync/async
faults remain contained and the owner retires after the existing three-fault
threshold.

`task-provider` supplies work/state to declared Widgets but is not itself a
catalog definition. Legacy sidebar/topbar/composer hooks, notices, events, and
single commands are not automatically promoted. Existing v1 surfaces require
an explicit adapter with conservative geometry/context and no inferred
permissions; unsupported globals/global CSS remain unsupported.

---

# Widget design: Extension compact/sidebar shape

**Design state:** First draft, host-manifest prerequisite

| Contract | Value |
|---|---|
| Type | dynamic `ext:<owner>:<id>` |
| Context / role | Manifest-declared Scene, Library, Settings, or global / Module |
| Multiplicity | Manifest-declared; single by default |
| Minimum / preferred | At least 220 x 160 px / manifest within host bounds |
| Placement | toolbar only above declared minimum; narrow/medium grid; bounded float |

This shape fits a durable status/tool surface comparable to a current
`play-tool`, compact `library-type`, or explicitly adapted sidebar view. It has
one clear primary purpose, bounded controls, semantic empty/loading/error/
unavailable states, and no assumption of a permanent left sidebar.

The host supplies title, owner/trust badge disclosure, overflow (`About`,
`Locate settings`, `Remove`), focus/drag handles, and unavailable/fault chrome;
the extension renders only content. Accepted selection/context gates run before
mount. Async work registers with the task service and survives unmount rather
than living in DOM closure state.

Miniature defaults to a host-rendered icon/title/purpose/status unless the
manifest supplies a safe bounded renderer with synthetic data. Acceptance
proves geometry/reflow, one-live behavior, context loss, disable/re-enable,
teardown, three-fault retirement, theme/zoom/keyboard, and no extension code in
the catalog preview.

---

# Widget design: Extension full-workspace shape

**Design state:** First draft, host-manifest prerequisite

| Contract | Value |
|---|---|
| Type | dynamic `ext:<owner>:<id>` |
| Context / role | Manifest-declared canonical destination / Workspace-editor |
| Multiplicity | Single by default; repeatable only with qualified instance key |
| Minimum / preferred | 420 x 340 px / 760 x 620 px or validated manifest value |
| Placement | focused/wide grid; bounded large float; no toolbar |

This shape hosts a substantial contained workspace comparable to an extension
destination/legacy view. Destination affinity remains canonical: Library types
open with Library selections, Play tools with Scene, and destination/legacy
settings surfaces under Add-ons/Settings. Registration does not create a fourth
primary destination or parallel navigation architecture.

The extension may declare internal sections, recoverable draft schema, and
background tasks, but the host owns outer header, Back/focus staging, placement,
unavailable/fault treatment, and keyboard escape. Destructive actions declare
consequence metadata for host confirmation. Long drafts are owner/instance/
context qualified and migrated by definition version.

States cover no/invalid context, lazy loading, ready, clean/dirty/conflict,
background work, owner disabled/updated/removed, schema migration, contained
fault, retired placeholder, and offline.

The miniature is host-generated unless an explicitly safe synthetic renderer
is validated. Acceptance proves focused compact staging, draft survival and
migration, selection changes, action/task leases, disable/update teardown,
retired placeholder, fault isolation, theme/style contract, and accessibility.

---

# Widget design: Extension Settings shape

**Design state:** First draft, host-manifest prerequisite

| Contract | Value |
|---|---|
| Type | dynamic `ext:<owner>:<id>:settings` or declared owner-namespaced type |
| Context / role | Installed and enabled extension / Settings module-editor |
| Multiplicity | Single live settings owner per extension definition |
| Minimum / preferred | 300 x 240 px / 520 x 440 px |
| Placement | Add-ons/settings stack; medium grid; bounded float when safe |

This shape adapts `addon-settings` into the extension's own Add-ons ownership;
it never appears among host provider/content settings or creates an independent
Settings taxonomy. The Add-ons panel and placed module bind one settings draft,
save service, action leases, and server projection.

Rendering remains lazy: scanning Add-ons or opening the Catalog does not mount
every extension or trigger network calls. Disabled/retired extensions execute
no settings code. Trust/disclosure and extension version remain visible. A
dangerous or large configuration may declare `contained-only`, in which case
the Catalog offers Locate rather than drag.

States cover lazy/unmounted, loading, clean/dirty/saving/conflict/failure,
disabled, update/schema migration, owner fault/retired, and removed. Miniature
is host-generated and never reads extension settings. Acceptance proves one
owner, lazy mount, Settings scoping, disable/update teardown, migration,
contained-only disposition, failure isolation, and responsive/accessibility.

---

# Embedded design: Extension Turn Inspector renderer

**Disposition:** Supported embedded renderer; never a top-level Catalog Widget

An extension step renderer belongs inside the owning Turn Inspector step row.
Its identity is owner + exact step key + renderer version. Turn Inspector gives
it a read-only frozen stored-variant projection, extension disclosure, loading/
unavailable/fault shell, and the same frame/turn/variant context as the core
step. It cannot fetch or infer the active/latest turn instead.

The renderer may present stored output and owner-qualified actions explicitly
supported by the Inspector contract. It cannot replace core reroll/activate/
delete controls, mutate another step, reach private host DOM, or inject unsafe
HTML. Disable/retirement swaps it for a host JSON/text fallback when the stored
variant is still inspectable; historical evidence is not erased with code.

No Catalog entry, placement, miniature, multiplicity, or drag contract exists.
Acceptance proves exact stored variant, historical fallback, owner attribution,
read-only default, teardown/fault isolation, keyboard/zoom/reflow inside the
Inspector, and no unrelated top-level Widget.

---

# Extension-shape disposition register

| Current registration kind | Widget outcome |
|---|---|
| `play-tool` | compact or full shape only through explicit adapter/manifest |
| `library-type` | compact or full shape with Library context affinity |
| `destination`, legacy `view` | full-workspace shape under Add-ons/Settings affinity |
| `addon-settings` | Extension Settings shape |
| legacy `step` | embedded Turn Inspector renderer only |
| `task-provider` | service for declared Widgets; not a Widget by itself |
| legacy sidebar/topbar/composer | compatibility surface; no automatic Catalog promotion |
| `notice`, `event` | infrastructure; never Widgets |

## Coverage closeout

This first-pass design now accounts for every inventory entry without relying
on a family heading to imply an individual design:

| Coverage class | Inventory | Outcome |
|---|---:|---|
| Fixed built-in definitions | 69 | 69 individual Widget designs |
| Eligible Settings subwidgets | 23 | 22 Widget designs; 1 evidence-backed non-Widget disposition |
| Dynamic top-level extension shapes | 3 | Compact, full-workspace, and Settings contracts |
| Embedded extension shape | 1 | Turn Inspector renderer, explicitly outside the Catalog |
| **Widget design records** | — | **94 total: 69 + 22 + 3** |

The resulting mockup registry target is **91 built-in definitions** (69 fixed
plus 22 approved Settings subwidgets), with extension definitions added and
removed dynamically. Host session is not part of that registry. The three
extension shape records are templates, not hard-coded extension entries.

### Mockup translation order

The next artifact tranche should translate the contracts in dependency order:

1. shared Widget anatomy, unavailable/fault shells, owner badges, and
   stage-native exception;
2. Transcript/Composer and the current nineteen-definition migration;
3. compact Story/context/condition Widgets and their shared services;
4. Library and authoring workspaces;
5. Story-system and Settings compositions;
6. dynamic extension definition adapters and lifecycle placeholders;
7. responsive, keyboard, theme, privacy, and task/draft regression matrices.

Each translated Widget remains `First draft` until its real browser render is
compared with the canonical Atmospheric Workbench/Design Bible state at the
same viewport and its source-backed behavioral acceptance is demonstrated.
Completion of this workbook is design coverage, not implementation or visual-
review completion.

### Mechanical coverage evidence

The closeout audit parses all five fixed inventory tables and the complete
eligible-subwidget list, then requires an exact matching `Widget design` or
`Subwidget disposition` heading:

- fixed definitions: `69`, missing: `0`;
- eligible Settings subwidgets: `23`, missing: `0`;
- duplicate fixed inventory names: `0`;
- Widget design headings: `94` (69 fixed + 22 Settings + 3 extension shapes);
- non-Widget candidate dispositions: `1` (`Host session`);
- embedded extension dispositions: `1` (`Extension Turn Inspector renderer`).

The final repository checks also require valid relative links, no placeholder
markers, no trailing whitespace, and a clean Markdown diff check for the files
tracked before this workbook was created.
