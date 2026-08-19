# Triaging `UNBUILT.md` by felt quality of play — 2026-08-19

**Question asked:** of everything in the register, which items would produce the
most NOTICEABLE improvement in the quality of play if addressed now? Ranked by
what a reader would feel in the fiction, then by cost.

**Method.** The whole of [`docs/UNBUILT.md`](../UNBUILT.md) (5,071 lines, 127
`###` entries) was read, then every shortlisted claim was checked against source
and — wherever the shape was countable — against the owner's live `engine.db`,
opened `mode=ro` and never written. Every number below carries the query that
produced it. Where reach could not be measured the word is **unmeasured**, not
an estimate.

**Two denominators matter and are easy to get wrong.**

- The corpus is **2,356 turns / 71 chats / 101 character banks / 9,749
  memories**. Corpus-wide rates mix eight months of engine versions together.
- `_engine_notes` (the persisted per-step warning channel) only exists for turns
  played since alpha 6.9. The instrumented population is **290 `director_resolve`
  / 306 `commit` / 328 `interaction_loop` / 304 `narrator` steps**. That is the
  only honest denominator for a warning rate, and it is the RECENT engine —
  which makes it the better sample, not the worse one. Rates below are given
  against it, with the corpus-wide figure beside it where both are meaningful.

---

## 1. The top 10, ranked most-felt first

### 1 — §1.11a `flow.reactors` answers two different questions

**What a player would notice.** A character who is standing in the room, awake,
watching, stops missing the thing that just happened. Today their entire account
of the beat is the aftermath: they perceive the onset never, so they answer the
consequence instead of the act, and the narrator — seeing no reaction — is free
to render the absence as a chosen silence nobody chose.

**Measured reach.** `perception_act`'s perceiver list *is* `flow.reactors`
(`agents/perception.py:1618` `continue`s on anyone not in it). Using the
engine's own answer for who was present — who received an outcome view:

```python
# for each turn, active-variant content of director_interpret + perception_act + perception_outcome
witnesses = {k for k in perception_outcome["views"] if k != "player" and not k.startswith("extra:")}
reactors  = {str(x) for x in director_interpret["flow"]["reactors"]}
act_views = {k for k in perception_act["views"] if k != "player" and not k.startswith("extra:")}
```

| | corpus-wide | turns played on/after 2026-08-01 |
|---|---|---|
| beats with ≥2 character witnesses | 975 | 162 |
| …with ≥1 witness missing from `reactors` | **757 (77.6%)** | **64 (39.5%)** |
| (beat, character) pairs present at outcome | 4,292 | 796 |
| …that got **no act view at all** | **1,639 (38.2%)** | **111 (13.9%)** |
| beats where ≥1 present character got no act view | 765 / 2,249 (34.0%) | 67 / 594 (11.3%) |

The alpha 6.9 prompt sharpening genuinely moved it — 79%→39.5% — and did not
close it. One in seven character-presences in a recent beat still perceives the
onset never.

**Severity.** Durable. A character who never perceived the onset has no
appraisal of it, so no `goal_impacts`, no drive strain, no psychology commit and
no memory of having chosen anything. That absence is written into the bank and
compounds.

**Cost.** The register frames the fix as expensive because "every added reactor
is a character-step LLM call". **That is true of the pacing question and false
of the perception question, and they are separable at zero cost.** Perception is
deterministic — there is no `perception` role in `providers.ROLES` and the
module imports no model seam (pinned by `tests/test_perception_has_no_model.py`)
— so widening `perception_act`'s perceiver list to everyone the scene says is
present costs **no model call at all**, while `interaction_loop` stays gated on
`flow.reactors` and the turn's spend is unchanged. Small change, one function's
perceiver derivation. The full structural split (an onset-audience field beside
a reactor field, schema + prompt) can follow later or never.

---

### 2 — §1.10 + §1.24's byte-identical bullet + §3.9's ageing bullet: an entity's free-text `state` never ages, and a mind reads its own stale copy

*(These are one defect wearing three numbers — see the MERGE list.)*

**What a player would notice.** The prose stops describing people doing what
they stopped doing. Today a body's `posture` / `activity` / `held_items` blob is
overwritten only when a model happens to rewrite it, and a character is handed
its own stale copy as present-tense interoception every beat — so a mind that
lowered its wrench still reads *"raised to chest level, aimed forward into the
dark"* as what it is doing now.

**Measured reach.**

```sql
-- the engine's own detector, on instrumented commits
SELECT ... FROM steps s JOIN variants v ON v.step_id=s.id AND v.active=1
WHERE s.key='commit' AND v.content LIKE '%byte-identical%';
```
**62 of 306 instrumented commits (20.3%), 122 instances.** Subjects are
overwhelmingly the cast mirrored as scene entities: Hinami 44, Tamamo 32, The
Doctor 25.

```sql
SELECT count(*) FROM world_entities;                        -- 599
-- payload['state'] a non-empty dict:                       -- 408 (68.1%)
```
Walking every checkpoint in `chat_id, turn_idx` order and hashing each entity's
`state`: **2,074 unchanged runs across 425 (chat, entity) pairs; median 1 turn,
p90 14 turns, max 138; 172 pairs hold a run of ≥15 turns byte-identical.**

**Severity.** The worst on this list, because it is a **read-back loop**.
`agents/perception.py:2869` composes `composer.body_state_percept(entity_state)`
(`agents/composer.py:788` — `posture`, `activity`, `held_items`, channel
`interoception`, source "you"), so a stale blob is not merely bad prose: it is
what the mind believes about its own body, and it feeds the next declaration and
the memory of the beat. The earlier "skip the update" fix was reverted as
durable corruption (`persist/commit_entities.py:257-335` now warns and commits
anyway, pinned deliberately by
`tests/test_pipeline_audit_leak_gaps.py:728-795`).

**Cost.** Medium. Wants an ageing/reconciliation rule for free-text state keys,
not a guard — and the reverted fix is the record of what not to do. `contacts`
was fixed at source; this is the rest of the same disease. No schema change.

---

### 3 — §1.37 The aversive half of the stress model has never run

