# Causal completion holdout

## Measured result — 2026-09-15

The first pass through five previously untested scenes accounts for the **67
prelisted event propositions** in **75 event-log rows** and preserves all **14
spoken lines with their speakers**. It does **not** establish complete causal
fidelity. One compound span loses an intermediate state, and manual review
finds a key-in-lock topology omission outside the predefined structural checks.

The [evidence bundle](data/causal_completion_2026_09_15.json) preserves the input
corpus, reviewed chronology alignments, raw model replies, exact deduplicated
prompts, scoped payloads, intermediate worlds, execution receipts, observer
views, errors and call metadata. The [readable event logs](CAUSAL_COMPLETION_2026_09_15_EVENTS.md)
keep first-pass and later regression captures separate. No failed capture has
been replaced with a successful reroll.

### First unseen-case pass

| Scene | Expected propositions | Quotes | Log rows | Calls | Seconds | Structural/quote checks |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Seed case | 15 | 3 | 18 | 5 | 55.17 | 31 pass; 1 fail |
| Clip tag | 12 | 2 | 11 | 7 | 141.59 | 24 pass; 9 fail; 1 unobservable boundary |
| Coat | 14 | 3 | 17 | 7 | 128.24 | 31 pass; 2 fail |
| Two tins | 13 | 3 | 15 | 6 | 96.56 | 39 pass |
| Failed key | 13 | 3 | 14 | 7 | 322.03 | 34 pass; additional topology omission |

These counts are assertions, not independent trials or a reliability estimate.
Several assertions can expose the same underlying defect. Initial descriptions
and negative assertions can legitimately produce no state change; the finite
checklist and explicit human review remain the limits of the coverage claim.

- **Seed case:** all six lid transitions and both set-downs execute. Final
  composition initially undoes Jun's already-applied walk. The final-source
  replay now reaches the glasshouse and passes all 32 checks after a false
  doorway obstruction is fixed. The event log still marks the scoop set-down
  unresolved because contact never explicitly accounts for the untouched
  worktop reference, although its object transfer and placement execute.
- **Clip tag:** an off-row transform was incorrectly filed under the first
  private item handle, causing the recompiler to rewrite Ivo into the tag.
  This corrupts otherwise correctly named raw transfers. New validation and
  binding guards reject that response; replay honestly fails validation. The
  original Director also combines pickup and clipping, so the transient
  hand-held tag cannot be checked at a retained boundary. Both actions are in
  the account; the missing intermediate world is not certified by that fact.
- **Coat:** removal, handovers, set-downs and re-wearing preserve one coat. The
  first contact answer nevertheless says Noa holds Noa through the coat rather
  than holding the removed garment. The engine discards that self-contact,
  leaving the explicitly held intermediate without possession. The revised
  contract refuses the malformed contact instead of accepting silent loss.
- **Two tins:** all checked holders, releases, destinations and closed lids
  agree. Complementary forwarding fills six inventory omissions in the first
  dispatch. The embedded remembered instruction opens neither tin, and the
  ribbon remains on the counter.
- **Failed key:** the cup is carried, released and left in the alcove; the
  door remains locked and closed, and the folder sealed. The failed turn stays
  failed. However, the insertion is encoded as a hand pressing the lock and a
  transfer of the key `inside` a non-container door. No typed key-to-lock
  interior contact or containment survives. This is a real semantic gap even
  though all 34 predefined checks pass. Its original spatial answer also names
  a cup on rows that did not include the cup; final-source replay rejects that
  formerly accepted response. Quotes retain the correct speakers.

### Revision regression captures

These cases had already informed changes, so they are **regressions, not new
holdout evidence**.

The next tag capture uses 8 calls and 287.75 seconds. All 34 predefined checks
pass: the tag is held, mounted to the satchel, follows Ivo through the doorway,
remains attached on the bench, detaches to Tess, is released onto the bench,
and stays behind when Ivo carries the satchel away. The erroneous off-row
transform triggers repair. There is no Ivo-to-tag identity rewrite. Both
quotes survive. Its accepted responses replay without model calls; the
checked relations and event log agree. An incidental within-room cell for Ivo
differs while his room and authored station remain the same.

