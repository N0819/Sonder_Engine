# Credits — external projects looked at, and what was taken

**This file must be updated in the same commit as anything it credits.** A
credit added later is a credit nobody can verify against the change it belongs
to. If a commit adopts an idea from a project below, extend that project's table
in the same commit; if it adopts an idea from a project not yet listed, add the
project in that commit too.

Sonder Engine is MIT (`../LICENSE`). Every project below is recorded with its
own licence, because the licence decides whether an *implementation* may be
copied. An **idea** — a rule, an invariant, a shape of a guard — is free to
take; the credit is courtesy and this file is where it is paid. An
**implementation** — lines of source, a schema, a data file — is governed by the
other project's licence, and the licence column is the answer to whether it may
be used at all.

Two neighbouring documents, so nothing is filed twice:

- [`guides/RESEARCH.md`](guides/RESEARCH.md) is the **literature** bibliography —
  papers and established work the architecture maps onto.
- [`../design_notes/10-prior-art.md`](../design_notes/10-prior-art.md) is a
  **prior-art survey** for one specific decision (the deterministic composer).
- This file is the register of **other people's projects**: what was read, under
  what licence, and what was drawn from it.

Rules that keep it honest:

1. **A survey is not a debt.** Where a project was read and nothing was adopted,
   the row says so. The job of this document is to be ready and accurate, not to
   manufacture obligations.
2. **Record what was actually taken, not what was admired.** "Confirmed a
   decision already made" and "supplied the rule" are different entries.
3. **Name the Sonder symbol or file the idea landed in**, the same rule
   [`UNBUILT.md`](UNBUILT.md) uses — cite a symbol, not a line number.
4. An idea rejected for a stated reason is worth keeping in the table. The
   reason is the reusable part.

---

## Directive

| | |
|---|---|
| **URL** | https://github.com/MentallyQuill/Directive |
| **Author** | Josh Shapiro (`MentallyQuill`) |
| **Licence** | **MIT** — Copyright (c) 2026 Josh Shapiro. Implementation may be reused with attribution; ideas are free either way. |
| **What it is** | A pre-alpha SillyTavern extension running a persistent Star Trek command RPG ("Ashes of Peace"). JavaScript ES modules, no build step, deterministic reducers over an LLM host it does not own. |
| **Surveyed** | 2026-08-14, at clone HEAD. |

### What was looked at

`docs/architecture/` (`V1_GAMEPLAY_ARCHITECTURE.md`, `SEMANTIC_AUTHORITY.md`,
`STORY_SETTLEMENT.md`, `PEOPLE_AND_RELATIONSHIPS.md`, `MISSION_STATE.md`,
`FAIR_DISCOVERY.md`, `EPISODE_EVALUATOR_ROUTING.md`, `UI_RUNTIME_SURFACE.md`),
`docs/technical/` (`PLAYER_TURN_SEQUENCE.md`,
`MODEL_CALLS_AND_PROVIDER_ROUTING.md`, `DIRECTIVE_DATASETS.md`,
`HOST_INTEGRATION_MANUAL.md`, `STORY_DIRECTOR_TURN_FLOW.md`),
`docs/authoring/`, and `docs/source/Directive_Game_Design_Document.md`.

Source read directly: `src/runtime/state-delta-gateway.mjs`,
`src/mission/v1/duty-report-planner.mjs`,
`src/mission/v1/mission-package-linter.mjs`, `src/story/episode-boundary.mjs`,
and the layout of `src/mission/v1/`, `src/story/`, `src/people/`.

Its central boundary — *model proposes, deterministic runtime commits, narrator
continues* — is the same boundary Sonder draws at `persist/commit.py`, arrived at
independently. Most of what follows is Directive holding that boundary in a
place Sonder has not yet held it.

The adoption ORDER, the cost of each, and the firewall verdict per item are
shelved separately in
[`design/PROPOSAL_DIRECTIVE_ADOPTIONS.md`](design/PROPOSAL_DIRECTIVE_ADOPTIONS.md).
This table stays the register of what was read and what was taken.

### Ideas drawn from it

**Nothing has been adopted yet.** This table is the shortlist as surveyed; each
row moves to *taken* only in the commit that lands it, and gains the Sonder
symbol it landed in.

