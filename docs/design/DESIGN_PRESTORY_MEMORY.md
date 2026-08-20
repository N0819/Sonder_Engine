# Design: a past that is mostly absent

**Status:** proposal, **not built**. Nothing in this document exists except
where it says a thing already does — and a surprising amount already does. No
schema change is proposed. The four wiring fixes in §8 are the only part with
a defect attached; everything after them is argument.

Instrument: the live corpus at 2026-08-19 — 9,608 memories, 87 character
banks, 66 chats, 2,328 played turns — read read-only, plus the source at
`bc8a599`. Every count below was re-measured for this document rather than
quoted from `docs/guides/MEMORY.md` §12, whose snapshot is sixteen days and
3,145 rows stale.

Related: [`docs/guides/MEMORY.md`](../guides/MEMORY.md) for the layer this sits
in, [`DESIGN_LONG_TERM_GOALS.md`](DESIGN_LONG_TERM_GOALS.md) for the
authored-versus-earned argument this deliberately does *not* copy wholesale,
[`AUDIT_MEMORY.md`](../experiments/AUDIT_MEMORY.md) §4.5 for the refusal this
document leans on twice.

---

## 1. The problem is not the one it looks like

The reported symptom: *"It feels like my characters are starting off with a
terrible bout of amnesia."* A character three turns into a story, asked about
anything before turn 0, has nothing to retrieve.

The retrieval half of that is exactly true and measured:

| | |
|---|---|
| memories with `turn_idx < 0`, corpus-wide | **0** |
| memories with `turn_idx IS NULL` | **58** — all promotion seeds (§3) |
| lowest `turn_idx` anywhere | **0** |
| character-authored `ponder` queries in the whole corpus | **3**, at turns 45, 45, 58 |

So a `ponder` about a childhood returns empty, and always has.

**But the characters are not blank.** Measured across the 58 rows of
`characters`:

| card field | populated | size |
|---|---|---|
| `knowledge.public_history` | **56 / 58** | median 263 chars, max 713 |
| `knowledge.private_history` | **49 / 58** | median **3** entries, max 7, 143 total |

`private_history` reaches the deciding mind on every beat —
`agents/character.py:3224` calls `story/scene.py:2301`'s
`private_knowledge_for`, which hands back `{about, content, source}` per
entry. `public_history` reaches it at `agents/character.py:2906`, and reaches
the Director as `social_standing` (`agents/director.py:2454`).

So the past exists and is delivered. What it is *not* is a memory. It has:

- **no `when`** — no dating of any kind, relative or otherwise;
- **no `temporal_status`** — every memory row carries `remembered_past`
  (`docs/guides/MEMORY.md` §3); this carries nothing, so it reads as a
  standing fact rather than something lived;
- **no epistemic origin** — the three-scope separation the whole memory layer
  is built around (`_PROVENANCE_SCOPE`, `mind/memory_common.py:106`) does not
  apply to it;
- **no citable id.** `agents/character._ground_observation_citations`
  (`agents/character.py:951`) permits three disjoint namespaces —
  `current:<perceiver>:<n>`, `event:<hash>`, `summary:<scope>:<turn>` — and
  drops everything else. A `private_knowledge` entry is in none of them.
  **A character cannot cite its own past as evidence** for a belief update, a
  mind-model update, an appraisal modulation, or a dispute. It can mention its
  past. It cannot build on it.
- **no forgetting.** It is delivered in full, unranked, every beat, for the
  life of the story.

### The two-sided statement of the defect

The past is simultaneously **unrecallable** and **unforgettable**, and both
are the same missing thing: *the past is not in the retrieval layer.*

That reframe matters, because it changes what a fix has to do. It is not
"give the character content it lacks" — the median card already carries three
private facts and a 263-character public history. It is "put the content it
already has into the layer where coming-to-mind, failing-to-come-to-mind,
being-uncertain, and being-re-read are possible at all."

---

## 2. What the schema can already express

More than expected. `turn_idx IS NULL` is **already a tier**, half-wired,
carrying 58 live rows.

What works today, unmodified:

- **The read seam admits it.** `visible_memory_rows` clauses
  `(turn_idx IS NULL OR turn_idx<?)` (`mind/memory_read.py:89`), with the
  reason stated at `:58` — a row belonging to no turn cannot be this turn's
  leaked outcome, so the audit-F1 cutoff has nothing to withhold.
- **It is already dated in the right words.**
  `mind/memory_context.py:112-116`:

  ```python
  ti = mem.get("turn_idx")
  if ti is None:
      out["when"] = "before this story's recorded turns"
  ```

  That string is already asserted by `tests/test_memory_importance_and_dispute.py:253`.
  The engine already has a vocabulary for a pre-story memory and already
  speaks it to minds.
- **It sorts last** rather than nowhere (`mind/memory_context.py:349-353`,
  `10**12` sentinel; `mind/memory_snapshot.py:182,357`).
