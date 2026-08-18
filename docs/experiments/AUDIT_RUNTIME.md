# Audit: the runtime slice — `runtime.py`, `narration.py`, `mapping.py`, `storage.py`, `agents/__init__.py`, `core/pipeline_context.py`

Read whole, line by line, 2026-08-18. Same discipline and register as
[`AUDIT_DIRECTOR.md`](AUDIT_DIRECTOR.md): **every finding below is FLAGGED, NOT
FIXED.** Not one line of source was edited by this task, and `docs/UNBUILT.md`
was deliberately left alone (other agents are in flight).

**Baseline revision:** `d43b4ed`. Every `file:line` is as of that revision.
The working tree at audit time had unrelated modifications in
`agents/director.py`, `world/spatial_*.py`, `tests/test_scale.py` and
`docs/CODE_MAP.md`; none of the audited files were dirty.

| file | lines |
| --- | --- |
| `agents/runtime.py` | 1,116 |
| `agents/narration.py` | 1,210 |
| `agents/mapping.py` | 297 |
| `agents/storage.py` | 123 |
| `agents/__init__.py` | 89 |
| `core/pipeline_context.py` | 312 |

Measurements marked *(live)* come from the owner's `engine.db`, opened
read-only (`sqlite3.connect("file:engine.db?mode=ro", uri=True)`). Nothing was
written to it, and no test suite was run.

---

## Part 1 — findings. FLAGGED, NOT FIXED.

### The three lists are four, and one of them disagrees

The brief names three registries that must be kept in step by hand:
`runtime.STEP_HANDLERS`, `schemas.SCHEMA_MAP`, and the fields of
`core/pipeline_context.PipelineContext`. There is a fourth,
`FRIENDLY_STEP_LABELS` in `static/js/chat.js`, and both it and
`PipelineContext` are out of step. Full cross-check:

| step key | `STEP_HANDLERS`<br>(`runtime.py:182-197`) | `SCHEMA_MAP`<br>(`schemas.py:3289-3311`) | `PipelineContext` field<br>(`pipeline_context.py:146-166`) | `FRIENDLY_STEP_LABELS`<br>(`chat.js:703-719`) |
| --- | :-: | :-: | :-: | :-: |
| `director_establish` | ✔ | ✔ | ✔ | ✔ |
| `director_interpret` | ✔ | ✔ | ✔ | ✔ |
| `mapping_stage` | ✔ | ✔ | ✔ | ✔ |
| `mapping_quick` | ✔ | — (see below) | ✔ | ✔ |
| `perception_establish` | ✔ | — (deliberate) | ✔ | ✔ |
| `perception_act` | ✔ | — (deliberate) | ✔ | ✔ |
| `reaction_loop` | ✔ | — | ✔ | ✔ |
| `interaction_loop` | ✔ | — | ✔ | ✔ |
| `director_resolve` | ✔ | ✔ | ✔ | ✔ |
| **`background_react`** | ✔ | ✔ | **✘** | ✔ |
| `perception_outcome` | ✔ | — (deliberate) | ✔ | ✔ |
| `narrator` | ✔ | ✔ | ✔ | ✔ |
| **`narrator_extra`** | ✔ | — (borrows `narrator`) | ✔ | **✘** |
| **`commit`** | ✔ | — (no model output) | **✘** | ✔ |

The three "deliberate" absences from `SCHEMA_MAP` are documented in place
(`schemas.py:3230-3237`: perception makes no model call, so there is nothing to
validate). `mapping_quick` is undocumented but harmless — it either returns a
deterministic dict or delegates to `mapping_stage`, whose own call validates
under the `mapping_stage` key (`mapping.py:116-122`). The two real divergences
are findings 1 and 2.

### 1. `background_react` is a step everywhere except the context that carries it

`STEP_HANDLERS` registers it (`runtime.py:192`), `SCHEMA_MAP` validates it
(`schemas.py:3307`), `build_plan` plans it unconditionally
(`runtime.py:613`) — and `PipelineContext` has no field for it
(`pipeline_context.py:146-166`). Its output therefore lands in the untyped
`_extra` dict via `__setitem__`'s fall-through (`pipeline_context.py:236-237`).

`agents/README.md` step 5 is explicit: *"Give it a field on `PipelineContext`
if later stages read its output."* Five modules read it:

- `agents/narration.py:524` (`_ordered_beat_events`)
- `agents/perception.py:2972`
- `persist/commit_memory.py:236`
- `persist/commit_background.py:524, 763, 828, 830, 1446`

`commit` is in the same position, though nothing downstream reads it.

This is not cosmetic, because the two storage classes have **different
emptiness semantics**. `__contains__` (`pipeline_context.py:256-265`) answers
`getattr(self, key) is not None` for a declared field but `key in self._extra`
for everything else — so a declared field set to `None` reads as ABSENT while
an `_extra` key set to `None` reads as PRESENT. `_assert_plan_materialized`
(`agents/common.py:242-246`) is built on exactly that predicate. Every
declared-field step gets a real materialization check; `background_react`,
`commit` and every `ext:<id>:<key>` step get a weaker one that a `None` result
passes.

Corroborating evidence that the missing field is felt:
`tests/test_narrator_world_fidelity.py:667` reaches into the private dict —
`ctx._extra["background_react"] = {...}` — where every other stage in the same
file is set through `ctx[...]`.

### 2. `narrator_extra` is missing from the frontend's step-label list, which is the exact defect that list's own comment records fixing

`static/js/chat.js:703-719` maps 13 step keys to human phase names.
`narrator_extra` is not among them, so `friendlyPhase` (`chat.js:737`) falls
through to `return label || "Working…"` and the turn-status bar shows the raw
technical label *"Narrator · render (other players)"*.

The dictionary carries this comment, three lines above the gap
(`chat.js:716-718`):

> `// background_react was missing entirely, so it fell through to the raw`
> `// technical label. It covers two very different paths, named at plan time.`

Same class, one key over, in the same object literal. *(live)* 135
`narrator_extra` steps exist in the corpus, so this is a path real play takes.

### 3. `PipelineContext._extra` carries four cross-stage side-channels, and no resume path rebuilds any of them

