# Memory

How a character remembers: what gets written, what comes back, and what
decides. Every claim here is against source — `memory.py` (3,133 lines),
`commit.py`'s memory domain, `agents/character.py`'s retrieval seam, and
`providers.py`'s embedding role.

Memory is **per character**, never per chat. There is no shared pool a mind can
read from. `memories.char_id` is on every row and every read path filters on it
before ranking, which is what makes the firewall a property of the query rather
than a rule the retrieval code is asked to respect.

Related: [`docs/DATABASE.md`](DATABASE.md) for the schema-change checklist,
[`docs/PIPELINE.md`](PIPELINE.md) for where in a turn this runs,
[`docs/RESEARCH.md`](RESEARCH.md) §1.3–1.5 for the retrieval literature and why
there is no vector index.

---

## 1. The shape of a memory

One row in `memories` (`db.py`). The fields that do work:

| Field | What it is |
|---|---|
| `char_id` | Whose memory. The firewall's primary key. |
| `turn_idx` | Global play order. `NULL` for imported/authored memories with no place in play. |
| `frame_id` | Which temporal era it was formed in. `NULL` is the present. |
| `kind` | `episodic` / `dialogue` / `inference` / `semantic` / `relationship` / `promise` / `intention` |
| `category` | Derived from `kind` via `_default_category`; one of `MEMORY_CATEGORIES`. `episode`, `self` and `inference` are essentially all of it in practice — 4,920 of 4,939 live rows. |
| `provenance` | `witnessed` / `heard` / `told` / `read` / `inferred` / `remembered` |
| `salience` | How much it mattered when formed. Drives archiving, unbidden recall, and a ranking term. Never revised. |
| `confidence` | How much the character credits it *now*. Revised every turn for inferences (§7). |
| `content` | The full text. |
| `gist` | First sentences up to 240 chars (`_gist`), or model-supplied. |
| `key_phrases`, `entities` | Extracted at mint (`_extract_key_phrases`, `_extract_entities`) unless supplied. JSON arrays. |
| `location` | Room name. A retrieval cue (§5). |
| `valence`, `arousal` | The affect the character carried *into* the event. |
| `embedding`, `cue_embedding` | Two float32 blobs (§4). |
| `embedding_model`, `embedding_dim` | Which model made them. A mismatch scores 0.0 forever (§8). |
| `archived` | Folded into a summary and retired from the default read. |
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

**Own acts** — `category: self`, `provenance: remembered`, content `"I chose to
…"`. Written only when the character's declaration had salience ≥ 0.7 or
contained speech.

**Dialogue** — `provenance: heard`, salience 0.82, or 0.9 for a promise. Gated
hard by `_durable_dialogue_category`: only quotes containing a promise marker
(`"i swear"`, `"i vow"`, `"you have my word"`) or an identity/confession marker
(`"my name is"`, `"i confess"`, `"i killed"`, `"i love you"`). Everything else
spoken lives in the episode memory and nowhere else. This is why the live
corpus has 15 dialogue rows against 2,028 episodes — by design, not by defect.

The speaker's name passes through a **recognition gate**. If the hearer's
`known` map does not contain the speaker, the memory stores
`_unknown_actor_label`'s appearance-based description instead — and if there is
no appearance to describe, `"a voice"` rather than `"the unfamiliar person"`,
because a heard line is no evidence the hearer saw a body. `intended_target` is
dropped in that case too, since it names the speaker.

**Inference** — one row per mind-model update. `provenance: inferred`,
`salience: 0.45 + 0.3 * confidence`. That formula is load-bearing: it is how
`_mint_confidence_of` recovers the original confidence later without a second
column (§7).

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
working_memory:            event_id "current", current_perception, mood, goal,
                           active_concerns (≤6)
recent_episodes:           recent_memory_buffer — last 4 turns, ≤12 rows
recalled_old_memories:     search_memories, k=16, minus anything already recent
autobiographical_summary:  first-hand only
summary_key_phrases, unresolved_threads
what_i_was_told:           hearsay summary, if any
what_i_concluded:          surmise summary, if any
surfaces_unbidden:         one contrast memory, when triggered (§6)
```

`working_memory.event_id` is the literal string `"current"`. It exists because
`recent_memory_buffer` excludes the current turn, so every real id in the
payload belongs to an earlier turn — a character asked to cite evidence could
only ever cite the past, and did: across one 61-turn chat, `observations_used`
cited a previous turn 15 times and the current beat zero times. That is why the
character kept answering the line before the one just spoken.

### Two hard filters, applied before any ranking

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

Both filters run in `search_memories`, `contrast_memory`,
`recent_memory_buffer`, `list_memories` and `consolidate_character_memory` —
every read path, not a shared wrapper. That is duplication, and it is the
reason a new read path cannot forget.

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
+0.08 * salience
+0.04 * confidence
+0.10 * (confidence - 0.5)     inference rows only, signed around 0.5
+0.08 * exact_cue_score
+0.05 * mood_axis * valence    mood congruence
+0.12 * age  or  (1 - age)     only if the query carries a temporal cue
+0.09                          memory's location == where you are
+0.05                          memory's location is visible from here
+0.10                          promise category, when the query says "promise"
```

