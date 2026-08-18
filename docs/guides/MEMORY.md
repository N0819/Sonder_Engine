# Memory

How a character remembers: what gets written, what comes back, and what
decides. Every claim here is against source — `memory.py`, `commit.py`'s
memory domain, `agents/character.py`'s retrieval seam, and `providers.py`'s
embedding role.

Memory is **per character**, never per chat. There is no shared pool a mind can
read from. `memories.char_id` is on every row and every read path filters on it
before ranking, which is what makes the firewall a property of the query rather
than a rule the retrieval code is asked to respect.

Related: [`docs/guides/DATABASE.md`](DATABASE.md) for the schema-change checklist,
[`docs/guides/PIPELINE.md`](PIPELINE.md) for where in a turn this runs,
[`docs/guides/RESEARCH.md`](RESEARCH.md) §1.3–1.5 for the retrieval literature and why
there is no vector index.

---

## 0. What this layer has already demonstrated

Long-term character memory is already more durable than raw model context. Its
rows live outside any one provider request or context window, remain owned by
the same character, survive process restarts, checkpoints, rerolls, branches
and portable archives, and return older experience through bounded retrieval
rather than requiring the whole transcript to remain in every prompt.

This is an achieved orchestration advantage, not a claim that recall is solved.
The measurements below show relevant old evidence and earlier life windows
returning after they have left the recent-turn buffer; they also document real
failures in ranking, consolidation, embedding compatibility and belief
provenance. Durability is proven. Selecting the right memory, preserving what
it meant, and using it well remain measurable engineering problems.

---

## 1. The shape of a memory

One row in `memories` (`db.py`). The fields that do work:

| Field | What it is |
|---|---|
| `char_id` | Whose memory. The firewall's primary key. |
| `turn_idx` | Global play order. `NULL` for imported/authored memories with no place in play. |
| `frame_id` | Which temporal era it was formed in. `NULL` is the present. |
| `kind` | `episodic` / `dialogue` / `inference` / `semantic` / `relationship` / `promise` / `intention` |
| `category` | Derived from `kind` via `_default_category`; one of `MEMORY_CATEGORIES`. `episode`, `self` and `inference` are essentially all of it in practice — 5,301 of 5,380 live rows. |
| `provenance` | `witnessed` / `heard` / `told` / `read` / `inferred` / `remembered` |
| `salience` | How much it mattered **when formed**. Set at mint, never revised. |
| `importance` | How central it **became**, through consequences. `NULL` = never revised, and reads as `salience` (`effective_importance`). |
| `disputed` | The character's own later re-reading, if any. JSON `{turn_idx, reading, count}`; `''` when undisputed. |
| `confidence` | How much the character credits it *now*. Revised every turn for inferences (§7). |
| `content` | The full text. |
| `gist` | First sentences up to 240 chars (`_gist`), or model-supplied. |
| `key_phrases`, `entities` | Extracted at mint (`_extract_key_phrases`, `_extract_entities`) unless supplied. JSON arrays. |
| `location` | Room name. A retrieval cue (§5). |
| `valence`, `arousal` | The affect the character carried *into* the event. |
| `encoding_valence`, `encoding_arousal` | Resolved affect *after* appraisal — how the event left the character. |
| `embedding`, `cue_embedding` | Two float32 blobs (§4). |
| `embedding_model`, `embedding_dim` | Which model made them. A mismatch scores 0.0 forever (§9). |
| `archived` | Folded into a summary and retired from RECENT-buffer and consolidation reads. Still retrievable: `search_memories` passes `include_archived=True`, so archiving removes a row from the rolling window, never from recall. |
| `event_key` | Idempotency key. Re-minting the same key UPDATEs instead of inserting. |

`access_count` / `last_accessed` are written by `search_memories` and read by
nothing in the ranking. They are instrumentation.

### Provenance is not decoration

Six classes, and they route. `_PROVENANCE_SCOPE` maps each to one of three
summary scopes:

- `witnessed`, `remembered` → **autobiographical** — what I experienced
- `heard`, `told`, `read` → **hearsay** — what I was told
- `inferred` → **surmise** — what I concluded

Consolidation writes a separate `memory_summaries` row per scope, and
`build_character_memory_context` hands them back under three distinct keys.
The reason is stated in `memory.py` and worth repeating: a single melted
summary made a belief the character *inferred* come back a few turns later
indistinguishable from something they had *witnessed*. That is belief
laundering into knowledge inside one mind — the same layer collapse the engine
polices between minds, happening internally. Three scopes rather than a
provenance tag per sentence, because the summary is model-written prose and a
tag inside prose is a convention the model can drop; a separate row cannot be.

---

## 2. Writing — what a turn mints

All minting is in `commit.py`'s `prepare_memory_commit`, which builds the batch
without touching the database, and `commit_memories`, which writes it inside
the turn's transaction. Nothing else creates memories on the turn path.

Per character in the cast, from **their own perception view** (`v`):

**Episode** — `kind: episodic`, `category: episode`, `provenance: witnessed`.
The view verbatim. Salience from `_salience_of`: `0.45 + len/1600`, plus 0.08
per hit against a 15-word list (`attack`, `blood`, `secret`, `betray`, `kiss`,
`dead`, `weapon`, `threat`, `love`, `steal`, `scream`, `knife`, `confess`,
`liar`, `promise`), capped at 0.95. Crude, and deliberately so — it is a
deterministic floor, not a judgement.

A view that records no event mints nothing. `_is_empty_view` matches the
engine's own two placeholders — `"You are in an unspecified area"` (perception
could not name a room) and `"You register nothing new"` (character fallback).
Before that gate, 356 rows across five stories — 7.3% of the whole bank, and a
third of one story's — were that single sentence at salience 0.47, all
identical, all eligible to be handed to a character instead of something that
happened.

**Own conduct** — `category: self`, `provenance: remembered`. The only
durable record of what this character themselves said and did. The episode
cannot carry it: deterministic perception structurally excludes a mind's own
speech and acts from its own view (the `speaker == name` / `actor == name`
skips in `agents/perception.py`, plus `_strip_self_narration`) — that is the
firewall working, and it means a view is never "the first-person episode" of
the character's own conduct. Rendered by `_own_sequence_memory` as
grammatical chronological first person in decision framing (`"I said … Then
I tried to …"`), never the former `"I chose to attempted …"` fragment,
which replayed an attempt as a second resolved event beside the episode.
Bounded: every spoken beat mints one; a silent act mints only at the
character's own `salience >= 0.7` — idle motion keeps its 12-turn
`_recent_self_moves` window and the episode of its consequences instead.

This row was suppressed whenever a view existed between 2026-08-10
(d290ca4) and the repair — a premise true under model-composed perception,
false the day after, when 3a82657 made every view deterministic. Measured:
chat 67 holds 20 self rows over 51 turns; chats 69–80 hold 0 over 240
turns, and those eight days of play are not backfilled (see
`docs/UNBUILT.md`).

**Dialogue** — `provenance: heard`, salience 0.82, or 0.9 for a promise. Gated
hard by `_durable_dialogue_category`: only quotes containing a promise marker
(`"i swear"`, `"i vow"`, `"you have my word"`) or an identity/confession marker
(`"my name is"`, `"i confess"`, `"i killed"`, `"i love you"`). Everything else
spoken lives in the episode memory and nowhere else. This is why the live
corpus has 145 dialogue rows against 2,601 episodes — by design, not by defect.

The speaker's name passes through a **recognition gate**. If the hearer's
`known` map does not contain the speaker, the memory stores
`_unknown_actor_label`'s appearance-based description instead — and if there is
no appearance to describe, `"a voice"` rather than `"the unfamiliar person"`,
because a heard line is no evidence the hearer saw a body. `intended_target` is
dropped in that case too, since it names the speaker.

**Inference** — one row per mind-model update. `provenance: inferred`,
`salience: 0.45 + 0.3 * confidence`. That formula is load-bearing: it is how
`_mint_confidence_of` recovers the original confidence later without a second
column (§7). Empty evidence facts are omitted rather than producing
`Evidence: ; ;`, and a claim that already begins with its subject is not
prefixed with `About <subject>:` a second time.

### Encoding-time affect

`valence` and `arousal` come from the character's **stored resolved affect** —
last beat's `active_state.affect.surface` — not from the self-report the
character emitted this beat:

```python
_surface = (((st.get("active_state") or {}).get("affect") or {}).get("surface") or {})
if not _surface:
    _surface = (active_state.get("affect") or {}).get("surface") or {}
```

This is the mood the character carried *into* the event, before the beat's own
appraisal moved them, which is what encoding-time affect should be. The
fallback is only for a character's first beat.

