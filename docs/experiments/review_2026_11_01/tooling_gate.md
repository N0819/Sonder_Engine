# Audit — the gate itself (`make check`, `tools/project_check.py`, CI, test infra)

Auditor: tooling/gate lane, 2026-11-01. Read-only. All Python run on `.venv/bin/python`.

**A moving tree, and how this report handles it.** `git status` was clean when I started, and I ran
`make map` (8.55 s, `docs/CODE_MAP.md` unchanged, md5 `0945394e…` before and after) and `make structure`
once each. While `make structure` was running, the orchestrator began landing the `agents/common.py` split. It
became commit `a7ea29aa`, and the `agents/composer.py` split is now in flight. So that make run's verdict is void.
It reported three errors, and all three came from the moving tree: the map, the UI catalog (`PY_FILES` was frozen
at import), and a new design doc. Its wall time still holds: **4:33, 271 s user, single-threaded**. Every other
measurement and every `path:line` below comes from a stable snapshot of **`84f3de23`**, extracted with
`git archive` into `S/gate/headtree`. After `a7ea29aa`, `tools/project_check.py` lines after 1735 shift by +1
because `"agents.common"` joined `FACADE_FAMILIES`. Scripts: `S/gate/time_checks.py`,
`S/gate/time_checks_cached.py`, `S/gate/facade_patch_probe.py`, `S/gate/assertless_probe2.py`. Raw timings:
`S/gate/check_times.out`.

## Scope read

Read in full (snapshot `84f3de23`):
- `tools/project_check.py` 1-3451 (all 36 checks, their helpers, `main`, `--source-roots`, `--write-package-edges`).
- `tools/generate_code_map.py` 1-385.
- `tools/extract_ui_catalog.py` 1-492.
- `Makefile` 1-124.
- `.github/workflows/ci.yml` 1-149.
- `pyproject.toml` 1-88, `constraints.txt`, `requirements.txt`, `requirements-dev.txt`, `requirements-browser.txt`.
- `tests/conftest.py` 1-318, `tests/helpers.py` 1-273, `tests/model_seams.py` 1-89.
- `docs/guides/TESTING.md` 1-551.
- `browser_tests/conftest.py` 1-35.

`tools/package_edges.json`: I recomputed it in full against the code and compared it programmatically, without
reading every row by eye.

Read in part, for a specific trace:
- `llm/decisions.py` 60-200 and 280-318.
- `llm/providers.py` 315-335, plus a census of every HTTP and subprocess call site.
- `tests/test_schemas.py` 217-290, `tests/test_model_seams.py` (structure), `tests/test_repo_hygiene_source_roots.py` 135-160.
- `tests/test_routines.py` 150-195, `tests/test_background_work_lifecycle.py` 60-100, `tests/test_causal_overlay_verification.py` 125-160.
- `tests/test_launcher_python_range.py` 1-30.
- `extension_runtime/__init__.py` 1420-1525, `persist/commit.py` 905-930.
- `story/room_citations.py` 90-130, `persist/llm_capture.py` 465-605, `core/jobs.py` 202-240.
- `world/charter_history.py` 735-745, `story/journey_history.py` 183-190, `story/character_schema.py` 300-312, `persist/chat_archive.py` 116-126, `llm/schemas.py` 275-310 and 405-416.
- `agents/common.py` 12899-12920.
- `tools/story_drive.py` 1-40 and 540-552.
- `Start_Sonder.sh` (install lines and candidate list).
- `docs/design/DESIGN_MODULE_LAYOUT.md` 190-215, `docs/UNBUILT_PLATFORM.md` §1.61, `docs/UNBUILT_IDENTITY.md` 25-56.

CI evidence: run `41366860777` (2026-11-02 00:23 UTC, branch `worktree-jev-character-tracking`, all green). I read
its job logs through `gh api`. The suite itself was not run (per the brief). For the suite's cost I use the
orchestrator's baseline in `S/baseline.txt`/`baseline.time`: `.venv`, `-n 6`, 19,635 passed, 281 s wall,
1,414 s user.

## Findings

### F1 — `make check` and `make run` run a stack no player has  [SILENT-NOOP, CONFIRMED]
`Makefile:1` `PYTHON ?= python`. `Makefile:34` and `:40` run bare `uvicorn web.app:app …`.

Measured on this machine:

| interpreter | Python | pydantic | numpy | pytest | xdist | fastapi |
|---|---|---|---|---|---|---|
| `python` → `/home/nathan/.local/bin/python` | 3.12.3 | **1.10.14** | **1.26.4** | **9.1.1** | **missing** | — |
| `uvicorn` → `/usr/bin/uvicorn` → `#!/usr/bin/python3` | — | **1.10.14** | 1.26.4 | — | — | **0.101.0** (below the declared floor `fastapi>=0.115.14`, `requirements.txt:22`) |
| `.venv/bin/python` (what both launchers build: `Start_Sonder.sh:45-46,335` `pip install -c constraints.txt -r requirements.txt`) | 3.12.3 | 2.11.7 | 2.2.6 | 8.4.1 | 3.8.0 | 0.115.14 |

