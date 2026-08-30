# Building Language Packs

This is the maintained implementation guide for adding a human language to
Sonder Engine. English (`language_packs/en`) is the reference schema. Japanese
(`language_packs/ja`) is the first non-English worked example.

## The boundary

A language pack owns every engine-authored human-language surface:

- model system prompts and retry instructions;
- deterministic recognition rules, token/quote handling, and grammar cues;
- compositor, fallback-perception, and memory-episode prose;
- character/persona authoring defaults;
- browser labels, messages, errors, and text direction.

It does not translate protocol objects. JSON keys, schema field names, enum
literals, operation names, step names, identifiers, and body-region ids remain
canonical English. For example, a Japanese result still uses
`{"movement":{"to_room":"hall"}}`, while summaries and dialogue inside that
object are Japanese. This separation is mandatory because stored objects from
different languages must remain readable by the same deterministic engine.

## Directory layout

```text
language_packs/<language-id>/
  manifest.json
  prompt_policy.json
  ui.json
  cards/
    authoring.json
    compositor.json
    linguistics.json
    system_prompts.json          <- the INDEX: structure + $text references
    system_prompts/              <- the PROSE: one .txt per prompt leaf
      <top-level note>.txt
      prompts/<id>.txt
      specialists/<name>/core.txt
      specialists/<name>/chunks/<op>.txt
      prose_author_sheet/<NN>[_<key>].txt
```

Use a normalized lowercase BCP-47-like id (`ja`, `es`, `pt-br`). The directory
name and `manifest.id` must agree.

## 1. Manifest

Start from the English manifest and change identity, direction, version,
fallback, and adapter:

```json
{
  "schema_version": 1,
  "id": "ja",
  "name": "Japanese",
  "native_name": "日本語",
  "direction": "ltr",
  "version": "0.2.0-beta",
  "translation_status": "model-draft",
  "fallback": "en",
  "ui": true,
  "story": true,
  "adapter": "japanese",
  "coverage": {
    "authoring": true,
    "compositor": true,
    "deterministic_linguistics": true,
    "system_prompts": true,
    "ui": true
  },
  "cards": ["authoring", "compositor", "linguistics", "system_prompts"]
}
```

Do not declare coverage until it exists. The loader compares all required leaf
paths, prompt ids, and UI source ids with English and rejects missing data.
Coverage flags are a claim about behavior, not a request to inherit English
recognition silently.

## 2. Prompt policy and system prompts

`prompt_policy.json.common` is appended to every system prompt at the provider
boundary, including repairs and one-off utilities. It must say all of the
following in language the target model will reliably follow:

1. reader-facing free text must use the selected language;
2. JSON keys, fields, enums, ids, operations, steps, and body-region ids stay
   canonical English;
3. only free-text values are translated;
4. requested JSON must remain structurally valid.

Role suffixes can add language-specific craft guidance: Japanese person and
honorific consistency, Spanish gender/number agreement, Arabic direction and
register, and so on.

`cards/system_prompts.json` is an index whose prose lives in per-prompt files
beside it; see § 2a below before editing any prompt. The card must contain
every id in the English card. A pack
claiming linguistic completeness must translate every authored instruction;
bilingual text is acceptable when it improves model reliability, but a
byte-identical English body is not a translation. The output/schema contract
must always be written and tested for the target language. Never translate
literal schema examples inside a prompt.

## 2a. The split prompt card

`cards/system_prompts.json` is an INDEX, not the prompts. It holds the card's
structure -- assembly order, gate names, flags, allow-lists -- and, wherever a
prose leaf used to sit, a single reference:

```json
"prompts": { "narrator": { "$text": "prompts/narrator.txt" } }
```

The prose lives one leaf per file in the sibling directory `cards/
system_prompts/`. `language_runtime/card_source.py` owns the format and
`language_runtime._read_card` assembles the two at pack load, before fragment
resolution and before freezing. 111 part files per pack.

**Why.** The card reached 414 KB (English) and 525 KB (Japanese) as one JSON
document whose values are 62,000-character prompt strings with escaped
newlines. Editing one meant a surgical raw-text replace against an escaped
blob -- slow, unreviewable as a diff, and the shape that turns a one-word fix
into an accidental reflow of everything around it.

