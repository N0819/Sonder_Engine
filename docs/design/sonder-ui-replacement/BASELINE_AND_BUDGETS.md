# Current UI baseline and release budgets

**Baseline commit:** `c99173dd8b7544d6ef7c53e9ed837fc0f841bbcc`  
**Browser:** chromium 149.0.7827.55  
**Platform:** Windows-10-10.0.19045-SP0

All content is synthetic. No live database, credential, join code, or player
story is read. Candidate screenshots are reference material and are not part of
this current-source baseline.

## G0 qualification record

**Qualified implementation tree:** `7d4ee3c`  
**Gate result:** passed on 2026-08-21

GNU Make is not installed on the qualification host, so the maintained
Makefile targets were executed through their exact underlying Python commands.

| Gate | Exact command | Result |
|---|---|---|
| Focused WP-00 | `.venv\Scripts\python.exe -m pytest -q tests/test_ui_replacement_control_plane.py tests/test_ui_replacement_inventory.py tests/test_ui_baseline_recorder.py tests/test_ui_next_entry.py browser_tests/test_ui_next_entry.py --basetemp=.tmp\pytest-wp00-final --disable-warnings` | 18 passed in 3.96s |
| Compile | `.venv\Scripts\python.exe -m compileall -q <source roots printed by tools/project_check.py --source-roots>` | passed |
| Map | `.venv\Scripts\python.exe tools/generate_code_map.py` | generated `docs/CODE_MAP.md` |
| Structure | `.venv\Scripts\python.exe tools/project_check.py` | passed |
| Full regression | `.venv\Scripts\python.exe -m pytest -q -n auto --basetemp=.tmp\pytest-full-final-3 --disable-warnings` | 8,740 passed, 4 platform skips, 0 failures/errors in 204.32s |
| Full browser | `.venv\Scripts\python.exe -m pytest -q browser_tests --basetemp=.tmp\pytest-browser-final-3 --disable-warnings` | 51 passed in 64.40s |
| Inventory determinism | generator run twice with the recorded baseline/candidate SHAs and SHA-256 comparison | all 8 generated artifacts byte-identical |

Failures found while qualifying G0 were treated as blockers and retained here
rather than hidden by the final green run:

- Structure first rejected a stale English catalog, package-relative paths in
  the byte-for-byte vendored Bible, and historical candidate paths presented as
  current paths. The scaffold copy was reduced to existing catalog language;
  vendored/history paths are now classified explicitly.
- The first full run produced 16 failures and 336 teardown errors (8,723
  passes); the next produced 16 failures and 165 teardown errors (8,724
  passes). Windows exposed unowned startup, request-worker, migration, and
  direct-stream SQLite handles. Production shutdown now tracks/drains these
  handles, and direct-route tests own their producer threads.
- The remaining 16 assertions were Windows test portability defects: implicit
  cp1252 reads of UTF-8 source/catalogs, a CRLF-sensitive JavaScript harness,
  and deletion of Git read-only object files. Their platform-neutral forms
  passed individually.
- The next full run passed every assertion but reported 11 teardown errors.
  These were direct route tests with no ASGI stream consumer, startup-message
  tests launching unrelated maintenance, and an intentionally failed migration
  retaining its standalone connection. Each owner was made explicit before the
  final clean run.
- Browser collection initially reported three package-import errors after the
  new isolated-entry test made `browser_tests` a package. Relative imports fixed
  all three. One later assertion sampled a transient disabled button after its
  instantaneous mock had already rerendered; it now captures the click state in
  the same browser task. The final browser run is clean.

## Captured journeys

