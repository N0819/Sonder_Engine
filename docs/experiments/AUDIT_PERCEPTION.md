# Audit: `agents/perception.py` and `agents/composer.py`, read whole

Working notes in the register of
[`AUDIT_DIRECTOR.md`](AUDIT_DIRECTOR.md) and
[`AUDIT_SPATIAL.md`](AUDIT_SPATIAL.md). Both files were read end to end —
4,383 lines of `perception.py`, 1,725 of `composer.py` — rather than
sampled. Nothing was edited; every finding below is FLAGGED, NOT FIXED.

**Baseline revision:** `3e92174` (2026-08-18). Every `file:line` is as of
that revision. `docs/UNBUILT.md` was deliberately not touched (other work in
flight); where a finding is already registered there it says so and is not
re-litigated.

**Method.** Each `def` in `perception.py` was checked for callers with
`grep -rnw` over every `*.py` in the tree, separating production callers
from `tests/` and `tools/`. Each key written into a perceiver dict was
checked against the keys the composer orchestrators actually read
(`awk NR>=3189` over the composer section, extracting `p.get("…")` and
`p["…"]`). Every claim of "nothing reads this" below is that grep, counted.
Claims I could not close are in "Unverified suspicions" at the end.

---

## Part 1 — findings. FLAGGED, NOT FIXED.

### The one leak

#### F1. An identity-concealing disguise does not break recognition in `perception_outcome`, or for the player at onset

