# Audit record — `tools/` and the test suite as code

Status: EVIDENCE. Written 2026-08-18 against `c4da50b`, three days after the
`commit.py` split (`daa37b8`), one day after the director and spatial splits,
and the same day as `a6d823f` — "Eighty-one modules leave the root", which
moved every engine module into eight subsystem packages and rewrote 2,714
import statements across 506 files.

Scope: `tools/` (47 files, 18,666 lines) and `tests/` (443 files) **as code**,
not as a measure of the engine. Findings are **flagged, never fixed** — no
source or test file was edited for this audit, and nothing was executed:
`make check` and the suite were both deliberately not run, because other work
was in flight and a moving tree cannot be read.

Every `file:line` is as of `c4da50b`. Where a claim required proof it is
stated with the proof inline: the patched path, the module the reading
function actually lives in now, and the line that reads it.

---

## 0. Summary

| | count |
|---|---|
| `tools/` findings | 12 (F1–F12: 3 broken, 1 silently degraded, 8 stale) |
| `project_check.py` checks narrower than the rule they state | 6 (S1–S6) |
| test-suite findings | 9 (T1–T9) |
| verified-clean sweeps (reported as negative results) | 5 |

The three most serious, in order:

1. **`tools/perception_quality.py:100-101` measures nothing and says so only in
   its JSON.** Two `__import__` targets are still bare pre-move module names,
   so the dialogue-entitlement gate — the metric the harness exists for —
   is disabled and every line is filed `ungated`.
2. **33 of 43 `MODULE_PURPOSES` keys in `tools/generate_code_map.py` are dead**,
   so 100 of 110 rows in the generated `docs/CODE_MAP.md` now carry an empty
   Purpose column. `make check` regenerates the file and compares, so the loss
   is invisible by construction.
3. **`tests/test_composer_pipeline.py:21-31` and
   `tests/test_composer_admission_gate.py:134-142` are autouse assert-by-absence
   fixtures whose patch cannot reach any caller.** They guard two whole files
   and prove nothing.

---

## 1. `tools/`

### 1.1 The four load-bearing tools, read line by line

`project_check.py` (1,037), `generate_code_map.py` (337),
`extract_ui_catalog.py` (399), `scene_lint.py` (634). Findings that belong to
`project_check.py`'s *checks* are in §2; what follows is everything else.

---

**F1. `tools/generate_code_map.py:18-62` — 33 of 43 `MODULE_PURPOSES` keys can
never match a module again.**

`module_name()` (line 78) builds a dotted name from the path relative to
`ROOT`, so since `a6d823f` it returns `core.db`, `llm.providers`,
`persist.commit`, `world.spatial`, `mind.memory`, `web.app`. `MODULE_PURPOSES`
still keys on the pre-move bare names: `app`, `auth_routes`, `chat_archive`,
`character_schema`, `checkpoints`, `commit`, the thirteen `commit_*`, `db`,
`importers`, `llm_quality`, `logging_utils`, `memory`, `pipeline_context`,
`pipeline_trace`, `prompt_cache`, `prompts`, `providers`, `scene`, `schemas`,
`spatial`, `spatial_orientation`. Only the ten `agents.*` keys survive, because
`agents/` did not move.

Measured by importing the module and diffing the key set against
`{module_name(p) for p in source_paths()}`: **33 dead keys, and 100 of 110
module rows now render an empty Purpose cell.** Confirmed in the committed
artefact — `docs/CODE_MAP.md` lines for `core/db.py`, `mind/memory.py`,
`persist/commit.py`, `web/app.py` and `world/spatial.py` all read
`| … | <lines> |  | …`.

The reason nothing caught it is the shape worth recording: `check_generated_map`
(`project_check.py:451`) compares the file on disk against `generate()`'s
output. Both sides lost the purposes at the same instant, so the check agrees
with itself. A generator's own lookup table is invisible to a freshness check.

`a6d823f` touched this file by seven lines — the `source_paths()` package list
and the `core/db.py` path — and the table was not rekeyed with them.

---

**F2. `tools/extract_ui_catalog.py:261` — `READER_FACING_TABLES` names two
tables that do not exist, and one of them never did.**

```python
READER_FACING_TABLES = {
    "agents/runtime.py": {"FRIENDLY_STEP_LABELS", "STEP_LABELS"},
```

`FRIENDLY_STEP_LABELS` is defined at `static/js/chat.js:703` — a JavaScript
const, harvested by the JS scanner, not by `_table_strings`. `STEP_LABELS`
exists nowhere in the repository, in Python or JavaScript.
`git log -S FRIENDLY_STEP_LABELS -- agents/runtime.py runtime.py` returns
nothing: the name has never been in that module, so this is not move damage —
it has been wrong since it was written (`23d05c5`). The other three entries
(`world/living_world.py`, `story/scene.py`, `mind/affect.py`) are correct and
were repointed by the codemod.

