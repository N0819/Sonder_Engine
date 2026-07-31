PYTHON ?= python
PYTEST ?= $(PYTHON) -m pytest

.PHONY: run serve test test-fast test-full test-browser browser-install map structure compile check-fast check clean

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

test-fast:
	$(PYTEST) -q -m "not slow"

test-full:
	$(PYTEST) -q

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

check-fast: compile structure test-fast

check: compile map structure test-full

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache
