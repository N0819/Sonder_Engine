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

**Status (2026-07-24): all six implemented.** F1–F4 as narrator payload fields
plus deterministic `_check_*` backstops in `agents/common.py` wired through
`agents/narration.py`'s enforceable-warning rewrite loop
(`tests/test_narrator_world_fidelity.py`); F5 as the `world_pressures` world-KV
ledger owned by `commit_world_pressure` with a director-side must-tick retry
(`tests/test_world_pressure.py`); F6 as `affect.ground_tells` + the
`tell_grounds` cstate ledger (`tests/test_tell_grounds.py`). Per-item notes
appended below each spec.

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
**Done.** `_ordered_beat_events` (agents/narration.py) builds the numbered list
from step order + loop call sequences, view-filtered (a quote enters only if it
reached the player); EVENT ORDER prompt rule; `_check_event_order`
(agents/common.py) fires on a verbatim position inversion between located
quotes and buys one narrator rewrite via `_ENFORCEABLE_PREFIXES`. Placement
note: the deterministic check runs at the narrator stage's own rewrite loop
rather than literally inside commit — same determinism, and re-rendering
narration there is the engine's existing correction seam.

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
**Done.** `_position_delta_payload` (agents/narration.py) supplies
`co_present_positions` (prev_room -> room + moved flag, committed KV vs
outcome scene); POSITION CONTINUITY prompt rule; `_check_position_fidelity`
flags an unmoved character narrated with a placement preposition at another
known room (look-verbs and quoted speech exempt) -> one rewrite.

## F3 — A shut portal reads as open in a later beat  *(major, simulation/state)*
**Symptom.** DW t9 "pulls the double doors shut... the street is gone"; t12 "through
the open doors, the streetlights flicker". Nobody reopened them.
**Fix.** Door/portal state as first-class `world.scene` entity state (the DW-1 fix
touches this area). Narrator payload states `portals: {front_doors: shut}`;
deterministic rule: named portal state in prose must match the scene blob.
**Test.** Doors committed shut at N; at N+1 with no open event, narration saying
"open doors" -> warning.
**Done.** Portal state was already first-class in the scene blob
(entity `state.link` phase, `state.transit.hatch`, door adjacency barriers);
`_visible_portal_states` (agents/narration.py) projects all of them into
`portal_states` for the player's room, adding a generic `doors` entry only
when every visible door-state agrees (so DW t12's bare "the open doors" is
checkable); PORTAL STATE prompt rule; `_check_portal_fidelity` -> one rewrite.

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
**Done.** Quotes bind to speakers in `event_order` (each entry carries the
speaker's DISPLAY — the canonical name when the player recognizes them via the
shared `_recognizes` rule, else the same appearance-derived anonymous label
perception injects, so the binding never out-leaks the view).
`_check_quote_attribution`: trailing attribution naming the true speaker
clears; a positively-nearest DIFFERENT speaker's reference fires; a
mismatched-gender pronoun in between declines to call -> one rewrite.
**Investigation ("unfamiliar woman" regress).** The label is not producible by
the deterministic scrub (whose fallback is "the unfamiliar person" and whose
appearance-derived labels never contain "unfamiliar") — it is the perception
LLM's own coinage for a speaker absent from the player's `known` set, i.e. the
anonymization itself was CORRECT per the info barrier given the stored known
map; what is wrong is that the known map was never seeded for crew who
in-fiction obviously know each other. That is the still-open promotion/attach
seeding half of backlog P7 (the V3 `_recognizes` fix covers only rank/title
variants of names already known, and by design cannot admit a bare role-noun).
The harm path — a tracked mind's line landing under the anonymous body — is
now closed deterministically by the attribution check regardless of seeding.

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
**Done.** World-KV `world_pressures` ledger owned by
`commit.commit_world_pressure` (new commit domain): open/tick/hold/resolve ops
on `DirectorResolve.world_pressure` (+ `DirectorEstablish.world_pressure`
openers for authored scenario processes); silence about an open entry is
recorded as an implicit hold AND warned; `world_pressure_view` feeds the
resolve payload with a deterministic `must_tick_this_beat` flag
(held >= `WORLD_PRESSURE_STALL_AGE` beats), which agents/director.py enforces
with one bounded correction retry. "Required field" is realized as the
deterministic silence-accounting rather than schema-required (a required
pydantic field would only fail validation, not create the tick).

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
**Done.** Manifest tells carry `because` (character prompt + JSON contract);
`affect.ground_tells` is the deterministic floor at the character stage
(derives a missing ground from the tell's own `betrays` pointer — suppressed
want text / undercurrent label — and warns only when nothing is derivable);
commit persists `{cue, because, turn}` onto the capped `tell_grounds` cstate
ledger and character_step feeds it back as `self.tell_grounds` with a TELL
PAYOFF prompt block. Observers still receive only the cue.
