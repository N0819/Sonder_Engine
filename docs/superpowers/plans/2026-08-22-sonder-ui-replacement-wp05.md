# Sonder UI replacement WP-05: Story Tools implementation plan

> Execute this plan in an isolated worktree from `interface`. Follow TDD for
> every behavioral task. WP-05 is intentionally decomposed into independently
> gateable tranches; G3 closes only after all five tranches pass together.

**Goal:** replace every current-story contextual surface with module-owned,
story- and frame-safe Story Tools on desktop and mobile, keep conditions
available without covering reading or composing, and integrate backdrop,
weather, ambience, chime, and media state without reviving classic controls.

**Program authority:**

- `docs/superpowers/specs/2026-08-21-sonder-ui-full-replacement-design.md`
- `docs/guides/INTERFACE.md`
- `docs/guides/PIPELINE.md`
- `docs/guides/DATABASE.md`
- `docs/design/sonder-ui-replacement/REQUIREMENTS_TRACEABILITY.md`
- `docs/design/sonder-ui-replacement/CANDIDATE_SALVAGE_LEDGER.md`
- `docs/design/sonder-ui-bible/docs/13_COMPONENT_CONTRACTS.md`
- `docs/design/sonder-ui-bible/docs/14_PLAY_WORKSPACE.md`
- `docs/design/sonder-ui-bible/docs/18_RESPONSIVE_AND_MOBILE.md`
- `docs/design/sonder-ui-bible/docs/21_MOTION_SOUND_AND_FEEDBACK.md`

**Current integration head:** `21cddb14431a1046dcc089148cf2fc864874d439`

**Candidate disposition:** adapt the candidate inspector's three-zone geometry,
pin/resize intent, focus-return behavior, and mobile staged presentation. Rebuild
the hosting contract, all tool mounts, all reads/writes, route/history ownership,
media lifetime, and responsive condition treatment. Reject classic ids,
`window.S`, synthetic clicks, hidden duplicate controls, DOM-owned authority,
polling, prompt/confirm dialogs, global busy state, and the candidate rule that
removes vitals on mobile.

## Responsibility boundaries

| Concern | Owner after WP-05 | Explicitly not owned here |
|---|---|---|
| Story Tool registry and route | `story-tools-registry.js` and replacement router | classic tab/modal ids |
| Tool request, draft, save, and media lifetime | `story-tools-runtime.js` | tool DOM or selected inspector node |
| Desktop inspector/mobile sheet presentation | `inspector-host.js`, `story-tools-view.js`, Story Tool CSS | squeezed desktop columns on mobile |
| Cast/current-story state | Cast tool over current chat/position/color routes | reusable character-card authoring (WP-07) |
| World/style/dialogue/attire | explicit-save Story Tools over current routes | parallel fiction authority or turn history |
| Conditions | current vitals/survival projection | inferred diagnosis or client simulation |
| Frames and guests | current frame/persona/invite routes and server guards | auth/entry replacement (WP-10) |
| Backdrop/weather | current turn/backdrop response and fixed stage layers | image generation or weather rules in JS |
| Ambience/chime | current ambience/oneshot routes plus browser media state | credential/provider configuration (WP-08) |
| Turn details | existing lazy Play pipeline surface, linked contextually | duplicate raw-output authority |

## Tranche A — Story Tool platform and inspector lifecycle

**Files:**

- Add `tests/test_ui_story_tools_contracts.py`
- Add `browser_tests/test_ui_story_tools.py`
- Add `static/js/ui-next/story-tools-registry.js`
- Add `static/js/ui-next/story-tools-runtime.js`
- Add `static/js/ui-next/story-tools-view.js`
- Add `static/css/ui/story-tools.css`
- Modify replacement bootstrap, router, shell, inspector host, HTML, CSS, and
  localization catalogs

1. Write failing contracts for the supported tool ids, a complete `wp05.1`
   release graph, a story/frame-owned runtime coordinator, and the absence of
   classic globals, ids, polling, synthetic clicks, browser prompts, arbitrary
   HTML, and hidden duplicate controls.
2. Define stable routes as `#/play/story-tools?tool=<id>&chat=<id>` with useful
   fallback when the story or tool disappears. The route names a stable tool;
   the transient mobile sheet remains a history layer so Back closes it first.