The distinction was measured, and it matters: raw self-report averaged **+0.773
with 0% negative** against resolved affect's **+0.467 with 22% negative**.
Memories had been inheriting the saturated one — newer stories sat at a median
valence of +0.85 with 4 negatives in 3,162 rows. That is not an emotional axis,
it is a constant, and it silently disabled everything downstream that reads
affect (§5's mood congruence was unbuildable until this was fixed).

Schema v24 adds `encoding_valence` and `encoding_arousal`, stamped after
`resolve_affect` appraises this event. The original pair remains the affect
carried into it. Together they preserve two different facts: the state in
which an event was encountered and the state in which it was encoded. Legacy
rows migrate to neutral zeros rather than having an emotional arc invented;
new non-psychology rows default the after-pair to the before-pair. Both pairs
survive checkpoints, archives, portable character banks, and editor updates.

### Ordering, and why

`prepare_memories_batch` normalizes and **embeds** outside the write lock —
embedding is a network round trip and must never hold SQLite's writer. Then
`commit_memories` opens one transaction: `delete_turn_memories(turn.id)` (so a
rerun replaces rather than duplicates), the batch insert, relationship ops,
character state, then `reconcile_inference_confidence` — deliberately *after*
the state write, so this turn's own fresh inference rows are re-weighted by the
same reconciled mind-models everything else now reads.

Consolidation runs **after** the transaction, in a thread pool, because
summaries are reconstructible caches and a consolidation failure must never
roll back a valid turn.

---

## 3. Reading — what a character receives

`build_character_memory_context(chat_id, char_id, turn_idx, view, active_state)`,
called once per character per beat from `agents/character.py`. It returns:

```
unresolved_from_past:      remembered concerns/threads only (≤6)
recent_episodes:           first-hand chronological episodes, last 4 turns
recent_received_information: durable heard/told/read side records, if any
recent_conclusions:        inferred side records, if any
recalled_old_memories:     search_memories, k=16, minus anything already recent
autobiographical_summary:  first-hand only — the LATEST window (§8)
summary_key_phrases, unresolved_threads
summary_citations:         typed past ids/when/epistemic origin for summaries
earlier_in_my_life:        ≤2 earlier first-hand windows the beat ranks up,
                           oldest first, dated relatively; absent when none
where_i_came_from:         origin-era window, surfaced on drift signal (§8);
                           absent when no drift or no origin window
what_i_was_told:           hearsay summary, if any
what_i_concluded:          surmise summary, if any
surfaces_unbidden:         one contrast memory, when triggered (§6)
```

Nothing current is repeated under `memory`. The current view and observations
live under `perception`; current affect and goals live under
`self.active_state`. Micro-round observations use
`current:<perceiver>:micro:<nonce>`, so separate dialogue rounds cannot
collapse onto one evidence id. Legacy present spellings are normalized only at
the schema boundary.

Every row in those three recent lanes and `recalled_old_memories` is projected with
its durable `event_key` as `memory_ref`, `temporal_status: remembered_past`, a
relative `when`, `memory_form`, and `epistemic_origin`. The model projection is
an allow-list: numeric/database ids, access counters, archive state, embedding
metadata and retrieval scores remain host-only. Legacy rows without an event key are assigned a deterministic
portable key before retrieval. This duplication is deliberate: temporal status must be
visible in the row itself, not inferred from a parent list whose meaning a
model can flatten. Splitting recent rows is also chronological hardening: a
single turn is one experienced episode, while a durable quote and a conclusion
from that turn remain annotations rather than looking like two more events.
At the output boundary,
`agents.character._ground_observation_citations` permits only present, memory
and summary ids actually delivered to that mind across evidence, belief
updates, association updates and mind-model updates. It drops invented/stale
citations and warns rather than fabricating one if the model omitted it.
`present_evidence_used` accepts only current observation ids;
`memory_evidence_used` accepts only delivered memory/summary refs. Summary
windows use the third disjoint namespace `summary:<scope>:<end-turn>`; their
metadata lives in `summary_citations` (or directly on earlier/origin windows),
so summary-supported answers are citable without pretending a field name is an
event id. Derived summaries are rejected as evidence for durable belief,
association, relationship, or mind-model changes: compression may remind a
mind of a claim, but cannot independently reinforce it.

Epistemic origin describes the claim, not merely the shape of the memory that
contains it. A vivid first-hand episode of hearing another person make an
assertion still carries received information; it does not make their assertion
directly experienced truth. A conclusion formed during a witnessed episode is
still inferred. The character prompt states this explicitly so episodic
vividness cannot launder testimony or interpretation into knowledge.

### Psychology bandwidth and memory modulation

`cognitive_absorption` reaches the memory seam. Below 0.35 the normal budget is
12 recent / 16 recalled / 2 earlier windows. From 0.35–0.70 it narrows to
8 / 8 / 1; at ≥0.70 it narrows to 4 / 4 / 0. Those last raw memories are the
automatic-recognition lane: bodily absorption reduces deliberative historical
search without erasing a familiar face, warning, or promise associated with
the present cue.

Character appraisal has the same structural split. Present novelty, goal
impact and somatic impact require current evidence. Remembered past may change
familiarity, expectation, anticipatory emotion, and perceived coping only
through `appraisal.memory_modulation`, grounded to past refs. At commit,
familiarity can reduce novelty by at most 35%, and remembered coping can move
coping potential by at most ±0.25.

A recollection may also produce a mild, explicitly labelled body echo.
`somatic_echo` is signed (aversive tension to pleasant warmth) and
`threat_bias` primes danger detection; both require a delivered past ref and
are engine-capped to 0.2. They reach mood/arousal and acute stress only through
`active_state.memory_echo {temporal_source: remembered_past, source_refs}`.
They never enter `somatic_impact`, hedonic pain/pleasure, injury, or a current
goal impact, and threat bias is not evidence that danger is present. The echo
is one-beat state: it may leave ordinary affect/stress inertia behind, but its
source label itself is not carried forward after the recollection stops.

### Deliberate recall: `ponder`

A character may exceptionally place
`{type: "ponder", query, why}` in its sequence. Normalization removes that
private cognitive action from the public sequence before Director resolution,
perception, and narration. Commit stores one query on the character's own
state; the next turn in which that character runs consumes it.

The next memory payload keeps normal cue/mood/goal recall unchanged and adds:

```text
deliberate_recall:
  query_i_chose_last_turn
  temporal_status: remembered_past
  retrieval_origin: deliberate_ponder
  result_refs
  additional_episodes
  may_set_another_ponder_this_turn: true
```

Any ponder result already present in normal recall is marked with both
`normal_recall` and `deliberate_ponder` rather than duplicated. Up to four
additional episodes may be supplied. Their refs are grounded exactly like any
other raw memory. The result therefore says both *this is remembered past* and
*this came back because I deliberately asked myself about it*.

Ponder is intentionally not a default retrieval tax. A non-empty query and a
concrete `why` are required, only one pending query exists, and ponder is
absent from the default output example. A result may legitimately raise a new
question immediately, so there is no cooldown; receiving results by itself is
explicitly not a reason to ponder again. It costs an extra embedding call only
when used.

### One seam, two hard filters, applied before any ranking

Every mind-facing read goes through `memory.visible_memory_rows`. Its three
invariant-bearing arguments — `before_turn_idx`, `viewer_frame_id`,
`include_archived` — are **required and have no defaults**, so a caller cannot
omit one. It can only state it, including stating `None`. Forgetting a rule is
a `TypeError` rather than a leak.

The remaining arguments (`since_turn_idx`, `require_turn_idx`) only ever
*narrow*. None can readmit a row the filters excluded, which is what keeps this
a seam rather than a configurable query builder.

**The turn cutoff (audit F1).** `search_memories` drops every row with
`turn_idx >= current_turn_idx` before scoring. A mind deciding turn N must never
retrieve a memory of how turn N turned out — which is not hypothetical, because
a reroll or rerun-from-stage replays the onset of a turn whose outcome memories
are already committed. `current_turn_idx` used to feed only recency scoring,
which *ranked those rows highly* rather than dropping them. `turn_idx IS NULL`
rows are kept: they belong to no turn, so they cannot be this turn's leaked
outcome.

**Frame visibility.** `frames.is_memory_visible(char_id, memory_frame,
viewer_frame, turn_idx)` — a memory is visible if it is diegetically at or
before the viewer's era, or if the character is a registered traveller of that
frame. Spatial frames short-circuit the ordinal rule and **fail closed** on a
missing `turn_idx`.

`search_memories`, `contrast_memory`, `recent_memory_buffer`, `list_memories`
and `consolidate_character_memory` all read through the seam.
`list_memories` is the one that passes `before_turn_idx=None`, deliberately:
it is the host's memory panel, where nobody is deciding a beat and there is no
future to withhold.

**This document used to claim the opposite, and the claim was wrong.** The
filters were previously written out again at each of those five call sites, and
this section said that repetition "is the reason a new read path cannot
forget." That reasoning is backwards. Repetition is precisely how a sixth path
forgets, because nothing obliges it to reproduce five rules it may not know
exist — the safety was resting on whoever wrote it next remembering, which is
not a property of the code. Hence the seam.

Enforcement is `tests/test_memory_read_seam.py`, which asserts each rule
against the seam, asserts it again through every character-facing public API
one excluded class at a time, and asserts that the invariant arguments have no
defaults. All four rules are mutation-tested: deleting any one of the turn
cutoff, the frame filter, the character scoping, or the archived policy fails
between 1 and 6 of those tests. That check earned its keep immediately — an
earlier draft of the seam applied the turn cutoff twice, in SQL and again in
Python, and deleting the Python half left all 21 tests green. A guard nothing
can observe failing is not a guard, so it went.

### Reads that deliberately cross characters

`dramatic_irony_feed` and `promise_ledger` answer a question *about the cast* —
what the player knows that a character does not, what has been promised across
the story — rather than a question a character asks itself. They are not scoped
to one `char_id` and must never feed a mind's context. They are listed in
`memory.HOST_SCOPE_READERS` so the crossing is a named exception, and a test
fails if an unlisted cross-character reader appears.

### The two filters

---

## 4. Embeddings

Two vectors per memory, both L2-normalised:

- **`embedding`** — from `_memory_document`: a labelled block of category, turn,
  location, people, key phrases, gist, details, source, emotion.
- **`cue_embedding`** — from `_memory_cues`: gist, key phrases, entities,
  location, category. Shorter, and closer in shape to a query. It carries the
  highest weight of the four rankings for that reason.

`providers.embed_texts_meta` calls the configured `embeddings` role and returns
an `EmbeddingBatch` with `model_key = "{kind}:{id}:{model}"`, `dimensions`, and
a `fallback` flag.

**Any failure degrades to `cheap_embed`** — a signed hashing trick over
character 3- and 4-grams into 256 dimensions, stamped `cheap:crc32:256`. It is
a fuzzy *lexical* signature, not a semantic vector. It retrieves reworded text
well when the wording shares vocabulary and **not at all when it does not**:
measured against a real 441-memory story with vocabulary-disjoint paraphrases,
recall was **0% at every k**, median rank 228 of 441 — indistinguishable from
random.

The failure is silent by construction, so it is announced in three places: a
`ctx.warning` on the turn, `_warn_stranded_embeddings` once per
(chat, char, model) at retrieval, and `embedding_bank_status`'s
`fallback_reason` — verbatim from the provider, because "no embeddings
provider" is the wrong sentence when one *is* configured and is simply not an
embeddings model. Selecting a chat model for this role returns `"Model
inception/mercury-2 does not exist"`, which is the one line that explains why
recall stopped improving.

---

## 5. Ranking

`search_memories` fuses **four rankings plus one per aspect** with Reciprocal
Rank Fusion, then applies scalar bonuses, then diversifies.

### The four rankings

| Ranking | Weight | Source |
|---|---|---|
| exact phrase or entity match | 1.25 | `_exact_cue_score` — a key phrase, entity or location literally present in the query |
| cue-vector match | 1.15 | cosine(query, `cue_embedding`) |
| keyword match | 1.1 | BM25 over `memory_retrieval_fts` (FTS5, `unicode61 remove_diacritics 2`) |
| semantic match | 1.0 | cosine(query, `embedding`) |

The cue vector outranks the full-document vector because it is built from the
same short, cue-shaped material a query is: gist, phrases, entities, location.

Each contributes `(weight * _RRF_SCALE) / (60 + rank)`.

### `_RRF_SCALE = 12.0`, and why it exists

RRF output is arbitrary in magnitude — about 0.02 at rank 1 — and only its
*order* carries meaning. The bonuses that follow are hand-tuned on a 0..1
utility scale. Summed raw, the four rankings could contribute at most **0.074
combined**, while the recency bonus alone reaches **0.12**. A recent, salient
memory with *no relevance to the query at all* outranked the single best match
on every relevance signal the engine has.

It was invisible until alpha 6.3: with the crc32 fallback the vector rankings
were lexical noise, so nobody could tell they were being ignored. Configuring a
real provider made the signal real and the imbalance measurable — end-to-end
retrieval of a paraphrased memory ran at **1/16**, and **88%** of the memories
handed to a character carried no vector match at all.

Scaling rather than re-tuning the bonuses, because the bonuses' *relative*
values are meaningful. 12 puts the four rankings at ~0.9 against a ~0.4 bonus
band: relevance leads, and salience/recency/presence still decide between
comparably relevant memories, which is what they are for.

### Aspects — `_ASPECT_WEIGHT = 0.55`

What the character *brings* to the beat travels as separate facets, each with
its own ranking:

```python
aspects = [("what you are trying to do", active_state["goal"]),
           ("how you are feeling",       active_state["mood"]),
           ("what is still unsettled",   " ".join(unresolved_threads))]
```

Concatenating them onto the query did nothing, and this is the measurement that
proves it: the view runs a median **1,015 characters** against a mood fragment
of 10–60, so `cosine(query_with_mood, view_alone)` came out at **0.994**. The
mood moved the query vector by essentially nothing and reached recall only
through whatever stray n-grams the word happened to share. A short facet cannot
compete for influence inside a long string; given its own rank list it does not
have to.

Weighted below both vector rankings on purpose: an aspect should break a tie
between comparably relevant memories, never outrank what the beat is about. One
embedding call covers the query and every aspect, so separating them is free.

### Scalar bonuses

```
+0.08 * rank_normalized_importance
+0.04 * confidence
+0.10 * (confidence - 0.5)     inference rows only, signed around 0.5
+0.08 * exact_cue_score
+0.05 * mood_axis * valence    mood congruence
+0.12 * age  or  (1 - age)     only if the query carries a temporal cue
+0.09                          memory's location == where you are
+0.05                          memory's location is visible from here
+0.10                          promise category, when the query says "promise"
```

**Salience is respaced before it is weighed**
(`_rank_normalized_importance`). The term reads `effective_importance` —
revised importance where there is one, minted salience otherwise — but
rank-normalised across the rows THIS search can see, inside their own p10-p90.
Ordering is preserved exactly and the influence budget is unchanged; only the
gaps move.

That is a smaller change than it sounds and a larger one than it looks,
because the obvious versions of it are neither. Replaying 270 real recalls
(`tools/salience_replay.py`):

| arm | top-16 membership moved |
|---|---|
| the term deleted entirely | 35.2% |
| percentile-normalised to [0,1] | 59.6% |
| stretched 3x about the mean | 47.0% |
| respaced inside the bank's own range | **15.2%** |

So the term was never decoration — deleting it moves a third of all results —
and both ways of "fixing" the measured compression (p10-p90 spread 0.27, 70%
of the corpus between 0.6 and 0.8) move retrieval MORE than deleting it,
because values in a 0.27-wide band mapped onto [0,1] gain about 3.7x the
influence while reordering nothing. The defect actually fixed is that this
term's discrimination depended on how the minting model happened to spread its
numbers: a bank minted at 0.70 ± 0.03 had a silent salience term and one
spanning 0.4-0.9 had a loud one, for a reason with nothing to do with the
story. Callers asking an ABSOLUTE question — archiving, contrast selection —
still read `effective_importance` directly.

**Belief weighting** is signed around 0.5 so a held belief is promoted and an
abandoned one demoted, and it is in the same band as salience rather than
larger — it should break a tie between competing inferences, not outrank an
actual semantic match. It carries a `retrieval_reasons` list either way: *"belief the
character still holds"* (≥0.6) or *"belief the character has since revised"*
(≤0.25).

**Mood congruence** (`_MOOD_CONGRUENCE = 0.05`) reads the *signed* half of an
affect signal the engine already tracked and had never used. `_mood_axis`
word-matches the mood string against a small closed vocabulary — deliberately
not embedded, because this is a tiebreak and a wrong sign is worse than no
sign. Same-signed feeling pulls up, opposite pushes down, scaled by how charged
the memory itself is; a neutral memory is untouched. Bounded on purpose:
congruence is a **feedback loop** — a character in despair recalling only
despair deepens the despair. That may be exactly right for fiction (it is what
rumination is), but it should be a chosen intensity rather than an emergent
one.

**Temporal cues** only fire on explicit query language: `_OLD_CUES` (`"years
ago"`, `"back then"`, `"first time"`) or `_RECENT_CUES` (`"just now"`, `"a
moment ago"`). There is no unconditional recency term — recency reaches recall
through `recent_episodes`, which is a separate field.

**Location** was stored on every row and read by nothing until alpha 6.3.
"What happened in *this* room", and the navigational form of it — "which way
did I go from here last time" — had no index behind it at all. Additive rather
than a filter: being here makes a memory easier to reach, it does not make
everything elsewhere unreachable. The visible-room cue is weighted below the
here-cue, since standing somewhere is stronger evidence of relevance than
looking at it.

### Selection: MMR, then chronological padding

```python
mmr = 0.82 * relevance - 0.18 * redundancy
```

Greedy maximal-marginal-relevance over the top `max(k*8, 40)`, where redundancy
is cosine against already-selected memories (`_memory_similarity`, falling back
to Jaccard when vectors are incomparable).

Then up to `k+2` total: for the top 3 selected *episodes*, pull in
chronological neighbours within one turn, tagged `"chronological neighbor of
recalled episode"`.

Results are returned in chronological order, not ranked order, because every
caller reads them as a narrative. `access_count` is bumped for everything
returned.

### `_RECALL_LIMIT = 16`

Was 8, and measured too low once relevance actually worked: at 8, the padding
neighbours were a third of what the character saw. Raising it dilutes them with
relevance-selected memories — mean relevance of the whole set **rises** from
0.608 to 0.640 while the least-relevant slot does not move, i.e. the added
memories are better than the padding they displace.

16 rather than 24 because the curve flattens: end-to-end paraphrase recall goes
**7/16 → 11/16 → 13/16** across k = 8/16/24, but relevance moves only 0.640 →
0.649 while the payload grows ~890 → ~1,242 tokens per character per beat. The
attention budget is real.

---

## 6. Unbidden recall (contrast)

Ordinary recall asks *what is most like this beat*. A character measurably
stuck needs the opposite question answered once: *what that mattered is least
like this beat*. Adapted from SIGMA SRIP-14 §XXII, *Retrieval as Perturbation
Source* — see [`docs/guides/RESEARCH.md`](RESEARCH.md) §1.5 for what carries over and
what deliberately does not.

**The trigger is fully deterministic — no model call.**
`agents/character._unbidden_trigger` fires on one of four stuck signals:
`refrain` (a repeated sentence shape), `verbatim_repeat`, `goal_held` (the same
ungoverned goal for a dozen beats), or `plateau` (sustained hedonic stimulus).

Then four suppressors, in order:
- absorption ≥ ceiling — a mind fully absorbed is not stuck, it is busy;
- an open **drive-rupture** window — engine-crisis machinery outranks texture;
- `suppressed`, set by commit after **two consecutive injections that helped
  nothing** — a character stuck for a reason contrast cannot reach should stop
  receiving reminiscence and let the real cause surface;
- cooldown, plus **`clear_seen` hysteresis** — edge-triggered, so the trigger
  must have been observed clear before it may fire again. A level-triggered
  version would re-fire every beat of a long stuck stretch and become
  wallpaper.

**Scoring** (`contrast_memory`) is a second pass over the same rows ordinary
recall reads — same character, same turn cutoff, same frame filter, and **no
writes**, because it runs mid-pipeline at character-stage time and must not
touch `access_count`. Requires a bank of ≥20 and salience ≥ 0.5. Excludes
`promise` / `intention` / `relationship`, which have their own governance —
surfacing a promise "unbidden" reads as the engine nagging.

```
score  = salience
       + 0.5 * |valence|          emotional charge
       + 0.3 * arousal
       + 0.4 * (age / current)    older is further from now
       - 0.8 * jaccard(query, gist+phrases)
       - 0.7 * cosine(query, embedding)     only when comparable
       - 0.3   same location
       - 0.4 * (share of entities present in the query)
```

Confidence is deliberately ignored: a belief the character has since set aside
is exactly the sort of thing that returns unprompted.

### The inversion trap

The semantic term is gated on **90% model coverage** of the bank
(`_CONTRAST_SEMANTIC_COVERAGE`), and that gate is not optional. A row embedded
by a different model scores 0.0 against any query. In `search_memories` that
makes it invisible — a silent omission. Here the axis is **inverted**, so the
same 0.0 reads as *maximally contrasting*, and unbidden recall would
preferentially surface precisely the memories that have not been rebuilt yet.
The identical number flips from an omission into a systematic bias. A story
mid-rebuild degrades to the old structural-only behaviour rather than to a
wrong one.

**Delivery substitutes, never adds** (`_attach_unbidden`): when recall is
already at budget, the lowest-scoring ordinary memory yields its slot, so total
recalled material per payload is constant. The payload key carries the
epistemic status — `it_comes_back_to_me`, with `from` in the same three
provenance labels the summaries teach, plus `when` and `where`. No id, no
score, no instruction. Nothing here mints a memory row: a surfaced memory is
context, and only what the character then *does* is canonical.

---

## 7. Belief revision

An inference memory is minted with the confidence the character declared when
they formed it. Meanwhile their `mind_models` keep moving —
`theory_of_mind.apply_mind_model_updates` blends a restated belief upward,
partially explains away the competitor it displaces, decays the unreinforced,
and prunes what falls through the floor. Without reconciliation a character
could hold one belief and preferentially **recall the one they had already
abandoned**, because recall ranked on a number frozen at mint time.

`reconcile_inference_confidence` runs every turn inside the commit transaction:

- claim still carried by a live hypothesis → that hypothesis's decay-adjusted
  credence, **floored** at the abandoned resting value (half-life decay on a
  surviving hypothesis measures staleness, not disbelief — held ≥ abandoned,
  always);
- claim no hypothesis carries → `_abandoned_confidence(salience)` =
  `min(mint, max(0.08, mint * 0.55))`, where `mint` is recovered from salience
  by inverting the mint formula.

**A fixed fraction of the mint value, never a compounding per-turn decay**, and
that correction has numbers behind it. Under the compounding rule, 76–80% of a
long chat's entire inference bank reached the floor within 7–18 played turns,
at which point belief weighting removed inferences from recall almost
completely — 0–1 of top-8 against 13–15 at mint confidence in replayed
late-turn retrievals. A belief that merely aged out of the working set was
never concluded *wrong*, and must not rank as though it was. Being a pure
function of the untouched salience also makes reconciliation **idempotent**,
so a corpus previously crushed by the old rule self-heals on its next pass with
no migration.

`salience` is never touched — it records how much the inference mattered when
formed, which is a different question from how much the character credits it
now.

**The firewall note that matters:** the only inputs are this character's own
memory rows and their own mind-models. Nothing consults the objective record,
another mind's state, or whether the belief was actually *true*. A character
revises because of what they later perceived, never because they were graded
against reality — reconciling against truth would collapse the belief layer
into the truth layer, which is the one distinction this engine exists to keep.

---

## 8. Consolidation and archiving

`maybe_consolidate_character_memory` fires when the character is ≥10 turns past
their last summary **or** has ≥40 unarchived memories since it. It refuses to
run outside the present frame: a per-character summary has nowhere to put "as
of the present era" versus "as of the flash-forward", and consolidating outside
the present would permanently blend eras with no way to un-blend them. A frame
visited away from the present just accumulates raw memories until play returns.
(Windows do not change this. They are bounded by turn index, which is *global*
play order shared by every frame, so a window still cannot separate two eras
that interleave in it.)

`frame_id` is passed **explicitly** rather than read from the ambient
contextvar, because the real caller runs each character on a
`ThreadPoolExecutor` worker, and that does not propagate contextvars.

`consolidate_character_memory` sends only memories **after** the previous
summary's `end_turn_idx` — the earlier ones are already folded in, and re-sending
them made the payload grow without bound across a long chat. It writes one
`memory_summaries` row per scope, **per window**. The first-hand row is written unconditionally,
even for a window that produced nothing first-hand, because its `end_turn_idx`
*is* the cursor — skip it on a hearsay-only window and the same memories
re-consolidate forever.

**Archiving** then retires rows that are all of:

- older than `max(start_turn, end_turn - 12)`,
- salience **< 0.72**,
- not `promise` / `relationship` / `intention`,
- and **part of this frame-visible consolidation set** — a blanket UPDATE also
  archived another era's memories that had correctly been excluded from the
  summary and so were never folded into any summary at all.

Archived rows are not deleted. `search_memories` defaults to
`include_archived=True`, so they remain retrievable; archiving removes them
from the consolidation window and the recent buffer.

### Windows — one row per era, not one per character

Until schema **v23** the key was `UNIQUE(chat_id, char_id, scope)`, so a scope
held exactly one row and every consolidation overwrote it. The cost was not
storage. It was that **the summary layer could not be searched**, because there
was nothing to search between — while every summary already carried a
maintained `embedding`, computed on write, re-embedded on a model change,
carried verbatim through every archive and checkpoint, and read by no retrieval
path in the engine. Sixty-seven vectors on the live bank, maintained for years
of turns, never once ranked.

v23 completes the key with `end_turn_idx`. Two things follow, and the first is
the notable one:

**Consolidation did not change.** It was already computing bounded windows —
`start_turn = min(turn_idx)` and `end_turn = max(turn_idx)` over the memories of
*that pass only*, which are already the ones after the previous summary's
`end_turn_idx`. Correct windows were being computed and then thrown away by the
constraint on the next write. Completing the key was the entire fix; re-running
a consolidation that lands on the same boundary still updates in place rather
than duplicating.

**`search_memory_summaries` ranks them.** Scoped exactly like `search_memories`:
`char_id` is the bank, `before_turn_idx` applies the same exclusive cutoff (a
window that closed at or after the deciding turn describes how this beat turned
out), and a window whose vector came from a different embedding model is
skipped rather than compared. `exclude_latest` defaults to true so a caller
sending both this and `get_memory_summary` does not send the same window twice.

`get_memory_summary` returns the *latest* window, which was identical behaviour
for every bank alive at the migration — each had exactly one row.

### A window is a chapter, not a life — and the singleton was losing the rest

The payload half was deferred on the reasoning that summaries are CUMULATIVE:
consolidation folds the previous summary into each new window, so sending
bounded windows without a reliable path to the older ones would cost a character
their early history. **Measurement inverted that**, and the inversion is the
reason the payload half then landed.

The consolidator is told to merge the previous summary forward. It is told just
as firmly to keep low-salience detail out, and shedding wins:

| | successive live windows |
|---|---|
| shared text | **3–16%** |
| cosine | 0.57–0.88 |

The Doctor's second window (chat 58) recaps the first in one clause — *"escaped
the Dalek into the TARDIS and dematerialized"* — and is otherwise entirely about
its own ten turns. Six pairs is a small sample and the direction is not
marginal.

So the latest window is the latest **chapter**. Which means the pre-v23
singleton was not holding a life and overwriting nothing; it was overwriting
every chapter before the last one. The pre-repair survey found **53 of 67
banks with no summary covering their opening turns**. Windows did not create
that risk; they are the first thing that stops it.

The raw rows survive — nothing was deleted and `search_memories` reaches
archived rows — so the loss is in the summary layer only.
`backfill_memory_summary_windows` reconstructs destroyed leading windows from
those rows without archiving anything or moving the forward consolidation
cursor. The host exposes that repair, and the checkpoint propagation described
below keeps a later rollback from undoing it. Bounded gaps *between* surviving
windows remain a separate repair problem (`docs/UNBUILT.md` §2.17).

### Reading the earlier chapters

`build_character_memory_context` ranks the earlier windows against the beat's
own query and sends the best `_SUMMARY_RECALL_LIMIT` (2) beside the current one:

```
earlier_in_my_life: [{what_i_lived_through_then, when}, ...]
```

- **First-hand scope only.** Hearsay and surmise have windows too; three
  provenances in one field is the collapse the separate scopes exist to prevent.
- **Chronological, oldest first.** Ranking chooses *which*; it must not choose
  the order a life is read in.
- **`when` is relative** — "between about 40 and 50 beats ago", never an
  absolute index. `turn_idx` is global play order shared by every frame, so an
  absolute number would tell a mind where a flash-forward sits in the story's
  construction. Every dated thing in the payload obeys this (see
  `_unbidden_entry`).
- **Absent, not empty**, when there is nothing to send — like the provenance
  summaries. An empty key still spends attention.
- Same guarantees as raw recall: one character's bank, the same exclusive turn
  cutoff, a cross-model vector skipped rather than compared, and
  `exclude_latest` so `autobiographical_summary` is never sent twice.

The cutoff applies to **every** summary surface, not only ranked earlier
windows: latest autobiographical, hearsay, surmise and drift-triggered origin
reads all require `end_turn_idx < current_turn_idx`. This matters on a rerun,
where later windows still exist in storage but do not yet exist for the mind
deciding the earlier beat.

**No minimum score, deliberately.** Every prose vector scores every window
somewhere in a compressed 0.45–0.55 band, so an absolute floor drops everything
or nothing depending on the embedding model — and would silently become
"nothing" the day the model changes. What the band *does* separate is rank: a
memory formed inside a window ranks that window above the other one 97% and 82%
of the time across the Doctor's two windows (176 embedded memories). The
ordering is trustworthy where the magnitude is not.

**It costs no extra round trip.** `search_memories` has always batched the query
with its aspects; the windows rank against the same query vector, so both take
one shared `EmbeddingBatch`. Raw recall validates the batch shape against its
aspects; the summary layer deliberately reads only vector zero, the beat query.

**And it duplicates little.** Across 48 probes on the live bank, a mean **14%**
(median 12%) of the sixteen recalled raw memories fall inside the sent window's
own turn span. The window is mostly reaching turns raw recall did not.

### Origin-era retrieval on drift

```
where_i_came_from: {what_i_lived_through_then, when}
```

An origin is not a similarity match: a character's foundational era is
frequently dissimilar to whatever is happening now, which is exactly when it
should still be present. Top-k drops it in the beats where it matters most.
Rather than always including the origin (which costs a slot every beat for
something usually irrelevant), `_origin_on_drift` surfaces the earliest
first-hand summary window when a drift signal fires:

- **goal_held**: the same ungoverned goal for 12+ beats.
- **project adrift**: a held project has gone 8+ beats without anything
  serving it.
- **mood sign-flip**: the current affect valence has flipped sign from the
  character's baseline (abs > 0.15, product < 0).

Absent (not empty) when no signal fires or when there is no origin window. Not
added to `earlier_in_my_life` because those are similarity-ranked; the origin
is surfaced for a different reason and should not compete for a similarity
slot. Deliberately does not duplicate a window already in `earlier_in_my_life`.
Like every other summary read it requires the window to have closed strictly
before the deciding turn.

### Backfilled windows survive rollback

Backfill is a repair performed after old checkpoints were written. Without a
second step, restoring one of those checkpoints restores the pre-v23 singleton
and silently deletes every reconstructed era. After a host-triggered backfill,
`propagate_memory_summaries_to_checkpoints` adds each derived window to every
eligible checkpoint (`end_turn_idx < checkpoint.turn_idx`). Existing snapshot
rows win and every other checkpoint field remains byte-for-byte untouched.

The longest live story, chat 38, was repaired through this path on 2026-08-02:
**41 summary rows** are live (19 first-hand, 9 hearsay, 13 surmise), all five
legacy memories missing an `event_key` were assigned stable keys, and the
windows were propagated into **109 eligible checkpoints**. No live memory in
that story now lacks an event key. Substantive first-hand coverage is Doctor
419/452, Picard 8/17, and Guinan 25/29; the remaining bounded interior gaps are
recorded rather than silently described as complete.

### Controlled semantic-versus-lexical result

`tools/benchmark_memory_temporal.py` asks the Doctor seven independent
memory questions against chat 38. Each arm uses the same character prompt,
current observation and payload schema; only production retrieval's embedding
function changes. The character model was `x-ai/grok-4.20` and every question
ran in an isolated call.

| Measure | Semantic embeddings | Lexical-only fallback |
|---|---:|---:|
| character answers passing | 7/7 | 5/7 |
| citations grounded in delivered evidence | 100% | 100% |
| historical cases with relevant evidence delivered | 5/5 | 2/5 |
| historical cases with a relevant earlier window | 5/5 | 0/5 |
| raw-memory mean reciprocal rank | 0.207 | 0.400 |

The answer totals include one deterministic scorer correction on the stored
outputs: “never stated” was the same correct kitsune-provenance answer as
“never said,” but the original term list recognized only the latter. The raw
artifact therefore says 6/7 vs 4/7; the benchmark source now recognizes both.

The empirical claim is narrow and useful: embeddings materially improve
coverage (all five historical questions versus two), especially the correct
earlier chapter, and the tested answer score improved with it. Lexical MRR is
higher because its two successful exact-word queries landed at rank 1 while
its other three queries missed entirely; semantic retrieval reached all five,
at ranks 2, 8, 3, summary-only, and 13. Temporal typing and citation grounding
worked in both arms. This benchmark proves reachability and present/past
separation, not yet reliable conduct; the next behavioural measurements are
shelved in `docs/UNBUILT.md` §2.17.

---

## 9. Changing the embedding model

A vector can only be compared with one from the same model. Switching providers
re-embeds nothing, and a mismatched row scores 0.0 on both vector rankings
**forever** — correct behaviour, and silent, which is the problem. The bank
splits into two eras and nothing says a word. Retrieval still *works* (BM25 and
exact match are unaffected), so it degrades rather than breaks, which is
exactly why it needs announcing.

Three pieces handle it:

**`rebuild_embeddings`** re-embeds every row whose model key does not match the
live one, in batches of 32, each committing on its own. Resumable by
construction, since the selection *is* "rows that do not match". It rebuilds
with the same document construction `_embed_memory` uses — a vector built from
different text is not comparable with one built from the same text, and a
rebuild that quietly changed the recipe would be a subtler version of the bug
it fixes. It **refuses to write a fallback over a real vector**: a batch that
comes back `fallback` when the caller is not deliberately rebuilding *to* the
fallback aborts the run and reports what it managed, because marking rows
migrated while downgrading them is the one outcome worse than not running.

**`rebuild_checkpoint_embeddings`** carries a completed rebuild back through
saved states. A checkpoint holds each vector so that restoring one never
re-embeds a bank — which means a checkpoint written *before* a rebuild holds
the old vectors, and rolling back silently undoes the rebuild. Measured live:
one reroll put **637 of 642 rows** back on the crc32 fallback.

It **re-embeds nothing**. A vector is a pure function of the memory, and the
same memory appears in dozens of checkpoints unchanged — one chat held 40,224
memory copies across its checkpoints and only 526 distinct, 90.7% of which
already had a rebuilt vector in the live table. So the fix is substitution:
look each saved memory up by `_memory_vector_key` and write in the vector
already earned. A saved row with no live match is left exactly as it was, never
blanked and never guessed at. A blob is rewritten only after re-parsing to
prove it is still valid JSON with the same row count. `dry_run` is the default.

That key is `(char_id, sha1(the exact text that was embedded))`, and *which*
text is the whole point. It keyed on the `content` field until alpha 6.6, on
the reasoning that a vector is a pure function of the memory. It is — but not
of its content: `_memory_document` also folds in turn, location, category,
key_phrases, entities, gist, provenance and emotional_context, and a summary's
vector comes from `_summary_retrieval_text`, not its `summary` field. Two rows
could therefore agree on content, hold different vectors, and be handed each
other's. `_memory_vector_key` now hashes the whole document and
`_summary_vector_key` the whole retrieval text.

### Where a checkpoint's vectors actually live

Not inline, since alpha 6.6. A checkpoint is a full snapshot of the bank, so
storing two float32 blobs per memory re-stored the same vector on every turn
for the life of the story. Measured on a live database: checkpoints were 94.5%
of a 4.4 GB file, `memories` was 98.9% of each checkpoint, and the two vector
fields were 96.9% of that — one story held 40,224 memory copies and 583
distinct vectors, 1.00 GB that needs 13 MB.

`checkpoints.compact_checkpoints` lifts them into `memory_vectors`, keyed by
**`memory.vector_address`: sha1 over the vector BYTES**, prefixed `v1:`. The
entry keeps a `vkey` reference in place of its blobs. Note the two addressing
schemes answer different questions and must not be confused: `_vector_key`
above joins a *saved memory to a live rebuilt row* and so keys on the embedded
text; `vector_address` deduplicates *identical stored vectors* and so keys on
the bytes, so two rows collide only if their vector payloads are byte-identical,
in which case sharing storage is correct rather than a fault. The hash itself
is not a proof: SHA-1's collision resistance is broken, and an address space is
never collision-FREE, only collision-unlikely. What removes the production
failure is that the address is over the exact bytes rather than over a
reconstructed text. Byte-addressing was the fix for a real production collision — chat
36 held "You are in Ten Forward." at turn 42 and again at turn 44, same
character, same content, two different embedding payloads.

Each checkpoint stays **independently restorable**: this is content-addressing,
not delta encoding, so there is no chain to walk backwards and no intermediate
whose corruption poisons what follows. `_verify_no_loss` proves a compacted
blob restores field-for-field to what the original held before the rewrite
commits. `memory_vectors` is **append-only and never garbage-collected** — a
checkpoint predating a deletion still references the vector, and a rollback
that cannot resolve one is a worse failure than some orphaned rows. Schema and
operational detail in [`docs/guides/DATABASE.md`](DATABASE.md).

**`start_rebuild_if_needed`** is the standing reconciler. It is deliberately
*not* a one-time migration: a mismatch appears whenever the embedding model
changes — configuring a provider, switching providers, a provider changing its
default model or dimensions, or falling back to the hash because a key expired.
It is a condition to be reconciled whenever it holds.

Where it actually runs, which is narrower than the module comment above it
suggests:

- **after a checkpoint restore** (`checkpoints.py`), automatically — a restore
  writes old vectors back over rebuilt ones, so this is repair, not a new
  decision;
- **on `POST /api/memory/embeddings/rebuild`**, i.e. when a host asks.

It is **not** called at startup, and **not** by `PUT /api/agent_models`. That
route detects an embeddings-role change and returns `embeddings_role_changed`
plus the bank status for the UI to prompt on, but deliberately starts nothing:
a rebuild talks to a paid provider and can run for a while on a large bank, and
doing that silently because someone opened a settings panel is the wrong
default. The host is told and decides.

Never call any of these on the turn path: they are O(bank) and they talk to a
provider.

---

## 10. Why there is no vector index

Recall ranks one character's rows in Python and deliberately uses no ANN index.
There are two arguments for that, they have **different shelf lives**, and an
earlier draft of this section filed both under "settled permanently" — which
was true of one of them.

**Structural, and it does not expire.** The filters that matter run before
ranking. A mind may not retrieve how the turn it is deciding turned out, and
may not see another frame's memories. Both are per-query predicates over
`turn_idx` and `frame_id`. An approximate-nearest-neighbour index cannot apply
them cheaply before its search — it would return neighbours and let the filters
cut them afterwards, which changes *how many* results survive rather than
*which* are best. Any future index has to answer this, whatever the corpus
looks like.

**Workload, and it is a measurement, so it can go stale.** Measured: 126 ms at
3,500 memories, 709 ms at 35,000, 2.2 s at 200,000. Beside an LLM call measured
in seconds that is not a cost worth an index, and two unbuilt optimisations sit
in front of one anyway. One of the two has since landed: `_cos` is now a plain
dot product, because both producers already normalise and the two
`np.linalg.norm` calls per comparison were dividing by 1.0 twice — measured
4.4x (4.99 ms → 1.13 ms over 442 real rows), and verified rather than assumed,
with scores agreeing to 8.7e-06 over 8,000 stored vectors and identical top-8,
top-20 and top-60 sets. Stacking rows into one matmul (~20x) is still unbuilt;
see `docs/UNBUILT.md`.

Read that table carefully: it is **per character**, at the measured growth of
~3.5 rows per turn *per character*. 200,000 rows is one character with roughly
57,000 turns of their own, not a chat total. Banks are disjoint by `char_id`
and character steps run in parallel (`agents/runtime._stream_parallel`), so a
four-character chat holding 200,000 memories gives each mind ~50,000 rows
scanned concurrently — better than the 2.2 s figure, not worse. What does not
divide is CPU: four concurrent NumPy scans still contend for cores, and NumPy
only releases the GIL for the larger operations.

So the accurate claim is **no ANN index is justified under present workloads or
architecture**, not that the question is closed forever. If it ever reopens,
the answer is more likely to be per-character matrix caches, hot/cold tiers,
summary-first candidate narrowing, or frame-partitioned banks than a global
index — all of which keep the pre-ranking filters that a global index cannot.

---

## 11. Neighbours in the same module

`memory.py` also owns lore and relationships, which are *not* character memory
and follow different rules:

- **Lorebooks** — `resolve_lorebook_graph`, `search_lore`,
  `knowledge_for_character`. World knowledge gated by `access_tags`
  (`common`/`scholarly`/`esoteric`), range (`local`/`global`), and room. Books
  form a tree with inheritance modes and typed links.
- **Relationships** — `RelationshipGraph` on a `world` KV blob, updated from
  explicit director output and from inference. Stance axes are event-linked but
  the link is optional and there is no change log (`Design.md` records this as
  **Partial**).
- **Host-facing feeds** — `dramatic_irony_feed` (what the player knows that a
  character does not), `promise_ledger`.

---

## 12. Current state and known gaps

The live corpus, as of 2026-08-03: **6,463 memories across 37 chats**, all on
`openrouter:3:perplexity/pplx-embed-v1-4b` — 2,601 episodes, 2,400 inferences,
1,312 self, 145 dialogue, 5 promises; 115 archived; 105 autobiographical
summaries, 51 surmise, 38 hearsay.

Every corpus figure in this document is a snapshot and goes stale the moment
anyone plays a turn. Three separate ratios in here disagreed with each other
before this pass, each correct on the day it was written. Treat a number as
evidence for the SHAPE of a claim (dialogue is rare relative to episodes) and
re-count before quoting it as a fact.

Open, and tracked in [`docs/UNBUILT.md`](../UNBUILT.md):

- **§1.15** the rebuild story above, now marked SUPERSEDED for its premise: a
  real provider is configured and the whole bank is on it, so the split-era
  scenario is no longer hypothetical. The remaining gap is announcement: a host
  is told their bank is split when they open a story or open the settings
  panel, not at startup.
- **§1.16** greeting knowledge seeds enter memory at salience 1.00 in third
  person, never age out (the archive threshold is 0.72), and grow *more* likely
  to intrude unbidden as a story lengthens.

Raised in review and now built (§13 has the mechanics):

- **A witnessed memory's interpretation can be revised** — `record_dispute`,
  recorded beside the memory, never over it.
- **Salience split in two** — `salience` (when formed) and `importance` (what
  it became), consequence-driven and explicitly not access-driven.
- **Dialogue durability is no longer only a phrase list** — a character marks
  its own keepers with `remember_lines`.

Raised in review and still open:

- **Unbidden recall has one mode where it should have several.**
  `contrast_memory` maximises dissimilarity, which is faithful to SIGMA
  SRIP-14 §XXII — but that spec is about breaking convergence in a *reasoning
  system*, not about modelling involuntary memory, and involuntary recall in
  people is usually cue *similarity*. Contrast is right as an anti-stagnation
  mechanism; it wants siblings — echo (structurally or affectively similar),
  unfinished (tied to an open concern), identity (challenges the self-concept),
  intrusion (highly charged despite low relevance).
- **Hierarchical summary retrieval** — storage, retrieval, earlier chapters,
  drift-triggered origin retrieval, leading-era repair and checkpoint
  propagation have landed (§8). What remains is bounded interior-hole repair
  for legacy banks and evidence-traceable summaries; see `docs/UNBUILT.md`
  §2.17.

### Sense as a retrieval channel — built, measured, reverted

**Do sight, scent and sound work as cues?** Yes, through prose, and adding
machinery for them did not measurably help. Recorded here because the idea is
an obvious one to have twice.

What is true today: there is **no modality anywhere in memory** — no column, no
tag — and `sensory_events` never reach `commit.py` at all. They are read in one
place, the *establishment* path in `agents/perception.py`, and folded into view
prose. The structured channel is also thin and unnormalised: across the live
corpus the Director emitted 26 `smell` events under a `kind` vocabulary that
also contains `olfactory`, `audio`, `ambient_sound`, `visual`, `sight` and
`light` as separate values, on 48 of 400 outputs. Meanwhile **715 of 4,953
memories carry scent language in their text**. So a smell is words in an
episode, the episode's words are the query, and cosine does the rest.

Two additions were built to sharpen that and then removed:

1. **Sense clauses as their own retrieval aspects** ("what you can smell"),
   on the reasoning that a short facet cannot compete inside a ~1,015-character
   query — the argument that justified the mood/goal aspects.
2. **Sense clauses folded into `key_phrases`** at mint, so a one-off scent
   reaches the cue vector, FTS and exact-match instead of being dropped by
   frequency ranking.

Measured on six scent pairs, each a memory queried by a **vocabulary-disjoint**
description of the same smell inside an otherwise-unrelated view, against
decoys sharing the view's surface language:

| | mean rank | recall@1 | recall@3 |
|---|---|---|---|
| unchanged engine | 2.83 | 0/6 | 6/6 |
| + `key_phrases` | 2.67 | 0/6 | 6/6 |
| + sense aspects | 2.67 | 0/6 | 6/6 |

Ranks were **identical pair-for-pair** with and without the aspects. Both
additions were reverted.

**Why the aspect did nothing, which is the part worth keeping.** RRF
contributes `weight * 12 / (60 + rank)`. At the aspect weight of 0.55 that is
0.108 at rank 1 and 0.107 at rank 2 — **the discrimination between rank 1 and
rank 6 of an aspect ranking is 0.008**, against a flat 0.09 for the
`location` bonus and up to 0.08 for salience. An aspect ranking adds an almost
uniform ~0.10 to every candidate and separates them by less than a hundredth.
**This does NOT generalise to the existing mood, goal and unresolved-thread
aspects, and an earlier revision of this section wrongly said it did.** The
sentence removed here read "no measurement has ever shown them reordering
anything"; that was true only in the sense that nobody had looked. Measured
since, replaying the real fusion over five real banks with real vectors, 40
trials, three aspects each, comparing the top-16 with the aspect rankings on
and off:

| | |
|---|---|
| trials where the top-16 ORDER changed | 39 / 40 |
| trials where top-16 MEMBERSHIP changed | 39 / 40 |
| memories swapped into the top-16 by aspects | mean 4.50, max 8 |

Aspects reorder nearly every retrieval and replace about a quarter of what the
character is handed.

The arithmetic above is not wrong; the inference from it was. **The
discriminating quantity is presence versus absence in an aspect's list, not
rank within it.** Appearing anywhere in the top-60 of an aspect is worth
0.09–0.11; not appearing is worth zero. Three aspects therefore contribute up
to ~0.33 of separation against a ~0.4 bonus band — while the intra-list
separation that ~0.008 measures is, correctly, almost nothing. A near-uniform
bonus applied to a SELECTED SUBSET is a set-membership signal, and reading it
as a ranking signal is what made it look decorative.

Why the scent experiment still came out flat is then a different fact about
that experiment: its decoys were engineered to share the query's wording, so
they were in the aspect's list too. When every candidate is a member, a
membership signal has nothing to separate.

**The reframe that settles it.** The right question was never "does a scent
memory beat decoys engineered to share the query's wording" but "does it
surface at all". At rank 2–3 of 6 with no help, against adversarial decoys, in
a real bank of hundreds it is already comfortably retrieved. The prose channel
works.

If it ever needs to be sharper, the shape that would work is the one `location`
already uses: a **flat scalar bonus** on a stored per-memory sense vector, not
another RRF list. That costs a column and an embedding per memory, and should
not be spent until something in play actually asks for it.

Not in the register, and true:

- **Summary retrieval needed windows before it could be ranked.** *Landed —
  schema v23 and `earlier_in_my_life`; see §8.* Kept here for the shape of the
  argument, which was right about the problem and wrong about the cost. It
  predicted the consolidation cursor as the risk and expected the fix to need
  `save_memory_summary` rewritten to append: in the event, consolidation was
  **already** computing correct bounded windows and the constraint was
  destroying each one on the next write, so completing the key was the whole
  change and the cursor kept working untouched. What the entry did not
  anticipate is that the destroyed windows were never coming back — 53 of 67
  banks have no summary over their opening turns.

  The half it describes that is still unbuilt is the one it mentions in
  passing: using a window's turn range to **narrow which raw memories to
  pull**. Today the windows travel beside raw recall rather than steering it.
- **Provenance can still blur inside a scope.** The three scopes are separate
  rows, which a model cannot collapse; but within the first-hand paragraph the
  model's prose can still lose which specific memory a clause came from.
- **`access_count` / `last_accessed` are written and never read.** Nothing
  ranks on how often a memory has been recalled.
- **Salience is never revised.** It is set at mint by a 15-word keyword rule
  and a length term, and that number governs archiving and unbidden recall for
  the life of the story. Only `confidence` moves.

While writing this document two UNBUILT entries were found already landed and
deleted from the register per the repo's own rule: §1.9 (consolidation flattens
provenance — P8 shipped as the three scopes in §1) and §3.7a (unbidden recall
avoids embeddings — shipped as the gated semantic axis in §6). Both now have
`Design.md` conformance rows instead.