The comment above the table reads "Each entry here is a promise that the
table's values are interface copy." One of the two names in the first entry is
a promise about a table in another language, and the other about a table that
does not exist.

---

**F3. `tools/extract_ui_catalog.py:32` scans `agents/` non-recursively while
`generate_code_map.py:74` and `project_check.py:699` scan it recursively.**

`tuple(sorted((ROOT / "agents").glob("*.py")))` versus `rglob("*.py")` in the
other two. `agents/` has no subdirectory today, so the three tools agree by
accident. It is a latent divergence between three files that all claim to
enumerate "the engine's own modules", and only one of them would notice a new
`agents/<subpkg>/`.

---

**F4. `tools/scene_lint.py:29-32` — the module docstring contradicts the
function it describes.**

The docstring says "Healing uses `attire.release_removed_garments` (which
reder1ves the entry, dropping stale derived notes) and
`commit._fold_duplicate_shed_garments`." `heal_scene`'s own docstring
(`:342-360`) opens with "Deliberately **NOT** `attire.release_removed_garments`",
and explains at length why — it would have rewritten 127 pre-region wardrobes
and renamed ten garments. The function is right and the module header is a
description of the version that was rejected. (`reder1ves` at `:29` is also a
typo for `rederives`.)

Everything else in `scene_lint.py` checks out: `commit._fold_duplicate_shed_garments`,
`attire.resolve_garment` and `attire.flat_state` all resolve through the current
facades; the read path opens `file:{db}?mode=ro` and backs up into `:memory:`
before touching anything; `contacts`/`substances`/`scales`/`following` are the
shapes the checks assume (`story/scene.py:383` seeds `contacts` as a list,
`world/spatial_contacts.py:454` writes `actor`/`target`, which `:108`'s role
list covers). The three unused role names in that list (`a`, `b`, `subject`)
are dead but harmless.

---

### 1.2 The ~43 experiment drivers

An AST pass over every `tools/*.py` resolving imports against the current
package layout found **zero** stale module imports and **zero** `from X import
Y` naming a name absent from `X`. A second pass resolved 263 call sites against
real signatures: no arity or keyword drift. `git show a6d823f -- tools/`
confirms the codemod changed only `import` statements in the 36 files it
touched.

So the surviving breakage is exactly where an import-rewriting codemod cannot
look: **strings, shell, and prompt-id keys.** All four classes below were
verified independently of the sweep that proposed them.

---

**F5 (BROKEN). `tools/test_server.sh:67` — `exec python3 -m uvicorn app:app`.**

`app.py` no longer exists at the repository root; it is `web/app.py`.
`Makefile:24` and `:30` were updated to `uvicorn web.app:app`; this file was
not, because it is a shell script and is absent from
`git show a6d823f --name-only -- tools/`. It fails at startup with
"Could not import module app". It is the only non-`.py` file in `tools/`, which
is precisely why it was missed.

---

**F6 (BROKEN). `tools/scale_probe.py:200` — `KeyError: 'perception'` on the
default invocation.**

`--step` defaults to `"perception"` (`:179`), and `:200` does
`prompts.DEFAULT_PROMPTS[args.step]`. Verified by import: `DEFAULT_PROMPTS` has
42 ids and `perception` is not among them — the role, the prompt and the schema
were deleted together when perception became deterministic. `:220`'s
`schemas.validate_llm_output_strict("perception", …)` is dead for the same
reason (`SCHEMA_MAP` has 21 keys, none of them `perception`). The tool's
crowded-scene firewall probe — `_perception_payload` / `_check_perception` — is
unreachable; only `--step director_interpret` still runs.

---

**F7 (BROKEN). `tools/creation_probe.py:211` — `KeyError: 'director_resolve'`.**

`--step` is `choices=sorted(PAYLOADS)` and `PAYLOADS` has exactly two keys,
`mapping_stage` and `director_resolve` (`:86`). `director_resolve` is a
`SCHEMA_MAP` stage but not a prompt id — the monolith is gone and the prose
author's sheet is `director_resolve_lean`. Verified by import.
`tools/contract_bench.py:219` already carries the compensating map
(`PROMPT_KEY = {"director_resolve": "director_resolve_lean"}`, applied at
`:336`); `creation_probe.py` has no such map. The failing invocation is the
tool's own documented example at `:28`.

---

**F8 (SILENTLY DEGRADED — the worst of the twelve).
`tools/perception_quality.py:100-101` disables its own headline metric.**

```python
"spatial": ["spatial_rel", "room_of"],
"character_schema": ["character_name"],
```

These are string keys fed to `__import__(module_name, fromlist=names)` at
`:106`. Verified directly: `__import__("spatial", …)` and
`__import__("character_schema", …)` both raise `ModuleNotFoundError` — the
modules are `world.spatial` and `story.character_schema`. The `except` at
`:104` swallows it and sets all three symbols to `None`.

The consequence is at `:367`:

