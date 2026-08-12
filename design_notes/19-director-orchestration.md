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

**OFFSCREEN'S 0% IS NOT EVIDENCE IT DOES NOT MATTER — it is evidence it is
unbuilt.** Read the wrong way, that row says "delete it"; read correctly it
says the world outside the scene is a capability the engine has declared and
not yet grown. Crowds moving, couriers carrying news, plans advancing while
nobody watches, what a town does between visits: that is plausibly as complex
a task as the whole present Director, and it is the specialist most likely to
become the largest rather than the smallest.

That is an argument FOR this architecture, not a footnote to it. A monolithic
Director cannot absorb an offscreen simulator without every ordinary beat
paying for it — which is exactly why the capability has stayed at 0%, since
nothing that large could be added to an 18.7k sheet already too big. A
specialist gives it somewhere to grow that costs a beat nothing when the beat
is indoors with two people and no elsewhere in play.

**Pinned for development, not for deletion.** Its subjects (crowds, couriers,
offscreen plans) are scene facts, so the gate for it cannot miss today; the
gate will need revisiting the moment "somewhere else is happening" stops being
readable from the current scene's contents, because at that point absence of a
subject in THIS room stops meaning absence of the subject.

## Offscreen is a different KIND of parallel

The specialists above are parallel WITHIN a step: the turn fans out and waits
for them, so their latency is `max(specialist)` and their size still matters.

Offscreen is not that. The intent is that it runs alongside the main turn
entirely — the player never waits for it and never notices it happened. That
makes its size irrelevant to turn latency, which is what allows it to become
the largest specialist without costing a beat anything, and it is why it does
not belong inside the resolve step at all.

**The design problem moves to writing, not to speed.** `commit.py` is the sole
persistence boundary and a turn's mutations land in one outer transaction
precisely so there is never a second writer. Offscreen mutating the world
while a turn is also mutating it is exactly what that boundary exists to
prevent — and offscreen output is not reconstructible the way autobiographical
consolidation is (which is why consolidation is allowed to run after the write
lock). It IS world state.

**So it queues rather than writes.** Offscreen runs concurrently, produces a
PROPOSAL, and the next turn's commit applies it inside the normal transaction
through the guards that already exist. Latency is hidden, the single-writer
rule is untouched, and a proposal that has gone stale (its subject moved, its
room was destroyed) is refused by the same deterministic checks that refuse a
stale diff today. The mapping stage's propose/ratify contract is the precedent.

**Firewall.** Offscreen events reach a mind the way any other event does — by
being perceived, or by arriving as news somebody carries. Never by appearing
in a head because the simulator computed it. An offscreen simulator that can
write into anyone's knowledge directly is a leak with a scheduler attached.

**It will be large and expensive when it is done, and the architecture has to
assume that from the start rather than discover it.** Consequences that follow
and should not be retrofitted:

- **Its cadence is its own.** A world does not need re-simulating every beat.
  Whatever drives it — elapsed story time, rooms left behind, a plan's due
  date — the trigger is not "a turn happened", or an expensive task runs
  hundreds of times to report that a town is still standing.
- **Cost has to be visible and bounded.** It is the one part of the engine
  that spends money while the player is not waiting for it, which is exactly
  the shape of a bill nobody notices. `_log_usage` already records per-role
  spend; offscreen needs its own role so it is separable, and a ceiling.
- **It must be interruptible and resumable.** A long simulation racing a
  player who quits, branches or rerolls must be abandonable without leaving a
  half-applied world — which the proposal/ratify shape above already gives,
  since an abandoned proposal is simply never ratified.
- **Failure is silence, never a broken turn.** If it dies, times out, or the
  provider refuses, the story continues exactly as it does today. Nothing on
  the player's path may depend on it having succeeded.

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
