# Disposition of the 46-finding review bundle

Reviewed artifact: `Sonder_Engine_Review_Complete_Bundle_Main_48920a7`, baseline
`48920a7` (`alpha9.6.1`). This is the point-by-point answer, written against
`main` after the work landed.

**Every one of the 46 was triaged against current source, and every actionable
one is fixed or explicitly deferred with a reason.** Seven commits,
`73a380a..6f70cb3`, 79 files, +8,103/−710. The suite went 8,243 → 8,450 —
207 new regression tests, each written failing first — and is green on both
dependency resolutions (system Python, and the pinned `constraints.txt` stack
the launchers actually build).

| Verdict | Count |
|---|---|
| REAL | 32 |
| PARTIAL — the finding is right, the proposed remedy is not | 11 |
| REFUTED | 3 |

**Zero were already fixed.** The baseline was two commits stale and the register
warned to revalidate; in the event, nothing in those two commits touched
anything the bundle found. That is a point in the review's favour.

---

## 1. This round was substantially better than the last

The previous review's response spent most of its length on refutations. This one
does not. Three findings out of 46 do not survive contact with the source, and
the other 43 describe real code. Several are things no amount of local testing
here would have surfaced.

The five that most earned their keep:

**SE/MASTER-027 — lorebook plans can write outside their tree.** The sharpest
finding in the bundle and correctly rated P0. `update_lore` ended in
`UPDATE lore_entries SET ... WHERE id=?` — no `lorebook_id`, no `chat_id`, no
`canon_locked` check — and the plan applier passed the model's id straight to it.
Reproduced end to end: a plan applied for chat A overwrote a **`canon_locked`
entry belonging to chat B** and parented a chat-A book under chat B's book,
returning `ok: True`.

**MASTER-046 — schema drift between fresh and migrated databases.** Real, and
the half you found was the harmless one. See §4.

**MASTER-012 — 3.13 declared but untested.** One line, and the sharpest kind of
gap: both launchers try 3.13 *first*, so the interpreter a fresh player is most
likely to receive was the one no gate had ever run.

**MASTER-045 — no regression budget on package cycles.** The best-evidenced
architecture finding, and the one that correctly distinguishes itself from
re-litigation: the design note declined an import *linter* while designating its
table "the baseline a future cleanup should measure itself against". Nobody built
that. We measured the tree at two commits one day apart, all gates green
throughout, and found three edges had gained eager module-level imports inside
existing cycles in 24 hours.

**MASTER-017 — remote first-run claim.** `/api/auth/setup` was public and took no
`Request` at all. Correct, and it matters more than the bundle argued, because
the app ships its own network-exposure instructions.

---

## 2. Where the finding was right and the remedy was wrong

This is the largest category and the most useful feedback we can give. In each
case the diagnosis was accurate and the prescription would have cost us
something.

**MASTER-026 — the proposed monkeypatch checker would have flagged 71 correct
tests and zero real ones.** The rule "patch the owner, not the compatibility
export" is not this codebase's rule. We AST-scanned every `monkeypatch.setattr`
site in `tests/`: **zero** patch a facade re-export whose reader has moved, and
71 patch a re-exported name whose owner is a different module — every one the
ordinary patch-where-used idiom. Obeying the rule would have made 71 working
tests stop working. The correct rule is "patch the module whose globals the
reader resolves", which is a call-graph question an export-owner map cannot
answer. We built the narrow version instead: for a facade patch, assert no
sibling in that family both imports the name and calls it. Zero violations.

**MASTER-008 — the `duplicate column` swallow is the crash-recovery mechanism.**
DDL runs in autocommit, so a mid-list failure leaves earlier statements applied
with the version not advanced; the swallow is what makes the re-run succeed, and
`TestARebuildMigrationSurvivesACrashedRebuild` pins it. Removing it trades a
latent hazard for a wedged upgrade. We took the introspection half —
`PRAGMA table_xinfo` instead of matching an error message — and left the
restructure alone.

**MASTER-015 — per-client rate-limit keying is wrong for a single-user app.**
The race is real and now fixed with a lock and an atomic check-and-consume
(measured at the route: 20 concurrent logins yielded 20×401 before, 10×401 +
10×429 after). But keying by IP on an application with exactly one legitimate
user hands a rotating-source attacker an unlimited budget. The limit stays
global.

