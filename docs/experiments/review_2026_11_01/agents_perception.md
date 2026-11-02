# Audit — `agents/perception.py` (2026-11-01, tree at `84f3de23`)

Auditor's scope: the module the engine calls the information firewall's
deterministic floor. Every `path:line` is the current working tree. Snippets
were run with `.venv/bin/python` and `ENGINE_DB` pointed at a scratch file
(never the repo db); live scenes were read from `engine.db` with
`?mode=ro`. One focused test file was run (`tests/test_perception_card_senses.py`,
6 passed).

## Scope read

- **Read in full:** `agents/perception.py` 1–9323 (every line, in order).
- **Read in part, to trace a finding:** `agents/composer.py` (`_sense_graded`
  240–275, `concealed_from_observer` 664–684, `_dim_figure`/`_unfamiliar_person`
  1287–1293, `cue_percept`/`demeanor_percept` 2929–2975, `crossing_percept`
  5585–5600); `agents/common.py` (`sequence_event_allowed` 645–653,
  `sequence_onset_elements` 416–426, `_sync_sequence_mirrors` 5127–5145,
  `observer_body_regions` 1750–1830, `_room_notes_for_view` 4234–4248);
  `agents/director_evidence.py` (`beat_timeline` 1176–1236, `beat_event_ledger`
  1289–1345, `normalize_causal_ledger` 2802–3090); `agents/director_prose.py`
  (header 1–60, `WORLD_SOURCE` 3228–3311, `ledger_from_events` 4548–4624,
  `_ROW_FIELDS` 4261); `agents/director.py` (495–530, 2228–2250, 2680–2690,
  4490–4600 `add_group`, 6245–6300, 7325–7336, 7895–7930);
  `world/beat_ledger.py` 100–184; `world/scene_memo.py` 1–200;
  `world/spatial_sound_field.py` (`sound_field` 3051–3110,
  `stamp_sound_relation` 3401–3450); `world/spatial_senses.py`
  (`spatial_rel_between` 674–740, sense tables 2280–2430);
  `world/spatial_substance.py` 856–891; `story/scene.py` 1975–2030;
  `story/attire.py` 2925–2960; `core/pipeline_context.py` 278–380;
  `agents/runtime.py` 1520–1535, 1560–1600, 1700–1795;
  `tools/project_check.py` 1682–1790, 3187–3330; `tests/test_perception_has_no_model.py`
  (whole); the 24 patch sites and 16 source pins (each line in context).
- **Skimmed, not audited:** the rest of `composer.py`, `common.py`,
  `director*.py` and the world modules perception calls.
- **Registers grepped for every finding:** `docs/UNBUILT*.md` (all ten).

## Findings

### F1 — The sense card gates bodies and lines, and nothing else: a blind card is told the room, a deaf card hears it

**Severity: LEAK. Confidence: CONFIRMED (reproduced).**

`agents/perception.py:6178-6184` (`_composer_standing_percepts`):

```python
env = composer.environment_percept(
    room, p.get("room_name"), room_notes,
    effective_light(sc, room) if room else "",
    features=_visible_features(sc, name, room, sweep=sweep),
    openings=_visible_openings(sc, name, room, sweep=sweep, gate=gate,
                               named_out=via_names),
    light_shape=light_shape(sc, name, sweep=sweep) if room else None)
```

`senses = p.get("sense_card")` is read (6335) only for presence, pose,
appearance, far places, vistas and scent. Every other builder takes no card:
`_visible_features`/`_visible_openings`/`_visible_things` (5697, 5916, 5727 —
`feature_visibility(sc, name, sweep)` has no card), `light_shape`, the
station-read admission in `_things_read_by` (566: `if at and not
_is_dark(effective_light(sc, room))`), `observer_body_regions` (6517),
`room_content_percepts`/`chatter_percepts` (6311, 6328 — posted notices are read
by sight, chatter is heard), the soundscape (6188), `weather_sound_percepts`
(6278), every `_gated_ambient_percepts` call (6883, 6898, 7173, 7183, 8394, 8437, 8877),
`heard_events` (6892, 7177, 8411, 8423), `distant_sound_percepts` (8447), and
`_reaches_this_ear` (1704: "Always, for an open ear" — the card is never asked).

Reproduced through the real builder, same scene, two cards:

