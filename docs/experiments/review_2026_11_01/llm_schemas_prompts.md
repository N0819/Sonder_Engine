# Audit: `llm/schemas.py`, `llm/json_mend.py`, `llm/decisions.py`, `language_runtime/` (prompt-card loader)

Auditor run 2026-11-01, tree at `84f3de23` (clean). Read-only. Every snippet ran on
`.venv/bin/python` (Pydantic 2.11) with `PYTHONPATH` = repo root; the owner's
`engine.db` was opened only as `file:engine.db?immutable=1` (no lock, no shm, no
write). Snippet sources are kept in
`<review scratch>/sn/`
(`examples.py`, `silent.py`, `enums.py`, `cardfields.py`, `shapes.py`, `jashape.py`,
`mendfuzz.py`, `menddiff.py`, `mendpath.py`, `reach.py`, `perf.py`).
One focused test run: `tests/test_schemas.py` -> 15 passed.

## Scope read

Read in full:
- `llm/schemas.py` 1-7005 (all of it; the longest comment blocks in `RoomDef`,
  `StateDiff`, `DirectorResolve` and the prose-markup section were read at speed,
  the code in them line by line).
- `llm/json_mend.py` 1-302.
- `llm/decisions.py` 1-325.
- `language_runtime/card_source.py` 1-389 and `language_runtime/__init__.py` 1-787
  (the loader: `_read_card`, `_resolve_prompt_fragments`, `_load_pack`,
  `installed_language_packs`, `_linguistic_cached`).

Read in part, for tracing:
- `llm/llm_quality.py` 29-1045, 1378-1445, 1738-1870 (parse, mend, accept, repair payloads).
- `agents/director_repair.py` 180-313, 405-430, 955-975, 1040-1185, 1225-1260, 1365-1410.
- `agents/director_prose.py` 700-790, 4230-4265; `agents/director_evidence.py` 2940-3070;
  `agents/director.py` 440-460, 1120-1175, 2100-2135, 2836-2900, 3014-3040,
  3162-3200, 3440-3475, 3860-3905, 6255-6300, 7780-7805; `agents/common.py`
  420-500, 4740-4800; `agents/character_bare.py` 836-990; `world/spatial_senses.py`
  1372-1530; `world/spatial_sound_field.py` 105-115, 320-345, 1785-1835, 4120-4175;
  `agents/composer.py` 3095-3130.
- `tests/test_schemas.py` 217-306 (the reachability test); `tools/project_check.py`
  20-75, 330-640.
- Cards read whole: `encoder/core.txt`, `encoder/{cast_changes,inventory_ops,obligations,
  claim_dispositions,comms_ops,crowd_ops,sensory_events}.txt`; the en and ja
  `prompts/director_establish.txt` printed shapes; `ja/prompt_policy.json`.
  Every other card under `language_packs/en/cards/system_prompts/**` was covered only by
  the scripted extractions (`enums.py`, `cardfields.py`, `shapes.py`, `jashape.py`),
  not read by eye.

Not read: `language_runtime/referring.py` (609 lines; not a card loader), the
other ~290 part files beyond the scripted scans.

## Findings

