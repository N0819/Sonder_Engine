PYTHON ?= python
PYTEST ?= $(PYTHON) -m pytest

# Workers for the full tier. `auto` is xdist's PHYSICAL core count -- but only
# when psutil is importable, which is why psutil is a dev dependency; without
# it `auto` silently means LOGICAL cores. Measured on 8,566 tests, 8 physical
# / 16 logical: 220s serial, 117s at 4, 76s at 8, 87s at 16. The curve turns
# back up past the physical count because the engine keeps daemon threads
# alive across tests, so one worker per hardware thread oversubscribes them.
# Override for a machine that disagrees: `make test JOBS=4`, or `JOBS=0` for
# the serial run.
JOBS ?= auto

.PHONY: run serve test test-fast test-full test-serial test-lf test-browser browser-install map structure compile check-fast check clean

# `--reload` is not free. With watchfiles installed (which `uvicorn[standard]`
# in pyproject.toml already asks for) the watcher is event-driven and costs
# nothing. WITHOUT it, uvicorn silently falls back to StatReload, which re-walks
# the whole tree and stats every .py file every `--reload-delay` seconds --
# measured here at 35ms a sweep, so 14% of a core, permanently, for a server
# that is otherwise doing NOTHING (the app process itself measured 0%). The
# walk descends into backdrops/ and .git too, neither of which holds any code.
# So: slow the sweep right down when the cheap watcher is missing.
RELOAD_DELAY := $(shell $(PYTHON) -c "import watchfiles" >/dev/null 2>&1 && echo 0.25 || echo 2)

# Ctrl+C must actually stop the server. Uvicorn's graceful shutdown waits
# FOREVER by default for a client that has not finished reading its response --
# and a browser buffering a multi-megabyte ambience bed is exactly that client,
# so "Shutting down" would hang on "Waiting for connections to close" until a
# second Ctrl+C. Reproduced and measured: unbounded hang vs a 4s exit.
SHUTDOWN := --timeout-graceful-shutdown 3

run:
	uvicorn web.app:app --host 127.0.0.1 --port 8008 --reload --reload-delay $(RELOAD_DELAY) $(SHUTDOWN)

# The same server without the watcher: nothing is reloaded, and nothing is
# spent noticing that nothing changed. This is the one to use for PLAYING, as
# opposed to working on the code.
serve:
	uvicorn web.app:app --host 127.0.0.1 --port 8008 $(SHUTDOWN)

test: test-full

# NOT the tier to check your own work with -- it deselects every test that
# touches the database, and with them the persistence and information-firewall
# suites. (Counts are deliberately not written down here: they were re-synced
# twice and drifted twice. `make test-full` reports the real number, and
# `$(PYTEST) -q -m "not slow" --collect-only` reports what this tier skips.) Since test
# databases moved to tmpfs (tests/conftest.py) the whole suite costs about
# what this used to, so there is no longer a speed argument for running less
# of it -- and CI no longer calls this at all (the matrix runs check-fast).
# Kept as a manual escape hatch for a machine with no usable /dev/shm.
test-fast:
	$(PYTEST) -q -m "not slow"

# Parallel by default, because this is the tier the docs tell you to check
# your own work with and 76s against 220s decides whether it actually gets
# run. `JOBS=0` is the serial escape hatch -- reach for it when a failure's
# output is confusing, since xdist interleaves workers and cannot show the
# live log of the test that failed.
# DEGRADES rather than fails when xdist is absent, and says why. `make test`
# runs on whatever `python` resolves to, which on a PEP 668 system interpreter
# cannot be pip-installed into without --break-system-packages -- so the
# choice is a working slow run with one line of explanation, or
# "unrecognized arguments: -n" for a developer who did nothing wrong.
test-full:
	@if [ "$(JOBS)" = "0" ]; then \
		$(PYTEST) -q; \
	elif $(PYTHON) -c "import xdist" 2>/dev/null; then \
		$(PYTEST) -q -n $(JOBS); \
	else \
		echo "note: pytest-xdist not installed for '$(PYTHON)' -- running serially (~3x slower)."; \
		echo "      pip install -r requirements-dev.txt, or run: make test JOBS=0 to silence this."; \
		$(PYTEST) -q; \
	fi

test-serial:
	$(PYTEST) -q

# The fix-verify loop: last-failed first, then the rest. Free -- the pytest
# cache is already on -- and the right tool while iterating on one bug.
test-lf:
	$(PYTEST) -q --lf --ff

test-browser:
	$(PYTEST) -q browser_tests

browser-install:
	$(PYTHON) -m playwright install chromium

map:
	$(PYTHON) tools/generate_code_map.py

structure:
	$(PYTHON) tools/project_check.py

# The directory list is NOT written here. `extension_runtime` and
# `language_runtime` were missing until 2026-08-18 -- the first is the public
# extension API, an integrator's production code is told to depend on it, and a
# syntax error there was caught by nothing. That happened because "where the
# source is" was written down in four places and only one of them was updated.
# There is now one: `ENGINE_SOURCE_ROOTS` in tools/project_check.py, which the
# structural checks walk and which `--source-roots` prints for this rule.
compile:
	$(PYTHON) -m compileall -q $$($(PYTHON) tools/project_check.py --source-roots)

# Both tiers now run every test. The difference is `map`: `check` regenerates
# docs/CODE_MAP.md, `check-fast` only verifies the copy on disk is current.
# check-fast USED to mean "skip the database tests", which made it a fast path
# that quietly skipped the persistence and firewall suites -- the tests this
# repo exists to keep honest. That was a real trade when a temp_db cost 1.2s;
# it is not one now.
check-fast: compile structure test-full

check: compile map structure test-full

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache
