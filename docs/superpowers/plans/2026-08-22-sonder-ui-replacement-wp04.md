# Sonder UI replacement WP-04: Play core implementation plan

> Execute this plan in an isolated worktree from `interface`. Follow TDD for
> every behavioral task. WP-04 replaces the Play workflow inside `/ui-next`;
> it does not bridge to, hide, or synthetically drive the classic host.

**Goal:** make `/ui-next` a dependable place to select and read a story,
compose and preserve story-owned drafts, run and stop generation, recover from
failures, reroll with the engine's checkpoint authority, browse narration
variants, and use essential turn actions across the supported viewport matrix.

**Program authority:**

- `docs/superpowers/specs/2026-08-21-sonder-ui-full-replacement-design.md`
- `docs/guides/INTERFACE.md`
- `docs/guides/PIPELINE.md`
- `docs/guides/DATABASE.md`
- `docs/design/sonder-ui-replacement/REQUIREMENTS_TRACEABILITY.md`
- `docs/design/sonder-ui-replacement/CANDIDATE_SALVAGE_LEDGER.md`
- `docs/design/sonder-ui-bible/docs/14_PLAY_WORKSPACE.md`
- `docs/design/sonder-ui-bible/docs/18_RESPONSIVE_AND_MOBILE.md`
- `docs/design/sonder-ui-bible/docs/22_UX_FLOWS_AND_EXPERT_ACCELERATION.md`

**Current integration head:** `3e3ffb7c263ce0be871649316b354e3ab3bad293`

**Candidate disposition:** adapt only the proven behavior and presentation
ideas in the candidate/current-classic `chat.js`: sequence-guarded story loads,
captured run ownership, safe prose emphasis, speaker attribution, friendly
pipeline phases, early narration preview, latest-turn reroll rules, narration
variant selection, and checkpoint-restore warning. Rebuild all of it as native
ES modules over the WP-02 runtime. Reject `window.S`, classic ids, global busy
state, hidden classic controls, synthetic clicks, whole-transcript replacement
on every state change, DOM-owned authority, polling, browser prompts, and
candidate stylesheet/HTML copying.

## Responsibility boundaries

| Concern | Owner after WP-04 | Explicitly not owned here |
|---|---|---|
| Story route/load/run lifetime | `static/js/ui-next/play-runtime.js` | classic globals or DOM nodes |
| Play presentation | `static/js/ui-next/play-view.js` and `static/css/ui/play.css` | Story Tool implementations |
| Prose and speaker rendering | `static/js/ui-next/prose.js` | accepting arbitrary model HTML |
| Draft durability | WP-02 local state, keyed by story and frame | server persistence or cross-story reuse |
| Generation stream | current NDJSON routes and runtime task service | client-authored outcome or rollback logic |
| Reroll/variant authority | current turn endpoints | reproducing checkpoints in JavaScript |
| Story archive | existing portable export endpoint | inventing an archived-story flag or relabeling delete |
| Story creation | WP-09 | a fake New Story action |
| Cast/World/Style/etc. | WP-05 | hidden classic modals |
| Backdrops, ambience, conditions | WP-05 | decorative overlap with prose/composer |
| Library item lifecycle | WP-06/WP-07 | broad archive/delete management in Play |

## Task 1: Pin Play contracts and candidate salvage boundaries

**Files:**

- Add `tests/test_ui_play_contracts.py`
- Add `browser_tests/test_ui_play.py`
- Extend `tests/test_ui_runtime_contracts.py`

1. Write failing source contracts for dedicated Play runtime/view/prose modules,
   one `wp04.1` release graph, story-owned routes and drafts, bounded streaming
   detail, semantic transcript/composer markup, and absence of classic globals,
   private ids, polling, mutation observers, inline layout, browser prompts,
   arbitrary model `innerHTML`, and synthetic clicks.
2. Write failing browser journeys for no-story, loading, empty transcript,
   story open/switch, A/B drafts, stale load refusal, send/stop/retry, session
   expiry, reroll warning, variants, turn actions, scrollback review, new-turn
   affordance, keyboard, touch, and short landscape.
3. Pin the 500-turn ceiling at `198.73 ms` p95, zero idle requests, no
   replacement-attributable long task above 200 ms, and no DOM growth after
   repeated story navigation.
4. Record that portable export is the WP-04 archive action. True Library
   lifecycle archive/delete distinctions remain WP-06/WP-07.
5. Run focused tests and retain the expected missing-module failures.
6. Commit `test(ui): define WP04 Play contracts`.

## Task 2: Advance one coherent replacement release

**Files:**

