# The prose contract: an author that writes, one encoder that builds

**Status: EXPERIMENT, 2026-09-22, branch `worktree-jev-prose-director`.** Off
by default. Selected by the setting `director_contract = "prose"`; the causal
ledger contract ([`DESIGN_SPECIALIST_CONTRACT.md`](DESIGN_SPECIALIST_CONTRACT.md))
stays the default and is untouched when the setting is absent.

## Why

The causal contract made state tracking work. It did it by making the
Director two things at once: the author of how a beat realistically unfolds,
and its dispatcher, which meant cutting spans, allocating item handles, and
routing every row to channel categories under a 12 KB sheet. Five hands then
re-read those rows positionally, with a forwarding round and a recompiler to
reconcile them. The owner's observation that motivated this branch: the
tracking works, but making the model track everything cost it the ability to
play author. The narrative lost its flow.

A shorter output contract does not fix that, because the job is still
dispatch. This contract takes dispatch away from the author entirely.

## The contract

For both `director_interpret` and `director_resolve`:

1. **The Director writes prose** (`prose_contract.director_<stage>` card,
   role `director`, step key `director_prose`). It resolves the beat as an
   objective account, with wide latitude to add detail and carry consequences
   as far as they would reach. It has two limits: a declared act is not
   replaced, and another mind's choices are its own. The rest of the sheet is
   habits that make prose buildable (order, exact quotes, one name per thing,
   where bodies end up, how long things take), not rules.
2. **Jev picks the tools** (`llm/decisions.py`: TypeSafe's decision model on
   OpenRouter's `/api/alpha/decisions`). One `noul` question per channel the
   story keeps and the stage serves (`jev_questions.<channel>`), all asked
   at once against the prose, the cast names and the known rooms. A channel is
   granted when its yes-probability reaches `prose_contract_threshold`
   (default 0.3). Jev writes nothing, so it cannot start authoring. It
   **fails open**: if Jev is unreachable, every candidate is granted.
3. **One encoder does every hand's job** (role `director_specialist`, step key
   `director_specialist`). Its sheet is a small core plus the granted
   channels' **existing, unmodified** chunks. The core tells it how to read
   those chunks' several-hands vocabulary. Its payload is the prose, the
   Director's own inputs, and the union of the world slices the granted
   channels' owners would have received, so it binds existing things by
   their keys. It writes the beat as **ordered events**, each carrying its
   transforms. It also spans: one event per causal step, and every spoken line
   is its own event.
4. **Code converts.** Position becomes `chrono_id`. Each distinct item name
   gets one handle. Categories come from the channels actually written, plus
   `speech` and `attention`. The rows then enter `normalize_causal_ledger`
   exactly where the causal Director's did. The transforms are split by channel
   owner and handed to `_run_specialists(answer_for=...)`, so the binding,
   patch validation and fold that judge a hand's work judge this too. Every
   floor after the fan-out runs unchanged.

With one writer, the encoder's output order is the chronology. No forwarding
round runs, and nothing is reconciled across hands. The global compile still
runs; with a single source, it is only in-order application.

**Widening.** If the encoder names a tool it needed and was not granted
(`missing_tools`), the engine grants it and asks once more. That answer
replaces the first; nothing is merged. `prose_contract_widen = 0` turns this
off.

## What is kept and what is replaced

| Kept | Replaced |
|---|---|
| Stage outputs: `ledgers`/`sequence`/`causal_ledger`, `state_diff`, `state_assertions` | The causal Director sheet (`causal_director.txt`) at both stages |
| `normalize_causal_ledger`, the authority checks, every post-fan-out floor | Director-authored spans, item handles and categories |
| Bind, validation and fold in `_run_specialists` | Five parallel hand calls, forwarding, positional reconciliation |
| Channel chunks, verbatim | `_dispatch_specialists`' gates, as the predictor of which tools a beat needs |
| Commit, perception, narrator | — |

## Where it lives

- `agents/director_prose.py`: the contract (`run`, `dispatch`, `ledger_from_events`).
- `llm/decisions.py`: the Jev client (`decide`, `OVERRIDE` for tests).
- `llm/prompts.py`: `prose_director_prompt`, `unified_specialist_prompt`, `jev_channel_questions`.
- `llm/schemas.py`: `ProseDirectorOutput`, `UnifiedEvent`, `UnifiedSpecialistOutput`.
- Cards: `prose_contract/*.txt`, `jev_questions/*.txt` (the `ja` pack carries the English text until translated).
- `agents/director.py`: the two call-site branches and `_run_specialists(answer_for=)`.
- `tests/test_prose_contract.py`.

Each stage's record persists at `orchestration.prose_contract`: the prose,
Jev's probability per channel, the selection, encoder timings, any widening,
and the raw events.

## Known gaps

- **Extension specialist families are not absorbed.** Their sheets are not
  built from engine chunks. Under this contract they do not run.
- **The chunks still speak the several-hands dialect** ("request inventory_ops
  in required_channels"). The core reinterprets it. A native rewrite would be
  shorter, but it would fork the chunks between the two contracts.
- **Establish is out of scope.** The opening turn keeps its own Director.
- **Author-side retries** (world-pressure must-tick, player-authority) re-ask
  the causal Director with corrections. Under this contract they read the
  converted rows, which carry the same fields. That path is untested under
  this contract.

## Measurements

See the section below, filled in from the first A/B on chat 153.
