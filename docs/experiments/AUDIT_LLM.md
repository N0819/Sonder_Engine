# Audit: the `llm/` package, read whole

Working notes in the register of
[`AUDIT_DIRECTOR.md`](AUDIT_DIRECTOR.md): a finding is written down and the
reading continues. **Nothing below was changed.** No source file was edited,
`docs/UNBUILT.md` was deliberately not touched (concurrent work), and no test
suite was run.

**Baseline revision:** `be2a2ee`. Every `file:line` is as of that revision.

**Read end to end:** `llm/schemas.py` (5,259), `llm/providers.py` (3,158),
`llm/prompts.py` (408), `llm/llm_quality.py` (655), `llm/prompt_cache.py` (78),
`llm/__init__.py` (6) — 9,564 lines. Plus the data they serve
(`language_packs/en/cards/system_prompts.json`, 377,327 characters of authored
prompt across 41 ids; `language_packs/{en,ja}/prompt_policy.json`) and the
existing guards (`tools/project_check.py`
`check_prompt_schema_ops` / `check_specialist_prompt_chunks` /
`check_prose_author_chunks` / `check_language_pack_surfaces` /
`check_no_dead_prompts`).

24 findings. The three that cost something today are **1** (the six specialist
sheets exist twice and have already drifted, in both packs), **2** (a worked
example the engine's own validator rejects, shipped as the repair contract) and
**7** (every warning `validate_llm_output_strict` writes is discarded by its
only caller, so a dropped world-state channel is silent).

---

## Part 1 — findings. FLAGGED, NOT FIXED.

### 1. The six specialist sheets are stored TWICE in every pack, and the copies have already drifted

`llm/prompts.py:39-42` builds `DEFAULT_PROMPTS` from the pack card's
`prompts` map, which contains `director_body`, `director_social`,
`director_contact`, `director_objects`, `director_spatial`,
`director_offscreen` as whole sheets. `llm/prompts.py:50-59` and
`specialist_prompt` (`llm/prompts.py:266-282`) build the sheet the runtime
actually sends from a *different* card key, `specialists.<name>.core` +
the granted `chunks`. Nothing checks the two agree.

They do not:

| pack | sheet | stored copy vs assembled sheet |
| --- | --- | --- |
| en | `director_spatial` | **-1,518 chars**: the whole `comms_ops` (VOICE CHANNELS) chunk is missing from `prompts["director_spatial"]` |
| ja | all six | every one differs; the two copies are INDEPENDENT TRANSLATIONS of the same English source, differing line by line (`director_spatial` -1,283, `director_offscreen` -669, `director_contact` -161, `director_objects` -36, `director_social` -24, `director_body` -12) |

Three costs, all live:

* **The prompt editor lies.** `/api/default_prompts` and the bootstrap ship
  `DEFAULT_PROMPTS`, so a host reading `director_spatial` in ⚙ Prompts sees a
  sheet with no VOICE CHANNELS block while the engine sends one.
* **Editing one word deletes a chunk.** `specialist_prompt` consults
  `_preset_override(pid)` FIRST (`llm/prompts.py:271-274`) and, when a preset
  carries that id, uses the stored body *whole* — scope selection included.
  `static/js/settings.js:3207` saves any textarea that differs from the
  baseline, so one edit to `director_spatial` permanently drops `comms_ops`
  from every beat that grants it.
* **Every language pays twice.** The six duplicate bodies are 103,817 of the
  English card's 377,327 characters (27.5%), and
  `check_language_pack_surfaces` requires each of them to be translated
  independently — which is exactly how the ja pack ended up with two
  paraphrases of every specialist sheet.

`tools/project_check.py:433-450` already enforces this equality **for the prose
author** ("`DEFAULT_PROMPTS['director_resolve_lean']` is not the full-scope
assembly of `PROSE_AUTHOR_SHEET`"). The same check for the six specialists does
not exist, which is the whole finding: one half of the registry is held level
and the other half is not.

### 2. `OUTPUT_EXAMPLES["scene_life"]` is INVALID against the schema it teaches

`llm/schemas.py:4747-4763` shows each entry's speech as
`{"exact_quote": …, "volume": …, "intended_target": …, "tone": …}`.
`SceneLifeEntry.speech` is `Optional[DialogueLogEntry]`
(`llm/schemas.py:1799-1810`) and `DialogueLogEntry.speaker`
(`llm/schemas.py:1772`) is REQUIRED. Verified by running the engine's own
validator over the example:

```
FAIL scene_life ['entries.0.speech.speaker: field required']
```

It is the only example in the table that fails on shape (the establish one
fails on semantics — finding 3; the other 18 pass). This is not decoration:
`output_example(step_key)` is the `required_json_example` handed to the model on
the temperature-0 repair (`llm/llm_quality.py:486`) and on every fallback
candidate (`llm/llm_quality.py:552`), and `scene_life` goes through that ladder
(`agents/background.py:574` → `_agent_json` → `complete_validated_json`). So a
scene_life call that just failed validation is answered by handing the model an
object the validator would reject for the same reason.

The pack's own shape line has it right — "`speech:{speaker, exact_quote,
volume, intended_target, tone}|null`" — so the example is the outlier, not the
prompt.

### 3. `OUTPUT_EXAMPLES["director_establish"]` fails the exact semantic check that sends establish into repair

`llm/schemas.py:4513-4534` shows `"rooms": {}` and `"positions": {}`.
`semantic_output_errors` (`llm/schemas.py:4969-4976`) rejects an establish
output with either one empty:

```
FAIL director_establish ['rooms is empty', 'positions is empty']
```

An opening turn that fails on "rooms is empty" is repaired by a call whose
`required_json_example` shows rooms empty. This is the same defect the
`state_diff.time` comment two hundred lines below documents in full
(`llm/schemas.py:4562-4577`: "this same example is the
`required_json_example` handed to the repair attempt, so the repair was shown
the identical `null` and had no way to converge") — unfixed, one step key over.

### 4. The `director_resolve` example still teaches the DEAD monolith's `state_diff`

`llm/schemas.py:4536-4600`. Its `state_diff` carries 24 keys. The prose
author's own sheet says (`director_resolve_lean`, DELEGATED CHANNELS block):

> "None of those channels exists in YOUR output shape, and you must not add
> one: anything you write in a delegated channel is discarded unread and
> re-encoded by its specialist, so every token spent there buys nothing and
> slows the beat. … What stays YOURS in state_diff: time, weather, location,
> consequences".

Measured against that sentence: **19 of the 24 keys in the example are
delegated** (positions, rooms, entities, remove_entities, remove_rooms,
remove_adjacent, conditions, inventory_ops, contact_ops, substance_ops, poses,
overlays, attire, cast_changes, world_facts, introductions, offscreen_plan_ops,
crowd_ops, telling_ops, courier_ops, artifact_ops), and **two of the four that
are the author's own — `weather` and `location` — are missing from it.**
`agents/director.py:2833-2839` calls the prose author with `step_key
"director_resolve"`, so this is what a resolve repair or fallback is shown.
`AGENTS.md` states `channels_replaced` "is `[]` on every healthy beat"; this
example is an instruction to make it non-empty.

### 5. The `character` repair example omits the psychology tiers the prompt asks for

`llm/schemas.py:4673-4746` lists 18 keys. The character sheet's own
`Output STRICT JSON` line asks for `project_ops` (named 4 times in the sheet),
`intent_ops` (4), `manifest` (2) and `follow_op` (3). None of the four is in
the example, nor is `drive_shift`, `speech`, `action` or `actions`.

The repair instruction beside it is "Rebuild the complete response. Preserve
valid details and restore omitted information" (`llm/llm_quality.py:487-490`),
against an example that is a strict subset. `project_ops` is precisely the
field whose silent absence cost an entire tier — the schema comment at
`llm/schemas.py:3002-3020` records "0 of 14 live banks have ever held a
project" — so a repair rung that shows the model a shape without it is the same
hole one layer up. Nothing here is enforced: the fields are optional, so the
shrunken answer validates.

### 6. `tick_interval_seconds`: asked for on every conditions beat, read by nothing, and the tick it configures cannot fire

The body specialist's `conditions` chunk instructs: "record them in
`state_diff.conditions` with condition_id, subject_id, kind, severity,
started_at_seconds, **tick_interval_seconds**, and state", and
`OUTPUT_EXAMPLES["director_body"]` repeats it (`llm/schemas.py:4609`).

Grepped `-w` over every `*.py` outside `.claude/`: `tick_interval_seconds`
occurs exactly twice, both in `llm/schemas.py` — the declaration on the dead
`PersistentCondition` model (`llm/schemas.py:1414`, finding 19) and the worked
example. No commit path reads it. What commit DOES read is
`next_tick_seconds` (`persist/commit_entities.py:485`), which no prompt asks
for and no model has ever sent, so `world_conditions.next_tick` is written NULL
on every row. And no query anywhere selects `next_tick`: the six readers of
that table select `subject_id`, `payload`, `condition_id`, `started_at`,
`expires_at`. `core/db.py:720` maintains
`idx_world_conditions_due ON world_conditions(chat_id, active, next_tick)` for
a query that does not exist.

So a condition cannot tick, the field the model pays tokens for every beat is
unreachable, and the field the schema would need is unasked. (`expires_at` is
real — `persist/commit_mechanics.py:66` — so expiry works and only ticking is
dead.) The prompt half is mine; the commit/db half belongs to whoever owns
`commit_entities`.

### 7. Every warning `validate_llm_output_strict` produces is discarded by its only caller

`llm/schemas.py:5185-5230` is the deterministic prune: when every validation
error is rooted under a `state_diff` sub-field (or a specialist channel), those
fields are DROPPED and the beat is returned `valid=True` with a warning saying
so — "Dropped malformed state_diff.%s so the beat could commit what it did
adjudicate (%s)".

`complete_validated_json` returns `report.output` at every exit
(`llm/llm_quality.py:341`, `447`, `470`, `577`) and never touches
`report.warnings`. `ValidationReport.warnings` (`llm/schemas.py:4482`) has no
production reader anywhere in the tree — verified by grep over all `*.py`; the
only readers are `tests/test_state_diff_prune.py:54` and `:102`.

The stages re-run `validate_llm_output` afterwards
(`agents/director.py:2881`, `agents/character.py:3357`) and push THOSE warnings
into `ctx.warnings` — but that second pass runs on the already-pruned output,
which validates cleanly, so it can never recover the message. Net effect: the
engine can silently drop `state_diff.attire` (or `positions`, or a whole
specialist channel) from a committed beat, and the sentence written to say so
reaches neither `ctx.warnings`, nor `_engine_notes`, nor the pipeline drawer.
This is the shape `AGENTS.md` names ("Real leaks fail open and silent, because
the thing that would have announced them is the thing that did not run"),
applied to world state rather than to knowledge. The mechanism is tested; its
delivery is not.

### 8. `comms_ops` is classified as a dict channel and is declared a list

`llm/schemas.py:3549-3552` puts `comms_ops` in `_SPECIALIST_DICT_CHANNELS`;
`_SPECIALIST_LIST_CHANNELS` (`:3553-3559`) does not carry it. It is declared
`list[CommsOp]` on all three models that hold it (`llm/schemas.py:1697`,
`2027`, `2414`). Consequence at `llm/schemas.py:4219`: a spatial specialist
answering `comms_ops: []` has it rewritten to `{}` by
`_coerce_empty_list_to_dict` before validation.

It is inert TODAY only because `LenientModel` reverses it one step later
(`llm/schemas.py:707-709`, "`{}` or `""` where a list was declared" → `[]`).
Every other channel in those two sets is classified correctly (checked
exhaustively against the declared annotations; `destruction` is deliberately in
neither). A constant that says a list is a dict, kept harmless by a coercion in
another function, is one edit away from eating the channel.

### 9. `greeting_interpret` pays for a model call whose output is 9/11 unread, and its one deterministic guard sets a flag nobody reads

`GreetingInterpret` (`llm/schemas.py:3273-3287`) declares `location`, `time`,
`scene_description`, `rooms`, `positions`, `entities`, `attire`,
`character_state`, `knowledge_seeds`, `player_room`, `notes`.
`story/greetings.py` is the only consumer and reads exactly two:
`extraction.get("time")` (`:248`) and `extraction.get("knowledge_seeds")`
(`:268`). The launch does not bake an establishment from the extraction at all
— it puts the greeting prose in `chats.scenario` and runs the ordinary
`director_establish` (`story/greetings.py:234`, `:319-327`).

Grepped `-w`: `character_state` occurs only in the schema and its own worked
example; `player_room` has no reader in `story/`, `agents/` or `persist/`.
The example (`llm/schemas.py:4778-4797`) fills all of them, including
`attire: {"Kara": {"summary": …}}` — a shape `AttireState`
(`llm/schemas.py:1632-1641`, `wearing`/`state`/`regions`) does not have and
nothing would read if it did.

Worse, `revealed_in_prose` (`llm/schemas.py:3267`) is written by a
deterministic information-boundary guard — `story/greetings.py:119-121`, "a
'secret' seed that names the player is not actually asymmetric, so it can't be
routed as private-from-the-player" — and **read by nothing**. The seed loop at
`story/greetings.py:268-302` routes every seed to that character's memory
regardless of the flag. The guard cannot fire in the sense that matters: there
is no branch for it to change.

`docs/design/GREETING_IMPORT_DESIGN.md:136` describes the branch
("For each `knowledge_seeds` with `revealed_in_prose == False`: append to
`chat_chars.state.private_history` …"), which is the half that was not built.
Design notes are argument, not authority — but the schema and its example are
still shaped for the unbuilt half, and a per-card LLM call pays for it.

### 10. `Observation`'s defaults and the composer's compaction defaults disagree, and the schema comment says they cannot

`llm/schemas.py:1519-1546` declares `intensity=0.5`, `suddenness=0.0`,
`ambiguity=0.5`, and its comment states: "the engine's own projection
(`agents/composer.py`, `OBSERVATION_DEFAULTS`) omits wrapper fields at their
resting values — absent means the default — so a compacted observation must
validate."

`agents/composer.py:1615-1622` omits `intensity` at **0.35**, `suddenness` at
**0.1**, `ambiguity` at **0.15**. A compacted observation does validate — and
comes back with three different numbers than the ones the composer measured.
Two representations of one rule, already drifted on three of six fields.

Harmless today for two reasons, both worth stating: no deterministic code
consumes the numbers (`docs/guides/PIPELINE.md` says so explicitly), and
`Observation` has no production reader at all — grepped `-w`, it appears in
`llm/schemas.py` (declaration plus one cross-reference comment) and in five
test files, nowhere else. The model that documents the compaction is itself
dead code (finding 19's class, kept out of that list because a comment names
it).

### 11. `llm/schemas.py` drops model output in ~17 places and has no way to say so

The module imports `html`, `json`, `math`, `re`, pydantic and
`story.attire`. It does not import `core.pipeline_context`, so
`note_step_warning` is unreachable from it, and the only repair that reports
itself does so by smuggling a list back through the return value
(`_uncross_concealed_speech` → `result["concealment_repairs"]`,
`llm/schemas.py:4029-4098`, read at `:4451`).

Everything else is silent. Non-exhaustive, all verified by reading:

| site | what disappears |
| --- | --- |
| `:723` | a free-string list past 64 entries, truncated |
| `:739` | non-dict elements of a bare `list[dict]` (`relevant_lore`, `sequence`, `staged_lore`) |
| `:2872`, `:2887` | `response_candidates` in an unrecognised shape → `[]`, the whole deliberation |
| `:2923` | `serves` past 6 entries |
| `:3072-3077` | `remember_lines` with no quote |
| `:3078-3091` | `memory_disputes` missing both locators |
| `:3092-3098` | `association_updates` with no `cue` |
| `:3388-3418` | `considered_responses` non-list → `[]` |
| `:3474-3524` | non-dict condition entries |
| `:3598-3634` | entity-def-shaped sibling debris, dropped rather than hoisted |
| `:4341` | dialogue lines whose `exact_quote` is empty |
| `:4285-4295` | sequence entries that are neither dict nor prose |
| `:3451-3472` | a non-dict `state_diff.time` |

Each individual choice is argued in its own comment and most are right — a
dropped alternative beats a crashed beat. What is missing is the third option
the concealment repair proves is available: keep the beat AND say what was
dropped. As it stands, a 64-entry truncation and a well-formed 64-entry list
are indistinguishable in the stored variant.

### 12. The native Anthropic request path silently ignores four request features the rest of the engine advertises

`_chat_complete_once` branches at `llm/providers.py:2085` (and the async twin
at `:2475`): the Anthropic body is built and RETURNED inside that branch, so
the four calls below it never run for `kind="anthropic"`.

* `_apply_reasoning_effort` (`:914`) — the per-role reasoning-effort setting is
  a first-class UI control (`web/app.py:1439`, `static/js/settings.js:2671`)
  with no provider-kind awareness. Set it on a native Anthropic connection and
  nothing is sent and nothing is said. Anthropic's own control is
  `thinking: {type, budget_tokens}`, which this module never emits.
* `_apply_json_mode` (`:1623`) — so `json_schema`, whose measured value is
  "narrator 2/5 → 5/5 valid, character 53.4s/2029 tokens → 15.3s/587", is
  unavailable on that path. The schema is still built and cached
  (`llm/llm_quality.py:250-273`) and then dropped on the floor.
* `_apply_cache_affinity` (`:678`) — correct to skip (native caching is
  explicit), but it means `cache_affinity_allow` naming an Anthropic provider
  does nothing, which the setting does not say.
* `_apply_provider_routing` (`:770`) — correctly OpenRouter-only.

The first two are the finding: a configured value that changes nothing, with no
warning, on the one provider kind the module treats specially everywhere else.

### 13. `_note_served_model` cannot fire on either Anthropic streaming path

`llm/providers.py:1779` sets `served = ""` in `_sse_anthropic` and never
assigns it again; `:2627` does the same in `_sse_anthropic_async`. Both then
call `_log_usage(..., served=served, kind="stream")` (`:1817`, `:2670`), so
`_note_served_model` (`:1971`) returns immediately on `if not served` and the
ledger entry records `served == requested` by fallback (`:2029`).

The information is present in the stream: Anthropic's `message_start` event
carries `message.model`, and the code already opens that object to read
`message.usage` (`:1802-1804`). The OpenAI-compatible SSE paths do read it
(`:1740-1742`, `:2597-2599`). The docstring at `:1971` argues that an
unrecorded model substitution is what made a whole latency investigation
produce artefacts; on this path the guard is present and cannot report.

### 14. `_targeted_field_patch` has two dead parameters, and the comment above its call names the wrong model role

`llm/llm_quality.py:188` — `def _targeted_field_patch(step_key, parsed,
errors, payload)`. AST-checked: `step_key` and `payload` are referenced nowhere
in the body. It is the only function in the module with unused parameters.

`payload` being unused is worth a second look rather than a rename: the cheap
repair asks the `repair` model to fix a field with **no view of the request
that produced it** — just the invalid fragment and the validator's message
(`:219-227`).

And `llm/llm_quality.py:458` says "Try a small `utility` call that returns only
the corrected fields" — the call at `:220` uses role `"repair"`. `repair` and
`utility` are separate rows in `ROLES` (`llm/providers.py:1053`, `:1054`) that
a host configures independently, so the comment names a lane that is not billed.

### 15. The enforced JSON schema is sent on the first call only — every recovery rung runs unconstrained

`llm/llm_quality.py:324` passes `json_schema=json_schema`. The three later
provider calls do not: the truncation re-ask (`:406-414`), the temperature-0
repair (`:496-505`) and each fallback candidate (`:560-570`).

Two of those rebuild the identical object (`repair_json` and the fallback both
say "Rebuild the complete response" / "Produce a complete replacement
response"), so the step's own schema applies to them unchanged. The rung that
loses it hardest is the truncation re-ask, whose whole problem is a model
spending output budget it does not have — and the measured effect of the
grammar is that "a constrained model cannot pad: `character` went 53.4s/2029
tokens to 15.3s/587" (`llm/providers.py:1623-1660`). The calls made because
validation failed are the ones running without the constraint that makes
validation pass.

### 16. Eight public names in `llm/prompts.py` have no reader, under a comment saying they have four

`llm/prompts.py:37-38`: "Compatibility exports used by the prompt editor,
project checks, benches, and tests." Grepped `-w` over the whole tree
(`.claude/worktrees` excluded — it holds full repo copies and poisons every
grep):

| name | line | readers outside `llm/prompts.py` |
| --- | --- | --- |
| `CATEGORY_NOTE` | 43 | none |
| `BOOK_TYPE_NOTE` | 44 | none |
| `TRANSIT_NOTE` | 45 | none |
| `NSFW_OVERLAY` | 47 | none |
| `NSFW_PROMPT_IDS` | 48 | none (`get_prompt_body:400` reads the card key directly) |
| `INTERPRET_DELEGATION_NOTE` | 49 | none (`agents/director.py` calls the *function* `interpret_delegation_note`) |
| `DIRECTOR_RESOLVE_SHEET_IDS` | 374 | only its own function |
| `director_resolve_sheets()` | 381 | none |

`EXTRA_PARTS_NOTE` (46) is the one that is read — by `story/importers.py` — and
that is its own small defect: the constant is the ENGLISH fragment resolved at
import (`_ENGLISH = _prompt_card("en")`, `:35`), while the localized accessor
`extra_parts_note(language)` (`:147`) exists and has no caller, so a
non-English import path gets the English note.

### 17. `nsfw_prompt_ids` still lists `perception`, a prompt no pack has

Both packs' `nsfw_prompt_ids` carry `perception`
(`language_packs/en/cards/system_prompts.json`,
`language_packs/ja/…`, 16 ids each). No pack's `prompts` map has that id — the
perception prompt was deleted when perception became deterministic, and
`tools/project_check.py:654-693` cites that deletion by name as the reason
`check_no_dead_prompts` exists. The reverse check — an nsfw id that names no
prompt — does not exist, so the entry sits in both packs and in every future
translation. It can never match; `get_prompt_body:400` looks the requested pid
up in the set.

### 18. Four authored fragments are duplicated verbatim into 17 prompt bodies, kept in step by hand

`category_note` (897 chars), `book_type_note` (1,322), `transit_note` (1,578)
and `extra_parts_note` (1,292) are card entries AND are pasted whole into the
bodies of the prompts that use them:

| fragment | copies inside `prompts` |
| --- | --- |
| `category_note` | `mapping_stage`, `mapping_commit`, `lore_reinterpret`, `generator_lorebook`, `generator_lorebook_entries` |
| `book_type_note` | `mapping_stage`, `mapping_commit`, `generator_lorebook` |
| `transit_note` | `director_establish`, `director_resolve_lean`, `mapping_stage` |
| `extra_parts_note` | `promote_character`, `fill_appearance`, `generator_character`, `generator_persona`, `import_character_reinterpret`, `import_persona_reinterpret` |

All 17 copies are currently byte-identical to their fragment (checked), so this
is drift-in-waiting rather than drift. Nothing compares them; three of the four
canonical entries are reachable only through the dead constants of finding 16,
so the "source" copy is the one no code can reach. Same class as finding 1, one
layer down: 5,089 characters of authored text with 17 hand-maintained copies
and no guard.

### 19. 27 schema models, 234 lines, referenced by nothing anywhere

Verified by AST + `grep -rlw` over every `*.py` (excluding `.claude/`): zero
references, including inside `llm/schemas.py` itself.

`TemporalMode` (231), `GenreProfile` (888), `FictionModel` (907),
`ScenePressure` (930), `SimulationClock` (939), `TimeDiff` (945),
`TemporalProperties` (953), `ResolutionCheck` (1025), `AuthorityClaim` (1075),
`ClaimDisposition` (1084), `GenerationRequest` (1090), `WorldEntity` (1285),
`AggregateEntity` (1299), `ComponentState` (1318), `SpatialZone` (1372),
`StrategicPlacement` (1396), `PersistentCondition` (1407), `ScheduledEvent`
(1419), `InventoryOp` (1485), `ObjectStatePatch` (1493), `ReactionDeclaration`
(1501), `EventAtom` (1507), `SensorChannel` (1548), `ActorDef` (1559),
`LorebookDef` (3206), `LoreEntryScope` (3217), `LoreEntryRelation` (3224).

Several are the typed shape of a channel that ships UNTYPED: `StateDiff`
carries `inventory_ops: list[dict]` beside `InventoryOp`, `conditions:
dict[str, list[dict]]` beside `PersistentCondition`, `claim_dispositions:
list[dict]` beside `ClaimDisposition`. So the file contains a validated shape
for those channels and does not use it — which is how finding 6's
`tick_interval_seconds` could look declared and be unread. Distinct from
`WorldDef` / `LocationDef` / `TransitEdge` (1340/1356/1381), which are dead in
the same way but carry an explicit "DEPRECATED — MARKED FOR REMOVAL" block
(`:1330-1338`) and are honest about it.

### 20. Two prompts name a story instead of the distinction

* `mapping_commit`: "an entity with interior_rooms (a ship, **a TARDIS**, a
  vehicle with rooms) gets its own book_type 'vehicle' book". The clause
  already states the rule structurally (`interior_rooms`) and gives two generic
  instances; the third is one franchise's object, shipped to every story.
* `character`: "Each observation of the present beat carries a unique id of the
  form `current:<perceiver>:<n>` (for example `current:Hinami:0`)". The format
  is the teaching; the instance is a live character from the owner's own chats,
  read by every character in every story.

`CLAUDE.md` is explicit that prompt text is where this matters most ("a prompt
is read by every story, so an example drawn from one of them narrows what the
model thinks the field is for"). Both are one-word fixes; neither is urgent.

### 21. `OutputGuard` is shared across the retries inside one `_chat_complete_once`

`llm/providers.py:2083` wraps the sink once (`sink = _guarded_sink(sink)`), and
every retry inside that call re-uses it: the staged 400 retries (`:2183`,
`:2202`), and — the one that matters — the placeholder-skeleton retry
(`:2219-2229`), which re-streams a whole second response into the same guard.

`OutputGuard.text` therefore accumulates ACROSS attempts, so both the 4 KB tail
window and the 16 KB loop window (`_LOOP_WINDOW`, `:288`) can span the boundary
between two different responses. `_repeating_period` (`:296`) finds a cycle by
`rfind` over that window, so two attempts whose tails resemble each other can
in principle be reported as a repeating phrase the model never emitted. Narrow,
not observed — but the guard's own documentation is careful that "a loop is a
thing that has STARTED and is still going", and a concatenation of two attempts
is not that.

### 22. `_name_what_was_discarded`'s worked case can no longer occur

`llm/schemas.py:5051-5090` exists to correct a false complaint: a model that
answered `["Picks up the PADD.", "Says, \"Nobody leaves this room.\""]` was
told "sequence is empty despite nonempty player input", and the repair was
handed that false sentence.

`preprocess_llm_output` now converts a string entry into an object first
(`_sequence_event_from_prose`, `llm/schemas.py:3316-3345`, applied at `:4285`),
so a list of sentences produces a non-empty sequence and the semantic error
never fires. The function still counts those strings as "dropped" (it reads the
RAW payload, `:5083`), so the branch survives only for entries that are neither
dict nor string — numbers, nested lists — and the message it prints describes a
repair that another function now performs. Dead in the case it documents.

### 23. `_EMBED_STATS` counts four things nothing reports

`llm/providers.py:3007` — "Visible arithmetic for 'did this help': callers vs
the requests they cost." `callers`/`texts_in` are incremented in
`_coalesced_embed` (`:3070-3072`), `groups`/`texts_sent` in
`_serve_embed_group` (`:3053-3054`). Grepped `-w`: the only reader outside this
module is `tests/test_embedding_write_resilience.py`. No log line, no route, no
`/api` surface, nothing in the pipeline drawer. The coalescer's own measure of
whether coalescing works is write-only.

### 24. The body specialist's conditions channel is described one way and exampled another

The `conditions` chunk's shape line ends
`conditions:{condition_id:{condition_id,subject_id,kind,severity,…}}` — one
object per key. The schema declares `dict[str, list[dict]]`
(`llm/schemas.py:1985`, `:2347`) and `OUTPUT_EXAMPLES["director_body"]`
(`llm/schemas.py:4605-4613`) shows a LIST of one. `resolve_repair`'s prompt
agrees with the chunk (single object), not with the example.

Both spellings survive — `_coerce_list_valued_map` (`:93-150`) and
`_coerce_conditions` (`:3474-3524`) wrap the singular — so this costs nothing
today. It is listed because it is the same file teaching two shapes for one
channel, and because the coercion that saves it is the same one whose comment
records what a rejection of the shape cost live ("cost a full temperature-0
repair round-trip (4.9s) for a shape that means the same thing").

### The known triple, checked exhaustively

`SCHEMA_MAP` (`llm/schemas.py:3289-3311`, 21 keys) vs `STEP_HANDLERS`
(`agents/runtime.py:182-197`, 14) vs `PipelineContext`'s declared step fields
(`core/pipeline_context.py:146-166`, 12):

* **Handlers with no schema (8):** `commit`, `interaction_loop`,
  `reaction_loop`, `mapping_quick`, `narrator_extra`, `perception_act`,
  `perception_establish`, `perception_outcome`. All correct — the three
  perception steps and `mapping_quick` (`agents/mapping.py:199`) make no model
  call, the loops and commit are orchestration, and `narrator_extra` validates
  under `narrator`.
* **Schema keys that are not plan steps (15):** the six specialists, the three
  repair/reconcile shapes, `character`, `mapping_commit`, `greeting_interpret`,
  `scene_life`, `blurb_mint`, `backdrop_prompt`. All correct — sub-calls and
  out-of-band calls, each with a real caller.
* **Handlers with no `PipelineContext` field (2):** `background_react` and
  `commit`. Both work, through the `_extra` catch-all
  (`core/pipeline_context.py:225-226`, `:211-225`), so this is an asymmetry
  rather than a defect: 12 of 14 stages are typed fields and 2 are dictionary
  keys, and nothing says which is which.
* **Prompt ids vs `SCHEMA_MAP`:** the only mismatch is
  `director_resolve` ↔ `director_resolve_lean`, covered deliberately by
  `PROMPT_MODEL_ALIASES` (`tools/project_check.py:175-177`).
* **`ROLES` vs `SPECIALISTS_BY_NAME`:** exact agreement on the six
  `director_*` lanes.

### Unverified suspicions

* **`_flatten_to_text`'s key order may pick the wrong prose.** `_PROSE_KEYS`
  (`llm/schemas.py:304-306`) ends `…, "reason", "name", "id"`, so a structured
  value landing on a `str` field whose only string leaves are `name` and `id`
  reduces to an identifier presented as prose. `_coerce_candidate_response`
  documents exactly this failure for its own field ("the generic flatten
  scavenges every scalar it can find and returns the `type` discriminator as if
  it were prose"). I did not find a live instance in the corpus, and did not
  read the database to look for one.
* **`json_schema` may be rejected more often than the memo suggests.**
  `_step_json_schema` returns Pydantic's full schema including `$defs`/`$ref`
  (`llm/llm_quality.py:250-273`). Several hosts accept only a flattened schema
  with `additionalProperties: false`. `_note_json_schema_rejected` handles the
  400 and memoises, so the cost is one failed call per process — but whether
  the engine's biggest models ever get the grammar is a measurement (the
  `kind`/`served`/`cached` ledger would answer it), not something reading can
  settle.
* **`FREE_STRING_LIST_LIMIT = 64` against `dialogue_order`.** The constant's
  note says the longest free-string list ever produced was 13. A scene-manager
  beat in a crowded room with `max_managed` at its ceiling plus a crowd could
  plausibly grow `dialogue_order`; I did not check the live database (read-only
  or otherwise) to bound it.

---

## Part 2 — what the code actually does, checked against the documents

Method: each module's behaviour written from the code, then compared against
`Design.md`, `AGENTS.md`, `docs/guides/PIPELINE.md`, `CLAUDE.md` and the design
notes those cite. Verdicts: RIGHT / STALE / LOST.

### `llm/prompts.py` — 408 lines, and none of the prose

The module is prompt *selection*: it resolves the story language, fetches the
pack's `system_prompts` card, applies host presets, appends the NSFW overlay
where the card says to, and applies the language/schema policy suffix. Four
assembly surfaces: `get_prompt` (a whole sheet by id), `specialist_prompt`
(core + one chunk per granted channel), `prose_author_prompt` (the prose
author's core + one segment per granted duty), and `character_prompt`
(subtractive — it removes paragraphs whose payload paths are unstamped,
`:322-371`).

Preset handling is careful in a way worth recording: a preset is a
language-tagged document (`:85-114`), an untagged legacy map reads as English,
and `_preset_override` refuses to apply an English preset to a Japanese story
(`:155-176`) because a sheet is human-language text and swapping it swaps the
language the model is addressed in. `preset_import_document` fails closed on
every axis (`:208-252`) with the right reason stated: half a preset silently
dropped "reappears as a model behaving oddly many beats later".

**Docs: RIGHT**, with one correction and finding 1's gap.

* `AGENTS.md` § Director orchestration names `SPECIALIST_PROMPT_SPECS`,
  `specialist_prompt`, `PROSE_AUTHOR_SHEET`, `prose_author_prompt` and "the
  `_RESOLVE_*`/`RESOLVE_*` segments — each belongs to exactly one specialist or
  to the prose author's sheet; there is no monolithic sheet and no registry
  entry for one". Verified: there is no `DEFAULT_PROMPTS["director_resolve"]`,
  only `director_resolve_lean`, and `check_prose_author_chunks` holds it to the
  assembly. What the row does not say is that `DEFAULT_PROMPTS` ALSO carries
  six whole specialist sheets that nothing assembles from (finding 1).
* `docs/guides/PIPELINE.md` § `director_resolve` says the specialists run with
  "sheets assembled per beat from its granted channels' chunks
  (`prompts.specialist_prompt`)" and that "a beat still dispatches a mean 1.75
  of 6 sheets of **1-4k** against the single sheet's ~21k". The mean and the
  ~21k are not re-derivable here, but the per-sheet range is: the six cores are
  1,831–1,959 tokens each and a FULL-scope sheet runs 2,071 (social) to 6,114
  (body) tokens — so the floor is right and the ceiling understates by half.
  Typical scope (core + one or two chunks) does land inside 1-4k. **Minor
  STALE**: the range describes the common case, not the bound.

### `llm/schemas.py` — 5,259 lines, three jobs

1. **Declared shapes** for every stage output (`SCHEMA_MAP`, 21 models) plus
   the world-state vocabulary they nest.
2. **Tolerance**: `LenientModel` and about twenty coercions that read a
   near-miss shape rather than discarding a beat. Each one carries the live
   failure that earned it, which makes this the best-documented file in the
   engine.
3. **Deterministic repair and audit**: `preprocess_llm_output` (envelope
   unwrap, paragraph markers, prose markup canonicalisation, dialogue-log
   normalisation, the concealed-from-addressee fix), `semantic_output_errors`,
   and the pruning validator.

**Docs: RIGHT.** Every maintained claim checked out:

* `AGENTS.md`: "`schemas.LenientModel` … accepts a structured value where a
  field is declared `str` … It fires ONLY on a `str`-typed field receiving a
  dict/list, so it cannot mask a real type error." Verified at
  `llm/schemas.py:660-810` — the `is_str` branch is guarded exactly that way,
  and the other branches (bool-that-is-not-boolish, empty-container-for-object,
  `{}`-for-list, per-member coercion, map-where-a-list-was-declared) are each
  narrower than the type they repair.
* `AGENTS.md` § stations: "Any new field on a scene-blob diff must be DECLARED
  on its Pydantic model … Keep `stations` a plain `dict[str, dict]`, never a
  typed sub-model". Verified — `StateDiff.stations` is a plain dict with
  `_coerce_station_table` (`:50-91`), and the docstring gives the partial-merge
  and `exclude_none` reasons.
* `AGENTS.md` § entity projection names `_fill_entity_names` and
  `is_derived_entity_name` in `llm/schemas.py`; both are there (`:3716`,
  `:3694`) and behave as described (an opaque hex key derives NO name rather
  than a garbage one).
* `Design.md`'s firewall claims that touch this file — no `perception` entry in
  `SCHEMA_MAP`, the two `step_key == "perception"` branches gone — are true;
  the removal note stands at `:3234-3242`. (The pack's `nsfw_prompt_ids` did
  not get the memo — finding 17.)
* `AGENTS.md` § SPECIALIST_CHANNELS: "One authority for the preprocess unwrap,
  the channel-level prune, and (via import) the project-structure check". True,
  and `check_specialist_prompt_chunks` does hold the three registries level —
  it just cannot see finding 8's dict/list misclassification, which lives in a
  fourth constant nothing cross-checks.

The one place the file's own comments outrun it is finding 10
(`Observation` vs the composer) and finding 22 (`_name_what_was_discarded`).

### `llm/providers.py` — 3,158 lines, the transport

Provider rows → resolved (provider, model, config) per role; sampler merge;
per-call timeouts with a contextvar override; two request dialects (native
Anthropic and OpenAI-compatible) each with streaming and non-streaming forms; a
staged 400-recovery ladder that is memoised per (provider, model); degenerate-
output detection on the stream; retry with equal jitter; the embeddings lane
with adaptive pacing, request coalescing and a crc32 fallback that now says so
out loud.

**Docs: RIGHT**, with one stale pointer:

* `AGENTS.md` row "Whether a call is cached…" names
  `prompt_cache_enabled_for`, `_cache_denied`, `_cache_passthrough_allowed`,
  `cache_affinity_allowed`/`_apply_cache_affinity` and insists "both must ask
  the same predicate". Verified: `_anthropic_system` (`:524`) consults
  `_cache_denied(prov)` and `_openai_system_message` (`:707`) consults
  `_cache_passthrough_allowed(prov)`, and `prompt_cache_enabled_for` (`:606`)
  is the single question the UI asks. The allowlist posture is intact.
* `AGENTS.md` row "Provider behavior" lists `llm/prompt_cache.py` as the
  file to inspect. **STALE, and already registered** —
  `docs/UNBUILT.md` § 8 says "`llm/prompt_cache.py` is dead — no importer
  anywhere — and its `estimate_cacheable_tokens` heuristic is wrong by 5x to
  262x on every stage. `AGENTS.md` still names it as the watch-file for
  cacheability." Confirmed here: grepped `-w`, zero importers.
  `Design.md:774` lists it as part of the "Provider layer" too. Two further
  details for whoever removes it: `add_cache_breakpoint` returns an
  `extra_body` shape no caller in this engine sends, and `CACHEABLE_SEGMENTS`
  (`llm/prompt_cache.py:61-70`) still lists `"You are the PERCEPTION layer"`,
  a prompt that no longer exists.
* `AGENTS.md` on `ROLE_FALLBACKS`: "deliberately EMPTY — an unconfigured
  specialist follows `default` like every other blank row, and MUST NOT be
  given `director` as a hidden parent again". Verified at `:1420`
  (`ROLE_FALLBACKS = {}`) with the removal argument preserved in full above it,
  and `reasoning_effort_for` (`:894-911`) documents the coupling any future
  entry would break.
* `AGENTS.md` on the per-call ledger: "`_engine_notes.llm_calls`:
  `{step_key, role, requested, served, in, out, cached, duration, kind}` …
  must stay counts and identifiers, never content". Verified — `record_llm_call`
  (`:2038`) forwards exactly those keys (plus `texts` on the embedding batch),
  and it swallows every sink failure so a diagnostic cannot fail the call it
  describes. The one hole is finding 13: `served` is never populated on the
  Anthropic streams.
* `Design.md`'s cache-affinity row (`:235`) describes `_apply_cache_affinity`
  adding `user: "sonder:<role>"` on "both OpenAI-compatible body builders (sync
  and async; the SSE paths consume those bodies)", fail-closed behind
  `cache_affinity_allow`, stripped by the 400 retry. All four clauses verified
  (`:678-684`, `:1533-1544`, `:2157`, `:2497`).

`chat_complete_async` is dead (already in `docs/UNBUILT.md` § 8: "Defined,
imported by `web/app.py`, and called from nowhere but its own retry loop"). Two
things noticed while reading it that make deleting it easier to justify than
maintaining it: it never applies `_scale_for_language` (`:939`), so a Japanese
story would truncate on it, and its non-streaming 400 ladder is missing the
json_schema→json_object stage the sync path has (`:2537-2546` vs `:2240-2262`).

### `llm/llm_quality.py` — 655 lines, the ladder

`complete_validated_json` is the engine's strict path: one call with the step's
grammar; strict parse (fence strip, then a string-aware brace scan for
prose-wrapped JSON); schema + semantic validation; then, in order, a
length-escalated re-ask if the provider or the JSON's own shape says the
response was cut off, a targeted field patch on the cheap `repair` model, one
temperature-0 full repair, then each fallback candidate. It raises rather than
returning junk, and the exception carries what the model actually sent plus the
tail of its reasoning trace.

**Docs: RIGHT.** `agents/common.py:1473-1484` describes this function
accurately, including the important sentence that the follow-up
`validate_llm_output` calls some stages make are "warning-only
re-normalization of already-validated output, NOT the guard". `AGENTS.md` and
`docs/guides/PIPELINE.md` do not describe the ladder in detail, which is
consistent with `agents/common.py` owning that description.

Three properties are load-bearing and undocumented outside the code:
truncation recovery is straight-line and cannot re-enter (so at most one
oversized retry, whatever the model does); the targeted patch splices ONLY at
paths that failed and returns `None` on any doubt; and `report.warnings` is
dropped at every exit (finding 7).

### `llm/prompt_cache.py` — dead, and stale where it is dead

78 lines, no importer. Covered above and in `docs/UNBUILT.md` § 8.

### `language_packs/*/prompt_policy.json`

`{common, roles}`. `common` is the LANGUAGE AND SCHEMA CONTRACT appended to
every sheet, enforced twice — once at assembly (`apply_prompt_policy`) and once
at the transport boundary (`providers.chat_complete:1815` →
`apply_common_prompt_policy`), idempotently, because
`language_runtime.apply_prompt_policy:425-447` proves the suffix is already
present rather than doubling it. `check_language_pack_surfaces` asserts every
`DEFAULT_PROMPTS` body carries the contract. `roles` is a per-role suffix map
that both shipped packs leave `{}`; it is read (`prompt_suffix:133-137`) and
validated at load, so it is an extension point rather than a dead value — but
nothing populates it, and the comment at `apply_prompt_policy:436-440` records
that English's empty `roles` map is what hid a double-append bug that Japanese
exposed.

### `tools/project_check.py` — what it does and does not hold level

Four checks touch this slice, and they are good ones:
`check_prompt_schema_ops` (every `_ops` name a prompt asks for exists on that
stage's model, walking nested models both by `annotation` and `outer_type_`),
`check_specialist_prompt_chunks` (the three specialist registries agree, every
owned channel has exactly one chunk, no chunk is unordered, a core never names
its own channel, and the assembled sheet passes the `_ops` check),
`check_prose_author_chunks` (chunk/gate/audit sets agree, the never-gated
contract blocks are in the core, and `DEFAULT_PROMPTS['director_resolve_lean']`
IS the full assembly), `check_no_dead_prompts` (every pack prompt is fetched by
something).

What no check covers, all of it evidenced above:

* `DEFAULT_PROMPTS['director_<name>']` vs the assembled specialist sheet
  (finding 1). `check_no_dead_prompts` even counts those six ids as "used"
  because they collide with `SPECIALISTS_BY_NAME.values()` — the names match,
  the sheets need not.
* Whether an `OUTPUT_EXAMPLES` entry validates against its own
  `SCHEMA_MAP` model, or passes its own `semantic_output_errors` (findings 2
  and 3). Nineteen lines of test would have caught both.
* Whether an id in `nsfw_prompt_ids` names a prompt that exists (finding 17).
* Whether `_SPECIALIST_DICT_CHANNELS`/`_SPECIALIST_LIST_CHANNELS` match the
  declared annotations (finding 8).
* Whether the duplicated fragments of finding 18 still match their copies.

### Cross-document verdicts

| document | verdict |
| --- | --- |
| `AGENTS.md` § "Whether a call is cached…" | **RIGHT** — every clause verified against both request builders |
| `AGENTS.md` § "Provider behavior" (names `llm/prompt_cache.py`) | **STALE** — module is dead; already in `docs/UNBUILT.md` § 8 |
| `AGENTS.md` § Director orchestration (prompts/schemas half) | **RIGHT** — but silent about the duplicate specialist bodies (finding 1) |
| `AGENTS.md` § `LenientModel` | **RIGHT** — the "fires ONLY on a `str`-typed field" claim holds in code |
| `AGENTS.md` § per-call ledger | **RIGHT**, except `served` on the Anthropic streams (finding 13) |
| `Design.md:235` (cache affinity) | **RIGHT** — all four clauses verified |
| `Design.md:774` (provider layer) | **STALE** — lists the dead `llm/prompt_cache.py` |
| `docs/guides/PIPELINE.md` § `director_resolve` (specialist sheets) | **RIGHT**; the "1-4k" sheet range describes typical scope, not the bound (2.0k–6.1k full) |
| `docs/guides/PIPELINE.md` § `commit` / conditions | untouched here, but see finding 6: a condition can expire and cannot tick |
| `docs/design/GREETING_IMPORT_DESIGN.md` | **STALE as a description of what shipped** — no `bake_establishment`, no `private_history` routing, no eager ingest-time extraction; the schema still carries the fields that half needed (finding 9) |
| `CLAUDE.md` / `Design.md` "no `perception` role, prompt or schema" | **RIGHT** in `providers.ROLES`, `SCHEMA_MAP` and the pack's `prompts`; `nsfw_prompt_ids` still lists it (finding 17) |

Nothing in this slice was found built-and-quietly-lost in the way the spatial
audit found `_SCENT_BARRIERS`. What this package loses instead is **evidence**:
the pruned-channel warning (7), the served-model report (13), the coalescer's
own arithmetic (23) and every silent coercion (11) are all mechanisms that
work and then fail to tell anyone they ran.
