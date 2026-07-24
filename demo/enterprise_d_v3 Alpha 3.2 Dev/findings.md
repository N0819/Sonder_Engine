# Enterprise-D v3 (alpha3.2-dev) — findings

Live-run findings against `alpha3.2.3`. Turn numbers refer to `run.db` / the
`run_log.jsonl` beside this file.

---

## V1 — A character invited to speak, in-fiction, is never given the call

**Severity: high.** Plausibly upstream of the v2 audit's W1 ("the rupture never
lands"), which was previously diagnosed as a strain-accrual bug.

**Symptom.** Across turns 1–8, Dr. Vorne (id 27) is the subject of the episode
and is listed in `flow.reactors` on **every** turn. His character agent actually
ran on only turns 1, 2 and 5. On turns 7 and 8 — the two beats aimed squarely at
his drive — he did not run at all, and the narrator rendered his silence as
characterful refusal:

> Vorne's hands, twitching at his sides a moment ago, go still. He meets my gaze.
> His jaw is tight. **He does not speak.**

No agent ever chose that silence. The prose is describing a decision that was
never simulated.

**Turn 8, step by step.**

| Signal | Value |
|---|---|
| `flow.reactors` | `[26, 27, 28, 29, 30, 31]` (all cast) |
| `flow.tom_triggers` | `[27]` — the engine flagged Vorne as the mind to model |
| `flow.addressed_to` | `[]` — **empty** |
| `max_character_calls` | 6 (not binding) |
| `interaction_loop.calls` | 1 |
| rounds actually run | `[26]` (Picard) |
| `stop_reason` | `"awaiting player response"` |

Two independent causes compound:

**(a) The addressee was not resolved.** The player's vocative was *"Doctor."*
rather than *"Vorne"*. Address by name resolves reliably (turn 5 → `[27]`, turns
6–7 *"Mr. Data"* → `[29]`); address by title did not. This is partly defensible —
there are **two** doctors on the bridge (Dr. Vorne and Dr. Beverly Crusher), so a
bare *"Doctor"* is literally ambiguous and the ADDRESSEE PRIORITY rule
(`prompts.py`) does say to leave the field empty when address is ambiguous.
But the same rule also licenses *"unambiguous surrounding context"*, and the
entire preceding exchange is with Vorne — including the player naming him in the
same breath as *"thirty years"*, his own stated tenure. The context was available
and unused.

With `addressed_to` empty there is no priority sort, so `initial_reactors` stays
in cast-registration order and Picard (26) is called first.

**(b) The loop yielded while the invited character was still unheard.** Picard's
generated line explicitly hands the floor to Vorne:

> "Doctor, I would hear your answer as well. If there is knowledge you have set
> aside, now is the time to share it."

The loop then stopped with `stop_reason: "awaiting player response"` after a
single call, with 5 of 6 permitted calls unused. An in-fiction invitation to
speak, issued *by another character in the same beat*, did not earn the invited
character a call.

**Why it matters beyond one beat.** Drive strain accrues from appraisal
`goal_impacts` — which only exist if the character agent runs. Vorne's interior
after 8 turns:

```
drive_strain : 0.0
drive_rupture: None
mood         : None
recent_tells : ['hands clasped tightly behind back',
                'posture straightens slightly, shoulders squaring',
                'slow, deliberate breath before speaking']
```

The tells are accumulating (written by beats where he *did* run) while strain is
pinned at zero, because the beats that would wound the drive are precisely the
ones where he isn't simulated. alpha3.1/3.2 fixed the strain **arithmetic**
(`4f562c7`); this is the layer above it — correct arithmetic over an input that
never arrives. A rupture cannot build no matter how well the math works.

**Suggested fix.** Two separable changes:

1. Give a `tom_triggers` character a call before the loop yields to the player.
   That set is the engine's own statement of "this is the mind that matters this
   beat"; ending the beat without simulating it wastes the signal. Cheap version:
   when `stop_reason` would be `awaiting player response` and a `tom_triggers`
   character has not yet been called and calls remain, call them first.
2. Resolve title/role vocatives against the cast when context disambiguates —
   and, when it genuinely doesn't (two doctors), prefer the character already in
   dialogue with the player over registration order.

**Test hint.** Feed a beat whose speech targets a character by title only, with
that character in `tom_triggers` and another cast member earlier in registration
order; assert the targeted character receives a call.

---

## Note on run methodology

The player turns for 1–5 are replayed verbatim from the destroyed 2026-07-23 run
(see `README.md`) so the opening reproduces it; turns 6+ are authored fresh.
Turn 4 and one turn 6 attempt were killed mid-pipeline by harness timeouts and
removed via the engine's own delete path (checkpoint restored inside the delete
transaction) before being re-run — so no partial beat survives in `run.db`.
