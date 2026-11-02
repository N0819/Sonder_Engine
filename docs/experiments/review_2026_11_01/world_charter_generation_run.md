# Audit: world/charter_{generate,run,practice,skip,predation,history,trigger,social,author}.py

Auditor scope as assigned. Read-only; no repo file touched. Probes ran on `.venv/bin/python`, pure in-memory or on a scratch DB under the scratchpad (never `engine.db`). This auditor's probe scripts are `<review scratch>/charter_audit/skip_short_end.py`, `<review scratch>/charter_audit/leased_prey.py`, `<review scratch>/charter_audit/registry_graph.py`, `<review scratch>/charter_audit/quarrel_life2.py` and `<review scratch>/charter_audit/quarrel_life.py`. Other files in that directory belong to another auditor.

**A premise correction first.** The five commits named in the assignment (f9ba52ae, 4d398090, 8e3c60f2, 17a2b3cb, 1342bbde) do **not** touch `world/charter_skip.py`. They touch `agents/skip_stage.py`, `agents/skip_work.py`, `world/skip_itinerary.py` and `llm/llm_quality.py` (`git show --stat`). `charter_skip.py`'s own history is dbbe5532, 8557e755 and cb69070e (2026-10-21). Question (3) is answered against the code those five commits changed, as it meets `charter_skip`.

## Scope read

Read in full, every line:
- `world/charter_skip.py` 1-1096
- `world/charter_run.py` 1-1640
- `world/charter_generate.py` 1-1949
- `world/charter_history.py` 1-897
- `world/charter_trigger.py` 1-881
- `world/charter_social.py` 1-865
- `world/charter_practice.py` 1-1203
- `world/charter_predation.py` 1-1063
- `world/charter_author.py` 1-813

Read in part, as each finding needed:
- `agents/skip_stage.py`: 300-371 (`skip_block`, `ask`) and 671-860 (`skip_lives`), 896-1010 (`FarEnd`).
- `world/skip_itinerary.py`: 341-566 (expansion, `AT_THE_END_SECONDS`), 1415-1452 (`stretch_outcome`), 1532-1560 (`_row`), 1764-1962 (`lay_over`, `judge_without`, `carry_sleep`, `far_end_of`).
- `world/charter_runtime.py`: 929-960, 1243-1300, 2420-2470, 3075-3420 (`charter_scene`, `sync_minds_to_scene`, `advance_snapshot`), 4500-4570 and 5790-5815.
- Sibling charter modules, only at the lines cited: `charter_model`, `charter_space`, `charter_move`, `charter_place`, `charter_intervene`, `charter_figure`, `charter_log`, `charter_mind`, `charter_news`, `charter_politics`, `charter_harm`.
- `story/journey_history.py` 185-262 and 300-352. `story/greetings.py` around 1050 and 1085-1115. `web/app.py` 6160-6180. `story/prelude.py` 175-190.
- Commit diffs read in full: 8e3c60f2 (code part) and 1342bbde.
- f9ba52ae, 4d398090 and 17a2b3cb: only the stat and the current text of the functions they changed that meet `charter_skip` (`stretch_outcome`, `judge_without`, `lay_over`, `told_rows`, `_part_tag`). The full 600-line test diff and `skip_work.py` beyond `told_rows`/`told_account` were not read.
- Docs: `docs/design/DESIGN_THE_CAST_ACROSS_A_SKIP.md` in full. The `AGENTS.md` rows 442, 459, 490 and 491; the `Design.md` rows 347-348; and the cited `docs/UNBUILT_*.md` sections.

Not read: the other 30 `world/charter_*.py` modules beyond the cited lines. `docs/design/DESIGN_CHARTER_PLACEMENT.md`, `DESIGN_CHARTER_PLACES.md`, `DESIGN_CHARTER_SPATIAL_PROMOTION.md` and `DESIGN_CREATURES_AS_CHARTER.md` were only skimmed by grep.

## Findings

### F1 — The predation round kills, takes and hurts bodies the scene holds on screen: deterministic on-screen conduct

- **Location:** `world/charter_predation.py:133-160` (`_company`), `:502-640` (`_attack`), `:608` (`apply_harm(prey, target_key, ...)`), `:713-745` (the encounter loop).
- **Code:** `_company` indexes every body that is `available` and not gone, with no lease test. `_attack` then calls `apply_harm(..., outcome=outcome, ...)` on the drawn target.
- **What the rule is.**
  - `charter_move.walk` (`world/charter_move.py:572-577`) refuses to move a leased body: "ON SCREEN, THE SCENE MOVES IT ... (owner, 2026-09-14)".
  - `charter_place.lease_scene_bodies` (`:503-533`) says that while a body stands in the player's aperture, "the scene keeps its row and the Director moves it".
  - The module's own `figure` branch (`:555-575`) says "what happens to the people there is the pipeline's ruling and not a dice roll in a background window". It therefore only FILES a `creature_on_figure` event.
  - Nothing in `charter_predation.py`, `charter_harm.py` or `charter_creature.py` reads `leased`. A leased townsperson standing in the scene is ordinary `unposted`/`posted` prey, and a leased creature body still attacks.
