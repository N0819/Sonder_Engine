# 16 — The blocking fixes, and what the re-measurement says

Status: **COMPLETE.** Six changes landed on `perception-spatial`, all
uncommitted. `make check` green at **5,732 passed** (was 5,690; +42 tests).
The corpus was re-replayed and re-scored after the changes; every number
below is measured, and the before/after columns are scored by the SAME
scorer against the SAME corpus file, so they are comparable to each other
even though both are now smaller than note 14's (chats 68/69, 131 turns,
were deleted through a live server mid-measurement — see note 14 §Corpus
stability caveat).

Replay after the fixes: 2,165 turns, **4,261 stage executions, 0 stage
errors, 0 provider calls.**

---

## 1. The scored table — the three blocking items are cleared

Identity-floor era, 2,844 composed views against 2,858 stored.
"composer (was)" is note 14's build re-scored here; "now" is this tree.

| metric | model | composer (was) | composer (now) |
|---|---|---|---|
| identity-leak views | 107 | 69 | **22** |
| self-narration views | 131 | 0 | **0** |
| invented-dialogue views | 7 | 0 | **0** |
| concealed-line leaks | 0 | 0 | **0** |
| delivered-line recall | 94.32% | 98.40% | **99.63%** |
| same-room line recall | 94.73% | 98.59% | **100%** |
| **player same-room lines missing** | 6 | **33** | **0** |

The regression that blocked shipping is not merely repaired; the composer
is now ahead of the model on the metric it was behind on.

### 1a. "Self-narration 0 → 33" was the checker, not a regression

Disarming the repair pass made `self_narration_views` jump from 0 to 33,
which read as the expected trade. It was not. All 33 were sampled: every
one is a FRAGMENT OF A DELIVERED LINE — `Hinami's magic-box description is
fair."`, `Hinami speaks of you with real pride."` — i.e. somebody saying
the perceiver's name to their face, cut mid-quote by the same
sentence-splitter the repair pass used.

Then the decisive check: the 33 views flagged self-narrating after the fix
are **exactly, all 33 of them**, views that had lost an entitled line
before it (43 lost lines total floor-era; overlap 33/33). The old build
scored 0 self-narration because the repair had already deleted the
evidence. A metric that scores its own mis-split as a defect keeps
rewarding whatever destroys it.

`tools/perception_quality.py` now prefers `_strip_self_narration_quote_safe`
when the tree has one, so the check measures what it claims. Both columns
above are scored with it — the model's own self-narration count falls from
186 to 131 under the honest check, and it is still 131 against zero.

---

## 2. What changed

### Composer fix 1 — the repair passes are graded by what a wrong repair destroys
`agents/perception.py::_composer_tripwires`

- **Identity still repairs.** `_scrub_unknown_identities` substitutes a
  descriptor for a name outside quoted spans; it cannot delete a sentence
  or touch a delivered line, and what it prevents is a firewall breach,
  which must not ship on the strength of a warning nobody reads.
- **Self-narration repairs only where it can prove it is safe.**
  `_strip_self_narration_quote_safe` masks quoted spans BEFORE the split
  (the pattern `_dedupe_view_sentences` already documents: a per-fragment
  "does this contain a quote" test is defeated by the splitter itself),
  then refuses outright to drop any sentence still carrying a mask token.
  The stripper's own two floors now report their refusals too, instead of
  declining silently.
- **Invented dialogue no longer repairs at all.** It deletes whole lines,
  and on this path every quote was built from `dialogue_log` by
  `speech_percept`, so a fire is a bug report — not a licence to take the
  reader's line away.

### Composer fix 2 — authored prose is gated at admission
`_composer_identity_space`, `_authored_prose_gate`, `_composer_authored_prose`,
`_gated_ambient_percepts`

Room notes, appearance/overlay descriptions and ambient events are the
three surfaces nobody wrote for a particular mind. All three now pass
through a per-observer gate at percept-build time, which scrubs unearned
identities and strips perceiver self-narration before the percept exists —
so the fact cannot be rendered, cannot be re-derived into an observation,
and cannot be minted into a memory.

The identity space is no longer the stage roster. `active_cast` filters to
`status='active'`, so a departed or dormant character was off the roster
while their name stayed written into room notes — which is why 69 leaks
survived with **zero warnings**: the tripwire had never heard of them
either. The space is now every character ever attached to the chat, plus
extra players, plus background presences. Recognition still decides: a name
in the space is scrubbed only for an observer who has not earned it.

Result: 69 → 22 floor-era leak views, against the model's 107.