**What a player would notice.** Characters can currently be excited and cannot
be threatened. Fix it and a body under real pressure starts accruing strain,
crossing coping thresholds, and behaving like something is at stake.

**Measured reach.** `mind/psychology_runtime.py:277` reads
`appraisal.get("goal_impacts")` and weights `threat` at **0.55** — more than
every other aversive term combined (`:291`). Its only production caller
(`persist/commit_memory.py:1046-1051`) passes `affect.appraise`'s return, and
that dict has no `goal_impacts` key (`mind/affect.py:593-621`). So `threat` has
always been `0.0`.

```python
# chat_chars.state -> active_state.stress, all 101 banks
banks with a resolved stress block: 33
  strain      min 0.0235  median 0.0596  max 0.3608
  load        min 0.0000  median 0.0266  max 0.5949
  activation  min 0.0286  median 0.3518  max 0.7984
  overloaded true: 0 of 33
```
`overloaded` has fired **zero times in the engine's history**; strain has never
reached half its own threshold.

**Correction to the entry, in the owner's favour.** The list *is* returned now —
under the name `impacts` (`mind/affect.py:593-599`, added for
`_relief_impacts`). So this is a **name agreement**, not new plumbing: pass
`goal_impacts` as its own parameter so no caller shape can silently omit it.

**Severity.** Not a wrong thing on the page — a whole missing dimension of
conduct. Corroborating signal that the character side is producing the data:
characters emit `appraisal.goal_impacts` constantly (the ungrounded-citation
warning for that exact field fires on **69 of 328 instrumented
`interaction_loop` steps, 21.0%, 109 instances**).

**Cost.** The smallest diff in the top ten. The risk is not the code: it changes
the emotional trajectory of every existing character in the corpus, so it is a
behavioural release with `overloaded` moving off zero as the row to watch — not
a silent correction.

---

### 4 — §1.23(d) / §1.56 The project tier has never once been entered

**What a player would notice.** NPCs would start having a life's work, and
walking somewhere for a durable reason across many beats instead of re-deriving
an aim each turn.

**Measured reach.**
```python
# chat_chars.state -> interior
banks: 101
  carrying a projects/former_projects key at all: 33
  HOLDING a project:        0
  holding a former project: 0
  bank whose state mentions project_review: 6
```
Zero, 329+ turns after the v4 fix that made the review beat reachable, and after
`project_ops` was added to `CharacterOutput` (`llm/schemas.py:2866`,
`ce2ab6a`/`ce6a2ab`, 2026-08-10). **Both known gates are open and adoption is
still zero.**

**Severity.** `CLAUDE.md` records projects as *what made NPCs pass the maze
without any alteration to their drives*, and as the tier that carries "take the
injured one to a doctor, go home, go to the bar". The longest single block in
the character prompt is behind a tier that has never run.

**Cost.** The register's own rule blocks a fix: *"Do not change a gate on this
until one of the three candidates is measured"* — deliberation refusing,
adoption losing the beat auction to a drive-serving want, or `project_review`
firing on beats where nothing is a plausible life's work. So the work is a
`tools/fire_rates.py` run plus a payload read, not a code change. Cheap to
measure, unknown to fix.

---

### 5 — §1.20 (absorbing §1.14) A body's room changes with no warrant

**What a player would notice.** Scenes stop quietly coming apart — two people
conversing from different rooms, a fight written at a door while two of its
three participants stand a room away.

**Measured reach.** Each turn judged against its **own pre-beat checkpoint**, so
"changed" means changed:

```python
prev = json.loads(checkpoint[chat_id, turn.idx])["world"]["scene"]["positions"]
pos  = director_resolve["state_diff"]["positions"]
changed = [w for w,r in pos.items() if prev.get(w) not in (None, r)]
```
- 2,280 turns comparable to their own checkpoint
- **746 bodies actually changed room** in `state_diff.positions`
- **91 of those 746 (12.2%)** happened on a beat whose `director_interpret`
  declared no `movement.to_room` **and** whose whole declaration contains no
  locomotion verb of any kind — across 20+ chats (27:14, 38:10, 59:9, 63:8,
  64:8, 23:6, …)
- separately, 706 turns (30.9%) wrote positions for 2,056 bodies with no
  declared player movement at all

**Severity.** The highest single-beat severity in the register — everything
downstream is correct given a wrong geometry, so a resolve is asked to
adjudicate a fight between bodies that cannot see, hear or reach each other, and
a stronger model returns more confident nonsense.

**Cost.** Medium, and two-thirds of §1.14's headline is already paid: the
route/adjacency floor now exists as `_unreachable_position_writes`
(`agents/director_movement.py:554`, wired at `agents/director.py:3237`, pinned
by `tests/test_position_passability.py`). What survives is the **authority**
half, and it is hard for the reason the entry states: three warrants exist and
only two are legible. `world/offscreen.py:81` already cites §1.20 as open.

---

### 6 — §1.18 (exposure half) + §2.14 (guessed garment spans): the fallback is deciding physical facts, and the detector is written and unwired

**What a player would notice.** People stop reading as naked from the waist
down, and sheltered rooms stop being weathered as though they were open sky.

**Measured reach.**
```python
# across all 73 scene blobs in world.key LIKE 'scene%'
rooms in live scenes: 475      with an authored `exposure`: 62 (13.1%)
worn garment records (regions ledger): 588
  span the cue table GUESSED (attire.span_is_a_guess, excluding hand-placed): 114 (19.4%)
  across 69 distinct bodies
  worst repeat offenders: fitted tank top ×22, **Nagajuban ×20**, loafers ×6, wristwatch ×6
```
A Nagajuban is a full-length under-kimono. It lands on the torso alone, so
twenty live garment records report legs and groin **bare** on a clothed body.
`weather.room_exposure` (`world/weather.py:296-325`) still consults the 36-word
`_ENCLOSED_WORDS` list for the other 413 rooms, **recomputes the guess from the
room name on every read, and stores nothing** — so a wrong guess cannot be
corrected by a host and editing the word list silently rewrites the past.

**Severity.** Not durable corruption, but constant and visible, and the attire
half surfaces at exactly the dramatic moment (something comes off).

