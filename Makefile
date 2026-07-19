.PHONY: run test map structure compile check clean

run:
	uvicorn app:app --host 127.0.0.1 --port 8008 --reload

test:
	pytest -q

map:
	python tools/generate_code_map.py

structure:
	python tools/project_check.py

compile:
	python -m compileall -q *.py agents tools tests

check: compile map structure test

clean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache
