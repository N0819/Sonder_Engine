# customs-office-10: firewall + memory audit

10 turns · persona **Auditor Dana Rennick** · character **Séverine Moreau** ·
`known` seeded empty (strangers) · run 2026-08-01 against live providers.

The run that found the `spatial_frame` identity leak. Its throwaway database was
deleted before this file was written, so the numbers here come from the run's
own stdout and from queries made against it while it existed — they cannot be
re-derived. The 30-turn run that follows it writes its audit directly.

**Scenario.** A rain-soaked customs office on the harbour road, an hour before
dawn. One lamp, one desk, one locked ledger. The clerk on duty has been waiting
for someone all night and is not sure this is them.

---

## Run

| turn | seconds | memories | player input |
|---|---|---|---|
| 0 | 40.7 | 0 | _(establish)_ |
| 1 | 75.6 | 4 | "I'm here about the Kestrel manifest." |
| 2 | 139.1 | 8 | "The seal drops at midnight tomorrow…" |
| 3 | 93.9 | 12 | "If anyone asks, you never saw me…" |
| 4 | 76.2 | 16 | "The number is four-seven-three-one." |
| 5 | 122.6 | 20 | "How long have you worked here?" |
| 6 | 106.0 | 23 | "Who told you to wait for me tonight?" |
| 7 | 76.5 | 27 | _(slides a folded paper across)_ |
| 8 | 156.8 | 31 | "That name on the paper. Have you seen it before?" |
| 9 | 83.7 | 35 | "I'm not who you were told to expect." |
| 10 | 168.5 | 39 | "Everything I said before tonight was someone else's script." |

**39 memories** — `{episode: 11, self: 10, inference: 18}`. ~18 minutes of
wall clock.

---

## The finding: a structured field handed over an identity the prose withheld

`known` was `{}` for the whole run, and Séverine **asked for the name twice, in
dialogue**:

> t1 — "The Kestrel manifest. To whom do I have the pleasure of speaking this evening?"
> t2 — "Your name and the precise nature of your oversight here would be most helpful."

She was never answered. The player-persona's scripted lines never gave a name.

**11 of 39 memories carry the persona's canonical name anyway.** By t8 she says
it aloud: _"The name is unfamiliar to me, Dana."_ — a first name that appears
nowhere she could have learned it.

### Where it came from

Her own authored prose was correct throughout. `attempt`, `observable`,
`relationship_updates.target_entity` all say "the auditor". Only the structured
binding fields carried the name, and `about_entity` flipped at t5:

```
t1–t4  about_entity: ["the auditor"]
t5–t10 about_entity: ["Auditor Dana Rennick"]
```

Traced by elimination. Every channel that could have carried it:

| channel | leaked? |
|---|---|
| perception views / observations | no — "the auditor" throughout |
| event summaries (`recent_events_for_observer`) | no — 0 mentions in any turn's summary |
| memories t1–t4 | no |
| relationships / mind_models | no — keyed "the auditor" |
| `_known_pronouns` | no — correctly gated on recognition |
| `private_knowledge_for` | no |
| `rekey_place_claims` | no — explicitly protects people |
| `bind_sequence_targets` | no — cast only, not the persona |
| **`perception.spatial_frame.ahead_entity`** | **yes** |

```python
spatial_digest(scene, "Séverine Moreau")
# -> {"behind": [...], "ahead_entity": "Auditor Dana Rennick"}
```

`spatial_digest` reads `scene.positions`, which is keyed by **canonical name**
by convention, and `ahead_entity` is the one field in that payload naming a
body rather than a room. Nothing gated it.

Two earlier guesses of mine — the mind-model rekey path, then
`bind_sequence_targets` — were both wrong, and are listed above with the others
so the elimination reads honestly.

### The fix

`agents/common.observer_label_fn` reuses perception's own gate — same `known`
map, same `_unknown_actor_label` — so this stays one identity floor rather than
a second that can drift. Verified against this run's own scene:

```
BEFORE (no gate) : ahead_entity = "Auditor Dana Rennick"
AFTER  (gated)   : ahead_entity = "the lean sharp-eyed woman"
once she KNOWS   : ahead_entity = "Auditor Dana Rennick"
```

Regression: `tests/test_spatial_identity_gate.py` (6 tests, including one that
asserts the *wiring*, since `spatial_digest` still defaults to ungated for the
narrator and internal geometry).

---

## What held

- **memories containing "the player": 0.** The alpha 6.4.1 fix works in play.
- Views and episodes used "the auditor" / "the lean sharp-eyed woman in a
  charcoal uniform" throughout — the perception identity floor is solid.

---

## What did not fire, and why

Three features shipped with 3,733 passing tests produced nothing in 10 turns.

| | emitted | cause |
|---|---|---|
| `remember_lines` | **0** | absent from the prompt's JSON output contract, so the model emitted the documented shape and the schema filled the default |
| `memory_disputes` | **0** | same |
| importance via citation | **0** | the reader required a numeric memory row id; characters cite `event:<hash>` |

The citation one is the instructive failure. What characters actually wrote:

```
current                            ×66
current:39:4
turn:2:character:39:0:action
turn:3:character:39:1:speech
event:2913301d0f7dbb2a18e0a96c
```

`event:<hash>` **is** `memories.event_key`. All five distinct handles emitted in
this run resolved to a real row. The format was there the whole time; the reader
was looking for one nothing produces — and the unit test asserting `== [41]`
agreed with it, which is how a dead feature passed a full suite.

Replayed through the repaired reader, the citation path fires: turn 10 cited the
t9 inference _"The act of revelation itself is producing or amplifying the fear
scent"_ and raised its importance 0.63 → 0.674. One hit in ten turns — sparse,
but the right memory.

---

## Method note

`t9`'s memory count fell from 39 to 27 in a mid-run check because I queried the
wrong step key: this plan runs `interaction_loop` (single character), not
`character:<id>`, and my first analysis pass reported a confident zero from a
place the data was never in. The audit script now reads both shapes.
