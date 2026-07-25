# Background Life — making extras feel like people

Status: **design / theorycraft only**. Nothing here is implemented. Written after a
read of `agents/background.py`, `commit.py`'s presence-tracking and gate code,
`prompts.py:background_react`, and the merge sites in `agents/perception.py` /
`agents/narration.py`.

The goal this document argues for: a room should feel inhabited *whether or not
the player is doing anything*. Today it only feels inhabited when the player
pokes it.

---

## 1. What exists today

Read this section as an accurate summary of current behaviour, not a complaint.
The existing system is well-built for the job it was scoped to do.

**Discovery** (`commit.track_background_presences`) is deterministic and
LLM-free. A name becomes a tracked presence only from structured fields commit
already trusts: `dialogue_log` speakers, `state_diff.entities` with a non-inert
`kind` (deny-list `_INERT_ENTITY_KINDS`), `director_establish`'s top-level
entities on the opening turn, and `background_react`'s own authored line. No NER
over prose — later prose *mentions* of an already-tracked name are counted, but
never discover a new one.

**Record shape** per presence:

```
{first_turn, last_turn, dialogue_turns: [idx], mention_turns: [idx],
 sketch: {role_hint, station_room}, pending_reply?: {from, quote, tone,
 turn, expires_turn}}
```

**Gate** (`commit.pick_background_reactors`) is deterministic and free. A
presence qualifies independently on any of six conditions:

| condition | meaning |
|---|---|
| `flow_addressed` | director's `flow.addressed_to` named them (forced pick, bypasses cap) |
| `addressed` | player input names them |
| `char_addr` | a roster speaker aimed a hearable line at them this beat |
| `owed` | unexpired `pending_reply` from a previous beat |
| `mentioned` | named in `resolved_event` |
| `dialogue_turns` | they have ever spoken |

No qualifier → `[]` → no LLM call. This is the common case and it is correct.

**Reaction** (`agents/background.py:background_react`) makes one LLM call per
picked presence (cap 1, hard-ceiling 3 via `scene.background_config`). Payload:
`{entity: {name, role_hint, station_room}, beat: {resolved_event,
addressed_by, player_declaration, present_others}}`. The beat is
perception-filtered (`_beat_for_presence`, `_filtered_player_declaration`):
concealed lines dropped, unhearable lines dropped by `hear_level`, concealed
quote bodies redacted out of the objective prose. Output is at most one line and
one brief action.

**Merge**: entries are appended to the dialogue log inside
`agents/perception.py` (not by mutating `director_resolve`, deliberately — see
the comment at the merge site), so hear-level scoping, concealment and the
narrator's `_ordered_beat_events` all apply for free.

**Promotion**: `dialogue_turns >= 2` (or `mention_turns >= 4`) makes a presence
promotable; `>= 3` dialogue turns plus activity this beat auto-promotes one per
beat into a real character with a sheet and memory.

---

## 2. Why they still read as props

Five structural reasons, in rough order of how much they cost.

### 2.1 Every trigger is a mirror of the player

All six gate conditions are downstream of the player or of the director's prose
*about the beat the player caused*. There is no condition that means "this
person has their own reason to make noise right now."

That is precisely the wrong shape for the effect we want. What makes a place
feel inhabited is **indifference** — two dockworkers arguing about a debt that
has nothing to do with you, a barkeep telling someone else the kitchen's closed.
An extra who only ever exists in response to you is, structurally, a vending
machine.

### 2.2 Amnesia was applied one notch too broadly

Refusing extras memory, psychology, mind-models and relationships is right —
that is what promotion is *for*, and it is the engine's central information
discipline.

But the current design also denies a presence **its own previous public
utterance**, which is not memory of the world. It is replay of something already
committed to the dialogue log and already shown to the player. The barkeep can
answer the same question on turn 4 and turn 9 with two different attitudes and
two different registers, and nothing in the system notices.

The insight worth building on: **continuity is not interiority.** Most of what
makes a person feel real across encounters is consistency of *surface* — how
they talk, what they call you, the thing they always complain about. That can be
delivered by deterministic replay of their own public record, at zero
information-barrier cost. Interiority stays behind the promotion wall where it
belongs.

### 2.3 They have no place

`station_room` in the payload is a bare **room id string**. Not the room's name,
not its description, not `scene.location`, not `scene.time`, not the
`fiction_model` genre, not the style guide.

So the entire location-theming budget for a background line is 160 characters of
`role_hint` harvested from the director's entity description. A barkeep in a
cyberpunk dive and a barkeep in a Regency inn receive functionally identical
context. This is the single biggest lever available and it is nearly free.

