#!/usr/bin/env python3
"""Lightweight repository-shape checks that require no external linter."""

from __future__ import annotations

import ast
import io
import json
import re
import sys
import tokenize
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


#: Decorators under which a repeated name in one body is the language working
#: as intended: a property's setter/getter/deleter, and `typing.overload`
#: stubs. Everything else that repeats a name discards the earlier definition.
_LEGITIMATE_REDEFINITION = frozenset(
    {"setter", "getter", "deleter", "overload"})


def _decorator_names(node) -> set:
    names = set()
    for decorator in node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if isinstance(target, ast.Attribute):
            names.add(target.attr)
        elif isinstance(target, ast.Name):
            names.add(target.id)
    return names


def _redefinitions(body) -> dict:
    """`{name: [line, line]}` for every name this body defines more than once."""
    seen: dict[str, list[int]] = defaultdict(list)
    for node in body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                _decorator_names(node) & _LEGITIMATE_REDEFINITION):
            continue
        seen[node.name].append(node.lineno)
    return {name: lines for name, lines in seen.items() if len(lines) > 1}


def check_duplicate_python_symbols(errors: list[str]) -> None:
    """A redefined name silently replaces the first one.

    `tests/` is included because that is where it does the most damage and
    the least noise: a duplicated test name does not error, it DELETES the
    earlier test. Four were being dropped from
    `tests/test_player_act_authority.py` -- three guards each defining
    `test_empty_and_missing_inputs_are_noops` -- and one of the lost four was
    the false-positive guard on player-speech authority, whose whole job is to
    stop the check crying wolf on ordinary narration.

    CLASS BODIES are walked too, and were not: this read `tree.body` only, so
    a method defined twice -- the exact damage the paragraph above describes,
    and the shape a test class takes -- was invisible to the check that exists
    to catch it. A property's setter/getter/deleter and `@overload` stubs are
    the one legitimate way to repeat a name in a body, and are exempt.
    """
    for path in sorted(engine_python_paths()
                       + list((ROOT / "tests").glob("test_*.py"))):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        rel = path.relative_to(ROOT).as_posix()
        for name, lines in _redefinitions(tree.body).items():
            errors.append(
                f"{rel} defines top-level symbol {name!r} "
                f"more than once at lines {lines}"
            )
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for name, lines in _redefinitions(node.body).items():
                errors.append(
                    f"{rel} defines {node.name}.{name!r} more than once at "
                    f"lines {lines}; the second definition replaces the first"
                )


def _module_level_bodies(tree: ast.AST, source: str) -> dict:
    """Module-level `def`s and simple assignments, keyed by name.

    The value is the definition's own source with its leading indentation and
    trailing blank lines stripped, so two files can be compared on what the
    definition SAYS rather than on where it sits. A docstring is included: two
    copies with different docstrings are still two copies, and the difference
    is usually one of them explaining why it exists.
    """
    lines = source.splitlines()
    found = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names = [node.name]
        elif isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names = [node.target.id]
        else:
            continue
        end = getattr(node, "end_lineno", None)
        if end is None:
            continue
        body = "\n".join(lines[node.lineno - 1:end]).strip()
        for name in names:
            found[name] = body
    return found


def check_cross_file_duplicate_definitions(errors: list[str]) -> None:
    """One definition written out twice, in two modules, with separate callers.

    `check_duplicate_python_symbols` is PER FILE -- it catches a name bound
    twice in one module, which Python resolves by discarding the first. This
    catches the other shape, which Python resolves by keeping both: the same
    function or constant copied into a second module, where nothing ever
    reports the two drifting apart because neither file is wrong on its own.

    Measured on the shape that prompted it (audit STORY-F11):
    `sanitize_attire_items` and its `_NON_ATTIRE_TERMS` set existed in
    `story/attire.py`, `persist/commit_attire.py` and `story/scene.py`, each
    with its own consumers -- the Director sanitising what a specialist
    proposed, commit sanitising what is about to be written, and scene
    sanitising an authored outfit at seed time. Three chances for one rule
    about what counts as clothing to become three different rules.

    NAME PLUS BODY, never name alone. A repo has many honest same-name
    definitions in different modules (`_key`, `_normalize`, `main`), and
    reporting those would make this noise rather than a check. Two definitions
    that are BYTE-IDENTICAL after stripping indentation are a copy, and the
    false-positive rate for that is the rate at which two people independently
    write the same lines -- which for anything longer than a line is nil.

    ENGINE FILES ONLY. A test fixture repeated across test files is ordinary
    and deliberate, and this rule is about one authority for one rule.
    """
    seen = {}
    for path in sorted(engine_python_paths()):
        rel = path.relative_to(ROOT).as_posix()
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            continue
        for name, body in _module_level_bodies(tree, source).items():
            if name in _PER_MODULE_HOOKS:
                continue
            if len(body.splitlines()) < _DUPLICATE_MIN_LINES:
                continue
            seen.setdefault((name, body), []).append(rel)
    for (name, _body), files in sorted(seen.items()):
        if len(files) > 1:
            errors.append(
                f"{name!r} is defined identically in {len(files)} modules "
                f"({', '.join(files)}); one of them owns it and the rest "
                "should import it, or they will drift apart with nothing "
                "reporting it"
            )


#: Module hooks the language resolves PER MODULE. A module-level `__getattr__`
#: cannot be imported and shared -- defining one in each module that needs it
#: is the only way to have one at all -- so "one of them owns it and the rest
#: should import it" is advice that cannot be followed. `story/importers.py`
#: and `world/offscreen.py` both carry the same four-line compat shim for
#: `_COMPAT_PROMPT_IDS`, correctly.
_PER_MODULE_HOOKS = frozenset({"__getattr__", "__dir__"})

#: Below this many lines a same-name, same-body definition is as likely to be
#: a coincidence as a copy -- `_key = lambda x: x` and a two-line `__init__`
#: are written the same way by everybody. The pair this check was built for is
#: an eight-element set and a twelve-line loop.
_DUPLICATE_MIN_LINES = 3


def check_duplicate_dict_keys(errors: list[str]) -> None:
    """A dict literal binding the same key twice keeps only the LAST one.

    Python does not warn, and the earlier entry is not a syntax error -- it is
    a line of code that reads as live, is unreachable, and disagrees with the
    one that wins. `world/spatial_barriers.py` bound `one_way_mirror` to
    `window` at line 63 and to `one_way_window` at 87: two contradictory
    readings of the same authored word, with a 20-line comment directly under
    the second carefully arguing about a NEIGHBOURING key and never noticing
    the collision. Which one won was source order.

    Alias tables are where this lands, because they are long, alphabetically
    unsorted and edited by appending -- exactly the shape a reader cannot
    check by eye. Tests are included: a duplicated key in a fixture is a case
    silently deleted from the fixture.
    """
    for path in sorted(engine_python_paths()
                       + list((ROOT / "tests").glob("test_*.py"))):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            seen: dict[tuple, int] = {}
            for key in node.keys:
                # `**spread` gives a None key, and a non-constant key cannot be
                # compared without evaluating it. Both are skipped: this check
                # reports only what is provably the same literal twice.
                if not isinstance(key, ast.Constant):
                    continue
                try:
                    marker = (type(key.value).__name__, key.value)
                    first = seen.get(marker)
                except TypeError:
                    continue
                if first is not None:
                    errors.append(
                        f"{path.relative_to(ROOT)}:{key.lineno} binds dict key "
                        f"{key.value!r} again; line {first} is dead")
                else:
                    seen[marker] = key.lineno


#: The one module allowed to derive the install root from `__file__`.
INSTALL_ROOT_OWNER = "core/paths.py"



def check_install_root_derivations(errors: list[str]) -> None:
    """Only `core/paths.py` may work out where the install is.

    Every module that derived it from `__file__` was correct while the engine
    was a flat directory. On 2026-08-18 eighty-one modules moved into
    packages and three of those derivations silently began naming their own
    package: `core/updates.py`'s `REPO_ROOT` became `<install>/core`, which
    disabled self-update for every real install, and `dressing/backdrops.py`
    and `dressing/ambience.py` started looking for the host's generated
    images and fetched audio under `dressing/` -- orphaning 751 MB of the
    owner's assets on the machine this was found on.

    Nothing failed. `_is_git_repo` returned False, which is a legitimate
    answer; the asset directories were simply created empty. That is why this
    is a structural check and not a test: the symptom of getting it wrong is
    an engine that quietly does less.

    The rule is `__file__` itself, not three spellings of walking up from it.
    It used to be a substring match on
    `os.path.dirname(os.path.abspath(__file__))`,
    `Path(__file__).resolve().parent.parent` and `Path(__file__).parent.parent`
    -- a literal guard, evaded by `parents[1]`, by an aliased `Path`, or by
    splitting the walk across two statements, none of which is exotic. The
    stronger rule costs nothing HERE and only here: measured 2026-08-19,
    `__file__` appears four times across the twelve engine roots, once in
    `core/paths.py` itself and three times inside comments explaining this very
    rule. An AST walk does not see a comment, so the check ships with **no
    exemption list at all** -- which will stop being true the first time
    someone adds one, and that is the point at which the exemption should be
    argued rather than inherited.
    """
    for path in sorted(engine_python_paths()):
        # `.as_posix()`, not `str()`. `INSTALL_ROOT_OWNER` is written with a
        # forward slash because every constant in this file is, and on Windows
        # `str(Path)` yields `core\paths.py` -- so the one file PERMITTED to
        # derive a root audited itself as a violation and no maintainer on
        # Windows could get a green structural check. Reported by the
        # Directive team against alpha 9.6.1, reproduced in their 3.12 venv.
        # Every other comparison site in this file already did this; this one
        # was the outlier, which is why it was invisible.
        rel = path.relative_to(ROOT).as_posix()
        if rel == INSTALL_ROOT_OWNER:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == "__file__":
                errors.append(
                    f"{rel}:{node.lineno} reads __file__; import INSTALL_ROOT "
                    f"from core.paths instead -- a module that moves takes "
                    f"its own wrong answer with it. Only {INSTALL_ROOT_OWNER} "
                    f"may ask where the install is.")


def check_patch_debris(errors: list[str]) -> None:
    paths = (engine_python_paths()
             + list((ROOT / "static" / "js").glob("*.js")))
    for path in sorted(paths):
        text = path.read_text(encoding="utf-8")
        for marker in FORBIDDEN_PATCH_MARKERS:
            if marker in text:
                errors.append(f"{path.relative_to(ROOT)} still contains patch marker {marker!r}")


