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
(`llm/prompts.py`) does say to leave the field empty when address is ambiguous.
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

**Status: FIXED** in `86fa6ab`, with regression tests in
`tests/test_interaction_focus_call.py`. Two changes: the interaction loop now
gives a flagged `tom_triggers` character a call before yielding to the player
(granted at most once per beat, so a focus character who also turns to the
player cannot hold the loop open), and the Director's ADDRESSEE PRIORITY rule
now covers role/title vocatives where context disambiguates.

**Evidence.** `v1_evidence_prefix_run.jsonl` is the 9-turn (0–8) log of the run
that exposed this, played against the *unfixed* engine. It is kept as the
before-picture: Vorne's agent ran on turns 1, 2 and 5 only, and his drive strain
never left 0.0. `run.db` / `run_log.jsonl` were then restarted from turn 0 on the
fixed engine, so the transcript is uniformly one engine version rather than
changing behaviour mid-episode. Turns 0–5 replay the same player inputs in both.

Two caveats on the diagnosis, recorded because they narrow the claim:

- `max_character_calls` is **6**, not 1. An early reading of the `.get(..., 1)`
  default suggested the budget was binding; it was not. The loop had 5 calls
  spare and stopped by choice, so the defect is the stop condition, not the
  budget.
- The empty `addressed_to` on turn 8 was **partly the player's fault**: the
  vocative was a bare *"Doctor."* with two doctors present (Vorne and Crusher),
  which the existing rule correctly treats as ambiguous. The prompt change
  targets only the narrower gap — that surrounding context was available and
  unused.

---

## Result: strain accrual confirmed; no rupture, and that is the correct outcome

**The mechanism works, in both directions.** Vorne's drive-strain across the run:

| Turn | Strain | What moved it |
|---|---:|---|
| 0–3 | 0.0 | scene-setting; no drive contact |
| 4 | 0.0375 | Vale reaching for his console — `serves=drive −0.25 @ 0.6` |
| 6 | 0.0741 | *"in thirty years, did you ever run the other search?"* |
| 7 | 0.1082 | pressed on his deflection |
| 8 | 0.107 | decay — no wound this beat |
| 9 | **0.0548** | the decode **vindicated** him — `serves=drive +0.20 @ 0.85` |
| 10 | **0.1604** | his taboo named; he confesses he was afraid to look |
| 11 | 0.0693 | he chooses evidence over fear, publicly credited |

That is the alpha3.2 accrual fix (`4f562c7`) confirmed live: strain rises on
genuine drive wounds, decays when nothing wounds, and **falls when the fiction
vindicates the drive**. The curve is not monotonic, by design.

**No rupture landed, and the run should not be read as a failure for it.** The
episode vindicated Vorne twice — the decoded message said the Array is "not a
weapon… we leave it to the first who hears us", and Data's grammar later
undercut the accusation against him. A character the fiction has just proved
right has nothing to break. The engine declining to stage a collapse here is
correct behaviour, not inability.

**This reframes the v2 audit's W1.** That finding read the engine as able to
"detect that a soul should break … but not make a character walk through the
door". The v3 evidence says the problem was upstream and simpler: the focus
character was not being *simulated* on the beats aimed at him (see V1), so
strain had nothing to accrue from and sat pinned at 0.0. With V1 closed, Vorne's
agent ran on **8 of 11** turns (vs 3 of 8 in the pre-fix prefix run) and the
strain curve above became possible.

**Authoring note, recorded because it distorted several turns.** Turns 6–10 were
played by an author steering toward a predetermined rupture. The engine declined
each time, on the evidence: at t9 it vindicated him rather than breaking him,
and at t10 **Picard and Data jointly refuted the player's own premise** — Data
re-examining his earlier translation to note that the Kelvan `vir'kel` denotes
inability, not action, so the text never says the builders died answering the
question. Nothing in the player input invited that. Turn 11 accordingly has Vale
concede the overreach on the record. A demo run is a poor instrument when the
player is trying to produce a result rather than play a character.

---

## V2 — Player-echo stripping leaves broken sentences  *(open, cosmetic)*

**Symptom.** t7: *"I turn back to face Vorne, and when I speak again it's
quieter, almost gentle: Vorne swallows once, then turns his head…"* — a dangling
colon where Vale's line was removed. The PLAYER ECHO RULE correctly strips the
player's own quoted speech (the UI already shows what they typed), but the
lead-in that introduced the quote is left behind, running straight into the next
sentence. t8 shows the related shape: an orphaned line lands after narration that
already describes the speaking.

**Fix.** `_strip_player_echo` (`agents/common.py`) now heals a dangling
attributive colon left when the quote it introduced is stripped: the lead-in
TEXT is kept and only the orphaned colon becomes a full stop, so nothing
legitimate is eaten and a real non-speech colon (list, ratio, time) is untouched.

**Status: FIXED** (`tests/test_echo_colon_heal.py`).

---

## V3 — A background presence still renders as "the unfamiliar person"  *(open)*

**Symptom.** t5 and t11: *"The unfamiliar person crosses his arms…"*, *"The
unfamiliar person nods once: 'I second that. Doctor, you've earned the right to
be heard first on this.'"* A presence articulate enough to second a captain's
ruling is still anonymized to the player.

**Root cause.** A background presence voiced as "Commander Riker"; the player
recognized "William T. Riker". Perception's identity scrub compared names by
exact string, so the rank variant missed the recognized set and was anonymized.

**Fix.** Recognition now allows a rank/title VARIANT of a known person
(`_recognizes` in `agents/perception.py`), kept deliberately tight to protect the
information barrier: a variant resolves only when every one of its significant
tokens is contained in a single known name. "Commander Riker" resolves against
"William T. Riker"; a true stranger ("Commander Sato") and a same-surname
stranger ("Thomas Riker") both stay anonymized.

**Status: FIXED** (`tests/test_name_variant_recognition.py`). This closes the
name-variant half of backlog P7; the promotion-turn seeding half remains open.

## Note on run methodology

The player turns for 1–5 are replayed verbatim from the destroyed 2026-07-23 run
(see `README.md`) so the opening reproduces it; turns 6+ are authored fresh.
Turn 4 and one turn 6 attempt were killed mid-pipeline by harness timeouts and
removed via the engine's own delete path (checkpoint restored inside the delete
transaction) before being re-run — so no partial beat survives in `run.db`.
