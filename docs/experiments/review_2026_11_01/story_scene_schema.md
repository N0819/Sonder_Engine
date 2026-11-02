# Audit: story/scene.py, story/character_schema.py, story/naming.py and six small story modules

Auditor: story-scene-schema lane. Working tree at 84f3de23 (branch `worktree-jev-character-tracking`), 2026-11-01.
Read-only. One focused test run (`tests/test_ability_isolation.py`, 1 passed). Snippets ran on `.venv`
(Pydantic 2.11.7). Owner DB (`engine.db`) was opened `mode=ro` only, for counts.

## Scope read

Read in full, every line:

- `story/scene.py` 1-3195
- `story/character_schema.py` 1-2781
- `story/naming.py` 1-555
- `story/dialogue_colors.py` 1-268
- `story/lore_structure.py` 1-248
- `story/authored_events.py` 1-299
- `story/provenance_text.py` 1-132
- `story/opening_plan.py` 1-128
- `story/prelude.py` 1-189

Read as context for callers and claims (partial, the line ranges named):

- `web/app.py` 1258-1345 (branch id remap), 3455-3850 (the character routes), 4380-4410, 4545-4605,
  4840-4875, 4967-4998, 5070-5095, 5380-5470 (per-story card PUT), 6015-6070 (dialogue config route)
- `agents/director.py` 1940-1990, 2115-2175 (`flow.dice`), 5377-5411 (dice roll), 6415-6425, 7440-7460,
  7530-7540, 7595-7615
- `agents/director_evidence.py` 2890-3020; `agents/perception.py` 1070-1082, 3255-3340, 4215-4240
- `agents/common_cast.py` 281-400 (`cast_spelling_policy`); `agents/common_views.py` 195-260, 596-650
- `persist/commit_background.py` 2065-2140, 2925-2945, 4889-4930, 4990-5050, 5100-5225
- `persist/commit_attire.py` 99-160; `persist/commit_entities.py` 96-140, 560-630; `persist/commit_mapping.py` 120-145
- `story/attire.py` 659-836, 3425-3450; `story/importers.py` 470-614, 800-860, 960-1010, 1860-1900 (plus
  the `return` lines of 1101-1700); `story/greetings.py` 955-985
- `world/charter_identity.py` 425-800 (reservation, LCS, Jaro-Winkler); `world/offscreen.py` 1120-1135,
  1495-1512, 2199-2230; `mind/knowledge_circles.py` 40-60
- `core/db.py` `wget`/`wset`/`wget_for_frame`; `llm/schemas.py` 250-305, 1317-1325, 4945-5000;
  `tools/project_check.py` 2021-2090
- Encoder cards `language_packs/en/cards/system_prompts/encoder/conditions__form.txt`,
  `conditions__restraint.txt`; `language_packs/ja/cards/linguistics.json` (`story.scene`,
  `agents.common._APPEARANCE_LABELS`)
- Registers grepped for every name below: `docs/UNBUILT*.md`.

Skimmed only (not audited): the rest of `web/app.py`, `story/importers.py`, `story/attire.py`.

## Findings

### F1 — LEAK: an authored empty `known_to` is read as "never filled in", so every acquaintance sees through an identity disguise

- **Where:** `story/scene.py:1282-1298` (`disguise_known_to`), fed by `story/scene.py:793-805`
  (`disguises_from_rows` collapses the field to a list).
- **Code:**
  ```python
  listed = (disguise or {}).get("known_to") or []
  for n in listed:
      who.add(str(n).strip().casefold())
  if not listed:
      subj_cf = str(subject_name or "").casefold()
      for observer, knows in (known_map or {}).items():
          if any(subj_cf == str(k).casefold() for k in (knows or [])):
              who.add(str(observer).casefold())
  ```