**MASTER-019 — `GZipMiddleware` is the thing the custom middleware replaced.**
The `Vary` merge bug is real and fixed. The suggested alternative of adopting
Starlette's middleware is recorded in that module's own docstring as having
stalled the NDJSON turn stream.

**MASTER-004 — the `BackgroundSupervisor` merges two modules kept separate on
purpose.** Every factual claim holds. But concurrency is bounded in practice by
the dedup keyspace, and `core/outofband.py` declines a thread pool deliberately
and on the record. We took the two pieces worth having — staleness on `reset()`,
and a public drain API for the lifespan shutdown — and skipped the rewrite.

**MASTER-025 — a 1500/3000-line budget fires on 21 of 111 files on day one.**
The measurements are right (eight engine files over 3,000 lines). But the
function-level version of this is already registered, three of the eight are
explicitly deferred or *declined* by our own design notes, and a gate shipping
with a 21-entry exception list is one that gets waived rather than obeyed. We
registered the census as measured fact and split nothing.

**MASTER-023 — the proposed fix is built on tables that do not exist.** The
firewall breach is real (§3). The remedy references `observations` and
`subject_actions` tables that are not in the schema. The actual fix was smaller:
generate memory seeds from the presence's own quoted lines and conduct tail,
which is fail-closed by construction.

**MASTER-028 — the warrant architecture is a proposal; the defect is a hole in
the guard that already exists.** A structured movement warrant would refuse
legitimate dragged, carried and lift-borne moves — the existing floor's docstring
argues this correctly. The real bug is that the floor's exemption set was built
unconditionally for every body sent to the same destination whenever *any* move
was declared, so on a **legal** move every other body skipped route checking.

**MASTER-039 — the collision half is already guarded, twice.** The bundle did not
read the guard. Ambiguity deliberately refuses to merge, on the stated ground
that an over-merge welds two characters into one, which is worse than a split a
name would fix. The **fragmentation** half was real and unguarded, and is fixed.

**MASTER-010 — severity is retrieval quality, not disclosure.** The integrity gap
is real and now validated. But embeddings are opaque float32 used only for cosine
ranking; `_cos` returns 0.0 on a dimension mismatch rather than raising, and the
cross-chat chain needs the victim's exact bytes to forge a colliding key. The
worst outcome is memories ranked at zero relevance.

**MASTER-043 — the headline claim is refuted by measurement.** See §3.

---

## 3. The three refutations, and one partial

**MASTER-029 — interpret repair cannot delete a player act. REFUTED.**
`_reconcile_interpretation` is **append-only**: `out["sequence"] = old + new`.
There is no code path that removes or replaces an element. The semantic check the
finding asks for already exists and runs against the raw player input:
`_uncovered_declarations` splits `ctx.input` into declaration units and tests each
against the coverage corpus, triggers a bounded repair, re-checks
**deterministically after the merge**, and raises a `PLAYER AUTHORITY` warning for
anything still uncovered. `repaired` is metadata on the step record, not an
acceptance gate. The proposed `validate_interpret_semantics` layer would duplicate
an existing stronger test.

*One real residual we logged separately:* the uncovered-unit list truncates at
four, so a long multi-clause input dropped wholesale loses clauses 5+ silently.

**MASTER-034 — multi-worker lore-job ownership. REFUTED.** No shipped
configuration runs more than one worker. `make run`, `make serve` and both
launchers invoke `uvicorn` with no `--workers`. Within one process the mechanism
is correct, and the "no staleness timeout to tune" criticism inverts the design's
virtue: the owner token is regenerated per process, so orphan reclamation is
exact across a restart with no heartbeat to skew. The finding hedged this itself.
The residual is documentary — the single-worker contract is not written down.

**MASTER-038 — `ActionStage` is not a reliable semantic contract. REFUTED.**
`stage` is read: `_REACTIVE_STAGES` drives `_requires_reaction_phase`, which sets
`resolution_flags["contested"]` and inserts the `reaction_loop` into the plan. The
finding appears to have read two comments stating `stage` is unread *on the
resolve path* — a deliberately narrower claim — and generalised. The
recommendation to constrain resolver effects by stage is the approach this repo
measured and rejected against a 1,249-turn corpus, with last-element stage alone
producing false positives that blocked legitimate arrivals; that is why
`MovementDecl.arrives` exists as a separate field. We took the one real fragment:
an alias map so an off-vocabulary stage word costs no repair call.

