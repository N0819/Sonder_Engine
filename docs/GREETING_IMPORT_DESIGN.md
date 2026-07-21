# Greeting-seeded openings — implementation design

> Status: **design / not yet implemented.** Import SillyTavern greetings + alt-greetings,
> preserve the prose verbatim, extract the simulation scaffolding underneath at ingest,
> and let a player jump straight in with any persona via "Start story now".

## Core idea

`greeting_interpret` is to a character's greeting what `director_interpret` is to player
input: one bounded job — turn freeform opening prose into structured establishment seeds —
but run **once per card at ingest** and cached, not per turn.

Two properties are non-negotiable:
1. **Preserve the greeting prose verbatim** as the opening narration (never paraphrase a
   hand-authored intro). Extract structured scaffolding *underneath* it.
2. **Persona-neutral at ingest.** The persona isn't chosen yet, so the player slot is a
   canonical placeholder `{{PLAYER}}` (normalize `{{user}}`/`<USER>`/… at import), resolved
   deterministically at launch.

## The clean cut (better than a new pipeline stage)

Do **not** add a `greeting_interpret` stage to `establishment_plan`. Instead, at launch,
**pre-bake the four establishment steps as saved variants** (`mapping_stage`,
`director_establish`, `perception_establish`, `narrator`) and call the existing
`POST /api/turns/{tid}/resume` — `resume_key_for_turn` finds the first missing step
(`commit`) and `_run_pipeline`'s establishment branch hydrates the pre-baked predecessors
(runtime.py ~586-599) and runs only `commit_all`. Consequences:

- The **narrator LLM never runs on turn 0** → the greeting is verbatim *by construction*
  (the only real guarantee, given `_strip_player_echo` + narrator paraphrase pressure).
- No new stage, no `register_step`, no `_run_pipeline` surgery — reuses the branch that was
  already built to run from a mid-plan key with hydrated predecessors. `PUT /api/turns/{tid}/prose`
  is precedent for hand-written narrator variants.

## Data cached on the card (sheet JSON, no DB migration)

```jsonc
"opening": {
  "first_message": "<verbatim greetings[0].prose — legacy mirror>",
  "greetings": [{
    "greeting_id": "greet_<sha1 of normalized prose>",   // stable across re-extracts
    "prose": "…verbatim, {{PLAYER}}-normalized…",
    "extraction": { /* GreetingInterpret dump, or null until extracted */ },
    "extractor_version": 1,
    "extracted_at": 0.0,
    "extraction_error": null
  }]
}
```
`_deep_defaults` preserves unknown `opening` keys, so native export→import round-trips it
for free. Per-chat launch state → one `world` key `greeting_seed` (covered by
snapshot/restore/branch/export). Chat-local private knowledge → `chat_chars.state.private_history`
(the store `private_knowledge_for` already reads).

## `GreetingInterpret` schema (schemas.py)

Reuse establishment sub-models (`RoomDef`, `SceneEntityDef`, `AttireState`,
`InitialEntityState`, `DialogueLogEntry`) so the baked output merges into `DirectorEstablish`
with no shape translation. New fields worth calling out:

- `knowledge_seeds: [{content, about_entity, kind, salience, revealed_in_prose, quote}]`
  — **the critical field.** Things the greeting implies the *character* knows/remembers/intends.
  `revealed_in_prose=false` (implied secret, off-page event, hidden motive) routes to the
  character's private memory and **never** to the player; `true` (stated openly on the page)
  gets a memory write only.
- `player_slot: {present, room, posture, activity, known_to_character, pronoun_tokens[],
  hard_attributes[{attribute,value,quote}]}` — `{{PLAYER}}` left symbolic; `hard_attributes`
  records only what the prose *hard-asserts* about the player, with quotes.

Wire into `SCHEMA_MAP` + `OUTPUT_EXAMPLES` + `semantic_output_errors` (rooms non-empty;
positions contains the character; if player present, positions contains `{{PLAYER}}`), reuse
`_coerce_empty_list_to_dict` in `preprocess_llm_output`. Add prompt id to `NSFW_PROMPT_IDS`.

