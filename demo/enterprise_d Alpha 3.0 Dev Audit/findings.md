# Enterprise-D: The Kelvan Array — Audit Findings & Fix Plan

A 30-turn Sonder-Engine episode (deepseek-v4; director/character on pro-cheaper),
run to stress the **background-character promotion** path, the new **drive-rupture**
system, and overall **narrative quality** — with a harsh Fable narrative critique
(grade: **D+**). 30 turns, **0 pipeline errors**. This is the weakness ledger and
the code/prompt fixes each points to.

## Feature coverage
FIRED 18 / MISS 17 (of 35 checks). The MISSes are mostly features this bridge-bound
episode never called for (concealed speech, dice, attire, destruction, co-player).
The **meaningful** misses are the two the test targeted: **PROMOTION** and **DRIVE
SHIFT** — both open/qualify but never complete. Full table in `coverage.md`.

---

## Part 1 — Systemic engine weaknesses (highest value first)

### W1. The Director defers plot forever — pending obligations never discharge  *(CRITICAL)*
**Symptom.** Geordi's report is demanded 7× (turns 9,10,11,12,14,16,24) and Geordi
speaks **zero words all episode**. The core log is demanded 7× and **never read** —
the episode *ends* with it unread at "87 percent," so its content (the makers died
powering the Array) exists only as the player's unbacked claim. Data "will begin the
analysis" (24) and no analysis is ever shown. Picard's whole function decays to
re-requesting a report the engine never generates.
**Root cause.** `director_resolve` treats "stall / ask for more evidence" as the
safe move and has no ledger of open obligations, so a promised/ demanded beat can be
re-deferred indefinitely. Nothing forces resolution.
**Fix.** An **obligation ledger** (world KV `pending_obligations: [{who, what, opened_turn, kind}]`)
written when the Director registers a demand/promise/announced action, surfaced back
into the `director_resolve` payload, with a hard rule: *an obligation older than ~2
turns must be discharged this beat (delivered or explicitly, on-page, refused) — it
may not be re-deferred.* Mirror the existing `standing_intentions`/promise-ledger
machinery. This one fix resolves W1, most of W2, and the anticlimax (W-narr).

### W2. Player asserts the entire plot; the engine never corroborates or contradicts  *(CRITICAL)*
**Symptom.** Every plot fact is the player's assertion, merely tolerated: the deaths
on deck 12 (never confirmed by Crusher or anyone), the log's contents, "Vorne's
changed his mind" (23 — contradicted by Vorne in 26 and 29), the Array's death. The
Director leaves player claims in "assertion limbo."
**Root cause.** The interpret/resolve seams capture player-declared *world objects*
(rooms/items) but do not adjudicate player-declared *facts/outcomes* about NPCs and
offscreen events — they neither confirm with on-page evidence nor contradict.
**Fix.** Extend `director_resolve` to classify a player-asserted fact as
`confirmed | contested | false`, and require the resolved_event to *land* it: a
confirmed death gets Crusher's on-page line; a contested claim gets a challenge; a
false one is corrected. Never pass an unadjudicated plot claim through.

### W3. Addressed background characters do not answer — a foreground character intercepts  *(HIGH)*
**Symptom.** Troi is addressed twice (7, 25) and never speaks; Worf and Crusher are
mute; every crew answer is intercepted by Vorne or Picard. Only Riker (once) and Data
(technobabble) exist. The crew are "furniture with famous names."
**Root cause.** `pick_background_reactor` fires ≤1 background presence per beat and is
not forced to select an **addressed** presence; a foreground cast member's
interaction-loop line satisfies the beat first, so the addressed background NPC is
skipped. Combined with W4, addressed crew never get depth *or* a voice.
**Fix.** When `addressed_to` names a background presence, force that presence to be a
reactor this beat (bypass the ≤1 cap / priority it), so a directly-addressed NPC
always answers with its own line.

