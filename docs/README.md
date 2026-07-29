# Documentation Index

## Maintained implementation guides

These are current implementation authority. Change one in the same commit that
changes the behaviour it describes.

- [`../README.md`](../README.md): setup and repository overview.
- [`../AGENTS.md`](../AGENTS.md): practical editing rules and invariants.
- [`../CLAUDE.md`](../CLAUDE.md): Claude Code entry point into the same
  maintained guide set.
- [`ENGINEERING.md`](ENGINEERING.md): how the system operates, layer by layer,
  and why each boundary is where it is.
- [`PIPELINE.md`](PIPELINE.md): implemented turn execution and debugging map.
- [`DATABASE.md`](DATABASE.md): persistence and schema-change guide.
- [`TESTING.md`](TESTING.md): fast/full/browser test tiers, dependency
  constraints, and CI policy.
- [`CODE_MAP.md`](CODE_MAP.md): generated structural index.
- [`../agents/README.md`](../agents/README.md): pipeline package ownership and
  stage-addition checklist.
- [`../tests/README.md`](../tests/README.md): regression-test placement and
  database-fixture rules.
- [`../Design.md`](../Design.md): product philosophy, architecture, and the
  verified built / partial / not-built conformance table.
- [`UNBUILT.md`](UNBUILT.md): **the single register of unfinished work** —
  known defects, the roadmap, deferred audit findings, and every design-note
  residual. Nothing else in this tree keeps its own status list.
- [`RESEARCH.md`](RESEARCH.md): sourced bibliography — research the code cites
  (belief revision, RRF/MMR, Novikov) and the established work the architecture
  maps onto.

`CODE_MAP.md` is generated. The other maintained documents are curated and
should explain intent rather than mirror every function.

Character-psychology changes span the maintained guides: `PIPELINE.md` owns the
runtime information flow, `../Design.md` owns the psychology model and its
status, `UNBUILT.md` owns the known gaps, and `../AGENTS.md` owns the edit/test
routing.

## Design notes

Each argues for one subsystem and keeps the reasoning behind it. They are
context, not implementation authority — where a claim disagrees with source,
source wins. What any of them has **not** built is registered in
[`UNBUILT.md`](UNBUILT.md), not in the note itself.

- [`DESIGN_PLACE_PURPOSE.md`](DESIGN_PLACE_PURPOSE.md) — what a place is FOR.
- [`DESIGN_LONG_TERM_GOALS.md`](DESIGN_LONG_TERM_GOALS.md) — the project tier
  between drive and intention.
- [`DESIGN_RUNNING.md`](DESIGN_RUNNING.md) — multi-room movement, bounded by
  decision rather than sight.
- [`DESIGN_SURFACE_COMFORT.md`](DESIGN_SURFACE_COMFORT.md) — ambient comfort
  from surfaces, and the two rules that stop it becoming an attractor.
- [`DESIGN_PSYCHOLOGY_AS_PRESSURE.md`](DESIGN_PSYCHOLOGY_AS_PRESSURE.md) — why
  a sheet should bias deliberation rather than serve as its premises.
- [`BACKGROUND_LIFE_DESIGN.md`](BACKGROUND_LIFE_DESIGN.md) — the tier between
  an amnesiac extra and a promoted character.
- [`OFFSCREEN_LIFE_DESIGN.md`](OFFSCREEN_LIFE_DESIGN.md) — off-screen life,
  reactivation, and villain ticks. Unbuilt.
- [`EXTENSIONS_DESIGN.md`](EXTENSIONS_DESIGN.md) — user-authored extensions.
  Unbuilt.
- [`GREETING_IMPORT_DESIGN.md`](GREETING_IMPORT_DESIGN.md) — greeting-seeded
  openings. Shipped, under a different architecture than proposed.
- [`DESIGN_MAZE_EXPANSION.md`](DESIGN_MAZE_EXPANSION.md) — can a mind revise a
  map it already trusts? Designed, not built.

## Experiment records

Evidence of runs that happened once and cannot be reproduced — the models are
not deterministic and the character's accumulated memory is itself part of the
experiment. Read as findings, never as a build artifact.

- [`SPATIAL_LEARNING_EXPERIMENT.md`](SPATIAL_LEARNING_EXPERIMENT.md) — the
  findings.
- [`MAZE_ARMS.md`](MAZE_ARMS.md) — the arm registry: each arm's question, code
  state, and what it may legitimately be compared against.
- [`MAZE_RUNS.md`](MAZE_RUNS.md) — index of rendered move-by-move traces, one
  document per arm, under [`maze/`](maze).

## Audits

There are none in the tree. Five dated audit documents — the 2026-07-19
architecture audit, the information-pipeline leak sweep, the enterprise_d_v2
backlog, the Fable adversarial-review follow-ups, and the place-graph review —
were re-verified against source at alpha 6.1 and erased once their live findings
were folded into [`UNBUILT.md`](UNBUILT.md) §3–§6, which carries their original
finding ids and enough mechanism detail to act on.

They were erased rather than kept because a stale audit is worse than none: most
of their contents had shipped, every line citation had drifted, and a reader
taking them at face value would have chased about forty closed findings. The
reasoning is in git history and `CHANGELOG.md`.
