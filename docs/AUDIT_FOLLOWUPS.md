# Audit follow-ups — deferred & partial fixes

Backlog from the `demo/enterprise_d_v2/` 40-turn audit (see that dir's
`findings.md` for the full evidence). alpha3.1 shipped the crux (W1 drive-rupture
floor) plus W2/W5/W7/W9/W11 and the narrator pronoun *data*; the items below were
deferred to keep that release surgical, or shipped **partial** (a prompt rule that
reduces but does not eliminate the tic). Each entry is written to be resumable cold:
symptom, root cause with `file:line`, concrete fix, and a test hint.

Ordering ≈ leverage. Prefer a focused test-first change per item; run `make check`.

**Shipped since:** P1 (pronoun fidelity). Open: P2–P7.

---

## P1 — Pronoun mismatch correction-retry  *(W6, SHIPPED)*
**Shipped.** Three layers, all tested in `tests/test_pronoun_fidelity.py`:

1. **Deterministic narrator floor.** `_check_pronoun_fidelity`
   (`agents/common.py`, called from `_check_narrator_fidelity`) flags a clause that
   OPENS with exactly one known cast name and then uses a pronoun from a different
   paradigm. Its warning prefix (`"Pronoun mismatch for"`) is in
   `_ENFORCEABLE_PREFIXES` (`agents/narration.py`), so it drives the existing
   correction-retry. Deliberately narrow — a false positive costs a full narrator
   rewrite — so it stays silent on: a second name in the clause, a pronoun in a later
   clause, quoted dialogue, plural "they", neopronoun/mixed sets, a name two cast
   members share, and names that are ordinary English words.
2. **Character agents.** `_known_pronouns` (`agents/character.py`) adds a
   `known_pronouns` map to the payload, gated on the character's own
   relationship/mind-model key set (already frame-filtered by recognition) — so a
   speaker gets the pronouns of people they KNOW and nothing about a stranger.
   Prompt rule: PRONOUNS OF OTHERS (`prompts.py`, character).
3. **Perception.** `_observed_pronouns` (`agents/perception.py`) adds `cast_pronouns`
   to all three perception payloads, **excluding any character under an active
   disguise** — canonical pronouns are part of the identity a disguise conceals, and
   supplying them would out the subject in an unaware observer's view. Prompt rule:
   PRONOUNS (`prompts.py`, perception).

**Known limit.** The narrator check scores same-clause pronouns only, so a
cross-sentence flip ("Vorne stepped back. She said nothing.") is not caught — the
referent of a bare leading pronoun is genuinely ambiguous in prose and enforcing it
would misfire on any nearby unnamed person. The prompt rule still covers that case.

## P2 — Ambient repetition, deterministic  *(W7, partial)*
**State.** alpha3.1 added an AMBIENT RESTRAINT prompt rule (`prompts.py`). "The bridge
hums" still recurred (confirmation turns 1 & 4) — reworded variants slip the
exact-word-run diff (`_already_established_phrases`).
**Fix.** Extend the recent-cue dedupe to ambient set-dressing: maintain a small
per-chat ledger of recently-used ambient sensation lemmas (hum/thrum, klaxon, flicker,
door-open) and fuzzy-match (stem/lemma, not exact word-run) against the draft; drop or
warn on a re-mention that isn't flagged as changed. Sits alongside
`already_established_phrases` in `agents/narration.py` / `agents/common.py`.
**Test.** "The bridge hums." established in recent prose; a new draft "the ambient hum
of the bridge" is caught despite the reworded surface.

## P3 — Dialogue dedupe, source-count-capped  *(W4, deferred deterministic half)*
**State.** alpha3.1 added a prompt rule (render each declared line once). The
deterministic `_dedupe_view_sentences` (`agents/common.py:1410`) deliberately EXEMPTS
quoted sentences (an intentional-repeat is legitimate — `tests/test_view_dedupe.py::
test_quoted_dialogue_is_never_dropped`), so a stuttered quote in differently-worded
attributions still passes.
**Fix.** New function `_cap_repeated_quotes(prose, source_quote_bodies)` applied in the
narrator finalize path (`agents/narration.py`, alongside `_dedupe_view_sentences`): cap
each quote body's occurrences in the prose at its occurrence count in the authoritative
source (the view + declared sequence). Artifact (prose 3× / source 1×) → drop extras,
keep first; intentional (source 2×) → both survive. Do NOT modify `_dedupe_view_sentences`
(keeps the existing test valid). Get source quote bodies from the same extraction
`_check_narrator_fidelity` already uses.
**Test.** New test file; assert a line surfaced once in source but 3× in prose collapses
to 1, and a line genuinely twice in source survives twice.