**The path is derived, never chosen.** `canonical_part_path` maps a leaf path
to exactly one file path, and the loader REJECTS a reference that spells it
any other way. So the paths stay greppable (`grep -rn
'prompts/character.txt'`) while drift stays impossible. The prose-author sheet
is named index-first, key-second (`00_voices.txt` ... `27.txt`) because the
index is the identity: `mapping_proposal` is the gate name at both 11 and 15,
and 12 of the 28 segments have no name at all. Index-first also sorts the
files into assembly order in any listing.

**The file format, and the one convention in it.** A part file is the leaf's
exact text plus a single trailing newline. Reading strips exactly one trailing
newline if present, and nothing else.

That convention exists because the dominant real-world corruption is an editor
adding a final newline on save. Of the 226 English leaves, **163 end with no
newline at all**, 48 end with `\n\n` and 15 with `\n` -- and the specialist
and prose-author sheets are built by bare `"".join` with no separator, so
every one of those terminators is a live joint in a shipped sheet. Under a
no-convention scheme, `files.insertFinalNewline` would silently change 163 of
226 prompts. Under this one, every file already ends with a newline, so the
editor's "fix" is a no-op.

**Never let an editor tidy these files.** Not one character. Two live
examples of why: `prose_author_sheet/20_world_pressure.txt` ends in a
SIGNIFICANT single space, and `prose_author_sheet/16.txt` is a single newline
and nothing else -- a paragraph break between two segments. Both are erased
by a `trimTrailingWhitespace` save. `.editorconfig` and `.gitattributes` at
the repo root say so to the tools; `tests/test_prompt_card_split.py` catches
it if they are ignored.

**What fails, and how loudly.** Every fault below raises `LanguagePackError`
at pack load, which is negative-cached and stops the server starting and the
suite collecting. There is deliberately NO path on which a lost part yields a
SHORT prompt -- a truncated sheet that loads is a silent behaviour change read
by every story in that language:

- a reference whose file is missing, empty, BOM'd or CR-bearing;
- a reference at a non-canonical path, or one escaping the parts directory;
- a `.txt` no reference claims. That is the new-prompt-written-but-never-
  shipped case, and it is the only one that would otherwise be invisible.

**Editing a prompt.** Open the `.txt`, change it, and add the leaf's dotted
path to `tests/data/prompt_cards_presplit/EXPECTED_DIVERGENCE.json` with a
one-line reason, in the same commit. That ledger is what keeps
`test_assembled_card_matches_the_pre_split_reference` meaningful: the
pre-split reference is immutable and drift from it is enumerated rather than
re-baselined, so a deliberate edit costs one line and an accidental
whitespace change costs a red test.

**Reading authored text from code.** Use `language_runtime.raw_card(language,
card)` -- assembled from its parts, mutable, and UNRESOLVED. Do not read the
JSON file (since the split it holds no prose, so a grep over it passes by
finding nothing), and do not use `pack.card(...)` for an audit of authored
text: that one is frozen and has already substituted four fragments into
seventeen bodies.

**Two things that must not be done.**

1. `prose_author_sheet[27][1]` is byte-identical to
   `prose_author_output_shape`. They get two files and stay duplicated.
   Deduping them behind a shared reference is a behaviour change wearing a
   refactor's clothes: the two are read by different assemblies and either
   may legitimately change without the other.
2. The seven ids in `llm.prompts.ASSEMBLED_SHEET_IDS` are BUILT from
   specialists and `prose_author_sheet` and must never get a part file of
   their own. A stored body beside the parts is one sheet with two
   spellings, free to drift -- and English `director_spatial` had already
   drifted 1,518 characters short of its own assembly while the prompt
   editor displayed the stored one as the sheet.

`authoring.json`, `compositor.json` and `linguistics.json` are NOT split and
should not be. `linguistics` is regexes and verb inventories -- machine data,
where splitting makes a diff harder to read, not easier. A card with no
references and no parts directory passes straight through the loader, so
splitting one later needs no loader change.

## 3. Deterministic linguistics

`cards/linguistics.json` supplies the values loaded by `linguistic()` at use
time. Pipelines carry their language in a context variable, including worker
threads and queued jobs, so process-global language tables are forbidden.

Supported encoded types are:

```json
{"$type":"regex","pattern":"…","flags":34}
{"$type":"tuple","items":[…]}
{"$type":"set","items":[…]}
{"$type":"frozenset","items":[…]}
```

**Four rules that are enforced, each earned by a defect the shipped Japanese
pack actually had:**

