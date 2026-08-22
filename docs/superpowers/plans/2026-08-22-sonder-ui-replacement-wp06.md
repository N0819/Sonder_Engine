# Sonder UI replacement WP-06: Library discovery and associations plan

> Execute this plan in the isolated `codex/ui-wp06` worktree from the
> qualified `interface` head `c7ed352`. Follow TDD for every behavioral task.
> WP-06 is a Library data/discovery package; Gate G4 remains open until the
> WP-07 through WP-11 product surfaces pass together.

**Goal:** replace the Library placeholder with one truthful, searchable view of
Stories, Characters, Personas, and Lore; expose their real story associations;
and provide responsive selection, safe attach/detach, story open/archive/
restore/delete, and bounded undo without turning story scopes into ownership.

**Program authority:**

- `docs/superpowers/specs/2026-08-21-sonder-ui-full-replacement-design.md`
- `docs/guides/INTERFACE.md`
- `docs/guides/DATABASE.md`
- `docs/design/sonder-ui-replacement/REQUIREMENTS_TRACEABILITY.md`
- `docs/design/sonder-ui-replacement/CANDIDATE_SALVAGE_LEDGER.md`
- `docs/design/sonder-ui-bible/docs/05_INFORMATION_ARCHITECTURE.md`
- `docs/design/sonder-ui-bible/docs/13_COMPONENT_CONTRACTS.md`
- `docs/design/sonder-ui-bible/docs/15_LIBRARY.md`
- `docs/design/sonder-ui-bible/docs/18_RESPONSIVE_AND_MOBILE.md`

**Candidate disposition:** reuse only the candidate's visual notion of a
quiet ledger, restrained index/icon rows, and current-story context copy.
Reject its bootstrap-count dashboard, classic `#sidelist` filtering,
`MutationObserver`, `hostState`, synthetic classic tab selection, fake scope
counts, and direct DOM/router authority. Rebuild projection, search, scopes,
associations, lifecycle state, routes, responsive detail staging, and all
mutations against current database and HTTP contracts.

## Package boundary

| Owned by WP-06 | Deferred to its named owner |
|---|---|
| Unified Library projection, counts, scopes, search, filters, sorting, paging, selection, item summaries | Full Character, Persona, Lore, and story editors — WP-07 |
| Accurate active/dormant/prior-use character associations, primary/extra persona associations, reusable/story-owned/copied lore origins | Lore hierarchy, entry, relationship, generation, and recovery authoring — WP-07 |
| Browser-local favorites and recents; server-owned archive state | New Story and reusable record creation/generation — WP-09/WP-07 |
| Add/remove from a selected story through existing guarded routes; reversible archive/detach receipts | New persistence authority or client-side relationship rows |
| Story Open, portable Export, Archive/Restore, and explicit Delete | Story setup and import workflow — WP-09/WP-07 |
| Read-only item detail/usage summary | Long-form drafts, validation, and edit conflict UX — WP-07 |

## Tranche A — Authoritative Library projection and lifecycle state

**Files:**

- Add `web/library.py`
- Add `tests/test_library_projection.py`
- Modify `core/db.py`, `web/app.py`, `docs/guides/DATABASE.md`, and route/map
  contracts

1. Write failing database/API tests before implementation. Fixtures must cover
   two stories; active and dormant cast; one primary and one extra persona;
   unattached, single-story, and multi-story reusable records; direct and
   copied lorebook attachments; story-owned lore; an archived item; a missing
   resource referenced by a stale deep link; and at least 1,000 mixed rows.
2. Add a small `library_item_state` table keyed by stable resource kind/id for
   host-authoring lifecycle metadata. Archive is a reversible presentation/
   authoring state, never a story event and never a checkpoint rollback. Add
   fresh-schema, v32-to-v33 migration, cleanup, and fresh/migrated parity tests.
3. Add `GET /api/library` as the sole Library projection. Accept bounded
   `scope`, `story_id`, repeated/CSV type filters, query, sort, offset, limit,
   and `visibility=active|archived`. Return normalized summaries, usage counts, named
   story associations and their real state, totals/facets, and pagination.
   Never return credentials, private memory, runtime character state, raw
   model output, or full long-form sheets.
4. Define scopes on server truth: All; Current/Chosen Story; Unassigned
   reusable assets; and Used in Multiple Stories. A story scope includes its
   story row plus connected reusable records. Dormant cast remains named as
   prior/dormant use instead of disappearing. A copied story lorebook resolves
   back to its reusable origin; story-owned lore is represented only in that
   story overview and never masquerades as globally reusable.
5. Search normalized names, public summaries/descriptions/tags, lorebook
   summary/type, and association names. Sorting supports name, type, created
   date where the schema knows it, and story-use count; unsupported timestamps
   are null and never fabricated. Enforce deterministic tie-breaking and
   bounded pages.
6. Add explicit archive/restore routes with idempotent behavior and typed 404s.
   Archive never deletes or detaches. Existing resource/story delete routes
   clear orphan lifecycle metadata. Commit `feat(ui): add Library projection`.

## Tranche B — Library runtime, routes, search, and ledger

**Files:**

- Add `static/js/ui-next/library-runtime.js`
- Add `static/js/ui-next/library-view.js`
- Add `static/css/ui/library.css`
- Add `tests/test_ui_library_contracts.py`
- Add `browser_tests/test_ui_library.py`
- Modify replacement release graph, store/bootstrap, router, destinations,
  inspector host, shell markup/styles, local state, and localization catalogs