## Module placement (deviation, argued)

Put the extractor in a **new top-level `greetings.py`**, not `agents/`. Rationale: `agents/`
modules are per-turn stages dispatched by `runtime.py`; `greeting_interpret` runs per-card at
ingest, and `importers.py` already runs ingest-time LLM work via `chat_complete`/`get_prompt`
under `_silent_provider_stream()`. Registering it in `STEP_HANDLERS` would be dead weight and
drag heavy scene/memory imports into the import path.

```python
# greetings.py
EXTRACTOR_VERSION = 1
PLAYER_TOKEN = "{{PLAYER}}"
def normalize_player_slots(text, char_name): ...   # {{user}}/<USER> -> {{PLAYER}}; {{char}} -> name
def extract_greeting(sheet, greeting_prose):        # one complete_validated_json call, step "greeting_interpret"
    # + deterministic guard: a seed that names {{PLAYER}} is not asymmetric -> revealed_in_prose=True
def bake_establishment(sheet, greeting, persona):   # deterministic launch merge (below)
```

## Ingest (importers.py)

Capture `first_mes` + `alternate_greetings[]` in all three import paths (`character_book`
is already imported). Normalize placeholders, hash ids, **eagerly extract greeting[0] only**
(alt-greetings lazily on first swipe). Extraction failure must not fail the import
(record `extraction_error`). Extend `REINT_CHAR_SYS` to re-attach greetings deterministically
rather than asking the model to echo long prose back.

## Launch — deterministic merge (`POST /api/characters/{cid}/start`)

