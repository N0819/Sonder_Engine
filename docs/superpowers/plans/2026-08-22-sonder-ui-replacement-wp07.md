# Sonder UI replacement WP-07: Library authoring program plan

> Execute in the isolated `codex/ui-wp07` worktree from accepted WP-06 head
> `2bc02a9`. Follow red-green-refactor for every behavior change. WP-07 is too
> broad for one source tranche, so this document is the checked program map;
> each subplan below receives its own focused tests, review, and commit cycle.

**Goal:** move every supported Story, Character, Persona, and Lore management
workflow out of classic dialogs and into coherent, routed Library authoring
surfaces without losing fields, drafts, associations, archive semantics, or
engine-owned transaction boundaries.

**Program authority:**

- `docs/superpowers/specs/2026-08-21-sonder-ui-full-replacement-design.md`
- `docs/guides/INTERFACE.md`, `docs/guides/DATABASE.md`, and
  `docs/guides/TESTING.md`
- `docs/design/sonder-ui-replacement/REQUIREMENTS_TRACEABILITY.md`
- `docs/design/sonder-ui-replacement/CAPABILITY_LEDGER.md`
- `docs/design/sonder-ui-replacement/CANDIDATE_SALVAGE_LEDGER.md`
- UI Bible chapters 04, 05, 13, 15, 18, 19, 20, 21, 22, and 25
- current server routes and persistence code, which outrank historical UI

**Candidate disposition:** use the candidate only for restrained editor
hierarchy, ledger-to-editor staging, and plain-language authoring cues already
approved in the salvage ledger. Reject its `window.S` state, classic-control
clicks, hidden dialogs, bootstrap ownership, polling, DOM observers, and broad
file replacement. The replacement reads and writes current server documents.

## Audited boundary and plan double-check

The following checks were performed before source edits:

| Contract | Current authority | Plan coverage |
|---|---|---|
| Library discovery, association truth, archive/restore, delete distinction | WP-06 `web/library.py` and `library-runtime.js` | Extended, never duplicated |
| Story rename/scenario/persona, export/import, branch, archive/delete | chat, archive, turn-branch, and WP-06 routes | Subplan A |
| Character fields, greetings, generation/fill/recovery, import/export, story card override | `story/character_schema.py`, `static/js/editors.js`, character and chat-card routes | Subplan B |
| Persona fields, generation/fill, import/export, primary/additional association rules | persona and chat-persona routes | Subplan B |
| Lore hierarchy, entries, links, generation plan/recovery/apply, reinterpretation, import/export | lore routes, `mind/memory.py`, `static/js/lorebooks.js` | Subplan C |
| Drafts, save state, stale writes, conflicts, validation, retry/copy recovery, leave protection | WP-02 local state and save policy | Shared substrate in A; exercised by B/C |
| Rename, duplicate, import, export, archive, detach, delete, promotion where supported | current route inventory | A-D action-parity matrix; no invented story clone |
| Desktop editor pane and compact full-screen staged editor | WP-03 shell and WP-06 detail staging | Every subplan |
| Remaining `LIB-08`–`LIB-10`, `LIB-12`, `LIB-14`–`LIB-16` | requirements traceability | Closed only in D after combined proof |

The route audit found no safe generic `GET` authoring endpoint or optimistic
concurrency token for Character and Persona. Existing `PUT` handlers replace
whole sheets. Subplan A therefore adds a narrow authenticated authoring
projection and content-derived revision checks while leaving old callers
compatible when they omit an expected revision. It does not add a parallel
database, timestamps, or browser-owned record authority.

The action audit also found that Story supports branch-from-turn rather than
an arbitrary duplicate operation. The new UI labels that real behavior as
Branch and does not counterfeit Duplicate. Character, Persona, and reusable
Lore duplication will use exact server-side copies with fresh resource UIDs.

## Shared invariants for all subplans

1. The server document is authoritative. Browser-local drafts are bounded
   recovery material, not a second saved record.
2. Every edit owner is `kind:id`; create/import owners use a nonce and never
   collide with an existing item.