```
--- seeing: kinds=[('environment','sight'), ('ambient','sight')]
   view: You are in Kitchen. A warm kitchen with a scrubbed table. You can see the hearth within arm's reach and the long oak counter within arm's reach. Through the back door is The Yard. A muddy yard. There is a silver coin at the long oak counter.
--- BLIND (vision acuity "blind"; sense_acuity_offset -> None):
   view: (byte-identical)
--- hearing card / DEAF card (hearing acuity "deaf"), plant room with a loud generator and a kettle event:
   view: You are in Plant Room. You can see the generator within arm's reach. The noise from the generator is a din at the generator. Where you are, you are in the din. A kettle shrieks on the stove.
   (byte-identical for both; _reaches_this_ear -> True for the deaf card)
```

Scenario: a character authored blind stands in a lit kitchen; her view, her
observations and her memory episode say she can see the hearth, the counter,
a coin on it and the yard through the door. A deaf character's memory holds
the kettle's shriek. `composer._sense_graded`'s own docstring says this class
was fixed ("an authored-blind card saw the room in its onset view, its outcome
view and its memory of the beat"); `tests/test_perception_card_senses.py` (6
passed) pins bodies and spoken lines only.

Fix: grade the environment/things/openings/notices/body-region admissions
through `composer._sense_graded(..., "sight", card)` and the soundscape,
ambient, near-field, far and weather-sound admissions through the hearing
card, at the perception side where the card is in hand. Never subtract more
than the card says (an `equivalent`/`needs_light: false` sight keeps the room).
Test: extend `test_perception_card_senses.py` with a blind and a deaf card
over a room with anchors, a stationed thing, an open doorway, a standing
sound source and a one-beat sound event — assert no sight/hearing percept of
those kinds, and that touch (`_felt_percepts_for`) still arrives.

### F2 — A heard tell is graded by none of the rules the line beside it uses

**Severity: LEAK (and its inverse). Confidence: CONFIRMED (three reproductions).**

`agents/perception.py:3123-3139` (`_delivered_manifest`):

```python
rel = spatial_rel_between(scene, observer, sname,
                          observer_room=o_room, target_room=s.get("room"))
visible = (visual_level_between(scene, observer, sname,
                                _sense_card(observer_sheet)) != "none"
           and sname not in behind)
...
audible = bool(rel.get("same_room")) \
    and hear_level(rel, "normal") == "full"
```

1. **No hearing card.** A deaf observer in a dark cellar (`sight=none`,
   hearing offset `None`) is delivered `{'Bo': {'cues': ['a ragged breath catches
   in the dark']}}`, minted by `_cue_percept` as `('cue', 'hearing', …)`.
2. **Every tell is a normal voice.** A `breath` tell 77 paces off in a vast dark
   hall: `hear={'whisper': 'none', 'mutter': 'none', 'normal': 'full'}` →
   delivered. A breath carries less than a whisper; the line rule would refuse it.
3. **`same_room` is required.** A `voice` tell from the next room through an
   open doorway in the dark: the speaker's normal line is `full` there under
   the dB rule, the tell is withheld (`delivered={'breath': False, 'voice': False}`).
4. The relation is built with no `sound=` field, so `stamp_sound_relation`
   derives one from the scene alone — no crowds, no turn index, no events: a
   third field for the same beat (see F4).

Also on the sight half: `visual_level_between(..., card)` spends the card only
on `needs_light` (it returned `full` for a `vision: blind` card in a lit room
— measured), so `visible` here, `_manifest_percepts` (4675) and `_cue_percept`
(4712) hand a blind observer seen tells and demeanor; every other sight reader
in the module wraps it in `composer._sense_graded`.

