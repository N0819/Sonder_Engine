# Audit — the Director's floors, evidence, repair, views, contact and fan-out modules

Auditor scope: `agents/director_evidence.py` (4,107), `agents/director_floors.py` (2,548),
`agents/director_repair.py` (1,691), `agents/director_fanout.py` (1,121),
`agents/director_views.py` (760), `agents/director_contact.py` (611). Working tree at
`84f3de23` (clean). Read-only; all probes were pure-function snippets on `.venv/bin/python`
(no test run was needed: the orchestrator's baseline is green, 19,635 passed / 4 xfailed).

## Scope read

**Read in full, every line:** all six files above.

**Read in part, to trace callers and data (not audited as files):**
- `agents/director.py`: import block 1-420; `director_interpret` call sites 2105-2130,
  2285-2335, 2355-2395, 2539; `_reconcile_interpretation` 2836-2900; `_block_restrained_moves`
  and `_reconcile_resolution` 3100-3420, 3510-3560; `_refuse_cast_doubles` 3712-3737;
  `_run_specialists` 3740-4000; `_ground_public_evidence` 4300-4345; dispatch helpers
  5180-5250; `director_resolve` 5377-5600, 6240-6300, 6634-6672, 7262-7300, 7325-7470,
  7755-7830.
- `agents/director_prose.py`: 210-232, 553-583, 1240-1345, 1515-1530, 2060-2080, 4261,
  4546-4626, 4780-4850, 5050-5130.
- `agents/common.py` 2112-2250, 3859-3910, 12899-12970; `agents/composer.py` 664-714;
  `agents/character.py` 3555-3640, 4255-4300; `agents/loops.py` 1255-1320, 1915-1970;
  `agents/background.py` 236-320, 516-560.
- `story/scene.py` 734, 1400-1460, 1693-1724, 1849-1880; `persist/commit_entities.py`
  130-170, 600-630; `world/spatial_contacts.py` 83-95, 330-420, 1900-2030;
  `world/causal_program.py` 320-420; `world/site_plan.py` 499-590; `llm/schemas.py`
  (StateDiff, UnifiedEvent, CausalLedgerEntry, DirectorInterpret, EncoderRepair*,
  ActionVisibility/ActionCommitment, `_ANIMATE_ENTITY_KINDS`); `llm/llm_quality.py`
  1143-1175 and the failure tail of `complete_validated_json`; `llm/decisions.py` 281-320;
  `tools/project_check.py` 1620-1800; `language_runtime/__init__.py` 743-773;
  `language_packs/{en,ja}/cards/linguistics.json` (`agents.director`, two `agents.common`
  keys); encoder card `core.txt`, `prose_contract/encoder_repair.txt`.
- Docs: `AGENTS.md` 284-300, 427-428, 444, 492-493, 850-856, 921-931; `Design.md` rows
  467, 554, 555; `docs/UNBUILT_PIPELINE.md` §1.1 (all items), §1.11b, §1.214, §2.18;
  `docs/UNBUILT_PERCEPTION.md` §3.2; `docs/UNBUILT_LIVING_WORLD.md` 1868-1890, 2940-2975.

Method for liveness (question 1): an AST pass over every `.py` in the repo (excluding
`.venv`, `output/`) indexed every Name/Attribute use and every identifier-shaped string
constant (`getattr(m, "x")`, patch strings) of each top-level name in the six files, then a
name-resolution reachability fixpoint from module-level code, decorated defs and class
bodies (prod only, then prod+tools). Every candidate was then confirmed by hand with
`grep -rw` across `.py/.js/.json/.md`.

## Findings

Index to the assignment's questions: Q1 liveness -> F18 + "Liveness map" in Structure notes;
Q2 prose regexes -> F5, F11, F13, F15 + the inventory table in Structure notes; Q3 repair ->
F7, F8, F9, F17; Q4 normalisers -> F1, F10, F19; Q5 floors against data nobody produces ->
F14, F18, F20 + Already registered; Q6 efficiency -> Efficiency.

### F1 — The ledger normaliser passes `visibility` (and `commitment`) through raw, and the firewall reader matches one exact token

- **Where:** `agents/director_evidence.py:2963-2965` (inside `normalize_causal_ledger`)
  ```python
  "commitment": str(entry.get("commitment") or "asserted"),
  "targets": targets,
  "visibility": str(entry.get("visibility") or "overt"),
  ```
  and the reader it feeds, `agents/composer.py:671`:
  ```python
  if entry.get("visibility") != "concealed":
      return False
  ```
  while the floors in this tree read the same field case-insensitively:
  `director_floors.py:2255`, `:2409` (`str(...).strip().lower() != "concealed"`), `:2448`;
  `background.py:684/1704/2114`, `common.py:7911` likewise.
- **Scenario:** the encoder (UnifiedEvent declares `visibility: str`, not the
  `ActionVisibility` enum; its card `encoder/core.txt:21` never states the values) writes a
  whispered aside as `"visibility": "Concealed"` or `"concealed "`. `strip_addressee_concealment`
  and `resolve_concealment_refs` treat it as concealed and rewrite its `conceal_from`; the
  projection keeps the raw string; `concealed_from_observer` reads it as overt and the line
  is delivered in full to the body it was hidden from. Same class for `commitment`:
  `"Contestable"` is contestable to `director.py:4524/4536/6575`, `skip_stage.py:176`,
  `beat_timeline` (all casefold) and asserted to `director_prose.py:277` and
  `narration.py:2312` (exact compare) -- two readers of one row disagree.
- **Verified:** snippet — `UnifiedEvent(visibility="Concealed ")` keeps `'Concealed '`;
  `concealed_from_observer({"visibility": "Concealed ", "conceal_from": ["Ivo"]}, "Ivo")`
  -> `False`, with `"concealed"` -> `True`. Traced encoder event -> `ledger_from_events`
  (`_ROW_FIELDS` copies raw) -> `normalize_causal_ledger` (raw) -> sequence/dialogue_log.
  `vocal_affect` is the one delivery field this dict already canonicalises
  (`schemas.normalize_vocal_affect`, line 2974).
- **Confidence:** mechanism CONFIRMED; occurrence PLAUSIBLE (needs a non-canonical spelling).
- **Severity:** LEAK.
- **Fix:** canonicalise both fields at this ingest point against `ActionVisibility` /
  `ActionCommitment` (strip + casefold); an unknown visibility value fails CLOSED with a
  warning (hidden from non-actors, as an empty `conceal_from` already means), which is the
  direction `resolve_concealment_refs`' own docstring argues for. The prompt half (state
  the two values in the core card) is separate and optional.
- **Test:** `normalize_causal_ledger` on a speech row with `visibility: "Concealed "` ->
  projection `visibility == "concealed"`; then `concealed_from_observer(projection, x)` is
  True for a listed `x`.

### F2 — At interpret, concealment is resolved against the cast alone, so a line hidden from a PLAYER by an alias is published to that player

- **Where:** `agents/director.py:2293-2305` and `:2326-2328` call
  `director_floors.resolve_concealment_refs` (`agents/director_floors.py:2218`) with
  `cast_by_id, target_forms = _cast_match_forms(ctx.cast)` -- cast only. The resolve site
  (`director.py:5467`) passes `_scene_match_forms(ctx)`, which adds the persona and extra
  players with their aliases; its docstring (`director_views.py:67-77`) records this exact
  bug ("reported as naming 'no body in this scene'") and fixed it at one of two sites.
