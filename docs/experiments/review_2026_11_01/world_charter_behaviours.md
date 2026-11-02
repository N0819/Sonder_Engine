# Audit — world/ charter behaviour modules (28 files, 11,250 lines)

Auditor scope: `world/charter_{move,place,observe,needs,promote,news,log,chatter,feel,creature,economy,enrol,surgery,ops,crowd,surface,talk,intervene,space,mark,commitment,decide,harm,mind,plan,temper,politics,drift}.py`.
Method: every file read in full with `cat -n`; a repo-wide reference count for every top-level symbol (all `.py/.js/.json/.txt/.md/.html` outside `.venv`), read-only `.venv/bin/python` snippets (pasted below with their output), no test runs needed (every claim reproduced by a snippet or a traced call chain). Registers grepped before each finding.

## Scope read

Read IN FULL, every line:

| file | lines | file | lines |
|---|---|---|---|
| charter_move.py | 1-690 | charter_crowd.py | 1-368 |
| charter_place.py | 1-671 | charter_surface.py | 1-364 |
| charter_observe.py | 1-664 | charter_talk.py | 1-351 |
| charter_needs.py | 1-615 | charter_intervene.py | 1-344 |
| charter_promote.py | 1-612 | charter_space.py | 1-337 |
| charter_news.py | 1-565 | charter_mark.py | 1-302 |
| charter_log.py | 1-521 | charter_commitment.py | 1-292 |
| charter_chatter.py | 1-487 | charter_decide.py | 1-279 |
| charter_feel.py | 1-469 | charter_harm.py | 1-264 |
| charter_creature.py | 1-464 | charter_mind.py | 1-262 |
| charter_economy.py | 1-444 | charter_plan.py | 1-234 |
| charter_enrol.py | 1-431 | charter_temper.py | 1-167 |
| charter_surgery.py | 1-402 | charter_politics.py | 1-161 |
| charter_ops.py | 1-384 | charter_drift.py | 1-106 |

Read in PART, only to trace callers/consumers (not audited): `world/charter_runtime.py` (270-295, 2646-2700, 2846-2890, 2915-2945, 3120-3150, 3983-4003, 4560-4720, 4795-4900, 5036-5200, 5201-5228, 5298-5390, 5740-5860), `world/charter_run.py` (575-630, 680-760, 930-1030, 1240-1290, 1620-1640), `world/charter_model.py` (48-70, 112-145, 240-300, 395-410, 485-492, 539, 640-660, 682-690, 860-900, 952-971), `world/charter_social.py` (271-345, 420-500, 810-830), `world/charter_history.py` (214-260, 349-390, 745-830), `world/charter_generate.py` (145-156, 1295-1370), `persist/commit_scene_state.py` (2040-2100, 3009-3066), `persist/commit_background.py` (3232-3295, 4929-5300), `agents/common.py` (2950-3135, 6642-6700), `agents/perception.py` (5250-5300, 6310-6345), `agents/background.py` (3120-3175), `agents/composer.py` (4515-4555), `mind/psychology_runtime.py` (228-300), `world/spatial_barriers.py` (226-262, 415-438), `world/region_events.py` (375-392), relevant AGENTS.md (30-330), registers by grep.

## Findings

Question map (the assignment's eight questions -> findings): (1) near-duplicate helpers: F9, F10, F12, F13, F23 + Structure notes "Near-duplicates"; (2) place stored twice / writers updating one: F13, F14, F15; (3) promotion routes: F10, F17 + "Q3 observations" at the end of Findings; (4) what an offscreen body comes to know: F1, F2, F3, F4, F5, F6, F11; (5) charter_log growth/reads: no persistent growth (trace is opt-in, unstored); its cost is E1; one mislabel F26(d); (6) harm/surgery conditions with no end: F8 (the one real "no end", via the intervention cap), F11; charter `condition` itself is NOT the UNBUILT_WORLD 1.84 class (see Already registered); (7) English: F23, F24, F20; (8) all-bodies passes: E1-E6.

---

### F1 — The institution's blame REGISTER count reaches every voiced background body's payload
**Severity:** LEAK. **Confidence:** CONFIRMED (snippet + traced to the model payload).

`world/charter_log.py:440` (inside `scene_ledger`, per presence):
```python
            "blamed": int(blame.get(key, 0)),
            "knows_it_is_blamed": sorted(heard_blame.get(key, ())),
```
`blame` is `politics.blame`, the register counter `attribute_blame` writes from the watch the charter BELIEVED it had arranged (`charter_politics.py:121-161`). The module's own rule says this may not reach a head: `charter_promote.py:29-33` ("the blame ledger, unless somebody said it aloud (`heard_blame` is the channel; a body blamed in the books and never told arrives innocent of it)"), `charter_feel.py:48-56`, `charter_mark.py` (`disgraced` excluded by allowlist). `scene_ledger`'s docstring (`charter_log.py:296-302`) says "The institution's register is absent". `presence_view`'s docstring (`charter_runtime.py:5039`) says "never its institution's register".

Path: `scene_ledger` -> `charter_runtime.presence_view` (5158) -> `_voiced_presence` keeps it (`out = dict(presence)`, 4847; only values are rendered) -> `agents/background.py:3134-3156` `shown_context` -> model payload. Scenario: a gate guard blamed twice in the books for a mill that failed while the roster wrongly had him posted, never accused aloud, is voiced with `"blamed": 2, "knows_it_is_blamed": []` and can say "they keep blaming me".

Verified:
```
c = normalize_charter({... "bodies": {"tam": {"place": "yard", "name": "Tam"}}})
c["politics"] = dict(c.get("politics") or {}, blame={"tam": 2})
scene_ledger(c, "yard")["presences"]["tam"]  ->  blamed: 2 | knows_it_is_blamed: []
```
Note `tests/test_charter_runtime.py:346` allowlists `"blamed"` in the presence key set, so the leak is pinned by a test.
**Fix:** drop `blamed` from the presence slice (the voice already has `knows_it_is_blamed`, which is the channel); keep the count in `place_state`/diagnostics only. **Test:** a presence whose body has `politics.blame` but no `heard_blame` carries no blame count; remove `"blamed"` from the allowlist test.

### F2 — The addressee's canonical name rides `public_evidence.target` into a witness's head and out through its voice
**Severity:** LEAK (a name never learned). **Confidence:** CONFIRMED to the presence slice; the voice-side relabel is traced (covers only figures present in the voicing beat).

`world/charter_observe.py:218-226`:
```python
    licensed = {
        field: copy.deepcopy(evidence[field])
        for field in (
            "kind", "actor", "target", "surface", "exact_quote",
            "speech_acts", "status", "salience")
        if field in evidence
    }
    if "actor" in licensed:
        licensed["actor"] = shown
```
The actor is relabeled to the witness's stranger label; `target` (the engine's canonical name of whoever the line was aimed at) is copied verbatim. `charter_log.scene_ledger` (348-349) copies `public_evidence` into `can_bring_up`; `charter_runtime._relabel` (4692-4707) replaces only strings equal to a figure key passed in THAT voicing call, so an addressee absent from the later beat keeps their real name in the voice payload. Scenario: the player says "The well is poisoned" to Hinami without naming her; the barmaid who overheard holds `target: "Hinami"`; voiced next day in the yard (Hinami absent) she is handed the name.

