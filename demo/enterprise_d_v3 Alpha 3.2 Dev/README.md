# Enterprise-D — The Kelvan Array (v3, alpha3.3)

**Status: complete — a 12-beat run on `alpha3.3`.** An earlier v3 attempt was
destroyed by a power cut; what could be salvaged of it is kept alongside as
evidence (see *The destroyed first attempt* below).

| File | What it is |
|---|---|
| `transcript.md` | The run, beat by beat: player input, narrated prose, speakers. |
| `findings.md` | V1 (fixed), V2/V3 (open), and the result — strain accrual confirmed, no rupture, and why that is correct. |
| `run_log.jsonl` | Per-turn machine-readable capture, appended as each beat committed. |
| `run.db` | The isolated run database. Gitignored; kept locally. |
| `transcript_partial.md` | Salvage of the destroyed first attempt. |
| `v1_evidence_prefix_run.jsonl` | The 9-turn log of the pre-fix run that exposed V1 — kept as the before-picture. |

## Headline

- **Strain accrual works, in both directions** — it rises on genuine drive
  wounds, decays when nothing wounds, and falls when the fiction *vindicates*
  the drive. `findings.md` has the full curve.
- **No rupture landed, and that is the correct outcome.** The episode vindicated
  Dr. Vorne twice over; a character the fiction has just proved right has
  nothing to break.
- **V1**: a beat could end with the character it was about never simulated —
  found here, fixed in `86fa6ab`, and it reframes the v2 audit's W1.
- The run's best beat is one the player did not author: Picard and Data jointly
  refuted the *player's* premise using a grammatical distinction inside a
  translation Data had produced four turns earlier.

## The destroyed first attempt

### What happened

A v3 run of the Kelvan Array scenario was played on 2026-07-23 against
alpha3.2-dev, to regression-test the fixes that shipped after the v2 run —
principally the drive-strain accrual fix (`4f562c7`), which the v2 audit had
identified as the central open flaw (v2 `findings.md`, W1: "the engine can now
detect that a soul should break … but it cannot yet make a character walk
through the door").

The run reached **turn 15** and the rupture landed: Vorne ordered the Array
shut down himself and let go of his life's work. That was the result the run
existed to obtain.

The harness had correctly isolated the run from the real `engine.db` by copying
it to a scratch database — but placed that copy under `/tmp`. The machine lost
power, and `/tmp` is cleared on boot (boot recorded 2026-07-23 23:47). The
database, the harness, and the per-turn output files went with it.

`engine.db` chat 28 (`USS Enterprise — Kelvan Array (fresh test)`) is the
scaffold the run was seeded from; it holds the scenario, cast, and lorebook but
zero turns, because every turn was written to the scratch copy.

### What survived, and how

The driving session's own log lives outside `/tmp`
(`~/.claude/projects/.../*.jsonl`) and was mined for anything the run had
echoed into it. That yields:

| File | Contents |
|---|---|
| `transcript_partial.md` | Turns 0–5 in full — player input, narrated prose, speaker list, and Vorne's drive-strain reading. Turns 6–15 as quoted excerpts and metrics only. |

Everything else a demo folder normally carries is **absent and cannot be
reconstructed**: no `.chat.json` (nothing to export), no `audit_data.json`, no
`coverage.md`, no complete transcript. Turns 6–15 had their prose written to
files in the destroyed scratchpad; only the lines quoted in conversation
remain.

Treat the excerpt section of `transcript_partial.md` as evidence, not as a
transcript — it is a selection made for discussion at the time, not a record of
the beat-by-beat run.

### Lesson applied

The isolation was right; the location was wrong. A run database belongs
somewhere durable (this folder, gitignored) rather than `/tmp`, so that
isolation from `engine.db` costs nothing when a machine dies mid-run.
