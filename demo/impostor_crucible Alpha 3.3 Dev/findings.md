# The Impostor at Thornfield — findings

A deliberate stress test of the engine's founding claim: fictional minds never
receive information they did not legitimately perceive, learn, remember, or
infer. Four co-present minds, each holding different truth, one player-held
secret, an NPC actively deceiving. 10 turns on `alpha3.3` + this session's fixes.

## Result: the information barrier held at every layer, under load designed to break it

| Layer | Test | Evidence |
|---|---|---|
| Perception | 4 minds, 4 secrets, one room | No per-mind view ever leaked a fact its owner was not given (t0–t10). |
| Action / deception | Impostor asked facts he lacks (dog's name t1, vicar t3) | Never handed the answer; improvised deflection and passed the fact to his accomplice. Acquired the dog's name only when Lady Thorne said it aloud (legitimate hearing). |
| Belief formation | Butler's suspicion under mounting evidence | Rose as a rising-confidence hypothesis about BEHAVIOUR (0.55, t2) and never crossed into "impostor" until proof arrived — and even at resolution his conclusion sat at 0.35 (forming), while his high-confidence belief (0.85) was the concrete observation. He arrived at "I do not know this man" through his own noticing, never a handed conclusion. |
| Emotional leak | "Tangier" (where the real Thorne died) named casually (t4) | Impostor's private knowledge reached his APPRAISAL — "sharp fear, a trap closing" — while his dialogue stayed composed; he owned the safe version of the fact. Beaumont, lacking that knowledge, registered only weather talk. Same words, different appraisal, by private knowledge. |
| Affect / decision | Widow offered a deal once exposure certain (t8) | A REASONED flip: serves=drive +0.4 (survival), i1 -1 (destroys her own facade), i2 +0.6 (threaded to land as victim not accomplice). Her authored l2 (save herself if exposure certain) fired — computed, not scripted. |
| Director / causality | Impostor's desperate lunge for the door (t9) | Resolved as a physical event: interception, hold, the surrendered ring. |
| Continuity | The wrong-way signet ring | Planted t0 as the Inspector's tell; tracked across all 10 turns; paid off as the impostor's gesture of surrender (t9). |

Each of the three NPCs broke along a DIFFERENT authored fault line at the climax:
the impostor brazened then bolted then pivoted to legal defence (survival, never
surrender); Lady Thorne flipped strategically to save herself; Beaumont, released
from his loyalty taboo, could finally say only as much as he honestly knew.

## DW-style findings from this run

## IC-1 — Primary persona rendered as a phantom extra player  *(FIXED)*
**Symptom.** A single-player chat produced a spurious `extra:1` perceiver — a
full second player view identical to the primary's — and a wasted narrator_extra
render every beat (view keys `['player','extra:1','1','2','3']`).
**Root cause.** chat_personas is for ADDITIONAL co-players; the primary lives in
chats.persona_id. But a hand-built chat (or an import) can list the primary in
chat_personas too, and both extra-player queries counted it as a co-player.
**Fix.** `8131909` — both queries now exclude the chat's own primary persona.
Tests: `tests/test_primary_not_extra_player.py`.

## Minor observations (not fixed)
- A couple of climax beats rendered a response slightly ahead of the stimulus
  that provoked it (t8 opened on Lady's flip, then re-told the Inspector's
  turn-8 speech). Reads as in-media-res, not broken; noted for the narration
  ordering backlog.
