I've read the house rules (AGENTS.md § Narration routing row, CLAUDE.md), the live payload assembly in `agents/narration.py` (`narrator`, lines ~1158–1420), the helpers (`_past_narration_block`, `_render_observed_events`, `_sensory_channels_manifest`, `_position_delta_payload`, `_visible_portal_states`, `spatial_digest`), the enforcement floor (`agents/common.py` `_check_narrator_fidelity`, `_check_action_direction`, the `_ENFORCEABLE_PREFIXES` list in `language_packs/en/cards/linguistics.json`), the composer seam (`composer.observations_from_render`, `_composer_finish_observer` and `_composer_tripwires` in `agents/perception.py`), the 30.3k narrator sheet (`language_packs/en/cards/system_prompts.json` → `prompts.narrator`), and the whole of `tools/narrator_sheet_bench.py`. Judgement below.

First, three corrections to the framing, because they change the proposal:

**A. The live code has already shipped the winning arm.** `agents/narration.py` today builds `current_events` from perception's observations plus the player's reconciled acts (`_render_observed_events`), carries `current_narration` as its own section, ends `past_narration` before this turn's input, and includes a field the briefing omits: **`player_declared`** — the Director-interpreted sequence with content stripped (targets, volume, visibility, `private_thought`). So the question is not "adopt split_perception_acts" but "what next, from that baseline." Corollary: `tools/narrator_sheet_bench.py`'s `payload_for` still builds the *retired* shape (tail-in-past, no `current_narration`, no `player_declared`, `current_events` from `event_order`). **Sync the bench baseline to the shipped payload before running any new arm**, or every comparison is against a control the engine no longer sends.

**B. "present_scene is redundant" is true but the safe direction of the merge is the opposite of the obvious one.** `observations_from_render` projects from `rendered` — and `_composer_finish_observer` (agents/perception.py:3061–3065) projects it **before `_composer_tripwires` repairs the view**. The tripwires REPAIR: identity substitution (descriptor for an unearned name) and quote-safe self-narration drops. So the observations can carry a name the final view scrubbed, and `_render_observed_events` applies **no containment check** against the final view — unlike `_sensory_channels_manifest`, which byte-gates every `this_beat` span for exactly this reason (its docstring says so). Today that is a live re-entry path for a repaired leak *even with* present_scene in the payload; drop present_scene without fixing it and current_events becomes the sole, unguarded carrier. Your 102/104 byte-identical measurement is consistent with the 2 divergents being tripwire repairs — worth confirming, because those two beats are the whole risk.

**C. "already_established_phrases came back empty 12/12" does not mean the field is dead — it means its firing condition moved.** `render_view(mode='player', prev_standing=...)` suppresses unchanged standing state, so on ordinary beats the view has nothing to overlap with recent prose. But there is a full-render path (room change / re-entry), and on those beats the view *does* re-describe and the overlap list is exactly what stops re-cataloguing. The right change is absent-when-empty emission plus fixing the sheet's now-false "perception is stateless" claim (which also lives in `_already_established_phrases`' own docstring, agents/common.py:5432) — not deletion, until an arm on re-entry beats says deletion is free.

---

## 1. The proposed payload, field by field, in order

The organizing principle, stated once because every call below derives from it: **every string an enforceable check will demand must have been in the payload, and every payload field should either (a) back a deterministic check, (b) carry information nothing else carries, or (c) be authored config.** A field that is a second copy of another field is not free even when small — the payload's two measured drift defects (the "meals and a bed" paraphrase from the third quote copy; the pre-repair observations) were both second copies.

**Section A — voice and authority (~400–900 chars, stable across a story):**

| # | Field | Call | Why | Est. |
|---|---|---|---|---|
| 1 | `narration_person` | keep | verified by `_check_narration_person_match`; the model must be told what the detector will hold it to | 25 |
| 2 | `player_name` | keep, pending the `no_player_name` arm | in first/second person its only *narrating* use is prohibition, but it also disambiguates NPC lines that address the player by name in `past_narration`; corpus violation rate (4/2,369) says it is not causing harm; ~30 chars buys the disambiguation | 30 |
| 3 | `player_pronouns` | keep | load-bearing in third person; inert but tiny otherwise | 60 |
| 4 | `cast_pronouns` | keep | backs the enforceable pronoun-mismatch check and the single-token proper-noun check's pronoun tolerance — one record, two readers, the pattern this codebase treats as correct | 150–400 |
| 5 | `player_awareness` | keep | the gate that empties the world fields is announced to the model; renders the honest fade-out | 25 |
| 6 | `private_voice_setting` | keep, absent-when-empty | authored config; nothing else carries it | 0–100 |
| 7 | `scene_opening` | keep | switches the whole reading mode | 20 |
| 8 | `authored_body_parts` | keep, absent-when-empty (as now) | the measured six-fox-tails leak class; it is the *whole truth* claim ("a body not listed has none"), which only works as an explicit list | 0–400 |
| 9 | `player_declared` | keep | sole carrier of targeting/volume/visibility/`private_thought`; the NO ORIGINATED PLAYER CONDUCT rule needs a record to be checked against by the model itself | 150–400 |

**Section B — craft constraints (~50–2,500 chars):**

| # | Field | Call | Why | Est. |
|---|---|---|---|---|
| 10 | `exemplars` | keep, absent-when-empty | authored config; unmeasured, but cutting a user-authored surface is not the engine's call | 0–2,000 |
| 11 | `overused_phrases` | keep | computed ban list feeding the largest residual warning class (content reuse, 298); the deterministic diff is the only thing that can see cross-turn tics | 0–300 |
| 12 | `already_established_phrases` | keep, **emit only when non-empty**, and rewrite the sheet block per correction C | fires only on full-render beats now; empty-field emission on 12/12 ordinary beats is payload noise arguing for a rule with no referent | 0–400 |

**Section C — standing world facts (~600–1,800 chars, gated on awareness as now):**

| # | Field | Call | Why | Est. |
|---|---|---|---|---|
| 13 | `spatial_frame` | keep, flagged unmeasured | the *only* carrier of the egocentric direction license — the enforceable direction check (`_check_action_direction`) reads event_order *verbs*, not this field, so nothing deterministic backs it; but it is firewall-shaped (it subtracts the one-way-window edge, chat 78 t3) and without it the model has no licensed source for "behind you" at all. Candidate for a drop arm, prior is keep | 200–600 |
| 14 | `co_present_positions` | keep | backs enforceable wrong-room; perception-gated (`_player_sees_character`) | 100–400 |
| 15 | `portal_states` | keep | backs enforceable portal contradiction; literally the same object goes to model and check | 50–200 |
| 16 | `sensory_channels` | keep `status`/`why`/`standing`; **drop `this_beat` iff the `channel_tags` arm passes** | statuses and standing are unique content (silent/degraded verdicts, standing touch, weather-by-channel); `this_beat` is the third copy of beat percepts. Moving the channel onto the current_events line ("3. [hearing] …") keeps the per-sense information at the point of use — the instructions-attached-to-data lever, measured to work three times | 250–900 |

**Section D — the packages, chronological, material last:**

| # | Field | Call | Why | Est. |
|---|---|---|---|---|
| 17 | `past_narration` | keep, depth 12 | nothing shows length hurts; the block's value is continuity; run a depth-8 arm for cost only, not by default | ~10,500 |
| 18 | `current_narration` | keep | half of the only clean-sweep arm; the sentence the prose continues from, unmissable by position | 200–800 |
| 19 | `present_scene` | **DROP — but only after B is fixed** (see §2) | 450–900 chars of byte-duplicate; two authorities on "what reached this mind" is the drift condition this repo names explicitly | −450–900 |
| 20 | `current_events` | keep: player reconciled acts first with the per-line "NOT yet on the page" markers, then **post-repair** observation texts, numbered; optionally channel-tagged | the measured levers (14→0 placeholders; 3→1 enforceable; 7/9 act coverage) all live in this field's line format | 500–1,200 |
| 21 | `variant_seed` | keep, last | reroll divergence; inert content | 15 |

Estimated total: **~12.3–13.2k chars** against 13.7k today. This is not a size play — the payoff is one authority per fact and the closure of the two second-copy hazards.

## 2. What I would drop, and the precondition

- **`present_scene`** — after, and only after, the projection fix: either project `observations_from_render` from the *repaired* view (re-render post-tripwire), or apply the identity repair to observation texts, or byte-gate `_render_observed_events` entries against the final view **with the repaired sentence substituted rather than dropped** (a bare containment gate would silently delete a repaired line, and a delivered line the model never saw becomes an enforceable dialogue-fidelity finding it cannot fix — a guaranteed wasted rewrite). Then add the standing guard: a deterministic build-time assertion that every quote `_check_narrator_fidelity` will demand is present in the serialized payload, falling back to including `present_scene` on the (measured ~2%) divergent beats and logging that it did. That is the class-level rule: *the floor may only score the model against material the payload carried.* Measurement 3 is the same rule violated in the other direction.
- **`sensory_channels.this_beat`** — conditional on the `channel_tags` arm.
- **Empty-field emission** for `already_established_phrases` (and audit the other always-emitted empties: `exemplars: []`, `private_voice_setting: ""` — absent-when-empty is already the house pattern via `authored_body_parts`).
- **In the sheet, not the payload:** the four-package framing becomes three; ESTABLISHED-DETAIL ECONOMY rewritten to the ledger reality (currently argues against a behaviour `composer_ledger.standing` removed); PROPER NOUN FIDELITY and DIALOGUE FIDELITY re-pointed from `present_scene` to `current_events`; named examples cut (measured free). Note `do_not_quote_verbatim` is already gone in live code.
- **Not dropped, deliberately:** `player_name` (arm first), `spatial_frame` (unmeasured ≠ useless; it is the only direction license), `past_narration` depth.

## 3. What is missing — the floor's blind spots

