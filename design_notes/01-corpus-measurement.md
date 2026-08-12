# 01 — Corpus measurement: how much of `resolved_event` already has a structured home?

**Question.** What fraction of the physically consequential content asserted in
`DirectorResolve.resolved_event` prose (schemas.py:1907) already has a structured home in the
same turn's `state_diff` (schemas.py:1737) plus the declared act/character `sequence` events —
and for the residual, what kind of content is it?

**Corpus.** Read-only snapshot `engine.db` (2.1 GB), 2,296 turns across 61 chats;
2,231 active non-stale `director_resolve` steps (one active variant each). All numbers below
come from those persisted variants. Nothing was written to the database.

---

## Two independent measurements

### A. Engine's own reconciliation telemetry (whole corpus, deterministic-check based)

The post-resolve reconciliation seam (`agents/director.py`, `_reconcile_resolve`-family;
`out["reconciliation"] = recon` at director.py:3493) **persists its full output inside every
`director_resolve` variant** — manifest, detected omissions, repair result, unresolved
residue. This is a ready-made whole-population measurement.

- Coverage: **1,885 / 2,231 turns (84.5%)** carry the telemetry (turn_id ≥ 386; the 346
  earlier turns predate the feature).
- The deep audit (`_deep_audit_omissions`) ran on **0 turns** — `audited: false` everywhere.
  So the manifest numbers below are the resolve model's *self-report* of the persistent
  changes its own prose asserts, checked deterministically against the diff
  (`_evidence_present`). That makes them a **lower bound** on prose-vs-diff residual.

**Manifest-level encoding rate (pre-repair):** 3,952 `changes_asserted` items over 1,885
turns (2.1/turn). 681 (**17.2%**) were not evidenced anywhere in the state_diff as first
returned → **82.8% of self-declared persistent changes were already encoded in the same
call's diff.**

Manifest volume by category (top): entities 975, positions 943, conditions 431, rooms 326,
contact(+contacts/contact_ops) 406, stations 173, inventory 160, attire 125, other 112,
transit 93, adjacency 79.

Detected omissions by source (all tiers, pre-repair): manifest 681, player_claim 205
(always categorized `other` by construction), structural placeholder-strips 101,
restraint_scan 41, unconsciousness_scan 18. Manifest-source omissions by category:
conditions 241, positions 203, other 74, contact(+ops/contacts) 57, inventory 32,
entities 17, rooms 16, stations 15, attire 7, adjacency 5.

**After the Tier-2 LLM self-repair** (ran on all 643 turns that had ≥1 omission):
571 items stayed on the `unresolved` list, but 217 of those were overruled by the repair
model (`rejected`/`already_encoded`). The **true residual — asserted in prose, still not
evidenced in the final merged diff — is 354 items on 261 turns**: **0.19 items/turn;
13.8% of telemetry-era turns end with at least one un-encoded persistent change.**

True residual by category: other 110 (mostly player-claim effects), positions 76,
conditions 73, inventory 25, contact 28 (contact+contacts+contact_ops), rooms 14,
attire 13, stations 8, entities 3, misc 4.

### B. Independent clause-level sample (n = 50 turns, my classification)

Methodology: 50 turns drawn with `random.Random(42).sample` from all 2,231 non-stale
resolve turns, so the sample mirrors the population (it therefore contains 3 clone-duplicate
beat pairs from branched chats — kept, and noted). For each turn I read `resolved_event`
in full and segmented it into distinct assertions (a physical claim: a movement, a contact,
an entity-state change, a speech act, a perceptual ruling, an atmosphere clause). Each
assertion was classified against that turn's `state_diff`, the `director_interpret`
sequence/movement, the `interaction_loop` character sequences, and the `dialogue_log`.
**323 assertions total** (median resolved_event ≈ 666 chars ≈ 5–6 sentences).
This is my judgment call per clause — grain and edge-cases are mine, not the engine's.

| Class | n | % of all | % of consequential |
|---|---|---|---|
| Physically consequential, homed in **state_diff** | 64 | 19.8% | 22.6% |
| Consequential, homed in **declared sequences** (interpret/character events) | 68 | 21.1% | 24.0% |
| Consequential (speech), homed in **dialogue_log** | 104 | 32.2% | 36.7% |
| **Consequential, NO structured home** | **47** | **14.6%** | **16.6%** |
| Not physically consequential (atmosphere/restatement/etc.) | 40 | 12.4% | — |

**Headline: 236 / 283 = 83.4% of physically consequential assertions already have a
structured home** in state_diff + sequences (+ dialogue_log). This independently lands on
the same magnitude as the engine's own 82.8% pre-repair manifest rate.

Turn-level: 31/50 turns (62%) carried ≥1 unhomed consequential assertion; 19/50 (38%)
were fully covered.

**Residual (47 unhomed assertions) by category** — starting from the `ReconcileOmission`
vocabulary, with three additions the data demanded (perception, transient_action,
expressive):

