#!/usr/bin/env python3
"""Lightweight repository-shape checks that require no external linter."""

from __future__ import annotations

import ast
import json
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping
from pathlib import Path
from string import Formatter

from generate_code_map import OUTPUT, ROOT, generate
from extract_ui_catalog import UI_PATH, catalog as english_ui_catalog

FORBIDDEN_PATCH_MARKERS = (
    "Replace the entire",
    "Insert this BEFORE",
    "Add after build_plan",
    "---- PATCH ",
)

CANONICAL_LANGUAGE_TOKEN = re.compile(
    r"`[^`]+`|\$\{[^}]+\}|"
    r"\{[A-Za-z_][A-Za-z0-9_.]*(?:![rsa])?(?::[^{}]+)?\}|"
    r"https?://[^\s)\]}>;,）】〉》」、。；，]+|"
    r"[\"'](?P<jsonkey>[a-z][a-z0-9_.:-]*)[\"'](?=\s*:)|"
    # `|` and `<>` belong in this class. A schema example's enum is written as
    # one quoted alternation ("reinforce|weaken|revise") and its id templates
    # as "current:<perceiver>:0" -- excluding those characters meant the whole
    # span matched nothing, so a translator could render the enum in the target
    # language and no check objected. Underscore-bearing members like
    # `stated_fact` were caught by the identifier rule below and survived,
    # which is precisely the split the shipped Japanese pack shows.
    r"(?P<quote>[\"'])(?P<quotedtoken>[A-Za-z][A-Za-z0-9_.:|<>-]*)(?P=quote)|"
    # A language quotes with its own marks. The protocol span is what must
    # survive, not the punctuation a translator wrapped it in.
    r"「(?P<cornertoken>[A-Za-z][A-Za-z0-9_.:|<>-]*)」|"
    r"『(?P<dcornertoken>[A-Za-z][A-Za-z0-9_.:|<>-]*)』|"
    r"(?<![A-Za-z0-9_])[a-z][a-z0-9]*_[a-z0-9_]+(?:\.[a-z0-9_]+)*|"
    # `(?<!\.)`: the character class contains `.`, so a dotted name at the
    # END OF A SENTENCE swallowed the full stop -- "…with a manifest.json."
    # yielded the token `manifest.json.`, which no translation can carry
    # through because the Japanese sentence ends in 。 instead. The token is
    # the name, never the punctuation after it.
    r"(?<![A-Za-z0-9_])[a-z]+\.[a-z][a-z0-9_.{}\[\]]+(?<!\.)|"
    r"</?[A-Za-z][^>]*>"
)


_TOKEN_CONTENT_GROUPS = ("jsonkey", "quotedtoken", "cornertoken", "dcornertoken")


def canonical_language_tokens(text: str) -> set:
    """The protocol spans a translation must carry through unchanged.

    Returns a SET, not a multiset. A translation legitimately repeats or merges
    sentences -- Japanese splits one English clause about `"keep"` into two --
    and counting occurrences would forbid ordinary rephrasing while catching
    nothing extra. What must never happen is a span DISAPPEARING, which set
    difference reports exactly.
    """
    found = set()
    for match in CANONICAL_LANGUAGE_TOKEN.finditer(text):
        token = next(
            (match.group(name) for name in _TOKEN_CONTENT_GROUPS
             if match.group(name) is not None),
            match.group(0))
        if token.lower() not in {"e.g", "e.g.", "i.e", "i.e."}:
            found.add(token)
    return found


def check_duplicate_python_symbols(errors: list[str]) -> None:
    """A redefined top-level name silently replaces the first one.

    `tests/` is included because that is where it does the most damage and
    the least noise: a duplicated test name does not error, it DELETES the
    earlier test. Four were being dropped from
    `tests/test_player_act_authority.py` -- three guards each defining
    `test_empty_and_missing_inputs_are_noops` -- and one of the lost four was
    the false-positive guard on player-speech authority, whose whole job is to
    stop the check crying wolf on ordinary narration.
    """
    for path in sorted(engine_python_paths()
                       + list((ROOT / "tests").glob("test_*.py"))):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        symbols: dict[str, list[int]] = defaultdict(list)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                symbols[node.name].append(node.lineno)
        for name, lines in symbols.items():
            if len(lines) > 1:
                errors.append(
                    f"{path.relative_to(ROOT)} defines top-level symbol {name!r} "
                    f"more than once at lines {lines}"
                )


def check_patch_debris(errors: list[str]) -> None:
    paths = (engine_python_paths()
             + list((ROOT / "static" / "js").glob("*.js")))
    for path in sorted(paths):
        text = path.read_text(encoding="utf-8")
        for marker in FORBIDDEN_PATCH_MARKERS:
            if marker in text:
                errors.append(f"{path.relative_to(ROOT)} still contains patch marker {marker!r}")


def check_empty_tests(errors: list[str]) -> None:
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        if not path.read_text(encoding="utf-8").strip():
            errors.append(f"{path.relative_to(ROOT)} is empty")