def check_empty_tests(errors: list[str]) -> None:
    """A `test_*.py` that contributes no test, and a test that runs nothing.

    Only whitespace-only files were flagged, which is the one shape this
    never actually takes. A file whose tests were all deleted, renamed out of
    the `test_` prefix, or absorbed into a class that lost its `Test` prefix
    still holds imports, helpers and docstrings -- it reads like a suite and
    collects nothing, and the suite total moves by a number nobody watches.

    The second rule is narrower on purpose. A test with no `assert` is not
    automatically empty: "this call does not raise" is a real assertion made
    by execution. A test whose body is nothing BUT imports asserts neither --
    `test_the_producer_is_wired_at_the_commit_tail` was a docstring and
    `import tests.test_commit_tail_producers`, and it passed.
    """
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT).as_posix()
        if not text.strip():
            errors.append(f"{rel} is empty")
            continue
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError:
            continue
        collected = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and node.name.startswith("test"):
                collected.append(node)
            elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                collected.append(node)
        if not collected:
            errors.append(
                f"{rel} collects no test: nothing in it is named `test*` or "
                f"`Test*`, so pytest runs none of it.")
        for node in collected:
            if isinstance(node, ast.ClassDef):
                continue
            body = [n for n in node.body
                    if not (isinstance(n, ast.Expr)
                            and isinstance(n.value, ast.Constant))]
            if body and all(isinstance(n, (ast.Import, ast.ImportFrom))
                            for n in body):
                errors.append(
                    f"{rel}:{node.lineno}: {node.name} does nothing but "
                    f"import. It passes without exercising anything.")


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



_TIME_SHAPE_LINE = re.compile(r"time:\s*\{([^}]*)\}")
_TIME_PROSE_LINE = re.compile(r"state_diff\.time with ([^.。]*)")
_TIME_TOKEN = re.compile(r"[a-z_]+")


def _time_non_seconds_keys() -> frozenset:
    """Which tokens a shape/prose scan may legitimately surface that are not
    `*_seconds`. Everything else in those spans is ordinary English ("and",
    "bool") or an enum member ("action", "time_skip"), not a field name.

    Read from `world.mechanics.TIME_METADATA_KEYS` rather than copied: that
    set IS "the vocabulary's non-claim half", and a second hand-kept copy of
    a set whose whole purpose is to be the single authority is the drift this
    check exists to catch."""
    from world.mechanics import TIME_METADATA_KEYS

    return TIME_METADATA_KEYS


def check_time_channel_vocabulary(errors: list[str]) -> None:
    """Every `state_diff.time` key the engine TEACHES must be one its reader
    can read.

    `state_diff.time` is `Optional[dict]`, so validation accepts any key and
    the only thing that decides whether a key means anything is
    `world.mechanics.read_time_diff`. That reader knew exactly one absolute
    spelling from before this repository's first commit while the resolve
    payload printed the clock to the model under a different one, and the
    corpus paid: 22 stored diffs named the position as `elapsed_seconds`, 5
    of them with no other numeric key at all, every one silently discarded.
    In chat 88, turns 61 and 64 claimed 1107 and 1266 against a clock
    standing at 1106.0 and turn 66 claimed 7200 against 1136.0; none of the
    three moved the clock and nothing warned anywhere.

    HONEST LIMIT, stated because the general form is the one you would want:
    "any bare-dict channel whose reader ignores keys the schema accepts" is
    NOT statically tractable in this checker's style. `Optional[dict]`
    accepts every key by construction, and reader blindness is a dataflow
    property, not a shape one. What IS cheap is the narrow fold below --
    hold the prompts and the shipped output examples to the reader's own key
    set -- and it catches the drift class from the side that a repository
    can control.

    The authority is deliberately `TIME_DIFF_KEYS` and not the prompt: the
    spelling that actually bit was never prompt-taught at all. The payload's
    own `simulation_clock` key taught it, which is a surface no prompt scan
    would ever have seen.
    """
    sys.path.insert(0, str(ROOT))
    try:
        from world.mechanics import TIME_DIFF_KEYS
        from llm import schemas
    except Exception as exc:  # pragma: no cover - import failure is its own error
        errors.append(f"could not check the state_diff.time vocabulary: {exc}")
        return

    def report(source: str, key: str) -> None:
        errors.append(
            f"the {source} teaches state_diff.time key {key!r}, which is not "
            "in world.mechanics.TIME_DIFF_KEYS -- no reader in the engine "
            "has any meaning for it, so a beat that spells it advances "
            "nothing and warns instead"
        )

    def walk(node, path: str) -> None:
        if isinstance(node, Mapping):
            for key, value in node.items():
                if (key == "state_diff" and isinstance(value, Mapping)
                        and isinstance(value.get("time"), Mapping)):
                    for name in sorted(value["time"]):
                        if name not in TIME_DIFF_KEYS:
                            report(f"{path}/{key} output example", name)
                walk(value, f"{path}/{key}")
        elif isinstance(node, list):
            for i, value in enumerate(node):
                walk(value, f"{path}/{i}")

    walk(schemas.OUTPUT_EXAMPLES, "")

    # The repo root is not on sys.path at module scope here; `tools/` is.
    sys.path.insert(0, str(ROOT))
    from language_runtime.card_source import read_card_source

    non_seconds = _time_non_seconds_keys()
    scanned = 0
    # `read_card_source`, deliberately, not `pack.card(...)`. This scans the
    # AUTHORED text once per authored leaf, which is what the check has always
    # done; the loaded card has already substituted four fragments into
    # seventeen bodies, so reading that would rescan each of them seventeen
    # times. Since the split the prose is not in the JSON at all -- it is in
    # `cards/system_prompts/*.txt` -- so a glob over the index file would scan
    # 14 KB of `{"$text": ...}` references and find nothing at all.
    for pack_dir in sorted(
            path for path in (ROOT / "language_packs").iterdir()
            if (path / "cards" / "system_prompts.json").exists()):
        try:
            card = read_card_source(pack_dir, "system_prompts")
        except Exception as exc:
            errors.append(f"could not read {pack_dir.name} system_prompts: {exc}")
            continue

        def strings(node):
            if isinstance(node, str):
                yield node
            elif isinstance(node, Mapping):
                for value in node.values():
                    yield from strings(value)
            elif isinstance(node, list):
                for value in node:
                    yield from strings(value)

        rel = (pack_dir / "cards" / "system_prompts").relative_to(ROOT).as_posix()
        for text in strings(card):
            scanned += 1
            for pattern in (_TIME_SHAPE_LINE, _TIME_PROSE_LINE):
                for span in pattern.findall(text):
                    for token in _TIME_TOKEN.findall(span):
                        if not (token.endswith("_seconds")
                                or token in non_seconds):
                            continue
                        if token not in TIME_DIFF_KEYS:
                            report(f"{rel} prompt", token)

    # A self-tripwire. This check once read a file whose prose had moved and
    # would have passed on an empty scan -- a check that stops looking is
    # worse than one that fails, because it is believed. Two packs carry 226
    # authored string leaves each.
    if scanned < 200:
        errors.append(
            f"time-channel scan saw {scanned} prompt strings; the card source "
            "is not being read")


