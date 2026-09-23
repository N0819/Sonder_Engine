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

## Measurements (2026-09-22, chat 153 turns 23/25/26, copies of `engine.db`)

Each stage was rerolled alone (`run_pipeline(only_key=)`) on its own
database copy, so both contracts read identical inputs. The models were the
owner's configured stack (Fireworks GLM-5.2 on every Director role, default
reasoning effort `high`), with Jev on OpenRouter. The harness lives in the job's
scratch directory; `orchestration.prose_contract` on each variant holds the raw
record.

**Wall clock per stage, final configuration** (threshold 0.5, sharpened
questions, record pre-filter, `already_happened`, widening fix, encoder
`reasoning_effort=off`):

| | turn 23 | turn 25 | turn 26 |
|---|---|---|---|
| interpret, causal | 59.7 s | 13.1 s | 64.8 s |
| interpret, prose | **12.6 s** | **10.2 s** | **11.9 s** |
| resolve, causal | 43.4 s | 13.6 s | 32.0 s |
| resolve, prose | **34.5 s** | 19.6 s | **30.6 s** |

**Where the time goes.** The prose Director's call is shorter than the causal
Director's: 5.7–8.2 s against 5.6–19.8 s at resolve, and 0.7–1.3 s against
5.1–18.3 s at interpret. Jev takes 0.21–0.44 s and costs about $0.00002 for
the whole 38-question battery. The encoder is the rest.

**The encoder's cost was reasoning trace, not the single call.** At the
default `high` effort it wrote 12–20k output tokens per beat, one run hitting
the 50k ceiling, against a real answer of about 1.5k tokens. Resolve took
102–198 s. `low` barely moved GLM (46–60 s). With `off` it writes 1–2.4k
tokens in 3–11 s. **Set `director_specialist` to `off` under this
contract**, in Settings → reasoning effort. The encoder transcribes a decided
account; the thinking happened in the Director.

**Jev routing.** With the first question wording and threshold 0.3, it granted
13–18 channels per resolve beat. The questions matched words, not record
classes: `public_evidence` scored 0.76–0.85 on every beat with dialogue, and
`contact_action_ops` 0.84–0.94 because the prose described room-wide vibration.
Three changes brought it to 3–9 channels:
- each question now states its class and its complement ("Answer no when…");
- channels that can only act on a standing record are asked only when that
  record exists (`_RECORD_FACTS`);
- the threshold is 0.5.

Replayed against six stored beats, the 0.5 selection still covered every
channel the encoder went on to write, except on one beat where the causal
contract wrote nothing either. Live, widening fired on 2 of 3 resolves and
cost about 10 s each.

**Fidelity.**
- Interpret wrote the same channels as causal on all three turns.
- Resolve wrote a superset of causal's channels on turns 23 and 25, and on
  turn 26 every causal channel except `poses`.
- Two defects were found live and fixed before the final round:
  - the Director wrote past a player-asserted landing (`already_happened`);
  - a widened re-ask returned only the events its new tool touched, and the
    replacement dropped the rest of the beat (`previous_events`, plus a
    thinner answer never replaces the first).

**Authorship, read as fiction.** The prose is concrete and consequential. The
Director reconciles a character's declared line with the world rather than
editing it: *"'…she's in flight.' But even as he said it, the console room
shuddered underfoot…"*. With the latitude this contract gives, it also runs
ahead. On turn 25 it landed the ship, one beat before the player wrote that
the ship "begins to land". Whether to pace it is an owner decision; nothing
here clamps it.

**Not measured yet:** more beats, other stories, the narrator's page
downstream of each contract, and repair and correction rates over a long run.
