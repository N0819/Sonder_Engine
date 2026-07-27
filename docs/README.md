# Documentation Index

## Maintained implementation guides

- [`../README.md`](../README.md): setup and repository overview.
- [`../AGENTS.md`](../AGENTS.md): practical editing rules and invariants.
- [`../CLAUDE.md`](../CLAUDE.md): Claude Code entry point into the same
  maintained guide set.
- [`PIPELINE.md`](PIPELINE.md): implemented turn execution and debugging map.
- [`DATABASE.md`](DATABASE.md): persistence and schema-change guide.
- [`TESTING.md`](TESTING.md): fast/full/browser test tiers, dependency constraints, and CI policy.
- [`CODE_MAP.md`](CODE_MAP.md): generated structural index.
- [`../agents/README.md`](../agents/README.md): pipeline package ownership and
  stage-addition checklist.
- [`../tests/README.md`](../tests/README.md): regression-test placement and
  database-fixture rules.
- [`RESEARCH.md`](RESEARCH.md): sourced bibliography — research the code cites (belief revision, RRF/MMR, Novikov) and the established work the architecture maps onto.
- [`../Design.md`](../Design.md): full product philosophy, current architecture, weaknesses, and roadmap.

`CODE_MAP.md` is generated. The other maintained documents are curated and
should explain intent rather than mirror every function.

Character-psychology changes span the maintained guides: `PIPELINE.md` owns the
runtime information flow, `../Design.md` owns the psychology model and known
gaps, and `../AGENTS.md` owns the edit/test routing.

## Scoped audits and design records

`ARCHITECTURE_AUDIT_2026-07-19.md`, `AUDIT_FOLLOWUPS.md`,
`FABLE_REVIEW_FOLLOWUPS.md`, and the `*_DESIGN.md` files preserve a dated audit,
an implementation proposal, or a subsystem-specific rationale. They are useful
context, but they are not current implementation authority unless their claims
also agree with source and the maintained guides above.