Verified:
```
claim = evidence_claim({"source_id":"s1","kind":"speech","actor":"Sarah Moon","target":"Hinami",
                        "exact_quote":"\"The well is poisoned.\""}, 7, 0.0, "taproom", label="the slight woman")
scene_ledger(...)["presences"]["tam"]["can_bring_up"][0]
-> about 'the slight woman' | public_evidence {'kind':'speech','actor':'the slight woman','target':'Hinami', ...}
```
Same class, lesser: `subject` (canonical actor key) is stored on the claim too (fine as a key, it is relabeled when present). `charter_mind.hear_claim` (160-169) strips `target` on retelling, so only firsthand witnesses carry it.
**Fix:** at `evidence_claim`, render `target` through the same `labels` map as the actor (or drop it: `speech_acts` already carries direction). **Test:** `evidence_claim` with a target not in `labels` stores no canonical target; `scene_ledger` slice of such a claim contains no registered name.

### F3 — A creature cannot be blind: `senses` has no sight, an authored `sight: false` is silently dropped, and every overt act is witnessed
**Severity:** LEAK (a fact through a channel the body does not have). **Confidence:** CONFIRMED (snippet).

`world/charter_creature.py:266-275` keeps only `range_rooms`, `hearing`, `scent`; an unknown `senses` key is neither kept nor refused (unlike `contest`, line 161, which refuses). `world/charter_observe.py:167-172` grades an `action` by sight with no sense check, while speech is gated (`141-142`). The comment at `charter_creature.py:257` quotes the very creature this fails for ("blind, deaf, indifferent to vibration and light").

Verified:
```
c = normalize_charter({"key":"stalker", "creature": {"senses": {"hearing": False, "scent": True, "sight": False}}, "bodies": {"it": {"place":"shaft"}}, ...})
normalized senses: {'range_rooms': 2, 'hearing': False, 'scent': True}
plan_public_evidence(c, [action 'draws a knife', speech 'run'], scene, 3)
acquired claims: [('it', 'figure_action')]     # speech refused, action witnessed
```
This is exactly the class fixed for hearing on chat 117 turn 63 (`charter_observe.py:111-118`), one sense over.
**Fix:** declare `sight` in the closed sense card (declared, not defaulted, like `hearing`), gate the action branch on it, and refuse unknown `senses` keys with a notice. **Test:** a creature with `sight: false` acquires no `figure_action`; `creature_warnings` reports an unknown sense key.

### F4 — Overheard chatter names a figure by its canonical key, a name the speaking townsfolk never learned
**Severity:** LEAK at source (the final-view identity scrub is the floor). **Confidence:** PLAUSIBLE.

`world/charter_chatter.py:481-482`:
```python
    if key in (figures or {}):
        return key
```
`subject_label` justifies naming ("the name was said aloud"), but a charter body's claim about a figure is a `figure_claim` keyed by canonical name whose only surface is the stranger label (`charter_observe.py:573-576`); nobody in the charter heard the name. `relabel_fragment` (perception `6327-6331`) relabels speaker and other only, not the subject, and `notable` (`agents/common.py:3067-3072`) makes acts about figures in the room the preferred fragment. The rendered view is protected by `agents/common._scrub_unknown_identities` ("runs LAST on every view"), but the raw `subject_label` also rides `Percept.data` (`agents/composer.py:4536-4538`).
**Fix:** return the speaker body's own surface label for a figure subject (its claim's `surface.label`), so the fragment carries what was said. **Test:** a chatter fragment about a figure the speaker knows only by label never contains the figure's key.

### F5 — Register blame lowers every co-watch head's per-head regard of the blamed body
**Severity:** LEAK (register fact into heads) / design question. **Confidence:** PLAUSIBLE (design tension; owner to rule).

`world/charter_politics.py:146-158` lowers `regard[other->blamed]` for every body on the watch and every body ever blamed, on a register attribution. Regard is per-head ("a->b how much a weighs what b says", 11-13) and surfaces as a head's own view: `scene_ledger` `knows_here[...].regard` (voiced), `charter_promote.remembered` "knows X and thinks less of them" (335-343), `acquainted` -> relationship warmth at promotion. The politics docstring says blame "shape[s] who is believed next" (25), which conflicts with promote/scene_ledger/presence_view docstrings that keep the register out of heads.
**Fix (if ruled a leak):** keep the regard cost institutional (a separate `register_regard` read only by the planner/report_up), or apply it only to heads that heard the accusation (`heard_blame`/`accusation` news). **Test:** a body with no channel to a blame event keeps its regard of the blamed.

### F6 — A promoted townsperson is "told" every non-berth room of the charter's graph, including secret and provisional rooms
**Severity:** LEAK (minor, documented limit). **Confidence:** PLAUSIBLE.

`world/charter_promote.py:490-511, 578-585`: `private_rooms` excludes only somebody else's berth; everything else becomes a `told` node with its `name`. The docstring states the limit ("a private interior nobody berths in -- a vault, a back office -- reads as public") but it is not in any register. A hidden passage or a planted secret chamber, and any `provisional` frontier stub the plan holds open, would be handed to the promoted mind as known geography.
**Fix:** exclude rooms the plan marks as concealed/provisional (and any room with `parent_entity`) from `told`; register the residual. **Test:** `inherited_place_graph` over a scene with a provisional stub and a concealed room yields neither as `told`.

