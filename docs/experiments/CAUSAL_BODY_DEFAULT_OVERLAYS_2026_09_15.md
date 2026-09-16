# Body-default surface assessment stress — 2026-09-15

## Measured result

The single new live scene validates the intended model contract: the Director
routes surface-only changes through **body**, and the body specialist adds and
removes the same mark using its always-loaded surface instructions. An ordinary
cap removal creates no mark, and a brief smile remains a transient action.
All **7 prelisted events and 3 correctly attributed quotes** survive.

The capture also found an engine bug: onset preview did not apply overlays,
although final composition did. The body applier was corrected, and a
**zero-call replay of the exact captured responses** now adds, preserves and
removes the mark at the correct boundaries in both stages. Both onset and
outcome perception include the application, smile and wipe in order. The
original failing onset snapshots remain in the evidence. No corrective paid
run was necessary because the model's output was already correct.

The [frozen fixture](../../tests/data/causal_overlay_default_stress.json) was
written before the live call, including all manual checks. SHA256:
`6aa3a2e5cf466b78cb499dcf45ae473dddfd0cf3b7456557ecbf71514ff158c5`.
The [evidence bundle](data/causal_body_default_overlays_2026_09_15.json) preserves
exact prompts and scoped payloads, replies, both stages' intermediate worlds,
receipts, event logs, observer views, reviewed alignment, and stage comparisons.
The [readable log](CAUSAL_BODY_DEFAULT_OVERLAYS_2026_09_15_EVENTS.md) shows both
onset histories and observer views, making the initial omission visible beside
the corrected replay.

## Input and expectations

At a washstand, Sela puts a small blue dot on her left cheek and asks Bram
whether he sees it. Bram removes his grey cap and keeps it in his left hand,
confirms the dot's location, and sees Sela smile briefly before wiping the dot
completely away. He confirms it has gone. The dot should survive the intervening
speech and unrelated cap change, then disappear at the wipe; cap removal and
smiling must not generate persistent surface marks.

| Semantic event | Chrono | Final composed result | Initial onset | Fixed-code onset |
| --- | ---: | --- | --- | --- |
| Add cheek dot | 1 | Mark present; applied | Mark absent; unresolved | Mark present; applied |
| Sela asks about dot | 2 | Speech recorded; mark persists | Speech recorded; no mark | Speech recorded; mark persists |
| Bram removes/holds cap | 3 | Attire, held parent and left-hand grip agree | Cap correct; no cheek mark | Cap correct; cheek mark persists |
| Bram confirms location | 4 | Speech recorded; mark persists | Speech recorded; no mark | Speech recorded; mark persists |
| Brief smile | 5 | Recorded action; no persistent change | Recorded action; no mark | Recorded action; mark persists |
| Wipe dot completely away | 6 | Mark absent; applied | Already absent; unchanged | Mark absent; applied |
| Bram confirms removal | 7 | Speech recorded | Speech recorded | Speech recorded |

The finite checker reports **18 structural/quote assertions passed** in the
capture and the replay, plus four reviewed events without additional state
assertions. It reads the final composed chronological worlds, so its initial
pass count does **not** certify onset correctness. Manual review and the
supplementary overlay-stage comparisons identify that distinction explicitly.

## Contract and lifecycle findings

- Director addition/removal rows use `categories: ["body"]`; no row names
  overlays as a Director category.
- The captured body call contains the full overlay decision and lifecycle
  instructions. It handles both surface rows and the ordinary attire row.
  This demonstrates the behavior of that call; deterministic scope tests cover
  other call configurations.
- Body emits `name: "small blue dot on left cheek"` with `active: true`, then
  exactly the same name with `active: false`. It does not invent a second mark
  or use a transient expression as an overlay.
- Bram's cap leaves his wardrobe, remains the same world object, and becomes
  held with a left-hand grip. His brown coat remains worn. Neither Bram nor
  the cap receives a surface mark.
- Smiling has an empty category list and a recorded action receipt. It appears
  in perception without being persisted as a condition or appearance change.
- The three quoted lines preserve both wording and speaker. No extra physical
  event is created for the closing negative assertion.

## Engine correction and replay limits

The initial `preview_player_state_assertions` path applied attire inside each
chronological span but omitted the overlay merger. Consequently the addition
correctly failed postcondition verification during onset, and the action was
withheld from `perception_act`; the later final composer did apply the mark.
The corrected onset body applier now uses the existing overlay merge before
attire, matching final composition. This is an execution correction, not a
prompt reroll or a relaxed verifier.

The replay uses **zero provider calls** with network connections and DNS
blocked. All five accepted request prompt/payload pairs match exactly, every
response validates, and there are no unused replies or replay errors. All nine
standard compared world fields and the entire final event log equal the live
capture. Because the general runner does not include overlays in that field
list, this audit additionally compares **final overlays and every composed
overlay boundary**, and compares onset against composition after the fix.
Onset state and its observer delivery intentionally differ from the original
capture; the original failure is retained. Replay verifies deterministic
execution of these captured answers, not an additional fresh model success.

## Usage and artifact safety

One live scene used **5 OpenRouter `z-ai/glm-5.2` calls, 29,597 input tokens and
4,910 output tokens**, completing in **19.78 seconds**. No model validation
repair or full-scene reroll was needed. Counts are provider-reported; monetary
cost was not captured. The fixed-code replay completed in 0.58 seconds with
zero calls.

The runner uses a fresh private synthetic database; provider/settings
configuration is read-only at its source and no played story is copied or
committed. Scratch databases and credentials are not exported. Evidence and
readable logs are checked against configured secrets, and specialist payloads
contain no private item or chronology IDs.

## Reproduce from captured answers

```bash
.venv/bin/python tools/causal_stress.py unpack \
  --bundle docs/experiments/data/causal_body_default_overlays_2026_09_15.json \
  --run initial --out /tmp/body-default-captured
.venv/bin/python tools/causal_stress.py run \
  --corpus tests/data/causal_overlay_default_stress.json \
  --replay-root /tmp/body-default-captured \
  --out /tmp/body-default-replayed
```

The bundle's `alignments.initial` contains the reviewed event-to-chrono map.
Use it with `score --alignment`; event numbering is not automatically assumed
to equal the Director's segmentation. These results cover one novel scene,
not a general reliability estimate.

## Regression validation

- Added **38 regression cases** for default scopes, forwarded and repaired body
  work, retired route compatibility, optional surface duties, exact overlay
  referrals, per-mark verification, and chronological onset delivery.
- Final focused run: **463 passed**, including both language contracts and all
  five category-publication checks described below.
- Full suite: **15,465 passed, 35 failed, 3 skipped** in 649.94 seconds. Thirty
  failure names **and their reported failure details** exactly match the prior
  completed full-suite baseline. The other five expected every owned output
  channel to appear as a Director category; those expectations were updated to
  require the published owner route for default duties. All five pass in the
  final focused run. No production code changed after the full run, and the
  full suite was not repeated after those test-only expectation updates.
- Code map regenerated; project structure and diff whitespace checks passed.
  The structure check retains its existing Japanese protocol-parity notice.

Validation logs: `/tmp/sonder-body-default-final-full.log`,
`/tmp/sonder-body-default-final-contracts.log`, and
`/tmp/sonder-body-default-final-structure.log`. Baseline comparison:
`/tmp/sonder-prompt-clarity-correct-runtime-full.log`.