### Composer fix 3 — the prose pass
`agents/composer.py`, `agents/common.py::_tone_clause`

- **Tone grammar.** "says with quietly authoritative in their voice" — one
  slot built for abstract nouns, fed both nouns and adjectives. The head
  word now decides, defaulting to adjective (the broken half, and the more
  common one): *in a quietly authoritative voice*, *with warmth in their
  voice*, *with a faint smirk*.
- **Capitalization.** Event spans are capitalized at assembly, so a
  dialogue tag opening with a lowercase display label no longer follows a
  full stop in lower case.
- **Chronology.** A crossing BOUNDS the beat for that body; it does not
  queue inside it. Arrivals and departures now sit in bands outside the
  outcome stage's running counter, so "X says … X comes in." cannot recur.
  Episodes get this too, since they sort by the same key.
- **Presence is one observation.** Every co-present body the observer can
  see renders as one sentence — "Reya is close by on your left and the tall
  man is across the room" — split by fidelity first, because folding a
  `degraded` body into a `full` body's sentence would read as clearly
  perceived. That is the boundary a prose choice could launder.
- **Bodies you cannot make out are counted.** "Three indistinct figures are
  close by", replacing the same fixed sentence repeated (282 views).

**Not done, and why:** the 94.2% templated-opening figure is not a defect
to fix. Character-mode views render the full standing state every beat BY
DESIGN — a character agent is stateless and its view is the whole context
it gets. Player views are deltas and do not repeat. That figure needs
re-measuring split by mode before anyone changes rendering to chase it.

### R1 — mapping stops transcribing lore back to the engine
`prompts.py`, `agents/mapping.py::_join_relevant_lore`

The ask is now `relevant_lore:[{id, why_relevant}]`; content, keys,
category and book_id are joined engine-side from `hits` by id. An id the
engine never offered keeps the model's text and warns.

Fidelity first: 13.6% of echoed entries came back mutated (5.8% truncated,
7.7% rewritten at a median 59% of true length) and poisoned `lore_cache`,
which `mapping_quick` re-serves with no model call for 1,879 of 1,881
measured steps. Latency second: ~485 tok/call, 38% of mapping's
model-written output, ~0.06–0.09 s/turn at 1000 tps and ~7.6 s/call at 64.

### R2 — the resolve contract stops asking for what the engine overwrites
`prompts.py`

`volume`/`visibility`/`conceal_from` are re-stamped on every declared line
from the declaration itself (`director.py:4880-4890`, `:4949-4950`). The
contract now asks for them only on lines the Director originates. Pinned by
a new test that an omitted volume on a declared whisper is re-stamped
rather than defaulted — the trim must not reintroduce the 200-metre-shaft
leak the backstop exists to stop.

### G6 — a room nobody sized is a perception grade the engine picked
`spatial.py::guessed_room_sizes`, `commit.py::prepare_scene_commit`

`proximity_rel` reads size to say two people are `across` a room; S2a caps
sight in a large room at `shapes`. 175 of 392 live rooms carry no size.
Warned at the scene-commit seam, only for rooms with two or more occupants
(a room with nobody in it has no proximity to grade) and only on the beat
the room CROSSES into being shared — a standing condition reported every
beat is one the reader learns to skip.

---

## 3. Tests added (42)

| file | count | what it pins |
|---|---|---|
| `tests/test_composer_admission_gate.py` | 11 | the quote-safe floor, the gate, off-roster leaks, no repair pass deleting a line |
| `tests/test_composer_prose.py` | 11 | tone grammar both ways, capitalization, arrival/departure ordering, presence fusion, fidelity never mixed, span-verbatim invariant |
| `tests/test_mapping_lore_join.py` | 7 | the join, the model's surviving judgement, uncited ids, string/int ids, the prompt |
| `tests/test_room_size_coverage.py` | 9 | reported once on crossing, never for empty rooms, never when authored, wired into the seam |
| `tests/test_speech_concealment.py` | +4 | omitted tags re-stamped, originated tags kept, defaults, the contract |

---

## 4. Still open (unchanged by this pass)

- **Chat 18's checkpoints reference a deleted turn id** in
  `world_entities.created_turn_id`; the engine's own `restore_checkpoint`
  would abort on that chat today. Deserves an UNBUILT entry.
- **Outcome views render declared intent, not resolved outcome** — 29
  measured direction contradictions, 511 dropped overt acts. Needs the
  Phase-1 typed outcome surface.
- Episodes omit micro-loop content on 339 turns.
- Poses / scales / contained-ledger not composed (~100 turns each).
- R3 (perception-adjudication prose instructions) stays blocked on the
  composer flag defaulting on. R4 (`dialogue_order`) and R5
  (`resolved_event` privatization) unchanged.