Note the style-guide exclusion in `scene.py` (`STYLE_GUIDE_FIELDS` reaches only
the Director and mapping; character agents are excluded so that "every mind in
the world" doesn't sound like the narrator). That rationale protects *authored*
characters with their own voice. A background presence has no authored voice —
it is engine-generated set dressing with a mouth, which is exactly the category
the style guide says it governs ("anything the engine GENERATES"). Extending the
guide to background presences is arguably fixing a mis-drawn boundary, not
loosening a policy.

### 2.4 One at a time, and mutually blind

At `cap > 1` each reactor is called separately, blind to the others, and the
prompt forbids referencing anyone else present. The comment in
`background_react` is explicit about the tradeoff and it is a defensible one for
*reactions*.

But it structurally forecloses the single most recognizable signature of an
inhabited room: two extras talking **to each other**. No amount of tuning the
reaction path produces that, because the architecture guarantees each voice is
generated in ignorance of the other.

### 2.5 Population depends on the director bothering

Presences only exist if the director writes structured entity defs or voices
someone in `dialogue_log`. The mapping stage mints rooms and lore for new space
but no people. So a freshly generated tavern is architecturally empty, and stays
empty until the director happens to invent someone.

---

## 3. The theory: three jobs, currently one mechanism

One stage is being asked to do three different things with three different cost
models, gating shapes, and info-barrier profiles:

| | job | trigger | cost shape | status |
|---|---|---|---|---|
| **A** | **Response** — an extra answers when engaged | player/character salience | 1 call per engaged presence | exists, works |
| **B** | **Ambient life** — the room talks to itself | *absence* of player salience + cadence | 1 call per beat, N voices | missing |
| **C** | **Continuity** — the same extra is recognizably the same person | free, deterministic | 0 calls | missing |

Separating them is the whole proposal. In particular B is gated by the *inverse*
of A's gate — it should fire on the quiet turns, which are exactly the turns
where A costs nothing today.

---

## 4. Proposals

Ordered cheapest-first, and each is independently shippable.

### P1 — `place` block in the payload (theming, ~30 lines, no schema change)

Add to `_react_one`'s payload:

```python
"place": {
    "room_name":        sc["rooms"][station_room]["name"],
    "room_desc":        sc["rooms"][station_room]["desc"],
    "location":         sc.get("location"),
    "ambient_location": _ambient_location_for(sc, station_room),  # perception.py
    "time":             sc.get("time"),
    "genre":            fiction_model(cid)["genre"],
    "style":            {k: style_guide[k] for k in ("genre", "tone", "avoid")},
}
```

Every field is objective self-locating information the presence trivially
possesses — you know what room you are standing in. Reuse
`perception._ambient_location_for` rather than reading `scene.location` raw, so
the nesting rules (an enclosed room does not receive the outer location's
ambience) hold identically to how they hold for real characters.

Only `genre`/`tone`/`avoid` from the style guide — `director_notes` and
`mapping_notes` are instructions to other stages, not to a person in a room.

Prompt change: tell the reactor its line should sound like it belongs to *this*
place at *this* hour.

**This alone converts existing reactions from generic to location-themed.**

### P2 — Self-continuity by replay (`last_lines`)

Extend the presence record, harvested deterministically at commit from what was
already committed:

```
"last_lines": [{"turn": idx, "quote": "..."}]   # ring buffer, max 2, own quotes only
"player_exchanges": {"addressed_by_player": int, "answered": int}
```

Replay `last_lines` into the payload as *"the last things you yourself said out
loud"*. This is not memory: it is the presence's own public record, already
rendered to the player, replayed back. No perception filter is needed because
they said it.

`player_exchanges` is a counter tuple in the same category as the existing
`dialogue_turns` — objective interaction history, not a relationship model. It
lets the prompt say "the player has spoken to you four times tonight" without
anyone modelling how the barkeep *feels* about that.

Also: keep `first_role_hint` immutable alongside the currently-overwritten
`sketch.role_hint`, so a presence's original identity is not drifted away by
each new director description.

### P3 — The `ambient_beat` stage (the actual feature)

A new optional stage, placed after `background_react` and before
`perception_outcome` so its lines ride the same merge path.

**Gate** (deterministic, LLM-free, in `commit.py` next to the existing one):

- fires only when the beat is **quiet** — no `flow_addressed`, no owed reply, no
  `reaction_loop` and no `interaction_loop` ran this turn;
- requires ≥1 tracked presence whose `station_room` is inside
  `spatial.ambient_scope(sc, player_room)` and who did not speak this beat
  (otherwise the lines are generated and then dropped by perception — wasted
  call);
- fires on a **cadence**: a pure function of `(chat_id, turn_idx)` — e.g. a hash
  mod k, with k from `background_config`. Purity matters: a rerun or reroll must
  not flip fire/no-fire, or step/variant replay desyncs.

**Call shape**: **one** call producing up to N (default 2) short lines from
*named, distinct* presences. This is the fix for §2.4 — a single call can author
an exchange, which N blind calls structurally cannot. It is also the fix for the
cost objection: ambient life costs one call on quiet turns, not N.

**The load-bearing constraint**: an ambient line is *not addressed to the
player*. Enforce deterministically after the call, not by prompt alone:

- drop any entry whose `intended_target` resolves to the player/persona;
- drop any entry whose quote names the player or persona;
- force `visibility: "overt"`, `volume ∈ {"quiet", "normal"}`, speaker forced to
  the gate-picked name (same discipline as `_react_one`).

This is what separates ambient life from "another channel for NPCs to talk at
the protagonist." Without it, P3 degenerates into P0 with extra steps.

**Merge**: identical to `background_react` — append to the dialogue log at the
`agents/perception.py` merge site. Hear-level scoping, concealment and
`_ordered_beat_events` then apply unchanged, and an ambient line spoken in the
tavern correctly fails to reach the player in the cellar.

**Narrator contract**: ambient lines are **texture, not beats**. The narrator
prompt needs an explicit clause that these may be compressed, rendered as
overheard fragments, or folded into a sentence of atmosphere — never dramatized
as the turn's event. Without this clause, every quiet turn inflates into a
tavern set-piece and the pacing dies.

### P4 — Location-themed population at mapping time

When the mapping stage mints a new room, let it optionally emit:

```
"ambient_presences": [{"name", "role_hint", "station_room"}]   # 0–3
```

Commit tracks these into `background_presences` with `seeded: true` and empty
`dialogue_turns` (so they do *not* auto-qualify for reaction — see §2.1's gate
table, where `dialogue_turns` non-empty is itself a qualifier).

Mapping already receives the style guide and the fiction model, so theming is
free and consistent with the room it just invented: a tavern gets a barkeep and
a regular, a morgue gets a night attendant, a bridge gets an ensign at ops.

**Pruning is mandatory.** Seeded presences that have never spoken and whose
`last_turn` is older than N turns should be dropped at commit, or the presence
dict grows without bound over a long chat and every entry is a promotion
candidate.

### P5 — The chorus presence

The hard-cap comment in `background_react` already states the principle: *"beyond
this a crowd is a chorus."* Make it a real entity kind.

A presence flagged `aggregate: true` renders unattributed collective reaction —
"someone at the back laughs", "the line behind you starts complaining" — with no
name, no promotion path, and no per-member tracking. One call represents fifty
people. Mapping seeds one for any room it describes as crowded.

---

## 5. Risks, and how each is contained

**Promotion pollution.** Ambient chatter must not accrue `dialogue_turns`, or a
barfly who says three unrelated things auto-promotes into a full character with
a sheet and memory (`AUTO_PROMOTE_DIALOGUE_THRESHOLD = 3` — three turns of
ambient noise clears it). Record ambient lines under a separate `ambient_turns`
counter that is *excluded* from both promotion thresholds. Speaking **to the
player** is what should earn a mind.

**Narrator dilution.** See the narrator contract in P3. Additionally cap ambient
lines at 2 per turn and suppress the stage entirely on any turn where the
director's beat is high-stakes (a contested reaction ran, someone drew a weapon).
Ambient life is a low-tension-only feature.

**Rerun / variant determinism.** The new stage must be a real `steps`/`variants`
row like every other stage, and its cadence gate must be a pure function of
`(chat_id, turn_idx)` with no wall-clock and no RNG, or rerun-from-stage and
reroll silently change whether the room was alive.

**Cost.** One extra call on quiet turns only — and quiet turns are exactly the
turns where `background_react` currently costs nothing, so the marginal spend
lands where there is budget. The gate's "is anyone actually in ambient scope"
check exists specifically to avoid paying for lines perception will discard.

**Information barriers.** P1's `place` block and P2's `last_lines` are both
strictly self-knowledge (your own room, your own past words) and introduce no
new leak surface. P3's output rides the existing merge path, so it is filtered
by the same perception machinery as everything else. The one genuinely new
surface is P4: a mapping-seeded presence is a *fact about the world* the mapping
stage invented, and must be committed through the normal scene/entity path
rather than written straight into `background_presences` behind commit's back.

---

## 6. Suggested sequencing

1. **P1** (`place` block) — smallest diff, immediate qualitative win, no schema
   or pipeline change. Do this first and evaluate before building anything else.
2. **P2** (`last_lines` replay) — small commit-side harvest plus one payload
   field.
3. **P3** (`ambient_beat`) — the real feature. New stage, new prompt, new
   schema entry, deterministic gate, narrator clause, and the anti-addressing
   post-validation. Needs its own tests mirroring `tests/test_background_react.py`
   and `tests/test_background_beat_filter.py`.
4. **P4 / P5** (seeded population, chorus) — only worth building once P3 proves
   the ambient channel reads well, because they exist to feed it.
