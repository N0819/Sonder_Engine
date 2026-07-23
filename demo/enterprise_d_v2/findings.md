# Enterprise-D: The Kelvan Array (v2) — Audit Findings & Fix Plan

A fresh **40-turn** Sonder-Engine episode (deepseek-v4; director/character on
`pro-cheaper`, perception/narrator on `flash:thinking`), a re-run of the prior
`demo/enterprise_d/` Star Trek scenario to regression-test the fixes that shipped
since (obligation ledger, autonomous promotion, action-first narration, the
perception name-scrub) and to hunt new flaws. **41/41 turns committed, 0 pipeline
errors.** Fable narrative grade: **C+** (up from the prior **D+**).

Artifacts in this directory:
- `transcript.md` — full story, each beat tagged `(activated: …)` from real pipeline evidence.
- `coverage.md` — feature matrix, **FIRED 26 / MISS 8** of 34 checks.
- `audit_data.json` — the machine-readable per-turn capture (input, prose, step digests, per-turn world + interior snapshots).
- `Enterprise_D_Kelvan_Array.chat.json` — the real, portable, importable export (`version 3`, `resources` bundle). **Round-trip verified: 41/41 turns, 6 cast, 349 memories, scene reconstructed — `ok: true`.**
- `roundtrip.json` — the export→import verification result.

Provenance tags: **[telemetry]** = confirmed by captured per-turn engine state · **[fable]** = the narrative critic's page-level finding · **[verified]** = confirmed by hand against the audit data + source.

---

## Part 0 — What got FIXED since the D+ run (regressions cleared)

The prior run's two CRITICALs and its fact-adjudication gap visibly shipped and
work. This is the good news, and it's what moved the grade 2.5 steps.

