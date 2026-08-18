# Split plan — `agents/director.py`

Status: PROPOSED. Companion to [`DESIGN_MODULE_LAYOUT.md`](DESIGN_MODULE_LAYOUT.md).

8,135 lines · 114 defs/classes · 28 module-level constants. All 142 symbols
assigned exactly once, verified against the AST.

## The finding that shapes the whole plan

The 41 private test imports are **not** the binding constraint — a facade
re-export handles all of them. The binding constraint is one no import census
shows:

**106 sites across 17 test files do `monkeypatch.setattr(director,
"_agent_json", fake)`**, plus 2× `validate_llm_output`, 2× `_ability_mod`, 1×
`_prose_gate_facts`. A monkeypatch writes into `agents/director.py`'s module
dictionary. A function moved to `agents/director_x.py` resolves `_agent_json` in
**its own** globals and never sees the patch.

`tests/conftest.py:158`'s `fanout_resolve_agent` makes it concrete: one fake
must be seen simultaneously by `director_resolve` (prose-author call),
`_run_specialists` (specialist calls) and `_specialist_repairs` (repair calls).
A naive split puts those in three modules and one patch reaches one of them.

Nine functions reference a patched name: `director_establish` (639),
`director_interpret` (815), `_reconcile_interpretation` (1487),
`_deep_audit_omissions` (3702), `_specialist_repairs` (4052),
`_reconcile_resolution` (4173), `_prose_author_scope` (5613), `_run_specialists`
(6098), `director_resolve` (6473). For four of them the breakage is **silent**:
the fake is installed, some other call reaches it, and the moved function
quietly makes a real model call.

Hence two phases.

## Phase 1 — 9 modules, ~4,640 lines out, zero test changes

Every model-calling function **stays in `director.py`**, which ends at ~3,560
lines: the stage bodies plus the import surface.

| module | ~lines | owns |
| --- | --- | --- |
| `director_lingua.py` | 14 | The language-pack accessor for the `"agents.director"` pack key and the three eager English consciousness cues. |
| `director_contact.py` | 395 | Validation and merging of player-asserted contact ops, character-declared endings, character material effects. **Leaf.** |
| `director_views.py` | 435 | Read-only views the stages put in a payload, plus the two post-hoc output audits. **Leaf.** |
| `director_floors.py` | 654 | The deterministic prose-vs-diff floors — restraint, consciousness onset both directions, waking exits, destruction. |
| `director_evidence.py` | 854 | The detection substrate both seams stand on — declaration coverage, diff normalisation, subject matching, evidence classes, the `changes_asserted` manifest. |
| `director_reconcile.py` | 400 | Resolve-seam support making no model call — claim findings, verdict settling and acquittal, repair routing, articulation stamping. |
| `director_movement.py` | 904 | Every spatial backstop on the merged diff — heading-aware exits, near-group cohesion, following, passability, multi-beat travel, approach-is-not-arrival. |
| `director_scopes.py` | 513 | The specialist registry and channel-ownership map, work gates, the extension seam, prose-duty shipped-anyway table, gate facts, dispatch. |
| `director_fanout.py` | 471 | Concurrency choice, per-specialist beat views, payload assembly, manifest slicing, channel merge normalisation, the scope backstop. |

### `director_lingua.py` — a hard warning

The pack key is the **string literal** `"agents.director"`, in `_ling`'s body and
in lines 137–139. It is a language-pack coordinate, not a module identity:
`tools/build_japanese_pack.py:308–311` and `tests/test_language_packs.py:133`
key on it. **Do not** rewrite it to `__name__` or to the new module's name.
`language_runtime.linguistic()` is a pure keyed lookup with no registration side
effect, so the move is safe as long as the literal survives byte-for-byte.

### The two stages

`director_scopes` + `director_fanout` **are** the shared set, and they are shared
for a stated reason: `AGENTS.md` says the specialists are shared between
interpret and resolve, and `_dispatch_specialists`' docstring says dispatch "is
decided at THIS stage's time, from what is true then" — one mechanism, two
invocations. They should not be split by stage.

`director_evidence` is the interesting one: the two seams are described as
"structural twins" but share **only `_norm_subject`** in code. Everything else is
parallel-but-separate — coverage tokens vs evidence classes, `_unit_covered` vs
`_evidence_present`. So it is one module by *kind*, not by *reuse*. Worth stating
plainly; the alternative is a 140-line module holding the same information.

`director_contact`'s split across stages is real, not cosmetic: player contact
assertions are *validated* at interpret and *merged* at resolve, and keeping
validate/merge pairs together is correct — the merge exists to honour what the
validation admitted.

## Module-level state

Three mutable globals, **all owned by `director_scopes`**: `SPECIALISTS`,
`_CHANNEL_GATES`, `_CHANNEL_SPECIALISTS`. The rule that guarantees no
co-writers: `register_specialist`, `unregister_specialists`,
`_rebuild_channel_owners` and `_default_channel_gate` all stay with the
registries, even though the first two are the extension seam and would be
tempting to lift into a `director_extensions.py`. Lifting them would make two
modules co-writers of all three dicts.