1. **Player-act coverage as a harness metric and a warning-only check.** The 1/9-with-12/12-clean result is the proof: a mind's own conduct is invisible to every check, so payload regressions here are *structurally unmeasurable* today. `_check_action_direction` only sees an act that names a vertical direction. Add a content-word coverage warning over `event_order` acts with `actor == player` (the facts already sit in `_fidelity_facts`), measure its false-positive rate over the 2,369 stored variants before letting it near `_ENFORCEABLE_PREFIXES`, and surface it in the bench's summary line regardless — the bench needs the metric even if production never warns.
2. **The post-repair observation projection** (§2) — a firewall item, not a craft item; it exists whether or not present_scene is dropped.
3. **A `spatial_frame` efficacy metric**: deterministic, harness-side — when prose uses an egocentric direction word, does it agree with the bucket? That makes the 2,824-char sheet block and the field itself measurable for the first time.
4. **NPC interiority tripwire (warning-only, low priority).** `_check_player_interiority_prose` covers only the player; nothing sees "she decides/realizes/hopes" about a body whose interior the player has no channel to. Perception filters input; this is invented output, the exact asymmetry your framing names. Class statement: asserted interiority of any mind other than the narratee's. Measure corpus FP first — free indirect style will trip a naive verb list, so it may not survive measurement, and per the house rule it must not become enforceable until it does.
5. **Language-pack coverage for the marker strings**: the per-line markers in `_render_observed_events` are English f-string literals in code. They are the measured highest-leverage instruction in the payload, and a Japanese story currently gets them in English. Any channel-tag addition should go through the pack's canonical tokens, and the existing markers should follow.

## 4. Ordering rationale

Keep the shipped order and its comment ("ORDER IS THE MESSAGE"): stable → volatile, constraints before material, the writing material last so generation begins immediately after `current_events`. The user message has no cached prefix, so this costs nothing. One candidate refinement — moving `player_declared` from Section A to just before `current_narration`, grouping all beat-scoped material — is defensible but unmeasured; the previous reordering was justified by an arm, and this one should be too or not done. Do not rename anything: a rename costs the Japanese pack and `tools/project_check.py`'s canonical-token check; a removal costs nothing.

## 5. Ranked risks, with the arms for the top three

1. **Dropping present_scene delivers a repaired leak or an unrenderable obligation** (the §2 pair). Arms, in order: first an **offline corpus audit, zero model calls** — for every stored turn with a view and observations, diff concatenated observation texts against the final view; count divergent beats and classify each (tripwire repair vs merge cap vs other). That settles whether 2/104 generalizes and what the guard must substitute. Then the live arm `drop_view` (= shipped payload minus `present_scene`, observations post-repair), n≥24 across ≥8 chats, scored on enforceable/turn, dialogue-fidelity findings specifically, and the new act-coverage metric.
2. **Channel tags on event lines confuse the model or leak into prose.** Arm `channel_tags`: shipped payload, `this_beat` removed from the manifest, `[channel]` token per observation line; add a deterministic bracket-leak grep to `score()`; select beats that *have* a silent or degraded channel (dark rooms, enclosure) or the arm cannot exercise what the manifest is for. Compare against shipped, n≥24.
3. **already_established_phrases removal or absent-when-empty hurting re-entry beats.** Arm `no_established_reentry`: beat selector restricted to turns whose player room differs from the prior beat's (the full-render class); compare content-reuse warnings and craft tells with the field present vs absent. If present wins on those beats and they are the only beats it is ever non-empty, absent-when-empty is exactly right.

Lower: (4) sheet rewrite (three-package framing) regressing something a cut block backed — rerun the measurement-5 style sheet arm after the rewrite; (5) model dependence — your own memory notes say guard efficacy varies with the model, and the paragraph contract is measured fragile, so repeat the top two arms once on a second configured model before shipping; (6) `no_player_name` in first/second person — cheap to run, tiny expected effect either way.

## 6. What I am uncertain about

- **n=12 is thin for per-turn enforceable rates.** The effects you measured (3→1, 14→0) are large enough to trust directionally; "roughly neutral" results at this n are not — 11/12 vs 12/12 is one beat.
- **The cause of the 2/104 divergence is my inference** (tripwire repairs), not a measurement. The offline audit settles it and should run before anything else.
- **Whether `spatial_frame` and `exemplars` earn their place at all** — neither has ever been measured, and no check can see either. I keep both on priors (firewall-shaped subtraction; authored config), not evidence.
- **Depth 12 for `past_narration`** — chosen, as far as I can see, by observation that it bounds well, not by comparison. It is 80% of the payload and the one field where an arm could move real cost; I would still only cut it on a measured no-regression, because CURRENT-BEAT FIDELITY and the continuity value both lean on it.
- **Whether the harness's reconstruction drift matters**: `payload_for` and its `beat_events`/`past_narration` helpers rebuild a retired payload shape, and `world_fields` rebuilds standing facts from the *current* stored scene rather than the scene as of that turn — replayed old beats are scored against today's world. Both are acceptable for A/B deltas (both arms share the bias) but not for absolute rates; the baseline sync in correction A is the part that must happen first.