`_rehydrate_loop_results` (`runtime.py:707-747`) exists precisely because
`ctx[key] = content` does not reconstruct everything a stage populated in an
uninterrupted run — its docstring cites "audit #11". It rebuilds
`character_results` and `reaction_results`, and stops there. Three more
cross-stage values live in `_extra` and are written by direct assignment, so no
step content carries them and nothing restores them:

| key | written | read | lost on resume |
| --- | --- | --- | --- |
| `outcome_scene` | `perception.py:2939` | `narration.py:616, 873, 1136` | this beat's post-move, orientation-refreshed scene |
| `interaction_views` | `loops.py:713, 944` | `character.py:2478, 2480` | a mind's own micro-view of the round |
| `reaction_views` | `loops.py:1029` | `character.py:2479, 2480` | a mind's own reaction-phase view |

**The `outcome_scene` case is the serious one.** `narrator` reads it at
`narration.py:873` with `or get_scene(chat["id"], chat)` as the fallback, under
a comment (`narration.py:980-984`) that names the exact harm:

> `# Using the committed scene here would describe the space with LAST beat's`
> `# facing on movement beats (commit runs after this stage).`

On a single-step reroll of the narrator — `POST /api/steps/{sid}/reroll`,
`web/app.py:5322`, which passes `only_key=step["key"]` — `_run_pipeline`
restores the **pre-turn** checkpoint first (`runtime.py:840`,
`_restore_and_refresh`) and then recomputes the narrator with `outcome_scene`
absent. Everything keyed on it silently changes answer: `spatial_digest`, the
whole `_position_delta_payload` (`narration.py:616` — `prev_sc` and `sc` become
the same scene, so `moved` is False for everyone and the payload usually
empties), `_visible_portal_states`, `_sensory_channels_manifest`, and
`_player_perceives` inside `_ordered_beat_events`.

*(live)* 451 of 2,349 `narrator` steps carry more than one variant, and **450 of
those 451 sit on turns that also have a `commit` step** — i.e. every one of
them was re-rendered against a restored pre-turn world unless it happened to
come through a `from_key` rerun that re-ran `perception_outcome`.

The `reaction_views` case has the same shape one layer down: on a contested
beat at `autonomy > 0`, `reaction_loop` writes the views and the character
steps *inside* `interaction_loop` read them. Resume from `interaction_loop` and
`character.py:2481-2482` falls back to `perception_act`'s base onset view. That
fallback SUBTRACTS (the safe direction, no leak), but it means a resumed turn
produces a materially different decision from the uninterrupted one — which is
the property `active_content`'s own comment (`storage.py:65-71`) calls "the
worst kind of difference between a fresh run and a resumed one".

### 4. Additional human players get no opening-turn narration, and two dead code paths pretend otherwise

`establishment_plan()` (`runtime.py:698-705`) is a fixed five-element list.
`build_plan`'s extra-player branch (`runtime.py:621-628`) has no counterpart
there, so `narrator_extra` cannot be planned on `turn.idx == 0`.

Two pieces of code are written as though it could be:

- `narrator_extra`'s establishment branch, `narration.py:1093-1095`:
  `view = (establish_views.get(f"extra:{pid_key}") if est else ...)`. Doubly
  dead — the stage never runs on turn 0, *and* `perception_establish`
  (`perception.py:2343-2450`) builds no `extra:<pid>` perceiver at all. Only
  `perception_act`/`perception_outcome` do (`perception.py:3121`).
- `narrator_extra`'s `est = ctx.get("director_establish") or {}`
  (`narration.py:1073`) is therefore always `{}`, making `scene_opening`
  (`narration.py:1130`) a constant `False` on that path.

Effect: a second human player joining a story sees the opening beat rendered
for nobody. `_load_extra_players`' own docstring (`runtime.py:61-68`) states the
principle this violates — *"Silently dropping idle players would mean anyone not
acting every single beat gets no rendered update at all"* — and turn 0 is the
one beat where nobody has acted.

*(live)* 69 opening turns exist, carrying exactly five step keys between them
(`director_establish`, `mapping_stage`, `narrator`, `perception_establish`,
`commit`); zero `narrator_extra`. 3 `chat_personas` rows across 2 chats.

Not in `docs/UNBUILT.md`. §3.4's S3-A6 covers a *different* narrator_extra gap
(the consciousness gate and fidelity facts), which is correctly recorded and is
not re-reported here.

### 5. The opening turn bypasses the extension plan-splice seam entirely

`build_plan` ends with `return _extension_splices(plan, chat_id)`
(`runtime.py:634`), under a comment explaining that it must be last.
`establishment_plan()` (`runtime.py:698-705`) returns a bare list. So an
extension anchored `after:mapping_stage`, `before:narrator` or `after:commit`
— all valid core anchors, all steps that DO run on turn 0 — is silently not
planned on the opening turn.

`docs/guides/EXTENSIONS.md:320-323` states the contract this breaks:

> An anchor naming a step **this particular turn does not run** means your stage
> is simply not planned that turn. Not an error, and — importantly — not bolted
> onto a different position…

Here the step runs and the splice still does not happen. The documented rule
predicts the opposite of the behaviour, and the failure is silent by design
(`apply_plan_splices` is total and returns the plan unchanged on any problem —
`extension_runtime/__init__.py:734-736`). A campaign extension that wants to
seed the first beat is the obvious victim; `api.provision_story` exists to make
turn zero arrive whole (`Design.md:258`), and the plan half of that is missing.

*(live)* One `ext:cohesion-demo:pulse` step exists, so the seam is exercised.

### 6. `mapping_stage` writes the entire lore-candidate list into every stored step, and nothing reads it — 66% of that step's stored bytes

`mapping.py:139`: `out["candidates"] = hits`, appended after `_agent_json`
returns (so it survives `MappingStageOutput`'s `extra="ignore"`, which has no
`candidates` field — `schemas.py:3239-3245`).

Verified no reader: grepped `-w candidates` over every `*.py` in the repo, plus
`static/js/`, `tools/` and `docs/`. Every hit is an unrelated local variable.
The only consumer of a stored mapping step is `common.lore_for`
(`agents/common.py:1555-1560`), which reads `relevant_lore` and nothing else.
The candidates the model actually cited are already merged into
`relevant_lore` by `_join_relevant_lore` (`mapping.py:124-125`) from the
in-memory `hits`, not from this field.