```python
gate_available = bool(dialogue_hear_level and spatial_rel and room_of
                      and isinstance(scene, dict))
```

`False`, always. So `:383-384` files **every** dialogue line as `ungated`, and
the entitled-line recall and leak accounting — the reason this harness exists —
is not computed. The tool exits 0. It reports `gate_available: false` and
`engine_symbols_missing` in its JSON, so the damage is legible, but only to a
reader who already suspects it. The two entries above these
(`agents.common`, `agents.perception`) were already package-qualified and still
resolve, which is what makes the block look healthy at a glance.

This is the same class the `a6d823f` commit message names — "string-form
monkeypatch targets (13)… a dotted name inside a string is not necessarily an
import" — found by running the suite. `tools/` has no suite, so its share of
that class was never found.

---

**F9 (STALE). `tools/backdrop_preview.py:26` defaults `--db` to a database
outside this repository.**

`os.environ.get("ENGINE_DB") or "/home/nathan/Documents/Fiction-improved/Fiction/engine.db"`.
That file exists — 398 MB, last written 2026-07-25 — so with `ENGINE_DB` unset
the tool runs happily against a two-month-stale copy of a pre-rename checkout
and reports on it as though it were current.

---

**F10 (STALE). Three drivers still plumb the removed `perception` model role.**

- `tools/model_playthrough.py:150` — `models["perception"] = {…}` writes an
  `agent_models` entry for a role absent from `providers.ROLES` (verified: 18
  roles, no `perception`). `PERCEPTION_MODEL`, `FAST_PERCEPTION_MODEL`
  (`:118-122`) and the `perception_model` parameter are all no-ops, and the
  comment at `:120` — "the fastest generator wins the role that runs once per
  perceiver" — describes a role that has not existed for releases.
- `tools/story_drive.py:302` and `tools/maze_experiment.py:1281` —
  `if role == "perception":` inside the stubbed model seam. Dead branches.

---

**F11 (STALE). Prose pointers to pre-split files.**
`tools/reproject_world_entities.py:33` and `tools/remember_lines.py:49,57`
point a reader at "commit.py" for code that now lives in
`persist/commit_entities.py` and `persist/commit_memory.py:40`. The symbols
still resolve through the facade; only the pointers are wrong.

Related and already recorded in `AUDIT_COMMIT.md` §1.3:
`tools/remember_lines.py` inlines the same hardcoded English durable-quote
word list that `persist/commit_memory.py` carries.

---

**F12 (SUSPECT). `ChatArchiveService.export_chat(None, cid)` in three drivers.**

`tools/live_drive.py:251`, `tools/model_playthrough.py:426`,
`tools/quest_drive.py:803` all call the export with `self=None`.
`persist/chat_archive.py:182` defines it as an instance method that
dereferences `self._remap.json_id_list(...)` at `:352-353`, inside
`for frame in export["frames"]`, and again at `:390-391` for checkpoint-blob
frames. With `self=None` that is an `AttributeError` the moment the chat has
any row in `frames` — and frames rows appear on their own, because
`world/spatial_frames.py:833`'s `perform_split` is reached from
`detect_and_reconcile` (`:1078-1080`) at commit time. A party splitting across
zones mid-drive turns the final export into a crash *after* the whole run has
been paid for. It stays green in the suite only because
`tests/test_artifacts.py:245` and `tests/test_couriers.py:361` make the
identical call on chats that never split. Marked SUSPECT rather than BROKEN
because it is conditional on the run's content, and it is not move damage.

---

**Verified clean (negative results worth recording).** Every other driver
resolves: no module attribute that no longer exists, no signature drift, every
`ROOT` derivation still correct (`tools/` did not move, so
`parents[1]`/`dirname(dirname(__file__))` still lands on the repo root), and
every SQL table and column present in `core/db.py`'s schema. Per-file coverage
was taken; the 34 files not named above are runnable.

---

## 2. `make check`'s structural checks that cannot fire, or cannot fire on
what they claim

`tools/project_check.py` runs fourteen checks. Six have a hole worth naming.
None of these is a bug in the sense that `make check` is currently wrong; each
is a check narrower than the rule it states, which is the more expensive
condition, because it also supplies the belief that something is watching.

---

**S1. `check_facade_import_direction` (`:949`) cannot see the
`from <package> import <sibling>` form, which is the form the repository
actually uses.**

The matcher is `head, _, tail = name.rpartition(".")` against
`node.module` (`:988-995`). For `from persist.commit_memory import X` that
gives `tail="commit_memory"` — caught. For **`from persist import
commit_memory`** it gives `name="persist"`, `tail="persist"` — not a sibling,
not the facade, no error.

Measured with the check's own logic re-implemented over both spellings:
**twelve sites in `tests/` import a `commit_*` sibling in the missed form and
are not reported.**

