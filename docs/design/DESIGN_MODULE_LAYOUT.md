# Module layout: splitting the monoliths, then grouping the tree

Status: **LANDED 2026-08-18.** Both jobs are done: the three monoliths were
split behind facades, then the tree was regrouped. What follows is the plan
as argued plus, at the end, what executing it actually cost.

Two jobs are described here, and the argument of this note is that they are
**two jobs and must not be one commit**:

1. **Split the three monoliths** (`world/spatial.py`, `persist/commit.py`,
   `agents/director.py` — 24,783 lines between them) behind re-export facades,
   so no import path anywhere changes.
2. **Group the tree** into subsystem packages, so the repository root stops
   being 55 `.py` files, and rewrite the 2,544 import statements that names
   them.

Job 1 reduces the thing that actually costs you: a file you cannot hold in
your head while changing it safely. Job 2 buys navigability and costs a
codemod plus a documentation sweep. Job 1 first, because it is invisible to
every other file, and because doing it after a tree move would mean reviewing
two kinds of change in the same diff.

## What was measured

Counted, not estimated, on 2026-08-18 (alpha 9.5, `418ab5b`):

| Fact | Value |
| --- | --- |
| `.py` files at the repository root | 55 |
| Lines in those files | 73,104 |
| `world/spatial.py` / `persist/commit.py` / `agents/director.py` | 8,451 / 8,197 / 8,135 |
| Top-level defs in those three | 199 / 132 / 114 |
| Import statements naming a root module | **2,544**, across **473 files** |
| Most-imported: `db` / `schemas` / `commit` / `character_schema` / `spatial` | 349 / 209 / 207 / 196 / 160 |
| Markdown files naming a `.py` path | 59 (`persist/commit.py` alone appears in 48) |

The facade contract, extracted by AST (`from X import name`, whole repo):

| Module | distinct names imported | reached from production | private names crossing |
| --- | --- | --- | --- |
| `spatial` | 135 | 74 | 20 |
| `commit` | 61 | 27 | 22 |
| `agents.director` | 46 | **3** | **41** |

