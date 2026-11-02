# Audit — `agents/composer.py` (2026-11-01)

Auditor's scope: the deterministic perception composer — percept builders
(Layer A), the English reference renderers (Layer B), and the observation
projection. Read-only; every line number is the current working tree
(`84f3de23`, branch `worktree-jev-character-tracking`, clean). Snippets were run
with `.venv/bin/python` importing the module and calling pure functions (some
snippets monkeypatched the module object inside their own process only); no
test file was run, no database touched.

## Scope read

**Read in full:** `agents/composer.py` 1–7691 (every line, in order).

**Read in part, for tracing (not audited):**
- `language_adapters/japanese.py` 28–100, 236–320, 391–437, 519–680 (the
  `_sentence` dispatch, `render_view` head, residue path) — read, because the
  brief asks how the Japanese pack gets its words; the rest skimmed by grep.
- `agents/perception.py` ranges 2933–2990, 3440–3500, 4525–4540, 4940–5000,
  5438–5470, 6330–6432, 6570–6720, 6800–6900, 8040–8100, 8280–8320,
  8600–8700, 8770–8860, 8990–9050 (callers of the builders; how `display`,
  `can_see`, `force`, `room` are computed; `_repaired_observations`).
- `agents/common.py` 1086–1130 (`_conceal_from_targets_observer`), 9521–9561;
  `agents/director_floors.py` 2290–2340; `agents/director.py` 5445–5475;
  `agents/background.py` 214–262; `agents/loops.py` 385–415; `agents/character.py`
  4490–4540; `story/scene.py` 1236–1270, 2005–2030; `world/spatial_senses.py`
  1014–1060; `world/spatial_geometry.py` 1316–1330; `language_runtime/__init__.py`
  520–800; `llm/schemas.py` 2090–2140; `tools/project_check.py` 1682–1800,
  2600–2700; `tests/helpers.py` 120–211; the seven patch-site tests (excerpts).
- Docs: `AGENTS.md` composer rows and invariants (655–690, 880–892),
  `Design.md` rows 164, 302, 330, `agents/README.md` 1–80, `CLAUDE.md`,
  `docs/design/DESIGN_MODULE_LAYOUT.md`, `docs/design/SPLIT_MEMORY.md`,
  `docs/experiments/AUDIT_COMMIT.md` 1–250, and the register entries cited below.

## Findings

Counts: **LEAK 3 · WRONG-SCENE 6 · SILENT-NOOP 1 · DEAD 1 · STALE-DOC 1**
(PERF items are in § Efficiency).

### F1 — `observations_from_render` tells a mind a line was addressed to it when the words did not carry

- **Severity:** LEAK · **Confidence:** CONFIRMED (snippet)
- **Where:** `agents/composer.py:4919-4920` (`speech_percept` data),
  `4882-4883` (the seen-speaking-unheard percept), `5343-5345`
  (`communication_percept`), projected at `7618-7620`.

```python
"directed_at_self": _addresses(
    entry.get("intended_target"), observer_name),          # 4919, every fidelity
...
"directed_at_self": bool(
    percept.data.get("directed_at_self")                    # 7618, copied into the row
    or percept.channel == "interoception"),
```

- **Scenario.** A guard in the next room says "Tomorrow you hang." to the
  prisoner at normal volume through a door. The words do not carry; the voice
  does (`fidelity="voice"`). The view says `A voice — the words do not carry.`
  The observation row the character payload carries
  (`character.py:4512` → `perception_packet`) and the narrator packet carries
  (`narration.py:1864`) says `"directed_at_self": true`. The same line said to
  the cook produces the identical sentence and no such flag. Run:

```
TEXT : 'A voice — the words do not carry.'
OBS  : {... 'kind': 'speech', 'ambiguity': 0.75, 'directed_at_self': True ...}   # to the prisoner
TEXT2: 'A voice — the words do not carry.'
OBS2 : {... 'kind': 'speech', 'ambiguity': 0.75 ...}                             # to the cook
```

  So the second representation carries a fact the first cannot — the exact
  property the module (`cue_percept`: "Observations derive from the render, so
  a reader downstream cannot recover more than the page says"), AGENTS.md
  ("A rendering path structurally cannot ADD information") and CLAUDE.md
  ("the second representation cannot expand the information budget") claim
  cannot fail. The one bit the design DOES grant for an unheard line is
  `own_name` ("your name was said"), and only when a name form is in the line;
  `directed_at_self` hands over "it was said to you" without that.
  Same for a communication heard in pieces (`"speaks indistinctly"` + flag).
- **Verified by:** `speech_percept` → `render_view` → `observations_from_render`
  with `line_hear_level` stubbed to `none` and `voice_carries` to True (the
  shape of `tests/test_composer.py:1025`); traced the consumers (the character
  payload is the model-read JSON; `llm/schemas.py:2121` keeps the field). The
  register's `UNBUILT_WORLD §1.28` calls the observation metadata "consumed by
  nothing" in code — the model reading the payload is the consumer.
- **Fix:** set `directed_at_self` on a speech/communication percept only where
  the rendered sentence carries the addressee (fidelity `full`), plus the
  `own_name` case the text does say. **Test:** two `speech_percept`s at `voice`
  (and at `fragment`, and a fragmentary `communication_percept`) differing only
  in `intended_target` must produce byte-identical `observations_from_render`
  rows.

### F2 — A body met for the first time is filed as a CHANGE because `force` (a world fact) decides the observation phase

- **Severity:** LEAK (minor: one bit of the past state) · **Confidence:** CONFIRMED (snippet)
- **Where:** `agents/composer.py:7597-7599`; `force` set by `agents/perception.py:6421-6422`
  (`force=changed`, where `changed` is the objective "this body's visible form
  moved this beat", gated on `saw_before` only for the delta).

```python
phase = ("event" if percept.order_key is not None else
         "change" if percept.data.get("force") or
         percept.data.get("beat") else "state")
```

- **Scenario.** A woman changes her coat in the hall; the player walks in that
  beat and sees her for the first time. Her verdict for the player is `first`;
  the view says `You see a woman in a grey wool coat.` The observation is
  `phase: "change"`, so `perception_packet` files it under `changes_noticed`
  for the character and the narrator — "this body changed" — to an observer
  who never saw it before. Run (player and character tiers alike):
  `verdicts: {'described:…': 'first'} | phase: ['change'] | changes_noticed: 1`.
  `_render_view_english`'s own docstring states the rule this breaks: "`force`
  is an objective judgement … and it was deciding a per-observer question";
  and perception's comment at 6405-6418 explains why a transition must not
  ride for an observer who did not hold the body ("TRANSITION PHRASING
  DISCLOSES THE PAST STATE").
- **Fix:** derive `phase` from the observer's own ledger — the `beat` mark
  `as_beat` stamps, or an appearance `delta` (which is already gated on
  `saw_before`) — never from `force`. **Test:** a first-sight appearance
  percept with `force=True` and a non-empty, non-matching `prev_standing`
  projects `phase == "state"` on both tiers.

### F3 — `ambient_percepts` admits every room-scoped sensory event to an observer that has no room

- **Severity:** LEAK · **Confidence:** CONFIRMED for the composer; reachability PLAUSIBLE
- **Where:** `agents/composer.py:3166`

```python
if room and observer_room and room != str(observer_room):
    continue
```

- **Scenario.** A cast member who is attached but not placed (`character_room`
  returns None — `perception.py:3488-3492` still builds a perceiver with
  `"room": None`) reaches `_gated_ambient_percepts(gate, sensory_events,
  p.get("room"), …)` (`perception.py:6883`, and six more sites) with no room
  guard. Every event scoped to ANY room is admitted:
  `ambient_percepts([{'room': 'vault', 'detail': 'a slow hiss behind the vault door'}], None)`
  → delivered, while `environment_percept(None, …)` returns None ("A mind in
  unloaded space perceives NOTHING"). The guard fails open on the one input it
  cannot judge.
- **Fix:** fail closed — `if room and room != str(observer_room or ""): continue`.
  **Test:** `ambient_percepts([{"room": "vault", "detail": "x"}], None) == []`,
  roomless events still admitted (`tests/test_ambient_channel_scope.py` has no
  roomless case).

### F4 — The Japanese view renders a movement HEARD behind the observer as a subject-less sight sentence

- **Severity:** WRONG-SCENE · **Confidence:** CONFIRMED (snippet)
- **Where:** `language_adapters/japanese.py:561-569` (renders the composer's IR;
  the percept is minted at `agents/composer.py:5476-5487`).
- **Scenario.** `act_percept`'s rear-arc branch mints
  `Percept(kind="act", channel="hearing", source_label="", fidelity="shapes",
  data={"motion": True, "unseen": True, "bearing": …})`. English renders
  `Something moves behind you.` (`_render_event` checks `unseen` first). The
  Japanese adapter has no `unseen` branch; it takes the `shapes` branch with an
  empty label: **`が動いているが、それ以上は見て取れない。`** — no subject, and a
  claim of SIGHT ("cannot make it out") for a sound behind the reader. The
  pack's `act_heard`/`act_heard_placed` (ja compositor lines 193-194) are
  written and never used. Every rear-arc movement in a Japanese story reads so.
- **Fix:** the `unseen` branch before `shapes`, as `_render_event` has it.
  **Test:** add an unseen act to `tests/test_japanese_renderer_parity.py`'s
  KINDS and assert the ja text is `act_heard[_placed]`'s.

### F5 — The English episode files that same heard movement as a subject-less sight sentence

- **Severity:** WRONG-SCENE (memory) · **Confidence:** CONFIRMED (snippet)
- **Where:** `agents/composer.py:7195-7202` (`_episode_sentence` has no `unseen` check)

```python
if p.kind == "act":
    if p.fidelity == "shapes":
        ...
        return _en("episode_act_shapes", label=_cap(p.source_label))
```

- **Scenario.** View: `Something moves behind you.` Episode filed:
  `(' moved, too little of it to make out.', ' moved, too little of it to make out.', [])`
  — no subject, the bearing gone, and "make out" makes a heard event a seen one.
  `episode_signature` of every such percept is the same string, so at the
  outcome stage a second body's movement is dropped as a "repeat" of the
  first's (`perception.py:9026-9033` counts signatures).
- **Fix:** an `unseen` branch filing the movement heard, with its bearing (a
  pack template; the residue's `pain_episode` is the precedent for an
  episode-wording key). **Test:** `render_episode([unseen_act])` names the
  bearing and contains no sight wording; two bodies' unseen acts have different
  signatures.

### F6 — A reported act of speech never reaches English memory

- **Severity:** WRONG-SCENE (memory) · **Confidence:** CONFIRMED (snippet)
- **Where:** `agents/composer.py:7171-7274` — `_episode_sentence` has branches
  for speech, act, cue, crossing, substance, environment, pose, sensation,
  appearance, scent, residue and ambient; `communication` (an EVENT kind, minted
  by `communication_percept` at 5316) falls to `return ""`.
- **Scenario.** "Rhona warns Pell the tide is turning" (no quoted line).
  View: `Rhona warns the tide is turning.` English episode: `('', '', [])` — no
  memory row when it is the beat's only event. The Japanese episode files it
  (`Rhonaがwarns the tide is turningのを見た。` — the English verb is the
  registered `communication_surface` issue). The two renderers disagree about
  whether a delivered event is remembered.
- **Fix:** a `communication` branch mirroring the act branch
  (`_observable_predicate(label, surface)`, with `via`). **Test:** the English
  episode of a full communication percept is non-empty and carries its surface.

### F7 — Learning a name re-declares every pose arranged against that body as CHANGED

- **Severity:** WRONG-SCENE (false obligation) · **Confidence:** CONFIRMED (snippet)
- **Where:** `agents/composer.py:2857-2861` (key over rendered fields), fed by
  `2840/2844` (`relative_to` = the observer's DISPLAY LABEL for the referent)

```python
dedupe_key=standing_key(
    "pose", (body_key(name),),
    tuple(str(data.get(f) or "")
          for f in (_OWN_POSE_KEY_FIELDS if is_self else _POSE_RENDER_FIELDS))),
```

- **Scenario.** Xan leans against a stranger the observer calls "the woman in
  grey". The observer learns her name (Yul). Nothing moved, but the pose key's
  content now hashes "Yul": `verdict: changed, leads: True`, and the player view
  renders `The tall man is leaning against Yul.` as a beat-marked span — a
  numbered `current_events` obligation. This is the 1.70 class's second half
  exactly: `scent_percepts` was fixed to stop hashing "a fact about this
  observer's recognition of the source" (3329-3341); the pose key still does,
  through every referent label (`support`, `relative_to`), and the referents of
  the observer's OWN pose too.
- **Fix:** key the referents by what they ARE (a body's `body_key`, an
  entity's id, the authored text otherwise), not by the label rendered for this
  observer; bump the tag so old ledgers read as first sight. **Test:** one pose,
  two display maps differing only in the referent's label →
  `standing_verdicts` says `unchanged`.
- Related, registered: `UNBUILT_PERCEPTION §1.80` (a re-WORDING reads as a
  change). This trigger is recognition, not wording.

### F8 — A beat asleep forgets every voice the mind knew (English renderer only)

- **Severity:** WRONG-SCENE · **Confidence:** CONFIRMED (snippet)
- **Where:** `agents/composer.py:6803-6805`

```python
return RenderedView(text=text, spans=[(p, text)],
                    standing_keys={p.dedupe_key},
                    described=set(prev_described))
```

- **Scenario.** The ledger (`perception.py:6685`, `"standing":
  sorted(rendered.standing_keys)`) is replaced each beat. On a non-awake beat
  the English renderer files the residue key alone, so the `voice:` keys
  `carried_voices` exists to carry are gone; the next line from every known
  speaker is a first hearing and re-declares their register ("in a low
  contralto voice") — against the code's own rule ("A VOICE ONCE KNOWN STAYS
  KNOWN … Carried forward unconditionally", 6817-6822). `described` IS carried
  on the same path. The Japanese adapter carries the voices
  (`japanese.py:671`); measured: EN asleep keeps the voice `False`, EN woken
  `True`, JA asleep `True`.
- **Fix:** `standing_keys=carried_voices(prev_standing) | {p.dedupe_key}`.
  **Test:** both renderers, an asleep view with a voice key in `prev_standing`
  keeps it.

### F9 — Layer A writes English and ASCII into percept text the Japanese view prints verbatim

- **Severity:** WRONG-SCENE (language pack) · **Confidence:** CONFIRMED (snippet) for (a),(b); by reading for (c),(d)
- **How the Japanese pack gets its words:** for `sensation`, `substance` and
  `ambient`, `JapaneseRenderer._sentence` prints `data["clause"|"text"|"desc"]`
  verbatim (`japanese.py:622-624`). So whatever Layer A writes there is the ja
  page. Templates read through `_t`/`compositor_text` are per-pack; `_en(...)`
  and literals are English always.
  - (a) `agents/composer.py:3198` — `desc.rstrip(".") + _en("sound_echo")`:
    `鐘の音が鳴り響く。, and the place gives it back` (run). The next line
    (3200-3202, `after`) already uses `compositor_text`.
  - (b) `4443-4444` (`room_content_percepts`) and `4532-4533`
    (`chatter_percepts`): `if desc[-1:] not in ".!?": desc += "."` →
    `群衆がざわめいている。.` (run). `_strip_sentence_ends` (205-216) and
    `_end_sentence` (6448) already read the pack's stops.
  - (c) `"someone"` reaches ja views: `_pose_referent` 1948 (the observer's own
    pose against a body it was not shown — the "pinned beneath someone" case),
    `pose_percepts` 2766, `body_part_percepts` 1589, `body_region_percepts`
    3084. The ja adapter translates only `SELF_SOURCE_LABEL = "you"`
    (`japanese.py:28`, 405-409).
  - (d) `thing_reading_text` 4338: booleans read `yes`/`no` in every pack.
- **Fix (the class):** no English literal and no ASCII-only stop test in
  Layer A text; route through `_t`/`compositor_text`/`_ling("_SENTENCE_ENDS")`.
  **Test:** in a `language_scope("ja")`, these builders' text fields contain no
  ASCII letters beyond what their inputs held.
- Not repeated here (registered): `weather_percepts`' `_en` sentences and
  `"speaks indistinctly"` — see § Already registered.

### F10 — An act's `directed_at_self` is an English regex; the structural answer is computed and thrown away

- **Severity:** SILENT-NOOP (language pack; under-grant) · **Confidence:** CONFIRMED (snippet)
- **Where:** `agents/composer.py:5545-5546`, with `targets_self` computed at 5522

```python
"directed_at_self": bool(
    re.search(r"\byou\b|\byour\b", surface, re.I))},
```

- **Scenario.** In Japanese, an act whose `targets` name the observer:
  `{'surface': '葵の肩に手を置く', 'directed_at_self': False}`; English, same
  event: `True`. The typed `targets_self` (5522-5526) answers the question
  structurally and is used only to choose a rewrite. Inert in code (the field
  has no code reader — `UNBUILT_WORLD §1.28`), live for the model reading the
  payload. (Also seen in passing: the ja surface kept the observer's own name in
  its own view — `common._self_second_person`'s, not this module's; for that
  file's auditor.)
- **Fix:** `directed_at_self = targets_self or <the existing test>`.
  **Test:** a ja act targeting the observer projects `directed_at_self: true`.

### F11 — Production-dead code that still describes itself as live

- **Severity:** DEAD · **Confidence:** CONFIRMED (repo-wide AST and token sweep over `.py/.js/.json/.html`)
- `micro_round_percept` / `micro_round_percepts` (`4557-4613`): no production
  caller; `tests/test_speaking_turns.py:193-205` pins that perception must NOT
  call `micro_round_percepts(` (the outcome stopped re-delivering the loop's
  drafts, 2026-09-23). The docstring still says "What matters is that it goes
  in the SAME list as everything else" and names a residual in
  `design_notes/13`. Only tests keep it alive.
- `_YOU_TO_ME` (`7092-7095`): no reader anywhere ("English compatibility
  view" — nothing reads it).
- `DIM_FIGURES` (`1284`): no reader anywhere (the comment says "The English
  compat exports stay for tests and audits"; `DIM_FIGURE` is read by 3 test
  files, `DIM_FIGURES` by none).
- **Fix:** delete in their own commit after the split (or register). No test.

### F12 — Docstrings and comments describing code that is not there

- **Severity:** STALE-DOC · **Confidence:** CONFIRMED (grep)
- `agents/composer.py:47-50` "Module discipline: imports `agents/common.py`,
  `spatial.py`, `scene.py` only" — also `core.pipeline_context`,
  `language_runtime`, `story.provenance_text`, and deferred
  `world.charter_surface`, `world.landscape`, `world.weather`,
  `story.character_schema`, `llm.schemas`. (The half that matters, "never
  another role module", holds — § Docs checked.)
- `:6` "percept builders (`build_*_percepts`)" — no function has that name.
- `:228` `fidelity: str = "full"  # full|degraded|fragment|trace` — builders
  also mint `voice`, `silence` and `shapes` (`_FIDELITY_AMBIGUITY` knows two of
  them). Unlike `kind` and `channel`, `fidelity` is not validated.
- `:7000` names `perception._composer_render_observer`'s floor — no such
  function exists; the floor is in `perception._composer_outcome_views`
  (`perception.py:8995`, `composer.near_text`).
- `world/spatial_light_field.py:1362` names `composer._light_shape` — it is
  `JapaneseRenderer._light_shape`.
- `agents/README.md:12-14` "`observations_from_render`, which is where the
  structured observations are re-derived from the final scrubbed view" — it
  projects from `rendered`, BEFORE the tripwires; `perception._repaired_observations`
  (6576-6633) reconciles afterwards and says so.
- **Fix:** correct each in a docs commit.

## Efficiency

1. **Stranger label ladders are recomputed per observer, though they depend only
   on the stranger.** `observer_display_map` → `assign_stranger_labels`
   (`composer.py:475-538`) calls `common.stranger_label_ladder` for every
   stranger, for every observer, at every call site:
   `perception.py:2985` (company), `6849` (establish), `7149` (act), `8312`
   (outcome) and `loops.py:404` (per micro-round, per observer). Measured:
   `stranger_label_ladder` 3.0 ms per body; `assign_stranger_labels` over six
   mutual strangers 13.6–18.4 ms. A room of six strangers costs ~6 × 4 × 15 ms
   ≈ 0.35 s per beat (plus `_joint_stranger_labels`, `perception.py:4996`, over
   everyone). Typical stories are cheaper — the module's own comment measures an
   unrecognised body on 6.2% of beats, ≤2 at once — but a story's opening (nobody
   knows anybody) is the expensive case. **Gain:** N-fold on that cost with a
   per-read-pass memo keyed on `(name, appearance, aliases, role, surface, noun)`,
   the shape `world/scene_memo.py` already gives `visual_level_between`. Cheap.
2. **`_episode_sentence` runs ~3× per act per observer per beat**:
   `episode_signature` for the act stage's `said` list (`perception.py:7496`),
   again for the outcome's dedupe (`9030`), and again inside `render_episode`.
   Each act runs `_verbs_in_base` (0.33 ms; `episode_signature` 0.45 ms).
   ~10 acts × 6 observers × 3 ≈ 80 ms on a busy beat. A per-stage memo by
   percept identity removes two thirds. Low–moderate.
3. **Pack tables rebuilt per call.** `_pack_words` (5.5 µs) builds a frozenset
   per call, `_label_core` (24 µs) builds two, `_active_ordinal_words` a dict,
   `_t` re-reads the card; `_noun_phrase` (7–23 µs) calls `_pack_words` up to
   three times and runs once per authored description (features, openings,
   every landscape item). A few ms per view at most. Low gain; an
   `lru_cache` on `(language id, name)` like `_linguistic_cached`.

Checked and NOT an issue: `visual_level_between` is asked ~3× per pair
(display map, presence, pose) but is memoised inside a `scene_read_pass`
(`world/spatial_senses.py:1035-1039`).

## Already registered

- `weather_percepts` mints its sight/touch sentences through `_en`, so a
  Japanese view carries them in English (run: `Heavy 雪 out of the 鉛色の空 sky.`,
  `The 北風 pulls at you.`) — `UNBUILT_PERCEPTION §2.36` (round-2 lane C
  residuals: "pre-existing, found on the way, not touched").
- `communication_percept`'s literal `"speaks indistinctly"`
  (`composer.py:5341`; run: `番人はspeaks indistinctly。`) and
  `common.communication_surface`'s English verb table — `UNBUILT_IDENTITY §1.48`.
- The micro-round labels one actor at a time, so two strangers of one
  description collapse to one label there while the composed view widens them
  (run: joint `{'Ann': 'the tall woman in a grey coat with a scar on her jaw',
  'Bea': '…with red hair'}`, alone `{'Ann': 'the tall woman'}`) —
  `UNBUILT_PERCEPTION §3.8`.
- `_addresses` matches `intended_target` against the canonical name only;
  `line_hear_level` (817-818) uses it for the addressed rescue while the ear
  rung and the din use the caller's `addressed` (alias-aware, `targets`
  included) — the two answers can disagree inside one call —
  `UNBUILT_IDENTITY §1.38` (the deliberate "do not loosen on a string match").
- A standing content hash is lexical, so a re-worded pose/contact reads as
  `changed`; the episode keeps its own changed-list logic —
  `UNBUILT_PERCEPTION §1.80`.
- Observation metadata (`intensity`, `suddenness`, `ambiguity`,
  `directed_at_self`) has no reader in code — `UNBUILT_WORLD §1.28` (but see F1
  and F10: the model reading the payload is a reader).
- The change-key repetition class itself — `UNBUILT_PIPELINE §1.70`
  (room contents keyed on state, scent label unhashed: both hold in the code).
- Rear-arc act residuals (no habituation for a routine act behind a listener) —
  `UNBUILT_PERCEPTION §2.36`.

## Structure notes

- **Seams for the split:** twelve siblings, written up in
  `plans/SPLIT_COMPOSER.md` (common · person · figures · bodies · speech ·
  acts · fields · landscape · things · standing · render · episode). The file's
  banners are 6 seams and 4 lies; the worst is "Layer A -- standing-state
  percepts", which heads 3,738 lines including the phrase splicers and the
  whole grammatical-person subsystem.
- **Monoliths in miniature:** `_render_view_english` 290 lines,
  `speech_percept` 289, `compose_landscape_line` 229 (eight nested closures
  sharing a mutable `said_kinds`), `presence_percepts` 181, `pose_percepts`
  178, `_verbs_in_base` 166, `act_percept` 166, `_render_episode_english` 139,
  `line_hear_level` 130, `_episode_sentence` 125, `_pose_referent` 119.
- **`compose_landscape_line` (3705-3933), "no intra-module refs":** it
  references no module-level name because every pack-specific thing is
  injected (`text`, `thing`, `compass_words`), which is why it is an island in
  the anatomy graph. It is CALLED by `render_landscape_line` (3936-3941, English
  with `_en`/`_noun_phrase`), `_far_line_text` (3497-3505, a non-English far
  look, with `compositor_text`) and `JapaneseRenderer._landscape_line`
  (`japanese.py:265-272`). It is the shared realiser of `landscape_lines`'
  layout — the one place both packs' far lines are worded from.
- **Module-level mutable state:** 12 dicts (`_ORDINAL_WORDS`,
  `_PRESENCE_DEPTH_TIERS`, `_COUNT_NAMES`, `_ENGINE_CHANNEL_PERCEPT`,
  `_SCENT_FIDELITY`, `_FELT_SALIENCE`, `_STANDING_ORDER`, `_TIER_PHRASES`,
  `_SIZE_PHRASES`, `_COUNT_WORDS`, `_FIDELITY_AMBIGUITY`,
  `OBSERVATION_DEFAULTS`). **No writer anywhere** in the repository, no
  `global` statement, no ContextVar. Cross-module readers through the facade:
  `agents/loops.py:597` (`_FIDELITY_AMBIGUITY["shapes"]`),
  `agents/narration.py:1891,1893` (`OBSERVATION_DEFAULTS`). The pack cards
  (`_ENGLISH_COMPOSITOR`, `_EN_TEMPLATES`) are `mappingproxy` (checked).
- **Dead percept kinds:** none. All 18 `PERCEPT_KINDS` have a builder here and
  a production caller (verified per builder), and the English view renders all
  of them. The gaps are per-renderer: the English EPISODE cannot render
  `communication` (F6) or an `unseen` act (F5); the Japanese VIEW cannot render
  an `unseen` act (F4). The `micro_round_percept` path (the only producer of a
  `mixed`-channel ambient besides `_ambient_channel`'s fallback) is dead (F11).
- **Two copies of one rule, free to drift:**
  - `world.spatial_senses.sighted_level` calls itself "ONE RULE FOR EVERY
    READER THAT ASKS WHETHER A MIND SAW A BODY" (visual level + senses + rear
    arc); `presence_percepts` (1409-1438) and `pose_percepts` (2759-2765)
    restate it inline, and `observer_display_map` (624-626) grades sight
    without the rear arc.
  - `concealed_from_observer` (664-685, canonical name / id /
    `character:<id>` / `*`) vs `common._conceal_from_targets_observer` (every
    handle, fails closed). The composer's narrower reader is safe only because
    `director_floors.resolve_concealment_refs` canonicalises the list first —
    for the player at the interpret floor and for character declarations
    (`director.py:5454-5472`). An entry naming nobody stays as written and
    "excludes nobody" (warned, documented at `director_floors.py:2302-2311`).
  - `render_view` validates the adapter's return type (7066-7075);
    `render_episode` (7483-7497) does not — an adapter returning a bare string
    would be unpacked as three characters.
- **Latent 1.70 instances (no live failure measured):** `weather_percepts`'
  touch keys hash the composed CLAUSE (template text) and share one subject
  (`("sky",)`) across three clauses (4035); `ambient_percepts`' key hashes
  `desc` after the echo/after-sight suffix is appended (3198-3207). A template
  edit re-keys every live chat's weather touch and echoing sound once.
- **`own_name_forms` (5201)** strips English articles from a literal
  `("the ", "a ", "an ")` rather than the pack's `articles` — harmless for the
  two shipped packs (ja names take none), a hazard for a third.
- **`scent_percepts` (3315)** cuts the authored scent at 160 characters
  mid-word with no marker; the cap is the owner's (not proposing a number).

## Docs checked

| claim | where | verdict |
| --- | --- | --- |
| `composer` is a LEAF the roles share: "calls none of them back" | `agents/README.md:61-63`, `CLAUDE.md` | **HELD.** Eager imports: `.common`, `core.pipeline_context`, `language_runtime`, `story.scene`, `story.provenance_text`, `world.spatial`. Deferred: `.common`, `world.{charter_surface,landscape,weather,spatial}`, `story.character_schema`, `llm.schemas`, `language_runtime`. `agents/common.py` imports no role module and not composer. The only lazy role imports reachable through `world` (`world/spatial_frames.py:441` → `agents.background`, `:2699` → `agents.offscreen_beat`) are in `_room_presences_named` / `detect_and_reconcile`, chat-level functions no scene reader the composer imports reaches. |
| "imports `agents/common.py`, `spatial.py`, `scene.py` only" | composer docstring 47-50 | **STALE** (F12). |
| "the structured observations are re-derived from the rendered view … so the second representation cannot expand the information budget" | `CLAUDE.md` § Architecture | **FAILS** for `directed_at_self` (F1) and `phase` (F2); holds for `observed.text`, `actor` (both callers map an unseen stranger to "a voice": `perception._attributed_label` 4952-4983, `background.py:241-243`) and `channel`. |
| "A rendering path structurally cannot ADD information" | `AGENTS.md:661-666` | **HELD** for the rendered text (signatures take percepts and mode only); the observation projection is the exception (F1, F2). |
| "observations_from_render preserves one admitted span per observation; never merge" | `AGENTS.md:884-886` | **HELD** (no cap; one row per span). |
| "re-derived from the final scrubbed view" | `agents/README.md:12-14` | **STALE** (F12). |
| Scent is attribution-blind; its label is the display map's | `AGENTS.md:660` | **HELD** (`scent_percepts` 3311-3322: label only when `attributed` and `level == "full"`). |
| "What changed is computed per observer, never from the scene" | `AGENTS.md:671-680` | **HELD** for `standing_verdicts` (its operands are percepts and the observer's ledger); the observation `phase` reads `force`, a world fact (F2). |
| A pack asks `standing_verdicts`, `leads_the_beat`/`as_beat`/`ACTIVE_STANDING_KINDS`, `player_view_order` | `AGENTS.md:672-680` | **HELD** (ja adapter imports them through the facade). |
| "A memory speaks in its own first person" (Built) | `Design.md:302` | **HELD** except an unseen act (F5) and a communication (F6). |
| "A body the view showed is named as the view named it, in every delivery" (Built) | `Design.md:330` | **PARTIAL**: disguise and sight hold; joint stranger widening does not in the micro-round (registered `UNBUILT_PERCEPTION §3.8`, which the Design row does not mention). |
| "`composer._MAX_OBSERVATION_ATOMS` is 8 and is untouched" | `UNBUILT_PIPELINE §1.70` (line 582) | **STALE** (register): no such name exists anywhere; `observations_from_render` says "There is no row-count cap here". |
| `_SELF_DIRECTED`, `_observation_spans`, `_MAX_OBSERVATION_ATOMS = 8` | `UNBUILT_WORLD §1.28` (431-452) | **STALE** (register): that prose derivation was deleted; the fields are now copied from percept data, which is how F1 arises. |
| "a false 'changed' verdict buys a re-description the observer was already entitled to, never a fact" | `UNBUILT_PERCEPTION §1.80` | **HELD** for its lexical case and for F7. |