3. A write captures kind, id, route, request sequence, and expected revision.
   A late response cannot repaint, clear, or overwrite another owner.
4. `409` is a visible conflict. The local draft remains available for retry,
   copy/export, or explicit reload; it is never silently merged.
5. Small name/summary metadata may autosave after a short delay only when the
   domain operation is low risk. Whole structured documents and all generated,
   relationship, import, attach/detach, archive, and destructive changes use
   an explicit verb.
6. A valid accepted save clears its matching draft only after the returned
   revision and normalized document are installed.
7. Validation is local for immediate guidance and server-authoritative at
   commit. Invalid drafts survive navigation and trigger leave protection.
8. Structured forms carry every unpresented field forward. An Advanced JSON
   disclosure edits the complete document and is round-tripped in tests.
9. No user/story prose is localized or rendered as HTML. All interface copy
   is cataloged in English and Japanese in the same tranche.
10. Compact layouts retain every action, use at least 44 px targets, keep
    labels visible above the virtual keyboard, and return to the exact prior
    Library query/scroll/selection context.

## Subplan A — Authoring substrate and Story workspace

**Owned capabilities:** story overview/management; shared authoring routing,
load/save/draft/conflict/leave/import state; Library-home recents, favorites,
and drafts; recent-use/recent-edit sorting where underlying authority permits.

**Primary files:**

- Add `web/library_authoring.py`
- Add `static/js/ui-next/library-authoring-runtime.js`
- Add `static/js/ui-next/library-authoring-view.js`
- Add `static/js/ui-next/library-editors/story.js`
- Add `static/css/ui/library-authoring.css`
- Add `tests/test_library_authoring.py`
- Add `tests/test_ui_library_authoring_contracts.py`
- Add `browser_tests/test_ui_library_authoring.py`
- Modify `web/app.py`, `web/library.py`, Library runtime/view, router/release
  graph, HTML/CSS entry, language catalogs, database/interface guides, and
  focused control-plane tests

**Execution tasks:**

1. Write failing server tests for stable canonical revisions, bounded Story
   authoring projection, overview associations/activity/unresolved references,
   optional expected-revision compatibility, 409 conflict payloads, and exact
   Story rename/scenario/persona round trips. Reuse the current chat mutation,
   archive, import/export, and branch authorities.
2. Write failing runtime tests for `view|edit|create|import` Library modes,
   owner-scoped request cancellation, stale-response rejection, versioned local
   drafts, accepted-save clearing, conflict/failure preservation, retry,
   portable draft copy, and `beforeunload`/route leave protection.
3. Implement `library_authoring.py` as a presentation/revision seam. Revisions
   are SHA-256 over canonical domain documents and are compared inside the
   existing domain write transaction. Do not expose turns, private memory,
   credentials, raw model output, or unrelated world state.
4. Implement the shared authoring runtime using the WP-02 API/local-state/save
   services. Add bounded draft metadata to the versioned local envelope and
   derive visible Library draft badges/home groups from that local state only.
5. Replace Story detail with Overview/Edit actions. Show connected cast,
   primary/additional Personas, lore, recent activity, dormant/disabled state,
   and missing/unresolved references. Provide explicit rename/scenario/player
   Persona save, export, archive/delete, and branch-at-turn entry. Import uses
   the current portable archive route and reports validation errors inline.
6. Add server-backed `recently_used` and `recently_edited` sorts only for kinds
   with defensible timestamps/activity. The UI explains unavailable ordering
   rather than inventing values for records without that authority.
7. Prove desktop split-pane and compact staged editing, keyboard and Back
   behavior, 44 px targets, draft restoration, conflicts, offline/failure,
   import errors, invalid fields, and Japanese long copy.
8. Review and commit Subplan A before starting Character/Persona work.

**Subplan A exit:** Story overview and every currently supported Story
management operation have native routes; shared drafts/conflicts/leave
protection work under behavioral tests; no Story data or Library context is
lost across save, failure, Back, refresh, or stale responses.

