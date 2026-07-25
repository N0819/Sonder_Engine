# Enterprise-D bridge scene-manager run — findings

7 turns (opening + 6), `zai-org/glm-latest` for every role. **Picard is the only
registered character.** The entire bridge crew was left to the Director to
invent. The player is Commander Sela Ndiaye, a Starfleet observation officer
expected to watch and record — deliberately near-silent for three of six turns,
which is the hardest case for the salience gate and the best case for the
manager. `scene_life = "full"`, `max_managed = 6`.

See `transcript.md` for the full run.

---

## 1. Did it generate the right crew?

Yes, from **station names alone**. Nothing in the seed named a single character
besides Picard; the scenario listed only *"first officer, operations, tactical,
conn, engineering, counselor"*.

| station in seed | Director produced |
|---|---|
| first officer | Commander William T. Riker |
| operations | Lieutenant Commander Data |
| tactical | Lieutenant Worf |
| engineering | Lt. Cmdr. Geordi La Forge |
| counselor | Lt. Cmdr. Deanna Troi |
| conn | Ensign (Conn Officer) — generic, correct for TNG's rotating conn |

Beverly Crusher was added unprompted (tracked, never on the bridge).

The canon licence worked exactly as §3.8.1 specifies: **authorial and opt-in**,
carried in the style guide (`genre: "Star Trek: The Next Generation"` plus
`director_notes` naming the ship and instructing use of the established senior
staff). Nothing inferred it; the standing no-outside-canon rule would otherwise
have applied.

## 2. Blurbs

Minted in one batched call, frozen thereafter, and strikingly well observed:

- **Riker** — *tell:* "Right elbow propped on the chair arm, forefinger across
  his lips when listening." *manner:* "asks short questions that assume
  competence."
- **Data** — *manner:* "states values to more decimal places than anyone asked
  for." *tell:* "Fingers lift from the panel between inputs at a consistent
  interval, like a metronome."
- **Worf** — *manner:* "Clipped, formal, drops articles when reporting."
  *trait:* "Wants the simulation to present a real tactical challenge."
- **Troi** — *manner:* "phrases observations as questions until she's certain."
- **Conn Ensign** — *trait:* "Trying to fly the simulated course clean enough
  that nobody notices he's on the mid-watch." An original for a character canon
  never named.

**Register adapted to the place.** In the tavern, extras muttered to each other
and largely ignored the party. On an evaluated bridge they speak in station
reports addressed to the captain — correct, and not something the prompt says
explicitly. The `place` block and style guide carried it.

## 3. The claims loop closed, end to end

First live exercise of `background_claims.py`, in the setting with the most
canon to trip over.

- **t3** — Worf self-declares *"Two D'deridex-class warbirds at bearing
  two-seven-one mark eight"* (credence `ordinary`); Data self-declares
  *"Disruptor charge at 89.2% of maximum"* (credence `high`, from his blurb).
  Both elaborate a Director-established event with detail the Director never
  authored. Recorded as hearsay.
- **t4** — the Director **deliberately** populated
  `state_diff.ratified_claims` with both, verbatim. Not incidental text-match
  ratification: an explicit adopt decision.

So: manager invents → self-declares via `asserts` → recorded with
blurb-derived credence → surfaced in the Director's payload → Director adopts →
canon. The `asserts` path — the mechanism I was least confident would hold —
worked without a single prompt retry.

**The strongest single justification for the whole design is t5.** La Forge
says:

> *"…secondary systems failure in the simulation lines up with an actual power
> loss on that junction. The hardware damage is real, not just the drill
> scenario."*

That escalates a training exercise into a genuine emergency — a world event, the
single thing §3.12 says the manager must never author unilaterally. The system
**caught it and held it** as unratified hearsay for the Director to settle.
Before the claims loop this would have silently become canon: a stateless
background agent rewriting the premise of the scene with no ratifier.

---

## Bugs found (all five fixed)

The run was worth it for these. Four of five share one root cause: **ranks and
titles were not normalized anywhere in the new code**, though `commit.py`
already carried the vocabulary for it.

**1. A registered character was tracked as background furniture — serious.**
The Director wrote "Captain Jean-Luc Picard"; the roster holds "Jean-Luc
Picard". Exact-casefold comparison missed it, so Picard was tracked as a
presence, given a blurb, and *handed to the stateless scene manager as
manageable furniture* — on turns 2–6 he was in the managed list. The model
declined to puppet him every time, which is precisely the "compliance holds
until it doesn't" situation this codebase has repeatedly made structural
instead. Fixed by `commit.strip_name_titles` / `name_in_roster`, applied to both
tracking and `managed_presences`.

**2. A bare rank was recorded as invented lore.** Data's *"…profiles, Captain."*
produced a claim `['Captain']`, then auto-ratified because "Captain" appears
throughout the prose. Fixed by `is_title_only`.

**3. A known crewmate's surname was recorded as invented lore.** Riker saying
*"Worf"* did not match the known "Lieutenant Worf". Fixed by title-stripping in
`_known_variants`.

**4. Hyphenated names split.** "Captain Jean-Luc Picard" scanned as
"Captain Jean" + "Luc Picard", matching nothing. Fixed in the proper-noun regex.

**5. Long refs are unmatchable ratification keys — a design-level bug.**
La Forge self-declared a whole sentence as his ref. On t6 Picard plainly acted
on it (*"Mister La Forge — isolate that junction. Bypass the EPS tap"*) but the
Director never listed it in `ratified_claims`, and the long ref shared no string
with the prose, so a claim the fiction had visibly adopted stayed hearsay and
would have expired as if never established. Fixed by capping refs at
`MAX_REF_WORDS` (6) and instructing the manager that an assert is a *short
referring phrase*, not a sentence.

All five verified against the run's real data after fixing: Picard reads as
registered; Worf and Riker correctly do not; "Captain" and "Worf" no longer
generate claims; `"Two D'deridex"` still does.

---

## Still open

**Ratification is one-sided.** The Director can adopt explicitly, and claims
expire, but there is no *contradict* path that records the outcome — a claim the
Director rejects looks identical to one it ignored. §3.13 argues contradiction
should not be inferred by string matching, which is right, but an explicit
`contradicted_claims` list alongside `ratified_claims` would let the engine know
a presence was *wrong* and let a later beat show it.

**The manager still does not exclude presences the Director already voiced this
beat.** It behaved correctly every turn across both runs, but nothing enforces
it (see the tavern findings).

**Cost.** 179–545s per turn.
