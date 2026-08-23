# Alpha 9.8 UI Parity Design

**Status:** approved

**Date:** 2026-08-22

**Target branch:** `interface`

**Upstream baseline:** `alpha9.8` / `2ac1d162fe69b23c9b7bdbcc6a8efa8e6231c979`

## Purpose

Bring the completed replacement interface from its alpha 9.7.1 engine base to
full alpha 9.8 player- and author-facing parity. The work ports every new 9.8
UI capability into the replacement module graph while retaining the existing
engine implementation and the deletion of the classic frontend.

This is a UI and frontend integration task. It is not permission to redesign
the engine or create new backend architecture.

## Authority and reference order

The implementation follows these authorities together:

1. Current alpha 9.8 source, routes, schemas, persistence, and tests own
   behavior.
2. `AGENTS.md` and maintained guides own integration, security, localization,
   async lifetime, extension, testing, and repository rules.
3. The supplied screenshot archive, identified by SHA-256
   `299ad1fbb7edd60255f2cd2bf160e43479fc382a355be9218f60308983d94fe0`,
   owns covered composition and geometry.
4. The supplied candidate implementation, identified by SHA-256
   `52a1ef6c1bbf46f30cc54c1e0d1c3f576635cda81434d048e09d3e9a8a120dc3`,
   is the preferred visual porting source where the salvage ledger permits it.
5. The Sonder UI Design Bible explains how the approved composition extends
   to new alpha 9.8 states and viewports.

The New Story, Library, Settings, dialog, and mobile screenshots are the
nearest visual references for this work. No current replacement screenshot
may substitute for them during visual review.

## Scope boundary

### Frontend work in scope

- replacement modules under `static/js/ui-next/`;
- replacement component and surface styles under `static/css/ui/`;
- the replacement HTML entry and coordinated release identifier;
- English and Japanese interface catalogs generated from replacement source;
- frontend contract tests, browser journeys, responsive screenshots, and
  review evidence;
- maintained UI guidance, traceability, and generated maps affected by the
  frontend change.

### Backend handling in scope

- merge the complete alpha 9.8 release ancestry;
- resolve merge conflicts so released 9.8 behavior and existing interface
  authentication, cache, Library, deletion, localization, and extension
  contracts all survive;
- run affected released backend tests without weakening or reinterpreting
  them.

### Backend work out of scope

- new API endpoints or server services;
- schema or persistence changes;
- new simulation, Charter, history-routing, or deletion semantics;
- changes to prompts, agent behavior, world mechanics, or model orchestration;
- refactoring backend architecture for frontend convenience.

If the released alpha 9.8 endpoints cannot support a required workflow, work
stops with a concrete compatibility report. The frontend must not silently
invent server authority or broaden this scope.

## Integration strategy

Merge `origin/main` into an isolated branch created from `interface`. Preserve
the classic frontend deletions when resolving modify/delete conflicts. Treat
the alpha 9.8 classic UI changes as a capability inventory and behavior
reference, never as files to restore.

Conflict resolution in `web/app.py` preserves the replacement root route,
authentication, no-store document policy, immutable versioned assets, Library
routers, and Library lifecycle cleanup while accepting the released alpha 9.8
routes and deletion boundary. Generated files and catalogs are rebuilt from
their post-merge sources rather than manually combining generated conflicts.

The replacement module graph uses one coordinated alpha 9.8 release identifier
across HTML, module imports, module declarations, and the server cache policy.
Mixed cached releases continue to fail before services start.

## Frontend architecture

### Shared lived-location module

A focused replacement module owns the reusable lived-location presentation and
request construction used by all four entry seams:

- New Story;
- Character Quick Start;
- Lore-to-location generation;
- current-Story simulation and institution tools.

It normalizes the author-controlled fields supported by alpha 9.8:

- enabled state;
- location brief;
- history horizon of 0, 168, or 720 hours;
- bounded `active_tail_hours`;
- `generate_history`;
- per-character route mode and optional guidance;
- selected lore and story-owned lore provenance where applicable.

