# Audit: the `story/` package, read whole

Working notes in the register of
[`AUDIT_DIRECTOR.md`](AUDIT_DIRECTOR.md) and
[`AUDIT_SPATIAL.md`](AUDIT_SPATIAL.md). Every line of all twelve modules
(12,251 lines) was read end to end; nothing here was changed.

**Baseline:** working tree at `4f33b17` (2026-08-17), `story/` unmodified.
Every `file:line` is as of that tree.

**One drift already:** while this audit was being written, a concurrent
change inserted 16 lines into `disguise_breaks_recognition`
(`story/scene.py:908`, a fail-closed branch for `conceals_identity is None`).
Every `story/scene.py` citation below line 908 is unaffected; every citation
above it is 16 lines lower than the current file. Nothing in this audit
touches that function or changes a verdict because of it.

| module | lines | what it owns |
| --- | --- | --- |
| `story/attire.py` | 2,619 | clothing by region: the pure coverage/ladder/displacement model |
| `story/importers.py` | 2,618 | card + lorebook ingestion, the authoring generators, the resumable tree generator |
| `story/scene.py` | 1,996 | the scene blob's accessors, cast rosters, per-chat config ladders, disguise/transformation/awareness/restraint reads |
| `story/character_schema.py` | 1,634 | the versioned character/persona card, its normalizers and its accessors |
| `story/couriers.py` | 1,090 | a message with a body on a route; caravans |
| `story/carriers.py` | 696 | the report envelope: who holds what, and how telling copies it |
| `story/artifacts.py` | 565 | a claim nailed to a wall |
| `story/greetings.py` | 413 | greeting extraction and "Start story now" |
| `story/dialogue_colors.py` | 248 | a colour per speaking character |
| `story/lore_structure.py` | 242 | the tree a SillyTavern book draws in its entry titles |
| `story/authored_events.py` | 124 | player-scheduled future beats |
| `story/__init__.py` | 6 | the package note |

Method for every "no caller" claim below: an AST pass collected all 481
top-level names defined in `story/`, then one regex pass over all 627
first-party `.py` files (repo root plus the fourteen source packages and
`tests/`) counted word-boundary references per file, bucketed
own-module / other-production / tests. Claims that a value is *written* but
never *read* were additionally checked against `web/app.py`, `static/js/`
and the language packs by hand. Live measurements read `engine.db` through
`sqlite3.connect("file:engine.db?mode=ro", uri=True)` and wrote nothing.

---

## Part 1 — findings. FLAGGED, NOT FIXED.

### Configuration nothing reads

#### 1. `allow_npc_initiative` and `stop_on_player_address` are host-visible settings with no reader

`story/scene.py:1570` and `1572` declare both in `DEFAULT_INTERACTION_CONFIG`.
`web/app.py:4124` and `4126` accept, coerce and persist both on
`PUT /api/chats/{cid}/dialogue_config`. `static/js/settings.js:262` and `264`
render a checkbox for each and `settings.js:462-463` post them back. Nothing
in `agents/`, `persist/`, `world/`, `mind/` or `llm/` ever reads either key —
zero references outside the default dict, the route and the two checkboxes.

Their four neighbours in the same panel are all live:
`allow_npc_to_npc_dialogue` (`agents/loops.py:520`),
`stop_on_question_to_player` (`agents/loops.py:853`),
`silence_ends_exchange` (`agents/loops.py:904`),
`promote_after_addressed` (`persist/commit_background.py:1386`). Two of six
are theatre, sitting in the same table as four that work, which is the worst
possible arrangement: a host who unticks "stop on player address" has every
reason to believe the loop changed behaviour.

