# Audit: mind/ affect, psychology, theory of mind, skip memories, character_jev, notebook (2026-11-01)

Auditor scope: `mind/affect.py`, `mind/affect_mix.py`, `mind/affect_pass.py`, `mind/affect_appraisal.py`,
`mind/psychology_runtime.py`, `mind/theory_of_mind.py`, `mind/skip_memories.py`, `mind/character_jev.py`,
`mind/notebook.py`, `mind/canon_provenance.py`, `mind/knowledge_circles.py`, `mind/thoughts.py`.
Working tree at 84f3de23 (branch worktree-jev-character-tracking). Read-only; nothing in the repo was edited.

## Scope read

Read IN FULL (every line):
- `mind/affect.py` 1-2600
- `mind/affect_mix.py` 1-844
- `mind/affect_pass.py` 1-788
- `mind/affect_appraisal.py` 1-282
- `mind/psychology_runtime.py` 1-873
- `mind/theory_of_mind.py` 1-861
- `mind/skip_memories.py` 1-1482
- `mind/character_jev.py` 1-1139
- `mind/notebook.py` 1-406
- `mind/canon_provenance.py` 1-398
- `mind/knowledge_circles.py` 1-134
- `mind/thoughts.py` 1-131

Read in part, for callers/context only (not audited):
`agents/character.py` 995-1015, 2330-2470, 2602-2630, 3555-3600, 3860-3950, 4040-4150, 4700-4910, 5025-5140;
`agents/character_bare.py` 218-300, 490-610, 650-735, 960-1010; `persist/commit_memory.py` 625-700, 1426-1445,
1600-1680, 1730-1990, 2020-2130, 2200-2240, 2325-2375, 2425-2495; `persist/commit_memory_write.py` 173-215, 375-420;
`persist/checkpoints.py` 1774-1806; `llm/decisions.py` 144-330; `llm/providers.py` 236-267, 3483-3700 (grep),
3930-3945, 4331-4460, 5130-5145; `world/skip_itinerary.py` 575-615, 1960-2005; `story/character_schema.py`
1796-1850, 2218-2275, 2340-2375; `mind/memory_context.py` 830-860; `mind/memory_routes.py` 135-152;
`mind/memory_jev.py` 428-445; `agents/loops.py` 1440-1475; `agents/runtime.py` 620-720; `agents/common_beat.py`
200-260; `world/day_cycle.py` 349-382; `world/mechanics.py` 553-583; en pack `character_jev/*.txt` (the yes/no
questions, `strike_kind`), `prompts/character_skip.txt` line 7.
Docs: `docs/UNBUILT_CHARACTERS.md` §1.56, §6.15; `docs/UNBUILT_WORLD.md` §1.166; `DESIGN_LONG_TERM_GOALS.md`
165-250; `DESIGN_JEV_CHARACTER_PASS.md` 240-360, 1220-1240; `Design.md` rows 231, 250, 260, 322, 351;
`AGENTS.md` 400-420, 432, 468, 469, 541.

Tests run (serial, `.venv`): `tests/test_projects.py` 53 passed; `tests/test_affect_pass.py` 27 passed.
Read-only DB queries (`engine.db?mode=ro`): card resting arousal; `mood_habits` sizes; hypothesis kinds/ages;
chat 20/40 checkpoint hypothesis history. Snippets below are pure-function calls.

## Findings

Counts: LEAK 2, CORRUPTION 3, WRONG-SCENE 11, SILENT-NOOP 3, CRASH 1, DEAD 2, STALE-DOC 1 (several items).

### F1 — LEAK (reader side): the read-back state and the kept thoughts take `providers.last_reasoning` without clearing it first, so they can carry the previous speaker's reasoning

- Reader: `agents/character.py:4883-4900`
  ```python
  from llm.providers import last_reasoning
  _trace = str(last_reasoning.get() or "")
  _thought_in_order = _trace
  ...
  _holding.reasoning = _trace
  ```
  No `last_reasoning.set(None)` precedes `_agent_json(...)` (4874) or `look_then_answer` (4835).
- Consumers in scope: `mind/character_jev.py:441-443`
  ```python
  if h.reasoning:
      parts.append("YOUR OWN THINKING AS YOU WORKED IT OUT (some of it you set aside):\n"
                   + _text(h.reasoning, REASONING_CHARS))
  ```
  and `mind/thoughts.py:47-70` (`keep_thought`, fed `out["_thought"] = [_thought_in_order]` at
  `agents/character.py:5130-5136` and `persist/commit_memory.py:2010-2012`), which hands the text back as
  `what_you_were_thinking` for `character_thoughts_kept` turns.
- Scenario: `interaction_loop` runs every speaker's `character_step` sequentially in ONE worker context
  (`agents/loops.py:1466`). Speaker A's call leaves its trace in the ContextVar (`_sse_openai`,
  `llm/providers.py:5140`, or the tools-loop re-set at `agents/character.py:4899`). Speaker B's call goes
  through a path that never writes it: `_sse_anthropic` (`llm/providers.py:3602-3670`, no setter), the
  Anthropic non-stream branch (`4446-4460` returns without setting), or claude_cli without thinking
  (`3939-3943` sets only `if reasoning`). B's read-back state then presents A's private thinking as B's own,
  so B's typed answers (addressees, concealment, which memory shaped the act, notebook evidence, tell floor)
  are chosen with A's hidden knowledge in context; with `character_thoughts_kept` on, B's state stores A's
  trace and B's next packets quote it verbatim. `mind/thoughts.py:17-20` ("No other mind ... ever reads it")
  is false on those paths.
- Verified: traced every `last_reasoning.set` (`providers.py:264, 3588, 3941, 5140`) against the return
  paths, the reader, and the loop. Not executed end to end. The writer-side defect (`_chat_complete_once`
  not clearing) is another auditor's; this is the reader half.
- Confidence: PLAUSIBLE (needs a non-clearing provider path for at least one mind in a loop: Anthropic
  direct, claude_cli, or a tools-loop speaker before one of those).
- Fix: `last_reasoning.set(None)` immediately before the character's model call(s), so the reader never
  depends on every provider path. Test: set the var to a sentinel, stub `_agent_json` to return a reply
  without touching it, capture the read-back `state` via `decisions.OVERRIDE`; assert the sentinel is absent
  and `out.get("_thought")` is falsy.

### F2 — LEAK (cross-file, PLAUSIBLE): a skip record relays another mind's declared `doing` verbatim; the beat path's observable floor has no skip counterpart