```
tests/test_awareness_not_from_speech.py:68,106   from persist import commit_entities
tests/test_character_contract_slim.py:68         from persist import commit_memory
tests/test_commit_mind_models.py:86              from persist import commit_memory_write
tests/test_commit_tail_producers.py:121          from persist import commit_memory_write
tests/test_consolidation_out_of_band.py:34       from persist import commit_memory_write
tests/test_dw_audit_scene.py:54                  from persist import commit_room_registry
tests/test_memory_affect.py:45                   from persist import commit_memory
tests/test_memory_commit.py:132                  from persist import commit_memory_write
tests/test_memory_consolidation_parallel.py:73   from persist import commit_memory_write
tests/test_own_conduct_memory.py:61              from persist import commit_memory
tests/test_room_size_coverage.py:97              from persist import commit_scene_state
```

Worth one more fact: **zero** sibling imports anywhere in `tests/` use the
spelling the check DOES catch. All twelve use the one it does not.

This is the finding with teeth, because of what it implies: those twelve are
the **deliberate repoints** the `commit.py` split made (`AUDIT_COMMIT.md` §1.2 —
a facade patch whose reader moved is silently inert, so the patch had to name
the sibling). The check's stated rule — "Import the facade instead — it
re-exports every name" — and the split's own correctness requirement are in
direct conflict, and the only thing keeping `make check` green is that the
check reads one spelling and the tests use the other. Closing the hole as
written would turn twelve correct tests red. The rule needs a stated exception
for a test that must patch where the name is READ, not a narrower matcher.

The inside-out half has the same hole: a sibling doing `from persist import
commit` is not seen either (`:1001` compares `name == facade_mod`, i.e.
`"persist.commit"`).

---

**S2. `check_facade_import_direction` does not cover `world/spatial.py`,
which is the third split family.**

`families` (`:969-972`) lists `agents.director` and `commit` only. `AGENTS.md`
describes `world/spatial.py` in exactly the same terms — "a pure re-export
facade over the thirteen `spatial_*` modules… every name, private ones
included, still imports as `from spatial import X`" — and `SPLIT_SPATIAL.md`
is its plan. Re-running the check's own logic with the fourteen modules
`world/spatial.py` actually re-exports finds three sites it would report today:

```
tests/test_barrier_vocabulary.py:29   from world.spatial_orientation import ...
tests/test_bearing_integrity.py:36    from world.spatial_orientation import ...
tests/test_orientation.py:13          from world import spatial_orientation   (the S1 form)
```

Worth being exact about *why* it was not simply added, because the reason is a
second defect in the mechanism: siblings are discovered by
`home.glob("%s_*.py" % stem)` (`:975`), a **name-prefix** guess, not membership.
`world/spatial_frames.py` matches `spatial_*` and is **not** behind the facade —
`world/spatial.py` does not import it. Adding `world.spatial` to `families`
unchanged would therefore flag six correct engine imports of `spatial_frames`
(`agents/perception.py:2932`, `persist/commit.py:53-54`,
`persist/commit_destruction.py:13`, `persist/commit_scene_state.py:16`,
`world/mechanics.py:65`) as facade violations, and would flag
`world/spatial_frames.py:41`'s `from world.spatial import (…)` as the
import cycle the check exists to prevent — which it is not, because
`spatial_frames` is not a sibling. **A family cannot be inferred from a
filename prefix; it has to be read off the facade's own import block.**

---

**S3. `check_prompt_schema_ops` (`:225`) does not cover the prompts its own
docstring cites as its founding defect.**

`checks = [(stage, stage) for stage in schemas.SCHEMA_MAP]` (`:260`), so a
prompt is checked only if its id is also a `SCHEMA_MAP` key. Measured:
**21 of 42 prompt ids are outside the loop, and two of them name `_ops`
fields**:

```
generator_lorebook          book_ops, entry_ops, link_ops
generator_lorebook_entries  entry_ops
```

The docstring's first worked example is "`entry_ops` asked for by the lore
prompt, `entries` opened by the reader. Shipped, reported by a user against
alpha 7.2, fixed in 7.2.1." Those are the two prompts, and they are exactly
the two the check cannot see.

