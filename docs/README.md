# Documentation Index

Four kinds of document live here, one folder each, and the difference between
them is how much authority they carry:

| Folder | Authority |
|---|---|
| `guides/` | **Current implementation authority.** Change one in the same commit that changes the behaviour it describes. |
| `design/` | Argument for one subsystem. Context, not authority — where a claim disagrees with source, source wins. |
| `experiments/` | Evidence of runs that happened once and cannot be reproduced. Findings, never build artifacts. |
| `archive/` | Superseded. Kept for the reasoning, not the conclusions. Do not act on one without re-checking source. |

`UNBUILT.md` and `CODE_MAP.md` sit at the top level because they are registers
rather than prose, and everything points at them.

## Start here

- [`../README.md`](../README.md) — setup and repository overview.
- [`../AGENTS.md`](../AGENTS.md) — edit routing table and invariants. **Read
  first for any behavioural change.**
- [`../CLAUDE.md`](../CLAUDE.md) — Claude Code's entry point into the same set.
- [`../Design.md`](../Design.md) — product philosophy, architecture, and the
  verified built / partial / not-built conformance table.

## Registers

- [`UNBUILT.md`](UNBUILT.md) — **the single register of unfinished work**: known
  defects, the roadmap, deferred audit findings, and every design-note residual.
  Delete an entry in the commit that lands it.
- [`CODE_MAP.md`](CODE_MAP.md) — generated structural index of modules,
  functions, routes, tables and frontend sections. Regenerate with `make map`;
  never hand-edit.
- [`CREDITS.md`](CREDITS.md) — other people's PROJECTS: what was read, under
  what licence, and what was drawn from it. Update it in the same commit as
  anything it credits. (Distinct from `guides/RESEARCH.md`, which is the
  literature bibliography.)

## `guides/` — maintained implementation authority

- [`ENGINEERING.md`](guides/ENGINEERING.md) — how the system operates, layer by
  layer, and why each boundary is where it is. The connective tissue between the
  references below; it explains mechanism and does not restate their tables.
- [`PIPELINE.md`](guides/PIPELINE.md) — implemented turn execution, stage by
  stage, and the debugging map.
- [`DATABASE.md`](guides/DATABASE.md) — persistence, schema, and the checklist
  every new persistent field must satisfy.
- [`MEMORY.md`](guides/MEMORY.md) — what a character remembers: minting,
  provenance, ranking, unbidden recall, belief revision, embeddings.
- [`TESTING.md`](guides/TESTING.md) — test tiers, dependency policy, CI layout.
- [`LANGUAGE_PACKS.md`](guides/LANGUAGE_PACKS.md) — build and validate a full
  story/UI language pack while preserving canonical English schemas.
- [`EXTENSIONS.md`](guides/EXTENSIONS.md) — write, install and distribute an
  extension: the manifest, the Python facade, `window.Sonder`, the four state
  homes, and what is and is not actually restricted.
- [`FEATURES.md`](guides/FEATURES.md) — every user-visible feature in plain
  language, one line each. A catalogue, not an argument.
- [`RESEARCH.md`](guides/RESEARCH.md) — sourced bibliography: the research the
  code cites and the established work the architecture maps onto.
- [`../agents/README.md`](../agents/README.md) — pipeline package ownership and
  the stage-addition checklist.
- [`../tests/README.md`](../tests/README.md) — regression-test placement and
  database-fixture rules.

Character-psychology changes span several of these: `PIPELINE.md` owns the
runtime information flow, `../Design.md` owns the psychology model and its
status, `UNBUILT.md` owns the known gaps, `../AGENTS.md` owns the edit/test
routing.

## `design/` — one subsystem argued for

What any of these has **not** built is registered in
[`UNBUILT.md`](UNBUILT.md), not in the note itself.

Minds:

- [`DESIGN_LONG_TERM_GOALS.md`](design/DESIGN_LONG_TERM_GOALS.md) — the project
  tier between drive and intention. Built (v1).
- [`DESIGN_PSYCHOLOGY_AS_PRESSURE.md`](design/DESIGN_PSYCHOLOGY_AS_PRESSURE.md)
  — why a sheet should bias deliberation rather than serve as its premises.
  Partly built.

World and body:

- [`DESIGN_PLACE_PURPOSE.md`](design/DESIGN_PLACE_PURPOSE.md) — what a place is
  FOR. Built (v1).
- [`DESIGN_RUNNING.md`](design/DESIGN_RUNNING.md) — multi-room movement, bounded
  by decision rather than sight. Built.
- [`DESIGN_SURFACE_COMFORT.md`](design/DESIGN_SURFACE_COMFORT.md) — ambient
  comfort from surfaces, and the two rules that stop it becoming an attractor.
  Built.