**Belief weighting** is signed around 0.5 so a held belief is promoted and an
abandoned one demoted, and it is in the same band as salience rather than
larger — it should break a tie between competing inferences, not outrank an
actual semantic match. It carries a `retrieval_reason` either way: *"belief the
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
Source* — see [`docs/RESEARCH.md`](RESEARCH.md) §1.5 for what carries over and
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
run outside the present frame: a singleton per-character summary has nowhere to
put "as of the present era" versus "as of the flash-forward", and consolidating
outside the present would permanently blend eras with no way to un-blend them.
A frame visited away from the present just accumulates raw memories until play
returns.

`frame_id` is passed **explicitly** rather than read from the ambient
contextvar, because the real caller runs each character on a
`ThreadPoolExecutor` worker, and that does not propagate contextvars.

`consolidate_character_memory` sends only memories **after** the previous
summary's `end_turn_idx` — the earlier ones are already folded in, and re-sending
them made the payload grow without bound across a long chat. It writes one
`memory_summaries` row per scope. The first-hand row is written unconditionally,
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
saved states. A checkpoint stores each vector verbatim so restoring one never
re-embeds a bank — which means a checkpoint written *before* a rebuild holds
the old vectors, and rolling back silently undoes the rebuild. Measured live:
one reroll put **637 of 642 rows** back on the crc32 fallback.

It **re-embeds nothing**. A vector is a pure function of content, and the same
memory appears in dozens of checkpoints unchanged — one chat held 40,224 memory
copies across its checkpoints and only 526 distinct by content, 90.7% of which
already had a rebuilt vector in the live table. So the fix is substitution:
look each saved memory up by `(char_id, sha1(normalised content))` and write in
the vector already earned. A saved row with no live match is left exactly as it
was, never blanked and never guessed at. A blob is rewritten only after
re-parsing to prove it is still valid JSON with the same row count. `dry_run`
is the default.

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
Two reasons, and the first is the real one:

**The filters that matter run before ranking.** A mind may not retrieve how the
turn it is deciding turned out, and may not see another frame's memories. Both
are per-query predicates over `turn_idx` and `frame_id`. An approximate-nearest-
neighbour index cannot apply them cheaply before its search — it would return
neighbours and let the filters cut them afterwards, which changes *how many*
results survive rather than *which* are best.

**And the scan is cheaper than the problem.** Measured: 126 ms at 3,500
memories, 709 ms at 35,000, 2.2 s at 200,000 — a novel series in one chat.
Beside an LLM call measured in seconds that is not a cost worth an index, and
two unbuilt optimisations sit in front of one anyway (`_cos` recomputes norms
although every stored vector is already normalised; stacking rows into one
matmul is ~20x). See `docs/UNBUILT.md`. The question is settled permanently,
not provisionally.

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

The live corpus: **4,939 memories across 34 chats**, all on
`openrouter:3:perplexity/pplx-embed-v1-4b` — 2,028 episodes, 1,873 inferences,
1,019 self, 15 dialogue, 4 promises; 115 archived; 48 autobiographical
summaries, 5 surmise, 1 hearsay.

Open, and tracked in [`docs/UNBUILT.md`](UNBUILT.md):

- **§1.15** the rebuild story above. The remaining gap is announcement: a host
  is told their bank is split when they open a story or open the settings
  panel, not at startup.
- **§1.16** greeting knowledge seeds enter memory at salience 1.00 in third
  person, never age out (the archive threshold is 0.72), and grow *more* likely
  to intrude unbidden as a story lengthens.

Not in the register, and true:

- **Relevance-ranked summary retrieval is unwired.** `memory_summaries` carries
  an `embedding` column, and only the rebuild paths read it. Summaries reach a
  character as whole strings — there is no ranking across them.
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
