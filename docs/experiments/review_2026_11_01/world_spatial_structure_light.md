# Audit: world/spatial structure, identity, barriers, light, scent (2026-11-01)

Auditor scope: `world/spatial_substance.py`, `spatial_barriers.py`, `spatial_identity.py`,
`spatial_lint.py`, `spatial_bubbles.py`, `spatial_pack.py`, `spatial_prose.py`,
`spatial_contact_migration.py`, `spatial_levels.py`, `spatial_light_field.py`,
`spatial_light.py`, `spatial_scent_field.py`. Working tree = `84f3de23`, clean.
Line numbers are against that tree.

## Scope read

Read in full, every line:

| File | Lines |
|---|---|
| world/spatial_substance.py | 1-1198 |
| world/spatial_barriers.py | 1-1130 |
| world/spatial_identity.py | 1-923 |
| world/spatial_lint.py | 1-858 |
| world/spatial_bubbles.py | 1-674 |
| world/spatial_pack.py | 1-623 |
| world/spatial_prose.py | 1-410 |
| world/spatial_contact_migration.py | 1-332 |
| world/spatial_levels.py | 1-250 |
| world/spatial_light_field.py | 1-1482 |
| world/spatial_light.py | 1-855 |
| world/spatial_scent_field.py | 1-233 |

Honest limits: the packing search (`pack_anchors`, `_end_to_end`, `_full_lines`),
`leaf_rows`'s walk-order reasoning and the light field's shadowcast and bounce
arithmetic were read line by line. I did not re-derive them independently. My
findings there cover only what a snippet could confirm.

Read in part, to trace callers and consumers: `world/spatial.py` (the import
blocks), `world/spatial_merge.py:2240-2300`, `world/spatial_frames.py:1320-1400,
2090-2160, 2491-2560`, `world/spatial_senses.py:376-450, 2262-2285`,
`world/spatial_contacts.py:55-100, 975-1000, 1205-1245`,
`world/charter_space.py:40-75`, `world/charter_runtime.py:3465-3515`,
`world/scene_memo.py` (all), `story/scene.py:2385-2425, 2537-2555`,
`persist/commit_room_registry.py:40-255`, `persist/commit_mapping.py:148-215`,
`persist/commit_scene_state.py:160-192, 2740-2780, 2910-2935`,
`agents/character.py:3895-3912, 4270-4320, 4655-4700`,
`agents/perception.py:5320-5375, 6640-6680`, `agents/director_prose.py:1650-1700`,
`agents/mapping.py:255-290`, `agents/common_cast.py:580-605`,
`language_adapters/japanese.py:600-640`, `web/world_routes.py:405-440`,
`world/layout_bridge.py:555-585` (`DOOR_BARRIERS`), the cards
`encoder/rooms.txt`, `encoder/entities.txt`, `room_vocabulary.txt` and
`compositor.json` (en), `encoder/rooms.txt` (ja).

The corpus was read from `engine.db` opened `file:...?immutable=1`, which is
read-only and touches no -wal or -shm file. It holds 145 `world.scene` rows,
1,093 rooms and 118 contacts. **No Japanese story exists in the owner's db**:
all 91 `story_language` rows say "en". Every ja-pack finding below is
therefore latent on this corpus.

Tests run (2 of the allowed 6, `.venv`, serial):
`tests/test_senses_gate.py::test_ordinary_and_unlisted_are_byte_identical`
passed. `tests/test_charter_traversal.py -k shut_door_holds` passed. I ran both
to show that they pass while missing the defects in F13 and in "Already
registered".

Scratch scripts are in `S/wsl/`: `scan1.py`, `scan2.py`, `time1.py`,
`time2.py`, `time3.py`.

## Findings

Count: 16. By severity: LEAK 1, CORRUPTION 1, WRONG-SCENE 6, SILENT-NOOP 4,
DEAD 3, STALE-DOC 1.

### F1 — An enclosure label carries its owner's canonical name past the identity floor (LEAK)

**Where.** The renderer is in `world/spatial_prose.py`:
- `:28-56` `_interior_label` strips a leading possessive by the name it is given.
- `:119-123` `contact_phrase`'s interior branch uses the raw `target_interior`.
- `contact_sensation` relabels the other party at `:244` before it strips at
  `:295` and `:304`.

The engine itself writes a room's name into `target_interior`:
`world/spatial_contacts.py:1241-1242`
(`contact["target_interior"] = _contact_text(room.get("name") or inner)`).
The unscrubbed consumer is `agents/character.py:4283-4293`, which builds
`self.standing_contacts[].description` from `contact_phrase`.

```python
if callable(label_for) and not self_contact:
    other = str(label_for(other) or other)                 # :244 relabel first
...
target_interior = _interior_label(raw_interior, other)     # :295 strips by the LABEL
```

**Scenario.** An interior contact whose holder is "Mirelle Sulmirath" and whose
`target_interior` is "Mirelle's Mouth". That is chat 97's stored value; 2 of
the 24 interior contacts in the corpus name their own holder. The occupant has
not learned the name and labels her "the woman".

- `contact_sensation(..., label_for=...)` returns: "You feel the woman's
  Mirelle's Mouth enclosing your hand, with contact at the woman's tongue: ...".
- With "Mirelle Sulmirath's Throat" it returns: "You feel the woman's Mirelle
  Sulmirath's Throat enclosing your hand ...".
- `contact_phrase`, given the relabelled record exactly as `character.py`
  builds it, returns: "your hand remains within the woman's Mirelle's Mouth,
  maintaining contact at the woman's tongue".