- **Two mint sites already use it.** Background promotion
  (`persist/commit_background.py:1618-1627`, `turn_idx: None`, salience 0.6,
  provenance `witnessed`, `event_key: promotion:<chat>:<char>:<n>`) and the
  portable character-bank import (`mind/memory_snapshot.py:389-390`, which
  hard-sets `turn_idx` to `None` **unconditionally, even on a same-chat
  re-import**, with the reason at `:379-383`).

What does **not** work today, and each is a live defect on those 58 rows:

1. **The temporal cue cannot reach it.** `mind/memory_retrieval.py:561`
   gates the `+0.12 * age` old-memory bonus on `if ti is not None and
   max_turn`. `_OLD_CUES` is `"years ago"`, `"back then"`, `"first time"` —
   *the exact query language that names the pre-story past* — and it is the
   one bonus the pre-story rows are structurally excluded from. The query
   that should reach them is the query that cannot.
2. **It never consolidates.** `consolidate_character_memory` passes
   `require_turn_idx=True` (`mind/memory_summaries.py:608`). So a pre-story
   row is never folded into a summary window, never appears in
   `autobiographical_summary`, never appears in `earlier_in_my_life`, and —
   critically — **can never be the `where_i_came_from` origin window**, which
   is the one payload key whose entire purpose is answering "who was I before
   all this" and which fires on exactly the drift signals that make the
   question urgent (`docs/guides/MEMORY.md` §8).
3. **It never archives.** Archiving selects from the consolidation set
   (`mind/memory_summaries.py:641-654`), which excluded it in (2). A pre-story
   row sits at its mint salience for the life of the story with no decay path
   of any kind. This is `docs/UNBUILT.md` §1.16's greeting-seed complaint,
   arriving by a different road.
4. **It silently counts toward two floors it was never calibrated against.**
   `_CONTRAST_MIN_BANK = 20` (`mind/memory_retrieval.py:795`) and
   `_RECALL_CONFIDENCE_MIN_BANK = 40` (`:688`) both count
   `visible_memory_rows`, which includes NULL-turn rows. See §5 for why that
   is not a rounding error.

**The tier exists. It is not finished.** That distinction is the whole reason
this document proposes no new table.

---

## 3. What the engine already does about a past, in four places

Worth listing, because three of the four are precedents and one of them is
the proposal already shipped by accident.

| mechanism | shape | `turn_idx` | provenance | salience | decays? |
|---|---|---|---|---|---|
| card `private_history` | knowledge block, always on | — | — | — | no |
| greeting knowledge seeds (`story/greetings.py:322-331`) | memory rows | **0** | `remembered` | clamped ≤ **0.7** (`:218`) | yes, just under the 0.72 archive floor |
| promotion seeds (`persist/commit_background.py:1618`) | memory rows | **NULL** | `witnessed` | 0.6 | no (§2.3) |
| portable bank import (`mind/memory_snapshot.py:374`) | memory rows | **NULL** | carried verbatim | carried verbatim | no |

The greeting-seed row is the one to copy. Its salience clamp exists for a
reason stated at `story/greetings.py:200-218` and worth restating in full,
because it is the density argument already won once:

> A seed is scaffolding for a story that has not happened yet… Above 0.72
> nothing is ever archived, and `contrast_memory` scores `salience + 0.4 *
> (age / current_turn)` — so those seeds not only outranked lived experience
> permanently, their chance of intruding UNBIDDEN grew with the length of the
> story.

105 pre-clamp rows at salience ≥ 0.99 are still live, 104 of them at
`turn_idx <= 1`, and `mind/memory_write.repair_seed_salience` exists to bring
them down. **That is this exact defect, already found once, in the one place
an authored past already reaches a bank.**

---

## 4. Why a generated past is a worse failure than no past, in arithmetic

This is not a stylistic worry. It is three measurements about how the current
engine behaves on a bank that is majority-authored.

**Bank size, measured over the 86 in-play banks:**

| at turn | banks alive | median rows |
|---:|---:|---:|
| 0 | 86 | 1 |
| 1 | 83 | 5 |
| 3 | 82 | **11.5** |
| 5 | 81 | 19 |
| 10 | 76 | 32 |
| 20 | 65 | 43 |

Median growth is **3.15 rows per turn per character** (n = 72 banks with a
span of ≥ 10 turns). The 40th row lands at a median turn of **10** — and 24
of 86 banks never reach 40 rows at all, because the median chat is **23.5
turns** long and 30 of 64 chats never exceed 20 turns.

### (a) For the opening turns, `recalled_old_memories` would be *entirely* the authored past

`recent_memory_buffer` takes the last 4 turns and passes
`require_turn_idx=True` (`mind/memory_retrieval.py:937-965`), so it holds
essentially the whole in-play bank at turn 3 — and `recalled` then excludes
every id already in `recent` (`mind/memory_context.py:352`). A pre-story row
is not eligible for the recent buffer. So the recalled lane, budget
`_RECALL_LIMIT = 16`, is competing over a pool from which every lived row has
already been removed.