- **Scenario:** multiplayer chat; extra player Bob whispers to Mara, `conceal_from:
  ["Hina"]` (the persona's alias). `_resolves_to_a_body("Hina", cast-only maps)` is False
  -> the entry is kept raw and the note says no body answers to it -> the composer compares
  `"hina"` with observer name `"hinami"` -> the persona receives the whispered line. The
  fail-closed branch for an unresolved `character:<x>` form (`director_floors.py:2312-2327`)
  likewise lists every CAST body and no player, so the players still receive the line.
  Extension (PLAUSIBLE): background presences and charter figures standing in the room are
  in neither map at either stage, so a line concealed from "the stablehand" by any spelling
  but its exact presence name reaches its stateless reaction (`background._presence_line`
  -> `composer.speech_percept`).
- **Verified:** snippet with `_cast_match_forms` maps -> notes
  `["conceal_from named 'Hina', which no body in this scene answers to ..."]`,
  `conceal_from` unchanged, `concealed_from_observer(seq[0], "Hinami") -> False`.
- **Confidence:** CONFIRMED (function + call-site maps); scenario needs an alias or engine
  form naming a player.
- **Severity:** LEAK.
- **Fix:** pass `_scene_match_forms(ctx)` at both interpret call sites (the class: one set
  of body maps for every concealment floor); consider adding present non-cast bodies
  (presences, laid figures) to those maps.
- **Test:** an extra player's concealed line naming the persona by alias at
  `director_interpret`; assert the persona's composed view lacks it.

### F3 — The cast-double floor refuses only `kind == "person"`, and is a no-op at interpret

- **Where:** `agents/director_floors.py:2524-2527`
  ```python
  if eid in held or not isinstance(entity, dict):
      continue
  if str(entity.get("kind") or "person").strip().casefold() != "person":
      continue
  ```
  and `agents/director.py:3720` (`_refuse_cast_doubles`), called at interpret
  (`director.py:2388`) and resolve (`:6499`):
  `sd = out.get("state_diff") if isinstance(out.get("state_diff"), dict) else None`.
- **Scenario A (kind):** `kind` is "free text in the fiction's own words"
  (`encoder/entities__new.txt:4`). The measured case the floor was written for (a stranger
  filed as `ines_calder`, aliased "the doctor") minted with `kind: "woman"`, `"human"`, or in
  a Japanese story `"人物"` is NOT refused: a second body of a cast member persists, the
  phantom that "38 turns later answered a line in the doctor's place".
- **Scenario B (stage):** interpret writes its channels into `state_assertions`
  (`director_fanout._stage_container`), never `state_diff`, so the interpret call returns
  `[]` before looking. The interpret mint is then previewed into `resolve_sc`
  (`preview_player_state_assertions`, `director.py:5568`), so at resolve it is in
  `held = set(sc["entities"])` and skipped; `merge_player_state_assertions` carries it into
  the durable diff. A double minted at interpret is refused at neither stage.
- **Verified:** snippet — same cast row, mint `{"name": "Ines Calder"}` with kind `person`
  / none -> refused; `woman`, `human`, `人物` -> "KEPT (second body)". Scenario B by trace
  (no `state_diff` at interpret: only `director.py:522` (establish), `:3175`, `:6688` set it).
  `tests/test_cast_double_refused.py` uses `kind: "person"` only.
- **Confidence:** A CONFIRMED; B CONFIRMED by trace (not executed end to end).
- **Severity:** CORRUPTION (a second record of a cast member is committed).
- **Fix:** state the one excluded case instead of the included one: skip only kinds in the
  engine's own inert set (`persist.commit._INERT_ENTITY_KINDS`, already imported by the
  sibling binder at `director_floors.py:1899`); run the interpret call on
  `out["state_assertions"]` (the stage container) and exempt only entities held BEFORE the
  beat (`sc`, not the previewed `resolve_sc`).
- **Test:** parametrize the existing test over `kind in ("person", "woman", "human",
  "人物")`; one test driving `_refuse_cast_doubles` with an interpret `out` carrying
  `state_assertions.entities`.

### F4 — Body identity is compared by casefold string equality in three floors whose siblings use the engine's resolver

- **Where (the class, three sites):**
  - `agents/director_floors.py:943-945` (`_restraint_blocked_moves`, run on EVERY resolve via
    `_block_restrained_moves`, and by `director_movement._travel_continues`):
    ```python
    by_subject.setdefault(record["subject"].casefold(), []).append(record)
    for who in list(positions):
        subject_records = by_subject.get(str(who).casefold())
    ```
  - `agents/director_contact.py:354-358` (`_merge_player_contact_assertions.same_pair`):
    `str(left.get("actor") or "").casefold() == str(right.get("actor") or "").casefold()`.
  - `agents/director_contact.py:591-593` (`_merge_character_contact_endings.key`).
  The validator in the same module canonicalises with `_canonical_scene_subject` /
  `same_subject` (`director_contact.py:57-61`, `:80-81`), and the restraint liveness check
  in the same floor uses `room_of(sc, record["subject"])`, which resolves aliases.