- `engine.db` in this worktree is LIVE, not frozen. Copy it before any
  future measurement run.

---

# Addendum — the perception model is gone

Landed after the above, on the same branch. `make check` green at **5,723**.

## What was removed

| | |
|---|---|
| `perception_llm_disabled()` + the `PERCEPTION_NO_LLM` env var | deleted |
| `_per_observer_model_views` (the 4-wide fan-out) | deleted |
| the model path inside the three stage functions | 84 + 290 + 536 lines, deleted |
| `agents/perception.py` net | **−1,028 / +320 lines** |

Each stage now assembles its typed inputs and ends in a single
`return _composer_*(...)`. `agents/perception.py` no longer imports
`_agent_json`, `get_prompt`, `contextvars` or `ThreadPoolExecutor` — there is
nothing left in it that could reach a model, which
`tests/test_perception_has_no_model.py` asserts structurally rather than
behaviourally (a behavioural test passes while a model call sits on a path it
did not happen to take).

**Deliberately kept:** the `perception` prompt text in `prompts.py`, with a
comment saying nothing sends it. Stored steps, archives and pipeline traces
still resolve through the `perception` step key, and deleting the entry would
break replay and reroll of every pre-change turn — the same reasoning that
keeps retired schema fields declared.

## It changed nothing, and that is the point

Full corpus re-replayed after the deletion — 2,165 turns, **4,261 stage
executions, 0 stage errors** — and re-scored. Identity-floor era:

| metric | model path | flagged composer | LLM-free |
|---|---|---|---|
| identity-leak views | 107 | 22 | **22** |
| self-narration views | 131 | 0 | **0** |
| invented dialogue | 7 | 0 | **0** |
| concealed-line leaks | 0 | 0 | **0** |
| unentitled-line leaks | 16 | 16 | **16** |
| delivered-line recall | 94.32% | 99.63% | **99.63%** |
| same-room line recall | 94.73% | 100% | **100%** |
| player same-room lines missing | 6 | 0 | **0** |

Byte-for-byte the same behaviour the flag already produced. The flag was
routing to the composer; removing it removed the road not taken.

## 92 tests moved, and the migration found two defects

Deleting the model path broke 92 tests across 17 files. **None were deleted
for convenience.** They fell into three kinds:

1. **Payload-shape tests** — asserting what the model was *told*
   (`proximity_to_sources`, `present_appearances`, `scene.body_regions`).
   Migrated to assert the composed VIEW. This is a strictly better test: a
   payload could carry a fact the model then declined to use, and a view
   cannot. Where a test needed an internal (the perceiver list), the capture
   point moved to the `_composer_*` handoff, which is the same data computed
   by the same code.
2. **Model-prose scrub tests** — feeding adversarial prose and checking the
   scrub removed it. Re-aimed from "the scrub caught it" to "it was never
   admitted", which is the stronger claim and the one the firewall actually
   makes. The scrubs still exist as tripwires with their own tests.
3. **Source-inspection tests** bound to deleted code. Three retired with a
   note; `test_perception_pass1_unknown_roster.py` was rewritten end-to-end —
   it had sliced a source block out of the file and exec'd it because, in its
   own words, "exercising it end-to-end needs a model call".

Two real defects surfaced from the migration itself:

- **Degraded sight was costing acquaintance.** `presence_percepts` labelled
  every body seen at `shapes` "an indistinct figure", including bodies the
  observer knows. A dim room turned everyone you know into a stranger, which
  reads as amnesia and under-grants: knowing who has been standing in the room
  with you is knowledge you already hold, and the dim light takes their face,
  not their name. Fixed; an unrecognised body still gets the fixed label
  rather than its appearance descriptor, because a silhouette cannot show fox
  ears. **Measured across the corpus: views containing "indistinct figure"
  fell 570 → 439.**
- **Stranger labels were cut mid-phrase.** "a tall woman in a long grey coat"
  capped at five words gave *"the tall woman in a long"* — a dangling
  adjective, reader-facing. The trim now walks back past the connective when
  the cap cut a phrase short, so a label is always grammatical at every cap.

## What this unblocks

R3 (the perception-adjudication prose instructions in the Director's prompt,
`design_notes/15`) was conditional on the composer being the only path. It now
is: nothing reads `resolved_event` for per-perceiver routing, so those prompt
paragraphs can lose their "narrate who perceives what" halves while keeping
the outcome causality that is the Director's real job.
