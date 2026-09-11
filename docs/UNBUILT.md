# Unbuilt work — the register

Everything designed, proposed, or found-and-deferred that is **not in the code
today**, in one register split into category files. Compiled 2026-07-29 against
alpha 6.1 by re-verifying every claim in every design and audit document against
source.

**This index and its linked category files are the only worklist.**
`CHANGELOG.md` and the git log are the history; the surviving design notes keep
the *argument* for an item and are linked from it, but they no longer carry
their own status lists — those drifted, which is why this register exists.

It also **replaces five audit documents**, which were erased once their live
findings were folded in here: the 2026-07-19 architecture audit, the
information-pipeline leak sweep, the enterprise_d_v2 audit backlog, the
Fable adversarial-review follow-ups (all six closed), and the place-graph review.
Roughly 60% of the pipeline sweep and all six review items had already shipped,
and a reader taking those documents at face value would have chased about forty
closed findings. What survived is linked below, with enough mechanism detail to
act on without them. Their reasoning is in git history and in `CHANGELOG.md`.

**Partially re-verified 2026-07-31** against alpha 6.3. Entries confirmed still
true against source this pass: §1.1, §1.3, §1.6, §1.11, §1.13, §2.3, §2.5,
§3.2 B1-residual (§2.14's `fStrList` was confirmed then and has since been
converted at eight of its ten sites). Entries **corrected** this pass: §1.13
(the enum is real, but the validation seam the pipeline uses does not enforce
it), and the present-beat citation entry, whose premise was stale — the ids it
asked for already existed and already reached the payload; only the prompt
never learned. That one has since landed and is deleted per rule 1; the record
is `Design.md` § Structural debt #1. §1.4 (`sqlite-vec`) was
re-decided and **landed** — its either/or was wrong, since wiring the vector
index would have regressed the information firewall — and is deleted per rule 1;
`docs/guides/RESEARCH.md` §1.4 carries the reasoning. The embedding-model
cliff that entry pointed at (§1.15, "changing the embedding model silently
erases semantic recall") is also gone: a provider is configured, the bank is
migrated, and the mismatch guard and the resumable rebuild it prescribed both
exist — `memory.embedding_bank_status`, `rebuild_embeddings`,
`rebuild_checkpoint_embeddings`, `repair_pending_embeddings`. See `Design.md`
§ Changing the embedding model is safe. Everything else in the register
still carries its 2026-07-29 verification date and should be re-checked before
being acted on — rule 2 exists because the register's claims go stale faster
than the code does, and two of the ten checked this pass had.

Rules that keep it honest:

1. Delete an entry in the same commit that lands it. Do not mark it done here.
2. Cite a symbol, not a line number. Line citations in this repo's docs went
   stale within days — that is most of why the audits had to go.
3. If an entry has sat untouched through three releases, either promote it or
   admit it is parked and move it to §8.
4. Findings keep their original ids (P-, F-, S3-, X-, Gap-) so old commit
   messages and test docstrings still resolve.

---

## How this register is organized

Work is filed once under its primary system owner. Cross-cutting entries use the
category that owns the next concrete change. The numeric prefix still records
status, so existing references such as `docs/UNBUILT.md §1.84` resolve through
the locator below.

| Category | Scope |
|---|---|
| [Pipeline and orchestration](UNBUILT_PIPELINE.md) | Director authority, stage contracts, narration, reconciliation, and beat execution. |
| [Perception and presentation](UNBUILT_PERCEPTION.md) | Information admission, senses, concealment, rendering, and the player-facing page. |
| [World, space, and physical state](UNBUILT_WORLD.md) | Scenes, rooms, geometry, movement, bodies, objects, conditions, garments, and material causality. |
| [Identity, naming, and language](UNBUILT_IDENTITY.md) | Names, recognition, address, promotion identity, personas, and language-pack boundaries. |
| [Characters, memory, and psychology](UNBUILT_CHARACTERS.md) | Character decisions, dialogue, memory retrieval, beliefs, affect, relationships, and goals. |
| [Living world and institutions](UNBUILT_LIVING_WORLD.md) | Background presences, Charter, off-screen simulation, institutions, creatures, and population continuity. |
| [Story planning and authoring](UNBUILT_PLANNING.md) | Writers' Room, predictive staging, planned entities, structure generation, and authoring tools. |
| [Platform, persistence, and tooling](UNBUILT_PLATFORM.md) | Storage, restore, multiplayer, schemas, extensions, diagnostics, tests, cost, and maintenance. |
| [Parked](UNBUILT_PARKED.md) | Deliberately unscheduled work and removal candidates. |

## Status key

### 1. Known defects

Live bugs and unfinished corrections — places the engine is currently wrong,
not places it is merely thin.

**Rule 3 is overdue here, and this note is the debt.** §1.2, §1.3, §1.5, §1.13,
§1.17, §1.19 and both surviving §1.24 bullets were all found at alpha 6.0–6.9;
the tree is at alpha 9.6, so each has sat through ten-plus releases untouched.
Rule 3 gives two answers and neither is "leave it here": promote it, or admit it
is parked and move it to §8. The next reader to touch one of those entries owes
one of those answers for each of the eight.

### 2. Roadmap

Features the architecture intends and has not built. Stable ids preserve the
former value-per-risk ordering within each category; items 2.2–2.3 repay the
structural debt in
[`../Design.md`](../Design.md) § Structural debt.

### 3. Information-pipeline leaks still open

Ids are the erased pipeline sweep's own. Severity vocabulary: **leak** (a mind
receives what it did not earn) / **degradation** (a mind is denied what it did
earn, or is told something false about its own perception) / **corruption**
(durable state made wrong) / **latent** (mechanism real, crossing model-gated).

