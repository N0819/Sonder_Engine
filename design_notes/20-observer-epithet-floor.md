# 20 — A minted epithet is not a name, and an index is not prose

STATUS: built with this note. Method: three live playthroughs of the same
village-square opening through `tools/model_playthrough.py`, with three
different narrator models against IDENTICAL perception views (scratch DBs
`mix.db` — cerebras narrator — and `mix2.db` — fireworks narrator, read-only).
Every defect below is visible only in the comparison: each model failed
differently on the same input, so the divergence localises the fault in the
INPUT rather than in any of them.

This note extends note 18's subject — the composer's identity floor — to the
half it did not cover.

## The scene, and why it is the worst case for this

Four bodies in a market square. Three cast cards with an empty
`embodiment.visible`, which normalizes to the generic
`"A person of unremarkable appearance."`; one persona, Corin, reading
`"A young smith's apprentice with a borrowed sword."` Nobody has recognized
anybody. So `_unknown_actor_label` mints:

| body | minted label |
|---|---|
| Corin (the player) | `the young smith's apprentice` |
| Sera / Bryn / Wren | `the person of unremarkable appearance` ×3 |

One distinctive label and a three-way collision, in one room. That is the
whole diagnosis.

## Defect 1 — the epithet in the objective record

`director_resolve.resolved_event` read:

> Bryn turns toward **the young smith's apprentice** standing at the group's
> edge — a lean figure barely past boyhood…

That body is the player, and the same paragraph had already named him
canonically ("Corin goes still among the group at the well"). The Director is
omniscient; it knows the name. "The young smith's apprentice" is an EPISTEMIC
label built from the persona's appearance FOR OBSERVERS WHO DO NOT KNOW HIM.
The cast using it in their declarations is correct and is the firewall working
(66 occurrences in `interaction_loop`, all legitimate). The Director taking it
into the objective account is not.

The consequence is exact: the composer TRANSLATES a canonical name into the
right thing for each observer — the epithet for a stranger, "you" for the
body it belongs to. Handed the epithet instead of the name, it had nothing to
translate. Traced through one turn: resolve 8 occurrences → `perception_outcome`
23 → narrator prose 1. In `mix2` the player's own view carried

> The person of unremarkable appearance shifts weight to one side, eyes
> settling on the sword at **the apprentice's** hip.

— the player reading about himself in the third person, described by a label
that exists only because other people do not know who he is.

### The fix: the composer knows the string, because it minted it

`agents/common.self_reference_forms` is the other half of `self_name_forms`.
`self_name_forms` answers "what does prose call this mind by NAME";
`self_reference_forms` answers "what descriptors did the engine ITSELF put
into circulation for this body", and both feed the same
`_self_second_person`, which was already rewriting a perceiver's own name into
"you" in every view. It returns:

- the exact minted label(s): the base `_unknown_actor_label` descriptor, plus
  whatever the caller actually minted this beat (a widened or
  ordinal-distinguished variant, via `perception._joint_stranger_labels`);
- ONE short definite form cut from the label's head noun — "the apprentice" —
  because prose shortens a long descriptor on second mention, and that is the
  form that actually reached the player.

It is a floor under the problem whatever the Director writes next, which is
the point: a leak (or, here, a framing error) is an engine failure, never a
model's.

### Three guards, and why each is there

- **`avoid`** — every label this observer is currently using for OTHER bodies.
  Any form colliding with one is dropped outright. Two strangers who look
  alike share a descriptor, and rewriting a reference to one of them into
  "you" would tell a mind it did something somebody else did. Under-matching
  costs one clumsy sentence; over-matching invents an act.
- **`_GENERIC_LABEL_HEADS`** — "the person of unremarkable appearance" must
  never yield "the person". That is the word every stranger label is built
  from, not a shortening of one body's descriptor.
- **No indefinite variant.** "A young smith's apprentice" is how prose
  INTRODUCES a body nobody has met; matching it would reach for referents this
  cannot check.

### Where it is applied — two delivery sites, one policy

The rule is not "wherever the epithet appears" but *wherever engine-written
prose is handed to the mind it is about*:

- `agents/perception.py` (`_composer_self_forms`), feeding
  `composer.act_percept`'s existing `self_forms` in both `perception_act` and
  `perception_outcome` — so it lands at ADMISSION, before the percept exists,
  the same discipline `_composer_scrub_surface` follows.
- `agents/narration.py` (`_ordered_beat_events`), because `event_order` is a
  SECOND delivery of this beat's prose to the player — the cast's own
  `observable` surfaces, written in the third person by minds that refer to
  the player by epithet. That is not narrator compensation; it is the same
  floor at a second door.

### And a note back to the Director

