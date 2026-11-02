# Audit — `agents/common.py` (2026-11-01)

Auditor lane: the `agents/common.py` split (plan:
`<scratchpad>/plans/SPLIT_COMMON.md` / `.json`). Read-only; nothing in the
repository was edited. Every `path:line` is the current working tree
(`worktree-jev-character-tracking`, HEAD `84f3de23`). Snippets were run with
`.venv/bin/python` against pure functions; the one database measurement opened
`engine.db` with `?mode=ro`. No test file was run (none was needed: every
mechanism below was reproduced directly).

## Scope read

- **`agents/common.py` lines 1–12971, read in full**, in order, in ~500-line
  chunks, with working notes. This is the whole file.
- Read to confirm a claim (partial): `agents/director.py` 790–812, 1171–1200,
  2300–2325, 2640–2680, 2905–2930, 7495–7530; `agents/loops.py` 560–580,
  1622–1636, 1970–1990; `agents/composer.py` 4425–4545; `agents/__init__.py`
  1–20; `persist/commit_common.py` 34–60; `persist/commit_background.py`
  392–406; `world/charter_runtime.py` 751–823; `world/charter_place.py` 113–117;
  `story/attire.py` 3406–3440; `story/couriers.py` 226–236; `story/scene.py`
  464–476, 2846; `core/db.py` 2993–3023; `core/pipeline_context.py` (ChatData);
  `language_runtime/__init__.py` 572–600, 646–672, 736–773; `tools/project_check.py`
  1682–1830, 2600–2700; `tests/helpers.py` 100–240; `tests/model_seams.py` 35–50;
  the 46 monkeypatch sites and their tests (listed in the plan);
  `language_packs/{en,ja}/cards/linguistics.json` (the `agents.common` section,
  compared key by key); the encoder card `claim_dispositions.txt`.
- Skimmed only (not audited): the rest of `director.py`, `composer.py`,
  `perception.py`, `narration.py`, `loops.py`, `character.py`.
- Prior art read in full: `docs/experiments/AUDIT_AGENTS_COMMON.md` (baseline
  `d43b4ed`, 2026-08-18, when this file was 6,186 lines). Its findings 2 (pronoun
  tokenizer), 3 (healer vocabulary), 4 (`_muffle_middle` join), 5 (ambiguous
  mental verbs), 6 (per-element subject), 7/14/18/19 (dead names, stale
  comment), 9 (`_recognizes`), 10 (fail-open exclusion), 11 (`==` self check),
  12 (multi-word proper-noun regex), 16 (English conflict list), 17
  (authority fallback), 20 (truncated comment) and 21 (`_compositor_value`,
  silent resolver failure) are **fixed at HEAD** — verified line by line. Its
  findings 13 (orphan comments) and 15/16's class (English-only tokenisation)
  are still live and reappear below in their current shape.

**Tooling caveat that changes several conclusions.** The anatomy report
counted only `from agents.common import …`; fourteen role modules import
`from .common import …` (relative). With relative imports resolved, **248
names** are used from outside, and functions the anatomy showed with "0 prod
importers" — `_requires_reaction_phase`, `_assert_plan_materialized`,
`_join_text`, `_lore_fingerprint`, `_char_known_tags`, `_books` … — are live.
Every dead-code claim below was re-derived from a transitive liveness closure
over the resolved contract plus a repo-wide word search (incl. `tests/`,
`tools/`, `extension_runtime/`, `language_adapters/`, string forms).

## Findings

### F1 — LEAK (ja): a Japanese stranger's label carries their given name

`agents/common.py:6188-6189` (`_summary_label`, the head-final/unspaced branch):

```python
    if referring.head_final() or referring.unspaced(text):
        sentence = _strip_identity_tokens(referring.first_sentence(text), forms)
        clause = referring.head_final_clause(sentence)
```

The branch strips only WHOLE name/alias forms (`forms` = the full name and the
authored aliases). The token-level strip the English branch applies
(`name_tokens`, computed above it, and `_holds_the_name`) never runs here. A
Japanese card named 佐藤ヒナミ whose appearance summary leads with the given
name — the shape the code's own comments call routine ("Summaries routinely
lead with the canonical name") — mints a label that names her to every observer
who has not met her.

Reproduced (`language_scope("ja")`):

```
_unknown_actor_label("佐藤ヒナミ", "ヒナミは狐耳の背の高い女性。", [])  -> 見知らぬヒナミは狐耳の背の高い女性
_unknown_actor_label("佐藤ヒナミ", "狐耳の背の高い女性、ヒナミ。", [])  -> 見知らぬヒナミ
_unknown_actor_label("佐藤・ヒナミ", "ヒナミは狐耳の背の高い女性。", []) -> 見知らぬヒナミは狐耳の背の高い女性
en: _unknown_actor_label("Hinami Sato", "Hinami, a fox-eared young woman with amber eyes.", []) -> the fox-eared young woman
```

Reach: `observer_label_fn` (common.py:5609-5612), the identity scrub's labels
(6705), `stranger_label_ladder` → `composer.assign_stranger_labels`, the
narrator's earned labels. `character_scene_keys` derives no name parts, so a
card that does not list ヒナミ as an alias always takes this path.
CONFIRMED (pure function, three spellings). Not registered: UNBUILT_PIPELINE
C2/E2 is the English token-floor complaint and UNBUILT_PERCEPTION §1.217 notes
only "Japanese reads the first sentence only".

**Fix:** in the head-final branch, also strip every `_name_tokens(actor_name)`
token that passes `_name_token_floor` (the parts `_player_name_forms` already
derives) through `name_boundary_pattern` + the pack's `_NAME_TAIL_PATTERN`,
exactly as `_strip_identity_tokens` strips a form. **Test:** ja-scoped
parametrised labels for 姓名, 姓・名 and 名-led summaries asserting no name
token survives; the English cases unchanged.