1. **Never translate a protocol span, and note that an enum is one span.** A
   schema example writes its enum as a single quoted alternation
   (`"reinforce|weaken|revise"`). Rendering that in the target language leaves
   valid JSON and a value no consumer matches, so the operation silently does
   not happen — a contradicted belief was reinforced instead, and the entire
   project tier stopped adopting. `make structure` now compares protocol spans
   in both directions, quote characters normalized, so 「state_diff.<channel>」
   counts as the same span as `'state_diff.<channel>'`.
2. **A widened regex must keep English's capture groups.** Callers read
   `m.group(2)` positionally and `re.split` keeps only captured text. Putting
   your alternatives in fresh groups makes `group(1)` `None` on every match of
   them: an `AttributeError` mid-turn, or text silently deleted from a view.
   Put them inside the groups English defines.
3. **An anchor on one branch does not apply to the branch beside it.** If the
   English pattern ends `\s*$` because the rule means "immediately precedes",
   your alternatives need it too, or the guard degrades to "appears anywhere".
4. **Never wrap a cue in `\b`.** Word boundaries describe scripts that space
   their words. Use `character_schema.cue_boundary_pattern` for alternations
   and `name_boundary_pattern` for names — both exclude only spaced-script
   letters, so Japanese matches after a particle while `walk` still refuses to
   match inside `sidewalk`. The decision is per-token, not per-language, which
   is what keeps code-switching working in both directions.

Translate behavior, not spelling. A useful checklist is:

- word/token and sentence boundaries;
- straight, curly, and language-native quotation marks;
- first/second/third-person forms and possessives;
- speech attribution and dangling-quote repair;
- motion, manipulation, attempt, mental-state, autonomy, sleep, waking,
  restraint, destruction, and perception cues;
- titles, articles/determiners, conjunctions, and clause boundaries;
- narrator fidelity and repeated-line detection.

Keep English alternatives where code-switching, proper names, imported cards,
or quoted text make them legitimate. Do not rely on `\b` around scripts where
Unicode word boundaries do not behave like spaces. For languages that need
morphological segmentation, add a maintained tokenizer dependency or a trusted
adapter; a regex pretending to be a tokenizer is not sufficient evidence of
complete support.

## 4. Compositor card and adapter

Layer A remains language-neutral and decides which typed `Percept` records an
observer may receive. Language support must never move or weaken that boundary.

`cards/compositor.json` owns words, grammar tables, deterministic fallback
phrases, and templates. A non-English pack also names a trusted adapter with:

```python
render_view(percepts, *, mode, prev_standing, prev_described, full_render)
render_episode(percepts, *, prev_standing, prev_described)
```

The adapter receives only admitted percepts and render state—never the scene,
database, hidden identity, or objective event ledger. Built-in adapters are
explicitly allowlisted in `language_runtime`; Python placed inside a downloaded
pack directory is never imported.

Test **every percept kind the composer emits**, not a sample. Layer A has
already decided what the observer may receive, so a kind your renderer does not
handle is a fact they earned and do not get — and it fails by returning `""`,
with no error anywhere. The bundled Japanese adapter shipped dropping
`body_part`, room notes, lighting, and the whole of `body_state` (it read keys
the percept does not carry), because its only test used `kind="speech"`.
`tests/test_japanese_renderer_parity.py` is the shape to copy: assert each kind
against the English renderer, so a regression appears as a divergence rather
than as prose somebody has to read.

Two behaviours are floors rather than wording and must be reproduced exactly:
a view containing any `residue` percept is the residue **and nothing else**,
and `prev_described` suppresses a repeated appearance. Both were missing, and
the first is the non-awake information floor.

## 5. UI catalog

`ui.json` maps English source-message ids to target-language strings. Preserve
every English key exactly, including `${placeholder}` names. Translate the
value only. Set `manifest.direction` to `rtl` where appropriate.

An intentionally unchanged value must be a code fragment, protocol literal,
brand, or proper name recorded with a reason in
`translation_exceptions.json`. The project check rejects unexplained unchanged
values and stale exceptions. Structural key parity alone is not completeness.

After changing UI code, regenerate English and compare all packs:

```bash
python tools/extract_ui_catalog.py
make structure
```

The catalog scanner is deliberately broad and can include technical strings
that never render. Keeping an unchanged value for a confirmed non-UI code
fragment is preferable to translating code. Actual reader-visible strings
must be translated.

## 6. Validation and tests

Before enabling `story: true`, add tests that prove behavior rather than file
presence:

