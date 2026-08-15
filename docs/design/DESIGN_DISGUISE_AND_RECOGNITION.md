# Disguise and recognition

**Status:** floors built 2026-08-15. The graded half is designed, not built —
see §5. Registered in [`../UNBUILT.md`](../UNBUILT.md) §1.

Two questions live under one word, and collapsing them is what produced every
defect in this area:

| question | kind of question | answered by |
|---|---|---|
| what does an observer SEE of this body | perception | the disguise's presented form, delivered to everyone |
| does an observer know WHO they are looking at | inference | recognition, which the disguise may or may not touch |

The engine already separated seeing from knowing — `_subject_disguise_context`
says so in as many words, and has since it was written: *every* observer
visually perceives the outward form, and being in `known_to` grants the truth
as knowledge rather than as sight. What was collapsed is the second row.
Identity was treated as a thing a disguise always concealed.

## 1. A disguise conceals features

The rule was that any active disguise severed the name for anyone not in
`known_to`, however well they knew the person. That makes every disguise a
perfect identity mask, which is wrong about most disguises: something that
hides an added feature does not touch a face, and a person who knows that face
still knows it — now attached to something unfamiliar.

The observable failure was a view contradicting itself inside one paragraph:
the subject's **name** three times from the proximity and pose lines, and a
stranger's **descriptor** once from the appearance line. The disguise leaked
the identity and showed the false body — the worst of both.

`conceals_identity` now carries the distinction: true when the disguise covers
what a body is recognised *by* (face, build, bearing, voice), false when it
covers something else. `scene.disguise_breaks_recognition` is the single rule;
the three sites that used to share the idiom by copy now call it.

**Defaulting to recognition surviving is deliberate**, and follows the
firewall's own statement rather than contradicting it: *inference is the
product, not the risk*, and a guard must not make a mind conclude less than
its senses support. The cost is that a disguise which genuinely should hide
who you are must now say so. The benefit is that it can — and can be told
apart from one that never meant to.

## 2. Knowledge accumulates; appearance does not

`known_to` is not a property of a row. It is a fact about people, and a
superseded row does not un-tell them. Two rules now hold it:

- the **write** side inherits it forward when a superseding row is silent
  (silence is not the same as an authored empty list — the same trap
  `psychology.capacity` documents);
- the **read** side unions it across every active row, because branching is
  how duplicate rows actually arrive. A branch copies conditions wholesale
  with no write, so the supersession rule never runs on them.

## 3. One outward form

`physical_disguise` and `physical_transformation` are a singular **group**, not
two singular kinds. Scoping supersession to one kind let a body be disguised
and transformed at once — which is how a dropped glamour survived its own
undoing, the transformation landing beside three live disguises instead of
ending them.

## 4. A presented appearance may only say what is seen

Stating an absence hands the observer the category. `conceal_disguised_parts`
met this from the other side — a negation was reading as a mention and granting
concealed parts back — and fixed the mechanical half. The epistemic half is
now closed too: clauses that both negate and name something concealed are
dropped before delivery, and only those, because a glamour over a feature *is*
a description of that feature.

## 5. What is not built: the graded half

`conceals_identity` is a boolean, and the real question is graded:

- **coverage vs familiarity.** Does what this disguise covers overlap what
  *this* observer knows the subject by? A stranger and a spouse are not
  equally fooled by the same hood.
- **circumstantial defeat.** The hood blows back, the illusion falters in
  rain, someone takes hold of the concealed feature. `contact` and `spatial`
  both hold facts that bear on this and neither is consulted.
- **witnessing grants knowledge.** Watching a disguise go on or come off
  should add the witness to `known_to` without anyone declaring it. This is
  deterministic — perception already knows exactly who received the beat —
  and is the highest-value unbuilt item here.

### Why this is a ladder, not a seventh specialist

The obvious shape is a `disguise` specialist beside the six. It is the wrong
one, for a reason worth writing down:

**recognition is a per-observer question, and the Director emits one diff for
everybody.** A specialist would produce a single verdict for the whole room —
which is the binary `known_to` that already exists, bought with an extra model
call.

Every other per-observer perceptual question in this engine is answered
deterministically over typed data: `hear_level`, `region_visibility`,
`visual_level_between`, scent, containment, darkness. Perception calls no model
at all, by design (design note 00). Recognition is the same shape of question,
and making it the one that needs a model would be the odd one out.

So the split is: the **body** specialist authors what the disguise presents and
covers — a body fact, in a channel it already owns; **social** should own
`known_to`, which is a fact about who has been told and is currently written by
the specialist least equipped to reason about it; and the verdict is a
deterministic ladder in perception.

**What would change the answer.** If, after the ladder exists, there is a
recurring judgement it cannot express — one that needs weighing rather than
comparing — that is when a call earns its place. Not before.
