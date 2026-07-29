# Design: comfort from surfaces

**Status:** built — `comfort.py` (derivation), `resolve_hedonic`'s
`ambient_comfort` argument (`psychology_runtime.py`), the `tick_vitals` rest
derivation (`survival.py`), wired at the single hedonic call site in
`commit.py`; pinned by `tests/test_surface_comfort.py`. Independent of the
place graph, but its most interesting effect (a remembered warm corner) only
exists once place purpose does — see §5, still not built; `rest_affording`
is the seam its future writer should read.

Two implementation deviations from §1 as written, both deliberate: the
`relief` multiplier (and `pleasure_sensitivity`) apply *under* an absolute
0.3 ceiling rather than on top of it — the uncapped formula would let a
spent sybarite reach 0.54, breaking §4's absorption promise — and
`comfort_level` returns `(level, source)` so the habituation key and the
prompt-visible source string are the same fact.

Sitting on a cushioned bench, lying on a bed, standing by a hearth should give a
small pleasure. Not an event; a background ease that makes a body feel better
than it did standing in a corridor.

The engine already has the machinery. `resolve_hedonic`
(`psychology_runtime.py:49`) carries bounded pain and pleasure, integrates
sustained pleasure into a `charge` that demands resolution, and feeds
`cognitive_absorption` (`psychology_runtime.py:326`). What it lacks is any way
for the *world* to contribute pleasure: pain has a deterministic floor —

```python
proposed_pain = max(proposed_pain, injury * 0.8, (1 - air) * 0.75)
```

— and pleasure has no symmetric counterpart. Pleasure enters only if the model
proposes `somatic_impact.pleasure` with a concrete `why`. So a character on a
featherbed feels exactly what a character on flagstones feels, unless the model
happens to mention it.

---

## 1. Mechanism

A new `comfort_level(scene, name) -> 0.0..0.3`, derived from what the body is
verifiably doing: station `at` an anchor or `near` an entity whose kind or
description matches a comfort lexicon (bed, couch, cushioned, hearth, fur, warm
spring), scaled by posture where `scene.contacts` and entity state distinguish
lying > sitting > standing-near.

Then, mirroring the pain floor:

```python
proposed_pleasure = max(proposed_pleasure, ambient_comfort * relief)
relief = 1.0 + 0.8 * fatigue        # fatigue = 1 - stamina, or 0 if no vitals
```

A chair is worth more to a spent body. That is hedonically true, and it is what
makes *"sank gratefully onto the bench"* emerge from state rather than from an
author deciding it would be a nice line.

---

## 2. Two hard rules

These are not tuning parameters. Without either one, the feature is harmful.

### Rule 1 — comfort never feeds `charge`

`resolve_hedonic` currently computes `drive = max(proposed_pleasure,
proposed_pain * 0.5)` (`psychology_runtime.py:108`), integrating *any* pleasure
into an unresolved-drive term. Ambient comfort must be added to the **level**
after the charge computation — pass it as a separate `ambient_comfort=`
argument and compute `drive` from the appraisal-proposed value only.

Comfort is a resolved, self-limiting state. It is the opposite of a drive
demanding release. Letting it accumulate charge would manufacture `saturated`
bodies out of sitting quietly, and a saturated body holds
`cognitive_absorption` at the `_ABSORPTION_SATURATED_FLOOR` of 0.45
(`psychology_runtime.py:323`) — which is the couch literally eating the mind.

**Regression test:** `charge` is invariant under pure ambient comfort. Assert it
directly, because a future refactor that folds the argument back into `drive`
would reintroduce this silently.

### Rule 2 — habituation

Track `hedonic.comfort_beats` inside the already-persisted hedonic dict — no new
state surface. Consecutive beats with the same comfort source halve the
contribution every ~4 psych units, floored near 0.05.

Sensation adapts. The tenth beat on the cushion is barely felt. This is the
primary anti-attractor and it is deterministic rather than hoped for.

---

## 3. Interaction with what exists

**Stress.** Pleasure already damps chronic `load` accumulation (`resolve_stress`,
`psychology_runtime.py:191`), so hearthside comfort quietly aids stress recovery
with no new code at all.

**Rest.** Derive `tick_vitals`' resting set from posture: a body lying on a
rest-affording surface gets `_REST_STAMINA_PER_HOUR` (`survival.py:94`) without
the Director having to remember to declare it. This closes a real existing gap —
rest currently only works when a model thinks to say the word.

**Interoceptive sensitivity.** A character with low `pleasure_sensitivity` has
proposed pleasure damped (`psychology_runtime.py:79-83`). The ambient floor as
written bypasses that scaling, which would make a stoic and a sybarite feel the
same bench. **It must pass through the same sensitivity multiplier.**

---

## 4. What stops it dominating behaviour

Stated explicitly, because "a character who never leaves the couch" is the
obvious failure and hand-waving it is not a design:

1. **Habituation** drives marginal pleasure toward ~0.05 while hunger and
   stamina keep draining and untried exits keep their verdict pull.
2. **Exclusion from `charge`** means no accumulating pressure to stay.
3. **The 0.3 ceiling** puts absorption at roughly `0.3^1.3 ≈ 0.21` — well below
   anything that erodes cognition, since `absorbed_cap` erosion is proportional
   (`theory_of_mind.py:584`). A comfortable character still thinks clearly.
4. **Comfort never writes a want.** Wants derive from drive and intentions
   (`prompts.py:759`). Comfort reaches the model only as a low hedonic level
   with a source string.
5. **`max()` composition** means comfort never stacks on top of real stimuli.

The residual risk is not mechanical but rhetorical — see below.

---

## 5. The interesting effect, and why it must go the long way round

A genuinely restful stay — sustained comfort plus stamina recovery, both
deterministic and both own-body — should write `affords.rest {basis:
witnessed}` onto the place-graph node. Later fatigue surfaces that node through
`recalled_places`, and the character decides whether to go.

That is the firewall-correct route for *the cat returns to the warm spot*: the
pull is a **remembered fact surfaced at need, mediated by a decision**, never a
gradient in the hedonic engine. Comfort must not create navigational pull
directly.

It also degrades gracefully into fiction. A character can remember the hearth
and be unable to reach it, which is a story. A gradient would just be a slope.

---

## 6. Risks

**Charge contamination** — the catastrophic version, excluded by construction in
Rule 1, but only for as long as the argument stays out of the `drive` term.

**Model dramatisation.** The model sees `pleasure: 0.08, source: "the cushioned
bench"` and writes a paragraph of luxuriating every beat. The number is bounded;
the prose is not. Needs one line in the character prompt's PAIN AND PLEASURE
section: ambient comfort at low levels is background, not an event, and
habituated comfort is not worth a tell.

**Survival-off stories** have no fatigue term, so `relief` collapses to 1.0 and
comfort goes flat. Acceptable. **Do not** backfill a fake fatigue estimate from
beat counts — that would be inventing a body the story deliberately turned off.

**Lexicon creep.** The comfort lexicon has the same failure mode as the place
purpose one: it will want to grow until it is an unversioned ontology of
furniture. Keep it small and generic; anything story-specific belongs in
authored lore.

---

## 7. Experiment that would settle it

Property test: a body parked on a bed for 30 beats ends with **stamina up,
`charge` unchanged, absorption below 0.25, and at least one departure-capable
want intact.** If any of those four fails, the anti-attractor design is wrong
and no amount of constant-tweaking fixes it.