`agents/director.py` is the striking one: almost nothing in production imports
it (the pipeline reaches it through `agents/runtime.py`'s step registry), while
**41 private names are imported by tests**. Its facade is therefore almost
entirely a test-compatibility surface. That is worth knowing before the split
and worth fixing after it — not during.

## Job 1: split behind facades

The pattern already exists in this repo and is the one to follow:
`world/spatial_orientation.py` was carved out of `world/spatial.py` and is
re-exported through it; `agents/__init__.py` is an explicit compatibility
facade. Re-exported means the sibling is no longer importable in its own right
— `tools/project_check.py` holds all three families (`world.spatial`,
`agents.director`, `persist.commit`) to the facade spelling, which is what
stops a facade decaying into a directory of modules that merely share a
prefix. Each monolith keeps its filename, keeps every name it
exports today — **including the private ones** — and becomes a module whose
body is the orchestration plus a block of re-exports.

Consequences of doing it this way, all of them the point:

- No caller changes. All 2,544 import sites stay valid.

### The facade preserves imports. It does not preserve monkeypatching.

This is the one thing the plan got wrong before the files were read, and it is
the difference between "mechanical" and "not":

`monkeypatch.setattr(director, "_agent_json", fake)` writes into
`agents/director.py`'s module dictionary. A function moved to
`agents/director_fanout.py` resolves `_agent_json` in **its own** globals and
never sees the patch. Re-exporting the function through the facade does not
help — the binding a function reads is the one in the module where it was
defined.

Measured, per file:

| file | patch sites | on a move they… |
| --- | --- | --- |
| `agents/director.py` | **106** `setattr(director, "_agent_json", …)` across 17 test files, plus 5 others | 4 of 9 affected functions fail **silently** |
| `persist/commit.py` | 6 test files patch `commit.<name>` | 5 fail loudly; 1 passes for the wrong reason, permanently |
| `world/spatial.py` | **zero** | nothing to do |

Silent is the word that matters. `tests/test_commit_tail_producers.py:118`
installs a raising stub and asserts *by absence* that it never runs; after the
memory-write extraction the patch is inert, the test is green, and it can no
longer catch the 29.5-second regression it was written for. Four Director
functions behave the same way: the fake is installed, some other call reaches
it, and the moved function quietly makes a real model call.

Two consequences for how this is executed:

1. **Every step repoints its own patch sites in the same commit.** The three
   per-file plans list them by `file:line`.
2. **`agents/director.py` splits in two phases.** Phase 1 moves only the
   deterministic helpers and leaves every model-calling function where it is —
   9 modules, ~4,640 lines out, zero test changes. Phase 2 moves the stage
   bodies and needs a `patch_agent_json` helper in `tests/conftest.py` plus 111
   mechanical call-site rewrites. Phase 2 is a separate decision, not a
   continuation.

A tempting third option — making `agents.director` a module subclass whose
`__setattr__` forwards writes to the submodules — was considered and rejected:
it preserves the tests verbatim while hiding the exact coupling this exercise
exists to expose, and it makes a patch of a name nothing reads any more pass
silently instead of failing loudly.
- All 59 documents stay true. `AGENTS.md`'s edit-routing table keeps working.
- `git bisect` stays clean and reviews stay mechanical.
- `tools/project_check.py` already fails the build on duplicate top-level
  symbols, so a botched split — a function copied rather than moved — cannot
  land quietly.

Rules for every move, without exception:

- **Verbatim.** Whole functions and classes, unchanged. No renaming, no
  reordering, no docstring edits, no cleanups noticed in passing. A defect
  found while moving gets written down, not fixed: a behaviour change hiding
  inside a 4,000-line rename diff is undiscoverable, and the whole value of
  this refactor is that `git diff -M` reads as pure renames.
- **One module per commit**, each independently green under `make check`.
- **Leaf-first**, so each extraction depends only on what is already extracted.

Per-file decomposition plans, each verified against the source with an AST
pass over every symbol:

- [`SPLIT_SPATIAL.md`](SPLIT_SPATIAL.md) — 13 modules, no state, no
  monkeypatching, four cycles pre-empted by moving symbols against file order.
- [`SPLIT_COMMIT.md`](SPLIT_COMMIT.md) — 14 modules, one mutable global, and a
  transaction boundary the split provably does not cross.
- [`SPLIT_DIRECTOR.md`](SPLIT_DIRECTOR.md) — 9 modules in phase 1, and the
  106-site monkeypatch finding that forced a second phase.

## Job 2: the tree

The root should hold what you run and what you read — `Start_Sonder.bat`,
`Makefile`, `pyproject.toml`, the requirements files, `README.md`,
`CHANGELOG.md`, `CLAUDE.md`, `AGENTS.md`, `Design.md` — and not 55 modules.

Proposed grouping, derived from the actual dependency graph rather than from
intuition:

```text
core/      db  logging_utils  outofband  updates  frames  pipeline_context  jobs
llm/       providers  prompt_cache  prompts  llm_quality  schemas
world/     spatial(+14 children, orientation among them)  spatial_frames  weather
           mechanics  place_purpose  subjects  crowds  living_world  offscreen
           degradation  paradox  gaps  routines  background_claims  comfort  survival
mind/      memory  affect  psychology_runtime  theory_of_mind  canon_provenance
story/     scene  character_schema  attire  importers  greetings  artifacts
           lore_structure  authored_events  dialogue_colors  carriers  couriers
dressing/  ambience  backdrops
agents/    (unchanged — already a package)
persist/   commit(+children)  checkpoints  chat_archive  pipeline_trace
web/       app  auth_routes  guest_access  story_view
```

### The finding that changes what this grouping can claim

A first grouping produced **nine package-level cycles**. Reassigning four
modules to where the graph says they belong — `frames` and `pipeline_context`
down into `core`, `comfort` and `survival` across into `world` — removed three
of them and made `core` and `mind` clean. Six remain, and they are not
artefacts of a bad taxonomy:

| Cycle edge | import sites | of those, lazy |
| --- | --- | --- |
| `world → story` | 26 | 23 |
| `persist → story` | 33 | 29 |
| `story → world` | 10 | 3 |
| `story → turn`, `persist → turn`, `core → llm`, `llm → story` | 1–9 each | nearly all |

**Most of these imports are already deferred inside function bodies.** That is
a workaround for circular imports, applied repeatedly, over a long time. The
entanglement is not something a directory scheme would introduce; it is
something a directory scheme would finally make visible.

So the grouping is proposed **for navigability, and explicitly not as an
enforced layering**. Do not add an import linter on top of it until those edges
are broken, and do not break them as part of the move — that is logic work, and
this is not a logic change.

**The table above is NO LONGER the baseline, and that sentence is why it had
to stop being one.** It was written as "the baseline a future cleanup should
measure itself against" in the same paragraph that declined to build anything
that could read it, so it drifted immediately and silently: re-measured
2026-08-19, `persist → story` carries 19 eager and 29 deferred sites against
the 33/29 recorded here, and a census across one day of green gates
(`a6d823f` → `73a380a`) found three edges gaining EAGER module-level imports
inside existing cycles. A baseline nothing regenerates records what someone
believed on one afternoon.

The baseline is now `tools/package_edges.json`, which is generated
(`python tools/project_check.py --write-package-edges`) and checked by
`check_package_edge_budget`. It enforces the one thing this section actually
argues for: **no NEW cycle**, measured as a strongly connected component of the
EAGER import graph. It does not budget edges — `web → *` and `agents → *` are
supposed to grow, and a gate that fought a legitimate dependency would be
waived within the week. The eager graph currently has one SCC,
`{agents, persist, story, world}`, which is this section's six two-cycles seen
whole.

### How the move is executed

Not by hand. 2,544 import statements across 473 files is a scripted AST
rewrite (`from db import q` → `from core.db import q`), run once, verified by
`make check`, landed as a single commit that touches nothing else. The
documentation sweep is a second commit: mechanical for paths inside backticks,
by hand for prose that describes where things live — `AGENTS.md`'s routing
table above all, since a stale routing table is worse than none.

Open question for the owner: whether the packages are plain directories or
whether the project becomes an installed package. Today `CLAUDE.md` states
"the app uses top-level imports (`from db import q`), so it is not an
installed package", and commands must run from the repository root. The
grouping above preserves that property. Changing it is a third job.

## The split is also the audit

This is the only task in the project's life that requires somebody to read all
24,783 lines of the three biggest files. Nothing else does — a normal change
reads the neighbourhood of one function and leaves. So the reading is going to
happen anyway, and the marginal cost of writing down what it finds is close to
zero, while the cost of finding it later is a live story behaving wrongly fifty
beats in.

Every module extraction therefore produces two artefacts: the move, and a list
of what the mover saw.

**What counts as a finding.** Anything a careful reader would not want to
discover from a bug report:

- Dead code — a branch nothing can reach, a parameter nobody passes, a helper
  with no callers. (`docs/UNBUILT.md` §1.3 is already one of these, found the
  same way.)
- A guard that reads a value that can no longer take the form it tests for.
- Two functions that do nearly the same thing on slightly different inputs —
  the shape that produced the six-entries-for-three-things presence ledger in
  alpha 9.5.
- A comment that describes behaviour the code no longer has. Worth as much as
  a bug: the next reader believes it.
- Silent tolerance — an empty value, a missing key, or an unknown enum member
  accepted without complaint. CLAUDE.md's psychology section is a catalogue of
  what that costs, and `_barren_intent` and the presence-nature work in 9.5
  both came from the same shape.
- A function long enough that it is a monolith in miniature.

**What does not count.** Style, naming, formatting, and anything whose fix is
"I would have written this differently". The register is for defects.

**The discipline, and it is the whole thing: flag, never fix.** A finding is
written down and the move continues. Fixing it in the move commit destroys the
one property that makes this refactor safe — that `git diff -M` reads as pure
renames and a reviewer can confirm behaviour is untouched without reading the
logic. It also destroys bisectability precisely when the tree is churning
most.

**Where findings go.** `docs/UNBUILT.md` is already the register for exactly
this ("known defects … deferred audit findings"), and CLAUDE.md names it the
one status list that wins when the others disagree. Audit output lands there,
one entry per finding, each carrying `file:line` **as of the pre-split
revision** and the commit that moved the code, so the entry stays findable
after the line numbers change. A finding that turns out to be live gets a
failing test in its own commit, on its own terms, after the split lands —
never inside it.

## The split is also a documentation reconciliation

The audit above asks *is this code wrong*. This asks a different and equally
cheap question while the file is open: **does anything we have written down
still describe it**.

That question is unusually live here, because this project does not have one
status list — it has five, and `CLAUDE.md` says so outright:

1. `docs/UNBUILT.md` — the register, and the one that wins when they disagree
2. `Design.md`'s conformance table (built / partial / not built)
3. each design note's `Status:` header
4. `docs/guides/FEATURES.md`'s `(partial)` markers
5. `docs/design/OFFSCREEN_WORLD_COMPLETION.md`'s per-item tags

Five lists drift in five directions, and nothing checks them against source.
`Design.md`'s rows were verified against the code once, by hand, and
`CLAUDE.md` asks that they be kept that way — which is a request nobody can
honour while reading only the neighbourhood of the function they came to
change.

So each module extraction produces a third artefact: **a short report of what
the extracted code actually does**, written from the code and not from the
docs, and then checked against every claim any of the five lists makes about
it. Three outcomes, each handled differently:

- **The docs are right.** Say so, briefly, and move on. This is the common
  case and recording it is what makes the exceptions credible.
- **The docs are stale** — they describe behaviour that has since changed.
  Correct the document in a commit of its own, citing the code that disproved
  it. `UNBUILT.md` first when the lists disagree, per `CLAUDE.md`.
- **The docs describe something that was never built, or that was built and
  then quietly lost.** This is the valuable one, and alpha 9.5 contains a
  worked example of why: no character formed a memory of their own conduct for
  six days, while every document still described a mind that remembers what it
  said. Nothing in the documentation was edited to make that untrue — the
  behaviour simply left, and the prose stayed. A finding of this kind is a
  defect, not a documentation bug, and goes to `UNBUILT.md` §1 with a failing
  test, on its own terms, after the split lands.

The reports themselves are working notes, not permanent documentation: they
live under `docs/experiments/` (the directory `docs/README.md` designates as
evidence) so they can be cited by the commits that act on them and then left
alone. `docs/CODE_MAP.md` regenerates from source and is not part of this — it
was never the problem, because it is generated and the prose lists are not.

### Order of operations, all three artefacts together

For each module extracted, in this order:

1. **Read** the code that is about to move, completely.
2. **Report** what it does (this section) and **flag** what looks wrong
   (previous section). Both are written before anything is edited, because
   after the move the reader has already stopped being a stranger to it.
3. **Move** it, verbatim, and land it green under `make check`.
4. Only then: doc corrections, and failing tests for live defects, each in
   its own commit.

Steps 2 and 4 are deliberately far apart. Everything that makes this refactor
safe depends on step 3 containing nothing but renames.


## What it cost, measured

The tree move landed as one codemod, verified by `make check` (7,274 tests).
Numbers at execution, which differ from the numbers this note was planned
against because the splits ran first and added 27 modules:

| | planned | actual |
| --- | --- | --- |
| root `.py` files moved | 55 | **81** |
| import statements rewritten | 2,544 | **2,714** across 506 files |
| markdown files updated | 59 | 54 (living docs only) |

Four classes of reference an import-only codemod does not see, all found by
running the suite rather than by reading:

1. **String-form patch targets.** `monkeypatch.setattr("scene.dialogue_config",
   …)` — 13 sites. These are invisible to an AST import walk and fail loudly.
2. **Filesystem path literals.** 18 sites reading a module's own source
   (`root / "app.py"`). A naive regex over these is WRONG in two ways it took a
   red suite to notice: `path.name` never carries a directory, and a plain
   string used as a dict key is not a `Path`, so `"world" / "living_world.py"`
   is `str / str`.
3. **Root derived from a module's `__file__`.** `Path(degradation.__file__)
   .parent` was the repository root and is now a package directory, so a sweep
   that used it silently narrowed to one package instead of failing.
4. **Dynamic imports by literal name.** `__import__("providers")`.

One near-miss worth recording: `web/story_view.py` builds a viewer-scoped
presence id by hashing the literal `"story_view.presence"`. It is a namespace
coordinate, not a module path. Rewriting it would have silently re-keyed every
stranger's identity in every existing story — the same class of mistake as the
language-pack key in `agents/director_lingua.py`. **A dotted name inside a
string is not necessarily an import.**

The move also let one guard finally be finished rather than extended.
`tools/project_check.py`'s `EXTENSION_DEEP_IMPORTS` matches the FIRST dotted
component, so as a list of module names it had to grow by thirteen the moment
`commit.py` was split. Scoped to packages it is complete by construction — the
same argument that retired the animate/inert kind lists in alpha 9.5.

Two new checks guard the arrangement, both proven to fire before being kept
(`check_facade_import_direction`): nothing outside a split family may import a
sibling behind its facade, and no sibling may import its own facade — the
import cycle the facade exists to prevent.