Seed twenty pre-story rows and, for roughly the first ten turns, **the
character's entire "recall" is its authored childhood, in full, on every
beat.** Not "at high salience" — *all of it*, because sixteen slots is more
than twenty rows minus the ones the beat happens to rank first. That is the
"every childhood memory load-bearing and retrievable at full salience"
failure, and it is arithmetic rather than prediction.

### (b) `contrast_memory` will preferentially surface exactly the authored rows

Unbidden recall scores (`docs/guides/MEMORY.md` §6):

```
score = salience + 0.5*|valence| + 0.3*arousal + 0.4*(age/current)
      - 0.8*jaccard(query, gist) - 0.7*cosine(query, embedding)
      - 0.3 (same location) - 0.4*(entity share)
```

A memory from another decade and another place has near-zero jaccard,
near-zero cosine, no shared location and no shared entities — **it is
maximally penalty-free by construction**. Seed at 0.6 and it clears
`_CONTRAST_MIN_SALIENCE = 0.5` (`:803`). Seed twenty and the bank clears
`_CONTRAST_MIN_BANK = 20` (`:795`) **at turn 0, on authored rows alone**, so
unbidden recall switches on before the character has lived anything.

The only term the authored rows *lose* is `0.4 * (age/current)`, and they lose
it by the accident in §2.1 rather than by design. Fix that accident naively
and the pre-story tier becomes the strictly dominant contrast candidate.

The trigger is stuckness — `refrain`, `verbatim_repeat`, `goal_held`,
`plateau` — which is common early, before a story has given a character
anything to do. **A character seeded with a thick childhood would be haunted
by it, on exactly the beats where the story has not yet started.**

### (c) The abstention signal cannot see the condition it is being credited with detecting

`recall_confidence` (`mind/memory_retrieval.py:712`) returns
`available: False` — explicitly "no signal, never emptiness" — below 40
visible rows (`:738`). The median bank crosses 40 at turn 10.

**So `nothing_comes_back_clearly` is structurally unable to fire during the
window where the amnesia symptom lives,** and never fires at all in 24 of 86
banks. The premise that the engine can now *detect* the empty-past condition
is false in precisely the place it was wanted. It is a mature-bank instrument.

And the converse is worse: seed 40+ authored rows and the floor starts
computing a lift distribution over authored prose and reporting conviction
about it. It would be measuring the author, not the life.

### The conclusion this forces

Generation is not the problem. **Generation without a forgetting story is.**
Every one of (a), (b) and (c) is a property of *volume* interacting with
floors calibrated on lived banks. A past that is mostly absent is not a
stylistic preference — it is the only shape the existing retrieval layer can
hold without lying.

And the reassuring number: the authors are **already thin**. Median
`private_history` is **3 entries**. The cheapest fix is already inside the
safe band; it is only *generation* that would leave it.

---

## 5. The design space

### Option A — episodic rows at negative `turn_idx`. **Reject.**

`mind/memory_context.py:112-116` computes `age = current_turn_idx - ti` for
any non-NULL `ti`. A memory at `turn_idx = -5`, read at turn 3, is handed to
the mind as **"about 8 beats ago."** It dates a childhood in story beats, and
it dates it as *recent* — the newest pre-story rows would look like the most
recent things that ever happened. `_beats_ago_span` (`:126`) does the same to
any summary window built over them.

Deeper than the arithmetic: `turn_idx` is documented as *global play order
shared by every frame*, and the relative-dating rule at `:128-134` exists
because an absolute index tells a mind where a flash-forward sits in the
story's construction. A pre-story memory has no place in play order at all.
Negative `turn_idx` is a type error dressed as a range extension.

### Option B — a distinct table. **Reject.**

Every mind-facing read goes through one seam whose three invariant arguments
have no defaults, so a caller cannot forget a rule. `docs/guides/MEMORY.md`
§3 records why, and records that the previous design — the same filters
written out at five call sites — was wrong for a reason that applies verbatim
here: *"Repetition is precisely how a sixth path forgets, because nothing
obliges it to reproduce five rules it may not know exist."* A second table is
a sixth path. It also needs its own migration, commit, archive
(`persist/chat_archive.py`), checkpoint snapshot+restore, and branch/clone ID
remapping (`docs/guides/DATABASE.md`) — for zero expressive gain over a
column value that already exists.

### Option C — `turn_idx IS NULL` episodic rows. **Accept as the substrate.**

Everything in §2 that works, works today. Everything that does not is four
bounded fixes (§8) with a live defect already attached to each. No schema
change, no new seam, no migration, and the 58 promotion rows are a free test
population.

### Option D — a summary window with no episodes underneath. **Accept, and make it the majority of the answer.**

This is the "known but not recalled" tier, and the engine already gives it
exactly the right epistemic status without being asked:

- A summary is **barred from reinforcing durable belief** — "compression may
  remind a mind of a claim, but cannot independently reinforce it"
  (`docs/guides/MEMORY.md` §3). That is precisely the correct relationship to
  a past one has an account of and no scenes from.
