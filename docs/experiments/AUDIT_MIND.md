# Audit: the `mind/` package, read whole

Working notes in the register of
[`AUDIT_DIRECTOR.md`](AUDIT_DIRECTOR.md) and
[`AUDIT_SPATIAL.md`](AUDIT_SPATIAL.md): every line of the six files read end
to end, findings written down and not fixed, then each module's behaviour
checked against `Design.md`, `AGENTS.md`, `docs/guides/MEMORY.md` and the two
design notes that argue for this subsystem.

**Baseline:** working tree at `4f33b17` (2026-08-18), `mind/` at 9,253 lines:

| file | lines |
| --- | --- |
| `mind/memory.py` | 5,496 |
| `mind/affect.py` | 2,186 |
| `mind/theory_of_mind.py` | 703 |
| `mind/psychology_runtime.py` | 502 |
| `mind/canon_provenance.py` | 360 |
| `mind/__init__.py` | 6 |

**Nothing in this audit was changed.** No source file was edited, no test was
run, `docs/UNBUILT.md` was not touched. Every measurement below was taken from
the owner's live `engine.db` opened `file:engine.db?mode=ro`.

**"No caller" means** `grep -rn --include=*.py -w <name> .` over the whole
repository returned nothing outside the defining module and `tests/`. Where
that is the claim, the count is given.

---

## Part 1 — findings. FLAGGED, NOT FIXED.

Ordered by how much of the engine's own stated contract they cost, not by
size.

### 1. `belief_credence` and the merge it exists to mirror stopped using the same matcher — 33 of 3,593 live inference memories take their confidence from the wrong belief

`mind/theory_of_mind.py:542`:

```python
        sim = claim_similarity(claim, str(hyp.get("claim") or ""))
```

against `mind/theory_of_mind.py:368-369`, the merge path:

```python
            sim = claim_similarity(claim, str(hyps[i].get("claim") or ""),
                                   ignore=about)
```

`belief_credence`'s own docstring (`theory_of_mind.py:527-530`) states the
invariant it is now breaking:

> Returns the decay-adjusted confidence of the best-matching hypothesis above
> `_SIMILARITY_THRESHOLD` — **the same threshold and the same matcher the
> merge itself uses, so a memory and a hypothesis are judged "the same belief"
> by one rule rather than two that can drift apart.**

The `ignore` parameter was added to `claim_similarity` precisely to stop a
claim's SUBJECT tokens inflating every same-subject pair toward a match; its
docstring (`theory_of_mind.py:213-224`) gives the measured cases — *"Chamber
0505 has a toppled bench"* against *"Chamber 0505 is empty and swept"*, and
*"Vorne is afraid"* against *"Vorne wants to leave"*. `apply_mind_model_updates`
was updated to pass it. `belief_credence` was not, so the two rules did exactly
what the docstring says they must not.

Worked, with the docstring's own example: `_tokens("Vorne is afraid")` is
`{vorne, afraid}`, `_tokens("Vorne wants to leave")` is `{vorne, wants,
leave}`; overlap 1 over `min(2,3)` = **0.5**, above `_SIMILARITY_THRESHOLD`
(0.4), so it MATCHES. With `ignore="Vorne"` it is 0.0 and does not.

This matters because `belief_credence` has two live consumers and both ask a
question whose answer moves durable state:

* `memory.reconcile_inference_confidence` (`mind/memory.py:5484-5486`) re-anchors
  every inference memory's `confidence` to it every turn, and `search_memories`
  ranks on that confidence (`memory.py:2064`);
* `world/place_purpose.py:386` and `:412` re-ask a `told` afford's `sureness`
  from it, and drop the afford outright when it returns `None`.

The inference path is the worse of the two, because commit mints the row's
`gist` as the bare claim and its `entities[0]` as the subject
(`persist/commit_memory.py:734-735`), and the claim routinely *begins with the
subject's name* — the prefix logic at `commit_memory.py:723-724` exists
because of it. So the subject tokens are inside the very string being compared.

**Measured, live corpus, read-only:** 3,593 inference memories across 72 banks
that carry `mind_models`. Replaying both matchers over every row:

| | rows |
| --- | --- |
| matched hypothesis identical under both | 3,560 |
| **today matches a hypothesis the merge matcher would reject** | **27** |
| **today matches a DIFFERENT hypothesis than the merge matcher** | **6** |

0.9% of the bank, and the 27 are the sharper half: those rows are currently
being held at a live hypothesis's confidence when they should be falling
through to `_abandoned_confidence`. A sample of what it looks like — a
memory whose gist is *"Her name is Hinami"* is currently anchored to the
hypothesis *"Hinami has a familial or maternal figure called 'Kaa Sama' who
taught her to cook…"* at similarity 0.5, purely on the shared token `hinami`.
Under the merge matcher it anchors to *"Answered 'I'm a Hinami' — treats her
name as a category…"* at 1.0, which is the belief it is actually about.

A further 75 rows pick the same hypothesis at a different similarity score;
those are harmless, because the returned value is the hypothesis's live
confidence and not the similarity.

### 2. The card field labelled "Protected beliefs" is read by nothing

`story/character_schema.py:307-311` normalises
`psychology.self_model.protected_beliefs` as a string list.
`static/js/editors.js:289` gives it a labelled editor field
(`fLineList("Protected beliefs", …)`) and `:511` writes it back. It rides
every archive, branch and checkpoint, and reaches the model inside the
psychology block.

The only thing anywhere in the engine that grants protected-belief inertia is
`mind/psychology_runtime.py:378`:

```python
                step = 0.05 if item.get("protected") else 0.15
```

`item` there comes from `_authored_beliefs` (`psychology_runtime.py:327-332`),
which reads `self_model["beliefs"]` — a list of `BeliefProfile`
(`character_schema.py:172-175`) carrying its own `protected: bool`.
`protected_beliefs` is never consulted: `grep -rn -w protected_beliefs`
returns six hits, all schema defaults, plus two editor lines. Zero readers.

So an author who types a belief into the field named "Protected beliefs" gets
a belief with **no** inertia — it weakens at the ordinary 0.15 step like any
other — while the field that actually does the work is a `protected`
checkbox on a different list. This is exactly the failure shape `CLAUDE.md`
records as the worst one in this subsystem: the field does not error, does not
warn, does not appear in a test, and surfaces fifty beats later as a character
whose core conviction eroded for no visible reason.
`importers.character_import_warnings` does not name it either.

`Design.md:171` lists "protected beliefs" among what
`mind/psychology_runtime.py` builds. That is true of the flag and false of the
field the UI calls by that name.

### 3. The 20-belief cap silently resurrects an evicted authored belief at its card confidence

