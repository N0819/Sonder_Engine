# Close-contact scenario audit — 2026-08-23

This is an experiment record, not implementation authority. It evaluates the
same general physical substrate in partnered dancing, examination, surgery,
and resisted combat. The opening scenes were authored; every playable beat ran
through the configured production Director, character, perception, narration,
specialist, and commit pipeline.

## Runs and artefacts

- Baseline: `/tmp/sonder-close-contact-baseline-20260823` and
  `/tmp/sonder-close-contact-baseline-rest-20260823`
- First optimized four-scenario run:
  `/tmp/sonder-close-contact-optimized-20260823`
- Surgical/combat authority rerun:
  `/tmp/sonder-close-contact-final-live-20260823`
- Final surgical proof run:
  `/tmp/sonder-close-contact-surgical-proof-20260823`
- Reusable harness: `tools/close_contact_scenarios.py`

Across these runs, 44 scenario turns were generated, including openings. Each
artefact directory contains `transcript.md` and full stage-level `results.json`.

## Critical assessment

| Scenario | Narrative | Physical/social realism | Judgment |
|---|---:|---:|---|
| Partnered dance | 8/10 | 8/10 | Consent and timing read naturally. The partner accepted before contact, the frame became a real standing relation, sway became an ongoing contact action, and release cleared contact. The last partner pose retained an ambiguous “right hand resting lightly” detail after release. |
| Wrist examination | 7/10 | 7/10 | History, permission, systematic examination, neutral splinting, and neurovascular recheck were convincing. The patient sometimes asked to be told before an act after it had already happened. Findings remained prose/conditions rather than a clean structured clinical-result record. |
| Minor surgery | 5/10 | 4/10 | The Director could produce clinically literate branches, but repeated generation exposed the hardest remaining failure: it can occasionally proceed after a finding falsifies an explicit “only if” predicate. Before repair, narration and patient memory also promoted a partially realized action into irrigation/suturing. The latter authority leak is now closed; conditional adjudication is reinforced but remains the weakest model-owned judgment in this audit. |
| Resisted combat | 8/10 | 7/10 | The clinch sequence conveyed timing, resistance, pummelling, counter-pressure, and failed disengagement well. Before the final floor, momentary jabs became standing contacts. That is now rejected deterministically. A stale underhook detail can survive one evidence beat while a replacement overhook is established, so contact refinement is still less exact than the prose. |

## Defects found and repaired

1. **Completed-outcome leakage before reaction.** A contestable multi-stage act
   was delivered to the other character as completed before they chose a
   reaction. Pass-one perception now exposes only the first observable phase.

2. **Partial realization promoted a whole action.** One realized effect in a
   multi-effect declaration caused every sibling phase to be narrated and
   remembered. Outcome delivery now releases the full action only when every
   disposition belonging to that action is realized. Mixed results expose only
   onset; a wholly deferred conditional alternative exposes nothing.

3. **Narrator treated raw input as objective event.** Contestable success
   branches no longer enter the numbered event record unless adjudicated. The
   narrator receives a scrubbed declaration and exact verbatim reprints of a
   player's action paragraph are removed.

4. **Interpreter invented player dialogue.** Exact player speech is retained
   only when its words are a contiguous span of the actual player input. “I
   explain the warning signs” can no longer become a newly authored quote.

5. **Momentary acts became persistent topology.** Model-resolved `strike`,
   `jab`, `kiss`, `brush`, and other event manners can no longer be added to
   the standing contact ledger. Continued contact must be stated as a durable
   relation (`press`, `rest`, `hold`, `wrap`, interior contact) with an optional
   ongoing contact action.

6. **Treatment was classified as disguise.** Splints, dressings, sutures, and
   similar treatment now route to honest condition/device state rather than
   physical disguise.

7. **Released contact left stale poses.** The spatial specialist is explicitly
   required to refresh contact-bound pose snapshots when a hold is released or
   replaced. The dance rerun cleared the hold correctly, though pose detail
   remains an area for a deterministic invalidation floor.

## Remaining design work

The most valuable next addition is a general **observation/result ledger** for
tests whose results gate later actions. It should not be medicine-specific. A
result would carry an id, observer, subject, method, bounded finding, time, and
provenance. Conditional action phases would reference the result id and a
predicate. That same mechanism serves a surgeon checking numbness, a mechanic
testing pressure, a dancer checking balance, a hacker validating access, or a
fighter checking whether a grip was actually secured. It would move branch
truth out of prose interpretation without hard-coding clinical rules.

Two smaller follow-ups are also justified:

- invalidate or refresh a pose deterministically when every contact supporting
  its relational detail is removed or replaced;
- give examinations and material procedures typed durable results and device
  state, so a splint, dressing, anesthetic, finding, and aftercare plan are not
  reduced to generic conditions or prose.

## Verification

- Focused authority/narration/contact suite: 180 passed.
- Broader changed-area suite: 364 passed.
- Code-map regeneration completed.
- Project structure checks passed.
- `git diff --check` passed.