| Category | n | share | What it is |
|---|---|---|---|
| **perception** (added) | 13 | 28% | Director adjudicating perception *in prose*: who heard what through which wall, what a desk now occludes, a viewer screen showing another room, "the taste registers normally", a scent gradient. No `ReconcileOmission` category covers it because it is not a state change — it is per-perceiver routing, asserted by the wrong stage. |
| **transient_action** (added) | 9 | 19% | Physical acts by non-managed presences (an innkeeper's chin-jerk, a bartender working a replicator panel, crowd heads turning) or Director-invented player/character conduct that appears in no sequence. |
| entities | 7 | 15% | Entity state/behavior events never encoded: a door sliding shut after a transit, a console panel lighting up in response to touch, a machine chiming, crowd density blocking a concourse. |
| contact | 6 | 13% | Contacts asserted in prose with no `contact_ops` and no covering sequence: a tail coiling around a leg, an embrace persisting, a grapple released. |
| **expressive/pose** (added) | 6 | 13% | Perceivable body language invented at resolve time (posture squaring, head tilt, nods) belonging to no sequence and no `poses` entry. |
| positions | 3 | 6% | Granularity the schema lacks: mid-transit ("has not yet reached the doors" while the diff already places her at the destination), insertion depth. |
| inventory | 1 | 2% | An absence assertion (fingers find no combadge). |
| conditions | 1 | 2% | A character's hedonic release state present for one body but not the other. |
| lighting (added) | 1 | 2% | Room illumination changed by a carried light source. |

### Content that is not physically consequential at all

**40/323 assertions (12.4%)** assert nothing physical that isn't already state: roughly half
are *restatements of unchanged prior state* (the cup of tea is still on the ledge, the door
still spills light, X remains unconscious), ~40% pure atmosphere/sensory dressing (steam,
hums, candlelight), the rest negative/pending assertions ("she makes no move", "has not yet
responded") and interiority leakage. By character count this share is larger — atmosphere
sentences run long. This slice is deletable without any new structured home; restatements
are *re-derivable* from the scene, which is exactly what a spatial-pure perception would do.

---

## Caveats — measured vs inferred

- **Measured:** everything in section A (whole corpus, deterministic checks the engine
  itself ran and persisted); the counts in section B.
- **Inferred/judged:** section B's segmentation and per-clause classification are mine;
  another rater would move individual clauses a few points either way. Truncated sequence
  dumps forced ~6 lenient "homed_seq" calls; the residual could be modestly *higher*.
- "Structured home" ≠ "typed spatial data". Two tiers hide inside the 83.4%:
  - ~15% of the state_diff-homed assertions live in **prose-inside-structure** —
    `rooms.notes`, `world_facts` strings, entity `description`, `attire.state` free lists,
    `claim_dispositions.notes`. A pure-function perception can *route* these but cannot
    *compute* with them.
  - Sequence events carry their content in `attempt`/`observable` prose. They are
    per-event and attributable (which is what perception routing needs), but not geometric.
- The engine's manifest is authored by the same model in the same call and the deep audit
  never ran, so 17.2%/0.19-per-turn are lower bounds on prose-vs-diff divergence; my
  independent 16.6% suggests the self-report is not wildly under-counting.
- Clone-duplicate turns (3 pairs) were kept because the population genuinely contains them.

## Reading for the branch thesis

The bulk of `resolved_event` is already redundant with structure: 83% of consequential
content is homed, and another 12% of the prose is deletable narration/restatement. The
residual 17% is NOT dominated by missing state_diff fields — positions/rooms/adjacency
misses are rare (9 of 47). It is dominated by three things the schema has no vocabulary
for at all:

1. **Perception adjudication smuggled into objective prose** (28% of residual) — precisely
   the content `_redact_concealed_from_event` / `_surface_translate_event`
   (agents/perception.py:3116 / :3079) exist to fight over. If perception becomes a pure
   spatial function, this class must stop being *asserted* by resolve and start being
   *computed* — it needs deletion plus computation, not a structured home.
2. **Transient acts by unregistered presences** (19%) — a home shaped like sequence events,
   authored at resolve time for bodies that have no agent.
3. **Entity response events and micro-behavior** (15% + 13%) — transient happenings
   (a door closes, a panel lights, a face changes) that are neither persistent state nor
   anyone's declared act.

Contact (13%) is the one category where an existing typed field (`contact_ops`) simply
went unused often enough to matter.

## Pointers

- Telemetry source: `agents/director.py:3484-3527` builds `recon`;
  `out["reconciliation"] = recon` at :3493 persists it in every `director_resolve` variant.
- Pull pattern: `steps s JOIN variants v ON v.step_id=s.id AND v.active=1 WHERE
  s.key='director_resolve' AND s.stale=0`, JSON key `reconciliation`.
- Schemas: `StateDiff` schemas.py:1737, `AssertedChange` :1883, `DirectorResolve` :1906,
  `ReconcileOmission` :1941.
- Sample dump + tally scripts: session scratchpad (`sample50.txt`); regenerate with the
  seeded query above (`random.Random(42).sample(turn_ids, 50)`).
