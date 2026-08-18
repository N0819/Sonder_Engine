# Audit: `agents/director.py`, read whole during the Phase-1 split

Working notes per `docs/design/DESIGN_MODULE_LAYOUT.md` §"The split is also
the audit" and §"…a documentation reconciliation". Produced while executing
`docs/design/SPLIT_DIRECTOR.md` Phase 1 — the one task that required reading
all 8,135 lines of the file.

**Baseline revision:** `418ab5b` (alpha 9.5). Every `file:line` below is as
of that revision's `agents/director.py` unless said otherwise.

**The split's commits** (each independently green under `make check`, 7,274
tests):

| step | commit | module | lines |
| --- | --- | --- | --- |
| 1 | `0315f55` | `agents/director_lingua.py` | 22 |
| 2 | `a6e58b7` | `agents/director_contact.py` | 421 |
| 3 | `69030e2` | `agents/director_views.py` | 453 |
| 4 | `a531ba1` | `agents/director_movement.py` | 938 |
| 5 | `7af863a` | `agents/director_floors.py` | 678 |
| 6 | `119f7f7` | `agents/director_evidence.py` | 892 |
| 7 | `4783afe` | `agents/director_scopes.py` | 545 |
| 8 | `c86fbdf` | `agents/director_fanout.py` | 501 |
| 9 | `7f3354b` | `agents/director_reconcile.py` | 424 |
| 10 | `9187a39` | comment relocation + facade header | — |

