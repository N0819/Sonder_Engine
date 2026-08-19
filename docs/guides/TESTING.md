# Testing and dependency policy

Sonder Engine keeps the ordinary local install small while offering three
deliberately different verification levels.

## Test commands

```bash
make test-full     # every Python regression test (6329 tests, ~74s)
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

### Why the fast tier is no longer a tier you should use

Tests requesting the shared `temp_db` fixture are still marked `slow` during
collection, and `make test-fast` still deselects them. Do not reach for it to
check your own work: it deselects **1841 of 6329 tests, emptying 119 of 391
test files**, including the persistence and information-firewall suites — the
invariants this repo exists to keep honest. **Nothing runs it any more.** It
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
the time. The suite has since grown to 6329 tests and ~74s, which is the same
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
HTML and script order. API requests are intercepted in focused UI tests, so
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

1. `fast` — `make check-fast` on Python 3.11 and 3.12. Named `fast` for
   history, because it is a required check elsewhere; it has not been the
   reduced tier since the databases moved to tmpfs, and compiles, runs the
   structure/map checks, and runs **every** test on both interpreters. The
   separate `full` job that used to follow it was a strict subset and was
   deleted.
2. `pydantic1` — `make test-full` on Python 3.12 with Pydantic downgraded past
   the constraint, covering the half of the declared range the pin does not.
   It asserts the major it is actually running before testing.
3. `browser` — the optional Chromium behavior suite once on Python 3.12.

Jobs 2 and 3 need job 1, so a broken build fails once rather than three times.
**Both majors run the whole suite**: the asymmetry — 1.x on the fast tier only
— is exactly what hid `_subject_field`, and restoring it would hide the next
one.