Fix: grade `audible` with the listener's card and at the tell's own level
(breath ≈ the breath ladder, voice = the speaker's line level), through the
stage's field, without the `same_room` precondition; wrap `visible` in
`_sense_graded`. Test: the three cases above as a parametrised
`_delivered_manifest` test (deaf, far breath, voice across an open doorway)
plus a blind card in a lit room.

### F3 — An act concealed from ONE observer is withheld from EVERY observer at outcome

**Severity: WRONG-SCENE (a floor that subtracts more than its rule). Confidence: CONFIRMED (reproduced).**

`agents/perception.py:1141-1142` (`_outcome_event_stream`):

```python
elif (event.get("type") == "action"
      and event.get("visibility") != "concealed"):
```

The docstring (995–997) says "Concealment, sight, hearing, containment and
identity remain per-observer decisions in the loop that consumes the stream";
the per-observer rule is `composer.concealed_from_observer` ("a populated list
is an explicit excluded audience"), and the onset pass hands concealed acts to
`composer.act_percept`, which applies it. The outcome stream decides it
pre-perceiver for actions only (lines and communications keep their
`conceal_from` and are gated per observer).

Reproduced — a character's act `conceal_from: ["Guard"]`:

```
non-causal stream: []
hidden from Mara? False      (composer.concealed_from_observer)
hidden from Guard? True
causal stream: []            (_restrict_causal_concealment copies it onto the span, then dropped)
```

Scenario: Nera slips a key into Mara's palm, hidden from the guard. Character
acts reach observers only at outcome, so Mara — the accomplice, not in
`conceal_from` — never perceives the handoff, in her view or her memory.

Fix: keep concealed actions in the stream (with their `visibility` and
`conceal_from`) and let `act_percept`'s existing gate decide per observer.
Test: `_composer_outcome_views` (or the stream plus `act_percept`) with an act
concealed from one named observer: the excluded observer gets nothing, a
co-present non-excluded observer gets the act.

### F4 — Uncited outcome lines are graded on a field without the beat's own sounds (one beat, two fields)

**Severity: WRONG-SCENE. Confidence: CONFIRMED (path traced, field difference measured).**

The perceiver maps are built before the composer region with no events:
`agents/perception.py:4340, 4370, 4404` — `sound=_sound_field_for(ctx, sc,
p_name, p_room)`. Inside `_composer_outcome_views` the observer's `field`
carries them (8319: `_sound_field_for(ctx, sc, name, p.get("room"),
events=beat_sounds)`) and grades the soundscape, ambient sounds and acts. But
a line with no causal moment and no pending mover cut is graded on the
pre-built relation (8540–8545):

```python
def _channel_as_of(counterparty, at_index, _observer=name, _spatial=spatial):
    standing = _spatial.get(counterparty)
    moment = _as_of(at_index)
    if moment is None:
        return standing, measured_proximity_rel(sc, _observer, counterparty)
```

`event_worlds` gives a moment only to cited spans; background presences'
lines, Director-originated rows and every line of an archived beat are
uncited. Measured with a `drowns` event in the speaker's room:
`line heard without the beat's events=full / with them=none`. Scenario: the
falls drown the yard; the cast's lines are lost, a background guard's line in
the same beat arrives whole — the "ONE BEAT, ONE FIELD (PC3)" rule the code
states at 2065, 8508 and 8650. `world/spatial_senses.py:706` says perception builds
the field "with the beat's crowds, events and turn index"; it does not here.

Fix: build the perceiver-level maps with the beat's events (they are known
after `compose_beat_scene`), or have `_channel_as_of` restamp `standing` with
`field`. Test: a background presence line plus a `drowns` sound event, assert
the line is refused exactly as a cast line in the same room is.

### F5 — `_tell_acuity` reads a card's senses with its own vocabulary, and disagrees with the engine's

**Severity: WRONG-SCENE (subtracts). Confidence: CONFIRMED (table below).**

`agents/perception.py:3031-3043`: channel accepted only if exactly `vision`,
`hearing` or `general`; acuity from a nine-word dict, anything else 0.4.
The engine's reader (`spatial.sense_acuity_offset`, `_SENSE_CHANNEL_ALIASES`,
`_ACUITY_PLUS_ONE/TWO`) maps `sight`/`eyes`/`visual` and
`keen/acute/sharp/…`, `extraordinary/supernatural/…`.

```
vision keen          tell_acuity=0.65  engine sight=+1
sight  keen          tell_acuity=0.40  engine sight=+1
eyes   keen          tell_acuity=0.40  engine sight=+1
vision acute         tell_acuity=0.40  engine sight=+1
vision sharp         tell_acuity=0.40  engine sight=+1
hearing extraordinary tell_acuity=0.40 engine hearing=+2
vision supernatural  tell_acuity=0.40  engine sight=+2
vision exceptional   tell_acuity=0.90  engine sight=+1
```

Scenario: a card written with the engine's own channel word (`sight`) or an
ordinary synonym (`acute hearing`) is graded as an ordinary observer, so
`subtle` tells (0.65) are withheld from a mind its author made perceptive. A
Japanese card's acuity words fail both readers alike (English tables), which
is a separate, world-side hazard. Fix: derive the tell acuity from
`sense_acuity_offset` (one reader), keeping the owner's 0.4/0.65/0.9 scale.
Test: the table above as a parametrised test against `sense_acuity_offset`.

### F6 — English literals reach the page of a non-English story

**Severity: WRONG-SCENE. Confidence: CONFIRMED (rendered).**