The module produces request data only. It does not store a second Charter
registry or infer server truth. Runtime owners perform the requests through the
existing owner-bound API client and reject stale results.

### New Story

The approved three-route, three-step New Story composition remains intact.
Lived-location preparation is progressive disclosure within the existing flow,
not a fourth route or a new dashboard.

- Describe a Story and Use My Library configure lived-location preparation in
  the material step after cast and lore are known.
- Start Blank exposes the same optional preparation without forcing AI or
  existing Library material.
- Selected and generated characters receive independent history-route choices:
  automatic, resident, moving institution, visitor, generated journey,
  authored only, or no generated past.
- Optional guidance explains eras, places, relationships, duties, habits, or
  canon to emphasize.
- More than 16 full characters blocks lived-location creation with the released
  plain-language limit while leaving ordinary Story creation available.
- Review states summarize the selected location history and character routes,
  including model-cost implications, before creation.

The creation sequence remains explicit:

1. prepare reusable Persona and Character assets;
2. create the Story;
3. attach Persona, cast, and lore;
4. generate and pre-simulate the lived location;
5. enter Play only after every required operation succeeds.

If a post-creation step fails, the frontend deletes that exact incomplete Story
through the released deletion route. The setup draft and prepared reusable
assets remain available for retry. A cleanup failure is shown explicitly with
the surviving Story identity and a route to Library; the UI never claims a
failed cleanup succeeded.

### Character Quick Start

Quick Start remains an integrated section of the Character editor. It gains:

- Persona and greeting selection;
- optional lore selection;
- the existing name-recognition choice in plain language;
- optional lived-location preparation;
- the featured Character's history-route choice and guidance;
- clear explanation that public card details may shape the location, private
  material enters only the bounded history handoff, and Charter stops speaking
  or deciding for the Character after handoff.

The released `/api/characters/{id}/start` route remains the sole creation
authority. Failure stays in the editor with the user's choices intact.

### Lore-to-location generation

The selected Lore detail receives a contextual `Create lived location` action
when a current Story exists. The action lives in Library's existing contextual
inspector on desktop and staged detail sheet on mobile.

The flow:

- refuses Lore owned by a different Story;
- refuses generation into a historical/future frame and explains how to return
  to the present;
- identifies the selected Lore as the generation source;
- uses the shared lived-location control and released generation route;
- returns to the same Lore detail after success;
- reports the generated place, room count, and institution count without
  patching a parallel local registry.

### Dialogue Story Tool and institutions

The Dialogue Story Tool is the canonical home for story-scoped simulation
reach and Charter inspection. It keeps its existing right-inspector placement
on desktop and Back-owned full-screen sheet on compact layouts.

The tool presents:

- dialogue pacing and NPC autonomy;
- off-screen-life ceiling and maximum actors;
- world clocks and aftermath using the revised alpha 9.8 terminology;
- the unconditional witnessing, telling, and carrying rule as explanatory
  text, not a setting;
- institution summaries with people, posts, upkeep, markets, obligations,
  orders, local judgments, and simulated hours;
- the deterministic-ceiling clamp when institutions cannot run;
- character history-route summaries, confidence, author lock, reasoning,
  guidance, and handoff result;
- `Generate a lived-in location from lore`;
- warnings and empty states;
- plain-language diagnostics with full ledgers behind disclosure.

Settings retains its searchable living-world entry and updated alpha 9.8 copy,
but it does not become a second owner of Charter state. It points users toward
the canonical current-Story tool for institution generation and inspection.

## Visual and interaction contract

The new controls extend existing replacement compositions rather than
introducing a new visual language.

- New Story remains the approved centered editorial modal.
- Quick Start remains an integrated action cluster in the Character editor.
- Lore generation remains contextual Library work.
- Charter remains contextual Story Tool work.
- Compact rows, hairline separators, restrained disclosures, and shared
  controls replace generic card grids and dashboard tiles.