- [`DESIGN_DISGUISE_AND_RECOGNITION.md`](design/DESIGN_DISGUISE_AND_RECOGNITION.md)
  — what an observer SEES of a disguised body versus whether they know WHO it
  is. Floors built; the graded half designed and registered in `UNBUILT.md`
  §1.43, including why it is a deterministic ladder and not a seventh
  Director specialist.
- [`DESIGN_REGION_VISIBILITY.md`](design/DESIGN_REGION_VISIBILITY.md) —
  concealment applied to bodies, over a four-state coverage ladder. Partly built.
- [`DESIGN_0c_subject_identity.md`](design/DESIGN_0c_subject_identity.md) —
  subject identity and the liveness gate. **No route chosen; not agreed.**

The off-screen world — five documents on one programme, filed together because
they answer different questions about it:

- [`OFFSCREEN_WORLD_ARCHITECTURE.md`](design/OFFSCREEN_WORLD_ARCHITECTURE.md) —
  the accepted normative architecture: invariants, the seven parts, the shapes
  deliberately rejected.
- [`OFFSCREEN_WORLD_COMPLETION.md`](design/OFFSCREEN_WORLD_COMPLETION.md) —
  where that architecture actually stands, item by item, with release gates.
- [`OFFSCREEN_LIFE_DESIGN.md`](design/OFFSCREEN_LIFE_DESIGN.md) — characters
  **not** in the room: gap generation, reactivation, villain ticks.
- [`BACKGROUND_LIFE_DESIGN.md`](design/BACKGROUND_LIFE_DESIGN.md) — extras **in**
  the room: short-context furniture, rolling digest, promotion.
- [`DESIGN_LIVING_WORLD.md`](design/DESIGN_LIVING_WORLD.md) — a comparative
  frontier analysis of five routes (A–E) rated on cheapness × fidelity, citing
  the three above as sources.
- [`DESIGN_CROWDS.md`](design/DESIGN_CROWDS.md) — crowd blobs: one row with many
  people in it. Built 2026-08-10; §7a records what the building changed.

Elsewhere:

- [`EXTENSIONS_DESIGN.md`](design/EXTENSIONS_DESIGN.md) — user-authored
  extensions. Built in 9.0; the note is now the argument for the shape that
  shipped, including the ruling that the firewall is for minds rather than
  developers, and the fourteen things building it changed. The reference for
  *writing* one is [`guides/EXTENSIONS.md`](guides/EXTENSIONS.md).
- [`DIRECTIVE_HOST_SURFACE.md`](design/DIRECTIVE_HOST_SURFACE.md) — what the
  extension surface was short of for a *total-conversion* extension, measured
  against Directive. §§1–7 began as a study and named three blockers — no
  narration-context seam, a declared UI surface two mount points wide, and no
  ES module loading — and found the port is a host adapter rather than the
  Python rewrite it was taken for. All three are built. §9 answers the gap
  report that followed and records the two premises it got wrong, both the same
  error: reading "information firewall" as a restriction on what a developer
  may observe.
- [`DIRECTIVE_GAP_REPORT.md`](design/DIRECTIVE_GAP_REPORT.md) — the report
  itself, written against 9.2 by Directive's author. Kept verbatim as received;
  it is evidence, and the response belongs beside it rather than inside it.
- [`DIRECTIVE_REMAINING_GAPS.md`](design/DIRECTIVE_REMAINING_GAPS.md) — the
  follow-up, written against 9.3 after the five gaps closed: three residual
  contracts exposed by how the new capabilities compose. Kept verbatim, same
  ruling. Its §2 (the structured people projection) is built as
  `player_view["people"]`; §1 and §3 are registered in
  [`UNBUILT.md`](UNBUILT.md) §6.2.
- [`GREETING_IMPORT_DESIGN.md`](design/GREETING_IMPORT_DESIGN.md) —
  greeting-seeded openings. Shipped, under a materially different architecture
  than proposed; its header records the deviation.

## `experiments/` — records of runs that cannot be repeated

The models are not deterministic and the character's accumulated memory is
itself part of the experiment, so none of this reruns. The three maze documents
are split on purpose and must stay split: merging them recreates two failure
modes each one documents.

- [`SPATIAL_LEARNING_EXPERIMENT.md`](experiments/SPATIAL_LEARNING_EXPERIMENT.md)
  — the **findings**: can a character get better at a maze?
- [`MAZE_ARMS.md`](experiments/MAZE_ARMS.md) — the **registry**: each arm's
  question, code state, and what it may legitimately be compared against. It
  exists so no result is compared against a baseline it does not belong to.
- [`MAZE_RUNS.md`](experiments/MAZE_RUNS.md) — the **index** of rendered
  move-by-move traces, one document per arm, under
  [`experiments/maze/`](experiments/maze).
- [`DESIGN_MAZE_EXPANSION.md`](experiments/DESIGN_MAZE_EXPANSION.md) — the next
  arm: can a mind revise a map it already trusts? Designed, not built.
