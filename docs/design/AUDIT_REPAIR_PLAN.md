# Repair-and-re-audit plan

Status: NOT STARTED. Written 2026-08-18 as a handoff, so the work survives a
context compaction. Three phases, in order. Do not merge them.

## Where things stand

`main` is at the tree move, `make check` green (7,274 tests), **47 commits
unpushed**, working tree clean. Today landed, in order: alpha 9.5; the split of
`spatial.py` → 13 modules, `commit.py` → 14, `agents/director.py` → 9 (Phase 1
only); then 81 modules out of the repository root into eight subsystem packages
(`core llm world mind story dressing persist web`) beside `agents/`.

Reference documents, all current:

- [`DESIGN_MODULE_LAYOUT.md`](DESIGN_MODULE_LAYOUT.md) — the layout, its limits,
  and what the move actually cost. **Marked LANDED.**
- [`SPLIT_SPATIAL.md`](SPLIT_SPATIAL.md) / [`SPLIT_COMMIT.md`](SPLIT_COMMIT.md)
  / [`SPLIT_DIRECTOR.md`](SPLIT_DIRECTOR.md) — the executed plans. `SPLIT_DIRECTOR`
  still carries an unstarted **Phase 2**, which is a separate decision.
- [`../UNBUILT.md`](../UNBUILT.md) §1.52 — the register entry indexing all 43
  findings.
- `docs/experiments/AUDIT_{SPATIAL,COMMIT,DIRECTOR}.md` — full detail, each
  finding carrying `file:line` **as of `418ab5b`** plus the commit that moved
  the code. Line numbers have all changed since; resolve by symbol name.

## Phase 1 — repair the 43

One commit per finding, each with a failing test first where the finding is
live. `make check` green before every commit. Do NOT batch unrelated fixes: the
whole point of flagging rather than fixing was that a repair should be
bisectable to its own cause.

Verified live by hand before this plan was written, so start here:

1. **`_LIST_DELEGATED` and `_DELEGATED_CHANNELS` are frozen; `_CHANNEL_SPECIALISTS`
   is not.** All three in `agents/director_scopes.py`. An extension family's
   list-valued channel returns a list, misses the hand-written frozenset, and
   `_normalized_channel_value` (`agents/director_fanout.py:286`) replaces it with
   `{}` — dispatched, accepted, discarded, silently. The scope backstop is
   likewise blind to any channel registered after import. **One shared fix**:
   derive both from `SPECIALISTS` inside `_rebuild_channel_owners()`, exactly as
   `_CHANNEL_SPECIALISTS` already is. Extension-facing, so it matters while
   Directive is porting against `ext_api: 1`.
2. **The `auto_dialogue` promotion threshold is enforced nowhere.**
   `auto_promote_background_characters` (`persist/commit_background.py`) gates
   only on `addressed_turns >= _promote_after_addressed`; the function contains
   ZERO references to `AUTO_PROMOTE_DIALOGUE_THRESHOLD` while its own docstring
   promises it. Decide which is true — the docstring or the code — and make the
   other match.
3. **`_BARRIER_ALIASES` maps `'one_way_mirror'` twice** (`world/spatial_barriers.py`,
   lines 63 and 87 of 128 keys). The first mapping is dead; which wins is a
   source-order accident.
4. **`world_entities.retired_turn_id` is filtered on and never written.**
   `persist/commit_common.py:342` filters `retired_turn_id IS NULL`; the removal
   path DELETEs rows instead, and the only write is the checkpoint restore
   round-tripping NULLs. `core/db.py`'s comment claims `room_registry` mirrors
   it. Either the delete becomes a retire, or the column and comment go.
5. **`commit_cast_changes` silently drops every status but `active`/`dormant`**
   while `llm/schemas.py`'s own worked example writes `"departed"` and the
   prompt names no vocabulary at all.

Then the rest, from the three audit files. Three carry a standing caveat:

- The **ten uncalled `spatial` symbols** are all in the facade contract. Deleting
  one is an API change, not a cleanup — decide deliberately.
- The **three dead Director cue constants** cannot simply be deleted either;
  their tests assert against them. Rewrite the tests to
  `english_linguistic("agents.director", ...)` first — `tests/test_language_packs.py`
  already shows the form — then drop the constants.
- **Comment/label defects are still defects** here, but they are the cheapest
  and should not crowd out the live ones. Do them last, batched by file is fine.

## Phase 2 — a whole-codebase audit, now that it is navigable

Fan out subagents by PACKAGE, which is the thing the reorganisation just made
possible: `core llm world mind story dressing persist web agents` plus
`extension_runtime`, `language_runtime`, `tools`, `static/js`. Nobody has read
`mind/memory.py` (5,496 lines), `llm/schemas.py` (5,253) or `web/app.py` (5,772)
end to end the way the three monoliths were just read.

Each agent gets the same brief the split agents got, minus the moving: read
every line of its package; report defects with `file:line`; **flag, never fix**;
and separately report what the code actually does, checked against what
`Design.md`, `AGENTS.md`, `docs/guides/` and the design notes claim about it.
Findings go to `docs/experiments/AUDIT_<PACKAGE>.md`, one file per agent — NOT
to `UNBUILT.md`, which would conflict N ways.

Categories that paid off last time, and the reasons they did:

- dead code, and guards whose condition can no longer be true
- a configurable value nothing reads (found twice today)
- a list that must be kept in sync by hand and is not (found three times today)
- two representations of one rule, free to drift
- silent tolerance of empty, missing, or unknown values
- comments describing behaviour the code no longer has
- tests that assert by absence, or on source layout, or against the wrong object

## Phase 3 — cross-verify, THEN repair

Do not repair Phase 2's findings directly. Every finding gets an independent
verifier — a different agent, told to REFUTE it, defaulting to refuted when
uncertain. Today's own record is the argument: of my four claims about this
codebase this session, one ("0 own-speech memories corpus-wide") was wrong, one
overstated a count 4-vs-3, and a fable agent's §1.51 claim about a missing test
was false. **A finding is a hypothesis until somebody tries to kill it.**

Survivors become the repair batch, run like Phase 1: one commit per finding,
failing test first, `make check` between.

## Standing constraints

- `engine.db` is the owner's live database. Never write to it; reads must be
  read-only (`file:engine.db?mode=ro`). Tests use the `temp_db` fixture.
- `make check` is the gate — compile, map, structure, full tier. Never
  `make test-fast` to check your own work.
- Committing is not releasing: a version number, a CHANGELOG heading and a tag
  each need their own ask.
