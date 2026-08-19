# Response to the Directive compatibility review

The Directive team reviewed `reorganization` at `52fd9573` against `main` at
alpha 9.5 and filed a technical compatibility review plus a P0/P1 code
recommendation document. This is the point-by-point answer, written against
`main` after the work landed.

**Summary: every P0 and P1 is addressed, and the review was right about all of
them.** Two findings were worth more than they were filed as. Two of the
review's own patch sketches are refuted, with evidence, and the refutations are
the useful part of this document — they are places where doing exactly what was
proposed would have shipped a subtler version of the same bug.

Their review was against a snapshot 179 commits behind; nothing below leans on
that, and every claim was re-verified against source before being acted on.

---

## P0.1 — Public reads can span different frames

**Confirmed on current `main`, and fixed.**

`player_view` resolved the latest committed turn's frame and held it for its
own call; `api.frame_state(...)` and `api.char_state(...)` followed the ambient
`active_frame_id`, which is unset on an extension HTTP route and therefore
answers for the present. One DTO composed from both carried the future's scene
and identity beside the present's mission, clock and crew state.

The review's framing — *"more dangerous than a hard failure because consumers
receive plausible, internally inconsistent data"* — is exactly right and is why
this was taken first.

**Built:** `api.at_frame(chat_id, frame_id=…)` resolving the frame once and
returning an immutable `ExtensionFrameView`; explicit `frame_id` on both web
views; `player_view` now reports its `frame` the way `story_view` does.
Argument and the seven decisions in
[`DESIGN_FRAME_COHERENT_READS.md`](DESIGN_FRAME_COHERENT_READS.md).

We took the facade over parameters alone, for the review's own reason: the
defect was **composition**, and a per-call parameter must be remembered by
every read a growing DTO adds.

Four things the review did not specify, decided here:

- **Writes bind exactly like reads.** A read-only facade would have
  *manufactured* the write half of the same defect — read era A through the
  view, write era B through the only ambient channel left. The commit gate is
  unchanged: binding decides WHERE, the gate still decides WHEN.
- **`None` means the present era**, which is the engine's own spelling
  everywhere in the persistence layer. "Omitted" is a module-private sentinel,
  and the two modules deliberately use *different* sentinel objects so neither
  can travel into the other as a value.
- **A selected frame with no turns is honoured, never fallen back from** —
  `provision_story` legitimately seeds frame state before any turn runs there.
- **`events` stays story-global** under any selection. `world_events` is
  objective record; a frame is an epistemic cursor, not a partition of what
  happened. The review asked us to decide this explicitly rather than let a new
  facade imply it, which was the right thing to ask.

**Not built, deliberately:** binding `api.state` / `api.documents` (chat-global
by design — binding them would imply a scoping they lack, the mirror image of
the defect), and binding route dispatch ambiently (the review's own alternative;
it would repair routes by the exact contextvar-spanning mechanism the facade
exists to avoid, and leaves hook and job compositions unrepaired).

**A bonus the constraint flushed out:** making the views frame-selectable
exposed two more members of a class we already knew. `_viewer_memories` was a
sixth raw memories read that had forgotten the frame filter — a past-bound view
handed the consumer future-era memories — and the relationships read went to
`chat_chars`, the present's row, under a held frame.

---

## P0.2 — The declared CI/runtime contract

**All four confirmed and fixed. This is the finding that was worth the most,
and not for the reasons it was filed under.**

### The 3.11 parse failure

Confirmed: three `_ling("…")` calls inside `rf"…"` patterns in
`agents/director_floors.py`. PEP 701 lifted same-quote nesting in 3.12; the
declared minimum is 3.11, which cannot parse the file at all.

Fixed, and generalised: `tools/project_check.check_minimum_python_syntax`
detects the construct through **3.12's own tokenizer** rather than by regex or
by having 3.11 installed. A grep for nested quotes reported 108 sites; this
reports the 3 that are real, and catches the multi-line-replacement-field case
too.

### The Pydantic field introspection

Confirmed exactly as described, and it is worse than "seven orchestration
failures". `_schema_list_channels` read `field.outer_type_`, which exists only
on Pydantic 1. On Pydantic 2 it returned the **empty set**, so `_LIST_DELEGATED`
was empty and `_normalized_channel_value` coerced all seventeen op-list Director
channels to `{}` — every `contact_ops`, `introductions`, `crowd_ops` and
`remove_rooms` a specialist wrote was dispatched, paid for, and discarded in
silence.

