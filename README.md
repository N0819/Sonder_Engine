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
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8008 --reload
```

Open http://127.0.0.1:8008. The default SQLite database is engine.db; set ENGINE_DB before startup to use another path.

## Development commands

```bash
pip install -c constraints.txt -r requirements-dev.txt
make test-fast  # broad suite without explicitly slow integration tests
make test-full  # every Python regression test
make check      # compile, regenerate/verify the map, structure check, full test
make map        # regenerate docs/CODE_MAP.md
make run        # start the local server
```

Real-browser tests are optional; see [`docs/TESTING.md`](docs/TESTING.md) for
their isolated install and for the dependency/CI policy.

The application intentionally uses top-level imports such as `from db import q`. Run commands from the repository root rather than treating the directory as an installed package.

## Project layout

```text
agents/               role-specific agents, shared helpers, and pipeline runtime
app.py                 FastAPI assembly, remaining routes, and streaming API
auth_routes.py         typed host-authentication routes
chat_archive.py        portable chat archive service and routes
commit.py              validated persistence boundary
schemas.py             model-output contracts and validation
character_schema.py     versioned character-card schema and migration
psychology_runtime.py   bounded stress, hedonic, belief, and association state
prompts.py             system prompts
providers.py           LLM providers, streaming, retries, embeddings
memory.py              lore, memory, relationships, retrieval
scene.py / spatial.py  deterministic scene and perception support
spatial_orientation.py bearing math and reciprocal edge normalization
pipeline_trace.py      private-by-default persisted-history diagnostics
db.py                  SQLite schema, migrations, transactions
static/                 browser UI
tests/                  invariant and regression tests
browser_tests/          optional real Chromium behavior tests
docs/                   practical architecture documentation
tools/                  maintenance scripts
archive/                inactive historical files retained for reference
```

## Dependency notes

`sqlite-vec` is used when available for vector search. Providers can point to OpenAI-compatible endpoints, Anthropic, Ollama, KoboldCpp, and configured remote services. API keys and provider settings are stored in the local database, so do not commit a populated `engine.db`.

## Credits

Prior art and research the engine draws on is sourced in
[`docs/RESEARCH.md`](docs/RESEARCH.md). Named here because it is an external
standard rather than a library:

- **[Sigma Stratum — SIGMA Runtime documentation](https://github.com/sigmastratum/documentation)**
  ([sigmastratum.org](https://sigmastratum.org/)). SRIP-14 §XXII, *Retrieval as
  Perturbation Source*, is the source of the idea that retrieval can serve
  divergence as well as recall — fetching contrasting rather than matching
  material when a mind has converged, and marking it non-authoritative. Public
  SRIPs are CC BY 4.0 with an Independent Implementation Safe Harbor. See
  [`docs/RESEARCH.md`](docs/RESEARCH.md) §1.5 for what carries over and what
  deliberately does not.

  Attribution only: citing or independently implementing a public SRIP implies
  no certification, endorsement, partnership, or official compatibility, and no
  Sigma marks are used as product identity.

## License

Released under the [MIT License](LICENSE).
