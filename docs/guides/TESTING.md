# Testing and dependency policy

Sonder Engine keeps the ordinary local install small while offering three
deliberately different verification levels.

## Test commands

```bash
make test-full     # every Python regression test, in parallel
make test-lf       # last-failed first, then the rest -- the fix-verify loop
make test-browser  # optional Chromium behavior tests
make check-fast    # compile, structure/map freshness, then the full suite
make check         # compile, code map, structure checks, then the full suite
make test-fast     # CI matrix-breadth only -- see the warning below
```

`make test` remains an alias for the full Python suite. **Both `check` and
`check-fast` now run every test**; they differ only in that `check`
regenerates `docs/CODE_MAP.md` while `check-fast` verifies the copy on disk is
current.

### The full tier runs in parallel, and the worker count is not `auto` by luck

Measured 2026-08-20 on 8,566 tests, 8 physical cores / 16 logical:

| workers | wall |
|---|---|
| serial | 220s |
| `-n 4` | 117s |
| **`-n 8`** | **76s** |
| `-n 16` | 87s |

**The curve turns back up past the PHYSICAL core count.** The engine keeps
daemon threads alive across tests -- `memory_write`'s embedding repair thread
is the loud one -- so one worker per hardware thread oversubscribes them and
loses more than the extra parallelism wins.

`JOBS ?= auto` in the Makefile is xdist's physical-core count, **but only when
`psutil` is importable**; without it `auto` silently means LOGICAL cores, which
on this machine is 16 -- the wrong side of the knee. That is the entire reason
`psutil` is a dev dependency. Override with `make test JOBS=4`, or `JOBS=0`
for the serial run (also `make test-serial`).

Parallel isolation holds by construction rather than by arrangement:
`tests/helpers.scratch_db_path()` is `tempfile.mkstemp`, and
`tests/conftest.py` redirects `db.DB` at conftest IMPORT -- which happens once
per worker PROCESS. So every worker gets its own scratch database before it
collects a single test, and no worker can reach another's.

**Reach for `JOBS=0` when a failure is confusing.** xdist interleaves workers,
so the live log of the test that failed is not shown beside its traceback.

When `pytest-xdist` is not installed for whatever `python` resolves to, the
tier degrades to a serial run and says so, rather than failing on
`unrecognized arguments: -n`. A PEP 668 system interpreter cannot be
pip-installed into without `--break-system-packages`, and a developer who did
nothing wrong should not meet a cryptic argument error.

### Why the fast tier is no longer a tier you should use

Tests requesting the shared `temp_db` fixture are still marked `slow` during
collection, and `make test-fast` still deselects them. Do not reach for it to
check your own work: it deselects **every database-backed test file** —
roughly a quarter of the suite — including the persistence and
information-firewall suites, the invariants this repo exists to keep honest.
No count is written down here on purpose: the numbers in this document were
re-synced twice and had drifted again within a day both times. `pytest -q`
reports the total, and `pytest -q -m "not slow" --collect-only` reports what
this tier skips; a literal in prose can only be wrong. **Nothing runs it any more.** It
was kept for the CI matrix-breadth run, but that job now runs `make check-fast`
— the whole suite — on both interpreters, so `test-fast` has no consumer left
in `.github/workflows/ci.yml`. It survives only as a manual escape hatch for a
machine with no usable `/dev/shm`.

That split was a real trade when it was written. `db.init()` is fsync-bound —
`executescript(SCHEMA)` auto-commits ~117 DDL statements against a brand-new
file — and a `temp_db` setup measured 1.2–1.6s on a loaded checkout against
test bodies of 0.02–0.10s. That one call was ~90% of the suite's wall clock.

Moving the fixture's temp directory to tmpfs (`tests/helpers.py`,
`fast_tmp_dir`; a test that builds its own database calls `scratch_db_path`)
removed it: **15m35s → 36s for all 3799 tests**, measured at
the time. The suite has since grown by roughly a factor of two at the same
per-test cost.
Nothing about the database changed — same schema, same WAL, same isolation,
same per-test file; only the storage backing moved, so no test can tell the
difference. `ENGINE_TEST_TMPDIR` overrides the location, and platforms without
`/dev/shm` fall back to tempfile's default and are merely slow, not wrong.

Apply the `slow` marker to a new test only when measured cost shows it
exercises similarly expensive concurrency or integration boundaries. Never mark
a test slow because it is inconvenient or intermittently failing.