- `agents/perception.py:8929-8931` (crossing label): `label = mover if
  _recognizes(mover, recognized) else "a figure"` — reached when `diff.positions`
  keys a presence by entity id (the display map is keyed by display name).
  Rendered: `en -> 'A figure comes in.'`, `ja -> 'a figureが入ってくる。'`
  (the pack's own word is `見知らぬ人物`; `composer._dim_figure()` exists).
- `6373-6374`: `display_map.get(b_name) or (b_name if recog else "the unfamiliar person")`
  — `composer._unfamiliar_person()` is the pack-driven spelling, used by this
  same module at 9174, 9277 and 9317.
- `6516`, `6526`, `743`, `4897`: `"someone"` region/part labels; `6472`:
  `or "something"` for a contact party the ladder drops.
- `4311`: an extra player with no appearance gets
  `f"{e_name}, a person of unremarkable appearance."`, which feeds the stranger
  descriptor in every view of that seat.
- `3918` `_REDACTED_NOTICE` and its second spelling in `story/scene.py:2027`
  reach a character payload through `recent_events_for_observer`.
- `_self_body_detail` (714–725, live through `_composer_bare_details`) rewrites
  `her`→`your` only; a Japanese card's bare-region detail stays third person in
  the body's own view.

`_unseen_voice_label` (4940) is the precedent the module already set for this
class ("It was the English literal "a voice" in every pack"). Fix: the pack's
`unknown_actor_fallback`/`dim_figure` and a compositor template for the rest.
Test: a Japanese outcome with an entity-keyed mover crossing in, asserting no
ASCII label in the view.

### F7 — The disguise tripwire cannot fire in Japanese, and never checks a cast member's disguise

**Severity: SILENT-NOOP (a firewall tripwire). Confidence: CONFIRMED.**

`agents/perception.py:3379-3389`:

```python
if pid.casefold() == "player":
    continue  # the player is the subject / always knows
...
    if t and re.search(rf"\b{re.escape(t)}\b", v):
```

`\b` never matches between Japanese characters; the redactor fixed exactly
this with `name_boundary_regex` (3981). Reproduced: `en warnings: [...]`,
`ja warnings: []` for `狐の耳` in `彼女の狐の耳がぴくりと動くのが見える。`
(`name_boundary_regex` finds it). And both call sites (7500, 9070) pass the
PLAYER's terms only, so an NPC's disguise is never tripwired, and the player
perceiver is skipped whoever the subject is. "Real leaks are guards that
cannot fire" (the module's own banner). Fix: `name_boundary_regex(t)`; loop
the check over every body with concealed terms, skipping only the subject.
Test: the Japanese case and an NPC subject with the player as the unaware viewer.

### F8 — The outcome stream drops every element kind it does not name, without a word

**Severity: SILENT-NOOP (latent today). Confidence: CONFIRMED.**

`agents/perception.py:1114-1157`: `speech` (bound to a dialogue row),
`communication` (with a surface), `action` (overt, with a surface) — anything
else is skipped with no `note_step_decision`, and a declared line whose words
match no dialogue row (1116–1132) is dropped likewise. The engine's own
projection emits a fourth kind: `director_evidence.py:3069-3071` makes every
world/mechanical row `{"type": "event", "description": …}`, and
`common.py:4924` does the same for a player's world assertion. Reproduced:
`timeline element types: ['event', 'action']` → `stream: [('action', 'boat', …)]`.
Latent for live play only because `normalize_causal_ledger` tests `worldly`
on the RAW row's `authority_mode` (2923–2924), which `director_prose._ROW_FIELDS`
(4261) never carries — so the `event` projection is itself unreachable for
prose-contract rows (a dead branch left by 2026-09-27, question 6). It is live
on a rerun of an archived pre-2026-09-27 beat. Also: in the consuming loop,
any kind other than speech/silence/communication falls through to the act
branch (8763). Fix: an explicit branch (or an explicit refusal with a step
decision) per kind; decide whether a world `event` is an act the composer
renders. Test: a stream with an `event` row asserting it is either delivered
or recorded as refused.

### F9 — Ten perceiver payload fields are computed every stage and read by nothing

**Severity: DEAD (and PERF, see E2). Confidence: CONFIRMED (repo grep).**

At all three stages (e.g. `agents/perception.py:3464-3483`, `3737-3777`,
`4326-4344`) each perceiver gets `visible_rooms`, `behind_rooms`,
`proximity_to_sources`, `behind_sources`, `focus_target`, `ambient_location`,
`senses` (prose), `attention`, `scent_channel_to_sources` (2118, its own
comment says "DELIVERED NOWHERE"), and `knows_identity` (registered). No
reader exists in perception (`p.get`/`p[...]` grep) or anywhere else
(`narration.visible_rooms` is a local of its own). At onset,
`_co_present_company` (2933–3012, with `observer_display_map` and four sight
derivations per body) exists only to fill two of them (3737). Its docstring
and `_visible_rooms_for`'s describe "the two fields the perception prompt
already describes" — there is no prompt. Measured cost: E2. Fix (no function
removed — nothing reads them): delete the fields and the helpers only they
use (`_co_present_company`, `_proximity_to_sources`), with the tests that pin
them (`test_perception_presence.py`, `test_perception_field_of_view.py`,
`test_adjacency_reciprocity.py`, `test_pose_anchor_orientation.py`,
`test_monitoring_scope.py`, `test_masked_floor_leaks.py`, `test_scent_delivery.py`).
`_behind_sources`/`_focus_target` stay: `_delivered_manifest` calls them.