Question map (the assignment's eight questions -> where answered):
(1) silent tolerance: F1, F2, F11 and the table at the end of this section;
(2) OUTPUT_EXAMPLES: all 16 validate (`examples.py`), one carries a dropped key -> F6;
(3) registries: F9, F10, and "Structure notes"; (4) cards asking for fields the
schema lacks: F4, F5, F6, F8; (5) legacy shims: F11; (6) json_mend: F3;
(7) decisions keyed answers: merged by key everywhere (confirmed), but see F7;
(8) efficiency: "Efficiency".

### F1 — `visibility` has no vocabulary on the encoder's and the ledger's events, and a concealment written in any other word is delivered as overt

- `llm/schemas.py:3277` `UnifiedEvent.visibility: str = "overt"` and `:1508`
  `CausalLedgerEntry.visibility: str = "overt"` — free strings, no validator.
  `agents/director_evidence.py:2965` `"visibility": str(entry.get("visibility") or "overt")`
  carries any spelling onto the projected speech/event element.
- Every reader is binary on the exact token: `agents/common.py:4852`
  `"concealed" if e.get("visibility") == "concealed" else "overt"` (case-sensitive),
  `agents/perception.py:850`, `agents/composer.py:671`, `agents/loops.py:443/528`,
  while `agents/background.py:684/1704/2114` casefold first. `conceal_from` is
  ignored unless the token is exactly `concealed` (`perception.py:850`).
- The only fold of a near-miss lives in one path: `llm/schemas.py:5858`
  `if vis in ("concealed", "hidden", "secret"): line["visibility"] = "concealed"`
  — `dialogue_log` only. A `sequence` event (interpret), an encoder event and a
  ledger row get no fold.
- The encoder card never names the vocabulary: `encoder/core.txt:21` "volume
  (ear|whisper|...), visibility, conceal_from: delivery facts, when they matter."
  (ja `core.txt` the same). No card under `encoder/` or `prose_contract/` contains
  `overt|concealed`.

Snippet (`silent.py`): the encoder answer `{"visibility": "private", ...}` validates
and stays `"private"`; an interpret `sequence` speech event with `"hidden"` stays
`"hidden"` (→ `overt` in `norm_sequence`); the same word on a resolve
`dialogue_log` line becomes `"concealed"`. No warning on any path.

Measured, raw captured answers (`llm_capture` ⋈ `llm_blobs`, 6,170 calls,
2026-09-01..10-28): concealment-intent spellings `private` ×8, `hidden` ×3,
`intimate` ×5, `low` ×8, `close` ×3, `partial` ×2, `subtle` ×1 — four of them
beside a NON-EMPTY `conceal_from` (e.g. variant 50506, chat 123 turn 9: "The Doctor
flicks his eyes past Hinami..." `visibility:"partial"`, `conceal_from:["Hinami"]`;
50583: `low` + `conceal_from:["Hinami"]`) — every one delivered overt. All are
2026-09-14..25, before the prose contract; post-cutover encoder events (440
variants, 1,605 events) carried `overt` 1570, `None` 30, `plain` 3, `concealed` 2.
So the class is LATENT today, and held only by the encoder choosing the exact
word with no card telling it which word.

Failure scenario: an encoder (or the next model) writes `visibility:"hidden",
conceal_from:["Bob"]` for a palmed key → the projected element is overt → Bob's
view receives the act. The firewall depends on the model spelling one token.

Severity LEAK (latent). Confidence: path CONFIRMED by trace + snippet; live
frequency today PLAUSIBLE-low. Fix (class, not instance): one
`normalize_visibility` beside `normalize_speech_volume`, applied as a validator on
`UnifiedEvent`/`CausalLedgerEntry` and in `preprocess_llm_output` for sequence
dicts (the same closed fold `dialogue_log` already uses, plus `_note_drop` for an
unknown word); treat a non-empty `conceal_from` as concealed regardless of the
token; state `visibility (overt|concealed)` in `encoder/core.txt` en+ja. Test:
encoder event `{visibility:"hidden", conceal_from:["Bob"]}` → the projected row
is `concealed` and Bob's composed view lacks it. Related registered item: X3
(UNBUILT_PERCEPTION §3.2) covers only the background gate.

### F2 — `normalize_speech_volume` folds the closed set's own inflections to `normal`, silently

- `llm/schemas.py:448-471`: unknown → `return "normal"` (`:469`), no `_note_drop`;
  `world/spatial_senses.py:1379-1380` `_volume_word` does the same at hearing time.
- Snippet: `whispered`, `whispering`, `shouted`, `shouting`, `yelled`, `bellowed`,
  `low`, and `"pitched low, only for Hinami"` all → `normal`; `quietly`/`soft` →
  `mutter`.
- Raw captures held `muttered` ×1, `low` ×8, `"pitched low, only for Hinami"` ×2,
  `"pitched: soft enough that only..."` ×1, `projected` ×3 (2026-09-08..24) —
  each graded as an ordinary voice: a line the speaker pitched or muttered heard
  by the whole room.
- The vocabulary is also stated three different ways: `encoder/core.txt:21`
  teaches the closed set and says "a soft, breathy, shaky, murmured or moaned
  line ... carries ... at normal", while `_VOLUME_ALIASES` (`:419-446`) folds
  `soft/softly/quiet/quietly` to `mutter` and `excited/enthusiastic` to `loud`
  (how it sounds, which the card says volume is not); and the
  `background_react`, `scene_life` and `director_establish` cards print `volume`
  with no vocabulary at all.

Severity LEAK/WRONG-SCENE (latent: post-cutover encoder volumes were all
canonical). CONFIRMED (snippet). Fix: fold a value that IS a member's inflection
or BEGINS with a member word (`muttered`→`mutter`, `pitched low…`→`pitched`) —
a closed table the engine owns, not a prose list — and `_note_drop` every fold of
a non-empty unknown to `normal`; print the closed set in the three cards. The
DEFAULT direction for a truly unknown word (normal vs quieter) is the owner's
(UNBUILT_CHARACTERS §6.19 already leaves "the quiet fallback" to the owner) —
propose, do not pick. Test: `normalize_speech_volume("whispered") == "whisper"`,
`("pitched low, only for X") == "pitched"`, unknown emits a step note.

### F3 — a JSON mend that validates is accepted even when it moved a member into the wrong container; the loss is never named

- `llm/llm_quality.py:1426-1436`: on an unparseable answer, `_mended` returns the
  FIRST candidate that validates and it is accepted ("mended locally ...; no model
  call"). `_mended` (`:899-927`) chooses by validity alone. The lenient schema
  ignores keys a model does not declare, so a member that lands one level wrong
  validates. Only the `goes_on` path (`_read_answer`, `:485-501`) names left-out
  keys, and only TOP-level ones.
- `llm/json_mend.py:202-208` (`early-close`) and `:183-196` (`sibling-close`) are
  the two edits that do it.

Measured (`mendfuzz.py`): every single bracket slip (delete / flip / double / swap
one closer) of all 16 `OUTPUT_EXAMPLES`: 427 mend back to the original, 94 do not
mend, **10 mend into a DIFFERENT object that validates** (1 deleted closer, 9
doubled closers). Worked cases (`menddiff.py`, `mendpath.py`):
- `scene_life`, the `}` closing `entries[0].speech` missing → `sibling-close` →
  `entries[0].action` ("sets the tankard down harder than needed") is now inside
  `speech`, ignored by `DialogueLogEntry`, so the accepted entry has
  `action: ""` — and the only warning says the JSON "was mended locally (closed an
  object left open before its next sibling)". The figure's act is gone silently.
- `director_establish`, one doubled `}` after `pier_head` → `early-close` →
  `rooms.quay_road` is hoisted to the root and dropped; the opening commits a room
  whose only exit points at a room that does not exist (this one IS named, by the
  goes_on path's top-level note).
- `resolve_repair`, doubled closer → `state_diff` keeps `positions` only; `rooms`,
  `entities` ... `time` hoisted and dropped.

Severity WRONG-SCENE (a beat's act or an opening's room lost; can reach commit).
CONFIRMED. Fix: before accepting, compare the candidate's parsed key paths with
the validated dump's (recursively — the comparison `examples.py` uses) and prefer a
candidate that drops nothing; on both paths name every dropped path. Test: the
`scene_life` missing-closer string through `_mended` keeps `entries[0].action` or
emits a warning naming it.

### F4 — the Japanese opening card prints `服装` where the schema key is `attire`; validation drops it and the protocol guard cannot see it

- `language_packs/ja/cards/system_prompts/prompts/director_establish.txt:74`
  (printed shape): `服装:{entity_name:{wearing:[], state:[]}}`,
  `entity_states:{entity_name:{姿勢、活動、held_items:[],...}}`,
  `sensory_events:[{種類、説明、source_room、距離、強度}]`,
  `fiction_frame:{..., スケール, ...}` — `attire`, `posture`, `activity`, `kind`,
  `description`, `distance`, `intensity`, `scale` translated. `jashape.py`: the en
  establish shape's `attire` key is the one top-level schema key absent from ja's.
- `ja/prompt_policy.json` says keys are never translated; the printed shape — the
  thing a model imitates — says otherwise.
- Snippet: an establish answer with `"服装": {...}` and `entity_states:{A:{"姿勢":
  ..., "活動": ...}}` validates with `attire: {}` and `posture: ""`, `activity:
  ""`, no warning (`DirectorEstablish` ignores undeclared keys).
- Why no guard fired: `tools/project_check.py:27-52` `CANONICAL_LANGUAGE_TOKEN`
  only sees backticked, quoted, underscore-bearing or dotted spans;
  `canonical_language_tokens("attire:{...}, entity_states:{entity_name:{posture,
  activity,...}}, sensory_events:[{kind,description,...}]")` returns
  `entity_name, entity_states, held_items, sensory_events, source_room,
  visible_conditions` — never `attire/posture/activity/kind/description`. The
  same split its own comment documents for enums.

Severity CORRUPTION (a Japanese story's opening attire — "the richest clothing
detail any story ever has", `AttireState` comment — and opening postures lost at
beat 0). PLAUSIBLE for live effect (the owner's db has no Japanese story:
`story_language` is `en` on all 91 chats); mechanism CONFIRMED. Fix: restore the
English keys in the ja shape; extend `CANONICAL_LANGUAGE_TOKEN` with "an
identifier directly before `:` or inside `{...}` of a printed shape". Test: the
protocol-span test fails on the current ja card.

### F5 — the prompt/schema drift checks skip every card of the live Director contract

- `tools/project_check.py:494/498` and `:553`: both checks pair a step with
  `prompts.DEFAULT_PROMPTS.get(<step key>)`; `PROMPT_MODEL_ALIASES` (`:411`) is
  `{}` ("none since the causal Director's lean sheet went").
- Snippet: SCHEMA_MAP keys with no same-id prompt, hence never checked:
  `director_prose`, `director_specialist` (encoder core + ~50 chunks),
  `director_repair`, `director_rooms`, `director_rooms_reconcile`, `character`,
  `prestory_journey`, `prestory_resident` (+ the five owner keys).
- F6 is a miss of exactly the class the check exists for, inside that gap.

Severity SILENT-NOOP (a guard that does nothing for the Director). CONFIRMED.
Fix: map step → card leaves (`director_specialist` → `encoder/*`,
`prose_contract/encoder_*`; `director_repair` → `prose_contract/encoder_repair*`;
...) and check backticked/printed names against each model tree. Test: a
structure test asserting the encoder-repair card's backticked fields resolve on
`EncoderRepairOutput`. Related registered item: UNBUILT_PLATFORM §1.61 (about
prompts with NO model; this is prompts WITH one).

### F6 — the repair card asks every recovered event for `sources`; `UnifiedEvent` has no such field

- `prose_contract/encoder_repair.txt` (job kind `event`): "Return in `events` only
  the missing events ... each with `sources`". `OUTPUT_EXAMPLES["director_repair"]`
  (`llm/schemas.py:6188`) shows `"sources": ["s3"]`.
- `examples.py`: validating that example drops `answers[].events[].sources` (the
  only example key any schema drops other than `None`s).
- `agents/director_repair.py:1403` then `event.setdefault("sources",
  job.get("sentences"))`: every recovered event is credited with ALL of its job's
  sentences; attribution elsewhere is recomputed by trigrams (`attribute`, `:277`),
  so the model's answer is paid for and discarded.

Severity SILENT-NOOP (the held_by class; low impact today). CONFIRMED. Fix: either
declare `sources: list[str]` on `UnifiedEvent` and read it, or remove the ask and the
example key. Test: the example's validated output keeps `sources`, or the card no
longer names it.

### F7 — a decision answer that omits a key reads as a confident "no"; only a raised error fails open

- `llm/decisions.py:281-315` never compares asked keys with answered keys;
  `:318-325` `probability(None) == 0.0`.
- `agents/director_prose.py:731-752`: an exception → "every channel granted
  (fail-open)" with a warning; a missing key → `probability(answers.get(channel))
  == 0.0` → channel not granted, no warning. Same reading in `director_repair`
  (`:759`, `:1250`), `skip_memories:959`, `story_planner:2812`.
- `_post` (`:155-160`) also assumes `body` is a dict (`body.get` on a JSON list
  raises `AttributeError`, not `DecisionError`); callers catch `Exception`, so
  this one is benign.
- Merge by key (question 7) holds: `decide` merges shard dicts with
  `dict.update` (`:304`, `:314`); `director_repair.merge_answers` (`:1058`) and the
  retry binding (`:1153-1163`) are by job id with suffix folding.

Severity SILENT-NOOP (a channel the prose needed not granted → change not
encoded). PLAUSIBLE (no measurement of missing keys exists). Fix: in `decide`,
`missing = set(questions) - set(answers)`; raise `DecisionError` (callers already
fail open) or return them as `None` and have callers fail open on `None`. Test:
`decisions.OVERRIDE` returning a partial dict → `select_channels` grants the
unanswered channel and warns. AGENTS.md's "FAILS OPEN" holds only for raised errors.

### F8 — two shapes for one channel: the opening still teaches the old `sensory_events` row

- en `prompts/director_establish.txt:74`: `sensory_events:[{kind,description,
  source_room,distance,intensity}]`; `encoder/sensory_events.txt`:
  `{kind,room,level|db,source,detail,drowns}`. Reader
  `world/spatial_sound_field.py:4125-4166` folds `source_room`→room,
  `description`→detail, keeps `intensity` as an old level spelling; `distance` is
  read by nothing; `level`, `db`, `source` and `drowns` are never taught to the
  opening, and `intensity` is taught with no vocabulary (any word outside
  `EVENT_DB`/`SPEECH_DB` grades as `audible`, `:1797-1811`).
- `agents/composer.py:3105` already documents the divergence and fixed the
  reader rather than the card.

Severity SILENT-NOOP (low: an opening's sound has no source and cannot drown a
voice; `distance` costs tokens for nothing). CONFIRMED by reading. Fix: print the
encoder's shape in both establish cards. Test: the establish card's
`sensory_events` keys ⊆ `normalize_sensory_event`'s closed set.

### F9 — the strict validator's remaining dead branches, and a register correction that is wrong

- Production never validates `director_interpret`, `director_resolve` or
  `character` strictly: the step keys reaching `complete_validated_json` are
  listed in the `_agent_json` grep (director_prose, director_specialist,
  director_repair, director_rooms[_reconcile], director_establish, character_bare,
  character_skip, background/scene_life/thread/blurb, greeting, prestory_*,
  backdrop, ambience, and the three dormant repairs). So:
  - `semantic_output_errors`' `character` branch (`llm/schemas.py:6597-6603`) is
    dead (the interpret/resolve branches are registered, see below);
  - the specialist prune (`:6953-6976`) needs `step_key in SPECIALIST_CHANNELS`,
    i.e. `director_body` ... `director_spatial`, which nothing validates strictly:
    dead;
  - `semantic_output_errors(notes=...)` (`:6501`) is never written in the body,
    so `semantic_notes` (`:6988-7004`, "Two channels, deliberately") is always
    `[]`.
  - `_name_what_was_discarded` (`:6653`) returns `error` unchanged for every key
    except `director_interpret` — the one key never validated strictly. UNBUILT_
    PIPELINE §1.1 item 11 says it "is NOT dead -- it names every step's semantic
    errors": it is CALLED on every step's errors and is the identity on all of
    them.

Severity DEAD (+ STALE-DOC for the register line). CONFIRMED. Fix: move the ten
schema tests to live keys (the register's own plan), then cut the branches, the
specialist prune, the `notes` parameter and `_name_what_was_discarded`.

### F10 — models that validate nothing in production, kept "reachable" by comments and English words

`reach.py` computes reachability from production AST names (no comments, no
docstrings, no tests) plus the step keys production validates plus field
annotations: **not reached** — `ActionElement` (+`IntendedEffect`,
`normalize_action_stage`, `_ACTION_STAGE_ALIASES`), `BookOp`, `LoreOp` (+
`_one_or_many_locations`), `ScenePatch`, `DestructionEffect`, `Engagement`,
`Observation`, `DirectorBody/Contact/Objects/SpatialSpecialist`, and the three
allowlisted fixtures `CausalRegime`, `FictionFrame`, `SpeechElement`.
`ResolvedEvent`, `CausalTransform`, `LedgerTransformResult` are reached only as
field types of `DirectorSocialSpecialist`, which `validated_specialist_patch_
channels` instantiates with `public_evidence`/`obligations` only — never
exercised.

Why the test passes (`tests/test_schemas.py:217-306`): it regex-matches class
names in the TEXT of every `.py` file, tests included. `Engagement` (0 production
uses, 0 tests) survives on the English word in `persist/commit_background.py:4819`
("Engagement only:") and `mind/affect.py:1178` ("Engagement revives ...");
`Observation` on "Observation Room"/"Observation ids" comments; `ActionElement`
and `DestructionEffect` on comments. The test proves "the name is written
somewhere", not "something validates against it" — the property its own
docstring claims. And schemas.py's own comments make two stale claims about them:
`:4566-4572` "ScenePatch, BookOp and LoreOp above survive as the shapes the
scene-patch fold and the lorebook writer read" (nothing validates against them),
`:2037` "`DestructionEffect` REVIVED ... carried in StateDiff.destruction"
(`StateDiff.destruction` is `Optional[dict]`).

Severity DEAD. CONFIRMED. Fix: reachability from AST `Name`/`Attribute`/import
nodes of non-test modules plus validated step keys; delete or explicitly
allowlist each model (the four specialist models are the owners table's field-name
source — say so, or derive the names from `SPECIALIST_CHANNELS`). Test: the
reachability test itself, rewritten.

### F11 — leniency for shapes no model writes any more (question 5), one of which drops silently

Since the bare contract, `CharacterOutput` is written only by
`character_bare.compile_bare` (`agents/character.py` calls the model as
`character_bare`, then compiles; `compile_bare` builds every list, `:836-990`).
So these run on every validation and can no longer meet the shape they exist for:
`_LEGACY_EVENT_IDS`/`_normalize_event_id` (`:3607-3634`; its comment cites
"UNBUILT §2.1", which no longer holds that entry), the bare-string paths of
`_coerce_evidence_refs`, `_coerce_candidate_list`/`_coerce_candidate_response`/
`CANDIDATE_SERVES_LIMIT`/`ResponseCandidate` ("`response_candidates` is no longer
asked for", `agents/character.py:1543`), `_coerce_considered_responses`, and
`_canonical_mind_hypothesis/_relationship_update/_goal_impact`. On the Director
side, `changes_asserted`, `ledger_notes`, `thoughts_omitted` (+ `AssertedChange`,
`OmittedThought`) were empty on 431 of 431 interpret/resolve variants since the
2026-09-27 cutover (`immutable` db scan); no en card names any of them.

Two of these drop SILENTLY where the base class would have wrapped: `:4445`
`_coerce_remember_lines` and `:4451` `_coerce_disputes` return `[]` for a single
object (`silent.py`: `remember_lines: {"quote": "Meet me at dawn", ...}` → `[]`,
no note), while `association_updates` given the same shape is wrapped by
`_lenient_coerce`. And `_canonical_relationship_update` (`:3706`) turns
`{axis: "affection", delta: 0.1}` into an all-zero update, no note. All dormant
today (compile_bare writes lists and canonical deltas).

Severity DEAD (latent SILENT-NOOP for memory if a model ever writes the full shape
again). CONFIRMED. Fix: route the single-object case through `_kept`/wrap like
`association_updates`; then decide per shim whether stored variants still need it
(rerun-from-stage of a pre-bare turn is the only producer) and cut the rest.

### F12 — comments that describe the deleted specialist architecture as live

Each is a claim the next reader will believe (STALE-DOC, CONFIRMED by grep):
- `llm/schemas.py:1569-1574` `DirectorInterpret.ledger_notes`: "`director_interpret`
  fans out to the same five specialists ... a hand reading only the player's
  declaration" — no hand exists; `:1575-1588` `changes_asserted` "says WHAT
  CHANGED, in categories the engine routes" — never written (F11).
- `:2999-3012` `DirectorResolve.ledger_notes`: "Specialists ... receive the
  finished prose and must each re-read it".
- `:2186-2207` the canonical `PoseEntry.from_event` note: records resolve "the entry
  in this hand's `changes_asserted` slice"; no slice is handed out and the encoder
  writes no `from_event` (registered as an effect, §1.1 item 1).
- `:6676-6687` `_diff_prunable_roots`: "`resolve_reconcile`/`resolve_repair` exist to
  detect changes asserted in prose" — gated off on every beat with rows
  (registered §1.1 item 3); `:6710-6716` `_prunable_specialist_fields`: "A
  specialist's whole output IS channels" (F9: dead).
- `:6905-6925` the strict prune's "a complete, correct 4,000-token resolve was
  discarded" — the resolve is no longer strictly validated.
- `:4362-4380` `CharacterOutput.project_ops`: "The character prompt asks for
  `project_ops` by name in three places" — that card is gone; `compile_bare`
  writes the ops.
- `:2009-2032` "`CausalRegime`, `FictionFrame` and `SpeechElement` are kept because
  tests use them as fixtures" beside "A declared-and-unreferenced model is worse than
  no model" — the file's own rule, waived in the next sentence.
Fix: rewrite each to the prose contract or delete with the dead code (F9-F11).

### Silent-tolerance table (question 1, systematic)

Every `LenientModel` (all SCHEMA_MAP models), no warning reaches `ctx.warnings`:
undeclared key → dropped by `_dump` (except `CharacterAppraisal`/
`CharacterActiveState`, `extra=allow`); explicit `null` on a non-Optional field →
default; dict/list where `str` declared → flattened; number → str, 1.5 → 1;
non-bool on a bool field → default (snippet: `container:"kess_vantar"` → False);
every `_clamp_float` field → default on non-numeric (`urgency:"high"` → 0.0) and
clamped silently. WITH a note (good): free-string list > 64, bare `list[dict]`
non-dicts, `state_diff.time` scalar, non-dict `conditions` rows, `dialogue_log`
lines without a quote, `considered_responses` not a list, candidate maps of the
wrong shape, concealment uncrossing.

| Model / field | Silent coercion | Note |
|---|---|---|
| DirectorInterpret `sequence[].visibility` | any token kept; ≠`concealed` → overt downstream | F1 |
| UnifiedEvent / CausalLedgerEntry `visibility`, `volume`, `commitment` | free strings, not normalized | F1, F2 |
| all `volume` fields | unknown → `normal` | F2 |
| DialogueLogEntry `vocal_affect`, `articulation`; BlurbMintEntry `nature` | outside closed set → `""` | by design, no note |
| `flow.dice/generation_requests/authority_claims` | non-dict entries dropped | `:5916-5927`, no note |
| `other_players[].sequence` | non-dict events dropped | `:5948-5963`, no note (primary uses `_kept`) |
| StateDiff/Establish `stations` | non-dict station dropped; `cell:[1.0,2.0]` dropped | `:117-118`, `:155-162`; `_parts_or_none` accepts integral floats, so the siblings disagree |
| StateDiff `entities` sibling keys | popped (hoisted or discarded) | `:5090-5097`, no note |
| RoomDef `transit_seconds/extent/parts` | prose → None | by design |
| UnifiedEvent `seconds/until_hour` | prose fails the WHOLE encoder answer → repair | asymmetric with RoomDef; 0 string seconds in 1,646 captured rows, so latent |
| CharacterOutput `remember_lines/memory_disputes` | single object → `[]` | F11 |
| RelationshipUpdate `axis/delta` | unknown axis → zero update | F11 |
| CharacterSkipOutput stretches | non-object stretch dropped; bad `day` → 0 | no note |
| `normalize_action_stage` | unknown passes → enum refuses | loud, but the model is dead (F10) |

Enum vocabularies cross-checked (card ↔ engine table; `enums.py`): `vocal_affect`,
`size`, `shape`, `light_source`/`LIGHT_LEVELS`, `sound_source`/`SOUND_LEVELS`,
`steadiness`, `exposure`, weather axes, `placement`, crowd `band`, awareness
`level`, `WAYS`, barrier words, `cast_changes.status` (fixed: `scene.cast_change_status`
returns None for unknown and its callers must say so) — all agree. Disagreements
found: `visibility` (F1), `volume` (F2), opening `sensory_events` (F8).

## Efficiency

- E1 — `_declared(field)` is recomputed for every field of every validation:
  `LenientModel._coerce_structured_into_str` (`llm/schemas.py:1203-1210`) calls
  `_fields(cls).get(...)` and `_declared(...)` (get_args/get_origin per call).
  Profiled on the largest post-cutover `director_resolve` variant (145 KB):
  `validate_llm_output` ≈ 10.4 ms/call, of which `_declared` ≈ 35%. Runs per field
  per validation — every stage output, every encoder answer and every mend
  candidate. Gain: ~3 ms per resolve validation; cache `_declared` by
  `(cls, field_name)` (fields are fixed after class creation). Cheap, small.
- E2 — `_dump` → `_plain` walks the whole dumped dict to replace enum members
  (`:258-274`, `:286`): another ≈ 34% of the same profile. On Pydantic 2,
  `model_dump(mode="json", exclude_none=True)` returns enum values directly (keep
  `_plain` for the v1 branch). Gain ~3 ms per resolve validation. Cheap, small.
- E3 — already right: `_step_json_schema` caches `model_json_schema()` per step
  (`llm/llm_quality.py:800-826`); `OUTPUT_EXAMPLES` is serialized only on repair /
  fallback rungs (`:1751`, `:1853`), never per prompt.
- E4 — json_mend is bounded: 0.7 s / 1.3 s / 1.5 s on 22 / 90 / 180 KB unmendable
  answers (`MAX_TRIES` 60, `_repeated` rescans per kind); cheaper than the 6-7 s
  model rebuild it replaces. No action.
- E5 — `decisions.decide` does 3-4 `get_setting` reads and a `providers` query per
  call (`_provider`, `_explicit_url` twice, `jev_model`, `capture_on`), ~10+
  calls a beat; unmeasured, likely negligible if `get_setting` is cached.
- E6 — `installed_language_packs()` copies the pack dict on every call (its own
  comment: "thousands of calls per turn"); two entries, negligible.

## Already registered

- `semantic_output_errors`' `director_interpret`/`director_resolve` branches dead;
  the `ledger_notes` layer; `required_channels` — UNBUILT_PIPELINE §1.1 item 11
  (F9 adds the `character` branch, the specialist prune, the `notes` parameter, and
  disputes the register's `_name_what_was_discarded` line).
- `dialogue_order` and `routed_to_background` never populated — UNBUILT_PIPELINE
  §1.1 item 8.
- `_reconcile_resolution` (hence `resolve_reconcile`/`resolve_repair`) gated off on
  every beat with rows — §1.1 item 3; measured here: 0 of 223 post-cutover resolves
  and 0 of 209 interprets with rows took the legacy repair path.
- Prose records carry no `from_event` — §1.1 item 1.
- `conceal_from` without `visibility:"concealed"` at the background gate — X3,
  UNBUILT_PERCEPTION §3.2 (F1 is the schema-level class beyond it).
- Unsolved `pitched` read as ordinary voice; quiet fallback is the owner's —
  UNBUILT_CHARACTERS §6.19 (F2's default-direction question).
- Prompt ids with no model outside the drift check — UNBUILT_PLATFORM §1.61 (F5 is
  the steps WITH a model).
- `sensory_events.source` dropped by the composer — UNBUILT_PIPELINE §1.135 (PX13)
  (adjacent to F8).

## Structure notes

- Natural seams in `llm/schemas.py` (7,005 lines): (a) the coercion core
  `_note_drop` … `LenientModel` (15-1221) — a module of its own; (b) the closed
  vocabularies and their normalizers (volume, stage, vocal affect, and the missing
  visibility of F1) (349-539); (c) output models by contract — prose-contract
  Director (`ProseDirectorOutput`, `UnifiedEvent`, `EncoderRepair*`, `RoomDesign*`),
  world-state (`StateDiff`, `RoomDef`, `SceneEntityDef`, the op models), character
  (bare/skip/compiled), background, greeting/prestory, and a LEGACY block
  (`CausalLedgerEntry`'s retired fields, `AssertedChange`, `ResolvedEvent`,
  `CausalTransform`, `LedgerTransformResult`, the five specialist models,
  `ReconcileOmission`, `Resolve*`/`InterpretRepairOutput`); (d) preprocessing
  (`preprocess_llm_output` 5673-5966) and the prose-markup canonicalizer
  (5283-5540, a clean `llm/prose_markup.py`); (e) the validation entry points and
  prunes (5968-7005); (f) `OUTPUT_EXAMPLES` (6008-6364), pure data.
- Monoliths in miniature: `preprocess_llm_output` (294 lines, one `if step_key ==`
  branch per step), `StateDiff` (241, mostly comment), `RoomDef` (217),
  `_lenient_coerce` (159), `CharacterOutput` (150), `validate_llm_output_strict`
  (139), `semantic_output_errors` (128), `canonicalize_prose_markup` (102).
- `SCHEMA_MAP` is two registries in one dict: step-output models and the five
  channel-owner validators (`director_body` … `director_spatial`) that no step
  produces any more; `SPECIALIST_CHANNELS` keys the second by the same strings.
  `_STATE_DIFF_DICT_FIELDS` names `entity_states`, which `StateDiff` lacks
  (harmless: establish's own prep reuses the tuple).
- `DirectorInterpret.update_forward_refs()` (`:2939`) is the Pydantic-1 spelling
  (deprecated on 2.11); `model_rebuild()` on the v2 branch.
- Module-level mutable state, schemas.py: `_ACTION_STAGE_ALIASES`,
  `_VOLUME_ALIASES`, `_VOCAL_AFFECT_ALIASES`, `_LEGACY_EVENT_IDS`,
  `_BARE_NOTE_ALIASES`, `SCHEMA_MAP`, `SPECIALIST_CHANNELS`,
  `CAUSAL_CATEGORY_REDIRECTS`, `_PROSE_MARK_TAGS`, `_PROSE_INK`, `OUTPUT_EXAMPLES` —
  no writer outside their definitions; `output_example()` (`:6366`) hands out the
  shared dict by reference (llm_quality embeds it and `json.dumps` it;
  `tools/story_drive.py:142` deep-copies, acknowledging the hazard).
  decisions.py: `OVERRIDE`, `CAPTURE_ROOT` (test hooks), `_CAPTURE_LOCK`.
  language_runtime: `_packs`, `_pack_failure`, `_renderers` under `_lock`;
  `_linguistic_cached` (lru 1024; 163 entries a language fit) returns MUTABLE
  `set`/`dict` values shared process-wide (9 `set` entries, all
  `agents.common` word sets) — no mutating caller found.
- Japanese pack drift beyond F4: the regex spot-scan (`jashape.py`) found no other
  printed STRICT shape with a translated top-level key; ja shapes also glue
  "は任意" onto optional keys (`held_byは任意:`), which reads as a key to a literal
  model.

## Docs checked

- AGENTS.md (decision model) "FAILS OPEN -- every channel granted -- when it
  cannot answer" — HOLDS for raised errors; DOES NOT for an answer missing a key (F7).
- AGENTS.md (`llm/json_mend.py`) "brackets, commas and a key's quotes, never a value
  ... a mend is used only if it validates" — the edit set HOLDS; "used only if it
  validates" holds but validation cannot see a misplaced nested member (F3).
- CLAUDE.md "`SPECIALISTS` ... is now only the owners table" — HOLDS; but
  `SCHEMA_MAP` still holds their output models (F10/Structure).
- CLAUDE.md memory rule "a field a card asks the model to WRITE must be on the
  output schema" — VIOLATED by `sources` (F6); `held_by` is now declared (HOLDS).
- `StateDiff.cast_changes` comment (normalize `departed`/`arrived`, warn otherwise)
  — HOLDS at `scene.cast_change_status`.
- `llm/schemas.py:4566-4572` (mapping shapes "read") — STALE (F10);
  `:2037` `DestructionEffect` "carried in StateDiff.destruction" — STALE (F10);
  `:3606` "(UNBUILT §2.1)" — DANGLING; the specialist-era comments — STALE (F12).
- `semantic_output_errors` docstring "Anything less goes to `notes`" — STALE (F9).
- `agents/composer.py:3105` "`director_establish` asks for `sensory_events:[{kind,
  description,source_room,...}]` in both packs" — WRONG for ja (`種類/説明/強度`, F4).
- UNBUILT_PIPELINE §1.1 item 11 "`_name_what_was_discarded` is NOT dead" — WRONG (F9).
- UNBUILT_IDENTITY §1.0 — STALE: it gates on `DEFERRED_PACK_PARITY = ("ja",)`, which
  is `()` (`tools/project_check.py:3335`); names `causal_director.txt`,
  `prompts/director_interpret.txt`, `interpret_delegation_note.txt`, none of which
  exist in either pack; says "the English prompts declare [`changes_asserted`] in all
  three places" — no en card names it. Its own "To clear" says delete the entry when
  the tuple empties.
- `card_source.py`/`_read_card` "a missing, empty or unreadable part ... raises"
  — HOLDS (`decode_part`, orphan scan, `_assert_no_surviving_reference`).
- `tests/test_schemas.py::test_no_schema_model_is_declared_without_anything_reaching_it`
  docstring ("Nothing validates against it ... a model is live if any `.py` outside
  it names it") — the second half is what it checks, and it is weaker than the
  first half claims (F10).