**Add as a module docstring invariant:** `agents/director_scopes.py` is the sole
writer of `SPECIALISTS`, `_CHANNEL_GATES` and `_CHANNEL_SPECIALISTS`.

`SPECIALISTS` is live, mutable and extension-writable — the one global where
ownership has runtime consequences. `register_specialist` mutates three dicts in
concert and `_dispatch_specialists` reads `SPECIALISTS` live then indexes
`_CHANNEL_GATES` by channel, so a partial registration is a `KeyError` inside the
Director on **every beat**. The comment at 5330 says so explicitly.

**There are no prompt constants in this file.** Every prompt string is fetched at
call time from `llm/prompts.py`, inside functions that stay. No new module needs to
import `prompts` — a clean pre-existing boundary the split must not disturb.

## Import graph

Acyclic. Topological order: `lingua`, `contact`, `views` → `floors`,
`evidence`, `movement` → `scopes` → `fanout` → `reconcile` → `director.py`.
`contact` and `views` have zero sibling edges.

**One-way rule check:** `agents/common.py` has no `from .` import at all. All
nine new modules may import `.common`; none is imported by it. **No new
violation**, and the warned-about role-modules-importing-each-other pattern is
not extended — every new edge is inside the Director family.

State the new invariant in `AGENTS.md` and in each module docstring:

> Nothing outside `agents/director*.py` may import an `agents/director_*`
> submodule, and no `director_*` module may import `agents.director` (that is
> the cycle the facade exists to prevent).

Both existing external importers already comply — `agents/__init__.py:65` and
`agents/runtime.py:36` name `.director`, and `extension_runtime` imports
`register_specialist`/`unregister_specialists` through the facade.

**Worth adding to `tools/project_check.py` as a follow-up:** two 10-line AST
checks enforcing those two directions. They are what stops the facade rotting.

## Facade

The existing import header is pruned to what retained code uses, and nine
sibling import blocks appended. **The facade is the import block.** No `__all__`
— there is none today and adding one changes `import *` semantics.

All 46 contract names map to a home; 44 to the new modules, `_reconcile_resolution`
and `CampaignInvariantError` stay.

**Three names the census missed.** `tools/project_check.py` reaches them by
`getattr(director, …)` rather than by import, so they are absent from the
contract, and **`make structure` fails without them**: `SPECIALISTS` (line 269),
`_PROSE_DUTY_GATES` (371, stays), `_PROSE_DUTY_SHIPPED` (372, moves to
`director_scopes` and **must** be re-exported).

**Four names must remain defined in `director.py`'s own globals**, not
re-exported from anywhere: `_agent_json`, `validate_llm_output`, `_ability_mod`,
`_prose_gate_facts`. They are monkeypatch targets.

## Execution order

Leaf-first, one commit each: 1 `lingua` · 2 `contact` · 3 `views` ·
4 `movement` · 5 `floors` · 6 `evidence` · 7 `scopes` · 8 `fanout` ·
9 `reconcile` · 10 comment relocation.

**Line numbers shift after every step.** Cut bottom-up within a step, and
re-derive later ranges by symbol name (`grep -n "^def _name"`), never from a
table written before step 1.

Verification per step, beyond `make check`:

- `python -c "import agents.director as d; [getattr(d,n) for n in (...)]"` over
  the 46 contract names plus `_PROSE_DUTY_GATES` and `_PROSE_DUTY_SHIPPED`.
- `git diff -M --stat` should show pure moves; non-import `+`/`-` lines should be
  empty.
- Run `test_director_orchestration`, `test_resolve_reconciliation`,
  `test_awareness_waking`, `test_interpret_reconciliation` before the full tier.

Docs in the same commits: `make map`; the `AGENTS.md` § Director orchestration
routing row (it names ten symbols that land in four different modules) and every
other row naming `agents/director.py`; the Director bullet in `CLAUDE.md`.

## Phase 2 — separate decision, needs a test change

Move the nine model-callers out; `director.py` becomes a ~120-line pure facade.

1. `tests/conftest.py` gains `patch_agent_json(monkeypatch, fn)` setting the name
   on every module holding a model caller; rewrite 106 sites across 17 files plus
   the 5 others.
2. `director_scopes` ← the prose-duty gate family (rejoins its shipped-anyway
   table, which Phase 1 splits from it).
3. `director_fanout` ← `_run_specialists`.
4. New `director_repairs.py` — `_reconcile_resolution`, `_specialist_repairs`,
   `_deep_audit_omissions` (672).
5. New `director_stage_interpret.py` (778).
6. New `director_stage_resolve.py` (1,513 ⚠ — over the ceiling by a rounding
   error, and there is no honest way under it without a logic change).

A third option was rejected: making `agents.director` a `ModuleType` subclass
whose `__setattr__` forwards to the submodules. It works and preserves the tests
verbatim, but it hides the exact coupling this exercise exists to expose, and it
makes a patch of a name nothing reads any more pass silently instead of failing
loudly.

## Resistance