This is the exact shape `CLAUDE.md` names ("a promotion threshold with a
route, an editor and a test, and no reader at all"), twice over.

#### 2. `max_speakers_per_round` is a default with no route, no editor and no reader

`story/scene.py:1553`. `dlg_put` (`web/app.py:4118-4145`) does not carry it,
so it can never be set to anything but 1; nothing reads it. Only two tests
mention it, and both merely include it in a fixture dict.

#### 3. `greetings.EXTRACTOR_VERSION` is a version stamp nothing stamps or checks

`story/greetings.py:31`. Zero references anywhere, including tests. Both
producers of a greeting record write `"extractor_version": None` outright
(`greetings.py:393`, `importers.py:276`), and `start_story` reuses a stored
`rec["extraction"]` (`greetings.py:218`) with no version test at all. So the
one thing the constant exists for — refusing an extraction produced by an
older extractor — cannot happen, and a card carrying an extraction from any
past version is replayed as current. `greetings.py:161-165` explicitly
reasons about stored extractions bypassing the schema; it is the same
exposure, and the version field that would have bounded it is inert.

#### 4. `attire._DIFF_KNOWN_KEYS` is an unread second copy of a dispatch list

`story/attire.py:1214-1215` enumerates `("wearing", "add", "remove",
"replace", "state", "conditions", "coverage", "regions", "notes",
"placement")`. Nothing reads it — the actual dispatch is the `if name ==`
chain in `coerce_diff_shape` (`attire.py:1278-1370`). The two agree today;
the constant is a hand-maintained mirror with no test binding it and no
consumer to break when it drifts.

### Dead code, and parameters that are not parameters

#### 5. Five public symbols with no caller at all

| symbol | site | tests |
| --- | --- | --- |
| `salience_of` | `story/scene.py:1352` | none |
| `base_appearance_of` | `story/scene.py:1167` | none |
| `visible_appearance_payload` | `story/character_schema.py:1617` | none |
| `default_character_document` | `story/character_schema.py:649` | none |
| `default_persona_document` | `story/character_schema.py:684` | none |

`salience_of` is the notable one: a keyword-weighted salience heuristic
(`"attack"`, `"blood"`, `"betray"`…) that nothing has called in the tree, and
whose job has since been taken by `memory`'s own scoring plus the mint-time
`salience = 0.45 + 0.3*confidence` relation `AGENTS.md` documents. It reads
as live, sits between two live functions, and is the sort of thing a future
reader will "reuse" without noticing the engine already answers this question
elsewhere.

`character_export_document`/`persona_export_document` (`character_schema.py:1620`,
`1628`) ARE used; their `default_*_document` siblings are not, which is why
the pair is easy to mistake for one working set.

#### 6. `lore_structure.derive_knowledge(record, category=None)` — the parameter is never passed and never read

`story/lore_structure.py:195`. The body does not mention `category`; the two
production callers (`importers.py:1393`, `tools/repair_lore_structure.py:62`)
and all six test call sites pass one argument. It is the vestige of a design
the 19-line comment directly above it (`lore_structure.py:174-192`) argues
against at length — "Using the entry's `category` as a second signal was
tried and MEASURED WORSE, so it is deliberately absent." It is not absent; it
is a silent no-op in the signature, and the next reader who supplies it will
get exactly the behaviour the comment says was rejected, with no error.

#### 7. `carriers._crowd_index(cid, scene, frame_id)` ignores two of its three arguments

`story/carriers.py:482-495`. The body reads only `wget(cid,
crowds_model.CROWDS_WORLD_KEY, [])`. Its one call site
(`carriers.py:533`) passes `scene` and `frame_id`, which reads as "this
lookup is frame-scoped and spatially aware". It is neither — it is
frame-scoped only incidentally, because `crowds` is in
`db.FRAME_SCOPED_WORLD_KEYS` and `wget` redirects on the ambient
`active_frame_id` contextvar. Any caller outside a pipeline run gets the
present frame's crowds whatever it passes.

#### 8. `resolve_cast_colors`' `hue is None` branch cannot fire

`story/dialogue_colors.py:216-217`. `entries` only admits members with a
non-empty `uid` (`dialogue_colors.py:197-201`), and the seed is
`personality_digest(...) or uid`, so `_hue_from` never receives the empty
string, which is its only `None` path (`dialogue_colors.py:140-141`). The
identical guard in `auto_dialogue_color` (`:161-162`) CAN fire, because that
function accepts a falsy `uid`. Two guards that look like one rule; one of
them is unreachable.

#### 9. `greetings._strip_greeting_wrapping` computes a condition and does nothing

`story/greetings.py:410-412`:

```python
    if len(text) >= 2 and text[0] in "\"“" and text[-1] in "\"”" \
            and text.count('"') + text.count("“") == 1 + text.count("”"):
        pass  # ambiguous -- leave dialogue-opening greetings intact
```

A four-term condition whose whole body is `pass`. The function's own
docstring (`:398-400`) promises the opposite: "A utility model sometimes wraps
prose in a code fence, a leading label, **or whole-string quotes** despite the
prompt. Peel those without touching the prose itself." Quotes are never
peeled, and a leading label is never peeled either — only the fence is. Two
of the three behaviours the docstring claims do not exist.

#### 10. Patch debris

- `story/greetings.py:388` re-imports `hashlib` inside `generate_greeting`;
  it is already imported at module scope (`:13`).
- `story/importers.py:13` imports `EXTRA_PARTS_NOTE` from `llm.prompts` and
  never uses it.

### Lists kept in sync by hand, and not

#### 11. `sanitize_attire_items` + `_NON_ATTIRE_TERMS` exist twice, byte-identical, in two packages

`story/scene.py:42-58` and `persist/commit_attire.py:14-30` are the same nine
words and the same eleven-line function, character for character. Different
consumers use different copies: `scene.seed_initial_attire` (`scene.py:76`)
uses the scene copy, `agents/director.py:335,347` and
`commit_attire.py:632,649,656` use the commit copy (re-exported through
`persist/commit.py:90`).

`tools/project_check.py`'s duplicate-symbol check
(`check_duplicate_python_symbols`, `:76-99`) is **per file** — it walks each
module's own `tree.body` — so a cross-file duplicate is structurally
invisible to `make structure`. Adding a term to one list silently misses the
other.

Measured, live: the term list is already inadequate in a way this makes
harder to fix. Across the 69 scene blobs in `engine.db`, 560 worn garment
records, **10 of them name a submachine gun as clothing** — `_NON_ATTIRE_TERMS`
carries `"weapon"` and `"tool"` but no actual weapon nouns, and now there are
two places to add one.

#### 12. `_outfit_items` is defined twice in this package, with different semantics

`story/character_schema.py:397` and `story/importers.py:350`. Same name, same
purpose, and they disagree on two points: the schema copy accepts a `set` and
DEDUPES; the importers copy unwraps a dict (`{"wearing": …}` / `{"items": …}`)
and does NOT dedupe. Both feed the same field (`initial_outfit.wearing`) on
the same import path — `heuristic_character_sheet` builds the outfit with the
importers copy (`importers.py:384`), and `normalize_character_data` re-reads
it with the schema copy (`character_schema.py:443`). A duplicated garment
survives the first and is dropped by the second, which means the dedupe rule
is decided by which of two same-named helpers ran last.

#### 13. `PLAYER_TOKEN` is defined twice

`story/greetings.py:32` and `story/importers.py:224`, both `"{{PLAYER}}"`.
`greetings.py` already imports from `importers` (`greetings.py:342`), so the
second definition buys nothing and can drift. Both modules' comments explain
the token's contract, in different words.

#### 14. `guess_book_type`'s map contains two categories `guess_category` cannot return

`story/importers.py:1133-1140` maps `character → "characters"` and
`knowledge → "knowledge"`. `guess_category` (`:1097-1118`) returns exactly
one of `layout|mechanic|myth|event|location|other` — never `character`,
never `knowledge`. Two of six rows are unreachable, and the two categories
`guess_category` DOES return that are missing from the map (`myth`, `other`)
fall through to `"general"`. A reader adding a category to one function has
no signal that the other is the thing that must change.

### Silent tolerance of empty, missing, and unknown values

#### 15. Which card validations are universal and which are import-only — the map

This is the gap `CLAUDE.md` asks to be mapped. The answer is starker than
"import-only": **every warning in the package fires on exactly one route.**

`character_import_warnings` (`story/importers.py:538`) has one production
caller: `web/app.py:2368`, inside `POST /api/characters/import`. It reports
four things — an empty `psychology.drive.essence`, empty
`initial_state.goals`, an unset `psychology.capacity`, and body prose naming
a part that `embodiment.extra_parts` does not declare.

Every other path that can create or change a card reaches the database
without it:

| path | entry point | warns |
| --- | --- | --- |
| card import | `web/app.py:2368` → `import_character` | **yes** |
| AI generation | `web/app.py:2328` → `importers.generate_character:790` | no |
| blank card | `web/app.py:2335` `char_create` → `default_character_data` | no |
| hand edit | `web/app.py:2461` `PUT /api/characters/{cid}` | no |
| per-story card override | `PUT /api/chats/{cid}/characters/{ch}/card` | no |
| background promotion | `importers.draft_promoted_character:737` + confirm route | no |
| psychology fill | `importers.fill_character_psychology:870` | no |
| appearance fill | `importers.fill_appearance:949` | no |
| greeting launch | `greetings.start_story:177` | no |

The blank-card row is the sharp one. `default_character_data`
(`character_schema.py:613`) ships `{"essence": "", "expression": "", "taboo":
""}` and `"capacity": ""` and `"goals": []` — it produces, by construction,
precisely the sheet whose three warnings exist to catch, and says nothing.
`CLAUDE.md` records what that costs fifty beats later.

By contrast, the *coercions* are genuinely universal, because they run inside
`normalize_character_data`/`normalize_persona_data`, which every accessor
calls: extra-part menu enforcement (`_normalize_extra_parts:499`), the
capacity enum (`PsychologyProfile._capacity:249`), every float clamp
(`_profile_float:111`), the profile-list shapes (`_as_profile_list:38`),
shape repair (`repair_character_shape:915`), outfit region migration
(`_normalize_initial_outfit:412`), private-history coercion
(`_legacy_private_history:767`). Not one of them warns. Universal coercion
plus single-route warning is the package's whole validation posture, and it
means a card is silently corrected everywhere and questioned in one place.

#### 16. `_normalize_awareness_level` calls `dazed` "the MILDEST gate"; `dazed` is not a gate

`story/scene.py:948-956`:

```python
    """Casefold a level string to the enum. Unknown/garbage degrades to the
    MILDEST gate ('dazed') rather than vanishing; empty/awake -> 'awake'."""
```

`NON_AWAKE_GATED` is `frozenset({"asleep", "sedated", "unconscious"})`
(`scene.py:945`) and its own comment two lines above says so: `"dazed" is NOT
gated`. So an awareness level this enum cannot read produces a mind that
perceives normally and runs a full character step. That may well be the right
fail-open direction — but the comment states the opposite, and a future
reader hardening this will "restore" a gate that never existed.

The exposure is real rather than theoretical: the body specialist's sheet
does publish the enum (`language_packs/en/cards/system_prompts.json`,
`director_body`: "level ∈ {unconscious|sedated|asleep|dazed}"), and yet the
live database contains only `unconscious` and `dazed` — no `asleep`, no
`sedated` — across all 12 active awareness rows.

#### 17. `RESTRAINT_LEVELS` is a vocabulary no prompt publishes, read by a function that silently narrows

`story/scene.py:1065` declares `("held", "bound", "pinned", "encased")`.
Grepped over `llm/prompts.py` and every card in `language_packs/`: the words
`encased` and `pinned` as a *level enum* appear nowhere. What the body
specialist is actually told is a parenthetical of examples — "physical
restraint (bound, held hostage, grappled, pinned)" — with no `level ∈ {…}`
clause of the kind awareness gets one paragraph later in the same sheet.

`_normalize_restraint_level` (`scene.py:1071-1079`) then maps an empty level
to `"bound"` and **anything it does not recognise to `"held"`, the mildest
rung**. So "grappled" and "held hostage" — the two examples the prompt
itself offers — are both unreadable, and both land on the mildest reading.
`RESTRAINT_LEVELS` and `IMMOBILIZING_RESTRAINTS` have zero references outside
`scene.py` and zero in tests, so nothing anywhere notices.

This is `AGENTS.md`'s weather rule ("Extend `_SYNONYMS` rather than widening
an enum when a model writes a word this cannot read; a silent fall to the
default inverts the meaning of the beat") applied to a ladder that never got
the synonym table.

#### 18. `awareness_map` collapses several rows the way its stated sibling explicitly does not — measured live

`awareness_map` (`scene.py:1008-1023`) says it "Mirrors active_disguises" and
that where several rows name one subject, "the last wins". The last *by
rowid*: `awareness_conditions` orders `ORDER BY rowid` (`scene.py:974`).

`active_disguises` orders `ORDER BY started_at ASC, rowid ASC`
(`scene.py:453`) and its 16-line comment (`:440-479`) is entirely about why:
"with no ORDER BY that was whichever the scan happened to reach last: the
glamour appeared to work for a turn and then stop, because a different row
won." Awareness is the case that comment describes, unfixed — and awareness
is not in `SINGULAR_BODY_CONDITIONS` (`scene.py:519`, disguise and
transformation only), so `commit_entities._supersede_singular_conditions`
never collapses it either and rows genuinely pile up.

Measured against the live database, read-only:

```
active awareness rows: 12   subjects: 7   subjects with >1 active row: 2
  chat 23, 'hinami': rowid 82 unconscious@130, 86 unconscious@160, 89 dazed@185  -> map returns 'dazed'
  chat 27, 'hinami': rowid 149 unconscious@130, 153 unconscious@160,
                     156 dazed@185, 165 dazed@1250                                -> map returns 'dazed'
```

A body carrying two standing `unconscious` conditions reads as ungated. Here
rowid order and clock order happen to agree, so the outcome is defensible —
but that is luck, and it is exactly the luck the disguise comment says ran
out ("Equal `started_at` makes the ORDER BY a coin flip resolved by rowid").
`awareness_conditions`' own docstring cites this same chat as the reason it
exists; the collapsing reader beside it was not given the same rule.

#### 19. `apply_awareness_diff` emits a record shape missing the key the endings path is built around

`scene.py:1047-1049` builds `{subject, level, cause, rousable_by}`.
`awareness_map` (`:1016-1022`) builds the same four plus `condition_id`. The
whole point of carrying `condition_id` is stated at `scene.py:966-970` and
enforced at `agents/director_floors.py:374,409,466`: "an ending must re-emit
the SAME `condition_id` … a fresh id would INSERT a second row instead of
closing the first."

The one production consumer of the diffed map (`agents/narration.py:872`)
only asks `awareness_of`, so nothing breaks today. But the two producers of
"the awareness map" now have different shapes, and the field that goes
missing is the one whose absence opens a second condition row — the defect
finding 18 measures.

### Two spellings of one rule

#### 20. `attire._compact_garment_piece` and the inline block in `compact_line` are the same rule, written twice

`story/attire.py:2418-2437` is a helper that renders one garment as
`NAME(state;condition)=look`. `compact_line:2558-2596` renders a garment as
`NAME(state;condition)=look` — inline, 39 lines, same `_safe`, same
`re.split(r"[;—.]", …, 1)[0]` first-clause rule, same word-boundary
truncation, same `look_said` dedupe, same final `piece`/`described` join.

The helper serves only the zoned (torso) branch; the inline copy serves every
other region. `compact_line`'s payload is the sole path by which a garment's
appearance reaches prose (its own comment, `:2564-2572`), so a change to the
look rule that lands in one copy changes what the Director is told about a
torso and not about a skirt.

#### 21. `dialogue_colors.auto_dialogue_color` is a second derivation of `resolve_cast_colors`' rule, with no production caller

`story/dialogue_colors.py:151`. Zero references outside its own module except
in tests (18 of them). Production colour resolution goes through
`resolve_cast_colors` (`:177`), which recomputes the same chain inline —
`_hue_from(personality_digest(...) or uid)` then `_hex_from_hsl` — plus
`_spread`.

`tests/test_dialogue_color_wiring.py:70` asserts the API's answer *equals*
`auto_dialogue_color(...)`. That holds only because the fixture cast has one
member, so `_spread` returns the hue unchanged (`:235`). The moment the
oracle and the implementation disagree — a second speaker, or a change to
`AUTO_LIGHTNESS`/`AUTO_SATURATION` reaching one and not the other — the test
that is supposed to pin the wiring becomes the thing that breaks.

Related: `_hex_from_hsl(hue, saturation=AUTO_SATURATION, lightness=AUTO_LIGHTNESS)`
(`:146`) has parameters no caller ever overrides.

#### 22. `character_projects` hard-codes the project cap

`story/character_schema.py:1541`: `if len(out) >= 2: break`, while the
docstring two lines earlier says "the runtime cap (`affect.PROJECT_CAP`)
holds the same line" and `mind/affect.py:1375` is `PROJECT_CAP = 2`.
Mitigated — `tests/test_projects.py:204` asserts
`len(character_projects(sheet)) == PROJECT_CAP`, so raising the constant
fails the suite. Recorded because the mitigation is a test rather than a
read, and the docstring already asserts a relationship the code does not
express.

### Comments describing behaviour the code no longer has

#### 23. `guessed_spans` documents a commit seam that does not exist — and 20% of live garments would trip it

`story/attire.py:249-271`: "Returns the garment names, once each. **For the
commit seam to hand to the Director**, which CAN say what a garment covers
and is the only stage with the fiction in front of it."

No production caller. `guessed_spans` and `span_is_a_guess` (`:221`) are
referenced only by each other and by `tests/test_attire_displacement.py:724,731`.

`docs/UNBUILT.md:2879-2882` already records this correctly and in the right
words ("It is **unwired** — no production caller, only tests — and its own
docstring says where it belongs"). The docstring itself was never softened,
so a reader who meets the function before the register believes the feedback
loop is closed.

Measured, read-only, over `engine.db`: of 560 worn garment records across 69
scene blobs, **110 (20%) carry a span the cue table guessed** — neither
`placed` nor `covered_zones` set, and `span_is_a_guess` true. The most
frequent are `Nagajuban` (20 records), `Zōri` (4), `Tabi` (4), `fitted tank
top` (21), `charcoal pinstripe suit` (6). A *nagajuban* is a full-length
under-kimono; all 20 records sit on the torso alone, so those bodies report
legs and groin bare while wearing one.

#### 24. `decisive_targets`' documented attribution ladder has three tiers; the code has six, in a different order

`story/attire.py:1414-1421` documents:

> Attribution, in order … 1. the garment. … 2. first person, but only in the
> player's own input … 3. a name, when the sentence names exactly one body
> and no garment.

`_attributed_targets` (`:1455-1544`), the shared implementation both
`decisive_targets` and `process_targets` call, runs: (1) garment phrase
(`:1476`), (2) **genitive owner** — `<Name>'s tank top` (`:1482-1501`), (3)
**head noun, when exactly one body carries it** (`:1502-1507`), (4) first
person, player only (`:1508`), (5) sole name, with the
`_OTHERS_POSSESSIVE` re-attribution (`:1511-1538`), (6) player default on
ambiguity (`:1542`). Two whole tiers are undocumented and first-person has
moved from second to fourth. The docstring was written for the function
before `_attributed_targets` was extracted, and describes the shape it had
then.

#### 25. `attire.py`'s own header names a failure the cue tables still produce

The module header (`:46-51`) is emphatic that `waist` and `groin` must stay
separate because "a body wearing nothing but an obi reports its groin as
COVERED — and a dress whose span stopped at the waist reports it as BARE".

Two cue-table entries reproduce that failure from the other side. Verified by
running the pure functions:

```
region_of("girdle-cloth")        -> 'waist'      (it is listed under groin, attire.py:112)
region_of("a silk girdle-cloth") -> 'waist'
attaches_only("a leather cord belt") -> True     ('cord' is in both tables)
```

- `"girdle-cloth"` was added to the **groin** cue list (`:112`), but
  `"girdle"` sits in the **waist** list (`:108`) and matches the same string
  at the same offset. `region_of`'s tiebreak is `if best_at is None or
  match.start() > best_at` (`:216`) — strictly greater — so on a tie the
  region that comes first in `_REGION_CUES` order wins, and `waist` precedes
  `groin`. The groin entry is unreachable: a body in a girdle-cloth reports
  its groin bare.
- `"cord"` is in `_REGION_CUES["waist"]` (`:108`) **and** in `_ATTACH_CUES`
  (`:173`). `attaches_only` wins in `normalize_regions` (`:443-444`), and an
  attaching garment covers nothing by definition (`concealing_garments:621`),
  so any belt whose name contains "cord" is worn at the waist and conceals
  it not at all.

Both are one-word fixes; both are invisible without running the function,
which is the point.

### Frame scoping

#### 26. `scene.extant_cast(chat_id, frame_id=None)` accepts a frame and ignores it

`story/scene.py:143-161`. The parameter is never referenced in the body; the
query is `WHERE cc.chat_id=? AND cc.status NOT IN (…)` with no
`chat_char_frames` join at all.

Its sibling `active_cast` (`:164-194`) honours `frame_id` properly, LEFT
JOINing `chat_char_frames` and preferring the override — and its docstring
explains why that matters ("a character genuinely can be simultaneously
alive/active in one frame and dead/dormant in another"). Three production
callers pass a real frame to `extant_cast` and get the base rows back:

- `world/gaps.py:123`
- `world/subjects.py:106`
- `story/carriers.py:400` (via `_carriers`, therefore `_cast_index`,
  therefore `apply_tellings`, `run_couriers` and `run_artifacts`)

Consequence in this package: a character whose `chat_char_frames` row marks
them `departed` in the current era is still a carrier, a telling listener, a
courier addressee and an artifact reader in that era. `carriers._carriers`'
own docstring (`:376-385`) is a careful argument about *why* extant rather
than active cast is the right roster — the argument is right and the frame
half of it silently does not run.

#### 27. The player's carrier state is the only carrier home that is not frame-scoped

`carriers.PERSONA_STATE_KEY = "persona_carrier_state"` (`story/carriers.py:66`),
written through `wset` (`:353`) and read through `wget` (`:334`). It is
**not** in `core/db.py`'s `FRAME_SCOPED_WORLD_KEYS` (`:24-47`) — where
`crowds`, `couriers` and `artifacts` all are, each with a comment explaining
that a rewind or a branch must not inherit the other era's road.

Every other carrier's state is per-era: a cast member's reports go through
`set_char_state(..., frame_id=frame_id)` (`carriers.py:355`), crowds' hearsay
rides the frame-scoped `crowds` key, couriers and artifacts likewise.
`save_state`'s docstring (`:342-348`) says its whole purpose is that "every
reader below is indifferent to which of the two it was handed" — they are
indifferent to the *storage*, and the two homes have different era
semantics.

So the player alone carries what they learned in one era into another, and a
checkpoint restore that rolls the world back does not roll back what the
player's envelope holds.

### Tests that assert on source layout or by absence

#### 28. `tests/test_carriers.py` asserts over module source text, three ways

- `:158-159` — `source = inspect.getsource(carriers)`, then
  `assert "chat_complete" not in source and "providers" not in source`.
  Assertion by absence over text: it passes for any spelling that avoids
  those two substrings (an aliased import, a call through
  `llm.llm_quality.complete_validated_json`, or a provider reached through
  one of the modules `carriers.py` already imports — `world.degradation`,
  `world.living_world`, `story.scene`). The property it means to protect —
  "this floor makes no model call" — is not the property it tests.
- `:222` — `gate = body[body.index("said nothing this beat")]`. This indexes
  a string with an int, so `gate` is a **single character**, and it is never
  read again. The line's only effect is that `.index` raises if the substring
  is absent. Read as written it looks like a slice; it is not one.
- `:222-228, 257-258` — the same test then asserts four literal source
  spellings, including `'speaker.get("crowd") is None and speaker_key not in
  spoke'`. Extracting that condition into a named predicate — the ordinary
  refactor — fails the test while the behaviour is unchanged; deleting the
  runtime effect while leaving the string passes it. This is the sibling of
  the memory note *Literal guards fail when models rewrite*, pointed at our
  own source instead of a model's prose.

#### 29. Two more layout assertions in this slice's tests

- `tests/test_disguise_hides_extra_parts.py:132-138` slices
  `agents/perception.py`'s **text** from `"def _composer_extra_parts"` to the
  next `"\n\n\n"`, then asserts call ORDER by comparing `str.index` results.
  A blank-line change or a helper extraction breaks it. Same class as
  `AUDIT_DIRECTOR.md` finding 11, in a different file.
- `tests/test_attire_authoring.py:619-627` asserts exact substring COUNTS in
  `static/js/editors.js` and `static/js/components.js`
  (`editors.count("f.outfit_regions = fAttireGarments(") == 2`, `… == 4`).
  A third editor surface, or one refactored to a loop, fails a test about
  attire authoring for reasons that have nothing to do with attire.

### Cross-boundary, recorded here because this package's ledger is the casualty

#### 30. The attire identity-key heal merges `wearing`/`state` and drops `regions`

`persist/commit_attire._heal_attire_identity_keys:32-104` folds an attire
record keyed by a uid or alias onto the display-name key, merging field by
field — but only `for field in ("wearing", "state")` (`:94`). The duplicate
record's `regions` — the authoring surface, and the only place garment
`state`, `condition`, `covered_zones`, `placed` and `attaches` live — is
dropped with the popped record.

`story/attire.rederive_entry` (`:2362`) then rebuilds `regions` from the
merged flat `wearing` through the cue tables, so the ledger stays
*self-consistent* while every per-garment fact the dropped record held is
gone: a loosened, wine-stained, hand-placed kimono returns as a pristine
torso-anchored one. The heal reads as lossless because the invariant it
restores (all three representations agreeing) is restored.

Measured: **5 of 203 attire bodies in the live database are keyed by a uid**
(`char_…`/`character:…`/`persona_…`) rather than a display name, so the fold
is a live path, not a hypothetical.

Related, same key space: `scene.seed_initial_attire` (`scene.py:70-85`)
refuses to overwrite only on `if name in ledger` — an exact display-name
match. Its three attach/promotion callers (`web/app.py:2942`, `:3300`,
`:3445`) and `commit_background.py:1318` run outside the commit fold, so a
body whose live ledger currently sits under its uid can be seeded a second,
authored record under its name. The `CLAUDE.md` invariant ("no card read or
edit may overwrite clothing already changed in the story") is not violated —
nothing is overwritten — but two records for one body is how the ledger got
into the state finding 30 exists to repair.

---

## Unverified suspicions

Recorded separately because I could not close them.

- **`recent_events_for_observer` admits frameless events into every frame.**
  `scene.py:1266-1271` filters `(e.turn_id IS NULL OR t.frame_id IS ?)`. An
  `events` row with a NULL `turn_id` therefore reaches every frame's "what
  just happened" context, which the docstring above it calls an
  "information-boundary leak across frames, not just noise". I could not find
  a writer that produces a NULL `turn_id` events row, so the branch may be
  unreachable; I did not exhaustively read every `INSERT INTO events`.
- **`_positive_presented_appearance`'s rejoining rule.** `scene.py:772`
  chooses `". "` or `"; "` from `seps[:-1] or ["."]`. With a single kept
  clause `seps[:-1]` is empty, so the fallback makes the joiner `". "` — but
  with one clause there is nothing to join, so the choice cannot matter. With
  two kept clauses separated by `;` the joiner becomes `"; "`. I believe this
  is correct in every reachable case but did not enumerate them.
- **`interaction_limits` preset ties.** `scene.py:1616` picks
  `min(presets, key=abs(item[0] - value))`; on an exact tie (`value == 12.5`
  is impossible after `int()`, but `value == 37` is not a tie and `value ==
  12` picks 0 over 25 by one) Python's `min` keeps the first. Deterministic,
  possibly not intended, no evidence either way.
- **`authored_events.resolve_authored_events` on a summary with no content
  tokens.** `authored_events.py:106` computes `covered = bool(stoks) and …`,
  so a summary whose every word is a stopword can never be covered and always
  burns its two requeues before going `stale`. I did not check
  `agents.common._content_tokens`' stoplist to see whether such a summary is
  reachable from the `scheduled_assertions` schema.

---

## Part 2 — what the code actually does, module by module, against the docs

Verdicts follow `AUDIT_DIRECTOR.md`: **RIGHT** / **STALE** / **LOST**.

### `story/scene.py`

Four unrelated jobs live here and only three of them are "the scene".

1. **Cast rosters.** `active_cast` (frame-aware), `extant_cast` (frame-blind,
   finding 26), `all_cast_name_to_id`, `chat_character_sheet`, plus the
   `chat_chars.status` writers. The three-questions comment (`:120-140`) —
   "does this person exist / are they in the scene / should the engine spend
   a call on them" — is an accurate description of what the two rosters
   answer, and `DEPARTED_STATUSES` is honestly labelled as a status nothing
   writes yet.
2. **The scene blob.** `get_scene` materialises defaults, strips
   `NON_ENTITY_FIELD_KEYS` debris from `entities`/`positions` on read
   (`:374-380`), and seeds initial attire exactly once, on first
   materialisation (`:392-393`).
3. **Condition readers.** Disguise, transformation, awareness, restraint —
   each a `world_conditions` query collapsed to a per-subject map, plus the
   pure helpers perception consumes (`conceal_disguised_parts`,
   `disguise_breaks_recognition`, `disguised_visible_appearance`,
   `transformed_sheet`/`_true_appearance`/`_parts`).
4. **Per-chat configuration ladders.** `dialogue_config`, `reaction_config`,
   `background_config`, `promotion_config`, `player_authority`,
   `style_guide`/`weather_severity`, `fiction_model`, `simulation_clock`,
   `OFFSCREEN_LIFE_LADDER`.

Plus one function that belongs to none of them: `_ability_mod` (`:1361`), a
Director causality helper, defined here and imported into
`agents/director.py:48`. `AUDIT_DIRECTOR.md` lists it among "the four
monkeypatch targets … all still defined in `director.py`'s own globals" —
true of the *binding* (which is what the monkeypatch needs) and not of the
definition. Worth knowing before the next Director split moves something.

**Docs: RIGHT, with two exceptions already filed.** `AGENTS.md`'s rows for
awareness (`awareness_conditions`, `awareness_map`, `NON_AWAKE_GATED`),
off-screen life (`OFFSCREEN_LIFE_LADDER`, `normalize_offscreen_life`,
`offscreen_life_allows`), background config (`max_reactors` default 1,
`scene_life` default `off`), initial outfit (`seed_initial_attire`, seed once
and never reset) and perception (`recent_events_for_observer`) all match the
code clause for clause. The exceptions are findings 16-18 (awareness) and 17
(restraint), and neither is a doc error — the maintained docs simply do not
describe these two vocabularies at all, which is how they got this far.

`Design.md` row "Authored initial outfit with live story attire" —
**RIGHT**. `initial_outfit` is separated from `embodiment.visible` by
`_coerce_appearance` (`character_schema.py:842-854`, which pops `outfit` /
`clothing` / `attire` out of `embodiment` and top level into
`initial_outfit`), seeds `scene.attire` once through `seed_initial_attire`,
and every one of the five production seed sites is guarded by the same
`if name in ledger: return False`.

`CLAUDE.md`'s identity-lock claim — **RIGHT**, and enforced outside this
package: `web/app.py:3676` refuses a name change and `:3684` refuses a uid
change on the per-story card route.

### `story/attire.py`

Pure functions over dicts, database-free — `AGENTS.md` says it must stay so,
and it does: the only import is `re`. Six layers:

- **placement** — `region_of` / `regions_covered` / `attaches_only` /
  `span_is_a_guess` over three hand-written cue tables (`_REGION_CUES`,
  `_SPANNING_CUES`, `_ATTACH_CUES`);
- **normalisation** — `normalize_regions` → `dedupe_regions` →
  `_sync_spanning_garments`, the read-path heal that makes one garment across
  five regions behave as one garment;
- **identity** — `resolve_garment`'s four narrowing tiers, with the
  head-noun tier optional so a MERGING caller is stricter than a
  note-ROUTING one;
- **the ladder** — `advance` / `apply_flat_change`, with the clamp inverted
  (a resolved `removed` lands unless `process` prose says otherwise);
- **displacement** — `covered_zones` at region grain, `zones_of`,
  `apply_coverage_changes`, and the `coverage_removal_escalations` steal
  guard;
- **rendering** — `describe`, `perceptible_region_surfaces` (the stricter
  per-observer projection), `compact_line` (the Director's fixed-shape,
  cache-friendly line), `flat_wearing` / `flat_state` / `rederive_entry`.

**Docs: RIGHT** on every checkable clause. `AGENTS.md`'s attire row — waist
and groin separate, `regions_covered` spanning, `_sync_spanning_garments`
after any rebuild, regions as the only authoring surface with `wearing`
derived, `resolve_garment` on every incoming handle, tiering deliberate
because `dedupe_regions` MERGES, `dedupe_regions` idempotent on read,
`coerce_diff_shape` run at commit as well as validation, `attire.py`
database-free — every one verified in source. `Design.md`'s three attire rows
likewise.

Two doc/code frictions worth naming:

- **`initial_outfit.state` is described as retired outright and is still
  consumed.** `AGENTS.md`: "`initial_outfit.state` is retired — what happened
  to a garment is that garment's `condition`."
  `character_schema._normalize_initial_outfit:445` still returns it
  ("Existing values are preserved, never extended" — a softer claim than the
  row), and `scene.seed_initial_attire:77-81` still copies it into the live
  ledger's `state`, where `rederive_entry:2391-2393` will preserve it forever
  because `is_derived_state_note` does not recognise authored prose.
  Retired as an authoring surface; not retired as an input. **Row STALE by
  omission**, code correct.
- **`Design.md`'s "the Director is given an explicit `exposed` list and told
  it is the whole truth about bare skin"** is true of the payload builder,
  not of this module; `exposed_regions:751` only answers for regions the
  ledger actually mentions, which is the right behaviour and a narrower claim
  than the row reads as making.

### `story/character_schema.py`

Two normalizers (`normalize_character_data`, `normalize_persona_data`), each
with a native branch and a legacy branch, plus ~35 accessors that all call a
normalizer first. Everything downstream of a card goes through here, which is
why the accessors are as expensive as they are — and why
`character_name_from_text` (`:1272`) exists, memoising the name derivation on
the raw sheet TEXT rather than re-implementing it.

The shape-repair machinery is the interesting half: `repair_character_shape`
(`:915`) lifts canonical sections that landed inside another section and
folds a flattened identity back, using `_content_weight` (`:897`) to tell a
model's emitted skeleton from its real content. It runs on READ, so damaged
sheets heal without a migration. `_as_profile_list` / `_is_profile_map`
(`:38`, `:90`) recover four different spellings of a profile list including
the bare-number map that "read as populated and named nobody".

Name matching lives here too and is genuinely load-bearing:
`name_boundary_pattern` (`:1201`) decides per-NAME rather than per-language
whether `\b` applies, and `fold_identity_key` (`:1233`) keeps non-ASCII
letters so two Japanese names no longer fold to the empty string and compare
equal. Both are firewall infrastructure sitting in a card module; both are
correctly described by their own comments.

**Docs: RIGHT.** `AGENTS.md`'s rows for character format, psychology,
capacity (`psychology.capacity` stored `""` when unauthored, never backfilled
— verified at `:247` and `:618`), extra body parts (`EXTRA_PART_ASPECTS`,
`_normalize_extra_parts`, `at` reusing `attire.REGIONS`, `through_clothing`
defaulting true) and `character_offscreen_agent` (author-owned, default
false) all hold.

One drift not worth a finding: the legacy branch's `simulation` dict
(`:1057-1062`) omits `curiosity`, which the native default carries
(`:562-563`). `character_curiosity` reads it through `_profile_float(...,
0.5)` so a legacy sheet gets the same value the default would have given it —
correct by accident of the accessor rather than by construction.

### `story/importers.py`

Four things share this file: card import (PNG chunk extraction, native
round-trip, heuristic sheet, AI reinterpretation), the authoring generators
(`generate_character`, `generate_persona`, `fill_character_psychology`,
`fill_appearance`, `draft_promoted_character`), lorebook import, and the
resumable lorebook-tree generator (`_GEN_OWNER` through
`apply_lorebook_plan`, ~840 lines).

The recovery discipline is the module's strongest work and it is consistent:
`_jparse`'s escalating repair, `_reinterpret_entries`' two-step
repair-then-keep-the-source (one bad batch used to lose a 300-entry book),
`_json_arrived_whole` distinguishing a salvaged object from a complete one on
a path a human is about to read, `_normalize_entry_ops` re-anchoring every op
onto its stub so a model that drops `outline_index` cannot misfile lore, and
`_gen_reap_orphans` classifying a `running` row owned by a dead process as an
interruption with no staleness timeout.

**Docs: RIGHT.** `AGENTS.md`'s lorebook-generation row (`generate_lorebook_plan`,
`resume_lorebook_plan`, `apply_lorebook_plan`, the `generator_lorebook*`
prompts, `lore_gen_jobs`, the job routes) matches. `DATABASE.md`'s
`lore_gen_jobs` paragraph is accurate down to the status vocabulary
(`running|interrupted|failed|ready|applied|cancelled`), the per-process
`owner` token, `params` holding the whole request including the raised
timeout, and pruning to `LORE_GEN_KEEP_PER_BOOK` on create.

`Design.md`'s "Generated body and clothing" row is RIGHT, including
`beneath` being stripped when not opted in (`:1048-1055`) — and the code is
stricter than the row, refusing to amputate an authored `extra_parts` list
the model merely omitted (`:1039-1045`).

### `story/lore_structure.py`

240 deterministic lines that recover the tree a SillyTavern author drew in
the `comment` field with rule characters, and derive `knowledge_tag` /
`knowledge_range` / `knowledge_locations` from where the author filed each
entry. `_matches`' whole-word rule (`:160-171`) and its recorded failure —
`"author"` matching `"AUTHORITY"`, deleting a whole power system from what
anyone in that world can know — is the best-documented near-miss in the
package.

**Docs: RIGHT**, in the sense that no maintained doc describes this module at
all beyond `AGENTS.md` naming `importers.py` as the lorebook-import owner.
The module's own header is the specification and the code matches it. The one
defect is finding 6.

### `story/carriers.py`, `story/couriers.py`, `story/artifacts.py`

One envelope shape (`world_event_id`, `claim`, `kind`, `occurred_at`,
`hops`, `retellings`, `told_by`, `provenance`) and four bodies that move it:
a person who walks (`carriers`), a crowd that walks (`world/crowds.py`), a
rider or caravan on a route (`couriers`), and a thing nailed to a wall
(`artifacts`). The two counters stay apart deliberately — `hops` for distance
(free) and `retellings` for mouths (the only thing that degrades) — and both
`artifacts.reading_copy` and `couriers._copy_of`'s sealed branch encode the
same rule from opposite ends: writing and reading are copies, not mouths.

Every refusal is deterministic and none is left to a model: the speaker must
hold the report, must have spoken this beat, must share a room, must not
exceed `TELL_FANOUT_CAP`; a courier departs only from its sender's own room
along a `passable_path` the graph can actually walk; an artifact is posted
only where its poster stands and refuses every read once torn down. The
invented-claim path (`_invented_claim:446`) is the one asymmetry, and it is
asymmetric only at the source — the speaker's own row says `invented`, the
listener's copy is shaped exactly like a copy of the truth, and nothing a
mind can read marks it false.

**Docs: RIGHT on the physics, and `Design.md`'s living-world row now
understates the floor in three ways.** The row says C's floor "copies only a
non-empty public `witnessed` surface to a registered character actually
co-located with the fired event". Since then the code has added:

1. **the player** — `persona_entry:307` and `_carriers:421-423` make the
   persona a carrier with its own state home, because "a body standing in the
   room where something happened learns it" and in a single-player engine the
   likeliest sender of news was structurally unable to send anything;
2. **arrival surfaces** — `advance_carriers:159-172` admits surfaces that
   landed here on an EARLIER beat and are still standing, bounded by
   `ARRIVAL_SURFACES`, because consequences fire off-screen in rooms chosen
   for being empty;
3. **crowds** — `_crowds_acquire:249` puts surfaces into a standing crowd, a
   lane that was previously unreachable except by an explicit Director
   telling that never came.

All three are documented in the code's own comments with their measurements.
The `Design.md` row is **STALE (understated)**, not wrong. `AGENTS.md`'s
carrier row is closer and still says "only a registered character physically
at that location acquires the current floor", which the persona path now
exceeds.

The one genuine boundary defect is finding 27 (the persona's home is not
frame-scoped while every other carrier's is).

### `story/greetings.py`

`greeting_interpret` is to a card's first message what `director_interpret`
is to player input: one bounded parse, cached on the card. The module's real
content is the identity floor around it. `_PLAYER_SLOT` (`:49-53`) catches
both `{{PLAYER}}` and the bare words "the player" — the latter because three
of four live seeds in "Run!" reached The Doctor's memory saying "The Doctor
knows **the player** was being chased by a Dalek", the engine's own
vocabulary at salience 1.0 inside a fictional mind. `player_handle_for`
(`:80`) routes through the same `_unknown_actor_label` every perception path
uses, so a strangers-meeting greeting cannot hand over the player's name on
beat zero. `_SEED_SALIENCE_MAX` (`:166`) caps a seed just under the 0.72
archive floor, with the reasoning — including that `contrast_memory` scores
`salience + 0.4 * (age / current_turn)`, so an uncapped seed's chance of
intruding unbidden GREW with story length — written out beside it.

**Docs: RIGHT.** `Design.md` row 160 credits this module as one of the two
places `known` was ever seeded, which matches `start_story:242-243`. The
defects are findings 3 (`EXTRACTOR_VERSION`) and 9 (the no-op quote branch).

### `story/dialogue_colors.py`

Three rules, all sound: the colour is never stored on a turn (only the
speaker is, and `events.content.dialogue_log` already carries that), hue is
free while lightness and chroma are clamped for legibility over a
60%-transparent panel, and distinctness is a property of the CAST so
collisions are spread in cast order by `resolve_cast_colors`. `blake2b`
rather than `hash()` because the builtin is salted per process.

**Docs: RIGHT** — no maintained doc describes this module; its header is the
specification. Findings 8 and 21.

### `story/authored_events.py`

124 lines giving a player-narrated future beat ("the elevator crashes next
turn") a durable home in `scheduled_events` as `kind='authored_event'`, fired
by TURN INDEX rather than sim-clock time, with bounded re-queueing so a beat
the resolution failed to enact is never silently dropped. Coverage is judged
by content-token overlap (`_COVERAGE_RATIO`), never a keyword list. Stable
ids keyed on the minting turn make a rerun idempotent.

**Docs: RIGHT** — described nowhere in the maintained set; the module header
is the specification, and `persist/commit.py:187-201` wires both halves as
described.

### Cross-document verdicts

| document | scope | verdict |
| --- | --- | --- |
| `CLAUDE.md` — three physical domains kept distinct | `embodiment.visible.summary` / `initial_outfit` / `scene.attire` | **RIGHT** — separated on read by `_coerce_appearance:836`, seeded once by `seed_initial_attire:61`, mutated only through commit |
| `CLAUDE.md` — no card read or edit overwrites clothing changed in the story | 5 production seed sites | **RIGHT**; see finding 30 for the key-space caveat (a second record, never an overwrite) |
| `CLAUDE.md` — no card edit may rekey identity name or uid | `web/app.py:3676`, `:3684` | **RIGHT** |
| `AGENTS.md` § Character/persona format | `story/character_schema.py` | **RIGHT** |
| `AGENTS.md` § Initial outfit / live attire | `initial_outfit` + `seed_initial_attire` | **RIGHT** |
| `AGENTS.md` § Clothing regions and undressing | `story/attire.py` | **RIGHT**, except `initial_outfit.state` "retired" (**STALE by omission**) |
| `AGENTS.md` § Extra body parts | `EXTRA_PART_ASPECTS`, `_normalize_extra_parts` | **RIGHT** |
| `AGENTS.md` § How much a mind holds at once | `psychology.capacity` stored `""`, never backfilled | **RIGHT** |
| `AGENTS.md` § What the cast may do off screen | `OFFSCREEN_LIFE_*` | **RIGHT** |
| `AGENTS.md` § How off-screen information reaches a mind | carriers/couriers/artifacts | **RIGHT** on physics; the registered-character clause is narrower than the code |
| `AGENTS.md` § Lorebook-tree generation | `importers.py` | **RIGHT** |
| `AGENTS.md` § Going under and waking up | `awareness_conditions`, `awareness_map`, `NON_AWAKE_GATED` | **RIGHT** as far as it goes; silent on the collapse rule (finding 18) and on the unknown-level fall (finding 16) |
| `docs/guides/DATABASE.md` § `lore_gen_jobs` | `importers.py` job store | **RIGHT** |
| `docs/guides/DATABASE.md` § `world.scene` attire paragraph | `attire` ledger shape | **RIGHT** |
| `docs/guides/PIPELINE.md` § `director_establish` | `initial_outfit` projection only | **RIGHT** |
| `Design.md` "Authored initial outfit with live story attire" | | **RIGHT** |
| `Design.md` "Clothing by body region" / "Garment condition" / "Undressing as a sequence" / "Displacement" | | **RIGHT** |
| `Design.md` "Living world — the five state-producers", clause C | | **STALE (understated)** — persona carriers, arrival surfaces and crowd acquisition all postdate the wording |
| `docs/UNBUILT.md` § 2.14 (`guessed_spans` unwired) | | **RIGHT** — the register is correct and the docstring is the thing that is stale (finding 23) |

Nothing in this package was found built-and-quietly-lost in the sense
`tools/fire_rates.py` exists to catch, with one exception measured above:
`guessed_spans` is built, tested, documented, has 110 live cases waiting for
it, and has no caller — and `UNBUILT.md` already says so. The rest of the
findings are settings with no reader, vocabularies with no publisher, and
lists with two copies.