**What the floor catches.** The composed view and the memory episode both go
through `_scrub_unknown_identities` (`perception.py:5354, 6661`). The result
there is a garbled line, "You feel the woman's the woman's Mouth ...", plus a
`COMPOSER TRIPWIRE -- unearned identity ... (engine defect)` warning on every
beat the contact stands. I confirmed this by snippet.

The character payload is not scrubbed. `character.py` scrubs only
`world_knowledge` (`:3903`) and the interim text (`:4665`), so the name reaches
the mind through `self.standing_contacts`.

**Verified.** Snippets of both renderers and of the scrub; the writer and both
consumers traced. **CONFIRMED** at Layer A. The end-to-end leak into the
payload is **PLAUSIBLE**: it needs an occupant who has not learned the holder's
name, inside an interior room named for its holder.

**Fix.** Two parts:
- Strip possessives by the canonical owner (all name tokens and aliases)
  before `label_for` is applied, in `_interior_label`. Use `_interior_label`
  in `contact_phrase`'s interior branch too.
- Better, pass `target_interior` through the same observer label map as the
  parties.

Test: an interior contact with `target_interior` "<Owner>'s Mouth" and a
`label_for` that hides the owner. Neither renderer's output, and no payload
built for a stranger, may contain the owner's name.

### F2 — The room fold is ASCII-only, so a Japanese or accented place name is no spelling of its room (CORRUPTION, latent in ja)

**Where.**
- `world/spatial_identity.py:796-797` `normalize_room_id`
  (`re.sub(r"[^a-z0-9]+", "_", ...)`).
- `:819` `room_spellings` folds the room's name with it.
- `:903` `room_name_words` splits on the same class.

The same file already uses a script-aware fold for beings: `_positions_lookup`
calls `story.character_schema.fold_identity_key`, and its comment at `:27-28`
reads "the old ASCII fold erased every non-Latin name".

**Snippets.**
- `normalize_room_id("台所")` is `''`; `fold_identity_key("台所")` is `'台所'`.
- `room_spellings("kitchen", {"name": "台所"})` is `('kitchen',)`, and
  `scene_room_id(scene, "台所")` is `''`. A held room cannot be found by its name.
- `agents/director_prose.py:1674` `reserve_places([{"name": "台所"}, {"name": "裏庭"}])`
  is `{}`; the English control `[{"name": "Back Yard"}]` reserves `back_yard`.
  A Japanese new place is never reserved, so the room author never builds it.
- `spatial_light._room_named(scene, "台所")` is `None`. A lamp aimed at a room
  by its name is unreadable and falls back to all-round.
- Accented Latin: "Café Rouge" folds to `caf_rouge`, so
  `scene_room_id("Cafe Rouge")` is `''`. "Ærø Quay" folds to `r_quay`.

**The same class outside these files** (for their auditors):
- `persist/commit_room_registry.py:197-212` dedups by `room_spellings`, so a
  Japanese-named mint never dedups. This confirms the other auditor's report.
- `persist/commit_room_registry.py:75`
  `index.setdefault(normalize_room_id(row["room_uid"]), ...)` is not guarded
  against `""`. Every non-ASCII uid keys `""`, so a new non-ASCII mint in an
  anchored scope would `.get("")` and be redirected onto the first one: two
  rooms merged. **PLAUSIBLE**, since it needs non-ASCII ids.
- `persist/commit_mapping.py:197-202` dedups lorebooks with
  `normalize_room_id(row["name"]) == name_slug`. With Japanese names that is
  `"" == ""`, which would fold every Japanese-named book onto the first.
  Latent: the docstring says no turn stage proposes books now.
- Engine-wide there are 67 `[a-z0-9]`-class regexes in 30 files, and about 25
  call sites of `normalize_room_id`. Some of those mint ids:
  `director_prose:1674`, `common_cast:599`, `director_lots:161`.

**Corpus.** No room name is non-ASCII, because no ja story has been played.
The ja cards ask for names in Japanese.

**Fix (the class).** Make the fold Unicode-aware: NFKC, casefold, then
`re.sub(r"[\W_]+", "_", ...)`, and decide on combining marks. Ids already
minted keep matching by exact key. Guard every dict keyed by a fold against
`""`.

Test: a scene with a Japanese-named room. `scene_room_id` by name,
`room_spellings`, `reserve_places` and the registry alias index must all
answer, and "Café" and "Cafe" must fold together. **CONFIRMED** by snippets.

### F3 — The entity-state contact lift invents touches from idioms, reverses passive keys, and deletes what it cannot lift (WRONG-SCENE)

**Where.** `world/spatial_contact_migration.py`:
- `:43-56` the fragment table: `("bit","bite")`, `("pin","pin")`,
  `("rest","rest")`, `("press","press")`, `("hold","hold")`, `("held","hold")`,
  `("carried","carry")`, `("_on","touch")`.
- `:170-183` matches a fragment as a substring of the key and pops the key
  before anything validates it. `:199-201` does the same for Pattern B.
- `:209-211` `apply_contact_ops(..., _age=False)` is called with no `report`.
- `:256-266` matches `word.startswith(fragment)`.

It runs on every merge (`world/spatial_merge.py:2286`), so it is not dead.

**Snippets** (Elyra and Hinami in one room):
- `eyes_on: "Hinami"` becomes (Elyra, touch, Hinami, part 'eyes').
  `focus_on` becomes touch, part 'focus'.
- `expression_toward` becomes press, part 'ex'. `interest` becomes rest, part
  'inte'. `spine_toward` becomes pin, part 's'. `threshold` becomes hold,
  part 'thres'.