### W4. Background→cast promotion never fires autonomously  *(HIGH)*
**Symptom.** Data becomes `promotable` at turn 4 and stays promotable **26 turns** —
addressed 20+ times, central to the drama — and is **never promoted**. Deserving crew
stay shallow (no memory, psychology, interiority, or drive) the whole episode.
**Root cause.** Promotion is **UI-only**: the sole callers of
`promotable_background_presences` are the HTTP routes `draft_promotion` /
`confirm_promotion` (`app.py:1721,1734`). There is **no autonomous/commit-side path**,
so headless or hands-off play never promotes anyone.
**Fix.** Factor the confirm-route body into `promote_background_character(cid, name)`
and call it from `commit` (in `detect_and_reconcile` or a commit-side sweep) for any
presence crossing an **auto-threshold** (promotable + `dialogue_turns >= 3` +
addressed/present this beat), gated behind a `setting("auto_promote", default on)` so
operators who want manual control keep it. Reuses `draft_promoted_character` + the
existing scene/known/memory seeding.

### W5. Chain of command / social authority is unmodeled  *(MEDIUM)*
**Symptom.** Vale, a *visiting ethics observer*, orders "Mister Worf — shields" and
Worf complies with no glance at Picard (12); Vale issues engineering orders and Data
obeys (24). Picard's real first line — *nobody gives orders on my bridge* — never comes.
Trek verisimilitude collapses.
**Root cause.** `director_resolve` resolves an order purely by physical plausibility;
it has no notion of rank/authority/standing, so any speaker's command is obeyed.
**Fix.** Add a light **authority appraisal** to resolve: an order from someone without
standing over the actor is *contestable*, not auto-executed — the actor (or their
commander) may refuse/redirect. Cheap version: a `social_standing` hint per character
+ a resolve rule that a command crossing a standing gap is contested.

---

## Part 2 — Interior depth & drive rupture

### W6. Drive rupture opens but never *lands* — logged, never dramatized  *(HIGH)*
**Symptom.** Vorne's `drive-strain` hits 0.8 organically and the rupture window opens
twice (turns 15–18, 21–24), but he emits `drive_shift: null` every time and plays the
same controlled-lawyer denial ("a requisition is not a verdict"). No cracked voice, no
collapse — the rupture is a telemetry number that never reaches the page, and the
player's asserted "he changed his mind" (23) is contradicted by the character (26, 29).
**Root cause (two).** (a) The in-window `RUPTURE` prompt block is a terse "you MAY"
appended after a long prompt; the model under-emits `drive_shift` and, in character,
resists. (b) Even *without* a formal shift, the extreme strain + undercurrent aren't
being forced to the surface as visible crisis behavior.
**Fix.** (i) Strengthen the in-window prompt: a worked example + firmer framing ("this
event has *already* changed you; denial is a phase, not a stable end — show the crack
now, and if your core is remade, say so"). (ii) Make the window **re-openable** and
longer while strain stays ≥ rupture-min. (iii) Feed a `crisis` flag to the character
when strain ≥ ~0.8 so the manifest/tells escalate to visible breaking even before a
shift. (iv) minor: the appraisal `serves:"intention:<text>"` prefix doesn't match the
payload's intention **ids**, so it scores at default priority — normalize `intention:*`
to the matching id (or instruct the model to use the id).

### W7. Repetitive tells / gestures — no anti-repetition on the manifest  *(MEDIUM)*
**Symptom.** Vorne's entire interiority across 30 turns is "jaw tight" (11×) and "two
trembling hands" (nearly every turn); "the bridge hums" appears in 14 turns; "a muscle
jumps beneath the skin" recurs **verbatim in consecutive turns** (18→19).
**Root cause.** The `manifest.tells` and narration have no recent-cue dedupe; the model
reaches for the same physical vocabulary every beat.
**Fix.** A per-character **recent-tell ledger** (last ~6 cues) fed into the character
payload with a "do not reuse a recent cue" rule, plus extend the narrator craft screen
with a banned-recent-gesture check (like the existing anti-repetition on prose).

---

## Part 3 — Narration integrity (mechanical bugs)

### W8. Vorne's pronouns flip six times (her/she ↔ his/he)  *(HIGH, mechanical)*
Turns 2,7,12,13,14,18,19 alternate Vorne's gender. **Root cause:** the character's
pronouns aren't pinned or enforced. **Fix:** carry explicit `pronouns` on the character
sheet, put them in the perception/narrator payload, and add a narrator rule to use a
character's given pronouns consistently (a mismatch is a correction-retry, like the
dialogue-fidelity floor).