---

## 13. Importance, disputes, and what a character chooses to keep

Three additions from the alpha 6.4.1 review. All three default to the previous
behaviour, so a bank that has never been touched behaves exactly as it did.

### `salience` and `importance` are different questions

`salience` answers *how much did this matter when it happened* — set at mint by
`_salience_of`, never revised, and still what consolidation reads. `importance`
answers *how central did it turn out to be*. `NULL` means never revised and
reads as the salience (`effective_importance`), which is the only place that
fallback is decided.

Two consequences move it, and **retrieval is not one of them**. A memory that
got recalled would rank higher and get recalled more, which is a popularity
loop wearing the word "importance" — and it is why `access_count` staying
written-and-unread is correct rather than an oversight.

- **It was load-bearing.** `_cited_memory_ids` reads three signals: evidence
  on a mind-model update, evidence on a belief update, and a `memory_effects`
  entry with disposition `integrated` — the character stating that a recalled
  memory changed their recognition, appraisal, choice or speech. All are
  downstream of retrieval, so the loop is closed structurally instead:
  `only_unrevised=True` lifts a given row exactly once, ever. Bare
  `memory_evidence_used` deliberately does not count — citing a memory while
  describing the beat is not building anything on it — and `resisted` /
  `dismissed` effects do not either, because a memory the character pushed away
  influenced the beat without turning out to matter.

  It read only the first of those three until 2026-08-03, and that is why
  importance had been revised on 9 memories out of 6,480. Measured over the 83
  results that could supply any candidate: mind-model evidence citing a stored
  memory 6, belief evidence 1, `memory_effects` **74**. The one field being
  read was the rarest thing a character emits, and the field that says exactly
  what the function is looking for fires on 89% of eligible beats. Second time
  this function has been wrong the same way — its first version required a
  numeric row id and matched nothing at all, because characters cite
  `event:<hash>`.