*(live)* 462 of 463 active `mapping_stage` variants carry it: **4,961,385 bytes
of 7,510,198 total — 66.1%.** That rides every checkpoint, branch, archive and
pipeline trace as opaque content, and is re-read on every rerun's hydration.

### 7. The reasoning-trace fix landed in one of the two thread-spawning helpers

`_stream_one` (`runtime.py:350-370`) carries a 14-line comment explaining why
`providers.last_reasoning` must be lifted out of the worker BY HAND, ending:

> `// so every stored trace was empty: 0 of 27,020 variants in a live install,`
> `// since the column existed.`

`_stream_parallel`'s `work()` (`runtime.py:396-424`) has no such capture. Its
`finally` block posts `__done__` and nothing else. `_run_parallel_group`
consequently calls `save_step(..., reasoning=h.get("reasoning"))`
(`runtime.py:474-475`) with `h` never holding that key, so `save_step` falls
through to its ContextVar fallback (`storage.py:46-51`) — read on the generator
thread, where the worker's write was never visible. That is the identical
failure, in the identical shape, in the copy the fix did not touch.

It affects all three parallel pairings: `character:<id>` siblings, `mapping_stage`
beside `perception_act`, and `narrator` beside `narrator_extra`.

*(live)* Not measurable from the corpus yet — no parallel group has run since
the fix landed (`f385bef`, 2026-08-17 22:09), and only the character-role model
emits reasoning at all (11 of 12 `interaction_loop` variants since that commit;
0 for every other key). The defect is structural and verified by reading, not
by measurement.

### 8. `SPATIAL_SCAFFOLD` is set nowhere in the tree, and the narrator prompt pays for it on every call

`narration.py:49-60`:

```python
def _spatial_facts_field(scene, observer):
    """Env-gated (SPATIAL_SCAFFOLD=1) ... On -> {'spatial_facts': [...]} the
    narrator is told not to contradict."""
    if not os.environ.get("SPATIAL_SCAFFOLD"):
        return {}
```

Grepped the whole repository (every file type, not just `*.py`):
`SPATIAL_SCAFFOLD` appears in exactly four places — this function, its twin at
`perception.py:339-347`, and two design notes that describe it as
"env-gated OFF". Not in the `Makefile`, not in `.github/workflows/`, not in
`tests/`, not in any documentation as something to set. So
`payload["spatial_facts"]` structurally cannot reach the narrator.

The narrator system prompt nevertheless carries a live three-clause
**SPATIAL GROUND TRUTH** block about it
(`language_packs/en/cards/system_prompts.json`, `prompts.narrator`; three
occurrences of the token), including:

> "if `spatial_facts` is present, every line in it is OBJECTIVE FACT for this
> beat. Your prose MUST NOT contradict any of it… When they conflict with the
> raw `player_view`, `spatial_facts` win."

Two costs. The obvious one: those tokens are in the prefix of every narrator
call in every chat, forever, describing a field that never arrives. The
subtler one, and the reason it belongs in an audit rather than a cleanup list:
a reader of the prompt is told the narrator has a spatial ground truth that
outranks the view. It does not. `spatial_frame` (`narration.py:875`) is what
actually ships, and it is a different structure with a different contract —
`docs/UNBUILT.md` §3.3 F6/S3-A5 records that `spatial_digest` is still ungated
and renders room names the player has never visited.

### 9. The S3-A5 portal-state gate is optional, has no production caller that skips it, and a test pins the leaky answer

`_visible_portal_states(scene, room_id, visible_rooms=None)`
(`narration.py:665`) branches on `_filter_adjacent = visible_rooms is not None`
(`narration.py:686`) in four places (`711-714`, `729`, `754`). The comments call
the `None` arm "backwards-compatible callers".

There is exactly one production caller and it always passes the set
(`narration.py:935`). The `None` arm therefore cannot fire outside tests — a
guard whose bypass condition can no longer be true, which is the shape
`AGENTS.md` § Information boundaries asks auditors to look for.

Worse, the bypass is *pinned*.
`tests/test_pipeline_audit_leak_gaps.py:642-660`
(`test_backwards_compatible_no_visible_rooms`) asserts that the two-argument
call still reports `door to Room 2` for a room the caller did not declare
visible — i.e. it asserts the pre-S3-A5 leak is preserved, for a caller class
that does not exist. And the module's primary F3 test,
`tests/test_narrator_world_fidelity.py:236-265`, exercises the whole feature
(link portals, transit hatches, adjacency barriers, the generic `doors` entry)
**only** through the unfiltered path — so the code shape production actually
runs is covered by the leak-gap suite alone.

### 10. The plan is not stable across the turn's own commit, and `resume_key_for_turn` recomputes it against post-commit state

`build_plan`'s consciousness gate (`runtime.py:574-579`) reads
`awareness_map(chat_id)` live. `director_resolve`'s `_awareness_exits`
(`agents/director_floors.py:417`, called at `agents/director.py:1351`) merges
condition ENDINGS into `state_diff.conditions`, and commit persists them. So
the reactor set `build_plan` computes depends on state THIS TURN writes.

Inside `_run_pipeline` this is safe by ordering: `_restore_and_refresh()` runs
at `runtime.py:876`, before `build_plan` at `runtime.py:973`. `resume_key_for_turn`
has no such protection — it is called from a web handler against the live,
un-restored world (`web/app.py:641`, `5183`, `5276`).

The reachable chain, reasoned from code (not reproduced — no suite runs
allowed):

1. An NPC is `asleep`; the player shakes them. The Director lists them in
   `flow.reactors` (they are being acted on), the gate drops them
   (`runtime.py:578-579`), `reactors` empties, so **no `interaction_loop` is
   planned** (`runtime.py:591-593`) even at the default `autonomy: 50`.