## Adversarial sequence follow-up — 2026-08-24

A second live run added two same-pronoun cases (a consensual intimate
encounter and a two-person rescue handoff) and reran dance, medical examination,
and resisted combat. Artefacts are in
`/tmp/sonder-sequence-audit-20260824-results`; the reusable harness now exposes
the `intimacy` and `rescue` scenario names. This run contains 20 turns,
including openings.

The original regression did not recur. All 15 NPC action elements and all 25
NPC speech elements reached the player's outcome observations in their declared
action/speech order. No actor was reduced to their terminal action, and the
full run completed without a pipeline error.

### Additional defect classes exposed

1. **A described speech act can vanish from a mind.** The medical intake input
   introduced the clinician, asked injury/history/neurovascular questions,
   explained the examination, and waited for permission. Interpret's first
   output omitted the complete sequence. Its repair tried to turn summarized
   speech into invented exact quotes; the player-speech authority guard
   correctly discarded those quotes, but the fallback routed the verbatim
   declaration to *mapping*, not to the patient's perception. Rowan therefore
   received a silent clinician and answered as though no questions had been
   asked. Rescue lost `where does it hurt?`, the toe/sensation check, and the
   explanation of the east route by the same path. This needs a typed
   **communicative-act surface**: exact quotes remain quote-authority data;
   `asks about X`, `explains Y`, and `reports Z` are observable semantic acts
   that can be delivered without inventing words.

2. **A contestable onset was grammatically asserted as success.** Combat
   resolution rejected the retreat and committed `retreat prevented`, but the
   narrator's safe fallback surface was `creates space`, producing “I create
   space.” Contestable onset rendering now carries explicit attempt modality,
   so the same structure becomes `attempts to create space` until resolution
   proves the complete surface.

3. **A short quote was located inside a longer quote.** The echo-stripped
   player line `More?` was treated as present inside the NPC line `More of
   that.`, causing a false enforceable dialogue-order finding and three
   narrator calls on an already ordered beat. Ordering now locates complete
   quoted spans rather than substring prefixes.

4. **One action element can contain both the stimulus and its future.** The
   dance declaration bundled `signal dip -> take weight -> return upright ->
   release`. Pass-one perception correctly gave Mara only the signal, but the
   page placed the fully adjudicated player element before Mara yielding into
   the dip. The resulting prose returned and released her, then had her settle
   into the already-ended dip. This is not an event-stream sorting defect; it
   is missing phase identity. Compound contestable actions need stable phase
   ids/dependencies so a reaction can sit between onset and continuation.

5. **A blocked prerequisite did not cancel dependent phases.** Rescue
   movement toward `east_exit_door` was rejected by the deterministic route
   backstop. Mapping had also failed to materialize the input's “waiting
   responder.” Resolution nevertheless completed transfer, release, report,
   and the responder's steadying action. Invalid contact topology was dropped
   at commit, but prose and character cognition had already interacted with a
   bodiless participant. Phase dependencies must fail closed when their
   required arrival/entity/contact is absent; prose validation is too late.

6. **Releasing support left relational pose state behind.** Rescue contact
   removals committed while both poses still said Dana bore Reya's weight and
   Reya was supported by Dana. The next beat would begin from that
   contradiction. Contact-bound pose invalidation remains required as a
   deterministic floor; the earlier specialist instruction is not sufficient.

7. **Same-pronoun prose needs referent boundaries, not global replacement.**
   Target-owned body terms with modifiers (`her injured lower back`) now stay
   on the structured target, and naming another body ends the local rewrite.
   Direct-object and instrument pronouns remain intrinsically ambiguous:
   `kisses her` and `takes Alice's hand with her left hand` cannot both be
   solved by assuming every later `her` is Alice. The durable fix is typed
   referents (actor/target/body endpoint) on action surfaces; prose anaphora is
   only a compatibility repair.

8. **Sensor-ledger diction has inflections.** The craft screen caught
   `registers` but the live pages copied `steady pressure and shared warmth
   register` and `registering against my own`. The same bounded tell now covers
   `register`, `registers`, `registered`, and `registering` when tied to the
   compositor's pressure/warmth list, without flagging a clerk or instrument
   that legitimately registers something.

### Recommended implementation order

1. Add typed communicative acts and deliver them through perception, memory,
   public evidence, Charter observation, and narration without minting a quote.
2. Give compound contestable actions phase ids plus `requires` dependencies;
   resolution and narration should order outcomes by phase, not one compound
   prose field.
3. Require every resolved participant and contact endpoint to resolve to a
   scene body/entity/presence, and reject dependent phases when it does not.
4. Add deterministic contact-bound pose invalidation.
5. Replace same-pronoun compatibility heuristics gradually with typed action
   referents generated alongside the observable surface.

These are genre-neutral. The same machinery serves consent and intimacy,
dancing, surgery, rescue, combat, maintenance, trade handoffs, and any scene
where information or physical control changes hands.
