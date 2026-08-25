# The narrator paraphrases delivered dialogue, and insisting does not stop it

Experiment record, not implementation authority. Measured 2026-08-24 against
chat 1 turn 3 of the Enterprise-D run
(`demos/enterprise-d-artifact/`, harness
`tools/dialogue_placeholder_experiment.py`, artefact
`dialogue_experiment.json`).

## The failure

Nine lines from three speakers reached the player's view verbatim. The
narrator returned:

> I suggest modelling the signal as a counting system, and the spare upright
> man gives his approval in that measured, encouraging voice.
>
> Then come his layered cautions: yellow alert, the possibility that the
> object is counting toward us, the need for maneuvering room, all delivered
> in that sequence of even, tactical, and finally quiet firm tones.

Every line is present upstream — `director_resolve.dialogue_log` holds all
nine with exact quotes, and `perception_outcome`'s player view carries them
word for word. The loss is entirely at the narrator.

**The engine detected it and could not repair it.** `fidelity_warnings`
carried one entry per dropped quote and the retry loop spent **three narrator
calls** on the beat, feeding the specific dropped lines back as correction
notes. The model paraphrased all three times.

**And the reader loses the line outright.** There is no second surface: the UI
renders the narrator's prose and uses `dialogue_log` only to *tint* quotes it
finds inside it (`static/js/chat.js`: "DIALOGUE FIDELITY requires every one of
those lines to appear in the prose verbatim... a quote that no longer matches
simply goes uncoloured"). A paraphrased line is gone, and the speaker colouring
silently degrades with it.

## Why the prompt is not the variable

`DIALOGUE FIDELITY` is already the strongest statement in the narrator card —
"ABSOLUTE", "MUST appear in your prose, verbatim, complete, and unaltered",
"NEVER SUMMARISE A SPOKEN LINE" — and it names this exact failure mode in its
own examples ("she tells him plainly"). It is marked as overriding SCENE CRAFT
and the paragraph budget. There is no stronger sentence available, and three
attempts with concrete correction notes did not produce compliance.

This is the guard class this repo already has a name for: a literal check whose
failure rate rises with how fluently the model writes. The difference from
`_check_player_interiority_prose` (deleted, alpha 9.8.1) is that **this rule is
correct**. Dialogue fidelity is not a matter of taste. So the fix is not to
delete the rule; it is to stop asking prose to carry it.

## Arms

Three shapes of the same task, same view, same model (`narrator` role), three
samples each. Scored with the engine's own `_contains_quote` over the eight NPC
lines — the player's own line is excluded, because the PLAYER ECHO RULE
requires its *absence*, the opposite test.

| Arm | What changed | NPC lines surviving |
|---|---|---|
| A baseline | nothing — the shipped prompt | 18/24 (75%) |
| B named | speakers named in the view instead of "the spare upright man" | 16/24 (67%) |
| C placeholder | the model never types a line | **24/24 (100%)** |

**B is the result worth stating plainly: naming did not help.** The obvious
hypothesis was that the composer's appearance labels — the story had an empty
`known` ledger, so Picard rendered as "the spare upright man" — pushed the
model toward describing speech rather than quoting it. It did not. B is
slightly *worse* than baseline, inside noise. The identity gap is a real
defect and it is not this one.

## C, and why it keeps the prose

The model writes the beat normally and puts `{{L1}}`…`{{Ln}}` where each
delivered line belongs. The engine substitutes the exact text afterwards.

It cannot paraphrase a line it never types. That is the whole mechanism, and
it is the move this codebase has already made once: perception stopped
repairing model prose when the composer began writing percepts, because
"chronology is a field rather than a pass". Dialogue fidelity is the same
shape — a property of the assembly, not a behaviour to be requested.

Nothing is taken from the writer except retyping. Placement, attribution, beat
order, paragraphing and every sentence around the speech stay with the model,
and the output holds up:

> Picard meets your eyes with that measured calm, then nods once. "Proceed
> with the counting-system model, Lieutenant. Incorporate the temporal
> correlation to our arrival and project the terminus."
>
> Riker leans forward in his chair, voice cutting in before the order can
> settle. "If it's a counting system, those shortening intervals could be a
> countdown, Captain..."

**The residual failure mode changes character, which matters more than the
percentage.** Under A, a lost line is a paraphrase: undetectable except by
substring search, unrecoverable, and already past the reader. Under C, a lost
line is an unused token: countable before the prose is shown, and the engine
knows exactly which line is missing and can place it. A failure that can be
counted can be fixed deterministically; a paraphrase cannot.

## What this does not settle

- One turn, one model, three samples per arm. The direction is large and
  consistent, the magnitude is not established.
- Nine lines in one beat is the hard end of the distribution; turn 2 of the
  same run passed with one narrator call and no warnings. The failure is
  load-dependent and the experiment measures the load where it bites.
- Whether a model that must place tokens writes *better* or *worse* prose than
  one retyping lines is not measured here — only that C's output is not
  visibly degraded.
- C was run with the quotes still present in the view. Blanking them would
  change two variables at once and was deliberately not done.