**Cost.** The smallest real work in the top ten, because **both answers are
already written and neither is called.** `attire.span_is_a_guess` /
`guessed_spans` (`story/attire.py:319,347`) have zero production callers —
verified: the only references are each other and
`tests/test_attire_displacement.py:724,731` — and the docstring names the seam
it wants (the commit path handing them to the Director). The exposure half is
"seed the existing guess once at commit and STORE it", the same shape
`restraint_scan` / `unconsciousness_scan` already use.

---

### 7 — §1.62 + §3.4 X12: a co-player is a second-class perceiver, and the register wrongly reads as unreached

**What a player would notice.** A second person at the table would get an
opening scene at all, and would perceive acts as they happen rather than only in
the aftermath.

**Measured reach.** The register files §3.4 as "all multiplayer-only, which is
why they survived", and `chat_personas` holding 3 rows makes that look decisive.
It is wrong:
```sql
SELECT count(*) FROM steps WHERE key='narrator_extra';   -- 135, across chats 9 (25), 10 (100), 20 (10)
```
Idle co-players are still rendered every beat (`agents/runtime.py:66-86`), so the
row count understates traffic ~7×. And on all 135 of those turns:
- `perception_act` (`agents/perception.py:1534`) contains **zero** references to
  `extra` / `ctx.extra_players` — only `perception_outcome` builds `extra:<pid>`
  perceivers (`:2015,2051-2054`). A co-player gets no onset perception, ever, so
  the reaction-gate and `targets` guarantees never run for them.
- `agents/runtime.establishment_plan` is a fixed five-step list
  (`agents/runtime.py:821-828`) with no `narrator_extra`, and
  `perception_establish` builds `"player"` + cast only (`:1476,1497`) — while
  `agents/narration.py:1119` already reads `establish_views["extra:<pid>"]`, a
  key nothing writes. So a co-player attached before the story opens sees
  nothing until turn 1, and nothing warns.

**Severity.** Degradation, not corruption, but total for the affected player.

**Cost.** Small and fully specified: two named files for §1.62, one perceiver
list for X12. It rides item 1's change — the same derivation that fixes
`perception_act`'s cast perceivers is where extras belong.

---

### 8 — §1.13 `ActionStage` is classified, never enforced, and never read on the resolve path

**What a player would notice.** An act that has not landed yet stops being
resolved as though it had — the "approach is not arrival" class, of which
`MovementDecl.arrives` fixed exactly one instance by routing around the field.

**Measured reach.** `llm/schemas.py:289` declares the enum; the only reader
anywhere is `agents/common.py:1410`, inside `director_interpret`. The resolve
path reads it nowhere. And the enum is **not enforced at the seam the pipeline
uses**: `DirectorInterpret.sequence` is `list[dict]` (`llm/schemas.py:1126`), so
`ActionElement(stage="initiation")` raises while
`validate_llm_output("director_interpret", …)` returns the element with
`stage: "initiation"` intact and zero errors — re-confirmed against `.venv`
today. The corpus holds 250 `sustained` beats (128 of which move somebody), 8
`preparation`, and 9 `initiation` that are not enum members at all.

**Severity.** Medium-high but diffuse: any guard keyed on the declared values
silently misses the invented ones.

**Cost.** Two separable pieces. Typing the sequence so the closed set is
actually closed is small. Giving `preparation` a consequence is a Director rule.
`sustained` is explicitly the least safe to act on — an ongoing act is not an
unfinished one, and the schema does not carry the difference.

---

### 9 — §5.2 P4 `established_facts` continuity ledger

**What a player would notice.** Second-act amnesia stops: a character no longer
contradicts a fact the whole room watched being established nine turns ago.

**Measured reach.** **Unmeasured**, and honestly so — there is no stored signal
for "a character contradicted an established fact", which is precisely the gap
the ledger would create. Confirmed absent in source: **zero** occurrences of
`established_facts` in any `.py` (only `CHANGELOG.md`, `UNBUILT.md`,
`docs/archive/`). The adjacent path is not this one — `world_facts` feeds lore,
not character payloads.

**Ranked on symptom, not on rate.** It is on this list because it is the only
entry that names the failure a long story actually produces, and because the
neighbouring ledgers (`obligations`) prove the shape works.

**Cost.** Medium: a new optional list op on `director_resolve`, a commit domain
mirroring `commit_obligations` with dedup and a cap, injection into every
co-present character payload, and a prompt rule. No schema change (world-KV). A
prompt clause is load-bearing, so it is **unproven until observed in conduct**.

---

### 10 — §3.3 F4 residual: an act is delivered whole or not at all, where a line is delivered as a fragment

**What a player would notice.** Half-seen things start reading as half-seen.
Speech already degrades gracefully — a distant line arrives as a fragment; an
action in the same conditions arrives as a complete, confident sentence or
vanishes.

**Measured reach.** Verified in source: `agents/loops.py:216-247` grades speech
`full` / `trace` / `muffled`; `:248-265` runs `_delivery_ok(..., "action", ...)`
as a boolean and then emits a whole `_observable_predicate` sentence. The
sense-profile half already landed, so the input exists. **Per-beat rate is
unmeasured** — micro-loop deliveries are merged into the outcome view before
persistence, so there is no stored artifact to count.

**Severity.** Steady, low-grade wrongness on every beat with distance, dim light
or a barrier in it — the conditions this engine is built to make interesting.

**Cost.** Small-to-medium, and it shares its answer with §1.39: `agents/loops.py`
should emit **percepts** rather than pre-rendered strings, at which point
grading, the identity floor and the epithet floor all apply for free. That is the
residual `design_notes/13-composer-build.md` already names.

---

## 2. The best three to do FIRST

Ordered by felt quality **per unit of work**, not by rank.

### First — §1.11a's cheap half: derive `perception_act`'s perceivers from the scene, not from `flow.reactors`