- `where_i_came_from` already selects the **earliest** first-hand window and
  surfaces it on drift rather than on similarity, "because a character's
  foundational era is frequently dissimilar to whatever is happening now,
  which is exactly when it should still be present." That sentence was written
  about turn 0–10 of a story. It is a better description of a life before the
  story.
- `memory_summaries.support` (schema v25) permits an empty `support_refs`, and
  the doc already says what that means: "the clause generalises, compresses
  several rows, or was invented. This does not try to tell those apart." A
  pre-story window is the honest case of exactly that.

The blocker is small and named in §8.2: `_beats_ago_span` has no vocabulary
for a window with no turn span, and `require_turn_idx=True` means
consolidation will never produce one, so it must be written directly.

### Option E — a lore entry with privileged access. **Reject for autobiography; note it is already right for the public half.**

Lore is *shared-world* knowledge gated by `access_tags` and range
(`mind/memory_lore_entries.py`). A personal past put there becomes reachable
by anyone holding the tag — a firewall inversion, not a firewall use. But
`knowledge.public_history` — 263 median characters of *what the world knows
about this person* — is world knowledge by its own definition and sits in a
character card only for authoring convenience. That it is not a lore entry is
a separate, smaller observation, not proposed here.

---

## 6. Consistency across stories

Memory is keyed `(chat_id, char_id)` — both NOT NULL (`core/db.py:524-525`) —
and every read path filters on both. Measured, the fragmentation is extreme:

| character | chats | banks | total rows | largest |
|---|---:|---:|---:|---:|
| The Doctor (char 35) | **17** | 17 | **4,172** | 657 |
| Jean-Luc Picard (char 32) | 13 | 11 | 611 | 111 |
| Guinan (char 40) | 7 | 7 | 534 | 106 |

Three *different* `characters` rows are also named "The Doctor", so identity
across stories is already fuzzy above the id level.

`LORE_INHERITANCE_MODES` (`mind/memory_common.py:60`) is the obvious analogy,
and reading what the three modes actually *do* is what makes it useful.
`mind/memory_lorebooks.py:220` severs the upward walk for anything not
`inherit`; `:268-273` handles the downward one:

```python
if mode == "isolated":
    continue                                    # never surfaced through the parent
child_weight = weight * (0.5 if mode == "reference_only" else 0.95)
```

