# Gate G3 Play-core review

**UI source:** `d08b1ac1932a34a3e97a2086c3778e253cadbd14`
**UI tree SHA-256:** `185024c36abb3b714db6505e90cb662989eb8eb33ab734982467e2d4f7be4243`
**Evidence:** [deterministic Play report](g3/play-report.json), [screenshots](g3/screenshots/), [browser contracts](../../../browser_tests/test_ui_play.py), [source contracts](../../../tests/test_ui_play_contracts.py), [WP-04 plan](../../superpowers/plans/2026-08-22-sonder-ui-replacement-wp04.md)
**Scope:** selected-story loading and switching, transcript and composer, generation/stop/retry, story-owned drafts, reroll, narration variants, current story/turn actions, and responsive Play states. Story Tools, conditions, backdrops, ambience, and lifecycle-wide Library actions remain WP-05 through WP-07.

## Decision

The Play-core tranche of Gate G3 is accepted. G3 as a whole remains open for
WP-05 Story Tools, conditions, backdrops, ambience, and their state-preservation
contracts. `/ui-next` now opens a real current
story, renders its frame-filtered transcript through a reviewed text-only
boundary, keeps browser-local drafts isolated by story and frame, streams new
turns without retaining token history, and refreshes authoritative server
truth at completion. The runtime captures story, frame, and run identity, so a
late load cannot replace a newer selection and Stop cannot target the story the
reader navigated to afterward.

The latest turn exposes Edit, Reroll, Versions, and More on desktop and mobile.
More owns narration edit, branch, current pipeline details, and guarded latest-
turn deletion. Story actions own rename and the existing portable archive
export. This package does not invent a New Story action or a distinct archived-
story flag; those remain with New Story and Library lifecycle packages.

## Product-flow and state review

No-story, loading, empty transcript, offline story, recoverable generation
failure, fatal malformed story, running, stopping, and ready states are named
separately. Empty input deliberately means continue; whitespace-only input is
rejected as likely accidental. A draft is cleared only after the server accepts
the request, remains present on a pre-acceptance failure, and never crosses its
`chat-{id}:frame-{id}` owner.

Generation progress keeps the friendly phase, elapsed time, and Stop together.
Bounded raw event detail stays under Advanced and token events are not retained.
An early narration preview is provisional and is replaced by the refreshed
turn. Retry is offered only before the server accepted the write, preventing a
completed turn from being replayed by the client.

Reroll uses the current streaming endpoint and explains that server-owned world
state, memories, and lorebooks return to the start-of-turn checkpoint. The
browser never reconstructs checkpoint state. Narration variants load lazily,
select through the current endpoint, and support labeled previous/next controls
plus guarded arrow navigation.

## Visual, responsive, and accessibility review

The transcript and composer share one stable reading measure. Story chrome and
the desktop inspector do not change prose geometry. Unknown or malformed HTML
remains literal; approved emphasis is rebuilt from nodes, and speech color is
applied only to exact attributed quotations. Story names, player input, prose,
and raw technical data are marked outside localization while interface copy,
including dialogs created after boot, is translated.

The 18-case matrix covers no story, desktop, medium, tablet, 390 and 360 px
phones, short landscape, short desktop, a 200-percent-zoom equivalent, 500
turns, Japanese, scrollback, versions, reroll warning, turn details, story
actions, recoverable generation failure, and offline story. Every case has zero
horizontal page overflow. Every compact case has zero visible target below 44
by 44 CSS pixels. Phone and short-landscape layouts retain Edit, Reroll,
Versions, More, the active field, Send/Retry, and bottom navigation.

Native dialogs provide containment, Escape behavior, and focus placement. The
reroll confirmation focuses the explicit Reroll action; dialog labels and
destructive text are exposed through native semantics. The transcript is the
only story scroll region. A reader at the active turn stays pinned, while a
reader at scroll position 900 remains there and gets the New turn affordance.

## Performance, security, and integration review