The register argues this item is expensive because widening `reactors` means
more character-step LLM calls in crowded scenes. **That argument does not apply
to the half that produces the felt failure.** Perception makes no model call —
there is no `perception` role in `providers.ROLES`, the module imports no model
seam, and `tests/test_perception_has_no_model.py` pins that. So the onset
audience can be widened to everyone the scene says is present for **zero
additional spend**, while `interaction_loop` keeps reading `flow.reactors` and
the turn's cost is byte-for-byte unchanged. It closes the 38.2% / 13.9%
"perceived the onset never" number without touching a schema, a prompt or the
pacing question the Director legitimately owns. Highest measured reach in this
document, at the lowest cost of the three.

### Second — §1.37: pass `goal_impacts` to `resolve_stress`

One argument, one call site (`persist/commit_memory.py:1046-1051`), and the
whole aversive half of the psychology model switches on for every character in
every story. It is already 55% of the weight in a function that has been running
against an empty list since it was written, and the producer already returns the
data under a different name. Take it as an explicit parameter rather than a dict
key, so no future caller shape can silently omit it again. Ship it as a
behavioural change with `overloaded` as the watched row, not as a silent fix.

### Third — §2.14 + §1.18: wire the two detectors that are already written

`attire.guessed_spans` and `attire.span_is_a_guess` are built, tested, and
called by nothing; wiring them at the commit seam surfaces **114 live garment
records across 69 bodies** whose coverage nothing actually knew. `room_exposure`
needs the same shape in reverse: seed the guess once at commit and store it, so
413 of 475 rooms stop being re-guessed from their name on every read and become
editable. Both are "call a function that exists", both remove a class of visible
wrongness, and neither touches a model, a prompt or a schema.

**Why not §1.10/§3.9 (ranked 2nd) first:** it is the highest-severity item here,
but the naive fix was already tried and reverted as durable corruption. It
deserves its own pass with a designed ageing rule, not a quick win.

---

## 3. Overrated — reads urgent, measures rare

| Entry | The number that demotes it |
|---|---|
| **§1.33** "An interpret that says nothing costs two model calls" — 42 of 50 interprets degenerate | The `waits` element appears in **0 of 4,605** live sequence elements and **0 of 1,724** turns carrying an action element. Config-specific to one authored playthrough. The genuine half is small: `recon["repaired"] = True` fires on `if new_elems:` alone (`agents/director.py:1014,1024,1033`), so 125 of 1,937 reconciliations report success and 14 of those still leave `unresolved` non-empty — a metric bug, not a lost beat. |
| **§3.5 P6** "the widest lore-to-mind channel… one mis-filed secret is instantly in every character's `world_knowledge`" | `SELECT count(*) FROM lore_entries WHERE category='knowledge'` → **24 of 2,637**. Of those, 3 are `range='global'` and 10 are NULL (treated as global at `mind/memory.py:4629`), so the true exposure is **13 rows**. The door is real and almost nothing is behind it. |
| **§1.6** "See-through barriers mint walkable edges" | `window` and `bars` appear on **0 of 653** live scene edges (barriers: `open` 267, `open_door` 139, `closed_door` 123, `wall` 110, `one_way_window` 8, `membrane` 6). The only live non-wall unwalkable barrier is `one_way_window`, 8 edges, and `membrane` is genuinely passable. The mechanism is confirmed (`persist/commit_place_graph.py:129,136` excludes only `wall`) and the population is eight edges. |
| **§1.43 / §1.44** graded recognition and the attire-description disguise leak | `SELECT count(*) FROM world_conditions WHERE kind='physical_disguise'` → **16 rows across 5 chats (70–74)**, and **0** carry `conceals_identity`. §1.44's own text says it has not fired; the population it could fire on is sixteen rows. Item 3 (witnessing grants `known_to`) stays worth doing because it is purely deterministic — just not urgent. |
| **§1.17 / §1.19** presence identity fragmentation and "the unfamiliar person" | The article split survives in **1 of 34** chats holding presences (chat 57's `A Dalek` / `Dalek` / `The Dalek`); `_fold_duplicate_presences` healed the rest. `unfamiliar person` appears in **9 of 2,352** stored narrator variants. |
| **§1.58 RUNTIME-11** "a character knocked unconscious in one era is unconscious in every era" | `SELECT count(*) FROM frames` → **4, across 71 chats**. Multi-era play is effectively nonexistent, so every frame-scoping row in §1.58 is a correctness debt with almost no live exposure. Keep them; do not schedule them ahead of anything above. |

---

## 4. Prune list — what `UNBUILT.md` should stop carrying

**Headline.** The file holds **127 `###` entries in 5,071 lines**. Proposed:

| disposition | entries | ~lines |
|---|---|---|
| **DELETE — already built** | 5 (+10 sub-items) | 204 |
| **DELETE — overtaken** | 5 | 348 |
| **DELETE — record duplicated in `CHANGELOG.md`** | 6 | 199 |
| **DELETE — not actually a defect** | 2 (+2 sub-items) | 110 |
| **DELETE — unmeasurable / unreachable** | 1 (+4 sub-items) | 21 |
| **MERGE into a survivor** | 7 | 46 |
| **DEMOTE out of the register** | 25 entries + 2 whole sections | 913 |
| **COLLAPSE** (long entries trimmed to their open half, not deleted) | 10 | ~560 |
| **KEEP** | ~76 | — |

**Total: 46 entries leave the register outright, ~2,400 of 5,071 lines removed —
roughly 47% of the file.**

### 4.1 DELETE — already built

| entry | evidence |
|---|---|
| **§1.16** greeting knowledge seeds | Cap at the write: `story/greetings.py:218-227`, applied `:328`, pinned `tests/test_greetings.py:242-320`. Items 2/3/4 are verbatim prompt rules in `language_packs/en/cards/system_prompts.json`; item 5 fixed at `:100-117`. The "also unbuilt, and cheap" tail is overtaken — the nine world fields were deliberately deleted from the extraction schema (`llm/schemas.py:3173-3199`, "no world field returns here") and the world assigned to `director_establish`. |
| **§1.21** origin-era retrieval | `earlier_in_my_life` (`mind/memory.py:3048`), `_origin_on_drift` / `where_i_came_from` (`:2809-2903`), `backfill_memory_summary_windows` (`:3337`), checkpoint propagation (`persist/checkpoints.py:1203-1248`); `tests/test_summary_window_recall.py`, `tests/test_summary_backfill.py`. Already at `CHANGELOG.md:3420`. Residual is a maze-arm question, not a defect. |
| **§1.36** conftest DB redirect | `tests/conftest.py:43 _redirect_default_database`, called at import (`:70`). Heading already says CLOSED; the lesson is in `docs/guides/TESTING.md` and `CLAUDE.md`. |
| **§1.42** ambience cluster over the story column | `static/styles.css:682-684` (volume hidden ≤1180, cluster un-floated ≤1040) plus `browser_tests/test_ui_smoke.py:405` asserting `controls.x >= column.x + column.width`. Its own comment: *"The overlap this guards is real and was live until 2026-08-19."* |
| **§1.54** "Scent is a permission system with nothing to permit" | Landed after the entry was written: `agents/composer.py:941` mints `Percept(kind="scent", channel="smell", …)`; `llm/schemas.py:1221 scent: Optional[str]`; `embodiment.scent` on cards. Commits `5b2e62c`, `3dc351c` (2026-08-18). |

**Sub-items inside surviving entries that are already built and should be struck:**
`§3.1 E1` (`knows_identity` is write-only — set at six sites in
`agents/perception.py`, read nowhere; the live gate `_recognizes`
(`agents/common.py:2368`) is already title-tolerant, so the inconsistency it
names no longer exists); `§3.2 B4` (`_ensure_environment`,
`agents/common.py:4842`, has no production caller); `§3.2 C3` (`_normalise_views`,
`common.py:4784`, likewise); `§1.52`'s DIRECTOR D11 row
(`tests/test_style_guide.py` contains no `open(` — it reads payloads via
`_payloads_sent`, `:172-200`); `§2.17` item 8 (per-clause `support` with
`support_refs` + `epistemic_origin`, `core/db.py:589-598`, `mind/memory.py:2509,2544`);
`§2.7` step 2's "a per-character RUNG opt-in remains open" (it is
`simulation.offscreen_agent`, `world/offscreen.py:1296-1312`); `§2.2`'s
"**Verified absent: no `relationship_events` table exists**" — **that sentence is
false**: the table is at `core/db.py:663-678` with **341 live rows**, writer
`record_relationship_event` (`mind/memory.py:4703-4728`), reader
`relationship_history` (`:4729`), archive, checkpoint and branch-remap support,
and `tests/test_relationship_events.py`; `§6.1`'s interim-on-return bullet
(`world/gaps.py:421 interim_for`, wired at `agents/character.py:3284`);
`§1.28` bullet 1 (`world/spatial_contacts.py:460-468` now refuses a
non-anatomical part slot at the commit seam); `§1.27` bullet c (intent stall
retirement exists: `mind/affect.py:224 _INTENT_STALL_AFTER=2`, `:1158` sets
`status="dormant"`).