### F10 — Dead pack tables and test-only helpers that read as live floors

**Severity: DEAD. Confidence: CONFIRMED (repo grep incl. tests, tools, extensions).**

- `language_packs/*/cards/linguistics.json` `agents.perception`:
  `_AMBIGUITY_CUES`, `_INTENSITY_CUES`, `_SUDDENNESS_CUES` — no reader at all;
  `_SELF_DIRECTED` — tests only (`test_firewall_across_scripts.py:164` asserts it
  "decides whether an observer is told an event landed on" their body; nothing
  decides with it); `_RAISING`/`_LOWERING` — only the cut tripwire's comment;
  `_CHANNEL_CUES` — only `_atom_channel` (454), itself test-only. Seven of the
  section's twelve tables.
- `_inverted_motion_check` (3336) returns immediately and is still called
  (9072); "Kept as a name so a stored variant that names it still loads" — no
  loader resolves functions by name from a variant.
- `_touch_only_sources` (3805) and `_surface_translate_event` (3889): tests
  only; UNBUILT_PIPELINE §3.1 still lists the latter as a live boundary
  ("now fails closed").
- `_dialogue_hear_level` (338): reached only by `tools/perception_quality.py`
  (its docstring says "the model path's … entry point").

Fix: delete with their pins (one commit, after the split), or say in each
docstring that it is a compatibility export. Test: none needed; `make
structure` could flag pack keys with no reader.

### F11 — `_explicit_look_intent` asks a field nothing has written since 2026-09-27

**Severity: DEAD. Confidence: CONFIRMED (repo grep: `setdefault(None)`/reset only).**

`agents/perception.py:4475`: `if str(interp.get("location_query") or "").strip(): return True`.
No prompt in either pack asks for `location_query` and no code writes one
(`director.py:2529`, `2688` only default and clear it). The mapping-side
consumers (`agents/mapping.py:537-672`, the `location_query_unmatched`
planning need) are dead for the same reason. Fix: delete the branch (the
`look: around` and look-verb branches carry the behaviour), or restore a
producer. Test: none.

### F12 — Comments and docstrings that describe the model path or a cut tripwire

**Severity: STALE-DOC. Confidence: CONFIRMED (read against the code).**

- `4447-4453` (composer banner): "It is read in exactly one place … `_inverted_motion_check` compares the FINISHED view against the resolved event" — cut 2026-09-15; `resolved_event` now reaches only that no-op. Same claim at `agents/director.py:7332`.
- `996-998` (`_outcome_event_stream`): concealment "remain[s] per-observer" — false for actions (F3).
- `3944-3945` (`_redact_concealed_from_event`): "the perception prompt's own instruction remains the second layer" — no prompt exists.
- `3815`, `3895` (`_touch_only_sources`, `_surface_translate_event`): "the perception LLM … resolves those acts".
- `3780-3786` (`perception_act`): "Input-side hygiene … the model has no legitimate use for the canonical name … ("actor_name": "Hinami")" over no code; "excluded from the LLM call" (3790), and `4417` (`perception_outcome`) "EXCLUDED from the LLM call entirely".
- `1194-1196` and `7845-7846`: "the recompiler reassembles it" / "The causality recompiler records it" — deleted 2026-09-27.
- `1997` (`_source_channels`): "the deterministic actor-describer, which is gated on exactly this map" — `common._inject_visible_actor`, dead (§1.45).
- `375` (`_dialogue_hear_level`): "the model path's (and the quality harness's) entry point".
- `386-397` (`_ling`): `_SELF_DIRECTED` "never fired" — it has no reader now (F10).
- Orphans: `3326-3333`, `3916-3917`, `5246-5251` (see the split plan).
- `AGENTS.md:431`: "concealed actions are sentence-level redacted from the resolved event per-perceiver …; touch-only sources get surface-translated event text" — no view is built from `resolved_event`; the redactor survives only on `story/scene.py`'s stored-event replay.
- `world/spatial_senses.py:706-707` (F4) and `agents/composer.py:253-275` (F1).

Fix: one documentation commit after the split.

### F13 — Voice register and voice sound match speakers against a ctx key nothing writes

**Severity: SILENT-NOOP (minor). Confidence: CONFIRMED (grep: no `ctx["scene"]` writer).**