| Journey | Viewport | Screenshot | SHA-256 |
|---|---:|---|---|
| `extensions` | 1440×900 | `desktop_extensions.png` | `9ffefb8f58b08537bad25a1051d8678a2309d28a81e316c7dc001bab5f6486bf` |
| `guest-join` | 390×844 | `mobile_guest_join.png` | `692531609a69309b7767323e315a3ea149f692dc27004d1594c93b14cb0a3b61` |
| `library-scale` | 1440×900 | `desktop_library_scale.png` | `b886fadc803f72d37063b7927e2984f18aedf930c39543c6e9f40e413742c1e1` |
| `login` | 390×844 | `mobile_login.png` | `f05598b4e14afc4ab1813ba3f55cb58b7aaa3c5b5f259e1f118586ee4c505d30` |
| `new-story` | 390×844 | `mobile_new_story.png` | `8bd8b8f586c2366081d3f7f3cc09bc6a0617738f53588a1baf02668dcc05cead` |
| `play-500` | 1440×900 | `desktop_500_turns.png` | `92cb41d8902baf57a4bf13534b99c189d6e2c0bb694a7341d6e2c683a041e56b` |
| `play-empty` | 1440×900 | `desktop_empty_play.png` | `359f18f7c3b6fe3386e3d2d356d0285e432ee5031714a4fa44cd49fb57afea68` |
| `play-landscape` | 844×390 | `mobile_landscape_play.png` | `2fe8033fb5c803cf0be61cc985219856b20778518d93a254f6aade1fb7131811` |
| `play-mobile` | 390×844 | `mobile_play.png` | `d6124a69ebb5beaece0e962d4dfb3d6c8542b26800fcd6c6e2e06dfeec22144f` |
| `play-narrow` | 360×640 | `mobile_narrow_play.png` | `d2e05a4395d53d004ca9202d50cca226d6c231e819cae0fe7de9d03987b2d7aa` |
| `play-populated` | 1440×900 | `desktop_play.png` | `55d447d5f0e7886b68357433d5a28ef1f9a2211b0a29dd3db7b4d6e6a2b4f988` |
| `play-tablet` | 1024×768 | `tablet_play.png` | `828e850983836920d707e6c3b6e95e24a9bf47cee2db1a63ce7e1167cad95059` |
| `settings` | 1440×900 | `desktop_settings_appearance.png` | `83ae1f31e43a65afa87f296218c590723d5261a744831d179f29bbc3da896e7a` |
| `settings-short` | 1280×640 | `short_settings_appearance.png` | `e6ef7f6b838dfb1d41c212f039051fd6babc0865345bf0e85422011455e69f76` |

## Measurements

Times are milliseconds. Boot, 500-turn transcript, and 1,000-story list use
three fresh pages; frame cadence uses 60 animation frames; navigation growth
records each of 50 story switches; idle traffic observes two seconds after the
page settles.

| Metric | Median | p95 | Runs/samples |
|---|---:|---:|---:|
| `boot_interactive_ms` | 110.01 | 111.59 | 3 |
| `effects_frame_ms` | 16.7 | 16.7 | 60 |
| `idle_api_requests` | 0.0 | 0.0 | 1 |
| `library_1000_render_ms` | 359.52 | 368.88 | 3 |
| `navigation_dom_growth` | 37.0 | 37.0 | 50 |
| `transcript_500_render_ms` | 164.41 | 165.61 | 3 |

## Observed current limitations

- `play-landscape`: story selection did not settle at 844x390; chat request count 0, selected state `false`, visible title `No story selected`, opened dialog ``.

## Release ceilings

| Budget | Ceiling |
|---|---:|
| `boot_interactive_p95_ms` | 133.91 |
| `effects_frame_p95_ms` | 20.04 |
| `idle_api_requests` | 0 |
| `library_1000_render_p95_ms` | 442.66 |
| `navigation_dom_growth_after_50` | 45 |
| `replacement_long_task_ms` | 200 |
| `transcript_500_render_p95_ms` | 198.73 |

Boot, long transcript, large Library, and effects ceilings are the conservative
current p95 plus 20 percent. Any tighter number would make normal measurement
noise fail the replacement before it changes behavior. The replacement permits
zero steady-state API polling while idle, at most the recorded/buffered DOM
growth after 50 navigation cycles, and no replacement-attributable long task
above 200 ms. Supported viewport/zoom evidence must show no continuous overlap,
clipping, horizontal page overflow, hidden essential action, or mobile
capability deletion.

A budget can be exceeded only through an explicit evidence-backed deviation in
the traceability matrix; historical candidate measurements cannot waive it.