### 4.2 DELETE — overtaken

| entry | evidence |
|---|---|
| **§1.11b** reactors stranded by a touch | The mechanism it records was later **reversed**: `initial_parallel_reactors` now defaults to **1** (`story/scene.py:1901`, `agents/loops.py:726`); stranding is fixed at its cause by the `commitment` gate plus `_defer_to_focus` / `_defer_to_unrun_reactor` (`agents/loops.py:284,314`). The record describes a default that no longer runs. |
| **§1.11d** a heard line delivered then scrubbed | The four-pass scrub chain it describes is gone with the model-perception path (`3a82657`, `dbe9ffa`), and the re-injection floor went with it. Its stated residual ("which of the four passes ate the line") is unanswerable because the four passes no longer exist. What stands is `_composer_tripwires` (`agents/perception.py:2539`). |
| **§1.11h** the asker inside the blind wave | Code present (`agents/loops.py:847-874`) but reachable only if somebody raises `initial_parallel_reactors` above its default of 1. Moot until then; the argument is in `CHANGELOG.md:3083`. |
| **§1.23** memory/psychology/capacity (landed record, 220 lines) | Every artifact verified present (`tools/fire_rates.py`, `tools/salience_replay.py`, `tools/remember_lines.py`, `mind/memory.py:1839`, `persist/commit_memory.py:129-149`, `mind/affect.py:169-193,1729`, schema v30). Already at `CHANGELOG.md:2859-2910`. **Keep only sub-item (d)** — promote it as ranked item 4 above. |
| **§1.26** speech-channel smuggling (landed) | `agents/common.py:1838 split_stage_directions`; full record already in `CHANGELOG.md` § alpha 7.0; tests in `tests/test_speech_channel_smuggling.py`. Sole residual is "re-run `tools/fire_rates.py`" — a task, not a defect. |

Also overtaken inside surviving entries: `§1.24`'s "one being, two names —
landed" bullet (`world/spatial_identity.py:338,127`; `CHANGELOG.md:3007`);
`§1.18`'s "196 hand-maintained word tables (30 in `world/spatial.py`)" line —
`world/spatial.py` is now a facade with **0** constants; `§8`'s
`chat_complete_async` recommendation ("delete the import") — `web/app.py` no
longer imports it, so the correct text is "delete the function"
(`llm/providers.py:2448,2499,2539`); `§3.6`'s A7 and E3 (both describe fields
and paths with no reader).

### 4.3 DELETE — record duplicated in `CHANGELOG.md`

`§1.11c` (lore names people — `observer_name_scrub`, `agents/common.py:2460`;
`CHANGELOG.md`), `§1.11e` (two speakers welded — `common.py:6285-6315`;
`CHANGELOG.md:3272`), `§1.11f` (a nod ended the beat — gated at
`common.py:1420`; and its "unverified in play" caveat is now **answered**:
`stop_reason == "physical resolution required"` fell from **1150/1626 (71%)**
before 2026-08-01 to **227/588 (39%)** after, mean rounds 1.03→1.16, max still
4, zero budget-exhausted after), `§1.11g` (`agents/character.py:327-487,560`;
`CHANGELOG.md:3152`).

`§1.11i` and `§1.11j` are the two exceptions: **they are not in `CHANGELOG.md`
at all** (there is no 6.9.2 section), so the register is currently the only
written trace of both fixes. Move them to `CHANGELOG.md`, then delete. §1.11j's
"0.6 is the next stop if the reviews read as churn" is the only live content in
either.