- Modify every `static/js/ui-next/*.js` release constant/import
- Modify replacement HTML/CSS asset queries
- Modify affected runtime, entry, browser, and source tests

1. Advance the complete replacement graph from `wp03.1` to `wp04.1` in one
   mechanical change.
2. Preserve mixed-release rejection, immutable caching, the runtime fixture,
   and classic `/` isolation.
3. Add Play modules and stylesheet to the declared release inventory before
   any production consumer imports them.
4. Commit `chore(ui): advance replacement release to WP04`.

## Task 3: Build a runtime-owned Play coordinator

**Files:**

- Add `static/js/ui-next/play-runtime.js`
- Modify `static/js/ui-next/bootstrap.js`
- Modify `static/js/ui-next/store.js`
- Modify `static/js/ui-next/api.js`
- Extend runtime/browser tests

1. Start one Play coordinator for the host runtime and keep it alive across
   destination/view remounts. It owns route-to-story loading, active story and
   frame identity, generation, refresh, retry, stop, and turn mutations.
2. Load `/api/chats/{id}` on one superseding read channel. Validate ids against
   authoritative bootstrap stories, capture owner/request identity, abort
   superseded reads, and refuse late A results after navigation to B.
3. Keep a run bound to the story/frame/turn with which it started. Navigation
   may leave the story without aborting the run; Stop targets the captured run,
   and completion refreshes only the same story if it is still current.
4. Stream NDJSON incrementally without retaining every token event. Bound
   technical detail and progress records and release readers/controllers on
   runtime teardown.
5. Model story, transcript, and composer states distinctly: unrequested,
   loading, ready, empty, running, stopping, recoverable error, session loss,
   and fatal malformed response.
6. Preserve extension `turn:*` signals through the registered extension
   boundary after host processing, without restoring a broad global bus.
7. Commit `feat(ui): add runtime-owned Play lifecycle`.

## Task 4: Render safe literary prose and stable transcript geometry

**Files:**

- Add `static/js/ui-next/prose.js`
- Add `static/js/ui-next/play-view.js`
- Add `static/css/ui/play.css`
- Modify `static/js/ui-next/destinations.js`
- Modify `static/js/ui-next/shell.js`
- Extend source/browser tests

1. Render player input, narrated prose, dialogue speaker tint, approved inline
   emphasis, stale explanation, frame membership, and pending narration using
   created text/elements only. Unknown, attributed, malformed, and unbalanced
   markup remains literal text.
2. Keep a roughly 720 px shared reading/composer measure. Story chrome,
   inspector, tasks, notices, backdrops, and progress may not change prose line
   breaks or continuously cover the story.
3. Give turns stable identities and use bounded DOM plus
   `content-visibility`/intrinsic sizing to meet the 500-turn budget without
   forcing the reader to the bottom.
4. Preserve scroll anchoring during updates. When the reader is reviewing old
   turns, a completed/new preview shows a visible “new turn” affordance; it
   never steals scroll. When already pinned, it follows the active turn.
5. Make destination mounts explicit lifecycle objects so leaving/re-entering
   Play tears down view observers/listeners but not the runtime-owned run or
   story draft.
6. Commit `feat(ui): render the literary Play transcript`.

## Task 5: Implement the story-owned composer and drafts

**Files:**

- Modify `static/js/ui-next/play-runtime.js`
- Modify `static/js/ui-next/play-view.js`
- Modify `static/js/ui-next/storage.js`
- Modify `static/css/ui/play.css`
- Extend browser/runtime tests

1. Restore and persist drafts as `story` records owned by the stable
   `chat-id:frame-id` identity. Switching stories, changing inspector state,
   navigating away, refresh, recoverable failure, and runtime remount preserve
   the right draft and never copy it into another story.
2. Explain that an empty submission means “continue” and allow it deliberately;
   distinguish whitespace-only accidental input from the explicit empty action.
3. Keep Send and Stop in one stable action slot, expose a clear stopping state,
   and preserve typed text until the server has accepted the turn request.
4. `Ctrl/Cmd+Enter` sends on desktop while plain Enter remains text entry;
   visible touch Send is always present. IME composition and textarea caret
   behavior are never intercepted.
5. Resize without per-keystroke forced layout, honor safe areas and visual
   viewport/keyboard changes, and keep active field, action, validation, and
   bottom navigation mutually usable on phones and short landscape screens.
6. Commit `feat(ui): add durable story composer`.

## Task 6: Make generation progress, stop, retry, and recovery truthful

**Files:**

- Modify `static/js/ui-next/play-runtime.js`
- Modify `static/js/ui-next/play-view.js`
- Extend task/notice integration and browser tests

