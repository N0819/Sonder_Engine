# The Director as an orchestrator over scoped specialists

**Branch `director-orchestration`, opened 2026-08-12.** Experiment, not a
landing. `docs/UNBUILT.md` §2.18 holds the argument and the measurements; this
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

---

# Design detail — as built (body, social, contact, objects; both stages)

Behind the `director_orchestration` setting (`orchestration_enabled()` in
`agents/director.py`): default OFF, any of `1|on|true|body` turns it on, and
OFF is byte-for-byte the old path — the monolithic sheet is a byte-identical
recomposition of named segments in `prompts.py`, verified against the
pre-split sha256 on every change. Everything below lives inside the two
Director steps; `agents/runtime.py` learned nothing, and
`tests/test_director_orchestration.py` pins each joint.

## One correction to the note above, from the owner, and it closes a fork

The section that framed conditional prompt assembly as the CHEAP ALTERNATIVE
to orchestration is retracted: **they are not competitors, they are levels of
one hierarchy.** Orchestration gives ownership, parallelism and fault
isolation; intra-specialist conditional assembly gives the token savings.
Dispatch specialists, then assemble each specialist's sheet from the channels
it needs. Measured over the 2,243 stored resolves, a specialist that runs at
all almost always touches exactly ONE of its own channels (objects 1.11 of 5,
social 1.10 of 4, body 1.13 of 4, contact 1.22 of 4, spatial 1.52 of 6), so
an unscoped specialist carries ~4x what the beat needs — which is what makes
the 1–2k specialist figure above real without rewriting a word.

## Scope: the orchestrator measures how much of a job a specialist needs

The orchestrator's output per specialist is not a boolean — it is a SCOPE,
the set of that specialist's channels with possible work this beat
(`_dispatch_specialists` over `_CHANNEL_GATES`). Everything follows from that
one value:

    scope == empty         not dispatched at all
    scope == some channels dispatched; sheet = core + those channels' chunks
    scope == all channels  dispatched with everything (the fail-open ceiling)

Dispatch is `bool(scope)` — one computation, one code path, so "which
specialists run" and "how much sheet loads" can never disagree. Per-CHANNEL
gates read standing scene state and structured declarations only (the
conditions/contact/containment/scale ledgers, the wardrobe, the survival
setting, posted notices, carried reports, destructible entities,
`_beat_has_physical_activity`, declared speech): never prose. FAIL OPEN per
channel: a channel is gated out only when its subject provably does not
exist; where structure cannot decide, it is in scope, which is why most
gates degrade to `physical_beat`.

**Documented residuals, all backstopped, none closed:** dressing a fully
bare body (attire gates on `anyone_wears`; the manifest backstop catches
it); posting an INVENTED claim with nothing standing and nothing carried
(artifact_ops; reconciliation catches it); narrated destruction of a bare
room (`destruction` gates on a destructible entity; the deterministic
destruction tripwire stays core and warn-only, as before).

**One backstop covers both gating levels** (`_orchestration_scope_backstop`,
run LAST on the final reconciled output): if content shipped for a channel
not in any SERVED scope — a `changes_asserted` entry in that channel's
category, or channel content in the final diff — say so via `tell_director`.
A wrongly-skipped specialist and a wrongly-omitted chunk are the same fact
at this level. A specialist's `notes` lane is the under-grant escape valve
from the other side: its sheet tells it never to emit a channel it has no
block for and to flag the work instead; notes reach `tell_director` too, and
an out-of-scope emission that arrives anyway is kept (fail-open, asserted
state is never discarded) and reported.

**Measured per beat and persisted** on the step's `orchestration` record:
`scope_report = {granted, served, produced}`. Under-grant is the dangerous
direction and the backstop catches it; over-grant is only cost, and is the
number that says how well the scoping works.

## Chunked sheets, enforced

A specialist's sheet is authored as a shared CORE (identity, source scope,
output contract, refusals — the only part that always loads) plus one chunk
per owned channel, keyed by the channel name
(`prompts.SPECIALIST_PROMPT_SPECS`); assembly is literally
`core + [chunk[c] for c in scope]` in canonical order
(`prompts.specialist_prompt`), cache-stable per scope combination. The
chunks REUSE the same segment constants the monolith is recomposed from
(one spelling), plus a specialist-only shape fragment each; per the owner,
a specialist's own prompt MAY later be rewritten leaner than the verbatim
blocks — it exists only on the orchestrated path — but that is deferred
prompt-writing work, not architecture.