2. `director_resolve`'s rouse rule ends the condition; commit persists it.
3. The next new-turn attempt calls `_gate_new_turn` → `resume_key_for_turn`
   (`web/app.py:641-648`) → `build_plan` against the now-awake map → the plan
   contains `interaction_loop` → no such step row exists → a non-`None` resume
   key → **409, "The latest turn in this frame has an edited or incomplete
   step. Resume or reroll it before starting a new turn."**
4. The user resumes. `run_pipeline(from_key="interaction_loop")` →
   `_run_pipeline` restores the pre-turn checkpoint (asleep again) → rebuilds
   the plan without `interaction_loop` → `runtime.py:977-984` raises
   `RuntimeError: step 'interaction_loop' is not in this turn's plan` → 500.

The chat is then wedged: it can neither advance nor resume. Note the contrast
with the extension half of the same function, whose docstring
(`extension_runtime/__init__.py:693-695`) states the requirement explicitly —
*"Pure function of durable settings + manifests. `resume_key_for_turn` and every
`from_key` path rebuild this plan from stored step content, so a splice that
varied with anything else would break resume."* The engine's own gate varies
with something the turn itself writes.

### 11. The consciousness gate is chat-global while everything else in `build_plan` is frame-scoped

`build_plan` takes `frame_id` and uses it for the cast (`runtime.py:760`) and
for the extra-player check (`runtime.py:624`, `685-696`). The awareness gate
calls `awareness_map(chat_id)` (`runtime.py:575`), which reaches
`awareness_conditions` (`story/scene.py:959-976`) — a query over
`world_conditions WHERE chat_id=?` with **no frame column at all**
(`core/db.py:708-719`), keyed by casefolded subject NAME.

In a multi-frame chat where the same character exists in two eras, a sleep
condition established in one frame gates that character out of the reactor set
in the other. `narrator`'s own awareness read (`narration.py:871-872`) has the
same property.

### 12. Two representations of "must mapping run before perception", and they already differ

| | phrases matched against `flow.mapping_request` |
| --- | --- |
| `runtime._mapping_must_precede_perception` (`runtime.py:679-682`) | `"new room"`, `"generate room"`, `"scene graph"`, **`"new location"`** |
| `mapping.mapping_quick` (`mapping.py:213-215`) | `"new room"`, `"generate room"`, `"scene graph"` |

They answer adjacent questions — one decides serialization, one decides
escalation from cached recall to a full mapping call — but they are the same
hand-written phrase list, and they have drifted by one entry. A turn whose
`mapping_request` says `"new location"` with `needs_mapping` false takes
`mapping_quick`, which does not escalate, so the location is never staged. Both
lists are also naked `in` tests against model-authored free text, which is the
`literals-vs-rewriting` failure the user's own memory note records.

### 13. `_generate_narration`'s `text` fallback can no longer fire

`narration.py:799`:

```python
out.setdefault("prose", out.get("text", ""))
```

`NarratorOutput.prose` is declared `str = ""` (`schemas.py:2484`) and `_dump`
excludes only `None` (`schemas.py:189`), so the validated dict `_agent_json`
returns ALWAYS has a `prose` key and `setdefault` never assigns. Verified by
running the validator against a `text`-only payload (`ENGINE_DB` pointed at a
scratch file, engine.db untouched):

```
validate_llm_output_strict('narrator', {'text': 'hello world'})
  valid  False
  keys   ['new_specifics', 'paragraph_count', 'prose', 'text']
  prose  ''
```

Doubly dead: the strict path rejects the output before the fallback is reached,
and the fallback could not repair it if it were. The `text` field it reaches
for (`schemas.py:2486`) has no reader either.

### 14. An unreachable branch in `PipelineContext.get`

`pipeline_context.py:216-217`:

```python
if key.startswith("_") and key in self._extra:
    return self._extra[key]
```

`__setitem__` (`pipeline_context.py:227-237`) routes any key for which
`hasattr(self, key)` is true to `setattr`, and all five underscore fields
(`_player_room`, `_books`, `_persona`, `_fiction_model`, `_simulation_clock`)
are declared dataclass fields, so `hasattr` is always true for them. The only
direct writes into `_extra` anywhere in the tree are `interaction_views`,
`reaction_views` and `outcome_scene` (`loops.py:712-713, 944, 1028-1029`;
`perception.py:2939`) — none underscore-prefixed. The branch cannot be reached.

### 15. `mapping_quick` hand-builds a `scene_patch` shape that `_normalize_scene_patch` guarantees on the other path

`mapping.py:254-259` writes `{"rooms","entities","positions","stations",
"remove_entities","remove_rooms"}` by hand. `common._normalize_scene_patch`
(`agents/common.py:1026-1034`), which `mapping_stage` runs
(`mapping.py:127`), also guarantees `remove_adjacent`. Every consumer currently
spells it `diff.get("remove_adjacent") or []`
(`world/spatial_merge.py:792`, `persist/commit_room_registry.py:110`,
`agents/director_evidence.py:512, 571`), so nothing breaks today — but this is
one shape written in two places, and the copy that is not the normalizer is
already a field behind. `_normalize_scene_patch({})` would produce it.

### 16. `_ENFORCEABLE_PREFIXES` has no production reader; six test files assert against it

`narration.py:46-47` compiles the English pack's list eagerly at import. Every
live check goes through `_ling("_ENFORCEABLE_PREFIXES")` instead
(`narration.py:1003`, `1028`, `1150`), exactly as `AUDIT_DIRECTOR.md` finding 4
describes for `_UNCONSCIOUSNESS_CUE`/`_SLEEP_CUE`/`_STAY_UNDER_CUE`. Verified:
the constant's only non-test references are its own definition and
`AGENTS.md:53`.

Six test files score against the English object —
`test_pronoun_fidelity.py:35`, `test_player_person_discipline.py:269`,
`test_perception_self_narration.py:152`, `test_merged_speakers.py:69`,
`test_narrator_world_fidelity.py:624, 643`, plus
`test_language_pack_integrity.py:152` — none against what a non-English story
evaluates.

Weaker than the director case in one respect worth stating: the `en` and `ja`
packs currently carry **byte-identical** English values for this key
(`language_packs/{en,ja}/cards/linguistics.json`), so the two cannot disagree
today. That also means the pack indirection buys nothing here yet, and that a
future translation of the list would silently break every one of those six
tests' relationship to the code they think they cover.

