# DESIGN_OFFSCREEN_MIND_MODELS — does a mind's theory of other minds travel off screen?

Status: **Built.** `agent_context` carries `mind_models` as the derived view
(decay-applied, claim + current confidence, frame-masked); the raw ledger
never travels. Pinned by `tests/test_offscreen_agent_context.py`
(`TestItsOwnTheoryOfOtherMindsTravels`).

Audience: whoever next wants to add a key to `AGENT_CONTEXT_KEYS`
(`world/offscreen.py`), and whoever is tempted to re-raise this question.
The answer matters less than the rule this note extracts, which is stated
first so it cannot be buried:

> **The allowlist bounds CHANNELS, not volume. The question for any candidate
> key is never "how much does this tell the mind" — it is "who wrote this
> field, from what inputs, and does handing it back open a path between two
> heads that the fiction says are separate."** A field whose only writer is
> the mind's own firewalled turns is the mind's own state, and excluding it
> is not caution; it is making a mind conclude less than its own evidence
> supports, which is the one repair the firewall's doctrine names as wrong
> (`Design.md` § What the firewall is; `AGENTS.md` § Information boundaries,
> consequence 1).

---

## 1. The question, and where it came from

Commit `92ee2a8` repaired the `beliefs` entry of `agent_context` — the
fail-closed allowlist the paid `character_agent` rung rests on — which had
read `state["beliefs"]` while the only writer puts beliefs at
`state["interior"]["beliefs"]`. Every absent mind the engine ever paid to
think had gone in believing nothing. The same commit found
`state["mind_models"]` — the mind's own theory of other minds — was not on
the list at all, and left that as an open question in a comment, because
adding a key to the one fail-closed allowlist in the engine is a widening
rather than a repair.

