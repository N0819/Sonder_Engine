# Enterprise-D — The Kelvan Array (v3, alpha3.2-dev)

**Status: salvaged partial. The run's database was destroyed and is not
recoverable.** A clean re-run is the intended replacement for this folder.

## What happened

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

## What survived, and how

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

## Lesson applied

The isolation was right; the location was wrong. A run database belongs
somewhere durable (this folder, gitignored) rather than `/tmp`, so that
isolation from `engine.db` costs nothing when a machine dies mid-run.