`agents/director._report_observer_epithets` reports (`tell_director` +
`ctx.add_warning`) when the objective record refers to a body by the label
perception mints for strangers. Report-only: it never rewrites the account.
It exists for the cost the prose floor CANNOT reach — `intended_target` on
both of Bryn's lines read `"young smith's apprentice"` rather than `"Corin"`,
and `intended_target` is matched against canonical names, so a line addressed
by epithet is addressed to nobody. It stays quiet when the descriptor is
shared by two bodies in the scene, because then it may honestly be describing
someone unregistered.

## Defect 2 — a disambiguation INDEX in prose-facing view text

The player's own view contained, verbatim:

> The person of unremarkable appearance is within arm's reach, the person of
> unremarkable appearance **(2)** is within arm's reach, and the person of
> unremarkable appearance **(3)** …

`(2)`/`(3)` was `assign_stranger_labels`' last resort when two bodies'
appearances genuinely cannot distinguish them. It is an ENGINE device, and
Layer B renders PROSE. One narrator copied it onto the page ("The person of
unremarkable appearance (2) speaks in a flat, appraising voice"); another
paraphrased it away. Neither misbehaved — the view contained it.

**The distinguisher is now ordinal language** (`composer._ordinal_label`):
"the second person of unremarkable appearance". The reasoning, since the
choice is the interesting part:

- **An ordinal distinguishes by nothing the observer has not already got.**
  They can see three bodies; counting them adds no attribute, no history and
  no identity. Two bodies that look identical stay described identically apart
  from the count, so the firewall constraint — *nothing here may give an
  observer a distinction they have not earned* — is met by construction
  rather than by argument.
- **Position and posture read better in one sentence and were rejected.**
  They change within the beat, so the same stranger would stop being the same
  stranger across sentences; and they are separately admitted percepts, so
  folding them into the referring expression would restate them in sentences
  whose channel never carried them. A referring expression must be stable
  while the thing it refers to moves.
- **Stability is unchanged from the index it replaces.** The assignment is a
  pure function of the body list, so it is fixed within a beat; across beats
  it moves exactly when the set of bodies moves, as `(2)` did.
- Ordinal WORDS stop at twelfth; past that a numeral ("the 14th person of…")
  is still prose rather than an engine device, and past twelve identical
  strangers the honest reading is "a crowd".

An appearance that CAN distinguish still wins: the widening ladder
(caps 6/8/10/14) is untouched and the ordinal remains the last resort.

## Defect 3 — narration person was asked for and never verified

`_narration_person_counts` was called in exactly one place — on the PLAYER's
raw input, to decide `narration_person`. The narrator was then told "PERSON
DISCIPLINE: ONLY the player character is 'I'/'me'/'my'" and nothing read the
prose that came back. `_check_player_person` catches the player being NAMED;
nothing caught the draft being written in the wrong person outright.

`agents/common._check_narration_person_match` runs the SAME detector over the
output — reused, not re-implemented, because it already strips quoted dialogue
and folds unterminated quotes, which is the hard part. Two narrowings:

- third-person evidence from the player's NAME only (`player_pronouns` is not
  passed): every other body on the page is legitimately "he"/"she"/"they", and
  the player's own pronouns are routinely the same words;
- the dominant person must lead the declared one by 2 — the same hysteresis
  margin `_resolve_narration_person` uses, for the same reason.

**Measured before shipping** (AGENTS.md's rule for any new narrator warning):
2,303 stored narrator drafts, each scored against the person replayed from
that turn's own input rather than the chat's final stored value — **12
warnings, 0.52%**, and every one is a real disagreement (prose reading "Your
words land in the corridor's flat hum" on a turn whose person resolved to
`first`). It is a WARNING and deliberately NOT in `_ENFORCEABLE_PREFIXES`: a
rewrite costs a whole narrator call, and person is a whole-draft property a
correction note cannot patch locally.

**Its limit, stated in the code as well as here: it would NOT have caught
defect 1.** The offending phrase was an epithet, not a name or a pronoun, so
it is invisible to every person detector. It is a backstop for genuine model
non-compliance, not a fix for bad input.

## Rejected

- **Fixing defect 1 in the narrator** (rewriting the prose that comes back):
  the data is wrong before it gets there, and the view is wrong even when the
  narrator handles it gracefully. CLAUDE.md's own rule.
- **Rewriting `resolved_event` at the Director boundary.** The resolve
  reconciliation seam's contract is explicit that the prose is the account
  being reconciled against, not the thing under repair. The note back to the
  Director is report-only for the same reason.
- **Canonicalising `intended_target` from the epithet.** It would fix a real
  hole (see UNBUILT §), but `_addresses` feeds an ADMISSION decision —
  `line_hear_level`'s addressed-audibility rescue — and loosening an admission
  gate on a string match is the wrong direction to take without measuring
  first. Left as a known gap rather than closed by guess.
- **A synonym or head-noun table for epithets.** The short form is cut
  structurally (the label's own last word, guarded three ways); a vocabulary
  would have to be extended by hand for every appearance an author writes.
