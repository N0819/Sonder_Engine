# Audit: `agents/common.py`, read whole

Working notes in the register of
[`AUDIT_DIRECTOR.md`](AUDIT_DIRECTOR.md): read the file end to end, write
findings down, change nothing. `agents/common.py` is the shared foundation
every role module imports, and the import direction is one-way — role modules
import `common.py`, and `common.py` imports no role module. That invariant
holds at this revision (verified: no `from agents.<role>` anywhere in the
file; the four deferred imports are `llm.llm_quality`, `core.db`,
`story.couriers`/`story.artifacts`, `language_runtime` and
`persist.commit.apply_attire_diff`).

**Baseline revision:** `d43b4ed`. `agents/common.py` is 6,186 lines, 168
module-level functions, 28 module-level constants, and is unmodified in the
working tree. Every `file:line` below is as of that revision. Three other
agents were working concurrently; nothing here was edited, and
`docs/UNBUILT.md` was declared off-limits to this task.

How each finding was established: 1, 2 and 5 were **reproduced by running the
code** and the runs are quoted inline; 3, 4 and 7 were extracted from
`language_packs/*/cards/linguistics.json` and `compositor.json`; 6 and the
empty-predicate half of it were **measured** against the owner's live
`engine.db`, opened `mode=ro`; 7, 8, 14, 18 and 19 rest on exhaustive
`grep -rnw` over every tracked `*.py`, counted. The rest are read from source
and quoted.

---

## Part 1 — findings. FLAGGED, NOT FIXED.

### 1. The enclosed-state firewall gate is blind to an entity keyed by id — a fail-open leak, reproduced

`_perceptible_entities` withholds an entity's `state` from a payload when no
perceiver in that call can reach it. The gate is one line:

```python
# agents/common.py:996
if not _state_reaches_anyone(name or eid):
    drop.add("state")
```