`agents/director.py` ends at 3,652 lines: the stage bodies, every
model-calling function, the four monkeypatch targets (`_agent_json`,
`validate_llm_output`, `_ability_mod`, `_prose_gate_facts` — all still
defined in `director.py`'s own globals), and the facade import block. Zero
monkeypatch-site changes; all 49 externally-imported names plus the two
`project_check` getattr names re-export through the facade.

---

## Part 1 — findings. FLAGGED, NOT FIXED.

Per the layout note's discipline: a finding is written down and the move
continues. Nothing below was changed in the move commits beyond relocation.
`SPLIT_DIRECTOR.md` §"Defects noticed" listed six; all six are confirmed
below (1–6), with one sharpened (2). Findings 7–13 are new from the
line-by-line read.

### 1. `_DELEGATED_CHANNELS` is frozen at import; `_CHANNEL_SPECIALISTS` is not — CONFIRMED

`director.py:5195-5196` (now `director_scopes.py`, moved in `4783afe`) is a
module-level comprehension over `SPECIALISTS`. The comment 176 lines below,
on `_CHANNEL_SPECIALISTS` (5367-5370), describes that exact pattern as a bug
already fixed there: "a family registered afterwards was invisible … a split
that routes a repair to nobody." `register_specialist` calls
`_rebuild_channel_owners`, which rebuilds `_CHANNEL_SPECIALISTS` and nothing
else. `_DELEGATED_CHANNELS`' only reader is `_orchestration_scope_backstop`
(6361, now `director_fanout.py`, `c86fbdf`), so an extension family's
channels are dispatched, merged, and invisible to the scope backstop: the
gate-mispredict report is blind to every extension channel. The split makes
the pair visible side by side in `director_scopes.py` — one rebuilt registry,
one frozen one.

### 2. A doc comment is attached to the wrong symbol — CONFIRMED, and worse than misattached

`director.py:5249-5253` ("channel -> the specialist that owns it (derived,
so the two cannot disagree). The reconciliation repair router reads this")
describes `_CHANNEL_SPECIALISTS` (5371) while sitting directly above
`_LIST_DELEGATED` (5254). Read against the symbol it sits on, the claim is
FALSE, not merely misplaced: `_LIST_DELEGATED` is a hand-enumerated
frozenset of list-shaped channels, not derived from anything, and it CAN
disagree with `SPECIALISTS` (see finding 9 for a live consequence).
`_LIST_DELEGATED` itself remains undocumented. Moved verbatim to
`director_scopes.py` in `4783afe`; still misattached there, per the
verbatim rule.

### 3. A 54-line doc block 2,500 lines from its subject — CONFIRMED; relocated in step 10

`director.py:1606-1659` (52 lines fence to fence) documents the resolve
reconciliation seam and sat above one Tier-0 detector,
`_untracked_restraint_subjects`. Relocated byte-identical to directly above
`_reconcile_resolution` in `9187a39`, which the plan designates as the one
sanctioned relocation. `director_floors.py` and `director_evidence.py`
docstrings point back at it rather than duplicating it.

### 4. Three module constants no production code reads; their tests test the wrong thing — CONFIRMED

`director.py:136-139` (now `director_lingua.py`, `0315f55`):
`_UNCONSCIOUSNESS_CUE`, `_SLEEP_CUE`, `_STAY_UNDER_CUE` are
`english_linguistic(...)` resolved at import. Every runtime use goes through
`_ling(...)` so concurrent pipelines follow their own story language; the
eager constants are referenced nowhere in `agents/director*.py` at runtime
(verified during the move) and are alive only as test fixtures.
`tests/test_awareness.py:342-364` and `tests/test_awareness_waking.py:470`
assert cue behaviour against the English objects — not what a non-English
story evaluates. Not a live bug while every story is English; a guard that
would not fire on the language it was written to protect.

### 5. `fanout_is_parallel` was 1,600 lines from the machinery it configures — CONFIRMED; corrected by the move

`director.py:3484-3503`, wedged inside the reconciliation-constants block
(between `_RECONCILE_MIN_CONFIDENCE` and `_deep_audit_mode`). Placement
only; it now opens `director_fanout.py` (`c86fbdf`), beside the fan-out it
configures, as the plan predicted the split would do as a side effect.

### 6. A stale symbol name in a doc block — CONFIRMED

`director.py:5124` (the orchestration block comment) says
"`_orchestration_gate_backstop` is `changes_asserted` reconciliation pointed
at the GATE". No such symbol exists; it is `_orchestration_scope_backstop`,
spelled correctly at 5270 and 5480 of the same revision. Moved verbatim to
`director_scopes.py` in `4783afe`; the stale name is still there, per the
verbatim rule.

### 7. NEW — `if True:` vestige of the removed orchestration flag

`director.py:6914-6916` (stays in `director.py`; not moved):

```python
_orch_dispatch = None
_prose_scope = None
if True:
```

The `if True:` and the two `None` pre-initialisations are the skeleton of
the `director_orchestration` setting removed when the monolith was deleted
(no such setting exists anywhere in the tree — verified by grep over
`db.py`, `providers.py`, `commit.py`). The conditional cannot not run, the
`None`s are unconditionally overwritten, and the indentation it forces makes
the dispatch block read as though it were still optional. Dead code, one
`if` and two assignments.

### 8. NEW — a comment describing a future that has since arrived

`director.py:5127-5131` (the orchestration block comment, now
`director_scopes.py`, `4783afe`): "when `director_interpret` grows its own
specialists it will call its own dispatch against the state it sees".
`director_interpret` HAS its own specialists and its own dispatch — the
`_dispatch_specialists`/`_run_specialists` call at `director.py:1077-1118`
of the same revision, whose own comment ("Orchestrated interpret, design
note 19: THE SAME specialists resolve dispatches…") says so. The next reader
of the scopes block is told interpret-side dispatch is future work; it is
shipped and tested (`tests/test_director_orchestration.py`).

### 9. NEW — an extension specialist's list-valued channel is silently emptied at assembly

`_normalized_channel_value` (`director.py:6030-6035`, now
`director_fanout.py`, `c86fbdf`) coerces any channel not named in
`_LIST_DELEGATED` and not `destruction` to dict-or-`{}`. Extension channels
are namespaced `ext:<id>:<channel>` (`register_specialist`,
`director.py:5406`), and the hand-frozen `_LIST_DELEGATED` (finding 2) can
never contain one — so an extension family that emits a LIST under its own
channel has its entire output silently replaced by `{}` in
`_run_specialists`' assembly and in `_specialist_repairs`' patch build. No
warning fires; the extension's ledger entry is simply absent. Same class as
finding 1 (a registry frozen against the extension seam), and the silent
kind of tolerance the layout note asks to be flagged. Whether extension
channels are meant to be dict-only is stated nowhere; if it is intended, it
is an undocumented contract enforced by silent deletion.

### 10. NEW — `_travel_in_flight_view` and `_travel_continues` are near-duplicates

`director.py:4833-4890` and `4893-5016` (both now `director_movement.py`,
`a531ba1`). Both normalise the legacy scene-global `{"who": …}` approach
shape, both build the declared-movers exemption from `interp["movement"]`,
both find the edge to the next step and both apply the
`_LONG_EDGE_DISTANCES`/`_LONG_EDGE_BEATS` rule — the view answering
`still_crossing` where the mutator answers `held`. Parallel-but-separate on
slightly different inputs: exactly the six-entries-for-three-things shape
the layout note names. A change to the long-edge rule, the legacy-shape
tolerance or the declared-mover exemption must currently be made twice, and
nothing checks the copies agree.

### 11. NEW — a test asserts on the source file's layout, and the class may have more members

`tests/test_style_guide.py:143-146` slices `agents/director.py`'s TEXT
between `"def director_interpret"` and `"def _decl_tokens"` to assert the
interpret body carries no `style_guide`. The evidence move (`119f7f7`) broke
the end marker; the marker was retargeted to
`"def _reconcile_interpretation"` in the same commit (assertion unchanged).
Flagged because the technique — def-name markers over file text — breaks on
any reorganisation, and only the suite's one member of the class surfaced
here. The Phase-2 mover should expect others.

### 12. NEW — `docs/UNBUILT.md` §2.18 still carries the orchestration proposal the code has landed

`docs/UNBUILT.md:3010` ("The Director as an orchestrator over scoped
specialists") still reads as a proposal with measurements, while
`Design.md`'s conformance row ("The Director is a writer plus specialists,
not one mind") says **Built** and the monolith is verifiably gone (no
`DEFAULT_PROMPTS["director_resolve"]`; only `director_resolve_lean` exists
in `prompts.py`; no `director_orchestration` setting anywhere). Per
`CLAUDE.md`, an UNBUILT entry is deleted in the commit that lands it and
UNBUILT wins when the lists disagree — so the register currently loses to
the conformance table. **Not edited here**: three agents are working
concurrently and `UNBUILT.md` was explicitly declared off-limits to this
task. Whoever reconciles it should also check §2.19's cross-reference
("alongside §2.18", `docs/UNBUILT.md:3200`).

### 13. NEW — design note 19's header describes a branch experiment; the code is the only path

`design_notes/19-director-orchestration.md` opens "Branch
`director-orchestration`, opened 2026-08-12. **Experiment, not a landing.**"
The architecture it describes is landed on `main` as the ONLY Director path
(PIPELINE.md: "there is no monolithic sheet and no setting that returns
one"; verified against source). The note's content is accurate; its framing
header is stale in the direction that most misleads — a reader doing
`docs/README.md` triage would file the shipped architecture as an open
experiment. Design notes are argument, not authority, so this is
low-severity; still, the note is cited by AGENTS.md's routing row as
contract documentation, which gives its header more weight than a design
note's header usually carries.

### Notes that are NOT findings

- `_RECONCILE_MAX_AUDIT_OMISSIONS` / `_RECONCILE_MIN_CONFIDENCE` stay in
  `director.py` beside their only reader (`_deep_audit_omissions`, a
  model-caller that stays); their sibling `_RECONCILE_MAX_MANIFEST_ITEMS`
  moved to `director_evidence.py` with `_manifest_items`. The three-line
  constants block is now split across two files — a layout consequence of
  the monkeypatch constraint, not a defect.
- `_awareness_view` calls `_rouse_attempts(interp, char_actions, "", …)`
  with an empty `resolved_event` — correct, not an oversight: the view is
  built for the resolve PAYLOAD, before any prose exists.
- The many `except Exception: → True` reads in `_gate_facts` /
  `_prose_gate_facts` are the documented fail-open rule, with the one
  documented deviation (`offscreen_planning_enabled` fails closed, with its
  reason in a comment). Checked, deliberate.

---

## Part 2 — what the code actually does, checked against the documents

Method: each module's behaviour written from the code during the move, then
compared against `Design.md` (conformance row "The Director is a writer plus
specialists, not one mind"), `AGENTS.md` § Director orchestration,
design notes 19 and 21, and `docs/guides/PIPELINE.md` §`director_interpret`
/ §`director_resolve`. Verdicts: RIGHT / STALE / LOST, per the layout note.

### `director_lingua.py`

`_ling(name)` is a pure keyed lookup into the language pack under the
literal key `"agents.director"`; the three module constants are eager
ENGLISH compilations of the same entries, used only by tests (finding 4).
**Docs: RIGHT** — no maintained doc describes these; the language-packs
guide's claim that packs key on module-path strings matches
`tools/build_japanese_pack.py`.

### `director_contact.py`

Validates player contact assertions at the player-authority boundary
(refinement of a standing relation is allowed; minting an NPC act is not;
`cross` must match the standing interior endpoint), merges them over resolve
ops without silent coarsening (an endpoint change requires an explicit
remove/clear or a cross), resolves character-declared contact endings
against the `contact:N` options that character was shown, and admits only
additive actor-owned material effects with a code-supplied source identity.
**Docs: RIGHT** — PIPELINE.md's `director_resolve` section describes exactly
this (endpoint-carrying manifests, source-locked material effects), and the
code matches clause for clause.

### `director_views.py`

Read-only payload projections: crowds/couriers/notices in scene rooms WITH
the uids their ops require, carried reports as a telling_ops index (holder's
degraded gist, never objective truth), unratified hearsay, round conduct (a
projection of interaction/reaction rounds to who-spoke-and-did, reading both
the `speaker` and `reactor` spellings), opening pose seeds, the extension
payload dispatch seam, and the two post-hoc audits (unadjudicated
player-asserted facts; observer-relative epithets in the objective record).
Also `_route_authorial_npc_beat`, the authorial-channel floor rerouting
player-authored NPC cognition into offers. **Docs: RIGHT** — the firewall
commentary inside `_couriers_view` ("may see where a rider is … NOT what he
carries") is honoured by the code; AGENTS.md's carrier row says the same.
The AGENTS.md rows naming `_unratified_background_claims` and
`_route_authorial_npc_beat` were repointed to this module in `69030e2`.

### `director_movement.py`

The deterministic spatial backstops, all judging the MERGED diff:
heading-aware exits (`_egocentric_exits`), the near-group repair (an anchor
may position, never relocate; the player is never moved by somebody else's
anchor), actor-owned following projection and carry (ordinary pace only,
route-proved), the reachability floor for undeclared position writes
(`_unreachable_position_writes` — reachability, never declaration), the
movement-mover resolution (vehicle vs body), multi-beat travel
(`_travel_in_flight_view` / `_travel_continues`: silence continues a
declared walk; an interruption must be established) and
approach-is-not-arrival. **Docs: RIGHT** — AGENTS.md's
objective-action-resolution row describes the two-guard split, the
travel-continuation burden inversion and the station-is-not-a-mover rule
precisely as coded; PIPELINE.md likewise. Near-duplicate concern in finding
10.

### `director_floors.py`

The prose-vs-diff floors: restraint/duress co-occurrence scan; the
unconsciousness scan with clause-level subject attribution (nearest tracked
name within `_MAX_UNCONSCIOUSNESS_GAP` tokens, sentence-break barriers,
title-abbreviation handling); the onset floor protecting the PLAYER from an
unsupported gated awareness level; the waking exits (player declaration,
deliberate rouse of an `asleep` subject, the clock at
`_NATURAL_SLEEP_SECONDS`) each built to re-emit the SAME `condition_id`
closed; the destruction tripwire (known place names in destruction-shaped
grammatical positions, warn-only, never fed to self-repair). **Docs: RIGHT**
— AGENTS.md's awareness row (including "the Director never once emitted an
ending" provenance) matches the code and its comments; the row was repointed
to this module in `7af863a`.

### `director_evidence.py`

The detection substrate: lexical declaration coverage for the interpret seam
(quoted spans + clauses, ≥half of significant tokens with 4-char-prefix
stemming, capped at `_RECONCILE_INTERPRET_MAX_UNITS`); diff shape
normalisation (including the schema-field-name-is-not-a-room strip, sourced
from the schemas rather than hand-listed); blank-placeholder stripping;
`_merge_repair_into_diff`'s additive contract (positions/stations add-only;
rooms edge-aware; conditions append); subject identity forms via cast scene
keys and entity aliases; the category-aware `_evidence_present` (232 lines,
moved as one block) accepting every legitimate spelling of a change; and the
engine-numbered `changes_asserted` manifest with derived-event folding.
**Docs: RIGHT** — design note 21's numbering contract (engine-assigned ids,
emission order, numbering before the clamp) is exactly
`_manifest_items`; AGENTS.md's evidence-class commentary (garment as well as
wearer, `cross`'s ended endpoint, station for a within-room drop) is all
present in code. The plan's observation stands and is worth repeating: the
two seams are "structural twins" that share only `_norm_subject` — this
module is one module by KIND, not by reuse.

### `director_scopes.py`

The specialist registry (dict order = canonical assembly order), channel →
category and channel → owner maps, the per-channel work gates (fail open;
gated out only when the subject provably does not exist), the extension
registration seam (namespaced channels, collision refusal, gate
installation, owner rebuild), the prose-duty shipped-anyway table, the
per-stage `_gate_facts`, and `_dispatch_specialists` (dispatch is
`bool(scope)`, never a second decision). Sole-writer invariant now stated in
the module docstring. **Docs: RIGHT**, with the two stale comment lines
flagged above (findings 6 and 8) and the frozen `_DELEGATED_CHANNELS`
(finding 1) — all three are in the moved COMMENTS, not in the maintained
docs; AGENTS.md and Design.md describe the built behaviour correctly.

### `director_fanout.py`

The fan-out's deterministic frame: the concurrency switch (sequential is a
provider accommodation, not a monolith fallback — verified: same hands, same
scopes, same canonical merge), the per-stage beat views (interpret's view is
built from the structured declaration and NEVER `ctx.input` or
`private_thought` — the X19 lesson, honoured in code), per-specialist scoped
payload assembly (each hand gets its own ledgers plus a name index; never
another specialist's ledgers), manifest slicing by the ONE filter that also
records answerability, channel value normalisation (finding 9), the
event-verdict echo (verdicts on un-granted ids discarded; only a specialist
that RAN contributes), and the scope backstop (granted vs served vs
produced; structural-absence categorisation notes; a failed call is
explicitly not a gate mispredict). **Docs: RIGHT** — every one of AGENTS.md's
long-row clauses about the echo, acquittal evidence-not-authority, and
`channels_replaced` vs `channels_filled` was checked against this code
during the move and holds.

### `director_reconcile.py`

Resolve-seam support making no model call: player-claim coverage (asserted
effects non-rejectable; unreferrable subjects degrade to notes — the chat 72
`narrative_assertion` case), the settling verdicts and the
`_verify_already_true` defect detector (refuses acquittal only on a provably
incoherent ledger: removed-yet-resident attire, wearing/regions drift, a
position naming a non-room, a contained body with its own disagreeing
position; everything undecidable trusts), acquittal bookkeeping, reroute
routing (a forwarding note beats the category map, checked against the
roster), and dialogue articulation stamping (authoritative in both
directions, quotes never touched). **Docs: RIGHT** — AGENTS.md's
`_verify_already_true` clause ("a defect detector, never a truth prover,
because change DIRECTION lives only in manifest prose") is a precise
description of the code.

### What stays in `agents/director.py`

The three stage bodies (`director_establish`, `director_interpret`,
`director_resolve` — the last still 1,474 lines, the split's stated
residual), `_reconcile_interpretation`, `_reconcile_resolution`,
`_deep_audit_omissions`, `_specialist_repairs`, `_run_specialists`,
`_prose_author_scope` and the prose-gate family, the campaign validation
pair, and the facade. Every function that references `_agent_json`,
`validate_llm_output`, `_ability_mod` or `_prose_gate_facts` is here, which
is the monkeypatch constraint the phase boundary exists for.

### Cross-document verdicts, summarised

| document | verdict |
| --- | --- |
| `Design.md` row "The Director is a writer plus specialists, not one mind" | **RIGHT** — every checkable clause (one step per stage, dispatch = bool(scope), mean-1.75 dispatch framing, monolith gone with `DEFAULT_PROMPTS['director_resolve']`, concurrency-only `director_fanout_mode`, owner-routed repair) verified against source |
| `AGENTS.md` § Director orchestration | **RIGHT**; symbol homes updated across `69030e2`…`9187a39` as the split moved them |
| `docs/guides/PIPELINE.md` §director_interpret / §director_resolve | **RIGHT** — including the travel-continuation and station-not-a-mover accounts |
| design note 19 | content RIGHT; **header STALE** (finding 13) |
| design note 21 | **RIGHT** — `_manifest_items` / `_resolved_event_verdicts` / `_acquit_addressed_events` implement it as written |
| `docs/UNBUILT.md` §2.18 | **STALE** — proposal text for a landed feature (finding 12); deliberately not edited by this task |

Nothing examined here was found built-and-quietly-lost: every mechanism the
maintained docs claim for the Director was located, live, and reachable —
with the one reachability exception being finding 1/9's extension-channel
blind spots, which are gaps in the extension seam's coverage rather than
lost engine behaviour.
