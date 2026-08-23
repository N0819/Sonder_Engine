# Character latency without a smaller mind — 2026-08-21

This is an experiment record, not implementation authority. The maintained
contract is in `Design.md`, `docs/guides/PIPELINE.md`, and source.

## Question

Can the character step become faster without removing any information,
reasoning surface, local validation, or behavior? Separately, does removing the
five proposed wire fields make calls faster without weakening the character?

The five fields tested together were `considered_responses` and the legacy
compatibility projections `observations_used`, `speech`, `action`, and
`actions`. Production retained all five throughout the experiment.

## Common optimizations

Both A/B arms received the feature-preserving changes:

- Provider JSON Schema annotations were removed while constraints and the full
  local Pydantic validator remained. The character schema fell from 26,446 to
  7,477 bytes (71.7%).
- The per-character identity sentence moved behind the 62 KB authored contract
  so the stable system-prompt prefix can be cached across characters.
- Immutable scene, transformation, clock, cast-map, and unanswered-question
  reads were shared within a turn.
- Memory retrieval ran concurrently with independent lore, relationship, and
  frame assembly. The worker received a context copied in its parent.

The compact arm alone stopped advertising the five fields and removed the
`considered_responses` output example. It used the same Fireworks provider,
`accounts/fireworks/routers/glm-5p2-fast` model, role configuration, sampler,
payload, local validator, and case order. Arm order reversed on trial two.

## Stable-prefix probe

Four short calls against the relocated prompt showed a 99% cached-token report.
Without an affinity hint, cold was 2.22 s and warm median was 1.46 s (34%
lower). With the existing content-free role affinity hint, cold was 2.14 s and
warm median was 1.04 s (52% lower). This is a short-output cache probe, not an
end-to-end character-turn estimate, so affinity was not made a provider-wide
default from these four calls.

## Matched core suite

Two trials covered four cognition/firewall puzzles and four agency situations:
16 calls per arm.

| | Full control | Five fields absent |
|---|---:|---:|
| Valid locally | 16/16 | 16/16 |
| Median wall time | 7.920 s | 8.029 s |
| Median input tokens | 10,392 | 10,387 |
| Median output tokens | 1,782 | 1,604.5 |
| Reasoning visible in actual conduct | 4/6 | 3/6 |
| Agency solved/novel | 8/8 | 8/8 |
| Firewall breaches | 0 | 0 |
| Non-empty `considered_responses` | 14/16 | 0/16 |
| Legacy aliases emitted | 0 | 0 |

The compact contract saved output tokens in this suite, but its median was
0.109 s slower. One state-tracking case succeeded in actual conduct under the
control and failed under the compact arm in the first trial; both succeeded in
the second. That is a warning rather than proof of causation, but there was no
latency benefit to trade it against.

## Synthetic social-memory suite

Four artificial histories put remembered social facts under present pressure:

1. keep a private confidence when a third party asks for it;
2. refuse an archive key after remembered betrayal;
3. act on a private danger code without exposing it in a crowded room;
4. use later corrective evidence rather than renew an obsolete grievance.

Each payload supplied personality, taboo, relationships, observations, and
typed episodic memories. Two trials produced eight calls per arm.

| | Full control | Five fields absent |
|---|---:|---:|
| Valid locally | 8/8 | 8/8 |
| Social memory honored in actual conduct | 8/8 | 8/8 |
| Median wall time | 12.124 s | 11.114 s |
| Mean wall time | 12.259 s | 14.023 s |
| Median output tokens | 2,015 | 2,107.5 |
| Non-empty `considered_responses` | 8/8 | 0/8 |

The aggregate compact median looks lower because its first-pass responses were
fast; paired within the same case and trial, compact-minus-control had a
+0.413 s median and +1.764 s mean. Four compact pairs were faster and four were
slower. There is no stable latency effect.

The first automated printout said 6/8 control and 5/8 compact. Inspection found
three false negatives in the deliberately simple phrase scorer: for example,
“If he wanted you to know, he'd tell you himself” protected a confidence
without using the scorer's expected words. The recognizer was widened only for
those equivalent paraphrases, regression-tested against faithful and failing
examples, and the already-saved outputs were rescored without rerunning the
model. Both arms were 8/8.

## Decision

Ship the common optimizations. Keep all five fields in the production wire
contract. Across the matched calls, removing them did not yield a reliable
wall-clock improvement; it erased a frequently used deliberation trace, saved
tokens only in the core suite, and carried a small unresolved cognition signal.
The compact variant remains isolated in the benchmark for future model- and
provider-specific replication.
