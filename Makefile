PYTHON ?= python
PYTEST ?= $(PYTHON) -m pytest

.PHONY: run serve test test-fast test-full test-lf test-browser browser-install map structure compile check-fast check clean

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
	uvicorn app:app --host 127.0.0.1 --port 8008 --reload --reload-delay $(RELOAD_DELAY) $(SHUTDOWN)

# The same server without the watcher: nothing is reloaded, and nothing is
# spent noticing that nothing changed. This is the one to use for PLAYING, as
# opposed to working on the code.
serve:
	uvicorn app:app --host 127.0.0.1 --port 8008 $(SHUTDOWN)

test: test-full

# NOT the tier to check your own work with -- it deselects every test that
# touches the database, 1841 of 6329 tests, emptying 119 of 391 files and
# with them the persistence and information-firewall suites. Since test
# databases moved to tmpfs (tests/conftest.py) the whole suite costs about
# what this used to, so there is no longer a speed argument for running less
# of it -- and CI no longer calls this at all (the matrix runs check-fast).
# Kept as a manual escape hatch for a machine with no usable /dev/shm.
test-fast:
	$(PYTEST) -q -m "not slow"

test-full:
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

compile:
	$(PYTHON) -m compileall -q *.py agents tools tests browser_tests

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