Deleting §1.11b/f/h needs one touch to `docs/guides/PIPELINE.md:340,361,373`,
which cites them by number — the behaviour is already described there, so it is
the citation that goes, not the prose.

### 4.4 DELETE — not actually a defect

- **§1.63** six dropdowns show stored enum values. The entry's own conclusion is
  "**Refuted** rather than repaired" — the extractor is behaving correctly and
  the protocol rule forbids translating the values. What is left is a UI-labels
  wish; it belongs in a frontend issue, not a defect register.
- **§1.51b** a retired setting's row outlives its feature. The entry says it
  outright: *"this is tidiness, not a defect."* Four readerless keys, nothing
  sensitive at rest, and the repair writes to live stories. Move the CLASS
  observation (the engine cannot check a settings key from the tree) to
  `docs/guides/DATABASE.md` and delete.
- **§1.23(c)** `character:<id>` parallel steps fire on 3 of 1,633 turns. Source
  answers the question the bullet asks: that branch is the `autonomy == 0`,
  uncontested path (`agents/runtime.py:706-728`) and autonomy defaults to 50.
  Rare because nobody sets autonomy to 0 — not vestigial. (Live DB agrees: 3
  `character:<id>` steps.)
- **§6.5**'s second and third bullets ("do not remove the three-valued frontier
  semantics", "live sight correctly outranks the remembered gradient") are
  *anti*-entries — instructions not to change working code. They belong in a
  code comment, and largely already are.

### 4.5 DELETE — unmeasurable and unreachable

- **§1.70** a garment condition may still describe a body. The contradiction
  half landed (`persist/commit_attire.py:637-664`); the entry then states there
  is no handle at all — *"nothing here reads the sentence… that is the whole of
  it"* — and offers no measurement. Nothing actionable is left. It cannot be
  verified either way.
- **§1.23(b)** mood congruence 75/25. The limit is already written at the code
  site (`mind/memory.py:1728-1758`), and the corpus still cannot answer it:
  **2,145 rows carry both values, 4 disagree in sign, 0 rows fall below −0.05**.
  Revisit only if a story goes dark; that is a note, not a row.
- **§3.4 X11** extra-player concealed speech. Could not be verified against
  source; `perception_act` handles no extras at all, which changes the shape of
  the claim. Rewrite it against X12 or drop it.
- **§3.2 A8 residual**: the channel is closed (`_p_disguise` is discarded at the
  `_composer_act` call, `agents/perception.py:1576`); what remains is a tripwire
  whose own docstring says *"A WARNING, never a scrubber."* Deliberate, not open.

### 4.6 MERGE

| survivor | absorbs | why |
|---|---|---|
| **§1.10** entity `state` staleness | **§1.24**'s "byte-identical while the prose names it" bullet; **§3.9**'s "entity `state` still has no ageing of any kind" bullet | One finding, one warn-and-commit site (`persist/commit_entities.py:310-335`), one blob. Written three times in three sections. This is ranked item 2 above and the split is why it reads as three small things. |
| **§1.20** unwarranted room change | **§1.14** resolve-asserted position has no authority check | `docs/archive/PROPOSAL_2026-08-06.md:651` already says these are one defect written twice, and two-thirds of §1.14's headline is now paid by `_unreachable_position_writes` (`agents/director_movement.py:554`). What survives is §1.20's claim, one body narrower. |
| **§2.14** clothing regions | **§1.18**'s attire half | §1.18's proposed signal is `attire.span_is_a_guess`, which is §2.14's own unwired detector. Keep §1.18 for the **exposure** half only. |
| **§1.28** contact-sensation residuals | **§1.27**'s `manner`/`contained` bullet | Verbatim the same item. |
| **§3.1 C2** short/common-word names | **§3.1 E2** `_unknown_actor_label` strips only name and alias tokens | Both are "the identity floor is token-based". One item. |
| **§1.23(d)** does the project tier fire | **§1.56** the occasion arrives and is declined | Same zero, same three unmeasured candidates. §1.56's diagnosis is the better text; keep it and delete §1.23's row when §1.23 goes. |
| **§7**'s "Why 3 of 31 characters have ever formed a PROJECT" | into the same survivor | Third statement of one number. |

**Explicitly do NOT merge §1.65 and §1.67.** They look like one family — a being
carrying several legitimate spellings — and they have different causes and
opposite fixes. §1.65 is that the fold is **never applied** to `world_conditions`
(a DB table; `normalize_scene_subjects` walks only `_SUBJECT_KEYED` inside the
scene blob, `world/spatial_identity.py:338-370`). §1.67 is that where the fold
**is** applied it picks the wrong authority — the entity's `name` over the cast
sheet's `identity.name` (`world/spatial_identity.py:261-272`) — with its alias
branch dead whenever `eid == name` (`:313` vs `:320`). Routing §1.65's subjects
through `canonical_subject` today would inherit §1.67's wrong canonical.

*(For the record, §1.65's live reach: 38 `world_conditions` rows carry a raw hex
uid as subject, 33 active, across 10 chats — but only **5 of 21** active
awareness-family rows, in 3 chats. Real, narrow.)*

### 4.7 DEMOTE — real, but not a defect register's business

**Move to `docs/experiments/`** (measurements, negative results, benchmarking):
§1.25 (prompt cache prefix — its own close condition is "run
`tools/cache_latency.py`"), §1.40 (slow turn; everything actionable landed, the
residual is "look it up next time"), §1.47 (`contract_bench` payloads — a tool
caveat), §1.12's last two bullets (observation-text duplication and the gist
ladder — both recorded negative results with retry protocols), **the whole of
§7** (86 lines; the section's own words are *"an unrun experiment is unfinished
work, not a broken thing"* — which is the argument for a separate home, not for
this one).

