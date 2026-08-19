# Design: what a paradox may cost, and who has to agree to it

**Status:** All three decisions implemented (`world/paradox.py`,
`tests/test_paradox.py`: `TestCeilingIsTerminalNotARung`,
`TestTollIsAChosenMode`, `TestForceRestoreWritesTheScene`). No residual is
deferred from this note except the two boundary questions in §5, which are
recorded as open choices rather than unfinished work.

Instrument: none of this was found in play. No live story has ever opened a
wound — verified read-only against the owner's `engine.db` on 2026-08-18: one
chat holds an empty `paradoxes` dict, one holds a `paradox_policy` that is
byte-for-byte the default triple (`hazard` / rate 1 / `toll_in_radius: true`),
two chats hold fixed points, and zero wound markers (`paradox_consumed`, the
hazard note text) exist anywhere in the `world` table. These are decisions
about latent machinery, made before the first story finds them, which is the
one time a consequence design can be changed without changing anyone's story.

---

## 1. The ladder has four rungs; the ceiling is not a rung

`STAGE_THRESHOLDS` held five thresholds while every consequence applier
distinguished four: `_apply_warden_stage` acts at >= 1, `_apply_hazard_stage`
at >= 2 and >= 3, and no code anywhere gave stage 4 a behaviour of its own.
What stage 4 did in practice was re-run the stage-3 shapes inside
`_advance_paradox`'s ceiling call — four lines before the same call
force-restored the anchor, un-consumed the rooms, and cleared the wound.

The incoherence is not that the top rung was wasted; it is that the ceiling
was treated as a rung at all. Severity 1.0 is a **terminal event** — reality
wins — and a terminal event that first applies one more escalation step is
only harmless if every consequence is reversible. Two are not: `_apply_toll`'s
`UPDATE memories SET confidence=...` (measured in the regression test: a
traveler's memory went 1.0 → 0.95 in the very call that declared reality
restored) and a warden spawned at the ceiling, which outlives its own
resolved wound as a hostile body in the ledger.

Decided: four rungs (stages 0–3), which is the reading that makes the
constant, `_stage_for`, and the appliers agree with each other; and the
ceiling checked **before** any stage consequence in `_advance_paradox`, so a
wound that leaps from stage 1 past 1.0 in one clock jump also resolves
without a farewell consequence. The ordering is the load-bearing half — with
five thresholds trimmed to four but the old ordering kept, the same
incoherence simply moves down one rung.

## 2. The toll is a chosen mode, never a rider on the default

`_apply_stage_consequence` ran `_apply_toll` for `hazard` as well as for
`toll`. With `DEFAULT_MODE = "hazard"` and `DEFAULT_TOLL_IN_RADIUS = True`,
the policy a story gets by never opening the panel decayed its travelers'
memory confidence — a consequence the module docstring presents as its own
mode, under a mode whose own entry promises an environmental wound and says
nothing about a mind's records. The settings panel only ever writes `mode`,
so no player even has a surface where the enabling knob is visible.

The question underneath is the one worth writing down: **is memory-confidence
decay a consequence a player may receive without having opted into it?** No,
and the argument is a classification, not a taste:

Sort this module's consequences by two axes — *reversible on resolution?* and
*visible to a perceiver?*

- Hazard's wrongness note and room consumption: visible (perception reads
  `room.notes` verbatim) and reversible (`_restore_consumed` strips exactly
  what was added; rooms were only ever flagged, never deleted).
- A warden or bureau enforcer: visible (an ordinary scene entity every
  spatial and reaction system treats as real) and removable by an ordinary
  `remove_entities`.
- The toll: **invisible and irreversible.** No percept carries a confidence
  change; `_restore_consumed` touches rooms only; and there is deliberately
  no restore path for it — a spent witness is spent, which is what makes the
  mode dramatically real (§5 keeps it that way).

Memory confidence is not cosmetic. It is weighted in retrieval, so it changes
what a mind can rely on having witnessed — and what a mind legitimately
witnessed is the substrate everything downstream of the information firewall
reasons from. The engine's own discipline is that deterministic code may
*filter* what a mind receives; silently degrading what it already received is
a different act, and the only party entitled to authorize it is the story,
by choosing the mode whose entire identity is that cost. The module's own
principle — "a consequence layer that can't be configured down to nothing was
never a layer" — cuts both ways: a consequence that cannot be *declined by
never choosing it* was never a choice.