### 17. `_MANIFEST_CHANNELS` is a hand-copy of `composer.CHANNELS`

`narration.py:290-293` declares the manifest's channel vocabulary with a
comment claiming it is *"the fixed vocabulary of `composer.CHANNELS` minus
`mixed`"*. It is a separate literal. Today the two agree
(`composer.py:94`). A seventh channel added to the composer would be built into
percepts, survive `observations_from_render`, arrive in `by_channel`
(`narration.py:340-341`) — and be silently dropped from the narrator payload by
the loop at `narration.py:406`, because only `mixed` has an explicit
pass-through (`narration.py:416-418`). Silent, and exactly the class this audit
was asked to look for.

### 18. The sensory manifest's sight `standing` list is not gated by the sight status it computes ten lines later

`narration.py:368-388`. `sight_standing` is filled from
`weather_words(scoped, "sight")` and then unconditionally appended with
`f"light: {light}"`, so the sight entry's `standing` list is never empty.
`sight_status` is computed afterwards and can be `("silent", "no light reaches
this room")`.

`weather_words`' sight arm gates on `sky_visible` / `falls_on_you` /
`wind_reaches` (`world/weather.py:566-575`) — room EXPOSURE, never light. So an
exposed room at night hands the narrator a single entry reading
`{"status": "silent", "why": "no light reaches this room",
"standing": ["storm sky", "heavy rain", "light: dark"]}`. Not a firewall
breach — the weather is legitimately the player's — but the payload contradicts
itself in the one field the prompt's SENSORY CHANNELS block is told to read as
authoritative.

### 19. A parallel group discards a successful sibling's paid output when an earlier member raised

`_run_parallel_group` (`runtime.py:467-477`) iterates the group in plan order
and does `raise h["e"]` on the first failure. Every member has already
finished — `_stream_parallel` joins them all (`runtime.py:437-438`) — so a
sibling that came LATER in the group and succeeded has its output thrown away
unsaved and unset on `ctx`. Contrast the Director fan-out, where "a failed call
costs exactly its own channels" is a stated property (`AGENTS.md`
§ Director orchestration). Cost only: resume re-runs both. Worth stating
because the parallel pairings exist precisely to save provider latency.

### 20. `_load_extra_players` parses a persona sheet unguarded, where its own module's siblings do not

`runtime.py:88`: `sheet = normalize_persona_data(json.loads(row["sheet"]))`,
inside the `PipelineContext` construction at `runtime.py:770-777` — i.e. before
`ensure_checkpoint`'s protection means anything and before any step runs. One
malformed `personas.sheet` row on a co-player kills every turn in that chat at
setup with a raw `JSONDecodeError`.

`narration._cast_pronouns` (`narration.py:226-229`) and
`narration._authored_body_parts` (`narration.py:211-214`) both wrap the same
parse in `try/except` and skip the row. Three readings of the same data, two
tolerances.

### 21. `agents/__init__.py` omits exactly the two stage entry points the facade test cannot notice

`agents/__init__.py:65-87` re-exports 11 of the 13 in-package `STEP_HANDLERS`
values. Missing: `narrator_extra` (`narration.py:1060`) and `background_react`
(`background.py`). `agents/README.md` step 7 makes the export conditional on an
external caller needing it, and no external caller does today — but
`test_agent_package.test_legacy_facade_exports_application_entry_points`
(`tests/test_agent_package.py:16-33`) asserts `required <= set(dir(agents))`
against a hand-written 12-name subset, so it is structurally incapable of
noticing a name the facade drops. Its sibling
`test_agent_roles_live_in_focused_modules` names `narrator` but not
`narrator_extra`.

### 22. Tests that assert on source text, in this slice

Same class as `AUDIT_DIRECTOR.md` finding 11; the Phase-2 mover should expect
these to break on any reorganisation, and none of them checks behaviour:

- `tests/test_pipeline_perspectives.py:207-209` —
  `assert inspect.getsource(runtime._run_pipeline).count("_run_parallel_group(") == 3`
  plus `assert "_stream_parallel(bus, jobs, holders)" not in src`. A substring
  COUNT over a 300-line function.
- `tests/test_engine_notes.py:253-262` — three substring assertions over
  `runtime.compute_step` (`"current_step_key.set"`, `".reset"`, `"finally"`).
- `tests/test_narration_person.py:214-220` — asserts the literal
  `"top - stored_support >= 2"` is present and `"top - runner >= 2"` is not.
- `tests/test_sensory_channels.py:243-249` — substrings over
  `narration.narrator` plus the prompt text.
- `tests/test_pipeline_perspectives.py:186-224` — `_between(CHAT_JS, ...)`
  slices `static/js/chat.js` between two function-name markers.

### 23. Comments describing behaviour the code no longer has

- `runtime.py:609-612`: *"pick_background_reactor (commit.py) is a cheap,
  LLM-free check"*. The function lives in `persist/commit_background.py:1008`,
  is a single-winner **wrapper**, and the stage calls the plural
  `pick_background_reactors` (`background.py:262`) with a cap. `CLAUDE.md` and
  `AGENTS.md:46` already say so; this comment and `PIPELINE.md:485` do not.
- `narration.py:161-170`: a 10-line comment block explaining which fidelity
  warnings are worth an automatic rewrite and why missing-proper-noun warnings
  were never in "this list" — attached to no symbol at all. The list it
  describes is `_ENFORCEABLE_PREFIXES`, 115 lines above at
  `narration.py:46-47`; what follows it is the unrelated craft-screen comment
  and `_craft_tells`. Same shape as `AUDIT_DIRECTOR.md` finding 2 (a doc block
  read against the wrong subject) and finding 3 (a doc block far from what it
  documents).
- `narration.py:1043-1044`: *"ctx.warnings is accumulated pipeline-wide but
  never surfaced anywhere (not streamed, not persisted, not logged)"*. False
  since the engine-notes work: `_with_engine_notes` (`runtime.py:302-305`)
  persists `warnings_for_step(key)` on every saved step, and the pipeline
  drawer renders them (`AGENTS.md:88`). `pipeline_context.py:177-184` documents
  the opposite of this comment, six files away.