`_state_reaches_anyone` asks `containment_conceals(sc, observer, ent_name)`
— and it is handed the entity's **display name**, while `scene.positions` and
`scene.contained` routinely key that same entity by its **id**.
`world/spatial_identity.canonical_subject_map` refuses to fold a lone
entity-id key on purpose (`spatial_identity.py:211-218`: "`positions`
legitimately keys objects, fixtures and unregistered presences by id … the
fold only fires when the canonical name is already live as a subject spelling
somewhere in this scene"). So for the ordinary id-keyed entity the lookup
misses, `containment_conceals` answers `False`, and the gate passes.

Reproduced against the exact story `tests/test_enclosed_act_leak.py` was
written for, with the enclosed body keyed by id instead of by name:

```
conceal by eid : True
conceal by name: False
{"Ada": {"name": "Ada", "kind": "object",
         "state": {"posture": "unfolding a sheet of paper and reading it"}}}
```

That posture string is the leak the whole file exists to close — its own
docstring says so (`common.py:943-951`: "Observed live: a body shut inside a
container had its every act written out in `state` while no perceiver in the
call had any sight of it at all"). And the module's own worked example for
name-vs-id is in the docstring twenty lines above (`common.py:928-935`:
"entity `tardis_001`, display name 'Blue Police Box'").

**Every test in `tests/test_enclosed_act_leak.py` keys the enclosed entity by
its display name** (`ENCLOSED = "Ada"` is simultaneously the dict key, the
`name`, and the `contained` key — `tests/test_enclosed_act_leak.py:52-72`), so
the suite exercises only the arrangement in which the bug cannot appear.

The sibling guard in this same file gets it right and shows what the fix
looks like: `_check_presence_knowledge_channel` asks both spellings —
`e_room = (positions.get(eid) or room_of(sc, eid) or room_of(sc, name))`
(`common.py:3451-3454`), and likewise `hiding_holders_of(sc, eid) or
hiding_holders_of(sc, name)`. Two representations of one lookup, one correct.

**Why it matters:** this is the shape AGENTS.md § Information boundaries #4
names — "look for guards that CANNOT fire rather than guards that fired
wrongly". It fails open, silently, and delivers act-naming objective state to
a mind with no channel to it.

### 2. `_check_pronoun_fidelity` cannot fire for a non-Latin cast name — the documented Japanese fix landed half-way

`_pronoun_to_group` carries a docstring celebrating a fix
(`common.py:5212-5222`):

> Built at MODULE level before, which evaluated `_ling` once at import with
> the contextvar still at its "en" default. The Japanese pack deliberately
> adds 彼/彼女/彼ら groups and every one of them was dead, so the pronoun
> fidelity check silently returned nothing for a Japanese story.

The pronoun map is now per-story. The **name** tokenizer three lines into the
consumer is not:

```python
# agents/common.py:5280
for token in re.findall(r"[A-Za-z']+", canonical):
```

`token_owner` therefore ends up empty for any cast member whose name is not
spelled in Latin letters, and `_check_pronoun_fidelity` returns `[]` at line
5290-5291 before it ever consults a pronoun. Run:

```
_check_pronoun_fidelity('Hinami Sato lifts his hand.', {'Hinami Sato': she/her})
  -> ["Pronoun mismatch for 'Hinami Sato' (canonical she/her/hers): prose renders 'his'"]
_check_pronoun_fidelity('佐藤ヒナミ lifts his hand.', {'佐藤ヒナミ': she/her})
  -> []
_check_pronoun_fidelity('佐藤ヒナミは彼の手を上げた。', {'佐藤ヒナミ': she/her})
  -> []
```

The guard the fix was written to revive is still dead in the language it was
revived for. Same tokenizer, same consequence, in five more places:

| site | ASCII-only construct | consequence for a non-Latin name |
|---|---|---|
| `_significant_name_tokens` `common.py:2101` | `re.findall(r"[A-Za-z']+", …)` | `_recognizes`' rank/title tolerance dead (fails closed — over-anonymises) |
| `_player_name_forms` `common.py:2949-2952` | `re.split(r"[\s,]+")` + `clean[:1].isupper()` | only the full name is a form; `・`-joined names never split |
| `_actor_reference_patterns` `common.py:5566-5580` | article list + `display[:1].isupper()` + `[A-Za-z']+` | a cast name under 4 characters yields `[]`, so `_check_quote_attribution` and `_check_position_fidelity` decline entirely (`ヒナミ` is 3) |
| `_check_narrator_fidelity` `common.py:5834-5835` | `\b[A-Z][a-z]+…` | the proper-noun-fidelity check sees no names at all (see also finding 12) |
| `_check_quote_attribution` `common.py:5660` | `\b(he\|she\|they)\b` | the ambiguity brake never engages, so the check is *less* conservative in Japanese than in English |

### 3. The two dangling-speech healers still do not share one vocabulary, and in Japanese neither has any Japanese in it — *measured*

`common.py:4575-4581` states the invariant:

> ONE vocabulary, shared with the colon healer below. These two lists drifted…
> A dangling verb and a dangling colon are the same wound from the same cut,
> and there is no reason for them to disagree about what counts as speech.
> `_SPEECH_CUE` is defined below and reused here.

Three things are wrong with that paragraph, and the third is the finding.

1. `_SPEECH_CUE` is defined **above**, at `common.py:101`, not below.
2. It is not "reused here": nothing on the runtime path reads it. It is an
   eager English compile (`english_linguistic`) whose only reader anywhere in
   the repo is `tests/test_echo_colon_heal.py:97`. The healers read
   `_ling("_DANGLING_SPEECH_VERB_RE")` and `_ling("_DANGLING_SPEECH_COLON_RE")`,
   which are independent literal patterns in the pack.
3. The two still disagree. Extracted from `language_packs/*/cards/linguistics.json`:

```
en  _SPEECH_CUE == colon-healer vocabulary?  True
    verb-healer knows and colon-healer does not: call, called, calls, shout, shouted, shouts
ja  _SPEECH_CUE == colon-healer vocabulary?  False
    _SPEECH_CUE   Japanese verbs: ささやく つぶやく 叫ぶ 囁く 尋ねる 答える 言う 話す
    _DANGLING_SPEECH_VERB_RE  Japanese verbs: (none)
    _DANGLING_SPEECH_COLON_RE Japanese verbs: (none)
```

`tools/build_japanese_pack.py:266` appends the Japanese speech verbs to
`_SPEECH_CUE` — the one entry nothing reads — and leaves both healer patterns
English-only. So for a Japanese story `_strip_player_echo` and
`_cap_repeated_quotes` cut the player's line out and heal nothing, on every
turn, silently.

The test pair that should have caught it instead **records the asymmetry as
intended**: `test_the_verb_healer_and_the_colon_healer_share_one_vocabulary`
(`tests/test_echo_colon_heal.py:87-101`) asserts only one direction
(cue ⊆ verb-healer), and its neighbour
`test_the_verbs_the_colon_healer_never_had_are_kept` (`:105-111`) asserts that
`call`/`shout` live in the verb healer alone. Both assert against the eager
English objects, so neither can observe the Japanese pack at all.

### 4. `_muffle_middle` ignores the pack's `muffle_join` — the typesetting fix landed in one of the two muffling functions

`_muffled_fragment` carries a comment explaining exactly this class of defect
(`common.py:3941-3945`):

> The glyphs belong to the language: Japanese sets an ellipsis as the doubled
> three-dot leader with no spaces (……棚……小瓶……) … The pack's own
> `muffled_indistinct` already used the right form, so the same feature was
> being typeset two different ways.

It still is. `_muffle_middle` — the interaction-loop half, called from
`agents/loops.py:157` — joins its surviving chunks with a hardcoded ASCII
space:

```python
# agents/common.py:3909
return " ".join(kept[start:start + keep])
```

The pack defines `muffle_join = "……"` for `ja` (and `"... "` for `en`);
`_muffled_fragment` reads it at `common.py:3947` and `_muffle_middle` does
not. The docstring immediately above the offending line
(`common.py:3899-3900`) asserts the opposite: "Shares `_muffle_tokens` with
`_muffled_fragment` so there is ONE rule for what survives half-hearing."
What is shared is the token *selection*; the rendering is two rules.

### 5. `_MENTAL_VERBS` silently makes ordinary physical acts imperceptible — reproduced

`norm_sequence` defaults an action's `observable` surface to `""` when
`_is_mental_action` says the act is interior (`common.py:1964-1967`), and
`observable_action_text` returns `""` so every deterministic delivery site
skips the element (`common.py:167-181`). `_is_mental_action` checks the
**leading token** of `attempt` against `_ling("_MENTAL_VERBS")`, whose English
list is:

```
assume believe concentrate consider decide deliberate doubt fear FEEL FOCUS
hope imagine intend know plan ponder realise realize recall recognise
recognize recollect REFLECT remember RESOLVE sense think understand
visualise visualize wonder
```

Five of those (`feel`, `focus`, `reflect`, `resolve`, `sense`) lead ordinary
physical interactive-fiction actions. Run:

```
'feel along the wall for the light switch' -> observable='' | delivered: False
'focus the lantern beam on the lock'       -> observable='' | delivered: False
'reflect the beam down the corridor'       -> observable='' | delivered: False
'grip the lever and pull'                  -> observable='grip the lever and pull' | delivered: True
warnings: []
```

No warning is raised — `norm_sequence`'s `warn` callback is used only for
stage-direction promotion (`common.py:1867-1869`). The act reaches no
perceiver's view, no composer percept, and no witness's memory, and the only
trace is an empty string in the stored variant. This is the engine's
signature failure shape: it does not error, does not warn, and shows up
later as a character who did not react to something that plainly happened.

`_is_mental_action`'s docstring calls the check "Conservative: only the
leading token is checked" — true of *where* it looks, false of *what it
matches*.

### 6. `_extract_authority_claims`' self-subject fallback is scoped per ELEMENT, not per EFFECT — *measured*, 112 of 306

The docstring says why the fallback exists (`common.py:1352-1355`):

> Without this those claims carried subject_id=None and tripped the resolve
> reconciliation's 'no resolvable subject' note every beat.

The guard is:

```python
# agents/common.py:1403
self_subject = actor_name if not (event.get("targets") or []) else None
```

`targets` is a property of the whole action element; the effects hanging off
it are separate claims. So an element that both acts on somebody **and**
asserts something about the player's own body loses the subject on the body
claim — and `_named_cast_subject`, the guard added to catch a claim plainly
about someone else, is nested *inside* `if self_subject and target_forms`
(`common.py:1404`) and therefore cannot run either.

Measured over the 400 most recent stored `director_interpret` active variants
in `engine.db` (read-only):

| | count |
|---|---:|
| `scope="effect"` authority claims | 306 |
| …with `subject_id` null | **112 (36.6%)** |
| …with an empty `predicate` | 7 |
| …carrying `subject_inferred` | 7 |

Over the whole stored corpus: 856 of 1,673 effect claims (51.2%) carry no
subject. Every one of those lands in `director_reconcile._player_claim_findings`'s
"no resolvable subject; coverage not checkable" note
(`agents/director_reconcile.py:83-88`) — the player's asserted effect is never
held against the diff at all. Live examples, verbatim from variant 29272:

```
{'claim_id': 'claim:1:effect:0', 'scope': 'effect', 'subject_id': None,
 'predicate': 'Hinami is seated on the bed', 'commitment': 'asserted',
 'source_text': 'Hinami sits down on the double bed, … and turns her
                 attention to watch The Doctor.'}
```

The element's `targets` names The Doctor, so the claim about Hinami's own body
— the player's — is never checked.

**Second, smaller half:** 48 of 2,055 stored claims (2.3%) have an **empty**
`predicate`, because `_normalize_effect` passes a dict through untouched
(`common.py:1321-1322`) and the claim is minted with
`eff.get("kind", "")` (`common.py:1430`, `1455`). An empty predicate with a
resolvable subject becomes an omission reading `player-asserted completed
effect '' on <subject>` (`director_reconcile.py:123-127`), which buys a full
`resolve_repair` Director call for a claim with no content.

### 7. `_inflect` has no caller, and the `_STEMS` pack entries it generated are a hand-maintained duplicate that has already drifted

`_inflect` (`common.py:3110-3120`) turns a verb stem into an inflection regex
and carries a real bug-fix docstring about phrasal-verb heads. It is called
**nowhere** — verified `grep -rnw _inflect` over every tracked `*.py`: one
hit, its own `def`.

It was the generator for the four `_VERBS` alternation regexes in the
language packs. Both representations are now stored side by side in
`linguistics.json`, only the regex is read, and nothing regenerates one from
the other:

| pack key | read by | |
|---|---|---|
| `_LOCOMOTION_VERBS` `_PLAYER_ACT_VERBS` `_ATTRIBUTION_VERBS` `_MANIPULATION_VERBS` | `common.py` (5 sites) | live |
| `_LOCOMOTION_STEMS` `_PLAYER_ACT_STEMS` `_ATTRIBUTION_STEMS` `_MANIPULATION_STEMS` | **nothing in the repo** | dead |

`tools/build_japanese_pack.py` maintains both by hand, twice, adjacent
(lines 249/250, 252/253, 290, 293) — and has already drifted:
`_PLAYER_ACT_VERBS` gained `上げる 下げる 開ける 閉める` that
`_PLAYER_ACT_STEMS` never got. Harmless today because nothing reads the
stems; it is the trap a future reader who wires them up walks into.

Four more `agents.common` pack entries are read by nothing anywhere:
`ASSERTION_SKIP_CUES`, `_SPEECH_CUE` (finding 3), `_SPEECH_VERBS`,
`_SPEECH_VERB_RE`. Eight of the section's 69 keys are dead, and five of them
were translated into Japanese by hand.

### 8. AGENTS.md's `_delivery_ok` invariant is not true of the code; the test that guards it asserts existence and restates the implementation

AGENTS.md:199 states it as an architectural guarantee:

> The unified delivery gate `_delivery_ok` in `agents/common.py` consolidates
> containment, awareness, sight (including rear-arc/`behind_sources`), and
> hearing (with proximity) checks. **Every deterministic delivery site must
> call it** rather than using scattered bare checks.

`docs/guides/PIPELINE.md:499-501` and `docs/guides/ENGINEERING.md:268` repeat
it, and `_delivery_ok`'s own docstring names three sites it unified — "the
micro-loop … the outcome action backstop … the background channel"
(`common.py:2365-2370`).

Repo-wide, `_delivery_ok` has **two call sites, both in one module**:
`agents/loops.py:122` and `:164`. `agents/perception.py` mentions it only in
a comment (`:4174`); `agents/composer.py` and `agents/background.py` never
touch it. `docs/UNBUILT.md:3489-3491` already records this ("Two families of
delivery gate now exist"), so **AGENTS.md is the copy that is wrong**, and per
`CLAUDE.md` the register wins.

The regression test does not close the gap either.
`tests/test_pipeline_audit_leak_gaps.py:302-312` opens with the same claim in
its class docstring — "the single predicate every deterministic delivery site
calls" — and nothing below verifies a call site. Two of its members are
weaker than they read:

- `test_delivery_ok_exists` (`:327-329`) is `assert callable(_delivery_ok)` —
  an assertion by existence, in a class whose own docstring says the previous
  version of these tests "was vacuous".
- `test_hearing_applies_the_proximity_downgrade` (`:375-378`) ends with
  `assert _delivery_ok(…, "hearing", volume="mutter", proximity="far")
  == (hear_level(rel, "mutter", proximity="far") != "none")`. That is
  `_delivery_ok`'s hearing branch transcribed (`common.py:2398-2401`), with
  `senses=None`. It cannot fail for any implementation of that branch.

### 9. `observer_label_fn` and `observer_name_scrub` use exact `known` membership while `_recognizes` sits 30 lines above them

`_recognizes` (`common.py:2109-2135`) exists to admit a rank/title variant of
a person the observer knows, and its docstring says where it lives and why:

> Lives here (not in `agents/perception.py`) so the narrator payload builders
> resolve speaker displays with the SAME recognition rule perception used to
> build the view — role modules never import each other.

The two identity floors defined immediately below it do not use it:

```python
# agents/common.py:2182   observer_label_fn
if not text or text == observer_name or text in known:
# agents/common.py:2240   observer_name_scrub
if not name or name == observer_name or name in known:
```

`observer_label_fn`'s own docstring asserts they cannot drift: "Same rule as
`agents/perception.py`'s own gate, from the same `known` map and through the
same `_unknown_actor_label`, so this is one identity floor rather than a
second one that can drift from it." Perception's prose gate is
`_recognizes`-based at nine sites (`perception.py:1036, 1056, 1618, 1813,
2016, 3310, 3751, 4254, 4285`). It is not the same rule.

The direction is safe — these two over-scrub, replacing a known person's
title-variant with a stranger descriptor — so the cost is quality, not a
leak: a character who knows "William T. Riker" reads a lore paragraph about
"the unfamiliar person" where perception would have said "Commander Riker".
AGENTS.md:43 makes the same claim the docstring does ("both read the same
`known` map"), which is true of the map and false of the predicate.

### 10. `_conceal_from_targets_observer` fails open on a malformed sheet, silently

```python
# agents/common.py:286-289
try:
    keys = {k.casefold() for k in character_scene_keys(observer_sheet)}
except Exception:
    keys = set()
```

`conceal_from` is documented one line above as "an absolute exclusion list".
When `character_scene_keys` raises, every name/uid/alias form of the observer
is dropped and only the numeric-id form survives — so a `conceal_from` entry
written as a NAME (which the schema permits, and which the docstring says
readers "must resolve against ALL of the observer's handles") stops matching
and the concealed line is delivered to the person it was concealed from. No
warning, no counter. The house rule is `AGENTS.md` § Information boundaries
#2: a leak is an engine failure. This is the one bare `except` in the file on
a firewall path.

### 11. `_delivery_ok`'s self-check is a bare `==` where `region_visibility` in the same file uses `same_subject`

```python
# agents/common.py:2392
if observer_name == source_name:
    return True
```

versus, 1,750 lines earlier:

```python
# agents/common.py:634
if not same_subject(sc, observer, body):
```

with `region_visibility`'s docstring spelling out why (`common.py:612-614`):
"`same_subject`, not `==` — a being routinely carries a display name and an
entity id at once". AGENTS.md's body-enclosure row makes it a rule: "five
separate defects here were a single `==` between them, including a firewall
that failed OPEN".

Here the miss direction is closed, not open — a body whose two spellings do
not match `==` is denied its *own* percept rather than granted someone
else's, which is the `_self_cannot_see_own_surface` class of defect. Both
current callers pass display names, so it does not bite today. It is the same
`==` the rule was written about, in the file that documents the rule.

### 12. `_check_narrator_fidelity`'s proper-noun check only ever sees multi-word names

```python
# agents/common.py:5834-5835
view_names = set(re.findall(
    r"\b[A-Z][a-z]+(?:\s+(?:of\s+)?(?:the\s+)?[A-Z][a-z]+)+\b", view_text))
```

The `(?:…)+` is one-or-more, so a single-token name never matches:
`"Hinami says hello. The Doctor nods. Elyra Voss waits."` yields
`['The Doctor', 'Elyra Voss']` and drops `Hinami`. Every warning under
"Proper noun from view missing in narrator prose" is therefore structurally
unavailable for a single-name cast — the commonest shape in this engine's own
stored stories. The comment beneath (`:5839-5842`) explains the *surname*
fallback and says nothing about the multi-word requirement, so it reads as
though single names are covered.

### 13. Roughly 35 comment blocks document constants the module no longer has, and one is attached to the wrong symbol

The language-pack extraction moved ~40 word lists and regexes out of this
file into `language_packs/*/cards/linguistics.json`. The comments that
explained *why each list is drawn where it is* stayed behind, and now sit
above unrelated functions. A sample, with the vanished symbol each describes:

| lines | describes | now sits above |
|---|---|---|
| 61-70 | `_MENTAL_VERBS` | another orphan comment |
| 72-80 | `_AUTONOMY_VERBS` / `_AUTONOMY_PHRASES` | another orphan comment |
| 83-86 | `_SUBJECT_LEADS` | `def _ling` |
| 111-113 | `_CLAUSE_BREAKS` | `def _predicate_after_name` |
| 1642-1644 | `_OVERLAP_STOPWORDS` | `def split_stage_directions` |
| 2093-2094 | `_NAME_TITLE_TOKENS` | `def _significant_name_tokens` |
| 2433-2449 | `_COMMON_WORD_NAMES`, `_QUOTED_SPAN_RE` | `def _scrub_unknown_identities` |
| 2926-2933 | `_PLAYER_ACT_VERBS` — **two stacked drafts of the same paragraph**, the first superseded by the second | another orphan comment |
| 3482-3489 | `_INTERIOR_STATES`, `_INTERIOR_VERBS`, `_INTERIOR_CERTAINTY` | `def _check_player_interiority_authority` |
| 3566-3581 | `_MANIPULATION_VERBS`, `_OWN_BODY_NOUNS`, `_DIRECT_OBJECT_RE` | `def _undeclared_world_object` |
| 4215-4226 | `_YOU_AGREEMENT`, `_NON_VERB_S_WORDS`, `_ES_STEM_ENDINGS` | `def _base_from_third_person_s` |
| 4855-4864 | the view-dedupe splitter **and** the dialogue attribution cue — two unrelated orphans run together | `_YOU_RE = re.compile(...)` |
| 5499-5504 | `_NARR_LOWERING` / `_NARR_RAISING` | `def _check_action_direction` |

Two of these are worse than misplaced:

- **`common.py:2976-2980`** documents a bare-pronoun-subject regex
  (`_SUBJECT_PRONOUN_RE`) and sits directly on `_SUBJECT_OPENERS = {}`, which
  is a compiled-pattern cache. Read against the symbol it sits on the comment
  is false, not merely stray — the same shape as `AUDIT_DIRECTOR.md` finding 2.
- **`common.py:3799-3803`** says the two quote-span patterns are "constants,
  hoisted to module level like the other hot-path patterns in this file
  (`_QUOTED_SPAN_RE` etc.) — each was being re-compiled on every narrator
  validation pass." No constant follows; they are `_ling(...)` lookups now,
  and the performance claim describes an arrangement that no longer exists.

The pack JSON carries no prose (only `_YOU_AGREEMENT` and `_PRONOUN_GROUPS`
have any extra keys at all), so the design rationale for forty deterministic
word lists is now stranded in a file that does not hold them, and the data a
maintainer edits has none.

### 14. A stale symbol name warns about a duplicate that does not exist

```python
# agents/common.py:3107-3109
# NOTE the distinct name: `_SPEECH_VERBS` further down is a different thing
# (a literal tuple used for dialogue-cue detection). Two symbols of that name
# in one module is exactly the duplicate `make structure` fails on.
```

There is no `_SPEECH_VERBS` in `agents/common.py`, "further down" or anywhere
— verified `grep -rnw _SPEECH_VERBS` over every `*.py`: one hit, this comment.
The name survives as a pack key that nothing reads (finding 7). The comment
sends the next reader looking for a collision hazard that was resolved by the
extraction.

### 15. Eight inline quote-span regexes in three spellings, beside ten pack-side quote patterns

"What counts as a quoted span" is answered at least eighteen times in one
6,186-line module whose central job is quote fidelity.

Inline, hand-written:

```
3172  r'"[^"]*"|“[^”]*”'      _check_character_speech_authority
3243  r'"[^"]*"|“[^”]*”'      _check_character_act_authority
3776  r'"[^"]*"|“[^“”]*”'     _check_player_act_authority
4640  r'["“]([^"“”]{1,})["”]' _protected_view_quotes
4931  r'["“]([^"”]*)["”]'     _scrub_invented_dialogue
5296  r'"[^"]*"|“[^“”]*”'     _check_pronoun_fidelity
5713  r'"[^"]*"|“[^“”]*”'     _check_position_fidelity
5760  r'"[^"]*"|“[^“”]*”'     _check_portal_fidelity
```

Note lines 3172/3243 use `[^”]*` where 3776/5296/5713/5760 use `[^“”]*`: the
first pair spans **across** a nested opening curly quote, the second stops at
it. So the two character-authority guards strip a wider region of prose than
the three narrator-fidelity guards do, on the same input, for no stated
reason.

Pack-side, ten more: `_QUOTED_SPAN_RE`, `_VIEW_QUOTED_SPAN_RE`,
`_QUOTE_SPAN_RE`, `_QUOTE_BODY_RE`, `_PROSE_QUOTE_RES`, `_EMPTY_QUOTE_RE`,
`_NARRATION_QUOTE_RE`, `_NARRATION_SQUOTE_RE`, `_NARRATION_DOUBLED_QUOTE_RE`,
`_NARRATION_DANGLING_QUOTE_RE` — several with careful comments about
apostrophe-awareness (`common.py:2437-2449`) that the eight inline copies do
not have. Every inline copy is invisible to a language pack.

### 16. Eight guards hardcode English where their siblings go through the pack

`_ling(...)` resolves 61 distinct pack keys in this file. These are the sites that were
missed, all of which run on every story regardless of language:

| line | literal | function |
|---|---|---|
| 1300-1303 | `("attack","grab","restrain","steal","break","force","cast","shoot","stab","strike","move into","leave","enter")` | `_requires_director_resolution` — its sibling `_requires_reaction_phase` reads `_ling("_REACTIVE_VERBS")` for the same job (`:1259`) |
| 4292 | `("she","he","they","it")` | `_observable_predicate` |
| 4416-4421 | four `"no visual sign of the speaker is visible"`-style patterns | `_inject_visible_actor` |
| 4916 | `"something about "` | `_scrub_invented_dialogue` |
| 5566 | `("the","a","an")` | `_actor_reference_patterns` (the pack has `articles`, used at `:3973`, `:4300`) |
| 5660 | `\b(he\|she\|they)\b` | `_check_quote_attribution` |
| 5698, 5727 | `("room","area","here")`; `(?:back\s+)?(?:in\|inside\|within\|into\|at)` | `_check_position_fidelity` |
| 5749-5750 | `_PORTAL_OPEN_RE` / `_PORTAL_SHUT_RE` | `_check_portal_fidelity` |

`_requires_director_resolution` is the consequential one: it is the
interaction loop's commonest early exit and it ends the BEAT
(`docs/guides/PIPELINE.md` § `interaction_loop`), so in a non-English story
its conflict-verb backstop is inert and the loop's bound is `commitment`
alone.

### 17. `apply_player_authority` re-derives the mode normalization, and its unknown-mode fallback lands on the *most permissive* rung

```python
# agents/common.py:3682-3684
mode = str(mode or "world_author")
granted = PLAYER_AUTHORITY_GRANTS.get(
    mode, PLAYER_AUTHORITY_GRANTS["world_author"])
```

`story/scene.py:1667-1669` already owns this: `normalize_player_authority`
folds anything unrecognised to `DEFAULT_PLAYER_AUTHORITY`, and
`player_authority(chat_id)` runs it on both the stored mode and every history
entry. The one production caller (`agents/director.py:801`) therefore passes
an already-normalized value, so the fallback here is a second copy that never
fires — until someone calls the function directly, which the `agents`
compatibility facade re-exports it for.

`world_author` grants `{own_body, own_effect, world}` — the whole ladder. So
an unreadable mode silently grants full world authorship with no warning. It
is defensible as "an unreadable level falls to the DEFAULT, never to the
floor" (AGENTS.md's offscreen rule) only because the default here *is* the
ceiling; the same code under a stricter default would be the opposite rule.

### 18. Two functions with no production caller and a dedicated test file each

- **`_detect_narration_person`** (`common.py:5188-5205`). Zero callers outside
  `tests/test_narration_person.py`. Production resolves person through
  `agents/narration._resolve_narration_person`, which calls
  `_narration_person_counts` directly and applies its own hysteresis. Five
  assertions in `tests/test_narration_person.py:39-81` exercise a function
  the pipeline does not use; the file's own header
  (`tests/test_narration_person.py:6-9`) lists it beside the live resolver as
  though both were on the path.
- **`_player_subject_sentences`** (`common.py:2958-2973`). Zero callers outside
  `tests/test_player_act_authority.py`. It was superseded by
  `_sentence_subjects`, whose docstring (`common.py:3017-3023`) cites it by
  name as the thing that "deliberately refuses to resolve pronouns … which is
  why the live miss (chat 56 t1391) slipped through". The superseded version
  is still exported, still tested, and still reads as an alternative.

### 19. Four facade re-exports with no consumer anywhere

`agents/__init__.py` re-exports 53 names from `common.py`. Four have zero
references outside `agents/__init__.py` and `agents/common.py` in any tracked
`*.py`: `_text_piece`, `_classify_action_commitment`, `_normalize_effect`,
`_llm_resolve_player_room`. All four are live *internally*; it is the
compatibility surface that is dead.

### 20. A truncated sentence in `_check_prose_quote_authority`

```python
# agents/common.py:3307-3311
# Measured across the live corpus: 14 flags, 13 of them cleared by
# this test -- a 93% false-positive rate on a guard whose every
# firing costs a full second Director call, the most expensive
# ONE DIRECTION ONLY: the flagged span must sit INSIDE something
```

"the most expensive" runs straight into "ONE DIRECTION ONLY". A line was lost
in an edit. Patch debris of the kind `make structure` looks for, in a comment
carrying a measurement (93% false positives) that is the whole justification
for the carve-out below it.

### 21. Smaller notes

- **`_llm_resolve_player_room`** (`common.py:5951-5979`) is the only LLM call
  in this module, and it is on the bare `chat_complete` + `jparse` path that
  `_agent_json`'s own docstring 4,500 lines above warns against
  (`common.py:1481-1483`). Its whole body is wrapped in
  `except Exception: pass`, so a provider failure is indistinguishable from
  "no match" and the caller silently returns `None` for the player's room.
  Defensible (its output is checked against `positions` before use), but it is
  a model call sitting in the module that role modules import for
  determinism.
- **`norm_sequence`'s ponder branch** (`common.py:1896-1904`) drops the whole
  private query when either `query` or `why` is empty, with no warning. A
  ponder is by design not in the public sequence, so nothing downstream can
  notice it went missing.
- **Redundant deferred imports**: `from core.db import wget` at
  `common.py:801` and `:857` re-imports the module-level import at `:26`; and
  `_compositor_value` (`:3891-3893`) is a deferred-import wrapper around the
  `compositor_value` already imported at `:28` and called directly at `:3973`,
  `:4017`, `:4300`, `:4496`. Two names for one function, used in the same
  file.
- **`_SUBJECT_OPENERS`** (`common.py:2980`) is an unbounded process-global
  regex cache keyed by name form, never cleared. Bounded in practice by cast
  size across all chats in a process; worth a note only because it is the
  file's one piece of mutable module state.
- **`observer_body_regions`** (`common.py:686`) treats an explicitly empty
  `body_labels` dict as "no labels supplied" and substitutes a self-only map,
  so "gate nobody" and "gate the default" are the same argument.

---

## Part 2 — what the code actually does, checked against the documents

The file has no section markers; these groupings are mine, in file order.
Verdicts: **RIGHT** / **STALE** / **LOST**, per `AUDIT_DIRECTOR.md`'s
convention.

### Language-pack access and interior-act classification (`common.py:89-181`)

`_ling(name)` is a keyed lookup into the active story pack under the literal
key `"agents.common"`, resolved at use time; `_text` wraps `compositor_text`.
Two eager English compatibility constants exist for tests (finding 3/14).
`_is_autonomous_response`, `_is_mental_action` and `_predicate_after_name`
classify an action element as the player's own predicate or as another mind's
interior/volitional business, and `observable_action_text` returns the
outward surface (or `""` for an interior act).

**Docs: RIGHT** on the boundary, **STALE** on the symbol home. AGENTS.md:43
lists `agents/common.py (_delivery_ok, _AUTONOMY_VERBS, bind_sequence_targets)`
as the perception-leakage edit route; `_AUTONOMY_VERBS` has not been a symbol
in this file since the pack extraction — it is `language_packs/*/cards/
linguistics.json` → `agents.common._AUTONOMY_VERBS`, and the routing row sends
an editor to the wrong file. The behaviour AGENTS.md § Authority boundaries
describes ("An interior or autonomous outcome the player authors FOR a
character … is rerouted to an offer") is implemented exactly as written in
`authored_other_subject` (`:1100-1176`), including the two shapes and the
predicate scoping.

### Attire and body projection (`common.py:395-780`)

`attire_view` / `compact_attire` / `scene_*` project a body's clothing through
`attire.rederive_entry` so `wearing`, `state` and `regions` present as one
answer; `region_visibility` derives per-observer, per-region concealment with
three causes (`garments`, `containment`, `vantage`); `observer_body_regions`
turns that into the payload rows, gating extra parts on the same verdicts.

**Docs: RIGHT.** `Design.md:173` ("`agents/common.attire_view` is the shared
prompt projection, and `beneath` reaches no prompt unless the host sets
`attire_beneath`") is exact — `_beneath_visible` reads that setting
(`:406`), the route and the settings checkbox both exist
(`web/app.py:1878`, `static/js/settings.js:2281`), and an uncovered region
still reports itself uncovered. AGENTS.md's extra-parts row is likewise exact,
including the fail-closed unknown-region rule at `:748-757` — the one place in
this file where an unresolvable value is explicitly treated as concealment
rather than permission, with the chat-76 fox-ears case recorded in the comment.
`region_visibility`'s "safe-closed" claim was verified by running it: an
observer the scene cannot place gets all eight regions `concealed`.

### Scene-derived payload views (`common.py:783-1015`)

`crowds_for_room`, `couriers_for_room`, `artifacts_for_room` deliver
per-observer, own-room-scoped descriptions of the three mobile/immobile
presence kinds; `_perceptible_entities` strips lookup-only fields, withholds
an enclosed entity's `state`, and withholds an entity's exterior
`description` from its own occupant.

**Docs: RIGHT in intent, LOST in one arm.** AGENTS.md's carrier row —
"a satchel does not broadcast its contents" — is honoured by
`couriers_for_room`, which emits only figure, heading and waiting state
(`:867-889`). The crowd `talk` field is correctly own-room-only by
construction. The enclosed-`state` gate is the one that does not hold
(finding 1).

### Sequence normalization and authority claims (`common.py:1036-1461`, `1637-2070`)

`norm_sequence` is the single normalizer for every declared beat: it lifts
legacy `speech`/`actions` mirrors into a `sequence`, excises stage directions
written inside spoken text into their own action elements, dedupes a promoted
action against a properly declared one, carries speech concealment through,
and runs the concealment backstop that propagates a concealed action's
`conceal_from` onto a co-declared, not-explicitly-public speech line.
`_extract_authority_claims` mints the claim record the resolve seam holds the
diff to; `apply_player_authority` enforces the `PlayerAuthorityMode` ladder on
both the claim and the sequence element.

**Docs: RIGHT.** `docs/guides/PIPELINE.md` § `director_interpret` and
AGENTS.md § Authority boundaries describe this correctly, including the point
that a downgrade must move *both* representations. The known gap in the
concealment backstop is documented in the code itself
(`:2000-2009` — the addressee written into the SPEECH's own `conceal_from`
cannot be rescued here because `targets` carries a name and `conceal_from`
carries an id; `schemas._uncross_concealed_speech` does it) and is accurate.
`bind_sequence_targets`' contract — bind `targets`, never mirror onto
`target_id` — matches AGENTS.md's clause word for word. The subject-resolution
gap is finding 6.

`Design.md:179` says of `ActionStage`: "read on the resolve path by nothing
(`agents/common._requires_reaction_phase` is its one consumer anywhere)".
Accurate about the resolve path and about consumption; `agents/perception.py:2338`
does copy `stage` into a model payload, so "its one consumer anywhere" is true
only of code that acts on it.

### Identity floors (`common.py:2093-2543`, `4053-4158`)

Four mechanisms: `_unknown_actor_label` mints a stable descriptor for an
unrecognised body (dropping the actor's own name tokens first, truncating at a
linking participle, trimming a dangling function word);
`_scrub_unknown_identities` runs last on every view, replacing unknown forms
outside quoted spans with that descriptor and returning what leaked;
`observer_label_fn` / `observer_name_scrub` / `scrub_names_deep` gate a name
and a paragraph in any payload outside perception's own scrubbing; and
`self_name_forms` / `self_reference_forms` run the floor in the other
direction, so a mind is never told about itself in the third person by name or
by the epithet the engine minted for it.

**Docs: RIGHT.** `Design.md:203` ("A mind is never told about itself in the
third person, by name OR by the label strangers use for it", **Built**) checks
out clause by clause against `self_reference_forms` (`:4086-4158`): exact
minted labels plus one short definite form, guarded by `_GENERIC_LABEL_HEADS`,
by `avoid`, and by a three-word minimum, with no indefinite variant. The
CJK handling in `_scrub_unknown_identities` (`:2496-2510`) is genuinely
script-aware — a two-character Latin form is skipped as indistinguishable from
a word while a two-character CJK form is not, and allowed forms are matched
and replaced with themselves so a short unknown name cannot eat into a longer
recognised one. The predicate mismatch between the paragraph gate and
perception's is finding 9.

### The delivery gate and deterministic injection (`common.py:2360-2410`, `3994-4536`)

`_delivery_ok` answers awareness → containment → hearing (with proximity and
optional card senses) or sight (with `behind_sources` and the rear arc).
`_inject_dialogue`, `_inject_action`, `_inject_visible_actor` and
`_ensure_environment` are the deterministic backstops that append what the
perception path must deliver, each guarded by `_action_already_rendered`'s
content-token overlap so the model's own rendering is not duplicated.

**Docs: STALE.** `PIPELINE.md:499-501`, `ENGINEERING.md:268` and AGENTS.md:199
all state the "one predicate every deterministic site calls" invariant;
`UNBUILT.md:3489` records that it is not true and the code agrees with UNBUILT
(finding 8). The gate itself does what its docstring says, and the `senses`
caveat ("with an extraordinary-hearing card this can answer True at hearing
level `trace`, which is DETECTION ONLY") is honoured by its live caller
(`agents/loops.py:128-147`, which re-grades and emits a contentless hint).

### Narrator fidelity (`common.py:3266-3323`, `5333-5949`)

Ten deterministic checks feed `_check_narrator_fidelity`: player interiority,
proper nouns present, recycled prose from earlier turns, dialogue survived
verbatim, one quoted span per mouth, pronoun paradigm, player named under
first/second person, prose person matching the person asked for, event order,
quote attribution, position, portal state, and act direction.

**Docs: RIGHT.** AGENTS.md's narration row states the two-question split
precisely — "did the line survive … and did it land in the right mouth" — and
the merge check is its own pass (`:5915-5930`), keyed on `event_order` rather
than the raw dialogue log exactly as the row requires. The 0.52%-of-2,303
measurement quoted for `_check_narration_person_match` is recorded in the
docstring (`:5412-5415`) with the honest statement of what it cannot catch.
`_check_action_direction`'s two confidence tiers (reversed = enforceable,
missing = warning) match the row's "only add one whose false-positive rate you
have measured" discipline. Findings 2, 12, 15 and 16 are gaps *inside* these
checks, not disagreements with the docs.

### Player state assertions (`common.py:6011-6186`)

`validated_player_state_assertions` validates the player's declared changes as
a full `StateDiff` — shape only, no channel filter and no subject guard — and
mints a stub room for a position naming a place the scene does not have.
`preview_player_state_assertions` applies them to a deep copy in commit's own
order (`merge_scene_with_diff`, then `apply_attire_diff`).
`merge_player_state_assertions` carries them into the durable diff, with
resolve winning wherever it speaks about the same subject.

**Docs: RIGHT**, and this is the most exactly-documented section in the file.
AGENTS.md § Authority boundaries ("`director_interpret` is not a lesser
authority than `director_resolve`… a full `StateDiff`, the same channels
resolve uses, no subset") and `PIPELINE.md` § `perception_act` both describe
what the code does, including the two-call preview and the reason attire needs
its own applier. The mint-rather-than-refuse decision at `:6076-6117` is
argued in the code and consistent with `prepare_scene_commit`'s treatment of a
declared movement destination.

### Cross-document verdicts

| document | verdict |
|---|---|
| `Design.md:173` (clothing by region — the `attire_view` clause) | **RIGHT** |
| `Design.md:179` (`ActionStage` has one consumer) | **RIGHT** on the resolve path; `perception.py:2338` also carries it into a payload |
| `Design.md:203` (self-epithet floor, **Built**) | **RIGHT** — every checkable clause verified against `self_reference_forms` |
| `Design.md:233` (`declared_goal` as the single derivation) | **RIGHT** — `:2813-2837`, legacy field kept as fallback |
| `AGENTS.md:43` (perception/leakage edit route) | **STALE** — names `_AUTONOMY_VERBS` in `agents/common.py`; it lives in the language packs. The `observer_label_fn`/`observer_name_scrub` "same `known` map" clause is true of the map, false of the predicate (finding 9) |
| `AGENTS.md:199` (`_delivery_ok`, every site must call it) | **STALE** — two call sites, one module; `UNBUILT.md:3489` already says so |
| `AGENTS.md` § Authority boundaries (`bind_sequence_targets`, interpret-as-equal-authority) | **RIGHT** |
| `AGENTS.md` § narration row | **RIGHT** |
| `docs/guides/PIPELINE.md` § `perception_act` / `interaction_loop` / `narrator` | **RIGHT**, except the `_delivery_ok` sentence at `:499-501`, which inherits AGENTS.md:199 |
| `docs/guides/ENGINEERING.md:268` + its mermaid node at `:312` | **STALE**, same clause |
| `docs/CODE_MAP.md:148` (agents/common section) | **RIGHT** — it lists the eight largest functions by design, and all eight line numbers are current |

Nothing in this file was found built-and-quietly-lost in the sense
`AUDIT_DIRECTOR.md` uses: every mechanism the maintained guides claim for
`agents/common.py` exists and is reachable. What this read turned up instead
is a different shape — **five guards that exist, are tested, and cannot fire
in the situation they were written for**: the enclosed-state gate against an
id-keyed entity (1), pronoun fidelity against a non-Latin name (2), the
speech-healers against a Japanese story (3), the proper-noun check against a
single-word name (12), and the conflict-verb backstop against any story not
in English (16).

## Unverified suspicions

Stated separately because I could not close them.

- **`_action_already_rendered`'s thresholds** (0.6 per-sentence overlap, ≥2
  tokens with the actor named, ≥3 across the whole view — `:4307-4346`) are
  documented as "biases toward silence", but the cost of a false positive is a
  legitimately-new beat never delivered. I have no measurement of how often
  the whole-view arm suppresses a genuine second action by the same actor in
  one beat, and the stored corpus does not record what the injector declined
  to add.
- **`_dedupe_promoted_actions`' 0.8 overlap** against the *shorter* of the two
  token sets (`:1764-1766`) is asymmetric by design, but a two-word declared
  action and a longer promoted one can hit 1.0 on two shared content words. I
  did not find a live case; the shape is there.
- **`cut_short_speech`'s `_MIN_INTERRUPTIBLE_WORDS = 5`** and the `ratio=0.6`
  default are unmeasured in the file. The docstring says the cut point "was
  chosen by reading the output rather than by picking a number", which is a
  claim about the *position* of the cut, not the threshold.
- **`_check_prose_quote_authority`'s 93% false-positive measurement**
  (`:3307-3309`) predates the inner-quote carve-out that followed it. Whether
  the rate is now acceptable is not re-measured anywhere I could find, and the
  guard still costs a full Director call per firing.
- **`_scrub_invented_dialogue`'s clause surgery** (`:4926-5012`) computes
  boundaries with a hand-rolled quote-depth toggle over `'"“”'`, which treats
  a curly-open and a curly-close identically. An unbalanced curly quote in the
  view should invert `inside` for the remainder of the text and move every
  subsequent boundary. I could not construct a live view that triggers it.
