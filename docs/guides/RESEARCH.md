# Research and Prior Art

This document sources the research the Sonder Engine draws on. It has two
parts:

1. **Explicitly referenced** — work the code or docs name directly (with the
   file where it appears).
2. **Conceptual / implicit** — established research the architecture
   instantiates but does not cite. These mappings are reconstructed after the
   fact, not attributions the original authors made.

Line numbers drift; treat file paths as the durable anchor and grep for the
named symbol if a line has moved. A verification note appears at the end.

---

## 1. Explicitly referenced research

### 1.1 Belief revision — `mind/theory_of_mind.py`

The module docstring (`theory_of_mind.py:9-25`) names five findings from the
psychology of how minds revise beliefs about other people. They drive the
per-kind confidence caps, plasticity, and half-lives in
`_TOM_CONFIDENCE_CAPS` / `_TOM_PLASTICITY` and the `decayed_confidence()`
decay model.

- **Belief perseverance / self-perception** — Ross, L., Lepper, M. R., &
  Hubbard, M. (1975). *Perseverance in self-perception and social perception:
  Biased attributional processes in the debriefing paradigm.* Journal of
  Personality and Social Psychology, 32(5), 880–892.
  <https://www.semanticscholar.org/paper/561546cdf8508e4883317ea09bc48ef6b2499a7b>
  — why `trait`/`identity` beliefs get low plasticity and resist
  single-instance revision.
- **Primacy in impression formation** — Asch, S. E. (1946). *Forming
  impressions of personality.* Journal of Abnormal and Social Psychology,
  41(3), 258–290. doi:10.1037/h0055756.
- **Ebbinghaus-style forgetting** — Ebbinghaus, H. (1885). *Über das
  Gedächtnis* (trans. 1913, *Memory: A Contribution to Experimental
  Psychology*). — unreinforced beliefs decay; see `decayed_confidence()` and
  per-kind half-lives.