### W9. Reversed chronology — the player's action is rendered *after* its reactions  *(MEDIUM)*
Turn 4 ends "The words come out flat, certain" after Data has already replied; same in
6 and 22. **Root cause:** the narrator orders the player's own declared action behind
the NPC reactions. **Fix:** a narrator ordering rule — the player's declared
action/speech is rendered *first* (it causes the beat); reactions follow.

### W10. POV collapse into an NPC (turn 29) and third-person naming of the player (18)  *(MEDIUM)*
"*I* turn my head slowly toward Vale" (Vorne rendered as the first-person "I" while the
player is Vale); "her focus narrows on **Vale's face**" names the first-person narrator
in third person. **Root cause:** narrator/perception don't hold the person mapping (the
player is "I"; everyone else is named). **Fix:** extend the existing `narration_person`
discipline — only the player character is "I"; a non-player action rendered in first
person is a correction-retry.

### W11. Fabricated retro-continuity — an invented callback quote (turn 27)  *(HIGH, integrity)*
Picard "quotes" a line — "The line will hold, Commander…" — that appears in **no prior
turn**. In an engine whose whole premise is information integrity, the narrator
inventing a past quotation is a serious failure. **Fix:** extend the narrator's proper-
noun/dialogue-fidelity rules — a quoted "callback" must match a real prior line; do not
fabricate past dialogue.

### W12. Duplicated beats within a turn (turn 7 renders the same sentence twice)  *(LOW)*
"Picard turns his head slightly toward Troi" and "a flicker of anxiety" each appear
twice in one turn. **Fix:** a within-view dedupe pass in perception/narration.

---

## Part 4 — Fable's verdict (harsh critic)
> **D+.** "A thirty-turn holding pattern wearing a Starfleet uniform… the engine has
> built a world where nothing it controls is ever allowed to happen." Best moments:
> Riker T6 (the one crew member with a voice), Vorne T21 ("I won't let you define what
> it means before I read it myself"), Vorne T29 ("an ending without understanding is
> not peace — it is an amputation").
> **Single biggest improvement:** *"Give the engine the authority — and the obligation
> — to resolve what it opens."* Force pending obligations to discharge; make the
> Director confirm-or-contradict player-asserted facts; dramatize a crossed rupture
> threshold in the character's own output instead of only logging it.

## Part 5 — Prioritized fix plan
1. **W1 obligation ledger** (Director) — the single highest-leverage fix; kills the
   deferral loop and the anticlimax.
2. **W2 player-fact adjudication** (Director) — no unbacked plot claims.
3. **W3 addressed-presence forced reactor** + **W4 autonomous promotion** — the
   background-character system's two real gaps; together they let the crew both answer
   and deepen.
4. **W6 drive-rupture dramatization** — strengthen in-window prompt, re-openable
   window, crisis flag; fix the `serves:` prefix.
5. **W8/W9/W10/W11 narration integrity** — pronoun pinning, action-first ordering, POV
   discipline, anti-fabrication — mostly narrator-prompt + correction-retry, cheap.
6. **W7 tell anti-repetition**, **W5 authority**, **W12 within-turn dedupe** — polish.

Cheapest high-impact first pass (prompt-only, no architecture): W6(i), W8, W9, W10,
W11 — all narrator/character prompt rules + correction-retries. The Director-side W1/W2
and the promotion W3/W4 are the structural work that most changes the fiction.