`agents/perception.py:4612, 4636`: `same_subject(ctx.get("scene") or {}, character_name(sheet), target)`.
`PipelineContext` declares no `scene` and no stage stores one (`loops.py:1278`
and `character.py:3622` write a different dict). The alias-tolerant half of
the match is inert; only the casefolded `!=` beside it works, so a speaker
spelled by uid or alias gets no register and no voice sound. Fix: pass the
stage's scene. Test: a line whose speaker is a cast alias carries the card's voice sound.

### F14 — Broad excepts that disarm a subtracting floor fail OPEN

**Severity: SILENT-NOOP. Confidence: PLAUSIBLE (failure not injected).**

`2289-2292` `_crossing_legs` (`except Exception: return ()` → `_multi_room_legs`
empty → the multi-room act floor never refuses); `5785-5789` `_visible_things`
(`_ANIMATE_ENTITY_KINDS = frozenset()` → rule 2b off: a person entity said as a
thing, by name); `2275-2278` `_line_of_sight_blocked` (→ occluder ignored);
`7900-7905` charter noises (`except Exception: pass  # a story with no charter
adds nothing` — `registry_for` on a chat with no charter returns `{}` and
`charter_noises({})` returns `[]`, so the except only ever hides a real
failure, the "a creature's voice reached no reader at all" regression its own
comment documents). Fix: fail closed where the floor subtracts, and warn
(`ctx.add_warning`) where it hides a delivery. Test: monkeypatch each callee
to raise; assert refusal/warning.

### F15 — A second human seat never knows a place

**Severity: WRONG-SCENE (subtracts). Confidence: PLAUSIBLE.**

`agents/perception.py:4364`: extra players get `"known_places": {}`, so the
far layer names nothing for them (`far_places(..., known=…)`, ruling 3: "a far
place named only once the mind knows it"); `_player_known_places` reads the
primary player's `subject_last_seen` stamps only. Fix: a per-seat ledger, or
the stamps keyed per persona. Test: an extra player standing where the
primary player has stood is told the far place by name iff it has stood there.

### F16 — `_PAIN_CUES` is an unanchored substring scan over free prose

**Severity: WRONG-SCENE (minor). Confidence: PLAUSIBLE.**

`agents/perception.py:7121, 8232`: `pain = any(w in cause for w in _ling("_PAIN_CUES"))`
with en cues `injur, wound, blood, hurt, struck, broke, burn` — "awestruck",
"heartbroken", "burnt-out" all read as pain in a residue. The module's own
comment (381–385) records why this shape was abandoned elsewhere ("paint"
matched "pain"). Pack-driven, so not English-only. Fix: anchor per pack, or
type the cause (`awareness` condition kind). Test: a sedation whose cause is
"awestruck" mints no pain residue.

## Efficiency

**E1 — Every stage builds its perceiver maps outside any read pass.** Where:
the perceiver loops of `perception_establish` (3459–3520), `perception_act`
(3716–3778, after its own `_presence_bodies` call at 3713), `perception_outcome` (4321–4410), and `_delivered_manifest`
inside them; per stage, per perceiver × source. The C12 read pass is opened
only inside `_composer_*`, so each `spatial_rel_between` here pays
`stamp_sound_relation`'s scene-wide `_cache_key` serialisation (no `sound=` in
`_delivered_manifest`) and every sight/proximity derivation runs uncached.
Measured on the owner's live scenes (warm caches), `_source_channels` +
`_proximity_to_sources` + `_behind_sources` for every perceiver:
chat 175 (6 bodies) **413 ms outside, 92 ms inside a pass**; chat 172 (7)
**274 → 76 ms**; chat 179 (4) 83 → 39 ms; outputs byte-identical.
`spatial_rel_between` without a field: 3.6–3.8 ms/pair outside a pass, 0.8
inside. Fix: open `scene_read_pass(sc)` (and one over `prev_scene`) around
the perceiver loop only — it derives and does not write; `_presence_bodies`,
which does write, runs before the loop at onset (3713) and after it (as the
last argument) at the other two stages, and stays outside the pass. Gain ~0.2–0.35 s per
stage on a mid-size scene, three stages a beat.

**E2 — The never-read payload fields (F9) cost as much as the read ones.**
Same loops; measured `_proximity_to_sources` + `_behind_sources` +
`_visible_rooms_for` + `_behind_rooms` + `_focus_target` +
`_ambient_location_for` + `_co_present_company` per perceiver: chat 175
**375 ms**, chat 172 **115 ms** per stage (outside a pass), against 401/244 ms
for the channel maps that ARE read. Deleting them is pure gain.