### F7 — `heal_unbound_twins` rebinds its own spelling table to a scene ledger mid-loop
**Severity:** CRASH (swallowed: the whole lease step is skipped) / CORRUPTION (an arbitrary entity bound to a bogus charter body). **Confidence:** CONFIRMED (snippet).

`world/charter_place.py:426,437-438` build and read `table` (the spelling table); then `450-454`:
```python
            for channel in PLACEMENT_ROWS:
                table = scene.get(channel)
                if isinstance(table, dict):
                    table.pop(eid, None)
```
After the first pre-existing twin is released, `table` is `scene.get("poses")`. The next unbound entity either raises (`poses` missing: `f in None`) or is looked up in the poses ledger.

Verified (fixtures from `tests/test_a_charter_body_is_leased_to_the_scene.py`, stale twin ordered before a lamp):
```
A raised: TypeError argument of type 'NoneType' is not iterable
B: [..., {'entity_id': 'lamp', 'charter': 'u', 'body': 'p', 'name': 'a lamp', 'released_from': ''}]
B lamp now: {'name': 'a lamp', 'kind': 'person', 'charter_ref': {'charter': 'u', 'body': 'p'}}
```
The caller `persist/commit_scene_state.py:2059-2095` wraps it in `except Exception -> "charter lease not settled"`, so case A silently skips healing of later twins, every lease move and every release for the beat (the scene keeps a second positions row for released bodies); case B persists a lamp as a `person` with a `charter_ref` into the stored scene. Tests pass because the healed twin is always the last entity.
**Fix:** rename the inner variable (`ledger = scene.get(channel)`). **Test:** two-entity scene with the stale twin FIRST and an unrelated entity after it, with and without a `poses` dict: no exception, the lamp untouched.

### F8 — The intervention cap silently evicts a scheduled END: a called watch never stands down, a dial never reverts
**Severity:** CORRUPTION (a condition with no end). **Confidence:** CONFIRMED (snippet).

`world/charter_intervene.py:109-110`:
```python
    rows.sort(key=lambda row: (row["at_hours"], row["id"]))
    return rows[:INTERVENTION_CAP]
```
Every append re-normalizes (`charter_surgery.charter_shock` 268, `charter_run` `interventions + calls` ~1004, `apply_due` 332). At the cap, the row with the LATEST `at_hours` is dropped without a refusal or warning, and the latest rows are exactly the `:stand_down` (`296-300`) and `:revert` (`205-210`) rows other ops schedule. The `drift_dial` revert comment (195-199) documents the same "dormant for good" defect this reintroduces.

Verified:
```
after window: pending 64 stand_down present: True
after one more authored shock: pending 64 stand_down present: False | watch still standing: ['gate']
```
The `guard:<place>` upkeep stays first in `priority` and its posts keep pulling crew forever.
**Fix:** never evict a scheduled end (keep follow-up rows outside the cap), and refuse the NEW row with a notice when full; the cap number is the owner's. **Test:** fill to the cap, schedule a watch, append one more row: the stand-down survives (or the append is refused visibly).

### F9 — The teller of a claim is stored three ways in one field; formal reports file judgments under a display name
**Severity:** CORRUPTION (stances written where no reader looks; regard lookups miss). **Confidence:** CONFIRMED (snippet).

`heard_from` is a BODY KEY from ordinary talk (`charter_mind.hear` 96-97, `report_up` 297), a DISPLAY NAME from formal reports (`charter_talk.py:341-348`, `heard_from=source_name or subordinate`, pinned by `tests/test_charter_hierarchy.py` `== "Iven Marr"`), and FREE TEXT from authored plants (`charter_surgery.plant_claim` 178, 196). Readers assume the key: `charter_news.check_reports` (451-484) mints `report_confirmed/refuted` with `about=actor=teller`; `charter_social.update_judgments_from_minds` (441-444) weights by `regard_value(regard, holder, source)`, keyed by body key.

Verified:
```
heard_from on superior's copy: 'Ann Tull'
checks 2 [('report_refuted', 'Ann Tull')]
judgment subjects of reeve: ['Ann Tull']        # not 'clerk:0001'
```
This is the B7 class `charter_social._signals_in_claim` documents ("Keying a stance by the label files it against nobody"); the superior's regard for its subordinate is also ignored for formal reports (neutral weight).
**Fix:** store the subordinate's body key in `heard_from` and render the name at read time; for `plant_claim`, resolve `told_by` to a body key when it names one, else mark it external. Update the hierarchy test. **Test:** after `report_to_superiors` + `check_reports`, the superior's stance is keyed by the subordinate's body key.