It had replaced a hand-written frozenset that was correct under both majors.

**Why our gate could not see it, which is the real finding.** The interpreter
`make check` resolves to on the maintainer's machine carried Pydantic 1.10.14
and NumPy 1.26.4. `.venv` — what both launchers build, what every player runs,
and what `constraints.txt` pins — carries Pydantic 2.11.7 and NumPy 2.2.6. A
green local gate was saying nothing about the shipped engine.

**One correction to the recommendation.** The proposed fix reads
`_declared(field).is_list`, and that flag counts only a *parametrized* list,
because it drives wrap-a-single-item coercion and needs a known item type.
`StateDiff.world_facts` is annotated bare `list`. Taking the patch as written
would have replaced a 17-channel set with a **16**-channel set and lost
`world_facts` silently — a subtler version of the same bug. We added
`llm.schemas.list_shaped_fields`, deliberately wider, in the module that already
owns the version branch.

Two structural guards now hold the class:
`check_pydantic_major_reads_are_owned` confines major-specific field attributes
to `llm/schemas.py` (it found a fourth site on its first run), and
`docs/guides/TESTING.md` carries the command to run the pinned stack and the
reason.

### The NumPy fixture

Confirmed, and the diagnosis is right including the instruction not to widen
`_vec` to accommodate it. `np.ones(dims, dtype=np.float32) / np.sqrt(dims)` is
float32 under NumPy 1's value-based casting and float64 under NumPy 2's NEP 50.
`_unit_vector` now builds it and asserts its own `nbytes`.

### The CI gates

Confirmed and fixed: `pydantic1` and `browser` carry
`if: ${{ always() && !cancelled() }}`. A 3.11 parse error had erased the
evidence from two unrelated gates.

**We also closed a gap the review could not have seen from outside:**
`extension_runtime`, `language_runtime` and `language_adapters` were in neither
`make compile` nor any structural check. `extension_runtime/api.py` — the entire
public extension API, the module Directive's production code is told to depend
on instead of our internals — was **the least covered source in the
repository**. Widening the net immediately found two live instances of a class
we had already fixed once (deriving an install root from `__file__`).

---

## P1.1 — An executable extension contract fixture

**Built:** `tests/test_extension_contract.py` — one generic fixture extension
that knows no engine module, gates on capability *names*, serves a projection
composing five public reads and a route writing all four durable homes, driven
only through `web.app` and `dispatch_route`. It runs in `check-fast`, so it is
in both Python jobs and the Pydantic-1 job.

The review's argument for it is correct and we can now demonstrate it twice
over:

- Where a scenario was already proven elsewhere the new file **cites** the
  existing test rather than copying it. The real gaps a per-part suite had left
  were: the frame-scoped (`extf:`) and per-character homes had ridden **no**
  checkpoint restore and **no** branch at all, and nothing asserted that a
  branch *remaps* the frame id embedded in an `extf:` key.
- Composing the fixture through `commit_all` found a defect the seam-level test
  could not: `run_commit_domains` re-raised **bare** on `on_error="fail"`. Every
  engine domain goes through `commit._commit_domain`, which prefixes the domain
  name and writes `ctx.warnings`; the extension fan-out did neither. So the one
  rollback a third party can cause was the only one that arrived anonymous — at
  exactly the moment the host's question is "engine defect, or an extension
  exercising its declared right?"

One honest limitation, stated in the file: route re-registration is
unobservable from outside, because `_record_route` keys by `"<METHOD> <path>"`
and is idempotent by construction. The exactly-once test counts what
registrations *do*.

---

## P1.2 — Audit the install payload, not the development tree

**Confirmed and fixed.** `_audit_tree` walked `rglob("*")`; the copy that
followed applied `ignore_patterns(".git", "__pycache__", "*.pyc")`. Both halves
of the review's complaint hold: a developer cannot install their own checkout,
and — worse — the set that passed the ceilings was not the set that landed.

There is now one `TreeAudit`, produced by `_source_manifest` and consumed by
both the audit and the copy, on all three install paths. A git checkout is
audited as `ls-files --cached --others --exclude-standard` would ship it; a
plain directory keeps the strict walk. Errors name the observed number beside
the allowed one; install records carry `file_count` and `extracted_bytes`;
`audit_extension_source(path)` is the dry run.

**Two corrections to the recommendation.**

