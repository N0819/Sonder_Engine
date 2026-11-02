# Audit — story/attire.py, story/importers.py, story/greetings.py, story/room_bible.py, story/room_citations.py, story/history_routing.py

Auditor: story_attire_import. Tree: branch `worktree-jev-character-tracking` at `84f3de23`, read 2026-11-01.
All snippets ran on `.venv/bin/python`, in memory; nothing touched `engine.db` or any repo `*.db`
(the two snippets that reach a DB writer stub `qi`/`db` in-process). No test files were run.

## Scope read

Read in full, every line:
- `story/attire.py` 1-3699
- `story/importers.py` 1-3300
- `story/greetings.py` 1-1340
- `story/room_bible.py` 1-447
- `story/room_citations.py` 1-221
- `story/history_routing.py` 1-215

Read in part, to trace callers and consequences (not audited):
- `persist/commit_attire.py` 250-370 (`interpret_attire_notes`), 675-800 (`_mint_shed_garments`), 889-915 (`_sanitized_wearing`), 1110-1700 (write gate, wholesale restatement, `apply_flat_change` call, guessed-span report)
- `world/spatial_containment.py` 1620-1665 (shed-garment key reservation); `world/spatial_listener.py` 150-185, 375-392
- `agents/common_bodies.py` 160-215, 340-360, 425-480; `agents/skip_stage.py` 395-495; `agents/skip_work.py` 133-255
- `agents/director.py` 455-500, 6700-6735; `agents/common_sequence.py` 1215-1245; `agents/mapping.py` 668
- `story/room_tools.py` 140-220; `story/room_conversation.py` 375-395; `story/prelude.py` 140-165; `web/app.py` 2570-2600, 3215-3230, 3495-3520, 3660-3680, 3860-3915
- `static/js/editors.js` 960-1050; `static/js/lorebooks.js` 3285-3390
- `mind/memory_lore_entries.py` 108-160; `core/db.py` 2350-2362; `core/jobs.py` 91-150
- prompts: en `greeting_interpret.txt`, `lore_reinterpret.txt`, `promote_character.txt` (field list), `encoder/attire.txt` 1-12; ja `greeting_interpret.txt` (player-word clause)
- tests: `test_greeting_minds.py` 100-140, 275-312; `test_room_cites_what_it_read.py` (test list); `test_attire_displacement.py` 195-225; `test_attire_regions.py` 1240-1275; `test_lore_structure.py` (test list); `test_import_macros.py` 1-40; `test_greetings.py` 690-740
- registers grepped for every symbol below: `docs/UNBUILT*.md`; designs `DESIGN_GREETING_MINDS.md` 100-225, `GREETING_IMPORT_DESIGN.md` 34-42

## Findings

### F1 — Heuristic card import puts the card's description, secrets included, into the body's VISIBLE summary (and in Japanese, all of it)

- **Where:** `story/importers.py:433-436` (`heuristic_character_sheet`), `:656-659` (`import_persona`), sentence splitter `:259-264`.
  ```python
  sheet["embodiment"]["visible"]["summary"] = (
      _first_sentences(desc, 3)
      or "A person of unremarkable appearance."
  )
  ...
  parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
  ```
- **Failure:** a SillyTavern `description` mixes appearance, backstory and secrets in any order. The first three sentences become `embodiment.visible.summary` — the "stable body appearance" (CLAUDE.md) that every observer is delivered: it feeds `_unknown_actor_label` (`agents/common_identity.py:212,434`), background presences' views of bodies (`agents/background.py:353,2186,2269,2423`) and the narrator's body facts (`agents/narration.py:2431`). The splitter knows only `.!?` + whitespace, so a Japanese description (`。`, no spaces) is one "sentence" and the WHOLE description becomes the visible body.
- **Verified:** CONFIRMED, snippet:
  ```
  h({'name':'Aria','description':'Aria is a 23-year-old mage. She secretly spies for the thieves guild and has told no one. Silver hair, blue eyes. Lost her family young.'})
  -> visible.summary 'Aria is a 23-year-old mage. She secretly spies for the thieves guild and has told no one. Silver hair, blue eyes.'
  h({'name':'アリア','description':'アリアは二十三歳の魔術師。銀髪で青い瞳。実は盗賊ギルドの密偵であり、誰にも正体を明かしていない。幼い頃に家族を失った。'})
  -> visible.summary = the entire description, secret included
  ```
  Path: import route `web/app.py:3503-3516` with `reinterpret=false` (the checkbox is on by default, `static/js/editors.js:1002`, so this is the opt-out path, but it is a supported one and the persona path is identical).
- **Severity:** LEAK (a mind's secret delivered to every observer and to the player's page). Not registered (UNBUILT_CHARACTERS §2.3 is about sparse psychology, not this).
- **Fix:** never derive the visible summary from free description prose by position: leave the placeholder plus a `character_card_warnings` line pointing at the appearance fill, or keep the description in `knowledge.private_history`/`self_model` and let `fill_appearance` write the body. Test: heuristic import of a description whose second sentence is a secret leaves `visible.summary` without it; a `。`-punctuated description does not land whole in the summary.

### F2 — The greeting extractor force-reveals every seed naming `{{PLAYER}}`, and the only mind that flag affects is the player's, where it widens the page

- **Where:** `story/greetings.py:146-157` (`extract_greeting`), sole reader `:526` (`_seed_player_mind`).
  ```python
  for mind in out.get("minds") or []:
      for seed in (mind or {}).get("knowledge_seeds") or []:
          if PLAYER_TOKEN in str(seed.get("content", "")):
              seed["revealed_in_prose"] = True
  ...
  if not seed.get("revealed_in_prose"):
      refused.append("unrevealed player-mind item withheld: ...")
  ```
- **Failure:** `revealed_in_prose` is read in exactly one place (grep: `greetings.py:526`). For character minds `_route_mind_memories` writes every seed to private memory regardless, so the forced flag is a no-op there and the comment ("can't be routed as private-from-the-player") describes a routing that no longer exists. For the PLAYER mind, the flag is the admission gate to `persona_private_history`, the one player-readable store, and the design states why implied items are refused there: "a guess can embed another mind's secret in its phrasing" (`DESIGN_GREETING_MINDS.md` §revealed_in_prose point 2). Point 3's forced reveal overrides point 2 for any player-mind seed that names the slot: `{"who":"{{PLAYER}}", "knowledge_seeds":[{"content":"{{PLAYER}} drank the tea the innkeeper poisoned","revealed_in_prose":false}]}` is flipped to revealed and written into the panel the player opens. The prompt asks for first person (so a compliant model rarely writes the token in a player seed); the module's own docstring (`:64-75`) records models ignoring exactly this token instruction, and "a leak that only a cooperative model avoids IS a leak".
- **Verified:** path CONFIRMED by grep (single reader) and trace; frequency PLAUSIBLE. `tests/test_greeting_minds.py:111-135` pins the forced reveal on a non-player mind only; the player-mind refusal test (`:292-310`) uses content without the token, so the interaction is untested.
- **Severity:** LEAK. Not registered (UNBUILT_PIPELINE §6.3 cites the forced reveal as a strength).
- **Fix:** apply the guard to non-player minds only (where it is inert, so delete it) and never upgrade an implied player-mind item; update `DESIGN_GREETING_MINDS.md` point 3. Test: a player-mind seed `"{{PLAYER}} drank the poisoned tea"` with `revealed_in_prose: false` is refused and recorded.