- the pack loads and can be selected for story and UI capabilities;
- its prompt tells the model to write the target language while preserving
  canonical English schemas;
- target-language mental, action, speech, sleep/wake, and authority cues fire;
- the compositor produces target-language view and episode prose;
- story and interface languages persist independently;
- missing cards, prompt ids, UI ids, or adapters fail closed;
- English output remains byte-compatible.

Run:

```bash
pytest -q tests/test_language_packs.py tests/test_prompt_card_split.py
make check
```

For a beta pack, also run real stories covering narration persons, dialogue
register, code-switching, concealed perception, rerolls, and memory recall.
Record known weak areas in the pack README or manifest version; do not hide
them behind English fallback behavior.

## Japanese worked example

`tools/build_japanese_pack.py` reproducibly builds the bundled Japanese pack
from the English reference shape, then applies Japanese compositor, UI, prompt
policy, and deterministic-language overrides. Its executable renderer is
`language_adapters/japanese.py`. `tools/openrouter_translate_japanese.py` can
build a complete model draft through the configured OpenRouter provider. It
masks protocol spans across each complete prompt leaf before chunking, rejects
missing or duplicated masks, checkpoints accepted values, writes translation
provenance, and enforces a hard budget (`--budget`, never more than $5). For
example:

```bash
python tools/openrouter_translate_japanese.py --ui --prompts \
  --model openai/gpt-4.1-mini --budget 5
```

Sending the UI/prompt corpus to a hosted provider is an external-data action;
obtain authorization before running it. Generated text remains
`translation_status: model-draft` until native review promotes it. The builder
is useful while English inventory is still changing: rerun it, inspect the
diff, then run the validation commands above. Regeneration is never
translation review—native-speaker review decides whether Japanese is natural
and whether a cue is too broad.


---

## Two things the pack layer accepts and does not implement

*(Moved out of `docs/UNBUILT.md` §1.48 on 2026-08-19 — both are facts a pack
author needs before starting, not defects in a story.)*

**RTL is accepted and unimplemented.** `manifest.direction: "rtl"` validates,
reaches `document.documentElement.dir`, and nothing else: there are no
`[dir=...]` rules in `static/`, and the stylesheets use physical `left`/`right`
properties throughout. Both shipped packs are `ltr`, so no RTL pack has ever
been rendered. A pack declaring `rtl` today gets a mirrored text direction over
an unmirrored layout.

**The UI catalog scanner is deliberately broad.** `tools/extract_ui_catalog.py`
harvests string literals, so roughly 4% of the 2006 English messages are code
fragments, selectors and markup that never render. They are carried as
`translation_exceptions.json` entries rather than filtered, which keeps the
parity check honest but hands translators strings they must not touch.

## A `$note` key on typed pack values — the convention that does not exist yet

*(Moved out of `docs/UNBUILT.md` §2.4 on 2026-08-19: it is a documentation
convention plus a `tools/project_check.py` rule, which makes it this guide's
business.)*

The language-pack extraction moved roughly forty deterministic word lists and
regexes out of `agents/common.py` and its siblings into
`language_packs/*/cards/linguistics.json`. The comments explaining WHY each
list is drawn where it is could not go with them, because the pack format has
nowhere to put prose: only `_YOU_AGREEMENT` and `_PRONOUN_GROUPS` carry any
extra key at all. `a5c9ef4` re-sited twenty of those rationales onto the
`_ling(...)` call that reads each value, which is the best Python allows — but
the data a TRANSLATOR edits still has none of them, and a translator is
precisely the reader who most needs to know that an English verb table anchors
`^...s?$` because it is matched against a single declared token while a
script with no spaces has no token to anchor.

The structural answer is a `$note` key alongside `$type`, which the decoder
would ignore for free: `_decode_linguistic` reads `pattern`/`flags` for a
regex and `items` for a tuple/frozenset/set and passes over anything else, and
`_leaf_paths` already treats a `$type` value as a leaf, so a note on one would
not become a required path a Japanese pack has to supply. What is missing is
the CONVENTION and the one place it is stated — `language_runtime/__init__.py`,
`docs/guides/LANGUAGE_PACKS.md`, and a `project_check` rule that a note is
never load-bearing. Untyped values (a plain dict of strings) would need a
decision of their own, since there `$note` would land in the dict.

Cheap, and it is what stops the next extraction stranding its rationale the
same way.
