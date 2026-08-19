# Where the audit-and-repair stands

Written 2026-08-19 as a handoff, so the work survives a context compaction.
Supersedes nothing; `AUDIT_REPAIR_PLAN.md` still holds the owner decisions and
the A/B design, and this file says what has happened since.

## State

`main`, working tree clean, `make check` green at **8,007 tests** (7,297 when
the repair began). **444 commits** ahead of `origin/main`.

`origin/reorganization` holds the first 268 and is **176 behind** — pushing it
forward is one command and has not been done since.

## What happened

**Phase 1** — the 43 findings from the monolith-split audit. 22 landed.

**Phase 2** — twelve package audits, every line of ~112k read. ~312 findings
in `docs/experiments/AUDIT_*.md`.

**Phase 3** — four fable triage agents produced 365 rows, 325 CONFIRMED, in
`$CLAUDE_JOB_DIR/tmp/triage_*.md`. **22 were refuted at triage**, which is the
number that justifies the pass.

**Wave 1** — eleven patch agents, ~180 rows, one commit each.

**Wave 2** — planned in `$CLAUDE_JOB_DIR/tmp/WAVE2_ASSIGNMENT.md` (150 rows,
ten slices). Slices 1-9 merged. **Slice 10, the terminal tools/tests/register
sweep, is STILL RUNNING** at 15 commits — merge it when it reports.

**Six fable decision agents**, all merged: the offscreen mind-models firewall
question, the paradox ladder, the host/API shape, prompt-fragment substitution,
restraint + awareness, and greeting mind-seeding.

## Still open

1. **Slice 10 must be merged** — it owns `docs/UNBUILT.md`, `Design.md`,
   `AGENTS.md`, `CLAUDE.md`, `README.md`, `tools/**`, `docs/**` and the test
   residue, and it is applying **nine slices' worth of doc handbacks** that no
   other agent could. Until it lands, the register and the conformance table
   understate what is built.
2. **Handbacks from the six decision agents** are NOT in slice 10's brief —
   they finished after it started. Each is in that agent's final report:
   an `AGENTS.md` restraint row, `Design.md` rows for restraint/awareness,
   greeting minds, offscreen mind models and the paradox work, plus a
   `docs/UNBUILT.md` entry for condition subjects written as scene uids.
3. **The A/B run should be repeated.** `docs/experiments/AB_9_5_VS_9_6.md`
   records the first one — both installs completed ten turns, zero rollbacks.
   It tested an engine whose slowest path was an unconfigured role, and ~300
   repairs have landed since. A second run says much more.
4. **Housekeeping**: ~305 orphan test databases in `/dev/shm` (~151 MB, the
   leak itself is fixed), 43 worktrees, 36 merged agent branches. All
   destructive, none authorised.
5. **Release**: nothing written. A CHANGELOG entry, a version number and a tag
   each need their own ask, and none has been given.

## Decisions the owner made, in force

Beyond `AUDIT_REPAIR_PLAN.md`'s four:

- **Do not make the currently-active chats the priority.** Decide what is right
  for the engine; the live corpus is evidence, never the specification. This
  is what unblocked restraint and awareness.
- **Greetings**: the scene half is `director_establish`'s by decision, not a
  gap waiting to be wired. What the greeting call owes is the MIND half, now
  built.
- **Python range**: 3.11-3.13, enforced by both launchers. A newer interpreter
  has no `pydantic-core` wheel and falls into a Rust build.

## Standing constraints

- `engine.db` is the owner's LIVE database. Never write to it; reads are
  `file:engine.db?mode=ro`.
- `make check` is the gate. Never `make test-fast` to check your own work.
- Committing is not releasing.
- **Never `git add -A`** and **never `git stash`** with agents running — stash
  is repo-wide across worktrees and lost work twice in wave 1.
- Agent worktrees branch from local HEAD (`.claude/settings.json`), not
  `origin/main` — that trap put eleven agents on alpha 9.5's tree.
