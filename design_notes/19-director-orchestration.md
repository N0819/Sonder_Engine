# The Director as an orchestrator over scoped specialists

**Branch `director-orchestration`, opened 2026-08-12.** Experiment, not a
landing. `docs/UNBUILT.md` §2.16 holds the argument and the measurements; this
note holds the architecture and the decisions already closed, so the branch
does not re-litigate them every time it is picked up.

## Why, in one paragraph

`director_resolve` reads 18,718 tokens of static instruction sheet plus a
~7,500-token payload — the prompt is 71% of a median call. Roughly 10–11k of
it is conditional machinery a typical beat does not touch, and six op families
have never fired once across 2,243 stored resolves while costing ~1,870 tokens
of instruction on every one of them. It is also the only stage that can make a
turn uncommittable, and 84% of rerolls begin at a Director stage. The owner's
thesis: *the Director is the single most complex task and the most failure
prone, and anything that reduces its payload may increase its reliability.*

## The shape

Each Director stage stays ONE pipeline step, and fans out inside itself:

    one step (one steps/variants row)
      dispatch        which specialists this beat needs, decided HERE
      prose author    one call, owns resolved_event
      specialists ∥   parallel; each owns state_diff channels; each reads the prose
      assemble        cross-channel judgments, deterministic

**One step, not several.** Reroll, replay, rerun-from-stage and variant
storage are untouched: the fan-out is internal. `agents/runtime.py` needs to
know nothing new, and every stored turn replays through the same step key.

**One prose author.** Splitting prose from diff is refused, not deferred:
prose↔diff reconciliation is the largest measured defect class in resolve's
warnings, and blind concurrent peers make it structurally unfixable rather
than merely error-prone. Structure is owned AGAINST the prose — the pattern
alpha 8.0 used to make perception deterministic.

## Both stages dispatch, and neither inherits the other's plan

`director_interpret` cannot gate `director_resolve`. Characters declare
between them, and a declaration brings channels into play that nothing at
interpret time could have predicted — an NPC smashing a lantern is
`destruction` and `overlays` out of nowhere. A flow plan fixed at the top of
the turn does not survive the middle of it.

So each stage dispatches at its own time from what is true THEN: interpret
from the player's declaration, resolve from the whole beat including every
character result.

## The gate must fail open, and gates on STATE rather than prose

This is the one thing that could make the Director less durable rather than
more. A specialist that is wrongly skipped is a silently dropped channel — no
warning, no retry, nothing in the ledger. That failure class has cost this
codebase a measurement three times (`entry_ops`, `offscreen_plan_ops`,
`project_ops`) and once hid the very guard built to catch it (the `ForwardRef`
blind spot in `tools/project_check.py`, 2026-08-12).

**Gate on scene state, not on the beat's words.** "Are there couriers in this
scene", "does anyone present wear anything", "is there a crowd here" are
facts — checkable, cheap, and incapable of missing, because if the subject
does not exist there is no op about it to lose. Prose matching would be the
silent-drop risk, and `docs/UNBUILT.md` §3.1 already refuses it as a boundary.

Where structure cannot decide, THE SPECIALIST RUNS. A scoped specialist with a
1–2k prompt costs little to run needlessly, and that asymmetry is what lets
the gate be generous: the saving comes from never loading machinery whose
subject does not exist, not from predicting cleverly.

**Backstop.** A deterministic post-check in the shape of `changes_asserted`
reconciliation, pointed at the gate instead of the channel: if the resolved
prose asserts a change and no specialist owned it, say so.

## The split, sized against the corpus

Candidate specialists and how often each would actually run, measured over all
2,243 stored `director_resolve` outputs:

| specialist | channels | fires on |
|---|---|---|
| spatial | positions, rooms, stations, poses, remove_rooms, remove_adjacent | 60.0% |
| objects | entities, remove_entities, inventory_ops, destruction, artifact_ops | 58.5% |
| body | attire, conditions, vitals, overlays | 25.7% |
| contact | contact_ops, substance_ops, containment, scales | 21.5% |
| social | cast_changes, introductions, world_facts, following_ops | 9.1% |
| offscreen | offscreen_plan_ops, crowd_ops, telling_ops, courier_ops | **0.0%** |

**Mean 1.75 of 6 per beat.** 12.1% of beats need none at all — prose and
nothing else. 76% need two or fewer. Five specialists at once happens on 0.3%.

The offscreen family has never fired in 2,243 beats and is the clearest case
for cold storage rather than conditional inclusion: its subjects (crowds,
couriers, offscreen plans) are scene facts, so the gate for it cannot miss.

## What stays with the orchestrator

The cross-channel judgments, which cannot be seen from inside one channel:

- the movement backstop validates against the MERGED diff (a door another
  channel opens this beat is what makes the route passable);
- substance destinations derive from contact topology;
- a `scales` change cancels contacts before the beat's own contact ops;
- containment derives positions;
- stations key to rooms' anchors.

The orchestrator is therefore not purely a router.

## Per-specialist models

`agent_models` already keys configuration by role, so a lean fast model for a
scoped structural task and a frontier model for the prose author is a
configuration change rather than new machinery. Untested; one of the more
interesting things this experiment can measure.

## How it gets judged

Not on argument. Every latency and error-rate number behind the case above was
served by a router silently substituting backing models, and cannot be
segmented — `providers.py` now records the model that actually answered
(`_note_served_model`), and a PINNED model is a precondition for any
measurement here meaning anything.

Success metric is the deterministic detectors already in place: reconciliation
omissions, authority residuals, uncommittable turns, rerolls. Not a subjective
read of the prose.

## Closed, so the branch does not reopen them

- **Prose and diff are not split.** One prose author, always.
- **Not a plan decided once per turn.** Both Director stages dispatch.
- **Not one step per specialist.** One step per Director stage, fan-out inside.
- **The information firewall is not a performance trade.** Every specialist
  needs an explicit entitlement; the Director's omniscience is justified by
  owning objective causality, and a specialist that emits text reaching a
  perceiver does not inherit it.
- **`commit.py` stays the sole persistence boundary.**
