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
5. [`docs/MEMORY.md`](docs/MEMORY.md) — what a character remembers: minting,
   provenance, ranking, unbidden recall, belief revision, embeddings.
6. [`docs/CODE_MAP.md`](docs/CODE_MAP.md) — generated index of modules,
   functions, routes, and tables. Regenerate with `make map`; never hand-edit.
7. [`docs/TESTING.md`](docs/TESTING.md) — test tiers and CI policy.
8. [`docs/FEATURES.md`](docs/FEATURES.md) — every feature in plain language:
   what the app does, one line each.
9. [`Design.md`](Design.md) — philosophy, architecture, and a verified
   built / partial / not-built conformance table.
10. [`docs/UNBUILT.md`](docs/UNBUILT.md) — the single register of known defects
   and unbuilt work. [`CHANGELOG.md`](CHANGELOG.md) is the history.

## Run locally

Python 3.11 or newer.

**Windows:** double-click `Start Sonder.bat` — it creates the environment,
installs dependencies, and opens the app.

**macOS / Linux:**

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8008 --timeout-graceful-shutdown 3
```

That last flag is not optional in practice. Uvicorn's graceful shutdown waits
*indefinitely* for a client that has not finished reading its response, and a
browser tab buffering a multi-megabyte ambience bed is exactly such a client —
so Ctrl+C prints "Shutting down", then "Waiting for connections to close", and
sits there until a second Ctrl+C kills it. `make run` and `make serve` pass it
for you.

Then open <http://127.0.0.1:8008>. The database is `engine.db` by default; set
`ENGINE_DB` before startup to use another path.

**To play, do not pass `--reload`** (and `make serve` is the same command).
Idle, the server itself costs nothing — measured at 0% of a core with a story
open. The file watcher behind `--reload` is a different matter: given
`watchfiles` it is event-driven and free, but without it uvicorn falls back to
re-walking the whole tree and stat-ing every `.py` file four times a second,
which measured **16% of a core, permanently, for a server doing nothing**.
`requirements.txt` asks for `uvicorn[standard]`, which includes `watchfiles`,
so a clean install of the above is fine — but a system-packaged uvicorn often
is not. If you are developing and want reloads, check with:

```bash
python -c "import watchfiles" || pip install watchfiles
```

`make run` checks this for you and slows the fallback watcher down when
`watchfiles` is missing.

## Development

```bash
pip install -c constraints.txt -r requirements-dev.txt

make check       # compile + map freshness + structure + full tests — run before calling a change done
make check-fast  # the same, with the database-backed slow tests skipped
make test-fast   # broad suite, no database-backed tests
make test-full   # every Python regression test
make structure   # duplicate symbols, patch debris, stale map
make map         # regenerate docs/CODE_MAP.md
make run         # start the server, watching for code changes
make serve       # start the server with no watcher — for playing
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
and configured remote services. Recall ranks a character's own memories in
Python and deliberately uses no vector index: one character's rows are scored
in NumPy and fused with a BM25 keyword ranking and an exact-phrase ranking,
because the two filters that matter most — a mind may not retrieve how the turn
it is deciding turned out, and it may not see another frame's memories — have
to run *before* ranking, which is exactly what an approximate-nearest-neighbour
index cannot do cheaply. At this workload the exhaustive scan is also simply
cheaper than the problem: a few tens of milliseconds for a long story
([`docs/RESEARCH.md`](docs/RESEARCH.md) §1.3–1.4).

Configuring an `embeddings` provider is what makes recall work by MEANING.
Without one, the two vector rankings fall back to a character n-gram hash: a
fuzzy lexical signature that retrieves reworded text well when it shares
vocabulary, and **not at all when it does not** — measured against a real
441-memory story, recall of a genuine paraphrase is indistinguishable from
random. Keyword and exact-phrase matching still work, so nothing breaks; what
is missing is a character recalling something relevant that was worded
differently three hundred turns ago.

Switching providers does **not** re-embed what is already stored — a vector can
only be compared with one from the same model. The engine notices and offers to
rebuild when you open a story, and API Connections shows the count and a button
([`docs/UNBUILT.md`](docs/UNBUILT.md) §1.15).

**Prompt caching is a per-provider checkbox** in API Connections, and it is off
for any provider not known to forward a cache breakpoint — one that *rejects* it
fails the turn, which is worse than not caching. It applies to Claude models
only, because the caching is Anthropic's. Turning it on is not automatically a
win: across 14 probed models a ~98% hit rate ran anything from **8× faster to
6.5× slower** than no cache at all ([`docs/UNBUILT.md`](docs/UNBUILT.md) §1.25),
which is why it is a switch and not a default.

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

- **[Freesound](https://freesound.org/)** — the optional room-ambience feature
  can source its sound beds from Freesound's APIv2, the collaborative
  Creative Commons sound database maintained by the [Music Technology
  Group](https://www.upf.edu/web/mtg) at Universitat Pompeu Fabra, Barcelona.
  Every recording it plays is somebody's field work, uploaded under a licence
  that asks to be credited: the engine fetches only CC0 and Attribution sounds
  unless a host opts into more, stores the uploader, licence and source URL
  beside each cached file, and shows them in the 🎧 panel while that sound is
  playing. Sonder is not affiliated with or endorsed by Freesound, and using
  the feature needs your own free API key from
  [freesound.org/apiv2/apply](https://freesound.org/apiv2/apply). If you
  publish or stream anything containing an Attribution-licensed bed, credit
  its uploader — the panel tells you who.

  The alternative source is a local folder of audio you already own, which
  involves no third party at all.

Two published findings changed what got built rather than what got
imported, so they are ideas only — no code read, taken, or depended on.
**Lee, Goel & Ramchandran, [*Quantifying Positional Biases in Text Embedding
Models*](https://arxiv.org/abs/2412.15241)**: embedding models over-weight a
text's opening sentence, which is why a minted memory leads with the beat's
events and puts the room change last. **Li et al., [*On the Sentence
Embeddings from Pre-trained Language Models*](https://arxiv.org/abs/2011.05864)
(BERT-flow, EMNLP 2020)**: cosine similarity tracks surface overlap more than
meaning, so a memory omits unchanged standing state entirely rather than
appending a delta to a fixed frame. Together they took the verbatim-twin rate
in the memory bank from 14.6% to 0.4%. [`docs/RESEARCH.md`](docs/RESEARCH.md)
§1.6 has the detail, and names the leads deliberately *not* used — Angband's
message aggregation is GPL and was not read, TADS 3 is proprietary and
prohibits derivatives, Curveship's licence was never verified.

The weather overlay has no third-party dependency at all. It began as
[tsParticles](https://particles.js.org/) by Matteo Bruni — a good library,
and thanks are owed for the version that shipped first — but a particle engine
redraws a full-screen canvas from JavaScript every frame, which is a great deal
of power for scenery. It now draws one small tile, generated at runtime and
seamless by construction, repeated as a background and moved by a CSS
`transform`: no per-frame JavaScript, no repaint, and the animation runs on the
compositor rather than the CPU. Nothing is downloaded and nothing is vendored.

## License

Released under the [MIT License](LICENSE).