- **The character re-read it** (below), which moves it further, because being
  wrong about something is a bigger fact about it than using it once.

Raises are asymptotic — each closes a fraction of the distance to a 0.97
ceiling — so repetition cannot run away. `raise_importance` takes `chat_id` and
`char_id` and applies them in the `WHERE` clause: the ids arrive from model
output, and ownership belongs in the query rather than in whoever remembers to
check first.

Downstream, ranking's salience term reads `effective_importance`, contrast's
floor reads it, and **archiving reads the higher of the two** — a memory that
turned out to matter is not retired on the strength of how ordinary it looked
at the time, which is the entire reason the numbers are separate.

### A memory can be re-read without being rewritten

`reconcile_inference_confidence` moves what a mind *concluded*. But this engine
exists so a character can be deceived, and when they learn the face was a
disguise, the memory of seeing it stays true while its meaning does not.

`record_dispute` writes `{turn_idx, reading, count}` to the row's `disputed`
column. The memory itself — `content`, `gist`, `provenance`, `salience`,
`valence` — is untouched. `build_character_memory_context` hands the memory over
unchanged with the revision beside it under `i_now_read_this_differently`, so
the character holds both: they still remember seeing what they saw, and they
remember having since decided it meant something else. Collapsing the two would
either erase the experience or hide the correction.