The 500-turn case rendered all 500 identities in 5,637 DOM nodes under the
recorded 198.73 ms ceiling. `content-visibility` and intrinsic sizing avoid
paying full paint cost for old turns. The NDJSON transport can discard token
history while still delivering host-processed `turn:*` extension events.

No capture exposes the classic `window.S` global. All cases report no
credential-, API-key-, join-code-, cookie-, or session-shaped text and no page
error. The two expected console errors are the deliberately aborted network
requests used to prove recoverable generation and offline-story presentation;
both stay in context with preserved work and a visible recovery action.

Current route shapes are used for story read/rename/export, new turn, abort,
reroll, narration variants, input/prose edits, pipeline detail, branch, and
delete. No engine, checkpoint, persistence, or information-firewall behavior
was duplicated in the client.

## Historical candidate disposition

The historical candidate at
`73a380a0df2f6b139c98d66da9005489bd549d1d` remained reference input. No
candidate file was copied wholesale.

| Candidate idea | Disposition in WP-04 |
|---|---|
| Sequence-guarded story loading and run ownership | Retained as behavior; rebuilt in one runtime-owned coordinator with explicit story/frame identity and stale-result refusal. |
| Literary transcript, safe emphasis, and speaker tint | Retained as presentation intent; rebuilt with created nodes, exact-quote attribution, a stable measure, and no arbitrary HTML. |
| Friendly pipeline progress and early narration | Retained; rebuilt as bounded task state and provisional narration replaced by authoritative refresh. |
| Latest-turn reroll and versions | Retained as workflow intent; delegated to current checkpoint and narration endpoints with explicit confirmation and keyboard/touch access. |
| Candidate globals, DOM-owned busy state, polling, hidden controls, prompts, and synthetic clicks | Rejected. The replacement uses imported services, explicit store slices, native dialogs, and visible real controls. |
| Candidate whole-transcript replacement as application authority | Rejected. Server story data remains authoritative; view remounts do not own runs or drafts. |

## Findings resolved during review

| Finding | Resolution |
|---|---|
| The turn More menu was exposed semantically but opened under the sticky composer and could not receive a pointer click. | Turn menus now expand in transcript flow; an end-to-end browser journey executes every menu action. |
| Compact CSS hid Versions, creating mobile capability loss. | All four latest-turn actions remain visible and measured at 44 px minimum in compact cases. |
| Initial transcript population could race layout and show a false New turn affordance. | Empty-to-populated initialization is treated as pinned; only a reader already reviewing prior turns gets the affordance. |
| A turn-wide `translate=no` also suppressed action and dialog localization. | Only story/player/model data nodes opt out; dynamic controls and async dialog bodies localize at creation. |
| `${name}` replacement handled `{name}` first and left a stray dollar sign. | Dollar-prefixed variables are replaced first and have a browser regression. |
| Network and malformed story failures shared an undifferentiated unavailable surface. | Network load failure is a named offline state with retry; malformed payload is fatal; ordinary server failure remains unavailable. |
| Evidence timing and asynchronous fonts made complete capture comparison nondeterministic. | The recorder waits for fonts, the transcript-settled signal, and three paint frames, then records the fixed render ceiling plus pass/fail; consecutive reports and screenshots are byte-identical. |

## Qualification evidence

The checked-in report is SHA-256 bound to every screenshot and has SHA-256
`B634DB2E087C7E45738BC9BCB35E13AEB8349450A7462E61D322FF5BCD7BE578`.
Two consecutive complete captures produced byte-identical JSON and PNG
evidence. Chromium 149.0.7827.55 on Windows generated the record. The complete
browser suite passes 140 tests. The final repository qualification passes 8,774
tests with four expected Windows/platform skips; the focused UI qualification
passes 134 tests. Python compilation and `tools/project_check.py` also pass on
the same source.

WP-04 closes only the Play-core rows proven in the traceability matrix. G3
remains open. Story Tools, conditions, backdrops, ambience, full
theme/accessibility matrices,
Library lifecycle, New Story, auth/guest, installed-extension compatibility,
cutover, and final release qualification remain open under their owning work
packages.
