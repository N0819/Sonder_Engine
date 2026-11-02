# Audit: `dressing/ambience.py`, `dressing/backdrops.py`, `language_runtime/*`, language-pack structure

Auditor run 2026-11-01, working tree at `84f3de23` (branch `worktree-jev-character-tracking`), read-only.
Snippets were run with `.venv/bin/python` from the repo root. Database reads were `mode=ro` only.
The two focused test runs were `tests/test_ambience.py` (92 passed) and `tests/test_a_strangers_label_is_a_body.py` (25 passed). Both are green: none of the defects below is covered by a test.

## Scope read

**Read in full, line by line:**
- `dressing/ambience.py` 1-2103
- `dressing/backdrops.py` 1-1782
- `language_runtime/__init__.py` 1-787
- `language_runtime/referring.py` 1-609
- `language_runtime/card_source.py` 1-389
- `language_packs/README.md`, both `manifest.json`, both `prompt_policy.json` (keys, role names and lengths, the English role texts' openings)
- `docs/guides/LANGUAGE_PACKS.md` 40-402

**Analysed by script, not read line by line:**
- the `authoring`, `compositor`, `linguistics` and `system_prompts` cards of both packs, via `raw_card`: leaf-path parity both ways, value types, emptiness, byte-identical values, regex flags and `\b` placement.
- `ui.json` parity, plus the unchanged-value count against `translation_exceptions.json`.
- The scripts are in `<review scratch>/dlr/parity.py` and inline below.

**Read in part to trace callers:**
- `story/character_schema.py` 1796-1860 (`name_boundary_pattern`)
- `tools/project_check.py` 997-1232 (`check_language_pack_surfaces`)
- `tests/test_prompt_card_split.py` 1-60 and 300-390
- `tests/test_name_matching_scripts.py` 1-80
- `tests/test_ambience.py` (the anchor and occupant tests)
- `agents/common_names.py` 175-420 and 880-960
- `agents/composer.py` 490-530, 600-640 and 2395-2480
- `agents/perception.py` 6830-6850
- `agents/runtime.py` 640-700 and 2125-2180
- `web/app.py` 940-1000, 4513-4520 and 7925-8230
- `persist/chat_delete.py`
- `persist/commit_scene_state.py` 160-195 and 625-680
- `persist/commit_room_registry.py` 520-550
- `core/code_version.py` 1-160
- `core/outofband.py` (grep only)
- `story/scene.py` 1095-1140
- `mind/theory_of_mind.py` 355-385
- `mind/notebook.py` 100-125
- `world/spatial_light.py` 120-140 and 325-345
- `llm/schemas.py` 165-192 and 2585-2600

**Skimmed only, not audited:**
- `static/js/backdrops.js` and `static/js/ambience.js`, by grep for poll constants and how room names are used.
- `docs/UNBUILT_*.md`, by grep, for the "Already registered" checks.

## Findings

### F1 — In a Japanese story, nothing removes people from the room description before it reaches the image prompt
- **Where:**
  - `dressing/backdrops.py:381-397` (`_PERSON_WORDS`), `:513-517` (`_BODY_WORDS`), `:400` (`_SENTENCE_SPLIT = (?<=[.!?])\s*`) and `:403-433` (`_setting_only`). All four are English-only.
  - `place_desc` (`:144-153`) runs the description through them before `room_projection` (`:933-936`) and `compose_prompt` (`:1343-1344`) use it.
  - The same unstripped text reaches the `backdrop_prompt` model through `refine_prompt` (`:1455-1460`).
  - It also reaches the `ambience_prompt` model through `room_soundscape` (`ambience.py:584-587`).
- **Code:**
  ```python
  _PERSON_WORDS = re.compile(r"\b(he|she|they|him|her|...|crew ?members?|civilians?|...|people|figures?)\b", re.I)
  _SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s*")
  ```
- **Scenario:** a Japanese room description that names a population or a character keeps it.
  ```
  >>> place_desc({'desc':'琥珀色の光とパノラマ窓。非番の乗組員や民間人がここに集まる。ヒナミがカウンターに寄りかかっている。'})
  '琥珀色の光とパノラマ窓。非番の乗組員や民間人がここに集まる。ヒナミがカウンターに寄りかかっている。'
  >>> 'ヒナミ' in compose_prompt(room_projection(sc,'tf'))
  True
  ```
  The English control loses both people-sentences and returns `'Amber light and panoramic windows.'`
- **Why this is a leak by the module's own rule:** rule 2 of the module docstring (`:18-25`) says this field is "additionally people-stripped on the way out". The "no people" instruction is the belt-and-braces half that the module explicitly refuses to rely on alone (`:368-372`). In Japanese only the instruction is left. "A leak that only a cooperative model avoids IS a leak": a hidden or unperceived occupant named in the description can be painted.
- **Verified:** snippet above, plus the caller trace `generate_backdrop` → `build_backdrop_request(for_prompt=True)` → `room_projection`. CONFIRMED.
- **Severity:** LEAK.
- **Fix:** move the person, body and visual-register recognisers and the sentence-end set into the language pack (a `dressing.backdrops` module in `linguistics.json`). This is owner decision 2 of UNBUILT_WORLD §1.65. Split sentences on the pack's sentence ends (`。` included).
- **Test:** a ja room description naming a person: `place_desc` drops that sentence and `compose_prompt` does not contain the name. Write it for both packs.

### F2 — The backdrop and the sound bed show the room the player is in even when the player character perceives nothing
- **Where:**
  - `dressing/backdrops.py:156-175` (`_room_of_player` = `room_of(scene, player_name)`), `:1128-1196` (`build_backdrop_request`)
  - `dressing/ambience.py:1443-1485` (`build_ambience_request`)
  - the routes `web/app.py:8007-8020` and `8163-8177`
  - None of these reads the player's awareness or senses. Neither does `static/js/backdrops.js` / `ambience.js`; a grep for `awake|asleep|unconscious|residue|blind` finds nothing.
- **Scenario:** the player character is knocked out and carried into a cell. Perception gives the player the non-awake floor and nothing else:
  ```python
  if p.get("awareness") in NON_AWAKE_GATED:
      percepts = composer.residue_percepts(p["awareness"])
  ```
  That is `agents/perception.py:6843-6845`.
  - The same turn's backdrop is drawn from `scene.rooms[cell]`: walls, openings, light sources.
  - The ambience bed plays that cell's sound.
  - The human player sees and hears where the character is, through a channel the perception floor closed.
  - The same holds for a blindfolded or sleeping player. `_viewer_light` (`:560-574`) accounts for the player's lamp and not for their eyes.
- **Why it counts:** both modules call the presentation layer a perception channel. Ambience rule 2 (`ambience.py:16-22`) says a crowd murmur "would report that character's presence through a channel perception never authorized".
- **Verified:** traced every reader from route to projection; there is no gate. CONFIRMED for the mechanism. Whether dressing must obey the awareness floor is an owner ruling; this report states it as the modules' own standard.
- **Severity:** LEAK.
- **Fix:** before resolving the room, have `build_*_request` ask the floor perception asks: the player's committed awareness for that turn in `NON_AWAKE_GATED`, and their sight or hearing. Where the floor applies, return the "absent" request (the frontend already keeps the previous picture only while the room is the same).
- **Test:** a scene with the player `unconscious` and moved to a new room. `build_backdrop_request` and `build_ambience_request` return None, and `GET /api/turns/{id}/backdrop` answers `status: absent`.

### F3 — Dressing works out a room's doorways from the room's own edges again, against AGENTS.md; one copy sends raw edge names to the image-prompt model
- **Where:**
  - `dressing/backdrops.py:954-965`: `room_projection.exits` comes from `room.get("adjacent")` with the raw `name`.
  - `dressing/ambience.py:613-621`: `room_soundscape.openings` comes from `room.get("adjacent")` alone.
- **Code:**
  ```python
  for edge in (room.get("adjacent") or []):
      ...
      exits.append({k: edge[k] for k in ("barrier", "vertical", "dir", "name") if edge.get(k)})
  ```
- **Scenario:**
  ```
  room_projection(hall with edge name 'the door she locked behind her', plus a far-side 'open' edge from the yard)
  openings: {'n': [{'barrier': 'closed_door'}], 'e': [{'barrier': 'open'}]}      <- effective_adjacent, name stripped
  exits:    [{'barrier': 'closed_door', 'dir': 'n', 'name': 'the door she locked behind her'}]   <- raw, one-sided
  room_soundscape(cell open to a street only through the street's own edge)['openings'] -> None
  effective_adjacent(cell) -> [{'barrier': 'open', 'to': 'street', 'implicit': True, 'dir': 's'}]
  ```
  - `place` (with `exits`) is the payload of the `backdrop_prompt` call (`:1455-1460`) and is stored as the room's continuity anchor (`:1690`). The people-strip `_openings_of` applies (`:724`) is skipped for the copy the model also reads.
  - Ambience tells its model that a cell open to a street is sealed.
- **Why it counts:** AGENTS.md:495 says "Which ROOMS an edge joins ... has one answer: `effective_adjacent` ... Never re-derive it ... leave sound, scent, sight and ambience undirected". It measured 117 of 374 live pairs as one-sided.
- **Verified:** snippets above. CONFIRMED.
- **Severity:** LEAK (minor: text with a person in it reaches the prompt model) and WRONG-SCENE (the ambience model is told the room is enclosed).
- **Fix:**
  - Drop `exits`; `openings` from the brief already carries the same doors, stripped and undirected.
  - Build `room_soundscape.openings` from `effective_adjacent`.
- **Test:** a one-sided edge plus an edge name containing a person word. The projection carries no raw name, and the soundscape has the opening.

### F4 — A person who emits light is named in the image prompt and the picture's cache key
- **Where:** `dressing/backdrops.py:577-608` (`_light_sources_in`, docstring "Occupant-free by construction: only entities, never people's positions"), consumed by `_source_lighting` (`:1238-1265`) and `visual_signature` (`:242`).
- **Scenario:** `scene.entities` holds `kind: "person"` bodies too (`agents/common_cast.py:602`, `agents/director_floors.py:1742`), and any entity with `light_source` lights its room (`world/spatial_light.py:329-334`).
  ```
  entities={'wisp': {'name':'Elowen the Lightbearer','kind':'person','light_source':'dim'}}
  room_projection(...)['light_sources'] -> [{'name': 'Elowen the Lightbearer', 'emits': 'dim', 'fills_room': True}]
  'Elowen' in compose_prompt(...) -> True
  ```
  - The picture is "lit by Elowen the Lightbearer".
  - The key moves when she walks in or out, against rule 3 ("a bystander is still not one").
- **Verified:** snippet above. The owner's database has 0 person-kind light sources among 57 (kinds: fixture 28, object 12, celestial 11, ...). CONFIRMED mechanism, PLAUSIBLE frequency.
- **Severity:** LEAK (low).
- **Fix:** leave out body-kind entities (and cast or position-holding bodies). The light they give still reaches the picture through `_viewer_light` / `effective_light`.
- **Test:** a person entity carrying `light_source` is absent from `light_sources` and the signature does not change when they leave.

### F5 — Backdrop and ambience caches outlive their chat, and a reused chat id inherits them
- **Where:**
  - `dressing/backdrops.py:271-283` and `:1503-1560`: images and `rooms.json` continuity anchors are keyed by room id under `BACKDROP_DIR/<chat_id>/`.
  - `dressing/ambience.py:392-397` and `:1495-1538`: manifests and beds under `AMBIENCE_DIR/<chat_id>/`.
  - `persist/chat_delete.py:8-43` deletes rows only; nothing removes either directory (grep finds no other cleanup).
  - `chats.id INTEGER PRIMARY KEY` has no AUTOINCREMENT (`core/db.py:507-508`), so SQLite gives a deleted maximum id to the next row:
    ```
    insert a, b; delete b; insert c -> [(1,'a'), (2,'c')]
    ```
- **Scenario:** delete the newest chat, then start or import a new story.
  - `room_anchor(chat, "tavern")` (`:1510-1537`) returns the dead story's tavern image as the anchor every state of the new tavern is edited from, with `backdrop_continuity` on.
  - `set_room_anchor` never overwrites an existing anchor (`:1554-1555`), so the inheritance is permanent.
  - `reusable_manifest` (`ambience.py:1495-1538`) adopts any dead-story bed whose fingerprint is the same room id at ≥0.5 similarity.
- **Verified:** read the deletion path; demonstrated SQLite id reuse. Not executed end to end. PLAUSIBLE.
- **Severity:** CORRUPTION (a new story's on-disk presentation state comes from another story).
- **Fix:** branches read ancestors' directories in place (`branch_lineage`), so deleting the directories outright would strand descendants. Two options:
  - write a marker in each directory (chat `created` stamp, or a uuid) and ignore a directory whose marker disagrees with the live chat;
  - delete the directories only when no chat lists this id in `branched_from`.
- **Test:** create, generate a fake anchor, delete, create (same id), then `room_anchor` returns `(None, {})`.

### F6 — A fourth sentence splitter cuts the stranger label: `referring.SENTENCE_END`
- **Where:** `language_runtime/referring.py:73-75`, used by `first_sentence` (`:262-278`) and `read` (`:394-396`), and re-exported as `agents/common_names.py:187` `_SENTENCE_END`.
- **Code:**
  ```python
  SENTENCE_END = re.compile(r"(?<=[a-z]{3}[.!?])\s+|(?<=[。！？])")
  ```
  - It splits after any abbreviation of four or more letters: `Capt.`, `Prof.`, `approx.`.
  - It never splits after a digit, an acronym or a non-ASCII letter: `40s.`, `RAF.`, `café.`.
  - The pack already owns `_SENTENCE_ABBREVIATIONS` (capt, prof, ...) and `common_names.split_sentences` (`:899`). This splitter uses neither.
- **Scenario:** what `_unknown_actor_label` / `stranger_label_ladder` produce:
  ```
  'A grizzled former Capt. of the harbour guard, broad and scarred.' -> 'the grizzled former capt'
  'A stocky dwarf in his 300s. He wears chainmail.' -> ladder ['the stocky dwarf in his 300s. he wears chainmail']
  'An elderly man of the RAF. He walks with a cane.' -> ladder ['the elderly man of the raf. he walks with a cane']
  ```
  The ladder is what `composer.assign_stranger_labels` (`agents/composer.py:517-530`) hands an observer when two strangers collide. That label goes into every view and memory of that observer.
- **Verified:** snippet output above. CONFIRMED.
- **Severity:** WRONG-SCENE.
- **Not the registered one:** UNBUILT_PIPELINE §1.69 lists THREE remaining splitters that "none ... decides what a mind receives". This one is not in the list and does decide a label.
- **Fix:**
  - Route `first_sentence` and `read`'s split through `split_sentences` and the pack's abbreviation set.
  - Accept any letter, digit or closing bracket before the stop.
  - Keep the full-width stops.
- **Test:** the three summaries above. The label does not end in "capt" and no ladder step contains ". ".

### F7 — `name_boundary_pattern` matches inside longer words in kana and kanji; its docstring promises whole-name matching
- **Where:** `story/character_schema.py:1812-1836`.
  ```python
  lead = "" if _UNSPACED_SCRIPT.match(text[0]) else f"(?<![{_SPACED_WORD_CHARS}])"
  tail = "" if _UNSPACED_SCRIPT.match(text[-1]) else f"(?![{_SPACED_WORD_CHARS}])"
  ```
  The docstring says "Match `form` as a whole name, in whatever script the name is written".
- **The contract it actually keeps, documented here:**
  - It decides per edge of the name, not per language.
  - **Spaced-script edge:** a negative lookaround over spaced-script letters only (Latin and its supplements, Greek, Cyrillic, digits, `_`).
  - **Unspaced edge** (kana, CJK, CJK compatibility, Hangul, Thai): no assertion at all.
  - An empty name gives `(?!)`.
  - It returns a pattern string, `lru_cache(2048)` per name, independent of language. Callers compile it through `re`'s shared cache.
- **The proof the orchestrator asked for comes out the other way:**
  ```
  'ヒナミ' in 'ヒナミは'        -> True (0,3)      (correct: particle)
  'ヒナミ' in 'ヒナミコは来た'  -> True (0,3)      (matches INSIDE the longer name)
  'ヒナミ' in 'アヒナミ'        -> True (1,4)
  'レイ'   in 'プレイヤーは'    -> True (1,3)      ("player")
  'Hinami' in 'Hinamis'         -> False           (Latin control)
  'Hinami' in '彼はHinamiに'    -> True
  ```
- **What it breaks:**
  - **Over-subtraction**, the inverse firewall defect. `story/scene.py:1132` `disguised_visible_appearance`, concealing 「角」 (horns): `'角ばった顎の背の高い女性、額に二本の角がある。'` → `'ばった顎の背の高い女性、額に二本のがある。'`. The angular jaw, which is not concealed, is mangled in every observer's view.
  - **Over-inclusion:** `mind/notebook.py:108-116` `_named_in` ("stands as a whole name ... (any script)") puts notes about 「レイ」 in play wherever 「プレイヤー」 appears.
  - The `mind/theory_of_mind.py:373-375` rekey has the same over-inclusion.
  - Only `agents/common.py` (~6680) compensates, with a longest-first alternation shield.
- **Verified:** snippets above. CONFIRMED.
- **Severity:** STALE-DOC plus WRONG-SCENE.
- **Fix:**
  - State the contract honestly in the docstring.
  - Give unspaced-script callers a set matcher: longest-first alternation over every known form, the class fix `common.py` already uses.
  - For a concealment scrub, require the term to be a registered body-part token, not a bare substring. Owner's call.
- **Test:** `ヒナミ` does not fire inside 「ヒナミコ」 when both are known. The disguise scrub of 「角」 keeps 「角ばった」.

### F8 — `compose_query` cuts off its own "ambience" anchor when a room has nine or more terms
- **Where:** `dressing/ambience.py:683-684`.
  ```python
  out.append("ambience")
  return " ".join(out[:9])
  ```
  It contradicts `_anchored`'s docstring (`:1033`), "`compose_query` always ends on "ambience"", and the prompt card's "END EVERY QUERY WITH 'ambience'".
- **Scenario:**
  ```
  compose_query({'name':'Waystation main hall','desc':'A warm, modest hall where a stone hearth crackles.','anchors':['crackling stone hearth'],'time':'evening'})
  -> 'waystation main hall crackling stone hearth warm modest evening'     (no anchor)
  _query_ladder(...) -> 8 rungs, none containing 'ambience'
  ```
  - With no `ambience_prompt` model, this draft IS the tone layer's query.
  - The `standard` fallback search (`:1839-1847`) uses it too.
  - So a richly described room is searched unanchored, the "kitchen returns knives and cupboard doors" failure the anchor exists to prevent.
  - `test_query_always_asks_for_ambience` (`tests/test_ambience.py:134-137`) passes only because its room has two words.
- **Verified:** snippet. CONFIRMED.
- **Severity:** WRONG-SCENE (wrong bed).
- **Fix:** `return " ".join(out[:8] + ["ambience"])`.
- **Test:** a room with ≥9 distinct terms ends on "ambience", and so does every ladder rung.

### F9 — For an outdoor room, the image-edit prompt is handed a Python dict as a "change" (`ground` means two things)
- **Where:**
  - `dressing/backdrops.py:876`: an open room's brief puts its anchors under `"ground"`.
  - `:1404`: `_REVISION_STATE_KEYS = ("overlays", "weather", "ground")` treats `ground` as STATE.
  - `:1416-1424`: a non-list value is printed with `%s`.
- **Scenario:**
  ```
  compose_revision(room_projection(open hilltop with a cairn anchor), None, {})
  -> "... Change only what follows: ground: {'n': [{'desc': 'a tumbled stone cairn'}]}; time of day: evening. ..."
  ```
  - This fires whenever the anchor image's stored `place` lacks or differs from the current anchors dict: a new fixture, an anchor drawn before the brief existed, a room that became open.
  - The weather floor (mud, snow), which the tuple was meant for, never reaches a revision or a generation (see F16).
  - Only behind `backdrop_continuity`.
- **Verified:** snippet. CONFIRMED.
- **Severity:** WRONG-SCENE.
- **Fix:**
  - Rename the brief's open-room key (for example `features`), or drop it from `_REVISION_STATE_KEYS`.
  - Carry the weather floor's `state` text under its own key.
- **Test:** `compose_revision` for an open room with `previous={}` contains no `{'`.

### F10 — Ambience reads Japanese room text through an ASCII-only tokenizer and English tables, so the bed is blind to a Japanese room
- **Where:**
  - `dressing/ambience.py:625-635`: `_keywords` = `re.findall(r"[a-z][a-z'-]{2,}", ...)`.
  - `_STOPWORDS` (`:562-568`), `_RAIN_SURFACES` (`:693-707`), `_CUE_NEGATIONS` (`:731`).
  - Used by `acoustic_fingerprint` (`:260-307`), `fingerprint_similarity` (`:330-363`), `compose_query`, `rain_surface`, `search_local` and `ranking_terms`.
- **Scenario (ja):**
  ```
  acoustic_fingerprint(ja room) -> {'name': [], 'desc': [], 'anchors': [], 'time': 'evening', 'weather': [], 'genre': [], 'state': []}
  hearth lit vs hearth cold (ja) -> identical signature
  compose_layers(ja place) -> tone query 'evening quiet ambience'; rain_surface -> ''
  ```
  - `_REUSE_EXACT` "anchors" exists to stop "the fire playing in a cold room" (`:320-327`). In Japanese it is always `[]`, so a hearth going out keeps its bed.
  - Every two Japanese fingerprints score 1.0 (`:361-362`), so `reusable_manifest` adopts anything.
  - On search, the room's own words give `ranking_terms(standard) == set()`, so every candidate's `fit` is 0. `target = max(1, min(2, 0)) = 1` is never met: the ladder always runs to the end (prefix rungs plus up to 5 probes), and `resolve_ambience` then runs the `standard` ladder as well (`:1839-1847`).
  - With no `ambience_prompt` model, `intent` is empty and the filter at `:1876-1877` removes every tone candidate (fit 0, intent 0). A Japanese story gets no room tone at all.
- **Verified:** snippets for keying and query. CONFIRMED. The search consequence was traced, not run against Freesound: PLAUSIBLE.
- **Severity:** SILENT-NOOP.
- **Note:** the tables that judge Freesound's tags (`_MUSIC_WORDS`, `_THUNDER_WORDS`, `_FAUNA_WORDS`, `_EVENT_WORDS`, `_LOOP_WORDS`) are rightly English, because the library is indexed in English.
- **Fix:** key and draft from fields that do not depend on the language:
  - anchor ids;
  - `ground.kind`/`state`;
  - `day_phase` (F11);
  - room `exposure`;
  - the barrier kinds;
  - leave the prose to the model.
  Any recogniser over story prose goes through the pack (owner decision 2).
- **Test:** a ja room's signature moves when its hearth anchor's state changes. A ja deterministic draft carries at least one term from the room.

### F11 — Time of day comes from the free-text label through an English table; the canonical `scene.day_phase` is ignored
- **Where:**
  - `dressing/backdrops.py:85-91` (`_TIME_BUCKETS`) and `:131-141` (`time_bucket`).
  - Readers: `visual_signature:236`, `_sky_of:847`, `room_projection:949`, `ambience.acoustic_fingerprint:295` and `room_soundscape:595`.
  - None of them reads `scene.day_phase`, which the day cycle writes (`persist/commit_scene_state.py:186`).
  - `_PHASE_BUCKETS` (`:120-122`) already maps every phase to a bucket.
- **Scenario:**
  ```
  time_bucket('夕方') -> ''   time_bucket('夜') -> ''   time_bucket('午後9時') -> ''   time_bucket('Late in the third watch') -> ''
  ```
  - With an anchored clock, `day_phase` is `'evening'` while `time_of_day` keeps the unreadable label. The day cycle only overwrites it when the label READS as another phase (`commit_scene_state.py:187-189`).
  - So a Japanese story's backdrops and beds never carry the hour.
- **Verified:** snippet, plus a grep showing no `day_phase` in `dressing/`. CONFIRMED.
- **Severity:** SILENT-NOOP. The same fact is stored twice and the reader picks the copy it cannot parse.
- **Fix:** `time_bucket(scene)` prefers `_PHASE_BUCKETS[scene["day_phase"]]` and falls back to the label.
- **Test:** a scene with `day_phase: "evening"`, `time_of_day: "夕方"` buckets to `evening` in both modules.

### F12 — `story_language()` swaps a broken Japanese story to English, with no log or warning
- **Where:** `language_runtime/__init__.py:539-545`.
  ```python
  try:
      return require_language_pack(stored, capability="story").id
  except LanguagePackError:
      return DEFAULT_LANGUAGE
  ```
  This is called by `agents/runtime.py:2136` for every turn.
- **Scenario:**
  ```
  healthy: ja
  adapter broken: en      (_BUILTIN_ADAPTERS['japanese'] pointed at a missing module; no log line at DEBUG)
  ```
  - A Japanese story whose adapter fails to import (a syntax error, a missing dependency) runs every turn with English prompts, recognisers and renderer.
  - The stored `story_language` still says `ja`.
  - The comment at `:698-702` presents the fallback as a feature. LANGUAGE_PACKS.md §6 says "adapters fail closed", and that is true only for selecting a pack, not for an existing story.
- **Verified:** snippet. CONFIRMED.
- **Severity:** SILENT-NOOP / WRONG-SCENE.
- **Fix:** keep the fallback (the owner's "warn, never refuse"), but log once per (chat, error) and add a turn warning (`ctx.add_warning`) naming the stored language and the error.
- **Test:** patch the adapter map; `story_language` returns `en` AND a warning is recorded.

### F13 — `referring` swallows every lookup error and turns a broken pack into empty tables
- **Where:** `language_runtime/referring.py:99-103` (`_values`: `except Exception: return ()`), `:184-189` (`conjunctions`), `:207-216` (`feature_connectives`), `:558-565` (`generic_heads`).
- **Scenario:** rename `label_dangling` or `articles` in both packs. The en→ja parity check passes, because both packs agree.
  - `compositor_value` raises `LanguagePackError`, which is swallowed.
  - `articles()` returns `frozenset()`, so `head_final()` is True for English. English stranger labels silently switch to the Japanese head-final rule.
  - Today every key is present in both packs (checked), so this is dead tolerance that would hide the next rename.
- **Verified:** read, plus a check that all eleven keys exist in en and ja. CONFIRMED (latent).
- **Severity:** SILENT-NOOP.
- **Fix:** catch nothing; `LanguagePackError` is the loud failure the loader designed.
- **Test:** monkeypatch `compositor_value` to raise; `referring.articles()` raises.

### F14 — `overlays` and `conditions` as room-keyed visual and sound state: neither ever matches, and the comments describe a shape nothing writes
- **Where:**
  - `dressing/backdrops.py:65-72` and `:255-266` (key), `:966-971` (projection), `:1404` (revision).
  - `dressing/ambience.py:84-91` and `:276-283` (fingerprint), `:604-606` (soundscape), `:661-662` (query).
  - All look up `scene.overlays[room_id]` and `scene.conditions[room_id]`. The comments promise "smoke, darkness, wreckage", "a fire, a hull breach, flooding".
- **What the data says** (read-only scan of the owner's database, 145 live scenes):
  - `scene.overlays` holds 93 entries and **0** are keyed by a room. Every key is a body ("Hinami", "Sister Odile Verrant"). By schema it is the body owner's output channel (`llm/schemas.py:171`, `:1485`).
  - `scene.conditions` is **None in 145/145** scenes. A diff's `conditions` are committed to the `world_conditions` table (`persist/commit_entities.py:555-556`), never into the scene.
- **Verified:** database scan plus the writer trace. CONFIRMED.
- **Severity:** DEAD / STALE-DOC. The promised behaviour (a burning room is a new picture and a new bed) does not exist.
- **Partly registered:** UNBUILT_PERCEPTION §1.128 registers that the brief does not carry `world_conditions`. The dead room-keyed reads and their comments are not registered.
- **Fix:** delete the two dead reads and fix the comments in one commit. Wire `world_conditions` where §1.128 says.
- **Test:** no change in behaviour. A structural test can assert `_VISUAL_STATE_KEYS` contains only keys a writer produces room-keyed.

### F15 — `cancel_backdrops` and `cancel_ambience` are never called
- **Where:** `dressing/backdrops.py:1738-1746`, `dressing/ambience.py:2060-2067`.
- **What the grep found:** the only references are their own definitions and one docstring mention. There is no route, no call from chat deletion (`persist/chat_delete.py`), none from branch or tests.
  - The cooperative-cancel boundaries inside `generate_backdrop` / `resolve_ambience` are reachable only through `supersede` and process shutdown.
  - Deleting a chat leaves a running generation writing into `BACKDROP_DIR/<cid>`, which is F5's directory.
- **Severity:** DEAD.
- **Fix:** call both from `chat_del` (`web/app.py:4513-4518`) before `delete_chat_data`, or delete them.
- **Test:** deleting a chat calls `cancel_group(cid)` on both queues.

### F16 — The backdrop's cache key changes with the ground's water level, but the prompt never mentions the ground: a paid redraw of an identical prompt
- **Where:**
  - `dressing/backdrops.py:72`: `_VISUAL_STATE_KEYS` includes `ground`.
  - `:255-266` hashes the whole record `{kind, level, state}`.
  - `room_projection` (`:902-980`) and `compose_prompt` (`:1331-1378`) never carry the ground. Their `ground` key is the F9 anchors.
- **Scenario:**
  ```
  ground level 7 -> 8, same state 'standing puddles':
  backdrop signature differs: True | prompts identical: True | prompt mentions puddles: False
  ```
  - The level changes once per window while a room is wetting or draining (`world/weather.ground_after`).
  - Each change is a full image generation (tens of seconds, provider cost) of a byte-identical prompt.
  - This breaks the module's stated rule (`:191-195`): "a key that hashes text the prompt never sees pays for regenerations the picture cannot show".
- **Verified:** snippet. CONFIRMED.
- **Severity:** PERF / SILENT-NOOP.
- **Fix:** carry `ground.state` text in the projection and the prompt, and key only `state`. Or drop `ground` from the visual key.
- **Test:** two scenes differing only in `level` hash the same; differing in `state`, the prompts differ.

### F17 — The backdrop's cache key hashes `scene.location`, which the projection leaves out on purpose
- **Where:** `dressing/backdrops.py:237` (`"location": scene.get("location")` in `visual_signature`) against `:940-948` ("scene.location is NOT included").
- **Scenario:**
  ```
  same room, location 'USS Enterprise' -> 'USS Enterprise-D, Deck 10': signature moved: True | prompt identical: True
  ```
  - `commit_room_registry.py:526-543` leaves a venue-level label standing within a region and replaces it with a room label on other moves.
  - So A → B → A can come back under a different label and buy a second picture of A.
  - Historical checkpoints with stale labels (the module's own example) split one room into several keys.
- **Verified:** snippet. CONFIRMED.
- **Severity:** PERF.
- **Fix:** remove `location` from `visual_signature`'s material.
- **Test:** two scenes differing only in `location` hash the same.

### F18 — The pre-split prompt test now protects 21 of 308 prompt files (7-8% of the text); the docs say accidental edits fail
- **Where:**
  - `tests/test_prompt_card_split.py:341-385` with `tests/data/prompt_cards_presplit/EXPECTED_DIVERGENCE.json`.
  - `_explained` (`:334-337`) excuses a whole subtree for an ancestor key.
- **Measured:**
  - **287 of 308** prompt files in each pack are excused: 92% of en prompt characters, 93% of ja.
  - Excused as whole subtrees: `prose_contract`, `encoder`, `character_bare`, `character_jev`, `jev_questions`, `affect_appraisal`, `character_tools`, `character_thinking`, and others.
  - A listed path means "this text has diverged", so every later edit to it is also free.
- **Docs that overclaim:**
  - `language_runtime/card_source.py:14-17` ("holds it to that against a committed pre-split reference forever").
  - LANGUAGE_PACKS.md §2a (`:168-170`, "an accidental whitespace change costs a red test").
  - AGENTS.md:557 ("the reference test catches it if it happens anyway").
  - UNBUILT_PIPELINE §1.49 (the test "fails if [prose_author_sheet[20]'s space] disappears"). That leaf was deleted on 2026-09-12 and `prose_author_sheet` is now an ancestor entry in the ledger.
- **Verified:** script over `part_plan` and the ledger. CONFIRMED.
- **Severity:** STALE-DOC, and a guard that has quietly lost most of its coverage.
- **Fix:** make the ledger values a hash of the accepted text (`{path: sha256}`). Each edit then rewrites one line, and an accidental change to an already-diverged leaf fails again. The ledger is still enumerated, not re-baselined.
- **Test:** the existing test, comparing hashes.

### F19 — `apply_prompt_policy` comment: "English hides this (its `roles` map is empty)" stopped being true on 2026-08-24
- **Where:** `language_runtime/__init__.py:616-620`.
- **What changed:** `language_packs/en/prompt_policy.json` `roles` = `['interpret_repair', 'narrator']`. It was empty at `77787a64` (2026-08-17) and gained role texts at `2dd6f5dd` (2026-08-24), checked with `git show`.
- **Severity:** STALE-DOC. The duplicate-common risk the comment describes now applies to English too; the code handles it.
- **Fix:** reword the comment.

### F20 — Counts in the pack docs and docstrings are out of date
- **README:**
  - "111 files per pack" (`language_packs/README.md:22`): there are **308**.
  - "all 37 system-prompt families ... the measured count is `len(prompts.DEFAULT_PROMPTS)`" (`:37`): `prompts` has **42** ids and `DEFAULT_PROMPTS` is **93**.
  - "114 deterministic linguistic structures" (`:39`): **163**, across 15 modules.
- **LANGUAGE_PACKS.md:**
  - "111 part files per pack" (`:120`).
  - "substituted four fragments into seventeen bodies" (`:177-178`).
- **`language_runtime/__init__.py`:**
  - "Four authored fragments are embedded in seventeen prompt bodies" (`:148-150`).
  - "a single authored fragment appears in it seventeen times" (`:511-512`).
  - Measured: **8 fragments, 29 references, at most 7 for one fragment** (`card_person_note`).
- **Severity:** STALE-DOC.
- **Fix:** replace the numbers with "see `make structure`", or drop them.

### F21 — `referring` says the engine "has no dictionary", but English grammar is hard-coded in it
- **Where:**
  - `language_runtime/referring.py:15-17` (the claim).
  - `:194` `_COORDINATORS = frozenset({"and", "or"})`.
  - `:153-161` English plural folding: `\d+s`, `-ies` → `-y`, trailing `-s`.
  - `:75` the ASCII `[a-z]{3}` sentence heuristic.
- **Scenario:** Japanese is kept out by its callers (`names_a_body` takes the head-final route; `composer.py:2475` returns early for unspaced text). A third spaced pack (es, fr) would get English coordinators and plurals: "y"/"o" and "et"/"ou" never coordinate.
- **Severity:** STALE-DOC plus a latent language-pack hazard.
- **Fix:** move the coordinators into `compositor.json` (`coordinators`), the plural rule into the pack, and the sentence end per F6.

### F22 — `_setting_only`'s quote class repeats the ASCII `"` where curly quotes were meant
- **Where:** `dressing/backdrops.py:418` `r'[""«»"][^""«»"]*[""«»"]'`.
- **What the bytes show:** the only non-ASCII characters are `«»`, and the class has been this way since the first commit `45179114`. `“ ”` (U+201C/D), which models write, and `「」` are not treated as quotes.
  ```
  _setting_only('A cramped office. “Get out of my office!” The window rattles.')
  -> 'A cramped office. “Get out of my office! ” The window rattles.'
  ```
- **Verified:** bytes plus snippet. CONFIRMED.
- **Severity:** WRONG-SCENE (minor; descriptions rarely quote anyone).
- **Fix:** `[“”«»"「」『』]` on both ends. Better, take the quote set from the pack.

## Efficiency

**E1 — `referring` rebuilds every pack table for every word. Biggest gain, cheapest fix.**
- **Where:** `language_runtime/referring.py:110-222`. `articles()`, `number_words()` (5 compositor lookups plus a 41-word casefold set), `phrase_openers()` (58+12 casefolds), `conjunctions()`, `generic_heads()` and `feature_connectives()` are all rebuilt on every call.
- **Call volume:** `is_boundary()` calls three of them per word; `_cap_phrase` (`agents/common_names.py:275-399`) calls `is_boundary` per word again.
- **Measured:**
  - `read()` = 1.22 ms with 80 `compositor_value` calls.
  - `stranger_label_ladder` = **6.29 ms**.
  - cProfile per label: 378 `compositor_value` calls and 7,120 `casefold` calls.
- **How hot:**
  - `composer.observer_display_map` → `assign_stranger_labels` computes one ladder per UNRECOGNISED visible body, per observer.
  - It is called from `perception.py:6849/7149/8312`, `:2985` and `loops.py:404`, plus 27 `_unknown_actor_label` call sites (narration, memory, background, director views).
  - Order of magnitude: observers × strangers × ≥3 stages per beat. For 4 × 8 × 3 that is roughly 0.6 s per beat. This is an estimate, not a measured turn.
- **Gain:**
  - A scratch prototype memoizing the six tables per `current_language_id` brought the ladder from **6.29 ms to 1.51 ms (-76%)**, with identical output.
  - The ladder does not depend on the observer, so an `lru_cache` keyed on (language, name, appearance, aliases, role, noun) on `stranger_label_ladder` / `_unknown_actor_label` collapses observers × stages to one computation per body.
  - Clear both caches next to `_linguistic_cached.cache_clear()` in `installed_language_packs`.

**E2 — Paid image redraws of an identical prompt (F16, F17).**
- **Where:** `visual_signature` hashes `ground.level` and `scene.location`.
- **Cost:** each key change is a full image generation (tens of seconds, provider cost). During and after rain that is one per window per outdoor room; a relabelled location also forces one.
- **Gain:** it removes every one of those generations. The fix is two lines.

**E3 — A Japanese story's ambience search always runs the whole query ladder (F10).**
- **Where:** `fit` is always 0, so `search_freesound` (`ambience.py:1418-1428`) never stops early. That is up to about 9 Freesound requests per layer, and then the `standard` ladder runs again (`:1839-1847`).
- **How hot:** out of band, once per cache miss.
- **Gain:** about 5-10× fewer API requests per Japanese bed once the room's own terms exist (F10's fix).

**E4 — The backdrop and ambience polls each parse the same checkpoint scene.**
- **Where:** `GET /api/turns/{id}/backdrop` and `GET /ambience` each call `scene_after_turn`.
  - That is a `json_extract` over a checkpoint blob of several megabytes; the module's own measurement is 15.0 ms on the largest (`backdrops.py:1100-1104`).
  - Each also re-resolves `_backdrop_player` (`SELECT * FROM chats` plus the persona) and `style_guide`.
- **How hot:** polled every 3 s (backdrop, up to 70 times) and every 2.5 s (ambience, up to 30 times) while pending, plus once per turn scrolled to (`static/js/backdrops.js:191`, `static/js/ambience.js:86`).
- **Gain:** about half of the poll cost, with a small (chat, turn, checkpoint-rowid) memo shared by both halves. Low priority.

**E5 — `reusable_manifest` reads every manifest in the chat's ambience folder on each miss.**
- **Where:** `ambience.py:1495-1538`. The read is O(states resolved). For every candidate above the threshold it also walks `cached_ambience`'s lineage.
- **How hot:** out of band.
- **Gain:** low. Keep a small fingerprint index file per chat.

**E6 — `installed_language_packs()` copies the pack dict under the RLock on every lookup.**
- **Where:** `language_runtime/__init__.py:399-403`. Every `language_pack()` and `compositor_value()` copies the dict.
- **Measured:** 0.73 µs for the copy; `compositor_value` costs 2.33 µs. The module's own comment says it is called "thousands of times per turn". That adds up to single-digit milliseconds per turn.
- **Gain:** small. Return the frozen map (`MappingProxyType`) instead of copying.

**E7 — `name_boundary_pattern` hands back a string that every caller compiles again (PLAUSIBLE, not measured).**
- **Where:** `story/character_schema.py:1812`. The string is recompiled through `re`'s shared 512-entry cache at about 40 call sites. Long stories with many name forms and other dynamic patterns may churn that cache.
- **Fix:** callers should use `name_boundary_regex` (`:1839`). It is only useful if it is also cached; today it relies on `re`'s cache too.

## Already registered

- **`LanguagePack.fallback` is a dead contract.** Registered as UNBUILT_IDENTITY §1.48. The register's line references are stale: it cites `:154`, `:118`, `:272`; the code is now at `language_runtime/__init__.py:266-267`, `:230` and `:423-425`.
- **`dressing/backdrops.py` `_SENTENCE_SPLIT` splits on a bare full stop.** Registered as UNBUILT_PIPELINE §1.69 (a watch item). Note that §1.69 says only THREE such splitters remain; `referring.SENTENCE_END` (F6) is a fourth, and it does decide what minds receive.
- **The backdrop brief carries no `world_conditions` (a smoke plume, a fire).** Registered as UNBUILT_PERCEPTION §1.128. The brief's empty `lighting` slot is UNBUILT_PERCEPTION §2.34.
- **A sheltered lane draws rain while the backdrop prompt stays dry** (`weather_words(..., "sight")`). Registered as UNBUILT_PERCEPTION §2.11.
- **Ambience layering is capped at three, has no sends, and loopability is guessed from tags** (`_LOOP_WORDS`). Registered as UNBUILT_PERCEPTION §2.12.
- **`_TIME_BUCKETS` is a word table that will need widening.** Registered as UNBUILT_WORLD §2.28. The fix proposed in F11, reading the canonical `day_phase`, is not registered.
- **`ambience_prompt` output is consumed as a raw dict, outside the prompt/schema drift check.** Registered as UNBUILT_PLATFORM §1.61.
- **Story content authored outside the language layer stays English, and a story does not record which pack version wrote it.** Registered as UNBUILT_IDENTITY §1.48.
- **English restraint synonym tables, and the class "route recognisers through the packs" (owner decision 2).** Registered as UNBUILT_WORLD §1.65. F1, F10, F11 and F21 are instances of this class in `dressing/` and `referring`, which the register does not name.
- **RTL is accepted but unimplemented; the UI scanner is broad; the `$note` convention does not exist yet.** Recorded in LANGUAGE_PACKS.md (moved out of UNBUILT).
- **UNBUILT_PIPELINE §1.49 is itself stale.** It describes `prose_author_sheet/20_world_pressure.txt`, retired 2026-09-12, and `specialists/body/chunks/conditions.txt`, whose chunks went 2026-09-27, as live. It also says the pre-split test protects that trailing space; `prose_author_sheet` is now an ancestor entry in the ledger (F18).

## Structure notes

**Module-level mutable state and who writes it**
- `language_runtime`:
  - `_packs` and `_pack_failure` are rebound with `global` only in `installed_language_packs`. Other modules import the function, not the names, so there is no stale-import hazard.
  - `_renderers` is mutated under `_lock` by `register_renderer`.
  - `_linguistic_cached` is an `lru_cache(1024)`; 163 names × 2 packs = 326 entries.
  - `current_language_id` is a ContextVar:
    - set and reset by `agents/runtime.py:2136/2173` (in `finally`), `language_scope`, `director_rooms.py:2784/2788`, `commit_memory_write.py`, `commit_background.py:5682/5725`;
    - streamed on one thread by `web/app.py` `_drain_on_own_thread`, so the set survives every `next()`.
- `dressing`: `_GEN_LOCKS`, `_AMB_LOCKS` (`outofband.KeyedLocks`) and two `outofband.Queue`s. `core/outofband.py:176` threads do not copy the context, unlike `core/jobs.py:130`. That is harmless today only because the dressing code makes no pack lookups (traced: zero `linguistic` calls) and pins English deliberately.
- `story/character_schema.name_boundary_pattern`: `lru_cache(2048)`, process-wide, independent of language.

**Latent hazards, not findings**
- `_linguistic_cached` hands every caller the SAME mutable objects: 9 `$type: set` values (`_REACTIVE_VERBS`, `_MENTAL_VERBS`, `_SENTENCE_ABBREVIATIONS`, ...) and 16 plain dicts (`_PRONOUN_GROUPS`, `AFFECT_LEXICON`, ...). One caller mutating one would corrupt it for every story in the process. A scan of every module-level binding found no mutator today. Decoding `set` as `frozenset` and dicts as `MappingProxyType` would make the hazard impossible.
- The lock in `_linguistic_cached` (`:744-748`) does not fully close the race its comment describes: `lru_cache` stores the result after the function returns, which is after the lock is released. Only `refresh=True` (`tools/project_check.py`, `tools/split_prompt_cards.py`) can trigger it, never the server.
- Three spellings of "which scripts are unspaced", free to disagree:
  - `character_schema._UNSPACED_SCRIPT`: kana, CJK, CJK compatibility, Hangul, Thai.
  - `referring._CJK`: kana, CJK, half-width katakana; no Hangul or Thai.
  - `referring._NOMINAL_END`: CJK, katakana, phonetic extensions, half-width.
  The differences are partly deliberate (Korean spaces its words), but nothing states which question each one answers.
- `refine_prompt` (`backdrops.py:1446-1464`) and `refine_layers` (`ambience.py:797-862`) swallow every exception with no log. The backdrop module's own lesson, "THE FALLBACK WAS CORRECT AND INVISIBLE" (`:1643-1655`), applies to them too: a misconfigured prompt role degrades silently. PLAUSIBLE; the provider layer may log, and this was not traced.
- `pack_source_files()` lists the files held at startup. A part file added later is not flagged by `core.code_version`, but it is an orphan, so the next restart refuses to load the pack.
- `language_packs/ja/translation_exceptions.json` is mode 0600 in this checkout; the other pack files are 0664. Git does not carry this, so it is local only.

**Natural seams for the split program**
- `dressing/ambience.py`, 2,103 lines:
  - (a) settings and pins, 120-231;
  - (b) keying (fingerprint, signature, similarity), 233-390;
  - (c) cache I/O (`manifest_path`, `_as_layered`, `cached_ambience`, `reusable_manifest`, `_write_manifest`);
  - (d) query composition (stopwords, `_keywords`, `compose_query`, rain surfaces, `compose_layers`, `refine_layers`), 556-862;
  - (e) sources and ranking (`library_files`, `search_local`, the Freesound page, sound, ladder and ranking), 865-1438;
  - (f) resolution (`build_ambience_request`, `_materialize`, `_pin_manifest`, `resolve_ambience`), 1441-1907;
  - (g) one-shots, 1910-2001;
  - (h) the queue facade.
  Candidates: `ambience_query.py` (d), `ambience_freesound.py` (e), `ambience_cache.py` (b+c).
- `dressing/backdrops.py`, 1,782 lines:
  - (a) time and keying;
  - (b) the people strip and visual register: the English word tables, which belong in a pack (F1);
  - (c) the brief, 618-899;
  - (d) the projection;
  - (e) prompt and revision composition, 1199-1464;
  - (f) continuity anchors, 1489-1577;
  - (g) generation and queue;
  - (h) database readers (`scene_after_turn`, `player_view_for_turn`, `branch_lineage`).
  `ambience` imports backdrops' private `_room_of_player` together with `branch_lineage`, `place_desc`, `scene_after_turn` and `time_bucket`. That shared-readers module is the natural seam (`dressing/scenery_common.py`).

**Monoliths in miniature**
- `ambience.resolve_ambience`, about 222 lines (1686-1907).
- `ambience._rank_candidates`, about 105.
- `backdrops.generate_backdrop`, about 116.
- `language_runtime._load_pack`, about 108.
- `referring.read`, about 78.
- `installed_language_packs`, about 66.

## Docs checked

**AGENTS.md**
- AGENTS.md:446 (stranger label, `referring` functions and the pack keys it reads): HOLDS. All eleven keys exist in both packs.
- AGENTS.md:489 (`time_bucket` is "the one place a free-text label is categorised ... CATEGORIES-not-vocabulary"): PARTLY. It is a vocabulary table plus a clock reading, and the canonical `day_phase` is ignored (F11).
- AGENTS.md:495 (`effective_adjacent`: "Never re-derive it ... leave ... ambience undirected"): FAILS in `ambience.room_soundscape` and `backdrops.room_projection.exits` (F3).
- AGENTS.md:528 (backdrop brief: "a whitelist with no concept of an occupant ... The key is a function of what reaches the image"): FAILS on the key half (`ground`, `location`; F16, F17) and on the whitelist half (raw exit names, light-source people; F3, F4).
- AGENTS.md:557 (prompt text: "the reference test catches it if it happens anyway"): MOSTLY FAILS. 92% of prompt text is excused (F18).
- AGENTS.md:558 (a story-capable pack must "never silently fall back to English guards"): FAILS. `story_language()` falls back silently (F12), and `dressing/` keeps English-only recognisers outside the packs (F1, F10, F11).

**Design.md:1107-1121** (backdrops "structurally excludes occupants"; ambience "cannot report a presence perception did not deliver")
- HOLDS for entities and positions.
- FAILS for a Japanese description (F1), a person emitting light (F4), raw exit names reaching the model (F3), and the awareness floor (F2).

**LANGUAGE_PACKS.md**
- §2a "111 part files": STALE (308).
- "an accidental whitespace change costs a red test": STALE (F18).
- "four fragments into seventeen bodies": STALE (8 and 29).
- §3 "including worker threads and queued jobs": HOLDS for `core.jobs`, not for `core.outofband`. Harmless today.
- §6 "adapters fail closed": holds for SELECTING a pack; for an existing story it fails OPEN to English, silently (F12).
- "silently falling back to English recognition ... would disable guards": the loader holds this at the key level (en ⊆ ja, verified).

**`language_packs/README.md`**
- "111 files", "37 families", "114 structures": STALE (F20).
- "an omitted surface fails installation instead of falling back silently": HOLDS for keys.

**Docstrings and comments**
- `card_source` module docstring ("forever"): STALE (F18). Its fault list (missing, empty, BOM, CR, orphan, traversal, non-canonical): HOLDS. Every one raises `CardSourceError`, which `_read_card` wraps into `LanguagePackError` (`__init__.py:122-125`) and which is cached as a failure.
- `language_runtime._resolve_prompt_fragments` and `raw_card` docstring counts: STALE (F20). The `apply_prompt_policy` comment: STALE (F19).
- `character_schema.name_boundary_pattern` ("whole name ... in whatever script"): FAILS for unspaced scripts (F7).
- `referring` module docstring ("no dictionary"): FAILS (F21). Its head-final description (last clause if the sentence ends on a noun, else the first nominal clause): HOLDS against `head_final_clause`.
- `ambience._anchored` ("`compose_query` always ends on ambience"): FAILS (F8).
- The overlay and condition comments in both dressing modules: STALE (F14).
- `_light_sources_in` ("occupant-free by construction"): FAILS (F4).

**Owner memory "Edits reach the live server" / `core.code_version` claims about packs**
- "the language packs it reads once and keeps": HOLDS. They load once per process and are never reloaded by the server.

## Appendix — answers to the assignment's particular questions

**(1) What the language runtime promises**

*`name_boundary_pattern(form)`* lives in `story/character_schema.py:1812`, not in `language_runtime`.
- It decides per edge of the name, not per language.
- A spaced-script edge gets `(?<![Latin/Greek/Cyrillic/digit/_])` or `(?!...)`.
- An unspaced-script edge (kana, CJK, compatibility ideographs, Hangul, Thai) gets NO assertion. It therefore matches a particle-suffixed name (「ヒナミは」 ✓) AND inside longer words (「ヒナミコ」, 「アヒナミ」, 「プレイヤー」 for レイ).
- An empty name gives `(?!)`.
- It returns a pattern string, cached per name string with `lru_cache(2048)`.
- Proof snippet and consequences: F7. **The requested proof that it does not match inside 「ヒナミコ」 is false; it does.**

*`linguistic(module, name, language_id=None)`*
- The language is the explicit argument, else `current_language_id`, normalised.
- Cache: `_linguistic_cached`, `lru_cache(1024)` keyed (language, module, name), holding DECODED values (compiled regex, tuple, frozenset, set, dict). It is cleared when the packs reload. The values are shared objects (Structure notes).
- A missing key raises `LanguagePackError` "lacks linguistic transform", loudly.
- An unknown or uninstalled language id resolves silently to its base language, then English (`language_pack`, the documented forgiving read path).
- `compositor_value` and `compositor_text` raise loudly on a missing key or template, or a template that cannot be filled.

*`referring`*
- These are pure functions over the ACTIVE pack's compositor and linguistics tables, read through `current_language_id` on every call with no caching (E1).
- **Article languages (Latin):** an article-led clause promises a noun, and the head is the last word before a boundary (an opener, participle, conjunction or measure).
- **Head-final mode** (no `articles`, or text that is mostly CJK by `unspaced()`): the noun-bearing clause is chosen by script facts; ideographs or katakana at the end mean a noun.
- It swallows all lookup errors (F13), splits sentences by an ASCII heuristic (F6), and hard-codes English coordinators and plurals (F21).

*The ContextVar*
- Set at `run_pipeline` start (`agents/runtime.py:2136`) and reset in its `finally` (`:2173`).
- `web/app.py` drains the generator on one thread inside one `context.run`, so the value survives every yield.
- Worker pools copy the context: `_stream_one`/`_stream_parallel`, `skip_work`, `skip_stage`, `background`, `commit_memory_write`, `director_prose`, `director_repair`, `memory_routes`.
- `core.outofband` does not copy it (dressing is unaffected).
- `make structure` checks that turn-scoped contextvars are cleared.

*Silent English fallback*
- **At the key level, NO.** A story pack missing any en leaf path in authoring/compositor/linguistics/system_prompts, any en prompt id, or (for a UI pack) any en UI key fails the whole load. The failure is cached and the server does not start.
- **At the pack level, YES, silently:**
  - `story_language()` returns `en` on any `LanguagePackError`, including an adapter that fails to import (F12);
  - `ui_language()` does the same;
  - `language_pack()` resolves an uninstalled id to its base language, then `en`.

**(2) Pack parity** (script: `<review scratch>/dlr/parity.py`)

| card | en leaves | ja leaves | only in en | only in ja | type mismatches | ja empty where en is not | byte-identical non-empty |
|---|---|---|---|---|---|---|---|
| linguistics | 410 | 540 | 0 | 130 (ja-only dict entries: `_PRONOUN_GROUPS.彼`, `_OMISSION_CATEGORY_ALIASES.会話`, `AFFECT_LEXICON.不安` ...) | 0 | 0 | 233 (234 counting one empty list) |
| compositor | 472 | 529 | 2 (`body_part_counters`, `counter_numerals`: empty dicts in en, filled in ja; not a parity break, since `_leaf_paths` skips an empty dict) | 59 | 0 | 7 (`articles`, `indefinite_article.*`, `linking_participles`, `pose_bare_determiners`, `surface_adjective_join`; by design) | 0 |
| authoring | 2 | 2 | 0 | 0 | 0 | 0 | 0 |
| system_prompts | 672 | 672 | 0 | 0 | 0 | 0 | 6 (`nsfw_prompt_ids`, `specialists.*.order`; structural) |

- **The 233 identical non-empty linguistics values:** 199 are the English halves of the omission-alias and affect-lexicon tables, which ja keeps for code-switching. The other 34 are English morphology (`_YOU_AGREEMENT`, `_YOU_VERB_RE`, `_TONE_NOUN_SUFFIXES`, `_ES_STEM_ENDINGS`, `_SENTENCE_ABBREVIATIONS`, pronoun groups) and English diagnostic prefixes (`_ENFORCEABLE_PREFIXES`, which match engine-written English warnings, so identical is correct).
- **Flag drift:** four ja regexes drop flags English has: `persist.commit_memory._STATION_POSSESSED_BEFORE` 34→32, `story.scene._ABSENCE_RE` 2→0, `story.scene._DANGLING_TAIL_RE` 2→0, `mind.skip_memories._NUMBER_RUN` 2→0. Each is a pure-Japanese replacement with no English branch, so case does not matter. They also drop the English code-switch branches the guide asks packs to keep.
- **`\b` placement:** the 23 ja regexes that have `\b` next to kana have it on the ENGLISH branches only. Correct by guide rule 4.
- **Other files:** `ui.json` 2897/2897, identical 338 = 338 recorded exceptions. `prompt_policy` roles: en {interpret_repair, narrator}, ja adds `character_bare`, a live prompt id. Not compared by any check.

*`tools/project_check.check_language_pack_surfaces`* (`tools/project_check.py:997-1232`)

It COVERS:
- en card prompt ids plus Director sheets == `DEFAULT_PROMPTS`;
- every prompt (except encoder pieces) carries "LANGUAGE AND SCHEMA CONTRACT";
- the en UI catalog is fresh;
- for each non-en pack:
  - the unchanged UI values == `translation_exceptions` keys, whose reasons must be non-empty, not machine-generated and not an echo;
  - canonical-token drift in UI values and prompts;
  - no prompt body of ≥160 characters is byte-identical to English;
- for every pack:
  - no blank prompt text where en has text;
  - every linguistics regex compiles, with the same capture-group COUNT as en;
  - compositor template fields are a subset of en's, and every template parses;
  - no `⟦⟧` mask markers left in the prompt, compositor, authoring or UI files.

It does NOT cover:
- regex flags, named groups, or per-branch anchors (guide rule 3);
- types or emptiness of non-regex linguistics and compositor values;
- missing template fields;
- `prompt_policy` roles;
- ja-only keys (whether anything reads them);
- the English recognisers that live outside the packs (`dressing/`, `referring._COORDINATORS`, `composer._SEQUENCERS`): no pack-level check can see code tables.

**(3) Backdrops and ambience**
- **Hidden state sent to the providers:**
  - Neither payload carries another mind's secret, concealed lines or a Director event.
  - Both send OBJECTIVE room data: name, description, anchors, light sources, edges, region look. That is Director truth about the player's room, sent regardless of what the player perceives (F2).
  - The firewall-relevant gaps are F1 (Japanese descriptions unstripped), F3 (raw edge names), F4 (people emitting light) and F2 (the awareness floor).
  - Freesound receives search keywords only. For English rooms those can include description words, which are third-party exposure of story text, not of a mind.
- **The sentence-splitter class:** `backdrops._SENTENCE_SPLIT` is registered (§1.69). `referring.SENTENCE_END` is new (F6).
- **English word tables against the ja pack:** F1 (people, body, visual register), F10 (keywords, stopwords, rain surfaces, negations), F11 (time). The tables over Freesound's tags are correctly English.
- **Caching:**
  - Images and beds are cached by content-addressed signature (picture: room plus visible state; sound: room plus audible state).
  - PROMPTS are not cached. They are recomputed only on a miss, inside the generation lock, with the model refining once per miss (backdrop `force` regenerates and re-asks; an ambience reroll reuses the stored per-layer queries).
  - Nothing runs per beat in the pipeline. Each GET poll recomputes the signature (E4).
  - Key churn without any visible change: F16, F17. Keys blind to visible changes: F10 (Japanese), F14 (dead state keys).

**(4) `card_source`**
- **How cards are loaded:** once per process, inside `installed_language_packs()` → `_load_pack` → `_read_card` → `expand_card_parts`. That means the index JSON plus every referenced `.txt`, with orphan detection by `rglob`, then fragment resolution, then freezing.
- **Reloads and staleness:** there is no mtime check and no reload. `refresh=True` is used only by tools. `core.code_version` content-hashes `pack_source_files()` at startup and warns, never reloads, when the disk diverges.
- **`raw_card` / `read_card_source`** re-read from disk on every call; they are used only by tests and tools.
- **What `EXPECTED_DIVERGENCE.json` protects:** it pins the assembled `system_prompts` card of each pack to the byte-for-byte pre-split reference (`tests/data/prompt_cards_presplit/{en,ja}.json`, frozen 2026-08-30). Any leaf that changed, was added or was removed must be listed with a reason. Its reach is now 21 of 308 files (F18).

**(5) Efficiency summary**
- Pack JSON is NOT re-read per call; it loads once.
- Regexes are compiled once per (language, transform) by `_linguistic_cached`. The dressing and referring code compiles string patterns through `re`'s shared cache.
- The real costs are `referring`'s table rebuilding (E1, -76% available) and the paid image redraws from key/prompt disagreement (E2).
