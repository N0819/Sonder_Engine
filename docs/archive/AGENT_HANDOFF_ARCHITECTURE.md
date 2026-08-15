# Agent handoff — architectural completion and off-screen life

> **ARCHIVED.** A session handoff for the off-screen build, kept for its
> "Known traps" and edit map. Its required-order list is now entirely
> `[built]`. Current status is in
> [`../design/OFFSCREEN_WORLD_COMPLETION.md`](../design/OFFSCREEN_WORLD_COMPLETION.md);
> the normative architecture is in
> [`../design/OFFSCREEN_WORLD_ARCHITECTURE.md`](../design/OFFSCREEN_WORLD_ARCHITECTURE.md).

This is the concise working map for the next coding agent. Read the linked
maintained documents before editing; do not treat this handoff as runtime
authority.

## Intent

- Keep the core genre-agnostic. Core owns causal/physical/epistemic structure;
  lorebooks and the Director supply setting law and genre meaning.
- Preserve the pipeline firewall: Director knows objective causality,
  Perception builds observer-specific evidence, characters decide privately,
  Narration sees only the player's view, `commit.py` persists.
- Make the world feel alive through structured aftermath and fallible carriers,
  not omniscient cutaways.
- Spend by dramatic density. Long stories and large casts must be cheap while
  nothing relevant is happening.

Normative proposal: [`OFFSCREEN_WORLD_ARCHITECTURE.md`](../design/OFFSCREEN_WORLD_ARCHITECTURE.md).
Detailed off-screen rationale: [`OFFSCREEN_LIFE_DESIGN.md`](../design/OFFSCREEN_LIFE_DESIGN.md).
Living-world frontier: [`DESIGN_LIVING_WORLD.md`](../design/DESIGN_LIVING_WORLD.md).
Crowd substrate: [`DESIGN_CROWDS.md`](../design/DESIGN_CROWDS.md).

## Current status at start of this build

Built:

- deterministic gap skeleton and `subject_last_seen`;
- seeded provisional stochastic ticks;
- out-of-band profile-state producer with rollback guard;
- A/B/D living-world floors: routine residue, scheduled consequences, place
  obligations;
- one off-screen authority ceiling and bounded actor cap.

Current unreleased state:

- the frame-scoped world epoch and honest fire-rate instrumentation are built;
- seeded/profile producers use that epoch, not `director_establish` or raw turn
  cadence;
- the reactive E floor is built as grounded typed plan stages with no model
  call at firing, and its plan state restores with checkpoints;
- the checkpoint/archive/branch-safe `world_events` spine is built and receives
  only fired mechanics rows; full character agents and re-contact settlement
  remain unbuilt;
- C's first physical floor is also built: public surfaces enter only a
  co-located registered witness's frame-specific state and follow that holder's
  movement; crowd/message copying and degradation remain;
- character-card opt-in and `full_agent_candidates` are built; no paid producer
  or landing exists yet, so `character_agent` remains honestly unavailable;
- E's floor is built; its adaptive ceiling remains gated on C.

## Required order

1. [built] Add a stable frame-scoped world/off-screen epoch derived from canonical time,
   top-level location change, opening, and due events.
2. [built] Move seeded and profile producers to that epoch. Remove the
   `director_establish` and raw-turn cadence assumptions.
3. [built] Store opportunity/fire results and extend `tools/fire_rates.py` with
   denominators.
4. [built] Add typed reactive plan stages using existing consequence validation.
5. [built] Activate `world_events` with checkpoint/archive/branch fidelity.
6. [physical floor built] Build carrier C before allowing full agents to adapt
   to player-caused facts; finish crowd/message copies separately.
7. [selection built] Add the reduced private character/Director job; card
   opt-in and private-reason candidate selection already exist.
8. Land full-agent consequences, plan updates, and stable memory event keys.
9. Derive re-contact settlement from committed records; measure before adding a
   refusal-budget protocol.

## Verification checkpoint

The working tree at this boundary passes `make check` against a freshly
initialized isolated database: **5,112 tests passed** on 2026-08-09. The
command must initialize the temporary database before running the suite:

```bash
tmpdir=$(mktemp -d /tmp/sonder-offscreen-check.XXXXXX)
export ENGINE_DB="$tmpdir/engine.db"
python -c 'import db; db.init()'
make check
```

Compilation, project-structure validation, generated code-map refresh, and
`git diff --check` also pass. No project server was started. This is the safe
handoff boundary before the paid full-agent producer; do not infer that steps
7–9 are complete from the presence of candidate selection.

## Invariants to test at every step

- Same epoch + same seed + same inputs yields byte-identical deterministic
  output.
- Reroll/restore/branch cannot double-land a tick or job.
- A background job validates base turn and frame before writing.
- An absent character never receives player position/actions unless a carrier
  it legitimately learned from provides that information.
- Distance may select spend but is absent from model content.
- Lower rungs cannot write consequences, plans, canon, or memory.
- Only full Director-adjudicated agent work may create new world consequences.
- Off-screen output is state, never narrator prose.
- Unknown configuration falls to the documented safe/default behavior.
- All new persistent keys are covered by checkpoint, archive/import, branch,
  and deletion tests per `docs/guides/DATABASE.md`.
- `world_events` is the one objective happened-event spine; do not add an
  ad-hoc competing log. New columns/readers must keep its checkpoint,
  archive/import, branch-remap, cleanup, and cross-install fidelity tests whole.

## Edit map

- Ceiling/config/UI: `scene.py`, `app.py`, `static/js/settings.js`
- Epoch/ticks/jobs: `offscreen.py`, `jobs.py`, `commit.py`
- Consequences/events: `living_world.py`, `mechanics.py`, `canon_provenance.py`
- Information carriers: `carriers.py`, holder state, private character payload
- Private character context: `agents/character.py`, `memory.py`,
  `character_schema.py`, `schemas.py`, `prompts.py`
- Re-contact: `gaps.py`, mapping/Director payload seams
- Persistence: `db.py`, `checkpoints.py`, `chat_archive.py`
- Measurement: `tools/fire_rates.py`
- Maintained docs: `Design.md`, `docs/guides/PIPELINE.md`, `docs/guides/DATABASE.md`,
  `docs/UNBUILT.md`, generated `docs/CODE_MAP.md`, `CHANGELOG.md`

Run the narrow off-screen/living-world tests first, then `make map`,
`make structure`, and the full isolated `make check`. Never start or leave a
user-facing server; temporary test servers must be shut down.

## Known traps

- `prepare_mapping_commit` may skip when no lore/facts/introduction exists, so
  off-screen progression cannot remain inside `commit_mapping`.
- `director_establish` is opening-scene generation, not a reusable boundary.
- `standing_intentions` is untyped. Prose matching may choose spend, but cannot
  authorize consequence content. Type plans before reactive writes.
- `offscreen_log` is provisional history, not a second canon ledger.
- Derived gap facts should not be duplicated into lore. Persist only adjudicated
  events or genuinely invented particulars with provenance.
- Do not hand-edit `docs/CODE_MAP.md`; regenerate it.
- The unreleased changes belong under `CHANGELOG.md`'s **Unreleased —
  Development** heading, never inside the published alpha 7.2 release entry.