- **Scenario.** A creature registry, so `advance_snapshot` takes the `together` arm and calls `run_registry` (`charter_runtime.py:3215`, `:3307`). A wolf body reaches the room where the player is talking to a leased townsperson. The out-of-band charter tick after the commit draws the attack and writes `condition: dead` on the registry body. The Director never ruled it, and the scene still shows the person standing there.
- **Verification:** probe `charter_audit/leased_prey.py`. Setup: `small_town` plus `wolf_pack`, prey `["unposted"]`, odds 1.0, one unposted body with `leased: "present"` standing with the pack. Result: "seeds where the leased body was harmed: 30 of 40", for example `(39, 'dead', 'present', ['harm_done'])`.
- **Confidence:** CONFIRMED.
- **Severity:** WRONG-SCENE. It violates the 2026-09-14 lease ruling and "never deterministic onscreen conduct".
- **Fix (the class: a body the scene holds is the Director's to endanger).** In `predation_round`, leave leased prey bodies out of `_company`, or file them as `creature_on_figure` does. Do not let a leased creature body enter the encounter loop.
- **Test:** the probe's setup as a focused test: no harm to the leased body, and one filed encounter row.

### F2 — In a charter story, the skip's far end ignores the final stretch, so the account's offer and `at_the_end` are lost

- **Location:** `world/charter_skip.py:582-592` (`_directive` picks the stretch at the window's MIDDLE) and `:925-928` (`far_end` reads the run body's `place`). It meets `world/skip_itinerary.py:94` and `:531` (`at_the_end` is the last `AT_THE_END_SECONDS` = 1800 s).
- **Code:**
  ```python
  middle = max((start + end) / 2.0, self.span_from)
  for row in self.stretches:
      if row["from_s"] <= middle < row["until_s"]:
          return {"room": row["room"], ...}
  ```
  `far_end`: `place = str(body.get("place") or "")`.
- **Scenario.**
  - Windows are at most 2 h (`skip_windows`). Every answer with `at_the_end` has a 30-minute final stretch. Whenever the last window is longer than 1 h, no window's midpoint falls in that stretch.
  - The town therefore never walks the body there. The far end is the PENULTIMATE stretch's room.
  - The LOG's last row still names the declared room (`_stretch_row`, `:741-746`, sets `last_place = stretch["room"]`), so the log and the far end disagree.
  - `FarEnd._compute` (`agents/skip_stage.py:938-945`) places the mind from `far_end.room`.
  - The offer is taken up exactly in `at_the_end` (`skip_stage.skip_block` docstring: "comes down the tower stair into the kitchen ..."). In charter stories this re-creates the F16 defect the stage exists to fix: the mind is upstairs when the story resumes.
  - The stage's own executor uses the last row (`skip_itinerary.far_end_of:1940-1959`), so the two executors place the same answer differently.
- **Verification:** probe `charter_audit/skip_short_end.py`, scratch DB, `small_town`, span 08:00-21:00.
  - Windows (h): `[0, 2, 3, 5, 5.5, 7.5, 9.5, 10, 11.5, 13]`.
  - Itinerary: tavern 0-12.5 h, then house_a 12.5-13 h.
  - Output: last row `12.5 13.0 house_a not_known`, `far_end: {'room': 'tavern', ...}`.
- **Confidence:** CONFIRMED.
- **Severity:** WRONG-SCENE.
- **Fix.** Choose a window's directive by the stretch speaking at the window's END (keep the window-to-row assignment in `log()` consistent with it). Or, after the last window, walk the body to the speaking stretch's room when it held no window. Either keeps the grid mind-independent.
- **Test:** this probe as a test, asserting `far_end["room"] == "house_a"`. Add an asleep variant: a final sleep in a bed is slept in the bed.

### F3 — Japanese featured-resident histories are always rejected, so a ja story with a charter-route resident cannot be generated

- **Location:** `world/charter_history.py:575-578` and `:643-646`.
- **Code:**
  ```python
  if len(memory.split()) < 45:
      missing.append("thin_memory")
  if len(consequence.split()) < 4:
      missing.append("thin_consequence")
  ...
  if len(episodes) < PERSONAL_MEMORY_FLOOR:
      raise ValueError(...)
  ```
- **Scenario.**
  - `web/app.py:6174` runs `generate_lived_location` inside `story_language_scope(cid)`, so every attached character's history is written in the story's language (its own comment says so). `story/prelude.py:183` does the same.
  - `providers.chat_complete` appends the pack's `common` policy, which tells the model to write free text in Japanese. The episodes come back in Japanese.
  - Japanese has no spaces, so `split()` returns about one token per paragraph. Every episode is dropped as `thin_memory`.
  - `ValueError` follows, which fails `integrate_featured_resident` and the whole location request (HTTP 400; the quick start removes the half-made chat).
- **Verification.** A snippet fed `ground_recent_history` twelve 159-character Japanese episodes. Output: "chars 159 split words 1", then "ValueError: resident recent history produced 0 usable episodes; at least 10 ...".
- **Confidence:** CONFIRMED (the gate). Whether a live ja launch reaches it is PLAUSIBLE: the scope is applied at both entry points read.
- **Severity:** CRASH.
- **Same class:** `story/journey_history.py:227` (generated journeys). Outside this scope; not verified further.
- **Fix:** measure density in the pack's own units, a pack-scoped length rule like the `linguistic(...)` detector `journey_history` already uses. Do not count whitespace.
- **Test:** `ground_recent_history` given ja episodes of a realistic length accepts them.

### F4 — Every institution of a registry that holds a creature walks a graph where a closed door is a wall (the Aldermill regression)

- **Location:** `world/charter_predation.py:961-980` (`_Caches`).
- **Code:** `reach_map(self.scene, self.places, state["bodies"], cache=self.paths)` (no `neighbors=`) and `self.neighbors = passable_neighbors(self.scene)`.
- **Contrast:** `world/charter_run.py:1602-1604` (`run`) plans and walks on `people_neighbors(scene)`, which was the Aldermill fix of 2026-09-19 (`charter_space.people_neighbors` docstring: the inn's bill was `out_of_reach` on every window).
- **Scenario.** A town that shares a registry with any creature is stepped by `run_registry` (`advance_snapshot`'s `together` arm). Its people can neither be posted through nor walk through a door a person can open.
- **Verification:** probe `charter_audit/registry_graph.py`, `small_town` with the smithy's doors set to `closed_door`, 48 h, seed 3.
  - `run`: unfilled `('smith_shift','no_competence')` ...; smithy occupants `['smith']`.
  - `run_registry`: `('smith_shift','out_of_reach')`; smithy occupants `[]`; identical: False.
- **What this contradicts:** the docstring at `:1004-1008`, `AGENTS.md:459` ("byte-identical to `run`") and `tests/test_charter_creature.py:431`. That test passes only because `small_town` has no closed door.
- **Confidence:** CONFIRMED.
- **Severity:** WRONG-SCENE (posts unfilled, bodies held behind openable doors).
- **Fix:** `_Caches` builds `people_neighbors(scene)` for an ordinary charter and passes it to `reach_map`. Creatures keep `creature_neighbors`.
- **Test:** the probe's closed-door town through `run` and `run_registry`, asserting byte-identity.

### F5 — The town executor still makes a mind's own doing "unknown" when the grid never stepped it, so memories say "the rest was out of X's hands"

- **Location:** `world/charter_skip.py:735-756`.
- **Code:**
  ```python
  unrun = not windows or not all(...simulated...)
  ...
  elif unrun and not stretch["asleep"]:
      outcome = "not_known"
  ```
- **Scenario.**
  - Every stretch that holds no window midpoint (the `at_the_end` row in F2, a clipped first stretch) is `not_known`. So is every stretch after the time-skip budget ran out.
  - `mind/skip_memories.py` renders that as `skip_record_not_known`: "{name} set about it, and the rest was out of {name}'s hands." (`language_packs/en/cards/compositor.json:568`).
  - Since 1342bbde, `skip_work.told_account` also tags it `[own part]`, telling the encoder it is "the mind's own doing in something whose outcome was not its alone", which is false for a solo stretch.
  - This is the class 4d398090 ruled on ("Being away never makes a mind's own doing unknown"): off the map nobody simulates either, and that was ruled not a reason.
  - The stage's own executor marks the same stretch `done`.
- **Verification.** Code read. The F2 probe printed the 30-minute stretch as `not_known`. The compositor key was read.
- **Confidence:** CONFIRMED (mechanism); live frequency unmeasured.
- **Severity:** WRONG-SCENE (memory content and the encoder's tag).
- **Fix:** a stretch the grid did not step goes through `stretch_outcome` like any other (done unless `with`/partial), with routing judged by a route check from where the body stood. "The town did not watch" is not "the world's to judge".
- **Test:** a 30-minute solo stretch in a charter skip comes back `done`.

### F6 — No social practice outlives one window of 2 h or more, and `reconcile` is unreachable at any shipped window size

- **Location:**
  - `world/charter_practice.py:112` (`IDLE_CLOSE_HOURS = 2.0`) and `:1193-1203` (`close_stale` compares against the window's END).
  - `:1171` (`last_effect_at = at_hours`, the end of the window acted in).
  - `:729-736` (`_afford_reconcile`: `if state["at"] - float(practice["opened_at"]) < 12.0: return None`).
  - `world/charter_run.py:1062`, `:1175-1176` (spawned practices are added after `enact`).
- **Scenario.**
  - Next window, `close_stale(at + hours)` sees an age equal to the new window's length, so a 2 h or 4 h window closes every practice before anyone can act in it.
  - Spawned practices (greet opens converse, accuse opens quarrel; the module docstring's "acting spawns practices ... the system cannot run dry") are dead on arrival in presim (4 h/8 h), the town's ordinary advance (4 h) and the skip grid (exactly 2.0 h).
  - A quarrel lives only while it produces an effect every under-2 h. Its only effects are `accuse`, which is self-limited (regard 1.0, falling 0.1 a time, gate 0.45: six), and `reconcile`, which needs 12 h. So `reconcile`, its `apology` event and `DEFAULT_SIGNALS["apology"]` are reachable only at window sizes between about 1.72 h and 2.0 h.
- **Verification:** probe `charter_audit/quarrel_life2.py`, a planted quarrel with a grievance, stepped in `step`'s order.
  - w=0.25: 6 accuse, last at 1.5 h, closed.
  - w=1.0: 6 accuse, closed at 8 h.
  - w=2.0 and 4.0: zero acts, closed at the first window.
- **Confidence:** CONFIRMED.
- **Severity:** DEAD / SILENT-NOOP.
- **Fix.** Measure idleness from the window's START, so a practice touched in the previous window survives one window. Gate `reconcile` on time since the last accusation, or let a quarrel idle while a grievance stands.
- **Test:** a planted quarrel at 4 h windows reaches a `reconcile` act within N windows.

### F7 — A featured resident the planner omitted is placed by an English-only word overlap; a Japanese one lands at the first post

- **Location:** `world/charter_generate.py:977-979` (`_words`: `re.findall(r"[a-z0-9]+", ...)`) and `:1093-1114` (the omission repair). The role match before it uses `spatial_identity.room_name_words`, which also splits on `[^a-z0-9]+`.
- **Scenario:** a Japanese card's `public_history` yields no tokens. Every score is 0, and `min(options)` picks charter 0's alphabetically first post key.
- **Verification:**
  - Snippet: `_featured_assignments(plan, [Japanese resident])` gives `'post': 'brewer'`.
  - The English twin gives `'harbour_master'`; `_words(ja)` is `set()`.
- **Confidence:** CONFIRMED.
- **Severity:** WRONG-SCENE (Japanese stories only; the planner gets first refusal).
- **Fix:** a pack-scoped tokenizer, or ask the decision model to pick a post from the closed list (the Writers' Room already owns placement).
- **Test:** a ja resident with an obvious post is repaired onto it.

### F8 — A figure's purchase never names a good in a Japanese story

- **Location:** `world/charter_author.py:697-733` (`good_named`, `_label_tokens = re.findall(r"[a-z0-9]+", ...)`).
- **Code:** `tokens <= words`. For Japanese text and labels, both sets are empty, so nothing matches.
- **Verification:**
  - Snippet: `good_named(eco, 'bakery', 'I would like to buy some bread')` returns `'bread'`.
  - `good_named(eco, 'bakery', 'パンを一斤ください')` returns `''` with a `パン`-labelled good on sale.
- **Confidence:** CONFIRMED.
- **Severity:** SILENT-NOOP (ja).
- **Fix:** the closed goods table stays; token the text with the pack's own segmenter, or ask the decision model to pick a good from the closed list.
- **Test:** a ja purchase names the ja-labelled good.

### F9 — `charter_history` decides with English recognisers and writes English text into a character's pre-story memories

- **English-only recognisers:**
  - `_public_words` (`:99-111`, `[a-z0-9]+` plus English suffixes and stopwords) gates which abilities reach placement (`:131`). For a Japanese card no ability is ever "corroborated", so the seed carries none.
  - `featured_resident_private_habits` (`:153-155`) is an English WORD LIST over free card prose: `private|privately|alone|off-clock|locked|comfort|bake|sweet|doodle|plush|hobby|ritual`. "bake / sweet / doodle / plush" reads as one character's vocabulary. A coping strategy phrased any other way, and every Japanese card, yields no habit.
- **English memory text:**
  - `_first_person` English regex replacements (`:213-229`).
  - `_named_surface` templates: "I made private time ...", "I {past} {other}", "{actor} {past} me" (`:232-256`).
  - `career = "I worked as " ... ", then " ... " in {place}."` (`:402-406`).
  - The episode glue ", in {place}", ", with ...", " What remained afterward: ..." (`:598-607`).
  - The reciprocal "I shared ... with ..." (`:694-698`).
  - All of these become memory rows (`integrate_featured_resident`, `add_memories_batch`) in any language.
- **Confidence:** CONFIRMED by reading (literal regex and f-strings).
- **Severity:** SILENT-NOOP / WRONG-SCENE (ja).
- **Fix (the class).** Recognisers move to pack-scoped rules or to a decision-model question. For habits, state the class "a coping response done alone or off duty" to the model, not a word list. Glue text moves to compositor templates in both packs.
- **Tests:** a ja card keeps its abilities; a habit phrased without the listed words is found.

### F10 — Situations open only between bodies adjacent in key order, so in a settled room a body never meets most of the people standing in it

- **Location:** `world/charter_practice.py:955-966`.
- **Code:** `for other in able_here[index + 1:index + 3]:`, where `able_here` is the room's bodies in a stable order.
- **Verification:**
  - Snippet: six strangers a-f in one hall; `opportunities` opens `greeting:a:b, a:c, b:c, b:d, c:d, c:e, d:e, d:f, e:f`.
  - `a` is never offered d, e or f, and the same pairs recur every window while nobody moves.
- **Confidence:** CONFIRMED (mechanism). Impact PLAUSIBLE (bodies circulate on errands).
- **Severity:** WRONG-SCENE (low): the practice-level social graph inside a room is a chain over key order.
- **Fix:** draw the partners from the run's seed (crc32 over seed, window and pair) and keep the 2-per-actor bound. The bound stays; the bias goes.
- **Test:** over N windows of a static room, every pair is offered.

### F11 — Authored trigger rules are truncated silently; 32 authored rules evict the shipped default

- **Location:** `world/charter_trigger.py:348` (`list(raw.get("then") or ())[:TRIGGER_THEN_CAP]`) and `:455` (`[rows[key] for key in sorted(rows)][:TRIGGER_CAP]`).
- **What it contradicts:** `trigger_warnings`' own contract ("a rule that silently does nothing is the empty-psychology-field failure") and `_normalize_rule`'s "Refused rather than dropped".
- **Verification (snippet):**
  - A rule with 4 ops: `then kept: 3 refused: None warnings: []`.
  - 32 authored rules with ids `a00`-`a31`: `rules kept: 32 default kept: False warnings: []`. `blame_opens_a_quarrel` sorts after them and is cut.
- **Confidence:** CONFIRMED.
- **Severity:** SILENT-NOOP.
- **Fix:** keep the caps (they are owner-visible constants) and add a refusal notice for each cut op and rule. Never cut a default before an authored row.
- **Test:** both snippets as tests asserting a warning.

### F12 — The "subjective meaning over cited evidence" pass has been dead since it was written, and the module docstring describes it

- **Location:** `world/charter_history.py:43-54` (`_PERSONAL_HISTORY_SYSTEM`, referenced nowhere) and `:452-532` (`ground_personal_history`).
- **Evidence:**
  - `ground_personal_history` is called only by itself (`:517`) and by `tests/test_fable_town.py:180`.
  - `git log -S"_PERSONAL_HISTORY_SYSTEM"` shows only 7c756260, the commit that wrote it, and that version already had only the definition.
- **The stale docstring.** The module docstring (`:1-8`: "A model may add only subjective meaning to those cited surfaces") describes this dead path. The live path, `flesh_resident_history` with `_RECENT_LIFE_SYSTEM`, is "an author licence to invent bounded PERSONAL recent life".
- **Confidence:** CONFIRMED (repo-wide grep including tests and tools).
- **Severity:** DEAD + STALE-DOC.
- **Fix:** delete the prompt and `ground_personal_history`, or wire them; rewrite the docstring for the licensed path.
- **Test:** none needed for the deletion.

### F13 — The skip's town budget is per mind and runs serially, so the inline bound is N × 60 s, not the 60 s the docstring claims

- **Location:**
  - `world/charter_skip.py:176-177`: each `live_in_charter` call starts its own `deadline = time.monotonic() + CHARTER_BUDGET_SECONDS["time_skip"]`.
  - `agents/skip_stage.py:754`: it is called inside the serial `for row in rows` loop. Only the question is parallel.
- **What it contradicts:** the module docstring (`charter_skip.py:31-40`): "bounded by the time-skip budget the town's own advance already has".
- **Cost:** every mind also re-deep-copies the whole registry (`:412-425`) and re-simulates the same town.
- **Confidence:** CONFIRMED (code read).
- **Severity:** PERF / STALE-DOC.
- **Fix:** one deadline per skip, shared across minds. See E1 for removing the repetition.

### F14 — The skip commits changed behaviour without the rows that state it (`CLAUDE.md`: "edit the row in the same commit as the behaviour")

- 4d398090 changed `stretch_outcome` ("away ... decides nothing"). Still stating `away` makes a row `not_known`:
  - `AGENTS.md:490`: "`not_known` is another's response (`with`), a world off the map (`away`) or a stretch that partly failed".
  - `Design.md:347`: "a stretch whose success is the world's to judge -- another's response, `with`, or the world off the map, `away` -- `not_known`".
- 1342bbde made `told_rows` tell `not_known` rows. Still stating otherwise:
  - `AGENTS.md:491`: "Only a `done` row ... is told (never `failed`, `not_known`, ...)".
  - `Design.md:348`: "A `failed`, `not_known`, off-map or asleep row changes nothing" and, under Not built, "the mind's own part of a `not_known` row".
  - `DESIGN_THE_CAST_ACROSS_A_SKIP.md` § 4.4 "Things", the same sentence.
- **Verification:** grep and the two diffs (1342bbde touched only `skip_work.py`, `CODE_MAP`, the encoder cards and tests; 4d398090 only `skip_itinerary.py`, `CODE_MAP` and tests).
- **Confidence:** CONFIRMED.
- **Severity:** STALE-DOC.
- **Fix:** edit those rows. `UNBUILT_LIVING_WORLD` § 1.99d's "A `not_known` row changes nothing ... the owner's call" is equally stale; it is listed under Already registered.

### F15 — Smaller stale comments and docstrings in the nine files

- `world/charter_run.py:1086-1091`: "`COARSE_PRACTICES` is the subset that does not saturate ... Gossip stays where it belongs, on screen". In fact `charter_practice.py:908` has `COARSE_PRACTICES = None` (every kind, owner's call 2026-08-27). The F6 probe's off-screen run recorded 5,486 `ask` acts.
- `world/charter_trigger.py:245`: "`quarrel` is not in `COARSE_PRACTICES`". Same staleness; its conclusion still holds only because the off-screen branch passes no `blame`.
- `world/charter_run.py:103-104` and `world/charter_practice.py:1006-1008`: "roughly two accusations per pair". With `NEUTRAL_REGARD = 1.0`, a 0.45 gate and a cost of 0.1, it is six (the F6 probe).
- `world/charter_practice.py:104-106`: `PRACTICE_CAP` "Past this the oldest is dropped". The code (`:1147`, `:1063`, `:870`) acts on the FIRST four in insertion order, which are the oldest, ignores the newest, and drops nothing.
- `world/charter_skip.py:361-368` (`skip_seed`): "the instant the skip began". Both callers pass the charter's own last instant (`_prepare:425`, `advance_snapshot:3254-3260`). They agree with each other, not with the docstring.
- `AGENTS.md:442` lists `charter_skip._window_edges`. No such function exists repo-wide; it is `skip_windows`.
- **Severity:** STALE-DOC. **Confidence:** CONFIRMED (each against code or a probe).

### F16 — The skip's record of whom a mind saw orders tied strangers by hash-salted set order

- **Location:** `world/charter_skip.py:913-915`.
- **Code:** `people = sorted(set(presence) | set(interaction), key=order)` with `order = (0/1, rank, label)`.
- **Scenario.**
  - Two residents with the same stranger label and the same rank tie. The input order of a set of tuples of strings then decides their output order and which one `[:SEEN_PER_ROW_CAP]` cuts.
  - That order varies with `PYTHONHASHSEED`, so a rerun process can file a different `seen` list.
  - Only "between" interactions carry differing text under one label, so the visible effect is narrow.
- **Verification:** snippet under four `PYTHONHASHSEED` values; the first two refs differed.
- **Confidence:** PLAUSIBLE (that it occurs).
- **Severity:** low (determinism).
- **Fix:** add the ref itself as the last sort key.

## Efficiency

- **E1. The skip re-simulates the whole town once per asked mind, serially and inline before perception.**
  - Where: `agents/skip_stage.py:754` calls `world/charter_skip.py:live_in_charter` per mind. Each call deep-copies every institution (`:414`), recomputes `charter_scene` and `reach_map` per charter, catches up, and steps every window of the span.
  - Hotness: every skip beat, before perception. The module measured 0.6-1.4 s per mind for 24 h on chat 175, and the windows and seeds are identical for every mind.
  - Gain: `step` already takes a set of lifted bodies and an itinerary dict, so one `_TownRun` per skip lifting all charter-held minds turns N runs into one. Semantics need checking: withheld bodies change the watch bill. A cheaper half: copy and prepare once, then share.
- **E2. `_remember_experience` copies the holder's whole list and re-sorts it on every append.**
  - Where: `world/charter_run.py:173-188`, plus a linear id scan when folding. A holder's list reaches `EXPERIENCE_CAP` = 4000.
  - Hotness: per experience row, per window, in presim and every advance.
  - Fix: `bisect.insort` with a precomputed key, or append and sort once per holder per window.
- **E3. `normalize_judgments` rebuilds the whole judgment store three times per window.**
  - Where: `normalize_charter` at `charter_model.py:595`, then `update_judgments_from_minds` at `:430` and `:475`. Each rebuild copies every stance's `seen` list (up to 128).
  - The idempotence test (`:455`) is a list scan. `judgment_of`/`judgment_view` (`:479`, `:485`) normalise the whole store to read one holder.
  - Hotness: per window once judgments exist; the docstring measured 104 stances in a famine quarter.
  - Fix: normalise once at the head, test against a set, read one holder directly.
- **E4. The historian's input has no cap.**
  - Where: `world/charter_generate.py:1811` puts every presim event in the payload (`event_chronicle(events)`). Only the OUTPUT is budgeted (`historian_budget`).
  - Hotness: once per lived-location generation, but a famine presim of 320 stood-down bodies (Brackwater, quoted at `:1253`) emits thousands.
  - Fix: rank and cap the chronicle by the selected residents' own events. The number is the owner's.
- **E5. (minor) `post_of` is rebuilt inside the per-encounter loop.** `world/charter_run.py:375`. Hoist it.
- **E6. (minor) `charter_skip._char_id_of` reads and parses every attached sheet per mind.** `:230-246`, so O(cast²) per skip. Resolve once per skip.

**Where the loop is O(bodies²):** the encounter and `served_beside` loops (`charter_run.py:1404-1434`) are quadratic per place, capped at `CO_PRESENCE_WIDTH` = 64. That is up to 4,096 sha256 draws per crowded place per window. It is bounded and documented; it is listed here for the question asked.

## Already registered

- `charter_author.authored` filters marks by `bindings` only (`external = set((charter.get("bindings") or {}).keys())`, now `:264`), and `has_standing` reads riders by binding name. These are `UNBUILT_IDENTITY.md` § 1.92's residual "Twelve other sites spell `body_key in bindings`" (cited there as `charter_author.py:186`).
- `UNBUILT_LIVING_WORLD.md` § 1.99d (the town's half of the skip) registers:
  - a featured resident's post differs between the minds' run and the town's own advance;
  - residents' talk differs between two minds' runs;
  - a creature registry's predation is not stepped in the scratch run;
  - the charter walks frontier joins and water, and an away body returns with no walk (also `UNBUILT_WORLD.md` § 1.166).

  That entry's line "A `not_known` row changes nothing ... the owner's call" is itself stale after 1342bbde (see F14).
- Predation drift is per hour, so a creature's hunger cannot move in a scene: `UNBUILT_LIVING_WORLD.md` § 1.142 / § 1.150. No held hunt: § 1.150.
- The last window's kills are reported at the next window: `UNBUILT_LIVING_WORLD.md` § 2.32.
- No blame-opened quarrel off screen: `UNBUILT_LIVING_WORLD.md` § 1.99a / § 1.99b. Those sections repeat the stale "`quarrel` is not in `COARSE_PRACTICES`" wording.
- `run_registry` takes no deadline ("a group begun is a group finished"): stated in `advance_snapshot`'s own comment. It is a known design choice, not registered as a defect.

## Structure notes

**Monoliths in miniature:**
- `charter_run.step` (`:428-1544`, about 1,120 lines), with natural seams at its phases:
  - interventions and harm;
  - the watch plan and the posted bodies;
  - movement (walks, relocate, errands, the itinerary);
  - upkeep and economy;
  - roster;
  - needs;
  - minds, news, talk and sighting;
  - decisions and mobilisation;
  - practices, triggers and enact;
  - experiences, marks and feel;
  - co-presence and encounters;
  - ties.

  Each already reads and writes a named slice of `after_charter`.
- `charter_generate.close_plan` (`:1112-1570`, about 460 lines): the rooms allowlist, per-charter closure, berth spreading, needs/feeder and fixtures.
- `charter_predation.hunt_moves` (about 190 lines) and `_attack` (about 170 lines).
- `charter_history.integrate_featured_resident` (`:745-883`) repeats one 10-line comment block three times verbatim (the blocks opening at `:777`, `:804` and `:826`).

**Natural file seams (for the split program):**
- `charter_generate`:
  - prompts: `_PLAN_SYSTEM`, `_FRAME_CLAUSE`, `_HISTORY_SYSTEM`, `_HISTORIAN_SYSTEM`, `_CAST_SYSTEM`;
  - closure: `close_plan`, `_scale_populations`, `_ensure_shift_crews`, `_post_seats`;
  - berth splitting: `_spread_berths`, `berth_split_warning`;
  - featured residents: `normalize_featured_residents`, `_featured_assignments`, `lore_cast_residents`;
  - historian: `event_chronicle`, `resident_service_chronicle`, `ground_history_output`, `narrate_actual_history`.
- `charter_history`:
  - placement seed and habits;
  - evidence packet;
  - grounding;
  - DB integration.
- `charter_predation`:
  - senses;
  - contest;
  - spoor;
  - tribute;
  - the stepper (`run_registry`).

  The stepper is the half that duplicates `charter_run.run`; F4 is that duplication drifting.

**Two functions that do the same job:**
- `charter_run.run` and `charter_predation.run_registry`: per-window caches, seeds and graphs (F4).
- `charter_skip._TownRun._stretch_row`/`far_end` and `skip_itinerary.live_through`/`far_end_of`: the two skip executors disagree on the final stretch (F2) and on unrun stretches (F5).
- `charter_practice._afford_tend` and `charter_author._figure_act` "tend": the same rule written at two doors, as their own comments acknowledge.

**Module-level mutable state:** none in the nine files. `_PLAN_SYSTEM +=` rebinds an immutable string at import. `DEFAULT_SIGNALS` is copied by `normalize_social_norms`. Every RNG is `hashlib`/`zlib`/`stable_event_key` over a seed. There is no `random` and no `hash()`; `uuid4` appears only in `charter_runtime` job ids.

**Determinism answers (question 1):**
- Seeds:
  - every window: `seed + index` (`run`, `run_registry`, the skip loop's `seed + index - 1` from `index` 1);
  - per epoch: `stable_event_key(epoch_id, key)`;
  - per skip: `skip_seed(cid, charter, last instant)`, the same in `advance_snapshot`'s `time_skip` arm.
- The predation round's seed is `run_registry`'s `seed` argument plus `index`, and `advance_snapshot` passes only `seeds=`. The round's draws are therefore not per-epoch: they are deterministic and vary only by clock and place.
- **What a replay cannot reproduce: wall-clock budgets.**
  - `run(deadline=)` stops a town part-way through.
  - `_TownRun.live` marks the rest of a skip unsimulated, so those rows become `not_known` (F5).
  - A rerun on a slower or busier machine can therefore store a different town and a different skip log. This is by design ("a STOP, not a skip"), but it is the one replay-sensitive input in these files.
- The only hash-salted order found is F16.

**Unbounded growth (question 2):**
- Capped, with the constant named in code:
  - `EXPERIENCE_CAP` 4000 (`ENCOUNTER_ODDS` 12 is the owner's call, 2026-08-27);
  - `PENDING_CHANGE_CAP` 32, `TRIGGER_MEMORY_CAP` 256, `TRIGGER_CAP` 32, `TRIGGER_THEN_CAP` 3, `TRIGGER_YIELD_CAP` 8;
  - `JUDGMENT_CAP` 24, `REASON_CAP` 6, `SEEN_CAP` 128, `TIE_CAP` 24;
  - `PRACTICE_CAP` 4 (per body; the store is bounded by `close_stale`), `PAIR_TAIL` 256;
  - `CO_PRESENCE_WIDTH` 64, `SEEN_PER_ROW_CAP` 12;
  - `PERSONAL_MEMORY_CAP` 60, `HISTORIAN_RESIDENT_CAP` 240, `PLAN_CHARTERS` 8;
  - spoor (`SPOOR_CAP` in `charter_creature`), `CAST_BEATS` 6.
- Grow with the institution's shape, not with time, and uncapped: `served_beside` and `heard_blame` (at most bodies²), `walked` (bodies × rooms²), `stood` (bodies × posts), `politics.blame` (a monotone counter per body).
- Uncapped and growing per generation: the historian's chronicle input (E4).
- No store in the nine files grows with simulated time without a cap.

## Docs checked

| Claim | Held? |
|---|---|
| `AGENTS.md:442`: `charter_skip` exports `_window_edges` | No. No such function; it is `skip_windows` (F15). |
| `AGENTS.md:442`: a scratch run, never a write; a lifted body acts on nobody | Held. `_TownRun` deep-copies, and `step` keeps lifted bodies in `unminded`. |
| `AGENTS.md:459`: a one-charter registry through `run_registry` is byte-identical to `run` | No, with a closed door (F4). |
| `AGENTS.md:459`: the `figure` category is never prey off screen | Held (the figure branch files and does not harm). The broader "on screen is the Director's" does not hold for leased bodies (F1). |
| `AGENTS.md:490`: `_stretch_row` calls `stretch_outcome` for every stretch the town stepped | Held for stepped stretches. Unstepped ones bypass it (F5). |
| `AGENTS.md:490` / `Design.md:347`: `away` makes a row `not_known` | No, after 4d398090 (F14). |
| `AGENTS.md:491` / `Design.md:348`: only `done` rows are told; `not_known` changes nothing | No, after 1342bbde (F14). |
| `charter_skip` docstring: one town for every mind; the town's advance stores the day the minds lived | Held on the matched grid and seed. Exceptions: those registered in § 1.99d, plus charters whose last instant differs from the mind's charter (`begin = max(start, held["last"])` steps a different grid), plus F2's far end. |
| `charter_skip` docstring: inline cost bounded by the time-skip budget | No. Per mind, serial (F13). |
| `charter_practice` docstring: "acting spawns practices; the system cannot run dry" | No at windows of 2 h or more (F6). |
| `charter_trigger` docstring: pure and deterministic, frame persisted, depth/fire-once/refractory/yield bound the cascade | Held, read in full. The `pending_changes` frame is replaced every window, so nothing fires twice across an advance; the refractory store is pruned by `normalize_charter` (`charter_model.py:645`). |
| `charter_history` module docstring: a model adds only subjective meaning to cited surfaces | No. That path is dead; the live path is licensed invention (F12). |
| 8e3c60f2: "`reasoning_effort` carried to every attempt this call makes" | Held. All four `chat_complete` calls in `complete_validated_json` (`llm/llm_quality.py:1285`, `1305`, `1768`, `1863`) pass it. The skip question's payload (`wire`) and card are unchanged, so no field the answer needs was dropped. |
| f9ba52ae: a stretch fails only on positive evidence, in both executors | Held. `lay_over` fails `not_held` only for a carryable thing held elsewhere and not fetchable, and `judge_what_was_missing`/`judge_without` run after either executor. An unanswered or failed decision request turns the row `not_known`, never `failed`. |
| 1342bbde: a `not_known` row is told "as far as it went" | Held for the stage's own executor. In a charter story the tag `[own part]` is also applied to rows `not_known` only because the grid never stepped them (F5). |
