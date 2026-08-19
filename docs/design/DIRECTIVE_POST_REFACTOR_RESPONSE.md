# Response to the Directive post-refactor findings

The Directive team verified `main` at `48920a7` (`alpha9.6.1`) and filed
`SONDER_POST_REFACTOR_FINDINGS.md`. This is the point-by-point answer, written
against `main` after the work landed.

**Summary: all three Sonder-owned findings are fixed, and none of them needed
refuting.** That is worth saying plainly, because the previous round's response
spent most of its length on two refutations. This report was accurate on every
point it made about this codebase, including one — the Windows path comparison
— that no amount of local testing here would have found, because every gate in
this project runs on POSIX.

Two items on their deferred-hardening list are declined, with their own
arguments. One is built.

Baseline for everything below: `main` at `7bebcf3`.

---

## Sonder P1 — the structural checker false-failed on Windows

**Confirmed, fixed, and it was worse than one line.**

`tools/project_check.py` compared `str(path.relative_to(ROOT))` against
`INSTALL_ROOT_OWNER = "core/paths.py"`. On Windows that produces
`core\paths.py`, so the one file *permitted* to derive a filesystem root
audited itself as a violation — and a maintainer on Windows could not get a
green result out of the tool this project calls its local evidence gate.

Their proposed `.as_posix()` is exactly right. What it did not say, and what
made the bug possible: **eight other sites in that same file already used
`.as_posix()`.** Line 313 was the lone survivor of an earlier sweep. A rule
applied everywhere except one place is invisible precisely because the file
looks consistent when you read it.

So all four `rel = …` derivations are now normalised, message-only sites
included. The distinction between "this one is compared, that one is only
printed" is real but it is not worth remembering, and the next person to add a
`rel = …` should not have to know which kind theirs is.

Pinned by `tests/test_directive_post_refactor_findings.py`, asserted through
`PureWindowsPath` so the guard fails on Linux too. A test that can only run on
the platform it is broken on is not a guard.

**Still theirs to confirm:** nobody has run `project_check.py` on real Windows
since the change. The fixture proves the comparison is separator-independent;
it cannot prove the whole checker is.

## Sonder P2 — installer diagnostics replaced a cause with a symptom

**Confirmed, fixed, and their diagnosis found a second instance of it.**

`_git_source_files` caught every `ExtensionError` and returned `None`, so git
refusing their checkout for dubious ownership was read as "this is not a
repository". `_source_manifest` then walked the directory strictly — `.git`,
`node_modules`, every ignored artifact — and reported

> extension source holds at least 4097 files, more than the 4096 an extension
> may install

for a package git would have shipped as 207 files and 8MB. The host was told to
shrink an extension that was never too big, and never told the thing they could
have fixed with one `git config` command.

`_git_says_not_a_repository` now separates the two: git saying, in its own
words, that this is not a repository is an ANSWER and keeps the plain-directory
fallback; anything else is an inspection failure and re-raises with its cause.
Matched on wording rather than exit code, because git returns 128 for both, and
deliberately narrow — an unrecognised failure re-raises, which is the safe
direction. A real cause reported oddly beats a wrong cause reported clearly.

The `ls-files` swallow was the second instance and is gone outright rather than
narrowed. `rev-parse` has already answered `true` by the time it runs, so
returning `None` there claims the directory is not something git *just said it
is*. There is no reading of that failure under which the fallback is correct.

Both cases pinned, including the one they asked for: `rev-parse` establishes a
repository, `ls-files` fails, and the original failure is not replaced by a
size error.

## Sonder P1 — exact-main CI had no browser result

**Confirmed. Fixed, and green.**

Their reading of the history is right, and the part worth recording is that the
previous repair worked and was still not enough. The step timeout added in
`f46588a` turned a fifty-minute silent hang into a twelve-minute reported
failure. That made the failure *legible*; it did not make provisioning
*deterministic*, and the release commit therefore had passing Python jobs and no
browser evidence at all.

Their recommendation 3 is the one taken. `--with-deps` shells out to apt-get,
and apt is the part that is not deterministic here — the same command succeeded
on the runs either side of the failure, which is the signature of a mirror and
not of a missing dependency. The libraries are already on the runner image;
`--with-deps` exists for bare containers. It is gone, and the browser payload is
cached on the pinned Playwright version instead.

