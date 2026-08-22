# WP-06 Library replacement review

**UI source:** `c1efafabee972be40f277b5f23f36e138d2a1d04`

**UI tree SHA-256:** `a4ef9405e24441caa100dd00b3f9634fc78cf7808ca595c42a6db7055614522f`

**Evidence:** [deterministic 32-case report](g4/library/library-report.json), [screenshots](g4/library/screenshots/), [Library browser contracts](../../../browser_tests/test_ui_library.py), [projection/server contracts](../../../tests/test_library_projection.py), [WP-06 plan](../../superpowers/plans/2026-08-22-sonder-ui-replacement-wp06.md)

**Scope:** unified discovery, scope/type/search/sort/visibility routes, public
projection, story associations, archive/restore, safe detach/delete, bounded
undo, wide detail and compact staged detail.

## Decision

WP-06 is accepted. Library discovery and lifecycle are native replacement
surfaces backed by current database and HTTP authority. The historical
candidate supplied hierarchy and interaction references only; none of its
browser globals, DOM authority, polling, hidden-control clicks, parallel
association state, or broad file replacement was retained.

This does not close Gate G4. WP-07 still owns long-form Story, Character,
Persona, and Lore editors; remaining rename/duplicate/import parity; recent
and edited sorting; visible Library-home recents/favorites/drafts; full story
overview; and import, validation, and permission states. New Story, Settings,
auth, guest, extension compatibility, cutover, and final qualification remain
with their later work packages.

## Product-flow review

Stories, reusable Characters, Personas, and reusable Lore share one Library
destination. All, chosen-story, not-used, and multi-story scopes are filters
over the same projection. A story chooser changes the association filter; it
does not relocate or clone a reusable source. Story-owned lore remains visibly
distinct and enters only its story's projection.

Every row exposes type, public summary, and truthful use. Detail names each
story and the actual state: active/dormant Character, primary/additional
Persona, or attached/disabled/canon Lore. Character removal uses dormant state
and explicitly preserves history. Primary Personas cannot be removed here.
Lore detach targets the story copy and undo reattaches its reusable origin.

Archive and restore are reversible discovery lifecycle operations. They do not
change story membership or enter snapshots/exports. Story deletion has no
optimistic undo and uses an inline confirmation naming the complete story,
history, and story-owned lore that will be removed, while stating which
reusable sources remain. Open in Play and portable Export use their existing
routes.

The server's running-story guard now covers Character and Persona membership
changes as it already covered story/lore mutations. A refusal changes no row
and leaves the selected Library context intact.

## Visual-system review

The Library uses the accepted semantic surfaces, quiet dividers, numeric
ledger indices, field/button primitives, state markers, and contextual
inspector. Selection is marked by both surface and border, association states
have text beside the marker, and destructive confirmation is an inline scoped
decision rather than a browser prompt.

The original candidate's category rail, ledger rhythm, and detail hierarchy
were adapted. Its cosmetic ownership and legacy-control bridge were rejected.
The final UI is controlled by `library.css` and the shared shell/component
layers only.

Japanese capture translates all Library chrome, association states, and late
inspector actions while retaining story names and authored summaries in their
source language. Catalog review added every reader-visible Library string to
the replacement catalog boundary instead of documenting untranslated dynamic
DOM as an exception.

## Responsive review

The 32-case matrix covers expansive, wide, medium, tablet, 430/390/360 px
phones, short landscape, short desktop, a 200-percent-zoom equivalent,
Japanese, reduced motion, and a 1,000-item fixture. It includes every scope and
type, search and no-results, selected details, archive/restore, associations,
loading, empty, unavailable, offline, server error, compact Back restoration,
and scale.

Every case records zero horizontal page overflow, zero Library-region
horizontal overflow, zero compact target below 44 by 44 CSS pixels, zero
page/console errors, no classic `window.S`, and no sensitive text. Direct
compact item links stage the detail sheet once. Browser Back closes it and
retains the 100-row list context rather than reopening or rebuilding it.