| Idea | Where it lives in Directive | What it would answer in Sonder | Status |
|---|---|---|---|
| A commit proposal **declares the state roots it may mutate**, and the gateway diffs before/after and hard-errors on a root nobody declared (`DIRECTIVE_V1_STATE_UNDECLARED_MUTATION`) | `src/runtime/state-delta-gateway.mjs` (`normalizeDomains`, `ensureAuthorizedChanges`) | Sonder's commit domains are named but their blast radius is unverified — nothing catches a domain writing outside itself | Not adopted |
| **Base-revision compare-and-swap** on a monotonic `stateCustody.revision`, with a distinct persistence-conflict error that **refuses to roll back** when in-memory state has already moved on | same file (`assertRevision`, `persistCommit`) | [`UNBUILT.md`](UNBUILT.md) §4.4 Gap 6 verbatim — "prepared commits touching shared canon should carry a base revision… Verified absent: no revision concept in `core/db.py`, `persist/commit.py` or `core/frames.py`" | Not adopted |
| **Commit idempotency by content-hashed proposal id** held in a bounded recent-commit ring, so a replay is a no-op rather than a double write | same file (`proposalId`, `alreadyCommitted`) | Generalises Sonder's per-event `event_key` from memory rows to the commit itself | Not adopted |
| **Fair Discovery**: an authored fact that is true but unnarrated stays `discoverable`; it may become known only through a **delivery route** naming who can deliver it, what capability makes them credible, when delivery is appropriate, and what disclosure counts | `docs/architecture/FAIR_DISCOVERY.md`; `src/mission/v1/duty-report-planner.mjs` (`selectPendingDutyReport`, `selectReporter`) | The authored half of the channel rule. Sonder has the transport half and better (`story/carriers.py`, `story/couriers.py`, `story/artifacts.py`) but no way to say *this fact must reach someone, and here is the legitimate mouth*. Directly answers §1.16's residual 5 — "the seed asserts a conclusion whose channel does not exist" | Not adopted |
| **Delivery custody**: a disclosure is pending → assigned → visibly delivered in narration → accepted → materialised as knowledge, bound to an exact source; invalidating the source removes the knowledge and everything derived from it | `src/mission/v1/duty-report-delivery.mjs`, `deliveredDutyReportIds` | Makes knowledge a **derivation over surviving evidence** rather than a status flag — the same correction `AGENTS.md` already records for background claims ("ratifying is a WRITE, not a status flag"), taken one step further | Not adopted |
| **Authored-content reachability lint**: a static check that a fact which is meant to become knowable has at least one policy by which it can, and that every required objective has a reachable terminal fixture | `src/mission/v1/mission-package-linter.mjs` (`lintEvidenceCoverage`, `lintScenarioReachability`) | The missing third lint. `tools/scene_lint.py` finds two live ledgers contradicting each other; `tools/fire_rates.py` measures whether a mechanism fired in history. Neither asks the static question — *can this authored thing ever reach anyone?* A knowledge tag no cast member holds, an empty `psychology.drive` (`CLAUDE.md`), and a lore entry gated out of every range all fail that way and fail silently | Not adopted |
| **Names are display facts, never identity keys.** An emergent person gets a stable runtime id minted from branch + accepted-message lineage; two records are never guessed to be the same person | `docs/architecture/PEOPLE_AND_RELATIONSHIPS.md`; `src/story/story-settlement.mjs` | Independent corroboration of the fix §1.17 already prescribes ("key on the scene ENTITY id"), plus the discipline Sonder's `_fold_duplicate_presences` currently breaks: do not merge, mint at the encounter | Not adopted |
| **Creation threshold**: a person record exists only from an accepted **direct encounter in which they gave the player a usable name**; a name heard in narration about someone else is insufficient | `docs/architecture/PEOPLE_AND_RELATIONSHIPS.md` | §1.8 — promotion seeds are minted from the objective `resolved_event` with no perception filter and written `provenance: "witnessed"`. This is the missing filter stated as a rule | Not adopted |
| **Typed episode boundaries with a trusted-source table**: a closed list of hard boundary codes, each valid only from a named engine authority (a `mission-transition` boundary is not assertable by a model), beside a soft model-proposed boundary that must cite significance criteria and effect ids | `src/story/episode-boundary.mjs` (`EPISODE_HARD_BOUNDARY_CODES`, `SOURCE_KINDS_BY_CODE`, `EPISODE_SIGNIFICANCE_CRITERIA`) | §2.6 (scene-boundary coherence pass, verified absent) and the **contract** §2.16 asks for — "the turn-range semantics are emergent, not contractual… an index built on that would rest on behaviour a prompt edit could silently revoke" | Not adopted |
| **Significance predicate**: a scene enters durable story memory only on a lasting change, consequential disclosure, commitment, relationship turning point, future-constraining decision, lasting cost, or unresolved consequence. Routine exchanges produce an *insignificant-settlement receipt* and no entry | `src/story/episode-boundary.mjs` (`EPISODE_SIGNIFICANCE_CRITERIA`); `docs/architecture/STORY_SETTLEMENT.md` | A closed, auditable vocabulary beside Sonder's continuous `salience`. The receipt-for-nothing is the part worth having: an explicit record that the beat was judged and found ordinary | Not adopted |
| **Structured-output certification fingerprint**: native JSON-schema mode is used only while a fingerprint over the exact provider/model/completion-mode/policy configuration remains certified; changing any of them invalidates it, and explicit native mode **fails before transport** rather than silently downgrading | `docs/technical/MODEL_CALLS_AND_PROVIDER_ROUTING.md` | Generalises `providers.prompt_cache_enabled_for`'s allowlist — same problem (a provider capability that fails the turn when wrongly assumed), solved by measurement instead of a hand-kept list | Not adopted |
| **Clue resilience**: an important revelation must be reachable by more than one route, so a mission cannot collapse because the player did not select an unmarked intended verb | `docs/source/Directive_Game_Design_Document.md` §13.4 | A constraint on delivery routes above; folds into Fair Discovery rather than standing alone | Not adopted |