`mind/psychology_runtime.py:391`:

```python
    return result[-20:]
```

`apply_belief_updates` rebuilds `result` from the stored ledger in order, then
appends any authored belief whose text is not already present
(`:342-352`), then applies the turn's updates in place. Because order is
preserved across turns, the slice trims from the FRONT — the oldest entries,
which is where a belief seeded on turn 1 lives forever.

The moment an authored belief is trimmed, the next turn's
`_authored_beliefs` pass does not find its key in `by_text` and re-adds it
with `{**authored, "authored": True, "last_updated_turn": 0,
"last_updated_seconds": 0.0}` — i.e. at the card's confidence and the card's
`protected` flag, discarding every revision the character earned. A belief a
character spent thirty turns weakening comes back at full strength, and the
only trace is that its `last_updated_turn` is 0.

`protected` buys nothing here: the inertia at `:378` scales the weaken STEP,
not eviction, so a protected belief is trimmed exactly like any other.

**Not yet firing:** the largest live belief ledger holds 19 of 20
(measured across 100 `chat_chars` states). One more belief in that bank and it
starts. `apply_association_updates` has the identical shape at
`psychology_runtime.py:437`, with a live maximum of 16.

### 4. Nine hardcoded English word lists in `mind/`, in a language-pack engine with a story-capable Japanese pack — and no `mind.*` key exists for a pack to override them

`AGENTS.md` § Language packs: *"a story-capable pack must cover deterministic
recognition and rendering, never silently fall back to English guards."*
`language_packs/ja/manifest.json` declares `"story": true`.

The mechanism for this already exists and is used by six modules:
`language_runtime.linguistic(module, name)` (`language_runtime/__init__.py:579`),
keyed by module path. The English linguistics card carries exactly six keys —
`agents.common`, `agents.director`, `agents.character`, `agents.narration`,
`agents.composer`, `agents.perception`. There is no `mind.memory`,
`mind.affect` or `mind.theory_of_mind` key, and no file in `mind/` calls
`linguistic()` at all. So the pack has nowhere to put a translation even if
someone wrote one.