## Subplan B — Character and Persona authoring

**Owned capabilities:** complete reusable Character and Persona editors,
exact duplication, create/import/export/generate/fill/recovery, story-card
override editing, warnings, and association-aware action placement.

**Primary files:**

- Add `static/js/ui-next/library-editors/character-persona.js`
- Add schema-driven form helpers under `static/js/ui-next/library-editors/`
- Add `tests/test_library_character_persona_authoring.py`
- Add `tests/test_ui_character_persona_editor_contracts.py`
- Add `browser_tests/test_ui_character_persona_editor.py`
- Modify `web/library_authoring.py`, domain routes, authoring runtime/view,
  catalogs, CSS, guides, traceability, and inventories

**Execution tasks:**

1. Generate a machine-readable field-path fixture from normalized Character
   and Persona documents plus hostile unknown extension fields. First prove
   that open/edit/save, open/raw/save, import/export, duplicate, and generated
   preview acceptance preserve every untouched path byte-for-semantic-byte.
2. Add authenticated Character/Persona authoring reads and optional revision
   checks to current writes. Add exact duplicate operations with fresh IDs,
   resource UIDs, and truthful source provenance. Never copy story runtime
   state or memberships.
3. Build sectioned forms for every currently presented classic field:
   identity/pronouns/aliases; outfit regions; simulation; embodiment/senses,
   visible body, scent, latent capabilities, extra parts and interoception;
   Character psychology, social voice/stances, competence, knowledge, initial
   state, greetings, and opening; Persona description/embodiment/outfit.
4. Carry unpresented nested fields structurally and provide a complete
   validated Advanced JSON editor. Clearing an owned list/path is deliberate;
   untouched fields are never reconstructed from defaults.
5. Integrate Character generation, psychology fill, appearance fill, greeting
   generation/recovery, and quick-start handoff as explicit background tasks.
   A preview writes nothing until accepted. Interrupted/failed generation
   leaves the prior draft and exposes Retry/Discard.
6. Integrate Persona generation and appearance fill with the same preview
   contract. Keep primary Persona replacement and additional Persona
   association semantics distinct and idle-guarded.
7. Prove warnings, validation, conflict resolution, failed saves, 200,000-char
   draft bounds, keyboard/mobile operation, import errors, and complete
   English/Japanese copy. Compare saved normalized documents against the
   original field-path fixture after every journey.
8. Review and commit Subplan B independently.

**Subplan B exit:** no Character or Persona field silently changes merely by
opening and saving; every classic capability has a native action; generated and
imported work survives interruption/failure; compact and desktop editors have
action parity.

## Subplan C — Lore workspace and recovery

**Owned capabilities:** reusable and story-owned Lore hierarchy, book and
entry authoring, relationships, generation planning/application/recovery,
reinterpretation, create/import/export/duplicate/promote/demote/move/reorder,
and association context.

**Primary files:**

- Add `static/js/ui-next/library-editors/lore.js`
- Add `tests/test_library_lore_authoring.py`
- Add `tests/test_ui_lore_editor_contracts.py`
- Add `browser_tests/test_ui_lore_editor.py`
- Modify `web/library_authoring.py`, lore routes, authoring runtime/view,
  catalogs, CSS, guides, traceability, and inventories

**Execution tasks:**

1. Write failing complete-book fixtures for nested reusable and story-owned
   books, inherited/isolated/reference-only modes, all entry fields, aliases,
   locations, importance, scope, relations, source notes, links, disabled/canon
   associations, retired books, and an interrupted generation job.
2. Add revision checks to book, entry, and relationship writes without
   weakening their current validation or transaction boundaries. Add exact
   reusable-tree duplication with fresh book/entry/link UIDs and no story
   attachment side effects.
3. Build a routed Lore tree with keyboard navigation, retained selection,
   book metadata editor, entry ledger/editor, relationship editor, and
   Advanced JSON disclosures. Story-owned origin/canon/attachment status stays
   visible and uses plain language.
