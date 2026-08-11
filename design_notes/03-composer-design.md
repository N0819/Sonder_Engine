# 03 — The deterministic view composer

Branch goal (`perception-spatial`): perception becomes a pure function of
spatial data with zero LLM calls. Mapping and the Director only ever CHANGE
SPATIAL DATA; perspective is computed entirely by code.

This note designs the composer that replaces the perception model call: the
code that turns (per-observer scene projection + typed beat events) into each
mind's view prose. It is grounded in a full read of `agents/perception.py`
(3,996 lines), the three existing deterministic composers, the memory-minting
path in `commit.py`, and read-only measurements over the 2,296-turn play
corpus at `engine.db` (probe scripts summarized in the appendix; the database
was never written).

Verdict up front: the approach is sound, and most of it already exists in
production under other names. The engine already deletes the model's rendering
of the beat's own events and rebuilds them deterministically
(`_strip_onset_rendering` / `_inject_onset_sequence`, agents/perception.py:1317,
1420, applied at 2854/2958); already renders non-awake views, micro-round
views, interoception, standing contact and substance transfer with zero LLM
(`_compose_residue_view` agents/common.py:4057, `deterministic_micro_perception`
agents/loops.py:45, `contact_sensation` spatial.py:4911,
`substance_event_clause` spatial.py:4642); and already re-derives structured
observations from prose so the model cannot widen the budget
(`_observations_from_clean_views`, agents/perception.py:763). What the model
still contributes is ambient color and sentence flow. The composer's real risk
is not the firewall — it makes the firewall strictly stronger — it is prose
register, and specifically what template prose does to the memory bank
(commit.py:5510 mints each character's episodic memory verbatim from their
view). Section 3 quantifies that risk against the corpus and concludes it is
survivable **only if memory minting moves off view prose in the same change**.

---

## 1. Architecture

### 1.1 Two layers, one new module

`agents/composer.py`, a role module under the facade rule (may import
`agents/common.py`, `spatial.py`, `scene.py`; never another role module).
`agents/perception.py` keeps the three stage entry points and their exact
output contract; it becomes the orchestrator that builds inputs and calls the
composer instead of `_per_observer_model_views` (agents/perception.py:1146).

The design splits what today is smeared across payload construction, a model
call, and twelve repair passes into two functions with a typed seam between
them:

**Layer A — percept selection (`build_percepts`). This is the information
boundary.** Pure function of
`(scene, prev_scene, perceiver, typed_beat_events, known, awareness)` →
an ordered `list[Percept]`. Every admission decision the engine already knows
how to make happens here, on structured data, before any prose exists:

- delivery: `_delivery_ok` (agents/common.py:2176), `hear_level` with
  proximity, `visual_level_between`, `scent_level`, `containment_conceals`,
  rear-arc `entity_arc`, `crossing_visible_from`, `open_group_continuity`,
  `_visible_rooms_for` minus `_behind_rooms` (agents/perception.py:1901);
- identity: recognition through the `known` ledger picks the `source_label`
  at admission time — canonical name, `_unknown_actor_label`
  (agents/common.py:2115) built from the disguise-adjusted visible appearance,
  or "a voice"/"an indistinct figure" per sight level. Exactly the input-side
  floor `_co_present_company` already implements for pass-1 presence
  (agents/perception.py:1976–2052);
- concealment: a concealed event element is simply not admitted for an
  excluded observer (`_concealed_from_perceiver`, agents/perception.py:1197);
- touch-only sources (`_touch_only_sources`, agents/perception.py:2995)
  contribute **only** `contact_sensation`/motion-pressure percepts — no event
  surface at all;
- awareness: a non-awake mind gets the residue percepts and nothing else
  (`_compose_residue_view` inputs: level, targeted, loud_event, pain).

A `Percept` is a small typed record, illustratively:

```python
Percept(
    kind,          # environment|presence|appearance|act|speech|sensation|
                   # substance|body_region|crossing|residue|ambient
    channel,       # sight|hearing|touch|interoception|smell
    source_label,  # ALREADY recognition/disguise-gated display label
    fidelity,      # full|degraded|fragment|trace
    data,          # typed per kind: quote body+volume+tone, observable
                   # surface, contact record, region surface, room name/notes
    salience, suddenness,
    order_key,     # declared/beat order for events; None for standing state
    dedupe_key,    # event_id / contact identity / substance record id
)
```