def check_prompt_card_parts(errors: list[str]) -> None:
    """A split prompt card's index and its part files must agree exactly.

    Since the split, `cards/system_prompts.json` is an index of
    `{"$text": "<path>"}` references and the prose lives one file per prompt
    in `cards/system_prompts/`. Four ways that decays, each of which this
    catches and none of which a green suite would otherwise notice:

      * a `.txt` no reference claims -- a prompt written, committed, and
        never sent to any model;
      * a reference at a path that is not `canonical_part_path` for its own
        leaf, which would make the layout advisory rather than derived;
      * a part file not in canonical written form (exactly one trailing
        newline beyond the leaf's text), which is how a CRLF checkout or a
        trailing-whitespace-trimming editor first shows up. The READER
        forgives a missing final newline so the common accident cannot
        change a prompt; nothing forgives it on disk, or the convention that
        makes the accident harmless erodes;
      * a prose leaf RE-INLINED into the index. Nobody would move 62 KB back
        by hand, but a tool that rewrites the card without going through
        `write_card_source` would, and the card would keep working while
        quietly becoming unreadable again.

    Also en-vs-ja part-path parity, which the pack loader structurally cannot
    see: `_leaf_paths` treats `prose_author_sheet` as ONE path, so a pack
    shipping 27 segments instead of 28 passes its card-parity comparison.
    """
    sys.path.insert(0, str(ROOT))
    from language_runtime.card_source import (
        CardSourceError, canonical_part_path, card_parts_dir, decode_part,
        encode_part, is_part_leaf, part_plan, read_card_source,
    )

    #: A prose leaf shorter than this may legitimately sit inline (a card that
    #: has not been split at all is the normal case). Above it, a leaf at a
    #: part-leaf path is prose that belongs in a file.
    inline_limit = 200
    declared: dict[str, set[str]] = {}
    for pack_dir in sorted(
            path for path in (ROOT / "language_packs").iterdir()
            if path.is_dir()):
        for card_name in sorted(
                path.stem for path in (pack_dir / "cards").glob("*.json")
                if path.is_file()):
            parts_dir = card_parts_dir(pack_dir, card_name)
            label = f"{pack_dir.name}/{card_name}"
            index_path = pack_dir / "cards" / f"{card_name}.json"
            try:
                index = json.loads(index_path.read_text(encoding="utf-8"))
            except Exception as exc:
                errors.append(f"could not read {label} index: {exc}")
                continue
            if not parts_dir.is_dir():
                # Unsplit card. Nothing to check but the anti-decay rule,
                # which only applies once a card HAS been split.
                continue
            try:
                card = read_card_source(pack_dir, card_name)
            except CardSourceError as exc:
                errors.append(f"{label}: {exc}")
                continue

            plan = part_plan(card)
            expected = {rel for _leaf, rel, _text in plan}
            declared[label] = expected
            on_disk = {path.relative_to(parts_dir).as_posix()
                       for path in parts_dir.rglob("*.txt") if path.is_file()}
            for rel in sorted(on_disk - expected):
                errors.append(
                    f"{label}: {rel} is a part file no reference claims, so "
                    "nothing ships it to a model. Reference it from the card "
                    "index or delete it.")
            for rel in sorted(expected - on_disk):
                errors.append(f"{label}: {rel} is referenced but missing")

            for leaf_path, rel, _text in plan:
                node = index
                for segment in leaf_path:
                    try:
                        node = node[segment]
                    except (KeyError, IndexError, TypeError):
                        node = None
                        break
                if node != {"$text": rel}:
                    errors.append(
                        f"{label}: the index entry for {rel} is {node!r}, not "
                        f'{{"$text": "{rel}"}} -- part paths are derived from '
                        "the leaf path by `canonical_part_path`, never chosen")

            for rel in sorted(on_disk & expected):
                data = (parts_dir / rel).read_bytes()
                try:
                    text = decode_part(data, f"{label} {rel}")
                except CardSourceError as exc:
                    errors.append(str(exc))
                    continue
                if encode_part(text) != data:
                    errors.append(
                        f"{label}: {rel} is not in canonical written form. A "
                        "part file is its leaf's exact text plus exactly one "
                        "trailing newline; anything else is an editor having "
                        "changed a prompt on save.")

            # The anti-decay rule.
            def inline_prose(value, leaf_path=()):
                if isinstance(value, Mapping):
                    if "$text" in value:
                        return
                    for key, child in value.items():
                        yield from inline_prose(child, leaf_path + (str(key),))
                elif isinstance(value, list):
                    for position, child in enumerate(value):
                        yield from inline_prose(child, leaf_path + (position,))
                elif isinstance(value, str) and is_part_leaf(leaf_path):
                    if len(value) >= inline_limit:
                        yield leaf_path, value

            for leaf_path, value in inline_prose(index):
                errors.append(
                    f"{label}: {'.'.join(str(s) for s in leaf_path)} holds "
                    f"{len(value)} characters of prose inline in the card "
                    "index. Prose lives one leaf per file under "
                    f"cards/{card_name}/; re-inlining it is how a 414 KB "
                    "single-document card came back.")

    for card_name in sorted({label.split("/", 1)[1] for label in declared}):
        rows = {label.split("/", 1)[0]: paths
                for label, paths in declared.items()
                if label.split("/", 1)[1] == card_name}
        if "en" not in rows:
            continue
        for language, paths in sorted(rows.items()):
            if language == "en":
                continue
            missing = sorted(rows["en"] - paths)
            extra = sorted(paths - rows["en"])
            if missing or extra:
                errors.append(
                    f"{language}/{card_name} declares different part files "
                    f"than en: missing {missing[:5]}, extra {extra[:5]}. The "
                    "pack loader cannot see this -- `_leaf_paths` treats "
                    "`prose_author_sheet` as a single path, so a pack short "
                    "one segment passes its card-parity check.")


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
    # The card STORES a body for most prompts and assembles seven of them --
    # the six specialist sheets and the prose author's -- from
    # `specialists`/`prose_author_sheet` instead. Storing an assembled sheet
    # as well is what let the published `director_spatial` drift 1,518
    # characters short of the one the engine actually sends, so the absence is
    # deliberate and the registry is still the inventory both must agree on.
    prompt_ids = (set(english.card("system_prompts")["prompts"])
                  | set(prompts.ASSEMBLED_SHEET_IDS))
    if prompt_ids != set(prompts.DEFAULT_PROMPTS):
        errors.append("English system-prompt card and runtime registry disagree")
    stored_assembled = sorted(
        set(english.card("system_prompts")["prompts"])
        & set(prompts.ASSEMBLED_SHEET_IDS))
    if stored_assembled:
        errors.append(
            "English pack stores a body for assembled sheet(s) "
            f"{stored_assembled}; an assembled sheet has no stored body, and "
            "one that grows a second copy is free to drift from the sheet the "
            "engine sends")
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
        # A reason must be a DECISION, not a re-derivable guess. The reasons
        # used to be copied from the drafting tool's `code_reason` heuristic;
        # the heuristic was later improved and the ledger was not, so 17
        # player-facing strings sat untranslated in the shipped Japanese UI
        # behind the words "source, style, selector, or markup fragment" --
        # each one passing the non-empty check above. Banning the generated
        # vocabulary outright is what makes that class impossible: a stored
        # reason no machine can produce is one a person had to write.
        generated = {
            "protocol, brand, or literal control name",
            "identifier, route, enum, class, or filename",
            "path, selector, markup, or query fragment",
            "source, style, selector, or markup fragment",
            "placeholder-only template",
            "source expression fragment",
            "punctuation or numeric literal",
        }
        machine_written = sorted(
            text for text, reason in exceptions.items()
            if str(reason).strip() in generated)
        if machine_written:
            errors.append(
                f"language pack {language_id!r} has "
                f"{len(machine_written)} translation exceptions carrying a "
                "generated reason; write why that string is untranslatable: "
                + ", ".join(repr(text[:40]) for text in machine_written[:5]))
        echoed = sorted(text for text, reason in exceptions.items()
                        if str(reason).strip() == text.strip())
        if echoed:
            errors.append(
                f"language pack {language_id!r} has {len(echoed)} translation "
                "exceptions whose reason is a copy of the string itself: "
                + ", ".join(repr(text[:40]) for text in echoed[:5]))
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

#: Engine code that is NOT a subsystem package, and must not be added to
#: `SUBSYSTEM_PACKAGES` -- that tuple is also the deep-import BAN list, and
#: `extension_runtime` is the one package an extension is supposed to reach.
#: They are still the engine's own source and still owe every structural rule.
#:
#: They were in neither `make compile` nor any check here until 2026-08-18, so
#: `extension_runtime/api.py` -- the entire public extension surface, the thing
#: an integrator's production code is told to depend on -- was the least
#: covered source in the repository. Found while closing the gap that let a
#: 3.11-unparseable f-string ship: the checks that would have caught it did not
#: look here.
NON_PACKAGE_ENGINE_DIRS = ("agents", "extension_runtime", "language_runtime",
                           "language_adapters")

#: The engine's own importable modules: eight subsystem packages plus four
#: loose directories. This is the set every structural rule below is
#: answerable for.
ENGINE_PACKAGE_ROOTS = SUBSYSTEM_PACKAGES + NON_PACKAGE_ENGINE_DIRS

#: EVERY directory in this repository that holds Python this project wrote.
#: One tuple, because there were four hand-kept inventories of the same thing
#: -- this file's `SUBSYSTEM_PACKAGES` + `NON_PACKAGE_ENGINE_DIRS`, a third
#: ad-hoc list inside `check_undefined_names` that redundantly re-appended
#: three directories `engine_python_paths()` already returned, and the
#: `make compile` argument list. Four copies of "where the source is" is four
#: chances for a new directory to be covered by some of the checks and not
#: others, which is exactly how `demo/` came to be compiled by the Makefile
#: and scanned by nothing here.
#:
#: `make compile` now reads this tuple rather than repeating it:
#: `python tools/project_check.py --source-roots` prints it, one per line.
#: `extensions/` is deliberately absent -- it holds INSTALLED third-party
#: trees, not this project's source, and `_extension_dirs()` covers what the
#: engine actually promises about them.
ENGINE_SOURCE_ROOTS = ENGINE_PACKAGE_ROOTS + (
    "tools", "tests", "browser_tests", "demo")


def _python_files(root: str) -> list[Path]:
    """Every `.py` under one repository directory, `__pycache__` excluded.

    `rglob`, never `glob`. The packages were walked one level deep and the
    loose directories recursively, for no reason anyone recorded; measured
    2026-08-19 the difference was zero files, which is precisely why it was
    invisible and why the first `core/sub/thing.py` anyone adds would have
    been checked by nothing.
    """
    return [path for path in (ROOT / root).rglob("*.py")
            if "__pycache__" not in path.parts]


def engine_python_paths():
    """Every .py file the engine itself owns, packages plus the loose dirs."""
    out = []
    for root in ENGINE_PACKAGE_ROOTS:
        out.extend(_python_files(root))
    return sorted(out)


def repository_python_paths():
    """Every .py file this project wrote, engine plus tools/tests/demo."""
    out = []
    for root in ENGINE_SOURCE_ROOTS:
        out.extend(_python_files(root))
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

    # Enumerated rather than rglob'd from ROOT. `ROOT` contains
    # `.claude/worktrees/`, which holds several complete checkouts of this
    # repository, and a whole-tree walk therefore scans the engine seven times
    # over and takes minutes. `ENGINE_SOURCE_ROOTS` is the enumeration; the
    # three redundant re-appends that used to sit here (`extension_runtime`,
    # `language_runtime`, `language_adapters`, all already returned by
    # `engine_python_paths()`) are gone with it.
    paths = repository_python_paths() + list((ROOT / "extensions").glob("*/*.py"))
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
        # A dry-run registration: load the entry against a throwaway API and
        # see what it ACTUALLY registers. Cheaper and far more honest than
        # parsing the source for `add_stage` calls.
        #
        # Run for EVERY extension with a python entry, not only for one that
        # declares stages. It was gated on `if not declared: continue`, so of
        # three bundled extensions only `cohesion-demo` was ever load-tested:
        # `campaign-demo` and `overlay-demo` register commit domains, routes
        # and hooks instead of stages, and an import error or a `register()`
        # that raised in either would have reached a host's Extensions menu
        # with nothing between. Loading is the half that must run for
        # everyone; comparing stage keys is the half that needs a declaration.
        if not ext.python_entry:
            continue
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


#: A local name is being used AS A MODULE OBJECT, not called through.
#: `monkeypatch.setattr(mod, name, ...)` and `mod.__file__` both need the
#: module that DEFINES the symbol; a facade re-export is a different binding.
_MODULE_OBJECT_CALLS = frozenset({
    "setattr", "delattr", "getattr", "hasattr", "reload",
    "getsource", "getsourcefile", "getsourcelines", "getmembers", "signature",
})
_MODULE_OBJECT_ATTRS = frozenset({"__file__", "__name__", "__dict__", "__doc__"})


def _module_object_uses(tree: ast.AST) -> set[str]:
    """Local names this file treats as a module object rather than a namespace."""
    used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and node.args:
            func = node.func
            fname = (func.attr if isinstance(func, ast.Attribute)
                     else func.id if isinstance(func, ast.Name) else "")
            if fname in _MODULE_OBJECT_CALLS and isinstance(node.args[0], ast.Name):
                used.add(node.args[0].id)
        elif isinstance(node, ast.Attribute) and node.attr in _MODULE_OBJECT_ATTRS:
            if isinstance(node.value, ast.Name):
                used.add(node.value.id)
    return used