- `mind/skip_memories.py:159-166` (`LOG_FIELDS`, `SEEN_FIELDS = ("who", "doing")`), `:472-484` (record row `with`), filled
  by `world/skip_itinerary.py:1997-2003`:
  ```python
  doing = theirs.get("doing") or ""
  if scrub is not None:
      doing = scrub(observer, doing)          # the observer's identity floor: names only
  entry = {"who": label_for(observer, other), "doing": doing}
  ```
- The skip card asks "`doing` is only what someone watching you could see you do; what it is for ... go in
  `why`" (`language_packs/en/cards/system_prompts/prompts/character_skip.txt:7`) — compliance only. On a beat
  the same class is floored in code: `character_jev.act_parts` + `act_part_seen`, compiled by
  `agents/character_bare.py:_outward_part` (fails closed to the first part when unanswered), because "a
  motive, a plan, private knowledge or a memory written into it reached them as something seen"
  (`mind/character_jev.py:292-294`).
- Scenario: B's skip answer `doing: "slips the forged letter under the magistrate's door -- so he'll blame
  Mara"`; A shares the place; A's record row carries it, A's skip memories are written from it, and A's
  far-end payload (`the_stretch_just_passed`) quotes it.
- Verified: traced `share_company` -> `record_rows` -> `writer_payload`. Not measured live.
- Fix: run the act floor on a skip `doing` before `share_company` (the part question, or the first part
  when unasked). Test: two logs at one place with B's `doing` carrying a purpose clause; A's `with` holds only
  the observable part.

### F3 — CORRUPTION: a project the mind gave up out loud re-seeds silently from the card once six later projects have ended

- `mind/affect.py:1735`, `:1902`, `:1970`
  ```python
  _FORMER_PROJECTS_CAP = 6
  return (live, ended[-_FORMER_PROJECTS_CAP:], warnings)
  ```
  and the authored seed in `persist/commit_memory.py:1626-1642` dedupes only against `projects +
  former_projects`:
  ```python
  _seen_pids = {str(p.get("id") or "") for p in projects + former_projects}
  for _p in character_projects(sh):
      if len(projects) >= affect.PROJECT_CAP: break
      if str(_p.get("id") or "") in _seen_pids: continue
      if ... not in _seen_proj:
          projects = projects + [dict(_p, last_served_turn=turn.idx)]
  ```