The naive yes ("a mind should carry what it believes about people") and the
naive no ("a model of another mind is where a false belief lives, so it is
where a leak would be most costly") both dissolve on contact with what
`mind_models` actually is. So: what it actually is, first.

## 2. What `mind_models` actually is

**Provenance.** The ledger has exactly one writer:
`theory_of_mind.apply_mind_model_updates`, called on the commit path
(`persist/commit_memory.py`) with the `mind_model_updates` the character's
own ON-SCREEN call emitted — a call whose payload was already firewalled by
perception. Deterministic code then caps each hypothesis by kind
(`identity` can never exceed 0.35 raw), blends reinforcement by plasticity,
explains competing claims away rather than erasing them, decays the
unreinforced on Ebbinghaus curves, and prunes below the floor. Nothing in
the pipeline writes another mind's actual state into it. Place claims are
re-keyed onto place entities (`rekey_place_claims`), so the ledger holds
this mind's theories of people, places, and things — all earned the same
way.

**Not "another mind's state".** The allowlist's roadmap exclusion "no other
mind's state" does not cover this field, and the distinction is the whole
question: a mind model is *this* mind's state ABOUT another mind. The other
mind's actual interior never appears in it and cannot — there is no code
path from B's state into A's ledger. The distance between the model and the
person stays real precisely because the model can be wrong.

**Measured, live corpus, 2026-08-18 (read-only).** 72 of 100 `chat_chars`
rows carry a non-empty `mind_models`; 1,148 hypotheses in total; kinds:
goal 414, trait 248, emotion 196, observation 170, stated_fact 66,
identity 48, second_order 6. Two findings from reading them settle the two
halves of the question:

1. **The `beliefs` repair did not answer this.** `interior.beliefs` holds
   self- and world-directed convictions ("I must keep running", "there is
   always a clever way out"). Convictions about *people* — "Auditor Rennick
   is looking to assign blame", "Vrenak may be able to observe Picard's
   movements via the open channel" — live only in `mind_models`. The wary
   gate-keeper that `92ee2a8`'s own commit message reached for (one who
   believes the auditor is out for blame behaves differently from one who
   believes nothing) is a `mind_models` case, not a `beliefs` case. With the
   ledger excluded, the most decision-relevant social state a mind owns was
   still absent from the most expensive tick the engine buys.

2. **The ledger already respects disguise and identity boundaries,** because
   it was written under them. The same holder carries separate models keyed
   `"Hinami"` and `"fox_eared_woman"` depending on what each frame of the
   story had legitimately yielded; a holder who never learned the name holds
   only the description key. The field does not need to be filtered into
   honesty on the way out — it was built honest.

## 3. The argument

**The firewall restricts flow between minds. This is not a flow between
minds.** Handing a mind its own ledger back is the same act as handing it
its own memories, beliefs, and plans — all already on the list. Refusing it
is not a smaller payload; it is a mind whose own evidence about people is
confiscated whenever the player looks away.

**The generative-gap worry points the other way.** The gap the firewall
keeps is the gap *between* A's model of B and B's actual state — and that
gap is untouched here, because only A's side travels. What excluding the
ledger destroys is exactly the generativity the gap exists for: deception
and dramatic irony require a false belief to be *acted on*, and off screen
is where characters act unobserved. A rival who believes the player trusts
her cannot scheme while absent; a gate-keeper who believes the gate holds
cannot be wrong about it. Every one of those is the product, and every one
needs the model to arrive.

**The rung's own trigger demands it.** `full_agent_candidates` selects a
mind for a paid tick on two grounds: an active plan, or a fresh carried
report. A carried report is usually *about someone* ("a stranger barred the
gate"). A mind asked to act on a report about a person, with no access to
its own model of that person, under-concludes on its own evidence — the
precise failure mode consequence 1 forbids engineering.

## 4. Why the answer is not a clean yes — the three subtractions

The yes is conditional on shape, and the shape is where the firewall lives.

**(a) The derived view travels, never the raw ledger.** What crosses is
`mind_models_for_payload` output — per subject, per kind, the leading claim
and up to two live competitors, each as `{claim, confidence}` only. The raw
hypothesis records carry `first_seen_turn`, `last_updated_turn`,
`formed_under` (absorption bookkeeping) — engine instrumentation, not lived
knowledge. A mind that could read when the engine formed its belief, or
under what absorption cap, would be reading the engine rather than the
world: the same rule that keeps `importance` and `tier` out of this
context. Pinned: no bookkeeping key appears anywhere in the context blob.

**(b) The same function as on-screen, deliberately.** The `beliefs` defect
survived for the field's whole life because the reader and the writer held
two shapes of one field and a test was written in the reader's shape. One
derivation (`mind_models_for_payload`, shared with `agents/character.py`)
means the off-screen view cannot drift from the on-screen one without both
breaking at once.

**(c) Decay is applied at the moment of reading, and the frame mask rides
along.** An off-screen tick is exactly the moment the most simulation time
has passed, so a raw confidence would hand the mind its conviction at the
peak it once held rather than as it stands now — resurrecting beliefs the
merge had explained away or time had faded. And the on-screen step's
`nonexistent_cast` recognition backstop (`is_recognized_in_frame`, checked
against every attached character, dormant included) applies at this
boundary too: in a frame where a cast member does not yet exist, a native's
ledger must not hand back a model keyed to that identity, while a
stranger-shaped key ("the fox woman") rides as itself. Without (c) the
off-screen path would have been the one reader of `mind_models` without the
mask.

One nuance the tests document: the existing guard
`test_nothing_about_the_player_reaches_it` still holds — the *player's*
position, action, and turn feed cannot reach the context, structurally. But
a mind's own model keyed `"player"` travels, because it is the mind's own
state. Those are different directions of flow, and conflating them is how
this question gets re-raised.

## 5. Shapes considered and rejected

- **"Only models of parties present with them."** Inverts the rung's
  purpose — an absent mind acts *toward* people who are elsewhere — and is
  unimplementable without sin: filtering by presence requires reading the
  objective scene, which `agent_context` structurally cannot receive. The
  restriction would itself be the leak.
- **"Credence without content."** A confidence with no claim is not
  actionable by anything; the claim is the conclusion, and inference is the
  product. This subtraction protects nothing (the content never crosses a
  mind boundary) while deleting the capability.
- **"No."** Answered by §3. The cost is measured, not hypothetical: every
  paid tick in the corpus ran without the holder's models of the very
  people its carried reports were about.
- **`active_hypotheses` is deliberately NOT added.** The stable hypothesis
  sheet is an attention-pacing device for on-screen beats (capacity shrinks
  with absorption, hysteresis prevents churn). The derived view already
  carries everything it selects from. Adding it is a separate widening with
  its own argument, and this note is not that argument.

## 6. What would legitimately reopen this

- **If the off-screen tick starts WRITING mind-model updates.** Today the
  proposal schema is `{attempt, toward, plan_op, plan_id}` — the rung reads
  the ledger and writes only a deterministic autobiographical memory. A
  tick that emitted `mind_model_updates` would be forming theories about
  people from material the mind did not witness during the gap, and that
  is a genuinely different question (the write side is where breaches
  live — `AGENTS.md` § Information boundaries, final paragraph).
- **If `mind_models` ever gains a second writer** that is not the mind's
  own firewalled output — e.g. an authored seeding path, or any code that
  copies one character's state into another's ledger. The premise of §3 is
  single-writer provenance; break it and the field stops being "their own".

Neither is pending. Absent one of them, the answer stands: a mind's own
ledger is not a channel, and the allowlist has no business confiscating it.