- **Source monitoring** — Johnson, M. K., Hashtroudi, S., & Lindsay, D. S.
  (1993). *Source monitoring.* Psychological Bulletin, 114(1), 3–28.
  doi:10.1037/0033-2909.114.1.3.
  [PDF](https://memlab.yale.edu/sites/default/files/files/1993_Johnson_Hashtroudi_Lindsay_PsychBull.pdf)
  · [PubMed](https://pubmed.ncbi.nlm.nih.gov/8346328/) — provenance is tracked
  per memory (`MEMORY_PROVENANCE`, `memory.py:51`).
- **"Explaining away"** — term from Pearl, J. (1988). *Probabilistic Reasoning
  in Intelligent Systems.* Morgan Kaufmann. Used here in the colloquial
  belief-revision sense: a competing claim suppresses but does not erase a
  prior belief.

The epistemic confidence-cap ladder (`observation` 1.0 → `identity` 0.35,
`theory_of_mind.py:49-52`; mirrored in `Design.md`) is an original design
device, not a cited result.

### 1.2 Time travel and paradox — `world/paradox.py`

- **Novikov self-consistency principle** — Friedman, J., Morris, M. S.,
  Novikov, I. D., Echeverria, F., Klinkhammer, G., Thorne, K. S., & Yurtsever,
  U. (1990). *Cauchy problem in spacetimes with closed timelike curves.*
  Physical Review D, 42(6), 1915–1930.
  <https://link.aps.org/doi/10.1103/PhysRevD.42.1915> — named at
  `paradox.py:51-53` as the shape of future pre-commit deflection.
- **Doctor Who, "Father's Day"** (S1E8, 2005, Paul Cornell) — named at
  `paradox.py:6-8` as the reference beat for a violated fixed point (fiction,
  not research).

### 1.3 Information-retrieval algorithms implemented in `mind/memory.py`

The hybrid memory retriever names and implements four standard IR techniques.

- **Reciprocal Rank Fusion** — Cormack, G. V., Clarke, C. L. A., & Büttcher,
  S. (2009). *Reciprocal rank fusion outperforms Condorcet and individual rank
  learning methods.* SIGIR '09, 758–759.
  [ACM](https://dl.acm.org/doi/10.1145/1571941.1572114) ·
  [PDF](https://cormack.uwaterloo.ca/cormacksigir09-rrf.pdf) — the
  `weight / (60 + rank)` fusion in `_rrf_add` (`memory.py:977`), fusing
  semantic / cue-vector / lexical / exact rankings (`memory.py:1013-1016`).
- **BM25** — Robertson, S. & Zaragoza, H. (2009). *The Probabilistic Relevance
  Framework: BM25 and Beyond.* Foundations and Trends in IR, 3(4). Used via
  SQLite FTS5 `bm25()`; see the [FTS5 docs](https://www.sqlite.org/fts5.html).
- **Maximal Marginal Relevance** — Carbonell, J. & Goldstein, J. (1998). *The
  use of MMR, diversity-based reranking for reordering documents and producing
  summaries.* SIGIR '98, 335–336.
  [abstract](https://people.eng.unimelb.edu.au/ammoffat/sigir98/abstracts/carbonell.html)
  — the λ≈0.82 diversity re-ranker at `memory.py:1046`.
- **The signed hashing trick** — Weinberger, K., Dasgupta, A., Langford, J.,
  Smola, A., & Attenberg, J. (2009). *Feature hashing for large scale
  multitask learning.* ICML '09, 1113–1120.
  [ACM](https://dl.acm.org/doi/10.1145/1553374.1553516) — `providers.cheap_embed`
  is exactly this: character 3- and 4-grams hashed into 256 dimensions by
  CRC32, with bit 16 of the hash choosing each contribution's sign, then L2
  normalised. It is the FALLBACK used whenever no `embeddings` provider role
  is configured — and therefore, in practice, the only embedding most installs
  have ever had. Worth being precise about what that buys: it is a fuzzy
  *lexical* signature, not a semantic one, so the two vector lists it feeds are
  lexical evidence fused with two other lexical signals. Measured on live data
  (a memory's `gist` is the model's own paraphrase of its `content`, which makes
  gist→content a real paraphrase-retrieval test): **recall@1 85%, recall@5 94%,
  median rank 1** over 200 queries against 600 memories. That holds up because
  the query `character_memory_context` builds is dominated by the character's
  current perception — concrete prose thick with the proper nouns and places
  that recur in the memories worth retrieving, which is the regime n-gram
  hashing is strong in.

  **That number is the easy case, and it must be read with its companion.** A
  gist shares its content's proper nouns, so gist→content rewards lexical
  overlap. Re-measured on the hard case — eight real memories from a 441-memory
  bank, queried by paraphrases written to preserve meaning while AVOIDING the
  memory's own vocabulary, which is what recalling something worded differently
  actually is — crc32 scores **recall@1, @5 and @20 all 0%, at a median rank of
  228 of 441**. That is indistinguishable from random. So the honest summary is
  not "better than it sounds": it is a strong lexical retriever and a
  non-existent semantic one, and the whole of semantic recall is the headroom a
  real embeddings provider would open.

### 1.4 Interoperability specs and infrastructure (industry prior art)

- **SillyTavern character-card spec V2/V3** — PNG cards with base64 JSON in
  `chara`/`ccv3` tEXt chunks (`story/importers.py`), plus World Info import
  (`static/js/editors.js`).
  [V2](https://github.com/malfoyslastname/character-card-spec-v2) ·
  [V3](https://github.com/kwaroran/character-card-spec-v3).
- **No ANN index — dense retrieval is an exhaustive in-process scan.**
  `search_memories` loads one character's rows and scores them in NumPy
  (`_cos` over the stored `embedding` and `cue_embedding` blobs), fusing the
  result with BM25 and exact-match rankings. A `sqlite-vec` index was declared
  here once and never wired; it was **deleted rather than completed** in alpha
  6.3, for two reasons worth recording as prior art rather than as an
  omission. First, the ANN query could filter only on `chat_id`/`char_id`,
  while the scan applies two predicates before ranking — a turn cutoff (a mind
  deciding turn N must not retrieve how turn N resolved) and frame visibility
  — and those are precisely the selective predicates ANN indexes carry badly.
  Second, the scan is not a bottleneck at this workload: memories accrue at
  ~3.5 rows per turn per character, and a full scan measures 16 ms at a real
  story's worst case (442 rows), 126 ms at ~1,000 turns and 709 ms at ~10,000,
  against an LLM call in the same beat measured in seconds. Correctness
  constraints, not scale, decided it. See `docs/UNBUILT.md` §1.4.
- **Prompt caching** — Anthropic `cache_control` breakpoints and OpenAI
  prefix caching (`llm/prompt_cache.py`).
  [Anthropic](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching)
  · [OpenAI](https://platform.openai.com/docs/guides/prompt-caching).

### 1.5 Runtime specifications (external standards)

- **SIGMA Runtime Standard (SRS) — SRIP-14, "Retrieval and Memory Integration
  Layer (RMI)", §XXII *Retrieval as Perturbation Source*.** Sigma Stratum
  Research Group, Public Draft v0.3 (2026-05-20). Licensed **CC BY 4.0**, with
  an Independent Implementation Safe Harbor permitting independent
  implementation of the public normative requirements.
  Documentation set: <https://github.com/sigmastratum/documentation> ·
  <https://sigmastratum.org/> · Architecture reference: Tsaliev, E. (2025),
  *SIGMA Runtime Architecture v0.1*,
  doi:[10.5281/zenodo.17703667](https://doi.org/10.5281/zenodo.17703667).

  The idea taken: standard retrieval fetches what is most relevant *now*, which
  by construction reinforces whatever a mind is already doing — so a second,
  bounded mode exists for when a runtime detects sustained convergence and low
  behavioural variance, retrieving *contrasting* rather than matching material
  and marking it non-authoritative. Sonder's repetition guards
  (`agents/character.py`'s `_self_line_refrain` and `_first_verbatim_repeat`,
  `psychology_runtime.cognitive_absorption`'s plateau habituation) are all
  suppressive: they tell a stuck character "not that" and never "how about
  this". SRIP-14 §XXII names the missing half.

  What is NOT taken, and why: the bulk of SRIP-14 governs *external* retrieval
  — RAG sources, cross-origin provenance, cross-runtime exchange artifacts —
  which the information firewall forbids reaching a character context at all.
  Any adaptation here draws contrast from the character's own memory, so the
  provenance machinery that dominates the spec is inapplicable rather than
  merely unimplemented. SIGMA's control vocabulary ("attractor", "drift",
  "semantic load budget") is also deliberately not adopted: this repo names
  only quantities it can compute, and Sonder's equivalents already exist as
  measured state (absorption, `sustained_beats`, stress activation).

  *With thanks, and independently built.* Sonder is not an official or
  certified Sigma integration and nothing here speaks for Sigma Stratum — the
  insight is theirs, the adaptation and any mistakes in it are ours. Noted so
  neither project is mistaken for the other, not to hold the work at arm's
  length: it is a genuinely good piece of thinking and it is cited because it
  changed what got built.

### 1.6 Deterministic perception and the view composer

The composer (`agents/composer.py`) and the spatial derivation layer replace
a per-observer LLM call with code. Two published findings changed what got
built; both are **ideas only** — no code was read, taken, or ported, and
neither project is a dependency.

- **Lee, Goel & Ramchandran, "Quantifying Positional Biases in Text
  Embedding Models", arXiv:[2412.15241](https://arxiv.org/abs/2412.15241).**
  Embedding models over-weight a text's opening sentence. This is why
  `render_episode` leads with the beat's events and puts a room change
  last: a memory that opens with "I was in the Long Hall" every time
  embeds as *the Long Hall* and retrieves as a near-duplicate of every
  other beat there. Cited at the site it governs
  (`agents/composer.py:1014`). Measured effect on this corpus:
  verbatim-twin rate within the memory bank 14.6% → 0.4%.

- **Li, Zhou, He, Wang, Yang & Li, "On the Sentence Embeddings from
  Pre-trained Language Models" (BERT-flow), EMNLP 2020,
  arXiv:[2011.05864](https://arxiv.org/abs/2011.05864).** Cosine
  similarity tracks surface overlap more than meaning. So the *varying*
  content has to dominate a minted memory by length, not merely be present
  in it — which is why an episode omits unchanged standing state entirely
  instead of appending a delta to a fixed frame.

Read as leads and **deliberately not used**, recorded because the ideas
were on the table while this was designed:

- **Angband's message aggregation (`mon-msg.c`) — GPL.** Not read; no code,
  no code structure, no naming. The engine does count indistinguishable
  bodies into one line ("Three indistinct figures are close by",
  `_render_presence_group`), but the rule that decides *when* aggregation
  is legal comes from Sonder's own firewall principle — merging two
  percepts must never launder an information boundary, so the group splits
  by fidelity before anything is joined. That rule stands without reference
  to any other codebase, and a GPL implementation of a similar idea cannot
  be borrowed from into an MIT repo regardless.
- **TADS 3 `displaySchedule` and the adv3 occluder concept — proprietary,
  derivatives prohibited.** Nothing read, derived, or modelled. Both ideas
  it was cited for — re-announce on change rather than on presence, and a
  gating pass that may only remove — were independently specified in
  `design_notes/03` before the lead existed, and are implemented from
  scratch. Corroboration only.
- **Curveship (reported ISC, unverified).** Source not read, licence not
  checked. Its realiser stays a lead for future work on Layer B; nothing
  from it is in the current implementation.

Everything else in the deterministic-perception work derives from the
owner's own design notes, the existing MIT-licensed Sonder code, and
aggregate vocabulary counts from the owner's own corpus. Python standard
library only.

### 1.7 The off-screen charter simulation (`world/charter*.py`)

Added 2026-08-21 with the `offscreen` branch prototype
(`docs/design/DESIGN_INSTITUTIONS_AND_UPKEEP.md`). **Only work that actually
shaped the code appears here**, with what was taken, what was refused, and
what it measured. Two sources were read in full and are cited in the module
docstrings; everything else is marked for how it was read.

#### 1.7.1 Versu — social practices (read in full; cited in code)

Evans, R., & Short, E. (2014). *Versu — A Simulationist Storytelling System.*
IEEE Transactions on Computational Intelligence and AI in Games, 6(2),
113–130. Read directly.

Cited in `world/charter_practice.py`; the architecture it supplies is that
module and `world/charter_author.py`.

Taken:

- **A social practice is "a type of recurring social situation"** whose *"main
  function … is to describe the actions the agents can do in that situation."*
  Practices offer; they never control. *"The practice provides the agent with
  a set of suggested actions, but it is again the agent himself to decide
  which action to perform, using utility-based reactive action selection."*
- **Concurrency, and the union of affordances.** Versu's dinner party runs
  eating, the political conversation, a rising flirtation and a response to
  spilled soup at once: *"The agent's set of options is the union of the
  affordances from each of the practices he is participating in."*
- **Acting spawns practices** — *"old practices are deleted, or new practices
  are spawned"* — which is the anti-convergence engine, and the reason the
  loop cannot run dry.
- **Role-agnostic authoring.** Practices name roles, never characters, which is
  the same discipline `tests/test_charter_genre.py` enforces here.
- **One architecture for chosen and authored conduct**: *"The same
  architecture is used for player choice — except the Action Instances are
  sent directly to the user-interface, rather than to the Decision Maker."*
  That sentence is the whole of §12a's "no handoff, only a change of author".

Measured on adoption: the social layer had converged and died — 103
interactions across 100 beats, all in the first nine, 91 consecutive empty
beats. After practices: 5,432 interactions, zero empty beats, min 35 / median
47 per beat.

#### 1.7.2 Talk of the Town — character knowledge phenomena (read in full)

Ryan, J., & Mateas, M. (2017). *Simulating Character Knowledge Phenomena in
Talk of the Town.* In S. Rabin (Ed.), **Game AI Pro 3**, ch. 37, pp. 433–447.
CRC Press. Read directly.

Referenced in `world/charter_talk.py`. Shaped `charter_mind`, `charter_talk`
and `charter_news`.

Taken:

- **Knowledge implantation at the boundary.** They refuse to simulate
  knowledge across 140 years of world generation and instead implant the
  beliefs that would believably be ingrained. Independent arrival at this
  repo's `O(re-contact)` cost rule, and the strongest evidence for it.
- **An evidence typology** across origination, reinforcement, deterioration
  and termination — observation, transference, confabulation, lie, implant;
  declaration; mutation; forgetting.
- **Belief strength as the sum of its evidence**, decaying with time and
  scaled by the recipient's affinity for the source and the source's own
  confidence.
- **Salience as one number** driving observation, propagation *and*
  deterioration together.

Refused, with the reason:

- **The hand-authored per-attribute belief mutation graph** (`black→brown
  0.75`, `black→red 0.15`…). Reference-valued facets need no such table:
  misremembering becomes pointing at the wrong referent, which is one rule
  rather than one table per attribute.
- **Candidate beliefs** and **declaration-reinforces-belief** are taken as
  designs and not yet built; registered rather than implemented.

Its own measured tuning failure is why this package treats authored rates as
a hazard: across 100+ live performances of *Bad News* they found *"a
prevalence of misremembered home addresses, including cases where characters
could not remember where their own parents lived,"* fixed by turning one
mutation rate down. They also concede the method *"is not very
computationally efficient."*

Corrected here: their reported **~60 s per turn** at ~500,000 belief facets
was cited in early design discussion as the cost of the work. It is not — it
is a 2016-era implementation cost, and they name the cause (string-valued
facets mutated through authored graphs, plus salience summed over every
entity each conversant knew). The same sweep measured **845 ms** in plain
Python here. The number that had been quietly setting the ambition was wrong
by ~70×.

#### 1.7.3 Read and deliberately not used

- **Neighborly** (Johnson-Bey, MIT) — <https://github.com/ShiJbey/neighborly>.
  Repository read directly 2026-08-21. Talk of the Town's explicit successor
  as a reusable Python/ECS library. **Archived 2026-04-07 and unmaintained**,
  so it stands as a reference implementation to read for structure, never a
  dependency. Nothing from it is in the code.
- **Ensemble / Comme il Faut** (UC Santa Cruz; *Prom Week*) —
  <https://github.com/ensemble-engine/ensemble>. Identified as the social-
  physics lineage Versu descends from. **Superseded 2026-08-27 by §1.7.6,
  which reads it properly.** The line below is kept because the reason it was
  skipped is itself a finding: it was recorded as "the lineage Versu descends
  from", and Versu had already been read, so it looked like ancestry rather
  than a live source. What it actually holds is the half Versu does not —
  Versu says what a character MAY do in a situation, CiF says why they WANT to
  and what it costs them afterwards. Original note: *Not read in depth;
  nothing taken.*

#### 1.7.6 Comme il Faut / Ensemble — social physics (read 2026-08-27)

McCoy, J., Treanor, M., Samuel, B., Reed, A. A., Mateas, M., & Wardrip-Fruin,
N. (2011). *Prom Week: Social Physics as Gameplay.* FDG 2011. And Samuel, B.,
Reed, A. A., et al. (2015). *The Ensemble Engine: Next-Generation Social
Physics.* FDG 2015. Read via the FDG papers and Guimaraes, Santos & Jhala
(2017), *CiF-CK: An Architecture for Social NPCs in Commercial Games*, IEEE
CIG — the last read in full, being the clearest statement of the data model.

Read to answer one question: what makes a background population feel deep and
BELIEVABLE rather than merely busy. Nothing below is built yet; this section
is the argument, and the gaps it names are measured, not supposed.

**The architecture.** Four components — Social State, Characters, Social
Exchanges, Trigger Rules. *"NPCs perceive the Social State around them and try
to change it to accomplish their Social Goals."* The Social State is itself
four representations: **social networks** (directional numeric links, every
character to every other, on axes such as coolness/friendliness/romance),
**relationships** (discrete symmetric ties — friends, dating, enemies), a
**cultural knowledge base** (what this world treats as normal), and a **social
facts knowledge base** — the record of what has actually passed between
people. A Character holds a name, permanent **traits**, temporary **status**,
and a prospective memory of desires toward specific others. A Social Exchange
holds an intent, *initiator influence rules*, *responder influence rules*, and
effects; volition is *"the sum of true rules that pertain"*, and the responder
independently accepts or rejects on its own rules.

**What this repository already has, under other names.** More than expected.
`world/charter_social.py`'s judgments are a directional five-axis social
network (trust/warmth/fear/respect/suspicion) and its `DEFAULT_SIGNALS` with
`social_norms.signals` is a cultural knowledge base with an author override.
`world/charter_practice.py` is the exchange layer, from Versu rather than CiF
but the same seam, and `offers` computing utility per affordance is volition
under another name. Since 2026-08-27 `experiences` is a real social facts
store. So the shapes are largely present.

**The gap, and it is one line.** `charter_practice._state_of` builds what
every affordance may reason over, and it is `bodies, figures, minds, needs,
regard, blame, at`. Not `experiences`. Not `judgments`. Not `served_beside`,
not `commitments`. **A Charter character deciding what to do cannot see
anything that has ever passed between them and the person in front of them.**
CiF's entire claim to believability is the opposite of this: an exchange is
scored against the social facts, so a refusal has a reason and the reason is a
specific remembered thing. Prom Week's own worked example is Simon refusing to
carry Cassandra's gossip because his friendship with Naomi outweighs her
influence — legible, cited, and false in this engine, where the same character
would decide from need levels and a scalar regard.

**Taken, as design; ordered by depth bought.** None of these are built.

1. **Volition reads history.** Widen `_state_of` to carry the pair's shared
   record and let affordances weight on it. This is the change that turns
   "acted because the state permitted it" into "acted because of what
   happened", and everything else here is smaller.
2. **Ordinary evidence, not only failure.** The five-axis network exists and
   measures EMPTY across four charters of a real story, because judgments form
   only from witnessed events and every event the sim can emit is an
   institutional failure. CiF's networks move on ordinary exchanges. Same
   finding as `charter_run`'s amended docstring, with a name.
3. **Discrete relationships beside the numeric axes.** *(BUILT 2026-08-27.)*
   CiF keeps both on purpose: numbers drive scoring, labels drive legibility,
   and a label is what a narrator can state plainly and a reader can hold.
   `world/charter_social.py`'s tie layer is six labels — `close`, `at_odds`,
   `wary`, `afraid_of`, `looks_up_to`, `familiar` — each one a reading of an
   axis already there plus the holder's own directed regard and its own
   `served_beside` count, stored sparsely as the charter's `ties` and VALIDATED
   on every normalize so a label the numbers no longer support is deleted
   rather than merely discouraged. DIRECTIONAL, unlike CiF's: two people do not
   share a head, so A may hold B `close` while B holds A merely `familiar`, and
   the unrequited tie is the more generative one. The signed labels needed
   design 2 to be reachable at all — before it, the largest axis anywhere in a
   stressed simulated year of `twin_towns(40)` was 0.142 against a form
   threshold of 0.30. See `docs/UNBUILT.md` §1.99 for what a HEALTHY
   institution still produces, which is `familiar` and nothing else.
4. **Status as temporary traits.** Charter has needs and felt state and
   nothing socially temporary — newly raised, in disgrace, owed a favour.
   These are what make a beat read as motivated rather than merely caused.
5. **Trigger rules.** *"Trigger Rules can be fired at any point and have
   cascading effects in the Social State."* Charter has none: an act changes
   state and nothing fires off the change, which is why the social layer needs
   prodding to stay in motion.

**Refused, with the reason.** CiF's rulebase is hand-authored at scale — *"over
5,000"* social considerations, *"over 40"* exchanges, 20+ templated dialogue
scenes per outcome. That authoring burden is the thing this engine exists to
avoid: prose belongs to the model over cited surfaces, not to a template
library. Take the SCORING discipline and leave the script.

**On believability, which is the whole reason to read them.** Their finding is
that believability comes from MANY SMALL WEIGHTED REASONS rather than one
strong rule — five thousand considerations exist so that no single factor
dominates any decision. The corollary is the failure mode Talk of the Town
already taught this repository (§1.7.2): one mis-tuned rate produced characters
who could not remember where their own parents lived. Depth and believability
are the same mechanism read from two ends — a decision is believable when the
reason behind it is specific, remembered, and one of many.

#### 1.7.4 Consulted in summary; informed decisions rather than code

Read via search summaries and secondary sources only — **not** read at the
source, and recorded at that strength deliberately.

- **Shadow of Mordor's Nemesis system** (Monolith, 2014). Two ideas carried:
  a population whose ranks actually churn (*"promotion, demotion and death —
  causing the balance of power to organically shift"*), and depth concentrated
  on the individuals the player has actually met. Informed `stood` and
  `world/charter_promote.py`; the observation that charter bodies never change
  rank remains open work.
- **Dwarf Fortress** (Adams). Confirms the equilibrium problem is universal
  rather than ours — a fortress that cannot fall becomes *"very conservative
  and very boring"* — and that its own answer, retiring the fort to worldgen
  scale, is an admission rather than a solution. Its personality model
  (facets 0–100, values −50…50, needs separated from stress, and *conflicting*
  facets and values as characterisation) was noted and not implemented,
  because `mind/psychology_runtime.py` already owns that layer.
- **RimWorld** (Ludeon). The owner's original framing for this work: needs as
  drifting quantities, and "most ticks should be boring." Both survive. Two
  things were **refused**: its storyteller injecting incidents from outside
  causality — the "insertion" shape `DESIGN_INSTITUTIONS_AND_UPKEEP.md` §13
  rejects — and tuned per-body mood meters, refused on measurement rather than
  taste (`charter_needs.mood` correlates with `pressure` at r = 0.9939; see
  the `f2b31c5` commit message).
- **FAtiMA Toolkit** (Mascarenhas et al.). Rule-based OCC appraisal generating
  all 22 OCC emotions. Its main effect here was a decision **not** to build:
  the character tier already owns appraisal, so `world/charter_feel.py` calls
  `mind/psychology_runtime.resolve_hedonic`/`resolve_stress` rather than
  modelling affect beside them.

#### 1.7.5 The strongest influences were internal

Recorded because it is true and easily lost: more of this design came from
existing Sonder modules than from any outside source.

- **`story/carriers.py`** — *"when a mechanically fired event has a non-empty
  public `witnessed` surface, only registered characters physically at that
  location acquire that surface."* `charter_news.witness` is that rule one
  tier down, and `advance_carriers` reading `world_events` directly is why the
  wiring plan needs no bridge between two event vocabularies.
- **`world/routines.py`** — a pure function of the clock that never ticks and
  never writes. The standard for the recompute-versus-commit split in
  `charter_drift` / `charter_run`.
- **`agents/composer.py`'s `observations_from_render`** — a second
  representation *derived* so it cannot expand the information budget. The
  precedent for news claims living in the one `minds` store discriminated by
  `kind`, and for facets as an index rather than a parallel store.
- **`docs/design/DESIGN_PSYCHOLOGY_AS_PRESSURE.md`** — psychology as pressure
  rather than premises, which is exactly the relationship between the
  background tier and the character tier.

Apart from §1.6's single in-code citation at `agents/composer.py:1014` and
§1.7's citations in `world/charter_practice.py` and `world/charter_talk.py`,
the repo contains no bibliography, arXiv links, DOIs, or "inspired by"
attributions — including throughout `Design.md`, `AGENTS.md`, and `docs/`.
Everything in Part 2 is a reconstructed mapping.

---

## 2. Conceptual / implicit research

Established work the architecture instantiates without citing it.

### 2.1 Agent memory streams with reflection
`mind/memory.py` — episodic rows scored by salience + confidence + recency, with
autobiographical-summary consolidation archiving low-salience memories.
- Park, J. S., et al. (2023). *Generative Agents: Interactive Simulacra of
  Human Behavior.* UIST 2023. <https://arxiv.org/abs/2304.03442>
- Packer, C., et al. (2023). *MemGPT: Towards LLMs as Operating Systems.*
  <https://arxiv.org/abs/2310.08560>

### 2.2 Retrieval-augmented generation
`agents/mapping.py` + `mind/memory.py` — semantic + cue + lexical + exact retrieval
fused and injected into prompts; lorebook activation follows the World Info
pattern.
- Lewis, P., et al. (2020). *Retrieval-Augmented Generation for
  Knowledge-Intensive NLP Tasks.* NeurIPS 2020.
  <https://arxiv.org/abs/2005.11401>
- Industry: NovelAI Lorebook / SillyTavern World Info
  (<https://docs.sillytavern.app/usage/core-concepts/worldinfo/>).

### 2.3 Multi-agent LLM orchestration with role separation
The whole pipeline (`agents/runtime.py`; Director/Perception/Character/Narrator
boundaries in `AGENTS.md`).
- Wu, Q., et al. (2023). *AutoGen.* <https://arxiv.org/abs/2308.08155>
- Li, G., et al. *CAMEL.* <https://arxiv.org/abs/2303.17760> ·
  Hong, S., et al. *MetaGPT.* <https://arxiv.org/abs/2308.00352>

### 2.4 Theory of mind and false belief
`mind/theory_of_mind.py`; the `second_order` belief kind; characters may hold false
beliefs legitimate only relative to their evidence.
- Premack, D. & Woodruff, G. (1978). *Does the chimpanzee have a theory of
  mind?* Behavioral and Brain Sciences, 1(4), 515–526.
- Wimmer, H. & Perner, J. (1983). *Beliefs about beliefs.* Cognition, 13(1),
  103–128; Perner & Wimmer (1985) on second-order beliefs.
- LLM context: Kosinski, M. (2023). *Theory of Mind May Have Spontaneously
  Emerged in Large Language Models.* <https://arxiv.org/abs/2302.02083>

### 2.5 Epistemic logic — knowledge vs. belief
The core thesis: objective truth, perception, memory, inference, belief, and
narration as distinct non-collapsible layers (`Design.md`; the "epistemic
firewall").
- Hintikka, J. (1962). *Knowledge and Belief.* Cornell University Press.
- Fagin, R., Halpern, J. Y., Moses, Y., & Vardi, M. Y. (1995). *Reasoning About
  Knowledge.* MIT Press.

### 2.6 Partial observability
Perception as a per-observer filter over objective state
(`agents/perception.py`, sense gating in `world/spatial.py`, zone splits in
`world/spatial_frames.py`).
- Kaelbling, L. P., Littman, M. L., & Cassandra, A. R. (1998). *Planning and
  acting in partially observable stochastic domains.* Artificial Intelligence,
  101(1–2), 99–134. (The game-design analogue is fog-of-war.)

### 2.7 Interactive narrative and drama management
The Director owns causality but not psychology or narration; contestable vs.
asserted player declarations (`Design.md`).
- Riedl, M. O. & Bulitko, V. (2013). *Interactive Narrative: An Intelligent
  Systems Approach.* AI Magazine, 34(1), 67–77.
  <https://ojs.aaai.org/aimagazine/index.php/aimagazine/article/view/2449>
- Mateas, M. & Stern, A. (2003). *Façade: An Experiment in Building a
  Fully-Realized Interactive Drama.* GDC 2003.

### 2.8 Narratological focalization
The Narrator renders only the player-facing slice and cannot reveal unperceived
facts (`agents/narration.py`) — restricted internal focalization enforced
mechanically.
- Genette, G. (1972/1980). *Narrative Discourse: An Essay in Method.* Cornell
  University Press.

### 2.9 Appraisal-based emotion
Characters emit appraisals; emotional reads are volatile, appraisal-linked
states (`mind/theory_of_mind.py`, `Design.md`).
- Ortony, A., Clore, G. L., & Collins, A. (1988). *The Cognitive Structure of
  Emotions.* Cambridge University Press (OCC model).
- Gratch, J. & Marsella, S. (2004). *A domain-independent framework for
  modeling emotion.* Cognitive Systems Research, 5(4), 269–306 (EMA).

### 2.10 Tabletop RPG resolution
`llm/schemas.py` (`DiceSpec`, `ResolutionCheck`: actor/ability/difficulty/opposed
rolls, seeded); the Director mirrors GM adjudication.
- Wizards of the Coast, *D&D 5th Edition SRD 5.1*, CC-BY-4.0.
  <https://www.dndbeyond.com/srd>

### 2.11 Structured output with repair loops
`llm/llm_quality.py` (strict JSON, semantic validation, repair retries), Pydantic
schemas (`llm/schemas.py`), provisional-until-committed (`persist/commit.py`). Established
industry practice (Instructor, Guardrails-AI, provider structured-output
features); no single canonical paper.

### 2.12 Transactions as the coherence substrate
One outer transaction per turn with savepoints and whole-turn rollback on
domain failure (`persist/commit.py`).
- Gray, J. & Reuter, A. (1992). *Transaction Processing: Concepts and
  Techniques.* Morgan Kaufmann. Applied via SQLite
  (<https://www.sqlite.org/transactional.html>).

---

## Verification status

- **Web-verified this session:** Ross/Lepper/Hubbard 1975; Johnson/Hashtroudi/
  Lindsay 1993; Friedman–Novikov et al. 1990; Cormack et al. 2009 (RRF);
  Carbonell & Goldstein 1998 (MMR); Park et al. 2023; Wu et al. 2023 (AutoGen);
  Packer et al. 2023 (MemGPT); Riedl & Bulitko 2013; SillyTavern
  card specs V2/V3.
- **Canonical, cited from established knowledge (not re-fetched):** Asch 1946;
  Ebbinghaus 1885; Pearl 1988; Hintikka 1962; Fagin et al. 1995; Premack &
  Woodruff 1978; Wimmer & Perner 1983/85; Kaelbling et al. 1998; Genette 1972;
  OCC 1988; Gratch & Marsella 2004; Lewis et al. 2020; Mateas & Stern 2003;
  CAMEL / MetaGPT; Kosinski 2023; Gray & Reuter 1992; Robertson & Zaragoza 2009;
  Weinberger et al. 2009 (feature hashing).
- **Industry practice / no academic citation:** JSON repair-loop validation;
  lorebook/World Info format; provider ecosystem.
- **External specification, read directly:** SIGMA SRS / SRIP-14 (RMI),
  documentation set dated 2026-05-28 — license terms and §XXII read from the
  document itself. Built in alpha 6.1 as `memory.contrast_memory` — see §1.5
  for what carries over and what deliberately does not.
- **Verified for §1.7 (the charter simulation), 2026-08-21:** Evans & Short
  2014 (Versu, IEEE TCIAIG 6(2)) and Ryan & Mateas 2017 (Talk of the Town,
  Game AI Pro 3 ch. 37) were both **read at the source** — the PDFs, page by
  page — and every quotation in §1.7.1 and §1.7.2 was transcribed from them
  rather than from a summary. The Neighborly repository was fetched directly.
  Nemesis, Dwarf Fortress, RimWorld and FAtiMA are marked §1.7.4 precisely
  because they were **not**: those came from search summaries and secondary
  articles, and no quotation from them should be treated as verified.

  One correction belongs on the record because it changed a design decision:
  Talk of the Town's ~60 s per turn was, in early discussion here, treated as
  the cost of simulating character knowledge. It is the cost of *their 2016
  implementation*, which the chapter itself explains. Measuring the same work
  produced 845 ms. An unchecked number from a real source is still an
  unchecked number, and it had been setting this project's ambition.

- **Verified for §1.6 (deterministic perception):** Lee/Goel/Ramchandran
  arXiv:2412.15241; Li et al. EMNLP 2020 (BERT-flow). Both re-checked
  against the papers before adoption.

  Stated plainly because it is the reason that re-check happened: the
  prior-art survey that produced these two also produced several claims
  that turned out to be **fabricated** — attributions, figures and quoted
  passages for work that says no such thing. They were retracted, and only
  the findings that survived independent verification appear above. Nothing
  enters this file on the strength of a summary; if a claim here cannot be
  checked against the source, it should be removed rather than softened.