def facade_import_violations(source, *, pkg: str, stem: str, siblings,
                             inside: bool = False, is_test: bool = False):
    """Every facade-rule violation in one file: `(lineno, kind, module)`.

    `kind` is `"outside-in"` (a caller reached past the facade to a sibling)
    or `"inside-out"` (a sibling imported its own facade, which is the cycle
    the arrangement exists to prevent).

    Both spellings count, and that is the repair this function exists for.
    The matcher this replaced `rpartition`ed the module name, so it saw
    `from persist.commit_memory import X` and never `from persist import
    commit_memory` -- and the second is the form the whole tree is written in.
    Twelve sibling imports sat in `tests/` unseen; the rule held only where
    nobody was writing.

    `is_test` carries the exception the split's own correctness requires. A
    monkeypatch must name the module that DEFINES the function it intercepts:
    a moved function resolves names in its own globals, so a patch on the
    facade's re-export is silently inert (`docs/experiments/AUDIT_COMMIT.md`),
    and the same holds for a test that reads a sibling's `__file__` to parse
    the source. The facade is a contract for CALLERS, and neither of those is
    a call -- so a test may name a sibling it patches or introspects, and may
    not name one it merely calls through.
    """
    tree = source if isinstance(source, ast.AST) else ast.parse(source)
    siblings = set(siblings)
    exempt = _module_object_uses(tree) if is_test else set()
    facade_mod = "%s.%s" % (pkg, stem)
    out = []

    def record(node, module, local):
        if module == facade_mod or module == stem:
            if inside:
                out.append((node.lineno, "inside-out", module))
        elif not inside and not (local and local in exempt):
            out.append((node.lineno, "outside-in", module))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                head, _, tail = alias.name.rpartition(".")
                if head not in (pkg, ""):
                    continue
                if tail in siblings or tail == stem:
                    local = alias.asname or (alias.name if not head else None)
                    record(node, "%s.%s" % (pkg, tail), local)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            module = node.module or ""
            if module == pkg:
                for alias in node.names:
                    if alias.name in siblings or alias.name == stem:
                        record(node, "%s.%s" % (pkg, alias.name),
                               alias.asname or alias.name)
            else:
                head, _, tail = module.rpartition(".")
                if head in (pkg, "") and (tail in siblings or tail == stem):
                    # Names lifted OUT of the sibling: no module object is
                    # bound, so no patch or source read can be meant by it.
                    record(node, "%s.%s" % (pkg, tail), None)
    return sorted(out)