**Scenario.** A developer runs `make check`. The verdict comes from Pydantic 1, NumPy 1 and pytest 9.1.1. Then
`test-full` finds no xdist (`Makefile:69-74`) and falls back to a serial run of a suite whose CPU cost is 1,414 s
(the orchestrator's baseline). That is roughly 23+ minutes, plus 4.5 minutes of structure, for a verdict on the wrong
stack. CLAUDE.md records two defects that lived in exactly this gap. `make run` (the "start the local server"
command in CLAUDE.md) serves the engine on FastAPI 0.101 and Pydantic 1, so a developer can watch behaviour that
no player can produce. Neither `check_python_version_agreement` nor `check_pydantic_major_reads_are_owned` (see F11)
can see any of this. The first compares 3.x version strings across four files. The second confines six field-attribute
names. Neither looks at which environment the gate runs in.

**Fix.** Concrete, and CI is unaffected because CI has no `.venv`:
```make
VENV_PYTHON := $(firstword $(wildcard .venv/bin/python .venv/Scripts/python.exe))
PYTHON ?= $(if $(VENV_PYTHON),$(VENV_PYTHON),python)
run:   ;  $(PYTHON) -m uvicorn web.app:app --host 127.0.0.1 --port 8008 --reload --reload-delay $(RELOAD_DELAY) $(SHUTDOWN)
serve: ;  $(PYTHON) -m uvicorn web.app:app --host 127.0.0.1 --port 8008 $(SHUTDOWN)
check-fast: stack compile structure test-full
check:      stack compile map structure test-full
stack: ; @$(PYTHON) tools/stack_check.py   # print interpreter + pydantic/numpy; exit 1 when a constraints.txt pin differs, unless ALLOW_UNPINNED=1
```
`check_asgi_targets` still parses `-m uvicorn web.app:app`. The `stack` guard fixes the class: the gate states which
stack its verdict is about, instead of trusting a path.

**Test.** A structure check or test that runs `make -pn` and asserts `PYTHON` resolves to `.venv/bin/python` when
`.venv` exists, plus a unit test of the `stack_check` comparison.

### F2 — The facade rule cannot see relative imports: 7 live outside-in violations  [SILENT-NOOP, CONFIRMED]
`tools/project_check.py:1666` (`facade_import_violations`) only matches `ast.ImportFrom` when `node.level == 0`.
A module in the same package that reaches a sibling with a relative import passes. Live, at `84f3de23` (from
`S/gate/facade_patch_probe.py`-style scan, with family membership from `facade_siblings`):
```
agents/character.py:5062      from .director_floors import strip_addressee_concealment
agents/character.py:5063      from .director_views import _scene_match_forms
agents/director_prose.py:70   from .director_fanout import _beat_rooms, _specialist_payload
agents/director_prose.py:71   from .director_scopes import (
agents/director_prose.py:408  from .director_evidence import (QUOTED_LINE_CARRIED, _QUOTED_SPAN,
agents/perception.py:864      from .director_evidence import beat_timeline, declared_elements
world/charter_creature.py:142 from .spatial_fov import normalize_footprint
```
`director_prose` is not re-exported by `agents/director.py`, so by the check's own membership rule it is a caller.
CLAUDE.md states that `tools/project_check.py` "enforces that for `world.spatial`, `agents.director` and
`persist.commit` alike: a caller imports the facade". For relative spellings it does not. Separately, the check
scans only engine files plus `tests/*.py` (`:1773`). `tools/` holds 39 more outside-in sibling imports (for example
`tools/bench/recall_scan_cost.py:49,78,79` and `tools/chrono_bench/run.py:303`).

This matters now: the `common`, `composer` and `perception` splits will produce many relative sibling imports.

**Fix.** Resolve `level > 0` imports to absolute names before matching (`generate_code_map.resolve_import` already
does this). Decide whether `tools/` counts as callers. If it does, the test exemption (`_module_object_uses`) applies
there too.

**Test.** `tests/test_project_check_matchers.py` shape: feed `from .director_floors import x` as `agents/character.py`
and expect one outside-in violation.

### F3 — The side-channel check reads only `agents/` and `story/`; `_extension_routing` is undeclared  [SILENT-NOOP, CONFIRMED trace / consequence PLAUSIBLE]
`tools/project_check.py:3130` `_SIDE_CHANNEL_ROOTS = ("agents", "story")`.

- **Writer.** `extension_runtime/__init__.py:1457` and `:1501` write `ctx["_extension_routing"] = entries` from the
  narration and character-payload hooks.
- **Reader.** `persist/commit.py:916`: `_routing = _extensions.routing_notes(ctx)`, then
  `results["extensions"]["routing"] = _routing`. The comment above it says this is where "an extension that rewrote
  what a mind was given names itself … so a character who knows something they should not is one read from their
  author rather than looking like an engine defect".
- **Registry.** The key is neither a `PipelineContext` field nor in `agents/runtime.py:1300` `SIDE_CHANNELS`.

**Scenario.** An extension rewrites a character's payload. The turn is then resumed, or commit or the narrator is
rerun alone. The character stage is not re-executed and nothing rehydrates `_extension_routing`, so the committed turn
silently loses the attribution record. That is the firewall-forensics record the comment describes.

Also unread anywhere: `setattr(ctx, ENGINE_NOTICES_REWRITTEN, True)` at `persist/commit_common.py:652`. This one is
in-stage and harmless, but the walker cannot see the spelling.

**Fix.** Walk `ENGINE_PACKAGE_ROOTS`. Declare `_extension_routing` in `SIDE_CHANNELS` with how it survives (rebuilt
from the persisted character variants, or "in-stage only", in which case commit must say so).

**Test.** Add the root widening to the existing `test_repo_hygiene` test. Add a runtime test that reruns from the
narrator with an extension routing note and asserts the commit keeps it, or states that it does not.

### F4 — Model and network doors no sealer covers; two door lists; no autouse floor  [SILENT-NOOP, CONFIRMED code / impact PLAUSIBLE]

Two lists of the same fact, which already disagree:
- `tests/helpers.py:112-116` `MODEL_SEAMS` has 3 doors (`_agent_json`, `complete_validated_json`, `chat_complete`).
  It sweeps 9 packages (`_SEAM_PACKAGES`, `:120`) and matches only the same attribute name.
- `tests/model_seams.py:38-44` `MODEL_DOORS` has 5 doors (adding `embed_texts` and `embed_texts_meta`). It sweeps
  8 packages (`_ENGINE_ROOTS`, `:48-49`, **without `dressing`**) and matches any alias.

So `forbid_model_calls` leaves both embedding doors open.

Neither list covers:
- `llm/decisions.py:144-148`: `_post` → `_http().post(...)`, which is `providers._session()`.
- `llm/providers.py:4846`: `chat_complete_async`.
- `:2283` and `:2322`: `generate_image` and `edit_image` (called by `dressing/backdrops.py:1667,1680`).
- `llm/research_providers.py:169,204,231`.
- `list_models` (`:5236`).

`llm/decisions.py` arrived on 2026-09-22 (`62a188a7`), after both lists. `tests/model_seams.py:25-27` says that
"forgetting to [add a door] is the one way this can go quiet", and that is what happened.

`docs/guides/TESTING.md:413-419` says `model_seams.py` "seals every provider door". It does not.

No autouse fixture refuses an outbound connection. The suite stays offline only because a fresh scratch DB has no
provider row (`decisions.decide` raises at `llm/decisions.py:295-296` without a keyed OpenRouter row). I found no live test that
reaches an unsealed door: `tests/test_decision_model_setting.py:101,142` stubs `decisions._http`, and the other
tests that configure a provider drive no Director stage.

**Fix.** One door list: delete `MODEL_SEAMS` and make `forbid_model_calls` delegate to `seal_model_seams`. Add
`("llm.decisions", "_post")`, `chat_complete_async`, `generate_image`, `edit_image` and the research fetch to it.
Use `ENGINE_PACKAGE_ROOTS` for the sweep. Then add the floor that does not depend on the list. In `tests/conftest.py`,
an autouse fixture patches `socket.socket.connect`/`connect_ex` (and `socket.getaddrinfo` for non-local names) to
raise `AssertionError("test reached the network: host:port")` for anything other than loopback or `AF_UNIX`, with a
registered opt-out marker `network`. That covers requests, httpx, urllib and any door added later.

**Test.** `tests/test_model_seams.py` parametrised over the new doors. Add a test that `socket.create_connection(("192.0.2.1", 443))`
raises inside a plain test.

### F5 — The schema-reachability test is satisfied by prose; three schema classes are dead  [DEAD, CONFIRMED]
`tests/test_schemas.py:250-261` seeds reachability by running a regex over the raw text of every `*.py` under the
repo root: tests, tools, comments, docstrings, and English words. I recomputed it with seeds taken only from engine
modules' AST identifiers (Name, Attribute, alias, or a string constant equal to the class name). 104 of 110 classes
stay reachable. Six are reachable only through text. Three of those six are deliberately kept as test fixtures
(`llm/schemas.py:2031-2032` names `CausalRegime`, `FictionFrame` and `SpeechElement`). The other three are dead:
- `PlayerAuthorityMode` (`llm/schemas.py:407`). Named only in a comment (`agents/director.py:2563`) and a docstring
  (`agents/common.py:8901`).
- `BehaviorController` (`:412`). Named only in comments: `world/offscreen.py:159`, `story/scene.py:2217,2220`,
  `tools/fire_rates.py:5`.
- `Engagement` (`:2072`, a `LenientModel`). Kept alive by the English word "Engagement" at `mind/affect.py:1178`
  ("Engagement revives a set-aside goal…") and `persist/commit_background.py:4819`.

The test's own docstring says a model nothing references "states a shape the engine does not enforce". That is these
three.

**Fix.** Seed from engine-module AST identifiers only, with an explicit `KEPT_AS_TEST_FIXTURES` set for the three
named in the comment. Then delete the three dead classes, or give them a real reader.

**Test.** The rewritten test, which fails until those three are resolved.

### F6 — The contextvar check covers 2 modules of 9; the per-test reset covers 11 vars of 24  [SILENT-NOOP gate, CONFIRMED / scope leak PLAUSIBLE]
`tools/project_check.py:2543` scans only `llm/providers.py` and `core/pipeline_context.py`. These ContextVars are
never examined:
- `core/db.py:18` `active_frame_id`
- `llm/llm_quality.py:683` `answered_by`
- `world/charter_runtime.py:685` `_REGISTRY_SESSION`
- `story/room_citations.py:91` `_rows_read`: a mutable set. `enter_reading()` at `:115` sets it "for the rest of
  this context, with no close".
- `persist/llm_capture.py:469` `_room_scope`: `enter_room_capture()` at `:602` sets it with no reset.
- `extension_runtime/api.py:30` `_COMMIT_SCOPE`
- `language_runtime/__init__.py:69` `current_language_id` (inherited deliberately)

`core/jobs.py:202-237` `_clear_turn_scoped_context` clears none of them. Its docstring claims an audit on 2026-08-19
found no other live survivor; four of these vars postdate that audit (`_rows_read` and `_room_scope` 2026-09-05, `_REGISTRY_SESSION` 2026-09-07, `answered_by` 2026-10-10). If a Room reply worker that armed `_rows_read`
or `_room_scope` calls `jobs.submit` (for example the Dramaturge, `agents/story_planner.py:2240`, or the bible,
`story/room_bible.py:447`), the job gets the reply's citation set object and capture scope. I did not trace whether
those submits happen inside such a worker.

`tests/conftest.py:291-318` `_fresh_provider_context` resets only `vars(llm.providers)`. The leak it was written for
("a ContextVar set on a test's thread outlives the test") applies equally to the other 13. I found no live unbalanced
set: the three mismatched set/reset counts in tests are thread-local or reset through a token list.

**Fix.** Have the check enumerate ContextVars across `engine_python_paths()`, and require each one to be cleared or
listed in `BACKGROUND_SAFE_CONTEXTVARS` with a reason. In conftest, reset every engine ContextVar found in
`sys.modules` to its default via `contextvars.Context().run(var.get)`.

**Test.** The existing `test_turn_scoped_contextvars_are_cleared_or_declared_safe` turns red until the seven are
classified.

### F7 — CI's `make check-fast` hides the suite behind a structure failure  [SILENT-NOOP, CONFIRMED]
`Makefile:118` `check-fast: compile structure test-full`. `make` stops at the first failing prerequisite, and CI runs
it as one step (`ci.yml:48-49`). The project's own record shows the cost twice:
- `tools/project_check.py` `_check_against_a_scratch_database` docstring: "every push from 2026-09-28 (8f408adf) to
  2026-10-05 stopped at `make structure` and ran no test at all -- sixty red runs".
- `check_tests_reach_pydantic_through_helpers` docstring: "red from 2026-09-27 while the structure failure beside it
  hid the result".

**Fix.** `run: make -k check-fast`, or three steps each with `if: ${{ !cancelled() }}`, so compile, structure and
the suite each report.

### F8 — `check_facade_patch_targets` reads one patch spelling, and its criterion is an approximation  [SILENT-NOOP latent, CONFIRMED]
`tools/project_check.py:2636-2700` reads only `X.setattr(<Name|Attribute>, "<const>", …)`.

**String-form patches.** Invisible. 7 are live, all on the `mind.memory` facade:
- `tests/test_character_history_routing.py:246,290`
- `tests/test_fable_town.py:258,516`
- `tests/test_relationship_history_reaches_the_mind.py:170,236`
- `tests/test_room_tools.py:138`

The four `add_memories_batch` patches assert on the writes they record, so they verify themselves.

**`mock.patch` and `patch.object`.** Invisible too (0 live).

**Names a sibling defines and calls itself.** Invisible. One is live:
`tests/test_causal_overlay_verification.py:146` patches `commit._merge_overlays`, which is defined and called inside
`persist/commit_scene_state.py:611/1993/2241`. That patch is **not** inert. Its reader,
`agents/common.py:12917-12918`, does `from persist.commit import _merge_overlays` at call time. So the check's model,
"a sibling imported and calls it, therefore inert", is itself only an approximation: whether a patch is inert depends
on the path under test.

**Fix.** Remove the class instead of detecting it. Mark facade modules (`__facade__ = True`) and give `monkeypatch`
a wrapper (an autouse fixture) that spreads a patch on a facade to every engine module holding the same original
object, which is `patch_seam` semantics. That covers the string form, new facades (common, composer, perception) and
same-sibling definitions.

### F9 — `patch_seam`'s "matched nothing" raise cannot fire, and its docstring promises it does  [DEAD + STALE-DOC, CONFIRMED]
`tests/helpers.py:200-201` always appends the origin, so the `if not patched:` at `:209-211` is unreachable. The
`# pragma: no cover - defended, never reached` comment says as much. The docstring at `:185-187` says it "raises when
that list is empty: a seam matching nothing is a typo or a rename":
- A typo already raises earlier, as `AttributeError` at `:198`.
- The case worth catching passes silently: only the origin was patched, and the origin is a facade whose name no code
  reads.

**Fix.** Raise when nothing other than the origin was patched and the origin is a facade, or delete the dead branch
and correct the docstring.

**Test.** `patch_seam` on a facade attribute with no other holder raises.

### F10 — `.venv-browser` cannot run the browser suite; the dev extra disagrees with `requirements-dev.txt`  [CRASH, CONFIRMED]
`.venv-browser/bin/python -m pytest browser_tests --collect-only` fails with
`error: unrecognized arguments: -n` (inifile `pyproject.toml`). The cause is `pyproject.toml:85`
`addopts = "-ra --strict-markers -n auto"`, and `.venv-browser` has no `xdist`. Its psutil is 5.9.8, not the pinned
7.2.2, so it was not built from `requirements-browser.txt`, which pulls in `-r requirements-dev.txt` and therefore
xdist. `Makefile:85-86` `test-browser` has no degrade path, unlike `test-full` (`:66-75`). Also,
`pyproject.toml:58-60` `[project.optional-dependencies] dev = ["pytest>=8.4.1,<10"]` omits pytest-xdist and psutil,
so `pip install -e .[dev]` followed by `pytest` fails the same way. The dev set has two spellings, free to disagree.

**Fix.** Make `test-browser` mirror `test-full`'s `import xdist` probe, or always run
`-o addopts="-ra --strict-markers"`. Add `BROWSER_PYTHON ?= $(or $(wildcard .venv-browser/bin/python),$(PYTHON))`.
Make the `dev` extra equal `requirements-dev.txt`.

### F11 — `check_pydantic_major_reads_are_owned` enforces six attributes; its rule claims more  [STALE-DOC (claim > enforcement), CONFIRMED]
The docstring (`:2031-2047`) says `llm.schemas` "already branches once … and a second branch anywhere else is how the
two drift apart again". `_PYDANTIC_MAJOR_ATTRS` (`:2020-2023`) holds six field attributes only. Four model-level
major branches live outside `llm/schemas.py` today, all correct:
- `world/charter_history.py:740-741` `parsed.model_dump() if hasattr(parsed, "model_dump") else parsed.dict()`
- `story/journey_history.py:188` (same)
- `story/character_schema.py:309-312` `getattr(model_cls, "model_validate", None)` / `parse_obj` / `model_dump` / `.dict()`
- `persist/chat_archive.py:122-124` `_model_validate`

The check also has no rule for:
- private attributes, which is the `_subject_field` / `ModelPrivateAttr` defect that `ci.yml:58-65` and
  `TESTING.md:237-243` cite;
- `hasattr` probes;
- `tools/`;
- NumPy-major behaviour, which is CLAUDE.md's second defect (NEP 50) and has no guard at all.

Its false-positive surface is the generic names `annotation` and `type_`.

**Fix.** Route the four sites through `llm.schemas._validate` and `_dump`. Better, publish `model_from` and
`model_dict` from `llm.schemas` and have `tests/helpers.py` import them, so there is one branch. Then add the
model-level names (`model_dump`, `model_validate`, `dict`, `parse_obj`) to the engine rule.

### F12 — `tools/package_edges.json`: cycles are current, edges are stale and unread  [STALE-DOC, CONFIRMED]
Generated once, at `6280b635` on 2026-08-19. The cycle set still matches (`[agents, persist, story, world]`), and
`tests/test_repo_hygiene_source_roots.py:149-155` pins it exactly, so a shrinking cycle is ratcheted. The `edges`
table is read by nothing: `check_package_edge_budget` reads only `cycles` (`:2883-2886`), and the test compares only
`cycles`. **54 of 58 stored rows differ from `84f3de23`.** Examples:

| edge | eager, baseline → HEAD | deferred, baseline → HEAD |
|---|---|---|
| `story->world` | — | 3 → 133 |
| `agents->world` | 23 → 37 | 11 → 254 |
| `persist->story` | 19 → 22 | 29 → 59 |
| `story->persist` | 0 → **1** | — |

That is "a baseline nothing regenerates", the exact failure `DESIGN_MODULE_LAYOUT.md:190-199` gives as the reason
the file exists. Eight eager edges inside the cycle have grown since the baseline. That growth is the measurement the
check's docstring opens with, and the check tolerates all of it by design.

Also, `_import_kind_edges` (`:2744`) never descends into an `if` inside a function: `ast.If` is guarded by
`kind != "deferred"` and is not in the generic tuple. Those edges go uncounted. Deferred counts are undercounted;
cycles are unaffected.

**Fix.** Store `cycles` only and print edges on demand, or regenerate the whole file in the test. A ratchet on eager
edges inside the cycle is a budget, so it is the owner's call. I am proposing it, not choosing a number.

### F13 — CI: `needs: fast` with `always()` buys only delay, and TESTING.md still describes the old guarantee  [PERF + STALE-DOC, CONFIRMED]
`ci.yml:73-74` and `:111-112`. Both jobs run regardless of what `fast` concludes, so `needs` only orders them.

Run `41366860777`:

| job | duration | started |
|---|---|---|
| fast, 3.11 | 9:26 | 00:23:13 |
| fast, 3.12 | 9:21 | 00:23:13 |
| fast, 3.13 | 10:25 | 00:23:13 |
| pydantic1 | 4:21 | **00:33:40** |
| browser | 1:44 | **00:33:40** |

Total wall time was **14:52**. Run in parallel it would have been about 10:30. `TESTING.md:343`, "Jobs 2 and 3
need job 1, so a broken build fails once rather than three times", has been false since `always()` was added
(`d041fe02`, 2026-08-18).

**Fix.** Drop `needs: fast` from both jobs and correct `TESTING.md:343`.

### F14 — `make compile` compiles `sys.path` when the inventory command fails  [SILENT-NOOP low, CONFIRMED by reading]
`Makefile:110` `$(PYTHON) -m compileall -q $$($(PYTHON) tools/project_check.py --source-roots)`.
`project_check.py` imports `generate_code_map` and `extract_ui_catalog` at module top (`:17-18`). If either fails to
import, the substitution is empty, and `compileall` with no directory arguments calls `compile_path()`, which
compiles `sys.path` (I confirmed this in `compileall.main` on `.venv`). The step then goes green without compiling
the repository. `structure` would fail on the same import, so the overall verdict holds and only the compile step
misreports.

**Fix.** `roots="$$($(PYTHON) tools/project_check.py --source-roots)" && $(PYTHON) -m compileall -q $$roots`.

### F15 — Assert-by-absence: one live test whose net has a hole by construction  [SILENT-NOOP, PLAUSIBLE]
I scanned for tests whose own body (not counting nested defs) carries no `assert`, `raise`, `pytest.raises`/`fail`,
or `assert*`/`check*` helper call. 28 of 17,886 test functions qualify, and most call a module helper that asserts.
`check_empty_tests` (`:354-400`) flags only import-only bodies, so this class is indeed invisible.

The one that matters is `tests/test_routines.py:161-194` `test_this_module_writes_nothing`. It booby-traps
`core.db.{wset, wset_if_changed, qi, qtx, transaction, wset_for_frame}` and `providers.chat_complete` on the
**defining modules only**. `story/scene.py:5` binds `qi` and `wset` at import, and `routines.residue_for` reaches
`story.scene.style_guide`. A write routed through `story.scene` would pass the test. This is the defect that
`forbid_model_calls`' own docstring (`tests/helpers.py:128-134`) describes. No write happens today.

**Fix.** Use `patch_seam` (identity sweep) for each seam. For the gate, extend `check_empty_tests`: a test that
installs a seal or raising stub and asserts nothing must assert the returned binding list, which is its positive
control.

### F16 — Stale documentation in the gate's own files  [STALE-DOC, CONFIRMED]
- `ci.yml:11-15` says check-fast "runs EVERY test, on both interpreters, in about 40 seconds". There are three
  interpreters, and in run `41366860777` structure took 124-151 s and the suite 398-440 s per leg. `ci.yml:64-65`
  and `TESTING.md:243-244` say "~40s". `TESTING.md:70-71` says "on both interpreters".
- `tests/conftest.py:32-35` says the `slow` marker is "Kept for CI's matrix-breadth job (``make test-fast``)".
  `pyproject.toml:87` says "make test-fast, which is a CI matrix-breadth job". CI never runs it (`TESTING.md:69-73`,
  `ci.yml`).
- `tools/story_drive.py:12-14` says "the only thing replaced is `providers.chat_complete`". The code at `:545-551`
  replaces `llm_quality.complete_validated_json`.
- `tools/extract_ui_catalog.py:33-37` says `PY_FILES` matches `project_check.engine_python_paths`. The latter rglobs
  12 roots, including `extension_runtime`, `language_runtime` and `language_adapters`. `PY_FILES`, like
  `generate_code_map.source_paths` (`:95-103`), globs 8 packages one level deep plus `agents`. No harvestable string
  is lost today. `docs/CODE_MAP.md` has 0 mentions of those three roots, although CLAUDE.md calls it the module index.
- `check_character_payload_names` docstring (`:3067-3087`) names two hazards. The code (`:3102-3106`) checks only
  that the table is injective. A projected name colliding with a key the payload already carries is not checked.
- `tools/project_check.py:3314-3334` is the `DEFERRED_PACK_PARITY` block. It still describes an active, "TEMPORARY,
  … PROMPT-OPTIMIZATION BRANCH" deferral, while the tuple at `:3335` is `()`. `docs/UNBUILT_IDENTITY.md:36-50` still
  says `DEFERRED_PACK_PARITY = ("ja",)` and "delete this entry in the same commit". The entry was not deleted.
- `TESTING.md:413-419` "seals every provider door" (F4). `TESTING.md:343` (F13). `tests/helpers.py:185-187` (F9).

### F17 — CI proves the direct pins, not the transitive stack players run  [SILENT-NOOP, PLAUSIBLE]
`constraints.txt` pins 12 direct packages. Transitive dependencies float. CI resolves fresh on every push, while a
player's `.venv` is reinstalled only when the digest of `requirements.txt` plus `constraints.txt` changes
(`Start_Sonder.sh:300-339`). Today, CI vs the owner's `.venv`:

| package | CI | `.venv` |
|---|---|---|
| anyio | 4.16.0 | 4.14.2 |
| websockets | 17.4 | 17.0.1 |
| uvloop | 0.23.0 | 0.22.1 |
| watchfiles | 1.3.0 | 1.2.0 |
| urllib3 | 2.8.0 | 2.7.0 |
| httptools | 0.9.0 | 0.8.0 |
| idna | 3.20 | 3.19 |
| click | 8.5.0 | 8.4.2 |

Only the direct pins agree. No defect has been measured. "CI is the authority" (CLAUDE.md) holds only for the
direct layer, and there is no Windows or macOS leg although a `.bat` launcher ships.

**Fix.** Owner's call. A full lock file used by both the launchers and CI, for example `pip freeze` from the CI job
committed as `constraints-lock.txt`.

### F18 — `make clean` reaches into other environments and checkouts  [PERF low, CONFIRMED by reading]
`Makefile:123` `find . -type d -name __pycache__ -prune -exec rm -rf {} +` descends into `.venv`, `.venv-browser`,
`.git` and `.claude/worktrees` (present here, currently empty). It deletes bytecode caches that other sessions and
servers use.

**Fix.** Add `-not -path './.venv*' -not -path './.claude/*' -not -path './.git/*'`, or the equivalent prunes.
`charter-audit` is also missing from `.PHONY` (`Makefile:14`).

## Efficiency

### Where `make check` spends its time (this machine, 8 physical / 16 logical cores, `.venv`)

| stage | wall | source |
|---|---|---|
| `compile` | 0.2 s warm / 9.3 s cold | `compileall` on the snapshot |
| `map` | 8.55 s | `make map`, measured |
| `structure` | **221 s** in-process (light load) / **273 s** via make | `S/gate/check_times.out`; make run 4:33 |
| `test-full` | **281 s** at `-n 6` (19,635 tests, 1,414 s CPU) | orchestrator baseline |
| **total** | **≈ 8.5-9.5 min**; structure is 40-48 % of it | |

With the default `PYTHON=python` (F1) there is no xdist, so the suite runs serially at about 1,400 s. The total is
then **≈ 28 min**, on the wrong stack.

CI, run `41366860777`, per `fast` leg:

| leg | compile | structure | suite (incl. ~35-43 s xdist collection) |
|---|---|---|---|
| 3.11 | 5 s | 124 s | 416 s |
| 3.12 | 6 s | 137 s | 398 s |
| 3.13 | 6 s | 151 s | 440 s |

Structure is single-threaded. It parses the same 1,752 files about 11 times per run. With `ast.parse` memoised, I
counted 18,263 cache hits against 1,756 misses. Every check, timed in-process on `84f3de23`:

| check | s | check | s |
|---|---|---|---|
| facade_import_direction | **61.1** | identity_fold_is_owned | 6.7 |
| undefined_names | **20.9** | language_pack_surfaces | 6.4 |
| duplicate_python_symbols | 13.0 | memory_identity_writers | 6.3 |
| conftest_not_imported | 12.7 | nsfw_overlay_roster | 6.2 |
| duplicate_dict_keys | 11.6 | pydantic_major_reads | 6.1 |
| facade_patch_targets | 10.5 | generated_map | 6.0 |
| minimum_python_syntax | 9.8 | install_root_derivations | 5.5 |
| tests_reach_pydantic | 7.5 | package_edge_budget | 4.1 |
| engine_imports_resolve | 7.1 | cross_file_duplicates | 3.7 |
| empty_tests | 6.8 | pipeline_side_channels | 3.0 |
| (the other 16) | < 2 each, 7.1 together | **TOTAL** | **221.3** |

### The three cheapest cuts

**E1. `check_facade_import_direction`: parse and walk each file once, not once per family.**
`tools/project_check.py:1767-1773` loops family → files, so every engine and test file is parsed and walked once per
facade. I prototyped the loop inverted, with one walk that keeps only `Import`/`ImportFrom` nodes and the
module-object uses. Measured under the same load: **95.1 s → 19.6 s**, with an identical verdict (light load:
61 s → about 13 s). As written, each new family adds about 15 s. `a7ea29aa` added the fifth, and composer and
perception are in flight, so seven families would cost about 105 s for this one check. The cut keeps it flat.
About 20 lines.

**E2. A text prefilter before parsing, in checks that hunt for one token.**
The AST rule can fire only if the token appears in the source, so this is exact, not a literal guard. I measured it
by short-circuiting `ast.parse` for sources that lack the token. Verdicts were identical:

| check | before | after |
|---|---|---|
| install_root (`__file__`) | 7.3 s | 0.4 s |
| conftest_not_imported (`conftest`) | 17.5 s | 0.5 s |
| identity_fold (`[^a-z0-9]`) | 9.0 s | 1.4 s |
| memory_identity_writers (`add_memor`, `stable_event_key`) | 7.9 s | 1.4 s |
| tests_reach_pydantic (`model_`) | 9.0 s | 2.4 s |
| **total** | **50.7 s** | **6.1 s** |

`nsfw_overlay_roster`'s engine scan (`nsfw_`) is the same shape. In `check_undefined_names` (`:1418-1426`), the
full `ast.parse` and `ast.walk` exist only to detect a star import, which a line regex answers. `symtable` over all
files costs 4.7 s, so 20.9 s → about 6 s (estimated).

**E3. Stop generating the code map four times per `make check`.**
It is generated by `map` (8.5 s), by `check_generated_map` (`:990-994`, 6.0 s), and twice in the suite
(`tests/test_code_map_generator.py:7,14`; 8.0 s and 6.8 s in the baseline `--durations`). In `check`, skip
`check_generated_map` after `map` has run. Make the generator test parse two small fixtures instead of the whole tree.
Inside the generator, prefilter `"add_api_route" in source` before the full `ast.walk` at
`tools/generate_code_map.py:193-227` (one engine file, `persist/chat_archive.py`, contains it) and read each file once
(`:136` and `:234` both read it). Measured: `generate()` **6.94 s → 4.92 s, byte-identical output**.

### Beyond the three
- **E4. A shared source index.** Path → text, tree, and node lists by type, built once with `gc.freeze()` after the
  build. Memoising `ast.parse` alone took structure from **221 s to 149 s**. Whole-tree `ast.walk` passes (about 4 s
  each) are what remain. With E1 and E2 on top, structure should land under about 60 s (estimated).
- **E5. CI ordering** (F13): run wall 14:52 → about 10:30.
- **E6. Structure checks also run inside the suite.** Twelve checks are re-run as tests: facade_patch_targets 14.0 s,
  identity_fold 10.2 s, package edges 5.8 s and 5.1 s, cross-file duplicates 6.0 s, schema reachability 6.4 s, all from
  the baseline `--durations`. E1 to E4 shrink these too.
- **E7. Lead, not measured to cause.** In the same CI run, the same 19,635 tests took **244 s** on the Pydantic-1 job
  and **398 s** on the Pydantic-2 3.12 leg, with 5 warnings against 662. Players run Pydantic 2, so one profile of
  where v2 spends the extra time (validator wrapping in `LenientModel`, or class build at import) is worth doing.
  Runner variance is not excluded.
- `RELOAD_DELAY := $(shell $(PYTHON) -c "import watchfiles" …)` (`Makefile:24`) starts a Python process on every
  `make` invocation, including `make test`. Trivial.

## Already registered

- **`docs/UNBUILT_PLATFORM.md` §1.61, "Half the prompt ids are outside the prompt/schema drift check".** The entry
  covers the model-less generator group: `generator_lorebook` (`book_ops`, `entry_ops`, `link_ops`),
  `generator_lorebook_entries`, `fill_*`, `offscreen_*` and others. Updated measurement: `check_prompt_schema_ops`
  (`:494`) and `check_prompt_shape_covers_prose` (`:552`) now see **13 of 93** prompt ids (the entry recorded 21 of
  41). The growth is the encoder's pieces (`encoder.*`, 23 of which name an `*_ops` field), `prose_director_*`,
  `story_planner`, `room_sketch` and `skip_memory*`. Unlike the generator group, the encoder pieces **do** have
  models: the channel owners' `director_*` schemas. Their exclusion is the id-equals-step-key lookup, not the
  structural "no model" that §1.61 describes, which makes it a sub-case worth adding to the entry. I ran the ops rule
  by hand over those pieces against the union of `director_*` models and `StateDiff`: **no drift today**.
  `check_prompt_shape_covers_prose` also skips seven prompts that print a `STRICT JSON` shape: `fill_appearance`,
  `fill_character_psychology`, `lore_reinterpret`, `offscreen_agent_adjudicate`, `offscreen_agent_attempt`,
  `offscreen_profile`, `position_resolver`. The fix shape fits §1.61's owner decision: make the prompt-to-model map
  total, so every prompt id is either mapped to a model or listed with a reason, and a new prompt cannot fall outside
  silently.
- **`docs/UNBUILT_PIPELINE.md` ~1637**, "`make structure` is green through" stale `prose_author_sheet/16.txt`
  citations. The mechanism is `check_docs_name_real_paths`'s first-segment rule (`:2416`): a token whose first
  segment is not a top-level directory is skipped. The cited strings no longer appear in `AGENTS.md` or
  `agents/director*.py`, so that entry may itself be stale.
- **`docs/UNBUILT_PIPELINE.md` ~473**, "a `project_check` rule asserting every marker prefixes some line of the body
  is cheap and is not written". Still not written.
- **`docs/UNBUILT_PARKED.md` ~38**, a conformance test for `Design.md`. Idea only.
- **`docs/UNBUILT_IDENTITY.md` 36-50** (`DEFERRED_PACK_PARITY`). Registered, but the register is stale: the code is
  `()`. See F16 and Docs checked.

## Structure notes

- **`tools/project_check.py` is 3,451 lines and 36 checks over one hidden shared input.** About twenty checks
  independently `read_text` + `ast.parse` + `ast.walk` the same files. The natural seam is a `SourceIndex` built once
  (path → text, tree, nodes by type, imports resolved to absolute names), with checks as consumers. That one seam
  carries E1, E2 and E4, the relative-import resolution (F2) and the root widening (F3, F6). A package split
  (`tools/checks/{python_shape,facades,prompts,packs,docs,gate}.py`) would follow it.
- **Monoliths in miniature:**
  - `check_language_pack_surfaces` (`:997-1237`, about 240 lines, nine checks in one);
  - `check_prompt_card_parts` (`:711-855`);
  - `check_time_channel_vocabulary` (`:597-710`);
  - `check_docs_name_real_paths` (`:2354-2440`).
- **"Where the engine source is" is still written five times.** `ENGINE_SOURCE_ROOTS`'s comment (`:1296-1312`) says
  it was created to end that:
  - `project_check.ENGINE_SOURCE_ROOTS`, the authority (rglob, 12 engine roots);
  - `generate_code_map.source_paths` (`:95-103`: 8 packages glob + `agents` rglob);
  - `extract_ui_catalog.SUBSYSTEM_PACKAGES`/`PY_FILES` (`:25-32`, the same);
  - `tests/model_seams._ENGINE_ROOTS` (8 packages, no `dressing`);
  - `tests/helpers._SEAM_PACKAGES` (9 packages).

  The last two also disagree with each other.
- **Two door lists for one fact:** `MODEL_SEAMS` (3) and `MODEL_DOORS` (5). See F4.
- **Two spellings of `addopts`:** `pyproject.toml:85` and the fallback at `Makefile:74`
  (`-o addopts="-ra --strict-markers"`). A flag added to pyproject is silently dropped on the fallback path.
- **Two spellings of the dev set:** `pyproject.toml:58-60` and `requirements-dev.txt`. See F10.
- **Module-level mutable state:**
  - `extract_ui_catalog._LONG_MESSAGES`, a set filled by `_message` and never cleared, which accumulates across
    `catalog()` calls in one process;
  - `extract_ui_catalog.PY_FILES`/`HTML_FILES`/`JS_FILES`, frozen at import. That is why an in-process run straddling
    a file move reports a false "UI catalog is stale", which I hit mid-audit;
  - `sys.path.insert(0, ROOT)`, repeated by seven checks on every call (duplicates accumulate);
  - `_check_against_a_scratch_database` reconfigures `core.db` globally. That is fine in `make structure`'s own
    process and must never be called from a test.

## Docs checked

| claim | where | holds? |
|---|---|---|
| "`make check` runs whatever `python` resolves to" (Pydantic 1 vs 2) | CLAUDE.md, TESTING.md:191-197 | **Holds**, still true today (F1) |
| `make structure` catches "uncleared turn-scoped contextvars" | CLAUDE.md | **Partial**: 2 of 9 modules (F6) |
| project_check "enforces … a caller imports the facade" | CLAUDE.md | **Fails** for relative imports, 7 sites (F2) |
| `check` regenerates the map; `check-fast` verifies the copy | TESTING.md:17-20, Makefile:112-117 | Holds (both generate in memory, E3) |
| test-fast "has no consumer left in ci.yml" | TESTING.md:69-73 | Holds |
| "…on both interpreters" | TESTING.md:70-71, ci.yml:13-14 | **Stale**: three |
| "~40s" / "about 40 seconds" | ci.yml:14,65; TESTING.md:244 | **Stale**: 398-440 s suite plus 124-151 s structure per leg |
| test-fast is a CI matrix-breadth job | conftest.py:32-35, pyproject.toml:87 | **Stale** |
| every install path passes `-c constraints.txt` | TESTING.md:157-160, requirements.txt:3-9 | Holds for direct pins; transitives float (F17) |
| two structural guards exist for the majors; "a guard covers the class it names and nothing else" | TESTING.md:213-217 | Holds, and F11 is the proof |
| "no production module uses `parse_obj`/`.dict()` any more" | TESTING.md:310-314 | **Partial**: four 1.x fallback branches outside `llm/schemas.py` still call them (correct, but they are branches; F11). "six test assertions still call `.dict()`" holds (6 in the 4 named files) |
| CI layout: three jobs, 3.11-3.13, pydantic1 asserts its major | TESTING.md:320-341 | Holds (the log shows `pydantic 1.10.27`) |
| "Jobs 2 and 3 need job 1, so a broken build fails once" | TESTING.md:343 | **Stale** (F13) |
| `model_seams.py` "seals every provider door" | TESTING.md:413-419 | **False** (F4) |
| "forgetting to [add a door] is the one way this can go quiet" | model_seams.py:25-27 | Holds, and it happened: `llm/decisions.py` |
| `patch_seam` "raises when that list is empty" | helpers.py:185-187 | **False** (F9) |
| "the only thing replaced is `providers.chat_complete`" | tools/story_drive.py:12-14 | **False** (F16) |
| `PY_FILES` matches `engine_python_paths` | extract_ui_catalog.py:33-37 | **Partial** (F16) |
| `packages = […]` is `ENGINE_SOURCE_ROOTS` minus four | pyproject.toml:16-24 | Holds (12) |
| the matrix, `requires-python` and both launchers are held equal | ci.yml:28-35, TESTING.md:334-337 | Holds (`check_python_version_agreement`). `tests/test_launcher_python_range.py:29` and README.md:56,62 are further hand-kept copies it does not see |
| `tools/package_edges.json` "is generated … and checked" | DESIGN_MODULE_LAYOUT.md:201-209 | Cycles hold; **edges stale and unread** (F12) |
| `DEFERRED_PACK_PARITY = ("ja",)`, "delete this entry in the same commit" | UNBUILT_IDENTITY.md:36-50 | **Stale**: the tuple is `()` (`project_check.py:3335`). The comment block at `:3314-3334` still describes the deferral as active |
| second payload-name hazard (collision with an existing key) is guarded | project_check.py:3077-3078 | **False**: only injectivity is checked |
| `_clear_turn_scoped_context`'s 2026-08-19 audit "found no other survivor" | core/jobs.py:217-220 | Out of date: four of the seven unscanned vars were added after it, between 2026-09-05 and 2026-10-10 (F6) |

## Appendix — the 36 checks: what each proves, its blind spot, its cost

Runtime: in-process on `84f3de23`, light load. Line numbers: `84f3de23`. "Engine" means 267 files and 325k lines;
`tests/` means 1,305 files and 360k lines.

| # | check (line) | proves | blind spot | s |
|---|---|---|---|---|
| 1 | `undefined_names` (1374) | no function reads a module global nothing binds (symtable) | a name referenced at module level counts as known; star-import modules skipped (0 today); `mod.missing` attribute errors; `extensions/*/*.py` one level only | 20.9 |
| 2 | `extension_manifests` (1449) | bundled manifests parse, entries exist, `register(api)` runs, declared stages are registered | only `stages` compared, not commit domains, routes or hooks; `_Recorder` stubs 7 API methods, so any other call runs the real method during `make structure` | 0.08 |
| 3 | `extension_imports` (1551) | non-`system` extensions import no engine package | `importlib.import_module("core.db")` / `__import__` strings | 0.01 |
| 4 | `facade_import_direction` (1743) | outside-in and inside-out facade rule for `FACADE_FAMILIES` | relative imports (7 live, F2); `tools/` (39), `demo/`, `browser_tests/` unscanned; a family exists only when hand-added | 61.1 |
| 5 | `conftest_not_imported` (1910) | nothing imports `conftest` under a second name | string imports; costs 12.7 s for one token (E2) | 12.7 |
| 6 | `minimum_python_syntax` (1956) | no PEP 701 same-quote nesting or newline in a single-quoted f-string field | backslash or `#` inside a replacement field, PEP 695 syntax (0 live); no-op on a 3.11 host. CI's 3.11 `compileall` covers it there, but nothing covers it locally (no 3.11 on this machine) | 9.8 |
| 7 | `pydantic_major_reads_are_owned` (2030) | engine code outside `llm/schemas.py` reads none of six field attributes | model-level branches (4 live), private attributes, `hasattr`, `tools/`, NumPy-major behaviour (F11); false-positive surface on `annotation`/`type_` | 6.1 |
| 8 | `tests_reach_pydantic_through_helpers` (2091) | tests call no 2.x-only model attribute | `getattr(m, "model_dump")`; list omits `model_extra`, `model_fields_set`, `model_rebuild`, `model_post_init` | 7.5 |
| 9 | `engine_imports_resolve` (1847) | tools and engine imports name existing engine modules | imported names not checked; tests, demo and browser_tests unscanned; relative and `importlib` imports | 7.1 |
| 10 | `asgi_targets` (1877) | `uvicorn mod:attr` in Makefile/`*.sh`/`*.bat` names a real module | `:attr` unchecked; Python launchers and doc commands not scanned | 0.04 |
| 11 | `duplicate_python_symbols` (110) | no def or class bound twice in a module or class body (engine + `tests/test_*.py`) | assignments; test helper modules, `tools/`, `demo/`, `browser_tests/` | 13.0 |
| 12 | `duplicate_dict_keys` (241) | no dict literal repeats a constant key | keys spelled via named constants; same file set as #11 | 11.6 |
| 13 | `install_root_derivations` (288) | only `core/paths.py` reads `__file__` | `Path.cwd()`, `sys.argv[0]`, `inspect.getfile` | 5.5 |
| 14 | `no_dead_prompts` (1239) | every `en` prompt id has a literal `get_prompt[_body]("id")` | regex over raw text, so a comment counts (0 such today) | 0.26 |
| 15 | `patch_debris` (344) | 4 literal markers absent from engine `.py` and `static/js` | git conflict markers not listed; tests, tools, css, html, json, md unscanned | 0.08 |
| 16 | `empty_tests` (354) | each test file collects a test; no test body is imports only | a `pass`/docstring-only body (`if body and …` is False when empty; 0 live); assert-by-absence (F15) | 6.8 |
| 17 | `cross_file_duplicate_definitions` (175) | no byte-identical ≥3-line module-level def or assignment in two engine modules | classes, methods, near-duplicates (by design) | 3.7 |
| 18 | `prompt_schema_ops` (459) | each `*_ops` a prompt names exists on its stage model | 13 of 93 prompt ids checked (§1.61 plus the encoder pieces) | 0.51 |
| 19 | `prompt_shape_covers_prose` (521) | backticked top-level fields of 11 shape-printing prompts appear in the shape | 7 more shape-printing prompts unchecked; substring match (`act` is "in" `action`) | 0.00 |
| 20 | `time_channel_vocabulary` (597) | `state_diff.time` keys taught by examples and prompts are readable | dataflow (stated in its own docstring); two regex shapes only | 0.55 |
| 21 | `prompt_card_parts` (711) | card index ↔ part files ↔ canonical form ↔ en/ja parity | none material | 0.15 |
| 22 | `channel_owners` (856) | owners = `SPECIALIST_CHANNELS`; pack orders cover them; each channel has an encoder chunk | chunk content; one direction only (no orphan chunks today) | 1.9 |
| 23 | `nsfw_overlay_roster` (929) | one roster, no second spelling, only `llm/prompts.py` names the keys | f-string or concatenated key names; parses every engine file for two constants (E2) | 6.2 |
| 24 | `language_pack_surfaces` (997) | EN card ↔ registry, contract text, UI catalog fresh, pack parity, exception ledger, regex groups, template fields, mask markers | contract check is a substring; UI harvest skips 3 roots; 240-line monolith | 6.4 |
| 25 | `python_version_agreement` (2150) | pyproject, both launchers and the CI matrix name one 3.x series | which environment the local gate runs in (F1); dependency majors; README and the launcher test's `SUPPORTED` | 0.01 |
| 26 | `no_machine_paths_in_scripts` (2227) | no `/home/<u>/`, `/Users/<u>/`, drive letter or worktree path in runnable files | `Makefile`, `.github/workflows`, `extensions/` not scanned | 2.0 |
| 27 | `docs_name_real_paths` (2354) | links and backticked repo paths in authority docs resolve | tokens whose first segment is not a top-level dir; symbols; line numbers | 0.53 |
| 28 | `docs_imports_resolve` (2466) | backticked imports in guidance docs name real modules | imported names | 0.06 |
| 29 | `turn_scoped_contextvars_are_cleared` (2572) | each ContextVar in 2 modules is cleared for jobs or justified | 7 ContextVars in 7 other modules (F6) | 0.06 |
| 30 | `facade_patch_targets` (2636) | no test patches a facade name that a sibling imported and calls | string form (7), `mock.patch`, same-sibling definitions; approximate criterion (F8) | 10.5 |
| 31 | `package_edge_budget` (2848) | no new eager strongly connected component beyond the baseline | growth inside the cycle (8 edges); stored edges stale and unread; `if` inside functions not walked (F12) | 4.1 |
| 32 | `memory_identity_writers` (2941) | engine memory writers are registered; `turn.id` minting only in `commit_memory` | `tid = turn.id; stable_event_key(tid)`; registry prose not verified | 6.3 |
| 33 | `character_payload_names` (3067) | `PAYLOAD_NAMES` is injective; prose never says `decision.<engine_name>` | collision with other payload keys (its own second hazard); non-`decision.` mentions | 0.12 |
| 34 | `identity_fold_is_owned` (3015) | no `X.sub("[^a-z0-9]", "", …)` fold outside `character_schema` | compiled-pattern form `_RX.sub("", s)`; other ASCII classes | 6.7 |
| 35 | `pipeline_side_channels` (3256) | `ctx` writes in `agents/` and `story/` are fields or `SIDE_CHANNELS` | other roots (live miss `_extension_routing`, F3); `setattr(ctx, …)` and `ctx._extra.update`; computed keys (stated) | 3.0 |
| 36 | `generated_map` (990) | `docs/CODE_MAP.md == generate()` | the generator skips 3 engine roots; it regenerates what `make map` just wrote (E3) | 6.0 |

Repository: `/home/nathan/Documents/Sonder_Engine`. Snapshot: `S/gate/headtree` (`git archive 84f3de23`), deleted at
the end of this task to free 115 MB; regenerate it with `git archive 84f3de23 | tar -x -C <dir>`.
`S` = `<review scratch>`.