**The single largest item in this register**, on which the pipeline sweep and the
architecture audit converged independently: **structured signals with stable
identity, rather than prose matching, as the concealment and identity boundary.**
Everything in §3.1 is a symptom of its absence, and `grep signal_id` returns
nothing repo-wide. See §4.2.

### 4. Architecture gaps

From the erased 2026-07-19 audit. Its Gap 1 was conceptual, Gap 2 and Gap 7 are
now largely closed, and Gap 4 is partial. These are what remain. Its Priority 3
is done bar one item, and Priority 4 is done — the suite it measured at 527 tests
now stands at 3,112. Gap 3 / Priority 0 (overlapping physical authorities) is
gone too, and was settled the OPPOSITE way to the direction it recommended: it
asked for the scene to be generated from the normalized tables, and
consolidation made the frame-scoped `world.scene` blob the sole runtime
authority with `world_entities` a derived projection and `world_placements`
decommissioned. The matrix it said was "verified absent" is published in
`docs/guides/DATABASE.md` and pinned by `tests/test_world_authority_consolidation.py`,
whose `test_world_placements_have_no_runtime_writer` fails if the model forks
again.

### 5. Deferred backlog

From the erased enterprise_d_v2 40-turn audit backlog. Its P1 (pronoun fidelity)
and P3 (dialogue dedupe) shipped, as did the variant/alias half of P7. Each §5
entry in the category files is written to be resumable cold: symptom, root
cause, fix, test.

### 6. Design-note residuals

Features their design notes argue for that are not built. The note holds the
argument; only the gap is listed in the register.

### 7. Experiments not yet run

Moved to
[`docs/experiments/MEASUREMENT_BACKLOG.md`](experiments/MEASUREMENT_BACKLOG.md)
§1 on 2026-08-19. An unrun experiment is unfinished work, not a broken thing —
which is the argument for keeping it with the evidence rather than in a defect
register.

### 8. Parked

Not scheduled and not committed to a phase. See the
[parked register](UNBUILT_PARKED.md).

## Entry locator

### Pipeline and orchestration

[Open the category file.](UNBUILT_PIPELINE.md)

**1. Known defects**