1. **Trusting git's manifest whenever git answers is not safe.** A folder
   inside an unrelated repository that ignores it — `~/work/build/my-ext` under
   a repo whose `.gitignore` names `build/` — yields an **empty** manifest. The
   sketch would install nothing and then fail with "no manifest.json in the
   bundle", a misleading error for a perfectly good package. Our
   `_source_manifest` falls back to the strict walk when git's manifest holds
   no `manifest.json` at depth ≤ 2. Pinned by test.
2. **Mode `120000` is listed as a requirement but not implemented** in the
   sketch, which only calls `Path.is_symlink()`. We read the mode from git's
   index — a checkout without symlink permission writes a link as an ordinary
   file, and one staged but never checked out is not on disk at all. `160000`
   is refused as a submodule.

**On `pack` versus the manifest:** we took the manifest and added the dry run.
A pack command would be a second way to produce bytes `git ls-files` already
names, with its own artifact format and its own way of diverging from what
install measures. The invariant the review asked for — the audited set and the
copied set are identical — is satisfied without it, and the one thing authors
need beyond it is a CI check, which `audit_extension_source` gives by running
the real thing.

---

## P1.3 — Directive's test-only imports

Agreed, and agreed with the reasoning: **we will not add top-level
compatibility shims.** `db.py`, `checkpoints.py` and `app.py` at the root would
turn former internals into an accidental public API, which is the opposite of
what the reorganization was for.

The host-side half — documenting the stable public seams — is
[`docs/guides/EXTENSIONS.md`](../guides/EXTENSIONS.md), now including §4a: the
accepted anchor grammar, per-surface collision behaviour, per-surface ordering
guarantees, and how `list_channels` affects validation and merge.

---

## P2 / §6 — The hardening list

| opportunity | status |
|---|---|
| Frame-bound facade | **Built** — `api.at_frame` |
| Capability discovery | **Built** — `api.capabilities` (14 names), `api.api_version`, `ext_api` + `host_capabilities` on `GET /api/extensions` |
| Contract test fixture | **Built** — `tests/test_extension_contract.py` |
| Actionable diagnostics | **Built** — every registration refusal names the extension; stored failure reasons carry the exception type and cause chain rather than `str(exc)`; a failed extension's route dispatch says why it did not load |
| Lifecycle invariants | **Built**, and one review claim corrected — see below |
| Independent CI jobs | **Built** |
| Atomic read snapshot | **Deliberately not built** — a different axis from frame coherence (point in TIME, not choice of ERA). Registered in `docs/UNBUILT.md`, and named by a test as an example of a capability that must not be declared |
| Archive schema declaration | **Deliberately not built** — export/import already carries and round-trips extension state, char state and documents; a version number with one member is a version number nobody reads. Registered; revisit when a second home exists |

**The one review claim we had to correct.** *"Asset serving requires an enabled
extension"* is true as written and insufficient. **Enabled and live are two
different states**: an extension whose `register(api)` raises stays in the
enabled set having registered nothing. Every *dispatch* seam escaped by
accident — a failed record's hook lists are empty, so iterating them does
nothing — and every *serving* seam did not. Measured: a failed extension's
`ui.js` was handed out by `asset_path`, `extension_script` and `ui_bundle`
alike, so its browser half went on running against routes that do not exist.

A second gap the review did not find: `_deregister` dropped the extension's
Python package from `sys.modules` only on success. A failed extension kept its
modules cached — and fixing a failure means editing exactly those files.

`api.capabilities` is a promise, not a description: a name goes in when the
behaviour lands and is never removed or repurposed while `ext_api` stays 1.
`frame_coherent_reads` was deliberately withheld while it was being built in a
parallel branch and declared in the commit that merged the two.

---

## The acceptance matrix

Every row owned by Sonder is now covered by a test in `check-fast`, which means
it runs on both declared Python versions and on the Pydantic-1 job.

Two rows are Directive's and remain Directive's: atomic provisioning, and the
fail-closed player-authority correction. Two are shared and need a live pass
against this release: browser desktop/mobile, and clean install of a real
Directive bundle.

## What we did not do

- We did not extend the host's own `GET /api/chats/{id}/story_view` and
  `player_view` routes with a `frame` parameter. The extension API was the
  reviewed surface; the host UI has no consumer for it yet, and the underlying
  functions already accept it. Registered.
- We did not add a `read_snapshot` capability or the transaction behind it.
- We did not version the archive's extension schema.

Each is registered in `docs/UNBUILT.md` with the argument, not left implicit.

---

*Written 2026-08-19 for alpha 9.6. Suite green at both dependency resolutions.*