Open-inspector wide layouts stack toolbar fields when the remaining component
space cannot carry four columns. Short landscape keeps the detail sheet
scrollable and every visible action at least 44 px. The destructive decision
uses a two-column grid so its buttons cannot overlap after target enlargement.

## Implementation and state-preservation review

`web/library.py` joins only public resource fields and real associations. It
never returns sheets, private history, runtime state, credentials, or raw
model output. The endpoint validates types/scopes, bounds query text and pages,
and returns at most 100 rows to the client; the 1,000-item evidence reports a
100-row/1,082-node ceiling.

`library-runtime.js` owns exactly one projection channel and one mutation
channel. Projection results carry canonical route identity. Mutations capture
route, item, story, and action before sending; a Story A response is stale
after selection changes to Story B even when the reusable item is the same.
Accepted writes refresh the projection rather than patching a client-owned
association model.

Undo receipts remain in memory, carry an exact inverse and owner, and expire
after twelve seconds. Only sound inverses receive one. Favorites are bounded
to 20 identities, recents to 50, and per-route scroll records to 20. Those
presentation records contain no story content, associations, lifecycle truth,
archive state, credentials, or output.

`library_item_state` is host-authoring metadata outside turn/checkpoint and
portable-export domains. True resource deletion cleans the matching metadata.
All other writes reuse guarded current routes.

## Findings resolved during review

| Finding | Resolution |
|---|---|
| Direct compact item links selected a row but did not stage its detail sheet. | The inspector now stages an initial selected Library link once; Back closes the layer without an automatic reopen. |
| Late Library detail DOM remained English under Japanese UI. | Detail remounts now pass through the localizer, and all dynamic Library copy is inside the extracted catalog boundary. |
| Compact All chips measured 33–35 px wide; short-landscape Search/Favorite measured 36.5 px high. | Library filters and every detail/toolbar action now enforce a 44 px minimum in compact layouts. |
| With the inspector open, a 1280–1440 px center column could hide visibility in Library-region horizontal overflow. | Open-inspector wide/near-expansive layouts use an available-space-safe stacked toolbar and narrower rail. |
| Enlarging destructive buttons exposed overlap between Delete and Keep. | The confirmation uses a bounded two-column grid with wrapping labels and no pointer overlap. |
| Initial evidence treated the inspector placeholder as the main result state. | Capture now measures destination result state and visible detail state separately and reports Library-region overflow independently. |
| The first full repository run rejected the newly closed Library rows because the executable qualified-gate allowlist ended at WP-05. | The control-plane test now names exactly the nine reviewed WP-06 rows; its focused run and the repeated full suite pass. |

No unresolved P0 or P1 finding remains in WP-06 scope. The intentionally open
WP-07 requirements are recorded individually in traceability rather than
being misreported as polish debt.

## Qualification evidence

The checked-in report is SHA-256 bound to every screenshot and has SHA-256
`8AEB6B29A9F6A6E66C989B1DBB53A86341261AA158210F497EDCE24768978046`.
Two consecutive complete captures produced byte-identical JSON and PNG
evidence across 33 files. Chromium 149.0.7827.55 on Windows generated the
record.

Focused qualification passes 9 Library browser tests, 7 projection/server
tests, 104 impacted/source-contract tests, and the 3-test replacement
control-plane suite. The complete browser suite passes 164 tests. The repeated
full repository suite passes 8,807 tests with four platform-specific skips;
the first pass had 8,806 passes plus the stale allowlist failure recorded
above. Catalog extraction covers 2,292 English source messages with complete
Japanese key parity. Python compilation and generated map/structure checks
pass on the isolated source.

WP-06 closes `LIB-01` through `LIB-07`, `LIB-11`, and `LIB-13`. `LIB-08`
through `LIB-10`, `LIB-12`, and `LIB-14` through `LIB-16` remain open with
specific WP-07 ownership. Gate G4 and the full replacement remain open.