- `eyes: "pinned_to_Hinami"` becomes pin. `thoughts: "resting_with_Hinami"`
  becomes rest. `hand: "pink_ribbon_around_Hinami's_wrist"` becomes pin,
  because 'pink' starts with 'pin'.
- Passive keys reverse the act. A lantern with `held_by: "Hinami"` becomes
  (lantern, hold, Hinami). `carried_by` becomes (lantern, carry, Hinami).
- `gaze: "resting_on_Hinami's_face"`, `attention_on: "Hinami"` and
  `mood_on_seeing` produce a contact that `apply_contact_ops` refuses (the part
  is not anatomical), and the state key is deleted anyway.

The module states its own rule: "inventing a hold is worse than missing one,
because a contact becomes ground truth the narrator is told". `Design.md:496`
says "`gaze` is never touched", but the key is deleted.

**Verified.** Snippets on `contacts_from_entity_state` and
`_lift_valued_contact`. **CONFIRMED** mechanism.

Frequency is **PLAUSIBLE** and cannot be measured on stored scenes, because the
merge consumes lifted keys. The encoder's entities card lists "held" among
state configuration. The corpus's 6 contacts with a non-body actor are encoder
`rest` ops that name parts, not lifts.

**Fix.**
- Match fragments against whole `_`-tokens of the key.
- Refuse a key with a passive marker, or swap actor and target for it.
- Pop a key only when `apply_contact_ops` accepted its record.
- Do not widen the fragment table.

Tests: `eyes_on`, `held_by` and `gaze: resting_on_X` produce no contact and
keep their state key. Correct `Design.md:496`.

### F4 — A sealed door is reopened by its own name at every merge (WRONG-SCENE)

**Where.** `world/spatial_barriers.py:494-495`:

```python
edge["barrier"] = _barrier_against_its_own_name(normalize_barrier(...), edge.get("name"))
```

`_barrier_against_its_own_name` is at `:514-540`. It contradicts
`:215-221` `_BARRIER_SEAL_QUALIFIERS`, whose rule is that "a qualifier must not
quietly promote one back to a door it can be opened through".

**Snippet** (`normalize_scene_barriers`, which the merge runs at
`spatial_merge.py:2258` and the World Browser runs on every write at
`world_routes.py:1727`):

```
'welded_door'  named 'blast doors'         normalize_barrier='wall' -> stored 'closed_door'
'bricked_up'   named 'the old cellar door'                          -> stored 'closed_door'
'sealed'       named 'airlock hatch'                                -> stored 'closed_door'
'boarded_door' named 'back door'                                    -> stored 'closed_door'
'wall'         named '玄関の扉'                                       -> stored 'wall' (English-only, F12)
```

**Scenario.** The story welds a blast door shut. The encoder writes
`welded_door` on an edge already named "blast doors". The merge stores
`closed_door`, and any hand opens it next beat. It is not even held as
fastened, because of the registered fold in §1.216.

Not registered. **CONFIRMED.**

**Fix.** Apply the name floor only when the wall came from the fallback or
from a bare `wall` spelling, never from a seal qualifier. That needs the
written word to survive the merge, either stored beside the folded value or
recorded as a `sealed` field. §1.216's fastening loss wants the same repair.

Test: welded, bricked and boarded doors with door names stay `wall` across two
merges. Chat 74's `{'barrier': 'wall', 'name': 'lobby doors'}` still becomes
`closed_door`.

### F5 — `same_subject` treats an alias two beings share as both of them (WRONG-SCENE, firewall-adjacent)

**Where.** `world/spatial_identity.py:216-243`. It resolves each side through
`_entity_named` (`:270-276`, first match wins). `room_of` (`:156`) and
`canonical_subject_map` (`:498-585`) both refuse ambiguity under the module's
own rule, "AMBIGUITY RESOLVES TO NOTHING".

**Snippet.** Entities "Guard Aldo" and "Guard Bren" are both aliased "the
guard". A contact's actor is "the guard".
- `same_subject('the guard', 'Guard Aldo')` is True, and so is
  `same_subject('the guard', 'Guard Bren')`.
- `room_of('the guard')` is None, and the canonical map leaves the alias
  unfolded.
- `contact_sensation(you=...)` tells **both** guards "You feel Hinami's
  shoulder against your hand: steady pressure, ...".

`contact_sensation`'s own docstring rule is that a non-party "feels nothing,
and this must never be the thing that tells them otherwise". The consumers are
`contact_sensation._is_observer`, `substance_event_clause`,
`contact_actions_for_observer`, `speech_articulation_impediment`,
`substances_for` and the substance selectors.

**Fix.** Use `_unique_entity_keyed` (the strict form) inside `same_subject`.
Test: the two-guard scene, in which neither guard feels the contact, while an
alias held by one entity still matches.

**CONFIRMED** mechanism. Occurrence is **PLAUSIBLE** (crowds with generic
aliases).

### F6 — A destination naming an unbuilt place resolves to any one room whose name ends in its letters (WRONG-SCENE)

**Where.** `world/spatial_identity.py:877-884` is the words fallback of
`scene_room_id`. `:920` matches `h.endswith(word)` for words of three letters
or more.

**Snippets.**
- Rooms {Walled Garden, Kitchen, Entrance Hall}: `scene_room_id("the den")`
  is `'garden'`.
- Rooms {Cockpit, Main Deck}: `"the pit"` is `'cockpit'`.

**Consumers.**
- `agents/mapping.py:267`: the movement compiler reports "known" and raises no
  planning need.
- `agents/director_prose.py:1048, 1140, 1215` bind a `new:<words>` place to the
  held room, and `reserve_places` skips it through `_held_room`.

So "she retreats to the den" walks her into the garden, and no den is ever
built.