### F3 — `coarsen_region_surface` removes a description only up to its first `;`, so the rest of it reaches an observer who cannot resolve detail

- **Where:** `story/attire.py:2876-2888`; caller `agents/common_bodies.py:475-477` (the scale-acuity subtraction).
  ```python
  _SURFACE_DETAIL_TAIL = re.compile(r"\s+—\s+[^;]*")
  return _SURFACE_DETAIL_TAIL.sub("", str(surface or "")).strip()
  ```
- **Failure:** `;` is both the surface grammar's part separator and an ordinary character in authored text (`_clean` keeps it; `_compact_garment_piece:3539` even cuts looks at `;` because descriptions contain it). A garment description or a region's `beneath` text with a `;` keeps everything after it through the coarsening.
- **Verified:** CONFIRMED, snippet: description `"black wool; a regimental crest stitched over the heart"` -> perceptible `'greatcoat — black wool; a regimental crest stitched over the heart'` -> coarse `'greatcoat; a regimental crest stitched over the heart'`.
- **Severity:** LEAK (detail past a perception subtraction; small). Not registered.
- **Fix:** produce the coarse surface from the structured record (a `coarse=True` mode of `perceptible_region_surfaces` that simply omits descriptions and `beneath`) instead of regex-stripping rendered text. Test: a description containing `;` yields a coarse surface that names only the garment.

### F4 — A `wearing` restatement with a short handle forks the garment: the worn one is reported removed (and minted on the floor) and a second one is put on

- **Where:** `story/attire.py:3159-3182` (`apply_flat_change`), with the commit path `persist/commit_attire.py:1360-1363` (gate resolves WITH the head-noun tier), `:1424-1427` (`cur["wearing"]` = the raw handles), `:1594` (`apply_flat_change(_before, cur["wearing"], ...)`).
  ```python
  # Without it, a beat naming the robe by a shorter phrase read as "the robe is
  # not in the wanted list" (so: start removing it) AND "this wanted garment is
  # not worn" (so: add it) at the same time
  ...
  resolved = resolve_garment(name, worn_names, allow_head_noun=False) or str(name)
  ```
- **Failure:** tiers 1-3 cannot resolve a one-word handle under eight characters (`_CONTAINMENT_FLOOR_*`, `:1316-1317, 1377-1379`), and tier 4 is switched off here. The encoder card tells the model the opposite: "Use the wearer's wardrobe handle -- it need not repeat the full registered name ('robe' finds the one robe she is wearing)" and names `wearing` as a ladder channel (`encoder/attire.txt:3,7`). `remove`/`add`/`replace` resolve with tier 4 (`commit_attire.py:1435-1460`) and the wholesale gate's `_staying` does too, so the gate sees nothing omitted, while the reconcile removes the garment: `newly_removed` reports it and `_mint_shed_garments` makes it a floor object, on a body that is still wearing it under the shorter name. This is the docstring's own measured case, still open for one-word handles.
- **Verified:** CONFIRMED (attire half by snippet, commit half by trace):
  ```
  prev = normalize_regions({'wearing':['sheer obsidian silk robe that parts with every movement','leather sandals']})
  apply_flat_change(prev, ['robe','leather sandals'])
  -> flat_wearing ['robe', 'leather sandals']; newly_removed [('torso', 'sheer obsidian silk robe that parts with every movement')]
  resolve_garment('robe', worn)  # tier 4 on -> 'sheer obsidian silk robe that parts with every movement'
  ```
  Same result for `['blouse', ...]` against `white silk blouse`, and for Japanese `ブラウス` against `白いブラウス`. The opening is protected by `agents/director.py:483-495` (authored outfit restored); every later beat is not.
- **Severity:** CORRUPTION (ledger renames a garment and mints a phantom shed object). Not registered.
- **Fix:** resolve `wanted` once, in one place, with the same tier the gate used (canonicalise `d["wearing"]` through `resolve_garment(..., worn)` in commit, as `replace` already does), so the gate and the reconcile cannot disagree. Test: `apply_flat_change` (or the commit seam) given `wearing: ["robe"]` against the long robe keeps one worn robe and mints nothing.

### F5 — A retried greeting launch re-extracts and re-seeds every mind: beliefs, relationship-ledger rows and the player's private history are appended twice

- **Where:** `story/greetings.py:846-847` (extraction re-run; imported cards store `"extraction": None`), `:1080-1082` (`_seed_minds` called unconditionally on `resume_chat_id`), appends at `:429-430`, `:460-465`, `:537-541`.
  ```python
  interior["beliefs"] = list(interior.get("beliefs") or []) + interior_rows
  ...
  record_relationship_event(chat_id, char_id, target, axis, value, ...)
  ...
  entries.append({"about": player_name, "content": content, "known_by": []})
  ```
- **Failure:** `web/app.py:2570-2595` (`chat_retry_start`) and `story/prelude.py:153-162` resume the same chat. A start that failed after the minds stage (journey history, featured-resident handoff, turn 0 — the chat-128 case the turn-row comment at `:1200-1211` describes) re-runs `_seed_minds`: every interior belief and every relationship-ledger row is written again, and `persona_private_history` gains duplicates. Because the extraction itself is re-run (temperature 0.2), the memory upsert key `greeting_seed:<sha1(content)>` only dedupes byte-identical seeds; a reworded seed lands as a second memory. The comment at `:874-881` ("Every stage below asks the CHAT whether its own work is already there") is false for this stage.
- **Verified:** CONFIRMED, snippet with `db`/graph stubbed in-process, calling `_seed_mind_state` twice as a resume does:
  ```
  interior beliefs after a retry: ['The east lock is broken.', 'The east lock is broken.']
  relationship ledger rows: 2
  ```
- **Severity:** CORRUPTION. Not registered (UNBUILT_PIPELINE §6.3 says a retried launch "updates one row rather than writing a second" — true only for memories with identical content).
- **Fix:** make the stage ask the chat like its siblings — skip when `greeting_minds` already records a claimed card mind for this extractor version — and persist the extraction on the chat so a resume replays it instead of re-asking. Test: `start_story` with a pipeline that raises, then `resume_chat_id`; interior beliefs, ledger rows and persona history counts are unchanged.