## P4 — `established_facts` continuity ledger  *(W3, deferred)*
**Symptom.** Second-act amnesia: a character contradicts a fact the whole room
established (Geordi "I can't translate it" 9 turns after the log was translated; Troi
relief→fear across adjacent turns).
**Fix.** A world-KV `established_facts` ledger. Emit from `director_resolve` (new
optional `established_facts` list op, like `obligations`), persist in `commit.py`
(dedup + cap, mirror `commit_obligations` at `commit.py:2550`), and inject the recent N
into every co-present character payload (`agents/character.py:~206`, alongside
`world_knowledge`) with a prompt rule: "settled on-page facts may be disputed, never
forgotten/contradicted." Note the existing `world_facts` path (`commit.py:2265`) feeds
lore, not character payloads — this is a separate, always-included ledger.
**Test.** Establish a fact at turn N; assert it appears in a later turn's character
payload and the prompt carries the no-contradict rule.

## P5 — Route player-authored NPC acts through the character reaction  *(W2/W9, deferred deterministic half)*
**State.** alpha3.1 added director-prompt rules (NPC acts belong to the NPC; being
acted upon is not passive) — the resolve now *renders* the reaction. Not yet routed
through the actual `reaction_loop`, so the NPC gets no genuine agent-generated
interiority/choice for the beat.
**Root cause.** `_requires_reaction_phase` (`agents/common.py:307`) gates a reaction on
`commitment == "contestable"`; a player physical act on an NPC is `asserted` (player
authority), so the NPC never enters the reaction loop. And a player-*authored* NPC
volitional act (t33 lunge, t36 badge) is executed as an objective event with no
character-agent call.
**Fix.** (a) In `director_interpret`, when a player action targets a present, volitional
sheeted character with a conflict verb, add that character to the beat's reactors even
when the player's act is `asserted` — the reaction is the NPC's *response*, not a contest
over whether the player's act succeeded. (b) When the player declares a volitional act
*by* an NPC, hand it to that NPC's character agent to adopt (supply interiority/voice) or
refuse. Both touch the delicate director/reaction seam — go test-first, small.
**Test.** A player "grab Vorne" beat produces a reaction step for Vorne; a player-authored
"Vorne lunges" beat calls Vorne's character agent.

## P6 — Room-boundary scene-truth  *(W10, deferred)*
**Symptom.** t31 closes the observation-lounge door; t32 reopens it silently; t33 has
bridge characters (Geordi, Data) speaking *into* the lounge and Picard effectively
inside it. Info-integrity failure in an engine whose premise is the information barrier.
**Root cause.** Not the perception *rules* (they already gate same-room / closed-door /
wall correctly — `prompts.py` perception, ~lines 346–348). It is scene *state*: door
state and positions drift (a door silently reopens; a character's room isn't updated),
so perception is fed a wrong co-present set. Investigate the movement/transit + door-state
commit path (`spatial_frames.py`, `commit.py` scene writers) and the perceiver co-present
computation in `agents/perception.py`.
**Fix.** Build the perceiver's co-present set strictly from `world.scene` room membership
+ open-door adjacency; ensure a door's closed state persists across turns unless an action
changes it; ensure a character led into a room has their position updated. Add a hard
invariant check.
**Test.** Close a door at turn N; at N+1 assert the door is still closed and a character in
the adjacent room is not in the lounge occupant's co-present set.

## P7 — Promotion-turn identity binding  *(W8, deferred, low severity/cosmetic)*
**Symptom.** On the turn a background presence promotes to cast, the player's view can
render it "the unfamiliar person" for one turn (enterprise_d_v2 t11, Data).
**Root cause.** Autonomous promotion runs at commit (AFTER that turn's perception), and
the promoted character's canonical name (e.g. "Lt. Commander Data") isn't yet in the
observer's `known` set during that turn's perception — plus a name-variant mismatch
(seeded "Data" vs promoted "Lt. Commander Data"). Perception scrubber anonymizes the
unrecognized name.
**Fix.** Either pre-seed recognition when a background presence the player has addressed
by name is first tracked, or have the perception name-match fall back to alias/variant
matching (a name containing an already-known name). `promote_background_character`
(`commit.py:1923`) seeds recognition — extend it to register all name variants/aliases.
**Test.** Promote a presence the player addressed by name; assert the observer's view of
it that turn is not anonymized to "the unfamiliar person".
