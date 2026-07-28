# Design: psychology as pressure, not as premises

**Status:** investigation with measurements, no code changed. The measurements
are the contribution; the proposals are ranked by how sure I am of them.

Instrument: 158 beats of one character's full reasoning traces (maze arm A11,
`arcee-ai/trinity-large-thinking` at medium reasoning). A character agent
thinking aloud about its own psychology, at a length no ordinary playtest
produces.

---

## 1. What was measured

**He reasons FROM his sheet, deductively, on every beat.**

| | count | per beat |
|---|---|---|
| cites *"his drive"* | 299 | 1.9 |
| cites *"never breaking stride"* | 249 | 1.6 |
| explicit *"Given his X, he would Y"* | 197 | 1.2 |
| *"impatient with standing still"* | 189 | 1.2 |

**Conflict is computed, not felt.**

| | count |
|---|---|
| `conflicts_with` / `inhibition` / `norm_compatibility` scored | ~125 |
| *"torn between"* | **1** |
| *"tension between"* | 1 |
| *"at odds"* | 0 |
| acts against a stated value | **0** |

**Ambivalence is structurally present and phenomenally absent.** Of 52 beats
where both fields appear, 29 mark a *different* want as suppressed from the one
enacted, and only 1 is incoherent. The schema is being satisfied correctly. It
is simply not being experienced — the field is filled and the reasoning above it
contains no tension.

## 2. The mechanism, and it is ours

The character prompt says:

> "Derive 2-3 beat wants from your drive (`self.psychology.drive`) and standing
> intentions (`self.intentions`) as they meet THIS situation"

**We instruct the deduction.** The payload hands the character its own
psychology as labelled, citable data, and the prompt tells it to derive
behaviour from that data. It complies, 197 times.

This is the salience lesson from `_annotate_known_exits`, in a new place. There,
the correct exit was the *lightest* entry in the payload — every good thing
about it was the absence of something — and it was chosen against nineteen
beats running. Position and weight are salience, and ours pointed the wrong way.
Raw psychology is the heaviest, most quotable block in the character payload,
so it gets quoted.

## 3. Where it diverges from real psychology

None of this is a claim that the engine's model is unsophisticated — the
appraisal, stress, hedonic and ambivalence machinery is all present and
correct. The divergence is in **presentation**, and it produces four artefacts:

**People do not consult their trait list.** They act and rationalise afterward.
A character who reasons "given his traits: brisk, decisive, impatient" is
performing a psychological self-assessment no person performs. It makes the
character a consistent *function* of its sheet — which is exactly what a person
is not.

**Values are revealed by trade-offs, not applied as filters.** A flat list —
"a fast clean run", "never breaking stride" — has no ranking, so it cannot be
traded against anything, so it operates as a constraint set. What makes
character legible is which value gives way under pressure.

**Ambivalence is felt before it is resolved, and often stays unresolved.**
Here it is resolved in the same breath it is recorded: a suppressed index and no
trace of the suppression in the thinking.

**Self-description and behaviour diverge, and the gap IS the character.** This
character's self-description is a perfect predictor of his behaviour. Nobody's
is. "Never breaking stride" should be a thing he believes about himself and
violates under enough pressure, noticing or not noticing afterwards.

## 4. Proposals, most-confident first

### (a) Values as ordered trade-offs, not a flat list — HIGH confidence

`psychology.values` as authored (`["a fast clean run", "never breaking stride"]`)
cannot express which one yields. Prefer pairs that name the loser:

```
"speed over thoroughness"       (not "a fast clean run")
"arriving over looking good"    (not "never breaking stride")
```

Cheap, needs no engine change, and directly fixes the negation problem in
[`DESIGN_RUNNING.md`](DESIGN_RUNNING.md) §5 — *"never breaking stride"* inverted
into an argument against running because a prohibition has no counterweight
named in it.

### (b) Stop instructing derivation — HIGH confidence

Change the WANTS AND GOALS wording so wants arise from *the situation as this
character meets it* rather than being derived from the drive. The drive should
be the thing that makes some options obvious and others invisible, not a premise
in an argument. Small edit, and everything measured above says it is the live
wire.

### (c) Deterministic inclination beside the raw sheet — MEDIUM

The engine's own pattern, from `psychology_runtime`: stress **biases the next
deliberation without selecting behaviour**. Psychology could arrive the same
way — a derived, short "what pulls at you right now" computed from drive ×
situation, carrying the salience, with the raw sheet demoted or dropped from the
payload.

The risk is real and I would want it tested rather than assumed: a derived
inclination is the engine deciding what the character is inclined to, which is
one step from the engine deciding behaviour. It must stay an inclination the
character can act against — and, unlike today, sometimes should.

### (d) A trait as a disposition, not a switch — MEDIUM

"Impatient" currently reads as *always impatient*. Dispositions are
probabilistic and situation-dependent, and the engine already has the machinery
to express that (stress, hedonic state, absorption). Whether that is worth
representing explicitly, or emerges once (b) and (c) land, is the open question.

### (e) Permit self-violation — LOW confidence, high value if right

Zero violations in 158 beats. Something should make a character act against a
stated value under enough pressure and then have to sit with it. But an
instruction to "sometimes violate your values" would produce random
inconsistency, which is worse than rigidity and reads as a broken machine. The
honest position: the *absence* is measured and real; the fix is not obvious, and
should probably fall out of (a) — a value that names what it beats can lose to
something else — rather than being built directly.

## 5. What would settle it

Re-run the same maze arm with (a) and (b) only, and re-measure the same
counters: *"Given his X"* per beat, *"torn between"* per beat, and violations of
a stated value. The prediction is that deductive constructions fall sharply
while behaviour stays recognisably the same character — which is the whole
claim, that this is presentation rather than substance.

If behaviour changes character too, the diagnosis is wrong and the sheet was
doing more real work than this document credits.
