# Character continuity: 2026-09-16

## Scope

The character already receives its authored identity, earned memory, current
observations, beliefs, intentions and emotion. This change repairs the joins
between those inputs, its decision and the next turn. It adds no model call to
the runtime and does not introduce a private thought transcript.

## Changes

- Preserve explicit enacted and suppressed wants through normalization. A
  lower-urgency choice such as restraint can remain the choice even when the
  unchosen impulse is stronger. Capacity limits still apply.
- Compile the existing decision hinge and uncertainty into one private
  `decision_continuity` note, with chosen/suppressed text and its turn. Each
  text field is bounded to 240 characters. It records a decision, not success.
- Give a character its own earlier feelings and decision during repeated
  exchanges in one beat, clearly marked as a proposal awaiting resolution.
  Other minds' private state and discarded reroll results are excluded.
- Let empty concerns and null undercurrents clear prior state. Preserve those
  operations through later legacy replies that omit the fields.
- Retain the latest accepted intention transition's reason and up to three
  evidence references. Rejected or barren changes do not overwrite it.
- Add explicit belief revision by `target_belief`, with replacement wording
  and resulting confidence. Reject unknown/ambiguous targets and collisions.
  Preserve the origin of an authored belief so its old wording does not seed
  itself again or reappear as an independent card claim.
- Keep low-salience indirect communication in the character's own memory,
  using the same existing decision-framed wording as other own conduct.
- Clarify both language packs: continuing emotion, held belief versus
  possibility, actual memory paths, private continuity and speech-budget
  precedence. Remove duplicate rules and the redundant mood/baseline output
  fields. Correct the active-hypotheses gate to its actual payload location.
- Require complete, cited belief updates in the current kernel and bound
  want/hinge/uncertainty text to 240 characters. These guards were added after
  the live diagnostics below exposed silent learning loss and runaway output.
  Legacy decoding remains permissive. Broken current output uses the existing
  repair path; no additional stage is introduced.

## Deterministic verification

New tests cover actual compilation, schema validation, memory commit and a
subsequent `character_step` payload; they do not stop at prompt strings.
Cases include deliberate restraint, clearing versus omission, memory-bound
intention evidence, low-salience indirect speech, private-state isolation,
authored-belief revision, and rerunning multi-round exchanges.

The final narrow integration cohort passed all 33 tests. After tightening the
live contract, the kernel, belief, prompt and continuity cohort passed all 131
tests. An additional 2,000 randomized normalization cases checked selected
choice preservation, deduplication, capacity, situational limits and input
immutability.

Full suite: **15,634 passed, 30 failed, 3 skipped**. All 29 failures recorded
before this character work remain. The additional failure is the existing
`test_frames_cache_separately_and_ambient_follows_the_pipeline` order issue:
prefilling the two-entry registry cache reproduces its object-identity failure,
while the same test passes alone. It does not change registry data or involve
the new character paths. No character regression remains in the full run.

The English prompt is 17,851 characters on the latency test payload, below its
unchanged 18,000-character limit. The kernel grammar is 6,363 characters; its
ceiling increased from 6,000 to 6,500 specifically to retain the new required
learning fields and length bounds. Code map and UI catalog were regenerated.
The catalog and language-pack follow-up, including the registry-cache test
file in isolation, passed all 81 tests. New validation messages have matching
English and Japanese catalog entries.
Final project structure checks and whitespace checks passed. The existing
Japanese protocol-parity deferral remains unchanged.

## Live diagnostics

Eight synthetic calls used OpenRouter, with no quality retries within a phase.
No played story content was sent or changed. Reported total cost: **$0.1093**.
The original four calls used `z-ai/glm-5.2`:

- Private-promise and provisional-intent continuity worked.
- A resolved-key response ran into the completion limit while repeating text
  inside a want.
- A stair response said the old belief was wrong, but omitted target,
  confidence and evidence from its learning row. That response passed the old
  schema and could not update the stored conviction.

Those failures prompted the strict learning contract and short-field bounds.
The same two payloads were then tested under the final contract:

| Model | Missing-key concern | Belief revision |
| --- | --- | --- |
| `google/gemma-4-31b-it` | Completed; concerns empty, undercurrent null | Replaced the safe-stair belief with unsafe, confidence 0.95 |
| `z-ai/glm-5.2` | Completed; missing-key concern cleared, mild newly worded unease retained | Replaced the safe-stair belief with not-safe, confidence 0.95 |

Gemma was the configured model after the session resumed. Its results were
retained as an additional model check; GLM was explicitly selected afterward
for the original-model comparison. All four follow-up responses validated.
Both belief updates were also passed through the engine's pure belief updater,
which replaced the original record rather than retaining two conflicting
claims. These are small diagnostic samples, not an estimated success rate.

Exact synthetic request/response artifacts and dry-apply results are in
`output/character-continuity-2026-09-16/`, with separate `after-contract` and
`after-contract-glm` directories. The original report is retained to document
the failures before tightening.

## Limits

These repairs preserve the model's declared choices and brief reasons; they
cannot guarantee that a model makes good choices or consistently notices
every opportunity for learning. The latest private choice is one bounded
record. Longer experience continues through the existing memory and belief
systems. Settled affect and world outcomes retain their existing owners.
