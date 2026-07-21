# Meridian Station — The Vesper Audit (demo story)

A 30-turn showcase run of the Sonder Engine, purpose-built to activate and verify
(nearly) every engine capability. Near-future hard-SF investigative thriller: an
Oversight auditor investigates an "incident" aboard a deep-space research station
where the chief scientist is hiding the reactor logs and the station AI is under a
protocol lock.

Generated headlessly on the hardened engine (`google/gemini-3.5-flash`) with
**zero schema-validation failures** across all 30 turns.

## Files

| File | What it is |
|---|---|
| `transcript.md` | The full story, each narration box tagged **(activated: …)** with the engine features that actually fired that turn (derived from real pipeline evidence). |
| `coverage.md` | Feature-coverage matrix: 27/30 in-story checks FIRED + 7 phase-2 capabilities verified. |
| `findings.md` | Pipeline findings on the fixed run (2 benign: one network transient, one minor id-encoding note). |
| `findings_before_fixes.md` | Findings from the *pre-fix* run (8, including a live concealed-speech leak) — the before/after. |
| `Meridian_Vesper_Audit.chat.json` | **Playable chat file** (gitignored — regenerate or keep locally). Portable, self-contained. |
| `meridian_showcase.html` | The published showcase page (gitignored). |

## Loading the playable chat

Import `Meridian_Vesper_Audit.chat.json` via the app's **"⤓ Import story"** button,
or `POST /api/chats/import` with body `{"data": <file contents>}`. It imports with all
30 turns, 4 characters, 3 lorebooks, 204 memories, and the full scene graph — ready to
continue playing from turn 30.

> The export was produced with the portability fix (`chat_export` now embeds a
> `resources` bundle), so it imports cleanly into a fresh install.

## Features exercised

Establishment · perception split · dialogue_mode · addressed_to · relationships ·
theory-of-mind · **concealed speech** (verified no-leak) · private thought · movement ·
mapping (full + quick) · room creation · location & system lore retrieval ·
contested + dice · reaction_loop · interaction_loop · parallel blind character steps ·
background_react · **promotion** (background NPC → cast) · dramatic-irony feed ·
promise ledger · attire · conditions · **time_skip** · sensor firewall ·
**multiplayer** (`narrator_extra`) · first-person narration · branch · reroll ·
rerun-from-stage · checkpoint restore · memory consolidation · temporal frame ·
**paradox engine** (fixed-point + hazard).