3. Replace inspector placeholder copy with a real mount contract. Desktop owns
   open, replace, pin, three bounded sizes, collapse, close, and focus return.
   Compact/medium layouts own a full-screen staged sheet with Back/Close and
   safe-area padding; mobile pinning means favorites, never a permanent column.
4. Keep tool selection, reasonable width, pinned/favorite state, and the
   last-safe subview in versioned browser-local state. Do not persist secret,
   story, model, or raw-output text in those records.
5. Make tool loads superseding and owner-checked by story, frame, tool, and
   request sequence. A late response cannot repaint another story. Tool teardown
   aborts only its own reads; it cannot stop a Play run, clear a Play draft, or
   reset transcript scroll.
6. Prove desktop resize/pin/replace/close, mobile Back/Escape/focus, refresh,
   invalid routes, story A/B switching, active generation, draft, scroll, and
   turn-selection preservation.
7. Run focused platform tests and commit `feat(ui): add Story Tool platform`.

## Tranche B — Cast, conditions, frames, and multiplayer

**Files:**

- Add Story Tool modules under `static/js/ui-next/story-tools/`
- Extend Story Tool runtime/view/CSS and focused browser/source tests
- Add narrowly required server tests only when an existing response contract
  needs to be pinned or safely projected

1. Cast shows current-story membership, active/dormant state, dialogue color,
   and current frame location from authoritative chat/position responses.
   Existing attach/remove/position/color operations keep server guards and use
   explicit verbs; reusable card editing remains Library authoring.
2. Conditions renders player and optional NPC vitals using names, values,
   labels, and non-color markers from `/api/chats/{id}/vitals`. Loading,
   disabled, untracked, unavailable, and confirmed-empty states remain distinct.
3. Conditions use a measured reservation or staged tool surface. At every
   supported width, zoom equivalent, text scale, and short height, conditions,
   utility controls, transcript, and composer have zero continuous overlap.
   Mobile retains the same information and actions in Story Tools.
4. Frames lists/selects/creates supported frames and persona stationing through
   current routes. Switching frame invalidates only frame-owned tool data and
   restores the correct Play draft/transcript owner.
5. Multiplayer/guest administration lists participants and grants, creates and
   revokes invites with server-owned authority, shows host/permission failures
   in context, and never exposes join secrets outside the guarded result.
6. Keep private history, promotion, deep memory, lore authoring, and reusable
   cards in later owning packages unless already required by an exact current-
   story workflow.
7. Prove desktop/mobile parity, keyboard operation, stale refusal, host/guest
   authorization states, and story/frame changes; commit
   `feat(ui): replace live story state tools`.

## Tranche C — World, Style, Dialogue, and Attire

**Files:**

- Add the four tool modules under `static/js/ui-next/story-tools/`
- Extend runtime, save-policy consumers, localization, CSS, and tests

1. World presents a readable summary of rooms, placements, entities, and
   conditions from the authoritative world response, with the complete current
   JSON editor available under Advanced for parity. It never invents a second
   normalized world model.
2. Style preserves every current style-guide, story-language, survival, and
   player-authority field owned by the current story. Host UI language stays a
   Settings concern and must never be rewritten by a story save.
3. Dialogue preserves every current dialogue/background/living-world field and
   numeric constraint. Labels explain story consequences in plain language;
   invalid values block the write and stay associated with their fields.
4. Attire presents current participants and region/garment structure while
   preserving the complete route payload. It writes only through the existing
   attire endpoint and never derives or commits story changes client-side.
5. All four are explicit-save long-form/structural tools. Owner-scoped local
   drafts survive close, navigation, refresh, and failed save until accepted or
   explicitly discarded. Stale responses and conflicts preserve user work.
6. Prove complete field/payload parity against current responses, Japanese
   chrome with story data excluded from translation, keyboard/mobile staged
   forms, validation, retry/export recovery, and no silent autosave; commit
   `feat(ui): replace story author controls`.

## Tranche D — Backdrops, weather, ambience, chime, and effects

**Files:**

- Add atmosphere/media modules under `static/js/ui-next/story-tools/`
- Extend Play runtime/view, Story Tools, foundation effects policy, HTML/CSS,
  localization, and browser/source tests