**A column, not an edge to the superseding memory.** Checkpoint restore is
delete-and-reinsert, so every row id changes; an id-keyed edge would be
shredded by the first rollback. Stored on the row it rides the existing
dump/restore round-trip verbatim.

Disputes address an exact delivered stable `memory_ref` and require current
evidence for the new reading. Gist matching remains only as a compatibility
path for legacy output and is accepted only when it resolves unambiguously
inside the character's **own** bank.

**It had fired zero times in production** — 0 of the 181 beats whose stored
result carried the field, beside `remember_lines`, introduced in the same
commit, on the same 181 results, firing 78%. `tests/test_dispute_reachability.py`
settles which of the two explanations that is by building the occasion the
corpus never produced (a stranger remembered as kind, seen this beat picking a
pocket) and walking a model-shaped dispute through every stage: schema
coercion, citation grounding, the commit collector, `record_dispute`, and the
projection back to the mind. Every stage holds. So the wire is intact and
nobody in these stories has been deceived — a doctor and a fox spirit having
dinner give a mind nothing to re-read.

The prompt was the other half of it. The instruction was two prohibitions and
one abstract permission, next to `memory_effects` — which fires 89% and names
four concrete occasions. CLAUDE.md records the same shape twice from the maze
arms: bare prohibitions invert. It now names five occasions (a disguise, a
staged kindness, a lie, the wrong person, an arranged scene) and keeps both
constraints. Whether that changes the rate is a question for
`tools/fire_rates.py` after the next few stories, not for an argument.