**Fix.** Keep the tail rule only where the evidence is strong, for example the
candidate is within the walker's reach, and file the guess as an engine
notice. Never let it decide identity silently. Test: both scenes above answer
`''`. **CONFIRMED.**

### F7 — Room-level light spill reads only the dark room's own edges (WRONG-SCENE, latent today)

**Where.** `world/spatial_light.py:797-805` loops
`for edge in room.get("adjacent")`, with no `effective_adjacent` and no
`resolve_edge`. By contrast, `_light_crosses` (`:533-543`) uses
`effective_adjacent`. That function's own docstring says 20 corpus rooms
declare no edge of their own, 9 of them occupied.

**Snippet.** A dark cellar and a lit kitchen, with the open door declared only
from the kitchen: `effective_light(cellar)` is `'dark'`. Declared from the
cellar, it is `'dim'`.

**Effect.** A room without light geometry reads pitch dark ("It is dark
here.", sight `none`) beside an open way onto a lit room. That contradicts
`room_vocabulary.txt`: "a dark room with an open way through to a lit one is
dim ... the engine works that out". The fallback also ignores the neighbour's
room-filling sources, because it reads only `room_light`.

**Corpus.** 440 of 1,093 rooms take this path. Of the 37 dark-declared rooms
among them, 0 currently have an edge declared only from the far side.

**Fix.** Iterate `effective_adjacent`, and read the neighbour as
`room_light` combined with `source_light(filling_only=True)`. Test: the
one-sided edge reads dim. **CONFIRMED**; latent on today's corpus.

### F8 — The ground storey is seeded from whatever stands first in `positions`, then frozen (WRONG-SCENE)

**Where.** `world/spatial_levels.py:143-185`. The docstring at `:148-149` says
"the player's room first when one is placed". The code at `:159-165` takes the
first positions row of any kind. `:182-185` writes the inferred levels into
the rooms, after which they read as declared ("A declared level is never
moved").

**Snippet.** Kitchen goes up to bedroom; yard opens into kitchen. With
positions `{"lamp": "bedroom", "Hinami": "kitchen"}`, the result is bedroom 0,
kitchen -1 and yard -1.

**Readers of the absolute level.** Site-plan elevations
(`site_plan.py:1647`, `elev_m = level * STOREY_M`), occlusion by height in the
landscape and vista code, and the layout tier's below-ground handling.

**Fix.** Seed from ground evidence (the player's room as documented, or an
open-exposure room), and mark inferred levels with a flag such as
`level_inferred`, following the `ROOM_NAME_DERIVED` precedent, so that a later
declaration can move them. Test: in the snippet's scene, kitchen and yard are
at 0. **CONFIRMED** mechanism. Impact is **PLAUSIBLE**: it applies only to
scenes with stairs and no declared level.

### F9 — `uncouple_decision`'s reason is never read, and a pair within full earshot is reported "channel_closed" (SILENT-NOOP)

**Where.** `world/spatial_bubbles.py:470-515`; the docstring at `:483-494`
says "the caller routes on it". The only caller,
`world/spatial_frames.py:2128-2129`, does
`ended = ...; return None if ended else (...)`, and `close_couple` (`:2491`)
partitions unconditionally.

**Snippet.** A hall and a study joined by an open door, with a live duplex
handset between Ada and Ben.
- The voice from the study reaches the hall at `'full'`.
- `_cross_link` is None, because `comms_link` suppresses a radio wherever a
  normal voice already arrives whole (`spatial_senses.py:428-432`).
- `uncouple` returns reason `'channel_closed'`, because the reunion test only
  checks for a shared room (`:505-513`).

**Effect.** The route the docstring promises ("reunited — do NOT partition")
does not exist. Two people talking through an open doorway end their call and
are partitioned back into two frames.

**Fix.** Make the reunion test comms_link's own audibility test
(`hear_level(spatial_rel, "normal") == "full"`), and have the caller route on
`reason`. Test: the snippet's scene yields `'reunited'` and is not
partitioned. **CONFIRMED** for the decision; the downstream frame outcome is
**PLAUSIBLE**.

### F10 — An off-ladder light word silently reads `lit` (SILENT-NOOP)

**Where.** `world/spatial_light.py:31-46`. `normalize_light` is an
exact-match alias table after `replace(" ", "_")`; anything else returns
`'lit'`.

**Snippet.** "pitch-dark", "dimly lit", "gloomy", "moonlight", "candlelight",
"lamplight", "firelight", "soft lamplight" and "bright fluorescent" all return
`'lit'`.

**Corpus.** 34 of 311 declared room light words are off the ladder: soft
lamplight 18, bright fluorescent 10, fluorescent 3, moonlight 2, even
institutional 1. "moonlight", which means dim, reads lit. Nothing reports it;
the barrier pass has `unresolved`, but light has no equivalent. The commit
that retired §1.174 (`5da62aa5`) notes the same fold read 薄暗い as lit, and
answered it on the card only.

**Fix.** No word list. Fold the way `normalize_barrier` does: separators
first, then the last understood token. Report unread words as an engine
notice. Whether an unread word stays fail-open `lit` is the owner's decision.
**CONFIRMED.**

### F11 — The lit switch is spelled six times, case-sensitively (SILENT-NOOP, latent)

**Where.** `world/spatial_light.py:357, 494-495, 738`;
`world/spatial_light_field.py:336-339`; `world/landscape.py:401`;
`dressing/backdrops.py:596`. Each reads
`state.get("lit", True) in (False, 0, "off", "false", "no", "doused", "out")`.

**Snippet.** `lit` set to "False", "Off", "unlit" or "extinguished" gives
`source_light` `'lit'` and `light_at` `'lit'`. Entity `state` is free-form;
`llm/schemas` does not coerce it.

**Corpus.** All 44 stored `lit` values are booleans (37 True, 7 False), so
this is latent.

**Fix.** One `is_lit(entity)` that casefolds strings and reads the schemas'
`_BOOLISH` set, called from all six sites. Test: the four spellings read as
out. **CONFIRMED** mechanism.

### F12 — Two floors read free prose in English only (SILENT-NOOP in ja)

- **`world/spatial_barriers.py:508-512` `_OPENING_WORDS`**
  (door|doorway|archway|...|portal), applied to the edge `name`. In the ja
  pack the name is written in Japanese while the barrier stays a protocol
  token, so the rule "an edge named as an opening cannot be a wall" never
  fires. Snippet: '玄関の扉' stays wall; 'the lobby doors' becomes
  `closed_door`. Chat 74's class, a lift reachable from one side only, is
  unguarded in Japanese.
- **`world/spatial_substance.py:161-166`**
  `manner in {"seal","sealed","cover","covered"}`, applied to the free-text
  contact manner. The manner vocabulary's tail is open by design
  (`spatial_contacts.py:974-1000`), so "clamped", "smothering" or "gagging"
  never stifle speech.
- **`world/spatial_contact_migration.py`** fragment, direction and drop tables
  are English. Japanese state never lifts, which fails safe.

**Fix.** The opening floor should read a typed fact (the edge has a `way`, a
passage record, or a door anchor) instead of English nouns. Since this is a
guard on free prose, the owner rules after the false-positive rate is
measured. **CONFIRMED** for the first item; **PLAUSIBLE** for the second.

### F13 — `SCENT_LEVELS` names two ladders, and the facade exports the wrong one to the senses test (DEAD test coverage)

**Where.** `world/spatial.py:282` imports it from `spatial_senses`
(`('none','muffled','full')`); `:447` imports it from `spatial_scent_field`
(`('trace',...,'overpowering')`). The later binding wins. An AST scan of
every import, def and assign in the facade finds this to be its only name
collision.

`tests/test_senses_gate.py:24, 44` iterates `SCENT_LEVELS` meaning the sense
ladder and gets the strength ladder. `sense_adjusted` returns an unknown word
unchanged, so the scent half of
`test_ordinary_and_unlisted_are_byte_identical` asserts nothing; I ran it and
it passes. `world/charter_runtime.py:3477-3480` gets the strength ladder only
because of the facade's import order.

**Fix.** Rename one of the two, for example to `SCENT_STRENGTH_LEVELS`, and
import it explicitly in each reader. Add a facade-collision check to the
duplicate-symbol pass in `tools/project_check.py`. Test: the senses test
iterates `('none','muffled','full')`. **CONFIRMED.**

### F14 — `spatial_facts` and the four builders under it are dead, and three documents say they reach the narrator (DEAD + STALE-DOC)

**Where.** `world/spatial_prose.py:325-410` `spatial_facts`. Its only callers
are tests and the facade. `size_facts`, `containment_facts`, `pose_facts` and
`vitals_facts` have no other production caller (whole-repo grep).
`tests/test_acuity_proportionality.py:5-6` already says "which nothing on the
live path imports".

**Stale claims.**
- `spatial_prose.py:64`: "narrator ground truth via `spatial_facts`".
- `Design.md:355`: "`containment_facts` states the place form ... so the
  occupant is still told where they are".
- `AGENTS.md:500-502` lists `spatial_facts`, `size_facts` and
  `containment_facts` as companions in three routing rows.

The dead code also still carries a retired light rule. `:365-367` says "dim;
shapes and movement, not detail", while the live `_LIGHT_SIGHT` grades dim as
`conduct`. `:405` filters contacts by exact string.

**Fix.** Delete the bundle and its tests, or wire up a live equivalent.
Correct the three documents. **CONFIRMED.**

### F15 — Orphan helpers (DEAD)

No caller anywhere, only a facade re-export and no test:
- `world/spatial_light_field.py:1054` `observer_light_field`.
- `world/spatial_substance.py:1034` `contact_actions_of` and `:1060`
  `actions_for_contact`.

Dead in production, called only by tests:
- `world/spatial_scent_field.py:198` `scent_at`. The module says at `:18` "A
  body is told how strong it is", but no perception path reads the ledger.
  Its one reader is the charter hunter (`scent_gradient`, `scent_word`), and
  the commit deposits only "breath" (`commit_scene_state.py:2765-2770`).
- `world/spatial_barriers.py:453` `unresolved_barrier_words`. The merge passes
  no `unresolved` set, so the docstring's "reported" (`:354-372`) never
  happens at merge.
- `world/spatial_barriers.py:441` `barrier_opens_to_a_hand`.

**CONFIRMED** by grepping the whole repo, including tests, tools and
extensions.

### F16 — Stale docstrings (STALE-DOC)

- `spatial_bubbles.py:14, 20`: "only the detectors" and "NOTHING HERE HAS SIDE
  EFFECTS. The three functions...". The module also holds the reach, fuse and
  sibling-meeting code, and `bubble_radius` (`:188`) reads the db.
- `spatial_bubbles.py:432-435`: couple refusal 3 says `perform_split` gives the
  child "every away-zoned AND every unzoned room". Since 2026-09-17 both
  frames hold the whole map (`spatial_frames.py:1342-1365`).
- `spatial_light.py:709`: `light_at` says "across the room you are a shape in
  the dark". Since 2026-09-05, dim grades `conduct`.
- `spatial_light.py:145-150`: `_celestial_phase` says a scene with two moons
  "leaves to the sky's own axis". The code takes the first celestial entity's
  phase.
- `spatial_identity.py:596-612`: `normalize_scene_subjects` lists the ledgers
  it folds. It also folds `orientation`, `vitals`, `overlays`,
  `contact_actions.actor` and `poses.support`, which are not listed.
- `spatial_barriers.py:354-372`: `normalize_barrier` says the unread word "is
  collected into `unresolved` and reported". At merge it is neither (F15).

**CONFIRMED.**

## Efficiency

Ranked by the gain for the least work.

**E1 — The layout lint runs twice per commit and once per World Browser request.**
- `persist/commit_scene_state.py:2924` calls
  `room_layout_lint(sc, prev_scene, plan_rows=True)`, which re-lints the
  previous scene (`spatial_lint.py:773`) even though the previous commit
  already linted it.
- The browser recomputes the whole lint on its tree, room, grid and map GETs
  (`web/world_routes.py:704, 827, 1317, 1376`).
- The room designer lints again per draft (`agents/director_rooms.py:223,
  248, 421, 1022, 1373`).

Measured on the largest stored scenes (23-24 rooms): 26-90 ms per call, and
48-58 ms per call with the previous scene. On synthetic towns: 37 ms at 36
rooms, 93 ms at 100 and 238 ms at 196. A commit on a 196-room town spends
about half a second here.

Fix: memoise `room_layout_lint(scene, plan_rows)` on a fingerprint of rooms,
passages and the site-plan inputs, the way `_FIELD_CACHE` does. Alternatively
keep last commit's row keys in `world_flags`. Gain: the previous-scene half of
every commit, and all repeat browser requests.

**E2 — Every `effective_adjacent` call scans every room, and recomputes `frontier_joins`.**
- `spatial_barriers.py:902-996` scans all rooms for far-side edges, so one
  call is O(R·E), and calls `frontier_joins` each time.
- The callers loop it per room: the lint BFS through `_beared_neighbours`,
  `scent_edges` per scented room per commit, `_light_crosses`,
  `spatial_levels._edges`, and `infer_room_levels` at every merge
  (`spatial_merge.py:2265`).

Measured over all rooms: 1.3 ms at 36 rooms, 7.8 ms at 100 and 27.9 ms at
196. `infer_room_levels` on a flat scene takes 0.7, 5.0 and 18.6 ms per merge
just to discover there are no storeys.

Fix: build a reverse-edge index and the frontier joins once per pass
(`scene_memo`), or once per call site. Gain: O(R²E) becomes O(E).

**E3 — `light_field` lookups outside a read pass pay a JSON key each time.**
`spatial_light_field.py:995-1008` json-dumps the whole read set on each
lookup. On chat 63 (24 rooms) a content-cache hit costs 0.54 ms, of which the
key is 0.51 ms. `light_at` costs 0.81 ms per body outside a pass and 0.48 ms
inside one.

Fix: open `scene_read_pass` in the remaining per-observer loops (narrator,
Director floors), or key on a hash of parts that is computed once per pass.

**E4 — `canonical_subject` rebuilds the whole canonical map on every call.**
`spatial_identity.py:587-593` costs 0.50 ms per call with 60 entities.
`_live_contact_actions` (`spatial_substance.py:1004-1031`) re-cleans every
row on each read through `canonical_subject` and `resolve_contact_action_ref`.
It is called per observer (`contact_actions_for_observer`), by the ledger
index, and twice inside `apply_contact_action_ops`. `resolve_substance_ops`
calls it twice per op. Fix: memoise the map per pass.

**E5 — `same_subject` is O(E) and runs in nested loops over substances.**
`_substance_target_exists` (`spatial_substance.py:249-289`) is
O((P + E·A)·E) per add. `_standing_substance_pools` and `_same_pool` are
O(S²·E). This is small today. Fix: resolve each label once into an id map
for the loop.

**E6 — `_room_fixtures` builds a fresh `PositionsIndex` per call.**
`spatial_light_field.py:376-398` is called per room per field build:
`ambient_floor_word` for every room in the field, and twice per wall in
`_spill`. Fix: take the index once in `compute_light_field`.

Not hot: `advance_scents` runs once per commit, and `scent_gradient` once per
creature place per charter window. No perception path reads the scent ledger
per observer.

## Already registered

These are not findings.

- **UNBUILT_PIPELINE §1.216 (residual): "`locked_door` folds to
  `closed_door`".** One consequence is not in the register.
  `normalize_scene_barriers` overwrites the written word at every merge, so
  `barrier_fastening` returns `''` for every stored edge. The snippet: a merged
  `locked_door`, and a diff-written `jammed_door`, both come back
  `closed_door` with fastening `''`.
  - So `charter_space.people_neighbors`'s fastened-door hold
    (`charter_space.py:70`, which its docstring calls "not a nicety") never
    fires. The snippet: a locked street-tavern edge is `{}` raw and
    `{'street': {'tavern'}, ...}` after the merge's pass.
  - `barrier_opens_to_a_hand` is dead with it.
  - `tests/test_charter_traversal.py::...::test_a_shut_door_holds_the_body_where_it_stands`
    passes only because `_lock` writes `locked_door` into an unmerged scene.
- **UNBUILT_PIPELINE §1.216: "the composer renders 'soup of soup'".** Still
  live at `spatial_substance.py:56-72`. `_material_phrase` produces "Your
  mouth registers a spoonful of soup of soup being deposited within it" (the
  beat of eating still delivers the event), and "some of soup" for the amount
  "some".
- **UNBUILT_IDENTITY §1.48: contact and substance clauses stay English in a
  Japanese view and memory.** Confirmed: `language_adapters/japanese.py:622-624`
  passes `data["clause"]` verbatim. `contact_action_clause`
  (`spatial_substance.py:1177`, "You sustain/feel ... through the contact")
  belongs to the same class and is not listed there.
- **UNBUILT_WORLD §1.228 (residual): scent crosses every far way.**
  `scent_edges` ignores `distance` and `frontier_join`.
- **UNBUILT_WORLD §1.209: a floor word the sound tables do not hold reads as
  masonry.** Corpus: 8 of 170 floor words fall outside `FLOOR_LOSS_DB`
  (gravel and clay 3, metal 2, cracked poured concrete 1, earth 1, gravel 1).
  The same `floor` field also carries `MEDIUM_FLOORS = {"water"}`
  (`spatial_transit.py:954`).
- **UNBUILT_WORLD §1.2: the layout lint reports and never refuses.**
- **UNBUILT_WORLD §2.38:** the `LAYOUT_COLLISIONS_COMPARED_BY_PAIR` flag is
  still the owner's open question.
- **UNBUILT_WORLD §1.10: an entity's free-text `state` never ages.** This is
  the context for F3.
- **Resolved by the owner (former UNBUILT_PIPELINE §1.174, commit `5da62aa5`):
  an outdoor room's declared light keeps the hour it was written in.** It was
  answered with a card clause, and "rooms already holding an hour keep it". The
  corpus today holds 89 `dark` and 132 `dim` declared words.

## Structure notes

**Seams.**
- `spatial_substance.py`: lines 900-1198 are a second ledger, the contact
  effects (`contact_actions`), with their own ids, ops and renderer. That is
  a clean split.
- `spatial_barriers.py`: the vocabulary (aliases, `normalize_barrier`,
  fastening, scent table) can separate from the graph (`effective_adjacent`,
  `neighbor_map`, passages, frontier joins).
- `spatial_identity.py`: there are two identity domains, beings
  (`same_subject`, `canonical_subject_map`, `room_of`) and rooms
  (`normalize_room_id`, `room_spellings`, `scene_room_id`, derived names),
  and each uses a different fold (F2).
- `spatial_light.py`: the beam and aim half (`aim_of`, `_beams`,
  `_room_beam_on`, `beam_*`) belongs with `spatial_light_field`.

**Monoliths in miniature:**
- `pack_anchors` (about 150 lines) and `_full_lines` (about 110).
- `leaf_rows` (about 90).
- `light_shape` (about 130), `light_sources` (about 90) and
  `compute_light_field` (about 70).
- `normalize_scene_subjects` (about 150 with its nested helpers) and
  `canonical_subject_map` (about 85).
- `contacts_from_entity_state` (137) and `_resolved_substance_add` (about 120).
- `apply_contact_action_ops` (about 85) and `normalize_barrier` (about 80).

**Module-level mutable state:**
- `spatial_light_field._FIELD_CACHE`: written by `_light_field`, cleared
  whole at 64 entries. Hits are shared by reference and are never mutated by
  readers.
- `scene_memo._PASSES`: not in scope, but read here.
- `spatial_lint.LAYOUT_COLLISIONS_COMPARED_BY_PAIR`: a constant flag.

**Two identity rules in one renderer.** `contact_phrase` compares "you" by
casefold, while `contact_sensation` uses `same_subject`. `held_beam_falls_on`
compares holders by casefold.

**Raw versus folded barrier.** `normalize_scene_barriers` stores the folded
value over the written word. That one choice is the root of the fastening
loss (§1.216) and of F4. The written word, or its qualifier, needs a field of
its own.

**`_clusters` is not transitive** (`spatial_bubbles.py:248-271`). If A
reaches C and C reaches B, but A does not reach B, the result is {A, C} and
{B}. A sibling meeting merges them later at the cost of an extra split.

## Docs checked

| Claim | Held? |
|---|---|
| AGENTS.md:502 "Contact must have one record ... anything that puts it back into an entity's state re-creates a copy" | Held: the lift removes it. But the lift also invents (F3). |
| Design.md:496 "`gaze` is never touched" | **Failed**: the key is deleted (F3). |
| Design.md:355 "`containment_facts` states the place form ... the occupant is still told" | **Failed**: the path is dead (F14). |
| AGENTS.md:500-502 routing rows naming `spatial_facts`, `size_facts`, `containment_facts` | **Stale**: the code is dead (F14). |
| Design.md:575 and AGENTS.md:525 "`_walled_by_a_door`, `DOOR_BARRIERS`" reads a door "the engine reads as one" | Held: `layout_bridge.py:576-580` normalizes first. Note that `membrane` is not a door there. |
| `spatial_lint` header: the commit reports a row once under `layout_lint_told`, and the Room's `inspect_contradictions` shows every row | Held (`commit_scene_state.py:2921-2928`, `story/room_tools.py:826`). |
| `room_layout_lint`: "the room designer's own check and the doorway search never ask for [plan_rows]" | Held. |
| `uncouple_decision`: "the caller routes on [reason]" | **Failed** (F9). |
| `couple_decision` refusal 3's description of `perform_split` | **Stale** (F16). |
| `infer_room_levels`: "the player's room first when one is placed" | **Failed** (F8). |
| room_vocabulary card: "a dark room with an open way through to a lit one is dim ... the engine works that out" | **Failed** for an edge declared from the far side, on the room-level path (F7). |
| encoder rooms card: a `locked_door`/`stuck_door` word "the engine reads ... as one that does not yield to a hand" | **Failed** (registered §1.216; see Already registered). |
| `spatial_scent_field` header: "A body is told how strong it is" | **Failed**: no perception reader (F15). |
| `contact_phrase` docstring consumer list | **Stale** (F14). |
| `scene_memo.SCENE_READS` covers what the light field reads (eye_rank → stations, poses, entities; altitude → stations, rooms) | Held for every read I traced. |
| `spatial_light_field` header "THERE IS NO GLARE" and the owner's ruling "light never obscures detail" | Held. No sight cap from source power, contrast or position remains. Only `_LIGHT_SIGHT` grades sight. |

## Answers to the assigned questions

**(1) Light.**

*What does a view get for a room with no light source at night?*
- An open or sheltered room reads the sky's word, so `dark` (or `dim` under a
  moon). The composer says "It is dark here." (`compositor.json`
  `light_dark`), and a doorway into such a room says "Through {opening}, only
  darkness.". Both name a cause, so they are compliant.
