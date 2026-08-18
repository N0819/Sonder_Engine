# Audit: `agents/character.py`, `agents/loops.py`, `agents/background.py`

The fictional minds, read whole. `character.py` (3,408 lines), `loops.py`
(1,050), `background.py` (964) — every line, in order, against `Design.md`,
`AGENTS.md`, `docs/guides/PIPELINE.md` and the design notes those three cite.

Same register and discipline as
[`AUDIT_DIRECTOR.md`](AUDIT_DIRECTOR.md): **flagged, not fixed.** Nothing in
this audit changed a line of source, and `docs/UNBUILT.md` was deliberately
not touched (other agents are working concurrently).

**Baseline revision:** `8f203c3`. Every `file:line` below is as of that
revision unless said otherwise.

**One commit dominates the residue.** `e629d60` ("Weak output is not broken
output, and only broken output earns a redo", 2026-08-18) removed the
character stage's decision-review re-ask. It is the right change and its
reasoning is written into the file. But it touched no maintained document —
`git show --stat e629d60` lists `docs/CODE_MAP.md` and nothing else under
`docs/` — so four separate doc claims and one dead function survive it
(findings 6, 7, 8 and Part 2's character-module verdict).

---

## Part 1 — findings. FLAGGED, NOT FIXED.

### Information-boundary findings

These come first because they are the slice's own category. Per `AGENTS.md`
invariant 4, each was found by looking for a guard that CANNOT fire or a
payload field that never had one — not by an error.

#### 1. `_unanswered_question_note` delivers another mind's verbatim line with no delivery gate at all

`agents/character.py:285-401`, reached unconditionally from the payload at
`3103-3104`.

The function walks the last three turns' stored `interaction_loop` /
`reaction_loop` variants, reads **every other character's** result, and on a
match copies that character's own spoken text into this character's payload:

```python
speaker = str(result.get("name") or "").strip()
said = [e.get("text") for e in (result.get("sequence") or [])
        if isinstance(e, dict) and e.get("type") == "speech"
        and e.get("text")]
...
asked = {"from": speaker, "asked": str(said[-1])[:240],
         "turns_ago": int(current_turn_idx) - int(row["idx"])}
```
(`character.py:371-400`)

There is no `_delivery_ok`, no `hear_level`, no room comparison, no
`visibility == "concealed"` check, and no awareness check. The only test is
the ASKER's own `interaction.expects_response` + `interaction.addresses` — a
field the asker writes about its own intent. Intending to address somebody is
not the same as their having heard it; separating those two is what
`agents/common.py:_delivery_ok` exists for, and `AGENTS.md` names it as the
gate "every deterministic delivery site must call".

Two concrete crossings:

* A character declares a question addressed to B while B is in another room
  behind a shut door. Perception correctly delivers B nothing. Up to three
  beats later B's payload carries `awaiting_your_answer: {from: <name>,
  asked: "<the line, verbatim>"}`.
* `said[-1]` is the LAST speech element of that result, whatever its
  `visibility`. A character who asks B a question overtly and then whispers a
  concealed line has the **concealed** line copied into B's payload, because
  the element list is filtered on `type == "speech"` and nothing else.

The player branch (`character.py:344-362`) has the same shape: it reads
`director_interpret["speech"]` — the player's whole declared line, which is
where a concealed player line also lives (`_filtered_player_declaration` in
`background.py:102-108` exists precisely because that string may carry
concealed words) — and gates it only on `flow.addressed_to`.

What makes this unambiguous rather than arguable is the function five lines
above it in the same payload block. `_player_silence_note`
(`character.py:438-470`) refuses to say even *whether the player spoke*
without co-location:

```python
positions = (sc or {}).get("positions") or {}
here = positions.get(character_name(sh))
if not here or positions.get(player) != here:
    return {}
```

with the reason in its own docstring: "a character elsewhere has no standing
to know either way". The note beside it hands over 240 characters of somebody
else's speech with no such standing test.

#### 2. `_present_others` is documented "co-located" and has no location filter

`agents/background.py:856-900`. Docstring, first line: *"Co-located character
names for a background presence's payload"*. The body:

```python
present_others = [p_name if p_name in recognized
                  else _unknown_actor_label(p_name, persona_appearance(pers))]
for row in ctx.cast:
    sh = json.loads(row["sheet"])
    cname = character_name(sh)
    present_others.append(
        cname if cname in recognized
        else _unknown_actor_label(cname, character_appearance(sh)))
```

`ctx.cast` is `active_cast(chat_id, frame_id)` (`agents/runtime.py:760`) —
the whole frame's active cast, never room-scoped. So a background presence
standing at its post is told, in its `beat.present_others`, about every
attached character in the story: those in the next room, those across the
city, those it has never been within a mile of. The recognition gate is
intact (an unrecognized body renders as its appearance label), which is why
this reads as safe — but the label still asserts a BODY IS HERE, and that
assertion is the leak: *"a tall woman in a red travelling coat"* about
somebody three rooms away.

Both paths use it: the per-presence payload at `background.py:943` and the
manager's `beat.present_characters` at `567-568`.

Every other gate in this file is per-presence and spatial —
`_beat_for_presence` gates on station room and `hear_level`, `_audience_map`
runs `hear_level` per managed presence, `managed_presences` filters on
`ambient_scope`. This one field skipped all of it, and its docstring asserts
the property it lacks.

#### 3. `player_declaration` bypasses the audience map and the `_prose_shared` gate

`agents/background.py:82-108`, used at `564` (manager) and `942`
(per-presence).

`_filtered_player_declaration` removes concealed sequence elements and the
private thought. It applies **no** hearing check, no room check, and no
per-presence audience tag. It is then dropped into the payload beside two
fields that were built precisely to answer that question:

* `events` (`background.py:530`) — every line carries `audience`, a per
  presence `hear_level` map, and `_audience_map` returns `None` (the event is
  not admitted at all) when no managed presence can hear it
  (`background.py:490-491`).
* `resolved_event` (`background.py:563`) — admitted only when
  `_prose_shared`, i.e. every managed presence stands in the player's room,
  with a 10-line comment (`547-557`) explaining that a shared context makes
  annotation insufficient and non-admission necessary: *"This is the field
  that nullified `_audience_map`'s work: the tags said 'none' while the prose
  beside them said everything."*

`player_declaration` is a third field carrying the same beat's content, and
it is the one nothing gates. The player's spoken line reaches a presence for
whom `_audience_map` computed `"none"` and for whom `_prose_shared` withheld
the prose.

On the per-presence path the mismatch is sharper still: `_beat_for_presence`
(`background.py:111-190`) fails closed three separate ways — no station room,
no speaker room, station room != beat room — and returns `""`. The very next
key in the same dict hands over the player's declaration regardless
(`background.py:938-942`).

`docs/design/BACKGROUND_LIFE_DESIGN.md:133-135` states the property the code
does not have:

> The beat is perception-filtered (`_beat_for_presence`,
> `_filtered_player_declaration`): concealed lines dropped, unhearable lines
> dropped by `hear_level` […]

`hear_level` appears nowhere in `_filtered_player_declaration`.

#### 4. A follower is handed its target's objective room with no perception gate

`agents/character.py:2908-2917`:

```python
_self["following"] = {
    "target": _my_follow.get("target"),
    ...
    "target_room": room_of(sc, _my_follow.get("target")),
    "same_room": (room_of(sc, _my_follow.get("target")) == char_room ...),
}
```

`room_of` reads `scene.positions` — objective truth. The comment above it
(`2897-2899`) justifies only the SEPARATION fact: *"Surface its own relation
as self-knowledge even after a fast target has pulled ahead; separation does
not silently decide whether it keeps chasing or stops."* `same_room` carries
that justification entirely. `target_room` carries more: the exact room id of
a body the follower may have lost through a door, into a hidden interior, or
across a sight barrier.

No test asserts on either field (`tests/test_following.py` contains neither
string), and no maintained doc mentions them, so this is not a documented
exception — it is an ungated read of another body's position, in the one
payload whose whole contract is "own interoception and own scrubbed
observations".

#### 5. The background gate still reads the raw player input the payload was filtered to remove

`persist/commit_background.py:1082` and `1143`:

```python
player_input = str(ctx.get("input") or "")
...
addressed = _background_name_mentioned(name, player_input)
```

`agents/background.py:82-89` describes this as a solved problem:

> `background_react` used to pass `ctx.input` raw, leaking whispered or
> silently-sent content (and any private thought the player typed) straight
> into an unregistered presence's payload; **worse, a declaration that named
> the presence WHILE concealing made the deterministic gate more likely to
> pick them to react to words they never heard.**

The first half was fixed (the payload now goes through
`_filtered_player_declaration`). The second half is still live: the gate is a
different function in a different module, and it reads `ctx.input` whole.
A player who whispers a background presence's name still makes that presence
qualify as `addressed`, be picked, and react — to words nobody delivered to
them. The comment reads as a description of the fixed state; it is a
description of half of it.

---

### Removed-feature residue (`e629d60`, 2026-08-18)

#### 6. `_sanitize_nonsteering_intention_refs` has no production caller; one test keeps it alive

`agents/character.py:700-728`. Its only caller was
`_retry = _sanitize_nonsteering_intention_refs(_retry, _retry_spent)`, deleted
in `e629d60` (`git show e629d60 -- agents/character.py`, line 212 of the
diff). Verified with `grep -rnw` over every `*.py` in the tree: zero
production references. The single surviving caller is
`tests/test_character_self_lines.py:403`.

Its docstring now describes something that does not happen: *"Prevent a
rejected spent aim from persisting as next beat's steering."* Nothing is
rejected any more — `_spent_refs` produces a warning string
(`character.py:3304-3313, 3347-3351`) and the result is committed unchanged.
The boundary itself survives, but at commit
(`persist/commit_memory.py:886`), not here; this function is a second,
unreachable copy of it.

#### 7. Three multi-sentence `instruction` strings are built and never read

`agents/character.py:3280-3313`. The `_corrections` dict was the retry
payload — `_agent_json(..., {**payload, **_corrections}, ...)` in the removed
block. Today the dict has exactly two consumers:

* the warning message at `3347-3351`, which formats only
  `you_already_said` / `you_already_did` / `nonsteering_ids`;
* `_barren_beat` at `3346`.

`repeat_correction.instruction`, `move_correction.instruction` and
`intention_correction.instruction` — 13 lines of prompt text between them —
are assembled on every character call that trips a screen and go nowhere.

Also at `3346`: `_barren_beat = bool(_corrections) and "move_correction" in
_corrections` — the left conjunct cannot be False when the right is True.

#### 8. Three dead imports

`agents/character.py:7` (`import time`), `:46` (`get_prompt`), `:69`
(`attire_view`). Verified by AST: no `Name` or attribute-base reference to any
of the three anywhere in the module. `time` was left by `e629d60` (it timed
the retry); `attire_view` was superseded by `compact_attire`
(`character.py:2797`). `make structure` does not check for unused imports, so
nothing catches these.

---

### A configurable value nothing reads

#### 9. Five interaction-config knobs have no consumer, and two of them have a UI checkbox

Verified with `grep -rlw` over every `*.py`, `*.js` and `*.html`:

| key | defined | route | UI | read by |
| --- | --- | --- | --- | --- |
| `max_speakers_per_round` | `story/scene.py:1553` | — | — | **nothing** (2 tests set it) |
| `max_director_calls` | `story/scene.py:1568`, per-rung in `interaction_limits` | `web/app.py:4147` | — | **nothing** |
| `max_perception_calls` | `story/scene.py:1569`, per-rung in `interaction_limits` | `web/app.py:4147` | — | **nothing** |
| `stop_on_player_address` | `story/scene.py:1572` | `web/app.py:4127` | `static/js/settings.js:264` | **nothing** |
| `allow_npc_initiative` | `story/scene.py:1570` | `web/app.py:4125` | `static/js/settings.js:262` | **nothing** |

The last two are the serious ones: a host sees a labelled checkbox, toggles
it, the value is validated and persisted, and no code anywhere asks for it.
`stop_on_question_to_player` and `silence_ends_exchange`, rendered by the same
two lines of `settings.js`, ARE read (`agents/loops.py:853, 904`) — so the
panel is half live, and nothing distinguishes the halves.

`max_director_calls`/`max_perception_calls` are additionally re-derived per
autonomy rung by `interaction_limits` (`story/scene.py:1604-1615`) and stored
by `dlg_put`'s derived loop, so the ladder maintains four numbers of which two
are decoration.

The constants live in `story/scene.py`, outside this slice; `agents/loops.py`
is the module they were written for and is where their absence is visible.

#### 10. `initial_parallel_reactors` cannot be set, and saving the settings panel erases a hand-set value

`agents/loops.py:638` reads it; `story/scene.py:1559` defaults it to 1;
`Design.md:159` calls it a supported knob — *"so `initial_parallel_reactors`
defaults to 1 and survives as a knob"*.

`web/app.py:4110-4155` is the only production writer of `dialogue_config`
(`grep` for the key: `story/scene.py` reads, `persist/checkpoints.py` lists,
three `tools/*_drive.py` scripts write, `web/app.py:4154` writes). It builds
a **whole-config replacement** from an explicit whitelist and `wset`s it. The
whitelist contains neither `initial_parallel_reactors` nor
`parallel_isolated_reactors`.

So the knob has no writer at all, and worse: a value set by hand through
`wset` survives only until the next time anyone saves the dialogue panel, at
which point the blob is replaced without it and `dialogue_config()` falls back
to the default. A knob a maintained doc names as the supported way to restore
a behaviour is unreachable through every supported path.

---

### Two representations of one rule, free to drift

#### 11. Three hand-maintained copies of the language pack's verdict vocabulary, and the integrity test declares that vocabulary translatable

`agents/character.py:1213-1220`:

```python
_APPEAL_ORDER = ("UNTRIED", "proven", "unentered", "known", "circling",
                 "spent", "no way through", "closed")
_DISCOURAGING = frozenset({"circling", "spent", "no way through", "closed"})
```

Both are English literals. The labels they index come from the language pack
(`_ling("_VERDICTS")`, `character.py:1238`), which stores triples of
`(entry_key, label, because)`. They are consumed by exact match in four
places: `_appeal`'s `_APPEAL_ORDER.index(label)` (`1305`), `_verdict`'s
`label == "circling"` (`1262`) and `label in _DISCOURAGING` (`1282`),
`_rank`'s `str(entry.get("verdict")).startswith("known")` (`2201`), and
`only_way_onward`'s `_APPEAL_ORDER.index("circling")` (`2224`). A label the
tuple does not contain silently sorts last (`_appeal` returns
`len(_APPEAL_ORDER)` on `ValueError`, `1306-1307`) — so a mistranslated or
renamed label does not error, it collapses exit ordering, the
discouraging-marker pruning and the goal clamp all at once, with no warning.

`tests/test_language_pack_integrity.py:147-149` is the guard, and it protects
the wrong element:

```python
CANONICAL_BEARING = {
    ("agents.character", "_VERDICTS"):
        "element [0] is the maze exit-entry key read by affect's verdict table",
```

with `_canonical_values` extracting `item[0]` only and a comment stating *"the
tail is reader prose and is expected to be translated"* (`:169-172`). Element
[1] IS the tail and IS canonical. The `ja` pack happens to leave the labels in
English (`language_packs/ja/cards/linguistics.json:2116` — only element [2] is
translated, by `tools/build_japanese_pack.py:325-330`), so the invariant holds
today by convention, enforced by nothing and documented nowhere.

The same comment names the wrong reader: there is no verdict table in
`mind/affect.py`. `grep -rnw _VERDICTS` finds the two pack files, this test,
the builder, and `agents/character.py:1238`. The one reader is `_verdict`.

#### 12. `_attach_unbidden`'s recall budget is a hand-set 8 against `memory._RECALL_LIMIT = 16`

`agents/character.py:864-878`:

```python
def _attach_unbidden(memory_context, entry, recall_limit=8):
    """Substitute, never add: … When recall came back under budget it simply
    takes the spare slot; when full, the lowest-ranked ordinary recall yields."""
```

The caller (`character.py:2634-2635`) passes nothing, so `8` decides. The
actual budget is `mind/memory.py:1685` `_RECALL_LIMIT = 16`, narrowed by
absorption to `min(recall_limit, 8)` at ≥0.35 and `min(recall_limit, 4)` at
≥0.7 (`memory.py:2915-2920`). So for a calm mind — absorption < 0.35, the only
band where unbidden recall can fire at all (`_UNBIDDEN_ABSORPTION_CEILING =
0.85`, and the plateau/refrain triggers are commonest when calm) — recall
returns up to 16 rows and the function evicts one at 8. Eight spare slots
exist and it drops a memory anyway.

`AGENTS.md`'s statement of the contract ("substituting for one of the ordinary
recall slots so the payload budget is constant") is satisfied by accident:
constancy holds above 8 and the docstring's "spare slot" case is what actually
misfires. `tests/test_unbidden_memory.py:234, 241` pass `recall_limit=8`
explicitly, so the suite asserts against the constant rather than against the
budget it is meant to track.

#### 13. Two answers to "where is this background presence standing"

`agents/background.py:364-376` defines `_presence_room`, which prefers the
live scene position (own key, then entity id, then the sketch's
`station_room`) and exists because *"a direct `_room_of(name)` lookup misses
almost every presence"*. The scene-manager path uses it (`444`).

The per-presence path never does. `_react_one` reads `sketch.get(
"station_room")` three times (`915`, `930`, `935`, `939`) and
`pick_background_reactors` reads the same sketch field
(`persist/commit_background.py:1143`). The sketch is what
`track_background_presences` harvested when the presence was INTRODUCED.

So a presence who has since moved is judged, addressed and fed its beat at the
room it was first seen in: `_beat_for_presence`'s `str(station_room) !=
str(beat_room)` check (`background.py:188`) returns `""` for a presence
standing in the player's room whose sketch says otherwise, and conversely
admits the beat prose to a presence whose sketch matches the player's room but
who has walked out of it. The manager path, on the same beat, uses the live
position. Nothing reconciles them.

#### 14. `_unanswered_question_note` and `_recent_self_moves` read different step sets

`character.py:179` (`_recent_self_moves`):

```sql
AND (s.key='interaction_loop' OR s.key=?)     -- f"character:{char_id}"
```

`character.py:323` (`_unanswered_question_note`):

```sql
AND s.key IN ('director_interpret','interaction_loop','reaction_loop')
```

`agents/runtime.py:591-596` plans bare `character:<id>` steps instead of
`interaction_loop` whenever `autonomy == 0` on an uncontested beat. On such a
chat every character's declaration is stored under `character:<id>`, which the
second query does not select — so no character-asked question ever becomes a
debt, `awaiting_your_answer` is permanently absent, and
`interaction_loop`'s `_owes` ordering (`loops.py:476-502`) has nothing to
order (moot there, since the loop is not planned either). The sibling ledger
five hundred lines up already reads both step keys.

The failure is invisible: the note is absent on every beat, which is exactly
what the design says a beat with nothing owed should look like
(`character.py:309-310`, "Presence is the signal … the field is absent on any
beat where nothing is owed").

---

### Behaviour defects

#### 15. `background_react` discards the scene manager's entire output on any beat with an unpaid routed debt

`agents/background.py:228-292`:

```python
out = scene_life(ctx, nonce, level, cfg)
...
_unpaid = [n for n in _owed if n.casefold() not in _spoke]
if out["fired"] and not _unpaid:
    return out
if not out["fired"] and level == "full" and not _unpaid:
    return out
cap = int(cfg.get("max_reactors", 1) or 1)
...
names = pick_background_reactors(ctx, dr, cap=cap)
if not names:
    return _result([], [])
...
return _result(names, reactions, mode="background_react", ...)
```

When the manager fired for presences A and B while a third presence C carries
an unpaid `routed_to_background` debt, control falls past both returns. `out`
is then referenced nowhere: `_result([], [])` or `_result(names, reactions)`
is returned, and A's and B's lines, `out["blurbs"]` and `out["claims"]` are
dropped on the floor. The `blurb_mint` provider call that produced those
blurbs was already paid for, and because commit never persists them
(`background.py:637` — *"persisted by commit.track_background_presences"*)
they will be minted again next beat.

The two tests around this (`tests/test_background_react.py:444-508`) cover
manager-silent-plus-routed and manager-voiced-the-routed-one. Neither covers
manager-voiced-somebody-else-plus-routed, which is the case that loses work.

`story/scene.py:1725-1728` states the fall-through as unconditional —
*"a line directed at one of them is withheld and falls through to
background_react"* — which is true only when the manager stayed silent.

#### 16. An interruption truncates every line the victim spoke this beat, including ones already delivered in full

`agents/loops.py:691-706`:

```python
victim = ctx.character_results.get(victim_id) or {}
cut_any = False
for prior in (victim.get("sequence") or []):
    if prior.get("type") == "speech":
        shortened = cut_short_speech(prior.get("text"))
        if shortened:
            prior["text"] = shortened
            prior["cut_short"] = True
```

`ctx.character_results[id]` is the MERGED result across every micro-round —
`agents/common.py:331` `merged["sequence"] = _list(existing.get("sequence")) +
_list(new.get("sequence"))`. So a character who spoke in round 0 and round 2
carries both lines, and an interruption declared in round 3 truncates **both**,
plus marks every action element in either round `interrupted: True`. Only the
line actually being cut into was interrupted; the earlier one completed, was
answered, and nobody touched it.

The delivery side compounds it: `deterministic_micro_perception` ran when the
victim spoke and appended the FULL text to every eligible observer's
`local_views` (`loops.py:725-728, 818-821`). Rewriting the stored sequence
afterwards leaves the committed record disagreeing with what the other minds
in the room were told they heard.

`Design.md:159` describes the intended behaviour precisely — *"`interrupts:
"<name>"` on a speech or action element says the beat landed DURING that
line"* — one line, the one being cut into.

#### 17. `_player_silence_note` uses a raw position lookup where the rest of the module uses the identity-tolerant one

`agents/character.py:463-466`:

```python
positions = (sc or {}).get("positions") or {}
here = positions.get(character_name(sh))
if not here or positions.get(player) != here:
    return {}
```

`positions.get(name)` is an exact dict hit. Sixty lines of `world/spatial_
identity.py:room_of` exist because it is not sufficient — the same key may be
stored under `identity.uid`, an alias, a different case, or a non-Latin fold —
and `agents/common.py:2643 character_room` wraps `room_of` over every one of a
character's scene keys because *"perception was previously blind to a
character whose position was stored under its uid … placing them in 'an
unspecified area' and leaking a false empty view"*.

`character_step` itself uses the tolerant resolver 50 lines later
(`character.py:2514`, `char_room = character_room(sc, sh)`). This one call
site does not, for either body it looks up — the character's or the player's —
so for a scene that keys either under a uid the note returns `{}` and the
signal is silently absent. `AGENTS.md`'s body-enclosure row is explicit about
this class: *"one being, one name … five separate defects here were a single
`==` between them."*

---

### Silent tolerance of empty, missing, or unknown values

#### 18. A bare `except Exception` deletes three navigational signals with no warning

`agents/character.py:1847-1864`:

```python
if here_rid:
    try:
        from world.spatial import visible_adjacent_rooms
        for item in visible_adjacent_rooms(scene, here_rid) or []:
            ...
    except Exception:
        seen_onward, seen_bearings = {}, {}
```

Any failure inside `visible_adjacent_rooms` — or in the loop body — silently
empties `seen_onward`, which is the sole source of `onward_exits_visible`,
`onward_bearings` and `visibly_no_way_through`. `visibly_no_way_through` is
the first key `_verdict` tests (`1238-1240` over the pack's ordered tuple),
and it is the sole gate on the `unentered` verdict (`1255`) that maze arm A11
was built around. The character's exits payload degrades to pre-A11 behaviour
and nothing is written to `ctx.warnings`.

Two smaller notes at the same site: `visible_adjacent_rooms` is already
imported at module scope (`character.py:62`, used at `2606`), so the local
re-import is redundant; and the `except` covers the import itself, so an
import error reads identically to a spatial failure.

#### 19. `character_step` never checks for the empty drive it reads every beat

`agents/character.py:2702-2704`:

```python
_psych = character_psychology(sh)
_psych["drive"] = effective_drive(_psych, _interior)
```

`effective_drive` (`story/character_schema.py:1406-1407`) returns
`{"essence": "", "expression": "", "taboo": ""}` for a sheet with no drive,
and the payload ships it. `CLAUDE.md` names this the engine's worst
authoring failure — *"`psychology.drive` empty is the worst of them … it
fails invisibly because `serves: "drive"` stays valid against an empty
drive"* — and `story/importers.py:538-557` contains the exact check
(`character_import_warnings`) that would catch it.

That check runs on the import path only. `character_step` is the one function
that reads the sheet on every single beat of every character's life, and it
has no equivalent. This is a known gap rather than a new one, recorded here
because this slice is where it would cost nothing to close: one
`ctx.add_warning` beside the assembly above.

#### 20. `_awareness_gated` is written by production and read by nothing but one test

`agents/character.py:2473-2476`:

```python
if awareness_of(chat["id"], character_name(sh)) in NON_AWAKE_GATED:
    return {"sequence": [], "speech": None, "action": None, "actions": [],
            "manifest": {}, "mind_model_updates": [],
            "_awareness_gated": True}
```

`grep -rnw _awareness_gated` over the tree: this line and
`tests/test_awareness.py:248`. The gate itself is correct and load-bearing —
`AGENTS.md`'s awareness row is right that a gated mind must run no step — but
the marker it stamps has no consumer, so nothing downstream, in the pipeline
drawer, or in `_engine_notes` can distinguish "this mind was asleep" from
"this mind declared nothing".

The same dict also omits `name` and `char_id`, which the normal return path
sets (`character.py:3384-3385`) and which
`_unanswered_question_note`'s speaker match (`371`) reads back off stored
variants. Harmless today because a gated mind says nothing; a latent
inconsistency in the one result shape that differs from every other.

#### 21. Two functions take a parameter no body reads

* `agents/character.py:755` `_barren_intent(active_annotated, stored_state)` —
  the body uses only `stored_state`. Called at `800` with
  `active_annotated`; `tests/test_no_quality_redo.py:120` passes `{}`.
* `agents/character.py:404` `_player_quiet_beats(chat_id, current_turn_idx,
  frame_id, chat, cap=8)` — the body uses only the first three and `cap`.
  Called at `3099-3100` with `chat`; `tests/test_unanswered_question.py:195`
  passes `None`.

Both are trivial. Both are the shape that makes a later reader believe a
dependency exists.

---

### Language-pack seam

#### 22. Six prompt appendices and most of the navigation payload's prose are English literals inside a pack-selected call

`character.py:3168-3169` selects the contract through the pack:

```python
_cprompt = character_prompt(payload, language=ctx.language).replace(...)
```

and then appends, unconditionally in English: CARRIED REPORTS (`3171-3187`),
DRIVE RUPTURE (`3192-3212`), RUPTURE — FORCED RESOLUTION (`3214-3227`),
CRISIS (`3229-3237`), TELL VARIETY (`3239-3245`), TELL PAYOFF (`3247-3254`).
The payload carries English prose on the same footing: `_verdict`'s
`unentered` override (`1257-1260`), its frontier-distance clauses
(`1276-1280`), the destination clauses (`2167-2173`), `only_way_onward`
(`2228-2232`), `_run_end_note` (`2287-2290`), `sprint_offers`' `ends_in`
(`2383-2385`), `_en_route`'s keys, and `speaking_now.sense`
(`2887-2895`).

The `ja` pack translates `_VERDICTS[i][2]` and `_REFRAIN_WORD_RE`
(`tools/build_japanese_pack.py:324-330`) — so a Japanese story receives a
Japanese verdict clause with an English sentence appended to it, and one whole
verdict (`unentered`) in English only. `AGENTS.md`'s language row asks that a
story-capable pack "never silently fall back to English guards"; here the
fallback is not silent so much as unavoidable, because the strings were never
routed through the pack in the first place.

---

### Notes that are NOT findings

* `_isolated_wave` / `_perceptually_isolated` (`loops.py:332-409`) are
  unreachable in production — `parallel_isolated_reactors` defaults to
  `False` and, per finding 10, cannot be set through the API. This is
  deliberate and documented at both ends (`loops.py:373-381`,
  `story/scene.py:1560-1567`), including the loose end the author chose to
  ship it with (`loops.py:340-348`). Recorded so a future reader does not
  "discover" it as dead code.
* `reaction_loop` filters reactors with a bare `int(rid)`
  (`loops.py:1012-1015`) while `interaction_loop` uses
  `normalize_character_refs` (`loops.py:417-420`). Not a defect:
  `llm/schemas.py:4388` int-coerces `flow["reactors"]` and
  `agents/director.py:731` recovers any name form from `reactor_refs` before
  that. Three readers of one field with three different tolerances, all
  currently correct.
* `_defer_to_focus` (`loops.py:196-223`) is nearly, but not entirely,
  subsumed by `_defer_to_unrun_reactor` (`226-262`), which runs first at both
  exits. It remains reachable for a `tom_triggers` character drawn in later by
  `_next_speaker_candidates` rather than present in the initial queue.
  Checked; kept.
* `_claimed_refs` logs quote bodies at INFO (`background.py:686-688`). The
  comment says instrumentation stays "in the LOGGER only" and explains why the
  previous file-probe was removed. Deliberate, and the logger is not an
  archive.
* `now_turn=getattr(ctx, "turn_idx", None)` (`character.py:2760`) resolves —
  `core/pipeline_context.py:275-277` defines the property. It is the only
  place in the module that spells it that way rather than `ctx.turn.idx`, and
  the `None` default would silently disable `_intent_is_live`'s 40-turn
  staleness gate for any caller passing a stub. No such caller exists today.

---

## Part 2 — what the code actually does, checked against the documents

Method as in `AUDIT_DIRECTOR.md`: each module's behaviour written from the
code, then compared against `Design.md`'s conformance rows, `AGENTS.md` §
"Character decisions or dialogue" / "Character psychology…" / "Background
(unregistered) presence reactions", and `docs/guides/PIPELINE.md`
§`character:<id>` / §`interaction_loop` / §`reaction_loop` /
§`background_react`. Verdicts: RIGHT / STALE / LOST.

### `agents/character.py`

**What it does.** One function of substance (`character_step`, 960 lines) and
~35 pure helpers around it. The helpers fall into five families:

1. *Self-continuity ledgers* — `_recent_self_lines` (own quotes off prior
   `director_resolve.dialogue_log`), `_recent_self_moves` (one selected
   conversational job per turn off immutable prior variants),
   `_self_line_refrain` (the reused opening/closing word), `_first_verbatim_
   repeat`, `_first_repeated_move` (move similarity plus a separate
   question-to-question comparison at `_REPEATED_ASK_THRESHOLD = 0.5`).
2. *Goal governance, read-side only* — `_annotate_fading` (an intention two
   thirds of the way to the dormancy sweep), `_annotate_project_drift`
   (`adrift` after 8 unserved beats), `_annotate_goal_currency`
   (`goal_reached` / `goal_held` after 12), `_merge_standing_intentions`,
   `_nonsteering_intention_refs`. All non-mutating; commit owns the ledger.
3. *Navigation over the character's OWN place graph* —
   `_destination_from_goals` (double gate: named by his own text AND holding a
   node for it), `_taken_adjacency` (doorways actually walked, minus
   disproven), `_hops_to` / `_toward_hops` / `_frontier_hops`, `_verdict` /
   `_appeal` / `_annotate_known_exits` (the exit reading), `_en_route`,
   `sprint_offers` (`sprint_reach` narrowed by remembered ground and a
   two-room worth floor), `_run_end_note`.
4. *Unbidden recall* — `_unbidden_trigger` (five stuck signals, absorption
   ceiling, rupture suppression, cooldown with `clear_seen` hysteresis and
   two-strikes suppression), `_unbidden_entry`, `_attach_unbidden`.
5. *Output grounding* — `_ground_observation_citations`, which re-anchors
   every evidence reference against the two disjoint namespaces actually
   delivered and zeroes or drops what it cannot ground.

`character_step` itself: consciousness gate → view/observation selection
(micro-view substitution collapses to one synthetic observation) → memory
context with absorption narrowing and optional unbidden substitution → lore
gated through `scrub_names_deep` → relationships and mind-models
frame-filtered by `is_recognized_in_frame` → the `_self` block → the
perception block (view, `here_affords`, annotated exits, `corridor_sight`,
`sprint_reach`) → decision block → one `_agent_json` call → deterministic
screens (recorded, never re-asked) → validation, normalization, tell
grounding, mind-model capping, event-id assignment, unbidden telemetry.

**Docs: STALE in one specific, recent way, RIGHT everywhere else.**

The information-boundary account holds. `AGENTS.md`'s psychology row —
*"transient state may use only the character's scrubbed current observations,
own sheet, own body state, and earned memory"* — is honoured by the payload
with the four exceptions in findings 1 and 4. Absorption spends exactly the
three ways `AGENTS.md` describes (`sheet_capacity` at `2670-2671`,
`cap_mind_model_updates` at `3378-3379`, the memory narrowing inside
`build_character_memory_context`). `steering_intention_ids`,
`active_hypotheses`, `worked_before`, `carried_reports`, `while_you_were_
offscreen`, `project_review` and the capacity ladder are all present and
behave as their rows claim.

What is stale is the repetition seam, in four places, all of them
`e629d60`-shaped:

| document | claim | status |
| --- | --- | --- |
| `docs/guides/PIPELINE.md` §`character:<id>` | "Verbatim, potential semantic-move, and spent-intention findings are combined into at most one review call. Only an exact line that survives that review feeds the stuck mind signal; a semantic move deliberately retained after review does not." | **STALE.** There is exactly one `_agent_json` call in `character_step` (`3262`). No review call exists. `_repeat_survived = bool(_repeated)` (`3342`) — the flag now means "a verbatim repeat was detected", not "it survived a review". |
| `AGENTS.md` § Character decisions or dialogue | "Semantic similarity opens one contextual review; it is not proof of bad repetition." | **STALE** in the same way. The second clause is still true and still the governing principle; the first names a mechanism that was deleted. |
| `Design.md:199` | "`_first_repeated_move` uses conservative lexical similarity only to open one bounded contextual review, combined with any exact-line or already-spent-intention finding. … A semantically similar move retained after contextual review is not marked as a stuck-mind signal." | **STALE.** Row is marked **Built** and its substance survives (`_recent_self_moves`, the ledger's turn-granularity, `steering_intention_ids`); the review sentence does not. |
| `Design.md:234` | "…and the character stage's decision-review retry each re-issue a full provider call" | **STALE clause** in a row whose subject (warning instrumentation for second calls) is otherwise correct. The repair ladder rungs it also names are intact. |

Per `CLAUDE.md` those rows should have been corrected in `e629d60` itself.
The replacement behaviour is fully documented — in the source, at
`character.py:3314-3341`, which is the best account of it that exists and
should be where the doc edits draw from.

One further doc/code mismatch, older: `PIPELINE.md` says the character step
receives *"its own interoception/body state"*. It does — `body_state` from
`vitals_of` (`2918-2922`) — and the comment beside it states the rule
correctly. Finding 4's `following.target_room` is the one field in that block
that is somebody else's.

### `agents/loops.py`

**What it does.** Three public entry points and one deterministic delivery
function.

`deterministic_micro_perception` is the delivery floor: per observer, it
builds one `spatial_rel_between` relation in `(observer, actor)` order, reads
that observer's card senses, and runs each of the actor's sequence elements
through concealment (`_conceal_from_targets_observer`), `_delivery_ok`, and a
`sense_adjusted(hear_level(...))` ladder that renders full / trace (contentless,
not even the gated label) / muffled (through the shared `_muffle_middle`, not a
second copy of the rule). Actions deliver the intent-free `observable` surface
only. It returns per-observer additions plus the `perceived_by` set that the
interruption check keys on.

`interaction_loop` orders the queue — untargeted band by standing want-urgency
plus seeded jitter, then spoken-to / acted-upon / present, then answer-debt
first, then the person being answered deferred out of the opening wave — runs
one speaker at a time (`wave_size` default 1), delivers micro-perception only
after the wave, evaluates the two early exits for the wave as a whole, defers
them while any summoned reactor has not run, and reports the deferred exit's
reason rather than whatever it ran out of.

`reaction_loop` is the flat contested phase: cap by `max_reactors`, drop
non-awake, one `character_step` per reactor from its `perception_act` view,
break on the first result needing Director resolution.

**Docs: PIPELINE.md and AGENTS.md are STALE; `Design.md` is RIGHT.**

`Design.md:159` ("A beat opens with one character, and causality builds")
describes the current code exactly, including why the wave was retired,
`initial_parallel_reactors` defaulting to 1, the three-band ordering, the
seeded jitter, declarative interruption, and both exits draining the summoned
cast. It is the accurate account.

`docs/guides/PIPELINE.md` §`interaction_loop` still presents the wave as the
stage's shape:

> **The first wave is simultaneous.** Everyone in the initial reactor queue is
> answering the same thing … So the first `initial_parallel_reactors` speakers
> declare blind: micro-perception for the whole wave is delivered only once
> every member has declared … After the wave, one speaker at a time,
> unchanged.

and closes with the justification `Design.md` says was superseded ("This
exists because the early exits end the beat, not the round, and the commonest
of them fires on any declared act with a target"). `AGENTS.md` § Character
decisions or dialogue carries the same framing — *"The first wave
(`initial_parallel_reactors`) is simultaneous in the FICTION: members declare
blind"*.

Both are technically satisfiable at N=1 ("the first 1 speakers declare
blind"), which is how they survived; read as prose they tell the next
maintainer that a shipped default is simultaneous when it is sequential, and
that the wave is why stranding is fixed when the gating of
`commitment: "contestable"` plus `_defer_to_unrun_reactor` is why. The code's
own 39-line ONE AT A TIME comment (`loops.py:600-637`) is, again, the correct
account.

Everything else checks out: `_requires_director_resolution` as the commonest
exit and its narrowing, `max_micro_rounds` as the real bound, the asker
stepping out of the wave, "parallel in the FICTION, not in execution" (the
wave loop at `802-806` is a plain `for`), and the reaction loop's single-cap
docstring (`981-1008`) which correctly records that the second cap was
removed.

`PIPELINE.md`'s claim that `flow.reactors` "is *also* `perception_act`'s
entire perceiver list" is outside this slice but is what makes finding 14 and
the reactor-normalization spread worth watching: three modules read that field
with three tolerances.

### `agents/background.py`

**What it does.** Two paths behind one step key, chosen by
`background_config.scene_life`.

`off` — `pick_background_reactors` (deterministic, LLM-free, in
`persist/commit_background.py`) returns up to `max_reactors` names, forced
past the cap for a flow-addressed or `routed_to_background` presence; each
gets one `_react_one` call with a place block, its harvested sketch, an
earshot-filtered beat, an `addressed_by` line (fresh or a one-beat
`pending_reply` debt), the filtered player declaration and recognition-gated
`present_others`. Output is at most one line and one action; the stage writes
nothing.

`ambient` / `full` — `managed_presences` builds the roster from the tracked
ledger inside `ambient_scope`, excluding roster names and anything
`_presence_speech_verdict` does not call a person; `_manager_events` admits
dialogue with per-presence audience tags (fail-closed on an unplaceable
speaker, and at `ambient` refusing any event whose audience diverges);
`_redacted_resolved_event` strips concealed quote bodies; `_prose_shared`
withholds the prose unless every managed presence stands in the player's room;
`_mint_blurbs` batches blurb creation per ROOM; post-validation drops
unmanaged names, duplicates, and anything reproducing withheld content, and
records novel proper nouns as claims rather than facts.

**Docs: RIGHT on the manager's admission control, and it is genuinely
well-built. Three gaps against the documents, all recorded above.**

| document | claim | status |
| --- | --- | --- |
| `docs/design/BACKGROUND_LIFE_DESIGN.md:133-135` | "The beat is perception-filtered (`_beat_for_presence`, `_filtered_player_declaration`): concealed lines dropped, unhearable lines dropped by `hear_level`" | **Overstated.** True of `_beat_for_presence`; `_filtered_player_declaration` has no `hear_level` and no room test (finding 3). |
| `story/scene.py:1725-1728` (`background_config` docstring) | at `ambient`, "a line directed at one of them is withheld and falls through to background_react" | **Conditional, not stated as such.** The fall-through requires the manager to have produced no reaction at all; a manager that voiced somebody else keeps the beat and the withheld directed line is answered by nobody (finding 15). |
| `agents/background.py:1-34` (module docstring) and `PIPELINE.md` §`background_react` | both name `pick_background_reactor` (singular) as the gate | **Cosmetic.** The plural is what runs (`background.py:56, 262`); the singular survives as a one-line wrapper (`commit_background.py:1008`) with real callers in tests. PIPELINE.md's own `max_reactors` paragraph is correct. |

`AGENTS.md`'s background rows are otherwise accurate and were checked clause
by clause: the forced hand-off for a directly-addressed or
`routed_to_background` presence, the this-beat seeding of a presence minted
this beat, `_at_post_within_earshot` scoping at-post by `hear_level` rather
than room equality, and the positions-ledger keying. One nuance the row's
parenthetical understates: *"Perception always modelled this
(`_beat_for_presence` runs the same check before handing a presence a word of
the beat)"* — the dialogue path does run `hear_level`, but the prose
fall-through is gated on exact room equality (`background.py:188`), so a clerk
one open doorway from the bell is now correctly PICKED and still receives no
beat prose. That is defensible (prose is the omniscient frame) and worth
saying out loud in the row, because the two halves of "the same check" are not
the same check.

`Design.md:327`'s subsystem row ("one stateless reaction per beat each …
`max_reactors` defaults to 1 and is hard-clamped to 3 … each extra reacts to
the same beat blind to the others") is **RIGHT**, verified at
`background.py:260-292`.

### Cross-document verdicts, summarised

| document | verdict |
| --- | --- |
| `Design.md:159` (a beat opens with one character) | **RIGHT** — the most accurate account of `interaction_loop` in the maintained set |
| `Design.md:199` (a conversation remembers the job it already did) | **STALE** — the contextual-review sentences describe a call removed in `e629d60` |
| `Design.md:234` (a second model call says it happened) | **STALE clause** — "the character stage's decision-review retry" no longer exists |
| `Design.md:228` (unbidden recall), `Design.md:327` (background presence) | **RIGHT** |
| `AGENTS.md` § Character decisions or dialogue | **STALE twice** — the contextual review, and the first wave described as the shipped behaviour |
| `AGENTS.md` § Character psychology / capacity / theory of mind rows | **RIGHT** — every clause checkable from this slice was located and matches |
| `AGENTS.md` § Background (unregistered) presence reactions | **RIGHT**, with the earshot nuance above |
| `docs/guides/PIPELINE.md` §`character:<id>` | **STALE** in the dialogue-continuity paragraph; RIGHT elsewhere |
| `docs/guides/PIPELINE.md` §`interaction_loop` | **STALE** — describes the retired simultaneous wave as current |
| `docs/guides/PIPELINE.md` §`background_react` | **RIGHT** |
| `docs/design/BACKGROUND_LIFE_DESIGN.md` §"Reaction" | **Overstated** on `_filtered_player_declaration` |

Nothing in this slice was found built-and-quietly-lost in the
`AUDIT_SPATIAL.md` F1 sense — every mechanism the maintained docs claim for
these three modules was located and is reachable. The reachability exceptions
are the two deliberately shelved ones (`_isolated_wave`, and
`initial_parallel_reactors` as a knob with no writer — finding 10), the five
dead config keys (finding 9), and the one dead function `e629d60` left behind
(finding 6).

---

## Unverified suspicions

Listed separately because each would need a measurement or a live corpus read
this audit did not do.

* **`_first_repeated_move`'s question comparison may be double-counting a
  multi-round beat.** `_recent_self_moves` records one entry per TURN
  (`character.py:242-243`, loop result wins), but within a turn a character
  may speak in several micro-rounds and `_speech_texts(result)` on the merged
  result returns all of them. Whether the merged `asked` list makes a
  two-round exchange look like a repeated ask needs the stored corpus to say.
* **`_mint_blurbs` seeds on `ctx.turn.idx` rather than `nonce`**
  (`background.py:746`), unlike every other call in the slice. A reroll of the
  same turn should therefore re-mint an identical blurb. Whether that is
  intended (a blurb is frozen characterization) or an oversight is not
  recoverable from the code or its comment.
* **`_ground_observation_citations`'s `"no delivered present observation was
  cited"` warning** (`character.py:1006-1008`) fires only when `current` is
  non-empty and `present` is empty. Its rate across the stored corpus would
  say whether it is a live signal or wallpaper; `tools/fire_rates.py` is the
  instrument, and `AGENTS.md` asks for the denominator before anyone enriches
  it.
* **The `awaiting_your_answer` note's own fire rate.** Finding 14 predicts it
  is structurally zero on `autonomy == 0` chats; measuring it against beats
  where a question was in fact outstanding would confirm the gap and size it.