1. Show a compact progress line containing friendly current phase, elapsed
   time, and Stop. Concurrent stages name their overlap without exposing raw
   step keys as the primary status.
2. Keep optional technical events behind an Advanced disclosure and bound the
   buffer. Token painting is animation-frame batched; narration preview is
   provisional and replaced by the authoritative fetched turn.
3. A recoverable request/stream failure preserves the draft, last confirmed
   transcript, story owner, and a visible Retry action. Retry reuses the
   correct operation and payload once; it cannot duplicate a completed turn.
4. Stop calls the captured story/frame abort endpoint, moves through stopping,
   handles the stream's aborted terminal event, and never targets the newly
   viewed story.
5. Session expiry requests login once and preserves browser-local draft and
   last confirmed content. Offline/malformed/fatal states remain visually and
   semantically distinct.
6. Task and notice surfaces remain compact/non-blocking in Play; a persistent
   problem is recoverable in place and an acknowledgement does not cover text.
7. Commit `feat(ui): expose truthful generation recovery`.

## Task 7: Preserve engine reroll authority and expose narration variants

**Files:**

- Modify `static/js/ui-next/play-runtime.js`
- Modify `static/js/ui-next/play-view.js`
- Extend server/browser tests around existing endpoints

1. Offer reroll only for the latest turn/frame and call the existing reroll
   route. Before the call, explain exactly that world state, memories, and
   lorebooks return to the start-of-turn checkpoint, including later manual
   edits. The client never snapshots, restores, or merges world state.
2. Load narration variants lazily for the latest turn. Selecting a variant
   paints immediately, persists through the existing narration endpoint, and
   rolls back presentation on failure.
3. Keep variant navigation discoverable with labeled previous/next buttons and
   count. Arrow shortcuts operate only outside editable/modal contexts.
4. A reroll run uses the same captured ownership, streaming, Stop, preview,
   retry, and final authoritative refresh lifecycle as Send.
5. Commit `feat(ui): preserve reroll and variant authority`.

## Task 8: Add essential story and turn actions without scope leakage

**Files:**

- Modify `static/js/ui-next/play-runtime.js`
- Modify `static/js/ui-next/play-view.js`
- Extend browser/server tests

1. Put current story identity, Rename, Export archive, and a stable More menu
   in Play. Rename uses `PUT /api/chats/{id}` and updates bootstrap/library
   projection only after accepted server truth. Export downloads the existing
   portable archive with a safe filename.
2. No-story offers truthful recent-story shortcuts and Open Library. It does
   not fake New Story before WP-09; the traceability evidence records the
   package boundary.
3. Every turn exposes Edit and More; the latest turn also exposes Reroll and
   Versions. Touch keeps Edit/Reroll/More visible. More contains Edit narration,
   Branch, Turn details, and latest-turn Delete where valid.
4. Use accessible routed/modal layers with validation, explicit confirmation,
   focus containment/return, and no browser `prompt`/`confirm`. Destructive
   actions retain server guards and refresh authoritative state.
5. Turn details fetch current pipeline data on demand and keep raw content
   behind Advanced. Editing narration remains presentation-only; other
   mutations surface the server's stale explanation instead of hiding it.
6. Commit `feat(ui): add scoped Play actions`.

## Task 9: Prove current-server and extension integration

**Files:**

- Extend `tests/test_ui_runtime_routes.py`
- Extend `tests/test_frontend_turn_signals.py`
- Extend `browser_tests/test_ui_play.py`

1. Exercise real current route shapes for bootstrap, chat payload, new turn,
   abort, narration variants, reroll, edit input/prose, pipeline details,
   branch, delete, rename, and portable export without changing server
   persistence authority.
2. Prove host auth, one-login session expiry, 403 inline behavior, malformed
   response containment, teardown cancellation, and no credential/session data
   in DOM, route, local storage, tasks, notices, or diagnostics.
3. Prove the v1 extension receives post-host turn step/token/done/aborted/error
   signals through its adapter and cannot alter Play rendering or retain a
   mount after disable/retire/teardown.
4. Keep `/`, login, guest, and their existing tests unchanged.
5. Commit `test(ui): prove current Play integration`.

## Task 10: Close responsive, accessibility, localization, and performance findings

**Files:**

- Extend `browser_tests/test_ui_play.py`
- Extend `tests/test_ui_catalog_extraction.py`
- Modify Play source/styles as findings require