`tools/project_check.py` (`check_specialist_prompt_chunks`) makes the
structure checkable: every owned channel has a chunk; no orphan chunks; the
three registries (`agents/director.SPECIALISTS`,
`prompts.SPECIALIST_PROMPT_SPECS`, `schemas.SPECIALIST_CHANNELS`) agree; the
assembled sheet passes the `_ops` drift check against its own schema; and a
specialist's core never names its own channels (word-boundary regex).
**Limitation, recorded rather than papered over:** the core-purity check
cannot see a paraphrase — a core that described a channel's rules without
naming it would pass. The honest guarantee is only that channel names, and
therefore channel shapes and `state_diff.<channel>` references, cannot live
in a core.

## Both stages, one specialist definition

Interpret and resolve are equivalent in capability — interpret is the same
authority scoped to the player's input (the alpha-8.1 fix), and the
orchestration must not rebuild that asymmetry by construction. So the
specialists are SHARED: one definition, two callers, differing only in
source and dispatch timing. `payload.source` names the scope of a call:
`resolved_beat` (encode what the authoritative prose asserts) or
`player_declaration` (encode ONLY what the declaration asserts as already
true or completed; attempts and contestable acts encode nothing). At
interpret the channels merge into `state_assertions` — contact into
`contact_assertions`, the interpret spelling of the same channel — BEFORE
the deterministic validators (`validated_player_state_assertions`,
`_validated_player_contact_assertions`), so the merged result crosses the
exact floor a model-authored copy crosses. Each stage dispatches at its own
time from its own facts; nothing is stored between them. The interpret-side
specialist never receives `ctx.input` or `private_thought` (the X19 lesson):
it reads the structured declaration.

## The specialist contract

One call per dispatched specialist: role = step key (`director_body`,
`director_social`, `director_contact`, `director_objects`; in
`providers.ROLES`, inheriting the `director` model via `ROLE_FALLBACKS` when
unconfigured, always separable in `_log_usage`). Schemas own exactly the
channels (`DirectorBodySpecialist` etc.); validation prunes a malformed
channel rather than failing the call, and `preprocess_llm_output` unwraps
the `state_diff`/`state_assertions` envelope a model sometimes adds. A
failed specialist leaves the stage model's channels standing, warns, and
never kills the beat. Assembly is ownership per GRANTED channel; everything
outside the channels is untouched, and the deterministic projections that
override model output in the monolith (player state assertions, character
contact endings, following ops, movement backstop, restraint floor,
reconciliation) run AFTER assembly on the merged output — same authority
order, same detector signals, pinned by the parity test.

**Entitlements, per specialist** (enforced by the entitlement tests): each
receives the beat (prose+dialogue at resolve; the structured declaration at
interpret), declared action attempts, final dice, its categories' manifest
entries, the roster — plus its OWN ledgers only: body gets the wardrobe,
overlays, active awareness (with condition ids), vitals when tracked, extra
body parts, a room-name index; social gets background presence names;
contact gets the standing contact ledger (post-onset at resolve), the
containment and scale records, actor-owned endings and material effects,
extra parts, room and entity name indexes; objects gets the scene entities
with state, posted notices with ids, a room-name index. None receives the
room graph, lore, minds, positions, world machinery, or another
specialist's ledgers.

**`following_ops` finding:** the corpus table lists it under social, but it
is actor-owned and engine-projected (`_collect_following_ops` overwrites the
channel deterministically every resolve) — no model authors it, so no
specialist owns it. Social owns three model channels, not four.

## The fan-out is genuinely parallel, and never streams

Specialists produce structured output, not player-facing prose — only prose
streams, and that is the prose author alone. So the ∥ in the shape has no UI
question in it: `_run_specialists` submits every dispatched specialist to a
thread pool, each call running under a COPY of the caller's context (the
`loops.py`/`narration.py` precedent — `copy_context` is what carries
`cancel_event` into the worker, so a cancelled turn aborts in-flight
specialists through the existing `_check_cancel`) with both sinks cleared.
Three properties, each pinned by a test:

