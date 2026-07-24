# Fable review — remaining follow-ups

The alpha3.3-era adversarial review (three demo runs: impostor crucible, Doctor
Who paradox, Enterprise v3) is largely implemented. Fixed in commits
`c3b058f`, `1622df2`, and this one:

- **A1 (double-render half)** — `_cap_repeated_quotes` caps a spoken line's prose
  occurrences at its source count (backlog P3). Ordering half: still open (below).
- **A2** — empty-quote debris collapse; "don't grade the player's rhetoric" rule.
- **A4** — `_overused_phrases` ban list + prompt rule (the tic lexicon).
- **A3 / B1** — "AUTHORITY STOPS AT OTHER MINDS" (director_interpret): player
  claims about NPC past words/actions are claims not canon; player-narrated NPC
  actions route to the NPC; outcomes vs another body/hazard stay contestable.
- **B4** — "PERCEPTION IS NOT MEMORY" (narrator): new detail is discovery, never
  foreknowledge contradicting the player's own stated uncertainty.
- **B8** — "NO ORIGINATED PLAYER CONDUCT" (narrator).
- **B9** — "NEVER SUMMARISE A SPOKEN LINE" (narrator).
- **B7** — investigated, FALSE ALARM (background speech merges at commit and
  reaches every view + memory; the critic saw only the pre-merge dialogue_log).

The items below are real but touch delicate seams (perception attribution, a new
world process, the scene-commit position/portal writers) and are specified here
rather than rushed. Each is written to be resumable cold.

---

## F1 — A1 ordering half: stimulus renders after the response it provokes  *(major, craft)*
**Symptom.** At climaxes the narrator renders a response before its stimulus, or
re-tells the player's turn-8 speech after the beats it caused (impostor t6 answer-
before-question; Enterprise t4 lockout-before-order). The double-render half is
fixed; the ORDERING half is not.
**Fix.** Pass the narrator an explicit numbered event list built from step order +
the interaction-loop call sequence (`stimulus -> response` pairs), with a prompt
rule to render in list order. Deterministic backstop in commit: for each quoted
NPC line, its position in the prose must not precede the rendered position of the
event `flow` says it answers. Re-render narration only (cheap) on violation.
**Test.** A beat where an NPC line answers the player's line; assert the player's
line's prose position precedes the NPC line's.

## F2 — Cast character position reverts without a movement event  *(major, simulation)*
**Symptom.** DW t6 ends with the Doctor mid-road ("a dead sprint... closing the
distance"); t7 renders him back in the TARDIS doorway with no return narrated.
Same family as DW-4 but for a cast character's position, not an auto-created one.
**Fix.** The narrator payload should carry each co-present entity's position
DELTA this beat (prev_room -> room). A deterministic check: a character rendered
at a room this beat that differs from last beat's committed position, with no
movement event in this beat's diff, is a warning -> re-render. The DW-1 relocation
work already sits in this neighborhood.
**Test.** Character committed in room A last beat, no movement diff this beat,
narration places them in room B -> warning fires.

## F3 — A shut portal reads as open in a later beat  *(major, simulation/state)*
**Symptom.** DW t9 "pulls the double doors shut... the street is gone"; t12 "through
the open doors, the streetlights flicker". Nobody reopened them.
**Fix.** Door/portal state as first-class `world.scene` entity state (the DW-1 fix
touches this area). Narrator payload states `portals: {front_doors: shut}`;
deterministic rule: named portal state in prose must match the scene blob.
**Test.** Doors committed shut at N; at N+1 with no open event, narration saying
"open doors" -> warning.

## F4 — A tracked mind's line renders under an anonymous body  *(major, simulation/attribution)*
**Symptom.** Enterprise t4: Vorne's second line (per `spoke` metadata) renders
immediately after "The unfamiliar woman pulls her hands back...", so by prose
convention an anonymous woman speaks a tracked character's line. Two defects: an
unlogged anonymization ("the unfamiliar woman"), and a dialogue-adjacency
collision reassigning a tracked mind's speech.
**Fix.** Bind quotes to speaker ids in the narrator payload (the dialogue_log
already has speakers). Commit-side check: each quoted line's nearest preceding
actor reference must resolve to the speaker `spoke`/dialogue_log expects; re-render
on mismatch. Separately investigate the "unfamiliar woman" recognition regress
(the V3 rank-variant fix would not catch a bare role-noun with no name).
**Test.** A dialogue_log line by character X placed after a reference to Y in the
draft -> attribution warning.

## F5 — The world never acts: a scenario object stays inert across a whole run  *(major, craft; minor simulation)*
**Symptom.** Enterprise: an active scan of an unknown alien Array produces zero
world response across 12 beats; every joule of tension is interpersonal. The
environmental cousin of DW-2 — the Director resolves character causality but runs
no off-character world process, so nothing external ever forces a decision.
**Fix.** A `world_pressure` field the Director owns: a scenario object with an
authored threat/escalation note must be TICKED or explicitly HELD each
director_resolve (a required field, so silence is a choice). The DW-2 "significance
floor" pointed at ongoing processes rather than one-shot events.
**Test.** A scenario with an escalation note; assert director_resolve emits a
world_pressure tick/hold each beat.

## F6 — A planted tell has no stored referent  *(nit, craft)*
**Symptom.** Impostor t2: Beaumont notes Sir Julian's right hand on the glass held
"a half-second longer than a servant's glance should" — but no ground for the
suspicion (handedness? habit?) ever surfaces; in a mystery, readers bank every
such detail.
**Fix.** When a perception/appraisal output flags an anomaly, store its ground (a
`because` field). The narrator may render the tell without the ground, but the
ground must exist so a later beat can pay it off — untethered tells are how a
generator fakes significance.
**Test.** An appraisal-flagged anomaly carries a non-empty `because`.