### The character decides what was worth hearing

`_durable_dialogue_category` is a fixed phrase list — promises, "my name is", a
few confessions — which is why the corpus holds 145 dialogue rows against 2,601
episodes. Warnings, instructions, codes, indirect threats and newly established
facts all fail it. Each marker must begin at a word boundary (inflections
still match): bare substring matching had filed "compromised" as a promise,
and 3 of the corpus's 5 promise rows were that one word.

Measured (`tools/remember_lines.py`, 1,633 turns, 146 marks): **0 of the 125
marks that became rows would have been caught by the phrase list**, and marked
lines are retrieved later at 30.4% against 9.3% for every non-dialogue row. The
two mechanisms have no overlap at all, and what the character keeps is what
comes back. A budget or novelty gate was considered and refused on those
numbers — it would throttle the highest-yield rows in the bank. `why` is
present on 146 of 146 marks, so it cannot predict anything; a constant is not a
signal.

`CharacterOutput.remember_lines` lets the mind add to that floor (never remove
from it — the floor exists for the model that declares nothing). Commit has
already proved the quote was said this beat and reached *this observer's view*
before the mark is consulted, so a mark can only ever preserve something the
character genuinely heard, never invent one. The mark now carries current
evidence, and its `why` is retained in `emotional_context` rather than being
discarded after it opened the gate.