The reason is structural rather than an oversight, which is why it belongs
here rather than in a fix list: `story/importers.py:2029` and `:2576` consume
this prompt through `_jparse(raw)` and hand-written `parsed.get("book_ops")`
reads, with no Pydantic model anywhere. There is nothing for `_field_names` to
compare against. The comment at `story/importers.py:2578` records the *same*
defect recurring on that path ("Reading only the legacy `entries` key therefore
rejected every compliant answer"), which is the proof that the uncovered half
is still where it happens. The check is real and valuable for the 21 stages it
does cover; the register entry is that the schema-less consumers are an
uncovered half, not that the check is broken.

---

**S4. `check_duplicate_python_symbols` (`:76`) walks `tree.body` only, so a
duplicated method inside a class is invisible.**

`for node in tree.body:` — top-level `FunctionDef`/`AsyncFunctionDef`/`ClassDef`
only. A second `def test_y` inside `class TestX:` silently deletes the first
with no error from `make structure`, which is precisely the damage the
docstring describes ("a duplicated test name does not error, it DELETES the
earlier test"). Verified against the tree: **1,087 classes, 4,079 methods, zero
collisions today** (excluding legitimate `@x.setter`/`@overload` pairs), so the
hole is latent, not live. Three adjacent blind spots, all also currently
empty: a top-level `def` shadowed by a later assignment or import binding (the
check counts only Def nodes); nested `def`s inside one function; and
module-scope defs inside `if`/`try` that collide with a top-level def — the
only raw hits there are `llm/schemas.py`'s two arms of
`if _PYDANTIC_V2:` at `:182`, which are correct.

**Scan-set gaps, shared by `check_duplicate_python_symbols`,
`check_duplicate_dict_keys` and `check_patch_debris`:** `engine_python_paths()`
(`:694`) is the eight packages (`glob`, non-recursive) plus `agents/`
(`rglob`), and the duplicate checks add `tests/test_*.py`. Outside all of them:
**78 `.py` files** — `tools/` (47), `demo/` (11), `browser_tests/` (10),
`extensions/` (4), `extension_runtime/` (2), `language_adapters/` (2),
`language_runtime/` (1), `tests/conftest.py`. Plus six extension UI JS files
for the debris check. All clean today. One quirk if the set is ever widened:
the only patch-marker hits anywhere in the repo are the marker *definitions* at
`tools/project_check.py:19-20`, so adding `tools/` would make the guard flag
itself.

---

**S5. `check_extension_manifests` (`:813`) never imports the Python entry of
two of the three bundled extensions.**

`if not declared: continue` (`:854-855`) skips straight past any extension
whose manifest declares no `stages`. Measured: `campaign-demo` and
`overlay-demo` declare `stages: []`; only `cohesion-demo` declares one
(`pulse`). So `_dry_run_registrations` — which is the half that actually loads
the module and would report `register(api) failed` — runs for **one of three**.
A `register()` that raises in either of the other two is not caught by
`make check`. The file-existence and manifest-parse halves do run for all
three.

---

**S6. `check_empty_tests` (`:154`) only catches a file that is entirely
whitespace.**

A `tests/test_*.py` with imports and no test function passes. Verified over all
440 test files: no whitespace-only file, no file collecting zero tests, none
imports-only. Latent. Related and live, in §3: a test file can contain a test
function that asserts nothing at all, which this check is not shaped to see
either.

**Also outside `make check` entirely:** `make compile` (`Makefile:65`) compiles
`core llm world mind story dressing persist web agents tools tests
browser_tests`. It does not compile `extension_runtime` (2 files),
`language_runtime` (1), `language_adapters` (2), `extensions` (4) or `demo`
(11). `check_undefined_names` does scan the first four, so the only directory
with no static coverage of any kind is **`demo/` (11 files)** — which
`a6d823f` did rewrite the imports of. Checked by hand for this audit: all 11
parse, import-resolve and compile cleanly.

Two checks whose escape hatches are currently costing nothing, recorded so they
are not re-derived: `check_undefined_names` skips any module containing a
star-import — **zero files repo-wide** trigger it; and `check_no_dead_prompts`
reads only literal-argument `get_prompt("…")` calls, so the id tables behind
`world/offscreen.py:1660`'s and `story/importers.py:437`'s `__getattr__`
compatibility shims are invisible to it — but that direction produces a false
POSITIVE (a loud failure), never a silent pass.

---

## 3. The test suite as code

### 3.1 A test that asserts by ABSENCE, on a name nothing reads

**T1. `tests/test_composer_pipeline.py:21-31` and
`tests/test_composer_admission_gate.py:134-142` — autouse fixtures whose
raising stub cannot be reached by anything.**

Both install the same guard:

```python
@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    import agents.common as common
    def _boom(*args, **kwargs):
        raise AssertionError("perception attempted a model call")
    monkeypatch.setattr(common, "_agent_json", _boom)
```

`_agent_json` is **defined** at `agents/common.py:1463` and is called nowhere
inside `agents/common.py`. Every consumer binds it into its own module globals
with a module-level from-import and then calls it bare, so the name resolves in
the **caller's** globals, which no `setattr` on `common` can reach:

| reader | binds at | calls at |
|---|---|---|
| `agents/director.py` | `:95` | `:318, :557, :963, :1070, :1194, :1611, :1990, :2618, :2677, :2837` |
| `agents/character.py` | `:70` | `:3262` |
| `agents/narration.py` | `:70` | `:789` |
| `agents/background.py` | `:77` | `:574, :749, :948` |
| `agents/mapping.py` | `:24` | `:116` |

There is no attribute-style `common._agent_json(...)` call anywhere in the tree
(checked across all eight packages plus `agents/`), so no call site can ever
see the stub.

It is worse than inert, because there is also no positive control: the modules
under test do not import the name at all. `agents/perception.py:763` and
`agents/composer.py:69` each import a long list from `.common` and
`_agent_json` is in neither. The fixture's own docstring states the intent —
"it still fires if any perception code path ever reaches for a model again" —
and that is the one thing it cannot do. A regression written in this package's
own dominant idiom (module-level from-import; five of five role modules use it)
walks straight past. Both fixtures are `autouse=True`, so the guard is dead
across both entire files.

**Same bug, non-test copy: `tools/pose_drive.py:42`** — `common._agent_json =
_boom`, inert for the identical reason.

Contrast, so the distinction is on record rather than re-derived:
`tests/test_ambience.py:888` patches the *same name* and is **live**, because
`dressing/ambience.py:785,863` and `dressing/backdrops.py:940` do the
from-import **inside the calling function**, where it re-executes per call. The
discriminator across this repo is import scope, not module identity:
`dressing/`, `world/`, `web/`, `persist/` and `story/` overwhelmingly defer the
import into the function; `agents/` role modules do not. `agents/` is where
this class lives.

---

**T2. Four absence-assertions with a correct target and no positive control.**

Live patches, so not the T1 defect — but nothing in the repository ever
demonstrates the stub firing, so "it did not happen" is asserted without a case
that shows it *could*.

- `tests/test_commit_tail_producers.py:100-124` —
  `commit_memory_write._consolidate_committed_memories`. This is the case
  `AUDIT_COMMIT.md` §1.1 found and step 13 repointed; the target is now right
  (defined `persist/commit_memory_write.py:21`, read at `:229`). A grep over
  all of `tests/` shows nothing anywhere causes this stub to fire. The repoint
  restored the correct name without restoring the proof.
- `tests/test_backdrops.py:960-974` — counting wrapper on
  `dressing.backdrops.arrival_turn_for_room`, `assert walked == []`. Live
  (defined `:627`, called bare at `:680` in the same module); no test installs
  the wrapper on a path that does walk.
- `tests/test_memory_summary_windows.py:209-224` — `memory.embed_texts_meta` =
  `_boom`, `assert calls == []`. Live (`mind/memory.py:9`, read at `:962,
  :1224, :2444, :3890`). No test shows `restore_memory_summaries` reaching the
  embedder when a stored vector is absent, so "reuses the stored vector" is
  asserted with nothing that would consume one.
- `tests/test_ambience.py:1125-1135` — `amb.search_freesound` throw-lambda on
  the pinned-id path. Live (`dressing/ambience.py:1376`, called `:1444`); the
  positive calls at `:387/:406/:431` are direct, not through
  `search_candidates`, so the bypass path itself is never shown to route there.

---

**T3. `tests/test_offscreen_resolution.py:471-479` is a test that asserts
nothing.**

```python
def test_the_producer_is_wired_at_the_commit_tail(self):
    """Superseded by `tests/test_commit_tail_producers.py`. …"""
    import tests.test_commit_tail_producers  # noqa: F401  (the real cover)
```

Its body is a docstring and an import. It passes, it is counted, and it proves
nothing. The docstring is honest — it explains that the old version asserted a
substring of `inspect.getsource` and that `job = None if True else
schedule_profile_ticks(ctx)` keeps that text while never running the call,
which is a good statement of the class. But the replacement it points at is
T2's first entry: the "real cover" has the right target and no case that fires
it. Nothing named here is dishonest; the net effect is that a producer both
tests are about has one green stub and one uncalibrated guard.

---

### 3.2 The facade-monkeypatch sweep — a negative result, stated precisely

Every `monkeypatch.setattr` / `setattr` / `patch` in `tests/*.py` was resolved
to a `(module, attribute)` pair — **678 of 698 sites resolved** (the remainder
patch objects and dicts, not modules) — and each was classified by whether a
patch on that module attribute can reach a caller, distinguishing module-level
from-imports (bound once, unreachable) from function-level ones (re-executed
per call, reachable) and from the module's own self-reads.

**Result: zero mismatches of the `AUDIT_COMMIT` §1.2 shape.**

- **224 sites patch a name the target module RE-EXPORTS rather than defines**
  — the exact facade shape that made the `commit.py` split dangerous. All 224
  are effective: in every case the facade itself reads the name inside one of
  its own functions, so the patch lands. This includes all thirteen
  `commit_*` targets, `mind.memory.embed_texts_meta`,
  `story.importers.chat_complete`, `web.app.run_pipeline`,
  `agents.perception.active_disguises` and `agents.character.persona_of`.
- **Zero sites patch a name with no live reader anywhere in the engine.**
- The one genuine inert patch found in the whole suite is T1's `_agent_json`,
  which is not a facade re-export at all — it is a patch on the DEFINING
  module whose callers each hold their own binding. That is the *inverse* of
  the shape `AUDIT_COMMIT` warned about, which is presumably why the repoint
  pass did not look for it.

Worth recording as the general rule the two audits together establish: **a
module-attribute patch is inert exactly when every reader on the path under
test bound the name at module import time.** Whether the patched module is a
facade or the definer is irrelevant; only the reader's import scope decides.

One live consequence of that rule, not currently costing anything but one
refactor away from doing so: `llm/llm_quality.py:8-9` binds
`providers.chat_complete` at module level, so patching
`llm.providers.chat_complete` does **not** intercept `llm_quality`'s calls at
`:220/:316/:406/:496/:560`. The tests that need those correctly patch
`llm_quality.chat_complete` instead (`test_second_call_instrumentation`,
`test_strict_stage_validation`, `test_truncated_output_recovery`), and the
tests that patch `providers.chat_complete` are all after
`world/offscreen.py`'s function-level imports at `:1122, :1683, :1735`. The
two groups are correct today and there is nothing in the file to stop them
being swapped.

---

### 3.3 Tests that assert on SOURCE LAYOUT

**T4. 19 sites call `inspect.getsource(<module>)` — the module object, not a
function.**

`AUDIT_COMMIT.md` §1.2 named this class and repointed nine of them to function
objects, which survive a move because the facade re-exports the same object.
Nineteen module-level ones remain:

```
test_attentional_capacity.py:233   test_barren_progress.py:131,145,177
test_cache_affinity.py:110         test_carriers.py:158
test_character_self_knowledge.py:223  test_coerce_hardening.py:240
test_extension_director_context.py:317  test_memory_read_seam.py:243
test_no_quality_redo.py:33,63      test_offscreen_life.py:233
test_project_tier_reachable.py:114,123  test_relationship_events.py:189
test_routines.py:149               test_speech_mouth_engagement.py:194
test_story_view.py:786
```

None is broken today: the modules they pin (`agents/character.py`,
`llm/providers.py`, `story/carriers.py`, `mind/memory.py`, `story/scene.py`,
`world/routines.py`, `persist/chat_archive.py`, `web/story_view.py`) have not
been split. The one on a split family is
`test_extension_director_context.py:317`, `inspect.getsource(director)`, and it
still passes because all three
`_extension_director_payload(ctx, payload, phase="…")` call sites remain in
`agents/director.py` (`:316, :555, :2605`) — only the function itself moved, to
`agents/director_views.py:117`.

Its two failure modes are worth separating, because they point opposite ways.
Moving a call site into a `director_*` sibling makes it go **red** for a
non-behavioural reason — loud, and a false alarm. Adding a **fourth** path that
needs the seam and does not get one leaves it **green**, because the assertion
is three membership tests and never a completeness claim — and completeness is
what the docstring says the test is for ("whether any Director call ever calls
it"). It also matches the exact keyword spelling, so a line-wrap breaks it.

---

**T5. 57 assertions assert a substring is ABSENT from source text.**

The two failure modes are different and both matter. A positive
`inspect.getsource` assertion fails loudly on a rename. A **negative** one goes
vacuously green: the string is gone because the thing was renamed, not because
it was removed, and the test cannot tell the difference.

Checked all 57 pinned strings against the whole repository. **Twenty-two
appear nowhere in any source file in any spelling** — e.g. `move_repeat_screen`,
`for _was, _now in _contact_report`, `["message"]["content"]`,
`top - runner >= 2`, `dormant_actors`, `1-2 sentences`, `projects.append`,
`0.08 * effective_importance(mem)`, `Initial outfit — clothing only`. Each is
a guard that has no way to distinguish "correctly removed" from "renamed and
back under another name". That is inherent to the technique rather than a
defect in any one test, and it is the reason
`tests/test_offscreen_resolution.py:471`'s docstring gives for retiring its own
source-substring assertion — a good instinct that was applied once and not to
the class.

The ones that are correctly scoped and do have live positive controls were
checked and are fine, including
`tests/test_pipeline_perspectives.py:209` (`_stream_parallel(bus, jobs,
holders)` exists at `agents/runtime.py:466`, correctly asserted absent from
`_run_pipeline`) and `tests/test_offscreen_resolution.py:488-490`
(`jobs.cancel` exists at `persist/checkpoints.py:304`, correctly asserted
absent from `persist/commit.py`, `web/app.py` and `agents/runtime.py`).

---

### 3.4 The fast tier

**T6. The `slow` marker keys on a FIXTURE NAME, so a database-backed test that
builds its own database is in the fast tier.**

`tests/conftest.py:20-22`: `if "temp_db" in item.fixturenames`. Four tests take
no `temp_db`, create their own temp file, and call `db.configure()` +
`db.init()` directly:

- `tests/test_fable_audit_migrations.py:40, 66, 83` (via the local
  `fresh_db_path` fixture at `:28`)
- `tests/test_world_entity_chat_scope.py:72`

All four restore `db.DB` in a `finally`, so nothing leaks. But each runs a full
`db.init()` — the ~117-DDL, fsync-bound call `conftest.py:28-38` documents as
having been the dominant cost of the whole suite — and each does it with
`tempfile.mkstemp(suffix=".db")` and **no `dir=_TMP_DIR`**, so they land on the
platter rather than on the tmpfs the fixture was moved to precisely to avoid
that. They are in `make test-fast`, which is documented as "deselects every
test that touches the database".

---

**T7. The fast tier's stated invariant is no longer checkable, and the
documented way to check it no longer does anything.**

`AGENTS.md` and `docs/guides/TESTING.md` both state the rule: "A test intended
for `make test-fast` must not depend on another test having initialized
`engine.db`."

`tests/conftest.py:55-84` now calls `_redirect_default_database()` **at
conftest import**, before any test module is imported, and that function does
`db.configure(path); db.init()` on a fresh scratch file. It exists for an
excellent reason, spelled out in its docstring — a module-level import can
reach `db.q()` during collection, and on a developer's machine that opened the
**live `engine.db`**. That fix is correct and should stay.

Its side effect is that **every test, fast tier included, now runs against a
fully initialised database.** So a fast-tier test that quietly depends on one
passes under `make test-fast` as readily as under the full suite, and nothing
anywhere would notice the rule being broken. The invariant survives only as a
sentence in two guides.

`TESTING.md` also prescribes the verification: "Validate changes to tiering
with `ENGINE_DB` pointing at a new path so a populated development database
cannot mask missing initialization." `core/db.py:95` reads `ENGINE_DB` at
import — and then `_redirect_default_database()` overrides it unconditionally
with its own temp path and initialises it. The prescribed procedure cannot
surface a missing initialization, because conftest supplies one either way.

---

### 3.5 Duplicated names, and empty tests

**T8. No live hits — reported as a negative result with the blind spots
named.** An AST pass over 627 files (549 the guard sees, 78 it does not),
covering 1,087 classes, 4,079 methods and 532 nested defs, found **zero**
duplicate class methods, zero nested-def collisions, zero def-shadowed-by-
assignment, zero duplicate top-level symbols in the 78 unscanned files, zero
duplicate constant dict keys outside the scan set, zero duplicate set-literal
elements (`ast.Set` is not checked at all), and zero duplicate keys in the
repository's JSON (language packs, extension manifests — no guard exists there
and `json.loads` silently keeps the last). The detector was self-tested against
a synthetic file planting one of each, and all five patterns fired, so the
zeros are the tree's and not the scanner's. The blind spots themselves are
S4 above.

**T9. No empty or zero-collecting test files.** All 440 `test_*.py` collect at
least one test; none is imports-only; none uses a module-level skip; no test
body is a bare `pass`. Ten tests contain no literal `assert`/`raises`
(`test_output_guard.py:17,64,71,91`, `test_output_guard_throttle.py:27`,
`test_pipeline_safety.py:143`, `test_stage_b_recompute.py:37,74`,
`test_extension_documents.py:270`, `test_firewall_across_scripts.py:188`);
four were spot-checked and assert through a helper or are deliberate
assert-by-not-raising invariant tests. Not defects. `test_offscreen_resolution.py:471`
(T3) is the one genuinely assertion-free test and was found by reading, not by
this scan.

---

## 4. Unverified suspicions

Everything above was verified. These were not, and are recorded so the next
reader knows they were considered rather than missed.

- **Payload SHAPE drift in the drivers.** The hand-authored dicts in
  `contract_bench.PAYLOADS`, `creation_probe.PAYLOADS` and `scale_probe`'s
  scene were checked for step keys, prompt ids and role names only, not
  field-by-field against current `llm/schemas.py` requirements. A payload that
  parses but no longer means what the harness thinks would look identical to a
  working one.
- **`world.scene` blob-key drift** inside driver-authored `state_diff`
  fragments. The `wget`/`wset` key names are all valid (`crowds`,
  `living_world`, `subject_last_seen`, `scene`, `known`, `dialogue_config`,
  `simulation_clock`, `standing_intentions`); the diff channel names inside
  them were not exhaustively checked against the six specialists' channel sets.
- **Runtime-only conditions** in every driver — API keys, provider rows, model
  availability, rate limits — are out of scope, because nothing was executed.
- **Database columns** were checked against the `CREATE TABLE`/`ALTER TABLE`
  text in `core/db.py`, never against `engine.db`, which was read only through
  `ls` for this audit and never opened.
- **Test name-versus-body mismatches beyond the known case.** A systematic
  sweep of the ~7,289 test names against their bodies was started and is not
  complete; nothing is claimed here. The known instance —
  `test_below_dialogue_threshold_stays_tracked`, which seeded two dialogue
  turns and asserted on the ADDRESSED threshold — was fixed in `e8568d4` and is
  not re-reported.