### F2 — LEAK (ja): the last-pass identity scrub never scrubs a Japanese given name

`agents/common.py:6750-6753` (`_scrub_unknown_identities`):

```python
        parts = [tok.strip("-") for tok in re.split(r"[^\w-]+", name)
                 if tok.strip("-")
                 and tok.strip("-").casefold() not in _generic] \
            if len(name.split()) > 1 else []
```

The PX1 rule ("A NAME'S OWN PARTS ARE SPELLINGS OF THE BODY IT NAMES" — a
Director writing a bare given name walked past this pass) derives parts only
when the name contains a SPACE. Unspaced (佐藤ヒナミ) and middle-dot
(佐藤・ヒナミ) names yield no parts, so the given name in free prose reaches
the view unscrubbed and `leaked` stays empty — no tripwire.

```
ja: _scrub_unknown_identities("ヒナミが手を振る。", allowed_forms=[], unknown_sources=[{"name":"佐藤ヒナミ",...}])
    -> ('ヒナミが手を振る。', [])                      # also for 佐藤・ヒナミ
ja: "佐藤ヒナミが手を振る。" -> ('見知らぬ狐耳の背の高い女性が手を振る。', ['佐藤ヒナミ'])
en: "Hinami waves." (unknown "Hinami Sato") -> ('the fox-eared woman waves.', ['Hinami Sato'])
```

CONFIRMED. This is the "runs LAST on every view" floor; F1 and F2 are one
class — *a name's parts are found by whitespace* — in the two places the
identity floor decides what an observer may read.

**Fix:** derive parts with `_name_tokens` (script runs, the `・`/`＝` joiners
already outside its classes) when the name has no space, keeping the
`_generic`, `allowed` and capitalised-part guards (the last is a no-op in a
caseless script, which is correct). **Test:** the ja pair above in
`tests/test_firewall_across_scripts.py`'s shape.

### F3 — LEAK (ja): the presence-knowledge channel floor cannot fire in Japanese

`agents/common.py:8650-8680` (`_check_presence_knowledge_channel`):

```python
                   if p and len(p) >= 3}                       # 8652
            if len(p.split()) >= 2:                          # 8666
            ...
                    r"(?<!\w)(?:%s)\s+(?:[\w'-]+\s+){0,2}%s(?!\w)"   # 8671
```

Three whitespace assumptions: a two-character name (硬貨, 佐藤) is never a
phrase; an unspaced multi-word name is "one word", so it needs a definite
determiner; and the determiner rule demands `\s+` after the determiner and a
non-word after the noun — a Japanese determiner is written straight onto its
noun (その硬貨) and the noun straight onto its particle. The ja pack's
`_DEFINITE_DETS` does carry Japanese determiners; the regex shape around them
cannot match. This floor is SUBTRACTIVE: `agents/director.py:7502-7507` drops
the line when it warns.

```
ja: _check_presence_knowledge_channel("カドマン", "その奇妙な硬貨のことは知っている", sc, {}, "")  -> []
en: _check_presence_knowledge_channel("Kadoman", "I know about the strange coins", sc, {}, "")   -> [warning]
    (entity unplaced, aliases ["奇妙な硬貨"] / ["strange coins"])
```

CONFIRMED (pure function; consumer traced). Exposure: Director-voiced presence
lines (`director_may_voice` kinds), so narrower than F1/F2.
**Fix:** match the pack's determiner with the pack's own boundary
(`cue_boundary_pattern`/`name_boundary_pattern`), treat an unspaced form as a
phrase, and floor length by `_display_floor`. **Test:** the ja pair above.

### F4 — LEAK (ja, channel): a Japanese stage direction is delivered as speech

`agents/common.py:4385` (`split_stage_directions`):

```python
        if len(body.split()) == 1:
            # Emphasis on a single spoken word. It stays in the line.
            return body
```

"A ONE-WORD span is markdown emphasis" is measured in whitespace, so every
Japanese span is "one word": the asterisks come off and the conduct stays in
the SPOKEN text. The docstring names the consequence — a body movement goes
"down the acoustic channel ... a wrong flow is an engine failure, never a
model's" — and in a Japanese story nothing is excised, so a listener behind a
door is told what the speaker's body did.

```
ja: split_stage_directions('*身を乗り出して彼女の肩に手を置く* 座ったほうがいい。')
    -> ('身を乗り出して彼女の肩に手を置く 座ったほうがいい。', [])
en: split_stage_directions('*leans in and sets a hand on her shoulder* You will want to sit down.')
    -> ('You will want to sit down.', ['leans in and sets a hand on her shoulder'])
```

CONFIRMED. **Fix:** count units with `_countable_word_units` (one unit per
unspaced character, the trade the file already makes) and keep the one-word
rule only for a spaced script. **Test:** the ja pair through `norm_sequence`,
asserting a promoted action and clean speech.

### F5 — WRONG-SCENE (measured): two word-list guards match SUBSTRINGS of free prose and end beats

`agents/common.py:3760` (`acts_awaiting_resolution`, the predicate behind
`_requires_director_resolution`) and `:3782` (`_classify_action_commitment`):

```python
                or any(term in text for term in _ling("_CONFLICT_VERBS"))):
    ...
    if any(cue in text for cue in _ling("ATTEMPT_CUES")):
```