and the weight becomes a score multiplier of `0.7 + 0.3*weight`
(`mind/memory_lore_entries.py:308`) — so `reference_only` is a **~15% rank
haircut, not a contents barrier.** (The lorebook UI says otherwise —
`static/js/lorebooks.js:1434` calls it "organizational context without
automatic entry retrieval" — which is a real mismatch worth its own ticket
and is not this document's business.)

So the vocabulary the repo already owns is not three visibility levels. It is
**one exclusion and one down-weight**, and that is a better fit for memory
than three levels would be.

### `isolated` — today's behaviour. Keep it as the default, permanently.

### `inherit` — already built, already shipped, and it has a firewall hole

`GET/POST /api/chats/{cid}/characters/{ch}/memories/export|import`
(`web/app.py:4815-4835`), UI at `static/js/chat.js:2105-2262`. Import sets
`turn_idx = None` (`mind/memory_snapshot.py:390`) and clears `event_key`
(`:400`), carrying `provenance`, `salience`, `importance` and `disputed`
verbatim.

**So the engine already converts one story's lived experience into another
story's pre-story tier, and has for some time.** That is the strongest single
argument that §5 Option C is the right substrate: the only existing
cross-story continuity path already lands there.

It also has three defects, all in the same import:

1. **The other story's player is not scrubbed.** `content` is carried
   verbatim. Chat 63's persona's name, conduct and private revelations land
   inside a mind in chat 64 — a mind that had no channel to any of it. Every
   other path that writes a player reference into a character's memory goes
   through `player_handle_for` / `_substitute_player_slot`
   (`story/greetings.py:78-115`), whose docstring is explicit that "the
   player" is a word from outside the fiction. The import path bypasses all
   of it.
2. **`archived` is exported (`:369`) and silently dropped on import.** A
   round trip resurrects every retired memory at full retrievability.
3. **`frame_id` falls through to the ambient contextvar**
   (`mind/memory_write.py:340,362`), so an import performed while a chat sits
   in a past frame silently stamps that frame on a whole imported life.

### `reference_only` — the mode worth building, and the one nobody has

**Carry the summary windows, not the episodes.** `dump_memory_summaries` /
`apply_memory_summary_restore` already exist and already carry `support`,
`embedding` and window bounds.

The character arrives in story B knowing they have lived, with an account of
who they were, and no retrievable scenes. Four properties fall out for free:

- **correct density by construction** — one window per era rather than 657
  rows;
- **firewall-softer** — a summary is already barred from reinforcing durable
  belief, so an inherited account can colour appraisal and speech without
  laundering another story's events into knowledge;
- **already the right payload key** — `earlier_in_my_life` and
  `where_i_came_from` read exactly this shape;
- **cheap to scrub** — one prose block per era to check for the other
  story's player, against 657 rows.

It still needs the persona scrub. A summary is prose, and the prose names
people.

---

## 7. The firewall

### Does an authored past violate the invariant?

**No, and the reason has to be stated precisely or it licenses too much.**

The rule (`AGENTS.md` § Information boundaries) is that a mind may not acquire
a fact *that reached it through no channel*. The verb is **reach** — it is a
rule about transfer between things that already exist. It has never
constrained what a mind *is*. A card's traits, values, drive, appearance,
abilities and `private_history` are all held with no in-play channel, and
nobody has ever called that a leak.

**Authorship is the constitutive act, not a transfer.** The author is where
the mind comes from, so there is no gap for a fact to cross.

That gives a clean four-way ruling, and the second and third are the ones
worth writing down:

| act | verdict | why |
|---|---|---|
| a host authors a past on the card | **legitimate** | constitutive; same status as `drive` |
| a tool generates a past from the card, at creation, on host command | **legitimate** | the same act, performed by an instrument the host ran |
| the engine generates a past **from what has happened in this story** | **illegitimate** | the fact was produced *in response to* the mind's own output. There is no channel at either end — the loop is closed inside the engine |
| the engine copies a past from **another story** | **illegitimate as a default; legitimate as an explicit host act, after a persona scrub** | chat A is a different world. `(chat_id, char_id)` is the engine's own statement that these are different minds |

The third row is the one that needs stating because it is the tempting one.
Backfilling "what she must have remembered about her mother" after a
conversation about mothers at turn 40 *feels* like continuity and is a
provenance lie — the memory did not cause the conversation, the conversation
caused the memory.

The fourth row already has a precedent in this repo's own hand.
`docs/guides/MEMORY.md` closes with the chats 69–80 self-memory hole and
refuses to backfill it:

> inventing a memory a mind never formed is a worse falsification than the
> absence, which at least behaves like ordinary forgetting… If a future need
> arises, the honest shape is an **authored-memory import a host chooses per
> character, never an automatic reconstruction.**

That sentence was written about a different problem and is the correct answer
to this one.

### What provenance should a pre-story memory carry?

Candidates, and the answer is none of the obvious ones.

- **`witnessed`** — asserts the character was there and saw it. True for
  much of a past, false for the rest, and it is what the 58 promotion rows
  use today (defensibly: a promoted background presence genuinely was in the
  room).
- **`remembered`** — already FIRSTHAND scope, already the tag for material
  the engine did not derive from a perception view (own conduct, greeting
  seeds, the drive-shift memory).
- **A new `authored` value.** **Reject**, for three reasons:
  1. `_PROVENANCE_SCOPE` must map it to one of the three existing scopes
     anyway, so it adds a value without adding a distinction.
  2. `summary_scope_for` (`mind/memory_common.py:124`) **fails open** —
     an unrecognised provenance silently becomes `autobiographical`. The
     `kind` vocabulary has already been escaped once this way: 253 `episode`
     rows and one `belief` row, and the `belief` row was a belief that could
     never be revised or demoted because two consumers test kind by exact
     string (`AUDIT_MEMORY.md` §1.5). Adding a value to a fail-open enum is
     how that happens again.
  3. The real objection: **`authored` describes how the row got there, not
     what the mind's relationship to it is.** Provenance answers "through
     what channel did this reach me". Authorship is not a channel inside the
     fiction — no character experiences their past as authored. It would put
     a host-facing fact in a mind-facing field.

**The rule, in engine vocabulary: an authored past is authored WITH
provenance, not tagged with one.**

A pre-story entry carries the channel the character had *at the time the
remembered thing happened*. `witnessed` for what they saw. `told` for what
their mother told them. `read` for what they found in a file. `inferred` for
what they worked out at nineteen and have believed since.

This is not bookkeeping. It is the generatively richest option available, and
it costs nothing because the routing already exists:

- "I saw my father drown" → FIRSTHAND → `autobiographical_summary`,
  citable as evidence for a belief.
- "I was told my father drowned" → HEARSAY → `what_i_was_told`, a
  separate row a model cannot melt into experience — and a thing that can
  turn out to be **false**, which is the whole reason the scopes are
  separate.
- "I concluded my father drowned" → SURMISE → `what_i_concluded`, subject
  to `reconcile_inference_confidence`, revisable, and rankable by belief
  weighting.

A character whose past has epistemic texture can be *wrong about their own
childhood*, and can find out. That is the gap being generative, in the one
place the engine has never applied it.

`remembered` is the right default when the author says nothing — it is
already the FIRSTHAND tag for engine-minted non-view material — but a default
is not the design.

### One small existing observation

`memory_ref` is the `event_key`, delivered verbatim to the model. Today that
means a mind can see `greeting_seed:a1b2c3` and `promotion:9:11:0` in its own
payload. It leaks a word, not a fact, and it is already true; a pre-story
prefix would join it. Worth knowing before choosing one.

---

## 8. Recommendation

**A pre-story past is a summary-heavy, episode-light `turn_idx IS NULL` tier,
authored with real per-entry provenance, seeded once at scene creation from
material already on the card, hard-capped, and never written by a model
during play.**

In four parts, cheapest first. Parts 1 and 2 are worth doing even if the rest
is refused.

### 8.1 Finish the tier (no new content, four bounded fixes)

Each has a live defect on the 58 existing rows:

1. `_temporal_mode == "old"` must reach NULL-turn rows
   (`mind/memory_retrieval.py:561`). Today the only query language that names
   the pre-story past cannot reach the only rows that hold it.
2. Decide contrast's treatment of a NULL-turn row deliberately. Today the
   `0.4 * (age/current)` term is silently 0, and §4(b) says the naive fix
   makes the tier dominant. The likely correct answer is a **fixed** age term
   below the maximum a lived memory can earn — a past is old, but it is not
   older than the oldest thing in the story by an unbounded margin.
3. Decide whether a NULL-turn row may archive. Today it structurally cannot
   (§2.3), which is the greeting-seed defect in a new place.
4. Decide whether a NULL-turn row counts toward `_CONTRAST_MIN_BANK` and
   `_RECALL_CONFIDENCE_MIN_BANK`. Today it does, silently, and §4(b)/(c) say
   both are wrong.

### 8.2 Seed the card's own material, once

One function beside `story/greetings._route_mind_memories`, run at the same
place `scene.seed_initial_attire` runs — **once, at scene creation or first
attachment, never overwriting what the story has changed.** Reuse
`_seed_salience`'s 0.7 clamp verbatim.

- Each `private_history` entry mints one row per mind that holds it. An entry
  with `known_by: [Ana, Bo]` mints **three** rows — the owner's and one each
  — same content, and *different provenance per mind*: the owner's is
  `witnessed` or `remembered`, the others' is `told`. That is the firewall
  producing better fiction, not obstructing it: the same event is a memory for
  one person and a confidence for another.
- One `memory_summaries` window per authored era, scope
  `autobiographical`, written directly rather than through consolidation
  (which will not touch turn-less rows), with empty `support_refs` — which
  the schema already permits and already means the honest thing.
- `_beats_ago_span` needs one branch for a window with no turn span. It
  should say what `_with_reading` already says: *"before this story's
  recorded turns."*

What this buys: recall by cue, `ponder` reaching pre-story material,
**citability as evidence** (§1), `record_dispute` on a pre-story fact, and
eligibility for the `where_i_came_from` origin read.

What it costs, stated rather than hidden: it converts 1–7 *always-on* facts
into 1–7 *sometimes-recalled* ones. If an author wrote a `private_history`
entry expecting it to be in front of the character every beat, this is a
loss. The honest resolution is that both surfaces continue to exist and the
card says which — not that memory silently replaces knowledge.

### 8.3 The ratio, with a derivation

A lived summary window covers ~10 turns × 3.15 rows ≈ **30 rows compressed to
one row of prose.** A pre-story era should be the same object: **one summary
window and at most three episodes.** Not because three is a nice number, but
because that is the compression ratio the engine's own consolidator produces,
and because the median author already writes three.

**Cap it in the writer, not in the schema** — `story/greetings.py:213-218`
argues this exactly, having learned it the hard way: a stored extraction
replayed by `start_story` never passes through the schema, so "the write is
the boundary that matters."

### 8.4 `reference_only` inheritance, per character, per target chat

Summary windows only, host-initiated, persona-scrubbed. And fix the three
defects in the existing `inherit` path (§6) whether or not this is built,
because that path is live today.

### What would falsify this

The claim is that **thinness plus recallability** is what reads as a person
with a past, and that thickness reads as a person reciting a dossier.

Falsified if a measured arm shows characters seeded with one era summary and
≤ 3 episodes are indistinguishable, on the counters below, from characters
seeded with twenty episodes — or, worse, if the thin arm still reads
amnesiac, which would mean the deficit was never about retrieval and §1's
reframe is wrong.

Counters, all of which the existing instrumentation already emits:

| counter | prediction |
|---|---|
| share of `recalled_old_memories` that is pre-story, turns 0–20 | thin arm: falls below 50% by turn 5. Thick arm: ~100% through turn 10, per §4(a) |
| `contrast_memory` selections that are pre-story, turns 0–20 | thin arm: rare. Thick arm: dominant, per §4(b) |
| `ponder` queries targeting pre-story, and whether they return anything | currently 0/3 could have; any non-zero return is the first evidence the lane works |
| `memory_effects` with `disposition: integrated` on a pre-story ref | the only counter that measures *influence* rather than retrieval (`docs/guides/MEMORY.md` §13); if this stays 0, the tier is decoration |
| `record_dispute` firing on a pre-story ref | currently structurally impossible. Non-zero means a character revised its own past, which is the capability this whole document is for |

Cost to measure: the harness exists. `tools/memory_probe_harness.py` and the
frozen sets in `tools/memory_probes/` are the same shape; a pre-story probe
set, one seeded scratch chat under `ENGINE_DB`, and a replay. **One probe set
and a replay, not a play-through** — which is the honest reason to insist on
the measurement before shipping any of §8.2 onward.

---

## 9. What should not be built

Six refusals, most-confident first.

1. **LLM backstory generation as an automatic step at character creation.**
   Not because generation is illegitimate — §7 rules it legitimate — but
   because of what §4 measures it will do: N rows of uniform salience, into a
   tier that never consolidates (§2.2) and never archives (§2.3), in a bank
   where the recalled lane holds nothing else for ten turns (§4a), preferred
   by unbidden recall from the first beat (§4b), under an abstention floor
   that will start reporting conviction about authored prose (§4c). Permit it
   only in the §8.3 shape: **one era summary, at most three episodes, through
   the same clamp greeting seeds pass.**

2. **Negative `turn_idx`.** §5 Option A. The reason is one line of arithmetic
   at `mind/memory_context.py:114`.

3. **A separate pre-story table.** §5 Option B. The reason is
   `docs/guides/MEMORY.md` §3's own argument about a sixth read path.

4. **An `authored` provenance value.** §7. Three reasons, of which the
   fail-open `summary_scope_for` default and the `kind='belief'` precedent
   are the mechanical ones and "authorship is not a channel" is the real one.

5. **Automatic memory inheritance across chats.** §6/§7. The engine's own
   `(chat_id, char_id)` key is the statement that these are different minds;
   carrying a bank across is one mind receiving another's memories, dressed
   as continuity. Permitted only as an explicit host act with a persona
   scrub.

6. **Model-minted pre-story memories during play** — the "character remembers
   something about their past for the first time, mid-story, and it becomes
   true from then on" version. This is the interesting one, so it gets a
   section.

### 9.1 Why the projects argument does not carry, and what it becomes instead

`DESIGN_LONG_TERM_GOALS.md` made projects form dynamically for reasons that
are good and specific: the cap gives adoption a price
(`DESIGN_LONG_TERM_GOALS.md:82-89`); the world may only *offer*, adoption is
always the character's own act (`:170-176`); establishment is earned by
service, never by survival (`:241-247`); and giving one up must be a legible
act with a stated reason, "the one revision a character currently cannot
perform."

**None of it carries, because a project is a commitment and a memory is not.**
A commitment you did not make is not yours — that is the entire argument. But
nobody adopts their childhood. There is no scarce slot for a past to compete
for, no price to pay for having had a mother, and no act of arriving at
having been nineteen. `DESIGN_PSYCHOLOGY_AS_PRESSURE.md`'s objection — that
authored text must not override lived conduct — also does not apply, because
a past does not compete with conduct; it is a thing conduct can be *about*.

And the mechanical objection is decisive on its own. Letting a character mint
its own pre-story rows mid-play is `AUDIT_MEMORY.md` §4.5's MemGPT-style
self-edited memory, refused there because it "hands a model write authority
the deterministic commit boundary exists to withhold." Everything else in
this engine is provisional until `persist/commit.py` validates it. A memory
the model invented about itself has nothing to validate against — there is no
objective record of a childhood to check it with, which is exactly what makes
it different from every other model claim the commit boundary adjudicates.

**But the brief's intuition is right, and the engine has a better home for
it.** Human autobiographical memory *is* reconstructive; the reconstruction
does become the memory. The engine already models exactly that, and it is
called `record_dispute`: the character re-reads a memory without rewriting
it, current evidence required, both readings kept, delivered back as
`i_now_read_this_differently`. `docs/guides/MEMORY.md` §13 explains why the
two are kept separate — "collapsing the two would either erase the experience
or hide the correction."

Disputes have fired **zero times in production**, and
`tests/test_dispute_reachability.py` established that the wire is intact and
the occasion has simply never arisen: "a doctor and a fox spirit having
dinner give a mind nothing to re-read."

So the projects precedent inverts into a much better claim:

> **Seed the past thinly so it can be re-read, rather than letting it accrete
> so it can be invented.**

A thin authored past plus the dispute mechanism already built gives you "the
character's understanding of their own past changes during play," with no new
write authority for any model, and with both versions preserved. That is the
same shape as the projects argument — the *meaning* is earned in play —
applied to the layer where it actually fits: interpretation, not existence.

It also predicts something checkable. A pre-story tier should be where
`record_dispute` finally fires, because an authored past is the one thing in a
character's bank that a story is *likely* to contradict.

---

## 10. Not yet decided

- **Whether the seeded rows should be `episodic` or a distinct `kind`.**
  Current position: `episodic`, because `MEMORY_KINDS` is another exact-string
  enum with a demonstrated escape (§7), and `turn_idx IS NULL` already carries
  the distinction. Revisit only if a consumer needs to select the tier in SQL
  and cannot express it as `turn_idx IS NULL`.
- **Whether `private_history` should remain in the payload after being
  seeded.** Both surfaces existing is the safe default and the card should say
  which; but two representations of one fact is how `wearing` and `regions`
  drifted apart. Not decided here.
- **Whether the pre-story window should be one era or several.** One is
  simpler and matches `where_i_came_from`'s single-origin read. Several would
  let `earlier_in_my_life` rank between them, which is a real capability —
  and a real invitation to write six of them.
- **Whether an inherited `reference_only` window should be marked as coming
  from another story at all.** It carries no `chat_id` a mind can see, and the
  `when` string is already correct for it. Marking it may be host-facing
  honesty or may be a fact with no channel. Undecided, and it is the last
  question that has to be answered before §8.4 is written.

---

## Addendum, 2026-08-20: what was measured after this note was written

Five results from the retrieval work bear directly on the design above. Two
strengthen it, one weakens an argument it makes, one changes its arithmetic,
and one hands it a falsifier it did not have.

### (1) The attention budget is now a number, and it makes §4(a) WORSE

`_RECALL_LIMIT` moved 16 -> 24 on measurement
([`../experiments/RETRIEVAL_COST.md`](../experiments/RETRIEVAL_COST.md) §6:
conduct peaks at 24 and declines at 48 and 96). Every payload arithmetic in
§4(a) above was computed against 16.

This cuts AGAINST a generous authored past rather than for it. The argument in
§4(a) is that for the opening turns a seeded childhood would BE the character's
entire recalled lane, because the bank is too small to compete. Widening the
lane to 24 gives authored rows eight more slots to occupy while the lived bank
is still nearly empty. The median bank holds 11.5 rows at turn 3; at k=24 it
cannot even fill the payload, so anything authored is delivered in full, every
beat, for longer than this note assumed.

The cap of "one summary window and <=3 episodes" therefore stands and is if
anything generous. Recompute before changing it.

### (2) 2.23's retrieval argument is REFUTED, and the note should not lean on it

This note observes that `semantic` is unreachable and that stable facts have
nowhere to live. That remains true and remains a reason to want the tier.

What is now measured false is the RETRIEVAL consequence: that storing a stable
fact as an episode hurts recall because the episode's incidentals dilute its
document. Tested directly -- embedding the stored document against the bare
content across 15 missed preference probes -- dropping every incidental made it
0.005 WORSE, and content beat document on 9 of 15. The real cause is a plain
semantic gap: misses sit at 0.33-0.36 cosine from their answers, hits near
0.50, in every class.

So do not justify the tier's SHAPE by retrieval quality. Justify it by
citability -- the argument §1 already makes, which measurement did not touch.

### (3) The dispute prediction in §7 is now much more credible

This note predicts that a pre-story tier is where `record_dispute` would
finally fire, since an authored past is the one thing in a bank a story is
likely to contradict. That was a hypothesis about a mechanism which had fired
once in 9,608 rows.

Measured since
([`../experiments/SYNTHETIC_BANK.md`](../experiments/SYNTHETIC_BANK.md), and
UNBUILT 2.24 as corrected): handed a belief and the observation overturning it,
characters took the corrected fact **18 times out of 18** and NAMED the
contradiction in 15 of those, unprompted, with the stale row usually ranked
higher. The capability is real and runs at 83%; only the recording channel is
missing.

That makes the prediction testable rather than speculative, and it raises the
stakes: an authored past that a story contradicts will produce disputes a
character articulates and the engine still cannot store. **Build the channel
(2.24) before the tier, or the tier's most interesting output is discarded on
arrival.**

### (4) There is now an instrument for the tier's own falsifier

`memories.last_accessed_turn` (schema v32) records the TURN a recall reached a
row on, so depth of reach is `last_accessed_turn - turn_idx` and
`tools/recall_depth.py` reports the distribution.

Turn-less rows -- which is what this tier is made of -- have no `turn_idx`, so
depth is undefined for them. But `last_accessed_turn` alone answers the
question that decides whether the tier works at all: **are authored rows ever
reached, and how late in a story?** A seeded past that is retrieved in the
opening ten beats and never again is the failure §4 predicts, and it is now
visible without a benchmark. Instrument the arm this way rather than by
question-answering.

### (5) The ponder lane now scales with the payload

Deliberate recall asked for a fixed 4 rows and now asks for `recall_limit`
after absorption. It also passes `include_archived=True`, so it can reach
retired rows.

Both matter here. A character asking itself about its own past is exactly the
lane a pre-story tier should serve, and it is no longer the narrowest one in
the engine -- it was, until this week, permanently sized for a maximally
absorbed mind. If the tier is built summary-heavy as §5 Option D recommends,
the ponder lane is where those summaries will actually be consulted.

### Standing conclusion, unchanged

Nothing measured since contradicts the recommendation: a thin, summary-heavy
`turn_idx IS NULL` tier, authored with per-entry provenance, capped in the
writer, seeded once from card material already present. What changed is the
ORDER -- 2.24's channel should land first -- and the strength of the case
against a generous seed, which the wider payload makes worse rather than
better.