1. Exercise pointer, touch, and keyboard at 360×800, 390×844, 430×932,
   768×1024, 844×390, 1024×600, 1024×768, 1280×800, 1440×900, and the
   640×360 zoom equivalent, plus long Japanese, Accessibility Mode, high
   contrast, solid surfaces, large UI/prose, reduced motion, and virtual
   keyboard geometry.
2. Verify heading/landmark order, transcript semantics, live-region restraint,
   labeled progress/actions, 44 px targets, visible focus, modal focus trap,
   no focus behind a layer, no horizontal page overflow, no hidden essential
   action, and mobile capability parity.
3. Measure 500-turn render p95, story-switch DOM growth, idle traffic, stream
   token paint cadence, and chrome/backdrop line-break stability against the
   recorded budgets.
4. Regenerate English copy and Japanese parity; model/story prose, player
   input, names, and extension data remain outside localization.
5. Conduct product-flow, visual-system, responsive, and state-preservation
   reviews. Fix every P0/P1 and record every other finding and disposition.
6. Commit `fix(ui): resolve Play core review findings`.

## Task 11: Capture deterministic WP-04 evidence

**Files:**

- Add `tools/capture_ui_play.py`
- Add generated `docs/design/sonder-ui-replacement/g3/play-report.json`
- Add generated screenshots under
  `docs/design/sonder-ui-replacement/g3/screenshots/`
- Add `docs/design/sonder-ui-replacement/G3_PLAY_REVIEW.md`

1. Capture no-story, empty story, populated desktop, 500 turns, medium, tablet,
   common/narrow phone, phone landscape, short desktop, zoom equivalent, long
   Japanese, active generation, stopped/retry, scrollback/new-turn, variants,
   reroll warning, turn details, story actions, and session expiry.
2. Record source commit/tree, browser/platform, viewport, story/run owner,
   overflow, measures, target sizes, focus, line-break hashes, render timing,
   DOM counts, requests, console/page errors, screenshot hashes, and a
   sensitive-data scan.
3. Run two complete captures and require byte-identical generated evidence.
4. Treat screenshots as presentation evidence only; behavioral gate closure
   remains executable.
5. Commit `test(ui): capture Play core evidence`.

## Task 12: Qualify WP-04 and hand G3 to Story Tools

**Files:**

- Modify `docs/design/sonder-ui-replacement/REQUIREMENTS_TRACEABILITY.md`
- Modify `docs/guides/INTERFACE.md`
- Modify `docs/UNBUILT.md` section 2.26
- Regenerate `docs/CODE_MAP.md`, catalogs, inventories, and drift

1. Add exact WP-04 evidence to applicable `IA-*`, `RESP-*`, `PLAY-*`,
   `STATE-*`, `A11Y-*`, `I18N-*`, `PERF-*`, `ARCH-*`, `SEC-*`, and `VER-*`
   rows. Close only requirements proven by Play core. Leave Story Tools,
   conditions, backdrops, ambience, Library lifecycle, New Story, auth/guest,
   compatibility, and cutover work open for their owning packages.
2. Regenerate English/Japanese catalogs, code map, structure artifacts,
   replacement inventories, and frontend drift against the integration head.
3. Run Play/runtime/source/server/browser focus, compile all maintained source
   roots, `tools/project_check.py`, full pytest, and all browser tests. Record
   the seven known root-only Directive facade-coupling findings separately.
4. Re-run deterministic evidence and inspect every capture at native size.
5. Commit `docs(ui): lock Play core`, fast-forward into `interface`, refresh
   drift to the integrated SHA, re-run focused merged verification, and remove
   the clean worktree and merged branch.

## WP-04 exit checklist

- [ ] Story selection, open, switch, rename, and portable archive export are real.
- [ ] No-story, loading, empty, ready, running, stopping, recoverable, session,
      and fatal states are distinct.
- [ ] Transcript prose, input, emphasis, speakers, stale notes, frames, and
      provisional narration render safely at literary measure.
- [ ] Story A/B drafts remain isolated through navigation, errors, and refresh.
- [ ] Send, Stop, Retry, and progress are explicit and owner-correct.
- [ ] Late story/load/run results cannot overwrite the active story.
- [ ] Reroll delegates checkpoint restoration entirely to current server logic.
- [ ] Latest-turn variants and essential turn actions work on pointer, touch,
      and keyboard.
- [ ] Scrollback review is never force-scrolled; new turns remain discoverable.
- [ ] 500-turn, idle, DOM-growth, long-task, and line-reflow budgets pass.
- [ ] No classic script/global/private id/hidden control/synthetic click/polling
      dependency exists in Play.
- [ ] WP-04 is complete; WP-05 owns Story Tools, conditions, and scene utilities.