The prompt for this audit names one known instance in the salience code
(`persist/commit.py`'s 15-word list). These are its siblings, all inside my
slice:

| where | what it decides |
| --- | --- |
| `theory_of_mind.py:77` `_STOPWORDS` | every `claim_similarity` comparison — belief matching, want dedupe, intent dedupe, the project `satisfied_when` circularity gate, drive-shift coherence, the strain pump damper |
| `theory_of_mind.py:139` `_KIND_CUES` (English regexes) | `effective_kind`, the F8 guard that stops a model buying confidence by mislabelling a claim. On a Japanese story `_inferred_kind` returns `None` on every claim and the guard silently stops existing |
| `affect.py:301` `AFFECT_LEXICON` | `label_matches` / `quadrant_label` / `_undercurrent_label` — whether a self-reported mood contradicts the computed appraisal, i.e. whether an undercurrent is synthesised at all |
| `memory.py:666` `_STOPWORDS` | `_extract_key_phrases`, `_memory_fts_query` |
| `memory.py:677`/`:681` `_OLD_CUES`/`_RECENT_CUES` | `_temporal_mode`, a ±0.12 term in recall ranking |
| `memory.py:744` `blocked` + the `[A-Z][a-z]+` regex at `:742` | `_extract_entities`, which produces the `entities` column — and `entities[0]` is the subject `reconcile_inference_confidence` keys on. Capitalisation-based extraction returns nothing at all for Japanese |
| `memory.py:1771` `_MOOD_VALENCE` | `_mood_axis`, the mood-congruence term |
| `memory.py:2088` the tuple `("promise","promised","swore","vow","agreed")` | a +0.1 promise-category recall bonus |
| `memory.py:2472` `_SUPPORT_STOPWORDS` | `derive_summary_support`, the per-clause audit trail on every summary |
| `memory.py:2851`/`:2856` two mood word lists | `_origin_on_drift`'s mood sign-flip signal |

Two of these deserve separate mention.

**`memory.py:2851` also contradicts its own comment.** Two lines above it
(`:2846-2850`) the code says *"We use the mood label vocabulary the engine
already maintains"* — and then hardcodes a fresh 19-word negative list and a
17-word positive list rather than reading `affect.AFFECT_LEXICON`, which is
the vocabulary the engine already maintains and which disagrees with them
(`AFFECT_LEXICON` has `bored`, `weary`, `lonely`, `numb`; the new lists have
`horror`, `anguish`, `desolate`, `triumphant`, `ecstatic`, `love`). Two
representations of one rule, free to drift, with a comment asserting they are
one.

**The engine already knows how to do this properly, in the same file.**
`memory._empty_view_markers` (`memory.py:3192-3212`) walks
`installed_language_packs()` and adds each pack's `narrator_nothing` template
to its English literals, with a comment explaining that the English-only
version consolidated a Japanese empty view into autobiography. That fix was
applied to one list and not to the nine above it.

### 5. `_relief_impacts` reads an appraisal key nothing writes

`mind/affect.py:799`:

```python
    for extra in (appraisal or {}).get("impacts") or []:
```

`grep -rn '"impacts"' .` over the repository returns exactly one hit: that
line. `appraise` returns `{dV, dA, emotions, dominant, drive_impact}` plus the
extended dimensions (`affect.py:604-624`), never `impacts`, and the sole
production caller passes `appraisal_out` straight through
(`persist/commit_memory.py:982` → `:1004`).

So the "relief clears a standing undercurrent" rule in `resolve_affect`'s
step (d) can only ever see ONE impact — the beat's single highest-weight one.
A confirmed win on the exact goal a dread is `serves`-keyed to does not
dissolve that dread unless it also happened to out-weigh every other impact in
the beat. The list comprehension exists to make relief look at more than the
dominant impact and cannot.

### 6. `LORE_INHERITANCE_MODES` is dead, and four hand-written copies of the vocabulary disagree — including two readers with opposite fallbacks for an unrecognised value

`mind/memory.py:55`:

```python
LORE_INHERITANCE_MODES = ["inherit", "isolated", "reference_only"]
```

Total references in the repository, including tests: **one** — that line.
Every sibling vocabulary in the same block is exported and used
(`LORE_CATEGORIES`, `LOREBOOK_TYPES`, `LOREBOOK_LINK_TYPES`, `KNOWLEDGE_TAGS`,
`KNOWLEDGE_RANGES`, `MEMORY_CATEGORIES`, `MEMORY_PROVENANCE` all reach
`story/importers.py` or `web/app.py`). This one is declared and orphaned.

The vocabulary it declares is then hand-written three more times, differently:

| site | accepts | on anything else |
| --- | --- | --- |
| `persist/commit_mapping.py:136` | `inherit`, `isolated` | coerces to `inherit` — the mapping stage can never create a `reference_only` book |
| `web/app.py:2622-2627` (PUT) | `inherit`, `isolated`, `reference_only` | HTTP 400 |
| `web/app.py:2586` (POST) | anything | stored verbatim — and `book_type` is validated against `LOREBOOK_TYPES` on the line above, so the omission is visible |

And the two readers of the stored column disagree about what an unrecognised
value means:

* `memory._inheriting_ancestors:391` — `if (row["inheritance_mode"] or
  "inherit") != "inherit": break`. Anything unrecognised **severs** the
  ancestor chain.
* `memory.resolve_lorebook_graph:439-443` — only `"isolated"` hides a child,
  only `"reference_only"` decays it to 0.5; anything else takes the `0.95`
  branch and behaves as **inherit**.

So a book stored with a typo'd mode through the POST route inherits downward
and not upward, silently, and nothing validates it on the way in.

### 7. `rebuild_checkpoint_embeddings` has no caller — the defect it repairs is live and both maintained docs describe it as built

`mind/memory.py:5120`, 142 lines. References in the repository: its own
definition, one mention inside another docstring at `memory.py:3553`, and four
lines in `tests/test_embedding_rebuild.py`. No route in `web/app.py`, no entry
in `tools/`, no call from `persist/checkpoints.py`.

`docs/guides/MEMORY.md:946-970` and `Design.md:184` both describe it in detail
as shipped behaviour, including the measurement that motivates it — *"one
reroll put 637 of 642 rows back on the crc32 fallback"* — and the run that
proved it — *"99,442 saved memories repaired across 1,040 checkpoints in 98
seconds and zero API calls"*. That run can only have been made by hand from a
REPL. There is no way for the shipped product to make it.

The consequence is not that rollback is broken: `persist/checkpoints.py:700`
calls `start_rebuild_if_needed(chat_id)` after a restore, so the live table is
re-reconciled. But that reconciliation is `rebuild_embeddings` — a paid,
O(bank) provider walk — where the substitution pass is free and offline.
Every rollback past a migration pays the expensive repair because the cheap one
is unreachable.

### 8. `backfill_lore_embedding_stamps` and `lore_embedding_health` have no caller; 1,160 of 2,586 live lore rows are permanently unstamped

`mind/memory.py:4324` and `:4397`. Callers outside `tests/`: none.

`backfill_lore_embedding_stamps`'s docstring calls itself *"the one-time
retrofit that puts lore into the same reconciliation system `memories` has
always been in — after it, the column carries the answer and nothing ever
hashes a corpus again."* Nothing runs it, so the corpus is never stamped.

**Measured live:** `lore_entries` holds 2,586 rows; 1,426 carry
`embedding_model = 'openrouter:3:perplexity/pplx-embed-v1-4b'` (written by
`add_lore`/`update_lore`, which do stamp) and **1,160 carry NULL** — 45% of
the corpus, every one of them predating the columns.

That matters because both the health count and the repair predicate are
written STAMP-FIRST, WIDTH-ONLY-AS-FALLBACK
(`memory.py:5026-5036`, `memory.py:4880-4890`):

```sql
AND ((embedding_model IS NOT NULL
      AND (embedding_model != ? OR embedding_dim != ?))
  OR (embedding_model IS NULL AND length(embedding) != ?))
```

For 45% of the corpus the stamp branch can never be taken, so those rows are
judged on vector WIDTH alone — the weaker test the comment at `memory.py:5008`
explicitly calls out ("two models sharing a width are indistinguishable"), and
the one `_stamped_live_dimensions`' docstring says inverts the moment a
current model is narrower than a retired one. The design has a strong test and
a weak fallback, and the pass that would move rows from the second to the
first is unreachable.

`lore_embedding_health` is the other half: *"THE QUESTION HAD NO ANSWER BEFORE
THIS… This answers it on demand, per book when asked, so a corpus can be
checked before it is trusted."* Nothing asks.

### 9. `monitoring_subtree` — 75 lines, no caller

`mind/memory.py:585-659`. Seven references: the definition, two comments in
`persist/commit_scene_state.py:60` and `persist/commit_destruction.py:128`
that mention it as a thing that exists, and four lines of
`tests/test_monitoring_scope.py`. No route, no tool, no engine path.

Its docstring says *"Monitoring/reporting ONLY (UI, ops, tests)"*. There is no
UI and there are no ops; the parenthesis is accurate only in its last term.

### 10. `relationship_events` is not the ledger it says it is, and its only reader has no caller

`mind/memory.py:4598` `record_relationship_event` — *"Append one reason a
stance moved. Never updated, never deleted."* — is called from exactly one
place, `apply_relationship_updates` (`memory.py:4700-4706`), which handles the
`explicit` relationship-update path.

The OTHER path, `update_relationships_from_inference` (`memory.py:4684`, live
at `persist/commit_memory_write.py:182`), moves `trust` by up to ±0.15 and
`familiarity` by +0.05 per inference and writes **no ledger row at all**:

```python
        if trust_delta != 0:
            graph.adjust_trust(about, trust_delta, conclusion[:200])
```

`RELATIONSHIP_AXES` (`memory.py:4593`) is commented *"Named here so the ledger
and the scalar graph cannot disagree about what they are called."* They agree
about the names and disagree about the events: an entire class of trust
movement exists in the scalar graph and not in the ledger.

`relationship_history` (`memory.py:4627`), the function whose docstring calls
itself *"the question the scalar graph could never answer"*, has no caller
outside `tests/test_relationship_events.py` — no route, no payload, no tool.
So the incompleteness has never been visible. (341 `relationship_events` rows
exist live.)

Separately, `update_relationships_from_inference` is a tenth English word list
(`memory.py:4694-4697`: `trustworthy / honest / kind / saved / helped` against
`lied / betrayed / deceitful / dangerous / threat`) deciding a durable
relationship axis by substring match on model prose — see finding 4.

### 11. Two docstrings in the drive-rupture family describe a threshold the code stopped using, and an input it stopped reading

`mind/affect.py:1859` (`update_drive_strain`) and `mind/affect.py:1935`
(`detect_drive_rupture`) both say the drive impact is used *"only when that
impact serves the drive and is confirmed (certainty >= `_CERTAINTY_THRESHOLD`)"*
— 0.8.

The code uses `_STRAIN_CERTAINTY_MIN` (0.5) in both places, at
`affect.py:1896` and `affect.py:1953`. The change was deliberate and is
explained at length in the constant's own comment (`affect.py:246-256`: *"the
certainty bar moves"*, with the live observation of a -0.35 contradiction at
certainty 0.7 accruing nothing). Neither docstring was updated, so the two
functions document a gate 60% stricter than the one they run.