- **Autonomous background→cast promotion** *(prior W4, was CRITICAL)* — **FIXED [telemetry].** Geordi (t10), Data (t11), Troi (t14), Crusher (t16) promoted to full characters with no human in the loop. Last run Data stayed "promotable" 26 turns and was never promoted; the crew are people now.
- **Obligation ledger discharges** *(prior W1, was CRITICAL)* — **FIXED [telemetry].** Obligations opened and cleared (3 open at t24 → 0 by t26). Last run demands were re-deferred forever. (New, smaller timing issue: **W8** below.)
- **Player-fact adjudication** *(prior W2, was CRITICAL)* — **WORKING [fable].** At t23 the player asserts "Vorne's changed his mind"; the Director makes Picard *contest* it — "What change of mind, Commander? And what, specifically, is Dr. Vorne offering to do?" — instead of passing the claim through unchallenged.
- **Action-first narration** *(recent fix)* — **WORKING [verified].** The narrator anchors the player's action lightly and spends prose on consequence; no more "You <verb>…" re-narration opening every beat.
- **Export / import portability** *(the user's flagged concern)* — **VERIFIED OK [telemetry].** The full 40-turn chat exports and re-imports cleanly into a fresh DB (turns/cast/memories/scene all reconstructed). Did **not** reproduce as broken on either the smoke or full run.

---

## Part 1 — Systemic engine weaknesses (highest value first)

### W1. The drive rupture opens, is held open for 23 turns, and never *lands* — the transformation is entirely model-gated with no floor  *(CRITICAL)*
**Symptom [telemetry+fable].** Vorne's `drive_strain` accrued organically (first at
t9, 1.0 at t19–21) and his **rupture window opened at t18 and stayed open through
t40 — 23 turns** — yet `former_drives` never populated: the core drive **never
shifted.** On the page [fable], the *collapse* is beautifully dramatized (t18 "his
voice catching… 'We became the signal'"; t21 "'I want… for it to have been worth
something.' The word 'worth' hangs, then fractures into silence") — but every
post-collapse identity beat is authored from *outside* the character, and his last
substantive line (t39, "I feared they'd find a reason to see only the danger — not
the message") is functionally his **turn-2 credo restated.** The engine detected a
soul should break, held the door open for 23 turns, and the character stood in the
doorway describing the weather. What shipped is *collapse and reversion*, not
collapse and rebirth.

**Root cause [verified].** The shift is applied **only** if the character model
emits a `drive_shift` field: `commit.py:2897` (`elif own_result.get("drive_shift")`).
deepseek declined every beat — and the prompt (`agents/character.py:225–243`) even
*licenses* the refusal ("do not shift for a survivable wound", "You need not change
what you live for"). Worse, the window **re-extends indefinitely** while strain ≥
`RUPTURE_STRAIN_MIN` (`commit.py:2923–2934`) with **no escalation**, so the intended
"denial is a phase, not an exit" degrades into a *permanent stable limbo* — strain
pinned ~0.8, window forever open, resolving into neither transformation nor
recovery. All the prior W6 prompt fixes (worked example, "this event has ALREADY
changed you", crisis-escalation block) are present and were **insufficient**: the
beat has no deterministic floor. It is the *exact* disease the obligation ledger
cured for plot beats (open something, never forced to discharge) — the drive system
never got the same medicine.

**Fix.** Give the engine the authority *and the obligation* to resolve what it opens:
1. **Forced adjudication after a sustained window** [fable-F1a]. After the window
   is open N turns (≈4) with strain ≥ threshold *and* a qualifying trigger has
   fired (t21's absolution, t22's cooperation both qualified), stop appending an
   optional "you MAY" block. Run a dedicated one-call micro-stage: *"Is your core
   drive still ⟨drive⟩? Answer `reaffirmed | cracked | replaced`. If `replaced`,
   state the new drive in one sentence and name the moment it broke."* Make silence
   an invalid output — the current failure (model never touches the tail field)
   becomes impossible.
2. **Behavioral-contradiction detection at commit** [fable-F1b]. The page already
   held shift-consistent *acts* (offering to end the Array t22, surrendering the
   badge t36). Add a commit-side check comparing committed actions over the last K
   turns against the stated drive; a sustained contradiction forces the adjudication
   in (1). The evidence was on the page; the ledger never read it.
3. **A committed shift must mandate a page-visible articulation** [fable-F1c]. When
   a shift lands, inject a one-turn requirement: the character states, in their own
   words, what they no longer believe — "the rupture is not real until the character
   says something their turn-2 self could not have said."
4. **Cap the re-extension** (`commit.py:2931`): after M re-opens, force a resolution
   (shift via the detected `direction`, or decay-with-scar) so no character can sit
   in permanent crisis limbo.

### W2. Player-authored NPC volitional acts bypass the character agent entirely  *(HIGH)*
**Symptom [verified+fable].** The two most dramatic things Vorne *does* were written
by the **player**, not originated by his mind: the lunge to purge the log (t33, "Vorne
lunges for the lounge console… I catch his wrist") and the surrender of his
thirty-year commbadge (t36, "Vorne unpins the Kelvan-studies commbadge"). The engine's
entire response to the arc's central gesture was "a clink and a nod" — Vorne says
nothing — because the act arrived at commit with **no character contribution
attached** and the narrator had nothing to render.

**Root cause [verified].** `director_interpret` captures a player-declared act on an
NPC as an objective event but does not route it to that NPC's character agent for
interiority/dialogue; the character system only ever runs on the NPC's *own*
declarations. So the most character-defining beats had zero character-agent input.

**Fix [fable-F2].** (a) Classify a player-declared *volitional NPC act* as contested
and hand it to the character agent to **adopt or refuse** — adoption means the agent
supplies interiority + dialogue for its own act. (b) Give a character in an open
rupture window an **initiative budget** via the existing `standing_intentions`
machinery (elevated priority while the window is open) so the most dramatic beats
*originate* inside the character whose drama it is, rather than being puppeteered.

### W3. Second-act continuity amnesia — characters forget facts the episode already established  *(HIGH)*
**Symptom [fable].** t26: Geordi says the Array signal is "structured, almost like a
language. I can't translate it" — **the log was translated nine turns earlier** (t17).
Troi senses "desperation… fear" (t26) one turn after "relief… acceptance" (t25). The
episode forgets its own second act.

**Root cause.** Settled plot facts live only in per-character memory (retrieval-gated
and lossy); there is no always-included ledger of on-page-established truths, so a
retrieval miss lets a character contradict a fact the whole room witnessed.

**Fix [fable-F4].** A world-level `established_facts` ledger: when a major fact lands
on-page (log translated t17, Array powering down t24–25), commit it and inject it into
every co-present character payload. Characters may *dispute* a settled fact; they may
not *forget* it. Cheap, always-included, closes the amnesia.

---

## Part 2 — Narration integrity (mechanical)

### W4. Verbatim within-turn duplication — on the two heaviest turns  *(HIGH, mechanical)*
**Symptom [fable].** t18 replays "…We became the signal" three times, stepping on the
episode's best moment; t34 delivers Crusher's full casualty report **twice** and
renders Vorne's hand-on-thigh and Geordi's nod each twice; t13 has Geordi and Data
both restate "targeting our primary power conduits." **Root cause.** Interaction-loop
emissions and the narrator both render the same declared line/gesture, stitched.
**Fix [fable-F3].** Deterministic near-duplicate hash of dialogue/gesture events at
perception-payload assembly + a narrator craft rule: a quoted line appears at most
once per turn. Code, not prompt.

### W5. Player-supplied dialogue is paraphrased away  *(MEDIUM, integrity)*
**Symptom [fable].** t40 "I… tell him what he needs to hear" and t29 "I tell him
what he's done matters" **summarize the player's own supplied climactic lines**
instead of rendering them. **Root cause.** The dialogue-fidelity floor protects NPC
quotes but not the player's. **Fix [fable-F6].** If the player supplied quoted
speech, render it as speech, never summary; extend the existing NPC-dialogue
correction-retry to player lines.

### W6. Pronoun pin missing from character-agent generation (not just narration)  *(MEDIUM, mechanical)*
**Symptom [fable].** Vorne (male) is "her" at t0, t4, t9 — and, tellingly, inside
**Crusher's dialogue** at t15 ("her discovery may save thousands"). The flip is
inside a *character agent's* mouth, so the pin is missing from generation, not only
narration. **Fix [fable-F7].** Carry explicit `pronouns` into the character +
perception + narrator payloads and the opening-establish path; a mismatch is a
correction-retry.

### W7. Ambient anti-repetition ineffective  *(LOW-MEDIUM)*
**Symptom [fable].** "The bridge hums" in ~14 turns; the turbolift doors are
re-announced open at t0/5/8/20/23; Vorne's body has three settings (restless hands,
tight jaw, white knuckles) cycled all episode. The recent-tell ledger (prior W7)
is either unimplemented for ambient scenery or ineffective. **Fix.** Cap ambient
re-description to first-establishment + change; extend the recent-cue dedupe to
narrator set-dressing, not just character tells.

### W8. Promotion identity-binding lost on the page  *(LOW-MEDIUM, mechanical)*
**Symptom [fable].** t11 — the turn Data promotes — renders "The unfamiliar person
stands near him, silent" for a character the player has addressed by name for turns.
**Root cause.** The promotion's name/known-identity record isn't committed before
perception assembly on the promoting turn. **Fix [fable-F7].** Commit the
promotion's identity/known record before perception; narrator rule against unnamed
references to already-met characters.

---

## Part 3 — World / perception & resolution

### W9. A clear two-party physical struggle is classified uncontested  *(MEDIUM)*
**Symptom [telemetry].** t33 — the player grabs Vorne's wrist and wrenches it off the
console he's trying to purge — was resolved by `director_interpret` as
`resolution_flags.contested = False`, with **no reaction_loop and no dice.** An
opposed physical act between two present agents ran through as if uncontested.
**Root cause.** The interpret seam under-classifies player-vs-NPC physical opposition
as non-contested. **Fix.** Treat a player physical act *targeting* a present,
volitional NPC (especially one with an active counter-goal, e.g. Vorne mid-purge) as
contestable → route to `reaction_loop` so the struggle is actually adjudicated.

### W10. Scene truth violated: closed-room audio/occupancy leaks across walls  *(MEDIUM, info-integrity)*
**Symptom [fable].** t31 closes the observation-lounge door; t32 reopens it silently;
t33 has Geordi and Data speaking *into* the lounge from the bridge and Picard
effectively teleported inside. In an engine whose premise is the information barrier,
a wall that doesn't gate perception is a core-value failure, not cosmetics.
**Root cause.** The perception payload isn't strictly filtered to in-room (or
through-open-door) entities; the whisper/proximity gating that exists for volume isn't
applied to walls/rooms. **Fix.** Build the perceiver's co-present set strictly from
`world.scene` room membership + open-door adjacency; extend proximity gating to room
boundaries. (`world.scene` is supposed to be the single source of truth — enforce it.)

### W11. Obligation discharge has no dramaturgical timing  *(MEDIUM)*
**Symptom [fable].** The ledger works (credit due) but has no sense of occasion: at
t40, in the middle of the intimate closing two-person beat, **Data walks in** —
"Commander, the report you requested is complete." The receipt discharges on the
worst possible beat. **Root cause.** `director_resolve` discharges a due obligation
by availability, not scene tone. **Fix [fable-F5].** A beat-tone check before
discharging a mechanical obligation — a report delivery can wait one turn when the
current beat is an intimate close. (The ledger traded the old sin, *never
delivering*, for a new one, *delivering at the worst moment*.)

---

## Part 4 — Fable's verdict (harsh critic)

> **C+** (up from D+ — a real, two-and-a-half-step improvement). "This run is not
> [a holding pattern]. It is an actual episode: the log gets read, the deaths get
> names, the Array actually dies, the crew actually speak… Turns 18–22 are the best
> sustained sequence this engine has produced — a real interrogation scene with real
> silence in it." Grade capped at C+ because "the episode's *central* event — Vorne's
> transformation — never happens on the page (and the telemetry confirms it never
> happened underneath either)," plus verbatim within-turn stutters on the two heaviest
> turns and a finale that paraphrases its own closing line while a report padd is
> handed over mid-embrace.
>
> **On the rupture:** "The break lands. The transformation does not… read t33 and t39
> together and the *old drive is still running*… What the fiction actually delivered
> is collapse and *reversion*, not collapse and rebirth… The door was open for 23
> turns and the character stood in the doorway describing the weather."
>
> **Bottom line:** "The engine can now detect that a soul should break, hold the door
> open, and even stage a beautiful collapse — but it cannot yet make a character walk
> through the door. Until the rupture is something the character *must answer for* in
> his own forced words (W1) and can *act on* with his own initiative (W2), every
> transformation will be what this one was: a number at 1.0, a player doing the
> character's living for him, and a man at turn 40 who is his turn-2 self with a bruise."

---

## Part 5 — Prioritized fix plan

1. **W1 — drive-rupture floor** *(CRITICAL)*: forced adjudication micro-stage after a
   sustained window + behavioral-contradiction trigger + mandated page-visible
   articulation + capped re-extension. The single highest-leverage fix; it is the
   drive-system analogue of the obligation-ledger cure that already worked here.
2. **W2 — player-authored NPC acts route through the character agent** + initiative
   budget in an open window. Fixes the "clink and a nod" and lets the biggest beats
   originate inside the character.
3. **W3 — `established_facts` ledger** (continuity) + **W4 within-turn dedupe** — two
   cheap, deterministic, high-visibility fixes; W4 is currently defacing the heaviest
   turns.
4. **W9 physical-contest classification** + **W10 room-wall perception gating** — the
   two world/info-integrity fixes; W10 matters most for an engine whose premise *is*
   the information barrier.
5. **W5 player-dialogue fidelity, W6 pronoun pin in character generation, W8 promotion
   identity-binding, W11 obligation timing** — mostly prompt-rule + correction-retry +
   commit-ordering; cheap.
6. **W7 ambient anti-repetition** — polish.

Cheapest high-impact first pass (no architecture): **W4, W5, W6, W8** (deterministic /
prompt-rule) and **W3** (small always-included ledger). The structural work that most
changes the fiction is **W1** and **W2** — make the engine both *able* and *obligated*
to resolve the interior ruptures it already knows it has opened.