Body `{persona_id, greeting_index}`. Steps:
1. Ensure extraction (lazy / stale `extractor_version` → extract now).
2. `bake_establishment`: substitute `{{PLAYER}}`→persona name (and possessives); rename
   `{{PLAYER}}` keys in positions/attire/entity_states; place player in `player_slot.room`
   (fallback: character's room). **Persona wins appearance** — drop the greeting's player
   body descriptors (they survive only inside the verbatim prose). Assemble a
   `DirectorEstablish`-shaped dict + the deterministic tail `director_establish()` appends
   (extract that tail into a shared `establishment_tail(out, cast)` helper so it can't drift).
3. **Escalation** (tiny LLM only if it fires): iff a `hard_attributes` entry conflicts with
   the persona's non-empty visible field, or `pronoun_tokens` disjoint from persona pronouns.
   Minimal-span edits only, guarded by an edit-distance cap.
4. Create chat; if `player_slot.known_to_character`, seed the `known` map (code exists at
   chat_add_char).
5. Route private knowledge (below).
6. `wset(cid, "greeting_seed", {...})`.
7. Create turn 0, `ensure_checkpoint`, pre-bake the four steps with `save_step`, return
   `{chat_id, turn_id}`. UI opens the chat and calls the existing `resume` → only `commit` runs.

## Knowledge routing (the boundary mechanism)

For each `knowledge_seeds` with `revealed_in_prose == False`:
1. Append `{fact_id: "greet:{gid}:{i}", content, about, known_by: []}` to
   `chat_chars.state.private_history` → served to `character_step` via `private_knowledge_for`;
   `known_by: []` means only the owner sees it — the player's viewer name never matches, so it
   cannot reach `perception_*` or the narrator by construction.
2. `add_memories_batch` with stable `event_key="greeting:{cid}:{char}:{gid}:{i}"` (the pattern
   `confirm_promotion` uses) for idempotency on re-launch/swipe.

Revealed seeds get the memory write only. Player-facing leak surface = zero: the only
player-visible artifacts are the verbatim prose and the committed objective scene.

## Greeting swipe (turn-0 variants)

`POST /api/chats/{cid}/greeting_swipe {greeting_index}` (turn 0, idle only): lazy-extract;
replace knowledge (delete `greeting:{cid}:{char}:%` memories, re-add for new greeting); rewrite
`greet:`-prefixed private_history; `refresh_checkpoint(cid, 0)` (critical — the pipeline run
does `restore_checkpoint(cid, 0)`, which contains memories); `save_step` the four new contents
(each a new active variant — this *is* the variants rail); stream `run_pipeline(cid, tid, from_key="commit")`.
Pure variant-activation can't implement swipe because activating an old variant doesn't re-run
`commit_all`, and turn-0 commit writes scene/memories/events.

## API surface

| Route | Follows |
|---|---|
| `POST /api/characters/{cid}/start` `{persona_id, greeting_index}` → `{chat_id, turn_id}` | composite like `confirm_promotion` |
| `POST /api/characters/{cid}/greetings/{gi}/extract` `{force?}` | re-extract + `extractor_version` migration hook |
| `PUT /api/characters/{cid}/greetings/{gi}` `{prose?, extraction?}` | reviewable/editable (or fold into `char_edit`) |
| `POST /api/chats/{cid}/greeting_swipe` `{greeting_index}` → NDJSON | mirrors `turn_reroll`/`resume` streaming |

## UI (editors.js / app.js / chat.js)

- `charEditor`: greeting pager (`◀ 2/5 ▶`) over the prose textarea + collapsible extraction
  JSON with "✨ Extract"/"↻ Re-extract (v1→v2)".
- `renderCharacterSidebar`: `▶ Start` per character → persona `<select>` + greeting preview →
  "Start story now" → `/start` → `openChat` then resume-stream.
- Turn-0 bubble: `◀ ▶` swipe arrows when the chat has a `greeting_seed` and >1 greeting.

## Edit-routing table

| Change | Primary files | Inspect |
|---|---|---|
| Greeting capture/normalization | `importers.py`, `greetings.py` | `character_schema.py`, importer tests |
| Extraction schema/prompt | `schemas.py`, `prompts.py` | `llm_quality.py` |
| Launch merge / escalation | `greetings.py` | `agents/director.py` tail (share it), `commit.py` |
| Seeded turn-0 execution | `app.py` (`/start`, `/greeting_swipe`) | `agents/runtime.py` (hydration, read-only), `storage.py`, `checkpoints.py` |
| Private-seed routing | `app.py` launch | `scene.py:private_knowledge_for`, `memory.py`, `commit.py` |
| Greeting UI | `static/js/editors.js`, `app.js`, `chat.js` | matching `app.py` routes |

## Test surface

- `test_greeting_import.py`: alt greetings captured; placeholder normalization; `character_book`
  still imported; native round-trip byte-identical; extraction failure doesn't fail import.
- `test_greeting_schema.py`: `validate_llm_output_strict("greeting_interpret", …)`; the
  `{{PLAYER}}`-in-seed guard flips `revealed_in_prose`.
- `test_greeting_launch.py`: `/start` → turn 0 with the steps materialized, `resume_key` None
  after resume; **narrator prose byte-equals the substituted greeting** (the verbatim test);
  persona placed in `player_slot.room`.
- `test_greeting_knowledge_boundary.py` (cognition-test placement): unrevealed seed appears in
  `private_knowledge_for(char)` and the char's memories, and **not** in `perception_establish`
  player view, narrator prose, or `private_knowledge_for(player)`.
- `test_greeting_swipe.py`: swipe A→B replaces active variants + scene, greeting-A memories
  gone, checkpoint 0 refreshed.
- `test_greeting_merge_escalation.py`: attribute/pronoun conflict fires, matching persona
  doesn't, edit-distance cap falls back.

## Risks

- Char-view = greeting prose slightly inflates turn-0 episodic salience — cap or strip
  already-minted dialogue quotes.
- Baked-tail drift — mitigated by the shared `establishment_tail` helper (the one small edit
  inside `agents/`).
- Extraction quality is the real product risk; because it's cached, reviewable JSON with a
  version, bad extractions are editable/re-extractable without touching any chat — which is
  exactly why ingest-time extraction is the right call.