**MASTER-043 — PARTIAL, and the headline is wrong.** We ran crafted inputs rather
than reading the parser. A 200 MB zlib bomb compressed to 203 KB inflated to
*exactly* 10,485,760 bytes and stopped — `decompressobj().decompress(rest, _MAX)`
already bounds it. A 4-byte length field of `0xFFFFFFF0` allocates nothing in
Python and ends the loop. Two of seven bullets are non-issues. But the finding did
contain one real vector nobody had flagged at the top: **no size cap before
`base64.b64decode`**, on precisely the path documented for importing files from
community boards. Fixed.

---

## 4. What the bundle led us to that it did not itself find

Offered in the spirit the findings were: several of these only surfaced because a
finding pointed at the right file.

**MASTER-046: you found the harmless twin.** `memories_fts` is dead — dead table,
no reader. Its twin has a live one: `lore_fts` supplies the 0.35 keyword term of
`search_lore`. Fresh databases have **zero** FTS triggers, because six of them
existed only inside `MIGRATIONS` while `init()` stamps a fresh database straight
to `SCHEMA_VERSION` and skips the chain. Measured: a fresh database returns `{}`
from the keyword scorer where the developer's migrated one has 2,322 rows.
**Every Sonder install created since that change has ranked lore on the vector
term alone** — the keyword half scoring 0.0 for every entry, silently, forever.
That is the class the fix's own fresh-vs-migrated equality guard now closes.

**And the naive fix would have corrupted live databases.** Adding the triggers to
`SCHEMA` fixes fresh installs, but live triggers over a *desynced*
external-content FTS index corrupt it on the next UPDATE — we hit
`database disk image is malformed` while writing the test. The change needed a
migration that rebuilds both indexes, not just a schema move.

**MASTER-027 has a second half.** The guard alone would have made `allow_updates`
a dead feature, because the generator prompt *asks* the model for
`{"op":"update","id":…}` while the context builder sends it **no entry ids at
all** — so every update op it can produce carries a hallucinated integer. Against
2,322 entries with ids spanning 9–3880 across ~20 chats, an invented id has
roughly a 60% chance of landing on a real row in a different story. We closed
both sides: the scope guard, and sending real ids.

**MASTER-031 loses data on the success path too.** The missing transaction is
real (three entries in, a failure on insert 3 left two rows and the third gone
permanently). But even a fully successful reinterpretation dropped `title`,
`importance`, `aliases`, `knowledge_tag`, `knowledge_range`,
`knowledge_locations`, `scope`, `relations` and `source_notes` on **every entry,
every time**. The knowledge fields decide who can retrieve an entry.

**MASTER-022 has a third writer.** Beyond the two the finding names, the
sight-visible loop was unconditionally minting a route edge to every room a
character could merely *see*.

**MASTER-002 escapes to the route.** Beyond the wedged signature, the raise
reaches the HTTP handler unwrapped, so the host gets a 500 instead of the
documented "pending".

**MASTER-011: mtime is the wrong mechanism.** Porting the `.sh` checks to the
`.bat` would have inherited a flaw — a fresh `git clone` gives every file the
same recent mtime, so `-nt` was answering a question about the filesystem rather
than about dependencies. Both launchers now stamp a digest.

**MASTER-035: the comment's claim is unreachable.** `pyproject.toml` justifies its
Python upper bound by saying it makes `pip install -e .` "fail with the reason
instead of a build log". Tested: the flat-layout discovery error fires first, so
the bound cannot deliver what its own comment claims.

**MASTER-042 is worse than stated.** The paths name a *pre-rename* project
directory and, in four files, a `.claude/worktrees/` path that does not exist on
the developer's machine either — so those scripts could not run anywhere. Had
that worktree existed, they would have silently exercised a different checkout
than the one under review.

**MASTER-014: one of the stale docs is an instruction to coding agents.**
`CLAUDE.md` and `AGENTS.md` both assert that `from commit import X` "stays the
universal import path". It raises `ModuleNotFoundError`. `EXTENSIONS.md` tells
extension authors to `import db`.

---

## 5. Deferred, with reasons

Not everything actionable was actioned. These are open and recorded:

| Item | Why not now |
|---|---|
| **017** cloudflared residual | Loopback-only closes `--host 0.0.0.0`. The tunnel runs *on the host machine*, so tunneled requests arrive as `127.0.0.1` and are indistinguishable from the owner's browser. Closing it needs a console bootstrap token, which changes the first-run workflow — an owner decision, not an engineering one. Announced at startup meanwhile. |
| **028** commit-path route check | The Director path is guarded. The merged diff is still applied at commit with no route check, so a hand-edited variant or rerun-from-stage bypasses it. Needs its own guard; landing it untested beside a gate is how a green suite ships a broken engine. |
| **024** basis requirement | Reciprocity landed. Requiring a stated basis for a new adjacency is a schema and prompt change across two specialists. Note: we landed the room-existence check the triage called obvious, watched a live mapping flow fail (edges are legitimately minted before rooms exist), and removed it. |
| **036** `activity` expiry | Breath and voice quality now expire. `activity` is the sharpest read-back key and an existing test pins it as load-bearing standing state; that contract needs deciding first. |
| **`memories_fts` drop** | Deferred until the new fresh-vs-migrated equality guard has proven itself. Removing it now breaks the guard's migrated-path construction. |
| **005** ContextVar allowlist | Not implemented, deliberately. The proposed test asserts the **opposite** of an existing green one — an arbitrary ContextVar reaching the worker is the documented contract. An audit of every ContextVar in the tree found none escaping. A structural guard was added instead. |
| **030** UI display | **Closed after this document was first drafted.** Refused operations now raise a warning toast and a dialog listing them, because a plan review screen that asks for approval it does not honour is worse than one that refuses loudly. |

### Which of these actually costs you something in play

Asked directly, and answered against source rather than from the disposition
table, because "partial" flattens two very different things.

**Two will show up in ordinary play:**

**036's `activity` key.** The expiry mechanism is built and `activity` is not
wired into it — and the function's own docstring names the case it does not
cover: *"an entity the diff is silent about is precisely the one whose 'running'
has gone stale"*, where `running` is an `activity` value. `breath` and
`voice_quality` expire; the key the register calls the sharpest read-back does
not. A body that stopped doing something keeps reading the old activity as its
own current state, and that feeds its next declaration and the memory of the
beat. This is the most likely of everything open to be noticed by a player.

**024's basis requirement.** The minted-edge shield is explicit about its own
scope: it refuses one-sided unsealing through a standing `wall`, and checks
neither geometry, nor basis, nor the existence of the target room. So a model
asserting a fresh adjacency between two known rooms with no standing declaration
in either direction is still accepted — which is precisely the measured
`r0204 <-> r0303` class that stood for hundreds of turns and was walked as a
real doorway. Narrowed, not closed.

**The rest are not functional:**

- **028's commit-path gap** needs a hand-edited `director_resolve` variant or a
  rerun-from-stage to reach; the Director path that normal play uses is guarded.
- **008, 005, 025, 026** change no behaviour at all — they are hazard budget and
  tooling.
- **`memories_fts`** is a dead table with no reader; its dangerous twin is fixed.
- **017's tunnel residual** is a security exposure rather than a functional one,
  and only on the window between starting a tunnel and claiming the instance.

---

## 6. Process notes

Two things about the bundle's own construction, offered as feedback.

**The metadata's honesty is the best thing about it.** Recording that no full
checkout was available, that the suite was never run, that one probe was
executed and the rest are source-confirmed, and instructing "revalidate every
finding if main advances" — that framing is what made the bundle usable at speed.
We triaged against source before touching anything, and the three refutations
were all cases where source contradicted a plausible reading.

**Reproduction separates the strong findings from the weak ones.** Every finding
that survived verification cleanly was one where the mechanism could be
demonstrated. The three refuted ones and the worst-calibrated severities are all
cases where a code path was read but not executed — most visibly the zlib bomb,
which is bounded by a line adjacent to the one quoted.

**Nine of the REAL findings were already registered in `docs/UNBUILT.md`** — §1.2,
§1.3, §1.6, §1.8, §1.10, §1.17, §1.31, §1.35 and §1.52 — several with sharper
diagnoses and live measurements. That is not a criticism of the review, which had
no way to know; it is a signal that the register is worth reading before the next
pass, and it is public.

Those rows have since been brought up to date, so a reader following the section
numbers above will not find all of them: §1.3, §1.6, §1.8 and §1.31 are deleted
(landed), §1.2, §1.10 and §1.17 are narrowed to only what remains, and §1.35 is
corrected — its trigger-drift claim was general and is now true of the dead
table alone. That housekeeping is the register's own documented rule ("delete an
entry in the commit that lands it") and it was missed across all seven commits
before being caught; a register that overstates its debt is the exact condition
that made nine of these findings look new.