`update_drive_strain`'s docstring compounds it: it says the accrual comes from
*"the appraisal's **dominant** impact"*. The code calls `_drive_serving_impact`
(`affect.py:1882`), which prefers `appraise`'s dedicated `drive_impact` and
falls back to `dominant` — and `appraise`'s own comment
(`affect.py:596-601`) records why: a -0.5 drive contradiction was being
discarded because an intention wound out-ranked it by 0.03, *"the exact reason
ruptures never built"*. The fix landed; the sentence describing the bug is
still presented as the contract.

### 12. Three more docstrings frozen at the pre-capacity constants

`psychology.capacity` made the want and intention caps per-character
(`affect.CAPACITY_LADDER`, 1/2 through 5/6). The docstrings did not move:

* `affect.py:1003` — *"Caps to 3"*, in a function whose signature is
  `normalize_wants(wants, valid_intention_ids, *, want_cap=None)`.
* `affect.py:1228` — *"Enforced floors: at most 4 active intentions"*, in
  `apply_intent_ops(..., intent_cap=None, ...)`.
* `affect.py:1236` — *"anything active but untouched for more than 30 turns
  goes dormant"*. That one is still literally true (`_INTENT_DORMANT_AFTER` is
  not on the ladder), but sits in the same sentence as the two that are not,
  which is how a reader concludes all three are constants.

`AGENTS.md`'s capacity row and `Design.md:246` both describe the ladder
correctly; only the module's own docstrings are stale.

### 13. The barren-beat audit is bypassed by rephrasing the goal as an `add`

`mind/affect.py:1265`:

```python
                if _advance_intent(match, turn_idx, warnings):
                    _revive_intent(match)
```

versus `affect.py:1299-1300`, the `progress` branch:

```python
                moved = _advance_intent(target, turn_idx, warnings,
                                        barren_beat=barren_beat)
```

`_advance_intent`'s docstring (`affect.py:1122-1146`) is explicit that the
barren rule was found in play (chat 80, turns 1-3: a psychologist repeating
three propositions while `ia1` went 0.0 → 0.2 → 0.4) and that the caller
supplies the flag *"because the engine has already measured it"*. The
add-rephrase path is a caller and does not supply it.

The comment directly above line 1265 says *"Rephrasing is not a way around a
spent goal: the restatement revives it only if it had somewhere left to go"* —
which closes the CEILING loophole (`_advance_intent` still refuses at
`progress >= 1.0`) and leaves the barren one open. On a beat the engine has
already classified as a repeat, `{"op": "progress", "id": "i1"}` is held at the
old value and warned about, while `{"op": "add", "intent": "<i1 reworded>"}`
gains +0.2 and refreshes `last_progress_turn`, which also postpones the
dormancy sweep. Same beat, same intent, opposite outcome, decided by which op
the model happened to emit.

### 14. `search_memories` writes to the memory bank on the character stage, for a column nothing ranks on — and the sibling that refuses to do so gives a reason that applies to it too

`mind/memory.py:2137`:

```python
        qi(f"UPDATE memories SET access_count=access_count+1, last_accessed=? WHERE id IN ({ph})", (now, *ids))
```

`memory.py:2148-2150`, twelve lines later, on `contrast_memory`:

> it is a pure read -- unlike `search_memories` it must never touch
> `access_count`, **because it runs mid-pipeline at character-stage time**.

Both run mid-pipeline at character-stage time.
`agents/character.py:2594` calls `build_character_memory_context`, which calls
`search_memories` (once, or twice when a ponder is pending) for every character
in the beat. The stated reason for one function's purity is a property the
other function also has.

The column is instrumentation with no ranking consumer — `memory.py:848` says
so outright (*"which is also why `access_count` stays written and unread"*) and
`docs/guides/MEMORY.md:66-68` repeats it. Consequences, all small and all real:

* every character step issues an extra `UPDATE … WHERE id IN (…)` of up to 18
  rows inside the turn's wall clock;
* `tools/salience_replay.py` has to **copy the whole database** before running
  (`salience_replay.py:34`) purely because of this line;
* two author-facing routes mutate the bank as a side effect of reading it —
  `GET …/memories/search` (`web/app.py:4429`) and `GET …/memory-context`
  (`web/app.py:4464`, which additionally runs
  `backfill_missing_memory_event_keys` and its `UPDATE`s). That pollutes
  `tools/remember_lines.py`, which reads `access_count > 0` as the answer to
  *"did it come back"* (`remember_lines.py:158`).

### 15. A `weaken` or `contradict` update on a belief the character does not hold CREATES it

`mind/psychology_runtime.py:365-374`. The `item is None` branch builds a new
belief from the update's own `confidence` and never looks at `operation`:

```python
        if item is None:
            item = {
                "belief": text,
                "confidence": confidence,
                ...
```

`operation` is read only in the else-branch (`:377`). So a character
contradicting a belief they were never recorded as holding is stored as
*holding it*, at the confidence they attached to the contradiction. The list
is keyed on exact case-folded text (`:341`), so a model that weakens a belief
using slightly different words from the stored one mints a second, positive
copy of the belief it was trying to revise.

`theory_of_mind.apply_mind_model_updates` — the sibling layer, one file over
— does not have this shape: an unmatched claim there is a *competing*
hypothesis that suppresses its group rather than an assertion.

### 16. `generalization_tags`: authored on 87 of 152 live associations, written by nothing, read by nothing deterministic

`story/character_schema.py:204` declares it, `static/js/components.js:746-752`
edits it, `mind/psychology_runtime.py:422` initialises it to `[]` on every
association the runtime creates — and no code anywhere reads it. It rides into
the character payload as part of `learned_associations`
(`agents/character.py:2853`), so an authored tag reaches the model as prose;
a tag the runtime could have learned never appears, because
`apply_association_updates` updates `appraisal_bias`, `response_tendency` and
`strength` (`:431-436`) and never touches this field.

The name promises generalisation — the mechanism by which a cue learned in one
situation transfers to a similar one — and there is no engine behind it.
87 of 152 live associations carry tags nothing generalises on.

### 17. `mind/canon_provenance.py`: the function its own docstring calls "the whole safety property" has no caller

Of the module's public surface, only three names are imported by production
code: `is_node_id` (`world/gaps.py:53`), `Subject` (`world/subjects.py:57`) and
`validate_provisional` (`world/offscreen.py:431`). The rest have no caller
outside `tests/`:

| name | line | what it claims |
| --- | --- | --- |
| `may_assert_consequence` | 150 | *"Whether a record at this disposition may change the world. False for the provisional tier, **and that is the whole safety property**."* |
| `is_canon` | 144 | *"True only for a disposition something adjudicated."* |
| `outranks` | 159 | the provisional-loses-to-everything ranking |
| `unavailable` | 178 | the constructor for *"a provisional record saying the thing could not be produced, and why"* |
| `promote` | 340 | deliberately `NotImplementedError` — named seam, fine |
| `ADJUDICATED_DISPOSITIONS` / `KNOWN_DISPOSITIONS` / `BASES` | 49/59/79 | the vocabulary |

The safety property IS enforced, but by `_CONSEQUENCE_KEYS` inside
`validate_provisional` (`:311-315`), which is a different mechanism with a
different name. `may_assert_consequence` is the stated boundary and nothing
asks it. Likewise `world/gaps.py:105` builds its own `basis: "unavailable"`
record through `_record(...)` rather than calling `unavailable()` — two
constructors for one shape, and only the unused one enforces the non-empty
reason (`canon_provenance.py:185-188` raises; `gaps._record` does not).

One stale claim in the same file: `promote`'s docstring
(`canon_provenance.py:346-353`) says *"`settle_claims` sets a status flag in
the world-KV blob and writes nothing into canon. That missing write is 0a's
successor."* `AGENTS.md`'s background-claims row now states the opposite as a
landed invariant — *"ratifying is a WRITE, not a status flag"* — and
`world/background_claims.write_canon` plus `memory.ensure_chat_canon_book`
(`memory.py:4056`) are the write. The docstring describes the defect, not the
code.

### 18. The cross-character read guard has a dead branch, cannot see a private reader, and is evaded by an f-string

`tests/test_memory_read_seam.py:238-271` is the firewall tripwire named in
`AGENTS.md`'s test list. It scans `inspect.getsource(memory)` for top-level
defs whose body contains the literal `"FROM memories"` without `char_id=?`.

Three problems, in ascending order:

```python
        if "m.char_id" in body or "WHERE id=?" in body:
            pass
        offenders.append(name)
```

(`:254-256`) — the `if` is a no-op. Whatever it was meant to do (`continue`,
by shape), it does nothing, and `offenders.append` runs unconditionally.

`:263-264` excludes every name starting with `_`, so a private cross-character
reader is structurally invisible to the check.

And the predicate is the literal string `"FROM memories"`, so any reader that
builds its table name — `repair_pending_embeddings` at `memory.py:1085`
(`f"SELECT * FROM {table} WHERE id IN …"`) and the `embedding_bank_status`
counters at `memory.py:4805` — is never even a candidate. Those two happen to
be maintenance paths, which is luck rather than design: the guard cannot fire
on the shape it would most need to catch, an f-string query added by someone
who did not read this test.

### 19. Two tests assert on the source text of a function nothing calls

`tests/test_embedding_rebuild.py:299-320`:

```python
        src = inspect.getsource(memory.rebuild_checkpoint_embeddings)
        i = src.index("if hit is None:")
        branch = src[i:i + 220]
        assert "memories_unmatched" in branch and "continue" in branch
```

and

```python
        assert "check = json.loads(text)" in src
        assert "!= len(blob.get(\"memories\")" in src
```

A 220-character slice measured from a string literal, and two exact-source
assertions. Both pass green today, both would keep passing if the function
were unreachable — which, per finding 7, it is.

### 20. Two unused imports, and two redundant local re-imports

`mind/memory.py:5` imports `os` and `math`; neither name appears anywhere else
in the 5,496 lines (verified by AST walk plus textual count of 1 each, the
import itself).

`memory.py:4611` (`record_relationship_event`) does `from core.db import qi`
and `memory.py:4633` (`relationship_history`) does `from core.db import q`,
both already imported at module scope on line 8. `restore_lorebook:3977` does
`import hashlib, uuid` where `hashlib` is already a module-level import.

### 21. `_TOM_HALF_LIFE` is documented in turns and measured in minutes whenever the simulation clock advances

`mind/theory_of_mind.py:43-45`:

> `half_life`: **turns** until an unreinforced belief's confidence decays by
> half.

`_elapsed` (`:249-262`) returns `(elapsed_seconds - last_updated_seconds) /
60.0` — minutes — whenever the caller supplies `elapsed_seconds` and the
delta is positive, and only falls back to `turn_idx` arithmetic otherwise.
Commit always supplies it (`persist/commit_memory.py:1392`,
`:1413`), so on any story that advances its simulation clock an
`observation` half-life of 5 is five MINUTES of story time, not five turns; on
a story that does not, it is five turns.

`psychology_runtime.elapsed_psych_units` documents this conversion carefully
for its own layer (*"One unit is one minute"*, `psychology_runtime.py:82`) and
`affect.py`'s half-lives inherit those units through commit's
`elapsed_units`. `theory_of_mind` is the one layer that switches units without
saying so, and its own constant block says the opposite. The same applies to
`decay_affect`'s docstring (`affect.py:672-674`, *"every `half_life` turns"*).

Not a bug — the behaviour is defensible either way — but the constants cannot
be tuned by anyone reading the comment beside them.

### 22. `Relationship.notes` is rendered by the UI and written by nothing

`mind/memory.py:4551` declares `notes: str = ""` on the `Relationship`
dataclass. `static/js/chat.js:2021-2023` reads it as the preferred display
(`r.notes || ("last shift triggered by event " + r.salient_event)`). No engine
path ever passes `notes=` to `graph.update`, so the branch the UI prefers is
dead and every relationship falls to the event-id fallback.

---

## Part 2 — what the code actually does, checked against the documents

Method as in `AUDIT_DIRECTOR.md`: behaviour written from the code, then
compared against `Design.md`'s conformance table, `AGENTS.md`'s routing rows
and invariants, `docs/guides/PIPELINE.md`, `docs/guides/MEMORY.md`, and design
notes `DESIGN_LONG_TERM_GOALS.md` / `DESIGN_PSYCHOLOGY_AS_PRESSURE.md`.
Verdicts: **RIGHT** / **STALE** / **LOST**.

### `mind/psychology_runtime.py` (502 lines)