- **Failure:** the encoder card (`encoder/conditions__form.txt`, PHYSICAL DISGUISE (c)) asks for
  `known_to` = "the characters who legitimately KNOW the real form". A disguise nobody has been told
  about is therefore written `known_to: []` — 3 of the 18 live `physical_disguise` rows are exactly
  that. `disguises_from_rows` turns both "authored empty" and "field absent (legacy)" into `[]`, and
  `disguise_known_to` then applies the legacy backstop: every observer whose recognition map knows the
  subject is added to `known_to`. Perception (`agents/perception.py:3292`) feeds that set to
  `disguise_breaks_recognition`, so for a disguise with `conceals_identity: true` (a mask, another's
  uniform) every acquaintance recognises the masked body — the disguise fools only strangers, i.e. none
  of the people it exists to fool — and the concealed-term tripwire treats those acquaintances as aware,
  so a leak to them is not flagged either. A cooperating model writing the correct `[]` produces the
  leak; that is the engine's failure, not the model's. The commit side already names this exact trap
  (`persist/commit_entities._supersede_disguises`: "an empty value must not mean both 'authored as
  empty' and 'never filled in'") — the read side never adopted it.
- **Verified:** snippet over `disguises_from_rows` → `disguise_known_to` → `disguise_breaks_recognition`:
  row `state={known_to: [], conceals_identity: True}`, known map `{"Captain Holt": ["Mara"]}` →
  `known_to = ['captain holt', 'mara']`, Captain Holt recognition broken: **False**, a stranger: True.
  Live DB: `known_to=[]` on 3/18 disguise rows; none of those 3 also carries `conceals_identity: true`
  yet, so end-to-end it is PLAUSIBLE; the helper chain is CONFIRMED.
- **Fix:** carry "some row carried the key" out of `disguises_from_rows` (e.g. `known_to_authored`) and
  apply the known-map backstop only when no row carried it.
- **Test:** `disguises_from_rows` with `state.known_to=[]`, `conceals_identity=True` → an observer in
  the known map is not in `disguise_known_to(...)` and `disguise_breaks_recognition` is True; a row with
  no `known_to` key keeps the backstop.

### F2 — CORRUPTION: the first per-story card save of a uid-less card persists a minted uid, rekeying the cast entity id and the knowledge-circle key

- **Where:** `web/app.py:5405-5427` and `5454-5458` (`chat_char_card_put`); the keys it moves:
  `story/character_schema.py:2043-2063` (`cast_entity_id`), `mind/knowledge_circles.py:47-56`
  (`identity_key`).
- **Code:**
  ```python
  sheet = normalize_character_data(body.get("sheet") or {})
  ...
  # Very old cards may genuinely have no stored uid; the normalized editor
  # supplies one on their first save. Once a uid exists it is immutable.
  if (
      raw_identity.get("uid")
      and str(identity.get("uid") or "") != str(current_identity.get("uid") or "")
  ):
      raise HTTPException(400, "A story character's identity uid cannot be changed")
  ...
  "UPDATE chat_chars SET sheet=?,state=? WHERE chat_id=? AND char_id=?",
  (json.dumps(sheet, ensure_ascii=False), ...
  ```
- **Failure:** `normalize_character_data` mints a fresh `char_<hex>` for a card with no uid (and the
  chat GET at `web/app.py:4560` hands the editor a normalized, freshly minted copy each load). The uid
  check is skipped because the raw card has none, and the minted uid is written into
  `chat_chars.sheet`. From then on `authored_uid` finds it: `cast_entity_id` flips from
  `character:<row id>` to `char_<hex>` (orphaning `subject_last_seen` rows keyed by the old id,
  `world/gaps.py:387`) and `identity_key` flips from the casefolded name to the uid (orphaning every
  circle membership the character earned in play, `agents/character.py:3869-3871` — a mind silently
  loses compartment knowledge). CLAUDE.md and AGENTS.md row "Per-story character-card edits" both say
  uid is locked for exactly these keys. The library-card route escapes this only by accident (its
  `old_uid` is itself freshly minted, so the snapshot always fires).
- **Verified:** snippet: raw `{"identity":{"name":"Mara Quill"}}` → before save
  `cast_entity_id=character:12`, `identity_key='mara quill'`; after persisting the normalized card
  `cast_entity_id=char_3d91…`, `identity_key='char_3d91…'`. Owner DB: 6 of 183 attachments read a
  uid-less effective card (3 library cards). Not registered (grep `uid` in UNBUILT*). CONFIRMED.
- **Fix:** when the stored raw card has no authored uid, persist the edited sheet without
  `identity.uid` (a minted uid is not authored), so `cast_entity_id`/`identity_key` keep their fallback.
- **Test:** attach a uid-less card, PUT its normalized form back with the name unchanged → stored sheet
  has no uid; `cast_entity_id(stored, id) == "character:<id>"`.

### F3 — CORRUPTION: an authored event's identity includes the chat id, and branching remaps it to a random id — idempotent re-mint breaks in every branched, cloned or imported chat

- **Where:** `story/authored_events.py:129-144` (`_event_id`), `166-182` (the "live row absorbs its
  echo" check); `web/app.py:1324-1334` (`_build_world_id_remap` registers every `scheduled_events.event_id`).
- **Code:**
  ```python
  key = " ".join(str(summary or "").casefold().split())
  digest = hashlib.sha256(f"{cid}:{key}".encode("utf-8")).hexdigest()[:20]
  return f"authored:{digest}"
  ```
  ```python
  for ev in blob.get("scheduled_events") or []:
      reg(ev.get("event_id"))          # -> uuid4().hex[:16]
  ```
- **Failure:** the table's key is already `(chat_id, event_id)` (`core/db.py:1221-1231`), so `cid` in
  the hash buys nothing and costs the guarantee. A branch copies a pending authored event under a random
  16-hex id; an archive import keeps the id but the new chat's `cid` changes the digest. When the
  Director re-emits the still-standing assertion (the module docstring calls this routine), the lookup
  at :179 misses, a second pending row is inserted with a fresh requeue budget, and both are delivered
  as due — the multiplication the docstring says this id exists to prevent.
- **Verified:** traced `mint_authored_events` → `_event_id`, `web/app.py:1307-1331` and the PK. Not
  registered. CONFIRMED by trace (not executed).
- **Fix:** hash the normalised assertion alone (`_event_id(summary)`), and exempt `authored:` ids from
  the branch remap.
- **Test:** mint a summary in chat A, copy its row into chat B under a remapped id (or run the branch
  helper), re-mint the same summary in B → `minted == 0`, one pending row.

### F4 — WRONG-SCENE: `seed_initial_attire` tests membership by exact key, so a case-variant (or uid/alias) spelling of a dressed body gets the card's outfit seeded beside its live clothes

- **Where:** `story/scene.py:67-71`. Callers: `persist/commit_background.py:5210` (promotion),
  `web/app.py:4862` (attach), `4399` (persona change), `5083` (extra persona), `story/scene.py:101-115`
  (scene creation).
- **Code:**
  ```python
  ledger = scene.setdefault("attire", {})
  if name in ledger:
      return False
  ```
- **Failure:** `attire.entry_for`'s own docstring calls it "THE ONLY WAY TO READ ONE BODY'S WARDROBE"
  because the ledger key is not reliably canonical; the seed's existence test bypasses it. A presence
  the Director dressed as `mirela` promoted to a card named `Mirela` (the vitals block four lines above
  documents this very spelling split, B4) gets a second record holding the drafted `initial_outfit`.
  `key_for` prefers the exact key, so every reader now sees the card outfit; at the next commit
  `_heal_attire_identity_keys` (`persist/commit_attire.py:141-157`) folds `mirela` into `Mirela` by
  UNION, so the body wears its live clothes and the card's starting outfit at once. That is the
  forbidden overwrite (AGENTS.md "Seed once and never reset existing attire from a card").
- **Verified:** snippet: ledger `{"mirela": authored_entry(["wet shift"])}`, `seed_initial_attire(sc,
  "Mirela", {"wearing": ["green wool dress", "leather boots"]})` → `True`, keys
  `['Mirela', 'mirela']`, `key_for → 'Mirela'`. Merge read in `_heal_attire_identity_keys` /
  `cast_spelling_policy`. CONFIRMED for the seed, PLAUSIBLE end-to-end.
- **Fix:** test existence through `attire_model.key_for(ledger, name)` (and the cast spelling policy
  where a cast is in reach); a body held under any of its spellings is not re-seeded.
- **Test:** the snippet above returns False and leaves the ledger unchanged.

### F5 — WRONG-SCENE: the player's short name is never recognised as the player when it is under four characters — every Japanese given name of 1-3 kana/kanji, and Latin ones like "Kai"

- **Where:** `story/scene.py:2207-2211` (`is_player_speaker`).
- **Code:**
  ```python
  if s_norm and len(s_norm) >= 4:
      for a in aliases:
          a_words = {fold_identity_key(w) for w in a.split()}
          if s_norm in a_words:
              return True
  ```
- **Failure:** the floor counts code points; four Latin letters are a short name, four kanji are a whole
  one. A line the model attributes to "ヒナミ" (persona "佐藤 ヒナミ") or "Kai" ("Kai Rowan") is not the
  player's: `agents/director.py:7451` skips the player-speech authority check (a Director-invented player
  line under the short name survives as a bystander's), `7603` does not retag it to `p_name`, and
  `agents/perception.py:4222/4234` grade it from `cast_room(...)`/`_bg_rooms` — not the player's room.
- **Verified:** snippet (`persona_of` stubbed): `佐藤 ヒナミ / ヒナミ → False`, `Hinami Sato / Hinami →
  True`, `Mira Vale / Mira → True`. Not registered. CONFIRMED.
- **Fix:** the floor exists to keep substring-ish tokens ("the") out; whole-token equality already does
  most of that. Judge the floor per script (`character_schema._UNSPACED_SCRIPT`) or replace it with a
  stopword exclusion; the number is the owner's.
- **Test:** the three pairs above, plus `"Al"` vs `"Alex Chen"` → False.

### F6 — WRONG-SCENE (ja): an authored event in an unspaced language can never be "fired", so it is re-delivered as due twice after it happened

- **Where:** `story/authored_events.py:214-215`, `246-262`, using `agents/common_views.py:220-232`
  (`_content_tokens`).
- **Code:**
  ```python
  rtoks = set(_content_tokens(resolved_text or ""))
  ...
  stoks = set(_content_tokens(ev["summary"]))
  narrated = _covers(stoks, rtoks)
  ```
- **Failure:** `_content_tokens` splits on `[^\w]+`; an unspaced Japanese sentence is one token. The
  summary's single token matches the resolved prose only if the prose contains the identical clause
  between punctuation, so a Japanese assertion is effectively never `narrated`/`covered`, nor `stale` by
  retirement. It is requeued (`MAX_REQUEUES = 2`) and handed back to the Director as a due,
  resolve-now event on the next two beats — inviting a second and third enactment of a thing that
  already happened — then goes stale. The "narrated and encoded in no channel" warning can never fire.
- **Verified:** `_content_tokens('エレベーターが地下に墜落する') → ['エレベーターが地下に墜落する']`
  (one token); English splits into three. CONFIRMED (tokenizer), PLAUSIBLE end-to-end.
- **Fix:** tokenize through the language pack (segment unspaced scripts, e.g. character bigrams) in
  `_content_tokens`, or give `authored_events` its own pack-aware comparator.
- **Test:** a Japanese summary and a resolved text that enacts it in other words → `fired == 1`.

### F7 — WRONG-SCENE (ja): the provenance floor deletes a whole Japanese room description, and lets a Japanese provenance note through

- **Where:** `story/provenance_text.py:74` (`_BRACKETED_RE`), `78` (`_SENTENCE_RE`), `50-66` (patterns).
  Delivery floors: `agents/composer.py:1041,1052`, `agents/common_rooms.py:803`; persist:
  `persist/commit_mapping.py:135`, `persist/commit_scene_state.py:2152`.
- **Code:**
  ```python
  _BRACKETED_RE = re.compile(r"[\(\[][^\)\]\n]{1,300}[\)\]]")
  _SENTENCE_RE = re.compile(r"[^.!?\n]*(?:[.!?\n]+|$)")
  ```
- **Failure:** sentences end only at ASCII `.!?`; Japanese `。` is not a boundary, so
  `港の事務所。机が並ぶ。generated because no candidate described this location.` is ONE "sentence",
  matched, and filed wholesale as provenance — the view (and the persisted description) gets nothing.
  Conversely a Japanese note in full-width brackets `（候補がなかったため自動生成）` matches neither the
  ASCII bracket class nor the English vocabulary and reaches the view. The module's own premise is that
  this floor must not depend on a model cooperating.
- **Verified:** snippets: first → `('', '港の事務所。机が並ぶ。generated because …')`; second → passed
  through unchanged. CONFIRMED (mechanism), PLAUSIBLE (reach).
- **Fix:** split on the pack's `_SENTENCE_ENDS`, add full-width brackets, move the vocabulary into the
  pack (keeping English for code-switching).
- **Test:** the two snippets as assertions.

### F8 — WRONG-SCENE: the naming reservation reads the LIBRARY card's name, not the name the story plays under

- **Where:** `story/naming.py:166-172` (`_person_name_evidence`) and `324-330`
  (`registered_identity_names`); same well in `persist/commit_background.py:4918`
  (`_refuse_name_collision`).
- **Code:**
  ```python
  "SELECT ch.name AS name FROM chat_chars cc "
  "JOIN characters ch ON ch.id=cc.char_id "
  "WHERE cc.chat_id=? ORDER BY cc.char_id"
  ```
- **Failure:** `char_edit` (`web/app.py:3827-3836`) supports renaming a library card by snapshotting the
  old card into every attachment without its own — after which the story's person is the snapshot's
  name and `characters.name` is the new one. Every other cast reader resolves `COALESCE(cc.sheet,
  ch.sheet)`; these three read `ch.name`, so the in-story name is unreserved: the presence mint, the
  Charter body allocator and promotion can each issue a registered person's name to a stranger.
- **Verified:** read; owner DB currently has 0 divergent attachments, so PLAUSIBLE.
- **Fix:** read `character_name_from_text(COALESCE(cc.sheet, ch.sheet))` (and reserve both names).
- **Test:** attach, rename the library card, then `registered_identity_names(cid)` contains the old name.

### F9 — WRONG-SCENE (ja): name reservation cannot see the family name inside an unspaced registered name (reached through `story.naming.story_identity_reservation`)

- **Where:** `world/charter_identity.py:429-430` (`_tokens`), `494-508` (`_reserves_component`),
  `549-583` (`reconstructs_a_reserved_name`, `NAME_RUN_FLOOR`/`NAME_PREFIX_FLOOR` = 4).
- **Failure:** `_tokens` splits on whitespace, so a cast member `佐藤ヒナミ` is one run; no component of a
  candidate can match its start or end, and the LCS/prefix floors (4 code points) never fire on 2-3
  character kanji/kana names. A minted `佐藤タロウ` passes beside her — two people the story addresses as
  佐藤 — and `ヒナミコ` passes although it carries her whole given name. The owner ruled the numbers;
  what is not ruled is that they are measured in code points regardless of script.
- **Verified:** snippet: runs `('佐藤ヒナミ',)`; `_reserves_component(res,'佐藤') → False` (True when the
  registered name is written `佐藤 ヒナミ`); `reconstructs('ヒナミコ') → False`;
  `reconstructs('Crushen') → True`. UNBUILT_IDENTITY (around line 720-775) registers the exact-share and
  the JW wiring, not this. CONFIRMED.
- **Fix:** segment unspaced names before tokenizing (the Japanese adapter), and state the floors per
  script (owner's numbers).
- **Test:** the snippet as assertions.

### F10 — WRONG-SCENE (non-English lorebook): the knowledge tree's classifier is an English keyword list over free prose

- **Where:** `story/lore_structure.py:133-140`, `160-171`, `215-230`; called from
  `story/importers.py:1882-1886`.
- **Failure:** section names in any other language match no table: a "writing style" scaffolding entry
  is classified `common/global` world knowledge (the docstring calls excluding it "the single most
  valuable thing the tree buys"), and locality is never derived. `\b` inside `_matches` would not bound
  an unspaced word either.
- **Verified:** read; PLAUSIBLE (no non-English book measured).
- **Fix:** move the four vocabularies into the language pack; at least report "no section matched" on
  import.
- **Test:** a book with Japanese section titles for style/location → `(None, None, None)` and `local`.

### F11 — SILENT-NOOP: `_ability_mod` is handed an identity handle and returns 0 (confirming agents_director_core F6)

- **Where:** `story/scene.py:2144-2171`; caller `agents/director.py:5404`, actor from
  `agents/director.py:2164-2170` (`entry.get("source_entity_id")`), which `director_evidence.py:2908-2912`
  normalises to `persona:N` / `character:N`.
- **Call shape confirmed:** `_ability_mod(d.get("actor"), d.get("ability"), ctx)` with
  `actor = "persona:7"` or `"character:58"`; the function compares `actor` against persona-name aliases
  and `name_of(sheet)`. Snippet: `Bob → 6`, `character:2 → 0`, `persona:7 → 0`.
  `tests/test_ability_isolation.py` passes because it pins display names, which production never sends.
  Extra players (`persona:<other>`) have no path at all. Already reported by
  `audits/agents_director_core.md` F6 (with the measurement that no encoder card asks for
  `ability`/`difficulty`), so not counted as new.
- **Fix:** resolve the handle through the identity index (`row["id"]`, `chat.persona_id`, extra players).

### F12 — SILENT-NOOP / CRASH: `character_card_warnings` runs on all ten surfaces, but three of its warnings cannot fire on the input nine of them pass, and the one raw surface crashes after it has committed

- **Where:** `story/character_schema.py:2664-2728` (interior and outfit-region warnings), comment
  `2709-2711`; surfaces `web/app.py:3476, 3501, 3516, 3597, 3710, 3719, 3749, 3765, 3791, 3800, 3842,
  4997, 5468`, `story/importers.py:980`.
- **Failure (a):** every surface except `confirm_promotion` passes a NORMALIZED card
  (`normalize_character_data` in the route, or the `fill_*`/`generate_*` helpers' `return
  normalize_character_data(...)`). Normalization drops nameless interior stations, truncates to 8 and
  re-homes stray outfit regions, so "a station with no name", "declares N stations" and "places clothing
  at …" are structurally unable to fire — including on `fill_interior`, the surface that produces
  interiors. The comment says the import and editor surfaces "hand in" the raw card; they do not.
- **Failure (b):** `confirm_promotion` passes the raw body sheet; `sheet.get("psychology") or {}` then
  `.get("drive")` raises `AttributeError` on a scalar where a mapping belongs — after
  `promote_background_character` has written the character, so the host sees a 500 for a promotion
  that succeeded (and a retry is refused as a name collision).
- **Verified:** snippet: the same sheet raw → no-name/too-many/stray-region all True; normalized → all
  False. `character_card_warnings({"psychology": "brave"})` → AttributeError (also
  `{"psychology": {"drive": "…"}}`, `{"embodiment": {"visible": "tall"}}`). Wiring of all surfaces
  verified by grep. UNBUILT_WORLD (around line 968) notes warnings read a flattened OUTFIT for the
  regions-vs-wearing case only. CONFIRMED.
- **Fix:** run the structural checks on the raw authored input each route already holds
  (`body["sheet"]`, the model's parse) and the semantic ones on the normalized card; make every `.get`
  type-tolerant.
- **Test:** PUT a card with a nameless station → the response carries the warning;
  `confirm_promotion` with `psychology: "brave"` → 200 with warnings.

### F13 — SILENT-NOOP (authored content lost): a drive written as a string is dropped by normalization, and the warning then says none was authored

- **Where:** `story/character_schema.py:295-299` (`_mapping_fields`), `237-239` (default),
  `2578-2585` (the warning).
- **Code:**
  ```python
  @validator("drive", "self_model", "coping", "stress_profile", "learning", pre=True)
  def _mapping_fields(cls, value):
      return value if isinstance(value, dict) else {}
  ```
- **Failure:** `"drive": "to keep her brother alive whatever it costs"` — the most natural way a model or
  an author writes it — normalizes to `{"essence": "", …}`; import, generation and every edit surface
  persist the normalized card, so the text is gone. The warning reports "No drive was authored", which
  is false. This is the field CLAUDE.md calls "the worst of them". `_pronouns` and
  `_with_normalized_outfit` set the precedent this skips: a field that can READ the scalar does.
- **Verified:** snippet → drive `{'essence': '', 'expression': '', 'taboo': ''}` and the "No drive"
  warning. Live cards are all dicts, so frequency PLAUSIBLE; mechanism CONFIRMED.
- **Fix:** read a string drive as `{"essence": text}` before validation (same seam for `self_model.summary`).
- **Test:** `normalize_character_data({"psychology": {"drive": "x"}})["psychology"]["drive"]["essence"] == "x"`.

### F14 — STALE-DOC / DEAD: `dialogue_config` forces the retired ladder keys, which permanently disables all three off-screen tick schedulers — while its own comment and the register say the toggle still derives the rung

- **Where:** `story/scene.py:2527-2536` (comment) vs `2554-2567` (code); readers
  `world/offscreen.py:1126-1131, 1506-1508, 2225-2227`, `world/living_world.py:266`;
  `extension_runtime/api.py:2385-2401` (`provision_story(offscreen_life=...)`).
- **Code:**
  ```python
  config["offscreen_life"] = OFFSCREEN_LIFE_DEFAULT
  config["offscreen_cognition"] = OFFSCREEN_COGNITION_DEFAULT
  config["max_offscreen_actors"] = 0
  ```
- **Failure:** the comment block at 2527-2536 ("the toggle wins … An explicitly STORED rung wins …
  the rung follows it") describes a derivation the code 30 lines below removed. With
  `max_offscreen_actors = 0`, `stochastic_ticks` (`cap > 0`), `schedule_profile_ticks` (`cap <= 0`) and
  `schedule_agent_ticks` (`cap_zero`) can never run; `living_world`'s ceiling is always `stochastic`; an
  extension's published `provision_story(offscreen_life=...)` is stored and ignored, as is the
  `web/app.py:6029-6069` route's own comment ("`dialogue_config` derives the ladder rung from it").
  UNBUILT_LIVING_WORLD §1.105 still says the toggle "still enables … `schedule_profile_ticks` and
  `schedule_agent_ticks`". `cognition_from_rung` (`scene.py:2368`) has no caller.
- **Verified:** read and grep; the 2554 comment confirms intent ("present, defaulted and unread").
  CONFIRMED.
- **Fix:** rewrite 2527-2536, update §1.105 and the route comment; whether to delete the three schedulers
  and the contract parameter is the owner's call.

### F15 — SILENT-NOOP: the two readers of `initial_state.goals` disagree about a goal written as a string

- **Where:** `story/character_schema.py:2274-2275` (`character_initial_active_state`) vs `2323-2324`
  (`character_standing_intentions`, which accepts strings on purpose).
- **Failure:** `goals: ["find the lost ledger"]` gives a standing intention but `active_state.goal == ""`
  — the value the memory query ("what you are trying to do", `mind/memory_context.py:422`), the Jev
  packet (`mind/memory_jev.py:373`) and `agents/offscreen_beat.py:473` read before the first commit.
- **Verified:** snippet → `'' [{'id': 'ia1', 'intent': 'find the lost ledger', …}]`. Live cards are all
  dicts; PLAUSIBLE.
- **Fix:** accept a string `goals[0]` in `character_initial_active_state`.

### F16 — SILENT-NOOP: a cast member dormant when the scene is created never receives their authored outfit

- **Where:** `story/scene.py:103-106` (`_seed_scene_initial_attire` iterates `active_cast` only); no
  seed on dormant→active (`commit_cast_changes`), and the attach route seeds only `if not ex`
  (`web/app.py:4859-4865`).
- **Failure:** attach three characters, make one dormant (`chat_del_char`) before the opening; when the
  Director brings them in, the ledger has no entry for them and nothing ever seeds one, so every view
  carries no clothing for that body until a beat happens to dress it.
- **Verified:** grep of all five seed callers. PLAUSIBLE.
- **Fix:** seed `extant_cast` at creation (clothing belongs to the body, not to presence).

### F17 — CRASH: `apply_awareness_diff` converts `active` unguarded; its sibling guards it (and reads null the opposite way)

- **Where:** `story/scene.py:1535` vs `1778-1782`; callers `agents/director_movement.py:3002, 3162`.
- **Code:** `if not int(cond.get("active", 1)) or level == "awake":`
- **Failure:** `state_diff.conditions` entries are untyped dicts (`llm/schemas.py:2299`;
  `_coerce_conditions` does not touch `active`), so a model writing `"active": null` or `"false"` raises
  `TypeError`/`ValueError` in the movement floor. `apply_restraint_records_diff` catches the same error
  and treats null as ACTIVE — two answers to one field.
- **Verified:** snippet: restraint overlay keeps the record; awareness overlay → `TypeError int()
  argument … 'NoneType'`. CONFIRMED (helper), PLAUSIBLE reach.
- **Fix:** one `_condition_active(cond)` helper (with `world_conditions`' commit writer, which has the
  same unguarded `int()` at `persist/commit_entities.py:145, 222, 615, 636`).

### F18 — DEAD: branches and values nothing reaches

- `story/scene.py:2090-2142` `director_context(..., entitled=False)`: no caller passes `entitled=False`
  (repo-wide grep, tests included); the mapping consumer its docstring guards was made deterministic.
- `story/scene.py:2030-2088` `recent_events_for_observer` with a real observer: only tests call it; the
  one production path is `recent_events` (observer None).
- `story/scene.py:2368-2374` `cognition_from_rung`: no caller.
- `story/scene.py:2855-2856, 2927-2928` `STYLE_GUIDE_AUTO` and the `key == "genre"` branch: unreachable
  (`STYLE_GUIDE_FIELDS = ("tone", "avoid")`); the in-code comment already says so (E39), not registered.
- `story/prelude.py:176-177`: `chat = q("SELECT scenario …")`, `passage = …` — computed, never used.
- **Verified:** grep. CONFIRMED.

### F19 — STALE-DOC: scene.py comments that name things that are not so

- `story/scene.py:58-66` `seed_initial_attire`: "The merge happens HERE rather than in the card so a
  cue-table guess is never written back". The card normalization DOES fold `wearing` into regions by
  the cue table (`character_schema._normalize_initial_outfit`, whose docstring says so on purpose) and
  `char_edit`/`chat_char_card_put`/create/import persist it. Snippet: `{"wearing": ["silk sash",
  "leather boots"]}` → regions `{'waist': ['silk sash'], 'feet': ['leather boots']}`.
- `story/scene.py:785, 830`: `_supersede_singular_conditions` does not exist; the superseder is
  `persist.commit_entities._supersede_disguises` (as `scene.py:1896` correctly says).
- `story/scene.py:1401`: `awareness_conditions` "in id order" — it re-sorts by `started_at_seconds` (1456).
- `story/scene.py:1578-1585`: "No prompt publishes `RESTRAINT_LEVELS` -- the body specialist is handed a
  parenthetical" — the encoder card `conditions__restraint.txt` publishes `level ∈
  {held|bound|pinned|encased}`; the body specialist was deleted 2026-09-27 (same for "social
  specialist" at 242-244).
- `story/scene.py:1979-1986`: `recent_events` "Both of them -- mapping_stage and mapping_quick … becomes
  a lore entry or a scene_patch room note" — one deterministic caller (`agents/mapping.py:82`) that mints
  nothing.
- **Verified:** grep and snippets. CONFIRMED.

### F20 — STALE-DOC: the dialogue colour hashes the drive too, so a drive edit repaints the whole backlog unannounced

- **Where:** `story/dialogue_colors.py:28-33` (module), `87` ("Traits and values only.") vs `125-129`.
- **Failure:** `personality_digest` appends `drive.essence`; the docstrings warn authors only about traits
  and values. A psychology fill or a drive edit re-colours three hundred turns of dialogue with nothing
  saying it would. Fix the docs (or drop the drive from the digest — owner's taste).
- **Verified:** read. CONFIRMED.

### F21 — STALE-DOC: `derive_knowledge` describes a leaf "veto" that no longer exists

- **Where:** `story/lore_structure.py:237-241` vs `246-247`.
- **Failure:** "The veto applies only to a LEAF … That is where "Od Lagna" sits … A rule about how the
  world works is true and known the same way everywhere." There is no veto: a leaf under a Locations
  heading returns `local` unconditionally — which is what the block at 174-192 and the removal of the
  `category` parameter decided. A reader restoring the "missing" veto would re-introduce the rejected
  behaviour.
- **Verified:** read. CONFIRMED.

### F22 — STALE-DOC: provenance_text says a prompt asks for a structured `provenance` field; nothing does

- **Where:** `story/provenance_text.py:16-17, 33-35`; the reader `persist/commit_mapping.py:136`.
- **Failure:** no card under `language_packs/*/cards/system_prompts` asks for `provenance` on a lore or
  layout op, and there is no mapping model role; `op.get("provenance")` reads a field no producer
  writes, so the English-only floor (F7) is the whole mechanism, not a backstop.
- **Verified:** grep. CONFIRMED.

### F23 — WRONG-SCENE (ja): English model-facing labels and defaults beside localized siblings

- `story/scene.py:3167, 3171, 3181`: three of the four `private_knowledge` `source` labels ("your own
  private history", "private knowledge shared by {owner}", "something you privately know about them")
  are English literals in the character payload (`agents/character.py:4586`); the fourth uses
  `linguistic("story.scene", "_ALREADY_KNOWN_SOURCE")`.
- `story/scene.py:682` "no notable appearance recorded" (not in `_APPEARANCE_LABELS`), `440-446`
  `persona_of` fallback ("The Stranger", English appearance/senses), `story/character_schema.py:753, 898,
  2090, 2404` default summary "A person of unremarkable appearance." (written INTO new cards),
  `2448-2467` `senses_as_text` ("ordinary senses", "{acuity} {channel}, {range} range"), `1197-1209`
  `_coerce_appearance` "Build: …" labels, `story/opening_plan.py:45-47` the opening mandate sentence.
- **Verified:** grep of both packs. CONFIRMED (presence), effect on ja views PLAUSIBLE.
- **Fix:** route through `linguistic(...)` like the fourth label already does.

## Efficiency

- **E1 — persona normalised twice per `is_player_speaker`, per dialogue line.** `story/scene.py:2173-2183`:
  `_player_aliases` → `persona_of` (one `personas` query + `normalize_persona_data(json.loads)`) →
  `persona_name(pers)` (a second full normalization: personas have no `NormalizedCharacterSheet`-style
  mark). Called per dialogue line at `agents/director.py:6422, 7451, 7537, 7603` and
  `agents/perception.py:1078, 4222, 4234`. Measured: 0.36 ms per normalization on the median in-use
  persona (1.6 KB), 3.2 ms on the largest (11 KB) → 0.7-6.5 ms + 1 query per call; a 10-line beat makes
  dozens. 88 `persona_of` and 101 `persona_name` call sites repo-wide. Fix: memo `persona_of` by
  (persona_id, sheet text) as `normalized_character_from_text` does and mark its product; or compute the
  alias set once per beat. Cheap, large where personas are big.
- **E2 — `_cast_private_histories` is O(cast²) per beat.** `story/scene.py:3080-3106`, reached per
  character payload via `private_knowledge_for` (`agents/character.py:4586`) and again via
  `own_private_history`. Each call re-queries every cast row (all statuses), deep-copies each normalized
  card from the memo (0.77 ms at the owner's largest 40 KB card) and re-parses each state (0.77 ms at
  54 KB), plus `persona_of` and a `persona_name(pers)` per shared persona entry inside the loop (3179).
  Max cast in the owner DB is 7 → ~50 card copies + parses per beat. Fix: one per-beat read.
- **E3 — `sheet_state` deep-copies the normalized card on every call.** `story/scene.py:424` →
  `character_schema.stored_card_from_text:1497-1500`: 1.23 ms per call at 40 KB (0.77 ms of it the
  deepcopy) whether or not the caller asks a normalized question; 14 call sites, 11 in
  `agents/perception.py` per stage per cast row. Fix: normalize lazily on first
  `normalize_character_data(card)`.
- **E4 — un-memoized full normalizations.** `_seed_scene_initial_attire` (`scene.py:104-106`:
  `character_name` + `character_initial_outfit` on a plain dict, 6.6 ms each at 40 KB, per cast row, per
  `get_scene` call until the opening commits) and `_ability_mod` (`2161-2164`, per cast row per dice
  entry; dead in practice). Fix: `normalized_character_from_text`.
- **E5 — `world_conditions` scanned and parsed once per family.** `awareness_conditions`,
  `restraint_conditions`, `active_condition_rows`, `active_disguises`, `active_transformations` each
  SELECT the chat's active rows and `json.loads` every payload, several times per beat across stages.
  Unmeasured; small today (363 active rows over 50 chats), grows because 360 of them never expire. One
  per-beat parsed snapshot would serve all five.

## Already registered

- UNBUILT_WORLD §1.46 — `normalize_transformed_parts` repairs transformation parts on read; the producer
  still writes free text.
- UNBUILT_LIVING_WORLD §1.105 — the off-screen ladder/toggle (its text is now stale against
  `dialogue_config`; see F14).
- UNBUILT_IDENTITY (around lines 720-775, the name-material section) — exact surname share at the mint,
  `NAME_ELEMENT_FLOOR`, Jaro-Winkler wired to place words only. F9 is a separate (script) gap.
- UNBUILT_IDENTITY (around 300-322) — disguise coverage vs familiarity; "witnessing grants knowledge".
  Adjacent to F1, not the same defect.
- UNBUILT_PERCEPTION (around 150-165) — the attire ledger is not scrubbed for disguised features.
- UNBUILT_WORLD (around 955-968) — card warnings read an already-flattened outfit (regions vs wearing).
- UNBUILT_CHARACTERS (around 622-633) — a populated-field threshold for sparse imports.
- `audits/agents_director_core.md` F6 (another lane, not a register) — the dice path (F11 here).

## Structure notes

- **`story/scene.py` is eight modules.** Natural seams: (1) cast roster and per-story state
  (`extant_cast` … `sheet_state`, `chat_character_sheet`, `cast_scene_context`, private knowledge);
  (2) scene materialisation (`get_scene`, the two seeders, `_lay_beat_onset`); (3) appearance, disguise,
  transformation (`appearance_of` … `disguise_known_to`, ~500 lines); (4) world conditions — awareness,
  restraint, `active_condition_rows`, `condition_exit_owner` (~600 lines, a clean `story/conditions.py`);
  (5) the omniscient-history readers with redaction (`recent_events*`, `director_context`); (6) player
  speaker resolution and dice; (7) chat dials (`dialogue_config`, the off-screen ladder, background,
  reaction, promotion, player authority, style guide, weather, tense, clock); (8) `dialogue_budget`.
- **Monoliths in miniature:** `get_scene` (85 lines, five independent responsibilities, three of them
  broad-`except`), `dialogue_config` (comments longer than the code, now contradicting it),
  `character_card_warnings` (190 lines, 11 checks with two input contracts — F12), the legacy branch of
  `normalize_character_data` (a 130-line literal).
- **`story/character_schema.py`** holds name-matching utilities that are not card schema
  (`name_boundary_pattern`, `fold_identity_key`, `cue_boundary_pattern`, `_UNSPACED_SCRIPT`) and a second
  unspaced-script table lives in `scene._UNSPACED_RUN` — one script table, two spellings.
- **Module-level mutable state:** only process-wide `lru_cache`s, all keyed by immutable text —
  `_normalized_from_text` (1024 × ~34 KB), `character_name_from_text` (512), `_identity_from_text` (512),
  `name_boundary_pattern` (2048), `_canonical_card_shape` (1). No writers besides the decorators.
- **Swallowed failures:** `scene._seed_scene_from_plan:625-628` (`except Exception: pass`) hides a real
  failure to seed planned rooms — the exact "invented square" failure its docstring measures — while its
  two siblings in `get_scene` log; `get_scene:498-499`; `_redact_for_observer` fails closed (correct).
- **Kind matching disagrees three ways:** `condition_exit_owner` casefolds the kind
  (`scene.py:1922`), `_supersede_disguises` and the `active_disguises` SQL match it exactly. Inert today
  (all 30 live rows exact).
- **Pydantic (question 4):** in `story/character_schema.py` — `from pydantic import … validator` (13);
  a second major read `_PYDANTIC_V2 = hasattr(BaseModel, "model_validate")` (19-21, duplicate of
  `llm/schemas.py:255`); V1 `class Config: extra = "allow"` (123-124); thirteen V1 `validator(...)`
  sites at 151, 154, 165, 168, 180, 183, 195, 228, 231, 271, 277, 286, 295 (13
  `PydanticDeprecatedSince20` warnings at import on 2.11.7, measured), plus the V1-only `@validator("*")`
  at 139; `allow_reuse=True` everywhere; `_profile` (302-312) re-implements `llm.schemas._validate/_dump`
  with different semantics (no `exclude_none`, no `_plain` enum flattening) — the second branch
  `check_pydantic_major_reads_are_owned` exists to prevent but cannot see (it flags field attributes
  only). All of it is removed in V3; `pydantic>=1.10.13,<3` holds it off. Same class outside these
  files: `story/couriers.py:869`, `story/artifacts.py:227`, `story/carriers.py:1197` use
  `op.dict() if hasattr(op, "dict") else op` — on V3 that silently passes a model object on;
  `llm/schemas.py` (91 V1 validator sites, two `class Config`), `persist/chat_archive.py:236, 245`.
- **JSON parsing in the small modules (question 7):** `authored_events.py:205, 258` catch
  `TypeError/ValueError` but then call `payload.get` on a non-dict JSON value (crash on `null`/list);
  `prelude.py`/`opening_plan.py` parse nothing themselves (`wget` does). Payloads are always written as
  dicts by their own writers, so this is robustness only.

## Docs checked

- CLAUDE.md "`scene.active_cast` resolves [`chat_chars.sheet`] over the reusable `characters.sheet`" —
  HELD in `active_cast`, `extant_cast`, `all_cast_name_to_id`, `chat_character_sheet`,
  `_cast_private_histories`; NOT in `naming.registered_identity_names`/`_person_name_evidence` (F8).
- CLAUDE.md "never permit a card edit to rekey the in-story identity name or uid" — name: HELD (400 at
  `web/app.py:5419-5420`; library rename snapshots attachments, 3827-3836). uid: FAILS for uid-less cards (F2).
- CLAUDE.md / AGENTS.md row 548 "seed once … no card read or edit may overwrite clothing already changed"
  — HELD for an exact-key body; FAILS for a case-variant/uid/alias key (F4); dormant-at-creation never
  seeded (F16).
- CLAUDE.md "`character_card_warnings` … now runs on all ten surfaces" — HELD as wiring (13 route sites +
  the promotion draft); three warnings dead on nine surfaces, one surface crashes (F12).
- CLAUDE.md "psychology … an empty drive … `character_card_warnings` catches this" — HELD for an empty
  dict; a string drive is erased and then reported as never authored (F13).
- AGENTS.md naming paragraph ("`registered_identity_names` (the persona and `characters.name`, the two
  wells …)") — accurate as a description; the well is the library name (F8).
- AGENTS.md row 551 "identity name/uid are locked because scene and knowledge records use them as keys" —
  see F2.
- Design.md row 415 (naming law; mint in `commit_background._mint_missing_presence_names`; GET/PUT
  `/api/chats/{cid}/naming_profile`) — HELD (`persist/commit_background.py:2065-2140`,
  `web/app.py:6254-6271`).
- UNBUILT_LIVING_WORLD §1.105 ("`dialogue_config` derives the rung … still enables the machinery") —
  DOES NOT HOLD (F14).
- `tools/project_check.check_pydantic_major_reads_are_owned` — enforces field attributes only; the
  character_schema major branch and `_profile` are outside it (Structure notes).
- `story/provenance_text.py` docstring "the mapping prompt now asks for a structured `provenance` field"
  — DOES NOT HOLD (F22).
