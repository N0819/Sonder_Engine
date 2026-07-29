# Sonder Engine

A local, single-player interactive-fiction engine in which the characters are
separate minds rather than voices of one narrator.

Its defining constraint: **no fictional mind may use information it did not
legitimately perceive, learn, remember, or infer.** Objective truth, perception,
memory, belief, and narration are kept as distinct layers that never collapse
into one context — which is what lets a character be wrong, be surprised, or be
deceived, and mean it.

## How a turn works

Each stage is a separate model call over a separate context. The Director owns
objective causality; Perception decides what each observer legitimately
receives; character agents choose behaviour from private context and never
their own success; the Narrator renders only the player-facing slice; and
`commit.py` is the sole boundary where model output becomes persistent state.

```text
director_interpret → mapping → perception_act
    → [reactions] → [character agents, in parallel or in an interaction loop]
    → director_resolve → background_react → perception_outcome
    → narrator → commit
```

Every stage's output is stored as a step/variant pair, so any turn can be
rerolled, rerun from a stage, or hand-edited. `docs/PIPELINE.md` has the exact
flow, including the different opening-turn path.

## Start here

1. [`AGENTS.md`](AGENTS.md) — edit routing, invariants, source-of-truth order.
   **Read first for any behavioural change.**
2. [`docs/ENGINEERING.md`](docs/ENGINEERING.md) — how the system operates,
   layer by layer, and why each boundary is where it is.
3. [`docs/PIPELINE.md`](docs/PIPELINE.md) — stage-by-stage execution.
4. [`docs/DATABASE.md`](docs/DATABASE.md) — schema, write helpers, and the
   checklist every new persistent field must satisfy.
5. [`docs/CODE_MAP.md`](docs/CODE_MAP.md) — generated index of modules,
   functions, routes, and tables. Regenerate with `make map`; never hand-edit.
6. [`docs/TESTING.md`](docs/TESTING.md) — test tiers and CI policy.
7. [`Design.md`](Design.md) — philosophy, architecture, and a verified
   built / partial / not-built conformance table.
8. [`docs/OPEN_ITEMS.md`](docs/OPEN_ITEMS.md) — known defects and unfinished
   work. [`CHANGELOG.md`](CHANGELOG.md) is the history.

## Run locally

Python 3.11 or newer.

**Windows:** double-click `Start Sonder.bat` — it creates the environment,
installs dependencies, and opens the app.

**macOS / Linux:**

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8008 --reload
```

Then open <http://127.0.0.1:8008>. The database is `engine.db` by default; set
`ENGINE_DB` before startup to use another path.

## Development

```bash
pip install -c constraints.txt -r requirements-dev.txt

make check       # compile + map freshness + structure + full tests — run before calling a change done
make check-fast  # the same, with the database-backed slow tests skipped
make test-fast   # broad suite, no database-backed tests
make test-full   # every Python regression test
make structure   # duplicate symbols, patch debris, stale map
make map         # regenerate docs/CODE_MAP.md
make run         # start the server
```

`make check` treats a stale `docs/CODE_MAP.md`, a duplicated top-level symbol,
or leftover patch-debris markers as hard failures. Real-browser tests are
optional (`make test-browser`); see [`docs/TESTING.md`](docs/TESTING.md).

Run everything from the repository root — the app uses top-level imports such
as `from db import q` and is not an installed package.

## Layout

```text
agents/          pipeline stages (director, perception, character, narration,
                 background) plus runtime, plan building, and shared helpers
app.py           FastAPI assembly, routes, streaming
commit.py        the sole persistence boundary; validates before anything sticks
db.py            SQLite schema, migrations, transactions
schemas.py       model-output contracts       prompts.py    system prompts
providers.py     LLM providers, streaming, retries, embeddings

world            scene.py · spatial.py · spatial_frames.py ·
                 spatial_orientation.py · mechanics.py · survival.py · comfort.py
minds            character_schema.py · psychology_runtime.py (stress, pain and
                 pleasure, absorption) · affect.py (mood, wants, intentions,
                 projects) · theory_of_mind.py (belief) · memory.py (memory,
                 lore, retrieval)
services         auth_routes.py · guest_access.py · chat_archive.py ·
                 checkpoints.py · pipeline_trace.py · importers.py

static/          browser UI — browser globals, not ES modules; load order matters
tests/           invariant and regression tests
docs/            architecture documentation
tools/           maintenance scripts and experiment harnesses
```

## Providers and data

Providers can target OpenAI-compatible endpoints, Anthropic, Ollama, KoboldCpp,
and configured remote services. `sqlite-vec` is used for vector search when
available; without an embeddings provider configured, semantic recall falls back
to a cheap lexical hash and quality drops accordingly.

API keys, provider settings, and all story content live in the local database —
**never commit a populated `engine.db`.**

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

  Implemented independently from the public specification, with thanks. Sonder
  isn't an official or certified Sigma integration, and nothing here speaks for
  Sigma Stratum — the good idea is theirs, any mistakes in using it are ours.

## License

Released under the [MIT License](LICENSE).