That makes memory formation psychology-dependent, which is the point: one mind
keeps an insult another shrugs off.

### Retrieval is not influence

`memory_effects [{memory_ref,use,disposition,changed}]` records when delivered
past actually changed recognition, appraisal, choice, or speech. Merely being
retrieved is not an effect. The field accumulates across micro-rounds and is
grounded to delivered raw memories. Unbidden recall uses it as the preferred
"helped" signal, falling back to goal/stuck-state movement for older model
outputs. This is telemetry in the character step and its existing bounded
unbidden ledger; it does not strengthen the memory.

### Summary support sets — per-clause provenance

A summary is the one thing that reaches a character with no provenance at all.
`memory_effects` is grounded to raw rows, beliefs cite evidence, disputes need
a delivered ref — a consolidator sentence arrives as prose and is read as true.
Summaries are barred from reinforcing durable belief, which contains most of
the danger, and they still move appraisal and speech, and they used to leave no
trace when they did.

`memory_summaries.support` (schema v25) records one entry per clause:

```json
{"claim": "...", "support_refs": ["event:aa"], "epistemic_origin": "what_i_experienced"}
```

`derive_summary_support` builds it host-side at consolidation from the window's
own memories, by content-word overlap at a floor of three shared words —
calibrated, not guessed: at two, every clause matched every memory in its own
window. Deliberately **not** a model call and not embeddings: the question is
"which stored rows does this sentence actually talk about", which has a
checkable answer, and an audit trail produced by the same kind of process it
audits is not one.