1. Write failing source and browser contracts for the `wp06.1` graph, the
   normalized item contract, stable selection routes, owner-checked requests,
   staged details, and absence of classic ids/globals/observers/click bridges,
   prompt/confirm, arbitrary HTML, polling, and unbounded list rendering.
2. Route Library as
   `#/library/<type>?scope=<scope>&story=<id>&item=<kind:id>&q=<query>&sort=<sort>&visibility=<active|archived>`.
   Canonicalize invalid types/scopes/items to the nearest useful parent with a
   visible explanation. Query, scope, type, sort, selection, and scroll survive
   refresh and Back where safe; story/item names never enter the URL.
3. Create a Library runtime owner separate from DOM. It issues one superseding
   projection request per route/query owner, rejects stale replies, keeps the
   last confirmed page during recoverable refresh, and names loading, empty
   Library, empty scope, no results, offline, error, and unavailable-item
   states separately.
4. Build the wide category/scope column plus bounded searchable ledger. At
   medium width collapse to two panes. Compact uses a full-width ledger and
   the existing history-owned full-screen detail sheet. Back returns to the
   same filters and scroll position; ordinary compact targets measure at least
   44 px.
5. Rows show icon/index, name, type when useful, concise public metadata, and
   `Not used`, one story name, or `Used in N stories`. Story data is explicitly
   excluded from translation. Use semantic selection and named state markers,
   not color alone.
6. Store only bounded favorites, recent stable ids, last safe Library route,
   and per-route scroll in versioned local state. No sheet/story content,
   association payload, secrets, raw output, or archive data enters local
   storage. Commit `feat(ui): replace Library discovery`.

## Tranche C — Associations, story lifecycle, and bounded undo

**Files:**

- Extend Library runtime/view, inspector integration, routes, notices,
  localization, and focused server/browser tests

1. Detail shows every current usage with story name and state. Character
   removal uses the existing dormant transition and says `Remove from active
   cast`; it must not claim history was erased. Persona removal distinguishes
   primary persona from an extra active participant. Lore detach identifies
   the story-owned copy while preserving its reusable origin.
2. Add-to-story and remove-from-story use the existing guarded character,
   persona, and lorebook routes. Capture the mutation's story/item identity
   before issuing it; a late result cannot mutate a newly selected item.
   Refresh from `/api/library` after acceptance instead of patching a parallel
   association model client-side.
3. Offer bounded undo only when reversal is sound: archive -> restore;
   character/persona removal -> reactivate; lore detach -> reattach its reusable
   origin. The notice receipt includes exact owner and expiry. True Delete has
   no optimistic undo and remains behind an explicit scoped confirmation.
4. Story detail exposes Open in Play, portable Export, Archive/Restore, and
   explicit Delete. Delete copy names that the complete story and its owned
   history/lore are removed while reusable Characters, Personas, and original
   Lore remain. A running story refusal remains server-owned and preserves the
   selected row.
5. Archive removes the item from ordinary projection only after the server
   accepts it. Restore works from the archived scope/detail. Favorites/recents
   never override archived or unavailable truth.
6. Prove attach/detach does not delete reusable rows, lore-copy origin
   survival, dormant honesty, primary-persona refusal, undo acceptance/expiry,
   archive persistence, deletion confirmation, story A/B stale refusal, and
   offline/failure preservation. Commit `feat(ui): add Library lifecycle`.

## Tranche D — WP-06 evidence and integration

**Files:**

- Add `tools/capture_ui_library.py`
- Add `docs/design/sonder-ui-replacement/WP06_LIBRARY_REVIEW.md`
- Add deterministic evidence under
  `docs/design/sonder-ui-replacement/g4/library/`
- Update traceability, candidate ledger, inventories, maintained interface/
  database guides, `docs/UNBUILT.md`, and control-plane tests

1. Capture All, Current Story, Choose Story, Unassigned, multi-story, each
   type, search/no-results, selected details, archived/restore, associations,
   loading, empty, unavailable, offline, and error at expansive, wide, medium,
   tablet, 430/390/360 phones, short landscape, short desktop, 200-percent
   equivalent, Japanese, reduced motion, and 1,000-row scale.
2. Record zero horizontal page overflow, zero compact target below 44 px,
   retained list context after detail Back, bounded rendered rows/work,
   deterministic query totals, no page/console errors, no classic globals,
   no sensitive text, and exact source/report/screenshot hashes. Two complete
   captures must be byte-identical.
3. Perform and record product-flow, visual-system, responsive, and
   implementation/state-preservation reviews. Resolve all P0/P1 findings and
   record lower findings honestly.
4. Close only Library requirements fully proved by WP-06. Keep long-form editor,
   complete authoring/action parity, cross-product save/accessibility/theme,
   and Gate G4 rows open for WP-07 through WP-11.
5. Run focused server/source/browser tests, the complete browser suite,
   localization catalog check, Python compile, generated map/structure checks,
   and the full repository suite using a Windows-safe pytest base temp.
6. Regenerate inventories against the exact WP-06 source head, fast-forward
   `interface`, verify the integrated head, and retire only the clean WP-06
   worktree.

## WP-06 exit conditions

- Every Library result and scope is derived from database truth, including
  dormant cast, multiplayer personas, copied lore origins, and archived state.
- Detach/archive never deletes reusable material; true deletion is explicit
  and names its scope.
- Search, filters, sort, item routes, association detail, and story lifecycle
  work with equivalent capability on desktop and compact layouts.
- Stale requests cannot replace a newer query/story/item and parent list state
  survives detail staging.
- No replacement surface drives, filters, or hides a classic Library control.
- WP-06 evidence is reproducible and honest about the still-open WP-07 editor
  and later Gate G4 work.