The invariant that matters: **nothing outside a Percept ever reaches the
renderer, and no Percept field carries a fact the observer has no channel
to.** That property is unit-testable on the IR itself — assert no
`source_label` or `data` string contains an unrecognized roster identity —
without regex over prose. Today the same property is enforced by scrubbing
prose after the fact and warning when it fires.

**Layer B — rendering (`render_view`).** Pure function of
`(list[Percept], style_seed)` → `str`. No scene access, no DB, no decisions
about *what* is delivered — only *how it reads*. Its core is the renderers
already in production: `_inject_dialogue`'s sentence grammar including the
bare-infinitive/heard forms, articulation and conducted variants
(agents/common.py:3601), `_observable_predicate` (3842),
`_self_second_person` + `_fix_you_agreement` (3715, 3810),
`_appearance_as_prose` (3960), `contact_sensation`/`contact_phrase`
(spatial.py:4911/4680), `substance_event_clause` (spatial.py:4642),
`_compose_residue_view` (agents/common.py:4057), the muffled-fragment form
(agents/loops.py:116–120). These stop being "injectors into model prose" and
start emitting into an empty document, which deletes their hardest problem —
duplicate detection against a paraphrasing model
(`_action_already_rendered`, `_contact_already_felt`).

### 1.2 Input contract

Per observer, Layer A consumes exactly what the engine already assembles:

1. **The per-observer scene projection** — `_observer_scene_payload`
   (agents/perception.py:849) survives nearly unchanged as the scene half of
   the IR builder: allowed rooms with blinded edges, `_perceptible_entities`,
   contacts with `standing`+`sensation`, poses/`pose_unknown`, substances with
   source-blinding, scales, contained, light, sightlines,
   `observer_body_regions`. It was already "intentionally stricter than an
   output scrub"; it becomes the only scene doorway.
2. **Typed beat events** — the structures the deterministic paths already
   trust: `director_interpret.sequence` via `_observer_facing_sequence`
   (intent stripped, mental beats dropped; agents/perception.py:2256),
   `director_resolve.dialogue_log` (+ background reactions merged as today,
   agents/perception.py:3266–3300), each character result's `sequence`,
   reaction results, `resolve_substance_ops` events, the state diff (for
   movement/attire/weather/awareness change percepts), and the interaction
   loop's per-round deliveries.
3. **Observer state** — senses, awareness, focus, proximity/side/arc maps,
   `known`, standing contacts, own entity/body state.

**The honest gap: `resolved_event` prose.** Today the outcome model is handed
a per-observer redacted copy of the Director's omniscient prose and asked to
filter it. The composer must not consume that prose at all — pasting even the
redacted form re-imports every prose failure this module spent a year
repairing (self-narration was literally the Director's sentence copied
through, agents/perception.py:1695–1719). Composing purely from typed data
loses one thing: outcome *nuance* the Director resolved only in prose (an act
that failed, an environmental consequence not in the diff). The branch thesis
already names the fix — the Director only ever changes spatial/typed data —
so `director_resolve` must grow a small typed outcome surface: per declared
act, `{event_id, outcome: succeeded|blocked|partial, observable_outcome}`,
plus typed environment events. This is the same primitive
`_redact_concealed_from_event`'s own docstring asks for ("carry the actor's
id on the event element and redact on identity, never on text",
agents/perception.py:3133–3140, pointing at docs/UNBUILT.md §3.1/§4.2).
Until it exists, `resolved_event` becomes narrator-only input (the narrator
is player-facing, model-rendered, and fidelity-checked), and NPC views are
composed from what is typed. That is a real interim regression in outcome
detail for NPC minds and should be stated as such in UNBUILT, not papered
over.

### 1.3 Output contract and stage slotting

`PerceptionOutput` is unchanged: `views: dict[str, Optional[str]]`,
`observations: dict[str, list[Observation]]` (schemas.py:2670–2675). Keys stay
`"player"`, `"extra:<pid>"`, `"<cast id>"`; `None` still means "nothing
reached this mind". Steps/variants, the pipeline inspector
(`chat.js perceiverViews`), archives and traces see the same shape; reroll
still works because the style seed folds in the stage `nonce`.

