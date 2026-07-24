# Enterprise-D — The Kelvan Array (v2, 40-turn demo/audit)

A fresh **40-turn** Sonder-Engine run of the Star Trek: TNG "Kelvan Array"
scenario (a re-run of `../enterprise_d/`), built to **regression-test the fixes
that shipped since the prior D+ run** and to surface new engine flaws. Player =
Cmdr. Vale (Federation ethics auditor); Picard and Dr. Vorne are cast; the senior
staff are seeded as background presences and promote as the episode runs; Vorne is
the drive-rupture subject the episode is built to break.

Generated headlessly on `deepseek-v4` (director/character on `pro-cheaper`,
perception/narrator on `flash:thinking`), on an **isolated DB** — the real
`engine.db` was never touched. **41/41 turns committed, 0 pipeline errors.**
Fable narrative grade: **C+** (up from the prior **D+**).

## Files

| File | What it is |
|---|---|
| `transcript.md` | The full story, each beat tagged **(activated: …)** with the engine features that fired that turn, from real pipeline evidence. |
| `coverage.md` | Feature-coverage matrix: **FIRED 26 / MISS 8** of 34 checks, plus the round-trip result. |
| `findings.md` | The weakness ledger (W1–W11, Symptom / Root cause / Fix), Part 0 = regressions cleared, Part 4 = Fable's verdict, Part 5 = prioritized fix plan. |
| `audit_data.json` | Machine-readable per-turn capture: input, prose, pipeline step digests, and per-turn world + character-interior snapshots (incl. the drive-strain curve). |
| `roundtrip.json` | Export→import verification result. |
| `Enterprise_D_Kelvan_Array.chat.json` | **Playable, importable export** (`version 3`, self-contained `resources` bundle). Gitignored (33 MB) — kept locally. |

## Loading the playable chat

Import `Enterprise_D_Kelvan_Array.chat.json` via the app's **"⤓ Import story"**
button, or `POST /api/chats/import` with body `{"data": <file contents>}`. It
imports with all 41 turns, 6 characters, 349 memories, and the full scene graph —
verified to round-trip into a fresh install (`roundtrip.json`: `ok: true`).

## Headline result

- **Fixed since D+:** autonomous background→cast promotion (4 crew promoted on
  their own), obligation-ledger discharge (3→0), player-fact adjudication, and
  export/import portability — all confirmed working (`findings.md` Part 0).
- **The central open flaw:** the **drive rupture never lands** — the engine held
  the rupture window open for 23 turns (strain pinned ~1.0) but the transformation
  is entirely model-gated with no deterministic floor, so Vorne collapses
  beautifully and then *reverts* to his turn-2 self. `findings.md` **W1** has the
  root cause (`commit.py:2897` / `2931`) and the fix. As Fable put it: "the engine
  can now detect that a soul should break, hold the door open, and even stage a
  beautiful collapse — but it cannot yet make a character walk through the door."
</content>