The next coat capture uses 6 calls and 123.95 seconds. Its 33 predefined checks
pass, including the previously missing held state. Manual review still finds
an incomplete re-wear: containment says the coat is worn by Noa, but her
wardrobe list and garment regions are empty. The model routed wearing solely
to inventory. This capture also remains in the evidence; passing the finite
parent/room checklist does not excuse the wardrobe inconsistency. A later
wardrobe-completion regression is recorded separately below.

The final coat-only capture uses **8 calls and 222.59 seconds**. Its actual body
specialist restores the same coat in Noa's wardrobe and torso/arm/waist garment
regions. Worn containment, carriage to the landing and free hands agree. The
new supplemental wardrobe assertion passes. In this particular live capture,
the Director itself routes the body hand; the automatic inventory-to-body
referral is established by its deterministic regression, not uniquely proved
by this live response.

**The final coat capture still has an intermediate conflict.** At removal
span 3, objects requests `coat → Noa, held`, while contact simultaneously
requests `containment.coat = null`. The clear wins; Noa has a real hand-to-coat
contact, but the held parent is absent at spans 3–4. The engine receipt reports
the inventory postcondition as missing instead of certifying the whole span.
This yields **31 predefined checks passed and 2 failed**, plus the separate
wardrobe check passed. It reproduces with zero model calls and identical
compared world fields/event log. The earlier wardrobe failure and this later
conflict are both retained. There were no further paid rerolls.

### Remaining limitations

1. **Contradictory effects in one span.** A containment clear and a new held
   relationship can still disagree. The receipt exposes the missing requested
   result; it does not select an invented narrative intent to settle it.
2. **Incomplete key topology.** A log entry for insertion does not establish
   the key's actual relationship to the lock.
3. **Movement after chronological execution.** The measured false doorway
   blocker is fixed, but the whole-beat movement pass still runs after onset
   execution and can clamp an already-applied move. A general redesign of that
   temporal boundary is outside these repairs.
4. **Conservative reference accounting.** Unaccounted fixture/reference items
   can leave an otherwise correct action unresolved. Seed-case scoop placement
   is the measured example. Consequently these results do not claim that every
   valid action reaches perception; unresolved physical events are withheld
   while their audit accounts and independently valid speech remain available.

### Usage and replay limits

The original five captures used **32 recorded provider calls**, **244,285 input
tokens** and **182,539 output tokens**. The first two regression captures used
**14 calls**, **112,246 input tokens** and **82,050 output tokens**. Token counts
are provider-reported; output can include reasoning. Monetary cost is not
present in the captured usage and has not been estimated. The 198-second
contact response in the key case completed successfully; latency is not a
semantic failure or pass.

The final coat-only capture adds **8 calls**, **71,916 input tokens** and
**65,198 output tokens**. Across all eight paid captures, totals are **54
recorded calls**, **428,447 input tokens** and **329,787 output tokens**. Every
replay uses zero provider calls. The separately labeled regression captures
preserve eight additional quoted lines; all **22 quoted lines across the eight
captures** match their expected speaker and words under the stated typography
normalization.

Final-source replay consumes the original seed and tin replies with zero model
calls. The old tag, coat and key replies fail the strengthened semantic checks;
those errors are preserved, not bypassed or counted as successful replays.
The later tag/coat regression replies were separately replayed with zero calls.
Receipt and binding fixes made during the investigation are therefore
distinguished from fresh model behavior. Exact captured prompts are retained
so prompt revisions cannot be confused with a frozen-model experiment.

The checker normalizes established world identity aliases, the engine's typed
posture aliases (`seated`/`sitting`), quotation glyphs and terminal attribution
punctuation. It does not rewrite the frozen expectations or accept a different
speaker. No specialist ledger in the eight captures exposes private item or
chronology IDs.

## Automated verification

- **756 focused tests passed** for the causal, physical and contract changes.
- A later **22 channel/harness tests passed**. These sets overlap and should
  not be added together.
- All **9 walking regressions passed** after the doorway-body fix and the
  test's import was aligned with the public Director interface.
- Regenerated `docs/CODE_MAP.md`; final project structure checks and
  `git diff --check` passed. The structure checker retains the repository's
  existing notice that Japanese protocol parity is deferred.
- The full run recorded **15,325 passed, 60 failed and 3 skipped**. Two newly
  failing obligation-registry expectations were subsequently corrected and
  covered by **104 passing focused tests**. The remaining **58 failing test
  names also failed the previous full run**. This is not a clean full-suite
  result; isolated follow-up checks are reported separately.