Five pure functions and one unit converter, no imports at all beyond
`__future__`. `elapsed_psych_units` turns the simulation clock into psych units
(one unit = one minute) and preserves the one-per-turn cadence for stories that
do not use it. `resolve_hedonic` resolves peak-held, fast-decaying `pain` and
`pleasure` levels from a grounded `somatic_impact` (a non-empty `why` is
required or the numbers are discarded outright), floors pain on survival
vitals, floors pleasure on world-side ambient comfort — habituating on a
sustained source and never touching `charge` — and integrates the slow
`charge`, which only the character's declared `released` discharges.
`resolve_stress` splits activation into aversive `strain` (threat, novelty,
low control, low coping, norm violation, memory threat bias, pain) and
non-distressing `drive` (pleasure + charge), keeps `load`/`overloaded`
strain-only, and peak-holds strain separately so last beat's drive is never
re-read as this beat's distress. `cognitive_absorption` is the valence-blind
0..1 figure, convex (`level ** 1.3`), habituating across `sustained_beats`
toward a floor of 0.35, with a saturated floor of 0.45 and a
`0.5 * activation` floor. `apply_belief_updates` / `apply_association_updates`
merge card-authored and lived ledgers under a 20-row cap.

**`Design.md:171` ("Event-grounded live psychology", Built): RIGHT with one
false clause.** Every mechanism it names — strain/drive split, mixed
pain/pleasure outside survival, the slow-integrating charge, learned cue
associations, simulation-time recovery, the ambient-comfort floor that raises
level and never charge — is in the code as described, including the two hard
rules stated in the `_AMBIENT_COMFORT_*` comment. "Protected beliefs" is the
false clause: the `protected` flag is built, the card field of that name is not
(finding 2).

**`AGENTS.md` § Sensation constrains cognition: RIGHT.** The invariant that
consumers must read `cognitive_absorption` and not `strain`, that the figure is
deliberately valence-blind, and that `load`/`overloaded` stay strain-only, all
hold in code and are stated in the docstrings.

**`PIPELINE.md` §`character:<id>`: RIGHT.** "Pain and pleasure are independent
and do not require survival mode" is exactly `resolve_hedonic`'s shape.

### `mind/theory_of_mind.py` (703 lines)

Per-kind caps, plasticities and half-lives; a stopword-stripped overlap-
coefficient similarity with a subset short-circuit; `effective_kind`, which
takes the stricter of the model's declared kind and one inferred from the
claim's own language; `apply_mind_model_updates`, which blends a matched claim
toward new evidence at the kind's plasticity, treats an unmatched one as a
competing hypothesis that partially explains away its same-group siblings,
decays everything unreinforced and prunes below a floor; the absorption
family (`absorbed_cap`, `formation_floor`, `sheet_capacity`,
`due_for_reappraisal`); `select_active_hypotheses`, the 1–5 entry sheet with
`_SHEET_INCUMBENT_MARGIN` hysteresis and `i_suspect` keys; `rekey_place_claims`;
`belief_credence`; `mind_models_for_payload`.

**`AGENTS.md` § "A model-declared `kind` is not trusted": RIGHT in structure,
English-only in fact.** Both entry points do agree on the kind
(`cap_mind_model_updates:111` and `apply_mind_model_updates:349` both call
`effective_kind`), and the arrangement genuinely can only lower confidence.
What the row does not say is that `_inferred_kind` is a list of English regexes
(finding 4), so on a Japanese story the stricter-of-two rule degenerates to
"trust the declared kind".

**`AGENTS.md` § "Belief provenance belongs to the belief": RIGHT.**
`first_seen_turn`, `formed_under` and `reappraised_turn` are carried explicitly
at `:399-402` because `merged` is rebuilt from the incoming update, exactly as
the row warns. `due_for_reappraisal` is called with the character's live
absorption at both sites (`:383` and `:665`).

**`AGENTS.md` § "The stable hypothesis sheet": RIGHT.** Selected at commit
(`commit_memory.py:1408`), read by `agents/character.py`, hysteresis present,
`i_suspect` key present. Live: 32 of 100 banks carry a sheet; 95 sheet entries
carry `formed_under`.

**`AGENTS.md` § "Absorption gates formation, not reinforcement": RIGHT.** Two
ceilings, `formation_cap` and `reinforce_cap` (`:357-358`), with the comment
recording the measured regression (a confirming beat cutting a settled belief
0.6 → 0.37).

**`AGENTS.md` § "Recall follows belief": RIGHT in every clause except the
matcher.** The one-shot idempotent re-anchoring, the held ≥ abandoned floor,
the reconstruction of mint confidence from `salience = 0.45 + 0.3*confidence`,
the refusal to consult the objective record — all present and correct
(`memory.py:5394-5496`). The row says the demotion is keyed on "no surviving
hypothesis carries this claim"; finding 1 is that *which* hypothesis carries it
is decided by a matcher that has drifted from the one that stored it.

**Live fire rates, for the record:** 1,147 stored hypotheses across 100 banks
— goal 414, trait 248, emotion 196, observation 170, stated_fact 65,
second_order 6. 427 carry `formed_under`; **2** carry `reappraised_turn`. The
reappraisal mechanism is built, reachable and firing at 0.5% of eligible
beliefs.

### `mind/affect.py` (2,186 lines)

The largest single body of deterministic psychology in the engine, in six
layers: the OCC appraisal (`appraise`, with the unresolved-drive correction
that withdraws the satisfaction stand-down while a charge stands); mood
dynamics (`blend_affect`, `decay_affect`, the optional surface-habituation
family, and `resolve_affect`, the commit-side orchestrator); wants
(`normalize_wants`); intentions (`apply_intent_ops`, `_advance_intent`,
`steering_intent_ids`); projects (`apply_project_ops`, `settle_probation`,
`projects_served_this_beat`, `project_boundary`, `goal_slot_currency`,
`serves_priority`); drive rupture (`update_drive_strain`,
`detect_drive_rupture`, `validate_drive_shift`, `former_drive_entry`); and two
tail utilities (`leak_scan`, `tell_gate`, `ground_tells`).

**`DESIGN_LONG_TERM_GOALS.md` "Status: v1 built" + the v2/v3/v4 Decided
bullets: RIGHT, clause by clause.** Every named symbol exists and does what the
note says: `PROJECT_CAP = 2`; adoption refused over a full ledger with no
eviction; `displace`/`satisfy` requiring a stated `why`; `satisfy` refused on a
project with no `satisfied_when`; the circularity gate at
`_CRITERION_RESTATES_SIM = 0.4`; probation weighing at 0.8 and lapsing at
`_LAPSE_AFTER = 24`; establishment at ≥3 served beats over ≥12 turns;
`serves_priority` granting drive weight (1.0) to an established project and
0.8 to a probationary one; `project_boundary` detecting arrival, an intention
closing, and a scene/frame change against the persisted `scene_marker`;
`goal_slot_currency`'s word-keyed `goal_since` / `goal_room` /
`goal_room_reached`; `projects_served_this_beat`'s three channels with the
substance channel keyed on room NAMES rather than text similarity. Commit wires
all of it (`persist/commit_memory.py:776-1180`), including the
`_established_ids = _project_ids - _probation_ids` split that keeps the two
weights disjoint.