### On running only the tests near what you changed

Investigated and deliberately **not** built. A subsystem partition of the test
files was designed and simulated against 300 real commits: it would run a
median 42% of the suite, ~2x, at the cost of a mapping table that must be
maintained forever and that leaks in ways nothing detects — most sharply for
tests that couple by `monkeypatch.setattr("agents.director._foo", ...)`, a
string path no import graph can see. Against a full suite in the tens of
seconds that is not a trade worth making. Use `make test-lf` while iterating and run everything
before you are done.

A fast-tier test must also be order-independent on a clean checkout. The
database half of that rule is now enforced structurally rather than by
discipline: `tests/conftest.py` calls `_redirect_default_database()` at module
IMPORT — before pytest imports a single test module, because collection itself
can reach the database through a module-level import — which points `db.DB` at
a scratch file and runs `db.init()` on it. No test, in either tier, can open
the developer's `engine.db`, and none needs another test to have initialized
one. Say what changed rather than what the rule used to warn about: the failure
it guarded (a prompt test whose result depended on a checkbox in the working
copy's own provider rows) is no longer reachable.

What is still worth doing is the other half, which was never about the file:
prefer built-in constants or an explicit stub to a runtime settings/prompt
lookup when settings behavior is not what the test covers, so the test says
what it depends on. `ENGINE_DB` still overrides the default path for anyone
validating tiering by hand.

Information-flow changes require adversarial tests, not only happy-path schema
tests. For perception or cognition payloads, include hostile model output that
tries to smuggle raw intent/private grounds through new fields and cross-body
fixtures that place distinctive secret vitals on another character. Assert the
forbidden marker is absent from both the model payload and persisted result.

The browser tests live outside the default `tests/` collection. This keeps
`pip install -r requirements-dev.txt` and all normal Python checks independent
of browser binaries:

```bash
python -m pip install -c constraints.txt -r requirements-browser.txt
python -m playwright install chromium
make test-browser
```

The browser layer uses Playwright against the repository's actual unbundled
ES-module entry and import graph. API requests are intercepted in focused UI tests, so
tests can exercise DOM behavior without provider credentials or a populated
database. Add tests here for behavior that static source assertions cannot
prove: event wiring, modal state, navigation races, persistence in browser
storage, focus, and accessibility-visible state.

## Dependency policy

`pyproject.toml` and the requirements files declare supported compatibility
ranges. `constraints.txt` pins the direct dependency set exercised in CI plus
Starlette, whose version is tightly coupled to FastAPI's test client.
This separates two useful promises:

- installing without a constraints file receives compatible maintenance
  updates within the declared major-version bounds;
- installing with `-c constraints.txt` reproduces the CI baseline.

**A declared FLOOR is a promise the version works, and until 2026-08-19 five of
the six were promises nobody had tested.** Every install path in the project —
both launchers, the README's by-hand recipe, and all three CI jobs — passes
`-c constraints.txt`, so the pin is what gets installed and the minimum is
reachable only in a pre-existing environment. `fastapi>=0.101`, `httpx>=0.24`,
`numpy>=1.26`, `requests>=2.31` and `uvicorn>=0.27` had therefore never been
run against this code by anything, and `numpy>=1.26` could not even install on
3.13. The floors now name the version CI actually installs. `pydantic` is the
deliberate exception and stays wide, because both majors genuinely run.

A minimum-resolution CI lane (`pip install --resolution=lowest`) was considered
and **not** built: it would add a fourth job and a second dependency
resolution to maintain in order to test a configuration nothing here produces.
Raising the floors to what is measured costs nothing and makes the declaration
true, which is the honest half of the same fix. If a floor is ever lowered
again, that is a claim, and it wants evidence.

When updating dependencies, change the range only if support policy changes,
refresh the corresponding direct pin in `constraints.txt`, run
`python -m pip check`, then run the fast, full, and browser tiers. The
Playwright packages are an optional extra and never belong in
`requirements-dev.txt`; browser binaries are installed explicitly.

`pydantic>=1.10.13,<3` spans two majors, and the range is a real promise:
`llm/schemas.py` reads a field's declared shape through `_declared`, which has one
branch per major, because Pydantic 2 removed `ModelField` entirely. Anything
that needs to know what a field declared goes through there. Reaching into a
version-specific internal instead is how `pydantic.fields.SHAPE_LIST` reached
`import` scope and made the engine refuse to start for anyone whose install
resolved to 2.x — invisibly, because a dev machine on 1.10 cannot see it, and
`@validator("*", pre=True)` with a `field` parameter is a hard error on 2.x for
the same reason.

### A local green is not evidence about the shipped stack

**`make check` runs whatever `python` resolves to, and that is very unlikely to
be the pinned baseline.** Measured on the owner's own machine, 2026-08-18: the
system interpreter that runs `make check` carried **Pydantic 1.10.14 and NumPy
1.26.4**, while `.venv` — which is what both launchers build and what every
player's engine serves from, and what `constraints.txt` pins — carried
**Pydantic 2.11.7 and NumPy 2.2.6**. Two defects were live in that gap at once,
and the suite was green through both:

- `agents/director_scopes._schema_list_channels` read `field.outer_type_`,
  which exists only on Pydantic 1. On the shipped major it returned the empty
  set, so `_LIST_DELEGATED` was empty and every one of the seventeen op-list
  Director channels — `contact_ops`, `introductions`, `crowd_ops`,
  `remove_rooms` — was coerced to `{}`: dispatched, paid for, and discarded
  without a word.
- `tests/test_lore_blind_scoring.py` built its fixtures as
  `np.ones(dims, dtype=np.float32) / np.sqrt(dims)`, which stays float32 under
  NumPy 1's value-based casting and becomes float64 under NumPy 2's NEP 50 — so
  on the shipped NumPy the buffer held twice the values the test claimed, and
  every dimension-mismatch assertion in the file measured the fixture instead of
  the engine.

Neither was found here. Both were found by the Directive team running the
declared CI matrix against `reorganization`. Two structural guards now exist —
`check_pydantic_major_reads_are_owned` confines major-specific field attributes
to `llm/schemas.py`, and `check_minimum_python_syntax` catches source the
declared minimum interpreter cannot parse — but a guard covers the class it
names and nothing else.

**Before believing a green run means the engine works, run the suite once on
the pinned stack:**

```bash
python3.12 -m venv /tmp/sonder-ci && \
  /tmp/sonder-ci/bin/pip install -c constraints.txt -r requirements-dev.txt && \
  /tmp/sonder-ci/bin/python -m pytest -q
```

CI does this on every push, and CI is the authority. The local gate is a fast
approximation of it, and the approximation is exactly as wide as the difference
between two dependency resolutions.

Because the constraints pin is 2.x, the other side of that range needs its own
job: `pydantic1` installs the pinned set, downgrades past the constraint, and
runs the suite. It exists because a range is only a promise if something
checks it.

It ran only the fast tier until alpha 6.6, and that hid the failure running the
other way. `llm/schemas.py` lets an item model name its own subject slot
(`GoalImpact._subject_field`), read back with a bare `getattr` — a plain string
on 1.x, an unhashable `ModelPrivateAttr` on 2.x, where the next line raises
`TypeError`. The 1.x job was green, so the red 2.x test read as "the 1.x side
is the special one" rather than "the pinned major is broken", and the feature
never once ran in a default install. Both directions run everything now, which
is affordable at ~40s. **Symmetry is the point: a job that covers one major
more thoroughly than the other will mislead you about which one is wrong.**

Worth being exact about how the 1.x-only import above survived, because the
lesson is not the one it looks like: **CI caught it immediately.** The next push
went from a passing fast tier to 160 collection errors, and stayed there through
five more pushes across a day. Nobody read the result. A job nobody looks at is
weaker than no job, because it also supplies the belief that something is
checking. Read the run, or nothing above this line matters.

The two majors also differ in *leniency*, not only in API, and that difference
is the engine's business rather than Pydantic's: 1.x coerced a number into a
`str` field, 2.x refuses it and discards the beat. `_lenient_coerce` now does
that coercion itself so both behave alike. When changing `_declared` or
`_lenient_coerce`, check the majors against each other rather than trusting one
— the cheap version is to dump every field's coercion under both interpreters
and diff, which is how the bare-`list` divergence was caught (v1 treats a bare
`list` as a singleton, v2's `get_origin` does not).

Done exhaustively — every field of every `LenientModel` × a corpus of wrong
spellings, run under both interpreters and diffed — that check found 311
payloads that parsed on 1.x and failed on 2.x, in three families the
field-level coercion could not see:

- `[]` and `""` where a **dict or nested model** was declared, which 1.x
  accepted everywhere for free because `dict([]) == dict("") == {}`;
- a wrongly-typed **list element** or **dict value**, which is not a field of
  anything, so no per-field validator ever reaches it;
- a fractional float where an `int` was declared, which 1.x truncated.

The lesson generalises past Pydantic: **the leniency is per-field, and content
does not only arrive in fields.** A new coercion should be asked whether the
same spelling can arrive one level down, in a `list[X]` element or a
`dict[str, X]` value — `_coerce_member` is where that answer goes.

None of these are visible to the suite unless a test feeds the wrong spelling
deliberately: the full suite passed on both majors while all 311 diverged, and
the cost is not a warning but a *silently unnormalized step*, because
`validate_llm_output` returns the raw payload when validation fails. One
`"appraisal": []` costs that step every default, flatten and wrap the rest of
the layer would have applied.

The same exposure exists outside `llm/schemas.py`. `story/character_schema.py`'s profile
models are plain `BaseModel`s that were relying on 1.x to turn a number into
prose, which made a card with `"expression": 3` a 500 on save and an unreadable
character on every later turn — on the read path of every accessor, because
`_normalize_psychology` validates with no `try`. They now share
`schemas.coerce_to_declared`, and so does `persist/chat_archive.py`, whose import gate
was refusing `world: []` outright while the code behind it read
`dict(data.get("world") or {})` — a gate stricter than its own consumer, which
1.x hid by coercing for free. Any new model anywhere in the repo inherits the
same obligation.

Two remaining differences are deliberate rather than fixed:

- `LoreOp.book_id` and `BookOp.parent_id` are `Union[int, str]` on purpose (an
  existing book's id **or** a same-turn temp handle), and the majors resolve
  that union differently — 1.x coerces `"77"` to `77`, 2.x's smart union keeps
  the string. Both consumers in `persist/commit.py` now resolve either spelling to the
  same book, so the outcome agrees; normalising the *type* at the schema
  boundary would make a digit-shaped temp handle collide with a real id, which
  is a new failure mode traded for cosmetic agreement.
- `auth_routes.AuthCredentials` rejects a non-string username or password on
  2.x where 1.x coerced it. That is a typed auth boundary doing its job; the
  laxity was never intended, and a browser form cannot produce it.

`pydantic>=1.10.13,<3` also has to stay honest about the `<3`. `Extra`,
`parse_obj` and `.dict()` are deprecated on 2.x and gone in 3.x, and no
production module uses them any more — six test assertions still call
`.dict()` (`test_scale.py`, `test_body_position.py`, `test_light_and_survival.py`,
`test_containment.py`) and are the whole remaining deprecation-warning tail.
`class Config` and `@validator` remain everywhere, because their replacements
do not exist on 1.x; those are what to migrate first if the ceiling moves.

## CI layout

GitHub Actions (`.github/workflows/ci.yml`) runs three jobs:

1. `fast` — `make check-fast` on Python 3.11, 3.12 **and 3.13**. Named `fast`
   for history, because it is a required check elsewhere; it has not been the
   reduced tier since the databases moved to tmpfs, and compiles, runs the
   structure/map checks, and runs **every** test on every interpreter. The
   separate `full` job that used to follow it was a strict subset and was
   deleted.

   3.13 was added 2026-08-19 and had never been run by any gate. It was inside
   `requires-python` (`>=3.11,<3.14`), inside both launchers' candidate lists,
   and inside `tests/test_launcher_python_range.py`'s `SUPPORTED` — and outside
   this matrix. Both launchers are ordered NEWEST-FIRST, so 3.13 is the
   interpreter a fresh player is most likely to land on, which made it the
   worst possible one to leave untested. The matrix, `requires-python` and the
   two launcher lists are now held equal by
   `tools/project_check.py::check_python_version_agreement`; a version that
   drifts out of any of the four fails `make structure`.
2. `pydantic1` — `make test-full` on Python 3.12 with Pydantic downgraded past
   the constraint, covering the half of the declared range the pin does not.
   It asserts the major it is actually running before testing.
3. `browser` — the optional Chromium behavior suite once on Python 3.12.

Jobs 2 and 3 need job 1, so a broken build fails once rather than three times.
**Both majors run the whole suite**: the asymmetry — 1.x on the fast tier only
— is exactly what hid `_subject_field`, and restoring it would hide the next
one.


---

## Assertions that read source instead of running it

*(Moved out of `docs/UNBUILT.md` §1.64 on 2026-08-19. It is test-instrument
hygiene, so it belongs here rather than in a defect register — but see fault 3:
the class can counterfeit a dependency-resolution failure, which is why it is
worth a section rather than a line.)*

**The fix is always the same: assert against BEHAVIOUR, not source text.**

**Census 2026-08-18, re-counted 2026-08-19**: 34 negative source-substring
assertions against PYTHON source across 22 test files, plus 131
`inspect.getsource` calls of which 21 pass a whole MODULE. The numbers moved
between the two counts (128→131 calls, 18→22 files) because test files landed
in between, and a third count by a different method got 125. **The exact
figures are not reproducible and the magnitude is.** Separately, negative
assertions in ten files read a non-Python asset — a `.js`, `.html`, `.css` or
`.sh` file — and those are a different thing, treated below.

Three faults, and only the first is the one usually noticed.

1. **It passes for code that does the wrong thing.** "This path makes no model
   call" written as `"chat_complete" not in source` holds for an aliased
   import, for a call through `llm_quality.complete_validated_json`, and for a
   provider reached through a module the file already imports. It is also
   false-POSITIVE on the word appearing in a comment, which is how a correct
   file gets a red test and somebody deletes the prose instead of the import.
2. **It fails a refactor that changed nothing.** Extracting a condition into a
   named predicate — the ordinary tidy-up — breaks an assertion on the
   condition's literal spelling.
3. **It is NON-DETERMINISTIC, which is the fault that makes this a defect
   rather than a preference.** `inspect.getsource` resolves the source through
   `linecache`, reading the file from disk AT ASSERT TIME, while the module
   object was imported earlier. Anything editing that file concurrently — a
   second agent, an editor writing on save, a `git checkout` in another
   worktree — yields a mismatch: `getsource` returns the WRONG function's text and the
   assertion fails on a defect that does not exist. The test fails once and
   passes on re-run, and passes in isolation always.

   Measured six times. Two agents hit it independently during the 2026-08-18
   repair wave, in different files, and both first read it as a real failure.
   Three more in one session on 2026-08-19, each from editing a module while a
   gate was running:

   - `tests/test_perception_self_narration.py::test_every_perception_stage_applies_the_guard`
     sliced `_composer_company` while asserting about `_composer_tripwires`
     (edit in flight: `agents/perception.py`).
   - `tests/test_pipeline_audit.py::TestNarrationPersonDeferredToCommit::test_commit_all_wires_the_domain`
     — same shape (edit in flight: `persist/commit.py`).
   - `tests/test_crowds.py::TestACrowdWalksTheGraphEveryoneElseWalks::test_there_is_no_second_pathfinder`
     asserted `"passable_neighbors(scene)" in getsource(passable_route_exists)`
     and got the source of `passable_neighbors` itself (edit in flight:
     `world/spatial_routing.py`, where ~45 lines had just been inserted above
     it).

   **Where the third one bit is the argument.** It failed on the pinned-venv
   run while `make check` on the same tree was green — which is exactly the
   signature this guide teaches you to read as a dependency-resolution defect.
   It was not one. A test instrument that can COUNTERFEIT the one signal the
   project treats as most serious is more than hygiene.

**Two instruments now exist, and the row is what remains after using them.**

- `tests/model_seams.py` seals every provider door (`chat_complete`,
  `embed_texts`, `embed_texts_meta`, `complete_validated_json`, `_agent_json`)
  including the aliases callers bound at import time, and raises from inside
  the call naming which door opened. A "makes no model call" claim is now
  DRIVEN. `tests/test_model_seams.py` proves each door is really shut by
  opening it, because a sealer that silently misses one turns a weak assertion
  into a false one.
- Where the property genuinely is about the module rather than about a run,
  the assertion goes against the PARSED TREE — imported names including the
  original behind an `as`, called names, string constants, attribute access —
  which answers the question the substring was approximating and is immune to
  comments, spelling and formatting.

**Converted so far**: `test_style_guide.py` (three assertions, driven through
the payload), `test_offscreen_reactive.py`, `test_offscreen_resolution.py`'s
seeded draw (both sealed and driven), `test_perception_has_no_model.py`,
`test_story_view.py`'s layering rule and
`test_offscreen_agent_context.py`'s fail-closed allowlist (all four to AST).

Institutions/upkeep has a separate narrow seam in
`tests/test_charter_runtime.py`: run it with the nearest pure Charter tests
before the broader off-screen suite. It pins JSON-safe politics, exact blame
ownership, frame isolation, epoch/rewind-safe landing, the scheduled-
consequence handoff, and the per-presence knowledge aperture. The longer
population/month simulations are deliberately **not** pytest tests. Run
`make charter-audit` when investigating Charter realism, scale, convergence,
famine/recovery, or replay under load; its 49 scenarios live under
`tools/charter_audit_*.py` and take roughly six minutes serially. Default
pytest uses `tests/test_charter_simulation_smoke.py` to prove that a small
institution advances, reports failure and replays deterministically. Measured
at the split: the Charter pytest family fell from 342 seconds to 8.1 seconds.
Do not move a population experiment back under `tests/` merely because it has
assertions—an executable audit can and should fail too.
`tests/test_charter_identity.py` pins thousand-body deterministic naming,
non-renaming after profile edits/insertion, title aliases and permanent color
seeds. `tests/test_charter_name_learning.py` pins the delivered-view and
co-location firewall for players and characters, including an indexed
five-thousand-person lookup. Dialogue-color and promotion coverage pins the
same color before and after a Charter body becomes registered cast.

`tests/test_charter_social_economy.py` pins local-only judgment, hearer-only
commitments, scarcity pricing, hierarchical order delivery and stock effects.
`tests/test_fable_town.py` pins qualitative deterministic closure, planned/live
graph composition, prose-free fringe materialization, intervention firewalls,
presim determinism, historian citation grounding, and a rich recent-life
handoff as 10–16 independently keyed episode rows rather than one packet.
`tests/test_charter_identity.py` also pins legacy full-name recovery for formal
formats such as `Dr. {family}`, so named residents cannot collapse to “Dr.”.
Keep multi-month,
hundred-person immersion and fire-rate scenarios in `tools/`; pytest proves
the mechanisms on compact deterministic fixtures and must not call a model.
`tests/test_charter_routes.py` additionally pins selected-lore subtree scope
and additive, collision-safe generation without re-aging an existing Charter.
`tests/test_greetings.py` pins that selected generation lands before turn 0,
reads the selected library subtree, and grounds rooms in its story-local copy.
`tests/test_character_history_routing.py` is the compact topology tripwire: an
itinerant fixture cannot become a Charter resident, explicit residence and a
bounded moving institution can, competence alone cannot, uncited canon is
dropped, generated journeys remain ordered and identified, and private habits
enter only their owner's bounded experience. Keep long journey-quality and
multi-month autobiography evaluation in tools; pytest proves authority,
grounding and ordering without calling a model.

**Left, and left honestly.** A source assertion that is the only available
instrument is a different thing from one that was merely easier, and both
kinds remain:

- **The only instrument.** The 19 assertions against `.js`, `.html`, `.css`
  and `.sh` files (`test_ui_themes.py`, the three `test_frontend_*` files,
  `test_guest_page.py`, `test_provider_fallbacks.py`,
  `test_launcher_python_range.py`). A Python suite cannot execute a stylesheet
  or a shell installer, so reading it IS the test; there is also no imported
  module for the read to disagree with, so fault 3 does not apply to them at
  all. These should be left alone.
- **Merely easier**, and still open: the 34 Python ones, chiefly
  `test_crowds.py` (5), `test_offscreen_resolution.py` (6),
  `test_offscreen_life.py` (3), `test_launcher_python_range.py` (3),
  `test_body_position.py` (2), `test_pipeline_audit_leak_gaps.py` (2),
  `test_living_world.py` (2). Each needs its own judgement about what the
  property IS, which is why this is a row rather than a sweep — and a sweep is
  what would produce 34 tests that pass and mean nothing.

**No new one should be written.** Both instruments are in `tests/`, and a
third option exists that beats either: give the code the seam the test wants.
`tests/test_carriers.py` keeps one source assertion and says so in its own
docstring — `prepare_memory_commit` offers no way to observe which clock it
stamped without running a commit, and inventing that seam belongs to whoever
owns `persist/`. That is the right shape for a residual: named, reasoned, and
pointing at the change that would remove it.