Three properties:

- **Scoped to the summary's own epistemic class.** A first-hand clause
  supported by something the character was only told would be an audit trail
  that launders hearsay into experience. `epistemic_origin` names the class of
  the strongest supporter, and is left blank rather than defaulted when there
  is none — the safest wrong answer is the one that claims the least.
- **An empty `support_refs` is the finding, not a failure.** It means the
  clause generalises, compresses several rows, or was invented. This does not
  try to tell those apart, because that is a judgement and this is a
  measurement. What changed is that the clause is countable.
- **Refs are `event_key`s, never row ids** — restore is delete-and-reinsert, so
  an id-keyed trail would be shredded by the first rollback. Same reasoning as
  disputes.

Existing rows keep `'[]'`, which means "never derived" rather than "nothing
supports it"; the two are unknowable after the fact, because consolidation has
already archived the window.

### Schema-change checklist

Both columns are carried by `dump_chat_memories` / `prepare_chat_memory_restore`
(checkpoints and branches), `dump_character_memories` /
`import_character_memories` (portable character banks), and
`chat_archive.py`'s import. Importance/dispute migration is v20→v21;
before/after affect is v23→v24. Both are additive. `NULL` importance reads as
salience, empty dispute is undisputed, and old encoding axes remain neutral
instead of fabricating a retrospective emotional change.

`memory_summaries.support` is v24→v25, additive, and carried by
`dump_memory_summaries` / `apply_memory_summary_restore` — which is every path
summaries travel, since checkpoints and `chat_archive.py` both go through
them. Because its refs are `event_key`s rather than row ids, branch and clone
need no remapping.
