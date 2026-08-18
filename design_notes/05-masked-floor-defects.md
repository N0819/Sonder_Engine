# Masked floor defects: where the prompt states a rule the code does not implement

Defect class under audit: the perception system prompt (`prompts.py:571-919`)
states a rule correctly, the model applies it, and the deterministic floor
underneath does NOT implement it — so the gap is invisible in play (the model
compensates) and already live wherever code runs without a model
(`deterministic_micro_perception`, the two dialogue-injection floors, the
outcome action backstop, background hearing). Under the zero-LLM design every
one of these becomes a live information leak or a hole in perception.

Method: every threshold, tier, absolute exclusion, and enum in the perception
prompt was enumerated and traced to the code that should implement it
(`world/spatial.py`, `agents/perception.py`, `agents/common.py`, `agents/loops.py`,
`agents/background.py`). Every finding cites both halves — prompt line and
code line. "Confirmed" means confirmed by reading the code end-to-end;
"suspected" means a test is needed. Corpus figures are aggregates from the
read-only snapshot (`mode=ro`), no story content.

Corpus context (64 scenes, 7,668 variant rows carrying `volume`):
volumes `normal` 22,081 / `mutter` 1,364 / `loud` 497 / **`whisper` 391** /
`shout` 95; room sizes `""` 199 / `small` 108 / `large` 101 / `medium` 8 /
huge+vast **0**; scenes with `stations` 17/64, with `orientation` 42/64, with
a set `focus` 41/64; scenes with a `contained` ledger 7/64, with
body/entity-parented interior rooms **36/64**.

---

## A. Confirmed leaks (over-grant — information crosses a gap it has no channel through)

### L1. `whisper` is delivered FULL to every same-room perceiver at any distance

The quietest volume outranks the second-quietest.

- Prompt: `prompts.py:880` — "whisper: ONLY same-room perceivers in close
  proximity." Also `prompts.py:686-688` (within_reach = "close enough to …
  murmur to").
- Code: `spatial.py:1039-1044` — the same-room branch of `hear_level` tests
  only `volume == "mutter"` for the proximity downgrade; `whisper` falls
  through to `return "full"` at any proximity, including `across`. (The
  enclosure branches at `spatial.py:1010` and `:1032` handle the pair
  `("mutter", "whisper")` correctly, so the same-room branch is the one that
  forgot the second member.)
- Every path is affected: micro-loop (`agents/loops.py:111`), onset injection
  floor (`agents/perception.py:1257-1260`), outcome injection floor
  (`agents/perception.py:3838`), background hearing
  (`agents/background.py:152-155`, `:431`), `_delivery_ok` hearing
  (`agents/common.py:2208`).
- **The floors actively defeat a correct model.** The injection floors re-add
  a quoted line whenever `hear_level` != "none" and the quote is absent from
  the view (`agents/perception.py:1272` onward; `:3842`). A model that
  correctly withheld a whisper from an across-the-room perceiver has the
  verbatim line re-injected by the engine at zero temperature.
- Live exposure: 391 whispered lines in the corpus.
- Severity: leak. Regression assertion: `hear_level({'same_room': True},
  'whisper', proximity='across') == 'none'`, and at every proximity tier
  whisper is ≤ mutter.

### L2. The enclosure direction flags are set by a function nothing in production calls — both `hear_level` enclosure guards CANNOT fire

- Prompt: `prompts.py:727-738` (scent of a body sealed inside another arrives
  muffled at best, never unfiltered), `prompts.py:820-827` (an enclosed body
  perceives only its enclosure; the enclosing body perceives its contents by
  touch alone). `AGENTS.md:168-179` (conducted hearing: `inside_source` →
  full; the three directions).
- Code: `spatial.spatial_rel_between` (`spatial.py:729-781`) is the ONLY
  setter of `enclosed_from_source` (`:757`) and `source_enclosed` (`:780`) —
  and it has **zero non-test callers** (verified by repo-wide grep; only
  `tests/test_parented_room_concealment.py`, `tests/test_subject_identity.py`
  exercise it). Production rels are built by `spatial_rel` +
  ad-hoc enrichment: `_source_channels` sets only `inside_source` + `concealed`
  (`agents/perception.py:1549-1568`); the onset perceiver build sets only
  `crossing` + `concealed` (`agents/perception.py:2648-2658`); the micro-loop
  sets nothing (`agents/loops.py:78`).
