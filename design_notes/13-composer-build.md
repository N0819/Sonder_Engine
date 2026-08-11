# 13 — Composer build notes (branch `composer`)

What landed, what it does, what it deliberately does not do yet. Spec: note
03 (with §2.6's lexical-variation ranking overturned by measurement), 00-PLAN
Phase 2/3, 06 for the bars. Everything here is opt-in behind
`PERCEPTION_NO_LLM`; with the flag unset the engine is byte-identical to the
base (verified: full suite green with the flag exercised only by the new
tests).

`make check`: **5,614 passed** (base was 5,576; +38 new tests, 0 failures).

---

## What was built

### `agents/composer.py` — two layers, one typed seam

**The IR.** `Percept(kind, channel, source_label, fidelity, data, salience,
suddenness, order_key, dedupe_key)`. Kinds: environment, presence,
appearance, act, speech, sensation, substance, body_region, body_state,
crossing, residue, ambient. `order_key=None` marks standing state; events
carry declared/beat order and chronology is authoritative within the event
chain. `source_label` is recognition/disguise-gated AT ADMISSION;
`data` carries only fidelity-degraded surfaces (a fragment percept holds the
muffled fragment, never the full quote body). Canonical names ride **no**
field — not even bookkeeping: the first-mention ledger uses an opaque
`body_key()` hash, so the firewall invariant is checkable by plain string
containment over the whole record (`tests/test_composer.py::
test_unrecognized_actor_never_named_in_ir`).

**Layer A — admission.** Small pure builders (`speech_percept`,
`act_percept`, `presence_percepts`, `contact_percepts`,
`substance_percept`, `crossing_percept`, `body_region_percepts`,
`residue_percepts`, `environment_percept`, `ambient_percepts`,
`body_state_percept`) each of which either admits a gated record or returns
nothing. Gates: concealment (absolute, never a volume), `hear_level` with
measured proximity + the comm/addressed rescue (`line_hear_level` — moved
here whole; `perception._dialogue_hear_level` now DELEGATES to it so the two
paths cannot drift), enclosure directions, sight levels via
`visual_level_between` (containment-aware), rear arc, co-location. Every
admission subtracts; no builder adds a channel.

**Layer B — rendering.** `render_view(percepts, mode, prev_standing,
prev_described, full_render)` — signature takes percepts and mode parameters
only, no scene, no ctx (pinned by `test_render_takes_no_scene`), so a
rendering path structurally cannot add information. Grammar reuses
production renderers: `_inject_dialogue` emitting into an empty document
(bare-infinitive heard form, conducted, articulation),
`_observable_predicate`, `contact_sensation`/`substance_event_clause`
clauses carried as data, `_compose_residue_view` for non-awake minds. Plain
templates, zero lexical-variation machinery (per the corrected ranking:
0.24% collisions for the retired crude formatter vs 1.03% for model prose —
templating did not collapse retrieval). One discourse rule: a sudden event
chain (suddenness ≥ 0.6) leads the view; otherwise standing state anchors
and the beat follows.

### Three render modes over one percept list

- **character** — full standing state every beat (a character agent is a
  stateless call; if it is not in context the mind does not have it), plus
  the event chain in declared order.
- **player** — delta only: events always; a standing percept renders only
  when its content changed. Change detection is free because every standing
  `dedupe_key` hashes its content (a darkened room is not the lit room
  restated). An explicit look/examine intent
  (`perception._explicit_look_intent`, read from `director_interpret`'s
  structured output — `location_query` or a look-verb action) re-renders
  everything.
- **memory** — `render_episode`: first person, the salient delta only.
  Event-bearing sentences LEAD; changed standing trails; any room change
  goes last (load-bearing ordering — embedding models over-weight the first
  sentence, arXiv:2412.15241, cited at the code site). All-unchanged
  standing state is a **non-event: content ""**, and commit mints nothing.

**First-mention tracking** (the 481+249-verbatim-repeat fix): the full
appearance description renders once per observer per body, in every mode,
keyed by an opaque body ledger; a structural appearance change
(attire/overlay/scale/description diff) re-earns it via `force`. The
cross-turn ledger (`composer_ledger`: per-observer standing keys + described
keys) rides the stage output and is recovered from the previous turn's
stored step — the same recovery pattern as `_previous_open_group_continuity`.

**Referring expressions**: `assign_stranger_labels` chooses distinguishing
descriptors JOINTLY against the others present — colliding stranger labels
widen word-by-word from their own appearance summaries ("the fox woman with
six tails" vs "the fox woman with a single silver tail") before any numeric
suffix; names/aliases are stripped before the descriptor is cut, as before.

**Observations project from the IR**, never regex-classified from prose:
channel, suddenness, intensity, ambiguity and directed_at_self are known
fields. Each `observed.text` is a rendered sentence span, so the second
representation still cannot exceed the first. **Aggregation keys on the
delivery verdict**: atoms merge only when channel AND fidelity class AND
self-direction match, and a cap-forced merge degrades to the weakest verdict
present (max ambiguity, channel→mixed). Merging two percepts can never
launder an information boundary — Sonder's own firewall requires this
independently of any prior art.

### Wiring (`agents/perception.py`)

Each stage branches to `_composer_establish/_composer_act/_composer_outcome`
right after its awareness gate, when `perception_llm_disabled()`. The
orchestrators reuse the stage's own structures (rel maps, enriched dialogue
log, co-present bodies with disguise-adjusted visible appearance,
`observer_body_regions` + `_bare_body_details` for anatomy floors,
last-overt acts, substance events, state-diff movement for crossing
percepts). **`resolved_event` is never consumed** — the omniscient prose
does not exist on this path, which closes the two documented prose-matching
holes (`_redact_concealed_from_event`'s fresh-subject paraphrase,
`_surface_translate_event`'s all-or-nothing replacement) structurally.
Director/character observable surfaces are identity-scrubbed at ADMISSION
(`_composer_scrub_surface`) so an authored "steps toward Hinami" never enters
a stranger's percept.

### Scrub passes: what became assertions/tripwires

Run as **runtime tripwires** over composed views (warn loudly as "COMPOSER
TRIPWIRE … engine defect"; scrubbed text still taken as free
defense-in-depth): `_scrub_unknown_identities`, `_strip_self_narration`,
`_scrub_invented_dialogue`. Kept armed as warning-only checks exactly as on
the model path: `_disguise_leak_check`, `_inverted_motion_check`.

Not run at all on the composer path because the failure they repair is
structurally impossible there: `_strip_onset_rendering` (composer owns
order), `_strip_unknown_pose_claims` (composer asserts no poses at all —
see gaps), `_strip_unreachable_bodies` (Layer A never admits a channel-less
body), `_scrub_undeclared_player_speech` (only typed lines are rendered),
`_ensure_environment` / `_fallback_perception_views` (the composer is the
always-path), `_dedupe_view_sentences` (dedupe keys on the IR; still used at
the micro-append seam), `_action_already_rendered` / `_contact_already_felt`
/ `_authored_detail_already_present` (nothing paraphrases),
`_redact_concealed_from_event` / `_surface_translate_event` (no omniscient
prose to redact). On the model path everything is untouched.

### The memory change (`commit.py`, coupled per 00-PLAN Phase 3)

`perception_outcome` (composer path) emits `episodes` + `episode_meta`
(gist, typed entities) per character, minted by `render_episode` from the
SAME fidelity-degraded percepts the view rendered — subset-checked by test
(`test_episode_never_exceeds_the_view`). `prepare_memory_commit` prefers the
composed episode over the view when present; a composed `""` is a non-event
and mints no row; typed `entities`/`gist` ride the pending memory so
`memory.py`'s `_extract_entities` prose-scraping fallback is bypassed.
Entities are the observer's own display labels (a stranger's descriptor,
never an unearned canonical name), generic labels ("a voice", "the
unfamiliar person") excluded. Absent keys fall back to view prose exactly as
before — the model path's memory behavior is unchanged.

The "You are in an unspecified area." pathology (812 rows, 97.3% collision)
dies twice over: `environment_percept` returns None for an unresolvable
room (no percept → no sentence → no episode), and an eventless beat mints
nothing regardless.

---

## Honest gaps / residuals (candidates for docs/UNBUILT.md when this merges)

1. **Layer B is plain templates without fusion.** Note 03 §2.3's
   aggregation (presence + first act fused into one sentence; per-source
   coordination) is not built. Views read staccato. Deliberate: correctness
   first, and the no-fusion form makes the span↔percept mapping exact for
   observations.
2. **The micro-loop seam is unchanged.** Interaction-round deliveries
   arrive pre-rendered and are appended after the composed view (gated by
   `_delivery_ok` when the loop ran); they appear in views and as a single
   mixed observation atom but NOT in IR-minted episodes. The right fix
   remains note 03 §5.6: the micro loop should emit percepts.
3. **Outcome acts keep the last-overt-only rule** for the same reason the
   model path has it (no per-stage room/barrier snapshot). The per-sub-action
   gating 03 §1.3 wants needs the Phase-1 typed outcome surface.
4. **Not rendered on the composer path** (the model payload carried them;
   character minds lose them until built): poses, scales, contained ledger,
   sightlines/visible-room descriptions, crowds/couriers/notices, scent
   percepts (smell is only reachable via authored ambient events at
   establish), `source_manifest` tells/demeanor, other-players' declared
   sequences at onset. Each is a subtraction, never a leak — but it is real
   interim regression in completeness and should be stated, not papered
   over.
5. **Background movers** in crossing percepts get the fixed label "a
   figure" when they are not in the appearance roster; no descriptor is
   derived for them.
6. **The full percept lists are not persisted** — only views, observations,
   episodes and the ledger. Replay assertions over the IR therefore rerun
   Layer A rather than reading stored IR. Cheap to add if the replay harness
   wants it.
7. **Player-view delta vs narrator**: the narrator now receives a delta
   view on ordinary beats. That is the design (note 05 consumers), but the
   narrator prompt has not been retuned for it; watch the first live runs.
8. **Verification plan (03 §4) not run here**: no corpus replay, no
   shadow-bank embedding comparison (no API budget this session). The unit
   and stage tests pin the structural properties; the quantitative gates
   (100% delivered-line recall over 9,351 views, collision ≤ 14.7%, MRR ≥
   0.299) still need the harness run before the flag defaults on.

---

## Credits and provenance

External sources actually used in this implementation:

- **Lee, Goel & Ramchandran, "Quantifying Positional Biases in Text
  Embedding Models", arXiv:2412.15241** — *idea only* (academic finding,
  no code): embedding models over-weight a text's first sentence. Drives
  the load-bearing ordering rule in `render_episode` (events lead, room
  change last); cited in the code comment at that site.
- **Li et al., "On the Sentence Embeddings from Pre-trained Language
  Models" (BERT-flow), EMNLP 2020** — *idea only*: cosine similarity tracks
  surface overlap more than meaning, so the varying content must dominate
  the minted text by length, not merely be present. Drives the episode
  design of omitting unchanged standing state entirely rather than
  appending deltas to a fixed frame. No code, no citation needed at a
  single site; recorded here.

Explicitly NOT used:

- **Angband `mon-msg.c` (GPL)** — no code, no code structure, not read.
  The rule that aggregation must key on the visibility/channel verdict is
  implemented from Sonder's own firewall principle (merging two percepts
  must never launder an information boundary), which stands without
  reference to any other codebase.
- **TADS 3 `displaySchedule` (proprietary)** — nothing derived. The
  edge-sensitive re-announcement idea (re-emit on change, not on presence)
  was independently specified in note 03 §2.2 ("rendered when the room
  *changed* … omitted otherwise") before the lead existed; treated as
  corroboration only.
- **Curveship (reported ISC)** — no code taken, source not read, licence
  not verified; its realiser remains a lead for a future Layer B
  refinement only.

Everything else in this change is derived from this repository's own
production code (the renderers and gates listed above, all MIT, all
in-tree) and its design notes.
