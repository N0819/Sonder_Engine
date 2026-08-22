# WP-13 cutover review

WP-13 makes the reviewed replacement the only production host UI. The root
route serves `static/ui-next.html` behind the existing host-session check. The
former `/ui-next` product route and classic host entry, global scripts, styles,
dialogs, polling bridges, and hidden-control paths are removed. The
authenticated component and runtime fixtures remain at `/ui-next/lab` and
`/ui-next/runtime`; neither is a fallback product shell.

## Cutover disposition

- `web/app.py` owns the authenticated `/` entry and no longer exposes a second
  product route.
- Play, pipeline inspection, Story Tools, Library authoring, Settings, themes,
  authentication, guest play, and extension UI are owned by native modules
  under `static/js/ui-next/` and semantic styles under `static/css/ui/`.
- The v1 extension adapter remains explicit at
  `static/js/ui-next/extensions-v1.js`; the general `window.S` host bridge is
  not restored.
- Legacy theme choices remain data mapped onto the semantic theme system. No
  classic theme sheet is loaded.
- Existing API, persistence, authentication, guest, archive, checkpoint, and
  extension-runtime contracts are unchanged. This package changes frontend
  ownership and entry routing only.

## Deletion and migration evidence

The cutover contract test verifies that the classic entry, scripts, and styles
do not exist, the production entry imports only the replacement graph, the
root route serves it, and no product `/ui-next` route remains. Former
classic-source assertions were either migrated to their replacement owner or
removed where an existing replacement browser/contract suite already proves
the behavior.

The remaining classic capabilities were migrated before deletion:

- readable per-perceiver pipeline lenses, specialist ownership, engine notes,
  concurrency/cost evidence, reasoning, and raw JSON live in
  `pipeline-inspector.js`;
- narrator exemplar, provider fallback, prompt-cache, living-world, and affect
  habituation controls live in `settings-view.js`;
- local ambience browsing and pinning live in `story-tools/ambience.js`;
- server-authored player-authority labels live in `story-tools/style.js`;
- robust dialogue attribution and quoted-region coloring live in `prose.js`.

## Verification

The focused cutover, route, migrated-capability, documentation-hygiene, and
JavaScript syntax gate passed 95 tests. The replacement Play, atmosphere,
Settings, Library-authoring, shell, auth/guest, and extension browser matrix
passed 137 tests. `tools/project_check.py` passed after regenerating the code
map, inventories, and English/Japanese production catalogs. The full Python
suite passed **8,705 tests with 4 platform skips** in 426.39 seconds. WP-14
remains the final exact-release qualification and does not reopen a legacy
fallback.

## Rollback boundary

Cutover adds no database migration. Before release, rollback is the scoped Git
revert of WP-13, restoring the prior root entry and classic files together.
The released product has no runtime selector or supported fallback shell.