**`Design.md:182` ("Long-term goals (the project tier)", Built (v4)): the code
is RIGHT and the measurement in the row is now the wrong number.** The row's
diagnosis is confirmed in source — `project_boundary` no longer opens `if not
projects: return None`, and its docstring records why. But the row's headline
measurement (*"0 of 14 banks that carry the field have ever held a project or a
former one"*) was the case FOR the fix. Re-measured against the live database
today, after the fix has been in place since 2026-08-04 and **328 turns have
been played**:

| | count |
| --- | --- |
| `chat_chars` states carrying an `interior` blob | 100 |
| live projects across all of them | **0** |
| former projects | **0** |
| banks currently carrying a one-beat `project_review` flag | **6** |

So the reachability defect is genuinely fixed — the review beat now fires, and
fires often enough that 6 of 100 banks are carrying one right now — and the
tier has still never been used. The occasion is offered and declined. That is a
different failure from the one the row diagnosed, and the row currently reads
as though the problem were closed.

**`DESIGN_PSYCHOLOGY_AS_PRESSURE.md` (a) and (b) implemented, (c) deferred:
RIGHT.** Nothing in `mind/` computes a derived inclination — (c) is genuinely
absent, as the note says — and the values-as-trade-offs change is prompt-side,
outside this slice. The note's own §1 measurement (`conflicts_with` scored ~125
times, "torn between" once) is a measurement of prose, not of this module; the
ambivalence machinery it credits is `normalize_wants`' enacted/suppressed pair
(`affect.py:1073-1084`), which is present and correct.

**`AGENTS.md` § "Outcome feedback exists, narrowly": RIGHT.**
`apply_intent_ops` gates `satisfy` behind `evidence_ok` within
`_INTENT_EVIDENCE_WINDOW` turns of formation, and commit credits
`routes_that_worked` from a newly-satisfied intention
(`commit_memory.py:864-884`). The claim that this is the ONLY success signal
anywhere holds against this file: nothing else in `mind/` reads an outcome.

**`AGENTS.md` § "How much a mind holds at once": RIGHT.** `CAPACITY_LADDER`,
`normalize_capacity` (never invents a rung), `capacity_caps` (absorption
narrows by one, floored at one), `PROJECT_CAP` deliberately off the ladder with
the reason stated. Unset is stored as `""` and not backfilled, exactly as the
row requires.

**`AGENTS.md` § surface habituation: RIGHT.** `affect_habituation` defaults off
and is byte-identical when off (the `habituation` key is neither read nor
written — `resolve_affect:930-936`); `_compress_top_slice` compresses only the
slice above `_HABITUATION_ELEVATION_FLOOR` of the axis's own span; the release
both refunds the accumulated cost and waives compression on its own beat
(`:914-921`). `tools/affect_replay.py` exists and replays both arms.

**Stale within the module:** findings 5, 11, 12, 13.

### `mind/memory.py` (5,496 lines)

Seven concerns in one file, as `AGENTS.md`'s landmark list says: the lorebook
hierarchy and graph resolution; chat lorebook attachment; memory normalisation
and hybrid retrieval; summaries and consolidation; snapshot/restore; lore
entries; relationships; and the vector maintenance family that has grown up
around the embedding model.

**The read seam is the best thing in the file, and it is RIGHT.**
`visible_memory_rows` (`:1284-1338`) makes `before_turn_idx` and
`viewer_frame_id` required positional-keyword arguments with no defaults, so
forgetting the F1 turn cutoff or the frame filter is a `TypeError` rather than
a leak. The comment above it (`:1259-1282`) is one of the clearest statements
of the engine's own philosophy anywhere: *"repetition is precisely how a sixth
path forgets, because nothing makes it reproduce five filters it may not know
exists."* The remaining parameters can only narrow. Every read path in the file
goes through it. **`AGENTS.md`'s "a character deciding turn N never retrieves
memories stamped turn N or later" and `PIPELINE.md`'s F1 row: RIGHT.**

**Host-scope crossings are listed, not accidental.** `HOST_SCOPE_READERS =
("dramatic_irony_feed", "promise_ledger")` (`:1338`), both reached only from
author-facing routes (`web/app.py:3336`, `:3340`). This is the correct reading
of `AGENTS.md`'s "the firewall is for MINDS, not for developers or tooling".
The tripwire that keeps the list honest is weaker than it looks — finding 18.

**Retrieval: `docs/guides/MEMORY.md` §§4-6 and `Design.md:183-190`: RIGHT.**
Four RRF rankings (semantic, cue-vector, keyword, exact) scaled by `_RRF_SCALE
= 12` against a ~0.4 bonus band; per-aspect rankings at `_ASPECT_WEIGHT = 0.55`
fused separately rather than concatenated; `_rank_normalized_importance`
respacing inside the bank's own p10–p90; belief weighting signed around 0.5 on
inference rows; mood congruence at 0.05 reading `_congruence_valence`'s
75/25 encoded/incoming blend; here/in-sight location cues at 0.09/0.05; MMR
diversification at 0.82/0.18; chronological-neighbour padding to `k+2`. Every
number in `MEMORY.md` §5 matches the source.

**Unbidden recall: `Design.md:228`: RIGHT, including the inversion gate.**
`contrast_memory` requires `_CONTRAST_SEMANTIC_COVERAGE = 0.9` of the bank to
be model-comparable before the semantic term is used at all, for the reason the
row gives — on an inverted axis an incomparable 0.0 reads as maximal contrast.
The code comment at `:2224-2237` states it better than the row does.

**Summaries: `Design.md:187-189`: RIGHT.** `memory_summaries` is keyed per
window; `search_memory_summaries` applies char scope, the same exclusive
`before_turn_idx` cutoff, and skips cross-model vectors;
`build_character_memory_context` sends `earlier_in_my_life` chronologically
with relative `_beats_ago_span` dating and never an absolute `turn_idx` — the
firewall reasoning at `:2773-2783` is correct and worth keeping.
`backfill_memory_summary_windows` neither archives nor moves the consolidation
cursor, as documented, and both properties are visible in the code.

**Provenance scopes: `Design.md:229` (P8): RIGHT.** Three summary rows per
window, first-hand written unconditionally because
`maybe_consolidate_character_memory` reads its `end_turn_idx` as the cursor
(`:3286-3291`) — a subtle dependency, stated in the code.

**Empty views: RIGHT and language-aware.** `_empty_view_markers` reads every
installed pack's `narrator_nothing` template beside the English literals, with
the measured reason. This is the one place in `mind/` that does what
`AGENTS.md`'s language row requires — see finding 4 for the nine places that
do not.