### F6 — AI-reinterpreted lorebook import (the UI default) drops the recovered tree and every knowledge field, so its entries reach no mind

- **Where:** `story/importers.py:1880-1901` (structure keyed by SOURCE content), `:1920-1927` (rewrite), `:1958-1973` (exact-key lookup on REWRITTEN content), `:1715, 1766` (`"locked": 0`).
  ```python
  structure[body] = {... "knowledge_tag": tag, ...}       # body = _structure_key(source content)
  ...
  meta = structure.get(_structure_key(entry["content"])) or {}   # entry = rewritten
  ```
- **Failure:** `lore_reinterpret` asks the model to rewrite, merge and split (`lore_reinterpret.txt`). `_structure_key` is the first 120 casefolded characters, and the lookup is exact, so any rewritten opening loses `title`, the `[>]` parent link, `knowledge_tag/range/locations` and `importance`; both halves of a split lose it although `_structure_key`'s docstring says they "legitimately inherit" it (`reinterpret_lorebook._source_for:2044-2052` has the prefix tolerance this path lacks). `add_lore`'s contract: "An entry with NO depth tag reaches no mind: it is Director-only" (`mind/memory_lore_entries.py:121-124`). A source `constant` entry (locked=1) is also rewritten — `reinterpret_lorebook` skips locked rows — and stored unlocked. The import dialog has AI reinterpretation checked by default (`static/js/editors.js:1002`). The better the rewrite, the more is lost; only batches that FAIL (kept unrewritten) keep their structure.
- **Verified:** CONFIRMED structurally, snippet: a two-entry `[castle]`/`[>]` book parsed by `parse_structure`, then three plausible rewrites (one split) -> `structure.get(...)` is `None` for all three. `tests/test_lore_structure.py:136-146` covers only `reinterpret=False`.
- **Severity:** CORRUPTION (+ a floor that subtracts more than its rule: minds lose standing knowledge). Not registered.
- **Fix:** carry the structure through the rewrite by identity rather than text — send each source entry with an index and require the model to echo `source` indices (merge/split keep them), or fall back to `_source_for`'s prefix/keys matching; never send `constant` entries to the rewrite. Test: import the `test_lore_structure` book with a stubbed rewrite that rephrases and splits; every row keeps a title and a `knowledge_tag`, and the constant entry stays locked.

### F7 — `room_bible` is written by read-modify-write from two threads with no lock, and the fold job ignores cancellation

- **Where:** `story/room_bible.py:223-249` (`add_entry`), `:252-274` (`mark_paid`), `:383-434` (`fold`), `:437-447` (`schedule_fold`: `_run(job)` never reads `job.cancelled`).
- **Failure:** the fold runs as a `core/jobs` job keyed `room_bible`; `note_publish`/`note_resolve` run from the planner (`agents/story_planner.py:1189-1206`, `story/room_sketch.py:1220-1223`), which runs under other job keys and can overlap (jobs dedupe per `(chat, key)` only, `core/jobs.py:91-116`). Each writer reads the whole row (`_row`), changes it and writes it back (`_save`); a publish landing between `fold`'s `_row` at `:427` and `_save` at `:432` (or inside `mark_paid`) is lost. A fold cancelled by a restore still files entries and advances `folded_through`.
- **Verified:** PLAUSIBLE (traced; no lock or transaction anywhere in the module; race not reproduced).
- **Severity:** CORRUPTION (a lost `decided`/`paid` line; low frequency).
- **Fix:** wrap each read-modify-write in `core.db.transaction()` (the per-key row is small), and have `_run` return early when `job.cancelled` is set. Test: interleave `note_publish` inside a stubbed fold's `_call` and assert both lines survive.

### F8 — In Japanese, garment handles do not resolve and the write gate refuses almost every undressing

- **Where:** `story/attire.py` — `resolve_garment:1376-1386` (containment floor counts spaces/ASCII length; `\b` cannot fire inside unsegmented text; tier 4 `len(head) <= 3`), `_attributed_scoped:2021-2068` (`_SENTENCE` splits on `.!?\n` only; word set `[a-z0-9\-’']+`; genitive `\b<name>['’]s\b`; single-name `\b<name>\b`), `_CLOTHING_CONTEXT:1238-1254` (English), `garments_named_in:2386-2423` (suffix windows split on spaces; tier (c) uses the ASCII word set).
- **Failure:** `_named_pattern`/`_UNSEGMENTED` (`:2212-2286`) fixed the whole-name case only. Japanese drops modifiers exactly as English does ("ブラウス" for "白いブラウス"), but an unsegmented name has no suffix windows and no ASCII words, so the licence needs the ledger's full spelling in the prose. The subject reading (`wardrobe_change_subjects`) never fires on a Japanese sentence that lacks that spelling: `_CLOTHING_CONTEXT` cannot match, `\bヒナミ\b` fails before a particle, and a paragraph is one "sentence". Meanwhile `resolve_garment("ブラウス", ...)` is `None`, so `remove: ["ブラウス"]` is the no-op the commit reports. The encoder card promises short handles work. Failure direction is the gate's worst one ("fails CLOSED ... no restatement able to recover it", `:2253-2255`).
- **Verified:** CONFIRMED, snippet:
  ```
  resolve short ja: None            | resolve short en: white silk blouse
  named ja abbrev : []              | named en abbrev : ['white silk blouse']
  subjects ja     : set()           | subjects en     : {'Hinami'}
  subjects ja chg : set()  (ヒナミは服を着替えた。) | subjects en chg : {'Hinami'} ("changes out of her clothes")
  ```
- **Severity:** WRONG-SCENE (ledger keeps clothes the prose took off; the narrator renders from the ledger) in a shipped, parity-enforced pack. Not registered (UNBUILT_WORLD §1.113 is the English short-name case).
- **Fix:** one script-aware tokenizer for all of these readers (`[^\W_]+` words for segmented scripts; character-run containment for unsegmented ones, with tier 4 as "the handle is a suffix/substring of exactly one worn name"), and pack-supplied clothing context instead of `_CLOTHING_CONTEXT` for the subject gate. Test: the four Japanese cases above license/resolve.

### F9 — The guessed-span advice cannot work: coverage cannot extend a garment, the override is silently stored for a region it does not occupy, `flat_state` then reports a displacement that never happened, and the report goes quiet