**Move to `CHANGELOG.md`**: §1.49 (chats 69–80 have no self-memories — minting
repaired at `persist/commit_memory.py:711-722`, pinned by
`tests/test_own_conduct_memory.py`; what is left is a permanent corpus caveat
for anyone reading those chats' memory counts).

**Move to a guide**: §3.6 "Deliberately kept" (a keep-list by construction —
belongs in `AGENTS.md` § Information boundaries); §3.4 X9 (the entry says it
itself: *"Not a code bug — the host is the trust root"*); §2.4 (`$note` key —
a documentation convention plus a `project_check` rule →
`docs/guides/LANGUAGE_PACKS.md`); §1.51b's class observation →
`docs/guides/DATABASE.md`; §1.64 and §1.66 (test-instrument hygiene and a CSS
clamp — both real, neither felt in the fiction).

**Move to their design notes**: §3.9's remaining three bullets, §4.7 (matter has
no volume — its own last line is *"blocked on that answer rather than on
difficulty"*), §4.8, §6.4, §6.5, §6.6, §6.7, §6.10, §6.11, §6.12, §6.13 (paradox
— re-measured: the `world` table holds exactly two paradox-keyed rows, chat 10's
empty `paradoxes` and chat 20's default `paradox_policy`, and no wound markers
anywhere; the section's own conclusion is "none of the above is urgent").

**Downgrade to a watch item / one-line question**: §1.5 (names a field with no
reader — `_confirm` overwrites `rec["bearing"]` on every re-standing,
`persist/commit_place_graph.py:113`; the store that actually held the stale
heading is learned associations, `mind/psychology_runtime.py:504`), §1.7 (every
named repair exists; the mixed-sentence residual is now pinned as intended at
`tests/test_schema_leniency.py:804`, and the character step does have a bounded
schema-repair path — `agents/character.py:3427` → `agents/common.py:1688` →
`llm/llm_quality.py:498`), §1.11 (tagging, persistence and drawer rendering all
shipped — `core/pipeline_context.py:47`, `agents/runtime.py:354`,
`static/js/chat.js:1592`; the residual is "no aggregate reader", a roadmap
wish), §1.69 (verified **three** splitters, not four —
`agents/common.py:5364`, `dressing/backdrops.py:315`,
`tools/perception_retrieval.py:59` — and the entry's own body says none of them
decides what a mind receives), §5.5 (the entry opens *"Low severity,
cosmetic"*), §5.2 (a proposed new ledger, i.e. roadmap — though it earns its
place; see ranked item 9).

**§8's five feature ideas** (minimap, salience-driven personal lore,
per-character retrieval depth, belief-revision salience) belong in an ideas
file. The sixth — *"Perception prose bound by the audibility layer"* — is the
odd one out: it cites live data showing prose contradicting the deterministic
verdict, which is a defect. **Promote that one bullet into §3.3 beside F4.**

### 4.8 COLLAPSE — keep the entry, cut it to its open half

These are the file's longest entries and most of their length is history:

| entry | now | keep |
|---|---|---|
| **§6.2** Extensions | 264 lines | ~60. Roughly three-quarters is a changelog of five shipped batches → `CHANGELOG.md` / `Design.md`. Only the "Still missing:" list is register material. |
| **§2.8** Richer off-screen life | 99 lines | ~10. Exactly **one** bullet is open and it verifies: the mixed `offscreen_log` shapes are coerced on the write path (`persist/commit_mapping.py:21,384`) and never migrated. Everything else named as landed is present. |
| **§2.17** Memory reliability | 126 lines | ~50. The benchmark narrative → `docs/experiments/`; keep the numbered priority list, minus item 8 (built). |
| **§1.52** monolith-split audit | 112 lines | ~20. All sixteen SPATIAL and DIRECTOR rows and every COMMIT row but one have landed; DIRECTOR D11 has landed too. What remains open is **COMMIT-10 alone** (`persist/commit_mapping.py:185 specifics = []`, never mutated, sent as `proposed_specifics` at `:217`), plus the "honest ceiling" paragraph. |
| **§1.48** Language packs | 104 lines | ~60. Real, but the RTL and catalog-scanner bullets are guide material. |
| **§2.15** Movement is an arrival | 60 lines | ~15. Needs (1) and (3) are DONE and verified (`agents/director_movement.py:669,728,779,739`); only need (2), mid-crossing perception, is open. The "original statement, kept because…" block is history. |
| **§2.7** Reactivation negotiation | 45 lines | ~12. Steps 1/3/4/5 verified landed; steps 6–7 verified absent (**zero** hits for `reactivation`, `negotiat`, `refusal_budget` outside tests). |
| **§1.18** the fallback | 61 lines | ~25, exposure half only (attire half merges into §2.14, table census is stale). |
| **§1.1a** conduct authority | 69 lines | ~50. Bullet 5 (unmeasured locomotion false positives) → §1.12; bullet 2 is self-obsoleting — `_scrub_undeclared_player_speech` (`agents/common.py:5344`) has no production caller. |
| **§1.16→§1.23 block** | — | Deleting §1.16, §1.21, §1.23 and the nine §1.11x records reclaims ~700 lines from §1 alone. |

### 4.9 KEEP — with a reason

