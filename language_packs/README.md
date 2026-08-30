# Language packs

Language packs own human-language behavior around Sonder Engine's canonical
protocol. They do **not** translate schema keys, enum values, step ids, ledger
keys, body-region ids, or other persisted identifiers.

Every pack is a directory named for its normalized language id:

```text
language_packs/<id>/
  manifest.json
  prompt_policy.json
  ui.json
  cards/authoring.json
  cards/compositor.json
  cards/linguistics.json
  cards/system_prompts.json     # the index: structure + {"$text": ...} refs
  cards/system_prompts/         # the prose: one .txt per prompt leaf
```

`cards/system_prompts.json` holds the card's SHAPE. The prompt text itself
lives one leaf per file in the sibling directory beside it -- 111 files per
pack -- and the two are assembled at pack load. Edit the `.txt`; never
re-inline prose into the JSON. The format, the trailing-newline convention it
depends on, and what happens when a part file goes missing are in
[`docs/guides/LANGUAGE_PACKS.md`](../docs/guides/LANGUAGE_PACKS.md) § 2a and
`language_runtime/card_source.py`.

`manifest.json` declares the pack id, version, text direction, capabilities,
trusted renderer adapter, coverage declaration, and required cards. The loader
validates the whole pack before it can be selected for a story. It compares
every story pack's prompt ids and every UI pack's message ids against English,
so an omitted surface fails installation instead of falling back silently.

The built-in `en` pack is the compatibility reference. Its cards own all 43
system-prompt families — 36 authored bodies plus the seven Director sheets
assembled from `specialists` and `prose_author_sheet`, which are never stored
a second time (this line read "42 — 35 authored" until 2026-08-29; the
measured counts are `len(prompts.DEFAULT_PROMPTS)` and
`len(prompts.ASSEMBLED_SHEET_IDS)`) — authoring defaults, compositor vocabulary/templates, 114
deterministic linguistic structures, and the browser/API source-message
catalog. The linguistic card includes quote and sentence rules, morphology,
agreement, pronouns, action/authority cues, title handling, narration-person
detection, Director omission aliases, and the `mind.*`/`persist.*`
recognizers that decide belief-confidence calibration, claim similarity,
memory salience, mood valence and durable-quote detection. Lookups happen at
use time through a context variable, so two concurrent stories can safely
run different language packs. `llm/prompts.py` now contains assembly and gating code only. The project
check regenerates and compares the English UI source inventory, preventing a
new reader-visible string from bypassing the catalog.

## Deterministic renderer boundary

`agents.composer` Layer A remains language-neutral and admits typed `Percept`
records through the ordinary information firewall. Layer B dispatches that
already-admitted list to the story language renderer. A renderer receives no
scene, database, hidden identity, or objective state, so changing language
cannot widen what an observer knows.

Renderer adapters are registered explicitly by trusted engine code and must
provide both `render_view` and `render_episode`. A non-English story pack
cannot be selected until its named adapter is registered. A pack is never
allowed to execute Python merely because a file exists in its directory. This
keeps downloaded data-only packs inert and makes executable language support
an auditable extension rather than an import side effect.

## Prompt contract

`prompt_policy.json` contains a mandatory common suffix and optional
role-specific suffixes. They are appended after the active prompt preset and
content-policy overlay. The provider boundary also applies the common suffix
to repair and one-off utility calls, so no system prompt can bypass it.

Every policy must explicitly separate output language from protocol language.
Every system prompt—including repairs and ad-hoc utility calls—is told that
human-readable values use the selected language while JSON keys, schema
fields, enum literals, ids, body-region ids, operation names, and step names
stay canonical English. Those are code objects shared by every pack and are
never translated.

## UI catalog

The UI uses English source text as a gettext-style message id. `t()` handles
static messages and template messages, while a DOM observer covers both the
initial HTML and dynamically inserted controls. Run
`python tools/extract_ui_catalog.py` after adding or changing UI/error copy;
`make structure` fails when the English catalog is stale. A pack declaring
`ui: true` must supply every English source-message id and its own direction.

## Adding a complete language

The maintained step-by-step authoring and validation guide is
[`docs/guides/LANGUAGE_PACKS.md`](../docs/guides/LANGUAGE_PACKS.md). The
Japanese beta pack and `tools/build_japanese_pack.py` are the worked example.

A genuinely complete pack needs more than translated UI strings:

1. Unicode-aware tokenization, sentence boundaries, and quote handling.
2. Recognition cards for spatial, action, speech, attire, affect, weather,
   perception, memory, belief, lore, and authority checks.
3. Layer-B compositor templates and perspective/grammar transforms.
4. Prompt policy for every model-authored surface.
5. UI catalog, plural behavior, text direction, and font coverage.
6. End-to-end tests proving authority and information-boundary behavior in
   that language, not only fluent-looking output.

The loader compares every story card's complete key shape with English, not
only its top-level files. Missing deterministic coverage prevents selection;
silently falling back to English recognition under non-English prose would
disable guards in ways that fail open.

`translation_status` reports language quality separately from structural
capability. `native` means human-authored/reviewed; `model-draft` is complete
enough to exercise and has passed structural/protocol audits, but still
requires language review. A non-English UI pack
must record every deliberately unchanged code/proper-name value in
`translation_exceptions.json`; unexplained English fallback fails the project
check.