#: An `_ops` name a prompt may mention without owning it. Kept explicit and
#: tiny: an entry here is a promise that the stage is DESCRIBING another
#: stage's field rather than asking for one, and every addition should be
#: justified in the same breath as it is made.
OPS_MENTIONED_BUT_NOT_OWNED: dict[str, set[str]] = {
    # The spatial specialist's stations/poses chunks name contact_ops
    # precisely to DISCLAIM it ("Stations are not contact: contact_ops says
    # what a body is AGAINST...") -- contact is the contact specialist's
    # channel, and the shared segments reference it to draw that boundary.
    "director_spatial": {"contact_ops"},
}

#: Prompt ids validated against another stage's model: the orchestrated
#: prose author's lean sheet is the SAME step (same schema, same step key)
#: as the monolithic resolve, under a different prompt id.
PROMPT_MODEL_ALIASES = {
    "director_resolve_lean": "director_resolve",
}

OPS_NAME = re.compile(r"\b([a-z][a-z0-9]*(?:_[a-z0-9]+)*_ops)\b")


def _models_within(annotation) -> list:
    """Every Pydantic model reachable through a type annotation.

    `list[CrowdOp]`, `Optional[StateDiff]` and bare `StateDiff` all have to
    yield their model, because the field a prompt names is often two levels
    down -- `state_diff.crowd_ops` lives on `StateDiff`, not on the stage's
    own output model.
    """
    from pydantic import BaseModel

    found, stack = [], [annotation]
    while stack:
        candidate = stack.pop()
        if isinstance(candidate, type) and issubclass(candidate, BaseModel):
            found.append(candidate)
        stack.extend(getattr(candidate, "__args__", ()) or ())
    return found


def _field_names(model, seen: set | None = None) -> set:
    seen = set() if seen is None else seen
    if model in seen:
        return set()
    seen.add(model)
    names = set()
    fields = (getattr(model, "model_fields", None)
              or getattr(model, "__fields__", {}))
    for name, field in fields.items():
        names.add(name)
        # BOTH, not the first truthy one. A forward-referenced field keeps an
        # unresolved `ForwardRef` in `.annotation` long after
        # `update_forward_refs()` has put the real class in `.outer_type_` --
        # so preferring `.annotation` made every forward-referenced nested
        # model invisible here, and this check silently stopped covering it.
        # Found by `DirectorInterpret.state_assertions: Optional["StateDiff"]`,
        # which is exactly the shape the check exists for.
        for source in (getattr(field, "annotation", None),
                       getattr(field, "outer_type_", None)):
            for nested in _models_within(source):
                names |= _field_names(nested, seen)
    return names


def check_prompt_schema_ops(errors: list[str]) -> None:
    """Every `_ops` field a prompt asks for must exist on that stage's model.

    A prompt and a schema are two spellings of one contract, and this project's
    own rule is that where two spellings of a thing can exist, they should be
    folded rather than trusted to stay level. Nothing folded them, and the same
    defect landed three times in two days:

      * `entry_ops` asked for by the lore prompt, `entries` opened by the
        reader. Shipped, reported by a user against alpha 7.2, fixed in 7.2.1.
      * `offscreen_plan_ops` printed OUTSIDE `state_diff` by a stray brace in
        the resolve prompt's shape line, while `offscreen.apply_plan_ops`
        opens `state_diff.offscreen_plan_ops`.
      * `project_ops` asked for by name in three places in the character
        prompt, with no such field on `CharacterOutput`. Pydantic dropped every
        op, silently, and "has ever held a project: 0 of 14 banks" was the
        cost -- an entire tier of psychology that could be asked for, answered,
        and never heard.

    Each cost a measurement or a user to find. This finds them for nothing, and
    it is deliberately narrow: `_ops` fields are where the pattern actually
    bites, because they are the fields a prompt has to name in prose AND print
    in a shape, which is two chances to drift.

    Verified against the real defect rather than assumed -- at the commit
    before the fix, this reports `character MISSING ['project_ops']`.
    """
    sys.path.insert(0, str(ROOT))
    try:
        from llm import prompts
        from llm import schemas
    except Exception as exc:  # pragma: no cover - import failure is its own error
        errors.append(f"could not check prompt/schema ops drift: {exc}")
        return

    checks = [(stage, stage) for stage in schemas.SCHEMA_MAP]
    checks += [(pid, stage) for pid, stage in PROMPT_MODEL_ALIASES.items()]
    for pid, stage in checks:
        model = schemas.SCHEMA_MAP.get(stage)
        text = prompts.DEFAULT_PROMPTS.get(pid)
        if model is None or not isinstance(text, str):
            continue
        allowed = OPS_MENTIONED_BUT_NOT_OWNED.get(pid, set())
        missing = sorted(set(OPS_NAME.findall(text))
                         - _field_names(model) - allowed)
        for name in missing:
            errors.append(
                f"the {pid!r} prompt asks for {name!r} and "
                f"{model.__name__} has no such field, so validation will drop "
                "every one the model sends"
            )