- [`bench-2026-08-03/`](experiments/bench-2026-08-03) — a dated model shootout,
  its raw logs, and
  [`FAST_SUBSCRIBER_CONFIG.txt`](experiments/bench-2026-08-03/FAST_SUBSCRIBER_CONFIG.txt),
  the per-role configuration derived from it. **The model ids in that config are
  stale** — it predates the Director fan-out — but its two arguments are not:
  why role fallbacks exist, and why embeddings must not move providers.

## `archive/` — superseded

- [`PROPOSAL_2026-08-06.md`](archive/PROPOSAL_2026-08-06.md) and
  [`PROPOSAL_2026-08-06_AMENDMENTS.md`](archive/PROPOSAL_2026-08-06_AMENDMENTS.md)
  — a matched pair, deliberately left un-merged so the two can be read against
  each other. Most of the parent's §1 has since been built and its build order
  was overtaken by its own amendments.
- [`AGENT_HANDOFF_ARCHITECTURE.md`](archive/AGENT_HANDOFF_ARCHITECTURE.md) — a
  session handoff for the off-screen build, whose required-order list is now
  entirely `[built]`. It disclaims its own authority in its second paragraph.

## `../design_notes/` — sequential working notes

A different genre from this tree: numbered, dated, method-first notes for one
programme at a time, each stating its own status and measurement method. They
are cited from source comments as "design note N". Residuals from 09, 11 and 17
are in [`UNBUILT.md`](UNBUILT.md) §6.

| # | Topic |
|---|---|
| [00](../design_notes/00-PLAN.md) | The plan: perception becomes a pure function of spatial data, zero LLM calls |
| [01](../design_notes/01-corpus-measurement.md) | How much of `resolved_event` prose already has a structured home |
| [02](../design_notes/02-spatial-fov-gaps.md) | Gap analysis of the spatial/FOV substrate |
| [03](../design_notes/03-composer-design.md) | Design of the deterministic view composer |
| [04](../design_notes/04-leaner-director.md) | Typed beat events; the Director's last free-prose channel |
| [05](../design_notes/05-masked-floor-defects.md) | Where the perception prompt stated a rule the code did not implement |
| [06](../design_notes/06-quality-baseline.md) | Making "same quality, just faster" falsifiable |
| [07](../design_notes/07-spatial-buildout.md) | Designing the authorised spatial buildout |
| [08](../design_notes/08-latency-benchmark.md) | What perception's model call cost |
| [09](../design_notes/09-character-agent-audit.md) | What determinism can take out of `character_step` |
| [10](../design_notes/10-prior-art.md) | Has anyone built per-observer perception or a non-LLM prose composer |
| [11](../design_notes/11-extra-body-parts.md) | Extra body parts as structured data. Implemented |
| [12](../design_notes/12-spatial-derivation-build.md) | What landed on `spatial-derivation` |
| [13](../design_notes/13-composer-build.md) | Composer build notes |
| [14](../design_notes/14-composer-verification.md) | Full-corpus replay measurement. Complete |
| [15](../design_notes/15-director-opportunities.md) | Director/mapping opportunities after the composer. Investigation only |
| [16](../design_notes/16-blocking-fixes.md) | Six blocking fixes and the re-measurement. Complete |
| [17](../design_notes/17-garment-displacement.md) | What a worn garment no longer covers. Built |
| [18](../design_notes/18-dim-light-proximity.md) | Dim light up close vs at range. Built |
| [19](../design_notes/19-director-orchestration.md) | The Director as orchestrator over scoped specialists. Built |
| [20](../design_notes/20-observer-epithet-floor.md) | A minted epithet is not a name. Built |
| [21](../design_notes/21-numbered-beat-events.md) | Numbered beat events, closing an ambiguity note 19 created |

[`STATE.md`](../design_notes/STATE.md) is an ephemeral session handoff, not a note.

## Audits

There are none in the tree, by decision. Five dated audit documents — the
2026-07-19 architecture audit, the information-pipeline leak sweep, the
enterprise_d_v2 backlog, the Fable adversarial-review follow-ups, and the
place-graph review — were re-verified against source at alpha 6.1 and erased
once their live findings were folded into [`UNBUILT.md`](UNBUILT.md) §3–§6,
which carries their original finding ids and enough mechanism detail to act on.

They were erased rather than kept because a stale audit is worse than none: most
of their contents had shipped, every line citation had drifted, and a reader
taking them at face value would have chased about forty closed findings. The
reasoning is in git history and `CHANGELOG.md`.

## Where status lives

`UNBUILT.md` says it is the only list of unfinished work, and that is the rule
worth keeping. It is not currently true: `Design.md`'s conformance table,
each design note's `Status:` header, `FEATURES.md`'s `(partial)` markers and
`OFFSCREEN_WORLD_COMPLETION.md`'s per-item tags are four more status surfaces.
They disagree eventually. When one of them contradicts `UNBUILT.md`, `UNBUILT.md`
is the one to fix first, and the other should become a pointer.