- **`perception_establish`** (agents/perception.py:2290): IR = environment
  percepts (room name/notes, light, sightlines, visible rooms), presence
  percepts for co-located bodies, own entity-state percepts (posture,
  activity, held items — the existing no-view fallback at 2450–2460 is the
  skeleton), authored sensory_events filtered per channel. Zero calls.
- **`perception_act`** (agents/perception.py:2470): IR = onset sequence
  events in declared order (the chronology invariant `_inject_onset_sequence`
  already enforces), presence/company, standing sensations, environment only
  as anchor. Note pass 1 today already deletes and rebuilds the declared
  events; the model's whole remaining contribution here is ambient color.
- **`perception_outcome`** (agents/perception.py:3183): IR = dialogue_log
  lines through the hearing/comm gate (`_dialogue_hear_level`,
  agents/perception.py:287), each actor's overt act surfaces (the composer
  can do better than today's last-overt-only heuristic at 3658–3684, because
  Layer A can gate each sub-action against the start-of-beat *and* end-of-beat
  channel via the `prev_sc` union logic of `_source_channels`,
  agents/perception.py:1492), reaction/interaction round percepts (the micro
  loop should emit percepts rather than pre-rendered strings, unifying it
  with the composer instead of appending text at 3976–3987), substance
  events, standing sensations, body-region foregrounding, movement/crossing
  percepts, appearance-novelty percepts (`_novel_visible_appearances`,
  agents/perception.py:1076).
- **Non-awake minds** in every pass: residue percepts only, exactly as today.

### 1.4 What becomes deletable, what survives

With no model output to repair, the following are deletable as runtime passes
(most should be **kept as replay/test assertions** — see §5):

| Pass | Site | Why it dies |
|---|---|---|
| `_strip_onset_rendering` | agents/perception.py:1317 (call 2854) | nothing to strip; composer owns order |
| `_strip_self_narration` | 1687 (calls 1873, 2946) | composer writes second person by construction; its two refusal floors (never empty a view, never drop the only sight) become moot |
| `_strip_unknown_pose_claims` | 1104 | composer asserts no pose the ledger does not hold |
| `_strip_unreachable_bodies` | 1796 | Layer A never admits a channel-less body |
| `_scrub_unknown_identities` as repair | agents/common.py:2274 (calls 1862, 2916) | labels chosen at admission; keep as tripwire |
| `_scrub_invented_dialogue` | agents/common.py:4390 (call 3915) | only typed lines are rendered |
| `_scrub_undeclared_player_speech` | agents/common.py:4537 (call 3898) | same |
| heard-line floor re-injection | 3922–3955 | no scrub chain left to eat delivered lines |
| `_dedupe_view_sentences`, `_action_already_rendered`, `_contact_already_felt`, `_authored_detail_already_present` | common.py:4586, 3874; perception.py:489, 687 | dedupe_key on the IR; the composer knows what it rendered |
| `_deliver_foreground_body_details` cue regexes | 718 | foregrounding becomes a salience decision, not a paraphrase hunt |
| `_ensure_environment`, `_inject_visible_actor`, `_normalise_views`, `_fallback_perception_views`, retry/empty-view floors | common.py:4089, 3976, 4028, 4113 | the composer is the always-path; no model keys to fold, no fallback tier |
| `_inverted_motion_check`, `_disguise_leak_check` | 2186, 2229 | nothing can reverse a direction or leak a term it was never given; keep as replay assertions |
| `_redact_concealed_from_event` (prose form) | 3116 | replaced by identity-gated typed admission — this **closes** the documented hole (a paraphrase with a fresh explicit subject escapes the sentence matcher, 3126–3140) |
| `_surface_translate_event` | 3079 | replaced by touch-only percept restriction; also cures its admitted over-redaction (it currently nukes the entire event to one fixed sentence) |

Survive, promoted from repair/injection to the composer's own law:

- `_observer_scene_payload` and every gate it calls (Layer A's scene half);
- `_delivery_ok` and the channel ladders in `spatial.py` (Layer A's event half);
- `_unknown_actor_label`, `_strip_identity_tokens`, recognition/disguise
  logic (label selection);
- `_compose_residue_view`, `contact_sensation`, `contact_phrase`,
  `substance_event_clause`, `_inject_dialogue`'s grammar,
  `_observable_predicate`, `_self_second_person` (Layer B's renderers);
- quoted-speech verbatim rule (a quote body is never rewritten; degradation
  replaces, never paraphrases — the fragment form keeps loops.py's
  middle-words ellipsis);
- the perception prompt itself (prompts.py:571–830) is retired as a prompt
  and becomes the composer's spec sheet — nearly every paragraph in it
  (attenuation, FOV, focus/periphery, proximity/side, scent
  non-directionality, touch-resolves-at-the-surface, standing-contact
  continuity, RESTRAINT) is a rule the composer can enforce rather than
  request.

Why `_fallback_perception_views` is NOT the starting point, despite being the
no-LLM path: the comment at agents/perception.py:3302–3308 says it exactly —
the fallback admits a line on same-room alone, with no concealment check, no
hear_level, no per-observer vantage, so its *caller* must pre-filter the
dialogue log. It is a renderer that trusts its inputs, with the gates living
ad hoc upstream. The composer inverts that: gating is Layer A's single job,
the renderer is provably decision-free, and there is no caller who can forget
to pre-filter. That is the architectural lesson of the fallback, applied.

`observations` stop being regex-classified prose: they project directly from
the IR (channel, suddenness, intensity, directed_at_self are *known*, not
cue-guessed — the cue lists at agents/perception.py:335–420 measured 46.8%
of observations unclassifiable before the touch expansion). One invariant
must survive the change: each observation's `observed.text` is the rendered
sentence span, so the second representation still cannot exceed the first —
both now derive from the same gated IR, which makes the equality structural
instead of enforced-by-derivation.

---

## 2. Composition strategy

The failure mode to design against is not ugliness, it is *fixed shape*: a
constant field order (room → presence → acts → speech) reads like a status
report and — worse — puts constant tokens at the front of every view, which
is exactly where memory embedding and first-sentence retrieval look. The
consumers of a view are the character model, the memory bank, and the
narrator; none needs beauty, all need completeness, order, and
discriminability.

**1. Sentence planning over percepts.** Group percepts by source; order
groups by (suddenness desc, salience desc), with one hard exception: the
beat's event chain (declared sequence, dialogue in `dialogue_order`,
reactions) renders in declared/causal order inside its group — chronology is
authoritative, the invariant `_inject_onset_sequence` exists to protect.
Standing state (environment, contacts, poses) is interleaved by salience,
not prepended.

**2. Salience-driven omission — the single biggest anti-template move.**
"You are in the taproom." is rendered when the room *changed* (entered,
light shifted, first view of the scene) and omitted otherwise; a standing
contact is re-stated at intervals or on change, not every beat (the prompt's
RESTRAINT and A-STANDING-CONTACT rules become code, with the composer
tracking what the previous beat's view for this observer already carried —
readable from the prior turn's stored step, or a small per-observer ledger
in the step output). Omission is also the honest reading of perception:
habituation is real. The empty-view outcome ("nothing reached this mind")
remains `None`, as today.

**3. Aggregation.** Merge percepts sharing (source, channel) into
coordinated sentences ("The tall figure crosses to the shelf and lifts the
lantern"); fuse a presence percept with the source's first act
("A tall figure in a grey travelling coat pushes through the door" — one
sentence, not "You see a figure. The figure pushes..."). The appearance-paste
run-on problem the outcome pass documents (agents/perception.py:3800–3812)
is solved by planning first mention + short label + pronoun continuity
(`described_this_pass` generalized into a referent tracker) instead of
gluing paragraphs.

**4. Channel-appropriate register.** Per-channel lexical families, exactly
the shape `contact_sensation` already ships (pressure/weight/warmth/friction
for touch; fullness/stretch for interior): sight gets spatial verbs and
detail scaled by sight level and focus/periphery; unseen sound gets
"You hear ..." with a direction (sound is directional; smell is not —
rendered as intensity/gradient only, per the prompt rule the composer now
enforces); interoception in own-body register; vestibular/moved-while-unaware
keeps `_compose_residue_view`'s direction-less phrasing.

**5. Degradation rendering.** Fidelity picks the frame, never adds
information: `full` → declarative; `degraded` (shapes/muffled) → determiner
downgrade ("a figure", "movement at the edge of the light",
"A muffled voice: ..."); `fragment` → the middle-words ellipsis; `trace`
(muffled scent) → "a faint trace of ..."; `dazed` → percepts survive but
low-salience ones drop and a temporal-smear lead opens the view. Variant
sets within one site must be sense-equivalent — a muffled family never
contains a clear form — so wording variation can never be information-bearing.

**6. Deterministic lexical variation.** Every template site registers 3–6
equivalent surface forms; selection is
`hash(chat_id, turn_idx, perceiver_id, template_id, nonce)` — the exact
seeding discipline `_untargeted_order` (agents/loops.py:264–289) and weather
drift already use: stable across rerun-from-stage, free to land differently
on reroll, divergent between observers so two views of one event do not read
as one sentence photocopied.

**7. Authored prose is the color channel.** Room `notes` (authored/lore),
authored appearance summaries, and authored body-region detail are quoted as
written — they are the story's own voice, the observer is entitled to them,
and they are precisely what the composer cannot invent. This matters beyond
aesthetics: character models mirror the register of their inputs, and views
built solely from engine grammar would flatten the cast. What is lost
honestly: the model's ambient invention (a fire settling, mist on glass,
mood) is gone from views. That belongs to the narrator (still a model,
player-facing) and to authored room notes; a view is an instrument reading
for a mind, and the engine's own benchmark is measured gains, not plausible
prose (AGENTS.md §Genre boundary).

---

## 3. The prose-register problem

`commit.py:5510` (`episode_content = v`) mints each character's episodic
memory verbatim from their view; `search_memories` (memory.py:1719) ranks by
embedding+RRF over that content. If the composer emits uniform prose,
thousands of memories share prefixes and embed into a ball. Measured against
the corpus, the picture is different from the fear in two ways.

**Measured baseline (engine.db, read-only; scripts in appendix):**

| Metric | Value |
|---|---|
| Stored non-empty views | 9,351 across 4,526 perception steps (2,667 act / 6,560 outcome / 124 establish) |
| View length median / p10 / p90 | 764 / 31 / 1,540 chars |
| Views whose first sentence appears verbatim in another view | **73.1%** |
| All view sentences appearing verbatim more than once | **72.2%** of 76,576 |
| Views opening "you are in ..." | 15.3%; top opening 4-gram "you are in an" alone 9.7% |
| Opening-4-gram entropy | 8.83 bits over 2,162 forms |
| Episodic memories | 5,402 of 9,545 rows |
| Episodic rows sharing exact content with another row | **76.0%** |
| Top episodic openings | "i chose to attempted" 23.9% (the retired fallback formatter, cf. commit.py:5161's docstring), "you are in an" 15.4% |
| Episodic opening entropy | 5.74 bits over 773 forms |

Two conclusions. First, the model corpus is already heavily templated — the
cliff is not from artisanal prose down to templates; it is from ~5.7 bits of
opening entropy, a quarter of which is already the engine's own retired
deterministic formatter. Second, the engine has already lived the
worst case and written it down: 356 identical "You are in an unspecified
area." memories — 7.3% of one bank — described at commit.py:5511–5527 as
"retrievable memory carrying no information". A naive composer manufactures
that pathology at scale. So: **the risk is real, the naive form does sink
retrieval quality, and the mitigation is not optional.**

**Mitigations, in order of leverage:**

1. **Mint memory from the IR, not from view prose — mandatory, same change.**
   `episode_content = render_episode(percepts)`: first-person, past-tense,
   leading with the highest-salience percept, omitting standing environment
   unless it changed, filling `gist`, `key_phrases` and `entities` from typed
   fields (which the RRF aspects and lexical leg already consume). Firewall-
   safe by construction: it renders the *same* gated, fidelity-degraded IR
   the view rendered — never richer (rule and test in §5). This also fixes a
   defect the current design has anyway: today's memories inherit every
   injected boilerplate sentence and every repair scar.
2. **Salience-driven omission in views (§2.2)** removes the constant
   prefixes from the text embeddings see first. The composer can *guarantee*
   the discriminative content leads, which the model never did (15.3% of its
   views open with the room).
3. **Deterministic lexical variation (§2.6)** — honest assessment: it
   raises opening entropy and helps the lexical/RRF leg and human readers,
   but embedding models are built to collapse paraphrase families, so it
   contributes little to cosine discrimination. It is a readability measure,
   not a retrieval one.
4. **Mint-time hygiene**: the `_is_empty_view` suppression generalizes — a
   view whose percepts are all standing-state carries no episode; write
   nothing (the turn index still records the beat), and `event_key` already
   prevents same-event duplicates.

**Verdict.** The prose-register problem does not sink the approach, but it
is a hard coupling: shipping the composer while `commit.py:5510` still mints
episodes from view prose would measurably degrade the memory bank below its
already-poor baseline. The composer and IR-minted episodes must land
together, and the retrieval-discrimination comparison in §4 is the gate.

---

## 4. Verification plan — before wiring anything

Replay harness over the corpus, read-only (`mode=ro`, the `tools/fire_rates.py`
discipline; copy first if anything touches `search_memories`, which writes
`access_count`). For each of the 2,296 turns: reconstruct inputs from stored
steps and the pre-turn checkpoint (the exact recovery pattern
`_previous_open_group_continuity` already uses, agents/perception.py:171–257),
run Layer A + Layer B for every perceiver, and hold the result against three
different yardsticks — because a diff against stored model views measures
similarity to an artifact that *contains the defects the twelve passes exist
to repair* (self-narrated views, dropped heard lines — 30 of 1,549 same-room
lines never reached the player's view, agents/perception.py:3933–3934 —
invented dialogue, reversed motion). Matching it is not the goal.

**A. Fact fidelity against structured ground truth (the real quality bar).**
Derive the entitled-fact set per (turn, observer) from typed data alone:
lines the hearing gate delivers, overt acts the sight gate admits, standing
contacts, substance adds. Score **both** the composer output and the stored
model views on:
- delivered-line recall (composer must be 100% by construction — assert it);
- overt-act recall for sighted observers;
- violation counts, using the engine's own definitions of wrong run as
  metrics rather than repairs: identity-floor hits
  (`_scrub_unknown_identities`), self-narration hits
  (`_strip_self_narration`), invented-dialogue hits, unsupported-pose hits,
  channel violations (sight vocabulary for a no-sight source),
  `_inverted_motion_check`, disguise-term hits.
Acceptance: composer scores **zero** on every violation class where the model
corpus scores nonzero, at equal or better recall. This reuses audited
checkers, so the yardstick itself is already trusted.

**B. Retrieval discrimination (the §3 gate).** For a stratified sample of
chats, mint a shadow episodic bank from composer IR episodes; embed both
banks with the same provider; report per character:
(i) mean pairwise cosine within the bank (spread), (ii) share of rows within
0.95 cosine of a neighbor (collision rate — the corpus's verbatim-twin rate
of 76.0% is the baseline to beat), (iii) self-retrieval MRR: querying with a
turn's view must rank that turn's own episode first, and same-room
different-event episodes must not outrank genuinely related ones.
Acceptance: composer bank ≥ model bank on all three.

**C. Consumer-task and register judgment.** Similarity to model prose is
out; instead judge fitness for the consumers. Cheap tier: an LLM judge given
(entitled-fact set, view) — never (model view, composer view) side by side —
scoring completeness, contradiction, channel-register correctness, and
"reads as perception, not a report", blind to provenance, on ~200 stratified
beats of both corpora; per AGENTS.md's discipline, measure the judge's
false-positive rate on a hand-labeled slice before trusting it. Expensive
tier, sampled: replay a character step with the composer view substituted and
check the declared behavior still grounds its citations
(`_ground_observation_citations`, agents/character.py:817) and reacts to the
same facts — the view's actual job.

**D. Engine invariants.** Byte-identical output on identical inputs;
rerun-from-stage stable, reroll (nonce) varies; zero DB writes during
replay; wall-clock per pass in milliseconds against today's three
per-observer fan-outs per turn (`_PERCEPTION_FANOUT_WORKERS`,
agents/perception.py:1139–1194 — removing 3×N provider calls per turn is a
major latency and cost win and should be reported alongside quality).

Ship gate: A at zero violations over all 9,351 replayed views, B at parity
or better, C completeness within tolerance of the model with contradictions
strictly lower, D clean. Only then wire the stages.

---

## 5. Firewall consequences

**Where it gets strictly stronger.**
- No omniscient prose ever enters a mind's context: `resolved_event` leaves
  the perception path entirely, which closes the two documented
  prose-matching holes — the fresh-subject paraphrase that walks through
  `_redact_concealed_from_event` (agents/perception.py:3126–3140), and
  `_surface_translate_event`'s all-or-nothing fail-closed replacement
  (3079–3103).
- The identity floor moves input-side for every path, not just pass-1
  presence: a name an observer has not earned never exists in their IR, so
  the leak class "model wrote the canonical name anyway" is gone rather than
  scrubbed.
- The boundary stops depending on N separate model calls behaving; it is one
  code path with unit-testable admission (`_per_observer_model_views`'s
  structural boundary becomes a property of a pure function).
- A leak is now unambiguously an engine failure — which is what AGENTS.md
  says it always was; there is simply no model left to misattribute it to.

**Where it could accidentally get weaker — each needs a named defense.**
1. **Loss of defense in depth.** Today facts are gated at input AND scrubbed
   at output; deleting the scrubs removes the second layer, and the audit
   history says real leaks are guards that *cannot* fire (AGENTS.md, the
   "fail open and silent" consequence). Defense: keep the output-side
   checkers — identity scrub, self-narration, invented dialogue, disguise
   terms — as assertions in the replay harness and as cheap runtime
   tripwires that warn (they are deterministic and fast). A tripwire firing
   now means a composer bug, which is the honest severity.
2. **IR-minted memory outrunning the view.** If `render_episode` reads
   richer IR fields than the view rendered (a fragment percept's full quote
   body survives in `data`), memory exceeds perception. Rule: the episode
   renderer may consume only the same fidelity-degraded surface forms the
   view renderer consumed; test: every quote and identity token in the
   episode must appear in the view (token-level subset check, run in
   replay).
3. **Composer reading the raw scene.** Layer B taking a scene argument "for
   convenience" reopens the exact bypass `_observer_scene_payload` exists to
   close, now with no scrub behind it. Defense: the renderer's signature
   takes percepts and a seed, nothing else; enforce with a test that renders
   with a sentinel scene absent.
4. **Determinism as a meta-channel.** Fixed sentence shapes let a downstream
   model learn "engine-certain fact" vs "ambient color", and identical
   wording across observers correlates their views. Minor; per-perceiver
   seeds already diverge wording, and variant families are sense-equivalent
   so nothing factual rides the choice.
5. **Scope creep on shared texture.** Room notes reach every co-located
   perceiver today (`_room_notes_from_lore`, agents/common.py:1427); the
   composer must keep that scope, not extend notes to merely-visible
   adjacent rooms, and must keep mapping's lore emissions out of minds that
   are not in the room — the boundary is inherited, not new, but a rewrite
   is where inherited boundaries get dropped.
6. **The micro-loop seam.** `deterministic_micro_perception` and the
   composer must not become two opinions about one delivery rule. Unify:
   the micro loop emits percepts through the same Layer A predicates
   (`_delivery_ok` already shared), and outcome renders them, replacing the
   verbatim text append at agents/perception.py:3976–3987.

And the generative half of the principle survives untouched: the composer
subtracts nothing that was legitimately delivered, and inference remains the
character agent's job — the composer, like the prompt it replaces, renders
sensation and never the conclusion ("working out what a sensation means is
the character agent's job"). Nothing here makes minds conclude less; it makes
what they conclude *from* exact.

---

## Appendix — corpus probe method

Read-only probes (`sqlite3.connect("file:...engine.db?mode=ro", uri=True)`)
over `steps`/`variants` (active variants of the three perception keys) and
`memories`; scripts `corpus_probe.py` / `corpus_probe2.py` in the session
scratchpad. Sentence split on terminal punctuation; openings normalized to
lowercase alpha 4-grams; "verbatim twin" = exact string equality after
strip. 62 chats, 2,296 turns. Injector-shape share (sentences matching the
deterministic injectors' known forms: dialogue tags, "You see", "You
are/stand in", sensation clauses) is ~10.4% of all view sentences — a floor
on how much of today's "model prose" is already composer output.