- [§1.1 — The specialist contract: BUILT, with two parts still open](UNBUILT_PIPELINE.md#unbuilt-1-1)
- [§1.1a — Conduct authority: what the guards still do not reach](UNBUILT_PIPELINE.md#unbuilt-1-1a)
- [§1.7 — JSON validation stalls cost beats](UNBUILT_PIPELINE.md#unbuilt-1-7)
- [§1.11 — `ctx.warnings` reaches the pipeline drawer but not the story reader](UNBUILT_PIPELINE.md#unbuilt-1-11)
- [§1.11a — Pacing still decides who may ANSWER, and that half is unmeasured](UNBUILT_PIPELINE.md#unbuilt-1-11a)
- [§1.13 — `ActionStage` is classified and the resolve path never reads it](UNBUILT_PIPELINE.md#unbuilt-1-13)
- [§1.32 — A region assertion has an owner only by slot position](UNBUILT_PIPELINE.md#unbuilt-1-32)
- [§1.33 — An interpret that says nothing costs two model calls](UNBUILT_PIPELINE.md#unbuilt-1-33)
- [§1.49 — Three things the prompt-card split made visible and did not change](UNBUILT_PIPELINE.md#unbuilt-1-49)
- [§1.59 — A channel census over persisted `state_diff`s cannot see `phase_sources`](UNBUILT_PIPELINE.md#unbuilt-1-59)
- [§1.60 — The interpret sheet and `agents/common.py` state opposite rules about concealed speech](UNBUILT_PIPELINE.md#unbuilt-1-60)
- [§1.69 — Three other sentence splitters still have no abbreviations](UNBUILT_PIPELINE.md#unbuilt-1-69)
- [§1.70 — Narrator repetition: what the change-key fix reached, and what it did not](UNBUILT_PIPELINE.md#unbuilt-1-70)
- [§1.73 — The chronological-padding brake stops the inner loop only](UNBUILT_PIPELINE.md#unbuilt-1-73)
- [§1.77a — Speaking turns and the page: what the utterance fix reached, and what it did not](UNBUILT_PIPELINE.md#unbuilt-1-77a)
- [§1.82 — Two narrator checks that fire and buy nothing](UNBUILT_PIPELINE.md#unbuilt-1-82)
- [§1.101 — A handover the scene has no record of is refused out loud, and still refused](UNBUILT_PIPELINE.md#unbuilt-1-101)
- [§1.112 — The process clamp reads a generic word in a clothing sentence](UNBUILT_PIPELINE.md#unbuilt-1-112)
- [§1.119 — The declared room word against the sources: two owner decisions the PA3 repair did not take](UNBUILT_PIPELINE.md#unbuilt-1-119)
- [§1.122 — What the 2026-09-05 presentation and plan fixes left open](UNBUILT_PIPELINE.md#unbuilt-1-122)
- [§1.126 — Every cut a play run proposed, audited: not one field was dead](UNBUILT_PIPELINE.md#unbuilt-1-126)
- [§1.133 — A declaration of stillness is read as silence, and the walk carries on (PQ6)](UNBUILT_PIPELINE.md#unbuilt-1-133)
- [§1.135 — The turn row, the narrator's contract and the guards (lane H, 2026-09-05)](UNBUILT_PIPELINE.md#unbuilt-1-135)
- [§1.154 — What the Director could not parse is filed as a thing to be built](UNBUILT_PIPELINE.md#unbuilt-1-154)
- [§1.156 — The player is never told what their own attempt DID](UNBUILT_PIPELINE.md#unbuilt-1-156)
- [§1.159 — One beat, read at every stage: what a stage-by-stage audit of turn 82 found and did not fix](UNBUILT_PIPELINE.md#unbuilt-1-159)

**2. Roadmap**

- [§2.18 — The orchestrated Director: what is left after it landed](UNBUILT_PIPELINE.md#unbuilt-2-18)

**3. Information-pipeline leaks still open**

- [§3.1 — Prose matching as a boundary](UNBUILT_PIPELINE.md#unbuilt-3-1)

**5. Deferred backlog**

- [§5.1 — P2 — ambient repetition, deterministic](UNBUILT_PIPELINE.md#unbuilt-5-1)
- [§5.3 — P5 — route player-authored NPC acts through the character reaction](UNBUILT_PIPELINE.md#unbuilt-5-3)

**6. Design-note residuals**

- [§6.3 — Greeting-seeded openings — `GREETING_IMPORT_DESIGN.md`](UNBUILT_PIPELINE.md#unbuilt-6-3)

### Perception and presentation

[Open the category file.](UNBUILT_PERCEPTION.md)

**1. Known defects**

- [§1.18 — The fallback is doing all the work](UNBUILT_PERCEPTION.md#unbuilt-1-18)
- [§1.22 — One window answers most beats, because every view describes the same person](UNBUILT_PERCEPTION.md#unbuilt-1-22)
- [§1.24 — What the enclosure investigation found and did not fix](UNBUILT_PERCEPTION.md#unbuilt-1-24)
- [§1.44 — A concealed feature can leak through an attire description](UNBUILT_PERCEPTION.md#unbuilt-1-44)
- [§1.50 — Residuals from the speaking-device repair (chat 80)](UNBUILT_PERCEPTION.md#unbuilt-1-50)
- [§1.68 — A barrier's appearance, and knowing how it works, are both in the room note](UNBUILT_PERCEPTION.md#unbuilt-1-68)
- [§1.80 — Residuals from the change tier](UNBUILT_PERCEPTION.md#unbuilt-1-80)
- [§1.93 — A contact with an object is narrated as a contact with a person](UNBUILT_PERCEPTION.md#unbuilt-1-93)
- [§1.109 — A spoken line shorter than four characters is invisible, and takes the next one with it](UNBUILT_PERCEPTION.md#unbuilt-1-109)
- [§1.116 — The 2026-09-05 play runs: the perception-delivery classes](UNBUILT_PERCEPTION.md#unbuilt-1-116)
- [§1.117 — A sound that HAPPENS has no channel, and `running` is the only word for it](UNBUILT_PERCEPTION.md#unbuilt-1-117)
- [§1.118 — Residuals from the addressed-hearing repair (PB1/PB6)](UNBUILT_PERCEPTION.md#unbuilt-1-118)
- [§1.120 — Outdoors, ordinary speech is `full` only inside about five paces — a constants decision](UNBUILT_PERCEPTION.md#unbuilt-1-120)
- [§1.121 — The two rescues that promote an unheard line, and the record that would show them](UNBUILT_PERCEPTION.md#unbuilt-1-121)
- [§1.125 — The decibel constants: a wall's loss, two new rungs, and three margins](UNBUILT_PERCEPTION.md#unbuilt-1-125)
- [§1.128 — What the light-and-sources repair left for other hands](UNBUILT_PERCEPTION.md#unbuilt-1-128)
- [§1.129 — The perception-admission lane of the campaign-3 runs: what landed, and the seven answers that live in other files](UNBUILT_PERCEPTION.md#unbuilt-1-129)
- [§1.136 — The rear arc promises sound and delivers silence — ANSWERED and BUILT 2026-09-05](UNBUILT_PERCEPTION.md#unbuilt-1-136)
- [§1.140 — A crowbar on steel does not carry eighteen paces down a dead corridor — BUILT 2026-09-06](UNBUILT_PERCEPTION.md#unbuilt-1-140)
- [§1.146 — Two people three rooms apart cannot call to each other, and three models disagree about it — FIXED 2026-09-06](UNBUILT_PERCEPTION.md#unbuilt-1-146)
- [§1.147 — The cone hid the way on, because a guess was allowed to subtract — FIXED 2026-09-06](UNBUILT_PERCEPTION.md#unbuilt-1-147)
- [§1.149 — A lamp cannot be aimed at the thing worth aiming it at](UNBUILT_PERCEPTION.md#unbuilt-1-149)
- [§1.151 — Being TOLD does not ask for ears, and a closed intake leaves the old claims standing](UNBUILT_PERCEPTION.md#unbuilt-1-151)
- [§1.158 — A sense can be masked by nothing, so the gas the plan was for was modelled as a noise](UNBUILT_PERCEPTION.md#unbuilt-1-158)

**2. Roadmap**

- [§2.11 — Weather rendering is rain, snow and lightning only](UNBUILT_PERCEPTION.md#unbuilt-2-11)
- [§2.12 — Ambience layering is capped at three, and has no sends](UNBUILT_PERCEPTION.md#unbuilt-2-12)
- [§2.13 — Matching a recording to a room is keyword overlap, not hearing](UNBUILT_PERCEPTION.md#unbuilt-2-13)
- [§2.34 — The light field — PROTOTYPE, what is left](UNBUILT_PERCEPTION.md#unbuilt-2-34)
- [§2.36 — The sound field — PROTOTYPE, what is left](UNBUILT_PERCEPTION.md#unbuilt-2-36)

**3. Information-pipeline leaks still open**

- [§3.2 — Concealment gates not applied everywhere](UNBUILT_PERCEPTION.md#unbuilt-3-2)
- [§3.3 — Sense and awareness gaps](UNBUILT_PERCEPTION.md#unbuilt-3-3)
- [§3.8 — A structural risk, not a finding](UNBUILT_PERCEPTION.md#unbuilt-3-8)

**4. Architecture gaps**

- [§4.2 — Gap 4 residual / Priority 1 — evidence-carrying perception](UNBUILT_PERCEPTION.md#unbuilt-4-2)

**6. Design-note residuals**

- [§6.12 — Scent — `DESIGN_SCENT.md`](UNBUILT_PERCEPTION.md#unbuilt-6-12)

### World, space, and physical state

[Open the category file.](UNBUILT_WORLD.md)

**1. Known defects**

- [§1.2 — Nothing validates the geometry of an asserted doorway](UNBUILT_WORLD.md#unbuilt-1-2)
- [§1.10 — An entity's free-text `state` never ages, and a mind reads its own stale copy (S3-A8)](UNBUILT_WORLD.md#unbuilt-1-10)
- [§1.20 — A body's room changes with no warrant, and the scene never recovers](UNBUILT_WORLD.md#unbuilt-1-20)
- [§1.28 — Residuals from the contact-sensation work](UNBUILT_WORLD.md#unbuilt-1-28)
- [§1.46 — A transformation's parts are repaired on read, never at the source](UNBUILT_WORLD.md#unbuilt-1-46)
- [§1.65 — A condition subject written as a scene uid names nobody](UNBUILT_WORLD.md#unbuilt-1-65)
- [§1.66 — The story column's floor overrides the room it reserved](UNBUILT_WORLD.md#unbuilt-1-66)
- [§1.71 — `nature` is the designed answer and it is almost never asked](UNBUILT_WORLD.md#unbuilt-1-71)
- [§1.72 — `placement` and `add[].covers` are documented, passed, and inert](UNBUILT_WORLD.md#unbuilt-1-72)
- [§1.78 — One authored body field reaches no reader](UNBUILT_WORLD.md#unbuilt-1-78)
- [§1.79 — Four readers spell the same tolerant ledger lookup](UNBUILT_WORLD.md#unbuilt-1-79)
- [§1.81 — A part-qualified pose support is invisible to the pose sweeper](UNBUILT_WORLD.md#unbuilt-1-81)
- [§1.83 — A beat that names only where the clock ENDS ages no body at all](UNBUILT_WORLD.md#unbuilt-1-83)
- [§1.84 — A condition with no declared end and no owning floor still stands forever](UNBUILT_WORLD.md#unbuilt-1-84)
- [§1.84a — A condition's start is still a model-declared clock position](UNBUILT_WORLD.md#unbuilt-1-84a)
- [§1.100 — A card can author one garment twice, and the ledger cannot tell](UNBUILT_WORLD.md#unbuilt-1-100)
- [§1.110 — An opening may leave the whole cast nowhere, and nothing objects](UNBUILT_WORLD.md#unbuilt-1-110)
- [§1.113 — A short whole garment name cannot license its own wardrobe](UNBUILT_WORLD.md#unbuilt-1-113)
- [§1.114 — The ledger can say what a garment replaced; nothing says it yet](UNBUILT_WORLD.md#unbuilt-1-114)
- [§1.127 — A place the plan already holds, named from anywhere (PS5, BUILT 2026-09-05)](UNBUILT_WORLD.md#unbuilt-1-127)
- [§1.130 — Harm, conditions and the body: what the 2026-09-05 fixes left open](UNBUILT_WORLD.md#unbuilt-1-130)
- [§1.131 — Geometry after the 2026-09-05 campaign: what the vertical repair left open](UNBUILT_WORLD.md#unbuilt-1-131)
- [§1.132 — What the possession and wardrobe fixes of 2026-09-05 left open](UNBUILT_WORLD.md#unbuilt-1-132)
- [§1.138 — An anchor with no bearing is placed in the middle of the room](UNBUILT_WORLD.md#unbuilt-1-138)
- [§1.143 — A door exists twice and only one of them decides passage](UNBUILT_WORLD.md#unbuilt-1-143)
- [§1.144 — A voice turned a body away from what its hands were on — FIXED 2026-09-06](UNBUILT_WORLD.md#unbuilt-1-144)
- [§1.145 — Sixty-two percent of bodies have never faced a direction](UNBUILT_WORLD.md#unbuilt-1-145)
- [§1.148 — The median room has nowhere to stand](UNBUILT_WORLD.md#unbuilt-1-148)
- [§1.153 — The corridor grows as fast as the player walks it, so a search can recede forever](UNBUILT_WORLD.md#unbuilt-1-153)
- [§1.155 — A fixture is two records with two owners and no link, so the player was not told what his own hands had just done](UNBUILT_WORLD.md#unbuilt-1-155)
- [§1.157 — A room in a chat with no lorebook is never registered, and the escape route died of it](UNBUILT_WORLD.md#unbuilt-1-157)

**2. Roadmap**

- [§2.6 — Scene-boundary coherence pass](UNBUILT_WORLD.md#unbuilt-2-6)
- [§2.14 — Clothing regions: the guess is reported, the authored answer is inert](UNBUILT_WORLD.md#unbuilt-2-14)
- [§2.15 — Movement is an arrival, never a crossing](UNBUILT_WORLD.md#unbuilt-2-15)
- [§2.27 — Room geometry and occlusion — PROTOTYPE, on `main`](UNBUILT_WORLD.md#unbuilt-2-27)
- [§2.28 — The day cycle's residuals](UNBUILT_WORLD.md#unbuilt-2-28)
- [§2.37 — Room fidelity — what the 2026-09-04 prototype left](UNBUILT_WORLD.md#unbuilt-2-37)

**4. Architecture gaps**

- [§4.7 — Does the engine grow a material model at all?](UNBUILT_WORLD.md#unbuilt-4-7)

**5. Deferred backlog**

- [§5.4 — P6 — room-boundary scene-truth](UNBUILT_WORLD.md#unbuilt-5-4)

**6. Design-note residuals**

- [§6.4 — Place purpose — `DESIGN_PLACE_PURPOSE.md`](UNBUILT_WORLD.md#unbuilt-6-4)
- [§6.5 — Place graph](UNBUILT_WORLD.md#unbuilt-6-5)
- [§6.10 — Extra body parts — `../design_notes/11-extra-body-parts.md`](UNBUILT_WORLD.md#unbuilt-6-10)
- [§6.11 — Garment displacement — `../design_notes/17-garment-displacement.md`](UNBUILT_WORLD.md#unbuilt-6-11)
- [§6.13 — Paradox consequences — `DESIGN_PARADOX_CONSEQUENCES.md`](UNBUILT_WORLD.md#unbuilt-6-13)
- [§6.14 — Close-contact causality — `CLOSE_CONTACT_SCENARIO_AUDIT_2026-08-23.md`](UNBUILT_WORLD.md#unbuilt-6-14)

### Identity, naming, and language

[Open the category file.](UNBUILT_IDENTITY.md)

**1. Known defects**

- [§1.0 — The Japanese pack cannot route the Director's manifest](UNBUILT_IDENTITY.md#unbuilt-1-0)
- [§1.17 — A generic name cannot count](UNBUILT_IDENTITY.md#unbuilt-1-17)
- [§1.19 — An unregistered presence has no name to be called by](UNBUILT_IDENTITY.md#unbuilt-1-19)
- [§1.38 — A line addressed by epithet is addressed to nobody](UNBUILT_IDENTITY.md#unbuilt-1-38)
- [§1.39 — Micro-perception deliveries bypass the composer's identity floor](UNBUILT_IDENTITY.md#unbuilt-1-39)
- [§1.43 — Recognition under a disguise is a boolean where the question is graded](UNBUILT_IDENTITY.md#unbuilt-1-43)
- [§1.48 — Language packs: what is not finished](UNBUILT_IDENTITY.md#unbuilt-1-48)
- [§1.51 — Residuals from immutable people identity (Directive hardening §1)](UNBUILT_IDENTITY.md#unbuilt-1-51)
- [§1.67 — Subject spellings outside the scene blob are not folded](UNBUILT_IDENTITY.md#unbuilt-1-67)
- [§1.89 — A minted name serves only the unnamed](UNBUILT_IDENTITY.md#unbuilt-1-89)
- [§1.90 — A minted person never takes a registered mind's address](UNBUILT_IDENTITY.md#unbuilt-1-90)
- [§1.90a — A generic name is never made out of a named person — LANDED](UNBUILT_IDENTITY.md#unbuilt-1-90a)
- [§1.91 — Nothing tells a character they were addressed](UNBUILT_IDENTITY.md#unbuilt-1-91)
- [§1.92 — A registered character can be voiced by the background path — FIXED](UNBUILT_IDENTITY.md#unbuilt-1-92)
- [§1.104 — The persona has no per-story copy, so a card edit reaches every story at once](UNBUILT_IDENTITY.md#unbuilt-1-104)
- [§1.106 — Promotion has four authorities and the owner wants two](UNBUILT_IDENTITY.md#unbuilt-1-106)

**5. Deferred backlog**

- [§5.5 — P7 remainder — promotion-turn identity binding](UNBUILT_IDENTITY.md#unbuilt-5-5)

### Characters, memory, and psychology

[Open the category file.](UNBUILT_CHARACTERS.md)

**1. Known defects**

- [§1.5 — A character cannot revise a bearing they learned wrong](UNBUILT_CHARACTERS.md#unbuilt-1-5)
- [§1.27 — Residuals from the speech-channel investigation](UNBUILT_CHARACTERS.md#unbuilt-1-27)
- [§1.29 — Parallel reaction chains, and the isolated wave that is shelved for them](UNBUILT_CHARACTERS.md#unbuilt-1-29)
- [§1.37 — The aversive half of the stress model is live and unobserved](UNBUILT_CHARACTERS.md#unbuilt-1-37)
- [§1.41 — Surface-affect habituation ships default-off; flipping it is a decision this entry exists to force](UNBUILT_CHARACTERS.md#unbuilt-1-41)
- [§1.56 — The project tier's occasion now arrives, and is declined](UNBUILT_CHARACTERS.md#unbuilt-1-56)
- [§1.76 — `recall_confidence` measures distribution shape, and absence has the same shape as presence](UNBUILT_CHARACTERS.md#unbuilt-1-76)
- [§1.85 — A memory's age off a per-beat estimate, not a per-beat record](UNBUILT_CHARACTERS.md#unbuilt-1-85)
- [§1.99g — Memories the player owns, and the one thing that must be true first](UNBUILT_CHARACTERS.md#unbuilt-1-99g)
- [§1.107 — `generalization_tags` promises a mechanism that does not exist](UNBUILT_CHARACTERS.md#unbuilt-1-107)

**2. Roadmap**

- [§2.2 — Make stance auditable](UNBUILT_CHARACTERS.md#unbuilt-2-2)
- [§2.3 — Teach the heuristic import to read `description`](UNBUILT_CHARACTERS.md#unbuilt-2-3)
- [§2.16 — A summary window should be an INDEX over raw memory, not more prose](UNBUILT_CHARACTERS.md#unbuilt-2-16)
- [§2.17 — Memory reliability after temporal separation](UNBUILT_CHARACTERS.md#unbuilt-2-17)
- [§2.19 — Character: scope the sheet, do not split the judgement](UNBUILT_CHARACTERS.md#unbuilt-2-19)
- [§2.20 — Characters begin every story with no past they can recall](UNBUILT_CHARACTERS.md#unbuilt-2-20)
- [§2.22 — Exact-cue matching scans the whole bank, and an index is what it wants](UNBUILT_CHARACTERS.md#unbuilt-2-22)
- [§2.23 — Four of the seven memory kinds cannot be minted](UNBUILT_CHARACTERS.md#unbuilt-2-23)
- [§2.24 — A superseded belief is read before its correction](UNBUILT_CHARACTERS.md#unbuilt-2-24)
- [§2.25 — Two retrieval ideas measured, one rejected, one parked](UNBUILT_CHARACTERS.md#unbuilt-2-25)

**6. Design-note residuals**

- [§6.6 — Psychology as pressure — `DESIGN_PSYCHOLOGY_AS_PRESSURE.md`](UNBUILT_CHARACTERS.md#unbuilt-6-6)
- [§6.7 — Long-term goals — `DESIGN_LONG_TERM_GOALS.md`](UNBUILT_CHARACTERS.md#unbuilt-6-7)
- [§6.9 — Character-agent output audit — `../design_notes/09-character-agent-audit.md`](UNBUILT_CHARACTERS.md#unbuilt-6-9)

### Living world and institutions

[Open the category file.](UNBUILT_LIVING_WORLD.md)

**1. Known defects**

- [§1.10a — A charter body promoted to a character knows nothing about where it is](UNBUILT_LIVING_WORLD.md#unbuilt-1-10a)
- [§1.30 — The background-claims lane has fired seven times, all one way](UNBUILT_LIVING_WORLD.md#unbuilt-1-30)
- [§1.84b — A ship with three captains: a rotation applied to a post that cannot rotate](UNBUILT_LIVING_WORLD.md#unbuilt-1-84b)
- [§1.84c — Succession — OWNER'S DESIGN, not to be specified here](UNBUILT_LIVING_WORLD.md#unbuilt-1-84c)
- [§1.84d — A character has nowhere to carry a rank, so the rank goes in the name](UNBUILT_LIVING_WORLD.md#unbuilt-1-84d)
- [§1.84e — An institution with no members below its posts — OWNER'S CHOICE OF THREE SHAPES](UNBUILT_LIVING_WORLD.md#unbuilt-1-84e)
- [§1.95 — A crew who have served together for years begin as strangers](UNBUILT_LIVING_WORLD.md#unbuilt-1-95)
- [§1.96 — One body, two simulations, and a door that only opens one way](UNBUILT_LIVING_WORLD.md#unbuilt-1-96)
- [§1.96a — The stateless rule was written for one population and applied to two](UNBUILT_LIVING_WORLD.md#unbuilt-1-96a)
- [§1.97 — Volition reads history; the rest of the social physics does not](UNBUILT_LIVING_WORLD.md#unbuilt-1-97)
- [§1.98 — Ordinary evidence, and the healthy institution that is still empty](UNBUILT_LIVING_WORLD.md#unbuilt-1-98)
- [§1.99 — The discrete tie, and the health that only ever earns one label](UNBUILT_LIVING_WORLD.md#unbuilt-1-99)
- [§1.99a — Status as a temporary trait, and the accusation nobody offscreen makes](UNBUILT_LIVING_WORLD.md#unbuilt-1-99a)
- [§1.99b — Trigger rules, and the blame that finally reaches somebody](UNBUILT_LIVING_WORLD.md#unbuilt-1-99b)
- [§1.99c — The Charter scale audit's 45-second guard is broken, and the branch broke it](UNBUILT_LIVING_WORLD.md#unbuilt-1-99c)
- [§1.99d — A person is owned by an institution, and a timeskip carries nobody](UNBUILT_LIVING_WORLD.md#unbuilt-1-99d)
- [§1.99e — The three tiers, and the chatter already being thrown away](UNBUILT_LIVING_WORLD.md#unbuilt-1-99e)
- [§1.99f — A companion arrives having never met the player](UNBUILT_LIVING_WORLD.md#unbuilt-1-99f)
- [§1.102 — What reaches a charter voice: what the 2026-09-03 fix reached, and what it did not](UNBUILT_LIVING_WORLD.md#unbuilt-1-102)
- [§1.103 — The player's dealings with a townsperson: what the ledgers do not yet answer](UNBUILT_LIVING_WORLD.md#unbuilt-1-103)
- [§1.105 — The off-screen ladder should collapse to one toggle, and it has five rungs](UNBUILT_LIVING_WORLD.md#unbuilt-1-105)
- [§1.108 — What the Living World audit found](UNBUILT_LIVING_WORLD.md#unbuilt-1-108)
- [§1.111 — Every charter already written names no commons](UNBUILT_LIVING_WORLD.md#unbuilt-1-111)
- [§1.115 — The needs filter reads free prose, and its threshold is a judgement](UNBUILT_LIVING_WORLD.md#unbuilt-1-115)
- [§1.123 — An errand the fiction promised has no channel to the institution](UNBUILT_LIVING_WORLD.md#unbuilt-1-123)
- [§1.124 — The Director dispatches an errand to an institution (PB13, BUILT 2026-09-05)](UNBUILT_LIVING_WORLD.md#unbuilt-1-124)
- [§1.137 — A planned room is deaf until somebody puts a counter in it — BUILT 2026-09-06](UNBUILT_LIVING_WORLD.md#unbuilt-1-137)
- [§1.139 — A creature holds the words it merely heard](UNBUILT_LIVING_WORLD.md#unbuilt-1-139)
- [§1.141 — A scent hunter that loses the trail stops instead of casting — BUILT 2026-09-06](UNBUILT_LIVING_WORLD.md#unbuilt-1-141)
- [§1.142 — An edge cost ten minutes because the courier said so](UNBUILT_LIVING_WORLD.md#unbuilt-1-142)
- [§1.150 — A creature has no held hunt — the courier maze problem, one subsystem over](UNBUILT_LIVING_WORLD.md#unbuilt-1-150)
- [§1.152 — A creature can be stopped by the shape of an opening and by nothing else](UNBUILT_LIVING_WORLD.md#unbuilt-1-152)

**2. Roadmap**

- [§2.7 — Reactivation negotiation](UNBUILT_LIVING_WORLD.md#unbuilt-2-7)
- [§2.8 — Richer off-screen life](UNBUILT_LIVING_WORLD.md#unbuilt-2-8)
- [§2.29 — Who the player talks to — residuals](UNBUILT_LIVING_WORLD.md#unbuilt-2-29)
- [§2.31 — A townsperson's surface — residuals](UNBUILT_LIVING_WORLD.md#unbuilt-2-31)
- [§2.32 — Creatures as charter — residuals (2026-09-03)](UNBUILT_LIVING_WORLD.md#unbuilt-2-32)

**6. Design-note residuals**

- [§6.1 — Background life — `BACKGROUND_LIFE_DESIGN.md`](UNBUILT_LIVING_WORLD.md#unbuilt-6-1)
- [§6.8 — Living world — `DESIGN_LIVING_WORLD.md`](UNBUILT_LIVING_WORLD.md#unbuilt-6-8)

### Story planning and authoring

[Open the category file.](UNBUILT_PLANNING.md)

**1. Known defects**

- [§1.134 — What the campaign-3 plan/structure/tools wave left open (2026-09-05)](UNBUILT_PLANNING.md#unbuilt-1-134)

**2. Roadmap**

- [§2.9 — Predictive staging](UNBUILT_PLANNING.md#unbuilt-2-9)
- [§2.26 — Writers' Room and Dramaturge](UNBUILT_PLANNING.md#unbuilt-2-26)
- [§2.26a — Phase A's residuals: the compiler, the filing and the retired hand](UNBUILT_PLANNING.md#unbuilt-2-26a)
- [§2.30 — The replay closer's residuals (2026-09-03)](UNBUILT_PLANNING.md#unbuilt-2-30)
- [§2.33 — Planned entities and enrolment — residuals (2026-09-03)](UNBUILT_PLANNING.md#unbuilt-2-33)
- [§2.35 — What the 2026-09-04 debug runs left open](UNBUILT_PLANNING.md#unbuilt-2-35)

### Platform, persistence, and tooling

[Open the category file.](UNBUILT_PLATFORM.md)

**1. Known defects**

- [§1.12 — Watch items](UNBUILT_PLATFORM.md#unbuilt-1-12)
- [§1.35 — `memories_fts` is dead, and has been for some time](UNBUILT_PLATFORM.md#unbuilt-1-35)
- [§1.40 — A restore racing a mid-flight consolidation call](UNBUILT_PLATFORM.md#unbuilt-1-40)
- [§1.45 — A dead helper family with passing tests and no production caller](UNBUILT_PLATFORM.md#unbuilt-1-45)
- [§1.57 — Two per-item tags in `OFFSCREEN_WORLD_COMPLETION.md` overstate what is built](UNBUILT_PLATFORM.md#unbuilt-1-57)
- [§1.58 — Schema-touching work deferred by owner policy 4](UNBUILT_PLATFORM.md#unbuilt-1-58)
- [§1.61 — Half the prompt ids are outside the prompt/schema drift check](UNBUILT_PLATFORM.md#unbuilt-1-61)
- [§1.62 — An extra player has no opening turn](UNBUILT_PLATFORM.md#unbuilt-1-62)
- [§1.88 — A restored checkpoint is as old as the beat it snapshot](UNBUILT_PLATFORM.md#unbuilt-1-88)
- [§1.94 — A time block that disagrees with itself is not detected](UNBUILT_PLATFORM.md#unbuilt-1-94)
- [§1.160 — A phantom character id, one past the real one, is written into memory](UNBUILT_PLATFORM.md#unbuilt-1-160)
- [§1.161 — The 2026-09-07 review: what landed and what is still open](UNBUILT_PLATFORM.md#unbuilt-1-161)

**2. Roadmap**

- [§2.5 — Complete automatic canon lock](UNBUILT_PLATFORM.md#unbuilt-2-5)
- [§2.10 — Session digest](UNBUILT_PLATFORM.md#unbuilt-2-10)

**3. Information-pipeline leaks still open**

- [§3.4 — Multiplayer](UNBUILT_PLATFORM.md#unbuilt-3-4)
- [§3.5 — Persistence](UNBUILT_PLATFORM.md#unbuilt-3-5)
- [§3.7 — Test gaps](UNBUILT_PLATFORM.md#unbuilt-3-7)

**4. Architecture gaps**

- [§4.3 — Gap 5 — canon validation needs provenance tiers](UNBUILT_PLATFORM.md#unbuilt-4-3)
- [§4.4 — Gap 6 / Priority 2 — frame/global conflict control](UNBUILT_PLATFORM.md#unbuilt-4-4)
- [§4.5 — Gap 8 — uniform cost against non-uniform uncertainty](UNBUILT_PLATFORM.md#unbuilt-4-5)
- [§4.6 — Priority 3 residual — request-size limits](UNBUILT_PLATFORM.md#unbuilt-4-6)

**5. Deferred backlog**

- [§5.2 — P4 — `established_facts` continuity ledger](UNBUILT_PLATFORM.md#unbuilt-5-2)

**6. Design-note residuals**

- [§6.2 — Extensions — `EXTENSIONS_DESIGN.md`](UNBUILT_PLATFORM.md#unbuilt-6-2)

### Parked

- [§8 — Parked](UNBUILT_PARKED.md)