- Reproduced (pure functions; the commit's seed rule copied into the snippet): seed `pa1` -> `displace` pa1
  "the light was automated; I am done with it" -> six later adoptions each displaced -> `former` =
  `['p2'..'p7']` -> next commit seeds `('pa1', 'Keep the lighthouse lit through the winter')` again, live,
  `last_served_turn` = now. Probation lapses (`settle_probation`) count toward the six.
- Contradicts `docs/design/DESIGN_LONG_TERM_GOALS.md:182-183` ("deduped against live *and former* so a project
  given up never silently re-seeds") and `AGENTS.md:469` ("never let the engine adopt, satisfy or displace
  one"). Under the bare contract adoptions are short-lived (§1.56: fifteen distinct, held 1-7 beats), so six
  endings is ordinary in a long story. No test pins the promise (grep of tests/).
- Confidence: CONFIRMED.
- Fix: keep ended AUTHORED ids outside the rolling window (an uncapped `retired_authored` id set, or exempt
  `authored` rows from the cut); the former cap itself is the owner's. Test: the snippet's sequence; pa1 must
  not return after seven endings.

### F4 — CORRUPTION (ruling pending): the per-beat "Is it settled now?" check deletes a concern with no record

- `mind/character_jev.py:890-891` asks `concern:{k}` (en: "ON YOUR MIND: {concern} / Is it settled now?");
  `agents/character_bare.py:975-980`
  ```python
  kept_concerns = [c for k, c in enumerate(h.concerns)
                   if not (k < jev.MAX_CONCERNS and jev.yes(answers, f"concern:{k}"))
                   and notebook.concern_id(c) not in struck_concerns]
  ```
  and `persist/commit_memory.py:1975-1980` stores the new list: no memory row, no reason, nothing a later beat
  can reopen by name.
- The owner's ruling of 2026-10-05 (project memory `concern-design-rulings`): "the character strikes only,
  and every retirement is filed. The unprompted Jev 'Is it settled now?' check that silently deletes a concern
  goes". The same note says the concern build was not approved ("ask before building"). The ruling appears in
  no register; `DESIGN_JEV_CHARACTER_PASS.md:175` and `:1230` still describe the per-beat check as the design.
- Confidence: CONFIRMED (code); a defect relative to the ruling, whose build is pending.
- Fix: register the ruling (UNBUILT §6.15 or a concern-build row) now; when built, a retirement is a filed
  memory row and the check goes. Test (when built): a concern the reply did not strike survives a "yes".

### F5 — CORRUPTION (low): `theory_of_mind._clamp01` reads NaN — or the string "nan" — as 1.0

- `mind/theory_of_mind.py:120-125`
  ```python
  def _clamp01(value, fallback=0.5):
      try:
          v = float(value)
      except (TypeError, ValueError):
          return fallback
      return max(0.0, min(1.0, v))      # min(1.0, nan) == 1.0
  ```
- Reproduced: `_clamp01(float('nan')) == 1.0`; `apply_mind_model_updates({}, [{... 'kind':'stated_fact',
  'confidence':'nan'}], 3)` stores 0.9 (the kind's ceiling); `cap_mind_model_updates([... nan goal])` -> 0.65.
  `affect._clamp01(nan)` -> 0.0 and `psychology_runtime._float` -> default: the siblings disagree.
- Reachable only from model-written confidences (greeting impressions, `story/greetings.py:405-433`); the
  bare path computes confidence in code.
- Confidence: CONFIRMED. Fix: NaN -> fallback (as `affect._float_or`). Test: `_clamp01(float('nan'), 0.0) == 0.0`.

### F6 — WRONG-SCENE: the room a goal or project names is found by bare substring and last position — "beginning" names the Inn, "Great Hall" names the Hall

- `mind/affect.py:1973-1987`
  ```python
  folded = str(text or "").casefold()
  for key, rid in (named_rooms or {}).items():
      ...
      pos = folded.rfind(str(key))
      if pos >= 0 and (best is None or pos > best[0]):
          best = (pos, str(rid))
  ```
  duplicated inline in `agents/character.py:2433-2441` (`_destination_from_goals`, `rfind` at 2438).
- Reproduced:
  ```
  'Go back to the beginning'             -> r_inn
  'Walk to the Great Hall'               -> r_hall      (shorter name starts later and wins)
  'Search the garden for what was hidden'-> r_den
  'Find the barrel'                      -> r_bar
  projects_served_this_beat([p1 'Tend the garden until spring'], [], 'Head to the Den') -> {'p1'}
  goal_slot_currency({}, 'Go back to the beginning', named, 'r_inn', 7)
      -> {'goal_since': 7, 'goal_room': 'r_inn', 'goal_room_reached': 7}
  project_boundary([p1 'Return to the beginning of it all'], ..., new_room='r_inn')
      -> 'you have arrived where your project p1 points'
  _destination_from_goals({'active_state': {'goal': 'Go back to the beginning'}}, pg) -> Inn
  _destination_from_goals({... 'Walk to the Great Hall'}, pg)                     -> Hall
  ```
- Effects: routing steers a mind to a room its words never named; the substance channel of
  `projects_served_this_beat` (2024-2029) credits service that never happened, so a probationary project can
  ESTABLISH at drive weight by coincidence of letters (or escape its lapse); `goal_slot_currency` stamps the
  false room `goal_room_reached`, after which the router discards the real goal as spent; `project_boundary`
  fires a false arrival review (2156-2163).
- THE CLASS — "does this text name this place?" has five implementations that disagree:
  1. `mind/affect.py:1973` `_last_named_room` — bare substring, last start wins;
  2. `agents/character.py:2433-2441` — the same, inlined;
  3. `world/skip_itinerary.py:587-592` `_named_at` — punctuation-folded, space-padded phrase (fails closed for
     unspaced scripts: a Japanese room name followed by a particle never matches);
  4. `mind/memory_routes.py:135-152` `names_place` — every 3+-letter word of the name anywhere in the text;
  5. `story/character_schema.py:1813` `name_boundary_pattern` (used by `persist/commit_memory.py:629`
     `_intent_names_term`, `theory_of_mind.rekey_place_claims`, `notebook._named_in`) — the engine's
     script-aware whole-name matcher.
  Even 5 alone leaves the Hall/Great Hall case: overlapping matches need longest-first resolution.
- Confidence: CONFIRMED. Not in any register.
- Fix: one reader built on `name_boundary_pattern` (deferred import, as `notebook.py:114` and
  `theory_of_mind.py:373` already do for the `story -> mind` cycle), discarding a match whose span lies inside
  another match's span, then last position. Test: {Inn, Hall, Great Hall, Den} against the five texts above
  (None, Great Hall, Den...), plus a Japanese name followed by a particle.

### F7 — WRONG-SCENE: both decision passes around a character call read the CARD's psychology — a rupture-shifted drive and everything the story taught the mind's cues are invisible to them

- `mind/affect_pass.py:371-394` (`psychology_text(sheet)`):
  ```python
  psy = (sheet or {}).get("psychology") or {}
  drive = psy.get("drive") or {}
  ...
  cues = [a for a in (psy.get("learning") or {}).get("associations") or [] ...]
  lines.append("WHAT STIRS YOU, LEARNED: " + ...)
  ```
  `agents/character_bare.py:233-237, 252`:
  ```python
  psy = (sheet or {}).get("psychology") or {}
  drive = psy.get("drive") or {}
  if str(drive.get("essence") or "").strip():
      aims.append({"kind": "drive", "id": "drive", "text": drive["essence"]})
  ...
  psychology=affect_pass.psychology_text(sheet),
  ```
  Both receive the card `sh` (`agents/character.py:4131-4133` `before_call(character_name(sh), sh, ...)`;
  `4742-4743` `holding_from(character_name(sh), sh, ...)`), while the payload is built live:
  `agents/character.py:4048` `_psych["drive"] = effective_drive(_psych, _interior)` and `4245-4246`
  `learned_beliefs`/`learned_associations` from `interior` — whose comment (4065-4076) says "the interior copy
  is ... the live one -- credence moves there, not on the card".
- Scenario: after a drive break (`interior.drive_override`, `story/character_schema.py:2218-2229`) the mind
  sees its new drive, but the affect pass appraises every event against "WHAT DRIVES YOU: <old essence>", and
  the read-back offers "drive" as the OLD essence: a want serving the new drive is not tagged `drive` (0.4
  instead of 1.0 in `affect.serves_priority`), and `impact:<a>` asks how the beat touched the old drive, whose
  strain then accrues against a drive the mind no longer holds. An association the story extinguished
  (strength 0 in `interior.associations`) is still quoted to both passes as "LEARNED"; ones learned in play
  never are. The skip writer reads the same card: `mind/skip_memories.py:522-552` (`card_of`, `_person`).
- Verified: `effective_drive` has one production caller (`agents/character.py:4048`), none in the passes.
- Confidence: CONFIRMED (code path); effect on answers unmeasured. Not registered.
- Fix: one "live psychology" view (the dict built at 4047-4048 plus interior beliefs/associations) handed to
  `before_call`, `holding_from` and the skip writer. Test: card drive A, `interior.drive_override` B; assert
  `holding_from(...).aims[0]["text"] == B` and "WHAT DRIVES YOU: B" in `before_call(...).state_text`.

### F8 — WRONG-SCENE: a held project drops out of the read-back's aims whenever the drive and steering intentions fill `MAX_AIMS`, so nothing can serve it explicitly

- `mind/character_jev.py:51` `MAX_AIMS = 5`; `agents/character_bare.py:236-243, 257` append drive, then
  steering intentions, then projects, and cut `aims=aims[:jev.MAX_AIMS]`.
- Reproduced (drive + four steering intentions — the `ordinary` rung's cap — + project p1):
  ```
  aims: [('drive','drive'), ('intention','i1'), ('intention','i2'), ('intention','i3'), ('intention','i4')]
  want_serves options: ['a0','a1','a2','a3','a4','situational']
  ```
  p1 cannot be chosen for `want:serves`/`held_back:serves` and gets no `impact:<a>` questions; its only
  remaining service channel is the room-name match (F6). A probationary project cannot earn its three serving
  beats while the ledger is full and lapses at 24; an established one reads `adrift` indefinitely. Whenever
  drive + steering intentions >= 5 (always at `broad`/`wide` with a full ledger) projects are cut.
- Confidence: CONFIRMED. Not registered (§1.56 notes "probation and service are unmeasured" without a cause).
- Fix: order aims drive -> projects -> intentions (projects are capped at two and are the tier meant to
  outrank), or exempt projects from the cut; the number is the owner's. Test: `holding_from` with four steering
  intentions and one project; the project id is in `h.aims`.

### F9 — WRONG-SCENE: notes about people and things fade on MINUTES in every clocked story — a stated fact leaves the notebook after ~75 story minutes, every person/thing note within about a story day

- `mind/theory_of_mind.py:104-115` (`_TOM_HALF_LIFE`: observation 5, stated_fact 18, emotion 6, goal 45,
  second_order 75, trait/identity/what_it_is/what_happened 400, what_will_happen 45), `:298-318` (`_elapsed`
  returns minutes when `elapsed_seconds` is given), sweep `:611-628` DELETES below `floor=0.05`.
  `persist/commit_memory.py:2345-2348` always passes `elapsed_seconds=_clock_seconds`, and every resolved beat
  advances the clock (`world/mechanics.py:553-583`, the unclaimed-beat floor), so "a turn a unit" no longer
  describes any story.
- Reproduced:
  ```
  t=0       {'Mara': stated_fact 0.9, 'the letter': what_happened 0.7, 'Tobin': trait 0.45}
  t=90min   {'the letter': ..., 'Tobin': ...}        # the stated fact is gone
  t=1560min {}                                       # everything is gone
  clockless +26 turns: all three survive
  ```
  Prune age at each kind's cap: observation ~22 min, emotion ~24 min, stated_fact ~75 min, what_will_happen
  ~2.7 h, goal ~2.8 h, second_order ~4.2 h, identity ~18.7 h, trait ~21 h, what_happened ~25 h, what_it_is
  ~27 h. The notebook's `people_and_things` (`mind/notebook.py:264-289`) IS this store, so a note the mind
  wrote ("Mara says the ferry leaves at dawn") is gone before the evening ends, and a night's skip ages every
  note by the whole span; `belief_credence` (place_purpose's told affordances) answers None for them. The
  module calls the minute unit "defensible and deliberate" for emotion (`:59-68`); the durable kinds' prune
  ages have no stated rationale and sit against "Good memory is the goal" (`mind/notebook.py:17-19`). The
  `_STRAIN_HALF_LIFE` note (`mind/affect.py:257-276`) documents and bounds exactly this unit split for strain
  (`_STRAIN_DECAY_FLOOR_PER_BEAT`). Second clock in the same ledger: greeting impressions are merged with no
  `elapsed_seconds` (`story/greetings.py:433`), so they fade by turns until first reinforced.
- Not yet visible in play: stamped hypotheses in the play DB span at most ~46 story minutes.
- Confidence: CONFIRMED (arithmetic, executed). Rates are the owner's.
- Fix (proposal): bound per-beat decay of the durable kinds as strain is bounded, or fade only
  emotion/observation by the clock; stamp greeting seeds with `last_updated_seconds`. Test: a stated_fact note
  survives a 90-minute gap; a trait note survives an 8-hour skip (at confidences the owner sets).

### F10 — WRONG-SCENE: the mood's home reads the card's resting arousal on a 0..1 scale, so a card left at the editor default (0) rests "drained"; arousal is signed everywhere else

- `mind/affect_pass.py:158-164`
  ```python
  arousal = mix._clamp(b.get("arousal", 0.5), 0.0, 1.0) * 2.0 - 1.0
  return mix.Mood({"pleasure": valence, "energy": arousal, "tension": arousal})
  ```
  Baseline from `character_initial_active_state` (`story/character_schema.py:2265`, default 0.0); the editor
  labels it "Mood arousal (0..1)" default 0 (`static/js/editors.js:133, 484, 735`); `story/greetings.py:474`
  seeds it on [-1, 1]; `mind/affect.py` treats arousal as signed (`_va_pair` [-1,1], `_sign` at +/-0.05).
- Reproduced: `home_mood({'valence':0,'arousal':0.0})` -> energy -1, tension -1; mood words at rest
  `['drained', 'calm']` (at 0.5: none). Read-only count over `characters`: 70 cards, 15 at exactly 0 and 2
  negative (both clamp to the floor) — 17 minds whose mood decays toward the bottom of both arousal axes every
  beat (`carried` -> `mix.decay`) and whose packet leads with "drained" when nothing is happening.
- Confidence: CONFIRMED (code + count); behavioural impact unmeasured. Not registered.
- Fix: one scale for `affect.baseline.arousal` (the owner's), converted at this one reader; at minimum read an
  unset default as the scale's middle (the function's own fallback is 0.5) and name it in
  `character_card_warnings` — the empty-field-fails-silently class. Test: the default card's home has energy and
  tension 0.

### F11 — WRONG-SCENE: a memory's habituation lands once per ROUND and once per re-delivery in the recent lane, so the turn's own memory is dulled to a fifth within two or three beats of a conversation

- `mind/affect_pass.py:505-509`
  ```python
  for m in memories:
      multiplier = 1.0
      if m.get("keyed", True):
          multiplier, felt.habits = mix.recall_lands(felt.habits, m["ref"], felt.clock)
  ```
  `memories_from` (236-288) includes every recent-lane row (delivered by code for 8 turns) on every round;
  `carried(..., earlier=...)` (167-176) hands the earlier round's habits on with no time elapsed, so a second
  round adds a second full `HABITUATION_STEP`.
- Reproduced (`affect_mix.recall_lands`, half a story-minute per beat):
  ```
  two rounds a beat: [1.0, 0.65, 0.2, 0.2, 0.2, 0.2, 0.2, 0.2]
  one round a beat:  [1.0, 1.0, 1.0, 0.75, 0.45, 0.2, 0.2, 0.2]
  ```
  The module's own rule is "one beat, one moment" (456-457; `_recall`'s "ONE MOMENT, FELT ONCE", 499); the owner's
  model is "full for a few recalls, less after" (`affect_mix.py:37-38`) — a re-delivery the mind did not ask
  for, or a second round of the same beat, is not a recall.
- Confidence: CONFIRMED (real function). Whether recent-lane delivery lands at all is the owner's.
- Fix: land once per memory per beat (skip refs `earlier` already landed). Test: two `before_call`s in one beat
  with `earlier`; the memory's `h` rose by one step.

### F12 — WRONG-SCENE: the affect pass tells the decision model that the mind's absent ties are "here"

- `mind/affect_pass.py:424-427` `parts.append("THE PEOPLE YOU KNOW HERE: " + ...)`, where `people =
  people_from(relationships)` (363-368) is the top three relationship rows by familiarity and `relationships`
  is deliberately not presence-scoped (`agents/character.py:3920-3938`: "she is a floor above him"). Every
  before/after appraisal question, including the connection/sociability/longing mood readings, reads a state
  claiming those people are present.
- Confidence: CONFIRMED (code); effect unmeasured (§6.15 notes standing feelings read as present).
- Fix: drop "HERE", or split present from known using the call's actor labels. Test: `state_text` with a
  relationship absent from `events` does not claim presence.

### F13 — WRONG-SCENE (language-pack hazard): the decision model's state frames are hard-coded English

- `mind/character_jev.py:388-445` (`state_text`: "YOU ARE", "WHAT YOU ARE AFTER", "WHAT YOU BELIEVE",
  "YOUR NOTEBOOK", "WHO IS HERE", "WHAT JUST REACHED YOU", "You said", "You did", "WHAT YOU WENT FOR",
  "YOUR OWN THINKING ..."), `:448-449` (`_NOTEBOOK_SECTIONS`), `:579-596` (`moment_text`), `:1094-1098`
  (`heard_question` "WHAT YOU HEARD", "someone"); `mind/affect_pass.py:377-393` (`psychology_text` headers),
  `:415-441` (`state_text`, "YOU ARE" at 421), `:567-580` (`acts_from` "You said", "You held back from").
- A Japanese story's requests mix English frames with Japanese questions and content; the packs' probes were
  run "with the name alone as state" (§1.184). No pack key exists for any frame (grep of `language_packs/`), so
  the parity guard cannot see them.
- Confidence: CONFIRMED (presence); effect on Japanese answers unmeasured.
- Fix: move the frames into the packs and probe each pack on its own battery. Test: parity test over the frame
  keys in en and ja.

### F14 — WRONG-SCENE (low): reviving a dormant or blocked intention bypasses the attentional cap

- `mind/affect.py:1384-1388` (a restating `add` revives) and `:1456-1457` (`progress` revives) call
  `_revive_intent` without counting active rows; the cap is checked only for a fresh add (1389-1395). The
  docstring (1337-1339) says "at most `intent_cap` active intentions".
- Reproduced: four active at `intent_cap=4` + one dormant -> `progress` on it -> 5 active, no warning; same via
  a restating add.
- Confidence: CONFIRMED. Fix (owner's rule): refuse at the cap with the refused-add notebook fallback, or
  displace the stalest by name. Test: the snippet.

### F15 — WRONG-SCENE (low): a seeded memory's age is measured against the wrong origin

- `mind/affect_pass.py:775-776` stamps a seeded row on the STORY clock (`record["at"] =
  round(float(r["encoded_at_seconds"]) / 60.0, 4)`); `_recall` (523-525) subtracts it from `felt.clock`, the
  mind's `mood_clock`, whose origin is its first affect pass (`carried`, 178). Lived rows are stamped on
  `mood_clock` (481, 515, 605). A mind first called at story minute T0 (a promoted resident, a late arrival)
  reads its seeded past T0 younger: promoted on day three, an inherited memory carries 0.65 of its feeling where
  0.48 is due. The docstring (737-739: "a feeling from nine days back fades like one lived nine days back")
  holds only for T0 ~ 0.
- Confidence: CONFIRMED by trace. Fix: stamp seeded `at` on the mind's clock, or put `mood_clock` on the story
  clock's origin. Test: a mind first called at minute 4320; the recalled multiplier equals
  `memory_fade(4320 + D)`.

### F16 — WRONG-SCENE (low): probation counts global turns, so a mind dormant across the fuse returns to a lapse with one beat's notice

- `mind/affect.py:1946-1949` (`idle = turn_idx - last_served_turn`), `:1914-1924` (`_LAPSE_AFTER = 24`, "a
  lapse is never the first notice"); the drift marker (`agents/character.py:2602`, 8) is shown only on beats the
  mind is called. Out of the cast for 24+ turns, it sees `adrift` on its first beat back and loses the project
  at that beat's commit unless that beat serves it. Contradicts `DESIGN_LONG_TERM_GOALS.md:246-247` and
  `AGENTS.md:469`.
- Confidence: CONFIRMED by trace. Fix (owner): count idle on the mind's own beats, or never lapse on a first beat
  back. Test: `settle_probation` after a 30-turn gap keeps the project one beat.

### F17 — SILENT-NOOP: a struck project with no `satisfied_when`, read back as "done", stays held

- `agents/character_bare.py:536-539`
  ```python
  done = jev.pick(answers, f"nb:{j}:strike") == "done"
  out["project_ops"].append({"op": "satisfy" if done else "displace", "id": row["id"],
                             "why": entry["strike"]})
  ```
  `mind/affect.py:1855-1862` refuses `satisfy` on a criterion-less project with a warning only.
- Reproduced: `apply_project_ops([pa1 with satisfied_when ''], [], [{'op':'satisfy','id':'pa1','why':'the
  winter is over and the light never failed'}], 40)` -> pa1 still live. Authored projects routinely have no
  criterion (`story/character_schema.py:2370`), and the "done" option reads "It is finished: what would end it
  has come." (en `strike_kind.done`) of a project that names no end. The warning's advice ("displace it with a
  reason") reaches no one: code wrote the op, the mind sees the project again next beat, its strike gone.
- Confidence: CONFIRMED. Fix: send `displace` with the strike's reason when the shown project has no `until`
  (or skip `strike_kind` for it); the floor stays. Test: compile such a strike with "done"; the project ends in
  `former_projects` with the reason.

### F18 — SILENT-NOOP (low): the reply's tails are cut without a word

- `mind/character_jev.py:248` (`steps` -> `out[:MAX_STEPS]`, 8), `:323` (`notebook_entries` ->
  `[:MAX_NOTEBOOK_WRITES]`, 8), `:251` + `:847` (`lines_of(..., "changes", MAX_CHANGES)`, 6). The ninth step is
  absent from the compiled sequence (`agents/character_bare.py:726` iterates `jev.steps`), a ninth notebook
  entry (a strike included) and a seventh change line vanish; no warning anywhere. No leak (dropped, not passed
  unfloored).
- Confidence: CONFIRMED. Fix: warn on truncation; caps are the owner's. Test: a nine-step reply yields a warning.

### F19 — SILENT-NOOP (low): a rewrite answer without a key after a keyed one binds to an already-claimed memory

- `mind/skip_memories.py:689-695`
  ```python
  order = iter(sorted(flagged))
  for episode in episodes_of(raw):
      index = episode["index"] if episode["index"] is not None else next(order, None)
  ```
  Keyed answers do not consume `order`, so with flagged {0, 2} and answers `[{index:0}, {index:None}]` the second
  is bound to 0 again, memory 2 gets no candidate and falls to the sentence drop. The class of the project
  memory "models split keyed answers -- merge by key".
- Confidence: CONFIRMED by reading. Fix: draw the unkeyed fallback from flagged indices no keyed answer claimed.
  Test: the two-answer case binds the unkeyed rewrite to 2.

### F20 — CRASH (low): `before_call` is documented "Never raises" but parses stored state outside its try

- `mind/affect_pass.py:449-486`: `carried(...)` (`float()` over stored `mood_coords`/`mood_clock`) and
  `_recall(...)` (`recall_lands` -> `float(prior.get("at", now))`) run outside the `try` that wraps only
  `appraisal.appraise`. A `mood_habits` entry with `"at": null` or a non-numeric coordinate (imported or
  hand-edited state) raises into `character_step`.
- Confidence: PLAUSIBLE (no producer writes those shapes today). Fix: fail open around the parse with the note.
  Test: `before_call` with `mood_habits={"m1": {"h": 0.4, "at": None}}` returns a Felt.

### F21 — DEAD / STALE-DOC: `resolve_affect`'s self-report machinery is unreachable on the live path, and the module still describes it

- `mind/affect.py:937-950` synthesises an undercurrent only when `not clear_under and prop_under is None`;
  the only live producer of `proposed` is `affect_pass.given_affect` (`agents/character.py:5034-5038` ->
  `persist/commit_memory.py:1865-1869`), which always carries an explicit `"undercurrent"` key
  (`affect_pass.py:650-668`). The label gate is inert too: engine labels are `"<word> (<about>)"`
  (`affect_pass.label`, 636-641), never an `AFFECT_LEXICON` key, so `label_matches` returns True; only 7 of 58 pack
  emotion/mood words are lexicon keys at all ("joy", "distress", "relief", "pride", "shame" are not).
- Reproduced: strong drive-loss appraisal + given affect -> no synthesised undercurrent; the same proposal
  without the key -> still None (unknown label).
- Stale text: `mind/affect.py:3-6` ("Character agents emit a proposed interior state each turn: a mood
  label..."), `:25-28` ("Suppression is not deletion ... stored as an explicit *undercurrent*"), `resolve_affect`
  (c)/(d) at `:836-846` ("surface label = the model's proposed label (the character's *self-report*)").
  `_undercurrent_label` (786) is reachable only through this branch; `quadrant_label` substitution only from
  tests and `story/greetings.py:484-485`.
- Confidence: CONFIRMED. Fix: rewrite the docstrings (the proposal is the engine's mood); the owner decides
  whether the branch goes or is fed. Doc-truth test: `given_affect` output passes through `resolve_affect`
  with its undercurrent unchanged.

### F22 — DEAD: helpers with no production caller (repo-wide grep incl. tests, tools, extensions, string forms)

- `mind/affect_mix.py:754` `rehabituate` — tests only; its promise ("a reinterpretation ... resets its
  habituation at once") is unwired: a re-read memory (`why_read` "reread") still lands habituation
  (`affect_pass.py:508`).
- `mind/affect_mix.py:775` `mood_name` and `:184-187` `OCTANTS` — tests only ("for logs and traces": no log
  uses it).
- `mind/notebook.py:404` `find_reminder` — no caller anywhere, tests included.
- `mind/canon_provenance.py:173` `outranks`, `:192` `unavailable` — tests only.
- `mind/skip_memories.py:1192` `is_skip_memory` — tests only.
- Confidence: CONFIRMED. Fix: delete, or wire `rehabituate` where a dispute is recorded.

### F23 — STALE-DOC (several)

- `mind/canon_provenance.py:43` and `:372`: "seven" adjudicated dispositions; the tuple holds eight
  (`web_reference`).
- `mind/affect_mix.py:610-612` (`decay`): "pleasure below home more slowly"; `NEGATIVE_DECAY_FACTOR = 1.0`
  (208) since 2026-09-26.
- `mind/knowledge_circles.py:37-40`: "Circles one character may hold at once" — the cap counts story rows only
  (sheet circles uncounted), and eviction (`:94-97`) is silent.
- `mind/thoughts.py:17-20` ("No other mind ... ever reads it") — see F1.
- `docs/design/DESIGN_LONG_TERM_GOALS.md:182-183` (F3), `:246-247` (F16).
- `docs/design/DESIGN_JEV_CHARACTER_PASS.md:247-248` ("Temperament is home ... the card's `stress_profile` and
  traits. No new card field") — the code's home is the initial-mood baseline (`affect_pass.home_mood`);
  `:353-355` "pleasure below home decays more slowly" (neutral since 2026-09-26).
- `mind/affect_pass.py:34-37` ("every reader of the character's affect now reads the engine's mood") —
  readers read `resolve_affect`'s blend (registered §6.15; see Already registered).

## Efficiency

### E1 — the mood reading: 54 questions on every before-call, every round
`mind/affect_pass.py:471-472` -> `affect_appraisal.questions_for(..., mood=True)` (`:174-180`): 14 `dim:*`
(five steps) + 40 `mood:*` (four grades), ~230 options, in every `before_call` that has anything to appraise —
and the recent lane makes that every call, including each round of an interaction-loop beat (`earlier` does not
skip it). The reading only `settle`s the mood by `REACTIVITY` 0.25 (`affect_mix.settle`). Hotness: per character
per round per beat. Gain: asking it once per beat halves it on loop beats; whether it earns its place at all is
the owner's, after measuring what `settle` adds beyond `mix` (§6.15 measured the shape, not the margin).

### E2 — `skip_memories.write_rows` dumps the whole chat's memory bank under the write lock, per mind
`mind/skip_memories.py:1321-1326`: `dump_chat_memories(chat_id, inline_vectors=False)` (every character's
rows) inside `transaction()`, once per mind, to pick out that mind's <= 8 skip rows; then
`carry_memories_forward` (`persist/checkpoints.py:1793-1805`) parses and rewrites every later checkpoint blob
(each holding the whole bank) — again once per mind. Hot when the job lands after the next beat began, which the
module expects ("the next beat may well start" inside the writers' ~90 s). Gain: a targeted `SELECT ... WHERE
chat_id=? AND char_id=? AND turn_id=? AND event_key LIKE 'skip:%'`, and one carry per job for all minds, takes
O(bank) work and N-1 checkpoint rewrites out from under the lock that blocks the next commit. Cheap.

### E3 — `mood_habits` grows without bound
`mind/affect_pass.py:193` persists `felt.habits` whole; `affect_mix.recall_lands` adds an entry per memory
ever recalled; nothing prunes (`rehabituate` is dead, F22). Play DB: max 80 entries / 4.5 KB after 36 turns
(chat 178, char 83), ~2.2 a turn, rewritten every commit and copied into every per-turn checkpoint and archive.
Gain: at `persisted`, drop entries whose rest-decayed `h` is below ~0.005 — they behave exactly as absent
(the multiplier is 1.0 below `HABITUATION_GRACE` and the next landing starts from ~0). Cheap.

### E4 — the dispute check reasks every claim memory against the full state
`mind/character_jev.py:530-539` (`before_questions`): one yes/no per claim-bearing delivered memory, with the
memory text, against a state that already quotes every memory — every beat something reached the mind (32
questions on chat 159 turn 23 by the module's own count). Already trimmed by `DISPUTABLE_ORIGINS`; modest gain
from asking only memories recall placed in the top N.

### E5 — `check_and_mend` asks the decision model serially per memory
`mind/skip_memories.py:1113-1167`: up to 8 memories x 2 requests, then each rewrite candidate re-checked, all
sequential. Out of band; a thread pool over memories (as `run_skip_memories` does over minds) shortens the
window in which the job's write contends with the next beat.

### E6 — one large state re-sent in up to five requests per character call
`affect_pass.before_call`, `after_call`, `character_jev.ask_before` (dispute), `ask_after` (read-back, echo) each
send a state quoting every delivered memory (~69 rows x 300 chars ~ 20 KB on the owner's chats), and `_batches`
re-sends it per batch. Low priority; for the cost bill.

(Sheet parsing: `skip_memories.card_of` normalises a raw sheet five times per mind — 28.8 ms vs 0.6 ms
normalised once, out of band, negligible. `claim_similarity` is 17 us/call; no hot quadratic found.)

## Already registered

- **Two records of one mood** (`mood_coords` vs the stored `affect.surface` that `resolve_affect` blends) —
  `docs/UNBUILT_CHARACTERS.md` §6.15 (and `Design.md:260`). Added measurement: the stored surface DOUBLE-COUNTS
  the beat — commit's `resolve_affect` adds the read-back's appraisal delta (goal impacts, pleasantness,
  somatic) on top of a proposal the affect pass already moved with the same events. Synthetic replay, same good
  news six beats running: mood pleasure handed to the mind 0.14 -> 0.49, stored surface valence 0.28 -> 0.81.
  Recall's mood-congruent lane reads the stored surface (`mind/memory_jev.py:436-441`, `feeling_valence`) and
  memory rows' `encoding_valence` are stamped from it (`persist/commit_memory.py:1870-1874`).
- **The circularity gate** (`affect._CRITERION_RESTATES_SIM`) refusing journeys — §1.56.
- **Probation and service unmeasured under the bare contract** — §1.56 (F3, F8, F17 are mechanisms beneath it
  that the entry does not name).
- **The concern-settle wording** ("the worry question's six misses of 21") — §6.15. (F4 is the separate,
  unregistered ruling.)
- **Surface habituation ships default-off** — §1.41.
- **The tell scene floor's live rate** — §1.184 (`TELL_SCENE_FLOOR`).
- **Knowledge circles have no writer** — `Design.md:322` residual ("no caller yet writes it"), not in any UNBUILT
  file. `join_circle`/`leave_circle` are test-only. Q7 verified: `leave_circle` edits story rows only and
  `effective_circles` always unions the sheet, so a sheet-authored circle cannot be stripped; but
  `leave_circle` returns True for a sheet circle the story had ALSO joined, while the mind stays inside it.
- **§1.166 (UNBUILT_WORLD)** — the skip beat reads the stored clock. `skip_memories` adds no instance: the job
  pins the beat's frame (`schedule_skip_memories`) and reads only the clock's stored anchor, which is stable.

## Structure notes

- `mind/affect.py` (2600) has five natural seams: mood dynamics (~300-1000: appraise, resolve_affect, blend,
  decay, habituation); wants and intentions (~1000-1680: normalize_wants, apply_intent_ops,
  settle_intent_world_anchors); projects (~1680-2230: adoption_refusal, apply_project_ops, settle_probation,
  projects_served_this_beat, goal_slot_currency, project_boundary, serves_priority); drive rupture
  (~2230-2440); leak scan and tells (~2440-2600). Monoliths in miniature: `apply_intent_ops` (~170 lines),
  `resolve_affect` (~180 with docstring), `appraise` (~150).
- `mind/skip_memories.py` (1482): record (record_rows/how_it_went), number floor (`_digit_mentions`, `_compose`,
  `unsupported_numbers`), the decision check (ask_model/flags_of/check_and_mend ~70 lines), rows and write, job.
- `mind/character_jev.py`: `after_questions` (~230 lines) is a monolith in miniature.
- The room-naming class (F6) belongs in one function shared by mind/affect, agents/character,
  world/skip_itinerary and mind/memory_routes. The "live psychology" read (F7) belongs in one function shared by
  the payload builder, both decision passes and the skip writer.
- Six clamp helpers with three NaN semantics: `affect._clamp/_float_or` (fallback), `affect_mix._clamp` (0.0),
  `theory_of_mind._clamp01` (1.0, F5), `psychology_runtime._clamp/_float` (default), `skip_memories._clamp`
  (default, finite-checked).
- Module-level mutable state: none in the assigned files (constants only). Writers of persistent state go
  through `wset_for_frame` (knowledge_circles), `qi` (affect_pass.feel_seeded, inside no transaction — one
  UPDATE per seeded row) and `transaction()` (skip_memories.write_rows).

### The assignment's questions, answered

1. **Bounds.** Every stored affect/stress/pain/pleasure value is clamped on write (`affect._clamp`,
   `psychology_runtime._clamp`, `affect_mix.mix/settle/ease`); `decay` stays inside bounds by construction;
   `persisted` rounds and drops |v| <= 1e-4 (NaN dropped too). Counters `sustained_beats`/`comfort_beats` grow
   unbounded but only feed decaying terms. Unbounded growth: `mood_habits` (E3). Scale, not clamp, is the
   defect: arousal (F10). NaN: F5. No float drift found: per-beat rounding to 4 dp.
2. **Projects.** The cap of two holds on every production writer (card seed loop, `character_projects`,
   `adoption_refusal`). Probation is in global turns (F16); service is starved by F8 and inflated by F6; a
   displace always carries a reason, but an authored project re-seeds after its "displaced" record rolls out
   (F3) and a criterion-less strike is lost (F17). `serves: "drive"` against an empty drive: the bare read-back
   offers the drive aim only when its essence is non-empty (`character_bare.py:236-237`), so the live path
   cannot produce it; `normalize_wants` (`affect.py:1055`) still accepts it from any producer and the payload
   warns (`agents/character.py:4053-4064`).
3. **theory_of_mind inputs.** Pure; every live input is the mind's own (its notebook entries, the decision
   model's nudges asked against `moment_text` = who is here + what reached it, its own stored mind_models). No
   read of another mind's state, hidden traits or Director truth found. Defects there are F9 and F5.
4. **psychology_runtime fields and sources** (commit: `persist/commit_memory.py:1896-1924, 2223-2232`):
   | function | reads | source |
   |---|---|---|
   | `resolve_hedonic` | `previous.{pain,pleasure,source,charge,stim_continuity,stim_climb,comfort_source,comfort_beats,stimulus,sustained_beats}` | own `active_state.hedonic` |
   | | `appraisal.somatic_impact.{pain,pleasure,why}`, `novelty` | `affect.appraise` over the read-back's answers about own observations |
   | | `interoception.{pain_sensitivity,pleasure_sensitivity}` | own card |
   | | `body_state.{injury,air,stamina}` | `vitals_of(sc, cname)` — own vitals |
   | | `released` | read-back `released` |
   | | `ambient_comfort/_source`, `ambient_discomfort/_source` | `comfort_level`/`discomfort_level(sc, cname, ...)` — own body |
   | | `stimulation.{active,tier,intensity_floor}` | `stimulation_of(sc, cname, ...)` — contacts on own body |
   | `resolve_stress` | `previous.{strain,activation,load,coping_mode,overloaded}`; `appraisal.{novelty,controllability,coping_potential,norm_compatibility,memory_echo.threat_bias}`; `profile.{baseline_reactivity,recovery_rate,overload_threshold}`; `hedonic.{pain,pleasure,charge}`; `goal_impacts[].{impact,certainty}`; `proposed_mode` | own state; read-back; own card `stress_profile`; this beat's hedonic; `appraise().impacts`; read-back |
   | `apply_belief_updates` | `existing`, card `self_model.{beliefs,protected_beliefs}`, `updates[].{belief,evidence,operation,confidence,target_belief,emotional_charge}` | `interior.beliefs`; own card; own result |
   | `apply_association_updates` | `existing`, card `learning.associations`, `updates[].{cue,evidence,amount,operation,appraisal_bias,response_tendency}` | `interior.associations`; own card; own result |
   | `cognitive_absorption` | `hedonic.{pain,pleasure,sustained_beats,charge,saturated}`, `stress.activation` | own settled state |
   Nothing reads another mind's vitals or state; the module docstring holds.
5. **skip_memories.** Clock: no new 1.166 instance (above). Work not done: `how_it_went` words for every
   outcome and reason exist in both packs (checked `compositor_text` for all keys, en and ja), and the `outcome`
   question checks them. Reroll duplicates: none — `write_rows` deletes the mind's earlier rows for the beat
   inside its transaction after `still_committed`, and `carry_memories_forward` replaces by predicate. Defects:
   F2, F19, E2, E5.
6. **character_jev.** Keyed answers are merged by distinct keys (`ask_before`/`ask_after` `update`); the read-
   back keys are enumerated identically on ask and read (`concern:{k}`, `rel:{p}`, `nb:{j}`, `tell:{j}`). No
   missing key is read as a positive: `pick`/`yes` give None/False, `read_before` and `heard_question` read a
   missing yes-share as 0.0 (fewer actions), `affect_appraisal.read` leaves unanswered out. Silent consequence:
   a partial answer drops `released` (charge never discharges) and `keep:` lines without a warning. Yes/no
   questions with no named cause (candidates for a per-pack probe, not findings): `dispute`, `concern_settled`,
   `cue_present`, `contact_end`, `line_expects`, `done_talking`, `heard_question`, `released`; `rel_break` and
   `tell_outside` name theirs. Reader side of `last_reasoning`: F1.
7. **knowledge_circles.** Verified (Already registered).
8. **Efficiency.** E1-E6. Appraisal passes per memory per beat: one `recall_lands` per memory per ROUND (F11),
   three model questions only for unfelt/reread/pondered rows, a dispute question per claim memory (E4).

## Docs checked

- `AGENTS.md:409-417` (the mood is given; inputs exactly the call's own) — HOLDS for scope of inputs, qualified
  by F7 (card, not live), F12 ("here"), F1 (trace).
- `AGENTS.md:468` (projects not on the capacity ladder) — HOLDS.
- `AGENTS.md:469` ("never let the engine adopt, satisfy or displace one"; "a lapse must never be the first
  notice") — FAILS: F3, F16.
- `AGENTS.md:541` (knowledge circles; never strip a sheet circle) — HOLDS for `leave_circle`; the seam has no
  production caller, which AGENTS.md does not say (Design.md:322 does).
- `Design.md:231` (ToM "event-triggered — tom_triggers on the flow") — HOLDS (`agents/character.py:3912`).
- `Design.md:260` (mood given; residual two records) — HOLDS; registered.
- `Design.md:322` (circles residual) — HOLDS.
- `DESIGN_LONG_TERM_GOALS.md:182-183` — FAILS (F3); `:242-248` probation numbers 3/12/24 — HOLD; "never the
  first notice" — FAILS for absent minds (F16).
- `DESIGN_JEV_CHARACTER_PASS.md:247-248, 353-355` — STALE (F23); `:175, :1230` describe the concern settle check
  the owner's later ruling retires (F4).
- `CLAUDE.md` psychology ("`serves: drive` stays valid against an empty drive") — on the live bare path the
  drive aim is offered only for a non-empty essence; the card and payload warnings name an empty drive. HOLDS
  as a description of the authoring hazard.
- `CLAUDE.md` ("projects capped at two") — HOLDS on every production writer.
- `mind/psychology_runtime.py:1-6` ("never receives another character's private state") — HOLDS (Q4 table).
- `mind/thoughts.py:17-20` — FAILS on the F1 paths.
- `mind/notebook.py:17-19` ("Good memory is the goal, never realistic forgetting") — HOLDS for reminders; the
  `people_and_things` half fades per F9.