def check_specialist_prompt_chunks(errors: list[str]) -> None:
    """The orchestrated Director's scoping is only real if the prompts are
    CHUNKED to match it (design note 19, hierarchical gating): a specialist's
    sheet is core + one chunk per channel in the granted scope, and scope
    selects chunks with no other logic. An unchunked prompt silently defeats
    the mechanism -- a specialist whose instructions all live in its core
    loads everything on every beat while appearing scoped. Three files spell
    the ownership (agents/director.SPECIALISTS, prompts.
    SPECIALIST_PROMPT_SPECS, schemas.SPECIALIST_CHANNELS); this holds them
    level and enforces the chunk structure:

      * every channel a specialist owns has a chunk, and no chunk exists for
        a channel it does not own (an orphan means a channel changed hands
        and its instructions did not);
      * the three registries agree on channels per specialist;
      * a specialist's CORE never names its own channels (word-boundary
        match): channel-specific instruction lives in chunks ONLY. This is
        the honest approximation of "no channel-specific instruction in the
        core" -- it cannot see a paraphrase, and that limitation is
        accepted and recorded in design note 19 rather than papered over
        with a semantic check that would pass for the wrong reason.
    """
    sys.path.insert(0, str(ROOT))
    try:
        from llm import prompts
        from llm import schemas
        from agents import director
    except Exception as exc:  # pragma: no cover - import failure is its own error
        errors.append(f"could not check specialist prompt chunks: {exc}")
        return

    prompt_specs = getattr(prompts, "SPECIALIST_PROMPT_SPECS", {})
    runtime_specs = getattr(director, "SPECIALISTS", {})
    schema_channels = getattr(schemas, "SPECIALIST_CHANNELS", {})

    if set(prompt_specs) != set(runtime_specs):
        errors.append(
            "specialist registries disagree: prompts.SPECIALIST_PROMPT_SPECS "
            f"has {sorted(prompt_specs)} but agents/director.SPECIALISTS has "
            f"{sorted(runtime_specs)}")
        return

    for name, runtime in sorted(runtime_specs.items()):
        owned = set(runtime.get("channels") or ())
        prompt_spec = prompt_specs.get(name) or {}
        chunks = set((prompt_spec.get("chunks") or {}).keys())
        order = list(prompt_spec.get("order") or ())
        step_key = runtime.get("step_key")
        schema_owned = set(schema_channels.get(step_key) or ())

        for missing in sorted(owned - chunks):
            errors.append(
                f"specialist {name!r} owns channel {missing!r} but its "
                "prompt has no chunk for it -- the scoped sheet can never "
                "teach that channel and every grant of it loads nothing")
        for orphan in sorted(chunks - owned):
            errors.append(
                f"specialist {name!r} prompt carries a chunk for "
                f"{orphan!r}, a channel it does not own -- the channel "
                "changed hands and its instructions did not")
        if owned != schema_owned:
            errors.append(
                f"specialist {name!r} channels disagree with schemas."
                f"SPECIALIST_CHANNELS[{step_key!r}]: {sorted(owned)} vs "
                f"{sorted(schema_owned)}")
        if set(order) != chunks:
            errors.append(
                f"specialist {name!r} chunk order {order} does not cover "
                f"exactly its chunks {sorted(chunks)} -- an unordered chunk "
                "never loads")

        core = str(prompt_spec.get("core") or "")
        for channel in sorted(owned):
            if re.search(r"(?<![\w.])%s\b" % re.escape(channel), core):
                errors.append(
                    f"specialist {name!r} core names its own channel "
                    f"{channel!r} -- channel-specific instruction belongs "
                    "in that channel's chunk, or scoping silently stops "
                    "meaning anything")

        # The same `_ops` drift check the stage prompts get, against the
        # FULLY assembled sheet: every _ops name the sheet can ask for must
        # exist on this specialist's model, or validation silently drops
        # every one the model sends (the project_ops lesson, one level in).
        model = schemas.SCHEMA_MAP.get(step_key)
        if model is not None:
            sheet = core + "".join(
                str(chunk) for chunk in
                (prompt_spec.get("chunks") or {}).values())
            allowed = OPS_MENTIONED_BUT_NOT_OWNED.get(step_key, set())
            for op_name in sorted(set(OPS_NAME.findall(sheet))
                                  - _field_names(model) - allowed):
                errors.append(
                    f"specialist {name!r} sheet asks for {op_name!r} and "
                    f"{model.__name__} has no such field, so validation "
                    "will drop every one the model sends")


#: Blocks of the orchestrated prose author's sheet that must NEVER be
#: gateable: every-beat authority/firewall contract material. Each marker
#: must appear in the CORE (the segments that load on every scope,
#: including the empty one) -- a marker migrating into a gated chunk is
#: exactly the quality regression the scoping was forbidden to introduce.
PROSE_AUTHOR_NEVER_GATED = (
    "KNOWLEDGE FIREWALL",
    "CHANGES MANIFEST",
    "PLAYER-ASSERTED FACTS",
    "DIALOGUE LOG — MANDATORY",
    "PLAYER AUTHORITY CONTRACT",
    "DELEGATED CHANNELS",
    "WORLD PRESSURE — OPENING",   # opening a process is undecidable
    "Output STRICT JSON",
)