### 24. Two representations of "is this the opening turn"

`_run_pipeline` decides it from the turn row: `establishment = (turn_row["idx"] == 0)`
(`runtime.py:784`). `narrator` decides it from a model stage's output:
`est = ctx.get("director_establish") or {}` … `if est:` (`narration.py:821-827`).
`ctx.turn.idx` is available at both sites.

The narration spelling gates three separate things — which view is read
(`narration.py:823` vs `826`), the `scene_opening` payload flag
(`narration.py:971`), and the entire `_world_fields` / `_fidelity_facts` block
(`narration.py:886`) — on the truthiness of a dict a model produced. Latent
rather than live today (`DirectorEstablish` default-fills, so the dump is never
empty), but it is a rule with two owners and only one of them is authoritative.

### Smaller notes, verified but not worth a numbered finding

- `mapping.py:90-91` calls `style_guide(chat["id"])` twice to build one payload
  key — two `world` reads per mapping call.
- `runtime.py:636` defines `_BG_KEY` *after* `build_plan` uses it. Legal
  (resolved at call time), but it reads as an error at the use site.
- `runtime.py:1079-1080`: when `run_pipeline` is handed an `abort`, it writes
  `ABORTS[(chat_id, frame_id)] = abort` with no check, while `begin_pipeline`
  goes to some length to make the check-then-register atomic
  (`runtime.py:173-180`). Harmless while callers pass the same `frame_id` to
  both — `web/app.py` does — but the invariant is enforced in one of the two
  entry points.
- The `only_key` path never calls `_assert_plan_materialized`
  (`runtime.py:798-873`), unlike both other branches.
- `resume_key_for_turn` returns `"director_interpret"` for a turn row that does
  not exist (`runtime.py:502-503`), which a caller then hands to
  `run_pipeline` for that same missing turn.
- `build_plan`'s `int(char_id)` (`runtime.py:566-567`) and `_dict(fl.get(...))`
  will raise on a hand-edited `director_interpret` variant whose `reactors`
  holds a name. The model path is safe (`schemas.py:4388`, `_coerce_int_list`);
  the pipeline drawer's manual-edit path is not.

---

## Part 2 — what the code actually does, checked against the documents

Method as in `AUDIT_DIRECTOR.md`: each module's behaviour written from the code,
then compared against `Design.md`, `AGENTS.md`, `docs/guides/PIPELINE.md`,
`agents/README.md` and `docs/guides/EXTENSIONS.md`. Verdicts: RIGHT / STALE /
INCOMPLETE.

### `agents/runtime.py`