1. Put backdrop imagery in fixed central-stage layers behind the transcript.
   Resolve/generate only through current turn endpoints. Loading, absent,
   disabled, ready, and error states are explicit; changing or removing a
   backdrop preserves identical prose line breaks and composer geometry.
2. Render weather from the server backdrop payload behind interactive UI.
   Reduced motion stops continuous movement before first paint; effects Off
   removes decorative overlays while permitting a static content backdrop.
   Hidden tabs stop animation/compositing work.
3. Keep ambience media lifetime in the runtime, not the inspector DOM. Resolve,
   reroll/change, pin/clear, library/search, and one-shot actions use current
   routes. A user gesture unlocks audio; story/frame changes retire mismatched
   media without leaking it into the new owner.
4. Add the composer-adjacent instrument cluster with immediate Mute and bounded
   Volume; Change, Chime, pins, source detail, and advanced controls remain one
   level deeper when space is limited. It never overlaps input or Send.
5. Completion chime is optional, independently muted, and fires only for the
   current runtime-owned completion/watch event. UI interaction sounds remain
   off. Media errors never block a turn or become toast-only work.
6. Link unavailable provider/source configuration to the correct Settings
   section without moving credentials into Story Tools.
7. Prove backdrop line-wrap invariance, compact/landscape geometry, reduced/
   off effects, visibility pausing, audio unlock/mute/volume/change, story
   switching, active generation, reroll, offline/error recovery, and zero idle
   polling; commit `feat(ui): integrate Play atmosphere and sound`.

## Tranche E — G3 parity evidence and integration

**Files:**

- Add `tools/capture_ui_story_tools.py`
- Add `docs/design/sonder-ui-replacement/G3_STORY_TOOLS_REVIEW.md`
- Add deterministic evidence under `docs/design/sonder-ui-replacement/g3-tools/`
- Update traceability, candidate ledger, inventories, `docs/guides/INTERFACE.md`,
  `docs/UNBUILT.md`, and control-plane tests

1. Capture desktop, expansive, medium, tablet, 390 px phone, 360 px phone,
   short landscape, short desktop, 200-percent zoom equivalent, Japanese,
   every tool, pinned/resized/replaced inspector, mobile staged navigation,
   conditions, frames/guests permission states, backdrop states, effects
   reduced/off, ambience states, active generation, story switch, offline,
   empty, and error cases.
2. Record zero horizontal page overflow, zero compact target below 44 px, zero
   continuous overlap, stable reading/composer geometry, bounded DOM/work,
   no idle requests, no page errors, no classic globals, no sensitive text,
   and exact-source screenshot/report hashes. Two complete captures must be
   byte-identical.
3. Perform and record the four required reviews: product flow, visual system,
   responsive behavior, and implementation/state preservation. Resolve every
   P0/P1 finding and record lower findings honestly.
4. Close only `PLAY-04`, `PLAY-07` through `PLAY-10`, `PLAY-13`, and `PLAY-15`
   when their implementation and desktop/mobile evidence are linked. Keep
   cross-program accessibility, theme, responsive, save, architecture, and
   verification rows open until their owning final gates.
5. Run focused Story Tool/Play/runtime/shell/localization tests, the complete
   browser suite, Python compilation, generated map/structure checks, and the
   full repository suite with an explicit Windows-safe pytest base temp.
6. Regenerate the UI inventories against the exact integrated head, preserve
   the seven known local Directive integration-test findings only in the root
   checkout, fast-forward `interface`, and retire the clean WP-05 worktree.
7. Commit the evidence and lock G3 only after every deliverable above passes.

## WP-05 exit conditions

- Every current-story tool has an honest module owner, stable route, explicit
  state model, and desktop/mobile journey.
- Inspector/tool changes preserve selected story/frame, transcript scroll,
  composer draft, active turn/run, and media state.
- Conditions remain available and non-overlapping on mobile and desktop.
- Backdrops/weather/ambience/chime cannot reflow, cover, or block Play.
- No replacement surface drives or hides a classic control.
- All G3 `PLAY-*` rows are closed with reproducible current-source evidence;
  later package rows remain open.