def check_prose_author_chunks(errors: list[str]) -> None:
    """The prose author's sheet scoping, held level the same way the
    specialists' is (design note 19): prompts.PROSE_AUTHOR_SHEET names the
    chunks, agents/director._PROSE_DUTY_GATES grants them, and
    agents/director._PROSE_DUTY_SHIPPED audits the gated-out ones. A chunk
    with no gate never loads on the orchestrated path (silent drop); a gate
    with no chunk grants nothing; an audit for a name that is not a chunk
    audits nothing. And the never-gated contract blocks must live in the
    CORE -- the firewall is an invariant, not an optimization target."""
    sys.path.insert(0, str(ROOT))
    try:
        from llm import prompts
        from agents import director
    except Exception as exc:  # pragma: no cover - import failure is its own error
        errors.append(f"could not check prose author chunks: {exc}")
        return

    sheet = getattr(prompts, "PROSE_AUTHOR_SHEET", ())
    chunk_names = set(getattr(prompts, "PROSE_DUTY_CHUNKS", ()))
    gates = set(getattr(director, "_PROSE_DUTY_GATES", {}))
    audits = set(getattr(director, "_PROSE_DUTY_SHIPPED", {}))

    if chunk_names != gates:
        errors.append(
            "prose-author registries disagree: prompts.PROSE_DUTY_CHUNKS "
            f"has {sorted(chunk_names)} but agents/director."
            f"_PROSE_DUTY_GATES has {sorted(gates)} -- an ungated chunk "
            "never loads on the orchestrated path, and a chunkless gate "
            "grants nothing")
    for orphan in sorted(audits - chunk_names):
        errors.append(
            f"agents/director._PROSE_DUTY_SHIPPED audits {orphan!r}, which "
            "is not a prose-duty chunk -- the audit can never fire")

    core = "".join(text for name, text in sheet if name is None)
    gated = "".join(text for name, text in sheet if name)
    for marker in PROSE_AUTHOR_NEVER_GATED:
        if marker not in core:
            errors.append(
                f"never-gated prose-author block {marker!r} is missing "
                "from the sheet's core -- it must load on every beat")
    for marker in ("KNOWLEDGE FIREWALL", "CHANGES MANIFEST",
                   "DIALOGUE LOG — MANDATORY", "PLAYER AUTHORITY CONTRACT"):
        if marker in gated:
            errors.append(
                f"never-gated prose-author block {marker!r} appears inside "
                "a gated chunk -- a beat could load a second, gateable "
                "spelling of an every-beat contract")

    full = "".join(text for _name, text in sheet)
    if prompts.DEFAULT_PROMPTS.get("director_resolve_lean") != full:
        errors.append(
            "DEFAULT_PROMPTS['director_resolve_lean'] is not the full-scope "
            "assembly of PROSE_AUTHOR_SHEET -- the _ops drift check and "
            "preset editing would see a different sheet than the "
            "orchestrated path can load")


def check_generated_map(errors: list[str]) -> None:
    expected = generate()
    actual = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
    if actual != expected:
        errors.append("docs/CODE_MAP.md is stale; run python tools/generate_code_map.py")