- Consequences, all confirmed by tracing the rel through:
  1. **A voice sealed inside a body reaches the whole room at full clarity.**
     A contained body's position derives to its carrier's room, so the rel is
     `same_room: True` (+ `concealed`, which `hear_level` never reads —
     `spatial.py:988-1107` has no `concealed` branch). `hear_level` →
     `"full"`. The guard written for exactly this — `source_enclosed` →
     none/fragment, `spatial.py:1031-1032`, whose own comment describes the
     measured live failure — cannot fire. Both injection floors deliver the
     verbatim quote (`agents/perception.py:1257`, `:3838`).
  2. **A perceiver sealed inside a body hears the whole room at full
     clarity.** Same rel shape; the `enclosed_from_source` guard
     (`spatial.py:1023-1024`, "a window latch rattling across the room at
     full clarity", measured live) cannot fire.
  3. **Scent misgrades in both directions on every production path.**
     `scent_level` (`spatial.py:273-278`): `enclosed_from_source` → "none"
     never fires (perceiver sealed in a body still gets "muffled" scent of
     the room beyond — the exact one-symmetric-flag bug the docstring at
     `spatial.py:250-262` says was fixed); on the ONSET path `inside_source`
     is also never set (`agents/perception.py:2676` builds from the bare
     rel), so a perceiver inside a body gets "muffled" for the one body that
     should drown out everything ("full").
- Live exposure: 7 scenes carry a `contained` ledger; 36 carry parented
  interior rooms.
- Severity: leak (1 and 2), plus paired under-grants. This is the purest
  instance of AGENTS.md invariant 4: the guard that cannot fire. Regression
  assertions: with a `contained` ledger sealing B inside A, (a) a `normal`
  line spoken by B arrives at a bystander in A's room at ≤ "fragment" through
  the production channel-building path (not by calling `spatial_rel_between`
  directly); (b) a `normal` line spoken by the bystander arrives at B as
  "none"; (c) `scent_channel` from bystander to B is "none" and from A to B
  is "full".

### L3. The outcome dialogue floor ignores proximity — a mutter crosses a great hall at full clarity

- Prompt: `prompts.py:688-690` — "'across' … a MUTTER to them does not
  carry"; `prompts.py:881`.
- Code: `_dialogue_hear_level` (`agents/perception.py:287-315`) has no
  proximity parameter and calls `hear_level(rel, volume)` bare; its one call
  site on the outcome pass (`agents/perception.py:3838`) therefore never
  applies the downgrade that the ONSET floor applies two hundred lines away
  (`agents/perception.py:1257-1260` passes
  `proximity=perceiver.get("proximity_to_actor")`). With `proximity=None`,
  `hear_level`'s same-room branch returns "full" for mutter
  (`spatial.py:1037-1044`, deliberate pre-Phase-2 fallback).
- Two floors implementing one rule differently — the defining shape of this
  class. Background hearing (`agents/background.py:152-155`, `:431`) has the
  same bare call.
- Live exposure: 1,364 muttered lines.
- Severity: leak (verbatim full quote where the spec says nothing arrives).
  Regression assertion: an NPC `mutter` in the dialogue_log, with speaker and
  perceiver at distinct anchors of a `size: "large"` room, is not delivered
  full by the outcome injection floor.

### L4. Dazed minds get clean, full-fidelity content from every deterministic path

- Prompt: `prompts.py:865-875` — dazed degrades EVERYTHING to periphery
  fidelity; "even a dazed mind never gets clean semantic content."
- Code: the only deterministic awareness gate is `NON_AWAKE_GATED`
  (`scene.py:457` = asleep/sedated/unconscious). `_delivery_ok` checks
  exactly that (`agents/common.py:2200-2201`), so the micro-loop delivers
  verbatim quotes and full observable sentences to a dazed observer
  (`agents/loops.py:106-137`) — and those additions flow into subsequent
  character steps, outcome views, and durable memory. The outcome injection
  loop skips only NON_AWAKE perceivers (`agents/perception.py:3717-3731`);
  there is no dazed branch, so the floor re-injects the verbatim line into
  the degraded view the model wrote ("level == full and quote absent" is
  precisely the state a correctly-degraded dazed view is in).
- Severity: leak (the floor defeats the model's correct degradation, and the
  no-model path never degrades at all). Regression assertion: a perceiver
  with awareness `dazed` receives no verbatim quoted line from
  `deterministic_micro_perception` or the outcome injection floor.

### L5. Graded sight is collapsed to a boolean in deterministic delivery — identity and fine detail at silhouette fidelity

- Prompt: `prompts.py:670-679` (periphery: no foveal detail, no fine motor
  detail); the engine's own tier definition — `spatial.py:620` "dim:
  movement, outline, bulk — not faces, not detail", `spatial.py:632` "enough
  to know someone is there and not enough to know who".
- Code: `_delivery_ok`'s sight/action branch is `bool(has_visual(relation))`
  (`agents/common.py:2214`) — its own cross-seam comment claims the
  micro-loop previously "skipped … graded sight", but the consolidated gate
  is still binary. `sight_level` "shapes" → delivered as if "full". The
  micro-loop then attributes the act to the actor's recognized NAME
  (`agents/loops.py:73-76`) and delivers the complete observable sentence
  (`:133-136`) — identity plus fine detail through a channel that carries an
  outline. No deterministic path degrades by proximity tier `across`, by
  `focus_target` periphery, or to "shapes" fidelity at all.
- Severity: leak in the deterministic floor (identity through a
  shapes-grade channel); the model path receives graded fields and is asked
  to degrade. Regression assertion: in a `dim` room,
  `deterministic_micro_perception` does not attribute an action to the
  actor's canonical name.

### L6. Adjacent-room sight is graded by the light in the wrong room

- Prompt/spec: `prompts.py:592-593` (sight through open barriers "if
  line-of-sight"); `spatial.py:855-857`'s own contract — "The light in the
  room being LOOKED AT: seeing into a dark room from a lit one is still
  seeing nothing."
- Code: `spatial_rel(scene, a_room, b_room)` stamps
  `light: effective_light(scene, b_room)` (`spatial.py:857`) — the SECOND
  argument. The onset perceiver build calls `spatial_rel(sc, p_room, r)` with
  the ACTOR first and the perceiver second (`agents/perception.py:2644`),
  then `visual_channel_to_actor = has_visual(rel)` (`:2675`); the micro-loop
  does the same (`agents/loops.py:78` → `_delivery_ok` →
  `has_visual`, `agents/common.py:2214`). So sight OF the actor is graded by
  the light in the OBSERVER's room: an actor standing in a dark adjacent
  room, watched from a lit room through a `window`/`open_door`, yields
  `visual_channel_to_actor = True` (leak); the reverse (lit actor, dark
  observer) yields False (under-grant). `visual_level_between`
  (`spatial.py:784-803`) answers correctly via `light_at(target)` — the
  outcome path uses it (`agents/perception.py:1487`), the onset and micro
  paths do not: two paths, one rule, different answers.
- Live exposure: 39 `dim` + 3 `dark` rooms in the corpus.
- Severity: leak in one direction, blindness in the other. Regression
  assertion: with actor in a `dark` room adjacent via `open_door` to a
  perceiver's `lit` room, the onset perceiver entry carries
  `visual_channel_to_actor` False (or "shapes"-grade), and the micro-loop
  does not deliver the observable.

### L7. `visible_rooms` hands over a dark adjacent room's full description as literal sight

- Prompt: `prompts.py:857-858` — "render what the perceiver literally SEES
  through openings."
- Code: `visible_adjacent_rooms` (`spatial.py:5578-5693`) gates on
  `_SIGHT_BARRIERS` only — no light check anywhere in the function; it ships
  up to 800 chars of the neighbour's authored `notes`/`desc`.
  `_visible_rooms_for` (`agents/perception.py:1901-1930`) subtracts
  behind_rooms but not darkness. `sight_level`/`_LIGHT_SIGHT` know dark →
  none (`spatial.py:617-623`); this consumer never asks.
- Severity: payload over-grant (model compensation currently expected; under
  the zero-LLM design it is a direct leak). Regression assertion:
  `visible_adjacent_rooms` (or its per-perceiver wrapper) withholds or
  reduces to darkness the description of an adjacent room whose
  `effective_light` is `dark`.

### L8. Scene-manager audience fails OPEN where its sibling fails closed

- Spec: `agents/background.py:140-151` (X1) states the principle — "not
  knowing where a presence stands is a reason to deliver nothing", and
  `_beat_for_presence` drops the line when speaker or station cannot be
  placed.
- Code: `_audience_map` (`agents/background.py:430-433`) does the opposite:
  `lvl = "full"` whenever `sp_room` or the presence's room is unresolved —
  and its comment claims this is "the same as `_beat_for_presence`", which is
  false. An unplaceable speaker's line is admitted at full to every managed
  presence.
- Severity: leak (fail-open on unresolvable geometry, the direction
  `_perceptually_isolated` at `agents/loops.py:310-313` explicitly refuses).
  Regression assertion: `_audience_map` yields "none" (or refuses the event)
  for a presence whose room, or whose speaker's room, cannot be resolved.

### L9. Volume-table divergences from the stated tiers (mild, verbatim-content-bearing)

- `loud` through a closed door: prompt `prompts.py:883` says muffled; code
  returns "full" (`spatial.py:1096-1097`) — `loud` and `shout` are the same
  volume to every barrier except `window`/`wall`, which is not what the
  five-step ladder promises.
- `mutter` heard across an adjacent open barrier: prompt `prompts.py:881`
  says "fragments at best WITH KEEN HEARING"; code grants the fragment to
  every ear (`spatial.py:1059-1060`, `:1070-1071`) — `hear_level` has no
  senses/acuity input at all, so the qualifier is unimplementable as
  currently plumbed. (The prompt's "extraordinary senses" clause,
  `prompts.py:595-602`, likewise has no deterministic counterpart —
  acceptable while a model applies it, a spec gap once none does.)
- Severity: mild over-grants (three verbatim words of a private aside;
  full clarity instead of a fragment through a door). Regression assertions:
  `hear_level({'barrier':'closed_door'}, 'loud') == 'fragment'`;
  adjacent-mutter fragments require a keen-hearing input once one exists.

---

## B. Confirmed under-grants and path disagreements (minds that should perceive and do not)

### U1. `_delivery_ok` blocks conducted hearing outright — the deterministic and model paths disagree in OPPOSITE directions

- Spec: `AGENTS.md:175-179` — hearing from inside a parented interior is
  CONDUCTED (`inside_source` → `hear_level` full); `hear_level` itself:
  fragment escapes a body at normal+ volume (`spatial.py:1031-1032`).
- Code: `_delivery_ok` consults `containment_conceals` BEFORE the hearing
  branch (`agents/common.py:2204-2208`), and `containment_conceals` is
  symmetric (`spatial.py:2290-2305`) — so in every `_delivery_ok` path a body
  inside another hears NOTHING of its enclosure's speech, and the room hears
  NOTHING of an enclosed speaker (not even the fragment). Meanwhile the model
  path (L2) delivers the same voices at FULL. Both floors are wrong, in
  opposite directions; nothing pins either.
- Severity: under-grant (micro path) paired with L2's over-grant (model
  path). Regression assertion: with B sealed inside A, A's `normal` speech
  reaches B as "full" (conducted) through
  `deterministic_micro_perception`, and B's `loud` speech reaches a bystander
  as "fragment".

### U2. Rear-arc actions are dropped with no sound fallback

- Prompt: `prompts.py:652-657` — a silent gesture behind you does not reach
  you, "while that same person knocking something over DOES (as sound)";
  the restriction is "a visual restriction, never sensory deprivation".
- Code: the micro-loop's action branch asks only channel "action"
  (`agents/loops.py:125-127`), which `_delivery_ok` resolves as sight +
  rear-arc (`agents/common.py:2210-2214`) — "an action is visible or it is
  nothing". The outcome action backstop skips a behind_sources actor entirely
  (`agents/perception.py:3861-3867`). Neither derives the audible surface of
  a physical act, so behind a perceiver's back the deterministic world is
  silent as well as unseen.
- Severity: under-grant (and a dramatic-irony generator lost: the noise
  behind you). Regression assertion: an overt physical act with an audible
  surface by an actor in the perceiver's rear arc contributes SOME non-visual
  delivery to that perceiver's view.

### U3. The violent/alarming-event exemption exists only in the prompt

- Prompt: `prompts.py:681-685` — explosion, gunshot, scream, being struck
  "bypasses ALL of the above (behind, focus, and periphery) and reaches
  everyone in range at full detail".
- Code: no deterministic counterpart anywhere. `_delivery_ok`'s rear-arc gate
  has no loudness exemption (`agents/common.py:2210-2213`); the B3 backstop
  skip is unconditional (`agents/perception.py:3866`). (The regexes at
  `agents/perception.py:381-392` classify observation intensity after the
  fact; they gate nothing.) A gunshot behind a perceiver is dropped by U2's
  gate with no override.
- Severity: under-grant today; a spec hole for the deterministic design.
  Regression assertion: TBD with the new design — at minimum, a `loud`/
  `shout`-class event is never fully withheld from a same-room perceiver by
  rear-arc/focus gating.

### U4. A mutter to someone "a few steps off" arrives as a three-word fragment

- Prompt: `prompts.py:881` — "mutter: same-room hears"; `prompts.py:688` —
  'near' is "same conversational space".
- Code: `spatial.py:1042-1043` degrades same-room mutter at `near` to
  "fragment"; only `within_reach` gets the full line. The micro-loop then
  mechanically truncates to 3 words (`agents/loops.py:116-120`).
- Severity: under-grant/inconsistency (prompt and code disagree about which
  tier a mutter survives). Decide which is the spec and pin it; if the code
  is right the prompt line should say so.

---

## C. Confirmed inconsistencies (latent — no live corpus instance yet)

### C1. Two size vocabularies: `proximity_rel` tests one member of a set `_ROOM_COST` says has six

- Prompt: `prompts.py:549`, `:3555` author `small|medium|large` only.
- Code: `_ROOM_COST` accepts `tiny/small/""/medium/large/huge/vast`
  (`spatial.py:5279-5280`); `proximity_rel` grants `across` only on
  `size == "large"` (`spatial.py:1375`). The first room a writer sizes
  `huge`/`vast` sprints slower (cost 3) yet can never place anyone `across`
  it — the bigger the room, the closer everyone stands. With L1/L3 that means
  whispers and mutters carry whole across it.
- Corpus: 0 `huge`/`vast` rooms live (101 `large`), so latent — the exact D1
  shape (an enum member the comparison never tests), one authored room away
  from live.
- Regression assertion: `proximity_rel` returns `across` for distinct anchors
  in a room sized `huge` or `vast`.

### C2. Proximity tiers are mostly inert for want of stations

`across` needs BOTH parties to hold `stations.at` (`spatial.py:1368-1375`);
17 of 64 corpus scenes have any stations. Not a rule defect — a fire-rate
warning for every tier-dependent rule above: measure before trusting a tier
gate to have ever run (`AGENTS.md` row 49).

---

## D. Suspected (needs a test or a design ruling to confirm)

### S1. `visibility` values outside the enum read as overt

`ActionVisibility` is strict `overt|concealed` (`schemas.py:156-158`) with no
normalizer (volume has one, `schemas.py:209-222`; visibility does not), and
every delivery gate tests `== "concealed"` (`agents/loops.py:97`, `:123`;
`agents/perception.py:1252`, `:1431`, `:3763`; `agents/background.py:418`).
The corpus contains 2 stored sequence elements with `visibility: "internal"`
(plus 20 non-enum strings on entity-state fields, which are out of scope) —
whatever wrote them bypassed validation, and every gate above treats them as
overt. Frequency is tiny and the mental-act path (`observable: ""`) usually
saves it; still, an unrecognized visibility should fail closed or normalize.
Assertion once confirmed: a sequence element with an unrecognized
`visibility` is treated as concealed-from-everyone (or normalized with a
warning), never as overt.

### S2. A recognized name is handed over at silhouette sight

`_co_present_company` labels a recognized, undisguised body by NAME even at
`sight: "shapes"` (`agents/perception.py:2033-2039` — only an UNrecognized
body degrades to "an indistinct figure"), relying on the model to honor the
`sight` field; `spatial.py:632` says dim is "not enough to know who". The
docstring calls this deliberate ("degrades honestly rather than growing a
face"). Under the zero-LLM design this becomes a direct identity grant at
outline fidelity and needs a ruling: either identity requires `sight: full`
(or voice), or the design accepts silhouette-recognition of known bodies.

### S3. `within_reach` is never in the rear arc

`entity_arc` returns "front" for any within_reach target
(`spatial.py:1504-1505`), so a body at arm's length DIRECTLY BEHIND a
perceiver is fully visible to them, while the prompt promises "a hand raised
at their back, is unseen" (`prompts.py:655-656`). Deliberate per the
docstring ("at arm's length beside you") — but "beside" is an assumption the
station data cannot check. Needs a design ruling more than a fix.

---

## Cross-cutting shape

Five separate mechanisms (L1 whisper, L2 enclosure directions, L3 outcome
proximity, L4 dazed, L5 graded sight) share one anatomy: **the graded fact is
computed somewhere in `world/spatial.py`, and the delivery site consumes a coarser
projection of it** — a missing enum member, a missing parameter, a boolean
where a tier exists, a missing flag-setter call. And in three of them
(L1, L3, L4) the injection floors convert the model's correct behaviour back
into a leak, because "the deterministic floor must not depend on a model
cooperating" was built as re-adding content, with the floor's own gate as the
only authority. The single highest-leverage fix for the branch is therefore
exactly what the branch plans: ONE production channel function (per channel)
that every path — model payload, injection floor, micro-loop, background —
must call, with `spatial_rel_between` (already written, already tested,
currently unreachable) as its relation builder.
