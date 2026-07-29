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

## CI layout

GitHub Actions runs:

1. fast checks on Python 3.11 and 3.12;
2. the full Python suite once on Python 3.12;
3. the optional Chromium behavior suite once on Python 3.12.

This catches supported-Python drift quickly without paying the full-suite cost
for every matrix entry.