Owns five things: the plan (`build_plan`, `establishment_plan`), the handler
registry (`STEP_HANDLERS`, `register_step`, `compute_step`), the streaming
thread machinery (`Bus`, `_stream_one`, `_stream_parallel`,
`_run_parallel_group`, `_step_stream`), the resume/rerun state machine
(`resume_key_for_turn`, `_run_pipeline`'s three branches), and the
per-(chat, frame) abort registry (`ABORTS`, `begin_pipeline`, `request_abort`).

`compute_step` is the single funnel that binds three contextvars —
`current_step_key`, `current_warning_sink`, `call_ledger_sink` — with `getattr`
tolerance for stand-in contexts and a `finally` that resets all three
(`runtime.py:257-292`). That matches `AGENTS.md:88` clause for clause,
including "warning attribution is by contextvar, never by list position".
**Docs: RIGHT.**

### `agents/narration.py`

Three stages' worth of work in two entry points. `narrator` assembles a payload
of ~20 keys, calls `_generate_narration`, then runs two correction ladders: one
enforceable fidelity rewrite (`narration.py:1003-1010`) and up to two craft
rewrites accepted only if they preserve fidelity AND strictly reduce the tell
count (`narration.py:1017-1034`). Everything player-facing then passes
`_strip_player_echo` → `_dedupe_view_sentences` → `_cap_repeated_quotes`
(`narration.py:1052-1057`). `narrator_extra` mirrors it per persona, in a
`ThreadPoolExecutor` with one copied context per job — the worked example
`AGENTS.md:40` cites for the fan-out contextvar hazard, and it is correct here
(`narration.py:1198-1201`).

The information-boundary work is real and subtracts, as claimed. `event_order`
admits an NPC line only if its quote body is byte-present in the player's own
view (`narration.py:551-554`), an NPC act only if overt AND
`_player_sees_character` passes (`narration.py:485-494`, `578-606`), and applies
`_self_second_person(text, player_forms)` to the act surface
(`narration.py:572-573`) — the design-note-20 identity floor on the second
delivery. `_position_delta_payload` drops anyone who left and withholds an
origin room the player cannot see into (`narration.py:634-653`).
`_sensory_channels_manifest` refuses outright for an enclosed player
(`narration.py:329-330`).

**Against `Design.md`: two rows are now materially wrong.**

- Row `Design.md:167`: *"Narrator exemplar pool, event-amnesiac | **Built** |
  `exemplars` setting read in `agents/narration.py`; **narrator receives the
  player view, not the event stream**"*. The `exemplars` half is right
  (`narration.py:990`). The second half is no longer true: the payload carries
  `event_order` — the pipeline's own numbered stimulus→response record built
  from `director_interpret.sequence`, both loops' rounds and
  `character_results` (`narration.py:422-575`) — plus
  `co_present_positions`, `portal_states`, `sensory_channels`, `spatial_frame`
  and `authored_body_parts`. Every one of them is gated, and `AGENTS.md:53`
  describes `event_order` accurately as "a SECOND delivery of this beat's prose
  to the player". The row is the thing that is stale, and the fix is to say
  *a filtered event record, gated to what the view already delivered*, not to
  say the narrator has none.
- Row `Design.md:891` control column: *"Deny the narrator everything but the
  player's perception object"*. Same divergence, stated as the control.

**Against `AGENTS.md:53` (§ Narration): RIGHT.** Every clause checks out —
`_ENFORCEABLE_PREFIXES` (with finding 16's caveat about which spelling is
live), `_ordered_beat_events` carrying `player_forms` rather than inheriting a
floor, `_check_narration_person_match` being warning-only, "read `event_order`
rather than the raw dialogue log".

### `agents/mapping.py`

`mapping_stage` builds a retrieval query from the declaration, the mapping
request, the location query, raw input and the last five events; on the
establishment path it also folds in the scenario and every cast member's public
surface (`mapping.py:43-54`). It retrieves `k=14` with `knowledge` excluded,
attaches owed history, and hands the model a payload whose recent-messages
field is deliberately un-entitled (`director_context(..., entitled=False)`,
`mapping.py:78-79`) — X18, correctly implemented and correctly commented.
`_join_relevant_lore` replaces the model's echoed lore text with the engine's
own rows and WARNS on an uncited id rather than dropping it
(`mapping.py:165-196`).

`mapping_quick` escalates to the full stage on four conditions and otherwise
merges fresh retrieval over the cache, id-first (`merge_lore`,
`mapping.py:265-297`).

**Against `AGENTS.md:51` (owed history is the obligation ledger's ONLY
reader): RIGHT** — `attach_owed_history` appears once
(`mapping.py:65-69`), on the `mapping_stage` path only. Worth stating
explicitly since it is not written down anywhere: a turn that takes
`mapping_quick` reads no obligation ledger at all. *(live)* that is 1,896 of
2,359 mapping steps, 80%. Consistent with the design (arrival is the earning
event and arrival forces `mapping_stage` via `movement.to_room`), but it is an
inference the reader has to make.

**Against `PIPELINE.md:176-181`: RIGHT**, with finding 12's drift.

### `agents/storage.py`

Four concerns, each with its atomicity reasoning in place: `save_step` wraps
deactivate-then-activate in one transaction (`storage.py:27-56`),
`delete_step` wraps variant-then-step deletion (`storage.py:121-123`),
`active_content` strips `ENGINE_NOTES_KEY` on the rehydration path so a rerun
cannot carry the engine's repair log into a prompt (`storage.py:64-74`), and
`clear_steps_stale` is deliberately scoped to plan keys so orphans keep showing
as stale (`storage.py:106-112`).

**Against `PIPELINE.md:589-593` and `AGENTS.md:88`: RIGHT.** The one thing the
docs do not say, and that finding 7 turns on: `save_step`'s `reasoning`
ContextVar fallback (`storage.py:46-51`) is only correct for a caller on the
same thread as its own model call, and no pipeline caller is.

### `agents/__init__.py`

A pure re-export facade, 107 names in `__all__`, derived from `globals()`. No logic.
**Docs: RIGHT**, with finding 21's two omissions.

### `core/pipeline_context.py`

Three dataclasses plus two contextvars and `StepTaggedWarnings`. The
warning-tagging design (tag in the list, not at ~40 call sites, so a stand-in
context with a bare list keeps working) is stated in the class docstring
(`pipeline_context.py:47-60`) and holds. `note_llm_call` and
`llm_calls_for_step` (`pipeline_context.py:290-306`) implement the per-call
ledger `AGENTS.md:88` describes, tagged by contextvar for the same reason.
`tell_director` is the engine→model feedback channel, deduped
(`pipeline_context.py:308-312`).

**Docs: RIGHT** as far as they go. What no document states, and what findings 1,
3 and 14 all sit on: this class has **two** storage mechanisms with different
semantics — declared fields, and an untyped `_extra` dict that carries both
undeclared step outputs and three anonymous cross-stage side-channels — and
`__contains__`, `get`, `_assert_plan_materialized` and the resume paths all
treat them differently.

### `docs/guides/PIPELINE.md` verified against `build_plan`, line by line

The document claims to state the exact flow. Here is the comparison.

**Opening turn** (`PIPELINE.md:24-34` vs `runtime.py:698-705`): the five stages
and their order are **exactly right**. `mapping_stage → director_establish →
perception_establish → narrator → commit`. What the section does not say, and
should:

- no `narrator_extra` is ever planned here (finding 4);
- `establishment_plan()` is the one plan that does not go through
  `_extension_splices` (finding 5).

**Normal turn** (`PIPELINE.md:118-153` vs `runtime.py:550-634`): the diagram and
both "conditions the diagram cannot show" are **exactly right**, including the
subtleties:

| PIPELINE.md claim | code | verdict |
| --- | --- | --- |
| plan built dynamically from `director_interpret.flow` | `runtime.py:556-558` | RIGHT |
| `mapping_stage` OR `mapping_quick` on `flow.needs_mapping` | `runtime.py:559-562` | RIGHT |
| `reaction_loop` when contested physical reactions required | `runtime.py:586-589` — `flags["contested"] AND reactors` | RIGHT |
| `interaction_loop` when reactors exist and `autonomy > 0` | `runtime.py:591-593` | RIGHT |
| parallel `character:<id>` when reactors exist, `autonomy == 0`, NOT contested | `runtime.py:594-597` | RIGHT |
| "reactor set is consciousness-gated FIRST" | `runtime.py:574-579`, before every branch | RIGHT |
| "contested beats plan no parallel character steps… recorded as a deliberate fix" | `runtime.py:598-605`, an 8-line comment saying exactly that | RIGHT |
| `background_react` unconditional but self-gating | `runtime.py:613` | RIGHT |
| `narrator_extra` when the chat has other human players | `runtime.py:621-628` | RIGHT, but omit "…and never on the opening turn" |

**Divergences found:**

1. **PIPELINE.md never mentions extensions.** Grepped: zero occurrences of
   `ext:`, `extension` or `Extension` in the whole 658-line file. Yet
   `build_plan`'s final act is `_extension_splices` (`runtime.py:634`), a plan
   may contain `ext:<id>:<key>` steps at any anchor, and
   `docs/guides/EXTENSIONS.md:313-315` sends the reader **here** for the anchor
   vocabulary: *"See [`PIPELINE.md`](PIPELINE.md) for the full plan."* The
   authority on the exact plan omits the one mechanism that can change it.
   **PIPELINE.md is wrong (incomplete).**
2. **`PIPELINE.md:485` names the wrong owner.** *"`persist/commit.py`'s
   `pick_background_reactor` is a deterministic, LLM-free check"*. The gate is
   `persist/commit_background.py:1018` `pick_background_reactors` (plural, with
   a cap); `pick_background_reactor` (`commit_background.py:1008`) is a
   single-winner wrapper the stage does not call — `background.py:262` calls the
   plural. `CLAUDE.md` and `AGENTS.md:46` are already correct.
   **PIPELINE.md is stale**, along with the matching comment at
   `runtime.py:609`.
3. **`PIPELINE.md:601` overstates what resume restores.** *"Earlier active
   variants are loaded back into `PipelineContext`."* True of step content;
   false of `outcome_scene`, `interaction_views` and `reaction_views`, which no
   path rebuilds (finding 3). **PIPELINE.md is incomplete**, and this is the
   costly one — a reader checking whether a reroll is faithful is told it is.
4. **`PIPELINE.md:604` overstates materialization.** *"`_assert_plan_materialized`
   verifies that every planned stage has a valid result before the turn is
   considered complete."* The `only_key` branch (`runtime.py:798-873`) never
   calls it. **PIPELINE.md is incomplete.**
5. **`PIPELINE.md:519-527` (`narrator_extra`)** correctly records S3-A6 and
   correctly describes `_PRESENTATIONAL_TAIL`, but "Planned only when the chat
   has other human players" needs the turn-0 exclusion (finding 4).
   **PIPELINE.md is incomplete.**

Everything else in §Streaming (`PIPELINE.md:565-593`) is **RIGHT**, including
the narrow-conditions paragraph — all three pairings do go through
`_run_parallel_group`, `group` does ride every `step_start`
(`runtime.py:461-462`), `parallel_with` does ride every saved step
(`runtime.py:472-473`), and `_engine_notes` is stripped by `active_content`.

### `agents/README.md`

The "Adding an agent stage" checklist is accurate and is the right document.
Two corrections it needs:

- Step 5 ("Give it a field on `PipelineContext` … if later stages read its
  output") is violated by `background_react`, whose output five modules read
  (finding 1).
- The closing note — *"step ids themselves are also named in
  `schemas.SCHEMA_MAP` and `core/pipeline_context.py`, which is why steps 2 and
  5 exist"* — is right as far as it goes and one list short:
  `static/js/chat.js`'s `FRIENDLY_STEP_LABELS` is a fourth, and it is the one
  currently wrong (finding 2). The README's own warning that a step id is a
  published name ("Renaming a core step therefore breaks every extension
  anchored on it, in a way nothing in this repo will catch") applies to that
  list too.

### Cross-document verdicts, summarised

| document | verdict |
| --- | --- |
| `docs/guides/PIPELINE.md` opening-turn flow | **RIGHT**, incomplete on turn-0 `narrator_extra` and extension splices |
| `docs/guides/PIPELINE.md` normal-turn flow | **RIGHT** — every branch of `build_plan` verified, including both "conditions the diagram cannot show" |
| `docs/guides/PIPELINE.md` §`background_react` | **STALE** — wrong module, wrong (singular) function |
| `docs/guides/PIPELINE.md` §Resume and rerun | **INCOMPLETE** — the `_extra` side-channels are not restored; `_assert_plan_materialized` is skipped on the reroll path |
| `docs/guides/PIPELINE.md` §Streaming | **RIGHT** |
| `docs/guides/PIPELINE.md` (extensions) | **INCOMPLETE** — no mention at all, while `EXTENSIONS.md` cites it as the plan authority |
| `AGENTS.md:53` § Narration | **RIGHT** |
| `AGENTS.md:41` § Flow planning row | **RIGHT** (`build_plan`, `_run_pipeline`, `agents/storage.py`, `persist/checkpoints.py`) |
| `AGENTS.md:88` § Inspecting a turn | **RIGHT** |
| `Design.md:167` "Narrator exemplar pool, event-amnesiac" | **STALE** — "not the event stream" is no longer true; `event_order` is a gated event record |
| `Design.md:891` narrator control column | **STALE** — same divergence, stated as the control |
| `agents/README.md` add-a-stage checklist | **RIGHT**, one list short and one step violated |
| `docs/guides/EXTENSIONS.md:320-323` anchor contract | **STALE against the opening turn** — the stated rule predicts the opposite of the behaviour there |

Nothing in this slice was found built-and-quietly-lost. Two things were found
built-and-never-reachable (`spatial_facts`, finding 8; the turn-0 extra-player
render, finding 4), one found built-and-never-read (`candidates`, finding 6),
and one found half-fixed (the reasoning trace, finding 7).

---

## Unverified suspicions

Listed separately because I could not close them without running the suite or
observing a live turn, both out of scope for this task.

- **Finding 10's wedge is reasoned from code, not reproduced.** The chain
  (gate drops a sleeper → `_awareness_exits` wakes them → `resume_key_for_turn`
  recomputes a plan containing a step that never ran → 409 → 500) follows from
  four verified facts, but I did not construct the turn. The narrower claim —
  that `build_plan`'s reactor set depends on state the same turn commits, while
  `resume_key_for_turn` reads it un-restored — is verified.
- **How often `_run_parallel_group` actually runs.** *(live)* the corpus shows
  three `character:<id>` steps total and 135 `narrator_extra`, so the parallel
  paths are rare — which is consistent with `PIPELINE.md:583-587` ("a typical
  story runs strictly sequentially") and means findings 7 and 19 are structural
  rather than currently expensive.
- **Whether the SPATIAL GROUND TRUTH prompt block measurably harms output.**
  Finding 8 establishes the field never arrives and the block is therefore
  unreachable instruction. Whether a model reading "if `spatial_facts` is
  present…" for an absent key degrades its use of `spatial_frame` is a bench
  question (`tools/`), not a read question.
- **Finding 18's exposed-dark-room case.** The contradiction is structural in
  the code; I did not confirm that a live scene reaches
  `effective_light == "dark"` in a room whose exposure passes
  `weather_words("sight")`. An outdoor night scene is the obvious candidate.
- **`_stream_one`'s stray-event path.** `runtime.py:382-392` yields any event
  that is not its own `__done__`. With one `Bus` per pipeline and strictly
  sequential use of `_stream_one` I could construct no interleaving that puts
  another key's `__done__` on the queue, but the loop is written as though one
  could.
