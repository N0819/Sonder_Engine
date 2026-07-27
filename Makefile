PYTHON ?= python
PYTEST ?= $(PYTHON) -m pytest

.PHONY: run test test-fast test-full test-browser browser-install map structure compile check-fast check clean

run:
	uvicorn app:app --host 127.0.0.1 --port 8008 --reload

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