If a future image does drop a library, Chromium fails to launch and names it,
which is a better failure than twelve minutes of Ubuntu font packages.

Result on `9551786`:

```
Checks (Python 3.11)      success
Checks (Python 3.12)      success
Browser behavior          success
    Install Chromium              success
    Run browser behavior tests    success
Schemas on Pydantic 1.x   success
```

Their recommendations 1 and 4 stand as written: the finite timeout is kept (now
6 minutes, under the job's 25), and a fresh exact-main browser pass is the gate.

**Note on their recommendation 2** — a pinned Playwright image matching the
installed version — is a better answer than caching if this ever regresses
again. It is not taken now because removing apt removed the failure, and a
container adds a moving part to a job that currently has none.

---

## Deferred hardening: one built, two declined

### Built — `frame` on the host's own view routes

Their table calls this "No immediate Directive blocker", and that is accurate.
It is built anyway, because the asymmetry is its own defect: `api.at_frame` let
an in-process caller compose a frame-coherent read while the HTTP twin — the
only surface a companion app, a script or a second machine can reach — could
not say which era it wanted. Two doors onto one room, and one of them could not
name the era.

`GET /api/chats/{cid}/story_view` and `…/player_view` take `frame`. It is
**omitted, not defaulted**, when the caller does not ask: the underlying default
is a sentinel meaning "the latest committed turn across every frame", and `None`
is a different question that would be validated as a frame id. A route that
always passed the parameter would turn "I did not ask" into "frame None".

### Declined — the archive does not declare its extension schema

The register's argument for deferring this still holds, and their own wording
agrees with it: *"future extension-home evolution will need an explicit
completeness/version contract."* Future. A completeness contract designed
against exactly one extension encodes that extension's shape as the standard,
and a version number with one member is one nobody reads. Building it now would
mean inventing the second consumer in order to design for it.

What exists today is tested carriage of `ext:<id>`/`extf:<id>` state, char state
and documents through export, import, checkpoint and branch. What is missing is
the declaration that lets an importer tell complete carriage from partial. That
remains in `docs/UNBUILT.md` § 6.2, unchanged.

### Declined — no read-snapshot token

Their table says "Retain as concurrency hardening", and that is the right
disposition. Recording why it is not folded into the frame work, since the two
look adjacent and are not: `at_frame` chooses an **era**; a snapshot would fix a
**moment**. Different axis, and doing it properly means a read transaction
spanning several domains rather than a parameter.

There is a test — `test_no_capability_is_declared_for_work_that_is_not_built` —
that exists to stop the capability being *declared* before the machinery is
real. Half-building this is the exact failure it was written to prevent, so the
honest state is: not built, not declared, named in the register.

---

## Acceptance matrix, Sonder-owned rows

| Behavior | Their evidence | Now |
|---|---|---|
| Python 3.11 / 3.12 | exact-main jobs passed | unchanged |
| Pydantic 1.x and 2.x | complete 1.x job plus pinned stack | unchanged; both stacks run on every local gate too |
| Browser behavior | last green run; exact-main timed out | **green on `9551786`, tests executed** |
| Structural checker | failed on Windows | fixed; Windows confirmation is theirs |

Completion criteria 6 and 7 are the two that were ours. 6 is closed. 7 is closed
in the code and open in the verification.

Criteria 1–5 are Directive-owned and their document is accurate about them,
including the harness failing at `import db` — that is the P1 test-import
migration they predicted, not a production loader fault. The refactored owner is
`core.db`; the engine is not an installed package and is still run from the
repository root.

---

## What changed here since their baseline

`48920a7` → `7bebcf3`, four commits. The three findings above, the `frame`
parameter, and a documentation pass that corrected `README.md` (it still
described the pre-reorganization flat module root and named `from db import q`),
the test counts in four places, and `pyproject.toml`, which had carried a
placeholder version through nine releases and declared no upper Python bound
though the pinned `pydantic-core` has no wheel above 3.13.

Suite: 8,226 tests, green on both dependency resolutions.