The ~76 survivors, and the reason each still earns its place, in one line each:
§1.1a (four verified live guard edges), §1.2 (no doorway validation exists at
all — `world/spatial_merge.py:128` upserts any asserted edge), §1.3 (dead sleep
branch confirmed; `exerting=` is dead by the identical route, add it), §1.6
(mechanism confirmed, population eight edges — keep, rank low), §1.8 (promotion
seeds still unfiltered, `story/importers.py:628-660`), §1.10 (ranked 2), §1.11a
(ranked 1), §1.12's four live watch bullets — noting **two conditions have
fired**: the payload budget grew to eleven keys (`agents/character.py:1016-1020`)
and the place graph now has three module-level readers
(`agents/character.py`, `world/place_purpose.py:304,377`,
`persist/commit_memory.py:1113`), so that bullet is a decision that is due, not
a watch item — §1.13 (ranked 8), §1.17, §1.19, §1.20 (ranked 5), §1.22 (nothing
shipped; `search_memory_summaries` is still plain cosine on the unstripped view,
`mind/memory.py:2399,2964,3040`, so the 24/30 origin-hub result is live, and
`CHANGELOG.md:3443` still recommends the fix this entry measured as worse),
§1.24's scale and world-pressure bullets, §1.28, §1.29, §1.30, §1.31, §1.32,
§1.33 (metric half only), §1.35, §1.37 (ranked 3), §1.38, §1.39, §1.41, §1.43,
§1.44, §1.45, §1.46, §1.50, §1.51, §1.53–§1.62, §1.65, §1.67, §1.68, §2.2
(minus the false sentence), §2.3, §2.5, §2.6, §2.9–§2.14, §2.16 (with a
correction: the turn range is **not** missing — `memory_summaries.start_turn_idx`
/ `end_turn_idx` exist at `core/db.py:584-585`; what is missing is the retrieval
shape and the prompt contract), §2.18, §2.19, §3.1 C1–D1, §3.2 X3/X7 (halved —
the player-input half is closed at `persist/commit_background.py:1163-1165`; the
`resolved_event` half survives at `:1228`), §3.3 F4/F6/F7, §3.4 S3-A6/B2/B4/X12,
§3.5 P6 (widen to 13 rows)/P7/X24, §3.7, §3.8, §4.2–§4.6, §5.1, §5.3, §5.4
(narrow it — the co-present set **is** now built from `world.scene` membership,
`agents/perception.py:1594-1610` + `agents/composer.py:552-590`; what is unbuilt
is the commit-path invariant on door state and led positions), §6.1, §6.3, §6.8,
§6.9, and §8's four dead-code rows.

### 4.10 Corrections to make while editing

- **§2.2**: delete "Verified absent: no `relationship_events` table exists" — the
  table shipped with archive, checkpoint and branch support, and holds 341 rows.
- **§1.37**: the return value *does* carry the list, under the name `impacts`.
  The behavioural claim is unchanged; the fix is smaller than stated.
- **§1.45**: line numbers have drifted ~100; the finding holds.
- **§1.58**: `engine_notices` writers also include
  `persist/commit_scene_state.py:650,659`, and the director sites are
  `agents/director.py:541,2614` (not 532/2550).
- **§2.18**: `INTERPRET_DELEGATION_NOTE` does not exist; the live name is the
  function `interpret_delegation_note` (`llm/prompts.py:202`, called
  `agents/director.py:572`).
- **§1.69**: title says four splitters; there are three.
- **§1.64**: the census is not reproducible — 125 `inspect.getsource` calls
  (claimed 128) and a broad grep yields 69 negative-substring asserts (claimed
  34 + 19). Magnitude corroborated, exact counts are not.
- **§3.4**'s preamble "all multiplayer-only, which is why they survived" implies
  unreached. It is not: 135 `narrator_extra` steps across 3 chats.
- **§1.18**: authored ratios moved — `exposure` 62/475 (13.1%, was 2.8%),
  regions 79/207 (38%, was 9.6%). Conclusion unchanged.
- **§1.30**: re-verify before acting — the read side is still ungated
  (`write_canon` writes `category="other"`, `world/background_claims.py:287,389`;
  `knowledge_for_character` filters `category='knowledge'`,
  `mind/memory.py:4615`; `search_lore` has no observer parameter, `:4362`).

### 4.11 A dead helper family that backs three entries

`_normalise_views`, `_ensure_environment`, `_fallback_perception_views`,
`_inject_action`, `_inject_visible_actor` and `_perceptible_entities` in
`agents/common.py` have **no production caller** — only the
`agents/__init__.py:55-61` facade re-export and tests. Any register entry
describing behaviour inside them (§3.2 C3, §3.2 B4, and three of §1.45's rows)
is describing a dead path. `knows_identity` is likewise **write-only**: set at
six sites in `agents/perception.py`, read nowhere, which is what makes §3.1 E1
and §3.6 E3 unreachable. §1.45's own conclusion — "the likely correct change is
deletion" — should be extended to cover the family, in one commit.

### 4.12 Rule 3 is overdue across §1

The register's own rule 3 says an entry untouched through three releases must be
promoted or parked. §1.2, §1.3, §1.5, §1.13, §1.17, §1.19 and both surviving
§1.24 bullets were found at alpha 6.0–6.9; the tree is at alpha 9.6. They have
each sat through ten-plus releases. Either they move up this list or they move
to §8.

---

## 5. What could not be measured, and why

Five kinds of claim in this document rest on something other than a number, and
the ranking is only as good as those edges.

Anything **model-mediated** is unmeasurable offline by construction: whether a
prompt clause changes conduct (§5.2's no-contradict rule, §1.16's three landed
greeting rules, §1.46's specialist contract) cannot be settled by any query,
which is why `CLAUDE.md` calls prompt fixes unproven until observed in conduct —
so item 9's rank rests on the symptom the owner named, not on a rate. Anything
**not persisted** leaves no artifact: micro-perception deliveries are merged into
the outcome view before storage, so §1.39 and §3.3 F4 (item 10) have confirmed
mechanisms and no countable exposure, and the same is true of every "does this
read better" question — §1.11f's pacing change was answerable only because
`stop_reason` happens to be stored. Anything **gated by `_engine_notes`** is
measurable only over the last ~300 turns, because the channel did not exist
before alpha 6.9; the corpus-wide numbers for items 1, 5 and 6 come from stage
outputs and checkpoints instead and are directly comparable, but items 2's
20.3% and 3's corroborating 21.0% are recent-engine rates by necessity — which
makes them better evidence about today and no evidence about the corpus.
Anything **counterfactual** is out of reach entirely: how many beats would have
gone differently had `threat` been non-zero, or had a present witness perceived
the onset, is not in the data — items 1 and 3 are ranked on the size of the
population affected and the mechanism's weight, not on an observed behavioural
delta. And **§1.20's 12.2%** is the one number here with a soft classifier
inside it: "no warrant" was approximated as "no `movement.to_room` and no
locomotion verb anywhere in the declaration", which deliberately over-credits
warrants (any locomotion word anywhere counts), so 91 is a floor and the true
figure is higher by an unknown margin. Finally, the prune list's **line
arithmetic** is an estimate: entry deletions are exact (2,401 lines), but the
ten COLLAPSE rows are judgement calls about how much of a long entry is history,
so "47%" should be read as 45–55%.