def facade_siblings(home: Path, stem: str) -> set:
    """The modules a facade actually re-exports, read off its own imports.

    NOT `glob("<stem>_*.py")`. A filename prefix is a guess about membership,
    and it is wrong here: `world/spatial_frames.py` matches `spatial_*` and is
    NOT behind `world/spatial.py` — the facade contains zero references to it —
    so a family built by prefix would have flagged six correct engine imports
    and three correct test imports as facade violations. The facade's own
    import block is the only statement of what it promises to re-export, and
    it cannot drift from the promise because it IS the promise.

    Relative and absolute spellings both count: `agents/director.py` imports
    its nine siblings as `from .director_lingua import ...`, and
    `persist/commit.py` imports its thirteen as `from persist.commit_x`.
    """
    facade_path = home / (stem + ".py")
    try:
        tree = ast.parse(facade_path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return set()
    prefix = stem + "_"
    found = set()
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        elif isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        else:
            continue
        for name in names:
            tail = name.rpartition(".")[2]
            if tail.startswith(prefix) and (home / (tail + ".py")).is_file():
                found.add(tail)
    return found


#: Every facade family this rule covers, as `name -> (package dir, stem)`.
#:
#: A MODULE-LEVEL map rather than a local, so a test can ask which facades are
#: covered without re-parsing the tree or reading this function's source.
#: `world.spatial` was the third of the three and sat outside the check for as
#: long as the check existed, behind a comment saying adding the line was all
#: it took. It took the line plus eight import sites -- `world/crowds.py`
#: reaching for `world.spatial_geometry`'s `ROOM_SIZES`, and seven test sites
#: naming `spatial_orientation`/`spatial_senses`/`spatial_contacts` to CALL
#: through rather than to patch -- each of which is the drift a facade rule
#: exists to stop: a caller that knows which sibling defines a name, and
#: therefore pins where the name lives.
#:
#: `facade_siblings` reads each family's members off the facade's own import
#: block, never off a filename glob, which is why `world/spatial_frames.py`
#: (prefix match, not behind the facade) is correctly outside `world.spatial`.
FACADE_FAMILIES = {
    "agents.director": (ROOT / "agents", "director"),
    "commit": (ROOT / "persist", "commit"),
    "mind.memory": (ROOT / "mind", "memory"),
    "world.spatial": (ROOT / "world", "spatial"),
}


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

    The rule is about CALLERS. `facade_import_violations` carries the one
    exception, and why a test is not always a caller.
    """
    tests_dir = ROOT / "tests"
    for facade, (home, stem) in FACADE_FAMILIES.items():
        pkg = home.name
        siblings = facade_siblings(home, stem)
        if not siblings:
            continue
        facade_mod = facade if "." in facade else "%s.%s" % (pkg, facade)
        for path in engine_python_paths() + sorted(tests_dir.glob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError):
                continue
            rel = path.relative_to(ROOT).as_posix()
            inside = path.parent == home and (
                path.stem == stem or path.stem in siblings)
            is_test = path.parent == tests_dir
            for lineno, kind, module in facade_import_violations(
                    tree, pkg=pkg, stem=stem, siblings=siblings,
                    inside=inside, is_test=is_test):
                if kind == "outside-in":
                    extra = ("" if not is_test else
                             " A test may name a sibling it PATCHES or reads"
                             " the source of — patching the facade's re-export"
                             " is inert — but not one it only calls through.")
                    errors.append(
                        f"{rel}:{lineno}: imports {module!r}, a sibling "
                        f"behind the {facade_mod!r} facade. Import the "
                        f"facade instead — it re-exports every name.{extra}")
                else:
                    errors.append(
                        f"{rel}:{lineno}: imports its own facade "
                        f"{facade_mod!r}. That is the import cycle the facade "
                        f"exists to prevent; import the sibling that defines "
                        f"the name, or move the name down.")


def _engine_module_index() -> tuple[set[str], dict[str, list[str]]]:
    """Every engine module by dotted name, and by its bare final component."""
    names = {"agents"}
    for path in engine_python_paths():
        rel = path.relative_to(ROOT).with_suffix("")
        parts = list(rel.parts)
        if parts[-1] == "__init__":
            parts.pop()
        names.add(".".join(parts))
    names.update(SUBSYSTEM_PACKAGES)
    by_tail: dict[str, list[str]] = {}
    for name in names:
        by_tail.setdefault(name.rpartition(".")[2], []).append(name)
    return names, by_tail


def engine_import_violations(source, names: set[str], by_tail: dict) -> list:
    """`(lineno, message)` for every import naming a module that is not there."""
    tree = source if isinstance(source, ast.AST) else ast.parse(source)
    engine_roots = set(SUBSYSTEM_PACKAGES) | {"agents"}
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            targets = [node.module or ""]
        else:
            continue
        for target in targets:
            if target in names:
                continue
            root = target.partition(".")[0]
            if root in engine_roots:
                out.append((node.lineno, "imports %r, which is not a module "
                                         "in this tree." % target))
            elif "." not in target:
                moved = sorted(by_tail.get(target, []))
                if moved:
                    out.append((node.lineno,
                                "imports %r, a module name from before the "
                                "package move. It is now %s."
                                % (target, " or ".join(moved))))
    return sorted(out)


def check_engine_imports_resolve(errors: list[str]) -> None:
    """An import naming an engine module that does not exist.

    The class the package move created and nothing catches: `tools/` drivers
    are imported by nothing — no test, no route, no other module — so a name
    that stopped resolving fails only when a human runs the tool, months
    later, and usually into a bare `except` that degrades a metric instead of
    raising. `tools/perception_quality.py` asked for `spatial` and
    `character_schema` for weeks; its dialogue-entitlement gate was off the
    whole time and it exited 0.

    Checked statically, by name, against the modules that actually exist: a
    bare name matching a moved module is reported WITH where it went, so the
    repair is in the message. Nothing is executed to run this — a driver must
    not have to be runnable to be checked.
    """
    names, by_tail = _engine_module_index()
    for path in sorted((ROOT / "tools").glob("*.py")) + engine_python_paths():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        rel = path.relative_to(ROOT).as_posix()
        for lineno, message in engine_import_violations(tree, names, by_tail):
            errors.append(f"{rel}:{lineno}: {message}")


ASGI_TARGET = re.compile(r"uvicorn\s+(?:[-\w]+\s+)*([\w.]+):(\w+)")


def check_asgi_targets(errors: list[str]) -> None:
    """Every `uvicorn module:attr` a launcher runs must name a real module.

    The launchers are shell, batch and make — nothing imports them, nothing
    compiles them, and the suite cannot see them at all. `tools/test_server.sh`
    still said `uvicorn app:app` nine days after the app became `web.app`, so
    the script whose whole job is "start a server against a COPY of the
    database, never the live one" failed at startup and sent anyone who
    reached for it back to the launcher that uses the real database.
    """
    names, by_tail = _engine_module_index()
    launchers = [ROOT / "Makefile"] + sorted((ROOT / "tools").glob("*.sh"))
    launchers += sorted(ROOT.glob("*.bat")) + sorted(ROOT.glob("*.sh"))
    for path in launchers:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = path.relative_to(ROOT).as_posix()
        for lineno, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            for match in ASGI_TARGET.finditer(line):
                module = match.group(1)
                if module in names:
                    continue
                moved = sorted(by_tail.get(module.rpartition(".")[2], []))
                where = (" It is now %s." % " or ".join(moved)) if moved else ""
                errors.append(
                    f"{rel}:{lineno}: runs {match.group(0)!r}, but "
                    f"{module!r} is not a module in this tree.{where}")


def check_conftest_not_imported(errors: list[str]) -> None:
    """`conftest.py` is pytest's to import, and only pytest's.

    pytest loads a conftest under a name of its own choosing (`conftest` for a
    directory with no `__init__.py`). Any other module that imports the same
    file under a second name -- `tests.conftest`, `from conftest import X` --
    does not reach that module object; Python builds a SECOND one. Every
    import-time side effect then runs twice, and only one copy's fixtures are
    registered, so whatever the second copy allocated has no owner and no
    teardown.

    Measured, 2026-08-18: five test files imported `tests.conftest` for one
    plain helper function. `_redirect_default_database()` therefore ran twice
    per session, `db.DB` ended the collection pointing at the unowned copy,
    and every suite run left one more 516,096-byte scratch database in
    /dev/shm -- 164 of them by the time anyone counted. Nothing failed.

    A helper that tests share belongs in a module tests import BY NAME
    (`tests/helpers.py`). A conftest holds fixtures and hooks, which pytest
    delivers without an import.
    """
    for path in sorted((ROOT / "tests").rglob("*.py")) + engine_python_paths():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        if path.name == "conftest.py":
            continue
        rel = path.relative_to(ROOT).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level == 0:
                names = [node.module or ""]
            elif isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            else:
                continue
            for name in names:
                if name.rpartition(".")[2] == "conftest":
                    errors.append(
                        f"{rel}:{node.lineno}: imports {name!r}. pytest already "
                        f"imported that file under its own name, so this builds "
                        f"a second module object and runs its import-time side "
                        f"effects again. Move the shared helper into a plain "
                        f"module (tests/helpers.py) and import that.")


def check_minimum_python_syntax(errors: list[str]) -> None:
    """No source may need a parser newer than the declared minimum.

    Both launchers declare 3.11-3.13, and 3.11's parser reads an f-string as
    ONE string token -- so a quote inside a replacement field that matches the
    opening quote ends the literal early and the FILE WILL NOT COMPILE. PEP 701
    lifted that in 3.12, which is why nobody developing on 3.12 or 3.13 can see
    it: the code is correct, the interpreter is not the declared one.

    Found by the Directive team, who ran the declared minimum in CI and got a
    compile failure on `agents/director_floors.py` -- three `_ling("...")` calls
    inside `rf"..."` patterns. `make check` was green the whole time.

    Detected through 3.12's own TOKENIZER rather than by regex or by having
    3.11 installed: 3.12 emits FSTRING_START/END around the parts, so a STRING
    token inside those bounds whose quote matches the opening one is exactly
    the construct 3.11 cannot read. A multi-line replacement field in a
    single-quoted f-string is the same class and is caught here too. A grep for
    nested quotes reported 108 sites; this reports the 3 that are real.
    """
    if not hasattr(tokenize, "FSTRING_START"):
        return                       # pre-3.12 host: it is the minimum itself
    for path in engine_python_paths() + sorted((ROOT / "tests").rglob("*.py")):
        try:
            src = path.read_text(encoding="utf-8")
            toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
        except (OSError, SyntaxError, tokenize.TokenError):
            continue
        rel = path.relative_to(ROOT).as_posix()
        stack = []
        for tok in toks:
            if tok.type == tokenize.FSTRING_START:
                quote = tok.string[-1]
                stack.append((quote, tok.string.endswith(quote * 3)))
            elif tok.type == tokenize.FSTRING_END:
                if stack:
                    stack.pop()
            elif not stack:
                continue
            elif tok.type == tokenize.STRING:
                quote, triple = stack[-1]
                inner = tok.string.lstrip("rRbBuUfF")
                if not triple and inner[:1] == quote:
                    errors.append(
                        f"{rel}:{tok.start[0]}: an f-string delimited by {quote}"
                        f" contains {quote} inside a replacement field. Python "
                        f"3.12 accepts this (PEP 701); the declared minimum "
                        f"3.11 cannot parse the file at all. Use the other "
                        f"quote inside the braces.")
            elif tok.type == tokenize.NL:
                quote, triple = stack[-1]
                if not triple:
                    errors.append(
                        f"{rel}:{tok.start[0]}: a replacement field spans a "
                        f"line break inside a single-quoted f-string. PEP 701 "
                        f"again: 3.12 parses it, the declared minimum 3.11 "
                        f"does not.")


#: The field attributes that exist on exactly one Pydantic major. Reading one
#: outside the module that owns the branch is how a check silently becomes a
#: no-op on the OTHER major -- which is not hypothetical: the suite runs
#: whatever `python` resolves to and the engine serves from `.venv`, and those
#: were pydantic 1 and pydantic 2 on the owner's own machine.
_PYDANTIC_MAJOR_ATTRS = {
    "outer_type_": 1, "allow_none": 1, "type_": 1, "field_info": 1,
    "model_fields": 2, "annotation": 2,
}

#: Modules allowed to read them: the one that OWNS the compatibility branch,
#: and this checker, which deliberately reads both and says so at the site.
_PYDANTIC_BRANCH_OWNERS = {"llm/schemas.py", "tools/project_check.py"}


def check_pydantic_major_reads_are_owned(errors: list[str]) -> None:
    """Only `llm/schemas.py` may read a Pydantic-major-specific field attribute.

    `agents/director_scopes._schema_list_channels` read `field.outer_type_`,
    which exists only on Pydantic 1. On a Pydantic-2 install it returned the
    empty set, `_LIST_DELEGATED` was empty, and `_normalized_channel_value`
    coerced all seventeen op-list channels to `{}` -- so every `contact_ops`,
    `introductions` and `crowd_ops` a Director specialist wrote was dispatched,
    paid for, and discarded without a word. It had replaced a hand-written
    frozenset that was correct under BOTH majors.

    The suite never saw it: `make check` ran on Pydantic 1, where the attribute
    exists. A green gate on one major is not evidence about the other, and the
    engine ships on the other. So the rule is structural rather than a test --
    `llm.schemas` already branches once (`_fields`, `_declared`,
    `_outer_annotation`, `list_shaped_fields`) and a second branch anywhere
    else is how the two drift apart again.
    """
    for path in engine_python_paths():
        rel = path.relative_to(ROOT).as_posix()
        if rel in _PYDANTIC_BRANCH_OWNERS:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            attr = None
            if isinstance(node, ast.Attribute):
                attr = node.attr
            elif (isinstance(node, ast.Call)
                  and isinstance(node.func, ast.Name)
                  and node.func.id == "getattr"
                  and len(node.args) >= 2
                  and isinstance(node.args[1], ast.Constant)
                  and isinstance(node.args[1].value, str)):
                attr = node.args[1].value
            major = _PYDANTIC_MAJOR_ATTRS.get(attr)
            if major is None:
                continue
            errors.append(
                f"{rel}:{node.lineno}: reads {attr!r}, which exists only on "
                f"Pydantic {major}. On the other major this silently reads "
                f"nothing rather than failing. Go through llm.schemas "
                f"(_fields / _declared / list_shaped_fields), which owns the "
                f"one version branch.")


# ---------------------------------------------------------------------------
# Version agreement across the four places the supported Python is written
# ---------------------------------------------------------------------------

#: Where the supported interpreter range is stated. Four files, because three
#: of them are executed by something that cannot read the fourth: pip reads
#: `pyproject.toml`, a Windows player runs the `.bat`, everyone else runs the
#: `.sh`, and CI runs the matrix. They agreed on 3.11-3.13 in three places and
#: on 3.11-3.12 in the fourth for the whole life of the 3.13 support, so the
#: interpreter a fresh player was MOST likely to get (both launchers try 3.13
#: first) was the one no gate had ever run.
_PYPROJECT_RANGE = re.compile(
    r'^requires-python\s*=\s*"\s*>=\s*3\.(\d+)\s*,\s*<\s*3\.(\d+)\s*"',
    re.MULTILINE)
_BAT_CANDIDATES = re.compile(r"^\s*for %%V in \(([^)]*)\)", re.MULTILINE)
_SH_CANDIDATES = re.compile(r"^\s*for candidate in ([^\n;]+?)(?:;|\s*do)",
                            re.MULTILINE)
_CI_MATRIX = re.compile(r"^\s*python-version:\s*\[([^\]]*)\]", re.MULTILINE)
_VERSION_TOKEN = re.compile(r"3\.\d+")


def declared_python_series() -> list[str]:
    """`["3.11", "3.12", "3.13"]`, read from `pyproject.toml`'s own bound."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = _PYPROJECT_RANGE.search(text)
    if not match:
        return []
    low, high = int(match.group(1)), int(match.group(2))
    return ["3.%d" % minor for minor in range(low, high)]


def check_python_version_agreement(errors: list[str]) -> None:
    """`pyproject.toml`, both launchers and the CI matrix must name one range.

    `requires-python` is the declaration; the launchers are what a player
    actually runs; the matrix is the only one of the four that PROVES the range
    works. When the matrix is a subset, the versions outside it are supported
    in writing and untested in fact -- and the gap is worst at the top of the
    range, because both launchers are ordered newest-first and therefore
    select precisely the untested end.

    Reported as a set difference in both directions: a matrix entry outside
    `requires-python` is the same defect wearing the other sign.
    """
    supported = declared_python_series()
    if not supported:
        errors.append("pyproject.toml: could not read a "
                      "`requires-python = \">=3.X,<3.Y\"` bound; the launcher "
                      "and CI agreement check has nothing to compare against")
        return
    expected = set(supported)

    def report(where, found, note=""):
        if found == expected:
            return
        missing = sorted(expected - found)
        extra = sorted(found - expected)
        parts = []
        if missing:
            parts.append("does not cover " + ", ".join(missing))
        if extra:
            parts.append("names " + ", ".join(extra)
                         + " which requires-python excludes")
        errors.append(
            "%s %s (pyproject.toml declares %s)%s"
            % (where, " and ".join(parts), ", ".join(supported), note))

    bat = (ROOT / "Start_Sonder.bat").read_text(encoding="utf-8",
                                                errors="replace")
    match = _BAT_CANDIDATES.search(bat)
    report("Start_Sonder.bat's candidate list",
           set(_VERSION_TOKEN.findall(match.group(1) if match else "")))

    sh = (ROOT / "Start_Sonder.sh").read_text(encoding="utf-8",
                                              errors="replace")
    match = _SH_CANDIDATES.search(sh)
    report("Start_Sonder.sh's candidate list",
           set(_VERSION_TOKEN.findall(match.group(1) if match else "")))

    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    match = _CI_MATRIX.search(ci)
    report("the CI matrix in .github/workflows/ci.yml",
           set(_VERSION_TOKEN.findall(match.group(1) if match else "")),
           note=" -- a version outside the matrix is supported in writing and "
                "untested in fact, and both launchers pick the newest one "
                "first")


# ---------------------------------------------------------------------------
# Absolute paths in anything executable
# ---------------------------------------------------------------------------

#: A path that names one machine. Drive letters are matched only where a
#: quote or whitespace precedes them, so `C:` inside prose or a URL scheme is
#: not mistaken for one.
#: The one file allowed to contain these strings, because it is where they
#: are DEFINED. Named rather than special-cased silently, like
#: `INSTALL_ROOT_OWNER` above.
MACHINE_PATH_OWNER = "tools/project_check.py"

_MACHINE_PATHS = (
    re.compile(r"/home/[A-Za-z0-9._-]+/"),
    re.compile(r"/Users/[A-Za-z0-9._-]+/"),
    re.compile(r"""['"\s]([A-Za-z]:[\\/])"""),
    re.compile(r"\.claude/worktrees"),
)


def check_no_machine_paths_in_scripts(errors: list[str]) -> None:
    """No runnable file may name one machine's filesystem.

    Measured 2026-08-19: eleven sites across six `demo/` trees hard-coded
    `/home/<user>/Documents/Fiction-improved/Fiction`, a project name from
    before this repository was renamed, and four of them additionally named a
    git worktree that exists on nobody's disk. Those scripts could not run
    anywhere, including on the machine that wrote them -- and nothing noticed,
    because `demo/` was compiled by the Makefile and scanned by no check here.

    The rule is the path, not the directory: a driver in `demo/` derives the
    repository root from its own location exactly as an engine module does.
    Documentation is excluded (an absolute path in prose is often the point);
    `.log` and `.jsonl` transcripts are excluded because a recorded run is
    evidence of where it ran.
    """
    paths = list(repository_python_paths())
    for pattern in ("*.sh", "*.bat", "*.ps1"):
        for root in ENGINE_SOURCE_ROOTS:
            paths.extend(p for p in (ROOT / root).rglob(pattern)
                         if "__pycache__" not in p.parts)
        paths.extend(ROOT.glob(pattern))
    for path in sorted(set(paths)):
        rel = path.relative_to(ROOT).as_posix()
        if rel == MACHINE_PATH_OWNER:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            # A comment saying where something used to live, or why this rule
            # exists, is not an execution path. Both comment syntaxes, since
            # this walks `.py`, `.sh` and `.bat` alike.
            if line.lstrip()[:1] == "#" or line.lstrip()[:4].lower() == "rem ":
                continue
            for pattern in _MACHINE_PATHS:
                found = pattern.search(line)
                if found:
                    errors.append(
                        f"{rel}:{lineno} hard-codes an absolute path "
                        f"({found.group(0).strip()}); derive it from the "
                        f"file's own location -- a machine path is wrong on "
                        f"every machine but one, including after a rename")
                    break


# ---------------------------------------------------------------------------
# Documentation that names a file, or an import, that is not there
# ---------------------------------------------------------------------------

#: Docs that are maintained guidance or argument about the CURRENT tree. The
#: archive is superseded by definition and `CHANGELOG.md` is history: both are
#: SUPPOSED to name files that no longer exist.
def live_doc_paths() -> list[Path]:
    out = [ROOT / name for name in
           ("README.md", "CLAUDE.md", "AGENTS.md", "Design.md")]
    out.extend(p for p in (ROOT / "docs").rglob("*.md")
               if "archive" not in p.relative_to(ROOT / "docs").parts)
    return sorted(p for p in out if p.is_file())


def authority_doc_paths() -> list[Path]:
    """`live_doc_paths()` minus the records of one moment.

    `docs/experiments/` reports an unrepeatable run and quotes the tree as it
    stood that day; a filename in one is EVIDENCE, and correcting it would be
    falsifying the record. Excluded from the "this file must exist" rule and
    kept in the "this import must work" rule, because a broken import is bad
    advice whenever it was written.
    """
    return [p for p in live_doc_paths()
            if "experiments" not in p.relative_to(ROOT).parts]


_BACKTICKED = re.compile(r"`([^`\n]+)`")
_MD_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
#: `agents/director.py:3484-3527` is a citation, not a claim that a file named
#: `director.py:3484-3527` exists. Line numbers go stale by design here (the
#: audit documents say so in their own headers); the FILE is the claim.
_LINE_CITATION = re.compile(r":\d+(?:-\d+)?$")
#: Extensions whose presence makes a backticked token a claim about a FILE.
_PATH_SUFFIXES = (".py", ".md", ".sh", ".bat", ".js", ".css", ".html",
                  ".json", ".yml", ".yaml", ".toml", ".txt")
#: Characters that mean the token is prose, a glob, or a code expression
#: rather than one path.
_NOT_A_PATH = set("()[]{}<>,;|\"'=*?`")
#: Directories that are generated, downloaded, or a player's own data. Walking
#: them costs minutes (`.claude/worktrees` holds whole checkouts of this
#: repository) and none of them is something documentation names by filename.
_UNWALKED = {".git", ".claude", ".venv", ".venv-browser", ".pytest_cache",
             "__pycache__", "node_modules", "backdrops", "backups",
             "artefacts", "ambience"}


def _repository_files() -> tuple[set[str], set[str], set[str]]:
    """Every relative path, every directory, and every basename in the tree."""
    paths: set[str] = set()
    dirs: set[str] = set()
    names: set[str] = set()
    stack = [ROOT]
    while stack:
        here = stack.pop()
        for child in here.iterdir():
            if child.name in _UNWALKED or child.name.startswith("."):
                continue
            rel = child.relative_to(ROOT).as_posix()
            if child.is_dir():
                dirs.add(rel)
                stack.append(child)
            else:
                paths.add(rel)
                names.add(child.name)
    return paths, dirs, names


def _top_level_dirs() -> set[str]:
    return {child.name for child in ROOT.iterdir()
            if child.is_dir() and child.name not in _UNWALKED
            and not child.name.startswith(".")}


def check_docs_name_real_paths(errors: list[str]) -> None:
    """Live documentation must not name a file, or a link, that is not there.

    The class, measured 2026-08-19: the launchers were renamed
    `Start Sonder.bat` -> `Start_Sonder.bat` in `e7fee15`, and a grep for the
    new name across every `*.md` returned ZERO -- so `README.md`'s own "run
    this" instruction, the first command a macOS or Linux player types,
    produced `No such file or directory`. A rename is exactly the change that
    leaves documentation wrong, and it was the change nothing here could see.

    Three rules, each decidable, none guessing:

    1. A markdown LINK target must resolve relative to the document. This is
       the exact one: in ``[`TESTING.md`](guides/TESTING.md)`` the backticked
       half is only link text, and the parenthesised half is a promise that the
       reader's click works.
    2. A backticked token whose FIRST segment is a top-level directory here,
       and which carries a file extension, is a claim about where something
       lives, and must be true.
    3. A bare `.sh`/`.bat` name is a launcher a reader will type. Spaces are
       allowed in this one on purpose -- `Start Sonder.bat` was the wrong name,
       and a rule that skipped tokens containing a space could not see the very
       rename that motivates the check.

    Deliberately silent about a token naming some OTHER project's source, since
    its first segment is not a directory here, and about `agents/common.foo`,
    which is a module and a symbol rather than a path. `docs/archive/` and
    `CHANGELOG.md` are excluded entirely: naming a file that has since gone is
    what they are FOR, and `docs/experiments/` is excluded from this rule for
    the same reason (see `authority_doc_paths`).
    """
    paths, dirs, names = _repository_files()
    tops = _top_level_dirs()
    for path in authority_doc_paths():
        rel = path.relative_to(ROOT).as_posix()
        here = path.parent
        text = path.read_text(encoding="utf-8")
        seen: set[str] = set()
        for lineno, line in enumerate(text.splitlines(), 1):
            for target in _MD_LINK.findall(line):
                target = target.split("#")[0]
                if not target or "://" in target or target.startswith(
                        ("http", "mailto:", "#")):
                    continue
                if (here / target).exists() or ("link:" + target) in seen:
                    continue
                seen.add("link:" + target)
                errors.append(
                    f"{rel}:{lineno} links to `{target}`, which does not "
                    f"resolve. A dead link in maintained documentation is a "
                    f"rename nobody followed through.")
            for token in _BACKTICKED.findall(line):
                token = _LINE_CITATION.sub("", token.strip().rstrip(".,;:"))
                directory = token.endswith("/")
                token = token.rstrip("/")
                if not token or token in seen:
                    continue
                if token[0] in ".-/$#~" or _NOT_A_PATH & set(token):
                    continue
                if "/" in token:
                    if directory or " " in token:
                        continue      # a directory, not a file
                    if token.partition("/")[0] not in tops:
                        continue
                    if not token.endswith(_PATH_SUFFIXES):
                        continue      # a module and a symbol, not a path
                    if token.rpartition("/")[0] not in dirs:
                        # The DIRECTORY does not exist here either, so the
                        # token is a path in some other tree -- `docs/CREDITS.md`
                        # cites Directive's `docs/architecture/...` by its own
                        # repository-relative path, and that is not a claim
                        # about this one. Only a file whose parent directory is
                        # here is being said to be here.
                        continue
                    if token in paths:
                        continue
                elif token.endswith((".sh", ".bat")):
                    if token in names:
                        continue
                else:
                    continue
                seen.add(token)
                errors.append(
                    f"{rel}:{lineno} names `{token}`, which is not in the "
                    f"tree. Documentation that names a moved or renamed file "
                    f"is an instruction that fails on the reader's first try.")


_DOC_IMPORT = re.compile(
    r"^(?:from\s+([A-Za-z_][\w.]*)\s+import\s+|import\s+([A-Za-z_][\w.]*))")


def guidance_doc_paths() -> list[Path]:
    """The maintained guidance set, per `AGENTS.md`'s own definition.

    `AGENTS.md`, `Design.md` and `docs/guides/` are "current implementation
    authority", and `README.md`/`CLAUDE.md` are read as instructions by every
    human and every coding agent that arrives. An import spelled out in one of
    these is something a reader will TYPE.

    Everything else is deliberately outside: `docs/design/` argues about a
    change and quotes the spellings that existed before it
    (`DESIGN_MODULE_LAYOUT.md` reproduces `from db import q` to describe what
    the move replaced), and `docs/experiments/` records what was true on the
    day it was measured. Correcting a quotation is not a fix.
    """
    out = [ROOT / name for name in
           ("README.md", "CLAUDE.md", "AGENTS.md", "Design.md")]
    out.extend((ROOT / "docs" / "guides").glob("*.md"))
    return sorted(p for p in out if p.is_file())


def check_docs_imports_resolve(errors: list[str]) -> None:
    """An import spelled out in maintained guidance must actually work.

    `CLAUDE.md` and `AGENTS.md` both told coding agents that
    `from commit import X` "stays the universal import path" for the thirteen
    split persistence modules. Measured 2026-08-19: `import commit` raises
    `ModuleNotFoundError`, and all 256 real call sites say `persist.commit`.
    An instruction to an agent that cannot execute is worse than a missing one
    -- it is followed, and then debugged.

    Read out of BACKTICKED spans only. Unquoted prose is not code: "generator
    /import prompts" and "two import paths of very different quality" both
    contain an import statement to a regex and neither contains one to a
    reader. Only imports naming an engine package, or a bare name that used to
    be one, are judged; a doc quoting `import json` is nobody's business here.
    """
    names, by_tail = _engine_module_index()
    engine_roots = (set(SUBSYSTEM_PACKAGES) | {"agents"}
                    | set(NON_PACKAGE_ENGINE_DIRS))
    for path in guidance_doc_paths():
        rel = path.relative_to(ROOT).as_posix()
        for lineno, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), 1):
            for span in _BACKTICKED.findall(line):
                match = _DOC_IMPORT.match(span.strip())
                if not match:
                    continue
                target = match.group(1) or match.group(2) or ""
                if not target or target in names:
                    continue
                root = target.partition(".")[0]
                if root in engine_roots:
                    errors.append(
                        f"{rel}:{lineno} spells `{span.strip()}`; "
                        f"{target!r} is not a module in this tree")
                elif "." not in target and by_tail.get(target):
                    moved = " or ".join(sorted(by_tail[target]))
                    errors.append(
                        f"{rel}:{lineno} spells `{span.strip()}`; {target!r} "
                        f"is a module name from before the package move and "
                        f"does not import. It is now {moved}.")