- **Deterministic assembly:** results are collected per specialist and
  merged in canonical `SPECIALISTS` order, never completion order — the
  test inverts completion order with delays and asserts the sequential
  merge.
- **Failure isolation survives concurrency:** a failed call becomes that
  specialist's recorded error and never touches a sibling's completed work,
  including two failing at once.
- **Cancellation:** `Aborted` is the one exception that propagates — a
  cancelled turn has no beat to fail open into.

Measured through the real fan-out with a 0.5s-per-call provider stand-in,
five dispatched specialists: sequential 2.50s → parallel 0.51s, machinery
overhead 9ms. The critical path is `max(specialist)` instead of
`Σ(specialist)`; at live structured-call latencies (1.5–4s) a physical beat
dispatching four or five specialists gets seconds back per beat.

## The numbers, as of this build (all six specialists)

Sheets (chars ÷ 4 ≈ tokens; **monolith 21,064 tok**, byte-identical when the
flag is off):

| specialist | core | full sheet | expected loaded* | biggest chunks |
|---|---|---|---|---|
| body | ~0.7k | ~4.3k | **~1.7k** | attire 1.8k, conditions 1.5k |
| social | ~0.7k | ~0.9k | **~0.7k** | (all three chunks < 0.1k) |
| contact | ~0.7k | ~4.0k | **~1.7k** | contact_ops 1.5k, substance 1.0k |
| objects | ~0.7k | ~2.7k | **~1.2k** | entities 1.0k, destruction 0.6k |
| spatial | ~0.8k | ~3.0k | **~1.4k** | positions 0.9k, rooms 0.5k |
| offscreen | ~0.7k | ~3.4k | **~1.2k** | crowds 0.8k, couriers 0.7k |

\* core + mean-touched × average chunk — a FLOOR, from the corpus touched
distribution. The fail-open gates grant more than the touched distribution
(most undecidable channels degrade to `physical_beat`), so real loads sit
between "expected" and "full"; the persisted `scope_report` is what settles
it per beat.

**The headline pair, against the 21,064-token monolith:**

- **Largest single call: lean core ~9,236 tok** (down 56%). The delegation
  note is ~1.1k of that — it covers six families and every surviving prose
  duty, and is the main reason the core sits above the ~8.2k arithmetic
  target.
- **Typical-beat sheet total (floor, corpus fire rates): ~11.6k tok** —
  lean core + fire-rate-weighted expected specialist loads.
- **In practice (fail-open, a full physical beat):** body+social+contact+
  objects+spatial dispatched with generous scopes ≈ 13–14k of specialist
  sheet on top of the 9.2k core ≈ 23k TOTAL — at or slightly above the
  monolith in total tokens on the heaviest beats, but spread over parallel
  calls none of which exceeds 9.2k, which is the reliability thesis. A
  dialogue beat runs ~10–12k total. Offscreen is cold on both (0 fires in
  2,243 beats; it dispatches the moment a crowd, courier, carried report or
  unratified claim exists — pinned by test in both directions).

**Said plainly, per the owner:** social's gate barely gates — world_facts
and introductions are undecidable from scene state, so social dispatches on
any beat with speech or physical activity. That is fine at a 0.9k full
sheet and is not a working gate; it is a cheap specialist with a formality
in front of it.

## What remains after this build

- The prose author's PAYLOAD is untouched (still the full monolithic
  payload); payload slicing is the next real token win.
- Interpret's own sheet is not leaned (its model still writes the delegated
  channels; ownership assembly resolves the double-write).
- Leaner rewrites of specialist chunks are permitted (they exist only on
  the orchestrated path) and deferred — the verbatim blocks keep one
  spelling with the monolith.
- The offscreen SIMULATOR (out-of-band, propose/ratify) stays owner-
  deferred; what shipped is its ops surface and gate only.
- The measurement: flag on vs off on a pinned model, judged by the
  deterministic detectors plus the persisted scope_report, before the flag
  may default on.
