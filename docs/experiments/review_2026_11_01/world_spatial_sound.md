# Audit — `world/spatial_sound_field.py`, `world/spatial_senses.py`, `world/spatial_listener.py` (2026-11-01, tree at `84f3de23`, clean)

Every `path:line` is the current working tree (these three files are not part of
the split in flight; `agents/*` lines are cited at `84f3de23`). Snippets ran on
`.venv/bin/python` with `ENGINE_DB` pointed at a scratch file; live scenes were
read from `engine.db` with `?mode=ro` (145 `world.scene` rows, 1,093 rooms).
One focused test file was run: `tests/test_sound_field.py` — 82 passed.
Scripts are in the scratchpad (`sound_corpus.py`, `no_grid_far*.py`,
`air_leak.py`, `field_for_gate*.py`, `reciprocity*.py`, `soundflood_brute.py`,
`cache_stale.py`, `sound_prof*.py`, `cache_key_cost.py`).

## Scope read

- **Read in full, in order:** `world/spatial_sound_field.py` 1–5381;
  `world/spatial_senses.py` 1–2485; `world/spatial_listener.py` 1–782.
- **Read in part, to trace a finding:** `agents/composer.py@84f3de23`
  `line_hear_level` 723–870, `ambient_percepts` 3127–3215,
  `distant_sound_percepts`, `_sound_bearing_phrase` 1850–1865;
  `agents/perception.py@84f3de23` 4575–4592, 6170–6250, 7880–7925;
  `agents/common.py@84f3de23` 7860–7935, 12690–12712;
  `world/spatial_frames.py@84f3de23` 520–560; `world/charter_runtime.py`
  3395–3445; `persist/commit_scene_state.py@84f3de23` 680–720;
  `world/spatial_fov.py` 294–318 (`room_has_geometry`), 1770–1815;
  `world/spatial_light_field.py` 259–289 (`light_geometry_exists`);
  `world/spatial_barriers.py` 902–942, 1012, 1095–1125; `world/weather.py`
  675–750; `world/scene_memo.py` 1–100; `world/crowds.py` 30–60, 239–260;
  `story/character_schema.py` 940–985; `llm/schemas.py` 1830–1850;
  `story/plot_packages.py` 3345 (the planner's room/edge card); both packs'
  `senses_note.txt`, `encoder/sensory_events.txt`, `encoder/entities__emits.txt`;
  `tests/test_sound_field.py` 113–150, 1721–1760;
  `tests/test_a_window_onto_a_room_is_no_way_through.py` 1–60;
  `docs/design/DESIGN_SOUND_FIELD.md` §§ 11.2–11.4 and every "owner's
  questions" subsection; the register entries cited below; `AGENTS.md`
  rows naming these modules.
- **Skimmed, not audited:** the rest of `spatial_fov.py`, `spatial_barriers.py`,
  `weather.py`, `composer.py`, `perception.py`.
- **Registers grepped for every finding:** all ten `docs/UNBUILT*.md`.

## Findings

### F1 — A listener whose room has no grid gets no `air` and no far field: the by-name rescue delivers lines through walls, and rooms-away voices fall back to "a shout carries through everything"

**Severity: LEAK (and over-gating in the other direction). Confidence: CONFIRMED (live corpus, real composer function).**

`world/spatial_sound_field.py:3443-3456`:

```python
if sound is None:
    sound = sound_field(scene, observer, room=observer_room)
if sound is None or sound.locate(observer, observer_room) is None:
    ...
    if rel.get("frontier_join"):
        _stamp_far_path(scene, rel, ...)
    return rel
```

Everything stamped below that return at `3462-3470` — `air`,
`far_loss_db`, `far_muffled`, `floor_db` — is a **room-graph** fact
(`far_path`, `_rooms_joined`, `rooms_adjacent`, `quiet_floor`) that needs no
cell grid. But `sound_field` returns None whenever the listener's room fails
`_room_grid_exists` (no size tier, extent or anchors): **440 of 1,093 live
rooms**. For those listeners:

1. `agents/composer.py@84f3de23:844` — `if rel.get("air"): return base` — never
   fires, so a line that NAMES the listener and that the hearing table grades
   `none` is rescued to `full` as "a transmission by device". Measured over the
   live scenes: **693** joined body pairs with a gridless listener; in **492** of
   them a named normal line (and a named loud line) the table refuses is
   delivered `full`; with `air` stamped the same lines stay `none`. Example:
   chat 2, `Alex Rivera` in `main_corridor` speaking to `Marcus Boyle` in
   `room_1A` through a **wall**. This is exactly the class the `air` stamp was
   built to close ("a shout three rooms up a stone tower delivered verbatim",
   composer's own comment), surviving for 40% of rooms.
2. Rooms-away pairs keep the edge model's `separated` row (shout = fragment,
   everything else none) instead of the far field: over **458** live pairs (10
   chats) the as-built verdict hands a shout a fragment the far field says does
   not arrive in **358**, and denies a line the far field delivers in 60
   (normal), 79 (loud), 79 (shout).

Fix: stamp the room-graph keys (`air`, `far_*`, `floor_db`) before the field
gate, whenever both rooms resolve; keep only the cell-dependent stamps
(`open_air_loss_db`, `paces`, `din_db`, `masking_db`, `doorway_air`,
`speaker_turned_away`) behind it. This changes no-geometry scenes, so the pin
`tests/test_sound_field.py:113` (`rel == {same_room, barrier, distance,
light}`) moves — the owner's call. Test: two rooms with no size/extent/anchors
joined by a wall; a named normal line → `line_hear_level == "none"`; a
three-room chain with no sizes → `rel["far_loss_db"]` present.

Related register: UNBUILT_PERCEPTION § 1.121 / § 1.129 (the addressed rescue's
premise). The `air` gate is the landed answer; this gap in it is not registered.

### F2 — The world side of the deaf-card seam: no sound reader in these files can be told the listener's card

**Severity: LEAK (the same defect as `agents_perception.md` F1, seen from this side — count once). Confidence: CONFIRMED (signatures read).**

Every function here that decides what reaches an ear takes no `senses`:
`heard_events` (`spatial_sound_field.py:3547`), `distant_sounds` (5026),
`sound_shape` (5227), `sound_fill` (5335), `SoundField.level_of` (2560),
`spatial_listener.heard_at_ear` (651), `ear_adjusted_db` (635),
`movement_heard_at_ear` (664). The module that models "the listener's state"
— `stamp_listener_ear` (`spatial_listener.py:497-515`) — stamps covered ears,
own noise and a blast's shift, and nothing from the card; the card's hearing
acuity is applied only by callers via `spatial_senses.sense_adjusted`
(`spatial_senses.py:2438`), which perception does for bodies and lines only.
So two representations of one fact — "how well this listener hears" — exist
(the card's `acuity`, the ear ledger), and only one reaches sounds, events,
far sounds, the soundscape and movement.

Fix (class): give the ear state a card term — `deaf` an infinite shift,
`dulled` a threshold shift, `keen` a negative one — stamped by
`stamp_listener_ear` and read by `ear_adjusted_db`/`ear_level`, so every reader
that already goes "through the listener's ear" honours the card in one place.
Test: a deaf card in a room with a running `loud` thing, a beat event in the
next room and a far `thunderous` event → `heard_events`, `distant_sounds`,
`sound_fill` all empty; `felt_vibrations` unchanged (touch).

### F3 — Both floods keep one label per room under a cost that is not separable: the voice flood is not reciprocal and both miss better paths

**Severity: WRONG-SCENE (over-gating). Confidence: CONFIRMED (randomised + brute force + live corpus).**

`_voice_flood` (`spatial_sound_field.py:4830-4927`) prices a way as
`source_db - barrier - max(spreading(free), ONE + DROP + couple - held)` and
keeps ONE record per room (`best[other]`, `state[other]`, 4917-4925). Its
docstring (4851-4852) promises "the answer from A to B is the answer from B to
A". The objective is a max of two accumulated sums, so the label kept at an
intermediate room is not always the one that is best further on.

- 400 random graphs (4–8 rooms, mixed barriers/exposures/surfaces/ducts/far
  ways): **117** asymmetric room pairs (109 numeric, 8 reached one way only),
  median 2.1 dB, max **24.2 dB**. Brute force over simple paths, trial 297:
  flood `r2→r5` = 4.97 dB, best path `r2→r0→r5` = **29.16 dB**; flood
  `r5→r2` = 29.16. A shout one way is a voice under the floor, the other way it
  is whole.
- Live scenes: of **4,430** rooms-away pairs the voice flood reaches, **97** are
  asymmetric and in **67** a normal line's word differs by direction (chat 150:
  `breakwater`↔`clinic_front` 36.0 vs 41.2 dB → `none` vs `fragment`).
- `room_sound_flood` (the sound flood, 4763-4826, "label-correcting ... a room
  is re-expanded only on a strict improvement") has the same flaw: 19 of 3,751
  records below the best simple path, worst **14.2 dB** short.

`far_path` floods from the SPEAKER's room, so which body hears whom depends on
who spoke. Fix: Pareto labels per room (free span, couple−held, indoors) or,
the permissive reading the module takes elsewhere, the louder of the two
directions in `far_path`; for the sound flood, labels per (room, length band).
Test: the reciprocity property over random graphs (`_voice_flood(a)[b] ==
_voice_flood(b)[a]`) and a brute-force optimality check on small graphs.

### F4 — A window whose `material` is `glass` is acoustically a wall

**Severity: WRONG-SCENE (over-gating). Confidence: CONFIRMED (live chat 172).**

`spatial_senses.py:1198` gives `"glass": -1` and `_material_shifted_barrier`
(1224-1236) walks `window` one rung "more solid" on `_SOUND_LADDER` (1212) — to
`wall`. The step exists for a door made of glass (`closed_door` → `window`);
on a window it counts the pane twice. The planner's own card invites it
(`story/plot_packages.py:3345`: "material? ... stone, metal or glass hardly
does"), and the engine's own fixture writes it
(`tests/test_a_window_onto_a_room_is_no_way_through.py:23`). Live: chat 172 has
**six** window edges with `material: glass` (`garden`↔`hinami_room`,
`meditation_room`, `roost`). Through them:

```
loud   window: fragment | window+glass: none
at the pane (within_reach): normal fragment→none, loud full→none, shout full→fragment
```

and worse: `_pair_reach` (818) only stamps `within_reach` for a shifted
`window`, so the at-the-pane rows are unreachable; `sound_passes`/
`_aperture_pass` (1581-1611) gives `wall` a pass of 0, so the garden is not laid
on the bedroom's acoustic grid at all (no near-field sound through the window);
the far field charges `WALL_LOSS_DB` 45 instead of 28 (`_edge_loss_db`, 4319).

Fix (class): a material that names what the barrier class already IS shifts
nothing (glass on a window, cloth on a curtain) — a per-class baseline in
`_material_shifted_barrier`. Test: window+glass hears exactly as a bare window
in `hear_level`, `_pair_reach`, `sound_passes` and `_edge_loss_db`.

### F5 — `SoundField._field_for` gates on the narrow FOV opt-in, so the speaker's own noise is never stamped across rooms

**Severity: WRONG-SCENE (over-gating). Confidence: CONFIRMED (live gate counts + reproduced verdict).**

`spatial_sound_field.py:2388`: `if room_has_geometry(self.scene, room_id):`
— the FOV furniture opt-in (an anchor with an authored height). `sound_field`
itself gates on `_room_grid_exists` (3088), widened 2026-09-06 (UNBUILT_LIVING_WORLD
§ 1.137); `_field_for` (added 2026-09-05, `775da04e`) was not. Live: **479** of
1,093 rooms have a field by the wide gate and none by the narrow one. Every
cross-room pair whose speaker stands in such a room gets no `speaker_din_db`
(3523-3527) and no `speaker_masking_db` (3533-3537), so the speaker's voice is
never Lombard-raised (`_din_voice_db` 1391-1396, `_masked_voice_db` 1360-1365,
`spatial_listener.voice_at_ear_db` 560-566). Reproduced: two rooms with size
tiers, an open doorway, "a few dozen" in each; a normal line to its addressee
7.4–9.8 paces off grades `none` (`din_beyond_reach`); with the speaker's din
stamped, `fragment` — the class the din rule documents ("raised over the din
where its SPEAKER stands").

Fix: use `_room_grid_exists` in `_field_for` (better: build siblings through
`sound_field(...)` so they are shared — see E6). Test: the two-tavern case above
asserts `speaker_din_db` present and `fragment`.

### F6 — The hearing table prices a curtain as a shut door and glass at 35 dB; the module's own budget disagrees on nine cells

**Severity: WRONG-SCENE (over-gating). Confidence: CONFIRMED (table vs `_voice_path_loss_db`, every cell enumerated).**

The rule's stated justification is that "every entry is the answer a decibel
budget built from real hearing gives with margin" (`spatial_senses.py:1251-1255`).
`DOOR_REACH_BARRIERS = ("closed_door", "membrane")` (1221) sends a curtain
through the shut-door branch (1808-1815), whose arithmetic is the door's 25 dB;
`APERTURE_DB["membrane"]` is 5 (`spatial_sound_field.py:514`). The window
branch (1817-1835) is written for 35 dB ("60 less some 35"); `APERTURE_DB`
says 28. Grading the same relation with the module's own path budget
(`_voice_path_loss_db`, which the masking, tone and ear budgets all read):

```
membrane nobody at it  normal  table fragment  budget +12 dB full
membrane door_reach    whisper table none      budget  +3 dB full
membrane door_reach    mutter  table none      budget  +6 dB full
membrane within_reach  whisper/mutter none / normal fragment   budget full
window   within_reach  normal  table fragment  budget  +5 dB full
window   nobody at it  normal  table none      budget -11 dB fragment
```

(Shouts through glass capped at `fragment` are the documented "low half"
clause, not counted.) The design note's § 11.3 table carries the same rows
("a shut door or curtain"), so the fix is the owner's: give `membrane` its own
row (an opening's breath-by-reach and a full voice) and price glass at
`APERTURE_DB`, or let the table read the budget it cites. Test: parametrise
`hear_level` against `_voice_path_loss_db` over every barrier × reach × volume.

### F7 — `can_perceive_onset` never asks the far field, so the planner refuses a target who hears the line whole

**Severity: WRONG-SCENE (over-gating at the planning gate). Confidence: CONFIRMED.**

`spatial_senses.py:491-497` grades the ROOM-level `spatial_rel` (no body
stamps, no `far_loss_db`): rooms beyond the next are `separated`, so only a
shout passes. Its callers decide who is asked what they do
(`agents/common.py@84f3de23:7928` `acted_upon_cast`, `agents/director.py:2510`).
Reproduced on a chain of small rooms with open doorways: cast in room `c`, two
doorways from the player: `can_perceive_onset(a, c) == False` while
`spatial_rel_between` + `hear_level` delivers the player's normal line `full`
(far loss 29 dB); in `d`, `fragment`. The function's own docstring says a gate
too tight "is invisible -- the character simply says nothing and reads as
incurious -- so the tie goes to letting them answer".

Fix: for rooms the room graph joins beyond the next, stamp the room-level
relation with `_stamp_far_path` before `hear_level(rel, "normal")`. Test: the
three-room chain → `can_perceive_onset(a, c)` True.

### F8 — On a still night outdoors the sound flood is cut 3 dB above what the listener can hear

**Severity: WRONG-SCENE (over-gating, distant sounds). Confidence: CONFIRMED.**

`_inaudible_everywhere_db` (`spatial_sound_field.py:4627-4635`) lowers the
flood's cut only for rooms declaring `quiet`. The still-night hush that
`_ambient_floor` (2303-2305) and `quiet_floor` (2994-3000) apply to open rooms is
missing, though the comment above it (4601-4615) says the cut is "the quietest
floor THIS SCENE has". Measured: open room, night, no wind: listener floor
23.98 dB, its gate (`_gate_db`) 23.98, the flood's cut **26.99**; arrivals at
24.5–26.9 dB grade `faint` in `distant_level_word` but never leave
`room_sound_flood` (4807, 4814). Same loss in `charter_runtime.py:3425`.
(`_voice_inaudible_db`, 4638, does include the hush — the two cuts disagree.)
Fix: take the cut as the minimum `_gate_db(_ambient_floor(...))`-style floor
including the still night. Test: still-night open scene, a sound arriving at
25 dB → `distant_sounds` returns it `faint`.

### F9 — The senses and event-kind vocabularies read free prose with English token lists, misreading ordinary phrasings both ways

**Severity: WRONG-SCENE (language-pack hazard; both directions). Confidence: CONFIRMED (snippet).**

`sense_acuity_offset` (`spatial_senses.py:2397-2417`) tokenises `acuity` with
`[^a-z]+` and matches `_ACUITY_*` sets (2294-2309); `_sense_channel`
(2321-2340) does the same with `_SENSE_CHANNEL_ALIASES`; `sense_range_class`
(2420-2435) with `_RANGE_*`. The card note tells the model `channel` is "the
fiction's own word" and `acuity` free text (`senses_note.txt`, both packs).
Measured:

```
hearing "high-frequency hearing loss" -> +1 (keen)          adds capability
hearing "deaf in one ear"             -> None (fully deaf)
vision  "blind in one eye"            -> None (fully blind)
hearing "ordinary, nothing lost"      -> None (deaf)  ("lost")
hearing "none"                        -> None (deaf)
hearing "hard to fool"                -> -1
range   "not far" / "never far"       -> extended
聴覚 / 鋭い, 聞こえない                  -> channel None -> ordinary
```

The same reader decides whether a beat's event is a SOUND
(`_is_sound_event`, `spatial_sound_field.py:1838-1844`, on the event's free
`kind`, kept verbatim by `normalize_sensory_event` 4143); the ja encoder card
describes `kind` in Japanese with no closed set, so `kind: "音"` is dropped from
the field — not heard next door, not far, not felt, no masking even with
`drowns: true`. (Live corpus kinds today: sound 22, smell 1, sight 1.) The edge
`material` table (`_MATERIAL_SOUND_STEPS`, 1187-1202) is the same class as the
registered floor table (UNBUILT_WORLD § 1.209): 116/116 live materials match
today, all English; "紙" would leave a shoji a solid door. Fix (class): closed
sets the engine owns, stated on the cards as `level` and `barrier` are —
`acuity` (absent|dulled|ordinary|keen|extraordinary), event `kind`
(hearing|sight|scent|touch), edge `material` — normalised at ingest
(`character_card_warnings`, `normalize_sensory_event`). Test: the table above
as a parametrised test against the normaliser.

### F10 — Breath privacy and conversational reach are measured in the duct's acoustic paces

**Severity: WRONG-SCENE (over-delivery; PLAUSIBLE as a defect — the owner may intend it). Confidence: CONFIRMED (mechanism).**

`_pair_paces` (`spatial_sound_field.py:2815-2840`) returns the flood's path
length, which `spread` scales by `DUCT_STEP` 0.5 inside a duct (1723). That
number is compared with body distances: `WHISPER_REACH_PACES`/
`MUTTER_*_PACES` (`spatial_senses.py:1447-1453`), `CONVERSATION_REACH_PACES`
(`_in_a_din_beyond_reach` 1584; `_speaker_turned_away` 2956). Reproduced: two
bodies 4 cells apart in a 2×12 corridor → `paces` 2.0, whisper `full`, mutter
`full`; in a 6×12 room → 4.0, `none`/`fragment`. "Arm's reach" doubles down
every corridor. Fix: stamp the body path length unscaled for the reach rules
(keep the scaled length for `spreading_loss_db`). Test: the corridor pair.

### F11 — `_under_the_sky` reads the raw `exposure` field; every other reader asks `weather.room_exposure`

**Severity: WRONG-SCENE (latent: 0 vertical edges affected in the live corpus today). Confidence: CONFIRMED (divergence measured).**

`spatial_senses.py:2103-2111` treats any declared word other than `enclosed`
as sky and an absent field as `enclosed`. `weather.room_exposure` derives
(parent_entity → enclosed; declared; keyword fallback). Live: **118** rooms
with no declared exposure that `room_exposure` calls open/sheltered read as
enclosed here, and 3 rooms declared `indoor`/`interior` read as UNDER THE SKY
(the sight cap at 935-936 then answers "full ... no wall, no floor"). Two
readers of one fact. Fix: call `weather.room_exposure`. Test: a vertical edge
between a keyword-open square and a porch; a room declared `indoor`.

### F12 — The field caches hold scene objects: a content hit reads a mutated scene, and the identity caches outlive any read pass

**Severity: WRONG-SCENE (PLAUSIBLE — no production in-place mutation between two reads was found). Confidence: CONFIRMED (mechanism, snippet).**

`_sound_field` (3097-3112) is keyed on content but stores the `SoundField`,
which keeps `self.scene` and reads it at query time (`locate` 2366-2375,
`masking_db_at`, `_field_for`). Built on S, S mutated in place, then asked
with a fresh object holding S's ORIGINAL content: the hit returns the old
field, `field.scene is S`, and `locate("L")` answers the mutated cell (4,4)
while the asking scene says (0,0). `_FAR_GRAPH_CACHE` / `_FAR_WAYS_CACHE`
(4498-4519, 3262-3305) are module-global identity memos — the pattern
`world/scene_memo.py:23-30` names as unsafe — and they outlive passes: a
doorway turned to a wall in place on the same object keeps its far loss at
39.0 dB where a fresh copy says 74.0. Fix: move both under `scene_memo`
(born and dying with a pass) and never return a cached object that carries a
scene reference (rebind or key per object). Test: the two snippets above.

### F13 — A card's sense `range` does nothing

**Severity: SILENT-NOOP. Confidence: CONFIRMED (git grep).**

`sense_range_class` (`spatial_senses.py:2420-2435`) has no production caller
(5 test calls); no other reader touches a sense's `range`. Every generated card
writes `"range":"ordinary"` and the senses note calls it "how far". Its
docstring ("Consumers pass sound_walk_level a bigger max_hops for `extended`")
and UNBUILT_PERCEPTION § 1.146 ("the consumer widens `max_hops` for
`extended`") both describe a consumer that does not exist. Fix: wire it (as a
dB envelope, per § 1.146's own note) or say on the card that `range` is unread.

### F14 — The sound field builds failure notices nobody reads, and says the Director hears them

**Severity: DEAD (+STALE-DOC). Confidence: CONFIRMED.**

`sound_sources` formats an English notice per failing source on every call
(`spatial_sound_field.py:2046-2051`); it lands on `SoundField.notices` (2329)
and `sound_notices` (2186-2195), neither read in production (test-only). The
real notice is filed by `persist/commit_scene_state.py@84f3de23:681-720` from
`failing_sound_sources_out`. The docstring at 2020-2025 still says these
notices reach the Director "through ... `ctx.engine_feedback`" (E16). Fix:
drop the notice list (keep the hash) and the stale paragraph.

### F15 — Unreachable code: two senses helpers, a speech guard and a crowd branch

**Severity: DEAD. Confidence: CONFIRMED (whole-repo grep incl. tests/tools).**

- `comms_reach` (`spatial_senses.py:449-459`) and `can_perceive` (1926-1927):
  no caller anywhere (only the facade re-export, `world/spatial.py:276-277`).
- `far_field_sources`' `if source.get("kind") == "speech": continue`
  (`spatial_sound_field.py:4964-4965`): `sound_sources` has emitted no
  `speech` kind since 2026-10-20 (its own docstring, 2015-2018).
- `room_holds_a_standing_source`'s crowd branch (5133-5135) reads
  `scene.get("crowds")` and `crowd.get("room")`: crowds live in world-KV
  `crowds` (`world/crowds.py:46`), never on a scene dict, keyed `room_uid`.
  A guard that reads a value nothing writes, twice over.

### F16 — Comments and docstrings that describe a model that no longer exists

**Severity: STALE-DOC. Confidence: CONFIRMED (each read against code).**

- `spatial_sound_field.py:28-36` — the field "exists ... only when the
  listener's room carries geometry (`room_has_geometry` ...)": the gate is
  `_room_grid_exists` since 2026-09-06.
- `:45-53` — "the one place noise decides a line, a deafening source's reach":
  the din (`din_level`) is a second since wave A.
- `:525` — `BARRIER_LOSS_DB` does not exist (it is `WALL_LOSS_DB`/
  `_edge_loss_db`). `:969` — `_masking_noise_db` does not exist.
- `:682-685` — "enclosed 27.0 | sheltered 30.0 | open 33.0": open is 30.0
  (`AMBIENT["open"]` 0.1 since 2026-09-05; the table at 562 is right).
- `:4235-4277` and `tests/test_sound_field.py:1732-1743` — "a real 45 dB wall,
  compressed, is 16", "a real 50 dB concrete floor is 18 here", "pins the mixed
  state": the losses are real (45/50, `APERTURE_DB` 25/28) and the test asserts
  `k = 1.0`.
- `:4740-4741` — `room_sound_flood` takes "a sound of `source_db` at one
  pace": every caller passes the level AT THE CELL (+3.01 dB: `SPEECH_DB`,
  `EVENT_DB`, `db_of_power(power)`), and the arithmetic treats it as such.
- `:2562` (`level_of` "or `speech:<name>`"), `:3068` (extras "speakers"),
  `:5104-5107` (`speech` kind), `:5181-5182` (`noise_at` "counts everything, as
  masking must" — it skips events and is not the masking floor since
  2026-09-25/10-20).
- `spatial_senses.py:700-711` — `spatial_rel_between` "carries `signal` ...
  and `noise` ... `hear_level` quantises those": neither is stamped since
  2026-10-20.
- `AGENTS.md:518` — "`spatial_rel_between` sets `rel["glare"]`": glare was
  removed 2026-09-16 (`spatial_senses.py:542-546`). `AGENTS.md:503` — lists
  `sound_source` faint|audible|loud|deafening (six rungs now) and the POWER
  tables as owner-set (the dB tables are; powers are derived).

## Efficiency

- **E1 — `_voice_flood`/`room_sound_flood` are recomputed per relation (hot, cheap fix).**
  `far_path` floods from the speaker's room on every `stamp_sound_relation`
  (`3462`); `_first_hop` runs a second, sound flood for a bearing (2905);
  `distant_sounds` floods per (listener × source) (5071) though the flood
  depends on the source only; `charter_runtime.py:3425` per (place × event).
  Measured on chat 167 (18 rooms, 9 bodies): two 72-relation sweeps ran the
  voice flood **72 times for 2 distinct source rooms**; `_voice_flood` was ~18%
  of the profiled sweep. A `scene_memo(scene, ("room_sound_flood", room, db,
  voice), ...)` collapses P×T floods to one per source room per pass; on the
  600-room maps the docstrings cite (41 ms a flood) it is the dominant term.
- **E2 — `stamp_listener_ear` re-derives the listener's whole attire entry per relation.**
  `garment_over_ears_db` → `attire.rederive_entry` (spatial_listener.py:178)
  runs for every (listener, target): ~17% of the warm sweep on chat 167, ~2.6
  ms a call on chat 172's scene. Depends on the listener only — memo per
  (scene, listener).
- **E3 — `spatial_rel_between` without `sound=` outside a read pass costs 11–13 ms a call** on the
  three largest live scenes (vs ~1.2 ms with a field): `sound_field` misses
  `scene_memo` and pays `_cache_key` (json.dumps + sha1 of the read set,
  0.5–0.8 ms) plus every geometry re-derivation. Callers: `pitched_level_db`
  (1217), background, loops, `commit_background`, `charter_observe`,
  `director_movement`. Open a `scene_read_pass` or hand a field.
- **E4 — Clear-all eviction.** `_SOUND_FIELD_CACHE` (64) and
  `_FAR_GRAPH_CACHE` (8) drop everything when full (3109-3110, 4507-4508);
  per-perceiver × with/without events × as-of moment worlds can exceed 64 in
  one outcome stage (PLAUSIBLE, not measured). LRU is a one-line change.
- **E5 — Per-listener whole-scene sweeps.** `far_field_sources` and
  `felt_vibrations` call `sound_sources` (every entity, room, crowd, event) once
  per listener; one call per beat would serve all.
- **E6 — Sibling fields are per listener field.** `_field_for` caches in
  `self._siblings`, so every listener's field builds its own composite for each
  speaker room; fixing F5 multiplies this unless siblings go through
  `sound_field()` (content-cached and shared). `spread` itself is Dijkstra
  O(C log C) per source cell with an O(W) wall scan per band crossing; fine.

## Already registered

- **UNBUILT_WORLD § 1.209** — a floor word `FLOOR_IMPACT_DB` (1915-1917) does
  not hold reads as masonry; `footfall_db` (3891-3905) cites it. Live floors
  include "gravel and clay", "metal", "cracked poured concrete", "earth",
  "gravel" (all → masonry).
- **UNBUILT_PERCEPTION § 1.146** — the hop-bounded walk's caps:
  `sound_walk_level` `max_hops=2` (alarm snap, `spatial_frames.py:548`) and
  `sound_bearing`'s non-adjacent arm `sound_path(max_hops=2)` (2177: a voice
  heard 3+ rooms off, or through a shut door, gets no bearing). Not named
  there: `earshot_rooms` (2-hop, `common.py@84f3de23:12707`, which rooms'
  bodies may be voiced) is the same second model of reach.
- **UNBUILT_PERCEPTION § 1.121 / § 1.129** — the addressed rescue's premise
  (F1 is the gap in the landed `air` fix).
- **UNBUILT_LIVING_WORLD § 1.137** — the near-field gate widening; the 440
  gridless rooms are its remaining "room nobody has described" (F1, F5).
- **Owner questions, OPEN — not decided here** (`DESIGN_SOUND_FIELD.md`):
  § 11.9 (household `loud` at 65; `ear` lines naming nobody; the read-back's
  two options; contact derivation); § 12.6 (conversational reach 2 paces; din
  at 57; babble by band and mood; informational masking; AV benefit 6 dB; tone
  rung 10 dB; breath has no voice rung; tone through a wall; stranger by
  register; footfall numbers; a room change is a walk; the pace clause);
  § 13.7 (waking 60 dB/10 out; names wake; only sleep; mass wakes by name;
  waking beat; own speech; garments; own-noise din; covering 20/27; blast 120;
  ear threshold 25; habituation; rain stops; own-name rescue; waking clause);
  § 14.7 (facing 8/3; facing at beat end; the unattended door; wind 60/70;
  addressee in a din; bend sizes; `wind_from` by model; open air across an
  opening; after-sight 0.3 s; felt numbers; storm in every view); § 16.7
  (`deafening` blow 105; a shot is `thunderous`; a room's own `sound` moved 28
  dB; household din; gale shout; indoor leg 6 dB; thunder's exclusion; far
  sound as standing state); § 17.5; § 18.4 (garment 10 dB; larger of two;
  whisper through a hood; empty voice; voice field floor; clauses need a run);
  § 19.3 (the ring; sight untouched; three readings of `far`; `remote` carries
  no loud event); § 20.6 (layout stair as three openings; stair 3 dB; holds
  count apertures; sounds keep the free field; an absolute intelligibility
  floor; source room's 6 dB drop; bodies absorb nothing). F6 is NOT among them.
- Cross-reference, not a register: `agents_perception.md` F1 (deaf card hears
  din — F2 here is its world half), F4 (one beat, two fields — `pitched_level_db`
  at 1217 and every `sound=None` stamp derive a third, without crowds/events),
  F5 (`_tell_acuity` vs `sense_acuity_offset` — the engine reader itself
  misreads, F9).

## Structure notes

- **Q1 — the 31 module-level mutable values have no runtime writer.** Whole-repo
  grep (prod, tests, tools) for `X[...] =`, `.update/.pop/.clear/.setdefault`,
  `global`, `monkeypatch.setitem/setattr` on every one: none outside their own
  definitions; no `global` statement in any of the three files; nothing reads
  settings. The only mutated ones are the three caches, mutated in place
  (`[]=`, `.clear()`) and never rebound: `_SOUND_FIELD_CACHE` (writers 3110-3111;
  readers 3100; a test clears it), `_FAR_WAYS_CACHE` (3303-3304),
  `_FAR_GRAPH_CACHE` (4508-4511). No story- or settings-driven override exists,
  so no cross-story corruption through the tables; the cross-chat reach is the
  caches' (F12: content-keyed hits are identical answers, but the stored object
  carries the first scene). `_QUIET_ALIASES`, `_DOOR_OPEN`, `TREAD_LEVEL`,
  `FLOOR_IMPACT_DB`, `ABSORPTION`, `WAY_LOSS_DB` likewise constant in practice.
  In `spatial_senses.py`: `_MATERIAL_SOUND_STEPS`, `_SENSE_CHANNEL_ALIASES` and
  the acuity frozensets — no writers.
- **Q2 — units and hidden caps** (names only; no numbers changed): `_DB_EPS`
  (1e-12) is a pure tie tolerance, not a cap. Real gates on audibility:
  `HEAR_FLOOR_DB` 27 (fragment for sounds and breath, taken with the room's
  noise); `_inaudible_everywhere_db` (sound flood cut — F8);
  `_voice_inaudible_db` (voice flood cut, floor − 22); `FAR_FIELD_ENTRY_DB` 70
  (a sound below it at its cell never walks the room graph; ring-boosted);
  `FAR_CLEAR_EDGE_DB` 25 (any heavier edge caps a far voice at `fragment`);
  `WHISPER_REACH_PACES` 2 / `MUTTER_REACH_PACES` 3 / `MUTTER_PIECES_PACES` 4;
  `CONVERSATION_REACH_PACES` 2; `DIN_DB` 57; `OVERWHELMING_*`; `sound_walk_level`
  2 hops (registered); `MAX_SENSORY_EVENTS` 8 (commit). Unit mixes found: paces
  vs duct-scaled length (F10); "at one pace" vs "at the cell" (F16,
  `room_sound_flood`); `noise_at`'s signal includes the wind bend while the noise
  does not (by design).
- **Q3 — apertures.** Every barrier read goes `normalize_barrier` →
  `_material_shifted_barrier`; readers of the doorway: `effective_adjacent`
  (passage-resolved: the far graph, the near-field placement) vs raw
  `room["adjacent"]` (`door_events._edge`, `_declared_edge`, `_next_door`,
  `far_field_way_paces`, `_edge_vertical`, `_declared_way_between`,
  `_overlook_between`). The raw readers take only `to`/`distance`/`vertical`/
  `way` except `door_events`, which reads `barrier` raw — safe while
  `spatial_merge.sync_scene_passages` copies a passage's barrier onto both
  edges, a second representation kept in step by one writer. Outside these
  files: `normalize_barrier("arch")` and `("passage")` return `wall` and
  `(None)` returns `open` — for the spatial_barriers auditor.
- **Q4 — every subtractive step on one line, source → listener:**
  `into_another_ear` (ear rung, identity) → [comm channel adds] → `hear_level`:
  `_graded_word`, `_facing_its_addressee` → `_hear_level` table (conducted
  flags; same room: breath by reach/paces, open air by distance + facing; far
  field loss + muffle; unknown/remote; opening: breath by reach default
  `near`; shut door/curtain; window/glass; wall/separated) → masking cap
  (`masked_level`) → din cap (`din_level`, beyond 2 paces, addressee known, no
  own noise) → ear cap (`ear_level`: cover, own noise, blast shift) →
  `_sense_graded` (card) → [compensation; by-name rescue adds]. Over-gating
  found at: the far-field gate (F1), the flood (F3), glass windows (F4), the
  speaker's din (F5), curtains/glass rows (F6), the planning gate (F7), still
  nights (F8), card words (F9).
- **Q5 — word tables.** Canonical (fine): `SOUND_LEVELS`, `SPEECH_VOLUMES`,
  `TREAD_GAITS`, `CROWD_SOUND`/`CROWD_BABBLE_DB` (keys = `crowds.BANDS`),
  `ABSORPTION`, `QUIET_SCALE`, `WIND_*`, `APERTURE_DB`, `MASKING_LEVELS`,
  `STANDING_SOURCE_KINDS`, `REVERB_WORDS`, `FELT_LEVELS`. Free prose matched by
  English: `_MATERIAL_SOUND_STEPS`, `_SENSE_CHANNEL_ALIASES`, `_ACUITY_*`,
  `_RANGE_*`, event `kind` via `_sense_channel` (F9); `FLOOR_IMPACT_DB`
  (registered); `_QUIET_ALIASES` (tolerance for a closed set the card states —
  minor); `_OFF` (tolerance for a boolean the card states — fine);
  `spatial_listener._is_a_pair`/`_ear_side` read contact-part prose for
  "both" and English plurals (fails toward an uncovered ear — minor).
- **Monoliths in miniature:** `SoundField` (281 lines), `sound_sources` (176),
  `stamp_sound_relation` (144; it carries two copies of the far stamp,
  3462-3467 and `_stamp_far_path` 3387-3398), `_voice_flood` (98),
  `room_sound_flood` (90), `distant_sounds` (69), `tread_events` (66);
  `spatial_senses._hear_level` (167) and `_opening_view_cap` (155).
- **Natural seams for a split of `spatial_sound_field.py`:** (1) denomination
  and ladders 89–1097; (2) voice budgets and quantisers 1153–1575; (3) the
  near-field grid and `spread` 1577–1776; (4) sources, reverberation and the
  event channel 1778–2312 + 3579–3606 + 4060–4190; (5) `SoundField` and its
  caches 2315–2600, 2981–3112; (6) open air, doorway, wind, facing 2602–2978;
  (7) far field — graph, floods, `far_path`, the relation stamp 3115–3544,
  4193–4972; (8) after-sight, felt, tread, doors 3609–4122; (9) distant sounds,
  shape and fill 4975–5381. `spatial_senses.py`: comms 97–501, sight 503–1173,
  hearing rule 1176–1928, hop walk and bearings 1930–2250, perceiver senses
  2253–2485. Two models of "how far a voice carries" live side by side (the
  hop walk and the floods) and feed different gates (F7, § 1.146).
- **Design observation, not a finding:** for same-room and next-room pairs the
  table and the tone/ear budgets grade against a fixed 27 dB (`floor_db` is
  stamped only for far and open-air pairs), so a room's declared `quiet` reaches
  voices only rooms away and under the sky.

## Docs checked

- CLAUDE.md "Perception is deterministic ... imports no model seam": these three
  files import no `llm`, provider or `core.db` — **held**.
- AGENTS.md "What a listener hears ... (the sound field)" (503): rows' symbols
  exist; "`sound_source` faint|audible|loud|deafening" and "owner-set
  `SPEECH_POWER`/`SOUND_POWER`/`APERTURE_PASS`" — **stale** (F16).
- AGENTS.md "Light on the grid" (518): "`spatial_rel_between` sets
  `rel["glare"]`" — **stale** (no glare since 2026-09-16).
- AGENTS.md "Whether a spoken line is heard": `hear_level`, `_breath_level`,
  `_pair_reach`, `door_reach`, `hearing_reason`, the `stamp_sound_relation`
  stamps listed — **held**; "the `air` gate on the addressed rescue" — held only
  for listeners with a grid (F1).
- AGENTS.md "conducted flags ... never stamped over" and "comms decide before
  `hear_level`": **held** (`_CONDUCTED` early return 3441; composer checks
  `comm_channel` first).
- AGENTS.md "A footfall heard below or beside", "the LISTENER'S own state",
  "Which way a speaker faces", "A sound heard after the sight ... loud sound
  felt": symbols exist and behave as described — **held**.
- `spatial_rel_between` docstring (senses 700-711) — **stale** (F16).
- `far_field_graph` docstring ("one beat's scene is one object ... mutated by
  nobody while it is being read") — true within a read, but the cache outlives
  it (F12).
- `_voice_flood` "the answer from A to B is the answer from B to A" — **does not
  hold** (F3).
- `can_perceive_onset` "the tie goes to letting them answer" — **does not hold**
  rooms away (F7).
- `_inaudible_everywhere_db` "the quietest floor THIS SCENE has" — **does not
  hold** on a still night (F8).
- `sense_acuity_offset` "free text never adds capability" — **does not hold**
  ("high-frequency hearing loss" → +1; F9).
- `sense_range_class` "Consumers pass sound_walk_level a bigger max_hops" and
  UNBUILT_PERCEPTION § 1.146's same claim — **no consumer** (F13).
- DESIGN_SOUND_FIELD § 11.3 table vs § 11.2 constants table (curtain ~5,
  glass 28) — **disagree** (F6).