`term in text` is a substring test: "enter" fires inside *center*, "stab"
inside *stable* and *established*, "restrain" inside *restraint*, "break"
inside *breakfast*, "cast" inside *forecast*/*castle*, "rush" inside
*brushing*, "try" inside *pastry*/*entry*, "aim" inside *claim*. A firing
`_requires_director_resolution` ENDS THE BEAT in both loops
(`agents/loops.py:1629` "physical resolution required", `:1977`); a firing
`ATTEMPT_CUES` makes an act `contestable` wherever `commitment` was omitted —
always for a promoted stage direction (`_promoted_stage_action`, 4419), which
then also ends the beat through the same predicate.

Snippet (en): "eats breakfast by the window", "points to the center of the
map", "reads the forecast aloud", "nods toward the castle" → each ends the beat;
"brushes the crumbs from her sleeve", "walks to the pantry", "smiles and claims
a seat" → each classified `contestable`.

**Measured** on the owner's `engine.db` (read-only, the 2,500 most recent
active `interaction_loop` variants, 2,554 distinct character action elements):
153 asserted, overt acts end the beat through `_CONFLICT_VERBS`; the host words
are *center* 30, *force* 21, *breaks* 20, *break* 18, *breaking* 14, *grabbing*
14, *stable* 6, *restraint(s)* 8, *casts* 4, *entertaining* 2, *interleaved* 2,
*forceful* 2, *established* 2 … — **at least 52 of 153 (34%) are in-word
substrings** (center/stable/established/restraint/entertaining/interleaved/forceful),
before asking whether "casts a glance" or "breaks eye contact" are conflicts.
`ATTEMPT_CUES` hosts: *brushing/brush/brushes* 36, *pastry* 10, *entry* 6,
*claim*-words 6, *recharge*/*discharges* 4. CONFIRMED.

**Fix (subtractive, per the owner's FP rule):** match through
`cue_boundary_pattern` as the authority checks in this file already do; then
re-measure the word-level remainder before deciding whether the list itself
should go. **Test:** parametrised false positives above (en, plus a ja row),
asserting `_requires_director_resolution` is False and the commitment stays
`asserted`.

### F6 — WRONG-SCENE (ja): a contestable multi-phase act reaches pass-one reactors whole

`agents/common.py:783` (`observable_action_onset_text`):

```python
        r"\s*;\s*|\s*,\s*(?:and\s+)?(?:then\s+)?|\s+\b(?:then|afterward|subsequently)\b\s+",
```

The onset cut — the floor that keeps a dance partner from receiving "every
outcome she existed to help resolve" — splits only on ASCII `;`/`,` and three
English words. Japanese clauses are joined by 、 and verb inflection, so the
whole surface is the "onset".

```
ja: {'observable':'彼女の手首をつかみ、引き寄せ、壁に押しつける','commitment':'contestable'} -> 彼女の手首をつかみ、引き寄せ、壁に押しつける
en: {'observable':'grabs her wrist, pulls her close, then pins her to the wall',...} -> attempts to grab her wrist
```

The English-only "attempts to" morphology is declared out of scope in the
comment ("their morphology belongs to the language adapter"); the SPLIT is not.
CONFIRMED. **Fix:** a pack value for the sequence boundary (ja: 、 / て-form
clause ends / そして / それから), read like `_CLAUSE_BREAKS`. **Test:** the ja
pair.

### F7 — WRONG-SCENE (ja, over-subtraction): `_act_surface_admission` refuses the whole act

`agents/common.py:6548`:

```python
_SURFACE_CLAUSE_SPLIT = re.compile(r"(?<=[,;:])\s+|\s+[—–]\s+|\s+--\s+")
```

Japanese clauses are never split, so one span names an unseen body and the
WHOLE surface is cut — the actor's own visible conduct with it. The project
rule is that a floor subtracts what the rule states and no more.

```
ja: _act_surface_admission('グラスを持ち上げ、イヴォの素顔を眺め、ゆっくりと一口飲む', ..., forms_by_body={"イヴォ":["イヴォ"]}, perceived=set()) -> ('', ['イヴォ'])
en: 'lifts his glass, looks over Ivo's uncovered face, takes a slow sip' -> ('lifts his glass, takes a slow sip', ['Ivo'])
```

CONFIRMED. Three delivery floors call it (`perception.py:7398`, the composer
path, `loops.py:570`). **Fix:** add the fullwidth marks (、，；：) without the
whitespace requirement, as `_SEGMENT_BREAK` (10229) already does.
**Test:** the ja pair.

### F8 — WRONG-SCENE (ja): a mind's own name is never turned into second person

`agents/common.py:8069` (`name_occurrence_pattern`, used by
`_self_second_person`):

```python
    tail = r"(['’]s)?(?!\w)" if possessive else r"(?!\w)"
```

A Japanese particle is a word character, so ヒナミの / ヒナミは never match
and `_self_second_person` rewrites nothing; the perceiver reads herself in the
third person inside her own view (the defect the function exists for).

```
ja: _self_second_person("ドクターがヒナミの肩に手を置く。ヒナミは扉を開ける。", ["ヒナミ"]) -> unchanged
en: "...sets a hand on Hinami's shoulder. Hinami opens the door." -> "...on your shoulder. You open the door."
```

Callers: `composer.py:2780,2789,5538`, `character.py:4685`, `narration.py:1393`.
CONFIRMED (whether the ja renderer later masks it was not traced — PLAUSIBLE
for the rendered page, CONFIRMED for the function). AGENTS.md:431's
self-reference clause is unqualified by language. **Fix:** build the name part
with `name_boundary_pattern` (as `_subject_opener` did after A2) and let the
pack supply the second-person replacement (an English "you" is the wrong
replacement in ja anyway). **Test:** the ja sentence through
`_self_second_person`.

### F9 — WRONG-SCENE: `_subject_opener`'s LRU cache is keyed without the story language

`agents/common.py:8077`:

```python
@lru_cache(maxsize=_SUBJECT_OPENER_CACHE)
def _subject_opener(form):
    lead = _name_title_alternation()      # reads _ling("_NAME_LEADERS"/"_NAME_TITLE_TOKENS")
```

The compiled pattern embeds the ACTIVE pack's title alternation but the cache
key is the form alone, so whichever language first compiles a form wins for
every later story in the process. `language_runtime.linguistic`'s own docstring
forbids exactly this ("every regex … must follow its own context-local story
language without mutating process globals"); the server runs stories in both
packs concurrently.

```
cache_clear(); en: _subject_opener("ヒナミ"); ja: _subject_opener("ヒナミ") -> pattern identical to the en one (158 chars)
cache_clear(); ja: _subject_opener("ヒナミ") -> a different, 180-char pattern
```

Readers: `_sentence_subjects` → the four authority checks, `_strip_subject`.
CONFIRMED. **Fix:** key the cache on `(current_language_id, form)` or on the
alternation string. **Test:** the cross-scope sequence above asserts the
patterns differ.

### F10 — WRONG-SCENE (ja): the narrator's tic ban list bans Japanese grammar

`agents/common.py:10325` (`_overused_phrases`):

```python
            if all(w in _ling("_TIC_STOPWORDS") for w in words):
```

An unspaced script is tokenised per character (`_PHRASE_TOKEN`) and
`_TIC_STOPWORDS` is byte-identical in `en` and `ja`, so any three-character run
recurring across two drafts is a "tic" — including inflection.

```
ja: _overused_phrases(["彼女はゆっくりと扉を開けている。外では雨が降っている。"], "彼は窓の外を見ている。誰かが笑っている。") -> ['っ て い る']
en (same content): -> []
```

The list is handed to the narrator as phrases to vary — here the progressive
-ている, character-spaced. `_already_established_phrases` has the same shape
(six characters is a phrase fragment in ja; it returned 'の 外 を 見 て い'
for two unrelated sentences). CONFIRMED. **Fix:** count n-grams in
`_countable_word_units`' unit only for spaced scripts, or give the ja pack a
morpheme-level stop set; at minimum do not emit character-spaced phrases.
**Test:** the ja pair asserts no tic.

### F11 — WRONG-SCENE (low): `whole_sentences` returns the whole text, or one sentence, after an abbreviation line break

`agents/common.py:4299`:

```python
        at = text.find(piece, pos)
        if at < 0:
            break
```

`split_sentences` rejoins an abbreviation with ONE space, so a piece whose
original carried a newline or double space after "Dr." is not found in the
text. If that is the first sentence nothing is kept and the uncut text is
returned; if later, the description is cut to the sentences before it.

```
whole_sentences("Dr.\n  Watson keeps the lamp lit here. " + "The hall runs on. "*50, 600) -> 938 chars (cap 600)
whole_sentences("The hall runs on. Dr.\n  Watson ..." + ..., 600)                    -> 17 chars
```

CONFIRMED. Reach: `room_prose` → every room description in every view
(`ROOM_PROSE_CHARS` = 600). **Fix:** locate pieces on whitespace-normalised
offsets. **Test:** the two inputs above.

### F12 — WRONG-SCENE (latent): one fact, two spellings — the shared lookups this file re-spells

None disagree today; each is free to. UNBUILT_WORLD §1.79's three inline
attire-ledger copies are **gone** from this file (they read through
`attire.key_for`, 1706-1707 and 1787-1788, and `attire.entry_for`, 1485); these
remain:

| fact | spelled here | the owner's spelling |
|---|---|---|
| a charter body's placement key | `present_charter_figures`, 2874: `placements.get("charter:%s:%s" % (...))` | `charter_place.placement_uid` (= `identity_seed`), used by `presence_figures_for_room` (2443-2445) |
| a role from a presence's `role_hint` | `present_charter_figures` 2820-2826 and `observer_label_fn._looks` 5578-5581, both `hint.startswith("member of ")` + the private `charter_crowd._role_noun` | `charter_runtime.py:4763` writes the hint |
| a claim's sequence index | `apply_player_authority` 8955-8957 | `downgraded_sequence_indices` 8894-8896, whose docstring says a second parse "is a second thing to keep in step" — 60 lines above the second parse |
| the sentence splitter | `_sentence_subjects` default `(?<=[.!?])\s+` (8231) | `_SENTENCE_SPLIT` (10949), made CJK-aware for exactly this reason (see F13) |
| the narration-tense vocabulary | `("present", "past")` at 11318 | `story/scene.py:2846 NARRATION_TENSES` (see F21) |
| a crude English stem | `_stem_token` (108: ing, es, ed, s) | `_content_tokens` (9391: ing, ed, es, s) |
| attribution vocabulary stripped from shingles | `_SHINGLE_STOPWORDS` (10479), module-level English | the pack holds every sibling list (`_TIC_STOPWORDS`, `_OVERLAP_STOPWORDS`); the composer's ja attribution formula is never stripped |

PLAUSIBLE as failures, CONFIRMED as duplication (each pair read side by side).
**Fix:** call the owner's function/constant. **Test:** for the placement key, a
test that rows from `present_charter_figures` and `presence_figures_for_room`
for one body carry the same placement.

### F13 — WRONG-SCENE (plausible): a courier row's id is invisible to the composer, and its "passing through" is English

`agents/common.py:3165, 3181-3183` (`couriers_for_room`):

```python
            "courier_id": courier.get("uid"),
            ...
            "what": "%s, passing through without stopping"
                    % couriers_model.courier_voice(courier),
```

Crowds publish `uid`, notices `artifact_id`, couriers `courier_id`; the
composer keys a room-content percept on `entry.get("uid") or
entry.get("artifact_id")` (`composer.py:4448`), so every courier is subject
`""` and two alike-described couriers in one room share one dedupe key. The
appended clause is an English literal glued into a percept the ja composer
renders verbatim. PLAUSIBLE (the dedupe consequence was read, not run).
**Fix:** publish `uid` (or read `courier_id` in the composer) and move the
clause to the compositor templates. **Test:** two couriers, one room, two percepts.

### F14 — SILENT-NOOP (ja): the authority checks and five narrator/view guards cannot fire in Japanese

Root: `agents/common.py:8231` — `_sentence_subjects` splits with its own
ASCII default, `re.compile(r"(?<=[.!?])\s+")`, though `_SENTENCE_SPLIT`
(10949) exists because "an ASCII-only splitter returned the whole passage as one
clause". A Japanese paragraph is ONE sentence whose subject is its first name:

```
ja: _sentence_subjects("ヒナミは立ち上がる。ドクターは静かに笑う。彼は扉を開ける。", ["ヒナミ","ドクター"])
    -> [('ヒナミは立ち上がる。ドクターは静かに笑う。彼は扉を開ける。', 'ヒナミ')]
ja: _check_character_speech_authority("ドクターは黙っている。ヒナミは「行こう」と言った。", ["ヒナミ"], other_names=["ドクター"]) -> []
en: same beat -> [warning]
```

The same class, guard by guard (each reproduced or read):

| guard | line | why it is inert in ja | checked |
|---|---|---|---|
| `_check_character_speech_authority`, `_check_character_act_authority`, `_check_player_act_authority`, `_check_player_interiority_authority` | 8332, 8388, 8966, 8693 | one-sentence paragraphs (above); the act check also searches `\b(?:{verbs})\b` (8452) — its own `_predicate_heads` docstring says so ("in ja that verb check is still inert") | run (speech) / read |
| `_undeclared_world_object` | 8795 | `_DIRECT_OBJECT_RE` is byte-identical in en and ja (an English article regex) | read + pack diff |
| `_check_player_person` | 11116 | `(?<!\w)form(?:['’]s)?(?!\w)` — a name + particle never matches | run: ja `[]`, en warns |
| `_check_narrator_fidelity` proper-noun arm | 12196-12198 | same `(?!\w)` boundary | run: ja `[]` |
| `_check_action_attribution` | 11378 | content words are `[a-z]{5,}` | read |
| `cut_short_speech` | 4601 | `len(body.split()) < 5` — a Japanese line is never interrupted | run: `None` |
| `_dedupe_view_sentences` | 10801 | `len(key.split()) >= 5` + ASCII splitter | run: unchanged |
| `_strip_player_echo` fold pass | 10124 | `len(folded.split()) < 3` — a tidied echo is never caught | read |
| `_check_player_contact_authority` reach | 9119 | parts by `name.split()`, `len(part) >= 4` — a declaration naming the target by given name reaches nobody, so a legitimate contact is reported and may be DROPPED after a retry | read |
| `_other_peoples_names` | 5754 | `" " not in name` — a relative's unspaced name is never shielded | read |
| `exposure_owner_refs` → `_check_attire_fidelity` | 1509 | the owner ref is `display + "'s"` | read |

The pack routing landed (the ja pack extends 68 of the 81 `agents.common` keys
with Japanese); the Python around the lookups still measures words in spaces,
sentences in ASCII and boundaries in `\b`. Not registered as a class (UNBUILT
§1.69 is the abbreviation splitters; UNBUILT_IDENTITY §1.0/§3.x are the
Director manifest and native review). **Fix (the class):** route every one of
these through the file's own script-aware primitives — `_SENTENCE_SPLIT`,
`_name_tokens`, `_countable_word_units`, `name_boundary_pattern`,
`cue_boundary_pattern`. **Test:** extend `tests/test_common_recognizers_localise.py`
with one positive ja case per guard (that file today checks the pack VALUES
are Japanese, which they are).

### F15 — SILENT-NOOP: the proper-noun check is satisfied by "the" for every article-led name

`agents/common.py:12198`:

```python
        parts = [w for w in text.split() if len(w) >= 3] or [text]
        if any(re.search(rf"(?<!\w){re.escape(w)}(?!\w)", prose, re.I) for w in parts):
            continue
```

"The" is a part of "The Doctor", matched case-insensitively, so any page
containing the word *the* has "mentioned" him.

```
en: view "The Doctor stands at the door.", prose "The door opened quietly." -> []
    prose "A door opened quietly."                                      -> [warning]
    "Elyra Voss" (no article) behaves correctly.
```

CONFIRMED. Warning-only since E12, so the cost is a measurement that cannot
see the commonest name shape in the owner's stories. **Fix:** take parts from
`_significant_name_tokens`. **Test:** the pair above.

### F16 — SILENT-NOOP: `norm_sequence` drops unrecognised elements without a word

`agents/common.py:4778-5086`, the four non-ponder arms (`if txt:` 4810/4824,
`if content:` 4869, `if description:` 4916, `if att:` 4948) have no `else`;
an unknown `type` falls into the action arm. The `ponder` arm (4892-4907) warns
on a half-drop — "dropping half of one silently is the same failure shape as
blanking an act" — and the others drop whole elements silently. And when
`sequence` is a non-empty list, the scalar `speech` is never consulted, so a
declaration whose elements are all malformed loses its spoken line too.

```
norm_sequence({"sequence": [None, 5, {}, {"type": "gesture", "text": "waves"},
               {"type": "action", "observable": "nods"}, {"type": "speech", "text": ""}],
               "speech": "hi"}, warn) -> sequence [] , speech None, warnings []
```

Also: the action arm passes `visibility` through raw (`e.get("visibility",
"overt")`, 5000) while the other three arms normalise to concealed|overt;
`norm_sequence({"sequence":[{"type":"action","attempt":"steps aside","visibility":"private"}]})`
keeps `"private"`, which every reader compares to `"concealed"`. On validated
paths `schemas.ActionElement.visibility` is an enum first, so that half is
PLAUSIBLE; the drop half is CONFIRMED.
Empty/None trace (as asked): `norm_sequence(None)` raises AttributeError (all
four callers pass a dict: `director.py:2181,2320,2923`, `character.py:5054`);
`norm_sequence({})` returns `{"sequence": [], "speech": None, "speech_volume":
"normal", "action": None, "actions": []}`.
**Fix:** one `warn` per dropped element naming its keys; normalise action
`visibility` like its siblings. **Test:** the input above asserts warnings.

### F17 — SILENT-NOOP (plausible): broad `except` turns a reader's bug into a quieter scene

| site | swallows | falls back to |
|---|---|---|
| `_contextual_rooms` 1387-1391 | any error in `world.spatial.attended_rooms` (a deferred re-import of a module already imported eagerly — not a cycle dodge) | `nearby_rooms`, which omits the channel far-end and a body's inside: the payload silently loses the radio's far room |
| `chatter_inputs` 2040-2043 | any registry failure | `{"items": {}}` — every charter body, crowd and chatter vanishes from every view |
| `presence_figures_for_room` 2434-2438, 2531-2535 | placement and derived-record failures | `{}` — figures lose their cells / derived bodies vanish |
| `rooms_in_view` 12704, 12708 (two `except: pass`) | `visible_adjacent_rooms`, `earshot_rooms` errors | a narrower aperture |

None warns (`lay_charter_figures` 2646-2647 shows the house shape: `ctx.add_warning`).
PLAUSIBLE — no live failure was observed; the shape is the one the brief names.
**Fix:** `note_step_warning` in each except. **Test:** a raising stub per seam
asserting a warning.

### F18 — DEAD: `_ambient_blocked_slugs` and `_keys_reference_blocked`

`agents/common.py:4191-4232`. Zero references anywhere — not in production,
`tests/`, `tools/`, `extension_runtime/`, docs, or as strings. Their caller
(lore staging by ambient scope) went with the room filing's retirement
(`40d3a7ee`, 2026-09-03). Not registered. CONFIRMED (repo-wide word scan +
liveness closure). **Fix:** delete in its own commit after the split.

### F19 — DEAD + STALE-DOC: `_check_action_direction` is a stub under a 40-line description of what it no longer does

`agents/common.py:11514-11556`: the docstring describes REVERSED/MISSING
findings at two confidence tiers; the body is

```python
    # CUT 2026-09-15: 4 fires in 167 scratch turns ... Returns nothing.
    return []
```

and `_check_narrator_fidelity` still calls it (12386). The pack keys it read,
`agents.common._NARR_LOWERING` / `_NARR_RAISING`, are now read by no `.py` in
either pack (only `tools/build_japanese_pack.py:387-388` writes them) — the
only two unread keys left in the section. Not registered. CONFIRMED.
**Fix:** delete the stub, its call and the two pack keys (both packs), or
replace the docstring with the cut note.

### F20 — DEAD + STALE-DOC: `realized_event_ids` has had no producer since the prompt cards were split

`agents/common.py:487-498`:

```python
        if status == "realized":
            realized_ids.update(... row.get("realized_event_ids") ...)
    ...
        realized = bool(event_id and event_id in realized_ids)
```

The pre-split card asked for `claim_dispositions:[{claim_id,status,realized_event_ids,notes}]`
(`tests/data/prompt_cards_presplit/en.json`); today's encoder card
(`language_packs/*/cards/system_prompts/encoder/claim_dispositions.txt`) asks
for `{claim_id, status, reason?}`, and nothing in `agents/`, `llm/`,
`persist/` writes the key. The fallback can never be true from live output, and
two docstrings still describe it as THE mechanism (`scan_claims_for` 475-476,
`adjudicated_player_action_text` 832-834: "only when a claim disposition names
its event id in `realized_event_ids`"). CONFIRMED (repo-wide grep; the only
writers are tests and demos). **Fix:** drop the branch and correct both
docstrings — or restore the field to the card if the event-id path is wanted.

### F21 — DEAD (not registered): production-dead names the register does not list

UNBUILT_PLATFORM §1.45 registers six (below). Not listed there:
`_action_already_rendered` (9700 — reachable only from the registered six);
`_stable_event_key` (5289 — tests only; `persist.commit_common` has its own);
`_scrub_undeclared_player_speech` (10701 — `tools/perception_quality.py` reaches
it by `getattr`, no engine caller, and its `mode="player"` path depends on the
English `_YOU_RE`); `_SENTENCE_END` (5882 — kept "for the readers that import
it from here", one test); `_DANGLING_SPEECH_VERB_RE`/`_SPEECH_CUE` (105-106 —
test-only English compatibility views that load the en pack at import time).
CONFIRMED (liveness closure over the resolved contract).

### F22 — STALE-DOC: "this module owes `story.scene` nothing"

`agents/common.py:11312-11318`:

```python
    # The vocabulary is `story.scene.NARRATION_TENSES`; it is spelled out here
    # rather than imported for the same reason the person check spells out its
    # three values -- this module is imported by every role module and owes
    # `story.scene` nothing.
    ...
    if tense not in ("present", "past"):