def check_language_pack_surfaces(errors: list[str]) -> None:
    """English is the reference inventory every other complete pack matches."""
    try:
        from language_runtime import installed_language_packs
        from llm import prompts
        packs = installed_language_packs(refresh=True)
    except Exception as exc:
        errors.append(f"could not load language packs: {exc}")
        return
    english = packs.get("en")
    if english is None:
        errors.append("built-in English language pack is missing")
        return
    prompt_ids = set(english.card("system_prompts")["prompts"])
    if prompt_ids != set(prompts.DEFAULT_PROMPTS):
        errors.append("English system-prompt card and runtime registry disagree")
    for pid, text in prompts.DEFAULT_PROMPTS.items():
        if "LANGUAGE AND SCHEMA CONTRACT" not in text:
            errors.append(f"system prompt {pid!r} lacks the language/schema contract")
    expected_ui = english_ui_catalog()
    try:
        actual_ui = json.loads(UI_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"could not read English UI catalog: {exc}")
    else:
        if actual_ui != expected_ui:
            errors.append(
                "English UI catalog is stale; run python tools/extract_ui_catalog.py")

    # Structural parity is not translation completeness. A non-English pack
    # may retain source values only when it records each one as a code/proper-
    # name exception. Long authored prompt bodies must not remain byte-for-byte
    # English even though their prompt ids and schema paths match.
    english_prompts = english.card("system_prompts")

    def authored_strings(value, path=()):
        # Mapping, not dict: LanguagePack.card() returns the frozen
        # mappingproxy built by language_runtime._freeze, which is NOT a dict
        # subclass. Type-testing for dict walked zero leaves and silently
        # disarmed every prompt check below.
        if isinstance(value, Mapping):
            for key, child in value.items():
                yield from authored_strings(child, path + (str(key),))
        elif isinstance(value, (list, tuple)):
            for index, child in enumerate(value):
                yield from authored_strings(child, path + (str(index),))
        elif isinstance(value, str):
            yield path, value

    english_authored = dict(authored_strings(english_prompts))
    for language_id, pack in packs.items():
        if language_id == "en":
            continue
        pack_dir = ROOT / "language_packs" / language_id
        exceptions_path = pack_dir / "translation_exceptions.json"
        try:
            exceptions = json.loads(exceptions_path.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(
                f"language pack {language_id!r} has no readable translation "
                f"exception ledger: {exc}")
            exceptions = {}
        unchanged = {
            key for key, source in english.ui_catalog.items()
            if pack.ui_catalog.get(key) == source
        }
        if unchanged != set(exceptions):
            errors.append(
                f"language pack {language_id!r} has "
                f"{len(unchanged.difference(exceptions))} unexplained unchanged "
                f"UI values and {len(set(exceptions).difference(unchanged))} stale "
                "translation exceptions")
        if any(not str(reason or "").strip() for reason in exceptions.values()):
            errors.append(
                f"language pack {language_id!r} has an empty translation-exception reason")
        ui_protocol_drift = [
            key for key, source in english.ui_catalog.items()
            if canonical_language_tokens(source).difference(
                canonical_language_tokens(pack.ui_catalog.get(key, "")))
        ]
        if ui_protocol_drift:
            errors.append(
                f"language pack {language_id!r} changes canonical tokens in UI "
                f"values: {', '.join(repr(key) for key in ui_protocol_drift[:8])}")
        localized_authored = dict(authored_strings(pack.card("system_prompts")))
        unchanged_authored = []
        prompt_protocol_drift = []
        for path, source in english_authored.items():
            if any(segment in {"nsfw_prompt_ids", "order"} for segment in path):
                continue
            localized = localized_authored.get(path, "")
            if len(source) >= 160 and localized == source:
                unchanged_authored.append(".".join(path))
            lost = canonical_language_tokens(source).difference(
                canonical_language_tokens(localized))
            if lost:
                prompt_protocol_drift.append(
                    f"{'.'.join(path)} ({', '.join(sorted(lost)[:3])})")
        if unchanged_authored:
            errors.append(
                f"language pack {language_id!r} retains English authored prompt "
                f"bodies: {', '.join(unchanged_authored[:8])}")
        if prompt_protocol_drift:
            errors.append(
                f"language pack {language_id!r} changes canonical tokens in "
                f"system prompts: {', '.join(prompt_protocol_drift[:8])}")

    # Three surfaces that nothing validated. Each fails at USE time, deep
    # inside a turn, with an exception that does not name the language pack.
    for language_id, pack in packs.items():
        # Emptiness measured AGAINST ENGLISH, because the sheets carry
        # structural whitespace entries -- prose_author_sheet[16] is (None,
        # "\n"), a deliberate separator. What must never happen is English
        # holding real instructions where a pack holds nothing.
        localized = dict(authored_strings(pack.card("system_prompts")))
        blank = [".".join(path) for path, source in english_authored.items()
                 if source.strip() and not localized.get(path, "").strip()]
        if blank:
            errors.append(
                f"language pack {language_id!r} has empty authored prompt "
                f"text: {', '.join(sorted(blank)[:8])}")
        # A pattern is compiled lazily by _linguistic_cached, so an invalid one
        # loads clean and raises a bare re.error mid-turn.
        for module, transforms in pack.card("linguistics").items():
            for name, value in transforms.items():
                if not (isinstance(value, Mapping) and value.get("$type") == "regex"):
                    continue
                try:
                    compiled = re.compile(
                        str(value.get("pattern")), int(value.get("flags") or 0))
                except re.error as exc:
                    errors.append(
                        f"language pack {language_id!r} has an uncompilable "
                        f"regex {module}.{name}: {exc}")
                    continue
                # Capture groups are read POSITIONALLY (m.group(2)) and
                # re.split keeps only captured text, so a pack that adds its
                # own alternatives in fresh groups makes group(1) None on
                # every match of those alternatives -- an AttributeError deep
                # in a turn, or silently dropped text. A pack may widen a
                # pattern; it may not change its shape.
                reference = (english.card("linguistics")
                             .get(module, {}).get(name))
                if not (isinstance(reference, Mapping)
                        and reference.get("$type") == "regex"):
                    continue
                try:
                    expected = re.compile(
                        str(reference["pattern"]),
                        int(reference.get("flags") or 0)).groups
                except re.error:
                    continue
                if compiled.groups != expected:
                    errors.append(
                        f"language pack {language_id!r} regex {module}.{name} "
                        f"has {compiled.groups} capture groups; English "
                        f"defines {expected} and callers read them by position")
        # compositor_text() formats these at render time; an unknown field or
        # an unbalanced brace surfaces as a broken view, never as a bad pack.
        templates = pack.card("compositor").get("templates") or {}
        english_templates = english.card("compositor").get("templates") or {}
        for key, template in templates.items():
            try:
                fields = {name for _t, name, _s, _c
                          in Formatter().parse(str(template)) if name}
            except ValueError as exc:
                errors.append(
                    f"language pack {language_id!r} compositor template "
                    f"{key!r} is unparseable: {exc}")
                continue
            reference = english_templates.get(key)
            if reference is None:
                continue
            allowed = {name for _t, name, _s, _c
                       in Formatter().parse(str(reference)) if name}
            unknown = fields.difference(allowed)
            if unknown:
                errors.append(
                    f"language pack {language_id!r} compositor template "
                    f"{key!r} names fields English does not supply: "
                    f"{', '.join(sorted(unknown))}")
        # A mask token that survived translation is invisible to every rule
        # above, because it looks like ordinary text.
        leaked = sorted({
            ".".join(path) for card in ("system_prompts", "compositor",
                                        "authoring")
            for path, value in authored_strings(pack.card(card))
            if "⟦" in value or "⟧" in value})
        leaked += sorted(key for key, value in pack.ui_catalog.items()
                         if "⟦" in value or "⟧" in value)
        if leaked:
            errors.append(
                f"language pack {language_id!r} still contains translation "
                f"mask markers: {', '.join(leaked[:8])}")


def check_no_dead_prompts(errors: list[str]) -> None:
    """Every prompt in the pack must be fetchable by something.

    A prompt nobody fetches is not free. It is listed in the host's prompt
    editor as though editing it would change behaviour, it is shipped in every
    bootstrap response, and it is paid for again in every language a pack is
    translated into. The `perception` prompt was 28,467 characters of exactly
    that: perception composes each view deterministically from the typed IR
    and has no entry in `providers.ROLES`, so nothing had read it for
    releases.
    """
    import re as _re
    import sys as _sys

    # `tools/` is on sys.path, the repo root is not.
    if str(ROOT) not in _sys.path:
        _sys.path.insert(0, str(ROOT))
    from language_runtime import installed_language_packs
    from llm import prompts as _prompts

    ids = set(installed_language_packs()["en"].card("system_prompts")["prompts"])
    used = set(_prompts.SPECIALISTS_BY_NAME.values())
    used.add("director_resolve_lean")  # assembled, not fetched by id
    for path in engine_python_paths():
        used.update(_re.findall(
            r'get_prompt(?:_body)?\(\s*["\']([a-z_0-9]+)["\']',
            path.read_text(encoding="utf-8")))
    dead = sorted(ids - used)
    if dead:
        errors.append(
            "language pack 'en' carries prompts nothing fetches: "
            + ", ".join(dead))


#: The subsystem packages the engine's own modules live in
#: (docs/design/DESIGN_MODULE_LAYOUT.md). Enumerated rather than rglob'd:
#: ROOT also contains .claude/worktrees/ and .venv-browser/.
SUBSYSTEM_PACKAGES = ("core", "llm", "world", "mind", "story", "dressing", "persist", "web")


def engine_python_paths():
    """Every .py file the engine itself owns, packages plus agents."""
    out = []
    for pkg in SUBSYSTEM_PACKAGES:
        out.extend((ROOT / pkg).glob("*.py"))
    out.extend((ROOT / "agents").rglob("*.py"))
    return sorted(out)


EXTENSION_DEEP_IMPORTS = SUBSYSTEM_PACKAGES + ("agents",)
#: WHOLE PACKAGES, not a list of module names. Until the 2026-08-18 layout
#: change this was ten hand-kept names, and the matcher below compares the
#: FIRST dotted component -- so `import commit_memory` walked straight past it
#: the moment commit.py was split, and thirteen siblings had to be added by
#: hand to close that. A list of internals cannot be finished: the set of
#: modules an engine can grow has no end, which is the same argument that
#: retired the animate/inert kind lists in alpha 9.5.
#:
#: Deliberately BROADER than what it replaced. Every module inside these
#: packages is engine internals, and the rule extensions are being held to is
#: "use the api facade" -- so the package IS the boundary, and an extension
#: that genuinely needs the coupling still declares "system": true.


def _extension_dirs() -> list[Path]:
    root = ROOT / "extensions"
    if not root.is_dir():
        return []
    return sorted(child for child in root.iterdir()
                  if child.is_dir() and not child.name.startswith("."))


#: Names Python binds on a module that `symtable` does not list as symbols.
_IMPLICIT_MODULE_NAMES = frozenset({
    "__file__", "__name__", "__doc__", "__package__", "__spec__",
    "__loader__", "__builtins__", "__debug__",
})


def check_undefined_names(errors: list[str]) -> None:
    """A name used inside a function that nothing anywhere binds.

    The class: call a helper you forgot to import. `python -m compileall`
    passes -- it is valid syntax -- and the whole suite passes too whenever the
    line sits on a branch no test drives. It fails in PRODUCTION, as a
    NameError, mid-turn.

    That is not hypothetical. `director_interpret`'s reactor fallback called
    `can_perceive_onset` with no import for it, on a branch that only runs when
    the Director names no reactors; 6,826 tests were green and the first live
    beat died. Sweeping the tree for the same shape immediately turned up a
    SECOND one that had been sitting in `narrator_extra` -- `player_name`, a
    free variable bound in `narrator` and never in the function that used it,
    so every extra-player render would have raised the moment a chat had a
    second human in it.

    Uses `symtable`, which is CPython's own scope analyser, rather than a
    hand-rolled AST walk: comprehension scopes, walrus targets, `global`/
    `nonlocal`, class bodies and nested closures are exactly where a
    hand-rolled one produces false positives, and a false positive here blocks
    `make check` for everyone.

    Conservative on purpose. Only a symbol the analyser calls global, that is
    read, and that nothing in the module ever assigns, is reported -- and a
    module containing a star-import is skipped entirely, because then the
    module's own namespace is not knowable from the source.
    """
    import builtins
    import symtable

    # Enumerated rather than rglob'd. `ROOT` contains `.claude/worktrees/`,
    # which holds several complete checkouts of this repository, and a
    # whole-tree walk therefore scans the engine seven times over and takes
    # minutes. These are the directories the engine actually ships from.
    paths = (
        engine_python_paths()
        + list((ROOT / "tools").glob("*.py"))
        + list((ROOT / "tests").glob("*.py"))
        + list((ROOT / "extension_runtime").glob("*.py"))
        + list((ROOT / "language_runtime").glob("*.py"))
        + list((ROOT / "language_adapters").glob("*.py"))
        + list((ROOT / "extensions").glob("*/*.py"))
    )
    scanned = 0
    for path in sorted(paths):
        if "__pycache__" in path.parts:
            continue
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (OSError, SyntaxError):
            continue          # compileall owns syntax; this owns names
        if any(isinstance(node, ast.ImportFrom)
               and any(alias.name == "*" for alias in node.names)
               for node in ast.walk(tree)):
            continue
        try:
            top = symtable.symtable(source, str(path), "exec")
        except (SyntaxError, ValueError):
            continue
        scanned += 1
        known = ({symbol.get_name() for symbol in top.get_symbols()}
                 | set(dir(builtins)) | _IMPLICIT_MODULE_NAMES)
        relative = path.relative_to(ROOT).as_posix()

        def visit(scope):
            for symbol in scope.get_symbols():
                name = symbol.get_name()
                if (symbol.is_global() and symbol.is_referenced()
                        and not symbol.is_assigned() and name not in known):
                    errors.append(
                        f"{relative}: {scope.get_name()}() uses {name!r}, "
                        "which nothing in the module defines or imports")
            for child in scope.get_children():
                visit(child)

        visit(top)


def check_extension_manifests(errors: list[str]) -> None:
    """Every bundled extension loads, and declares what it actually registers.

    Two distinct failures, and only the first is loud at runtime. A manifest
    that will not parse is already an error the host sees in the Extensions
    menu -- catching it here just means the repo's own reference extension
    cannot ship broken. The second is silent: a capability DECLARED and never
    registered is a promise to the host that nothing keeps, which is the
    `check_no_dead_prompts` class of defect exactly. It matters more here than
    there, because the declaration is what the consent dialog shows -- a host
    reading "pipeline stage" and getting none has been told something false.
    """
    # `make structure` runs this from tools/, so the repo root is not on the
    # path the way it is for every test.
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    import extension_runtime

    for directory in _extension_dirs():
        manifest_path = directory / "manifest.json"
        if not manifest_path.is_file():
            errors.append(f"extensions/{directory.name}: no manifest.json")
            continue
        try:
            ext = extension_runtime._load_manifest(directory)
        except Exception as exc:
            errors.append(f"extensions/{directory.name}: {exc}")
            continue

        caps = ext.capabilities
        for field, relative in (("python", ext.python_entry),
                                ("ui.js", ext.ui_entry),
                                ("ui.css", ext.css_entry)):
            if relative and not (directory / relative).is_file():
                errors.append(
                    f"extensions/{ext.id}: {field} names {relative!r}, "
                    f"which does not exist")

        declared = {str(stage.get("key") or "")
                    for stage in (caps.get("stages") or [])
                    if isinstance(stage, dict)}
        if not declared:
            continue
        # A dry-run registration: load the entry against a throwaway API and
        # see what it ACTUALLY registers. Cheaper and far more honest than
        # parsing the source for `add_stage` calls.
        try:
            registered = _dry_run_registrations(extension_runtime, ext)
        except Exception as exc:
            errors.append(f"extensions/{ext.id}: register(api) failed: {exc}")
            continue
        missing = sorted(declared - registered)
        if missing:
            errors.append(
                f"extensions/{ext.id}: manifest declares stage(s) "
                f"{', '.join(missing)} that register(api) never adds")


def _dry_run_registrations(extension_runtime, ext) -> set[str]:
    """Which stage keys `register(api)` really adds, without enabling anything."""
    recorded: set[str] = set()

    class _Recorder(extension_runtime.SonderExtensionAPI):
        def add_stage(self, key, **kwargs):
            recorded.add(str(key))
            return f"ext:{self.id}:{key}"

        def add_commit_domain(self, name, fn, **kwargs):
            return f"ext:{self.id}:{name}"

        def on_step(self, pattern, fn=None):
            return fn if fn is not None else (lambda func: func)

        def on_turn_committed(self, fn):
            return fn

        def on_character_payload(self, fn):
            return fn

        def on_narration_payload(self, fn):
            return fn

        def add_route(self, path, fn, **kwargs):
            return f"/api/extensions/{self.id}/x{path}"

    module = extension_runtime._import_entry(ext)
    register = getattr(module, "register", None)
    if not callable(register):
        raise RuntimeError("entry defines no register(api)")
    register(_Recorder(ext.id, ext.path))
    return recorded


def check_extension_imports(errors: list[str]) -> None:
    """Deep engine imports inside `extensions/` stay VISIBLE, not forbidden.

    A `code` extension runs in-process and can import anything; pretending
    otherwise would be the read-gating mistake again (`AGENTS.md`: the firewall
    is for minds, not developers). What this check defends is the facade's
    STABILITY PROMISE -- an extension that imports `db` directly is coupled to
    an internal that moves, which is precisely the SillyTavern failure mode the
    design refuses. So: a warning for bundled extensions that do it without
    declaring `capabilities.system`, and nothing at all for those that declare
    it, because then the author has said they accept the coupling.
    """
    for directory in _extension_dirs():
        manifest_path = directory / "manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            continue  # check_extension_manifests already reported it
        if (manifest.get("capabilities") or {}).get("system"):
            continue
        for source in sorted(directory.rglob("*.py")):
            if "__pycache__" in source.parts:
                continue
            try:
                tree = ast.parse(source.read_text(encoding="utf-8"))
            except SyntaxError as exc:
                errors.append(f"{source.relative_to(ROOT)}: {exc}")
                continue
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                for name in names:
                    head = name.split(".")[0]
                    if head in EXTENSION_DEEP_IMPORTS:
                        errors.append(
                            f"{source.relative_to(ROOT)}:{node.lineno}: imports "
                            f"{name!r} directly. Use the api facade, or declare "
                            f'"system": true to accept the coupling.')


def check_facade_import_direction(errors: list[str]) -> None:
    """A split family's facade must stay the only way in, and the only way out.

    `agents/director.py` and `commit.py` were split into sibling modules that
    they re-export (docs/design/DESIGN_MODULE_LAYOUT.md). Two directions keep
    that arrangement honest, and nothing else enforces either:

    OUTSIDE-IN. A caller reaching past the facade to a sibling gets a name the
    facade never promised, so the facade stops being a contract anyone can
    read — and the split's whole claim was that no caller changed.

    INSIDE-OUT. A sibling importing its own facade is an import cycle, and it
    is the one this arrangement is built to prevent: the facade imports every
    sibling at module scope, so a sibling that imports it back is a partially
    initialised module for whoever loses the race.

    Not a style rule. Both are silent until they are not: the first fails when
    somebody later moves a symbol between siblings, the second when an
    unrelated import order changes.
    """
    families = {
        "agents.director": (ROOT / "agents", "director"),
        "commit": (ROOT / "persist", "commit"),
    }
    for facade, (home, stem) in families.items():
        pkg = home.name if home.name != "agents" else "agents"
        siblings = {p.stem for p in home.glob("%s_*.py" % stem)}
        if not siblings:
            continue
        facade_mod = facade if "." in facade else "%s.%s" % (pkg, facade)
        for path in engine_python_paths() + sorted((ROOT / "tests").glob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError):
                continue
            rel = path.relative_to(ROOT).as_posix()
            inside = path.parent == home and (
                path.stem == stem or path.stem in siblings)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.level == 0:
                    name = node.module or ""
                elif isinstance(node, ast.Import):
                    name = node.names[0].name
                else:
                    continue
                head, _, tail = name.rpartition(".")
                if tail in siblings and head in (pkg, ""):
                    if not inside:
                        errors.append(
                            f"{rel}:{node.lineno}: imports {name!r}, a sibling "
                            f"behind the {facade_mod!r} facade. Import the "
                            f"facade instead — it re-exports every name.")
                elif name == facade_mod and path.stem in siblings and path.parent == home:
                    errors.append(
                        f"{rel}:{node.lineno}: imports its own facade "
                        f"{facade_mod!r}. That is the import cycle the facade "
                        f"exists to prevent; import the sibling that defines "
                        f"the name, or move the name down.")


def main() -> int:
    errors: list[str] = []
    check_undefined_names(errors)
    check_extension_manifests(errors)
    check_extension_imports(errors)
    check_facade_import_direction(errors)
    check_duplicate_python_symbols(errors)
    check_no_dead_prompts(errors)
    check_patch_debris(errors)
    check_empty_tests(errors)
    check_prompt_schema_ops(errors)
    check_specialist_prompt_chunks(errors)
    check_prose_author_chunks(errors)
    check_language_pack_surfaces(errors)
    check_generated_map(errors)

    if errors:
        print("Project structure checks failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Project structure checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
