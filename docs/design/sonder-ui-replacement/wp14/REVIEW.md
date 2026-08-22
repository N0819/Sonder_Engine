# WP14 release qualification and adversarial audit

**Status:** complete

**Qualification date:** 2026-08-22

**Reference baseline:** `c99173dd8b7544d6ef7c53e9ed837fc0f841bbcc`

WP14 qualifies the replacement as the only host UI. It does not reinterpret
engine, persistence, authentication, guest, archive, or extension authority.
No open P0 or P1 finding remains, and no capability has an approved omission.

## Browser and input matrix

| Engine | Scope | Result |
|---|---|---:|
| Chromium 149 | Complete `browser_tests` suite | 180 passed |
| Firefox 151 | Auth, shell, Play, Library, Settings, New Story, guest, and extension journeys | 96 passed |
| WebKit 26.0 | Targeted cross-surface smoke, including safe prose | 9 passed |

The broader Windows WebKit sweep passed 84 of 96 journeys. Its twelve
remaining assertions all depended on exact emulated viewport geometry or
focus restoration after the emulated viewport was rescaled: this Windows
runtime reported a requested 390 CSS-pixel viewport as 341 pixels. The targeted
smoke avoids Chromium-specific exact-pixel assertions while retaining the
actual workflows. Firefox initially could not spawn content processes inside
the managed sandbox; the same pinned browser passed outside that sandbox.

The Chromium matrix covers continuous shell widths from narrow phone through
expansive desktop, short landscape, touch, safe-area CSS, virtual-keyboard-like
short viewports, 200-percent zoom-equivalent viewports, Japanese long copy,
keyboard-only routing and actions, Back-owned sheets, focus restoration,
destructive confirmation, streaming, offline recovery, and 500-turn history.
The role-based journeys exercise the same names, relationships, status, and
error text exposed to an accessibility tree.

## Accessibility and appearance

The foundation, shell, Play, Story Tools, Library, Settings, New Story, auth,
guest, and extension suites jointly cover:

- semantic navigation, main, complementary, dialog, form, heading, status,
  progress, and live-region ownership;
- keyboard-only navigation, activation, editing, dialog/sheet dismissal, and
  restored focus;
- 44-pixel ordinary compact targets and the larger Accessibility Mode preset;
- Carbon Signal, Ash and Brass, Midnight Ink, Parchment Night, and Legacy;
- high contrast, solid surfaces, stronger focus, reduced motion, larger UI and
  prose, roomier targets, and color-independent named states;
- untranslated story/model data beside localized English/Japanese UI copy.

This is the practical screen-reader contract for the build-free host: journeys
locate and operate controls through accessibility roles and names rather than
private selectors wherever user semantics are under test. No noisy token stream
is a live region.

## Performance

The release remains inside the WP00 ceilings through direct measurements and
bounded-structure tripwires:

| Surface | Release evidence | Ceiling / result |
|---|---|---|
| Boot and idle | shell/runtime reports; one bootstrap; runtime teardown test | no polling; no listener accumulation |
| Transcript | `test_500_turn_render_stays_inside_the_recorded_budget` | under 198.73 ms |
| Library | `scale-1000` Library report and browser contracts | 1,000 records, 100 rendered rows |
| Effects | backdrop/weather reduced-motion and effects-off cases | no continuous effect when disabled/reduced |
| Repeated navigation | runtime reboot and shell history contracts | listeners replaced, not accumulated |

The old host and its duplicate work are absent, so the release does not pay for
both implementations. No replacement-attributable long task or steady-state
API poll was observed by the qualification journeys.

Sonder's release artifact is the repository checkout launched by
`Start_Sonder.bat`/`Start_Sonder.sh`; `pyproject.toml` explicitly says the
project is not installed as a Python package. Packaging qualification therefore
checks the production root route, static replacement graph, generated source
inventories/catalogs, and absence of classic assets instead of inventing an
unsupported wheel release path.

## Extension and localization reports

WP12 proves the installed v1 adapter and native v2 facade, explicit slots,
owner-bound teardown, permissions, fault isolation, route retirement, and all
five appearance modes. `tools/project_check.py` verifies generated English and
Japanese catalogs, icon use, source structure, and the production module graph.
WP13 proves that no classic fallback host or general `window.S` bridge remains.

## Novice audit

- Destination recognition: Play, Library, and Settings are the only persistent
  primary destinations and use plain labels.
- First story: New Story offers describe, Library, and blank routes; only the
  describe route requires a provider.
- Hesitation: empty Play and Library states name useful next actions without a
  timer, forced redirect, or hidden choice.
- Misleading labels: loading, unavailable, empty, offline, saving, saved, and
  failed states remain distinct.
- Dead ends: invalid/retired deep links return to a useful parent with an
  explanation; guest and host connection failures retain work and offer retry.
- Error recovery: drafts survive recoverable Play, editor, New Story, auth, and
  guest failures where the underlying action is safe to retry.

## Expert audit

- Go To and registered shortcuts reduce destination action counts without
  firing while typing or composing with an IME.
- Recents, search, scope filters, sort choices, persistent Library/editor state,
  and pinned/resizable story tools remain available on wide screens.
- Compact density changes presentation, not data or capability.
- Frequent actions remain first-level: Send/Stop, story switching, Story Tools,
  ambience mute, New Story, search, and destination navigation are never hidden
  exclusively under More.
- Advanced prompts, raw story data, diagnostics, models, routing, and
  maintenance remain reachable without crowding Play.

## Requirements closure

The 170-row traceability matrix now links implementation and reproducible
evidence. The remaining rows closed here are grouped as follows:

- `GOV-*`: baseline, candidate-disposition, capability ledger, WP13 deletion,
  this adversarial audit, and full regression evidence.
- `IA-06`, `IA-08`, `IA-10`: router, story-tool host, Library/Settings/New Story
  routes, and cross-surface browser journeys.
- `RESP-*`: foundation, shell, Play, Story Tools, Library, authoring, Settings,
  New Story, auth, and guest viewport/keyboard/touch matrices.
- `LIB-08` through `LIB-16`: Library and authoring runtimes plus their browser
  and source contracts.
- `A11Y-*`: semantic components, accessibility preferences, form validation,
  focus, live-region, zoom, long-copy, and color-independent-state journeys.
- `SAVE-*`: save policy, request sequencing, per-owner drafts, explicit commit,
  dirty-state protection, and unload/recovery contracts.
- `VER-*`: the three-engine results above, appearance/accessibility matrices,
  regenerated catalogs/icons, performance evidence, WP13 legacy search, and
  exact-source repository gates.

The classic-interface roadmap entry is removed because the replacement and its
release qualification are now built. Historical reports remain evidence; they
are not a selectable fallback.

## Reproducible gates

```text
python -m pytest browser_tests -q --disable-warnings
python -m pytest --browser firefox <cross-surface files> -q --disable-warnings
python -m pytest --browser webkit <targeted smoke nodes> -q --disable-warnings
python -m pytest tests/test_ui_wp14_release.py -q --disable-warnings
python tools/project_check.py
python -m pytest -q --disable-warnings
```

Final candidate-tree results: project structure passed; focused integrated UI
passed 95 tests; Chromium passed 180 tests; Firefox passed 96 tests; WebKit
smoke passed 9 tests; full Python regression passed 8,709 tests with 4 expected
platform skips in 145.90 seconds. Exact-head verification follows the release
commit without changing its source tree.
