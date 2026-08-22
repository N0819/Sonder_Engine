# Gate G3 Story Tools and atmosphere review

**UI source:** `e65ff0a3517eceb9f1986901c824a2cb9fe1724f`  
**UI tree SHA-256:** `e8921be42cca1d019e8508437d6ce4c27440897d4ca8824f0e7aef917f1f3562`  
**Evidence:** [deterministic 21-case report](g3/story-tools/story-tools-report.json), [screenshots](g3/story-tools/screenshots/), [Story Tool browser contracts](../../../browser_tests/test_ui_story_tools.py), [live-state contracts](../../../browser_tests/test_ui_live_story_tools.py), [author-control contracts](../../../browser_tests/test_ui_story_author_tools.py), [atmosphere contracts](../../../browser_tests/test_ui_atmosphere_tools.py), [WP-05 plan](../../superpowers/plans/2026-08-22-sonder-ui-replacement-wp05.md)  
**Scope:** the complete current-story tool registry and hosting lifecycle; Cast, World, Style, Dialogue, Attire, Backdrops, Ambience, Conditions, Frames, and Multiplayer; runtime-owned backdrop, weather, ambience, and chime state; desktop and staged compact presentation.

## Decision

WP-05 is accepted and completes Gate G3. The replacement now owns every
current-story contextual surface without driving or hiding a classic control.
Story and frame identity remain runtime authority while each tool owns only its
current route requests and drafts. Tool navigation cannot clear the composer,
move transcript scroll, cancel a running turn, or let a late response repaint a
different story.

The historical candidate remains a reference, not an implementation base. Its
three-zone inspector geometry, resize/pin intent, focus return, and mobile
staging were adapted. Its globals, DOM authority, interval polling, hidden
controls, prompt/confirm flows, and classic click bridges were rejected.

## Product-flow review

The ten-tool registry is stable and every entry mounts a native module. Cast
owns current membership, dormant state, dialogue colour, and frame location.
Conditions names loading, disabled, untracked, empty, offline, error, and ready
states separately and exposes non-colour progress semantics. Frames owns frame
creation/switching and persona stationing. Multiplayer keeps invite creation,
revocation, permissions, and destructive detach on guarded server routes; the
one-time invite secret is never stored.

World and Attire show readable summaries while keeping the complete server
document under Advanced. Style preserves style guide, story language, survival,
and player authority without touching host UI language. Dialogue preserves the
dialogue, background, and living-world documents and blocks partial writes on
invalid numeric input. Their owner-scoped drafts survive navigation, refresh,
and failed saves until accepted or explicitly discarded.

Backdrop and ambience generation return immediately. Pending work says so and
advances only through an explicit Check status action; there is no idle or
multi-minute polling loop. Missing model/source configuration links to Settings
without bringing credentials into Story Tools. Pins use room identity and
one-shots use the existing guarded route.

## Visual-system review

The inspector uses the established semantic surfaces, spacing, typography,
badges, fields, state boxes, and 44 px compact targets. Story/model data is
marked out of localization while dynamic controls localize on mount. Japanese
captures show translated chrome around untranslated story names, garments, and
room data.

Backdrop and weather layers are absolute, non-interactive children behind the
central Play workspace. A tested ready-to-ready backdrop swap leaves transcript
and composer rectangles identical. Weather uses the server-projected condition;
Effects Off removes its decorative overlay while retaining a static backdrop,
and reduced motion removes continuous animation before capture.

Ambience Mute and bounded Volume remain composer-adjacent. Unlock, chime, pins,
reroll, layer detail, credit, and preview remain in the deeper Ambience tool.
No interaction sound was added.

## Responsive review

The 21-case record covers every tool at desktop width plus expansive, medium,
tablet, 390 px phone, 360 px phone, short landscape, short desktop, a
200-percent-zoom equivalent, Japanese, reduced-motion backdrop, and Effects Off
backdrop states. Every case reports zero horizontal overflow, zero compact
target below 44 px, zero continuous workspace overlap, a visible requested
tool, zero page/console errors, and no classic global or sensitive text.

Wide layouts keep the bounded inspector beside Play. Medium and compact layouts
use a focus-contained modal stage, so covering the inactive workspace is
recorded as `modal_staged`, not misreported as continuous overlap. Conditions
and all other tools retain the same information and actions in that stage.

## Implementation and state-preservation review

`story-tools-runtime.js` owns tool route identity and request cancellation by
story, frame, tool, mount, and sequence. Runtime media lives separately in
`atmosphere-runtime.js`: inspector teardown cannot stop it, story changes retire
its token and audio elements, page visibility pauses playback and weather work,
and only mute, volume, and chime preferences enter versioned local state.

Simultaneous desktop/sheet mounts share the atmosphere coordinator's in-flight
GET rather than duplicating work. Audio elements are created with `preload=none`
and receive no eager media request before a user unlocks audio. Completion
chime is optional, current-run-owned, and failure-isolated. Backdrop and
ambience failures never block a turn.

## Findings resolved during review

| Finding | Resolution |
|---|---|
| Desktop and staged tool mounts could ask for the same backdrop while route presentation settled. | Runtime-owned in-flight de-duplication now gives both mounts one current request and payload. |
| The compact landscape sheet Close button measured 36.5 px. | The staged inspector header now enforces a 44 px minimum; all compact capture targets pass. |
| Constructing an `Audio` element with a URL could trigger a media request before unlock. | Layers now set `preload=none` before assigning `src`; unlock changes preload and starts playback. |
| The first catalog regeneration made the Japanese pack incomplete by 33 new strings. | All new atmosphere copy has Japanese translations; application import, login journeys, and catalog checks pass. |
| Raw panel/composer rectangles treated an intentionally modal sheet as a continuous overlap. | Evidence records modal staging explicitly and separately measures continuous workspace overlap, which is zero. |
| Candidate backdrop/ambience loops waited through long interval polling. | Pending work has a visible manual status check and source/browser tripwires forbid interval polling. |

## Qualification evidence

The checked-in report is SHA-256 bound to every screenshot and has SHA-256
`46DC808AD7A4EF56FE6328009DFF343FAB46B6A438CAF4D817E6889591384C0A`.
Two consecutive complete captures produced byte-identical JSON and PNG
evidence. Chromium 149.0.7827.55 on Windows generated the record.

The focused WP-05 qualification passes 66 tests, the complete browser suite
passes 155 tests, and the full repository suite passes 8,796 tests with four
platform-specific skips. Catalog extraction covers 2,203 source messages and
`tools/project_check.py` passes on the isolated source. The server and module
graph now share the `wp05.1` release token, so versioned replacement assets
receive the cache policy their imports declare.

G3 closes `PLAY-04`, `PLAY-07` through `PLAY-10`, `PLAY-13`, and `PLAY-15` in
addition to the Play-core rows already accepted. Library lifecycle, New Story,
Settings/editors, auth/guest replacement, installed-extension compatibility,
cutover, and final release qualification remain open under their owning work
packages.