**E3 — `feature_visibility` three times per observer per stage.**
`_visible_features` (5711), `_visible_things` (5795), `_visible_openings`
(5961) each call it for the same `(observer, sweep)`; it is not behind
`scene_memo`. Inside the pass the inner derivations are memoised, so the
measured cost is small (≈7 ms for 6 observers × 3); memoise it under
`("feature_visibility", name, sweep)`.

**E4 — `_authored_prose_gate` rebuilt three times per observer at onset**
(`_composer_act_views` 7160, 7174, 7184), each re-running
`_composer_unknown_sources` over the chat's identity space. Build once.

**E5 — `present_label_fn` parses `background_presences` twice per call**
(9258–9259: `wget` inside the comprehension's condition and source), per
observer per caller (narration, character, director, spatial_senses).

**E6 — `inspect.signature(_composer_outcome_views).bind(...)` once per
outcome stage** (7772–7773): microseconds, but request-time reflection whose
only purpose is to read three arguments by name; pass them explicitly.

## Already registered

- **UNBUILT_PIPELINE §3.1 (prose matching as a boundary)** — instances in
  this module: `_redact_concealed_from_event` (D1 residual; live only through
  `story/scene.py:2016-2027` `_redact_for_observer` → `recent_events_for_observer`);
  the token-based identity floor (C2/E2) at six perception call sites
  (`_composer_scrub_surface` 5252, `_composer_authored_prose` 5267,
  `_composer_tripwires` 5312, `_repaired_observations` 6576,
  `_scrub_episode_identities` 6641, `gate.written` 5415); C1
  (`_scrub_invented_dialogue`, warn-only, in `_composer_tripwires`).
  **Further instance of the class, not itemised by the register:** PX5's
  `_act_surface_admission` (called at 7398 and 8819) cuts a span that names an
  unseen body by NAME and passes a pronoun reference whole — reproduced:
  `"reaches for Cy's hand …" -> ('', ['Cy'])`, `"reaches for her hand …" ->
  (whole string, [])`. Same structural answer (identity on the event). The
  self-narration strip (`_strip_self_narration` 2523, via `common._sentence_subjects`)
  and `_line_words` (967, a line's identity by its words) are the same class
  applied to self-reference and line binding.
- **UNBUILT_PLATFORM §1.45** — `_deliver_foreground_body_details` and its private
  family (`_SELF_EXPOSED_REGION_CUES`, `_OTHER_EXPOSED_REGION_CUES`,
  `_authored_detail_already_present`, `_BODY_DETAIL_GENERIC`); and
  `knows_identity` write-only (§3.1's struck E1 note).
- **UNBUILT_PERCEPTION §3.8** — perception and `common._delivery_ok` are two
  families of delivery gate (F1/F2 are instances of the drift it predicts).
- **UNBUILT_PERCEPTION §3.3 (≈ line 2734) / UNBUILT_CHARACTERS §1.184** — a
  tell's cue, `how` and `demeanor` carry their giver's scene to observers.
- **UNBUILT_PIPELINE §1.60** — the interpret sheet and `common` disagree about
  whether a concealed action hides its speech (adjacent to F3, a different rule).
- **UNBUILT_PIPELINE §1.69** — sentence splitters (the redactor's routes through `common.split_sentences`).

## Structure notes

**Firewall path inventory (question 1).** Every Director-truth input the module
reads, and the check that gates it per observer:

| input | where read | gate |
| --- | --- | --- |
| establish `state_diff` / resolve's composed scene | `perception_establish` 3423, `perception_outcome` 4141 (`compose_beat_scene`) | standing builders (sight via `feature_visibility`, `visual_level_between`, rear arc; **no card for environment/sound — F1**) |
| establish `entity_states`, `_own_body_state` | 3446, 7511 | keyed to the observer's own name (interoception) |
| `sensory_events` (establish, onset assertions, `diff`), charter noises, treads, doors | 3445, 7020–7040, 7871–7929 | own room (`ambient_percepts`), field (`heard_events`, `_reaches_this_ear`), bearing only (`distant_sounds`); **no hearing card — F1** |
| `dialogue_log` (+ background entries) | 4213–4245 | `speech_percept`: concealment, hearing level, card; **uncited lines on an events-less field — F4** |
| declared/resolved sequences, ledgers | `_outcome_event_stream`, onset loop 7275 | unresolved status, `_act_surface_admission` (PX5), identity scrub, legs, `act_percept` (concealment, sight, rear arc); **concealed actions pre-dropped — F3; unknown kinds dropped — F8** |
| `diff.positions` | 8131–8145 | crossing percept: observer's room at either end, sight at either end (card-graded) |
| `diff.attire/overlays/scales/entities/conditions` | 8046–8095 | only re-earns a description of a body already admitted by sight; the delta text only with `saw_before` |
| `substance_ops` | 4159, 8941–8950 | `substance_event_clause`: observer is target or source, else "" |
| manifests (tells, demeanor) | `_delivered_manifest` | sight (`visual_level_between`, rear arc) or hearing; **card and hearing rule not applied — F2** |
| `res.travel`, `inventory_ops`, looks | `_walk_underway`, `_own_handled`, `_own_looks` | keyed to the observer's own body |
| awareness conditions | 3524, 3794, 4420 | residue for non-awake minds; woken remainder |
| `resolved_event` | 9072–9073 only | reaches the no-op `_inverted_motion_check`; no view is built from it |

No path hands an observer another mind's vitals, interoception or raw
`state_diff`; the leaks found are senses not consulted (F1, F2), and the
inverse failures are F3, F2.3, F5, F15.

**Seams.** See `plans/SPLIT_PERCEPTION.md`: twelve siblings; one true seam
(the composer banner, 4437) and five orphaned comment blocks.

**Monoliths in miniature** (noted, not for rewriting here):
`_composer_outcome_views` 1,309 lines; `_composer_act_views` 556;
`_composer_standing_percepts` 409; `perception_outcome` 322; `perception_act`
223; `_outcome_event_stream` 199; `_source_channels` 142; `present_label_fn`
138. The three stage functions build six near-identical ~22-key perceiver
dicts by hand (3459, 3491, 3740, 4321, 4351, 4385) — the shape where one
copy learns a rule the others do not (F9's dead keys are on all six).

**Stringly protocols** (two representations free to disagree):
`_bare_body_details` (667) parses `story/attire.py:2801-2937`'s English
"`zone: bare — detail`" / "`[worn at, covers nothing]`" text; a format change
there silently empties every bare-region percept. `"an unspecified area"`
(3462 and five more) is a sentinel `composer.environment_percept` matches by
string (`composer.py:1019`).

**Module-level mutable state.** Two never-mutated dicts
(`_SELF_EXPOSED_REGION_CUES`, `_OTHER_EXPOSED_REGION_CUES`, dead family); no
`global`; no `ContextVar`. All caching is on the `PipelineContext` under
string keys (table in the split plan).

## Docs checked

- **CLAUDE.md** — "Perception is deterministic — there is no `perception` model
  role in `providers.ROLES` and the module imports no model seam": HELD
  (`providers.ROLES` has no perception role; the only `llm.*` import is
  `llm.schemas._ANIMATE_ENTITY_KINDS`; it does import `agents.director`
  lazily at 2290, 6988, 7848 for deterministic helpers). "composer composes
  every view from a typed IR; observations re-derived from the rendered view":
  HELD, with `_repaired_observations` filtering them against the repaired
  view. Role graph edge `perception → director`: HELD. Line 109's facade list
  omits `mind.memory`: STALE (outside this module).
- **AGENTS.md:431** — "concealed actions are sentence-level redacted from the
  resolved event per-perceiver …; touch-only sources get surface-translated
  event text": STALE (F12). "per-observer boundaries are STRUCTURAL —
  perception makes no model call … a rendering path cannot ADD information":
  HELD for the rendering path; the admission side misses the card (F1, F2).
  AGENTS.md:456 (`_things_read_by` and its four admissions): HELD, but the
  station admission ignores a blind card (F1).
- **Design.md:336** ("a player whose card says sight is absent was handed a
  body in a lit hall" — fixed): HELD for bodies; the environment half is F1.
  Design.md:479 (felt sound "gated by no sense card"): HELD.
- **`agents/composer.py:253-275` (`_sense_graded`)** — claims the blind-card
  class is closed for every builder: STALE (F1).
- **`world/spatial_senses.py:706-707`** — perception builds each field "with
  the beat's crowds, events and turn index": STALE for the perceiver-level
  fields (F4).
- **`tests/test_perception_card_senses.py` docstring** ("A blind character saw
  the room") — the fix covers bodies and lines; the room is F1.
- **UNBUILT_PIPELINE §3.1** lists `_surface_translate_event` as a live
  boundary ("now fails closed"): STALE — no production caller (F10).
- **UNBUILT_PLATFORM §1.45** (`_deliver_foreground_body_details` dead):
  HELD; the family's four private symbols are dead with it.
- **`docs/design/DESIGN_MODULE_LAYOUT.md`** facade rules — checked against the
  split plan; `FACADE_FAMILIES` holds four families today (`agents.director`,
  `commit`, `mind.memory`, `world.spatial`): HELD.