- Local reviewed SVG icons replace emoji and text-glyph icons.
- Geometry uses the Design Bible's 3-5 px radii, spacing scale, typography,
  semantic colors, and named z-index bands.
- Ordinary compact touch targets remain at least 44 px.
- Accent color identifies focus, selection, action, and state; it does not
  become surface decoration.
- Story names, Character names, Lore, generated history, and raw diagnostics
  remain untranslated user/model data.

Every essential desktop action exists on mobile. Contextual desktop inspectors
become staged sheets rather than squeezed columns. No capability is hover-only,
and no mobile overflow menu becomes a dumping ground for the primary action.

## Async, state, and error behavior

Every request captures Story, frame, record/tool, mount, and request identity
as applicable. Navigation, selection changes, and remounts cannot retarget a
late result.

The UI distinguishes:

- loading;
- background generation;
- unavailable provider or permission;
- confirmed empty state;
- validation warning;
- recoverable failure;
- cleanup failure;
- success.

Persistent tasks and failures remain inline. Toasts acknowledge completed
actions only. Destructive cleanup identifies the exact Story and is never
automatically retried. Credentials and private Character material never enter
general application state, notices, diagnostics, URLs, or local presentation
storage.

## Localization and accessibility

All new interface copy enters the generated catalog in the implementation task
that creates it. English and Japanese catalogs are merged/generated, never
replaced by upstream classic catalogs. Long Japanese content is included in
the responsive evidence.

Controls use native labels, descriptions, status regions, disclosure state,
focus containment, and focus restoration. Generation progress does not create
a noisy token-stream live region. Warnings and success are never color-only.
Keyboard, pointer, and touch can complete every workflow.

## Test-first implementation

Each behavior begins with a focused failing frontend contract or real-browser
test that names the regression it catches. Required coverage includes:

- exact lived-location payloads and per-character identity mapping;
- every New Story route, review state, retry, exact cleanup, and cleanup
  failure;
- Character Quick Start payload, explanatory boundary, and retained choices on
  failure;
- Lore action availability, cross-Story refusal, present-frame refusal,
  generation, and return-to-detail behavior;
- institution loading, confirmed empty, warning, clamp, populated summary,
  diagnostics, history routes, generation, and stale-response rejection;
- Settings terminology and canonical-tool link;
- keyboard, focus, touch, mobile staging, 200-percent zoom, long localization,
  themes, solid surfaces, high contrast, reduced motion, and Accessibility
  Mode.

Backend verification runs the alpha 9.8 tests affected by merge conflicts and
frontend requests without changing their contracts. Full repository and
browser gates follow focused green cycles.

## Visual evidence

Real browser renders are compared side by side with the supplied references at
the same viewports. At minimum, the evidence covers:

- New Story at 1440 x 900 and compact phone widths;
- Library Lore detail at desktop, tablet, and phone;
- Dialogue/Charter Story Tool at desktop, tablet, phone, landscape, and short
  height;
- Settings terminology at desktop and phone;
- populated, loading, empty, warning, generation, validation, and failure
  states;
- default and Accessibility Mode, plus long Japanese copy.

New Charter states are recorded as Design Bible extensions of the closest
approved composition. Any deliberate difference requires the change-control
record demanded by the Bible; implementation convenience is not a deviation
reason.

## Completion criteria

The work is complete only when:

- `interface` contains the complete alpha 9.8 ancestry;
- no deleted classic frontend file is restored or loaded;
- every alpha 9.8 player/author UI capability has a replacement owner;
- no backend architecture was added or redesigned;
- partial Story setup cannot silently strand an invisible Story;
- desktop and mobile capability parity is proven;
- generated catalogs, code map, structure, and maintained UI guidance match
  the implementation;
- focused tests, affected backend tests, full browser tests, and repository
  gates pass at the exact final commit;
- side-by-side visual review records no unapproved P0 or P1 finding;
- the completed commits are merged onto `interface`.