- **Scenario:** a restraint row's `subject_id` is model-written and stored as written
  (`commit_entities.py:135`: "Case-insensitive on subject because `subject_id` is a
  model-written name"). Subject `"Hinami Kurosawa"`, positions key `"Hinami"`: a bound
  (standing) body walks out of the cell. A resolve contact op spelled with the alias
  coarsens the player's asserted endpoint (`wrist` -> `arm`) without the
  "preserved player-declared contact endpoint" refusal, and re-adds a contact a character
  explicitly ended.
- **Verified:** snippets — restraint subject `"Hinami"`/`"hinami"` -> blocked;
  `"Hinami Kurosawa"` -> NOT blocked, while `same_subject(sc, "Hinami Kurosawa", "Hinami")`
  is True and `room_of` resolves it. Contact merge: actor `"Hinami"` -> coarsening refused
  (1 note); `"Hinami Kurosawa"` -> coarsened op kept, 0 notes. Ending merge: re-add by
  `"Mirelle"` dropped, by `"Mirelle Sulmirath"` kept.
- **Confidence:** CONFIRMED (mechanism); occurrence depends on an alias spelling.
- **Severity:** WRONG-SCENE (a restrained body relocates; a player's contact is re-described
  against their declaration; an ended contact stands again).
- **Fix:** one identity rule for all three: compare with `same_subject(scene, a, b)` (or
  canonicalise subjects to scene keys once at the top of each function, as the validator
  does). Not a guard widening: it makes the floor apply to the body it already names.
- **Test:** the three snippets as tests (restraint row keyed by an alias the scene's entity
  carries; alias-spelled resolve op against a player assertion; alias-spelled re-add
  against a character ending).

### F5 — `restore_declared_quotes`' lift says a line twice and corrupts an act's text

- **Where:** `agents/director_evidence.py:2661-2700`
  ```python
  said = {body(r.get("event")).casefold() for r in ledgers
          if isinstance(r, dict) and carries_speech(r)}
  ...
  lifted = [sp for sp in spans
            if sp.casefold() not in said and sp.casefold() in event.casefold()]
  ...
  residual = re.sub(
      r'["“]?\s*' + re.escape(sp) + r'\s*["”]?[.!?,]?',
      " ", residual, count=1, flags=re.IGNORECASE)
  ```
  Runs on every interpret (`director.py:2124`). "Already said" is EXACT body equality and
  "contained" is a bare substring; the second stage below it uses word share
  (`QUOTED_LINE_CARRIED`), whose comment promises a line "carried with its punctuation
  normalised ... is never said twice" (`:2551-2558`) -- true of that stage only.
- **Scenarios (all executed):**
  1. Input `"Hi" she calls, and hits the brass chime twice.`; encoder rows: speech `Hi!`,
     act `hits the brass chime twice`. Result: speech `Hi!`, speech `Hi` (the line twice),
     act `ts the brass chime twice` (the "hi" of "hits" was cut out).
  2. Input `"Wait here," she says, and walks to the door.`; rows: speech `Wait here.`,
     act `says "Wait here," and walks to the door`. Result: `Wait here.` and `Wait here,`
     -- every hearer is delivered the player's line twice.
  3. Japanese: act `Hinamiは「行こう」と言って扉を開けた` -> speech `行こう` plus an act
     `Hinamiは「 」と言って扉を開けた` (the residual strip knows only `"`/`“”`).
- **Confidence:** CONFIRMED (snippets above on the real function).
- **Severity:** WRONG-SCENE (duplicated player speech; an act surface rendered as nonsense).
- **Fix:** in the lift, treat a span as said when `_carried_share(sp, spoken) >=
  QUOTED_LINE_CARRIED` (the same test the second stage uses), and lift only a span that
  occurs as a QUOTED span inside the row (`_QUOTED_SPAN.finditer(event)`), never as a bare
  substring; strip the matching quote pair, `「」` included.
- **Test:** the three inputs above as a parametrised test of `restore_declared_quotes`.

### F6 — A contested reactor's contact endings are never read

- **Where:** `agents/director_contact.py:438-447` (`_validated_character_contact_endings`)
  reads `ctx.character_results` only:
  ```python
  result = (ctx.character_results.get(cid)
            or ctx.character_results.get(str(cid)) or {})
  ```
  while its sibling `_character_material_effects` (`:504`) reads both:
  `for results in (ctx.reaction_results or {}, ctx.character_results or {}):`.
- **Scenario:** in a contested physical beat the reaction loop runs `character_step` for the
  reactor (`loops.py:1966`) and stores it in `ctx.reaction_results` (`:1968`); that reactor
  is then excluded from the interaction loop (`loops.py:1299-1316`, `already_reacted`). Its
  declared `contact_ops: [{op: remove, contact_ref: "contact:0"}]` (wrenching free of a
  grip; `CharacterOutput.contact_ops`, `schemas.py:4395-4400`) is never validated, never
  shown to the encoder as `character_contact_endings`, and `_merge_character_contact_endings`
  cannot drop the Director's stale re-add of that grip. No warning is raised.
- **Verified:** by trace (call sites above; `director.py:5547` passes `sc` and `ctx`).
- **Confidence:** CONFIRMED by trace.
- **Severity:** WRONG-SCENE (a body that let go, or pulled free, stays in contact).
- **Fix:** iterate `(ctx.reaction_results, ctx.character_results)` as the material sibling
  does, de-duplicating endings (already `if ending not in out`).
- **Test:** a ctx whose reactor declared a removal only in `reaction_results`; assert the
  ending is returned and a resolve re-add is dropped.

### F7 — The repair retry keeps ONE of two answers and drops a declared act the other carried

- **Where:** `agents/director_repair.py:1109-1117` and its use at `:1150-1160`
  ```python
  def _fuller(job, first, again):
      ...
      return again if weight(again) > weight(first) else first
  ...
  redo[job_id] = _fuller(by_id[job_id], answered.get(job_id), answer)
  ```
- **Scenario:** a job declared acts A and B; the first answer carries A (plus a narration
  event), so the job is retried for falling short of its declared acts; the retry carries
  B. Weights (1, 2, True) vs (1, 1, True): the first wins and B is discarded, although the
  union of the two answers carries both. `_declared_left` then warns "no event carries
  declared act(s)" for an act the repair had produced. This is the 1.214 class one rung
  over ("the same members, put back where they belong") and the "merge by key" lesson
  `merge_answers` (`:1058`) already encodes for pieces of one answer.
- **Verified:** snippet — kept events `['She lifts the latch.', 'The gate creaks.']`,
  declared carried 1 of 2; the union carries 2.
- **Confidence:** CONFIRMED.
- **Severity:** WRONG-SCENE (a cast/player declared act goes uncarried; the prose tells it,
  the beat does not).
- **Fix:** merge the two answers by key instead of choosing: union `events` de-duplicated by
  `source_event_id` (then by event text), union `transforms`, first non-empty
  `after`/`move_to`/`none` -- the `merge_answers` rule.
- **Test:** the snippet as a test of `_repair_group` with `call_repair` stubbed to return the
  two answers in turn.

### F8 — A fix answered with both `move_to` and a corrected write moves the WRONG write and discards the correction

- **Where:** `agents/director_repair.py:1412-1425` (`apply_answers`)
  ```python
  transform["patch"].pop(job["channel"], None)
  if moves and job.get("write") is not None:
      events[refs.index(move_to)].setdefault("transforms", []).append(
          {"item": (transform or {}).get("item", ""),
           "patch": {job["channel"]: job["write"]}})
  elif writes:
      events[target].setdefault("transforms", []).extend(writes)
  report["applied"].append(job["id"])
  ```
- **Scenario:** the card says `move_to` and `transforms` are alternatives, but answers arrive
  in pieces (measured: 30 of 198 runs split an answer) and `merge_answers` joins a `move_to`
  piece with a `transforms` piece. The job's flagged (wrong) value is moved to the new
  event and the corrected value is dropped; the report says `applied`. Executed with the
  docstring's own measured case: the ship's transit `to: beach` moved to e2, the corrected
  `to: far_quay` lost.
- **Confidence:** CONFIRMED (snippet), occurrence PLAUSIBLE (needs both fields).
- **Severity:** WRONG-SCENE.
- **Fix:** when an answer carries both, place the corrected `writes` at `move_to` (the move
  says where, the write says what) and drop the flagged value; record the conflict.
- **Test:** the snippet (`merge_answers` of a `move_to` piece and a `transforms` piece, then
  `apply_answers`) asserting e2 holds `far_quay`.

### F9 — One failing repair call discards every other repair's answers

- **Where:** `agents/director_repair.py:1590-1600`
  ```python
  with ThreadPoolExecutor(max_workers=len(groups)) as pool:
      futures = [pool.submit(_isolated(contextvars.copy_context()), run_group, group)
                 for group in groups]
      results = [future.result() for future in futures]
  ```
  and `_repair_group` (`:1120-1196`), which calls `call_repair` twice (first + retry) with
  no handler. `call_repair` -> `director._agent_json` -> `llm_quality.complete_validated_json`,
  which ends in `raise RuntimeError(...)` when every rung fails.
- **Scenario:** the event-recovery group answers well; the fix group's call (or either
  group's retry) exhausts its rungs and raises. `future.result()` re-raises, the whole
  `_check_and_repair` unwinds, and `check_and_repair` (`:1476-1495`) keeps the UNREPAIRED
  draft: the recovered events and the first call's good answers are thrown away. It warns,
  so it is not silent, but the work was in hand.
- **Confidence:** CONFIRMED by trace.
- **Severity:** WRONG-SCENE (recoverable events lost).
- **Fix:** catch per call inside `_repair_group` (an `Aborted` still propagates): a failed
  call leaves its jobs unanswered (they already have a warning path), a failed retry keeps
  the first answers, and a failed group leaves the other group's answers to be applied.
- **Test:** stub `_agent_json` so the fix group raises `RuntimeError`; assert the event
  group's recovered events are in the returned events.

### F10 — World- and dice-caused rows are projected as an actor's ACTION

- **Where:** `agents/director_evidence.py:2923-2924`
  ```python
  worldly = str(entry.get("authority_mode") or "").strip().casefold() \
      in ("world", "mechanical")
  ```
  reads the RAW row, while the engine fills the authority it handed each source three
  dozen lines later (`:2950-2953`, `(authority or {}).get(source_entity_id) or ...`). Prose
  rows never carry `authority_mode` (`UnifiedEvent` has no such field;
  `director_prose._ROW_FIELDS`, `director_prose.py:4261`, does not copy it), so `worldly` is
  always False on the live path.
- **Scenario:** event_inputs groups `world_pressure:<id>` / `authored_event:<n>` ("world")
  and `engine:dice:<n>` ("mechanical") (`director.py:4502-4590`). Their rows project as
  `type: "action"`, `actor: "world_pressure:storm"`, `attempt: <event>` instead of
  `type: "event"`, `description: <event>` -- contradicting the block comment ("it is an
  EVENT because the world or the dice caused it rather than an actor"). Every reader that
  branches on `type == "event"` (`common.py:4475` content key, `beat_event_ledger`'s `kind`,
  perception's sourceless-event path) sees an act by a non-body id instead.
- **Verified:** snippet — rows with engine authority `world`/`mechanical` -> projected
  `action`, `actor= world_pressure:storm` / `engine:dice:0`, `description: None`.
- **Confidence:** CONFIRMED (projection); downstream rendering PLAUSIBLE (not traced to a
  composed view).
- **Severity:** WRONG-SCENE.
- **Fix:** `worldly = normalized["authority_mode"] in director_prose.WORLD_AUTHORITY`
  (compute after `normalized` is built). Same edit corrects the comment at `:2945-2949`
  ("never read back off the row"), which the fallback on `:2952` contradicts.
- **Test:** the snippet as a test of `normalize_causal_ledger` (row sourced to a world
  input -> `type == "event"`).

### F11 — The release floor frees the POSSESSOR of a thing untied (object side) — latent, floor gated

- **Where:** `agents/director_floors.py:1059-1077` (`_release_attempts`): the possessive
  exclusion exists only on the subject side (`:1069`, `if low[ne:ne + 2] in ("'s", "’s")`);
  the object side (`:1059-1067`) accepts any name within `_MAX_RELEASE_OBJECT_GAP` words.
- **Scenario:** "Mirelle unties Hinami's hair ribbon." -> releases Hinami from her restraint.
  Japanese: "ミレルはHinamiの髪をほどいた。" -> released (the possessive `の` is never
  checked on either side).
- **Verified:** snippet — all three sentences return `{'Hinami'}`. The cue battery in
  `tests/test_restraint_exits.py` (lines 259-340) has no object-side possessive case.
- **Confidence:** CONFIRMED. Latent: `_restraint_exits` runs only inside
  `_reconcile_resolution`, which prose beats skip (UNBUILT_PIPELINE §1.1 item 3) -- this
  fires the day that floor is enabled.
- **Severity:** WRONG-SCENE (a body somebody still holds is freed).
- **Fix:** on the object side, refuse a name whose match is followed by the possessive
  (English `'s`/`’s`; for ja, a pack-supplied possessive particle via `_ling`, e.g. `の`),
  the same rule the subject side states.
- **Test:** add "unties Hinami's hair ribbon" and the ja sentence to `TestReleasePrecision`
  expecting `set()`; keep "unties the ropes binding Hinami" -> `{Hinami}`.

### F12 — The observer-epithet report fires on any addressee that is a substring of a label

- **Where:** `agents/director_views.py:351-352`
  ```python
  in_target = any(label_cf in t.casefold() or t.casefold() in label_cf
                  for t in targets if t.strip())
  ```
  Runs on every resolve (`director.py:7776`), writes `ctx.tell_director` (next beat's
  Director payload) and a warning.
- **Scenario:** Corin's label is "the young smith's apprentice"; any line whose
  `intended_target` is "he", "Al", "Ed", "you" or another short string occurring inside
  that label produces "objective record: Corin was referred to in intended_target as 'the
  young smith's apprentice' ... name them canonically" -- a false instruction to the
  Director about a line it addressed correctly.
- **Verified:** snippet with a stub ctx — target `"he"` -> 1 report.
- **Confidence:** CONFIRMED.
- **Severity:** WRONG-SCENE (minor: a false note steering the next beat's author).
- **Fix:** drop the reverse containment (`t in label`) or require it to cover the whole
  label (`t.casefold() == label_cf`); the forward direction already catches a target that
  embeds the label.
- **Test:** the snippet as a test (short addressee -> no report; addressee equal to the label
  -> report).

### F13 — Role binding of a minted person is ASCII-only

- **Where:** `agents/director_floors.py:1564-1582`
  ```python
  _FIGURE_STOPWORDS = frozenset({"the", "a", "an", "of", "s"})
  ...
  words = [w for w in re.split(r"[^a-z0-9]+",
                               str(text or "").casefold().replace("'s", ""))
  ```
  used by `_bind_minted_entities_to_present_figures` (`:2028-2044`).
- **Scenario:** Japanese story; the encoder mints "門番" (gatekeeper) beside the charter's
  posted gatekeeper. `_figure_head_noun("門番") == ""`, so `heads` is empty and the role rung
  never binds: the beat keeps a second, unsimulated gatekeeper -- the "phantom fourth
  innkeeper" this floor exists to prevent. Name binding (`_bare_person_name`) still works.
- **Verified:** snippet — `'宿屋の主人' -> ''`, `'門番' -> ''`, and
  `_role_noun_matches('', {''}) -> False` even for identical Japanese roles.
- **Confidence:** CONFIRMED (function); scenario PLAUSIBLE.
- **Severity:** WRONG-SCENE (duplicate body in non-Latin stories).
- **Fix:** tokenise with the Unicode word class (`[^\W_]+`) and take the head from the
  pack (`_ling`), or, for unspaced scripts, compare the whole folded role phrase; the
  English compound rule stays as is. (Distinct from UNBUILT_LIVING_WORLD's registered
  English residual "a role noun the post's noun neither equals nor ends".)
- **Test:** a ja mint whose role phrase equals a present figure's role binds by role.

### F14 — The public-source list is cut at 20, and Charter minds lose every public act past it

- **Where:** `agents/director_fanout.py:189` (`"public_sources": public_sources[:20]`) and
  `:173` (`dialogue ... [:20]`). The list is the engine-authored source set
  `_ground_public_evidence` (`director.py:4304-4345`) annotates; its docstring and AGENTS.md
  row 444 promise "Every legitimate source receives a deterministic fallback record ... A
  failed annotation keeps the factual source".
- **Scenario:** a busy beat (player + cast) declares more than 20 public lines/acts; sources
  21+ never enter the view, so they get neither the encoder's annotation nor the fallback,
  and `commit_charter_observations` files nothing for them -- the town's bodies never
  witness those acts. No warning.
- **Verified:** snippet — 8 player lines + 4 cast x 5 lines = 28 -> 20 in the view, last kept
  `speech:C2:1` (C2's later lines and all of C3 dropped).
- **Confidence:** CONFIRMED.
- **Severity:** SILENT-NOOP.
- **Fix:** a cap is the owner's call: name it (constant + comment), and when it bites, keep
  the fallback for the overflow (the fallback costs no model call) and warn. (`dialogue`'s
  cap is read only by a dead branch, F18.)
- **Test:** 25 public sources -> `_ground_public_evidence` returns a record for each.

### F15 — The interpret-coverage detector is inert for Japanese input

- **Where:** `agents/director_evidence.py:78-87`
  ```python
  for tok in re.findall(r"[a-z0-9']+", str(text or "").casefold()):
      tok = tok.strip("'")
      if len(tok) >= 3 and tok not in _ling("_DECL_STOPWORDS"):
  ```
- **Scenario:** a Japanese declaration yields no tokens (a Latin name at most), so
  `_declaration_units` drops every unit (`< 2` tokens) and `_reconcile_interpretation`
  (`director.py:2851`, live on every interpret) never warns. The ja pack's
  `_DECL_STOPWORDS` is the English list verbatim and its `_CLAUSE_SPLIT_RE` has Japanese
  splitters -- the route exists and is unreachable. `tests/test_firewall_across_scripts.py:188`
  asserts only that a Japanese quote does not raise.
- **Confidence:** CONFIRMED by reading.
- **Severity:** SILENT-NOOP (a warn-only detector; low value per its own measurement, 3 flags
  / 0 real on the paragraph run).
- **Fix:** Unicode tokens (`[^\W_]+`) plus a pack-supplied segmentation for unspaced
  scripts, or document the detector as English-only and skip it for other packs.
- **Test:** a ja input whose clause no row covers produces the coverage warning.

### F16 — The restraint block's carry exemption reads only the standing ledger

- **Where:** `agents/director_floors.py:951-952`
  ```python
  if (sc.get("contained") or {}).get(who):
      continue
  ```
- **Scenario:** a bound body is picked up THIS beat: the diff carries `containment:
  {Hinami: {in: "Ogre"}}` and the Ogre's walk. The floor sees no standing carry, pops
  Hinami's position and records a refusal, while the merge derives her room from her
  carrier (`spatial_containment.derive_contained_positions`) and she moves anyway: a
  `movement_refused` row and a warning that the world contradicts. The docstring says
  "Being CARRIED somewhere while restrained is legitimate".
- **Confidence:** PLAUSIBLE (read, not executed through the merge).
- **Severity:** WRONG-SCENE (minor: a false refusal record).
- **Fix:** also exempt a body this diff's `containment` puts in a holder's keeping.
- **Test:** restrained body with a same-beat containment record + position change -> not
  blocked.

### F17 — Repair-pass failures recorded nowhere, or only on the record

- **Where:** `agents/director_repair.py:1644-1647` (re-check of the repaired draft):
  ```python
  try:
      bad = native_failures(repaired, sc, payload)
  except Exception:
      bad = []
  ```
  -- no record key, no warning; if it raises, writes the engine would discard are not
  dropped here and nothing says the check did not run. `:1521-1525` (`native_failures` on
  the draft) and `:1562-1565` (`explain_wrong`) record `native_failed` / `explain_failed`
  on the step record only, with no `ctx.add_warning`, unlike the Jev failure at `:1534-1539`.
  `_native_errors` (`:355-366`) swallows `TypeError/ValueError` (harmless: falls back to the
  generic detail).
- **Confidence:** CONFIRMED by reading.
- **Severity:** SILENT-NOOP.
- **Fix:** record `recheck_native_failed` and warn in all three, as the Jev branch does.
- **Test:** stub `native_failures` to raise on the second call; assert a warning and a
  record key.

### F18 — Dead and inert code (question 1)

Each confirmed by AST index + `grep -rw` over the repo (`.py/.js/.json/.md`, tests, tools,
extensions, string forms):

| Symbol | Where | State |
|---|---|---|
| `_concealment_forms` | `director_floors.py:2134` | no caller anywhere; replaced by `_bodies_of`/`_canonical_conceal_forms`, still cited by two docstrings (`:2173`, `:2195`) |
| `_VERDICTS_WITHOUT_CONTENT` | `director_fanout.py:991` | never read |
| `_RECONCILE_MAX_MANIFEST_ITEMS` | `director_evidence.py:2441` | "Kept for its importers": the only importer is the facade's import line (`director.py`), nothing reads it |
| `beat_ledger` | `director_evidence.py:1873` | no call anywhere, tests included (`world.beat_ledger` the KEY is a different thing) |
| `span_pairings`, `span_colocations`, `_record_place` | `director_evidence.py:976`, `:1750`, `:937` | tests only (`test_director_orchestration.py:1667-1697`) |
| `changes_asserted` manifest path: `_manifest_items`, `_fold_derived_manifest_events`, `_subject_is_registered_body`, `_DERIVED_OF_ATTIRE`, `_span_id_ceiling`; `director_fanout._specialist_manifest_slice` | `director_evidence.py:3894-4107`; `director_fanout.py:269` | called every beat, input always empty: no stage, card or code writes `changes_asserted` (only `offscreen_beat.py:103` writes `[]`); `_manifest_items` -> `[]`, so the fold, the slice and the id offset do nothing |
| `span_owners`' forwarding arm | `director_fanout.py:360-364` (`item.get("_forwarded_to")`) | no writer since the forwarding round was deleted |
| `_specialist_payload`'s dialogue arm | `director_fanout.py:628-629` | the payload's view is always built from an empty output (`_resolve_beat_view({"ledgers": []}, ...)`, `director.py:6258`; `_interpret_beat_view(ctx, {}, ...)`, `:2117`), so `view["dialogue"]` is always `[]` |
| View keys `declared_actions`, `dice`, `prose`, `source` | `director_fanout.py:165-196`, `:238-266` | no reader in the repo; `dialogue` read only by the dead arm above |
| Verdict vocabulary other than `encoded`; `reroute_to` | `director_fanout.py:977-978`, `:1079-1082`, `:1102-1103` | `director_prose.dispatch.answer_for` (`director_prose.py:5096-5122`) emits only `encoded`/`""`; see Already registered (§1.1 item 11) |
| `_SUBJECTLESS_CHANNELS` | `director_evidence.py:518` | read only by `tests/test_director_diff_channels.py` -- by design (the classification the drift test enforces); not dead |

`director_fanout.py` itself is LIVE: `_resolve_beat_view`, `_interpret_beat_view`,
`_specialist_payload` (every owner's slice of the encoder payload, via
`director_prose.encoder_payload` and `_room_payload`), `_beat_rooms`, `_grid_view`,
`_anchor_names`, `addressed_house`, `_time_of_day_beside`, `_stage_container`,
`_stage_state`, `_normalized_channel_value`, `_granted_event_ids`,
`_resolved_event_verdicts`, `_index_addressed_events` all have live callers in
`director._run_specialists` / `director_resolve` / `director_prose`. Its name and docstring
describe the deleted fan-out; its content is the encoder's payload builder.

Also inert on the live path (registered as skipped, §1.1 item 3, not a new finding):
`_evidence_present` (359 lines), `_omission_subject_encoded`, `_subject_match_forms`,
`_merge_repair_into_diff`, `_diff_is_substantive`, `_reconcile_scene_slice` run only inside
`_reconcile_resolution`, which runs only when the encoder returned NO rows -- and then
`_span_items(out)` and `_manifest_items(out)` are both empty, so `_evidence_present` checks
nothing. Reachable today only through `tools/echo_derivable.py` and tests.

- **Severity:** DEAD. **Confidence:** CONFIRMED.
- **Fix:** cut the first five rows; decide the manifest path (cut, or keep explicitly for
  replaying pre-2026-09-10 variants -- note that a rerun re-authors, so no live path feeds a
  stored `changes_asserted` back through it); cut the forwarding/dialogue arms and the
  unread view keys.

### F19 — Comments and docstrings that describe behaviour the code no longer has

| Where | Says | Code does |
|---|---|---|
| `director_evidence.py:3824-3826` (`_category_names`) | `_split_joined_categories` "still refuses to split a string unless EVERY part routes" | it splits when ANY part routes (`:3796`, whose own comment says "THE RULE USED TO BE `all`") |
| `director_evidence.py:3742`, `:3826` | unknown names reach `_unrouted_rulings` "to be reported" | `_unrouted_rulings` exists nowhere; an unknown category is now silently unrouted (on the prose path categories are code-derived channel names, `director_prose.ledger_from_events`, so this tolerance defends a deleted producer) |
| `director_evidence.py:2945-2949` | authority is "never read back off the row" | `:2952` falls back to the row's value, and `worldly` reads only the row (F10) |
| `director_evidence.py:2551-2558` (`QUOTED_LINE_CARRIED`) | a re-punctuated line "is never said twice" | the lift stage says it twice (F5) |
| `director_evidence.py:3202` (`causal_world_index`) | targets resolved by `_specialist_payload`'s `target_matches` | no `target_matches` anywhere |
| `director_evidence.py:1001-1003` | "Which hand owns each delegated channel ... Filled from `director_scopes` by the caller" | orphaned `#:` comment: no such constant; it sits above `_DURABLE_RECORD_FIELDS`' own comment |
| `director_evidence.py:1112-1144` (CAUSALITY RECOMPILER) | "the five hands RESOLVE them in parallel"; lists `span_pairings`, `span_colocations`, `beat_ledger` | hands deleted 2026-09-27; those three are test-only/dead (F18) |
| `director_evidence.py:1-9` (module docstring) | "the numbered `changes_asserted` manifest"; the seams "share only `_norm_subject`" | no producer of `changes_asserted`; `_norm_subject` is defined twice, here (`:679`) and in `director_floors.py:302` |
| `director_floors.py:2173`, `:2195` | refer to `_concealment_forms`' answer | dead helper (F18) |
| `director_floors.py:105`, `:400`, `:1217` | the floors "feed the Tier-2 self-repair" | the Tier-2 repair runs only on a beat with no rows (`director.py:3518-3525`) |
| `director_fanout.py:1-7`, `:50`, `:205` | "The Director fan-out's deterministic frame"; views "as every resolve/interpret-side specialist reads it" | no specialists; the views feed the encoder payload and `_run_specialists`' slicing |
| `director_fanout.py:1031-1062` (`_resolved_event_verdicts`) | specialist measurements, `not_mine`/`reroute_to` handling | only `encoded` can arrive (registered §1.1 item 11) |

- **Severity:** STALE-DOC. **Confidence:** CONFIRMED (each checked against the code cited).
- **Fix:** rewrite each to the current behaviour in the commit that touches it.

### F20 — AGENTS.md and Design.md describe the awareness/restraint floors as working; the live path skips them

- **Where:** `AGENTS.md:492` ("the deterministic exits are the player's own declaration, a
  deliberate rouse ... and a full sleep on the simulation clock"), `AGENTS.md:493` ("The
  engine ends only two things -- a hold whose holder is POSITIVELY elsewhere ... and a
  completed release the Director's own `resolved_event` asserts"; "`_untracked_restraint_subjects`
  / `_scan_for_untracked_restraint` for prose the diff forgot"); `Design.md:554` ("A gate
  that can be entered can be left -- **Built**"), `Design.md:555` ("A collapse gates the
  body that collapsed -- **Built**"). Also `story/scene.py:1891` and
  `persist/commit_entities.py:244` name `_awareness_exits` as what ends a gate.
- **Code:** `_awareness_exits`, `_restraint_exits`, `_unsupported_player_awareness`,
  `_unsupported_character_awareness`, `_untracked_*`, `_narrated_destruction_subjects` are
  called only from `_reconcile_resolution` (`director.py:3203-3375`), which runs only
  `if not out.get("causal_ledger")` (`director.py:7793`) -- never on a prose beat with rows.
  `Design.md:467` already says so ("the Director's waking floors run only on a beat with no
  encoded rows"), so the two tables contradict each other.
- **Confidence:** CONFIRMED. The underlying skip is registered (UNBUILT_PIPELINE §1.1 item
  3); the doc rows are not.
- **Severity:** STALE-DOC.
- **Fix:** qualify rows 492/493 and Design.md 554/555 with "on a beat with no encoded rows
  only; see UNBUILT_PIPELINE §1.1 item 3".

## Efficiency

### E1 — The repair pass recomputes sentence attribution 7-18 times per stage, each O(events x sentences) SequenceMatcher calls

- **Where:** `agents/director_repair.py:279-302` (`attribute`, whose `_holds` at `:233-242`
  runs `difflib.SequenceMatcher(...).find_longest_match` for EVERY (event, sentence) pair)
  and its callers on the SAME `(events, units)`: `_check_and_repair` `:1504` (`citations`),
  `battery` `:656`, `jev_state` `:585`, `declared_gaps` `:482`, `bridge(...citations(...))`
  `:1548`, `explain_wrong` -> `jev_state` `:1243`, `call_repair` `:961` + `_draft` `:861`
  (x2 groups x first/retry), `place` `:1323`, re-check `battery` + `jev_state` `:1661-1668`,
  `_declared_left` `:1687`.
- **Hotness:** every interpret and resolve with the repair on (default ON). Measured on a
  realistic beat (3,354-char account, 36 sentences, 17 events): 71 ms per `attribute()` ->
  ~0.5 s per stage with no jobs (7 calls), ~1.3 s with jobs and retries (18 calls); 176 ms
  per call at 30 events x 40 sentences. cProfile: `_holds`/`find_longest_match` dominate.
- **Gain / fix (cheap, output-identical):** compute `attribute`/`citations` once per events
  version and pass them through; and prefilter `_holds` with an exact bound -- a common run
  of length m puts m-2 of the sentence's trigram POSITIONS in the event's trigram set, so
  skip SequenceMatcher when that count is below `ATTRIBUTION_HOLDS*len - 2`. Expect >10x.

### E2 — Mint placement replays the beat and then merges the same diff again

- **Where:** `agents/director.py:7277-7282` with `director_evidence.beat_worlds`
  (`director_evidence.py:1841-1870`): N step merges, then
  `merge_scene_with_diff(sc, _rsd)` from scratch for `final_world`, which is exactly the
  world after `beat_worlds`' last step (computed and discarded inside its loop).
- **Hotness:** only beats with an unplaced mint; one merge is ~11 ms on a 38-room scene
  (`route_scene_for`'s own measurement).
- **Fix:** have `beat_worlds` return the final world too. Saves one merge per such beat.

### E3 — `_stand_up_plans_placed_by_name` is O(positions x plans x aliases) per resolve

- **Where:** `agents/director_floors.py:1825-1833` -- for every positions key (scene + diff)
  it recomputes `_bare_person_name` over every planned figure and alias (each call a
  function-local `from persist.commit import strip_name_titles` + split).
- **Hotness:** every resolve. Measured 49.6 ms at 300 positions x 40 plans; today's stored
  scenes are small (largest has 18 entities / 16 positions, read-only count on `engine.db`),
  so ~ms now -- a scaling note for charter towns.
- **Fix:** build `{bare name -> plans}` once per call.

### E4 — Three `world_conditions` SELECTs per stage for three views

- **Where:** `_awareness_view` -> `story.scene.awareness_conditions`, `_conditions_view` ->
  `active_condition_rows`, and the restraint view's `restraint_conditions`, each
  `SELECT ... FROM world_conditions WHERE chat_id=? AND active=1`, at interpret
  (`director.py:2075-2083`) and resolve (`:5903-5914`): six queries per beat for one row set.
- **Fix:** one query per stage feeding all three. Small gain.

### E5 — `_restraint_holder_in` compiles a regex per pool name per restraint record

- **Where:** `agents/director_floors.py:870-877` -- `re.finditer(name_boundary_pattern(...))`
  for every name in `_restraint_holder_pool` (every positions key, every entity name AND id),
  per live restraint record, in `_restraint_view` (both stages) and `_block_restrained_moves`
  (every resolve). A large pool thrashes `re`'s 512-pattern cache.
- **Fix:** prefilter with `label.casefold() in by` before compiling. Small at today's scale.

## Already registered

- **The prose-reading resolve floors are skipped on every beat with rows** -- UNBUILT_PIPELINE
  §1.1 item 3 (awareness onset drops, waking exits, prose-asserted releases,
  unconsciousness / untracked-restraint / destruction scans, player-claim findings).
  *Nuance for the register:* two of the three waking exits (`_awareness_exits` rule 1, the
  player's own declaration; rule 3, eight hours on the clock) and the restraint exit's
  rule 1 (holder positively gone) read only state -- the player's input, the clock,
  positions and the awareness map -- so they meet the register's own criterion for the
  "STATE-ONLY floors [that] run on every beat since 2026-09-28" and could move with them
  without a prose-FP measurement. F11 is a defect in one of the skipped floors.
- **`fact_adjudications` is never written; `_audit_fact_adjudications`
  (`director_views.py:251`) warns on every player world assertion** -- §1.1 item 7 (strict
  xfail `tests/test_director_obligations.py::test_adjudicated_event_claim_passes`).
- **Every interpret builds all five world views** -- §1.1 item 9; `_lazy_view`'s docstring
  (`director_views.py:525-541`) still claims the C8 saving.
- **Ledger-notes layer and verdict branches** -- §1.1 item 11 ("the views still carry a
  `ledger_notes` nothing on the prose path writes"; "the `required_channels` and verdict
  branches ... trace before cutting"). Traced here: `director_prose.dispatch.answer_for`
  (`director_prose.py:5096-5122`) emits status `encoded` or `""` only and never
  `reroute_to`; `_run_specialists` turns `""` into no receipt; so `_EVENT_VERDICTS` members
  `already_true`/`not_mine`/`no_referent`, the `reroute_to` arms of
  `_resolved_event_verdicts`/`_index_addressed_events`, and `_normalized_ledger_notes`
  (`director_fanout.py:33`) are unreachable on the live path.
- **Hard player authority / a player's world assertion filed as their own act** -- §1.1
  item 1 (related to, but distinct from, F10, which concerns engine-world sources).
- **The last-list slip in the JSON ladder** -- §1.214 (not in these files; F7-F9 are the
  same class one rung over in `director_repair`).
- **English role-noun residual** ("hostler" vs stablehand) -- UNBUILT_LIVING_WORLD
  replay residuals (line ~2952); F13 is the separate non-ASCII gap.
- **Concealment from background presences** -- UNBUILT_PERCEPTION §3.2 (X3 closed, X7 half
  open); F2's extension is the name-resolution side of the same surface.

## Structure notes

### Liveness map (question 1)

- `director_fanout.py`: live (encoder payload builder + view builders + `_run_specialists`
  helpers); dead remnants listed in F18.
- `director_floors.py`: live on every beat -- `_restraint_blocked_moves`/`_hold_is_live`/
  `_restraint_holder_pool` (via `_block_restrained_moves` and `_travel_continues`),
  `_awareness_view`, `_conditions_view`, `_restraint_view`, the concealment floors, the
  identity floors (`_bind_minted_entities_to_present_figures`, `_stand_touching_figures`,
  `_stand_up_plans_placed_by_name`, `_refuse_minted_cast_doubles`), mint placement. Live
  only on no-row beats: every prose-reading floor (see F20). Dead: `_concealment_forms`.
- `director_evidence.py`: live -- diff shape, placeholder strip, speech rows
  (`row_is_spoken`, `restore_declared_quotes`, `speech_transforms`), `normalize_causal_ledger`,
  `causal_*` index builders, the recompiler pieces `span_records`, `beat_worlds`,
  `item_survivors`, `apply_item_transforms`, `single_span_attributions`, `span_mint_rooms`,
  `span_result_findings`, `beat_timeline`/`beat_event_ledger`, `mover_cut_events`
  (perception), `voided_span_ids`/`void_span_records`. No-row-beat only: the omission
  evidence block. Dead/inert: F18.
- `director_repair.py`: all live when the repair is on (default).
- `director_views.py`, `director_contact.py`: all live.

### Prose-reading regexes and word lists (question 2)

| Where | Reads | Language route | Verdict |
|---|---|---|---|
| `director_evidence.py:83` `[a-z0-9']+` | player input | `_DECL_STOPWORDS` via `_ling` (ja = English copy) | ASCII-only (F15) |
| `director_evidence.py:96-98` `_QUOTED_UNIT_RE`, `_CLAUSE_SPLIT_RE` | player input | `_ling`, ja has 「」 and Japanese splitters | routed, but feeds the ASCII tokenizer |
| `director_evidence.py:882` `_OMISSION_CATEGORY_ALIASES` | category names | `_ling` | engine vocabulary (code-derived on the prose path) |
| `director_evidence.py:2340` `\b%s\b` over manifest `change` | legacy manifest prose | none | English word boundary; dead path (F18) |
| `director_evidence.py:2479`, `:2549` quote marks | ledger rows / input | punctuation incl. 「」 | `『』` absent from both (repair's `_OPENERS` has it) |
| `director_evidence.py:2564` `[^\W_]+` | quoted lines | Unicode | for unspaced ja a line is one "word": word share degrades to exact-run match; `QUOTED_LINE_CARRIED` measured on English |
| `director_evidence.py:2581` `_SENTENCE_END` | input | includes 。！？ | both |
| `director_evidence.py:2688`, `:2698` residual strip | act rows | `"`/`“”` only | leaves 「 」 (F5) |
| `director_evidence.py:3755` `[,;/|]|\band\b` | category strings | none | English "and"; legacy-only (categories code-derived now) |
| `director_floors.py:57-66` `_RESTRAINT_KEYWORDS` | resolved prose | `_ling`, ja cues present | gated (no-row beats) |
| `director_floors.py:138-141` breaks + `([a-z]+)$` abbreviation check | prose | `_TITLE_ABBREV` via `_ling` | ja adds 博士/先生/... which the ASCII regex can never match (dead entries, harmless) |
| `director_floors.py:181,368,370,517,776` `_SLEEP_CUE`, `_UNCONSCIOUSNESS_CUE`, `_ROUSE_CUE`, `_STAY_UNDER_CUE` | prose / input | `_ling`, both | gated, except `_ROUSE_CUE` via `_awareness_view` (payload hint) |
| `director_floors.py:483,1053,1064,1073` `\w+` word gaps | prose | Unicode | in unspaced ja the gap counts runs, so `_MAX_UNCONSCIOUSNESS_GAP`/`_MAX_RELEASE_OBJECT_GAP` bound nothing within a sentence |
| `director_floors.py:1040-1077` `_RELEASE_*` | resolved prose | `_ling`, both | possessive exclusion English-only and subject-side only (F11); gated |
| `director_floors.py:1243-1248` destruction pattern | resolved prose | cues via `_ling`; English determiners optional (documented) | gated |
| `director_floors.py:1564-1582` `_FIGURE_STOPWORDS`, `[^a-z0-9]+` | mint labels, roles | none | ASCII/English-only (F13) |
| `director_floors.py:1966` `[^a-z0-9]+` over `kind` | free-text kind | none | compared to engine-owned English `_ANIMATE_ENTITY_KINDS`; a non-English kind never reads animate |
| `director_views.py:460,484,506` `_AMBIGUOUS_NAME_WORDS`, `_NARRATION_QUOTE_RE`, `(?<![A-Za-z])` | resolved_event | `_ling` (agents.common), both | English-only BY STATED DESIGN (docstring: "quiet for a language that marks address with a suffix") |
| `director_views.py:351` containment | dialogue targets | n/a | F12 |
| `director_contact.py:536` `("self", "you")` | model-written material `target` | none | English literal; a ja `自分` is not mapped to the actor and the effect may fail to resolve |
| `director_contact.py:45` -> `world/spatial_contacts.contact_is_momentary` -> `CONTACT_MOMENTARY_MANNERS` (`spatial_contacts.py:83-91`) | free-text `manner` | none | English word list on prose, no route: a ja strike/kiss is never momentary and stays standing topology (outside these files; flag to the world/spatial auditor) |
| `director_repair.py:95-98` stops / openers | prose | includes 。！？「」『』 | both |
| `director_repair.py:586-597` Jev state labels | n/a | English scaffolding | consistent with `director_prose._jev_state`; questions are localised (`prose_contract_text(..., language)`) |

### Monoliths in miniature

`_evidence_present` 359 lines (no-row beats only), `_specialist_payload` 320,
`causal_world_index` 315, `normalize_causal_ledger` 288,
`_bind_minted_entities_to_present_figures` 278, `_check_and_repair` 183,
`restore_declared_quotes` 151, `_resolve_beat_view` 143, `resolve_concealment_refs` 123.

### Natural seams (for the split program)

- `director_evidence.py` has seven cohesive blocks: interpret coverage (75-206); diff shape
  + channel tables + placeholder strip (209-563); omission evidence (`_norm_subject`
  through `_subject_is_somewhere`, 679-934, plus `_evidence_present` 2076-2434) -- the
  block only `_reconcile_resolution` reads; the causality recompiler (937-2073: item
  transforms, timeline/event ledger, span records/slices/worlds, survivors); speech rows
  (2444-2780: `row_is_spoken`, quotes, `restore_declared_quotes`); the causal ledger
  normaliser + world index (2783-3509); spans/categories/manifest (3514-4107). The
  omission-evidence block is the obvious leaf to move first (its only live importer is
  `director_reconcile`).
- `director_floors.py`: awareness (35-833), restraint (835-1180), omission scans +
  destruction (1183-1330, 1543-1561), mint placement (1331-1540, 1611-1628), identity binding
  (1564-1610, 1629-2132), concealment (2134-2468), cast doubles (2471-2548).
- `director_fanout.py`: views (33-266), slicing/ownership (269-365), owner payload slices
  (368-922), stage containers (923-975), verdict echo (977-1121, mostly vestigial).

### Module-level state

- Mutable dicts with no writers anywhere: `director_evidence._NON_SUBSTANTIVE_CHANNELS`,
  `_SUBJECT_KEYED_CHANNELS`, `_SUBJECT_OP_CHANNELS`, `_CHANNEL_WORD_SUBJECTS`,
  `_SUBJECTLESS_CHANNELS`; `director_repair._OPENERS`, `_AT`. No `global` statement in any
  of the six files.
- `director_repair._AT` (`:751`) binds `MISSING_EVENT_AT`/`MISSING_LEDGER_AT`/
  `WRONG_LEDGER_AT` at import, and `findings()` reads `_AT`: patching the named thresholds
  (they are documented as the owner's) would change nothing. Nothing patches them today.
- `director_evidence._OUTPUT_FIELD_NAMES` is computed at import from the schemas (import
  side effect; cheap).

### Other

- `_norm_subject` is defined twice (`director_evidence.py:679`, `director_floors.py:302`,
  both `fold_identity_key`); `director.py` imports both names, the second binding wins.
- `director_repair.native_failures` (`:375`) and `director_prose` (`:220`) import
  `agents.director` function-locally. They are outside the facade family that
  `tools/project_check.py:facade_siblings` derives (`director_repair` is not imported by
  `director.py`), and `facade_import_violations` checks only absolute imports
  (`node.level == 0`, `project_check.py:1666`), so a relative `from . import director`
  inside a family sibling would not be caught either (tooling gap; outside this audit).
- Function-local imports of private names across packages:
  `persist.commit._INERT_ENTITY_KINDS`, `llm.schemas._ANIMATE_ENTITY_KINDS`
  (`director_floors.py:1899-1900`), `persist.commit.strip_name_titles` per call
  (`:1607`).
- Caps: `MAX_JOBS = 12` (named), `before_lines` `[:80]` and `_SHOWN = 280` (named/visible),
  `_CONDITIONS_VIEW_CAP = 40` (named), `addressed_house(cap=40)`; `public_sources[:20]` and
  `dialogue[:20]` are bare literals (F14). Jobs past `MAX_JOBS` are dropped with no warning
  (visible only as `record["found"]` vs `record["jobs"]`).

## Docs checked

| Claim | Held? |
|---|---|
| AGENTS.md:427-428 -- `director_fanout.py` holds "the beat views and `_specialist_payload`, the owners' world slices the encoder's payload is built from" | Holds |
| AGENTS.md:290 / director_repair docstring -- repair ON unless `prose_contract_repair` is `0/false/off` | Holds (`enabled()`, `:101-104`) |
| AGENTS.md:298 -- causal Director, co-hands, forwarding and verdicts deleted | Holds for the hands; vestiges remain (F18, §1.1 item 11) |
| AGENTS.md:444 -- every public source keeps a fallback record | Partly: sources past 20 are cut first (F14) |
| AGENTS.md:492-493 -- awareness/restraint exits and scans are the engine's mechanism | Not on prose beats (F20; skip registered §1.1 item 3) |
| AGENTS.md:853 -- a dropped quoted line is judged by word share, then lifted or stood where she said it | The lift stage judges by exact body and substring (F5) |
| AGENTS.md:856 -- `_route_authorial_npc_beat` reroutes a player-authored NPC interior/autonomous outcome to an offer | Holds (`director_views.py:114-167`) |
| Design.md:467 -- waking floors run only on no-row beats | Holds; contradicts rows 554/555 |
| Design.md:554/555 -- "Built" | Built but skipped on the live path (F20) |
| CLAUDE.md -- every deterministic floor judges the MERGED diff | Holds for the state-only floors (`_block_restrained_moves`, placeholder strip, articulation, scale conflicts, identity floors, cast doubles at resolve); the prose-reading ones do not run (registered) |
| CLAUDE.md -- a leak is an engine failure; the floor must not depend on a model cooperating | Violated by F1 (non-canonical `visibility` publishes) and F2 (alias at interpret) |
| `director_lingua._ling` -- "THE ONLY WAY THE DIRECTOR READS A CUE" | Holds for the cue tables; not for the ASCII tokenisers and English lists in F13/F15 and the table above |
| `director_floors` docstring -- "the deterministic prose-vs-diff floors of the Director's resolve seam" | Most are prose-reading floors that the resolve seam now skips (F20) |
