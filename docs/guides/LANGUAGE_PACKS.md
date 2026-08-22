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
    system_prompts.json
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

`cards/system_prompts.json` must contain every id in the English card. A pack
claiming linguistic completeness must translate every authored instruction;
bilingual text is acceptable when it improves model reliability, but a
byte-identical English body is not a translation. The output/schema contract
must always be written and tested for the target language. Never translate
literal schema examples inside a prompt.

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

The replacement runtime uses an explicit localizer rather than scanning the
live DOM. It compiles catalog templates once, validates placeholder parity,
sets the manifest language and direction, and translates only nodes handed to
it by a component or entry owner. `translate="no"`, form controls,
contenteditable regions, and story/user/model projections are hard boundaries;
no mutation observer may discover and reinterpret later content.

`tools/extract_ui_catalog.py` walks replacement modules recursively but reads
only literals inside `UI_CATALOG_START` / `UI_CATALOG_END` blocks. Development
fixtures such as the component laboratory and runtime harness are excluded by
name. Adding visible replacement copy therefore requires both an owning block
and regenerated `language_packs/en/ui.json`; technical strings elsewhere in a
module are not silently promoted into translator work.

The production application shell is the complete product consumer of this
boundary. Static shell labels are catalogued from `static/ui-next.html` and
dynamic navigation, inspector, Go To, fallback, and extension-host wording is
catalogued from the owning modules. English extraction is exact; Japanese has
matching keys. The G2 matrix exercises injected long Japanese copy on a compact
viewport and proves that navigation, focus, Go To, and 44 px targets remain
available without horizontal overflow. Full translation quality and every
later workflow remain release-gate work; key parity is still not native review.

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
pytest -q tests/test_language_packs.py
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