```

`agents/common.py:44-45` imports five names from `story.scene` at module scope.
The reason given for the second copy of the vocabulary is false. CONFIRMED.
**Fix:** import `NARRATION_TENSES`.

### F23 — STALE-DOC: `chatter_inputs` argues from a cost `registry_for` no longer has

`agents/common.py:2017-2019`: "`charter_runtime.registry_for` normalizes the
whole registry (measured 21.8ms with its deepcopy on one 40-body charter), so a
per-perceiver fetch would multiply that by the cast". `registry_for` now
returns the shared cached object (`world/charter_runtime.py:794-807`); the
deepcopy moved to `registry_for_update`, and this function calls
`cached_registry` anyway. CONFIRMED. **Fix:** restate the reason (one fetch of
presence records + slices per stage).

### F24 — STALE-DOC: orphaned comment blocks that now describe pack data or deleted code

Ten blocks, tabled in the plan (`SPLIT_COMMON.md`, "The section markers…"):
6533-6547, 7988-7990, 8266-8267, 10014-10026 (two contradictory drafts),
10276-10279 (describes a content-word list; the list is stopwords), 10815-10827,
10925-10929, 10942-10948 ("Splits a sentence into clauses" above the SENTENCE
splitter), 11843-11844, 11961-11964. The class AUDIT_AGENTS_COMMON.md #13 found
(then ~35 blocks); about a third remain. CONFIRMED by reading.

## Efficiency

1. **`widen_reactors_*` re-read the world on every call** —
   `agents/common.py:7693, 7741, 7833, 7968` (+ `widen_reactors_to_rejoined`'s
   two queries): each call does `get_scene(chat_id)` (an uncached
   `SELECT` + `json.loads`; `core/db.py:2993-2996`), `SELECT * FROM chats`,
   `persona_of` and `_present_cast_bodies`. Called from 13 sites per beat
   (`runtime.py` ×6, `loops.py` ×7). Measured: a median live scene is ~50 KB and
   parses in 0.78 ms, so ~15-25 ms of DB+parse per beat. Fix: one read per stage
   handed in (the scene and player name every caller already holds). Cheap.
2. **`_scrub_invented_dialogue` calls `_ling` once per CHARACTER** —
   `agents/common.py:10617` (`if ch in _ling("_QUOTE_CHARS")` inside
   `for i, ch in enumerate(view)`). Measured 0.94 µs per call → ~3 ms per
   3,000-character view, per observer, per composer pass. Fix: hoist one line.
   Cheapest item here.
3. **The identity floor re-reads the same rows per observer** —
   `observer_name_scrub` reads `known` (5647) after `observer_label_fn` already
   did (5539); `_other_peoples_names` reads `planned_entities` and the whole
   scene (5736, 5743) per call; `_presence_surface` (5510) recomputes a room's
   full `presence_figures_for_room` (fresh `chatter_inputs`, presence ledger,
   placements, derived records) for EACH dim-light name it labels. Per
   observer per payload. Fix: a per-stage memo on `ctx`/`inputs`, as the rest
   of this file does.
4. Smaller: `chatter_for_room` reads the crowd ledger directly (3041) instead of
   the stage's `_standing` copy (one extra read per room per stage);
   `_check_quote_attribution` recompiles the pronoun alternation per event and
   `_pronoun_to_group()` is rebuilt per word (µs); `cast_spelling_policy` is
   recomputed 7+ times a turn (sheet parsing is memoised; the dict build is
   not). Import-time: `_DANGLING_SPEECH_VERB_RE`/`_SPEECH_CUE` load and compile
   the en pack at import for tests only.

## Already registered

- **UNBUILT_PLATFORM §1.45** — `_inject_visible_actor`, `_inject_action`,
  `_normalise_views`, `_ensure_environment`, `_fallback_perception_views`,
  `_perceptible_entities` (+ `_ENTITY_LOOKUP_ONLY_FIELDS`): no production caller,
  tests only. Re-verified: still true.
- **UNBUILT_PIPELINE §1.13** — `ActionStage` read only by
  `_requires_reaction_phase`. Still true, and the function is LIVE
  (`director.py:2663`); the anatomy's "0 prod importers" was the relative-import
  undercount, not deadness.
- **UNBUILT_PIPELINE §5.3** — `_requires_reaction_phase` gating on
  `contestable` (P5(b) still open).
- **UNBUILT §3.8** / AGENTS.md:690 — `_delivery_ok` is one of two delivery
  families; its docstring and `tests/test_delivery_gate_not_universal.py` say so.
- **UNBUILT_PIPELINE C2/E2** — the English identity floor is token-based (F1/F2
  are the ja inverse and are NOT covered by it).
- **UNBUILT_PIPELINE §1.69** — the view deduper's splitter (`_VIEW_SENTENCE_SPLIT_RE`)
  has no abbreviation handling (watch item).
- **UNBUILT_PERCEPTION §1.217** — stranger-label residuals (English).

## Structure notes

- **Natural seams** (the plan's sixteen siblings): base · llm · names · cast ·
  bodies · rooms · figures · identity · acts · sequence · beat · scrubs ·
  authority · views · narration · fidelity. The intra-module graph has ONE
  giant component (220 defs) only because ~20 primitives (`_ling`, `_text`,
  `_quote_body`, `split_sentences`, `_name_tokens`, `cast_spelling_policy`,
  `_unknown_actor_label` …) are read everywhere; with those placed low it is a
  16-node DAG (verified by a dry-run import).
- **Monoliths in miniature:** `norm_sequence` 309 lines (4778-5086),
  `presence_figures_for_room` 284 (2276-2559, six nested helpers),
  `_check_narrator_fidelity` 258 (12140-12397), `_scrub_unknown_identities` 219
  (6642-6860), `_summary_label` 181, `_scrub_invented_dialogue` 151,
  `observer_body_regions` 140.
- **`presence_figures_for_room` empty/None trace (as asked):** `room_id` falsy →
  `[]`; `inputs` not a dict → a fresh `chatter_inputs` (registry + presence
  read); memo hit → shallow copies (nested `surface`/`placement`/`titles` shared
  with the memo — a caller mutating one corrupts the stage's memo); `sc=None`
  is tolerated (`presence_room` does `scene or {}`); a `None` ledger record
  becomes `dict({}, sketch={})`; placement and derived-record failures are
  swallowed (F17). `_noun_for(refs)` runs up to three times per emitted row.
- **Module-level mutable state:** `_COMMUNICATION_FORMS` (written once at import
  by the top-level `for` @310; `del` @313 removes the loop names),
  `_subject_opener`'s LRU (written per call; F9), `_REACTIVE_STAGES` and
  `COMMUNICATION_ACT_VERBS` (never written after import). No `global`, no
  `nonlocal`, no ContextVar defined here.
- **Deferred imports (62):** none dodges a cycle today — every target was
  imported in a fresh interpreter and loads no `agents.*` module. About twenty
  re-import a module already imported eagerly at the top (`world.spatial` ×8,
  `story.character_schema` ×3, `llm.schemas` ×3, `persist.commit` ×4 — eager at
  7525 —, `llm.llm_quality`, `language_runtime.referring` ×2 — already bound as
  `_referring` —, `core.db`). The one cycle-motivated statement is the EAGER
  mid-file `from persist.commit import _normalize_character_output` (7525),
  whose position is no longer needed (`import persist.commit` loads no agents
  module); it exists only to re-export a name to `character.py`. No hidden
  cycle: the real dodges are persist→agents (deferred in four `persist/commit_*`
  files), which `tools/package_edges.json` already counts as deferred.
- **One-way rule:** `common.py` imports no role module (eager or deferred) —
  holds.

## Docs checked

| claim | verdict |
|---|---|
| CLAUDE.md:105 "The **enforced** direction is one-way: role modules import `agents/common.py`, and `common.py` imports no role module" | **Holds in code; "enforced" is false.** No check in `tools/project_check.py` or `tests/` enforces it (searched). After the split it must hold for sixteen files with nothing checking. |
| AGENTS.md:431 routing row: `agents/common.py` (`_delivery_ok`, `_AUTONOMY_VERBS`, `bind_sequence_targets`) | **Stale in one name:** `_AUTONOMY_VERBS` is a pack key (`linguistics.json`), not a symbol here (first noted by AUDIT_AGENTS_COMMON.md; still unfixed). |
| AGENTS.md:431 "`observer_label_fn` gates one name, `observer_name_scrub`+`scrub_names_deep` gate a paragraph, and both read the same `known` map" | **Holds** — and both now use `_recognizes` (the old predicate mismatch is fixed). |
| AGENTS.md:431 "`common.self_reference_forms` + `perception._composer_self_forms` rewrite a mind's OWN minted epithet … into second person" | **Holds in English, not in Japanese** (F8). |
| AGENTS.md:431 "A capital letter is not a subject … (`common._observable_predicate`)" | **Holds** (English morphology). |
| AGENTS.md:690 / `_delivery_ok` docstring: not universal, only `loops.py` calls it, UNBUILT 3.8 | **Holds** (test-measured). |
| AGENTS.md:549 `attire_view` is the shared projection; `beneath` gated by `attire_beneath` | **Holds.** |
| UNBUILT_WORLD §1.79 "Three inline copies of the same fallback remain in `agents/common.py`" | **Stale:** the three sites read through `attire.key_for` (1706-1707, 1787-1788) and `attire.entry_for` (1485); no inline copy remains in this file. |
| UNBUILT_PERCEPTION §1.129 "PX5's THIRD floor, in `agents/loops.py` … needs the same call … moving it to `agents/common.py` … is the clean placement" | **Stale — landed:** `_act_surface_admission` is defined at common.py:6551 and called at `loops.py:570`. |
| UNBUILT_PLATFORM §1.45 (six dead helpers here) | **Holds**; add `_action_already_rendered` (reachable only through them). |
| PIPELINE.md:651-653 "only `_inject_visible_actor` and `_inject_action` survive in `agents/common.py`, as deterministic inputs rather than repairs" | **Stale:** they survive with no production caller (§1.45); they are inputs to nothing. |
| Design.md:292 (`_dedupe_view_sentences` masks quoted spans before splitting) | **Holds** in English; the deduper is inert in Japanese (F14). |
| `tools/generate_code_map.py:21` purpose "Shared normalization, lore, delivery, and perception helpers" / module docstring | **Understates** the file (identity floor, authority/fidelity checks, figures). Rewritten in step 17 of the plan anyway. |
| `chatter_inputs` docstring (registry_for cost) | **Stale** (F23). |
| `_check_narration_tense_match` comment ("owes `story.scene` nothing") | **False** (F22). |
| `scan_claims_for` / `adjudicated_player_action_text` docstrings (`realized_event_ids`) | **Stale** (F20). |
| `_check_action_direction` docstring | **Describes deleted behaviour** (F19). |
| `validated_player_state_assertions` docstring + warning text ("The spatial hand must create and describe a destination") | **Loosely true** under the owners-table reading (`SPECIALISTS` survives as the channel-owner table); the "repair ladder ask[s] the spatial hand for a complete room" describes the deleted specialist call — rooms now come from the room author (`agents/director_rooms.py`). Low. |
