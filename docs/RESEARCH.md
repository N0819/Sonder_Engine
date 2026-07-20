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

### 1.1 Belief revision — `theory_of_mind.py`

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

### 1.2 Time travel and paradox — `paradox.py`

- **Novikov self-consistency principle** — Friedman, J., Morris, M. S.,
  Novikov, I. D., Echeverria, F., Klinkhammer, G., Thorne, K. S., & Yurtsever,
  U. (1990). *Cauchy problem in spacetimes with closed timelike curves.*
  Physical Review D, 42(6), 1915–1930.
  <https://link.aps.org/doi/10.1103/PhysRevD.42.1915> — named at
  `paradox.py:51-53` as the shape of future pre-commit deflection.
- **Doctor Who, "Father's Day"** (S1E8, 2005, Paul Cornell) — named at
  `paradox.py:6-8` as the reference beat for a violated fixed point (fiction,
  not research).

### 1.3 Information-retrieval algorithms implemented in `memory.py`

The hybrid memory retriever names and implements three standard IR techniques.

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

### 1.4 Interoperability specs and infrastructure (industry prior art)

- **SillyTavern character-card spec V2/V3** — PNG cards with base64 JSON in
  `chara`/`ccv3` tEXt chunks (`importers.py`), plus World Info import
  (`static/js/editors.js`).
  [V2](https://github.com/malfoyslastname/character-card-spec-v2) ·
  [V3](https://github.com/kwaroran/character-card-spec-v3).
- **sqlite-vec** — Alex Garcia's vector-search SQLite extension (`memory.py`).
  <https://github.com/asg017/sqlite-vec>.
- **Prompt caching** — Anthropic `cache_control` breakpoints and OpenAI
  prefix caching (`prompt_cache.py`).
  [Anthropic](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching)
  · [OpenAI](https://platform.openai.com/docs/guides/prompt-caching).

Apart from the above, the repo contains no bibliography, arXiv links, DOIs, or
"inspired by" attributions — including throughout `Design.md`, `AGENTS.md`, and
`docs/`. Everything in Part 2 is a reconstructed mapping.

---

## 2. Conceptual / implicit research

Established work the architecture instantiates without citing it.

### 2.1 Agent memory streams with reflection
`memory.py` — episodic rows scored by salience + confidence + recency, with
autobiographical-summary consolidation archiving low-salience memories.
- Park, J. S., et al. (2023). *Generative Agents: Interactive Simulacra of
  Human Behavior.* UIST 2023. <https://arxiv.org/abs/2304.03442>
- Packer, C., et al. (2023). *MemGPT: Towards LLMs as Operating Systems.*
  <https://arxiv.org/abs/2310.08560>

### 2.2 Retrieval-augmented generation
`agents/mapping.py` + `memory.py` — semantic + cue + lexical + exact retrieval
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
`theory_of_mind.py`; the `second_order` belief kind; characters may hold false
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
(`agents/perception.py`, sense gating in `spatial.py`, zone splits in
`spatial_frames.py`).
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
states (`theory_of_mind.py`, `Design.md`).
- Ortony, A., Clore, G. L., & Collins, A. (1988). *The Cognitive Structure of
  Emotions.* Cambridge University Press (OCC model).
- Gratch, J. & Marsella, S. (2004). *A domain-independent framework for
  modeling emotion.* Cognitive Systems Research, 5(4), 269–306 (EMA).

### 2.10 Tabletop RPG resolution
`schemas.py` (`DiceSpec`, `ResolutionCheck`: actor/ability/difficulty/opposed
rolls, seeded); the Director mirrors GM adjudication.
- Wizards of the Coast, *D&D 5th Edition SRD 5.1*, CC-BY-4.0.
  <https://www.dndbeyond.com/srd>

### 2.11 Structured output with repair loops
`llm_quality.py` (strict JSON, semantic validation, repair retries), Pydantic
schemas (`schemas.py`), provisional-until-committed (`commit.py`). Established
industry practice (Instructor, Guardrails-AI, provider structured-output
features); no single canonical paper.

### 2.12 Transactions as the coherence substrate
One outer transaction per turn with savepoints and whole-turn rollback on
domain failure (`commit.py`).
- Gray, J. & Reuter, A. (1992). *Transaction Processing: Concepts and
  Techniques.* Morgan Kaufmann. Applied via SQLite
  (<https://www.sqlite.org/transactional.html>).

---

## Verification status

- **Web-verified this session:** Ross/Lepper/Hubbard 1975; Johnson/Hashtroudi/
  Lindsay 1993; Friedman–Novikov et al. 1990; Cormack et al. 2009 (RRF);
  Carbonell & Goldstein 1998 (MMR); Park et al. 2023; Wu et al. 2023 (AutoGen);
  Packer et al. 2023 (MemGPT); Riedl & Bulitko 2013; sqlite-vec; SillyTavern
  card specs V2/V3.
- **Canonical, cited from established knowledge (not re-fetched):** Asch 1946;
  Ebbinghaus 1885; Pearl 1988; Hintikka 1962; Fagin et al. 1995; Premack &
  Woodruff 1978; Wimmer & Perner 1983/85; Kaelbling et al. 1998; Genette 1972;
  OCC 1988; Gratch & Marsella 2004; Lewis et al. 2020; Mateas & Stern 2003;
  CAMEL / MetaGPT; Kosinski 2023; Gray & Reuter 1992; Robertson & Zaragoza 2009.
- **Industry practice / no academic citation:** JSON repair-loop validation;
  lorebook/World Info format; provider ecosystem.
