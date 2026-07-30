# Testing and dependency policy

Sonder Engine keeps the ordinary local install small while offering three
deliberately different verification levels.

## Test commands

```bash
make test-fast     # broad Python suite, excluding explicitly marked slow tests
make test-full     # every Python regression test
make test-browser  # optional Chromium behavior tests
make check-fast    # compile, structure/map freshness, then test-fast
make check         # compile, code map, structure checks, then test-full
```

`make test` remains an alias for the full Python suite. Tests requesting the
shared `temp_db` fixture are marked `slow` during collection: an instrumented
local run measured their isolated database setup at roughly 1.2--1.6 seconds
per test. This makes the fast tier a broad set of pure contracts, schemas,
spatial rules, prompt boundaries, and frontend guards while the full tier
retains every persistence invariant. Other tests should receive the `slow`
marker only when measured cost shows that they exercise similarly expensive
concurrency or integration boundaries. Never mark a test slow merely because
it is inconvenient or intermittently failing.

A fast-tier test must also be order-independent on a clean checkout. Do not let
pure prompt or schema tests call runtime settings helpers that implicitly open
`engine.db`; import built-in constants directly or stub the lookup when
database behavior is not what the test covers. Validate changes to tiering with
`ENGINE_DB` pointing at a new path so a populated development database cannot
mask missing initialization.

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
`schemas.py` reads a field's declared shape through `_declared`, which has one
branch per major, because Pydantic 2 removed `ModelField` entirely. Anything
that needs to know what a field declared goes through there. Reaching into a
version-specific internal instead is how `pydantic.fields.SHAPE_LIST` reached
`import` scope and made the engine refuse to start for anyone whose install
resolved to 2.x — invisibly, because a dev machine on 1.10 cannot see it, and
`@validator("*", pre=True)` with a `field` parameter is a hard error on 2.x for
the same reason.

Because the constraints pin is 2.x, the other side of that range needs its own
job: `pydantic1` installs the pinned set, downgrades past the constraint, and
runs the fast tier. It exists because a range is only a promise if something
checks it.

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

The same exposure exists outside `schemas.py`. `character_schema.py`'s profile
models are plain `BaseModel`s that were relying on 1.x to turn a number into
prose, which made a card with `"expression": 3` a 500 on save and an unreadable
character on every later turn — on the read path of every accessor, because
`_normalize_psychology` validates with no `try`. They now share
`schemas.coerce_to_declared`, and so does `chat_archive.py`, whose import gate
was refusing `world: []` outright while the code behind it read
`dict(data.get("world") or {})` — a gate stricter than its own consumer, which
1.x hid by coercing for free. Any new model anywhere in the repo inherits the
same obligation.

Two remaining differences are deliberate rather than fixed:

- `LoreOp.book_id` and `BookOp.parent_id` are `Union[int, str]` on purpose (an
  existing book's id **or** a same-turn temp handle), and the majors resolve
  that union differently — 1.x coerces `"77"` to `77`, 2.x's smart union keeps
  the string. Both consumers in `commit.py` now resolve either spelling to the
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

GitHub Actions runs:

1. fast checks on Python 3.11 and 3.12;
2. the full Python suite once on Python 3.12;
3. the fast tier once on Pydantic 1.x, the half of the declared range the
   constraints pin does not cover;
4. the optional Chromium behavior suite once on Python 3.12.

This catches supported-Python drift quickly without paying the full-suite cost
for every matrix entry. Jobs 2–4 need job 1, so a broken build fails once
rather than four times.