## Corpus and runner

The [frozen corpus](../../tests/data/causal_stress_holdout.json) contains five
new scenes, 67 expected semantic events and 14 spoken lines. It was written
before the first live call for this revision. The cases cover repeated lid
changes and release, an attachment that moves then detaches, coat removal and
re-wearing, two similar objects changing hands, unsuccessful action, negation,
and a quoted command that must not execute.

The [runner](../../tools/causal_stress.py) uses real Director interpretation,
specialist calls, resolution, scene composition and deterministic perception.
It does not generate autonomous character turns or a narrator, and does not
commit a production story. A fresh database per case keeps synthetic identity
and event IDs independent of which other cases are selected.

## Run and preserve evidence

```bash
.venv/bin/python tools/causal_stress.py run \
  --source-db engine.db --out /tmp/causal-completion-live \
  --provider openrouter --model MODEL_NAME
```

Omit the provider/model pair to keep the source's existing role configuration.
Only OpenRouter and NanoGPT providers are enabled in the scratch copy. The
source database is read-only; only provider/settings rows travel, never played
stories. Output directories are private and database files are owner-only.
**Do not publish scratch databases: they contain provider credentials.** JSON
and readable event-log exports are checked for copied credentials before write.

Each case directory records the original input and expectations, accepted and
rejected model exchanges, compiled program, before/after chronological worlds,
event log, observer views, warnings, call metadata and automatic checks.
Execution errors remain in the result. An existing case directory is refused,
so another run cannot silently replace the evidence. A `STOP_AFTER_CURRENT`
file in the output root stops before the next case.

## Replay without model calls

```bash
.venv/bin/python tools/causal_stress.py run \
  --replay-root /tmp/causal-completion-live \
  --out /tmp/causal-completion-replay
```

Replay has no provider credentials and blocks socket connections and DNS. Only
previously accepted responses are used, in each role's original order. A
missing or currently invalid response is an error, never a live retry or an
excuse to skip ahead. Unused accepted responses are also reported as an
incomplete replay. The result records prompt/payload drift and compares final
world fields and the entire event log with the capture. Random variant seeds
can cause payload drift by themselves; inspect the captured inputs before
interpreting the drift. Replayed correctness is not fresh model reliability.

The checked-in evidence can be unpacked without credentials or a scratch
database:

```bash
.venv/bin/python tools/causal_stress.py unpack \
  --bundle docs/experiments/data/causal_completion_2026_09_15.json \
  --run initial --out /tmp/causal-captured
.venv/bin/python tools/causal_stress.py run \
  --corpus /tmp/causal-captured/corpus.json \
  --replay-root /tmp/causal-captured --out /tmp/causal-reproduced
```

Use `--run regression` to unpack the separately labeled second captures and
select their case IDs for replay. Old replies rejected by the current contract
must still produce the documented replay errors.

## Score actual states

Final physical state, speaker-attributed quotations and non-events are checked
automatically. Intermediate states need a reviewed mapping from each fixture
event to the actual `stage` and `chrono_id` boundary:

```json
{
  "seed_case_repeated_lid_and_release": {
    "e01": {"stage": "interpret", "chrono_id": 1},
    "e02": {"stage": "interpret", "chrono_id": 2}
  }
}
```

```bash
.venv/bin/python tools/causal_stress.py score \
  --root /tmp/causal-completion-live --alignment /tmp/reviewed-alignment.json
```

The fixture event number is **not** assumed to be a Director chronology ID.
One span may validly transform several objects; a model may split one compound
action into several spans. Reviewers align meanings explicitly and inspect
ordering. Unaligned checks stay `unreviewed`, never pass by default. Merged
spans cannot prove an intermediate state they never retained. Exact worded
propositions and additional events still need human review; a structural check
cannot discover every semantic omission or fabrication.

Quoted words and speakers must match, with whitespace, surrounding quotation
marks and terminal attribution punctuation normalized. Repeated lines require
separate matching speech rows. Typed world checks verify parent relationships,
rooms, placements, residual grips, explicit state fields and object counts;
the scorer never derives engine operations from English.

Once a case informs a contract revision, call it regression evidence. Do not
present repeated tuning against this corpus as an independent holdout rate.
