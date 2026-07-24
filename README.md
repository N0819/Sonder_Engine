# Sonder Engine

Sonder Engine is a local multi-agent interactive-fiction system built around explicit information boundaries. The Director resolves objective causality, Perception creates observer-specific views, character agents act from private context, the Narrator renders the player-facing slice, and deterministic commit code decides what becomes persistent state.

## Start here

Read these in order when orienting yourself:

1. [`AGENTS.md`](AGENTS.md) — practical edit routing, invariants, and source-of-truth rules.
2. [`docs/PIPELINE.md`](docs/PIPELINE.md) — exact opening-turn and normal-turn execution flow.
3. [`docs/CODE_MAP.md`](docs/CODE_MAP.md) — generated modules, routes, large functions, tables, and frontend sections.
4. [`Design.md`](Design.md) — product philosophy, current architecture, known weaknesses, and roadmap.
5. [`docs/RESEARCH.md`](docs/RESEARCH.md) — sourced bibliography of the research the engine draws on.

## Run locally

Python 3.11 or newer is recommended.

### Windows (Quick Start)
Double-click `Start Sonder.bat`. This automatically sets up the environment, installs dependencies and opens the app in your browser.

### Manual / Mac / Linux
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8008 --reload
Open http://127.0.0.1:8008. The default SQLite database is engine.db; set ENGINE_DB before startup to use another path.
```

Open `http://127.0.0.1:8008`. The default SQLite database is `engine.db`; set `ENGINE_DB` before startup to use another path.

## Development commands

```bash
make test       # run the test suite
make check      # compile, regenerate/verify the map, run structure checks, then test
make map        # regenerate docs/CODE_MAP.md
make run        # start the local server
```

The application intentionally uses top-level imports such as `from db import q`. Run commands from the repository root rather than treating the directory as an installed package.

## Project layout

```text
agents/               role-specific agents, shared helpers, and pipeline runtime
app.py                 FastAPI routes and streaming API
commit.py              validated persistence boundary
schemas.py             model-output contracts and validation
prompts.py             system prompts
providers.py           LLM providers, streaming, retries, embeddings
memory.py              lore, memory, relationships, retrieval
scene.py / spatial.py  deterministic scene and perception support
db.py                  SQLite schema, migrations, transactions
static/                 browser UI
tests/                  invariant and regression tests
docs/                   practical architecture documentation
tools/                  maintenance scripts
archive/                inactive historical files retained for reference
```

## Dependency notes

`sqlite-vec` is used when available for vector search. Providers can point to OpenAI-compatible endpoints, Anthropic, Ollama, KoboldCpp, and configured remote services. API keys and provider settings are stored in the local database, so do not commit a populated `engine.db`.

## License

Released under the [MIT License](LICENSE).