---

## 7. Full disposition

| ID | Verdict | Disposition |
|---|---|---|
| 001 | REAL | Fixed — start failure files the job, slot released |
| 002 | REAL | Fixed — cancel after successful start, incumbent restored |
| 003 | REAL | Fixed — identity check on the error write |
| 004 | PARTIAL | Staleness + drain API fixed; supervisor rewrite declined |
| 005 | PARTIAL | Not implemented (contradicts an existing contract); structural guard added |
| 006 | REAL | Fixed — unstamped foreign file refused, untouched |
| 007 | REAL | Fixed — too-new schema refuses to open |
| 008 | PARTIAL | Introspection taken; restructure declined (crash recovery) |
| 009 | REAL | Fixed — archive version gate before the transaction |
| 010 | PARTIAL | Fixed; severity downgraded to retrieval quality |
| 011 | REAL | Fixed — digest stamp in both launchers |
| 012 | REAL | Fixed — 3.13 in matrix + agreement check |
| 013 | REAL | Fixed — static and DB default anchored to install root |
| 014 | REAL | Fixed — four sub-claims + two more found by the new checks |
| 015 | REAL | Fixed — lock + atomic claim; per-IP keying declined |
| 016 | REAL | Fixed — algorithm/factor stored, upgrade on login |
| 017 | REAL | Fixed for LAN; tunnel residual open and announced |
| 018 | REAL | Fixed — `SONDER_PUBLIC`, single cookie writer |
| 019 | PARTIAL | Fixed (merge); middleware swap declined |
| 020 | REAL | Fixed — startup sweep with retention + indexes |
| 021 | REAL | Fixed — sleepers from the awareness ledger |
| 022 | REAL | Fixed — one predicate, three writers, retraction path |
| 023 | REAL | Fixed — seeds fail-closed; P0→P5, autopromotion off by default |
| 024 | REAL | Reciprocity fixed; basis requirement deferred |
| 025 | PARTIAL | Census registered; no file split |
| 026 | PARTIAL | Narrow guard built; proposed checker declined (71 false positives) |
| 027 | REAL | Fixed — subtree scope + real ids sent to the model |
| 028 | PARTIAL | Exemption narrowed; commit-path gap deferred |
| 029 | REFUTED | Repair is append-only; existing check is stronger |
| 030 | PARTIAL | Fixed — refusals surfaced; UI display outstanding |
| 031 | REAL | Fixed — transaction + full metadata carry-through |
| 032 | REAL | Fixed — embeddings up front, insert in a transaction |
| 033 | REAL | Fixed — strict parse at nine authoring sites |
| 034 | REFUTED | No multi-worker configuration ships |
| 035 | REAL | Fixed — build-system + explicit packages |
| 036 | REAL | Transients expire; `activity` deferred |
| 037 | REAL | Fixed — view routed through the carriers enumeration |
| 038 | REFUTED | `stage` drives reaction-loop insertion; alias map taken |
| 039 | PARTIAL | Fragmentation fixed; collision already guarded |
| 040 | REAL | Fixed — floors raised to versions actually run |
| 041 | REAL | Fixed — one source inventory |
| 042 | REAL | Fixed — eleven sites + a static check |
| 043 | PARTIAL | Size cap fixed; bomb claim refuted by measurement |
| 044 | REAL | Fixed — AST rule, no exemption list |
| 045 | REAL | Fixed — generated baseline, fails on a new SCC |
| 046 | REAL | Fixed — triggers on both paths + rebuild migration + equality guard |

---

## 8. Verification

- **8,450 tests**, green on system Python and on the pinned `constraints.txt`
  resolution. Both, because the gap between those two resolutions has hidden a
  live defect in this repository before.
- Structural checks clean; code map regenerated; both language packs load.
- **Not verified locally:** Python 3.13. It is not installed on the development
  machine, so the new matrix leg and the raised `numpy` floor are reasoned and
  wheel-checked rather than executed. CI is the authority on those.
- The developer's live database was read **read-only** throughout. First launch
  after this lands runs the v30→v31 FTS rebuild — sub-second, idempotent, and
  required for correctness rather than cosmetic.