1. **`director_resolve` is 1,474 lines in one function.** With
   `director_interpret` (534) and `_reconcile_resolution` (445) that is **30% of
   the file, untouched by the split**. If the goal is "no file over 1,500", this
   gets 12 of 13 and then the work is decomposing `director_resolve` — a
   different, riskier project: it is the sole persistence-adjacent producer of
   `state_diff`, and `AGENTS.md` warns off broad rewrites of orchestration seams
   without dedicated tests.
2. **The monkeypatch coupling**, above.
3. **~600 lines of this file are argument, not code** — eight doc blocks of
   16–54 lines. Three describe machinery that ends up in more than one module.
   Rule: a block travels with the symbol immediately below it, except the
   54-line block at 1606–1659, which travels to its subject
   (`_reconcile_resolution`). Add a module docstring pointing back at the
   surviving block; do not duplicate it.
4. **`_evidence_present` is 232 lines in one function** and is the table the
   resolve seam lives or dies on. Moves as one block.

## On the 41 private test imports — the honest read

They are the symptom, not the disease, and about half are correct as they stand.

- **~14 are legitimate unit tests of pure functions that happen to be
  underscored** — `_round_conduct`, `_evidence_present`, `_subject_match_forms`,
  `_normalize_diff_shape`, `_sleep_elapsed`, `_egocentric_exits`,
  `_unreachable_position_writes`, `_manifest_items`. Deterministic,
  side-effect-free, plain data in. Testing them directly is right; the defect is
  the underscore. **The split makes this fixable for the first time**:
  `evidence_present` in `agents/director_evidence.py` reads as public to the
  family, where the same name in an 8,135-line `director.py` would have read as a
  promise to the whole application.
- **~3 are constants used as fixtures** — the three cues. These are the worst:
  the tests assert against the eagerly-compiled **English** copies while the
  runtime uses `_ling(...)` under a story-language context. The test is not
  testing the code path.
- **~26 are the real coupling** — seam internals asserted at seam granularity
  because there is no smaller thing to hold.

**I would not rewrite the 26 as a follow-up, and not soon.** Each private import
is a test written *because something broke in a chat* — the elevator narrated as
sealed, the player put under for closing their eyes, the shed `utility_sash`.
Rewriting against a coarser public surface trades a test that pins the exact
mechanism for one that pins an outcome, which is only correct if the coarser test
would still have caught the original defect — and for the awareness-exit rules
and the evidence categories, it would not. The coupling is real but is not
currently costing anything, and 26 rewritten tests is 26 chances to lose a guard
bought with a live incident.

Order I would actually follow: ship Phase 1 → add the two `project_check`
import-direction rules → do Phase 2 → drop the underscore from the ~14 pure
functions as each module docstring is written → leave the 26 alone until a change
actually fights them.

## Defects noticed — do not fix here

- **`_DELEGATED_CHANNELS` is frozen at import; `_CHANNEL_SPECIALISTS` is not.**
  `director.py:5195` is a module-level comprehension over `SPECIALISTS`. The
  comment 176 lines below, on `_CHANNEL_SPECIALISTS`, describes that exact
  pattern as a bug already fixed there: "a family registered afterwards was
  invisible to `_route_repair_omissions` while being perfectly visible to
  dispatch — a split that routes a repair to nobody." Its only reader is
  `_orchestration_scope_backstop`, so an extension's channels are dispatched and
  merged but invisible to the scope backstop: the gate-mispredict report is blind
  to every extension channel. The split surfaces this — `director_scopes` will
  own one rebuilt registry and one frozen one, side by side.
- **A doc comment is attached to the wrong symbol.** `director.py:5249–5253`
  describes `_CHANNEL_SPECIALISTS` (5371) while sitting above `_LIST_DELEGATED`
  (5254), which is therefore undocumented while carrying a description of
  something else. Flag it in the PR rather than silently re-attaching — the
  verbatim rule is what makes this split reviewable.
- **A 54-line doc block is 2,500 lines from its subject** (1606–1659, documenting
  the resolve seam, sitting above one Tier-0 detector). Step 10 relocates it.
- **Three module constants no production code reads, whose tests test the wrong
  thing.** The cues at 136–139 are `english_linguistic(...)` resolved at import;
  every runtime use goes through `_ling(...)` instead, deliberately, so that
  concurrent pipelines follow their own story language. The constants are dead at
  runtime and alive only as fixtures — and `tests/test_awareness.py:342–364` and
  `tests/test_awareness_waking.py:470` assert cue behaviour against the English
  objects, which is not what a non-English story evaluates. Not a live bug while
  every story is English, but a guard that would not fire on the language it was
  written to protect.
- **`fanout_is_parallel` is 1,600 lines from the machinery it configures** —
  wedged inside the reconciliation-constants block. Placement only; the split
  corrects it as a side effect.
- **A stale symbol name in a doc block**: `director.py:5124` says
  `_orchestration_gate_backstop`. No such symbol; it is
  `_orchestration_scope_backstop`, spelled correctly at 5270 and 5480.