### Ideas deliberately rejected, and why

| Idea | Reason it is not for Sonder |
|---|---|
| **One batched model call proposing every person's observations** — "Utility is never called per person" | This is the information firewall inverted. Sonder's per-mind separation *is* the structural boundary; `_per_observer_model_views` was removed in favour of a deterministic composer precisely so no shared call could exist. Batching minds into one prompt is the one change that must never be made, however much §1.40 wants call multiplicity down |
| **Story Settlement as a single semantic chronology**, with People a read-only projection of it | One omniscient episode ledger collapses memory, perception and objective truth into one context. Sonder's memory is per-mind by thesis. Take the boundary detection; never the ledger |
| **The People model** — one qualitative posture, one open matter, no relationship score | Strictly thinner than what Sonder already has (`mind/affect.py`, `mind/theory_of_mind.py`, `mind_models` with credence, the active-hypothesis sheet). Nothing to take |
| **Command Bearing** — a reserved/armed/committed/refunded metacurrency | A genre mechanic. `Design.md` § Genre-agnostic substrate puts world-specific law in lorebooks, and Sonder has no currency to two-phase-commit |
| **Mission definitions as the campaign unit** (objectives, clocks, `closeWhen`, terminal dispositions, transitions) | A quest system. The reusable part — consequences on a clock, place obligations — Sonder already has in `world/living_world.py` and `world/mechanics.py`. The part worth extracting is the Fair Discovery slice, not the graph |
| **Accepted-pair custody** — nothing is truth until the player's next message accepts the selected swipe | Directive's answer to hosting inside a chat log it does not own. Sonder already has a stronger boundary: `persist/commit.py` as sole persistence, a checkpoint before mutation, one active variant per step, one atomic outer transaction. The half that is *not* covered — editing a past turn invalidates derived state and it is **replayed deterministically, regenerating no prose** — is worth having, and belongs with the gateway rows above |
| **Keyword spoiler linting** (`DEFAULT_MISSION_SPOILER_TERMS`) | Prose matching as a boundary, with everything §3.1 and §1.18 say about it. The *reachability* half of that linter is the part that survives; the word list is not |
| **UI surface discipline** — "each fact has one primary home", "any new visible element must name which surface it replaces" | Genuinely good, and Sonder already carries the equivalent doctrine (`AGENTS.md`: two representations of one fact is the shape that produced `rekey_place_claims`; §1.12's nine-payload-keys attention budget). Nothing to import |
| **Outcome ladder** (success / success with cost / setback with opportunity / impossible under current conditions) | A prompt vocabulary, not a mechanism. §1.12 records that every added payload marker makes the previous one less likely to be read, and `AGENTS.md` § Genre boundary requires a measured gain before a new layer earns its seam |

### Non-runtime content, noted for completeness

`docs/source/` and `packages/` are Star Trek campaign content (a ship bible, a
senior-staff character bible, a campaign script). MIT covers the repository's
own text; the underlying setting is not the author's to license and none of it
is of interest here. Nothing from `docs/source/` beyond the design principles
cited above was read for adoption.

---

## grb-systems (Geometric Resource Bridging LLC)

| | |
|---|---|
| **URL** | https://github.com/grb-systems |
| **Author** | Geometric Resource Bridging LLC, Rhode Island |
| **Licence** | **Mixed.** Five repositories are MIT (`grb-foundations`, `grb-naps`, `grb-rd`, `grb-hinge`, `grb-lae`); the remaining twenty-two are **AGPL-3.0**. The AGPL is a strong copyleft with a network-use clause — Sonder is MIT, so no AGPL *implementation* may be incorporated without relicensing the whole engine. Ideas remain free; source does not. |
| **What it is** | 27 repositories of conceptual specifications for "geometric approaches to human–AI interaction": interaction posture, recursive doctrine, lexicon accretion, context-reinjection reduction, allocation topology, safety architecture. Prose specifications, not software. `grb-foundations` says so itself, and the disclaimer is honest: publication "should not be interpreted as evidence of implementation completion or empirical validation unless explicitly stated." |
| **Surveyed** | 2026-08-14. |

### What was looked at

The organisation profile, the full repository listing with licences, and the
README and complete file tree of **all 27 repositories**.

Every repository contains exactly `LICENSE` and `README.md`. One
(`grb-foundations`) has a third file, also prose. Across roughly 300 KB of text
there is no source file, test, dataset, executable line, or JSON Schema; there
are three YAML fragments, one of which has every value blank. Two repositories
document directory trees (`schemas/`, `telemetry/`, `examples/`, a named
`state-capsule.schema.json`) that are not present. `grb-laei`, whose stated
subject is telemetry for measuring whether any of this fires — the one thing
that would have been of direct use — is a 193-byte README of one sentence.

### Ideas drawn from it

**Nothing has been adopted, and nothing is shortlisted.**

The corpus is about posture between one human and one assistant across a long
conversation. It has nothing on multi-agent orchestration, information
partitioning between minds, or narrative state, which are the parts of Sonder
that are hard. The one adjacent theme, `grb-crrp`'s compact "state capsule" for
resuming a session without reinjecting the transcript, restates a problem Sonder
has already solved against measurement — `mind/memory.py` consolidation, the summary
window, `llm/prompt_cache.py`, and the payload-budget work registered at §1.25 and
§2.16 — and solves it for a single shared context between one human and one
model, which is the shape Sonder exists to refuse.

One phrase is worth keeping without owing anything for it: `grb-dhfd` names
*fluency diverging from structure* — output reading better while its structure
degrades, so prose quality is an actively misleading health signal. That is the
same shape as the engine's own measured finding that literal guards fail more
often the better the model writes. The naming is theirs; the detector, the
measurement and the fix are already Sonder's.

Recorded here so the survey is not repeated. **The licence split matters
practically**: 22 of the 27 are AGPL-3.0. The ideas are unprotectable and there
are none worth taking; the wording is protected, and none of it should be pasted
into this repository's documentation.

---

## Antonio (typeface)

**Source:** <https://github.com/googlefonts/antonioFont> · Copyright 2013 The
Antonio Project Authors
**Licence:** SIL Open Font License 1.1 — the full text travels with the files at
[`../static/fonts/OFL.txt`](../static/fonts/OFL.txt).

The **first** entry in this register that is an implementation rather than an
idea, so the licence column is doing real work here for the first time. OFL 1.1
permits bundling and redistribution inside a larger work, including a
commercial one, provided the font files keep their copyright and licence notice
and are not sold on their own. Nothing in it reaches Sonder's own MIT terms.

| Taken | Where it landed | Note |
|---|---|---|
| The typeface itself, two woff2 subsets (latin, latin-ext), variable 400–700, 42KB total | `static/fonts/antonio-*.woff2`, declared by the `@font-face` pair at the head of `static/themes.css` and consumed through `--ui-font` in the `lcars` theme | Bundled, **never linked**. The engine runs local and offline; a font fetched from a CDN is missing exactly under the conditions this application is built for. `tests/test_ui_themes.py::test_lcars_ships_its_own_condensed_face` pins both the files and the absence of any `fonts.googleapis.com` / `fonts.gstatic.com` reference |

Why a font at all, recorded because it is the reusable part: the `lcars` theme
had **asked** for `Antonio, Oswald, Roboto Condensed, Arial Narrow` since it was
written, and a machine with none of the four installed resolved that stack to
generic `sans-serif`. LCARS is a typographic system before it is a colour one,
so the entire frame was doing console work under a face that reads as a
settings panel — a defect invisible to anyone whose machine happened to have one
of the fallbacks. A named font stack is a request; only a bundled file is a
guarantee.

Nothing else from Google Fonts is vendored, and the OFL applies to this family
only.

---

## Change log for this file

| Date | Change |
|---|---|
| 2026-08-14 | Created. Directive and grb-systems surveyed; nothing adopted from either yet. |
| 2026-08-14 | Antonio added — the register's first adopted *implementation*, bundled under OFL 1.1 for the `lcars` theme. |