- An enclosed room with no `light` word reads `lit` by the documented
  fail-open, even at midnight with no lamp. This is not a placeholder; it is a
  design choice.
- Bodies at sight `none` are not rendered at all.
- The forbidden phrasing exists elsewhere, and none of it comes from light,
  since `_LIGHT_SIGHT` has no `shapes` rung. The compositor's `act_shapes*`
  ("too little of it to make out") belongs to the crossing grace.
  `speech_trace*`, `loop_faint_sound*` and `muffled_attributed` ("nothing you
  can make out") belong to sound. All of this is outside my files.

*Does any path reduce detail with light level?* Not in my files. Only
`_LIGHT_SIGHT` grades sight. A flicker lowers a source one rung on its
flicker beats, which is the light word grading sight; that follows the
ruling's letter. The dead `spatial_facts` still carries the old "dim ... not
detail" line (F14).

*Is light baked into state as well as derived?*
- The room's `light` word is authored and also met by the sky. The owner
  resolved this with a card clause (former §1.174); old rooms keep their hour.
- `day_phase` and `beat_idx` are stamped by the commit
  (`commit_scene_state.py:186, 2913`). They are derived values, stored once
  per beat, with a single writer.
- A failing source's `state.lit: false` is written by the commit from the
  same hash that the field reads, so the two agree.
- No authoring path in these files writes a light level on the clock's behalf.

**(2) `spatial_identity`.**
- The ASCII fold at `:797`, used at `:819`, is confirmed, and its class is
  described in F2.
- Two spellings of one room do not dedup in Japanese. A non-ASCII uid
  collapses to `""` in the registry index (PLAUSIBLE merge of two rooms).
- The compiler asks `scene_room_id` without registry aliases
  (`agents/mapping.py:267`), while the Director's binding passes them
  (`director_prose.py`). So a renamed room is "held" for one reader and not
  for the other. This is PLAUSIBLE, outside my files.
- Subject folding, `normalize_scene_subjects`, is consistent with the
  registry, because the registry keys rooms and not beings.
- Other identity defects: F5 (ambiguous alias) and F6 (tail-of-word match).

**(3)** `contacts_from_entity_state` is not dead. It runs every merge
(`spatial_merge.py:2286`), and its cost is negligible: O(entities × state keys
× positions). It is harmful (F3).

**(4) Barriers.**
- The encoder, establish and room-author cards teach the closed set of eight
  values plus a fastening qualifier in the word, in both packs.
- An unknown non-empty word becomes `wall`, silently at merge: no
  `unresolved` set is passed, and `unresolved_barrier_words` has no
  production caller. An empty word becomes `open`. The English name rule may
  then turn `wall` into `closed_door`, and that rule also unseals sealed
  doors (F4).
- `DOOR_BARRIERS` lives in `world/layout_bridge.py:559`, not in
  `spatial_barriers`. It normalizes first.

**(5) Who consumes `room_layout_lint`.** The commit, per beat, together with
the previous scene. The Room's `inspect_contradictions`. The World Browser,
per GET on four routes. The room designer, per draft. It only reports
(§1.2). Costs are in E1.

**(6) Bodies, cells and bubble radius.**
- `spatial_pack` places fixtures only. Two standing things on one cell are an
  overlap the designer's check names. The read-time map allows it, and a
  doorway never counts as crowding.
- Body cells come from `spatial_fov.body_cell`, which is outside my scope.
  Two bodies that each name the other as `near` are laid side by side.
- Bubble caps: `BUBBLE_RADIUS_DEFAULT` 3, `BUBBLE_RADIUS_FLOOR` 1 and
  `BUBBLE_RADIUS_CEILING` 12 (`story/scene.py:2402-2404`). `max_bubbles` is
  clamped to 0-12 with a default of 3 (`:2548-2551`).
  `rooms_under_one_roof` is uncapped; its docstring measures the largest at
  18 rooms.

**(7) Floor words.** No closed engine set is enforced at write time.
`FLOOR_LOSS_DB` is an exact-match lookup of the upper room's free `floor`
word, and anything else reads as masonry, 50 dB. `layout_bridge._floor_word`
keeps 20 characters of free text. Registered as §1.209; corpus numbers are
under Already registered.

**(8) How the Japanese pack gets these words.** It does not.
`contact_sensation`, `contact_phrase`, `substance_event_clause` and
`contact_action_clause` produce English text, and the ja adapter passes
`data["clause"]` through verbatim. Registered as UNBUILT_IDENTITY §1.48, which
does not list `contact_action_clause`. `layout_warning` and `pack_anchors`'
lines are English too, but they go only to the Room and the designer.

**(9) Light and scent recomputation.** Both are cached. Light fields are
memoised per read pass and content-cached up to 64 entries; the cost is the
JSON key outside a pass (E3). The scent ledger advances once per commit and
has no per-observer reader.
