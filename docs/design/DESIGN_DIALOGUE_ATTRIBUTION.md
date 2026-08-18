# Dialogue attribution (who said this line)

**Status: not built.** This is the argument, not the change. Current behaviour
is in [`story/dialogue_colors.py`](../../dialogue_colors.py) (colour derivation and
the render-time lookup), with `agents/composer.speech_percept` as the
already-existing per-observer, per-line seam this proposal would key off.

## The gap

Colour is a render-time lookup: a persisted `dialogue_log` entry supplies the
speaker, and the line is coloured where its `exact_quote` appears verbatim in
the narrator's prose. That indirection is right, and this note does not propose
replacing it — storing offsets would invalidate on every prose edit, and
storing the colour would freeze three hundred turns of backlog against a card
the host may still change. What is persisted is the *identity*; the colour is
derived. Keep that.

What it rests on is DIALOGUE FIDELITY: the assumption that every `dialogue_log`
line reappears in the prose, verbatim and separately delimited. Measured on
chat 76, that assumption holds most of the time and fails legibly when it
breaks:

| speaker | lines colourable | |
|---|---|---|
| The Doctor | 40 / 43 | |
| the player | 0 / 16 | **correct** — the narrator is not meant to echo player dialogue |
| **total** | **40 / 59** | |

The 16 are not a defect and must not be "fixed". The three are: on turn 60 the
narrator merged three separate `dialogue_log` entries into a single quoted
block. Each entry's text is present, but the interior ones no longer carry
their own delimiters, so the matcher finds no standalone quote to attribute and
all three fall through to uncoloured.

Two structural cases can never match, independent of narrator behaviour:

- A **fragment** percept (`speech_percept` with `level == "fragment"`) carries
  only `_muffled_fragment(body)`. There is no verbatim body to find, because
  the observer did not hear one.
- A line the narrator legitimately **paraphrases** rather than quotes.

So the failure mode is not rare model sloppiness. It is a textual match
standing in for a structural fact the engine already knows.

## What the engine already has

`agents/composer.speech_percept` emits one percept per delivered line per
observer. It carries `source_label` (already the observer-safe display name,
so recognition has been applied), `fidelity`, and a `dedupe_key`. Every fact
attribution needs is present at composition time and is thrown away by the time
anything is rendered.

The missing piece is small: a **key** on the percept, and a matching span in
the narrator's output.

## Proposal

The narrator marks spans it attributes, e.g. `<d:K>…</d>`, where `K` is a key
handed to it in its own payload. The renderer resolves `K` to a colour
server-side. Four constraints make this safe.

**1. Player-facing composition only.** This is the load-bearing one. A speaker
key that appears in any view composed for a *character* is a channel through
which a mind could learn that two lines came from one mouth — which is
precisely the fact the firewall exists to withhold when a speaker is disguised,
unseen, or unrecognised. Attribution markup belongs to the player-facing render
path and nowhere else. Character-facing composition keeps exactly what it has
today.

**2. Keys are per-turn, never durable.** A stable per-character key is a
correlatable pseudonym: identity without a name. Even player-facing, a durable
key asserts sameness across appearances — that the hooded figure in turn 12 and
the stranger in turn 40 are one person — which is a claim the story may not
have earned yet. Key by index into *this turn's* delivered lines. Nothing
survives the turn, so nothing can be correlated across turns.

**3. Resolution is recognition-gated.** A key resolves to a character's colour
only if the player's own vantage recognises that speaker. An unrecognised
speaker renders neutral. Colour is an assertion of identity, and an
unrecognised speaker's identity is exactly what has not been established;
colouring them their true colour would leak through the palette what the prose
carefully does not say. Neutral is not a degradation here — it is the correct
answer.

**4. The current matcher stays, as the fallback.** Every turn already on disk
has no spans, and reroll and replay must keep working. Resolution order:
explicit span → existing verbatim match → uncoloured. Uncoloured remains the
only safe failure; never colour by guess.

## Why not simply enforce fidelity

Tightening the narrator contract so it never merges quoted lines is worth doing
on its own merits, and would recover the three lines in turn 60. It does not
make attribution robust: the fragment and paraphrase cases above are correct
narration that a textual matcher still cannot attribute. Do both — but the
prompt fix is a fidelity fix, not an attribution fix, and treating it as the
latter is how this comes back.

## Residuals, stated up front

- The narrator can emit a key it was not given, or attach one to the wrong
  span. Resolution must validate the key against the turn's own delivered
  lines and fall through to the matcher when it does not, exactly as an
  unmatched quote does now.
- A single line spoken by two voices in unison has no single key. It falls
  through to neutral, which is right.
- Per-turn keys mean a reroll re-keys. That is intended: nothing downstream
  may store them.

## Before building

Confirm on a live turn that the player-facing composed view is genuinely a
distinct path from character-facing composition, and not a filtered projection
sharing the same builder. If it shares one, constraint 1 is not enforceable by
construction and the design needs the split first. That check is the first
task, not an assumption of this note.