### F10 — Promotion memories carry engine keys as prose, and the two consumers of one handoff disagree
**Severity:** WRONG-SCENE (a mind's own memories name people as `gate_watch:0002`) / two representations. **Confidence:** CONFIRMED (snippet + consumer traced).

`world/charter_promote.py` renders raw keys: 249 `f"heard from {claim['heard_from']} that {phrase}"`, 280 `f"{teller} said the fault was {key}'s"`, 298-308 promisor/beneficiary (body keys or canonical figure names) in "promised {other}: ...", 341-343 `f"knows {other}{standing}"` with `other = claim["body"]`, 367 `f"has stood {post_key} through {windows} watches"`; news phrases format `{about}` (upkeep or body key) and `{place}` (room id). The handoff's own `body_name` (124-126) is used only for experiences.

Verified (bodies named "Ilse Varn"/"Odo Brack"):
```
episodic | gate_watch:0002 said the fault was gate_watch:0001's
episodic | heard from gate_watch:0002 that custom failing at taproom
relationship | knows gate_watch:0002
semantic | has stood gate_watch through 12 watches
```
`persist/commit_background.py:5238-5256` stores `content` verbatim. The same promotion maps keys to names for the RELATIONSHIP GRAPH (`social_names`, 5066-5125), so the character trusts "Odo Brack" and remembers "gate_watch:0002". The featured-resident route renders the same handoff rows through names (`charter_history._named_surface`, 232+; `entities` mapped at 384-385). For a figure, promisor/beneficiary is the canonical name, a LEAK where the body only knew a label.
**Fix:** render memory content with the body's own known names (`social_names` restricted to bodies this head holds a claim about; figures through their surface label) inside `remembered`, or route the promotion path through `charter_history._named_surface`. **Test:** promote a body whose claims name other bodies; no stored memory content contains a body key, post key, upkeep key or room id.

### F11 — The dead stand in rooms: they receive speech, fill crowds, front them, and are laid as standing figures
**Severity:** WRONG-SCENE (+ a corpse's mind grows). **Confidence:** CONFIRMED (snippet).

`charter_harm.apply_harm` keeps a dead body's `place` (181-190; only `missing` clears it). Only `charter_talk.co_present` honours the rule "A body that is dead or missing ... is in no room: it witnesses nothing and is talked to by nobody" (146-157). Readers in scope that do not: `charter_observe.plan_public_evidence` (526-528, excludes only `bindings`), `charter_crowd.members_of` (148-169; `crowd_face` 320-326 picks min strain, and a corpse with no feel entry has strain 0), `charter_place.charter_placements` (231-243), `charter_log.scene_ledger` (330-331, presences and `strangers_here`), `charter_feel.advance_feel` (345-347). Out of scope but same gap: `charter_runtime.background_presence_records` (5317-5336 excludes departed, not dead), so a corpse becomes a voiceable presence.

Verified:
```
tam: dead place yard available False
receiving: ['ivo', 'tam', 'wat']
crowd members: ['ivo', 'tam', 'wat']
laid as placements: ['ivo', 'tam', 'wat']
```
A dead body that "heard" a promise is added to `recognized_by` (`observe_public_commitments`), and judgments update for it.
**Fix:** one predicate (`charter_harm.is_gone`) applied at every presentation/reception reader (or a shared `present_bodies(state)` helper). Lay a dead body as a body (a pose), not as a standing figure. **Test:** a dead body receives no evidence, is in no crowd, has no presence slice.

### F12 — A creature that can open doors walks through LOCKED doors; a person cannot
**Severity:** WRONG-SCENE. **Confidence:** CONFIRMED (snippet).

`world/charter_creature.py:355-362`:
```python
        every = neighbor_map(scene, None)
        for room, ends in (every or {}).items():
            for other in ends:
                edge = _edge(rooms, room, other)
                if edge and "door" in str(edge.get("barrier") or ""):
```
`charter_space.people_neighbors` (68-70) uses the engine's own fastening reader (`barrier_fastening`) so "a locked, padlocked, jammed, stuck or blocked one holds". The creature helper is the near-duplicate written first and never got the filter: `locked_door`, `padlocked_door`, `stuck_door` all contain "door".

Verified:
```
creature (can_open_doors): {'cell': {'hall'}, 'hall': {'cell'}}
people: {}
```
In a containment story the hunting thing leaves a locked cell off screen (`hunt_moves` walks `creature_neighbors`).
**Fix:** build the creature graph from `people_neighbors`' rule (`_ROUTE_MEMORY_BARRIERS` + `crossable=not barrier_fastening`) when `can_open_doors`, then apply the footprint filter. **Test:** a locked door holds a `can_open_doors` creature.

### F13 — `place` has ten writers, not one; they disagree about what moving a body clears
**Severity:** WRONG-SCENE + STALE-DOC. **Confidence:** CONFIRMED (grep + snippet).

AGENTS.md:167 says "A charter body's ROOM is `place` (the movers in `world/charter_move.py` are its only writers)" and that the station is "cleared by every writer of `place`" (also `charter_place.py:29-30`). Writers found: `charter_move._advance` (292) and `place_body` (637) clear station; `charter_surgery.move_body` (117) pops `walk` only; `charter_intervene._apply_relocate` (171) pops walk+station, not errand/lease; `charter_harm.apply_harm` missing (190) keeps station; `charter_enrol.depart_guests` (429) keeps walk/station/lease; `charter_runtime.sync_minds_to_scene` (3145, clears station); `charter_runtime.bind_promoted_character` (5841, no station pop); `charter_runtime.transfer_person` (290); `world/region_events.py:385` (displacement: `place = berth`, keeps walk and station).

Verified:
```
after move_body:  {'place': 'cellar', 'station': {'cell': [7, 2]}, 'errand': {'to': 'yard'}}
after place_body: {'place': 'cellar', 'station': None, 'errand': None}
```
After a Writers' Room `move_body`, rule (i) of `_station_and_facing` (153-170) still wins: the old room's cell is snapped onto the new room's grid, so the body stands at stale coordinates in the new room until another mover clears it. A displaced body keeps a route through a ruined room.
**Fix:** one `set_place(body, room)` helper in `charter_move` that clears station/walk/errand consistently, used by every writer; correct AGENTS.md. **Test:** each writer, given a body with a station and a walk, leaves neither behind when the room changes.

### F14 — `continue_walks` ignores the lease that `walk()` honours
**Severity:** WRONG-SCENE (an on-screen errand silently lost; registry and scene disagree for a beat). **Confidence:** PLAUSIBLE (traced, not executed end to end).

`world/charter_move.py:332` skips only `not en_route(body) or not body.get("available")`; `walk()` skips `body.get("leased")` (572-577). `charter_surgery.send_errand` (295-304) writes a walk with no lease check, and it is the Director's own `charter_ops` errand route (`persist/commit_scene_state.py:1981, 3021-3066`). For a townsperson the scene stands (an entity with `charter_ref`, leased), the next tick walks the registry body away (`charter_run.py:706-711` passes every non-external body), and the next commit's `lease_scene_bodies` -> `place_body(..., leased=...)` pops `walk` AND `errand` and snaps it back: the PB13 errand ("fetch the gate warden") is dropped without trace.
**Fix:** skip leased bodies in `continue_walks`, and have `send_errand` on a leased body either refuse with a note to the Director or release the lease explicitly. **Test:** a leased body with a walk record is not advanced by `continue_walks`.

### F15 — A body that finishes a walk and is re-dispatched in the same window is paid the window twice
**Severity:** WRONG-SCENE (bodies cross up to twice the rooms a window buys). **Confidence:** CONFIRMED (snippet).

`continue_walks` (343-345) credits the window and drops the leftover on arrival (`_advance` 299-300 pops the walk); `_dispatch` (239-240) then grants a FRESH `hours * WALK_ROOMS_PER_HOUR` to any re-posted, errand or homecoming body. The docstring (217-221) promises "not paid twice" only for the same target.
```
after continue_walks: b {'tam': 1}
after relocate in the SAME window: c rooms crossed this window: {'tam': 2}   # hours = 1/6: one room's credit
```
**Fix:** keep a per-window spent/remaining allowance on the body (or hand `_dispatch` the leftover credit from `continue_walks`). **Test:** in one window of one room's credit, `continue_walks` + `relocate` cross at most one room.

### F16 — The watch is called out again on the same stale claim as soon as it stands down
**Severity:** WRONG-SCENE (back-to-back false alarms; the caller blamed each time). **Confidence:** PLAUSIBLE (traced).

`world/charter_decide.py:236-252` dedupes a call only against places with a STANDING watch (`called = set(standing)`); `charter_intervene.apply_due` pops the record at stand-down (322). Nothing records that this evidence already spent a watch, so the leader's unchanged claim (a `harm_done` decays at the owner's grievance rate, 0.0005/h, so a firsthand claim stays above the 0.6 credence for ~800 h) re-calls the watch the window after every stand-down, and each lapse with nothing seen adds blame to the caller (`charter_run.py:1256-1262`).
**Fix:** remember the evidence id a watch was called on (e.g. on the lapsed event or a `called_on` set) and do not re-call on it; the credence and decay numbers stay the owner's. **Test:** after a false-alarm lapse, `mobilisation_calls` with the same head returns no call for that place.

### F17 — Promise memories read time keys no commitment carries
**Severity:** WRONG-SCENE (minor: chronology). **Confidence:** CONFIRMED (by reading both shapes).

`world/charter_promote.py:312-313`: `commitment.get("updated_at") or commitment.get("created_at") or 0.0`. `normalize_commitments` (`charter_commitment.py:52-65`) writes `opened_at_hours` and lifecycle `at_hours`, never those two. Every promise memory lands at hour 0. The featured-resident route sorts handoff evidence by `at_hours` (`charter_history.py:383, 513`), so promises are placed first; this is the class the comment at `charter_promote.py:264-267` fixed for news.
**Fix:** use the last lifecycle `at_hours`, else `opened_at_hours`. **Test:** a promoted body's promise memory carries the commitment's own hour.

### F18 — An enrolled person never starves: needs are seeded from the defaults, not the town's template
**Severity:** WRONG-SCENE (minor). **Confidence:** CONFIRMED (by reading; `ensure_needs` adds names, never `fed_by`).

`world/charter_enrol.py:282` `seed_needs({body_key: body})` vs the generator's `seed_needs(state["bodies"], needs_template(...))` (`charter_generate.py:1507`). Without `fed_by`, `advance_needs` services sustenance at supply 1.0 (`charter_needs.py:384-394`), the defect `needs_template`'s docstring describes; `registry_warnings` does not notice because other bodies of the charter carry `fed_by`.
**Fix:** seed from the charter's own need template (copy a sibling body's `fed_by`s or rebuild `needs_template` from the charter's economy). **Test:** an enrolled body's sustenance has the same `fed_by` as its institution's.

### F19 — `apply_charter_ops` skips validation for exactly the input the Director sends
**Severity:** SILENT-NOOP / CRASH (a cryptic refusal). **Confidence:** CONFIRMED (snippet).

`world/charter_ops.py:369-370`:
```python
        op = raw if isinstance(raw, dict) and raw.get("op") in CHARTER_OPS \
            else normalize_charter_op(raw)
```
The Planner normalizes first (`story/plot_packages.py:2758`); the Director does not: `state_diff.charter_ops` is `list[dict]` (`llm/schemas.py:2724`) and goes raw through `persist/commit_scene_state.py:1981 -> 3021-3066 -> author_charter_ops`. So the closed vocabulary's promises (module docstring 40-43: "a field outside it is a refusal rather than a silently ignored key"; caps; to/by exclusivity; `die` defaulting to `dead`) do not hold for the Director.
```
normalizer refuses: upkeep_fails does not take invented_key; its fields are upkeep, to, by, surface
raw path applied: {'intervention': 'authored:upkeep_shock:0', 'op': 'upkeep_shock'}
raw die: KeyError 'condition'          # the whole event refused; the Director is told "'condition'"
normalized die: dead
```
`docs/UNBUILT_LIVING_WORLD.md` §1.124 states "`world/charter_ops.py` already normalizes ... an `errand` op" (now stale for this route).
**Fix:** always `normalize_charter_op(raw, default_charter=...)`; it is idempotent on a normalized op. **Test:** a raw Director op with an unknown key is refused with its reason; a raw `die` with no condition lands as `dead`.

### F20 — Supply points' `place`, `route_burden` and `mode` are authored, normalized, stored and read by nothing; an English word list picks that unread place
**Severity:** SILENT-NOOP (+ DEAD English guard). **Confidence:** CONFIRMED (repo-wide grep).

The generator prompt asks for them (`charter_generate.py:149-154`, "declare a supply_point at a boundary"); `charter_economy.normalize_economy` keeps them (139-159); `advance_economy` reads only `holder`, `goods`, `reliability` (285-290). `ensure_supply_points` matches `boundary_tokens = ("gate", "entrance", "dock", "loading", "port", "checkpoint", "station", "depot", "surface")` as SUBSTRINGS of room uid/name/purpose (190-198): "port" hits "support"/"portrait", nothing hits a Japanese room name (falls back to the first room), and the result feeds the field nobody reads. Only `tests/test_fable_town.py:485` reads it. The docstring (173-179) claims the point names "their route burden and reliability".
**Fix:** either make route_burden/place mean something (deliveries arrive at the place, burden scales reliability) or drop the fields and the word list; never a word list either way. **Test:** if kept, a supply point's route burden changes delivered lots.

### F21 — An authored `duty_bearing: false` is dropped by the need template
**Severity:** SILENT-NOOP (minor). **Confidence:** CONFIRMED (snippet).

`world/charter_needs.py:322-325` copies only `fed_by, floor, drift_per_hour, service_per_hour, level`; `normalize_need` then defaults `duty_bearing` to True for any need not in `DEFAULT_NEEDS`.
```
template warmth: {'floor': 0.3, 'drift_per_hour': 0.02}
seeded: {... 'duty_bearing': True}
```
An authored loneliness-like need stands bodies down, the exact effect D18 forbade for `company`. **Fix:** add `duty_bearing` to the copied keys. **Test:** an authored non-duty-bearing need survives `needs_template` + `seed_needs`.

### F22 — A dangling `depends_on` (or a non-sustenance `fed_by`) starves silently
**Severity:** SILENT-NOOP. **Confidence:** PLAUSIBLE (by reading).

`charter_drift.supply_factor` (26-27) and `starving_input` read a missing input as level 0.0; `charter_needs.advance_needs` (385-387) does the same for any need's `fed_by`. `charter_runtime.registry_warnings` (2657-2697) checks `serves`, `reports_to` and SUSTENANCE `fed_by` only, so a misspelled `depends_on` collapses a chain and an authored `health.fed_by` (the very case `needs_template` documents, 310-312) never heals, without a notice.
**Fix:** warn on every unresolved `depends_on` and every need's `fed_by`. **Test:** `registry_warnings` names a dangling `depends_on`.

### F23 — Charter modules write English into views, voices, memories and the carrier rail
**Severity:** WRONG-SCENE in any non-English story. **Confidence:** CONFIRMED for `_plural` (snippet), by reading for the rest. Not registered.

Each of these reaches a reader-facing surface without `language_runtime` (which `charter_surface` uses correctly):
- `charter_chatter.py:48-49, 197-201, 280-292, 316, 364` — hum bands, "Close by, %s can be overheard %s", act phrases, "the %s"; into every observer's view (`agents/common.py:3094-3129` -> `composer.chatter_percepts`).
- `charter_crowd.py:183-204, 275` — English plural rules and " and ": `composition_of` gives `鍛冶屋s and 徒弟s` (verified) into crowd descriptions.
- `charter_observe.py:190-200` ("{actor} said {quote}", "someone", "acted") and `charter_mind.py:159` ("was reported saying") — the claim text a voice brings up.
- `charter_news.py:311-340` `_native_news_phrase` — voice `can_bring_up` (`charter_runtime._voiced_presence.happening`) and carrier envelopes (`report_from_claim`, whenever `claim_text` is empty, which is every native news claim).
- `charter_promote.py:85-98, 139-185, 247-251, 280, 291-309, 336-343, 367` — every promotion memory.
- `charter_feel.py:247-265, 293` — `why` persisted as the hedonic `source` (`mind/psychology_runtime.py` ~286) and handed to the promoted sheet.
- `charter_intervene.py:233-234` — `f"a disruption affected {upkeep_key}"`: English plus an engine key, put on the objective carrier rail by `charter_runtime._event_surface` (2864-2865).
Near-duplicate tables for one vocabulary: `_native_news_phrase`, `charter_promote._NEWS_PHRASES`/`_SELF_KINDS`, and `charter_runtime._event_surface` (out of scope) phrase the same event kinds three different ways.
**Fix:** one pack-owned template table per surface (`compositor_text`), and one event-kind phrase table. **Test:** with the `ja` pack active, a chatter fragment, a crowd composition and a promotion memory contain no ASCII template words.

### F24 — English-only recognisers decide who a line was aimed at and which post a person holds
**Severity:** WRONG-SCENE (silent in Japanese). **Confidence:** PLAUSIBLE (by reading).

`charter_observe._tokens` (245-246, `[a-z0-9]+`) and `_stem_role_word` (269-277, English suffixes) power `resolve_target_body`'s role and subset readings, `_post_forms`, and enrolment (`charter_enrol._role_words` 72-84, `posts_for_role` 98-113, whose head-noun rule cites English word order). A Japanese label yields no tokens, so a comm/ear line addressed by role reaches nobody, a promise's party resolves to nobody, and enrolment never finds the post. `charter_surface._phrase_in` (325-330) asserts `\w` boundaries, which never hold inside CJK text, so `settle_render`/`reconcile_surface` never react to a Japanese description.
**Fix:** route tokenizing/boundaries through the pack (`name_boundary_pattern` is already the engine's answer for names). **Test:** ja-pack `resolve_target_body` resolves an exact role title.

### F25 — Dead code
**Severity:** DEAD. **Confidence:** CONFIRMED (repo-wide reference count incl. tests/tools/JSON/markdown).

- `charter_space.room_traffic` (138-200, 63 lines): no reference anywhere but CODE_MAP.
- `charter_news.spread_of` (557-565), `charter_politics.regard_between` (100-101), `charter_mind.normalize_minds` (39-50): exported by the `world/charter.py` facade, called by nothing. `normalize_minds` is also duplicated inline by `charter_model.normalize_charter` (682-686).
- `charter_enrol.ENROL_HOW` (57, "for the record and the tests": no test reads it), `charter_surface.SILHOUETTE_AXES`/`FACE_AXES` (54-56; `surface_label` hard-codes its tiers).
- Test-only: `charter_move.walked_edges`, `charter_chatter.participant_label`. Tool-only: `charter_move.furthest_travelled`.
**Fix:** delete, or wire `SILHOUETTE_AXES`/`FACE_AXES` into `surface_label`/`surface_words`.

### F26 — Stale docstrings
**Severity:** STALE-DOC. **Confidence:** CONFIRMED.
(a) `charter_place.py:61-66, 205-206`: a placement is keyed by name "when it is unique across the registry"; the count (238-241) runs only over the frame's rooms. (b) `charter_move._dispatch` (217-221) "not paid twice": F15. (c) `charter_news.decay_news`/`check_reports` (442-446, 503-509) present the key index as the cheap path; measured slower than a full scan once a town holds many news subjects (E4). (d) `charter_log.life_of` (208-212) labels as `regarded_by` the regard this body HOLDS (`regard_key` is `listener->speaker`, `charter_politics.py:49-51`). (e) `charter_drift.hours_until_floor` (78) says None when "already below"; it returns 0.0. (f) `charter_economy.ensure_supply_points` (173-179): F20. (g) AGENTS.md:167: F13.

### Q3 observations (promotion routes) — not counted as findings
- Two routes bind a charter body to a registered character: background promotion (`persist/commit_background.promote_background_character` -> `charter_runtime.promotion_bundle` -> `charter_promote.promotion_handoff` -> `bind_promoted_character`) and featured residents (`charter_history.integrate_featured_resident` -> `bind_promoted_character`). `charter_skip` binds only inside a scratch copy. `charter_promote` itself mints nothing; it is the shared payload.
- They disagree on: memory text (raw keys vs names, F10); memory time (`turn_idx: promoted_turn` and no `encoded_at_seconds` vs `PRESTORY_TURN_IDX` plus `encoded_at_seconds`, `charter_history.py:768-794`, whose comment says a whole life at the current turn reads as recent); name-collision refusal and mutual recognition live only in the background route (`_refuse_name_collision` 5013, `seed_mutual_recognition` 5224), which is right for it (featured residents are already registered).
- `promotion_bundle` returns None when `_body_refs` does not find exactly one unbound body (5788-5791), and the promotion then proceeds with no binding and no handoff, so the charter body keeps simulating beside the new character (PLAUSIBLE, outside the 28 files).

## Efficiency

### E1 — `scene_ledger` re-normalizes whole social stores once per presence, and `presence_view` builds every presence to keep one
`world/charter_log.py:338-461`: `judgment_view` (453) runs `normalize_judgments` over the WHOLE store; `commitment_view` (455) `normalize_commitments`; `decision_view` (457) `normalize_decisions`, all inside the per-presence loop. `charter_runtime.presence_view` (5158) calls `scene_ledger(state, place)` for each matched body and keeps `.get(body_key)`. Hot: per beat, per voiced background body (agents/background), and per `place_view`. Measured (synthetic 300 bodies, 60 in one room, 12 stances x 4 reasons each): `scene_ledger(c, "yard")` 3.94 s; one `normalize_judgments` 0.0585 s (x60). Fix: normalize each store once per call and add an `only=body_key` mode. Expected gain: ~N-fold (60x here).

### E2 — The evidence appraisal tests every body in the town, and runs twice per beat inside the locked commit
`world/charter_observe.py:503-578` loops all bodies for every evidence row; the sensory cache keys on each body's own dealt cell, so it rarely hits. `charter_runtime.ingest_public_evidence` (4632-4655) appraises on the shared registry, then `apply_public_evidence` re-plans from scratch (592) instead of consuming the plan. Measured (300 bodies over 30 rooms, 6 rows): one plan 1.89 s for 1,800 opportunities, of which the 270 bodies outside the actor's room and its neighbours cannot sense anything. Fix: prefilter bodies to `rooms_in_frame(actor room)` (plus the comm endpoint), and pass the appraisal's plan into the apply. Expected gain: ~10x per plan and a further 2x per beat.

### E3 — `advance_economy` normalizes the whole economy twice per target, every window
`world/charter_economy.py:281-283, 308-309`: `stock_band(before/out, ...)` calls `normalize_economy` on each call (223). Hot: once per window per charter (`charter_run.py:806`), every beat. Measured: 0.72 s per call with 20 holders x 12 goods (one normalization 1.5 ms). `quote` does the same (243), and `scene_ledger` calls it twice per good (474-475). Fix: an internal band/quote over an already-normalized economy. Expected gain: ~400x on that loop.

### E4 — The news-key "index" iterates every news subject of the town for every head
`charter_news.decay_news` (515) and `check_reports` (445): `[s for s in keys if s in claims]` is O(heads x all subjects) where a full scan is O(heads x 48). Measured (500 heads x 48 claims, 1,500 distinct subjects): indexed 0.060 s vs full scan 0.011 s. Hot: twice per window per charter. Fix: keep the empty-index early return; otherwise `claims.keys() & keys` (O(min)) or scan the head's own claims.

### E5 — `charter_placements` recomputes room geometry per body
`world/charter_place.py:246-250` calls `effective_anchors(scene, room)` per body and `_dealt_cell` -> `room_grid` + `anchor_cells` per body (132-143). `observer_view` runs it over every room the scene holds per charter, twice per evidence beat (E2). Measured: 0.066 s for 300 bodies in 30 medium rooms. Fix: memoize `(anchors, grid, free cells)` per room for the call. Expected gain: ~10x.

### E6 — Minor repeated full scans
`charter_observe.apply_public_evidence` rebuilds `news_keys` over all minds (603-606); `charter_run` calls `news_keys_in` up to four times a window; `commitment_view`/`judgment_view` normalize per call wherever used. Low gain; fold into E1/E4.

## Already registered

- UNBUILT_LIVING_WORLD §1.152 "A creature can be stopped by the shape of an opening and by nothing else" — creature avoidance fields. Related to, but distinct from, F12 (the locked-door hole is not mentioned there; the entry asserts a door "holds a wolf").
- UNBUILT_WORLD §1.84 "A condition with no declared end ... stands forever" — free-text `world_conditions`. The charter `condition` is a closed enum whose `hurt` heals on `HURT_RECOVERY_HOURS` and whose `dead`/`missing` are final by design, so it is NOT this class. The one charter "no end" found is F8 (cap eviction), unregistered. (Inverse edge, not a finding: `normalize_body` defaults a missing `hurt_at_hours` to 0.0 (`charter_model.py:281-284`), so a body written `hurt` mid-story without a timestamp heals on the first window.)
- UNBUILT_LIVING_WORLD §1.99a — the `mood_weight` x disgrace double count (`charter_run.py:617-627`, `charter_needs.mood` docstring): registered, not re-reported.
- UNBUILT_LIVING_WORLD §1.124 (Director errand channel, BUILT): its text "already normalizes" is contradicted by F19 (the defect itself is new).
- UNBUILT_CHARACTERS §2.20 — the promotion memory prototype and the "haunting" concern; describes `remembered` but does not register F10/F17.
- UNBUILT_LIVING_WORLD §1.10a — promoted body's place knowledge (context for F6, which is about secret/provisional rooms and is not in it).

## Structure notes

**Monoliths in miniature:** `charter_promote.remembered` (268 lines; eight experience kinds, news, blame, promises, people, service, all string-building), `charter_log.scene_ledger` (217), `charter_creature.normalize_creature` (163), `charter_intervene.apply_due` (157, seven ops in one if-chain), `charter_observe.plan_public_evidence` (154), `charter_move.errands` (122), `charter_plan.plan_watch` (122, three closures redefined per post), `charter_feel.appraise_window`/`advance_feel` (112/104), `charter_enrol.enrol_person` (110), `charter_place.resolve_scene_placements` (100).

**Natural seams:** (1) a "presentation filter" module — who is present and perceivable (gone, departed, bound/reserved, leased, presented) — currently re-decided in `co_present`, `members_of`, `charter_placements`, `_spelling_table`, `plan_public_evidence`, `background_presence_records`, each with a different subset (F11). (2) One place writer in `charter_move` (F13). (3) A pack-owned "charter phrasing" module for event kinds, experiences, acts and crowd composition (F23), replacing three phrase tables. (4) `charter_promote.remembered` splits into "select" (pure, keys) and "render" (names + pack), the render shared with `charter_history._named_surface` (F10).

**Near-duplicates (question 1), beyond the findings:**
- Graph walks: `charter_enrol._room_distances` (BFS on `passable_neighbors`, where a shut door is a wall), `charter_space._route_on` (BFS on the caller's graph), `charter_intervene._apply_relocate` (inline BFS on `creature_neighbors`, 148-163). Enrolment measures "nearest house" on a graph people do not walk (`people_neighbors`); the class `walk_route`'s docstring warns about.
- Door graphs: `people_neighbors` vs `creature_neighbors` (F12).
- Surface vs description: `charter_enrol.reconcile_surface` (245-262: the seen value WINS) and `charter_surface.settle_render` (333-364: a contradicting value REFUSES the render) run the same pool/phrase loop with opposite policies.
- Body naming: `charter_promote.remembered.body_name`/`acquainted` (`name or key`) vs `charter_identity.display_name` vs `agents/common` chatter `_name` vs `charter_runtime._member_namer` (F10).
- Watch inversion (`{body: [posts]}`): `charter_place._roles_of` and `charter_crowd._held_posts` are body-identical; five more inline copies (`charter_observe.py:386, 475`, `charter_talk.py:318`, `charter_runtime.py:901, 3582`).
- Failing test: `charter_model.out_of_band` vs inline `level < floor` in `charter_feel.py:220-222, 339-340` (same meaning, different defaults on missing keys).
- Trivial helpers: `_text` in `charter_surgery`/`charter_ops` (byte-identical, limit 240) and `charter_enrol` (limit 200); `_number` in `charter_mark` (local by design), `charter_ops` (raises), `charter_model.number`.
- Spelling tables: `charter_place._spelling_table`, `charter_runtime.charter_carriers` (its docstring says so), `charter_observe._identity_forms`.
- Minds normalization: `charter_mind.normalize_minds` (dead) vs `charter_model.normalize_charter` 682-686.

**Module-level mutable state:** none. No `global`, no `lru_cache`, no module caches in the 28 files; module dicts (`DEFAULT_NEEDS`, `DEFAULT_CONTEST`, `MARK_HOURS`, `WITNESSABLE`, `_HANDLERS`) are read-only and copied before use (`charter_creature.py:156`, `charter_needs.py:126, 315`). In-place mutation of caller state is documented where it happens (`charter_intervene.apply_due`, `charter_surgery.*`, `charter_place.lay_charter_bodies`, `heal_unbound_twins`, `charter_move.place_body/station_body`, `charter_harm.apply_harm(copy_state=False)`).

**Smaller observations (not findings):** `charter_observe.plan_public_evidence`/`resolve_target_body` exclude only `bindings`, where every other reader uses `body_of_an_authored_mind` (a seat-reserved body grows a charter mind that `charter_run` drops next window). `charter_enrol.enrol_person`'s "already held" check (323-335) compares only `name`/body key, not display name or aliases, so a role-named person whose post seats are full is enrolled as a guest beside the real holder (PLAUSIBLE shadow). `charter_surgery.assign_post` forces `available=True` over needs (self-corrects next window).

## Docs checked

| claim | where | held? |
|---|---|---|
| "A charter body's ROOM is `place` (the movers in `world/charter_move.py` are its only writers)" | AGENTS.md:167-168 | NO: ten writers (F13) |
| station "cleared by every writer of `place`" | AGENTS.md:171; charter_place.py:29-30 | NO (F13) |
| "no positions, stations or orientation row for an unpromoted body is ever stored" | AGENTS.md:178-179 | Held in these modules (view-only `scene_with_charter_bodies`) |
| "Judgment is always holder->subject with evidence ids, never a universal reputation score" | AGENTS.md:115 | Partly: formal reports file stances under a display name (F9); blame moves regard institution-wide (F5) |
| "A commitment is locally recognized by actual hearers" | AGENTS.md:116 | Held, except the dead count as hearers (F11) |
| "Leaders read only news in their own minds, and typed orders move down staffed co-present reporting edges" | AGENTS.md:119-120 | Held (`advance_decisions`, `deliver_orders`) |
| "Markets use abstract lots and physical caravans; no broadcast trade or coin simulation" | AGENTS.md:118-119 | Held |
| "Name learning must still prove an exact delivered line and physical co-location" | AGENTS.md:55-56 | NO for `public_evidence.target` (F2) and chatter subjects (F4) |
| presence_view "Only what one Charter body earned, never its institution's register" | charter_runtime.py:5039 | NO (F1) |
| scene_ledger "The institution's register is absent" | charter_log.py:299 | NO (F1) |
| promotion: blame "never cross[es]" unless said aloud | charter_promote.py:29-33 | Held for promotion; broken on the voice path (F1) and via regard (F5) |
| co_present: the dead witness nothing and are talked to by nobody | charter_talk.py:153-155 | Held only there (F11) |
| `_dispatch`: "not paid twice" | charter_move.py:217-221 | NO for arrival + re-dispatch (F15) |
| decay_news: the key index avoids a costly full scan | charter_news.py:503-509 | Only for an empty index; slower otherwise (E4) |
| charter_ops: "a field outside it is a refusal rather than a silently ignored key" | charter_ops.py:40-43 | NO on the Director route (F19) |
| UNBUILT_LIVING_WORLD §1.124: charter_ops "already normalizes" | register | NO (F19) |
| "THE CHARTER ADVANCES EVERY BEAT" with a 10 s wall budget | AGENTS.md:182-203 | Not measured here; E1-E5 are costs inside it |
| Design.md | grep "charter" only | Skimmed, rows not verified |
