# Design note — subject spelling authority: the cast sheet decides

Status: **decided, not built.** Written 2026-08-19 against the working tree at
commit `4f33b17` (plus the same-day uncommitted `room_of` read-side repair,
already present in `world/spatial_identity.py`). Every live-data claim below
was re-verified read-only against `engine.db` on this date; the queries and
their outputs are quoted in § Evidence.

---

## 1. The question

When one being is both a registered cast character and a scene entity — the
ordinary case for every character who is physically present — the engine holds
two records that can each claim to know the being's name: the cast sheet's
`identity.name` (`story/character_schema.py:1367`, `character_name`) and the
scene entity record's `name` (`scene.entities[eid]["name"]`). The subject fold
(`world/spatial_identity.py:261`, `canonical_subject_map`; applied by
`normalize_scene_subjects` at `world/spatial_identity.py:338`, called from
`world/spatial_merge.py:953` inside `merge_scene_with_diff`) currently declares
the ENTITY's own `name` canonical, on the docstring's assumption
(`world/spatial_identity.py:269-271`) that for a mirrored cast member the
entity name "IS the display name every reader already expects." Chat 82 shows
that assumption failing live — the Director minted the entity as
`"Dr. Sarah Moon"` against a sheet named `"Sarah Moon"`, and one body now has
two spellings across the subject-keyed ledgers. The read side was repaired
today (`room_of`'s identity resolution, `world/spatial_identity.py:33`); this
note decides whether and in which direction the DATA folds.

## 2. Corrections to the framing

Two points in the question as posed are wrong on the evidence, and both
strengthen the eventual decision rather than weakening it.

**2a. Existing saved scenes are NOT "already folded toward the entity name."**
For cast-mirrored beings the entity-name fold has never fired even once,
because of the very unreachability the framing itself identifies: a
model-minted cast entity is keyed by its own name (chat 82: eid
`"Dr. Sarah Moon"`, name `"Dr. Sarah Moon"`), so the id-guard at
`world/spatial_identity.py:315-316` `continue`s before the alias loop at
lines 320-323 is reached. What the live corpus actually holds is a
**per-ledger split with each half folded by a different existing mechanism**:

- `attire` is folded toward the **sheet name** by
  `persist/commit_attire.py:96` `_heal_attire_identity_keys` — a cast-aware,
  alias-matching, commit-side fold called with `ctx.cast` at
  `persist/commit_attire.py:724`. That is why chat 82's scene `attire` is keyed
  `"Sarah Moon"` even though the establish diff wrote both spellings.
- `positions` is folded toward the **sheet name** by
  `agents/common.py:3044` `canonicalize_positions`, called in the Director
  stage bodies (`agents/director.py:382` for establish, `:3010` for resolve) —
  but it "Deliberately does NOT match on aliases" (its own docstring), so
  `"Dr. Sarah Moon"`, which is an *alias* on Sarah's sheet, passed through
  unfolded.
- `poses`, `stations` and `orientation` have no cast-aware fold at all and
  keep whatever the model wrote.

So the engine has already answered the authority question **twice, in code, at
cast-aware seams, both times choosing the sheet** — and the live defect is not
"data folded the wrong way" but "two half-coverage sheet-name folds
disagreeing with one unreachable entity-name fold." A third answer exists in
`story/scene.py:51` `seed_initial_attire`, which seeds the ledger under the
sheet name, and a fourth in `world/subjects.py` (§ 3 below).

**2b. `orientation` is subject-keyed live but absent from the fold's ledger
list.** `_SUBJECT_KEYED` (`world/spatial_identity.py:208`) is
`("positions", "scales", "attire", "stations", "poses", "contained",
"following")`; chat 82's scene carries an `orientation` table keyed by the
same subject spellings (verified below), written by
`world/spatial_frames.py:361` and read via case-tolerant-but-not-identity
`_ci_get` at `world/spatial_geometry.py:77` and `:380`. Any fold that lands
must cover it, or a renamed subject loses their `came_from`/`facing` record.
(It partially self-heals — spatial_frames prunes orientation for a name no
longer positioned — but that is loss, not healing.)

## 3. `world/subjects.py` already answers the authority question

The module docstring (`world/subjects.py:1-52`) chose route C: identity
decoupled from scene liveness, each kind resolved through "the durable ledger
that already owns beings of that kind," and for `character` that ledger is
**the cast row** — `character_schema.cast_entity_id`
(`story/character_schema.py:1401`) first, the scene entity only as fallback.
`_resolve_character` (`world/subjects.py:190`) implements exactly that order,
answering with `authority="cast"` and `display = character_name(sheet)`.

So the question "who decides" is answered: **the cast row outranks the scene
entity for a registered character.** What subjects.py deliberately does not do
is touch the scene data ("WHAT ALREADY EXISTS, AND IS NOT TOUCHED" — its own
words about the fold). What is left to decide — and what this note decides —
is: (a) whether the scene ledgers should be made to CONFORM to that authority,
(b) at which seam, and (c) what happens to standing saves.

## 4. Evidence (read-only queries, run 2026-08-19)

All via `sqlite3.connect('file:engine.db?mode=ro', uri=True)`.

**Chat 82 cast sheet vs scene entity vs ledgers:**

```
SELECT COALESCE(cc.sheet,ch.sheet) FROM chat_chars cc
  JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=82
→ identity.name = 'Sarah Moon', aliases ['Dr. Moon','Dr. Sarah Moon'],
  uid 'char_14dc8414a3314348aaf7bebf40e3f740'

json_extract(world.value) WHERE chat_id=82 AND key='scene' →
  entity 'Dr. Sarah Moon': name 'Dr. Sarah Moon',
                           aliases ['Sarah Moon','Dr. Moon']   ← keyed by own name
  positions/poses/stations/orientation keys: 'Dr. Sarah Moon'
  attire keys: 'Sarah Moon'                                    ← the split
```

**The divergence originates in one `director_establish` diff** (steps row
22861, active variant): `state_diff.attire` keys =
`['Dr. Sarah Moon', 'Site Security Guard 1', 'Site Security Guard 2',
'Hinami', 'Sarah Moon']` — both spellings in a single model output, exactly as
the framing states.

**Corpus measurement** (all chats; a cast member counts as "mirrored" when any
scene entity answers to their name/uid/aliases):

```
cast members mirrored as scene entities : 61
entity name != sheet identity.name      : 4
scenes with one being's subject ledgers
  split across >1 spelling              : 7
```

The four divergent entity names: chat 27 `'The Doctor 10'` vs sheet
`'The Doctor'`; chat 65 `'Onlooker'` vs sheet `'Garret'` (a promoted
background presence whose entity kept the pre-promotion label — and whose
`positions`/`stations`/`orientation` carry BOTH spellings at once, i.e. one
body with two live position rows); chats 81/82 `'Dr. Sarah Moon'` vs
`'Sarah Moon'`. Chats 23/27/29 additionally hold attire keyed by uid
(`char_f0ef86a7…`) or entity id (`the_doctor_10`, `picard_jl`) beside
name-keyed positions. Note chat 65: folding toward the entity name would
rename a promoted character back to `"Onlooker"` — the entity record is not
merely *sometimes* wrong, it is wrong in a way promotion guarantees.

## 5. The options and their real costs

**A. Do nothing (today's state).** The `room_of` read-side repair keeps rooms
resolvable, and `same_subject` (`world/spatial_identity.py:127`) exists for
comparisons. Cost: every subject-keyed lookup that is NOT `room_of` — attire
readers, `_ci_get` orientation reads, perception company assembly, any future
ledger — must individually remember identity, and
`normalize_scene_subjects`'s own docstring names why that loses: "A guard that
has to be remembered is a guard that will be forgotten." Five prior defects
were each a single `==` (AGENTS.md § "A body sealed INSIDE another body").
Worse, the two live cast-aware folds keep RE-diverging the data from the
entity record every turn, so the scene never converges. Rejected.

**B. Fold toward the entity name (make the alias loop reachable as-is).**
Hoisting the alias fold out of the id-guard would rewrite
`attire["Sarah Moon"] → attire["Dr. Sarah Moon"]`. Every cast-side reader
addresses her by `character_name(sheet)` — she loses her clothes. And it would
not even be stable: `_heal_attire_identity_keys` folds attire back to
`"Sarah Moon"` at the next commit, so the two mechanisms oscillate, one
rewrite per turn, forever. Also wrong on chat 65's shape (Garret becomes
"Onlooker" again). Rejected.

**C. Thread the cast into `normalize_scene_subjects` so the merge folds
toward the sheet.** Honest cost: `merge_scene_with_diff`
(`world/spatial_merge.py:695`) takes `(scene, diff)` and has ~12 production
call sites across seven modules — `agents/director.py:3103`,
`agents/director_movement.py:161/478/499/836`, `agents/perception.py:1443/1899`,
`agents/common.py:6536`, `persist/commit_scene_state.py:287`,
`world/paradox.py:567/575`, `tools/pose_drive.py:109` — plus 36 test files.
Several callers (`world/paradox.py`, route previews in movement) are pure
world-layer code with no `ctx` and no cast in scope; threading cast in couples
a pure scene function to the database or forces every caller to fetch and
carry cast rows. It also puts TWO authorities inside one fold, which must then
adjudicate their disagreement in a module that cannot see the sheet. Rejected
as the seam — but the *direction* it wants is correct.

**D. Make the entity record conform to the sheet, at the seams that already
hold the cast — so the existing fold becomes correct by construction.** This
is the decision; § 6.

**E. Prompt the Director to key cast bodies by sheet name.** The establish
payload already shows the model `name`, `entity_id` and `aliases` per cast
member (`story/scene.py:2277` `cast_scene_context`, assembled at
`agents/director.py:287-305`), and the model reached for the honorific anyway.
A prompt clause is a literal guard, and literal guards fail when models
rewrite (measured three in one day — memory note); doctrine says the
deterministic floor must not depend on a model cooperating (AGENTS.md
§ Information boundaries, consequence 2). Acceptable as a *reduction* in how
often the repair fires, never as the mechanism. Not rejected, but not the
answer.

## 6. Decision

**For a registered cast character, the canonical spelling is the cast sheet's
`identity.name`. For every other being, it remains the scene entity's own
`name`.** The cast sheet is authored, durable, locked against rekeying
(AGENTS.md edit-routing row for per-story card edits: "identity name/uid are
locked because scene and knowledge records use them as keys"), and is the key
under which memories, knowledge records, attire, relationships and every
cast-side reader already address the being. The scene entity record is minted
by a model on turn 0 and is provisional by doctrine ("model output is
provisional until deterministic commit code validates it" — CLAUDE.md,
`persist/commit.py`). Letting a model's incidental honorific become a being's
canonical name inverts the engine's source-of-truth order; `subjects.py`
route C, `canonicalize_positions`, `_heal_attire_identity_keys` and
`seed_initial_attire` have each already voted this way.

**Enforcement is NOT a new fold direction — it is making
`canonical_subject_map`'s existing rule true by construction.** Its docstring
assumes the entity's name is the display name; stop assuming and enforce:

1. **Entity-record reconciliation, at a cast-aware seam.** Where the cast is
   already in scope, deterministically reconcile any scene entity that
   *unambiguously* answers to exactly one cast member (by sheet name, uid, or
   alias — `agents/common.py:2919` `character_scene_keys` is the existing
   vocabulary): set `entity.name = identity.name`, and add the displaced
   spelling to `entity.aliases` so prose and lookups still resolve it. Never
   touch the entity dict KEY (the eid). Two seams, both already doing sibling
   work:
   - the Director stage bodies, beside the existing `canonicalize_positions`
     calls (`agents/director.py:382`, `:3010`) — the earliest stage where the
     data becomes wrong, so the same turn's perception already sees one
     spelling;
   - an idempotent pass over the *standing* scene at commit, beside
     `_heal_attire_identity_keys` (`persist/commit_attire.py:724`) — this is
     what heals existing saves lazily (§ 7).

   Ambiguity guards carried over from the code that already learned them:
   two cast rows answering to one spelling → no reconciliation (the
   `subjects.py` rule: folding two beings into one is strictly worse); an
   alias that is another cast member's own name never matches (the "Yuki"
   guard, `persist/commit_attire.py:120-127`); and a cast entity's alias list
   is stripped of any spelling that is another cast member's name or uid.

2. **Make the alias fold reachable — as a fold toward the name, never a
   rename of the id-key.** In `canonical_subject_map`, entities whose `name`
   equals their eid (the common minted shape) currently skip alias folding
   entirely (`world/spatial_identity.py:315-323`). Hoist the alias loop so it
   runs for those entities too, with its own guards: the alias must be
   unambiguous (`len(alias_hits) == 1`, already present), must not itself be
   any entity's name (`alias_folded not in by_name`, already present), and the
   canonical name must be live under some *other* spelling (G3 preserved,
   § 6a). This never renames an entity's own id-key — the eleven-test class is
   about renaming id-keyed rows of objects, and the id-key here IS the
   canonical spelling — it only folds *additional* spellings onto it.

3. **Add `orientation` to `_SUBJECT_KEYED`** so the fold covers the ledger
   § 2b found missing. Its records are plain per-subject dicts; the
   first-writer-keeps rule of `normalize_scene_subjects` applies unchanged.

4. **Converge on one policy function.** `canonicalize_positions` (no aliases,
   positions only) and `_heal_attire_identity_keys` (aliases, attire only) are
   two hand-rolled copies of one policy whose *disagreement about aliases* is
   the precise cause of chat 82's split. Once the entity record is reconciled
   and the merge fold reaches aliases, both shrink to callers of — or are
   subsumed by — the single reconciliation pass. Do not leave three
   half-copies standing; that is how the next ledger gets a fourth.

With these in place the pipeline is: model writes whatever spelling it likes →
stage body reconciles the entity record and diff keys against the cast →
merge's existing cast-free fold sees an entity whose `name` is the sheet name
(and whose eid now differs from it, so the id-guard passes) and folds every
ledger key and subject-valued field onto it → commit persists a single-spelled
scene. The merge stays pure and cast-free; the authority lives where the
authority's data lives.

### 6a. Why this does not re-break the G3 eleven-test history

The eleven-test regression (`world/spatial_identity.py:296-303`) came from
folding on identity alone: a lone id-keyed object position (`"tardis"`) was
renamed to its display name, and carried lights, derived stations and
destruction cascades — which resolve by entity id — lost their rows. This
decision changes nothing for that shape: non-cast entities keep entity-name
canonicalism, the liveness gate stays, the id-guard still refuses to fold an
entity's id-key away on its own evidence, and the new alias reach folds *onto*
the id-key, never off it. Cast-mirrored entities newly fold only because their
`name` genuinely differs from their eid after reconciliation — which is the
two-live-spellings shape G3 was built to permit.

## 7. Migration story for standing scenes

**No schema change, no new field, no bulk migration.** The commit-side
reconciliation pass is idempotent and runs on the standing scene every turn —
the established pattern (`dedupe_regions` "runs on read and must stay
idempotent, since a checkpoint restore replays it"; `_heal_attire_identity_keys`
heals existing saves by merging, its docstring says so). Consequences, against
`docs/guides/DATABASE.md:136`'s checklist:

- **Commit path**: the pass runs there; the next committed turn of any
  affected chat heals it. Measured blast radius: 7 scenes re-key ledger
  entries for exactly the beings in § 4's table; 54 of 61 cast-mirrored
  entities are byte-identical no-ops.
- **Restore path / checkpoints**: a restored pre-decision scene carries the
  old spellings and heals on its first committed turn; in the interim the
  read-side `room_of` repair keeps it fully playable. No checkpoint format
  change.
- **Portable archive**: scenes export/import as-is; imported chats heal on
  first turn. No archive format change.
- **Branch/clone remapping**: nothing to remap — canonical spellings are
  names, not row ids, and eids are untouched.
- **Scenes "already folded the other way"**: § 2a — there are none. The
  entity-name fold never fired for a cast-mirrored being, so no standing scene
  depends on a divergent entity spelling as its ledger key convention. The
  four divergent entity *records* (chats 27, 65, 81, 82) get their `name`
  corrected and the old spelling demoted to an alias; prose already written
  with the honorific stays valid because the alias still resolves.

Durable stores OUTSIDE the scene blob that hold subject spellings —
`world_conditions` (§ 8), `subject_last_seen`, background-presence recognition
ledgers — are *not* rewritten by this change; they are read-side consumers and
each already resolves (or must resolve) through identity. Rewriting them is
per-store work with its own checklist exposure and is deliberately out of
scope here.

## 8. Relation to `docs/UNBUILT.md` § 1.65

§ 1.65 (`docs/UNBUILT.md:3003`) is the same identity gap surfacing in
`world_conditions`: subjects written as scene uids match no display name, so
the rows are inert. **Same authority, same vocabulary, separate landing.**
This decision supplies the answer 1.65's fix must use — canonical spelling for
a cast subject is the sheet name, and the resolution vocabulary is
`character_scene_keys`/`same_subject`, not a new one — but folding
`world_conditions` rows touches its own commit path, restore path and
branch/clone remapping, which is exactly why UNBUILT already scopes it as "its
own change with its own tests." Close 1.65 second, citing this note for
direction; do not widen this change to swallow it.

## 9. What I would NOT do, and why

- **Not thread cast into `merge_scene_with_diff` / `normalize_scene_subjects`**
  (§ 5C): couples a pure world-layer function to the database, taxes ~12
  production call sites (several castless by nature) and 36 test files, and
  moves the authority decision into the one module that cannot see the
  authority.
- **Not hoist the alias fold under entity-name canonicalism** (§ 5B): folds
  the wrong way for cast, strips a character of her own attire key, and
  oscillates against `_heal_attire_identity_keys` every turn.
- **Not rekey the entity dict (eid)** when reconciling: eids are the stable
  handles for carried lights, destruction cascades, derived stations and
  `world_entities` projection; renaming them is the eleven-test class.
  `name` changes; the key never does.
- **Not fix it with a prompt clause alone** (§ 5E): a leak-class defect needs
  a deterministic floor; a prompt is a literal guard and the failure rate of
  literal guards rises with how well the model writes.
- **Not run a one-shot database migration over live saves**: idempotent
  commit-time healing is the repo's proven pattern, keeps archives and old
  checkpoints valid without version-gating, and makes the repair testable as
  ordinary commit behaviour rather than as a script run once and deleted.
- **Not backfill `identity.name` from the entity record** ("the Director
  called her Dr. Sarah Moon, maybe the sheet should say so"): the sheet is
  authored configuration; a model does not get to rename a character by
  spelling them differently once. Chat 65's Garret/"Onlooker" is the
  reductio.
- **Not special-case honorifics** (strip "Dr."/"Lt." etc. and match): that is
  a rule shaped around this chat's instance. The class rule — an entity
  unambiguously answering to one cast member takes that cast member's name —
  covers honorifics, promotion labels, uids and snake-case ids alike without
  naming any of them.

## 10. How to verify this landed

A regression suite (full tier, `temp_db` where DB-backed) asserting:

1. **The chat-82 shape folds to the sheet.** Scene with entity keyed AND named
   `"Dr. Sarah Moon"` (alias `"Sarah Moon"`), cast sheet named `"Sarah Moon"`
   (alias `"Dr. Sarah Moon"`); diff writes `attire` under both spellings and
   `positions`/`poses`/`stations` under the honorific. After stage
   reconciliation + merge: every `_SUBJECT_KEYED` ledger *and* `orientation`
   holds exactly one key for her, spelled `"Sarah Moon"`; the entity record's
   `name` is `"Sarah Moon"`; its eid is UNCHANGED; `"Dr. Sarah Moon"` is in
   its aliases.
2. **Idempotence / no oscillation.** Running merge → commit-side heal →
   merge again on the result is a fixpoint: the second pass folds nothing
   (`normalize_scene_subjects` returns `[]`) and the scene is byte-identical.
3. **The TARDIS guard holds.** A non-cast object entity keyed `"tardis"`,
   named `"TARDIS"`, with only an id-keyed position, keeps that position under
   its id — no fold fires on identity alone (the eleven-test tripwire,
   re-asserted).
4. **The Yuki guard holds.** Cast A named `"Yuki"`; cast B whose aliases
   include `"Yuki"`. No ledger key of A's ever folds onto B, and B's entity
   aliases do not retain `"Yuki"` after reconciliation.
5. **The promotion shape (chat 65) folds to the sheet.** Entity named
   `"Onlooker"`, sheet named `"Garret"` with alias `"Onlooker"`, `positions`
   holding BOTH keys in different rooms: after the pass there is one
   `positions` entry, keyed `"Garret"`, holding the room that was already
   under the canonical spelling (first-writer rule of
   `normalize_scene_subjects` unchanged).
6. **Ambiguity still resolves to nothing.** Two cast rows answering to one
   spelling, or two entities claiming one alias → no reconciliation, no fold,
   and the scene is unchanged.
7. **Corpus convergence (manual, read-only).** Re-run § 4's measurement after
   one committed turn per affected chat: `split_ledgers` 7 → 0,
   `entity name != sheet name` 4 → 0, with the other 54 mirrored entities
   untouched.

When built: delete the corresponding UNBUILT entry in the landing commit, add
the `Design.md` conformance row, and update `canonical_subject_map`'s
docstring — its "IS the display name" sentence becomes a statement of an
enforced invariant with this note as its argument.