So: `hazard` never takes the toll. A story that wants both an environmental
wound and fading travelers chooses `toll` (the wound's rooms still exist as
the toll's radius) or waits for an explicit combination mode; a silent
default is not the place to ship one.

Corollary, same commit: `toll_in_radius` becomes what its name says — the
localization knob. `True` (default) charges only travelers standing in the
wound's rooms; `False` lets a traveler's continuity fade wherever they stand,
which is the reference beat itself (Marty's photograph never required Marty
to stand in the wound). It used to early-return on `False`, an off switch
that made toll mode a silent dread duplicate through a knob whose name says
nothing about off — and a mode whose only consequence is the toll cannot also
carry a hidden switch that removes it. No stored policy holds `False`, so the
resemantic changes no story.

## 3. "Force restore" means rewriting reality's ledger, not its shadow

`_force_restore_anchor` wrote `world_entities` directly, under a
`# NOTE, unrepaired:` that was honest about the problem: the frame-scoped
`world.scene` blob is the single runtime source of truth and `world_entities`
is a derived projection of the scene commit. The projection-only DELETE left
the erased body *standing in the blob* — for every perceiver, and for the
next diff that touched it to re-mint the row from, which re-trips the anchor
the restoration had just satisfied. The projection-only INSERT minted a
durable row for a body no scene ever held.

Decided: reality wins by editing the scene through the engine's own merge,
with the projection kept in step in the same call — the pair every scene
writer owes.

- **Forced deletion** goes through `merge_scene_with_diff` with a
  `remove_entities` diff, so positions, poses and substance records are
  cleaned by the entity record's names exactly as a committed removal would
  clean them, plus an explicit `positions.pop` for an anchor subject standing
  without an entity record (a cast member's shape). Then the row is deleted.
- **Forced restoration** returns the body to the blob and places it at the
  wound's epicenter when this scene still has that room — the tear is where
  reality knits itself back together, and the only place the wound knows.
  Without a standing epicenter, existence returns without a place and the
  Director brings the body onstage: inventing a room here is the category
  error the warden guard already refuses (a body appearing somewhere nobody
  was standing). The projection row is written FROM the merged blob entity —
  the direction `commit_world_entities` projects, never the reverse.

Same rule, second instance found while fixing the first:
`_apply_warden_stage` wrote its hunter into the blob alone, which is
byte-for-byte the divergence `tools/scene_lint.py` reports ("scene entity
missing from world_entities"). The warden now goes through the shared
`_project_entity_row` helper. The class is stated in `_project_entity_row`'s
docstring so the next paradox scene-writer inherits it.

## 4. Is the subsystem safe to open a wound in now?

Mostly yes, with a precise boundary. Detection, escalation pacing,
per-frame independence, resolution, and all five modes' consequences are
deterministic, tested, and now coherent at both ends of the ladder; nothing
irreversible can happen to a story that didn't choose it, and the terminal
restoration leaves both world ledgers agreeing. What remains is narrative
rather than mechanical, and is listed in §5 so the first story to open a
wound knows where the edges are.

## 5. Open choices, deliberately not taken here

- **A warden survives ordinary resolution.** `state["consumed"]["entities"]`
  is written by nothing; a hunter spawned at stage 1 remains after the anchor
  is re-satisfied. Left as designed-for-now: the warden is an ordinary scene
  entity, and what becomes of a hunter whose wound closed is a Director/story
  question (it can be written out with a plain `remove_entities`), not a
  cleanup this module should silently perform. If play shows lingering
  wardens are always wrong, the fix is to record spawned entities in
  `consumed.entities` and extend `_restore_consumed`.
- **Cross-frame scenes.** `world_entities` has no frame partitioning (the
  documented Stage-3 limitation), so force restore edits the operative
  frame's scene and the chat-wide projection; another frame's blob that also
  holds the entity is not edited. Same boundary the whole subsystem already
  lives inside.
- **The toll has no restore path, on purpose.** Resolution stops further
  decay; it does not refund confidence. A witness that faded while reality
  was tearing does not un-fade because the tear closed — that irreversibility
  is the mode's dramatic weight, and is precisely why §2 makes it opt-in.