**The embedding-maintenance family: built, mostly reachable, partly not.**
`embedding_bank_status` → `start_rebuild_if_needed` → `rebuild_embeddings` is
wired at startup (`web/app.py:163`) and after a checkpoint restore
(`persist/checkpoints.py:701`), and the guards are careful in the way the docs
claim: it refuses to write a fallback over real vectors, refuses to run the
lore pass while the provider is degraded (because lore staleness is measured by
width and a degraded provider inverts the test), and separates "no provider
configured" from "provider not answering" so a 429 cannot be reported as a
migration. `note_failed_embedding_write` / `repair_pending_embeddings` /
`queue_fallback_rows_for_repair` are all reachable. Three functions in the same
family are not — findings 7 and 8 — and both maintained documents describe
them as shipped.

**`AGENTS.md`'s "Lore is the known case": CONFIRMED STILL OPEN.**
`knowledge_for_character` (`:4503-4540`) gates which knowledge entries reach a
character by tag and by room, and returns `r["content"]` verbatim with no name
scrubbing. That is exactly the residual the routing row names as a known
exception to the identity floor; it is unchanged.

**`Design.md:242` ("A mind can re-read what a memory meant", Built, never
occasioned"): RIGHT.** Live: 2 rows carry a non-empty `disputed`. 162 rows have
a revised `importance`.

### `mind/canon_provenance.py` (360 lines)

The provisional tier: a write-path validator refusing a low-tier record that
mints an event id, asserts a consequence, names a room in prose rather than by
node id, or keys a subject by display name. `validate_provisional` is live on
one path (`world/offscreen.py:441`); `is_node_id` and `Subject` are shared with
`world/gaps.py` and `world/subjects.py`. Everything else is unreferenced —
finding 17, plus the stale `promote` docstring.

The module docstring's three stated design choices (open subject-kind
vocabulary, no assumption that a subject is a person, promotion deliberately
unimplemented) are all true of the code.

### `mind/__init__.py` (6 lines)

Docstring only: *"Grouping is for navigability, NOT an enforced layering:
several packages here are mutually dependent and the deferred imports inside
function bodies are the long-standing evidence of it."* **RIGHT** — and the
evidence is present in this slice: `memory.py` defers `language_runtime`
(`:3200`), `llm.providers.cheap_embed` (`:4348`) and `core.db` (`:4611`,
`:4633` — those two redundantly, finding 20).

### Cross-document verdicts, summarised

| document | verdict |
| --- | --- |
| `Design.md:171` "Event-grounded live psychology" | **RIGHT**, except the "protected beliefs" clause (finding 2) |
| `Design.md:182` "Long-term goals (the project tier)" | code **RIGHT**; the row's measurement is **STALE** — 0 projects across 100 banks and 328 turns after the fix, with the review beat now firing |
| `Design.md:183-190` retrieval / summaries / eras | **RIGHT** in every checkable number |
| `Design.md:184` "Changing the embedding model is safe" | **RIGHT** about behaviour, **STALE** about reachability — `rebuild_checkpoint_embeddings` has no caller (finding 7) |
| `Design.md:228` unbidden recall | **RIGHT**, including the coverage gate |
| `Design.md:229` P8 provenance scopes | **RIGHT** |
| `Design.md:240` salience respacing | **RIGHT** |
| `Design.md:242` memory dispute | **RIGHT** — live corpus holds 2 |
| `Design.md:246` attentional capacity | **RIGHT** |
| `AGENTS.md` § Information boundaries (memory clauses) | **RIGHT** — the seam enforces them structurally |
| `AGENTS.md` § Sensation constrains cognition | **RIGHT** |
| `AGENTS.md` § belief provenance / hypothesis sheet / kind distrust | **RIGHT**, with the English-only caveat on `effective_kind` |
| `AGENTS.md` § "Recall follows belief" | **RIGHT** except the matcher drift (finding 1) |
| `AGENTS.md` § language packs ("never silently fall back to English guards") | **VIOLATED** in `mind/`, ten times (findings 4, 10) |
| `docs/guides/PIPELINE.md` §`character:<id>` / §`commit` | **RIGHT** |
| `docs/guides/MEMORY.md` §§1-9 | **RIGHT** on behaviour; silent about three unreachable functions it documents (findings 7, 8) |
| `DESIGN_LONG_TERM_GOALS.md` | **RIGHT** clause by clause against source |
| `DESIGN_PSYCHOLOGY_AS_PRESSURE.md` | **RIGHT**; (c) is genuinely unbuilt as it says |

Nothing in this slice was found built-and-quietly-lost in the sense
`AUDIT_DIRECTOR.md` uses — every engine mechanism the maintained docs claim
for a MIND was located, live and reachable. What is unreachable here is
entirely host-facing maintenance and reporting: five functions
(`rebuild_checkpoint_embeddings`, `backfill_lore_embedding_stamps`,
`lore_embedding_health`, `monitoring_subtree`, `relationship_history`) that
exist, are tested, are documented, and have no way in.

---

## Unverified suspicions

Recorded here rather than above because I could not close them by reading and
grepping alone.

1. **`_extract_entities`' `at_sentence_start` rule may be dropping the subject
   of short inference claims.** `memory.py:770-775` declines a single
   capitalised token at a sentence boundary unless it recurs later in the text.
   Inference rows supply `entities` explicitly (`commit_memory.py:735`), so
   they are unaffected; episode rows do not. Whether this loses subjects that
   `search_memories`' exact-entity ranking would have used is a measurement I
   did not take.

2. **`_STRANDED_REPORTED` (`memory.py:1806`) grows unbounded within a process**
   — one entry per `(chat_id, char_id, model_key)`, cleared only by a
   successful `rebuild_embeddings`. Bounded in practice by cast size times
   chats, so probably harmless; I did not measure a long-running process.

3. **`resolve_lorebook_graph`'s ancestor hop uses `depth = -1`**
   (`memory.py:446-449`), which makes an ancestor's own children reachable at
   depth 0 and therefore able to re-trigger the ancestor walk. I could not
   construct a case where this loops (the `visited` weight check should stop
   it) but the depth arithmetic is not obviously safe, and
   `max_link_depth + 2` at `:429` is a second magic offset in the same loop.

4. **The 108-vs-33 gap in finding 1** — 75 rows pick the same hypothesis at a
   different similarity score. I argued those are harmless because
   `belief_credence` returns the hypothesis's confidence rather than the
   similarity. If a future caller ever ranks on the similarity, they are not.

5. **Whether any live story has ever run under the `ja` pack.** The word-list
   findings are a violation of a stated invariant regardless, but their
   practical cost today depends on that, and I did not look for a chat with a
   non-English `language_id`.