# ---------------------------------------------------------------------------
# Turn-scoped contextvars must be cleared before background work
# ---------------------------------------------------------------------------

#: Contextvars in the two turn-scoped modules that a background job may keep.
#: Each needs a reason, because the default answer is "clear it": a job
#: inherits a COPY of the commit step's context (`core/jobs.py::submit`), so a
#: var nobody thought about rides into work that outlives the turn.
BACKGROUND_SAFE_CONTEXTVARS = {
    "last_reasoning":
        "an OUTPUT slot: every call overwrites it before anything reads it, "
        "so an inherited value is unreachable rather than stale",
    "last_finish_reason":
        "an OUTPUT slot, same as last_reasoning",
    "read_timeout_override":
        "a knob a caller sets around its own call and resets after; it names "
        "no turn, holds no sink, and cancels nothing",
}

_TURN_SCOPED_CONTEXTVAR_MODULES = ("llm/providers.py", "core/pipeline_context.py")


def _contextvar_names(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return set()
    out = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        else:
            continue
        if not isinstance(value, ast.Call):
            continue
        func = value.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(
            func, "id", "")
        if name != "ContextVar":
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                out.add(target.id)
    return out


def check_turn_scoped_contextvars_are_cleared(errors: list[str]) -> None:
    """Every contextvar in the two turn-scoped modules is cleared, or named.

    `core/jobs.py::submit` copies the WHOLE context so a job inherits the story
    language across the thread hop, and `_clear_turn_scoped_context` is the
    denylist that takes the turn's own things back out -- the live stream's
    `token_sink`, the abort `cancel_event`, sinks writing into a
    `PipelineContext` whose variants are already persisted. That function's own
    docstring records the obligation this check enforces: a new contextvar in
    `llm/providers.py` or `core/pipeline_context.py` must be added to the tuple
    or it rides into background work by DEFAULT.

    A denylist with a standing obligation and no enforcement is a denylist that
    is one commit from being incomplete, and the symptom is a background
    consolidation streaming tokens into a finished turn -- not an exception.
    The escape hatch is `BACKGROUND_SAFE_CONTEXTVARS`, which costs a sentence
    saying why the var outlives the turn safely.
    """
    try:
        jobs = ast.parse((ROOT / "core" / "jobs.py").read_text(encoding="utf-8"))
    except (OSError, SyntaxError) as exc:
        errors.append(f"core/jobs.py could not be parsed for the turn-scoped "
                      f"contextvar check: {exc}")
        return
    cleared: set[str] = set()
    for node in ast.walk(jobs):
        if (isinstance(node, ast.FunctionDef)
                and node.name == "_clear_turn_scoped_context"):
            for inner in ast.walk(node):
                if isinstance(inner, ast.Name):
                    cleared.add(inner.id)
    if not cleared:
        errors.append("core/jobs.py has no `_clear_turn_scoped_context`; the "
                      "turn-scoped contextvar guard cannot run")
        return
    for rel in _TURN_SCOPED_CONTEXTVAR_MODULES:
        for name in sorted(_contextvar_names(ROOT / rel)):
            if name in cleared or name in BACKGROUND_SAFE_CONTEXTVARS:
                continue
            errors.append(
                f"{rel} defines the contextvar {name!r}, which "
                f"core/jobs.py::_clear_turn_scoped_context does not clear. A "
                f"background job inherits a copy of the commit step's context, "
                f"so an unlisted var rides into work that outlives the turn. "
                f"Clear it there, or add it to "
                f"BACKGROUND_SAFE_CONTEXTVARS with the reason it is safe.")


# ---------------------------------------------------------------------------
# A facade patch that a sibling's own reader cannot see
# ---------------------------------------------------------------------------

def _calls_and_imports(tree: ast.AST) -> tuple[set[str], set[str]]:
    """Names this module imports by value, and names it calls bare."""
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                imported.add(alias.asname or alias.name)
    called = {node.func.id for node in ast.walk(tree)
              if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    return imported, called


def check_facade_patch_targets(errors: list[str]) -> None:
    """A test may not patch a facade name a sibling calls through its own globals.

    The narrow, decidable half of a rule that is wrong in general. Patching
    where a name is USED is the ordinary idiom and 71 correct sites in this
    suite do it, so "patch the owner, not the re-export" is not the rule. What
    IS always broken is patching the facade of a SPLIT family when a sibling of
    that family imported the name into its own globals and calls it there: the
    sibling's call resolves in `persist/commit_memory.__dict__`, never in
    `persist/commit.__dict__`, so the patch is applied, the test passes, and
    nothing was intercepted (`docs/experiments/AUDIT_COMMIT.md`).

    Zero violations when written. It exists because the failure mode is a
    GREEN test that proves nothing, which is the only kind that survives.
    """
    families = {}
    for family, (home, stem) in FACADE_FAMILIES.items():
        siblings = {}
        for name in facade_siblings(home, stem):
            path = home / (name + ".py")
            if not path.is_file():
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError):
                continue
            imported, called = _calls_and_imports(tree)
            shadowed = imported & called
            if shadowed:
                siblings[home.name + "/" + name + ".py"] = shadowed
        families[stem] = (family, siblings)

    for path in sorted((ROOT / "tests").rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        rel = path.relative_to(ROOT).as_posix()
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "setattr"
                    and len(node.args) >= 2):
                continue
            target, attr = node.args[0], node.args[1]
            if not isinstance(attr, ast.Constant) or not isinstance(
                    attr.value, str):
                continue
            if isinstance(target, ast.Name):
                module = target.id
            elif isinstance(target, ast.Attribute):
                module = target.attr
            else:
                continue
            if module not in families:
                continue
            family, siblings = families[module]
            for sibling, shadowed in sorted(siblings.items()):
                if attr.value not in shadowed:
                    continue
                owner = sibling[:-3].replace("/", ".")
                errors.append(
                    f"{rel}:{node.lineno} patches `{module}.{attr.value}` on "
                    f"the {family} facade, but {sibling} imports that name "
                    f"into its own globals and calls it there -- the patch is "
                    f"applied and intercepts nothing. Patch {owner} instead.")


# ---------------------------------------------------------------------------
# Package import cycles
# ---------------------------------------------------------------------------

PACKAGE_EDGES = ROOT / "tools" / "package_edges.json"


def _import_kind_edges(path: Path, pkg: str) -> list[tuple[str, str, str]]:
    """`(src_pkg, dst_pkg, kind)` for every cross-package import in one file.

    Three kinds, because they are three different couplings. `eager` is a
    module-level import: it must be satisfiable at import time, so it is what
    makes a cycle a cycle. `deferred` is an import inside a function body -- a
    real dependency, but one that costs nothing at import time and is how every
    existing two-cycle here is survivable. `typing` is inside
    `if TYPE_CHECKING:` and does not exist at runtime at all.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return []
    known = set(ENGINE_PACKAGE_ROOTS)
    out: list[tuple[str, str, str]] = []

    def targets(node) -> list[str]:
        if isinstance(node, ast.Import):
            return [alias.name for alias in node.names]
        if isinstance(node, ast.ImportFrom) and node.level == 0:
            return [node.module or ""]
        return []

    def walk(body, kind: str) -> None:
        for node in body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for target in targets(node):
                    dst = target.partition(".")[0]
                    if dst in known and dst != pkg:
                        out.append((pkg, dst, kind))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                walk(node.body, "deferred")
            elif isinstance(node, ast.If) and kind != "deferred":
                test = node.test
                names = {n.id for n in ast.walk(test) if isinstance(n, ast.Name)}
                inner = "typing" if "TYPE_CHECKING" in names else kind
                walk(node.body, inner)
                walk(node.orelse, kind)
            elif isinstance(node, (ast.ClassDef, ast.Try, ast.With,
                                   ast.AsyncWith, ast.For, ast.AsyncFor,
                                   ast.While)):
                walk(node.body, kind)
                for extra in ("orelse", "finalbody", "handlers"):
                    for item in getattr(node, extra, []) or []:
                        walk(getattr(item, "body", [item]), kind)
    walk(tree.body, "eager")
    return out


def package_import_graph() -> dict[str, Counter]:
    """`{kind: Counter[(src, dst)]}` over every engine package."""
    graph: dict[str, Counter] = {"eager": Counter(), "deferred": Counter(),
                                 "typing": Counter()}
    for pkg in ENGINE_PACKAGE_ROOTS:
        for path in _python_files(pkg):
            for src, dst, kind in _import_kind_edges(path, pkg):
                graph[kind][(src, dst)] += 1
    return graph


def _strongly_connected(edges) -> list[list[str]]:
    """Tarjan. Returns only the cycles -- components of more than one node."""
    successors: dict[str, set[str]] = defaultdict(set)
    nodes = set()
    for src, dst in edges:
        successors[src].add(dst)
        nodes.update((src, dst))
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    counter = [0]
    out: list[list[str]] = []

    def strongconnect(node: str) -> None:
        # Iterative: the recursion depth is bounded by the package count, but
        # an explicit stack is what keeps this readable when a family grows.
        work = [(node, iter(sorted(successors[node])))]
        index[node] = low[node] = counter[0]
        counter[0] += 1
        stack.append(node)
        on_stack.add(node)
        while work:
            head, children = work[-1]
            advanced = False
            for child in children:
                if child not in index:
                    index[child] = low[child] = counter[0]
                    counter[0] += 1
                    stack.append(child)
                    on_stack.add(child)
                    work.append((child, iter(sorted(successors[child]))))
                    advanced = True
                    break
                if child in on_stack:
                    low[head] = min(low[head], index[child])
            if advanced:
                continue
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[head])
            if low[head] == index[head]:
                component = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.append(member)
                    if member == head:
                        break
                if len(component) > 1:
                    out.append(sorted(component))

    for node in sorted(nodes):
        if node not in index:
            strongconnect(node)
    return sorted(out)


def package_edge_report() -> dict:
    """The whole measurement, in the shape the baseline file stores."""
    graph = package_import_graph()
    eager = sorted(graph["eager"])
    return {
        "cycles": _strongly_connected(eager),
        "edges": {
            "%s->%s" % pair: {
                "eager": graph["eager"].get(pair, 0),
                "deferred": graph["deferred"].get(pair, 0),
                "typing": graph["typing"].get(pair, 0),
            }
            for pair in sorted(set(graph["eager"]) | set(graph["deferred"])
                               | set(graph["typing"]))
        },
    }


def check_package_edge_budget(errors: list[str]) -> None:
    """No NEW import cycle between subsystem packages.

    Not a budget on edges. `web -> *` and `agents -> *` are supposed to grow --
    they are the orchestration layers, and a check that made adding a legitimate
    dependency a fight would be waived within a week. What must not grow is the
    set of packages that cannot be imported independently of each other, and
    that is measurable exactly: the strongly connected components of the EAGER
    (module-level, non-`TYPE_CHECKING`) import graph.

    Measured across one day of green gates -- `a6d823f` to `73a380a` -- three
    edges gained eager module-level imports inside existing cycles
    (`agents->persist` 8/3 -> 11/4, `story->mind` 6/2 -> 9/3,
    `persist->story` 47/18 -> 52/19). Nothing anywhere built an import graph, so
    the direction of travel was invisible; `DESIGN_MODULE_LAYOUT.md` declined an
    import linter and in the same paragraph named its table "the baseline a
    future cleanup should measure itself against", and that table had already
    drifted (33 for `persist->story` against 52 measured).

    The baseline in `tools/package_edges.json` is GENERATED, never hand-written:
    `python tools/project_check.py --write-package-edges`. Shrinking a cycle is
    always allowed; the file is only rewritten deliberately.
    """
    report = package_edge_report()
    if not PACKAGE_EDGES.is_file():
        errors.append(
            f"{PACKAGE_EDGES.relative_to(ROOT).as_posix()} is missing; "
            f"regenerate it with "
            f"`python tools/project_check.py --write-package-edges`")
        return
    try:
        baseline = json.loads(PACKAGE_EDGES.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        errors.append(f"tools/package_edges.json could not be read: {exc}")
        return
    allowed = [set(cycle) for cycle in baseline.get("cycles", [])]
    for cycle in report["cycles"]:
        members = set(cycle)
        if any(members <= known for known in allowed):
            continue
        errors.append(
            "a new eager import cycle between packages: "
            + " <-> ".join(cycle)
            + ". A module-level import is what makes a cycle real -- move the "
            "import into the function that needs it, or invert the dependency. "
            "If the cycle is genuinely intended, regenerate the baseline with "
            "`python tools/project_check.py --write-package-edges` and say why "
            "in the commit message.")


#: Every module that writes memory rows, and how each one keeps a row's
#: identity meaningful. `memories.event_key` is what `_upsert_memory`
#: reconciles on (`mind/memory_write.py`), and the rule it has to satisfy is
#: NOT "be unique" -- it is "come back identical when the same beat is
#: written again", or every `memory_summaries.support` clause citing the row
#: is stranded (`mind/memory_summaries.derive_summary_support`).
#:
#: Two ways to satisfy it, and a writer must pick one deliberately:
#:   * delete the turn's rows first, so nothing is reconciled by key at all;
#:   * mint a key from something that survives a copy -- content, or a scope
#:     that is re-derived the same way on the other side.
#:
#: The list exists because the third option is invisible: a new writer that
#: reconciles by a key minted from a row id works perfectly until the chat is
#: branched, and then silently writes a second row instead of updating the
#: first. Adding a writer means adding a line here and saying which way it
#: goes.
MEMORY_WRITERS = {
    "mind/memory_snapshot.py": "restore: deletes the whole chat's rows first",
    "persist/commit_memory_write.py":
        "calls delete_turn_memories(turn.id) before the batch",
    "story/greetings.py": "keys on a sha1 of the seed's content",
    "world/offscreen.py": "keys on a chat-scoped agent/epoch identity",
    "persist/commit_background.py": "keys on the charter's own identity",
    "world/charter_history.py":
        "keys on stable charter/body plus the re-derived evidence source id",
    "story/journey_history.py":
        "keys on hashes of the grounded memory content, independent of row ids",
    "web/app.py": "the manual add route passes no event_key, so it inserts",
}

#: `event_key` minted from the TURN ROW's id, which does not survive a copy.
#: Fine where it lives, because every site is entered through
#: `commit_memories`, which deletes by `turn_id` first -- and that is exactly
#: the coupling worth pinning, since it is an argument in a comment rather
#: than anything the code enforces.
TURN_ID_MINT_OWNER = "persist/commit_memory.py"


def check_memory_identity_writers(errors: list[str]) -> None:
    """Memory identities stay re-derivable, and new writers say how."""
    import ast as _ast

    # Both directions. A registry that only catches ADDITIONS rots: a module
    # that stops writing memories leaves a line here claiming it still does,
    # and the next reader trusts it. This repo has paid for that shape before.
    actual: set[str] = set()
    for root in ENGINE_SOURCE_ROOTS:
        for path in _python_files(root):
            rel = path.relative_to(ROOT).as_posix()
            # Engine writers only. A test builds rows to drive a path and is
            # never the thing a branch copies; requiring every fixture to
            # declare an identity strategy would make the registry noise and
            # teach people to append to it without reading it.
            if rel.startswith(("tests/", "extensions/", "tools/")):
                continue
            # The definition site is not a caller. Skipped rather than listed,
            # so that `add_memory` growing an internal call to the batch
            # writer does not read as an undeclared writer.
            if rel == "mind/memory_write.py":
                continue
            try:
                tree = _ast.parse(path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError):
                continue
            writes = False
            for node in _ast.walk(tree):
                if not isinstance(node, _ast.Call):
                    continue
                func = node.func
                name = (func.attr if isinstance(func, _ast.Attribute)
                        else getattr(func, "id", ""))
                if name in ("add_memories_batch", "add_memory"):
                    writes = True
                if name in ("_stable_event_key", "stable_event_key") \
                        and node.args:
                    first = node.args[0]
                    if isinstance(first, _ast.Attribute) \
                            and first.attr == "id" \
                            and isinstance(first.value, _ast.Name) \
                            and first.value.id == "turn" \
                            and rel != TURN_ID_MINT_OWNER:
                        errors.append(
                            f"{rel}:{node.lineno} mints an event_key from "
                            "`turn.id`, which does not survive a branch or an "
                            f"import. Only {TURN_ID_MINT_OWNER} may, because "
                            "every one of its sites is entered through "
                            "commit_memories, which deletes the turn's rows "
                            "first. Key on content or a re-derivable scope, "
                            "or delete before you write.")
            if writes:
                actual.add(rel)
            if writes and rel not in MEMORY_WRITERS:
                errors.append(
                    f"{rel} writes memory rows but is not in "
                    "`MEMORY_WRITERS`. Say how it keeps `event_key` "
                    "re-derivable -- delete the turn's rows first, or mint "
                    "from something that survives a copy. A key minted from "
                    "a row id reconciles correctly until the chat is "
                    "branched, then silently writes a duplicate.")

    for rel in sorted(set(MEMORY_WRITERS) - actual):
        errors.append(
            f"`MEMORY_WRITERS` lists {rel}, which no longer writes memory "
            "rows. Drop the entry: a registry that describes what a module "
            "used to do is worse than no registry, because it is believed.")


def main() -> int:
    errors: list[str] = []
    check_undefined_names(errors)
    check_extension_manifests(errors)
    check_extension_imports(errors)
    check_facade_import_direction(errors)
    check_conftest_not_imported(errors)
    check_minimum_python_syntax(errors)
    check_pydantic_major_reads_are_owned(errors)
    check_engine_imports_resolve(errors)
    check_asgi_targets(errors)
    check_duplicate_python_symbols(errors)
    check_duplicate_dict_keys(errors)
    check_install_root_derivations(errors)
    check_no_dead_prompts(errors)
    check_patch_debris(errors)
    check_empty_tests(errors)
    check_cross_file_duplicate_definitions(errors)
    check_prompt_schema_ops(errors)
    check_time_channel_vocabulary(errors)
    check_prompt_card_parts(errors)
    check_specialist_prompt_chunks(errors)
    check_prose_author_chunks(errors)
    check_language_pack_surfaces(errors)
    check_python_version_agreement(errors)
    check_no_machine_paths_in_scripts(errors)
    check_docs_name_real_paths(errors)
    check_docs_imports_resolve(errors)
    check_turn_scoped_contextvars_are_cleared(errors)
    check_facade_patch_targets(errors)
    check_package_edge_budget(errors)
    check_memory_identity_writers(errors)
    check_generated_map(errors)

    if errors:
        print("Project structure checks failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Project structure checks passed.")
    return 0


if __name__ == "__main__":
    # `--source-roots` exists so `make compile` can read the inventory instead
    # of keeping a fifth copy of it. It prints one directory per line and runs
    # no check.
    if "--source-roots" in sys.argv[1:]:
        print("\n".join(ENGINE_SOURCE_ROOTS))
        sys.exit(0)
    # The package-cycle baseline is GENERATED. Writing it by hand is how a
    # baseline comes to record what someone believed rather than what is there
    # -- which is what happened to the table in DESIGN_MODULE_LAYOUT.md.
    if "--write-package-edges" in sys.argv[1:]:
        PACKAGE_EDGES.write_text(
            json.dumps(package_edge_report(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        print("wrote %s" % PACKAGE_EDGES.relative_to(ROOT).as_posix())
        sys.exit(0)
    sys.exit(main())