4. Integrate move/reorder/promote/demote/create/delete, import/export,
   reinterpretation, direct generation, plan generation, resume/discard, and
   apply-plan through their existing routes. Long tasks live beyond a mounted
   editor and return only to the captured book owner.
5. Preserve drafts separately per book, entry, relationship, and generation
   brief. Conflict or failure never clears them. Destructive confirmation
   names whether one entry, one book subtree, or a story copy is affected.
6. Prove full-field round trips, link integrity, hierarchy ordering, generation
   interruption/resume/discard, disabled/canon handling, search, empty/error/
   permission states, compact staging, touch/keyboard, and localization.
7. Review and commit Subplan C independently.

**Subplan C exit:** every old Lore workspace action has a native routed home;
hierarchy, entries, relationships, and recovery survive all tested edits with
no field or association loss.

## Subplan D — WP-07 action parity, evidence, and Gate G4 contribution

**Owned capabilities:** cross-family action consistency, Library-home authoring
state, final WP-07 visual/state review, evidence, traceability, and integration.

**Primary files:**

- Add `tools/capture_ui_library_authoring.py`
- Add `docs/design/sonder-ui-replacement/WP07_LIBRARY_AUTHORING_REVIEW.md`
- Add deterministic evidence under
  `docs/design/sonder-ui-replacement/g4/authoring/`
- Modify traceability, capability/surface/API/global/DOM/icon/candidate
  inventories, `docs/guides/INTERFACE.md`, `docs/guides/DATABASE.md`,
  `docs/UNBUILT.md`, release graph, and control-plane allowlists

**Execution tasks:**

1. Execute an action matrix for each kind: Open/Edit, New, Duplicate where
   supported, Import, Export, Generate where supported, Attach/Detach where
   supported, Archive/Restore, Delete, and promotion/branch semantics where
   supported. Record deliberate domain differences in plain language.
2. Capture Library home, Story overview/editor, Character, Persona, Lore tree,
   entry/link/generation editors, drafts, saving/saved/conflict/failure,
   import/validation/permission errors, destructive confirmations, empty and
   scale states across expansive, wide, medium, tablet, 430/390/360 phones,
   short landscape/desktop, 200-percent equivalent, Japanese, reduced motion,
   high contrast, and keyboard journeys.
3. Record zero page/editor horizontal overflow, zero compact target below
   44 px, stable save/status geometry, bounded DOM/work, no page/console
   errors, no classic globals/dialogs, no sensitive text, and exact source/
   report/screenshot hashes. Two complete captures must be byte-identical.
4. Perform product-flow, visual-system, responsive, and implementation/state-
   preservation reviews. Resolve every P0/P1 and record lower findings.
5. Close only fully proved rows. `LIB-08`–`LIB-10`, `LIB-12`, and
   `LIB-14`–`LIB-16` should close here if their matrices pass; cross-product
   SAVE, responsive, accessibility, theme, and Gate G4 rows remain open for
   their later owners.
6. Run focused server/source/browser tests after each family, then the complete
   browser suite, catalog extraction/parity, Python compile, generated map and
   structure checks, and full repository suite with a Windows-safe base temp.
7. Regenerate inventories on the exact qualified source, fast-forward
   `interface`, verify the integrated head from a clean source view, and retire
   only the clean WP-07 worktree.

## WP-07 exit conditions

- Every supported asset-management dialog has a replacement route and no new
  surface drives or observes classic DOM.
- Field-completeness fixtures show no silent Character, Persona, Story, Lore,
  entry, relationship, or unknown-extension data loss.
- Long drafts survive route changes, refresh, conflicts, validation failures,
  offline writes, and interrupted generation.
- Import/export and exact duplicate flows round-trip current supported records
  without carrying IDs, memberships, runtime state, or stale revisions.
- Desktop and compact authoring expose the same capabilities and return to the
  exact prior Library context.
- WP-07 evidence is reproducible and remains honest that G4 also requires
  Settings, New Story, authentication, and guest surfaces from WP-08–WP-11.
