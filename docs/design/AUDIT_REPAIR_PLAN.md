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

## Owner decisions, 2026-08-18

Taken after triage, on the 70 confirmed rows marked NEEDS-OWNER. They are
policy, not one-off answers: a patch agent meeting a new row of the same shape
applies these without asking again.

1. **Dead-but-built features: WIRE UP, delete only the truly obsolete.**
   ~35 rows are features that were built, documented, tested and called by
   nothing — `PUT /api/exemplars` (so the narrator's STYLE EXEMPLARS clause
   runs against `[]` on every install), `attire.guessed_spans` (110 of 560
   live garment records carry a guessed span), `protected_beliefs`,
   `allow_npc_initiative`, `rebuild_checkpoint_embeddings` (1,160 of 2,586
   live lore rows sit permanently unstamped for want of it). The wiring is the
   last mile of work already paid for. Delete only what is genuinely
   superseded, and delete its docs, tests and settings rows in the same
   commit. **The ten uncalled `spatial` symbols keep their standing caveat:
   they are in the facade contract, so removing one is an API change.**

2. **Hardcoded English recognizers: ROUTE THROUGH THE PACKS, AND TRANSLATE
   JAPANESE NOW.** Two dozen recognizers decide belief-confidence
   calibration, claim similarity, memory salience, durable-quote detection
   and trust movement in English literals, and there is no `mind.*` key in
   the linguistics card at all — a pack has nowhere to put a translation.
   The `ja` pack declares `"story": true`, which is a claim to support play.
   Both halves land together, so the claim becomes true rather than
   better-structured.

3. **`background_claims`: fix the gate and the writer; leave the seven live
   rows alone.** Ratification matches any ≥4-character reference appearing
   anywhere in the resolved prose, and the live corpus is 7 ratified, 0
   contradicted, 0 expired — a three-outcome design collapsed onto its one
   irreversible branch. Two of seven `lore_entries` rows carry a raw engine
   uid as a speaker, and one establishes a DENIAL as truth. Canon is
   write-once, so the gate and the writer are the repair; the existing rows
   stay until the owner chooses to clean them.

4. **Schema changes: do the carrier-envelope leak, defer the rest.** The
   player's carrier envelope is the only carrier state not frame-scoped, so
   what the player learned in one era survives a rewind or a branch and can be
   told onward in an era that never produced it — a firewall leak, and worth a
   migration on live stories. Every other schema-touching row goes to
   `UNBUILT.md` with its `DATABASE.md` checklist written out, for a dedicated
   pass with its own testing and its own release.

## Phase 4 — the A/B playthrough, after the repairs land

Requested by the owner: ten turns on the repaired tree and ten on alpha 9.5,
run IN PARALLEL, stressing as many features as possible. Designed here so the
repairs cannot quietly invalidate it.

**What it actually tests.** Not "is 9.5 good" — 9.5 is pre-tree-move, so the
three defects fixed on 2026-08-18 (the orphaned asset roots, dead self-update)
cannot exist there, and several audit findings are younger than the tag. The
question is the other one: **did ~300 repairs break anything that used to
work.** 9.5 is the control, and the only honest verdict is a regression
verdict.

**Two installs, neither touching `engine.db`.**

| | A — repaired | B — control |
|---|---|---|
| tree | working tree at HEAD | git worktree at tag `alpha9.5` (`418ab5b`) |
| database | `$CLAUDE_JOB_DIR/tmp/ab_head.db` | `$CLAUDE_JOB_DIR/tmp/ab_95.db` |
| launch | `ENGINE_DB=... uvicorn web.app:app --port 8009` | `ENGINE_DB=... uvicorn app:app --port 8010` (flat layout, pre-move) |

`providers` rows and the `agent_models` setting are copied READ-ONLY out of
`engine.db` into both test databases, so the two runs differ in engine code
and in nothing else. The owner's live database is never opened for writing and
never pointed at by `ENGINE_DB`.

**Identical inputs, scripted in advance.** Same scenario, same cast sheets,
same ten player-input strings, same seed. Improvised input would make the
comparison meaningless — a different sentence produces a different beat and
proves nothing about either build.

**Compare STRUCTURE, not prose.** Sampling differs between two runs of the
same model, so the prose will differ and that is not evidence. Per turn,
compare what the engine did:

- turn completed, or the commit rolled back
- warnings and engine notes raised, by text
- firewall tripwires fired
- which `state_diff` channels carried content
- `tools/scene_lint.py` clean after every beat
- reroll and specialist-repair counts
- wall clock per stage

A difference in any of these is a finding. A difference in wording is not.

**Feature coverage, packed 2–3 per beat**: room movement; a vehicle interior
in transit (dock edges, hatch); attire change; contact ops; an
identity-concealing disguise (the leak repaired today — the observer must not
receive the name in EITHER the act view or the outcome view); a background
presence that speaks and is then promoted (the `auto_dialogue` gate repaired
today); a departure recorded through `cast_changes` (the status vocabulary
repaired today); a destruction with a stranded-occupant check; weather and a
time advance; a memory written and recalled several beats later; a false
belief held by one mind and not another; a scale change; a comms channel.

**Cost.** Real provider calls on the owner's keys: roughly twenty turns at
eight to twelve model calls each. Worth stating before starting, not after.

## Standing constraints

- `engine.db` is the owner's live database. Never write to it; reads must be
  read-only (`file:engine.db?mode=ro`). Tests use the `temp_db` fixture.
- `make check` is the gate — compile, map, structure, full tier. Never
  `make test-fast` to check your own work.
- Committing is not releasing: a version number, a CHANGELOG heading and a tag
  each need their own ask.