`scene.disguise_breaks_recognition(known_to, observer, conceals_identity)`
(`story/scene.py:884-911`) ends `return bool(conceals_identity)`. A missing
third argument is therefore *recognition survives* — the deliberate
fail-open direction argued in that docstring ("a guard must not make a mind
conclude less than its senses support").

Four sites build the body records that feed it. Two set the flag and two do
not:

| site | `disguise_conceals_identity` |
| --- | --- |
| `perception.py:2619-2626` (`co_present`, onset, NPCs) | set (`_ci`) |
| `perception.py:3866-3889` (`_composer_establish`, all bodies) | set (`_ci`) |
| `perception.py:3955-3959` (`_composer_act`'s `actor_body` — the PLAYER) | **absent** |
| `perception.py:4122-4129` (`_composer_outcome`'s `bodies` — EVERY body) | **absent** |

At `perception.py:4122` the value is computed and thrown away in the same
statement: `visible, _, known_to, _ci = _subject_disguise_context(...)`, and
`_ci` never reaches the dict below it. At `2494` the same `_ci` is computed
in `perception_act` and is never passed into `_composer_act` at all.

Two readers consume the flag, and both are on the outcome path:
`composer.observer_display_map` (`composer.py:306-308`) and
`_composer_standing_percepts` (`perception.py:3748-3751`). With the flag
absent, for an observer who already knows the subject:

- `display_map[name] == name` → the **canonical name** is rendered into
  presence, pose, speech attribution, act attribution and crossing sentences;
- `recog and not changed` at `perception.py:3754` → the full authored
  appearance is additionally suppressed as "a familiar stable body".

So a body wearing a mask that the fiction says covers what it is recognised
by is named, by name, in the outcome view of everyone who knew it before —
and `perception_outcome` is the view that feeds the narrator, the character
payloads and durable memory. This is the shape the firewall statement
predicts: a guard that CANNOT fire, failing open and silent.

`_disguise_leak_check` (`perception.py:2282`) does not cover it — it scans
only the disguise's `concealed_terms` (feature words), never the subject's
name.

The tests do not cover it either.
`tests/test_perception_disguise.py:209-238` exercises
`disguise_breaks_recognition` directly (the right object, the wrong layer),
and `tests/test_perception_presence.py:293` — the only end-to-end
`conceals_identity` test — disguises **Tamamo, a cast member**, and runs
`perception_act`, which is exactly the one populated path. No test disguises
the player, and no test asserts anything about a disguise through
`perception_outcome`.

Not in `docs/UNBUILT.md`. §1.43 discusses recognition being a boolean where
the question is graded; it does not record that the boolean is dropped on
two of four paths.

### Guards that cannot fire, and rules with two copies

#### F2. `_delivery_ok` — "the unified delivery gate" — is called by neither `perception.py` nor `composer.py`

`AGENTS.md` § Information boundaries: "The unified delivery gate
`_delivery_ok` in `agents/common.py` consolidates containment, awareness,
sight (including rear-arc/`behind_sources`), and hearing (with proximity)
checks. **Every deterministic delivery site must call it** rather than using
scattered bare checks." `PIPELINE.md` §`perception_outcome` repeats it.

Grep, whole tree, production only:

```
agents/common.py:2360:def _delivery_ok(...)
agents/loops.py:122:                if not _delivery_ok(...)
agents/loops.py:164:                if not _delivery_ok(...)
agents/perception.py:4174:    # Micro-round deliveries were gated by `_delivery_ok` when the loop ran;
```

One definition, two callers, both in `loops.py`, and one comment in
perception that refers to somebody else having called it. The composer
re-derives the same four questions itself —
`visual_level_between`/`entity_arc` (`composer.py:510-536`, `887-890`),
`proximity_rel` (`513`, `662`), `line_hear_level`/`hear_level` (`345-397`),
`concealed_from_observer` (`322-342`) — and the perception orchestrator
re-derives them a third time in `_source_channels` and `_in_plain_view`.
That is the two-representations-of-one-rule shape, on the load-bearing rule.

It is not merely stylistic: see F3 for what `_delivery_ok` applies that the
composer does not.

#### F3. The observer's card `senses` reach no view. Authored blindness, deafness and keen hearing are dead on the main path

`_delivery_ok`'s optional `senses` argument applies
`spatial.sense_adjusted` to the channel grade (`common.py:2396-2409`), and
`loops.deterministic_micro_perception` passes it (`loops.py:98, 126-130`).

`perception.py` computes `senses_of(pers)` / `senses_of(sh)` into every
perceiver at `2390`, `2416`, `2664`, `3105`, `3129`, `3157` — eighteen call
sites across three stages — and no composer orchestrator reads the key
(verified: the only keys read are `awareness`, `id`, `name`, `room`,
`room_name`, `room_notes`, `entity_state`, `behind_sources`,
`proximity_to_actor`, `spatial_to_actor`, `spatial_to_sources`,
`visual_channel_to_actor`, `visual_channel_to_sources`).

So `character_senses` / `persona_senses` — a card field, editable in the UI —
changes what a character perceives in an interaction micro-round and changes
nothing in their onset view, their outcome view, or their memory of the
beat. The two paths disagree inside one turn.

#### F4. Fifteen perceiver-payload keys are computed on every stage and read by nothing

The three stage bodies still assemble the model-era payload. These keys are
written and never read (line numbers are the establish/act/outcome writes):

| key | built by | writes |
| --- | --- | --- |
| `crowds` | `common.crowds_for_room` | 2386, 2412, 2660, 3101, 3125, 3153 |
| `couriers` | `common.couriers_for_room` | 2387, 2413, 2661, 3102, 3126, 3154 |
| `notices` | `common.artifacts_for_room` | 2388, 2414, 2662, 3103, 3127, 3155 |
| `source_manifest` | `_delivered_manifest` (2066-2126) | 3113, 3137, 3166 |
| `scent_channel_to_sources` | `_source_channels` (1495) | every `**_source_channels` splat |
| `proximity_to_sources` | `_proximity_to_sources` / `_co_present_company` | 2394, 2420, 2671, 3108, 3132, 3161 |
| `visible_rooms` | `_visible_rooms_for` → `_behind_rooms` | 2389, 2415, 2663, 3104, 3128, 3156 |
| `behind_rooms` | `_behind_rooms` | 2397, 2674, 3111, 3135, 3164 |
| `room_layout` | `spatial.room_layout` | 2396, 2422, 3110, 3134, 3163 |
| `focus_target` | `_focus_target` | 2398, 2675, 3112, 3136, 3165 |
| `ambient_location` | `_ambient_location_for` | 2385, 2411, 2659, 3100, 3124, 3152 |
| `senses` | `scene.senses_of` | see F3 |
| `attention` | cast `act.goal` | 2390, 2416, 2665, 3105, 3129, 3158 |
| `knows_identity` | `known` ledger | 2391, 2417, 2673, 3106, 3130, 3159 |
| `spatial_facts` | `_perceiver_spatial_facts` | 2399, 3115, 3139 |

`design_notes/13-composer-build.md` §"Honest gaps" item 4 names most of this
list and says the items are "candidates for `docs/UNBUILT.md` when this
merges". They did not land there: grepping `UNBUILT.md` for
`source_manifest`, `sightlines`, `scent percept` and "crowds/couriers" finds
one unrelated hit (line 3199, a Director payload). Per `CLAUDE.md`, UNBUILT
is meant to be the only status list, and this is the largest single block of
built-and-then-unwired behaviour I found.

Two of them contradict maintained guidance rather than a design note:

- `AGENTS.md` § "How off-screen information reaches a mind": "a dispatched
  report is a BODY with a position on a `passable_path` route, advanced on
  the simulation clock, **visible to perception (`couriers_for_room`)**, and
  stoppable". `couriers_for_room`'s only production callers are the six dead
  writes above. A rider is visible to the *Director*
  (`director_views._couriers_view`), and to no mind.
- `Design.md:153` ("Firewall as plumbing"): "percept builders decide
  admission on typed data (delivery gates, hear/sight/**scent** levels,
  containment, rear-arc, concealment, recognition labels)". See F5.

`agents/common.py`'s `crowds_for_room` (`common.py`), `couriers_for_room`
(`common.py:842`) and `artifacts_for_room` (`common.py:893`) have no other
production caller and are therefore dead with them.

#### F5. There is no scent percept. `CHANNELS` declares `"smell"` and nothing ever emits it

`composer.py:94` declares `CHANNELS = ("sight", "hearing", "touch",
"interoception", "smell", "mixed")`. Grepping `composer.py` for `smell`
returns that line and nothing else; no percept builder sets
`channel="smell"`. `scent_level` is imported by `perception.py:71`, called
once at `1495` to build `scent_channel_to_sources`, and that key is read by
nobody (F4).

So the barrier-gated scent ladder in `world/spatial_senses.py` — and
`AGENTS.md`'s "Every perceptual channel is barrier-gated: sight, sound,
scent (`_SCENT_BARRIERS`), and touch" — reaches no mind through perception.
The only way a smell arrives is an authored `sensory_events` entry with
`channel: "smell"` at the opening (`composer.ambient_percepts`, `768-791`).
Note this compounds with `AUDIT_SPATIAL.md` F1: `_SCENT_BARRIERS` is
already recorded there as read by nothing.

#### F6. `body_state_percept` fires only at the opening turn

`_composer_standing_percepts` emits the own-body percept only when its
`entity_state` kwarg is truthy (`perception.py:3775-3778`). It is passed at
`3908` (`_composer_establish`) and at neither `3984` (`_composer_act`) nor
`4219` (`_composer_outcome`).

`entity_state` carries `posture`, `activity` and `held_items`
(`composer.py:716`). A character's own held items and current activity are
therefore in their view on turn 0 and never again — while `character` mode
exists precisely because "a character agent is a stateless LLM call; if it
is not in context, the mind does not have it" (`composer.py:26-28`).

#### F7. `SPATIAL_SCAFFOLD` is a switch that no longer switches anything in perception

`_perceiver_spatial_facts` (`perception.py:338-347`) returns `{}` unless
`os.environ["SPATIAL_SCAFFOLD"]` is set, and when set produces the
`spatial_facts` key — one of F4's dead keys. Setting the variable changes
perception's behaviour not at all. It still works for the narrator, which
carries its own byte-identical copy of the function at
`agents/narration.py:50-57` (a second finding: one env-gated helper, two
definitions). `design_notes/00-PLAN.md:90` and
`design_notes/02-spatial-fov-gaps.md:50, 215` still cite the perception copy
by line number.

#### F8. `_SENTENCE_SPLIT` is defined twice in `perception.py`, and the surviving definition is the weaker one

`perception.py:376-377`:

```python
_SENTENCE_SPLIT = re.compile(
    r"(?<=[.!?…])[\"'”’)\]]*\s+|(?<=[。！？])[」』\"'”’)\]]*\s*")
```

`perception.py:1634-1636`, 1,258 lines later, rebinds the same name:

```python
_SENTENCE_SPLIT = re.compile(
    r'(?<=[.!?])\s+|(?<=[.!?]["”’\'])\s+'
    r'|(?<=[。！？])[」』"”’\')\]]*\s*')
```

Module globals are resolved at call time, so every reader gets the second.
The second is strictly weaker on ASCII: it does not treat `…` as a
terminator and does not tolerate a closing `)` or `]` after the terminator.
Both are matters the first was written for, and the 30-line comment block
above the first (`370-375`) plus a duplicated copy of the same comment above
the second (`1629-1633`) describe behaviour only the dead one has.

The readers matter. `_redact_concealed_from_event` (`2862`) — the concealment
redactor, whose own docstring calls it "the load-bearing guarantee for
concealment" and warns that an unsplittable text has "no safe subset to
keep" — splits on the survivor. So does `_strip_self_narration` (`1691`),
which is live on the composer path through
`_strip_self_narration_quote_safe`, and `_strip_unreachable_bodies` (`1792`).

#### F9. `PERCEPT_KINDS` is read by nothing and is two kinds out of date

`composer.py:88-92` declares twelve kinds. Grep over every `*.py` and `*.md`
in the tree returns exactly one hit: the declaration itself. `Percept.kind`
is a bare `str` with no validation (`composer.py:124`).

Meanwhile `pose_percepts` emits `kind="pose"` (`617-691`) and
`body_part_percepts` emits `kind="body_part"` (`581-614`), and neither is in
the tuple. `_STANDING_ORDER` (`958-965`), which IS read, has both. The two
hand-maintained lists of one thing have already diverged; only the unread
one is wrong, which is how it went unnoticed.

#### F10. The dim-figure grouping rule compares against the English constant while the labels come from the active pack

`composer.py:463-473` records the fix and its reason: the dim-figure label is
now read at use time from the active pack via `_dim_figure()`, "Bound from
the English pack at import before, so a Japanese reader in a dim room was
told about 'an indistinct figure'". `presence_percepts:553` uses
`_dim_figure()`.

`_render_presence_group` — the consumer — was not converted
(`composer.py:1053-1057`):

```python
if n > 1 and clause.startswith(DIM_FIGURE + " "):
    word = _COUNT_WORDS.get(n, str(n))
    rendered.append(
        f"{word.casefold()} {DIM_FIGURES}"
        + clause[len(DIM_FIGURE):].replace(" is ", " are ", 1))
```

`DIM_FIGURE`/`DIM_FIGURES` (`468-469`) are the English compat exports. In any
non-English story the `startswith` can never be true, so the counting rule
that exists because "three of them in one room rendered as the same sentence
three times (282 views in the corpus replay)" silently does not run. The
`" is "` → `" are "` rewrite is English grammar hard-coded into a
pack-selected renderer besides.

#### F11. The English-literal tables that survived are on the live paths; the `_ling` tables that were built are on the dead ones

`perception.py:355-367` explains at length why the module's recognition
tables must be read from the active pack at use time. Six entries exist,
authored in both packs
(`language_packs/{en,ja}/cards/linguistics.json` → `agents.perception`:
`_AMBIGUITY_CUES`, `_CHANNEL_CUES`, `_INTENSITY_CUES`, `_PRONOUN_SUBJECT`,
`_SELF_DIRECTED`, `_SUDDENNESS_CUES`).

Five of the six are read only by `_observations_from_clean_views` /
`_atom_channel` / `_cue_hits`, all of which have no production caller (F12).
The one live entry is `_PRONOUN_SUBJECT`, in `_redact_concealed_from_event`,
whose only production caller is `story/scene.py:1232` (F17).

Meanwhile the tables that DO run on the composer path are English literals:

- `_LOOK_VERBS` (`3215-3218`) → `_explicit_look_intent` (`3221`) → decides
  `full_render` for the player's outcome view. A Japanese story never
  re-earns a full render on an explicit look.
- `_RAPID_MOVEMENT_VERBS` (`80-82`) → `_declares_rapid_movement`, live at
  `4024` (the continuity floor inside `_composer_act`) and at `2262-2264`.
- `_SIGHT_ASSERTION` (`388-394`) → `_strip_self_narration`'s refusal floor,
  live through `_strip_self_narration_quote_safe`.
- `_RAISING`/`_LOWERING` (`2234-2236`) → `_inverted_motion_check`, live at
  `4374`.
- The residue pain-cue tuple `("injur","wound","blood","hurt","struck",
  "broke","burn")`, hand-duplicated at `3972-3974` and `4208-4210` — two
  copies of one table, ten lines of one function apart.

This is the `literal-guards-fail-when-models-rewrite` shape one layer over:
the guard is fine, the language it is written in is not the language the
story is in.

### Dead code

#### F12. Sixteen module-level functions in `perception.py` have no production caller

Verified with `grep -rnw` over every `*.py`, splitting `tests/` and
`tools/`. "Tests only" means the only non-`perception.py` references are
under `tests/`.

| function | line | callers |
| --- | --- | --- |
| `_observer_body_labels` | 1022 | **none anywhere** |
| `_strip_onset_rendering` | 1232 | **none in code** (cited by 3 design notes + `Design.md:198`) |
| `_pronouns_for_perceiver` | 1602 | **none anywhere** |
| `_scrub_view_for` | 1804 | **none in code** (cited by `Design.md:196`, `UNBUILT.md:3364`) |
| `_observer_scene_payload` | 808 | tests only — docstring says so |
| `_observations_from_clean_views` | 717 | tests only |
| `_observation_spans` / `_atom_channel` / `_cue_hits` | 416 / 409 / 405 | reachable only from the above |
| `_deliver_standing_sensations` / `_contact_already_felt` | 482 / 443 | tests only |
| `_deliver_substance_events` | 530 | tests only |
| `_deliver_foreground_body_details` / `_authored_detail_already_present` | 672 / 641 | tests only |
| `_novel_visible_appearances` | 1043 | tests only |
| `_strip_unknown_pose_claims` | 1071 | tests only |
| `_inject_onset_sequence` / `_inject_onset_speech` / `_concealed_from_perceiver` | 1335 / 1126 / 1112 | tests only (and see F19) |
| `_observed_pronouns` | 1576 | tests only |
| `_touch_only_sources` / `_surface_translate_event` | 2703 / 2787 | tests only |
| `_observer_facing_sequence` | 2309 | reachable only from dead `perception_act` locals (F13) |
| `_delivered_manifest` / `_tell_acuity` / `_focus_target` (as payload) | 2066 / 2038 / 1917 | payload-dead (F4) |
| `_co_present_company` | 1960 | payload-dead: both its outputs land on keys `_composer_act` never reads |

`_strip_self_narration`, `_strip_unreachable_bodies`, `_bare_body_details`,
`_self_body_detail`, `_source_channels`, `_in_plain_view`,
`_previous_open_group_continuity`, `_saw_across_beat`, `_with_comm_channel`,
`_subject_disguise_context`, `_subject_concealed_terms`,
`_disguise_leak_check`, `_inverted_motion_check` and `_ambient_location_for`
ARE live and were checked individually. `_dialogue_hear_level` (295) has no
pipeline caller but is a real entry point for `tools/perception_quality.py`
(`tools/perception_quality.py:99, 345`), exactly as its docstring claims.

`Design.md:198` already records three of these
(`_strip_onset_rendering`, `_inject_onset_sequence`, `_inject_visible_actor`)
as "UNREACHABLE — dead code calling dead code … retained pending removal",
and `UNBUILT.md:~2205` records `_inject_visible_actor`. The other thirteen
are recorded nowhere.

Two consequences worth stating separately:

- **`_touch_only_sources` + `_surface_translate_event` are the touch-only
  firewall guard**, and `AGENTS.md`'s "Perception or information leakage"
  routing row and `AGENTS.md`'s body-enclosure row both point at them. They
  cannot fire. `design_notes/13-composer-build.md` argues this is correct —
  the composer never consumes `resolved_event`, so there is nothing to
  surface-translate — and I agree; the routing table does not say so.
- **`_scrub_view_for` is the wrapper `Design.md:196` names as the home of
  `_strip_unreachable_bodies`** ("`_strip_unreachable_bodies` runs in
  `_scrub_view_for` beside `_strip_self_narration`"). Neither runs on the
  live path; `_composer_tripwires` runs identity + self-narration +
  invented-dialogue and not the unreachable-body pass.

#### F13. About 110 lines of dead computation inside the three stage bodies

Each stage still assembles the model call's inputs and then hands only a
subset to the composer. Assigned-and-never-read locals:

- `perception_establish`: `declared` (`2425-2437`, 13 lines),
  `awake_perceivers` (`2444-2445`).
- `perception_act`: `action_desc` (`2513-2519`), `overt_player_speech`
  (`2527-2534`), `observer_sequence` (`2546-2549`),
  `observer_action_attempt` (`2550-2552`), `concealed_actions`
  (`2557-2571`), `raw_speech`/`raw_speech_volume`/`primary_speech_concealed`
  (`2576-2581`), `action_onset` (`2584-2603`), `awake_perceivers`
  (`2695-2696`). `_composer_act` receives `interp`, `speech_elems` and
  `action` and rebuilds the onset sequence itself at `3934-3938`.
- `perception_outcome`: `npc_dlog` (`3006`), `fallback_dlog` (`3015-3019`),
  `concealed` (`3024-3056`, 33 lines and four loops), `awake_perceivers`
  (`3179-3180`).

Three of these carry comments asserting live safety properties that are now
about nothing: `action_onset`'s "Build action onset for reaction
eligibility" (`2583`), `fallback_dlog`'s "the no-LLM fallback is NOT that
gate … so it fails closed on the whole class" (`3008-3014`), and
`concealed`'s implicit contract with `_redact_concealed_from_event`.
Concealment itself is still enforced, at the percept level
(`composer.concealed_from_observer`, called from `speech_percept:821` and
`act_percept:879`) — the `concealed` list is simply not how.

`awake_perceivers` is the one worth reading twice: computed identically in
all three stages, never used, while the actual consciousness gate is the
`if p.get("awareness") in NON_AWAKE_GATED` branch inside each composer
orchestrator (`3897`, `3969`, `4199`). Correct behaviour, three dead
variables that look like the gate.

#### F14. Crossing percepts are not filtered to bodies

`_composer_outcome` builds `moves` from every key of `state_diff.positions`
(`4166-4172`) and emits a `crossing_percept` for each
(`4303-4322`). `AGENTS.md`'s body-enclosure row states the constraint that
makes this wrong: "`positions` legitimately keys objects and unregistered
presences by entity id".

Where the mover is an object, `display_map.get(mover)` is None and
`_recognizes(mover, recognized)` is False, so `label = "a figure"` and the
view says *"A figure arrives."* about a crate being carried between rooms.
`design_notes/13-composer-build.md` gap 5 records the label choice for
background movers; it does not record that objects are in the same list.
Every other body-scoped predicate in the engine goes through
`spatial._is_body_entity`; this loop does not.

#### F15. `==` where the module elsewhere uses `same_subject`, inside one function

`AGENTS.md`: "**one being, one name.** A being routinely carries two at once
(a cast display name and a scene entity id); five separate defects here were
a single `==` between them, including a firewall that failed OPEN."

`_composer_outcome` uses both, twelve lines apart:

- `4236`: `if speaker == name or (pid == "player" and is_player_speaker(...))`
  — the observer's own line is suppressed by string equality.
- `4277`: `if actor == name or actor in behind:` — the observer's own act.
- `4216`, `3901`, `3980`: `others = [b for b in bodies if b["name"] != name]`.
- `4304`: `if same_subject(sc, mover, name): continue` — correct.

`_standing_contacts_for` (`523-525`), `_touch_only_sources` (`2753-2771`),
`pose_percepts` (`643`, `647`) and `_composer_bare_details`' caller all use
`same_subject`. The failure mode is not a leak — it is an observer being
handed their own speech and their own act as though someone else did them,
with `self_forms` the only thing between that and the page.

### Silent tolerance, stale comments, stale docs

#### F16. `OBSERVATION_DEFAULTS["intensity"]` can no longer be reached by the composer, and its measured justification is from the retired path

`composer.py:1598-1622` justifies omitting six near-constant observation
fields with a corpus measurement: "`intensity` sat at its 0.35 base in 99%
of rows".

That measurement is of `_observations_from_clean_views`
(`perception.py:749`), which computed `min(1.0, 0.35 + 0.2 * cue_hits)` and
is now dead (F12). `observations_from_render` computes
`min(1.0, 0.35 + 0.4 * p.salience)` (`composer.py:1668`), and the minimum
salience any builder assigns is `0.2` (`environment_percept:452`). So
`intensity` is now ≥ 0.43 on every atom the composer can produce and is
emitted on every observation — the field the comment says is dropped 99% of
the time is dropped 0% of the time. `suddenness`, `source_atom_id` and
`perceiver_id` still compact as described.

#### F17. `_redact_concealed_from_event` lives in `perception.py`, is called only from `story/scene.py`, and is credited to `perception_outcome` by two maintained documents

Its one production caller is `story/scene.py:1232`, inside
`recent_events_for_observer` — a reverse dependency (`story/` importing an
`agents/` role module at call time).

`PIPELINE.md` §`perception_outcome`: "Concealed actions are sentence-level
redacted from the resolved event text per-perceiver via
`_redact_concealed_from_event`." `AGENTS.md`'s "Perception or information
leakage" row names it as one of perception's three leak-relevant functions.
`PIPELINE.md`'s "Where to debug" table sends a reader with a concealment
symptom to it.

The code is right and the docs are wrong in the direction that costs the most:
`perception_outcome` never reads `resolved_event` into a view at all
(`perception.py:3189-3213` states this explicitly), so there is nothing left
to redact there, and a reader debugging a concealment leak is pointed at a
function on the *memory* path.

#### F18. `pose_percepts`' stated invariant is now inverted

`composer.py:650-661`: "**A POSE IS NEVER MORE REACHABLE THAN A PRESENCE.**
… Presence had already declined to mention her — `proximity_rel` answers
None across rooms — while this gate checked only sight and arc".

`presence_percepts` has since grown the cross-room branch
(`composer.py:515-533`): when `proximity_rel` is None it does *not* decline,
it falls back to `tier="beyond"` plus the room label. `pose_percepts:662`
still returns early on `proximity_rel(...) is None`. So presence now outruns
pose: a body watched through observation glass is admitted as present and
never as posed. That is a defensible subtraction — but the comment states
the opposite rule as the reason for the code beneath it, and the next reader
who adds a third body percept will follow the wrong rule.

#### F19. Two tests assert on source layout; one of them guards dead code

`tests/test_self_surface_when_enclosed.py:107-118`:

```python
src = inspect.getsource(perception._inject_onset_sequence)
assert "_self_cannot_see_own_surface(" in src
assert src.index("_self_cannot_see_own_surface(") < src.index("_inject_action(")
```

Its own docstring names the failure it is defending against: "or it is a
well-tested function nothing calls". `_inject_onset_sequence` has no
production caller (F12), and `_self_cannot_see_own_surface`
(`perception.py:1303`) is called from nowhere else — so the test now
asserts the internal statement order of dead code, and the condition it
exists to prevent has already happened. (The property is not lost: on the
composer path an actor never receives their own act surface at all, because
`_composer_act` builds no perceiver for the player and `_composer_outcome`
skips `actor == name`. It is enforced by a different mechanism, and nothing
says so.)

`tests/test_perception_self_narration.py:100-104` also greps source
(`_composer_finish_observer` must mention `_composer_tripwires`), but that
one guards a live seam and is defensible; flagged only because the technique
breaks on any reorganisation, per `AUDIT_DIRECTOR.md` finding 11.

Separately, five test files pin functions with no production caller as
though they were floors: `test_observation_derivation.py`
(`_observations_from_clean_views`), `test_continuous_contact_sensation.py`
(`_deliver_standing_sensations`), `test_substance_transfer.py`
(`_deliver_substance_events`, `_observer_scene_payload`),
`test_body_pose.py` (`_novel_visible_appearances`,
`_strip_unknown_pose_claims`, `_observer_scene_payload`),
`test_perception_unreachable_body.py` (`_strip_unreachable_bodies` — live as
a tripwire only through `_strip_self_narration_quote_safe`'s sibling, but
not through the `_scrub_view_for` wrapper the test's own header describes).
`UNBUILT.md`'s note on `_inject_visible_actor` names this exact hazard:
"passing tests and no effect, which is the worst combination available: it
reads as a live floor."

#### F20. Micro-round additions are appended after the tripwires and given a hand-stamped observation

`perception.py:4343-4362`. `_composer_finish_observer` has already run
`_composer_tripwires` and `observations_from_render` on `rendered.text`;
the micro-loop's pre-rendered sentences are then concatenated onto
`clean_views[pid]` by `_append_micro_view` (a bare `"\n\n".join`,
`common.py:2792-2795`) and given a literal observation atom with
`channel: "mixed"`, `fidelity: "rendered"`, `intensity 0.5`,
`suddenness 0.2`, `ambiguity 0.3`, `directed_at_self: False`.

The identity floor half is already `docs/UNBUILT.md` §1.39. The half worth
adding: the observation for that text is *asserted* rather than derived, so
it is the one atom in the payload whose metadata is not a function of an
admitted percept — the property `observations_from_render`'s docstring
(`composer.py:1651-1658`) claims for the whole projection.

#### F21. `_composer_finish_observer` assumes a pack renderer returns a `RenderedView`

`render_view` (`composer.py:1346-1369`) wraps the adapter call in
`try/except Exception` and falls back to English — a deliberate floor, well
argued. `_composer_finish_observer` (`perception.py:3848-3859`) then reads
`rendered.text`, `rendered.standing_keys` and `rendered.described` with no
guard. A pack adapter that returns successfully but with a different shape
raises `AttributeError` outside the protected region and kills the turn —
the exact outcome `_safe_renderer`'s docstring says was being fixed ("that
is a configuration fault, and it was reaching callers as a dead turn").
Same for `observations_from_render`'s `rendered.spans` (`composer.py:1662`).

#### F22. Small duplications

- `_addresses` is defined identically at `perception.py:282-292` and
  `composer.py:400-406`. The perception copy has the 12-line docstring; the
  composer copy is the live one. `docs/UNBUILT.md` §1.38 already treats them
  as one rule with two readers.
- `_MAX_OBSERVATION_ATOMS = 8` at `perception.py:398` (dead) and
  `composer.py:1596` (live); `_MAX_SPAN_SENTENCES = 3` at
  `perception.py:402` (dead) against the literal `< 3` at
  `composer.py:1688` (live).
- `_MASK_TOKEN = re.compile("\\x00Q\\d+\\x00")` at `perception.py:3484`
  encodes the token format that `common.py:5035` defines as
  `_VIEW_MASK = "\x00Q%d\x00"`. Two spellings of one wire format in two
  modules; changing the mask in `common.py` silently disarms
  `_strip_self_narration_quote_safe`'s refusal check.
- `_perceiver_spatial_facts` exists twice, `perception.py:338` and
  `narration.py:50` (F7).

#### F23. `_subject_disguise_context`'s payload is model prompt text with no model

`perception.py:2183-2196` builds a `payload` dict containing
`capability_note` and `instruction` — two paragraphs of second-person
instruction to a perception LLM ("Every observer VISUALLY perceives only
outward_visible_appearance; never describe a concealed feature as seen…").
Its only consumers are the dead `action_onset["subject_disguise"]`
(`2603`) and a truthiness test at `4143`. Already registered as
`docs/UNBUILT.md` §A8 residual ("`concealed_truth` … now reaches no payload
in either pass … dead code that reads like a live floor"); repeated here
because the knowledge half of the disguise design goes with it — an observer
in `known_to` no longer receives the concealed truth as knowledge anywhere,
and `perception.py:2957-2960`'s comment still says "The knowledge layer (who
KNOWS the truth) rides the payload."

---

## Part 2 — what the code actually does, checked against the documents

Verdicts: **RIGHT** / **STALE** (doc describes something the code stopped
doing) / **LOST** (code stopped doing something the doc still promises).

### `agents/composer.py`

**Layer A — the eleven percept builders.** `environment_percept`
(room, notes, light; None for an unresolvable room), `presence_percepts`
(sight level, within-room tier or cross-room room-label, side, arc; rear arc
declined; degraded sight keeps a recognised name and takes a stranger's
descriptor), `pose_percepts` (posture at `shapes`, everything at `full`),
`appearance_percept` (first mention or `force`), `body_state_percept`,
`contact_percepts` (clause built by `spatial.contact_sensation`, empty for a
non-party), `body_region_percepts`, `body_part_percepts`,
`ambient_percepts` (room-scoped), `residue_percepts`, plus the event
builders `speech_percept` (concealment → `line_hear_level` → fragment
degradation), `act_percept` (concealment → rear arc → sight),
`substance_percept`, `crossing_percept` (arrival/departure bands outside the
event counter). Every one is a subtraction and none reads the database.

**Layer B.** `_render_view_english` orders standing state by
`_STANDING_ORDER`, groups presence into one sentence per fidelity, renders
events in `order_key` order, and leads with events when any is sudden.
`render_view`/`render_episode` dispatch to the story pack's adapter and fall
back to English on any exception. `observations_from_render` merges
consecutive atoms only when channel, fidelity class and self-direction all
match, degrading to the weakest verdict when the cap forces a merge.

- `Design.md:153` ("Firewall as plumbing"): **RIGHT except for "scent"** —
  every other clause verified against source (F5).
- `AGENTS.md` § "Per-observer boundaries are STRUCTURAL, not prompted":
  **RIGHT**. `render_view`/`render_episode` take percepts and mode
  parameters only; no scene, no DB. Verified by signature.
- `PIPELINE.md` §`perception_act`, "It also emits structured observations …
  reconstructed from each final scrubbed prose view after output validation
  … decomposes a view into per-channel atoms … grades intensity, suddenness
  and ambiguity **by cue density**": **STALE**. That is
  `_observations_from_clean_views`, which is dead. The live projection reads
  the axes off the IR (`p.channel`, `p.salience`, `p.suddenness`,
  `p.data["directed_at_self"]`), and the invariant it preserves is stated
  correctly in `composer.py:1651-1658` rather than in the guide.
- `composer.py`'s own module docstring, "Module discipline: imports
  `agents/common.py`, `spatial.py`, `scene.py` only — never another role
  module": **RIGHT**, verified against the import block (`53-81`) and the
  two deferred imports (`common.observable_action_text` at `882`,
  `spatial.room_of` at `488`).

### `agents/perception.py` — the orchestrator

Three stage bodies, each of which resolves the scene, previews what the beat
has already made true, assembles a perceiver list and a body list, and hands
off to one `_composer_*` function. Confirmed by
`tests/test_perception_has_no_model.py`'s AST assertion that each stage has
exactly one `return` and it is that call.

- `perception_establish`: merges `director_establish.state_diff`, previews
  `apply_attire_diff`, builds perceivers for the player and every cast
  member, overlays the establish diff onto the awareness map, renders every
  observer with `full_render=True`.
- `perception_act`: previews `contact_assertions` and
  `state_assertions` onto a copy of the scene (`preview_player_state_assertions`,
  `2486`), builds perceivers for `flow.reactors` only, and hands the player's
  declared sequence to `_composer_act`. **RIGHT** against `PIPELINE.md`
  §`perception_act`'s state-assertion account and `AGENTS.md`'s "interpret is
  not a lesser authority" row, clause for clause.
- `perception_outcome`: deep-copies the resolve diff, runs
  `dedup_minted_rooms` on it, merges, previews attire, refreshes
  `came_from`/`focus`/`facing` on the merged scene, merges
  `background_react` into the dialogue log rather than mutating the
  persisted resolve step, then composes.

Doc verdicts:

- `PIPELINE.md` §`perception_establish` — five paragraphs about "a
  generative perception model", "After the model returns, perception applies
  a deterministic body-detail fidelity floor", "This is semantic fidelity,
  not quotation fidelity: the model may rephrase": **STALE in full**. There
  is no model. The floor described is `_deliver_foreground_body_details`
  (`672`), which has no production caller; the equivalent live path is
  `_composer_bare_details` (`3289`) → `body_region_percepts`, which renders
  the authored bare-surface detail unconditionally rather than restoring it
  when a model generalises it away. Same parser (`_bare_body_details`), same
  gating (`observer_body_regions`), different contract.
- `PIPELINE.md` §`perception_act`, "The model supplies ambient
  observer-specific sensory prose, but it does not own the chronology … Model-
  rendered copies of declared speech/action are removed … Delivery
  metacommentary … is discarded": **STALE**. `_strip_onset_rendering` and
  `_DELIVERY_META_RE` are dead; chronology is `Percept.order_key`, which
  `Design.md:198` already describes correctly.
- `PIPELINE.md` §`perception_outcome`, "`_redact_concealed_from_event`" and
  "The unified delivery gate `_delivery_ok` … for every deterministic
  delivery site": **STALE** (F17) and **STALE** (F2) respectively.
- `PIPELINE.md` §`perception_outcome`, "Observer scene projections include
  only visible bodies' pose snapshots plus the observer's own … A
  legacy/current body without a snapshot appears in `pose_unknown`;
  action-onset removes model-authored static pose claims for that roster":
  **STALE**. `pose_unknown` is built only inside `_observer_scene_payload`
  (`921-933`), which is test-only, and `_strip_unknown_pose_claims` has no
  caller. The live rule is simpler and better: `pose_percepts` emits a pose
  only where one exists, so absence is silence rather than a roster.
- `PIPELINE.md` §`perception_outcome`, "Full authored appearance is scoped
  to discovery or a structural visible change; familiar stable card
  description is withheld": **RIGHT** —
  `_composer_standing_percepts:3752-3756` plus `appearance_changed`
  (`4134-4144`) plus `render_view`'s `described` ledger.
- `AGENTS.md` "Perception or information leakage" routing row: **partly
  STALE**. Of the three perception symbols it names, `_source_channels` is
  live and central, `_composer_outcome` is live and central, and
  `_redact_concealed_from_event` is on the memory path (F17). Of the composer
  symbols it names, all six percept builders plus `render_view`/
  `render_episode` are live and are the right place to look.
- `AGENTS.md`'s claim that "background-presence names pass through that
  presence's OWN recognition ledger": that gate is in `background.py`; on the
  perception side a background speaker enters `sources` (`3022-3023`) and
  hence `ident_roster` (`4150-4153`) and `_composer_identity_space`
  (`3421-3431`), so the tripwire and the authored-prose gate do cover their
  names. **RIGHT**.
- `Design.md:196` "A view describes only bodies the perceiver can reach":
  **RIGHT in effect, STALE in citation** — the mechanism named
  (`_strip_unreachable_bodies` in `_scrub_view_for`) is unwired; the property
  holds because Layer A never admits a channel-less body.
- `Design.md:198` "The repair functions that did this over prose … are
  UNREACHABLE — dead code calling dead code … retained pending removal":
  **RIGHT**, and the only place in the maintained docs that acknowledges any
  of the dead surface. It names three of the thirteen (F12).
- `Design.md:157` "deterministic perception excludes a mind's own conduct
  from its own view": **RIGHT** — `_composer_act` builds no perceiver for the
  player, `_composer_outcome` skips `actor == name` and `speaker == name`
  (with F15's caveat about the comparison).
- `design_notes/13-composer-build.md` §"Honest gaps": **RIGHT and
  unpropagated.** Its item 4 is the single most accurate description of F4
  anywhere in the tree, and it was never carried into `docs/UNBUILT.md`,
  which `CLAUDE.md` designates as the register that wins. Its item 1
  (poses not rendered) has since been BUILT — `pose_percepts` exists — so the
  note is stale in the reader's favour for once.

### The identity floor, end to end

Worth stating because it is the part that most clearly works. Three gates,
in this order:

1. **Admission-side, per observer.** `_authored_prose_gate` (`3669`) wraps
   `_composer_authored_prose` and is applied to room notes (`3731`),
   appearance/overlay descriptions (`3771`) and authored ambient events
   (`_gated_ambient_percepts`, `3690`). `_composer_scrub_surface` (`3541`) is
   applied to every act surface (`4028`, `4293`). Both scrub against
   `_composer_identity_space` (`3368`) — cast, off-roster `chat_chars`,
   extra players and background presences — which is the fix for the measured
   "69 surviving identity leaks … dominated by `room_notes` naming an
   off-roster character".
2. **Labelling.** `observer_display_map` + `assign_stranger_labels` decide
   what each observer may CALL each body, with widening and an ordinal last
   resort. This is where F1 fails.
3. **Output tripwires.** `_composer_tripwires` (`3600`) re-runs identity
   substitution (repairs), self-narration (repairs only where it can prove no
   delivered line is at risk), and invented dialogue (warns only). The
   grading argument in that docstring — 382 fires, 167 taking a quote with
   them, 33 lost player-view lines — is the best-evidenced piece of reasoning
   in either file.

The floor's other direction (`_composer_self_forms`, `3330`, plus
`_joint_stranger_labels`, `3314`) is live and matches design note 20 and
`AGENTS.md`'s epithet clause exactly.

---

## Unverified suspicions

Stated as suspicions because I could not close them without running code or
reading a live database, both of which were out of scope.

1. **`speech_percept`'s `via` fields may be reachable only when
   `comms_link` returns a dict AND the two are in different rooms**
   (`composer.py:859`). `line_hear_level` returns `"full"` for ANY
   `comm_channel` (`384-385`), including same-room, so a same-room PA
   announcement is rescued to full and rendered as an ordinary in-room voice.
   Probably harmless; I did not establish whether `comms_link` can return a
   channel for a same-room pair.
2. **`_previous_open_group_continuity` may no longer have live data to
   rescue.** It exists for checkpoints predating the near-group position
   repair, runs two DB queries per turn (cached), and its evidence is a
   previous turn's `director_resolve` diff plus a checkpoint blob. Whether
   any reachable checkpoint still carries the contradictory shape is a
   corpus question. If none does, this is ~120 lines and two queries per turn
   of dead compatibility.
3. **`_composer_prev_ledger` returns `{}` after a checkpoint restore that
   removes the previous turn's perception step**, which makes the player's
   next view a full render rather than a delta. Fail-open (more content, not
   less), so not a leak — but it means "the player's view is a delta" is not
   quite invariant across reroll, and I did not test it.
4. **`ambient_percepts` admits a roomless authored event to every
   observer** (`composer.py:777`, `if room and observer_room and room != …`).
   Both `room` and `observer_room` falsy ⇒ admitted. At establish that is
   scene ambience and correct; whether any later path can produce a roomless
   sensory event for a perceiver in a sealed interior I did not check —
   `_ambient_location_for`, the helper that would have answered it, is one of
   F4's dead keys.
5. **`compact_observation` treats `0` and `False` as equal**
   (`composer.py:1645`, `value == default`). No current field is affected
   (`directed_at_self` is the only bool and its default is `False`), but a
   future numeric field defaulting to `False`/`0` would compact wrongly.