- **Where:** `story/attire.py:1085-1101` (`apply_coverage_changes` writes `covered_zones` onto the garment's EXISTING copies only, no note when `changed_region` is not one of them), `:459-460` (`guessed_spans` treats any `covered_zones` as "somebody said where this goes"), `:3311-3319` (`flat_state`). Advice text: `persist/commit_attire.py:1688-1692`.
  ```python
  "If it covers more, say so once: attire.<name>.coverage = {'<garment>': {<region>: []}}."
  ```
- **Failure:** `[]` means "displaced off" in this vocabulary (`_clean_covered_zones` docstring), and no coverage entry adds a region. Following the advice leaves the span unchanged, writes a false derived note into `state` (which characters and the narrator read), and silences `guessed_spans` for that garment. The correct channels are `placement`/`add[].covers` (themselves inert through commit, §1.72).
- **Verified:** CONFIRMED, snippet:
  ```
  regions before: {'torso': ['nagajuban']}; guessed: ['nagajuban']
  apply_coverage_changes(r, {'nagajuban': {'legs': []}})
  regions after : {'torso': [('nagajuban', {'legs': []})]}   notes: []
  flat_state: ['nagajuban displaced off the legs'];  covered: ['torso'];  guessed after: []
  ```
- **Severity:** WRONG-SCENE. Not registered (UNBUILT_WORLD §2.14 says "The Director can answer with `coverage`").
- **Fix:** `apply_coverage_changes` should refuse, with a note, a region the garment does not occupy; `guessed_spans` should treat only `placed` as an authored span; the advice should point at `placement`. Test: coverage on an unoccupied region returns a note and leaves `flat_state` unchanged.

### F10 — `regions_covered` spans a garment by ANY cue in its name, while closed compounds match nothing

- **Where:** `story/attire.py:361-375` (spanning cue searched anywhere in the phrase) vs `region_of:378-403` (last cue wins) vs `attaches_only:328-358` (head before a placement preposition); comment `:220-221`.
- **Failure:** a modifier noun spans the garment like the garment it names: a belt worn alone reads as covering torso, groin and legs — the exact "body in only a sash reads as dressed" failure AGENTS.md's waist/groin rule exists to prevent. `\b` cannot fire inside closed compounds, so `overcoat`, `raincoat`, `trenchcoat`, `petticoat` match no cue and fall to the torso default; the comment "checked longest-first so 'overcoat' is a coat" is false (there is no `overcoat` cue and no longest-first pass).
- **Verified:** CONFIRMED, snippet:
  ```
  'dress belt'           covers ('waist','torso','groin','legs')
  'kimono sash'          covers ('waist','torso','arms','groin','legs')
  'trouser belt'         covers ('waist','legs','groin')
  'jeans jacket'         covers ('torso','legs','groin')
  'apron over the dress' covers ('torso','waist','groin','legs')
  'overcoat'/'raincoat'/'petticoat' -> ('torso',), span_is_a_guess('overcoat') True
  ```
- **Severity:** WRONG-SCENE. Not registered (§2.14 is "the table matched nothing", not "matched the wrong word").
- **Fix:** compute the head cue once (the `region_of` winner, within `attaches_only`'s garment phrase) and look its span up from that cue only; correct the comment. Test: `regions_covered("dress belt") == ("waist",)`, `regions_covered("jeans jacket") == ("torso","arms","waist")`.

### F11 — The player token written at import is never resolved for minds, and the AI path keeps raw `{{user}}`/`{{char}}`/`<USER>`

- **Where:** `story/importers.py:272-304` (macros -> `{{PLAYER}}`), `:427` (heuristic substitutes the whole card), `:500-539` (reinterpret: card sent raw, sheet stored with no substitution); readers that hand sheet text to minds raw, e.g. `agents/character.py:4151` (`"public_history": character_public_history(sh)`).
- **Failure:** `substitute_player_token` runs only on the Director's output (`agents/common_sequence.py:1215`, one caller `agents/director.py:462`), and `start_story` substitutes only the greeting/scenario (`greetings.py:849-857`). A card whose scenario says "{{user}} is your sister" becomes `knowledge.public_history = "{{PLAYER}} is your sister"` and is read verbatim by the character (and the same in lore from `character_book`). On the AI path the model sees the raw macros and the stored sheet keeps whatever it copied — not even the canonical token. This is the "engine vocabulary inside a fictional mind" class `greetings.py:64-75` measured live. `GREETING_IMPORT_DESIGN.md:37-39` says the slot is "resolved deterministically at launch"; that holds only for the greeting text.
- **Verified:** CONFIRMED. Snippet (chat_complete and `qi` stubbed in-process):
  ```
  public_history: Aria grew up next door to {{user}}; <USER> owes her money.
  private: ['{{char}} has loved {{user}} for years']
  greeting: Hi {{PLAYER}}
  ```
  Heuristic: `heuristic_character_sheet({...'scenario':'{{user}}は宿屋に着く。'})` -> `public_history '{{PLAYER}}は宿屋に着く。'`.
- **Severity:** WRONG-SCENE (and an identity-floor question: the fix must not hand a stranger the persona's name). Not registered.
- **Fix:** run `_substitute_card_macros` over the reinterpreted sheet; resolve `{{PLAYER}}` in sheet text and lore where a mind reads it through the same identity floor the greeting launch uses (`player_handle_for`: name if known, description otherwise). Test: a reinterpreted card containing `{{user}}` stores no raw macro; a character payload built from a sheet with `{{PLAYER}}` carries no token.

### F12 — Automatic history routing reads the PLAYER's arrival in the opening as the card character's travel; in Japanese it never routes at all

- **Where:** `story/history_routing.py:24-30` (`_TRAVEL_PATTERNS`, incl. `arrives?|visits?|visiting|passing through`), `:170` (searched over `public + opening_context`), `:176-180` (travel checked first, confidence .94); `:41-55, 93` (English patterns, ASCII word set).
- **Failure:** greetings routinely open on the player arriving ("{{user}} arrives at the Gilded Goose"). A card whose public history states twenty years of residence is routed `visitor`: `start_story` then compiles a journey for her (`greetings.py:1087-1091`) and does not seat her in the Charter town (`route_uses_charter` false), so the town is planned without her post. "She visits her mother each spring" in the card does the same. For a Japanese card nothing matches, so `auto` always returns `authored_only` — conservative, but the feature does nothing in that pack.
- **Verified:** CONFIRMED, snippet:
  ```
  public: 'Mara has run the Gilded Goose inn in Hollowmere for twenty years and lives in the rooms above it.'
  opening '{{PLAYER}} arrives at the Gilded Goose in Hollowmere...' -> 'visiting', reasons [explicit travel or arrival language]
  opening 'The rain hammers the Gilded Goose in Hollowmere. Mara wipes the bar.' -> 'resident'
  Japanese equivalent -> mode 'auto', opening_relationship 'arriving' (authored_only)
  ```
- **Severity:** WRONG-SCENE. Not registered (UNBUILT_CHARACTERS §2 entries cover the routing's scope, not this attribution).
- **Fix:** read travel language from the card only (or from opening sentences whose subject is the card character); residence evidence should outrank arrival language in the opening. This is a free-prose word list, so the durable fix is to ask the author (the launch already exposes the route) or a model, not to widen the list. Test: the Mara case routes `resident`.

### F13 — `sanitize_attire_items` refuses by the LAST word of the first clause, so "the cup in her hand" — the module's own example — stays in the wardrobe

- **Where:** `story/attire.py:55-58` (the example), `:107`, `_garment_keys:1292-1302` (last whitespace word).
- **Failure:** any prepositional tail makes the location or contents the "head noun": `a cup of tea`, `a glass of wine`, `the cup in her hand`, `a sword at her hip` are all kept as worn garments. `attaches_only` already cuts the garment phrase at `_PLACEMENT_PHRASE` (`:309-311, 351`); this reader does not, so two readers of "what is this thing" use two rules. Japanese items (`椅子`, `湯呑み`) are never refused (English table).
- **Verified:** CONFIRMED, snippet: `sanitize_attire_items([...])` keeps `'a cup of tea','the cup in her hand','a glass of wine','a sword at her hip'`.
- **Severity:** WRONG-SCENE (a body "wearing" a cup forever — the module's stated failure). Not registered.
- **Fix:** take the head from the phrase before `_PLACEMENT_PHRASE`/`of`, shared with `attaches_only`. Test: the four strings above are refused; `tinted glass goggles` and `bottle green coat` still kept.

### F14 — `normalize_regions` reads a removal word the module itself knows as `worn`

- **Where:** `story/attire.py:708, 724` vs `_REMOVAL_STATE_WORDS:1603-1606` / `is_removal_state:1624-1626`.
  ```python
  state = str(item.get("state") or "worn").strip().casefold()
  "state": state if state in GARMENT_STATES else "worn",
  ```
- **Failure:** a `regions` block (the opening's shape, and the "fourth door" the encoder is offered every beat, `commit_attire.py:1284-1300`) with `"state": "off"`, `"taken off"` or `"Removed."` puts the garment back ON, while the note path reads the same words as removal. No schema constrains the value.
- **Verified:** CONFIRMED, snippet: `[('wool coat','worn'), ('linen shirt','open'), ('vest','worn'), ('tie','worn')]` for states `off`, `Open`, `unbuttoned`, `Removed.`.
- **Severity:** WRONG-SCENE (low frequency). Not registered.
- **Fix:** canonicalise through `is_removal_state` (and strip `.`), and report any other unknown state instead of silently defaulting. Test: `state: "off"` normalises to `removed`.

### F15 — Greeting seeds rewrite the outside-the-fiction word "the player" only in English

- **Where:** `story/greetings.py:79-83` (`_PLAYER_SLOT`), `:292` (`_split_minds` identifies the player's mind with it).
- **Failure:** the ja prompt forbids `プレイヤー`/`ユーザー`/`主人公` but nothing deterministic catches them; a ja seed reading "プレイヤーは…" reaches the mind verbatim, and a mind with `who: "プレイヤー"` is filed as an unclaimed presence (retained for promotion) instead of the player.
- **Verified:** PLAUSIBLE (regex read; no ja extraction replayed).
- **Severity:** WRONG-SCENE (language-pack hazard). Not registered.
- **Fix:** take the player-word variants from the active language pack (they are a closed list the pack already names in its own prompt). Test: a ja mind `who: "プレイヤー"` is the player's.

### F16 — `guess_category` matches cue fragments inside other words, so most English prose lands in `layout`

- **Where:** `story/importers.py:1597-1618`.
- **Failure:** `anyof` is substring matching: `wing` fires on knowing/showing/following/drawing, `hall` on shall, before the myth/event/location rungs are tried. Japanese text always lands in `other`.
- **Verified:** CONFIRMED, snippet: "The goddess of the harvest, knowing all..." -> `layout`; "A battle shall be fought; showing no mercy." -> `layout`; `guess_book_type` of two such entries -> `location`.
- **Severity:** WRONG-SCENE, low: the `layout` consumers (`agents/director.py:6729-6730`, `persist/commit_scene_state.py:2154`) read `staged_lore`, which is always empty now (`agents/mapping.py:668`), so today the cost is the category and book-type labels only.
- **Fix:** word-boundary the cues; since this is a free-prose classifier, prefer `category` from the model on the reinterpret path and `other` otherwise. Test: the two sentences above do not classify as `layout`.

### F17 — `room_citations` never harvests the citation the room is told to use, nor any integer id, so a correctly cited lore claim is demoted

- **Where:** `story/room_citations.py:58-60` (`ID_KEYS` lacks `citation`), `:157-159` (`_add` keeps only `str`).
- **Failure:** `search_lore`/`read_lore`/`scan_lore` return `{"citation": "lore:42", "id": 42, ...}` and their tool description says "Cite an entry by its citation when you rely on it" (`story/room_tools.py:152,178,213,1468`). Neither `lore:42` nor `42` enters the ledger, so the claim is `unsupported` and reported as a proposal. Any tool row keyed by an int id (`id`, `book_id`, `char_id`, `turn_id`) is equally uncitable. `ID_KEYS`' own comment names this as the expensive direction of the error.
- **Verified:** CONFIRMED, snippet:
  ```
  note_reads('search_lore', {'hits':[{'citation':'lore:42','id':42,'uid':'e_abc','book_id':7}]}) -> rows ['e_abc']
  cites ['lore:42'] -> unsupported;  ['7'] -> unsupported;  ['e_abc'] -> supported
  ```
  `tests/test_room_cites_what_it_read.py` uses only string uids.
- **Severity:** SILENT-NOOP (the citation contract mis-grades honest claims). Not registered (UNBUILT_PLANNING lists the contract as built).
- **Fix:** add `citation` to `ID_KEYS` and stringify int ids in `_add`. Test: the snippet above yields `supported` for `lore:42`.

### F18 — `coerce_diff_shape` silently drops a declared placement whose region word is not one of the eight

- **Where:** `story/attire.py:1730-1734` (`add[].covers`), `:1748-1753` (`placement`).
- **Failure:** `covers: ["tail"]` for a body that declares a tail, or a zone word (`"chest"`), or `"Chest"` for a belt, is filtered to `[]` with no note; the garment falls back to the name table. Authored card regions get `rehome_region` (A89: declared parts land on their `at` region); the diff path has no such reading.
- **Verified:** CONFIRMED, snippet: `coerce_diff_shape({'add':[{'name':'silk tail-wrap','covers':['tail']},{'name':'lace bandeau','covers':['chest']}],'placement':{'belt':['Chest']}})` -> `{'add': ['silk tail-wrap', 'lace bandeau']}`; both land on the torso.
- **Severity:** SILENT-NOOP. Masked today because `placement`/`covers` are inert through commit anyway (registered UNBUILT_WORLD §1.72); it surfaces the day §1.72 is fixed.
- **Fix:** rehome through `rehome_region(region, parts)` (zone words to their region) and return a note for anything else. Test: `covers:["tail"]` with `parts={"tail":"waist"}` lands at the waist, attaching.

### F19 — A failed greeting-seed batch is swallowed and recorded as "0 memories"

- **Where:** `story/greetings.py:340-356`.
  ```python
  try:
      add_memories_batch(seed_specs)
      feel_seeded_quietly(chat_id, char_id)
  except Exception:
      return 0  # a failed seed batch must not abort the launch
  ```
- **Failure:** no log, no refusal line; `greeting_minds` then says the card mind received 0 memories — indistinguishable from an extraction with no seeds, which `_seed_minds`' docstring names as this subsystem's failure mode. If only `feel_seeded_quietly` raised, the memories WERE written and the record still says 0.
- **Verified:** CONFIRMED by reading.
- **Severity:** SILENT-NOOP.
- **Fix:** log and return the error into the mind's `refused` list; count rows written before the affect pass. Test: stub `add_memories_batch` to raise; the record carries a refusal.

### F20 — A file that is not a card is imported as a blank "Unnamed" character (or "Player" persona) instead of being refused

- **Where:** `story/importers.py:242-257` (`resolve_import_card` returns `{}` for a non-dict; `_card_data` passes any dict), `:424` (`name = d.get("name") or "Unnamed"`), `:649`.
- **Failure:** the import dialog accepts any JSON (`static/js/editors.js:993-996` only checks it parses, and advertises World Info under characters too). A lorebook or an unrelated JSON uploaded to the character importer with reinterpretation off inserts a default sheet named "Unnamed" and returns 200 with only the empty-drive warnings.
- **Verified:** CONFIRMED by trace (`heuristic_character_sheet({})` returns the default "Unnamed" sheet; insert at `:557-569`).
- **Severity:** SILENT-NOOP (silent tolerance; junk row).
- **Fix:** refuse a payload with no `name`/`description`/`first_mes`/native identity with a message naming what was expected. Test: importing `{"entries": {...}}` as a character raises `ValueError`.

### F21 — Common SillyTavern macros other than `{{char}}`/`{{user}}` render literally

- **Where:** `story/importers.py:277-289`.
- **Failure:** `{{random::a::b}}`, `{{// comment}}`, `{{original}}`, `{{persona}}`, `{{trim}}`, `<START>` (mes_example separator) are left verbatim in greetings (shown to the player word for word) and sheet fields — the same class `tests/test_import_macros.py` exists for.
- **Verified:** PLAUSIBLE (regex read; corpus frequency not measured).
- **Severity:** WRONG-SCENE, low.
- **Fix:** strip comment macros and `<START>`, resolve `{{random::}}` to its first option (or keep a greeting variant per option), and report unknown `{{...}}` in the import warnings. Test: a `first_mes` with `{{// note}}` imports without it.

### F22 — Two prose readers are kept alive only by tests

- **Where:** `story/attire.py:1282-1285` (`decisive_intent`), `:1831-1852` (`process_targets`).
- **Failure:** no production caller (grep across `agents/ world/ persist/ story/ web/ tools/ extension_runtime/`): commit uses `decisive_targets` and `process_targets_by_garment`. Each is a second spelling of a reading that can drift from the live one while its tests stay green.
- **Verified:** CONFIRMED (grep: only `tests/test_attire_displacement.py`, `tests/test_attire_authoring.py:1320-1325`).
- **Severity:** DEAD.
- **Fix:** delete both and point their tests at the live readers.

### F23 — `_DIFF_KNOWN_KEYS` has no production consumer and already omits a key the chain handles

- **Where:** `story/attire.py:1575-1584` vs `:1690-1701` (`from_event`).
- **Failure:** the comment says it lists "Every attire-diff key `coerce_diff_shape` HANDLES"; `from_event` is handled and absent. Only `tests/test_attire_regions.py:1246-1259` reads the tuple, and that test checks one direction only.
- **Verified:** CONFIRMED (grep).
- **Severity:** DEAD / STALE-DOC.
- **Fix:** derive the tuple from the dispatch (or delete it and keep the test against the chain).

### F24 — `guessed_spans` says it is UNWIRED; it runs on every attire commit

- **Where:** `story/attire.py:437-442`; production caller `persist/commit_attire.py:1688`.
- **Verified:** CONFIRMED (grep). UNBUILT_WORLD §2.14 already records "The report landed 2026-08-19".
- **Severity:** STALE-DOC.
- **Fix:** rewrite the docstring to say where it runs (and see F9 for what its advice does).

### F25 — "One step per beat" is described as the rule in three places; the clamp was inverted

- **Where:** `story/attire.py:25-30` (module docstring), `:1138-1140` (`_DECISIVE` comment), `docs/guides/FEATURES.md:507-511`; behaviour `advance:2626-2696`.
- **Failure:** a resolved removal lands in one beat unless `process` says the act is in progress; decisive language now matters only for intermediate jumps and process clamps.
- **Verified:** CONFIRMED, snippet: `apply_flat_change(normalize_regions({'wearing':['silk kimono']}), [])` -> every copy `removed` in one call, no decisive flag.
- **Severity:** STALE-DOC (the guide is an authority doc).
- **Fix:** restate both as "a removal lands when resolved; it is held one rung only while the beat's prose shows it in progress".

### F26 — `is_derived_state_note` says `flat_state` emits "exactly two shapes"; it emits four

- **Where:** `story/attire.py:3332-3334` vs `flat_state:3282-3326`.
- **Verified:** CONFIRMED by reading (the code recognises all four).
- **Severity:** STALE-DOC, low.

## Efficiency

1. **The ledger is re-derived by every reader, every beat.** `rederive_entry` (`story/attire.py:3453-3486`) runs `normalize_regions` -> `dedupe_regions` (an O(g²) `resolve_garment` pass with per-pair regex) -> `_sync_spanning_garments`, then `flat_state` (three more coverage walks). Measured 1.5 ms for a ten-garment body. Callers re-derive per observer x body (`agents/common_bodies.py:349-355, 433-444`), per body for the scene views (`:160-172, 204-214`), and 3-6 times per diffed body in commit (`persist/commit_attire.py:1128-1130, 1167, 1199-1200`, `_before`/`_after`). Estimate (not measured in a turn): 20-60 derivations per beat in a 4-6 body scene, 30-90 ms of pure CPU. Gain: memoise per beat on the entry's identity, or store the canonical form with a stamp at commit so readers skip normalisation when it is current. Cheap.
2. **The promotion seed call regenerates a whole character sheet to read 3-8 strings.** `story/importers.py:951-962` reuses `promote_character` (whose output schema is the full sheet with `memory_seeds` LAST) at `max_tokens=20000`. Cost: about one more full authoring call per promotion (~$0.01-0.02 on the owner's routing, per the `AUTHORING_ATTEMPTS` note). Reliability: truncation cuts the tail first, which is exactly the seeds, and for automatic promotion (`persist/commit_background.py:4986-4990`) there is no review screen to refill them. Gain: a seed-only prompt (or a mode flag the card reads), with a small budget.
3. **`apply_lorebook_plan` embeds every entry inside the global write transaction.** `story/importers.py:3025-3141` calls `add_lore`/`update_lore` without a vector, so each computes one (`mind/memory_lore_entries.py:130-131`) while `transaction()` holds `_write_lock` + `BEGIN IMMEDIATE` (`core/db.py:2356-2358`). A 40-entry plan is 40 embedding round trips during which a turn's commit waits. Every sibling path (`generate_lore_entries:3268-3275`, `reinterpret_lorebook:2061-2067`, `import_lorebook:1939`) computes vectors first. Gain: the same pattern here; also removes a lock-across-network hazard.
4. **A prelude greeting launch pays for `greeting_interpret` twice, and every resume pays again.** `story/greetings.py:845-847` extracts before `prelude` returns at `:963-987` (only `extraction["time"]` is used), and `begin_story` re-enters `start_story` (`story/prelude.py:153-162`) and extracts again; `retry_start` does the same. The write half of extraction caching is registered (UNBUILT_PIPELINE §6.3); a per-chat store of the extraction would remove the duplicate calls and also fix half of F5.
5. **`room_bible` writes the whole row once per filed entry.** `fold` (`story/room_bible.py:406-432`) calls `add_entry`/`mark_paid` per model entry, each re-reading and re-normalising the full row (`_row`) and writing it back, and `source_exists` runs a query per ref (`plot:` refs load every package, `:101-103`). `pending_fold_count` loads and decodes every unfolded `room_messages` row just to count them (`:352-367`), on every planner run that schedules a fold. Out of band; low. Gain: one row read/write per fold; a `COUNT(*)` for the threshold.
6. **`_promotion_evidence` parses every event of the chat per draft** (`story/importers.py:679-708`). O(turns) JSON decodes per promotion; occasional. Gain: filter by speaker/mention in SQL or cache the per-name index.
7. **The attribution ladder runs three times per beat over the same text** (`persist/commit_attire.py:1131-1159`: `decisive_targets`, `process_targets_by_garment`, `wardrobe_change_subjects`), each re-splitting sentences and recomputing `_garment_keys` for every garment of every body (`story/attire.py:2001-2029`). Small; one shared pass returning all three readings would do.

## Already registered

- `_override_narrator` replaces turn 0's narrator with the verbatim greeting; `greeting_interpret` may duplicate a conduct memory — UNBUILT_PIPELINE §1.163 (residuals).
- Extraction caching write half; `player_slot`; greeting swipe — UNBUILT_PIPELINE §6.3.
- `entry_for` re-spellings — UNBUILT_WORLD §1.79. **The register is stale:** the `agents/common.py` copies it names now go through `key_for` (`agents/common_bodies.py:349-352, 431-433`). Two NEW open-coded copies exist with a different fold (whitespace-collapsing) and they read the raw `wearing` list rather than the re-derived ledger: `agents/skip_stage.py:489` (`held_things`) and `agents/skip_work.py:249` (`_worn`); both also branch on `wearing` items being dicts with an `item` key, a shape `wearing` never holds. `story/attire.py:1416-1443` (`recover_shed_entity_changes`) builds its own strip+casefold map beside `key_for` in the same module (same rule today). `world/spatial_listener.py:164-170` extends `entry_for` with a `same_subject` fallback (an extension, not a copy).
- A short whole garment name cannot license its wardrobe — UNBUILT_WORLD §1.113 (English half of F8).
- Guessed spans reported; `placement`/`add[].covers` inert through commit — UNBUILT_WORLD §2.14, §1.72 (F9 and F18 are new defects inside that area).
- `displaced_by`/`apply_flat_change(displaces=)` have no production caller — UNBUILT_WORLD §1.114 (outstanding by design).
- The process clamp's generic-word co-occurrence — UNBUILT_PIPELINE §1.112. The removal-completion vocabulary class (`_DECISIVE`/`_DECISIVE_GAP_OFF`) — per the brief, registered.
- The promotion sheet's author reads the whole events record (omniscient `resolved_event`) — UNBUILT_LIVING_WORLD §6.1 bullet "Promotion conversion (§3.6)" (measured on story 166) and §1.8. Note for whoever fixes it: `draft_promoted_character`'s docstring (`importers.py:821-825`, "authoring is tooling, not a mind") contradicts the module's own `PLAN_FIELDS_FOR_SHEET` rationale 70 lines above ("a truth handed to the sheet's author is a truth placed in that head").
- A planned person's own truths withheld from the sheet — UNBUILT_PLANNING §1.198 / UNBUILT_IDENTITY.
- Heuristic import ignores `description` for psychology — UNBUILT_CHARACTERS §2.3.
- Citation contract's remaining owners (Planner envelope, panel display) — UNBUILT_PLANNING (recap cites what it read).

**On the `jacket_` question.** No helper in these six files produces that key. The slug is inline at `persist/commit_attire.py:768-772` (`re.sub(r"[^a-z0-9]+", "_", ...)` on garment and owner), and the same convention is re-spelled in `world/spatial_containment.py:1634-1637` (it reserves `<garment>_<owner>` keys so a transfer mint cannot take them) and `persist/commit_attire.py:685` (placeholder-name detection). Those three must change together, or the reservation stops matching the mint. Inside the six files the ASCII-only normalisers are tokenisers, not keys: `attire.py:2025, 2046, 2196, 2343` (`[a-z0-9\-’']+`), the `\b<name>\b` / `\b<name>['’]s\b` anchors at `:2042, 2067`, `_garment_keys`' whitespace head noun (`:1302`), and `history_routing.py:93`. For kana/kanji they yield an EMPTY set, so the tiers that use them are skipped silently (F8, F12); they do not make two names collide. Accented Latin degrades partially (`négligée` tokenises to `n`/`glig`/`e`, but the eight-character suffix window still finds it). Every hash-based id here (`room_bible._entry_uid`, greeting/seed digests, `_structure_key`) is Unicode-safe.

## Structure notes

- **`story/attire.py` (3,699 lines) has seven natural seams:** (a) the name tables and classification — `REGIONS`, `_REGION_CUES`, `_SPANNING_CUES`, `_ATTACH_CUES`, `region_of`, `regions_covered`, `attaches_only`, `span_is_a_guess`, `guessed_spans` (43-465); (b) the region-record model and normalisation — `region_record`, `normalize_regions`, `authored_entry`, `_sync_spanning_garments`, `dedupe_regions`, `rederive_entry`, `flat_*`, `release_removed_garments` (544-886, 1479-1561, 3227-3487); (c) the coverage/zone axis — `zones_of`, `covered_zones_for`, `apply_coverage_changes`, `concealing_garments`, the bare-body predicates, `coverage_*` (114-210, 579-631, 888-1128, 2429-2533); (d) the English prose readers — every regex table plus `_attributed_scoped`, `decisive_targets`, `process_targets*`, `wardrobe_change_subjects`, `garments_named_in`, `removal_directed_at` (1138-2427) — this is the language-pack-sensitive half and the one F8 lives in; (e) diff coercion — `coerce_diff_shape` and the state-word sets (1563-1782); (f) renderers — `describe`, `perceptible_region_surfaces`, `coarsen_region_surface`, `compact_line` (2764-2990, 3489-3699); (g) the ledger key — `key_for`, `entry_for` (3406-3450). Monoliths in miniature: `_attributed_scoped` (~140 lines), `normalize_regions` (~160), `coerce_diff_shape` (~135), `garments_named_in` (~125), `compact_line` (~120), `perceptible_region_surfaces` (~100). Module state: none mutable (all tables are tuples/frozensets/compiled regexes).
- **Three readers of "what is this garment called" disagree** (F10, F13): `region_of` (last cue in the whole phrase), `attaches_only` (last cue before a placement preposition), `regions_covered` (any spanning cue anywhere), `sanitize_attire_items` (last word of the first comma clause), `_garment_keys` (last word). One `garment_head(name)` would serve all five.
- **Two resolvers of one handle disagree in one commit** (F4): `resolve_garment(..., allow_head_noun=True)` in the gate and `remove`/`add`/`replace`, `allow_head_noun=False` in `apply_flat_change`, `normalize_regions` and `dedupe_regions`. The stricter tier is right for MERGING two records; it is wrong for MATCHING a handle to a worn garment, which is what `apply_flat_change` does.
- **`story/importers.py` (3,300 lines) seams:** card import (PNG chunks, macros, heuristic/native/reinterpret: 162-674), promotion drafting (676-981), the three fill surfaces (1024-1531), lorebook import/reinterpret (1572-2096), resumable lore generation (2098-2942), plan application and one-shot generation (2944-3300). `chat_complete` is bound at import (`:9-12`): tests patch `importers.chat_complete` correctly, but a harness that rebinds `providers.chat_complete` (the "patched at the provider seam" pattern in `tests/test_gap_boundaries.py:60-68`) cannot intercept these calls. No production code rebinds it (grep). `greetings.py` has the same shape with `complete_validated_json` (`:32`); its `generate_greeting` imports `chat_complete` lazily. Module state: `_GEN_OWNER` (per-process token, written once at import); `__getattr__` compat names resolved on access.
- PNG import reads `tEXt` and `zTXt` only (`:169-196`); a card stored in an `iTXt` chunk is refused with "expected a 'chara' or 'ccv3' metadata chunk". The v2/v3 specs use `tEXt`, so this is a compatibility note, not a finding.
- **`story/greetings.py`:** `start_story` (796-1241, ~445 lines) is a monolith with a stage-per-paragraph shape and a resume protocol each stage implements by hand — F5 is the one stage that did not. Import side effect: the module imports `agents.runtime._run_pipeline`, `persist.steps`, `world.charter_runtime` at load.
- **`story/room_bible.py`:** no lock (F7). **`story/room_citations.py`:** one ContextVar (`_rows_read`), written by `reading()`, `enter_reading()`, `note_reads()`. **`story/history_routing.py`:** pure; its whole automatic half is an English free-prose classifier.

## Docs checked

- AGENTS.md row "Clothing regions and undressing": `story/attire.py` "is pure functions over dicts and must stay database-free" — HOLDS (imports `copy`, `re` only). "A garment spans every region it covers (`regions_covered`)" — holds, with F10's wrong spans. "`_sync_spanning_garments` must run after any change that rebuilds garment dicts" — HOLDS (`advance`, `apply_coverage_changes`, `normalize_regions`, `release_removed_garments` via `rederive_entry`).
- AGENTS.md / CLAUDE.md: waist and groin are separate so "a body in only a sash reports its groin covered" cannot happen — VIOLATED by naming: `dress belt`, `kimono sash`, `trouser belt` cover the groin (F10).
- CLAUDE.md: `character_card_warnings` runs on every card-producing surface, import included — HOLDS for character import (`web/app.py:3515-3516`) and the promotion draft (`importers.py:980`); persona import returns none (personas carry no psychology; not a surface the rule names).
- `docs/guides/FEATURES.md:507-511` "worn, then loosened, then open, then off, one step per beat" — STALE (F25).
- `docs/guides/FEATURES.md:913-922` card import as JSON or PNG in old and new formats; lorebook import "keeping author-disabled entries switched off; export round-trips exactly" — HOLDS (native path exact; `disable`/`enabled:false` both honoured at `importers.py:1799-1803`); the AI path loses structure (F6).
- `entry_for` docstring "THE ONLY WAY TO READ ONE BODY'S WARDROBE ... Every per-name reader now routes here" — FAILS for `agents/skip_stage.py:489`, `agents/skip_work.py:249`.
- UNBUILT_WORLD §1.79 "Three inline copies ... remain in agents/common.py" — STALE (consolidated); see Already registered.
- UNBUILT_WORLD §2.14 "The Director can answer with `coverage`" — WRONG (F9).
- UNBUILT_PIPELINE §6.3 "a retried or partially-failed launch updates one row rather than writing a second" — holds only for byte-identical memory seeds (F5).
- `GREETING_IMPORT_DESIGN.md:37-39` "{{PLAYER}} ... resolved deterministically at launch" — holds for the greeting prose only (F11).
- `DESIGN_GREETING_MINDS.md` §revealed_in_prose points 2 and 3 — they conflict for player-mind seeds naming the slot (F2).
- `importers._structure_key` docstring ("the opening of the text survives a rewrite far better"; "both halves of a split entry legitimately inherit") — the import path's exact-key lookup delivers neither (F6).
- `apply_flat_change` comment on shorter phrases (F4); `_REGION_CUES` comment on `overcoat` (F10); `guessed_spans` "UNWIRED" (F24); `_DIFF_KNOWN_KEYS` (F23); `is_derived_state_note` (F26) — all checked, all stale as stated.
- `room_citations.ID_KEYS` "Harvesting is deliberately GENEROUS" — FAILS for `citation` and integer ids (F17).
- `importers.PLAYER_TOKEN` comment ("enough to stop a literal '{{user}}' from rendering to the player") — holds for the heuristic path, not the reinterpret path (F11).
- Encoder card `encoder/attire.txt:7` "'robe' finds the one robe she is wearing" — true for `remove`/`add`/`replace`, false for `wearing` (F4).
